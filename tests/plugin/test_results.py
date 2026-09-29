"""``plugin.results``: the record's crossing to the controller, and its status word (ADR 0016)."""


# Standard Library

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Cell,
    Usage,
)
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin import results as plugin_results
from tests.support import _metrics, _result


def _report(record: CellMetrics | None, *, when: str = "call") -> pytest.TestReport:
    """A real call report carrying (or not carrying) a cell's record, as a worker would send it."""
    return pytest.TestReport(
        nodeid="skills/demo/evals/eval_demo.py::eval_demo[claude/claude-opus-5]",
        location=("skills/demo/evals/eval_demo.py", 0, "eval_demo"),
        keywords={},
        outcome="passed",
        longrepr=None,
        when=when,
        user_properties=[] if record is None else [(plugin_results.PROPERTY, record.to_dict())],
    )


def test_the_record_decodes_back_into_its_type_on_the_controller_side() -> None:
    record = _metrics(_result("claude-opus-5", Usage(10, 20)))
    assert plugin_results.record_of(_report(record)) == record
    assert plugin_results.record_of(_report(None)) is None


@pytest.mark.parametrize(
    ("verdict", "category", "letter"),
    [(Verdict.PASS, "passed", "."), (Verdict.FAIL, "failed", "F"), (Verdict.ERROR, "failed", "E")],
)
def test_the_status_word_is_the_verdict_followed_by_the_cells_metrics(
    pytestconfig: pytest.Config, verdict: Verdict, category: str, letter: str
) -> None:
    result = _result("claude-opus-5", Usage(10, 20))
    result.estimated_cost_usd = 0.25
    status = plugin_results.pytest_report_teststatus(
        _report(_metrics(result, verdict=verdict, wall_ms=2000)), pytestconfig
    )
    assert status is not None
    assert (status[0], status[1]) == (category, letter)
    word, markup = status[2]
    assert word.startswith("PASSED" if verdict is Verdict.PASS else verdict.upper())
    assert "est $0.2500" in word and "2.0s" in word
    assert markup == ({"green": True} if verdict is Verdict.PASS else {"red": True})


def test_a_dry_run_cell_shows_dry_run_and_a_foreign_report_keeps_pytests_own_word(
    pytestconfig: pytest.Config,
) -> None:
    dry = CellMetrics.dry_run(node="n", cell=Cell(harness="claude", model="claude-opus-5"))
    assert plugin_results.pytest_report_teststatus(_report(dry), pytestconfig) == (
        "skipped",
        "s",
        ("DRY-RUN", {"yellow": True}),
    )
    # Not ours, or not the call phase: pytest's own status word stands.
    assert plugin_results.pytest_report_teststatus(_report(None), pytestconfig) is None
    assert plugin_results.pytest_report_teststatus(_report(dry, when="setup"), pytestconfig) is None
