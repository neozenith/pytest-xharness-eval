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


def _tool(root: Path) -> Path:
    for rel, body in {
        "tool/cli.py": "print(1)",
        "tool/rules/a.json": "{}",
        "tool/evals/eval_x.py": "grades the tool",
        "tool/__pycache__/cli.pyc": "cache",
        "tool/node_modules/dep/index.js": "vendored",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
    return root


def test_version_is_stable_and_moves_only_when_a_tracked_file_does(tmp_path: Path) -> None:
    """The subject's version: the digest of what a case tracks (ADR 0074)."""
    root = _tool(tmp_path / "project")
    first = ws.version(root, ["tool"])
    assert first == ws.version(root, ["tool"]) and len(first) == 12
    (root / "tool" / "__pycache__" / "cli.pyc").write_text("recompiled", encoding="utf-8")
    (root / "tool" / "node_modules" / "dep" / "index.js").write_text("upgraded", encoding="utf-8")
    assert ws.version(root, ["tool"]) == first  # caches and vendored trees are not the subject
    (root / "tool" / "rules" / "a.json").write_text('{"x": 1}', encoding="utf-8")
    assert ws.version(root, ["tool"]) != first


def test_version_excludes_named_directories_beneath_the_tracked_path_only(tmp_path: Path) -> None:
    root = _tool(tmp_path / "evals" / "project")  # an excluded name *above* the tracked path
    plain = ws.version(root, ["tool"], exclude=["evals"])
    (root / "tool" / "evals" / "eval_x.py").write_text("a new grader", encoding="utf-8")
    assert ws.version(root, ["tool"], exclude=["evals"]) == plain
    assert ws.version(root, ["tool"]) != plain  # without the exclusion the suite is part of it
    (root / "tool" / "cli.py").write_text("print(2)", encoding="utf-8")
    assert ws.version(root, ["tool"], exclude=["evals"]) != plain


def test_version_does_not_depend_on_where_the_project_is_checked_out(tmp_path: Path) -> None:
    assert ws.version(_tool(tmp_path / "here"), ["tool", "tool/cli.py"]) == ws.version(
        _tool(tmp_path / "elsewhere" / "deeper"), ["tool/cli.py", "tool"]
    )


def test_version_tracks_an_absolute_path_or_one_outside_the_root(tmp_path: Path) -> None:
    """A scenario's tool often lives in its own repository, beside the project rather than in it."""
    _tool(tmp_path / "tool-repo")
    project = tmp_path / "project"
    project.mkdir()
    absolute = ws.version(project, [str(tmp_path / "tool-repo" / "tool")])
    climbing = ws.version(project, ["../tool-repo/tool"])
    (tmp_path / "tool-repo" / "tool" / "cli.py").write_text("print(3)", encoding="utf-8")
    assert ws.version(project, [str(tmp_path / "tool-repo" / "tool")]) != absolute
    assert ws.version(project, ["../tool-repo/tool"]) != climbing


def test_version_of_a_path_that_is_not_there_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="tracked path does not exist"):
        ws.version(tmp_path, ["missing"])


def test_an_absolute_track_is_named_by_its_basename_so_the_checkout_location_does_not_move_it(
    tmp_path: Path,
) -> None:
    """Two machines with the tool's repository in different places record the same version."""
    here = _tool(tmp_path / "home" / "alice" / "tool-repo") / "tool"
    there = _tool(tmp_path / "srv" / "ci" / "deeper" / "tool-repo") / "tool"
    assert ws.version(tmp_path / "p1", [str(here)]) == ws.version(tmp_path / "p2", [str(there)])
    assert ws.version(tmp_path, [str(here / "cli.py")]) == ws.version(tmp_path, [str(there / "cli.py")])
    (there / "cli.py").write_text("print(9)", encoding="utf-8")
    assert ws.version(tmp_path, [str(here)]) != ws.version(tmp_path, [str(there)])
