# Research Validation Gates

## Contents

1. Gate 0 - task, authority, and manuscript readiness
2. Gate 1 - provenance
3. Gate 2 - fact and notation lock
4. Gate 3 - novelty
5. Gate 4 - proof integrity
6. Gate 5 - experiment and quantitative reconciliation
7. Gate 6 - claim-evidence alignment
8. Gate 7 - source and citation alignment
9. Gate 8 - version and cross-reference integrity
10. Gate 9 - structure and rhetoric
11. Gate 10 - mechanical integrity
12. Gate 11 - final regression
13. Reusable forms

Run gates in order. Record `PASS`, `FAIL`, or `NOT RUN` with named evidence. Never infer a later gate from an earlier one.

## 1. Gate 0 - task, authority, and manuscript readiness

Record:

```text
operation: audit / rewrite / generate
authority manuscript:
authority code/data/results/bibliography:
historical or supporting artifacts:
genre and target reader:
preserve exactly:
unavailable evidence:
```

### Fail conditions

- current authority cannot be identified;
- the abstract is absent or only a token fragment;
- a top-level section or promised contribution list has no substantive content;
- TODO, TBD, editorial placeholders, duplicate labels, dangling internal references, or venue-template author/header identities remain in the submission artifact;
- evidence is selected from conflicting runs or drafts;
- venue requirements are invented;
- audit is silently converted into a rewrite;
- publication prose and editorial plans are intentionally mixed without labels.

Do not treat this as a word-count quality score. It is a paper-shell precondition: once the shell is complete, the later novelty, proof, evidence, and composition gates still decide whether any claim is supportable.

Routes: `RES-001`, `RES-006`, `RES-049`.

## 2. Gate 1 - provenance

Build a segment table:

| Location | Label | Source | State | Attribution confidence | Editable | Notes |
|---|---|---|---|---|---|---|

Labels: `ARG`, `SRC`, `QUO`, `TRN`, `OCR`, `DAT`, `GEN`, `EDT`, `VER`.

### Checks

- inherited statements are separated from generated solutions;
- source quotations and translations are preserved;
- OCR uncertainty is marked;
- editorial commands remain outside the manuscript;
- stale version passages are not treated as current evidence.

### Fail conditions

- a core source has unknown identity;
- generated text silently alters quoted material;
- style conclusions rely on unattributable source text;
- reconstructed content is called official.

Routes: `RES-018`, `RES-021`.

## 3. Gate 2 - fact and notation lock

Create before editing:

| Item | Type/class | Definition/value | Domain/unit | Scope | Authority | All locations | Conflict |
|---|---|---|---|---|---|---|---|

Include numbers, denominators, metrics, budgets, seeds, exclusions, algorithm identities, symbols, equations, theorem statements, negative results, and status labels.

### Checks

- normalized and original quantities differ;
- one symbol has one object and derivative order;
- table and prose values agree;
- algorithm names and versions are stable;
- primary endpoints do not drift;
- precision matches identification.

### Fail policy

Do not select the newest-looking or smoothest value. Keep the conflict open until authority resolves it.

Routes: `RES-015`, `RES-022`, `RES-023`, `RES-025`, `RES-026`.

## 4. Gate 3 - novelty

Build:

| Claim | Type | Closest prior capability | Exact delta | Evidence | Search boundary | Allowed wording |
|---|---|---|---|---|---|---|

### Checks

- each contribution has a distinct operation and evidence;
- priority claims have documented search scope;
- closest baselines are included;
- prototype, implementation, theory, and result are not conflated;
- contribution language is consistent across title, abstract, body, and conclusion;
- weak bullets are removed rather than inflated.

### Fail conditions

- core novelty has no baseline;
- `first` or `unprecedented` has no search boundary;
- prototype performance is claimed without evaluation;
- observed benchmark separation is called a general theory.

Routes: `RES-002`-`RES-007`, `RES-024`.

## 5. Gate 4 - proof integrity

### Object ledger

| Symbol | Object/type | Definition | Domain/regularity | Dependence | Allowed operations | Conflict |
|---|---|---|---|---|---|---|

### Fragile transformation ledger

| Step | Before | Operation | Conditions | Lost factor/domain | Added branch | Direction | Back-check |
|---|---|---|---|---|---|---|---|

### Theorem ledger

| Theorem | Assumptions | Where verified | Conclusion used | Valid |
|---|---|---|---|---|

### Local-to-global coverage

| Region/index range | Certificate | Remainder/threshold | Endpoint/base check | Valid |
|---|---|---|---|---|

### Elimination/envelope candidates

| Branch | Production step | Parameter recovered | Back-substitution | Real/regular | Gradients | Keep/exclude |
|---|---|---|---|---|---|---|

### Mandatory checks

1. Recompute decisive signs, coefficients, exponents, and derivatives.
2. Preserve object and witness identity.
3. State theorem assumptions at use.
4. Split zeros, branches, signs, and orientations.
5. Cover every interval or integer range.
6. Record elimination direction and reverse recovery.
7. Verify envelope real existence, repeated-root condition, regularity, gradients, and degeneracies.
8. Justify every approximation and its error.
9. Expand `similarly` when the branch carries a conclusion.
10. Leave underdetermined results as families.

### Fail policy

Any failure carrying a theorem, global sign, exact locus, or central mechanism is Blocking. Do not polish around it.

Routes: `RES-025`-`RES-037`.

## 6. Gate 5 - experiment and quantitative reconciliation

Build:

| Run/comparison | Changed factors | Fixed factors | Budget mode | Endpoint | Sample/seeds | Exclusions | Claim supported |
|---|---|---|---|---|---|---|---|

### Checks

- independent and shared budgets are separated;
- preprocessing/decomposition cost is explicit;
- sample totals and denominators reconcile;
- primary and auxiliary endpoints are labeled;
- stopping and target criteria are predeclared;
- nulls, reversals, and failed runs are retained;
- statistical language names test and uncertainty;
- stored and displayed precision are distinct;
- calibration, sensitivity, held-out, and external validation are not renamed.

### Fail conditions

- decisive factors change together without acknowledgment;
- result uses a different run family than methods;
- metric reversal is hidden behind general superiority;
- negative result is removed from abstract or conclusion;
- a simulation is written as observed reality.

Routes: `RES-008`-`RES-017`, `RES-023`.

## 7. Gate 6 - claim-evidence alignment

Build for every title, abstract, and conclusion claim:

| Claim | Verb | Evidence | Level | Endpoint/domain | Counterevidence | Boundary | Revision |
|---|---|---|---|---|---|---|---|

Evidence order: proof, external validation, held-out test, controlled comparison, sensitivity, calibration, observation, heuristic, expectation.

### Checks

- claim exists in body evidence;
- endpoint, domain, and metric match;
- mechanism and causality are distinguished;
- approximation cannot exceed its domain;
- negative evidence changes wording;
- limitation states how inference changes;
- abstract remains below the strongest body evidence.

Routes: `RES-008`, `RES-009`, `RES-012`-`RES-016`, `RES-039`, `RES-047`.

## 8. Gate 7 - source and citation alignment

Build:

| Proposition | Source | Exact passage/fact | Assumptions | Location | Match | Action |
|---|---|---|---|---|---|---|

### Checks

- citation is adjacent to one proposition;
- exact source language is readable;
- paraphrase preserves modality and scope;
- source result and current inference are distinct;
- related work covers the closest baseline;
- software facts match code/tests/primary papers;
- no citation metadata or quote is invented.

### Fail policy

Mark `unverified` when the exact supporting passage cannot be found. Page proximity and polished documentation do not pass.

Routes: `RES-019`-`RES-024`.

## 9. Gate 8 - version and cross-reference integrity

### Version family

| Family | Files | Authority | Historical | Active claims | Conflicts |
|---|---|---|---|---|---|

### Claim migration

| Old claim | New claim | Delete/retain/replace | Locations updated | Verified |
|---|---|---|---|---|

### Checks

- title, abstract, contributions, captions, and conclusion use current claims;
- IDs, labels, equations, tables, and appendices resolve;
- result paths point to authority exports;
- historical drafts are labeled;
- code/pseudocode/manuscript describe one method version.

Routes: `RES-001`, `RES-006`, `RES-023`.

## 10. Gate 9 - structure and rhetoric

### Section map

| Section | Reader question | Unique claim | Evidence | Boundary | Duplicate | Action |
|---|---|---|---|---|---|---|

### Checks

- related work is selective by claim dependency;
- methods and results perform distinct jobs;
- decisive evidence receives the most space;
- balanced treatment is not mechanically symmetric;
- one full statement provides information exit;
- conclusion synthesizes robust, conditional, negative, and unresolved findings;
- evaluative adjectives have criteria;
- management, marketing, reviewer, and classroom voices are absent;
- blacklist search is followed by whole-argument reading.

Routes: `RES-038`-`RES-048`.

## 11. Gate 10 - mechanical integrity

Check when in scope:

- TeX/Markdown syntax and encoding;
- labels, references, citations, and bibliography keys;
- equations and tables preserved through rewrite;
- headings and numbering;
- source paths and code identifiers;
- no placeholder, editorial instruction, or conversion residue in submission text.

Compilation passes only syntax/build integrity. It does not establish proof, source, or research correctness.

Routes: `RES-017`, `RES-023`.

## 12. Gate 11 - final regression

Compare original and revised artifacts.

### Preservation

- no number, equation, citation, condition, negative result, or quotation changed without an authorized correction;
- no claim strengthened;
- no new fact, source, experiment, or reviewer reaction invented;
- all deleted claims appear in the change ledger.

### Improvement

- authority is singular;
- novelty is a bounded delta;
- claims match evidence and endpoints;
- proof gaps are repaired or explicitly unresolved;
- citations align proposition by proposition;
- negative evidence propagates;
- structure follows evidence rather than a template;
- rhetoric is restrained.

### Final declaration

```text
Authority: PASS/FAIL
Provenance: PASS/FAIL
Facts and notation: PASS/FAIL
Novelty: PASS/FAIL
Mathematics: PASS/FAIL/NOT APPLICABLE
Experiment/quantities: PASS/FAIL/NOT APPLICABLE
Claim-evidence: PASS/FAIL
Sources/citations: PASS/FAIL/NOT CHECKED
Versions/references: PASS/FAIL
Structure/rhetoric: PASS/FAIL
Mechanical integrity: PASS/FAIL/NOT RUN
Unresolved blockers:
```

## 13. Reusable forms

### Full audit finding

```markdown
| Rule | Severity | Location | Claim/passage | Failure | Consequence | Required action |
|---|---|---|---|---|---|---|
```

### Change ledger

```markdown
| Change | Location | Rule | Original function | Action | Evidence preserved | Open issue |
|---|---|---|---|---|---|---|
```

### Evidence request

```markdown
| Claim | Missing authority/evidence | Why prose cannot decide | Minimum resolution |
|---|---|---|---|
```

### Approximation ledger

```markdown
| Approximation | Target | Assumptions | Error/sensitivity | Valid domain | Dependent claims |
|---|---|---|---|---|---|
```

### Completion-state ledger

```markdown
| Artifact | Drafted | Source-aligned | Compiled | Reproduced | Mathematically checked | Externally validated | Evidence |
|---|---|---|---|---|---|---|---|
```
