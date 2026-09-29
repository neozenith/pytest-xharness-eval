"""``harness.records``: the record-kind catalogue and its categories (ADR 0022)."""


# Standard Library

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.harness import records


@pytest.mark.parametrize(
    ("harness", "rec", "kind", "category"),
    [
        ("claude", {"type": "user", "message": {"content": "hi"}}, "claude/user/prompt", "prompt"),
        (
            "claude",
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            "claude/user/tool_result",
            "tool_result",
        ),
        (
            "claude",
            {"type": "assistant", "message": {"content": [{"type": "thinking"}, {"type": "tool_use"}]}},
            "claude/assistant/tool_use",
            "tool_call",
        ),
        (
            "claude",
            {"type": "assistant", "message": {"content": [{"type": "thinking"}]}},
            "claude/assistant/thinking",
            "thinking",
        ),
        (
            "claude",
            {"type": "assistant", "message": {"content": [{"type": "thinking"}, {"type": "text"}]}},
            "claude/assistant/text",
            "assistant_text",
        ),
        (
            "claude",
            {"type": "attachment", "attachment": {"type": "skill_listing"}},
            "claude/attachment/skill_listing",
            "harness_context",
        ),
        (
            "claude",
            {"type": "attachment", "attachment": {"type": "brand_new"}},
            "claude/attachment/brand_new",
            "harness_meta",
        ),
        ("claude", {"type": "ai-title"}, "claude/ai-title", "harness_meta"),
        ("claude", {"type": "never-seen"}, "claude/never-seen", "unknown"),
        ("codex", {"type": "session_meta", "payload": {}}, "codex/session_meta", "session_meta"),
        (
            "codex",
            {"type": "response_item", "payload": {"type": "message", "role": "developer"}},
            "codex/response_item/message/developer",
            "harness_context",
        ),
        (
            "codex",
            {"type": "response_item", "payload": {"type": "custom_tool_call"}},
            "codex/response_item/custom_tool_call",
            "tool_call",
        ),
        ("codex", {"type": "event_msg", "payload": {"type": "token_count"}}, "codex/event_msg/token_count", "usage"),
        (
            "codex",
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "FileChange"}}},
            "codex/event_msg/item_completed/FileChange",
            "file_change",
        ),
        (
            "codex",
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "Shiny"}}},
            "codex/event_msg/item_completed/Shiny",
            "lifecycle",
        ),
        ("codex", "not a record", "codex/unknown", "unknown"),
        # Messages that open with an XML tag were written by the harness, not the person (ADR 0024).
        (
            "codex",
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "<environment_context>\n<cwd>/w</cwd>\n</environment_context>"}
                    ],
                },
            },
            "codex/response_item/message/user/injected",
            "harness_context",
        ),
        (
            "codex",
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Use the skill to <b>fix</b> it"}],
                },
            },
            "codex/response_item/message/user",
            "prompt",
        ),
        (
            "codex",
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {"type": "UserMessage", "content": [{"type": "text", "text": " <recommended_plugins/>"}]},
                },
            },
            "codex/event_msg/item_completed/UserMessage/injected",
            "harness_context",
        ),
        (
            "claude",
            {"type": "user", "message": {"content": "<system-reminder>x</system-reminder>"}},
            "claude/user/injected",
            "harness_context",
        ),
        (
            "claude",
            {"type": "user", "message": {"content": [{"type": "text", "text": "plain <not-a-tag"}]}},
            "claude/user/prompt",
            "prompt",
        ),
    ],
)
def test_classify_and_category(harness: str, rec: object, kind: str, category: str) -> None:
    assert harnesses.get(harness).classify(rec) == kind  # type: ignore[arg-type]
    assert records.category_of(kind) == category


def test_every_catalogued_kind_has_a_category_with_a_pill_colour() -> None:
    assert set(records.KINDS.values()) <= set(records.CATEGORIES)
    assert all(c.startswith("#") and len(c) == 7 for c in records.CATEGORIES.values())


def test_census_counts_kinds_in_sorted_order() -> None:
    recs = [{"type": "ai-title"}, {"type": "user", "message": {"content": "x"}}, {"type": "ai-title"}]
    assert harnesses.get("claude").census(recs) == {"claude/ai-title": 2, "claude/user/prompt": 1}
