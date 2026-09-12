# The parameter space, and what is still unexplored

**Status:** exploration, no decision made. **Before you start:** [experiments.md](experiments.md) for the first sweep, [README.md](README.md) for the metrics. **Measured** against `src/pytest_xharness_eval/` and `report-ui/src/` on 2026-09-12.

The first sweep was a manual grid dressed up as a search.
This one widens it and adds the two transforms that were missing.
It also runs the TypeScript codebase for the first time, and records four intuitions that are not yet tested.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [The parameter space, and what is still unexplored](#the-parameter-space-and-what-is-still-unexplored)
  - [What was explored, and what was not](#what-was-explored-and-what-was-not)
  - [The capacity curve](#the-capacity-curve)
  - [Extraction is invisible to modularity](#extraction-is-invisible-to-modularity)
  - [The drivers, on one plane](#the-drivers-on-one-plane)
  - [Two archetypes, two different numbers](#two-archetypes-two-different-numbers)
  - [Granularity saturates in both languages](#granularity-saturates-in-both-languages)
  - [A codebase as a network, and its hyperparameters](#a-codebase-as-a-network-and-its-hyperparameters)
  - [Double descent: not observed, and not yet ruled out](#double-descent-not-observed-and-not-yet-ruled-out)
  - [The classic metrics, run over the same rearrangements](#the-classic-metrics-run-over-the-same-rearrangements)
  - [The concerns to run to ground](#the-concerns-to-run-to-ground)

<!--TOC-->
</details>

---

## What was explored, and what was not

Being honest about coverage, because the first sweep was presented as broader than it was.

| Axis | Covered | Gap |
|---|---|---|
| Folder assignment | 25 variants, 2 languages | none material |
| Folder count | 2 to 40 | none material |
| Duplication | 3 depths | interaction with re-filing untested |
| Inlining | 3 depths | body is deleted, not spliced |
| Extraction | 4 depths | the extracted helper is a stub, not real code |
| Class folding | 1 variant | no class splitting, no method promotion |
| Languages | Python, TypeScript | no Rust, Go, or a REST boundary |
| Search strategy | grid, with a null distribution | **no surrogate model, no acquisition function** |
| Objectives | one at a time | **no Pareto front over the pair** |

The search is still a grid.
A Bayesian search needs a surrogate over a continuous space.
Most of these transforms are categorical with one integer parameter, so the honest description is a **factorial sweep with a random control**.
That is a gap, not a substitution.

---

## The capacity curve

If a codebase is a model, the number of **names** is its capacity.
Inlining removes names, extraction adds them, and behaviour is fixed throughout.

```plotly
{ "data": "data/cap-curve.json" }
```

Reading it left to right, from 237 names to 817:

| Variant | names | edges | `Q` | bits |
|---|---|---|---|---|
| inline, 3+ callers deleted | 237 | 90 | 0.513 | 1,254 |
| inline, 2+ deleted | 240 | 96 | 0.482 | 1,315 |
| inline, single-caller deleted | 257 | 131 | 0.547 | 1,573 |
| **baseline** | **312** | **225** | **0.589** | **2,332** |
| extract every 12 statements | 448 | 225 | 0.589 | 2,857 |
| extract every 6 | 466 | 225 | 0.589 | 2,922 |
| extract every 3 | 529 | 225 | 0.589 | 3,152 |
| extract every statement | 817 | 225 | 0.589 | 4,147 |

Modularity climbs to the real codebase and then goes **flat**.
Description length climbs the whole way, and by the far right it has nearly doubled.

**Takeaway:** the real codebase sits at the point where modularity stops improving.
That is the first time any measurement here has landed on the existing architecture rather than beside it.

---

## Extraction is invisible to modularity

The flat right-hand side is not a plateau in the interesting sense. `Q` is **identical to four decimal places** across all four extraction depths.

The cause is structural rather than a bug in the transform.
Extraction adds a name and a call inside the same folder, so it adds an internal edge and moves nothing across a boundary.
A partition metric cannot see it.

Description length sees it immediately, because every new name has to be stated.

> Modularity scores where the boundaries are.
> Description length scores how many names there are.
> Tidying changes only the second, which is why one number was never going to work.

This is the README's "one number cannot do both jobs" arriving from the measurement side rather than from Yang's proof.

**Caveat that limits the claim.** The extracted helper here is a stub that returns `None`, not a real slice of the original body.
It reproduces the *shape* of tidying, adding a single-caller name, and not its full effect on the call graph.

**Takeaway:** modularity and description length are not two views of one quantity, they are sensitive to different moves, and a scorecard needs both.

---

## The drivers, on one plane

Every Python variant, plotted as the spring against the damper.

```plotly
{ "data": "data/cap-drivers.json" }
```

The vertical line is the real codebase's 16 leveraged names.
Anything to the **left** of it has destroyed shared names, whatever its `Q`.

`duplicate` sits up and to the left, which is the signature of a change that games the metric. `leiden` sits straight up, higher `Q` at identical leverage, which is the signature of an honest improvement.

**Takeaway:** direction on this plane separates a real improvement from a gamed one, and neither axis alone does.

---

## Two archetypes, two different numbers

The first run of `report-ui/src/`, alongside the Python library.

```plotly
{ "data": "data/cap-archetype.json" }
```

| | Python library | TypeScript webapp |
|---|---|---|
| names | 312 | 323 |
| call edges | 225 | **542** |
| edges per name | 0.72 | **1.68** |
| names with 3+ callers | 16 (5%) | **60 (19%)** |
| single-caller names | 35.6% | **50.2%** |
| **modularity `Q`** | **0.589** | **0.425** |
| random control, same `k` | 0.506 | 0.322 |
| margin over random | **+0.083** | **+0.103** |

The webapp scores lower on `Q` and **further above its own random control**.

Its call graph is 2.3 times denser per name, because a component renders components and a library function does not.
A denser graph is harder to partition cleanly, so a lower `Q` is what a good webapp should look like.

> A score of 0.425 for a webapp may be as good as 0.589 for a library.
> Comparing the two numbers directly is a category error.

**Takeaway:** the margin over a random control of the same granularity transfers across archetypes, and the raw score does not.

---

## Granularity saturates in both languages

```plotly
{ "data": "data/cap-granularity.json" }
```

Random partitions in both codebases climb steeply, then flatten: Python near 0.548 from about fourteen folders, TypeScript near 0.36 from about twenty.

Both real architectures, the stars, sit **above every random partition at any count**.

**Takeaway:** meaning beats granularity in both languages, and the saturation point scales with the codebase rather than being a constant.

---

## A codebase as a network, and its hyperparameters

The analogy is worth writing down because it generates testable predictions.

| Neural network | Codebase |
|---|---|
| unit | a named callable |
| weight, or edge | a call site |
| activation | the call actually being reached at runtime |
| layer | a folder, module or package |
| capacity | how many names exist |
| regularisation | the cost of each new name, `BIC`'s `ln(n)` |
| architecture search | choosing the partition |
| overfitting | three hundred single-caller wrappers |
| underfitting | one function that does everything |

Under that framing the hyperparameters we have touched are name count, partition granularity, partition assignment, and duplication depth.
The ones we have not are call-graph depth, fan-out distribution, and the direction of edges, which is where a layering rule actually lives.

**Where the analogy breaks, and it matters.** A network is trained against a loss on held-out data.
A codebase has no held-out set and no loss, only a proxy.
Every score here is a *structural* prior with no outcome attached, which is exactly the gap the ground-truth fixture is meant to close.

**Takeaway:** the analogy is productive for generating axes to sweep, and it does not supply the thing that would make the sweep conclusive.

---

## Double descent: not observed, and not yet ruled out

The hypothesis is that a score against name count falls, rises, then falls again as capacity grows past the point where every name is trivial.

On the measured axis, it does not appear.
Modularity rises to the real codebase and stays flat to 817 names.
Description length rises monotonically with no second descent anywhere.

Three reasons that is **not** a refutation.

- **The capacity axis is short.** 237 to 817 names is a factor of three.
  Double descent in networks appears across orders of magnitude.
- **The extraction transform is a stub.** It adds names without redistributing real logic, so it does not simulate the regime where every function becomes uniformly trivial.
- **Neither metric is a test loss.** Double descent is a statement about generalisation error. `Q` and description length are training-set quantities, and there is nothing here that plays the role of held-out data.

A real test needs an extraction that genuinely splits bodies, pushed to tens of thousands of names, scored against something that behaves like a loss.

**Takeaway:** double descent is unfalsified rather than absent, and the experiment that would settle it has not been built.

---

## The concerns to run to ground

Carried forward explicitly so none of them is lost.

| Concern | Status | What would settle it |
|---|---|---|
| The sweep is not a real search | open | a surrogate model over a continuous parameterisation, with an acquisition function |
| Extraction is simulated with stubs | open | splice real statement runs into the extracted helper |
| Inlining deletes rather than splices | open | move the body into the caller and re-measure |
| Archetypes score differently | **first evidence** | run a CLI, a REST API and a library, and compare the margin over random rather than the raw score |
| Double descent | open | a capacity axis spanning orders of magnitude, and a held-out proxy |
| Does the score track human judgement | **untouched** | the ground-truth fixture, still the blocking piece |
| Cross-language edges | open | declared contracts, since no grammar contains them |
| Interaction effects | open | compose duplication with re-filing and test for additivity |

**The honest summary.** The sweep now covers filing thoroughly, structure partially, and two of the four archetypes named as likely to differ.
It has produced one genuine metric failure, one working damper, and a first archetype comparison.
It has produced no evidence at all that any of these numbers track what a reviewer would call better code.

---

## The classic metrics, run over the same rearrangements

`ruff` C901, `radon`, `lizard` and `complexipy` were run across every variant.
The point was not to rank the tools but to test one prediction from [You can always refactor more, and that is a theorem](README.md#you-can-always-refactor-more-and-that-is-a-theorem).

Extraction is subdivision, and subdivision lowers every per-unit count for free.
So adding do-nothing wrappers must lower cyclomatic complexity while changing nothing a program does.

It does.

```plotly
{ "data": "data/cap-response.json" }
```

Percent change from the real codebase, on three metric families at once.

| Transform | modularity `Q` | mean cyclomatic | tokens |
|---|---|---|---|
| **Every module in one folder** | **-100%** | **0%** | **0%** |
| Every module in one file | -100% | 0% | 0% |
| Every function folded into a class | -48% | 0% | 0% |
| **Extract a wrapper per statement** | **0%** | **-44%** | +24% |
| Extract every 3 statements | 0% | -29% | +11% |
| **Duplicate shared functions** | **+6%** | -0.3% | +6% |
| Delete single-caller functions | -7% | -14% | -28% |

Read the diagonal of blind spots.

- **Cyclomatic complexity cannot see filing at all.** Flattening the tree into one folder, collapsing it into one file, or folding every function into a class leaves `radon`, `lizard` and `complexipy` byte-identical.
  The same holds in TypeScript, where `lizard` gives the flattened webapp exactly the baseline's 688 functions and 2.45 mean.
- **Modularity cannot see extraction.** Adding 505 stub wrappers moves `Q` by nothing.
- **Neither can see duplication.** `Q` moves the wrong way and cyclomatic complexity moves 0.3%.

Only the token count responds to both extraction and duplication, and it cannot tell them apart, because it only knows the code got bigger.

### Adding 505 do-nothing functions cuts complexity by 44%

The strongest single number in this work.

| | functions | `C901` over 10 | radon mean | radon **max** | cognitive mean | cognitive **max** |
|---|---|---|---|---|---|---|
| the real codebase | 310 | **0** | 3.47 | **26** | 2.45 | **31** |
| extract every 12 statements | 446 | 0 | 2.72 | 26 | 1.71 | 31 |
| extract every 3 statements | 527 | 0 | 2.45 | 26 | 1.44 | 31 |
| **extract every statement** | **815** | **0** | **1.94** | **26** | **0.93** | **31** |

Mean cyclomatic complexity falls 44% and mean cognitive complexity falls 62%, for a change that adds five hundred names and no behaviour.

**The maximum does not move.** It is 26 for radon and 31 for cognitive across every single variant, because subdivision adds trivial functions and never touches the worst one.

That is the argument for the SIG model's risk bands over any average.
A mean is gamed by adding units; a distribution over thresholds is not.

### The existing gate never fires, under any rearrangement

`C901` at `max-complexity = 10` reports **zero violations in all thirteen Python variants**, including the ones built to be as bad as possible.

It reports zero while `radon` reports a maximum of 26 and `complexipy` reports 31 on the very same function.

**Takeaway:** the three metric families are blind in different directions, so a scorecard needs at least one of each.
The one currently in `make check` is inert under every transformation tested.
