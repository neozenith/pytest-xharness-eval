"""``model.metrics``: the Important Metrics declaration and each kind's aggregates (ADR 0071)."""

# Standard Library
import json
import math
import os
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model.metrics import (
    AGGREGATES,
    IMPORTANT_METRICS,
    Aggregate,
    ImportantMetric,
    MetricKind,
    Unit,
    summarise,
    wilson,
)


def test_the_declaration_names_each_metric_once_and_every_kind_reports_n() -> None:
    ids = [m.id for m in IMPORTANT_METRICS]
    assert len(ids) == len(set(ids))
    assert all(kind_aggregates[-1] is Aggregate.N for kind_aggregates in AGGREGATES.values())
    assert set(AGGREGATES) == set(MetricKind)


def test_a_spread_is_the_median_and_quartiles_so_one_runaway_sample_cannot_drag_it() -> None:
    out = summarise(MetricKind.SPREAD, [1.0, 2.0, 3.0, 4.0, 1000.0])
    assert out == {"median": 3.0, "p25": 2.0, "p75": 4.0, "n": 5}


def test_one_sample_is_its_own_median_and_quartiles() -> None:
    assert summarise(MetricKind.SPREAD, [7.5]) == {"median": 7.5, "p25": 7.5, "p75": 7.5, "n": 1}


def test_a_fraction_is_the_mean_with_its_extremes() -> None:
    assert summarise(MetricKind.FRACTION, [0.25, 0.5, 0.75]) == {"mean": 0.5, "min": 0.25, "max": 0.75, "n": 3}


def test_a_rare_count_is_the_mean_and_the_share_of_samples_where_it_happened() -> None:
    assert summarise(MetricKind.RARE, [0.0, 0.0, 2.0, 1.0]) == {"mean": 0.75, "share": 0.5, "n": 4}


def test_a_rate_carries_its_wilson_interval() -> None:
    out = summarise(MetricKind.RATE, [1.0, 1.0, 0.0, 1.0])
    assert out["pass_rate"] == 0.75 and out["n"] == 4
    low, high = out["ci_low"], out["ci_high"]
    assert isinstance(low, float) and isinstance(high, float)
    assert 0.0 < low < 0.75 < high < 1.0


@pytest.mark.parametrize("kind", list(MetricKind))
def test_no_samples_is_n_zero_and_every_other_aggregate_absent_never_zero(kind: MetricKind) -> None:
    out = summarise(kind, [])
    assert out[Aggregate.N.value] == 0
    assert all(v is None for k, v in out.items() if k != Aggregate.N.value)


def test_the_wilson_interval_is_honest_at_the_edges() -> None:
    assert wilson(1, 1)[1] == 1.0 and wilson(1, 1)[0] < 0.5  # one pass is weak evidence
    assert wilson(0, 1)[0] == 0.0 and wilson(0, 1)[1] > 0.5
    low, high = wilson(50, 100)
    assert math.isclose(low, 0.4038, abs_tol=1e-3) and math.isclose(high, 0.5962, abs_tol=1e-3)


def _metric(**overrides: object) -> ImportantMetric:
    fields: dict[str, object] = {"id": "x", "label": "x", "field": "a", "kind": MetricKind.SPREAD, "unit": Unit.COUNT}
    return ImportantMetric(**(fields | overrides), why="")  # type: ignore[arg-type]


def test_a_value_is_read_from_its_field_or_divided_by_its_denominator() -> None:
    assert _metric().value({"a": 3}) == 3.0
    assert _metric(per="b").value({"a": 3, "b": 4}) == 0.75
    # Absent, null, a non-number, a boolean, or a zero denominator: not recorded, never zero.
    assert _metric().value({}) is None
    assert _metric().value({"a": None}) is None
    assert _metric().value({"a": "3"}) is None
    assert _metric().value({"a": True}) is None
    assert _metric(per="b").value({"a": 3, "b": 0}) is None


def test_a_verdict_counts_pass_as_one_any_other_grade_as_zero_and_a_dry_run_not_at_all() -> None:
    verdict = _metric(field="verdict", kind=MetricKind.RATE)
    assert [verdict.value({"verdict": w}) for w in ("pass", "fail", "error", "dry-run", "", "maybe")] == [
        1.0,
        0.0,
        0.0,
        None,
        None,
        None,
    ]


def test_summarise_skips_the_samples_that_did_not_record_the_metric() -> None:
    out = _metric().summarise([{"a": 1}, {}, {"a": 3}, {"a": None}])
    assert out["n"] == 2 and out["median"] == 2.0


def test_the_declaration_serialises_its_aggregates_spelled_out() -> None:
    cost = next(m for m in IMPORTANT_METRICS if m.id == "cost")
    assert cost.to_dict() == {
        "id": "cost",
        "label": "cost",
        "field": "estimated_cost_usd",
        "per": None,
        "kind": "spread",
        "unit": "usd",
        "why": cost.why,
        "aggregates": ["median", "p25", "p75", "n"],
    }


def test_the_report_ui_fixture_is_the_declaration() -> None:
    """The page's unit tests mount these columns, so they hold the plugin's real declaration.

    Regenerate deliberately with ``XHARNESS_UPDATE_GOLDEN=1 uv run pytest tests/model/test_metrics.py``.
    """
    fixture = Path(__file__).parents[2] / "report-ui" / "src" / "__tests__" / "important-metrics.json"
    declared = [m.to_dict() for m in IMPORTANT_METRICS]
    if os.environ.get("XHARNESS_UPDATE_GOLDEN"):
        fixture.write_text(json.dumps(declared, indent=2) + "\n", encoding="utf-8")
    assert json.loads(fixture.read_text(encoding="utf-8")) == declared
