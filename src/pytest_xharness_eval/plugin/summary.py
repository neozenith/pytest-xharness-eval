"""What a session leaves behind when its last cell has run (ADR 0032, ADR 0037).

Three things, in this order: the per-cell table on the terminal, ``report/report.json``
for this session, and -- only if this session actually wrote evidence -- the combine step
that rebuilds the browsable microsite over *every* run in the cache, not just this one.

The document is a :class:`~pytest_xharness_eval.emit.summary.RunSummary`, so this hook
decides when to write and where, never what the file contains. A session that graded no
cell writes nothing at all, which is what keeps the plugin silent in a repository that has
evals installed but did not run any.
"""

from __future__ import annotations

# Standard Library
from pathlib import Path
from typing import TYPE_CHECKING

# Our Libraries
from pytest_xharness_eval.emit import page
from pytest_xharness_eval.emit.summary import RunSummary
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.plugin.results import RESULTS_KEY
from pytest_xharness_eval.runtime.settings import Settings

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator

    # Third Party
    import pytest
    from _pytest.terminal import TerminalReporter

    # Our Libraries
    from pytest_xharness_eval.emit.metrics import CellMetrics


def cell_line(record: CellMetrics) -> str:
    """One cell's row of the terminal table: verdict, estimate, node id."""
    cost = f"${record.estimated_cost_usd:.4f}" if record.estimated_cost_usd is not None else "-"
    return f"  {record.verdict:<8} {cost:>9}  {record.node}"


def combine(summary: RunSummary, settings: Settings) -> Iterator[str]:
    """Run the combine step for every cache root this session wrote into; yield what to print.

    Aggregating is per *cache root*, not per cell: the step rebuilds one browsable report
    over everything under ``results/`` -- every skill, every run, not only this session's
    (ADR 0032). A session that wrote no evidence names no root and combines nothing, which
    is how ``--dry-run`` stays free.
    """
    for root in summary.cache_roots():
        cache = CacheLayout(Path(root))
        inline = settings.report_inline
        report_page = page.write(cache, design_tokens=settings.report_tokens, inline=inline)
        yield f"  aggregated report: {report_page}{' (inline, opens over file://)' if inline else ''}"
        if not inline:
            yield f"  serve it: {page.serve_hint(cache)}"


def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
    """Print one line per cell with its verdict and USD, write ``report.json``, then combine."""
    summary = RunSummary.of(config.stash.get(RESULTS_KEY, {}).values())
    if not summary.cells:
        return
    tr = terminalreporter
    tr.section("agent eval report")
    for record in summary.cells:
        tr.write_line(cell_line(record))
    tr.write_line(f"  total estimated spend: ${summary.total_usd:.4f} across {len(summary.cells)} cell(s)")

    settings = Settings.from_config(config)
    summary.write(settings.cache.summary)
    tr.write_line(f"  report: {settings.cache.summary}")
    for line in combine(summary, settings):
        tr.write_line(line)
