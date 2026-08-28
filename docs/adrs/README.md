# Architecture decision records

One file per decision, numbered in the order they were settled. Records 0001 to
0013 were settled while the plugin was still a package inside the first project
that used it; records from 0014 on were made after it became the standalone
`pytest-xharness-eval` package.

A record's body is never edited once accepted. Its status line may gain a
cross-link when a later record supersedes or refines it, so a reader who lands on
an old record is pointed forward; the table below carries the same links. Every
record ends in a **Lens**: the reusable rule it leaves behind.

| ADR | Title | Status |
| ----- | ------- | -------- |
| [0001](0001-ship-as-a-pytest-plugin.md) | Ship as a pytest plugin with per-skill opt-in evals | accepted; in-repository location superseded by 0014 |
| [0002](0002-every-cell-invokes-the-real-cli.md) | Every eval cell always invokes the real CLI | accepted |
| [0003](0003-runresult-is-a-stdlib-dataclass.md) | RunResult is a stdlib dataclass serialised to JSON | accepted, schema pending; its invariants are typed by 0035 |
| [0004](0004-workspace-is-a-plain-copy.md) | A workspace is a plain copy of the fixture tree | accepted; work directory is an ini key since 0014 |
| [0005](0005-private-codex-home-per-run.md) | A private per-run CODEX_HOME, seeded with credentials | accepted |
| [0006](0006-local-price-table-is-authoritative.md) | A local prices.toml is authoritative | accepted, seed pending; bundled table plus override since 0014; the override moved into the pytest config by 0030 |
| [0007](0007-unpriced-model-aborts-before-spend.md) | An unpriced model aborts before spend | accepted |
| [0008](0008-evals-are-eval-prefixed-modules.md) | Evals are `eval_*.py` modules, directory-scoped | accepted, refined by 0016 |
| [0009](0009-register-via-rootdir-conftest.md) | Register the plugin from the rootdir conftest.py | superseded by 0014 |
| [0010](0010-matrix-options-and-dry-run.md) | Default matrix, per-case override, `--model` / `--cli` / `--dry-run` | accepted, refined by 0015 |
| [0011](0011-inject-skill-through-each-cli-path.md) | The skill loads through each CLI's own path | accepted |
| [0012](0012-grading-is-composable-not-prescribed.md) | Grading is composable, not prescribed | accepted, primitives pending |
| [0013](0013-verifiers-are-python-beside-the-case.md) | Custom verifiers are Python beside the case | accepted, helper pending |
| [0014](0014-register-through-the-pytest11-entry-point.md) | Register through the pytest11 entry point of an extracted package | accepted, supersedes 0009, refined by 0017 and 0026 |
| [0015](0015-harness-is-the-axis-and-the-project-owns-the-matrix.md) | Harness is the axis name, and the project owns the default matrix | accepted, refines 0010 |
| [0016](0016-results-travel-on-the-test-report.md) | Results travel on the test report, and cells group by harness | accepted, refines 0008 |
| [0017](0017-distributed-through-pypi-with-trusted-publishing.md) | Distribute through PyPI with trusted publishing, released from a GitHub Release | accepted; 0.1.0 published 2026-08-21 |
| [0018](0018-fixtures-directory-and-metrics-history.md) | Fixtures live under evals/fixtures/, and every live cell appends to a metrics history | accepted, refines 0004 and 0016; refined by 0019 and 0020 |
| [0019](0019-per-call-ledger-and-ttl-priced-cache-writes.md) | Every run carries a per-call ledger; tokens are reported as context and billed; cache writes price by TTL | accepted, refines 0003, 0006 and 0018; names refined by 0021; the ledger folds through one constructor since 0035 |
| [0020](0020-captured-report-is-a-static-microsite.md) | `captured/report.html` is a static microsite over the captured JSON | accepted, refines 0018; vocabulary and ids in 0021; built from a component workspace since 0028 |
| [0021](0021-metric-names-carry-unit-and-provenance.md) | Metric names carry their unit and their source; the report has a named vocabulary and addressable ids | accepted, refines 0019 and 0020; refined by 0022 and 0028; `total_tokens` row superseded by 0029; the estimate is applied atomically since 0035 |
| [0022](0022-record-kind-catalogue-and-skill-coverage.md) | A catalogued record kind per log line, and skill file coverage per run | accepted, refines 0019 and 0021; refined by 0023; detection rule refined by 0027; coverage records typed by 0035 |
| [0023](0023-turn-boundaries-skill-ignore-and-replay.md) | A turn owns its tools' results; skills declare what is not decision surface; captures replay without spend | accepted, refines 0019 and 0022; skill ignore refined by 0026; replay coverage under 0027 |
| [0024](0024-context-window-metrics-injected-messages-and-design-tokens.md) | Context window consumption and timing are first-class metrics; injected messages are not prompts; the report is themed by design tokens and can be written standalone | accepted, refines 0019, 0020 and 0022; tokens theme shadcn since 0028 |
| [0025](0025-results-name-their-case-and-charts-have-a-log-line-axis.md) | A result names the case that produced it, and the per-turn charts have a session-log-line axis | accepted, refines 0018 and 0024; the case reference is typed by 0035 |
| [0026](0026-skill-ignore-lives-in-the-pytest-config.md) | What is not decision surface is declared in the project's pytest config, not in a dotfile beside the skill | accepted, refines 0014 and 0023 |
| [0027](0027-coverage-follows-the-shells-working-directory.md) | Skill coverage follows the shell's working directory | accepted, refines 0022 and 0023 |
| [0028](0028-report-is-built-from-a-component-workspace.md) | The report page is built from a component workspace and shipped as one file | accepted, refines 0020, 0021 and 0024; the build was promoted to `assets/report.html` on 2026-08-23 |
| [0029](0029-the-billed-sum-is-named-accumulative-billed-tokens.md) | The billed sum is named `accumulative_billed_tokens` | accepted, supersedes one row of 0021, refines 0019 |
| [0030](0030-price-rows-live-in-the-pytest-config.md) | Project price rows live in the pytest config, not in a prices.toml beside it | accepted, refines 0006, 0014 and 0026 |
| [0031](0031-plotly-tamagui-and-a-deeplink-permutation-matrix.md) | The report draws with Plotly on a Tamagui base, every state deeplinks, and a Playwright matrix sweeps them all | accepted, refines 0020, 0024, 0025 and 0028; supersedes 0028's component stack and 0024's series-fold rule |
| [0032](0032-all-run-output-consolidates-under-a-cache-dir.md) | All run output consolidates under `.xharness_eval_cache/`, and the report is one combine step | accepted, refines 0014, 0018 and 0020; supersedes 0018's captured/ location, 0020's per-directory report and `xharness_workdir` |
| [0033](0033-subagent-transcripts-are-captured-and-billed.md) | Subagent transcripts are captured evidence, and their tokens are billed | accepted, refines 0019, 0021 and 0032; the fold moved into 0035's constructor |
| [0034](0034-a-harness-is-a-class-and-the-registry-is-the-only-dispatch.md) | A harness is a class, the registry is the only dispatch, and the layers are named | accepted, refines 0002, 0014, 0015 and 0023; structural only |
| [0035](0035-the-nouns-carry-their-own-invariants.md) | The nouns carry their own invariants | accepted, refines 0003, 0019, 0021, 0022, 0025 and 0033; structural only |
