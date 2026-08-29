# 0037: The emitted records are types, and the cache tree has one owner

Status: accepted, 2026-08-28. Refines
[0016](0016-results-travel-on-the-test-report.md) (results travel on the test
report), [0018](0018-fixtures-directory-and-metrics-history.md) (the metrics
record), [0020](0020-captured-report-is-a-static-microsite.md) (the report is a
static microsite), [0032](0032-all-run-output-consolidates-under-a-cache-dir.md)
(all run output consolidates under a cache dir) and
[0035](0035-the-nouns-carry-their-own-invariants.md) (the nouns carry their own
invariants). Structural only: no serialised key and no metric's value changes,
and the characterization goldens are byte-identical.

## Context

0035 and 0036 gave the run record and its parts real types. Everything the
product *emits* was still a mapping assembled by hand:

| Emitted document | How it was built | What that cost |
| --- | --- | --- |
| `history.json` (one per session) | `history.metrics_of`, a 41-key dict literal | no type, no key set, `.get()` at every reader |
| `report/index.json` rows | `report._row`, a 35-key dict literal | the same, plus the row's derivation buried in it |
| `report.json` cells | the same records, plus a *fourth* shape for `--dry-run` | five keys where readers expected 41 |

These are wire formats. `report-ui/src/lib/types.ts` mirrors them, the glossary
names them, and nothing in this repository failed when one drifted.

Three further consequences of not having the types:

- **`cache` was stamped on afterwards.** `pipeline.record_metrics` called
  `history.metrics_of` and then wrote `record["cache"] = str(cache)` onto the
  mapping a different module had just built. The record's own definition did not
  mention the field the controller depends on to find the cache root (0032).
- **The dry-run record was a different document.** Five keys with the same
  `verdict` field, written onto `report.json` beside full ones.
- **A replay read `history.json` twice, by hand.** `replay.rebuild` and
  `replay.case_meta` each opened it, each caught `JSONDecodeError`, and each
  `.get()`-ed the keys it wanted.

The cache tree had the same problem one level down. The five-level layout of
0032 is a published contract — the page fetches
`../results/{skill}/{harness}/{model}/{run}/{session}/log.jsonl` by that exact
shape — and it was spelled out in five modules:

| Spelling | Where |
| --- | --- |
| `HISTORY_NAME` = `history.json` | `pipeline.py` |
| `HISTORY_NAME` = `history.jsonl` | `report.py` — the same name, a different file |
| `glob("*/*/*/*/*/result.json")` | `report.cells`, `report.aggregate_history`, `replay.rebuild` |
| `session_dir / "log.jsonl"` | both harness adapters and `report._row` |
| `<cache>/results` | `Settings.results_root`, a third spelling |

## Decision

**The two emitted documents are types.** `metrics.CellMetrics` is the
`history.json` record, with `status_word()` as a method on it and `cache` as a
declared field; `report.IndexRow` is one `index.json` row, with the derivation
from a stored `result.json` in its `of()` constructor. Both serialise through
`asdict`, as `RunResult` does (0035), so the field names remain the wire format.
`history.py` becomes `metrics.py`: it holds the record, not an append-only file.

**The dict boundary is explicit and singular.** `TestReport.user_properties` is
serialised by execnet, which handles builtins only (0016), so a dataclass there
fails at runtime during a paid sweep and never at type-check time. The record is
therefore `to_dict()`-ed at the `pytest_runtest_makereport` hook and
`from_dict()`-ed on the controller, and it is a type everywhere else. `from_dict`
drops unknown keys and defaults absent ones, which is also what makes a capture
written by an older version readable rather than fatal.

**A dry run emits the same document.** `CellMetrics.dry_run(node=, cell=)` builds
a full record with nothing measured and an empty `cache` — and empty `cache` is
what already means "combine nothing", so a dry run still writes no evidence
(0018).

**The cache tree has one owner.** `layout.CacheLayout` is a value object over the
cache root: `build/`, `results/`, `report/`, every file name under them, the
`session(skill=, harness=, model=, run=, session=)` constructor and the
`sessions()` walk. `layout.SessionDir` is one session's evidence directory and
addresses its four members by property. `Settings.cache` *is* a `CacheLayout`,
so no caller reassembles a path under it, and `SessionDir.at(path)` serves the
callers handed a directory rather than finding one — a replay, a harness adapter
re-reading its own captured log.

**The key sets are pinned by a test, against literal lists.** `tests/test_units.py`
asserts the exact keys of `history.json` and of an `index.json` row against
spelled-out lists, and `tests/test_plugin.py` asserts `report.json` is
`{cells, total_usd}`. A field added, renamed or dropped without the matching edit
to `types.ts` and the glossary fails the gate here, which is the only place in
this repository that could ever have caught it.

`history.append` is deleted. It had no production caller after 0032 moved the
metrics record beside its evidence, and its only exercise was its own test.

## Consequences

`pricing` no longer imports `history` for a timestamp: `now_iso` moves to
`normalise`, beside `ms_between`, with the other dialect-free primitives. That
removes the one edge from the pricing layer up into the metrics layer.

Reading a `history.json` that exists but is missing keys now yields `""` and `0`
where it yielded `None`. Only a hand-truncated or pre-0021 record reaches that
path; a session with no record at all still indexes as `null`, which is the case
the tests pin.

`report.py` keeps `INDEX_NAME`, `TOKENS_NAME` and `REPORT_DIR` in its namespace
(re-exported from `layout` and listed in `__all__`) because
`report-ui/scripts/inline.py` builds the page through them.

## Lens

A document a program emits is part of its interface, and an interface assembled
as a dict literal has no definition anywhere — only the union of what its readers
happen to ask for. Give it a type, put the one serialisation boundary where the
transport actually requires it, and pin its key set against a list a human wrote.
Then the same rule holds for the tree those documents live in: a path shape that
appears in five modules is not a layout, it is five layouts that currently agree.
