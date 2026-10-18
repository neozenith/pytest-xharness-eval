"""``plugin.finish``: the analyzers' run at session end, on the controller only (ADR 0075).

The hook reads the records the session's cells left in the config stash. A record only
reaches it from a graded live cell, which no test may produce (ADR 0002), so each test
builds a real pytest ``Session`` over a pytester project, puts real ``CellMetrics`` records
in the stash the way ``plugin.results`` does, and calls the hook as pytest would.
"""

# Standard Library
import json
import textwrap

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.plugin.finish import ANALYSIS_KEY, pytest_sessionfinish
from pytest_xharness_eval.plugin.results import RESULTS_KEY
from pytest_xharness_eval.runtime.settings import Settings
from tests.support import _case_record, _store_record, make_tree

SUITE = "skills/demo/evals/eval_demo.py"
ANALYZER = """

from pytest_xharness_eval import analyzer

@analyzer
def analyze_passes(analysis):
    assert all(r.verdict == "pass" for r in analysis.samples), "a sample failed"
"""


def _session(pytester: pytest.Pytester, *records: CellMetrics, analyzers: bool = True) -> pytest.Session:
    """A session over the one-skill project, its stash holding ``records`` as the controller's would."""
    evals = make_tree(pytester)
    if analyzers:
        suite = evals / "eval_demo.py"
        suite.write_text(suite.read_text(encoding="utf-8") + textwrap.dedent(ANALYZER), encoding="utf-8")
    config = pytester.parseconfigure()
    config.stash[RESULTS_KEY] = {r.node: r for r in records}
    session = pytest.Session.from_config(config)
    session.exitstatus = pytest.ExitCode.OK  # what pytest's wrap_session sets before any hook runs
    return session


def _live(pytester: pytest.Pytester, verdict: Verdict = Verdict.PASS, session: str = "s1") -> CellMetrics:
    cache = Settings.from_config(pytester.parseconfig()).cache
    return _case_record(cache, suite=SUITE, case="eval_demo", session=session, verdict=verdict)


def test_a_failed_analyzer_writes_its_report_and_turns_the_session_red(pytester: pytest.Pytester) -> None:
    session = _session(pytester, _live(pytester, Verdict.FAIL))
    pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    cache = Settings.from_config(session.config).cache
    written = json.loads(cache.analysis.read_text(encoding="utf-8"))
    assert written["passed"] is False
    assert [f["analyzer"] for f in written["findings"]] == [f"{SUITE}::analyze_passes"]
    assert session.config.stash[ANALYSIS_KEY].failed[0].message == "a sample failed"


def test_stored_history_is_analysed_beside_this_sessions_records(pytester: pytest.Pytester) -> None:
    """A failure from an earlier sweep still fails the analyzer: it asks across every stored sample."""
    session = _session(pytester, _live(pytester))
    cache = Settings.from_config(session.config).cache
    _store_record(cache, _case_record(cache, suite=SUITE, case="eval_demo", session="old", verdict=Verdict.FAIL))
    pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED


def test_a_passing_analysis_leaves_the_exit_status_alone(pytester: pytest.Pytester) -> None:
    session = _session(pytester, _live(pytester))
    pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.OK
    assert session.config.stash[ANALYSIS_KEY].passed


def test_a_worse_exit_status_is_never_downgraded_to_tests_failed(pytester: pytest.Pytester) -> None:
    session = _session(pytester, _live(pytester, Verdict.FAIL))
    session.exitstatus = pytest.ExitCode.INTERRUPTED
    pytest_sessionfinish(session, pytest.ExitCode.INTERRUPTED)
    assert session.exitstatus == pytest.ExitCode.INTERRUPTED


def test_an_xdist_worker_never_runs_the_analyzers(pytester: pytest.Pytester) -> None:
    """Each worker holds its own records; one that analysed would race the controller's analysis.json."""
    session = _session(pytester, _live(pytester, Verdict.FAIL))
    session.config.workerinput = {"workerid": "gw0"}  # type: ignore[attr-defined]
    pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.OK
    assert ANALYSIS_KEY not in session.config.stash
    assert not Settings.from_config(session.config).cache.analysis.exists()


def test_a_session_with_no_live_record_or_no_analyzer_writes_nothing(pytester: pytest.Pytester) -> None:
    dry = _session(pytester)  # a --dry-run session: no record carries a cache
    pytest_sessionfinish(dry, pytest.ExitCode.OK)
    assert ANALYSIS_KEY not in dry.config.stash


def test_suites_that_declare_no_analyzer_leave_no_report(pytester: pytest.Pytester) -> None:
    session = _session(pytester, _live(pytester, Verdict.FAIL), analyzers=False)
    pytest_sessionfinish(session, pytest.ExitCode.OK)
    assert session.exitstatus == pytest.ExitCode.OK
    assert not Settings.from_config(session.config).cache.analysis.exists()
