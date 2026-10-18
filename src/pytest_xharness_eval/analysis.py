"""Re-run every suite's analyzers over a cache, without running a cell (ADR 0075).

    uv run -m pytest_xharness_eval.analysis <cache dir> [--suite eval_x.py ...] [--seed N]

The free half of a hill-climbing loop: edit the skill or tool, sweep the cells that matter,
then ask this what changed -- as often as needed, at no cost, over every record the cache
holds. Without ``--suite`` it runs the analyzers of every ``eval_*.py`` under the project's
skills root. It writes ``report/analysis.json``, prints one line per finding, and exits 1
when any analyzer failed, so a script or an agent can branch on the answer.
"""

from __future__ import annotations

# Standard Library
import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.runtime.analyzers import analyze_suites, finding_lines
from pytest_xharness_eval.runtime.settings import Settings

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pytest_xharness_eval.analysis", description=__doc__.split("\n")[0])
    parser.add_argument("cache", type=Path, help="the project's .xharness_eval_cache directory")
    parser.add_argument("--suite", type=Path, action="append", default=[], help="an eval_*.py to analyze (repeatable)")
    parser.add_argument("--seed", type=int, default=0, help="the seed every resampling statistic draws from")
    args = parser.parse_args(argv)
    settings = Settings.from_cache(args.cache)
    suites = args.suite or sorted(settings.skills_root.glob("*/evals/eval_*.py"))
    report = analyze_suites(settings, suites, seed=args.seed)
    if report is None:
        sys.stdout.write("no analyzers declared in: " + ", ".join(str(s) for s in suites) + "\n")
        return 0
    report.write(settings.cache.analysis)
    sys.stdout.write("\n".join([*finding_lines(report), f"  analysis: {settings.cache.analysis}"]) + "\n")
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - the module's command-line entry point
    raise SystemExit(main())
