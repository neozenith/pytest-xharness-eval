"""``verify.conduct``: budgets and behaviours read off the run record (ADR 0045, ADR 0071, ADR 0073)."""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, RunResult, Usage, verify
from pytest_xharness_eval.derive.toolcost import SkillUse, ToolCost
from pytest_xharness_eval.model.runresult import Call, ExecutedCommand, ToolCall
from tests.support import _subagent

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


def _at(second: int) -> str:
    return f"2026-10-01T00:00:{second:02d}.000Z"


def _tool(name: str, id: str, start: int, end: int, **input: str) -> ToolCall:
    return ToolCall(name=name, summary=id, input=input, id=id, started_at=_at(start), ended_at=_at(end))


def _cost(name: str, id: str, issuing: float, context: float, thread: str = "") -> ToolCost:
    return ToolCost(
        thread=thread,
        turn=1,
        id=id,
        name=name,
        summary=id,
        started_at="",
        ended_at="",
        duration_ms=None,
        issuing_cost_usd=issuing,
        result_tokens=10,
        context_cost_usd=context,
        cache_rereads=1,
    )


@pytest.fixture
def output(tmp_path: Path) -> CaseOutput:
    """A two-turn Claude run with two nested subagents, priced, costed and with a skill use."""
    calls = [
        Call(
            n=1,
            at=_at(0),
            usage=Usage(input_tokens=100, cache_read_tokens=600, cache_write_tokens=300, output_tokens=50),
            tools=[
                _tool("Bash", "lint", 1, 4, command="bun run scripts/lint.ts NOTES.md"),
                _tool("Read", "guide", 4, 5, file_path="resources/guide.md"),
            ],
        ),
        Call(
            n=2,
            at=_at(6),
            usage=Usage(input_tokens=200, cache_read_tokens=1800, output_tokens=40),
            executed=[ExecutedCommand(tool="Bash", command="node scripts/check.ts --strict")],
        ),
    ]
    child = _subagent(
        [
            Call(
                n=1,
                at=_at(7),
                usage=Usage(output_tokens=30),
                latency_ms=1000,
                tools=[_tool("Bash", "g", 7, 8, command="grep -n TODO .")],
            )
        ],
        id="a1",
        ended_at=_at(40),
    )
    grandchild = _subagent(id="a2", agent="Explore", parent="a1", depth=2, spawned_by="toolu_9", ended_at=_at(5))
    run = RunResult.folded(
        calls,
        [child, grandchild],
        harness="claude",
        model="m",
        session_id="s",
        session_log="l",
        workspace=str(tmp_path),
        exit_code=0,
        duration_ms=42_000,
        final_text="",
        tool_calls={"Bash": 2, "Read": 1},
        context_window=4000,
    )
    run.estimated_cost_usd, run.cost_by_tier = 0.5, {"input": 0.1, "output": 0.4}
    child.estimated_cost_usd, grandchild.estimated_cost_usd = 0.05, 0.01
    run.tool_costs = [
        _cost("Bash", "lint", 0.2, 0.05),
        _cost("Read", "guide", 0.1, 0.01),
        _cost("Bash", "g", 0.03, 0.0, "a1"),
    ]
    run.skill_use = SkillUse(
        skill="demo",
        trigger="prompt",
        triggered_turn=1,
        triggered_at=_at(0),
        last_turn=2,
        last_at=_at(6),
        duration_ms=6000,
        tool_calls=2,
        issuing_cost_usd=0.3,
        context_cost_usd=0.06,
        cache_rereads=2,
    )
    return CaseOutput(run=run, workspace=tmp_path)


def test_cost_wall_and_context_budgets(output: CaseOutput) -> None:
    verify.check_cost_within(output, 0.5)
    with pytest.raises(AssertionError, match=r"cost \$0.5000, over the \$0.4000.*2 subagent\(s\) \$0.0600"):
        verify.check_cost_within(output, 0.4)
    verify.check_wall_within(output, 42)
    with pytest.raises(AssertionError, match=r"took 42.0s of wall clock, over the 30.0s"):
        verify.check_wall_within(output, 30)
    # Peak prompt is the second call's 2000 tokens: half the 4000-token window.
    verify.check_context_within(output, 50)
    with pytest.raises(AssertionError, match=r"2000 tokens, 50.0% of the 4000-token window"):
        verify.check_context_within(output, 40)


def test_context_can_be_read_over_every_thread(output: CaseOutput) -> None:
    output.run.subagents[0].calls[0].usage = Usage(input_tokens=3000)
    verify.check_context_within(output, 50)  # the primary's peak is still 2000 tokens
    with pytest.raises(AssertionError, match=r"the a1 thread's peak prompt was 3000 tokens, 75.0%"):
        verify.check_context_within(output, 50, threads="all")
    with pytest.raises(ValueError):
        verify.check_context_within(output, 50, threads="some")


def test_timeout_long_context_and_per_thread_subagent_cost(output: CaseOutput) -> None:
    verify.check_no_timeout(output)
    output.run.timed_out_after_s, output.run.idle_before_timeout_s = 600, 400.0
    with pytest.raises(AssertionError, match="killed at the 600s timeout, 400s after its logs went silent"):
        verify.check_no_timeout(output)
    with pytest.raises(AssertionError, match="never priced"):
        verify.check_no_long_context(output)
    output.run.long_context_calls = 0
    verify.check_no_long_context(output)
    output.run.long_context_calls = 2
    with pytest.raises(AssertionError, match=r"2 call\(s\) were billed at the long-context tier"):
        verify.check_no_long_context(output)
    verify.check_subagent_cost_within(output, 0.05)
    verify.check_subagent_cost_within(output, 0.01, agent="Explore")
    with pytest.raises(
        AssertionError, match=r"1 subagent\(s\) cost more than \$0.0200:\n  \$0.0500 general-purpose a1"
    ):
        verify.check_subagent_cost_within(output, 0.02)
    output.run.subagents[1].estimated_cost_usd = None
    with pytest.raises(AssertionError, match=r"carry no cost estimate.*\['a2'\]"):
        verify.check_subagent_cost_within(output, 1.0)


def test_an_unpriced_run_or_unknown_window_cannot_pass_a_budget(output: CaseOutput) -> None:
    output.run.estimated_cost_usd = None
    with pytest.raises(AssertionError, match="never priced"):
        verify.check_cost_within(output, 100)
    output.run.context_window = None
    with pytest.raises(RuntimeError, match="reported no context window"):
        verify.check_context_within(output, 100)


def test_compaction_and_cache_share(output: CaseOutput) -> None:
    verify.check_no_compaction(output)
    # 2400 cache reads of 3000 prompt tokens, subagents included.
    verify.check_cache_efficiency(output, 0.8)
    with pytest.raises(AssertionError, match=r"80.0% of the run's 3000 prompt tokens were cache reads, below 90.0%"):
        verify.check_cache_efficiency(output, 0.9)
    output.run.compactions = 2
    with pytest.raises(AssertionError, match="compacted its context 2 time"):
        verify.check_no_compaction(output)
    output.run.usage = Usage()
    with pytest.raises(AssertionError, match="no prompt tokens"):
        verify.check_cache_efficiency(output, 0.1)


def test_tool_call_counts_and_durations(output: CaseOutput) -> None:
    # Counted off every thread's ledger, like the durations: the subagent's grep is one of the Bash calls.
    output.run.tool_calls = {}
    verify.check_tool_calls_within(output, at_most=3)
    verify.check_tool_calls_within(output, at_most=2, name="Bash")
    with pytest.raises(AssertionError, match=r"made 2 Bash call\(s\), more than the 1"):
        verify.check_tool_calls_within(output, at_most=1, name="Bash")
    verify.check_tool_durations_within(output, 3000)
    verify.check_tool_durations_within(output, 1000, name="Read")
    with pytest.raises(AssertionError, match=r"1 tool call\(s\) took longer than 1000ms:\n  3000ms Bash 'lint'"):
        verify.check_tool_durations_within(output, 1000, name="Bash")


def test_tool_cost_is_summed_by_the_named_attribution(output: CaseOutput) -> None:
    verify.check_tool_cost_within(output, 0.33)
    verify.check_tool_cost_within(output, 0.06, kind="context")
    with pytest.raises(AssertionError, match=r"Bash calls cost \$0.2300 \(issuing\).*\n  \$0.2000 Bash turn 1 'lint'"):
        verify.check_tool_cost_within(output, 0.2, name="Bash")
    with pytest.raises(ValueError, match="'issued' is not a valid CostKind"):
        verify.check_tool_cost_within(output, 1.0, kind="issued")
    output.run.tool_costs = []
    with pytest.raises(AssertionError, match="never attributed them"):
        verify.check_tool_cost_within(output, 1.0)


def test_commands_are_read_from_tool_calls_executions_and_subagents(output: CaseOutput) -> None:
    verify.check_commands_ran(output, r"scripts/lint\.ts", r"check\.ts --strict", r"^grep -n TODO")
    with pytest.raises(AssertionError, match=r"never ran a command matching \['prettier'\].*\n  bun run scripts/lint"):
        verify.check_commands_ran(output, "prettier")
    with pytest.raises(AssertionError, match="at least one pattern"):
        verify.check_commands_ran(output)


def test_skill_trigger_and_cost(output: CaseOutput) -> None:
    verify.check_skill_triggered(output, by="prompt", within_turns=1)
    verify.check_skill_cost_within(output, 0.3)
    with pytest.raises(AssertionError, match="triggered by 'prompt' at turn 1, not 'Read'"):
        verify.check_skill_triggered(output, by="Read")
    with pytest.raises(AssertionError, match=r"2 tool call\(s\) cost \$0.0600 \(context\) over turns 1-2"):
        verify.check_skill_cost_within(output, 0.05, kind="context")
    output.run.skill_use = None
    with pytest.raises(AssertionError, match="never triggered"):
        verify.check_skill_triggered(output)


def test_a_late_trigger_fails_within_turns(output: CaseOutput) -> None:
    assert output.run.skill_use is not None
    late = SkillUse(**{**{f: getattr(output.run.skill_use, f) for f in SkillUse.__slots__}, "triggered_turn": 3})
    output.run.skill_use = late
    with pytest.raises(AssertionError, match="first triggered at turn 3"):
        verify.check_skill_triggered(output, within_turns=2)


def test_subagent_count_depth_and_duration(output: CaseOutput) -> None:
    verify.check_subagents_within(output, at_most=2, max_depth=2)
    with pytest.raises(AssertionError, match=r"spawned 2 subagent\(s\), more than the 1"):
        verify.check_subagents_within(output, at_most=1)
    with pytest.raises(AssertionError, match=r"nested deeper than 1: \['a2 \(depth 2, spawned by toolu_9\)'\]"):
        verify.check_subagents_within(output, max_depth=1)
    verify.check_subagent_durations_within(output, 40_000)
    verify.check_subagent_durations_within(output, 5000, agent="Explore")
    with pytest.raises(AssertionError, match=r"40000ms general-purpose a1 \(1 turn\(s\), 30.0 tok/s\)"):
        verify.check_subagent_durations_within(output, 30_000)
