# 0026: What is not decision surface is declared in the project's pytest config, not in a dotfile beside the skill

Status: accepted, 2026-08-23. Refines [0023](0023-turn-boundaries-skill-ignore-and-replay.md)
(its skill-ignore decision) and [0014](0014-register-through-the-pytest11-entry-point.md).

## Context

0023 let a skill carry a `.skillignore` at its root and, separately, let a project
set `xharness_skill_ignore` in its pytest config; the two lists were concatenated.
In practice the dotfile was the one that got used, because only it could say
something about *one* skill: the ini key had no way to scope a pattern.

A dotfile beside the skill is a new convention with nothing to anchor it. A pytest
user expects a plugin's permanent, file-based configuration in the place pytest
keeps its own: `[tool.pytest.ini_options]` in `pyproject.toml` (or `pytest.ini`,
`tox.ini`, `setup.cfg`). Nothing in `pytest --help` or in the project's config
hinted that a second file, in a directory pytest never looks in, was also being
read; and the skill directory is shipped to agents as-is, so the dotfile rode along
into every `--add-dir` and `$CODEX_HOME/skills` copy as a file the agent could see
but that described a tool it had never heard of. 0014 already settled that every
location the plugin reads is an ini key resolved against the rootdir; the dotfile
was the one exception.

## Decision

`xharness_skill_ignore` is the only source of ignore patterns. The `.skillignore`
file is not read; a leftover one is just another dotfile, which 0022 never
catalogues.

Each line of the key is either a bare gitignore-style pattern, which applies to
every skill, or `<selector>: <pattern>`, which applies to the skills whose
directory name matches the `fnmatch` selector (`mermaidjs-diagrams: README.md`
names one skill, `*-diagrams: README.md` a family). This is the form pytest's own
`markers` lines use (`name: description`), so it reads as pytest config rather than
as a new grammar. A selector with nothing after the colon is a usage error that
stops the session at configure time, before any cell is collected, since it would
ignore nothing and is almost certainly a typo. The pattern grammar is unchanged
from 0023.

```toml
[tool.pytest.ini_options]
xharness_skill_ignore = [
    "README.md",                                # every skill
    "mermaidjs-diagrams: resources/examples/**",
    "mermaidjs-diagrams: scripts/{Makefile,CLAUDE.md}",
    "mermaidjs-diagrams: scripts/*.json",
]
```

The replay command runs outside a pytest session, so it resolves the key the way
pytest would: the first ancestor of the captured directory holding a `pytest.ini`,
a `pyproject.toml` with `[tool.pytest.ini_options]`, a `tox.ini` or a `setup.cfg`
with a pytest section. Its `--ignore` flag takes extra lines in the same form. A
replay and a live sweep therefore always agree on what is decision surface.

## Consequences

A project that had a `.skillignore` moves its lines into the ini key, prefixed with
the skill's name, and deletes the file; until it does, every file of that skill is
decision surface again and `not_loaded` grows. Patterns whose path contains `:`
cannot be written as bare lines (the first colon is the selector boundary); such
files are not portable anyway. Skill authors who do not own the project's
`pyproject.toml` no longer have a place to declare their skill's edges; that is
deliberate: which files count is a decision of whoever pays for the sweep.

## Lens

A plugin's configuration lives where its host keeps configuration; a convention
the host's users have never seen needs a stronger reason than convenience.
