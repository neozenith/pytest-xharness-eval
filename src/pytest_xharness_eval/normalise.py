"""Turn each CLI's session log into one RunResult.

The two dialects differ fundamentally:

* Claude writes ``~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`` with a
  per-assistant-message ``usage`` block, and reports ``total_cost_usd`` only on
  the ``-p --output-format json`` stdout envelope, never in the log.
* Codex writes ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl``
  with cumulative ``token_count`` events and no cost field anywhere.
"""

from __future__ import annotations

# Standard Library
import json
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.runresult import RunResult, Usage

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

# Codex item types that represent the agent acting rather than talking.
_CODEX_TOOL_ITEMS = {"CommandExecution", "FileChange", "Extension"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file, skipping blank and unparseable lines."""
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _claude_usage(records: list[dict[str, Any]]) -> tuple[Usage, dict[str, int], int]:
    usage = Usage()
    tools: dict[str, int] = {}
    seen_messages: set[str] = set()
    turns = 0
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") or {}
        # Claude writes one record per content block, all sharing the message id and
        # repeating its usage. Tool calls are counted from every record; usage and
        # turns once per message id (verified 2026-08-21: 16 records, 6 ids, 7 tools).
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name") or "unknown"
                tools[name] = tools.get(name, 0) + 1
        mid = msg.get("id")
        if mid and mid in seen_messages:
            continue
        if mid:
            seen_messages.add(mid)
        turns += 1
        u = msg.get("usage") or {}
        usage.input_tokens += int(u.get("input_tokens") or 0)
        usage.output_tokens += int(u.get("output_tokens") or 0)
        usage.cache_read_tokens += int(u.get("cache_read_input_tokens") or 0)
        usage.cache_write_tokens += int(u.get("cache_creation_input_tokens") or 0)
        details = u.get("output_tokens_details") or {}
        usage.reasoning_tokens += int(details.get("thinking_tokens") or 0)
    return usage, tools, turns


def from_claude(log: Path, envelope: dict[str, Any], workspace: Path, files_written: list[str]) -> RunResult:
    """Normalise a Claude session log plus its stdout result envelope."""
    records = read_jsonl(log)
    usage, tools, turns = _claude_usage(records)

    model = ""
    for rec in records:
        if rec.get("type") == "assistant":
            model = ((rec.get("message") or {}).get("model")) or model
    # The envelope carries the authoritative aggregates for the whole run.
    env_usage = envelope.get("usage") or {}
    if env_usage:
        usage = Usage(
            input_tokens=int(env_usage.get("input_tokens") or 0),
            output_tokens=int(env_usage.get("output_tokens") or 0),
            cache_read_tokens=int(env_usage.get("cache_read_input_tokens") or 0),
            cache_write_tokens=int(env_usage.get("cache_creation_input_tokens") or 0),
            reasoning_tokens=usage.reasoning_tokens,
        )

    return RunResult(
        harness="claude",
        model=model or str(envelope.get("model") or ""),
        session_id=str(envelope.get("session_id") or ""),
        session_log=str(log),
        workspace=str(workspace),
        exit_code=1 if envelope.get("is_error") else 0,
        duration_ms=int(envelope.get("duration_ms") or 0),
        turns=int(envelope.get("num_turns") or turns),
        final_text=str(envelope.get("result") or ""),
        usage=usage,
        tool_calls=tools,
        files_written=files_written,
        reported_cost_usd=envelope.get("total_cost_usd"),
    )


def _codex_usage(total: dict[str, Any]) -> Usage:
    # Cumulative: the caller passes the LAST token_count event, never a sum.
    cached = int(total.get("cached_input_tokens") or 0)
    raw_input = int(total.get("input_tokens") or 0)
    return Usage(
        # Codex input_tokens is INCLUSIVE of cached; split them so each tier prices once.
        input_tokens=max(raw_input - cached, 0),
        output_tokens=int(total.get("output_tokens") or 0),
        cache_read_tokens=cached,
        cache_write_tokens=int(total.get("cache_write_input_tokens") or 0),
        reasoning_tokens=int(total.get("reasoning_output_tokens") or 0),
    )


def from_codex(log: Path, exit_code: int, workspace: Path, files_written: list[str]) -> RunResult:
    """Normalise a Codex rollout file."""
    records = read_jsonl(log)

    session_id = ""
    model = ""
    final_text = ""
    duration_ms = 0
    turns = 0
    usage = Usage()
    tools: dict[str, int] = {}

    for rec in records:
        rtype = rec.get("type")
        payload = rec.get("payload") or {}
        if rtype == "session_meta":
            session_id = str(payload.get("id") or session_id)
        elif rtype == "turn_context":
            model = str(payload.get("model") or model)
        elif rtype == "event_msg":
            ptype = payload.get("type")
            if ptype == "token_count":
                total = (payload.get("info") or {}).get("total_token_usage") or {}
                if total:
                    usage = _codex_usage(total)
            elif ptype == "task_complete":
                turns += 1
                duration_ms += int(payload.get("duration_ms") or 0)
                final_text = str(payload.get("last_agent_message") or final_text)
            elif ptype == "item_completed":
                item = payload.get("item") or {}
                kind = item.get("item_type") or item.get("type") or ""
                if kind in _CODEX_TOOL_ITEMS:
                    tools[kind] = tools.get(kind, 0) + 1

    return RunResult(
        harness="codex",
        model=model,
        session_id=session_id,
        session_log=str(log),
        workspace=str(workspace),
        exit_code=exit_code,
        duration_ms=duration_ms,
        turns=turns,
        final_text=final_text,
        usage=usage,
        tool_calls=tools,
        files_written=files_written,
        reported_cost_usd=None,
    )
