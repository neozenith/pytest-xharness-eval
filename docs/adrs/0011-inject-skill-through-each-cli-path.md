# 0011: The skill under test loads through each CLI's own skill path

Status: accepted, 2026-08-20.

## Context

The deliverable being evaluated is a skill. Inlining its body into the prompt
would grade a prompt while still attributing the score to the skill. Copying it
into the workspace as `.claude/skills/` only takes effect when settings sources
are loaded, which fights the isolation goal.

## Decision

Claude receives the skill directory through `--add-dir`; Codex loads it from
`$CODEX_HOME/skills/<skill>`. Two mechanisms, each the path a real user's skill
travels.

## Consequences

The eval exercises skill loading, not just skill text. Two injection paths must
be kept in step in `runner.py`.

## Lens

Evaluate a deliverable through the loading path its real users take; a shortcut
that bypasses loading changes what is being measured.
