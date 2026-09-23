"""How hard an agent is told to think: the third matrix axis, and its portable aliases.

*Effort* is the reasoning budget a CLI is asked to spend on a cell. Both shipped
harnesses expose it -- ``claude --effort <level>`` and ``codex -c
model_reasoning_effort=<level>`` -- but they do not agree on the rungs, and neither of
them *fails* on a word it does not know: claude prints a warning and silently runs at its
default, codex accepts the override and ignores it. A misspelled level therefore buys a
full-priced run of the wrong experiment, which is the same failure ADR 0007 refuses for
an unpriced model. So the vocabulary is closed here and checked at collection, before
spend.

Two kinds of word are accepted, and both are members of one :class:`Effort`:

*Native rungs* (``low`` ... ``max``) name a level of one CLI's own ladder. They are
exact: a rung a harness does not have is an error, never the nearest thing to it. Both
shipped harnesses happen to declare the same five, but that is a fact about them rather
than a rule -- the ladder lives on the harness class, and a third CLI may declare any.

*Portable aliases* (:data:`PORTABLE` -- ``min``, ``mid``, ``max``) name a *position* on
whichever ladder the harness has, so one matrix line can sweep both arms at comparable
intensity without the author knowing either vocabulary. They resolve against the
harness's own ladder (:func:`resolve`), and the resolution happens once, at matrix
expansion, so a cell, its evidence directory and its report row all carry the rung that
was actually sent rather than the word that was typed.

``max`` is deliberately both: it is claude's top native rung *and* the portable alias for
a top rung, and on claude the two resolve to the same word. That collision is the reason
this module resolves rather than merely validates.
"""

from __future__ import annotations

# Standard Library
from enum import StrEnum


class Effort(StrEnum):
    """Every word a matrix entry's third component may be: the closed vocabulary (ADR 0041).

    The ``.value`` is what reaches a record, a directory name and a CLI flag; the member
    is what this package spells it with.
    """

    # Portable aliases: a position on the harness's own ladder, not a level.
    MIN = "min"
    MID = "mid"
    MAX = "max"
    # Native rungs, lowest first. ``max`` above is a native top rung as well as an alias.
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


#: The words that name a position on a ladder rather than a level of one. ``mid`` is the
#: middle rung by index, so it follows a harness that gains or loses a rung instead of
#: being pinned to a word that harness may not have.
PORTABLE: tuple[str, ...] = (Effort.MIN.value, Effort.MID.value, Effort.MAX.value)


class UnknownEffort(ValueError):
    """An effort word this plugin's vocabulary does not hold, or this harness's ladder lacks.

    A ``ValueError`` rather than a warning, and raised at matrix expansion rather than at
    spawn time, because every CLI that would receive the word accepts it and runs anyway.
    """


def resolve(effort: str, ladder: tuple[str, ...], *, harness: str) -> str:
    """The native rung ``effort`` names on ``ladder``: an alias's position, or an exact rung.

    Args:
        effort: a word from :class:`Effort` -- a portable alias or a native rung.
        ladder: this harness's own rungs, lowest first.
        harness: the harness name, for the error message only.

    Returns:
        The rung to hand the CLI. Always a member of ``ladder``.

    Raises:
        UnknownEffort: if ``effort`` is not in the vocabulary at all, if this harness
            declares no ladder, or if it is a native rung this harness does not have.
            ``max`` is tried as an alias first, so claude's top rung and the portable
            alias agree rather than one shadowing the other.
    """
    if effort not in set(Effort):
        raise UnknownEffort(
            f"unknown effort {effort!r}; the vocabulary is "
            f"{', '.join(e.value for e in Effort)} (aliases {', '.join(PORTABLE)} resolve per harness)"
        )
    if not ladder:
        raise UnknownEffort(f"harness {harness!r} declares no effort ladder, so {effort!r} cannot be resolved")
    if effort in PORTABLE:
        return _at_position(effort, ladder)
    if effort not in ladder:
        raise UnknownEffort(
            f"harness {harness!r} has no effort rung {effort!r}; its ladder is "
            f"{', '.join(ladder)} (or use {', '.join(PORTABLE)})"
        )
    return effort


def _at_position(alias: str, ladder: tuple[str, ...]) -> str:
    """The rung a portable alias names on this ladder."""
    if alias == Effort.MIN.value:
        return ladder[0]
    if alias == Effort.MAX.value:
        return ladder[-1]
    return ladder[len(ladder) // 2]
