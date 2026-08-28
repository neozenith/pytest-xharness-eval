"""The harness abstraction: one class per agent CLI, and the registry that names them.

*Harness* is the first matrix axis (ADR 0015). This module is where that axis stops
being a bare string: everything a provider does differently lives behind one interface,
so nothing outside this package branches on ``"claude"`` or ``"codex"`` again. Adding a
third CLI is subclassing :class:`Harness`, implementing its five members, and calling
:func:`register`; every dispatch site below picks it up with no further edit.

The two shipped dialects differ in what a session log *contains*, not merely in its
shape. Claude's log omits the session id, the cost and the aggregate usage -- those
exist only on the ``-p --output-format json`` stdout envelope -- while a Codex rollout
is self-contained but carries no exit code. That asymmetry is the reason
:class:`SessionLog` exists: each provider holds its own side-channel, so every caller
gets one uniform :meth:`SessionLog.to_result`, and no caller has to know which dialect
needs what. Before this split, the reconstruction of Claude's envelope lived in the
replay module, which otherwise knows nothing about Claude.

Spawning a CLI is never mocked or faked (ADR 0002): :func:`spawn` and every
``Harness.run`` carry ``pragma: no cover`` with that reason, and are exercised only by
paid live evals in a consuming repository.
"""

from __future__ import annotations

# Standard Library
import subprocess
from abc import ABC, abstractmethod
from collections import Counter
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    # Standard Library
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.layout import SessionDir
    from pytest_xharness_eval.model.runresult import RunResult

DEFAULT_TIMEOUT_S = 600


class RunError(RuntimeError):
    """A cell failed in a way that must not be graded (fail loud, never degrade)."""


class UnknownHarness(LookupError):
    """A harness name no registered class answers to.

    Raised rather than falling back to a default: a silent default would classify one
    provider's records as another's, which is the failure this registry exists to end.
    """


def spawn(
    cmd: list[str], cwd: Path, env: dict[str, str], timeout_s: int
) -> subprocess.CompletedProcess[str]:  # pragma: no cover - spawns a real CLI (ADR 0002)
    """Run a CLI to completion, capturing both streams. The one place a subprocess starts."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s)


class SessionLog(ABC):
    """One captured session in a provider's dialect, plus the side-channel that dialect needs.

    ``path`` is the JSONL log itself. Anything a dialect needs *besides* the log is held
    by the subclass -- Claude's stdout envelope, Codex's exit code and forked rollouts --
    so :meth:`to_result` has the same signature for every harness.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @abstractmethod
    def to_result(self, workspace: Path, files_written: list[str]) -> RunResult:
        """Fold this log into a RunResult: one :class:`Call` per model API call (ADR 0019)."""


class Harness(ABC):
    """One agent CLI: how it is invoked, how its log is read, and what its records mean."""

    #: The matrix axis value and the ``harness`` key on every record (ADR 0015).
    name: ClassVar[str]
    #: Tool names this CLI uses to run a shell command, for coverage attribution (ADR 0027).
    shell_tools: ClassVar[frozenset[str]] = frozenset()
    #: Of those, the ones whose working directory persists between calls.
    persistent_shells: ClassVar[frozenset[str]] = frozenset()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    @abstractmethod
    def run(
        self,
        *,
        prompt: str,
        model: str,
        workspace: Path,
        skill_dir: Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> RunResult:
        """Invoke the CLI in ``workspace`` and return the normalised result.

        Implementations must correlate the run to its own session log without searching
        for it, and raise :class:`RunError` rather than grading a run whose evidence is
        missing or ambiguous.
        """

    @abstractmethod
    def session_from_capture(self, session: SessionDir, stored: dict[str, Any]) -> SessionLog:
        """Rebuild this harness's session log from a captured session directory (ADR 0023).

        ``session`` names the captured files rather than spelling them out, so a dialect
        never hardcodes ``log.jsonl`` (ADR 0037). ``stored`` is the previously written
        ``result.json``: a dialect whose log is incomplete recovers its side-channel from
        there; a self-contained one ignores all but the fields it needs. This is the replay
        path, and it must fold to the same result the live run produced.
        """

    def classify(self, rec: dict[str, Any]) -> str:
        """The kind of one log record: ``<harness>/<type>[/<subtype>]`` (ADR 0022); never raises.

        A record that is not even a mapping is this harness's ``/unknown``: a census must
        describe a malformed log rather than refuse to read it.
        """
        if not isinstance(rec, dict):
            return f"{self.name}/unknown"
        return self.classify_record(rec)

    @abstractmethod
    def classify_record(self, rec: dict[str, Any]) -> str:
        """Classify one well-formed record of this harness's own dialect."""

    def census(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """How many records of each kind a log holds, sorted by kind (ADR 0022)."""
        return dict(sorted(Counter(self.classify(r) for r in records).items()))


# -- the registry ---------------------------------------------------------------------

_REGISTRY: dict[str, Harness] = {}


def register(harness: Harness) -> Harness:
    """Add a harness to the registry under its ``name``; the last registration wins."""
    _REGISTRY[harness.name] = harness
    return harness


def get(name: str) -> Harness:
    """The registered harness called ``name``, or :class:`UnknownHarness`."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownHarness(
            f"unknown harness {name!r}; registered harnesses are {', '.join(names()) or '(none)'}"
        ) from None


def unregister(name: str) -> None:
    """Remove a harness from the registry; unknown names are ignored.

    The counterpart to :func:`register`, so anything that adds a harness for the duration
    of a scope can take it out again without reaching into the registry itself.
    """
    _REGISTRY.pop(name, None)


def names() -> tuple[str, ...]:
    """Every registered harness name, sorted."""
    return tuple(sorted(_REGISTRY))
