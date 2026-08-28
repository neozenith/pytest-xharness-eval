"""How a cell's record reaches the controller, and the word it prints there (ADR 0016, ADR 0040).

A cell is graded in whichever process pytest ran it in. Under ``-n`` that is an xdist
worker, and the *only* channel from a worker back to the controller is
``TestReport.user_properties``, which execnet serialises -- and execnet handles builtins
only. So the record makes exactly one crossing as a plain mapping, encoded on the worker
in :func:`pytest_runtest_makereport` and decoded on the controller in :func:`record_of`.
Everywhere else it travels as a :class:`CellMetrics` (ADR 0037).

Both sides of that crossing, and both readers of the arrived record -- the per-cell status
word and the session's result registry -- live here, so the encode and the decode cannot
drift apart across modules.
"""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING, Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Generator, Mapping

# The ``user_properties`` key a cell's record travels under, worker to controller.
PROPERTY = "xharness_eval"

# One record per cell, keyed by node id, in the order their call reports arrived.
RESULTS_KEY: pytest.StashKey[dict[str, CellMetrics]] = pytest.StashKey()
# The record a cell produced, held on the item until its call report is made.
RECORD_KEY: pytest.StashKey[CellMetrics] = pytest.StashKey()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, Any]:
    """Worker side: put the cell's record on its call report so it survives xdist and reaches JUnit.

    This is the one place the typed record becomes a plain mapping (see the module
    docstring); :func:`record_of` is the matching decode. A record in the item's stash is
    the test that this is a cell -- nothing else puts one there -- so the crossing does not
    have to know the item class.
    """
    report = yield
    if call.when == "call" and RECORD_KEY in item.stash:
        record = item.stash[RECORD_KEY].to_dict()
        props: list[tuple[str, object]] = [(PROPERTY, record)]
        # Flat scalars as their own properties, so --junitxml carries the metrics history too.
        props.extend((f"xharness_{k}", v) for k, v in record.items() if isinstance(v, str | int | float))
        # The call report is what xdist ships to the controller; the item's list is what
        # pytest copies onto the teardown report, which is where junitxml reads properties.
        report.user_properties.extend(props)
        item.user_properties.extend(props)
    return report


def record_of(report: pytest.TestReport) -> CellMetrics | None:
    """Controller side: the cell record carried on a call report, decoded back into its type."""
    for name, value in report.user_properties:
        if name == PROPERTY and isinstance(value, dict):
            return CellMetrics.from_dict(value)
    return None


class ResultCollector:
    """Controller side (and single-process): gather records as call reports arrive.

    Registered by name in ``pytest_configure`` so the session owns exactly one, and it
    keeps the records in arrival order under the session's stash, which is what the
    terminal summary and ``report.json`` are built from.
    """

    def __init__(self, config: pytest.Config) -> None:
        self.config = config

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when != "call":
            return
        record = record_of(report)
        if record is not None:
            self.config.stash[RESULTS_KEY][report.nodeid] = record


def pytest_report_teststatus(
    report: pytest.CollectReport | pytest.TestReport, config: pytest.Config
) -> tuple[str, str, str | tuple[str, Mapping[str, bool]]] | None:
    """Replace the verbose status word of an eval cell with its verdict and metrics.

    A cell that carries no record is not ours: returning None leaves pytest's own word in
    place, which is what keeps a plain ``test_*`` in the same session looking normal.
    """
    if not isinstance(report, pytest.TestReport) or report.when != "call":
        return None
    record = record_of(report)
    if record is None:
        return None
    if record.verdict == Verdict.DRY_RUN:
        return ("skipped", "s", ("DRY-RUN", {"yellow": True}))
    detail = record.status_word()
    if record.verdict == Verdict.PASS:
        return ("passed", ".", (f"PASSED  {detail}", {"green": True}))
    letter = "F" if record.verdict == Verdict.FAIL else "E"
    return ("failed", letter, (f"{record.verdict.upper()}  {detail}", {"red": True}))
