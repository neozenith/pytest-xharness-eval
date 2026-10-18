"""``analyze.estimate``: one group's metric estimated by the estimator its kind calls for."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.analyze.estimate import centre, estimate, of_cells, of_values
from pytest_xharness_eval.analyze.sampleset import Samples
from pytest_xharness_eval.model.metrics import MetricKind, wilson
from tests.analyze import batch, record


def test_a_rate_is_the_pass_rate_with_its_wilson_interval() -> None:
    est = estimate(Samples(batch(10, 5)), "verdict", seed=0)
    assert (est.point, est.n, est.method) == (0.5, 10, "wilson")
    assert (est.low, est.high) == pytest.approx(wilson(5, 10))


def test_a_spread_is_the_median_with_a_bootstrap_interval() -> None:
    costs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 100.0]
    est = estimate(Samples([record(estimated_cost_usd=c) for c in costs]), "cost", seed=0)
    assert (est.point, est.n, est.method) == (5.0, 9, "median/bootstrap")
    assert est.low is not None and est.high is not None and est.low <= 5.0 <= est.high < 100.0


def test_a_fraction_is_the_mean() -> None:
    est = estimate(Samples([record(reasoning_share=v) for v in (0.2, 0.4)]), "thinking", seed=0)
    assert (est.point, est.method) == (pytest.approx(0.3), "mean/bootstrap")


def test_no_samples_estimate_nothing() -> None:
    for kind in MetricKind:
        assert of_values([], kind, seed=0, confidence=0.95).point is None
    assert estimate(Samples(), "cost_per_pass", seed=0).point is None


def test_cost_per_pass_is_bootstrapped_over_whole_sessions() -> None:
    est = estimate(Samples(batch(6, 3, estimated_cost_usd=2.0)), "cost_per_pass", seed=0)
    assert (est.point, est.n, est.method) == (4.0, 6, "ratio/bootstrap")
    assert est.low is not None and est.high is not None and est.low <= 4.0 <= est.high


def test_cost_per_pass_skips_errors_and_wasted_cost_sums_the_fails() -> None:
    errors = [record(verdict="error", estimated_cost_usd=50.0) for _ in range(3)]
    s = Samples([*batch(6, 3, estimated_cost_usd=2.0), *errors])
    per_pass = estimate(s, "cost_per_pass", seed=0)
    assert (per_pass.point, per_pass.n) == (4.0, 6)
    assert per_pass.high is not None and per_pass.high < 50.0
    wasted = estimate(s, "wasted_cost", seed=0)
    assert (wasted.point, wasted.n, wasted.method) == (6.0, 9, "sum/bootstrap")
    assert wasted.low is not None and wasted.high is not None and wasted.low <= 6.0 <= wasted.high
    assert estimate(Samples(), "wasted_cost", seed=0).point == 0.0


def test_one_cell_is_its_own_estimate_and_many_weigh_each_cell_once() -> None:
    assert of_cells([[1.0, 0.0]], MetricKind.RATE, seed=0, confidence=0.95).method == "wilson"
    est = of_cells([[1.0] * 9, [0.0]], MetricKind.RATE, seed=0, confidence=0.95)
    assert (est.point, est.n, est.method) == (0.5, 10, "cell-mean/bootstrap")
    assert of_cells([], MetricKind.RATE, seed=0, confidence=0.95).point is None


def test_each_kind_names_its_centre() -> None:
    assert centre(MetricKind.SPREAD)[0] == "median"
    assert {centre(k)[0] for k in (MetricKind.RATE, MetricKind.FRACTION, MetricKind.RARE)} == {"mean"}
