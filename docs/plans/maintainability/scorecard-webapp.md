# The same scorecard, run against the webapp

**Status:** exploration, no decision made.
**Before you start:** read [scorecard.md](scorecard.md), which defines conductance, leverage and the two-part code.
**Every number here was measured** against `report-ui/src/` on 2026-09-10, with the scripts in [How these numbers were produced](scorecard.md#how-these-numbers-were-produced).

[scorecard.md](scorecard.md) measured a Python library.
This document runs the identical method against `report-ui/src/`, the React and TypeScript webapp in the same repository.

Two questions were open.
Does the method transfer to a language whose LSP is a different implementation entirely?
And does a UI codebase, organised by convention rather than by a lint-enforced layering rule, score differently?

The answers are yes, and yes.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [The same scorecard, run against the webapp](#the-same-scorecard-run-against-the-webapp)
  - [The render graph is the call graph](#the-render-graph-is-the-call-graph)
  - [Three traps that nearly produced a fake result](#three-traps-that-nearly-produced-a-fake-result)
  - [The webapp, measured](#the-webapp-measured)
  - [Depth one is the wrong unit here](#depth-one-is-the-wrong-unit-here)
  - [What Leiden found](#what-leiden-found)
  - [The two codebases, side by side](#the-two-codebases-side-by-side)
  - [The one thing worth acting on](#the-one-thing-worth-acting-on)
  - [What this run changed about the method](#what-this-run-changed-about-the-method)

<!--TOC-->
</details>

---

## The render graph is the call graph

This was the risk that could have ended the exercise.

A React component is used as `<ChartPanel id=... />`, not as `ChartPanel(...)`.
Suppose `callHierarchy` treats JSX element usage as markup rather than as a call.
Then the extracted graph misses the render tree, which is most of what a UI codebase *is*.

It does not.
`typescript-language-server` reports JSX usage as an incoming call.

Checked directly against `ChartPanel`, which the graph says has five callers:

```
report-ui/src/components/charts/ContextWindowChart.tsx
report-ui/src/components/charts/TokenAccumulationChart.tsx
report-ui/src/components/charts/TokenWaterfallAggregateChart.tsx
report-ui/src/components/charts/TokenWaterfallChart.tsx
report-ui/src/components/charts/perTurnBars.tsx
```

Those are exactly the five files containing the string `<ChartPanel`.

**Takeaway:** for a React codebase the call graph and the render graph are the same object, so conductance measures component composition without any framework-specific work.

---

## Three traps that nearly produced a fake result

The first TypeScript run reported **747 names and an 82.7% orphan rate**.
Taken at face value it said the webapp was five-sixths dead code.
All three causes were measurement artefacts, and each is worth naming because none of them exists in the Python run.

**Inline lambdas are reported as named symbols.** There were 187 of them.
`typescript-language-server` returns a symbol called `map() callback` for every inline arrow function.
Nobody learns those names and nothing calls them by name.
Counting them in a metric defined over *names someone invented* is a category error, so they are now excluded by construction.

**Local variables are not components.** Kind 13 is too blunt a net.
Passing `--include-variables` to catch `const Foo = () => ...` also caught `children`, `p`, `s` and `node`.
The final run does not use it, at the cost of missing arrow-function components that are never called by name.

**Excluding tests manufactures orphans.** The Python run scored `src/` with no tests, so this run excludes `__tests__` to match.
That is the right comparison and it has a price.
An exported helper exercised only by a test now looks unreachable.

After all three corrections: **291 names, 247 call edges, 57% orphans.**

That orphan rate is still high, and one cause is architectural rather than a defect.
`components/records/records.tsx` holds a dispatch table, `R: Record<string, (r: Rec) => ReactNode>`, with **39 renderers keyed by record kind**.
They are reached as `R[kind]`, so no static call edge to any of them exists.

> A dispatch table is invisible to a static call graph.
> The pattern is good design and the graph cannot see it, so a tool that reports those names as dead is wrong, not the code.

**Takeaway:** every language brings its own artefacts, and the orphan rate is the number that exposes them.
A scorecard should surface it before any score.

---

## The webapp, measured

291 names and 247 call edges, extracted through `prepareCallHierarchy` and `callHierarchy/incomingCalls`.

| Layer | Names | Internal | Boundary | `phi` | Singleton rate | Mean leverage |
|---|---|---|---|---|---|---|
| `shims` | 3 | 0 | 0 | n/a | 0.00 | 0.00 |
| `lib` | 51 | 31 | 32 | **0.340** | 0.39 | 1.24 |
| `components` | 222 | 148 | 54 | 0.375 | 0.25 | 0.79 |
| `hooks` | 5 | 2 | 4 | 0.500 | 0.80 | 1.20 |
| `<root>` | 7 | 0 | 7 | 1.000 | 0.00 | 0.00 |
| `views` | 3 | 0 | 35 | 1.000 | 0.67 | 0.67 |

One number makes the rest of this table nearly meaningless.

**`components` holds 222 of 291 names, which is 76% of the webapp.** That is barely a partition.
Its conductance of 0.375 is a statement about the codebase as a whole, not about a module.

**Takeaway:** before reading a conductance table, check the sizes, because a lopsided partition produces numbers that look fine and mean nothing.

---

## Depth one is the wrong unit here

`components/` has subfolders, and they are the real declared structure.
Scoring at depth two instead:

```cytoscape
{ "data": "data/ts-layers.json" }
```

| Folder | Names | `phi` | Reading |
|---|---|---|---|
| `components/records` | 96 | **0.138** | a genuine deep module, the record renderers |
| `components/charts` | 20 | **0.184** | the chart subsystem, self-contained |
| `lib` | 51 | 0.340 | shared helpers |
| `components/panels` | 40 | 0.458 | mixed |
| **`components/` unfiled** | **55** | **0.684** | files sitting loose in `components/` |
| `components/ui` | 11 | 0.742 | leaf primitives, shallow by design |
| `views` | 3 | 1.000 | the top of the render tree |

Two entries need reading rather than grading.

`components/ui` at 0.742 is a set of leaf primitives that everything uses.
It is supposed to be reached from everywhere, exactly as `model/` is in the Python source, so its score describes its job.

`views` at 1.000 has three names and no internal calls, which is the volume floor from [scorecard.md](scorecard.md) again.
Views sit at the top of the render tree and never call each other.

**Takeaway:** the right scoring unit is the deepest folder level that is not lopsided.
That level is a property of the codebase rather than a constant.

---

## What Leiden found

40 communities at modularity 0.5026, against 85 for the Python source.

The largest cross-boundary cluster is **c18: 19 names at `phi` 0.122**, the tightest cluster in the webapp.
Sixteen of them are in `components/`, three in `lib/`.

```cytoscape
{ "data": "data/ts-charts.json" }
```

It is the chart subsystem: `ChartPanel`, `Plot`, `PlotWithLegend`, `ContextWindowChart`, `PerTurnBars` and the series helpers they share.
The folder structure splits it across `components/charts/` and `lib/`.

That split may well be correct, because `lib/` is where data shaping belongs.
But the call graph says these nineteen names are one thing, and that is worth knowing before the next change to either half.

**Takeaway:** a cross-boundary community is not automatically a defect, it is a question with a specific answer required.

---

## The two codebases, side by side

Both partitions scored with the two-part code, in bits.

```plotly
{ "data": "data/ts-bits.json" }
```

| Partition | Python `src/` | TypeScript `report-ui/src/` |
|---|---|---|
| Declared folders, depth 1 | **90.7** | 38.8 |
| Declared folders, depth 2 | 90.7 | **46.5** |
| One cluster per file | 24.0 | 5.3 |
| Leiden communities | 15.9 | 15.9 |

Three results, in order of how much they matter.

**The hand-drawn structure wins in both codebases.** Both architectures are doing real work.
In both languages the declared folders save more residual per boundary than either the file layout or the partition Leiden discovers.

**The Python architecture is about twice the stronger model.** 90.7 bits per boundary against 46.5.
That is not a moral judgement about either.
The Python side has an enforced layering rule, and a `TID251` lint that fails the build on a violation.
Its one exception carries a written ADR.
The webapp is organised the way React apps are organised, by component role.
The gap is what an enforced rule buys, measured.

**The webapp's nested folders beat its top level.** 46.5 against 38.8.
That is the numeric form of "`components/` is not a layer".

**Takeaway:** bits saved per boundary is comparable across languages.
That makes it the first number here that could sit on a dashboard next to coverage.

---

## The one thing worth acting on

Everything above is measurement. This is the finding.

**55 names sit directly in `components/` with no subfolder, and they score `phi` 0.684.**

They are the shallowest substantial cluster in the webapp, and the only one whose score is not explained by its job.
`components/ui` is shallow because primitives are shallow.
`views` is shallow because it is the top of the tree.
The unfiled 55 are shallow because they are unfiled.

Every other bucket under `components/` scores between 0.138 and 0.458.

The scorecard's prescription for the shallow corner is not "split them smaller".
It is to find the subfolders the call graph already implies, and move them there.
That is the one move that lowers conductance without adding a name.

```plotly
{ "data": "data/ts-quadrant.json" }
```

**Takeaway:** the actionable output of this method is a shelving instruction, not a refactor.
That is a cheaper class of change than any per-unit gate proposes.

---

## What this run changed about the method

Four things that [scorecard.md](scorecard.md) did not know.

- **The extractor is language-agnostic and the scoring is unchanged.** One `--lang` flag and a different LSP binary produced a comparable graph. That is the argument for building on LSP rather than a Python AST.
- **The orphan rate is a validity check, not a metric.** At 82.7% it was telling us the extraction was wrong. It should be the first thing a report prints and a hard gate on publishing any score.
- **The scoring depth has to be chosen per codebase.** A fixed "score the top-level folders" rule gives the webapp a meaningless answer. Picking the deepest non-lopsided level is a rule the tool can apply itself.
- **Dispatch tables and inline lambdas need explicit handling.** Both are common, both are invisible or noisy to a static call graph, and neither appears in the Python source at all.

**What is still open** is unchanged from [scorecard.md](scorecard.md).
There are no calibrated thresholds, no derivation for the volume floor, and no validation against review effort.
This run adds evidence that the measurement is portable, which is not evidence that it predicts anything.
