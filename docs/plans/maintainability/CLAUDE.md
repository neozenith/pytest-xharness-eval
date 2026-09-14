# AGENTS.md: operating instructions for docs/plans/maintainability/

Every `.md` file in this directory and below is subject to the `gooddocs` skill.
No file here is finished until it has been through it.

## The gate

Run the deterministic prose gate before declaring any file in this tree done:

```bash
bun run .claude/skills/gooddocs/scripts/prose_gates.ts docs/plans/maintainability/**/*.md
```

It exits `1` while findings remain and `2` on a usage error.
Add `--json` for machine-readable output.
Add `--fix` to reflow prose to one sentence per line, the only finding the script repairs on its own.
Every other finding is report-only and is fixed by hand.

| Rule | Catches |
|------|---------|
| `PG001` | a sentence wrapped across lines |
| `PG002` | a sentence over the length limit |
| `PG003` | a semicolon list |
| `PG004`, `PG005` | banned glyphs |
| `PG006` to `PG009` | disguised lists |

Code blocks are exempt by construction.
Fences tagged `markdown` or `md` are audited recursively, because they hold templates.

## The skill

Run `/gooddocs` over this tree for anything the deterministic gate cannot see:

| Mode | When |
|------|------|
| `AUDIT` | a doc here makes a claim about the repo, a tool, a command or a measured number, and the audit corroborates that the claim still holds |
| `WRITE` / `IMPROVE` | authoring a new doc in this tree, or rewriting one |
| `RESTRUCTURE` | the claims are right but the shape is not: heading hierarchy, list and table discipline, whitespace rhythm, frontloaded summaries |

`RESTRUCTURE` changes shape and never claims.
When a doc needs both, audit first so the restructure is not built on a stale claim.

## The files and their charters

| File | Charter |
|------|---------|
| `GOAL.md` | the maintainer's mission statement, which every finding and question is checked against. Never edit it without the maintainer |
| `README.md` | locked-in learnings only, each backed by a measurement or a primary source |
| `OPEN_QUESTIONS.md` | everything undecided, grouped by what blocks what |
| `GLOSSARY.md` | one entry per metric: formula, meaning, gaming, worked example |
| `tools/` | only the extractors and the live `graphdata.py`. A one-off script is archived once its finding lands in `README.md` |

A finding moves from `OPEN_QUESTIONS.md` to `README.md` only with evidence, and its question is then deleted.
Do not add session logs, per-run write-ups or "where to pick this up" lists to this tree.
Those were consolidated once already, and git keeps the originals.

## Why this tree in particular

These documents argue *from measured numbers*: scores, thresholds, correlation coefficients, tool output.
A number that has drifted is worse than no number, because it carries the authority of having been measured.
The audit mode exists to catch exactly that, so it is not optional here.
