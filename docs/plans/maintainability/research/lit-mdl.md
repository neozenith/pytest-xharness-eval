# Minimum description length and Kolmogorov complexity: source material for a reviewability score

Research date: 2026-09-03.
Web and literature only.
No claim here rests on this repository's code.

**Reading key.** Every claim carries one of three tags.

- **(a) proves**, what the cited source formally establishes, as a theorem or a measurement.
- **(b) claims**, what its authors assert informally, in prose, without proof in that paper.
- **(c) my reading**, my own inference or transfer to the reviewability problem.
  Not sourced.

Where a source could not be opened or a number could not be confirmed from the primary text, it says **could not verify**.

**Sources actually opened.** I read the full text of Grünwald's MDL tutorial, Grünwald and Vitányi's algorithmic information theory chapter, Vereshchagin and Vitányi's structure-function paper, Cilibrasi and Vitányi's compression paper, Hindle et al.'s naturalness paper, Koppel's sophistication paper, and Antunes et al.'s sophistication-versus-depth paper.
Bibliographic records were resolved against Crossref, Project Euclid, OpenAlex and the authors' own publication listings.
Akaike (1974), Rissanen (1978), Schwarz (1978), Bennett (1988) and the Li and Vitányi textbook are cited from records and from secondary quotation, not from the primary text.
Every place that matters is flagged.

---

## Table of contents

1. [Kolmogorov complexity](#1-kolmogorov-complexity)
2. [Minimum description length](#2-minimum-description-length)
3. [AIC, BIC and how they relate to MDL](#3-aic-bic-and-how-they-relate-to-mdl)
4. [The bridge to software](#4-the-bridge-to-software)
5. [The counter-argument: why shortest is not most reviewable](#5-the-counter-argument-why-shortest-is-not-most-reviewable)
6. [Formula sheet](#6-formula-sheet)
7. [Bibliography](#7-bibliography)
8. [Could not verify](#8-could-not-verify)

---

## 1. Kolmogorov complexity

### 1.1 The three independent formulations

The same quantity was invented three times, by three people, for three different reasons.
Grünwald and Vitányi state the attribution directly.

> "[The theory] was invented with different motivations by R.J. Solomonoff (born 1926), A.N. Kolmogorov (1903–1987) and G. Chaitin (born 1943) in 1960/1964, 1965 and 1966 respectively."
> — Grünwald and Vitányi (2008), §1, p. 2

**Solomonoff.** Two reports and then a two-part journal paper.
The reports are the primary 1960 statement, and both are listed on Solomonoff's own publication index.

- Solomonoff, R.J.
  (1960). *A Preliminary Report on a General Theory of Inductive Inference.* Report V-131, Zator Co., Cambridge, Mass., 4 February 1960.
  Contract AF 49(639)-376.
- Solomonoff, R.J.
  (1960). *A Preliminary Report on a General Theory of Inductive Inference.* Report ZTB-138 (revision of V-131), Zator Co., Cambridge, Mass., November 1960.
- Solomonoff, R.J.
  (1964).
  "A Formal Theory of Inductive Inference.
  Part I." *Information and Control* 7(1):1–22.
  DOI [10.1016/S0019-9958(64)90223-2](https://doi.org/10.1016/S0019-9958(64)90223-2)
- Solomonoff, R.J.
  (1964).
  "A Formal Theory of Inductive Inference.
  Part II." *Information and Control* 7(2):224–254.
  DOI [10.1016/S0019-9958(64)90131-7](https://doi.org/10.1016/S0019-9958(64)90131-7)

Solomonoff's motivation was **prediction**, not description.
He wanted a universal prior over sequences so that induction could be formalised.
Shortest-program length fell out of that as the object he needed.

**Kolmogorov.** One short paper, motivated by wanting a definition of information that applies to an *individual* object rather than to a distribution.

- Kolmogorov, A.N.
  (1965).
  "Three approaches to the quantitative definition of information." *Problems of Information Transmission* 1(1):1–7.
  (Russian original: *Problemy Peredachi Informatsii* 1(1):3–11.)

**Chaitin.** Motivated by randomness and by what a machine can prove about its own outputs.

- Chaitin, G.J.
  (1966).
  "On the Length of Programs for Computing Finite Binary Sequences." *Journal of the ACM* 13(4):547–569.
  DOI [10.1145/321356.321363](https://doi.org/10.1145/321356.321363)

**(c) my reading.** The three motivations are worth keeping separate when transferring to code.
Solomonoff's question is "what will the next token be", which is the naturalness literature in §4.
Kolmogorov's question is "how much structure does *this one artefact* have", which is the reviewability question.
Chaitin's question is "what can be proved", which is where the uncomputability wall in §1.4 comes from.

### 1.2 The reference textbook

- Li, M. and Vitányi, P.M.B. *An Introduction to Kolmogorov Complexity and Its Applications.* Springer.
  - 1st edition, 1993.
  - 2nd edition, 1997 (Graduate Texts in Computer Science).
    This is the edition cited as "[Li and Vitányi 1997]" throughout Grünwald and Vitányi (2008).
  - 3rd edition, 2008.
  - 4th edition, 2019, Texts in Computer Science, ISBN 978-3-030-11297-4 (print) / 978-3-030-11298-1 (ebook).
    DOI [10.1007/978-3-030-11298-1](https://doi.org/10.1007/978-3-030-11298-1)

The edition matters when chasing theorem numbers.
Grünwald and Vitányi cite "Theorem 3.9.1 in [Li and Vitányi 1997]" for additivity of complexity, and that number is edition-specific.

### 1.3 The definition and the invariance theorem

**Definition.** *K(x)* is the length in bits of the shortest program that, run on a fixed universal (prefix) Turing machine with no input, prints *x* and then halts.

**The invariance theorem, (a) proves.** Stated by Grünwald and Vitányi (2008), §2, equation (6):

> "for any two universal languages L₁ and L₂, letting K₁ and K₂ denote the respective complexities, for all x of each length,
> |K₁(x) − K₂(x)| ≤ C,
> where C is a constant that depends on L₁ and L₂ but not on x or its length."

Read the quantifier order carefully, because it is the whole content of the theorem.
The constant is chosen **after** the pair of machines and **before** the string.
One constant covers every string, of every length, forever.

**The proof, in one line.** There is a compiler.
Grünwald and Vitányi give it concretely.

> "let Λ be a program in L₁ implementing a compiler translating from L₂ to L₁. […] It follows that K_LISP(x) ≤ l(Λ) + l(p) + l(y) ≤ K_Java(x) + O(1), where O(1) is the size of Λ. By symmetry, we also obtain the opposite inequality."
> — Grünwald and Vitányi (2008), §2

**What invariance does not give you, (a) proves, stated by the same authors.**

> "Since we allow any universal language in the definition of K, K(x) is only defined up to an additive constant. This means that the theory is inherently asymptotic […] A statement such as K(a) = b is not very meaningful."
> — Grünwald and Vitányi (2008), §2

**(c) my reading, and this is the single most important caveat for a reviewability score.** Invariance licenses statements of the form "this family of artefacts has description length growing like *f(n)*".
It does not license "this pull request scores 4,182".
A per-diff absolute number has no invariant meaning at all.
Comparisons between two artefacts are meaningful only when their sizes are large relative to the machine constant, and a code review diff is small.

### 1.4 Uncomputability

**(a) proves.** *K* is not a recursive function.

> "Unfortunately K(x) is not a recursive function: the Kolmogorov complexity is not computable in general. This means that there exists no computer program that, when input an arbitrary string, outputs the Kolmogorov complexity of that string and then halts."
> — Grünwald and Vitányi (2008), §2

**The proof, verbatim from Example 3 of that chapter.** This is the Berry-paradox argument made precise.

> "let us assume by means of contradiction that K is computable. Then the function ψ(m) := min_{x∈ℕ}{x : K(x) ≥ m} must be computable as well […] The definition of ψ immediately implies K(ψ(m)) ≥ m. On the other hand, since ψ is computable, there exists a computer program of some fixed size c such that, on input m, the program outputs ψ(m) and halts. Therefore […] we must have that K(ψ(m)) ≤ L_ℕ(m) + c ≤ 2 log m + c. Thus, we have m ≤ 2 log m + c which must be false from some m onwards: contradiction."
> — Grünwald and Vitányi (2008), §4, Example 3

The English of it: "the smallest number that needs at least *m* bits to describe" is itself describable in about *log m* bits, once you can compute *K*.
Richard-Berry, exactly.
Grünwald and Vitányi name the paradox explicitly at §4.1 and note it "does not disappear, but resurfaces in the form of an alternative approach to proving Gödel's famous result".

**What you get instead, (a) proves.** *K* is upper semicomputable.
You can compute a descending sequence of over-estimates that converges to *K(x)*, but you can never know you have arrived.

> "while the approximating algorithm with input x successively outputs better and better approximations t₁ ≥ t₂ ≥ t₃ ≥ … to K(x), it is (a) excessively slow, and (b), it is in general impossible to determine whether the current approximation tᵢ is already a good one or not. In the words of Barron and Cover [1991], (eventually) 'You know, but you do not know you know'."
> — Grünwald and Vitányi (2008), §2

**The sanctioned escape hatch, (b) claims, by the same authors.**

> "we take some existing data compression program C (for example, gzip) that allows every string x to be encoded and decoded computably and even efficiently. We then approximate K(x) as the number of bits it takes to encode x using compressor C. For many compressors, one can show that for 'most' strings x in the set of all strings of interest, C(x) ≈ K(x)."
> — Grünwald and Vitányi (2008), §2

Note the hedges: "most", "in the set of all strings of interest".
This is an informal claim in a survey, not a theorem about your corpus.

**(c) my reading.** Uncomputability is not a footnote you can wave past.
It is the reason every practical instrument in §4 is a *compressor* or a *language model*, and it is the reason you must state which one you used.
Two compressors disagree.
A reviewability score built on `gzip` and a reviewability score built on a transformer are different measurements, and neither is *K*.

### 1.5 Conditional complexity and algorithmic mutual information

This is the part that maps directly onto "how much of this diff do I already know".

**Conditional complexity.** *K(x | y)* is the length of the shortest program that, given *y* as input, outputs *x* and halts.
Cilibrasi and Vitányi state it plainly.

> "Technically, the Kolmogorov complexity of x given y is the length of the shortest binary program that on input y outputs x; it is denoted as K(x|y). […] The Kolmogorov complexity of x is the length of the shortest binary program with no input that outputs x; it is denoted as K(x) = K(x|ε) where ε denotes the empty input."
> — Cilibrasi and Vitányi (2005), Remark 3.1

**Additivity of complexity, (a) proves, due to Gács (1974).**

> K(x,y) =⁺ K(x) + K(y | x*) =⁺ K(y) + K(x | y*)
> — Grünwald and Vitányi (2008), §5.4, equation (19)

Here *x\** is the first shortest prefix program that generates *x* and halts, and `=⁺` means equality to within an additive constant.
The starred conditional matters.
Grünwald and Vitányi warn:

> "the version with just x and y in the conditionals doesn't hold with =⁺, but holds up to additive logarithmic terms that cannot be eliminated."

**Algorithmic mutual information, (a) proves, definition and symmetry.**

> "The information in y about x is defined as
> I(y : x) = K(x) − K(x | y*) =⁺ K(x) + K(y) − K(x,y),
> where the second equality is a consequence of (19) and states that this information is symmetric, I(x : y) =⁺ I(y : x), and therefore we can talk about mutual information."
> — Grünwald and Vitányi (2008), §5.4, equation (20)

The symmetry is the surprising part.
For Shannon mutual information, symmetry falls out of averaging.
Here it holds for *individual objects*, with no distribution anywhere, and Grünwald and Vitányi call the underlying additivity result "quite remarkable" with "a difficult proof".

**(c) my reading, the reviewability translation.** Let *d* be the diff and *R* be everything the reviewer already holds: the repository before the change, the conventions, the idioms, the reviewer's own prior code.
Then the honest quantity for "how much new is here" is *K(d | R)*, not *K(d)*.
A 500-line diff that is five instances of an idiom the codebase already uses has small *K(d | R)* and large *K(d)*.
A 20-line diff introducing a genuinely new invariant has the reverse profile.
Algorithmic mutual information *I(R : d) = K(d) − K(d | R\*)* is the formal name for "the part of this diff you did not have to be told".
This is the cleanest theoretical justification I found for scoring a change *relative to its repository* rather than in isolation.
It is my transfer, not anyone's published result.

---

## 2. Minimum description length

### 2.1 The founding paper

- Rissanen, J.
  (1978).
  "Modeling by shortest data description." *Automatica* 14(5):465–471.
  DOI [10.1016/0005-1098(78)90005-5](https://doi.org/10.1016/0005-1098(78)90005-5)

Crossref confirms volume 14, issue 5, pages 465–471, published September 1978.
Its own reference list cites Kolmogorov and Akaike, which fixes the intellectual lineage.

**Historical note, (b) claims, from Grünwald.**

> "While Rissanen was not aware of Solomonoff's work at the time, Kolmogorov […] Another important inspiration for Rissanen was Akaike's [1973] AIC method […] Even though Rissanen was inspired by AIC, both the actual method and the underlying philosophy are quite different."
> — Grünwald (2004), §1.5

### 2.2 The two-part code, stated precisely

Grünwald's statement of what he calls the *crude* two-part MDL principle, verbatim.

> **Crude, Two-part Version of MDL Principle**
> Let H⁽¹⁾, H⁽²⁾, … be a set of candidate models. The best point hypothesis H ∈ H⁽¹⁾ ∪ H⁽²⁾ ∪ … to explain data D is the one which minimizes the sum L(H) + L(D|H), where
> • L(H) is the length, in bits, of the description of the hypothesis; and
> • L(D|H) is the length, in bits, of the description of the data when encoded with the help of the hypothesis.
> The best model to explain D is the smallest model containing the selected H.
> — Grünwald (2004), §2.4, p. 34

**Definition of the second term, (a) proves it is forced, not chosen.** Each hypothesis *H* is a probability distribution *P(· | H)* on the sample space, and the code length is fixed to be the log-loss:

> L(xⁿ | H) = − log P(xⁿ | H)

Grünwald gives two reasons and then a consistency argument that this is "in a sense, the only reasonable choice".
If you assign code lengths some other way, there exists a pair of distributions on which two-part MDL becomes *inconsistent*: it selects the wrong one for arbitrarily large *n* (Grünwald 2004, §2.4.1).

**Definition of the first term, this is where crude MDL is genuinely under-determined.**

> "In its weakest and crudest form, the two-part code MDL Principle does not give any guidelines as to how to encode hypotheses (probability distributions). Every code for encoding hypotheses is allowed, as long as such a code does not change with the sample size n."
> — Grünwald (2004), §2.4.2, p. 35

The one hard constraint is that *L(H)* must not depend on *n*.
Grünwald shows why with a Markov-chain counterexample: if you may re-choose the code per sample size, MDL collapses to maximum likelihood and overfits at every *n*.

**Consistency of crude two-part MDL, (a) proves, with a caveat.**

> "if we fix an arbitrary code for all hypotheses, identical for all sample sizes n, this is sufficient to make MDL consistent for a wide variety of models […] with probability 1 there exists some n₀ such that for all samples larger than n₀, two-part MDL will select P* — here n₀ may depend on P* and L."
> — Grünwald (2004), §2.4.2

And immediately the honest limitation:

> "While this result indicates that MDL may be doing something sensible, it certainly does not justify the use of arbitrary codes — different codes will lead to preferences of different hypotheses, and it is not at all clear how a code should be designed that leads to good inferences with small, practically relevant sample sizes."

**(c) my reading.** A "reviewability = L(model) + L(residual)" score inherits exactly this defect.
Whatever you choose as the encoding of the *model* (the abstractions, the names, the types, the structure a reviewer must load) is an arbitrary choice, and different choices rank different diffs first.
The asymptotic consistency result gives you nothing at diff scale.
Section 2.4 is what the field did about that.

### 2.3 The universal prior for integers

- Rissanen, J.
  (1983).
  "A Universal Prior for Integers and Estimation by Minimum Description Length." *The Annals of Statistics* 11(2):416–431.
  DOI [10.1214/aos/1176346150](https://doi.org/10.1214/aos/1176346150)

Page range 416–431 confirmed from Project Euclid.

**(b) claims, from the abstract as rendered by Project Euclid.** The paper reformulates estimation as "minimization of the number of bits required to write down the observed data", extending maximum likelihood.
It permits simultaneous estimation of parameter values, the number of parameters, and the model structure.
Its contribution is a universal prior over integers that works even when parameters are individual objects, with real-valued parameters discretised by their precision and the precision itself optimised.

**(c) my reading.** This is the paper that supplies a principled *L(H)* where 1978 left it open, at least for parameter counts.
The cost of "one more parameter" becomes the code length of an integer under the universal prior, roughly `log*` of it, rather than an arbitrary choice.

### 2.4 Refined MDL: stochastic complexity, parametric complexity, NML

The 1978 formulation left *L(H)* free.
Refined MDL closes that hole by abandoning the two-part split and using a single *universal code* for the whole model class.

**Stochastic complexity and parametric complexity, in Grünwald's words.**

> "the codelength L̄(D | H). L̄(D | H) is called the stochastic complexity of the data given H […] The second fundamental concept of refined MDL is the parametric complexity of a parametric model H which we denote by COMP(H). […]
> stochastic complexity of D given H = L(D | Ĥ) + COMP(H)."
> — Grünwald (2004), §1.4

So the one-part code decomposes, after the fact, into a fit term and a complexity term.

**Parametric complexity, the definition (Grünwald 2004, equation 2.17).**

> COMP_n(M) = log Σ_{xⁿ ∈ 𝒳ⁿ} P(xⁿ | θ̂(xⁿ))

Here θ̂(xⁿ) is the maximum-likelihood parameter for the sequence *xⁿ*.
Grünwald's intuition for why this is a complexity: "the more sequences that can be fit well by an element of M, the larger COMP_n(M)".

**The NML (Shtarkov) distribution, (a) proves, Proposition 2.14 of Grünwald (2004), attributed to Shtarkov (1987).**

> "Suppose that COMP_n(M) is finite. Then the minimax regret (2.16) is uniquely achieved for the distribution P̄_nml given by
> P̄_nml(xⁿ) := P(xⁿ | θ̂(xⁿ)) / Σ_{yⁿ ∈ 𝒳ⁿ} P(yⁿ | θ̂(yⁿ))."

The proof is two lines: plug it in, observe that the regret equals COMP_n(M) *for every* xⁿ, and note any other distribution must be smaller somewhere and so does worse in the worst case.
The property that makes NML canonical is that its regret is **constant**, the same excess code length no matter what data arrives.

**The asymptotic expansion, (a) proves, under regularity conditions.** Grünwald (2004) equation (2.21), attributed to Rissanen (1996) and Takeuchi and Barron (1997, 1998, 2000):

> COMP_n(M) = (k/2) · log(n / 2π) + log ∫_Θ √|I(θ)| dθ + o(1)

Symbols, verbatim from the text following the equation:

- *k*: "the number of parameters (degrees of freedom) in model M".
- *n*: "the sample size".
- *|I(θ)|*: "the determinant of the k × k Fisher information matrix I evaluated at θ".
- *o(1)*: "→ 0 as n → ∞".

The conditions are listed explicitly and are not decorative: COMP_n(M) and ∫√|I(θ)| dθ both finite, θ̂(xⁿ) staying away from the boundary of Θ, and *M* being (or asymptotically behaving like) an exponential family.

Grünwald then sets a boxed warning in the text:

> **"The Asymptotic Expansion of COMP_n Should Be Used with Care!"**
> "(2.21) does not hold for all parametric models; and for some models for which it does hold, the o(1) term may only converge to 0 only for quite large sample sizes. Foster and Stine [1999, 2004] show that the approximation (2.21) is, in general, only valid if k is much smaller than n."
> — Grünwald (2004), §2.6.2

**The optimal two-part code, for comparison, (a) proves, from Barron and Cover (1991) as adapted by Grünwald.**

> −log P̄₂₋ₚ(xⁿ | M) + log P(xⁿ | θ̂(xⁿ)) = (k/2) log(n/2π) + log ∫_{θ∈Θ} √|I(θ)| dθ + f(k) + o(1)

with *f* bounded, positive, and *f(k) → 0* as *k → ∞*.
Grünwald's reading:

> "for large k, optimally designed two-part codes are about as good as NML. The problem with two-part code MDL is that in practice, people often use much cruder codes with much larger minimax regret."

**(c) my reading.** This is the honest verdict on "should I build a two-part reviewability score or a one-part one".
A *well-designed* two-part code is nearly optimal.
The failure mode is not the two-part shape, it is that hand-rolled model codes are bad.
If you build a two-part reviewability score, the whole risk sits in how you price the model half.

### 2.5 The modern reference, and MDL without a true model

- Grünwald, P.D.
  (2007). *The Minimum Description Length Principle.* MIT Press.
  DOI [10.7551/mitpress/4643.001.0001](https://doi.org/10.7551/mitpress/4643.001.0001)
- Grünwald, P.D.
  (2004).
  "A tutorial introduction to the minimum description length principle." arXiv:[math/0406077](https://arxiv.org/abs/math/0406077). 80 pages, two chapters.
  This is the open-access text I read and quote throughout; it is the precursor to chapters of the 2007 book.
- Hansen, M.H. and Yu, B.
  (2001).
  "Model Selection and the Principle of Minimum Description Length." *Journal of the American Statistical Association* 96(454):746–774.
  DOI [10.1198/016214501753168398](https://doi.org/10.1198/016214501753168398)

**The framing, (b) claims, and it is the philosophical core.**

> "Many (but not all) other methods of inductive inference are based on the idea that there exists some 'true state of nature' […] According to Rissanen, such methods are fundamentally flawed. The main reason is that the methods are designed under the assumption that the true state of nature is in the assumed model H, which is often not the case. Therefore, such methods only admit a clear interpretation under assumptions that are typically violated in practice. […] In contrast, MDL has a clear interpretation which depends only on the data, and not on the assumption of any underlying 'state of nature'."
> — Grünwald (2004), §1.3, item 3, "We Have Only the Data"

And on noise:

> "According to the MDL philosophy, such a phrase [these data are quite noisy] means only that the data are not compressible with the currently hypothesized model — as a matter of principle, it can never be ruled out that there exists a different model under which the data are very compressible (not noisy) after all!"
> — Grünwald (2004), §1.3

**Consistency is a sanity check, not a design goal, (b) claims.**

> "consistency is important in the MDL philosophy, but it is used as a sanity check (for a method that has been developed without making distributional assumptions) rather than as a design principle."
> — Grünwald (2004), §1.3, item 4

**On Occam's razor, (b) claims, and worth quoting because it pre-empts an obvious objection.**

> "When two models fit the data equally well, MDL will choose the one that is the 'simplest' in the sense that it allows for a shorter description of the data. As such, it implements a precise form of Occam's Razor — even though as more and more data becomes available, the model selected by MDL may become more and more 'complex'!"
> — Grünwald (2004), §1.6

Grünwald explicitly rejects the reading that MDL believes simple models are *more likely to be true*, citing and rebutting Webb (1996) and Domingos (1999).
The razor here is epistemological, not metaphysical.

**Separating structure from noise, (b) claims, presented by Grünwald himself as imprecise.**

> "We present the following ideas in an imprecise fashion — Rissanen and Tabus [2004] recently showed how to make them precise. The stochastic complexity of data D relative to M […] can be interpreted as the amount of information in the data relative to M […] a term COMP_n(M) measuring the amount of structure or meaningful information in the data (as 'seen through M'), and a term −log P(D | θ̂(D)) measuring the amount of noise or accidental information in the data."
> — Grünwald (2004), §2.6.1

**(c) my reading.** This is the sentence a reviewability score should be built on, and §5 is where it earns its keep.
The two halves are not interchangeable.
The model half is what a reviewer *learns* and can reuse.
The residual half is what a reviewer must *memorise* and cannot.
A score that only reports the sum has thrown away the distinction that makes it useful.

---

## 3. AIC, BIC and how they relate to MDL

### 3.1 AIC

- Akaike, H.
  (1974).
  "A new look at the statistical model identification." *IEEE Transactions on Automatic Control* 19(6):716–723.
  DOI [10.1109/TAC.1974.1100705](https://doi.org/10.1109/TAC.1974.1100705)

Reprinted as Akaike, H.
(1974), in *Selected Papers of Hirotugu Akaike*, Springer Series in Statistics, pp. 215–222.
DOI [10.1007/978-1-4612-1694-0_16](https://doi.org/10.1007/978-1-4612-1694-0_16)

**The criterion, in its standard modern form.**

> AIC = 2k − 2 ln(L̂)

- *k*: the number of free parameters estimated in the model.
- *L̂*: the maximised value of the likelihood function for the model, that is *L̂ = p(D | θ̂)* where θ̂ is the maximum-likelihood estimate.
- *ln*: natural log, so AIC is in nats-times-two, not bits.
  Selection picks the model with the **smallest** AIC.

**Could not verify from the primary text.** IEEE Xplore was not reachable and no open copy of the 1974 paper resolved.
The formula above is the universally reproduced form and Akaike's own phrasing is generally quoted as "(−2)log(maximum likelihood) + 2(number of independently adjusted parameters within the model)", but I did not read that sentence in the original.
Treat the *wording* as unverified; the *formula* is not in dispute anywhere.

Note also that Grünwald consistently attributes AIC to **Akaike (1973)**, the Second International Symposium on Information Theory paper, when discussing Rissanen's inspiration.
The 1974 IEEE paper is the more-cited restatement.

### 3.2 BIC

- Schwarz, G.
  (1978).
  "Estimating the Dimension of a Model." *The Annals of Statistics* 6(2):461–464.
  DOI [10.1214/aos/1176344136](https://doi.org/10.1214/aos/1176344136)

Page range 461–464 confirmed from Project Euclid, which also lists the paper's own keywords as "Akaike information criterion, asymptotics, dimension".
It is four pages long.

**The criterion, in its standard modern form.**

> BIC = k · ln(n) − 2 ln(L̂)

- *k*: the number of free parameters estimated.
- *n*: the number of observations (sample size).
- *L̂*: as above, the maximised likelihood.

Smallest BIC wins.
The only structural difference from AIC is that the per-parameter penalty is *ln(n)* rather than the constant 2, so BIC penalises parameters harder as data accumulates and AIC does not.

**(b) claims, from Schwarz's own abstract as rendered by Project Euclid.** Schwarz derives the criterion as the leading terms of an asymptotic expansion of the Bayes solution, and observes that "these terms do not depend on the a priori distribution", which is what makes the criterion usable outside a Bayesian frame.

### 3.3 The MDL–BIC relationship, stated precisely

This is the part that is routinely muddled, so here it is with the source's own hedges intact.

**(a) proves, what Rissanen showed in 1978.**

> "In the first paper on MDL, Rissanen [1978] used a two-part code and showed that, asymptotically, and under regularity conditions, the two-part codelength of xⁿ based on a k-parameter model M with an optimally discretized parameter space is given by
> −log P(xⁿ | θ̂(xⁿ)) + (k/2) log n,      (2.42)
> thus ignoring O(1)-terms, which, as we have already seen, can be quite important."
> — Grünwald (2004), §2.9.2

**(a) proves, what Schwarz showed the same year.**

> "In the same year Schwarz [1978] showed that, for large enough n, Bayesian model selection between two exponential families amounts to selecting the model minimizing (2.42), ignoring O(1)-terms as well. As a result of Schwarz's paper, model selection based on (2.42) became known as the BIC (Bayesian Information Criterion)."
> — Grünwald (2004), §2.9.2

So the precise sense of the equivalence is: **two independent derivations, from different starting points, land on the same asymptotic expression, up to O(1) terms, with k fixed and n → ∞.** Rissanen got there by optimally discretising a parameter space and counting bits.
Schwarz got there by expanding a Bayes factor.
Note that (2.42) is BIC divided by two, and in log base 2 rather than *e*.
The criteria agree on ordering, not on units.

**(a)/(b), and here is where the folklore is wrong.**

> "It has sometimes been claimed that MDL = BIC; for example, [Burnham and Anderson 2002, page 286] write 'Rissanen's result is equivalent to BIC'. This is wrong, even for the 1989 version of MDL that Burnham and Anderson refer to — as pointed out by Foster and Stine [2004], the BIC approximation only holds if the number of parameters k is kept fixed and n goes to infinity. If we select between nested families of models where the maximum number of parameters k considered is either infinite or grows with n, then model selection based on both P̄_nml and on P̄_Bayes tends to select quite different models than BIC — if k gets closer to n, the contribution to COMP_n(M) of each additional parameter becomes much smaller than 0.5 log n [Foster and Stine 2004]."
> — Grünwald (2004), §2.9.2

Grünwald then concedes how the confusion arose:

> "However, researchers who claim MDL = BIC have a good excuse: in early work, Rissanen himself has used the phrase 'MDL criterion' to refer to (2.42), and unfortunately, the phrase has stuck."

And earlier in the same chapter:

> "Not taking into account the functional form of the model M, it often does not work very well in practice."

**Summary of the correct statement.**

| Claim | Status |
|-------|--------|
| Rissanen's 1978 two-part code length is asymptotically −log P(xⁿ\|θ̂) + (k/2) log n | true, under regularity conditions, ignoring O(1) |
| Schwarz's BIC is the same expression up to O(1) and units | true, for exponential families, k fixed, n → ∞ |
| Therefore "MDL = BIC" | **false**, and Grünwald names it as an error in Burnham and Anderson (2002, p. 286) |
| Why it is false | refined MDL prices a parameter by its contribution to COMP_n(M), which depends on the model's functional form via ∫√\|I(θ)\|dθ and shrinks below 0.5 log n as k approaches n; BIC prices every parameter identically |

### 3.4 What AIC and BIC are actually for

The distinction is real and it is not a matter of taste.

**AIC targets predictive accuracy.** It is an estimator of expected out-of-sample Kullback-Leibler divergence.
Its guarantee is *efficiency* (asymptotically minimax-rate optimal risk) and it does **not** require that the true model be in the candidate set.
AIC is not consistent: as *n* → ∞ it retains a non-vanishing probability of selecting an over-parameterised model.

**BIC targets identification.** Its guarantee is *consistency*: if the true model is among the candidates, BIC selects it with probability → 1.
That guarantee is conditional on the true model being in the set, which is exactly the assumption Grünwald reports Rissanen rejecting (§2.5 above).

**(a) proves, you cannot have both.**

- Yang, Y.
  (2005).
  "Can the strengths of AIC and BIC be shared?
  A conflict between model identification and regression estimation." *Biometrika* 92(4):937–950.
  DOI [10.1093/biomet/92.4.937](https://doi.org/10.1093/biomet/92.4.937)

The title states the result. **Could not verify from the primary text.** I resolved the citation but did not open the paper, so I am reporting the theorem as the title and the field's consistent summary state it, not from the proof.
The commonly stated form is that no model-selection criterion can simultaneously be consistent in the BIC sense and minimax-rate optimal in the AIC sense.

**(b) claims, the muddle, named.** Grünwald calls the MDL–AIC relationship "subtle", declines to work it out, and points the reader at Speed and Yu (1993).
Burnham and Anderson (2004), "Multimodel Inference", *Sociological Methods & Research* 33(2):261–304, DOI [10.1177/0049124104268644](https://doi.org/10.1177/0049124104268644), is the widely cited defence of AIC and the source Grünwald corrects on the MDL=BIC point.
Reading both is the honest way to see the disagreement.

**(c) my reading, for reviewability.** The AIC-versus-BIC split maps onto a real fork in what a code score is for.
"Will a reviewer of the *next* diff have an easier time" is a predictive question and belongs on the AIC side.
"Is this the right decomposition of the module" is an identification question and belongs on the BIC side.
Yang's result says a single number cannot answer both well.
That is a design constraint, not a nuance.

---

## 4. The bridge to software

**Verdict first: the bridge is real but narrow.** There is a substantial, high-quality literature on the *entropy* of source code under language models, and a smaller but solid one on *compression distance* between code artefacts.
There is, as far as I could find, **no substantial published work scoring code quality, comprehensibility or reviewability by compressibility or by MDL.** I searched Crossref, OpenAlex and arXiv for that specific combination and found nothing worth citing.
I am reporting that as an absence, not padding it with adjacent work.

### 4.1 Code is more predictable than English: the load-bearing result

- Hindle, A., Barr, E.T., Su, Z., Gabel, M. and Devanbu, P.
  (2012).
  "On the naturalness of software." *Proceedings of the 34th International Conference on Software Engineering (ICSE 2012)*, pp. 837–847.
  DOI [10.1109/ICSE.2012.6227135](https://doi.org/10.1109/ICSE.2012.6227135).
  Open copy: <https://www.cs.ucdavis.edu/~devanbu/natural.pdf>
- Reprinted with revision as Hindle, A., Barr, E.T., Gabel, M., Su, Z. and Devanbu, P.
  (2016).
  "On the naturalness of software." *Communications of the ACM* 59(5):122–131.
  DOI [10.1145/2902362](https://doi.org/10.1145/2902362)

**The measure they use, verbatim from §II of the paper.**

> H_M(s) = −(1/n) log p_M(a₁ … aₙ)
> and by the formulation presented in Section II-A:
> H_M(s) = −(1/n) Σ₁ⁿ log p_M(aᵢ | a₁ … a_{i−1})

That is cross-entropy in bits per token: the average surprise of document *s* under model *M*.
Ten-fold cross-validation, split 90/10 by lines at ten random locations.

**(a) measured, the actual numbers, quoted from §III-A.**

> "The single line above is the average over the 10 folds for the English corpus, beginning at about **10 bits for unigram models**, and trailing down to **under 8 bits for 10-gram models**. […] Second, cross-entropy declines rapidly with n-gram order, **saturating around tri- or 4-grams**. […] Last, but not least, **software is far more regular than English with entropies sinking down to under 2 bits in some cases.**"

And from §IV:

> "The strikingly low entropy (**between 3 and 4 bits**) produced by the smoothed n-gram model indicates that even at the local token-sequence level, there is a high degree of 'naturalness'. If we make 8–16 guesses (2³–2⁴) as to what the next token is, we may very well guess the right one!"

For calibration, the paper also computes the uniform-distribution ceiling:

> "If these unique token were uniformly distributed throughout the project (highly unlikely), we could expect a cross-entropy of log₂(1.15E6), or approximately **20 bits**. A similar calculation for the Java projects ranges from about **13 bits to about 17 bits**."

**(a) measured, the corpus.** Ten Java projects.
Ant (254,457 lines, 919,148 tokens, 27,008 unique), Batik (367,293 / 1,384,554 / 30,298), Cassandra (135,992 / 697,498 / 13,002), Eclipse-E4 (1,543,206 / 6,807,301 / 98,652), Log4J (68,528 / 247,001 / 8,056), Lucene (429,957 / 2,130,349 / 32,676), Maven2 (61,622 / 263,831 / 7,637), Maven3 (114,527 / 462,397 / 10,839).
Plus 593 Ubuntu packages across 10 application categories, some up to 9 million lines.

**(a) measured, the project-specificity result (RQ2).** Train a trigram model on one Java project, test on the other nine.
Self cross-entropy is always lower than cross-project cross-entropy.
The regularity is therefore not merely an artefact of Java's simple syntax; a meaningful part of it is *project-local*.

**(b) claims, as the paper's own boxed conclusion.**

> "Corpus-based statistical language models can capture a high level of local regularity in software, even more so than in English."

**(c) my reading.** The 2-to-4-bits figure is the empirical fact that makes a compressibility-based reviewability score plausible at all.
Code is roughly two to five times more predictable than English per token.
It also sets the ceiling: if a diff sits at the corpus's baseline entropy, it is by definition unremarkable, and the interesting diffs are the ones with anomalously *high* conditional entropy given the repository, which is precisely *K(d | R)* from §1.5, approximated by a language model.

### 4.2 The follow-on literature

- Allamanis, M., Barr, E.T., Devanbu, P. and Sutton, C.
  (2018).
  "A Survey of Machine Learning for Big Code and Naturalness." *ACM Computing Surveys* 51(4):1–37.
  DOI [10.1145/3212695](https://doi.org/10.1145/3212695).
  The standard survey of everything built on the naturalness hypothesis.
- Casalnuovo, C., Sagae, K. and Devanbu, P.
  (2019).
  "Studying the difference between natural and programming language corpora." *Empirical Software Engineering* 24(4):1823–1868.
  DOI [10.1007/s10664-018-9669-7](https://doi.org/10.1007/s10664-018-9669-7). **Could not verify** its specific findings; I resolved the record but did not read the paper.
- Casalnuovo, C., Barr, E.T., Dash, S.K., Devanbu, P. and Morgan, E.
  (2020).
  "A theory of dual channel constraints." *ICSE-NIER 2020*, pp. 25–28.
  DOI [10.1145/3377816.3381720](https://doi.org/10.1145/3377816.3381720).
  The framing that code has two simultaneous channels, the algorithmic one the machine reads and the natural one the human reads, and that they constrain each other.

### 4.3 Compression distance applied to code

- Li, M., Chen, X., Li, X., Ma, B. and Vitányi, P.M.B.
  (2004).
  "The Similarity Metric." *IEEE Transactions on Information Theory* 50(12):3250–3264.
  DOI [10.1109/TIT.2004.838101](https://doi.org/10.1109/TIT.2004.838101).
  The theoretical normalized information distance.
- Cilibrasi, R. and Vitányi, P.M.B.
  (2005).
  "Clustering by Compression." *IEEE Transactions on Information Theory* 51(4):1523–1545.
  DOI [10.1109/TIT.2005.844059](https://doi.org/10.1109/TIT.2005.844059). arXiv:[cs/0312044](https://arxiv.org/abs/cs/0312044).
  The practical NCD.
- Chen, X., Francia, B., Li, M., McKinnon, B. and Seker, A.
  (2004).
  "Shared Information and Program Plagiarism Detection." *IEEE Transactions on Information Theory* 50(7):1545–1551.
  DOI [10.1109/TIT.2004.830793](https://doi.org/10.1109/TIT.2004.830793).
  This is the direct application of the theory to source code, and the SID measure behind the SID plagiarism tool.
- Ishio, T., Maeda, N., Shibuya, K. and Inoue, K.
  (2018).
  "Cloned Buggy Code Detection in Practice Using Normalized Compression Distance." *ICSME 2018*, pp. 591–594.
  DOI [10.1109/ICSME.2018.00022]( https://doi.org/10.1109/ICSME.2018.00022)
- Threm, D., Yu, L., Ramaswamy, S. and Sudarsan, S.D.
  (2015).
  "Using normalized compression distance to measure the evolutionary stability of software systems." *ISSRE 2015*, pp. 112–120.
  DOI [10.1109/ISSRE.2015.7381805](https://doi.org/10.1109/ISSRE.2015.7381805)
- Ragkhitwetsagul, C., Krinke, J. and Clark, D.
  (2018).
  "A comparison of code similarity analysers." *Empirical Software Engineering* 23:2464–2519.
  DOI [10.1007/s10664-017-9564-7](https://doi.org/10.1007/s10664-017-9564-7). **Could not verify** the exact page range or its findings on compression-based analysers; record resolved via OpenAlex only.

**The NCD formula, (a) proves the theory it approximates, and states the approximation honestly.** Cilibrasi and Vitányi (2005), equation (3.1):

> NCD(x,y) = ( C(xy) − min{C(x), C(y)} ) / max{C(x), C(y)}

> "Here, C(xy) denotes the compressed size of the concatenation of x and y, C(x) denotes the compressed size of x, and C(y) denotes the compressed size of y. The NCD is a non-negative number 0 ≤ r ≤ 1 + ε representing how different the two files are. Smaller numbers represent more similar files. The ε in the upper bound is due to imperfections in our compression techniques, but for most standard compression algorithms one is unlikely to see an ε above 0.1 (in our experiments gzip and bzip2 achieved NCD's above 1, but PPMZ always had NCD at most 1)."

The theoretical object it approximates is the normalized information distance:

> max{K(x|y), K(y|x)} / max{K(x), K(y)}

The rewriting that makes the intuition obvious, from §3 of the same paper:

> "If, say, C(y) ≥ C(x) then we can rewrite NCD(x,y) = (C(xy) − C(x)) / C(y). That is, the distance NCD(x,y) between x and y is the improvement due to compressing y using x as previously compressed 'data base'."

**(c) my reading.** That last rewriting is the reviewability instrument, hiding in plain sight.
"The improvement due to compressing the diff using the repository as a previously compressed database" is a computable, tool-level stand-in for *K(d | R)*.
It is not *K*, and Cilibrasi and Vitányi are explicit that the compressor is a lossy proxy, but it is an instrument you can actually run.

### 4.4 Information-theoretic software metrics that are not compression-based

- Hassan, A.E.
  (2009).
  "Predicting faults using the complexity of code changes." *ICSE 2009*, pp. 78–88.
  DOI [10.1109/ICSE.2009.5070510](https://doi.org/10.1109/ICSE.2009.5070510).
  Uses Shannon entropy of the *distribution of changes across files* as a predictor. **Could not verify** its effect sizes; record resolved only.
- Buse, R.P.L. and Weimer, W.R.
  (2010).
  "Learning a Metric for Code Readability." *IEEE Transactions on Software Engineering* 36(4):546–558.
  DOI [10.1109/TSE.2009.70](https://doi.org/10.1109/TSE.2009.70), extending Buse and Weimer (2008), *ISSTA 2008*, pp. 121–130, DOI [10.1145/1390630.1390647](https://doi.org/10.1145/1390630.1390647). **Not compression-based**: it is a supervised model over surface features fitted to human ratings.
  Worth citing precisely *because* it is the well-known readability metric and it does not use this machinery at all.

---

## 5. The counter-argument: why shortest is not most reviewable

This is the section that matters most, so it goes in the most detail.

### 5.1 The objection, stated fairly

Minimise description length and the optimum is code golf.
Perl one-liners.
Single-letter identifiers.
Every abstraction inlined until the repetition disappears.
Maximum compression, minimum comprehension.

The objection is correct, and (this is the important part) **the theory already knows it and has three separate formal answers.** None of them is a patch bolted on afterwards.
All three predate any software-engineering interest in the question.

### 5.2 Answer one: logical depth. Short is not the same as cheap to run

- Bennett, C.H.
  (1988).
  "Logical Depth and Physical Complexity." In R.
  Herken (ed.), *The Universal Turing Machine: A Half-Century Survey*, Oxford University Press, pp. 227–257.
  Crossref lists the OUP chapter with year 1990 and pages 227–258, DOI [10.1093/oso/9780198537748.003.0008](https://doi.org/10.1093/oso/9780198537748.003.0008); the Springer/Computerkultur second-edition reprint is pp. 207–235, DOI [10.1007/978-3-7091-6597-3_8](https://doi.org/10.1007/978-3-7091-6597-3_8). **The 1988 date and 227–257 range are the citation everyone uses; the Crossref record disagrees on both by one, and I could not open the chapter to settle it.**

**The idea.** *K(x)* counts the *size* of the shortest program.
It says nothing whatever about how long that program takes to run.
The string of the first million digits of π has tiny *K* and enormous running time.
A random string has huge *K* and trivial running time.
Neither is "complex" in the way we mean the word about a structured object.

**The definition, quoted from a paper that restates Bennett precisely.** Antunes, Bauwens, Souto and Teixeira (2016), §1:

> "Bennett [4] defined the c-significant logical depth of an object x as the time required by a prefix-free machine to generate x with a program p that is c-incompressible (i.e. K(p) ≥ |p| − c, where K stands for the complexity on a universal prefix-free machine)."

And the simpler variant they work with, Definition 2:

> "For any c ≥ 0, the logical depth of a string x at significance level c is
> depth_c(x) = min{ time(p) : |p| ≤ C(x) + c and U(p) = x }."

In English: **among all programs that are within *c* bits of the shortest, how fast is the fastest?** Depth is a *time*, not a length.

Their intuitive gloss, quoted from the same page:

> "The time required to compute x by a program no more than c bits longer than a shortest program."

**Why this is the right shape of answer for code golf, (c) my reading.** A golfed function and a clear function may have nearly the same description length.
They do not have the same logical depth *in the reader*.
Bennett's clock is machine steps, not human seconds, so the transfer is an analogy and not a theorem.
But the *structure* of the answer is exactly what the objection demands: a second axis, orthogonal to length, that separates "short because there is nothing there" from "short because everything has been compressed out and must now be decompressed by whoever reads it".

Bennett's own framing, per Antunes et al., is that depth measures "evolvedness": how much computational history is folded into the object.

### 5.3 Answer two: sophistication. Split the shortest description into structure and noise

- Koppel, M.
  (1987).
  "Complexity, Depth, and Sophistication." *Complex Systems* 1(6):1087–1091. <https://content.wolfram.com/sites/13/2018/02/01-6-4.pdf>
- Koppel, M. and Atlan, H.
  (1991).
  "An almost machine-independent theory of program-length complexity, sophistication, and induction." *Information Sciences* 56(1–3):23–33.
  DOI [10.1016/0020-0255(91)90021-L](https://doi.org/10.1016/0020-0255(91)90021-L)
- Antunes, L. and Fortnow, L.
  (2007/2009).
  "Sophistication Revisited." *Theory of Computing Systems* 45(1):150–161.
  DOI [10.1007/s00224-007-9095-5](https://doi.org/10.1007/s00224-007-9095-5).
  Conference version: *ICALP 2003*, LNCS, pp. 267–277, DOI [10.1007/3-540-45061-0_23](https://doi.org/10.1007/3-540-45061-0_23).
- Antunes, L., Bauwens, B., Souto, A. and Teixeira, A.
  (2016).
  "Sophistication vs Logical Depth." *Theory of Computing Systems* 60(2):280–298.
  DOI [10.1007/s00224-016-9672-6](https://doi.org/10.1007/s00224-016-9672-6). arXiv:[1304.8046](https://arxiv.org/abs/1304.8046)

**Koppel's own statement of the idea, verbatim from the 1987 paper, §1.**

> "The total complexity of an object is defined as the size of its most concise description. The total complexity of an object can be large while its 'meaningful' complexity is low; for example, a random object is by definition maximally complex but completely lacking in structure."

> "The sophistication of an object is the size of that part of the most concise description of that object which describes its structure, i.e. the aggregate of its projectible properties. For example, the sophistication of a string which is random except that each bit is doubled (e.g. 00110000110011 …) is the size of the part of the description which represents the doubling of the bits."

That doubled-bits example is the whole concept in one line.
The string is nearly incompressible.
Its *sophistication* is tiny, because the only structure is "double every bit".

**The definition.** Koppel (1987), Definitions 2 and 3:

> "A description of α, (P,D), is c-minimal if |P| + |D| ≤ H(α) + c."
> "The c-sophistication of a finite string S, SOPH_c(S) = min{|P| : ∃D s.t. (P,D) is a c-minimal description of α}."

The modern restatement, from Antunes et al.
(2016), Definition 1, following Antunes and Fortnow:

> soph_c(x) = min_p { |p| : U(p,d) is defined for all d, and there is a d s.t. U(p,d) = x, and |p| + |d| ≤ C(x) + c }

In English: **among all two-part descriptions that are within *c* bits of optimal, how small can the *program* half be?** Sophistication is the size of the *model*, not the size of the whole.
The data half *d* is noise you must carry; the program half *p* is the structure you can learn.

**Koppel's theorem, (a) proves.** Koppel (1987)'s result is that sophistication and logical depth are the *same measure seen twice*.
His abstract:

> "Two measures of the 'meaningful' complexity of an infinite string are shown to be equivalent up to a constant (under appropriate translation). 'Sophistication', defined by Koppel and Atlan [3], is the size of the projectible part of the string's minimal description and formalizes the amount of planning which went into the construction of the string. 'Depth', defined by Bennett [1], is the amount of time required for the string to be generated from its minimal description and formalizes its 'evolvedness.'"

And the conclusion he draws, §1:

> "Thus, the more sophisticated an object the more time needed for its evolution."

**The refinement, for finite strings, (a) proves.** Antunes et al.
(2016) show that for *finite* strings the correspondence needs a Busy Beaver rescaling and holds only to logarithmic precision, and that sophistication is *unstable* in its significance parameter, a small change in *c* can change sophistication by nearly |x|.
That instability is a real caveat for anyone hoping to compute a sophistication-like score.

### 5.4 Answer three: the Kolmogorov structure function, and why {x} is a terrible model

This is the sharpest formalisation, and it is the one that names the code-golf failure exactly.

- Vereshchagin, N.K. and Vitányi, P.M.B.
  (2004).
  "Kolmogorov's Structure Functions and Model Selection." *IEEE Transactions on Information Theory* 50(12):3265–3290.
  DOI [10.1109/TIT.2004.838346](https://doi.org/10.1109/TIT.2004.838346). arXiv:[cs/0204037](https://arxiv.org/abs/cs/0204037).
  Earlier: *FOCS 2002*, pp. 751–760, DOI [10.1109/SFCS.2002.1182000](https://doi.org/10.1109/SFCS.2002.1182000).
- Vitányi, P.M.B.
  (2006).
  "Meaningful Information." *IEEE Transactions on Information Theory* 52(10):4617–4626.
  DOI [10.1109/TIT.2006.881729](https://doi.org/10.1109/TIT.2006.881729). arXiv:[cs/0111053](https://arxiv.org/abs/cs/0111053).
- Gács, P., Tromp, J. and Vitányi, P.M.B.
  (2001).
  "Algorithmic statistics." *IEEE Transactions on Information Theory* 47(6):2443–2463. **Could not verify** this record from Crossref; it is cited by Grünwald and Vitányi (2008) and by Vereshchagin and Vitányi (2004) and the details above are from those citations.

**The setup.** Models are finite sets *S* of binary strings, and the data *x* is one element of *S*.
Vereshchagin and Vitányi note this is not a restriction: the results generalise to computable probability densities and to total recursive functions.

**Randomness deficiency.** Vereshchagin and Vitányi (2004), preliminaries:

> δ(x | S) = log |S| − K(x | S*)

for *x ∈ S*, and ∞ otherwise, where *S\** is the shortest program that lists *S*.
If δ is small, *x* is a *typical* member of *S*.

**The three functions, verbatim, equations (3), (4) and (6).**

> Minimal randomness deficiency:
> β_x(α) = min_S { δ(x | S) : S ∋ x, K(S) ≤ α }

> The Kolmogorov structure function:
> h_x(α) = min_S { log |S| : S ∋ x, K(S) ≤ α }

> The MDL function:
> λ_x(α) = min_S { Λ(S) : S ∋ x, K(S) ≤ α },   where Λ(S) = log|S| + K(S)

*α* is a budget on how complex the model is allowed to be. λ_x is described by the authors as "the celebrated two-part Minimum Description Length code length with the model-code length restricted to at most α".

**The sufficiency line, (a) proves.** Since a two-part description of *x* via *S* is itself a valid description:

> K(S) + log|S| + c₂ ≥ K(x)

so *h_x(α)* can never drop more than a constant below the diagonal *L(α) + α = K(x)*.
Where it *touches* that diagonal, the witnessing set is an **algorithmic sufficient statistic**, and the one with the least *α* is the **algorithmic minimal sufficient statistic** (AMSS).

**Now the code-golf argument, made formally.** Grünwald and Vitányi (2008), §6.1.2, consider the two degenerate models available for any *x*.

> "Both the largest set {0,1}ⁿ [having low complexity of about K(n)] and the singleton set {x} [having high complexity of about K(x)], while certainly statistics for x, would indeed be considered poor explanations. We would like to balance simplicity of model vs. size of model."

A set *S* is called **optimal** when the two-part code is as short as the one-part code:

> K(x) = K(S) + log |S| + O(1)

And here is the sentence that settles the objection:

> "While 'optimality' is a refinement of 'typicality', the fact that {x} is still an optimal set for x shows that it is still not sufficient by itself to capture the notion of 'meaningful information'."
> — Grünwald and Vitányi (2008), §6.1.2

**Read that again, because it is exactly the code-golf case.** The singleton model *{x}* ("the program is: print this literal") achieves the *shortest possible two-part code length*.
It is optimal by the length criterion and it explains nothing.
Golfed code is the singleton model.
It has minimised total description length by pushing everything into the model and leaving no residual, and it has therefore learned nothing that transfers.

**What the theory does about it.** It refines the criterion from "shortest two-part code" to "**minimal** sufficient statistic": among the sets that achieve the shortest code, take the one with the *smallest model complexity α*.
Grünwald and Vitányi say so directly, at §6.3:

> "It follows that every set S that is an AMSS also minimizes the two-part codelength to within O(1). However, as we already indicated, there exist optimal sets S (that, because of their optimality, may be selected by MDL), that are not minimal sufficient statistics. As explained by Vitányi [2005], these do not capture the idea of 'summarizing all structure in x'. Thus, the AMSS may be considered a refinement of the idealized MDL approach."

**Note a probable typo in the source.** Grünwald and Vitányi (2008) give idealized MDL at equation (26) as "pick a set S ∋ x minimizing the two-part codelength K(S) − log |S|".
Every other statement in the same chapter, and Vereshchagin and Vitányi's Λ(S), uses **+**.
Read it as *K(S) + log |S|*.

**Vitányi's own framing of the split, (b) claims, from "Meaningful Information".** The paper divides the information in a finite object into "the information accounting for the useful regularity present in the object and the information accounting for the remaining accidental information", and studies *absolutely nonstochastic objects* whose structure function never approaches the diagonal until the very end, objects with no simple sufficient explanation at all.

**The gravity example, from Grünwald and Vitányi (2008), §6.1.**

> "let an object x be a sequence of observations of heavenly bodies. Then x can be described by the binary string pd, where p is the description of the laws of gravity and the observational parameter setting, while d accounts for the measurement errors: we can divide the information in x into meaningful information p and accidental information d. The main task for statistical inference and learning theory is to distill the meaningful information present in the data."

### 5.5 The synthesis, and what it licenses

**(c) my reading.
Everything in §5.5 is mine, built on the sources above.**

Put the three answers side by side and they agree.

| Measure | What it counts | What code-golf does to it |
|---------|----------------|---------------------------|
| K(x) | total description length | **minimises it**. Golf wins. |
| logical depth (Bennett) | running time of the near-shortest program | **maximises it**. Golf loses. |
| sophistication (Koppel) | size of the *model* half of the near-optimal two-part code | pushes everything into the model, so **maximises it**. Golf loses. |
| model complexity α at the AMSS | complexity of the minimal sufficient statistic | the singleton model is optimal but not minimal. Golf loses. |

So the single-number version of "shortest description wins" is not something the theory endorses.
The theory's own criterion is two-dimensional: it is the *shape of the curve h_x(α)*, not a scalar.
Kolmogorov's structure function is literally a plot of fit-quality against model budget.

**The practical rule this yields.** Do not score a diff by total description length.
Score it by the **split**.

- The model half (what a reviewer must *learn*, and can then reuse on the next diff) should be small and should transfer.
- The residual half (what a reviewer must *memorise*, and cannot reuse) is the real reviewing cost.
- Golfed code is a diff whose model half has swallowed the residual: the sum is minimal, the model half is maximal, and nothing transfers.
- Boilerplate is the mirror image: the model half is trivial and the residual half is enormous but individually cheap.

**Empirical corroboration, and it is direct.** Humans do not prefer the shortest expression.
They prefer the *most predictable* one, which is a different thing.

- Casalnuovo, C., Lee, K., Wang, H., Devanbu, P. and Morgan, E.
  (2020).
  "Do Programmers Prefer Predictable Expressions in Code?" *Cognitive Science* 44(12).
  DOI [10.1111/cogs.12921](https://doi.org/10.1111/cogs.12921)

**(a) measured, from the published abstract.**

> "Using meaning-preserving transformations, we produce equivalent alternatives to developer-written code expressions and run a corpus study on Java and Python projects. In general, language models rate the code expressions developers choose to write as more predictable than these transformed alternatives. Then, we perform two human subject studies asking participants to choose between two equivalent snippets of Java code with different surprisal scores (one original and transformed). We find that programmers do prefer more predictable variants, and that stronger language models like the transformer align more often and more consistently with these preferences."

**(c) my reading.** Surprisal, not length, is what tracked preference.
Predictability is *conditional* description length (*K(d | R)* again) and it is minimised by writing what the corpus already says, which is the opposite of golf.
Golf minimises unconditional length and maximises surprisal.
That is the empirical shape of the same distinction the theory draws formally.

**What I could not find.** No published work applies logical depth, sophistication, or the structure function to source code comprehensibility.
The bridge in §5.5 is built by me, from theory on one side and the naturalness literature on the other.
It is a plausible bridge and it is not a cited one.

---

## 6. Formula sheet

Every symbol defined, gathered for reference.

**Kolmogorov complexity.** K(x) = length in bits of the shortest program that outputs *x* on a fixed universal prefix machine and halts.

**Invariance.** |K₁(x) − K₂(x)| ≤ C, with *C* depending on the two universal machines and on nothing else.

**Conditional complexity.** K(x | y) = length of the shortest program that outputs *x* given *y* as input.
K(x) = K(x | ε).

**Additivity (Gács).** K(x,y) =⁺ K(x) + K(y | x\*) =⁺ K(y) + K(x | y\*), where x\* is the first shortest program for *x*.

**Algorithmic mutual information.** I(y : x) = K(x) − K(x | y\*) =⁺ K(x) + K(y) − K(x,y), symmetric to within a constant.

**Two-part MDL (crude).** minimise L(H) + L(D | H) over candidate hypotheses *H*.
L(H) is the code length of the hypothesis under a code fixed independently of *n*.
L(D | H) = −log P(D | H), forced by the consistency argument.

**Parametric complexity.** COMP_n(M) = log Σ_{xⁿ} P(xⁿ | θ̂(xⁿ)), where θ̂(xⁿ) is the ML estimate for xⁿ.

**NML / Shtarkov distribution.** P̄_nml(xⁿ) = P(xⁿ | θ̂(xⁿ)) / Σ_{yⁿ} P(yⁿ | θ̂(yⁿ)).
Its regret is COMP_n(M) for *every* xⁿ, and it is the unique minimax-regret distribution.

**Stochastic complexity.** −log P̄_nml(D | M) = −log P(D | θ̂(D)) + COMP_n(M).
Noise term plus structure term.

**Asymptotic expansion of parametric complexity.** COMP_n(M) = (k/2) log(n/2π) + log ∫_Θ √|I(θ)| dθ + o(1). *k* parameters, *n* observations, *I(θ)* the k×k Fisher information matrix.

**Rissanen's 1978 two-part asymptotic.** −log P(xⁿ | θ̂(xⁿ)) + (k/2) log n, ignoring O(1).

**AIC.** AIC = 2k − 2 ln L̂.
Smallest wins.
Targets predictive risk.

**BIC.** BIC = k ln(n) − 2 ln L̂.
Smallest wins.
Targets consistent identification.

**Normalized information distance (ideal).** NID(x,y) = max{K(x|y), K(y|x)} / max{K(x), K(y)}.

**Normalized compression distance (practical).** NCD(x,y) = (C(xy) − min{C(x), C(y)}) / max{C(x), C(y)}, for a real compressor *C*, in [0, 1+ε].

**Cross-entropy of a corpus under a language model (Hindle et al.).** H_M(s) = −(1/n) Σᵢ log p_M(aᵢ | a₁ … a_{i−1}), in bits per token.

**Randomness deficiency.** δ(x | S) = log |S| − K(x | S\*), for x ∈ S.

**Kolmogorov structure function.** h_x(α) = min_S { log |S| : S ∋ x, K(S) ≤ α }.

**MDL function.** λ_x(α) = min_S { K(S) + log |S| : S ∋ x, K(S) ≤ α }.

**Minimal randomness deficiency function.** β_x(α) = min_S { δ(x | S) : S ∋ x, K(S) ≤ α }.

**The main identity of Vereshchagin and Vitányi (2004), equation (7).** β_x(α) = h_x(α) + α − K(x) = λ_x(α) − K(x).

**Sufficiency.** A set *S* is an algorithmic sufficient statistic when α + h_x(α) = K(x), that is, when the structure function touches the diagonal.
The AMSS is the one with the least α.

**Logical depth.** depth_c(x) = min { time(p) : |p| ≤ C(x) + c and U(p) = x }.

**Sophistication.** soph_c(x) = min_p { |p| : ∃d with U(p,d) = x and |p| + |d| ≤ C(x) + c }.

---

## 7. Bibliography

Ordered by section, with DOIs where obtainable.

**Kolmogorov complexity.**

1. Solomonoff, R.J.
   (1960). *A Preliminary Report on a General Theory of Inductive Inference.* Report V-131, Zator Co., Cambridge, Mass., 4 Feb 1960; revised as ZTB-138, Nov 1960.
2. Solomonoff, R.J.
   (1964).
   "A Formal Theory of Inductive Inference, Part I." *Information and Control* 7(1):1–22.
   DOI 10.1016/S0019-9958(64)90223-2
3. Solomonoff, R.J.
   (1964).
   "A Formal Theory of Inductive Inference, Part II." *Information and Control* 7(2):224–254.
   DOI 10.1016/S0019-9958(64)90131-7
4. Kolmogorov, A.N.
   (1965).
   "Three approaches to the quantitative definition of information." *Problems of Information Transmission* 1(1):1–7.
5. Chaitin, G.J.
   (1966).
   "On the Length of Programs for Computing Finite Binary Sequences." *Journal of the ACM* 13(4):547–569.
   DOI 10.1145/321356.321363
6. Li, M. and Vitányi, P.M.B. *An Introduction to Kolmogorov Complexity and Its Applications.* Springer. 1st ed. 1993, 2nd ed. 1997, 3rd ed. 2008, 4th ed. 2019.
   DOI 10.1007/978-3-030-11298-1
7. Grünwald, P.D. and Vitányi, P.M.B.
   (2008).
   "Algorithmic Information Theory." In *Handbook of the Philosophy of Information*, Elsevier. arXiv:0809.2754. **The single best open-access source for §1; every quotation in §1.3 to §1.5 is from here.**

**MDL.**

8. Rissanen, J.
   (1978).
   "Modeling by shortest data description." *Automatica* 14(5):465–471.
   DOI 10.1016/0005-1098(78)90005-5
9. Rissanen, J.
   (1983).
   "A Universal Prior for Integers and Estimation by Minimum Description Length." *Annals of Statistics* 11(2):416–431.
   DOI 10.1214/aos/1176346150
10. Rissanen, J.
    (1996).
    "Fisher information and stochastic complexity." *IEEE Transactions on Information Theory* 42(1):40–47.
    DOI 10.1109/18.481776
11. Barron, A., Rissanen, J. and Yu, B.
    (1998).
    "The minimum description length principle in coding and modeling." *IEEE Transactions on Information Theory* 44(6):2743–2760. **Could not verify** this record independently; cited by Grünwald (2004) as the field's survey.
12. Grünwald, P.D.
    (2004).
    "A tutorial introduction to the minimum description length principle." arXiv:math/0406077.
13. Grünwald, P.D.
    (2007). *The Minimum Description Length Principle.* MIT Press.
    DOI 10.7551/mitpress/4643.001.0001
14. Hansen, M.H. and Yu, B.
    (2001).
    "Model Selection and the Principle of Minimum Description Length." *JASA* 96(454):746–774.
    DOI 10.1198/016214501753168398

**Model selection.**

15. Akaike, H.
    (1974).
    "A new look at the statistical model identification." *IEEE TAC* 19(6):716–723.
    DOI 10.1109/TAC.1974.1100705
16. Schwarz, G.
    (1978).
    "Estimating the Dimension of a Model." *Annals of Statistics* 6(2):461–464.
    DOI 10.1214/aos/1176344136
17. Yang, Y.
    (2005).
    "Can the strengths of AIC and BIC be shared?
    A conflict between model identification and regression estimation." *Biometrika* 92(4):937–950.
    DOI 10.1093/biomet/92.4.937
18. Burnham, K.P. and Anderson, D.R.
    (2004).
    "Multimodel Inference: Understanding AIC and BIC in Model Selection." *Sociological Methods & Research* 33(2):261–304.
    DOI 10.1177/0049124104268644

**Software.**

19. Hindle, A., Barr, E.T., Su, Z., Gabel, M. and Devanbu, P.
    (2012).
    "On the naturalness of software." *ICSE 2012*, 837–847.
    DOI 10.1109/ICSE.2012.6227135
20. Hindle, A., Barr, E.T., Gabel, M., Su, Z. and Devanbu, P.
    (2016).
    "On the naturalness of software." *CACM* 59(5):122–131.
    DOI 10.1145/2902362
21. Allamanis, M., Barr, E.T., Devanbu, P. and Sutton, C.
    (2018).
    "A Survey of Machine Learning for Big Code and Naturalness." *ACM Computing Surveys* 51(4):1–37.
    DOI 10.1145/3212695
22. Casalnuovo, C., Sagae, K. and Devanbu, P.
    (2019).
    "Studying the difference between natural and programming language corpora." *EMSE* 24(4):1823–1868.
    DOI 10.1007/s10664-018-9669-7
23. Casalnuovo, C., Barr, E.T., Dash, S.K., Devanbu, P. and Morgan, E.
    (2020).
    "A theory of dual channel constraints." *ICSE-NIER 2020*, 25–28.
    DOI 10.1145/3377816.3381720
24. Casalnuovo, C., Lee, K., Wang, H., Devanbu, P. and Morgan, E.
    (2020).
    "Do Programmers Prefer Predictable Expressions in Code?" *Cognitive Science* 44(12).
    DOI 10.1111/cogs.12921
25. Buse, R.P.L. and Weimer, W.R.
    (2010).
    "Learning a Metric for Code Readability." *IEEE TSE* 36(4):546–558.
    DOI 10.1109/TSE.2009.70
26. Hassan, A.E.
    (2009).
    "Predicting faults using the complexity of code changes." *ICSE 2009*, 78–88.
    DOI 10.1109/ICSE.2009.5070510

**Compression distance.**

27. Li, M., Chen, X., Li, X., Ma, B. and Vitányi, P.M.B.
    (2004).
    "The Similarity Metric." *IEEE TIT* 50(12):3250–3264.
    DOI 10.1109/TIT.2004.838101
28. Chen, X., Francia, B., Li, M., McKinnon, B. and Seker, A.
    (2004).
    "Shared Information and Program Plagiarism Detection." *IEEE TIT* 50(7):1545–1551.
    DOI 10.1109/TIT.2004.830793
29. Cilibrasi, R. and Vitányi, P.M.B.
    (2005).
    "Clustering by Compression." *IEEE TIT* 51(4):1523–1545.
    DOI 10.1109/TIT.2005.844059
30. Cebrián, M., Alfonseca, M. and Ortega, A.
    (2005).
    "Common Pitfalls Using the Normalized Compression Distance: What to Watch Out for in a Compressor." *Communications in Information and Systems* 5(4).
    DOI 10.4310/CIS.2005.v5.n4.a1. **Could not verify** the author list; record from OpenAlex only.
    Relevant because it is the known critique of NCD's compressor sensitivity.
31. Threm, D., Yu, L., Ramaswamy, S. and Sudarsan, S.D.
    (2015).
    "Using normalized compression distance to measure the evolutionary stability of software systems." *ISSRE 2015*, 112–120.
    DOI 10.1109/ISSRE.2015.7381805
32. Ishio, T., Maeda, N., Shibuya, K. and Inoue, K.
    (2018).
    "Cloned Buggy Code Detection in Practice Using Normalized Compression Distance." *ICSME 2018*, 591–594.
    DOI 10.1109/ICSME.2018.00022
33. Ragkhitwetsagul, C., Krinke, J. and Clark, D.
    (2017/2018).
    "A comparison of code similarity analysers." *EMSE*.
    DOI 10.1007/s10664-017-9564-7

**Depth, sophistication, structure.**

34. Bennett, C.H.
    (1988).
    "Logical Depth and Physical Complexity." In R.
    Herken (ed.), *The Universal Turing Machine: A Half-Century Survey*, OUP, pp. 227–257.
    Crossref: DOI 10.1093/oso/9780198537748.003.0008 (listed 1990, pp. 227–258); Springer reprint DOI 10.1007/978-3-7091-6597-3_8 (1995, pp. 207–235).
35. Koppel, M.
    (1987).
    "Complexity, Depth, and Sophistication." *Complex Systems* 1(6):1087–1091.
36. Koppel, M. and Atlan, H.
    (1991).
    "An almost machine-independent theory of program-length complexity, sophistication, and induction." *Information Sciences* 56(1–3):23–33.
    DOI 10.1016/0020-0255(91)90021-L
37. Gács, P., Tromp, J. and Vitányi, P.M.B.
    (2001).
    "Algorithmic statistics." *IEEE TIT* 47(6):2443–2463. **Could not verify** independently.
38. Vereshchagin, N.K. and Vitányi, P.M.B.
    (2004).
    "Kolmogorov's Structure Functions and Model Selection." *IEEE TIT* 50(12):3265–3290.
    DOI 10.1109/TIT.2004.838346. arXiv:cs/0204037
39. Antunes, L., Fortnow, L., van Melkebeek, D. and Vinodchandran, N.V.
    (2006).
    "Computational depth: Concept and applications." *Theoretical Computer Science* 354(3):391–404.
    DOI 10.1016/j.tcs.2005.11.033
40. Vitányi, P.M.B.
    (2006).
    "Meaningful Information." *IEEE TIT* 52(10):4617–4626.
    DOI 10.1109/TIT.2006.881729. arXiv:cs/0111053
41. Antunes, L. and Fortnow, L.
    (2009).
    "Sophistication Revisited." *Theory of Computing Systems* 45(1):150–161.
    DOI 10.1007/s00224-007-9095-5
42. Antunes, L., Bauwens, B., Souto, A. and Teixeira, A.
    (2016).
    "Sophistication vs Logical Depth." *Theory of Computing Systems* 60(2):280–298.
    DOI 10.1007/s00224-016-9672-6. arXiv:1304.8046

---

## 8. Could not verify

Everything on this list is stated somewhere above with the same flag.
Gathered here so nothing is lost.

| Item | Why |
|------|-----|
| Akaike (1974), the paper's own wording of the AIC formula | IEEE Xplore unreachable, no open copy found. The formula 2k − 2 ln L̂ is undisputed; Akaike's exact sentence is unverified. |
| Bennett (1988), year and page range | Crossref lists the OUP chapter as 1990, pp. 227–258; the universal citation is 1988, pp. 227–257. Chapter not opened. |
| Yang (2005), the theorem's precise statement | Record resolved via Crossref; paper not opened. Reported from the title and the field's consistent summary. |
| Gács, Tromp and Vitányi (2001), "Algorithmic statistics" | Not found in Crossref under that query. Details taken from citing papers. |
| Barron, Rissanen and Yu (1998) survey, volume and pages | Cited by Grünwald (2004) but not independently resolved. |
| Casalnuovo, Sagae and Devanbu (2019) findings | Record resolved; paper not opened. |
| Hassan (2009) effect sizes | Record resolved; paper not opened. |
| Ragkhitwetsagul et al. (2017/2018), page range and findings on compression-based analysers | OpenAlex record only. |
| Cebrián, Alfonseca and Ortega (2005), author list | OpenAlex record only; the title and DOI are confirmed. |
| Rissanen (1978), the primary text | Paywalled. The 1978 asymptotic result and its derivation are quoted from Grünwald (2004) §2.9.2, not from Rissanen. |
| Li and Vitányi, theorem numbers in the 4th edition (2019) | Grünwald and Vitányi cite the 1997 2nd edition. Theorem numbering differs across editions and I could not check the 2019 numbering. |
| Any published application of logical depth, sophistication or the structure function to source code comprehensibility | Searched Crossref, OpenAlex and arXiv. **No substantial literature found.** §5.5's bridge is my own construction. |
| Any published work scoring code quality or reviewability by compressibility | Searched the same three. **No substantial literature found.** The nearest neighbours are clone detection, plagiarism detection and evolutionary stability, all of which measure similarity between artefacts rather than the reviewing cost of one. |

**A note on the WebSearch budget.** This session's general web-search allowance was exhausted before research began, so every record here was resolved through structured bibliographic APIs (Crossref, OpenAlex, Project Euclid, arXiv) and direct document fetches rather than through search-engine results.
That biases the coverage toward work that is well indexed with a DOI.
Grey literature, blog posts and any recent preprint without a DOI is under-represented, and the "no substantial literature found" verdicts in §4 and §8 should be read with that limitation in mind.
