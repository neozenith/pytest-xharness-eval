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
