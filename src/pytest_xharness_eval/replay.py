"""Rebuild cached results from their session logs without re-running anything (ADR 0023, ADR 0032).

A captured cell is its session log plus the CLI's envelope, both kept verbatim.
Everything else in a ``result.json`` (the ledger, usage, pricing, record census,
skill coverage) is derived, so it can be derived again after the plugin changes:

    uv run -m pytest_xharness_eval.replay .xharness_eval_cache

rewrites every ``results/{skill}/{harness}/{model}/{run}/{session}/result.json``
from its ``log.jsonl``, re-prices it with the current price tables, re-annotates
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
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.derive import pricing, skillcov
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.emit.metrics import CellMetrics
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
    from pytest_xharness_eval.model.runresult import RunResult

log = logging.getLogger(__name__)


def rebuild_result(
    session_dir: Path,
    table: dict[str, pricing.Rates],
    files: list[skillcov.SkillFile],
    skill: str,
    settings: Settings | None = None,
) -> RunResult:
    """Re-derive one session's result from its captured log and stored envelope."""
    session = SessionDir(session_dir)
    old = json.loads(session.result.read_text(encoding="utf-8"))
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
    case = CaseRef.stored(old.get("case")) or case_meta(session, skill, settings or Settings.from_cache(session_dir))
    return pipeline.derive(result, table=table, skill=skill, skill_files=files, case=case)


def case_meta(session: SessionDir, skill: str, settings: Settings) -> CaseRef | None:
    """The :class:`CaseRef` recovered from the skill's suites, or None when it cannot be.

    The case name comes from the session's own metrics record; the suites sit at
    ``<skills root>/<skill>/evals/eval_*.py`` and are searched by
    :func:`~pytest_xharness_eval.model.suite.find_case`, which is the same loader
    collection imports a suite with.
    """
    previous = CellMetrics.stored(session.history)
    name = (previous.case if previous else None) or ""
    if not name:
        return None
    found = find_case(settings.skill_dir(skill) / "evals", name)
    if found is None:
        return None
    suite_path, case = found
    try:
        suite = str(suite_path.relative_to(Path.cwd()))
    except ValueError:
        suite = str(suite_path)
    return CaseRef.of(case, suite)


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
    for session in settings.cache.sessions():
        if not session.result.is_file():
            continue
        skill = session.skill
        if skill not in catalogs:
            skill_dir = settings.skill_dir(skill)
            catalogs[skill] = skillcov.catalog(skill_dir, ignore=settings.skill_ignore) if skill_dir.is_dir() else []
        result = rebuild_result(session.path, table, catalogs[skill], skill, settings)
        result.write(session.result)
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
            "extra xharness_prices line, '<model>: input=<usd/MTok> output=<usd/MTok> ...' "
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
