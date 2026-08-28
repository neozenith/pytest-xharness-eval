"""The normalised record both harness adapters produce (ADR 0003, ADR 0019, ADR 0021).

The types here carry their own invariants rather than restating them in prose (ADR 0035):
:class:`Usage` is frozen and accumulates only by producing a new total, so "usage is the
whole bill" is enforced by :meth:`RunResult.folded` computing it once; a price estimate
lands through :meth:`RunResult.apply_cost` as one indivisible block; and the case that
produced a run and the skill files it touched are typed records, not free-form mappings.

``to_dict`` stays ``asdict(self)`` plus derived keys. That is the serialisation contract:
every field name below is a key of ``result.json``, which ``report-ui/src/lib/types.ts``
mirrors, so a field rename here is a wire-format change.
"""

from __future__ import annotations

# Standard Library
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.case import EvalCase
    from pytest_xharness_eval.pricing import AppliedRates, CostEstimate
    from pytest_xharness_eval.skillcov import SkillCoverage


@dataclass(frozen=True, slots=True)
class Usage:
    """Token counts, normalised across both harness dialects; a total is never mutated.

    Cache tiers are kept separate because they price differently; collapsing
    them into ``input_tokens`` overstates cost by roughly an order of magnitude.
    ``cache_write_1h_tokens`` and ``cache_write_5m_tokens`` are the TTL split of
    ``cache_write_tokens`` where the harness reports one (Claude does); the
    remainder is priced at the plain cache-write rate.

    Frozen so that "a run's usage is its whole bill" cannot be broken by a second
    fold adding the same subagents twice: the only way to accumulate is
    :meth:`__add__`, and the only caller that does is :meth:`RunResult.folded`
    (ADR 0035).
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

    def __add__(self, other: Usage) -> Usage:
        """The tier-wise sum of two usages, as a new total."""
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cache_write_1h_tokens=self.cache_write_1h_tokens + other.cache_write_1h_tokens,
            cache_write_5m_tokens=self.cache_write_5m_tokens + other.cache_write_5m_tokens,
        )

    @classmethod
    def total(cls, usages: Iterable[Usage]) -> Usage:
        """The tier-wise sum of ``usages``, zero when there are none."""
        out = cls()
        for usage in usages:
            out = out + usage
        return out


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool invocation the model issued in a turn; ``input`` is the full argument payload.

    ``id`` is the harness's tool-use id (Claude ``tool_use.id``, Codex ``call_id``): the key a
    tool result — or a subagent transcript — points back at.
    """

    name: str
    summary: str
    input: Any = None
    id: str = ""


@dataclass(frozen=True, slots=True)
class ToolResult:
    """One tool result that entered the context before a turn; ``content`` is complete, never truncated."""

    tool: str
    chars: int
    content: str


@dataclass(slots=True)
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


@dataclass(slots=True)
class Subagent:
    """One parallel thread the primary session spawned, with its own captured transcript.

    Claude writes each subagent to ``<session>/subagents/agent-<id>.jsonl`` beside the
    session log; Codex forks one rollout per spawned thread. Both fold through the same
    ledger machinery as the primary, so a subagent carries its own :class:`Call` list and
    :class:`Usage`. ``parent_turn`` is the primary turn whose tool call spawned it
    (matched by tool-use id on Claude, by spawn timestamp on Codex). ``log`` is the
    captured transcript path relative to the session directory (``subagents/<name>``),
    absolute only before capture.
    """

    agent: str
    id: str
    log: str
    parent_turn: int | None = None
    turns: int = 0
    description: str = ""
    usage: Usage = field(default_factory=Usage)
    calls: list[Call] = field(default_factory=list)

    @classmethod
    def folded(cls, calls: list[Call], **fields: Any) -> Self:
        """A subagent whose ``turns`` and ``usage`` are derived from its own ledger.

        ``fields`` are the identity ones the transcript's metadata supplies (``agent``,
        ``id``, ``log``, ``parent_turn``, ``description``).
        """
        return cls(turns=len(calls), usage=Usage.total(c.usage for c in calls), calls=calls, **fields)


class CostStatus(StrEnum):
    """Whether a result carries a price-table estimate. There is no third state (ADR 0007).

    A ``str`` subclass, so ``asdict`` keeps the member and ``json.dumps`` writes the
    bare word the wire format has always carried.
    """

    UNPRICED = "unpriced"
    PRICED = "priced"


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseRef:
    """The case that produced a run: suite file, case name, skill, fixture, prompt (ADR 0025).

    One type for the three places that used to hand-build this record — the live cell, a
    replay carrying it forward, and a replay recovering it from the suite — so they cannot
    disagree about its keys. The field names are the ``case`` keys of ``result.json``.
    """

    suite: str = ""
    name: str = ""
    skill: str = ""
    fixture: str = ""
    prompt: str = ""

    @classmethod
    def of(cls, case: EvalCase, suite: str) -> Self:
        """The reference to ``case`` as collected from the suite file ``suite``."""
        return cls(suite=suite, name=case.name, skill=case.skill, fixture=case.fixture, prompt=case.prompt)

    @classmethod
    def stored(cls, raw: Mapping[str, Any] | None) -> Self | None:
        """The reference a captured ``result.json`` carries, or None when it names no case."""
        if not raw:
            return None
        return cls(
            suite=str(raw.get("suite") or ""),
            name=str(raw.get("name") or ""),
            skill=str(raw.get("skill") or ""),
            fixture=str(raw.get("fixture") or ""),
            prompt=str(raw.get("prompt") or ""),
        )


@dataclass
class RunResult:
    """One eval cell's outcome: what the agent did, cost, and where the proof is.

    Build one with :meth:`folded` rather than by hand: it is what makes ``usage`` the
    run's whole bill and ``turns`` the primary ledger's length, derived once from the
    same ledger rather than by each adapter (ADR 0035).
    """

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
    # What this plugin's price table says, with the rates it applied (ADR 0021). The four
    # move together through ``apply_cost`` and are written nowhere else.
    estimated_cost_usd: float | None = None
    cost_status: CostStatus = CostStatus.UNPRICED
    cost_by_tier: dict[str, float] = field(default_factory=dict)
    rates_applied: AppliedRates | None = None
    # The per-call ledger of the primary thread. ``turns`` is its length; ``usage`` is its
    # sum plus every subagent's, so pricing bills the whole run.
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
    skill_coverage: SkillCoverage | None = None
    # The model's context window as the harness reported it, and the run's timing (ADR 0024).
    context_window: int | None = None
    ttft_ms: int | None = None
    api_duration_ms: int | None = None
    # The case that produced this run (ADR 0025).
    case: CaseRef | None = None
    # Parallel threads the session spawned, each with its own ledger. Their usage is folded
    # into ``usage`` (the run's billed total); ``turns`` and ``calls`` stay the primary's.
    subagents: list[Subagent] = field(default_factory=list)

    @classmethod
    def folded(cls, calls: list[Call], subagents: Iterable[Subagent] = (), **fields: Any) -> Self:
        """The one constructor a harness adapter uses once its ledgers are folded.

        ``turns`` is the primary ledger's length and ``usage`` is that ledger's sum plus
        every subagent's — the run's whole bill, computed here and nowhere else, so a
        second fold cannot bill the spawned threads twice (ADR 0033, ADR 0035).
        ``fields`` are the remaining RunResult fields, which are the dialect's own.
        """
        subs = sorted(subagents, key=lambda s: (s.parent_turn or 0, s.agent, s.id))
        return cls(
            turns=len(calls),
            usage=Usage.total(c.usage for c in calls) + Usage.total(s.usage for s in subs),
            calls=calls,
            subagents=subs,
            **fields,
        )

    def apply_cost(self, estimate: CostEstimate) -> None:
        """Record a price-table estimate: the total, the tier split, the rates and the status.

        The four fields are written together and only here, so a result can never carry a
        cost without the provenance that explains it (ADR 0007, ADR 0021).
        """
        self.estimated_cost_usd = estimate.total_usd
        self.cost_by_tier = estimate.by_tier
        self.rates_applied = estimate.rates
        self.cost_status = CostStatus.PRICED

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
        """A JSON-ready mapping, with the derived token and timing figures included.

        ``asdict`` is the serialiser, not a per-field walk: it renders the typed records
        (``case``, ``skill_coverage``, ``rates_applied``) into the exact key sets they
        declare, and passes a plain mapping through unchanged for the callers that hand
        one straight to the field. An absent record has always serialised as ``{}``.
        """
        d = asdict(self)
        for absent in ("case", "skill_coverage", "rates_applied"):
            d[absent] = d[absent] or {}
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
        for sub, raw_sub in zip(self.subagents, d["subagents"], strict=True):
            raw_sub["usage"]["accumulative_billed_tokens"] = sub.usage.accumulative_billed_tokens
            for call, raw in zip(sub.calls, raw_sub["calls"], strict=True):
                raw["context_tokens"] = call.context_tokens
                raw["context_pct"] = self.pct_of_window(call.context_tokens)
                raw["output_tokens_per_sec"] = call.output_tokens_per_sec
        return d

    def write(self, path: Path) -> Path:
        """Serialise to ``path`` as indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path
