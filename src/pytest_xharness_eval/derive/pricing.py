"""Tokens to USD from dated local price records (ADR 0006, ADR 0007, ADR 0019, ADR 0021, ADR 0050, ADR 0051).

Every priced result records the rates it was priced with, where they came from and the
interval they were in effect (``rates_applied``), so a decision made on a stale or wrong
row can be traced back to that row rather than re-derived.

Rates are USD per million tokens everywhere: in the bundled ``prices/prices-YYYYMMDD.toml``
records, in a project's ``xharness_prices`` lines and on the wire. The one division by
1e6 happens per tier inside :func:`tier_costs` (ADR 0050).

A row is keyed by the pair ``(harness, model)`` and chosen by the date a run was stamped
with, so a replay of an old capture prices it at the rates in effect when it ran.

A row may carry a :class:`LongContext` tier: a provider that bills a request whose prompt
exceeds a threshold at higher rates, for the *whole* request (OpenAI: "Prompts with more
than 272K input tokens are priced at 2x input and cache rates and 1.5x output for the full
request"). The threshold is per request, so a run is priced request by request from its
per-call ledgers, never from its summed usage (ADR 0051).

The arithmetic belongs here, and the answer travels as one :class:`CostEstimate` that a
result applies in a single call. No module outside this one writes a cost field (ADR 0035).
"""

from __future__ import annotations

# Standard Library
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self

# Our Libraries
from pytest_xharness_eval.model import registry
from pytest_xharness_eval.model.clock import now_iso
from pytest_xharness_eval.model.runresult import Usage

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Mapping, Sequence

    # Our Libraries
    from pytest_xharness_eval.model.runresult import RunResult

# The dated records shipped with the package, one ``prices-YYYYMMDD.toml`` per interval.
# A project's ``xharness_prices`` ini lines add to or override these rows (see
# ``load_table``); they never have to replace them wholesale.
PRICES_DIR = Path(__file__).parent / "prices"
_RECORD_NAME = re.compile(r"prices-(\d{8})\.toml")

# The billed tiers a row states, in USD per million tokens (ADR 0030, ADR 0050).
LINE_KEYS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")
# The interval keys an ``xharness_prices`` line may add, as ISO dates.
DATE_KEYS = ("from", "to")
# A record row's long-context sub-table, and the threshold key inside it (ADR 0051).
LONG_CONTEXT_TABLE = "long_context"
THRESHOLD_KEY = "above_prompt_tokens"
# The same tier on an ``xharness_prices`` line: ``long_context_above=<n>`` plus ``long_<tier>=<n>``.
LINE_THRESHOLD_KEY = "long_context_above"
LINE_LONG_KEYS = tuple(f"long_{t}" for t in LINE_KEYS)
# The unit every rate is stated in, written beside the rates on the wire so a reader can
# tell them from the per-token rates a result written before ADR 0050 carries.
RATE_UNIT = "usd_per_mtok"
PER_MTOK = 1_000_000
# A per-MTok rate below this is almost certainly a per-token value pasted from an old
# table; refuse it rather than under-price by a factor of a million.
_MIN_PER_MTOK = 1e-3

# Anthropic bills a 1-hour cache write at 2x input and a 5-minute write at 1.25x;
# a row that states only ``cache_write`` gets its 1h rate by this ratio.
_ONE_HOUR_OVER_FIVE_MINUTE = 2.0 / 1.25


class PricingError(RuntimeError):
    """An unpriced model is a hard error, never a zero (ADR 0007)."""


@dataclass(frozen=True, slots=True)
class Interval:
    """When a row was in effect: ``[start, end)``, either end open.

    Half-open so one record's ``effective_to`` is the next one's ``effective_from`` and a
    boundary day belongs to exactly one of them. ``start`` is open only on an undated
    ``xharness_prices`` line; a bundled record always states it.
    """

    start: date | None
    end: date | None

    def __post_init__(self) -> None:
        if self.start and self.end and self.end <= self.start:
            raise PricingError(f"effective_to {self.end} is not after effective_from {self.start}")

    def covers(self, day: date | None) -> bool:
        """Whether ``day`` falls inside; an undated run is covered only by the interval still open."""
        if day is None:
            return self.end is None
        return (self.start is None or self.start <= day) and (self.end is None or day < self.end)

    def overlaps(self, other: Interval) -> bool:
        """Whether any day falls inside both."""
        starts_before_other_ends = other.end is None or self.start is None or self.start < other.end
        ends_after_other_starts = self.end is None or other.start is None or other.start < self.end
        return starts_before_other_ends and ends_after_other_starts


class TierRates(Protocol):
    """Anything that states the five billed tiers in USD per MTok: a row, or its long-context tier."""

    @property
    def input(self) -> float: ...
    @property
    def output(self) -> float: ...
    @property
    def cache_read(self) -> float: ...
    @property
    def cache_write(self) -> float: ...
    @property
    def cache_write_1h(self) -> float: ...


def tier_costs(usage: Usage, rates: TierRates) -> dict[str, float]:
    """USD per tier for ``usage`` at ``rates``. Cache writes price by TTL where the harness reported one."""
    tagged = usage.cache_write_1h_tokens + usage.cache_write_5m_tokens
    untagged = max(usage.cache_write_tokens - tagged, 0)
    return {
        "input": usage.input_tokens * rates.input / PER_MTOK,
        "output": usage.output_tokens * rates.output / PER_MTOK,
        "cache_read": usage.cache_read_tokens * rates.cache_read / PER_MTOK,
        "cache_write_5m": (usage.cache_write_5m_tokens + untagged) * rates.cache_write / PER_MTOK,
        "cache_write_1h": usage.cache_write_1h_tokens * rates.cache_write_1h / PER_MTOK,
    }


def prompt_tokens(usage: Usage) -> int:
    """The prompt one request sent: uncached input plus both cache tiers, as the provider counts it.

    OpenAI's long-context threshold counts cached input (LiteLLM compares its whole
    ``prompt_tokens``), and the adapters split that figure into these three tiers.
    """
    return usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens


def _tier_values(tiers: Mapping[str, float]) -> dict[str, float]:
    """The five tiers from the stated ones: cache tiers fall back to input, 1h to write x 1.6."""
    base = tiers["input"]
    cache_write = tiers.get("cache_write", base)
    return {
        "input": base,
        "output": tiers["output"],
        "cache_read": tiers.get("cache_read", base),
        "cache_write": cache_write,
        "cache_write_1h": tiers.get("cache_write_1h", cache_write * _ONE_HOUR_OVER_FIVE_MINUTE),
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class LongContext:
    """The rates a request is billed at, in full, once its prompt exceeds ``above_prompt_tokens`` (ADR 0051).

    Its field names are the ``rates_applied.long_context`` keys of ``result.json``, so they
    are a wire contract mirrored by ``report-ui/src/lib/types.ts``.
    """

    above_prompt_tokens: int
    input: float
    output: float
    cache_read: float
    cache_write: float
    cache_write_1h: float

    @classmethod
    def of(cls, above: int, tiers: Mapping[str, float]) -> Self:
        if above <= 0:
            raise PricingError(f"a long-context threshold must be a positive token count, got {above}")
        return cls(above_prompt_tokens=above, **_tier_values(tiers))

    def applies(self, usage: Usage) -> bool:
        """Whether this request's prompt is over the threshold (strictly, as providers bill it)."""
        return prompt_tokens(usage) > self.above_prompt_tokens


@dataclass(frozen=True, slots=True)
class AppliedRates:
    """The rates one result was priced with, and when: the audit block beside every estimate.

    This is :class:`Rates` plus its unit and the moment it was applied. Its field names are
    the ``rates_applied`` keys of ``result.json``, mirrored by ``report-ui/src/lib/types.ts``,
    so they are a wire contract (ADR 0021, ADR 0050, ADR 0051).
    """

    input: float
    output: float
    cache_read: float
    cache_write: float
    cache_write_1h: float
    long_context: LongContext | None
    unit: str
    harness: str
    model: str
    source: str
    effective_from: str | None
    effective_to: str | None
    applied_at: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Rates:
    """USD per million tokens for the billed tiers, plus which row this is and when it held.

    ``cache_write`` is the 5-minute (default TTL) rate. ``long_context`` is the tier a
    request over its threshold is billed at, or None where the provider has none (Anthropic
    bills its whole window at one rate). ``harness`` and ``model`` are the pair the row was
    stored under; ``source`` is the record file, or ``xharness_prices``; ``interval`` is when
    it was in effect.
    """

    input: float
    output: float
    cache_read: float
    cache_write: float
    cache_write_1h: float
    long_context: LongContext | None
    harness: str
    model: str
    source: str
    interval: Interval

    @classmethod
    def of(
        cls,
        tiers: Mapping[str, float],
        *,
        harness: str,
        model: str,
        source: str,
        interval: Interval,
        long_context: LongContext | None = None,
    ) -> Self:
        """One row with the shared defaulting rules: cache tiers fall back to input, 1h to write x 1.6."""
        return cls(
            **_tier_values(tiers),
            long_context=long_context,
            harness=harness,
            model=model,
            source=source,
            interval=interval,
        )

    def for_request(self, usage: Usage) -> TierRates:
        """The tier one request is billed at: the long-context tier if its prompt is over the threshold."""
        return self.long_context if self.long_context and self.long_context.applies(usage) else self

    def applied(self, at: str) -> AppliedRates:
        """This row stamped with its unit and the moment it was used to price a run."""
        start, end = self.interval.start, self.interval.end
        return AppliedRates(
            input=self.input,
            output=self.output,
            cache_read=self.cache_read,
            cache_write=self.cache_write,
            cache_write_1h=self.cache_write_1h,
            long_context=self.long_context,
            unit=RATE_UNIT,
            harness=self.harness,
            model=self.model,
            source=self.source,
            effective_from=start.isoformat() if start else None,
            effective_to=end.isoformat() if end else None,
            applied_at=at,
        )


def _residual(total: Usage, parts: Usage) -> Usage:
    """What ``total`` bills that ``parts`` does not account for, tier by tier (never negative)."""
    return Usage(
        input_tokens=max(total.input_tokens - parts.input_tokens, 0),
        output_tokens=max(total.output_tokens - parts.output_tokens, 0),
        cache_read_tokens=max(total.cache_read_tokens - parts.cache_read_tokens, 0),
        cache_write_tokens=max(total.cache_write_tokens - parts.cache_write_tokens, 0),
        reasoning_tokens=max(total.reasoning_tokens - parts.reasoning_tokens, 0),
        cache_write_1h_tokens=max(total.cache_write_1h_tokens - parts.cache_write_1h_tokens, 0),
        cache_write_5m_tokens=max(total.cache_write_5m_tokens - parts.cache_write_5m_tokens, 0),
    )


def calls_of(result: RunResult) -> tuple[list[Usage], Usage]:
    """Each billed call's usage from the per-call ledgers, and whatever the run bills beyond them.

    The long-context threshold is a property of one request, so the ledgers are the unit of
    pricing. The run's ``usage`` is folded from those same ledgers, so the remainder is
    normally zero; it is returned rather than dropped so that nothing billed goes unpriced,
    and it prices at the base tier because no request can be blamed for it (ADR 0051).
    """
    requests = [c.usage for c in result.calls] + [c.usage for s in result.subagents for c in s.calls]
    return requests, _residual(result.usage, Usage.total(requests))


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """What one run costs under one price row: the total, the tier split, and the provenance.

    Built here and applied by :meth:`RunResult.apply_cost` in a single call, so a result's
    cost fields are written together or not at all (ADR 0007, ADR 0035). ``by_tier`` sums
    each tier across both rate regimes; ``long_context_calls`` says how many calls were
    billed at the long-context tier (ADR 0051).
    """

    total_usd: float
    by_tier: dict[str, float]
    long_context_calls: int
    rates: AppliedRates

    @classmethod
    def of(cls, calls: Sequence[Usage], rates: Rates, residual: Usage | None = None) -> Self:
        """Price each call at the tier its own prompt size selects, stamped with the moment of application."""
        totals: dict[str, float] = dict.fromkeys(
            ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h"), 0.0
        )
        long_calls = 0
        for usage in calls:
            tier = rates.for_request(usage)
            long_calls += tier is not rates
            for key, usd in tier_costs(usage, tier).items():
                totals[key] += usd
        if residual is not None:
            for key, usd in tier_costs(residual, rates).items():
                totals[key] += usd
        return cls(
            total_usd=round(sum(totals.values()), 6),
            by_tier={k: round(v, 6) for k, v in totals.items()},
            long_context_calls=long_calls,
            rates=rates.applied(now_iso()),
        )


@dataclass(frozen=True, slots=True)
class PriceTable:
    """Every row a sweep may price from: the project's lines first, then the bundled records.

    Lookup is by ``(harness, model, day)``. The project's rows win over the bundled ones
    wherever their intervals cover the day, which is how ``xharness_prices`` layers on top
    of the package's records without replacing them (ADR 0030, ADR 0050).
    """

    rows: tuple[Rates, ...]

    def get(self, harness: str, model: str, day: date | None = None) -> Rates | None:
        """The row for exactly this pair on ``day``, or None; first match wins."""
        return next(
            (r for r in self.rows if r.harness == harness and r.model == model and r.interval.covers(day)),
            None,
        )

    def resolve(self, harness: str, model: str, day: date | None) -> Rates:
        """Exact key first, then a prefix-tolerant match within the harness (``claude-opus-5[1m]``).

        ``day`` is the date the run was stamped with; None (a capture with no datable
        stamp) is priced from the rows still in effect.
        """
        candidates = [r for r in self.rows if r.harness == harness and r.interval.covers(day)]
        exact = next((r for r in candidates if r.model == model), None)
        if exact is not None:
            return exact
        for rates in candidates:
            if model.startswith(rates.model) or rates.model.startswith(model):
                return rates
        on = f" in effect on {day.isoformat()}" if day else " still in effect"
        raise PricingError(
            f"no price row for {harness}/{model}{on}. Refusing to price as zero; "
            f"add an xharness_prices line '{harness}/{model}: input=<usd/MTok> output=<usd/MTok>' (ADR 0030, ADR 0050)."
        )

    def unpriced(self, entries: Iterable[str], day: date | None) -> list[tuple[str, str]]:
        """The ``(harness, model)`` of every ``harness/model[/effort]`` entry no row prices on ``day``."""
        out = []
        for entry in entries:
            harness, _, rest = entry.partition("/")
            model = rest.partition("/")[0]
            try:
                self.resolve(harness, model, day)
            except PricingError:
                if (harness, model) not in out:
                    out.append((harness, model))
        return out

    def validate_matrix(self, entries: Iterable[str], day: date | None) -> None:
        """Every ``harness/model[/effort]`` entry must resolve before a sweep spends anything (ADR 0007)."""
        entries = list(entries)
        unpriced = set(self.unpriced(entries, day))
        missing = [e for e in entries if tuple(e.split("/")[:2]) in unpriced]
        if missing:
            raise PricingError(
                f"unpriced models in matrix: {missing}. Add xharness_prices lines to your pytest config (ADR 0030)."
            )


def _known_harness(name: str, where: str) -> str:
    if name not in registry.names():
        raise PricingError(f"{where}: unknown harness {name!r}; registered harnesses are {registry.names()}")
    return name


def _per_mtok(value: object, where: str) -> float:
    """One rate, checked: a number, and not a per-token value in disguise."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise PricingError(f"{where}: {value!r} is not a number")
    try:
        rate = float(value)
    except ValueError as exc:
        raise PricingError(f"{where}: {value!r} is not a number") from exc
    if rate < _MIN_PER_MTOK:
        raise PricingError(
            f"{where}: {value!r} looks like a per-token rate; rates are USD per million tokens "
            "(e.g. input=3.00 for $3/MTok)"
        )
    return rate


def _tiers(raw: Mapping[str, Any], where: str) -> dict[str, float]:
    """The stated tiers of one row, each checked; ``input`` and ``output`` are required."""
    unknown = sorted(set(raw) - set(LINE_KEYS))
    if unknown:
        raise PricingError(f"{where}: unknown tier(s) {unknown}; tiers are {LINE_KEYS}")
    missing = [k for k in ("input", "output") if k not in raw]
    if missing:
        raise PricingError(f"{where}: missing required tier(s) {missing}")
    return {k: _per_mtok(v, f"{where} {k}") for k, v in raw.items()}


def _long_context(raw: Mapping[str, Any], where: str) -> LongContext:
    """A row's ``long_context`` sub-table: ``above_prompt_tokens`` plus at least ``input`` and ``output``."""
    tiers = dict(raw)
    above = tiers.pop(THRESHOLD_KEY, None)
    if isinstance(above, bool) or not isinstance(above, int):
        raise PricingError(f"{where}: {THRESHOLD_KEY} must be a whole number of prompt tokens, got {above!r}")
    try:
        return LongContext.of(above, _tiers(tiers, where))
    except PricingError as exc:
        raise PricingError(f"{where}: {exc}") from exc


def _record_row(harness: str, model: str, raw: Any, path: Path, interval: Interval) -> Rates:
    where = f"{path} [{harness}.{model!r}]"
    if not isinstance(raw, dict):
        raise PricingError(f"{where}: must be a table of tiers")
    tiers = dict(raw)
    long_raw = tiers.pop(LONG_CONTEXT_TABLE, None)
    if long_raw is not None and not isinstance(long_raw, dict):
        raise PricingError(f"{where}: {LONG_CONTEXT_TABLE} must be a table")
    long_context = _long_context(long_raw, f"{where}.{LONG_CONTEXT_TABLE}") if long_raw is not None else None
    return Rates.of(
        _tiers(tiers, where),
        harness=harness,
        model=model,
        source=str(path),
        interval=interval,
        long_context=long_context,
    )


def parse_record(path: Path) -> list[Rates]:
    """One ``prices-YYYYMMDD.toml`` record to rows, every one sharing the file's interval.

    The file's name must carry its own ``effective_from``, so a copied record cannot claim
    one interval in its name and another in its body. Each top-level table is a registered
    harness name holding that harness's models (ADR 0050); a model's table may hold a
    ``long_context`` sub-table (ADR 0051).
    """
    named = _RECORD_NAME.fullmatch(path.name)
    if named is None:
        raise PricingError(f"{path}: a price record is named prices-YYYYMMDD.toml")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    start, end = raw.pop("effective_from", None), raw.pop("effective_to", None)
    if not isinstance(start, date) or not isinstance(end, date | None):
        raise PricingError(f"{path}: effective_from (and effective_to, if stated) must be TOML dates")
    if start.strftime("%Y%m%d") != named.group(1):
        raise PricingError(f"{path}: the name says {named.group(1)} but effective_from is {start.isoformat()}")
    interval = Interval(start, end)
    rows = []
    for harness, models in raw.items():
        _known_harness(harness, str(path))
        if not isinstance(models, dict):
            raise PricingError(f"{path}: {harness!r} must be a table of models")
        rows += [_record_row(harness, model, tiers, path, interval) for model, tiers in models.items()]
    return rows


def load_records(directory: Path = PRICES_DIR) -> list[Rates]:
    """Every bundled record's rows; two records whose intervals overlap is an error.

    Gaps are allowed, and a run dated inside one stops at resolution rather than borrowing
    a neighbour's rates. At most one record is still open, so "the current rates" is one
    file, and the rows are returned newest record first.
    """
    records = []
    for path in sorted(directory.glob("prices-*.toml")):
        rows = parse_record(path)
        if rows:
            records.append((path, rows[0].interval, rows))
    records.sort(key=lambda rec: rec[1].start or date.min, reverse=True)
    for (newer, a, _), (older, b, _) in zip(records, records[1:], strict=False):
        if a.overlaps(b):
            raise PricingError(f"price records overlap: {older.name} and {newer.name}; set effective_to on the older")
    return [row for _, _, rows in records for row in rows]


def _selector(text: str, line: str) -> tuple[str, str]:
    harness, slash, model = text.strip().partition("/")
    if not slash or not harness or not model:
        raise PricingError(
            f"xharness_prices: the selector in {line!r} is '<harness>/<model>' (e.g. 'claude/claude-sonnet-5')"
        )
    return _known_harness(harness, f"xharness_prices line {line!r}"), model


def _day(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PricingError(f"{where}: {value!r} is not an ISO date (YYYY-MM-DD)") from exc


def _parse_line(line: str) -> Rates:
    head, sep, body = line.partition(":")
    if not sep or not body.strip():
        raise PricingError(f"xharness_prices: expected '<harness>/<model>: input=<n> output=<n> ...', got {line!r}")
    harness, model = _selector(head, line)
    tiers: dict[str, str] = {}
    long_tiers: dict[str, str] = {}
    days: dict[str, date] = {}
    threshold: str | None = None
    keys = LINE_KEYS + LINE_LONG_KEYS + (LINE_THRESHOLD_KEY,) + DATE_KEYS
    for part in body.split():
        key, eq, value = part.partition("=")
        if not eq or key not in keys:
            raise PricingError(f"xharness_prices: unknown key {part!r} in {line!r}; keys are {keys}")
        if key in DATE_KEYS:
            days[key] = _day(value, f"xharness_prices: {part!r} in {line!r}")
        elif key == LINE_THRESHOLD_KEY:
            threshold = value
        elif key in LINE_LONG_KEYS:
            long_tiers[key.removeprefix("long_")] = value
        else:
            tiers[key] = value
    return Rates.of(
        _tiers(tiers, f"xharness_prices: line {line!r}"),
        harness=harness,
        model=model,
        source="xharness_prices",
        interval=Interval(days.get("from"), days.get("to")),
        long_context=_line_long_context(threshold, long_tiers, line),
    )


def _line_long_context(threshold: str | None, tiers: Mapping[str, str], line: str) -> LongContext | None:
    """A line's long-context tier: none, or ``long_context_above`` with ``long_input`` and ``long_output``."""
    if threshold is None and not tiers:
        return None
    where = f"xharness_prices: line {line!r}"
    if threshold is None:
        raise PricingError(f"{where}: long_* rates need {LINE_THRESHOLD_KEY}=<prompt tokens>")
    if not threshold.isdigit():
        raise PricingError(f"{where}: {LINE_THRESHOLD_KEY}={threshold!r} is not a whole number of prompt tokens")
    missing = [f"long_{k}" for k in ("input", "output") if k not in tiers]
    if missing:
        raise PricingError(f"{where}: {LINE_THRESHOLD_KEY} needs {missing}")
    try:
        return LongContext.of(int(threshold), _tiers(tiers, where))
    except PricingError as exc:
        raise PricingError(f"{where}: {exc}") from exc


def parse_price_lines(lines: Iterable[str]) -> list[Rates]:
    """``xharness_prices`` ini lines to rows: ``<harness>/<model>: input=<n> output=<n> [...] [from=] [to=]``.

    Values are **USD per million tokens**, the unit providers publish. In the way pytest's
    own ``markers`` lines pair a name with its text, the selector before the colon is the
    ``harness/model`` pair a matrix entry names (the model exact or prefix-matched by
    ``resolve``, like any bundled row). ``input`` and ``output`` are required;
    ``cache_read`` and ``cache_write`` default to ``input``; ``cache_write_1h`` defaults
    to ``cache_write`` x 1.6 (Anthropic's 2.0/1.25 TTL ratio). ``from`` and ``to`` are ISO
    dates bounding when the line applies, ``[from, to)``; a line with neither applies on
    every date. ``long_context_above=<prompt tokens>`` with ``long_input`` and
    ``long_output`` (and optionally the other ``long_<tier>`` keys, defaulted the same way)
    states the tier a call over that prompt size is billed at in full (ADR 0051). Two lines
    for one pair whose intervals overlap, a malformed line, an unknown key, or a value that
    looks per-token is a ``PricingError``, never a silent zero (ADR 0007, ADR 0030, ADR 0050).
    """
    rows: list[Rates] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        row = _parse_line(line)
        clash = next(
            (r for r in rows if (r.harness, r.model) == (row.harness, row.model) and r.interval.overlaps(row.interval)),
            None,
        )
        if clash is not None:
            raise PricingError(
                f"xharness_prices: two lines for {row.harness}/{row.model} overlap in time; bound them with from=/to="
            )
        rows.append(row)
    return rows


def load_table(directory: Path = PRICES_DIR, rows: Iterable[str] = (), cached: Path | None = None) -> PriceTable:
    """The bundled records, with ``xharness_prices`` ini rows layered on top (ADR 0030, ADR 0050).

    ``cached`` is a project's ``<cache>/pricing/`` directory of live-priced records. They come
    after the bundled ones, so a live row only ever fills a gap the bundled records leave
    (ADR 0060).
    """
    live = tuple(load_records(cached)) if cached is not None and cached.is_dir() else ()
    return PriceTable(tuple(parse_price_lines(rows)) + tuple(load_records(directory)) + live)


def price(result: RunResult, table: PriceTable, day: date | None) -> RunResult:
    """Price ``result`` from the rows in effect on ``day`` and record the estimate; the run is returned.

    Each call is priced at the tier its own prompt size selects (ADR 0051). Resolving the row
    is the only step that can fail, and it raises rather than pricing an unknown model as
    zero (ADR 0007).
    """
    rates = table.resolve(result.harness, result.model, day)
    calls, residual = calls_of(result)
    result.apply_cost(CostEstimate.of(calls, rates, residual))
    return result
