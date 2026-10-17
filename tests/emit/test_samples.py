"""``emit.samples``: each cell's samples reduced to its Important Metrics in ``index.json`` (ADR 0071)."""

# Standard Library
import dataclasses
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import Usage
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.emit.index import UNKNOWN_CASE
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.emit.samples import ImportantMetrics, cell_key, is_sample
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.metrics import IMPORTANT_METRICS
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _metrics, _result


def _sample(model: str = "m", verdict: Verdict = Verdict.PASS, *, cost: float = 1.0, **fields: object) -> CellMetrics:
    record = _metrics(_result(model, Usage(10, 20)), verdict=verdict)
    return dataclasses.replace(record, estimated_cost_usd=cost, **fields)  # type: ignore[arg-type]


def test_every_declared_field_is_a_key_of_the_per_session_record() -> None:
    """The declaration names history.json keys; a typo here would aggregate nothing, silently."""
    keys = set(CellMetrics().to_dict())
    for metric in IMPORTANT_METRICS:
        assert metric.field in keys, metric.id
        assert metric.per is None or metric.per in keys, metric.id


def test_a_sample_is_a_graded_session_and_a_dry_run_or_unreadable_verdict_is_not() -> None:
    assert is_sample(_sample(verdict=Verdict.FAIL))
    assert is_sample(_sample(verdict=Verdict.ERROR))
    assert not is_sample(_sample(verdict=Verdict.DRY_RUN))
    assert not is_sample(dataclasses.replace(_sample(), verdict="maybe"))


def test_a_cell_is_skill_case_harness_model_effort_and_treatment() -> None:
    record = dataclasses.replace(_sample(), skill="s", case="eval_x", effort="", treatment="t")
    assert cell_key(record) == ("s", "eval_x", "claude", "m", None, "t")
    assert cell_key(dataclasses.replace(record, case=None))[1] == UNKNOWN_CASE


def test_samples_of_one_cell_reduce_together_and_another_model_is_another_cell() -> None:
    doc = ImportantMetrics.of(
        [
            _sample(cost=1.0),
            _sample(cost=3.0, verdict=Verdict.FAIL),
            _sample(cost=2.0),
            _sample("other", cost=9.0),
            _sample(cost=100.0, verdict=Verdict.DRY_RUN),
        ]
    )
    assert [(c.model, c.samples) for c in doc.cells] == [("m", 3), ("other", 1)]
    first = doc.cells[0].metrics
    assert first["cost"] == {"median": 2.0, "p25": 1.5, "p75": 2.5, "n": 3}
    assert first["verdict"]["pass_rate"] == round(2 / 3, 6)


def test_a_record_from_before_a_metric_existed_drops_out_of_its_n() -> None:
    """compactions is None on an old record: n counts the samples that recorded it, never a zero."""
    doc = ImportantMetrics.of([_sample(compactions=None), _sample(compactions=2)])
    assert doc.cells[0].metrics["compactions"] == {"mean": 2.0, "share": 1.0, "n": 1}


def test_the_combine_step_writes_the_declaration_and_the_cells_into_index_json(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    session = cache.session(skill="demo", harness="claude", model="m", run="20261022T000000Z", session="sid1")
    _result("m", Usage(1, 2)).write(session.result)
    _sample().write(session.history)
    page.write(cache)

    doc = json.loads(cache.index.read_text(encoding="utf-8"))["important_metrics"]
    assert [m["id"] for m in doc["metrics"]] == [m.id for m in IMPORTANT_METRICS]
    assert [(c["model"], c["samples"]) for c in doc["cells"]] == [("m", 1)]
    assert set(doc["cells"][0]["metrics"]) == {m.id for m in IMPORTANT_METRICS}
