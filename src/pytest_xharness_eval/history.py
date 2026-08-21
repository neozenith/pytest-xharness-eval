"""Per-cell metrics and the append-only run history (ADR 0018).

Every live cell produces one flat metrics record. It is shown in the verbose status
word, attached to the JUnit ``user_properties``, and appended as one JSON line to
``<skill>/evals/captured/history.jsonl``, beside the other run output (git-ignored);
derive anything longer-lived from it.
"""

from __future__ import annotations

# Standard Library
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult


def metrics_of(result: RunResult, *, node: str, verdict: str, wall_ms: int, started_at: str) -> dict[str, Any]:
    """The flat, JSON-ready metrics record for one cell."""
    return {
        "at": started_at,
        "node": node,
        "harness": result.harness,
        "model": result.model,
        "session_id": result.session_id,
        "verdict": verdict,
        "turns": result.turns,
        "tool_calls": sum(result.tool_calls.values()),
        "tool_calls_by_name": dict(result.tool_calls),
        "duration_ms": result.duration_ms,
        "wall_ms": wall_ms,
        "cost_usd": result.cost_usd,
        "tokens": result.usage.total_tokens,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cache_read_tokens": result.usage.cache_read_tokens,
        "cache_write_tokens": result.usage.cache_write_tokens,
        "files_written": len(result.files_written),
    }


def now_iso() -> str:
    """UTC timestamp, second precision, for the ``at`` field."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def append(path: Path, record: dict[str, Any]) -> Path:
    """Append ``record`` as one JSON line; parents are created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def status_word(record: dict[str, Any]) -> str:
    """The detail shown after the verdict in ``-v`` output."""
    return (
        f"${record['cost_usd']:.4f}  {record['tokens']:,} tok  {record['wall_ms'] / 1000:.1f}s  "
        f"{record['turns']} turns  {record['tool_calls']} tools"
    )
