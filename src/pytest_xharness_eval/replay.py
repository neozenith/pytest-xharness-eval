"""Rebuild cached results from their session logs without re-running anything (ADR 0023, ADR 0032).

A captured cell is its session log plus the CLI's envelope, both kept verbatim.
Everything else in a ``result.json`` (the ledger, usage, pricing, record census,
skill coverage) is derived, so it can be derived again after the plugin changes:

    uv run -m pytest_xharness_eval.replay .xharness_eval_cache

rewrites every ``results/{skill}/{harness}/{model}[--{effort}]/{run}/{session}/result.json``
from its ``log.jsonl``, re-prices it from the price record in effect on its run's day, re-annotates
skill coverage against the skill's current tree and ignore rules, rewrites each
session's ``history.json`` (verdict, timestamps and wall clock are kept; metrics
are recomputed), and runs the combine step (``report/``). No CLI is invoked and
nothing is spent.

Pointed at a legacy ``<skill>/evals/captured`` directory instead, it migrates that
evidence into the project's cache root and then rebuilds; that transitional path is
:mod:`~pytest_xharness_eval.runtime.legacy`, so what is left here is the rebuild and
the command line that drives it (ADR 0040).
"""

from __future__ import annotations

# Standard Library
import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.derive import pricing, skillcov
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.harness.threads import SubagentMismatch
from pytest_xharness_eval.model.catalogue import ModelSpec
from pytest_xharness_eval.model.layout import SessionDir
from pytest_xharness_eval.model.runresult import CaseRef
from pytest_xharness_eval.model.suite import find_case
from pytest_xharness_eval.runtime import pipeline
from pytest_xharness_eval.runtime.legacy import LegacyCapture
from pytest_xharness_eval.runtime.settings import (
    DEFAULT_CACHE_DIR,
    INI_CACHE_DIR,
    Settings,
    find_rootpath,
    ini_value,
)

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.model.catalogue import Catalogue
    from pytest_xharness_eval.model.runresult import RunResult

log = logging.getLogger(__name__)


def rebuild_result(
    session_dir: Path,
    table: pricing.PriceTable,
    files: list[skillcov.SkillFile],
    skill: str,
    settings: Settings | None = None,
    *,
    run_date: date | None,
    stored: Path | None = None,
) -> RunResult:
    """Re-derive one session's result from its captured log and stored envelope.

    ``run_date`` is the day the session's ``{run}`` stamp names, so the capture is priced
    from the record in effect when it ran rather than from today's (ADR 0050). ``stored`` is
    the record read back, ``result.json`` unless a quarantined run's ``unfolded.json`` is
    being retried (ADR 0072): its keys are the same.
    """
    session = SessionDir(session_dir)
    old = json.loads((stored or session.result).read_text(encoding="utf-8"))
    if not session.log.is_file():
        raise FileNotFoundError(f"no captured session log beside {session.result}: {session.log.name}")
    workspace = Path(old.get("workspace") or "")
    files_written = list(old.get("files_written") or [])
    # Each dialect knows what its own log is missing and recovers it from the stored result:
    # replay no longer reconstructs a Claude envelope, and an unregistered harness raises
    # rather than being read as Codex (ADR 0034).
    agent = harness.get(str(old.get("harness") or ""))
    result = agent.session_from_capture(session, old).to_result(workspace, files_written)
    # The same derivations the live cell runs, in the same order (ADR 0034). The case that
    # produced the run is not in the log: carry it forward, or derive it from the suite
    # that defines a case with the recorded name (ADR 0025).
    settings = settings or Settings.from_cache(session_dir)
    case = CaseRef.stored(old.get("case")) or case_meta(session, skill, agent, settings)
    # The rung the CLI was asked for is not in the log either, and unlike the case it cannot
    # be recovered from the suite: the matrix may have moved since. Carry the stored value
    # forward, so a rebuild reports the effort the run actually had rather than the effort
    # today's matrix would give it (ADR 0049).
    effort = old.get("effort")
    # The treatment the same way, for the same reason: the case's treatments may have moved
    # since, and the run had the overlay it had (ADR 0055).
    treatment = old.get("treatment")
    # A kill at the wall is not in the log either: it was observed at the spawn. Carry it
    # forward, so a rebuild still knows the run was cut off and how idle it was (ADR 0064).
    timed_out, idle = old.get("timed_out_after_s"), old.get("idle_before_timeout_s")
    if isinstance(timed_out, int):
        harness.mark_timed_out(result, timed_out, float(idle) if isinstance(idle, int | float) else None)
    # The case names the skill under test, none for a scenario case (ADR 0074); a capture whose
    # case is lost is annotated against its session's skill coordinate, as it always was.
    return pipeline.derive(
        result,
        table=table,
        run_date=run_date,
        uncased_skill=skill,
        skill_files=files,
        case=case,
        effort=str(effort) if effort else None,
        treatment=str(treatment) if treatment else None,
        spec=stored_spec(old, settings.catalogue()),
    )


def stored_spec(old: dict[str, Any], catalogue: Catalogue) -> ModelSpec | None:
    """The catalogue facts a stored result carried, or the catalogue's own for a capture that predates them.

    Carried forward first, so a rebuild reports what the run was archived as (ADR 0057).
    A capture written before the catalogue existed gets today's entry, which is the same
    answer because a family tier is frozen at release; a model the catalogue never
    described stays None rather than failing a replay of history.
    """
    line, tier, released = old.get("line"), old.get("family_tier"), old.get("released")
    if isinstance(line, str) and isinstance(tier, int) and isinstance(released, str):
        return ModelSpec(
            id=str(old.get("model") or ""), line=line, family_tier=tier, released=date.fromisoformat(released)
        )
    return catalogue.get(str(old.get("harness") or ""), str(old.get("model") or ""))


def case_meta(session: SessionDir, skill: str, agent: harness.Harness, settings: Settings) -> CaseRef | None:
    """The :class:`CaseRef` recovered from the skill's suites, or None when it cannot be.

    The case name comes from the session's own metrics record; the suites sit at
    ``<skills root>/<skill>/evals/eval_*.py`` and are searched by
    :func:`~pytest_xharness_eval.model.suite.find_case`, which is the same loader
    collection imports a suite with.

    ``agent`` is the harness that produced this session, so the recovered reference can
    carry the prompt that harness would render for the case's task -- the same string the
    live cell sent (ADR 0044). Recovering only the task and leaving the prompt empty would
    make a replayed record differ from the live one in a field the report displays.
    """
    previous = CellMetrics.stored(session.history)
    name = (previous.case if previous else None) or ""
    if not name:
        return None
    found = find_case(settings.skill_dir(skill) / "evals", name)
    if found is None:
        return None
    suite_path, case = found
    if case.task is None:
        # A generated case's task belongs to the scenario, which only the stored result names.
        return None
    return CaseRef.of(
        case, settings.suite_ref(suite_path), agent.prompt(skill=case.skill, task=case.task), subject=skill
    )


def rebuild(
    cache: Path,
    prices: list[str] | None = None,
    ignore: list[str] | None = None,
    design_tokens: Path | None = None,
    inline: bool = False,
) -> list[Path]:
    """Rebuild every result under ``<cache>/results/``, rewrite each ``history.json``, run the combine step.

    ``ignore`` and ``prices`` lines are added to the project's ``xharness_skill_ignore``
    and ``xharness_prices`` lines, in the same ini-line forms. The project's config is
    resolved through the same :class:`Settings` a live sweep uses (ADR 0034).
    """
    settings = Settings.from_cache(cache, prices=prices, ignore=ignore)
    table = settings.price_table()
    catalogs: dict[str, list[skillcov.SkillFile]] = {}

    rewritten: list[Path] = []
    still_unfolded: list[str] = []
    for session in settings.cache.sessions():
        retrying = not session.result.is_file() and session.unfolded.is_file()
        if not session.result.is_file() and not retrying:
            continue
        skill = session.skill
        if skill not in catalogs:
            skill_dir = settings.skill_dir(skill)
            catalogs[skill] = skillcov.catalog(skill_dir, ignore=settings.skill_ignore) if skill_dir.is_dir() else []
        stored = session.unfolded if retrying else None
        try:
            result = rebuild_result(
                session.path, table, catalogs[skill], skill, settings, run_date=session.run_date, stored=stored
            )
        except SubagentMismatch as exc:
            if not retrying:
                raise
            still_unfolded.append(f"{session.path.relative_to(cache)}: {exc}")
            continue
        result.write(session.result)
        if retrying:
            # The harness now folds what it once refused: the capture is an ordinary result.
            session.unfolded.unlink()
        rewritten.append(session.result)

        previous = CellMetrics.stored(session.history)
        if previous is not None:
            # The verdict, node and clock are the live run's and cannot be re-derived; the
            # metrics around them are rebuilt by the same call the live cell makes.
            pipeline.record_metrics(result, session, outcome=previous.outcome, cache=settings.cache)
        coverage = result.skill_coverage
        log.info(
            "rebuilt %s: %d turns, %s",
            session.path.relative_to(cache),
            result.turns,
            coverage.summary if coverage else None,
        )

    report_page = page.write(settings.cache, design_tokens=design_tokens, inline=inline)
    log.info("report: %s%s", report_page, " (inline)" if inline else "")
    if still_unfolded:
        # Everything else is rebuilt and the page written first, so a quarantined capture never
        # holds the rest hostage; it still fails the replay, because it is still unaccounted for.
        raise harness.RunError(
            f"{len(still_unfolded)} quarantined session(s) still do not fold (ADR 0072):\n" + "\n".join(still_unfolded)
        )
    return rewritten


def cache_root_for(legacy: LegacyCapture) -> Path:
    """The cache root a legacy capture directory migrates into: its project's ``xharness_cache_dir``."""
    return find_rootpath(legacy.path) / str(ini_value(legacy.path, INI_CACHE_DIR) or DEFAULT_CACHE_DIR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebuild cached eval results from their session logs; no CLI runs, nothing is spent."
    )
    parser.add_argument(
        "cache",
        type=Path,
        help="the project's cache root (.xharness_eval_cache), or a legacy <skill>/evals/captured directory to migrate",
    )
    parser.add_argument(
        "--price",
        action="append",
        default=[],
        metavar="LINE",
        help=(
            "extra xharness_prices line, '<harness>/<model>: input=<usd/MTok> output=<usd/MTok> ...' "
            "(repeatable; the project's pytest config lines apply as well)"
        ),
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "extra xharness_skill_ignore line, '<pattern>' or '<skill>: <pattern>' (repeatable; "
            "the project's pytest config lines apply as well)"
        ),
    )
    parser.add_argument(
        "--design-tokens", type=Path, default=None, metavar="FILE", help="design tokens JSON to theme report.html"
    )
    parser.add_argument("--inline", action="store_true", help="embed every result, log and the tokens into report.html")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse the command line, migrate a legacy directory if that is what it names, and rebuild."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    target = args.cache
    if not target.is_dir():
        raise SystemExit(f"not a directory: {target}")
    legacy = LegacyCapture.found_at(target)
    if legacy is not None:
        target = cache_root_for(legacy)
        count = legacy.migrate_into(target)
        log.info("migrated %d session(s) from %s into %s", count, legacy.path, target)
    rebuilt = rebuild(
        target,
        prices=args.price,
        ignore=args.ignore,
        design_tokens=args.design_tokens,
        inline=args.inline,
    )
    log.info("rebuilt %d result(s) under %s", len(rebuilt), target)


if __name__ == "__main__":
    main()
