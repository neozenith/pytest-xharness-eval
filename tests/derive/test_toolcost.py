"""``derive.toolcost``: each tool call's time and cost two ways, and the skill's span (ADR 0073)."""

# Standard Library
from dataclasses import replace

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Call, ToolCall, ToolResult, Usage
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.derive.pricing import Interval
from pytest_xharness_eval.derive.skillcov import Access, SkillAccess
from pytest_xharness_eval.derive.toolcost import CHARS_PER_TOKEN, SkillUse, tool_costs

#: $1 per MTok of prompt (every prompt tier), $10 per MTok of output: easy arithmetic.
RATES = pricing.Rates.of(
    {"input": 1.0, "output": 10.0, "cache_read": 1.0, "cache_write": 1.0},
    harness="claude",
    model="m",
    source="test",
    interval=Interval(None, None),
)


def _tool(tool_id: str, start: str = "", end: str = "") -> ToolCall:
    return ToolCall("Read", f"read {tool_id}", {}, tool_id, started_at=start, ended_at=end)


def _call(n: int, *, read: int, out: int, tools: list[ToolCall] = (), results: list[ToolResult] = ()) -> Call:  # type: ignore[assignment]
    """A call whose prompt is ``read`` cached tokens (``read`` of 0 means none) plus 100 fresh."""
    usage = Usage(input_tokens=100, output_tokens=out, cache_read_tokens=read)
    return Call(n=n, at=f"t{n}", usage=usage, tools=list(tools), results_in=list(results))


def _ledger() -> list[Call]:
    """Turn 1 issues two reads; their 400- and 1,200-character results enter turn 2."""
    results = [ToolResult("Read", 400, "x" * 400, "a"), ToolResult("Read", 1200, "y" * 1200, "b")]
    return [
        _call(1, read=0, out=50, tools=[_tool("a", "2026-10-18T00:00:00Z", "2026-10-18T00:00:01.5Z"), _tool("b")]),
        # Prompt growth into turn 2: 1,000 + 100 - (100 + 50 output) = 950 >= the 400 estimated.
        _call(2, read=1000, out=10, results=results),
        _call(3, read=1100, out=10),
        _call(4, read=200, out=10),  # compacted: the prompt shrank below where the results entered
    ]


def test_issuing_cost_is_the_issuing_call_split_evenly_across_its_tools() -> None:
    a, b = tool_costs(_ledger(), RATES)
    turn_one = (100 * 1.0 + 50 * 10.0) / 1_000_000
    assert a.issuing_cost_usd == b.issuing_cost_usd == round(turn_one / 2, 6)
    assert (a.duration_ms, b.duration_ms) == (1500, None)  # b's result was never stamped


def test_context_cost_follows_a_result_until_the_context_shrinks_below_it() -> None:
    a, b = tool_costs(_ledger(), RATES)
    assert (a.result_tokens, b.result_tokens) == (400 // CHARS_PER_TOKEN, 1200 // CHARS_PER_TOKEN)
    # Read at turn 2, re-read from cache at turn 3, gone by turn 4.
    assert [(c.turn, c.cached) for c in a.trace] == [(2, False), (3, True)]
    # Each turn's share is the result's share of that turn's prompt cost.
    assert a.trace[0].usd == round(100 / 1100 * 1100 / 1_000_000, 6)
    assert a.context_cost_usd == round(sum(c.usd for c in a.trace), 6) and a.cache_rereads == 1


def test_estimated_result_tokens_never_exceed_the_measured_prompt_growth() -> None:
    results = [ToolResult("Read", 40_000, "", "a")]
    calls = [_call(1, read=0, out=0, tools=[_tool("a")]), _call(2, read=100, out=0, results=results)]
    (a,) = tool_costs(calls, RATES)
    assert a.result_tokens == 100  # 10,000 estimated, but the prompt grew by 100


def test_a_tool_whose_result_nothing_read_has_no_context_cost() -> None:
    (a,) = tool_costs([_call(1, read=0, out=5, tools=[_tool("a")])], RATES)
    assert (a.result_tokens, a.context_cost_usd, a.cache_rereads, a.trace) == (0, 0.0, 0, [])


def _hit(tool_id: str, path: str, turn: int, access: Access = Access.LOADED) -> SkillAccess:
    return SkillAccess(thread="", call=turn, turn=turn, tool_id=tool_id, tool="Read", path=path, access=access)


def test_a_skills_span_runs_first_trigger_to_last_touch_and_counts_each_tool_call_once() -> None:
    a, b = tool_costs(_ledger(), RATES)
    a, b = replace(a, started_at="2026-10-18T00:00:00Z"), replace(b, started_at="2026-10-18T00:00:09Z")
    hits = [_hit("a", "SKILL.md", 1), _hit("a", "guide.md", 1), _hit("b", "scripts/x.py", 1, Access.RUN)]
    use = SkillUse.of("demo", hits, [a, b])
    assert use is not None
    assert (use.trigger, use.triggered_at, use.last_at, use.duration_ms) == (
        "Read",
        "2026-10-18T00:00:00Z",
        "2026-10-18T00:00:09Z",
        9000,
    )
    assert use.tool_calls == 2 and len(use.events) == 3  # a touched two files: two events, one call
    assert use.issuing_cost_usd == round(a.issuing_cost_usd + b.issuing_cost_usd, 6)
    assert use.cache_rereads == a.cache_rereads + b.cache_rereads


def test_a_prompt_that_names_the_skill_triggers_it_before_any_file_is_touched() -> None:
    use = SkillUse.of("demo", [], [], prompt_at="2026-10-18T00:00:00Z")
    assert use is not None and (use.trigger, use.triggered_turn, use.tool_calls) == ("prompt", 1, 0)


def test_an_untouched_uninvoked_skill_has_no_use() -> None:
    assert SkillUse.of("demo", [], []) is None


@pytest.mark.parametrize("tool_id", ["", "unknown"])
def test_a_command_no_tool_call_owns_is_an_event_without_figures(tool_id: str) -> None:
    use = SkillUse.of("demo", [_hit(tool_id, "SKILL.md", 2)], [])
    assert use is not None and use.tool_calls == 0
    (event,) = use.events
    assert (event.issuing_cost_usd, event.context_cost_usd, event.duration_ms) == (None, None, None)
