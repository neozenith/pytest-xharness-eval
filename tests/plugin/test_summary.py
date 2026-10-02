"""``plugin.summary``: the terminal summary hook and when the combine step runs (ADR 0040)."""

# Standard Library
import dataclasses
from pathlib import Path

# Our Libraries
from pytest_xharness_eval import (
    Cell,
    Usage,
)
from pytest_xharness_eval.emit.metrics import CellMetrics
from pytest_xharness_eval.emit.summary import RunSummary
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.plugin import summary as plugin_summary
from pytest_xharness_eval.runtime import settings
from tests.support import _metrics, _result


def test_the_terminal_line_shows_the_estimate_or_a_dash_when_a_cell_has_none() -> None:
    priced = _result("claude-opus-5", Usage(10, 20))
    priced.estimated_cost_usd = 1.5
    assert plugin_summary.cell_line(_metrics(priced, node="n1")) == "  pass       $1.5000  n1"
    dry = CellMetrics.dry_run(node="n2", cell=Cell(harness="claude", model="claude-opus-5"))
    assert plugin_summary.cell_line(dry) == "  dry-run          -  n2"


def test_the_combine_step_runs_once_per_cache_root_the_session_wrote_into(tmp_path: Path) -> None:
    """The step aggregates every run in the cache, not this session's cells (ADR 0032)."""
    cache = CacheLayout(tmp_path / ".xharness_eval_cache")
    session = cache.session(
        skill="demo", harness="claude", model="claude-opus-5", run="20261028T000000Z", session="sid1"
    )
    session.mkdir()
    result = _result("claude-opus-5", Usage(10, 20))
    result.session_id = "sid1"
    result.write(session.result)
    record = _metrics(result, cache=str(cache.root))
    record.write(session.history)
    project = settings.Settings(rootpath=tmp_path, skills_root=tmp_path, cache=cache)

    lines = list(plugin_summary.combine(RunSummary.of([record]), project))

    assert cache.page.is_file() and cache.index.is_file()
    assert lines[0] == f"  aggregated report: {cache.page}"
    assert "python3 -m http.server" in lines[1]
    # A record that names no cache root combines nothing at all.
    homeless = dataclasses.replace(record, cache="")
    assert list(plugin_summary.combine(RunSummary.of([homeless]), project)) == []
