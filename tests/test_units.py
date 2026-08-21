"""Unit tests for the pure modules: pricing, matrix, normalise, workspace, case, runresult."""

# Standard Library
import json
import tomllib
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import DEFAULT_MATRIX, Cell, EvalCase, RunResult, Usage, __version__, evalcase, history
from pytest_xharness_eval import matrix as mx
from pytest_xharness_eval import normalise, pricing, runner
from pytest_xharness_eval import workspace as ws

# -- package surface ---------------------------------------------------------------


def test_version_matches_pyproject(pytestconfig: pytest.Config) -> None:
    """`version` in pyproject.toml and `__version__` are declared twice; a release bumps both (ADR 0017)."""
    pyproject = tomllib.loads((pytestconfig.rootpath / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_runners_cover_exactly_the_known_harnesses() -> None:
    assert tuple(sorted(runner.RUNNERS)) == tuple(sorted(mx.KNOWN_HARNESSES))


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


def _result(model: str, usage: Usage) -> RunResult:
    return RunResult(
        harness="x",
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


def test_bundled_table_prices_each_tier_separately() -> None:
    table = pricing.load_table()
    r = pricing.price(_result("claude-opus-5", Usage(1_000_000, 1_000_000, 1_000_000, 1_000_000)), table)
    assert r.cost_status == "priced"
    assert r.cost_usd == pytest.approx(5.0 + 25.0 + 0.5 + 6.25)


def test_cache_reads_are_not_billed_at_the_input_rate() -> None:
    table = pricing.load_table()
    flat = pricing.price(_result("gpt-5.6-sol", Usage(input_tokens=200_000)), table).cost_usd
    tiered = pricing.price(
        _result("gpt-5.6-sol", Usage(input_tokens=30_000, cache_read_tokens=170_000)), table
    ).cost_usd
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


def test_overrides_layer_on_top_of_the_bundled_table(tmp_path: Path) -> None:
    local = tmp_path / "prices.toml"
    local.write_text(
        '["claude-opus-5"]\ninput = 1.0\noutput = 1.0\n\n["new-model"]\ninput = 2.0\noutput = 3.0\n', "utf-8"
    )
    table = pricing.load_table(overrides=local)
    assert table["claude-opus-5"] == pricing.Rates(1.0, 1.0, 1.0, 1.0)  # cache tiers default to input
    assert table["new-model"].output == 3.0
    assert "gpt-5.6-sol" in table  # bundled rows survive
    assert pricing.load_table(overrides=tmp_path / "absent.toml") == pricing.load_table()


# -- runresult -----------------------------------------------------------------------


def test_total_tokens_sums_the_four_priced_tiers_only() -> None:
    assert Usage(1, 2, 3, 4, reasoning_tokens=100).total_tokens == 10


def test_write_round_trips_with_total_tokens(tmp_path: Path) -> None:
    r = _result("m", Usage(1, 2, 3, 4))
    out = r.write(tmp_path / "nested" / "r.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["usage"]["total_tokens"] == 10
    assert data["cost_status"] == "unpriced"
    assert data["harness"] == "x"


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


# -- runner (pure part) --------------------------------------------------------------


def test_claude_log_path_slugifies_every_non_alphanumeric_character(tmp_path: Path) -> None:
    workspace = tmp_path / "tmp" / "evals" / "eval_demo-claude-claude-opus-5"
    workspace.mkdir(parents=True)
    path = runner.claude_log_path(Path("/cfg"), workspace, "abc-123")
    slug = path.parent.name
    assert path.parent.parent == Path("/cfg/projects")
    assert path.name == "abc-123.jsonl"
    assert "_" not in slug and "/" not in slug and "." not in slug
    assert slug.endswith("eval-demo-claude-claude-opus-5")


# -- normalise -----------------------------------------------------------------------


def _jsonl(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n\nnot json\n", encoding="utf-8")
    return path


def test_from_claude_prefers_envelope_aggregates_and_counts_tools(tmp_path: Path) -> None:
    msg = {
        "id": "m1",
        "model": "claude-opus-5",
        "usage": {"input_tokens": 5, "output_tokens": 7, "output_tokens_details": {"thinking_tokens": 3}},
        "content": [{"type": "tool_use", "name": "Edit"}, {"type": "tool_use", "name": "Edit"}, {"type": "text"}],
    }
    # Claude writes one record per content block; both records share id m1 and its usage.
    second_block = {**msg, "content": [{"type": "tool_use", "name": "Bash"}]}
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user"},
            {"type": "assistant", "message": msg},
            {"type": "assistant", "message": second_block},
            {"type": "assistant", "message": {"id": "m2", "model": "claude-opus-5", "usage": {}, "content": []}},
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
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 1000,
            "cache_creation_input_tokens": 200,
        },
    }
    r = normalise.from_claude(log, envelope, tmp_path, ["ARCHITECTURE.md"])
    assert (r.harness, r.model, r.session_id, r.exit_code, r.turns, r.final_text) == (
        "claude",
        "claude-opus-5",
        "sid",
        0,
        4,
        "done",
    )
    assert r.usage == Usage(100, 50, 1000, 200, reasoning_tokens=3)  # reasoning counted once for m1
    assert r.tool_calls == {"Edit": 2, "Bash": 1}  # tools counted across every record
    assert r.reported_cost_usd == 0.42
    assert r.files_written == ["ARCHITECTURE.md"]


def test_from_claude_falls_back_to_log_totals_without_envelope_usage(tmp_path: Path) -> None:
    log = _jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "assistant", "message": {"usage": {"input_tokens": 5, "output_tokens": 7}}},
            {"type": "assistant", "message": {"usage": {"input_tokens": 1, "output_tokens": 1}}},
        ],
    )
    r = normalise.from_claude(log, {"is_error": True, "model": "claude-sonnet-5"}, tmp_path, [])
    assert (r.exit_code, r.turns, r.model) == (1, 2, "claude-sonnet-5")
    assert r.usage == Usage(6, 8)


def test_from_codex_takes_the_last_cumulative_count_and_splits_cached(tmp_path: Path) -> None:
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
    r = normalise.from_codex(log, 0, tmp_path, [])
    assert (r.harness, r.model, r.session_id, r.turns, r.duration_ms, r.final_text) == (
        "codex",
        "gpt-5.6-sol",
        "01a0",
        1,
        321,
        "ok",
    )
    assert r.usage == Usage(input_tokens=1000, output_tokens=60, cache_read_tokens=4000, reasoning_tokens=9)
    assert r.usage.total_tokens == 5060
    assert r.tool_calls == {"CommandExecution": 1, "FileChange": 1}
    assert r.reported_cost_usd is None


# -- history -------------------------------------------------------------------------


def test_metrics_record_is_flat_and_complete() -> None:

    r = _result("m", Usage(10, 20, 30, 40))
    r.turns, r.duration_ms, r.cost_usd = 7, 4321, 0.5
    r.tool_calls = {"Edit": 2, "Bash": 3}
    r.files_written = ["a", "b"]
    rec = history.metrics_of(r, node="n[x/m]", verdict="pass", wall_ms=5000, started_at="2026-08-21T00:00:00+00:00")
    assert rec["tool_calls"] == 5 and rec["tool_calls_by_name"] == {"Edit": 2, "Bash": 3}
    assert (rec["turns"], rec["duration_ms"], rec["wall_ms"], rec["cost_usd"], rec["tokens"]) == (
        7,
        4321,
        5000,
        0.5,
        100,
    )
    assert rec["files_written"] == 2
    assert history.status_word(rec) == "$0.5000  100 tok  5.0s  7 turns  5 tools"


def test_history_append_is_one_json_line_per_call(tmp_path: Path) -> None:

    path = tmp_path / "evals" / "history.jsonl"
    history.append(path, {"b": 1, "a": 2})
    history.append(path, {"a": 3})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"a": 2, "b": 1}', '{"a": 3}']
    assert history.now_iso().endswith("+00:00")
