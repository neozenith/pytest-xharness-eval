"""The ``@evalcase`` decorator an ``eval_*.py`` module uses to declare its case (ADR 0008).

A case declares a *task*, never a prompt (ADR 0044). The task is the sentence a user
would type after naming the skill -- "Apply the palette mandate to ARCHITECTURE.md" --
and the harness renders it into that CLI's own invocation syntax when the cell runs.
Nothing here knows either syntax; :mod:`pytest_xharness_eval.model.registry` is the edge
that asks (ADR 0039).
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable

    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput

    Grader = Callable[[CaseOutput], None]


@dataclass
class EvalCase:
    """A case: one task, one skill under test, one fixture, and optionally its own matrix."""

    fn: Grader
    task: str
    skill: str
    fixture: str
    # None means inherit: the project's ``xharness_matrix`` ini key, else the plugin default.
    models: list[str] | None = None

    @property
    def name(self) -> str:
        """The grader function's name; the first half of every cell's node id."""
        return self.fn.__name__


def evalcase(
    *,
    task: str,
    skill: str,
    fixture: str,
    models: list[str] | None = None,
    **removed: Any,
) -> Callable[[Grader], EvalCase]:
    """Wrap a grader function with its declarative case definition.

    Args:
        task: What to do, as a user would say it *after* naming the skill. It must not
            name the skill, a CLI, or where a ``SKILL.md`` can be found: each harness
            renders its own invocation around this sentence (ADR 0044).
        skill: The skill under test, a directory name under the skills root.
        fixture: The seed workspace's name under ``evals/fixtures/`` (ADR 0018).
        models: ``harness/model`` entries to sweep. Omit to inherit the project matrix
            (``xharness_matrix`` in the pytest config) or, failing that, the plugin default.

    Raises:
        TypeError: if ``prompt=`` is passed. It is not accepted as an alias for ``task``,
            because the prompts it named all opened by explaining the harness to the agent,
            and an alias would carry that sentence through the upgrade untouched (ADR 0044).
    """
    if "prompt" in removed:
        raise TypeError(
            "@evalcase takes task=, not prompt= (ADR 0044). The task is what a user types "
            "*after* naming the skill; each harness renders its own invocation around it "
            "(claude: '/<skill> <task>', codex: '$<skill> <task>'). Drop any 'use the X "
            "skill / its SKILL.md is in ...' preamble -- that is the harness's job now."
        )
    if removed:
        raise TypeError(f"@evalcase got unexpected keyword argument(s): {', '.join(sorted(removed))}")

    def wrap(fn: Grader) -> EvalCase:
        return EvalCase(fn=fn, task=task, skill=skill, fixture=fixture, models=list(models) if models else None)

    return wrap
