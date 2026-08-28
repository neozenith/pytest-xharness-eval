"""The documents that leave: what a graded cell emits, and the microsite over all of them.

Everything a run says to the outside world is written here, and every field name in this
layer is a wire format: ``report-ui/src/lib/types.ts`` mirrors them and
``tests/test_units.py`` pins the key sets, so a rename in this package is a contract
change (ADR 0021, ADR 0039).

* :mod:`.metrics` -- ``history.json``: one :class:`CellMetrics` per graded cell, the
  record that also crosses the xdist boundary as a plain mapping (ADR 0016, ADR 0018).
* :mod:`.index` -- ``report/index.json``: one :class:`IndexRow` per captured session.
* :mod:`.summary` -- ``report/report.json``: the cells one pytest session graded and the
  spend they add up to, as a :class:`RunSummary` (ADR 0040).
* :mod:`.tokens` -- ``report/report.tokens.json``: the design tokens the page is themed
  with (ADR 0024).
* :mod:`.page` -- the combine step that assembles all of it into ``<cache>/report/``
  (ADR 0020, ADR 0032).

This file is that surface. The root package re-exports it as ``report``, which is the name
``report-ui/scripts/inline.py`` builds a page through, so the three
:mod:`~pytest_xharness_eval.model.layout` names that script needs to find a cache's index
are re-exported here as well.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.emit.index import IndexRow, aggregate_history, cells
from pytest_xharness_eval.emit.metrics import CellMetrics, Outcome
from pytest_xharness_eval.emit.page import INLINE_MARKER, inline_page, serve_hint, write
from pytest_xharness_eval.emit.summary import RunSummary
from pytest_xharness_eval.emit.tokens import load_tokens
from pytest_xharness_eval.model.layout import INDEX_NAME, REPORT_DIR, TOKENS_NAME

__all__ = [
    "INDEX_NAME",
    "INLINE_MARKER",
    "REPORT_DIR",
    "TOKENS_NAME",
    "CellMetrics",
    "IndexRow",
    "Outcome",
    "RunSummary",
    "aggregate_history",
    "cells",
    "inline_page",
    "load_tokens",
    "serve_hint",
    "write",
]
