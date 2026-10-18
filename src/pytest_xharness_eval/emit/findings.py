"""``report/analysis.json``: what every analyzer concluded over a cache, as a type.

One document per analysis run, live at session end or re-run free over a cache: when it was
generated, whether every analyzer held, and each
:class:`~pytest_xharness_eval.model.findings.Finding` with the comparisons and details that
justify it. The path is the caller's to choose (the cache layout names it); this type only
knows how to serialise itself there.
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
    from pytest_xharness_eval.model.findings import Finding


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalysisReport:
    """Every analyzer's finding from one analysis run, and when it ran."""

    generated_at: str
    findings: tuple[Finding, ...] = ()

    @classmethod
    def of(cls, findings: Iterable[Finding], *, generated_at: str) -> Self:
        """The report of these findings, in the order given."""
        return cls(generated_at=generated_at, findings=tuple(findings))

    @property
    def passed(self) -> bool:
        """Whether every analyzer held; an analysis with no analyzers holds vacuously."""
        return all(f.passed for f in self.findings)

    @property
    def failed(self) -> tuple[Finding, ...]:
        """The findings that did not hold, in report order."""
        return tuple(f for f in self.findings if not f.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
        }

    def write(self, path: Path) -> Path:
        """Serialise to ``path`` as indented JSON; parents are created."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path
