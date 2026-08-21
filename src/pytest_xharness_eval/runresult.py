"""The normalised record both harness adapters produce (ADR 0003)."""

from __future__ import annotations

# Standard Library
import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


@dataclass
class Usage:
    """Token counts, normalised across both harness dialects.

    Cache tiers are kept separate because they price differently; collapsing
    them into ``input_tokens`` overstates cost by roughly an order of magnitude.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Every billed token: the four priced tiers summed (reasoning is inside output)."""
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens


@dataclass
class RunResult:
    """One eval cell's outcome: what the agent did, cost, and where the proof is."""

    harness: str
    model: str
    session_id: str
    session_log: str
    workspace: str
    exit_code: int
    duration_ms: int
    turns: int
    final_text: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: dict[str, int] = field(default_factory=dict)
    files_written: list[str] = field(default_factory=list)
    reported_cost_usd: float | None = None
    cost_usd: float | None = None
    cost_status: str = "unpriced"

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready mapping, with the derived ``total_tokens`` included."""
        d = asdict(self)
        d["usage"]["total_tokens"] = self.usage.total_tokens
        return d

    def write(self, path: Path) -> Path:
        """Serialise to ``path`` as sorted, indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path
