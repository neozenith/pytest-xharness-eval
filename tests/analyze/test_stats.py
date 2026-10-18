"""``analyze.stats``: the Analyzer's pure, seeded statistics against known values."""

# Standard Library
import math

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.model.metrics import wilson


@pytest.mark.parametrize(
    ("n", "c", "k", "expected"),
    [(10, 3, 1, 0.3), (5, 2, 2, 0.7), (10, 0, 3, 0.0), (10, 8, 3, 1.0), (4, 4, 4, 1.0)],
)
def test_pass_at_k_is_the_unbiased_chance_one_of_k_draws_passes(n: int, c: int, k: int, expected: float) -> None:
    assert stats.pass_at_k(n, c, k) == pytest.approx(expected)


@pytest.mark.parametrize(("n", "c", "k", "expected"), [(5, 2, 2, 0.1), (10, 10, 5, 1.0), (10, 3, 1, 0.3), (6, 2, 3, 0)])
def test_pass_hat_k_is_the_chance_all_k_draws_pass(n: int, c: int, k: int, expected: float) -> None:
    assert stats.pass_hat_k(n, c, k) == pytest.approx(expected)


@pytest.mark.parametrize(("n", "c", "k"), [(5, 6, 1), (5, 2, 0), (5, 2, 6), (5, -1, 1)])
def test_pass_at_k_refuses_an_impossible_draw(n: int, c: int, k: int) -> None:
    with pytest.raises(ValueError):
        stats.pass_at_k(n, c, k)


def test_wilson_interval_matches_the_report_at_95_and_a_known_value() -> None:
    assert stats.wilson_interval(5, 10) == pytest.approx(wilson(5, 10))
    assert stats.wilson_interval(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    low90, high90 = stats.wilson_interval(5, 10, 0.90)
    assert 0.2366 < low90 < 0.5 < high90 < 0.7634
    with pytest.raises(ValueError):
        stats.wilson_interval(0, 0)


def test_benjamini_hochberg_adjusts_in_input_order_and_stays_monotone() -> None:
    assert stats.benjamini_hochberg([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert stats.benjamini_hochberg([0.9, 0.8]) == pytest.approx([0.9, 0.9])
    assert stats.benjamini_hochberg([]) == []


def test_fisher_exact_matches_the_lady_tasting_tea() -> None:
    assert stats.fisher_exact_p(1, 4, 3, 4) == pytest.approx(0.4857, abs=1e-4)
    assert stats.fisher_exact_p(5, 10, 5, 10) == pytest.approx(1.0)
    assert stats.fisher_exact_p(0, 10, 10, 10) < 1e-4


def test_permutation_p_is_exact_for_small_arms() -> None:
    # Of the 20 relabellings of six values into two threes, only the observed split and its
    # mirror are as extreme: p = 2 / 20.
    assert stats.permutation_p([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], seed=0) == pytest.approx(0.1)
    assert stats.permutation_p([1.0, 1.0], [1.0, 1.0], seed=0) == 1.0


def test_permutation_p_samples_large_arms_with_a_seed() -> None:
    a = [float(i) for i in range(12)]
    b = [float(i) + 6 for i in range(12)]
    first = stats.permutation_p(a, b, stats.median, seed=7)
    assert first == stats.permutation_p(a, b, stats.median, seed=7)
    assert 0 < first < 0.05
    with pytest.raises(ValueError):
        stats.permutation_p([], b, seed=0)


def test_bootstrap_is_seeded_and_brackets_the_statistic() -> None:
    values = [1.0, 2.0, 2.5, 3.0, 40.0]
    low, high = stats.bootstrap_ci(values, seed=3)
    assert (low, high) == stats.bootstrap_ci(values, seed=3)
    assert low <= stats.median(values) <= high
    assert stats.bootstrap_ci([2.0, 2.0, 2.0], seed=0) == (2.0, 2.0)
    with pytest.raises(ValueError):
        stats.bootstrap_draws([], stats.mean, seed=0)


def test_bootstrap_diff_draws_center_on_the_difference() -> None:
    draws = stats.bootstrap_diff_draws([1.0, 1.0, 1.0], [3.0, 3.0, 3.0], stats.mean, seed=0, resamples=50)
    assert set(draws) == {2.0}


def test_p_better_is_the_chance_the_second_rate_is_higher() -> None:
    assert stats.p_better(1, 10, 9, 10, seed=0) > 0.99
    assert stats.p_better(9, 10, 1, 10, seed=0) < 0.01
    assert stats.p_better(5, 10, 5, 10, seed=0) == pytest.approx(0.5, abs=0.02)
    assert stats.p_better(3, 4, 1, 4, seed=1) == stats.p_better(3, 4, 1, 4, seed=1)


def test_quantile_interpolates_and_refuses_nonsense() -> None:
    assert stats.quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert stats.quantile([5.0], 0.9) == 5.0
    assert math.isclose(stats.quantile([0.0, 10.0], 0.25), 2.5)
    with pytest.raises(ValueError):
        stats.quantile([], 0.5)
    with pytest.raises(ValueError):
        stats.quantile([1.0], 1.5)
