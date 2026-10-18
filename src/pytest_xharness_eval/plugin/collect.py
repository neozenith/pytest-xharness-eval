"""What pytest collects: which files are eval suites, and the item one cell is (ADR 0008).

The collection rule is a layout rule, and a narrow one on purpose: an ``eval_*.py`` file,
directly inside an ``evals/`` directory, one level under the skills root. Anything else
with the same name elsewhere in the repository is not an eval suite and is never imported.

Within a matched suite the rule repeats itself for functions -- the ``eval_`` prefix is to
this plugin what ``test_`` is to pytest -- and every way of getting it slightly wrong is a
loud :class:`pytest.UsageError` at collection rather than a session that quietly grades
nothing: no ``@evalcase`` in the file, a case whose grader is misnamed, a model nobody
has a price for (ADR 0007), an effort rung the named harness does not have (ADR 0049),
or a treatment with no files for a harness it is about to be swept on (ADR 0055).
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import harness
from pytest_xharness_eval.derive import skillcov
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.emit.samples import scenario_outcomes
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model import treatment
from pytest_xharness_eval.model import workspace as ws
from pytest_xharness_eval.model.catalogue import CatalogueError
from pytest_xharness_eval.model.layout import run_date
from pytest_xharness_eval.model.scenario import GenerationContext
from pytest_xharness_eval.model.suite import EvalSuite
from pytest_xharness_eval.plugin.cell import CellRun, run_stamp
from pytest_xharness_eval.plugin.results import RECORD_KEY
from pytest_xharness_eval.runtime.plan import CellPlan
from pytest_xharness_eval.runtime.settings import Settings

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator
    from pathlib import Path

    # Our Libraries
    from pytest_xharness_eval.model.case import EvalCase
    from pytest_xharness_eval.model.catalogue import Catalogue
    from pytest_xharness_eval.model.scenario import Scenario


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
        """Validate each case, resolve what its cells share, then yield one item per plan."""
        cases = self._cases()
        settings = Settings.from_config(self.config)
        suite = settings.suite_ref(self.path)
        for case in cases:
            cells = self._validate_matrix(settings, case)
            skill_dir, files = self._skill_inventory(settings, case)
            shared = _Shared(
                case=case,
                suite=suite,
                skill_dir=skill_dir,
                skill_files=tuple(files),
                version=self._version(settings, case, skill_dir),
            )
            for plan in self._plans(settings, shared, cells, self._scenarios(settings, case, suite)):
                yield EvalItem.from_parent(self, name=plan.name, plan=plan)

    def _validate_matrix(self, settings: Settings, case: EvalCase) -> list[mx.Cell]:
        """The case's cells after treatment and narrowing, once every one of them is priced, catalogued and treatable.

        ADR 0050: the rows that must exist are the ones in effect on the day this sweep's
        cells will be stamped with, which is the day every one of them is priced on.
        """
        today = run_date(run_stamp())
        models = settings.matrix_for(case, today)
        # ADR 0060: a gap is priced live from LiteLLM's feed into <cache>/pricing/ first;
        # ADR 0007: whatever is still unpriced stops the sweep here, before any spend.
        settings.ensure_priced(models, today).validate_matrix(models, today)
        cells = mx.expand(models)
        # ADR 0057: so does one the catalogue cannot say what kind of model it is.
        self._require_catalogued(settings.catalogue(), case, cells)
        # ADR 0055: a treatment that copies nothing onto some harness's workspace would bill
        # that harness's control twice under two names, so it stops collection here.
        treatments = settings.treatments_for(case)
        try:
            treatment.validate(self.path.parent, treatments, (c.harness for c in cells))
        except treatment.UnknownTreatment as exc:
            raise pytest.UsageError(f"{self.path}: {case.name}: {exc}") from exc
        opts = self.config.option
        return list(mx.narrow(mx.treat(cells, treatments), opts.model, opts.harness, opts.effort, opts.treatment))

    def _skill_inventory(self, settings: Settings, case: EvalCase) -> tuple[Path | None, list[skillcov.SkillFile]]:
        """The skill under test's directory and its catalogued files (ADR 0022).

        Catalogued here, before any cell runs, so every cell of the sweep is measured against
        the same inventory. A scenario case has no skill, so nothing to catalogue (ADR 0074).
        """
        skill_dir = settings.skill_dir(case.skill) if case.skill else None
        if skill_dir is None or not skill_dir.is_dir():
            return skill_dir, []
        return skill_dir, skillcov.catalog(skill_dir, ignore=settings.skill_ignore)

    def _plans(
        self, settings: Settings, shared: _Shared, cells: list[mx.Cell], scenarios: list[Scenario | None]
    ) -> Iterator[CellPlan]:
        """One frozen plan per scenario, cell and repeat, in that order (ADR 0074, ADR 0075).

        A repeat is another sample of the same cell, so only the node id and the workspace
        name carry it; the record keys the cell the same. ``--xharness-repeat`` was refused
        below one at configure time.
        """
        repeat = int(self.config.option.xharness_repeat or 1)
        case, evals_dir = shared.case, self.path.parent
        for scenario in scenarios:
            fixture_dir = (
                settings.cache.scenario_store(shared.suite, case.name).tree(scenario.id)
                if scenario is not None
                else evals_dir / "fixtures" / case.fixture_name
            )
            for cell in cells:
                where = f"{scenario.id}/{cell.id}" if scenario else cell.id
                overlays = treatment.layers(evals_dir, cell.treatment, cell.harness) if cell.treatment else []
                for sample in range(1, repeat + 1):
                    suffix = f"#{sample}" if repeat > 1 else ""
                    yield CellPlan(
                        case=case,
                        cell=cell,
                        node=f"{self.nodeid}::{case.name}[{where}]{suffix}",
                        suite=shared.suite,
                        subject=case.skill or evals_dir.parent.name,
                        fixture_dir=fixture_dir,
                        skill_dir=shared.skill_dir,
                        overlays=tuple(overlays),
                        skill_files=shared.skill_files,
                        scenario=scenario,
                        subject_version=shared.version,
                        sample=sample if repeat > 1 else None,
                    )

    def _version(self, settings: Settings, case: EvalCase, skill_dir: Path | None) -> str | None:
        """The digest of what the case tracks, taken once at collection (ADR 0074).

        A skill case tracks its skill's directory unless it names ``tracks=``; a scenario case
        tracks only what it names, and records no version without it.
        """
        try:
            if case.tracks:
                return ws.version(settings.rootpath, case.tracks)
            if skill_dir is not None and skill_dir.is_dir():
                return ws.version(skill_dir.parent, [skill_dir.name], exclude=["evals"])
        except FileNotFoundError as exc:
            raise pytest.UsageError(f"{self.path}: {case.name}: {exc}") from exc
        return None

    def _scenarios(self, settings: Settings, case: EvalCase, suite: str) -> list[Scenario | None]:
        """The case's generated scenarios, each written to ``<cache>/scenarios/``; ``[None]`` for a fixture directory.

        Generation runs here, before any cell spends, so a generator that raises, yields
        nothing, or yields two scenarios under one id stops the sweep by name (ADR 0074).
        """
        generator = case.generator
        if generator is None:
            return [None]
        store = settings.cache.scenario_store(suite, case.name)
        context = GenerationContext(
            evals_dir=self.path.parent,
            case=case.name,
            outcomes=scenario_outcomes(settings.cache, suite, case.name),
            store=store,
        )
        try:
            scenarios = list(generator.scenarios(context))
        except Exception as exc:  # noqa: BLE001 - user code: whatever it raises stops collection by name
            # A generator is suite code, and a Scenario refuses non-JSON params with a TypeError:
            # every failure is the suite's, so it is a usage error naming the generator, never an
            # INTERNALERROR that reads as the plugin's (ADR 0074).
            raise pytest.UsageError(
                f"{self.path}: {case.name}: fixture generator {generator.name}: {type(exc).__name__}: {exc}"
            ) from exc
        if not scenarios and generator.may_be_empty:
            # ADR 0074: a regression case before its first promotion, or an adversary that found
            # nothing new, collects no cell -- and says so, so the silence is never mistaken for a pass.
            self.warn(pytest.PytestCollectionWarning(f"{case.name}: {generator.name} yielded no scenarios this sweep"))
            return []
        if not scenarios:
            raise pytest.UsageError(
                f"{self.path}: {case.name}: fixture generator {generator.name} yielded no scenarios; "
                "a case that generates nothing must fail loudly, not collect zero cells"
            )
        untasked = [s.id for s in scenarios if case.task is None and not s.task]
        if untasked:
            raise pytest.UsageError(
                f"{self.path}: {case.name}: declares no task= and these scenarios name none: {untasked}"
            )
        ids = [s.id for s in scenarios]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise pytest.UsageError(f"{self.path}: {case.name}: two scenarios share an id: {dupes}")
        for scenario in scenarios:
            store.write(scenario)
        return list(scenarios)

    def _require_catalogued(self, catalogue: Catalogue, case: EvalCase, cells: list[mx.Cell]) -> None:
        """Every cell's model is in the catalogue, or a usage error naming the line that would add it (ADR 0057).

        A record states the model's line, tier and release date so it stands alone once
        archived; a model the catalogue does not describe would ship records that cannot.
        """
        try:
            for cell in cells:
                spec = catalogue.require(cell.harness, cell.model)
                # ADR 0063: a rung the model ignores is a full run at its default, billed and
                # reported under a label it never had, so it stops here like an unknown rung does.
                if cell.effort and not spec.takes_effort:
                    raise CatalogueError(
                        f"{cell.id}: {cell.harness}/{cell.model} takes no effort rung (effort = false in the "
                        "model catalogue): its CLI accepts one and runs at the default anyway. Drop the rung "
                        "from the matrix entry (ADR 0063)"
                    )
        except CatalogueError as exc:
            raise pytest.UsageError(f"{self.path}: {case.name}: {exc}") from exc

    def _cases(self) -> list[EvalCase]:
        """Every case this suite declares, or a usage error naming what is wrong with it.

        A file that matched the layout and declares nothing is the failure mode this check
        exists for: it looks like an opt-in, and silently collecting zero cells from it
        would report a green sweep that graded nothing.
        """
        suite = EvalSuite.load(self.path)
        cases = suite.cases
        # ADR 0075: an analyzer narrowed to a case the suite does not declare would analyse
        # nothing and pass, so the name is checked here, before any cell spends.
        names = {c.name for c in cases}
        for spec in suite.analyzers:
            unknown = sorted(set(spec.cases or ()) - names)
            if unknown:
                raise pytest.UsageError(f"{self.path}: {spec.name} names cases this suite does not declare: {unknown}")
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


@dataclass(frozen=True, slots=True, kw_only=True)
class _Shared:
    """What every cell of one case shares, resolved once per case at collection."""

    case: EvalCase
    suite: str
    skill_dir: Path | None
    skill_files: tuple[skillcov.SkillFile, ...]
    version: str | None


class EvalItem(pytest.Item):
    """One cell: run the CLI in a fresh workspace, price it, capture evidence, grade.

    The item is the pytest-facing half of a cell -- its node id, its markers, how a failure
    reads -- and holds the :class:`~pytest_xharness_eval.runtime.plan.CellPlan` collection
    resolved for it. Running it is :class:`~pytest_xharness_eval.plugin.cell.CellRun`,
    which knows nothing about pytest beyond the stash it leaves its record in.
    """

    def __init__(self, *, plan: CellPlan, **kw: Any) -> None:
        super().__init__(**kw)
        self.plan = plan
        self.add_marker("eval")
        # Optional lever: `-n N --dist loadgroup` keeps one harness's cells on one worker
        # (parallel across harnesses, serial within one). Plain `-n N` is also fine.
        self.add_marker(pytest.mark.xdist_group(plan.cell.harness))

    def runtest(self) -> None:
        """Check the two directories a cell cannot run without, then run it -- or skip, unpaid.

        Both checks fail the cell even under ``--dry-run``: a sweep whose skill or fixture
        has been renamed must not report "would invoke" for a run that could not happen.
        """
        plan = self.plan
        if plan.skill_dir is not None and not plan.skill_dir.is_dir():
            raise harness.RunError(f"skill under test not found: {plan.skill_dir}")
        if not plan.fixture_dir.is_dir():
            raise harness.RunError(f"fixture directory not found: {plan.fixture_dir}")
        run = CellRun(plan=plan, settings=Settings.from_config(self.config))
        if self.config.option.eval_dry_run:
            self._precheck_free(run)
            self.stash[RECORD_KEY] = CellMetrics.dry_run(node=plan.node, cell=plan.cell)
            # The rendered invocation, not the case's task: since ADR 0044 the prompt is
            # harness-specific and no longer readable off the suite file, so a preview that
            # did not show it would no longer be a preview of what is about to be sent.
            pytest.skip(f"dry-run: would invoke {plan.cell.id} with {plan.prompt!r}")
        self._run_live(run)

    def _precheck_free(self, run: CellRun) -> None:
        """Under ``--dry-run``, materialise the seed, gate it with the case's precheck, and tidy it (ADR 0074).

        The same steps the live cell takes before it spends, so a dry run is a free check that
        every fixture still reproduces what its case is about.
        """
        if self.plan.case.precheck is None:
            return
        workspace = run.materialise()
        try:
            run.precheck(workspace)
        finally:
            ws.discard(workspace)

    def _run_live(self, run: CellRun) -> None:  # pragma: no cover - spends (ADR 0002)
        """The paid path: execute this cell's run.

        One statement, and everything under it is covered: each step of
        :class:`~pytest_xharness_eval.plugin.cell.CellRun` is exercised from captured logs
        in ``tests/plugin/test_cell.py``. What no test may reach is the CLI spawn inside
        :meth:`~pytest_xharness_eval.plugin.cell.CellRun.invoke`, and faking it is what ADR
        0002 forbids -- so the pragma stops here rather than covering the sequence too.
        """
        run.execute(self.stash)

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:  # type: ignore[override]
        return f"[{self.plan.cell.id}] {excinfo.getrepr(style='short')}"

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, 0, f"eval: {self.name}"
