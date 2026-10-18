"""The Analyzer's nouns: what a comparison concluded, and how a suite declares an analyzer.

A cell's samples answer "how did this cell do?". An *analysis* asks the questions across
cells and across runs: which environment is best, did the new subject version regress,
which scenarios are fragile. The arithmetic lives in :mod:`pytest_xharness_eval.analyze`;
this module holds the vocabulary every layer above it shares and the result nouns an
:class:`~pytest_xharness_eval.emit.findings.AnalysisReport` serialises.

* :class:`Change` -- the four words a comparison may conclude, and no fifth. A tiny sample
  is :attr:`Change.INSUFFICIENT`, never a coin-flip "improved"; anything the evidence does
  not settle is :attr:`Change.INCONCLUSIVE`, which is the default.
* :class:`~pytest_xharness_eval.model.metrics.Direction` -- whether more of a metric is better,
  declared with the metrics in ``model/metrics.py`` and used here by :class:`Comparison`.
* :class:`Estimate`, :class:`Comparison`, :class:`ParetoPoint`, :class:`Finding` -- frozen
  results, each with the ``to_dict`` its JSON is.
* :func:`analyzer` -- the decorator an ``eval_*.py`` module declares an ``analyze_*``
  function with, which becomes an :class:`AnalyzerSpec`.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, overload

# Our Libraries
from pytest_xharness_eval.model.metrics import Direction

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Sequence

    #: An ``analyze_*`` function. Its one argument is an
    #: :class:`~pytest_xharness_eval.analyze.questions.Analysis`, which lives above this layer
    #: and so is not named here (ADR 0039); it returns nothing and fails by raising
    #: ``AssertionError``.
    AnalyzerFn = Callable[[Any], None]

#: The name every analyzer function carries, so a reader of a suite finds them by sight.
ANALYZER_PREFIX = "analyze_"


class Change(StrEnum):
    """What comparing a candidate with a baseline concluded about one metric in one scope."""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT = "insufficient"


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


@dataclass(frozen=True, slots=True, kw_only=True)
class Estimate:
    """A point estimate with its interval, the samples behind it, and how it was made.

    ``point`` (and the bounds) are None when ``n`` is zero: no value is ever invented for
    an empty group. ``method`` names the estimator, e.g. ``"wilson"`` or
    ``"median/bootstrap"``, so a reader knows what kind of interval it holds.
    """

    point: float | None
    low: float | None
    high: float | None
    n: int
    method: str

    def bound(self, which: str) -> float | None:
        """``"low"``, ``"point"`` or ``"high"``: the one number a threshold is held against."""
        if which not in ("low", "point", "high"):
            raise ValueError(f"bound must be 'low', 'point' or 'high', got {which!r}")
        value: float | None = getattr(self, which)
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": _round(self.point),
            "low": _round(self.low),
            "high": _round(self.high),
            "n": self.n,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Comparison:
    """A candidate against a baseline on one metric, within one matched scope.

    ``scope`` is the cell both sides were measured in (``{"harness": "claude", ...}``): a
    comparison is only ever made between samples of the *same* cell. ``diff`` is
    candidate minus baseline. ``p_better`` is the probability the candidate is better in
    the metric's direction; ``p_value`` the two-sided test of no difference and ``q_value``
    that p-value after Benjamini-Hochberg correction across every scope compared at once.
    The statistical fields are None when the comparison is :attr:`Change.INSUFFICIENT`.
    """

    metric: str
    scope: dict[str, Any]
    baseline: str
    candidate: str
    change: Change
    baseline_est: Estimate
    candidate_est: Estimate
    diff: Estimate | None
    p_better: float | None
    method: str
    seed: int
    direction: Direction = Direction.HIGHER
    p_value: float | None = None
    q_value: float | None = None

    def describe(self) -> str:
        """One evidence-rich line: what moved, where, by how much, and how sure."""
        scope = ", ".join(f"{k}={v}" for k, v in self.scope.items()) or "all samples"
        line = (
            f"{self.metric} {self.change.value} [{scope}]: "
            f"{self.baseline} {_fmt(self.baseline_est)} -> {self.candidate} {_fmt(self.candidate_est)}"
        )
        if self.diff is not None:
            line += f"; diff {_fmt(self.diff)}"
        if self.q_value is not None:
            line += f"; q={self.q_value:.3g}"
        if self.p_better is not None:
            line += f"; P(better)={self.p_better:.3f}"
        return line

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "scope": dict(self.scope),
            "baseline": self.baseline,
            "candidate": self.candidate,
            "change": self.change.value,
            "direction": self.direction.value,
            "baseline_est": self.baseline_est.to_dict(),
            "candidate_est": self.candidate_est.to_dict(),
            "diff": self.diff.to_dict() if self.diff else None,
            "p_better": _round(self.p_better),
            "p_value": _round(self.p_value),
            "q_value": _round(self.q_value),
            "method": self.method,
            "seed": self.seed,
        }


def _fmt(est: Estimate) -> str:
    if est.point is None:
        return f"(n={est.n})"
    return f"{est.point:.4g} [{est.low:.4g}, {est.high:.4g}] (n={est.n})"


@dataclass(frozen=True, slots=True, kw_only=True)
class ParetoPoint:
    """One group on (or off) the quality/cost frontier, with the two estimates that placed it."""

    key: dict[str, Any]
    quality: Estimate
    cost: Estimate
    on_front: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": dict(self.key),
            "quality": self.quality.to_dict(),
            "cost": self.cost.to_dict(),
            "on_front": self.on_front,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """What one analyzer concluded: whether it held, why, and the evidence behind it."""

    analyzer: str
    passed: bool
    message: str = ""
    comparisons: tuple[Comparison, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer": self.analyzer,
            "passed": self.passed,
            "message": self.message,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class AnalyzerSpec:
    """An ``analyze_*`` function as a suite declared it.

    ``cases`` narrows the analysis to the samples of those case names; None means every
    case of the suite. Calling the spec calls the function.
    """

    fn: AnalyzerFn
    name: str
    cases: tuple[str, ...] | None = None

    def __call__(self, analysis: Any) -> None:
        self.fn(analysis)


def _spec(fn: AnalyzerFn, cases: Sequence[str] | None) -> AnalyzerSpec:
    name = getattr(fn, "__name__", "")
    if not callable(fn) or not name.startswith(ANALYZER_PREFIX):
        raise TypeError(f"@analyzer decorates a function named {ANALYZER_PREFIX}*, got {name or fn!r}")
    if isinstance(cases, str):
        raise TypeError(f"@analyzer cases= takes a sequence of case names, got the string {cases!r}")
    return AnalyzerSpec(fn=fn, name=name, cases=tuple(cases) if cases else None)


@overload
def analyzer(fn: AnalyzerFn, /) -> AnalyzerSpec: ...


@overload
def analyzer(*, cases: Sequence[str] | None = None) -> Callable[[AnalyzerFn], AnalyzerSpec]: ...


def analyzer(
    fn: AnalyzerFn | None = None, /, *, cases: Sequence[str] | None = None
) -> AnalyzerSpec | Callable[[AnalyzerFn], AnalyzerSpec]:
    """Declare an ``analyze_*(analysis) -> None`` function, bare or with ``cases=``.

    ``@analyzer`` and ``@analyzer(cases=["eval_lint"])`` both work. The function fails by
    raising ``AssertionError`` (the ``expect_*`` helpers on the analysis do that with the
    evidence attached); any other exception is an error in the analyzer itself.

    Raises:
        TypeError: if the function is not named ``analyze_*``, or ``cases`` is a bare string.
    """
    if fn is not None:
        return _spec(fn, cases)

    def wrap(inner: AnalyzerFn) -> AnalyzerSpec:
        return _spec(inner, cases)

    return wrap
