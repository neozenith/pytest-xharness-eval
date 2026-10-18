"""``index.json``'s ``important_metrics``: every cell's samples reduced to its Important Metrics (ADR 0071).

A cell is one skill, case, harness, model, effort and treatment, and each graded session of
it is one sample. This module groups the stored per-session records into cells and reduces
each declared metric over them by its kind's aggregates, so the report reads finished
numbers and holds no second copy of the arithmetic.

The grouping is the report's own partition: the page groups its session rows by the same
six fields (``groupKey`` in ``report-ui/src/lib/summary.ts``). Every filter the page offers
is one of those fields or a property of the model, so a filter can drop whole cells but
never split one, and an aggregate written here is still true of what the page shows.
"""

from __future__ import annotations

# Standard Library
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

# Our Libraries
from pytest_xharness_eval.emit.index import UNKNOWN_CASE, aggregate_history
from pytest_xharness_eval.model.metrics import IMPORTANT_METRICS, ImportantMetric
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable

    # Our Libraries
    from pytest_xharness_eval.emit.metrics import CellMetrics
    from pytest_xharness_eval.model.layout import CacheLayout

#: A cell's identity: skill, case, harness, model, effort, treatment.
CellKey = tuple[str | None, str, str, str, str | None, str | None]


def is_sample(record: CellMetrics) -> bool:
    """Whether a stored record is a sample: a session that was graded, whatever it graded to.

    A dry run measured nothing, and a record whose verdict this version cannot read says
    nothing about how the cell went, so neither is a sample of it.
    """
    verdict = Verdict.stored(record.verdict)
    return verdict is not None and verdict is not Verdict.DRY_RUN


def cell_key(record: CellMetrics) -> CellKey:
    """The cell a record is a sample of, spelled as ``report/index.json``'s rows spell it."""
    return (
        record.skill,
        record.case or UNKNOWN_CASE,
        record.harness,
        record.model,
        record.effort or None,
        record.treatment or None,
    )


def scenario_outcomes(cache: CacheLayout, suite: str, case: str) -> dict[str, tuple[int, int]]:
    """``(failed, sampled)`` per scenario id, over every stored sample of one case (ADR 0074).

    ``suite`` is the suite file as records name it, relative to the project root, so a case
    keeps its history when the project is checked out somewhere else and two skills'
    same-named suites never share one. A ``fail`` counts as
    failed; an ``error`` does not, because a run that never sat the test says nothing about
    whether the scenario breaks the subject.
    """
    out: dict[str, tuple[int, int]] = {}
    for record in aggregate_history(cache):
        if not (record.scenario and record.case == case and record.suite == suite):
            continue
        verdict = Verdict.stored(record.verdict)
        if verdict not in (Verdict.PASS, Verdict.FAIL):
            continue
        failed, sampled = out.get(record.scenario, (0, 0))
        out[record.scenario] = (failed + (verdict is Verdict.FAIL), sampled + 1)
    return out


def _order(key: CellKey) -> tuple[str, ...]:
    return tuple(part or "" for part in key)


@dataclass(frozen=True, slots=True, kw_only=True)
class CellSamples:
    """One cell's samples reduced: how many there were, and each Important Metric's aggregates."""

    skill: str | None
    case: str
    harness: str
    model: str
    effort: str | None
    treatment: str | None
    samples: int
    #: Metric id -> aggregate name -> value, in declaration order.
    metrics: dict[str, dict[str, float | int | None]] = field(default_factory=dict)

    @classmethod
    def of(cls, key: CellKey, records: list[CellMetrics], declared: Iterable[ImportantMetric]) -> Self:
        skill, case, harness, model, effort, treatment = key
        rows = [r.to_dict() for r in records]
        return cls(
            skill=skill,
            case=case,
            harness=harness,
            model=model,
            effort=effort,
            treatment=treatment,
            samples=len(records),
            metrics={metric.id: metric.summarise(rows) for metric in declared},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "case": self.case,
            "harness": self.harness,
            "model": self.model,
            "effort": self.effort,
            "treatment": self.treatment,
            "samples": self.samples,
            "metrics": self.metrics,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportantMetrics:
    """The declared metric set and every cell's aggregates over it: ``index.json``'s ``important_metrics``."""

    declared: tuple[ImportantMetric, ...]
    cells: list[CellSamples]

    @classmethod
    def of(cls, records: Iterable[CellMetrics], declared: tuple[ImportantMetric, ...] = IMPORTANT_METRICS) -> Self:
        """Group ``records`` into cells, keep the samples, and reduce each cell; cells in key order."""
        grouped: dict[CellKey, list[CellMetrics]] = defaultdict(list)
        for record in records:
            if is_sample(record):
                grouped[cell_key(record)].append(record)
        return cls(
            declared=declared,
            cells=[CellSamples.of(key, grouped[key], declared) for key in sorted(grouped, key=_order)],
        )

    @classmethod
    def stored(cls, cache: CacheLayout) -> Self:
        """The aggregates over every session record the cache holds."""
        return cls.of(aggregate_history(cache))

    def to_dict(self) -> dict[str, Any]:
        return {"metrics": [m.to_dict() for m in self.declared], "cells": [c.to_dict() for c in self.cells]}
