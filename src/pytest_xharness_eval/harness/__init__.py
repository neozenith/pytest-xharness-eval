"""Harnesses: one class per agent CLI, discovered through the registry in :mod:`.base`.

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
