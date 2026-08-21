# 0007: An unpriced model aborts at matrix expansion and never prices as zero

Status: accepted, 2026-08-20.

## Context

A model missing from the price table could be priced at zero with a warning,
recorded as `null`, or treated as an error. Zero makes an expensive sweep look
free; `null` pushes the obligation onto every consumer of the report.

## Decision

Price coverage is validated when the matrix expands, before any cell runs. An
unpriced model stops the sweep with the model named. `--dry-run` surfaces the
same gap without spending.

## Consequences

A new model blocks a sweep until a row is added, which is the intended friction.
The failure lands before money is spent, so fail-loud costs nothing here.

## Lens

Validate anything that gates spend before the first paid call, and make the
failure name the fix.
