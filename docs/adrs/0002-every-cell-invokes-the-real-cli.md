# 0002: Every eval cell always invokes the real CLI

Status: accepted, 2026-08-20. Inside this package the boundary is the
`pragma: no cover` on every function that spawns a CLI
([0014](0014-register-through-the-pytest11-entry-point.md)).

## Context

Two project rules appeared to conflict: tests never mock, and paid agent runs are
never a dependency of the free `ci` target. A record-and-replay tier was the first
idea for reconciling them.

## Decision

There is no replay layer, no recorded-fixture tier, and no `--live` flag. A cell
always runs the real `claude` or `codex` process and always costs money. The eval
suite is a declared exception to the `ci` rule, recorded as a carve-out in the
consuming project's rules. The free `ci` target covers only `test_*.py` unit tests.

## Consequences

The only signal the harness produces is real agent behaviour; a cell that did not
invoke an agent has measured nothing. The rules are reconciled by scoping, not by
recording: unit tests are free and mock-free, evals are paid and mock-free. Every
sweep spends money, so the matrix became an explicit spend dial (ADR 0010).

## Lens

Never let a cell report a verdict without a real session log behind it. If a run
cannot be real, fail the cell; do not fake it.
