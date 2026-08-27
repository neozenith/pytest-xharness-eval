"""Tokens to USD from a local authoritative table (ADR 0006, ADR 0007, ADR 0019, ADR 0021).

Every priced result records the rates it was priced with and where they came
from (``rates_applied``), so a decision made on a stale or wrong row can be
traced back to that row rather than re-derived.
"""

from __future__ import annotations

# Standard Library
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval import history

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

# The table shipped with the package. A project's ``xharness_prices`` ini lines add to
# or override these rows (see ``load_table``); they never have to replace them wholesale.
PRICES_PATH = Path(__file__).parent / "prices.toml"

# The tiers an ``xharness_prices`` line may state, in USD per million tokens (ADR 0030).
LINE_KEYS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")
# A per-MTok rate below this is almost certainly a per-token value pasted from the
# bundled table; refuse it rather than under-price by a factor of a million.
_MIN_PER_MTOK = 1e-3

# Anthropic bills a 1-hour cache write at 2x input and a 5-minute write at 1.25x;
# a row that states only ``cache_write`` gets its 1h rate by this ratio.
_ONE_HOUR_OVER_FIVE_MINUTE = 2.0 / 1.25


class PricingError(RuntimeError):
    """An unpriced model is a hard error, never a zero (ADR 0007)."""


@dataclass(frozen=True)
class Rates:
    """USD per token for the billed tiers, plus where the row came from.

    ``cache_write`` is the 5-minute (default TTL) rate. ``model`` is the table key
    the row was stored under; ``source`` is the file that supplied it.
    """

    input: float
    output: float
    cache_read: float
    cache_write: float
    cache_write_1h: float
    model: str = ""
    source: str = ""


def _parse(path: Path) -> dict[str, Rates]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table: dict[str, Rates] = {}
    for model, r in raw.items():
        if not isinstance(r, dict):
            continue
        table[model] = _rates_from(model, {k: float(v) for k, v in r.items() if k in LINE_KEYS}, source=str(path))
    return table


def _rates_from(model: str, r: dict[str, float], source: str) -> Rates:
    """One row with the shared defaulting rules: cache tiers fall back to input, 1h to write x 1.6."""
    base = r["input"]
    cache_write = r.get("cache_write", base)
    return Rates(
        input=base,
        output=r["output"],
        cache_read=r.get("cache_read", base),
        cache_write=cache_write,
        cache_write_1h=r.get("cache_write_1h", cache_write * _ONE_HOUR_OVER_FIVE_MINUTE),
        model=model,
        source=source,
    )


def parse_price_lines(lines: list[str]) -> dict[str, Rates]:
    """``xharness_prices`` ini lines to rows: ``<model>: input=<n> output=<n> [cache_read=<n>] ...``.

    Values are **USD per million tokens**, the unit providers publish; they are divided
    by 1e6 here. In the way pytest's own ``markers`` lines pair a name with its text,
    the selector before the colon is the model key (exact or prefix-matched by
    ``resolve``, like any bundled row). ``input`` and ``output`` are required;
    ``cache_read`` and ``cache_write`` default to ``input``; ``cache_write_1h``
    defaults to ``cache_write`` x 1.6 (Anthropic's 2.0/1.25 TTL ratio). A malformed
    line, an unknown tier, or a value that looks per-token is a ``PricingError``,
    never a silent zero (ADR 0007, ADR 0030).
    """
    table: dict[str, Rates] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        model, sep, body = line.partition(":")
        model = model.strip()
        if not sep or not model or not body.strip():
            raise PricingError(f"xharness_prices: expected '<model>: input=<n> output=<n> ...', got {line!r}")
        rates: dict[str, float] = {}
        for part in body.split():
            key, eq, value = part.partition("=")
            if not eq or key not in LINE_KEYS:
                raise PricingError(f"xharness_prices: unknown tier {part!r} in {line!r}; tiers are {LINE_KEYS}")
            try:
                per_mtok = float(value)
            except ValueError as exc:
                raise PricingError(f"xharness_prices: {part!r} in {line!r} is not a number") from exc
            if per_mtok < _MIN_PER_MTOK:
                raise PricingError(
                    f"xharness_prices: {part!r} in {line!r} looks like a per-token rate; "
                    "lines state USD per million tokens (e.g. input=3.00 for $3/MTok)"
                )
            rates[key] = per_mtok / 1e6
        missing = [k for k in ("input", "output") if k not in rates]
        if missing:
            raise PricingError(f"xharness_prices: line {line!r} is missing required tier(s) {missing}")
        table[model] = _rates_from(model, rates, source="xharness_prices")
    return table


def load_table(path: Path = PRICES_PATH, rows: list[str] | None = None) -> dict[str, Rates]:
    """The bundled table, with ``xharness_prices`` ini rows layered on top (ADR 0030)."""
    table = _parse(path)
    table.update(parse_price_lines(list(rows or [])))
    return table


def resolve(model: str, table: dict[str, Rates]) -> Rates:
    """Exact key first, then prefix-tolerant match (``claude-opus-5[1m]`` and the like)."""
    if model in table:
        return table[model]
    for key, rates in table.items():
        if model.startswith(key) or key.startswith(model):
            return rates
    raise PricingError(
        f"no price row for model {model!r}. Refusing to price as zero; add an xharness_prices line (ADR 0030)."
    )


def validate_matrix(models: list[str], table: dict[str, Rates]) -> None:
    """Every ``harness/model`` entry must resolve before a sweep spends anything (ADR 0007)."""
    missing = []
    for entry in models:
        _, _, model = entry.partition("/")
        try:
            resolve(model, table)
        except PricingError:
            missing.append(entry)
    if missing:
        raise PricingError(
            f"unpriced models in matrix: {missing}. Add xharness_prices lines to your pytest config (ADR 0030)."
        )


def breakdown(result: RunResult, rates: Rates) -> dict[str, float]:
    """USD per tier. Cache writes price by TTL where the harness reported one."""
    u = result.usage
    tagged = u.cache_write_1h_tokens + u.cache_write_5m_tokens
    untagged = max(u.cache_write_tokens - tagged, 0)
    return {
        "input": u.input_tokens * rates.input,
        "output": u.output_tokens * rates.output,
        "cache_read": u.cache_read_tokens * rates.cache_read,
        "cache_write_5m": (u.cache_write_5m_tokens + untagged) * rates.cache_write,
        "cache_write_1h": u.cache_write_1h_tokens * rates.cache_write_1h,
    }


def rates_record(rates: Rates) -> dict[str, Any]:
    """The provenance block stored beside every estimate: per-tier USD/token, row key, file, time."""
    rec: dict[str, Any] = asdict(rates)
    rec["applied_at"] = history.now_iso()
    return rec


def price(result: RunResult, table: dict[str, Rates]) -> RunResult:
    """Attach ``estimated_cost_usd``, ``cost_by_tier`` and ``rates_applied`` to a RunResult."""
    rates = resolve(result.model, table)
    tiers = breakdown(result, rates)
    result.cost_by_tier = {k: round(v, 6) for k, v in tiers.items()}
    result.estimated_cost_usd = round(sum(tiers.values()), 6)
    result.rates_applied = rates_record(rates)
    result.cost_status = "priced"
    return result
