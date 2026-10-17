"""``model.runresult``: the run record's invariants and its derived figures (ADR 0035)."""

# Standard Library
import dataclasses
import json
from pathlib import Path
from typing import Any

# Our Libraries
from pytest_xharness_eval import (
    Call,
    RunResult,
    Usage,
)
from pytest_xharness_eval.model import runresult
from pytest_xharness_eval.model.runresult import Subagent
from tests.support import _result, _subagent


def test_accumulative_billed_tokens_sums_the_four_priced_tiers_only() -> None:
    assert Usage(1, 2, 3, 4, reasoning_tokens=100).accumulative_billed_tokens == 10


def test_write_round_trips_with_accumulative_billed_tokens(tmp_path: Path) -> None:
    r = _result("m", Usage(1, 2, 3, 4))
    out = r.write(tmp_path / "nested" / "r.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["usage"]["accumulative_billed_tokens"] == 10
    assert data["cost_status"] == "unpriced"
    assert data["harness"] == "claude"
    assert (data["baseline_tokens"], data["calls"], data["rates_applied"]) == (0, [], {})
    assert "context_tokens" not in data and "cost_usd" not in data and data["estimated_cost_usd"] is None


def test_baseline_comes_from_the_first_turn_of_the_ledger(tmp_path: Path) -> None:
    """``baseline_tokens`` is turn 1's context; per-turn context stays inside the ledger (ADR 0019, 0021)."""
    r = _result("m", Usage())
    r.calls = [
        Call(n=1, at="t1", usage=Usage(input_tokens=10, cache_read_tokens=20_000), records=[1, 2]),
        Call(n=2, at="t2", usage=Usage(input_tokens=2, cache_read_tokens=20_008, cache_write_tokens=5_000)),
        Call(n=3, at="t3", usage=Usage(input_tokens=2, cache_read_tokens=25_000, output_tokens=300)),
    ]
    assert [c.context_tokens for c in r.calls] == [20_010, 25_010, 25_002]
    assert r.baseline_tokens == 20_010
    data = json.loads(r.write(tmp_path / "r.json").read_text(encoding="utf-8"))
    assert "context_tokens" not in data  # no headline context figure (ADR 0021)
    assert [c["context_tokens"] for c in data["calls"]] == [20_010, 25_010, 25_002]
    assert data["calls"][0]["usage"]["cache_read_tokens"] == 20_000 and data["calls"][0]["records"] == [1, 2]


def _typed_dict_keys(td: Any) -> set[str]:
    """Every key a TypedDict declares.

    Required and optional are unioned rather than compared: this module's annotations are
    strings (``from __future__ import annotations``), so at runtime ``NotRequired`` is not
    unwrapped and every key reports as required. The type checker sees the real split.
    """
    return set(td.__required_keys__) | set(td.__optional_keys__)


def test_each_runresult_field_has_exactly_one_owner() -> None:
    """``folded``'s ``**fields`` is a TypedDict, so every field is checked by name (ADR 0035).

    A field belongs to one owner: the fold derives it from the ledgers, ``apply_cost``
    writes it with its provenance, the derivation pipeline attaches it after grading, or
    the harness adapter observed it — and only that last group is reachable through
    ``folded``. A key whose *type* drifts is already a static error, because ``folded``
    unpacks the TypedDict into the dataclass; a field whose *name* drifts is not, so it
    is asserted here: a new field would otherwise be silently unreachable, and a stale
    key would fail first at a paid call site.
    """
    derived = {"turns", "usage", "calls", "subagents"}
    priced = {"estimated_cost_usd", "cost_status", "cost_by_tier", "rates_applied", "long_context_calls"}
    attached = {"case", "effort", "treatment", "line", "family_tier", "released", "skill_coverage"}
    # Observed at the spawn when the CLI is killed at the wall, by `harness.mark_timed_out` (ADR 0064).
    killed = {"timed_out_after_s", "idle_before_timeout_s"}
    supplied = _typed_dict_keys(runresult.RunResultFields)
    assert not supplied & (derived | priced | attached | killed)
    assert supplied | derived | priced | attached | killed == {f.name for f in dataclasses.fields(RunResult)}


def test_each_subagent_field_is_derived_from_the_ledger_or_named_by_the_transcript() -> None:
    """The same partition for a spawned thread: ``turns`` and ``usage`` are never supplied."""
    derived = {"turns", "usage", "calls"}
    priced = {"estimated_cost_usd"}  # written by pricing at the subagent's own model's rates (ADR 0065)
    supplied = _typed_dict_keys(runresult.SubagentFields) | priced
    assert not supplied & derived
    assert supplied | derived == {f.name for f in dataclasses.fields(Subagent)}


def test_window_unknown_means_no_percentages() -> None:
    r = _result("m", Usage())
    r.duration_ms = 0
    r.calls = [Call(n=1, at="t", usage=Usage(input_tokens=10))]
    assert (r.context_window, r.context_window_pct, r.final_context_pct, r.output_tokens_per_sec) == (
        None,
        None,
        None,
        None,
    )
    assert r.to_dict()["calls"][0]["context_pct"] is None


# -- the Important Metrics a run derives (ADR 0071) ----------------------------------------


def _call(n: int, output: int, latency_ms: int | None) -> Call:
    return Call(n=n, at="", usage=Usage(input_tokens=10, output_tokens=output), latency_ms=latency_ms)


def _with_subagent(sub_model: str = "haiku", sub_cost: float | None = 0.25) -> RunResult:
    sub = _subagent([_call(1, 20, 1000)], model=sub_model)
    sub.estimated_cost_usd = sub_cost
    result = RunResult.folded(
        [_call(1, 50, 500), _call(2, 50, None)],
        [sub],
        harness="claude",
        model="opus",
        session_id="s",
        session_log="l",
        workspace="w",
        exit_code=0,
        duration_ms=1,
        final_text="",
    )
    result.estimated_cost_usd = 1.0
    return result


def test_reasoning_share_is_reasoning_over_output_and_none_with_nothing_generated() -> None:
    assert _result("m", Usage(output_tokens=200, reasoning_tokens=50)).reasoning_share == 0.25
    assert _result("m", Usage(input_tokens=5)).reasoning_share is None


def test_the_subagents_shares_of_tokens_and_cost() -> None:
    result = _with_subagent()
    # Primary: two calls of 10 in + 50 out; the subagent: 10 in + 20 out.
    assert result.subagent_token_share == round(30 / 150, 4)
    assert result.subagent_cost_share == 0.25
    assert _result("m", Usage(1, 1)).subagent_token_share == 0.0


def test_a_cost_share_of_an_unknown_is_none_never_zero() -> None:
    assert _with_subagent(sub_cost=None).subagent_cost_share is None
    unpriced = _with_subagent()
    unpriced.estimated_cost_usd = None
    assert unpriced.subagent_cost_share is None


def test_throughput_is_split_by_the_model_that_answered_and_counts_only_timed_calls() -> None:
    # Opus: 50 tokens over 0.5s (the untimed call counts on neither side); haiku: 20 over 1s.
    assert _with_subagent().output_tokens_per_sec_by_model == {"haiku": 20.0, "opus": 100.0}
    # A subagent that names no model ran on its parent's, so both threads pool under it.
    assert _with_subagent(sub_model="").output_tokens_per_sec_by_model == {"opus": round(70 / 1.5, 2)}


def test_the_derived_metrics_reach_result_json() -> None:
    data = _with_subagent().to_dict()
    assert {"reasoning_share", "subagent_token_share", "subagent_cost_share", "output_tokens_per_sec_by_model"} <= set(
        data
    )
    assert data["compactions"] == 0


# -- a subagent's span (ADR 0072) ----------------------------------------------------------


def test_a_subagents_duration_is_its_span_and_its_throughput_its_generation_speed() -> None:
    # 30 tokens over 1.5s of measured latency; the untimed call counts on neither side, and
    # the ten-second span (tool runs included) is not the divisor.
    sub = _subagent([_call(1, 20, 1000), _call(2, 10, 500), _call(3, 99, None)])
    assert (sub.duration_ms, sub.output_tokens_per_sec) == (10_000, 20.0)


def test_a_subagent_with_no_timed_call_or_an_unreadable_span_says_so() -> None:
    assert _subagent([_call(1, 20, None)]).output_tokens_per_sec is None
    assert _subagent(started_at="soon").duration_ms is None


def test_a_subagents_span_and_link_reach_result_json() -> None:
    (raw,) = _with_subagent().to_dict()["subagents"]
    assert raw["duration_ms"] == 10_000 and raw["output_tokens_per_sec"] == 20.0
    assert {"spawned_by", "parent", "depth", "parent_turn", "started_at", "ended_at"} <= set(raw)
