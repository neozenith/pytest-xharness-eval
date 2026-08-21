"""pytest-xharness-eval: run one agent-skill eval across every agent CLI harness.

Discovers ``eval_*.py`` cases under ``<skills root>/<skill>/evals/`` and runs each
across a matrix of agent CLIs and models, capturing every run's own session log,
pricing it, and grading what the agent left behind in a fresh workspace.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.case import EvalCase, evalcase
from pytest_xharness_eval.matrix import DEFAULT_MATRIX, Cell
from pytest_xharness_eval.runresult import RunResult, Usage

__all__ = ["DEFAULT_MATRIX", "Cell", "EvalCase", "RunResult", "Usage", "evalcase"]
__version__ = "0.1.1"
