"""How the run went about it: budgets and behaviours read off the run record (ADR 0045, ADR 0071, ADR 0073).

The checks in :mod:`~pytest_xharness_eval.verify.checks` ask whether the run is real and
what it left behind; these ask what it *spent* and *did* on the way, over the measured
fields of :class:`~pytest_xharness_eval.model.runresult.RunResult`:

* spend and time -- :func:`check_cost_within`, :func:`check_wall_within`,
  :func:`check_context_within`, :func:`check_no_compaction`, :func:`check_cache_efficiency`,
  :func:`check_no_timeout`, :func:`check_no_long_context`;
* tool calls -- :func:`check_tool_calls_within`, :func:`check_tool_durations_within`,
  :func:`check_tool_cost_within`, :func:`check_commands_ran`;
* the skill under test -- :func:`check_skill_triggered`, :func:`check_skill_cost_within`;
* delegation -- :func:`check_subagents_within`, :func:`check_subagent_durations_within`,
  :func:`check_subagent_cost_within`.

Every tool-call check counts the same calls: every thread's, the primary's and each
subagent's, read off their ledgers -- so a count, a duration and a cost always agree on
what a "call" is.

A budget is a case's claim about a behaviour, not a pricing control: a run over it still
cost what it cost. Every message names the figure measured and, where several things
contribute, the worst offenders. A figure the pipeline never attached (an unpriced run,
no tool costs) fails the check rather than passing it, as :func:`check_run_is_priced` does.
"""

from __future__ import annotations

# Standard Library
import re
from collections import Counter
from enum import StrEnum
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.model.registry import Shells

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator

    # Our Libraries
    from pytest_xharness_eval.derive.toolcost import SkillUse, ToolCost
    from pytest_xharness_eval.model.output import CaseOutput
    from pytest_xharness_eval.model.runresult import Call, RunResult, ToolCall


class CostKind(StrEnum):
    """Which of a tool call's two attributed costs a check sums (ADR 0073).

    A closed vocabulary rather than a ``Literal``, so a misspelled word stops the grader
    instead of silently summing the other attribution. It lives here, not in ``model/``,
    because only this grader layer speaks it (ADR 0041 moves a vocabulary to ``model/`` once
    two layers share it): the derivation layer names the two figures as fields, never as words.
    """

    ISSUING = "issuing"
    CONTEXT = "context"


class Threads(StrEnum):
    """Which threads a check reads: the primary's alone, or every thread's."""

    PRIMARY = "primary"
    ALL = "all"


#: How many offenders a message lists.
_WORST = 5


# -- spend and time -----------------------------------------------------------------------


def check_cost_within(output: CaseOutput, usd: float) -> None:
    """The run's estimated cost, subagents included, is at most ``usd``."""
    cost = output.run.estimated_cost_usd
    assert cost is not None, "the run carries no cost estimate, so no budget can be judged; it was never priced"
    assert cost <= usd, f"the run cost ${cost:.4f}, over the ${usd:.4f} this case allows ({_cost_split(output.run)})"


def _cost_split(run: RunResult) -> str:
    subs = [s.estimated_cost_usd or 0.0 for s in run.subagents]
    tiers = ", ".join(f"{tier} ${usd:.4f}" for tier, usd in sorted(run.cost_by_tier.items()))
    return f"{len(subs)} subagent(s) ${sum(subs):.4f}; by tier: {tiers or 'none'}"


def check_wall_within(output: CaseOutput, seconds: float) -> None:
    """The CLI's wall-clock run took at most ``seconds``."""
    took = output.run.duration_ms / 1000
    assert took <= seconds, (
        f"the run took {took:.1f}s of wall clock, over the {seconds:.1f}s this case allows "
        f"({output.run.turns} turn(s), {len(output.run.subagents)} subagent(s))"
    )


def check_context_within(output: CaseOutput, pct: float, *, threads: Threads | str = Threads.PRIMARY) -> None:
    """The largest prompt any call processed stayed within ``pct`` percent of the context window.

    ``threads="primary"`` (the default) reads the primary thread's calls; ``"all"`` reads
    every subagent's too, each against the window the harness reported for the run.

    Raises:
        RuntimeError: when the harness reported no context window. That is a gap in what
            the CLI logged, not something the agent did, so the cell errors.
    """
    run = output.run
    if run.context_window is None:
        raise RuntimeError(f"the {run.harness} run reported no context window, so its context share is unknown")
    peak, where = max(
        ((c.context_tokens, thread) for thread, calls in _threads(run, Threads(threads)) for c in calls),
        default=(0, ""),
    )
    used = run.pct_of_window(peak) or 0.0
    assert used <= pct, (
        f"the {where or 'primary'} thread's peak prompt was {peak} tokens, {used:.1f}% of the "
        f"{run.context_window}-token window, over the {pct:.1f}% this case allows"
    )


def check_no_compaction(output: CaseOutput) -> None:
    """The primary thread never compacted its context: it fit the task in one window.

    The primary's only: a harness counts compactions off the primary session log's record
    kinds, and a subagent's transcript carries no such count, so there is no ``threads``
    reading of this check (use :func:`check_context_within` with ``threads="all"``).
    """
    n = output.run.compactions
    assert n == 0, f"the run compacted its context {n} time(s); peak prompt {output.run.peak_context_tokens} tokens"


def check_cache_efficiency(output: CaseOutput, min_cache_read_share: float) -> None:
    """At least ``min_cache_read_share`` of every prompt token was read from the provider's cache.

    The share is :attr:`RunResult.cache_read_share`: ``cache_read / (input + cache_read +
    cache_write)`` over the whole run, subagents included. A low share on a long run usually
    means the prefix kept changing.
    """
    run = output.run
    usage = run.usage
    share = run.cache_read_share
    assert share is not None, "the run processed no prompt tokens, so it has no cache share to judge"
    prompt = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    assert share >= min_cache_read_share, (
        f"{share:.1%} of the run's {prompt} prompt tokens were cache reads, below {min_cache_read_share:.1%} "
        f"(uncached {usage.input_tokens}, cache writes {usage.cache_write_tokens})"
    )


def check_no_timeout(output: CaseOutput) -> None:
    """The CLI finished on its own rather than being killed at the wall-clock limit (ADR 0064).

    A live cell refuses a timed-out run before its grader is asked anything, so this reads
    true there; it states the claim for a grader re-run over a stored record.
    """
    run = output.run
    idle = f", {run.idle_before_timeout_s:.0f}s after its logs went silent" if run.idle_before_timeout_s else ""
    assert run.timed_out_after_s is None, f"the run was killed at the {run.timed_out_after_s}s timeout{idle}"


def check_no_long_context(output: CaseOutput) -> None:
    """No call was billed at the model's long-context tier (ADR 0051): every prompt stayed under its threshold."""
    run = output.run
    n = run.long_context_calls
    assert n is not None, "the run was never priced, so which calls crossed the long-context tier is unknown"
    assert n == 0, f"{n} call(s) were billed at the long-context tier; peak prompt {run.peak_context_tokens} tokens"


# -- tool calls ---------------------------------------------------------------------------


def _threads(run: RunResult, threads: Threads = Threads.ALL) -> Iterator[tuple[str, list[Call]]]:
    """Each thread's ledger: the primary (empty id) first, then every subagent unless ``threads`` is primary."""
    yield "", run.calls
    if threads is Threads.ALL:
        for sub in run.subagents:
            yield sub.id, sub.calls


def _tool_calls(run: RunResult) -> Iterator[tuple[str, ToolCall]]:
    for thread, calls in _threads(run):
        for call in calls:
            for tool in call.tools:
                yield thread, tool


def _label(thread: str, tool: ToolCall) -> str:
    where = f" in {thread}" if thread else ""
    return f"{tool.name}{where} {tool.summary!r}".rstrip()


def check_tool_calls_within(output: CaseOutput, *, at_most: int, name: str | None = None) -> None:
    """The run made at most ``at_most`` tool calls, of tool ``name`` when given, in any thread.

    Counted off every thread's ledger, the same calls :func:`check_tool_durations_within`
    and :func:`check_tool_cost_within` read -- not the harness's primary-only
    ``RunResult.tool_calls`` -- so delegating work to a subagent does not hide its calls.
    """
    counts = Counter(tool.name for _, tool in _tool_calls(output.run))
    made = counts.get(name, 0) if name is not None else sum(counts.values())
    what = f"{name} call(s)" if name is not None else "tool call(s)"
    assert made <= at_most, (
        f"the run made {made} {what}, more than the {at_most} allowed; it called {dict(sorted(counts.items()))}"
    )


def check_tool_durations_within(output: CaseOutput, ms: int, *, name: str | None = None) -> None:
    """No tool call (of ``name``, when given) took longer than ``ms``, in any thread.

    A call whose result never came back has no duration and is not counted here; the run
    that left it is caught by the wall-clock limit instead.
    """
    slow = sorted(
        (
            (tool.duration_ms, thread, tool)
            for thread, tool in _tool_calls(output.run)
            if (name is None or tool.name == name) and tool.duration_ms is not None and tool.duration_ms > ms
        ),
        key=lambda row: -(row[0] or 0),
    )
    listed = "\n".join(f"  {d}ms {_label(thread, tool)}" for d, thread, tool in slow[:_WORST])
    assert not slow, f"{len(slow)} tool call(s) took longer than {ms}ms:\n{listed}"


def _costs(output: CaseOutput) -> list[ToolCost]:
    costs = output.run.tool_costs
    assert costs or not output.run.tool_calls, (
        "the run made tool calls but carries no tool costs; the pipeline never attributed them"
    )
    return costs


def _usd(cost: ToolCost | SkillUse, kind: CostKind) -> float:
    return cost.issuing_cost_usd if kind is CostKind.ISSUING else cost.context_cost_usd


def check_tool_cost_within(
    output: CaseOutput, usd: float, *, name: str | None = None, kind: CostKind | str = CostKind.ISSUING
) -> None:
    """The tool calls (of ``name``, when given) cost at most ``usd`` together, attributed by ``kind``.

    ``issuing`` is what the calls that asked for the tools cost, split across their tools;
    ``context`` is what carrying the tools' results through later prompts cost (ADR 0073).
    Both are attributions, never part of the run's estimate.
    """
    kind = CostKind(kind)
    matching = [c for c in _costs(output) if name is None or c.name == name]
    total = round(sum(_usd(c, kind) for c in matching), 6)
    worst = sorted(matching, key=lambda c: -_usd(c, kind))[:_WORST]
    listed = "\n".join(f"  ${_usd(c, kind):.4f} {c.name} turn {c.turn} {c.summary!r}" for c in worst)
    what = f"{name} calls" if name is not None else "tool calls"
    assert total <= usd, (
        f"the run's {what} cost ${total:.4f} ({kind}), over the ${usd:.4f} allowed; costliest:\n{listed}"
    )


def _commands(run: RunResult) -> Iterator[str]:
    """Every shell command of every thread: what the model asked for, and what the shell reported."""
    shells = Shells.of(run.harness)
    for _, calls in _threads(run):
        for call in calls:
            for tool in call.tools:
                if tool.name in shells.tools:
                    yield from (command for command, _ in shells.commands(tool.input) if command)
            yield from (ran.command for ran in call.executed)


def check_commands_ran(output: CaseOutput, *patterns: str) -> None:
    """Each regex in ``patterns`` matches at least one shell command the run issued, in any thread.

    Read through the harness's own shell vocabulary (ADR 0034), from the tool calls the
    model issued and the commands the harness reported as executed (ADR 0048), so it
    means the same thing on both dialects.
    """
    assert patterns, "check_commands_ran needs at least one pattern to look for"
    ran = list(dict.fromkeys(_commands(output.run)))
    missing = [p for p in patterns if not any(re.search(p, command) for command in ran)]
    shown = "\n".join(f"  {c}" for c in ran[-_WORST * 4 :]) or "  (none)"
    assert not missing, f"the run never ran a command matching {missing}. Commands it ran:\n{shown}"


# -- the skill under test -----------------------------------------------------------------


def _skill_use(output: CaseOutput) -> SkillUse:
    use = output.run.skill_use
    assert use is not None, (
        f"the skill under test was never triggered: no prompt named it and no tool call touched its files. "
        f"Tools called: {dict(sorted(output.run.tool_calls.items())) or 'none'}"
    )
    return use


def check_skill_triggered(output: CaseOutput, *, by: str | None = None, within_turns: int | None = None) -> None:
    """The skill under test was triggered, by ``by`` (``prompt`` or a tool name) and by turn ``within_turns``.

    Turns are the primary thread's (``Call.n``). A subagent's touch of a skill file is
    credited at the primary turn its spawn descends from, never at the subagent's own turn
    number (``derive/skillcov.accesses``, ADR 0056), so a skill a subagent loaded at its own
    turn 1 after a turn-4 spawn was triggered at turn 4.
    """
    use = _skill_use(output)
    if by is not None:
        assert use.trigger == by, f"the skill was triggered by {use.trigger!r} at turn {use.triggered_turn}, not {by!r}"
    if within_turns is not None:
        assert use.triggered_turn <= within_turns, (
            f"the skill was first triggered at turn {use.triggered_turn} (by {use.trigger!r}), "
            f"later than the turn {within_turns} this case allows"
        )


def check_skill_cost_within(output: CaseOutput, usd: float, *, kind: CostKind | str = CostKind.ISSUING) -> None:
    """The tool calls that touched the skill under test cost at most ``usd``, attributed by ``kind``."""
    kind = CostKind(kind)
    use = _skill_use(output)
    spent = _usd(use, kind)
    assert spent <= usd, (
        f"the skill's {use.tool_calls} tool call(s) cost ${spent:.4f} ({kind}) over turns "
        f"{use.triggered_turn}-{use.last_turn}, over the ${usd:.4f} allowed"
    )


# -- delegation ---------------------------------------------------------------------------


def check_subagents_within(output: CaseOutput, *, at_most: int | None = None, max_depth: int | None = None) -> None:
    """The run spawned at most ``at_most`` threads, none nested deeper than ``max_depth``."""
    subs = output.run.subagents
    if at_most is not None:
        agents = sorted({s.agent for s in subs})
        assert len(subs) <= at_most, (
            f"the run spawned {len(subs)} subagent(s), more than the {at_most} allowed ({agents})"
        )
    if max_depth is not None:
        deep = [f"{s.id} (depth {s.depth}, spawned by {s.spawned_by})" for s in subs if s.depth > max_depth]
        assert not deep, f"{len(deep)} subagent(s) nested deeper than {max_depth}: {deep[:_WORST]}"


def check_subagent_durations_within(output: CaseOutput, ms: int, *, agent: str | None = None) -> None:
    """No subagent (of type ``agent``, when given) ran longer than ``ms`` from first record to last."""
    slow = sorted(
        (
            s
            for s in output.run.subagents
            if (agent is None or s.agent == agent) and s.duration_ms is not None and s.duration_ms > ms
        ),
        key=lambda s: -(s.duration_ms or 0),
    )
    listed = "\n".join(
        f"  {s.duration_ms}ms {s.agent} {s.id} ({s.turns} turn(s), {s.output_tokens_per_sec} tok/s)" for s in slow
    )
    assert not slow, f"{len(slow)} subagent(s) ran longer than {ms}ms:\n{listed}"


def check_subagent_cost_within(output: CaseOutput, usd: float, *, agent: str | None = None) -> None:
    """No subagent (of type ``agent``, when given) cost more than ``usd`` at its own model's rates (ADR 0065).

    Per thread, not summed: :func:`check_cost_within` already bounds the whole run. A thread
    that carries no estimate fails the check rather than passing it, as an unpriced run does.
    """
    subs = [s for s in output.run.subagents if agent is None or s.agent == agent]
    unpriced = [s.id for s in subs if s.estimated_cost_usd is None]
    assert not unpriced, f"{len(unpriced)} subagent(s) carry no cost estimate, so no budget can be judged: {unpriced}"
    costly = sorted(
        (s for s in subs if (s.estimated_cost_usd or 0.0) > usd), key=lambda s: -(s.estimated_cost_usd or 0)
    )
    listed = "\n".join(
        f"  ${s.estimated_cost_usd or 0.0:.4f} {s.agent} {s.id} ({s.model or output.run.model}, {s.turns} turn(s))"
        for s in costly[:_WORST]
    )
    assert not costly, f"{len(costly)} subagent(s) cost more than ${usd:.4f}:\n{listed}"
