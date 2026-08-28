"""How a cell graded: the four words a verdict may be, and no fifth (ADR 0041).

Domain vocabulary, so it lives with the nouns. Every layer that names a verdict sits
above this one -- ``plugin/cell.py`` decides one, ``emit/metrics.py`` records it,
``plugin/results.py`` prints it -- and the layer rule of ADR 0039 points the arrows this
way, so the word can be spelled once here and nowhere else.
"""

from __future__ import annotations

# Standard Library
from enum import StrEnum
from typing import Self


class Verdict(StrEnum):
    """A graded cell's outcome.

    A ``StrEnum``, so comparing a stored record's plain string against a member is the
    same comparison it always was. The ``.value`` -- never the member -- is what goes onto
    a :class:`~pytest_xharness_eval.emit.metrics.CellMetrics`: that record crosses the
    xdist boundary through execnet, which serialises builtins only (ADR 0016), and a
    ``StrEnum`` member is not one.
    """

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    DRY_RUN = "dry-run"

    @classmethod
    def stored(cls, word: str) -> Self | None:
        """The member a stored record's word names, or None when it names none of them.

        A record written before this field existed, truncated by hand, or produced by a
        version with a vocabulary this one does not have, says nothing this type can
        represent -- and None says exactly that, rather than inventing a grade the run was
        never given. Every reader of a stored verdict is therefore tolerant by
        construction, which is the same contract :meth:`CellMetrics.from_dict` keeps for
        the rest of the record (ADR 0038).
        """
        try:
            return cls(word)
        except ValueError:
            return None
