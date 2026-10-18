"""Builders for the Analyzer's tests: real ``CellMetrics`` records, built by keyword."""

# Standard Library
import itertools
from typing import Any

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.verdict import Verdict

_SERIAL = itertools.count()


def record(**fields: Any) -> CellMetrics:
    """One graded session record: a pass of ``demo/eval_x`` on claude/opus at $1, unless overridden."""
    i = next(_SERIAL)
    base: dict[str, Any] = {
        "at": f"2026-10-01T{i:08d}",
        "session_id": f"sid-{i}",
        "node": f"node-{i}",
        "skill": "demo",
        "case": "eval_x",
        "harness": "claude",
        "model": "opus",
        "verdict": Verdict.PASS.value,
        "estimated_cost_usd": 1.0,
    }
    return CellMetrics(**(base | fields))


def batch(n: int, passes: int, **fields: Any) -> list[CellMetrics]:
    """``n`` records of one cell, the first ``passes`` of them passing and the rest failing."""
    fail = {"verdict": Verdict.FAIL.value, "failure": "AssertionError: wrong"}
    return [record(**(fields | ({} if i < passes else fail))) for i in range(n)]
