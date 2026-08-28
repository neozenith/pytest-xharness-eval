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
evidence into the project's cache root (the original directory is left untouched)
and then rebuilds.
"""

from __future__ import annotations

# Standard Library
import argparse
import hashlib
import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import harness, pipeline, pricing, report, skillcov
from pytest_xharness_eval.case import EvalCase
from pytest_xharness_eval.runresult import CaseRef
from pytest_xharness_eval.settings import (
    DEFAULT_CACHE_DIR,
    INI_CACHE_DIR,
    Settings,
    find_rootpath,
    ini_value,
)

if TYPE_CHECKING:
    # Standard Library
    from types import ModuleType

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

log = logging.getLogger(__name__)


def rebuild_result(
    session_dir: Path,
    table: dict[str, pricing.Rates],
    files: list[skillcov.SkillFile],
    skill: str,
    settings: Settings | None = None,
) -> RunResult:
    """Re-derive one session's result from its captured log and stored envelope."""
    result_path = session_dir / pipeline.RESULT_NAME
    old = json.loads(result_path.read_text(encoding="utf-8"))
    log_path = session_dir / pipeline.LOG_NAME
    if not log_path.is_file():
        raise FileNotFoundError(f"no captured session log beside {result_path}: {log_path.name}")
    workspace = Path(old.get("workspace") or "")
    files_written = list(old.get("files_written") or [])
    # Each dialect knows what its own log is missing and recovers it from the stored result:
    # replay no longer reconstructs a Claude envelope, and an unregistered harness raises
    # rather than being read as Codex (ADR 0034).
    agent = harness.get(str(old.get("harness") or ""))
    result = agent.session_from_capture(session_dir, old).to_result(workspace, files_written)
    # The same derivations the live cell runs, in the same order (ADR 0034). The case that
    # produced the run is not in the log: carry it forward, or derive it from the suite
    # that defines a case with the recorded name (ADR 0025).
    case = CaseRef.stored(old.get("case")) or case_meta(
        session_dir, skill, settings or Settings.from_cache(session_dir)
    )
    return pipeline.derive(result, table=table, skill=skill, skill_files=files, case=case)


def case_meta(session_dir: Path, skill: str, settings: Settings) -> CaseRef | None:
    """The :class:`CaseRef` recovered from the skill's suites, or None when it cannot be.

    The case name comes from the session's ``history.json``; the suites sit at
    ``<skills root>/<skill>/evals/eval_*.py``.
    """
    hist = {}
    hist_path = session_dir / "history.json"
    if hist_path.is_file():
        try:
            hist = json.loads(hist_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hist = {}
    name = str(hist.get("case") or "")
    if not name:
        return None
    evals_dir = settings.skill_dir(skill) / "evals"
    for suite_path in sorted(evals_dir.glob("eval_*.py")):
        try:
            module = _load_suite(suite_path)
        except Exception as exc:  # noqa: BLE001 - a broken suite must not block replaying the others
            log.warning("could not import %s to recover case metadata: %s", suite_path.name, exc)
            continue
        for value in vars(module).values():
            if isinstance(value, EvalCase) and value.name == name:
                try:
                    suite = str(suite_path.relative_to(Path.cwd()))
                except ValueError:
                    suite = str(suite_path)
                return CaseRef.of(value, suite)
    return None


def _load_suite(path: Path) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    spec = importlib.util.spec_from_file_location(f"_xharness_replay_{path.stem}_{digest}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load eval module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_ts_of(value: str) -> str:
    """An ISO ``at`` timestamp as the path-safe run stamp (``20260826T042617Z``)."""
    digits = re.sub(r"[^0-9T]", "", value.split("+")[0].split(".")[0])
    return f"{digits}Z" if re.fullmatch(r"\d{8}T\d{6}", digits) else "00000000T000000Z"


def is_legacy_captured(path: Path) -> bool:
    """A pre-0032 ``<skill>/evals/captured`` directory: ``<case>/<harness>-<session>.result.json`` rows."""
    return path.name == "captured" and any(path.glob("*/*.result.json"))


def _legacy_history(path: Path) -> dict[str, dict[str, Any]]:
    """The latest legacy ``history.jsonl`` record per session id."""
    by_session: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return by_session
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        sid = str(rec.get("session_id") or "")
        if sid:
            by_session[sid] = rec
    return by_session


def migrate_legacy(captured: Path, cache: Path) -> int:
    """Copy a legacy captured directory into the cache's ``results/`` tree; the original is untouched.

    Returns the number of sessions migrated. Already-migrated sessions are skipped, so
    the migration is idempotent.
    """
    skill = captured.resolve().parent.parent.name
    by_session = _legacy_history(captured / "history.jsonl")

    migrated = 0
    for result_path in sorted(captured.glob("*/*.result.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        sid = str(result.get("session_id") or "")
        harness = str(result.get("harness") or "unknown")
        model = str(result.get("model") or "unknown")
        hist = dict(by_session.get(sid) or {})
        hist.pop("captured", None)
        run_ts = _run_ts_of(str(hist.get("at") or ""))
        session_dir = cache / report.RESULTS_DIR / skill / harness / model / run_ts / sid
        if (session_dir / "result.json").is_file():
            continue
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
        stem = result_path.name.removesuffix(".result.json")
        legacy_log = result_path.with_name(f"{stem}.jsonl")
        if legacy_log.is_file():
            (session_dir / "log.jsonl").write_bytes(legacy_log.read_bytes())
        if hist:
            hist["cache"] = str(cache)
            (session_dir / "history.json").write_text(json.dumps(hist, sort_keys=True) + "\n", encoding="utf-8")
        migrated += 1
        log.info("migrated %s -> %s", result_path.relative_to(captured), session_dir.relative_to(cache))
    return migrated


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
    for result_path in sorted((cache / report.RESULTS_DIR).glob("*/*/*/*/*/result.json")):
        session_dir = result_path.parent
        skill = session_dir.relative_to(cache / report.RESULTS_DIR).parts[0]
        if skill not in catalogs:
            skill_dir = settings.skill_dir(skill)
            catalogs[skill] = skillcov.catalog(skill_dir, ignore=settings.skill_ignore) if skill_dir.is_dir() else []
        result = rebuild_result(session_dir, table, catalogs[skill], skill, settings)
        result.write(result_path)
        rewritten.append(result_path)

        hist_path = session_dir / pipeline.HISTORY_NAME
        if hist_path.is_file():
            try:
                old = json.loads(hist_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                old = {}
            # The verdict, node and clock are the live run's and cannot be re-derived; the
            # metrics around them are rebuilt by the same call the live cell makes.
            pipeline.record_metrics(
                result,
                session_dir,
                node=str(old.get("node") or ""),
                verdict=str(old.get("verdict") or ""),
                wall_ms=int(old.get("wall_ms") or 0),
                started_at=str(old.get("at") or ""),
                cache=cache,
            )
        coverage = result.skill_coverage
        log.info(
            "rebuilt %s: %d turns, %s",
            session_dir.relative_to(cache),
            result.turns,
            coverage.summary if coverage else None,
        )

    page = report.write(cache, design_tokens=design_tokens, inline=inline)
    log.info("report: %s%s", page, " (inline)" if inline else "")
    return rewritten


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


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    target = args.cache
    if not target.is_dir():
        raise SystemExit(f"not a directory: {target}")
    if is_legacy_captured(target):
        cache = find_rootpath(target) / str(ini_value(target, INI_CACHE_DIR) or DEFAULT_CACHE_DIR)
        count = migrate_legacy(target, cache)
        log.info("migrated %d session(s) from %s into %s", count, target, cache)
        target = cache
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
