"""``verify.golden``: comparing a candidate to a golden facet by facet (ADR 0046)."""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import CaseOutput, verify
from pytest_xharness_eval.verify import (
    Count,
    Exact,
    Facet,
    GoldenCase,
    GoldenMismatch,
    Jaccard,
    facets,
)

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

# Our Libraries
from tests.support import DOC


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
