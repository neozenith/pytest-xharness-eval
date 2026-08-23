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

# The table shipped with the package. A consumer's own ``prices.toml`` adds to or
# overrides these rows (see ``load_table``); it never has to replace them wholesale.
PRICES_PATH = Path(__file__).parent / "prices.toml"

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
        base = float(r["input"])
        # Cache tiers default to the input rate when a row omits them.
        cache_write = float(r["cache_write"]) if "cache_write" in r else base
        table[model] = Rates(
            input=base,
            output=float(r["output"]),
            cache_read=float(r["cache_read"]) if "cache_read" in r else base,
            cache_write=cache_write,
            cache_write_1h=(
                float(r["cache_write_1h"]) if "cache_write_1h" in r else cache_write * _ONE_HOUR_OVER_FIVE_MINUTE
            ),
            model=model,
            source=str(path),
        )
    return table


def load_table(path: Path = PRICES_PATH, overrides: Path | None = None) -> dict[str, Rates]:
    """The bundled table, with rows from ``overrides`` layered on top when that file exists."""
    table = _parse(path)
    if overrides is not None and overrides.is_file():
        table.update(_parse(overrides))
    return table


def resolve(model: str, table: dict[str, Rates]) -> Rates:
    """Exact key first, then prefix-tolerant match (``claude-opus-5[1m]`` and the like)."""
    if model in table:
        return table[model]
    for key, rates in table.items():
        if model.startswith(key) or key.startswith(model):
            return rates
    raise PricingError(f"no price row for model {model!r}. Refusing to price as zero; add it to prices.toml.")


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
        raise PricingError(f"unpriced models in matrix: {missing}. Add rows to a prices.toml at your pytest rootdir.")


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
