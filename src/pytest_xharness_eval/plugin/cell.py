"""One cell's live run: the sequence around the one call that spends money (ADR 0002, ADR 0040).

A cell is a (case, harness, model, effort, treatment) point, and running it is always the
same seven steps: stamp the run, copy the fixture (and any treatment over it) into a fresh
workspace, invoke the CLI, derive everything derivable from what came back, write the
evidence, grade it, record the metrics. Exactly one of those steps spawns a paid process,
and it used to be inside a forty-line ``# pragma: no cover`` block that took the other six
with it -- so the ordering that a replay is pinned against could not be exercised at all
without spending (ADR 0034).

Here each step is a method. :meth:`CellRun.invoke` is the paid one and is the only method
that carries the pragma; the rest are exercised directly from captured logs in
``tests/plugin/test_cell.py``. Nothing is mocked to achieve that: the workspace is really
copied, the grader really runs, and the record is really written -- what the tests do not
do is spawn a CLI, which is what ADR 0002 forbids faking.
"""

from __future__ import annotations

# Standard Library
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.emit.metrics import Outcome
from pytest_xharness_eval.model import workspace as ws
from pytest_xharness_eval.model.clock import now_iso
from pytest_xharness_eval.model.output import CaseOutput, Seed
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin.results import RECORD_KEY
from pytest_xharness_eval.runtime import pipeline

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Sequence
    from pathlib import Path

    # Third Party
    import pytest

    # Our Libraries
    from pytest_xharness_eval.emit.metrics import CellMetrics
    from pytest_xharness_eval.model.layout import LocatedSession
    from pytest_xharness_eval.model.runresult import RunResult
    from pytest_xharness_eval.runtime.plan import CellPlan
    from pytest_xharness_eval.runtime.settings import Settings

# One UTC stamp per pytest session, exported so that xdist workers -- which are child
# processes -- agree with the controller and a sweep's cells share one ``{run}`` level.
RUN_STAMP_ENV = "XHARNESS_EVAL_RUN_TS"

#: A run killed at the wall whose session logs had been silent this long had stalled (ADR 0064).
#: Inside it the agent was still working when time ran out.
STALLED_AFTER_S = 300


def check_completed(result: RunResult) -> None:
    """Refuse a run the CLI was killed for at the wall-clock limit, with the verdict its cause earns.

    Still active within :data:`STALLED_AFTER_S` of the wall, the agent was working and simply
    ran out of time: a ``fail`` to complete in a timely manner, which a longer
    ``xharness_timeout_s`` might turn into a pass. Silent for longer, something stalled (a skill
    script, the harness, the network): an ``error`` to investigate, because a stalled run is not
    a clean run of the skill to call failed. A run with no log at all had no activity to show.
    """
    if result.timed_out_after_s is None:
        return
    idle = result.idle_before_timeout_s
    limit = result.timed_out_after_s
    if idle is not None and idle < STALLED_AFTER_S:
        raise AssertionError(
            f"did not complete within the {limit}s timeout: the session was still active {idle:.0f}s "
            "before the wall, so it ran out of time (raise xharness_timeout_s to let it finish)"
        )
    silent = f"no session activity for {idle:.0f}s" if idle is not None else "no session log at all"
    raise harness.RunError(f"stalled: killed at the {limit}s timeout after {silent} (ADR 0064)")


#: How much of a failure's message a record keeps: enough to group failures by, no more.
FAILURE_CHARS = 300


def redact(text: str, replacements: Sequence[tuple[str, str]]) -> str:
    """``text`` with each path of ``replacements`` replaced by its token, longest path first.

    Longest first, so a path inside another (the cache root inside a workspace under it) is
    never replaced before the path that contains it.
    """
    for path, token in sorted(replacements, key=lambda pair: -len(pair[0])):
        if path:
            text = text.replace(path, token)
    return text


def failure_line(exc: BaseException, replacements: Sequence[tuple[str, str]] = ()) -> str:
    """The first non-empty line of what ``exc`` says, prefixed with its type for anything but an assertion.

    ``replacements`` are redacted (:func:`redact`) before the line is truncated, so a path
    that differs per cell cannot split one cause into as many groups as there were cells.
    """
    text = next((line.strip() for line in str(exc).splitlines() if line.strip()), "")
    prefix = "" if isinstance(exc, AssertionError) else f"{type(exc).__name__}: "
    return redact(prefix + text, replacements)[:FAILURE_CHARS] or type(exc).__name__


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

    Everything it needs was resolved at collection and arrives as one frozen
    :class:`~pytest_xharness_eval.runtime.plan.CellPlan`; the mutable :attr:`verdict` is the
    one thing that is not known until the grader has run. It starts at ``ERROR`` because a
    run that has not reached its grader has not passed.
    """

    plan: CellPlan
    settings: Settings
    verdict: Verdict = Verdict.ERROR
    # The first line of what the grader or harness raised, recorded with the verdict.
    failure: str | None = None

    # -- the steps ---------------------------------------------------------------------

    def materialise(self) -> Path:
        """A fresh copy of the fixture, then the treatment over it, under ``<cache>/build/`` (ADR 0004, ADR 0055)."""
        plan = self.plan
        return ws.materialise(plan.fixture_dir, plan.cell_id, self.settings.cache.build, list(plan.overlays))

    def precheck(self, workspace: Path) -> None:
        """Gate the seeded workspace with the case's precheck, before anything spends (ADR 0074).

        Whatever the precheck raises -- a failed assertion included -- is the fixture's fault,
        not the agent's, so it surfaces as a :class:`~pytest_xharness_eval.harness.RunError`
        and the cell errors with nothing billed and no record written.
        """
        if self.plan.case.precheck is None:
            return
        try:
            self.plan.case.precheck(Seed(workspace=workspace, scenario=self.plan.scenario))
        except Exception as exc:
            raise harness.RunError(f"precheck refused the seed before any run: {failure_line(exc)}") from exc

    def invoke(self, workspace: Path) -> Attempt:  # pragma: no cover - spawns a paid CLI (ADR 0002)
        """Run the harness's CLI in ``workspace``: the one step of a sweep that spends money.

        The wall clock is measured around the call and not derived from the session log,
        because it is the only measure that includes the CLI's own startup and teardown.
        """
        started_at = now_iso()
        t0 = time.monotonic()
        result = harness.get(self.plan.cell.harness).run(
            prompt=self.plan.prompt,
            model=self.plan.cell.model,
            workspace=workspace,
            effort=self.plan.cell.effort,
            skill_dir=self.plan.skill_dir,
            timeout_s=self.settings.timeout_s,
        )
        return Attempt(result=result, started_at=started_at, wall_ms=int((time.monotonic() - t0) * 1000))

    def session_dir(self, session_id: str) -> LocatedSession:
        """Where this cell's evidence goes: its five coordinates under ``<cache>/results/``."""
        return self.settings.cache.session(
            skill=self.plan.subject,
            harness=self.plan.cell.harness,
            model=self.plan.cell.model,
            effort=self.plan.cell.effort,
            treatment=self.plan.cell.treatment,
            run=run_stamp(),
            session=session_id,
        )

    def store(self, result: RunResult) -> LocatedSession:
        """Derive everything derivable, then write the evidence: the replayed sequence (ADR 0034).

        From here on a live cell does exactly what a replay of its capture does, in the
        same order and through the same two calls, which is the invariant
        ``tests/test_characterization.py`` pins.
        """
        session = self.session_dir(result.session_id)
        pipeline.derive(
            result,
            table=self.settings.price_table(),
            run_date=session.run_date,
            skill_files=list(self.plan.skill_files),
            case=self.plan.case_ref,
            effort=self.plan.cell.effort,
            treatment=self.plan.cell.treatment,
            spec=self.settings.catalogue().get(self.plan.cell.harness, self.plan.cell.model),
        )
        pipeline.capture(result, session)
        return session

    def quarantine(self, err: harness.UnfoldedRun) -> LocatedSession:
        """Keep a billed run whose logs would not fold, where its result would have gone (ADR 0072).

        Called before the error leaves, so a mismatch fails the cell without losing what it
        paid for; a replay retries the fold once the harness reads the new shape.
        """
        session = self.session_dir(err.evidence.session_id)
        pipeline.quarantine(
            err,
            session,
            case=self.plan.case_ref,
            effort=self.plan.cell.effort,
            treatment=self.plan.cell.treatment,
        )
        return session

    def output(self, result: RunResult, workspace: Path) -> CaseOutput:
        """The rollout as the grader sees it: the record, the workspace, and the seed list.

        ``seeded`` is taken from the fixture tree and the treatment's directories rather
        than the workspace, because by grading time they are mixed together and only this
        side knows which was which (ADR 0045). A treatment's files are seeded, not written:
        the agent found them there, exactly as it found the fixture (ADR 0055).
        """
        seeded = frozenset(
            str(p.relative_to(layer))
            for layer in (self.plan.fixture_dir, *self.plan.overlays)
            for p in layer.rglob("*")
            if p.is_file()
        )
        return CaseOutput(run=result, workspace=workspace, seeded=seeded, scenario=self.plan.scenario)

    def grade(self, result: RunResult, workspace: Path) -> Verdict:
        """Run the case's grader over the finished run, and name what happened.

        The verdict is recorded on this run *before* the grader's exception leaves, because
        a failed cell still has to emit its record: an assertion is a ``fail``, anything
        else is an ``error``, and either way pytest gets the original exception (ADR 0012).

        A run whose CLI never reached the model is an ``error`` before the grader is asked
        anything (ADR 0063): a session limit, an expired login or a refused request did not
        attempt the task, so grading it would record the skill as failing a test it never sat.
        """
        try:
            check_completed(result)
            if not result.attempted:
                raise harness.RunError(
                    f"{result.harness} exited {result.exit_code} without a model call, so the task was "
                    f"never attempted: {result.final_text[:300] or '(no message)'}"
                )
            self.plan.case.fn(self.output(result, workspace))
        except Exception as exc:
            # One rule for every checker (ADR 0076): an assertion fails, anything else errors.
            self.verdict, self.failure = Verdict.of_exception(exc), failure_line(exc, self.redactions(workspace))
            raise
        self.verdict = Verdict.PASS
        return self.verdict

    def redactions(self, workspace: Path) -> list[tuple[str, str]]:
        """The per-cell paths a recorded failure names, each with the token it is recorded as.

        The workspace, its scratch directory beside it (``verify.tool.scratch_dir``'s
        ``.<workspace name>.scratch``) and the cache root differ for every cell, so a failure
        quoting them would group as one cause per cell. Each is listed as given and resolved,
        since a message may quote either (``/tmp`` against ``/private/tmp``).
        """
        named = (
            (workspace.parent / f".{workspace.name}.scratch", "<scratch>"),
            (workspace, "<workspace>"),
            (self.settings.cache.root, "<cache>"),
        )
        return [(str(form), token) for path, token in named for form in dict.fromkeys((path, path.resolve()))]

    def record(self, attempt: Attempt, session: LocatedSession) -> CellMetrics:
        """This cell's metrics record, written beside its evidence (ADR 0018)."""
        return pipeline.record_metrics(
            attempt.result,
            session,
            outcome=Outcome(
                node=self.plan.node,
                verdict=self.verdict,
                wall_ms=attempt.wall_ms,
                started_at=attempt.started_at,
                failure=self.failure,
            ),
            cache=self.settings.cache,
        )

    def tidy(self, workspace: Path) -> None:
        """Remove the finished cell's workspace, unless the project keeps them for inspection (ADR 0062)."""
        if not self.settings.keep_workspaces:
            ws.discard(workspace)

    # -- the sequence ------------------------------------------------------------------

    def execute(self, stash: pytest.Stash) -> None:  # pragma: no cover - invoke() spends (ADR 0002)
        """Run the cell and leave its record in ``stash``, whatever the grader decided.

        The record is written in a ``finally`` because a failing cell is the case a metrics
        history exists for: a sweep that only recorded its passes would show cost dropping
        as quality dropped. The workspace is tidied in an outer ``finally``, after the record,
        so a cell whose CLI failed does not leave its downloads behind either.
        """
        workspace = self.materialise()
        try:
            self.precheck(workspace)
            try:
                attempt = self.invoke(workspace)
            except harness.UnfoldedRun as err:
                self.quarantine(err)
                raise
            session = self.store(attempt.result)
            try:
                self.grade(attempt.result, workspace)
            finally:
                stash[RECORD_KEY] = self.record(attempt, session)
        finally:
            self.tidy(workspace)
