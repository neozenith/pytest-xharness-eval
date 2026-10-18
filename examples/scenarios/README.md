# Scenario suites: two bloated suites rewritten as generators

Two reference suites, each the rewrite of a real consuming repository's evals as
[scenario cases](../../docs/adrs/0074-a-case-may-be-a-scenario-and-its-fixtures-may-be-generated.md)
over generated fixtures, graded with the built-in checkers, and questioned by
[analyzers](../../docs/adrs/0075-an-analyzer-is-a-checker-over-every-sample.md).
Neither invokes a skill: every harness is sent the same sentence, and what is measured is
how well an agent clears a CLI tool's findings from its messages alone.

| Suite | Before | After |
|-------|--------|-------|
| `prose-gates/` | one near-identical `eval_*.py` per rule, a long `_gate.py` of hand-rolled checks, a `conftest.py` that edited `sys.path`, and a stub `SKILL.md` faking a skill | one `Table` case over the committed rule fixtures, an `Adversarial` case screened by the gate's own rule ids, a `Promoted` regression case, and two analyzers |
| `mermaidjs-lint/` | one `eval_*.py` per rule (most differing only in data), a `_lint.py` of hand-rolled checks, a `conftest.py`, and a hand-edited copy of each rule fixture | one `Table` case that generates its scenarios from the linter's own `tests/fixtures/rules/` and strips their `<!-- expect: -->` markers |

What replaced the hand-rolled helpers: `require_seed_fails` (as a `precheck`, so a drifted
fixture errors the cell *before* it spends), `check_tool_clean`, `check_content_kept`,
`check_length_kept`, `check_nothing_hidden`, `check_fences_kept` and `check_all`. The
plugin now puts a suite's directory on `sys.path`, so the `conftest.py` files went too.

## Running them

Each directory is a pytest project of its own. Point it at the tool's checkout; an unset
variable stops collection by name.

```bash
export PROSE_GATES_REPO=~/src/jpai-prose-gates MERMAIDJS_LINT_REPO=~/src/jpai-mermaidjs-lint
uv run pytest --rootdir examples/scenarios/prose-gates -c examples/scenarios/prose-gates/pyproject.toml \
  examples/scenarios/prose-gates/evals --dry-run          # free: every seed is prechecked
uv run pytest ... --xharness-repeat 5 -n 8                 # paid: five samples per cell
uv run -m pytest_xharness_eval.analysis examples/scenarios/prose-gates/.xharness_eval_cache
```

`prose-gates/tool/gate` is the subject under test in the hill-climbing run below: a thin
wrapper the agent is told to run, tracked with `tracks=`, so each edit of it is a new
subject version. The grader always judges with the unwrapped gate.

## What the live runs showed (2026-10-18, about $1.25 in all)

- **Tool as the variable.** v1 of the wrapper (the gate as shipped) passed 46 of 50 cells
  at five samples each; v2 (autofix first, then report) passed 49 of 50. Over ten matched
  cells, stratified by family tier, the pass rate moved 0.92 to 0.98 with P(better) 0.85
  and q 0.30: promising and, at this n, honestly inconclusive. pass^3 reliability rose from
  0.67 to 0.88 on `gpt-6-luna` and from 0.88 to 1.00 on `claude-haiku-5-5`.
- **The adversarial loop.** The adversary bred `paragraph-over-budget` with
  `no_final_newline` and `trailing_whitespace`, which `gpt-6-luna` failed three times in
  five. One command (`python -m pytest_xharness_eval.promote <session> <evals dir>`) froze
  it into `fixtures/paragraph-no-final-newline/` with its provenance beside it, and the
  `Promoted` regression case reproduced the failure live, two runs in three.
- **mermaidjs-lint.** 22 of 24 cells passed at two samples each; the two `gpt-6-luna`
  failures read straight off the records: an ERD finding left unresolved, and a run that
  never wrote the file.
- **What the runs caught in the plugin.** A race between xdist workers writing the
  scenario store, a fixture precondition that was billed after the run (now `precheck=`),
  and `error` cells polluting pass rates (now the separate `errors` metric).
