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
| [0003](0003-runresult-is-a-stdlib-dataclass.md) | RunResult is a stdlib dataclass serialised to JSON | accepted, schema pending |
| [0004](0004-workspace-is-a-plain-copy.md) | A workspace is a plain copy of the fixture tree | accepted; work directory is an ini key since 0014 |
| [0005](0005-private-codex-home-per-run.md) | A private per-run CODEX_HOME, seeded with credentials | accepted |
| [0006](0006-local-price-table-is-authoritative.md) | A local prices.toml is authoritative | accepted, seed pending; bundled table plus override since 0014 |
| [0007](0007-unpriced-model-aborts-before-spend.md) | An unpriced model aborts before spend | accepted |
| [0008](0008-evals-are-eval-prefixed-modules.md) | Evals are `eval_*.py` modules, directory-scoped | accepted, refined by 0016 |
| [0009](0009-register-via-rootdir-conftest.md) | Register the plugin from the rootdir conftest.py | superseded by 0014 |
| [0010](0010-matrix-options-and-dry-run.md) | Default matrix, per-case override, `--model` / `--cli` / `--dry-run` | accepted, refined by 0015 |
| [0011](0011-inject-skill-through-each-cli-path.md) | The skill loads through each CLI's own path | accepted |
| [0012](0012-grading-is-composable-not-prescribed.md) | Grading is composable, not prescribed | accepted, primitives pending |
| [0013](0013-verifiers-are-python-beside-the-case.md) | Custom verifiers are Python beside the case | accepted, helper pending |
| [0014](0014-register-through-the-pytest11-entry-point.md) | Register through the pytest11 entry point of an extracted package | accepted, supersedes 0009, refined by 0017 |
| [0015](0015-harness-is-the-axis-and-the-project-owns-the-matrix.md) | Harness is the axis name, and the project owns the default matrix | accepted, refines 0010 |
| [0016](0016-results-travel-on-the-test-report.md) | Results travel on the test report, and cells group by harness | accepted, refines 0008 |
| [0017](0017-distributed-through-pypi-with-trusted-publishing.md) | Distribute through PyPI with trusted publishing, released from a GitHub Release | accepted, first release pending |
| [0018](0018-fixtures-directory-and-metrics-history.md) | Fixtures live under evals/fixtures/, and every live cell appends to a metrics history | accepted, refines 0004 and 0016 |
