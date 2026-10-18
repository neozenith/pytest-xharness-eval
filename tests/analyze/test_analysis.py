"""``analyze.analysis``: the questions an analyzer asks, and the expectations that fail with evidence."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.analyze.analysis import Analysis, AnalysisFailure, Unbalanced
from pytest_xharness_eval.analyze.samples import Samples
from pytest_xharness_eval.model.analysis import Change
from pytest_xharness_eval.model.metrics import wilson
from tests.analyze import batch, record


def _analysis(*records: list, current: list | None = None) -> Analysis:
    return Analysis(history=Samples([r for group in records for r in group]), current=Samples(current or []))


def _frontier() -> Analysis:
    return _analysis(
        batch(10, 10, model="a", estimated_cost_usd=5.0),
        batch(10, 5, model="b", estimated_cost_usd=1.0),
        batch(10, 5, model="c", estimated_cost_usd=5.0),
    )


def _versions(v1_passes: int, v2_passes: int) -> Analysis:
    return _analysis(
        batch(12, v1_passes, subject_version="v1", at="2026-10-01"),
        batch(12, v2_passes, subject_version="v2", at="2026-10-02"),
    )


def test_history_and_current_merge_with_each_session_once() -> None:
    shared = record()
    analysis = _analysis([shared], current=[shared, record()])
    assert len(analysis.samples) == 2


def test_summarise_estimates_each_group_by_its_kind() -> None:
    analysis = _analysis(batch(10, 5, model="a"), batch(4, 4, model="b"))
    summary = analysis.summarise("verdict", by=("model",))
    assert list(summary) == [("a",), ("b",)]
    assert (summary[("a",)].low, summary[("a",)].high) == pytest.approx(wilson(5, 10))
    assert analysis.summarise("cost")[()].point == 1.0


def _effort_design(include_high_in_b: bool = True) -> Analysis:
    groups = [
        batch(5, 1, case="eval_a", effort="low"),
        batch(5, 5, case="eval_a", effort="high"),
        batch(5, 1, case="eval_b", effort="low"),
    ]
    if include_high_in_b:
        groups.append(batch(5, 5, case="eval_b", effort="high"))
    return _analysis(*groups)


def test_main_effects_on_a_balanced_design_are_centres_minus_the_slice_mean() -> None:
    effects = _effort_design().effects("effort", "passed", within=("case",))
    assert effects["high"].point == pytest.approx(0.4)
    assert effects["low"].point == pytest.approx(-0.4)
    assert effects["high"].n == 10 and effects["high"].method == "main-effect/bootstrap"
    low = effects["high"].low
    assert low is not None and low > 0


def test_an_unbalanced_design_is_refused_unless_incomplete_slices_are_dropped() -> None:
    analysis = _effort_design(include_high_in_b=False)
    with pytest.raises(Unbalanced, match="lacks effort='high'") as raised:
        analysis.effects("effort", "passed", within=("case",))
    assert raised.value.missing == [(("eval_b",), "high")]
    kept = analysis.effects("effort", "passed", within=("case",), drop_unbalanced=True)
    assert kept["high"].n == 5


def test_effects_hold_every_other_cell_field_fixed_by_default() -> None:
    # Two models each ran only one effort: no slice holds both, so nothing is comparable.
    analysis = _analysis(batch(5, 5, model="a", effort="high"), batch(5, 1, model="b", effort="low"))
    with pytest.raises(Unbalanced):
        analysis.effects("effort", "passed")
    with pytest.raises(Unbalanced):
        analysis.effects("effort", "passed", drop_unbalanced=True)


def test_best_ranks_by_direction_and_trails_groups_below_min_n() -> None:
    analysis = _analysis(
        [record(model="a", estimated_cost_usd=3.0) for _ in range(3)],
        [record(model="b", estimated_cost_usd=1.0) for _ in range(3)],
        [record(model="c", estimated_cost_usd=0.1)],
    )
    ranked = analysis.best("cost", by=("model",))
    assert [k for k, _ in ranked] == [("b",), ("a",), ("c",)]
    assert [k for k, _ in analysis.best("verdict", by=("model",))][-1] == ("c",)


def test_pareto_keeps_only_groups_no_other_beats_on_both_pessimistic_bounds() -> None:
    points = _frontier().pareto(by=("model",))
    assert [(p.key["model"], p.on_front) for p in points] == [("b", True), ("a", True), ("c", False)]


def test_tiers_pool_one_family_tier_across_harnesses() -> None:
    analysis = _analysis(
        batch(4, 4, harness="claude", model="opus", family_tier=3),
        batch(4, 0, harness="codex", model="sol", family_tier=3),
        batch(3, 3, harness="claude", model="haiku", family_tier=1),
    )
    tiers = analysis.tiers("verdict")
    assert list(tiers) == [1, 3]
    assert (tiers[3].point, tiers[3].n, tiers[3].method) == (0.5, 8, "cell-mean/bootstrap")


def test_a_tier_weighs_each_cell_once_so_the_most_run_harness_cannot_speak_for_it() -> None:
    analysis = _analysis(
        batch(12, 12, harness="claude", model="opus", family_tier=3),
        batch(3, 0, harness="codex", model="sol", family_tier=3),
        batch(2, 2, harness="codex", model="tiny", family_tier=3),  # below min_n: left out
    )
    tier = analysis.tiers("verdict")[3]
    assert (tier.point, tier.n) == (0.5, 15)  # pooled, it would read 12/15 = 0.8
    assert tier.low is not None and tier.high is not None and tier.low <= 0.5 <= tier.high


def test_a_coarse_comparison_is_stratified_over_matched_cells_never_pooled() -> None:
    # Simpson's trap: every cell improves, but v2 ran mostly the hard cell, so pooling reads a drop.
    analysis = _analysis(
        batch(20, 18, model="easy", family_tier=2, subject_version="v1", at="2026-10-01"),
        batch(5, 0, model="hard", family_tier=2, subject_version="v1", at="2026-10-01"),
        batch(5, 5, model="easy", family_tier=2, subject_version="v2", at="2026-10-02"),
        batch(20, 4, model="hard", family_tier=2, subject_version="v2", at="2026-10-02"),
    )
    [cmp] = analysis.compare("verdict", "v1", "v2", by=("family_tier",))
    assert cmp.scope == {"family_tier": 2}
    assert cmp.method == "stratified(2 cells)/bootstrap+bh"
    assert cmp.diff is not None and cmp.diff.point == pytest.approx(((1.0 - 0.9) + (0.2 - 0.0)) / 2)
    assert cmp.p_better is not None and cmp.p_better > 0.5


def test_versions_are_compared_cell_by_matched_cell() -> None:
    analysis = _versions(2, 12)
    assert analysis.versions() == ("v1", "v2")
    [cmp] = analysis.compare("verdict", "v1", "v2")
    assert (cmp.baseline, cmp.candidate, cmp.change) == ("v1", "v2", Change.IMPROVED)
    assert set(cmp.scope) == {"skill", "case", "harness", "model", "effort", "treatment", "scenario"}
    [sides] = analysis.compare("verdict", analysis.samples.where(subject_version="v1"), analysis.samples)
    assert (sides.baseline, sides.candidate) == ("baseline", "candidate")


def test_trend_follows_versions_in_first_measured_order() -> None:
    [(key, steps)] = _versions(6, 12).trend("verdict").items()
    assert key == ()
    assert [(v, e.point) for v, e in steps] == [("v1", 0.5), ("v2", 1.0)]


def test_regressions_compare_the_latest_version_against_the_one_before() -> None:
    assert [c.change for c in _versions(12, 1).regressions()] == [Change.REGRESSED]
    assert _versions(1, 12).regressions() == []
    assert _analysis(batch(5, 5)).regressions() == []


def test_expect_no_regression_fails_with_the_comparisons_attached() -> None:
    with pytest.raises(AnalysisFailure, match="1 of 1 cells regressed on verdict") as raised:
        _versions(12, 1).expect_no_regression()
    assert [c.change for c in raised.value.comparisons] == [Change.REGRESSED]
    assert "v1 1 [" in str(raised.value) and "-> v2 0.08333" in str(raised.value)
    assert [c.change for c in _versions(1, 12).expect_no_regression()] == [Change.IMPROVED]
    assert len(_versions(12, 12).expect_no_regression(baseline="v1", candidate="v2")) == 1


def test_a_regression_gate_never_passes_on_zero_evidence() -> None:
    with pytest.raises(AnalysisFailure, match="only 0 subject version recorded"):
        _analysis(batch(5, 5)).expect_no_regression()
    with pytest.raises(AnalysisFailure, match=r"only 1 subject version recorded \(v1\)"):
        _analysis(batch(5, 5, subject_version="v1")).expect_no_regression()
    thin = _analysis(
        batch(2, 2, subject_version="v1", at="2026-10-01"), batch(2, 0, subject_version="v2", at="2026-10-02")
    )
    with pytest.raises(AnalysisFailure, match="nothing was comparable") as raised:
        thin.expect_no_regression()
    assert "3/3 against 0/3" in str(raised.value) and "p = 0.10" in str(raised.value)
    assert [c.change for c in raised.value.comparisons] == [Change.INSUFFICIENT]


def test_versions_follow_a_revert_and_at_version_narrows_to_the_current_subject() -> None:
    analysis = _analysis(
        batch(3, 3, subject_version="v1", at="2026-10-01"),
        batch(3, 0, subject_version="v2", at="2026-10-02"),
        batch(3, 2, subject_version="v1", at="2026-10-03"),
    )
    assert analysis.versions() == ("v2", "v1")
    assert len(analysis.at_version().samples) == 6
    assert analysis.at_version("v2").summarise("verdict")[()].point == 0.0
    assert [v for v, _ in analysis.trend("verdict")[()]] == ["v1", "v2"]  # first-measured order


def test_fragile_ranks_scenarios_by_failure_rate() -> None:
    analysis = _analysis(
        batch(5, 5, scenario="calm", scenario_fingerprint="f1"),
        batch(5, 1, scenario="storm", scenario_fingerprint="f2"),
        batch(5, 0),
    )
    ranked = analysis.fragile()
    assert [(k[1], e.point) for k, e in ranked] == [("storm@f2", 0.8), ("calm@f1", 0.0)]


def test_errors_rank_scenarios_as_broken_never_as_fragile() -> None:
    error = {"verdict": "error", "scenario": "seed", "scenario_fingerprint": "f3"}
    analysis = _analysis(
        batch(4, 4, scenario="seed", scenario_fingerprint="f3"),
        [record(**error) for _ in range(4)],
        batch(4, 4, scenario="calm", scenario_fingerprint="f1"),
    )
    assert [(k[1], e.point, e.n) for k, e in analysis.fragile()] == [("calm@f1", 0.0, 4), ("seed@f3", 0.0, 4)]
    assert [(k[1], e.point) for k, e in analysis.broken()] == [("seed@f3", 0.5), ("calm@f1", 0.0)]


def test_failures_count_reasons_per_group_keyed_by_verdict_too() -> None:
    analysis = _analysis(batch(3, 1, model="a"), [record(model="b", verdict="error")])
    assert analysis.failures(by=("model",)) == {
        ("a",): {("fail", "AssertionError: wrong"): 2},
        ("b",): {("error", "(no reason recorded)"): 1},
    }


def test_reliability_reads_pass_at_k_and_pass_hat_k_per_group() -> None:
    rel = _analysis(batch(4, 2, model="a"), [record(model="a", verdict="error")]).reliability(2, by=("model",))
    assert rel[("a",)] == {"n": 4, "passes": 2, "pass_at_k": pytest.approx(5 / 6), "pass_hat_k": pytest.approx(1 / 6)}


def test_expect_at_least_holds_each_groups_bound_to_the_threshold() -> None:
    analysis = _analysis(batch(10, 10, model="a"), batch(10, 3, model="b"))
    with pytest.raises(AnalysisFailure, match=r"model=b\] low") as raised:
        analysis.expect_at_least("verdict", 0.5, by=("model",))
    assert "model=a" not in str(raised.value)
    assert raised.value.details["bound"] == "low"
    only_a = Analysis(history=analysis.samples.where(model="a"))
    assert set(only_a.expect_at_least("verdict", 0.5)) == {()}


def test_expect_at_most_and_an_empty_analysis() -> None:
    analysis = _analysis(batch(4, 4, estimated_cost_usd=1.0))
    assert analysis.expect_at_most("cost", 2.0)[()].point == 1.0
    with pytest.raises(AnalysisFailure):
        analysis.expect_at_most("cost", 0.5)
    with pytest.raises(AnalysisFailure, match="no samples at all"):
        _analysis().expect_at_least("verdict", 0.1)
    with pytest.raises(ValueError, match="bound must be"):
        analysis.expect_at_least("verdict", 0.1, bound="middle")


def test_expect_pareto_contains_names_the_frontier_when_it_fails() -> None:
    analysis = _frontier()
    assert len(analysis.expect_pareto_contains({"model": "b"}, by=("model",))) == 3
    with pytest.raises(AnalysisFailure, match="is not on the frontier") as raised:
        analysis.expect_pareto_contains({"model": "c"}, by=("model",))
    assert "[model=a]" in str(raised.value) and "[model=b]" in str(raised.value)
    with pytest.raises(AnalysisFailure, match="matches no group with n >= 3"):
        analysis.expect_pareto_contains({"model": "z"}, by=("model",))


def test_for_cases_narrows_both_history_and_current() -> None:
    analysis = _analysis(batch(3, 3, case="eval_a"), current=batch(3, 3, case="eval_b"))
    narrowed = analysis.for_cases(["eval_b"])
    assert len(narrowed.samples) == 3 and narrowed.samples.levels("case") == ("eval_b",)
    assert (narrowed.seed, narrowed.min_n, narrowed.confidence) == (0, 3, 0.95)
