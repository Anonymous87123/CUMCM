# Journal-Level Research Playbook

## Contents

1. Shared journal contract
2. Empirical and experimental paper
3. Algorithm and systems paper
4. Mathematical and theoretical paper
5. Modeling paper
6. Literature synthesis
7. Research-facing technical documentation
8. Audit, rewrite, and generation outputs

## 1. Shared journal contract

A journal-level manuscript must make a bounded, nontrivial claim and show why the available evidence is sufficient for that claim. Selectivity is part of rigor: omit claims, references, tables, and sections that do not change the argument.

Build this map before drafting:

```text
research question
-> prior capability
-> exact unresolved gap
-> contribution type and operation
-> evidence needed to discriminate the claim
-> observed result and counterevidence
-> valid scope
-> unresolved test
```

Use an authority ledger for manuscript, code, data, and result exports. Write abstract and conclusion after the evidence-bearing body.

## 2. Empirical and experimental paper

### Contract

Connect each claim to a comparison, controls, metric, sample, uncertainty, decision criterion, and opposite-result interpretation.

### Required evidence map

| Claim | Changed factors | Fixed factors | Endpoint | Budget/sample | Uncertainty | Counterevidence |
|---|---|---|---|---|---|---|

### Sequence

1. Define the observable question and primary endpoint.
2. Explain why the comparison isolates it.
3. Report sample, exclusions, seeds, budget, and stopping rule.
4. Report the primary result before interpretation.
5. Report metric reversals, nulls, and boundary groups.
6. Interpret mechanisms only after alternatives are addressed.
7. State external-validity limits as changes to inference.

### Reject

- significance without a defined test;
- post-hoc endpoint switching;
- one successful seed as robustness;
- pooled correlation as causal proof;
- an image as the sole numerical evidence;
- benchmark performance as universal validity.

### Gate

Pass only when totals reconcile, factors are isolated or named as confounded, negative evidence changes the claim, and abstract language matches the primary endpoint.

## 3. Algorithm and systems paper

### Contract

Identify a concrete capability gap, define the algorithm and invariants, compare against relevant baselines, and report cost, failure modes, implementation status, and evidence scope.

### Required map

```text
existing operation
-> missing decision or guarantee
-> input/output and assumptions
-> algorithm stages and invariants
-> complexity and resource accounting
-> baselines and ablations
-> primary endpoint
-> hostile cases and failure behavior
```

### Innovation test

Ask whether the contribution is a new objective, estimator, decision rule, guarantee, architecture, or merely a recombination. Recombination can be publishable, but novelty must be the verified interaction or capability it creates, not the number of components combined.

### Evidence boundaries

- Pseudocode, prose, implementation, and experiments must describe the same version.
- An ablation removes one component while holding the rest fixed.
- Independent budgets isolate output quality; shared budgets evaluate end-to-end efficiency.
- A prototype proves implementation feasibility only.
- API names and algorithm identities come from code or primary sources.

### Gate

Pass only with one authoritative algorithm, reproducible resource accounting, appropriate baselines, explicit failure behavior, and no unsupported general superiority claim.

## 4. Mathematical and theoretical paper

### Contract

State objects, assumptions, theorem, novelty relative to known results, proof architecture, exceptional cases, and the exact logical status of computations.

### Proof map

```text
definitions and domains
-> lemma dependencies
-> decisive construction
-> non-obvious transformation
-> branch/sign/degeneracy analysis
-> theorem conclusion
-> sharpness, counterexample, or boundary
```

### Required ledgers

**Object ledger:** symbol, type, domain, regularity, dependence, allowed operations.

**Transformation ledger:** before, operation, conditions, lost factors, added branches, direction, back-check.

**Coverage ledger:** interval or index range, proof certificate, endpoints, verified status.

### High-risk claims

- Local expansion to global sign: require complete domain coverage.
- Elimination to exact locus: require reverse recovery and substitution.
- Envelope/tangency: require real points, regularity, gradients, parameter correspondence, and degeneracies.
- `Bilinear`, `affine`, `invariant`, or `equivalent`: test the defining property.
- `Similarly`: show the omitted branch uses the same hypotheses and operations.
- CAS: record assumptions and independently interpret factors.

### Gate

Pass only when every theorem condition is verified at use and every universal quantifier has complete coverage. Classroom familiarity, examples, or omitted algebra cannot carry a research claim.

## 5. Modeling paper

### Contract

Explain assumptions, variables, equations, parameter identification, approximation, calibration, validation, sensitivity, results, and transfer limits without confusing model behavior with reality.

### Evidence ladder

```text
observed data
-> assumptions and omitted mechanisms
-> calibrated or assumed parameters
-> model equations
-> in-sample fit
-> held-out or external checks
-> sensitivity and failed robustness
-> conditional implications
```

### Approximation gate

For every approximation state:

- approximated object;
- expansion or discretization parameter;
- error order or empirical sensitivity;
- domain and stability condition;
- downstream claims that depend on it.

Do not apply a modeling approximation to a theorem proof. Do not write simulation as causal empirical fact. Extra decimal digits may be stored for reproduction but not presented as identification precision.

### Gate

Pass only when calibration and validation are separate, negative robustness narrows conclusions, parameter precision is justified, and recommendations do not exceed the modeled and observed scope.

## 6. Literature synthesis

### Contract

Represent sources accurately, compare assumptions and objects, identify the proposition each source supports, and derive a bounded synthesis rather than a catalog.

### Per-source fields

```text
question and object
assumptions and data
method
central result
failure or limit
exact supporting proposition
location in source
transferable operation
non-transferable condition
```

### Synthesis rules

- Put shared background once.
- Organize by propositions or disagreements, not publication order.
- Keep quotations, translations, paraphrases, and current inference distinct.
- Treat nearby OCR as a locator, not evidence.
- Do not force every source to support the current project's preferred mechanism.
- State search boundaries before coverage or novelty claims.

### Gate

Pass only when every material source claim is traceable and each citation has a proposition-level job.

## 7. Research-facing technical documentation

### Contract

Document verified research software without converting API completeness into scientific validity.

### Authority order

```text
importable object and tests
-> implementation source
-> primary algorithm paper
-> official project documentation
-> secondary summary
```

### Checks

- class/import paths exist;
- signatures, defaults, outputs, and side effects match code;
- algorithm names and acronym expansions match primary sources;
- runnable-looking examples use real APIs;
- performance and suitability claims cite defined benchmarks;
- implemented, tested, reproduced, and scientifically validated remain separate.

### Gate

Pass only when every technical identity has authority evidence and recommendation language has comparative data.

## 8. Audit, rewrite, and generation outputs

### Audit

Lead with Blocking findings. Provide exact locations, rule IDs, consequence, repair, and evidence still required. Include novelty and proof ledgers rather than a vague quality score.

### Rewrite

Repair authority, evidence, and proof before style. Preserve facts and negative results. Return a change ledger and unresolved blockers.

### Generate

Draft only from supplied or verified evidence. When evidence is missing, produce a research plan or marked evidence request, not submission-ready claims. Write contribution bullets and abstract last.
