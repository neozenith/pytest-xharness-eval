"""Realistic two-harness captures, built once and shared by the characterization tests.

These fixtures are deliberately rich: each exercises the whole provider dialect that
``normalise`` folds -- a prompt, thinking, tool calls whose results arrive out of
order, a subagent transcript, the harness's own meta records, and the usage figures
the ledger sums. They exist so a structural move can be proved behaviour-preserving
against a pinned result, not merely against green unit tests (see tests/golden/).
"""

from __future__ import annotations

# Standard Library
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

# Prices are pinned here rather than taken from the bundled prices.toml: a real price
# update is not a behaviour change, and the golden must not move when one lands.
PRICE_ROWS = [
    "claude-opus-5: input=15.00 output=75.00 cache_read=1.50 cache_write=18.75 cache_write_1h=30.00",
    "gpt-5.6-sol: input=1.25 output=10.00 cache_read=0.125",
]

SKILL = "demo"


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def skill_tree(root: Path) -> Path:
    """A skill the runs below partly load and partly ignore, so coverage has something to say."""
    skill_dir = root / SKILL
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "resources").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# demo skill\nRun scripts/check.py.\n", encoding="utf-8")
    (skill_dir / "resources" / "evidence.md").write_text("background reading\n", encoding="utf-8")
    (skill_dir / "scripts" / "check.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "scripts" / "unused.py").write_text("print('never run')\n", encoding="utf-8")
    return skill_dir


# -- Claude ----------------------------------------------------------------------------

CLAUDE_MODEL = "claude-opus-5"


def claude_capture(session_dir: Path) -> tuple[Path, dict[str, Any]]:
    """A two-turn Claude session with a subagent, written in the native captured layout."""
    turn1_a = {
        "id": "m1",
        "model": CLAUDE_MODEL,
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 40,
            "cache_read_input_tokens": 1800,
            "cache_creation_input_tokens": 300,
            "cache_creation": {"ephemeral_1h_input_tokens": 200, "ephemeral_5m_input_tokens": 100},
            "output_tokens_details": {"thinking_tokens": 15},
        },
        "content": [
            {"type": "thinking", "thinking": "read the skill first"},
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "demo/SKILL.md"}},
        ],
    }
    # The second block of the same message id: one call, two records (ADR 0023).
    turn1_b = {
        "id": "m1",
        "model": CLAUDE_MODEL,
        "usage": {},
        "content": [
            {
                "type": "tool_use",
                "id": "t2",
                "name": "Bash",
                "input": {"command": "cd demo && uv run scripts/check.py"},
            },
            {"type": "tool_use", "id": "t3", "name": "Agent", "input": {"description": "sub work"}},
        ],
    }
    turn2 = {
        "id": "m2",
        "model": CLAUDE_MODEL,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 9, "output_tokens": 22, "cache_read_input_tokens": 2100},
        "content": [{"type": "text", "text": "done"}],
    }
    log = write_jsonl(
        session_dir / "log.jsonl",
        [
            {"type": "user", "timestamp": "2026-08-22T00:00:00Z", "message": {"content": "grade the skill"}},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:02Z", "message": turn1_a},
            {
                "type": "user",
                "timestamp": "2026-08-22T00:00:03Z",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "# demo skill"}]},
            },
            {"type": "assistant", "timestamp": "2026-08-22T00:00:04Z", "message": turn1_b},
            {"type": "attachment", "timestamp": "2026-08-22T00:00:05Z", "attachment": {"type": "skill_listing"}},
            {
                "type": "user",
                "timestamp": "2026-08-22T00:00:06Z",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "ok"}]},
            },
            {"type": "system", "timestamp": "2026-08-22T00:00:07Z", "content": "harness note"},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:09Z", "message": turn2},
        ],
    )
    _claude_subagent(session_dir)
    envelope = {
        "session_id": "claude-sid-1",
        "model": CLAUDE_MODEL,
        "is_error": False,
        "duration_ms": 9000,
        "duration_api_ms": 7200,
        "ttft_ms": 950,
        "num_turns": 4,
        "result": "done",
        "total_cost_usd": 0.51,
        "usage": {
            "input_tokens": 21,
            "output_tokens": 62,
            "cache_read_input_tokens": 3900,
            "cache_creation_input_tokens": 300,
        },
        "modelUsage": {CLAUDE_MODEL: {"contextWindow": 1000000, "costUSD": 0.51}},
    }
    return log, envelope


def _claude_subagent(session_dir: Path) -> None:
    """The captured layout: ``<session dir>/subagents/agent-<id>.jsonl`` plus its sidecar."""
    subs = session_dir / "subagents"
    write_jsonl(
        subs / "agent-sub1.jsonl",
        [
            {"type": "user", "agentId": "sub1", "timestamp": "2026-08-22T00:00:05Z", "message": {"content": "go"}},
            {
                "type": "assistant",
                "agentId": "sub1",
                "timestamp": "2026-08-22T00:00:06Z",
                "message": {
                    "id": "s1",
                    "model": CLAUDE_MODEL,
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 4, "output_tokens": 11, "cache_read_input_tokens": 500},
                    "content": [{"type": "text", "text": "sub done"}],
                },
            },
        ],
    )
    (subs / "agent-sub1.meta.json").write_text(
        json.dumps({"agentType": "Explore", "description": "sub work", "toolUseId": "t3"}),
        encoding="utf-8",
    )


# -- Codex -----------------------------------------------------------------------------

CODEX_MODEL = "gpt-5.6-sol"


def codex_capture(session_dir: Path) -> Path:
    """A two-turn Codex rollout with a forked subagent, in the native captured layout."""
    log = write_jsonl(
        session_dir / "log.jsonl",
        [
            {
                "type": "session_meta",
                "timestamp": "2026-08-22T00:00:00Z",
                "payload": {"id": "codex-sid-1", "source": "exec"},
            },
            {"type": "turn_context", "timestamp": "2026-08-22T00:00:00Z", "payload": {"model": CODEX_MODEL}},
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:00Z",
                "payload": {"type": "task_started", "model_context_window": 400000},
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:01Z",
                "payload": {"type": "message", "role": "user", "content": [{"type": "text", "text": "grade it"}]},
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:02Z",
                "payload": {"type": "reasoning", "summary": [{"type": "text", "text": "read the skill"}]},
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:03Z",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "call_id": "c1",
                    "arguments": {"command": ["bash", "-lc", "cat demo/SKILL.md"], "workdir": "/w"},
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:04Z",
                "payload": {"type": "function_call_output", "call_id": "c1", "output": "# demo skill"},
            },
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:04Z",
                "payload": {"type": "item_completed", "item": {"item_type": "CommandExecution"}},
            },
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:05Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "model_context_window": 400000,
                        "last_token_usage": {
                            "input_tokens": 2200,
                            "cached_input_tokens": 1800,
                            "cache_write_input_tokens": 100,
                            "output_tokens": 45,
                            "reasoning_output_tokens": 20,
                        },
                        "total_token_usage": {"input_tokens": 2200, "output_tokens": 45},
                    },
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:06Z",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "call_id": "c2",
                    "arguments": {"command": ["bash", "-lc", "uv run demo/scripts/check.py"], "workdir": "/w"},
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:07Z",
                "payload": {"type": "function_call_output", "call_id": "c2", "output": "ok"},
            },
            {
                "type": "response_item",
                "timestamp": "2026-08-22T00:00:08Z",
                "payload": {"type": "message", "role": "assistant", "content": [{"type": "text", "text": "done"}]},
            },
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:09Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 2600,
                            "cached_input_tokens": 2400,
                            "output_tokens": 30,
                            "reasoning_output_tokens": 5,
                        },
                        "total_token_usage": {"input_tokens": 4800, "output_tokens": 75},
                    },
                },
            },
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:10Z",
                "payload": {
                    "type": "task_complete",
                    "duration_ms": 10000,
                    "time_to_first_token_ms": 1100,
                    "last_agent_message": "done",
                },
            },
        ],
    )
    _codex_subagent(session_dir)
    return log


def _codex_subagent(session_dir: Path) -> None:
    """A forked rollout under ``<session dir>/subagents/``, discovered when sub_rollouts is None."""
    write_jsonl(
        session_dir / "subagents" / "rollout-sub1.jsonl",
        [
            {
                "type": "session_meta",
                "timestamp": "2026-08-22T00:00:03Z",
                "payload": {
                    "id": "codex-sub-1",
                    "forked_from_id": "codex-sid-1",
                    "agent_nickname": "scout",
                    "agent_path": "agents/scout.md",
                    "source": {"subagent": {"thread_spawn": {}}},
                },
            },
            {"type": "turn_context", "timestamp": "2026-08-22T00:00:03Z", "payload": {"model": CODEX_MODEL}},
            {
                "type": "event_msg",
                "timestamp": "2026-08-22T00:00:04Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 600, "cached_input_tokens": 500, "output_tokens": 12},
                        "total_token_usage": {"input_tokens": 600, "output_tokens": 12},
                    },
                },
            },
        ],
    )
