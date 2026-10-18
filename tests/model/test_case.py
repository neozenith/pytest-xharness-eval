"""``model.case``: what an ``@evalcase`` declares."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    CaseOutput,
    EvalCase,
    evalcase,
)
from pytest_xharness_eval.model.case import CaseKind
from pytest_xharness_eval.model.generators import Table
from pytest_xharness_eval.model.output import Seed
from pytest_xharness_eval.model.scenario import Scenario


def test_evalcase_without_models_inherits() -> None:
    @evalcase(task="p", skill="s", fixture="f")
    def eval_thing(output: CaseOutput) -> None:
        pass

    assert isinstance(eval_thing, EvalCase)
    assert eval_thing.name == "eval_thing"
    assert eval_thing.models is None


def test_evalcase_override_is_copied() -> None:
    models = ["codex/gpt-5.6-luna"]

    @evalcase(task="p", skill="s", fixture="f", models=models)
    def eval_thing(output: CaseOutput) -> None:
        pass

    assert eval_thing.models == models
    assert eval_thing.models is not models


def test_evalcase_treatments_default_to_inherit_and_are_copied() -> None:
    treatments = ["lean-ci"]

    @evalcase(task="p", skill="s", fixture="f", treatments=treatments)
    def eval_treated(output: CaseOutput) -> None:
        pass

    @evalcase(task="p", skill="s", fixture="f")
    def eval_plain(output: CaseOutput) -> None:
        pass

    assert eval_treated.treatments == treatments
    assert eval_treated.treatments is not treatments
    assert eval_plain.treatments is None


def test_a_case_without_a_skill_is_a_scenario_case() -> None:
    """No skill names nothing to register with the CLI: the task is sent as it stands (ADR 0074)."""

    @evalcase(task="Clear every finding in doc.md", fixture="seed")
    def eval_tool(output: CaseOutput) -> None:
        pass

    @evalcase(task="p", skill="s", fixture="f")
    def eval_skill(output: CaseOutput) -> None:
        pass

    assert (eval_tool.kind, eval_tool.skill) == (CaseKind.SCENARIO, None)
    assert eval_skill.kind is CaseKind.SKILL and eval_skill.kind.value == "skill"
    assert evalcase(task="p", skill="", fixture="f")(eval_tool.fn).kind is CaseKind.SCENARIO


def test_a_fixture_is_a_directory_name_or_a_generator() -> None:
    table = Table(name="rows", rows=[{"n": 1}], build=lambda row: {"a.md": "x"})

    @evalcase(task="p", fixture=table)
    def eval_generated(output: CaseOutput) -> None:
        pass

    @evalcase(task="p", fixture="seed")
    def eval_committed(output: CaseOutput) -> None:
        pass

    assert (eval_generated.generator, eval_generated.fixture_name) == (table, "rows")
    assert (eval_committed.generator, eval_committed.fixture_name) == (None, "seed")
    with pytest.raises(TypeError, match="directory name or a FixtureGenerator"):
        evalcase(task="p", fixture=42)  # type: ignore[arg-type]

    class Undeclared:
        """A generator that never said whether an empty sweep is an answer: refused, not guessed."""

        name = "undeclared"

        def scenarios(self, context: object) -> list[object]:
            return []

    with pytest.raises(TypeError, match="may_be_empty"):
        evalcase(task="p", fixture=Undeclared())  # type: ignore[arg-type]


def test_tracks_is_copied_to_a_tuple_and_defaults_to_none() -> None:
    paths = ["tools/lint", "package.json"]

    @evalcase(task="p", fixture="f", tracks=paths)
    def eval_tracked(output: CaseOutput) -> None:
        pass

    assert eval_tracked.tracks == ("tools/lint", "package.json")
    assert evalcase(task="p", fixture="f")(eval_tracked.fn).tracks is None


def test_unknown_keywords_and_prompt_are_refused() -> None:
    with pytest.raises(TypeError, match="verbatim"):
        evalcase(task="p", fixture="f", prompt="x")
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        evalcase(task="p", fixture="f", subject="x")


def test_a_committed_fixture_needs_a_task_and_a_generator_may_leave_it_to_its_scenarios() -> None:
    """Only a generator's scenarios can each carry their own task (ADR 0074)."""
    with pytest.raises(TypeError, match="needs task= for a committed fixture"):
        evalcase(fixture="seed")
    rows = Table(name="rows", rows=[{"n": 1}], build=lambda row: {"a.md": "x"})

    @evalcase(fixture=rows)
    def eval_untasked(output: CaseOutput) -> None:
        pass

    assert eval_untasked.task is None


def test_task_for_prefers_the_scenarios_own_task_and_raises_when_neither_names_one() -> None:
    own = Scenario(generator="g", params={"n": 1}, files={"a.md": "x"}, task="Fix a.md")
    bare = Scenario(generator="g", params={"n": 2}, files={"a.md": "x"})
    rows = Table(name="rows", rows=[{"n": 1}], build=lambda row: {"a.md": "x"})

    @evalcase(task="Fix it", fixture=rows)
    def eval_tasked(output: CaseOutput) -> None:
        pass

    @evalcase(fixture=rows)
    def eval_untasked(output: CaseOutput) -> None:
        pass

    assert (eval_tasked.task_for(own), eval_tasked.task_for(bare), eval_tasked.task_for(None)) == (
        "Fix a.md",
        "Fix it",
        "Fix it",
    )
    assert eval_untasked.task_for(own) == "Fix a.md"
    with pytest.raises(ValueError, match=f"scenario {bare.id} names no task"):
        eval_untasked.task_for(bare)
    with pytest.raises(ValueError, match=r"scenario \? names no task"):
        eval_untasked.task_for(None)


def test_a_precheck_is_kept_on_the_case_and_defaults_to_none() -> None:
    def gate(seed: Seed) -> None:
        pass

    @evalcase(task="p", fixture="f", precheck=gate)
    def eval_gated(output: CaseOutput) -> None:
        pass

    assert eval_gated.precheck is gate
    assert evalcase(task="p", fixture="f")(eval_gated.fn).precheck is None
