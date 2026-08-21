# 0015: Harness is the axis name, and the project owns the default matrix

Status: accepted, 2026-08-21. Refines
[0010](0010-matrix-options-and-dry-run.md).

## Context

The first design named the first matrix axis "cli" (`--cli`, `Cell.cli`, `RunResult.cli`),
while the package is named for cross-*harness* evaluation. Two words for one axis
is the kind of drift the vocabulary table exists to prevent. Separately, the only
way to change a repository's sweep was to edit the plugin's `DEFAULT_MATRIX` or to
repeat `models=` on every case; there was no project scope between the two.

Visibility was also thin: a six-cell sweep printed as dots, and the verbose line
said only `PASSED`, hiding the cost that had just been incurred.

## Decision

The axis is called **harness** everywhere: the `--harness` option, `Cell.harness`,
`RunResult.harness`, `KNOWN_HARNESSES`, and the `harness` key in `report.json`.
Matrix entries stay `harness/model`.

The matrix has three scopes, highest precedence first: a case's `models=`, the
project's `xharness_matrix` ini key, and the plugin's `DEFAULT_MATRIX`. A case that
omits `models=` inherits; `EvalCase.models` is `None` in that state so inheritance
is distinguishable from an explicit choice.

Two hooks carry the itemised view inside ordinary pytest output. Before the first
cell runs, `pytest_report_collectionfinish` lists every permutation grouped by case.
As each cell lands, `pytest_report_teststatus` replaces the verbose status word with
the verdict, USD, token count, and duration, and shows `DRY-RUN` for a dry-run skip.

## Consequences

Captured `.result.json` files written before this change carry a `cli` key; they are
git-ignored run artefacts and are not migrated. Consumers see `--cli` rejected as an
unknown option, which is the loud failure wanted. The report header names which
matrix scope applied, so a surprising cell count is diagnosable from the first two
lines of output. A pivot report was considered and deferred: the requirement was
visibility inside pytest's own output, not a second report.

## Lens

Name an axis once, in the word the package is named for, and give every
configurable default a project scope between the case and the plugin.
