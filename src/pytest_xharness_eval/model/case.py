"""The ``@evalcase`` decorator an ``eval_*.py`` module uses to declare its case (ADR 0008).

A case declares a *task*, never a prompt (ADR 0044). There are two kinds (ADR 0074):

* a **skill** case names ``skill=``, and the task is the sentence a user would type after
  naming the skill -- "Apply the palette mandate to ARCHITECTURE.md". Each harness renders
  it into that CLI's own invocation syntax when the cell runs; nothing here knows either
  syntax, and :mod:`pytest_xharness_eval.model.registry` is the edge that asks (ADR 0039).
* a **scenario** case names no skill. Its task is sent verbatim, the same words on every
  harness, and no skill is registered with the CLI: it measures how well the agent copes
  with the situation the fixture sets up -- a linter CLI whose findings it must clear, say
  -- rather than how well a skill is followed.

Either kind runs on a committed fixture directory or on the scenarios a
:class:`~pytest_xharness_eval.model.scenario.FixtureGenerator` yields.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.model.scenario import FixtureGenerator

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Sequence

    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput, Seed
    from pytest_xharness_eval.model.scenario import Scenario

    Grader = Callable[[CaseOutput], None]
    Precheck = Callable[[Seed], None]


class CaseKind(StrEnum):
    """Whether a case invokes a skill or sends its task as it stands (ADR 0074)."""

    SKILL = "skill"
    SCENARIO = "scenario"


@dataclass
class EvalCase:
    """A case: one task, at most one skill under test, a fixture or its generator, and optionally its own matrix."""

    fn: Grader
    # None only for a generated case whose every scenario names its own task (ADR 0074).
    task: str | None
    fixture: str | FixtureGenerator
    skill: str | None = None
    # None means inherit: the project's ``xharness_matrix`` ini key, else the plugin default.
    models: list[str] | None = None
    # None means inherit: the project's ``xharness_treatments`` ini key, else none at all.
    # The control is never listed here; it is always swept (ADR 0055).
    treatments: list[str] | None = None
    # Paths, relative to the project root, whose content is the version of the subject under
    # test (ADR 0074). None means the skill's own directory for a skill case, and nothing for
    # a scenario case, which then records no version.
    tracks: tuple[str, ...] | None = None
    # Gates the seeded workspace before the CLI is invoked, and under --dry-run (ADR 0074):
    # a seed that no longer reproduces what the case is about errors the cell unpaid.
    precheck: Precheck | None = None

    @property
    def name(self) -> str:
        """The grader function's name; the first half of every cell's node id."""
        return self.fn.__name__

    def task_for(self, scenario: Scenario | None) -> str:
        """The task one cell is sent: its scenario's own, else the case's."""
        task = scenario.task if scenario is not None and scenario.task else self.task
        if task is None:
            raise ValueError(
                f"{self.name}: scenario {scenario.id if scenario else '?'} names no task and the case declares none"
            )
        return task

    @property
    def kind(self) -> CaseKind:
        return CaseKind.SKILL if self.skill else CaseKind.SCENARIO

    @property
    def generator(self) -> FixtureGenerator | None:
        """The fixture generator, or None for a committed fixture directory."""
        return self.fixture if isinstance(self.fixture, FixtureGenerator) else None

    @property
    def fixture_name(self) -> str:
        """The committed fixture's directory name, or the generator's name."""
        return self.fixture if isinstance(self.fixture, str) else self.fixture.name


def evalcase(
    *,
    fixture: str | FixtureGenerator,
    task: str | None = None,
    skill: str | None = None,
    models: list[str] | None = None,
    treatments: list[str] | None = None,
    tracks: Sequence[str] | None = None,
    precheck: Precheck | None = None,
    **removed: Any,
) -> Callable[[Grader], EvalCase]:
    """Wrap a grader function with its declarative case definition.

    Args:
        task: What to do. For a skill case, what a user types *after* naming the skill: it
            must not name the skill, a CLI, or where a ``SKILL.md`` can be found, because each
            harness renders its own invocation around it (ADR 0044). For a scenario case, the
            whole prompt, sent unchanged to every harness.
        fixture: The seed workspace's name under ``evals/fixtures/`` (ADR 0018), or a
            :class:`FixtureGenerator` whose scenarios each become a cell (ADR 0074).
        skill: The skill under test, a directory name under the skills root. Omit it for a
            scenario case.
        models: ``harness/model`` entries to sweep. Omit to inherit the project matrix
            (``xharness_matrix`` in the pytest config) or, failing that, the plugin default.
        treatments: Names under ``evals/treatments/`` to sweep beside the untreated control
            (ADR 0055). Omit to inherit ``xharness_treatments``.
        tracks: Paths relative to the project root whose content digest is recorded as the
            subject's version on every record, so the Analyzer can compare versions of the
            tool or skill under test. Defaults to the skill's directory for a skill case.
        precheck: A function over the :class:`~pytest_xharness_eval.model.output.Seed` that
            raises when the seed is unfit -- typically ``require_seed_fails``. It runs after the
            workspace is materialised and before the paid invoke, and under ``--dry-run``; a
            raise errors the cell without spending.

    Raises:
        TypeError: if ``prompt=`` is passed, which is not an alias for ``task`` (ADR 0044),
            or on any other unknown keyword.
    """
    if "prompt" in removed:
        raise TypeError(
            "@evalcase takes task=, not prompt= (ADR 0044). The task is what a user types "
            "*after* naming the skill; each harness renders its own invocation around it "
            "(claude: '/<skill> <task>', codex: '$<skill> <task>'). Drop any 'use the X "
            "skill / its SKILL.md is in ...' preamble -- that is the harness's job now. "
            "A case that names no skill= sends its task verbatim (ADR 0074)."
        )
    if removed:
        raise TypeError(f"@evalcase got unexpected keyword argument(s): {', '.join(sorted(removed))}")
    if task is None and isinstance(fixture, str):
        raise TypeError(
            "@evalcase needs task= for a committed fixture; only a generator's scenarios may each carry their own"
        )
    if not isinstance(fixture, str | FixtureGenerator):
        raise TypeError(
            f"@evalcase fixture= takes a directory name or a FixtureGenerator (a name, a may_be_empty flag "
            f"and scenarios(context)), got {fixture!r}"
        )

    def wrap(fn: Grader) -> EvalCase:
        return EvalCase(
            fn=fn,
            task=task,
            fixture=fixture,
            skill=skill or None,
            models=list(models) if models else None,
            treatments=list(treatments) if treatments else None,
            tracks=tuple(tracks) if tracks else None,
            precheck=precheck,
        )

    return wrap
