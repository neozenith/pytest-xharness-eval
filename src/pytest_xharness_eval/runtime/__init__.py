"""How a sweep is wired: where its configuration comes from, and what happens to a run.

The top layer below the two entry points. It knows every layer beneath it and is known by
none of them (the ruff layer rule in ``pyproject.toml`` says so), which is what lets a live
cell and a replay share one definition of "the settings" and one definition of "the steps
after the CLI returns" instead of two that drift (ADR 0034).

* :mod:`.settings` -- one resolved view of a project's ini keys, built either from the
  live :class:`pytest.Config` or from disk the way pytest finds its rootdir
  (ADR 0014, ADR 0026, ADR 0030).
* :mod:`.pipeline` -- price, annotate coverage, name the case, capture the evidence,
  record the metrics: the sequence both paths run, in one order.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.runtime.pipeline import capture, capture_subagents, derive, record_metrics
from pytest_xharness_eval.runtime.settings import (
    DEFAULT_CACHE_DIR,
    DEFAULT_SKILLS_DIR,
    INI_CACHE_DIR,
    INI_MATRIX,
    INI_PRICES,
    INI_REPORT_INLINE,
    INI_REPORT_TOKENS,
    INI_SKILL_IGNORE,
    INI_SKILLS_DIR,
    Settings,
    find_rootpath,
    ini_lines,
    ini_value,
)

__all__ = [
    "DEFAULT_CACHE_DIR",
    "DEFAULT_SKILLS_DIR",
    "INI_CACHE_DIR",
    "INI_MATRIX",
    "INI_PRICES",
    "INI_REPORT_INLINE",
    "INI_REPORT_TOKENS",
    "INI_SKILLS_DIR",
    "INI_SKILL_IGNORE",
    "Settings",
    "capture",
    "capture_subagents",
    "derive",
    "find_rootpath",
    "ini_lines",
    "ini_value",
    "record_metrics",
]
