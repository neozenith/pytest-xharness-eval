"""``report/index.json``: one summary row per captured session (ADR 0020, ADR 0032).

The row is what the page lists a sweep with *without opening a file*: which case, run and
cell a session was, how it graded, what it cost, and the relative paths to its result and
its log. Everything on it is a view over two stored documents -- a session's
``result.json`` and its ``history.json`` -- which is why the values coming off the result
are read defensively: the combine step indexes whatever a cache holds, including captures
written before a field existed.

Splitting this out of the page writer (ADR 0039) separates the two jobs the old ``report``
module did at once: deciding *what a session's summary is*, which the SPA's
``report-ui/src/lib/types.ts`` mirrors as a wire contract, and *assembling the microsite*,
which is :mod:`~pytest_xharness_eval.emit.page`.
"""

from __future__ import annotations

# Standard Library
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Self

# Our Libraries
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model.documents import read_json_object
from pytest_xharness_eval.model.layout import LOG_NAME, RESULT_NAME

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Mapping

    # Our Libraries
    from pytest_xharness_eval.model.layout import CacheLayout, LocatedSession


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexRow:
    """One row of ``report/index.json``: everything the page lists without opening a file.

    The row is a *view over two stored documents* -- a session's ``result.json`` and its
    ``history.json`` -- which is why the values coming off the result are read defensively:
    the combine step indexes whatever a cache holds, including captures written before a
    field existed. The field names are the row's wire format, mirrored by
    ``report-ui/src/lib/types.ts`` and pinned by ``tests/test_units.py``.
    """

    # Which case, run and cell this was.
    case: str
    run: str
    suite: str | None
    skill: str | None
    fixture: str | None
    prompt: str | None
    harness: str | None
    model: str | None
    session_id: str | None
    # How it graded, from the metrics record; None when the session has none.
    verdict: str | None
    at: str | None
    node: str | None
    wall_ms: int | None
    # Where the evidence is, relative to report/ (ADR 0032).
    result: str
    log: str | None
    # What it cost and spent.
    estimated_cost_usd: float | None
    harness_reported_cost_usd: float | None
    rates_applied: dict[str, Any] = field(default_factory=dict)
    accumulative_billed_tokens: int | None = None
    baseline_tokens: int | None = None
    context_window: int | None = None
    peak_context_tokens: int | None = None
    context_window_pct: float | None = None
    final_context_pct: float | None = None
    ttft_ms: int | None = None
    output_tokens_per_sec: float | None = None
    # What it did.
    turns: int | None = None
    reported_turns: int | None = None
    subagents: int = 0
    tool_calls: int = 0
    duration_ms: int | None = None
    files_written: list[str] = field(default_factory=list)
    has_ledger: bool = False
    record_kinds: dict[str, int] = field(default_factory=dict)
    skill_coverage: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, session: LocatedSession, result: Mapping[str, Any], hist: CellMetrics | None) -> Self:
        """Summarise one captured session from its result and its metrics record.

        The session must be a *located* one: the row carries its run and links to its
        evidence relative to ``report/``, and only a directory that knows its coordinates
        can name either (ADR 0038).
        """
        usage = result.get("usage") or {}
        tool_calls = result.get("tool_calls") or {}
        meta = result.get("case") or {}
        return cls(
            case=meta.get("name") or (hist.case if hist else None) or "(unknown case)",
            run=session.run,
            suite=meta.get("suite"),
            skill=meta.get("skill"),
            fixture=meta.get("fixture"),
            prompt=meta.get("prompt"),
            harness=result.get("harness"),
            model=result.get("model"),
            session_id=result.get("session_id"),
            verdict=hist.verdict if hist else None,
            at=hist.at if hist else None,
            node=hist.node if hist else None,
            wall_ms=hist.wall_ms if hist else None,
            result=session.report_link(RESULT_NAME),
            log=session.report_link(LOG_NAME) if session.log.is_file() else None,
            estimated_cost_usd=result.get("estimated_cost_usd"),
            harness_reported_cost_usd=result.get("harness_reported_cost_usd"),
            rates_applied=result.get("rates_applied") or {},
            accumulative_billed_tokens=usage.get("accumulative_billed_tokens"),
            baseline_tokens=result.get("baseline_tokens"),
            context_window=result.get("context_window"),
            peak_context_tokens=result.get("peak_context_tokens"),
            context_window_pct=result.get("context_window_pct"),
            final_context_pct=result.get("final_context_pct"),
            ttft_ms=result.get("ttft_ms"),
            output_tokens_per_sec=result.get("output_tokens_per_sec"),
            turns=result.get("turns"),
            reported_turns=result.get("reported_turns"),
            subagents=len(result.get("subagents") or []),
            tool_calls=sum(int(v) for v in tool_calls.values()),
            duration_ms=result.get("duration_ms"),
            files_written=result.get("files_written") or [],
            has_ledger=bool(result.get("calls")),
            record_kinds=result.get("record_kinds") or {},
            skill_coverage=(result.get("skill_coverage") or {}).get("summary") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """The JSON-ready mapping this row is in ``index.json``."""
        return asdict(self)


def cells(cache: CacheLayout) -> list[dict[str, Any]]:
    """One summary row per captured session, newest first; a session with no result is skipped."""
    rows = []
    for session in cache.sessions():
        result = read_json_object(session.result)
        if result is None:
            continue
        rows.append(IndexRow.of(session, result, CellMetrics.stored(session.history)).to_dict())
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows


def aggregate_history(cache: CacheLayout) -> list[CellMetrics]:
    """Every session's own metrics record, sorted by ``at`` (the combine step, ADR 0032)."""
    records = [m for session in cache.sessions() if (m := CellMetrics.stored(session.history)) is not None]
    records.sort(key=lambda rec: rec.at)
    return records
