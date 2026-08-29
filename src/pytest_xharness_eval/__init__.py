"""pytest-xharness-eval: run one agent-skill eval across every agent CLI harness.

Discovers ``eval_*.py`` cases under ``<skills root>/<skill>/evals/`` and runs each
across a matrix of agent CLIs and models, capturing every run's own session log,
pricing it, and grading what the agent left behind in a fresh workspace.

The package listing is the architecture (ADR 0039). Two entry-point modules sit at the
root because something outside this package resolves them by name -- ``plugin`` through
the ``pytest11`` entry point (ADR 0014), ``replay`` through ``python -m`` -- and the five
layers each run is pushed through are folders beneath them, each depending only on the
ones below it:

* ``model/`` -- the nouns: a run, a case, a cell, a workspace, a cache tree, the clock.
* ``harness/`` -- one adapter class per agent CLI, and the toolkit they fold with.
* ``derive/`` -- what a folded run cost, and which of the skill it reached.
* ``emit/`` -- the documents that leave: the metrics record and the report microsite.
* ``runtime/`` -- how a sweep is wired: settings, and the steps after the CLI returns.

Names re-exported here are the package's public API: the case decorator and the record
types a grader is handed, plus the five layer modules a project writing its own harness
or grader imports by name.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval import emit as report
from pytest_xharness_eval.derive import pricing as pricing
from pytest_xharness_eval.derive import skillcov as skillcov
from pytest_xharness_eval.harness import normalise as normalise
from pytest_xharness_eval.harness import records as records
from pytest_xharness_eval.model.case import EvalCase, evalcase
from pytest_xharness_eval.model.matrix import DEFAULT_MATRIX, Cell
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

__all__ = [
    "DEFAULT_MATRIX",
    "Call",
    "CaseRef",
    "Cell",
    "CostStatus",
    "EvalCase",
    "RunResult",
    "Subagent",
    "ToolCall",
    "ToolResult",
    "Usage",
    "evalcase",
    "normalise",
    "pricing",
    "records",
    "report",
    "skillcov",
]
__version__ = "0.3.0"
