# 0013: Custom verifiers are Python modules beside the case

Status: accepted, 2026-08-21; dynamic import helper not yet built.

## Context

Skills need checks the plugin did not anticipate. A shell command per verifier is
portable but loses structured detail on failure. Declarative assertions in a
manifest only cover checks anticipated when the schema was written.

## Decision

A verifier is a plain Python callable. It lives in `skills/<skill>/evals/`, is
versioned with the cases that use it, and is imported by the case module like any
other code. A verifier that fails to import fails the case loudly.

## Consequences

Extensibility uses a mechanism every Python developer already knows. No registry,
no DSL, no new file format. Until a dedicated import helper exists, a case imports
its verifiers directly.

## Lens

When extensibility is the goal, prefer the host language's own import mechanism
over a plug-in registry.
