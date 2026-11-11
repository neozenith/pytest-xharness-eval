"""``harness.kiro``: folding a Kiro V3 session log into a credit-metered run (ADR 0034, ADR 0072, ADR 0078).

The records below have the shapes kiro-cli 3.1.0 writes to ``messages.jsonl`` and
``sub-executions/<id>.jsonl``: a ``{id, timestamp, payload}`` envelope whose ``payload.type``
is the record's kind. They are built here rather than copied from a captured session, which
would carry a person's own prompts; nothing spawns or stands in for the CLI (ADR 0002).
"""

# Standard Library
import json
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import Usage
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.harness import RunError
from pytest_xharness_eval.harness import kiro as kiro_harness
from pytest_xharness_eval.harness.threads import SubagentMismatch
from pytest_xharness_eval.model.layout import SessionDir
from tests.support import DAY, _jsonl

KIRO = harnesses.get("kiro")


def rec(at: str, **payload: Any) -> dict[str, Any]:
    return {"id": f"r-{at}", "timestamp": f"2026-11-11T00:00:{at}Z", "payload": payload}


def say(at: str, text: str, op: str = "Say") -> dict[str, Any]:
    return rec(at, type="assistant", operationType=op, content=text, reasoningModelId="qdev::auto")


def tool(at: str, call_id: str, name: str, args: dict[str, Any], output: str) -> list[dict[str, Any]]:
    return [
        rec(at, type="tool_call", toolCallId=call_id, toolName=name, args=args, status="completed", kind="execute"),
        rec(at, type="tool_result", toolCallId=call_id, content=output, success=True),
    ]


def summary(at: str, credits: float, requests: int, status: str = "success", unit: str = "credit") -> dict[str, Any]:
    turns = [{"unit": unit, "unitPlural": f"{unit}s", "usage": credits, "usedTools": []}]
    ids = [f"req-{at}-{i}" for i in range(requests)]
    return rec(at, type="usage_summary", promptTurnSummaries=turns, elapsedTime=4000, status=status, requestIds=ids)


def start(at: str, sub: str, name: str = "introspect") -> dict[str, Any]:
    return rec(at, type="sub_agent_start", subSessionId=sub, subAgentName=name, explanation="checks the docs")


def two_turns() -> list[dict[str, Any]]:
    return [
        rec("00", type="agent_note", content="workspace context"),
        rec("01", type="user", content="/file-summary summarise README.md"),
        rec("02", type="turn_start", turnId="t1"),
        say("03", "Reading it.", op="Reasoning"),
        *tool("04", "c1", "run_command", {"command": "cat README.md", "cwd": "/w"}, "# Title"),
        say("05", "It is a title."),
        summary("06", 0.25, requests=2),
        rec("07", type="turn_end", stopReason="end_turn"),
        rec("08", type="user", content="shorter"),
        say("09", "Title."),
        summary("10", 0.5, requests=1, status="aborted"),
        rec("11", type="session_event", category="session_pause"),
    ]


def test_one_call_per_metered_turn_carries_its_credits_and_no_tokens(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "messages.jsonl", two_turns())
    r = kiro_harness.KiroSessionLog(log, 0, "sess_1", "claude-haiku-5.5", []).to_result(tmp_path, ["a.md"])
    assert (r.harness, r.session_id, r.model, r.turns) == ("kiro", "sess_1", "claude-haiku-5.5", 2)
    assert [c.usage for c in r.calls] == [Usage(credits=0.25), Usage(credits=0.5)]
    assert r.usage == Usage(credits=0.75) and r.usage.accumulative_billed_tokens == 0
    assert [c.stop_reason for c in r.calls] == ["end_turn", "aborted"]
    first = r.calls[0]
    assert (first.text, first.thinking) == ("It is a title.", "Reading it.")
    assert [(t.name, t.id, t.ended_at) for t in first.tools] == [("run_command", "c1", "2026-11-11T00:00:04Z")]
    assert [(o.tool, o.content) for o in first.results_in] == [("run_command", "# Title")]
    # Lines are 1-based; the trailing turn_end and session_event join the last call.
    assert first.records == [1, 2, 3, 4, 5, 6, 7, 8] and r.calls[1].records == [9, 10, 11, 12, 13]
    assert (r.final_text, r.duration_ms, r.api_duration_ms) == ("Title.", 8000, 8000)
    assert (r.reported_usage, r.reported_turns, r.tool_calls) == ({"requests": 3}, 2, {"run_command": 1})
    assert r.record_kinds["kiro/assistant/reasoning"] == 1 and r.record_kinds["kiro/usage_summary"] == 2


def test_a_subagent_is_linked_to_its_start_and_meters_nothing_of_its_own(tmp_path: Path) -> None:
    """A turn's credits include its subagent's work, so the subagent's ledger bills zero (ADR 0078)."""
    records = [
        rec("01", type="user", content="research"),
        start("02", "sub-a"),
        rec("03", type="sub_agent_complete", subSessionId="sub-a", status="success", response="done"),
        say("04", "Found it."),
        summary("05", 1.5, requests=4),
    ]
    log = _jsonl(tmp_path / "messages.jsonl", records)
    sub = _jsonl(
        tmp_path / "subagents" / "sub-a.jsonl",
        [say("02", "Fetching."), *tool("03", "f1", "web_fetch", {"url": "https://kiro.dev"}, "docs")],
    )
    r = kiro_harness.KiroSessionLog(log, 0, "sess_1", "auto").to_result(tmp_path, [])
    (s,) = r.subagents
    assert (s.id, s.agent, s.description, s.log) == ("sub-a", "introspect", "checks the docs", str(sub))
    assert (s.spawned_by, s.parent, s.depth, s.parent_turn, s.turns) == ("sub-a", "", 1, 1, 1)
    assert s.usage == Usage() and r.usage == Usage(credits=1.5)
    assert [t.name for t in s.calls[0].tools] == ["web_fetch"] and s.calls[0].text == "Fetching."
    priced = pricing.price(r, pricing.PriceTable(tuple(pricing.parse_price_lines(["kiro/auto: credit=0.04"]))), DAY)
    assert priced.estimated_cost_usd == pytest.approx(0.06) and s.estimated_cost_usd == 0.0


def test_a_nested_spawn_names_the_subagent_that_logged_it_as_parent(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "messages.jsonl", [start("01", "sub-a"), summary("02", 1.0, 1)])
    a = tmp_path / "subagents" / "sub-a.jsonl"
    _jsonl(a, [say("01", "delegating"), start("01", "sub-b", name="worker")])
    _jsonl(tmp_path / "subagents" / "sub-b.jsonl", [say("01", "working")])
    r = kiro_harness.KiroSessionLog(log, 0, "s", "auto").to_result(tmp_path, [])
    assert {s.id: (s.agent, s.parent, s.depth) for s in r.subagents} == {
        "sub-a": ("introspect", "", 1),
        "sub-b": ("worker", "sub-a", 2),
    }


@pytest.mark.parametrize(
    ("spawned", "transcripts", "match"),
    [
        (["sub-a"], [], "no captured subagent transcript: sub-a"),
        ([], ["sub-z"], "named by 0 spawn records"),
    ],
)
def test_spawns_and_transcripts_that_do_not_pair_stop_the_fold(
    tmp_path: Path, spawned: list[str], transcripts: list[str], match: str
) -> None:
    log = _jsonl(tmp_path / "messages.jsonl", [*(start("01", s) for s in spawned), summary("02", 1.0, 1)])
    paths = [_jsonl(tmp_path / "sub-executions" / f"{t}.jsonl", [say("01", "x")]) for t in transcripts]
    with pytest.raises(SubagentMismatch, match=match):
        kiro_harness.KiroSessionLog(log, 0, "s", "auto", paths).to_result(tmp_path, [])


def test_a_turn_metered_in_another_unit_stops_the_fold(tmp_path: Path) -> None:
    """Pricing a unit the log did not state would be a guess (ADR 0078)."""
    log = _jsonl(tmp_path / "messages.jsonl", [summary("01", 3.0, 1, unit="token")])
    with pytest.raises(RunError, match="meters 'token', not 'credit'"):
        kiro_harness.KiroSessionLog(log, 0, "s", "auto", []).to_result(tmp_path, [])


def test_a_log_with_no_metered_turn_is_one_unmetered_call_that_never_passes_as_real(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "messages.jsonl", [rec("01", type="user", content="/nosuchskill go"), say("02", "?")])
    r = kiro_harness.KiroSessionLog(log, 0, "s", "auto", []).to_result(tmp_path, [])
    assert (r.turns, r.usage, r.reported_turns) == (1, Usage(), 0)


def test_replay_recovers_the_id_and_model_the_log_does_not_name(tmp_path: Path) -> None:
    session = SessionDir(tmp_path / "session")
    _jsonl(session.log, two_turns())
    stored = {"exit_code": 0, "session_id": "sess_1", "model": "claude-haiku-5.5"}
    r = KIRO.session_from_capture(session, stored).to_result(tmp_path, [])
    assert (r.session_id, r.model, r.usage) == ("sess_1", "claude-haiku-5.5", Usage(credits=0.75))


def test_the_one_session_under_a_private_home_and_its_metadata(tmp_path: Path) -> None:
    with pytest.raises(RunError, match="found 0"):
        kiro_harness.primary_session(tmp_path)
    one = tmp_path / "sessions" / "3ef2a33371478438" / "sess_1"
    _jsonl(one / "messages.jsonl", [])
    (one / "session.json").write_text(json.dumps({"id": "sess_1", "modelId": "claude-haiku-5.5"}), encoding="utf-8")
    assert kiro_harness.primary_session(tmp_path) == one
    assert kiro_harness.session_meta(one) == ("sess_1", "claude-haiku-5.5")
    _jsonl(tmp_path / "sessions" / "3ef2a33371478438" / "sess_2" / "messages.jsonl", [])
    with pytest.raises(RunError, match="found 2"):
        kiro_harness.primary_session(tmp_path)
    (one / "session.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunError, match="names no session id"):
        kiro_harness.session_meta(one)


@pytest.mark.parametrize(
    ("record", "kind"),
    [
        ({"payload": {"type": "assistant", "operationType": "Say"}}, "kiro/assistant/say"),
        ({"payload": {"type": "assistant", "operationType": "Reasoning"}}, "kiro/assistant/reasoning"),
        ({"payload": {"type": "session_event", "category": "session_pause"}}, "kiro/session_event/session_pause"),
        ({"payload": {"type": "tombstone", "kind": "summarization"}}, "kiro/tombstone/summarization"),
        ({"payload": {"type": "usage_summary"}}, "kiro/usage_summary"),
        ({"payload": "not a mapping"}, "kiro/unknown"),
        ("not a record", "kiro/unknown"),
    ],
)
def test_records_classify_by_payload_type(record: object, kind: str) -> None:
    assert KIRO.classify(record) == kind  # type: ignore[arg-type]


def test_a_summarised_history_counts_as_a_compaction(tmp_path: Path) -> None:
    log = _jsonl(tmp_path / "messages.jsonl", [rec("01", type="tombstone", kind="summarization"), summary("02", 1, 1)])
    assert kiro_harness.KiroSessionLog(log, 0, "s", "auto", []).to_result(tmp_path, []).compactions == 1


def test_a_skill_is_invoked_as_its_slash_command_and_effort_is_a_flag() -> None:
    assert KIRO.prompt(skill="file-summary", task="summarise README.md") == "/file-summary summarise README.md"
    assert KIRO.prompt(skill=None, task="summarise README.md") == "summarise README.md"
    assert (KIRO.effort_args("xhigh"), KIRO.effort_args(None)) == (["--effort", "xhigh"], [])
    assert [KIRO.resolve_effort(a) for a in ("min", "mid", "max")] == ["low", "high", "max"]
    assert KIRO.shell_commands({"command": "cat README.md", "cwd": "/w"}) == [("cat README.md", "/w")]
