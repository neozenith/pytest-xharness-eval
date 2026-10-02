"""``emit.summary``: the ``report.json`` document (ADR 0040)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Cell,
    Usage,
)
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.emit.summary import RunSummary
from tests.support import _metrics, _result


def test_the_run_summary_is_the_two_keys_report_json_has_always_had(tmp_path: Path) -> None:
    priced = _result("claude-opus-5", Usage(10, 20))
    priced.estimated_cost_usd = 0.25
    cells = [
        _metrics(priced, node="n1", cache=str(tmp_path / "cache")),
        CellMetrics.dry_run(node="n2", cell=Cell(harness="claude", model="claude-opus-5")),
    ]
    summary = RunSummary.of(cells)

    assert summary.total_usd == pytest.approx(0.25)
    # A dry-run record names no cache root, which is what keeps a free run free (ADR 0018).
    assert summary.cache_roots() == [str(tmp_path / "cache")]
    doc = json.loads(summary.write(tmp_path / "report" / "report.json").read_text(encoding="utf-8"))
    assert sorted(doc) == ["cells", "total_usd"]
    assert doc["total_usd"] == 0.25
    assert [(c["node"], c["verdict"]) for c in doc["cells"]] == [("n1", "pass"), ("n2", "dry-run")]
