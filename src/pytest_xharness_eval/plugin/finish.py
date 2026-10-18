"""The analyzers' run at the end of a session, on the controller (ADR 0075).

``pytest_sessionfinish`` runs after every cell has reported -- on the xdist controller too,
where each worker's records have already arrived -- and before the terminal summary, so it
is where a failed analyzer can still turn the session's exit status red. The suites are
found from the records this session graded rather than from collection, because the xdist
controller never collects. The report is written to ``report/analysis.json`` and left in
the stash for :mod:`.summary` to print.
"""

from __future__ import annotations

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.emit.findings import AnalysisReport
from pytest_xharness_eval.emit.summary import RunSummary
from pytest_xharness_eval.plugin.results import RESULTS_KEY
from pytest_xharness_eval.runtime.analyzers import analyze_suites
from pytest_xharness_eval.runtime.settings import Settings

#: Where the session's analysis report waits for the terminal summary.
ANALYSIS_KEY = pytest.StashKey[AnalysisReport]()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Run every analyzer of the suites this session graded a live cell of; fail the session on a failed one."""
    config = session.config
    # ADR 0075: on the controller only. Every xdist worker holds its own records too, and a
    # worker that ran the analyzers would race the controller's analysis.json mid-sweep.
    if hasattr(config, "workerinput"):
        return
    summary = RunSummary.of(config.stash.get(RESULTS_KEY, {}).values())
    live = [record for record in summary.cells if record.cache and record.suite]
    if not live:
        return
    settings = Settings.from_config(config)
    suites = {settings.rootpath / str(record.suite) for record in live}
    report = analyze_suites(settings, suites, live)
    if report is None:
        return
    report.write(settings.cache.analysis)
    config.stash[ANALYSIS_KEY] = report
    if not report.passed and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
