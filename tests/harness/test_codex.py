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
from pytest_xharness_eval.harness.threads import SubagentMismatch
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


def _count(at: str, last: dict[str, int]) -> dict[str, object]:
    info = {"last_token_usage": last, "total_token_usage": last}
    return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": info}}


def _direct_spawn(call_id: str, task_name: str | None) -> list[dict[str, object]]:
    """A direct ``spawn_agent`` call and its output, which names the new thread's path."""
    output = json.dumps({"task_name": task_name}) if task_name else "spawn refused: depth limit"
    return [
        {"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": call_id}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id, "output": output}},
    ]


def _collab_spawn(item_id: str, sender: str, receiver: str) -> dict[str, object]:
    """The ``CollabAgentToolCall`` a code-mode ``exec`` completes when it spawns a thread."""
    item = {
        "type": "CollabAgentToolCall",
        "id": item_id,
        "tool": "spawn_agent",
        "status": "completed",
        "sender_thread_id": sender,
        "receiver_thread_ids": [receiver],
    }
    return {"type": "event_msg", "payload": {"type": "item_completed", "item": item}}


def _fork(
    at: str, thread: str, parent: str, path: str, nickname: str, *body: dict[str, object]
) -> list[dict[str, object]]:
    """A forked rollout: its own ``session_meta``, then its parent's replayed, as Codex writes one."""
    spawn = {"parent_thread_id": parent, "depth": 1, "agent_path": path, "agent_nickname": nickname}
    return [
        {
            "type": "session_meta",
            "timestamp": at,
            "payload": {"id": thread, "source": {"subagent": {"thread_spawn": spawn}}},
        },
        {"type": "session_meta", "timestamp": at, "payload": {"id": parent}},
        {"type": "turn_context", "payload": {"model": "gpt-5.6-luna"}},
        *body,
    ]


def _primary(tmp_path: Path, *turn2: dict[str, object]) -> Path:
    """A two-turn primary whose second turn logs ``turn2`` before its count."""
    return _jsonl(
        tmp_path / "log.jsonl",
        [
            {"type": "session_meta", "timestamp": "2026-08-28T00:00:00Z", "payload": {"id": "01a0-primary"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            _count("2026-08-28T00:00:05Z", {"input_tokens": 100, "output_tokens": 10}),
            *turn2,
            _count("2026-08-28T00:00:20Z", {"input_tokens": 200, "output_tokens": 20}),
        ],
    )


def test_from_codex_links_each_fork_to_the_turn_whose_record_spawned_it(tmp_path: Path) -> None:
    """A fork is linked by its spawn record, never by a timestamp, and carries its span (ADR 0072).

    Turn 2 spawns one thread directly (output names its path) and one through a code-mode
    ``exec`` (the item names its id); the second spawns its own subagent in turn.
    """
    _primary(tmp_path, *_direct_spawn("call_1", "/root/research"), _collab_spawn("exec-1", "01a0-primary", "01a0-b"))
    a = _jsonl(
        tmp_path / "subagents" / "rollout-a.jsonl",
        _fork(
            "2026-08-28T00:00:07Z",
            "01a0-a",
            "01a0-primary",
            "/root/research",
            "Curie",
            _count("2026-08-28T00:00:12Z", {"input_tokens": 50, "cached_input_tokens": 40, "output_tokens": 5}),
        ),
    )
    _jsonl(
        tmp_path / "subagents" / "rollout-b.jsonl",
        _fork(
            "2026-08-28T00:00:08Z",
            "01a0-b",
            "01a0-primary",
            "/root/checks",
            "Kuhn",
            *_direct_spawn("call_2", "/root/checks/inner"),
            _count("2026-08-28T00:00:18Z", {"input_tokens": 30, "output_tokens": 50}),
        ),
    )
    _jsonl(
        tmp_path / "subagents" / "rollout-c.jsonl",
        _fork(
            "2026-08-28T00:00:09Z",
            "01a0-c",
            "01a0-b",
            "/root/checks/inner",
            "Pasteur",
            _count("2026-08-28T00:00:11Z", {}),
        ),
    )
    # sub_rollouts=None discovers the captured layout: <session dir>/subagents/*.jsonl
    r = codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])
    links = {s.id: (s.agent, s.spawned_by, s.parent, s.depth, s.parent_turn) for s in r.subagents}
    assert links == {
        "01a0-a": ("Curie", "call_1", "", 1, 2),
        "01a0-b": ("Kuhn", "exec-1", "", 1, 2),
        "01a0-c": ("Pasteur", "call_2", "01a0-b", 2, 2),
    }
    first = r.subagents[0]
    assert (first.id, first.log, first.description) == ("01a0-a", str(a), "/root/research")
    assert (first.started_at, first.ended_at, first.duration_ms) == (
        "2026-08-28T00:00:07Z",
        "2026-08-28T00:00:12Z",
        5000,
    )
    assert first.usage == Usage(input_tokens=10, output_tokens=5, cache_read_tokens=40)
    assert r.usage == Usage(input_tokens=340, output_tokens=85, cache_read_tokens=40)
    assert r.turns == 2
    # The runner path passes the forks explicitly; the ledger is identical either way.
    explicit = codex_harness.CodexSessionLog(
        tmp_path / "log.jsonl", 0, sub_rollouts=sorted((tmp_path / "subagents").glob("*.jsonl"))
    ).to_result(tmp_path, [])
    assert [s.usage for s in explicit.subagents] == [s.usage for s in r.subagents]


def test_a_codex_fork_no_spawn_names_stops_the_fold(tmp_path: Path) -> None:
    _primary(tmp_path)
    _jsonl(
        tmp_path / "subagents" / "rollout-a.jsonl",
        _fork("2026-08-28T00:00:07Z", "01a0-a", "01a0-primary", "/root/a", "Curie", _count("2026-08-28T00:00:12Z", {})),
    )
    with pytest.raises(SubagentMismatch, match="01a0-a is named by 0 spawn records"):
        codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])


def test_a_codex_spawn_with_no_fork_stops_the_fold_unless_its_output_spawned_nothing(tmp_path: Path) -> None:
    _primary(tmp_path, *_direct_spawn("call_1", "/root/a"))
    with pytest.raises(SubagentMismatch, match="no captured subagent transcript: call_1"):
        codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])
    refused = tmp_path / "refused"
    _primary(refused, *_direct_spawn("call_1", None))
    assert codex_harness.CodexSessionLog(refused / "log.jsonl", 0).to_result(refused, []).subagents == []


def test_a_codex_fork_naming_a_parent_that_did_not_spawn_it_stops_the_fold(tmp_path: Path) -> None:
    _primary(tmp_path, *_direct_spawn("call_1", "/root/a"))
    _jsonl(
        tmp_path / "subagents" / "rollout-a.jsonl",
        _fork(
            "2026-08-28T00:00:07Z", "01a0-a", "01a0-elsewhere", "/root/a", "Curie", _count("2026-08-28T00:00:12Z", {})
        ),
    )
    with pytest.raises(SubagentMismatch, match="names 01a0-elsewhere as its parent"):
        codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])


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


def test_an_exec_script_yields_each_command_it_runs_with_its_workdir() -> None:
    script = (
        'const a = await tools.exec_command({"cmd": "ls", "workdir": "/w"});\n'
        'const b = await tools.exec_command({"cmd": ["bash", "-lc", "pwd"]});'
    )
    assert codex_harness.CodexHarness.shell_commands(script) == [("ls", "/w"), ("bash -lc pwd", None)]


def test_an_exec_input_that_is_not_a_script_is_read_as_before() -> None:
    assert codex_harness.CodexHarness.shell_commands({"command": "ls", "cwd": "/w"}) == [("ls", "/w")]
    assert codex_harness.CodexHarness.shell_commands("tools.exec_command(notjson)") == [
        ("tools.exec_command(notjson)", None)
    ]


def test_an_exec_script_with_bare_object_keys_is_read_too() -> None:
    """``{cmd:"..."}`` is JavaScript, not JSON, and the model writes it that way as often as not."""
    script = 'await tools.exec_command({cmd:"S=/s\\nbun run \\"$S/x.ts\\"", workdir: "/w", "yield_time_ms":10000});'
    assert codex_harness.CodexHarness.shell_commands(script) == [('S=/s\nbun run "$S/x.ts"', "/w")]
    assert codex_harness.CodexHarness.shell_commands("tools.exec_command({})") == [("", None)]
