# Source-Derived Research Cases

## Contents

1. Endpoint-specific superiority
2. Independent versus shared budgets
3. Prototype versus evaluated contribution
4. Boundary results narrow the mechanism
5. Selective related work
6. Exact quotation alignment
7. Benchmark generalization wall
8. API completeness without factual authority
9. Affine expression called bilinear
10. Special cases promoted to an envelope
11. Elimination promoted to exact locus
12. Local expansion promoted to global sign
13. Object identity changes mid-proof
14. Asymptotics used as a base-case proof
15. Zeros lost through a quotient
16. Underdetermination preserved honestly
17. Version residue after a claim pivot

These cases are diagnostic evidence. Reuse the reasoning, not the wording.

## 1. Endpoint-specific superiority

**Source pattern:** BYD large-scale optimization manuscript. A geometry-aware grouping achieved better final `best_so_far_y` on selected functions, while a linkage-first method performed better on process metrics for one function.

**Failure risk:** Compressing this into `method A outperforms method B` erases endpoint, budget, backend, and family boundaries.

**Required move:** State the final endpoint, functions, backend, budget mode, and reversed metrics in the same result family. Keep the conclusion about late-stage final precision, not universal method quality.

**Rules:** `RES-008`, `RES-009`, `RES-012`, `RES-039`.

## 2. Independent versus shared budgets

**Source pattern:** BYD comparisons tracked decomposition cost separately. Independent mode gave each grouping the same optimization budget; shared mode charged decomposition against a common total.

**Failure risk:** Independent mode isolates grouping quality but is not an end-to-end efficiency comparison. Shared mode measures resource allocation but confounds grouping with remaining optimization budget.

**Required move:** Name the mode in every claim and table. Use separate conclusions for grouping quality and resource efficiency.

**Rules:** `RES-010`, `RES-011`, `RES-023`.

## 3. Prototype versus evaluated contribution

**Source pattern:** A hybrid decomposer was implemented to make a design implication concrete but had no full-budget evidence supporting the paper's main claims.

**Failure risk:** Listing the prototype as a contribution invites readers to infer completed validation.

**Required move:** Label it `implemented prototype`, state what operation it demonstrates, and exclude performance language until evaluation exists.

**Rules:** `RES-003`, `RES-005`, `RES-039`.

## 4. Boundary results narrow the mechanism

**Source pattern:** Strong effects appeared on ill-conditioned function families; Ackley/Rastrigin boundary samples were flat or weak.

**Useful behavior:** Negative and boundary evidence was used to delimit the mechanism instead of being buried as a generic limitation.

**Required move:** Put the boundary functions in Results, propagate the narrower claim to abstract and conclusion, and identify the function-family condition.

**Rules:** `RES-006`, `RES-012`, `RES-013`, `RES-046`.

## 5. Selective related work

**Source pattern:** A research manuscript explicitly limited related work to sources needed for linkage, conditioning, benchmark structure, and the paper's actual claim.

**Useful behavior:** Selectivity made the novelty delta auditable; an exhaustive catalog would have hidden the comparison basis.

**Required move:** Map each source to baseline, gap, method justification, or interpretation. Remove papers that perform none of these jobs.

**Rules:** `RES-002`, `RES-024`, `RES-038`.

## 6. Exact quotation alignment

**Source pattern:** Probet literature notes separated PDF location, readable original passage, interpretation, transferable insight, and `cannot copy` boundary.

**Failure risk:** Nearby text from the right page can appear authoritative even when it does not state the attached proposition.

**Required move:** Mark the proposition `unverified` until the exact readable sentence is located. Separate source result from project inference.

**Rules:** `RES-019`, `RES-020`, `RES-021`.

## 7. Benchmark generalization wall

**Source pattern:** Probet notes on landscape features stressed that strong benchmark separation can fail under unseen functions, dimensions, sampling regimes, or generators.

**Failure risk:** Stable labels on one benchmark are renamed general structural understanding.

**Required move:** Name benchmark, dimension, sampling, seeds, and held-out design. Without independent transfer evidence, call the result benchmark-conditional.

**Rules:** `RES-008`, `RES-012`, `RES-014`, `RES-043`.

## 8. API completeness without factual authority

**Source pattern:** An algorithm API page contained polished bilingual headings, examples, defaults, class paths, and recommendations, but several acronym expansions and import paths did not match code or primary papers.

**Failure risk:** Documentation completeness creates false confidence in factual accuracy.

**Required move:** Resolve every identity and API fact from importable objects, tests, source, or primary documentation. Remove performance rankings without benchmark evidence.

**Rules:** `RES-017`, `RES-022`, `RES-043`.

## 9. Affine expression called bilinear

**Source pattern:** A conic chapter defined `T(M,N)=E(M,N)-1` and called `T` bilinear. The zero-vector test gives `T(0,N)=-1`, so bilinearity fails.

**Failure risk:** The prestigious term licenses invalid distribution in later proofs.

**Required move:** Keep `E` as the bilinear form; call `T` a symmetric affine two-point expression and state only the affine-combination identity actually used.

**Rules:** `RES-025`, `RES-026`, `RES-033`, `RES-044`.

## 10. Special cases promoted to an envelope

**Source pattern:** Several symmetric or limiting configurations matched a circle, after which the full envelope was declared to be that circle.

**Failure risk:** Compatibility at finitely many parameters proves neither uniqueness nor global correspondence.

**Required move:** Derive the general line-coefficient locus or a degree/uniqueness result; recover every admissible parameter and treat degeneracies.

**Rules:** `RES-028`, `RES-030`, `RES-035`.

## 11. Elimination promoted to exact locus

**Source pattern:** Eliminating a parameter from `F=0` and `F_s=0` produced `G=0`, which was immediately called the exact envelope.

**Failure risk:** Division, squaring, resultants, and algebraic closure may add branches or remove exceptional parameters.

**Required move:** First claim containment only. Upgrade to equality after parameter recovery and back-substitution; upgrade to envelope after regularity and tangency checks.

**Rules:** `RES-029`, `RES-030`, `RES-034`.

## 12. Local expansion promoted to global sign

**Source pattern:** A calculus proof listed Taylor terms near zero and concluded positivity for every positive argument.

**Failure risk:** No signed remainder, middle-interval certificate, or tail threshold covers the universal domain.

**Required move:** Partition near-zero, compact-middle, and tail regions. Downgrade to local positivity if any region remains uncovered.

**Rules:** `RES-027`, `RES-028`, `RES-036`.

## 13. Object identity changes mid-proof

**Source pattern:** A primitive, original function, interpolating polynomial, and remainder function exchanged symbols between definitions and differentiated equations.

**Failure risk:** A valid theorem may be applied to the wrong derivative order or regularity class.

**Required move:** Build an object ledger and recompute the proof from the intended object. A one-letter correction is insufficient.

**Rules:** `RES-025`, `RES-026`, `RES-031`, `RES-033`.

## 14. Asymptotics used as a base-case proof

**Source pattern:** `Exponential growth dominates a cubic` was used to prove an inequality for every integer from a named small index.

**Failure risk:** Eventual dominance provides neither the threshold nor finite initial cases.

**Required move:** Verify the base range, establish a concrete threshold, and prove persistence by ratio, difference, induction, or monotonicity.

**Rules:** `RES-027`, `RES-028`, `RES-034`.

## 15. Zeros lost through a quotient

**Source pattern:** A differential identity was divided by the unknown function and integrated as `log|y|` over the original interval.

**Failure risk:** The transformed equation is valid only on connected nonzero components; zero solutions and component-specific constants disappear.

**Required move:** Split at the zero set, solve on each component, and check zero/crossing solutions in the original equation.

**Rules:** `RES-031`, `RES-032`.

## 16. Underdetermination preserved honestly

**Source pattern:** One independent condition fixed one constant while another remained free. The solution reported a one-parameter family.

**Useful behavior:** The document resisted inventing a boundary condition for narrative closure.

**Required move:** Count constraints, state the family, and name the additional observation required for uniqueness.

**Rules:** `RES-008`, `RES-031`, `RES-037`.

## 17. Version residue after a claim pivot

**Source pattern:** A paper narrowed its central mechanism, but older abstracts, plans, captions, and appendices retained stronger language or incompatible experiment IDs.

**Failure risk:** A final disclaimer coexists with active contradictory claims.

**Required move:** Maintain a replacement ledger and search the entire version family for each superseded phrase, metric, ID, and recommendation.

**Rules:** `RES-001`, `RES-006`, `RES-023`.
