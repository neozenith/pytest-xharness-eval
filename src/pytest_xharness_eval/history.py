"""Per-cell metrics and the append-only run history (ADR 0018, ADR 0019, ADR 0021).

Every live cell produces one flat metrics record. It is shown in the verbose status
word, attached to the JUnit ``user_properties``, and appended as one JSON line to
``<skill>/evals/captured/history.jsonl``, beside the other run output (git-ignored);
derive anything longer-lived from it.

Metric vocabulary (ADR 0021; the report glossary carries the same names):

* ``estimated_cost_usd``: this plugin's price-table estimate; ``rates_applied``
  records the per-tier rates, the row and the file they came from.
* ``harness_reported_cost_usd``: what the harness CLI itself reported (Claude only).
* ``accumulative_billed_tokens``: every billed token summed over every model call (ADR 0029). The cached
  prefix is re-read each call, so this grows with turns x context.
* ``baseline_tokens``: the prompt of the first call, before the agent acted.
* ``turns``: model API calls; ``reported_turns`` is the CLI's own count.
"""

from __future__ import annotations

# Standard Library
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult


def metrics_of(result: RunResult, *, node: str, verdict: str, wall_ms: int, started_at: str) -> dict[str, Any]:
    """The flat, JSON-ready metrics record for one cell.

    Flat and built of builtins on purpose: this record travels to the xdist controller on
    ``TestReport.user_properties``, which serialises builtins only (ADR 0016).
    """
    u = result.usage
    case = result.case
    cov = result.skill_coverage
    summary = cov.summary if cov else None
    return {
        "at": started_at,
        "node": node,
        "suite": case.suite if case else None,
        "case": case.name if case else None,
        "skill": case.skill if case else None,
        "fixture": case.fixture if case else None,
        "harness": result.harness,
        "model": result.model,
        "session_id": result.session_id,
        "verdict": verdict,
        "turns": result.turns,
        "reported_turns": result.reported_turns,
        "tool_calls": sum(result.tool_calls.values()),
        "tool_calls_by_name": dict(result.tool_calls),
        "duration_ms": result.duration_ms,
        "wall_ms": wall_ms,
        "estimated_cost_usd": result.estimated_cost_usd,
        "harness_reported_cost_usd": result.harness_reported_cost_usd,
        "rates_applied": asdict(result.rates_applied) if result.rates_applied else {},
        "accumulative_billed_tokens": u.accumulative_billed_tokens,
        "baseline_tokens": result.baseline_tokens,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "reasoning_tokens": u.reasoning_tokens,
        "cache_read_tokens": u.cache_read_tokens,
        "cache_write_tokens": u.cache_write_tokens,
        "cache_write_1h_tokens": u.cache_write_1h_tokens,
        "files_written": len(result.files_written),
        "context_window": result.context_window,
        "peak_context_tokens": result.peak_context_tokens,
        "context_window_pct": result.context_window_pct,
        "final_context_pct": result.final_context_pct,
        "ttft_ms": result.ttft_ms,
        "output_tokens_per_sec": result.output_tokens_per_sec,
        "record_kinds": dict(result.record_kinds),
        "skill_files": summary.files if summary else None,
        "skill_files_loaded": summary.loaded if summary else None,
        "skill_scripts": summary.scripts if summary else None,
        "skill_scripts_run": summary.run if summary else None,
        "skill_not_loaded": list(cov.not_loaded) if cov else [],
        "skill_not_run": list(cov.not_run) if cov else [],
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
    """The detail shown after the verdict in ``-v`` output.

    The estimate comes first; where the harness reported its own cost it follows in
    brackets, so drift between the two is visible on every cell.
    """
    cost = f"est ${record['estimated_cost_usd']:.4f}"
    reported = record.get("harness_reported_cost_usd")
    if reported is not None:
        cost += f" (harness ${reported:.4f})"
    billed = f"{record['accumulative_billed_tokens']:,} accumulative_billed_tokens"
    baseline = f"{record['baseline_tokens']:,} baseline_tokens"
    word = (
        f"{cost}  {billed}  {baseline}  {record['wall_ms'] / 1000:.1f}s  "
        f"{record['turns']} turns  {record['tool_calls']} tools"
    )
    if record.get("context_window_pct") is not None:
        word += f"  ctx {record['context_window_pct']:.1f}%"
    if record.get("skill_files"):
        word += (
            f"  skill {record.get('skill_files_loaded', 0)}/{record['skill_files']} loaded"
            f" {record.get('skill_scripts_run', 0)}/{record.get('skill_scripts', 0)} run"
        )
    return word
