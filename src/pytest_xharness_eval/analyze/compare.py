"""A candidate against a baseline, cell by matched cell, with the false-discovery rate held.

The rules, each one a pitfall it closes:

* **Matched cells only.** Both sides are grouped by the same cell fields and only keys
  present on *both* sides are compared; a cell one side never ran is not compared at all.
  Pooling across cells would let a shift in *which* cells ran masquerade as a change in
  the subject. Grouping by ``scenario`` splits by fingerprint, so a scenario whose bytes
  changed between the two sides is not matched either.
* **Strata, never pools.** A coarser grouping (by family tier, by model) still matches
  whole cells, and a stratum's change is the mean of its cells' differences with each
  cell weighed once, so an uneven mix of cells cannot reverse the sign (Simpson's paradox).
* **Insufficient below ``min_n``.** A cell with fewer than ``min_n`` samples on either side
  is :attr:`~pytest_xharness_eval.model.findings.Change.INSUFFICIENT`, with no statistics.
* **Many cells, one error budget.** Every sufficient cell gets a two-sided p-value (Fisher
  exact for a rate, a permutation test of the kind's centre otherwise); the p-values are
  Benjamini-Hochberg adjusted together, and a cell changes only when its q-value is within
  ``1 - confidence`` *and* the bootstrap interval of the difference excludes zero.
  Everything else is :attr:`~pytest_xharness_eval.model.findings.Change.INCONCLUSIVE`.
"""

from __future__ import annotations

# Standard Library
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.analyze.estimate import centre, of_cells, of_values
from pytest_xharness_eval.analyze.sampleset import CELL_FIELDS, COST_PER_PASS, WASTED_COST, kind_of
from pytest_xharness_eval.model.findings import Change, Comparison, Estimate
from pytest_xharness_eval.model.metrics import Direction, MetricKind

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence

    # Our Libraries
    from pytest_xharness_eval.analyze.sampleset import Samples


@dataclass(frozen=True, slots=True, kw_only=True)
class Arms:
    """The two sides of a comparison and the labels a report names them by."""

    baseline: Samples
    candidate: Samples
    baseline_label: str = "baseline"
    candidate_label: str = "candidate"


def _test(a: list[float], b: list[float], kind: MetricKind, seed: int) -> tuple[float, str]:
    if kind is MetricKind.RATE:
        return stats.fisher_exact_p(int(sum(a)), len(a), int(sum(b)), len(b)), "fisher"
    name, stat = centre(kind)
    return stats.permutation_p(a, b, stat, seed=seed), f"permutation({name})"


def _p_better(a: list[float], b: list[float], kind: MetricKind, direction: Direction, seed: int) -> float:
    if kind is MetricKind.RATE:
        p = stats.p_better(int(sum(a)), len(a), int(sum(b)), len(b), seed=seed)
        return p if direction is Direction.HIGHER else 1.0 - p
    _, stat = centre(kind)
    draws = stats.bootstrap_diff_draws(a, b, stat, seed=seed)
    better = sum(d > 0 if direction is Direction.HIGHER else d < 0 for d in draws)
    return better / len(draws)


def _diff(a: list[float], b: list[float], kind: MetricKind, seed: int, confidence: float) -> Estimate:
    name, stat = centre(kind)
    draws = stats.bootstrap_diff_draws(a, b, stat, seed=seed)
    low, high = stats.percentile_interval(draws, confidence)
    return Estimate(point=stat(b) - stat(a), low=low, high=high, n=len(a) + len(b), method=f"{name}-diff/bootstrap")


def _decide(cmp: Comparison, q: float, alpha: float) -> Comparison:
    diff = cmp.diff
    if diff is None or diff.point is None or diff.low is None or diff.high is None:
        return replace(cmp, q_value=q)
    clear = q <= alpha and (diff.low > 0 or diff.high < 0)
    if not clear:
        return replace(cmp, q_value=q, change=Change.INCONCLUSIVE)
    better = diff.point > 0 if cmp.direction is Direction.HIGHER else diff.point < 0
    return replace(cmp, q_value=q, change=Change.IMPROVED if better else Change.REGRESSED)


#: One matched cell's samples: the baseline's values, then the candidate's.
Pair = tuple[list[float], list[float]]


@dataclass(frozen=True, slots=True, kw_only=True)
class _Setting:
    """What every comparison of one call shares."""

    arms: Arms
    metric: str
    kind: MetricKind
    direction: Direction
    seed: int
    min_n: int
    confidence: float

    def comparison(self, scope: dict[str, Any], base: Estimate, cand: Estimate) -> Comparison:
        """An insufficient comparison of ``scope``; :func:`dataclasses.replace` fills the statistics."""
        return Comparison(
            metric=self.metric,
            scope=scope,
            baseline=self.arms.baseline_label,
            candidate=self.arms.candidate_label,
            change=Change.INSUFFICIENT,
            baseline_est=base,
            candidate_est=cand,
            diff=None,
            p_better=None,
            method=f"min_n={self.min_n}",
            seed=self.seed,
            direction=self.direction,
        )


def _cell(s: _Setting, scope: dict[str, Any], a: list[float], b: list[float]) -> Comparison:
    """One matched cell: an exact or permutation test of its two arms."""
    kind, seed = s.kind, s.seed
    cmp = s.comparison(
        scope,
        of_values(a, kind, seed=seed, confidence=s.confidence),
        of_values(b, kind, seed=seed, confidence=s.confidence),
    )
    if len(a) < s.min_n or len(b) < s.min_n:
        return cmp
    p_value, test = _test(a, b, kind, seed)
    return replace(
        cmp,
        change=Change.INCONCLUSIVE,
        diff=_diff(a, b, kind, seed, s.confidence),
        p_better=_p_better(a, b, kind, s.direction, seed),
        p_value=p_value,
        method=f"{test}+bh",
    )


def _stratum(s: _Setting, scope: dict[str, Any], pairs: list[Pair]) -> Comparison:
    """Several matched cells in one stratum: each cell's difference, averaged with every cell weighed once.

    Never the pooled samples: a stratum whose cells ran unevenly on the two sides would
    otherwise report a change in *which* cells ran as a change in the subject (Simpson's
    paradox). The interval and the two-sided p-value come from one two-level bootstrap --
    cells resampled, then each drawn cell's samples on both sides.
    """
    kind, seed, conf = s.kind, s.seed, s.confidence
    ok = [(a, b) for a, b in pairs if len(a) >= s.min_n and len(b) >= s.min_n]
    shown = ok or pairs
    cmp = s.comparison(
        scope,
        of_cells([a for a, _ in shown], kind, seed=seed, confidence=conf),
        of_cells([b for _, b in shown], kind, seed=seed, confidence=conf),
    )
    if not ok:
        return cmp
    _, stat = centre(kind)
    rng = random.Random(seed)
    draws = [
        stats.mean(
            [stat(rng.choices(b, k=len(b))) - stat(rng.choices(a, k=len(a))) for a, b in rng.choices(ok, k=len(ok))]
        )
        for _ in range(stats.RESAMPLES)
    ]
    low, high = stats.percentile_interval(draws, conf)
    tail = min(sum(d <= 0 for d in draws), sum(d >= 0 for d in draws))
    better = sum(d > 0 if s.direction is Direction.HIGHER else d < 0 for d in draws)
    method = f"stratified({len(ok)} cells)/bootstrap"
    return replace(
        cmp,
        change=Change.INCONCLUSIVE,
        diff=Estimate(
            point=stats.mean([stat(b) - stat(a) for a, b in ok]),
            low=low,
            high=high,
            n=sum(len(a) + len(b) for a, b in ok),
            method=method,
        ),
        p_value=min(1.0, 2 * (tail + 1) / (len(draws) + 1)),
        p_better=better / len(draws),
        method=f"{method}+bh",
    )


def compare(
    arms: Arms,
    metric: str,
    *,
    by: Sequence[str],
    direction: Direction,
    seed: int,
    min_n: int,
    confidence: float,
) -> list[Comparison]:
    """One :class:`Comparison` per group of ``by`` both arms ran, in key order (see the module docstring).

    Samples are always matched by the whole cell -- ``by`` plus every cell field it leaves
    out -- so ``by`` names *strata*, never a pooling. With ``by`` covering the cell fields
    (the default) each stratum is one cell and gets an exact or permutation test; a coarser
    ``by`` (``("family_tier",)``, ``("model",)``) is a stratified comparison over the matched
    cells inside each stratum, each cell weighed once.

    Raises:
        ValueError: for a group statistic (``cost_per_pass``, ``wasted_cost``), which has no per-sample test.
    """
    if metric in (COST_PER_PASS, WASTED_COST):
        raise ValueError(f"{metric!r} has no per-sample test; compare 'cost' and 'verdict' instead")
    setting = _Setting(
        arms=arms,
        metric=metric,
        kind=kind_of(metric),
        direction=direction,
        seed=seed,
        min_n=min_n,
        confidence=confidence,
    )
    strata_by = tuple(by)
    cells = strata_by + tuple(f for f in CELL_FIELDS if f not in strata_by)
    base, cand = arms.baseline.group(*cells), arms.candidate.group(*cells)
    strata: dict[tuple[Any, ...], list[Pair]] = {}
    for key in (k for k in base if k in cand):
        strata.setdefault(key[: len(strata_by)], []).append((base[key].values(metric), cand[key].values(metric)))
    out: list[Comparison] = []
    for key, pairs in strata.items():
        scope = dict(zip(strata_by, key, strict=True))
        out.append(_cell(setting, scope, *pairs[0]) if len(pairs) == 1 else _stratum(setting, scope, pairs))
    tested = [i for i, c in enumerate(out) if c.p_value is not None]
    qs = stats.benjamini_hochberg([out[i].p_value or 0.0 for i in tested])
    for i, q in zip(tested, qs, strict=True):
        out[i] = _decide(out[i], q, 1.0 - confidence)
    return out
