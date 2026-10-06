"""``model.workspace``: materialising a fixture and diffing what the agent changed."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model import workspace as ws


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


def test_materialise_copies_each_overlay_over_the_fixture_in_order(tmp_path: Path) -> None:
    """A treatment is stacked on the fixture; a later layer's file replaces an earlier one's (ADR 0055)."""
    fixture, universal, dialect = (tmp_path / n for n in ("fixture", "lean", "lean__claude"))
    for d in (fixture, universal, dialect):
        d.mkdir()
    (fixture / "AGENTS.md").write_text("fixture", encoding="utf-8")
    (fixture / "a.md").write_text("seed", encoding="utf-8")
    (universal / "AGENTS.md").write_text("treated", encoding="utf-8")
    (dialect / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    ws_dir = ws.materialise(fixture, "cell", tmp_path / "work", [universal, dialect])
    assert sorted(p.name for p in ws_dir.iterdir()) == ["AGENTS.md", "CLAUDE.md", "a.md"]
    assert (ws_dir / "AGENTS.md").read_text(encoding="utf-8") == "treated"


def test_discard_removes_the_workspace_and_its_harness_run_dirs_only(tmp_path: Path) -> None:
    """A finished cell leaves nothing behind, and never takes a neighbour's workspace with it (ADR 0062)."""
    ws_dir = tmp_path / "eval_x-codex-gpt-5"
    for d in (ws_dir, tmp_path / "eval_x-codex-gpt-5.codex", tmp_path / "eval_x-codex-gpt-5.claude"):
        (d / "sub").mkdir(parents=True)
    neighbour = tmp_path / "eval_x-codex-gpt-5.6-sol"  # matches a `<ws>.*` glob, so must survive
    neighbour.mkdir()
    ws.discard(ws_dir)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["eval_x-codex-gpt-5.6-sol"]
    ws.discard(ws_dir)  # already gone: a no-op, not an error
