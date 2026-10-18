"""``analyze.compare``: matched cells, ``min_n``, and the false-discovery rate across cells."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.analyze.compare import Arms, compare
from pytest_xharness_eval.analyze.samples import Samples
from pytest_xharness_eval.model.analysis import Change, Direction
from tests.analyze import batch, record

BY = ("harness", "model")


def _compare(base: list, cand: list, metric: str = "verdict", direction: Direction = Direction.HIGHER) -> list:
    return compare(
        Arms(baseline=Samples(base), candidate=Samples(cand), baseline_label="v1", candidate_label="v2"),
        metric,
        by=BY,
        direction=direction,
        seed=0,
        min_n=3,
        confidence=0.95,
    )


def test_a_clear_improvement_with_enough_samples_is_improved() -> None:
    [cmp] = _compare(batch(12, 2), batch(12, 12))
    assert cmp.change is Change.IMPROVED
    assert cmp.scope == {"harness": "claude", "model": "opus"}
    assert (cmp.baseline, cmp.candidate) == ("v1", "v2")
    assert cmp.p_better is not None and cmp.p_better > 0.99
    assert cmp.q_value is not None and cmp.q_value < 0.05
    assert cmp.diff is not None and cmp.diff.point == pytest.approx(10 / 12)
    assert cmp.method == "fisher+bh"


def test_a_clear_drop_is_regressed() -> None:
    [cmp] = _compare(batch(12, 12), batch(12, 1))
    assert cmp.change is Change.REGRESSED


def test_fewer_than_min_n_samples_is_insufficient_with_no_statistics() -> None:
    [cmp] = _compare(batch(2, 0), batch(12, 12))
    assert cmp.change is Change.INSUFFICIENT
    assert (cmp.diff, cmp.p_better, cmp.p_value, cmp.q_value) == (None, None, None, None)
    assert cmp.method == "min_n=3"


def test_noise_is_inconclusive() -> None:
    [cmp] = _compare(batch(8, 5), batch(8, 6))
    assert cmp.change is Change.INCONCLUSIVE
    assert cmp.p_value is not None and cmp.p_value > 0.05


def test_a_lower_is_better_metric_improves_when_it_falls() -> None:
    base = [record(estimated_cost_usd=10.0 + i * 0.1) for i in range(10)]
    cand = [record(estimated_cost_usd=1.0 + i * 0.1) for i in range(10)]
    [cmp] = _compare(base, cand, "cost", Direction.LOWER)
    assert cmp.change is Change.IMPROVED
    assert cmp.diff is not None and cmp.diff.point == pytest.approx(-9.0)
    assert cmp.method == "permutation(median)+bh"


def test_only_cells_both_sides_ran_are_compared() -> None:
    base = batch(5, 5) + batch(5, 5, model="sonnet")
    cand = batch(5, 5) + batch(5, 5, model="haiku")
    assert [c.scope["model"] for c in _compare(base, cand)] == ["opus"]


def test_many_cells_share_one_error_budget() -> None:
    # Three cells with one borderline gap each: raw p-values that would pass one at a time
    # are adjusted together, so the q-value is never below the p-value.
    base = [r for m in ("a", "b", "c") for r in batch(10, 4, model=m)]
    cand = [r for m in ("a", "b", "c") for r in batch(10, 9, model=m)]
    made = _compare(base, cand)
    assert len(made) == 3
    assert all(c.q_value is not None and c.p_value is not None and c.q_value >= c.p_value for c in made)


def test_cost_per_pass_has_no_per_sample_test() -> None:
    with pytest.raises(ValueError, match="no per-sample test"):
        _compare(batch(5, 5), batch(5, 5), "cost_per_pass")
    with pytest.raises(ValueError, match="no per-sample test"):
        _compare(batch(5, 5), batch(5, 5), "wasted_cost")


def test_a_stratum_with_no_cell_at_min_n_is_insufficient() -> None:
    base = batch(2, 2, model="a", effort="low") + batch(2, 2, model="a", effort="high")
    cand = batch(2, 0, model="a", effort="low") + batch(2, 0, model="a", effort="high")
    [cmp] = _compare(base, cand)
    assert (cmp.change, cmp.diff, cmp.method) == (Change.INSUFFICIENT, None, "min_n=3")
    assert cmp.baseline_est.method == "cell-mean/bootstrap"
