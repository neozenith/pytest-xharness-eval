"""The pytest plugin: collection, matrix expansion, options, per-cell run, report.

Registered through the ``pytest11`` entry point (ADR 0014), so installing the
package is the whole setup; no ``conftest.py`` or ``-p`` flag is needed.

Layout the plugin expects, relative to the pytest rootdir::

    <skills root>/<skill>/evals/eval_<suite>.py    # the suite: eval_* functions
    <skills root>/<skill>/evals/fixtures/<name>/   # seed workspaces, copied per cell

Every run output consolidates under one git-ignored cache root (ADR 0032)::

    <cache>/build/                                             # per-cell workspaces
    <cache>/results/{skill}/{harness}/{model}/{run}/{session}/ # log.jsonl, result.json, history.json
    <cache>/report/                                            # report.json + the aggregated microsite

A cell writes only inside its own ``{run}/{session}/`` directory, so parallel
workers never contend; the report step at session end is the one combine step.
Ini options tune the paths and the project matrix; see ``pytest_addoption``.

Per-cell results travel on ``TestReport.user_properties`` (ADR 0016). That is the
one channel pytest-xdist serialises from a worker to the controller, so the verbose
status words and ``report.json`` are identical with and without ``-n``.
"""

from __future__ import annotations

# Standard Library
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import harness, history
from pytest_xharness_eval import matrix as mx
from pytest_xharness_eval import pipeline, pricing, report, skillcov
from pytest_xharness_eval import workspace as ws
from pytest_xharness_eval.case import EvalCase
from pytest_xharness_eval.settings import (
    INI_CACHE_DIR,
    INI_MATRIX,
    INI_PRICES,
    INI_REPORT_INLINE,
    INI_REPORT_TOKENS,
    INI_SKILL_IGNORE,
    INI_SKILLS_DIR,
    Settings,
)

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Generator, Iterator, Mapping
    from types import ModuleType

    # Third Party
    from _pytest.terminal import TerminalReporter


# The user_properties key a cell's record travels under, worker to controller.
PROPERTY = "xharness_eval"

# One record per cell, keyed by node id, in the order their call reports arrived.
RESULTS_KEY: pytest.StashKey[dict[str, dict[str, Any]]] = pytest.StashKey()
# The record an EvalItem produced, attached to the item until its call report is made.
RECORD_KEY: pytest.StashKey[dict[str, Any]] = pytest.StashKey()


# -- options -------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the matrix-narrowing options and the layout / matrix ini keys."""
    g = parser.getgroup("xharness-eval", "cross-harness agent CLI evals (always live, always paid)")
    g.addoption(
        "--harness",
        action="append",
        default=None,
        choices=list(mx.known_harnesses()),
        help="narrow the matrix to one harness (repeatable)",
    )
    g.addoption(
        "--model",
        action="append",
        default=None,
        metavar="SUBSTRING",
        help="narrow the matrix to models containing this string, or to one exact harness/model cell (repeatable)",
    )
    g.addoption(
        "--dry-run",
        action="store_true",
        dest="eval_dry_run",
        help="enumerate cells and validate pricing without invoking any CLI",
    )
    parser.addini(INI_SKILLS_DIR, default="skills", help="directory under rootdir holding <skill>/evals/ trees")
    parser.addini(
        INI_CACHE_DIR,
        default=".xharness_eval_cache",
        help="git-ignored root under rootdir for build workspaces, results and the report (ADR 0032)",
    )
    parser.addini(
        INI_PRICES,
        type="linelist",
        default=[],
        help=(
            "price rows that add to or override the bundled table: "
            "'<model>: input=<usd/MTok> output=<usd/MTok> [cache_read=..] [cache_write=..] [cache_write_1h=..]'"
        ),
    )
    parser.addini(
        INI_MATRIX,
        type="linelist",
        default=[],
        help="project matrix: harness/model entries, one per line; a case's models= overrides it",
    )
    g.addoption(
        "--xharness-report-design-tokens",
        dest="xharness_report_design_tokens",
        default=None,
        metavar="FILE",
        help="design tokens JSON that themes captured/report.html (overrides the ini key)",
    )
    g.addoption(
        "--xharness-report-inline",
        dest="xharness_report_inline",
        action="store_true",
        default=False,
        help="write captured/report.html with every result, log and the tokens embedded (opens over file://)",
    )
    parser.addini(
        INI_REPORT_TOKENS, default="", help="design tokens JSON for captured/report.html, relative to rootdir"
    )
    parser.addini(INI_REPORT_INLINE, type="bool", default=False, help="embed all data into captured/report.html")
    parser.addini(
        INI_SKILL_IGNORE,
        type="linelist",
        default=[],
        help=(
            "gitignore-style patterns for skill files that are not part of the decision surface; "
            "a bare pattern applies to every skill, '<skill>: <pattern>' to the skills matching the selector"
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register markers and the per-session result registry."""
    config.addinivalue_line("markers", "eval: paid agent eval cell (always live, ADR 0002)")
    # xdist registers this itself when installed; registering again is harmless and keeps
    # --strict-markers happy when it is not.
    config.addinivalue_line("markers", "xdist_group(name): cells of one harness share a worker under --dist loadgroup")
    config.stash[RESULTS_KEY] = {}
    # One UTC stamp per pytest session, path-safe and sortable; the env var makes xdist
    # workers (child processes) agree with the controller, so a run's cells share one
    # results/{...}/{run}/ directory level and repeated runs accumulate (ADR 0032).
    os.environ.setdefault("XHARNESS_EVAL_RUN_TS", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    # ADR 0026 / ADR 0030: a malformed ignore or price line stops the session here,
    # before any cell is collected.
    try:
        skillcov.patterns_for("", [str(p) for p in config.getini(INI_SKILL_IGNORE)])
        pricing.parse_price_lines([str(line) for line in config.getini(INI_PRICES)])
    except (ValueError, pricing.PricingError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    config.pluginmanager.register(_ResultCollector(config), "xharness-eval-results")


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Show where cells are looked for and which matrix scope applies.

    A missing skills root is reported here rather than as a warning: the plugin is
    installed in environments that have no evals at all, and must stay silent there.
    """
    settings = _settings(config)
    root = settings.skills_root
    state = "" if root.is_dir() else " (missing: no eval cells will be collected)"
    project = settings.matrix_lines
    source = (
        f"{INI_MATRIX} ({len(project)} entries)" if project else f"plugin default ({len(mx.DEFAULT_MATRIX)} entries)"
    )
    return [
        f"xharness-eval: skills root = {root}{state}, cache = {settings.cache_dir}",
        f"xharness-eval: matrix = {source}; a case's models= overrides it",
    ]


def _settings(config: pytest.Config) -> Settings:
    """This session's resolved configuration; the replay path builds the same object."""
    return Settings.from_config(config)


def _run_ts() -> str:
    return os.environ.get("XHARNESS_EVAL_RUN_TS") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


# -- collection (ADR 0008: eval_*.py files, eval_* functions, under <skills root>/*/evals/)


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.Collector | None:
    """Collect ``eval_*.py`` modules that sit in ``<skills root>/<skill>/evals/``."""
    if (
        file_path.suffix == ".py"
        and file_path.name.startswith("eval_")
        and file_path.parent.name == "evals"
        and file_path.parent.parent.parent.resolve() == _settings(parent.config).skills_root
    ):
        return EvalFile.from_parent(parent, path=file_path)
    return None


def _load_module(path: Path) -> ModuleType:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    name = f"_xharness_eval_{path.stem}_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load eval module {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # import errors propagate loudly
    return mod


class EvalFile(pytest.File):
    """One ``eval_*.py`` suite; yields one item per (case, cell)."""

    def collect(self) -> Iterator[pytest.Item]:
        mod = _load_module(self.path)
        cases = [v for v in vars(mod).values() if isinstance(v, EvalCase)]
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
        settings = _settings(self.config)
        table = settings.price_table()
        opts = self.config.option
        for case in cases:
            models = settings.matrix_for(case)
            # ADR 0007: an unpriced model stops the sweep at collection, before any spend.
            pricing.validate_matrix(models, table)
            # ADR 0022: the skill's file tree is catalogued here, before any cell runs, so every
            # cell of the sweep is measured against the same inventory.
            skill_dir = settings.skill_dir(case.skill)
            ignore = settings.skill_ignore
            files = skillcov.catalog(skill_dir, ignore=ignore) if skill_dir.is_dir() else []
            for cell in mx.narrow(mx.expand(models), opts.model, opts.harness):
                yield EvalItem.from_parent(
                    self, name=f"{case.name}[{cell.id}]", case=case, cell=cell, skill_files=files
                )


class EvalItem(pytest.Item):
    """One cell: run the CLI in a fresh workspace, price it, capture evidence, grade."""

    def __init__(
        self, *, case: EvalCase, cell: mx.Cell, skill_files: list[dict[str, Any]] | None = None, **kw: Any
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
    def results_dir(self) -> Path:
        """``<cache>/results/{skill}/{harness}/{model}/{run}/``: a per-session dir under it holds the evidence."""
        root = _settings(self.config).results_root()
        return root / self.case.skill / self.cell.harness / self.cell.model / _run_ts()

    def runtest(self) -> None:
        skill_dir = _settings(self.config).skill_dir(self.case.skill)
        if not skill_dir.is_dir():
            raise harness.RunError(f"skill under test not found: {skill_dir}")
        if not self.fixture_dir.is_dir():
            raise harness.RunError(f"fixture directory not found: {self.fixture_dir}")

        if self.config.option.eval_dry_run:
            self.stash[RECORD_KEY] = {
                "node": self.node,
                "harness": self.cell.harness,
                "model": self.cell.model,
                "verdict": "dry-run",
                "estimated_cost_usd": None,
            }
            pytest.skip(f"dry-run: would invoke {self.cell.id}")

        self._run_live(skill_dir)

    @property
    def suite(self) -> str:
        """This suite file, relative to the project root when it is under one (ADR 0025)."""
        try:
            return str(self.path.relative_to(self.config.rootpath))
        except ValueError:
            return str(self.path)

    def _run_live(self, skill_dir: Path) -> None:  # pragma: no cover - invokes a paid CLI (ADR 0002)
        cell_id = f"{self.case.name}-{self.cell.harness}-{self.cell.model}"
        settings = _settings(self.config)
        workspace = ws.materialise(self.fixture_dir, cell_id, settings.cache_dir / "build")

        started_at = history.now_iso()
        t0 = time.monotonic()
        result = harness.get(self.cell.harness).run(
            prompt=self.case.prompt, model=self.cell.model, workspace=workspace, skill_dir=skill_dir
        )
        wall_ms = int((time.monotonic() - t0) * 1000)

        # Everything from here is the same sequence a replay runs, in the same order.
        pipeline.derive(
            result,
            table=settings.price_table(),
            skill=self.case.skill,
            skill_files=self.skill_files,
            case=pipeline.case_record(self.case, self.suite),
        )
        session_dir = pipeline.capture(result, self.results_dir / result.session_id)

        verdict = "pass"
        try:
            self.case.fn(result, workspace)
        except AssertionError:
            verdict = "fail"
            raise
        except Exception:
            verdict = "error"
            raise
        finally:
            self.stash[RECORD_KEY] = pipeline.record_metrics(
                result,
                session_dir,
                node=self.node,
                verdict=verdict,
                wall_ms=wall_ms,
                started_at=started_at,
                cache=settings.cache_dir,
            )

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:  # type: ignore[override]
        return f"[{self.cell.id}] {excinfo.getrepr(style='short')}"

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, 0, f"eval: {self.name}"


# -- results travel on the report (ADR 0016) -----------------------------------


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, Any]:
    """Worker side: put the cell's record on its call report so it survives xdist and reaches JUnit."""
    report = yield
    if call.when == "call" and isinstance(item, EvalItem) and RECORD_KEY in item.stash:
        record = item.stash[RECORD_KEY]
        props: list[tuple[str, object]] = [(PROPERTY, record)]
        # Flat scalars as their own properties, so --junitxml carries the metrics history too.
        props.extend((f"xharness_{k}", v) for k, v in record.items() if isinstance(v, str | int | float))
        # The call report is what xdist ships to the controller; the item's list is what
        # pytest copies onto the teardown report, which is where junitxml reads properties.
        report.user_properties.extend(props)
        item.user_properties.extend(props)
    return report


def _record_of(report: pytest.TestReport) -> dict[str, Any] | None:
    for name, value in report.user_properties:
        if name == PROPERTY and isinstance(value, dict):
            return value
    return None


class _ResultCollector:
    """Controller side (and single-process): gather records as call reports arrive."""

    def __init__(self, config: pytest.Config) -> None:
        self.config = config

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when != "call":
            return
        record = _record_of(report)
        if record is not None:
            self.config.stash[RESULTS_KEY][report.nodeid] = record


# -- visibility: the verdict per cell as it lands --------------------------------


def pytest_report_teststatus(
    report: pytest.CollectReport | pytest.TestReport, config: pytest.Config
) -> tuple[str, str, str | tuple[str, Mapping[str, bool]]] | None:
    """Replace the verbose status word of an eval cell with its verdict and metrics."""
    if not isinstance(report, pytest.TestReport) or report.when != "call":
        return None
    record = _record_of(report)
    if record is None:
        return None
    if record["verdict"] == "dry-run":
        return ("skipped", "s", ("DRY-RUN", {"yellow": True}))
    detail = history.status_word(record)
    if record["verdict"] == "pass":
        return ("passed", ".", (f"PASSED  {detail}", {"green": True}))
    letter = "F" if record["verdict"] == "fail" else "E"
    return ("failed", letter, (f"{record['verdict'].upper()}  {detail}", {"red": True}))


# -- report: matrix x verdict x USD --------------------------------------------


def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
    """Print one line per cell with its verdict and USD, and write ``report.json``."""
    results = list(config.stash.get(RESULTS_KEY, {}).values())
    if not results:
        return
    tr = terminalreporter
    total = sum(r.get("estimated_cost_usd") or 0.0 for r in results)
    tr.section("agent eval report")
    for r in results:
        cost = f"${r['estimated_cost_usd']:.4f}" if r.get("estimated_cost_usd") is not None else "-"
        tr.write_line(f"  {r['verdict']:<8} {cost:>9}  {r['node']}")
    tr.write_line(f"  total estimated spend: ${total:.4f} across {len(results)} cell(s)")
    settings = _settings(config)
    report_path = settings.cache_dir / "report" / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"cells": results, "total_usd": round(total, 6)}, indent=2), encoding="utf-8")
    tr.write_line(f"  report: {report_path}")
    # The one combine step (ADR 0032): aggregate everything under results/ - every skill,
    # every run - into one browsable report, when this run wrote any evidence.
    tokens, inline = settings.report_tokens, settings.report_inline
    for cache in sorted({str(r["cache"]) for r in results if r.get("cache")}):
        page = report.write(Path(cache), design_tokens=tokens, inline=inline)
        tr.write_line(f"  aggregated report: {page}{' (inline, opens over file://)' if inline else ''}")
        if not inline:
            tr.write_line(f"  serve it: {report.serve_hint(Path(cache))}")
