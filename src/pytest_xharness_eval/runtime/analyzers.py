"""Running the suites' analyzers over a cache: once per sweep, and again on demand (ADR 0075).

An analyzer is a question across samples -- has this skill version regressed, which model
tier carries it, where is the cost-quality front -- so it runs after every cell, over every
stored record and not just this sweep's. Two entry points reach this one function: the
plugin at the end of a session, with that session's records as ``current``, and ``python -m
pytest_xharness_eval.analysis`` over a cache with nothing current, so a hill-climbing loop
can re-ask its questions without paying for a run.

Each suite's analyzers see the samples of that suite alone, matched by the suite file's
path relative to the project root, the way the scenario history is (ADR 0074): an analyzer
in ``skills/x/evals/eval_gates.py`` is about that file's cases -- never another skill's
``eval_gates.py`` -- and ``@analyzer(cases=...)`` narrows it further.
"""

from __future__ import annotations

# Standard Library
from dataclasses import replace
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import analyze
from pytest_xharness_eval.analyze import Analysis, Samples
from pytest_xharness_eval.emit.findings import AnalysisReport
from pytest_xharness_eval.model.clock import now_iso
from pytest_xharness_eval.model.suite import EvalSuite

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.emit.metrics import CellMetrics
    from pytest_xharness_eval.model.findings import Finding
    from pytest_xharness_eval.runtime.settings import Settings


def _of_suite(samples: Samples, suite: str) -> Samples:
    return samples.where(suite=suite)


def analyze_suites(
    settings: Settings,
    suites: Iterable[Path],
    current: Iterable[CellMetrics] = (),
    *,
    seed: int = 0,
) -> AnalysisReport | None:
    """Every analyzer the ``suites`` declare, run over the cache; None when they declare none.

    Each finding is named ``<suite path>::<analyzer>``, so two suites may both have an
    ``analyze_cost`` without their findings colliding in ``analysis.json``. An analyzer that
    raises anything but a failed assertion is a broken analyzer: it is reported as a failed
    finding marked ``error`` with its exception, never swallowed, and the other analyzers
    and the session's report still run -- a paid sweep must not lose its combine step to it.
    """
    loaded = [EvalSuite.load(path) for path in sorted({p.resolve() for p in suites})]
    if not any(suite.analyzers for suite in loaded):
        return None
    history, now = Samples.stored(settings.cache), Samples.of(current)
    findings: list[Finding] = []
    for suite in loaded:
        ref = settings.suite_ref(suite.path)
        scoped = Analysis(history=_of_suite(history, ref), current=_of_suite(now, ref), seed=seed)
        for spec in suite.analyzers:
            # ``run_one`` turns every outcome, a broken analyzer included, into a finding.
            finding = analyze.run_one(spec, scoped)
            findings.append(replace(finding, analyzer=f"{ref}::{finding.analyzer}"))
    return AnalysisReport.of(findings, generated_at=now_iso())


def finding_lines(report: AnalysisReport) -> list[str]:
    """The terminal's lines for a report: one per finding, its message indented beneath a failure."""
    lines = []
    for finding in report.findings:
        lines.append(f"  {'pass' if finding.passed else 'FAIL':<5} {finding.analyzer}")
        if not finding.passed:
            lines += [f"        {line}" for line in finding.message.splitlines()[:12]]
    return lines
