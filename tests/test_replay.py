"""``replay``: rebuilding cached results, history and the report from captured logs (ADR 0023)."""

# Standard Library
import json
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import replay
from pytest_xharness_eval.model import registry
from tests.support import _jsonl, _skill


def _stale_cache(tmp_path: Path) -> tuple[Path, Path]:
    """A project holding one captured Claude session whose ``result.json`` is out of date.

    The log and the stored envelope are the evidence a replay re-derives from; the rest of
    the stored result is deliberately wrong, so a rebuild that does nothing is visible.
    Returns the cache root and that session's directory.
    """
    skill = _skill(tmp_path)  # tmp_path/demo
    # The project's pytest config: rootdir discovery anchors here, and the skills root is tmp_path itself.
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\nxharness_skills_dir = "."\n', encoding="utf-8")
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20261022T000000Z" / "sid1"
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
        'from pytest_xharness_eval import evalcase\n\n@evalcase(task="go", skill="demo", fixture="seed")\n'
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
    return cache, session_dir


def test_replay_rebuilds_results_history_and_report_from_cached_logs(tmp_path: Path) -> None:
    cache, session_dir = _stale_cache(tmp_path)

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
    # The task is the suite's declaration; the prompt is what the *claude* harness renders
    # around it, so a replayed record carries the same string the live cell sent (ADR 0044).
    assert (
        fresh["case"]["name"],
        fresh["case"]["skill"],
        fresh["case"]["fixture"],
        fresh["case"]["task"],
        fresh["case"]["prompt"],
    ) == ("eval_demo", "demo", "seed", "go", "/demo go")
    # The combine step (ADR 0032): one index and one aggregated history under report/.
    index = json.loads((cache / "report" / "index.json").read_text(encoding="utf-8"))
    row = index["cells"][0]
    assert row["suite"].endswith("evals/eval_demo.py") and row["prompt"] == "/demo go"
    assert row["run"] == "20261022T000000Z"
    assert row["result"] == "../results/demo/claude/claude-opus-5/20261022T000000Z/sid1/result.json"
    assert row["log"] == "../results/demo/claude/claude-opus-5/20261022T000000Z/sid1/log.jsonl"
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


def test_replay_main_rebuilds_the_cache_named_on_its_command_line(tmp_path: Path) -> None:
    """The ``python -m`` entry point: parse, rebuild, report -- and spend nothing (ADR 0032)."""
    cache, session_dir = _stale_cache(tmp_path)

    replay.main([str(cache), "--price", "claude/claude-opus-5: input=1.00 output=2.00", "-v"])

    fresh = json.loads((session_dir / "result.json").read_text(encoding="utf-8"))
    assert fresh["turns"] == 1  # the stale 99 is gone
    assert fresh["rates_applied"]["input"] == 1.0  # the --price line was applied, in USD per MTok
    assert (cache / "report" / "report.html").is_file()


def test_replay_main_refuses_a_target_that_is_not_a_directory(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not a directory"):
        replay.main([str(tmp_path / "nowhere")])


def test_replay_main_pointed_at_a_legacy_directory_migrates_then_rebuilds(tmp_path: Path) -> None:
    """The pre-0032 location is an input to the entry point and never an output (ADR 0032)."""
    skill = _skill(tmp_path / "skills")  # skills/demo
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    captured = skill / "evals" / "captured"
    case_dir = captured / "eval_demo"
    case_dir.mkdir(parents=True)
    _jsonl(
        case_dir / "claude-sid1.jsonl",
        [
            {"type": "user", "message": {"content": "go"}},
            {
                "type": "assistant",
                "message": {"id": "m1", "model": "claude-opus-5", "usage": {"input_tokens": 5, "output_tokens": 7}},
            },
        ],
    )
    (case_dir / "claude-sid1.result.json").write_text(
        json.dumps(
            {
                "harness": "claude",
                "model": "claude-opus-5",
                "session_id": "sid1",
                "envelope": {"session_id": "sid1", "num_turns": 1, "total_cost_usd": 0.5, "usage": {}},
            }
        ),
        encoding="utf-8",
    )

    replay.main([str(captured)])

    # The destination is the project's own cache root, resolved from its pytest config.
    session = tmp_path / ".xharness_eval_cache" / "results" / "demo" / "claude" / "claude-opus-5"
    rebuilt = json.loads((session / "00000000T000000Z" / "sid1" / "result.json").read_text(encoding="utf-8"))
    assert (rebuilt["turns"], rebuilt["harness_reported_cost_usd"]) == (1, 0.5)
    assert rebuilt["estimated_cost_usd"] > 0
    assert (tmp_path / ".xharness_eval_cache" / "report" / "report.html").is_file()
    assert (case_dir / "claude-sid1.result.json").is_file()  # the original is untouched


def test_replay_refuses_a_result_without_its_log(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    session_dir = cache / "results" / "demo" / "claude" / "m" / "20260101T000000Z" / "x"
    session_dir.mkdir(parents=True)
    (session_dir / "result.json").write_text('{"harness": "claude", "session_id": "x"}', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="no captured session log"):
        replay.rebuild(cache)


def test_a_rebuild_carries_the_archived_catalogue_facts_forward_or_looks_them_up() -> None:
    """A stored tier wins, so an archived run says what it was; an older capture is looked up (ADR 0057)."""
    catalogue = registry.catalogue()
    stored = {"harness": "claude", "model": "claude-opus-5", "line": "opus", "family_tier": 9, "released": "2026-07-24"}
    spec = replay.stored_spec(stored, catalogue)
    assert spec is not None and spec.family_tier == 9 and spec.released == date(2026, 7, 24)
    older = replay.stored_spec({"harness": "claude", "model": "claude-opus-5"}, catalogue)
    assert older is not None and (older.line, older.family_tier) == ("opus", 3)
    # A capture of a model the catalogue never described replays rather than failing history.
    assert replay.stored_spec({"harness": "claude", "model": "claude-opus-4-5"}, catalogue) is None
