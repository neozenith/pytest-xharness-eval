"""``emit.metrics``: the per-cell metrics record and its frozen wire format (ADR 0037)."""

# Standard Library
import dataclasses
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CaseRef,
    Cell,
    Usage,
)
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.model import clock
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _applied_rates, _metrics, _result


def test_a_dry_run_record_names_the_rung_it_would_have_run_at() -> None:
    dry = CellMetrics.dry_run(node="n", cell=Cell(harness="claude", model="claude-opus-5", effort="high"))
    assert dry.effort == "high" and dry.verdict == Verdict.DRY_RUN.value
    assert CellMetrics.dry_run(node="n", cell=Cell(harness="claude", model="claude-opus-5")).effort == ""


def test_case_metadata_round_trips_and_reaches_history(tmp_path: Path) -> None:
    """The case that produced a run rides on the result: task and rendered prompt both (ADR 0025, ADR 0044)."""
    r = _result("m", Usage(1, 2, 3, 4))
    r.estimated_cost_usd = 0.1
    r.case = CaseRef(
        suite="skills/demo/evals/eval_demo.py",
        name="eval_demo",
        skill="demo",
        fixture="seed",
        task="say hi",
        prompt="/demo say hi",
    )
    data = json.loads(r.write(tmp_path / "r.json").read_text(encoding="utf-8"))
    assert data["case"]["suite"] == "skills/demo/evals/eval_demo.py"
    # Both are serialised, and they differ: the task is the declaration, the prompt is what
    # this harness rendered around it (ADR 0044).
    assert (data["case"]["task"], data["case"]["prompt"]) == ("say hi", "/demo say hi")
    rec = _metrics(r).to_dict()
    assert (rec["suite"], rec["case"], rec["skill"], rec["fixture"]) == (
        "skills/demo/evals/eval_demo.py",
        "eval_demo",
        "demo",
        "seed",
    )
    assert "prompt" not in rec  # the prompt lives on the result, not on every history line


def test_metrics_record_is_flat_and_complete() -> None:

    r = _result("m", Usage(10, 20, 30, 40))
    r.turns, r.duration_ms, r.estimated_cost_usd = 7, 4321, 0.5
    r.rates_applied = _applied_rates()
    r.tool_calls = {"Edit": 2, "Bash": 3}
    r.files_written = ["a", "b"]
    r.calls = [Call(n=1, at="t", usage=Usage(input_tokens=10, cache_read_tokens=30))]
    cell = _metrics(r, node="n[x/m]", wall_ms=5000, started_at="2026-08-21T00:00:00+00:00")
    rec = cell.to_dict()
    assert rec["tool_calls"] == 5 and rec["tool_calls_by_name"] == {"Edit": 2, "Bash": 3}
    assert (rec["turns"], rec["duration_ms"], rec["wall_ms"], rec["estimated_cost_usd"]) == (7, 4321, 5000, 0.5)
    # Names carry unit and source (ADR 0021); no bare "tokens", "cost_usd" or headline "context".
    assert (rec["accumulative_billed_tokens"], rec["baseline_tokens"], rec["peak_context_tokens"]) == (100, 40, 40)
    assert not {"tokens", "billed_tokens", "context_tokens", "cost_usd", "reported_cost_usd"} & rec.keys()
    assert (rec["harness_reported_cost_usd"], rec["reported_turns"]) == (None, None)
    assert rec["rates_applied"]["model"] == "m" and rec["rates_applied"]["source"] == "/p/prices-20260820.toml"
    # A wire contract mirrored by report-ui/src/lib/types.ts (ADR 0021, ADR 0050, ADR 0051).
    assert set(rec["rates_applied"]) == {
        "input",
        "output",
        "cache_read",
        "cache_write",
        "cache_write_1h",
        "long_context",
        "unit",
        "harness",
        "model",
        "source",
        "effective_from",
        "effective_to",
        "applied_at",
    }
    assert rec["files_written"] == 2
    assert (
        cell.status_word() == "est $0.5000  100 accumulative_billed_tokens  40 baseline_tokens  5.0s  7 turns  5 tools"
    )
    reported = dataclasses.replace(cell, harness_reported_cost_usd=0.6)
    assert reported.status_word().startswith("est $0.5000 (harness $0.6000)  100 accumulative_billed_tokens")


def test_history_carries_coverage_counts_and_the_status_word_shows_them() -> None:
    r = _result("m", Usage(10, 20, 30, 40))
    r.estimated_cost_usd = 0.5
    r.skill_coverage = skillcov.SkillCoverage(
        skill="demo",
        files=[],
        loaded=[],
        run=[],
        not_loaded=["a"],
        not_run=["b"],
        summary=skillcov.CoverageSummary(files=8, ignored=0, docs=0, scripts=2, tests=0, assets=0, loaded=3, run=1),
    )
    cell = _metrics(r, wall_ms=1000)
    rec = cell.to_dict()
    assert (rec["skill_files"], rec["skill_files_loaded"], rec["skill_scripts"], rec["skill_scripts_run"]) == (
        8,
        3,
        2,
        1,
    )
    assert (rec["skill_not_loaded"], rec["skill_not_run"]) == (["a"], ["b"])
    assert cell.status_word().endswith("1 turns  0 tools  skill 3/8 loaded 1/2 run")
    # Where the harness reports a window, how close the run came to it is in the word too.
    r.context_window = 1000
    r.calls = [Call(n=1, at="t", usage=Usage(input_tokens=100))]
    assert "  ctx 10.0%  skill 3/8 loaded" in _metrics(r, wall_ms=1000).status_word()


def test_a_metrics_record_round_trips_through_disk_and_the_wire(tmp_path: Path) -> None:
    """One line of sorted JSON out, the same record back (ADR 0037)."""
    record = _metrics(_result("m", Usage(10, 20, 30, 40)), node="n[x/m]", verdict=Verdict.FAIL)
    path = record.write(tmp_path / "sid" / "history.json")
    assert path.read_text(encoding="utf-8").endswith("}\n")
    assert json.loads(path.read_text(encoding="utf-8")) == record.to_dict()
    assert CellMetrics.stored(path) == record
    # The wire boundary: execnet ships builtins only, so the record crosses as a mapping
    # and is decoded on the controller (ADR 0016).
    assert CellMetrics.from_dict(record.to_dict()) == record
    assert clock.now_iso().endswith("+00:00")


def test_a_metrics_record_survives_a_partial_or_foreign_document(tmp_path: Path) -> None:
    """A capture from another version reads as a partial record, never as a failed rebuild."""
    assert CellMetrics.stored(tmp_path / "absent.json") is None
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    assert CellMetrics.stored(tmp_path / "broken.json") is None
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    assert CellMetrics.stored(tmp_path / "list.json") is None
    # Unknown keys are dropped and absent ones keep their default; the four values a
    # replay must carry forward come back as an Outcome.
    partial = CellMetrics.from_dict(
        {"verdict": "pass", "node": "n", "at": "t", "wall_ms": 7, "tokens": 99, "captured": "/old"}
    )
    assert partial.outcome == Outcome(node="n", verdict=Verdict.PASS, wall_ms=7, started_at="t")
    assert partial.turns == 0 and partial.estimated_cost_usd is None
    assert "tokens" not in partial.to_dict() and "captured" not in partial.to_dict()
    # A present-but-null value is dropped like an unknown key, so the *declared* type holds
    # and every reader may trust it: a record whose ``at`` is null sorts as "" rather than
    # raising in the combine step (ADR 0038).
    nulled = CellMetrics.from_dict(
        {"at": None, "verdict": None, "wall_ms": None, "rates_applied": None, "skill_not_run": None}
    )
    assert (nulled.at, nulled.verdict, nulled.wall_ms) == ("", "", 0)
    assert (nulled.rates_applied, nulled.skill_not_run) == ({}, [])
    # An optional field still admits its null, and JSON's one number type still reads as a float.
    priced = CellMetrics.from_dict({"reported_turns": None, "estimated_cost_usd": 0, "context_window": "wide"})
    assert priced.reported_turns is None and priced.context_window is None
    assert isinstance(priced.estimated_cost_usd, float)


# Every key of ``history.json``, spelled out. ``report-ui/src/lib/types.ts`` mirrors this
# set, and so does the glossary's metric table: a field added, renamed or dropped without
# the same edit there is a silently broken page, which is what this list exists to catch.
HISTORY_KEYS = [
    "accumulative_billed_tokens",
    "at",
    "baseline_tokens",
    "cache",
    "cache_read_tokens",
    "cache_write_1h_tokens",
    "cache_write_tokens",
    "case",
    "context_window",
    "context_window_pct",
    "duration_ms",
    "effort",
    "estimated_cost_usd",
    "family_tier",
    "files_written",
    "final_context_pct",
    "fixture",
    "harness",
    "harness_reported_cost_usd",
    "input_tokens",
    "line",
    "model",
    "node",
    "output_tokens",
    "output_tokens_per_sec",
    "peak_context_tokens",
    "rates_applied",
    "reasoning_tokens",
    "record_kinds",
    "released",
    "reported_turns",
    "session_id",
    "skill",
    "skill_files",
    "skill_files_loaded",
    "skill_not_loaded",
    "skill_not_run",
    "skill_scripts",
    "skill_scripts_run",
    "suite",
    "tool_calls",
    "tool_calls_by_name",
    "treatment",
    "ttft_ms",
    "turns",
    "verdict",
    "wall_ms",
]


def test_history_json_has_exactly_the_frozen_key_set() -> None:
    """A fitness function, not a restatement: these names are a published wire format."""
    assert sorted(_metrics(_result("m", Usage(1, 2))).to_dict()) == HISTORY_KEYS
    # The dry-run record is the same document, not a shape of its own (ADR 0037), and it
    # names no cache root, so a dry run combines nothing.
    dry = CellMetrics.dry_run(node="n", cell=mx.Cell(harness="claude", model="claude-opus-5"))
    assert sorted(dry.to_dict()) == HISTORY_KEYS
    assert (dry.verdict, dry.harness, dry.model, dry.cache) == ("dry-run", "claude", "claude-opus-5", "")
    # The fourth word's only producer names it from the vocabulary, and still stores the
    # plain word: this record is shipped by execnet (ADR 0016, ADR 0041).
    assert dry.verdict == Verdict.DRY_RUN and type(dry.verdict) is str
