# 0012: Grading semantics are not prescribed; the plugin supplies primitives

Status: accepted, 2026-08-21; golden-tree and projection
primitives not yet shipped.

## Context

Agent prose is non-deterministic, so byte-exact comparison of transcripts always
fails, while loosening comparison too far produces a grader that cannot fail. What
counts as a correct run differs per skill and is not knowable up front.

## Decision

No single comparison semantic is mandated. A case is an ordinary function that
composes checks with plain `assert` over the `RunResult` and the workspace. The
plugin's set of grading primitives is curated over time; an LLM judge may join it
later as one optional primitive, never as the house rule.

## Consequences

New primitives are added without touching existing cases. The one invariant that
survives: a check that cannot evaluate raises; it never passes. Today only plain
assertions are shipped; the reference case shows the intended layering.

## Lens

Give case authors tools, not a policy; enforce only that no check can silently
pass.
