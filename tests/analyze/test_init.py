"""``analyze.run``: each analyzer becomes a finding; a failed expectation fails it, a bug propagates."""

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import analyze
from pytest_xharness_eval.analyze import Analysis, Change, Samples, analyzer, run
from tests.analyze import batch


@analyzer
def analyze_holds(analysis: Analysis) -> None:
    analysis.expect_at_least("verdict", 0.1)


@analyzer
def analyze_regresses(analysis: Analysis) -> None:
    analysis.expect_no_regression()


@analyzer
def analyze_plain_assert(analysis: Analysis) -> None:
    assert len(analysis.samples) > 1000, "too few samples"


@analyzer
def analyze_bare_assert(analysis: Analysis) -> None:
    raise AssertionError


@analyzer
def analyze_broken(analysis: Analysis) -> None:
    raise KeyError("bug")


@analyzer(cases=["eval_b"])
def analyze_only_b(analysis: Analysis) -> None:
    assert analysis.samples.levels("case") == ("eval_b",)


def _analysis() -> Analysis:
    return Analysis(
        history=Samples(
            batch(12, 12, subject_version="v1", at="2026-10-01")
            + batch(12, 1, subject_version="v2", at="2026-10-02")
            + batch(3, 3, case="eval_b", at="2026-10-03")
        )
    )


def test_run_turns_each_analyzer_into_a_finding_in_order() -> None:
    specs = [analyze_holds, analyze_regresses, analyze_plain_assert, analyze_bare_assert, analyze_only_b]
    findings = run(specs, _analysis())
    assert [(f.analyzer, f.passed) for f in findings] == [
        ("analyze_holds", True),
        ("analyze_regresses", False),
        ("analyze_plain_assert", False),
        ("analyze_bare_assert", False),
        ("analyze_only_b", True),
    ]
    regressed = findings[1]
    assert "regressed on verdict" in regressed.message
    assert [c.change for c in regressed.comparisons] == [Change.REGRESSED]
    assert findings[2].message.startswith("too few samples")
    assert findings[3].message == "AssertionError"


def test_an_error_that_is_not_a_failed_assertion_propagates() -> None:
    with pytest.raises(KeyError, match="bug"):
        run([analyze_broken], _analysis())


def test_the_public_api_is_exported() -> None:
    assert {"Analysis", "Samples", "analyzer", "run", "Finding", "Comparison", "stats"} <= set(analyze.__all__)
    assert all(hasattr(analyze, name) for name in analyze.__all__)
