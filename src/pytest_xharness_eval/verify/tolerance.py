"""How much a candidate may differ from a golden, per facet, and how that reads (ADR 0046).

A tolerance answers one question about one extracted feature: *how free is this part of
the answer?* Six kinds cover the range between "there is one right value" and "this is a
number with a defensible band", and every one of them reports the same way -- a verdict
carrying the golden's value, the candidate's value, and, where the answer is a set, what
was missing and what was extra.

A facet with no tolerance is a type error rather than a default to :class:`Exact`. The
whole point of the mechanism is that the author states how free each part is; silently
defaulting to the strictest option would produce a red cell whose message blames the
agent for variation the author never meant to forbid.
"""

from __future__ import annotations

# Standard Library
import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Callable


def _as_set(value: Any) -> set[str] | None:
    """``value`` as a set of strings when it is set-shaped, else None.

    A string is deliberately *not* set-shaped: iterating one yields characters, and a
    facet returning a string almost always means "compare this text", not "compare these
    letters".
    """
    if isinstance(value, (set, frozenset)):
        return {str(v) for v in value}
    if isinstance(value, (list, tuple)):
        return {str(v) for v in value}
    return None


@dataclass(frozen=True, slots=True)
class Verdict:
    """One facet's outcome: whether it held, and the evidence either way.

    ``missing`` and ``extra`` are populated only by the set tolerances, and they are the
    reason a golden report is readable at all: "3 of 11 node ids differ" is a number,
    while "missing {Loader}, extra {Reader}" is a diagnosis.
    """

    ok: bool
    detail: str
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()


class Tolerance(ABC):
    """How far a candidate facet may sit from the golden's and still be correct."""

    @abstractmethod
    def describe(self) -> str:
        """This tolerance in one short phrase, for the report's own column."""

    @abstractmethod
    def check(self, golden: Any, candidate: Any) -> Verdict:
        """Whether ``candidate`` is within tolerance of ``golden``."""


@dataclass(frozen=True, slots=True)
class Exact(Tolerance):
    """Equality. For the part of the answer that has exactly one right value."""

    def describe(self) -> str:
        return "exact"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        g, c = _as_set(golden), _as_set(candidate)
        if g is not None and c is not None:
            return Verdict(
                ok=g == c,
                detail=f"{len(c)} of {len(g)} expected",
                missing=tuple(sorted(g - c)),
                extra=tuple(sorted(c - g)),
            )
        return Verdict(ok=golden == candidate, detail="equal" if golden == candidate else "differs")


@dataclass(frozen=True, slots=True)
class Superset(Tolerance):
    """The golden's items are a required floor; the candidate may add to them.

    For a facet where the golden enumerates what must be present and says nothing about
    what else may be -- a set of required headings, a minimum set of node ids.
    """

    def describe(self) -> str:
        return "contains all"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        g, c = _as_set(golden), _as_set(candidate)
        if g is None or c is None:
            return Verdict(ok=False, detail=f"Superset needs set-shaped facets, got {type(candidate).__name__}")
        missing = g - c
        return Verdict(
            ok=not missing,
            detail=f"{len(g & c)} of {len(g)} required present",
            missing=tuple(sorted(missing)),
            extra=tuple(sorted(c - g)),
        )


@dataclass(frozen=True, slots=True)
class Jaccard(Tolerance):
    """Set overlap at or above a threshold: |A ∩ B| / |A ∪ B|.

    For a facet whose *concepts* are fixed by the fixture but whose *names* are the
    agent's to choose. A threshold below about 0.7 is usually a sign the facet is the
    wrong extraction rather than a sign the threshold is right (ADR 0046).
    """

    at_least: float

    def describe(self) -> str:
        return f"overlap >= {self.at_least:.2f}"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        g, c = _as_set(golden), _as_set(candidate)
        if g is None or c is None:
            return Verdict(ok=False, detail=f"Jaccard needs set-shaped facets, got {type(candidate).__name__}")
        union = g | c
        score = len(g & c) / len(union) if union else 1.0
        return Verdict(
            ok=score >= self.at_least,
            detail=f"overlap {score:.2f}",
            missing=tuple(sorted(g - c)),
            extra=tuple(sorted(c - g)),
        )


@dataclass(frozen=True, slots=True)
class Ratio(Tolerance):
    """Text similarity at or above a threshold, by :class:`difflib.SequenceMatcher`.

    For prose that must stay recognisable without being reproduced: a preserved paragraph,
    a heading whose wording may drift.
    """

    at_least: float

    def describe(self) -> str:
        return f"similarity >= {self.at_least:.2f}"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        score = difflib.SequenceMatcher(None, str(golden), str(candidate)).ratio()
        return Verdict(ok=score >= self.at_least, detail=f"similarity {score:.2f}")


@dataclass(frozen=True, slots=True)
class Count(Tolerance):
    """A count near the golden's, or inside an absolute range.

    ``Count(delta=1)`` is relative to whatever the golden has; ``Count(lo=2, hi=4)`` is
    absolute and ignores the golden's own value. Set exactly one form.
    """

    delta: int | None = None
    lo: int | None = None
    hi: int | None = None

    def __post_init__(self) -> None:
        relative = self.delta is not None
        absolute = self.lo is not None or self.hi is not None
        if relative == absolute:
            raise ValueError("Count takes either delta= or lo=/hi=, not both and not neither")

    def describe(self) -> str:
        if self.delta is not None:
            return f"count +/- {self.delta}"
        return f"count in [{self.lo if self.lo is not None else '-'}, {self.hi if self.hi is not None else '-'}]"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        g, c = _count(golden), _count(candidate)
        if self.delta is not None:
            return Verdict(ok=abs(c - g) <= self.delta, detail=f"{c} vs {g} (delta {c - g:+d})")
        low_ok = self.lo is None or c >= self.lo
        high_ok = self.hi is None or c <= self.hi
        return Verdict(ok=low_ok and high_ok, detail=f"{c}")


@dataclass(frozen=True, slots=True)
class Within(Tolerance):
    """A number inside a closed range, independent of the golden's own value.

    For a measure with a band the author can defend -- a contrast ratio, a node count
    budget the skill itself declares.
    """

    lo: float
    hi: float

    def describe(self) -> str:
        return f"in [{self.lo:g}, {self.hi:g}]"

    def check(self, golden: Any, candidate: Any) -> Verdict:
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            return Verdict(ok=False, detail=f"not a number: {candidate!r}")
        return Verdict(ok=self.lo <= value <= self.hi, detail=f"{value:g}")


def _count(value: Any) -> int:
    """``value`` as a count: its length when it is sized, else the integer itself."""
    as_set = _as_set(value)
    if as_set is not None:
        return len(as_set)
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (int, float)):
        return int(value)
    return len(value) if hasattr(value, "__len__") else 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Facet:
    """One named, extracted feature of an artifact, and how free it is.

    ``extract`` is any ``str -> object``, so a project compares whatever its artifact has;
    :mod:`pytest_xharness_eval.verify.facets` ships the markdown and mermaid extractors the
    bundled cases need. ``why`` is one line saying what this facet protects, and it is
    printed beside a failure: a reader who does not already know the skill has to be able
    to judge whether the check itself is right.

    Keyword-only, because ``Facet("nodes", node_ids, Jaccard(0.9))`` reads as three
    interchangeable positional arguments and it is the third that carries the claim.
    """

    name: str
    extract: Callable[[str], object]
    tolerance: Tolerance
    why: str = ""

    def of(self, text: str) -> object:
        """This facet's value in ``text``."""
        return self.extract(text)
