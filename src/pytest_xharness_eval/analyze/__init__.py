"""The Analyzer: questions asked across cells, runs and subject versions, after the sweep.

A layer above :mod:`pytest_xharness_eval.emit` -- it reads the stored
:class:`~pytest_xharness_eval.emit.metrics.CellMetrics` records -- and below
:mod:`pytest_xharness_eval.runtime`. A suite declares ``@analyzer`` functions named
``analyze_*``; :func:`run` calls each with one :class:`Analysis` and turns what happened
into a :class:`~pytest_xharness_eval.model.analysis.Finding`:

* returned normally -- the finding passed;
* raised ``AssertionError`` (every ``Analysis.expect_*`` raises an :class:`AnalysisFailure`,
  which is one) -- the finding failed, with the message and any evidence attached;
* raised anything else -- an error in the analyzer, which propagates: a broken analyzer is
  not a failed expectation, and is never recorded as one.
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
    Direction,
    Estimate,
    Finding,
    ParetoPoint,
    analyzer,
)

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
    """Run one analyzer over ``analysis`` (narrowed to its ``cases``, if it names any)."""
    fresh = replace(analysis, notes={})
    scoped = fresh.for_cases(spec.cases) if spec.cases else fresh
    try:
        spec(scoped)
    except AnalysisFailure as failure:
        return Finding(
            analyzer=spec.name,
            passed=False,
            message=str(failure),
            comparisons=failure.comparisons,
            details=scoped.notes | failure.details,
        )
    except AssertionError as failure:
        message = str(failure) or type(failure).__name__
        return Finding(analyzer=spec.name, passed=False, message=message, details=dict(scoped.notes))
    return Finding(analyzer=spec.name, passed=True, details=dict(scoped.notes))


def run(analyzers: Sequence[AnalyzerSpec], analysis: Analysis) -> list[Finding]:
    """Every analyzer's finding, in the order given; an error other than a failed assertion propagates."""
    return [run_one(spec, analysis) for spec in analyzers]
