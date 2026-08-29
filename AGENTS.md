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
| Work on the report page (`report-ui/`, ADR 0028, ADR 0031) | `make ui-dev CAPTURED=<project>/.xharness_eval_cache`, then `make ui-check`, `make ui-test`, `make ui-e2e CAPTURED=… TIER=small|medium|large` (Playwright permutation sweep; `small` is the inner loop, `large` the full matrix), `make ui-smoke CAPTURED=…`, and `make ui-promote` to ship the build (CI fails if the asset is stale) | free |
| Release to PyPI | bump `version` and `__version__` together, `make test`, then publish a GitHub Release tagged `vX.Y.Z`; `publish.yml` does the rest (ADR 0017) | free |

In a consuming repository with the plugin installed:

| Task | Command | Cost |
|------|---------|------|
| List cells without running | `pytest --collect-only -q skills/<skill>/evals` | free |
| Preview cells and validate pricing | `pytest skills/<skill>/evals --dry-run` | free |
| Run one skill's evals, or all | `pytest skills/<skill>/evals -v`, `pytest skills/*/evals -v` | paid |
| Run cells in parallel | `pytest skills/*/evals -v -n 4`; add `--dist loadgroup` to keep each harness serial | paid |
| Run one harness or model only | `pytest skills/<skill>/evals --harness codex`, `--model opus`, `-k "opus or sol"` | paid |
| Read the last report | `cat .xharness_eval_cache/report/report.json` | free |
| Rebuild results, history and `report.html` from captured logs after a plugin change | `uv run -m pytest_xharness_eval.replay .xharness_eval_cache` (a legacy `<skill>/evals/captured` dir migrates into the cache, ADR 0032) | free |

Never `pytest skills` from the root: it collects every skill's `scripts/` unit tests.

Never use `pip install` or invoke `python` directly; use `uv`.

## Layout by purpose

All source lives under `src/pytest_xharness_eval/`, and the listing is the architecture
(ADR 0039). Two entry-point modules sit at the root because importlib resolves them by
name -- `plugin/` (the `pytest11` entry point, a package whose `__init__` is the hook
manifest, ADR 0040) and `replay.py` (`python -m`) -- and the five layers each run is
pushed through are folders beneath them, each depending only on the ones above it in
this list:

| Layer | What lives there |
|-------|------------------|
| `model/` | the nouns: `runresult.py`, `case.py`, `suite.py`, `matrix.py`, `verdict.py`, `layout.py`, `workspace.py`, `clock.py`, `documents.py`, and `registry.py` -- the one module below `harness/` that names it |
| `harness/` | one adapter class per agent CLI (`base.py`, `claude.py`, `codex.py`), the folding toolkit `normalise.py`, and the record-kind catalogue `records.py` |
| `derive/` | free derivations over a folded run: `pricing.py`, `skillcov.py`, `ignorerules.py`, and the bundled `prices.toml` |
| `emit/` | the documents that leave: `metrics.py`, `index.py`, `summary.py`, `tokens.py`, `page.py` |
| `runtime/` | how a sweep is wired: `settings.py`, `pipeline.py`, and the transitional `legacy.py` |

A ruff `TID251` rule fails the build when a layer names one above it; the exceptions are
the per-file-ignore list in `pyproject.toml` and nowhere else.

| Change you want | Edit |
|-----------------|------|
| How a CLI is invoked or its log is found | `harness/claude.py` or `harness/codex.py`; the shared spawn contract is `harness/base.py` (ADR 0034) |
| A whole new agent CLI | one module under `harness/`: subclass `Harness`, implement `run`, `session_from_capture`, `classify_record`, `shell_tools` / `persistent_shells`, then `register()` it in `harness/__init__.py`. Nothing else dispatches on the name (ADR 0034) |
| How subagent transcripts are found, attributed and billed | `harness/claude.py` and `harness/codex.py` (`subagents_of` per dialect), `runtime/pipeline.py`'s `capture_subagents` (capture into `subagents/`) (ADR 0033) |
| How a session log maps to `RunResult` fields | the harness's `SessionLog.to_result` in `harness/<provider>.py`; the primitives both dialects fold with are `harness/normalise.py` |
| A new field on the run record | `model/runresult.py`, then `harness/claude.py` and `harness/codex.py` for both dialects |
| A bundled model price | `derive/prices.toml` only; a project overrides with `xharness_prices` ini lines, USD per MTok (ADR 0030) |
| The plugin-default matrix or narrowing | `model/matrix.py`; the *known* harnesses are the registry, reached through `model/registry.py` and never a second list (ADR 0034, ADR 0039) |
| A plugin option or ini key's registration | `plugin/options.py` (which also validates the price and ignore lines at configure time, and prints the header) |
| The collection rule, the cell item, or how one cell runs | `plugin/collect.py` (`EvalFile`, `EvalItem`), `plugin/cell.py` (`CellRun`: materialise, invoke, store, grade, record; only `invoke` spends, ADR 0002) |
| How a record reaches the xdist controller, or a cell's status word | `plugin/results.py` (`PROPERTY`, the stash keys, the one dict crossing, ADR 0016) |
| The words a cell may grade to | `model/verdict.py` (`Verdict`); every producer names it from there, and the `.value` -- never the member -- reaches a record (ADR 0041) |
| The terminal table, `report.json`, or when the combine step runs | `plugin/summary.py` (the hook) and `emit/summary.py` (`RunSummary`, the document, ADR 0040) |
| How an `eval_*.py` suite is imported, or a case found in one | `model/suite.py` (`EvalSuite`, `find_case`) -- one loader for collection and replay alike (ADR 0040) |
| An ini key, or how a location is resolved for a sweep *and* a replay | `runtime/settings.py` (`Settings.from_config` / `from_cache`); `Settings.cache` is the `CacheLayout`, never a bare path (ADR 0034, ADR 0037) |
| What happens to a `RunResult` after the CLI returns (price, coverage, case, evidence, metrics) | `runtime/pipeline.py` -- one sequence, run by both the live cell and a replay (ADR 0034) |
| The per-cell metrics record or the verbose status word | `emit/metrics.py` (`CellMetrics`; its keys are a wire format, pinned in `tests/test_units.py`, ADR 0037) |
| A directory or file name under the cache root, or the `{skill}/{harness}/{model}/{run}/{session}` shape | `model/layout.py` (`CacheLayout`, `SessionDir`, `LocatedSession`) and nowhere else (ADR 0037, ADR 0038) |
| `report/index.json` or the aggregated `report/history.jsonl` | `emit/index.py` (`IndexRow`); the combine step that writes the microsite is `emit/page.py`, the design tokens `emit/tokens.py` (ADR 0032, ADR 0039) |
| The browsable `report/report.html` | `report-ui/src/` (the SPA, ADR 0028, ADR 0031: Tamagui base, Plotly charts), then `make ui-promote`; `assets/report.html` is the built artifact, never edited by hand |
| A page component, its id or its data contract | `report-ui/src/components/` or `views/`, `report-ui/src/lib/types.ts` (mirrors the JSON `emit/` writes), then the glossary |
| The report's colours, fonts or chart palette | `assets/report.tokens.json` (the bundled design tokens); a project overrides them with `xharness_report_design_tokens` |
| Context window, TTFT or tokens-per-second figures | `model/runresult.py` (the properties) and `harness/<provider>.py` (where each harness reports them); the derivation and its provider sources are `docs/token-accounting.md`, update it with them |
| A name, metric definition or id on the report | `assets/XHARNESS-REPORT-GLOSSARY.md` (shipped beside the page), then the element ids in `report-ui/src/` and the checklist in `report-ui/e2e/inline.spec.ts` |
| A session-log record kind, its category or pill colour | the harness's `classify_record` in `harness/<provider>.py` for the kind, `harness/records.py` for the catalogue and category, then the mirrored tables in `report-ui/src/lib/records.ts` (and the local map in `report-ui/src/components/panels/helpers.ts`), then the glossary |
| Which skill files count as loaded or run | `derive/skillcov.py` (`SkillFile` catalogued, `FileCoverage` annotated, `SkillCoverage` derived); the shell vocabulary it attributes with arrives as a `model.registry.Shells` value (ADR 0027, ADR 0039) |
| How `xharness_skill_ignore` lines (`<pattern>` or `<skill>: <pattern>`) select and match | `derive/ignorerules.py` (ADR 0035) |
| Rebuilding cached results without a paid run | `replay.py` (`uv run -m pytest_xharness_eval.replay <cache dir>`) |
| Migrating a legacy pre-0032 `captured/` dir | `runtime/legacy.py` (`LegacyCapture`); transitional, deletable in one file (ADR 0040) |
| How a workspace is built or diffed | `model/workspace.py` |
| The `@evalcase` contract | `model/case.py` |
| A behaviour of the plugin | `tests/test_plugin.py` (pytester), `tests/test_units.py` (pure modules) |

Evals themselves do not live here. They live beside the skill they grade, in the
consuming repository: `skills/<skill>/evals/eval_<suite>.py`, seed trees under
`evals/fixtures/<name>/`. Run output never lands in the skills tree (ADR 0032): each
session's evidence is `.xharness_eval_cache/results/{skill}/{harness}/{model}/{run}/{session}/`
(`log.jsonl`, `result.json`, `history.json`, all git-ignored by the `.*_cache` convention),
and the aggregated report is `.xharness_eval_cache/report/`. Per-cell metrics are built
in `emit/metrics.py`.

## Hard boundaries

- Never mock, patch, or fake a CLI, its subprocess, or its session log. Not in evals,
  not in unit tests. The functions that spawn a CLI carry `pragma: no cover` with a
  stated reason instead (ADR 0002).
- Never widen a `pragma: no cover` past the call that spends. If free steps sit inside
  it, push the paid call down into its own method until the pragma fits it exactly, and
  test the rest (ADR 0040) -- `plugin/cell.py` is the worked example.
- Never author a serialised document as a literal inside a pytest hook or a CLI entry
  point. Every emitted format is a type in `emit/` with `to_dict`/`write` on it, so a
  reader (and `report-ui/src/lib/types.ts`) has one definition to look at (ADR 0037,
  ADR 0040).
- Never spell a word from a shared vocabulary as a literal. A vocabulary two layers use
  is a `StrEnum` in `model/`, where every layer above may import it; its `.value` is what
  reaches a record that crosses execnet (ADR 0041).
- Never re-export an internal from `plugin/__init__.py`. It binds the seven hooks pluggy
  discovers plus the four compatibility names, and a test pins that set; everything else
  stays addressable at `plugin.<module>.<name>` (ADR 0041).
- Never make a cell pass without a real session log. A missing log, a mismatched
  session id, or zero tokens is a failure, not a skip.
- Never price an unknown model as zero or `None` and continue. Add the bundled row or
  an `xharness_prices` ini line, or let the sweep stop at collection (ADR 0007, ADR 0030).
- Never write run output under `evals/fixtures/`. A fixture is copied into every
  workspace, so anything placed there leaks into the next agent's working directory.
- Never add a runtime dependency beyond pytest and the standard library (ADR 0003).
- Never derive a path from `__file__` except for the bundled `derive/prices.toml`. Every
  other location is an ini key resolved against `config.rootpath` (ADR 0014).
- Never register the plugin through a `conftest.py` or `-p` flag. The `pytest11`
  entry point in `pyproject.toml` is the one registration (ADR 0014).
- Never branch on a harness name (`if harness == "claude"`, a dict keyed by it, a set
  unioning both providers' vocabularies). Reach a provider through `harness.get(name)`
  and put the difference on the class. A ruff `TID251` rule fails the build if anything
  outside `harness/` imports `harness.claude` or `harness.codex` by name (ADR 0034).
- Never put a dataclass on `TestReport.user_properties`. execnet serialises builtins
  only: the metrics record is `to_dict()`-ed at the `pytest_runtest_makereport` hook and
  `from_dict()`-ed on the controller, and is a type everywhere else (ADR 0016, ADR 0037).
- Never spell a cache path by hand (`cache / "results"`, `session_dir / "log.jsonl"`, a
  `*/*/*/*/*` glob). Go through `CacheLayout` / `SessionDir` (ADR 0037). A report link or
  a session key needs a `LocatedSession`, which only `CacheLayout` builds (ADR 0038).
- Never give a field a default that exists only because one constructor cannot fill it,
  and never let a boundary reader (`from_dict`) return a value its own declaration does
  not describe: drop the value, keep the type honest (ADR 0038).
- Never import a layer from beneath it. `model/` -> `harness/` -> `derive/` -> `emit/`
  -> `runtime/` -> the two entry points, one direction only; a lookup the domain genuinely
  needs from the registry goes through `model/registry.py`, the one declared exception. A
  ruff `TID251` rule fails the build on the rest (ADR 0039).
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
| A CLI flag in `harness/<provider>.py` | The isolation-levers table in `ARCHITECTURE.md` |
| `RunResult` fields | both `harness/claude.py` and `harness/codex.py`, and the vocabulary table |
| A term in the vocabulary table | The "How the terms relate" diagram beneath it in `ARCHITECTURE.md`; re-run the mermaid contrast and complexity gates |
| A plugin option or ini key | `README.md` tables and `tests/test_plugin.py` |
| The default matrix | `README.md` Quickstart expected output, `tests/test_plugin.py` |
| A decision recorded in an ADR | Write a new ADR that supersedes it; do not edit the old one |
| A key `emit/index.py` or `emit/metrics.py` writes | `report-ui/src/lib/types.ts`, the glossary's metric table, the frozen key lists in `tests/test_units.py`, and the `SessionTable` column definitions if it is shown |
| `report-ui/src/` | `make ui-check`, `make ui-test`; a `TIER=small` sweep while iterating, `TIER=medium` before shipping, `large` when the change ripples wide |
| A route param in `report-ui/src/lib/route.ts` | `report-ui/src/lib/permutations.ts` in the same change, or the e2e matrix silently stops covering it |

## Out of scope this iteration

Skills that need git history or a diff (ADR 0004). A case for such a skill must fail
loudly rather than run in a git-less workspace and report a score.
