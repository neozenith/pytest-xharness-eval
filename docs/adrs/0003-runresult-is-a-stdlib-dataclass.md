# 0003: RunResult is a stdlib dataclass serialised to JSON

Status: accepted, 2026-08-20; JSON Schema file not yet written.

## Context

Two adapters produce one record. Without a shared contract their shapes drift and
parity becomes an assertion nobody can check. Pydantic would validate but adds a
dependency to a harness whose brief is minimal.

## Decision

`RunResult` is a `dataclasses.dataclass` serialised to flat JSON, with a committed
`runresult.schema.json` that both adapters validate against.

## Consequences

The plugin has no runtime dependency beyond pytest. The schema is the single
source of truth for parity. Until the schema file ships, parity rests on both
adapters returning the same dataclass, which the type checker enforces but a
mismatched JSON artefact would not reveal.

## Lens

Prefer a committed schema over a validation library; a schema is diffable and
language-neutral, and it costs nothing at runtime.
