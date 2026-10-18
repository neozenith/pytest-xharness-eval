"""What one rollout left behind: the run record, and the workspace the agent wrote (ADR 0045).

A grader used to be handed two positional arguments, and they were never two things --
they were one rollout with no noun. Every suite in every consuming repository then
re-derived the same four lines of :mod:`pathlib` around the second of them, and reached
for ``.get()`` on the first because an undocumented payload looks like a mapping.

:class:`CaseOutput` is that pair named, with the accessors the copy-paste kept
re-deriving. It is the whole surface a grader sees, and ``docs/rollout.md`` documents it
field by field: :attr:`run` is the evidence the CLI produced, :attr:`workspace` is the
artifact it produced, and everything else here is a convenience over one of the two that
reads better in an assertion message than the expression it replaces.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.runresult import RunResult
    from pytest_xharness_eval.model.scenario import Scenario


@dataclass(frozen=True, slots=True)
class Seed:
    """The workspace as the agent will first find it, before anything has run (ADR 0074).

    What a case's ``precheck`` is handed: the materialised fixture (and any treatment over
    it) and the scenario that produced it. A precheck gates the *input* -- does this seed
    still reproduce the rule the case is about? -- so a broken fixture stops the cell before
    it spends, and ``--dry-run`` validates every fixture for free.
    """

    workspace: Path
    scenario: Scenario | None = None

    def path(self, rel: str) -> Path:
        """The absolute path of ``rel`` inside the seeded workspace."""
        return self.workspace / rel

    def read(self, rel: str) -> str:
        """The seeded text of ``rel``."""
        return self.path(rel).read_text(encoding="utf-8")

    @property
    def params(self) -> dict[str, Any]:
        """The scenario's parameters; a committed fixture has none, and asking raises."""
        if self.scenario is None:
            raise ValueError("this case runs on a committed fixture, which has no scenario params")
        return self.scenario.merged


@dataclass(frozen=True, slots=True)
class CaseOutput:
    """One rollout's outcome, as a grader sees it.

    Constructed by the cell that ran (and by a replay rebuilding one), never by a suite:
    a ``CaseOutput`` that does not name a real session is not an outcome (ADR 0002).
    """

    #: Everything the harness observed and the pipeline derived: usage, cost, the per-call
    #: ledger, skill coverage, the record census. See ``docs/rollout.md``.
    run: RunResult
    #: The directory the agent worked in: a fresh copy of the fixture tree (ADR 0004).
    workspace: Path
    #: The fixture's own file list, taken before the run. It is what makes :attr:`added`
    #: answerable: at grading time the workspace holds the seed and the writes mixed
    #: together, and only the collector knows which was which.
    seeded: frozenset[str] = frozenset()
    #: The generated scenario this rollout ran on, None for a committed fixture directory
    #: (ADR 0074). Its ``params`` are what the grader checks the outcome against, and its
    #: ``files`` are the seed exactly as the agent first saw it.
    scenario: Scenario | None = None

    # -- reaching into the workspace ---------------------------------------------------

    def path(self, rel: str) -> Path:
        """The absolute path of ``rel`` inside the workspace."""
        return self.workspace / rel

    def exists(self, rel: str) -> bool:
        """Whether ``rel`` exists in the workspace, as a file or a directory."""
        return self.path(rel).exists()

    def read(self, rel: str) -> str:
        """The text of ``rel``, decoded as UTF-8.

        Raises:
            AssertionError: if the file is absent, naming what the workspace does hold. A
                missing artifact is a fact about the skill, so it must read as a failed
                check and not as an ``OSError`` pytest renders as a harness error (ADR 0012).
        """
        target = self.path(rel)
        if not target.is_file():
            raise AssertionError(f"{rel} is not a file in the workspace; it holds: {self.filenames}")
        return target.read_text(encoding="utf-8")

    @property
    def filenames(self) -> list[str]:
        """Every file in the workspace, relative and sorted -- what the agent left behind."""
        return sorted(str(p.relative_to(self.workspace)) for p in self.workspace.rglob("*") if p.is_file())

    # -- what the run says it did ------------------------------------------------------

    def wrote(self, rel: str) -> bool:
        """Whether the run's file diff names ``rel`` as created or modified.

        Distinct from :meth:`exists`: a fixture file the agent never touched exists but was
        not written, which is the difference between "the artifact is there" and "this
        rollout produced it".
        """
        return rel in self.run.files_written

    @property
    def written(self) -> list[str]:
        """Every path the run created or modified, relative to the workspace."""
        return list(self.run.files_written)

    @property
    def added(self) -> list[str]:
        """Written paths the fixture did not seed: files this rollout brought into being."""
        return sorted(set(self.written) - self.seeded)

    @property
    def params(self) -> dict[str, Any]:
        """The scenario's parameters; a grader of a committed fixture that asks has a bug, so it raises."""
        if self.scenario is None:
            raise ValueError("this case runs on a committed fixture, which has no scenario params")
        return self.scenario.merged

    def seed(self, rel: str) -> str:
        """The text ``rel`` had before the agent touched it, read from the scenario or the seed list.

        The yardstick content-preservation checks compare the result with. Raises
        ValueError (a suite bug, so the cell errors) when the seed did not contain ``rel``.
        """
        if self.scenario is not None:
            if rel not in self.scenario.files:
                raise ValueError(f"{rel} was not part of the scenario; it seeded: {sorted(self.scenario.files)}")
            content = self.scenario.files[rel]
            return content.decode("utf-8") if isinstance(content, bytes) else content
        raise ValueError(
            "the seed text of a committed fixture is read from evals/fixtures/ by the suite itself; "
            "output.seed() answers only for a generated scenario"
        )

    @property
    def changed(self) -> list[str]:
        """Written paths the fixture did seed: files this rollout edited in place."""
        return sorted(set(self.written) & self.seeded)
