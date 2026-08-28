"""``history.json``: one cell's metrics record, as a type (ADR 0018, ADR 0021, ADR 0037).

Every graded cell -- live or replayed -- emits exactly one :class:`CellMetrics`. It is
written beside the cell's evidence, shown in the verbose status word, carried to the xdist
controller, flattened into ``--junitxml``, and combined into ``report/history.jsonl``. Its
field names *are* that wire format, which ``report-ui/src/lib/types.ts`` mirrors, so a
rename here is a wire-format change and ``tests/test_units.py`` pins the key set.

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
from dataclasses import asdict, dataclass, field
from types import UnionType
from typing import TYPE_CHECKING, Any, Final, Self, Union, get_args, get_origin, get_type_hints

# Our Libraries
from pytest_xharness_eval.normalise import read_json_object

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Mapping
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.layout import CacheLayout
    from pytest_xharness_eval.matrix import Cell
    from pytest_xharness_eval.runresult import RunResult


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
    """

    node: str
    verdict: str
    wall_ms: int
    started_at: str


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
    session_id: str = ""
    verdict: str = ""
    # What it did.
    turns: int = 0
    reported_turns: int | None = None
    tool_calls: int = 0
    tool_calls_by_name: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    wall_ms: int = 0
    # What it cost, and the rates that say so (ADR 0021).
    estimated_cost_usd: float | None = None
    harness_reported_cost_usd: float | None = None
    rates_applied: dict[str, Any] = field(default_factory=dict)
    # What it spent, tier by tier (ADR 0029).
    accumulative_billed_tokens: int = 0
    baseline_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_write_1h_tokens: int = 0
    files_written: int = 0
    # How close it came to the window, and how fast it ran (ADR 0024).
    context_window: int | None = None
    peak_context_tokens: int = 0
    context_window_pct: float | None = None
    final_context_pct: float | None = None
    ttft_ms: int | None = None
    output_tokens_per_sec: float | None = None
    record_kinds: dict[str, int] = field(default_factory=dict)
    # Which of the skill's files it reached (ADR 0022).
    skill_files: int | None = None
    skill_files_loaded: int | None = None
    skill_scripts: int | None = None
    skill_scripts_run: int | None = None
    skill_not_loaded: list[str] = field(default_factory=list)
    skill_not_run: list[str] = field(default_factory=list)
    # Which cache root to run the combine step against; a declared field rather than a key
    # written onto the record afterwards (ADR 0032, ADR 0037). Empty means "combine
    # nothing", which is how a dry run stays free of evidence.
    cache: str = ""

    # -- constructors ------------------------------------------------------------------

    @classmethod
    def of(cls, result: RunResult, *, outcome: Outcome, cache: CacheLayout) -> Self:
        """The record for one graded run: everything derived, nothing assigned afterwards."""
        u = result.usage
        case = result.case
        cov = result.skill_coverage
        summary = cov.summary if cov else None
        return cls(
            at=outcome.started_at,
            node=outcome.node,
            suite=case.suite if case else None,
            case=case.name if case else None,
            skill=case.skill if case else None,
            fixture=case.fixture if case else None,
            harness=result.harness,
            model=result.model,
            session_id=result.session_id,
            verdict=outcome.verdict,
            turns=result.turns,
            reported_turns=result.reported_turns,
            tool_calls=sum(result.tool_calls.values()),
            tool_calls_by_name=dict(result.tool_calls),
            duration_ms=result.duration_ms,
            wall_ms=outcome.wall_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            harness_reported_cost_usd=result.harness_reported_cost_usd,
            rates_applied=asdict(result.rates_applied) if result.rates_applied else {},
            accumulative_billed_tokens=u.accumulative_billed_tokens,
            baseline_tokens=result.baseline_tokens,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            reasoning_tokens=u.reasoning_tokens,
            cache_read_tokens=u.cache_read_tokens,
            cache_write_tokens=u.cache_write_tokens,
            cache_write_1h_tokens=u.cache_write_1h_tokens,
            files_written=len(result.files_written),
            context_window=result.context_window,
            peak_context_tokens=result.peak_context_tokens,
            context_window_pct=result.context_window_pct,
            final_context_pct=result.final_context_pct,
            ttft_ms=result.ttft_ms,
            output_tokens_per_sec=result.output_tokens_per_sec,
            record_kinds=dict(result.record_kinds),
            skill_files=summary.files if summary else None,
            skill_files_loaded=summary.loaded if summary else None,
            skill_scripts=summary.scripts if summary else None,
            skill_scripts_run=summary.run if summary else None,
            skill_not_loaded=list(cov.not_loaded) if cov else [],
            skill_not_run=list(cov.not_run) if cov else [],
            cache=str(cache.root),
        )

    @classmethod
    def dry_run(cls, *, node: str, cell: Cell) -> Self:
        """The record a ``--dry-run`` cell emits: the same document, with nothing measured.

        A dry run used to put a five-key mapping of its own shape on the report, so the
        one thing every reader of ``report.json`` could rely on -- that a cell record is a
        cell record -- did not hold (ADR 0037). ``cache`` stays empty: a dry run invokes
        nothing, so it must leave no evidence and trigger no combine step (ADR 0018).
        """
        return cls(node=node, harness=cell.harness, model=cell.model, verdict="dry-run")

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
        """The four values a replay must keep, since it cannot re-derive them."""
        return Outcome(node=self.node, verdict=self.verdict, wall_ms=self.wall_ms, started_at=self.at)

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


# What each field admits when a stored mapping is read back, resolved once from the
# declarations themselves so the two cannot drift (ADR 0038).
_ADMITTED: Final[dict[str, tuple[type, ...]]] = {
    name: _admitted(hint) for name, hint in get_type_hints(CellMetrics).items()
}
