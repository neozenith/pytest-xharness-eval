"""``plugin.cell``: one cell's live run, step by step (ADR 0002, ADR 0040)."""

# Standard Library
import json
import os
import re
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    CaseOutput,
    Cell,
    CostStatus,
    RunResult,
    Usage,
    evalcase,
)
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin import cell as cellrun
from pytest_xharness_eval.runtime import settings
from tests.support import _result, _skill


def test_two_cells_of_one_case_differing_only_in_effort_get_their_own_workspaces(tmp_path: Path) -> None:
    """A shared build directory would have the pair overwrite each other's workspace."""
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "seed.md").write_text("seed", encoding="utf-8")
    names = set()
    for rung in ("high", "low", None):
        run = cellrun.CellRun(
            case=_case_for_cell_id(),
            cell=Cell(harness="claude", model="opus", effort=rung),
            settings=settings.Settings(rootpath=tmp_path, skills_root=tmp_path, cache=CacheLayout(tmp_path / "cache")),
            skill_dir=tmp_path,
            fixture_dir=fixture,
            node="n",
            suite="s",
        )
        names.add(run.cell_id)
    assert names == {"eval_thing-claude-opus-high", "eval_thing-claude-opus-low", "eval_thing-claude-opus"}


def _case_for_cell_id() -> Any:
    @evalcase(task="t", skill="s", fixture="f")
    def eval_thing(output: CaseOutput) -> None:
        pass

    return eval_thing


def eval_ok(output: CaseOutput) -> None:
    """A grader that passes."""


def eval_fails(output: CaseOutput) -> None:
    """A grader whose assertion fails the cell."""
    raise AssertionError("the agent did not do the thing")


def eval_errors(output: CaseOutput) -> None:
    """A grader that is itself broken."""
    raise RuntimeError("boom")


def _cell_run(tmp_path: Path, grader: Any = eval_ok) -> cellrun.CellRun:
    """A CellRun over a real skill, a real fixture and a real cache: everything but the CLI.

    Nothing here is faked (ADR 0002). What the tests exercise are the six free steps
    around ``invoke``, which is the only one that would spawn a process.
    """
    skill = _skill(tmp_path / "skills")  # skills/demo
    fixture_dir = skill / "evals" / "fixtures" / "seed"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "README.md").write_text("seed\n", encoding="utf-8")
    case = evalcase(task="go", skill="demo", fixture="seed")(grader)
    return cellrun.CellRun(
        case=case,
        cell=Cell(harness="claude", model="claude-opus-5"),
        settings=settings.Settings(
            rootpath=tmp_path, skills_root=tmp_path / "skills", cache=CacheLayout(tmp_path / "cache")
        ),
        skill_dir=skill,
        fixture_dir=fixture_dir,
        node="skills/demo/evals/eval_demo.py::eval_demo[claude/claude-opus-5]",
        suite="skills/demo/evals/eval_demo.py",
        skill_files=skillcov.catalog(skill),
    )


def _captured_run(tmp_path: Path) -> RunResult:
    """A folded run with a session log on disk, as one would exist when the CLI returns."""
    result = _result("claude-opus-5", Usage(1_000_000, 0, 0, 0))
    log = tmp_path / "native" / "session.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('{"type": "user", "message": {"content": "go"}}\n', encoding="utf-8")
    result.session_log, result.session_id, result.workspace = str(log), "sid-1", str(tmp_path / "ws")
    return result


def test_the_run_stamp_is_minted_once_and_shared_through_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """One stamp per sweep, so a run's cells share one results/{...}/{run}/ level (ADR 0032)."""
    monkeypatch.delenv(cellrun.RUN_STAMP_ENV, raising=False)
    stamp = cellrun.run_stamp()
    assert re.fullmatch(r"\d{8}T\d{6}Z", stamp)
    # An xdist worker is a child process: it reads the controller's stamp back, not a new one.
    assert os.environ[cellrun.RUN_STAMP_ENV] == stamp == cellrun.run_stamp()
    monkeypatch.setenv(cellrun.RUN_STAMP_ENV, "")
    assert cellrun.run_stamp() != ""  # an empty stamp would name an unnamed run directory


def test_a_cell_materialises_its_own_workspace_under_the_caches_build_dir(tmp_path: Path) -> None:
    run = _cell_run(tmp_path)
    workspace = run.materialise()
    assert workspace == tmp_path / "cache" / "build" / "eval_ok-claude-claude-opus-5"
    assert (workspace / "README.md").read_text(encoding="utf-8") == "seed\n"


def test_a_cell_derives_and_captures_where_its_five_coordinates_say(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``store`` is the live half of the sequence a replay repeats (ADR 0034)."""
    monkeypatch.setenv(cellrun.RUN_STAMP_ENV, "20261028T000000Z")
    run = _cell_run(tmp_path)
    result = _captured_run(tmp_path)

    session = run.store(result)

    assert session.rel == "demo/claude/claude-opus-5/20261028T000000Z/sid-1"
    assert session.path == tmp_path / "cache" / "results" / session.rel
    # Priced, coverage-annotated and named after its case -- before anything is written.
    assert result.cost_status is CostStatus.PRICED and result.estimated_cost_usd is not None
    assert result.skill_coverage is not None and result.case is not None
    assert (result.case.name, result.case.suite) == ("eval_ok", "skills/demo/evals/eval_demo.py")
    assert json.loads(session.result.read_text(encoding="utf-8"))["session_id"] == "sid-1"
    assert session.log.read_text(encoding="utf-8").startswith('{"type": "user"')


@pytest.mark.parametrize(
    ("grader", "expected", "raises"),
    [
        (eval_ok, Verdict.PASS, None),
        (eval_fails, Verdict.FAIL, AssertionError),
        (eval_errors, Verdict.ERROR, RuntimeError),
    ],
)
def test_grading_names_the_verdict_and_still_lets_the_grader_fail_the_cell(
    tmp_path: Path, grader: Any, expected: Verdict, raises: type[Exception] | None
) -> None:
    """An assertion is a fail, anything else is an error, and pytest still sees the exception."""
    run = _cell_run(tmp_path, grader)
    result = _captured_run(tmp_path)
    if raises is None:
        assert run.grade(result, tmp_path / "ws") is Verdict.PASS
    else:
        with pytest.raises(raises):
            run.grade(result, tmp_path / "ws")
    assert run.verdict is expected


def test_a_cells_record_carries_a_plain_string_verdict_beside_its_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record crosses to the controller through execnet, which serialises builtins only (ADR 0016)."""
    monkeypatch.setenv(cellrun.RUN_STAMP_ENV, "20261028T000000Z")
    run = _cell_run(tmp_path)
    result = _captured_run(tmp_path)
    session = run.store(result)
    run.grade(result, tmp_path / "ws")

    record = run.record(cellrun.Attempt(result=result, started_at="2026-08-28T00:00:00+00:00", wall_ms=4321), session)

    assert record.verdict == "pass" and type(record.verdict) is str
    assert (record.node, record.wall_ms, record.at) == (run.node, 4321, "2026-08-28T00:00:00+00:00")
    assert record.cache == str(tmp_path / "cache")
    assert CellMetrics.stored(session.history) == record


def test_a_treated_cell_stacks_its_overlay_and_counts_it_as_seeded(tmp_path: Path) -> None:
    """The agent found the treatment's files there, so a grader must not see them as written (ADR 0055)."""
    run = _cell_run(tmp_path)
    overlay = tmp_path / "skills" / "demo" / "evals" / "treatments" / "lean-ci"
    overlay.mkdir(parents=True)
    (overlay / "AGENTS.md").write_text("use cheap subagents\n", encoding="utf-8")
    run.cell = Cell(harness="claude", model="claude-opus-5", treatment="lean-ci")
    run.overlays = [overlay]
    workspace = run.materialise()
    assert workspace.name == "eval_ok-claude-claude-opus-5-lean-ci"
    assert (workspace / "AGENTS.md").is_file()
    assert run.output(_captured_run(tmp_path), workspace).seeded == {"README.md", "AGENTS.md"}
    assert run.session_dir("sid").rel.split("/")[2] == "claude-opus-5+lean-ci"
