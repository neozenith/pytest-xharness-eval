"""The harness x model matrix: the spend dial (ADR 0010, ADR 0015).

A matrix entry is ``harness/model``. Three scopes supply the list, highest
precedence first: a case's ``models=``, the project's ``xharness_matrix`` ini key,
and :data:`DEFAULT_MATRIX` bundled here.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# The harnesses this plugin can drive. ``runner.RUNNERS`` must have exactly these keys.
KNOWN_HARNESSES: tuple[str, ...] = ("claude", "codex")

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
    for entry in models:
        harness, _, model = entry.partition("/")
        if harness not in KNOWN_HARNESSES or not model:
            options = " or ".join(f"'{h}/<model>'" for h in KNOWN_HARNESSES)
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
