"""``Samples``: an immutable collection of graded session records, and the metrics read off them.

Every stored session is one :class:`~pytest_xharness_eval.emit.metrics.CellMetrics`. A
:class:`Samples` holds any set of them -- this sweep, the cache's whole history, one cell
-- and filters, groups and reads values from it without copying a record or changing one.

A *metric* is named three ways, resolved in this order by :func:`record_value`:

1. an Important Metric id (``"cost"``, ``"verdict"``, ``"skill_loaded"``...), read exactly as
   the report reads it, ``per`` division included (ADR 0071);
2. a derived metric: ``"passed"`` (1.0 for a pass, 0.0 for a fail, nothing for an error),
   ``"tool_time_share"`` and ``"context_cost_share"`` per session, and the group statistics
   ``"cost_per_pass"`` and ``"wasted_cost"``, which exist only over a group
   (:meth:`Samples.cost_per_pass`, :meth:`Samples.wasted_cost`), never per session;
3. any numeric field of the record (``"turns"``, ``"skill_cost_share"``...), except the ones
   that are facts about the cell rather than measurements (``family_tier``,
   ``context_window``...), which raise.

**Errors.** An ``error`` did not attempt the task (ADR 0063), so it is never a sample of a
pass rate, ``passed``, ``cost_per_pass`` or pass@k; it is counted by the ``errors`` rate.

**Directions.** Each metric is better higher or lower; a few (``subagents``,
``files_written``, ``reasoning_share``...) are neutral, and ranking by one needs the
direction named.

**Scenarios and fingerprints.** A generated scenario id names a *situation*; its
``scenario_fingerprint`` names the bytes it had. Two records of one scenario id with
different fingerprints measured different workspaces and must never be pooled as one
scenario. :meth:`Samples.group` therefore splits by fingerprint automatically whenever it
groups by ``"scenario"``: the key's scenario part is :func:`scenario_identity`,
``"<scenario>@<first 12 of the fingerprint>"``. Filtering with :meth:`Samples.where` reads
the plain field, so ``where(scenario="lint-3")`` still selects every fingerprint of it.
"""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING, Any, Final

# Our Libraries
from pytest_xharness_eval.analyze import stats
from pytest_xharness_eval.emit.index import aggregate_history
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.emit.samples import is_sample
from pytest_xharness_eval.model.metrics import (
    IMPORTANT_METRICS,
    Direction,
    FieldRole,
    ImportantMetric,
    MetricKind,
    rate_value,
    roles,
)
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable, Iterable, Iterator

    # Our Libraries
    from pytest_xharness_eval.model.layout import CacheLayout

#: The fields one cell is: a comparison is only made between samples agreeing on all of them.
CELL_FIELDS: Final = ("skill", "case", "harness", "model", "effort", "treatment", "scenario")
#: The environment axes a sweep varies around a fixed subject.
ENVIRONMENT: Final = ("harness", "model", "effort", "treatment")
#: The derived metrics, beside the record's own fields and the Important Metrics.
PASSED: Final = "passed"
COST_PER_PASS: Final = "cost_per_pass"
WASTED_COST: Final = "wasted_cost"
#: Per-session derivations over two fields: the share of the CLI's run spent inside tool
#: calls (every thread's, so parallel subagents can push it past 1), and the share of the
#: estimate spent carrying tool results through later prompts.
TOOL_TIME_SHARE: Final = "tool_time_share"
CONTEXT_COST_SHARE: Final = "context_cost_share"
#: The group statistics: they exist over a set of sessions, never per session.
_GROUP_STATISTICS: Final = frozenset({COST_PER_PASS, WASTED_COST})

_FIELDS: Final = frozenset(CellMetrics.__dataclass_fields__)
_IMPORTANT: Final = {m.id: m for m in IMPORTANT_METRICS}
#: Each record field's role -- kind, better direction or neutral, or a fact about the cell --
#: declared once, on the field itself (``emit/metrics.py``), so no name list here can drift.
_ROLES: Final = roles(CellMetrics)
#: The derived metrics' roles: they are no field, so they are declared beside their derivation.
_DERIVED: Final = {
    PASSED: FieldRole(MetricKind.RATE, Direction.HIGHER),
    TOOL_TIME_SHARE: FieldRole(MetricKind.FRACTION, None),
    CONTEXT_COST_SHARE: FieldRole(MetricKind.FRACTION, Direction.LOWER),
    COST_PER_PASS: FieldRole(MetricKind.SPREAD, Direction.LOWER),
    WASTED_COST: FieldRole(MetricKind.SPREAD, Direction.LOWER),
}


def important(metric: str) -> ImportantMetric | None:
    """The Important Metric with this id, or None."""
    return _IMPORTANT.get(metric)


def _role(metric: str) -> tuple[MetricKind, Direction | None]:
    """The role of a metric: an Important Metric's, a derived metric's, or a record field's.

    An Important Metric keeps its declared kind; its direction is its field's, except a rate,
    which is better higher for the pass rate and lower for the error rate.

    Raises:
        ValueError: for a fact about the cell, and for a name that is none of the three.
    """
    declared = important(metric)
    if declared is not None:
        if declared.kind is MetricKind.RATE:
            return declared.kind, Direction.HIGHER if declared.counts is Verdict.PASS else Direction.LOWER
        return declared.kind, _ROLES[declared.field].better
    role = _DERIVED.get(metric) or _ROLES.get(metric)
    if role is None:
        raise ValueError(
            f"unknown metric {metric!r}: name an Important Metric id ({', '.join(_IMPORTANT)}), "
            f"{PASSED!r}, {COST_PER_PASS!r}, {WASTED_COST!r}, {TOOL_TIME_SHARE!r}, {CONTEXT_COST_SHARE!r}, "
            "or a numeric CellMetrics field"
        )
    if role.kind is None:
        raise ValueError(f"{metric!r} is a fact about the cell, not a measurement of the run; group by it instead")
    return role.kind, role.better


def kind_of(metric: str) -> MetricKind:
    """How a metric's samples are summarised: the kind its declaration names.

    Raises:
        ValueError: for a name that is no Important Metric, derived metric or measured field.
    """
    return _role(metric)[0]


def direction_of(metric: str) -> Direction:
    """Which way is better for a metric, as its declaration names it.

    Raises:
        ValueError: for an unknown metric, and for a neutral one (delegation, files written,
            thinking share), which has no better direction to assume: name it explicitly.
    """
    better = _role(metric)[1]
    if better is None:
        raise ValueError(f"{metric!r} has no better direction; pass direction=Direction.HIGHER or LOWER explicitly")
    return better


def _ratio(part: float | int | None, whole: float | int | None) -> float | None:
    return None if part is None or not whole else part / whole


def record_value(record: CellMetrics, metric: str) -> float | None:
    """One session's value of ``metric``, or None when the record does not carry it.

    ``passed`` is 1.0 for a pass and 0.0 for a fail; an error is no attempt at the task and
    carries no value, exactly as the ``verdict`` metric reads it.

    Raises:
        ValueError: for an unknown metric, or a group statistic, which has no per-session value.
    """
    if metric in _GROUP_STATISTICS:
        raise ValueError(f"{metric!r} is a group statistic; read it with Samples.{metric}()")
    kind_of(metric)
    declared = important(metric)
    if declared is not None:
        fields = (declared.field, declared.per) if declared.per else (declared.field,)
        return declared.value({name: getattr(record, name) for name in fields})
    if metric == PASSED:
        return rate_value(Verdict.stored(record.verdict))
    if metric == TOOL_TIME_SHARE:
        return _ratio(sum(record.tool_ms_by_name.values()), record.duration_ms) if record.tool_ms_by_name else None
    if metric == CONTEXT_COST_SHARE:
        return _ratio(record.tool_context_cost_usd, record.estimated_cost_usd)
    raw = getattr(record, metric)
    return None if raw is None or isinstance(raw, bool) else float(raw)


def scenario_identity(record: CellMetrics) -> str | None:
    """A scenario as one situation *and* its bytes: ``"<scenario>@<fingerprint[:12]>"``."""
    if record.scenario is None:
        return None
    fp = record.scenario_fingerprint
    return f"{record.scenario}@{fp[:12]}" if fp else record.scenario


def _check_field(name: str) -> None:
    if name not in _FIELDS:
        raise ValueError(f"CellMetrics has no field {name!r}")


def key_value(record: CellMetrics, name: str) -> Any:
    """A record's value for one grouping field; ``scenario`` is its fingerprinted identity."""
    _check_field(name)
    return scenario_identity(record) if name == "scenario" else getattr(record, name)


def _matches(value: Any, wanted: Any) -> bool:
    if callable(wanted):
        return bool(wanted(value))
    if isinstance(wanted, list | tuple | set | frozenset):
        return value in wanted
    return bool(value == wanted)


def _sort_key(key: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple("" if part is None else str(part) for part in key)


class Samples:
    """An immutable, ordered collection of session records: filter it, group it, read it."""

    __slots__ = ("_records",)

    def __init__(self, records: Iterable[CellMetrics] = ()) -> None:
        self._records: tuple[CellMetrics, ...] = tuple(records)

    @classmethod
    def of(cls, records: Iterable[CellMetrics]) -> Samples:
        """Only the graded samples among ``records``: dry runs and unreadable verdicts dropped."""
        return cls(r for r in records if is_sample(r))

    @classmethod
    def stored(cls, cache: CacheLayout) -> Samples:
        """Every graded sample the cache holds, oldest first."""
        return cls.of(aggregate_history(cache))

    # -- collection --------------------------------------------------------------------

    @property
    def records(self) -> tuple[CellMetrics, ...]:
        return self._records

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[CellMetrics]:
        return iter(self._records)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Samples) and self._records == other._records

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Samples({len(self._records)} records)"

    def __add__(self, other: Samples) -> Samples:
        """Both collections, oldest first, each session once (keyed by session, node and start)."""
        seen: set[tuple[str, str, str]] = set()
        merged = []
        for record in sorted((*self._records, *other._records), key=lambda r: r.at):
            identity = (record.session_id, record.node, record.at)
            if record.session_id and identity in seen:
                continue
            seen.add(identity)
            merged.append(record)
        return Samples(merged)

    # -- selection ---------------------------------------------------------------------

    def where(self, predicate: Callable[[CellMetrics], bool] | None = None, /, **fields: Any) -> Samples:
        """The records matching every condition.

        Each keyword names a record field; its value is matched by equality, by membership
        when it is a list, tuple or set, or by calling it when it is callable. ``predicate``
        is called with the whole record.
        """
        for name in fields:
            _check_field(name)
        return Samples(
            r
            for r in self._records
            if (predicate is None or predicate(r))
            and all(_matches(getattr(r, name), wanted) for name, wanted in fields.items())
        )

    def group(self, *fields: str) -> dict[tuple[Any, ...], Samples]:
        """The records split by the values of ``fields``, keys in sorted order.

        Grouping by ``"scenario"`` splits by fingerprint too (see the module docstring).
        """
        buckets: dict[tuple[Any, ...], list[CellMetrics]] = {}
        for record in self._records:
            buckets.setdefault(tuple(key_value(record, f) for f in fields), []).append(record)
        return {key: Samples(buckets[key]) for key in sorted(buckets, key=_sort_key)}

    def levels(self, field: str) -> tuple[Any, ...]:
        """The distinct values of one grouping field, sorted."""
        return tuple(key[0] for key in self.group(field))

    def first_seen(self, field: str) -> tuple[Any, ...]:
        """The distinct non-None values of ``field`` in the order they first appear by ``at``."""
        _check_field(field)
        order: dict[Any, None] = {}
        for record in sorted(self._records, key=lambda r: r.at):
            value = getattr(record, field)
            if value is not None and value != "":
                order.setdefault(value, None)
        return tuple(order)

    def last_seen(self, field: str) -> tuple[Any, ...]:
        """The distinct non-None values of ``field``, ordered by their most recent appearance by ``at``.

        The last is the value the newest record carries: after a revert from ``v2`` back to
        ``v1`` the order is ``(v2, v1)``, so the last is the subject as it now stands.
        """
        _check_field(field)
        order: dict[Any, None] = {}
        for record in sorted(self._records, key=lambda r: r.at):
            value = getattr(record, field)
            if value is not None and value != "":
                order.pop(value, None)
                order[value] = None
        return tuple(order)

    def latest(self, field: str = "subject_version") -> Samples:
        """The records carrying the value of ``field`` that the most recent record carries."""
        seen = self.last_seen(field)
        return self.where(**{field: seen[-1]}) if seen else Samples()

    # -- values ------------------------------------------------------------------------

    def values(self, metric: str) -> list[float]:
        """Every record's value of ``metric``; a record that does not carry it is left out."""
        return [v for r in self._records if (v := record_value(r, metric)) is not None]

    def passes(self) -> int:
        """How many records passed."""
        return int(sum(self.values(PASSED)))

    def attempted(self) -> Samples:
        """The records graded pass or fail: every error, which never attempted the task, dropped."""
        return self.where(lambda r: record_value(r, PASSED) is not None)

    def cost_per_pass(self) -> float | None:
        """Total estimated cost of the attempted records over their passes; None with no pass or no priced record.

        Errors are skipped explicitly, on both sides: an error is no attempt, so neither its
        cost nor its absence of a pass says what a pass costs.
        """
        attempted = self.attempted()
        costs = attempted.values("cost")
        passes = attempted.passes()
        return sum(costs) / passes if costs and passes else None

    def wasted_cost(self) -> float | None:
        """The summed estimated cost of the failed records: what attempts that did not pass cost.

        0.0 when nothing failed; None when no failed record is priced and something failed.
        """
        failed = self.where(verdict=Verdict.FAIL.value)
        costs = failed.values("cost")
        if len(failed) and not costs:
            return None
        return float(sum(costs))

    def pass_at_k(self, k: int) -> float | None:
        """The unbiased chance that at least one of ``k`` attempts passes; None with fewer than ``k`` attempts."""
        n, c = len(self.attempted()), self.passes()
        return stats.pass_at_k(n, c, k) if n >= k else None

    def pass_hat_k(self, k: int) -> float | None:
        """pass^k: the unbiased chance that all ``k`` attempts pass, the reliability reading; None below ``k``."""
        n, c = len(self.attempted()), self.passes()
        return stats.pass_hat_k(n, c, k) if n >= k else None
