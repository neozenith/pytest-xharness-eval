"""Shared builders for the test suite."""

# Standard Library
import json
import textwrap
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    RunResult,
    Usage,
)
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.model.verdict import Verdict


def _result(model: str, usage: Usage, harness: str = "claude") -> RunResult:
    # A real harness name: coverage attribution resolves it to ask which tool names mean
    # "ran a shell command" and which of those keep their cwd (ADR 0034).
    return RunResult(
        harness=harness,
        model=model,
        session_id="s",
        session_log="l",
        workspace="w",
        exit_code=0,
        duration_ms=1,
        turns=1,
        final_text="",
        usage=usage,
    )


# The day every bundled-table test prices on: inside the one open record, so the tests
# pin today's rates without depending on the wall clock (ADR 0050).
DAY = date(2026, 9, 29)


def _applied_rates(model: str = "m", source: str = "/p/prices-20260820.toml") -> pricing.AppliedRates:
    """A provenance block for tests that need one without going through a price table."""
    return pricing.Rates.of(
        {"input": 1.0, "output": 1.0},
        harness="claude",
        model=model,
        source=source,
        interval=pricing.Interval(date(2026, 8, 20), None),
    ).applied("2026-08-22T00:00:00+00:00")


def _metrics(
    result: RunResult,
    *,
    node: str = "n",
    verdict: Verdict = Verdict.PASS,
    wall_ms: int = 1,
    started_at: str = "t",
    cache: str = "/c",
) -> CellMetrics:
    """The record one graded cell emits, with the grading observations defaulted."""
    return CellMetrics.of(
        result,
        outcome=Outcome(node=node, verdict=verdict, wall_ms=wall_ms, started_at=started_at),
        cache=CacheLayout(Path(cache)),
    )


def _jsonl(path: Path, records: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n\nnot json\n", encoding="utf-8")
    return path


def _skill(tmp_path: Path) -> Path:
    skill = tmp_path / "demo"
    for rel, body in {
        "SKILL.md": "# demo",
        "resources/guide.md": "guide",
        "resources/unused.md": "never read",
        "scripts/check.ts": "console.log(1)",
        "scripts/never.py": "print(1)",
        "scripts/check.test.ts": "test",
        "scripts/package.json": "{}",
        "assets/icon.png": "png",
        "evals/eval_demo.py": "not part of the skill surface",
        "scripts/node_modules/x/index.js": "vendored",
        "scripts/__pycache__/a.pyc": "cache",
        ".hidden": "dotfile",
    }.items():
        (skill / rel).parent.mkdir(parents=True, exist_ok=True)
        (skill / rel).write_text(body, encoding="utf-8")
    return skill


DOC = textwrap.dedent(
    """\
    # Architecture

    ## Overview

    ```mermaid
    flowchart TD
        Loader[Load CSV] --> Transform[Transform]
        Transform --> Report[Report]
        classDef io fill:#1F4E5F,color:#FFFFFF
        class Loader,Report io
    ```

    <details>
    <summary>Detail</summary>

    ```mermaid
    flowchart LR
        Reader[Reader] --> Parser[Parser]
        classDef core fill:#7A4E2D,color:#FFFFFF
        class Reader,Parser core
    ```

    </details>
    """
)


# -- pytester trees: a one-skill project for whole-plugin sessions -------------

CASE = textwrap.dedent(
    """
    from pytest_xharness_eval import evalcase

    @evalcase(task="say hi", skill="demo", fixture="seed"{models})
    def eval_demo(output):
        assert output.run.exit_code == 0
    """
)


#: The two-cell project matrix nearly every test here wants: one arm per harness, enough to
#: exercise grouping and narrowing, and *pinned* so that widening the plugin default does not
#: renumber forty unrelated assertions. A test that is about the default itself passes
#: ``matrix=None`` and gets the bundled one.
PINNED_MATRIX = "xharness_matrix =\n    claude/claude-opus-5\n    codex/gpt-5.6-sol\n"


def make_tree(
    pytester: pytest.Pytester,
    *,
    models: str = "",
    skills_dir: str = "skills",
    ini: str = "",
    matrix: str | None = PINNED_MATRIX,
) -> Path:
    """Lay out ``<skills_dir>/demo/evals/eval_demo.py`` with ``fixtures/seed/`` and return the evals dir."""
    if matrix and "xharness_matrix" not in ini:
        ini = f"{ini}\n{matrix}" if ini else matrix
    pytester.makeini(f"[pytest]\n{ini}\n")
    skill = pytester.path / skills_dir / "demo"
    (skill / "evals" / "fixtures" / "seed").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo skill\n", encoding="utf-8")
    (skill / "evals" / "fixtures" / "seed" / "README.md").write_text("seed\n", encoding="utf-8")
    (skill / "evals" / "eval_demo.py").write_text(CASE.format(models=models), encoding="utf-8")
    return skill / "evals"


def cell_ids(result: pytest.RunResult) -> list[str]:
    """The ``harness/model`` part of every collected eval node id, in order."""
    return [line.split("[", 1)[1].rstrip("]") for line in result.stdout.lines if "::eval_demo[" in line]
