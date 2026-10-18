"""``plugin.cell``: one cell's live run, step by step (ADR 0002, ADR 0040)."""

# Standard Library
import contextlib
import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Call,
    CaseOutput,
    Cell,
    CostStatus,
    RunResult,
    Usage,
    evalcase,
    harness,
)
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.generators import Table
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.scenario import Scenario, write_scenario
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin import cell as cellrun
from pytest_xharness_eval.runtime import settings
from pytest_xharness_eval.runtime.plan import CellPlan
from tests.support import _late_transcript, _result, _skill, _unfoldable


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
        plan=CellPlan(
            case=case,
            cell=Cell(harness="claude", model="claude-opus-5"),
            skill_dir=skill,
            fixture_dir=fixture_dir,
            node="skills/demo/evals/eval_demo.py::eval_demo[claude/claude-opus-5]",
            suite="skills/demo/evals/eval_demo.py",
            subject="demo",
            skill_files=tuple(skillcov.catalog(skill)),
        ),
        settings=settings.Settings(
            rootpath=tmp_path, skills_root=tmp_path / "skills", cache=CacheLayout(tmp_path / "cache")
        ),
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


def test_a_run_whose_logs_would_not_fold_is_kept_where_its_result_would_have_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A subagent mismatch fails the cell, but the paid logs are captured first (ADR 0072)."""
    monkeypatch.setenv(cellrun.RUN_STAMP_ENV, "20261028T000000Z")
    err = _unfoldable(tmp_path / "native")
    _late_transcript(tmp_path / "native" / "late")
    err = harness.UnfoldedRun(
        str(err), dataclasses.replace(err.evidence, transcripts=(tmp_path / "native" / "late" / "agent-x.jsonl",))
    )

    session = _cell_run(tmp_path).quarantine(err)

    assert session.rel == "demo/claude/claude-opus-5/20261028T000000Z/sid-u"
    assert session.log.read_bytes() == err.evidence.log.read_bytes()
    assert (session.subagents / "agent-x.jsonl").is_file()
    assert not session.result.exists()  # a partial capture: the report skips it
    stored = json.loads(session.unfolded.read_text(encoding="utf-8"))
    assert stored["error"] == str(err) and stored["case"]["name"] == "eval_ok"


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
    assert (record.node, record.wall_ms, record.at) == (run.plan.node, 4321, "2026-08-28T00:00:00+00:00")
    assert record.cache == str(tmp_path / "cache")
    assert CellMetrics.stored(session.history) == record


def test_a_treated_cell_stacks_its_overlay_and_counts_it_as_seeded(tmp_path: Path) -> None:
    """The agent found the treatment's files there, so a grader must not see them as written (ADR 0055)."""
    run = _cell_run(tmp_path)
    overlay = tmp_path / "skills" / "demo" / "evals" / "treatments" / "lean-ci"
    overlay.mkdir(parents=True)
    (overlay / "AGENTS.md").write_text("use cheap subagents\n", encoding="utf-8")
    run.plan = dataclasses.replace(
        run.plan, cell=Cell(harness="claude", model="claude-opus-5", treatment="lean-ci"), overlays=(overlay,)
    )
    workspace = run.materialise()
    assert workspace.name == "eval_ok-claude-claude-opus-5-lean-ci"
    assert (workspace / "AGENTS.md").is_file()
    assert run.output(_captured_run(tmp_path), workspace).seeded == {"README.md", "AGENTS.md"}
    assert run.session_dir("sid").rel.split("/")[2] == "claude-opus-5+lean-ci"


def test_a_finished_cell_tidies_its_workspace_unless_the_project_keeps_them(tmp_path: Path) -> None:
    run = _cell_run(tmp_path)
    workspace = run.materialise()
    run.tidy(workspace)
    assert not workspace.exists()
    kept = dataclasses.replace(run, settings=dataclasses.replace(run.settings, keep_workspaces=True))
    workspace = kept.materialise()
    kept.tidy(workspace)
    assert workspace.is_dir()


def test_a_run_that_never_reached_the_model_is_an_error_not_a_fail(tmp_path: Path) -> None:
    """A session limit attempted nothing, so it must not read as the skill failing (ADR 0063)."""
    run = _cell_run(tmp_path, grader=eval_fails)
    result = _captured_run(tmp_path)
    result.exit_code, result.calls = 1, []
    result.final_text = "You've hit your session limit · resets 2:10am"
    with pytest.raises(harness.RunError, match="never attempted: You've hit your session limit"):
        run.grade(result, run.materialise())
    assert run.verdict is Verdict.ERROR


def test_a_run_that_called_the_model_then_exited_non_zero_is_still_graded(tmp_path: Path) -> None:
    run = _cell_run(tmp_path, grader=eval_fails)
    result = _captured_run(tmp_path)
    result.exit_code, result.calls = 1, [Call(n=1, at="t")]
    assert result.attempted
    with pytest.raises(AssertionError):
        run.grade(result, run.materialise())
    assert run.verdict is Verdict.FAIL


@pytest.mark.parametrize(
    ("idle", "verdict", "raised", "match"),
    [
        (
            30.0,
            Verdict.FAIL,
            AssertionError,
            "did not complete within the 1200s timeout: the session was still active 30s",
        ),
        (299.0, Verdict.FAIL, AssertionError, "ran out of time"),
        (
            300.0,
            Verdict.ERROR,
            harness.RunError,
            "stalled: killed at the 1200s timeout after no session activity for 300s",
        ),
        (None, Verdict.ERROR, harness.RunError, "no session log at all"),
    ],
)
def test_a_run_killed_at_the_wall_fails_if_still_active_and_errors_if_stalled(
    tmp_path: Path, idle: float | None, verdict: Verdict, raised: type[Exception], match: str
) -> None:
    """Working when time ran out is a fail to complete in time; silent for five minutes is a stall (ADR 0064)."""
    run = _cell_run(tmp_path)  # a grader that would pass: the timeout decides before it runs
    result = _captured_run(tmp_path)
    result.calls = [Call(n=1, at="t")]
    harness.mark_timed_out(result, 1200, idle)
    with pytest.raises(raised, match=match):
        run.grade(result, run.materialise())
    assert run.verdict is verdict


# -- scenario cases and the failure reason (ADR 0074) ------------------------------


@pytest.mark.parametrize(
    ("exc", "line"),
    [
        (AssertionError("\n  doc.md still fails  \nsecond line"), "doc.md still fails"),
        (RuntimeError("boom"), "RuntimeError: boom"),
        (AssertionError(), "AssertionError"),
        (AssertionError("x" * 400), "x" * cellrun.FAILURE_CHARS),
    ],
    ids=["first-line", "typed", "empty", "truncated"],
)
def test_a_failure_line_is_the_first_thing_the_exception_says(exc: BaseException, line: str) -> None:
    assert cellrun.failure_line(exc) == line


@pytest.mark.parametrize(
    ("grader", "failure"),
    [(eval_ok, None), (eval_fails, "the agent did not do the thing"), (eval_errors, "RuntimeError: boom")],
)
def test_grading_records_why_a_cell_did_not_pass(tmp_path: Path, grader: Any, failure: str | None) -> None:
    run = _cell_run(tmp_path, grader)
    with contextlib.suppress(AssertionError, RuntimeError):
        run.grade(_captured_run(tmp_path), tmp_path / "ws")
    assert run.failure == failure


def eval_quotes_paths(output: CaseOutput) -> None:
    """A grader whose failure names the per-cell paths, as a seed check's message does."""
    ws = output.workspace
    raise RuntimeError(f"the seed {ws.parent}/.{ws.name}.scratch/a.md under {ws}/b.md in {ws.parents[1]}/c")


def test_a_recorded_failure_redacts_the_per_cell_paths_so_one_cause_groups_as_one(tmp_path: Path) -> None:
    run = _cell_run(tmp_path, eval_quotes_paths)
    workspace = tmp_path / "cache" / "build" / "eval_demo-claude-claude-opus-5"
    with contextlib.suppress(RuntimeError):
        run.grade(_captured_run(tmp_path), workspace)
    assert run.failure == "RuntimeError: the seed <scratch>/a.md under <workspace>/b.md in <cache>/c"
    # Redacted before truncation, longest path first, and nothing else touched.
    assert cellrun.redact("/a/b/c and /a/b", [("/a/b", "<x>"), ("/a/b/c", "<y>"), ("", "<z>")]) == "<y> and <x>"
    long = AssertionError(f"{workspace}/" + "x" * 400)
    assert (
        cellrun.failure_line(long, run.redactions(workspace)) == ("<workspace>/" + "x" * 400)[: cellrun.FAILURE_CHARS]
    )


SCENARIO = Scenario(generator="rows", params={"target": "doc.md"}, files={"doc.md": "# bad\n"}, label="doc")


def _scenario_run(tmp_path: Path, scenario: Scenario = SCENARIO) -> cellrun.CellRun:
    """A scenario case's cell: no skill, the subject is the tool's directory, the fixture a stored scenario."""
    cache = CacheLayout(tmp_path / "cache")
    table = Table(name="rows", rows=[dict(scenario.params)], build=lambda row: dict(scenario.files))
    return cellrun.CellRun(
        plan=CellPlan(
            case=evalcase(task="Clear every lint finding in doc.md", fixture=table)(eval_ok),
            cell=Cell(harness="codex", model="gpt-5.6-sol"),
            fixture_dir=write_scenario(scenario, cache.scenarios("eval_lint", "eval_ok")),
            node="n",
            suite="skills/lint/evals/eval_lint.py",
            subject="lint",
            scenario=scenario,
            subject_version="abc123",
        ),
        settings=settings.Settings(rootpath=tmp_path, skills_root=tmp_path / "skills", cache=cache),
    )


def test_a_scenario_cells_grader_reads_the_scenario_and_its_seed(tmp_path: Path) -> None:
    run = _scenario_run(tmp_path)
    workspace = run.materialise()
    output = run.output(_captured_run(tmp_path), workspace)
    assert output.scenario is SCENARIO and output.params == {"target": "doc.md"}
    assert output.seed("doc.md") == "# bad\n" and output.seeded == {"doc.md"}
    assert not any(p.name.endswith(".provenance.json") for p in workspace.iterdir())


def test_a_scenario_cell_stores_no_skill_coverage_or_skill_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cellrun.RUN_STAMP_ENV, "20261028T000000Z")
    result = _captured_run(tmp_path)
    result.harness, result.model = "codex", "gpt-5.6-sol"
    session = _scenario_run(tmp_path).store(result)
    assert session.rel == "lint/codex/gpt-5.6-sol/20261028T000000Z/sid-1"
    assert (result.skill_coverage, result.skill_use) == (None, None)
    assert result.case is not None and result.case.kind == "scenario"
