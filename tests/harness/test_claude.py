"""``harness.claude``: folding a Claude session log into a run (ADR 0019, ADR 0033)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Usage,
)
from pytest_xharness_eval.harness import claude as claude_harness
from pytest_xharness_eval.harness import records
from tests.support import _jsonl


def test_claude_log_path_slugifies_every_non_alphanumeric_character(tmp_path: Path) -> None:
    workspace = tmp_path / "tmp" / "evals" / "eval_demo-claude-claude-opus-5"
    workspace.mkdir(parents=True)
    path = claude_harness.claude_log_path(Path("/cfg"), workspace, "abc-123")
    slug = path.parent.name
    assert path.parent.parent == Path("/cfg/projects")
    assert path.name == "abc-123.jsonl"
    assert "_" not in slug and "/" not in slug and "." not in slug
    assert slug.endswith("eval-demo-claude-claude-opus-5")


def test_from_claude_builds_one_call_per_message_id_and_keeps_the_envelope_for_reconciliation(
    tmp_path: Path,
) -> None:
    usage1 = {
        "input_tokens": 5,
        "output_tokens": 7,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 200,
        "cache_creation": {"ephemeral_1h_input_tokens": 200, "ephemeral_5m_input_tokens": 0},
        "output_tokens_details": {"thinking_tokens": 3},
    }
    msg = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": usage1,
        "stop_reason": "tool_use",
        "content": [
            {"type": "thinking", "thinking": "plan the edit"},
            {"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": "/w/ARCHITECTURE.md"}},
            {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/w/b.md"}},
            {"type": "text", "text": "editing"},
        ],
    }
    # Claude writes one record per content block; both records share id m1 and its usage.
    second_block = {
        **msg,
        "content": [{"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ls\n-la"}}],
    }
    tool_results = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "x" * 500},
                {"type": "tool_result", "tool_use_id": "t3", "content": [{"type": "text", "text": "ok"}]},
            ]
        },
    }
    usage2 = {
        "input_tokens": 2,
        "output_tokens": 40,
        "cache_read_input_tokens": 1205,
        "cache_creation_input_tokens": 90,
    }
    final = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": usage2,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "done"}],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"content": "the prompt"}},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:01Z", "message": msg},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:01Z", "message": second_block},
            tool_results,
            {"type": "assistant", "timestamp": "2026-08-22T00:00:09Z", "message": final},
        ],
    )
    envelope = {
        "session_id": "sid",
        "is_error": False,
        "duration_ms": 1234,
        "num_turns": 4,
        "result": "done",
        "total_cost_usd": 0.42,
        "usage": {
            "input_tokens": 7,
            "output_tokens": 47,
            "cache_read_input_tokens": 2205,
            "cache_creation_input_tokens": 290,
        },
    }
    r = claude_harness.ClaudeSessionLog(log, envelope).to_result(tmp_path, ["ARCHITECTURE.md"])
    assert (r.harness, r.model, r.session_id, r.exit_code, r.final_text) == (
        "claude",
        "claude-opus-5",
        "sid",
        0,
        "done",
    )
    # A turn is one model call (ADR 0019); the envelope's figure is kept beside it.
    assert (r.turns, r.reported_turns) == (2, 4)
    assert r.usage == Usage(7, 47, 2205, 290, reasoning_tokens=3, cache_write_1h_tokens=200)  # usage summed once per id
    assert r.reported_usage == envelope["usage"]
    assert r.reported_model_usage == {} and "result" not in r.envelope and r.envelope["num_turns"] == 4
    assert r.tool_calls == {"Edit": 2, "Bash": 1}  # tools counted across every record
    assert r.harness_reported_cost_usd == 0.42 and r.estimated_cost_usd is None
    assert r.files_written == ["ARCHITECTURE.md"]

    first, second = r.calls
    assert (first.n, first.at, first.stop_reason, first.text) == (1, "2026-08-22T00:00:01Z", "tool_use", "editing")
    assert first.thinking == "plan the edit"
    assert (first.context_tokens, first.results_in) == (1205, [])
    assert [(t.name, t.summary) for t in first.tools] == [
        ("Edit", "/w/ARCHITECTURE.md"),
        ("Edit", "/w/b.md"),
        ("Bash", "ls"),
    ]
    assert first.tools[2].input == {"command": "ls\n-la"}  # the whole argument payload, not the summary
    # Results that arrived between the two calls enter the second call's context, paired to their tool,
    # and are stored whole (ADR 0021: the ledger cuts nothing).
    assert [(x.tool, x.chars, len(x.content)) for x in second.results_in] == [("Edit", 500, 500), ("Bash", 2, 2)]
    assert (second.context_tokens, second.stop_reason, second.tools) == (1297, "end_turn", [])
    assert r.baseline_tokens == 1205
    # Each turn knows the log lines it was built from (ADR 0023): the prompt, both blocks of m1 and the
    # results of m1's own tools belong to turn 1; m2's block is turn 2. Ranges are contiguous.
    assert (first.records, second.records) == ([1, 2, 3, 4], [5])


def test_from_claude_turn_boundaries_follow_tool_ownership_not_log_order(tmp_path: Path) -> None:
    """Results of a turn's early tools land between its later blocks; they still belong to that turn (ADR 0023)."""

    def use(mid: str, tid: str) -> dict[str, object]:
        return {
            "type": "assistant",
            "message": {
                "id": mid,
                "usage": {},
                "content": [{"type": "tool_use", "id": tid, "name": "Read", "input": {}}],
            },
        }

    def res(tid: str) -> dict[str, object]:
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}

    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"content": "prompt"}},  # 1 -> turn 1
            use("m1", "a"),  # 2
            use("m1", "b"),  # 3
            res("a"),  # 4: result of m1's first tool, written before m1's third block
            use("m1", "c"),  # 5
            {
                "type": "attachment",
                "attachment": {"type": "total_tokens_reminder"},
            },  # 6: harness record, turn in progress
            res("b"),  # 7
            res("c"),  # 8
            use("m2", "d"),  # 9 -> turn 2
            res("d"),  # 10
            {"type": "ai-title"},  # 11 -> still turn 2
        ],
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid"}).to_result(tmp_path, [])
    assert r.turns == 2
    assert (r.calls[0].records, r.calls[1].records) == ([1, 2, 3, 4, 5, 6, 7, 8], [9, 10, 11])
    # results_in keeps its own meaning: what entered turn 2's context is turn 1's results.
    assert [x.tool for x in r.calls[1].results_in] == ["Read", "Read", "Read"]


def test_from_claude_context_window_latency_and_ttft(tmp_path: Path) -> None:
    """Window from modelUsage, TTFT and API time from the envelope, per-turn latency from timestamps (ADR 0024)."""
    m1 = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 2, "cache_read_input_tokens": 20_000, "output_tokens": 300},
        "content": [],
    }
    m2 = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": {
            "input_tokens": 2,
            "cache_read_input_tokens": 24_000,
            "cache_write_input_tokens": 0,
            "output_tokens": 100,
        },
        "content": [],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "timestamp": "2026-08-23T00:00:00.000Z", "message": {"content": "go"}},
            {"type": "assistant", "timestamp": "2026-08-23T00:00:03.500Z", "message": m1},
            {
                "type": "user",
                "timestamp": "2026-08-23T00:00:04.000Z",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]},
            },
            {"type": "assistant", "timestamp": "2026-08-23T00:00:06.000Z", "message": m2},
        ],
    )
    envelope = {
        "session_id": "sid",
        "ttft_ms": 1991,
        "duration_api_ms": 8000,
        "duration_ms": 9000,
        "modelUsage": {
            "claude-haiku-4-5-20251001": {"contextWindow": 200_000},
            "claude-opus-5": {"contextWindow": 1_000_000},
        },
    }
    r = claude_harness.ClaudeSessionLog(log, envelope).to_result(tmp_path, [])
    assert (r.context_window, r.ttft_ms, r.api_duration_ms) == (1_000_000, 1991, 8000)
    assert [c.latency_ms for c in r.calls] == [3500, 2000]
    assert [c.output_tokens_per_sec for c in r.calls] == [pytest.approx(85.71, abs=0.01), 50.0]
    assert (r.peak_context_tokens, r.final_context_tokens) == (24_002, 24_102)
    assert (r.context_window_pct, r.final_context_pct) == (2.4, 2.41)
    assert r.output_tokens_per_sec == 50.0  # 400 output tokens over 8 s of API time
    data = r.to_dict()
    assert [c["context_pct"] for c in data["calls"]] == [2.0, 2.4]
    assert data["context_window_pct"] == 2.4 and data["final_context_pct"] == 2.41


def test_from_claude_keeps_synthetic_messages_as_evidence_not_turns(tmp_path: Path) -> None:
    """Claude Code writes ``model: "<synthetic>"`` notices (API errors) into the log; no model call happened."""
    real = {"id": "m1", "model": "claude-opus-5", "usage": {"input_tokens": 3, "output_tokens": 4}, "content": []}
    synthetic = {
        "id": "s1",
        "model": "<synthetic>",
        "stop_reason": "stop_sequence",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "content": [{"type": "text", "text": "API Error: The response stopped arriving."}],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [{"type": "assistant", "message": real}, {"type": "assistant", "message": synthetic}],
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid"}).to_result(tmp_path, [])
    assert (r.model, r.turns) == ("claude-opus-5", 1)  # the synthetic record names no model and is no turn
    assert r.calls[0].records == [1, 2]  # but its line stays attributed as evidence
    assert r.record_kinds == {"claude/assistant/synthetic": 1, "claude/assistant/text": 1}
    assert records.category_of("claude/assistant/synthetic") == "harness_meta"


def test_from_claude_without_envelope_usage_still_sums_the_ledger(tmp_path: Path) -> None:
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "assistant", "message": {"usage": {"input_tokens": 5, "output_tokens": 7}}},
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "output_tokens": 1}}},
        ],
    )
    r = claude_harness.ClaudeSessionLog(log, {"is_error": True, "model": "claude-sonnet-5"}).to_result(tmp_path, [])
    assert (r.exit_code, r.turns, r.reported_turns, r.model) == (1, 2, None, "claude-sonnet-5")
    assert r.usage == Usage(6, 8)
    assert r.reported_usage == {}


def test_from_claude_folds_subagent_transcripts_and_bills_them(tmp_path: Path) -> None:
    """A captured session dir's ``subagents/`` transcripts become Subagent ledgers: the
    spawning turn is matched by the sidecar's ``toolUseId``, and their usage folds into
    the run's billed total (a spawned thread's tokens are real spend)."""
    spawn = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100},
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_agent", "name": "Agent", "input": {"prompt": "research"}}],
    }
    final = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 2, "output_tokens": 8, "cache_read_input_tokens": 120},
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "done"}],
    }
    log = _jsonl(
        tmp_path / "log.jsonl",
        [
            {"type": "user", "message": {"content": "go"}},
            {"type": "assistant", "timestamp": "2026-08-28T00:00:01Z", "message": spawn},
            {"type": "assistant", "timestamp": "2026-08-28T00:00:09Z", "message": final},
        ],
    )
    sub_dir = tmp_path / "subagents"
    _jsonl(
        sub_dir / "agent-abc123.jsonl",
        [
            {"type": "user", "isSidechain": True, "agentId": "abc123", "message": {"content": "research"}},
            {
                "type": "assistant",
                "isSidechain": True,
                "agentId": "abc123",
                "timestamp": "2026-08-28T00:00:03Z",
                "message": {
                    "id": "s1",
                    "model": "claude-opus-5",
                    "usage": {"input_tokens": 30, "output_tokens": 20, "cache_read_input_tokens": 400},
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "found it"}],
                },
            },
        ],
    )
    (sub_dir / "agent-abc123.meta.json").write_text(
        json.dumps({"agentType": "general-purpose", "description": "External research", "toolUseId": "tu_agent"}),
        encoding="utf-8",
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid", "result": "done"}).to_result(tmp_path, [])
    assert r.calls[0].tools[0].id == "tu_agent"
    (sub,) = r.subagents
    assert (sub.agent, sub.id, sub.description, sub.parent_turn, sub.turns) == (
        "general-purpose",
        "abc123",
        "External research",
        1,
        1,
    )
    assert sub.log == str(sub_dir / "agent-abc123.jsonl")
    assert sub.usage == Usage(input_tokens=30, output_tokens=20, cache_read_tokens=400)
    # The run's usage is primary (12, 13, 220) plus the subagent: the whole bill.
    assert r.usage == Usage(input_tokens=42, output_tokens=33, cache_read_tokens=620)
    assert r.turns == 2  # turns stay the primary thread's own


def test_the_workspace_is_added_so_its_own_claude_md_is_read_and_nothing_above_it(tmp_path: Path) -> None:
    """``--setting-sources ""`` drops every CLAUDE.md; this re-admits the workspace's alone (ADR 0055)."""
    assert claude_harness.workspace_memory_argv(tmp_path) == ["--add-dir", str(tmp_path)]
    assert claude_harness._WORKSPACE_MEMORY_ENV == {"CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD": "1"}
