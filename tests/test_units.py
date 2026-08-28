"""Unit tests for the pure modules: pricing, matrix, normalise, workspace, case, runresult."""

# Standard Library
import dataclasses
import json
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    DEFAULT_MATRIX,
    Call,
    CaseRef,
    Cell,
    CostStatus,
    EvalCase,
    RunResult,
    ToolCall,
    ToolResult,
    Usage,
    __version__,
    evalcase,
)
from pytest_xharness_eval import harness as harnesses
from pytest_xharness_eval import ignorerules
from pytest_xharness_eval import matrix as mx
from pytest_xharness_eval import normalise, pipeline, pricing, records, replay, report, runresult, settings, skillcov
from pytest_xharness_eval import workspace as ws
from pytest_xharness_eval.harness import claude as claude_harness
from pytest_xharness_eval.harness import codex as codex_harness
from pytest_xharness_eval.layout import CacheLayout, SessionDir
from pytest_xharness_eval.metrics import CellMetrics, Outcome
from pytest_xharness_eval.runresult import Subagent

# -- package surface ---------------------------------------------------------------


def test_version_matches_pyproject(pytestconfig: pytest.Config) -> None:
    """`version` in pyproject.toml and `__version__` are declared twice; a release bumps both (ADR 0017)."""
    pyproject = tomllib.loads((pytestconfig.rootpath / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_the_registry_is_the_only_list_of_known_harnesses() -> None:
    """The matrix reads the registry, so a harness cannot be runnable but unmatrixable (ADR 0034)."""
    assert mx.known_harnesses() == harnesses.names() == ("claude", "codex")
    assert [harnesses.get(n).name for n in harnesses.names()] == list(harnesses.names())


def test_an_unregistered_harness_fails_loudly_rather_than_defaulting() -> None:
    """The dispatch that used to fall through to Codex now raises (ADR 0034)."""
    with pytest.raises(harnesses.UnknownHarness, match="unknown harness 'gemini'"):
        harnesses.get("gemini")


# -- matrix --------------------------------------------------------------------------


def test_expand_default_matrix() -> None:
    cells = mx.expand(DEFAULT_MATRIX)
    assert cells == [Cell("claude", "claude-opus-5"), Cell("codex", "gpt-5.6-sol")]
    assert cells[0].id == "claude/claude-opus-5"
    assert cells[0].harness == "claude"


@pytest.mark.parametrize("entry", ["gemini/pro", "claude", "claude/", "/opus"])
def test_expand_rejects_malformed_entries(entry: str) -> None:
    with pytest.raises(ValueError, match="matrix entry must be"):
        mx.expand([entry])


def test_narrow_by_harness_and_model() -> None:
    cells = mx.expand(DEFAULT_MATRIX)
    assert mx.narrow(cells, None, ["codex"]) == [Cell("codex", "gpt-5.6-sol")]
    assert mx.narrow(cells, ["opus"], None) == [Cell("claude", "claude-opus-5")]
    assert mx.narrow(cells, ["codex/gpt-5.6-sol"], None) == [Cell("codex", "gpt-5.6-sol")]
    assert mx.narrow(cells, ["opus"], ["codex"]) == []
    assert mx.narrow(cells, None, None) == cells


# -- case ----------------------------------------------------------------------------


def test_evalcase_without_models_inherits() -> None:
    @evalcase(prompt="p", skill="s", fixture="f")
    def eval_thing(run: RunResult, workspace: Path) -> None:
        pass

    assert isinstance(eval_thing, EvalCase)
    assert eval_thing.name == "eval_thing"
    assert eval_thing.models is None


def test_evalcase_override_is_copied() -> None:
    models = ["codex/gpt-5.6-luna"]

    @evalcase(prompt="p", skill="s", fixture="f", models=models)
    def eval_thing(run: RunResult, workspace: Path) -> None:
        pass

    assert eval_thing.models == models
    assert eval_thing.models is not models


# -- pricing -------------------------------------------------------------------------


def _result(model: str, usage: Usage, harness: str = "claude") -> RunResult:
    # A real harness name: coverage attribution resolves it to ask which tool names mean
    # "ran a shell command" and which of those keep their cwd (ADR 0034).
    return RunResult(
        harness=harness,
        model=model,
        session_id="s",
        session_log="l",
        workspace="w",
        exit_code=0,
        duration_ms=1,
        turns=1,
        final_text="",
        usage=usage,
    )


def _applied_rates(model: str = "m", source: str = "/p/prices.toml") -> pricing.AppliedRates:
    """A provenance block for tests that need one without going through a price table."""
    return pricing.Rates(1e-6, 1e-6, 1e-6, 1e-6, 1e-6, model=model, source=source).applied("2026-08-22T00:00:00+00:00")


def _metrics(
    result: RunResult,
    *,
    node: str = "n",
    verdict: str = "pass",
    wall_ms: int = 1,
    started_at: str = "t",
    cache: str = "/c",
) -> CellMetrics:
    """The record one graded cell emits, with the grading observations defaulted."""
    return CellMetrics.of(
        result,
        outcome=Outcome(node=node, verdict=verdict, wall_ms=wall_ms, started_at=started_at),
        cache=CacheLayout(Path(cache)),
    )


def test_bundled_table_prices_each_tier_separately() -> None:
    table = pricing.load_table()
    r = pricing.price(_result("claude-opus-5", Usage(1_000_000, 1_000_000, 1_000_000, 1_000_000)), table)
    assert r.cost_status is CostStatus.PRICED and r.cost_status == "priced"  # a StrEnum on the wire
    # An untagged cache write prices at the 5-minute rate.
    assert r.estimated_cost_usd == pytest.approx(5.0 + 25.0 + 0.5 + 6.25)
    # Provenance rides with the estimate (ADR 0021): the row, the file, the rates, the time.
    applied = r.rates_applied
    assert applied is not None
    assert applied.model == "claude-opus-5"
    assert applied.source.endswith("prices.toml")
    assert applied.cache_write_1h == 1.0e-5 and applied.applied_at.endswith("+00:00")
    assert r.cost_by_tier == {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.5,
        "cache_write_5m": 6.25,
        "cache_write_1h": 0.0,
    }


def test_cache_writes_price_by_ttl() -> None:
    """Claude Code writes 1-hour cache entries at 2x input; the log says so and the price follows (ADR 0019)."""
    table = pricing.load_table()
    one_hour = Usage(cache_write_tokens=1_000_000, cache_write_1h_tokens=1_000_000)
    assert pricing.price(_result("claude-opus-5", one_hour), table).estimated_cost_usd == pytest.approx(10.0)
    mixed = Usage(cache_write_tokens=1_000_000, cache_write_1h_tokens=400_000, cache_write_5m_tokens=100_000)
    r = pricing.price(_result("claude-opus-5", mixed), table)
    # 400k at 1h, 100k tagged 5m plus 500k untagged at the 5m rate.
    assert r.cost_by_tier["cache_write_1h"] == pytest.approx(4.0)
    assert r.cost_by_tier["cache_write_5m"] == pytest.approx(600_000 * 6.25e-6)
    # A row without cache_write_1h gets the Anthropic 2.0 / 1.25 ratio (per-MTok line -> per-token rate).
    table = pricing.load_table(rows=["m: input=1.0 output=1.0 cache_write=2.0"])
    assert table["m"].cache_write_1h == pytest.approx(3.2e-6)


def test_cache_reads_are_not_billed_at_the_input_rate() -> None:
    table = pricing.load_table()
    flat = pricing.price(_result("gpt-5.6-sol", Usage(input_tokens=200_000)), table).estimated_cost_usd
    tiered = pricing.price(
        _result("gpt-5.6-sol", Usage(input_tokens=30_000, cache_read_tokens=170_000)), table
    ).estimated_cost_usd
    assert flat is not None and tiered is not None
    assert tiered < flat / 3


def test_resolve_is_prefix_tolerant_both_ways() -> None:
    table = pricing.load_table()
    assert pricing.resolve("claude-opus-5[1m]", table) == table["claude-opus-5"]
    assert pricing.resolve("gpt-5.6", table) in (table["gpt-5.6-sol"], table["gpt-5.6-luna"])


def test_unknown_model_raises_rather_than_pricing_zero() -> None:
    table = pricing.load_table()
    with pytest.raises(pricing.PricingError, match="Refusing to price as zero"):
        pricing.resolve("mystery-model", table)
    with pytest.raises(pricing.PricingError, match=r"unpriced models in matrix: \['codex/mystery-model'\]"):
        pricing.validate_matrix(["claude/claude-opus-5", "codex/mystery-model"], table)


def test_price_lines_layer_on_top_of_the_bundled_table() -> None:
    """`xharness_prices` lines are USD per MTok in pytest's `name: text` idiom (ADR 0030)."""
    table = pricing.load_table(
        rows=["# a comment", "", "claude-opus-5: input=1.0 output=1.0", "new-model: input=2.0 output=3.0"]
    )
    # Cache tiers default to input; every row remembers its key and that the ini supplied it.
    assert table["claude-opus-5"] == pricing.Rates(
        1.0e-6, 1.0e-6, 1.0e-6, 1.0e-6, 1.6e-6, model="claude-opus-5", source="xharness_prices"
    )
    assert table["gpt-5.6-sol"].source == str(pricing.PRICES_PATH)  # bundled rows survive
    assert table["new-model"].output == 3.0e-6
    assert pricing.load_table(rows=[]) == pricing.load_table()


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ("claude-opus-5 input=1 output=1", "expected"),
        ("claude-opus-5:", "expected"),
        (": input=1 output=1", "expected"),
        ("m: input=1 output=1 turbo=9", "unknown tier"),
        ("m: input=one output=1", "not a number"),
        ("m: input=1 cache_read=2", r"missing required tier\(s\) \['output'\]"),
        ("m: input=5.0e-6 output=25", "looks like a per-token rate"),
        ("m: input=1 output=-3", "looks like a per-token rate"),
    ],
)
def test_malformed_price_lines_stop_before_any_spend(line: str, match: str) -> None:
    with pytest.raises(pricing.PricingError, match=match):
        pricing.parse_price_lines([line])


# -- runresult -----------------------------------------------------------------------


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
    priced = {"estimated_cost_usd", "cost_status", "cost_by_tier", "rates_applied"}
    attached = {"case", "skill_coverage"}
    supplied = _typed_dict_keys(runresult.RunResultFields)
    assert not supplied & (derived | priced | attached)
    assert supplied | derived | priced | attached == {f.name for f in dataclasses.fields(RunResult)}


def test_each_subagent_field_is_derived_from_the_ledger_or_named_by_the_transcript() -> None:
    """The same partition for a spawned thread: ``turns`` and ``usage`` are never supplied."""
    derived = {"turns", "usage", "calls"}
    supplied = _typed_dict_keys(runresult.SubagentFields)
    assert not supplied & derived
    assert supplied | derived == {f.name for f in dataclasses.fields(Subagent)}


# -- workspace -----------------------------------------------------------------------


def test_materialise_copies_fresh_and_rebuilds(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "a.md").write_text("seed", encoding="utf-8")
    workdir = tmp_path / "work"

    first = ws.materialise(fixture, "case/claude:opus", workdir)
    assert first == workdir / "case_claude_opus"
    (first / "leftover.txt").write_text("from a previous agent", encoding="utf-8")

    second = ws.materialise(fixture, "case/claude:opus", workdir)
    assert second == first
    assert sorted(p.name for p in second.iterdir()) == ["a.md"]


def test_materialise_requires_an_existing_fixture(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="fixture directory does not exist"):
        ws.materialise(tmp_path / "missing", "cell", tmp_path / "work")


def test_snapshot_diff_reports_created_and_modified_only(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("same", encoding="utf-8")
    (tmp_path / "edit.txt").write_text("v1", encoding="utf-8")
    before = ws.snapshot(tmp_path)
    (tmp_path / "edit.txt").write_text("v2", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "new.txt").write_text("n", encoding="utf-8")
    assert ws.diff(before, ws.snapshot(tmp_path)) == ["edit.txt", "sub/new.txt"]


# -- claude: log path correlation --------------------------------------------------------------


def test_claude_log_path_slugifies_every_non_alphanumeric_character(tmp_path: Path) -> None:
    workspace = tmp_path / "tmp" / "evals" / "eval_demo-claude-claude-opus-5"
    workspace.mkdir(parents=True)
    path = claude_harness.claude_log_path(Path("/cfg"), workspace, "abc-123")
    slug = path.parent.name
    assert path.parent.parent == Path("/cfg/projects")
    assert path.name == "abc-123.jsonl"
    assert "_" not in slug and "/" not in slug and "." not in slug
    assert slug.endswith("eval-demo-claude-claude-opus-5")


# -- normalise -----------------------------------------------------------------------


def _jsonl(path: Path, records: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n\nnot json\n", encoding="utf-8")
    return path


def test_from_claude_builds_one_call_per_message_id_and_keeps_the_envelope_for_reconciliation(
    tmp_path: Path,
) -> None:
    usage1 = {
        "input_tokens": 5,
        "output_tokens": 7,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 200,
        "cache_creation": {"ephemeral_1h_input_tokens": 200, "ephemeral_5m_input_tokens": 0},
        "output_tokens_details": {"thinking_tokens": 3},
    }
    msg = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": usage1,
        "stop_reason": "tool_use",
        "content": [
            {"type": "thinking", "thinking": "plan the edit"},
            {"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": "/w/ARCHITECTURE.md"}},
            {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/w/b.md"}},
            {"type": "text", "text": "editing"},
        ],
    }
    # Claude writes one record per content block; both records share id m1 and its usage.
    second_block = {
        **msg,
        "content": [{"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ls\n-la"}}],
    }
    tool_results = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "x" * 500},
                {"type": "tool_result", "tool_use_id": "t3", "content": [{"type": "text", "text": "ok"}]},
            ]
        },
    }
    usage2 = {
        "input_tokens": 2,
        "output_tokens": 40,
        "cache_read_input_tokens": 1205,
        "cache_creation_input_tokens": 90,
    }
    final = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": usage2,
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "done"}],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"content": "the prompt"}},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:01Z", "message": msg},
            {"type": "assistant", "timestamp": "2026-08-22T00:00:01Z", "message": second_block},
            tool_results,
            {"type": "assistant", "timestamp": "2026-08-22T00:00:09Z", "message": final},
        ],
    )
    envelope = {
        "session_id": "sid",
        "is_error": False,
        "duration_ms": 1234,
        "num_turns": 4,
        "result": "done",
        "total_cost_usd": 0.42,
        "usage": {
            "input_tokens": 7,
            "output_tokens": 47,
            "cache_read_input_tokens": 2205,
            "cache_creation_input_tokens": 290,
        },
    }
    r = claude_harness.ClaudeSessionLog(log, envelope).to_result(tmp_path, ["ARCHITECTURE.md"])
    assert (r.harness, r.model, r.session_id, r.exit_code, r.final_text) == (
        "claude",
        "claude-opus-5",
        "sid",
        0,
        "done",
    )
    # A turn is one model call (ADR 0019); the envelope's figure is kept beside it.
    assert (r.turns, r.reported_turns) == (2, 4)
    assert r.usage == Usage(7, 47, 2205, 290, reasoning_tokens=3, cache_write_1h_tokens=200)  # usage summed once per id
    assert r.reported_usage == envelope["usage"]
    assert r.reported_model_usage == {} and "result" not in r.envelope and r.envelope["num_turns"] == 4
    assert r.tool_calls == {"Edit": 2, "Bash": 1}  # tools counted across every record
    assert r.harness_reported_cost_usd == 0.42 and r.estimated_cost_usd is None
    assert r.files_written == ["ARCHITECTURE.md"]

    first, second = r.calls
    assert (first.n, first.at, first.stop_reason, first.text) == (1, "2026-08-22T00:00:01Z", "tool_use", "editing")
    assert first.thinking == "plan the edit"
    assert (first.context_tokens, first.results_in) == (1205, [])
    assert [(t.name, t.summary) for t in first.tools] == [
        ("Edit", "/w/ARCHITECTURE.md"),
        ("Edit", "/w/b.md"),
        ("Bash", "ls"),
    ]
    assert first.tools[2].input == {"command": "ls\n-la"}  # the whole argument payload, not the summary
    # Results that arrived between the two calls enter the second call's context, paired to their tool,
    # and are stored whole (ADR 0021: the ledger cuts nothing).
    assert [(x.tool, x.chars, len(x.content)) for x in second.results_in] == [("Edit", 500, 500), ("Bash", 2, 2)]
    assert (second.context_tokens, second.stop_reason, second.tools) == (1297, "end_turn", [])
    assert r.baseline_tokens == 1205
    # Each turn knows the log lines it was built from (ADR 0023): the prompt, both blocks of m1 and the
    # results of m1's own tools belong to turn 1; m2's block is turn 2. Ranges are contiguous.
    assert (first.records, second.records) == ([1, 2, 3, 4], [5])


def test_from_claude_turn_boundaries_follow_tool_ownership_not_log_order(tmp_path: Path) -> None:
    """Results of a turn's early tools land between its later blocks; they still belong to that turn (ADR 0023)."""

    def use(mid: str, tid: str) -> dict[str, object]:
        return {
            "type": "assistant",
            "message": {
                "id": mid,
                "usage": {},
                "content": [{"type": "tool_use", "id": tid, "name": "Read", "input": {}}],
            },
        }

    def res(tid: str) -> dict[str, object]:
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}

    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"content": "prompt"}},  # 1 -> turn 1
            use("m1", "a"),  # 2
            use("m1", "b"),  # 3
            res("a"),  # 4: result of m1's first tool, written before m1's third block
            use("m1", "c"),  # 5
            {
                "type": "attachment",
                "attachment": {"type": "total_tokens_reminder"},
            },  # 6: harness record, turn in progress
            res("b"),  # 7
            res("c"),  # 8
            use("m2", "d"),  # 9 -> turn 2
            res("d"),  # 10
            {"type": "ai-title"},  # 11 -> still turn 2
        ],
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid"}).to_result(tmp_path, [])
    assert r.turns == 2
    assert (r.calls[0].records, r.calls[1].records) == ([1, 2, 3, 4, 5, 6, 7, 8], [9, 10, 11])
    # results_in keeps its own meaning: what entered turn 2's context is turn 1's results.
    assert [x.tool for x in r.calls[1].results_in] == ["Read", "Read", "Read"]


def test_from_claude_context_window_latency_and_ttft(tmp_path: Path) -> None:
    """Window from modelUsage, TTFT and API time from the envelope, per-turn latency from timestamps (ADR 0024)."""
    m1 = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 2, "cache_read_input_tokens": 20_000, "output_tokens": 300},
        "content": [],
    }
    m2 = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": {
            "input_tokens": 2,
            "cache_read_input_tokens": 24_000,
            "cache_write_input_tokens": 0,
            "output_tokens": 100,
        },
        "content": [],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "timestamp": "2026-08-23T00:00:00.000Z", "message": {"content": "go"}},
            {"type": "assistant", "timestamp": "2026-08-23T00:00:03.500Z", "message": m1},
            {
                "type": "user",
                "timestamp": "2026-08-23T00:00:04.000Z",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]},
            },
            {"type": "assistant", "timestamp": "2026-08-23T00:00:06.000Z", "message": m2},
        ],
    )
    envelope = {
        "session_id": "sid",
        "ttft_ms": 1991,
        "duration_api_ms": 8000,
        "duration_ms": 9000,
        "modelUsage": {
            "claude-haiku-4-5-20251001": {"contextWindow": 200_000},
            "claude-opus-5": {"contextWindow": 1_000_000},
        },
    }
    r = claude_harness.ClaudeSessionLog(log, envelope).to_result(tmp_path, [])
    assert (r.context_window, r.ttft_ms, r.api_duration_ms) == (1_000_000, 1991, 8000)
    assert [c.latency_ms for c in r.calls] == [3500, 2000]
    assert [c.output_tokens_per_sec for c in r.calls] == [pytest.approx(85.71, abs=0.01), 50.0]
    assert (r.peak_context_tokens, r.final_context_tokens) == (24_002, 24_102)
    assert (r.context_window_pct, r.final_context_pct) == (2.4, 2.41)
    assert r.output_tokens_per_sec == 50.0  # 400 output tokens over 8 s of API time
    data = r.to_dict()
    assert [c["context_pct"] for c in data["calls"]] == [2.0, 2.4]
    assert data["context_window_pct"] == 2.4 and data["final_context_pct"] == 2.41


def test_from_codex_context_window_latency_and_ttft(tmp_path: Path) -> None:
    def count(at: str, inp: int, out: int) -> dict[str, object]:
        usage = {"input_tokens": inp, "cached_input_tokens": 0, "output_tokens": out, "reasoning_output_tokens": 0}
        info = {"last_token_usage": usage, "total_token_usage": usage, "model_context_window": 258_400}
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": info}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {
                "type": "event_msg",
                "timestamp": "2026-08-23T00:00:00.000Z",
                "payload": {"type": "task_started", "model_context_window": 258_400},
            },
            count("2026-08-23T00:00:02.000Z", 18_000, 100),
            count("2026-08-23T00:00:05.000Z", 20_000, 300),
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "duration_ms": 5000,
                    "time_to_first_token_ms": 1234,
                    "last_agent_message": "ok",
                },
            },
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.context_window, r.ttft_ms, r.api_duration_ms) == (258_400, 1234, 5000)
    assert [c.latency_ms for c in r.calls] == [2000, 3000]
    assert r.context_window_pct == pytest.approx(7.74) and r.final_context_pct == pytest.approx(7.86)
    assert r.output_tokens_per_sec == 80.0


def test_case_metadata_round_trips_and_reaches_history(tmp_path: Path) -> None:
    """The case that produced a run (suite, name, skill, fixture, prompt) rides on the result (ADR 0025)."""
    r = _result("m", Usage(1, 2, 3, 4))
    r.estimated_cost_usd = 0.1
    r.case = CaseRef(
        suite="skills/demo/evals/eval_demo.py", name="eval_demo", skill="demo", fixture="seed", prompt="say hi"
    )
    data = json.loads(r.write(tmp_path / "r.json").read_text(encoding="utf-8"))
    assert data["case"]["suite"] == "skills/demo/evals/eval_demo.py" and data["case"]["prompt"] == "say hi"
    rec = _metrics(r).to_dict()
    assert (rec["suite"], rec["case"], rec["skill"], rec["fixture"]) == (
        "skills/demo/evals/eval_demo.py",
        "eval_demo",
        "demo",
        "seed",
    )
    assert "prompt" not in rec  # the prompt lives on the result, not on every history line


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


def test_from_claude_keeps_synthetic_messages_as_evidence_not_turns(tmp_path: Path) -> None:
    """Claude Code writes ``model: "<synthetic>"`` notices (API errors) into the log; no model call happened."""
    real = {"id": "m1", "model": "claude-opus-5", "usage": {"input_tokens": 3, "output_tokens": 4}, "content": []}
    synthetic = {
        "id": "s1",
        "model": "<synthetic>",
        "stop_reason": "stop_sequence",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "content": [{"type": "text", "text": "API Error: The response stopped arriving."}],
    }
    log = _jsonl(
        tmp_path / "s.jsonl",
        [{"type": "assistant", "message": real}, {"type": "assistant", "message": synthetic}],
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid"}).to_result(tmp_path, [])
    assert (r.model, r.turns) == ("claude-opus-5", 1)  # the synthetic record names no model and is no turn
    assert r.calls[0].records == [1, 2]  # but its line stays attributed as evidence
    assert r.record_kinds == {"claude/assistant/synthetic": 1, "claude/assistant/text": 1}
    assert records.category_of("claude/assistant/synthetic") == "harness_meta"


def test_from_claude_without_envelope_usage_still_sums_the_ledger(tmp_path: Path) -> None:
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "assistant", "message": {"usage": {"input_tokens": 5, "output_tokens": 7}}},
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "output_tokens": 1}}},
        ],
    )
    r = claude_harness.ClaudeSessionLog(log, {"is_error": True, "model": "claude-sonnet-5"}).to_result(tmp_path, [])
    assert (r.exit_code, r.turns, r.reported_turns, r.model) == (1, 2, None, "claude-sonnet-5")
    assert r.usage == Usage(6, 8)
    assert r.reported_usage == {}


def test_from_codex_builds_one_call_per_token_count(tmp_path: Path) -> None:
    """Outputs recorded before a count belong to the next call's context; calls before it are that call's."""

    def count(last: dict[str, int], total: dict[str, int]) -> dict[str, object]:
        info = {"last_token_usage": last, "total_token_usage": total}
        return {"type": "event_msg", "timestamp": "t", "payload": {"type": "token_count", "info": info}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            {"type": "response_item", "payload": {"type": "reasoning"}},
            {
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": "pwd\nls"},
            },
            {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "/w"}},
            count(
                {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 10, "reasoning_output_tokens": 9},
                {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 10, "reasoning_output_tokens": 9},
            ),
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "CommandExecution"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "FileChange"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "AgentMessage"}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {}}},  # no totals: ignored
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
            },
            count(
                {"input_tokens": 4000, "cached_input_tokens": 3200, "output_tokens": 50, "reasoning_output_tokens": 0},
                {"input_tokens": 5000, "cached_input_tokens": 4000, "output_tokens": 60, "reasoning_output_tokens": 9},
            ),
            {"type": "event_msg", "payload": {"type": "task_complete", "duration_ms": 321, "last_agent_message": "ok"}},
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.harness, r.model, r.session_id, r.duration_ms, r.final_text) == (
        "codex",
        "gpt-5.6-sol",
        "01a0",
        321,
        "ok",
    )
    assert (r.turns, r.reported_turns) == (2, 1)  # two model calls; one codex exec task
    assert r.usage == Usage(input_tokens=1000, output_tokens=60, cache_read_tokens=4000, reasoning_tokens=9)
    assert r.usage.accumulative_billed_tokens == 5060
    assert r.reported_usage == {
        "input_tokens": 5000,
        "cached_input_tokens": 4000,
        "output_tokens": 60,
        "reasoning_output_tokens": 9,
    }
    assert r.tool_calls == {"CommandExecution": 1, "FileChange": 1}
    assert r.harness_reported_cost_usd is None

    first, second = r.calls
    assert (first.context_tokens, first.usage.input_tokens, first.usage.cache_read_tokens) == (1000, 200, 800)
    assert [(t.name, t.summary, t.input) for t in first.tools] == [("exec", "pwd", "pwd\nls")]
    assert first.results_in == [] and first.stop_reason == "tool_use"
    assert [(x.tool, x.chars, x.content) for x in second.results_in] == [("exec", 2, "/w")]
    assert (second.text, second.stop_reason, second.tools) == ("ok", "end_turn", [])
    assert r.baseline_tokens == 1000
    # Every log line lands on exactly one turn; the trailing task_complete goes to the last.
    assert (first.records, second.records) == ([1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13])


def test_from_codex_diffs_cumulative_counts_when_last_usage_is_absent(tmp_path: Path) -> None:
    def count(total: int, cached: int, out: int) -> dict[str, object]:
        usage = {
            "input_tokens": total,
            "cached_input_tokens": cached,
            "output_tokens": out,
            "reasoning_output_tokens": 9,
        }
        return {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": usage}}}

    log = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count(1000, 800, 10),
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "CommandExecution"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "FileChange"}}},
            {"type": "event_msg", "payload": {"type": "item_completed", "item": {"item_type": "AgentMessage"}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {}}},  # no totals: ignored
            count(5000, 4000, 60),
            {"type": "event_msg", "payload": {"type": "task_complete", "duration_ms": 321, "last_agent_message": "ok"}},
        ],
    )
    r = codex_harness.CodexSessionLog(log, 0).to_result(tmp_path, [])
    assert (r.harness, r.model, r.session_id, r.turns, r.reported_turns, r.duration_ms, r.final_text) == (
        "codex",
        "gpt-5.6-sol",
        "01a0",
        2,
        1,
        321,
        "ok",
    )
    assert r.usage == Usage(input_tokens=1000, output_tokens=60, cache_read_tokens=4000, reasoning_tokens=9)
    assert r.usage.accumulative_billed_tokens == 5060
    assert [c.context_tokens for c in r.calls] == [1000, 4000]
    assert r.tool_calls == {"CommandExecution": 1, "FileChange": 1}
    assert r.harness_reported_cost_usd is None


def test_from_claude_folds_subagent_transcripts_and_bills_them(tmp_path: Path) -> None:
    """A captured session dir's ``subagents/`` transcripts become Subagent ledgers: the
    spawning turn is matched by the sidecar's ``toolUseId``, and their usage folds into
    the run's billed total (a spawned thread's tokens are real spend)."""
    spawn = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100},
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_agent", "name": "Agent", "input": {"prompt": "research"}}],
    }
    final = {
        "id": "m2",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 2, "output_tokens": 8, "cache_read_input_tokens": 120},
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "done"}],
    }
    log = _jsonl(
        tmp_path / "log.jsonl",
        [
            {"type": "user", "message": {"content": "go"}},
            {"type": "assistant", "timestamp": "2026-08-28T00:00:01Z", "message": spawn},
            {"type": "assistant", "timestamp": "2026-08-28T00:00:09Z", "message": final},
        ],
    )
    sub_dir = tmp_path / "subagents"
    _jsonl(
        sub_dir / "agent-abc123.jsonl",
        [
            {"type": "user", "isSidechain": True, "agentId": "abc123", "message": {"content": "research"}},
            {
                "type": "assistant",
                "isSidechain": True,
                "agentId": "abc123",
                "timestamp": "2026-08-28T00:00:03Z",
                "message": {
                    "id": "s1",
                    "model": "claude-opus-5",
                    "usage": {"input_tokens": 30, "output_tokens": 20, "cache_read_input_tokens": 400},
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "found it"}],
                },
            },
        ],
    )
    (sub_dir / "agent-abc123.meta.json").write_text(
        json.dumps({"agentType": "general-purpose", "description": "External research", "toolUseId": "tu_agent"}),
        encoding="utf-8",
    )
    r = claude_harness.ClaudeSessionLog(log, {"session_id": "sid", "result": "done"}).to_result(tmp_path, [])
    assert r.calls[0].tools[0].id == "tu_agent"
    (sub,) = r.subagents
    assert (sub.agent, sub.id, sub.description, sub.parent_turn, sub.turns) == (
        "general-purpose",
        "abc123",
        "External research",
        1,
        1,
    )
    assert sub.log == str(sub_dir / "agent-abc123.jsonl")
    assert sub.usage == Usage(input_tokens=30, output_tokens=20, cache_read_tokens=400)
    # The run's usage is primary (12, 13, 220) plus the subagent: the whole bill.
    assert r.usage == Usage(input_tokens=42, output_tokens=33, cache_read_tokens=620)
    assert r.turns == 2  # turns stay the primary thread's own


def test_from_codex_folds_forked_rollouts_and_attributes_the_spawning_turn(tmp_path: Path) -> None:
    """Forked rollouts become Subagent ledgers named by ``agent_nickname``; the parent turn
    is the first primary call measured at or after the fork's ``session_meta`` timestamp."""

    def count(at: str, last: dict[str, int]) -> dict[str, object]:
        info = {"last_token_usage": last, "total_token_usage": last}
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "token_count", "info": info}}

    _jsonl(
        tmp_path / "log.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "01a0-primary"}},
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count("2026-08-28T00:00:05Z", {"input_tokens": 100, "output_tokens": 10}),
            count("2026-08-28T00:00:20Z", {"input_tokens": 200, "output_tokens": 20}),
        ],
    )
    sub = _jsonl(
        tmp_path / "subagents" / "rollout-sub.jsonl",
        [
            {
                "type": "session_meta",
                "timestamp": "2026-08-28T00:00:07Z",  # after t1's count: turn 2 spawned it
                "payload": {
                    "id": "01a0-sub",
                    "forked_from_id": "01a0-primary",
                    "source": {"subagent": {"thread_spawn": {"agent_nickname": "Curie", "depth": 1}}},
                    "agent_nickname": "Curie",
                    "agent_path": "/root/external_research",
                },
            },
            {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            count("2026-08-28T00:00:12Z", {"input_tokens": 50, "cached_input_tokens": 40, "output_tokens": 5}),
        ],
    )
    # sub_rollouts=None discovers the captured layout: <session dir>/subagents/*.jsonl
    r = codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0).to_result(tmp_path, [])
    (agent,) = r.subagents
    assert (agent.agent, agent.id, agent.description, agent.parent_turn, agent.turns) == (
        "Curie",
        "01a0-sub",
        "/root/external_research",
        2,
        1,
    )
    assert agent.log == str(sub)
    assert agent.usage == Usage(input_tokens=10, output_tokens=5, cache_read_tokens=40)
    assert r.usage == Usage(input_tokens=310, output_tokens=35, cache_read_tokens=40)
    assert r.turns == 2
    # The runner path passes the forks explicitly; the ledger is identical either way.
    explicit = codex_harness.CodexSessionLog(tmp_path / "log.jsonl", 0, sub_rollouts=[sub]).to_result(tmp_path, [])
    assert explicit.subagents[0].usage == agent.usage


# -- history -------------------------------------------------------------------------


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
    assert rec["rates_applied"]["model"] == "m" and rec["rates_applied"]["source"] == "/p/prices.toml"
    assert set(rec["rates_applied"]) == {
        "input",
        "output",
        "cache_read",
        "cache_write",
        "cache_write_1h",
        "model",
        "source",
        "applied_at",
    }
    assert rec["files_written"] == 2
    assert (
        cell.status_word() == "est $0.5000  100 accumulative_billed_tokens  40 baseline_tokens  5.0s  7 turns  5 tools"
    )
    reported = dataclasses.replace(cell, harness_reported_cost_usd=0.6)
    assert reported.status_word().startswith("est $0.5000 (harness $0.6000)  100 accumulative_billed_tokens")


# -- records (ADR 0022) -----------------------------------------------------------------


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


# -- skill coverage (ADR 0022) ----------------------------------------------------------


def test_a_coverage_row_widens_the_catalogued_file_by_exactly_the_two_access_lists() -> None:
    """``FileCoverage`` is a ``SkillFile`` plus the turns that touched it (ADR 0035).

    The same silent-drift hole this closes for ``RunResult`` and ``Subagent`` above: the
    wire format is one flat row per file, so the row *widens* the catalogued record
    rather than nesting it, and a field added to ``SkillFile`` alone would disappear from
    every annotated row and from ``result.json``'s ``skill_coverage.files`` with nothing
    failing. ``FileCoverage.of`` spreads the record, which turns the omission into a
    ``TypeError``; this pins the other half — that the row adds the two access lists and
    nothing else, so ``touch`` has a list for every :class:`Access` member.
    """
    catalogued = {f.name for f in dataclasses.fields(skillcov.SkillFile)}
    row = {f.name for f in dataclasses.fields(skillcov.FileCoverage)}
    assert catalogued <= row
    assert row - catalogued == {a.value for a in skillcov.Access} == {"loaded", "run"}


def _skill(tmp_path: Path) -> Path:
    skill = tmp_path / "demo"
    for rel, body in {
        "SKILL.md": "# demo",
        "resources/guide.md": "guide",
        "resources/unused.md": "never read",
        "scripts/check.ts": "console.log(1)",
        "scripts/never.py": "print(1)",
        "scripts/check.test.ts": "test",
        "scripts/package.json": "{}",
        "assets/icon.png": "png",
        "evals/eval_demo.py": "not part of the skill surface",
        "scripts/node_modules/x/index.js": "vendored",
        "scripts/__pycache__/a.pyc": "cache",
        ".hidden": "dotfile",
    }.items():
        (skill / rel).parent.mkdir(parents=True, exist_ok=True)
        (skill / rel).write_text(body, encoding="utf-8")
    return skill


@pytest.mark.parametrize(
    ("pattern", "matches", "misses"),
    [
        (
            "resources/examples/**",
            ["resources/examples/a.png", "resources/examples/sub/b.md"],
            ["resources/a.md", "examples/x"],
        ),
        ("scripts/{Makefile,CLAUDE.md}", ["scripts/Makefile", "scripts/CLAUDE.md"], ["scripts/README.md", "Makefile"]),
        ("scripts/*.json", ["scripts/package.json"], ["scripts/sub/x.json", "package.json"]),
        ("scripts/_*.py", ["scripts/_helper.py"], ["scripts/helper.py"]),
        ("scripts/*.test.ts", ["scripts/a.test.ts"], ["scripts/a.ts"]),
        ("scripts/bun*", ["scripts/bun.lock", "scripts/bunfig.toml"], ["scripts/sub/bun.lock"]),
        ("README.md", ["README.md", "resources/examples/README.md"], ["README.mdx", "docs/README"]),
        ("assets/", ["assets/icon.png", "assets/deep/x", "other/assets/x.png"], ["x/assetsy", "assetsx/y"]),
        ("# a comment", [], ["anything"]),
    ],
)
def test_skill_ignore_globs(pattern: str, matches: list[str], misses: list[str]) -> None:
    rules = ignorerules.IgnoreRules.compiled([pattern, ""])
    assert all(rules.matches(p) for p in matches), pattern
    assert not any(rules.matches(p) for p in misses), pattern


def test_catalog_applies_bare_and_skill_scoped_ignore_lines(tmp_path: Path) -> None:
    skill = _skill(tmp_path)  # its directory name is "demo"
    lines = [
        "# tests are not decision surface",
        "scripts/*.test.ts",
        "demo: assets/",
        "de*: scripts/package.json",
        "other-skill: SKILL.md",
        "",
    ]
    files = skillcov.catalog(skill, ignore=lines)
    ignored = {f.path for f in files if f.ignored}
    assert ignored == {"assets/icon.png", "scripts/check.test.ts", "scripts/package.json"}
    r = _result("m", Usage())
    cov = skillcov.annotate("demo", files, r)
    assert cov.summary.ignored == 3 and cov.summary.files == 5 and cov.summary.tests == 0
    assert "scripts/package.json" not in cov.not_loaded and "scripts/check.test.ts" not in cov.not_loaded


def test_a_skillignore_file_in_the_skill_is_not_read(tmp_path: Path) -> None:
    """ADR 0026: the ini key is the only source; a leftover dotfile is neither read nor catalogued."""
    skill = _skill(tmp_path)
    (skill / ".skillignore").write_text("assets/\n", encoding="utf-8")
    files = skillcov.catalog(skill)
    assert not any(f.ignored for f in files)
    assert ".skillignore" not in {f.path for f in files}


@pytest.mark.parametrize(
    ("line", "applies"),
    [
        ("README.md", True),
        ("mermaidjs-diagrams: README.md", True),
        ("mermaidjs-diagrams : README.md", True),
        ("*-diagrams: README.md", True),
        ("mermaidjs-diagrams: scripts/{Makefile,CLAUDE.md}", True),
        ("other: README.md", False),
        ("mermaid: README.md", False),  # an exact name, not a prefix
    ],
)
def test_patterns_for_selects_lines_by_skill_name(line: str, applies: bool) -> None:
    resolved = ignorerules.patterns_for("mermaidjs-diagrams", [line])
    assert resolved == ([line.partition(":")[2].strip() or line] if applies else [])


@pytest.mark.parametrize("line", ["mermaidjs-diagrams:", ": README.md", ":"])
def test_patterns_for_rejects_a_selector_without_a_pattern(line: str) -> None:
    with pytest.raises(ValueError, match="xharness_skill_ignore"):
        ignorerules.patterns_for("mermaidjs-diagrams", [line])


def test_catalog_lists_the_skill_surface_with_kinds_and_hashes(tmp_path: Path) -> None:
    files = skillcov.catalog(_skill(tmp_path))
    assert all(f.ignored is False for f in files)
    assert [(f.path, f.kind) for f in files] == [
        ("SKILL.md", "doc"),
        ("assets/icon.png", "asset"),
        ("resources/guide.md", "doc"),
        ("resources/unused.md", "doc"),
        ("scripts/check.test.ts", "test"),
        ("scripts/check.ts", "script"),
        ("scripts/never.py", "script"),
        ("scripts/package.json", "asset"),
    ]
    assert files[0].bytes == 6 and len(files[0].sha256) == 64


def test_annotate_marks_loaded_and_run_turns_and_derives_the_missed_sets(tmp_path: Path) -> None:
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage())
    r.calls = [
        Call(n=1, at="t", tools=[ToolCall("Skill", "demo", {"skill": "demo"})]),
        Call(n=2, at="t", tools=[ToolCall("Read", "", {"file_path": "/x/skills/demo/resources/guide.md"})]),
        Call(n=3, at="t", tools=[ToolCall("Bash", "", {"command": "cat /x/skills/demo/scripts/check.ts"})]),
        Call(
            n=4, at="t", tools=[ToolCall("Bash", "", {"command": "bun run /x/skills/demo/scripts/check.ts README.md"})]
        ),
        Call(
            n=5,
            at="t",
            tools=[
                ToolCall(
                    "exec",
                    "",
                    'await tools.exec_command({cmd: "sed -n 1,40p codex_home/skills/demo/resources/guide.md"})',
                )
            ],
        ),
        Call(n=6, at="t", tools=[ToolCall("Bash", "", {"command": "bun run /x/skills/demo/scripts/check.ts again"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert (by["SKILL.md"].loaded, by["SKILL.md"].run) == ([1], [])
    assert (by["resources/guide.md"].loaded, by["resources/guide.md"].run) == ([2, 5], [])
    # Turn 3 only read the script; turns 4 and 6 ran it (each turn counted once).
    assert (by["scripts/check.ts"].loaded, by["scripts/check.ts"].run) == ([3], [4, 6])
    assert cov.loaded == ["SKILL.md", "resources/guide.md", "scripts/check.ts"]
    assert cov.run == ["scripts/check.ts"]
    assert cov.not_loaded == [
        "assets/icon.png",
        "resources/unused.md",
        "scripts/check.test.ts",
        "scripts/never.py",
        "scripts/package.json",
    ]
    assert cov.not_run == ["scripts/never.py"]  # tests are never expected to run
    assert cov.summary == skillcov.CoverageSummary(
        files=8, ignored=0, docs=3, scripts=2, tests=1, assets=2, loaded=3, run=1
    )


# -- effective working directory (ADR 0027) -----------------------------------------


@pytest.mark.parametrize(
    ("cwd", "target", "expected"),
    [
        ("/ws", "/x/skills/demo", "/x/skills/demo"),
        ("/x/skills/demo", "scripts", "/x/skills/demo/scripts"),
        ("/x/skills/demo/scripts", "..", "/x/skills/demo"),
        ("/x/skills/demo", "'/x/ws'", "/x/ws"),
        ("/x/skills/demo", None, None),  # bare ``cd`` goes home
        ("/x/skills/demo", "~/else", None),
        ("/x/skills/demo", "$DIR", None),
        (None, "scripts", None),  # relative from an unknown place stays unknown
    ],
)
def test_chdir_follows_absolute_relative_and_unknowable_targets(
    cwd: str | None, target: str | None, expected: str | None
) -> None:
    assert skillcov._chdir(cwd, target) == expected


def test_skill_subdir_locates_the_skill_root_inside_a_cwd() -> None:
    assert skillcov.skill_subdir("/x/skills/demo", "demo") == ""
    assert skillcov.skill_subdir("/x/skills/demo/scripts", "demo") == "scripts"
    assert skillcov.skill_subdir("/home/demo/ws", "demo") == "ws"  # last occurrence wins
    assert skillcov.skill_subdir("/x/ws", "demo") is None
    assert skillcov.skill_subdir(None, "demo") is None


def test_resolve_command_qualifies_relative_paths_after_a_cd_and_leaves_the_rest_alone() -> None:
    text, after = skillcov.resolve_command(
        'cd /x/skills/demo && cat SKILL.md && bun run scripts/check.ts "$F" --preset low 2>&1 | head -c 300',
        "demo",
        "/x/ws",
    )
    assert after == "/x/skills/demo"
    assert "demo/SKILL.md" in text
    assert 'bun run demo/scripts/check.ts "$F" --preset low 2>&1' in text
    # Runs of spaces (empty tokens) and a segment of only whitespace are not a crash.
    text, _ = skillcov.resolve_command("cat  SKILL.md   ;  \n\n", "demo", "/x/skills/demo")
    assert "demo/SKILL.md" in text
    # Outside the skill nothing is rewritten, and a bare word is never a path.
    text, after = skillcov.resolve_command("cd /x/ws; cat README.md; echo done", "demo", "/x/skills/demo")
    assert after == "/x/ws"
    assert "demo/README.md" not in text
    # Already-qualified, absolute, quoted and ./-prefixed forms resolve the same way.
    text, _ = skillcov.resolve_command(
        "./scripts/check.ts; cat '/abs/README.md'; ls demo/scripts/x.ts", "demo", "/x/skills/demo"
    )
    assert "demo/scripts/check.ts" in text
    assert "demo//abs" not in text
    assert "demo/demo/" not in text


def test_annotate_follows_the_claude_shells_cwd_and_the_harness_reset(tmp_path: Path) -> None:
    """Claude's Bash is one persistent shell, so a ``cd`` sticks until the harness resets it."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="claude")
    r.workspace = "/x/ws"
    r.calls = [
        # Turn 1: cd into the skill and read SKILL.md by its bare name (the Opus pattern).
        Call(n=1, at="t", tools=[ToolCall("Bash", "", {"command": "cd /x/skills/demo && cat SKILL.md"})]),
        # Turn 2: the shell is still in the skill; a relative run of the gate counts as run.
        Call(n=2, at="t", tools=[ToolCall("Bash", "", {"command": "bun run scripts/check.ts /x/ws/doc.md"})]),
        # Turn 3: a relative cd deeper, then the script by bare name, still run.
        Call(
            n=3,
            at="t",
            tools=[
                ToolCall("Bash", "", {"command": "cd scripts; bun run check.ts /x/ws/doc.md; echo exit=$?"}),
            ],
            results_in=[ToolResult("toolu_3", 40, "clean\nShell cwd was reset to /x/ws")],
        ),
        # Turn 4: the harness reset the shell to the workspace, so the same text no longer touches the skill.
        Call(n=4, at="t", tools=[ToolCall("Bash", "", {"command": "bun run check.ts /x/ws/doc.md; cat SKILL.md"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert (by["SKILL.md"].loaded, by["SKILL.md"].run) == ([1], [])
    assert (by["scripts/check.ts"].loaded, by["scripts/check.ts"].run) == ([], [2, 3])
    assert cov.run == ["scripts/check.ts"]


def test_annotate_resolves_each_codex_exec_at_its_own_workdir(tmp_path: Path) -> None:
    """Codex runs every exec in a fresh process, so a ``cd`` in one never reaches the next.

    The tool vocabulary is the harness's own (ADR 0034): ``exec`` is a shell for Codex and
    nothing at all for Claude, so this case cannot be expressed on the same run as the one
    above -- a result comes from exactly one harness.
    """
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="codex")
    r.workspace = "/x/ws"
    r.calls = [
        # Turn 1: the exec's own workdir is the skill, so a relative path resolves inside it.
        Call(
            n=1,
            at="t",
            tools=[
                ToolCall(
                    "exec",
                    "",
                    {"command": ["bash", "-lc", "cat resources/guide.md"], "workdir": "/x/skills/demo"},
                )
            ],
        ),
        # Turn 2 cds, but turn 3 starts again at its own workdir, so turn 3 never reaches the skill.
        Call(n=2, at="t", tools=[ToolCall("exec", "", {"command": "cd /x/skills/demo", "workdir": "/x/ws"})]),
        Call(n=3, at="t", tools=[ToolCall("exec", "", {"command": "cat resources/unused.md", "workdir": "/x/ws"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert by["resources/guide.md"].loaded == [1]
    assert by["resources/unused.md"].loaded == []
    assert cov.run == []


def test_codex_usage_splits_openai_inclusive_input_into_disjoint_tiers() -> None:
    """OpenAI's input_tokens contains cached and cache-written tokens; Anthropic's does not.

    The plugin keeps Anthropic's disjoint shape, so the tiers price once each and their
    sum is the prompt the call processed again (docs/token-accounting.md).
    """
    u = codex_harness._call_usage(
        {"input_tokens": 2600, "cached_input_tokens": 2000, "cache_write_input_tokens": 400, "output_tokens": 30}
    )
    assert (u.input_tokens, u.cache_read_tokens, u.cache_write_tokens) == (200, 2000, 400)
    assert u.input_tokens + u.cache_read_tokens + u.cache_write_tokens == 2600
    # A malformed count can never go negative.
    assert codex_harness._call_usage({"input_tokens": 10, "cached_input_tokens": 20}).input_tokens == 0


# -- codex: rollout selection ------------------------------------------------


def test_primary_rollout_skips_subagent_forks(tmp_path: Path) -> None:
    """A codex session that spawned subagents writes one rollout per thread; the primary is the log."""
    meta = {"timestamp": "t", "type": "session_meta", "payload": {"id": "p1", "source": "exec"}}
    sub = {
        "timestamp": "t",
        "type": "session_meta",
        "payload": {
            "id": "s1",
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": "p1", "depth": 1}}},
            "forked_from_id": "p1",
        },
    }
    primary = tmp_path / "rollout-1-p1.jsonl"
    primary.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (tmp_path / "rollout-2-s1.jsonl").write_text(json.dumps(sub) + "\n", encoding="utf-8")
    (tmp_path / "rollout-3-s2.jsonl").write_text(json.dumps(sub) + "\n", encoding="utf-8")
    assert codex_harness.primary_rollout(sorted(tmp_path.glob("rollout-*.jsonl"))) == primary
    # A lone primary still selects; two primaries or none is a hard failure, never a guess.
    assert codex_harness.primary_rollout([primary]) == primary
    second = tmp_path / "rollout-4-p2.jsonl"
    second.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    with pytest.raises(harnesses.RunError, match="found 2 of 4"):
        codex_harness.primary_rollout(sorted(tmp_path.glob("rollout-*.jsonl")))
    with pytest.raises(harnesses.RunError, match="found 0"):
        codex_harness.primary_rollout([tmp_path / "rollout-2-s1.jsonl"])


# -- the extension point (ADR 0034) ---------------------------------------------------


class _ProbeHarness(harnesses.Harness):
    """A third harness that exists only to prove one is reachable without editing anything.

    It deliberately cannot run: ADR 0002 forbids faking a CLI, its subprocess or its
    session log, and nothing here does. ``run`` and ``session_from_capture`` raise, and
    the test asserts they are never reached -- what is exercised is registration and
    dispatch, which is what a new provider actually has to plug into.
    """

    name = "probe"
    shell_tools = frozenset({"Terminal"})
    persistent_shells = frozenset({"Terminal"})

    def run(self, **kwargs: object) -> RunResult:  # type: ignore[override]
        raise NotImplementedError("the probe harness never invokes anything")

    def session_from_capture(self, session: SessionDir, stored: dict[str, Any]) -> Any:
        raise NotImplementedError("the probe harness has no dialect to replay")

    def classify_record(self, rec: dict[str, Any]) -> str:
        return f"probe/{rec.get('kind') or 'unknown'}"


@pytest.fixture
def probe_harness() -> Iterator[harnesses.Harness]:
    agent = harnesses.register(_ProbeHarness())
    try:
        yield agent
    finally:
        harnesses.unregister(agent.name)


def test_a_third_harness_needs_no_edit_outside_its_own_module(probe_harness: harnesses.Harness) -> None:
    """The operational claim ADR 0034 was made for, asserted rather than argued.

    Registering one class is the whole job: the matrix knows it, its records classify as
    its own, its census counts them, and coverage attribution uses *its* shell vocabulary
    -- with no branch on the name anywhere between here and those call sites.
    """
    assert "probe" in mx.known_harnesses()
    assert mx.expand(["probe/some-model"]) == [Cell(harness="probe", model="some-model")]

    # Classification is the harness's own, not a fall-through to Codex.
    assert probe_harness.classify({"kind": "widget"}) == "probe/widget"
    assert probe_harness.classify("not a record") == "probe/unknown"  # type: ignore[arg-type]
    assert probe_harness.census([{"kind": "widget"}, {"kind": "widget"}, {}]) == {
        "probe/unknown": 1,
        "probe/widget": 2,
    }


def test_coverage_uses_the_new_harnesss_own_shell_vocabulary(tmp_path: Path, probe_harness: harnesses.Harness) -> None:
    """``Terminal`` is a shell for this harness and for no other; nothing had to learn the name."""
    files = skillcov.catalog(_skill(tmp_path))
    r = _result("m", Usage(), harness="probe")
    r.workspace = "/x/ws"
    r.calls = [
        Call(n=1, at="t", tools=[ToolCall("Terminal", "", {"command": "cd /x/skills/demo && cat SKILL.md"})]),
        # The cwd persisted, because this harness says its Terminal is persistent.
        Call(n=2, at="t", tools=[ToolCall("Terminal", "", {"command": "bun run scripts/check.ts"})]),
    ]
    cov = skillcov.annotate("demo", files, r)
    by = {f.path: f for f in cov.files}
    assert by["SKILL.md"].loaded == [1]
    assert by["scripts/check.ts"].run == [2]


# -- pipeline: the sequence both the live cell and a replay run ------------------------


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
            verdict="pass",
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
        evalcase(prompt="go", skill="demo", fixture="seed")(lambda result, workspace: None),
        "skills/demo/evals/eval_x.py",
    )
    out = pipeline.derive(r, table=pricing.load_table(), skill="demo", skill_files=files, case=case)
    assert out is r
    assert r.cost_status is CostStatus.PRICED and r.estimated_cost_usd == pytest.approx(5.0)
    assert r.skill_coverage is not None and r.skill_coverage.loaded == ["SKILL.md"]
    assert r.case == CaseRef(
        suite="skills/demo/evals/eval_x.py", name="<lambda>", skill="demo", fixture="seed", prompt="go"
    )


# -- replay (ADR 0023) --------------------------------------------------------------


def test_replay_rebuilds_results_history_and_report_from_cached_logs(tmp_path: Path) -> None:
    skill = _skill(tmp_path)  # tmp_path/demo
    # The project's pytest config: rootdir discovery anchors here, and the skills root is tmp_path itself.
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\nxharness_skills_dir = "."\n', encoding="utf-8")
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260822T000000Z" / "sid1"
    session_dir.mkdir(parents=True)
    msg = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 5, "output_tokens": 7, "cache_read_input_tokens": 100},
        "content": [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "Read",
                "input": {"file_path": "/x/skills/demo/resources/guide.md"},
            }
        ],
    }
    _jsonl(
        session_dir / "log.jsonl",
        [{"type": "user", "message": {"content": "go"}}, {"type": "assistant", "message": msg}],
    )
    # A stale result: old schema, wrong turn count, no ledger; only the envelope and identity matter.
    stale = {
        "harness": "claude",
        "model": "claude-opus-5",
        "session_id": "sid1",
        "workspace": "/w",
        "files_written": ["a.md"],
        "final_text": "done",
        "turns": 99,
        "envelope": {
            "session_id": "sid1",
            "num_turns": 2,
            "total_cost_usd": 0.5,
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
    }
    (session_dir / "result.json").write_text(json.dumps(stale), encoding="utf-8")
    # No `case` on the stale result: replay recovers it from the suite that defines eval_demo,
    # via the case name recorded on the session's own history.json (ADR 0032).
    (skill / "evals" / "eval_demo.py").write_text(
        'from pytest_xharness_eval import evalcase\n\n@evalcase(prompt="go", skill="demo", fixture="seed")\n'
        "def eval_demo(run, workspace):\n    pass\n",
        encoding="utf-8",
    )
    (session_dir / "history.json").write_text(
        json.dumps(
            {
                "session_id": "sid1",
                "case": "eval_demo",
                "verdict": "pass",
                "at": "2026-08-22T00:00:00+00:00",
                "node": "n",
                "wall_ms": 1234,
                "turns": 99,
            }
        ),
        encoding="utf-8",
    )

    rewritten = replay.rebuild(cache)
    assert rewritten == [session_dir / "result.json"]
    fresh = json.loads((session_dir / "result.json").read_text(encoding="utf-8"))
    assert (fresh["turns"], fresh["harness_reported_cost_usd"], fresh["final_text"], fresh["files_written"]) == (
        1,
        0.5,
        "done",
        ["a.md"],
    )
    assert fresh["estimated_cost_usd"] > 0 and fresh["rates_applied"]["model"] == "claude-opus-5"
    assert fresh["skill_coverage"]["skill"] == "demo" and fresh["skill_coverage"]["loaded"] == ["resources/guide.md"]
    assert fresh["calls"][0]["records"] == [1, 2]
    # Recovered from the suite under the skills root, since the log does not know which case produced it.
    assert fresh["case"]["suite"].endswith("evals/eval_demo.py")
    assert (fresh["case"]["name"], fresh["case"]["skill"], fresh["case"]["fixture"], fresh["case"]["prompt"]) == (
        "eval_demo",
        "demo",
        "seed",
        "go",
    )
    # The combine step (ADR 0032): one index and one aggregated history under report/.
    index = json.loads((cache / "report" / "index.json").read_text(encoding="utf-8"))
    row = index["cells"][0]
    assert row["suite"].endswith("evals/eval_demo.py") and row["prompt"] == "go"
    assert row["run"] == "20260822T000000Z"
    assert row["result"] == "../results/demo/claude/claude-opus-5/20260822T000000Z/sid1/result.json"
    assert row["log"] == "../results/demo/claude/claude-opus-5/20260822T000000Z/sid1/log.jsonl"
    mine = json.loads((session_dir / "history.json").read_text(encoding="utf-8"))
    assert (mine["turns"], mine["verdict"], mine["at"], mine["wall_ms"], mine["node"]) == (
        1,
        "pass",
        "2026-08-22T00:00:00+00:00",
        1234,
        "n",
    )
    assert mine["skill_files_loaded"] == 1 and mine["cache"] == str(cache)
    aggregated = [
        json.loads(raw) for raw in (cache / "report" / "history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [rec["session_id"] for rec in aggregated] == ["sid1"]
    assert (cache / "report" / "report.html").is_file()


def test_replay_migrates_a_legacy_captured_directory(tmp_path: Path) -> None:
    """ADR 0032: pointed at a pre-cache captured/ dir, replay copies it into results/ and leaves it be."""
    skill = _skill(tmp_path / "skills")  # skills/demo
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    captured = skill / "evals" / "captured"
    case = captured / "eval_demo"
    case.mkdir(parents=True)
    (case / "claude-sid1.jsonl").write_text('{"type": "user", "message": {"content": "go"}}\n', encoding="utf-8")
    (case / "claude-sid1.result.json").write_text(
        json.dumps({"harness": "claude", "model": "claude-opus-5", "session_id": "sid1"}), encoding="utf-8"
    )
    # A pre-0032 line, with the ``captured`` key this version no longer carries.
    (captured / "history.jsonl").write_text(
        json.dumps(
            {
                "session_id": "sid1",
                "case": "eval_demo",
                "verdict": "pass",
                "at": "2026-08-22T00:00:00+00:00",
                "node": "n",
                "wall_ms": 1,
                "captured": str(captured),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # A second session whose record has a null timestamp: the run directory is stamped from
    # ``at``, so it falls back to the zero stamp rather than raising (ADR 0038).
    (case / "claude-sid2.result.json").write_text(
        json.dumps({"harness": "claude", "model": "claude-opus-5", "session_id": "sid2"}), encoding="utf-8"
    )
    with (captured / "history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"session_id": "sid2", "verdict": "pass", "at": None}) + "\n")

    cache = tmp_path / ".xharness_eval_cache"
    assert replay.migrate_legacy(captured, cache) == 2
    assert (cache / "results" / "demo" / "claude" / "claude-opus-5" / "00000000T000000Z" / "sid2").is_dir()
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260822T000000Z" / "sid1"
    assert (session_dir / "result.json").is_file() and (session_dir / "log.jsonl").is_file()
    hist = json.loads((session_dir / "history.json").read_text(encoding="utf-8"))
    # The record is migrated to the current shape, not copied verbatim: it names its new
    # cache root, the pre-0032 ``captured`` key is gone, and today's fields are present.
    assert hist["cache"] == str(cache) and "captured" not in hist
    assert (hist["case"], hist["verdict"], hist["node"]) == ("eval_demo", "pass", "n")
    assert hist["accumulative_billed_tokens"] == 0
    # The original evidence is untouched, and a second migration is a no-op.
    assert (case / "claude-sid1.result.json").is_file() and (captured / "history.jsonl").is_file()
    assert replay.migrate_legacy(captured, cache) == 0
    assert replay.is_legacy_captured(captured) and not replay.is_legacy_captured(cache)


@pytest.mark.parametrize(
    ("name", "body"),
    [
        (
            "pyproject.toml",
            '[tool.pytest.ini_options]\nxharness_skill_ignore = ["README.md", "demo: assets/"]\n',
        ),
        ("pytest.ini", "[pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
        ("tox.ini", "[pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
        ("setup.cfg", "[tool:pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
    ],
)
def test_settings_read_skill_ignore_from_the_projects_pytest_config(tmp_path: Path, name: str, body: str) -> None:
    captured = tmp_path / "skills" / "demo" / "evals" / "captured"
    captured.mkdir(parents=True)
    (tmp_path / name).write_text(body, encoding="utf-8")
    assert settings.ini_lines(captured, "xharness_skill_ignore") == ["README.md", "demo: assets/"]


def test_settings_ignore_a_pyproject_without_pytest_options_and_a_missing_config(tmp_path: Path) -> None:
    captured = tmp_path / "skills" / "demo" / "evals" / "captured"
    captured.mkdir(parents=True)
    assert settings.ini_lines(captured, "xharness_skill_ignore") == []
    (tmp_path / "skills" / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nxharness_skill_ignore = ["assets/"]\n', encoding="utf-8"
    )
    assert settings.ini_lines(captured, "xharness_skill_ignore") == [
        "assets/"
    ]  # the nearer pyproject is not pytest's config file


def test_replay_refuses_a_result_without_its_log(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "m" / "20260101T000000Z" / "x"
    session_dir.mkdir(parents=True)
    (session_dir / "result.json").write_text('{"harness": "claude", "session_id": "x"}', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="no captured session log"):
        replay.rebuild(cache)


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


# -- report ---------------------------------------------------------------------------


def test_report_indexes_every_captured_result_and_writes_the_page(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    claude_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260822T010000Z" / "9f5f73a0"
    new = _result("claude-opus-5", Usage(26, 5289, 492_998, 28_154, cache_write_1h_tokens=28_154))
    new.harness, new.session_id, new.turns = "claude", "9f5f73a0", 13
    new.harness_reported_cost_usd, new.estimated_cost_usd = 0.66, 0.55
    new.rates_applied = _applied_rates(model="claude-opus-5")
    new.case = CaseRef(name="eval_demo", skill="demo")
    new.calls = [
        Call(n=1, at="t", usage=Usage(input_tokens=2, cache_read_tokens=22_954), tools=[ToolCall("Bash", "ls")])
    ]
    new.write(claude_dir / "result.json")
    (claude_dir / "log.jsonl").write_text("{}\n", encoding="utf-8")
    (claude_dir / "history.json").write_text(
        json.dumps(
            {
                "session_id": "9f5f73a0",
                "verdict": "pass",
                "at": "2026-08-22T01:00:00+00:00",
                "node": "n",
                "wall_ms": 87_070,
            }
        ),
        encoding="utf-8",
    )
    # A result written before ADR 0019: no calls, no history record, no log, no case meta.
    codex_dir = cache / "results" / "demo" / "codex" / "gpt-5.6-sol" / "20260821T000000Z" / "01a022dc"
    old = _result("gpt-5.6-sol", Usage(100, 10, 0, 0))
    old.harness, old.session_id = "codex", "01a022dc"
    old.write(codex_dir / "result.json")

    page = report.write(CacheLayout(cache))
    assert page == cache / "report" / "report.html"
    html = page.read_text(encoding="utf-8")
    assert "index.json" in html and "window.__XH_DATA__ = " not in html and report.INLINE_MARKER not in html
    report_dir = cache / "report"
    assert "# xharness report glossary" in (report_dir / "XHARNESS-REPORT-GLOSSARY.md").read_text(encoding="utf-8")
    # The bundled design tokens land beside the page so they can be edited in place (ADR 0024).
    tokens = json.loads((report_dir / "report.tokens.json").read_text(encoding="utf-8"))
    assert set(tokens["themes"]) == {"light", "dark"} and tokens["categories"]["prompt"] == "#1d4ed8"
    index = json.loads((report_dir / "index.json").read_text(encoding="utf-8"))
    assert index["captured"] == str(cache)
    # The aggregated history is the combine step's other output (ADR 0032).
    aggregated = [json.loads(raw) for raw in (report_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [rec["session_id"] for rec in aggregated] == ["9f5f73a0"]
    first, second = index["cells"]  # newest first; the one without history sorts last
    assert (first["case"], first["harness"], first["model"], first["session_id"]) == (
        "eval_demo",
        "claude",
        "claude-opus-5",
        "9f5f73a0",
    )
    assert (first["verdict"], first["at"], first["wall_ms"], first["node"]) == (
        "pass",
        "2026-08-22T01:00:00+00:00",
        87_070,
        "n",
    )
    assert (first["result"], first["log"]) == (
        "../results/demo/claude/claude-opus-5/20260822T010000Z/9f5f73a0/result.json",
        "../results/demo/claude/claude-opus-5/20260822T010000Z/9f5f73a0/log.jsonl",
    )
    assert first["run"] == "20260822T010000Z" and second["case"] == "(unknown case)"
    assert (first["estimated_cost_usd"], first["harness_reported_cost_usd"], first["turns"]) == (0.55, 0.66, 13)
    assert first["rates_applied"]["source"] == "/p/prices.toml"
    assert (first["accumulative_billed_tokens"], first["baseline_tokens"]) == (526_467, 22_956)
    # The billed sum and the peak prompt are different quantities; the row carries both so the
    # page never has to pair accumulative_billed_tokens with a context percentage.
    assert first["peak_context_tokens"] == 22_956 and "peak_context_tokens" in html
    assert "context_tokens" not in first and "billed_tokens" not in first
    assert first["has_ledger"] is True
    assert (second["session_id"], second["verdict"], second["log"], second["has_ledger"]) == (
        "01a022dc",
        None,
        None,
        False,
    )
    hint = report.serve_hint(CacheLayout(cache))
    assert "report/report.html" in hint and str(cache) in hint


def test_report_inline_embeds_data_and_user_design_tokens(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20260101T000000Z" / "sid1"
    session_dir.mkdir(parents=True)
    r = _result("claude-opus-5", Usage(1, 2, 3, 4))
    r.harness, r.session_id = "claude", "sid1"
    r.write(session_dir / "result.json")
    (session_dir / "log.jsonl").write_text('{"type":"user"}\n<script>alert(1)</script>\n', encoding="utf-8")
    brand = tmp_path / "brand.json"
    brand.write_text(
        json.dumps({"name": "acme", "themes": {"light": {"accent": "#ff0000"}, "dark": {"accent": "#00ff00"}}}),
        encoding="utf-8",
    )

    page = report.write(CacheLayout(cache), design_tokens=brand, inline=True)
    html = page.read_text(encoding="utf-8")
    assert "window.__XH_DATA__ = {" in html and report.INLINE_MARKER not in html
    assert '"name": "acme"' in json.dumps(
        json.loads((cache / "report" / "report.tokens.json").read_text(encoding="utf-8")), indent=1
    )
    # The payload carries the index, the result, the log and the tokens; a "</script>" in a log cannot end the tag.
    start = html.index("window.__XH_DATA__ = ") + len("window.__XH_DATA__ = ")
    payload = json.loads(html[start : html.index(";</script>", start)].replace("<\\/", "</"))
    assert payload["tokens"]["name"] == "acme"
    assert payload["index"]["inline"] is True and payload["index"]["cells"][0]["session_id"] == "sid1"
    assert payload["results"]["sid1"]["model"] == "claude-opus-5"
    assert "<script>alert(1)</script>" in payload["logs"]["sid1"]
    assert "<script>alert(1)</script>" not in html  # it is escaped as <\/script> inside the payload


def test_report_refuses_missing_or_malformed_design_tokens(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    cache.mkdir()
    with pytest.raises(FileNotFoundError, match="design tokens file not found"):
        report.write(CacheLayout(cache), design_tokens=tmp_path / "absent.json")
    bad = tmp_path / "bad.json"
    bad.write_text('{"colours": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="'themes' key"):
        report.write(CacheLayout(cache), design_tokens=bad)


def test_report_tolerates_an_empty_or_corrupt_results_tree(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "s" / "h" / "m" / "20260101T000000Z" / "sid"
    session_dir.mkdir(parents=True)
    (session_dir / "result.json").write_text("not json", encoding="utf-8")
    (session_dir / "history.json").write_text("not json", encoding="utf-8")
    report.write(CacheLayout(cache))
    assert json.loads((cache / "report" / "index.json").read_text(encoding="utf-8"))["cells"] == []
    assert (cache / "report" / "history.jsonl").read_text(encoding="utf-8") == ""
    # A cache with no results/ at all still writes an empty report.
    empty = tmp_path / "empty-cache"
    report.write(CacheLayout(empty))
    assert json.loads((empty / "report" / "index.json").read_text(encoding="utf-8"))["cells"] == []

    # A stored record carrying a null where a string is declared: the combine step sorts
    # every record by ``at``, so a None there used to abort the whole report (ADR 0038).
    nulled = CacheLayout(tmp_path / "nulled-cache")
    session = nulled.session(skill="s", harness="h", model="m", run="20260101T000000Z", session="sid")
    session.mkdir()
    session.result.write_text('{"harness": "h", "session_id": "sid"}', encoding="utf-8")
    session.history.write_text('{"session_id": "sid", "at": null, "verdict": null}', encoding="utf-8")
    report.write(nulled)
    row = json.loads(nulled.index.read_text(encoding="utf-8"))["cells"][0]
    assert (row["session_id"], row["at"], row["verdict"]) == ("sid", "", "")
    assert json.loads(nulled.history.read_text(encoding="utf-8"))["at"] == ""


def test_a_metrics_record_round_trips_through_disk_and_the_wire(tmp_path: Path) -> None:
    """One line of sorted JSON out, the same record back (ADR 0037)."""
    record = _metrics(_result("m", Usage(10, 20, 30, 40)), node="n[x/m]", verdict="fail")
    path = record.write(tmp_path / "sid" / "history.json")
    assert path.read_text(encoding="utf-8").endswith("}\n")
    assert json.loads(path.read_text(encoding="utf-8")) == record.to_dict()
    assert CellMetrics.stored(path) == record
    # The wire boundary: execnet ships builtins only, so the record crosses as a mapping
    # and is decoded on the controller (ADR 0016).
    assert CellMetrics.from_dict(record.to_dict()) == record
    assert normalise.now_iso().endswith("+00:00")


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
    assert partial.outcome == Outcome(node="n", verdict="pass", wall_ms=7, started_at="t")
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


# -- the wire formats these two documents are (ADR 0037) --------------------------------

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
    "estimated_cost_usd",
    "files_written",
    "final_context_pct",
    "fixture",
    "harness",
    "harness_reported_cost_usd",
    "input_tokens",
    "model",
    "node",
    "output_tokens",
    "output_tokens_per_sec",
    "peak_context_tokens",
    "rates_applied",
    "reasoning_tokens",
    "record_kinds",
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
    "ttft_ms",
    "turns",
    "verdict",
    "wall_ms",
]

# Every key of one ``report/index.json`` row, likewise.
INDEX_ROW_KEYS = [
    "accumulative_billed_tokens",
    "at",
    "baseline_tokens",
    "case",
    "context_window",
    "context_window_pct",
    "duration_ms",
    "estimated_cost_usd",
    "files_written",
    "final_context_pct",
    "fixture",
    "harness",
    "harness_reported_cost_usd",
    "has_ledger",
    "log",
    "model",
    "node",
    "output_tokens_per_sec",
    "peak_context_tokens",
    "prompt",
    "rates_applied",
    "record_kinds",
    "reported_turns",
    "result",
    "run",
    "session_id",
    "skill",
    "skill_coverage",
    "subagents",
    "suite",
    "tool_calls",
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


def test_index_json_has_exactly_the_frozen_key_set(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    session = cache.session(skill="demo", harness="claude", model="m", run="20260822T000000Z", session="sid1")
    _result("m", Usage(1, 2)).write(session.result)
    report.write(cache)

    index = json.loads(cache.index.read_text(encoding="utf-8"))
    assert sorted(index) == ["captured", "cells", "generated_at", "inline"]
    assert sorted(index["cells"][0]) == INDEX_ROW_KEYS


# -- the cache tree has one owner (ADR 0037) --------------------------------------------


def test_cache_layout_names_every_path_in_the_tree(tmp_path: Path) -> None:
    """Each name is declared once; nothing else reassembles one of these paths."""
    cache = CacheLayout(tmp_path / "cache")
    assert (cache.build, cache.results, cache.report) == (
        tmp_path / "cache" / "build",
        tmp_path / "cache" / "results",
        tmp_path / "cache" / "report",
    )
    assert [p.name for p in (cache.index, cache.history, cache.summary, cache.page, cache.tokens, cache.glossary)] == [
        "index.json",
        "history.jsonl",
        "report.json",
        "report.html",
        "report.tokens.json",
        "XHARNESS-REPORT-GLOSSARY.md",
    ]
    session = cache.session(skill="demo", harness="claude", model="opus", run="20260822T000000Z", session="sid1")
    assert session.path == cache.results / "demo" / "claude" / "opus" / "20260822T000000Z" / "sid1"
    assert session.rel == "demo/claude/opus/20260822T000000Z/sid1"
    assert [p.name for p in (session.log, session.result, session.history, session.subagents)] == [
        "log.jsonl",
        "result.json",
        "history.json",
        "subagents",
    ]
    # The page fetches its evidence relative to report/, where index.json sits (ADR 0032).
    assert session.report_link("log.jsonl") == "../results/demo/claude/opus/20260822T000000Z/sid1/log.jsonl"


def test_cache_layout_walks_the_five_levels_and_keeps_the_coordinates(tmp_path: Path) -> None:
    """The walk the index, the aggregated history and the replay all share."""
    cache = CacheLayout(tmp_path / "cache")
    for model in ("sonnet", "opus"):
        cache.session(skill="demo", harness="claude", model=model, run="20260822T000000Z", session="sid").mkdir()
    # Neither a file at the session level nor a directory at the wrong depth is a session.
    (cache.results / "demo" / "claude" / "opus" / "20260822T000000Z" / "stray.txt").write_text("x", encoding="utf-8")
    (cache.results / "demo" / "shallow").mkdir(parents=True)

    found = list(cache.sessions())
    assert [(s.model, s.session) for s in found] == [("opus", "sid"), ("sonnet", "sid")]
    assert {(s.skill, s.harness, s.run) for s in found} == {("demo", "claude", "20260822T000000Z")}
    # A cache with no results/ at all walks to nothing rather than raising.
    assert list(CacheLayout(tmp_path / "empty").sessions()) == []


def test_a_session_dir_addressed_by_path_cannot_publish_a_report_link(tmp_path: Path) -> None:
    """The two variants are two types, so a garbage key is unrepresentable (ADR 0038).

    A caller handed a directory -- a replay, a harness adapter re-reading its own captured
    log -- gets the four documents and ``mkdir()``. It does not get ``rel`` or a report
    link, because a bare path does not know where it sits in a cache: when one type served
    both jobs with the coordinates defaulting to empty, that caller published ``"////sid1"``
    as a session key and no one was told.
    """
    session = SessionDir(tmp_path / "sid1")
    assert session.session == "sid1"
    assert session.log == tmp_path / "sid1" / "log.jsonl"
    assert session.mkdir().is_dir()
    assert not hasattr(session, "rel") and not hasattr(session, "report_link")

    located = CacheLayout(tmp_path).session(skill="s", harness="h", model="m", run="r", session="sid1")
    assert isinstance(located, SessionDir) and located.rel == "s/h/m/r/sid1"
