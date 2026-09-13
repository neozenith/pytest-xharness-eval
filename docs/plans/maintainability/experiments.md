# Rearranging the same code 40 ways, and scoring each

**Status:** exploration, no decision made. **Before you start:** read [README.md](README.md) for conductance and the two-part code. **Everything here was measured** against `src/pytest_xharness_eval/` on 2026-09-12, with `tools/experiment.py` and `tools/sweep.py`.

The question was which structural choices actually move a maintainability score, and by how much.
So the same program was rearranged forty ways, scored, and the rankings compared.

Every rearrangement preserves behaviour.
Nothing here changes what the code does, only where it lives or how many copies of it exist.

The setup is unusually clean.
`tools/treesitter.py` resolves calls by name and ignores imports.
Moving a file between folders therefore leaves the call graph's **edges** untouched and changes only the **partition**.
Filing effects are therefore isolated from everything else.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Rearranging the same code 40 ways, and scoring each](#rearranging-the-same-code-40-ways-and-scoring-each)
  - [Three objectives failed before one worked](#three-objectives-failed-before-one-worked)
  - [What actually drives the score](#what-actually-drives-the-score)
  - [The architecture beats chance](#the-architecture-beats-chance)
  - [The failure: duplication improves the score](#the-failure-duplication-improves-the-score)
  - [The damper that catches it](#the-damper-that-catches-it)
  - [Diminishing returns](#diminishing-returns)
  - [What this settles](#what-this-settles)

<!--TOC-->
</details>

---

## Three objectives failed before one worked

Each of the first three had a **degenerate optimum**: a rearrangement nobody would defend that scored best.

| Objective | Maximised by | Why |
|---|---|---|
| share of calls staying inside | **one folder** | nothing can cross a boundary that does not exist |
| bits of residual saved per boundary | **two folders** | the divisor is `k - 1` |
| total description length | **one folder** | `L(H) = n log2(k)` scales with names, the saving with edges, and this graph has fewer edges than names |

That third one is worth keeping.
A codebase with fewer call edges than callables cannot pay for any partition under a two-part code.
That is a property of the graph rather than of the architecture.

**Newman modularity** is the standard answer and it is degenerate-free by construction.
It subtracts the inside-share a random graph with the same degrees would have.
One cluster therefore scores exactly 0, and very small clusters score below 0.
The optimum is interior, which is the property an objective needs before it can be searched at all.

Everything below uses modularity over the folder partition, written `Q`.

**Takeaway:** three of four plausible objectives reward destroying the architecture, so an objective has to be checked against a degenerate case before it is trusted.

---

## What actually drives the score

Forty variants, ranked by how far they moved `Q` from the real tree's **0.589**.

| Rearrangement | `Q` | Change | Verdict |
|---|---|---|---|
| Folders replaced by the call graph's own communities | 0.667 | **+0.077** | the ceiling |
| **Copy every shared function into each caller** | 0.624 | **+0.035** | **the metric is wrong, see below** |
| **The tree as it is** | **0.589** | baseline | |
| Random folders, same count, 8 seeds | 0.506 avg | **-0.083** | filing without meaning |
| Folders by first letter of filename | 0.500 | -0.089 | filing without meaning |
| Two random folders | 0.281 | -0.308 | too coarse |
| Every module-level function folded into a class | 0.304 | -0.285 | structure destroyed |
| Every module in one folder | 0.000 | **-0.589** | no partition at all |
| Every module in one file | 0.000 | -0.589 | no partition at all |

Two sanity checks passed, and they matter more than the ranking.

- **File-level `Q` held at 0.5767 across every folder-only transform.** Moving files between folders must not change the file partition, and it did not.
- **The three collapse-to-one-cluster variants scored exactly 0.** Modularity is doing what it claims.

**Takeaway:** the spread between a meaningful partition and a random one of the same size is about 0.08.
The spread between having a partition and not having one is 0.59.

---

## The architecture beats chance

The interesting comparison is not against a flattened tree, it is against a **random tree with the same number of folders**.

Eight random 8-way partitions scored:

```
0.488  0.490  0.497  0.497  0.508  0.509  0.522  0.539     mean 0.506
```

The real tree scores **0.589**, above the maximum of all eight draws.

That is the first quantitative evidence in this work that the declared architecture carries information rather than convention.
It is eight samples, so it is suggestive rather than significant.

**Takeaway:** compare an architecture to a random partition of the same granularity, never to no partition, because the second comparison flatters everything.

---

## The failure: duplication improves the score

The `duplicate` transform copies every function with two or more cross-file callers into each file that calls it.
That is objectively worse code, the same logic in several places drifting apart, and it is what a reviewer rejects on sight.

It **raises** the score.

| | `Q` | file `Q` | nodes | lines |
|---|---|---|---|---|
| baseline | 0.5893 | 0.5767 | 312 | 6,974 |
| duplicate, 2+ callers | **0.6243** | **0.6683** | 334 | 7,212 |
| duplicate, 3+ callers | 0.6168 | 0.6027 | 318 | 7,028 |

Three percent more code buys six percent more modularity.

The mechanism is general and it is worth stating as a rule.

> Duplication is the cheapest way to delete a boundary-crossing edge.
> Any metric that counts crossings as bad will pay for it.

This applies to conductance exactly as it applies to modularity, and it disqualifies both as a **target** while leaving them useful as an **instrument**.

**Takeaway:** before adopting any structural metric, run the duplication transform against it, because a metric that rewards copy-paste cannot be optimised against.

---

## The damper that catches it

The README's two-springs test asks for a second metric that moves the opposite way under the cheapest cheat.
Counting **names with three or more callers** is that metric.

| | `Q` | names with 3+ callers |
|---|---|---|
| baseline | 0.5893 | **16** |
| duplicate, 2+ callers | 0.6243 | **13** |
| duplicate, 3+ callers | 0.6168 | 14 |
| folders replaced by communities | 0.6667 | **16** |

Re-filing moves `Q` and leaves leveraged names untouched, because it moves no code.
Duplication moves them in opposite directions, because it converts one name with three callers into three names with one caller each.

That gives a rule with no threshold in it:

> A change that raises `Q` while lowering the count of leveraged names is duplication.
> Reject it regardless of the score.

Normalising by size is the obvious alternative and it is not enough.
Discounting `Q` by node count catches the 2+ case and still rewards the 3+ case.
Removing three crossing edges for two extra definitions is a good trade under that pairing.
Counting leverage directly catches both.

**Takeaway:** the damper for a boundary metric is not size, it is leverage, because leverage is what duplication actually destroys.

---

## Diminishing returns

Random partitions swept from 2 to 37 folders, so the effect of granularity alone can be separated from the effect of meaning.

```
k       2     3     5     6     8    10    14    18    25    37
Q    0.281 0.454 0.372 0.506 0.528 0.480 0.539 0.538 0.546 0.548
```

The curve climbs steeply to about eight folders and is **flat from roughly fourteen onward**, converging near 0.548. `k = 5` and `k = 10` sit below trend because each point is a single hash draw rather than an average.

Two things follow.

- **Granularity saturates.** Past about fourteen folders, splitting further buys nothing.
- **Meaning beats granularity.** The real tree scores 0.589 with eight folders, above every random partition at any count including thirty-seven.

Duplication saturates too, and sooner.
Copying functions with five or more cross-file callers changes nothing, because no function here has five.

**Takeaway:** both axes reach diminishing returns quickly, so the reachable range on filing alone is roughly 0.28 to 0.67 and the architecture sits at 0.59.

---

## What this settles

**Folders matter less than the earlier documents assumed, and the thought experiment was right.** Flattening the tree costs the whole score, but that is the degenerate case rather than a judgement about code.
Between a meaningful partition and a random one of the same size there is only 0.08, which is a real signal and a small one.

**The ceiling is the call graph's own communities**, at 0.667 against the tree's 0.589.
The gap is what re-shelving could buy, and it is smaller than the gap to a random partition is large.

**No single number survives as a target.** Modularity is the only one of four that is not degenerate, and it still pays for duplication.
Paired with leveraged-name count it becomes usable, which is the two-springs result arrived at from the other direction.

**What is still missing** is unchanged from [README.md](README.md).
These transforms are mechanical, so they establish which *filing* choices move a score.
They say nothing about whether the score tracks what a reviewer would call better code, and that still needs a ground-truth fixture.
