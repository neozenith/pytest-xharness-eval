"""``verify.checks``: the shared verifiers a grader asserts with (ADR 0045)."""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, harness, pricing, skillcov, verify
from pytest_xharness_eval.model.layout import SessionDir
from tests.characterization_fixtures import PRICE_ROWS, RUN_DATE, SKILL, claude_capture, skill_tree

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path


@pytest.fixture
def rollout(tmp_path: Path) -> CaseOutput:
    """A real folded Claude run, priced and coverage-annotated, over a real workspace."""
    capture = tmp_path / "capture"
    claude_capture(capture)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.md").write_text("# edited by the agent\n", encoding="utf-8")
    (workspace / "seed.md").write_text("seeded\n", encoding="utf-8")

    session = SessionDir(capture)
    stored = {"envelope": {}, "session_id": "sid1", "final_text": ""}
    agent = harness.get("claude")
    result = agent.session_from_capture(session, stored).to_result(workspace, ["a.md"])
    result.session_log = str(session.log)
    pricing.price(result, pricing.load_table(rows=PRICE_ROWS), RUN_DATE)
    result.skill_coverage = skillcov.annotate(SKILL, skillcov.catalog(skill_tree(tmp_path / "skill")), result)
    return CaseOutput(run=result, workspace=workspace, seeded=frozenset({"seed.md"}))


def test_the_gate_passes_a_real_priced_run(rollout: CaseOutput) -> None:
    verify.check_rollout(rollout)


def test_zero_billed_tokens_never_passes(rollout: CaseOutput) -> None:
    """The shape an unresolved invocation takes: it costs nothing and does nothing (ADR 0044)."""
    rollout.run.usage = type(rollout.run.usage)()
    with pytest.raises(AssertionError, match="zero billed tokens"):
        verify.check_run_is_real(rollout)


def test_a_missing_session_log_never_passes(rollout: CaseOutput) -> None:
    rollout.run.session_log = "/nowhere/log.jsonl"
    with pytest.raises(AssertionError, match="session log missing"):
        verify.check_run_is_real(rollout)


def test_a_nonzero_exit_never_passes(rollout: CaseOutput) -> None:
    rollout.run.exit_code = 2
    with pytest.raises(AssertionError, match="exited 2"):
        verify.check_run_is_real(rollout)


def test_an_unpriced_run_never_passes(rollout: CaseOutput) -> None:
    """A sweep that silently produced no price would look free (ADR 0007)."""
    unpriced = CaseOutput(run=rollout.run, workspace=rollout.workspace)
    unpriced.run.cost_status = type(unpriced.run.cost_status).UNPRICED
    with pytest.raises(AssertionError, match="not priced"):
        verify.check_run_is_priced(unpriced)


def test_a_price_without_provenance_never_passes(rollout: CaseOutput) -> None:
    rollout.run.rates_applied = None
    with pytest.raises(AssertionError, match="rate provenance"):
        verify.check_run_is_priced(rollout)


def test_written_and_added_are_different_questions(rollout: CaseOutput) -> None:
    """A fixture file that exists but was never touched is not something the run produced."""
    assert rollout.exists("seed.md") and not rollout.wrote("seed.md")
    assert rollout.added == ["a.md"] and rollout.changed == []
    verify.check_files_written(rollout, "a.md")
    with pytest.raises(AssertionError, match="did not write"):
        verify.check_files_written(rollout, "never.md")


def test_reading_a_missing_file_is_a_failed_check_not_an_oserror(rollout: CaseOutput) -> None:
    """A grader's missing artifact is a fact about the skill, so it must grade as fail (ADR 0012)."""
    with pytest.raises(AssertionError, match="not a file in the workspace"):
        rollout.read("absent.md")


def test_new_files_are_refused_unless_allowed(rollout: CaseOutput) -> None:
    with pytest.raises(AssertionError, match=r"the run added \['a.md'\]"):
        verify.check_no_files_added(rollout)
    verify.check_no_files_added(rollout, allow=["a.md"])


def test_the_allow_list_takes_patterns(rollout: CaseOutput) -> None:
    """A skill's own toolchain writes names a case can only learn at run time."""
    rollout.run.files_written.extend([".playwright-cli/page-2026-08-30T16-32-44.yml", "sneaky.md"])
    verify.check_no_files_added(rollout, allow=["a.md", ".playwright-cli/*", "sneaky.md"])
    # The permission stays explicit: an unmatched addition is still an addition.
    with pytest.raises(AssertionError, match="sneaky.md"):
        verify.check_no_files_added(rollout, allow=["a.md", ".playwright-cli/*"])


def test_a_preserved_block_must_survive_character_for_character(rollout: CaseOutput) -> None:
    """The rule that erodes silently: a helpful agent reformats it and no diff review notices."""
    verify.check_file_unchanged(rollout, "a.md", "# edited by the agent")
    with pytest.raises(AssertionError, match="absent entirely"):
        verify.check_file_unchanged(rollout, "a.md", "## a heading nobody wrote")
    with pytest.raises(AssertionError, match="present but altered"):
        verify.check_file_unchanged(rollout, "a.md", "# edited by the agent\nand a second line")


def test_tools_turns_and_delegation_are_read_off_the_real_ledger(rollout: CaseOutput) -> None:
    verify.check_turns_within(rollout, at_least=1)
    with pytest.raises(AssertionError, match="more than the 0"):
        verify.check_turns_within(rollout, at_most=0)
    with pytest.raises(AssertionError, match="never called"):
        verify.check_tools_used(rollout, "NoSuchTool")
    with pytest.raises(AssertionError, match="delegated thread"):
        verify.check_subagents_spawned(rollout, at_least=3)


def test_coverage_is_reached_by_attribute_not_by_get(rollout: CaseOutput) -> None:
    """The drift ADR 0045 was written for: ``.get("run")`` on a dataclass errors, never fails."""
    assert rollout.run.skill_coverage is not None
    verify.check_skill_was_loaded(rollout, *rollout.run.skill_coverage.loaded[:1])
    with pytest.raises(AssertionError, match="never loaded"):
        verify.check_skill_was_loaded(rollout, "resources/never-read.md")
    with pytest.raises(AssertionError, match="never executed"):
        verify.check_skill_scripts_ran(rollout, "scripts/nope.ts")


def test_the_loaded_check_has_no_skill_md_default(rollout: CaseOutput) -> None:
    """A native invocation injects SKILL.md rather than reading it, so a default would
    fail every passing run (ADR 0044). Refusing the empty call is what says so."""
    with pytest.raises(AssertionError, match="needs the skill files to look for"):
        verify.check_skill_was_loaded(rollout)


def test_an_unannotated_run_says_so_rather_than_raising_attributeerror(rollout: CaseOutput) -> None:
    rollout.run.skill_coverage = None
    with pytest.raises(AssertionError, match="never annotated"):
        verify.check_skill_was_loaded(rollout, "SKILL.md")
