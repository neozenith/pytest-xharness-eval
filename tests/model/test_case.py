"""``model.case``: what an ``@evalcase`` declares."""


# Standard Library

# Third Party

# Our Libraries
from pytest_xharness_eval import (
    CaseOutput,
    EvalCase,
    evalcase,
)


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
