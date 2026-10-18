"""The statistics the Analyzer reasons with: pure, standard-library, and seeded.

Every function here is a pure function of its arguments. The ones that resample take a
``seed`` and build their own :class:`random.Random` from it, so an analysis re-run over the
same cache reaches the same numbers, and an ``analysis.json`` names the seed that made it.

* :func:`wilson` (the 95% interval the report already uses, re-exported from
  :mod:`pytest_xharness_eval.model.metrics`) and :func:`wilson_interval` at any confidence.
* :func:`bootstrap_ci` and its building blocks: the percentile bootstrap, for statistics
  of heavy-tailed metrics (a median cost) whose sampling distribution has no formula.
* :func:`p_better` -- the beta-binomial probability that one pass rate exceeds another,
  by seeded Monte Carlo over uniform-prior posteriors.
* :func:`permutation_p` -- a two-sided permutation test, exact while the arrangements are
  few enough to enumerate and a seeded Monte Carlo beyond; :func:`fisher_exact_p` is the
  exact test for two pass counts, the permutation test of 0/1 samples in closed form.
* :func:`pass_at_k` and :func:`pass_hat_k` -- the chance at least one, or all, of ``k``
  draws pass, unbiased from ``c`` passes in ``n`` samples.
* :func:`benjamini_hochberg` -- false-discovery-rate adjusted p-values (q-values).
"""

from __future__ import annotations

# Standard Library
import itertools
import math
import random
import statistics
from typing import TYPE_CHECKING, Final

# Our Libraries
from pytest_xharness_eval.model.metrics import wilson

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Sequence

    Stat = Callable[[Sequence[float]], float]

__all__ = [
    "benjamini_hochberg",
    "bootstrap_ci",
    "bootstrap_diff_draws",
    "bootstrap_draws",
    "fisher_exact_p",
    "mean",
    "median",
    "pass_at_k",
    "pass_hat_k",
    "percentile_interval",
    "permutation_p",
    "p_better",
    "quantile",
    "wilson",
    "wilson_interval",
]

#: Resamples a bootstrap draws by default: enough for a stable 95% percentile interval.
RESAMPLES: Final = 2000
#: Posterior draws :func:`p_better` takes by default.
DRAWS: Final = 20000
#: The most arrangements :func:`permutation_p` enumerates before it samples instead.
EXACT_LIMIT: Final = 20000
#: Slack for comparing floating-point test statistics, so a tie counts as "as extreme".
_EPS: Final = 1e-12


def median(values: Sequence[float]) -> float:
    """The median: the centre a heavy-tailed metric (cost, tokens, wall clock) is summarised by."""
    return float(statistics.median(values))


def mean(values: Sequence[float]) -> float:
    """The arithmetic mean: the centre a bounded metric (a share, a pass rate) is summarised by."""
    return statistics.fmean(values)


def quantile(values: Sequence[float], q: float) -> float:
    """The ``q``-quantile of ``values`` by linear interpolation between order statistics."""
    if not values:
        raise ValueError("quantile of no values")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q must be within [0, 1], got {q}")
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def wilson_interval(passes: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """The Wilson score interval for ``passes`` in ``n`` trials at any two-sided ``confidence``."""
    if n <= 0:
        raise ValueError("a Wilson interval needs at least one trial")
    z = statistics.NormalDist().inv_cdf(0.5 + confidence / 2)
    p = passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def percentile_interval(draws: Sequence[float], confidence: float = 0.95) -> tuple[float, float]:
    """The central ``confidence`` interval of a set of resampled statistics."""
    alpha = 1.0 - confidence
    return quantile(draws, alpha / 2), quantile(draws, 1.0 - alpha / 2)


def bootstrap_draws(values: Sequence[float], stat: Stat, *, seed: int, resamples: int = RESAMPLES) -> list[float]:
    """``stat`` of ``resamples`` with-replacement resamples of ``values``."""
    if not values:
        raise ValueError("bootstrap of no values")
    rng = random.Random(seed)
    n = len(values)
    return [stat(rng.choices(values, k=n)) for _ in range(resamples)]


def bootstrap_diff_draws(
    a: Sequence[float], b: Sequence[float], stat: Stat, *, seed: int, resamples: int = RESAMPLES
) -> list[float]:
    """``stat(b*) - stat(a*)`` over independent resamples of each arm: the difference's distribution."""
    if not a or not b:
        raise ValueError("bootstrap of an empty arm")
    rng = random.Random(seed)
    return [stat(rng.choices(b, k=len(b))) - stat(rng.choices(a, k=len(a))) for _ in range(resamples)]


def bootstrap_ci(
    values: Sequence[float],
    stat: Stat = median,
    *,
    seed: int,
    resamples: int = RESAMPLES,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """The percentile-bootstrap ``confidence`` interval of ``stat`` over ``values``."""
    return percentile_interval(bootstrap_draws(values, stat, seed=seed, resamples=resamples), confidence)


def p_better(passes_a: int, n_a: int, passes_b: int, n_b: int, *, seed: int, draws: int = DRAWS) -> float:
    """P(rate_b > rate_a) under independent Beta(1 + passes, 1 + fails) posteriors, by Monte Carlo."""
    rng = random.Random(seed)
    wins = 0
    for _ in range(draws):
        a = rng.betavariate(1 + passes_a, 1 + n_a - passes_a)
        b = rng.betavariate(1 + passes_b, 1 + n_b - passes_b)
        wins += b > a
    return wins / draws


def fisher_exact_p(passes_a: int, n_a: int, passes_b: int, n_b: int) -> float:
    """Two-sided Fisher exact p-value that two pass counts come from one pass rate.

    Sums the hypergeometric probability of every table at most as likely as the observed
    one: the exact permutation test of 0/1 samples, without enumerating arrangements.
    """
    total, passes = n_a + n_b, passes_a + passes_b
    denominator = math.comb(total, n_b)

    def prob(x: int) -> float:
        return math.comb(passes, x) * math.comb(total - passes, n_b - x) / denominator

    observed = prob(passes_b)
    support = range(max(0, n_b - (total - passes)), min(passes, n_b) + 1)
    return min(1.0, sum(p for x in support if (p := prob(x)) <= observed * (1 + 1e-7)))


def permutation_p(
    a: Sequence[float],
    b: Sequence[float],
    stat: Stat = mean,
    *,
    seed: int,
    exact_limit: int = EXACT_LIMIT,
    resamples: int = 10000,
) -> float:
    """Two-sided permutation p-value for ``|stat(b) - stat(a)|``.

    Exact -- every way of relabelling the pooled samples -- while there are at most
    ``exact_limit`` of them (every pair of arms of up to 8 samples each); beyond that, a
    seeded Monte Carlo of ``resamples`` relabellings with the ``(hits + 1) / (B + 1)``
    correction, so a sampled p-value is never zero.
    """
    if not a or not b:
        raise ValueError("a permutation test needs samples in both arms")
    pooled = [*a, *b]
    n_b = len(b)
    observed = abs(stat(b) - stat(a)) - _EPS

    def extreme(idx: Sequence[int]) -> bool:
        chosen = set(idx)
        arm_b = [pooled[i] for i in idx]
        arm_a = [v for i, v in enumerate(pooled) if i not in chosen]
        return abs(stat(arm_b) - stat(arm_a)) >= observed

    if math.comb(len(pooled), n_b) <= exact_limit:
        arrangements = list(itertools.combinations(range(len(pooled)), n_b))
        return sum(extreme(idx) for idx in arrangements) / len(arrangements)
    rng = random.Random(seed)
    indices = range(len(pooled))
    hits = sum(extreme(rng.sample(indices, n_b)) for _ in range(resamples))
    return (hits + 1) / (resamples + 1)


def _check_k(n: int, c: int, k: int) -> None:
    if not 0 <= c <= n:
        raise ValueError(f"passes c={c} must be within [0, n={n}]")
    if not 1 <= k <= n:
        raise ValueError(f"k={k} must be within [1, n={n}]")


def pass_at_k(n: int, c: int, k: int) -> float:
    """P(at least one of ``k`` draws passes): ``1 - C(n-c, k) / C(n, k)``, unbiased from ``c`` of ``n``."""
    _check_k(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """P(all ``k`` draws pass), the reliability reading: ``C(c, k) / C(n, k)``."""
    _check_k(n, c, k)
    return math.comb(c, k) / math.comb(n, k)


def benjamini_hochberg(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (q-values), in the order the p-values were given.

    ``q_(i) = min_{j >= i} p_(j) * m / j`` over the ascending p-values, capped at 1: the
    false-discovery-rate correction for testing many cells at once.
    """
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        adjusted[i] = min(1.0, running)
    return adjusted
