# Literature findings: cognitive complexity, comprehension, and reviewability

Research date: 2026-09-01. Lens: "low cognitive complexity" and "reviewable" code — what the
research actually says about human comprehension and code review.

**Reading convention used throughout.** Each claim is tagged:
- **[M]** what a study *measured*
- **[C]** what its authors *concluded*
- **[F]** industry *folklore* / assertion without a study behind it
- **[?]** could not verify from a primary source

---

## 0. The one-paragraph honest answer

No static, purely code-based metric reliably predicts how hard code is to understand. The best
validated one (SonarSource Cognitive Complexity) correlates ~0.54 with *comprehension time* in a
meta-analysis, but ~-0.13 with *correctness* and 0.00 with physiological load — and a peer-reviewed
replication concluded it is not a significant improvement on lines-of-code and cyclomatic
complexity. The strongest single finding across the literature is negative: Scalabrino et al. tested
121 metrics and found **none** reached even a medium correlation with understandability. Nesting
depth and parameter count do somewhat better than cyclomatic complexity in fMRI data, which is
itself an interesting result. Review-side evidence is more actionable than comprehension-side
evidence: change *size* has real, measured effects on review behaviour, and Google's own data shows
their median change is tiny.

---

## 1. Cognitive Complexity (SonarSource)

### 1.1 The specification — what it actually says

**Primary source (verified, full text read):** G. Ann Campbell, *"Cognitive Complexity: a new way of
measuring understandability"*, SonarSource white paper. Originally published with the TechDebt 2018
paper; the version read here is **Version 1.7, 29 August 2023**.
https://www.sonarsource.com/docs/CognitiveComplexity.pdf
Peer-reviewed companion: G. A. Campbell, "Cognitive Complexity: an overview and evaluation",
*Proceedings of the 2018 International Conference on Technical Debt (TechDebt '18)*, pp. 57–58.
https://dl.acm.org/doi/abs/10.1145/3194164.3194186

**Three basic rules** (verbatim from the white paper, p.5):

1. "Ignore structures that allow multiple statements to be readably shorthanded into one"
2. "Increment (add one) for each break in the linear flow of the code"
3. "Increment when flow-breaking structures are nested"

**Four increment types** (verbatim, p.5):

| Type | Definition |
|------|-----------|
| **A. Nesting** | "assessed for nesting control flow structures inside each other" |
| **B. Structural** | "assessed on control flow structures that are subject to a nesting increment, and that increase the nesting count" |
| **C. Fundamental** | "assessed on statements not subject to a nesting increment" |
| **D. Hybrid** | "assessed on control flow structures that are not subject to a nesting increment, but which do increase the nesting count" |

The white paper is explicit that the type "makes no difference in the math — each increment adds one
to the final score"; the taxonomy exists only to explain where nesting increments apply.

**Appendix B specification (verbatim, p.16) — the authoritative rule set:**

*B1. Increments — there is an increment for each of:*
- `if`, `else if`, `else`, ternary operator
- `switch`
- `for`, `foreach`
- `while`, `do while`
- `catch`
- `goto LABEL`, `break LABEL`, `continue LABEL`, `break NUMBER`, `continue NUMBER`
- sequences of binary logical operators
- each method in a recursion cycle

*B2. Nesting level — the following structures increment the nesting level:*
- `if`, `else if`, `else`, ternary operator
- `switch`
- `for`, `foreach`
- `while`, `do while`
- `catch`
- **nested methods and method-like structures such as lambdas**

*B3. Nesting increments — the following receive a nesting increment commensurate with their nested
depth inside B2 structures:*
- `if`, ternary operator
- `switch`
- `for`, `foreach`
- `while`, `do while`
- `catch`

Note the asymmetry that does the work: `else` / `else if` are in B1 and B2 but **not** B3 — they
score, and they raise the nesting level for things inside them, but they do not themselves pay a
nesting surcharge. The white paper's rationale (p.6): *"No nesting increment is assessed for these
structures because the mental cost has already been paid when reading the `if`."*

### 1.2 The specific divergences from Cyclomatic Complexity

**Methods cost nothing.** [C] "Cognitive Complexity does not increment for methods" (p.6) because
"breaking code into methods allows you to condense multiple statements into a single, evocatively
named call, i.e. to 'shorthand' it." This is the design decision that makes the metric aggregate
meaningfully above the method level — the white paper's stated secondary goal — since a domain class
of 40 getters scores 0 rather than 40.

**`switch` costs 1, total.** Verbatim (p.7): *"A switch and all its cases combined incurs a single
structural increment."* Rationale: *"a switch — which compares a single variable to an explicitly
named set of literal values — is much easier to understand than an if-else if chain because the
latter may make any number of comparisons, using any number of variables and values. In short, an
if-else if chain must be read carefully, while a switch can often be taken in at a glance."*
This is an explicit appeal to intuition, not to data.

**Boolean operators: one increment per *sequence of like operators*, not per operator.** Verbatim
(p.8): *"Cognitive complexity increments for each new sequence of like operators."* The worked
examples from the paper:

```
if (a                            // +1 for `if`
    && b && c                    // +1
    || d || e                    // +1
    && f)                        // +1        → total 4

if (a                            // +1 for `if`
    &&                           // +1
    !(b && c))                   // +1        → total 3
```
So `a && b && c && d` costs the same as `a && b`; `a || b && c || d` costs more. The stated reason:
*"boolean expressions become more difficult to understand with mixed operators."*

**Early returns are free.** Verbatim (p.8): *"`goto` adds a fundamental increment to Cognitive
Complexity, as do `break` or `continue` to a label and other multi-level jumps ... But because an
early return can often make code much clearer, no other jumps or early exits cause an increment."*
This is the guard-clause exemption — a plain `return`, `break`, or `continue` is free; only *labelled*
and multi-level jumps score.

**Recursion scores; cyclomatic complexity ignores it.** (p.8) "a fundamental increment for each
method in a recursion cycle, whether direct or indirect." Two stated motivations: recursion is a
"meta-loop", and "even some seasoned programmers find recursion difficult to understand."

**`try` and `finally` are free; each `catch` scores 1** regardless of how many exception types it
catches (p.7).

**Null-coalescing operators are free** (`a?.myObj`), as shorthand (p.6).

**Lambdas score 0 structurally but raise the nesting level by 1** (p.9). Worked example from the paper:

```java
void myMethod2 () {
  Runnable r = () -> {          // +0 (but nesting level is now 1)
    if (condition1) { … }       // +2 (nesting=1)
  };
}                               // Cognitive Complexity 2
```

**The canonical illustration (pp.5, 10)** — two Java methods with identical Cyclomatic Complexity 4:
a 4-case `switch` scores **Cognitive Complexity 1**; a doubly-nested prime-sum loop with a labelled
`continue` scores **Cognitive Complexity 7**.

**Language exceptions (Appendix A)** exist for genuine language *deficits*: COBOL's missing `else if`,
and Python decorators (a function containing only a nested function and a `return` does not raise the
nesting level). The paper says new exceptions "should come slowly."

### 1.3 THE MOST IMPORTANT FACT ABOUT THE SPECIFICATION

**The white paper contains exactly one reference: McCabe 1976.** [Verified by reading the full
22-page PDF, v1.7, 2023.] There is no validation study, no experiment, no dataset, and no empirical
justification anywhere in the document. Every design decision is justified by appeal to what
"strikes programmers as fairer", "seems intuitively obvious", or "programmer intuition". The paper
says so openly (p.11): *"Cognitive Complexity breaks from the practice of using mathematical models
to assess software maintainability. It starts from the precedents set by Cyclomatic Complexity, but
uses human judgment to assess how structures should be counted."*

Also note: **the paper proposes no threshold.** The widely-cited "15" is a SonarQube default rule
configuration, not a number in the specification. [F] Any claim that "15 is the research-backed
limit" is folklore.

### 1.3b Campbell's own "validation" — and why it does not count

The user asked specifically about Campbell's own validation. It exists, and it is not a
comprehension study.

**G. Ann Campbell, "Cognitive Complexity: An Overview and Evaluation", TechDebt '18**,
pp. 57–58. https://dl.acm.org/doi/abs/10.1145/3194164.3194186

**[M] What was measured** (as reported in Muñoz Barón et al.'s related-work section, which
summarises it): an analysis of **22 open-source projects** on SonarCloud, assessing *"whether a
development team 'accepted' the metric based on whether they fixed code areas of high Cognitive
Complexity as reported by the tool."*

**[M] Result: a 77% acceptance rate among developers.**

**[C] Campbell's argument, quoted:** *"for a metric formulated to bridge Cyclomatic Complexity's
understandability gap, the most important measure of success must be developer response."*

**[C] Muñoz Barón, Wyrich & Wagner's rebuttal, verbatim:** *"we do not consider this to be a
sufficient validation of Cognitive Complexity since its primary goal of capturing understandability
has not yet been evaluated."*

This is important framing. The metric's own evaluation measures *whether developers comply with the
tool*, not whether the metric tracks comprehension. Compliance with a linter rule is a measure of
the tool's persuasiveness (and of the low cost of the suggested refactor), not of the rule's validity.
Any gate designed on this basis will measure the same thing.

### 1.4 Validation: Muñoz Barón, Wyrich & Wagner (ESEM 2020)

**Marvin Muñoz Barón, Marvin Wyrich, Stefan Wagner, "An Empirical Validation of Cognitive Complexity
as a Measure of Source Code Understandability", ESEM '20**, Bari, Italy.
DOI https://doi.org/10.1145/3382494.3410636 · preprint https://arxiv.org/abs/2007.12520
Won **Best Full Paper Award at ESEM 2020**.
https://www.iste.uni-stuttgart.de/news/Best-Full-Paper-Award-at-The-14th-ACM-IEEE-International-Symposium-on-Empirical-Software-Engineering-and-Measurement-ESEM-2020/

**[M] What was measured.** Not a new experiment — a **meta-analysis over other people's data**.
Systematic literature search for studies that measured code understandability with open data, then
Cognitive Complexity was computed over their snippets and correlated with their outcome variables.
Aggregated dataset: **10 studies, 427 code snippets, ~24,000 individual human evaluations**
(~569 participants; Java, C/C++, C#, Scala, JavaScript). Random-effects meta-analysis on the
Fisher-z scale. Effect-size bands used: >0.1 small, >0.3 medium, >0.5 large.

**[M] The actual correlation coefficients** (verified against the paper's forest plots):

| Outcome variable | Studies | Snippets | Weighted mean r | 95% CI | Range across studies | Heterogeneity |
|---|---|---|---|---|---|---|
| **Comprehension time** | 9 | 327 | **0.54** | [0.24; 0.75] | −0.03 … 0.94 | I² = 85% |
| **Correctness** | 6 | 269 | **−0.13** | [−0.45; 0.21] | −0.52 … 0.57 | I² = 79% |
| **Subjective rating** | 4 | 203 | **−0.29** | [−0.49; −0.06] | −0.57 … −0.04 | I² = 46% |
| **Physiological (fMRI)** | 1 | 12 | **0.00** | [−0.37; 0.37] | −0.20 … 0.20 | I² = 0% |
| **Composite (time+correctness)** | 6 | 269 | **0.40** | [0.11; 0.62] | −0.10 … 0.68 | I² = 78% |

Read the heterogeneity column. I² of 79–85% on the time, correctness and composite results means
the between-study variance dominates; the individual time correlations run from −0.03 to 0.94. The
0.54 headline is a weighted mean over wildly disagreeing studies. The only *low*-heterogeneity result
(subjective rating, I² = 46%, and the fMRI one at 0%) are the weak ones.

**[C] Authors' conclusion (verbatim from the abstract):** *"Cognitive Complexity positively
correlates with comprehension time and subjective ratings of understandability. The metric showed
mixed results for the correlation with the correctness of comprehension tasks and with physiological
measures. ... It is the first validated and solely code-based metric which is able to reflect at
least some aspects of code understandability."*

Note the careful hedging: *"at least some aspects."* Their positive framing rests on comparison
against a very low bar — they explicitly compare to Scalabrino's 121-metric negative result, where
only 1 of 121 metrics reached even 0.11 with time.

**[C] Authors' threats to validity (verbatim, and this is the crucial one):**
*"Although our analysis is based on a large number of 427 different code snippets from different
languages and projects, almost all of them were of relatively low Cognitive Complexity. Only two of
the studies included code snippets with a value greater than 15, which is the default threshold in
SonarQube for reporting on too complex functions. The correlations that were found are still
meaningful, but we have little information about how well the metric works for higher values of
Cognitive Complexity and accordingly **no recommendation for a meaningful threshold**."*

**This is decisive for anyone setting a gate.** The single best validation of Cognitive Complexity
explicitly disclaims any basis for choosing a threshold, and its data barely reaches the value at
which the tool's own default rule fires. Their recommendation is only: *"keep the metric value as
low as possible."*

Further threat, verbatim: *"Different studies measure code understandability in different ways with
no clear agreement as to how those ways relate to each other."* Also: snippets had to be modified to
compile (syntax only, not control flow); two studies' datasets were no longer accessible; search
period restricted to post-2010, mitigated by backward snowballing.

### 1.5 The contradicting replication: Lavazza et al. (JSS 2023)

**Luigi Lavazza, Abedallah Zaid Abualkishik, Geng Liu, Sandro Morasca, "An empirical evaluation of
the 'Cognitive Complexity' measure as a predictor of code understandability", *Journal of Systems
and Software*, Vol. 197, 111561, March 2023.**
DOI https://doi.org/10.1016/j.jss.2022.111561 · https://dl.acm.org/doi/10.1016/j.jss.2022.111561
· https://www.sciencedirect.com/science/article/abs/pii/S0164121222002370

**[M] What was measured.** Reused data from previous understandability studies. Two goals: (1) is
Cognitive Complexity better correlated with understandability than traditional measures? (2) does
adding Cognitive Complexity improve predictive models?

**[C] Authors' conclusions (verbatim, from the published abstract):**
- *"The 'Cognitive Complexity' measure appears to be correlated to code understandability
  approximately as much as traditional measures"*
- *"the performance of models that use 'Cognitive Complexity' is extremely close to the performance
  of models that use only traditional measures"*
- *"The 'Cognitive Complexity' measure does not appear to fulfill the promise of being a significant
  improvement over previously proposed measures, as far as code understandability prediction is
  concerned."*

**[?] Could not verify** the paper's individual correlation coefficients — ScienceDirect, ACM DL and
ResearchGate all returned 403 to automated fetching, and no open preprint was located. The
conclusions above are quoted from the published abstract, which is reliable; the underlying per-model
numbers were not obtained. **If this matters to a decision, get the PDF through institutional access.**

**How to hold the two together.** They are not straightforwardly contradictory. Muñoz Barón asks "does
it correlate at all?" and answers yes for time. Lavazza asks "is it *better* than LOC and McCabe?"
and answers no. Both can be true, and together they say: Cognitive Complexity is a *fine* proxy but
not a *special* one. The marketing claim ("a new way of measuring understandability") is not supported;
the weaker claim (it tracks reading time about as well as counting lines does) is.

### 1.6 Later evidence through 2026

**Peitek, Apel, Parnin, Brechmann & Siegmund, "Program Comprehension and Code Complexity Metrics: An
fMRI Study", ICSE 2021**, pp. 524–536. ACM SIGSOFT Distinguished Paper Award.
https://dl.acm.org/doi/10.1109/ICSE43902.2021.00056 · PDF
https://www.tu-chemnitz.de/informatik/ST/publications/papers/ICSE21.pdf · replication package
https://github.com/brains-on-code/fMRI-complexity-metrics-icse2021

[M] fMRI, **19 participants**, short Java snippets, 41+ metrics explored. Kendall's τ against brain
(de)activation in four activated Brodmann areas, response time, correctness, and a subjective
card-sort rating. Participants averaged 32 s per task, 72% correct.

Headline numbers (Table II, τ with r² in brackets):

| Metric | Response time | Correctness | BA 21 | BA 44/45 (Broca's) |
|---|---|---|---|---|
| **McCabe v(G)** | **.06 (.00)** | **−.09 (.02)** | **.09 (.04)** | **−.04 (.00)** |
| LOC | .22 (.10) | −.46 (.29) | .43 (.39) | .15 (.04) |
| Halstead | .24 (.09) | −.45 (.26) | .32 (.27) | .17 (.06) |
| DepDegree (data flow) | .26 (.07) | −.41 (.22) | .41 (.24) | .22 (.09) |
| Subjective complexity | .34 (.18) | −.77 (.71) | .18 (.09) | .22 (.06) |

**[C] "McCabe has no correlation to neither response time nor correctness."** Cyclomatic complexity
is flat against every neuronal, behavioural and subjective measure in this study.

Table III extends to the top 26 of 37 differentiating metrics. Extracted rows (τ vs brain activation):

| Metric | BA 6 | BA 21 | BA 39 | BA 44/45 |
|---|---|---|---|---|
| BRANCH (branching statements) | .50 | .56 | .29 | .16 |
| **NP (number of parameters)** | .40 | .27 | **.56** | **.50** |
| **NBD (nested block depth)** | .36 | **.54** | .29 | .20 |
| D (Halstead difficulty) | .51 | .41 | .45 | .41 |
| IF NEST | .31 | .27 | .31 | .27 |
| **CogCompl (SonarQube Cognitive Complexity)** | **.30** | **.24** | **.14** | **.04** |
| v(G) (McCabe) | .21 | .10 | .12 | .00 |

**[C] Verbatim:** *"SONARQUBE's 'cognitive complexity' shows an improvement over McCabe, but only a
small correlation, at best. This corroborates a prior meta-analysis on the limitations of the
cognitive complexity regarding physiological data."* Also verbatim: *"In addition to Halstead, the
number of parameters is a second vocabulary-based metric that shows a strong correlation with brain
activation in BA 44/45."* And: *"some simple control-flow metrics, such as the number of branching
statements or the maximum loop depth, correlate more strongly than McCabe."*

**[C] Abstract conclusion:** *"Our results provide neuro-scientific evidence supporting warnings of
prior research questioning the validity of code complexity metrics."* Their positive finding is that
*textual size drives attention* and *vocabulary size burdens working memory* — i.e. the things that
predict are size and naming, not control-flow shape.

**Threat the authors raise themselves:** only 6 distinct McCabe values in the snippet set, max 8 —
below SonarQube's threshold of 10. So "McCabe is flat" is established only in the low range. They
speculate metrics "may not have a relationship with human cognition, until the values exceed some
extreme threshold."

**Esposito, Janes, Kilamo & Lenarduzzi, "Early Career Developers' Perceptions of Code
Understandability: A Study of Complexity Metrics"** (arXiv 2303.07722, 2023, rev. 2024).
https://arxiv.org/abs/2303.07722
[M] **216 early-career developers** (1–4 years' experience) rated the understandability of 12 Java
classes of varying complexity. [C] Both McCabe (CyC) and Cognitive Complexity (CoC) were *"modest
predictors for code understandability"*; no evidence either predicted problem severity. Their sharpest
formulation: **"low complexity measures indicate good understandability, but having either CoC or CyC
high makes understandability unpredictable."** That is an asymmetric, one-directional signal — worth
carrying into any gate design: a low score is informative, a high score is not.

**Hao, Hijazi, Durães et al., "On the accuracy of code complexity metrics: A neuroscience-based
guideline for improvement", *Frontiers in Neuroscience*, Feb 2023.**
https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.1065366/full
[M] EEG (64ch, 1000 Hz) + eye tracking, **27 programmers**, three Java programs. Tested LOC, v(G),
Halstead, CC-BCS, and SonarSource Cognitive Complexity (CC-Sonar). Validation of their cognitive-load
measure: EEG vs NASA-TLX rs = 0.829 (p<0.0001); EEG vs reading time rs = 0.9857 (p<0.001).
[C] **Both v(G) and CC-Sonar failed to be monotonic in measured cognitive load.** Their worked
counterexample: C1.function has CC-Sonar 5 and cognitive load 14.35, while C2.function1 has CC-Sonar
**4** and cognitive load **25.54** — lower score, nearly double the load. They also identify a
**saturation effect**: participants rated a v(G)=22 program as no more demanding than a v(G)=4–7 one
(p = 0.522, cannot reject equal distributions). Their proposed corrections: account for data
complexity (variables, operands, **parameter counts**), algorithm semantics, library/API usage,
saturation ceilings, and context-sensitive weights.
[C] Verbatim: *"popular metrics such as V(g) and the complexity metric from SonarSource tools deviate
considerably from the programmers' perception of code complexity."*

**Hao, Hijazi, Medeiros, Durães, Lam, de Carvalho & Madeira, "NRevisit: A Cognitive Behavioral Metric
for Code Understandability Assessment", EASE 2025.**
https://dl.acm.org/doi/10.1145/3756681.3757053 · https://arxiv.org/abs/2504.18345
[M] Number of eye-tracking *revisits* to each code region, validated against EEG cognitive load from
35 programmers. [C] **rs = 0.9067 to 0.9860** (p ≈ 0) against EEG ground truth — far above any static
metric. **But this is a behavioural instrument, not a static analysis**: it requires an eye tracker
and a reader. It cannot be a CI gate. It is useful as evidence that comprehension difficulty *is*
measurable — just not from the source text alone.

**[?] Could not verify** any 2026 publication that revisits Cognitive Complexity's validity at scale.
Two adjacent 2025 items surfaced but were not read in full: "Rethinking Cognitive Complexity for Unit
Tests: Toward a Readability-Aware Metric Grounded in Developer Perception"
(https://orbilu.uni.lu/handle/10993/66307) and "Complementarity in software code complexity metrics"
(*JSS* 2025, https://www.sciencedirect.com/science/article/abs/pii/S0164121225003486) — the latter's
title suggests the "portfolio of metrics" thesis, and would be worth a read.

---

## 2. Code comprehension research more broadly

### 2.1 The central negative result

**Scalabrino, Bavota, Vendome, Linares-Vásquez, Poshyvanyk & Oliveto, "Automatically Assessing Code
Understandability", *IEEE Transactions on Software Engineering*** (2019/2021; extends their ASE 2017
paper "Automatically assessing code understandability: How far are we?").
PDF https://www.cs.wm.edu/~denys/pubs/TSE'19-Understandability.pdf · ASE'17
https://www.cs.wm.edu/~denys/pubs/ASE'17-Readability.pdf

**[M] What was measured.** **121 metrics** — code-related, documentation-related, and
developer-related — against **444 human evaluations from 63 developers**. Six proxies for
understandability were defined: PBU (perceived binary understandability), TNPU (time needed for
perceived understanding), AU (actual understanding, from verification questions), TAU (timed actual
understanding), ABU50%, BD50%. Kendall's τ, bands: <0.1 none, 0.1–0.3 small, 0.3–0.7 medium, ≥0.7 strong.

**[M] Results, verbatim from the paper:**
- *"none of the 121 experimented metrics is able to capture code understandability, not even the ones
  assumed to assess quality attributes apparently related, such as code readability and complexity."*
- *"51 out of the 73 metrics considered showed no correlation at all with any of the proxies."*
- 8 metrics had a weak correlation with PBU; **only one** with TNPU; 13 with AU; 13 with TAU; 2 with BD50%.
- Highest correlation with perceived understandability: **maximum line length, τ ≈ −0.13**, tied with
  developer's language-specific experience, τ ≈ 0.13.
- Highest with TNPU: **DFT of conditionals, τ = 0.11** — that is the single best time predictor out of 121.
- Highest with actual understandability (AU): average textual coherence, τ ≈ **−0.16** — and the sign
  is backwards from what the authors expected.
- **Number of parameters correlates negatively with actual understandability, τ ≈ −0.13.**
- *"Summary for RQ1. None of the metrics we considered achieve a medium/strong correlation with any of
  the proxies of code understandability we defined."*

**[M] Combined models did not rescue it.** Regression results: best correlation for TNPU was **0.18**
(ML Perceptron), MAE 124.8 s against a mean TNPU of 143.4 s. Verbatim: *"any prediction of TNPU made
with the state of the art metrics is practically useless."* Best for AU and TAU: 0.37 and 0.36
respectively — medium — but MAE 0.29 on a 0–1 scale means *"we should expect our model to be wrong
by one answer, on average."*

**[C] Authors' conclusion.** Explicitly framed by the authors as a **negative result** (it is in the
paper's index terms). Understandability depends *far more on the developer* than on the code — a
finding they state in RQ0 and revisit by adding developer position as a model feature.

**This is the single most important paper for calibrating expectations.** Anyone proposing a
maintainability metric has to explain why it escapes this result.

### 2.2 Reconciling Scalabrino with Muñoz Barón

They used overlapping data. Muñoz Barón's meta-analysis *includes* Scalabrino-lineage datasets and
gets 0.54 for time where Scalabrino got 0.11 for their single best metric. The difference is method:
Scalabrino correlates *within* a large heterogeneous snippet pool; Muñoz Barón computes a
**per-study** correlation then takes a random-effects weighted mean across 10 studies, with I² = 85%.
Aggregating across studies where each study's snippets were designed to vary systematically will
produce higher within-study correlations than pooling everything. Neither is wrong; they answer
different questions. **[Flagged: this reconciliation is my analysis of the two methods, not a claim
either paper makes.]**

### 2.3 Theory: what comprehension actually is

The classical models — all of them decades old and none of them yielding a metric:

- **Brooks (1983), top-down/hypothesis-driven model.** Programmers generate, refine and repudiate
  hypotheses at descending levels of abstraction; the process is opportunistic and **driven by
  "beacons"** — recognisable code fragments that signal the presence of a known structure.
- **Soloway & Ehrlich, plan-based model.** Programmers hold **"programming plans"** — *"program
  fragments that represent stereotypical action sequences in programming to achieve a specific
  goal"* — plus "rules of programming discourse". Comprehension is matching code against a plan
  library; code that violates discourse rules (e.g. a variable named for one thing used as another)
  is measurably harder even at identical structural complexity.
- **Bottom-up / chunking models (Pennington, Shneiderman).** Read statements, **chunk** them into
  higher-level abstractions, cross-reference. Working-memory-bounded.
- **von Mayrhauser & Vans, integrated metamodel** — programmers switch between top-down and bottom-up
  opportunistically.

Surveys: Storey, "Theories, Methods and Tools in Program Comprehension: Past, Present and Future"
(IWPC/ICPC 2005) https://www.ptidej.net/courses/inf6306/fall10/slides/course8/Storey06-TheoriesMethodsToolsProgramComprehension.pdf ·
von Mayrhauser & Vans, "Program Comprehension During Software Maintenance and Evolution", *IEEE
Computer* 1995 https://www.cs.kent.edu/~jmaletic/cs69995-PC/papers/von_mayrhauser95.pdf ·
O'Brien, "Software Comprehension — A Review & Research Direction"
https://www.st.cs.uni-saarland.de/edu/empirical-se/2006/PDFs/brien03.pdf

**Why this matters for metrics.** Every one of these theories says comprehension difficulty is a
function of *the fit between the code and what the reader already knows* — beacons the reader
recognises, plans the reader holds, chunks the reader can form. That is a property of the
code-reader *pair*, not of the code. A purely static metric is structurally incapable of measuring
it. Scalabrino's finding that understandability depends more on the developer than the code is
exactly what these theories predict.

**Peitek's fMRI evidence supports this.** Verbatim from ICSE 2021: *"Complexity metrics seem to
neglect that programmers try to take such mental shortcuts. For example, McCabe counts the number of
all possible execution paths, but programmers often do not have to consider all paths; just enough to
solve the current task."* A participant who recognised a list of square numbers immediately expected
a square-root algorithm — a beacon, in Brooks's terms, collapsing the comprehension cost to near zero
regardless of the control-flow score.

### 2.4 Honest state of the art

**Is there ANY metric that reliably predicts how hard code is to understand? No.**

What the evidence does support, ranked by strength:
1. **Size and vocabulary beat control flow.** LOC, Halstead volume, identifier vocabulary and
   parameter count outperform McCabe in fMRI (Peitek 2021), and size is what drives attention.
2. **Data flow beats control flow.** DepDegree consistently outperformed McCabe on brain activation
   (τ .41–.50 vs .00–.10). Peitek et al. explicitly propose *"the delta between control flow measured
   by McCabe and data flow measured by DepDegree"* as a promising future metric.
3. **Nesting depth and branch count beat cyclomatic complexity** (Peitek Table III: NBD τ up to .54,
   BRANCH up to .56, vs v(G) ≤ .21).
4. **Cognitive Complexity is a modest improvement on McCabe** — real but small, and not better than LOC.
5. **Cyclomatic complexity predicts essentially nothing about comprehension.** It was never designed
   to; McCabe 1976 proposed it for *testability*. Campbell's white paper concedes this in its
   opening paragraph.
6. **Behavioural measures (gaze revisits, EEG) predict very well** — rs > 0.90 — but need a human in
   a lab.

### 2.5 Does the metric at least predict *defects* or *maintenance cost*?

A separate question from comprehension, and the answer is also weak.

**Lenarduzzi, Saarimäki & Taibi, "Some SonarQube Issues have a Significant but Small Effect on
Faults and Changes: A large-scale empirical study", *Journal of Systems and Software*, Dec 2020**
(arXiv 2019). https://arxiv.org/abs/1908.11590
[M] **33 Apache Java projects**, 726 commits, ~27,000 faults, 12 million changes, 95,000+ technical
debt items across 200,000+ classes, violating **173 SonarQube rules**.
[C] Verbatim: *"Clean classes (classes not affected by TD items) are less change-prone than dirty
ones, but the difference between the groups is small."* Clean classes were **more** change-prone
than classes carrying Code Smell or Security Vulnerability issues. **For faults, there was no
measurable difference between clean and dirty classes.** They also report *"a lot of incongruities
in the type and severity level assigned by SonarQube."*
**Implication for gate design: SonarQube's own severity ratings are not a reliable ordering.** Do not
inherit a tool's severity taxonomy as if it encoded evidence.

**Borg, Ezzouhri & Tornhill, "Ghost Echoes Revealed: Benchmarking Maintainability Metrics and Machine
Learning Predictions Against Human Assessments", ICSME 2024.** https://arxiv.org/abs/2408.10754
[M] Benchmarked state-of-the-art ML maintainability models, CodeScene Code Health, **SonarQube
Maintainability Rating**, and **Microsoft's Maintainability Index** against human expert assessments.
[C] CodeScene's Code Health *"matches the accuracy of SotA ML and outperforms the average human
expert."* They warn about **SonarQube's "tendency to generate many false positives"** and explicitly
*"question the validity of previous studies that relied solely on SonarQube for establishing ground
truth."*
**[Conflict-of-interest note: Adam Tornhill is the founder of CodeScene, whose tool wins the
benchmark. Treat the ranking accordingly; the SonarQube false-positive finding is corroborated
independently by Lenarduzzi et al. above, the CodeScene result is not.]**

### 2.6 The measurement problem underneath all of this

**Wyrich, Bogner & Wagner, "40 Years of Designing Code Comprehension Experiments: A Systematic
Mapping Study", *ACM Computing Surveys* 56(4), 2023, pp. 1–42.**
https://dl.acm.org/doi/abs/10.1145/3626522 · https://arxiv.org/abs/2206.11102 · open PDF
https://research.vu.nl/ws/portalfiles/portal/361250595/40_Years_of_Designing_Code_Comprehension_Experiments_A_Systematic_Mapping_Study.pdf
[M] **95 source-code comprehension experiments published 1979–2019**, mapped by design
characteristics. [C] Their finding relevant here is methodological: comprehension is measured in
widely varying, non-comparable ways across the literature. This is the same complaint Muñoz Barón
et al. raise as their central limitation. **There is no agreed operationalisation of "understandable",
which is a structural reason the correlations in this literature will stay noisy.**

### 2.7 A 2026-relevant aside: AI-generated code and these metrics

Flagged as a live but thinly-evidenced area; include only with caveats.

- **Molison, Moraes, Melo, Santos & Assunção, "Is LLM-Generated Code More Maintainable & Reliable
  than Human-Written Code?", ESEM 2025.** https://arxiv.org/abs/2508.00700
  [M] SonarQube over Python solutions at three difficulty levels, across zero-shot, few-shot and
  fine-tuned configurations. [C] LLM code had **fewer bugs with lower remediation effort overall**,
  but *"LLM solutions sometimes introduce structural issues that are not present in human-written
  code"* at competition difficulty. Modest, mixed result.
- **[F / vendor data — do not treat as research]** GitClear's widely-circulated reports of rising
  "code churn" and duplication in AI-assisted codebases are vendor-published analytics without peer
  review or an open dataset. Widely quoted secondary figures such as "AI-generated code introduces
  1.7× more issues" trace to marketing content, not studies. **Could not verify any of these against
  a primary, methodologically described source.**

---

## 3. Nesting depth, function length, and parameter count

### 3.0 Summary table

| Rule | State of the evidence |
|---|---|
| "Functions must be tiny (2–20 lines)" | **No empirical support.** Pre-2000 evidence runs the *other* way (defect density falls as size rises). The best modern evidence supports ~24 SLOC — 6–12× larger than Clean Code prescribes — and is derived from a benchmark distribution, not a cognitive limit. |
| "Module size has an optimum (U-curve)" | **Contested.** Hatton 1997 argues 200–400 lines. El Emam et al. 2002 explicitly refute the U-curve as unsupported. Rosenberg 1997 shows much of the effect is a ratio-correlation artifact. |
| Nesting depth | **Weak but real** support for comprehension *speed and confidence* effects; **not** for correctness. **No** empirical basis for any specific number (3, 4…). |
| Parameter count | **Directionally supported** by three independent modalities (fMRI, comprehension, EEG). **No evidence-derived limit exists.** One large-corpus study puts it near the bottom of 17 method-level metrics (τ = 0.18). |
| 7±2 | **Misreading of Miller 1956.** Folklore, and Miller himself called the number a coincidence. |

### 3.1 The strongest evidence-based number in this whole report: 24 SLOC per Java method

**Chowdhury, Uddin & Holmes, "An Empirical Study on Maintainable Method Size in Java", MSR 2022**,
Pittsburgh. https://arxiv.org/abs/2205.01842 · dataset
https://github.com/shaifulcse/MaintainableSLOC-data

This is the closest thing the literature has to an evidence-derived length limit, and it is worth
understanding in full because its *method* is reusable and its *caveats* are as important as its
headline.

**[M] What was measured.** **785,606 Java methods** extracted from **49 projects**, tracked across
their version histories; 520,874 survived a two-year-lifetime filter. Getters/setters excluded.
Five maintenance indicators: #revisions, new additions, diff sizes, edit distances, and
#buggy-commits. Kendall's τ. SLOC computed three ways (standard, as-is, pretty-printed) to test
sensitivity to formatting.

**[M] RQ1 — size correlates with maintenance effort.** Correlation coefficients were **positive in
all 49 projects**, but the range is wide and honest: for #revisions, docx4j gave τ = 0.05 while
voldemort gave τ = 0.56. Bug-proneness correlated **significantly lower** than change-proneness.
Verbatim: *"at the method-level, code metrics are comparatively less helpful for bug prediction than
for change prediction."* And their own caution, verbatim: *"it is unrealistic to expect very high
correlation between a code metric and maintenance effort. A very high correlation would mean that
maintenance effort can be estimated just by using one code metric. This is unrealistic because there
are many factors that influence code maintenance."*

**[M] RQ2 — how the 24 came about.** They applied **Alves, Ypma & Visser's benchmark-threshold
methodology** (see §6) to their own 49-project corpus. That procedure weights each method by its
share of its project's total SLOC, aggregates identical sizes, normalises per project, and reads
critical values off a cumulative distribution at the **70th, 80th and 90th percentiles of weighted
code volume**. The resulting size bands:

| Size | Lower bound | Upper bound | Percentile |
|---|---|---|---|
| Small | – | **24** | 70% |
| Medium | 25 | **36** | 80% |
| Large | 37 | **63** | 90% |
| Very large | 64 | – | – |

**[M] They then validated the band, which is what makes this different from a percentile assertion.**
Wilcoxon rank-sum comparisons between adjacent size categories, 3 comparisons × 49 projects = 147 per
indicator:

| Sample | #Revisions | Additions | DiffSize | EditDistance | #BuggyCommits |
|---|---|---|---|---|---|
| All 49 projects | 82.98% | 86.52% | 87.23% | 87.94% | 77.30% |
| Top 20 by method count | 96.67% | 96.67% | 96.67% | 96.67% | 91.67% |

(percentage of comparisons statistically significant at p ≤ 0.05)

**[M] The crucial nuance is in the effect sizes (Cliff's Delta), and it is the finding most people
drop when citing this paper:**

| Indicator | Small→Medium | Medium→Large | Large→Very Large |
|---|---|---|---|
| #Revisions | 0% negligible, 55.1% medium, 34.7% large | 35.4% negligible, 58.3% small | 29.6% negligible, 59.1% small |
| DiffSize | 0% negligible, **87.8% large** | 22.9% negligible, 66.7% small | 20.5% negligible, 52.3% small |
| EditDistance | 0% negligible, **89.8% large** | 18.8% negligible, 60.4% small | 22.7% negligible, 45.5% small |
| #BuggyCommits | **38.8% negligible, 57.1% small, 0% large** | 70.8% negligible | 52.3% negligible |

**Read that table carefully.** The entire effect lives in the **small→medium step**. Going from
medium to large, or large to very large, has negligible-to-small effect sizes. Verbatim from the
paper: *"converting a medium method to a large method, or a large method to a very large method are
not as harmful as converting a small method to medium method."* And bug-proneness shows essentially
no effect at any step.

**So the defensible claim is narrow: crossing ~24 lines is where the marginal cost appears; beyond
that, further length is nearly free. That is an argument for a single soft threshold, not for a
sliding scale of severity, and not for a bug-prevention rationale.**

**[M] RQ3 — does decomposition help or just redistribute?** They could not find paired
decomposed/undecomposed versions of real projects, so they used a proxy: treat any group of small
methods mergeable under strict rules (B called only by A; both ≤24 SLOC; transitive merging allowed)
as if it were the result of a past decomposition, then compare the *summed* change/bug-proneness of
the group against individual methods >24 SLOC. **[C] They conclude decomposition genuinely reduces
maintenance effort rather than redistributing it** — verbatim from the discussion: *"We also provide
evidence that inherently large methods should be refactored to a group of helper methods, each within
24 SLOC (RQ3)."* **[Flag: this is a proxy design, not an intervention study; the merged groups are
inferred, not observed. Weaker than RQ1/RQ2.]** It is, however, the only direct empirical answer
found to the "does splitting functions actually help, or does it just create shotgun surgery?"
objection — and it points the opposite way from the Clean Code critics.

**[M] RQ4 — size is a proxy for the others.** Controlling method size to ≤24 SLOC also controlled
McCabe, McClure, a readability model, and the Maintainability Index. Effect sizes were **large in
97.96%–100% of projects for the small→medium comparison** across all four quality factors (except
readability, where medium→large was small and large→very-large negligible).
[C] Verbatim: *"By controlling size we can control other complex code quality metrics, such as
McCabe, McClure, Readability, and Maintainability index."*
**This is a strong argument for metric parsimony: if you gate on size, the complexity metrics mostly
come along for free, and adding them buys little independent signal.**

**[C] And the paper directly attacks a widely-cited folklore number.** Verbatim: *"Although Visser et
al. recommended that developers should keep their method within 15 source lines of code, **this
recommendation was from intuition only, not based on evidence**. Also, in RQ2, we have provided clear
evidence that keeping method size always within 15 SLOC is less realistic."* That is a peer-reviewed
paper saying, in print, that the Software Improvement Group's well-known 15-line guideline is
unfounded. Worth knowing before adopting any published threshold.

### 3.2 Parameter count — better supported than expected

Three independent lines of evidence, from three different measurement modalities, all point the same
way. This is unusual in this literature and worth noting.

1. **fMRI (Peitek et al., ICSE 2021, above).** "NP" (number of parameters) was among the **strongest**
   metrics against brain activation: τ = .40 (BA 6), .27 (BA 21), **.56 (BA 39)**, **.50 (BA 44/45,
   Broca's area)** — outperforming Cognitive Complexity (.30/.24/.14/.04) and McCabe (.21/.10/.12/.00)
   on every area. The authors call it out by name: *"the number of parameters is a second
   vocabulary-based metric that shows a strong correlation with brain activation in BA 44/45."*
2. **Human comprehension (Scalabrino et al., TSE).** *"number of parameters negatively correlates
   with AU (τ ≈ −0.13)"* — one of only 13 metrics out of 121 to reach even a weak correlation with
   *actual* understandability, and one the authors say was independently corroborated by their
   developer interviews (RQ3).
3. **EEG (Hao, Hijazi, Durães et al., Frontiers in Neuroscience 2023).** Their proposed correction to
   complexity metrics leads with **"Data Complexity: Variables, operands, and parameter counts
   substantially impact comprehension difficulty but are ignored by V(g) and CC-Sonar."**

**[C] Honest summary: parameter count has more converging empirical support as a comprehension
signal than cyclomatic complexity does.** **[?] What does NOT exist, as far as this research found,
is an evidence-derived *number*.** No study located here derives "N parameters is the limit." The
familiar limits (3, 4, 7) are style-guide assertions. **The defensible position is "fewer parameters
measurably helps", not "more than N is a violation."**

### 3.3 Nesting depth

**[M] fMRI evidence (Peitek et al., ICSE 2021, Table III).** "NBD" (nested block depth) scored
τ = .36 (BA 6), **.54 (BA 21)**, .29 (BA 39), .20 (BA 44/45) — clearly ahead of Cognitive Complexity
and far ahead of McCabe. "IF NEST" scored .31/.27/.31/.27. And in the paper's own words, *"some
simple control-flow metrics, such as the number of branching statements or the **maximum loop
depth**, correlate more strongly than McCabe."*

**[C] So nesting depth is a better comprehension signal than the composite metrics built on top of
it.** That is a slightly awkward result for Cognitive Complexity, whose central innovation *is* the
nesting increment: the raw ingredient outperforms the recipe in the one physiological study that
measured both.

**Direct comprehension evidence — Johnson, Lubo, Yedla, Aponte & Sharif, "An Empirical Study
Assessing Source Code Readability in Comprehension", ICSME 2019**, pp. 513–523.
https://www.semanticscholar.org/paper/An-Empirical-Study-Assessing-Source-Code-in-Johnson-Lubo/4e63ff35c69adaedb6c9bb2fbe15c1ab7a84efce
[M] Online controlled experiment on two readability rules — **nesting** and **looping** — with
**32 Java methods** in a 2×2 design (follows/violates rule × logically correct/incorrect), ~275
participants (undergrads, MSc, professionals). [C] Minimising nesting **decreases reading and
understanding time**, **increases confidence**, and *"suggests"* improved bug-finding ability. Note
the authors' own hedge on the third outcome.
**[?] The reported participant subgroup counts (208 + 49 + 61 = 318) do not sum to the reported total
of 275 in the secondary sources reachable here. Unresolved.**

**Eye-tracking replication — Park, Johnson, Peterson, Yedla, Baysinger, Aponte & Sharif, "An eye
tracking study assessing source code readability rules for program comprehension", *Empirical
Software Engineering* 29:160, 2024.** https://link.springer.com/article/10.1007/s10664-024-10532-x
[M] Lab replication with eye tracking, 46 participants, rules "minimize nesting" and "avoid do-while".
Following the nesting rule vs violating it:

| Outcome | Effect |
|---|---|
| Confidence | **+14.8%** |
| Time on task | **−7.1%** |
| **Accuracy finding bugs** | **−5.4%** (not statistically significant — but the sign is *wrong* for the rule) |
| Fixation time on code lines (when *violating*) | −9.9%, with 3.5% fewer fixations |

**[C] Honest reading: what replicates is speed and subjective confidence, not correctness. The
confidence gain is roughly double the time gain — the classic signature of a processing-fluency
effect rather than a comprehension effect. No study has shown that reducing nesting reduces defects.**

**Nesting as a change-proneness predictor.** Chowdhury et al., "The Good, the Bad, and the Monstrous:
Predicting Highly Change-Prone Source Code Methods at Their Inception", *ACM TOSEM* 2025.
https://arxiv.org/abs/2408.05704 · https://dl.acm.org/doi/10.1145/3715006
[M] Kendall's τ between 17 method-level metrics and edit distance over a ~1.25M-method corpus; all
significant at p ≤ 0.05, and the authors stress **"None of the correlation coefficients are strong"**:

| Metric | τ | Metric | τ |
|---|---|---|---|
| Size (SLOC) | **0.34** | NVAR | 0.28 |
| Halstead Length | 0.34 | NCOMP | 0.28 |
| FanOut | 0.33 | Readability | −0.25 |
| MaintainabilityIndex | −0.33 | Getter/Setter | −0.23 |
| Variables | 0.32 | CommentRatio | 0.19 |
| **MaximumBlockDepth** | **0.31** | **Parameters** | **0.18** |
| SimpleReadability | −0.31 | IndentSTD | 0.17 |
| McCabe | 0.30 | isPublic | −0.12 |
| | | isStatic | 0.04 |

Max nesting depth (0.31) sits mid-table, below raw size (0.34) — consistent with the size-confounding
literature. **Parameter count (0.18) is second-lowest.** Note this *contradicts* the fMRI ranking in
§3.2 — different outcome variable (change-proneness vs brain activation), so both can hold, but it
means the parameter-count case is not uniform.

**Adjacent classic, frequently miscited:** Miara, Musselman, Navarro & Shneiderman, "Program
indentation and comprehensibility", *CACM* 26(11):861–867, 1983.
https://www.cs.umd.edu/~ben/papers/Miara1983Program.pdf — Pascal, blocked vs non-blocked style ×
0/2/4/6 spaces. Blocking style made no difference; **indent level did, with 2–4 spaces best**. This
is about indentation *width*, not nesting *depth*; it is routinely cited as if it were the latter.

**[?] No study located derives a specific nesting-depth threshold** from defect or comprehension
data. "Max depth 3" and similar are style-guide assertions (§3.6).

### 3.4 The module-size paradox: the older evidence points the other way

This is the part most "small functions" advocacy omits, and it needs stating carefully because the
metric involved (defect *density*) is partly an artifact.

**Basili & Perricone, "Software Errors and Complexity: An Empirical Investigation", *CACM*
27(1):42–52, 1984.** https://dl.acm.org/doi/abs/10.1145/69605.2085
[M] ~90 KLOC Fortran satellite software at NASA/Goddard SEL; modules binned by LOC; errors per KLOC:

| Module size (LOC) | Errors/1k lines (all) | Errors/1k lines (modules with ≥1 error) |
|---|---|---|
| 50 | 16.0 | 65.0 |
| 100 | 12.6 | 33.3 |
| 150 | 12.4 | 24.6 |
| 200 | 7.6 | 13.4 |
| >200 | 6.4 | 9.7 |

[C] *"module size did not account for error proneness. In fact, it was quite the contrary — the
larger the module, the less error-prone it was."*
**[Second-hand: the table is reproduced from Derek Jones' Shape of Code, https://shape-of-code.com/2023/09/ ,
not read from the original CACM tables.]**

**Hatton, "Reexamining the fault density–component size connection", *IEEE Software* 14(2):89–97,
1997.** https://ieeexplore.ieee.org/document/582978/ · author's full preprint (read in full)
https://www.leshatton.org/Documents/Ubend_IS697.pdf
[M] **Not a new experiment** — an aggregation of nine prior case studies across Ada, C, C++, Fortran,
Pascal, assembler and macro-assembler (Hatton & Hopkins 1989 on the NAG Fortran library, ~1600
routines / ~250 KLOC over 15 releases; Davey et al. 1993; Möller & Paulish 1993 at Siemens; Compton &
Withrow 1990; Basili & Perricone 1984; Shen et al. 1985; Kitchenham & Mellor 1991; plus personal
communications). His claim: *"there have been no conflicting studies."*
[M] The shape: faults grow **logarithmically** with component complexity up to a cut-off
(`Nbugs = m·log₁₀(r·Ω)`), then **quadratically**. The cut-off sits at **"about 200–400 lines"** and is
*"apparently independent of language"*. Plotted as density, this is the **U-curve**.
[M] His worked example: 1000 lines as 5 × 200-line components ⇒ 5·log₁₀(200) ≈ **25 bugs**; as
50 × 20-line components ⇒ 50·log₁₀(20) ≈ **150 bugs**. He calls this *"apparently inescapable but
unpleasant."*
[C] Verbatim: *"there is nothing conjectural about the fact that published reliability studies are
currently in serious conflict with the conventional wisdom that structural decomposition or
modularisation of systems into small, easily manageable components makes better systems. In terms of
reliability, it almost certainly does not."*
**[CRITICAL CAVEAT — the mechanism is 7±2 folklore.]** Hatton derives the log-then-quadratic shape
from a speculative two-level memory "cache overflow" model, and attributes programmer variance to
*"the known 7±2 variation in the 'size' of short-term memory."* He labels his own system-level
predictions "conjectures [that] need to be subjected to further experiments." **See §3.5 — this
inference is exactly the step Miller's paper forbids.** So the single most-cited number for optimal
function length has a folklore cognitive model bolted onto it.

**Rosenberg, "Some misconceptions about lines of code", METRICS '97, pp. 137–142.**
https://www.semanticscholar.org/paper/Some-misconceptions-about-lines-of-code-Rosenberg/31078af3520ac5f85dee8fd23a00b15d009cdb38
[C] Correlating size against defect *density* (defects ÷ size) produces **artificial ratio
correlations**: because size is in the denominator, a negative size–density relationship arises
partly by construction. **Basili & Perricone, Hatton's aggregation, and most "small modules are
worse" claims are density-based and therefore partly this artifact.**
**[Second-hand; METRICS '97 text not read.]**

**El Emam, Benlarbi, Goel & Rai, "The Confounding Effect of Class Size on the Validity of
Object-Oriented Metrics", *IEEE TSE* 27(7):630–650, 2001.**
https://ieeexplore.ieee.org/document/935855
[M] C&K metrics plus Lorenz & Kidd subset against fault-proneness on a large C++ telecom framework,
with and without controlling for class size. [C] Before size control, the metrics showed the expected
associations; **after controlling for class size, the associations largely vanished** — size explained
the variation. Recommendation: re-examine earlier validations under size control.
**[?] Two conflicting secondary summaries exist — "none of the metrics were associated with
fault-proneness any more" vs "only four of 24 remain related, only two useful for prediction." Could
not resolve against the paywalled text.**
**Published dissent:** Evanco, "Comments on…", *IEEE TSE* 29(7):670–672, 2003.
https://ieeexplore.ieee.org/document/1214331/ — argues size is not a legitimate confounder because it
does not *temporally precede* the OO metrics.
**Modern replication:** Tahir, Bennin, Xiao & MacDonell, "Does class size matter? An in-depth
assessment of the effect of class size in software defect prediction", *EMSE* 2021.
https://arxiv.org/abs/2106.04687 — [C] *"the size effect is not always significant for all metrics"*;
consistent mediation only for CBO→defects. Recommendation: test for the size effect per dataset
rather than control reflexively.

**El Emam, Benlarbi, Goel, Melo, Lounis & Rai, "The Optimal Class Size for Object-Oriented Software",
*IEEE TSE* 28(5):494–509, 2002.**
https://www.semanticscholar.org/paper/The-Optimal-Class-Size-for-Object-Oriented-Software-Emam-Benlarbi/e7a6b2516b4490654e31095db5e9ea2b08b823de
[C] Names the U-shaped defect/size curve the **"Goldilocks Conjecture"** and reports **"unambiguous
evidence that there is no threshold effect of class size"**, concluding that "optimal class size,
smaller classes are better, and threshold effects conjectures have no sound theoretical nor empirical
basis." **This is a direct, same-era, top-venue rebuttal of Hatton's 200–400 optimum. Anyone citing
the U-curve without citing this is telling half the story.**
**[Second-hand; paywalled.]**

**Koru, El Emam, Zhang, Liu & Mathew, "Theory of relative defect proneness", *EMSE* 13(5):473–498,
2008.** https://link.springer.com/article/10.1007/s10664-008-9080-x (closed-source replication:
https://link.springer.com/article/10.1007/s10664-010-9132-x)
[C] Across ten open-source products, a consistent **power law** in which defect proneness rises *more
slowly* than size — i.e. smaller modules are proportionally more defect-prone. Their recommendation
is about QA prioritisation, **not** a design instruction to write bigger functions.
**[Second-hand; paywalled.]**

**Fenton & Neil, "A Critique of Software Defect Prediction Models", *IEEE TSE* 25(5):675–689, 1999.**
https://ieeexplore.ieee.org/document/815326/ — the standing meta-critique of this whole line: the
defect-vs-failure gap, no consistent size pattern across datasets, and a call for causal/Bayesian
models. **[Read via abstract and summaries.]**

**How to hold §3.1 and §3.4 together.** Chowdhury 2022's 24-SLOC result and Hatton's 200–400
"optimum" are not measuring the same thing. Chowdhury measures *change*-proneness at *method*
granularity in modern Java with non-parametric statistics and effect sizes; Hatton aggregates
1980s–90s *fault-density* data at *component* granularity, in a metric Rosenberg shows is biased. And
Chowdhury's RQ3 directly tests Hatton's decomposition pessimism and finds against it — *"a group of
small methods, with sum SLOC x, are generally collectively less change- and bug-prone than an
individual large method with SLOC x"* — though with mostly *negligible* per-project effect sizes, so
the direction is right and the magnitude is small. **The defensible synthesis: decomposition is not
harmful, smallness past ~24 lines buys little, and nobody has shown tiny functions help.**

### 3.5 "7±2" — what Miller actually measured, and why the software use is folklore

**George A. Miller, "The Magical Number Seven, Plus or Minus Two: Some Limits on our Capacity for
Processing Information", *Psychological Review* 63:81–97, 1956.** Full text:
https://labs.la.utexas.edu/gilden/files/2016/04/MagicNumberSeven-Miller1956.pdf

**The paper covers two distinct, unrelated phenomena, and Miller says so explicitly.**

**(i) Span of absolute judgment** — identifying the magnitude of a **unidimensional** stimulus without
comparison. Measured as channel capacity in **bits**, not items:

| Dimension | Channel capacity | ≈ distinguishable categories |
|---|---|---|
| Loudness (Garner) | 2.3 bits | ~5 |
| Size of squares (Eriksen & Hake) | 2.2 bits | ~5 |
| Points on a line (Hake & Garner) | 3.25–3.9 bits | **10–15** (largest measured) |
| Curvature | 1.6 bits | lowest measured |
| Pitch | — | ~6 |

**And the limit evaporates when stimuli are multidimensional:** Pollack & Ficks combined six acoustic
variables at five values each and obtained **7.2 bits ≈ 150 absolutely identifiable categories.**
Miller lists three routine escapes from the limit: relative rather than absolute judgment, adding
dimensions, and sequencing judgments.

**(ii) Span of immediate memory** — measured in **chunks**, and Miller's central point is that this is
**independent of information per chunk**: *"people can repeat back eight decimal digits, but only nine
binary digits."* He reports that his own information-constancy hypothesis **failed**.

**Miller's own verdict, verbatim:**
> *"In spite of the coincidence that the magical number seven appears in both places, the span of
> absolute judgment and the span of immediate memory are quite different kinds of limitations that
> are imposed on our ability to process information. Absolute judgment is limited by the amount of
> information. Immediate memory is limited by the number of items."*

**His closing paragraph, verbatim:**
> *"Perhaps there is something deep and profound behind all these sevens… But I suspect that it is
> only a pernicious, Pythagorean coincidence."*

The paper opens with *"My problem is that I have been persecuted by an integer"* — it is framed
throughout as a rhetorical conceit.

**Chunking is what kills the code application specifically.** Miller's own emphasis is on **recoding**:
an expert reads a whole idiom as one chunk. A limit stated in *lines*, *parameters*, or *nesting
levels* assumes a fixed chunk size, which is precisely what Miller shows is not fixed. It is also
exactly what the beacons-and-plans literature (§2.3) predicts.

**Modern correction: Cowan, "The magical number 4 in short-term memory: A reconsideration of mental
storage capacity", *Behavioral and Brain Sciences* 24(1):87–114, 2001.**
https://www.cambridge.org/core/services/aop-cambridge-core/content/view/44023F1147D4A1D44BDC0AD226838496/S0140525X01003922a.pdf
[C] Verbatim from the abstract: *"Miller (1956) summarized evidence that people can remember about
seven chunks… However, that number was meant more as a rough estimate and a rhetorical device than as
a real capacity limit."* Cowan's synthesis supports **three to five chunks** when rehearsal and
long-term-memory support are controlled.

**[F] State plainly: the software-engineering use of 7±2 — as a bound on nesting levels, parameters,
local variables, methods per class, or lines per function — is folklore.** It misapplies a paper that
(a) measured two different things, (b) called the shared number a coincidence, (c) showed the limit
dissolves with added dimensions and chunking, and (d) closed by disowning it. The number that
survived replication is ~4, not 7, and it bounds *rehearsal-blocked recall of arbitrary items* — not
reading code that is on the screen in front of you.

**[?] Could not verify:** the author of "Magical numbers: the seven-plus-or-minus-two myth", *IEEE
Transactions on Professional Communication* 2002, https://ieeexplore.ieee.org/document/1003695/ ;
and R. Bailey's *Dr. Dobb's* "The Myth of 'Seven, Plus or Minus 2'" (domain no longer resolves).

### 3.6 Clean Code and the style guides: assertion, not evidence

**What Clean Code actually prescribes** (Robert C. Martin, 2008 — the claim under test):
- p.34: *"The first rule of functions is that they should be small. The second rule of functions is
  that they should be smaller than that."*
- *"Functions should hardly ever be 20 lines long"*; functions should be *"just two, three, or four
  lines long."*
- *"Blocks within `if` statements, `else` statements, `while` statements, and so on should be one line
  long."*
- On arguments: *"The ideal number of arguments for a function is zero (niladic)… Three arguments
  (triadic) should be avoided where possible. More than three (polyadic) requires very special
  justification."*

**[F] No empirical citation accompanies any of these.** They rest on the "Do One Thing" principle and
a testing-combinatorics argument. The nearest direct empirical test (Chowdhury 2022) lands at 24
SLOC — **6–12× above** Martin's 2–4 lines.

**Code Complete (McConnell), §7.4 "How Long Can a Routine Be?"** — the honest outlier, because it
actually cites studies, and they mostly contradict the folklore.
https://flylib.com/books/en/2.823.1.64/1/

| Study cited | Reported finding |
|---|---|
| Basili & Perricone (1984) | Routine size **inversely** correlated with errors up to 200 LOC |
| Shen et al. (1985) | Routine size showed **no** correlation with errors |
| Card, Church & Agresti (1986); Card & Glass (1990) | Small routines (≤32 lines) **not** correlated with lower cost or fault rate; larger routines (≥65 lines) **cheaper per line** |
| Selby & Basili (1991) | Routines <143 statements had **23% more errors per line** — but were **2.4× cheaper to fix** |
| Lind & Vairavan (1989) | Code needed **least** changing when routines averaged **100–150 lines** |
| IBM (per Jones 1986) | Routines **>500 lines** most error-prone |

[C] McConnell's own conclusion: no study distinguished among sizes above 200 lines, so *"if you want
to write routines longer than about 200 lines, be careful."* **The most-cited practitioner text sets
its limit at 200 lines — 50–100× Martin's — and every study it cites is from 1984–1991 in Fortran,
Pascal, PL/1, Ada and assembly.**
**[?] McConnell's widely-quoted "Few people can understand more than three levels of nested ifs" —
could not determine what, if anything, he cites for it.**

**Linux kernel coding style** (https://docs.kernel.org/process/coding-style.html — read directly):
- *"if you need more than 3 levels of indentation, you're screwed anyway, and should fix your program."*
- *"Functions should be short and sweet… They should fit on one or two screenfuls of text (the
  ISO/ANSI screen size is 80x24)"* — implying ~24–48 lines, though it also says function length is
  "inversely proportional to the complexity and indentation level."
- Locals: *"they shouldn't exceed 5-10, or you're doing something wrong."*
- **Stated justification: *"A human brain can generally easily keep track of about 7 different things,
  anything more and it gets confused."*** — unattributed 7±2 folklore (§3.5). **No study cited anywhere
  in the document.**

**Google C++ Style Guide** (https://google.github.io/styleguide/cppguide.html — read directly),
verbatim: *"Prefer small and focused functions. We recognize that long functions are sometimes
appropriate, so **no hard limit is placed on functions length**. If a function exceeds about **40
lines**, think about whether it can be broken up without harming the structure of the program."*
Rationale is a plausibility argument about future modification. **No evidence cited. Nesting depth:
not addressed. Parameter count: not addressed** (only parameter *ordering*, and even that "is not a
hard-and-fast rule").

**Chromium C++ style guide**
(https://chromium.googlesource.com/chromium/src/+/main/styleguide/c++/c++.md — read directly):
**says nothing about function length, nesting depth, or parameter count**; it defers to Google's
guide. **Any citation of "Chromium's nesting rule" is a misattribution.**

**[F] The pattern: all four style guides state numbers; none cites a study.** McConnell is the only
one that engages the literature, and the literature he cites points the opposite way from the doctrine
that grew up around him. The numbers in circulation (3 levels, 40 lines, 48 lines, 24 lines, 20 lines,
4 lines, 3 parameters) have no shared empirical parentage — they are conventions that hardened.

### 3.7 The Clean Code counter-argument, labelled as argument

**Ousterhout vs. Martin**, https://github.com/johnousterhout/aposd-vs-clean-code — a written debate
between John Ousterhout (*A Philosophy of Software Design*, 2018) and Robert C. Martin on method
length, comments, and TDD.

Ousterhout's position: decomposition can go too far. **Deep** methods have simple interfaces hiding
substantial functionality; **shallow** methods have interfaces complex relative to what they hide. Two
methods are **"entangled"** when *"in order to understand how one of them works internally, you also
need to read the code of the other"*, forcing the reader to *"flip back and forth between the
implementations."* He claims Martin's 2–4-line guidance *"encourages programmers to create teeny-tiny
methods that suffer from both shallow interfaces and entanglement."*

**[F] Neither side cites empirical evidence.** This is a disagreement about which cognitive cost
dominates — separation of concerns vs. navigation cost — argued from experience. It is the
best-articulated *opinion* on the question and should be cited as opinion.

**The broadest folklore test found: Roehm, Veihelmann, Wagner & Juergens, "Evaluating Maintainability
Prejudices with a Large-Scale Study of Open-Source Projects", 2018.** https://arxiv.org/abs/1806.04556
[M] 10 industry-belief hypotheses against **6,897 GitHub repositories, 402 million LOC, 5 languages**.
[C] *"Overall, most hypotheses are not supported by open-source data."* Accepted: C has longer methods;
Java > C# maintainability; Java interface docs better. **Rejected: JavaScript is worse;
team-developed code is higher quality; large codebases have lower maintainability; high-maintainability
projects are more popular/forked.** The cleanest demonstration that widely-held maintainability beliefs
mostly fail when measured.

**On extract-method specifically:** "Behind the Intent of Extract Method Refactoring: A Systematic
Literature Review", https://arxiv.org/abs/2312.12600 — notes that extraction *"may introduce
additional local variables and parameters, which can adversely hinder program comprehension and add a
maintenance burden."* **[?] But this appears as a stated limitation, not a measured effect. No
controlled experiment was found showing that extracting many tiny methods harms comprehension.** If
that study exists, this research did not find it. **Chowdhury 2022 RQ3 is the only direct empirical
evidence on the question and it points the other way.**

**Other opinion pieces, unverified:** qntm, "It's probably time to stop recommending Clean Code",
https://qntm.org/clean (HTTP 403 on fetch); "Codin' Dirty", https://htmx.org/essays/codin-dirty/ (not
fetched). arXiv 2507.19721 "Clean Code In Practice" surfaced repeatedly in searches but **the abs page
returned unrelated metadata — do not cite without independent confirmation.**

---

## 4. Reviewability

### 4.1 The headline: review is a comprehension activity, not a defect-detection activity

**Bacchelli & Bird, "Expectations, Outcomes, and Challenges of Modern Code Review", ICSE 2013**
(Microsoft, CodeFlow). https://sback.it/publications/icse2013.pdf
*(Full text read.)*

**[M] Study design — a genuine mixed-method design, unusually strong for this literature:**
(1) **observed 17 industrial developers** performing reviews; (2) interviews to saturation;
(3) **manually card-sorted 570 review comments drawn from 200 review threads**;
(4) **surveyed 165 managers** (28% response from 600) **and 873 programmers** (44% response).

**[M] Stated motivations, ranked by 873 developers** (3 pts for 1st choice, 2 for 2nd, 1 for 3rd):

| Rank | Motivation | 1st choice | 2nd | 3rd |
|---|---|---|---|---|
| 1 | **Finding defects** | 383 (44%) | 204 (23%) | 96 (11%) |
| 2 | **Code improvement** | 337 (39%) | 208 (24%) | 135 (15%) |
| 3 | Alternative solutions | | | |
| 4 | Knowledge transfer | | | |
| 5 | Team awareness | | | |

Managers agreed: finding defects was the top reason for **44%** of managers; code improvement for
**51 (31%)**.

**[M] Actual outcomes — the card sort of 570 real comments tells a different story:**

| Category | Comments | Share |
|---|---|---|
| **Code improvements** | **165** | **29%** |
| **Understanding** (clarification questions and answers) | — | **2nd most frequent** |
| Social communication | — | 3rd |
| **Defects** | **78** | **14%** (4th of nine) |
| Knowledge transfer | 12 | ~2% |

Within the 165 code-improvement comments: 58 on better practices, 55 on removing unnecessary/unused
code, 52 on readability. Within the 78 defect comments: **65 were logical issues**, 6 high-level, 5
security, 3 exception handling.

**[C] Authors' conclusion, verbatim:** *"Review comments about defects are few, comprising one-eighth
of the total in our sample, and mostly address 'micro' level and superficial concerns; while
programmers and managers would expect more insightful remarks on conceptual and design level
issues."* And their diagnosis: *"the outcome of code review does not match the main expectation of
both programmers and managers—finding defects."*

**[C] The mechanism they identify is comprehension cost.** Verbatim from a participant:
*"understanding the code takes most of the reviewing time"*; and *"the most difficult thing when
doing a code review is understanding the reason of the change."* Their survey quantified it:

- **798 of 873 (91%)** said it takes longer to review files they are **not familiar with**.
- **716 (82%)** said reviewers familiar with the changed files give **different** feedback — described
  as *"substantially deeper, more detailed and insightful."*
- Reviewers go and **talk to the author in person 20%–40% of the time** to get context.
- On a Likert scale of understanding needed per outcome: **finding defects required the most
  understanding**, followed by proposing alternative solutions — both *"clearly stand out."*

**[C] The load-bearing conclusion for a reviewability metric, verbatim:** *"if managers and developers
want code review to match their need for finding defects, context and change understanding must be
improved."*

**This is the strongest empirical link in the whole report between comprehension and review.** The
review literature says defect-finding is gated on understanding; the comprehension literature (§2)
says no metric measures understanding well. Together they say: **a "reviewability" metric should aim
at reducing the reviewer's comprehension load, and cannot expect to measure comprehension directly.**

### 4.2 The Google change-size data

**Sadowski, Söderberg, Church, Sipko & Bacchelli, "Modern Code Review: A Case Study at Google",
ICSE-SEIP 2018**, Gothenburg. https://sback.it/publications/icse2018seip.pdf *(Full text read.)*

**[M] Scale — by far the largest dataset in this section.** *"On an average workday at Google, about
20,000 changes are committed that meet the filter criteria… Our final dataset includes the
approximately **9 million changes** created by more than **25,000 authors and reviewers** from January
2014 until July 2016… and about **13 million comments**."* Changes with zero reviewers and
robot-authored changes were filtered out. Qualitative arm: **12 interviews** (median 5 years' tenure)
plus a survey with **44 valid responses from 98** engineers (45%).

**[M] The change-size distribution — quoted verbatim:**
> *"At Google, over **35% of the changes** under consideration **modify only a single file** and about
> **90% modify fewer than 10 files**. **Over 10% of changes modify only a single line of code**, and
> the **median number of lines modified is 24**."*

**[M] Reviewer counts — verbatim:**
> *"At Google… **fewer than 25% of changes have more than one reviewer**, and **over 99% have at most
> five reviewers with a median reviewer count of 1**. Larger changes tend to have more reviewers on
> average. However, even very large changes on average require fewer than two reviewers."*

Footnoted: *"30% of changes have comments by more than one commenter, meaning that about 5% of
changes have additional comments from someone that did not act as an approver."*

**[M] Latency and cadence — verbatim:**
> *"developers have to wait for initial feedback on their change a median time of **under an hour for
> small changes and about 5 hours for very large changes**. The overall (all code sizes) **median
> latency for the entire review process is under 4 hours**."*
> *"the median developer authors about **3 changes a week**, and 80 percent of authors make fewer than
> 7 changes a week… the median for changes reviewed by developers per week is **4**, and 80 percent of
> reviewers review fewer than 10 changes a week."*
> *"**70% of changes are committed less than 24 hours after they are mailed out** for an initial review."*
> *"developers spend an average of **3.2 (median 2.6) hours a week** reviewing changes… low compared to
> the 6.4 hours/week of self-reported time for OSS projects."*
> *"over **80% of all changes involve at most one iteration** of resolving comments."*

**[M] Comment volume rises with size, then falls:** *"the average number of comments per change grows
with the number of lines changed, reaching a **peak of 12.5 comments per change for changes of about
1250 lines**. Changes larger than this often contain auto-generated code or large deletions, resulting
in a lower average number of comments."*
**Read that carefully: past ~1250 lines, review commentary collapses. That is the clearest
quantitative signature of "too big to review" found in this research — and it is far above any
folklore threshold.**

**[C] Authors' conclusion:** *"Code review at Google has converged to a process with markedly quicker
reviews and smaller changes… Moreover, **one reviewer is often deemed as sufficient**, compared to two
in the other projects."* And on why: *"**The size distribution of changes is an important factor in
the quality of the code review process.** Previous studies have found that the number of useful
comments decreases and the review latency increases as the size of the change increases."*

### 4.3 Rigby & Bird's cross-project numbers

**Rigby & Bird, "Convergent Contemporary Software Peer Review Practices", ESEC/FSE 2013.**
DOI https://doi.org/10.1145/2491411.2491444
**[?] The primary PDF could not be retrieved** (sback.it returns 403/404 to automated fetching, ACM DL
403s). **The figures below are quoted from Sadowski et al. 2018, which replicates Rigby & Bird's
analysis and cites their numbers directly** — a reliable secondary, but secondary.

**[M] Median change size per project** (as reported by Sadowski et al.): **AMD 44 lines; Lucent 263
lines**; Bing, Office and SQL Server at Microsoft "somewhere between those boundaries". Open-source
projects: **11 to 32 lines changed**, per Rigby et al.

**[M] Median time to approval:** **AMD 17.5 h; Chrome OS 15.7 h; three Microsoft projects 14.7 h,
19.8 h, 18.9 h.** A separate Microsoft study put median time to approval at **24 h**.

**[M] Reviewer count:** Rigby & Bird found convergence on **two** reviewers *"remarkably regardless of
whether the reviewers were explicitly invited (such as in Microsoft projects, who invited a median of
up to 4 reviewers) or whether the change was openly broadcasted for review."*

**[C] Their much-repeated claim, as quoted by Sadowski:** a *"minimal increase in the number of
comments about the change when more [than 2] reviewers were active"*, concluding that **two reviewers
find an optimal number of defects.**
**[Contradicted at Google]:** *"At Google, the situation is different: A greater number of reviewers
results in a greater average number of comments on a change."* **So the "two reviewers is optimal"
result did not replicate at Google's scale. Treat it as project-dependent, not a law.**

### 4.4 The 200–400 LOC / 500 LOC-per-hour figures: what they actually are

**These are the most-cited numbers in all of code review, and they are vendor-published.**

**Primary source: SmartBear Software, *Best Kept Secrets of Peer Code Review* (Cohen et al.), and the
associated Cisco Systems case study.** The claims as published on SmartBear's own page
(https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/), read directly:

| Claim (verbatim) | Attributed to |
|---|---|
| *"developers should review no more than **200 to 400 lines of code (LOC) at a time**"* | SmartBear study of Cisco Systems |
| *"significant drop in defect density at rates faster than **500 LOC per hour**"* | SmartBear research |
| *"Do not review for more than **60 minutes** at a time"* | cited in article |
| A review of 200–400 LOC over 60–90 minutes should yield **"70–90% defect discovery"** | SmartBear/Cisco |
| *"lightweight code review takes **less than 20% the time** of formal reviews and finds just as many bugs"* | SmartBear/Cisco |
| *"spot checking" **20% to 33%** of code gave lower defect density with minimal effort* | SmartBear/Cisco |
| *"Formal, or heavyweight, inspection averages **nine hours per 200 LOC**"* | SmartBear/Cisco |

**[F — assess this honestly]:**
- It is a **commercial white paper published by the vendor of the code-review tool used to collect the
  data**. It is not peer-reviewed.
- The commonly-repeated study scale (**~2,500 reviews, ~50 developers, ~3.2 million LOC at Cisco over
  10 months**) is widely cited but **could not be confirmed against a primary document in this
  research** — SmartBear's public page states the conclusions without the method. **Could not verify.**
- **No raw data, protocol, or statistical detail is publicly available.** The "70–90% defect discovery"
  figure in particular has no stated denominator (defects discovered out of what known population?).
- The defect-density-vs-inspection-rate relationship is **confounded by exactly the ratio artifact
  Rosenberg described (§3.4)**: defects ÷ LOC falls mechanically as LOC rises.

**Verdict: cite these as an industry rule of thumb with a plausible mechanism and a commercial
origin. Do not present them as research findings.** The peer-reviewed numbers that *do* exist
(Google's median 24 lines / 1 file; Rigby & Bird's 11–263 lines) happen to sit well **below** the
200–400 band anyway, so the practice the folklore recommends is not in dispute — only its evidentiary
status.

**Fagan inspection, the ancestor:** M. E. Fagan, "Design and code inspections to reduce errors in
program development", *IBM Systems Journal* 15(3):182–211, 1976.
https://ieeexplore.ieee.org/document/5388086
**[?] The primary text was not retrieved in this research.** Fagan's prescribed inspection rates
(commonly quoted as ~125–150 LOC/hour for code inspection) and his reported defect-removal
efficiencies are widely repeated but **were not verified here**, and the replication record was not
established. **Flagged as unverified; do not quote numbers from it without reading it.**

### 4.5 Reviewability as a measurable property

**What the Google data implies is measurable and matters:**
- **files touched** (35% single-file, 90% under 10 files),
- **lines changed** (median 24; comment volume peaks at ~1250 lines then collapses),
- **iterations** (>80% of changes need at most one),
- **reviewer count** (median 1).

These are all cheap to compute from a diff, and Google's distribution gives real percentile anchors
rather than invented ones. **This is the most directly transferable material in the report for a
reviewability gate — and note it argues for percentile-style targets, not hard limits.**

**Change cohesion / tangling — the one metric with a demonstrated cost:**

**Herzig & Zeller, "The Impact of Tangled Code Changes", MSR 2013.**
https://www.st.cs.uni-saarland.de/publications/files/herzig-msr-2013.pdf *(Full text read.)*
[M] **Five open-source Java projects**; **more than 7,000 change sets manually classified** as tangled
or atomic; then an automated multi-predictor untangling algorithm.
[M] Verbatim results: *"we found **up to 15% of all bug fixes** to consist of multiple tangled
changes"*; *"on average **at least 16.6% of all source files are incorrectly associated with bug
reports**"*; and *"between **6% and 50% (harmonic mean: 17.4%)** of files originally marked as most
defect prone do not belong to this category."*
[C] Verbatim recommendation: *"we recommend that version control systems and processes be set up to
**avoid tangling changes** whenever possible."*

**Note carefully what this does and does not show.** Herzig & Zeller measured the damage tangled
commits do to **research datasets and defect-prediction models**, not to human reviewers. **It is
strong evidence that commit atomicity is measurable and that its absence corrupts downstream
analysis; it is not, by itself, evidence that tangled changes are harder to review.** The reviewer
argument is plausible and follows from Bacchelli's comprehension finding, but it is an inference, not
this paper's result. **Anyone citing Herzig & Zeller for "atomic commits are easier to review" is
over-reading it.**

**[?] Could not verify** in this research, and worth chasing if the topic matters:
- **McIntosh, Kamei, Adams & Hassan** on code review coverage and participation vs post-release
  defects (MSR 2014, extended in *EMSE* 2016) — the McGill PDF mirror failed TLS verification and no
  other primary copy was reached.
- **Kononenko et al.**, "Investigating code review quality" (2016).
- Any peer-reviewed study directly relating **changeset size to defect escape rate** (as opposed to
  comment count or latency). Sadowski et al. cite such findings second-hand (*"the number of useful
  comments decreases and the review latency increases as the size of the change increases"*) but the
  underlying papers were not read here.
- **DORA batch size:** DORA's guidance treats small batch size as an enabler of the four/five key
  metrics, but **no primary DORA analysis quantifying batch size against outcomes was located.**

---

## 5. Coupling and structure metrics that survive scrutiny

### 5.1 The CK suite: what actually replicated

**Basili, Briand & Melo, "A Validation of Object-Oriented Design Metrics as Quality Indicators",
*IEEE TSE* 22(10):751–761, October 1996.**
http://www.cs.umd.edu/~basili/publications/journals/J62.pdf *(Full text read.)*

**[M] Design:** **eight medium-sized C++ information management systems built from identical
requirements**, sequential lifecycle, OMT method. Univariate and multivariate logistic regression of
CK metrics against class fault-proneness.

**[M] Per-metric results, from the paper:**

| CK metric | Result |
|---|---|
| **WMC** (weighted methods per class) | Significant |
| **DIT** (depth of inheritance) | *"very significant (p-value = 0.0000)"*; larger DIT ⇒ higher fault probability; **R² rises 0.06 → 0.13** for new/modified classes |
| **RFC** (response for a class) | *"very significant overall (p-value = 0.0000)"*; **R² 0.06 → 0.24** (new/modified) and **→ 0.36** (UI classes) |
| **CBO** (coupling between objects) | *"significant and more particularly so for UI classes (p-value = 0.0000 and R² = 0.17)"* |
| **NOC** (number of children) | Significant but **in the opposite direction to the hypothesis** — *"The larger the NOC, the **lower** the probability of fault detection"*, which they attribute to verbatim-reused classes having many children |
| **LCOM** (lack of cohesion) | ***"shown to be insignificant in all cases"*** — and they blame the metric's definition, which *"sets cohesion to zero for classes with very different cohesions"* |

**[C] Conclusion, verbatim:** *"five out of the six Chidamber and Kemerer's OO metrics appear to be
useful to predict class fault-proneness during the high- and low-level design phases"* and they *"show
to be better predictors than the best set of 'traditional' code metrics."* Their own hedge: *"Our
results should be interpreted as **maximum possible gains and not as expected gains**."*

**[Critical caveats a citation must carry]:**
1. **These were student projects** at the University of Maryland, not industrial code — the paper's
   own "future work" is *"replicating this study in an industrial setting."*
2. **The R² values are 0.06–0.36.** Even the best case explains about a third of the variance.
3. **NOC's sign is backwards** and **LCOM is dead.** So "the CK suite is validated" really means
   "coupling (CBO/RFC), inheritance depth (DIT), and size (WMC) carry some signal; cohesion as
   defined by CK does not."
4. **§3.4's confounder applies in full force here.** El Emam et al. (TSE 2001) showed CK associations
   largely vanish once class size is controlled, and this paper does not control for size. **The
   honest reading is that much of the CK "validation" is size wearing a costume.**

**Original: Chidamber & Kemerer, "A Metrics Suite for Object Oriented Design", *IEEE TSE* 20(6):
476–493, 1994.** https://ieeexplore.ieee.org/document/295895

### 5.2 Fan-in / fan-out

**Henry & Kafura, "Software Structure Metrics Based on Information Flow", *IEEE TSE* SE-7(5):510–518,
1981.** https://ieeexplore.ieee.org/document/1702955 — the source of `length × (fan-in × fan-out)²`.
**[?] Primary not retrieved in this research; the formula is stated from general knowledge and should
be checked against the paper before being quoted.**

**[?] Shepperd's critique** ("A critique of cyclomatic complexity as a software metric", *Software
Engineering Journal* 1988; and Shepperd & Ince on design metrics) is real and well known — the
substance being that the Henry–Kafura measure's validation was circular and its definitions
ambiguous — **but no primary text was read here. Do not quote specifics.**

**What *was* verified about fan-out** comes from §3.3's large-corpus table: in Chowdhury et al.'s
TOSEM 2025 study of ~1.25M methods, **FanOut had τ = 0.33 against edit distance — third of 17
metrics, above McCabe (0.30) and max block depth (0.31), just below raw size (0.34).** That is the
best modern evidence located for fan-out carrying real signal, and it is still a *weak* correlation
by the authors' own insistence.

### 5.3 Martin's instability and abstractness

**Robert C. Martin, "OO Design Quality Metrics: An Analysis of Dependencies" (1994), later in *Agile
Software Development: Principles, Patterns, and Practices* (2002).**
Definitions: efferent coupling `Ce`, afferent coupling `Ca`, **instability `I = Ce / (Ca + Ce)`**,
**abstractness `A = abstract classes / total classes`**, **distance from the main sequence
`D = |A + I − 1|`**.

**[F/?] Empirical validation: none located.** This research found **no study validating I, A, or D
against defects, maintenance effort, comprehension, or any independent outcome.** The metrics are
derived from stated design principles (the Stable Dependencies and Stable Abstractions Principles),
and the "main sequence" is a geometric construction, not an empirical regularity. Tools implement
them widely (NDepend, JDepend, Structure101), which is adoption, not evidence.
**State this plainly when the metrics come up: they are a well-reasoned design heuristic with no
published empirical support that this research could find.** That is a weaker claim than "they are
invalid" — absence of evidence — but it is a materially different footing from CBO or size.

### 5.4 Design Structure Matrices, propagation cost, and the architectural core

This is the strongest-looking body of work in Section 5, and its central metric has real numbers.

**MacCormack, Rusnak & Baldwin, "Exploring the Structure of Complex Software Designs: An Empirical
Study of Open Source and Proprietary Code", *Management Science* 52(7):1015–1030, 2006** (HBS Working
Paper 05-016). https://www.hbs.edu/ris/Publication%20Files/05-016.pdf *(Full text read.)*

**[M] Method.** Build a Design Structure Matrix of file-level dependencies, take its transitive
closure, and define **propagation cost** as the density of the visibility matrix — verbatim, the
proportion of *"other source files in a system"* that a change to one file *"has the potential to
impact"*. Because for every fan-out there is a corresponding fan-in, the row and column measures are
identical.

**[M] The actual figures — Table 1, comparable versions:**

| | Mozilla (98-04-08) | Linux 2.1.105 |
|---|---|---|
| Source files | 1,684 | 1,678 |
| Dependencies | 6,717 | 9,110 |
| Density per 1000 file-pairs | 2.4 | 3.4 |
| **Propagation cost** | **17.35%** | **5.82%** |
| Functions per file | 12.8 | 17.7 |
| LOC per file | 670 | 733 |

**[M] Table 2 — Mozilla before and after the deliberate re-design:**

| | Mozilla (98-04-08) | Mozilla (98-12-11) |
|---|---|---|
| Source files | 1,684 | 1,508 |
| Dependencies | 6,717 | 3,037 |
| **Propagation cost** | **17.35%** | **2.78%** |
| LOC per file | 733 | 530 |

Verbatim: *"the propagation cost of the design has dropped from 17.35% to 2.78%. That is, changes to
a source file have the potential to impact **80% fewer source files**, on average, after the
re-design."* And: *"the re-design of Mozilla reduced propagation cost by over 80%."*

**[M] Table 3 — after the re-design, Mozilla was *more* modular than Linux:** propagation cost
**2.78%** (Mozilla) vs **5.65%** (Linux 2.1.88).

**[C] Conclusions, honestly stated by the authors:** results are *"exploratory"* and *"consistent
with a view that different modes of organization are associated with designs that possess different
structures"* — but crucially, *"purposeful managerial actions can have a significant impact in
adapting a design's structure."*
**[Note what is NOT claimed: this paper links propagation cost to organisation and to deliberate
re-design. It does not link propagation cost to defects, cost, or maintainability outcomes.]**

**Baldwin, MacCormack & Rusnak, "Hidden Structure: Using Network Methods to Map System Architecture",
HBS Working Paper 13-093 (2014), later *Research Policy*.**
https://www.hbs.edu/ris/Publication%20Files/13-093_e9b3b0e1-1d1f-4b1f-9e0a-000000000000.pdf
*(Full text read.)*
**[M]** Applied to **1,286 software releases from 17 distinct systems**. Method: find the largest
cyclic group (the **"Core"**), then classify files as Core / depends-on-Core / depended-on-by-Core /
Peripheral. Classification thresholds: a system is **core-periphery** if the largest cyclic group is
**>6%** of elements; **borderline** at 4–6%; **hierarchical** below 4%.
**[M] Result: 867 of 1,286 releases (67%) classified as core-periphery.** In their worked example the
Core is **33% of files**, and *"the Core, the components depending on it, and those it depends upon,
account for 73% of the system"*; their contrasting hierarchical example has a largest cyclic group of
only **3.5% of files**. Linux's Core dropped to **16 files (3.6% of the system)** at one point and
then *"consistently accounted for 4–5%"*; Linux 2.6 *"wavered around the 6% threshold."*
**[C]** Their contribution is a **classification methodology and a set of stylized facts**, not a
causal claim.

**MacCormack & Sturtevant, "Technical debt and system architecture: The impact of coupling on
defects", *Journal of Systems and Software* 120:170–182, 2016.**
DOI https://doi.org/10.1016/j.jss.2016.06.007
**[?] COULD NOT VERIFY.** Every access route failed (HBS working-paper URL 403; ScienceDirect and ACM
DL 403 to automated fetching; no open preprint located; the related MIT thesis, Sturtevant, "System
Design and the Cost of Architectural Complexity" (2013), https://dspace.mit.edu/handle/1721.1/79551,
returned HTTP 405). **The widely-repeated figures from this line of work — that files in the
architectural core have several times more defects, cost several times more effort to maintain, and
show markedly higher developer turnover — are exactly the numbers this section most needs, and I
could not confirm a single one of them. Do not quote a multiplier from this paper without reading
it.**

**[?] Also not verified:** any study linking coupling metrics to *measured maintenance cost* (money or
hours) rather than to defects or change counts. The closest verified thing in this report is
Chowdhury et al. 2022 (§3.1), which measures change effort proxies (edit distance, diff size) against
*size*, not coupling.

### 5.5 Architecture fitness functions — an enforcement pattern, not a metric

**Ford, Parsons & Kua, *Building Evolutionary Architectures* (O'Reilly, 2017; 2nd ed. 2022).**
ThoughtWorks Technology Radar entry (read directly):
https://www.thoughtworks.com/radar/techniques/architectural-fitness-function

**[C] Definition, verbatim from the Radar:** *"A fitness function is used to summarize how close a
given design solution is to achieving the set aims."* An architectural fitness function *"provides an
objective integrity assessment of some architectural characteristics."* Fitness functions can
encompass *"existing verification criteria, such as unit testing, metrics, monitors, and so on."*
The stated purpose: *"architects can communicate, validate and preserve architectural characteristics
in an automated, continual manner."*

**Radar placement: introduced November 2017, last updated May 2018, both times in the *Trial* ring**
— *"Worth pursuing. It is important to understand how to build up this capability."*

**[M/?] The book's taxonomy** (atomic vs holistic, triggered vs continuous, static vs dynamic,
automated vs manual, temporal, intentional vs emergent, domain-specific) is well known, but
**the primary text could not be retrieved** (O'Reilly 403). **Cite the taxonomy only from the book
itself.**

**Tools that implement the pattern:** ArchUnit (JVM), NetArchTest (.NET), jQAssistant, dependency-cruiser
(JS/TS), Structure101, import-linter (Python).
**[?] No tool list was verified against a primary source in this research.**

**[F — the honest framing]:** fitness functions are a **practice pattern for turning any chosen metric
into an executable, continuously-evaluated test**. The pattern says nothing about *which* metric to
choose and carries no evidence that architectures governed this way are better. **Its real value for
this brainstorm is structural: it is the mechanism by which a metric portfolio (§6.3) becomes
enforceable, and by which per-codebase thresholds (§6.4) become versioned artifacts rather than
tribal knowledge.** No evaluation of the pattern's effectiveness was located.

---

## 6. Metric gaming and the counter-pressure problem

### 6.1 Goodhart's and Campbell's laws

**Charles Goodhart (1975), "Problems of Monetary Management: The U.K. Experience"**, Papers in
Monetary Economics, Reserve Bank of Australia. The original is a statement about monetary aggregates:
once a statistical regularity is used for control purposes, it breaks down.

**The famous phrasing — "When a measure becomes a target, it ceases to be a good measure" — is
Marilyn Strathern's, not Goodhart's.** Strathern, **"'Improving ratings': audit in the British
University system", *European Review* 5(3):305–321, 1997**
(https://www.cambridge.org/core/journals/european-review/article/improving-ratings-audit-in-the-british-university-system/FC2EE640C0C44E3DB87C29FB666E9AAB).
**[?] The bibliographic record was verified directly (author, year, journal, volume, pages). The exact
sentence does not appear in the publicly visible abstract, and the full text was not retrieved — so
the attribution of that precise wording to that paper is standard in the literature but was not
confirmed here.** Verified from the abstract: *"audit does more than monitor—it has a life of its own
that jeopardizes the life it audits."* — which is the same argument in the author's own words.

**Donald T. Campbell (1979), "Assessing the impact of planned social change", *Evaluation and Program
Planning* 2(1):67–90** — Campbell's Law: the more a quantitative indicator is used for social
decision-making, the more it will distort and corrupt the processes it is meant to monitor.
**[?] Primary not read here.**

**Verified in a software context:** DORA's own guidance
(https://dora.dev/guides/dora-metrics-four-keys/, read directly) explicitly invokes Goodhart, warning
against *"Setting metrics as a goal"* and cautioning that *"making broad statements like, 'Every
application must deploy multiple times per day by year's end,' increases the likelihood that **teams
will try to game the metrics**."* It also warns against cross-team comparison: *"These metrics are
meant to be applied at the application or service level. Comparing metrics between vastly different
applications… can be misleading"*, and against *"Competing"* between teams.

### 6.2 Documented harm from gates — argument, mostly, not study

**[Honest finding: this research located no controlled study showing that a complexity gate produces
worse code.]** What exists is well-argued industry writing and a strong analogy from a neighbouring
metric.

**The best-verified analogue — Martin Fowler, "TestCoverage", 17 April 2012.**
https://martinfowler.com/bliki/TestCoverage.html *(read directly)*
Verbatim: *"**If you make a certain level of coverage a target, people will try to attain it. The
trouble is that high coverage numbers are too easy to reach with low quality testing.**"* And on the
consequence: *"you get lots of tests looking for things that rarely go wrong distracting you from
testing the things that really matter."* His prescription is diagnostic use, not gating: *"it helps
you find which bits of your code aren't being tested… It's worth running coverage tools every so
often and looking at these bits of untested code."*
**This is the cleanest statement of the failure mode, from a credible source, about the closest
analogous metric — but it is argument, not measurement.**

**The mechanism, for complexity specifically, and why it is credible.** Cognitive Complexity charges
**nothing** for a method (§1.2: *"Cognitive Complexity does not increment for methods"*). Therefore
**extracting an arbitrary fragment into a new method always reduces the score of the original method
and adds zero elsewhere.** The gate is trivially satisfiable by extraction regardless of whether the
extraction improves anything. That is not speculation about the metric — it follows directly from the
published specification. **A cognitive-complexity gate, on its own, has a free and always-available
evasion.**

**Corroborating indirect evidence already in this report:**
- **Campbell's own "validation" measures compliance, not comprehension** (§1.3b): a 77% rate of
  developers fixing flagged code. Muñoz Barón et al.'s rebuttal — *"we do not consider this to be a
  sufficient validation"* — is precisely the Goodhart objection.
- **Ousterhout's "entanglement" argument** (§3.7) describes the predicted harm: shallow interfaces and
  readers *"flip[ping] back and forth between the implementations."* **Unmeasured.**
- **Chowdhury et al. 2022's RQ3** (§3.1) is the only *empirical* test located, and it points the other
  way — decomposed groups of small methods were collectively less change- and bug-prone than
  equivalent large methods. **[But note its effect sizes were mostly negligible, and it tested
  decomposition, not gate-driven decomposition.]**
- **Lenarduzzi et al. 2020** (§2.5): classes carrying SonarQube Code Smell issues were **less**
  change-prone than clean ones, and there was **no** fault difference — direct evidence that the
  gate's own rule set does not order code by outcome.
- **Borg, Ezzouhri & Tornhill 2024** (§2.5): SonarQube's *"tendency to generate many false positives."*

**[?] Bouwers, Visser & van Deursen, "Getting What You Measure", *CACM* 55(7):54–59 / *ACM Queue*
10(5), 2012** (https://dl.acm.org/doi/10.1145/2209249.2209266) — **could not verify.** ACM Queue and
ACM DL both returned 403. This paper is directly on the topic of software-metric pitfalls and is the
single most relevant missing citation in this section. **Its four pitfalls are commonly summarised as
"metric in a bubble", "treating the metric", "one-track metric", and "metrics galore", but this
research could not confirm those names or their content against the primary text.** Get it through
institutional access.

**[?] Also not verified:** any documented industrial case study of a complexity gate causing
measurable harm (shotgun surgery, indirection tax, wrapper methods written to dodge a threshold).
Searches for this class of evidence returned opinion pieces only. **If someone claims such a study
exists, ask for the citation — I did not find one.**

### 6.3 Opposing metric pairs and metric portfolios

**The verified example is DORA.** Forsgren, Humble & Kim, *Accelerate* (IT Revolution, 2018), and the
current DORA guidance (https://dora.dev/guides/dora-metrics-four-keys/, read directly).

**[M] The structure is explicitly a paired portfolio.** DORA now publishes **five** metrics in two
groups:
- **Throughput** — change lead time, deployment frequency, failed deployment recovery time
  (*"a measure of how many changes can move through the system over a period of time"*)
- **Instability** — change fail rate, deployment rework rate (*"a measure of how well the software
  deployments go"*)

**[C] But note carefully what DORA claims, verbatim:** *"DORA's research has repeatedly demonstrated
that **speed and stability are not tradeoffs**… the metrics are correlated for most teams. Top
performers do well across all five metrics, and low performers do poorly."*

**This is important and often misread.** DORA is **not** an example of "opposing metrics that
constrain each other." DORA's empirical claim is the opposite — that the two groups move *together*.
The portfolio exists so that **gaming one group is visible in the other**, not because the two are in
genuine tension. **If the brainstorm wants an argument for opposing-metric pairs, DORA supports the
"pair a productivity metric with a quality metric so the cheat is visible" design — it does not
support "these metrics trade off against each other."**

**[?] No research was located** that evaluates opposing-metric portfolios for *code* metrics
specifically — e.g. pairing a complexity cap against an indirection/fan-out cap so that
gate-satisfying extraction is penalised. **This appears to be an open design space rather than a
studied one.** The mechanism sketched in §6.2 (extraction is free under Cognitive Complexity) is a
concrete reason such a pairing would be well-motivated, and §5.2's fan-out result (τ = 0.33, above
McCabe) suggests fan-out is the better-evidenced counterweight — **but this is my synthesis, not a
published finding.**

### 6.4 Per-codebase calibration — the most actionable idea in the report

**Alves, Ypma & Visser, "Deriving Metric Thresholds from Benchmark Data", ICSM 2010**, pp. 1–10.
DOI https://doi.org/10.1109/ICSM.2010.5609747

**[?] IMPORTANT SOURCING CAVEAT: the primary paper could not be retrieved** (the SIG-hosted PDF is
behind a form; TU Delft and other mirrors returned HTML; ACM/IEEE 403). **The method below is quoted
from Chowdhury, Uddin & Holmes (MSR 2022, §3.1), who reproduce the six steps explicitly "for
reproducibility" and apply them end-to-end. That is a strong, peer-reviewed secondary — but the
original's own derived thresholds and benchmark corpus size were NOT verified here.**

**[M] The method, as reproduced by Chowdhury et al.** (illustrated on their two-project toy example):

1. **Compute the metric per entity.** For each method *M* in project *P*, take its SLOC (or McCabe,
   or any metric).
2. **Weight each entity by its share of its project's total volume.** `weight(M) = sloc(M) / Σ sloc(Mₖ)`.
   *This is the key move: an entity contributes in proportion to how much code it represents, so a
   project is not dominated by its many tiny methods.*
3. **Aggregate identical metric values.** Group all entities with the same value; the group's weight
   is the sum of member weights.
4. **Normalise per project.** Divide each aggregated weight by the number of projects φ, so every
   project contributes equally regardless of size.
5. **Repeat across all φ projects**, producing per-project lists of values and normalised weights.
6. **Build the cumulative distribution** over the pooled, weighted values and **read the thresholds off
   as percentiles of weighted code volume.**

**[M] Which percentiles become which band edge — verified verbatim in Chowdhury et al.:**
> *"the first critical value in Figure 3 is 24 (from the x-axis), because it **covers 70% of the
> y-axis**. The second and the third values are 36 and 63, because they **cover 80% and 90%** of the
> y-axis respectively."*

So: **70th percentile ⇒ "small" upper bound; 80th ⇒ "medium"; 90th ⇒ "large"; above that "very
large."** Applied to 49 modern Java projects this yields **24 / 36 / 63 SLOC** (§3.1, Table).

**Why this method is worth the attention:** it is *"resilient to outlier projects"* and — in
Chowdhury et al.'s words — *"does not depend on intuition or expert opinion."* It converts "what
threshold?" from an argument into a measurement. And critically, **Chowdhury et al. then went on to
*validate* the derived band against outcomes** (Wilcoxon + Cliff's Delta against change- and
bug-proneness) rather than treating the percentile as self-justifying. **That two-step —
derive from the distribution, then validate against an outcome — is the defensible pattern.** A
percentile alone tells you only what is *typical*, never what is *good*.

**[?] The published Alves/SIG numbers for cyclomatic complexity and unit size** (the SIG
maintainability model's familiar low/moderate/high/very-high risk bands, and the star-rating
calibration in Alves, Correia & Visser, "Benchmark-based Aggregation of Metrics to Ratings", IWSM/
Mensura 2011) **were not verified in this research.** Note also that Chowdhury et al. explicitly
attack one SIG-lineage number: *"Visser et al. recommended that developers should keep their method
within 15 source lines of code, **this recommendation was from intuition only, not based on
evidence**"* (§3.1). **So SIG's published thresholds are a mix of benchmark-derived and asserted
values — check the provenance of any specific one before adopting it.**

### 6.5 Deriving thresholds from a *single* codebase's own distribution

This is what the brainstorm most likely wants, and it is the weakest-evidenced part of the section.

**[?] No study was located that derives metric thresholds from one codebase's own distribution and
validates them.** The Alves method is explicitly a **benchmark** method: steps 4 and 5 exist to
normalise *across* projects so that no single project dominates. **Applying steps 1–3 and 6 to a
single repository is a coherent adaptation, but it is an adaptation — it inherits none of the
method's validation.**

**Three honest cautions for a single-repo application, derived from what *is* verified:**

1. **A percentile is a description of the status quo, not a quality bar.** Setting the gate at your
   own 70th percentile institutionalises whatever the codebase already does. Chowdhury et al.'s
   second step — validating the band against an outcome (change-proneness) — is what makes the
   percentile meaningful, and a single repo usually lacks the statistical power to do it.
2. **Effect sizes are concentrated at one boundary.** In the one validated case (§3.1), all the
   signal was in the small→medium step; medium→large and large→very-large were negligible. **A
   four-band scheme derived from percentiles will therefore over-state the importance of its upper
   boundaries.** Prefer one soft threshold to a graded ladder.
3. **Sample size.** Chowdhury et al. used **49 projects / ~785,000 methods** to derive three numbers,
   and even then reported per-project correlations ranging from τ = 0.05 to 0.56 — *"SLOC performance
   is not similar across projects."* **[?] No source was found stating a minimum sample size for
   meaningful single-codebase threshold derivation.** Given that per-project variation in the
   benchmark study spans an order of magnitude in correlation strength, **a threshold derived from a
   single small repository should be treated as a convention the team has chosen to adopt, not as a
   measurement — and it should be labelled as such.**

**[?] Follow-up work not verified:** Alves, Correia & Visser (2011) on benchmark-based rating
aggregation; Vasilescu et al. on metric aggregation techniques; Foucault et al.'s critiques of
threshold derivation. **These were named in the research brief but no primary text was reached.**

---

## Appendix: claims I could NOT verify

Listed so that nothing here is mistaken for a confirmed finding. Each of these needs institutional
access or a better mirror before it is quoted.

**Section 1–2**
- Lavazza et al. (JSS 2023) individual correlation coefficients and model-performance numbers. Only
  the published abstract's conclusions were verified.
- Any 2026 publication revisiting Cognitive Complexity's validity at scale. Two adjacent 2025 items
  were surfaced but not read: "Rethinking Cognitive Complexity for Unit Tests" (orbilu.uni.lu/handle/10993/66307)
  and "Complementarity in software code complexity metrics" (*JSS* 2025).
- GitClear's AI-code churn/duplication figures and the derived "1.7× more issues" claim — vendor
  analytics, no primary methodology located.

**Section 3**
- Johnson et al. (ICSME 2019) participant subgroup counts do not sum to the reported total.
- El Emam et al. (TSE 2001): two conflicting secondary summaries of how many CK metrics survive size
  control; paywalled, unresolved.
- Basili & Perricone's error-density table was read from a secondary (Derek Jones), not the CACM original.
- Rosenberg (METRICS '97), El Emam et al. (TSE 2002 "Optimal Class Size"), Koru et al. (EMSE 2008):
  conclusions taken from abstracts/secondaries, not full texts.
- McConnell's "few people can understand more than three levels of nested ifs" — no source identified.
- arXiv 2507.19721 "Clean Code In Practice" — abs page returned unrelated metadata. **Do not cite.**
- No controlled experiment found showing that extracting many tiny methods harms comprehension.

**Section 4**
- **Rigby & Bird (ESEC/FSE 2013) primary text.** All its numbers here are quoted via Sadowski et al. 2018.
- **The SmartBear/Cisco study's scale** (~2,500 reviews / 50 developers / 3.2M LOC). Widely repeated;
  no primary document confirms it. The conclusions are published by the tool vendor without method or data.
- **Fagan (1976)** inspection rates, defect-removal-efficiency figures, and the replication record.
- **McIntosh et al.** (MSR 2014 / EMSE 2016) on review coverage and participation vs post-release defects.
- **Kononenko et al.** (2016) on code review quality.
- Any peer-reviewed study relating changeset size directly to **defect escape rate**.
- Any primary DORA analysis quantifying **batch size** against outcomes.

**Section 5**
- **Henry & Kafura (1981)** primary; the `length × (fan-in × fan-out)²` formula is stated from general
  knowledge. **Check before quoting.**
- **Shepperd's critiques** of Henry–Kafura and of design metrics — real, but no primary text read.
- **Any empirical validation of Martin's I / A / D at all.** None found. This is an absence of
  evidence, not evidence of absence.
- **MacCormack & Sturtevant (JSS 2016)** — every core-vs-peripheral multiplier for defects, effort and
  turnover. **This is the single biggest gap in Section 5.** Also Sturtevant's MIT thesis (2013).
- Any study linking coupling metrics to **measured maintenance cost** in money or hours.
- *Building Evolutionary Architectures*' fitness-function taxonomy (primary text 403).
- The list of fitness-function tools.

**Section 6**
- **Bouwers, Visser & van Deursen, "Getting What You Measure" (CACM/Queue 2012)** — the four pitfalls
  and their names. **The most relevant missing citation in Section 6.**
- Strathern 1997: bibliographic record verified; the exact "when a measure becomes a target" sentence
  was not located in the accessible text.
- Campbell (1979) primary text.
- **Any documented industrial case study of a complexity gate causing measurable harm.** Only opinion
  pieces were found.
- **Alves, Ypma & Visser (ICSM 2010) primary text** — the six-step method is quoted via Chowdhury et
  al. (MSR 2022), who reproduce it explicitly; the original's own derived thresholds and benchmark
  corpus size are unverified.
- SIG's published cyclomatic-complexity and unit-size risk bands, and the star-rating calibration
  (Alves, Correia & Visser 2011).
- Vasilescu et al. on aggregation; Foucault et al. on threshold-derivation critiques.
- **Any minimum sample size for meaningful single-codebase threshold derivation.**

