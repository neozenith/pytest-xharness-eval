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
