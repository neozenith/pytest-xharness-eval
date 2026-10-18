"""pytest-xharness-eval: run one agent-skill eval across every agent CLI harness.

Discovers ``eval_*.py`` cases under ``<skills root>/<subject>/evals/`` and runs each
across a matrix of agent CLIs and models, capturing every run's own session log,
pricing it, and grading what the agent left behind in a fresh workspace. A case invokes a
skill or sends a scenario's task verbatim, on a committed fixture or on generated
scenarios (ADR 0074), and the suite's analyzers question every stored sample (ADR 0075).

The package listing is the architecture (ADR 0039). Four entry-point modules sit at the
root because something outside this package resolves them by name -- ``plugin`` through
the ``pytest11`` entry point (ADR 0014), and ``replay``, ``promote`` and ``analysis``
through ``python -m`` -- and the seven layers each run is pushed through are folders
beneath them, each depending only on the ones below it:

* ``model/`` -- the nouns: a run, a case, a cell, a workspace, a cache tree, the clock.
* ``harness/`` -- one adapter class per agent CLI, and the toolkit they fold with.
* ``derive/`` -- what a folded run cost, and which of the skill it reached.
* ``verify/`` -- the shared checks and the golden comparison a grader is written with.
* ``emit/`` -- the documents that leave: the metrics record and the report microsite.
* ``analyze/`` -- the Analyzer: samples, estimates and comparisons across runs and versions.
* ``runtime/`` -- how a sweep is wired: settings, and the steps after the CLI returns.

Names re-exported here are the package's public API: the case decorator and the record
types a grader is handed, the fixture generators and the Analyzer, plus the layer modules
a project writing its own harness or grader imports by name.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval import emit as report
from pytest_xharness_eval import verify as verify
from pytest_xharness_eval.analyze import Analysis, Samples
from pytest_xharness_eval.derive import pricing as pricing
from pytest_xharness_eval.derive import skillcov as skillcov
from pytest_xharness_eval.harness import normalise as normalise
from pytest_xharness_eval.harness import records as records
from pytest_xharness_eval.model import generators as generators
from pytest_xharness_eval.model.case import CaseKind, EvalCase, evalcase
from pytest_xharness_eval.model.catalogue import ModelSpec
from pytest_xharness_eval.model.findings import Change, analyzer
from pytest_xharness_eval.model.generators import Adversarial, Generated, Promoted, Table
from pytest_xharness_eval.model.matrix import Cell
from pytest_xharness_eval.model.output import CaseOutput, Seed
from pytest_xharness_eval.model.runresult import (
    Call,
    CaseRef,
    CostStatus,
    ExecutedCommand,
    RunResult,
    Subagent,
    ToolCall,
    ToolResult,
    Usage,
)
from pytest_xharness_eval.model.scenario import Draw, FixtureGenerator, GenerationContext, Scenario

__all__ = [
    "Adversarial",
    "Analysis",
    "Call",
    "CaseKind",
    "CaseOutput",
    "CaseRef",
    "Cell",
    "Change",
    "CostStatus",
    "Draw",
    "EvalCase",
    "ExecutedCommand",
    "FixtureGenerator",
    "Generated",
    "GenerationContext",
    "ModelSpec",
    "Promoted",
    "RunResult",
    "Samples",
    "Scenario",
    "Seed",
    "Subagent",
    "Table",
    "ToolCall",
    "ToolResult",
    "Usage",
    "analyzer",
    "evalcase",
    "generators",
    "normalise",
    "pricing",
    "records",
    "report",
    "skillcov",
    "verify",
]
__version__ = "0.13.0"
