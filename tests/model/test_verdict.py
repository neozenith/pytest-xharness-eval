"""``model.verdict``: the words a cell may grade to (ADR 0041)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    Usage,
)
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _result


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("pass", Verdict.PASS), ("fail", Verdict.FAIL), ("error", Verdict.ERROR), ("dry-run", Verdict.DRY_RUN)],
)
def test_the_four_words_are_read_back_as_the_vocabulary(stored: str, expected: Verdict) -> None:
    """The words a record may grade to are named once, in the domain, and no fifth (ADR 0041)."""
    assert Verdict.stored(stored) is expected and expected.value == stored
    assert list(Verdict) == [Verdict.PASS, Verdict.FAIL, Verdict.ERROR, Verdict.DRY_RUN]


@pytest.mark.parametrize("stored", ["", "skipped", "PASS"])
def test_a_verdict_no_version_of_this_package_wrote_reads_as_no_verdict(stored: str) -> None:
    """A stored word outside the vocabulary is None, never a grade the run was not given (ADR 0038)."""
    assert Verdict.stored(stored) is None
    # Which is what a replay carries forward: the record keeps its empty verdict rather
    # than gaining one, and the rebuild does not abort on it.
    record = CellMetrics.from_dict({"verdict": stored, "node": "n", "at": "t", "wall_ms": 3})
    assert record.outcome.verdict is None
    rebuilt = CellMetrics.of(_result("m", Usage(1, 2)), outcome=record.outcome, cache=CacheLayout(Path("/c")))
    assert rebuilt.verdict == "" and rebuilt.node == "n"
