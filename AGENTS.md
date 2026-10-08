# AGENTS.md: operating instructions for pytest-xharness-eval

This repository is a pytest plugin that drives paid agent CLIs. Read this file, then
check [docs/adrs/index.md](docs/adrs/index.md) before asking a design question:
most of them are already decided, and a new binding decision is recorded there as a
new ADR, never as a rewrite of an old one.

How this repository organises its documentation, where a doc belongs, how an ADR is
authored, what each file's charter is, is [docs/CONVENTIONS.md](docs/CONVENTIONS.md).
Consult it before creating, moving or renaming any document.

## Commands

Run everything from the repository root.

| Task | Command | Cost |
|------|---------|------|
| Format | `make format` | free |
| Lint and type-check (`ruff`, `isort`, `mypy --strict`) | `make check` | free |
| Run the plugin's own tests with coverage (first runs `make prices-sync`, which curates a price snapshot only when `models.toml` lists an unpriced model, and otherwise exits offline) | `make test` | free |
| Build a wheel | `make build` | free |
| Check the decision records: generated markdown matches its `.yml`, and every record passes the pinned prose gates (fix findings in the `.yml`) | `make adrs-check`, `make adrs-prose` | free |
| Curate a new dated price record from LiteLLM's feed (first-party rows of the watched families; writes only on a change; `ARGS="--dry-run"` stages under `tmp/curate-prices/`; stops on a release `models.toml` has not decided, naming it, ADR 0067) | `make prices` | free |
| Work on the report page (`report-ui/`, ADR 0028, ADR 0031) | `make ui-dev CAPTURED=<project>/.xharness_eval_cache`, then `make ui-check`, `make ui-test`, `make ui-ct` (Playwright Component Testing: each component mounted alone in Chromium from `report-ui/ct/fixtures.ts`, no capture needed), `make ui-e2e CAPTURED=… TIER=small|medium|large` (Playwright permutation sweep; `small` is the inner loop, `large` the full matrix), `make ui-smoke CAPTURED=…`, and `make ui-promote` to ship the build (CI fails if the asset is stale) | free |
| Release to PyPI | bump `version` and `__version__` together, `make test`, then publish a GitHub Release tagged `vX.Y.Z`; `publish.yml` does the rest (ADR 0017) | free |

In a consuming repository with the plugin installed:

| Task | Command | Cost |
|------|---------|------|
| List cells without running | `pytest --collect-only -q skills/<skill>/evals` | free |
| Preview cells and validate pricing | `pytest skills/<skill>/evals --dry-run` | free |
| Run one skill's evals, or all | `pytest skills/<skill>/evals -v`, `pytest skills/*/evals -v` | paid |
| Run cells in parallel | `pytest skills/*/evals -v -n 4`; add `--dist loadgroup` to keep each harness serial | paid |
| Run one harness, model, effort or treatment only | `pytest skills/<skill>/evals --harness codex`, `--model opus`, `--effort max`, `--treatment control`, `-k "opus or sol"` | paid |
| Read the last report | `cat .xharness_eval_cache/report/report.json` | free |
| Rebuild results, history and `report.html` from captured logs after a plugin change | `uv run -m pytest_xharness_eval.replay .xharness_eval_cache` (a legacy `<skill>/evals/captured` dir migrates into the cache, ADR 0032) | free |

Never `pytest skills` from the root: it collects every skill's `scripts/` unit tests.

Never use `pip install` or invoke `python` directly; use `uv`.

## Layout by purpose

All source lives under `src/pytest_xharness_eval/`, and the listing is the architecture
(ADR 0039). Two entry-point modules sit at the root because importlib resolves them by
name -- `plugin/` (the `pytest11` entry point, a package whose `__init__` is the hook
manifest, ADR 0040) and `replay.py` (`python -m`) -- and the six layers each run is
pushed through are folders beneath them, each depending only on the ones above it in
this list:

| Layer | What lives there |
|-------|------------------|
| `model/` | the nouns: `runresult.py`, `case.py`, `output.py`, `suite.py`, `matrix.py`, `verdict.py`, `effort.py`, `treatment.py`, `catalogue.py`, `layout.py`, `workspace.py`, `clock.py`, `documents.py`, and `registry.py` -- the one module below `harness/` that names it |
| `harness/` | one adapter class per agent CLI (`base.py`, `claude.py`, `codex.py`), the folding toolkit `normalise.py`, and the record-kind catalogue `records.py` |
| `derive/` | free derivations over a folded run: `pricing.py`, `skillcov.py`, `ignorerules.py`, `catalogue.py` (reads `prices/models.toml`), `feed.py` (LiteLLM's feed into price records, for the curator and live pricing), and the bundled `prices/prices-YYYYMMDD.toml` records |
| `verify/` | what a *grader* is written with: `checks.py` (the shared `check_*` verifiers), `tolerance.py` (`Facet` and the six tolerances), `facets.py` (markdown/mermaid extractors), `golden.py` (`GoldenCase`) |
| `emit/` | the documents that leave: `metrics.py`, `index.py`, `summary.py`, `tokens.py`, `page.py` |
| `runtime/` | how a sweep is wired: `settings.py`, `pipeline.py`, and the transitional `legacy.py` |

A ruff `TID251` rule fails the build when a layer names one above it; the exceptions are
the per-file-ignore list in `pyproject.toml` and nowhere else.

| Change you want | Edit |
|-----------------|------|
| How a CLI is invoked or its log is found | `harness/claude.py` or `harness/codex.py`; the shared spawn contract is `harness/base.py` (ADR 0034) |
| How a skill is *named* to a CLI, or registered with it | `Harness.invoke` in `harness/<provider>.py` -- `/<skill> <task>` for claude (registered by `skill_plugin`'s `--plugin-dir` wrapper), `$<skill> <task>` for codex (copied into the private `CODEX_HOME/skills/`). The one edge from beneath is `model/registry.invocation` (ADR 0044) |
| A whole new agent CLI | one module under `harness/`: subclass `Harness`, implement `run`, `session_from_capture`, `classify_record`, `shell_tools` / `persistent_shells` (and `shell_commands` if its shell tool wraps commands, ADR 0066), `efforts` / `effort_args` (an empty ladder is a coherent "no effort control", ADR 0049), then `register()` it in `harness/__init__.py`. Nothing else dispatches on the name (ADR 0034) |
| How subagent transcripts are found, attributed and billed | `harness/claude.py` and `harness/codex.py` (`subagents_of` per dialect), `runtime/pipeline.py`'s `capture_subagents` (capture into `subagents/`) (ADR 0033) |
| How a session log maps to `RunResult` fields | the harness's `SessionLog.to_result` in `harness/<provider>.py`; the primitives both dialects fold with are `harness/normalise.py` |
| A new field on the run record | `model/runresult.py`, then `harness/claude.py` and `harness/codex.py` for both dialects |
| A bundled model price | `derive/prices/` only, USD per MTok, rows under their harness's table. A price *change* never edits a closed record: set `effective_to` on the open one and add `prices-<date>.toml` whose `effective_from` is that date. `make prices` does both from LiteLLM's feed; the watched families are `WATCHES` in `.github/scripts/curate_prices.py`, and a row with a comment line starting `# curate: keep` is a local override it never re-prices. A long-context rate is a row's `long_context` sub-table, never a comment. A project overrides with `<harness>/<model>: ...` `xharness_prices` lines, optionally `from=`/`to=` bounded and with `long_context_above` / `long_*` keys (ADR 0030, ADR 0050, ADR 0051) |
| The plugin-default matrix or narrowing | `model/matrix.py` (`catalogued`, `narrow`) and `Settings.default_matrix` in `runtime/settings.py`, which applies the `xharness_output_rate_limit` cost filter; the *known* harnesses are the registry, reached through `model/registry.py` and never a second list (ADR 0034, ADR 0039, ADR 0058) |
| A model released since the last snapshot ("check for new models"), found without being named | run `make prices ARGS="--dry-run"`. A first-party release `models.toml` neither catalogues nor excludes stops it, named with its feed `source` link; the weekly `prices.yml` opens an "Undecided model releases" issue with the same list. Read the source for the release date and whether it is gated, then add it to `[<harness>.models]` (its line from the id, the tier of that line's role, `released`) or to `[<harness>.excluded]` with a reason. Then `make prices` and `make test`, and follow the `models.toml` row of the change table below (ADR 0067) |
| The models the plugin supports, or a model's line, family tier or release date | `derive/prices/models.toml`, the one config file; `derive/catalogue.py` reads it, and the noun and the `xharness_models` line parser are `model/catalogue.py`. A tier is a hand-curated role, frozen at release, never derived from price. `make test` curates a price snapshot for a model added without one (ADR 0057, ADR 0059, ADR 0060) |
| How a model with no price row is priced at collection | `Settings.ensure_priced` in `runtime/settings.py`, which reads the feed at `xharness_price_feed` and writes `<cache>/pricing/` records through `derive/feed.py`; the conversion is shared with `.github/scripts/curate_prices.py` (ADR 0060) |
| How a treatment is named, found under `evals/treatments/`, or refused at collection | `model/treatment.py`; the crossing with the control is `matrix.treat`, the overlay copy is `model/workspace.py`'s `materialise`, and how each CLI reads the overlaid instructions file is its harness's isolation lever (ADR 0055) |
| The effort vocabulary, or a portable alias's meaning | `model/effort.py` (`Effort`, `resolve`); a harness's own ladder is `Harness.efforts` in `harness/<provider>.py` and the rendering is its `effort_args`, reached from beneath through `model/registry.py` (ADR 0049) |
| A plugin option or ini key's registration | `plugin/options.py` (which also validates the price and ignore lines at configure time, and prints the header) |
| The collection rule, the cell item, or how one cell runs | `plugin/collect.py` (`EvalFile`, `EvalItem`), `plugin/cell.py` (`CellRun`: materialise, invoke, store, grade, record; only `invoke` spends, ADR 0002) |
| How a record reaches the xdist controller, or a cell's status word | `plugin/results.py` (`PROPERTY`, the stash keys, the one dict crossing, ADR 0016) |
| The words a cell may grade to | `model/verdict.py` (`Verdict`); every producer names it from there, and the `.value` -- never the member -- reaches a record (ADR 0041) |
| The terminal table, `report.json`, or when the combine step runs | `plugin/summary.py` (the hook) and `emit/summary.py` (`RunSummary`, the document, ADR 0040) |
| How an `eval_*.py` suite is imported, or a case found in one | `model/suite.py` (`EvalSuite`, `find_case`) -- one loader for collection and replay alike (ADR 0040) |
| An ini key, or how a location is resolved for a sweep *and* a replay | `runtime/settings.py` (`Settings.from_config` / `from_cache`); `Settings.cache` is the `CacheLayout`, never a bare path (ADR 0034, ADR 0037) |
| What happens to a `RunResult` after the CLI returns (price, coverage, case, evidence, metrics) | `runtime/pipeline.py` -- one sequence, run by both the live cell and a replay (ADR 0034) |
| The per-cell metrics record or the verbose status word | `emit/metrics.py` (`CellMetrics`; its keys are a wire format, pinned in `tests/emit/test_metrics.py`, ADR 0037) |
| A directory or file name under the cache root, or the `{skill}/{harness}/{model}[--{effort}]/{run}/{session}` shape | `model/layout.py` (`CacheLayout`, `SessionDir`, `LocatedSession`, `model_level`) and nowhere else (ADR 0037, ADR 0038, ADR 0049) |
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
| The `@evalcase` contract, or what a case declares | `model/case.py` (`task=`, never `prompt=`, ADR 0044) |
| What a grader is handed, or an accessor over the workspace | `model/output.py` (`CaseOutput`), then the surface table in `docs/rollout.md` (ADR 0045) |
| A shared `check_*` verifier | `verify/checks.py`, then `docs/rollout.md`'s verifier table and `tests/verify/test_checks.py` (ADR 0045) |
| A golden tolerance, or a markdown/mermaid facet extractor | `verify/tolerance.py` or `verify/facets.py`, then `docs/rollout.md` (ADR 0046) |
| A behaviour of the plugin | `tests/<layer>/test_<module>.py`, mirroring `src/pytest_xharness_eval/<layer>/<module>.py` (shared builders in `tests/support.py`); whole-plugin sessions in `tests/test_plugin.py` (pytester). `tests/test_suite_shape.py` fails the build on a module that mirrors nothing or outgrows its budget (ADR 0053) |

Evals themselves do not live here. They live beside the skill they grade, in the
consuming repository: `skills/<skill>/evals/eval_<suite>.py`, seed trees under
`evals/fixtures/<name>/`, and known-good outputs under `evals/goldens/<name>/` mirroring
them (ADR 0046). Run output never lands in the skills tree (ADR 0032): each
session's evidence is `.xharness_eval_cache/results/{skill}/{harness}/{model}[--{effort}]/{run}/{session}/`
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
  an `xharness_prices` ini line, price it live from the feed into `<cache>/pricing/`, or let
  the sweep stop at collection (ADR 0007, ADR 0030, ADR 0060). Live pricing matches an exact
  first-party id only; it never guesses from a host's spelling or a neighbouring model.
  The same holds for a *day* no record covers: never borrow a neighbouring record's rates
  (ADR 0050).
- Never edit the rates in a closed price record, or re-price a run at a rate other than
  the one in effect on its `{run}` day. A price change is a new
  `derive/prices/prices-YYYYMMDD.toml`, and history stays reproducible (ADR 0050).
- Never reduce a published rate to a comment, and never price a threshold against a run's
  summed usage. A provider's long-context tier is data on the row, applied call by call
  from the per-call ledgers; a cost field the curator does not model stops curation
  rather than being dropped (ADR 0051).
- Never write a prompt that explains the harness to the agent. A case declares a `task`;
  the invocation (`/<skill> ...`, `$<skill> ...`) is `Harness.invoke`'s to render, and a
  `prompt=` reaching `@evalcase` is a `TypeError`, never an alias (ADR 0044).
- Never copy a `check_*` block between suites. If two cases want it, it belongs in
  `verify/checks.py` -- four drifted copies, two of them asserting nothing, is what that
  layer exists to end (ADR 0045).
- Never give a golden facet no tolerance, and never call `GoldenCase.record` from a
  grader: a run that laundered its own output into the reference makes every later
  comparison vacuous (ADR 0046).
- Never write run output under `evals/fixtures/`. A fixture is copied into every
  workspace, so anything placed there leaks into the next agent's working directory.
- Never add a runtime dependency beyond pytest and the standard library (ADR 0003).
- Never derive a path from `__file__` except for the bundled `derive/prices/` records and
  the model catalogue beside them (`models.toml`, ADR 0059).
  Every other location is an ini key resolved against `config.rootpath` (ADR 0014, ADR 0050).
- Never register the plugin through a `conftest.py` or `-p` flag. The `pytest11`
  entry point in `pyproject.toml` is the one registration (ADR 0014).
- Never let an effort rung reach a CLI unvalidated, and never round one to the nearest
  rung a harness does have. Both CLIs accept an unknown rung, warn at most, and bill a
  full run at their default, so the vocabulary closes in `model/effort.py` and resolves at
  matrix expansion -- and what a `Cell` carries is the resolved native rung, never the word
  the author typed (ADR 0049).
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
- Never change an accepted ADR's argument. Write a new one that supersedes it and update the
  index. Its shape may change to pass `make adrs-prose` (reflow, split a sentence, replace an
  em-dash, promote a disguised list), with every claim unchanged, and always in the `.yml`,
  never the generated `.md` (ADR 0054).

## Vocabulary

Use the terms in [GLOSSARY.md](GLOSSARY.md) for identifiers, docs, and conversation:
*case*, *cell*, *harness*, *matrix*, *effort*, *rung*, *alias*, *fixture*, *treatment*,
*control*, *workspace*, *session log*, *RunResult*, *captured*, *skills root*. The first
matrix axis is *harness*, never *cli* (ADR 0015); the third is *effort*, and one level of a
harness's ladder is a *rung*, never a "level" or a "thinking budget" (ADR 0049); the fourth
is *treatment*, and the untreated cell is the *control*, never a "baseline" or a "null
treatment" (ADR 0055). When a new domain term enters
the code, add it to the glossary in the same change.

## When you change one thing, update the other

| If you change | Also update |
|---------------|-------------|
| A CLI flag in `harness/<provider>.py` | The isolation-levers table in `ARCHITECTURE.md` |
| `RunResult` fields | both `harness/claude.py` and `harness/codex.py`, and the vocabulary table |
| A term in [GLOSSARY.md](GLOSSARY.md) | The "How the terms relate" diagram beneath it; re-run the mermaid contrast and complexity gates |
| A plugin option or ini key | `README.md` tables and `tests/test_plugin.py` |
| A `RunResult` field, a `CaseOutput` accessor, or a bundled verifier | `docs/rollout.md` -- it is the published grader surface, so a field a suite may assert on and cannot find there does not exist |
| The default matrix, or `derive/prices/models.toml` | `README.md` Quickstart expected output and its catalogue table, `GLOSSARY.md`'s family tier row, `tests/test_plugin.py`'s `DEFAULT_CELLS`, and a price row for every catalogued model (`make test` curates one; `tests/model/test_catalogue.py` fails the build without one) |
| A harness's `efforts` ladder, or a word in `model/effort.py` | `README.md`'s alias table, `GLOSSARY.md`, `ARCHITECTURE.md`'s isolation-levers table, and `tests/model/test_effort.py` -- the ladder is ordered, so adding a rung moves what `mid` resolves to |
| A decision recorded in an ADR | Write a new ADR that supersedes it; do not change the old one's argument (shape-only prose fixes to its `.yml` are allowed, ADR 0054) |
| Any ADR `.yml`, or `docs/adrs/templates/` | `make adrs`, then `make adrs-check` and `make adrs-prose` (both run in CI) |
| A key `emit/index.py` or `emit/metrics.py` writes | `report-ui/src/lib/types.ts`, the glossary's metric table, the frozen key lists in `tests/emit/test_metrics.py` and `tests/emit/test_index.py`, and the `SessionTable` column definitions if it is shown |
| `report-ui/src/` | `make ui-check`, `make ui-test`, `make ui-ct` (and the component's `report-ui/ct/<Component>.spec.tsx`); a `TIER=small` sweep while iterating, `TIER=medium` before shipping, `large` when the change ripples wide |
| A route param in `report-ui/src/lib/route.ts` | `report-ui/src/lib/permutations.ts` in the same change, or the e2e matrix silently stops covering it |

## Out of scope this iteration

Skills that need git history or a diff (ADR 0004). A case for such a skill must fail
loudly rather than run in a git-less workspace and report a score.
