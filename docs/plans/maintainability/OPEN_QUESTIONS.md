# Maintainability: open questions

**Status:** live list, ordered by what blocks what. **Before you start:** read [README.md](README.md) for the settled learnings.

Every question here is undecided, unmeasured or unvalidated.
When one is answered with evidence, its finding moves into [README.md](README.md) and the question is deleted from this file.
Metric names are defined in [GLOSSARY.md](GLOSSARY.md).

The questions fall into four groups, and each group depends on the one before it.

| Group | Blocks |
|---|---|
| [1. Is the call graph right?](#1-is-the-call-graph-right) | every graph metric |
| [2. Does any score predict review effort?](#2-does-any-score-predict-review-effort) | using a score as a target |
| [3. How is a score calibrated?](#3-how-is-a-score-calibrated) | using a score as a gate |
| [4. What gate, if any, do we adopt?](#4-what-gate-if-any-do-we-adopt) | changing `make check`, and deferred |

A separate group, [5. The method itself](#5-the-method-itself), lists the gaps in how the experiments were run.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Maintainability: open questions](#maintainability-open-questions)
  - [1. Is the call graph right?](#1-is-the-call-graph-right)
  - [2. Does any score predict review effort?](#2-does-any-score-predict-review-effort)
  - [3. How is a score calibrated?](#3-how-is-a-score-calibrated)
  - [4. What gate, if any, do we adopt?](#4-what-gate-if-any-do-we-adopt)
  - [5. The method itself](#5-the-method-itself)

<!--TOC-->
</details>

---

## 1. Is the call graph right?

The metric arithmetic is cross-validated and the extraction is not.
Until these close, every graph score is a lower bound of unknown looseness.

**G1 is deferred, 14 September 2026.** Building a ground-truth fixture is premature, and the exploration that proposed it got ahead of the work.
The measures are still being found, so there is nothing yet whose accuracy is worth the cost of hand-writing a corpus.
G2 to G6 stay open and are read against [EX-RES-01](GLOSSARY.md#ex-res-01-resolution-rate) and [EX-REC-02](GLOSSARY.md#ex-rec-02-extractor-agreement) in the meantime.

| ID | Question | What would settle it |
|---|---|---|
| G1 | Does either extractor produce the true call graph? | A **ground-truth fixture**: a small program per language with every call written down by hand, committed with its expected edge list and asserted against. **Deferred**, see above. |
| G2 | Which extractor do we trust, per language? | G1. Today the LSP looks better on Python and tree-sitter on TypeScript, but the two agree on only about half the union of their edges. |
| G3 | How are dispatch tables, decorator registries and `pluggy` hooks represented? | A declared-edge format, since no static extractor sees them. The 39 renderers in `report-ui/src/components/records/records.tsx` are the test case. |
| G4 | How is a cross-language contract declared as an edge? | A declared-edge format covering `emit/index.py` writing `report/index.json` and `report-ui/src/lib/types.ts` reading it. Zero edges cross the language boundary today. |
| G5 | Do the webapp layer scores survive a better graph? | Re-run them on the tree-sitter graph. They were computed on an LSP graph missing more than half its edges, so they are provisional. |
| G6 | Should edges be weighted by call sites or counted once per caller? | A case where the choice changes a ranking. Weighting moved `phi` by at most 0.059 here and changed no ordering. |

---

## 2. Does any score predict review effort?

Conductance and leverage are better *arguments* than cyclomatic complexity.
Nothing shows they are better *predictors*.
Of 121 metrics tested against understandability, none reached even a medium correlation.

| ID | Question | What would settle it |
|---|---|---|
| **V1** | Does conductance, leverage or bits per boundary track what a reviewer calls easier to review? | A validation against review effort: time to review, defects found, or reviewer ratings on real diffs. Untouched. |
| V2 | Is there a held-out quantity that plays the role of a test loss? | Every score here is a training-set quantity. Without one, a sweep cannot show generalisation. |
| V3 | Does a score against name count show double descent? | An extraction that splits real bodies, pushed across orders of magnitude of name count, scored against the V2 proxy. The measured range, 237 to 817 names, showed none and is too short to rule it out. |
| V4 | Does nesting depth resist extraction? | Run it over the rearrangement sweep. It needs no partition, and extraction relocates nesting rather than removing it. Untested. |
| V5 | Does screen load predict comprehension better than line count? | Score the Peitek et al. snippets, where lines of code reached tau -.46. Only snippets longer than one screen test the screen factor, so count those first. |

---

## 3. How is a score calibrated?

No threshold in this work has a derivation.
The SIG bands were calibrated on about 200 systems, and nothing equivalent exists for any graph metric.

| ID | Question | What would settle it |
|---|---|---|
| **C1** | What are the risk bands for conductance and leverage? | A benchmark of real repositories, with bands derived from percentiles in the manner of Alves, Ypma and Visser. The largest unfunded piece of work. |
| C2 | What is the volume floor below which `phi` is noise? | A derivation. The value of three internal edges was chosen by eye. |
| C3 | Which coding scheme should the two-part code use? | Adopt the Map Equation from Infomap and check whether it re-ranks the five partitions. The current scheme, `L(H) = n log2(k)` with a global index for crossing edges, is degenerate at one cluster. |
| C4 | How is the public API of a library excluded from leverage? | A source of truth for public names, such as `docs/rollout.md`. 24.7% of this repository's names have no caller in the graph, and most are the published grader surface. |
| C5 | Can the scoring depth be chosen automatically? | Test the rule "the deepest folder level that is not lopsided" on more codebases. At depth one the webapp's `components/` held 76% of all names. |
| C6 | Does the file boundary beat the folder boundary beyond two codebases? | Score the boundary levels on more codebases. File out-discriminated folder 24 points to 13, on two samples. |
| C7 | Does the margin over random transfer across archetypes? | Score a CLI, a REST API and a library alongside the two codebases here. The webapp scored a lower `Q` and a larger margin, which is first evidence only. |
| C8 | What screen height, and what penalty past it, should screen load use? | `H = 50` was chosen to match D5. Compare linear, quadratic and step penalties past `H`, and whether `BIC`'s `ln(N)` beats `AIC`'s flat 2, against the V5 proxy. |

---

## 4. What gate, if any, do we adopt?

**The whole group is deferred, 14 September 2026.** Any gate is premature.
The work is still finding measures worth trusting, and a gate assumes that question is settled.
The options below are recorded so the deferral is a choice rather than an omission.
Nothing here is adopted, and `make check` is unchanged.

| ID | Option | What it is | Strongest point against |
|---|---|---|---|
| D1 | Enforced gate portfolio | Opposing per-unit caps in `make check`: `C901` plus `PLR0913` arguments, `PLR0915` statements, `PLR1702` nesting | Every threshold is a convention, and per-unit maxima are what the industry moved away from |
| D2 | Distribution gate | SIG-style risk profiles over four damping axes | No Python implementation exists, and at 6,974 lines one function moves a band by about 1% |
| D3 | Change ratchet | `complexipy --diff`, or a `phi` delta, failing only on regression | Ratcheting has no peer-reviewed evaluation, and agents rewrite whole files, so "the diff" is often the module |
| D4 | Doctrine, no gate | Delete the gate that measures nothing, and route exceedances through an ADR with an owner and a review date | Nothing stops drift, and it relies on someone reading |

| ID | Question | Current evidence |
|---|---|---|
| **D5** | Do we cap function length, or gate on screen load instead? | A 50-line cap binds one of 312 Python functions, `pytest_addoption`, whose 25 repeated names give it half the screen load of `of`. The same cap binds 19 of 323 `report-ui` functions, which carry 61.6% of that tree's load. |
| D6 | Do we remove `C901` from `make check`? | It reported zero violations under all thirteen rearrangements, including the ones built to be bad. |
| D7 | Is a `phi` delta usable as a review prompt before G1 closes? | It needs no threshold, but it inherits every extraction error in group 1. |

---

## 5. The method itself

The rearrangement sweep covered filing thoroughly and structure partially.
These gaps limit what its results can claim.

| ID | Gap | What would close it |
|---|---|---|
| M1 | The sweep is a factorial grid, not a search | A surrogate model over a continuous parameterisation, with an acquisition function and a Pareto front over the metric pair |
| M2 | Extraction is simulated with stub wrappers | Splice real statement runs into the extracted helper |
| M3 | Inlining deletes a function rather than splicing its body | Move the body into each caller and re-measure |
| M4 | Transforms were tested one at a time | Compose duplication with re-filing and test whether the effects add |
| M5 | Three structural axes were never swept | Vary call-graph depth, fan-out distribution and edge direction, which is where a layering rule lives |
