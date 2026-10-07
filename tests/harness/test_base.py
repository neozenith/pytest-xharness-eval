"""``harness.base``: what every harness shares when a CLI is killed at the wall-clock limit (ADR 0064)."""

# Standard Library
import os
from pathlib import Path

# Our Libraries
from pytest_xharness_eval.harness import base
from pytest_xharness_eval.harness import claude as claude_harness


def test_seconds_idle_is_the_gap_since_the_newest_log_was_written(tmp_path: Path) -> None:
    """The last sign of activity a killed run left behind (ADR 0064)."""
    old, new = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    new.write_text("{}\n", encoding="utf-8")
    os.utime(old, (1000.0, 1000.0))
    os.utime(new, (1900.0, 1900.0))
    assert base.seconds_idle([old, new, tmp_path / "missing.jsonl"], now=2000.0) == 100.0
    assert base.seconds_idle([tmp_path / "missing.jsonl"], now=2000.0) is None


def test_a_timed_out_claude_run_gets_an_envelope_that_claims_no_figures() -> None:
    envelope = claude_harness.timed_out_envelope("sid-1")
    assert envelope == {"session_id": "sid-1", "is_error": True, "result": ""}
