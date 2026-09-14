# Maintainability glossary

**Status:** reference for this directory only. **Before you start:** arithmetic, and `log2(8) = 3`.

Every metric the other documents in this directory measure, defined once.
Each entry gives the formula, what it means when the number moves, and how it is gamed.
Worked examples sit in a collapsed section under each entry.

Every metric carries an ID such as `GR-CON-01`, and [the register](#the-register) lists them all.
Cite the ID, not the prose name, anywhere a metric is named outside this file.

The repository-wide vocabulary (*case*, *cell*, *harness*) is in [GLOSSARY.md](../../../GLOSSARY.md).
This file covers only the maintainability research.

---

<details>
<summary><b>Table of Contents</b></summary>
<!--TOC-->

- [Maintainability glossary](#maintainability-glossary)
  - [How a metric is identified](#how-a-metric-is-identified)
  - [PR-LOC-01 Source lines](#pr-loc-01-source-lines)
  - [PR-VIS-02 Visual source lines](#pr-vis-02-visual-source-lines)
  - [The call graph](#the-call-graph)
  - [GR-CON-01 Conductance, `phi`](#gr-con-01-conductance-phi)
  - [GR-VOL-02 Volume floor](#gr-vol-02-volume-floor)
  - [GR-MOD-03 Modularity, `Q`](#gr-mod-03-modularity-q)
  - [GR-MAR-04 Margin over random](#gr-mar-04-margin-over-random)
  - [GR-INS-05 Inside share](#gr-ins-05-inside-share)
  - [GR-LEV-06 Leverage](#gr-lev-06-leverage)
  - [GR-LVN-07 Leveraged names, singleton rate, mean leverage](#gr-lvn-07-leveraged-names-singleton-rate-mean-leverage)
  - [GR-ORP-08 Orphan rate](#gr-orp-08-orphan-rate)
  - [GR-FAN-09 Fan-out](#gr-fan-09-fan-out)
  - [GR-SIT-10 Call-site weight](#gr-sit-10-call-site-weight)
  - [IT-MDL-01 Two-part code: `L(H)` and `L(D given H)`](#it-mdl-01-two-part-code-lh-and-ld-given-h)
  - [IT-BPB-02 Bits saved per boundary](#it-bpb-02-bits-saved-per-boundary)
  - [IT-PEN-03 `AIC` and `BIC` penalty per name](#it-pen-03-aic-and-bic-penalty-per-name)
  - [TS-HAL-01 Halstead vocabulary, length and volume](#ts-hal-01-halstead-vocabulary-length-and-volume)
  - [TS-REU-02 Token reuse and operand reuse](#ts-reu-02-token-reuse-and-operand-reuse)
  - [TS-SCR-03 Screen load](#ts-scr-03-screen-load)
  - [TS-CYC-04 Cyclomatic complexity](#ts-cyc-04-cyclomatic-complexity)
  - [TS-COG-05 Cognitive complexity](#ts-cog-05-cognitive-complexity)
  - [TS-NES-06 Nesting depth](#ts-nes-06-nesting-depth)
  - [TS-VOC-07 Vocabulary coverage](#ts-voc-07-vocabulary-coverage)
  - [EX-RES-01 Resolution rate](#ex-res-01-resolution-rate)
  - [EX-REC-02 Extractor agreement](#ex-rec-02-extractor-agreement)
  - [Concepts that are not metrics](#concepts-that-are-not-metrics)

<!--TOC-->
</details>

---

## How a metric is identified

Every metric in this file carries an ID.

```
FF-MMM-NN

FF    family: what the metric needs before it can be computed at all
MMM   a mnemonic for the metric itself
NN    sequential within the family, never reused
```

| Family | Needs | Cost of porting it to a new language |
|---|---|---|
| `PR` | the raw text | nothing |
| `TS` | a syntax tree | one tree-sitter grammar |
| `GR` | a resolved call graph, and usually a partition | a grammar and a resolution rule |
| `IT` | a quantity from another family, priced in bits | whatever that family costs |
| `EX` | an extractor's own report, or two extractions to compare | whatever those extractions cost |

The families are ordered by what they cost to extract.
That order is the answer to [GOAL.md](GOAL.md)'s question about scoring any codebase regardless of language.
A `PR` metric ports for free, and an `EX` one ports last.

An ID is permanent.
A retired metric keeps its number, and the number is never given to something else.

### The register

| ID | Metric | Status |
|---|---|---|
| [PR-LOC-01](#pr-loc-01-source-lines) | Source lines | used |
| [PR-VIS-02](#pr-vis-02-visual-source-lines) | Visual source lines | available |
| [GR-CON-01](#gr-con-01-conductance-phi) | Conductance, `phi` | used |
| [GR-VOL-02](#gr-vol-02-volume-floor) | Volume floor | used |
| [GR-MOD-03](#gr-mod-03-modularity-q) | Modularity, `Q` | used |
| [GR-MAR-04](#gr-mar-04-margin-over-random) | Margin over random | used |
| [GR-INS-05](#gr-ins-05-inside-share) | Inside share | used |
| [GR-LEV-06](#gr-lev-06-leverage) | Leverage | used |
| [GR-LVN-07](#gr-lvn-07-leveraged-names-singleton-rate-mean-leverage) | Leveraged names, singleton rate, mean leverage | used |
| [GR-ORP-08](#gr-orp-08-orphan-rate) | Orphan rate | used |
| [GR-FAN-09](#gr-fan-09-fan-out) | Fan-out | available |
| [GR-SIT-10](#gr-sit-10-call-site-weight) | Call-site weight | available |
| [IT-MDL-01](#it-mdl-01-two-part-code-lh-and-ld-given-h) | Two-part code: `L(H)` and `L(D given H)` | used |
| [IT-BPB-02](#it-bpb-02-bits-saved-per-boundary) | Bits saved per boundary | used |
| [IT-PEN-03](#it-pen-03-aic-and-bic-penalty-per-name) | `AIC` and `BIC` penalty per name | used |
| [TS-HAL-01](#ts-hal-01-halstead-vocabulary-length-and-volume) | Halstead vocabulary, length and volume | used |
| [TS-REU-02](#ts-reu-02-token-reuse-and-operand-reuse) | Token reuse and operand reuse | rejected |
| [TS-SCR-03](#ts-scr-03-screen-load) | Screen load | available |
| [TS-CYC-04](#ts-cyc-04-cyclomatic-complexity) | Cyclomatic complexity | rejected |
| [TS-COG-05](#ts-cog-05-cognitive-complexity) | Cognitive complexity | rejected |
| [TS-NES-06](#ts-nes-06-nesting-depth) | Nesting depth | available |
| [TS-VOC-07](#ts-voc-07-vocabulary-coverage) | Vocabulary coverage | available |
| [EX-RES-01](#ex-res-01-resolution-rate) | Resolution rate | used |
| [EX-REC-02](#ex-rec-02-extractor-agreement) | Extractor agreement | used |

A metric is in exactly one of three states.

| Status | Meaning |
|---|---|
| `available` | the tooling computes it and nothing rests on it yet |
| `used` | a finding in [README.md](README.md) rests on it, or another number we rely on is checked against it |
| `rejected` | measured, found wanting, and kept here only so the blind spot stays on the record |

An **available measure** is the default state.
The tooling emits a great deal for free, and emitting a number is not the same as arguing from one.
Promotion to `used` needs a finding in [README.md](README.md).
Demotion to `rejected` needs the measurement that discredited it, recorded in the entry.

---

## PR-LOC-01 Source lines

**Status:** `used`.

The line span of one definition, counted without parsing.

```
nloc(v) = last line of v - first line of v + 1
```

| `nloc` moves | Meaning | Effect on the model |
|---|---|---|
| **up** | there is more text to read | the strongest single predictor of comprehension measured so far |
| **down** | the text moved somewhere else | extraction lowers it for free, so it is a spring |

**Extensive.** Splitting a definition lowers it without changing the program.
**Why it is kept.** Lines of code reached tau -.46 against measured comprehension, where cyclomatic complexity reached -.09.
The cheapest metric in the file is also the best-correlated one.
**Gamed by** extraction, which is why it is never read on its own.

---

## PR-VIS-02 Visual source lines

**Status:** `available`.

What actually scrolls: source lines with the blanks, the comments and the line wrapping accounted for.

```
s(v) = non-blank, non-comment lines of v, each counted ceil(width / W) times
W      the line-length limit, 120 in this repository
```

It differs from [PR-LOC-01](#pr-loc-01-source-lines) in both directions.
A commented function has fewer visual lines than source lines.
A function of very wide lines has more.

**Input only.** It exists to feed the screen factor in [TS-SCR-03](#ts-scr-03-screen-load).
**It blocks the obvious game.** Without the wrap at `W`, a function halves its screen count by joining every pair of lines.
**Not strictly `PR`.** Excluding comments needs the tree in practice, and a regex would do at a pinch.

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

## GR-CON-01 Conductance, `phi`

**Status:** `used`.

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

## GR-VOL-02 Volume floor

**Status:** `used`.

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

## GR-MOD-03 Modularity, `Q`

**Status:** `used`.

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
Pair it with [leveraged names](#gr-lvn-07-leveraged-names-singleton-rate-mean-leverage).

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

## GR-MAR-04 Margin over random

**Status:** `used`.

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

## GR-INS-05 Inside share

**Status:** `used`.

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

## GR-LEV-06 Leverage

**Status:** `used`.

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

## GR-LVN-07 Leveraged names, singleton rate, mean leverage

**Status:** `used`.

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
Leiden re-filing       0.667            16      Q up, leverage same: real
```

Duplication converts one name with three callers into three names with one caller each.
That is the move that lowers the count.

</details>

---

## GR-ORP-08 Orphan rate

**Status:** `used`.

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

## GR-FAN-09 Fan-out

**Status:** `available`.

Out-degree: the number of distinct names one definition calls.

```
fanout(v) = number of edges starting at v
```

It is [GR-LEV-06](#gr-lev-06-leverage) read from the other end.
Leverage asks how many places need a name, and fan-out asks how many names a place needs.

Figures are one `graphdata.py` run over `src/pytest_xharness_eval` and `report-ui/src` on 14 September 2026, which found 635 nodes, 767 edges and 1065 call sites.

```
max 34      SessionView       report-ui/src/views/SessionView.tsx
mean 1.21
350 of 635 definitions call nothing the extractor can resolve
```

**Available.** Nothing has checked whether a high fan-out predicts anything a reviewer feels.
Its likely role is as the damper for extraction, which moves calls without removing them.

---

## GR-SIT-10 Call-site weight

**Status:** `available`.

In-degree counted once per call rather than once per caller.

```
sites(v) = sum over callers of the number of times each one calls v
```

[GR-LEV-06](#gr-lev-06-leverage) counts a caller once no matter how often it calls.
This counts every call.

Figures are one `graphdata.py` run over `src/pytest_xharness_eval` and `report-ui/src` on 14 September 2026, which found 635 nodes, 767 edges and 1065 call sites.

```
77 of 635 definitions differ between the two
fmt   report-ui/src/lib/format.ts    16 callers, 69 call sites
```

**Available, and [G6](OPEN_QUESTIONS.md#1-is-the-call-graph-right) asks whether to switch to it.** Weighting moved `phi` by at most 0.059 here and changed no ranking.
Until a case is found where the choice changes an ordering, the unweighted count is the one in use.

---

## IT-MDL-01 Two-part code: `L(H)` and `L(D given H)`

**Status:** `used`.

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

## IT-BPB-02 Bits saved per boundary

**Status:** `used`.

How much leftover a partition removes for each cluster it asks you to learn.

```
saved       = L(D given H) at k = 1   -   L(D given H) of this partition
per boundary = saved / (k - 1)
```

| Moves | Meaning | Effect on the model |
|---|---|---|
| **up** | each boundary explains many calls | boundaries are earning their price |
| **down** | boundaries were added that explain little | over-partitioned, like single-caller names |

It is [leverage](#gr-lev-06-leverage) asked of a boundary instead of a name.
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

## IT-PEN-03 `AIC` and `BIC` penalty per name

**Status:** `used`.

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

## TS-HAL-01 Halstead vocabulary, length and volume

**Status:** `used`.

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

## TS-REU-02 Token reuse and operand reuse

**Status:** `rejected`.

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

## TS-SCR-03 Screen load

**Status:** `available`.

The symbols a reader must hold to understand one function, charged like `BIC`, and multiplied once the function no longer fits on one screen.

```
screen load = k ln(N) x max(1, s / H)

k   distinct identifier spellings in the function        the names held in your head
N   tokens in the function, comments excluded             the reading the names are spread over
s   visual lines: non-blank, non-comment, wrapped at W    what scrolls
H   screen height in lines, 50 by default
W   line-length limit, 120 in this repository
```

The symbol term is the [`BIC` penalty per name](#it-pen-03-aic-and-bic-penalty-per-name) applied at function scope.
There, `n` is the codebase and the name is a definition.
Here, `N` is the function body and the name is any identifier the reader meets.
Swap `ln(N)` for 2 to get the `AIC` form, which ignores how long the function is.

The screen factor is a hinge.
Below one screen it is exactly 1, so length costs nothing beyond the tokens it adds.
Above one screen the reader can no longer see where a name was bound, and every symbol is charged again per screen.

| Moves | Meaning | Effect on the model |
|---|---|---|
| `k` **up** | more names in one unit | load rises by about `ln(N)` per name |
| `s` **past `H`** | the function scrolls | the whole symbol term is multiplied |
| `s` **up**, `k` flat | long but repetitive | load barely moves, because `ln(N)` grows slowly |

**Separates long from dense.** Line count alone ranks a flat registration block as the worst function in `src/`.
Screen load ranks it below a shorter function holding three times the names.

**Measured in `tools/screenload.py`.** Nested functions are also counted inside their parent, since the reader of the parent reads them too.

**Gamed by splitting into stubs.** Five one-screen helpers cut the load of the parent, and each helper has one caller.
Pair it with the [singleton rate](#gr-lvn-07-leveraged-names-singleton-rate-mean-leverage), which rises when that happens.
**Gamed by wide lines**, which the wrap at `W` blocks.

<details>
<summary><b>Worked example</b></summary>

Three functions from this repository, measured on 14 September 2026.

```
function                          s     N     k    k ln(N)   screens   screen load
plugin/options.py pytest_addoption  71   343    25     146       1.42        207
emit/metrics.py of                  50   391    72     430       1.00        430
views/SessionView.tsx SessionView  238  2298   195    1509       4.76       7184
```

`pytest_addoption` is the longest Python function and still has half the load of `of`.
It is 71 lines of `addoption` calls repeating the same 25 names.

`SessionView` scrolls for almost five screens while holding 195 names.
Across `report-ui/src`, 19 of 323 functions exceed one screen, and those 19 carry 61.6% of the load.
In `src/`, one of 312 does, carrying 1.0%.

</details>

---

## TS-CYC-04 Cyclomatic complexity

**Status:** `rejected`.

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

## TS-COG-05 Cognitive complexity

**Status:** `rejected`.

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

## TS-NES-06 Nesting depth

**Status:** `available`.

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

## TS-VOC-07 Vocabulary coverage

**Status:** `available`.

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

## EX-RES-01 Resolution rate

**Status:** `used`.

The share of observed call expressions the extractor turned into an edge.

```
resolved%  = call sites resolved / (resolved + ambiguous + unresolved)
ambiguous    the name matches more than one definition
unresolved   the name matches none in the measured trees
```

Figures are one `graphdata.py` run over `src/pytest_xharness_eval` and `report-ui/src` on 14 September 2026, which found 635 nodes, 767 edges and 1065 call sites.

```
resolved 32%     ambiguous 63     unresolved 2231
```

**Used as a check.** It bounds every graph score above it.
Most of the 2231 are standard-library and third-party calls, which are outside the measured trees by design.
That is why the number is a floor on trust rather than a defect count.

---

## EX-REC-02 Extractor agreement

**Status:** `used`.

How much of each extraction the other one reproduces, edge by edge.

```
agreed   edges present in both
recall of A by B = agreed / edges(A)
```

Reported by `compare.py`, which exists because neither extractor is ground truth.
The LSP resolves types and loses edges when the workspace is half-open.
Tree-sitter resolves names and invents edges when two definitions share one.

```
the two agree on about half the union of their edges
```

**Used as a check.** Low agreement says the two disagree, never which one is right.
Only a ground-truth fixture would say that, and building one is deferred under [G1](OPEN_QUESTIONS.md#1-is-the-call-graph-right).

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
