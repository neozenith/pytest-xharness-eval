# 0032: All run output consolidates under `.xharness_eval_cache/`, and the report is one combine step

Status: accepted, 2026-08-27. Refines
[0014](0014-register-through-the-pytest11-entry-point.md) (path resolution),
[0018](0018-fixtures-directory-and-metrics-history.md) (history) and
[0020](0020-captured-report-is-a-static-microsite.md) (the microsite); supersedes
0018's `captured/` location, 0020's one-report-per-captured-directory rule, and the
`xharness_workdir` ini key.

## Context

Run output used to land in two conventions at once: per-cell workspaces and
`report.json` under `tmp/evals/` (`xharness_workdir`), and evidence under each
skill's own tree at `<skill>/evals/captured/<case>/` with a shared, appended
`history.jsonl` beside it. Three pressures broke that shape:

- A sweep across several skills produced several disconnected reports and no page
  over the whole run; the SPA had grown multi-skill affordances with no index that
  ever exercised them.
- Build artifacts accumulated inside `skills/` — the source tree — and every
  consuming repo needed its own git-ignore lines for them.
- The shared `history.jsonl` was the one file two parallel writers could contend
  on, which is exactly the problem pytest-cov solves with suffix files: every
  writer owns a unique path, and a single combine step aggregates.

## Decision

One git-ignored root, resolved against the pytest rootdir through the new
`xharness_cache_dir` ini key (default `.xharness_eval_cache`, matching the common
`.*_cache/` ignore convention). `xharness_workdir` is gone.

```text
.xharness_eval_cache/
  build/                                   # per-cell isolated workspaces
  results/{skill}/{harness}/{model}/{run_ts}/{session_id}/
    log.jsonl                              # the session log, verbatim
    result.json                            # the derived RunResult (replayable)
    history.json                           # one metrics record
  report/
    report.json                            # the last run's summary
    history.jsonl                          # aggregated from results/**/history.json
    index.json, report.html, report.tokens.json, XHARNESS-REPORT-GLOSSARY.md
```

- **Suffix convention.** A cell writes only inside its own
  `{run_ts}/{session_id}/` directory — no shared file, no lock, full
  parallelisation under xdist. `run_ts` is one UTC stamp per pytest session
  (`YYYYMMDDTHHMMSSZ`, exported as `XHARNESS_EVAL_RUN_TS` so xdist workers agree),
  so repeated runs accumulate side by side instead of overwriting.
- **One combine step.** At session end (and on every replay) the report step walks
  everything under `results/` — every skill, every run — aggregates the per-session
  `history.json` records into `report/history.jsonl`, and writes one `index.json`
  and one `report.html` into `report/`. Index rows point at evidence by relative
  path (`../results/…`), so serving the cache root serves the whole report:
  `python3 -m http.server --directory .xharness_eval_cache` →
  `/report/report.html`.
- **Replay is also the migrator.** `python -m pytest_xharness_eval.replay <cache>`
  rebuilds every result under `results/` as before; pointed at a legacy
  `<skill>/evals/captured` directory it migrates that evidence into the project's
  cache (the original is left untouched) and then rebuilds.
- **Plain files stay.** Everything remains human-readable `.json`/`.jsonl`; a
  database or columnar format is complexity to adopt when scale demands it, not
  before.

## Consequences

- Skills directories no longer accumulate run output, and one `.*_cache/` ignore
  line covers everything.
- The report is a sweep-level page: multiple skills, multiple runs, one index. The
  SPA needed no data-contract change — index rows were always opaque relative
  paths.
- `report.json` moves from `tmp/evals/` to `.xharness_eval_cache/report/`.
- Consuming repos drop `xharness_workdir` from their pytest config;
  `xharness_cache_dir` exists for the rare override.
