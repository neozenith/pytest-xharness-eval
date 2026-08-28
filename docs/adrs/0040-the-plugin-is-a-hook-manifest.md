# 0040: The plugin is a hook manifest, and each job behind it is a module

Status: accepted, 2026-08-28. Refines
[0008](0008-evals-are-eval-prefixed-modules.md) (evals are `eval_*.py` modules),
[0014](0014-register-through-the-pytest11-entry-point.md) (register through the
pytest11 entry point),
[0016](0016-results-travel-on-the-test-report.md) (results travel on the test
report),
[0032](0032-all-run-output-consolidates-under-a-cache-dir.md) (all run output
consolidates under a cache dir),
[0037](0037-the-emitted-records-are-types-and-the-cache-tree-has-one-owner.md)
(the emitted records are types) and
[0039](0039-the-package-listing-is-the-architecture.md) (the package listing is
the architecture). Structural only: no serialised key, no ini key, no CLI option
and no metric's value changes; every hook keeps its name and its signature, and
the characterization goldens are byte-identical.

## Context

0039 turned the layers into folders and left the two entry points at the root,
where importlib resolves them. `plugin.py` was then the last module in the
package doing five unrelated jobs at once, at 478 lines: it registered the
options and ini keys, decided what pytest collects, ran a cell end to end,
carried the record across the xdist boundary, and wrote `report.json` and the
combine step. Three consequences, none of them stylistic:

| Symptom | What it cost |
| --- | --- |
| Two serialised contracts authored inside pytest hooks | `report.json` was a dict literal in `pytest_terminal_summary`. 0037 gave every other emitted document a type; this one had no definition to point a reader (or `report-ui/src/lib/types.ts`) at. |
| One `# pragma: no cover` over the whole per-cell sequence | `_run_live` was forty lines of which *one* spends money. Materialise, derive, capture, grade and record were excluded from coverage along with the spawn, so the ordering a replay is pinned against could not be exercised at all without paying. |
| The suite loader written twice | `plugin._load_module` and `replay._load_suite` were the same eight lines of `spec_from_file_location`, differing in whether the module was registered in `sys.modules` while it executed — a difference nobody had decided. "Find the `EvalCase` called X" was written twice as well. |

The last one is the drift class 0034 removed for the settings and 0037 for the
cache tree: two implementations of one idea, each correct, neither aware of the
other.

## Decision

**`plugin` is a package whose `__init__` is a manifest.** Pluggy discovers a hook
as an attribute of the imported plugin module and importlib resolves
`pytest_xharness_eval.plugin` to the package, so the `pytest11` entry point of
0014 is unchanged and every hook is re-exported by name from `__init__`:

```text
plugin/
    __init__.py   the hook manifest: seven hooks, bound to the modules below
    options.py    every option and ini key, configure-time validation, the header
    collect.py    the collection rule, EvalFile, EvalItem
    cell.py       CellRun: the seven steps of one live cell, and the run stamp
    verdict.py    Verdict: the words a cell may grade to
    results.py    the record's one crossing to the controller, and its status word
    summary.py    the terminal table, report.json, and the combine step
```

**The paid step is one method, and the pragma stops there.** `CellRun` is the
cell's run as a small state machine: `materialise`, `invoke`, `store`, `grade`,
`record`, and an `execute` that sequences them and leaves the record in the
item's stash whether the grader passed or raised. Only `invoke` — and the
five-line `execute` that calls it — carries `# pragma: no cover`; every other
step is now exercised from captured logs in `tests/test_units.py`. Nothing is
mocked to achieve that, which is the constraint 0002 actually imposes: the
workspace is really copied, the grader really runs, the record is really written,
and no CLI is spawned.

**`report.json` is a type.** `emit/summary.py` holds `RunSummary`: the graded
cells and `total_usd`, plus `cache_roots()` — the roots this session wrote
evidence into, which is the one place the combine step's trigger is decided and
the reason a dry run stays free (0018, 0032). The hook decides *when* to write;
the type decides *what* the file is.

**One `EvalSuite` loads every suite, for both entry points.** `model/suite.py`
imports an `eval_*.py` by path under a name derived from that path, registering
it in `sys.modules` before executing it, and answers `cases` and
`case_named(name)`. Collection asks it for every case; a replay asks
`find_case(evals_dir, name)`, which skips an unimportable suite with a warning so
one broken file cannot stop the others being rebuilt (0023).

**The pre-0032 migration is its own module.** `runtime/legacy.py` holds
`LegacyCapture`, built only by `found_at`, which recognises a legacy
`captured/` directory by shape and returns `None` for anything else — so a
migration cannot be started against a cache root, and the entry point has no
"is it legacy?" question left to ask twice. It is transitional code with a known
end, and it is now deletable in one file. `replay.py` keeps the rebuild and the
command line that drives it, and `main` takes its `argv` so the entry point can
be exercised without touching the process.

## Consequences

`from pytest_xharness_eval.plugin import EvalItem` still resolves — a consuming
repository's `conftest.py` uses it to inspect collected cells — as do
`PROPERTY`, `RESULTS_KEY` and `RECORD_KEY`. What changes is that
`pytest_xharness_eval.plugin` is now a package: `plugin.py` no longer exists as a
file, and the per-file-ignore that exempts the entry points from 0039's layer
rules is `plugin/*`.

Coverage of the plugin's own code went from 89% to 93–100% per module, not
because tests were added around the old shape but because the shape stopped
hiding six free steps behind one paid one.

`Verdict` is a `StrEnum`, and its `.value` — never the member — is what reaches an
`Outcome`. The record it becomes crosses to the xdist controller through execnet,
which serialises builtins only (0016), and a test pins that the stored verdict is
a plain `str`.

One thing deliberately did *not* move: the `run_*` functions that spawn each CLI
stay module-level in their adapters. Relocating uncovered paid code buys style
and costs an unverifiable diff.

## Lens

A plugin's entry-point module is a manifest, not a place to work. Every job it
accumulates is a job with no name, no test seam and no type — and the two most
expensive symptoms are always the same: a serialised format authored inside a
hook, where no reader can find its definition, and a `pragma: no cover` drawn
around a whole sequence because one line of it is expensive. Push the expensive
line down until the pragma fits it exactly; what is left above is free, ordinary
code that can be tested like any other.
