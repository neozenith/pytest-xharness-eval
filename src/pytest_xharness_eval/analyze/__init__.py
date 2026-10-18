"""The Analyzer: questions asked across cells, runs and subject versions, after the sweep.

A layer above :mod:`pytest_xharness_eval.emit` -- it reads the stored
:class:`~pytest_xharness_eval.emit.metrics.CellMetrics` records -- and below
:mod:`pytest_xharness_eval.runtime`. A suite declares ``@analyzer`` functions named
``analyze_*``; :func:`run` calls each with one :class:`Analysis` and turns what happened
into a :class:`~pytest_xharness_eval.model.analysis.Finding`:

* returned normally -- the finding passed;
* raised ``AssertionError`` (every ``Analysis.expect_*`` raises an :class:`AnalysisFailure`,
  which is one) -- the finding failed, with the message and any evidence attached;
* raised anything else -- an error in the analyzer: a failed finding marked ``ERROR``
  with the exception named, because a broken analyzer is not a failed expectation.
"""

from __future__ import annotations

# Standard Library
from dataclasses import replace
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.analyze.analysis import Analysis, AnalysisFailure, Unbalanced
from pytest_xharness_eval.analyze.samples import (
    CELL_FIELDS,
    COST_PER_PASS,
    ENVIRONMENT,
    PASSED,
    WASTED_COST,
    Samples,
)
from pytest_xharness_eval.model.analysis import (
    AnalyzerSpec,
    Change,
    Comparison,
    Estimate,
    Finding,
    ParetoPoint,
    analyzer,
)
from pytest_xharness_eval.model.metrics import Direction
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence

__all__ = [
    "CELL_FIELDS",
    "COST_PER_PASS",
    "ENVIRONMENT",
    "PASSED",
    "WASTED_COST",
    "Analysis",
    "AnalysisFailure",
    "AnalyzerSpec",
    "Change",
    "Comparison",
    "Direction",
    "Estimate",
    "Finding",
    "ParetoPoint",
    "Samples",
    "Unbalanced",
    "analyzer",
    "run",
    "run_one",
    "stats",
]


def run_one(spec: AnalyzerSpec, analysis: Analysis) -> Finding:
    """Run one analyzer over ``analysis`` (narrowed to its ``cases``, if it names any), whatever it raises.

    The one place an analyzer's outcome becomes a finding, classified by
    :meth:`~pytest_xharness_eval.model.verdict.Verdict.of_exception` as a cell's grader is:
    a failed assertion fails the finding with its message and evidence; anything else is a
    broken analyzer, a failed finding whose message starts ``ERROR`` and names the
    exception, never swallowed and never an ``INTERNALERROR`` (ADR 0075).
    """
    fresh = replace(analysis, notes={})
    scoped = fresh.for_cases(spec.cases) if spec.cases else fresh
    try:
        spec(scoped)
    except Exception as exc:  # noqa: BLE001 - suite code: every outcome is reported as a finding
        if Verdict.of_exception(exc) is Verdict.ERROR:
            return Finding(
                analyzer=spec.name,
                passed=False,
                message=f"ERROR {type(exc).__name__}: {exc}",
                details={"error": type(exc).__name__},
            )
        if isinstance(exc, AnalysisFailure):
            return Finding(
                analyzer=spec.name,
                passed=False,
                message=str(exc),
                comparisons=exc.comparisons,
                details=scoped.notes | exc.details,
            )
        message = str(exc) or type(exc).__name__
        return Finding(analyzer=spec.name, passed=False, message=message, details=dict(scoped.notes))
    return Finding(analyzer=spec.name, passed=True, details=dict(scoped.notes))


def run(analyzers: Sequence[AnalyzerSpec], analysis: Analysis) -> list[Finding]:
    """Every analyzer's finding, in the order given; a broken analyzer is an errored finding, not a raise."""
    return [run_one(spec, analysis) for spec in analyzers]
