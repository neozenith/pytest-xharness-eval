"""The record a billed run leaves when its logs would not fold (ADR 0072).

A run whose subagents do not pair with their spawns stops before any :class:`RunResult`
exists, but the CLI was paid and its logs are real. The cell copies them into the session
directory and writes this record beside them in place of ``result.json``. The report skips
the directory as a partial capture, and a replay retries the fold from it.

Its keys are the ``result.json`` keys a replay reads back, the ones each harness's
``session_from_capture`` needs plus the cell's own facts, so one reader serves both.
"""

from __future__ import annotations

# Standard Library
import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.harness.base import Evidence
    from pytest_xharness_eval.model.runresult import CaseRef


@dataclass(frozen=True, slots=True, kw_only=True)
class UnfoldedRecord:
    """One unfoldable run: why it would not fold, and what a later fold needs from outside its log."""

    harness: str
    session_id: str
    #: The fold's own refusal, verbatim.
    error: str
    workspace: str
    files_written: list[str]
    exit_code: int
    #: Claude's stdout envelope minus its ``result`` text, which is ``final_text``; empty for Codex.
    envelope: dict[str, Any] = field(default_factory=dict)
    final_text: str = ""
    duration_ms: int = 0
    harness_reported_cost_usd: float | None = None
    case: dict[str, str] = field(default_factory=dict)
    effort: str | None = None
    treatment: str | None = None
    timed_out_after_s: int | None = None
    idle_before_timeout_s: float | None = None

    @classmethod
    def of(cls, evidence: Evidence, error: str, *, case: CaseRef, effort: str | None, treatment: str | None) -> Self:
        """The record of ``evidence``, with the cell facts no log carries."""
        envelope = evidence.envelope
        duration = envelope.get("duration_ms")
        cost = envelope.get("total_cost_usd")
        return cls(
            harness=evidence.harness,
            session_id=evidence.session_id,
            error=error,
            workspace=str(evidence.workspace),
            files_written=list(evidence.files_written),
            exit_code=evidence.exit_code,
            envelope={k: v for k, v in envelope.items() if k != "result"},
            final_text=str(envelope.get("result") or ""),
            duration_ms=int(duration) if isinstance(duration, int | float) else 0,
            harness_reported_cost_usd=float(cost) if isinstance(cost, int | float) else None,
            case=case.to_dict(),
            effort=effort,
            treatment=treatment,
            timed_out_after_s=evidence.timed_out_after_s,
            idle_before_timeout_s=evidence.idle_before_timeout_s,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> Path:
        """Serialise to ``path`` as indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path
