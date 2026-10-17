"""What each tool call cost and took, and the same for the skill under test (ADR 0073).

Providers bill tokens, never tools, so a tool call's cost is an attribution, made two ways:

- **Issuing cost**: the model call that asked for the tool, priced as billed and split evenly
  across the tools that call issued. What it cost to decide to run it.
- **Context cost**: the tokens the tool's result added to the context, priced at the call
  that first read them and at every later call that carried them, until the context shrank
  below where they entered (a compaction). What its output cost to keep. Each later call's
  share is that call's prompt cost times the result's share of its prompt, and every share is
  kept as a per-turn trace, so a result's downstream impact can be followed turn by turn.

A result's tokens are not reported per result by either provider. They are estimated from
its characters (:data:`CHARS_PER_TOKEN`) and bounded by what was measured: the prompt growth
at the call that read it, net of the previous call's own output.

A skill's use is built from the tool calls that touched its catalogued files: its span runs
from the first trigger to the last touch, and its costs sum each such tool call once.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

# Our Libraries
from pytest_xharness_eval.derive.pricing import tier_costs
from pytest_xharness_eval.model.clock import ms_between

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable
    from datetime import date

    # Our Libraries
    from pytest_xharness_eval.derive.pricing import PriceTable, Rates
    from pytest_xharness_eval.derive.skillcov import Access, SkillAccess
    from pytest_xharness_eval.model.runresult import Call, RunResult, ToolCall

#: Characters per token for estimating a tool result's size; bounded by measured prompt growth.
CHARS_PER_TOKEN = 4


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCharge:
    """One call's share of carrying a tool's result: the turn, whether it was re-read from cache, and USD."""

    turn: int
    cached: bool
    usd: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCost:
    """One tool call: when it ran, how long it took, and what it cost, both ways."""

    #: The thread that issued it: empty for the primary, else the subagent's id.
    thread: str
    #: That thread's turn (``Call.n``) that issued it.
    turn: int
    id: str
    name: str
    summary: str
    started_at: str
    ended_at: str
    duration_ms: int | None
    #: The issuing call's billed cost over the number of tools it issued.
    issuing_cost_usd: float
    #: The estimated tokens its result added to the context; 0 when no later call read it.
    result_tokens: int
    #: The sum of :attr:`trace`.
    context_cost_usd: float
    #: How many later calls re-read the result from the prompt cache.
    cache_rereads: int
    trace: list[ToolCharge] = field(default_factory=list)


def _call_costs(calls: list[Call], rates: Rates) -> tuple[list[float], list[float]]:
    """Each call's billed USD, and the part of it that paid for the prompt (everything but output)."""
    whole: list[float] = []
    prompt: list[float] = []
    for call in calls:
        tiers = tier_costs(call.usage, rates.for_request(call.usage))
        whole.append(sum(tiers.values()))
        prompt.append(sum(tiers.values()) - tiers["output"])
    return whole, prompt


def _entered(calls: list[Call]) -> dict[str, tuple[int, int]]:
    """For each tool id: the index of the call that first read its result, and its estimated tokens."""
    entered: dict[str, tuple[int, int]] = {}
    for j in range(1, len(calls)):
        before, call = calls[j - 1], calls[j]
        estimates = {r.id: r.chars / CHARS_PER_TOKEN for r in call.results_in if r.id}
        total = sum(estimates.values())
        if not total:
            continue
        growth = max(call.context_tokens - before.context_tokens - before.usage.output_tokens, 0)
        scale = min(1.0, growth / total)
        for tool_id, estimate in estimates.items():
            entered.setdefault(tool_id, (j, round(estimate * scale)))
    return entered


def _trace(calls: list[Call], prompt_usd: list[float], start: int, tokens: int) -> list[ToolCharge]:
    """The result's share of each call that carried it, from ``start`` until the context shrank below it."""
    floor = calls[start].context_tokens
    trace: list[ToolCharge] = []
    for m in range(start, len(calls)):
        context = calls[m].context_tokens
        if m > start and context < floor:
            break
        if context:
            trace.append(
                ToolCharge(
                    turn=calls[m].n,
                    cached=m > start and calls[m].usage.cache_read_tokens > 0,
                    usd=round(tokens / context * prompt_usd[m], 6),
                )
            )
    return trace


def tool_costs(calls: list[Call], rates: Rates, thread: str = "") -> list[ToolCost]:
    """Every tool call one thread's ledger issued, timed and priced at ``rates`` (that thread's model)."""
    whole, prompt = _call_costs(calls, rates)
    entered = _entered(calls)
    out: list[ToolCost] = []
    for i, call in enumerate(calls):
        for tool in call.tools:
            start, tokens = entered.get(tool.id, (-1, 0))
            trace = _trace(calls, prompt, start, tokens) if start >= 0 and tokens else []
            out.append(_cost(tool, thread, call.n, whole[i] / len(call.tools), tokens, trace))
    return out


def run_tool_costs(result: RunResult, table: PriceTable, day: date | None) -> list[ToolCost]:
    """Every thread's tool costs, each thread at the rates of the model that answered it (ADR 0065)."""
    rates = table.resolve(result.harness, result.model, day)
    costs = tool_costs(result.calls, rates)
    for sub in result.subagents:
        sub_rates = table.resolve(result.harness, sub.model, day) if sub.model else rates
        costs += tool_costs(sub.calls, sub_rates, sub.id)
    return costs


def _cost(tool: ToolCall, thread: str, turn: int, issuing: float, tokens: int, trace: list[ToolCharge]) -> ToolCost:
    return ToolCost(
        thread=thread,
        turn=turn,
        id=tool.id,
        name=tool.name,
        summary=tool.summary,
        started_at=tool.started_at,
        ended_at=tool.ended_at,
        duration_ms=tool.duration_ms,
        issuing_cost_usd=round(issuing, 6),
        result_tokens=tokens,
        context_cost_usd=round(sum(c.usd for c in trace), 6),
        cache_rereads=sum(c.cached for c in trace),
        trace=trace,
    )


# -- the skill under test -------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillEvent:
    """One touch of one skill file, with the figures of the tool call that made it.

    A tool call that touched two files appears as two events with the same figures; the
    :class:`SkillUse` totals count each tool call once.
    """

    thread: str
    turn: int
    tool_id: str
    tool: str
    path: str
    access: Access
    started_at: str
    duration_ms: int | None
    issuing_cost_usd: float | None
    context_cost_usd: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillUse:
    """When the skill under test was triggered, how long it was in use, and what its tool calls cost."""

    skill: str
    #: ``prompt`` when the run's own invocation named the skill, else the tool that first touched it.
    trigger: str
    triggered_turn: int
    triggered_at: str
    last_turn: int
    last_at: str
    #: From :attr:`triggered_at` to :attr:`last_at`.
    duration_ms: int | None
    #: The distinct tool calls that touched a skill file.
    tool_calls: int
    issuing_cost_usd: float
    context_cost_usd: float
    cache_rereads: int
    events: list[SkillEvent] = field(default_factory=list)

    @classmethod
    def of(
        cls, skill: str, hits: Iterable[SkillAccess], costs: list[ToolCost], prompt_at: str | None = None
    ) -> Self | None:
        """The skill's use from its file accesses and the tool costs; None when nothing triggered it.

        ``prompt_at`` is the time of the run's first turn when its invocation named the skill,
        which triggers it before any file is touched.
        """
        by_id = {(c.thread, c.id): c for c in costs}
        events = [_event(hit, by_id.get((hit.thread, hit.tool_id))) for hit in hits]
        if not events and prompt_at is None:
            return None
        used = {(e.thread, e.tool_id): by_id[(e.thread, e.tool_id)] for e in events if (e.thread, e.tool_id) in by_id}
        stamped = [e for e in events if e.started_at]
        first = min(stamped, key=lambda e: e.started_at, default=None)
        last = max(stamped, key=lambda e: e.started_at, default=None)
        triggered_at = prompt_at if prompt_at is not None else (first.started_at if first else "")
        last_at = last.started_at if last else triggered_at
        return cls(
            skill=skill,
            trigger="prompt" if prompt_at is not None else (first.tool if first else events[0].tool),
            triggered_turn=1 if prompt_at is not None else (first.turn if first else events[0].turn),
            triggered_at=triggered_at,
            last_turn=last.turn if last else (1 if prompt_at is not None else events[-1].turn),
            last_at=last_at,
            duration_ms=ms_between(triggered_at, last_at),
            tool_calls=len(used),
            issuing_cost_usd=round(sum(c.issuing_cost_usd for c in used.values()), 6),
            context_cost_usd=round(sum(c.context_cost_usd for c in used.values()), 6),
            cache_rereads=sum(c.cache_rereads for c in used.values()),
            events=events,
        )


def _event(hit: SkillAccess, cost: ToolCost | None) -> SkillEvent:
    """One access with its tool call's figures; a shell-reported command no tool call owns has none."""
    return SkillEvent(
        thread=hit.thread,
        turn=hit.turn,
        tool_id=hit.tool_id,
        tool=hit.tool,
        path=hit.path,
        access=hit.access,
        started_at=cost.started_at if cost else "",
        duration_ms=cost.duration_ms if cost else None,
        issuing_cost_usd=cost.issuing_cost_usd if cost else None,
        context_cost_usd=cost.context_cost_usd if cost else None,
    )
