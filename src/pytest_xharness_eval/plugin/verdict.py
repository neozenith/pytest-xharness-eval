"""How a cell graded: the words a record's ``verdict`` may carry, and no fifth (ADR 0040).

Its own module because the two ends of a cell's life need it and neither may import the
other: :mod:`~pytest_xharness_eval.plugin.cell` decides a verdict, and
:mod:`~pytest_xharness_eval.plugin.results` turns the one that comes back off a test
report into a status word.
"""

from __future__ import annotations

# Standard Library
from enum import StrEnum


class Verdict(StrEnum):
    """A graded cell's outcome.

    A ``StrEnum``, so comparing a stored record's plain string against a member is the same
    comparison it always was and the vocabulary can be named rather than spelled out at
    each site. The ``.value`` -- never the member -- is what goes onto an
    :class:`~pytest_xharness_eval.emit.metrics.Outcome`: the record it becomes crosses the
    xdist boundary through execnet, which serialises builtins only (ADR 0016).
    """

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    DRY_RUN = "dry-run"
