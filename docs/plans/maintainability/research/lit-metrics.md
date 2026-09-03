# Measurably maintainable code — literature findings

Research date: 2026-09-01. Web/literature only.

**Reading key.** Each claim is tagged:
- **(a) measured** — what the study actually computed, on what data.
- **(b) concluded** — what its own authors said it means.
- **(c) folklore** — what industry repeats, where that differs from (a)/(b).

Where a source could not be opened or a number could not be confirmed, it says **could not verify** rather than an estimate.

---

## 1. Cyclomatic complexity's empirical track record

### 1.1 Where the threshold of 10 comes from

**Primary source: McCabe, T.J. (1976). "A Complexity Measure." IEEE Transactions on Software Engineering SE-2(4):308–320.** PDF: <http://www.literateprogramming.com/mccabe.pdf>

**(a) measured.** The paper is a graph-theoretic construction (v(G) = e − n + 2p), not an empirical study. The only data reported in support of a threshold are anecdotes from McCabe's own consulting work.

**(b) concluded — verbatim, the actual origin of "10":**

> "These results have been used in an operational environment by advising project members to limit their software modules by cyclomatic complexity instead of physical size. **The particular upper bound that has been used for cyclomatic complexity is 10 which seems like a reasonable, but not magical, upper limit.** Programmers have been required to calculate complexity as they create software modules. When the complexity exceeded 10 they had to either recognize and modularize subfunctions or redo the software. […] The only situation in which this limit has seemed unreasonable is when a large number of independent cases followed a selection function (a large case statement), which was allowed."

The nearest thing to evidence in the paper is a single anecdote:

> "On one occasion the author was given a DEC tape of 24 Fortran subroutines that were part of a large real-time graphics system. It was rather disquieting to find, in a system where reliability is critical, subroutines of the following complexity: 16, 17, 24, 24, 32, 34, 41, 54, 56, and 64. After confronting the project members with these results the author was told that the subroutines on the DEC tape were chosen because they were troublesome and indeed **a close correlation was found between the ranking of subroutines by complexity and a ranking by reliability (performed by the project members)**."

That is n=24, single system, outcome ranked subjectively by the same people who were shown the complexity numbers. **No statistical test, no control, no independent outcome measure.**

**(c) folklore.** "10 is the empirically validated limit." It is not. It is a departmental policy McCabe describes as "reasonable, but not magical", supported by one uncontrolled anecdote.

---

**Secondary source usually cited as the justification: Watson, A.H. & McCabe, T.J. (1996). "Structured Testing: A Testing Methodology Using the Cyclomatic Complexity Metric." NIST Special Publication 500-235** (Dolores R. Wallace, ed.). PDF: <https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication500-235.pdf>

**(a)/(b), §2.5 "Limiting cyclomatic complexity to 10", verbatim:**

> "The precise number to use as a limit, however, remains somewhat controversial. **The original limit of 10 as proposed by McCabe has significant supporting evidence, but limits as high as 15 have been used successfully as well.** Limits over 10 should be reserved for projects that have several operational advantages over typical projects, for example experienced staff, formal design, a modern programming language, structured programming, code walkthroughs, and a comprehensive test plan. In other words, an organization can pick a complexity limit greater than 10, but only if it is sure it knows what it is doing and is willing to devote the additional testing effort required by more complex modules."

**Important**: the phrase "has significant supporting evidence" in SP 500-235 §2.5 **carries no citation**. I read the section; no reference is attached to that claim. **This is the single most load-bearing sentence in the folklore and it is unsourced in its own document.**

SP 500-235's recommended *policy* is notably softer than how it is quoted:

> "For each module, either limit cyclomatic complexity to 10 (as discussed earlier, an organization can substitute a similar number), **or provide a written explanation of why the limit was exceeded.**"

That is an **escape-hatch-with-justification** rule, not a hard cap — directly relevant to a "budget/ratchet" design.

§2.5 also contains a documented **gaming failure mode** from the field:

> "One developer started reporting a 'modified' complexity in which cyclomatic complexity was divided by the number of multiway decision branches. […] The actual result was that the developer could take a module with **complexity 90 and reduce it to 'modified' complexity 10 simply by adding a ten-branch multiway decision statement to it that did nothing.**"

Also worth noting, SP 500-235 §3.1 "Independence of complexity and size" argues the *opposite* of the redundancy critique — that CC and LOC are independent — using two hand-picked figures (complexity 1 with 282 LOC; complexity 28 with 30 LOC). **(c) folklore note**: both camps cite constructed examples; neither §3.1 nor the redundancy camp's early studies is a large-corpus measurement.

### 1.2 Shepperd 1988 — the critique

**Shepperd, M. (1988). "A critique of cyclomatic complexity as a software metric." Software Engineering Journal 3(2):30–36.** DOI 10.1049/sej.1988.0003 · <https://digital-library.theiet.org/doi/10.1049/sej.1988.0003> · full text: <https://www.cs.du.edu/~snarayan/sada/teaching/COMP3705/lecture/p1/cycl-1.pdf>

**(a) measured.** This is **a critical literature review, not a new experiment.** Shepperd reviews the then-existing empirical validations of v(G) (roughly 30 studies referenced) and audits their statistical method.

**(b) concluded — verbatim from the abstract:**

> "This critique demonstrates that it is based upon poor theoretical foundations and an inadequate model of software development. The argument that the metric provides the developer with a useful engineering approximation is not borne out by the empirical evidence. Furthermore, it would appear that for a large class of software **it is no more than a proxy for, and in many cases is outperformed by, lines of code.**"

The concrete counts he gives:

- "A considerable number of studies (Refs. 41, 47, 48, 53 and 55) indicate that **LOC actually outperforms cyclomatic complexity.**"
- "**Most damning is the out-performing of v(G) by a straightforward LOC metric in over a third of the studies considered.**"
- Methodological objections: "the use of correlation coefficients on skewed data causes artificially high correlations"; "the assumption of causality would seem doubtful given the consistently high association between cyclomatic complexity and LOC"; "the high variation in programmer ability reduces the statistical significance of correlation coefficients."
- On the underlying studies' scale: "frequently programs of less than 300 LOC (Refs. 43, 44, 53 and 54) are used. These programs are, by software engineering standards, trivial."
- The deepest objection: "**without an explicit underlying model the empirical 'validation' is meaningless and there is no hypothesis to be refuted.**"
- He also notes Basili & Perricone (1984) found **error density *diminishes* with increasing cyclomatic complexity** — i.e. the sign went the wrong way once normalised for size.

Shepperd's own recommendation is that **LOC should be treated as the baseline any complexity metric must beat** — which is exactly the design question here.

### 1.3 Jay/Graylin et al. 2009 — the "stable linear relationship" claim

**Jay, G., Hale, J.E., Smith, R.K., Hale, D.P., Kraft, N.A. & Ward, C. (2009). "Cyclomatic Complexity and Lines of Code: Empirical Evidence of a Stable Linear Relationship." Journal of Software Engineering and Applications 2(3):137–143.**
DOI 10.4236/jsea.2009.23020 · <https://www.scirp.org/journal/paperinformation?paperid=779> · <https://www.researchgate.net/publication/220204439>

**(b) concluded.** Their position is that the LOC–CC linear relationship is *stable across languages and paradigms*, and that "the aspects of code complexity that CC measures, such as the size of the test case space, grow linearly with source code size."

**(a) measured — ★ and this is the crux of the whole debate.** I could not open SCIRP directly (HTTP 403), but **Landman et al. 2016 tabulate this exact study as their reference [46]**, and the design is decisive:

| | Jay et al. 2009 (Landman's Table I, ref [46]) |
|---|---|
| Aggregation level | **File** — *not* method/function |
| Variables | **log(LOC) vs log(CC)** — *log-transformed on both axes* |
| Languages | Java, C, C++ |
| Corpus | **2,200 projects from SourceForge** |
| R² reported | **0.78 / 0.83 / 0.73** (one per language) |
| R² after **repeated median regression** | **0.87, 0.93, 0.97** |

**So the famous "~0.9" number is the post-hoc repeated-median-regression R² of a log–log fit at file level.** Landman et al. then demonstrate, on a 24-million-unit corpus, that **each** of those three choices independently inflates the correlation:
- **file-level aggregation** raises Java R² from 0.40 → 0.64 (and Σ-of-bodies → 0.73);
- **the log transform** raises Java R² from 0.40 → 0.68;
- both together → **0.90**, which is exactly Jay et al.'s figure.

**(c) folklore.** "CC correlates ~0.9 with SLOC, so CC is redundant." The 0.9 is real but it is measured on **aggregated, log-transformed, file-level** data. At the level anyone actually *gates* on — a single function or method — the same relationship is **R² ≈ 0.40–0.44**. The folklore claim silently swaps the unit of analysis.

Two further rows from Landman's Table I worth having, because they cut the other way:
- **2011, ref [22]**: class-level SLOC vs **max CC** and **mean CC**, Java, Arc dataset (234 classes) — **R² = 0.12 and 0.08**, and "correlations were not statistically significant."
- **2014, ref [8]** (Jbara, Matan & Feitelson, *EMSE* 19(5):1261–1298, "High-MCC Functions in the Linux Kernel"): function-level LOC vs CC in the Linux kernel gives R² ≈ 0.77 — but "hereafter they limit to methods with a CC higher than 100, [and] for these 138 functions they find a **much lower correlation** to SLOC."

Across the whole tabulated literature, reported **R² spans 0.51 to 0.96** with no time trend. "0.9" is a selection from a wide, heterogeneous, methodologically inconsistent spread — not a constant of nature.

### 1.4 Landman, Serebrenik, Bouwers & Vinju — the largest-corpus test (this is the strongest evidence in this section)

Two papers, same team:
- **Landman, D., Serebrenik, A. & Vinju, J.J. (2014). "Empirical Analysis of the Relationship between CC and SLOC in a Large Corpus of Java Methods." ICSME 2014, pp. 221–230.** DOI 10.1109/ICSME.2014.44
- **Landman, D., Serebrenik, A., Bouwers, E. & Vinju, J.J. (2016). "Empirical analysis of the relationship between CC and SLOC in a large corpus of Java methods and C functions." Journal of Software: Evolution and Process 28(7):589–618.** DOI 10.1002/smr.1760 · <https://onlinelibrary.wiley.com/doi/abs/10.1002/smr.1760> · preprint: <https://www.win.tue.nl/~aserebre/Landman2015-ccsloc-jsep2015-preprint.pdf> · data/scripts: <http://homepages.cwi.nl/~landman/jsep2015/>

**(a) measured.** Corpus: **17,633,256 Java methods** (from Sourcerer) and **6,259,031 C functions** (from Gentoo Linux packages). CC counted including `&&`/`||` short-circuit operators (and re-run without them as a sensitivity check). Pearson R², log-transformed R², and Spearman ρ, at method/function level and aggregated to file level. All correlations p ≤ 1×10⁻¹⁶.

**Headline numbers (their Tables IV–VI):**

| Aggregation | Java R² | Java log R² | C R² | C log R² |
|---|---|---|---|---|
| **None (per method/function)** | **0.40** | 0.68 | **0.44** | 0.71 |
| Per file (raw SLOC incl. headers) | 0.64 | 0.87 | 0.39 | 0.84 |
| Σ of method/function bodies per file | 0.73 | 0.90 | 0.70 | 0.90 |

Spearman ρ at unit level: **0.80 (Java), 0.83 (C)** — but ρ *collapses* as you move up the size range (Java ρ drops to 0.50 at min-SLOC 20, 0.33 at min-SLOC 77, 0.17 for the top 0.01%).

Fitted models at unit level:
- Java linear: `CC = 0.92 + 0.15·SLOC`; log fit `CC = 10^−0.28 · SLOC^0.65`
- C linear: `CC = 1.70 + 0.16·SLOC`; log fit `CC = 10^−0.41 · SLOC^0.79`

Other measured effects:
- Ignoring `&&`/`||` changed the CC of 1.3M/17.6M Java methods (74.2K by >50%) but moved Java R² only **0.40 → 0.41**; C stayed at 0.44.
- Heteroscedasticity **confirmed by Breusch–Pagan test**: CC variance grows with SLOC.
- Trimming the largest 5% of files raised file-level R² from 0.64 → **0.83** (Java) and 0.39 → **0.64** (C). But of ten randomly sampled large files, **5/10 (Java) and 9/10 (C) were generated code** — so trimming is partly removing artefacts, and they explicitly warn against treating large units as outliers wholesale.

**(b) concluded — verbatim from their conclusion:**

> "In summary, as opposed to the majority of the previous studies **we did not observe a strong linear correlation between CC and SLOC of Java methods and C functions. Therefore, we do not conclude that CC is redundant with SLOC.**"

> "**CC summed over larger code units measures an aspect of system size rather than internal complexity of subroutines. This largely explains the often reported strong correlation between CC and SLOC in literature.**"

Their practical framing, which is the most useful sentence for a gating design:

> "For the larger subroutines, and even the medium sized subroutines, correlation decreases rapidly. This means that **for all but the smallest subroutines CC is not redundant.** For example […] given a Java method of 100 SLOC, CC has a range between 1 and 40 […] For such larger Java methods, CC can be a useful metric to further discriminate between relatively simple and more complex larger methods."

**Also worth having**: their Table I is a full tabulation of ~30 prior CC/SLOC correlation studies with year, aggregation level, language, corpus and R². **Reported R² ranges 0.51–0.96**, with no time trend, and mostly on tiny corpora (26 Fortran subroutines; 3K COBOL programs; etc.).

### 1.5 Where this leaves the redundancy critique

- **Contested, not settled.** The "CC ≈ SLOC, therefore useless" claim rests on small-corpus studies from 1979–2009 whose R² spread is 0.51–0.96. The largest test ever run (24M units) gets **R² = 0.40/0.44 at the unit level** and explicitly rejects redundancy.
- **The redundancy claim is true at the level people usually aggregate to.** Summed/file-level CC does behave like a size measure (R² up to 0.73–0.90 log). So a *project-total* or *per-file* complexity metric is close to a size metric; a *per-unit distribution* is not.
- **This is the key design implication**: CC's non-redundant signal lives in the *tail* — the large units where CC ranges 1–40 for a fixed size. Aggregating averages it away; a max-threshold sees only the tail; a **distribution/risk profile** is the shape that preserves it.

### 1.6 Recent revisit

**"Reflections on McCabe's Cyclomatic Complexity", IEEE Transactions on Software Engineering / IEEE Software, 2025.** <https://ieeexplore.ieee.org/document/10855804/> · <https://www.computer.org/csdl/journal/ts/2025/03/10855804/23QQWd6urhC>
A retrospective on the 1976 paper including an interview with McCabe. **Could not verify** the author list or its detailed conclusions — the article is paywalled and I could not retrieve the full text. Flagged as a lead, not evidence.

---

## 2. Standardised maintainability models

### 2.1 ISO/IEC 25010

**ISO/IEC 25010:2023, Systems and software Quality Requirements and Evaluation (SQuaRE) — Product quality model** (2nd edition, replacing 25010:2011).

**Maintainability sub-characteristics (5):** modularity, reusability, analysability, modifiability, testability.

- **Modularity** — degree to which a system is composed of discrete components such that a change to one has minimal impact on others.
- **Reusability** — degree to which an asset can be used in more than one system.
- **Analysability** — effectiveness/efficiency of assessing the impact of an intended change, diagnosing deficiencies or causes of failure, and identifying parts to be modified.
- **Modifiability** — degree to which a product can be modified without introducing defects or degrading existing quality.
- **Testability** — effectiveness/efficiency of establishing test criteria and running tests to check compliance.

Overviews: <https://quality.arc42.org/standards/iso-25010> · <https://www.sonarsource.com/resources/library/iso-iec-25010-explained/> · <https://www.perforce.com/blog/qac/what-is-iso-25010>

**Critical caveat**: 25010 is a **vocabulary and decomposition**, not a measurement method. It defines *what* maintainability is; it prescribes no thresholds.

### 2.2 ISO/IEC 25023 — the measures

**ISO/IEC 25023:2016, Measurement of system and software product quality.** Supplies quality measure elements (QMEs) per sub-characteristic. Relevant maintainability measures, as reported in secondary sources:

- **Modularity**: "coupling of components" — ratio of completely independent components to the number of components that must be independent.
- **Modularity**: **"cyclomatic complexity adequacy"** — *the proportion of all software modules that have an acceptable cyclomatic complexity*. **Note the shape of this measure: it is a proportion-below-a-threshold, i.e. a one-bucket risk profile — not a max or a mean.**
- **Reusability**: proportion of assets designed to be reusable; coding-rules conformity (proportion of modules conforming to given coding rules).

**Could not verify**: I did not obtain the ISO/IEC 25023 text itself (paywalled). The above is from secondary summaries — see <https://arxiv.org/pdf/2108.02921> (Applicability of ISO/IEC 25023 measures) and <https://arxiv.org/pdf/2003.02619>. **25023 notably does not define what "acceptable" cyclomatic complexity is** — it delegates the threshold. That delegation is where every model below actually differs.

### 2.3 The SIG maintainability model — original (2007)

**Heitlager, I., Kuipers, T. & Visser, J. (2007). "A Practical Model for Measuring Maintainability." QUATIC 2007 (6th Int. Conf. on the Quality of Information and Communications Technology), pp. 30–39.** DOI 10.1109/QUATIC.2007.7 · <https://dl.acm.org/doi/10.1109/QUATIC.2007.7> · PDF: <https://webarchive.di.uminho.pt/wiki.di.uminho.pt/twiki/pub/Personal/Joost/PublicationList/HeitlagerKuipersVisser-Quatic2007.pdf>
(Won the QUATIC Most Influential Paper Award.)

**(a) what it is.** Six-ish source-code properties mapped onto ISO 9126 maintainability sub-characteristics (analysability, changeability, stability, testability), each ranked on a **++ / + / o / − / −−** scale.

**Property → sub-characteristic matrix (Fig. 3):**

| | volume | complexity/unit | duplication | unit size | unit testing |
|---|---|---|---|---|---|
| analysability | × | | × | × | × |
| changeability | | × | × | | |
| stability | | | | | × |
| testability | | × | | × | × |

System-level score per sub-characteristic = **equal-weighted average** of the marked properties (weights configurable). Overall maintainability = average of those. The authors explicitly deprecate the single number:

> "We do not attribute much added value to such a single score. Rather, the scores for the various sub-characteristics convey more information, and can be traced back in a straightforward manner to the underlying code-level scores. **In contrast to a single number, such as the Maintainability Index, this allows root-cause analysis.**"

**Volume ranking (2007) — verbatim table:**

| rank | Man-years | Java KLOC | COBOL KLOC | PL/SQL KLOC |
|---|---|---|---|---|
| ++ | 0–8 | 0–66 | 0–131 | 0–46 |
| + | 8–30 | 66–246 | 131–491 | 46–173 |
| o | 30–80 | 246–665 | 491–1,310 | 173–461 |
| − | 80–160 | 655–1,310 | 1,310–2,621 | 461–922 |
| −− | >160 | >1,310 | >2,621 | >922 |

(Converted via the Software Productivity Research LLC Programming Languages Table: LOC-per-function-point and FP-per-month per language.)

**Unit complexity — the risk bands (2007), taken from the SEI:**

| CC | Risk evaluation |
|---|---|
| 1–10 | simple, without much risk |
| 11–20 | more complex, moderate risk |
| 21–50 | complex, high risk |
| >50 | untestable, very high risk |

**★ THE KEY ARTIFACT — the risk-profile rating scheme (2007), verbatim:**
Aggregation is *not* a mean or a max. For each risk level, compute **what percentage of lines of code sits in units at that level**. Then:

| rank | max % LOC at moderate risk | at high risk | at very high risk |
|---|---|---|---|
| ++ | 25% | 0% | 0% |
| + | 30% | 5% | 0% |
| o | 40% | 10% | 0% |
| − | 50% | 15% | 5% |
| −− | (anything worse) | — | — |

> "Thus, to be rated as ++, a system can have no more than 25% of code with moderate risk, no code at all with high or very high risk. […] A system that has more than 50% code with moderate risk or more than 15% with high or more than 5% with very high risk is rated as −−."

**(b) how the numbers were justified — verbatim, and this matters:**

> "**The boundaries we defined are based on experience.** During the course of evaluating numerous systems, these boundaries turned out to partition systems into categories that corresponded to expert opinions."

So the 2007 thresholds are **expert-calibrated, not derived**. (§2.5 below is how SIG later fixed exactly this.)

**Duplication rating (2007) — verbatim:**

| rank | duplication |
|---|---|
| ++ | 0–3% |
| + | 3–5% |
| o | 5–10% |
| − | 10–20% |
| −− | 20–100% |

Definition: "the percentage of all code that occurs more than once in equal code blocks of at least 6 lines", ignoring leading whitespace, exact string match otherwise. Their comment: "a well-designed system should not have more than 5% code duplication […] When duplication exceeds 20%, source code erosion is out of control."

**Unit size (2007):** "The risk categories and scoring guidelines are similar to those for complexity per unit, except that the particular threshold values are different." The 2007 paper **does not print the unit-size thresholds** — see §2.4 for the current published ones.

Rationale for keeping unit size *as well as* CC, despite the correlation — verbatim, and this is a direct answer to the redundancy critique:

> "As remarked earlier, a strong statistical correlation exists between size (e.g. in terms of LOC) and cyclomatic complexity. The added value of computing unit size in addition to complexity per unit may therefore seem dubious; many of the complex units will also be large. Still, **using unit size as a measure complementary to complexity allows detection of large units with low complexity.** In our experience, many systems contain a significant number of such units."

**Unit test coverage rating (2007):**

| rank | coverage |
|---|---|
| ++ | 95–100% |
| + | 80–95% |
| o | 60–80% |
| − | 20–60% |
| −− | 0–20% |

With an explicit Goodhart warning attached:

> "A high level of unit test coverage is easy to obtain by writing unit tests of bad quality. A test that, directly or indirectly, invokes many methods is a 'unit' test only in name, but contributes to a high coverage value. Also, a test that invokes methods, but does not check behaviour (i.e. contains no assert statements), contributes to the coverage measure without actually testing anything. Thus, **the awareness of developers that coverage is being measured may lead to increased coverage without increased 'real' testing.**"

Their mitigation: **count assert statements** as a cross-check on coverage. "We currently have no fixed rating scheme in place, but merely use this measure to validate the coverage measure."

### 2.4 ★ SIG/TÜV NORD CERT Evaluation Criteria — the CURRENT published thresholds (v17.0, March 2025)

**This is the single most valuable artifact for a threshold design.** These are the numbers required for **4-star certification**, published as guidance to producers.

**Source: Vis, R. (2025). "SIG/TÜV NORD CERT Evaluation Criteria Trusted Product Maintainability: Guidance for Producers", Version 17.0, 12 March 2025, Software Improvement Group.**
<https://www.softwareimprovementgroup.com/wp-content/uploads/SIG-TUViT-Evaluation-Criteria-Trusted-Product-Maintainability-Guidance-for-producers.pdf>
(2018 edition, for comparison: <https://www.sig.eu/wp-content/uploads/2018/05/20180509-SIG-TUViT-Evaluation-Criteria-Trusted-Product-Maintainability.pdf>)

Definitions used: a **unit** is "the smallest named piece of executable code" (method/function/procedure). A **module** is "a delimited group of declarations… generally it corresponds to a file". A **component** is a top-level subdivision of the system.

**Eight measured properties, with the exact 4-star thresholds:**

**1. Volume** — "the total rebuild value of the product should not exceed **3.9 person-years**", normalised across languages:

| Language | LOC in 3.9 person-years |
|---|---|
| C++ | 32,000 |
| C# | 39,000 |
| Java | 35,100 |
| JavaScript | 36,300 |
| Python | **25,000** |
| Ruby | 24,600 |
| TypeScript | 31,600 |

**2. Duplication** — "the percentage of redundant lines of code for each programming language used should not exceed **5.6%**". A fragment counts as duplicated if it is **≥ 6 lines** and repeated literally (modulo whitespace) at least once elsewhere.

**3. Unit size** — % of LOC residing in units above each size:

| Units larger than | Max % of total LOC |
|---|---|
| > 15 LOC | **47.1%** |
| > 30 LOC | **23.1%** |
| > 60 LOC | **8.3%** |

**4. Unit complexity** — % of LOC residing in units above each McCabe CC:

| Units with McCabe CC above | Max % of total LOC |
|---|---|
| > 5 | **20.2%** |
| > 10 | **7.3%** |
| > 25 | **1.1%** |

**Note the drift from 2007**: the risk-band boundaries moved from **10/20/50** (2007, from the SEI) to **5/10/25** (2025). SIG's *bands got stricter* as the benchmark was recalibrated against real systems. Also note the *shape*: three nested "no more than X% of code above complexity Y" constraints — a **cumulative risk profile**, not a cap.

**5. Unit interfacing** (parameter count) — % of LOC in units with:

| Parameters | Max % of total LOC |
|---|---|
| ≥ 3 | **15.0%** |
| ≥ 5 | **3.3%** |
| ≥ 7 | **0.9%** |

**6. Module coupling** (incoming dependencies per module):

| Incoming dependencies above | Max % of total LOC |
|---|---|
| > 10 | **10.0%** |
| > 20 | **5.6%** |
| > 50 | **1.9%** |

Verbatim: "The percentage of lines of code residing in modules with a number of incoming dependencies above 10 should not exceed 10.0%." Coupling is counted as **incoming dependencies (e.g. invocations) per module**. Note the guidance pairs this with a size rule: "for modules that do require high(er) coupling, the software producer should keep them as small as possible" — because the metric is LOC-weighted, a highly-coupled *small* module costs little.

**7. Component entanglement** — combination of *communication density* (communication lines between components ÷ connected components) and *communication violations* (direct cyclic, indirect cyclic, and transitive dependencies, weighted by the total weight of all communication lines). 4-star threshold: the computed value "should not exceed **0.077**".

**8. Component independence** — "the percentage of code residing in modules **without** incoming cross-component dependencies should not drop below **93.7%**". (A module is *hidden* if no other component depends on it, *exposed* otherwise. Outgoing dependencies do not count.)

**Observation for design.** Six of the eight properties are expressed as **"no more than X% of code in the bad band"**, at **three nested severity levels**. Only volume, entanglement and independence are single scalars. This is the mature form of the risk-profile idea.

### 2.5 How SIG derived those thresholds — the calibration method

**Alves, T.L., Ypma, C. & Visser, J. (2010). "Deriving Metric Thresholds from Benchmark Data." ICSM 2010, pp. 1–10.** DOI 10.1109/ICSM.2010.5609747 · <https://dl.acm.org/doi/10.1109/ICSM.2010.5609747> · PDF: <https://webarchive.di.uminho.pt/wiki.di.uminho.pt/twiki/pub/Personal/Joost/PublicationList/AlvesYpmaVisserICSM2010.pdf>

**(a) measured.** Applied to a benchmark of **100 object-oriented systems** (proprietary and open-source). The method: pool metric values across systems, **weight each entity by its LOC**, normalise each system's weights so no big system dominates, then read thresholds off the pooled weighted distribution at chosen weight percentiles.

**(b) the derived risk categories — verbatim:**

> "Thresholds are derived by choosing the percentage of the overall code we want to represent. For instance, to represent 90% of the overall code for the McCabe metric, the derived threshold is 14. These percentiles are used in quality profiles to characterize code according to four categories: **Low risk (0–70%), Moderate risk (70–80%), High risk (80–90%), Very-high risk (>90%).**"

For their benchmark, the McCabe thresholds that fall at 70/80/90% of code were **6, 8 and 15**. (A second passage gives 14 for the 90th; the difference is which benchmark snapshot. Both figures appear in the SIG materials — **flagged as a minor inconsistency I could not resolve**.) They also note "for 60% of the overall code the maximal McCabe value is 2."

Worked example from the paper (unit complexity quality profiles, four P2P systems):

| System | Low | Moderate | High | Very high |
|---|---|---|---|---|
| JMule 0.4.1 | 70.52% | 6.04% | 11.82% | 11.62% |
| LimeWire 4.13.1 | 78.21% | 6.73% | 9.98% | 5.08% |
| FrostWire 4.17.2 | 75.10% | 7.30% | 11.03% | 6.57% |
| Vuze 4.0.04 | 51.95% | 7.41% | 15.32% | 25.33% |

**The critical methodological point**: thresholds are **not chosen for meaning, they are chosen so that a fixed share of real-world code falls in each band.** "It creates a realistic scale, since it is constructed to represent the full range of quality achieved by real-world systems." This is a **relative/benchmark** definition of "too complex", not an absolute one.

### 2.6 The star rating and its calibration

**Baggen, R., Correia, J.P., Schill, K. & Visser, J. (2012). "Standardized code quality benchmarking for improving software maintainability." Software Quality Journal 20(2):287–307.** DOI 10.1007/s11219-011-9144-9 · <https://link.springer.com/article/10.1007/s11219-011-9144-9> · slides/PDF: <https://homepages.dcc.ufmg.br/~mtov/mes/02%20-%20SIG.EU%20Quality%20Model.pdf>

**(a) measured.** Benchmark repository as of May 2010: **>500 evaluations covering ~200 systems**, ~85% proprietary, **45 different languages** (Java, C, COBOL, C#, C++, ABAP…).

**(b) the two-level calibration — verbatim:**

> "Calibration is performed on two different levels, namely to determine thresholds for: the raw metrics; aggregated quality profiles."
> Level 1: "analyzing the statistical distributions of the raw metrics among the different systems. Thresholds are then determined based on the variability between the systems" (this is the Alves method).
> Level 2: "**the model is calibrated such that systems have a <5; 30; 30; 30; 5> percentage-wise distribution over 5 levels of quality. If a system is awarded 5 stars, it is comparable to the 5% best systems in the benchmark, in terms of maintainability.** It would be possible to select any other distribution, since it is a parameter of the calibration algorithm. We chose this one in particular so that only very good systems attain 5 stars, hence promoting excellence."

**★ This is the most important structural insight in the whole model.** The star scale is a **forced percentile distribution over a benchmark**: 5% / 30% / 30% / 30% / 5%. A star rating means "you are in this percentile of real systems", not "you crossed an absolute quality bar". Certification requires **≥2 stars on every sub-characteristic and ≥3 stars overall**.

Their own stated advantages of benchmark calibration over expert thresholds: "the process is more objective since it is based solely on data; it can be done almost automatically; it creates a realistic scale."

### 2.7 Better Code Hub / "Building Maintainable Software" — the 10 guidelines

**Visser, J. et al. (2016). "Building Maintainable Software: Ten Guidelines for Future-Proof Code."** O'Reilly. Java edition ISBN 9781491955987, C# edition ISBN 9781491967423. Appendix "How SIG Measures Maintainability": <https://www.oreilly.com/library/view/building-maintainable-software/9781491955987/app01.html> (**could not verify** — O'Reilly returned HTTP 403 to my fetch; the appendix content is inferred from the SIG/TÜViT criteria above, which is the same model).

The ten guidelines, as popularised by Better Code Hub (SIG's since-retired GitHub checker):
1. Write short units of code
2. Write simple units of code
3. Write code once (no duplication)
4. Keep unit interfaces small
5. Separate concerns in modules
6. Couple architecture components loosely
7. Keep architecture components balanced
8. Keep your codebase small
9. Automate tests
10. Write clean code

Better Code Hub's per-guideline pass thresholds were the SIG 4-star numbers of the day (e.g. **"units ≤ 15 lines"**, **"units with CC ≤ 5"**), each expressed as a % -of-code compliance target rather than a hard cap. **Could not verify** the exact Better Code Hub numbers from a live source — the service has been discontinued and its docs are no longer reachable. Use the SIG/TÜViT v17.0 numbers in §2.4 as the authoritative current version.

### 2.8 TIOBE's variant

**TIOBE TÜViT Trusted Product Maintainability ISO/IEC 25010 Quality Model, v1.2.** <https://tiobe.com/files/TIOBETUViTTrustedProductMaintainability_v1_2.pdf> · <https://www.tiobe.com/quality-models/trusted-product-maintainability/>
An independent implementation of the same TÜViT scheme against ISO/IEC 25010. Noted as a lead; **I did not extract its thresholds** in this pass.

---

## 3. The Maintainability Index (MI)

### 3.1 Origin

- **Oman, P. & Hagemeister, J. (1992). "Metrics for assessing a software system's maintainability." ICSM 1992.** The original derivation.
- **Coleman, D., Ash, D., Lowther, B. & Oman, P. (1994). "Using metrics to evaluate software system maintainability." IEEE Computer 27(8):44–49.** <https://www.ecs.csun.edu/~rlingard/comp589/ColemanPaper.pdf> · <https://www.semanticscholar.org/paper/40196eb61a0c8757675a5db9fa5f0e5001216877>
- **Welker, K.D. (1997). "Development and Application of an Automated Source Code Maintainability Index." J. Software Maintenance 9(3):127–159.** <https://onlinelibrary.wiley.com/doi/abs/10.1002/(SICI)1096-908X(199705)9:3%3C127::AID-SMR149%3E3.0.CO;2-S>

**The four-metric formula** (as quoted in Heitlager et al. 2007):

```
MI = 171 − 5.2·ln(HV) − 0.23·CC − 16.2·ln(LOC) + 50·sin(sqrt(2.46·COM))
```

where HV = Halstead Volume, CC = *average* cyclomatic complexity per module, LOC = *average* lines of code per module, COM = percentage of comment lines (in radians).

**Coleman/Oman 1994 thresholds:** MI > 85 = highly maintainable; 65–85 = moderate; **< 65 = difficult to maintain** — described by the authors as a good "rule of thumb". The 65 line is documented as **the quality cutoff established by Hewlett-Packard**.

**(a) what it was calibrated on.** Small Hewlett-Packard systems, **1,000 to 10,000 lines of code**, written in **C and Pascal**, in the **late 1980s**, fitted against maintainers' expert opinions.

### 3.2 The variants in tools today

**Visual Studio** (introduced 2007), drops the comment term and rescales to 0–100:

```
MI = MAX(0, (171 − 5.2·ln(Halstead Volume) − 0.23·CC − 16.2·ln(LOC)) · 100 / 171)
```

| VS MI | Rating |
|---|---|
| ≥ 20 | High maintainability (green) |
| 10–19 | Moderate (yellow) |
| < 10 | Low (red) |

<https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-maintainability-index-range-and-meaning>

**radon** (Python) — <https://radon.readthedocs.io/en/latest/intro.html> and `/commandline.html`:

SEI derivative: `MI = 171 − 5.2·log₂V − 0.23·G − 16.2·log₂L + 50·sin(sqrt(2.4·C))`
radon's normalised variant: `MI = max[0, 100·(171 − 5.2·lnV − 0.23·G − 16.2·lnL + 50·sin(sqrt(2.4·C))) / 171]`

| radon MI | Rank | Label |
|---|---|---|
| 100–20 | A | Very high |
| 19–10 | B | Medium |
| 9–0 | C | Extremely low |

radon's CC ranks (worth having, since they are *different again* from SIG's and the SEI's):

| CC | Rank | Risk |
|---|---|---|
| 1–5 | A | low — simple block |
| 6–10 | B | low — well structured and stable |
| 11–20 | C | moderate — slightly complex |
| 21–30 | D | more than moderate — more complex |
| 31–40 | E | high — complex, alarming |
| 41+ | F | very high — error-prone, unstable |

**Note the incoherence across tools**: VS calls MI ≥ 20 "high maintainability"; Coleman called the equivalent unscaled ≈ 34 "difficult to maintain". Same formula, incompatible verdicts, no recalibration in either.

### 3.3 The criticisms

**van Deursen, A. (2014). "Think Twice Before Using the 'Maintainability Index'."** <https://avandeursen.com/2014/08/29/think-twice-before-using-the-maintainability-index/>

The specific charges, in his own framing:
1. **Unclear origin** — "There is no clear explanation for the specific derived formula."
2. **Stale calibration** — 1,000–10,000 LOC HP systems, C and Pascal, late 1980s. "Programs written in C and Pascal […] may have rather different maintainability characteristics than current object-oriented languages such as C#, Java, or Javascript."
3. **Weak validation** — "For the experiments conducted, only few programs were analyzed, and no statistical significance was reported. Thus, the results might as well be due to chance."
4. **Confounded by size** — all ingredients correlate with size; "just measuring lines of code and taking the average per module is a much simpler metric."
5. **Averaging destroys the signal** — citing Heitlager et al.: these metrics "follow a power law, and taking the average tends to mask the presence of high-risk parts."
6. **No recalibration by vendors** — "Tool smiths and vendors used the exact same formula and coefficients as the 1994 experiments, without any recalibration."
7. **Unjustified thresholds** — on Visual Studio's 20/10 bands: "**I have not been able to find a justification for these thresholds.**"

His recommendations, verbatim:
> *Researchers*: "Think twice before using the maintainability index in your experiments. Make sure you study and fully understand the original papers published about it."
> *Tool vendors*: "There is not much point in having several metrics that are all confounded by size. Check correlations between the metrics you offer, and if any of them are strongly correlated pick the one with the clearest and simplest explanation."
> *Developers*: "Most likely, you'll be better off looking at lines of code, as it gives easier to understand information on maintainability than a formula computed over averaged metrics confounded by size."

**Supporting empirical study he cites: Sjøberg, D.I.K., Anda, B. & Mockus, A. (2012). "Questioning software maintenance metrics: a comparative case study."** ESEM 2012. Design: **one application independently built by four different companies**, then compared on maintainability and on several metrics. Conclusion as reported: **"size as a measure of maintainability has been underrated"** and the "sophisticated" maintenance metrics are **overrated**. (**Partially verified** — I have this via van Deursen's summary, not the primary text.)

**Heitlager, Kuipers & Visser 2007 §IV** is the other primary critique, and it is more specific. Their six objections, verbatim in substance:
- **Root-cause analysis**: "since the MI fitting function is based entirely on statistical correlations, there may be no causal relation at all between the values of ingredient metrics and the value of the MI derived from them."
- **Average complexity**: "We feel this is a fundamentally flawed number. […] the complexity per module will follow a power law distribution. Hence, the average complexity will invariably be low (e.g. because all setters and getters of a Java system have a complexity of 1), whereas anecdotal evidence suggests that the maintenance problems will occur in the few outliers."
- **Computability**: "There is no consensual definition of what constitutes an operator or an operand in a language such as Java or C#" — Halstead Volume is ill-defined and expensive.
- **Comment**: "counting the number of lines of comment, in general, has no relation with maintainability whatsoever. More often than not, comment is simply code that has been commented out […] Also, more documentation for a particular piece of code may have been added, precisely because it is more complex."
- **Understandability**: "There is no logical argument why the MI formula contains the particular constants, variables, and symbols that it does. The formula just 'happens' to be a good fit to a given data set. […] Why is the cyclomatic complexity multiplied by 0.23? Why does the count of comment lines appear under a square root and a sin function?"
- **Control**: "the lack of control the developers feel they have over the value of the MI makes them dismissive of the MI."

**Verdict.** MI is **not merely contested — it is essentially abandoned by the people who study maintainability empirically**, while remaining shipped by default in Visual Studio, radon, and most linters. This is the clearest case in the whole survey of (c) folklore diverging from (b) authors' conclusions.

---

## 4. Technical debt / remediation-cost models

### 4.1 SQALE (Letouzey)

**SQALE = Software Quality Assessment based on Lifecycle Expectations.** Author **Jean-Louis Letouzey** (inspearit France, formerly DNV ITGS France). Licensed CC BY-NC-ND 3.0.

- **Method Definition Document v1.0, January 2012**, originally at `sqale.org`. **⚠️ `sqale.org` now returns HTTP 404.** Mirror: <https://www.researchgate.net/publication/262863290_The_SQALE_Method_Definition_Document>. Could not verify that any version later than v1.0 exists.
- **Letouzey, J.-L. (2012). "The SQALE method for evaluating technical debt." MTD '12 (3rd Int. Workshop on Managing Technical Debt, at ICSE 2012), pp. 31–36.** <https://dl.acm.org/doi/abs/10.5555/2666036.2666042>
- **Letouzey, J.-L. & Ilkiewicz, M. (2012). "Managing Technical Debt with the SQALE Method." IEEE Software 29(6):44–51.** DOI 10.1109/MS.2012.129 · <https://ieeexplore.ieee.org/document/6279447/>
- Presentation deck (Aug 2012): <https://www.agilealliance.org/wp-content/uploads/2016/01/SQALE-Meaningful-Insights-into-your-Technical-Debt.pdf>

**Quality model — eight characteristics**, ordered by lifecycle activity (Code → Test → Evolve → Deliver → Maintain → Reuse): Testability, Reliability, Changeability, Efficiency, Security, Maintainability, Portability, Reusability. The model is explicitly **orthogonal** — "a requirement relating to one of the code's internal attributes appears only once in the Quality Model."

**Structure**: 1 Quality Model + 2 Analysis Models (a *Technical* view producing **Remediation Cost** = technical debt, and a *Business* view producing **Non-Remediation Cost** = business impact) + 3 indices. **SQID** = SQALE Quality Index Density = debt ÷ size (function points or KSLOC).

**⚠️ Provenance warning on the famous 5/10/20/50% A–E grid.** The Aug 2012 deck shows the A–E rating chart **with no numeric thresholds printed**, and I could not verify the grid from any Letouzey primary source. Borg et al. (ICSME 2024) state that SonarQube's thresholds are a *divergence* from the original: "While SonarQube uses the SQALE method, there are some variation points in the implementation compared to the original 2012 paper by Letouzey. […] SonarQube's has evolved thresholds for its Maintainability Rating (A–E)." **Treat 5/10/20/50 as SonarQube's operationalisation.**

Crucially, the SQALE deck itself says remediation functions **"must be established and calibrated by the project or the organization."** The method never claimed the constants were universal — **the universality is what the tools added.**

### 4.2 SonarQube's technical debt model — the exact numbers

**Maintainability Rating (default) — verbatim from the SonarQube docs**, corroborated independently from `docs.sonarsource.com/llms-full.txt`:

| Rating | Technical Debt Ratio |
|---|---|
| **A** | ≤ 0.05 (≤5%) |
| **B** | > 0.05 and ≤ 0.10 |
| **C** | > 0.10 and ≤ 0.20 |
| **D** | > 0.20 and ≤ 0.50 |
| **E** | > 0.50 |

**Technical Debt Ratio (`sqale_debt_ratio`) — verbatim formula:**
```
Remediation cost / Development cost
= Remediation cost / (Cost to develop 1 line of code × Number of lines of code)
```

**★ The cost-to-develop-one-line constant — verified, and it is inconsistent with itself:**
- SonarQube 9.9 docs, verbatim: **"The value of the cost to develop a line of code is 0.06 days."**
- SonarQube 2025.1 docs: "the cost to develop one line of code is predefined in the database (**by default, 30 minutes**)."
- Source constant: `org.sonar.api.CoreProperties.DEVELOPMENT_COST_DEF_VALUE = "30"` (minutes), property `sonar.technicalDebt.developmentCost`, since SonarQube 4.5.
- The docs also state "An 8-hour day is assumed." **30 min = 0.0625 days, not 0.06** — a ~4% discrepancy baked into the flagship public figure.
- **No source anywhere states a derivation for either number.**

**Technical Debt (`sqale_index`) — verbatim:** "The technical debt is the sum of the maintainability issue remediation costs. An issue remediation cost is the effort (in minutes) evaluated to fix the issue."

**★ Structural asymmetry worth noting.** Reliability and Security ratings are **not** ratios — they are **worst-single-issue** gates: A = zero issues; B/C/D/E = at least one minor/major/critical/blocker issue. So **Maintainability is a normalised ratio (gameable by adding lines); Reliability and Security are max-severity gates (gameable only by suppression).** Two different gate shapes in the same product.

**Default remediation costs (from `sonar-java` rule metadata):**

| Rule | Title | Cost |
|---|---|---|
| **S3776** | Cognitive Complexity of methods should not be too high | 5 min + 1 min per point over threshold |
| **S1541** | Methods should not be too complex (cyclomatic) | 10 min + 1 min per point over threshold |
| S1067 | Expressions should not be too complex | 5 min + 1 min per operator over 3 |
| S1192 | String literals should not be duplicated | 2 min + 2 min per duplicate |
| S138 | Methods should not have too many lines | 20 min |

Rule defaults in source: **S3776 cognitive complexity `DEFAULT_MAX = 15`** (<https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/CognitiveComplexityMethodCheck.java>); **S1541 cyclomatic `DEFAULT_MAX = 10`**.

### 4.3 CAST / CISQ — OMG ASCMM

**Automated Source Code Maintainability Measure™ (ASCMM™) v1.0, OMG Document Number `formal/2016-01-01`**, cover date January 2016. <http://www.omg.org/spec/ASCMM/1.0> · PDF <https://www.omg.org/spec/ASCMM/1.0/PDF>

**How many patterns: exactly 20** — `ASCMM-MNT-1` … `ASCMM-MNT-20`. (Beta drafts were titled "CISQ **Top 21** Maintainability Measure" and "Top 20".) Examples: MNT-7 Inter-Module Dependency Cycles; MNT-8 Source Element Excessive Size; MNT-11 Callable/Method Excessive Cyclomatic Complexity; MNT-17 Class Excessive Inheritance Level.

**❌ Correction to a common belief: ASCMM patterns are NOT CWE-mapped.** The spec says so explicitly (§1.3, verbatim): *"Unfortunately there are no equivalent repositories of weaknesses for Reliability, Performance Efficiency, or Maintainability. Knowledge of these weaknesses is spread across software engineering textbooks, expert blogs, and information sharing sites such as github."* (The *security* and *reliability* siblings ASCSM/ASCRM **are** CWE-labelled.)

**What it computes (§1.5, verbatim):** *"This calculation is presented as the **simple sum of quality measure elements without being adjusted by a weighting scheme**."* — a plain unweighted violation count. No time, no money. Benchmarking uses **violation density** = violations ÷ Automated Function Points.

**Self-declared validity limit (§1.6, verbatim):** *"The Automated Source Code Maintainability Measure is a **correlated measure rather than an absolute measure.** That is, since it does not measure all possible Maintainability-related weaknesses it does not provide an absolute measure of Maintainability."*

**How the 20 were chosen (§1.4): expert consensus, not measurement.** 24 CISQ member organisations met "several times per year for two years in the US, France, and India"; members "individually evaluated the severity of each violation" over "several rounds of eliminating lower severity violations and re-rating", drawing on "company defect logs, their career experience in different environments, and industry sources such as books and blogs."

**ASCMM default thresholds (Table 6.1):**

| Parameter | Default |
|---|---|
| Horizontal layers, min / max | 4 / 8 |
| Inheritance levels (max parent classes) | 7 |
| Number of children (max child classes) | 10 |
| Outward references (fan-out) | 5 |
| Commented-out instructions | 2% |
| Lines of code per file | **1000** |
| **Cyclomatic complexity** | **20** |
| Parameters in a signature | 7 |

With the warning: *"when the threshold values are adjusted the results cannot be compared or benchmarked to data from other analyses that used the default values."*

**Successor status**: ASCMM v1.0 was consolidated into **ASCQM** (Automated Source Code Quality Measures) — v1.1 = `formal/22-07-01`, July 2022 — which is the basis of **ISO/IEC 5055**. <https://www.omg.org/spec/ASCQM/About-ASCQM/>

### 4.4 CISQ Automated Technical Debt Measure (ATDM) — the money layer

**Automated Technical Debt Measure v1.0, OMG Document Number `formal/18-09-01`.** <https://www.omg.org/spec/ATDM/About-ATDM/> · PDF <https://www.omg.org/spec/ATDM/1.0/PDF> (a v2 beta dated Sept 2023 exists).

**Five normative steps (§1.3, verbatim):** detect the **86** violations across ASCSM+ASCRM+ASCPEM+ASCMM; *"Assign an estimate of the amount of time to remediate each occurrence of a weakness **based on a survey of software professionals**; the estimate is **a constant for each occurrence**"*; collect qualification info; compute an adjustment factor; sum.

**★★ The single most citable admission about remediation-cost calibration in this entire literature (§1.4, verbatim):**

> "Second, **there are no existing industry-wide repositories of effort data related to remediating violations of good architectural and coding practices. Consequently, the remediation times used in this specification are based on surveys of experienced developers.** […] **Default times for each weakness were developed from the modal tendency of these distributions** with some adjustments […] **Variations in time estimates and sampling factors could impact the default remediation times drawn from these data.**"

Also verbatim: *"The measure defined in this specification is a **correlated rather than absolute** measure of Technical Debt."* And it measures **principal only** — interest, business risk and opportunity cost are defined but not measured.

**ATDM default remediation times for maintainability (Table 7.4), minutes — Default / Lo / Hi** (selected):

| Pattern | Default | Lo | Hi |
|---|---|---|---|
| MNT-4 Excessive outward calls (fan-out) | **360** | 60 | 600 |
| MNT-7 Inter-module dependency cycles | 300 | 60 | 600 |
| MNT-8 Source element excessive size | 180 | 40 | 420 |
| **MNT-11 Excessive cyclomatic complexity** | **120** | 50 | 300 |
| MNT-13 Excessive number of parameters | 180 | 50 | 420 |
| MNT-17 Excessive inheritance level | 300 | 60 | 600 |
| MNT-19 Excessive similarity (clones) | 40 | 20 | 150 |

(Table 7.4 lists only **19** of the 20 patterns — **MNT-9 has no remediation-effort row**; the table jumps MNT-8 → MNT-10.)

**★ Cross-model calibration divergence — the headline finding:**

| Cost of one excessively complex method | Estimate |
|---|---|
| **SonarQube S1541** | 10 min + 1 min/point over CC 10 → a CC-30 method ≈ **30 min** |
| **CISQ ATDM MNT-11** | **120 min** default (range 50–300), threshold CC > 20 |

**Two OMG/industry-standard models disagree by ~4× on the same defect class, and neither is calibrated to time-tracked data.**

### 4.5 Known gaming and validity failure modes

**(i) SonarQube's severity taxonomy does not predict faults.**
**Lenarduzzi, V., Lomio, F., Huttunen, H. & Taibi, D. (2020). "Are SonarQube Rules Inducing Bugs?" SANER 2020, pp. 501–511.** <https://arxiv.org/abs/1907.00376>
**(a) measured**: 21 mature OSS projects, **202 SonarQube Java rules**, SZZ to label fault-inducing commits, seven ML models.
**(b) concluded, verbatim**: *"violations considered as 'bugs' by SonarQube were generally not fault-prone and, consequently, **the fault-prediction power of the model proposed by SonarQube is extremely low**."* Only ~25–26 of 202 rules showed even low fault-proneness. *"the current way of calculating technical debt is incorrect as several non-fault-prone rules are counted as fault-prone."*

**(ii) Effect sizes are negligible at scale.**
**Lenarduzzi, V., Saarimäki, N. & Taibi, D. (2020). "Some SonarQube issues have a significant but small effect on faults and changes. A large-scale empirical study." Journal of Systems and Software.** <https://arxiv.org/abs/1908.11590>
**(a) measured**: 33 Apache Java projects, 726 commits, **200,893 classes**, **27,340 faults**, **12,373,716 changes**, 173 rules violated, >95,000 TD items.
**(b) concluded**: on fault-proneness "There is no difference between clean and dirty classes"; "**all of the effect sizes were found negligible**". On change-proneness, **Cliff's Delta between −0.048 and −0.133 (negligible)**. On the taxonomy: "**all the TD items classified as Bug have no impact on fault-proneness**", and for code smells "the change- and fault-proneness of the vast majority of TD items (**more than 70%**) does not always increase together with the severity level assigned."

**(iii) Remediation-time estimates are inaccurate and biased high.**
**Saarimäki, N., Baldassarre, M.T., Lenarduzzi, V. & Romano, S. (2019). "On the Accuracy of SonarQube Technical Debt Remediation Time." SEAA 2019, pp. 317–324.** DOI 10.1109/SEAA.2019.00055
**Baldassarre, M.T., Lenarduzzi, V., Romano, S. & Saarimäki, N. (2020). "On the diffuseness of technical debt items and accuracy of remediation time when using SonarQube." Information and Software Technology 128:106377.** DOI 10.1016/j.infsof.2020.106377
**(a) measured**: 21 OSS Java projects; **81 junior developers actually fixed TD items** with real times recorded against SonarQube's estimates.
**(b) concluded, verbatim**: "**the remediation time estimated by SonarQube is inaccurate and, as compared to the actual time spent to fix TD items, is in most cases overestimated.**" The same group found SonarQube had the **lowest precision (0.18)** of six static-analysis tools against a manual ground truth.

**(iv) ★★ The strongest single result against the debt ratio as a gate.**
**Borg, M., Ezzouhri, M. & Tornhill, A. (2024). "Ghost Echoes Revealed: Benchmarking Maintainability Metrics and Machine Learning Predictions Against Human Assessments." ICSME 2024.** <https://arxiv.org/pdf/2408.10754>
**⚠️ Conflict of interest**: two of three authors are at CodeScene, whose metric wins.
**(a) measured**: **MainData** (Schnappinger et al. 2020) — **519 manually annotated Java files, each assessed by ≥3 human experts**. Six approaches, two tasks (maintainability prediction; liability prediction), tools at default settings.
It also confirms the arithmetic verbatim: *"the SQALE method calculates the ratio between TD Time and the estimated total development time of the file — **the latter estimated as 0.06 days per LoC**."*

| Approach | Threshold | Acc | UC1 F1 | UC2 F0.5 | AUC |
|---|---|---|---|---|---|
| SotA ML (AdaBoost, code metrics) | 0.5 | 0.92 | 0.95 | 0.82 | **0.97** |
| CodeScene Code Health | 9.0 | 0.93 | **0.96** | **0.87** | 0.95 |
| **LoC baseline (lines of code alone!)** | **275** | **0.91** | **0.95** | **0.83** | **0.95** |
| MS Maintainability Index | 20 | 0.84 | 0.90 | 0.62 | 0.89 |
| SonarQube TD Time | 189 | 0.86 | 0.91 | 0.68 | 0.86 |
| Average human expert | — | 0.70 | 0.88 | — | 0.83 |
| **SonarQube TD Ratio (= Maintainability Rating)** | **0.05** | **0.61** | **0.75** | **0.12** | **0.60** |

**(b) concluded, verbatim:**
> "**SonarQube's Maintainability Rating (based on TD ratio) is notably less accurate (0.75) and should not be trusted for detecting maintainability issues.**"
> "Relying on SonarQube's Maintainability Indexes B–E to highlight unmaintainable files corresponds to an **F0.5 of only 0.12 – 7x and 6x worse than Code Health and MS-MI**."
> "For UC2 on MainData, **SonarQube's default threshold of TD Ratio > 0.05 performs worse than random chance.**"
> "**the threshold for SonarQube's Maintainability Rating A does not reflect human experts' views.**"

**★ The mechanism of failure — it is the denominator**, and this is the single most transferable lesson for anyone designing a ratio-based gate:
> "small files containing just a few Java statements often were flagged as highly problematic – **just a minor violation of a code convention in such a file can turn it into a major TD scapegoat**."

Their worked example: `SVGFEFuncBElement`, a tiny Java class with three trivial smells (a field that should be `static final`, a field that should be `final`, an empty constructor), rated a major debt item purely because the LoC denominator is small.

**A plain line count at threshold 275 beat the SQALE debt ratio on every column** — devastating for a metric whose entire premise is that it says more than size. They add that their findings "call into question the validity of previous studies that solely relied on SonarQube output for establishing ground truth labels."

**(v) The rating lacks discriminating power in practice.**
**Molnar, A.-J. & Motogna, S. "A Study of Maintainability in Evolving Open-Source Software."** <https://arxiv.org/pdf/2009.00959> — 111 releases of FreeMind, jEdit and TuxGuitar over 10+ years each, SonarQube 8.2 with 550+ rules. Finding: "**most studied versions receiving an A rating**; the only exceptions were FreeMind versions 0.8.0 and 0.8.1, which earned a B." Over a decade of real evolution in three systems, the A–E scale resolved essentially **two** values.

**(vi) The financial metaphor itself is unvalidated.**
**Ampatzoglou, A., Ampatzoglou, A., Chatzigeorgiou, A. & Avgeriou, P. (2015). "The financial aspect of managing technical debt: A systematic literature review." Information and Software Technology 64:52–73.** <https://research.rug.nl/en/publications/the-financial-aspect-of-managing-technical-debt-a-systematic-lite/> — SLR over **69 primary studies**; concluded "**a clear mapping between financial and software engineering concepts is lacking.**"

### 4.6 Summary of section 4

| Model | What it actually measures | Calibration basis |
|---|---|---|
| SQALE | remediation cost ÷ development cost | organisation-specific by design; universality added by tools |
| SonarQube debt ratio | Σ rule remediation minutes ÷ (0.06 days × LOC) | **no stated derivation**; docs and source disagree by 4% |
| CISQ ASCMM | **unweighted count** of 20 violation patterns | expert consensus of 24 companies over 2 years |
| CISQ ATDM | Σ survey-derived constant minutes over 86 patterns | **modal tendency of a developer survey**; spec admits no effort data exists |

**Both OMG specs describe themselves as "correlated rather than absolute" measures.** The only one that has been benchmarked against expert human judgement — SonarQube's — **loses to a raw line count.**

---

## 5. Risk-profile / distribution-based gating rather than per-unit caps

### 5.1 The SIG idea, restated as a design pattern

Established above from primary sources:

1. **Score the distribution, not the maximum or the mean.** For each unit, compute the metric; bin units into risk bands; report **% of total LOC in each band**. (Heitlager 2007 §V.C; Alves 2010 §III.)
2. **Weight by volume, not by unit count.** A 500-line CC-30 function and a 5-line CC-30 function are not the same risk. SIG weights every profile by lines of code. (Alves 2010: "as weight we will consider…" — LOC.)
3. **Derive band boundaries from a benchmark percentile, not from a principle.** 70 / 80 / 90% of pooled, system-normalised code volume → low / moderate / high / very-high. (Alves 2010.)
4. **Rate the profile against a forced distribution over real systems.** <5; 30; 30; 30; 5> across 5 stars. A rating is a percentile claim. (Baggen 2012.)
5. **Use nested cumulative constraints at three severity levels.** "≤20.2% of code above CC 5, ≤7.3% above CC 10, ≤1.1% above CC 25." One number cannot be traded against another; you must satisfy all three. (SIG/TÜViT v17.0.)
6. **Keep a size metric alongside the complexity metric even though they correlate** — precisely to catch "large units with low complexity", which a complexity gate alone never sees. (Heitlager 2007 §V.E.)
7. **Cross-check any gameable metric with a second, harder-to-game one.** SIG pairs test coverage with assert counts for exactly this reason. (Heitlager 2007 §V.F.2.)

### 5.2 The escape-hatch pattern from NIST

Watson & McCabe's own recommended policy is **not** a hard cap (SP 500-235 §2.5):

> "For each module, either limit cyclomatic complexity to 10 (as discussed earlier, an organization can substitute a similar number), **or provide a written explanation of why the limit was exceeded.**"

This is the ancestor of the modern "suppression with a justification comment" pattern. Note it is *documented in the source everyone cites as the origin of the hard cap.*

### 5.3 ★ The thresholds actually in use — side by side

The single most persuasive argument against a hard per-unit cap is that **nobody agrees what it should be**, and the spread is not small.

| Source | Year | "Fine" | "Watch" | "Bad" | "Very bad" | Shape |
|---|---|---|---|---|---|---|
| McCabe (orig.) | 1976 | ≤10 | — | >10 | — | hard cap + case-statement exemption |
| Watson & McCabe, NIST SP 500-235 | 1996 | ≤10 (15 allowed) | — | >10 | — | cap **or written justification** |
| SEI bands (via Heitlager) | ~1997 | 1–10 | 11–20 | 21–50 | >50 | risk bands |
| SIG model | 2007 | 1–10 | 11–20 | 21–50 | >50 | **% of LOC per band** |
| Alves benchmark (100 OO systems) | 2010 | ≤6 | 7–8 | 9–15 | >15 | **% of LOC, 70/80/90th pct.** |
| radon | current | 1–5 (A), 6–10 (B) | 11–20 (C) | 21–30 (D), 31–40 (E) | 41+ (F) | per-unit letter grade |
| **SIG/TÜViT v17.0** | **2025** | **≤5** | **>5 (≤20.2% LOC)** | **>10 (≤7.3% LOC)** | **>25 (≤1.1% LOC)** | **nested cumulative % of LOC** |
| ruff `C901` (`lint.mccabe.max-complexity`) | current | ≤10 | — | >10 | — | hard cap |
| ESLint `complexity` | current | ≤20 | — | >20 | — | hard cap |

Sources: <https://docs.astral.sh/ruff/rules/complex-structure/> and <https://docs.astral.sh/ruff/settings/> (default **10**); <https://eslint.org/docs/latest/rules/complexity> (default **20**).

**ESLint's own documentation is unusually candid about the problem** — it offers no rationale for 20 and says instead: *"If you can't determine an appropriate complexity limit for your code, then it's best to disable this rule."*

**Note the two independent axes of disagreement:**
- **Where the line is**: 5, 6, 10, 15, 20 — a 4× spread, all from serious sources.
- **What shape the rule is**: a cap (McCabe, ruff, ESLint), a cap-with-justification (NIST), a letter grade per unit (radon), or a **percentage-of-code-per-band** (SEI/SIG/Alves). Only the last preserves the tail signal that §1.4 showed is the non-redundant part of CC.

The benchmark-derived numbers (Alves ≤6, SIG 2025 ≤5) are **stricter than McCabe's 10**, but paired with an explicit allowance that ~20% of code may exceed it — which is a fundamentally different, and much more achievable, contract than "no function may exceed 10."

### 5.4 Quality ratcheting, budgets and trend-based gates

**★ The industry-standard example, and it comes from the vendor of the metric in §4.2.**
**SonarSource, "Clean as You Code."** <https://docs.sonarsource.com/sonarqube-server/10.3/user-guide/clean-as-you-code>

Verbatim: *"You own the quality and security of the new code you are working on today. You aren't responsible for anyone else's code."* · *"When standards are enforced on new code, you can focus on meeting those standards in **your** code without worrying about pre-existing issues."*

**The explicit anti-hard-cap statement, verbatim:**
> "**You should always focus on new code, so we do not recommend adding conditions for overall code to your quality gate.** […] Adding conditions on overall code shifts focus away from new code to old code, making it harder for developers to take ownership of their own work."

**The default "Sonar way" quality gate — every condition is on NEW code only** (<https://docs.sonarsource.com/sonarqube-server/2025.1/instance-administration/analysis-functions/quality-gates>):
1. No new issues are introduced (new-code issue count = 0)
2. All new Security Hotspots reviewed (100%)
3. New-code test coverage **≥ 80.0%**
4. Duplication in new code **≤ 3.0%**

**★ Note what is absent: the Maintainability Rating / debt ratio is not among them.** SonarSource's own recommended gate does not gate on the SQALE number. Given §4.5(iv), that is a well-judged omission — but it means anyone who *does* gate on the debt ratio is going beyond what the vendor recommends.

**Google's peer-reviewed version of the same principle — the strongest citation available:**
**Sadowski, C., Aftandilian, E., Eagle, A., Miller-Cushon, L. & Jaspan, C. (2018). "Lessons from Building Static Analysis Tools at Google." Communications of the ACM 61(4):58–66.** DOI 10.1145/3188720 · <https://cacm.acm.org/research/lessons-from-building-static-analysis-tools-at-google/>

**(a) measured / reported.** Deployment history of Tricorder at Google. **Two prior approaches failed**: (1) filing bugs from tool findings — "did not scale, with **84% of bugs not being fixed**"; (2) an earlier code-review integration killed by false positives and lack of customisation.
**(b) concluded.** The successful model surfaces findings **at code-review time, on the change under review**, where engineers fix them "by their own choice before the problematic code is checked into the codebase." **Legacy findings are not gated at all.** The workflow-integration point, not the metric, determines adoption.
See also Winters, Manshreck & Wright, *Software Engineering at Google*, Ch. 20 "Static Analysis" — free at <https://abseil.io/resources/swe-book/html/ch20.html>

**Explicit "quality ratchet" literature — ⚠️ all grey/practitioner, no peer-reviewed empirical study exists:**
- **Kevin Ball, "Introducing quality ratchets: A tool for managing complex systems," LeadDev, 1 July 2022.** <https://leaddev.com/software-quality/introducing-quality-ratchets-tool-managing-complex-systems> — a quality ratchet is "a process, ritual, or piece of tooling that **forces the codebase towards better quality over time**", moving in one direction only. Three types: fully automated tooling ratchets (CI-enforced type systems, lint configs), semi-automated (test suites that "prevent merging of code that causes a regression"), and process-based (incident review). Recommends automated over process-based to protect velocity.
- **★ Notion Engineering, "Custom ESLint ratcheting."** <https://www.notion.com/blog/how-we-evolved-our-code-notions-ratcheting-system-using-custom-eslint-rules> — **the canonical implementation pattern**: a checked-in **database of allowed error counts per file**; CI blocks any merge that *increases* a count; fixing a warning *automatically lowers* that file's allowance via a pre-commit hook, so it cannot be reintroduced.
- Dusty Burwell, "Ratchets: Improving systems incrementally" (2019) <https://www.dustyburwell.com/2019/05/29/ratchets>
- "Temporal Ratcheting: Automated Quality Improvement on a Schedule" <https://www.code101.net/temporal-ratcheting> — the variant where the baseline **must improve on a schedule**, not merely never worsen.

**Honest gap**: there is **no peer-reviewed empirical evaluation of quality ratcheting as such**. The closest peer-reviewed support is Sadowski et al. 2018 (new-code-only gating works; whole-codebase bug-filing does not). Label it "industry practice, not empirically validated."

### 5.5 Cognitive Complexity — the metric designed to fix CC's aggregation problem

**Campbell, G. Ann. "Cognitive Complexity: a new way of measuring understandability." SonarSource white paper, v1.7, 29 August 2023** (v1.0 2016/2017). <https://www.sonarsource.com/docs/CognitiveComplexity.pdf>
Companion: **Campbell, "Cognitive Complexity, Because Testability != Understandability," 7 Dec 2016.** <https://www.sonarsource.com/blog/cognitive-complexity-because-testability-understandability/>

**The stated critique of cyclomatic complexity — four charges, verbatim:**
1. *"Cyclomatic Complexity was initially formulated as a measurement of the 'testability and maintainability' of the control flow of a module. **While it excels at measuring the former, its underlying mathematical model is unsatisfactory at producing a value that measures the latter.**"*
2. *"methods with equal Cyclomatic Complexity do not necessarily present equal difficulty to the maintainer, leading to a sense that the measurement '**cries wolf**' by over-valuing some structures, while under-valuing others."*
3. *"Formulated in a Fortran environment in 1976, it doesn't include modern language structures like **try/catch, and lambdas**."*
4. **★ The charge most relevant to aggregate gating, verbatim:** *"because each method has a minimum Cyclomatic Complexity score of one, it is impossible to know whether any given class with a high aggregate Cyclomatic Complexity is a large, easily maintained domain class, or a small class with a complex control flow. Beyond the class level, **it is widely acknowledged that the Cyclomatic Complexity scores of applications correlate to their lines of code totals. In other words, Cyclomatic Complexity is of little use above the method level.**"*

**This is SonarSource independently arriving at Landman et al.'s empirical finding (§1.4): aggregated CC is a size metric.**

**The worked example — both methods have cyclomatic complexity exactly 4:**
```java
String getWords(int number) {          // CC 4  →  Cognitive 1
  switch (number) {                    // +1 for the whole switch
    case 1: return "one";
    case 2: return "a couple";
    case 3: return "a few";
    default: return "lots";
  }
}

int sumOfPrimes(int max) {                    // CC 4  →  Cognitive 7
  int total = 0;
  OUT: for (int i = 1; i <= max; ++i) {       // +1
    for (int j = 2; j < i; ++j) {             // +2 (nesting=1)
      if (i % j == 0) {                       // +3 (nesting=2)
        continue OUT;                         // +1 (labelled jump)
      }
    }
    total += i;
  }
  return total;
}
```

**The three basic rules, verbatim:**
1. "Ignore structures that allow multiple statements to be readably shorthanded into one"
2. "Increment (add one) for each break in the linear flow of the code"
3. "Increment when flow-breaking structures are nested"

**Scoring specification (Appendix B):**
- **+1 increments**: `if`, `else if`, `else`, ternary · `switch` (the whole thing, once) · `for`, `foreach` · `while`, `do while` · `catch` · labelled `goto`/`break`/`continue` · **each *sequence* of like binary logical operators** · **each method in a recursion cycle**.
- **Structures that raise the nesting level**: `if`/`else if`/`else`/ternary, `switch`, loops, `catch`, and **nested methods and lambdas**.
- **Structures that receive a nesting increment** (i.e. +1 per level of depth): `if`, ternary, `switch`, loops, `catch`. Note `else`/`else if` raise nesting but do not *receive* a nesting increment — the "hybrid" case.

**Explicitly ignored / discounted:**
- **The method itself** — "Cognitive Complexity does not increment for methods". **This is what makes aggregation meaningful**, and is the direct fix for charge 4.
- **`try` and `finally` are ignored altogether**; a `catch` is +1 regardless of how many exception types it catches.
- **A whole `switch` = one increment** (vs. cyclomatic's +1 per case). Rationale verbatim: *"an if-else if chain must be read carefully, while a switch can often be taken in at a glance."*
- **Sequences of like operators get one increment**: `a && b && c && d` = +1; `a || b && c || d` = +2.
- **Early `return` costs nothing** — "an early return can often make code much clearer".
- **Null-coalescing operators** — "they allow short-handing multiple lines of code into one".

**★ The default threshold of 15 — verified, but NOT from the white paper.** The white paper states **no numeric threshold**; nor does the blog post; nor does the S3776 rule page. It is only verifiable in source:
```java
@Rule(key = "S3776")
public class CognitiveComplexityMethodCheck ... {
  private static final int DEFAULT_MAX = 15;
```
<https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/CognitiveComplexityMethodCheck.java>

**No derivation, calibration or rationale for 15 is given anywhere I could reach.** It is a chosen constant, exactly like McCabe's 10 and SonarQube's 0.06 days/LOC. The widely repeated claim that the default is **25 for C/C++/Objective-C** "where developers seem to have a higher tolerance for complexity" — **could not verify** from a SonarSource primary source.

**Empirical standing**: see §6.1 — Muñoz Barón et al. (ESEM 2020) found r = 0.54 with comprehension *time* but −0.13 with *correctness*; Lavazza et al. (JSS 2023) rate both CC and Cognitive Complexity only "modest predictors" of understandability.

### 5.6 Goodhart's law and metric gaming

**The original (economics):** **Goodhart, C.A.E. (1975). "Monetary Relationships: A View from Threadneedle Street." Papers in Monetary Economics, Vol. 1, Reserve Bank of Australia.**
Original formulation: **"Any observed statistical regularity will tend to collapse once pressure is placed upon it for control purposes."**
<https://en.wikipedia.org/wiki/Goodhart%27s_law>
**Note the original is *not* the famous phrasing** — Goodhart never wrote "when a measure becomes a target…". Empirical context: after the 1971–73 UK deregulation, the demand-for-money function collapsed and monetary targets **overshot by 100%** once they were targeted.

**The popular phrasing (anthropology):** **Strathern, M. (1997). "'Improving ratings': audit in the British University system." European Review 5(3):305–321.** DOI 10.1002/(SICI)1234-981X(199707)5:3<305::AID-EURO184>3.0.CO;2-4 · <https://gwern.net/doc/statistics/decision/1997-strathern.pdf>
**This is the source of "When a measure becomes a target, it ceases to be a good measure."** Strathern attributes the "Goodhart's law" label to Hoskin. Context: the UK higher-education "audit explosion", where "the subject of audit is not so much the education of the students as the institutional provision for their education" — the proxy displaces the thing.
**⚠️ Could not page-verify the quotation**: both available PDFs are image/JBIG2-encoded and resisted text extraction. Cite the paper, and quote the sentence as universally reported rather than as a page-verified quotation.

**★ The best software-specific citation for metric gaming:**
**Bouwers, E., Visser, J. & van Deursen, A. (2012). "Getting What You Measure." Communications of the ACM 55(7):54–59** (also ACM Queue 10(4)). DOI 10.1145/2208917.2229115 · <https://queue.acm.org/detail.cfm?id=2229115> · open PDF <https://repository.ubn.ru.nl/bitstream/handle/2066/103392/103392.pdf>
Subtitle: "Four common pitfalls in using software metrics for project management." The four pitfalls:
1. **Metric in a bubble** — interpreting a value with no context or benchmark.
2. **Treating the metric** — optimising the number instead of the underlying property (Goodhart, named as a software pitfall).
3. **One-track metric** — steering on a single number.
4. **Metrics galore** — so many metrics that nobody acts.
**⚠️ All three URLs returned 403 to my fetcher; the pitfall names and framing are from search-result excerpts, so treat the wording as reported rather than verbatim-verified.**
Note the authorship: **the same SIG/TU Delft group behind the model in §2** — the people who built the risk-profile model also wrote the paper on how metrics get gamed.

**The canonical book-length treatment:**
**Austin, R.D. (1996). *Measuring and Managing Performance in Organizations*. Dorset House. ISBN 0-932633-36-6.**
Based on an award-winning Carnegie Mellon doctoral thesis and **explicitly grounded in software measurement** — findings "bolstered by interviews with eight recognized experts in the use of measurement to manage computer software" (Software Productivity Solutions, AT&T Bell Laboratories, others).
Thesis, verbatim: *"Because people often react with unanticipated sophistication when they are being measured, measurement-based management systems can become dysfunctional, interfering with achievement of intended results. Measurement dysfunction follows a pattern that can be identified and avoided."*
The model: a principal and an agent who splits effort between two tasks; **if the principal incentivises only one task, the agent starves the other.** Austin's key distinction — **full supervision vs. partial supervision**: measurement works when *all* dimensions of value are measured; when only some are, distortion is the rational agent response. **⚠️ Could not verify Austin's exact phrasing of the full/partial distinction from a primary source.**

**The documented failure modes already collected above, as a checklist:**

| Failure mode | Documented in |
|---|---|
| Redefine the metric to make it pass ("modified complexity" ÷ case branches: CC 90 → 10 by adding a dead 10-branch switch) | NIST SP 500-235 §2.5 |
| Raise coverage without raising testing (tests with no asserts) | Heitlager et al. 2007 §V.F.2 |
| Small-denominator pathology (a tiny file becomes "major debt" from three trivial smells) | Borg et al. ICSME 2024 |
| Averaging hides the tail (power-law CC ⇒ mean is always low) | Heitlager et al. 2007 §IV.B; van Deursen 2014 |
| Severity labels that don't track severity (>70% of smells don't worsen with rank) | Lenarduzzi et al. JSS 2020 |
| Aggregating CC turns it into a size metric | Landman et al. 2016; Campbell (Cognitive Complexity) |
| Threshold-shopping destroys comparability | OMG ASCMM §6, Table 6.1 note |

**⚠️ Sources found but NOT recommended.** Several SEO content-farm domains (`technicaldebtcost.com`, `codedebtcost.com`, `edana.ch`, `softwaremodernizationservices.com`) surface confident-sounding critiques, e.g. "the SonarQube default of 10 minutes per excess unit of cognitive complexity is plausible but not based on time-tracked data". The *direction* is supported by ATDM §1.4 and Saarimäki et al., but the specific figure is **wrong** (S3776 is 5 min + 1 min/point; 10 min is S1541's offset). Treat these as folklore; cite ATDM §1.4 and Saarimäki/Baldassarre for the same point with real provenance.

---

## 6. What actually predicts maintenance effort and defects

### 6.1 Do complexity metrics predict human comprehension? (mostly no)

**Muñoz Barón, M., Wyrich, M. & Wagner, S. (2020). "An Empirical Validation of Cognitive Complexity as a Measure of Source Code Understandability." ESEM 2020.** DOI 10.1145/3382494.3410636 · <https://arxiv.org/pdf/2007.12520> · *ESEM 2020 Best Full Paper*.

**(a) measured.** A meta-analysis over **10 studies, 427 code snippets, ~24,000 individual human evaluations**, correlating SonarSource's Cognitive Complexity with three families of comprehension outcome. Random-effects model, Cohen's guidelines (>0.1 small, >0.3 medium, >0.5 large).

| Outcome | Studies | Snippets | Range of effect sizes | **Weighted mean** |
|---|---|---|---|---|
| **Time** to comprehend | 9 | 327 | −0.03 to +0.94 | **+0.54** (large); I² = 85% |
| **Correctness** of comprehension | 6 | 269 | −0.52 to +0.57 | **−0.13** (small) |
| **Subjective rating** of difficulty | 4 | 203 | −0.57 to −0.04 | **−0.29** (medium); I² = 46% |
| Physiological (fMRI deactivation) | — | — | small, insignificant | no correlation found |

**(b) concluded.** "It is the first validated and solely code-based metric" for understandability — but note the heterogeneity (I² = 85% on the time result) is enormous, and the correctness result is essentially null.

**Key comparison finding reported in the same paper**, on cyclomatic complexity specifically: comparing against Peitek et al.'s fMRI data, "**While Cognitive Complexity performs slightly better than Cyclomatic Complexity in [the] BA31post region, the correlations are overall small and insignificant.**"

**Scalabrino, S., Bavota, G., Vendome, C., Linares-Vásquez, M., Poshyvanyk, D. & Oliveto, R. — "Automatically Assessing Code Understandability" (ICSE 2017 / IEEE TSE 2021).** As summarised in the Muñoz Barón paper: they "calculated correlations between **121 metrics** and proxy variables for understandability gathered in an experiment with professional developers… investigated code-metrics like LOC and Cyclomatic Complexity, documentation-related metrics… and metrics relating to a developer's experience and background. They concluded that **none of the investigated metrics could accurately represent code understandability. Even after repeating the study with an increased sample size, the results did not change.**"

**Trockman, A. et al.** reanalysed Scalabrino's dataset with different statistics and "found that code features had a **small but significant** correlation with understandability" — concluding a useful metric *could* be built but more data is needed. **A genuine disagreement in the literature; flagged as contested.**

**Peitek, N. et al.** — fMRI study of code comprehension: "for all deactivated areas, higher values for the metric DepDegree and Halstead's measures indicated more concentration. **Lines of code showed the weakest correlations** with concentration during comprehension tasks. For Cyclomatic Complexity, they found that higher values were associated with lower concentration." Authors themselves warn the sample size was small and snippets were not designed for this question.

**Lavazza, L., Abualkishik, A.Z., Liu, G. & Morasca, S. (2023). "An empirical evaluation of the 'Cognitive Complexity' measure as a predictor of code understandability." Journal of Systems and Software 197:111561.** DOI 10.1016/j.jss.2022.111561 · <https://www.sciencedirect.com/science/article/abs/pii/S0164121222002370>
Conclusion as reported: "**While the old-fashioned McCabe Cyclomatic Complexity and the most recent Cognitive Complexity are modest predictors for code understandability when considering the complexity perceived by early-career developers, they are not for problem severity.**" This is a **direct rebuttal** of the strong reading of Muñoz Barón et al. — same metric, different outcome variable, much weaker verdict.

**Wyrich, M., Bogner, J. & Wagner, S. (2023). "40 Years of Designing Code Comprehension Experiments: A Systematic Mapping Study." ACM Computing Surveys.** <https://arxiv.org/pdf/2206.11102> · <https://www.se.cs.uni-saarland.de/publications/docs/wyrich202340.pdf>
Finding: wide variation in tasks, measurements and contexts, and "substantial variation in how comprehension is implicitly defined", producing **limited comparability across experiments**. This is the meta-reason the comprehension literature does not converge.

### 6.2 Does code quality predict business outcomes? (the strongest recent positive results)

**Tornhill, A. & Borg, M. (2022). "Code Red: The Business Impact of Code Quality — A Quantitative Study of 39 Proprietary Production Codebases." TechDebt 2022 (IEEE/ACM Int. Conf. on Technical Debt).** DOI 10.1145/3524843.3528091 · <https://arxiv.org/abs/2203.04374> · replication package: <https://github.com/empear-analytics/code-health-study-tech-debt-2022>

**(a) measured.** **39 proprietary production codebases**, activity in **30,737 files**, using CodeScene's *Code Health* metric (source-code analysis + version-control mining + Jira issue data).

**(b) concluded — verbatim from the abstract:**
> "we find that **low quality code contains 15 times more defects than high quality code**. Furthermore, **resolving issues in low quality code takes on average 124% more time in development**. Finally, we report that issue resolutions in low quality code involve higher uncertainty manifested as **9 times longer maximum cycle times**."

**Caveats to record**: Code Health is a **proprietary composite** (CodeScene), the study is authored by CodeScene's founder, and codebases are not public. Treat the direction as credible, the multipliers as vendor-favourable point estimates. The replication package is public, which is more than most.

**Borg, M., Pruvost, I., Mones, E. & Tornhill, A. (2024). "Increasing, not Diminishing: Investigating the Returns of Highly Maintainable Code." TechDebt 2024, Lisbon.** <https://arxiv.org/abs/2401.13407>

**(b) concluded — verbatim from the abstract:**
> "Our results show that the associations vary across different intervals of code quality. Furthermore, the value model suggests **strong non-linearities at the extremes of the code quality spectrum**. Most importantly, the model suggests **amplified returns on investment in the upper end**. We discuss the findings within the context of the 'broken windows' theory and recommend organizations to **diligently prevent the introduction of code smells in files with high churn.**"

**The last clause is the operational recommendation**: gate on quality *where churn is high*, not uniformly. **Could not verify** the specific regression coefficients — the abstract does not carry them and I did not retrieve the full paper.

### 6.3 Process metrics vs product metrics — the strongest signal in the whole survey

#### Nagappan & Ball 2005 — relative churn

**Nagappan, N. & Ball, T. (2005). "Use of Relative Code Churn Measures to Predict System Defect Density." ICSE 2005, pp. 284–292.** DOI 10.1145/1062455.1062514 · PDF <https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse05churn.pdf>

**(a) measured.** Windows Server 2003 → W2k3 SP1. **44.97 million LOC (44,970 KLOC)**, **2,465 binaries**, **96,189 files**. Dependent variable: defects/KLOC per binary.

The **eight relative churn measures**, verbatim:

| | Definition |
|---|---|
| M1 | Churned LOC / Total LOC |
| M2 | Deleted LOC / Total LOC |
| M3 | Files churned / File count |
| M4 | Churn count / Files churned |
| M5 | Weeks of churn / File count |
| M6 | Lines worked on / Weeks of churn ("lines worked on" = churned + deleted) |
| M7 | Churned LOC / Deleted LOC (proxy for new feature development) |
| M8 | Lines worked on / Churn count |

The design is an explicit **cross-check lattice** — M1/M2/M7 cross-check each other; M8 cross-checks M3/M4 and M5/M6.

**★ The result, from the paper's own tables:**

| Model | R² | Adj. R² | F |
|---|---|---|---|
| **Absolute** measures, all predictors | **0.052** | (0.049) | 16.922, p<0.0005 |
| Absolute, step-wise | 0.051 | 0.050 | — |
| Absolute, PCA (2 components) | **0.026** | — | 33.279, p<0.0005 |
| **Relative (M1–M8), all measures** | **0.811** | 0.811 | 1318.44, p<0.0005 |
| Relative, step-wise (M7 dropped) | 0.811 | 0.811 | 1507.31 |
| Relative, PCA (3 components) | 0.749 | 0.748 | 2450.89 |

**A ~16× difference in variance explained, from nothing but normalising churn by size and time.**

Spearman ρ with defects/KLOC (all p<0.01): M1 **.883**, M3 **.868**, M6 **.843**, M2 **.798**, M5 **.729**, M4 **.631**, M7 **.507**.

Held-out prediction (train 1,645 binaries / test 820): test-set Pearson **0.889**, Spearman **0.929**. Repeated over three further random splits: Pearson 0.873/0.878/0.899.

Discriminant analysis, fault-prone vs not: **89.0%** (full-sample PCA), **89.6–90.1%** on held-out data.

**(b) concluded, verbatim from the abstract:** "**while absolute measures of code churn are poor predictors of defect density, our set of relative measures of code churn is highly predictive**."

**(c) folklore check.** The folklore is "churn predicts bugs." The finding is *stronger and more specific*: **raw churn is nearly useless (R² = 0.05)**; churn *normalised by size and time* carries the signal. The paper itself already cites Graves et al. (TSE 2000): "**in general, process measures based on change history have been found to be better indicators of fault rates than product metrics of code.**"

⚠️ **Could not verify**: the paper prints "The adjusted R² value for the absolute measures is 0.49" immediately after reporting R² = 0.052 — almost certainly a typo for 0.049, but I could not confirm which was intended.

#### Rahman & Devanbu 2013 — *why* process metrics win

**Rahman, F. & Devanbu, P. (2013). "How, and Why, Process Metrics Are Better." ICSE 2013, pp. 432–441.** <https://dl.acm.org/doi/10.5555/2486788.2486846> · PDF <https://research.cs.queensu.ca/home/ahmed/home/teaching/CISC880/F17/papers/HowAndWhyProcessMetricsAreBetter.pdf>

**(a) measured.** **85 releases across 12 Apache Java projects** (CXF, Camel, Derby, Felix, HBase, Hadoop-Common, Hive, Lucene, OpenEJB, OpenJPA, Qpid, Wicket). Defect labels from JIRA-linked fixing commits with a **median defect-linking rate >80%** (vs "typically under 50%" in the literature) — an unusually clean dataset. **14 process metrics** vs **54 code metrics** from Scitools Understand (including MaxCyclomatic, AvgCyclomatic, SumCyclomatic, MaxNesting, CountPath). Four learners (LogReg, J48, SVM, Naive Bayes). Evaluated by AUC, F50, and **cost-effectiveness AUCEC at 10%/20% of SLOC inspected**. Genuinely predictive setup: train on release *k*, test on *k+1*.

**(b) findings.** (Most results are boxplots, so exact point values are limited.)

- **Performance**: "process metrics **always** perform significantly better than code metrics across all learning techniques, with very low p value (**p < 0.001**)." Process + size does **not** beat process alone; process + code does **not** beat process alone. Code-metric AUC is "around 0.8", but at **AUCEC20 "code metrics don't do much better than random."**
- **Portability (cross-project)**: both degrade (p<0.001), but "**code metrics show a larger decline of performance than process metrics**."
- **★ Stasis — the mechanism.** Stasis = Spearman correlation of a metric's per-file values between successive releases.
  - **Code metrics have stasis ≈ 0.96** — so high the authors could not even run their high-vs-low-stasis comparison on them.
  - Process metrics span a range: **median stasis under 0.5**. The top 5 by stasis (OEXP, EXP, OWN, MINOR, DDEV) have median stasis **> 0.93**; the other 9 (SCTR, COMM, ADEV, NSCTR, NCOMM, NDDEV, NADEV, DEL, ADD) have median stasis **< 0.32**.
  - Models from **low-stasis** process metrics reach **median AUC > 0.9**; from **high-stasis** process metrics, "**barely around 0.8**" (all p<0.001). **Low stasis *causes* predictive power.**
- **Stagnation**: "the code metrics based models are **essentially spitting out the original probabilities** it learned from the training data" — they name the same files defective, release after release.
- **★ The punchline.** Partitioning files into *recurring* (defective in train and test), *bait* (train only) and *decoy* (test only): **recurringly defective files are significantly larger (p<0.001), while files defective only in the test release have significantly higher defect *density* (p<0.001).** So a stagnant code-metric model preferentially points at big, low-density files — **the worst possible use of an inspection budget.**

**(b) concluded, near-verbatim:** "code metrics, which is widely used in the literature, may not evolve with the changing distribution of defects, which leads code-metric-based prediction models **stagnating**, and tending to focus on files which are recurringly defective… such recurringly defective files are **larger and less defect dense**, therefore these large files may compromise the cost-effectiveness of the stagnant code-metric-based models."

Threat the authors flag: all 12 projects are Java, OSS and Apache-governed; they ask for commercial replication.

#### Majumder, Mody & Menzies 2022 — the 60× replication

**Majumder, S., Mody, P. & Menzies, T. (2022). "Revisiting Process versus Product Metrics: A Large Scale Analysis." Empirical Software Engineering 27(3).** <https://link.springer.com/article/10.1007/s10664-021-10068-4> · <https://arxiv.org/abs/2008.09569>

**(a) measured.** **722,471 commits from 700 GitHub projects** (vs Rahman & Devanbu's 85 releases / 12 projects).
**(b) concluded.** **Best process-based models: median recall 98%, AUC 95%. Best product-based models: median recall 44%, AUC 54%.** AUC 54% is barely above the 50% random baseline.

**Three teams, three eras, three orders of magnitude of scale, same answer.**

#### Bird et al. 2011 — ownership, and the "minor contributor"

**Bird, C., Nagappan, N., Murphy, B., Gall, H. & Devanbu, P. (2011). "Don't Touch My Code! Examining the Effects of Ownership on Software Quality." ESEC/FSE 2011, pp. 4–14.** DOI 10.1145/2025113.2025119 · PDF <https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bird2011dtm.pdf>

**(a) definitions, verbatim.** *Proportion of ownership* = a contributor's commits to a component ÷ total commits. **Minor contributor = "a developer who has made changes to a component, but whose ownership is below 5%."** (Sensitivity analysis from 2% to 10% "yielded similar results.") Metrics: **Minor** (count of minor contributors), **Major**, **Total**, **Ownership** (proportion held by top owner). Unit = binary (.dll/.exe/.sys). Corpus: **Windows Vista and Windows 7**, 2,000+ developers, thousands of binaries; pre-release faults and post-release failures over six months.

**Table 1 — bivariate Spearman correlation with failures:**

| Metric | Vista pre | Vista post | Win7 pre | Win7 post |
|---|---|---|---|---|
| Total | 0.84 | 0.70 | 0.92 | 0.24 |
| **Minor** | **0.86** | **0.70** | **0.93** | **0.25** |
| Major | 0.26 | 0.29 | −0.40 | −0.14 |
| Ownership | −0.49 | −0.49 | −0.29 | −0.02 |
| Size | 0.75 | 0.69 | 0.70 | 0.26 |
| Churn | 0.72 | 0.69 | 0.71 | 0.26 |
| **Complexity** | **0.70** | **0.53** | **0.56** | **0.37** |

The authors' own emphasis: "**Minor had a higher correlation with both pre- and post-release defects in Vista and pre-release defects in Windows 7 than any other metric that Microsoft collects!**"

**Table 2 — variance explained (adjusted R²), controlling for size/complexity/churn:**

| Model | Vista pre | Vista post | Win7 pre | Win7 post |
|---|---|---|---|---|
| Base (size + complexity + churn) | 26% | 29% | 24% | 18% |
| Base + Total | 40% | 35% | 68% | 21% |
| **Base + Minor** | **46%** | **41%** | **70%** | **21%** |
| Base + Minor + Major + Ownership | 50% | 44% | 72% | 22% |

**One process variable, `Minor`, roughly doubles the variance explained over the classic size/complexity/churn base**, and nearly triples it for Win7 pre-release (24% → 70%).

**The Pinzger replication (§7.2)** — the strongest evidence that *social* structure carries the signal: Pinzger et al.'s contribution-network predictor identified **90% of fault-prone binaries at 85% precision**. Retrained with **minor-contributor edges removed**, it drops to **58% recall, ~44% precision** — where random guessing gives 50%.

**(c) folklore check.** The folklore is "many cooks spoil the broth." The refinement is sharper and actionable: it is not headcount, it is the count of **low-expertise** contributors. `Major` barely matters, and in Win7 pre-release even correlates *negatively* (−0.40).

#### Supporting classics

**Basili, V.R., Briand, L.C. & Melo, W.L. (1996). "A Validation of Object-Oriented Design Metrics as Quality Indicators." IEEE TSE 22(10):751–761.** <https://www.cs.umd.edu/~basili/publications/technical/T102.pdf>
**8 student teams**, identical requirements, C++, **180 classes / 58 faulty / 258 faults**. RFC p=0.0000; DIT p=0.0000; CBO significant; **WMC only marginal overall (p=0.06)**; **NOC significant but in the wrong direction** (more children → *fewer* faults); **LCOM insignificant in all cases**. Head-to-head: OO design metrics completeness 88% / correctness 60% vs code metrics (incl. cyclomatic complexity) 83% / 45.5%. **Scope limit rarely quoted: students, one 180-class dataset.**

**Zimmermann, T. & Nagappan, N. (2008). "Predicting Defects Using Network Analysis on Dependency Graphs." ICSE 2008, pp. 531–540.** <https://thomas-zimmermann.com/publications/files/zimmermann-icse-2008.pdf>
Windows Server 2003 dependency graph. Predicting hand-curated critical binaries: **complexity metrics recall 0.30 vs network measures 0.60** — exactly twice as good. Defect classification: precision ~0.70 throughout; recall **~0.60 for complexity metrics vs ~0.70 for network measures** (+0.10, significant at 99%). **Structural *position* in the dependency graph carries defect signal that intra-module complexity does not.**

**Menzies, T., Greenwald, J. & Frank, A. (2007). "Data Mining Static Code Attributes to Learn Defect Predictors." IEEE TSE 33(1):2–13.**
Claimed: naive Bayes on log-transformed NASA MDP attributes gives **pd = 71%, pf = 25%**; and "**how the attributes are used to build predictors is much more important than which particular attributes are used**." ⚠️ Numbers from the abstract, not extracted from the PDF. Note this is *not* a claim that static metrics are good in absolute terms — 71% recall at 25% false alarms on imbalanced data is exactly the regime Rahman & Devanbu later show is cost-ineffective. Menzies' **2025 retrospective** (<https://arxiv.org/pdf/2501.15662>) is about why the paper spread, not a numeric recantation.

**★ Shepperd, M., Bowes, D. & Hall, T. (2014). "Researcher Bias: The Use of Machine Learning in Software Defect Prediction." IEEE TSE 40(6):603–616.** <https://bura.brunel.ac.uk/bitstream/2438/8784/2/Fulltext.pdf>
Meta-analysis of **42 primary studies / 600 result sets**, all re-expressed as Matthews Correlation Coefficient; 4-way random-effects ANOVA.

| Source of variance in MCC | % of total |
|---|---|
| **ResearcherGroup** | **31.0%** |
| Dataset | 11.2% |
| ResearcherGroup:Classifier | 6.6% |
| **Metric family** | **5.2%** |
| **Classifier** | **1.3%** |
| Residuals | 43.6% |

Verbatim: the variability due to classifier choice "is extremely small… the variability due to the groups of researchers could be seen as **twenty five times higher**."
**This is a strong prior against any claim of the form "metric X predicts defects with accuracy Y."** ⚠️ Contested: "Comments on 'Researcher Bias'" (IEEE TSE 2016, <https://ieeexplore.ieee.org/document/7450669/>) argues research group is confounded with dataset and metric family, and after mitigation **metric family matters more than research group**.

**Fenton, N.E. & Neil, M. (1999). "A Critique of Software Defect Prediction Models." IEEE TSE 25(5):675–689.** DOI 10.1109/32.815326
Argues models are weak because of (i) the unknown relation between *defects* and *failures*, (ii) statistical and data-quality problems, (iii) size/complexity single-issue models. The "**Goldilocks Conjecture**" (an optimum module size exists) is the worked example of what goes wrong. Recommends holistic Bayesian Belief Network models. ⚠️ Full text not obtained; internal figures unverified.

**Herraiz, I. & Hassan, A.E. (2010). "Beyond Lines of Code: Do We Need More Complexity Metrics?" ch. 8 in *Making Software: What Really Works, and Why We Believe It*, O'Reilly.** <https://www.oreilly.com/library/view/making-software/9780596808310/ch08.html> (403 to my fetcher)
Conclusion, quoted via a third party quoting the chapter: "for non-header files written in C language, **all the complexity metrics are highly correlated with lines of code, and therefore the more complex metrics provide no further information that could not be measured simply with lines of code**"; and complexity metrics "do not provide information on the amount of effort that is needed to comprehend a piece of code—or, at least, **no more information than lines of code do**."
⚠️ **Could not verify** the frequently-cited specifics (~200,000 Arch Linux C files; LOC↔CC r = +0.72; LOC↔Halstead r = +0.91). The qualitative conclusion is verified by direct quotation; the coefficients are not.

#### fMRI: cyclomatic complexity tracks nothing

**★ Peitek, N., Apel, S., Parnin, C., Brechmann, A. & Siegmund, J. (2021). "Program Comprehension and Code Complexity Metrics: An fMRI Study." ICSE 2021, pp. 524–536. (ACM SIGSOFT Distinguished Paper.)** PDF <https://web.eecs.umich.edu/~weimerw/2024-481F/readings/peitek2021-metrics.pdf> · replication <https://github.com/brains-on-code/fMRI-complexity-metrics-icse2021>

**(a) measured.** **19 participants** in an fMRI scanner; **>41 metrics** analysed, four reported in depth (LOC, Halstead, McCabe, DepDegree). Outcomes: brain activation, default-mode-network *deactivation* (a cognitive-load proxy), response time, correctness, subjective ratings. Kendall's τ. Behavioural baseline: 32 s/task, 72% correct.

**Table II — Kendall's τ:**

| Metric | vs correctness | vs response time | vs subjective complexity | vs DMN deactivation |
|---|---|---|---|---|
| **LOC** | **−.46** | .22 | .16 | −.30 / −.39 |
| **Halstead** | **−.45** | .24 | .20 | −.30 / −.42 |
| DepDegree | −.41 | .26 | .16 | −.24 / −.29 |
| **McCabe** | **−.09** | **.06** | **−.07** | **.05 / .04** |

**(b) concluded, verbatim:** "**McCabe, however, consistently lacked any significant correlation with our observed measures.**" And: "code's textual size drives programmers' attention, and vocabulary size burdens programmers' working memory." Overall: "Our results provide **neuro-scientific evidence supporting warnings of prior research questioning the validity of code complexity metrics**."

**The blunt version: in an fMRI scanner, LOC and Halstead track cognition; cyclomatic complexity tracks nothing.**

#### Scalabrino et al. — the flagship negative result, with numbers

**Scalabrino, S., Bavota, G., Vendome, C., Linares-Vásquez, M., Poshyvanyk, D. & Oliveto, R. "Automatically Assessing Code Understandability." IEEE TSE (2021; accepted 2019).** PDF <https://www.cs.wm.edu/~denys/pubs/TSE'19-Understandability.pdf> · ASE 2017 precursor <https://www.cs.wm.edu/~denys/pubs/ASE'17-Readability.pdf>

**(a) measured.** **121 metrics** — code (cyclomatic complexity, nested blocks, #parameters, #statements, Buse & Weimer readability features, LOC, token entropy, Halstead volume, Dorn's visual features, textual coherence), documentation, and developer-experience metrics — against **444 human evaluations from 63 developers** on **50 Java/Android methods** from 10 systems. Six understandability proxies (perceived, timed, actual correctness, deceptiveness).

**(b) results, verbatim:** "**Very few metrics have a correlation with understandability higher than |0.1|.** […] **51 out of the 73 metrics considered showed no correlation at all with any of the proxies.**"
Best single correlations (Kendall τ) are all ≈0.11–0.16, and one has the wrong sign (textual coherence vs actual understanding τ ≈ **−0.16**).
**RQ1 summary, verbatim: "None of the metrics we considered achieve a medium/strong correlation with any of the proxies of code understandability we defined."**
Models: classification AUC 0.69–0.72 but F-measures "not useful in practice"; regression for time-to-understand max correlation **0.18** with MAE 115–147 s against a mean of 143.4 s — "**practically useless**."
**Conclusion, verbatim: "the metrics we investigated are not enough to capture code understandability."** Interviews with 5 professionals found developers *believe* readability drives understandability — "**this contradicts our quantitative results.**"

**Contested by**: Trockman et al., "'Automatically assessing code understandability' reanalyzed," MSR 2018, <https://dl.acm.org/doi/10.1145/3196398.3196441> — LASSO on combined features got **AUC 0.64**; small but significant.

#### 2020–2026: the LLM era

**Peer-reviewed:**
- **Code review effort (FSE 2024)**: "An Empirical Study on Code Review Activity Prediction and Its Impact in Practice," *Proc. ACM Softw. Eng.* <https://dl.acm.org/doi/10.1145/3660806> · <https://arxiv.org/abs/2404.10703>. Median wait for review feedback **15–64 hours**. Review effort is driven by the patch and by author/reviewer experience — process, not intrinsic complexity.
- **Sepidband, M., Taherkhani, H., Wang, S. & Hemmati, H. (2025). "Enhancing LLM-Based Code Generation with Complexity Metrics: A Feedback-Driven Approach."** <https://arxiv.org/abs/2505.23953>. Uses logistic regression on complexity metrics to predict whether generated code passes tests, then feeds that back into generation: GPT-3.5-Turbo Pass@1 on HumanEval **+35.71%**; BigCodeBench **+20%** (GPT-4o), **+23.07%** (o3-mini). ⚠️ **Could not verify** the underlying correlation coefficients or which metrics were most predictive — the abstract does not publish them.
- **Benchmark-dependence caveat (2025)**: "Where Do LLMs Still Struggle?" <https://arxiv.org/html/2511.04355v1> — **LiveCodeBench shows a positive correlation between code complexity and failure rate, while other benchmarks do not.** Treat "complexity predicts LLM failure" as benchmark-contingent, not established.

**Preprints (not peer reviewed):**
- **"A Large-Scale Empirical Study of AI-Generated Code in Real-World Repositories"** (arXiv:2603.27130v2, Apr 2026) <https://arxiv.org/html/2603.27130v2>. **12,749 commits / 19,816 AI-generated files** vs **36,467 human files**. AI files: **256.57 vs 192.68 physical LOC**; **+2.61 statements per function**, deeper nesting; lexical density **0.531 vs 0.692**; **cross-file duplication 17.20% (AI) vs 24.52% (human)** — i.e. *lower*, contradicting the vendor narrative; static-analysis alerts **12.81 vs 11.58 per KLOC**; high-risk security alerts **0.934 vs 0.464 per KLOC**; commits smaller (92.85 vs 344.64 files) but **stabilisation time 0.658 vs 0.035 days**.
- **"Debt Behind the AI Boom"** (arXiv:2603.28592, Mar 2026) <https://arxiv.org/html/2603.28592v1>. **304,362 verified AI-authored commits across 6,275 repos**, five assistants. **484,606 distinct issues introduced** (code smells 89.1%, runtime bugs 5.8%, security 5.1%); **>15% of commits from every tool introduce at least one issue**; **24.2% of AI-introduced issues survive at HEAD**; **security issues most persistent at 41.1% survival**; AI is net-negative on code smells but **introduces nearly 2× as many security issues as it fixes**.
- **★ "Early-Stage Prediction of Review Effort in AI-Generated Pull Requests," MSR '26** <https://arxiv.org/html/2601.00753>. AIDev v1.0: **33,707 agent-authored PRs across 2,807 repos**. LightGBM **AUC 0.958** temporal / **0.8345 repo-disjoint** (CodeBERT semantic baseline: **AUC 0.52**). At a 20% review budget it captures **69% of high-effort PRs**. **The dominant features are structural size metadata — additions, deletions, changed files, total_changes.** A size-only baseline gets AUC 0.93 temporally but collapses to 0.65 repo-disjoint. **28.3% of agent PRs merge instantly.**
  **This is a straight replication of the 2013 lesson in the agent era: cheap change-shape signals beat expensive semantic analysis.**

**Vendor reports — explicitly NOT peer reviewed:**
- **GitClear, "Coding on Copilot" (2024)** <https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality>. **~153 million changed lines**, Jan 2020–Dec 2023. Defines churn as "the percentage of lines that are reverted or updated less than two weeks after being authored"; claims churn would **double in 2024** vs the 2021 pre-AI baseline. ⚠️ Repos undisclosed.
- **GitClear, "AI Copilot Code Quality: 2025"** <https://www.gitclear.com/ai_assistant_code_quality_2025_research>. **211 million changed lines**, Jan 2020–Dec 2024. Claims copy/pasted lines rose **8.3% (2021) → 12.3% (2024)**; refactored/moved code fell from ~25% to <10%; 2024 the first year copy/paste exceeded moved code. ⚠️ **Internal inconsistency**: the headline says "4× growth in code clones" and coverage says duplicated blocks rose **eightfold**, but the published figures (8.3%→12.3%) are ~1.48×. **Do not cite the 4×/8× figures without the underlying definition.** The *direction* also contradicts arXiv:2603.27130.
- **DORA 2024** <https://dora.dev/research/2024/dora-report/>. "a drop in throughput (**1.5%**) and stability (**7.2%**)" where AI had been adopted; **39%** report low or no trust in AI-generated code. ⚠️ **Could not verify** the widely-repeated "per 25% increase in AI adoption" conditioning.
- **DORA 2025, *State of AI-assisted Software Development*** <https://dora.dev/insights/balancing-ai-tensions/>. ~5,000 professionals. **90% use AI at work**; **>80% believe it increased productivity**; **30%** report little or no trust (down from 39%). **The 2024 direction reversed**: "we observe a **positive** relationship between AI adoption on both software delivery throughput and product performance" — but AI adoption "does continue to have a **negative** relationship with software delivery stability." ⚠️ No effect sizes published.

#### What section 6 supports, and what it doesn't

**Well supported across independent industrial and OSS datasets:**
1. **Change history beats code structure for predicting defects.** Nagappan & Ball 2005 (R² 0.81 vs 0.05, 45 MLOC of Windows); Rahman & Devanbu 2013 (p<0.001, all learners, all measures); Majumder & Menzies 2022 (AUC 95% vs 54%, 700 projects).
2. **Absolute counts are near-useless; normalised/relative measures work.**
3. **The mechanism is stasis.** Code metrics have stasis ≈0.96 between releases — they cannot track a moving defect distribution, so models stagnate onto big, low-density files.
4. **Who touched the code beats what the code looks like.** `Minor` (contributors with <5% ownership) correlates 0.86–0.93 with failures, higher than any metric Microsoft collects, and roughly doubles explained variance *on top of* size, churn and complexity.
5. **Cyclomatic complexity specifically has no measurable relationship to human comprehension.** Peitek (fMRI): τ ≈ −.09/.06/−.07/.04 while LOC reaches −.46. Scalabrino: not one of 121 metrics reliably reaches |0.1|; 51 of 73 correlate with nothing.
6. **Complexity metrics add little over LOC.** Herraiz & Hassan's conclusion; Rahman & Devanbu's "process + size ≈ process alone"; Borg et al.'s LoC baseline beating SonarQube's debt ratio (§4.5).

**Genuinely contested:**
- **Cognitive Complexity** is the one code-only metric with meta-analytic support (r = 0.54 with comprehension *time*), but r = −0.13 with correctness and ~0.00 with fMRI cognitive load. It measures **how long**, not **whether you get it right**.
- Whether AI-generated code is more or less duplicated: GitClear (vendor) says sharply up; arXiv:2603.27130 (preprint, cross-file measure) says AI duplicates *less* than humans. Different units, different corpora, unresolved.
- DORA reversed its own 2024 throughput finding in 2025. Stability stayed negative in both years.

**Folklore the literature does not support:**
- *"High cyclomatic complexity means hard-to-maintain code."* No measured link to comprehension effort in Scalabrino, Peitek, Feigenspan, or Herraiz & Hassan.
- *"A complexity threshold (10, 15, …) is a quality gate."* No study validates any threshold value. Muñoz Barón et al. say it outright: "**we do not know at what metric value a section of code can be considered too complex.**"
- *"Pick the right classifier / metric suite and defect prediction works."* Shepperd et al.: classifier explains **1.3%** of variance, metric family **5.2%**, researcher identity **31.0%**.
- *"More developers on a component means more bugs."* True but imprecise — it is specifically the **<5%-ownership** contributors; `Major` count is marginal and sometimes negative.

---

## Cross-cutting conclusions

1. **The threshold of 10 has no empirical parent.** McCabe 1976 calls it "reasonable, but not magical"; NIST SP 500-235's claim of "significant supporting evidence" is uncited in its own text. Anyone defending 10 is defending a 50-year-old departmental policy.
2. **The CC≈SLOC redundancy claim is real at file/project aggregation and false at unit level.** Landman et al.: R² = 0.40 (Java) / 0.44 (C) per unit; 0.73/0.70 summed per file; 0.90 with a log transform on top. The famous "~0.9" from Jay et al. 2009 is a **log–log, file-level, repeated-median** figure. Aggregating or log-transforming a complexity metric turns it into a size metric — **the redundancy critique is an artefact of the unit of analysis.** Gate per unit and CC is not redundant; report a project total and it is.
3. **Averaging any complexity metric destroys its signal**, because unit complexity is power-law distributed. This is the shared root cause of MI's failure and of "average CC" dashboards being useless.
4. **The best-evidenced practical model measures a distribution against a benchmark percentile**, at three nested severity levels, LOC-weighted — SIG/TÜViT. Current published 4-star thresholds are in §2.4.
5. **Nothing in the static-metric literature reliably predicts human comprehension, and cyclomatic complexity is the *worst* of the candidates.** Scalabrino et al.: none of 121 metrics reaches |0.1| reliably; 51 of 73 correlate with nothing. Peitek et al. (fMRI): McCabe's τ is −.09 with correctness, .06 with time, .04 with cognitive load — while **LOC reaches −.46 and Halstead −.45**. Cognitive Complexity is the one partial survivor (r ≈ 0.54 with comprehension *time*, but −0.13 with *correctness*, I² = 85%).
6. **Process metrics beat product metrics, replicated three times at increasing scale.** Nagappan & Ball 2005 (R² 0.81 relative churn vs 0.05 absolute, 45 MLOC Windows); Rahman & Devanbu 2013 (p<0.001 across 85 releases); Majumder & Menzies 2022 (**AUC 95% vs 54%**, 700 projects). The mechanism is **stasis**: code metrics barely change between releases (ρ ≈ 0.96), so models built on them stagnate onto big, low-defect-density files — the worst use of a review budget.
7. **Who touched the code beats what the code looks like.** Bird et al.: the count of **minor contributors (<5% ownership)** correlates 0.86–0.93 with failures — higher than any metric Microsoft collects — and roughly doubles explained variance on top of size, churn *and* complexity.
8. **Every threshold in the field is a chosen constant, and they disagree by 4×.** McCabe's 10 ("reasonable, but not magical"), SonarQube's cognitive-complexity 15 (no derivation anywhere), SonarQube's 0.06 days/LOC (contradicts its own 30-minute source constant by 4%), CISQ's CC 20, Alves' benchmark-derived 6, SIG's 2025 benchmark-derived 5. Only the last two were derived from data, and they are *relative* — "this is where the 70th percentile of real code sits", not "this is too complex".
9. **Ratio-based debt gates fail in a specific, predictable way: the denominator.** Borg et al. (ICSME 2024): SonarQube's TD Ratio at its default 0.05 scores **AUC 0.60** against 519 expert-labelled files — **worse than random for liability detection, and beaten by a plain 275-line LoC threshold (AUC 0.95)** — because a tiny file with three trivial smells becomes "major debt" purely from a small denominator.
10. **The vendors themselves have moved to ratchets.** SonarSource's own recommended quality gate contains **no** debt-ratio condition and its docs say "we do not recommend adding conditions for overall code to your quality gate." Google's Tricorder gates only the change under review after whole-codebase bug-filing failed (**84% of filed bugs never fixed**). This is the best-evidenced *shape* for a gate, even though ratcheting itself has no peer-reviewed evaluation.

### If you want the three-line version

- **Do not gate on a per-unit cyclomatic complexity cap.** The threshold has no empirical parent, the metric has no measured relationship to human comprehension, and every tool picks a different number.
- **If you gate on code structure at all, gate on the *distribution*** — "no more than X% of code sits above complexity Y", at three nested severity levels, LOC-weighted, with boundaries derived from your own benchmark percentiles (the SIG/Alves method). Keep a size metric beside it to catch large-but-simple units.
- **The strongest available signal is not in the code at all.** Churn normalised by size, change scattering, and minor-contributor count outperform every static metric tested, in every study, at every scale. If effort is the thing you care about, gate quality **where churn is high** (Borg et al. 2024's own recommendation) rather than uniformly.

---

## Appendix: claims I could NOT verify

| Claim | Status |
|---|---|
| Jay/Graylin et al. 2009's own corpus and R² figures from the primary text | SCIRP returned HTTP 403; **reconstructed from Landman et al.'s Table I** (file-level, log–log, 2,200 SourceForge projects, R² 0.78/0.83/0.73 → 0.87/0.93/0.97 after repeated-median regression) |
| ISO/IEC 25023 measure definitions | Paywalled; taken from secondary summaries |
| Better Code Hub's exact per-guideline thresholds | Service discontinued, docs unreachable; use SIG/TÜViT v17.0 instead |
| O'Reilly *Building Maintainable Software* Appendix A | HTTP 403 |
| Sjøberg, Anda & Mockus (2012) primary text | ACM 403; via van Deursen's summary only |
| "Reflections on McCabe's Cyclomatic Complexity" (2025) authors and conclusions | Paywalled |
| Alves 2010's McCabe 90th-percentile threshold: 14 or 15? | **Both figures appear in SIG materials**; different benchmark snapshots, unresolved |
| The 5/10/20/50% SQALE A–E grid attributed to Letouzey | Letouzey's own deck shows the chart with **no numbers**; verified only as SonarQube's operationalisation |
| SonarQube "0.06 days" vs source constant "30 minutes" | **Both verified, and they disagree by 4%** (30 min = 0.0625 days at an 8-hour day) |
| SonarQube cognitive-complexity default of 25 for C/C++/ObjC | Could not verify from a SonarSource primary source (15 for Java **is** verified in source) |
| Bouwers/Visser/van Deursen "Getting What You Measure" verbatim wording | All three URLs 403; pitfall names from search excerpts |
| Austin (1996) full-vs-partial supervision exact phrasing | Not verified from primary source |
| Strathern 1997 page-precise quotation | PDFs are image/JBIG2-encoded; quote as universally reported |
| Nagappan & Ball adjusted R² "0.49" vs 0.049 | Printed as 0.49 directly after R² = 0.052; **almost certainly a typo**, unresolved |
| Herraiz & Hassan's numeric coefficients (~200k Arch Linux files, LOC↔CC +0.72, LOC↔Halstead +0.91) | **Unverified** — from a search summary, not the chapter. The *qualitative* conclusion is verified by direct quotation |
| Fenton & Neil 1999 internal figures | Full text not obtained |
| Menzies 2007 pd=71%/pf=25% | From the abstract, not extracted from the PDF |
| DORA 2024's "per 25% increase in AI adoption" conditioning | **Unverified**; the 1.5%/7.2% figures are verified via a reputable secondary source |
| GitClear's "4× / 8× growth in code clones" | **Internally inconsistent** with their own published 8.3%→12.3% (≈1.48×); unit undefined. Do not cite |
| Sepidband et al. 2025 complexity↔LLM-success correlation coefficients | Not published in the abstract |
