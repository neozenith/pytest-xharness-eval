"""``analysis``: re-running every suite's analyzers over a cache from the command line (ADR 0075)."""

# Standard Library
import json
import textwrap
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import analysis
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.verdict import Verdict
from tests.support import _case_record, _store_record

SUITE = "agent-skills/demo/evals/eval_demo.py"
ANALYZER = """
from pytest_xharness_eval import analyzer

@analyzer
def analyze_passes(analysis):
    assert all(r.verdict == "pass" for r in analysis.samples), "a sample failed"
"""


def _project(tmp_path: Path, *verdicts: Verdict, body: str = ANALYZER) -> CacheLayout:
    """A project whose ``pyproject.toml`` names its skills root, one suite, and its stored samples."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nxharness_skills_dir = "agent-skills"\n', encoding="utf-8"
    )
    suite = tmp_path / SUITE
    suite.parent.mkdir(parents=True)
    suite.write_text(textwrap.dedent(body), encoding="utf-8")
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    for i, verdict in enumerate(verdicts):
        _store_record(cache, _case_record(cache, suite=SUITE, case="eval_demo", session=f"s{i}", verdict=verdict))
    return cache


def test_a_held_analysis_exits_zero_and_writes_its_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cache = _project(tmp_path, Verdict.PASS, Verdict.PASS)
    assert analysis.main([str(cache.root)]) == 0
    out = capsys.readouterr().out
    assert f"  pass  {SUITE}::analyze_passes" in out and f"  analysis: {cache.analysis}" in out
    assert json.loads(cache.analysis.read_text(encoding="utf-8"))["passed"] is True


def test_a_failed_analyzer_exits_one_so_a_script_can_branch_on_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = _project(tmp_path, Verdict.PASS, Verdict.FAIL)
    assert analysis.main([str(cache.root), "--seed", "7"]) == 1
    out = capsys.readouterr().out
    assert f"  FAIL  {SUITE}::analyze_passes" in out and "        a sample failed" in out


def test_suite_names_the_suites_to_analyze_instead_of_every_one_under_the_skills_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = _project(tmp_path, Verdict.FAIL)
    other = tmp_path / "elsewhere" / "eval_other.py"
    other.parent.mkdir()
    other.write_text("X = 1\n", encoding="utf-8")
    # The named suite declares no analyzer, so the one under the skills root is not run either.
    assert analysis.main([str(cache.root), "--suite", str(other)]) == analysis.NOTHING_TO_ANALYZE
    assert capsys.readouterr().err == f"nothing to analyze: no @analyzer declared in: {other}\n"
    assert not cache.analysis.exists()


def test_nothing_to_analyze_is_a_usage_error_never_a_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A typo in a hill-climbing script must not read as a green answer (ADR 0075)."""
    cache = _project(tmp_path, Verdict.FAIL, body="X = 1\n")
    assert analysis.main([str(cache.root)]) == analysis.NOTHING_TO_ANALYZE
    assert "no @analyzer declared" in capsys.readouterr().err
    assert analysis.main([str(tmp_path / "no-such-cache")]) == analysis.NOTHING_TO_ANALYZE
    assert analysis.main([str(cache.root), "--suite", str(tmp_path / "missing.py")]) == analysis.NOTHING_TO_ANALYZE
    assert "no suite file at" in capsys.readouterr().err
    assert not cache.analysis.exists()
