"""One cell's live run: the sequence around the one call that spends money (ADR 0002, ADR 0040).

A cell is a (case, harness, model) triple, and running it is always the same seven steps:
stamp the run, copy the fixture into a fresh workspace, invoke the CLI, derive everything
derivable from what came back, write the evidence, grade it, record the metrics. Exactly
one of those steps spawns a paid process, and it used to be inside a forty-line
``# pragma: no cover`` block that took the other six with it -- so the ordering that a
replay is pinned against could not be exercised at all without spending (ADR 0034).

Here each step is a method. :meth:`CellRun.invoke` is the paid one and is the only method
that carries the pragma; the rest are exercised directly from captured logs in
``tests/test_units.py``. Nothing is mocked to achieve that: the workspace is really
copied, the grader really runs, and the record is really written -- what the tests do not
do is spawn a CLI, which is what ADR 0002 forbids faking.
"""

from __future__ import annotations

# Standard Library
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.emit.metrics import Outcome
from pytest_xharness_eval.model import workspace as ws
from pytest_xharness_eval.model.clock import now_iso
from pytest_xharness_eval.model.output import CaseOutput
from pytest_xharness_eval.model.runresult import CaseRef
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin.results import RECORD_KEY
from pytest_xharness_eval.runtime import pipeline

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Third Party
    import pytest

    # Our Libraries
    from pytest_xharness_eval.derive.skillcov import SkillFile
    from pytest_xharness_eval.emit.metrics import CellMetrics
    from pytest_xharness_eval.model.case import EvalCase
    from pytest_xharness_eval.model.layout import LocatedSession
    from pytest_xharness_eval.model.matrix import Cell
    from pytest_xharness_eval.model.runresult import RunResult
    from pytest_xharness_eval.runtime.settings import Settings

# One UTC stamp per pytest session, exported so that xdist workers -- which are child
# processes -- agree with the controller and a sweep's cells share one ``{run}`` level.
RUN_STAMP_ENV = "XHARNESS_EVAL_RUN_TS"


def run_stamp() -> str:
    """This sweep's run stamp: path-safe, sortable, and minted at most once per session.

    The first caller mints it into the environment and every later one -- in this process
    or in an xdist worker started from it -- reads that same value back, which is what puts
    a run's cells under one ``results/{...}/{run}/`` directory (ADR 0032).
    """
    stamp = os.environ.get(RUN_STAMP_ENV)
    if not stamp:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        os.environ[RUN_STAMP_ENV] = stamp
    return stamp


@dataclass(frozen=True, slots=True, kw_only=True)
class Attempt:
    """What one invocation of a CLI produced, with the two clock facts no log carries."""

    result: RunResult
    started_at: str
    wall_ms: int


@dataclass(slots=True, kw_only=True)
class CellRun:
    """One cell's live run in progress: what it needs, what it did, and what it left behind.

    Everything it needs is resolved off the item once, at construction; the mutable
    :attr:`verdict` is the one thing that is not known until the grader has run. It starts
    at ``ERROR`` because a run that has not reached its grader has not passed.
    """

    case: EvalCase
    cell: Cell
    settings: Settings
    skill_dir: Path
    fixture_dir: Path
    node: str
    suite: str
    skill_files: list[SkillFile] = field(default_factory=list)
    verdict: Verdict = Verdict.ERROR

    # -- the steps ---------------------------------------------------------------------

    @property
    def cell_id(self) -> str:
        """The workspace name for this cell: case, harness and model, path-safe."""
        return f"{self.case.name}-{self.cell.harness}-{self.cell.model}"

    def materialise(self) -> Path:
        """A fresh copy of the fixture tree under ``<cache>/build/``, for this cell alone (ADR 0004)."""
        return ws.materialise(self.fixture_dir, self.cell_id, self.settings.cache.build)

    @property
    def prompt(self) -> str:
        """This cell's invocation: the case's task in this harness's own syntax (ADR 0044).

        A property rather than a field because it is a pure function of the cell, and free:
        a ``--dry-run`` preview and the stored :class:`CaseRef` must show the same string
        the CLI is about to be handed, not a second rendering of it.
        """
        return harness.get(self.cell.harness).invoke(skill=self.case.skill, task=self.case.task)

    def invoke(self, workspace: Path) -> Attempt:  # pragma: no cover - spawns a paid CLI (ADR 0002)
        """Run the harness's CLI in ``workspace``: the one step of a sweep that spends money.

        The wall clock is measured around the call and not derived from the session log,
        because it is the only measure that includes the CLI's own startup and teardown.
        """
        started_at = now_iso()
        t0 = time.monotonic()
        result = harness.get(self.cell.harness).run(
            prompt=self.prompt, model=self.cell.model, workspace=workspace, skill_dir=self.skill_dir
        )
        return Attempt(result=result, started_at=started_at, wall_ms=int((time.monotonic() - t0) * 1000))

    def session_dir(self, session_id: str) -> LocatedSession:
        """Where this cell's evidence goes: its five coordinates under ``<cache>/results/``."""
        return self.settings.cache.session(
            skill=self.case.skill,
            harness=self.cell.harness,
            model=self.cell.model,
            run=run_stamp(),
            session=session_id,
        )

    def store(self, result: RunResult) -> LocatedSession:
        """Derive everything derivable, then write the evidence: the replayed sequence (ADR 0034).

        From here on a live cell does exactly what a replay of its capture does, in the
        same order and through the same two calls, which is the invariant
        ``tests/test_characterization.py`` pins.
        """
        pipeline.derive(
            result,
            table=self.settings.price_table(),
            skill=self.case.skill,
            skill_files=self.skill_files,
            case=CaseRef.of(self.case, self.suite, self.prompt),
        )
        session = self.session_dir(result.session_id)
        pipeline.capture(result, session)
        return session

    def output(self, result: RunResult, workspace: Path) -> CaseOutput:
        """The rollout as the grader sees it: the record, the workspace, and the seed list.

        ``seeded`` is taken from the fixture tree rather than the workspace, because by
        grading time the two are mixed together and only this side knows which was which
        (ADR 0045).
        """
        seeded = frozenset(str(p.relative_to(self.fixture_dir)) for p in self.fixture_dir.rglob("*") if p.is_file())
        return CaseOutput(run=result, workspace=workspace, seeded=seeded)

    def grade(self, result: RunResult, workspace: Path) -> Verdict:
        """Run the case's grader over the finished run, and name what happened.

        The verdict is recorded on this run *before* the grader's exception leaves, because
        a failed cell still has to emit its record: an assertion is a ``fail``, anything
        else is an ``error``, and either way pytest gets the original exception (ADR 0012).
        """
        try:
            self.case.fn(self.output(result, workspace))
        except AssertionError:
            self.verdict = Verdict.FAIL
            raise
        except Exception:
            self.verdict = Verdict.ERROR
            raise
        self.verdict = Verdict.PASS
        return self.verdict

    def record(self, attempt: Attempt, session: LocatedSession) -> CellMetrics:
        """This cell's metrics record, written beside its evidence (ADR 0018)."""
        return pipeline.record_metrics(
            attempt.result,
            session,
            outcome=Outcome(
                node=self.node,
                verdict=self.verdict,
                wall_ms=attempt.wall_ms,
                started_at=attempt.started_at,
            ),
            cache=self.settings.cache,
        )

    # -- the sequence ------------------------------------------------------------------

    def execute(self, stash: pytest.Stash) -> None:  # pragma: no cover - invoke() spends (ADR 0002)
        """Run the cell and leave its record in ``stash``, whatever the grader decided.

        The record is written in a ``finally`` because a failing cell is the case a metrics
        history exists for: a sweep that only recorded its passes would show cost dropping
        as quality dropped.
        """
        workspace = self.materialise()
        attempt = self.invoke(workspace)
        session = self.store(attempt.result)
        try:
            self.grade(attempt.result, workspace)
        finally:
            stash[RECORD_KEY] = self.record(attempt, session)
