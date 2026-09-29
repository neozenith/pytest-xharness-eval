"""``runtime.legacy``: migrating a pre-0032 captured directory."""

# Standard Library
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval.runtime.legacy import LegacyCapture
from tests.support import _skill


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
                "at": "2026-10-22T00:00:00+00:00",
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
    capture = LegacyCapture.found_at(captured)
    # The directory is recognised by shape, and only a recognised one can be migrated.
    assert capture is not None and capture.skill == "demo"
    assert capture.migrate_into(cache) == 2
    assert (cache / "results" / "demo" / "claude" / "claude-opus-5" / "00000000T000000Z" / "sid2").is_dir()
    session_dir = cache / "results" / "demo" / "claude" / "claude-opus-5" / "20261022T000000Z" / "sid1"
    assert (session_dir / "result.json").is_file() and (session_dir / "log.jsonl").is_file()
    hist = json.loads((session_dir / "history.json").read_text(encoding="utf-8"))
    # The record is migrated to the current shape, not copied verbatim: it names its new
    # cache root, the pre-0032 ``captured`` key is gone, and today's fields are present.
    assert hist["cache"] == str(cache) and "captured" not in hist
    assert (hist["case"], hist["verdict"], hist["node"]) == ("eval_demo", "pass", "n")
    assert hist["accumulative_billed_tokens"] == 0
    # The original evidence is untouched, and a second migration is a no-op.
    assert (case / "claude-sid1.result.json").is_file() and (captured / "history.jsonl").is_file()
    assert capture.migrate_into(cache) == 0
    assert LegacyCapture.found_at(cache) is None  # a cache root is not a legacy capture
