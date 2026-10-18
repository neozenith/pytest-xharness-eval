"""What a finished rollout is checked against: the shared verifiers, and goldens (ADR 0045, ADR 0046).

The sixth layer, between ``derive/`` and ``emit/``. It depends on ``model/`` and
``derive/`` and nothing else, and nothing beneath it may name it: a verifier *reads* a
finished rollout, it never participates in producing one. A ruff ``TID251`` rule fails the
build on either direction (ADR 0039).

The modules split by what a suite is doing:

* ``checks`` -- named ``check_*`` verifiers over a :class:`CaseOutput`. Each returns when
  its claim holds and raises :class:`AssertionError` naming what went wrong when it does
  not. Start every case with :func:`~pytest_xharness_eval.verify.checks.check_rollout`.
* ``conduct`` -- budgets and behaviours over the run's measured fields: cost, wall
  clock, context, compaction, cache share, tool calls and their timing and cost, the
  commands it ran, the skill's trigger and cost, and its subagents.
* ``content`` -- the agent's file against its seed: content kept, length kept, nothing
  hidden in code, no fence or id removed, a pattern gone or present.
* ``tool`` -- the tool under test run on the workspace (:func:`run_tool`), its findings,
  and the precondition that the seed still fails it. A tool that cannot run raises
  :class:`RuntimeError`, which grades ``error``, never ``fail``.
* ``combine`` -- :func:`check_all`, which runs many checkers and reports every failure.
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
from pytest_xharness_eval.verify.combine import Checker, check_all
from pytest_xharness_eval.verify.conduct import (
    check_cache_efficiency,
    check_commands_ran,
    check_context_within,
    check_cost_within,
    check_no_compaction,
    check_no_long_context,
    check_no_timeout,
    check_skill_cost_within,
    check_skill_triggered,
    check_subagent_cost_within,
    check_subagent_durations_within,
    check_subagents_within,
    check_tool_calls_within,
    check_tool_cost_within,
    check_tool_durations_within,
    check_wall_within,
)
from pytest_xharness_eval.verify.content import (
    check_absent,
    check_content_kept,
    check_fences_kept,
    check_ids_kept,
    check_length_kept,
    check_matches,
    check_nothing_hidden,
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
from pytest_xharness_eval.verify.tool import (
    ToolRun,
    check_tool_clean,
    check_tool_passes,
    findings,
    require_seed_fails,
    run_tool,
    scratch_dir,
)

__all__ = [
    "GOLDENS_DIR",
    "Checker",
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
    "ToolRun",
    "Within",
    "check_absent",
    "check_all",
    "check_cache_efficiency",
    "check_commands_ran",
    "check_content_kept",
    "check_context_within",
    "check_cost_within",
    "check_fences_kept",
    "check_file_unchanged",
    "check_files_written",
    "check_ids_kept",
    "check_length_kept",
    "check_matches",
    "check_no_compaction",
    "check_no_files_added",
    "check_no_long_context",
    "check_no_timeout",
    "check_nothing_hidden",
    "check_rollout",
    "check_run_is_priced",
    "check_run_is_real",
    "check_skill_cost_within",
    "check_skill_scripts_ran",
    "check_skill_triggered",
    "check_skill_was_loaded",
    "check_subagent_cost_within",
    "check_subagent_durations_within",
    "check_subagents_spawned",
    "check_subagents_within",
    "check_tool_calls_within",
    "check_tool_clean",
    "check_tool_cost_within",
    "check_tool_durations_within",
    "check_tool_passes",
    "check_tools_used",
    "check_turns_within",
    "check_wall_within",
    "facets",
    "findings",
    "require_seed_fails",
    "run_tool",
    "scratch_dir",
]
