"""What every prose-gates scenario shares: the gate command, the seed rows, and a free oracle.

Imported by bare name from the suite beside it: the plugin puts the evals directory on
``sys.path`` (ADR 0074), so this needs no ``conftest.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from pytest_xharness_eval.model.generators import Table
from pytest_xharness_eval.model.scenario import Files, read_tree, write_tree

#: The prose-gates checkout under test. Required: an unset variable stops collection by name.
REPO = Path(os.environ["PROSE_GATES_REPO"])
GATE_ARGV = ("bun", "run", str(REPO / "src" / "bin.ts"), "--no-plugins")
FIXTURES = REPO / "evals" / "prose-gates" / "evals" / "fixtures"
SCRATCH = (".*_cache/*",)
ORACLE_DIR = Path(__file__).resolve().parents[3] / ".xharness_eval_cache" / "oracle"

#: One row per rule the fixer cannot settle: the seed directory, its file, the rule, and how
#: much of the prose a correct rewrite keeps. These were five suite files; now they are data.
ROWS = [
    {
        "dir": "em_dash_range",
        "target": "reading-order.md",
        "rule": "punctuation-em-dash-in-prose",
        "at_least": 1.0,
        "ratio": [0.95, 1.2],
    },
    {
        "dir": "paragraph_over_budget",
        "target": "onboarding.md",
        "rule": "paragraph-sentence-budget-exceeded",
        "at_least": 1.0,
        "ratio": [0.95, 1.25],
    },
    {
        "dir": "semicolon_without_lead_in",
        "target": "release-checklist.md",
        "rule": "list-semicolon-delimited-run",
        "at_least": 0.9,
        "ratio": [0.9, 1.3],
    },
    {
        "dir": "sentence_over_budget",
        "target": "release-guide.md",
        "rule": "sentence-word-budget-exceeded",
        "at_least": 0.9,
        "ratio": [0.9, 1.4],
    },
    {
        "dir": "sentence_with_series",
        "target": "supported-platforms.md",
        "rule": "sentence-word-budget-exceeded",
        "at_least": 0.9,
        "ratio": [0.9, 1.4],
    },
]

#: The subject under test: a wrapper around the gate that the agent runs. Each edit of it is
#: a new subject version (``tracks=``); the grader keeps judging with the unwrapped gate.
TOOL = Path(__file__).resolve().parents[3] / "tool" / "gate"
TASK = "Make `" + str(TOOL) + " {target}` exit 0 by editing {target} in place."


def _seed(row: dict[str, object]) -> Files:
    return {rel: raw.decode("utf-8") for rel, raw in read_tree(FIXTURES / str(row["dir"])).items()}


SEEDS = Table(name="prose-gates-rules", rows=ROWS, build=_seed, label="dir", task=TASK, expect=("at_least", "ratio"))


def rules_hit(files: Files) -> frozenset[str]:
    """The gate's rule ids on a file tree: free and deterministic, so it screens mutants before they cost a run."""
    # One directory per process: every xdist worker collects, and so screens, in parallel.
    scratch = write_tree(files, ORACLE_DIR / str(os.getpid()))
    targets = [rel for rel in files if rel.endswith(".md")]
    # From inside the tree: the gate discovers a GLOSSARY.md config from its cwd upwards.
    done = subprocess.run([*GATE_ARGV, "--json", *targets], capture_output=True, text=True, check=False, cwd=scratch)
    report = json.loads(done.stdout)
    return frozenset(str(f["rule"]) for f in report["findings"])
