"""``report/report.json``: what one pytest session graded, and what it spent (ADR 0037, ADR 0040).

Two keys, and always the two: ``cells`` -- every graded cell's
:class:`~pytest_xharness_eval.emit.metrics.CellMetrics` record, in the order their reports
arrived -- and ``total_usd``, the estimate they add up to. That is a serialised contract
like the other two documents in this layer, and it was the last one still authored as a
dict literal inside a pytest hook, where no type named it and no reader could be pointed
at its definition (ADR 0040).

The summary is also what tells the session *whether there is anything to combine*:
:meth:`RunSummary.cache_roots` is the set of cache roots its cells actually wrote evidence
into, which is empty for a dry run and is therefore the one place the combine step's
trigger is decided (ADR 0018, ADR 0032).
"""

from __future__ import annotations

# Standard Library
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.emit.metrics import CellMetrics


@dataclass(frozen=True, slots=True)
class RunSummary:
    """The cells one pytest session graded, and the spend they add up to.

    Immutable and total: a summary is built from the records that exist when the session
    ends, and every value it publishes is a view over them, so ``total_usd`` cannot
    disagree with ``cells``.
    """

    cells: tuple[CellMetrics, ...]

    @classmethod
    def of(cls, cells: Iterable[CellMetrics]) -> Self:
        """The summary of these cells, in the order they are given."""
        return cls(tuple(cells))

    # -- derived views -----------------------------------------------------------------

    @property
    def total_usd(self) -> float:
        """The price-table estimate summed over every cell; an unpriced cell adds nothing."""
        return sum(cell.estimated_cost_usd or 0.0 for cell in self.cells)

    def cache_roots(self) -> list[str]:
        """The distinct cache roots these cells wrote evidence into, in path order.

        A dry run invokes nothing and so names none: its records carry an empty ``cache``
        field, which is what keeps a free run free of a combine step (ADR 0018, ADR 0032).
        """
        return sorted({cell.cache for cell in self.cells if cell.cache})

    # -- serialisation -----------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """The JSON-ready mapping ``report.json`` is; the two keys are a frozen format."""
        return {"cells": [cell.to_dict() for cell in self.cells], "total_usd": round(self.total_usd, 6)}

    def write(self, path: Path) -> Path:
        """Write the summary as indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
