# Contributing

How to set up, build, test, and get a change accepted.

## Getting set up

Everything runs from the repository root through `make`. Use `uv`; never `pip install`
and never invoke `python` directly.

## Commands

```sh
make format   # ruff format + isort
make check    # ruff check + isort --check-only + mypy --strict
make test     # pytester-based suite, no mocks, coverage badge refresh
make build    # wheel into dist/
```

The functions that spawn a CLI are excluded from coverage with a stated reason rather
than faked: `harness.base.spawn`, `harness.claude.run_claude`,
`harness.codex.run_codex`, `plugin.cell.CellRun.invoke` and
`plugin.collect.EvalItem._run_live`. They are exercised by the paid evals in a
consuming repository. Never widen a pragma past the call that spends (ADR 0002,
ADR 0040).

Publishing happens from GitHub Releases via `.github/workflows/publish.yml` (PyPI
trusted publishing).

## The report page

`report/report.html` is built from `report-ui/`, a bun workspace (Vite, React,
TypeScript, Tamagui, Plotly, Tailwind, Vitest, Playwright) that emits one
self-contained HTML file (ADR 0028, ADR 0031). bun is needed only to change the
page; the plugin ships the built file.

```sh
make ui-dev CAPTURED=path/to/.xharness_eval_cache      # hot reload against real cached data
make ui-check                                          # tsc + eslint + prettier
make ui-test                                           # vitest component tests
make ui-e2e CAPTURED=path/to/.xharness_eval_cache TIER=small  # Playwright permutation sweep
make ui-smoke CAPTURED=path/to/.xharness_eval_cache    # build, populate inline, boot over file://
make ui-promote                                        # ship the build as assets/report.html (CI checks it is current)
```

## Decision records

Design questions are usually already answered. Check
[docs/adrs/index.md](docs/adrs/index.md) before opening one, and record a new binding
decision as a new record rather than editing an accepted one.

Records are authored as `docs/adrs/NNNN-slug.yml`; every `.md` beside them is generated
by `make adrs` (ADR 0047). Edit the YAML.

## Naming

Use the canonical terms in [GLOSSARY.md](GLOSSARY.md) for identifiers, documentation and
conversation. When a new domain term enters the code, add it to the glossary in the same
change.

## Releasing

Bump `version` in `pyproject.toml` and `__version__` in
`src/pytest_xharness_eval/__init__.py` together, run `make test`, then publish a GitHub
Release tagged `vX.Y.Z`. `.github/workflows/publish.yml` does the rest (ADR 0017).
