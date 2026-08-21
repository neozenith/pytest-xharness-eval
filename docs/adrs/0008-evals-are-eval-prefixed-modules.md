# 0008: Evals are `eval_*.py` modules collected by a directory-scoped hook

Status: accepted, 2026-08-20. Refined by
[0016](0016-results-travel-on-the-test-report.md): the `eval_` prefix also applies
to case functions. The `skills/` root is now the `xharness_skills_dir` ini key
([0014](0014-register-through-the-pytest11-entry-point.md)).

## Context

Paid eval cells must never be triggered by an ordinary unit-test run. pytest's
`python_files` option is a single rootdir-level setting, so changing it to
`eval_*.py` would stop `test_*.py` collecting across the whole repository.

## Decision

An eval case is a Python module named `eval_*.py` under `skills/<skill>/evals/`,
beside its `fixture/` and `captured/` directories. The plugin collects it through
its own `pytest_collect_file` hook scoped to that path shape. `python_files` is
left at its default.

## Consequences

The `eval_*` prefix separates paid cells from unit tests by name. Because a case
is an executable module, custom verifiers are ordinary functions and need no
second mechanism (ADR 0013). A directory that matches the layout but defines no
case fails collection loudly rather than contributing zero cells.

## Lens

Separate paid work from free work by collection scope and name, never by a skip
marker that exits green.
