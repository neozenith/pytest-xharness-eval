"""The pytest plugin: the hook manifest, and the five modules the hooks live in.

Registered through the ``pytest11`` entry point (ADR 0014), so installing the package is
the whole setup; no ``conftest.py`` or ``-p`` flag is needed.

Layout the plugin expects, relative to the pytest rootdir::

    <skills root>/<skill>/evals/eval_<suite>.py    # the suite: eval_* functions
    <skills root>/<skill>/evals/fixtures/<name>/   # seed workspaces, copied per cell

Every run output consolidates under one git-ignored cache root (ADR 0032)::

    <cache>/build/                                             # per-cell workspaces
    <cache>/results/{skill}/{harness}/{model}/{run}/{session}/ # log.jsonl, result.json, history.json
    <cache>/report/                                            # report.json + the aggregated microsite

A cell writes only inside its own ``{run}/{session}/`` directory, so parallel workers never
contend; the report step at session end is the one combine step. Ini options tune the paths
and the project matrix; see :func:`pytest_addoption`.

**This file is a manifest and nothing else.** Pluggy discovers a hook as an attribute of
the imported plugin module, and importlib resolves ``pytest_xharness_eval.plugin`` to this
package, so every hook is bound here and implemented in the module that owns that job
(ADR 0040):

* :mod:`.options` -- every option and ini key, what configure validates before collection,
  and the header (ADR 0010, ADR 0026, ADR 0030).
* :mod:`.collect` -- which files are eval suites, and the :class:`EvalItem` one cell is
  (ADR 0008).
* :mod:`.cell` -- the seven steps of a live cell, of which one spends money (ADR 0002).
* :mod:`.results` -- the record's one crossing to the xdist controller, and its status word
  (ADR 0016).
* :mod:`.summary` -- the terminal table, ``report.json``, and the combine step (ADR 0032).

What is bound here is the seven hooks pluggy calls, and the four names a consuming
repository's ``conftest.py`` already reaches for -- :class:`EvalFile`, :class:`EvalItem`
and the three keys a cell's record travels under. Everything else stays addressable where
it is implemented (``plugin.cell.CellRun``, ``plugin.results.ResultCollector``): a
manifest that re-exports internals is an API surface, not a manifest (ADR 0041).
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.plugin.collect import EvalFile, EvalItem, pytest_collect_file
from pytest_xharness_eval.plugin.options import pytest_addoption, pytest_configure, pytest_report_header
from pytest_xharness_eval.plugin.results import (
    PROPERTY,
    RECORD_KEY,
    RESULTS_KEY,
    pytest_report_teststatus,
    pytest_runtest_makereport,
)
from pytest_xharness_eval.plugin.summary import pytest_terminal_summary

__all__ = [
    "PROPERTY",
    "RECORD_KEY",
    "RESULTS_KEY",
    "EvalFile",
    "EvalItem",
    "pytest_addoption",
    "pytest_collect_file",
    "pytest_configure",
    "pytest_report_header",
    "pytest_report_teststatus",
    "pytest_runtest_makereport",
    "pytest_terminal_summary",
]
