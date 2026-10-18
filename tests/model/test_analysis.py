"""``model.analysis``: the Analyzer's vocabulary, result nouns and the ``@analyzer`` declaration."""

# Standard Library
import json
from typing import Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model.analysis import (
    AnalyzerSpec,
    Change,
    Comparison,
    Direction,
    Estimate,
    Finding,
    ParetoPoint,
    analyzer,
)

EST = Estimate(point=0.5, low=0.2366123, high=0.7633877, n=10, method="wilson")


def _comparison(**fields: Any) -> Comparison:
    base: dict[str, Any] = {
        "metric": "verdict",
        "scope": {"harness": "claude"},
        "baseline": "v1",
        "candidate": "v2",
        "change": Change.IMPROVED,
        "baseline_est": EST,
        "candidate_est": Estimate(point=1.0, low=0.72, high=1.0, n=10, method="wilson"),
        "diff": Estimate(point=0.5, low=0.2, high=0.8, n=20, method="mean-diff/bootstrap"),
        "p_better": 0.998,
        "p_value": 0.01,
        "q_value": 0.02,
        "method": "fisher+bh",
        "seed": 0,
    }
    return Comparison(**(base | fields))


def test_the_vocabularies_are_closed() -> None:
    assert [c.value for c in Change] == ["improved", "regressed", "inconclusive", "insufficient"]
    assert [d.value for d in Direction] == ["higher", "lower"]


def test_an_estimate_serialises_rounded_and_names_its_bounds() -> None:
    assert EST.to_dict() == {"point": 0.5, "low": 0.236612, "high": 0.763388, "n": 10, "method": "wilson"}
    assert EST.bound("low") == 0.2366123
    assert Estimate(point=None, low=None, high=None, n=0, method="wilson").to_dict()["point"] is None
    with pytest.raises(ValueError):
        EST.bound("mid")


def test_a_comparison_serialises_its_words_and_describes_its_evidence() -> None:
    cmp = _comparison()
    doc = cmp.to_dict()
    assert (doc["change"], doc["direction"], doc["diff"]["point"], doc["q_value"]) == ("improved", "higher", 0.5, 0.02)
    json.dumps(doc)
    line = cmp.describe()
    assert line.startswith("verdict improved [harness=claude]: v1 0.5 [0.2366, 0.7634] (n=10) -> v2 1 ")
    assert "q=0.02" in line and "P(better)=0.998" in line
    bare = _comparison(change=Change.INSUFFICIENT, diff=None, p_better=None, q_value=None, scope={})
    assert bare.to_dict()["diff"] is None
    assert bare.describe().endswith("(n=10)") and "[all samples]" in bare.describe()


def test_a_finding_and_a_pareto_point_serialise() -> None:
    finding = Finding(analyzer="analyze_x", passed=False, message="no", comparisons=(_comparison(),), details={"k": 1})
    doc = finding.to_dict()
    assert (doc["analyzer"], doc["passed"], doc["details"]) == ("analyze_x", False, {"k": 1})
    assert doc["comparisons"][0]["metric"] == "verdict"
    point = ParetoPoint(key={"model": "a"}, quality=EST, cost=EST, on_front=True)
    assert point.to_dict()["key"] == {"model": "a"} and point.to_dict()["on_front"] is True


def test_analyzer_declares_a_spec_bare_or_with_cases() -> None:
    calls: list[object] = []

    @analyzer
    def analyze_bare(analysis: object) -> None:
        calls.append(analysis)

    @analyzer(cases=["eval_a", "eval_b"])
    def analyze_scoped(analysis: object) -> None:
        calls.append(analysis)

    assert isinstance(analyze_bare, AnalyzerSpec)
    assert (analyze_bare.name, analyze_bare.cases) == ("analyze_bare", None)
    assert (analyze_scoped.name, analyze_scoped.cases) == ("analyze_scoped", ("eval_a", "eval_b"))
    analyze_bare("A")
    assert calls == ["A"]


def test_analyzer_refuses_a_misnamed_function_or_a_bare_string_of_cases() -> None:
    def check_things(analysis: object) -> None: ...

    def analyze_ok(analysis: object) -> None: ...

    with pytest.raises(TypeError, match="analyze_"):
        analyzer(check_things)
    with pytest.raises(TypeError, match="sequence of case names"):
        analyzer(cases="eval_a")(analyze_ok)
