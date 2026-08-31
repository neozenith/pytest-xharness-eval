"""The checks every eval was writing for itself, written once (ADR 0045).

A verifier is a plain function over a finished :class:`CaseOutput` that returns when the
claim holds and raises :class:`AssertionError` naming what went wrong when it does not.
That is the whole contract -- no registry, no result object, no DSL (ADR 0012, ADR 0013).
What ships here is the vocabulary, not a framework: each check is importable alone, and a
suite that needs something else still writes a plain function beside its case.

Two rules the messages follow, because a red cell is read by someone deciding whether the
*skill* is broken:

* say what the agent did, not what the harness expected. "agent never ran the contrast
  gate (ran: ...)" beats "assert 'scripts/x.ts' in ran".
* show the evidence that would let a reader disagree. Every message that names an absence
  also names what was present instead.
"""

from __future__ import annotations

# Standard Library
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.model.runresult import CostStatus

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable

    # Our Libraries
    from pytest_xharness_eval.derive.skillcov import SkillCoverage
    from pytest_xharness_eval.model.output import CaseOutput


# -- the evidence gate ------------------------------------------------------------------


def check_run_is_real(output: CaseOutput) -> None:
    """The verdict is tied to a session that actually happened.

    A harness that graded the wrong transcript, or an empty one, looks exactly like a
    harness that works. These four close that gap: the run knows its own session id, the
    log it names is on disk, the CLI exited cleanly, and the model produced billed tokens.
    If any fails, nothing a later check reports is worth reading.

    Zero tokens is the shape an unresolved skill takes: ``/nosuchskill`` comes back as
    "Unknown command" having billed nothing (ADR 0044).
    """
    run = output.run
    assert run.session_id, "no session id - the run cannot prove which log is its own"
    assert run.session_log, "the run names no session log"
    assert Path(run.session_log).is_file(), f"session log missing: {run.session_log}"
    assert run.exit_code == 0, f"agent CLI exited {run.exit_code}"
    assert run.usage.accumulative_billed_tokens > 0, (
        "zero billed tokens - an empty run must never pass. The usual cause is an "
        "invocation the CLI did not resolve, which costs nothing and does nothing."
    )


def check_run_is_priced(output: CaseOutput) -> None:
    """The run carries a positive price estimate with the provenance that explains it.

    Neither CLI's session log carries cost: Claude reports it on stdout, Codex nowhere, so
    the plugin prices from its own table. An unpriced model is supposed to abort before the
    cell runs (ADR 0007); this catches the case where pricing silently produced nothing,
    which is what makes an expensive sweep look free.
    """
    run = output.run
    assert run.cost_status is CostStatus.PRICED, f"run was not priced (cost_status={run.cost_status.value})"
    assert run.estimated_cost_usd, f"cost must be a positive USD figure, got {run.estimated_cost_usd!r}"
    assert run.rates_applied is not None and run.rates_applied.source, (
        "the estimate carries no rate provenance (rates_applied.source); a price with no "
        "source cannot be audited against the table that produced it"
    )


def check_rollout(output: CaseOutput) -> None:
    """The gate every case owes: the run is real, and it is priced (ADR 0045).

    One named call rather than five assertions, because the fifth is what gets dropped
    when the block is copied into the next suite. Every shipped case opens with this.
    """
    check_run_is_real(output)
    check_run_is_priced(output)


# -- what the rollout left behind -------------------------------------------------------


def check_files_written(output: CaseOutput, *paths: str) -> None:
    """Every named path was created or modified by the run.

    Stricter than "the file exists": a fixture file the agent never touched exists, so
    existence alone lets a no-op pass a case about editing something.
    """
    missing = [p for p in paths if not output.wrote(p)]
    assert not missing, f"the run did not write {missing}; it wrote {output.written or 'nothing'}"


def check_no_files_added(output: CaseOutput, *, allow: Iterable[str] = ()) -> None:
    """The run edited the fixture in place and brought no new files into being.

    The check behind every "do not add new files" instruction: without it an agent can
    satisfy a content assertion by writing a second, correct copy and leaving the original
    exactly as broken as it found it.

    ``allow`` entries are :mod:`fnmatch` patterns, so a directory of scratch output takes
    one line: ``allow=["DISCOVERY.md", ".playwright-cli/*"]``. Patterns rather than exact
    paths because a skill's own toolchain often writes timestamped files -- the discovery
    skill's browser tool leaves ``.playwright-cli/page-<iso>.yml`` behind -- and no case can
    enumerate names it will only learn at run time. The permission is still explicit: a
    case says which scratch it expects, and anything else is still an addition.
    """
    permitted = list(allow)
    added = [p for p in output.added if not any(fnmatch(p, pattern) for pattern in permitted)]
    tail = f", plus {sorted(permitted)}" if permitted else ""
    assert not added, f"the run added {added}; this case allows edits in place only{tail}"


def check_file_unchanged(output: CaseOutput, path: str, expected: str) -> None:
    """``path`` still contains ``expected``, character for character.

    For the boundary a skill must not cross -- a section another workflow owns, a checksum
    comment, a licence header. This is the rule that erodes silently: a helpful agent
    reformats the block, nothing in a diff review notices, and the skill's hardest
    constraint quietly stops holding.
    """
    text = output.read(path)
    if expected in text:
        return
    head = expected.strip().splitlines()[0] if expected.strip() else ""
    near = "present but altered" if head and head in text else "absent entirely"
    raise AssertionError(
        f"{path} no longer contains the block it had to preserve verbatim ({near}). "
        f"It must survive character for character, reformatting included. Expected to find:\n{expected}"
    )


# -- what the run did on the way there --------------------------------------------------


def check_tools_used(output: CaseOutput, *names: str) -> None:
    """Every named tool was invoked at least once during the run."""
    used = output.run.tool_calls
    missing = [n for n in names if not used.get(n)]
    assert not missing, f"the run never called {missing}; it called {dict(sorted(used.items())) or 'no tools'}"


def check_subagents_spawned(output: CaseOutput, *, at_least: int = 1) -> None:
    """The run delegated to at least ``at_least`` parallel threads.

    Read off the captured subagent transcripts rather than off a tool-name count, so it
    means the same thing in both dialects: Claude spawns through a named tool, Codex forks
    a rollout (ADR 0033). A skill whose method *is* parallel research has not been
    exercised by a run that did the research itself.
    """
    spawned = len(output.run.subagents)
    assert spawned >= at_least, (
        f"the skill's method calls for at least {at_least} delegated thread(s); "
        f"this run spawned {spawned}. Tools it did call: {dict(sorted(output.run.tool_calls.items()))}"
    )


def check_turns_within(output: CaseOutput, *, at_most: int | None = None, at_least: int | None = None) -> None:
    """The run took a plausible number of model calls.

    A one-turn run usually means the skill never loaded; a run at the ceiling usually means
    it looped. Both are cheaper to notice here than in the cost chart a week later.
    """
    turns = output.run.turns
    if at_least is not None:
        assert turns >= at_least, f"the run took {turns} turn(s), fewer than the {at_least} this case expects"
    if at_most is not None:
        assert turns <= at_most, f"the run took {turns} turns, more than the {at_most} this case allows"


# -- did the skill actually load? -------------------------------------------------------


def _coverage(output: CaseOutput) -> SkillCoverage:
    """The run's coverage record, or a failure saying it was never annotated."""
    coverage = output.run.skill_coverage
    assert coverage is not None, "the run carries no skill coverage; the pipeline never annotated it"
    return coverage


def check_skill_was_loaded(output: CaseOutput, *paths: str) -> None:
    """The run read the named skill files. Name the *resources*, never ``SKILL.md``.

    Coverage attributes a file as loaded when the run issued a tool call that read it, and
    the two dialects do not agree about whether the entry point is ever read. Observed on
    one case, same task, same fixture (claude 2.1.251, codex-cli 0.151.0):

    ==========  =====================================================================
    ``claude``  ``resources/color_theming.md``, ``scripts/mermaid_contrast.ts`` -- and
                *not* ``SKILL.md``: resolving ``/<skill>`` injects it into the context,
                so the agent never issues a read for it.
    ``codex``   ``SKILL.md``, then the same resources: its instructions tell it to read
                the file itself before acting.
    ==========  =====================================================================

    So asserting ``SKILL.md`` passes on one arm and fails on the other, for a reason that
    has nothing to do with the skill -- which is exactly the "two different experiments"
    failure ADR 0044 exists to end. It is therefore not a default, and an empty call is
    refused rather than quietly meaning it.

    What a case should name is the material ``SKILL.md`` *points at* -- its ``resources/``
    and ``scripts/``. Both dialects reach those when they follow the skill, and reaching
    them is the evidence that it was followed rather than guessed at.

    Coverage is a typed record, reached by attribute (ADR 0035): the ``.get("loaded")`` that
    four suites had drifted into raises ``AttributeError`` on a dataclass, so those checks
    were erroring rather than grading (ADR 0045).
    """
    assert paths, (
        "check_skill_was_loaded needs the skill files to look for. There is no default: "
        "a native invocation injects SKILL.md rather than reading it, so it never appears "
        "in coverage (ADR 0044). Name the resources or scripts the skill directs the agent to."
    )
    loaded = set(_coverage(output).loaded)
    missing = [p for p in paths if p not in loaded]
    assert not missing, (
        f"the run never loaded {missing} from the skill under test. It loaded: {sorted(loaded) or 'nothing'}. "
        "A run that produced the right artifact without reaching the skill's own material "
        "did not exercise the skill."
    )


def check_skill_scripts_ran(output: CaseOutput, *paths: str) -> None:
    """The run executed the named skill scripts.

    For a skill whose gates are mandatory: getting the structure right without running the
    checks is a different outcome from getting it right *and* checking, and only one of the
    two is the behaviour the skill mandates.
    """
    ran = set(_coverage(output).run)
    missing = [p for p in paths if p not in ran]
    assert not missing, (
        f"the run never executed {missing}, which the skill declares mandatory. It ran: {sorted(ran) or 'nothing'}"
    )
