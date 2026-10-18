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
(goldens). [0074](adrs/0074-a-case-may-be-a-scenario-and-its-fixtures-may-be-generated.md)
adds scenario cases, generated fixtures and the precheck, and
[0075](adrs/0075-an-analyzer-is-a-checker-over-every-sample.md) adds analyzers: checks
over every sample rather than one rollout.

## Contents

- [`CaseOutput`: the two halves](#caseoutput-the-two-halves)
- [What a case declares](#what-a-case-declares)
- [`Seed`: what a precheck is handed](#seed-what-a-precheck-is-handed)
- [`output.run`: what the CLI did](#outputrun-what-the-cli-did)
- [The bundled verifiers](#the-bundled-verifiers)
- [Goldens](#goldens)
- [Analyzers: checks over every sample](#analyzers-checks-over-every-sample)
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
| `output.added` | `list[str]` | Written paths the fixture did **not** seed: what this rollout brought into being. A treatment's files count as seeded (ADR 0055). |
| `output.changed` | `list[str]` | Written paths the fixture or treatment did seed: what it edited in place. |
| `output.scenario` | `Scenario \| None` | The generated scenario this rollout ran on: `.id`, `.params`, `.expect`, `.files` (the seed exactly as the agent first saw it), `.task`, `.fingerprint`. `None` for a committed fixture directory (ADR 0074). |
| `output.params` | `dict` | The scenario's `params` and `expect` merged: what it is, and the knobs the grader holds it to. **Fails as an assertion** on a committed fixture, which has none. |
| `output.seed(rel)` | `str` | The text `rel` had before the agent touched it, read from the scenario. **Fails as an assertion** when the scenario did not seed `rel`, or on a committed fixture. |

The `exists` / `wrote` distinction is the one worth internalising. A fixture file the
agent never touched **exists**; it was not **written**. A case about editing something
that only checks `exists` passes for a run that did nothing at all.

## What a case declares

`@evalcase(task=None, fixture=, skill=None, models=None, treatments=None, tracks=None, precheck=None)`.

| Argument | What it does |
|---|---|
| `task` | For a skill case, what a user types *after* naming the skill (ADR 0044). For a scenario case, the whole prompt, sent verbatim to every harness. A generated case may omit it when every scenario carries its own task; a scenario left with none stops collection. |
| `skill` | The skill under test. **Omit it for a scenario case**: no skill is registered, and coverage and skill use stay `None`. |
| `fixture` | A directory name under `evals/fixtures/`, or a fixture generator whose every scenario becomes its own cells, `eval_x[<scenario id>/<cell id>]`. |
| `tracks` | Paths, relative to the project root, absolute, or outside it, whose content digest is recorded as `subject_version`. A skill case tracks its skill directory less `evals/` by default. |
| `precheck` | A function over the [`Seed`](#seed-what-a-precheck-is-handed) that raises when the input no longer sets up what the case is about. It runs before the paid invoke, and under `--dry-run`. |

The generators ship in `pytest_xharness_eval.model.generators`. Generation runs at
collection on every xdist worker, so a generator and its oracle must be deterministic.

| Generator | Yields |
|---|---|
| `Table(name, rows, build, version=1, label=None, task=None, expect=())` | One scenario per row; `build(row)` returns its files, `task` is a format string over the row. The row keys named in `expect` become the scenario's expectations: they reach the grader through `output.params` but not the scenario id, so tuning one keeps its history. |
| `Generated(name, build, count, seed=0, version=1, task=None)` | `count` scenarios, `build(draw)` returning `(params, files)` from `Draw(name, version, seed, i)`. A `label` key in the params labels the id. |
| `from_dir(name, root, transform=None)` | One scenario per subdirectory of `root`, each text file optionally rewritten by `transform(path, text)`. |
| `Promoted(name, source=None, task=None)` | Every promoted fixture under `evals/fixtures/` (of generator `source`). None found collects no cells and warns by name, so a regression case may exist before its first promotion. `task` is a format string over each scenario's params and expectations that replaces its frozen task, so a task naming one machine's path (the tool under test) is rendered afresh; the bytes and the id are untouched. |
| `Adversarial(name, seeds, mutators, budget, seed=0, depth=2, oracle=None, version=1, attempts=20)` | Re-runs stored mutants that failed, up to half the budget, then new mutants of `seeds`' scenarios, screened by the free `oracle`. Each mutant's params are its parent's plus a `mutation` record (parent, mutators, generation, attempt); its `expect` is its parent's. A search that finds nothing new warns rather than failing collection. [Its fields](#adversarial-field-by-field) and [the mutators](#mutators) are below. |

A failing scenario is frozen into a regression fixture with
`uv run -m pytest_xharness_eval.promote <scenario or session dir> <evals dir> [--name NAME]`.

### Writing your own generator

`@evalcase(fixture=)` takes anything that satisfies the `FixtureGenerator` protocol
(`from pytest_xharness_eval import FixtureGenerator`). It is runtime-checkable, so
`@evalcase` refuses a class that lacks any of its three members:

| Member | What it must be |
|---|---|
| `name: str` | The generator's name. It is digested into every scenario id it yields. |
| `may_be_empty: ClassVar[bool]` | **Declared, never defaulted.** `False` stops collection when the generator yields nothing; `True` only for a generator whose empty sweep is an answer (a regression case before its first promotion, an exhausted search), which collection names in a warning. |
| `scenarios(self, context: GenerationContext) -> Iterable[Scenario]` | The scenarios to run this sweep, in a stable order. It runs at collection on every xdist worker, so it must be deterministic: draw randomness only through `Draw`. |

A minimal generator, one scenario per line width:

```python
from __future__ import annotations

import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar

from pytest_xharness_eval import CaseOutput, GenerationContext, Scenario, evalcase
from pytest_xharness_eval.model.scenario import read_tree
from pytest_xharness_eval.verify import check_rollout


@dataclass(frozen=True)
class Wrapped:
    """The seed notes, hard-wrapped at each width: the agent must rewrap them at 80."""

    name: str
    widths: tuple[int, ...]
    version: int = 1                          # bump when the same params start writing new bytes
    may_be_empty: ClassVar[bool] = False      # an empty sweep is a broken suite

    def scenarios(self, context: GenerationContext) -> Iterator[Scenario]:
        seed = read_tree(context.evals_dir / "seeds" / "notes")    # bytes, keyed by POSIX path
        text = seed["notes.md"].decode("utf-8")
        for width in self.widths:
            yield Scenario(
                generator=self.name,
                version=self.version,
                params={"target": "notes.md", "width": width},     # what it is: in the id
                expect={"max_width": 80},                          # a grader knob: not in the id
                files={"notes.md": textwrap.fill(text, width) + "\n"},
                label=f"width-{width}",
                task="Rewrap notes.md so that no line is longer than 80 characters.",
            )


@evalcase(fixture=Wrapped(name="notes-wrapped", widths=(40, 120, 200)), tracks=["tools/rewrap"])
def eval_rewrap(output: CaseOutput) -> None:
    check_rollout(output)
    limit = int(output.params["max_width"])
    assert all(len(line) <= limit for line in output.read("notes.md").splitlines())
```

A module beside the suite (a `_shared.py` holding the seed table, the oracle and the
command a check runs) is imported by bare name: the plugin puts the evals directory on
`sys.path` before it imports a suite, so it needs no `conftest.py` (ADR 0074). Its name
must not start with `eval_`, or it is collected as a suite.

#### `GenerationContext`: what collection hands `scenarios`

| Field | Type | What it is |
|---|---|---|
| `context.evals_dir` | `Path` | The suite's `evals/` directory: where a generator reads seed material. |
| `context.case` | `str` | The case function's name. |
| `context.outcomes` | `Mapping[str, tuple[int, int]]` | Scenario id to `(failed, sampled)` over every stored record of this case: where the subject already breaks. Empty on a first sweep. |
| `context.store` | `ScenarioStore \| None` | Where collection writes this case's scenarios (`<cache>/scenarios/<suite path>/<case>/`); `None` for a generator asked outside a sweep, which then sees no history. `.stored()`, `.provenance(id)` and `.lineage()` read it back. |
| `context.stored` | `dict[str, Path]` | Every complete scenario tree in the store, by id; empty without a store. |

#### `Scenario`: one generated fixture

`Scenario(generator, params, files, version=1, label=None, task=None, expect={})`, frozen
and keyword-only.

| Field | What it is | In the id? |
|---|---|---|
| `generator` | The generator's `name`. | yes |
| `version` | Bump it when the same params start producing different bytes. | yes |
| `params` | What the scenario *is*: the inputs that made it. JSON-able. | yes |
| `label` | A readable name for the id's slug; without one, the slug is the canonical params. | the slug only |
| `files` | Workspace-relative POSIX path to `str` or `bytes`. Must not be empty. | no: the fingerprint |
| `expect` | What the grader holds it to (a threshold, a ratio). JSON-able, and no key may also be in `params`. | no |
| `task` | This scenario's prompt, overriding the case's `task`. | no |

The rules that follow from those columns:

- **The id is `<slug>--<8 hex>`.** The slug is `label` (or the params) lowercased to
  `[a-z0-9-]`; the hex is the start of `scenario.key`, the digest of generator, version and
  canonical params. It never depends on a list position, so inserting a row renumbers
  nothing. Renaming a label or the generator starts a new history.
- **The fingerprint is the digest of `files`.** Two records of one id with different
  fingerprints measured different inputs, and the Analyzer never pools them. That is the
  signal to bump `version`.
- **The grader reads `params` and `expect` merged** as `output.params` (`scenario.merged`);
  a precheck reads the same as `seed.params`.
- **A bad scenario fails at construction.** A non-JSON param or expectation raises
  `TypeError`; empty `files` or a key in both `params` and `expect` raises `ValueError`.

`scenario.write(dest)` writes the tree, `scenario.provenance()` is the `Provenance` record
kept beside a stored copy, and `Scenario.promoted(dir)` reads a stored or promoted tree
back, refusing one whose bytes no longer match its recorded fingerprint.

#### `Draw`, `read_tree` and `write_tree`

`Draw(*seed)` is a seeded source of choices that stays reproducible across Python versions:
`.random()`, `.integer(low, high)` (both ends included), `.choice(options)`, `.chance(p)`,
`.shuffled(items)` and `.sample(items, k)`. Seed it from the generator's name, version and
an index, as `Generated` does, never from `hash()`.

`from pytest_xharness_eval.model.scenario import Files, read_tree, write_tree`:

| Name | What it does |
|---|---|
| `Files` | `dict[str, str \| bytes]`: the type of `scenario.files`, and what a mutator and an oracle take. |
| `read_tree(root)` | Every file under `root` as `Files` with **`bytes`** values, skipping `__pycache__`, `node_modules` and `.git`. Raises `FileNotFoundError` for a missing directory. The way to start from material already on disk, such as a linter's own rule fixtures. |
| `write_tree(files, dest)` | Writes `files` under `dest`, emptying it first, and raises `ValueError` for a path that escapes it. What an oracle uses to put a candidate on disk for the subject's own tool. |

An oracle runs on every xdist worker at once, so it writes to a directory per process
(`<project>/tmp/oracle/<pid>/`, say), and never under `evals/fixtures/`, which is copied
into every workspace.

#### Mutators

A mutator is any `Callable[[Files, Draw], Files]` that returns a new tree and leaves its
input alone; the name the mutant records is its `__name__`. The shipped ones are
`TextMutator`s in `pytest_xharness_eval.model.generators`. Each rewrites one drawn file
ending in `.md`, `.mmd`, `.markdown` or `.txt` (`TEXT_SUFFIXES`) whose content is text:
a `str`, or `bytes` that decode as UTF-8 (so a tree read with `read_tree` mutates as it is);
a binary file is never touched, and the mutated file is written back as a `str`.

| Constant | What it does to the drawn file |
|---|---|
| `CRLF` | Every line ending becomes `\r\n`. |
| `TRAILING_WHITESPACE` | Appends one to three spaces to some non-empty lines. |
| `ZERO_WIDTH` | Appends a zero-width space to some words. |
| `DUPLICATE_PARAGRAPH` | Repeats one paragraph in place. |
| `SHUFFLE_PARAGRAPHS` | Reorders every paragraph after the first. |
| `NO_FINAL_NEWLINE` | Strips the trailing newline. |
| `NBSP` | Turns some spaces into non-breaking spaces. |
| `TEXT_MUTATORS` | The tuple of all of the above. |

Write your own as `TextMutator(name, apply, suffixes=TEXT_SUFFIXES)`, where
`apply(text, draw)` returns the new text:

```python
from pytest_xharness_eval.model.generators import TextMutator
from pytest_xharness_eval.model.scenario import Draw


def _tabs(text: str, draw: Draw) -> str:
    return "\n".join("\t" + line[4:] if line.startswith("    ") and draw.chance(0.5) else line for line in text.split("\n"))


TABS = TextMutator("tabs", _tabs)
```

#### `Adversarial`, field by field

| Field | Default | What it does |
|---|---|---|
| `name` | required | The adversary's name: its mutants' `generator`, and what `Promoted(source=)` names. |
| `seeds` | required | The `FixtureGenerator` whose scenarios are the parents. One that yields nothing raises. |
| `mutators` | required | The mutators drawn from; empty raises. |
| `budget` | required | At most this many scenarios per sweep: stored failed mutants first (up to half, worst first), then new ones. |
| `seed` | `0` | Salts every draw. |
| `depth` | `2` | Each mutant applies one to `depth` distinct mutators, chained. |
| `oracle` | `None` | `Callable[[Files], frozenset[str]]`, free and deterministic (a linter's rule ids). A mutant is kept only if its signal set is non-empty and new to this sweep. |
| `version` | `1` | Digested into each mutant's id, like a scenario's. |
| `attempts` | `20` | Mutants drawn per kept scenario before the search gives up. |

A parent is drawn with weight `(f + 1) / (n + 2)` over its mutants' stored outcomes, so a
seed whose offspring broke the subject is mutated more. A mutant's `params` carry
`MUTATION_KEY` (`"mutation"`, importable from `model.scenario`): a precheck that tests the
seed for exactly one rule may relax to `exactly=False` when that key is present, since a
mutation can add findings.

## `Seed`: what a precheck is handed

A precheck gates the *input*. A grader asks whether the agent did the task; a precheck asks
whether the task is still there to do. It is handed a `Seed`, the workspace as the agent
will first find it: the fixture or scenario materialised, any treatment copied over it,
and nothing run yet.

| Member | Type | What it is |
|---|---|---|
| `seed.workspace` | `Path` | The materialised workspace. |
| `seed.scenario` | `Scenario \| None` | The generated scenario, or `None` for a committed fixture. |
| `seed.path(rel)` | `Path` | The absolute path of `rel` in the workspace. |
| `seed.read(rel)` | `str` | The seeded text of `rel`. |
| `seed.params` | `dict` | The scenario's params and expectations merged. Raises `ValueError` on a committed fixture. |

Anything a precheck raises, a failed assertion included, is the fixture's fault rather than
the agent's: the cell errors as a `RunError`, nothing is billed and no record is written.
`require_seed_fails` and `scratch_dir` accept a `Seed` as well as a `CaseOutput`:

```python
from pytest_xharness_eval import CaseOutput, Seed, evalcase
from pytest_xharness_eval.verify import require_seed_fails

def seed_reproduces(seed: Seed) -> None:
    target, rule = seed.params["target"], seed.params["rule"]
    require_seed_fails(seed, seed.read(target), [*LINT, "--json"], rules={rule}, name=target)

@evalcase(fixture=RULES, precheck=seed_reproduces)
def eval_lint_fix(output: CaseOutput) -> None: ...
```

`pytest --dry-run` materialises every seed and runs its precheck, so a fixture that has
drifted from its rule is found for free.

## `output.run`: what the CLI did

### Identity and outcome

| Field | Type | Notes |
|---|---|---|
| `harness` | `str` | `claude` or `codex`, the first matrix axis. |
| `model` | `str` | The model id the harness was told to use. |
| `effort` | `str \| None` | The reasoning rung the CLI was asked for, resolved to that harness's own ladder; `None` when the cell named none and inherited the CLI's default. The third matrix axis (ADR 0049). |
| `treatment` | `str \| None` | The treatment copied over the fixture; `None` for the control. The opt-in fourth matrix axis (ADR 0055). |
| `line` | `str \| None` | The model's product line from the catalogue, such as `opus` or `sol` (ADR 0057). |
| `family_tier` | `int \| None` | The model's hand-curated role in its lineup, 1 the smallest, frozen at release (ADR 0057). |
| `released` | `str \| None` | The model's release date, `YYYY-MM-DD` (ADR 0057). |
| `timed_out_after_s` | `int \| None` | The wall-clock limit the CLI was killed at; `None` when it finished on its own (ADR 0064). |
| `idle_before_timeout_s` | `float \| None` | How long the session's logs had been silent when it was killed. Under 300s the cell fails (it ran out of time); 300s or more, or no log, it errors (it had stalled) (ADR 0064). |
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
| `rates_applied` | `AppliedRates \| None` | **A typed record, not a dict.** `.source`, `.harness`, `.model`, `.unit` (`"usd_per_mtok"`), `.effective_from` / `.effective_to` (ISO dates, `None` when open), `.long_context` (a `LongContext` with `.above_prompt_tokens` and the five tier rates, or `None`); the tier rates are USD per MTok (ADR 0050, ADR 0051). `.get()` raises. |
| `long_context_calls` | `int \| None` | How many calls were billed at the row's long-context tier; `None` while unpriced (ADR 0051). |
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
| `run.output_tokens_per_sec_by_model` | `dict[str, float]`: throughput per model that answered, over calls with a measured latency; a subagent naming no model counts under its parent's (ADR 0071). |
| `run.reasoning_share` | `reasoning_tokens / output_tokens`, in `[0, 1]`; `None` when nothing was generated (ADR 0071). |
| `run.cache_read_share` | `cache_read / (input + cache_read + cache_write)` over the whole run, subagents included; `None` with no prompt tokens. |
| `run.compactions` | `int`: how many times the primary thread compacted its context, counted off `record_kinds` (ADR 0071). |

`docs/token-accounting.md` has the derivation and the provider quotations behind it.

### The ledger

`run.calls` is one `Call` per model API call, a *SessionTurn* in the report.

| Field | Notes |
|---|---|
| `call.n`, `call.at` | Turn number and timestamp. |
| `call.usage` | That call's own `Usage`. |
| `call.text`, `call.thinking` | What it said and thought. |
| `call.tools` | `list[ToolCall]`: `.name`, `.summary`, `.input` (the full payload), `.id`. |
| `call.executed` | `list[ExecutedCommand]`: `.tool`, `.command`, `.cwd` — the shell commands the harness itself reported as run this turn, after its own expansion. Empty for a harness that logs no such record (ADR 0048). |
| `call.results_in` | `list[ToolResult]`: what entered the context before this call. `.content` is complete, never truncated. |
| `call.records` | The 1-based session-log lines this turn owns. |
| `call.latency_ms`, `call.context_tokens` | Per-turn timing and prompt size. |

`run.turns` is `len(run.calls)`. `run.tool_calls` is a `{name: count}` roll-up across
every turn, the quick way to ask "did it ever call Bash".

`run.subagents` is a `list[Subagent]`, one per parallel thread the session spawned, each
with its own `.calls`, `.usage`, `.parent_turn` and captured `.log`. Their usage is
already folded into `run.usage`, so the run's bill is the whole bill. Each also names the
`.model` that answered it and carries its own `.estimated_cost_usd`, priced at that model's
rates rather than its parent's (ADR 0065). `run.subagent_token_share` and
`run.subagent_cost_share` are their part of the billed tokens and of the estimate, in
`[0, 1]`; the cost share is `None` while the run is unpriced or a subagent carries no
estimate (ADR 0071).

Every subagent is linked to the record that spawned it, at any depth, or the run fails
with `SubagentMismatch` rather than grading (ADR 0072). `.spawned_by` is that record's id,
`.parent` the spawning thread's id (empty for the primary), `.depth` 1 for a thread the
primary spawned, and `.parent_turn` the primary turn it descends from. `.started_at` and
`.ended_at` are its transcript's earliest and latest timestamps; `.duration_ms` is the span
and `.output_tokens_per_sec` its output tokens over the summed latency of its timed calls.

### Tool calls and skill use

Each `ToolCall` carries `.started_at`, `.ended_at` and `.duration_ms`, read off the records
that issued it and answered it (ADR 0073). `run.tool_costs` is one `ToolCost` per tool
call of every thread (`.thread` empty for the primary): `.issuing_cost_usd` is the issuing
call's cost split across its tools, and `.context_cost_usd` is its result's share of every
later prompt that carried it, with `.trace` per turn, `.cache_rereads` and the estimated
`.result_tokens`. Both are attributions, never part of `run.estimated_cost_usd`.
`run.skill_use` is the skill under test's `SkillUse` (`None` when nothing triggered it):
`.trigger`, `.triggered_turn`, `.last_turn`, `.duration_ms`, `.tool_calls`, both costs,
and `.events`, one per skill file access.

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

`run.case` is a `CaseRef` naming what produced the run: `.suite`, `.name`, `.skill` (the
subject), `.fixture`, `.task` (what the case declared) and `.prompt` (what this harness
actually sent), `.kind` (`skill` or `scenario`), `.scenario`, `.scenario_fingerprint`,
`.scenario_params` and `.subject_version` (ADR 0074). `run.record_kinds` is the census of session-log record kinds.

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

### Budgets and behaviours (`verify.conduct`)

Read off the run's measured fields. A figure the pipeline never attached (an unpriced run,
no tool costs, no skill use) fails the check rather than passing it.

| Verifier | Asserts |
|---|---|
| `check_cost_within(output, usd)` | `run.estimated_cost_usd`, subagents included, is at most `usd`. |
| `check_wall_within(output, seconds)` | `run.duration_ms` is at most `seconds`. |
| `check_context_within(output, pct, threads="primary")` | The largest prompt of the primary thread (`threads="all"`: of any thread) is at most `pct` of `run.context_window`. **Raises `Unmeasurable`** (a `RuntimeError`, so an `error`) when the harness reported no window. |
| `check_no_compaction(output)` | `run.compactions == 0`. Primary thread only: no harness counts a subagent's compactions. |
| `check_cache_efficiency(output, min_cache_read_share)` | `run.cache_read_share` (`cache_read / (input + cache_read + cache_write)` over the whole run) is at least the share. |
| `check_no_timeout(output)` | `run.timed_out_after_s is None`: the CLI was not killed at the wall (ADR 0064). |
| `check_no_long_context(output)` | `run.long_context_calls == 0`; fails on an unpriced run (ADR 0051). |
| `check_tool_calls_within(output, at_most=, name=None)` | At most `at_most` tool calls in any thread, of `name` when given: counted off every thread's ledger, like the duration and cost checks, not off the primary-only `run.tool_calls`. |
| `check_tool_durations_within(output, ms, name=None)` | No `ToolCall.duration_ms` in any thread exceeds `ms`; lists the slowest. |
| `check_tool_cost_within(output, usd, name=None, kind="issuing")` | The matching `run.tool_costs` sum to at most `usd`, by `issuing` or `context` attribution (ADR 0073); `kind` is a `CostKind` word, and an unknown one raises `ValueError`. |
| `check_commands_ran(output, *patterns)` | Each regex matches a shell command of some thread: shell tool calls read through the harness's own vocabulary, plus `call.executed`. |
| `check_skill_triggered(output, by=None, within_turns=None)` | `run.skill_use` exists, its `.trigger` is `by` (`"prompt"` or a tool name), and `.triggered_turn <= within_turns`. Turns are the primary's; a subagent's touch counts at the primary turn its spawn descends from. |
| `check_skill_cost_within(output, usd, kind="issuing")` | The skill's tool calls cost at most `usd`. |
| `check_subagents_within(output, at_most=None, max_depth=None)` | At most `at_most` subagents, none deeper than `max_depth`. |
| `check_subagent_durations_within(output, ms, agent=None)` | No subagent's `.duration_ms` exceeds `ms`. |
| `check_subagent_cost_within(output, usd, agent=None)` | No subagent's own `.estimated_cost_usd` exceeds `usd`, per thread; a thread with no estimate fails. |

### Content kept (`verify.content`)

The other half of every fixer's verdict: a quiet tool alone is reachable by deleting the
text. Each takes the seed explicitly as `seed_text`; for a generated scenario that is
`seed_text=output.seed("doc.md")`. "Prose" is the document minus fenced code, inline
code spans and HTML comments; words are lowercased, stopwords dropped, crudely stemmed.

| Verifier | Asserts |
|---|---|
| `check_absent(output, path, pattern, why=)` | `pattern` no longer occurs. A `str` matches literally, a compiled `re.Pattern` as a regex. The message quotes each matching line. |
| `check_matches(output, path, regex, at_least=1)` | The regex (a `str` is compiled, multiline) matches at least `at_least` times. |
| `check_content_kept(output, path, seed_text, at_least=0.9, per_sentence=0.5)` | The seed's content words survive at `at_least` recall, and every seed sentence keeps `per_sentence` of its own, so no sentence went whole. |
| `check_length_kept(output, path, seed_text, ratio=(lo, hi))` | The prose word count is within `lo`x to `hi`x the seed's: rewritten, not compressed. |
| `check_nothing_hidden(output, path, seed_text)` | No new fence line and no new inline code span: prose was not moved where a gate skips it. |
| `check_fences_kept(output, path, seed_text, lang=None)` | At least as many fences (of `lang`) as the seed. |
| `check_ids_kept(output, path, seed_text, extractor)` | Everything `extractor` (a facet such as `facets.node_ids` or `facets.entities`) finds in the seed is still there. |

### The tool under test (`verify.tool`)

Runs the *user's* tool on the workspace, never an agent CLI. A tool that cannot start,
hangs past `timeout_s`, exits outside `ok_codes`, or prints no parseable report raises
`Unmeasurable` (a `RuntimeError`, from `model.verdict`), which grades `error`, never `fail`: lint-style CLIs exit 1 for findings
and for some crashes alike, and only a report tells them apart.

| Name | What it does |
|---|---|
| `run_tool(output, argv, cwd=None, ok_codes=(0,), env=None, timeout_s=120)` | Runs `argv` (default `cwd` the workspace; `env` merged over the current one) and returns a `ToolRun`: `.argv`, `.returncode`, `.stdout`, `.stderr`, `.json()`, `.tail()`. |
| `findings(output, argv, json_key="findings", ok_codes=(0, 1))` | The tool's JSON findings list (`json_key=None` for a top-level list). |
| `check_tool_passes(output, argv, ok_codes=(0, 1))` | The tool exits 0; otherwise lists its findings, or the tail of its output. |
| `check_tool_clean(output, argv, json_key="findings")` | Zero findings, each remaining one listed as `file:line rule message`. |
| `require_seed_fails(output, seed, argv, rules=, exactly=True)` | Precondition: the seed (a `Path`, or text written under the scratch dir) still reports exactly `rules`. `argv` is the command prefix; the seed path is appended. **Raises `Unmeasurable`**: a fixture that drifted is the host's fault. |
| `scratch_dir(output)` | `<workspace parent>/.<workspace>.scratch`: where a check writes its own files, outside the workspace, so `check_no_files_added` is order-independent. |

### Many at once (`verify.combine`)

`check_all(output, *checkers)` runs every `Checker` (`Callable[[CaseOutput], None]`) and
raises one `AssertionError` listing each failure under the checker's name, so one failure
never masks another. Any other exception propagates at once, unchanged. The output is
passed first, so bind keywords with `functools.partial` and positionals with a lambda. A
partial is named by its function and bound arguments; a bare lambda has no readable name,
so its failure is reported by its own message alone, or under a label you give it as a
`(label, checker)` pair:

```python
check_all(
    output,
    check_rollout,
    lambda o: check_files_written(o, "NOTES.md"),
    ("NOTES.md kept its seed", lambda o: check_content_kept(o, "NOTES.md", seed_text=output.seed("NOTES.md"))),
    partial(check_cost_within, usd=0.50),
    partial(check_tool_clean, argv=[*LINT, "--json", output.path("NOTES.md")]),
)
```

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
`hex_colours`, `body_text`, `code_fences(doc, lang=None)` (every fenced block, where
`fences` is mermaid only), `entities` and `relationships` (`erDiagram` fences, as
`"LEFT ||--o{ RIGHT"`), `sections(doc, level=2)` (heading to body, headings inside code
ignored) and `section(doc, heading_prefix)` (case-insensitive prefix; fails as an
assertion naming the headings present). Any `str -> object` works.

`node_ids`, `edges` and `unstyled_nodes` read flowchart fences only, one fence at a time,
because a class applies only within the diagram that assigns it. Front matter, `%%`
comment lines, node labels of every shape and edge labels (`|x|`, `-- x -->`,
`-. x .->`, `== x ==>`) are dropped before anything is read as an id, and a `subgraph`
id is a container rather than a node.

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

## Analyzers: checks over every sample

A grader judges one rollout. An analyzer judges every sample the cache holds for its
suite, after the sweep: has the new tool version regressed a cell, which model tier
carries the skill, where is the cost-quality front. Declare one beside the cases:

```python
from pytest_xharness_eval import Analysis, analyzer

@analyzer                                    # or @analyzer(cases=["eval_lint_fix"])
def analyze_versions(a: Analysis) -> None:
    a.note("versions", list(a.versions()))
    a.note("front", a.pareto())              # published on the finding, pass or fail
    a.expect_no_regression("verdict")        # the current subject version against the one before
```

`expect_no_regression` never passes on no evidence. With fewer than two subject versions
recorded, or no matched cell at `min_n` samples on both sides, it fails, so the gate stays
red until the subject has changed and been swept again. To publish without gating on a
first sweep, record why with `a.note("skipped", "one subject version so far")` instead of
calling it.

The function is named `analyze_*`, takes one `Analysis`, returns nothing, and fails by
raising `AssertionError`. It sees only its own suite's records, matched by the suite
file's path relative to the project root. Its `Analysis` holds `a.history` (the cache),
`a.current` (this sweep's records, empty when rerun from the CLI) and `a.samples` (both,
each session once), plus `seed`, `min_n` (3) and `confidence` (0.95).

| Family | Call | Returns |
|---|---|---|
| any | `a.estimate(metric, on=None)` | One `Estimate` over `on` (default every sample) |
| environment | `a.summarise(metric, by=())` | `{group key: Estimate}` |
| environment | `a.effects(factor, metric, within=None, drop_unbalanced=False)` | Each level's main effect over balanced slices; an incomplete design raises `Unbalanced` |
| environment | `a.best(metric, by=ENVIRONMENT, direction=None)` | Groups best first; those under `min_n` trail unranked |
| environment | `a.pareto(quality="verdict", cost="cost", by=ENVIRONMENT)` | `ParetoPoint`s, each at its pessimistic bounds, front first |
| environment | `a.tiers(metric)` | `{family tier: Estimate}`, pooled across harnesses |
| narrow | `a.for_cases(cases)` | The same `Analysis` over only these case names' samples |
| narrow | `a.at_version(version=None, field="subject_version")` | The same `Analysis` over one subject version: `version`, or the current one (the version the newest sample measured) |
| environment | `a.reliability(k, by=ENVIRONMENT)` | Per group, `{"n", "passes", "pass_at_k", "pass_hat_k"}` over attempted samples; each estimate `None` while `n < k` |
| subject | `a.versions(field="subject_version")` | The versions ordered by when each was *last* measured: `[-1]` is the current one, `[-2]` the one it replaced (after a revert too). First-seen order is `a.samples.first_seen(field)` |
| subject | `a.compare(metric, baseline, candidate, by=CELL_FIELDS, direction=None, field="subject_version")` | One `Comparison` per matched cell; a side is a value of `field` or any `Samples`. `by=("family_tier",)` compares stratified by tier rather than cell by cell |
| subject | `a.trend(metric, by=(), field="subject_version")` | Per group, `(version, Estimate)` in first-measured order |
| subject | `a.regressions(metric="verdict", by=CELL_FIELDS)` | The cells where the latest version regressed against the one before; empty with fewer than two versions |
| scenario | `a.fragile(by=("case", "scenario"))` | Scenarios by failure rate over attempted samples, most fragile first |
| scenario | `a.broken(by=("case", "scenario"))` | Scenarios by error rate, most often ungraded first: a seed, tool or harness to fix, not a skill |
| scenario | `a.failures(by=())` | Per group, `{(verdict, failure): count}`, most common first |
| verdict | `a.expect_no_regression(...)`, `a.expect_at_least(metric, value, by=(), bound="low")`, `a.expect_at_most(metric, value, by=(), bound="high")`, `a.expect_pareto_contains(match)` | Raise `AnalysisFailure` (an `AssertionError`) with the comparisons and details attached |
| publish | `a.note(key, value)` | Stores `value` on the finding (an `Estimate` or `Comparison` as its dict) and returns it |

A metric is an Important Metric id (`cost`, `verdict`, ...), `passed`, a group statistic
(`cost_per_pass`, `wasted_cost`), `tool_time_share`, `context_cost_share`, or any numeric
`CellMetrics` field. `a.samples.where(**fields)` and `.group(*fields)` filter and split by
any record field; grouping by `scenario` splits by fingerprint too.

**Versions pool unless narrowed.** `summarise`, `best`, `pareto`, `tiers` and
`reliability` read every sample, whatever subject version it measured. To ask about the
subject as it now stands, narrow first: `a.at_version().pareto()`.

How the answers are reached, so you can read them:

- **A rate is Wilson; anything else is a seeded bootstrap** of its kind's centre.
- **A comparison is cell by matched cell.** A cell one side never ran is not compared.
- **Each cell is tested two-sided**, Fisher exact for a rate, a permutation test otherwise.
  The p-values are Benjamini-Hochberg adjusted together.
- **`improved` or `regressed` needs both** a q-value within `1 - confidence` and a
  difference interval that excludes zero. Below `min_n` on either side is `insufficient`.
  Everything else is `inconclusive`.
- **No pass on zero evidence.** A bound asked of no samples fails.
- **Errors are not attempts.** A sample graded `error` is left out of every pass rate.
- **Three samples per arm cannot reach significance.** The smallest two-sided p-value at
  n = 3 is 0.1. Run `--xharness-repeat 5` for a comparison that can decide.

A finding passes, fails, or is an `ERROR` finding when the analyzer raised anything but an
assertion. All of them land in `report/analysis.json`, named `<suite path>::<analyzer>`,
and a failed one fails the session. Rerun every analyzer for free over the cache, with
`--suite` to narrow and `--seed` to reseed; it exits 1 when one fails:

```bash
uv run -m pytest_xharness_eval.analysis .xharness_eval_cache [--suite skills/x/evals/eval_x.py] [--seed N]
```

### Scripted hill-climbing

An `Analysis` needs no sweep. Build one over the cache from a script, free, to decide
whether the last edit to the subject was worth keeping:

```python
from collections import Counter
from pathlib import Path

from pytest_xharness_eval import Analysis, Samples
from pytest_xharness_eval.model.layout import CacheLayout

samples = Samples.stored(CacheLayout(Path(".xharness_eval_cache")))
a = Analysis(history=samples.where(case="eval_gate"), min_n=5)
before, after = a.versions()[-2:]                  # last measured last: `after` is the subject now

for metric in ("verdict", "turns", "cost"):
    cells = a.compare(metric, baseline=before, candidate=after)
    print(metric, dict(Counter(c.change.value for c in cells)))
    for c in cells:
        if c.change.value in ("improved", "regressed"):
            print("   ", c.describe())
    for c in a.compare(metric, baseline=before, candidate=after, by=("family_tier",)):
        print("  stratified by tier:", c.describe())

for version in (before, after):
    at = a.at_version(version)
    print(version, "pass rate by tier", {tier: est.point for tier, est in at.tiers("verdict").items()})
    print(version, "cost per pass by model", {key: est.point for key, est in at.summarise("cost_per_pass", by=("model",)).items()})
    print(version, "pass^3 by model", at.reliability(3, by=("model",)))
```

`Samples.stored(CacheLayout(root))` reads every graded sample the cache holds, oldest
first; `Analysis(history=..., min_n=5)` matches a `--xharness-repeat 5` sweep. The
`Samples` surface a script filters with:

| Call | Returns |
|---|---|
| `Samples.stored(cache)` | Every graded sample under a `CacheLayout`; dry runs and unreadable verdicts dropped |
| `s.where(predicate=None, **fields)` | The records matching every condition: a value by equality, a list, tuple or set by membership, a callable by calling it |
| `s.group(*fields)` | `{key tuple: Samples}` in sorted key order |
| `s.levels(field)`, `s.first_seen(field)`, `s.last_seen(field)` | A field's distinct values: sorted, by first appearance, by latest appearance |
| `s.latest(field="subject_version")` | The records carrying the value the newest record carries |
| `s.values(metric)` | Each record's value of `metric`, records without one left out |
| `s.attempted()`, `s.passes()` | The pass-or-fail records, and how many passed |
| `s.cost_per_pass()`, `s.wasted_cost()` | The two group statistics |
| `s.pass_at_k(k)`, `s.pass_hat_k(k)` | The unbiased estimators; `None` below `k` attempts |
| `s + t` | Both collections, oldest first, each session once |

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
