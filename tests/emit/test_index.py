"""``emit.index``: the report index row and its frozen wire format (ADR 0037)."""

# Standard Library
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import (
    Usage,
)
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.model.layout import CacheLayout
from tests.support import _result

# Every key of one ``report/index.json`` row, likewise.
INDEX_ROW_KEYS = [
    "accumulative_billed_tokens",
    "at",
    "baseline_tokens",
    "case",
    "context_window",
    "context_window_pct",
    "duration_ms",
    "effort",
    "estimated_cost_usd",
    "files_written",
    "final_context_pct",
    "fixture",
    "harness",
    "harness_reported_cost_usd",
    "has_ledger",
    "log",
    "model",
    "node",
    "output_tokens_per_sec",
    "peak_context_tokens",
    "prompt",
    "rates_applied",
    "record_kinds",
    "reported_turns",
    "result",
    "run",
    "session_id",
    "skill",
    "skill_coverage",
    "subagents",
    "suite",
    "task",
    "tool_calls",
    "treatment",
    "ttft_ms",
    "turns",
    "verdict",
    "wall_ms",
]


def test_index_json_has_exactly_the_frozen_key_set(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    session = cache.session(skill="demo", harness="claude", model="m", run="20261022T000000Z", session="sid1")
    _result("m", Usage(1, 2)).write(session.result)
    page.write(cache)

    index = json.loads(cache.index.read_text(encoding="utf-8"))
    assert sorted(index) == ["captured", "cells", "generated_at", "inline"]
    assert sorted(index["cells"][0]) == INDEX_ROW_KEYS
