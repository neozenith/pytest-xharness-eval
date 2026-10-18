"""``emit.metrics``: the per-cell metrics record and its frozen wire format (ADR 0037)."""

# Standard Library
import dataclasses
import json
from pathlib import Path
from types import UnionType
from typing import get_args, get_type_hints

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CaseRef,
    Cell,
    CostStatus,
    ToolCall,
    Usage,
)
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.derive.toolcost import SkillUse, ToolCost
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.model import clock
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model.case import CaseKind
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.metrics import roles
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _applied_rates, _metrics, _result, _subagent


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
        subject="demo",
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
    "api_duration_ms",
    "at",
    "attempted",
    "baseline_tokens",
    "cache",
    "cache_read_share",
    "cache_read_tokens",
    "cache_rereads",
    "cache_write_1h_tokens",
    "cache_write_5m_tokens",
    "cache_write_tokens",
    "case",
    "compactions",
    "context_window",
    "context_window_pct",
    "duration_ms",
    "effort",
    "estimated_cost_usd",
    "exit_code",
    "failure",
    "family_tier",
    "files_written",
    "final_context_pct",
    "final_context_tokens",
    "fixture",
    "harness",
    "harness_reported_cost_usd",
    "idle_before_timeout_s",
    "input_tokens",
    "kind",
    "line",
    "long_context_calls",
    "model",
    "node",
    "output_tokens",
    "output_tokens_per_sec",
    "output_tokens_per_sec_by_model",
    "peak_context_tokens",
    "rates_applied",
    "reasoning_share",
    "reasoning_tokens",
    "record_kinds",
    "released",
    "reported_turns",
    "scenario",
    "scenario_fingerprint",
    "session_id",
    "skill",
    "skill_context_cost_share",
    "skill_context_cost_usd",
    "skill_cost_share",
    "skill_duration_ms",
    "skill_files",
    "skill_files_loaded",
    "skill_issuing_cost_usd",
    "skill_not_loaded",
    "skill_not_run",
    "skill_scripts",
    "skill_scripts_run",
    "skill_tool_calls",
    "skill_trigger",
    "skill_triggered",
    "skill_triggered_turn",
    "subagent_cost_share",
    "subagent_max_cost_usd",
    "subagent_max_depth",
    "subagent_max_ms",
    "subagent_ms",
    "subagent_peak_context_pct",
    "subagent_token_share",
    "subagents",
    "subject_version",
    "suite",
    "timed_out_after_s",
    "tool_calls",
    "tool_calls_by_name",
    "tool_calls_by_name_all",
    "tool_context_cost_usd",
    "tool_context_cost_usd_by_name",
    "tool_issuing_cost_usd",
    "tool_issuing_cost_usd_by_name",
    "tool_ms_by_name",
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


def _tool_cost(name: str, issuing: float, context: float, rereads: int) -> ToolCost:
    return ToolCost(
        thread="",
        turn=1,
        id=f"t-{name}",
        name=name,
        summary="",
        started_at="",
        ended_at="",
        duration_ms=None,
        issuing_cost_usd=issuing,
        result_tokens=0,
        context_cost_usd=context,
        cache_rereads=rereads,
    )


def _timed(name: str, seconds: int) -> ToolCall:
    return ToolCall(name, "", started_at="2026-10-01T00:00:00.000Z", ended_at=f"2026-10-01T00:00:0{seconds}.000Z")


def test_the_tool_skill_cache_and_subagent_figures_reach_the_record() -> None:
    """ADR 0073's per-tool and skill-use figures, flattened so the Analyzer can group and compare them."""
    r = _result("m", Usage(input_tokens=20, cache_read_tokens=60, cache_write_tokens=20))
    r.estimated_cost_usd, r.cost_status = 2.0, CostStatus.PRICED
    r.calls = [Call(n=1, at="t", tools=[_timed("Bash", 2), _timed("Read", 1), ToolCall("Bash", "")])]
    r.subagents = [
        _subagent([Call(n=1, at="t", tools=[_timed("Bash", 3)])]),
        _subagent(id="a2", depth=2, parent="a1", ended_at="2026-10-01T00:00:05.000Z"),
    ]
    r.tool_costs = [_tool_cost("Bash", 0.25, 0.5, 2), _tool_cost("Bash", 0.25, 0.0, 1), _tool_cost("Read", 0.1, 0.2, 0)]
    r.skill_use = SkillUse(
        skill="demo",
        trigger="prompt",
        triggered_turn=1,
        triggered_at="t",
        last_turn=3,
        last_at="t",
        duration_ms=900,
        tool_calls=2,
        issuing_cost_usd=0.5,
        context_cost_usd=0.25,
        cache_rereads=1,
    )
    rec = _metrics(r).to_dict()
    assert rec["tool_ms_by_name"] == {"Bash": 5000, "Read": 1000}  # an untimed call adds nothing
    assert (rec["tool_issuing_cost_usd_by_name"], rec["tool_context_cost_usd_by_name"]) == (
        {"Bash": 0.5, "Read": 0.1},
        {"Bash": 0.5, "Read": 0.2},
    )
    assert (rec["tool_issuing_cost_usd"], rec["tool_context_cost_usd"], rec["cache_rereads"]) == (0.6, 0.7, 3)
    assert rec["cache_read_share"] == 0.6
    assert (rec["skill_trigger"], rec["skill_triggered_turn"], rec["skill_duration_ms"]) == ("prompt", 1, 900)
    assert (rec["skill_tool_calls"], rec["skill_issuing_cost_usd"], rec["skill_context_cost_usd"]) == (2, 0.5, 0.25)
    assert (rec["skill_cost_share"], rec["skill_context_cost_share"]) == (0.25, 0.125)
    # Counts over every thread, beside the primary-only wire field, so ms per call divides like by like.
    assert (rec["tool_calls_by_name"], rec["tool_calls_by_name_all"]) == ({}, {"Bash": 3, "Read": 1})
    assert (rec["subagent_ms"], rec["subagent_max_depth"], rec["subagent_max_ms"]) == (15000, 2, 10000)
    # A thread with no estimate of its own leaves the costliest thread unknown, not zero.
    assert rec["subagent_max_cost_usd"] is None
    r.subagents[0].estimated_cost_usd, r.subagents[1].estimated_cost_usd = 0.3, 0.1
    assert _metrics(r).subagent_max_cost_usd == 0.3


def test_a_run_without_tool_costs_skill_use_or_subagents_records_none_not_zero() -> None:
    """An unpriced run, or a scenario case, must drop out of a metric's n rather than average as zero."""
    rec = _metrics(_result("m", Usage())).to_dict()
    assert (rec["tool_issuing_cost_usd"], rec["tool_context_cost_usd"], rec["cache_rereads"]) == (None, None, None)
    assert (rec["tool_ms_by_name"], rec["tool_issuing_cost_usd_by_name"]) == ({}, {})
    assert (rec["skill_trigger"], rec["skill_cost_share"], rec["cache_read_share"], rec["skill_triggered"]) == (
        None,
    ) * 4
    # Zero subagents is a count and a span of 0, like ``subagents`` itself; a window-less share is None.
    assert (rec["subagents"], rec["subagent_ms"], rec["subagent_max_depth"], rec["subagent_max_ms"]) == (0, 0, 0, 0)
    assert (rec["subagent_max_cost_usd"], rec["subagent_peak_context_pct"]) == (None, None)


def test_a_priced_run_with_no_tools_costs_nothing_and_a_skill_case_records_whether_it_triggered() -> None:
    r = _result("m", Usage(input_tokens=10))
    r.cost_status, r.context_window = CostStatus.PRICED, 1000
    r.case = CaseRef(kind=CaseKind.SKILL)
    rec = _metrics(r).to_dict()
    assert (rec["tool_issuing_cost_usd"], rec["tool_context_cost_usd"], rec["cache_rereads"]) == (0.0, 0.0, 0)
    assert (rec["skill_triggered"], rec["subagent_max_cost_usd"], rec["subagent_peak_context_pct"]) == (0, 0.0, 0.0)
    r.case = CaseRef(kind=CaseKind.SCENARIO)
    assert _metrics(r).skill_triggered is None


def test_how_the_cli_ended_and_its_timing_reach_the_record() -> None:
    r = _result("m", Usage(input_tokens=10, output_tokens=5, cache_write_tokens=8, cache_write_5m_tokens=8))
    r.calls = [Call(n=1, at="t", usage=Usage(input_tokens=10, output_tokens=5))]
    r.exit_code, r.api_duration_ms, r.long_context_calls = 3, 700, 1
    r.timed_out_after_s, r.idle_before_timeout_s = 600, 12.5
    rec = _metrics(r).to_dict()
    assert (rec["exit_code"], rec["attempted"], rec["api_duration_ms"], rec["long_context_calls"]) == (3, 1, 700, 1)
    assert (rec["timed_out_after_s"], rec["idle_before_timeout_s"]) == (600, 12.5)
    assert (rec["cache_write_5m_tokens"], rec["final_context_tokens"]) == (8, 15)
    r.calls = []
    assert _metrics(r).attempted == 0  # exited non-zero without a model call


def test_a_failure_reason_and_the_scenario_facts_ride_the_record_and_round_trip(tmp_path: Path) -> None:
    r = _result("m", Usage(1, 2))
    r.case = CaseRef(
        suite="s.py", name="eval_x", kind=CaseKind.SCENARIO, scenario="doc--1234abcd", subject_version="v1"
    )
    r.case = dataclasses.replace(r.case, scenario_fingerprint="f" * 64)
    outcome = Outcome(node="n", verdict=Verdict.FAIL, wall_ms=3, started_at="t", failure="doc.md still has MD009")
    record = CellMetrics.of(r, outcome=outcome, cache=CacheLayout(tmp_path))
    assert (record.failure, record.kind, record.scenario, record.subject_version) == (
        "doc.md still has MD009",
        "scenario",
        "doc--1234abcd",
        "v1",
    )
    assert record.scenario_fingerprint == "f" * 64
    back = CellMetrics.stored(record.write(tmp_path / "history.json"))
    assert back is not None and back.outcome == outcome  # a replay carries the reason forward


def test_every_numeric_field_declares_its_role_so_the_analyzer_never_guesses_one() -> None:
    """Kind and better direction, neutral, or a fact about the cell: declared on the field (ADR 0076)."""

    def numeric(hint: object) -> bool:
        parts = get_args(hint) if isinstance(hint, UnionType) else (hint,)
        return any(part in (int, float) for part in parts)

    numeric_fields = {name for name, hint in get_type_hints(CellMetrics).items() if numeric(hint)}
    declared = roles(CellMetrics)
    assert numeric_fields == set(declared)
    assert not declared["family_tier"].is_metric and declared["turns"].is_metric
    assert declared["subagents"].better is None  # neutral: delegation is neither good nor bad
