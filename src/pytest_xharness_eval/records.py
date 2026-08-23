"""The catalogue of session-log record kinds, shared by the plugin and the report (ADR 0022).

Every line of a Claude session log or a Codex rollout is one record. ``classify``
maps a record to a *kind* (``harness/type[/subtype]``) and every kind belongs to a
*category* that says what sort of information it carries. The report renders one
component per kind and colours its pill by category; this module is the source of
truth for both, and ``census`` counts kinds per run so sweeps can be compared.

The catalogue was built from a census of every captured log (2026-08-22, claude
2.1.237-2.1.239, codex 0.148-0.149); an unseen shape classifies as ``<harness>/unknown``
rather than failing, and the census makes it visible.
"""

from __future__ import annotations

# Standard Library
import re
from collections import Counter
from typing import Any

# Category -> pill colour (white text on each passes WCAG AA, verified 2026-08-22).
CATEGORIES: dict[str, str] = {
    "prompt": "#1d4ed8",
    "assistant_text": "#065f46",
    "thinking": "#6d28d9",
    "tool_call": "#4338ca",
    "tool_result": "#0f766e",
    "tool_exec": "#9a3412",
    "file_change": "#be185d",
    "usage": "#b45309",
    "harness_context": "#3f6212",
    "harness_meta": "#475569",
    "session_meta": "#1e3a8a",
    "lifecycle": "#b91c1c",
    "unknown": "#374151",
}

# Kind -> category. Kinds not listed here fall back by prefix in ``category_of``.
KINDS: dict[str, str] = {
    "claude/user/prompt": "prompt",
    "claude/user/injected": "harness_context",
    "claude/user/tool_result": "tool_result",
    "claude/assistant/text": "assistant_text",
    "claude/assistant/thinking": "thinking",
    "claude/assistant/tool_use": "tool_call",
    # Claude Code writes these itself (model "<synthetic>", zero usage) to report an API error or
    # interruption; they look like assistant turns but no model call happened.
    "claude/assistant/synthetic": "harness_meta",
    "claude/attachment/total_tokens_reminder": "harness_meta",
    "claude/attachment/deferred_tools_delta": "harness_context",
    "claude/attachment/agent_listing_delta": "harness_context",
    "claude/attachment/skill_listing": "harness_context",
    "claude/attachment/auto_mode": "harness_meta",
    "claude/attachment/task_reminder": "harness_meta",
    "claude/ai-title": "harness_meta",
    "claude/atis-latch": "harness_meta",
    "claude/last-prompt": "harness_meta",
    "claude/queue-operation": "harness_meta",
    "claude/system": "harness_meta",
    "codex/session_meta": "session_meta",
    "codex/turn_context": "session_meta",
    "codex/world_state": "harness_meta",
    "codex/response_item/message/user": "prompt",
    # A user-role message whose text opens with an XML tag (<environment_context>, <recommended_plugins>)
    # was written by the harness, not typed by the person; it is context, not the prompt under test.
    "codex/response_item/message/user/injected": "harness_context",
    "codex/response_item/message/developer": "harness_context",
    "codex/response_item/message/system": "harness_context",
    "codex/response_item/message/assistant": "assistant_text",
    "codex/response_item/reasoning": "thinking",
    "codex/response_item/custom_tool_call": "tool_call",
    "codex/response_item/function_call": "tool_call",
    "codex/response_item/custom_tool_call_output": "tool_result",
    "codex/response_item/function_call_output": "tool_result",
    "codex/event_msg/task_started": "lifecycle",
    "codex/event_msg/task_complete": "lifecycle",
    "codex/event_msg/token_count": "usage",
    "codex/event_msg/item_completed/AgentMessage": "assistant_text",
    "codex/event_msg/item_completed/CommandExecution": "tool_exec",
    "codex/event_msg/item_completed/FileChange": "file_change",
    "codex/event_msg/item_completed/Reasoning": "thinking",
    "codex/event_msg/item_completed/UserMessage": "prompt",
    "codex/event_msg/item_completed/UserMessage/injected": "harness_context",
}

_LEADING_TAG = re.compile(r"\s*<([A-Za-z_][\w.-]*)[\s>/]")


def leading_tag(text: Any) -> str | None:
    """The name of the XML-style tag a message opens with, or None for plain prose."""
    if not isinstance(text, str):
        return None
    m = _LEADING_TAG.match(text)
    return m.group(1) if m else None


def message_text(content: Any) -> str:
    """Flatten a content value (string or list of text-bearing blocks) to its text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text") or "") for b in content if isinstance(b, dict))
    return ""


_PREFIX_CATEGORY = (
    ("claude/attachment/", "harness_meta"),
    ("codex/event_msg/item_completed/", "lifecycle"),
    ("codex/event_msg/", "lifecycle"),
    ("codex/response_item/message/", "harness_context"),
    ("codex/response_item/", "harness_meta"),
)


def is_synthetic(message: dict[str, Any]) -> bool:
    """True for an assistant message Claude Code wrote itself rather than received from the API."""
    return str(message.get("model") or "").startswith("<")


def _block_types(content: Any) -> set[str]:
    if not isinstance(content, list):
        return set()
    return {str(b.get("type")) for b in content if isinstance(b, dict)}


def _classify_claude(rec: dict[str, Any]) -> str:
    rtype = str(rec.get("type") or "unknown")
    if rtype == "user":
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, str) and "tool_result" in _block_types(content):
            return "claude/user/tool_result"
        return "claude/user/injected" if leading_tag(message_text(content)) else "claude/user/prompt"
    if rtype == "assistant":
        msg = rec.get("message") or {}
        if is_synthetic(msg):
            return "claude/assistant/synthetic"
        kinds = _block_types(msg.get("content"))
        if "tool_use" in kinds:
            return "claude/assistant/tool_use"
        if "thinking" in kinds and "text" not in kinds:
            return "claude/assistant/thinking"
        return "claude/assistant/text"
    if rtype == "attachment":
        return f"claude/attachment/{(rec.get('attachment') or {}).get('type') or 'unknown'}"
    return f"claude/{rtype}"


def _classify_codex(rec: dict[str, Any]) -> str:
    rtype = str(rec.get("type") or "unknown")
    payload = rec.get("payload") or {}
    if rtype == "response_item":
        sub = str(payload.get("type") or "unknown")
        if sub == "message":
            role = str(payload.get("role") or "unknown")
            injected = role == "user" and leading_tag(message_text(payload.get("content")))
            return f"codex/response_item/message/{role}{'/injected' if injected else ''}"
        return f"codex/response_item/{sub}"
    if rtype == "event_msg":
        sub = str(payload.get("type") or "unknown")
        if sub == "item_completed":
            item = payload.get("item") or {}
            kind = str(item.get("item_type") or item.get("type") or "unknown")
            injected = kind == "UserMessage" and leading_tag(message_text(item.get("content")))
            return f"codex/event_msg/item_completed/{kind}{'/injected' if injected else ''}"
        return f"codex/event_msg/{sub}"
    return f"codex/{rtype}"


def classify(harness: str, rec: dict[str, Any]) -> str:
    """The kind of one record: ``harness/type[/subtype]``; never raises."""
    if not isinstance(rec, dict):
        return f"{harness}/unknown"
    return _classify_claude(rec) if harness == "claude" else _classify_codex(rec)


def category_of(kind: str) -> str:
    """The category a kind belongs to; unseen kinds fall back by prefix, then to ``unknown``."""
    if kind in KINDS:
        return KINDS[kind]
    for prefix, category in _PREFIX_CATEGORY:
        if kind.startswith(prefix):
            return category
    return "unknown"


def census(harness: str, records: list[dict[str, Any]]) -> dict[str, int]:
    """How many records of each kind a log holds, sorted by kind."""
    counts = Counter(classify(harness, r) for r in records)
    return dict(sorted(counts.items()))
