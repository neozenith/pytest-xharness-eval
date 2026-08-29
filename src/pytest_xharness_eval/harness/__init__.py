"""The adapters: one class per agent CLI, plus the toolkit every dialect folds with.

The layer that turns a provider's session log into the domain's :class:`RunResult` and
knows nothing about what happens to it afterwards. Four parts:

* :mod:`.base` -- the :class:`Harness` interface, the :class:`SessionLog` it folds, and
  the registry that is the only dispatch on a harness name (ADR 0034).
* :mod:`.claude` and :mod:`.codex` -- the two shipped dialects. Nothing outside this
  package may name them; the ruff rule in ``pyproject.toml`` enforces it.
* :mod:`.normalise` -- the dialect-free folding toolkit both adapters build a ledger with.
* :mod:`.records` -- the catalogue of record kinds and the categories they belong to
  (ADR 0022), shared by both dialects and mirrored by the report page.

Importing this package registers every shipped harness, so ``harness.get("claude")``
works anywhere without the caller importing the provider module. A project adding its
own CLI subclasses :class:`Harness` and calls :func:`register`; see :mod:`.base`.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.harness.base import (
    DEFAULT_TIMEOUT_S,
    Harness,
    RunError,
    SessionLog,
    UnknownHarness,
    get,
    names,
    register,
    spawn,
    unregister,
)
from pytest_xharness_eval.harness.claude import CLAUDE, ClaudeHarness, ClaudeSessionLog
from pytest_xharness_eval.harness.codex import CODEX, CodexHarness, CodexSessionLog

__all__ = [
    "CLAUDE",
    "CODEX",
    "DEFAULT_TIMEOUT_S",
    "ClaudeHarness",
    "ClaudeSessionLog",
    "CodexHarness",
    "CodexSessionLog",
    "Harness",
    "RunError",
    "SessionLog",
    "UnknownHarness",
    "get",
    "names",
    "register",
    "spawn",
    "unregister",
]
