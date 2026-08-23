# 0025: A result names the case that produced it, and the per-turn charts have a session-log-line axis

Status: accepted, 2026-08-23. Refines [0018](0018-fixtures-directory-and-metrics-history.md)
and [0024](0024-context-window-metrics-injected-messages-and-design-tokens.md).

## Context

A `SessionView` showed the harness, the model and the node id, but not which suite
file and case produced the run, which fixture it started from, or the prompt that
was sent; with one case per skill that was implicit, with a second suite it is not.
The four per-turn charts answered "what happened on turn 3" but not "what was the
state at line 27 of the log", which is the question a reader has while scrolling
the turn's records.

## Decision

`RunResult.case` records `suite` (the `eval_*.py` path relative to the rootdir),
`name`, `skill`, `fixture` and `prompt`; the plugin fills it after a run and the
replay command carries it forward from the previous result, since the log does not
know it. The history line carries `suite`, `case`, `skill` and `fixture` (not the
prompt); the index and `SessionMetaTable` carry all five, and `SessionTable` gains
a `suite` column.

Every per-turn chart can be drawn against the session-log line instead of the turn
(`ChartAxisToggle`). A value holds from the line that measured it (the turn's first
assistant record on Claude, its `token_count` on Codex) until the next measurement,
drawn as a step; turn starts are marked. The waterfall becomes a stacked step area
of cumulative tokens by category; the output and tier bars sit at their measuring
line. Nothing is interpolated between measurements.

## Consequences

Results written before this decision show "not recorded" for the suite until
replayed, and replay can only carry what an earlier result stored. The per-line
charts are honest about granularity: a flat segment means "no new measurement",
not "nothing happened".

## Lens

Say which question produced the evidence, and draw a measurement where it was
taken rather than where it would look smoother.
