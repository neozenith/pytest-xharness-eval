"""What pytest collects: which files are eval suites, and the item one cell is (ADR 0008).

The collection rule is a layout rule, and a narrow one on purpose: an ``eval_*.py`` file,
directly inside an ``evals/`` directory, one level under the skills root. Anything else
with the same name elsewhere in the repository is not an eval suite and is never imported.

Within a matched suite the rule repeats itself for functions -- the ``eval_`` prefix is to
this plugin what ``test_`` is to pytest -- and every way of getting it slightly wrong is a
loud :class:`pytest.UsageError` at collection rather than a session that quietly grades
nothing: no ``@evalcase`` in the file, a case whose grader is misnamed, or a model nobody
has a price for (ADR 0007).
"""

from __future__ import annotations

# Standard Library
from typing import TYPE_CHECKING, Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.derive import pricing, skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model.suite import EvalSuite
from pytest_xharness_eval.plugin.cell import CellRun
from pytest_xharness_eval.plugin.results import RECORD_KEY
from pytest_xharness_eval.runtime.settings import Settings

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.case import EvalCase


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.Collector | None:
    """Collect ``eval_*.py`` modules that sit in ``<skills root>/<skill>/evals/``."""
    if (
        file_path.suffix == ".py"
        and file_path.name.startswith("eval_")
        and file_path.parent.name == "evals"
        and file_path.parent.parent.parent.resolve() == Settings.from_config(parent.config).skills_root
    ):
        return EvalFile.from_parent(parent, path=file_path)
    return None


class EvalFile(pytest.File):
    """One ``eval_*.py`` suite; yields one item per (case, cell)."""

    def collect(self) -> Iterator[pytest.Item]:
        cases = self._cases()
        settings = Settings.from_config(self.config)
        table = settings.price_table()
        opts = self.config.option
        for case in cases:
            models = settings.matrix_for(case)
            # ADR 0007: an unpriced model stops the sweep at collection, before any spend.
            pricing.validate_matrix(models, table)
            # ADR 0022: the skill's file tree is catalogued here, before any cell runs, so every
            # cell of the sweep is measured against the same inventory.
            skill_dir = settings.skill_dir(case.skill)
            files = skillcov.catalog(skill_dir, ignore=settings.skill_ignore) if skill_dir.is_dir() else []
            for cell in mx.narrow(mx.expand(models), opts.model, opts.harness):
                yield EvalItem.from_parent(
                    self, name=f"{case.name}[{cell.id}]", case=case, cell=cell, skill_files=files
                )

    def _cases(self) -> list[EvalCase]:
        """Every case this suite declares, or a usage error naming what is wrong with it.

        A file that matched the layout and declares nothing is the failure mode this check
        exists for: it looks like an opt-in, and silently collecting zero cells from it
        would report a green sweep that graded nothing.
        """
        cases = EvalSuite.load(self.path).cases
        if not cases:
            raise pytest.UsageError(
                f"{self.path} matched the evals layout but defines no @evalcase; "
                "a malformed opt-in must fail loudly, not collect zero cells"
            )
        misnamed = [c.name for c in cases if not c.name.startswith("eval_")]
        if misnamed:
            raise pytest.UsageError(
                f"{self.path}: @evalcase functions must be named eval_*, got {misnamed}; "
                "the eval_ prefix is the collection rule for files and functions alike, as test_ is for pytest"
            )
        return cases


class EvalItem(pytest.Item):
    """One cell: run the CLI in a fresh workspace, price it, capture evidence, grade.

    The item is the pytest-facing half of a cell -- its node id, its markers, how a failure
    reads -- and holds what collection resolved for it. Running it is
    :class:`~pytest_xharness_eval.plugin.cell.CellRun`, which knows nothing about pytest
    beyond the stash it leaves its record in.
    """

    def __init__(
        self, *, case: EvalCase, cell: mx.Cell, skill_files: list[skillcov.SkillFile] | None = None, **kw: Any
    ) -> None:
        super().__init__(**kw)
        self.case = case
        self.cell = cell
        # The skill's catalogued files (ADR 0022), taken at collection.
        self.skill_files = list(skill_files or [])
        self.add_marker("eval")
        # Optional lever: `-n N --dist loadgroup` keeps one harness's cells on one worker
        # (parallel across harnesses, serial within one). Plain `-n N` is also fine.
        self.add_marker(pytest.mark.xdist_group(self.cell.harness))

    @property
    def node(self) -> str:
        """The node id without xdist's ``@<group>`` suffix, so records key the same with or without ``-n``."""
        return self.nodeid.removesuffix(f"@{self.cell.harness}")

    @property
    def evals_dir(self) -> Path:
        """The ``evals/`` directory this suite lives in."""
        return self.path.parent

    @property
    def fixture_dir(self) -> Path:
        """``evals/fixtures/<name>/`` (ADR 0018)."""
        return self.evals_dir / "fixtures" / self.case.fixture

    @property
    def suite(self) -> str:
        """This suite file, relative to the project root when it is under one (ADR 0025)."""
        try:
            return str(self.path.relative_to(self.config.rootpath))
        except ValueError:
            return str(self.path)

    def runtest(self) -> None:
        """Check the two directories a cell cannot run without, then run it -- or skip, unpaid.

        Both checks fail the cell even under ``--dry-run``: a sweep whose skill or fixture
        has been renamed must not report "would invoke" for a run that could not happen.
        """
        settings = Settings.from_config(self.config)
        skill_dir = settings.skill_dir(self.case.skill)
        if not skill_dir.is_dir():
            raise harness.RunError(f"skill under test not found: {skill_dir}")
        if not self.fixture_dir.is_dir():
            raise harness.RunError(f"fixture directory not found: {self.fixture_dir}")

        if self.config.option.eval_dry_run:
            self.stash[RECORD_KEY] = CellMetrics.dry_run(node=self.node, cell=self.cell)
            pytest.skip(f"dry-run: would invoke {self.cell.id}")

        self._run_live(settings, skill_dir)

    def _run_live(self, settings: Settings, skill_dir: Path) -> None:  # pragma: no cover - spends (ADR 0002)
        """The paid path: build this cell's run and execute it.

        Two statements, and everything under them is covered: each step of
        :class:`~pytest_xharness_eval.plugin.cell.CellRun` is exercised from captured logs
        in ``tests/test_units.py``. What no test may reach is the CLI spawn inside
        :meth:`~pytest_xharness_eval.plugin.cell.CellRun.invoke`, and faking it is what ADR
        0002 forbids -- so the pragma stops here rather than covering the sequence too.
        """
        run = CellRun(
            case=self.case,
            cell=self.cell,
            settings=settings,
            skill_dir=skill_dir,
            fixture_dir=self.fixture_dir,
            node=self.node,
            suite=self.suite,
            skill_files=self.skill_files,
        )
        run.execute(self.stash)

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:  # type: ignore[override]
        return f"[{self.cell.id}] {excinfo.getrepr(style='short')}"

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, 0, f"eval: {self.name}"
