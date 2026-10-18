"""Freeze a generated scenario into a committed regression fixture (ADR 0074).

    uv run -m pytest_xharness_eval.promote <source> <evals dir> [--name NAME]

``<source>`` is either a scenario directory under ``<cache>/scenarios/`` or a session
directory under ``<cache>/results/`` whose run measured one (the cell that failed). The
scenario's bytes are copied to ``<evals dir>/fixtures/<name>/`` and its provenance --
generator, version, parameters, fingerprint, and the session it was promoted from -- to
``<evals dir>/fixtures/<name>.provenance.json`` beside it, never inside it, so the agent of
every later run sees only the files.

Promotion writes bytes, not parameters: the generator that made the scenario will change,
and a regression fixture that re-generated itself would drift with it. A suite then runs
every promoted fixture with :class:`~pytest_xharness_eval.model.generators.Promoted`.
"""

from __future__ import annotations

# Standard Library
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.layout import CacheLayout, SessionDir
from pytest_xharness_eval.model.runresult import CaseRef
from pytest_xharness_eval.model.scenario import Provenance, Scenario

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence


def scenario_of_session(session_dir: Path) -> tuple[Path, dict[str, Any]]:
    """The stored scenario directory a session ran on, and what promoting it should record about the session.

    Raises:
        ValueError: if the session measured a committed fixture, which has nothing to promote.
        FileNotFoundError: if the scenario's stored bytes are gone from the cache.
    """
    session = SessionDir(session_dir)
    stored = json.loads(session.result.read_text(encoding="utf-8"))
    case = CaseRef.stored(stored.get("case"))
    if case is None or not case.scenario:
        raise ValueError(f"{session_dir} ran on a committed fixture, not a generated scenario; nothing to promote")
    cache = CacheLayout.holding(session_dir)
    store = cache.scenario_store(case.suite, case.name)
    found = store.stored().get(case.scenario)
    if found is None:
        raise FileNotFoundError(f"scenario {case.scenario} is no longer stored under {store.root}")
    history = CellMetrics.stored(session.history)
    return found, {
        "session": str(session_dir),
        "harness": stored.get("harness"),
        "model": stored.get("model"),
        "verdict": history.verdict if history else None,
        "failure": history.failure if history else None,
        "case": case.name,
        "suite": case.suite,
    }


def promote(source: Path, evals_dir: Path, name: str | None = None) -> Path:
    """Copy the scenario ``source`` names into ``<evals_dir>/fixtures/<name>/`` with its provenance beside it."""
    session_facts: dict[str, Any] = {}
    if SessionDir(source).result.is_file():
        source, session_facts = scenario_of_session(source)
    scenario = Scenario.promoted(source)
    fixtures = evals_dir / "fixtures"
    target = fixtures / (name or scenario.id)
    if target.exists():
        raise FileExistsError(f"{target} already exists; promote under another --name rather than overwrite it")
    scenario.write(target)
    replace(scenario.provenance(), promoted_from=session_facts).write(Provenance.path_for(target))
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pytest_xharness_eval.promote", description=__doc__.split("\n")[0])
    parser.add_argument("source", type=Path, help="a <cache>/scenarios/... directory, or a <cache>/results/... session")
    parser.add_argument("evals_dir", type=Path, help="the suite's evals/ directory")
    parser.add_argument("--name", help="the committed fixture's directory name (default: the scenario id)")
    args = parser.parse_args(argv)
    target = promote(args.source, args.evals_dir, args.name)
    sys.stdout.write(f"promoted to {target}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - the module's command-line entry point
    raise SystemExit(main())
