"""One group's metric as an :class:`~pytest_xharness_eval.model.analysis.Estimate`, by its kind.

The estimator follows the metric's :class:`~pytest_xharness_eval.model.metrics.MetricKind`,
the same split the report's aggregates make (ADR 0071):

* ``RATE`` (the verdict, ``passed``) -- the pass rate with its Wilson interval, honest at
  every ``n``.
* ``SPREAD`` (cost, tokens, turns, time) -- heavy-tailed, so the median with a percentile
  bootstrap interval; one runaway session cannot drag it.
* ``FRACTION`` and ``RARE`` -- bounded or rare counts, so the mean with a bootstrap interval.
* ``cost_per_pass`` -- total cost over passes, bootstrapped by resampling whole sessions;
  errors are skipped (no attempt, so neither a pass nor a costed miss).
* ``wasted_cost`` -- the summed cost of the failed sessions, bootstrapped the same way.
"""

from __future__ import annotations

# Standard Library
import random
from typing import TYPE_CHECKING, Final

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.analyze.samples import COST_PER_PASS, PASSED, WASTED_COST, kind_of, record_value
from pytest_xharness_eval.model.analysis import Estimate
from pytest_xharness_eval.model.metrics import MetricKind
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence

    # Our Libraries
    from pytest_xharness_eval.analyze.samples import Samples
    from pytest_xharness_eval.analyze.stats import Stat

#: The centre each kind is summarised by.
_STAT: Final[dict[MetricKind, tuple[str, Stat]]] = {
    MetricKind.RATE: ("mean", stats.mean),
    MetricKind.SPREAD: ("median", stats.median),
    MetricKind.FRACTION: ("mean", stats.mean),
    MetricKind.RARE: ("mean", stats.mean),
}


def centre(kind: MetricKind) -> tuple[str, Stat]:
    """The name and function of the statistic a kind of metric is centred on."""
    return _STAT[kind]


def of_values(
    values: Sequence[float], kind: MetricKind, *, seed: int, confidence: float, resamples: int = stats.RESAMPLES
) -> Estimate:
    """An estimate over plain values of a metric of ``kind``."""
    n = len(values)
    if kind is MetricKind.RATE:
        if not n:
            return Estimate(point=None, low=None, high=None, n=0, method="wilson")
        low, high = stats.wilson_interval(sum(values), n, confidence)
        return Estimate(point=sum(values) / n, low=low, high=high, n=n, method="wilson")
    name, stat = centre(kind)
    method = f"{name}/bootstrap"
    if not n:
        return Estimate(point=None, low=None, high=None, n=0, method=method)
    low, high = stats.bootstrap_ci(values, stat, seed=seed, resamples=resamples, confidence=confidence)
    return Estimate(point=stat(values), low=low, high=high, n=n, method=method)


def of_cells(
    cells: Sequence[Sequence[float]],
    kind: MetricKind,
    *,
    seed: int,
    confidence: float,
    resamples: int = stats.RESAMPLES,
) -> Estimate:
    """An estimate that weighs each cell equally: the mean of the cells' centres.

    Pooling raw samples across cells lets the most-run cell dominate (a harness run twice as
    often counts twice); here each cell contributes its own centre once. The interval is a
    two-level bootstrap: cells are resampled, then each drawn cell's samples. ``n`` counts the
    samples; with one cell it is that cell's ordinary estimate.
    """
    kept = [list(c) for c in cells if c]
    if len(kept) == 1:
        return of_values(kept[0], kind, seed=seed, confidence=confidence, resamples=resamples)
    n = sum(len(c) for c in kept)
    method = "cell-mean/bootstrap"
    if not kept:
        return Estimate(point=None, low=None, high=None, n=0, method=method)
    _, stat = centre(kind)
    rng = random.Random(seed)
    draws = [
        stats.mean([stat(rng.choices(c, k=len(c))) for c in rng.choices(kept, k=len(kept))]) for _ in range(resamples)
    ]
    low, high = stats.percentile_interval(draws, confidence)
    return Estimate(point=stats.mean([stat(c) for c in kept]), low=low, high=high, n=n, method=method)


def _cost_per_pass(samples: Samples, *, seed: int, confidence: float, resamples: int) -> Estimate:
    # An error never attempted the task: skipped on both sides, never a costed non-pass.
    pairs = [
        (cost, passed)
        for r in samples
        if (cost := record_value(r, "cost")) is not None and (passed := record_value(r, PASSED)) is not None
    ]
    point = samples.cost_per_pass()
    method = "ratio/bootstrap"
    if point is None:
        return Estimate(point=None, low=None, high=None, n=len(pairs), method=method)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        drawn = rng.choices(pairs, k=len(pairs))
        passes = sum(p for _, p in drawn)
        if passes:
            draws.append(sum(c for c, _ in drawn) / passes)
    low, high = stats.percentile_interval(draws, confidence)
    return Estimate(point=point, low=low, high=high, n=len(pairs), method=method)


def _total(values: Sequence[float]) -> float:
    return float(sum(values))


def _wasted_cost(samples: Samples, *, seed: int, confidence: float, resamples: int) -> Estimate:
    """The failed records' summed cost, its interval from resampling every session (a fail's cost or 0)."""
    point = samples.wasted_cost()
    wasted = [
        (cost if r.verdict == Verdict.FAIL.value else 0.0)
        for r in samples
        if (cost := record_value(r, "cost")) is not None
    ]
    if point is None or not wasted:
        return Estimate(point=point, low=point, high=point, n=len(wasted), method="sum")
    low, high = stats.bootstrap_ci(wasted, _total, seed=seed, resamples=resamples, confidence=confidence)
    return Estimate(point=point, low=low, high=high, n=len(wasted), method="sum/bootstrap")


def estimate(
    samples: Samples, metric: str, *, seed: int, confidence: float = 0.95, resamples: int = stats.RESAMPLES
) -> Estimate:
    """``metric`` over ``samples``, by the estimator its kind calls for (module docstring)."""
    if metric == COST_PER_PASS:
        return _cost_per_pass(samples, seed=seed, confidence=confidence, resamples=resamples)
    if metric == WASTED_COST:
        return _wasted_cost(samples, seed=seed, confidence=confidence, resamples=resamples)
    return of_values(samples.values(metric), kind_of(metric), seed=seed, confidence=confidence, resamples=resamples)
