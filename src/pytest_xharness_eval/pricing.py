"""Tokens to USD from a local authoritative table (ADR 0006, ADR 0007)."""

from __future__ import annotations

# Standard Library
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Our Libraries
    from pytest_xharness_eval.runresult import RunResult

# The table shipped with the package. A consumer's own ``prices.toml`` adds to or
# overrides these rows (see ``load_table``); it never has to replace them wholesale.
PRICES_PATH = Path(__file__).parent / "prices.toml"


class PricingError(RuntimeError):
    """An unpriced model is a hard error, never a zero (ADR 0007)."""


@dataclass(frozen=True)
class Rates:
    """USD per token for the four billed tiers."""

    input: float
    output: float
    cache_read: float
    cache_write: float


def _parse(path: Path) -> dict[str, Rates]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table: dict[str, Rates] = {}
    for model, r in raw.items():
        if not isinstance(r, dict):
            continue
        base = float(r["input"])
        table[model] = Rates(
            input=base,
            output=float(r["output"]),
            # Cache tiers default to the input rate when a row omits them.
            cache_read=float(r["cache_read"]) if "cache_read" in r else base,
            cache_write=float(r["cache_write"]) if "cache_write" in r else base,
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
    raise PricingError(
        f"no price for model {model!r}; add a row to a prices.toml at your pytest rootdir "
        f"(or to {PRICES_PATH}). Refusing to price as zero."
    )


def validate_matrix(models: list[str], table: dict[str, Rates]) -> None:
    """Abort before any cell runs if a model in the sweep has no price (ADR 0007)."""
    missing = []
    for m in models:
        try:
            resolve(m.split("/", 1)[-1], table)
        except PricingError:
            missing.append(m)
    if missing:
        raise PricingError(f"unpriced models in matrix: {missing}. Add rows to a prices.toml at your pytest rootdir.")


def price(result: RunResult, table: dict[str, Rates]) -> RunResult:
    """Attach ``cost_usd`` to a RunResult from its token counts, tier by tier."""
    rates = resolve(result.model, table)
    u = result.usage
    result.cost_usd = round(
        u.input_tokens * rates.input
        + u.output_tokens * rates.output
        + u.cache_read_tokens * rates.cache_read
        + u.cache_write_tokens * rates.cache_write,
        6,
    )
    result.cost_status = "priced"
    return result
