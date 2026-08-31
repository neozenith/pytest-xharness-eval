# xharness report glossary

The names on this page are the vocabulary for talking about `report.html`. Every
element carries its CamelCase name in the page (the small monospace tag beside a
heading, or the element's `id`), every metric keeps its `snake_case` JSON key, and
every session and turn has an id you can copy from the page and paste into a URL.

## Ids

| Id | Form | Example | Where to find it |
|----|------|---------|------------------|
| `SessionId` | the harness-minted session UUID (Claude `--session-id`; Codex rollout id) | `87c58138-7c63-4c22-8eed-337d1b7cbd12` | the dashed badge in `SessionTitle`; click to copy. `SessionRow` carries it as `data-sid` but no longer prints it: the row opens the `SessionView` that does |
| `SessionTurnId` | `<SessionId>/t<N>`, `N` = 1-based model call | `87c58138-7c63-4c22-8eed-337d1b7cbd12/t3` | the dashed badge in `SessionTurnRow`; click to copy |
| `RecordCard` anchor | `L<line>` | `#L42` (element id inside the page) | each record card's `id`; the card header says `line 42` |

A unique prefix of a `SessionId` is accepted everywhere a full one is (`87c58138`).
Shorthand in conversation: `S:87c58138` for a session, `S:87c58138/t3` for a turn,
`S:87c58138/t3/L42` for one record of that turn.

## URL routes (stateful deep links)

```text
report.html                                           SweepOverview
report.html?sort=turns&dir=desc                       SweepOverview, SessionTable sorted by that column
report.html?ssort=cost&sdir=desc                      SweepOverview, SessionSummaryTable sorted by that column
report.html?skill=discovery                           SweepOverview, only that skill
report.html?harness=claude,codex                      SweepOverview, either harness (comma-separated multi-select)
report.html?skill=discovery&harness=claude&model=claude-opus-5   all three at once (OR within a facet, AND across facets)
report.html?session=<SessionId>                       SessionView, summary view
report.html?session=<SessionId>&view=detailed         every SessionTurnDetails expanded
report.html?session=<SessionId>&turn=3                turn 3 expanded and scrolled into view
report.html?session=87c58138&turn=3&view=detailed     prefix form, both at once
report.html?session=<SessionId>&axis=line             the four charts on the session-log-line axis
report.html?session=<SessionId>&rec=raw               every RecordCard as raw JSON
report.html?session=<SessionId>&line=17               log line 17's RecordCard, its turn opened, flashed
report.html?…&theme=dark                              forced theme, on any route
```

Full History-API routes, no fragment router: navigating pushes a real history entry
(back/forward walk the pages you visited) and in-place controls rewrite the current
entry, so the address bar is always a link to what you are looking at. Query
strings, not path segments, because this one static file must route with zero
server rewrites and over `file://` (ADR 0020, ADR 0031). A param absent from the
URL means its default — the URL alone reproduces the whole state — and a legacy
`#session=…` fragment link is upgraded to its query form on load.
`lib/permutations.ts` enumerates the covering matrix of these states for the
Playwright sweep, one deterministic slug per state. An absent `skill`, `harness` or
`model` means **every** value of that facet, and so does a present-but-empty one
(`?skill=`); a value the sweep does not contain matches nothing, so a stale filter
deeplink lands in a visible empty state rather than silently showing everything
(ADR 0042).

## Turn boundaries

A `SessionTurn` is one model API call. Its `records` (the log lines shown under
`TurnRawRecords`) are, by cause rather than by file order:

- the call's own records (Claude: every content block of that `message.id`; Codex:
  everything between the previous `token_count` and its own);
- the results of the tools **that turn issued**, matched by `tool_use_id`, even when
  Claude Code wrote them between the turn's later blocks;
- the harness records written while that turn was in progress; records before the
  first call belong to the first call.

So each turn's lines are one contiguous range, shown in `SessionTurnRow` and in the
`TurnRawRecords` heading. `results in` keeps its own meaning: what entered the
turn's context, which is the previous turn's results.

## Design tokens and standalone reports

`report.tokens.json` sits beside `report.html` and is the page's palette: per-theme
colours (`bg`, `panel`, `ink`, `muted`, `line`, `accent`, `good`, `bad`, `warn`,
`code`, `grid`, `axis`, `plot`), the chart `series`, the `waterfall` colours, the
highlight.js style, the `fonts`, and the `categories` pill colours. Edit it and
refresh. To brand every report, point the project at your own file:

```toml
[tool.pytest.ini_options]
xharness_report_design_tokens = "branding/xharness.tokens.json"
xharness_report_inline = false
```

or per run: `pytest ... --xharness-report-design-tokens FILE`, `make evals-replay`
with `--design-tokens FILE`. A missing or malformed file is an error.

`--xharness-report-inline` (ini `xharness_report_inline`, replay `--inline`) writes a
standalone `report.html` with the index, every result and log, and the tokens
embedded; it opens over `file://` and needs no server, at the cost of size and of
going stale when a cell re-runs. The CDN libraries (Plotly, highlight.js, ansi_up)
are still fetched.

## Replay (no spend)

```text
uv run -m pytest_xharness_eval.replay skills/<skill>/evals/captured
make evals-replay SKILL=<skill>
```

Rebuilds every `.result.json` from its captured log and stored envelope, re-prices,
re-annotates skill coverage against the current tree and ignore rules, rewrites the
matching `history.jsonl` lines (verdict, timestamps, wall clock kept), and regenerates
`index.json` and `report.html`. Use it after a plugin change or an `xharness_skill_ignore` edit.

## Metrics

| Metric (JSON key) | Definition | Calculation |
|-------------------|------------|-------------|
| `estimated_cost_usd` | this plugin's price-table estimate | `Σ tier_tokens × rate` using `rates_applied`; cache writes tagged `ephemeral_1h` at `cache_write_1h`, the rest at `cache_write` |
| `harness_reported_cost_usd` | what the harness CLI itself said the run cost | Claude: `total_cost_usd` from the stdout envelope (includes a ~$0.001 session-title side call); Codex: none |
| `rates_applied` | provenance of the estimate | per-tier USD per token, the row key, its source (`xharness_prices` for an ini row, the bundled `prices.toml` path otherwise), and when it was applied |
| `accumulative_billed_tokens` | every billed token | `Σ over turns (input + output + cache_read + cache_write)`; the cached prefix counts once per turn that re-read it, so on a long run this exceeds the context window many times over; it is a spend figure, never a context figure |
| `baseline_tokens` | the harness's own prompt before the agent acts | `input + cache_read + cache_write` of turn 1 |
| `turns` | model API calls | Claude: distinct `message.id`; Codex: `token_count` events. `reported_turns` is the CLI's own count (Claude: tool calls + 1; Codex: tasks, always 1) |
| `tool_calls` | tool invocations issued | Claude: `tool_use` blocks; Codex: completed `CommandExecution` / `FileChange` / `Extension` items |
| `wall_ms` | harness wall clock around the subprocess | `time.monotonic()`; `duration_ms` is the CLI's self-reported figure |
| `case` (on the result) | which question produced the run | `suite` (the `eval_*.py` path), `name`, `skill`, `fixture`, `task`, `prompt`; history carries all but the two strings |
| `task` | what the case declared, in the words a user would use *after* naming the skill | identical on every arm of a case; the case's `@evalcase(task=...)` (ADR 0044) |
| `prompt sent` | what actually reached the CLI | the harness's own invocation rendered around `task` — `/<skill> <task>` for claude, `$<skill> <task>` for codex. Differs per arm by design (ADR 0044) |
| per-turn `context_tokens` | the prompt that one turn processed | `input + cache_read + cache_write` of that turn (shown only in `SessionTurnRow`) |
| `context_window` | the model's context window as the harness reported it | Claude: `modelUsage[<model>].contextWindow`; Codex: `model_context_window` |
| per-turn `context_pct` | how full the window was for that turn | `context_tokens / context_window`; measured by the provider, so earlier thinking the server kept or dropped is already inside it |
| `peak_context_tokens` | the largest prompt any one turn processed | `max(context_tokens)` over turns; the token figure behind `context_window_pct`, on the history line and the index. The full derivation, with provider quotations and a worked session, is `docs/token-accounting.md` in the plugin repository |
| `context_window_pct` | peak consumption, the top-level figure | `peak_context_tokens / context_window`; always read with `context_window` |
| `final_context_pct` | where the run ended | `(last turn's context_tokens + its output_tokens) / context_window` |
| `ttft_ms` | time to first token | Claude: envelope `ttft_ms`; Codex: `task_complete.time_to_first_token_ms` |
| `output_tokens_per_sec` | generation rate | output tokens over `api_duration_ms` (Claude `duration_api_ms`; Codex `task_complete.duration_ms`), else agent `duration_ms` |
| per-turn `latency_ms`, `output_tokens_per_sec` | how long a turn took | wall time from the previous log record to the turn's first record (request + generation; on Claude this includes harness time between tool result and request), and output over it |
| `record_kinds` | census of the session log | count of log lines per record kind (see the catalogue below) |
| `skill_coverage` | which skill files the run touched | per file: `ignored` flag, `loaded` turns, `run` turns; derived `not_loaded` and `not_run` sets (ignored files excluded); `summary` counts incl. `ignored`. History carries `skill_files`, `skill_files_loaded`, `skill_scripts`, `skill_scripts_run`, `skill_not_loaded`, `skill_not_run` |

### How skill coverage is detected

The skill's files are catalogued when the suite is collected (path, kind, bytes,
sha256), excluding `evals/`, `node_modules/`, caches and dotfiles. Kinds: `doc`
(markdown, text), `script` (`.py .ts .js .sh .mjs`, `Makefile`), `test`
(`test_*.py`, `*.test.ts`, `conftest.py`; never expected to run), `asset` (the rest).
A tool call **loads** a file when its arguments contain `<skill>/<path>`; a shell
call **runs** a script when an interpreter (`bun`, `uv`, `python`, `node`, `bash`,
`sh`, `npx`, `./`) precedes that path; a `Skill` tool invocation loads `SKILL.md`.
Shell commands are read at the working directory the shell actually had (ADR
0027): a `cd` in a Claude `Bash` call persists into later calls until the
harness reports `Shell cwd was reset to …`, Codex execs run at their `workdir`,
and a relative path in a command running under the skill directory (`cd <skill>
&& cat SKILL.md`, then `bun run scripts/gate.ts`) counts as that skill file.

### What is not decision surface: `xharness_skill_ignore`

Files that live in the skill directory but are not part of what an agent decides
over (example galleries, lockfiles, linter configs, the skill's own tests) are
declared in the project's `xharness_skill_ignore` pytest ini key (ADR 0026), one
gitignore-style glob per line. A bare line applies to every skill; `<skill>: <glob>`
applies to the skills whose directory name matches the `fnmatch` selector, the way
pytest's `markers` lines pair a name with its text. Supported: `**`, `*`, `?`,
`{a,b}`, a trailing `/` for a directory, `#` comments; a pattern with no `/`
matches at any depth. Not supported: `!` negation, nested braces. Ignored files stay
in the catalogue flagged `ignored` (toggle "show ignored files" in
`SkillCoveragePanel`) and are excluded from every denominator and from
`not_loaded` / `not_run`.

```toml
[tool.pytest.ini_options]
xharness_skill_ignore = [
    "README.md",
    "mermaidjs-diagrams: resources/examples/**",
    "mermaidjs-diagrams: scripts/{Makefile,CLAUDE.md}",
    "mermaidjs-diagrams: scripts/*.json",
    "mermaidjs-diagrams: scripts/*.test.ts",
]
```

## Elements

| Element | Contains | Purpose |
|---------|----------|---------|
| `Report` | `ReportHeader`, `NavSidebar`, `SweepOverview`, `SessionView` | the page |
| `NavSidebar` | `NavToggle`, an Overview link, then skill → suite → harness → model → one entry per session (verdict dot, case, short id); the open session lists section jump-links | the collapsible left navigation; every tree level starts collapsed (the reader opts in, and the active session's ancestors open themselves); collapse is remembered locally, never routed |
| `ReportHeader` | `ReportTitle`, `ReportMeta`, `ThemeToggle` | sticky chrome; `ReportTitle` is the report's name on the sweep and the `eval · session · harness · model` tuple inside a `SessionView` (the tab title follows it) |
| `SweepOverview` | `OverviewFilters`, `OverviewCharts`, `SessionSummaryTable`, `SessionTable` | every captured session at a glance; the header meta names every skill the sweep spans; the view owns the filtering and hands the same filtered cells to all three consumers |
| `OverviewCharts` | `TokenAccumulationChart` and `TokenWaterfallAggregateChart`, side by side | the pair is one question asked two ways over the same filtered population — how fast the bill grows, and where it went — so they are read against each other rather than one at a time. A `repeat(auto-fit, minmax(460px, 1fr))` grid: side by side from ~1150px, stacked below it rather than squeezed to a width their axes cannot carry, and each chart's legend wraps beneath its own plot once its column is narrower than plot + legend rail. Both notes reserve four lines so the two plots start on the same line at every width the pair is a row |
| `OverviewFilters` | one chip row per facet — skill, harness, model — each chip carrying its cross-filtered session count, and a status cluster holding `OverviewFiltersClear` and, set to the card's right edge, `OverviewFilterCount` | the one global filter on the overview, held in the URL, rippling through all three consumers. It is chrome, not a panel: an eyebrow heading in the page's eyebrow voice — 12/600/0.5 uppercase, muted, the same spec the `NavSidebar` sets — rather than a card title, so the data below it is not pushed down the page. `OverviewFilterCount` reads `N of M sessions` while a filter is on and `M sessions` when none is, so the selection is legible without reading the chips; a selected chip carries a mark as well as the accent, so lit and unlit are told apart at a glance and a chip is the same width either way; a facet with one distinct value says so; a chip that would select nothing is hollowed out, not hidden, and stays clickable; a *selected* value the sweep does not contain — what a stale deeplink leaves behind — still renders as a chip, lit, dashed and counting 0, so a selection is never invisible. Nothing in the bar changes size when it lights up, at any width: the chip mark is always in the DOM; `OverviewFiltersClear` is always rendered and merely hidden (`aria-hidden`, out of the tab order) while nothing is selected, so its box is reserved in both states; `OverviewFilterCount` holds a hidden sizer printing the widest sentence it can ever say, so its box is too; and each facet key holds a fixed column outside the wrapping chip box, so a wrapped chip line starts where every other chip line starts. The undo sits before the count so the count, the one part always present, holds the right edge in both states. `OverviewFilterCount` is a `role="status"` live region, so a chip toggle announces the new N of M; `OverviewFiltersClear` hands focus to the first chip as it unmounts |
| `SessionSummaryTable` | one row per skill × case × harness × model group with its run count and its mean measures; `SummaryCount` in the title says how many groups, as `SessionCount` says how many sessions | the aggregate view of exactly the runs `SessionTable` lists, one row per line of `TokenAccumulationChart`; every mean is named `mean <field>` and is over the runs that carry that field. Sortable on its OWN param pair (`ssort=`/`sdir=`), because a reader ranks groups by mean cost while ranking sessions by when they ran, and a shared pair would make every click here silently reorder the table below. Unsorted, rows come out in a fixed key order and are banded by skill, and a value repeating the row above's recedes to the muted ink so the first row of each band leads; **both the banding and the repeat muting switch off the moment a column is sorted**, because under any other order "the row above" is whatever the reader last clicked and a band would be drawing a grouping the table is no longer in. A group that did not pass clean takes `bad` ink on its `pass rate` fraction, which is this table's answer to the `VerdictBadge` rail one table below. Its rows are a readout, not links: unlike `SessionTable`'s they take no hover wash and go nowhere, which is the whole of the altitude difference between the pair. Its heads are the same `ColumnHead` component `SessionTable`'s are, so the pair's heads are one object rather than two that happen to agree: the printed label is the short form, the accessible name keeps the canonical field name beside it, and the definition reaches a pointer through the tooltip and a screen reader through `aria-describedby` on a visually-hidden span (the tooltip alone opens for pointer events only, which left the only spelling-out of `mean output_tokens_per_sec` unreachable by keyboard). Nothing in its *body* is focusable, so its scroll box is itself the tab stop — `role="region"`, labelled, and focusable only while columns are actually clipped — or the data past its right edge would be reachable by pointer alone |
| `SessionTable` | one `SessionRow` per session | sortable (`sort=`/`dir=`); a row opens its `SessionView`. **Budgeted to one screen**: every metric is present, but the session id is no longer a column (the row opens the view that prints it beside a `CopyId`; `data-sid` still carries it), `estimated_cost_usd` and `harness_reported_cost_usd` are one `cost` column reading the estimate with the harness's own figure as a muted signed drift from it, token counts are abbreviated (`1.5M`, `29.4k`) with the exact figure on the cell's `title`, `model` drops its vendor prefix and `case` the `eval_` every case shares, and each head prints the shortest form that still reads while keeping the canonical field name in its tooltip and accessible name. `accumulative_billed_tokens (billed)` is the cross-turn billed sum and `peak ctx` reads `peak_context_tokens · context_window_pct` (the window itself on the title), two different quantities; the `coverage` column reads `loaded/files · run/scripts` |
| `SessionView` | in order: `SessionHeader`, `TokenWaterfallChart`, `ContextWindowChart`, `ReconciliationPanel`, `CostByTierPanel`, `OutputPerTurnChart`, `TurnTiersChart`, `SkillCoveragePanel`, `RecordKindsPanel`, `SessionTurnTable`, `FinalMessagePanel` | one session |
| `SessionHeader` | `SessionTitle` (with the `SessionId` badge), `SessionMetaTable` | identity, verdict, the suite file / case / skill / fixture under test, the declared `task` and the `prompt sent`, evidence links, workspace, context window and peak / final consumption, time to first token, output tokens per second, timings, in one key/value table |
| `ChartAxisToggle` | `per turn` / `per session-log line` | the x-axis of the four charts below (`axis=` in the fragment); per line, a value holds from the record that measured it until the next measurement (a step), turn starts are marked, nothing is interpolated |
| `ChartLegend` | one chip per series, coloured by the design tokens | the charts' legend: a right-hand column beside the plot, scrolling past the chart height; a chip toggles its series |
| `ContextWindowChart` | per turn: one point per turn plus `final_context_pct`; per line: a step of the latest measured `context_pct` | how close the run came to the window, qualified by the window size in the axis title |
| `ReconciliationPanel` | ledger versus harness aggregate, per tier | proves the ledger matches the CLI's own totals |
| `CostByTierPanel` | USD per tier, harness per-model estimate, `RatesApplied` | how `estimated_cost_usd` was built and from which rates |
| `TokenWaterfallAggregateChart` | the same six categories and total as `TokenWaterfallChart`, averaged over every run in view: one column per turn index plus `baseline` and `total`, with a min–max whisker per column | where the tokens went, across many runs rather than one — the decomposition to `TokenAccumulationChart`'s accumulation, over the same filtered population. Each column is the arithmetic mean over the runs that *reached* that turn (a short run is missing from a late turn, never zero in it), so the stack's top is the mean running total and the whisker brackets the real runs behind it; the hover reports how many runs each column averages. The `total` column is each run's own final total, so on runs of unequal length it sits above the last turn's column rather than level with it |
| `TokenWaterfallChart` | per turn: `baseline_tokens`, then per turn cache read, new context, thinking, visible output and the whole bill of any subagents that turn spawned, ending at `accumulative_billed_tokens`; per line: the same categories as a stacked step area of cumulative tokens; the right-hand axis carries the running `estimated_cost_usd` as a line | where the tokens (and dollars) went |
| `OutputPerTurnChart` | thinking and visible output stacked, per turn or at each turn's measuring line | how much of each turn's output was reasoning |
| `TurnTiersChart` | the four billing tiers stacked, per turn or at each turn's measuring line | what each turn was billed for |
| `SkillCoveragePanel` | `SkillCoverageSummary` chips (the `files`, `loaded`, `run`, `not_loaded`, `not_run`, `ignored` chips are filters; click again to clear), one row per catalogued skill file with its loaded / run turns and status | which decision paths the run took through the skill |
| `RecordKindsPanel` | one pill per record kind with its count | the census of this session's log |
| `SessionTurnTable` | `ViewToggle`, `RecordViewToggle`, one `SessionTurnRow` per turn, each with a `SessionTurnDetails`; a turn that spawned subagents is followed by a `SubagentBand` | the ledger; Summary shows rows, Detailed expands every turn. Harness-specific: `SessionTurnTableClaude` carries the explicit cache-write tiers (`cache_write`, `1h`), `SessionTurnTableCodex` drops them (implicit caching) and shows `cached input` / `input (uncached)`; the panel carries `data-harness` |
| `SubagentBand` | per spawned thread: an agent pill in the waterfall's `sub` colour, its id, the spawn description, its turn/billed-token totals, and one `SubagentTurnRow` per call of its own ledger | the parallel threads a turn spawned (`subagents` in `result.json`); each thread's transcript is captured under `subagents/` beside `log.jsonl` and its bill is folded into the session's `usage` and `estimated_cost_usd`, attributed to the spawning turn (`parent_turn`) |
| `SessionTurnDetails` | `TurnRawRecords` | the session-log records attributed to that turn, untruncated |
| `TurnRawRecords` | the turn's line range, then one `RecordCard` per log line (`records` in the ledger) | the evidence itself, line-numbered |
| `RecordCard` | header: category-coloured kind pill, `L<line>`, the record's timestamp (`HH:MM:SS.mmm`), size, a context annotation (`ctx 7.2%` = the turn's measured prompt; `→ t4 7.5%` on a tool result = the next turn's prompt it became part of), a `raw`/`nice` flip and a permalink button (sets `line=` in the fragment and copies the URL); body: the rendered view or the raw JSON | one log line; `RecordViewToggle` flips every card at once. Harness-specific bases: `RecordCardClaude` renders the `claude/*` catalogue, `RecordCardCodex` the `codex/*` one; the card carries `data-harness` |

### How `SessionSummaryTable` aggregates

The grouping key is **skill × case × harness × model** — deliberately the same
partition `accumulationGroups` draws with, so one summary row is one line of the
`TokenAccumulationChart` above it and the two read as a pair. Rows come out in that
key order ascending (a null skill last); the table is not sortable, because its
sortable twin sits directly beneath it.

**The one mean rule**, applied to every `mean_*` column: the arithmetic mean over the
runs in the group that carry a value. A missing value is skipped, never zero-filled,
and the divisor is the count of present values rather than `runs`; an aggregate over
nothing is `–`, never `0`, so a sparse column reads as sparse.

**Mean, not median**, deliberately: the chart beside it already draws a mean line with
a min–max envelope, and a median row would disagree with that picture by construction;
cost and tokens are additive, so `mean × runs` is the group's total — the arithmetic a
reader actually does — while a median has no such relation; and a median over the group
sizes this data produces (1–2) is either the single value or the mean of the two. The
column names say `mean …` in full (ADR 0021), so the choice is never inferred.

The **pass rate**'s denominator is the runs that carry a verdict, not `runs`: an
ungraded run is never counted as a failure, and the cell says how many have no history.

| Column | What it is |
|--------|------------|
| `skill`, `case`, `harness`, `model` | the group's key |
| `runs` | captured sessions in this group; every mean below is over these runs |
| `verdict pass rate` | runs whose verdict is `pass`, over the runs that carry a verdict |
| `mean estimated_cost_usd` | arithmetic mean of `estimated_cost_usd` |
| `mean accumulative_billed_tokens` | arithmetic mean of the cross-turn billed sum; a spend figure, not a context figure |
| `mean peak_context_tokens` | arithmetic mean of the largest prompt one turn processed, with the mean `context_window_pct` and the window |
| `mean turns` | arithmetic mean of model API calls |
| `mean tool_calls` | arithmetic mean of tool invocations issued |
| `mean skill_coverage loaded share` | arithmetic mean of `loaded/files` per run, ignored files excluded, runs with no catalogue skipped |
| `mean output_tokens_per_sec` | arithmetic mean of output tokens per second of API time |
| `mean wall_ms` | arithmetic mean of wall clock around the subprocess |

### How a `RecordCard` is rendered

One component library, composed bottom-up, so every record reuses the same parts.
Every renderer wraps its output in `<div class="comp" data-el="<name>">` and the name
is drawn in the corner, so the HTML of a `RecordCard` reads in this table's vocabulary:
`RecordCard` › `R.claude/assistant/tool_use` › `claudeMessage` › `B.tool_use` › `T.Bash`
› `V.bash`. The names are `V.<value>`, `T.<tool>`, `B.<block type>`, `claudeMessage` /
`codexItem`, `R.<kind>`, with `T.fallback`, `B.fallback` and `R.fallback` for shapes no
renderer claims.

| Level | Components | Examples |
|-------|-----------|----------|
| values | `text`, `kvs`, `code(lang)`, `json`, `bash`, `diff`, `output` (sniffs JSON / diff / plain), `ansi`, `xmlish` (one titled block per top-level XML element), `listing` (`- name: description` lines as a table), `flag`, `usage`, `envelope` | a highlighted shell command; an `<environment_context>` block; the skill listing as a table; a token usage grid; the collapsible record envelope |
| tool payloads | one renderer per tool: `Bash`, `Read`, `Edit` (old/new as a diff), `MultiEdit`, `Write` (content by file type), `Skill`, `Glob`, `Grep`, Codex `exec` (the `cmd` inside `tools.exec_command({...})` as a shell block, `apply_patch` bodies as diffs; full JavaScript collapsed) | `claude/assistant/tool_use`, `codex/response_item/custom_tool_call` |
| blocks | one renderer per content block type: `text`, `thinking`, `tool_use`, `tool_result`, `input_text`, `output_text`, `Text` | Claude message content, Codex item content |
| messages | `claudeMessage` (blocks + model + stop reason + usage), `codexItem` | assistant records, `item_completed` events |
| records | one renderer per kind in the catalogue below, plus a JSON fallback for unseen kinds | the `RecordCard` body |

Highlighting is highlight.js, bundled into the page with a github-style token palette
that follows the theme (nothing is fetched at view time, ADR 0028). Tool output that
carries terminal colour codes renders in colour through `ansi_up`, also bundled;
nothing is stripped, so the raw JSON and the rendered view carry the same bytes. Scripts whose output is captured into logs should still default to
plain text and take a `--color` flag, as the mermaid gate scripts do.
| `FinalMessagePanel` | the agent's final message | what the harness returned as the result |

## Record kinds

Every session-log line has a **kind** (`harness/type[/subtype]`) and every kind a
**category**. The pill on a `RecordCard` is coloured by category, so the colour
changes exactly when the category of information changes. The catalogue lives in
`records.py` and is mirrored in the page; an unseen shape shows as `<harness>/unknown`.

| Category | Pill | Carries |
|----------|------|---------|
| `prompt` | `#1d4ed8` | what the user (or the harness, as the user) said |
| `assistant_text` | `#065f46` | what the model said in prose |
| `thinking` | `#6d28d9` | reasoning blocks (text usually omitted or encrypted by the CLI) |
| `tool_call` | `#4338ca` | a tool the model asked to run, with its full arguments |
| `tool_result` | `#0f766e` | what came back from a tool and entered the context |
| `tool_exec` | `#9a3412` | the harness's record of actually executing a command |
| `file_change` | `#be185d` | a diff the harness applied |
| `usage` | `#b45309` | token accounting events |
| `harness_context` | `#3f6212` | context the harness injected: skill and agent listings, deferred tools, developer messages |
| `harness_meta` | `#475569` | bookkeeping: titles, reminders, queue operations, world state |
| `session_meta` | `#1e3a8a` | session and turn configuration: cwd, model, sandbox, base instructions |
| `lifecycle` | `#b91c1c` | task started / completed |
| `unknown` | `#374151` | a shape not in the catalogue |

| Kind | Category | Rendered view shows |
|------|----------|---------------------|
| `claude/user/prompt` | prompt | the prompt text |
| `claude/user/injected` | harness_context | a user-role message that opens with an XML tag: harness-injected, not the prompt under test; rendered as titled blocks per element |
| `claude/user/tool_result` | tool_result | per block: `tool_use_id`, `is_error`, the full content; `toolUseResult` collapsed |
| `claude/assistant/text` | assistant_text | the text, model, stop reason, usage |
| `claude/assistant/thinking` | thinking | the thinking text (or that it was omitted), signature size, usage |
| `claude/assistant/tool_use` | tool_call | tool name, id, full input JSON, model, stop reason, usage |
| `claude/assistant/synthetic` | harness_meta | a message Claude Code wrote itself (`model: "<synthetic>"`, zero usage), e.g. `API Error: The response stopped arriving`; not a turn |
| `claude/attachment/total_tokens_reminder` | harness_meta | the reminder text |
| `claude/attachment/deferred_tools_delta` | harness_context | added and removed tool names |
| `claude/attachment/agent_listing_delta` | harness_context | added agent types and their listing lines |
| `claude/attachment/skill_listing` | harness_context | the full skill listing |
| `claude/attachment/auto_mode` | harness_meta | the mode flags |
| `claude/attachment/task_reminder` | harness_meta | item count |
| `claude/ai-title` | harness_meta | the generated session title |
| `claude/atis-latch` | harness_meta | the latch value |
| `claude/last-prompt` | harness_meta | the last prompt text |
| `claude/queue-operation` | harness_meta | operation, time, content |
| `codex/session_meta` | session_meta | cwd, CLI version, provider, source, context window; base instructions collapsed |
| `codex/turn_context` | session_meta | model, cwd, approval and sandbox policy, network, personality |
| `codex/response_item/message/user` | prompt | the prompt text |
| `codex/response_item/message/user/injected` | harness_context | `<environment_context>`, `<recommended_plugins>`: harness-injected user-role messages, rendered as titled blocks per element |
| `codex/response_item/message/developer` | harness_context | the injected developer message (`<permissions>`, `<skills_instructions>`, `<multi_agent_mode>`, ...), as titled blocks per element |
| `codex/response_item/message/assistant` | assistant_text | the text and phase |
| `codex/response_item/reasoning` | thinking | the summary (or that it is encrypted), encrypted size |
| `codex/response_item/custom_tool_call` | tool_call | tool, call id, status, full input |
| `codex/response_item/custom_tool_call_output` | tool_result | call id, full output |
| `codex/event_msg/task_started` | lifecycle | turn id, context window, mode |
| `codex/event_msg/task_complete` | lifecycle | duration, time to first token, last message |
| `codex/event_msg/token_count` | usage | this call's and the cumulative usage |
| `codex/event_msg/item_completed/AgentMessage` | assistant_text | the text and phase |
| `codex/event_msg/item_completed/CommandExecution` | tool_exec | command, cwd, status, exit code, output |
| `codex/event_msg/item_completed/FileChange` | file_change | per file: change type and unified diff |
| `codex/event_msg/item_completed/Reasoning` | thinking | the reasoning summary |
| `codex/event_msg/item_completed/UserMessage` | prompt | the prompt text |
| `codex/event_msg/item_completed/UserMessage/injected` | harness_context | the event mirror of an injected user-role message |
| `codex/world_state` | harness_meta | whether the snapshot is full, then each state flag as ✓ / ✗ |

Also catalogued without a live example yet: `claude/system`,
`codex/response_item/message/system`, `codex/response_item/function_call`,
`codex/response_item/function_call_output`.

## Containment

```mermaid
treemap-beta
"Report":::page
    "ReportHeader":::chrome
        "ReportTitle":::chrome
        "ReportMeta":::chrome
        "ThemeToggle":::chrome
    "SweepOverview":::overview
        "OverviewFilters":::overview
        "OverviewCharts":::overview
            "TokenAccumulationChart":::overview
            "TokenWaterfallAggregateChart":::overview
        "SessionSummaryTable":::overview
        "SessionTable":::overview
            "SessionRow":::overview
    "SessionView":::session
        "SessionHeader":::session
            "SessionMetaTable":::session
        "ChartAxisToggle":::session
        "ReconciliationPanel":::session
        "CostByTierPanel":::session
        "TokenWaterfallChart":::session
        "ContextWindowChart":::session
        "OutputPerTurnChart":::session
        "TurnTiersChart":::session
        "SkillCoveragePanel":::session
        "RecordKindsPanel":::session
        "FinalMessagePanel":::session
        "SessionTurnTable":::turns
            "ViewToggle":::turns
            "RecordViewToggle":::turns
            "SessionTurnRow":::turns
                "SessionTurnDetails":::details
                    "TurnRawRecords":::details
                        "RecordCard":::details
                "SubagentBand":::turns
                    "SubagentTurnRow":::turns
classDef page fill:#1e3a8a,stroke:#bfdbfe,color:#fff
classDef chrome fill:#475569,stroke:#e2e8f0,color:#fff
classDef overview fill:#7c3aed,stroke:#ddd6fe,color:#fff
classDef session fill:#065f46,stroke:#a7f3d0,color:#fff
classDef turns fill:#b45309,stroke:#fde68a,color:#fff
classDef details fill:#b91c1c,stroke:#fecaca,color:#fff
```

Colour encodes nesting level: page, chrome, overview, session, turns, turn details.
