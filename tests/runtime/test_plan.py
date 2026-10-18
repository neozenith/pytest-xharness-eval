"""``runtime.plan``: what collection resolves for one cell, and the names and prompt derived from it (ADR 0074)."""

# Standard Library
import dataclasses
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import CaseOutput, Cell, evalcase
from pytest_xharness_eval.model.generators import Table
from pytest_xharness_eval.model.scenario import Scenario
from pytest_xharness_eval.runtime.plan import CellPlan

SCENARIO = Scenario(generator="rows", params={"target": "doc.md"}, files={"doc.md": "# bad\n"}, label="doc")


def eval_thing(output: CaseOutput) -> None:
    """A grader the plans below never run."""


def _skill_plan(**overrides: object) -> CellPlan:
    fields: dict[str, object] = {
        "case": evalcase(task="t", skill="s", fixture="f")(eval_thing),
        "cell": Cell(harness="claude", model="opus"),
        "node": "skills/s/evals/eval_x.py::eval_thing[claude/opus]",
        "suite": "skills/s/evals/eval_x.py",
        "subject": "s",
        "fixture_dir": Path("f"),
    }
    return CellPlan(**{**fields, **overrides})  # type: ignore[arg-type]


def _scenario_plan(scenario: Scenario = SCENARIO) -> CellPlan:
    table = Table(name="rows", rows=[dict(scenario.params)], build=lambda row: dict(scenario.files))
    return CellPlan(
        case=evalcase(task="Clear every lint finding in doc.md", fixture=table)(eval_thing),
        cell=Cell(harness="codex", model="gpt-5.6-sol"),
        node="n",
        suite="skills/lint/evals/eval_lint.py",
        subject="lint",
        fixture_dir=Path("store") / scenario.id,
        scenario=scenario,
        subject_version="abc123",
    )


def test_two_cells_of_one_case_differing_only_in_effort_or_repeat_get_their_own_workspaces() -> None:
    """A shared build directory would have the pair overwrite each other's workspace."""
    names = {
        _skill_plan(cell=Cell(harness="claude", model="opus", effort=rung)).cell_id for rung in ("high", "low", None)
    }
    assert names == {"eval_thing-claude-opus-high", "eval_thing-claude-opus-low", "eval_thing-claude-opus"}
    assert _skill_plan(sample=2).cell_id == "eval_thing-claude-opus-r2"


def test_the_items_name_is_the_last_part_of_its_node_id() -> None:
    assert _skill_plan().name == "eval_thing[claude/opus]"


def test_a_skill_plan_renders_the_harnesss_own_invocation() -> None:
    plan = _skill_plan()
    assert plan.prompt == "/s t" == plan.case_ref.prompt
    assert (plan.case_ref.suite, plan.case_ref.kind) == ("skills/s/evals/eval_x.py", "skill")


def test_a_scenario_plan_is_named_for_its_scenario_and_sends_the_task_verbatim() -> None:
    plan = _scenario_plan()
    assert plan.cell_id == f"eval_thing-{SCENARIO.id}-codex-gpt-5.6-sol"
    # No `$<skill>` prefix: every harness is sent the same words (ADR 0074).
    assert plan.prompt == "Clear every lint finding in doc.md"
    ref = plan.case_ref
    assert (ref.kind, ref.subject, ref.fixture, ref.scenario, ref.subject_version) == (
        "scenario",
        "lint",
        "rows",
        SCENARIO.id,
        "abc123",
    )
    assert (ref.scenario_fingerprint, ref.scenario_params) == (SCENARIO.fingerprint, {"target": "doc.md"})


def test_a_scenarios_own_task_replaces_the_cases() -> None:
    plan = _scenario_plan(dataclasses.replace(SCENARIO, task="Fix doc.md and nothing else"))
    assert plan.prompt == "Fix doc.md and nothing else" == plan.case_ref.task
