# Research Writing Rule Library

## Scene ownership and prohibited use

Every `RES-*` rule has the unique owner `research_journal`. It applies to a
journal/research segment or to a local novelty/proof claim explicitly borrowed
by another scene. It is prohibited as a replacement for:

- NOTE teaching standards: do not impose novelty searches, journal abstracts,
  or maximal compression on ordinary course notes;
- MOD engineering standards: do not replace model-code, parameter, protocol,
  solver, and numerical-error checks with rhetorical research rigor;
- CORE integrity: research selectivity never permits omitted source identity,
  contradictory facts, invalid mathematics, or hidden negative results.

Each rule below inherits this owner and prohibition even when the individual
entry does not repeat it.

## Contents

1. Severity and use
2. Authority and novelty
3. Evidence and experiment
4. Sources and factual alignment
5. Proof integrity
6. Structure and composition
7. Research-specific blacklist
8. Delivery contract

## 1. Severity and use

`MUST` failures block acceptance when they invalidate a central claim, interpretation, proof, or reproducibility. Other `MUST` failures are Major. `SHOULD` failures are Moderate unless repeated enough to distort the paper. Cosmetic issues are Minor.

Apply rules in this order: authority, contradiction, provenance, novelty, evidence, mathematics, section responsibility, paragraph hierarchy, sentence restraint.

## 2. Authority and novelty

### RES-001 Declare the authority version (`MUST`)

Identify one current manuscript, data snapshot, code revision, and result export. Do not merge convenient claims from incompatible drafts.

### RES-002 Define novelty against an explicit baseline (`MUST`)

State what prior work already does, what precise decision or capability remains absent, and what operation the present work adds. `Novel` is not a synonym for recent implementation.

### RES-003 Separate contribution types (`MUST`)

Classify each contribution as question, theory, method, system, data, experiment, synthesis, or negative finding. Do not advertise a recombination, prototype, or benchmark observation as a new general theory.

### RES-004 Bound novelty-search claims (`MUST`)

Use `to our knowledge` only with a stated search boundary, date, databases or venues, and comparison criterion. Otherwise describe the concrete difference without priority language.

### RES-005 Keep prototypes outside evaluated claims (`MUST`)

An implemented prototype demonstrates feasibility of an operation, not performance, robustness, or superiority. Label unevaluated components and future work explicitly.

### RES-006 Replace superseded claims everywhere (`MUST`)

When evidence narrows a claim, update title, abstract, contribution list, results, discussion, conclusion, captions, and appendices. A late disclaimer does not neutralize an earlier overclaim.

### RES-007 Prefer selectivity to contribution inflation (`SHOULD`)

Retain only contribution bullets that carry distinct evidence. Merge implementation detail into methods and delete weak bullets that exist only to create symmetry.

## 3. Evidence and experiment

### RES-008 Match claim strength to the evidence ladder (`MUST`)

Use, in descending order, formal proof, independent external validation, held-out test, controlled comparison, sensitivity analysis, calibration, observation, heuristic, and expectation. Do not promote a lower level through wording.

### RES-009 Keep endpoint claims endpoint-specific (`MUST`)

Name metric, time or budget, aggregation, and direction. Better final precision does not imply better early progress, cost, sample efficiency, or all-metric performance.

### RES-010 Isolate comparison factors (`MUST`)

List changed and fixed factors. If budgets, backends, seeds, preprocessing, or data change together, prohibit single-factor causal language.

### RES-011 Distinguish independent and shared budgets (`MUST`)

State whether preprocessing or decomposition cost is charged to the optimization budget. Use independent-budget evidence for grouping quality and shared-budget evidence for end-to-end resource efficiency; do not collapse them.

### RES-012 Preserve negative and boundary results (`MUST`)

Report counterexamples, null results, family boundaries, metric reversals, and failed robustness beside the claim they narrow.

### RES-013 Separate observation, mechanism, and causality (`MUST`)

Report the pattern first. Mark a mechanism as interpretation unless the design or proof excludes relevant alternatives.

### RES-014 Justify approximation and modeling transfer (`MUST`)

State approximation target, assumptions, error or sensitivity, parameter identification, and domain. A simulation or local model cannot be written as empirical reality or theorem-level truth without independent support.

### RES-015 Match precision to identification (`MUST`)

Separate stored computational precision from displayed inferential precision. Report uncertainty or sensitivity when inputs are calibrated, normalized, assumed, or weakly identified.

### RES-016 Predeclare acceptance language (`MUST`)

Words such as `validated`, `consistent`, `significant`, `robust`, and `passes` require a criterion defined independently of the observed result.

### RES-017 Keep workflow states separate (`MUST`)

Compiled, transcribed, lint-clean, reproducible, mathematically checked, and externally validated are distinct states. Never infer a later state from an earlier one.

## 4. Sources and factual alignment

### RES-018 Map passage-level provenance (`MUST`)

Label author argument, inherited prompt, quotation, translation, OCR, generated explanation, code/data, editorial plan, and stale version. File-level provenance does not establish sentence authorship.

### RES-019 Cite propositions, not paragraphs (`MUST`)

Place each citation beside the proposition it supports. Split a sentence when different clauses require different sources.

### RES-020 Align quotations with exact source language (`MUST`)

Confirm that readable source text states the attached proposition under compatible assumptions. Page proximity, keyword overlap, or approximate OCR is not sufficient.

### RES-021 Distinguish source result from current inference (`MUST`)

Mark quotation, faithful paraphrase, synthesis, transfer hypothesis, and present-study result separately. Do not make a cited paper appear to endorse the current mechanism.

### RES-022 Verify software and API facts against authority (`MUST`)

Check algorithm identities, acronym expansions, import paths, defaults, return values, implemented features, and performance claims against code, tests, primary papers, or official documentation.

### RES-023 Reconcile numbers and denominators (`MUST`)

Check every reported value across abstract, text, tables, figures, appendices, and conclusion. Keep object, unit, denominator, version, and rounding rule stable.

### RES-024 Use a selective related-work dependency map (`SHOULD`)

Include sources needed to define the baseline, establish the gap, justify the method, or interpret results. Do not turn related work into an exhaustive catalog or repeat common project background for every paper.

## 5. Proof integrity

### RES-025 Define and type every mathematical object (`MUST`)

Record symbol, type, domain, regularity, units where relevant, parameter dependence, and first definition. Do not silently replace a normalized quantity with the original object.

### RES-026 Lock object identity through the proof (`MUST`)

Functions, derivatives, primitives, interpolants, random variables, points, vectors, affine coordinates, and homogeneous representatives must not exchange roles.

### RES-027 State theorem conditions at use (`MUST`)

Verify regularity, domain, independence, convergence, nondegeneracy, or invertibility when invoking a theorem. Familiar names do not supply missing hypotheses.

### RES-028 Cover local-to-global claims completely (`MUST`)

A Taylor expansion, finite sample, numerical grid, or leading asymptotic term cannot prove a global sign or universal property. Supply a signed remainder and complete interval or index coverage.

### RES-029 Make elimination reversible (`MUST`)

Record original conditions, operation, divided factors, denominator restrictions, introduced branches, implication direction, parameter recovery, and back-substitution.

### RES-030 Prove envelope and tangency regularity (`MUST`)

Verify smooth parameter dependence, real common points, repeated-root or parameter-derivative conditions, admissible parameter recovery, nonzero gradients, gradient collinearity, and singular or endpoint cases.

### RES-031 Preserve quantifiers and witness dependence (`MUST`)

Keep universal, existential, local, random, and data-dependent quantities distinct. Independent witnesses cannot be reused as one common value.

### RES-032 Treat zeros, branches, signs, and orientation (`MUST`)

Before division, logarithms, roots, inverse functions, or oriented integrals, split the domain and retain component-specific constants, signs, and branches.

### RES-033 Verify decisive algebra independently (`MUST`)

Recompute signs, coefficients, exponents, derivative orders, indices, denominators, and equality directions. A fluent chain or CAS output is not verification.

### RES-034 Expose the conclusion-carrying step (`MUST`)

Show the decisive factorization, coefficient relation, bound, branch exclusion, or uniqueness argument. Move only routine reversible algebra to an appendix.

### RES-035 Prohibit classroom looseness in research proof (`MUST`)

Do not use `similarly`, `obvious`, a diagram, several examples, or an answer choice to replace a proof obligation. Explain why the omitted case is structurally identical or prove it separately.

### RES-036 Prohibit unjustified modeling approximation (`MUST`)

Do not transfer a numerical approximation, surrogate, local linearization, or fitted model into a formal proof or real-world causal claim without a justified error and scope.

### RES-037 Leave underdetermined results non-unique (`MUST`)

Count constraints and degrees of freedom. Report the admissible family and missing condition instead of choosing a convenient value for narrative closure.

## 6. Structure and composition

### RES-038 Assign distinct section responsibilities (`MUST`)

Introduction frames the gap and contribution; methods define operations; results report evidence; discussion interprets and bounds it; conclusion synthesizes supported claims.

### RES-039 Keep the abstract below the evidence ceiling (`MUST`)

Every abstract claim must appear in the body with equal or stronger evidence and the same endpoint, domain, and boundary.

### RES-040 Build balanced but non-mechanical structure (`SHOULD`)

Balance competing evidence and alternatives, but do not force identical paragraph lengths, three-item lists, or matching advantage/limitation blocks when evidence is unequal.

### RES-041 Put evidence adjacent to claims (`MUST`)

Place equations, values, confidence intervals, citations, or counterevidence next to the proposition they qualify.

### RES-042 Establish an information exit (`SHOULD`)

State a claim and its boundary fully once. Later sections must add evidence, interpretation, or consequence rather than paraphrase it.

### RES-043 Use restrained evaluative language (`MUST`)

`Novel`, `effective`, `significant`, `robust`, `accurate`, `general`, and `state of the art` require explicit comparisons and criteria.

### RES-044 Keep terminology stable and standard (`MUST`)

Use one term per concept. Define nonstandard terms through standard objects and exact equivalence, or remove them.

### RES-045 Write with research voice (`SHOULD`)

Remove project-management, reviewer-simulation, customer-service, coaching, and marketing voice from submission prose.

### RES-046 Synthesize rather than enumerate in the conclusion (`MUST`)

Separate robust findings, conditional findings, negative results, unresolved questions, and supported implications. Do not repeat the table of contents or introduce evidence.

### RES-047 Bind limitations to inference (`SHOULD`)

Name which claim, dataset, backend, theorem condition, or parameter range each limitation affects and how the conclusion changes.

### RES-048 Keep figures and tables evidentiary (`SHOULD`)

State comparison basis, uncertainty, sample count, and the claim shown. Do not explain that a figure helps the reader or use a plot as the sole proof of a numerical claim.

### RES-049 Reject paper shells before humanization (`MUST`)

Do not run a prose-humanization pass over an unfinished submission shell. An empty or token abstract, an empty top-level section, a promised but absent contribution list, unresolved editorial placeholder, duplicate label, dangling internal reference, or venue-template author/header residue must be repaired from research evidence first. Passing this readiness check does not prove novelty, mathematics, experiments, or writing quality.

## 7. Research-specific blacklist

Treat the list as a locator, never as an acceptance gate.

| Blacklisted use | Required replacement |
|---|---|
| `first-ever`, `unprecedented`, `groundbreaking`, `paradigm-shifting` | bounded comparison to named prior capability and search scope |
| `fills a gap`, `solves the problem` | exact unresolved decision and measured result |
| `clearly`, `obviously`, `undeniably`, `without doubt` | equation, test, source, or delete |
| `fully validates`, `proves effectiveness`, `demonstrates superiority` | criterion, endpoint, scope, and comparison |
| `state-of-the-art` | benchmark, protocol, date, baselines, and uncertainty |
| `robust` | perturbed dimensions, fixed dimensions, range, and result |
| `general` or `universal` | verified domain and excluded cases |
| `mechanism` | tested causal relation or explicitly labeled interpretation |
| `closed loop`, `roadmap`, `lock`, `release-ready`, `storyline` | actual research operation or remove |
| `perfect`, `miraculous`, `ironclad`, `collapses beautifully` | exact algebraic event |
| `similarly`, `routine`, `straightforward` at a decisive step | explicit structural equivalence or proof |
| `after simplification` before the conclusion | decisive equation, factor, and conditions |

Also audit repetitive shells: `It is worth noting`, `Importantly`, `Taken together`, `In conclusion`, repeated claim-evidence-boundary triplets, and forced `first/second/third` contribution lists.

## 8. Delivery contract

For each finding record:

```text
rule | severity | exact location | claim/passsage | evidence
failure | consequence | required action | unresolved source/data request
```

Do not declare acceptance while a blocking rule remains. Report `NOT RUN` rather than inferring a gate from compilation, formatting, lexical scans, or another check.
