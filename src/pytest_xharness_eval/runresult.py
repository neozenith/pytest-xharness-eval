"""The normalised record both harness adapters produce (ADR 0003, ADR 0019, ADR 0021)."""

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
    ``cache_write_1h_tokens`` and ``cache_write_5m_tokens`` are the TTL split of
    ``cache_write_tokens`` where the harness reports one (Claude does); the
    remainder is priced at the plain cache-write rate.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_write_5m_tokens: int = 0

    @property
    def accumulative_billed_tokens(self) -> int:
        """Every billed token: the four priced tiers summed (reasoning is inside output).

        Summed over every model call, so the cached prefix counts once per call
        that re-read it. The per-turn waterfall in the report shows the same
        figure accumulating turn by turn.
        """
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def add(self, other: Usage) -> None:
        """Accumulate ``other`` into this usage, tier by tier."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cache_write_1h_tokens += other.cache_write_1h_tokens
        self.cache_write_5m_tokens += other.cache_write_5m_tokens


@dataclass
class ToolCall:
    """One tool invocation the model issued in a turn; ``input`` is the full argument payload."""

    name: str
    summary: str
    input: Any = None


@dataclass
class ToolResult:
    """One tool result that entered the context before a turn; ``content`` is complete, never truncated."""

    tool: str
    chars: int
    content: str


@dataclass
class Call:
    """One model API call, a *SessionTurn* in the report: what it cost, was given, and did (ADR 0019).

    ``records`` are the 1-based line numbers of the captured session log that belong
    to this turn (the call's own records and everything logged since the previous
    turn), so a reader can render the raw evidence without re-deriving the split.
    """

    n: int
    at: str
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = ""
    text: str = ""
    thinking: str = ""
    tools: list[ToolCall] = field(default_factory=list)
    results_in: list[ToolResult] = field(default_factory=list)
    records: list[int] = field(default_factory=list)
    # Wall time from the previous log record to this call's first record: request + generation (ADR 0024).
    latency_ms: int | None = None

    @property
    def context_tokens(self) -> int:
        """The prompt this call processed: uncached input plus both cache tiers.

        This is the figure the provider reported, so it already reflects whatever the
        server kept or dropped of earlier thinking; it is measured, not estimated.
        """
        return self.usage.input_tokens + self.usage.cache_read_tokens + self.usage.cache_write_tokens

    @property
    def output_tokens_per_sec(self) -> float | None:
        """Output tokens over the call's latency; None when latency is unknown or zero."""
        if not self.latency_ms:
            return None
        return round(self.usage.output_tokens / (self.latency_ms / 1000), 2)


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
    # What the harness CLI itself said the run cost (Claude only); never used to price.
    harness_reported_cost_usd: float | None = None
    # What this plugin's price table says, with the rates it applied (ADR 0021).
    estimated_cost_usd: float | None = None
    cost_status: str = "unpriced"
    cost_by_tier: dict[str, float] = field(default_factory=dict)
    rates_applied: dict[str, Any] = field(default_factory=dict)
    # The per-call ledger. ``turns`` is its length; ``usage`` is its sum.
    calls: list[Call] = field(default_factory=list)
    # The CLI's own aggregates, kept verbatim so a sweep can show how far they sit from the ledger.
    reported_usage: dict[str, int] = field(default_factory=dict)
    reported_turns: int | None = None
    # Claude's envelope ``modelUsage``: per-model tokens and USD, including side calls the log omits.
    reported_model_usage: dict[str, Any] = field(default_factory=dict)
    # The CLI's whole stdout envelope (Claude) verbatim, minus the result text already on ``final_text``,
    # so a cost or usage figure that drifts from the ledger can be explained later without a re-run.
    envelope: dict[str, Any] = field(default_factory=dict)
    # How many session-log records of each kind the run produced (ADR 0022; see ``records.py``).
    record_kinds: dict[str, int] = field(default_factory=dict)
    # Which of the skill's files the run loaded or ran, per turn, and which it never touched (ADR 0022).
    skill_coverage: dict[str, Any] = field(default_factory=dict)
    # The model's context window as the harness reported it, and the run's timing (ADR 0024).
    context_window: int | None = None
    ttft_ms: int | None = None
    api_duration_ms: int | None = None
    # The case that produced this run: suite file, case name, skill, fixture, prompt (ADR 0025).
    case: dict[str, Any] = field(default_factory=dict)

    @property
    def baseline_tokens(self) -> int:
        """The context of the first call: everything the harness loads before the agent acts."""
        return self.calls[0].context_tokens if self.calls else 0

    @property
    def peak_context_tokens(self) -> int:
        """The largest prompt any call processed."""
        return max((c.context_tokens for c in self.calls), default=0)

    @property
    def final_context_tokens(self) -> int:
        """The context after the last call: its prompt plus what it generated."""
        return (self.calls[-1].context_tokens + self.calls[-1].usage.output_tokens) if self.calls else 0

    def pct_of_window(self, tokens: int) -> float | None:
        """``tokens`` as a percentage of the context window; None when the window is unknown."""
        if not self.context_window:
            return None
        return round(100.0 * tokens / self.context_window, 2)

    @property
    def context_window_pct(self) -> float | None:
        """Peak context as a percentage of the window: how close the run came to the limit."""
        return self.pct_of_window(self.peak_context_tokens)

    @property
    def final_context_pct(self) -> float | None:
        """Final context (last prompt plus its output) as a percentage of the window."""
        return self.pct_of_window(self.final_context_tokens)

    @property
    def output_tokens_per_sec(self) -> float | None:
        """Output tokens over the harness-reported API time (else wall duration); None if neither is known."""
        ms = self.api_duration_ms or self.duration_ms
        if not ms:
            return None
        return round(self.usage.output_tokens / (ms / 1000), 2)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready mapping, with the derived token and timing figures included."""
        d = asdict(self)
        d["usage"]["accumulative_billed_tokens"] = self.usage.accumulative_billed_tokens
        d["baseline_tokens"] = self.baseline_tokens
        d["peak_context_tokens"] = self.peak_context_tokens
        d["final_context_tokens"] = self.final_context_tokens
        d["context_window_pct"] = self.context_window_pct
        d["final_context_pct"] = self.final_context_pct
        d["output_tokens_per_sec"] = self.output_tokens_per_sec
        for call, raw in zip(self.calls, d["calls"], strict=True):
            raw["context_tokens"] = call.context_tokens
            raw["context_pct"] = self.pct_of_window(call.context_tokens)
            raw["output_tokens_per_sec"] = call.output_tokens_per_sec
        return d

    def write(self, path: Path) -> Path:
        """Serialise to ``path`` as indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path
