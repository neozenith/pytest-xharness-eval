"""A golden: a known-correct artifact, compared facet by facet within declared tolerance (ADR 0046).

Between "the output contains the word" and "the output equals this file" there is one
honest position, and this module is it. A golden is a real, complete, correct artifact
committed at ``evals/goldens/<name>/<path>`` -- mirroring ``evals/fixtures/<name>/<path>``,
so the pairing between a seed and its known-good answer is the directory layout and not a
convention anyone has to remember. A :class:`GoldenCase` is that artifact plus the list of
facets to compare and, per facet, how much variation is still correct.

The failure is a delta, not a diff. :class:`GoldenMismatch` prints one row per facet --
name, tolerance, golden's value, candidate's value, what is missing and what is extra --
including the facets that *passed*, because a report showing only failures cannot tell a
reader "one facet failed" from "one facet ran".
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.output import CaseOutput
    from pytest_xharness_eval.verify.tolerance import Facet, Verdict

#: Where a golden artifact lives, relative to an ``evals/`` directory (ADR 0046).
GOLDENS_DIR = "goldens"

# How much of a value or a set difference one report row may show. Wide enough that a
# node-id set is legible in full, narrow enough that a whole document is not pasted into
# a pytest failure.
_WIDTH = 240


def _render(value: object) -> str:
    """One facet value, on one line, truncated to a readable width."""
    if isinstance(value, (set, frozenset)):
        value = sorted(str(v) for v in value)
    text = str(value)
    return text if len(text) <= _WIDTH else f"{text[: _WIDTH - 1]}…"


def _names(items: Sequence[str]) -> str:
    """A missing/extra list, truncated by count as well as width."""
    if not items:
        return ""
    shown = list(items[:12])
    tail = f" (+{len(items) - len(shown)} more)" if len(items) > len(shown) else ""
    return _render(shown) + tail


@dataclass(frozen=True, slots=True)
class FacetDelta:
    """One facet's comparison: what was wanted, what arrived, and whether that was allowed."""

    facet: Facet
    golden: object
    candidate: object
    verdict: Verdict

    @property
    def ok(self) -> bool:
        """Whether this facet held within its tolerance."""
        return self.verdict.ok

    def lines(self) -> list[str]:
        """This facet as report rows: the headline, then only the evidence it has."""
        mark = "ok  " if self.ok else "FAIL"
        out = [f"  [{mark}] {self.facet.name}  ({self.facet.tolerance.describe()}: {self.verdict.detail})"]
        if self.ok:
            return out
        if self.facet.why:
            out.append(f"           why: {self.facet.why}")
        out.append(f"           golden:    {_render(self.golden)}")
        out.append(f"           candidate: {_render(self.candidate)}")
        if self.verdict.missing:
            out.append(f"           missing:   {_names(self.verdict.missing)}")
        if self.verdict.extra:
            out.append(f"           extra:     {_names(self.verdict.extra)}")
        return out


class GoldenMismatch(AssertionError):
    """A candidate fell outside a golden's declared tolerances.

    An :class:`AssertionError`, so a cell that hits one grades as ``fail`` rather than
    ``error`` (ADR 0012): the skill produced the wrong answer, which is a result, not a
    harness malfunction.
    """


@dataclass(frozen=True, slots=True)
class GoldenDelta:
    """Every facet's comparison for one artifact, and how it reads as a failure."""

    path: str
    golden_path: str
    deltas: tuple[FacetDelta, ...]

    @property
    def ok(self) -> bool:
        """Whether every facet held."""
        return all(d.ok for d in self.deltas)

    @property
    def failed(self) -> tuple[FacetDelta, ...]:
        """The facets that fell outside tolerance."""
        return tuple(d for d in self.deltas if not d.ok)

    def report(self) -> str:
        """The whole comparison as text: the headline, then one block per facet."""
        head = (
            f"{self.path} is outside the golden's tolerances ({len(self.failed)} of {len(self.deltas)} facets failed)"
            if not self.ok
            else f"{self.path} matches the golden on all {len(self.deltas)} facets"
        )
        rows = [line for delta in self.deltas for line in delta.lines()]
        return "\n".join([head, f"  golden: {self.golden_path}", *rows])

    def raise_for_status(self) -> None:
        """Raise :class:`GoldenMismatch` carrying :meth:`report` when any facet failed."""
        if not self.ok:
            raise GoldenMismatch(self.report())


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """One golden artifact and the facets that decide whether a candidate matches it.

    ``path`` is the artifact's path inside the workspace -- ``ARCHITECTURE.md`` -- and the
    same path is read from the golden directory, which is what makes the two trees mirror
    images of each other.
    """

    #: The golden artifact on disk: ``evals/goldens/<name>/<path>``.
    golden: Path
    #: The candidate's path, relative to the rollout's workspace.
    path: str
    #: What to compare, and how free each part is. Order is the report's order.
    facets: tuple[Facet, ...]

    @classmethod
    def at(cls, evals_dir: Path, name: str, path: str, facets: Iterable[Facet]) -> Self:
        """The golden ``name``'s ``path``, resolved under ``<evals_dir>/goldens/``.

        The one constructor a suite uses, so no case spells the ``goldens/`` level itself
        and the convention stays movable (ADR 0046, and ADR 0037's rule for the cache).
        """
        return cls(golden=evals_dir / GOLDENS_DIR / name / path, path=path, facets=tuple(facets))

    @property
    def text(self) -> str:
        """The golden artifact's text.

        Raises:
            AssertionError: when the golden is absent. A case referring to a golden nobody
                committed must fail loudly rather than compare against an empty string,
                which every tolerance would then read as "everything is missing".
        """
        if not self.golden.is_file():
            raise AssertionError(
                f"no golden committed at {self.golden}. A golden is a real, correct artifact "
                f"under evals/{GOLDENS_DIR}/; write one (GoldenCase.record can capture a run's "
                "output as a starting point) and review it before it becomes the reference."
            )
        return self.golden.read_text(encoding="utf-8")

    def compare(self, candidate: str) -> GoldenDelta:
        """Compare ``candidate`` against the golden, facet by facet. Never raises on mismatch."""
        reference = self.text
        deltas = []
        for facet in self.facets:
            want, got = facet.of(reference), facet.of(candidate)
            deltas.append(FacetDelta(facet=facet, golden=want, candidate=got, verdict=facet.tolerance.check(want, got)))
        return GoldenDelta(path=self.path, golden_path=str(self.golden), deltas=tuple(deltas))

    def assert_matches(self, output: CaseOutput) -> GoldenDelta:
        """Compare the rollout's artifact against this golden; raise the delta if it is outside.

        The one call a case makes. It returns the delta on success too, so a case that
        wants to assert something further about the facets it just extracted can, without
        re-reading the file.
        """
        delta = self.compare(output.read(self.path))
        delta.raise_for_status()
        return delta

    def record(self, output: CaseOutput) -> Path:
        """Write the rollout's artifact into the golden path, and return it.

        For creating or deliberately regenerating a reference, from a run whose output a
        human has read. Never called during grading: a run that could launder its own
        output into the reference would make every later comparison vacuous (ADR 0046).
        """
        self.golden.parent.mkdir(parents=True, exist_ok=True)
        self.golden.write_text(output.read(self.path), encoding="utf-8")
        return self.golden
