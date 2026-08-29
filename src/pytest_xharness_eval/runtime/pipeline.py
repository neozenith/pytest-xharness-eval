"""The one sequence that turns a folded session log into a stored, graded record.

A live cell and a replay reach this module by different routes -- one has just spawned a
CLI, the other is re-reading a capture -- but from the moment a :class:`RunResult` exists
they must do exactly the same things to it, in the same order: price it, annotate which
of the skill's files it touched, name the case that produced it, write its evidence, and
append its metrics. Those steps used to be written out twice, in ``plugin.py`` and in
``replay.py``, and nothing failed when they drifted: a replay would quietly produce a
record a live run never would (ADR 0034).

Everything here is free. The paid part -- invoking the CLI -- belongs to the harness.
"""

from __future__ import annotations

# Standard Library
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.derive import pricing, skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.layout import SUBAGENTS_DIR

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.derive.skillcov import SkillFile
    from pytest_xharness_eval.emit.metrics import Outcome
    from pytest_xharness_eval.model.layout import CacheLayout, SessionDir
    from pytest_xharness_eval.model.runresult import CaseRef, RunResult


def derive(
    result: RunResult,
    *,
    table: dict[str, pricing.Rates],
    skill: str,
    skill_files: list[SkillFile],
    case: CaseRef | None,
) -> RunResult:
    """Price the run, annotate skill coverage, and name its case -- in that order.

    Coverage is annotated after pricing and before the case is attached only because that
    is the order the live path has always used; what matters is that both paths use one
    order, so a replay reproduces a live record exactly.
    """
    pricing.price(result, table)
    result.skill_coverage = skillcov.annotate(skill, skill_files, result)
    result.case = case
    return result


def capture_subagents(result: RunResult, session: SessionDir) -> None:
    """Copy each subagent transcript (and its Claude ``.meta.json`` sidecar) into
    ``<session dir>/subagents/`` and point ``Subagent.log`` at the captured copy, so the
    evidence survives the private ``CODEX_HOME`` teardown and a replay re-derives the
    same ledgers from the session directory alone.
    """
    if not result.subagents:
        return
    directory = session.subagents
    directory.mkdir(parents=True, exist_ok=True)
    for sub in result.subagents:
        source = Path(sub.log)
        if not source.is_file():
            continue
        (directory / source.name).write_bytes(source.read_bytes())
        sidecar = source.with_name(f"{source.stem}.meta.json")
        if sidecar.is_file():
            (directory / sidecar.name).write_bytes(sidecar.read_bytes())
        sub.log = f"{SUBAGENTS_DIR}/{source.name}"


def capture(result: RunResult, session: SessionDir) -> SessionDir:
    """Write one session's evidence: the log, any subagent transcripts, and the result.

    One directory per session and no shared file: the convention that makes parallel
    workers conflict-free (ADR 0032). Never inside ``fixtures/`` -- a fixture is copied
    into every workspace, so anything there would leak into the next agent's cwd.
    """
    session.mkdir()
    session.log.write_bytes(Path(result.session_log).read_bytes())
    capture_subagents(result, session)
    result.write(session.result)
    return session


def record_metrics(result: RunResult, session: SessionDir, *, outcome: Outcome, cache: CacheLayout) -> CellMetrics:
    """Build this cell's metrics record and write it beside its evidence (ADR 0018).

    ``cache`` is a declared field of the record, not a key written onto it afterwards
    (ADR 0037): the controller reads it to know which cache root to run the combine step
    against (ADR 0032).
    """
    metrics = CellMetrics.of(result, outcome=outcome, cache=cache)
    metrics.write(session.history)
    return metrics
