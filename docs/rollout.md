# What a rollout leaves you: the grader's surface

This is the reference for **what you can assert** in an `eval_*.py` case. A grader is
handed exactly one argument, a `CaseOutput`, and everything below hangs off it.

```python
from pytest_xharness_eval import CaseOutput, evalcase
from pytest_xharness_eval.verify import check_rollout

@evalcase(task="Apply the palette mandate to ARCHITECTURE.md", skill="mermaidjs-diagrams", fixture="unstyled_diagram")
def eval_palette_mandate(output: CaseOutput) -> None:
    check_rollout(output)                       # the evidence gate every case owes
    doc = output.read("ARCHITECTURE.md")        # the artifact the agent left behind
    assert output.wrote("ARCHITECTURE.md")      # ... and that this run is what produced it
```

Three ADRs govern this page: [0044](adrs/0044-a-skill-is-invoked-the-way-its-user-invokes-it.md)
(a case declares a *task*, the harness renders the invocation),
[0045](adrs/0045-the-verifiers-ship-with-the-plugin.md) (the shared checks, and this
surface) and [0046](adrs/0046-a-golden-is-compared-facet-by-facet-within-a-declared-tolerance.md)
(goldens).

## Contents

- [`CaseOutput`: the two halves](#caseoutput-the-two-halves)
- [`output.run`: what the CLI did](#outputrun-what-the-cli-did)
- [The bundled verifiers](#the-bundled-verifiers)
- [Goldens](#goldens)
- [What you may not assume](#what-you-may-not-assume)

## `CaseOutput`: the two halves

A rollout is a **record** and an **artifact**. The record is what the CLI reported about
itself; the artifact is the directory it worked in.

| Member | Type | What it is |
|---|---|---|
| `output.run` | `RunResult` | The normalised record: usage, cost, the per-call ledger, coverage, the record census. [Below.](#outputrun-what-the-cli-did) |
| `output.workspace` | `Path` | The directory the agent worked in: a fresh copy of `evals/fixtures/<fixture>/`. |
| `output.read(rel)` | `str` | The text of a workspace file. **Fails as an assertion**, naming what the workspace does hold, when the file is absent. |
| `output.path(rel)` | `Path` | The absolute path, for the cases that need to hand a file to a subprocess. |
| `output.exists(rel)` | `bool` | Whether the path is there at all. |
| `output.filenames` | `list[str]` | Every file in the workspace, relative and sorted. |
| `output.wrote(rel)` | `bool` | Whether *this run's diff* names the path. Not the same as `exists`. |
| `output.written` | `list[str]` | Every path the run created or modified. |
| `output.added` | `list[str]` | Written paths the fixture did **not** seed: what this rollout brought into being. |
| `output.changed` | `list[str]` | Written paths the fixture did seed: what it edited in place. |

The `exists` / `wrote` distinction is the one worth internalising. A fixture file the
agent never touched **exists**; it was not **written**. A case about editing something
that only checks `exists` passes for a run that did nothing at all.

## `output.run`: what the CLI did

### Identity and outcome

| Field | Type | Notes |
|---|---|---|
| `harness` | `str` | `claude` or `codex`, the first matrix axis. |
| `model` | `str` | The model id the harness was told to use. |
| `session_id` | `str` | The session this verdict is tied to. |
| `session_log` | `str` | Path to the captured JSONL. Exists on disk during grading. |
| `workspace` | `str` | The same directory as `output.workspace`, as the run recorded it. |
| `exit_code` | `int` | The CLI's process exit code. |
| `duration_ms` | `int` | Wall clock around the subprocess. |
| `final_text` | `str` | What the agent said last. Grade the artifact, not this. See [below](#what-you-may-not-assume). |
| `files_written` | `list[str]` | Behind `output.written`. |

### Cost

| Field | Type | Notes |
|---|---|---|
| `cost_status` | `CostStatus` | `PRICED` or `UNPRICED`. There is no third state. Compare to the enum member, not the string. |
| `estimated_cost_usd` | `float \| None` | This plugin's estimate from its own price table. |
| `cost_by_tier` | `dict[str, float]` | The estimate split by token tier. |
| `rates_applied` | `AppliedRates \| None` | **A typed record, not a dict.** `rates_applied.source`, `.model`. `.get()` raises. |
| `harness_reported_cost_usd` | `float \| None` | What the CLI itself claimed (Claude only). Never used to price. |

### Tokens

`run.usage` is a frozen `Usage`. The tiers are disjoint and priced separately.

| Field | Notes |
|---|---|
| `usage.input_tokens` | Uncached input. |
| `usage.output_tokens` | Generated, `reasoning_tokens` included. |
| `usage.cache_read_tokens` / `cache_write_tokens` | Kept apart because they price ~an order of magnitude apart. |
| `usage.accumulative_billed_tokens` | The four priced tiers summed over every call. **A spend figure, not a context figure.** |
| `run.baseline_tokens` | The first call's prompt: what the harness loads before the agent acts. |
| `run.peak_context_tokens` | The largest prompt any one call processed. |
| `run.context_window` / `context_window_pct` | The window the harness reported, and how close the run came to it. |
| `run.ttft_ms`, `run.output_tokens_per_sec` | Timing. |

`docs/token-accounting.md` has the derivation and the provider quotations behind it.

### The ledger

`run.calls` is one `Call` per model API call, a *SessionTurn* in the report.

| Field | Notes |
|---|---|
| `call.n`, `call.at` | Turn number and timestamp. |
| `call.usage` | That call's own `Usage`. |
| `call.text`, `call.thinking` | What it said and thought. |
| `call.tools` | `list[ToolCall]`: `.name`, `.summary`, `.input` (the full payload), `.id`. |
| `call.results_in` | `list[ToolResult]`: what entered the context before this call. `.content` is complete, never truncated. |
| `call.records` | The 1-based session-log lines this turn owns. |
| `call.latency_ms`, `call.context_tokens` | Per-turn timing and prompt size. |

`run.turns` is `len(run.calls)`. `run.tool_calls` is a `{name: count}` roll-up across
every turn, the quick way to ask "did it ever call Bash".

`run.subagents` is a `list[Subagent]`, one per parallel thread the session spawned, each
with its own `.calls`, `.usage`, `.parent_turn` and captured `.log`. Their usage is
already folded into `run.usage`, so the run's bill is the whole bill.

### Skill coverage

`run.skill_coverage` is a `SkillCoverage` **dataclass** (`None` only if the pipeline never
annotated it). Reach it by attribute:

| Member | Notes |
|---|---|
| `.loaded` / `.not_loaded` | Skill files the run did and did not read. |
| `.run` / `.not_run` | Skill *scripts* it did and did not execute. |
| `.files` | `list[FileCoverage]`, per-file and per-turn detail. |
| `.summary` | The counts behind the report's coverage column. |

> `run.skill_coverage.get("run")` raises `AttributeError`. Four suites in one repository
> had drifted into exactly that, so those cells were *erroring*, not grading, which is
> the reason `verify/` exists at all (ADR 0045).

### Provenance

`run.case` is a `CaseRef` naming what produced the run: `.suite`, `.name`, `.skill`,
`.fixture`, `.task` (what the case declared) and `.prompt` (what this harness actually
sent). `run.record_kinds` is the census of session-log record kinds.

## The bundled verifiers

`from pytest_xharness_eval.verify import ...`. Each returns on success and raises
`AssertionError` naming what went wrong, in the agent's terms.

| Verifier | Asserts |
|---|---|
| `check_rollout(output)` | **Start every case with this.** The run is real *and* priced. |
| `check_run_is_real(output)` | Session id, log on disk, clean exit, non-zero billed tokens. |
| `check_run_is_priced(output)` | A positive estimate with rate provenance. |
| `check_files_written(output, *paths)` | The run's diff names each path. |
| `check_no_files_added(output, allow=())` | It edited in place and added nothing. `allow` takes `fnmatch` patterns, e.g. `["OUT.md", ".scratch/*"]`. |
| `check_file_unchanged(output, path, expected)` | A block survived character for character. |
| `check_tools_used(output, *names)` | Each tool was invoked at least once. |
| `check_subagents_spawned(output, at_least=1)` | It delegated, read off captured transcripts, so it means the same in both dialects. |
| `check_turns_within(output, at_most=, at_least=)` | A plausible turn count. |
| `check_skill_was_loaded(output, *paths)` | It read the named skill files. **Name resources, not `SKILL.md`**, see below. |
| `check_skill_scripts_ran(output, *paths)` | It executed the skill's mandatory gates. |

Anything else is a plain function beside your case. That has always been the contract
(ADR 0013), and these are only the ones everybody was writing anyway.

## Goldens

When you can write down what a correct answer looks like, commit one at
`evals/goldens/<name>/<path>`, mirroring `evals/fixtures/<name>/<path>`, and compare
facet by facet, each with a declared tolerance.

```python
from pytest_xharness_eval.verify import Count, Exact, Facet, GoldenCase, Jaccard, facets

GOLDEN = GoldenCase.at(
    EVALS, "unstyled_diagram", "ARCHITECTURE.md",
    [
        Facet(name="fences", extract=facets.fence_count, tolerance=Exact(),
              why="the fence must be styled, never replaced or duplicated"),
        Facet(name="nodes", extract=facets.node_ids, tolerance=Jaccard(at_least=0.9),
              why="the fixture fixes what exists; only the naming is the agent's"),
        Facet(name="unstyled", extract=facets.unstyled_nodes, tolerance=Count(lo=0, hi=0),
              why="the mandate is that NO node is left on Mermaid's default"),
    ],
)
```

| Tolerance | Holds when | Use for |
|---|---|---|
| `Exact()` | equal | the part with one right answer |
| `Superset()` | candidate ⊇ golden | a required floor, additions allowed |
| `Jaccard(at_least=)` | set overlap ≥ threshold | naming freedom over a fixed concept set |
| `Ratio(at_least=)` | `difflib` similarity ≥ threshold | prose that must stay recognisable |
| `Count(delta=)` / `Count(lo=, hi=)` | count near the golden's, or in a range | structure with legitimate slack |
| `Within(lo=, hi=)` | a number in a closed range | a measure with a defensible band |

Extractors in `verify.facets`: `fence_count`, `fences`, `visible_fences`,
`collapsed_fences`, `node_ids`, `edges`, `classdef_names`, `classdef_count`,
`fill_colours`, `text_colours`, `unstyled_nodes`, `headings`, `headings_at(n)`,
`hex_colours`, `body_text`. Any `str -> object` works.

`GOLDEN.assert_matches(output)` raises `GoldenMismatch` (an `AssertionError`, so the cell
grades `fail`, not `error`) carrying one row per facet, passing ones included, with what
was missing and what was extra:

```
ARCHITECTURE.md is outside the golden's tolerances (1 of 3 facets failed)
  golden: skills/mermaidjs-diagrams/evals/goldens/unstyled_diagram/ARCHITECTURE.md
  [ok  ] fences  (exact: equal)
  [FAIL] nodes  (overlap >= 0.90: overlap 0.71)
           why: the fixture fixes what exists; only the naming is the agent's
           golden:    ['Loader', 'Report', 'Transform']
           candidate: ['Ingest', 'Report', 'Transform']
           missing:   ['Loader']
           extra:     ['Ingest']
  [ok  ] unstyled  (count in [0, 0]: 0)
```

`GOLDEN.record(output)` writes a run's output into the golden path, for creating or
deliberately regenerating a reference. It is never called during grading, a run that
could launder its own output into the reference would make every later comparison vacuous.

## What you may not assume

- **Not that the artifact is there.** `output.read` fails as an assertion for exactly this
  reason; say `check_files_written` when you mean the run produced it.
- **Not that `final_text` says anything.** A skill's contract is almost always about the
  file. Grade the file.
- **Not that both harnesses look alike in the ledger.** Tool *names* differ per dialect,
  prefer `check_subagents_spawned` over counting `Task` calls, and reach a provider's shell
  vocabulary through the registry rather than a set union.
- **Not that a fixture file is pristine.** The agent may have edited anything in the
  workspace; `check_file_unchanged` is how you say it must not have.
- **Not that a passing run read the skill.** Getting the right answer without loading the
  skill under test is a real outcome, and `check_skill_was_loaded` is how you distinguish
  it from the one you meant to measure.
- **Not that `SKILL.md` appears in coverage.** The two dialects disagree, and not about
  the skill. `claude` resolves `/<skill>` by *injecting* `SKILL.md`, so the agent never
  reads it and it never appears in `loaded`; `codex` is told to read the file itself, so
  it does. Asserting it passes on one arm and fails on the other for a harness reason,
  the "two different experiments" failure ADR 0044 exists to end. Name the `resources/`
  and `scripts/` files it points at instead: both dialects reach those when they follow
  the skill. `check_skill_was_loaded` has no default and refuses an empty call.
- **Not that the skill's own `evals/` tree is out of reach by accident.** It is excluded
  from what either harness ships to the agent (`harness/base.py`), because it holds the
  fixtures and the goldens, the answer key.
