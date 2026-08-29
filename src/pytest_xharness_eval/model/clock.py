"""The two wall-clock readings this package takes, and the only place it names a clock.

Every ``at``, ``applied_at`` and ``generated_at`` field is :func:`now_iso`, and every
"how long did that take" is :func:`ms_between`. They sit at the bottom of the stack --
depending on nothing, not even on what a run is -- because the layers that need a clock
have nothing else in common: pricing stamps the row it applied, the report stamps the
index it wrote, and a harness adapter measures the gap between two records of a session
log. Each of them used to reach into the folding toolkit for a timestamp, which made the
adapter layer a dependency of the derivation and emission layers for one function (ADR
0037).

Both readings are UTC and both are tolerant of the harnesses' spelling: an ISO-8601
string ending in ``Z`` parses the same as one ending in ``+00:00``.
"""

from __future__ import annotations

# Standard Library
from datetime import UTC, datetime


def now_iso() -> str:
    """UTC timestamp, second precision: the form every ``at`` and ``applied_at`` field takes."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ms_between(earlier: str | None, later: str | None) -> int | None:
    """Milliseconds between two ISO-8601 timestamps (``Z`` accepted); None if either is missing or unparseable."""
    if not earlier or not later:
        return None
    try:
        a = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
        b = datetime.fromisoformat(later.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(int((b - a).total_seconds() * 1000), 0)
