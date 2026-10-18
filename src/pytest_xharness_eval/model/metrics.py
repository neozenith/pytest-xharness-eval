"""The Important Metrics: what a cell is judged by, and how its samples reduce (ADR 0071).

Pass or fail is one signal among many. A cell is also judged by what it cost, how much of
the window it needed, whether it delegated or compacted, how long it took, and whether it
reached the skill files it was meant to. :data:`IMPORTANT_METRICS` is that set, declared
once, here, so ``emit/`` aggregates it, the report renders it, and the glossary names it
from one list rather than three copies that drift.

A **sample** is one graded session of a cell: same skill, case, harness, model, effort and
treatment. Repeated runs of a cell are repeated samples of one experiment. Each metric
names a :class:`MetricKind`, and the kind fixes which few :class:`Aggregate` values its
samples reduce to:

* :attr:`MetricKind.SPREAD` -- cost, tokens, turns, wall clock, throughput. Heavy-tailed,
  so the median and the interquartile range, which one runaway session cannot drag.
* :attr:`MetricKind.FRACTION` -- shares of a whole and percentages of the window. Bounded,
  so the mean with the extremes either side.
* :attr:`MetricKind.RARE` -- counts of rare events. The mean, and the share of samples in
  which the event happened at all: "how often does it compact?".
* :attr:`MetricKind.RATE` -- the verdict. The share of samples graded the metric's
  ``counts`` word (a pass, or an error) with its Wilson 95% interval, which is honest at
  every sample size: at ``n = 1`` it is simply wide. An ``error`` is no attempt at the
  task, so it is never a sample of the pass rate -- neither a pass nor a fail -- and is
  measured by the ``errors`` rate instead, where every graded sample counts.

Every kind also reports ``n``: the samples that carried a value. A metric a sample did not
record (a capture from before the field existed, an unpriced run) is left out of ``n``,
never counted as zero.
"""

from __future__ import annotations

# Standard Library
import math
import statistics
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

# Our Libraries
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Mapping


class MetricKind(StrEnum):
    """The shape of a metric's distribution, which decides its aggregates."""

    SPREAD = "spread"
    FRACTION = "fraction"
    RARE = "rare"
    RATE = "rate"


class Aggregate(StrEnum):
    """One number a cell's samples reduce to; the key it is stored under."""

    N = "n"
    MEDIAN = "median"
    P25 = "p25"
    P75 = "p75"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    SHARE = "share"
    PASS_RATE = "pass_rate"
    #: The headline of a rate that counts errors: never stored under ``pass_rate``, which it is not.
    ERROR_RATE = "error_rate"
    CI_LOW = "ci_low"
    CI_HIGH = "ci_high"


class Unit(StrEnum):
    """What a metric's value is measured in, so a reader formats it without guessing."""

    USD = "usd"
    TOKENS = "tokens"
    PERCENT = "percent"
    SHARE = "share"
    COUNT = "count"
    MS = "ms"
    TOKENS_PER_SEC = "tokens_per_sec"


#: Which aggregates each kind reports, headline first: a reader showing one number shows the first.
AGGREGATES: Final[dict[MetricKind, tuple[Aggregate, ...]]] = {
    MetricKind.SPREAD: (Aggregate.MEDIAN, Aggregate.P25, Aggregate.P75, Aggregate.N),
    MetricKind.FRACTION: (Aggregate.MEAN, Aggregate.MIN, Aggregate.MAX, Aggregate.N),
    MetricKind.RARE: (Aggregate.MEAN, Aggregate.SHARE, Aggregate.N),
    MetricKind.RATE: (Aggregate.PASS_RATE, Aggregate.CI_LOW, Aggregate.CI_HIGH, Aggregate.N),
}

#: The normal quantile of a two-sided 95% interval.
_Z95: Final = 1.959963984540054


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportantMetric:
    """One measure a cell is judged by.

    ``field`` names a key of the per-session metrics record (``history.json``). Where ``per``
    is set, the value is ``field / per``, so a coverage share is declared from the two counts
    the record already carries rather than stored a third time.
    """

    #: Short and stable: the report's column key and sort param, never its printed label.
    id: str
    label: str
    field: str
    kind: MetricKind
    unit: Unit
    #: The question this metric answers about a skill, as the report's tooltip states it.
    why: str
    per: str | None = None
    #: For a :attr:`MetricKind.RATE`: the verdict that counts as 1. ``PASS`` reads the pass
    #: rate, where an error is no sample at all; ``ERROR`` reads the error rate, where every
    #: graded verdict is one.
    counts: Verdict = Verdict.PASS

    @property
    def rate_key(self) -> Aggregate:
        """The key a rate's headline is stored under: ``pass_rate``, or ``error_rate`` for the error rate."""
        return Aggregate.ERROR_RATE if self.counts is Verdict.ERROR else Aggregate.PASS_RATE

    @property
    def aggregates(self) -> tuple[Aggregate, ...]:
        return tuple(self.rate_key if a is Aggregate.PASS_RATE else a for a in AGGREGATES[self.kind])

    def value(self, record: Mapping[str, Any]) -> float | None:
        """This metric's value in one session's record, or None when the record does not carry it."""
        raw = record.get(self.field)
        if self.kind is MetricKind.RATE:
            return rate_value(Verdict.stored(str(raw or "")), self.counts)
        if not isinstance(raw, int | float) or isinstance(raw, bool):
            return None
        if self.per is None:
            return float(raw)
        denominator = record.get(self.per)
        if not isinstance(denominator, int | float) or not denominator:
            return None
        return raw / denominator

    def summarise(self, records: Iterable[Mapping[str, Any]]) -> dict[str, float | int | None]:
        """This metric's aggregates over a cell's samples, keyed by :class:`Aggregate` value."""
        values = [v for r in records if (v := self.value(r)) is not None]
        return summarise(self.kind, values, rate_key=self.rate_key)

    def to_dict(self) -> dict[str, Any]:
        """The declaration as the report reads it: the aggregates are spelled out, never re-derived."""
        return {
            "id": self.id,
            "label": self.label,
            "field": self.field,
            "per": self.per,
            "kind": self.kind.value,
            "unit": self.unit.value,
            "why": self.why,
            "counts": self.counts.value,
            "aggregates": [a.value for a in self.aggregates],
        }


def rate_value(verdict: Verdict | None, counts: Verdict = Verdict.PASS) -> float | None:
    """One verdict as a sample of the rate of ``counts``: 1.0, 0.0, or None when it is no sample.

    A dry run and an unreadable word are never samples. An error is a sample only of the
    error rate: it did not attempt the task, so counting it as a fail would charge the skill
    for a session limit or a stalled harness (ADR 0063).
    """
    if verdict is None or verdict is Verdict.DRY_RUN:
        return None
    if verdict is Verdict.ERROR and counts is not Verdict.ERROR:
        return None
    return float(verdict is counts)


def _round(value: float) -> float:
    return round(value, 6)


def summarise(
    kind: MetricKind, values: list[float], *, rate_key: Aggregate = Aggregate.PASS_RATE
) -> dict[str, float | int | None]:
    """``values`` reduced to ``kind``'s aggregates; every aggregate but ``n`` is None with no values.

    ``rate_key`` names a rate's headline: ``pass_rate``, or ``error_rate`` for the error rate.
    """
    keys = tuple(rate_key if a is Aggregate.PASS_RATE else a for a in AGGREGATES[kind])
    out: dict[str, float | int | None] = {a.value: None for a in keys}
    n = len(values)
    out[Aggregate.N.value] = n
    if not n:
        return out
    found: dict[Aggregate, float]
    if kind is MetricKind.SPREAD:
        ordered = sorted(values)
        q1, _, q3 = statistics.quantiles(ordered, n=4, method="inclusive") if n > 1 else (ordered[0],) * 3
        found = {Aggregate.MEDIAN: statistics.median(ordered), Aggregate.P25: q1, Aggregate.P75: q3}
    elif kind is MetricKind.FRACTION:
        found = {Aggregate.MEAN: statistics.fmean(values), Aggregate.MIN: min(values), Aggregate.MAX: max(values)}
    elif kind is MetricKind.RARE:
        found = {Aggregate.MEAN: statistics.fmean(values), Aggregate.SHARE: sum(v >= 1 for v in values) / n}
    else:
        low, high = wilson(sum(values), n)
        found = {rate_key: sum(values) / n, Aggregate.CI_LOW: low, Aggregate.CI_HIGH: high}
    return out | {a.value: _round(v) for a, v in found.items()}


def wilson(passes: float, n: int) -> tuple[float, float]:
    """The Wilson score 95% interval for ``passes`` successes in ``n`` trials."""
    p = passes / n
    centre = (p + _Z95**2 / (2 * n)) / (1 + _Z95**2 / n)
    half = _Z95 * math.sqrt(p * (1 - p) / n + _Z95**2 / (4 * n * n)) / (1 + _Z95**2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


#: The Important Metrics, in the order the report shows them. Add one here and every reader
#: picks it up: the aggregation, the report's columns and the glossary check (ADR 0071).
IMPORTANT_METRICS: Final[tuple[ImportantMetric, ...]] = (
    ImportantMetric(
        id="cost",
        label="cost",
        field="estimated_cost_usd",
        kind=MetricKind.SPREAD,
        unit=Unit.USD,
        why="the felt cost of the skill with this model, from the plugin's price table",
    ),
    ImportantMetric(
        id="tokens",
        label="billed tokens",
        field="accumulative_billed_tokens",
        kind=MetricKind.SPREAD,
        unit=Unit.TOKENS,
        why="every billed token over every call: an order-of-magnitude proxy for effort",
    ),
    ImportantMetric(
        id="context",
        label="peak context",
        field="context_window_pct",
        kind=MetricKind.FRACTION,
        unit=Unit.PERCENT,
        why="is the outcome reachable in a small part of the window?",
    ),
    ImportantMetric(
        id="cache",
        label="cache reads",
        field="cache_read_share",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="the share of prompt tokens served from the cache: does the run keep its prefix stable?",
    ),
    ImportantMetric(
        id="subagents",
        label="subagents",
        field="subagents",
        kind=MetricKind.RARE,
        unit=Unit.COUNT,
        why="did the main agent delegate to manage its context?",
    ),
    ImportantMetric(
        id="subagent_tokens",
        label="subagent tokens",
        field="subagent_token_share",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="the subagents' share of the billed tokens: how much of the work was delegated",
    ),
    ImportantMetric(
        id="subagent_cost",
        label="subagent cost",
        field="subagent_cost_share",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="the subagents' share of the cost, each priced at its own model's rates",
    ),
    ImportantMetric(
        id="compactions",
        label="compactions",
        field="compactions",
        kind=MetricKind.RARE,
        unit=Unit.COUNT,
        why="did the task need the context compacted to finish?",
    ),
    ImportantMetric(
        id="turns",
        label="turns",
        field="turns",
        kind=MetricKind.SPREAD,
        unit=Unit.COUNT,
        why="model calls: is the model stuck fighting itself or a bad instruction?",
    ),
    ImportantMetric(
        id="skill_triggered",
        label="triggered",
        field="skill_triggered",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="does the skill under test reliably trigger? A skill case only; a scenario has no skill",
    ),
    ImportantMetric(
        id="skill_loaded",
        label="files loaded",
        field="skill_files_loaded",
        per="skill_files",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="does the model reliably read the skill files it is expected to?",
    ),
    ImportantMetric(
        id="skill_run",
        label="scripts run",
        field="skill_scripts_run",
        per="skill_scripts",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="does the model reliably run the skill scripts it is expected to?",
    ),
    ImportantMetric(
        id="thinking",
        label="thinking share",
        field="reasoning_share",
        kind=MetricKind.FRACTION,
        unit=Unit.SHARE,
        why="reasoning over output tokens: does a higher effort rung change how much it thinks?",
    ),
    ImportantMetric(
        id="throughput",
        label="tok/s",
        field="output_tokens_per_sec",
        kind=MetricKind.SPREAD,
        unit=Unit.TOKENS_PER_SEC,
        why="output tokens per second of API time; the session view splits it by model",
    ),
    ImportantMetric(
        id="ttft",
        label="first token",
        field="ttft_ms",
        kind=MetricKind.SPREAD,
        unit=Unit.MS,
        why="time to the first token: how long before the model starts answering",
    ),
    ImportantMetric(
        id="wall",
        label="wall clock",
        field="wall_ms",
        kind=MetricKind.SPREAD,
        unit=Unit.MS,
        why="the other felt cost: how long the reader waits",
    ),
    ImportantMetric(
        id="verdict",
        label="pass rate",
        field="verdict",
        kind=MetricKind.RATE,
        unit=Unit.SHARE,
        why="did it work? A pass rate over the attempted samples, never a single run's word",
    ),
    ImportantMetric(
        id="errors",
        label="error rate",
        field="verdict",
        kind=MetricKind.RATE,
        unit=Unit.SHARE,
        counts=Verdict.ERROR,
        why="how often the cell never reached a grade it earned: harness, limit or grader errors. Lower is better",
    ),
)
