# Research Rewrite Patterns

## Contents

1. Replace novelty theater
2. Separate prototype from result
3. Calibrate endpoint-specific superiority
4. Separate budget modes
5. Move negative evidence beside the claim
6. Convert mechanism to tested interpretation
7. Attach citations to propositions
8. Mark unsupported quotation alignment
9. Replace API authority theater
10. Repair object identity
11. Repair local-to-global proof coverage
12. Restore reversible elimination
13. Validate envelope language
14. Expand theorem conditions
15. Replace `similarly` at a decisive branch
16. Justify approximation
17. Rebuild mechanical contributions
18. Make related work selective
19. Consolidate limitations
20. Rewrite abstract and conclusion

Apply patterns only after fact, source, and proof checks. Never strengthen a claim to improve flow.

## 1. Replace novelty theater

**Trigger:** `first-ever`, `unprecedented`, `fills a critical gap`.

**Before:** `We propose the first framework that solves decomposition quality.`

**After:** `Existing interaction detectors estimate which variables should remain together; the present method additionally measures within-group curvature heterogeneity under the same backend.`

**Guardrail:** If priority matters, document the search boundary before using `to our knowledge`.

**Rules:** `RES-002`, `RES-004`, `RES-043`.

## 2. Separate prototype from result

**Trigger:** an implemented but unevaluated component appears in contributions or conclusion.

**Before:** `Our hybrid method improves structure and conditioning.`

**After:** `We implement a hybrid split operation to demonstrate feasibility. Its optimization performance has not been evaluated and is not part of the present result claims.`

**Rules:** `RES-003`, `RES-005`.

## 3. Calibrate endpoint-specific superiority

**Trigger:** one metric or phase favors a method while another reverses.

**Before:** `A consistently outperforms B.`

**After:** `Under the independent 1e6-evaluation budget, A attains lower final objective values on F4, F7, and F8. On F8, B remains better on log-AUC and evaluations-to-target, so the claim is limited to final precision.`

**Rules:** `RES-008`, `RES-009`, `RES-012`.

## 4. Separate budget modes

**Trigger:** preprocessing cost is charged in one analysis and excluded in another.

**Before:** `Both methods receive equal budgets.`

**After:** `The independent-budget comparison gives both groupings the same optimization budget and reports decomposition cost separately. The shared-budget analysis charges decomposition to the common total and addresses end-to-end efficiency.`

**Rules:** `RES-010`, `RES-011`.

## 5. Move negative evidence beside the claim

**Trigger:** null, reversed, or boundary results appear only in limitations.

**Before:** `The mechanism is broadly effective. Some limitations remain.`

**After:** `The effect is large on the Elliptic and Schwefel 1.2 families but weak on the tested Ackley and Rastrigin boundary functions. The evidence therefore supports a family-conditional mechanism.`

**Rules:** `RES-006`, `RES-012`, `RES-046`.

## 6. Convert mechanism to tested interpretation

**Trigger:** correlation or model behavior is called a mechanism.

**Before:** `Conditioning causes the observed performance gap.`

**After:** `Conditioning diagnostics covary with final performance under the fixed backend. Exact Hessian comparisons support the proposed explanation on F1; the pooled association alone does not establish causality.`

**Rules:** `RES-013`, `RES-016`.

## 7. Attach citations to propositions

**Trigger:** a paragraph-end citation cluster follows several claims.

**Before:** `DG detects interactions, reduces cost, and improves convergence [1-4].`

**After:** `Differential grouping uses finite-difference changes to detect variable interaction [1]. Later variants reduce detection cost under their stated benchmark protocols [2,3]. The present study tests convergence separately.`

**Rules:** `RES-019`, `RES-021`.

## 8. Mark unsupported quotation alignment

**Trigger:** only nearby OCR or a page-level anchor is available.

**Before:** `The source therefore supports our routing hypothesis.`

**After:** `The located passage discusses sampling sensitivity but does not state the routing proposition. Support for that proposition remains unverified.`

**Rules:** `RES-020`, `RES-021`.

## 9. Replace API authority theater

**Trigger:** polished documentation asserts class paths, defaults, acronyms, or rankings without code evidence.

**Before:** `DG2 is the Decomposition-based Genetic Algorithm and is highly scalable.`

**After:** `The repository implements the object at [verified path]. Its primary paper expands DG2 as [verified name]. No comparative scalability claim is made without benchmark evidence.`

**Rules:** `RES-022`, `RES-043`.

## 10. Repair object identity

**Trigger:** normalized/original quantities or function/derivative objects share one symbol.

**Before:** `After division by G, A=cosh(t) and G=1.`

**After:** `Define \hat A=A/G and \hat L=L/G. Then \hat A=\cosh t and \hat L=\sinh(t)/t; the original means retain their definitions.`

**Rules:** `RES-025`, `RES-026`.

## 11. Repair local-to-global proof coverage

**Trigger:** Taylor terms or samples imply a global sign.

**Before:** `The expansion is positive; hence H(t)>0 for t>0.`

**After:** `The signed remainder proves positivity on (0,delta]. On [delta,T], the derivative has no zero and H(delta)>0. For t>=T, bound (12) makes the positive leading term exceed all negative terms.`

**Guardrail:** Downgrade to a local claim if any region lacks a certificate.

**Rules:** `RES-027`, `RES-028`.

## 12. Restore reversible elimination

**Trigger:** `eliminating the parameter gives G=0, so the locus is G=0`.

**After:** `Every admissible original solution satisfies G=0. Equality is claimed only after each retained branch recovers an admissible parameter and passes substitution into the original system; discarded denominator cases are treated separately.`

**Rules:** `RES-029`, `RES-034`.

## 13. Validate envelope language

**Trigger:** a discriminant or resultant is immediately called the envelope.

**After:** `Elimination produces the candidate curve G=0. On the regular branch G1, parameter recovery gives F=F_s=0 and the nonzero gradients are parallel. Branch G2 has no real admissible parameter; the endpoint singularity is handled separately.`

**Rules:** `RES-029`, `RES-030`.

## 14. Expand theorem conditions

**Trigger:** a theorem name bridges a domain or regularity change.

**Before:** `By Taylor's theorem, the result follows.`

**After:** `Because f has four continuous derivatives on [a,b], Taylor's theorem with Lagrange remainder applies at x0. Bound (7) controls the remainder uniformly on the stated interval.`

**Rules:** `RES-027`, `RES-034`.

## 15. Replace `similarly` at a decisive branch

**Trigger:** the omitted branch has different signs, domains, or auxiliary objects.

**Before:** `The other inequality follows similarly.`

**After:** `For the left inequality define E(v)=... . Unlike the preceding branch, A0-I0 is positive, so the bound on log G preserves the direction. Differentiation gives E'(v)=...>0 and E(0)=0.`

**Rules:** `RES-033`, `RES-035`.

## 16. Justify approximation

**Trigger:** surrogate, linearization, numerical moment, or local model is used as exact evidence.

**Before:** `The approximation proves the estimator is unbiased.`

**After:** `Under assumptions A-C, the approximation error is O(h^2) uniformly on D. The numerical result supports local accuracy at the tested h values; exact unbiasedness is not claimed.`

**Rules:** `RES-014`, `RES-036`.

## 17. Rebuild mechanical contributions

**Trigger:** forced three-item contributions mix a question, code, and result.

**Operation:** Classify each item, merge duplicates, and retain only evidence-bearing deltas.

**After pattern:**

```text
Contribution 1: exact conceptual/method delta against baseline.
Contribution 2: controlled evidence that evaluates that delta.
Boundary result: where the contribution does not generalize.
```

**Rules:** `RES-003`, `RES-007`, `RES-040`.

## 18. Make related work selective

**Trigger:** each paper receives the same background-summary-transfer paragraph.

**Operation:** Move common background to one synthesis paragraph. Organize sources by the proposition they establish and preserve conflicting assumptions.

**Rules:** `RES-021`, `RES-024`, `RES-040`.

## 19. Consolidate limitations

**Trigger:** the same caveat appears in abstract, every result, discussion, and conclusion.

**After:** `The full scope boundary appears at the first result it changes. The conclusion retains one compressed synthesis; other repetitions are deleted unless a standalone caption needs the condition.`

**Rules:** `RES-042`, `RES-047`.

## 20. Rewrite abstract and conclusion

**Abstract pattern:** question -> exact contribution -> central evidence -> strongest boundary.

**Conclusion pattern:** robust findings -> conditional or negative findings -> unresolved test -> supported implication.

**Guardrail:** Do not introduce a new baseline, number, mechanism, or recommendation.

**Rules:** `RES-039`, `RES-046`.
