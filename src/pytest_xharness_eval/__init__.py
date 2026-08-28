"""pytest-xharness-eval: run one agent-skill eval across every agent CLI harness.

Discovers ``eval_*.py`` cases under ``<skills root>/<skill>/evals/`` and runs each
across a matrix of agent CLIs and models, capturing every run's own session log,
pricing it, and grading what the agent left behind in a fresh workspace.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.case import EvalCase, evalcase
from pytest_xharness_eval.matrix import DEFAULT_MATRIX, Cell
from pytest_xharness_eval.runresult import Call, CaseRef, CostStatus, RunResult, Subagent, ToolCall, ToolResult, Usage

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
]
__version__ = "0.2.0"
