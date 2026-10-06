"""The model catalogue: which models each harness supports, and what kind of model each is (ADR 0057).

A model used to be a bare string, named in the default matrix and in the price records and
described nowhere. Every harness class now declares its ``models``: one :class:`ModelSpec`
per supported model, beside the effort ladder it already declares (ADR 0049), because a
provider's differences live on its class and never in a table keyed by its name (ADR 0034).

A spec carries three curated facts:

- ``line`` -- the provider's own product line (``haiku``, ``opus``, ``luna``, ``sol``), the
  word Anthropic's Models API and models.dev both publish.
- ``family_tier`` -- a hand-curated integer for the model's role in its provider's lineup,
  1 the smallest. A number rather than a name, because names are reassigned when a lineup
  changes and a number keeps sliding. It is **frozen at release**: a model keeps the tier
  it shipped with, so history stays comparable when a lineup later gains or loses a line.
- ``released`` -- the release date, the one grouping field every comparator shares. A
  generation or cohort format derived from it is deliberately not decided yet.

A project can add a model, or correct one, before a plugin release with an
``xharness_models`` ini line in the same shape as ``xharness_prices``:

    codex/gpt-6.2-sol: line=sol tier=3 released=2026-10-20

and the project's line wins over the bundled spec of the same model.
"""

from __future__ import annotations

# Standard Library
import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Iterator


class CatalogueError(ValueError):
    """A catalogue line is malformed, or a model is not in the catalogue. Raised before spend."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelSpec:
    """One supported model: its id, its product line, its frozen family tier and its release date."""

    id: str
    line: str
    family_tier: int
    released: date

    def __post_init__(self) -> None:
        if self.family_tier < 1:
            raise CatalogueError(f"model {self.id!r}: family_tier must be 1 or more, got {self.family_tier}")


_LINE = re.compile(r"^(?P<harness>[^/\s]+)/(?P<model>[^:\s]+):\s*(?P<kv>.+)$")
_KEYS = ("line", "tier", "released")


def parse_model_line(text: str) -> tuple[str, ModelSpec]:
    """One ``xharness_models`` line as ``(harness, spec)``; a malformed line raises :exc:`CatalogueError`."""
    m = _LINE.match(text.strip())
    if not m:
        raise CatalogueError(
            f"xharness_models: expected '<harness>/<model>: line=<line> tier=<n> released=YYYY-MM-DD', got {text!r}"
        )
    fields = dict(part.split("=", 1) for part in m["kv"].split() if "=" in part)
    missing = [k for k in _KEYS if k not in fields]
    unknown = sorted(set(fields) - set(_KEYS))
    if missing or unknown:
        raise CatalogueError(f"xharness_models {text!r}: missing {missing}, unknown {unknown}")
    try:
        spec = ModelSpec(
            id=m["model"],
            line=fields["line"],
            family_tier=int(fields["tier"]),
            released=date.fromisoformat(fields["released"]),
        )
    except ValueError as exc:
        raise CatalogueError(f"xharness_models {text!r}: {exc}") from exc
    return m["harness"], spec


@dataclass(frozen=True, slots=True)
class Catalogue:
    """Every supported (harness, model): the registered harnesses' own specs, patched by the project's lines."""

    specs: dict[tuple[str, str], ModelSpec]

    @classmethod
    def of(cls, bundled: Iterable[tuple[str, ModelSpec]], lines: Iterable[str] = ()) -> Catalogue:
        """``bundled`` (harness, spec) pairs, in order, with ``xharness_models`` lines layered on top.

        :func:`~pytest_xharness_eval.derive.catalogue.load_catalogue` is the caller that supplies
        the bundled specs from ``models.toml``; this module names no harness itself, which is
        what lets a harness class import :class:`ModelSpec` without a cycle.
        """
        specs = {(h, s.id): s for h, s in bundled}
        harnesses = {h for h, _ in specs}
        for line in lines:
            harness_name, spec = parse_model_line(line)
            if harness_name not in harnesses:
                raise CatalogueError(f"xharness_models {line!r}: unknown harness {harness_name!r}")
            specs[(harness_name, spec.id)] = spec
        return cls(specs)

    def get(self, harness: str, model: str) -> ModelSpec | None:
        """The spec for ``model`` on ``harness``, or None when the catalogue does not list it."""
        return self.specs.get((harness, model))

    def require(self, harness: str, model: str) -> ModelSpec:
        """The spec, or :exc:`CatalogueError` naming the ini line that would add it."""
        spec = self.get(harness, model)
        if spec is None:
            raise CatalogueError(
                f"{harness}/{model} is not in the model catalogue; add it with an xharness_models line "
                f"'{harness}/{model}: line=<line> tier=<n> released=YYYY-MM-DD' (ADR 0057)"
            )
        return spec

    def __iter__(self) -> Iterator[tuple[str, ModelSpec]]:
        """Every (harness, spec) in declared order; a project-added model follows its harness's bundled ones."""
        order: dict[str, int] = {}
        for h, _ in self.specs:
            order.setdefault(h, len(order))
        return iter(sorted(((h, s) for (h, _), s in self.specs.items()), key=lambda hs: order[hs[0]]))
