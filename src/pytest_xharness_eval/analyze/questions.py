"""``Analysis``: the questions an ``analyze_*`` function asks of every sample a cache holds.

An analyzer is handed one :class:`Analysis` over the cache's history plus the sweep that
just ran. It asks three families of question:

* **The environment as the variable** -- :meth:`Analysis.summarise`, :meth:`~Analysis.effects`,
  :meth:`~Analysis.best`, :meth:`~Analysis.pareto`, :meth:`~Analysis.tiers`: which harness,
  model, effort or treatment does a fixed subject best under, and at what cost?
* **The subject as the variable** -- :meth:`~Analysis.versions`, :meth:`~Analysis.compare`,
  :meth:`~Analysis.trend`, :meth:`~Analysis.regressions`: did the tool or skill under test
  get better or worse between versions, cell by matched cell?
* **The scenario as the variable** -- :meth:`~Analysis.fragile`, :meth:`~Analysis.broken`,
  :meth:`~Analysis.failures`: which generated situations break it, which never get graded,
  and how?

**Versions pool unless narrowed.** :meth:`~Analysis.summarise`, :meth:`~Analysis.best`,
:meth:`~Analysis.pareto`, :meth:`~Analysis.tiers` and :meth:`~Analysis.reliability` read
every sample the cache holds, whatever subject version it measured. To ask about the subject
as it now stands, narrow first: ``analysis.at_version().pareto()``.

**Errors are not attempts.** An ``error`` never reached a grade the skill earned (ADR 0063),
so it is no sample of a pass rate, of ``fragile`` or of ``reliability``; :meth:`~Analysis.broken`
and the ``errors`` metric count it.

The ``expect_*`` helpers turn an answer into a verdict: each raises
:class:`AnalysisFailure`, an ``AssertionError`` carrying the comparisons and details that
justify it, which :func:`pytest_xharness_eval.analyze.run` records as a failed finding.

Every interval is at ``confidence``, every resample is seeded by ``seed``, and every group
with fewer than ``min_n`` samples is treated as insufficient rather than guessed at.
"""

from __future__ import annotations

# Standard Library
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.analyze.compare import Arms
from pytest_xharness_eval.analyze.compare import compare as compare_arms
from pytest_xharness_eval.analyze.estimate import centre, estimate, of_cells
from pytest_xharness_eval.analyze.sampleset import (
    CELL_FIELDS,
    ENVIRONMENT,
    PASSED,
    Samples,
    direction_of,
    kind_of,
)
from pytest_xharness_eval.model.findings import Change, Comparison, Estimate, ParetoPoint
from pytest_xharness_eval.model.metrics import Direction
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Mapping, Sequence

#: Resamples an effect's interval draws; each one re-estimates every cell.
_EFFECT_RESAMPLES = 500
#: What a regression gate can and cannot see, stated wherever it finds nothing to compare.
_POWER_NOTE = (
    "Each side needs at least min_n samples per cell, and min_n is a floor, not power: at 3 "
    "samples a side a two-sided Fisher test cannot reach p <= 0.05 even at 3/3 against 0/3 "
    "(p = 0.10), so only a gross pass-rate change is ever detectable. Run each cell 5 or more "
    "times per version to give the gate a chance (e.g. --xharness-repeat 5)."
)


class AnalysisFailure(AssertionError):
    """An ``expect_*`` that did not hold, with the evidence a finding reports."""

    def __init__(
        self, message: str, *, comparisons: Sequence[Comparison] = (), details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.comparisons = tuple(comparisons)
        self.details = dict(details or {})


class Unbalanced(ValueError):
    """A main effect asked of slices that do not each hold every level of the factor."""

    def __init__(self, factor: str, missing: Sequence[tuple[tuple[Any, ...], Any]]) -> None:
        shown = "; ".join(f"slice {s} lacks {factor}={lvl!r}" for s, lvl in missing[:8])
        more = f" (and {len(missing) - 8} more)" if len(missing) > 8 else ""
        super().__init__(
            f"unbalanced design for a main effect of {factor!r}: {shown}{more}. "
            "Narrow `within`, run the missing cells, or pass drop_unbalanced=True"
        )
        self.missing = list(missing)


def _plain(value: Any) -> Any:
    """``value`` as JSON-able builtins: ``to_dict`` where a noun has one, tuple keys joined with ``/``."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {("/".join(map(str, k)) if isinstance(k, tuple) else str(k)): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _scope(by: Sequence[str], key: tuple[Any, ...]) -> dict[str, Any]:
    return dict(zip(by, key, strict=True))


def _label(scope: Mapping[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in scope.items()) or "all samples"


def _fmt(est: Estimate) -> str:
    if est.point is None:
        return f"no samples (n={est.n})"
    return f"{est.point:.4g} [{est.low:.4g}, {est.high:.4g}] (n={est.n}, {est.method})"


@dataclass(frozen=True, eq=False, kw_only=True)
class Analysis:
    """Every sample of a cache, and the statistics an analyzer reads them with.

    ``history`` is what the cache held, ``current`` what this sweep graded; the two are
    merged into :attr:`samples` with each session once, oldest first.
    """

    history: Samples
    current: Samples = field(default_factory=Samples)
    seed: int = 0
    min_n: int = 3
    confidence: float = 0.95
    #: What the analyzer chose to publish with :meth:`note`, carried onto its finding whether
    #: it passed or failed: a hill-climbing loop reads the front, not just the verdict.
    notes: dict[str, Any] = field(default_factory=dict)
    samples: Samples = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "samples", self.history + self.current)

    def _narrowed(self, **fields: Any) -> Analysis:
        return Analysis(
            history=self.history.where(**fields),
            current=self.current.where(**fields),
            seed=self.seed,
            min_n=self.min_n,
            confidence=self.confidence,
            notes=self.notes,
        )

    def for_cases(self, cases: Sequence[str]) -> Analysis:
        """The same analysis narrowed to the samples of these case names."""
        return self._narrowed(case=tuple(cases))

    def at_version(self, version: str | None = None, field: str = "subject_version") -> Analysis:
        """The same analysis narrowed to one subject version: ``version``, or the current one.

        The current version is the one the most recently run sample (by ``at``) measured,
        so after a revert it is the reverted-to version. With no version recorded at all it
        narrows to the samples that carry none, which is every one of them.
        """
        seen = self.versions(field)
        return self._narrowed(**{field: version if version is not None else (seen[-1] if seen else None)})

    def note(self, key: str, value: Any) -> Any:
        """Publish ``value`` under ``key`` on this analyzer's finding, and return it.

        A value with ``to_dict`` (an :class:`Estimate`, a :class:`Comparison`) is stored as
        its dict; mappings and sequences of them are converted element by element.
        """
        self.notes[key] = _plain(value)
        return value

    # -- the environment as the variable -----------------------------------------------

    def estimate(self, metric: str, on: Samples | None = None) -> Estimate:
        """``metric`` over ``on`` (default: every sample), by its kind's estimator."""
        return estimate(self.samples if on is None else on, metric, seed=self.seed, confidence=self.confidence)

    def summarise(self, metric: str, by: Sequence[str] = ()) -> dict[tuple[Any, ...], Estimate]:
        """``metric``'s estimate for each group of ``by`` (the empty key for no grouping)."""
        return {key: self.estimate(metric, group) for key, group in self.samples.group(*by).items()}

    def effects(
        self,
        factor: str,
        metric: str,
        within: Sequence[str] | None = None,
        *,
        drop_unbalanced: bool = False,
    ) -> dict[Any, Estimate]:
        """Each level of ``factor``'s main effect on ``metric``: its cell centre minus the slice's mean.

        The samples are sliced by ``within`` (default: every cell field but ``factor``, so
        everything else is held fixed). An effect is only defined when every slice holds
        every level with at least ``min_n`` samples; then each cell weighs the same, and
        the effect is averaged over slices. An unbalanced design raises :class:`Unbalanced`
        unless ``drop_unbalanced``, which keeps only the complete slices.
        """
        slicing = tuple(f for f in CELL_FIELDS if f != factor) if within is None else tuple(within)
        levels = self.samples.levels(factor)
        cells, missing = self._effect_cells(factor, metric, slicing, levels)
        if missing and not drop_unbalanced:
            raise Unbalanced(factor, missing)
        incomplete = {s for s, _ in missing}
        cells = {s: by_level for s, by_level in cells.items() if s not in incomplete}
        if not cells:
            raise Unbalanced(factor, missing)
        _, stat = centre(kind_of(metric))
        point = _main_effects(cells, levels, stat)
        rng = random.Random(self.seed)
        draws: dict[Any, list[float]] = {lvl: [] for lvl in levels}
        for _ in range(_EFFECT_RESAMPLES):
            resampled = {s: {lvl: rng.choices(v, k=len(v)) for lvl, v in by.items()} for s, by in cells.items()}
            for lvl, eff in _main_effects(resampled, levels, stat).items():
                draws[lvl].append(eff)
        out = {}
        for lvl in levels:
            low, high = stats.percentile_interval(draws[lvl], self.confidence)
            n = sum(len(by[lvl]) for by in cells.values())
            out[lvl] = Estimate(point=point[lvl], low=low, high=high, n=n, method="main-effect/bootstrap")
        return out

    def _effect_cells(
        self, factor: str, metric: str, slicing: tuple[str, ...], levels: tuple[Any, ...]
    ) -> tuple[dict[tuple[Any, ...], dict[Any, list[float]]], list[tuple[tuple[Any, ...], Any]]]:
        cells: dict[tuple[Any, ...], dict[Any, list[float]]] = {}
        missing: list[tuple[tuple[Any, ...], Any]] = []
        for key, part in self.samples.group(*slicing).items():
            by_level = {lvl[0]: group.values(metric) for lvl, group in part.group(factor).items()}
            for lvl in levels:
                if len(by_level.get(lvl, [])) < self.min_n:
                    missing.append((key, lvl))
            cells[key] = by_level
        return cells, missing

    def best(
        self, metric: str, by: Sequence[str] = ENVIRONMENT, direction: Direction | None = None
    ) -> list[tuple[tuple[Any, ...], Estimate]]:
        """Groups ranked best first by ``metric``'s point; groups below ``min_n`` trail, unranked."""
        way = direction or direction_of(metric)
        summary = self.summarise(metric, by)
        ranked = [(k, e) for k, e in summary.items() if e.n >= self.min_n and e.point is not None]
        ranked.sort(key=lambda item: item[1].point or 0.0, reverse=way is Direction.HIGHER)
        return ranked + [(k, e) for k, e in summary.items() if (k, e) not in ranked]

    def pareto(
        self, quality: str = "verdict", cost: str = "cost", by: Sequence[str] = ENVIRONMENT
    ) -> list[ParetoPoint]:
        """Every group with ``min_n`` samples, flagged when on the quality/cost frontier.

        Conservative on both axes: quality is held at its pessimistic bound (a pass rate's
        Wilson low) and cost at its pessimistic bound (the bootstrap high), so a group earns
        its place on the front with evidence, not with one lucky run. Front first, cheapest first.
        """
        q_way, c_way = direction_of(quality), direction_of(cost)
        groups = [
            (key, self.estimate(quality, g), self.estimate(cost, g))
            for key, g in self.samples.group(*by).items()
            if len(g) >= self.min_n
        ]
        # Both axes oriented so that larger is better, each at its pessimistic bound.
        oriented = [
            (key, q, c, _oriented(q, q_way), _oriented(c, c_way))
            for key, q, c in groups
            if q.point is not None and c.point is not None
        ]
        points = []
        for key, q, c, qs, cs in oriented:
            dominated = any(
                (oq >= qs and oc >= cs) and (oq > qs or oc > cs) for k2, _, _, oq, oc in oriented if k2 != key
            )
            points.append(ParetoPoint(key=_scope(by, key), quality=q, cost=c, on_front=not dominated))
        points.sort(key=lambda p: (not p.on_front, p.cost.point or 0.0))
        return points

    def tiers(self, metric: str) -> dict[int | None, Estimate]:
        """``metric`` by family tier across harnesses: is a tier-3 model better whoever hosts it?

        Each cell of a tier with ``min_n`` samples weighs the same: its own centre, then the
        mean over the tier's cells, with a two-level bootstrap interval (cells, then samples).
        Pooling raw samples would let the most-run harness speak for the whole tier. A tier
        with no cell at ``min_n`` estimates nothing. Pools subject versions unless narrowed.
        """
        out: dict[int | None, Estimate] = {}
        cells = tuple(f for f in CELL_FIELDS if f != "family_tier")
        for (tier,), group in self.samples.group("family_tier").items():
            values = [vals for g in group.group(*cells).values() if len(vals := g.values(metric)) >= self.min_n]
            out[tier] = of_cells(values, kind_of(metric), seed=self.seed, confidence=self.confidence)
        return out

    # -- the subject as the variable ---------------------------------------------------

    def versions(self, field: str = "subject_version") -> tuple[Any, ...]:
        """The subject's versions ordered by when each was *last* measured: the last is the current one.

        After a revert from ``v2`` to ``v1`` this is ``(v2, v1)``, so ``versions()[-1]`` is the
        subject as it now stands and ``versions()[-2]`` the one it replaced. For the order
        they first appeared in, read ``analysis.samples.first_seen(field)``.
        """
        return self.samples.last_seen(field)

    def _arm(self, side: str | Samples, label: str, field: str) -> tuple[Samples, str]:
        if isinstance(side, Samples):
            return side, label
        return self.samples.where(**{field: side}), side

    def compare(
        self,
        metric: str,
        baseline: str | Samples,
        candidate: str | Samples,
        by: Sequence[str] = CELL_FIELDS,
        direction: Direction | None = None,
        field: str = "subject_version",
    ) -> list[Comparison]:
        """``candidate`` against ``baseline`` in every cell both measured (see :mod:`.compare`).

        A side is a value of ``field`` (a subject version, by default) or any :class:`Samples`.
        """
        base, base_label = self._arm(baseline, "baseline", field)
        cand, cand_label = self._arm(candidate, "candidate", field)
        return compare_arms(
            Arms(baseline=base, candidate=cand, baseline_label=base_label, candidate_label=cand_label),
            metric,
            by=tuple(by),
            direction=direction or direction_of(metric),
            seed=self.seed,
            min_n=self.min_n,
            confidence=self.confidence,
        )

    def trend(
        self, metric: str, by: Sequence[str] = (), field: str = "subject_version"
    ) -> dict[tuple[Any, ...], list[tuple[Any, Estimate]]]:
        """``metric`` per group, version by version in first-measured order."""
        order = self.samples.first_seen(field)
        out: dict[tuple[Any, ...], list[tuple[Any, Estimate]]] = {}
        for key, group in self.samples.group(*by).items():
            present = set(group.levels(field))
            out[key] = [(v, self.estimate(metric, group.where(**{field: v}))) for v in order if v in present]
        return out

    def regressions(self, metric: str = "verdict", by: Sequence[str] = CELL_FIELDS) -> list[Comparison]:
        """The cells where the latest subject version regressed against the one before it."""
        seen = self.versions()
        if len(seen) < 2:
            return []
        return [c for c in self.compare(metric, seen[-2], seen[-1], by) if c.change is Change.REGRESSED]

    # -- the scenario as the variable --------------------------------------------------

    def fragile(self, by: Sequence[str] = ("case", "scenario")) -> list[tuple[tuple[Any, ...], Estimate]]:
        """Scenarios ranked by failure rate, most fragile first: the input to adversarial generation.

        Over the attempted samples only: an error is no evidence the scenario is hard (see
        :meth:`broken`).
        """
        return self._ranked_scenarios(by, lambda group: [1.0 - v for v in group.values(PASSED)])

    def broken(self, by: Sequence[str] = ("case", "scenario")) -> list[tuple[tuple[Any, ...], Estimate]]:
        """Scenarios ranked by error rate, most often ungraded first: a seed, tool or harness to fix, not a skill."""
        return self._ranked_scenarios(by, lambda group: group.values("errors"))

    def _ranked_scenarios(
        self, by: Sequence[str], read: Callable[[Samples], list[float]]
    ) -> list[tuple[tuple[Any, ...], Estimate]]:
        scenarios = self.samples.where(scenario=lambda s: s is not None)
        out = []
        for key, group in scenarios.group(*by).items():
            values = read(group)
            if values:
                out.append((key, self._rate(values)))
        out.sort(key=lambda item: (-(item[1].point or 0.0), -(item[1].low or 0.0)))
        return out

    def _rate(self, values: list[float]) -> Estimate:
        low, high = stats.wilson_interval(sum(values), len(values), self.confidence)
        return Estimate(point=sum(values) / len(values), low=low, high=high, n=len(values), method="wilson")

    def failures(self, by: Sequence[str] = ()) -> dict[tuple[Any, ...], dict[tuple[str, str], int]]:
        """Why the samples that did not pass did not, counted per group by ``(verdict, failure)``, most common first.

        Keyed by the verdict too, so a grader's fail and a harness error that happen to say
        the same thing are never one cause. The recorded failure has its per-cell paths
        redacted (``<workspace>``, ``<scratch>``, ``<cache>``), so one cause groups as one.
        """
        failed = self.samples.where(lambda r: r.verdict != Verdict.PASS.value)
        return {
            key: dict(Counter((r.verdict, r.failure or "(no reason recorded)") for r in group).most_common())
            for key, group in failed.group(*by).items()
        }

    def reliability(self, k: int, by: Sequence[str] = ENVIRONMENT) -> dict[tuple[Any, ...], dict[str, Any]]:
        """pass@k and pass^k per group over its attempted samples (errors excluded).

        ``pass_at_k`` is the chance at least one of ``k`` attempts passes; ``pass_hat_k`` the
        chance all ``k`` do -- the reading for a skill that must work every time. Both are the
        unbiased estimators from ``passes`` of ``n``, and None while ``n < k``.
        """
        return {
            key: {
                "n": len(group.attempted()),
                "passes": group.passes(),
                "pass_at_k": group.pass_at_k(k),
                "pass_hat_k": group.pass_hat_k(k),
            }
            for key, group in self.samples.group(*by).items()
        }

    # -- assertions --------------------------------------------------------------------

    def expect_no_regression(
        self,
        metric: str = "verdict",
        baseline: str | Samples | None = None,
        candidate: str | Samples | None = None,
        by: Sequence[str] = CELL_FIELDS,
        direction: Direction | None = None,
    ) -> list[Comparison]:
        """Fail when any matched cell regressed; by default the current version against the one before.

        A gate that cannot see a regression must not report that there was none, so it also
        fails -- never passes on zero evidence -- when only one subject version is recorded
        (and no sides were named), and when no matched cell had ``min_n`` samples on both
        sides. Returns every comparison made.
        """
        if baseline is None or candidate is None:
            seen = self.versions()
            if len(seen) < 2:
                raise AnalysisFailure(
                    f"only {len(seen)} subject version recorded ({', '.join(map(str, seen)) or 'none'}), so no "
                    "regression can be judged; run the sweep again after the subject changes, or name both sides",
                    details={"metric": metric, "versions": list(seen)},
                )
            baseline = seen[-2] if baseline is None else baseline
            candidate = seen[-1] if candidate is None else candidate
        made = self.compare(metric, baseline, candidate, by, direction)
        regressed = [c for c in made if c.change is Change.REGRESSED]
        if regressed:
            lines = "\n".join(f"  {c.describe()}" for c in regressed)
            raise AnalysisFailure(
                f"{len(regressed)} of {len(made)} cells regressed on {metric}:\n{lines}", comparisons=made
            )
        if not any(c.change is not Change.INSUFFICIENT for c in made):
            raise AnalysisFailure(
                f"nothing was comparable on {metric}: {len(made)} matched cell(s), none with min_n={self.min_n} "
                f"samples on both sides. {_POWER_NOTE}",
                comparisons=made,
                details={"metric": metric, "min_n": self.min_n, "matched": len(made)},
            )
        return made

    def expect_at_least(
        self, metric: str, value: float, by: Sequence[str] = (), bound: str = "low"
    ) -> dict[tuple[Any, ...], Estimate]:
        """Fail for every group whose ``bound`` of ``metric`` is below ``value`` (or has no samples)."""
        return self._expect_bound(metric, value, by, bound, at_least=True)

    def expect_at_most(
        self, metric: str, value: float, by: Sequence[str] = (), bound: str = "high"
    ) -> dict[tuple[Any, ...], Estimate]:
        """Fail for every group whose ``bound`` of ``metric`` is above ``value`` (or has no samples)."""
        return self._expect_bound(metric, value, by, bound, at_least=False)

    def _expect_bound(
        self, metric: str, value: float, by: Sequence[str], bound: str, *, at_least: bool
    ) -> dict[tuple[Any, ...], Estimate]:
        summary = self.summarise(metric, by)
        bad = []
        for key, est in summary.items():
            got = est.bound(bound)
            if got is None or (got < value if at_least else got > value):
                bad.append(f"  [{_label(_scope(by, key))}] {bound} {got} : {_fmt(est)}")
        if bad or not summary:
            word = "at least" if at_least else "at most"
            shown = "\n".join(bad) or "  no samples at all"
            raise AnalysisFailure(
                f"{metric} {bound} bound not {word} {value} in {len(bad) or 1} group(s):\n{shown}",
                details={"metric": metric, "value": value, "bound": bound, "by": list(by)},
            )
        return summary

    def expect_pareto_contains(
        self,
        match: Mapping[str, Any],
        quality: str = "verdict",
        cost: str = "cost",
        by: Sequence[str] = ENVIRONMENT,
    ) -> list[ParetoPoint]:
        """Fail unless a group whose key agrees with every item of ``match`` is on the frontier."""
        points = self.pareto(quality, cost, by)
        matched = [p for p in points if all(p.key.get(k) == v for k, v in match.items())]
        if not any(p.on_front for p in matched):
            front = "\n".join(
                f"  [{_label(p.key)}] {quality} {_fmt(p.quality)}; {cost} {_fmt(p.cost)}" for p in points if p.on_front
            )
            why = "is not on the frontier" if matched else f"matches no group with n >= {self.min_n}"
            raise AnalysisFailure(
                f"{_label(match)} {why}; the frontier is:\n{front or '  (empty)'}",
                details={"match": dict(match), "points": [p.to_dict() for p in points]},
            )
        return points


def _oriented(est: Estimate, way: Direction) -> float:
    """The estimate's pessimistic bound, negated for a lower-is-better metric so larger is better."""
    if way is Direction.HIGHER:
        return float(est.low if est.low is not None else est.point or 0.0)
    return -float(est.high if est.high is not None else est.point or 0.0)


def _main_effects(
    cells: Mapping[tuple[Any, ...], Mapping[Any, Sequence[float]]], levels: Sequence[Any], stat: stats.Stat
) -> dict[Any, float]:
    effects: dict[Any, float] = dict.fromkeys(levels, 0.0)
    for by_level in cells.values():
        centres = {lvl: stat(by_level[lvl]) for lvl in levels}
        grand = stats.mean(list(centres.values()))
        for lvl in levels:
            effects[lvl] += (centres[lvl] - grand) / len(cells)
    return effects
