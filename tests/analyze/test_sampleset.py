"""``analyze.sampleset``: filtering, grouping and reading metrics off stored session records."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.analyze.sampleset import (
    COST_PER_PASS,
    Samples,
    direction_of,
    kind_of,
    record_value,
    scenario_identity,
)
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.metrics import Direction, MetricKind
from pytest_xharness_eval.model.verdict import Verdict
from tests.analyze import batch, record


def test_of_keeps_graded_samples_and_drops_dry_runs_and_unreadable_verdicts() -> None:
    kept = Samples.of([record(), record(verdict=Verdict.FAIL.value), record(verdict="dry-run"), record(verdict="?")])
    assert len(kept) == 2


def test_stored_reads_every_graded_record_a_cache_holds(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    for i, verdict in enumerate((Verdict.PASS, Verdict.DRY_RUN)):
        session = cache.session(skill="demo", harness="claude", model="opus", run="20261001T000000Z", session=f"s{i}")
        record(verdict=verdict.value).write(session.history)
    assert [r.verdict for r in Samples.stored(cache)] == ["pass"]


def test_where_matches_by_equality_membership_callable_and_predicate() -> None:
    s = Samples([record(model="opus", turns=3), record(model="sonnet", turns=9), record(model="haiku", turns=1)])
    assert len(s.where(model="opus")) == 1
    assert len(s.where(model=["opus", "haiku"])) == 2
    assert len(s.where(turns=lambda t: t > 2)) == 2
    assert len(s.where(lambda r: r.model.startswith("s"), turns=9)) == 1
    with pytest.raises(ValueError, match="no field"):
        s.where(colour="red")


def test_group_keys_are_sorted_and_carry_each_records_values() -> None:
    s = Samples([record(model="sonnet"), record(model="opus"), record(model="opus", effort="high")])
    groups = s.group("model", "effort")
    assert list(groups) == [("opus", ""), ("opus", "high"), ("sonnet", "")]
    assert s.levels("model") == ("opus", "sonnet")
    assert list(s.group()) == [()]


def test_grouping_by_scenario_never_pools_two_fingerprints_of_one_scenario() -> None:
    s = Samples(
        [
            record(scenario="lint-1", scenario_fingerprint="a" * 64),
            record(scenario="lint-1", scenario_fingerprint="b" * 64),
            record(scenario="lint-1", scenario_fingerprint="a" * 64),
        ]
    )
    groups = s.group("scenario")
    assert {k: len(v) for k, v in groups.items()} == {("lint-1@" + "a" * 12,): 2, ("lint-1@" + "b" * 12,): 1}
    # Filtering reads the plain field, so every fingerprint of the scenario is selected.
    assert len(s.where(scenario="lint-1")) == 3
    assert scenario_identity(record()) is None
    assert scenario_identity(record(scenario="x")) == "x"


def test_values_resolve_important_metrics_derived_metrics_and_fields() -> None:
    s = Samples(
        [
            record(skill_files=4, skill_files_loaded=2, turns=5),
            record(verdict=Verdict.FAIL.value, skill_files=None, turns=7, estimated_cost_usd=None),
        ]
    )
    assert s.values("skill_loaded") == [0.5]
    assert s.values("verdict") == [1.0, 0.0]
    assert s.values("passed") == [1.0, 0.0]
    assert s.values("turns") == [5.0, 7.0]
    assert s.values("cost") == [1.0]
    assert s.passes() == 1
    with pytest.raises(ValueError, match="group statistic"):
        record_value(record(), COST_PER_PASS)
    with pytest.raises(ValueError, match="unknown metric"):
        s.values("vibes")


def test_cost_per_pass_is_total_cost_over_passes() -> None:
    assert Samples(batch(4, 2, estimated_cost_usd=0.5)).cost_per_pass() == pytest.approx(1.0)
    assert Samples(batch(2, 0)).cost_per_pass() is None


ERROR = {"verdict": Verdict.ERROR.value, "estimated_cost_usd": 9.0}


def test_an_error_is_no_attempt_so_no_sample_of_a_pass_rate_or_its_cost() -> None:
    s = Samples([*batch(4, 2, estimated_cost_usd=0.5), record(**ERROR)])
    assert s.values("verdict") == s.values("passed") == [1.0, 1.0, 0.0, 0.0]
    assert s.values("errors") == [0.0, 0.0, 0.0, 0.0, 1.0]
    assert len(s.attempted()) == 4
    # The error's $9 neither inflates the cost of a pass nor counts as a wasted attempt.
    assert s.cost_per_pass() == pytest.approx(1.0)
    assert s.wasted_cost() == pytest.approx(1.0)
    assert Samples(batch(2, 2)).wasted_cost() == 0.0
    assert Samples(batch(1, 0, estimated_cost_usd=None)).wasted_cost() is None


def test_pass_at_k_and_pass_hat_k_read_the_attempted_samples() -> None:
    s = Samples([*batch(4, 2), record(**ERROR)])
    assert s.pass_at_k(1) == s.pass_hat_k(1) == pytest.approx(0.5)
    assert s.pass_at_k(3) == 1.0  # any 3 of 4 hold a pass
    assert s.pass_hat_k(2) == pytest.approx(1 / 6)  # C(2,2)/C(4,2)
    assert s.pass_at_k(5) is None and s.pass_hat_k(5) is None


def test_per_session_derivations_divide_the_record_by_itself() -> None:
    r = record(tool_ms_by_name={"Bash": 300, "Read": 100}, duration_ms=1000, tool_context_cost_usd=0.25)
    assert record_value(r, "tool_time_share") == pytest.approx(0.4)
    assert record_value(r, "context_cost_share") == pytest.approx(0.25)
    assert record_value(record(), "tool_time_share") is None
    assert record_value(record(ttft_ms=900), "ttft") == 900.0


@pytest.mark.parametrize(
    ("metric", "kind", "direction"),
    [
        ("verdict", MetricKind.RATE, Direction.HIGHER),
        ("passed", MetricKind.RATE, Direction.HIGHER),
        ("cost", MetricKind.SPREAD, Direction.LOWER),
        ("cost_per_pass", MetricKind.SPREAD, Direction.LOWER),
        ("skill_cost_share", MetricKind.FRACTION, Direction.LOWER),
        ("compactions", MetricKind.RARE, Direction.LOWER),
        ("throughput", MetricKind.SPREAD, Direction.HIGHER),
        ("tool_calls", MetricKind.SPREAD, Direction.LOWER),
        ("errors", MetricKind.RATE, Direction.LOWER),
        ("wasted_cost", MetricKind.SPREAD, Direction.LOWER),
        ("skill_triggered", MetricKind.FRACTION, Direction.HIGHER),
        ("cache", MetricKind.FRACTION, Direction.HIGHER),
        ("ttft", MetricKind.SPREAD, Direction.LOWER),
        ("subagent_max_depth", MetricKind.RARE, Direction.LOWER),
        ("cache_rereads", MetricKind.SPREAD, Direction.LOWER),
        ("context_cost_share", MetricKind.FRACTION, Direction.LOWER),
    ],
)
def test_each_metric_has_a_kind_and_a_better_direction(metric: str, kind: MetricKind, direction: Direction) -> None:
    assert (kind_of(metric), direction_of(metric)) == (kind, direction)


@pytest.mark.parametrize("metric", ["harness", "family_tier", "context_window", "skill_files", "exit_code"])
def test_a_non_numeric_field_or_a_fact_about_the_cell_is_no_metric(metric: str) -> None:
    with pytest.raises(ValueError):
        kind_of(metric)


@pytest.mark.parametrize("metric", ["subagents", "files_written", "reasoning_share", "tool_time_share"])
def test_a_neutral_metric_has_a_kind_but_no_assumed_direction(metric: str) -> None:
    kind_of(metric)
    with pytest.raises(ValueError, match="no better direction"):
        direction_of(metric)


def test_versions_are_ordered_by_first_or_last_appearance_and_latest_follows_a_revert() -> None:
    s = Samples(
        [
            record(at="2026-10-03", subject_version="v2"),
            record(at="2026-10-01", subject_version="v1"),
            record(at="2026-10-04", subject_version="v1"),
            record(at="2026-10-02"),
        ]
    )
    assert s.first_seen("subject_version") == ("v1", "v2")
    # Reverted to v1 on the 4th: v1 is the subject as it now stands.
    assert s.last_seen("subject_version") == ("v2", "v1")
    assert [r.subject_version for r in s.latest()] == ["v1", "v1"]
    assert len(Samples().latest()) == 0


def test_adding_merges_oldest_first_with_each_session_once() -> None:
    a, b = record(at="2026-10-02"), record(at="2026-10-01")
    merged = Samples([a]) + Samples([b, a])
    assert merged.records == (b, a)
    assert merged == Samples([b, a]) and merged != [b, a]
    assert repr(merged) == "Samples(2 records)"
