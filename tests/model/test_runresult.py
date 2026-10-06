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
from tests.support import _result


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
    supplied = _typed_dict_keys(runresult.RunResultFields)
    assert not supplied & (derived | priced | attached)
    assert supplied | derived | priced | attached == {f.name for f in dataclasses.fields(RunResult)}


def test_each_subagent_field_is_derived_from_the_ledger_or_named_by_the_transcript() -> None:
    """The same partition for a spawned thread: ``turns`` and ``usage`` are never supplied."""
    derived = {"turns", "usage", "calls"}
    supplied = _typed_dict_keys(runresult.SubagentFields)
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
