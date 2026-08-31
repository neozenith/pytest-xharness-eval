"""What a finished rollout is checked against: the shared verifiers, and goldens (ADR 0045, ADR 0046).

The sixth layer, between ``derive/`` and ``emit/``. It depends on ``model/`` and
``derive/`` and nothing else, and nothing beneath it may name it: a verifier *reads* a
finished rollout, it never participates in producing one. A ruff ``TID251`` rule fails the
build on either direction (ADR 0039).

Three modules, and the split is by what a suite is doing:

* ``checks`` -- named ``check_*`` verifiers over a :class:`CaseOutput`. Each returns when
  its claim holds and raises :class:`AssertionError` naming what went wrong when it does
  not. Start every case with :func:`~pytest_xharness_eval.verify.checks.check_rollout`.
* ``tolerance`` -- :class:`Facet` and the six :class:`Tolerance` kinds: how much a part of
  an answer may vary and still be correct.
* ``facets`` -- the markdown and mermaid extractors the shipped cases compare with.
* ``golden`` -- :class:`GoldenCase`, which puts the three together against a committed
  reference artifact.

Every name below is public API and versioned as such. A check whose assertion tightens is
a breaking change for the suites that import it, which is the correct pressure: a shared
gate that can be quietly loosened is worse than four copies of it.
"""

from __future__ import annotations

# Our Libraries
from pytest_xharness_eval.verify import facets as facets
from pytest_xharness_eval.verify.checks import (
    check_file_unchanged,
    check_files_written,
    check_no_files_added,
    check_rollout,
    check_run_is_priced,
    check_run_is_real,
    check_skill_scripts_ran,
    check_skill_was_loaded,
    check_subagents_spawned,
    check_tools_used,
    check_turns_within,
)
from pytest_xharness_eval.verify.golden import (
    GOLDENS_DIR,
    FacetDelta,
    GoldenCase,
    GoldenDelta,
    GoldenMismatch,
)
from pytest_xharness_eval.verify.tolerance import (
    Count,
    Exact,
    Facet,
    Jaccard,
    Ratio,
    Superset,
    Tolerance,
    Within,
)

__all__ = [
    "GOLDENS_DIR",
    "Count",
    "Exact",
    "Facet",
    "FacetDelta",
    "GoldenCase",
    "GoldenDelta",
    "GoldenMismatch",
    "Jaccard",
    "Ratio",
    "Superset",
    "Tolerance",
    "Within",
    "check_file_unchanged",
    "check_files_written",
    "check_no_files_added",
    "check_rollout",
    "check_run_is_priced",
    "check_run_is_real",
    "check_skill_scripts_ran",
    "check_skill_was_loaded",
    "check_subagents_spawned",
    "check_tools_used",
    "check_turns_within",
    "facets",
]
