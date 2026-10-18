"""``runtime.analysis``: every suite's analyzers over a cache, each scoped to its own suite (ADR 0075)."""

# Standard Library
import textwrap
from pathlib import Path

# Our Libraries
from pytest_xharness_eval.emit.analysis import AnalysisReport
from pytest_xharness_eval.model.analysis import Finding
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.verdict import Verdict
from pytest_xharness_eval.runtime.analysis import analyze_suites, finding_lines
from pytest_xharness_eval.runtime.settings import Settings
from tests.support import _case_record, _store_record

COUNTING = """
from pytest_xharness_eval import analyzer

@analyzer
def analyze_count(analysis):
    analysis.note("history", sorted(r.session_id for r in analysis.history))
    analysis.note("current", sorted(r.session_id for r in analysis.current))
    assert len(analysis.samples) >= {least}, f"only {{len(analysis.samples)}} samples"
"""
BROKEN = """

@analyzer
def analyze_broken(analysis):
    raise RuntimeError("no such metric")
"""


def _settings(root: Path, cache: CacheLayout) -> Settings:
    return Settings(rootpath=root, skills_root=root / "skills", cache=cache)


def _suite(root: Path, rel: str, body: str) -> Path:
    """An ``eval_*.py`` at ``root/rel`` holding ``body`` and nothing else."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _two_subjects(tmp_path: Path) -> tuple[CacheLayout, Path, Path]:
    """Two subjects' ``eval_lint.py``: same stem, different directories, two stored samples each."""
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    skill = _suite(tmp_path, "skills/a/evals/eval_lint.py", COUNTING.format(least=1))
    tool = _suite(tmp_path, "tools/b/evals/eval_lint.py", COUNTING.format(least=1) + BROKEN)
    for suite, sessions in (("skills/a/evals/eval_lint.py", "a1 a2"), ("tools/b/evals/eval_lint.py", "b1 b2")):
        for session in sessions.split():
            _store_record(cache, _case_record(cache, suite=suite, case="eval_lint", session=session))
    return cache, skill, tool


def _by_name(report: AnalysisReport | None) -> dict[str, Finding]:
    assert report is not None
    return {f.analyzer: f for f in report.findings}


def test_each_suites_analyzers_see_only_that_suites_samples_even_when_the_stems_match(tmp_path: Path) -> None:
    cache, skill, tool = _two_subjects(tmp_path)
    current = _case_record(cache, suite="tools/b/evals/eval_lint.py", case="eval_lint", session="b3")
    findings = _by_name(analyze_suites(_settings(tmp_path, cache), [tool, skill], [current]))
    a = findings["skills/a/evals/eval_lint.py::analyze_count"]
    b = findings["tools/b/evals/eval_lint.py::analyze_count"]
    assert a.passed and a.details == {"history": ["a1", "a2"], "current": []}
    assert b.passed and b.details == {"history": ["b1", "b2"], "current": ["b3"]}


def test_a_crashing_analyzer_is_an_errored_finding_and_the_others_still_run(tmp_path: Path) -> None:
    """A paid sweep must not lose its combine step to a broken analyzer, nor record it as a pass."""
    cache, skill, tool = _two_subjects(tmp_path)
    report = analyze_suites(_settings(tmp_path, cache), [skill, tool])
    findings = _by_name(report)
    broken = findings["tools/b/evals/eval_lint.py::analyze_broken"]
    assert not broken.passed and broken.message == "ERROR RuntimeError: no such metric"
    assert broken.details == {"error": "RuntimeError"}
    assert findings["skills/a/evals/eval_lint.py::analyze_count"].passed
    assert report is not None and not report.passed and len(report.findings) == 3


def test_a_failed_expectation_fails_its_finding_with_the_analyzers_message(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / "cache")
    suite = _suite(tmp_path, "skills/a/evals/eval_lint.py", COUNTING.format(least=5))
    _store_record(cache, _case_record(cache, suite="skills/a/evals/eval_lint.py", case="eval_lint", session="x"))
    (finding,) = _by_name(analyze_suites(_settings(tmp_path, cache), [suite])).values()
    assert not finding.passed and finding.message == "only 1 samples"


def test_dry_runs_and_other_suites_records_are_not_samples_of_a_suite(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path / "cache")
    suite = _suite(tmp_path, "skills/a/evals/eval_lint.py", COUNTING.format(least=1))
    for session, verdict in (("p", Verdict.PASS), ("f", Verdict.FAIL), ("d", Verdict.DRY_RUN)):
        record = _case_record(
            cache, suite="skills/a/evals/eval_lint.py", case="eval_lint", session=session, verdict=verdict
        )
        _store_record(cache, record)
    _store_record(cache, _case_record(cache, suite="skills/z/evals/eval_lint.py", case="eval_lint", session="z"))
    (finding,) = _by_name(analyze_suites(_settings(tmp_path, cache), [suite])).values()
    assert finding.details["history"] == ["f", "p"]


def test_suites_that_declare_no_analyzer_produce_no_report(tmp_path: Path) -> None:
    suite = _suite(tmp_path, "skills/a/evals/eval_lint.py", "X = 1\n")
    assert analyze_suites(_settings(tmp_path, CacheLayout(tmp_path / "cache")), [suite, suite]) is None


def test_finding_lines_indent_a_failures_message_beneath_it_and_cap_it() -> None:
    report = AnalysisReport.of(
        [
            Finding(analyzer="s.py::analyze_ok", passed=True),
            Finding(analyzer="s.py::analyze_bad", passed=False, message="\n".join(f"line {i}" for i in range(20))),
        ],
        generated_at="t",
    )
    lines = finding_lines(report)
    assert lines[:3] == ["  pass  s.py::analyze_ok", "  FAIL  s.py::analyze_bad", "        line 0"]
    assert len(lines) == 2 + 12 and lines[-1] == "        line 11"
