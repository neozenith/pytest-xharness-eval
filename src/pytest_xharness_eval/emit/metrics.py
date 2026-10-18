"""``history.json``: one cell's metrics record, as a type (ADR 0018, ADR 0021, ADR 0037).

Every graded cell -- live or replayed -- emits exactly one :class:`CellMetrics`. It is
written beside the cell's evidence, shown in the verbose status word, carried to the xdist
controller, flattened into ``--junitxml``, and combined into ``report/history.jsonl``. Its
field names *are* that wire format, which ``report-ui/src/lib/types.ts`` mirrors, so a
rename here is a wire-format change and ``tests/emit/test_metrics.py`` pins the key set.

The record crosses one boundary as a plain mapping and only one: ``TestReport.user_properties``
is serialised by execnet, which handles builtins only (ADR 0016), so :meth:`CellMetrics.to_dict`
is called at the ``pytest_runtest_makereport`` hook and :meth:`CellMetrics.from_dict` on the
controller side. Everywhere else the record travels as this type.

Metric vocabulary (ADR 0021; the report glossary carries the same names):

* ``estimated_cost_usd``: this plugin's price-table estimate; ``rates_applied``
  records the per-tier rates, the row and the file they came from.
* ``harness_reported_cost_usd``: what the harness CLI itself reported (Claude only).
* ``accumulative_billed_tokens``: every billed token summed over every model call (ADR 0029). The cached
  prefix is re-read each call, so this grows with turns x context.
* ``baseline_tokens``: the prompt of the first call, before the agent acted.
* ``turns``: model API calls; ``reported_turns`` is the CLI's own count.
"""

from __future__ import annotations

# Standard Library
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from types import UnionType
from typing import TYPE_CHECKING, Any, Final, Self, Union, get_args, get_origin, get_type_hints

# Our Libraries
from pytest_xharness_eval.model.case import CaseKind
from pytest_xharness_eval.model.documents import read_json_object
from pytest_xharness_eval.model.metrics import Direction, MetricKind, fact, measured
from pytest_xharness_eval.model.runresult import CostStatus
from pytest_xharness_eval.model.verdict import Verdict

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Mapping
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.layout import CacheLayout
    from pytest_xharness_eval.model.matrix import Cell
    from pytest_xharness_eval.model.runresult import RunResult


def _admitted(hint: Any) -> tuple[type, ...]:
    """The runtime classes one field annotation admits: ``int | None`` -> ``(int, NoneType)``.

    Only the shapes this record's fields actually use are handled -- a class, a union of
    classes, and a parameterised ``dict``/``list`` whose origin is the class to test.
    """
    parts = get_args(hint) if get_origin(hint) in (UnionType, Union) else (hint,)
    return tuple(get_origin(part) or part for part in parts)


@dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What grading a cell observed, and no session log can supply.

    Who ran it, when, for how long by the wall clock, and how it graded. A replay
    recomputes every other field on the record but keeps these four from the previous one,
    because there is nothing to recompute them from (ADR 0023).

    :attr:`verdict` is the vocabulary itself rather than a string that resembles it
    (ADR 0041), and is None only where it came from a stored record that named no verdict
    this version knows -- the one case a replay must carry forward without inventing a
    grade (ADR 0038).
    """

    node: str
    verdict: Verdict | None
    wall_ms: int
    started_at: str
    #: Why a cell that did not pass did not: the first line of what its grader or harness
    #: raised, so a reader groups failures without scraping a pytest log. None on a pass.
    failure: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CellMetrics:
    """One graded cell's metrics record: the document ``history.json`` is.

    Flat and built of builtins on purpose -- see the module docstring for the execnet
    boundary that requires it. Every field carries a default so that
    :meth:`from_dict` can read a record written by an older version of this package, or
    truncated by hand, without failing the combine step; :meth:`of` is the total
    constructor and the only one production code builds a record with.
    """

    # Identity: which cell, of which case, on which harness.
    at: str = ""
    node: str = ""
    suite: str | None = None
    case: str | None = None
    skill: str | None = None
    fixture: str | None = None
    harness: str = ""
    model: str = ""
    # The reasoning-effort rung this cell ran at; empty when it ran at the CLI's own
    # default, which is what every record written before ADR 0049 holds.
    effort: str = ""
    # The treatment this cell ran under; empty for the control, which is what every record
    # written before ADR 0055 holds.
    treatment: str = ""
    # What kind of model this was, from the catalogue (ADR 0057). None on a record of a
    # model the catalogue never described, and on every record written before it.
    line: str | None = None
    family_tier: int | None = fact(None)
    released: str | None = None
    session_id: str = ""
    verdict: str = ""
    failure: str | None = None
    # What kind of case it was (``skill`` or ``scenario``), which generated scenario it ran on
    # and the bytes that scenario had, and which version of the subject it measured: the
    # digest of the paths the case tracks. Empty or None on records written before them.
    kind: str = ""
    scenario: str | None = None
    scenario_fingerprint: str | None = None
    subject_version: str | None = None
    # What it did.
    turns: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    reported_turns: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    # ``tool_calls`` and ``tool_calls_by_name`` are the primary thread's, as the harness
    # counted them (the wire format since ADR 0018); ``tool_calls_by_name_all`` counts every
    # thread's ledger, the same calls ``tool_ms_by_name`` and the tool cost maps sum over, so
    # a per-call average divides like by like.
    tool_calls: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    tool_calls_by_name: dict[str, int] = field(default_factory=dict)
    tool_calls_by_name_all: dict[str, int] = field(default_factory=dict)
    duration_ms: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    # The harness-reported API time, where it reports one; None otherwise.
    api_duration_ms: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    wall_ms: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    # How the CLI ended (ADR 0063, ADR 0064): its exit code, whether it reached the model at
    # all (1 or 0), and -- for a run killed at the wall -- the limit and how long its logs had
    # been silent. None on a record written before them; the timeout pair is None on a run
    # that finished on its own.
    exit_code: int | None = fact(None)
    attempted: int | None = measured(None, MetricKind.FRACTION, Direction.HIGHER)
    timed_out_after_s: int | None = fact(None)
    idle_before_timeout_s: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    # What it cost, and the rates that say so (ADR 0021).
    estimated_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    harness_reported_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    rates_applied: dict[str, Any] = field(default_factory=dict)
    # Calls billed at the long-context tier; None while unpriced (ADR 0051).
    long_context_calls: int | None = measured(None, MetricKind.RARE, Direction.LOWER)
    # What it spent, tier by tier (ADR 0029).
    accumulative_billed_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    baseline_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    input_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    output_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    reasoning_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    cache_read_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    cache_write_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    cache_write_1h_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    cache_write_5m_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    files_written: int = measured(0, MetricKind.SPREAD, None)
    # How close it came to the window, and how fast it ran (ADR 0024).
    context_window: int | None = fact(None)
    peak_context_tokens: int = measured(0, MetricKind.SPREAD, Direction.LOWER)
    final_context_tokens: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    context_window_pct: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    final_context_pct: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    ttft_ms: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    output_tokens_per_sec: float | None = measured(None, MetricKind.SPREAD, Direction.HIGHER)
    record_kinds: dict[str, int] = field(default_factory=dict)
    # The Important Metrics no field above already carried (ADR 0071). None on every record
    # written before they existed, so an old sample drops out of a metric's ``n`` rather than
    # counting as a run that never delegated, compacted or thought.
    subagents: int | None = measured(None, MetricKind.RARE, None)
    subagent_token_share: float | None = measured(None, MetricKind.FRACTION, None)
    subagent_cost_share: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    compactions: int | None = measured(None, MetricKind.RARE, Direction.LOWER)
    reasoning_share: float | None = measured(None, MetricKind.FRACTION, None)
    output_tokens_per_sec_by_model: dict[str, float] = field(default_factory=dict)
    # Which of the skill's files it reached (ADR 0022).
    skill_files: int | None = fact(None)
    skill_files_loaded: int | None = measured(None, MetricKind.SPREAD, Direction.HIGHER)
    skill_scripts: int | None = fact(None)
    skill_scripts_run: int | None = measured(None, MetricKind.SPREAD, Direction.HIGHER)
    skill_not_loaded: list[str] = field(default_factory=list)
    skill_not_run: list[str] = field(default_factory=list)
    # Whether the skill under test triggered at all: 1 when it did, 0 on a skill case where
    # nothing triggered it, None on a scenario case (no skill) and every record written before it.
    skill_triggered: int | None = measured(None, MetricKind.FRACTION, Direction.HIGHER)
    # When the skill under test was triggered and what its use cost (ADR 0073). None when
    # nothing triggered it, on a scenario case, and on records written before it.
    # ``skill_cost_share`` is the *issuing* cost of the skill's tool calls over the run's
    # estimate; ``skill_context_cost_share`` the cost of carrying their results through later
    # prompts over the same estimate. Both are attributions inside the estimate, not additions.
    skill_trigger: str | None = None
    skill_triggered_turn: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    skill_duration_ms: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    skill_tool_calls: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    skill_issuing_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    skill_context_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    skill_cost_share: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    skill_context_cost_share: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    # Every tool call's time and cost, summed and split by tool name (ADR 0073).
    tool_issuing_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    tool_context_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    tool_ms_by_name: dict[str, int] = field(default_factory=dict)
    tool_issuing_cost_usd_by_name: dict[str, float] = field(default_factory=dict)
    tool_context_cost_usd_by_name: dict[str, float] = field(default_factory=dict)
    cache_rereads: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    # The share of prompt tokens served from the cache: how well the run reused its context.
    cache_read_share: float | None = measured(None, MetricKind.FRACTION, Direction.HIGHER)
    # The subagents' spans and per-thread extremes (ADR 0072). One convention: a count or a
    # span over zero subagents is 0, consistent with ``subagents = 0``; a figure that needs a
    # measurement the run lacks (a price, a context window) is None. None on every record
    # written before them. The peak context share is each thread's largest prompt over the
    # run's reported window, the window of the model the primary ran on.
    subagent_ms: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    subagent_max_depth: int | None = measured(None, MetricKind.RARE, Direction.LOWER)
    subagent_max_ms: int | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    subagent_max_cost_usd: float | None = measured(None, MetricKind.SPREAD, Direction.LOWER)
    subagent_peak_context_pct: float | None = measured(None, MetricKind.FRACTION, Direction.LOWER)
    # Which cache root to run the combine step against; a declared field rather than a key
    # written onto the record afterwards (ADR 0032, ADR 0037). Empty means "combine
    # nothing", which is how a dry run stays free of evidence.
    cache: str = ""

    # -- constructors ------------------------------------------------------------------

    @classmethod
    def of(cls, result: RunResult, *, outcome: Outcome, cache: CacheLayout) -> Self:
        """The record for one graded run: everything derived, nothing assigned afterwards.

        Each concern's fields come from one builder; :func:`figures` joins them and refuses
        two builders claiming one field, and a test pins that together they fill every field.
        """
        return cls(**figures(result, outcome=outcome, cache=cache))

    @classmethod
    def dry_run(cls, *, node: str, cell: Cell) -> Self:
        """The record a ``--dry-run`` cell emits: the same document, with nothing measured.

        A dry run used to put a five-key mapping of its own shape on the report, so the
        one thing every reader of ``report.json`` could rely on -- that a cell record is a
        cell record -- did not hold (ADR 0037). ``cache`` stays empty: a dry run invokes
        nothing, so it must leave no evidence and trigger no combine step (ADR 0018).

        A dry run is the fourth word's only producer, and it names it from the vocabulary
        like every other producer does (ADR 0041).
        """
        return cls(
            node=node,
            harness=cell.harness,
            model=cell.model,
            effort=cell.effort or "",
            treatment=cell.treatment or "",
            verdict=Verdict.DRY_RUN.value,
        )

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        """Rebuild the record from a plain mapping: the inverse of :meth:`to_dict`.

        Used at the two places a mapping is all there is: the xdist controller reading what
        execnet shipped, and a reader of a ``history.json`` on disk. A key this version does
        not know is dropped, and so is a value that is not of its field's declared type --
        most often a ``null`` where a ``str`` is declared, which an older capture wrote and
        a hand-truncated one still can. Both cases leave the field at its default, so a
        foreign document degrades to a partial record rather than failing the read *and*
        every reader may trust the declaration: the combine step sorting by ``at`` and a
        replay stamping a run directory from it cannot meet a None there (ADR 0038).
        """
        values: dict[str, Any] = {}
        for key, stored in raw.items():
            admitted = _ADMITTED.get(key)
            if admitted is None:
                continue
            # JSON has one number type, so a float field legitimately arrives as ``0``.
            value = float(stored) if float in admitted and type(stored) is int else stored
            if isinstance(value, admitted):
                values[key] = value
        return cls(**values)

    @classmethod
    def stored(cls, path: Path) -> Self | None:
        """The record written beside a session's evidence, or None when there is none to read.

        A missing or unparsable file is None, not an error: the combine step and the replay
        both index whatever a cache actually holds, including captures from before this
        record existed.
        """
        raw = read_json_object(path)
        return None if raw is None else cls.from_dict(raw)

    # -- derived views -----------------------------------------------------------------

    @property
    def outcome(self) -> Outcome:
        """The four values a replay must keep, since it cannot re-derive them.

        The stored word is read back through the vocabulary, so a record whose verdict is
        absent or foreign carries no verdict forward rather than a word no reader can
        interpret (ADR 0038, ADR 0041).
        """
        return Outcome(
            node=self.node,
            verdict=Verdict.stored(self.verdict),
            wall_ms=self.wall_ms,
            started_at=self.at,
            failure=self.failure,
        )

    def status_word(self) -> str:
        """The detail shown after the verdict in ``-v`` output.

        The estimate comes first; where the harness reported its own cost it follows in
        brackets, so drift between the two is visible on every cell.
        """
        cost = f"est ${self.estimated_cost_usd or 0.0:.4f}"
        if self.harness_reported_cost_usd is not None:
            cost += f" (harness ${self.harness_reported_cost_usd:.4f})"
        word = (
            f"{cost}  {self.accumulative_billed_tokens:,} accumulative_billed_tokens  "
            f"{self.baseline_tokens:,} baseline_tokens  {self.wall_ms / 1000:.1f}s  "
            f"{self.turns} turns  {self.tool_calls} tools"
        )
        if self.context_window_pct is not None:
            word += f"  ctx {self.context_window_pct:.1f}%"
        if self.skill_files:
            word += (
                f"  skill {self.skill_files_loaded or 0}/{self.skill_files} loaded"
                f" {self.skill_scripts_run or 0}/{self.skill_scripts or 0} run"
            )
        return word

    # -- serialisation -----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """The JSON-ready mapping this record is on the wire and on disk."""
        return asdict(self)

    def write(self, path: Path) -> Path:
        """Write the record as one sorted JSON line; parents are created.

        One line, whether it is a session's own ``history.json`` or a line of the
        aggregated ``history.jsonl``: the same document in the same form (ADR 0032).
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
        return path


def _share(part: float | None, whole: float | None) -> float | None:
    """``part / whole`` rounded, or None when either is missing or the whole is zero."""
    if part is None or not whole:
        return None
    return round(part / whole, 6)


def figures(result: RunResult, *, outcome: Outcome, cache: CacheLayout) -> dict[str, Any]:
    """Every field of the record for one graded run, joined from one builder per concern.

    Raises:
        ValueError: when two builders claim one field, which would let the later silently win.
    """
    out: dict[str, Any] = {}
    for part in (
        _outcome_figures(outcome, cache),
        _identity_figures(result),
        _case_figures(result),
        _run_figures(result),
        _usage_figures(result),
        _run_end_figures(result),
        _skill_use_figures(result),
        _coverage_figures(result),
        _tool_figures(result),
        _subagent_figures(result),
    ):
        clash = out.keys() & part.keys()
        if clash:
            raise ValueError(f"two metrics builders claim {sorted(clash)}")
        out |= part
    return out


def _outcome_figures(outcome: Outcome, cache: CacheLayout) -> dict[str, Any]:
    """What grading observed, and where the combine step runs."""
    return {
        "at": outcome.started_at,
        "node": outcome.node,
        # The word, never the member: this record is shipped by execnet (ADR 0041).
        "verdict": outcome.verdict.value if outcome.verdict else "",
        "failure": outcome.failure,
        "wall_ms": outcome.wall_ms,
        "cache": str(cache.root),
    }


def _identity_figures(result: RunResult) -> dict[str, Any]:
    """Which harness, model, rung and treatment ran, and what the catalogue says the model is."""
    return {
        "harness": result.harness,
        "model": result.model,
        "effort": result.effort or "",
        "treatment": result.treatment or "",
        "line": result.line,
        "family_tier": result.family_tier,
        "released": result.released,
        "session_id": result.session_id,
    }


def _case_figures(result: RunResult) -> dict[str, Any]:
    """The case, its subject and scenario, and the subject's version (ADR 0074)."""
    case = result.case
    return {
        "suite": case.suite if case else None,
        "case": case.name if case else None,
        "skill": case.subject if case else None,
        "fixture": case.fixture if case else None,
        "kind": case.kind.value if case and case.kind else "",
        "scenario": case.scenario if case else None,
        "scenario_fingerprint": case.scenario_fingerprint if case else None,
        "subject_version": case.subject_version if case else None,
    }


def _run_figures(result: RunResult) -> dict[str, Any]:
    """What the run did, cost and needed of the window, and how fast it ran."""
    return {
        "turns": result.turns,
        "reported_turns": result.reported_turns,
        "tool_calls": sum(result.tool_calls.values()),
        "tool_calls_by_name": dict(result.tool_calls),
        "duration_ms": result.duration_ms,
        "api_duration_ms": result.api_duration_ms,
        "estimated_cost_usd": result.estimated_cost_usd,
        "harness_reported_cost_usd": result.harness_reported_cost_usd,
        "rates_applied": asdict(result.rates_applied) if result.rates_applied else {},
        "long_context_calls": result.long_context_calls,
        "files_written": len(result.files_written),
        "context_window": result.context_window,
        "peak_context_tokens": result.peak_context_tokens,
        "final_context_tokens": result.final_context_tokens,
        "context_window_pct": result.context_window_pct,
        "final_context_pct": result.final_context_pct,
        "ttft_ms": result.ttft_ms,
        "output_tokens_per_sec": result.output_tokens_per_sec,
        "output_tokens_per_sec_by_model": result.output_tokens_per_sec_by_model,
        "record_kinds": dict(result.record_kinds),
        "compactions": result.compactions,
        "reasoning_share": result.reasoning_share,
        "cache_read_share": result.cache_read_share,
    }


def _usage_figures(result: RunResult) -> dict[str, Any]:
    """What it spent, tier by tier (ADR 0029)."""
    u = result.usage
    return {
        "accumulative_billed_tokens": u.accumulative_billed_tokens,
        "baseline_tokens": result.baseline_tokens,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "reasoning_tokens": u.reasoning_tokens,
        "cache_read_tokens": u.cache_read_tokens,
        "cache_write_tokens": u.cache_write_tokens,
        "cache_write_1h_tokens": u.cache_write_1h_tokens,
        "cache_write_5m_tokens": u.cache_write_5m_tokens,
    }


def _run_end_figures(result: RunResult) -> dict[str, Any]:
    """How the CLI ended: its exit code, whether it reached the model, and any kill at the wall (ADR 0063, 0064)."""
    return {
        "exit_code": result.exit_code,
        "attempted": int(result.attempted),
        "timed_out_after_s": result.timed_out_after_s,
        "idle_before_timeout_s": result.idle_before_timeout_s,
    }


def _skill_use_figures(result: RunResult) -> dict[str, Any]:
    """Whether and when the skill under test triggered, and what its use cost (ADR 0073)."""
    use = result.skill_use
    return {
        "skill_triggered": _triggered(result),
        "skill_trigger": use.trigger if use else None,
        "skill_triggered_turn": use.triggered_turn if use else None,
        "skill_duration_ms": use.duration_ms if use else None,
        "skill_tool_calls": use.tool_calls if use else None,
        "skill_issuing_cost_usd": use.issuing_cost_usd if use else None,
        "skill_context_cost_usd": use.context_cost_usd if use else None,
        "skill_cost_share": _share(use.issuing_cost_usd, result.estimated_cost_usd) if use else None,
        "skill_context_cost_share": _share(use.context_cost_usd, result.estimated_cost_usd) if use else None,
    }


def _coverage_figures(result: RunResult) -> dict[str, Any]:
    """Which of the skill's files the run reached (ADR 0022)."""
    cov = result.skill_coverage
    summary = cov.summary if cov else None
    return {
        "skill_files": summary.files if summary else None,
        "skill_files_loaded": summary.loaded if summary else None,
        "skill_scripts": summary.scripts if summary else None,
        "skill_scripts_run": summary.run if summary else None,
        "skill_not_loaded": list(cov.not_loaded) if cov else [],
        "skill_not_run": list(cov.not_run) if cov else [],
    }


def _triggered(result: RunResult) -> int | None:
    """1 when the skill under test triggered, 0 on a skill case where it did not, None without a skill."""
    if result.skill_use is not None:
        return 1
    return 0 if result.case is not None and result.case.kind is CaseKind.SKILL else None


def _subagent_figures(result: RunResult) -> dict[str, Any]:
    """Each thread's span, cost and context reduced to the run's: summed, deepest, longest, costliest, fullest.

    Zero subagents is 0 for the counts and spans; the cost is None while the run is unpriced
    or any thread carries no estimate, and the context share None without a window.
    """
    subs = result.subagents
    costs = [s.estimated_cost_usd for s in subs]
    priced = result.cost_status is CostStatus.PRICED and all(c is not None for c in costs)
    peak = max((c.context_tokens for s in subs for c in s.calls), default=0)
    return {
        "subagents": len(subs),
        "subagent_token_share": result.subagent_token_share,
        "subagent_cost_share": result.subagent_cost_share,
        "subagent_ms": sum(s.duration_ms or 0 for s in subs),
        "subagent_max_depth": max((s.depth for s in subs), default=0),
        "subagent_max_ms": max((s.duration_ms or 0 for s in subs), default=0),
        "subagent_max_cost_usd": round(max((c or 0.0 for c in costs), default=0.0), 6) if priced else None,
        "subagent_peak_context_pct": result.pct_of_window(peak),
    }


def _tool_figures(result: RunResult) -> dict[str, Any]:
    """The run's tool calls counted, summed and split by name: calls, milliseconds, issuing and context cost (ADR 0073).

    Every map covers every thread. The cost totals are None only while the run is unpriced
    (and on records from before ADR 0073); a priced run that called no tool is 0.0.
    """
    ms: dict[str, int] = defaultdict(int)
    made: dict[str, int] = defaultdict(int)
    for call in (*result.calls, *(c for s in result.subagents for c in s.calls)):
        for tool in call.tools:
            made[tool.name] += 1
            if tool.duration_ms is not None:
                ms[tool.name] += tool.duration_ms
    issuing: dict[str, float] = defaultdict(float)
    context: dict[str, float] = defaultdict(float)
    for cost in result.tool_costs:
        issuing[cost.name] += cost.issuing_cost_usd
        context[cost.name] += cost.context_cost_usd
    costed = result.cost_status is CostStatus.PRICED
    return {
        "tool_calls_by_name_all": dict(sorted(made.items())),
        "tool_ms_by_name": dict(sorted(ms.items())),
        "tool_issuing_cost_usd_by_name": {k: round(v, 6) for k, v in sorted(issuing.items())},
        "tool_context_cost_usd_by_name": {k: round(v, 6) for k, v in sorted(context.items())},
        "tool_issuing_cost_usd": round(sum(issuing.values()), 6) if costed else None,
        "tool_context_cost_usd": round(sum(context.values()), 6) if costed else None,
        "cache_rereads": sum(c.cache_rereads for c in result.tool_costs) if costed else None,
    }


# What each field admits when a stored mapping is read back, resolved once from the
# declarations themselves so the two cannot drift (ADR 0038).
_ADMITTED: Final[dict[str, tuple[type, ...]]] = {
    name: _admitted(hint) for name, hint in get_type_hints(CellMetrics).items()
}
