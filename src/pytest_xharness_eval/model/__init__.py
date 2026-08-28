"""The nouns: what a run, a case, a cell, a workspace and a cache tree *are*.

The bottom layer. Everything here is a value type with its own invariants or a pure
function over one, and nothing here knows how a CLI is invoked, how a price is looked up
or how a report is written -- those are the layers above (``harness/``, ``derive/``,
``emit/``, ``runtime/``), and the ruff layer rule in ``pyproject.toml`` keeps the arrows
pointing this way (ADR 0039).

* :mod:`.runresult` -- the normalised record every harness folds its session log into,
  and the ``result.json`` wire format (ADR 0019, ADR 0035).
* :mod:`.case` -- the ``@evalcase`` contract an ``eval_*.py`` module declares (ADR 0008).
* :mod:`.suite` -- importing one of those modules by path, and finding the case it
  declares: the one loader collection and a replay share (ADR 0040).
* :mod:`.matrix` -- the ``harness/model`` cells a case sweeps (ADR 0010, ADR 0015).
* :mod:`.layout` -- every path under a project's eval cache (ADR 0032, ADR 0038).
* :mod:`.workspace` -- materialising a fixture into a per-cell workspace (ADR 0004).
* :mod:`.clock` and :mod:`.documents` -- the wall clock, and reading back a document this
  package wrote.
* :mod:`.registry` -- the one module below the adapter layer that names it.

Submodules import each other by full dotted path, never through this file: importing the
matrix reaches the harness registry, so a name bound here is not yet available to
everything that ends up loading during it.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.model.case import EvalCase, evalcase
from pytest_xharness_eval.model.clock import ms_between, now_iso
from pytest_xharness_eval.model.documents import read_json_object
from pytest_xharness_eval.model.layout import CacheLayout, LocatedSession, SessionDir
from pytest_xharness_eval.model.matrix import DEFAULT_MATRIX, Cell, expand, known_harnesses, narrow
from pytest_xharness_eval.model.registry import Shells
from pytest_xharness_eval.model.runresult import (
    Call,
    CaseRef,
    CostStatus,
    RunResult,
    Subagent,
    ToolCall,
    ToolResult,
    Usage,
)
from pytest_xharness_eval.model.suite import EvalSuite, find_case, suites_under
from pytest_xharness_eval.model.workspace import diff, materialise, snapshot

__all__ = [
    "DEFAULT_MATRIX",
    "CacheLayout",
    "Call",
    "CaseRef",
    "Cell",
    "CostStatus",
    "EvalCase",
    "EvalSuite",
    "LocatedSession",
    "RunResult",
    "SessionDir",
    "Shells",
    "Subagent",
    "ToolCall",
    "ToolResult",
    "Usage",
    "diff",
    "evalcase",
    "expand",
    "find_case",
    "known_harnesses",
    "materialise",
    "ms_between",
    "narrow",
    "now_iso",
    "read_json_object",
    "snapshot",
    "suites_under",
]
