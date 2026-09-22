"""The harness x model x effort matrix: the spend dial (ADR 0010, ADR 0015, ADR 0049).

A matrix entry is ``harness/model`` or ``harness/model/effort``. Three scopes supply the
list, highest precedence first: a case's ``models=``, the project's ``xharness_matrix``
ini key, and :data:`DEFAULT_MATRIX` bundled here.

The third component is optional and its absence is meaningful: an entry that names no
effort leaves the CLI on whatever default its own configuration gives it, which is the
behaviour every matrix had before ADR 0049 and the reason an existing matrix line keeps
sweeping exactly the cell it always did.

An effort that *is* named is resolved here, once, against that harness's own ladder --
so ``min``/``mid``/``max`` become native rungs at expansion and every later reader (the
node id, the evidence directory, the report row) carries the rung that was actually sent.
An unknown or unavailable rung stops the sweep at collection, before spend, for the same
reason an unpriced model does (ADR 0007): both CLIs accept a bad effort word, warn at
most, and bill a full run of the wrong experiment.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# Our Libraries
from pytest_xharness_eval.model import registry
from pytest_xharness_eval.model.effort import UnknownEffort


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
    """One (harness, model, effort) point of a case: the unit pytest collects, runs, reports.

    ``effort`` is None when the entry named none, and otherwise a *native* rung of this
    harness's ladder: :func:`expand` resolves any portable alias before the cell exists,
    so nothing downstream ever holds a word the CLI would not understand.
    """

    harness: str
    model: str
    effort: str | None = None

    @property
    def id(self) -> str:
        """The ``harness/model[/effort]`` form used in node ids and on the command line.

        The effort component is omitted when there is none, so a matrix that names no
        effort produces exactly the node ids it produced before ADR 0049 and a project's
        stored history keys still line up.
        """
        return f"{self.harness}/{self.model}/{self.effort}" if self.effort else f"{self.harness}/{self.model}"


def expand(models: list[str]) -> list[Cell]:
    """Parse ``harness/model[/effort]`` entries into cells, resolving each effort as it goes.

    An unknown harness, an empty model, a fourth component, an unknown effort word or a
    rung this harness does not have are all errors here -- at collection, where the sweep
    has spent nothing yet (ADR 0007, ADR 0049).
    """
    cells = []
    known = known_harnesses()
    for entry in models:
        harness, _, rest = entry.partition("/")
        model, _, effort = rest.partition("/")
        if harness not in known or not model or "/" in effort:
            options = " or ".join(f"'{h}/<model>[/<effort>]'" for h in known)
            raise ValueError(f"matrix entry must be {options}: {entry!r}")
        cells.append(Cell(harness=harness, model=model, effort=_rung(harness, effort, entry)))
    return cells


def _rung(harness: str, effort: str, entry: str) -> str | None:
    """The native rung this entry asks ``harness`` for, or None when it asks for no effort.

    The harness's own :exc:`UnknownEffort` message already names the ladder and the
    aliases; it is re-raised with the offending matrix line in front of it, because the
    line is what the reader has to go and edit.
    """
    if not effort:
        return None
    try:
        return registry.resolve_effort(harness, effort)
    except UnknownEffort as exc:
        raise ValueError(f"matrix entry {entry!r}: {exc}") from exc


def narrow(
    cells: list[Cell],
    models: list[str] | None,
    harnesses: list[str] | None,
    efforts: list[str] | None = None,
) -> list[Cell]:
    """Apply the ``--harness``, ``--model`` and ``--effort`` filters, in that order.

    ``--harness`` is exact and ``--model`` is a substring of the model, or a full cell id.
    ``--effort`` is matched against the cell's *resolved* rung, and the filter word is
    resolved the same way the matrix entry was -- so ``--effort mid`` selects whatever
    ``mid`` meant on each harness, which is the only reading under which one flag narrows
    both arms of a two-harness sweep to the same intensity.

    A cell that named no rung matches only the empty filter: there is no rung to compare a
    CLI's own default against, so it stays selectable explicitly and is never swept up by
    a rung filter.
    """
    out = cells
    if harnesses:
        out = [c for c in out if c.harness in harnesses]
    if models:
        out = [c for c in out if any(m in c.model or m == c.id for m in models)]
    if efforts:
        out = [c for c in out if _matches_effort(c, efforts)]
    return out


def _matches_effort(cell: Cell, efforts: list[str]) -> bool:
    """Whether any filter word names ``cell``'s rung on ``cell``'s own harness.

    A word that does not resolve for this harness simply does not match it -- ``--effort
    minimal`` is a meaningful filter for codex cells and names nothing on claude's ladder,
    and narrowing a sweep is not the place to refuse the flag over it. A matrix *entry* is
    a different matter and does raise: that one is about to be billed.
    """
    for word in efforts:
        if (cell.effort or "") == word:
            return True
        try:
            if cell.effort and registry.resolve_effort(cell.harness, word) == cell.effort:
                return True
        except UnknownEffort:
            continue
    return False
