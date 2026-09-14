# Maintainability glossary

**Status:** reference for this directory only. **Before you start:** arithmetic, and `log2(8) = 3`.

Every metric the other documents in this directory measure, defined once.
Each entry gives the formula, what it means when the number moves, and how it is gamed.
Worked examples sit in a collapsed section under each entry.

The repository-wide vocabulary (*case*, *cell*, *harness*) is in [GLOSSARY.md](../../../GLOSSARY.md).
This file covers only the maintainability research.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Maintainability glossary](#maintainability-glossary)
  - [The call graph](#the-call-graph)
  - [Conductance, `phi`](#conductance-phi)
  - [Volume floor](#volume-floor)
  - [Modularity, `Q`](#modularity-q)
  - [Margin over random](#margin-over-random)
  - [Inside share](#inside-share)
  - [Leverage](#leverage)
  - [Leveraged names, singleton rate, mean leverage](#leveraged-names-singleton-rate-mean-leverage)
  - [Orphan rate](#orphan-rate)
  - [Two-part code: `L(H)` and `L(D given H)`](#two-part-code-lh-and-ld-given-h)
  - [Bits saved per boundary](#bits-saved-per-boundary)
  - [`AIC` and `BIC` penalty per name](#aic-and-bic-penalty-per-name)
  - [Halstead vocabulary, length and volume](#halstead-vocabulary-length-and-volume)
  - [Token reuse and operand reuse](#token-reuse-and-operand-reuse)
  - [Cyclomatic complexity](#cyclomatic-complexity)
  - [Cognitive complexity](#cognitive-complexity)
  - [Nesting depth](#nesting-depth)
  - [Vocabulary coverage](#vocabulary-coverage)
  - [Concepts that are not metrics](#concepts-that-are-not-metrics)

<!--TOC-->
</details>

---

## The call graph

Every graph metric below is computed on the same object.

```
node   a named callable: a function, method or component
edge   one call from a caller to a callee
n      number of nodes
m      number of edges
```

**Partition.** An assignment of every node to one cluster.
A folder layout is a partition, and so is a file layout or a Leiden community set.
`k` is the number of clusters.

**Boundary.** The line between two clusters.
An edge whose two ends sit in different clusters *crosses* it.

Every graph here is a **lower bound**.
Dispatch tables, decorators and plugin hooks produce calls no static extractor sees.

---

## Conductance, `phi`

The share of a cluster's call traffic that crosses its own boundary.

```
cut(S)   edges with exactly one end in S
vol(S)   edge ends touching S           internal edge counts 2, crossing edge 1
phi(S) = cut(S) / min(vol(S), vol(rest))                      between 0 and 1
```

| `phi` moves | Meaning | Effect on the model |
|---|---|---|
| **down**, toward 0 | the cluster mostly talks to itself | a deep module, readable on its own |
| **up**, toward 1 | nearly every call leaves | a shallow module, reading it sends you elsewhere |

**Intensive.** It is a ratio, so splitting a cluster does not lower it for free.
**No threshold.** A UI primitives folder is meant to be high, a parser is not.
Read the change across a diff, never the value.
**Gamed by** duplication, which deletes crossing edges by copying code.

<details>
<summary><b>Worked example</b></summary>

A module of five functions, `A` to `E`.
One outside caller calls `A`.
Inside, `A` calls `B` and `C`, both call `D`, and `D` calls `E`.

```
internal edges  5        each counts 2 toward vol   -> 10
crossing edges  1        counts 1 toward vol        ->  1
vol = 11,  cut = 1,  phi = 1 / 11 = 0.091          deep
```

Now rewire the same five functions.
One internal call, nine calls arriving from three outside callers.

```
vol = 2 x 1 + 9 = 11,  cut = 9,  phi = 9 / 11 = 0.818   shallow
```

Same node count, same volume, nine times the conductance.
No line or branch count can tell these two apart.

</details>

---

## Volume floor

The minimum internal call volume a cluster needs before its `phi` means anything.

```
measurable(S) = internal_edges(S) >= floor          floor = 3, chosen by eye
```

| Internal edges | Meaning | Effect on the model |
|---|---|---|
| **below** the floor | the denominator is tiny, so `phi` is noise | report "not measurable", never a number |
| **above** the floor | `phi` has enough traffic to rank | the cluster enters the scorecard |

The floor exists because a ratio over a small denominator lies in both directions.
Raising the floor hides more clusters, lowering it admits more noise.
**Open:** the value 3 has no derivation.

<details>
<summary><b>Worked example</b></summary>

`model/verdict.py` is a `StrEnum`.
It has no internal calls and two callers.

```
vol = 2,  cut = 2,  phi = 2 / 2 = 1.0         "perfectly shallow"
```

The score is correct and meaningless, because an enum has nothing to call.

The opposite trap is `verify/facets.py`.
Its callers live in consuming repositories, outside the measured graph.

```
cut = 0,  phi = 0.0                           "perfectly deep"
13 of its 17 names have no caller at all
```

Both sit below the floor, so both report "not measurable".

</details>

---

## Modularity, `Q`

Newman modularity: the share of edges inside clusters, minus the share random wiring would put there.

```
m        total edges
e_c      edges inside cluster c
d_c      sum of node degrees in cluster c
Q = sum over c of [ e_c / m  -  ( d_c / 2m )^2 ]
```

The first term is what you observed.
The second is what a random graph with the same node degrees would give.

| `Q` moves | Meaning | Effect on the model |
|---|---|---|
| **up** | clusters hold more of their calls than chance explains | the partition matches the real call structure |
| **to 0** | no better than chance, or one single cluster | the partition carries no information |
| **below 0** | clusters so small that almost everything crosses | worse than having no partition |

**Why it is used.** Its best score sits between the extremes.
One cluster scores exactly 0, so collapsing the architecture never wins.
**Blind to** extraction, because a new helper's call stays inside its own folder.
**Gamed by** duplication, which lowers crossings.
Pair it with [leveraged names](#leveraged-names-singleton-rate-mean-leverage).

<details>
<summary><b>Worked example</b></summary>

Six functions in two folders.
`A`, `B`, `C` all call each other, `D`, `E`, `F` all call each other, and one call `C -> D` crosses.

```
m = 7
folder 1:  e = 3,  degrees A2 B2 C3 = 7
folder 2:  e = 3,  degrees D3 E2 F2 = 7

Q = 2 x [ 3/7 - (7/14)^2 ]
  = 2 x [ 0.429 - 0.250 ]
  = 0.357
```

Put all six in one folder instead.

```
Q = 7/7 - (14/14)^2 = 1 - 1 = 0
```

The two-folder layout beats no layout by 0.357.

</details>

---

## Margin over random

How far a partition's `Q` sits above random partitions with the same cluster count.

```
margin = Q(declared) - mean( Q(random partition, same k) )
```

| Margin moves | Meaning | Effect on the model |
|---|---|---|
| **up** | the folders encode real structure, not just granularity | the architecture is doing work |
| **to 0** | any filing into `k` folders would score the same | the folders are convention only |

Raw `Q` does not compare across codebases, and the margin does.
A webapp's denser call graph lowers its `Q` without making it worse.

<details>
<summary><b>Worked example</b></summary>

```
                     Q       random, same k    margin
Python library     0.589         0.506         +0.083
TypeScript webapp  0.425         0.322         +0.103
```

The webapp has the lower `Q` and the larger margin.
Measured this way, its folders beat chance by more.

</details>

---

## Inside share

The share of call edges that do not cross a boundary, at one boundary level.

```
inside% = edges with both ends in the same cluster / m
```

| Inside share moves | Meaning | Effect on the model |
|---|---|---|
| **toward 100%** | almost nothing crosses this boundary | the level cannot discriminate |
| **toward 0%** | almost everything crosses | also cannot discriminate |
| **differs between codebases** | the level separates them | this is the level carrying signal |

**Degenerate as a target.** One cluster scores 100%, which is why `Q` replaced it.
It is useful for comparing boundary levels, and only for that.

<details>
<summary><b>Worked example</b></summary>

```
level     Python   TypeScript   gap
language   100%       100%        0
folder      74%        61%       13
file        63%        39%       24
class       40%        39%        1
```

Language and class barely separate the two codebases.
File separates them by 24 points, so file is the boundary with the most signal.

</details>

---

## Leverage

The number of distinct call sites reaching one name: its in-degree in the call graph.

```
leverage(v) = number of edges ending at v
```

| Leverage | Meaning | Effect on the model |
|---|---|---|
| **0** | no caller in the measured graph | dead code, or a public API called from outside |
| **1** | one caller | you tidied, the name moved code without sharing it |
| **3 or more** | many callers | you found a rule, one name replaces several readings |

**Why it matters.** It is the only measurement that separates deduplication from tidying.
Both add one name, and only deduplication saves reading.
**Undercounts** for a library, whose callers live in other repositories.

<details>
<summary><b>Worked example</b></summary>

Three functions each contain the same four-line block.

```
Extract it into one helper, called from all three.
  names added: 1     leverage: 3     three copies become one    worth it

Extract a single nested block into a helper, called once.
  names added: 1     leverage: 1     code only relocated        not worth it
```

Every complexity metric scores the two refactors the same.
Leverage separates them.

</details>

---

## Leveraged names, singleton rate, mean leverage

Three summaries of the leverage distribution over a cluster or a whole graph.

```
leveraged names  = count of v where leverage(v) >= 3
singleton rate   = count of v where leverage(v) == 1  /  n
mean leverage    = m / n                              edges per name
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| leveraged names **down** while `Q` **up** | shared names were copied into callers | duplication, reject regardless of score |
| singleton rate **up** | more names serve exactly one caller | over-extraction, or a pipeline of steps |
| mean leverage **up** | each name is called more | denser reuse, or a denser archetype such as a UI |

**Leveraged names is the damper for `Q`.** Re-filing moves `Q` and leaves it unchanged.
Duplication raises `Q` and lowers it.

<details>
<summary><b>Worked example</b></summary>

```
                          Q        leveraged names
baseline               0.589            16
duplicate shared code  0.624            13      Q up, leverage down: gamed
Leiden re-filing       0.667            16      Q up, leverage same: honest
```

Duplication converts one name with three callers into three names with one caller each.
That is the move that lowers the count.

</details>

---

## Orphan rate

The share of names with no caller in the extracted graph.

```
orphan rate = count of v where leverage(v) == 0  /  n
```

| Orphan rate moves | Meaning | Effect on the model |
|---|---|---|
| **high** | the extractor missed edges, or callers are out of scope | every other score is suspect |
| **low** | the graph covers most real calls | scores are worth reading |

**A validity check, not a metric.** Print it before any score.

<details>
<summary><b>Worked example</b></summary>

The first TypeScript run reported 82.7% orphans.
Taken at face value, the webapp was five-sixths dead code.

```
187 inline lambdas counted as named symbols      removed
local variables counted as components            removed
39 renderers reached through R[kind]             still invisible
after fixes: 57% orphans
```

Each drop in the rate was a measurement bug found, not code deleted.

</details>

---

## Two-part code: `L(H)` and `L(D given H)`

Minimum Description Length applied to a partition.
A description splits into a model, the rules, and a leftover, the exceptions.

```
H          the model: which cluster each name belongs to
D          the data: the call edges
L(H)       = n x log2(k)                        bits to state every name's cluster
L(D given H) = sum over edges of
               log2(size of target cluster)     edge stays inside: short local index
               log2(n)                          edge crosses: full global index
total      = L(H) + L(D given H)
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| `L(H)` **up** | more clusters or more names to learn | the model costs more to hold in your head |
| `L(D given H)` **down** | more calls stay inside small clusters | fewer exceptions to memorise |
| both together | the trade a partition makes | score both halves, never the total alone |

**Reviewing cost is the leftover**, not the total.
**Degenerate at `k = 1`** under this scheme, so the total is not usable as a ranking.
**Open:** the Map Equation (Infomap) is the standard alternative scheme.

<details>
<summary><b>Worked example</b></summary>

Four names in two clusters of two.
Three edges stay inside a cluster and one crosses.

```
L(H)          = 4 x log2(2) = 4 x 1 = 4
L(D given H)  = 3 x log2(2) + 1 x log2(4) = 3 + 2 = 5
total         = 9
```

The same four names in one cluster.

```
L(H)          = 0                               nothing to state
L(D given H)  = 4 x log2(4) = 4 x 2 = 8
total         = 8
```

One cluster wins the total, 8 against 9.
The two clusters win the leftover, 5 against 8.
That is the degeneracy, and it is why the next metric exists.

</details>

---

## Bits saved per boundary

How much leftover a partition removes for each cluster it asks you to learn.

```
saved       = L(D given H) at k = 1   -   L(D given H) of this partition
per boundary = saved / (k - 1)
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | each boundary explains many calls | boundaries are earning their price |
| **down** | boundaries were added that explain little | over-partitioned, like single-caller names |

It is [leverage](#leverage) asked of a boundary instead of a name.
**Degenerate as a target**, because `k = 2` minimises the divisor.
Use it to compare existing partitions, never to search for one.

<details>
<summary><b>Worked example</b></summary>

Continuing the four-name example above.

```
saved         = 8 - 5 = 3
per boundary  = 3 / (2 - 1) = 3 bits
```

On this repository:

```
partition          k     per boundary
declared folders   8        90.7
one per file      37        24.0
Leiden            85        15.9
```

Each hand-drawn folder saves nearly four times what a file boundary saves.

</details>

---

## `AIC` and `BIC` penalty per name

The price of adding one parameter to a model, mapped to the price of one new name in code.

```
AIC = 2k      - 2 ln(L)        penalty per name: 2
BIC = k ln(n) - 2 ln(L)        penalty per name: ln(n)

k   names someone invented
n   size of the codebase, in lines
L   how well the model fits
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| `n` **up** | the codebase grows | under `BIC`, each new name costs more |
| `k` **up** | more abstractions | total penalty grows, fit must improve to pay for it |

**Intuition.** A new name in a small script is cheap.
The same name in a large codebase joins a bigger vocabulary and costs more to find and learn.

<details>
<summary><b>Worked example</b></summary>

```
codebase lines   ln(n)    BIC penalty   AIC penalty   ratio
     500          6.2         6.2           2          3.1x
   6,974          8.85        8.85          2          4.4x
  50,000         10.8        10.8           2          5.4x
```

A new abstraction in this repository must save about 8.85 units of fit to break even under `BIC`.

</details>

---

## Halstead vocabulary, length and volume

Counts of operators and operands in the token stream.

```
h1  distinct operators        N1  total operator occurrences
h2  distinct operands         N2  total operand occurrences

vocabulary  n = h1 + h2
length      N = N1 + N2
volume      V = N x log2(n)          bits to write the program given its vocabulary
```

It maps onto the two-part code: `n` is the model to learn, `V` is the program spelled out with it.

| Moves | Meaning | Effect on the model |
|---|---|---|
| volume **up** | more program to read | reviewing cost rises |
| vocabulary **up** | more distinct things to learn | the model half grows |

**Catches extraction**, which `Q` and cyclomatic complexity cannot.
Adding a wrapper per statement raised volume 28%.
Correlated -0.45 with measured comprehension (Peitek et al.).
**Do not use `radon hal`.** It counts a narrow operator set and misses calls.

<details>
<summary><b>Worked example</b></summary>

One line: `x = a + a`.

```
operators  =  +          h1 = 2,  N1 = 2
operands   x  a  a       h2 = 2,  N2 = 3

n = 4,  N = 5
V = 5 x log2(4) = 5 x 2 = 10 bits
```

</details>

---

## Token reuse and operand reuse

How hard the vocabulary is worked: leverage measured on tokens instead of call sites.

```
token reuse   = N / n
operand reuse = N2 / h2
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | a small vocabulary used many times | more compressible |
| **down** | many names each used rarely | new names added that do little |

**Compressibility is not quality.** Duplication raises reuse, because repeats compress well.
The reviewer still reads every copy.
Pair volume with call-site leverage, not either Halstead half alone.

<details>
<summary><b>Worked example</b></summary>

Continuing `x = a + a`.

```
token reuse   = 5 / 4 = 1.25
operand reuse = 3 / 2 = 1.5          a is used twice
```

Copy the line three times and the vocabulary stays at 4 while `N` triples.

```
token reuse   = 15 / 4 = 3.75        up, yet the code got worse
```

</details>

---

## Cyclomatic complexity

The number of independent paths through one function (McCabe).

```
CC = decision points + 1
decision points: if, elif, for, while, except, and, or, ternary, comprehension
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | more branches in one unit | more paths to test in that unit |
| **mean down** | usually more tiny units, not simpler code | a per-unit count, gamed by extraction |

**Extensive.** Splitting a function lowers it for free.
Adding 505 do-nothing wrappers cut the mean 44%, while the maximum stayed at 26.
**Tool warning.** `ruff C901` uses `mccabe`, which skips ternaries, comprehensions and `and`/`or`.
It reported 3 where `radon` reported 26.
Correlated -0.09 with measured comprehension.

<details>
<summary><b>Worked example</b></summary>

```python
def grade(score, strict):
    if score is None:                  # +1
        return "missing"
    ok = score > 50 and not strict     # +1 for `and`
    return "pass" if ok else "fail"    # +1 for the ternary
```

```
radon, lizard:  CC = 3 + 1 = 4
ruff C901:      CC = 1 + 1 = 2        misses `and` and the ternary
```

</details>

---

## Cognitive complexity

Like cyclomatic complexity, with an extra charge for each level of nesting.

```
each break in flow   +1          if, for, while, catch, boolean operator run
each nesting level   +1 more     for a break inside another break
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | branches are nested, not sequential | harder to hold in mind than flat code |
| **mean down** | also gamed by extraction | fell 62% under the stub-wrapper transform |

Measured here with `complexipy`.
Its maximum of 31 never moved under any rearrangement.

<details>
<summary><b>Worked example</b></summary>

```python
for row in rows:              # +1
    if row.ok:                # +1, +1 nesting
        if row.fast:          # +1, +2 nesting
            send(row)
```

```
cognitive = 1 + 2 + 3 = 6
cyclomatic = 3 + 1 = 4
```

The same three branches written flat, one after another, score 3 cognitive.

</details>

---

## Nesting depth

How deep a node sits in the syntax tree.

```
depth(root) = 0
depth(child) = depth(parent) + 1
reported as the maximum and the mean over all nodes
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | code inside code inside code | more context to keep while reading |
| **down** | flatter structure | each line needs less surrounding context |

**Needs no partition**, unlike `Q` and `phi`.
Extraction relocates nesting instead of removing it, so it may resist subdivision.
**Open:** untested against any rearrangement.

<details>
<summary><b>Worked example</b></summary>

```
Python library     max 21    mean 7.23
TypeScript webapp  max 66    mean 9.95
```

The webapp's 66 is JSX: an element inside an element inside a `map` inside a component.

</details>

---

## Vocabulary coverage

How much of its language's grammar a codebase actually uses.

```
coverage = distinct node kinds used / node kinds the grammar defines
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | the code uses more language features | more constructs a reader must know |
| **down** | a narrower dialect | fewer constructs, easier onboarding |

Descriptive only.
No claim about quality has been tested.

<details>
<summary><b>Worked example</b></summary>

```
Python      89 used / 128 defined  = 69.5%
TypeScript 120 used / 202 defined  = 59.4%
```

</details>

---

## Concepts that are not metrics

**Extensive.** Scales with the amount of code: lines, branches, parameters.
Splitting a unit lowers it.

**Intensive.** A ratio of two extensive quantities: `phi`, leverage, duplication rate.
Splitting a unit leaves it unchanged.

**Spring and damper.** A spring is a metric that falls under the cheapest refactor.
A damper rises when the spring falls.
Two extensive metrics are two springs, and a damper has to be intensive.

**Degenerate optimum.** A layout nobody would defend that maximises an objective.
One cluster maximises inside share, and two clusters maximise bits per boundary.

**Leftover, or residual.** `L(D given H)`: the facts no rule produced.
Reviewing cost is this, never the total.

**Kolmogorov complexity, `K(x)`.** Length of the shortest program producing `x`.
It is uncomputable, so you can never know you have refactored enough.

**Minimal sufficient statistic.** The smallest model that explains everything explainable.
The target of refactoring, observed as the point where further change stops moving the scores.

**Delta, not position.** Compare a metric to its own previous value across a diff.
The module's job cancels out and the direction of travel remains.

**Ground-truth fixture.** A small program with every call written down by hand.
It is the only way to check an extractor, and it does not yet exist.
