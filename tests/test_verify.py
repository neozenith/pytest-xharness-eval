"""The shared verifiers and the golden comparison (ADR 0045, ADR 0046).

Every :class:`RunResult` here comes from folding a real captured session log through the
real adapter -- the same fixtures ``test_characterization.py`` pins -- because ADR 0002
forbids a fabricated run for the same reason it forbids a mocked CLI: a check that only
ever sees a hand-built record is a check against the test's idea of a rollout.

The golden half needs no rollout at all. Facet extraction and every tolerance are pure
functions over text, so they are exercised against literals: free, deterministic, and the
place a regex mistake actually shows up.
"""

from __future__ import annotations

# Standard Library
import textwrap
from typing import TYPE_CHECKING

# Third Party
import pytest
from characterization_fixtures import PRICE_ROWS, SKILL, claude_capture, skill_tree

# Our Libraries
from pytest_xharness_eval import CaseOutput, harness, pricing, skillcov, verify
from pytest_xharness_eval.model.layout import SessionDir
from pytest_xharness_eval.verify import (
    Count,
    Exact,
    Facet,
    GoldenCase,
    GoldenMismatch,
    Jaccard,
    Ratio,
    Superset,
    Within,
    facets,
)

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
    pricing.price(result, pricing.load_table(rows=PRICE_ROWS))
    result.skill_coverage = skillcov.annotate(SKILL, skillcov.catalog(skill_tree(tmp_path / "skill")), result)
    return CaseOutput(run=result, workspace=workspace, seeded=frozenset({"seed.md"}))


# -- the evidence gate ------------------------------------------------------------------


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


# -- what the rollout left behind -------------------------------------------------------


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


# -- what the run did on the way there --------------------------------------------------


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


# -- facets: the extractors a golden compares with --------------------------------------

DOC = textwrap.dedent(
    """\
    # Architecture

    ## Overview

    ```mermaid
    flowchart TD
        Loader[Load CSV] --> Transform[Transform]
        Transform --> Report[Report]
        classDef io fill:#1F4E5F,color:#FFFFFF
        class Loader,Report io
    ```

    <details>
    <summary>Detail</summary>

    ```mermaid
    flowchart LR
        Reader[Reader] --> Parser[Parser]
        classDef core fill:#7A4E2D,color:#FFFFFF
        class Reader,Parser core
    ```

    </details>
    """
)


def test_fences_split_by_whether_they_are_collapsed() -> None:
    assert facets.fence_count(DOC) == 2
    assert len(facets.visible_fences(DOC)) == 1
    assert len(facets.collapsed_fences(DOC)) == 1


def test_node_ids_and_edges_ignore_mermaid_keywords() -> None:
    assert facets.node_ids(DOC) == {"Loader", "Transform", "Report", "Reader", "Parser"}
    assert facets.edges(DOC) == {"Loader->Transform", "Transform->Report", "Reader->Parser"}
    assert "classDef" not in facets.node_ids(DOC)


def test_the_palette_facets_read_classdefs_not_substrings() -> None:
    assert facets.classdef_names(DOC) == {"io", "core"}
    assert facets.classdef_count(DOC) == 2
    assert facets.fill_colours(DOC) == {"#1f4e5f", "#7a4e2d"}
    assert facets.text_colours(DOC) == {"#ffffff"}


def test_unstyled_nodes_is_the_mandates_actual_claim() -> None:
    """ "A classDef exists" is satisfiable by styling one node of five; this is not."""
    assert facets.unstyled_nodes(DOC) == {"Transform"}
    inline = DOC.replace("    Transform --> Report[Report]", "    Transform:::io --> Report[Report]")
    assert facets.unstyled_nodes(inline) == set()


def test_headings_and_prose_facets() -> None:
    assert facets.headings(DOC) == {"Architecture", "Overview"}
    assert facets.headings_at(2)(DOC) == {"Overview"}
    assert "flowchart" not in facets.body_text(DOC)
    assert facets.hex_colours(DOC) == {"#1f4e5f", "#7a4e2d", "#ffffff"}


# -- tolerances -------------------------------------------------------------------------


def test_each_tolerance_reports_its_own_evidence() -> None:
    assert Exact().check({"a", "b"}, {"a", "b"}).ok
    missed = Exact().check({"a", "b"}, {"a", "c"})
    assert not missed.ok and missed.missing == ("b",) and missed.extra == ("c",)
    assert Exact().check(3, 3).ok and not Exact().check(3, 4).ok

    assert Superset().check({"a"}, {"a", "b"}).ok
    assert not Superset().check({"a", "z"}, {"a"}).ok

    assert Jaccard(at_least=0.5).check({"a", "b"}, {"a", "b", "c"}).ok
    assert not Jaccard(at_least=0.9).check({"a", "b"}, {"a", "c"}).ok

    assert Ratio(at_least=0.9).check("hello world", "hello worlds").ok
    assert not Ratio(at_least=0.9).check("hello world", "entirely different").ok

    assert Count(delta=1).check([1, 2, 3], [1, 2]).ok
    assert not Count(delta=0).check([1, 2, 3], [1, 2]).ok
    assert Count(lo=1, hi=3).check([], [1, 2]).ok and not Count(lo=5).check([], [1, 2]).ok

    assert Within(lo=0.0, hi=1.0).check(None, 0.5).ok
    assert not Within(lo=0.0, hi=1.0).check(None, 2.0).ok
    assert not Within(lo=0.0, hi=1.0).check(None, "not a number").ok


def test_count_refuses_an_ambiguous_declaration() -> None:
    """A tolerance that is both relative and absolute is neither (ADR 0046)."""
    with pytest.raises(ValueError, match="either delta="):
        Count(delta=1, lo=2)
    with pytest.raises(ValueError, match="either delta="):
        Count()


def test_a_set_tolerance_refuses_a_scalar_facet() -> None:
    assert not Superset().check(1, 2).ok
    assert not Jaccard(at_least=0.5).check(1, 2).ok


# -- the golden case --------------------------------------------------------------------


def _golden_case(evals: Path, *facet_list: Facet) -> GoldenCase:
    return GoldenCase.at(evals, "unstyled_diagram", "ARCHITECTURE.md", facet_list)


def _seed_golden(tmp_path: Path, text: str = DOC) -> Path:
    evals = tmp_path / "evals"
    target = evals / verify.GOLDENS_DIR / "unstyled_diagram" / "ARCHITECTURE.md"
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return evals


def test_a_golden_matches_a_candidate_that_differs_only_where_it_may(tmp_path: Path) -> None:
    """Names and whitespace are free; the concept set and the fence structure are not."""
    evals = _seed_golden(tmp_path)
    case = _golden_case(
        evals,
        Facet(name="fences", extract=facets.fence_count, tolerance=Exact(), why="dual density"),
        Facet(name="nodes", extract=facets.node_ids, tolerance=Jaccard(at_least=0.8), why="the concept set"),
        Facet(name="unstyled", extract=facets.unstyled_nodes, tolerance=Count(lo=0, hi=1), why="the mandate"),
    )
    candidate = DOC.replace("#1F4E5F", "#1f4e60").replace("Report[Report]", "Report[Report writer]")
    delta = case.compare(candidate)
    assert delta.ok, delta.report()
    assert "matches the golden on all 3 facets" in delta.report()


def test_a_mismatch_reports_the_delta_facet_by_facet(tmp_path: Path) -> None:
    evals = _seed_golden(tmp_path)
    case = _golden_case(
        evals,
        Facet(name="fences", extract=facets.fence_count, tolerance=Exact(), why="the dual-density structure"),
        Facet(name="nodes", extract=facets.node_ids, tolerance=Exact(), why="the concept set is fixed by the fixture"),
    )
    stripped = DOC[: DOC.index("<details>")].replace("Report[Report]", "Sink[Sink]")
    delta = case.compare(stripped)
    assert not delta.ok
    report = delta.report()
    assert "2 of 2 facets failed" in report
    # The report is a delta, not a diff: it names what is missing and what arrived instead.
    assert "missing:" in report and "Report" in report
    assert "extra:" in report and "Sink" in report
    assert "the concept set is fixed by the fixture" in report
    # Passing facets would be listed too; here there are none, and both carry their tolerance.
    assert report.count("[FAIL]") == 2


def test_assert_matches_raises_a_gradeable_failure(tmp_path: Path) -> None:
    """A wrong answer is a ``fail``, never an ``error``: the skill misbehaved (ADR 0012)."""
    evals = _seed_golden(tmp_path)
    case = _golden_case(evals, Facet(name="nodes", extract=facets.node_ids, tolerance=Exact()))
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ARCHITECTURE.md").write_text("# nothing here\n", encoding="utf-8")
    output = CaseOutput(run=None, workspace=workspace)  # type: ignore[arg-type]
    with pytest.raises(GoldenMismatch) as exc:
        case.assert_matches(output)
    assert issubclass(GoldenMismatch, AssertionError)
    assert "outside the golden's tolerances" in str(exc.value)


def test_a_case_naming_a_golden_nobody_committed_fails_loudly(tmp_path: Path) -> None:
    """An absent golden must not compare as an empty string, which reads as "all missing"."""
    case = _golden_case(tmp_path / "evals", Facet(name="nodes", extract=facets.node_ids, tolerance=Exact()))
    with pytest.raises(AssertionError, match="no golden committed"):
        case.compare(DOC)


def test_record_captures_a_candidate_as_the_new_reference(tmp_path: Path) -> None:
    """Never called during grading: a run that laundered its own output would grade nothing."""
    evals = tmp_path / "evals"
    case = _golden_case(evals, Facet(name="nodes", extract=facets.node_ids, tolerance=Exact()))
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ARCHITECTURE.md").write_text(DOC, encoding="utf-8")
    written = case.record(CaseOutput(run=None, workspace=workspace))  # type: ignore[arg-type]
    assert written.read_text(encoding="utf-8") == DOC
    assert case.compare(DOC).ok
