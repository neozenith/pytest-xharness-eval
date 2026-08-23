"""The pytest plugin: collection, matrix expansion, options, per-cell run, report.

Registered through the ``pytest11`` entry point (ADR 0014), so installing the
package is the whole setup; no ``conftest.py`` or ``-p`` flag is needed.

Layout the plugin expects, relative to the pytest rootdir::

    <skills root>/<skill>/evals/eval_<suite>.py        # the suite: eval_* functions
    <skills root>/<skill>/evals/fixtures/<name>/       # seed workspaces, copied per cell
    <skills root>/<skill>/evals/captured/<case>/       # each run's log and result; git-ignore it
    <skills root>/<skill>/evals/captured/history.jsonl # one metrics line per live cell

Four ini options tune the paths and the project matrix; see ``pytest_addoption``.

Per-cell results travel on ``TestReport.user_properties`` (ADR 0016). That is the
one channel pytest-xdist serialises from a worker to the controller, so the verbose
status words and ``report.json`` are identical with and without ``-n``.
"""

from __future__ import annotations

# Standard Library
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import history
from pytest_xharness_eval import matrix as mx
from pytest_xharness_eval import pricing, report, runner, skillcov
from pytest_xharness_eval import workspace as ws
from pytest_xharness_eval.case import EvalCase

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Generator, Iterator, Mapping
    from types import ModuleType

    # Third Party
    from _pytest.terminal import TerminalReporter

INI_SKILLS_DIR = "xharness_skills_dir"
INI_WORKDIR = "xharness_workdir"
INI_PRICES = "xharness_prices"
INI_MATRIX = "xharness_matrix"
INI_SKILL_IGNORE = "xharness_skill_ignore"
INI_REPORT_TOKENS = "xharness_report_design_tokens"
INI_REPORT_INLINE = "xharness_report_inline"

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
        choices=list(mx.KNOWN_HARNESSES),
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
        INI_WORKDIR, default="tmp/evals", help="directory under rootdir for per-cell workspaces and report.json"
    )
    parser.addini(
        INI_PRICES,
        default="prices.toml",
        help="prices.toml under rootdir whose rows add to or override the bundled table",
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
    # ADR 0026: a malformed ignore line stops the session here, before any cell is collected.
    try:
        skillcov.patterns_for("", [str(p) for p in config.getini(INI_SKILL_IGNORE)])
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    config.pluginmanager.register(_ResultCollector(config), "xharness-eval-results")


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Show where cells are looked for and which matrix scope applies.

    A missing skills root is reported here rather than as a warning: the plugin is
    installed in environments that have no evals at all, and must stay silent there.
    """
    root = _skills_root(config)
    state = "" if root.is_dir() else " (missing: no eval cells will be collected)"
    project = _project_matrix(config)
    source = (
        f"{INI_MATRIX} ({len(project)} entries)" if project else f"plugin default ({len(mx.DEFAULT_MATRIX)} entries)"
    )
    return [
        f"xharness-eval: skills root = {root}{state}, workdir = {_workdir(config)}",
        f"xharness-eval: matrix = {source}; a case's models= overrides it",
    ]


def _skills_root(config: pytest.Config) -> Path:
    return (config.rootpath / str(config.getini(INI_SKILLS_DIR))).resolve()


def _workdir(config: pytest.Config) -> Path:
    return config.rootpath / str(config.getini(INI_WORKDIR))


def _price_table(config: pytest.Config) -> dict[str, pricing.Rates]:
    return pricing.load_table(overrides=config.rootpath / str(config.getini(INI_PRICES)))


def _project_matrix(config: pytest.Config) -> list[str]:
    return [str(entry).strip() for entry in config.getini(INI_MATRIX) if str(entry).strip()]


def _matrix_for(case: EvalCase, config: pytest.Config) -> list[str]:
    """Case > project ini > plugin default (ADR 0015)."""
    return case.models or _project_matrix(config) or list(mx.DEFAULT_MATRIX)


# -- collection (ADR 0008: eval_*.py files, eval_* functions, under <skills root>/*/evals/)


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.Collector | None:
    """Collect ``eval_*.py`` modules that sit in ``<skills root>/<skill>/evals/``."""
    if (
        file_path.suffix == ".py"
        and file_path.name.startswith("eval_")
        and file_path.parent.name == "evals"
        and file_path.parent.parent.parent.resolve() == _skills_root(parent.config)
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
        table = _price_table(self.config)
        opts = self.config.option
        for case in cases:
            models = _matrix_for(case, self.config)
            # ADR 0007: an unpriced model stops the sweep at collection, before any spend.
            pricing.validate_matrix(models, table)
            # ADR 0022: the skill's file tree is catalogued here, before any cell runs, so every
            # cell of the sweep is measured against the same inventory.
            skill_dir = _skills_root(self.config) / case.skill
            ignore = [str(p) for p in self.config.getini(INI_SKILL_IGNORE)]
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
    def captured_dir(self) -> Path:
        """``evals/captured/<case>/``: this case's logs and results, git-ignored."""
        return self.evals_dir / "captured" / self.case.name

    def runtest(self) -> None:
        skill_dir = _skills_root(self.config) / self.case.skill
        if not skill_dir.is_dir():
            raise runner.RunError(f"skill under test not found: {skill_dir}")
        if not self.fixture_dir.is_dir():
            raise runner.RunError(f"fixture directory not found: {self.fixture_dir}")

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

    def _run_live(self, skill_dir: Path) -> None:  # pragma: no cover - invokes a paid CLI (ADR 0002)
        cell_id = f"{self.case.name}-{self.cell.harness}-{self.cell.model}"
        workspace = ws.materialise(self.fixture_dir, cell_id, _workdir(self.config))

        started_at = history.now_iso()
        t0 = time.monotonic()
        result = runner.RUNNERS[self.cell.harness](
            prompt=self.case.prompt, model=self.cell.model, workspace=workspace, skill_dir=skill_dir
        )
        wall_ms = int((time.monotonic() - t0) * 1000)
        result = pricing.price(result, _price_table(self.config))
        result.skill_coverage = skillcov.annotate(self.case.skill, self.skill_files, result)
        # Which suite file and case produced this run, and the prompt it sent (ADR 0025).
        try:
            suite = str(self.path.relative_to(self.config.rootpath))
        except ValueError:
            suite = str(self.path)
        result.case = {
            "suite": suite,
            "name": self.case.name,
            "skill": self.case.skill,
            "fixture": self.case.fixture,
            "prompt": self.case.prompt,
        }

        # Never inside fixtures/: a fixture is copied into every workspace, so logs
        # placed there would leak into the next agent's cwd.
        self.captured_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{self.cell.harness}-{result.session_id}"
        (self.captured_dir / f"{stem}.jsonl").write_bytes(Path(result.session_log).read_bytes())
        result.write(self.captured_dir / f"{stem}.result.json")

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
            record = history.metrics_of(result, node=self.node, verdict=verdict, wall_ms=wall_ms, started_at=started_at)
            # Where this cell's evidence landed, so the controller can build the captured report (ADR 0020).
            record["captured"] = str(self.captured_dir.parent)
            self.stash[RECORD_KEY] = record
            history.append(self.captured_dir.parent / "history.jsonl", record)

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
    report_path = _workdir(config) / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"cells": results, "total_usd": round(total, 6)}, indent=2), encoding="utf-8")
    tr.write_line(f"  report: {report_path}")
    # One browsable report per captured/ directory a live cell wrote into (ADR 0020, 0024).
    tokens_opt = config.option.xharness_report_design_tokens or str(config.getini(INI_REPORT_TOKENS) or "")
    tokens = (config.rootpath / tokens_opt) if tokens_opt else None
    inline = bool(config.option.xharness_report_inline or config.getini(INI_REPORT_INLINE))
    for captured in sorted({str(r["captured"]) for r in results if r.get("captured")}):
        page = report.write(Path(captured), design_tokens=tokens, inline=inline)
        tr.write_line(f"  captured report: {page}{' (inline, opens over file://)' if inline else ''}")
        if not inline:
            tr.write_line(f"  serve it: {report.serve_hint(Path(captured))}")
