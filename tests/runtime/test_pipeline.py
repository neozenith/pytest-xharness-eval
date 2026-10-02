"""``runtime.pipeline``: the one sequence a live cell and a replay both run (ADR 0034)."""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CaseRef,
    CostStatus,
    ToolCall,
    Usage,
    evalcase,
)
from pytest_xharness_eval.derive import pricing, skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.model.layout import CacheLayout, SessionDir
from pytest_xharness_eval.model.runresult import Subagent
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.runtime import pipeline
from tests.support import DAY, _result, _skill


def test_capture_writes_the_log_subagent_transcripts_and_the_result(tmp_path: Path) -> None:
    """Evidence capture, previously inline in the paid code path and so never exercised.

    The subagent transcripts are copied out of wherever the harness left them -- a private
    CODEX_HOME that is about to be torn down, or Claude's config dir -- and each
    ``Subagent.log`` is rewritten to the captured copy, so a replay re-derives the same
    ledgers from the session directory alone (ADR 0033).
    """
    native = tmp_path / "native"
    native.mkdir()
    (native / "session.jsonl").write_text('{"type": "user"}\n', encoding="utf-8")
    (native / "agent-a1.jsonl").write_text('{"type": "user"}\n', encoding="utf-8")
    (native / "agent-a1.meta.json").write_text('{"agentType": "Explore"}', encoding="utf-8")

    r = _result("m", Usage(1, 2, 3, 4))
    r.session_log = str(native / "session.jsonl")
    r.session_id = "sid-1"
    r.subagents = [
        Subagent(agent="Explore", id="a1", log=str(native / "agent-a1.jsonl"), turns=1, usage=Usage(1, 1)),
        # A transcript the harness never wrote is skipped rather than failing the capture.
        Subagent(agent="ghost", id="a2", log=str(native / "missing.jsonl"), turns=0, usage=Usage()),
    ]

    session = pipeline.capture(r, SessionDir(tmp_path / "results" / "sid-1"))

    assert session.log.read_text(encoding="utf-8") == '{"type": "user"}\n'
    assert (session.subagents / "agent-a1.jsonl").is_file()
    assert (session.subagents / "agent-a1.meta.json").is_file()
    assert r.subagents[0].log == "subagents/agent-a1.jsonl"  # rewritten to the captured copy
    assert r.subagents[1].log == str(native / "missing.jsonl")  # untouched: nothing was copied
    stored = json.loads(session.result.read_text(encoding="utf-8"))
    assert stored["session_id"] == "sid-1"


def test_capture_of_a_run_without_subagents_writes_no_subagents_dir(tmp_path: Path) -> None:
    r = _result("m", Usage())
    (tmp_path / "s.jsonl").write_text("{}\n", encoding="utf-8")
    r.session_log = str(tmp_path / "s.jsonl")
    session = pipeline.capture(r, SessionDir(tmp_path / "out"))
    assert not session.subagents.exists()


def test_record_metrics_writes_the_cell_record_beside_its_evidence(tmp_path: Path) -> None:
    """The live cell and a replay build this record with the same call (ADR 0032, ADR 0034)."""
    r = _result("claude-opus-5", Usage(10, 20, 30, 40))
    session = SessionDir(tmp_path / "sid")
    session.mkdir()
    record = pipeline.record_metrics(
        r,
        session,
        outcome=Outcome(
            node="skills/demo/evals/eval_x.py::eval_x[claude/claude-opus-5]",
            verdict=Verdict.PASS,
            wall_ms=1234,
            started_at="2026-08-22T00:00:00+00:00",
        ),
        cache=CacheLayout(tmp_path / "cache"),
    )
    assert record.verdict == "pass" and record.wall_ms == 1234
    # ``cache`` is a declared field of the record, not a key stamped on afterwards (ADR 0037).
    assert record.cache == str(tmp_path / "cache")
    assert CellMetrics.stored(session.history) == record


def test_derive_prices_annotates_and_names_the_case_in_one_order(tmp_path: Path) -> None:
    """The order matters only in that both paths must use the same one."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("claude-opus-5", Usage(1_000_000, 0, 0, 0))
    r.workspace = "/x/ws"
    r.calls = [Call(n=1, at="t", tools=[ToolCall("Read", "", {"file_path": "/x/skills/demo/SKILL.md"})])]
    case = CaseRef.of(
        evalcase(task="go", skill="demo", fixture="seed")(lambda output: None),
        "skills/demo/evals/eval_x.py",
        "/demo go",
    )
    out = pipeline.derive(r, table=pricing.load_table(), run_date=DAY, skill="demo", skill_files=files, case=case)
    assert out is r
    assert r.cost_status is CostStatus.PRICED and r.estimated_cost_usd == pytest.approx(5.0)
    assert r.skill_coverage is not None and r.skill_coverage.loaded == ["SKILL.md"]
    assert r.case == CaseRef(
        suite="skills/demo/evals/eval_x.py",
        name="<lambda>",
        skill="demo",
        fixture="seed",
        task="go",
        prompt="/demo go",
    )
