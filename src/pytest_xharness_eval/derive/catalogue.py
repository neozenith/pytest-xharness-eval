"""The bundled model catalogue: ``derive/prices/models.toml``, read into the domain's nouns (ADR 0059).

The catalogue is configuration, so it lives in one file beside the price records rather
than spread across the harness classes. One table per registered harness names the
``litellm_provider`` its first-party rows carry in LiteLLM's feed, and lists its models
with their line, hand-curated family tier and release date (ADR 0057).

Like the price records, it is located from this package's own directory, the one
``__file__``-relative location the plugin allows (ADR 0014, ADR 0050).
"""

from __future__ import annotations

# Standard Library
import tomllib
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.derive.pricing import PRICES_DIR
from pytest_xharness_eval.model import registry
from pytest_xharness_eval.model.catalogue import Catalogue, CatalogueError, ModelSpec

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable
    from pathlib import Path

#: The one catalogue file, beside the dated price records.
MODELS_FILE = PRICES_DIR / "models.toml"

_MODEL_KEYS = frozenset({"line", "tier", "released"})
_HARNESS_KEYS = frozenset({"feed_provider", "one_hour_cache_write_is_five_minute", "models"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Feed:
    """How one harness's models appear in LiteLLM's price feed (ADR 0060)."""

    harness: str
    #: The ``litellm_provider`` value on this harness's first-party rows.
    provider: str
    #: The provider publishes no 1-hour cache-write tier, so the 5-minute rate stands in.
    one_hour_is_five_minute: bool


def _read(path: Path) -> dict[str, dict[str, Any]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    for harness, table in raw.items():
        if harness not in registry.names():
            raise CatalogueError(f"{path}: unknown harness {harness!r}; registered harnesses are {registry.names()}")
        if not isinstance(table, dict) or set(table) - _HARNESS_KEYS:
            raise CatalogueError(f"{path} [{harness}]: expected only {sorted(_HARNESS_KEYS)}")
    return raw


def _spec(path: Path, harness: str, model: str, raw: Any) -> ModelSpec:
    where = f"{path} [{harness}.models.{model!r}]"
    if not isinstance(raw, dict) or set(raw) != _MODEL_KEYS:
        raise CatalogueError(f"{where}: expected exactly {sorted(_MODEL_KEYS)}")
    if not isinstance(raw["tier"], int) or not isinstance(raw["released"], date):
        raise CatalogueError(f"{where}: tier must be an integer and released a TOML date")
    return ModelSpec(id=model, line=str(raw["line"]), family_tier=raw["tier"], released=raw["released"])


def load_catalogue(lines: Iterable[str] = (), path: Path | None = None) -> Catalogue:
    """The bundled catalogue, in file order, with a project's ``xharness_models`` lines layered on top."""
    path = path or MODELS_FILE
    bundled = [
        (harness, _spec(path, harness, model, spec))
        for harness, table in _read(path).items()
        for model, spec in table.get("models", {}).items()
    ]
    return Catalogue.of(bundled, lines)


def feeds(path: Path | None = None) -> tuple[Feed, ...]:
    """Each catalogued harness's place in LiteLLM's feed, in file order."""
    path = path or MODELS_FILE
    return tuple(
        Feed(
            harness=harness,
            provider=str(table["feed_provider"]),
            one_hour_is_five_minute=bool(table.get("one_hour_cache_write_is_five_minute", False)),
        )
        for harness, table in _read(path).items()
    )
