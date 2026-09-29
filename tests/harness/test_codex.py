"""``harness.codex``: folding a Codex rollout into a run (ADR 0019, ADR 0033)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Usage,
)
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.harness import codex as codex_harness
from tests.support import _jsonl


def test_from_codex_context_window_latency_and_ttft(tmp_path: Path) -> None:
    def count(at: str, inp: int, out: int) -> dict[str, object]:
        usage = {"input_tokens": inp, "cached_input_tokens": 0, "output_tokens": out, "reasoning_output_tokens": 0}
        info = {"last_token_usage": usage, "total_token_usage": usage, "model_context_window": 258_400}
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": info}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {
                "type": "event_msg",
                "timestamp": "2026-08-23T00:00:00.000Z",
                "payload": {"type": "task_started", "model_context_window": 258_400},
            },
            count("2026-08-23T00:00:02.000Z", 18_000, 100),
            count("2026-08-23T00:00:05.000Z", 20_000, 300),
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "duration_ms": 5000,
                    "time_to_first_token_ms": 1234,
                    "last_agent_message": "ok",
                },
            },
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.context_window, r.ttft_ms, r.api_duration_ms) == (258_400, 1234, 5000)
    assert [c.latency_ms for c in r.calls] == [2000, 3000]
    assert r.context_window_pct == pytest.approx(7.74) and r.final_context_pct == pytest.approx(7.86)
    assert r.output_tokens_per_sec == 80.0


def test_from_codex_builds_one_call_per_token_count(tmp_path: Path) -> None:
    """Outputs recorded before a count belong to the next call's context; calls before it are that call's."""

    def count(last: dict[str, int], total: dict[str, int]) -> dict[str, object]:
        info = {"last_token_usage": last, "total_token_usage": total}
        return {"type": "event_msg", "timestamp": "t", "payload": {"type": "token_count", "info": info}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            {"type": "response_item", "payload": {"type": "reasoning"}},
            {
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": "pwd\nls"},
            },
            {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "/w"}},
            count(
                {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 10, "reasoning_output_tokens": 9},
                {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 10, "reasoning_output_tokens": 9},
            ),
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "CommandExecution"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "FileChange"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "AgentMessage"}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {}}},  # no totals: ignored
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
            },
            count(
                {"input_tokens": 4000, "cached_input_tokens": 3200, "output_tokens": 50, "reasoning_output_tokens": 0},
                {"input_tokens": 5000, "cached_input_tokens": 4000, "output_tokens": 60, "reasoning_output_tokens": 9},
            ),
            {"type": "event_msg", "payload": {"type": "task_complete", "duration_ms": 321, "last_agent_message": "ok"}},
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.harness, r.model, r.session_id, r.duration_ms, r.final_text) == (
        "codex",
        "gpt-5.6-sol",
        "01a0",
        321,
        "ok",
    )
    assert (r.turns, r.reported_turns) == (2, 1)  # two model calls; one codex exec task
    assert r.usage == Usage(input_tokens=1000, output_tokens=60, cache_read_tokens=4000, reasoning_tokens=9)
    assert r.usage.accumulative_billed_tokens == 5060
    assert r.reported_usage == {
        "input_tokens": 5000,
        "cached_input_tokens": 4000,
        "output_tokens": 60,
        "reasoning_output_tokens": 9,
    }
    assert r.tool_calls == {"CommandExecution": 1, "FileChange": 1}
    assert r.harness_reported_cost_usd is None

    first, second = r.calls
    assert (first.context_tokens, first.usage.input_tokens, first.usage.cache_read_tokens) == (1000, 200, 800)
    assert [(t.name, t.summary, t.input) for t in first.tools] == [("exec", "pwd", "pwd\nls")]
    assert first.results_in == [] and first.stop_reason == "tool_use"
    assert [(x.tool, x.chars, x.content) for x in second.results_in] == [("exec", 2, "/w")]
    assert (second.text, second.stop_reason, second.tools) == ("ok", "end_turn", [])
    assert r.baseline_tokens == 1000
    # Every log line lands on exactly one turn; the trailing task_complete goes to the last.
    assert (first.records, second.records) == ([1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13])


def test_from_codex_diffs_cumulative_counts_when_last_usage_is_absent(tmp_path: Path) -> None:
    def count(total: int, cached: int, out: int) -> dict[str, object]:
        usage = {
            "input_tokens": total,
            "cached_input_tokens": cached,
            "output_tokens": out,
            "reasoning_output_tokens": 9,
        }
        return {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": usage}}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count(1000, 800, 10),
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "CommandExecution"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "FileChange"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "AgentMessage"}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {}}},  # no totals: ignored
            count(5000, 4000, 60),
            {"type": "event_msg", "payload": {"type": "task_complete", "duration_ms": 321, "last_agent_message": "ok"}},
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.harness, r.model, r.session_id, r.turns, r.reported_turns, r.duration_ms, r.final_text) == (
        "codex",
        "gpt-5.6-sol",
        "01a0",
        2,
        1,
        321,
        "ok",
    )
    assert r.usage == Usage(input_tokens=1000, output_tokens=60, cache_read_tokens=4000, reasoning_tokens=9)
    assert r.usage.accumulative_billed_tokens == 5060
    assert [c.context_tokens for c in r.calls] == [1000, 4000]
    assert r.tool_calls == {"CommandExecution": 1, "FileChange": 1}
    assert r.harness_reported_cost_usd is None


def test_from_codex_folds_forked_rollouts_and_attributes_the_spawning_turn(tmp_path: Path) -> None:
    """Forked rollouts become Subagent ledgers named by ``agent_nickname``; the parent turn
    is the first primary call measured at or after the fork's ``session_meta`` timestamp."""

    def count(at: str, last: dict[str, int]) -> dict[str, object]:
        info = {"last_token_usage": last, "total_token_usage": last}
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": info}}

    _jsonl(
        tmp_path / "log.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0-primary"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count("2026-08-28T00:00:05Z", {"input_tokens": 100, "output_tokens": 10}),
            count("2026-08-28T00:00:20Z", {"input_tokens": 200, "output_tokens": 20}),
        ],
    )
    sub = _jsonl(
        tmp_path / "subagents" / "rollout-sub.jsonl",
        [
            {
                "type": "session_meta",
                "timestamp": "2026-08-28T00:00:07Z",  # after t1's count: turn 2 spawned it
                "payload": {
                    "id": "01a0-sub",
                    "forked_from_id": "01a0-primary",
                    "source": {"subagent": {"thread_spawn": {"agent_nickname": "Curie", "depth": 1}}},
                    "agent_nickname": "Curie",
                    "agent_path": "/root/external_research",
                },
            },
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count("2026-08-28T00:00:12Z", {"input_tokens": 50, "cached_input_tokens": 40, "output_tokens": 5}),
        ],
    )
    # sub_rollouts=None discovers the captured layout: <session dir>/subagents/*.jsonl
    r = codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])
    (agent,) = r.subagents
    assert (agent.agent, agent.id, agent.description, agent.parent_turn, agent.turns) == (
        "Curie",
        "01a0-sub",
        "/root/external_research",
        2,
        1,
    )
    assert agent.log == str(sub)
    assert agent.usage == Usage(input_tokens=10, output_tokens=5, cache_read_tokens=40)
    assert r.usage == Usage(input_tokens=310, output_tokens=35, cache_read_tokens=40)
    assert r.turns == 2
    # The runner path passes the forks explicitly; the ledger is identical either way.
    explicit = codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0, sub_rollouts=[sub]).to_result(tmp_path, [])
    assert explicit.subagents[0].usage == agent.usage


def test_codex_usage_splits_openai_inclusive_input_into_disjoint_tiers() -> None:
    """OpenAI's input_tokens contains cached and cache-written tokens; Anthropic's does not.

    The plugin keeps Anthropic's disjoint shape, so the tiers price once each and their
    sum is the prompt the call processed again (docs/token-accounting.md).
    """
    u = codex_harness._call_usage(
        {"input_tokens": 2600, "cached_input_tokens": 2000, "cache_write_input_tokens": 400, "output_tokens": 30}
    )
    assert (u.input_tokens, u.cache_read_tokens, u.cache_write_tokens) == (200, 2000, 400)
    assert u.input_tokens + u.cache_read_tokens + u.cache_write_tokens == 2600
    # A malformed count can never go negative.
    assert codex_harness._call_usage({"input_tokens": 10, "cached_input_tokens": 20}).input_tokens == 0


def test_primary_rollout_skips_subagent_forks(tmp_path: Path) -> None:
    """A codex session that spawned subagents writes one rollout per thread; the primary is the log."""
    meta = {"timestamp": "t", "type": "session_meta", "payload": {"id": "p1", "source": "exec"}}
    sub = {
        "timestamp": "t",
        "type": "session_meta",
        "payload": {
            "id": "s1",
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": "p1", "depth": 1}}},
            "forked_from_id": "p1",
        },
    }
    primary = tmp_path / "rollout-1-p1.jsonl"
    primary.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (tmp_path / "rollout-2-s1.jsonl").write_text(json.dumps(sub) + "\n", encoding="utf-8")
    (tmp_path / "rollout-3-s2.jsonl").write_text(json.dumps(sub) + "\n", encoding="utf-8")
    assert codex_harness.primary_rollout(sorted(tmp_path.glob("rollout-*.jsonl"))) == primary
    # A lone primary still selects; two primaries or none is a hard failure, never a guess.
    assert codex_harness.primary_rollout([primary]) == primary
    second = tmp_path / "rollout-4-p2.jsonl"
    second.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    with pytest.raises(harnesses.RunError, match="found 2 of 4"):
        codex_harness.primary_rollout(sorted(tmp_path.glob("rollout-*.jsonl")))
    with pytest.raises(harnesses.RunError, match="found 0"):
        codex_harness.primary_rollout([tmp_path / "rollout-2-s1.jsonl"])
