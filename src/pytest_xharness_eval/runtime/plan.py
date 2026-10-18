"""What collection resolves for one cell, once, before anything runs (ADR 0074, ADR 0075).

A cell is a case crossed with a scenario, a matrix point and a repeat. Everything the run
needs to know about that crossing -- the subject and its version, the suite as records name
it, the fixture directory, the treatment's overlays, the skill's catalogued files, the
prompt each harness is sent -- is settled at collection and frozen here, so the pytest item,
the dry-run preview and the live run read one value rather than each re-deriving a part.

The plan lives in ``runtime/`` because it is built from :class:`~.settings.Settings` and
names a :class:`~pytest_xharness_eval.derive.skillcov.SkillFile` and a harness's prompt
rendering: ``model/`` may name neither ``derive/`` nor ``harness/`` (ADR 0039), and the
plugin entry point is above every layer that might want to build one, a replay included.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.model.runresult import CaseRef

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.derive.skillcov import SkillFile
    from pytest_xharness_eval.model.case import EvalCase
    from pytest_xharness_eval.model.matrix import Cell
    from pytest_xharness_eval.model.scenario import Scenario


@dataclass(frozen=True, slots=True, kw_only=True)
class CellPlan:
    """One collected cell: the case, its scenario and matrix point, and what they resolve to.

    ``node`` is the item's node id without xdist's ``@<group>`` suffix, so a record keys the
    same with or without ``-n``. ``skill_dir`` is None for a scenario case, which registers
    no skill (ADR 0074). ``sample`` is the repeat this cell is under ``--xharness-repeat``,
    None when it runs once (ADR 0075).
    """

    case: EvalCase
    cell: Cell
    node: str
    suite: str
    #: The directory the suite's ``evals/`` sits under: the skill, or a scenario's tool (ADR 0074).
    subject: str
    fixture_dir: Path
    skill_dir: Path | None = None
    #: The treatment's directories, copied over the fixture in order; empty for the control (ADR 0055).
    overlays: tuple[Path, ...] = ()
    #: The skill's catalogued files (ADR 0022), the same inventory for every cell of the sweep.
    skill_files: tuple[SkillFile, ...] = ()
    scenario: Scenario | None = None
    subject_version: str | None = None
    sample: int | None = None

    @property
    def name(self) -> str:
        """The item's name: ``<case>[<scenario>/<cell>]`` with a ``#<sample>`` suffix under repeats."""
        return self.node.rsplit("::", 1)[-1]

    @property
    def cell_id(self) -> str:
        """The workspace name for this cell: case, scenario, harness, model, effort, treatment, repeat; path-safe.

        The effort rung and the treatment are part of the name because two cells of one
        sweep may differ in nothing else, and a shared workspace name would have them
        overwrite each other's build directory (ADR 0049, ADR 0055).
        """
        rung = f"-{self.cell.effort}" if self.cell.effort else ""
        treated = f"-{self.cell.treatment}" if self.cell.treatment else ""
        scenario = f"-{self.scenario.id}" if self.scenario else ""
        repeat = f"-r{self.sample}" if self.sample else ""
        return f"{self.case.name}{scenario}-{self.cell.harness}-{self.cell.model}{rung}{treated}{repeat}"

    @property
    def prompt(self) -> str:
        """This cell's invocation: the case's task in this harness's own syntax (ADR 0044).

        A property because it is a pure function of the plan: the ``--dry-run`` preview and
        the stored :class:`CaseRef` show the same string the CLI is handed.
        """
        return harness.get(self.cell.harness).prompt(skill=self.case.skill, task=self.case.task_for(self.scenario))

    @property
    def case_ref(self) -> CaseRef:
        """The case reference this cell's result carries: the case, its scenario, the subject's version."""
        return CaseRef.of(
            self.case,
            self.suite,
            self.prompt,
            subject=self.subject,
            scenario=self.scenario,
            subject_version=self.subject_version,
        )
