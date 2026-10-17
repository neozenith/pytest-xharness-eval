"""``emit.unfolded``: the record a billed run leaves when its logs would not fold (ADR 0072)."""

# Standard Library
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval.emit.unfolded import UnfoldedRecord
from pytest_xharness_eval.model.runresult import CaseRef
from tests.support import _unfoldable


def test_the_record_keeps_the_refusal_and_what_a_later_fold_needs(tmp_path: Path) -> None:
    err = _unfoldable(tmp_path)
    case = CaseRef(suite="s.py", name="eval_x", skill="demo", fixture="seed", task="go", prompt="/demo go")
    record = UnfoldedRecord.of(err.evidence, str(err), case=case, effort="high", treatment=None)
    written = json.loads(record.write(tmp_path / "out" / "unfolded.json").read_text(encoding="utf-8"))
    assert "no captured subagent transcript: tu_x" in written["error"]
    # The keys a replay reads back from result.json, so one reader serves both documents.
    assert (written["harness"], written["session_id"], written["exit_code"]) == ("claude", "sid-u", 0)
    assert (written["final_text"], written["duration_ms"], written["harness_reported_cost_usd"]) == ("done", 900, 0.5)
    assert "result" not in written["envelope"] and written["envelope"]["session_id"] == "sid-u"
    assert (written["files_written"], written["case"]["prompt"], written["effort"]) == (["a.md"], "/demo go", "high")
    assert (written["timed_out_after_s"], written["idle_before_timeout_s"]) == (None, None)
