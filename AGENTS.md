# AGENTS.md: operating instructions for pytest-xharness-eval

This repository is a pytest plugin that drives paid agent CLIs. Read this file, then
check [docs/adrs/README.md](docs/adrs/README.md) before asking a design question:
most of them are already decided, and a new binding decision is recorded there as a
new ADR, never as a rewrite of an old one.

## Commands

Run everything from the repository root.

| Task | Command | Cost |
|------|---------|------|
| Format | `make format` | free |
| Lint and type-check (`ruff`, `isort`, `mypy --strict`) | `make check` | free |
| Run the plugin's own tests with coverage | `make test` | free |
| Build a wheel | `make build` | free |
| Release to PyPI | bump `version` and `__version__` together, `make test`, then publish a GitHub Release tagged `vX.Y.Z`; `publish.yml` does the rest (ADR 0017) | free |

In a consuming repository with the plugin installed:

| Task | Command | Cost |
|------|---------|------|
| List cells without running | `pytest --collect-only -q skills/<skill>/evals` | free |
| Preview cells and validate pricing | `pytest skills/<skill>/evals --dry-run` | free |
| Run one skill's evals, or all | `pytest skills/<skill>/evals -v`, `pytest skills/*/evals -v` | paid |
| Run cells in parallel | `pytest skills/*/evals -v -n 4`; add `--dist loadgroup` to keep each harness serial | paid |
| Run one harness or model only | `pytest skills/<skill>/evals --harness codex`, `--model opus`, `-k "opus or sol"` | paid |
| Read the last report | `cat tmp/evals/report.json` | free |

Never `pytest skills` from the root: it collects every skill's `scripts/` unit tests.

Never use `pip install` or invoke `python` directly; use `uv`.

## Layout by purpose

All source lives under `src/pytest_xharness_eval/`.

| Change you want | Edit |
|-----------------|------|
| How a CLI is invoked or its log is found | `runner.py` |
| How a session log maps to `RunResult` fields | `normalise.py` |
| A new field on the run record | `runresult.py`, then `normalise.py` for both CLIs |
| A bundled model price | `prices.toml` only |
| The plugin-default matrix, a known harness, or narrowing | `matrix.py` |
| A plugin option, ini key (including `xharness_matrix`), collection rule, or the report | `plugin.py` |
| How a workspace is built or diffed | `workspace.py` |
| The `@evalcase` contract | `case.py` |
| A behaviour of the plugin | `tests/test_plugin.py` (pytester), `tests/test_units.py` (pure modules) |

Evals themselves do not live here. They live beside the skill they grade, in the
consuming repository: `skills/<skill>/evals/eval_<suite>.py`, seed trees under
`evals/fixtures/<name>/`, evidence under `evals/captured/<case>/` (git-ignored), and
one metrics line per live cell in `evals/captured/history.jsonl`. Per-cell metrics
are built in `history.py`.

## Hard boundaries

- Never mock, patch, or fake a CLI, its subprocess, or its session log. Not in evals,
  not in unit tests. The functions that spawn a CLI carry `pragma: no cover` with a
  stated reason instead (ADR 0002).
- Never make a cell pass without a real session log. A missing log, a mismatched
  session id, or zero tokens is a failure, not a skip.
- Never price an unknown model as zero or `None` and continue. Add the row or let the
  sweep stop at collection (ADR 0007).
- Never write run output under `evals/fixtures/`. A fixture is copied into every
  workspace, so anything placed there leaks into the next agent's working directory.
- Never add a runtime dependency beyond pytest and the standard library (ADR 0003).
- Never derive a path from `__file__` except for the bundled `prices.toml`. Every
  other location is an ini key resolved against `config.rootpath` (ADR 0014).
- Never register the plugin through a `conftest.py` or `-p` flag. The `pytest11`
  entry point in `pyproject.toml` is the one registration (ADR 0014).
- Never edit an accepted ADR. Write a new one that supersedes it and update the index.

## Vocabulary

Use the terms in [ARCHITECTURE.md](ARCHITECTURE.md#vocabulary) for identifiers,
docs, and conversation: *case*, *cell*, *harness*, *matrix*, *fixture*, *workspace*,
*session log*, *RunResult*, *captured*, *skills root*. The first matrix axis is
*harness*, never *cli* (ADR 0015). When a new domain term enters the code, add it to
that table in the same change.

## When you change one thing, update the other

| If you change | Also update |
|---------------|-------------|
| A CLI flag in `runner.py` | The isolation-levers table in `ARCHITECTURE.md` |
| `RunResult` fields | `normalise.py` for both CLIs, and the vocabulary table |
| A term in the vocabulary table | The "How the terms relate" diagram beneath it in `ARCHITECTURE.md`; re-run the mermaid contrast and complexity gates |
| A plugin option or ini key | `README.md` tables and `tests/test_plugin.py` |
| The default matrix | `README.md` Quickstart expected output, `tests/test_plugin.py` |
| A decision recorded in an ADR | Write a new ADR that supersedes it; do not edit the old one |

## Out of scope this iteration

Skills that need git history or a diff (ADR 0004). A case for such a skill must fail
loudly rather than run in a git-less workspace and report a score.
