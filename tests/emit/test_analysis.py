"""``emit.analysis``: ``report/analysis.json``, every analyzer's finding as one document."""

# Standard Library
import json
from pathlib import Path

# Our Libraries
from pytest_xharness_eval.emit.analysis import AnalysisReport
from pytest_xharness_eval.model.analysis import Finding


def test_the_report_passes_only_when_every_finding_does(tmp_path: Path) -> None:
    good = Finding(analyzer="analyze_a", passed=True)
    bad = Finding(analyzer="analyze_b", passed=False, message="regressed", details={"metric": "verdict"})
    report = AnalysisReport.of([good, bad], generated_at="2026-10-18T00:00:00Z")
    assert not report.passed and report.failed == (bad,)
    written = json.loads(report.write(tmp_path / "report" / "analysis.json").read_text(encoding="utf-8"))
    assert written == {
        "generated_at": "2026-10-18T00:00:00Z",
        "passed": False,
        "findings": [good.to_dict(), bad.to_dict()],
    }
    assert set(written["findings"][1]) == {"analyzer", "passed", "message", "comparisons", "details"}


def test_an_analysis_with_no_analyzers_holds() -> None:
    assert AnalysisReport(generated_at="t").passed
