"""The harness x model matrix: the spend dial (ADR 0010, ADR 0015).

A matrix entry is ``harness/model``. Three scopes supply the list, highest
precedence first: a case's ``models=``, the project's ``xharness_matrix`` ini key,
and :data:`DEFAULT_MATRIX` bundled here.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# Our Libraries
from pytest_xharness_eval.model import registry


def known_harnesses() -> tuple[str, ...]:
    """The harnesses this plugin can drive: whatever is registered, never a second list.

    Read through the registry rather than copied beside it, so registering a harness is
    the only edit a new CLI needs (ADR 0034); :mod:`~pytest_xharness_eval.model.registry`
    is the one module below the adapter layer that names it (ADR 0039).
    """
    return registry.names()


# The plugin-scope fallback sweep, used when neither the project nor the case sets one.
DEFAULT_MATRIX: list[str] = [
    "claude/claude-opus-5",
    "codex/gpt-5.6-sol",
]


@dataclass(frozen=True)
class Cell:
    """One (harness, model) pair of a case: the unit pytest collects, runs, and reports."""

    harness: str
    model: str

    @property
    def id(self) -> str:
        """The ``harness/model`` form used in node ids and on the command line."""
        return f"{self.harness}/{self.model}"


def expand(models: list[str]) -> list[Cell]:
    """Parse ``harness/model`` entries into cells; an unknown harness or empty model is an error."""
    cells = []
    known = known_harnesses()
    for entry in models:
        harness, _, model = entry.partition("/")
        if harness not in known or not model:
            options = " or ".join(f"'{h}/<model>'" for h in known)
            raise ValueError(f"matrix entry must be {options}: {entry!r}")
        cells.append(Cell(harness=harness, model=model))
    return cells


def narrow(cells: list[Cell], models: list[str] | None, harnesses: list[str] | None) -> list[Cell]:
    """Apply ``--harness`` (exact) and ``--model`` (substring, or a full cell id) filters."""
    out = cells
    if harnesses:
        out = [c for c in out if c.harness in harnesses]
    if models:
        out = [c for c in out if any(m in c.model or m == c.id for m in models)]
    return out
