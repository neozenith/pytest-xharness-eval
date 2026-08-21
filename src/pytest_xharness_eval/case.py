"""The ``@evalcase`` decorator an ``eval_*.py`` module uses to declare its case (ADR 0008)."""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

    Grader = Callable[[RunResult, Path], object]


@dataclass
class EvalCase:
    """A case: one prompt, one skill under test, one fixture, and optionally its own matrix."""

    fn: Grader
    prompt: str
    skill: str
    fixture: str
    # None means inherit: the project's ``xharness_matrix`` ini key, else the plugin default.
    models: list[str] | None = None

    @property
    def name(self) -> str:
        """The grader function's name; the first half of every cell's node id."""
        return self.fn.__name__


def evalcase(*, prompt: str, skill: str, fixture: str, models: list[str] | None = None) -> Callable[[Grader], EvalCase]:
    """Wrap a grader function with its declarative case definition.

    Args:
        prompt: The instruction sent to the agent CLI.
        skill: The skill under test, a directory name under the skills root.
        fixture: The seed workspace's name under ``evals/fixtures/`` (ADR 0018).
        models: ``harness/model`` entries to sweep. Omit to inherit the project matrix
            (``xharness_matrix`` in the pytest config) or, failing that, the plugin default.
    """

    def wrap(fn: Grader) -> EvalCase:
        return EvalCase(fn=fn, prompt=prompt, skill=skill, fixture=fixture, models=list(models) if models else None)

    return wrap
