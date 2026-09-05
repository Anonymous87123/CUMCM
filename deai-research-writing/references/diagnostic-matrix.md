# Research Manuscript Diagnostic Matrix

## Contents

1. Finding format and severity
2. Authority and provenance
3. Novelty and contribution
4. Claim-evidence alignment
5. Mathematical validity
6. Sources and citations
7. Quantitative consistency
8. Structure and composition
9. Rhetorical restraint
10. Scoring and delivery

## 1. Finding format and severity

Record:

```text
rule | severity | exact location | excerpt or claim | passage function
evidence available | failure | consequence | action | unresolved request
```

Severity:

- `Blocking`: invalid core proof, contradictory authority, fabricated or unsupported core novelty, source mismatch that carries a central claim, confounded decisive experiment, or missing definition that prevents interpretation.
- `Major`: other `MUST` failure affecting claim strength, reproducibility, terminology, or source alignment.
- `Moderate`: `SHOULD` structure, hierarchy, or rhetorical failure.
- `Minor`: local polish without claim consequences.

Do not call prose `AI-like` without an observable feature and research consequence.

## 2. Authority and provenance

### Authority table

| Artifact | Current authority | Version/date | Conflicts | Decision |
|---|---|---|---|---|
| manuscript | | | | |
| code | | | | |
| data | | | | |
| result export | | | | |
| bibliography | | | | |

### Segment labels

Use `ARG` author argument, `SRC` inherited source, `QUO` quotation, `TRN` translation, `OCR` transcription, `DAT` code/data output, `GEN` generated explanation, `EDT` editorial plan, and `VER` stale version.

### Fail indicators

- result values drawn from incompatible runs;
- old contribution claims survive after a method pivot;
- questions or quotations counted as author prose;
- plan commands copied into publication text;
- `latest` selected without reconciling authority.

Routes: `RES-001`, `RES-006`, `RES-018`, `RES-023`.

## 3. Novelty and contribution

### Novelty ledger

| Contribution | Type | Prior capability | Exact gap | New operation | Evidence | Search boundary | Status |
|---|---|---|---|---|---|---|---|

### Tests

1. Can the delta be stated without `novel`, `first`, or `framework`?
2. Does each contribution have distinct evidence?
3. Is an implementation being mistaken for a method or theory?
4. Is an evaluated result being generalized beyond its endpoint?
5. Does related work include the closest operational baseline?
6. Is priority language supported by a documented search?

### Fail indicators

- three contribution bullets manufactured from one operation;
- prototype listed as validated method;
- benchmark observation called a general mechanism;
- search-free `first-ever` claim;
- contribution changes between abstract and method.

Routes: `RES-002`-`RES-007`, `RES-024`.

## 4. Claim-evidence alignment

### Claim matrix

| Claim | Strength verb | Evidence class | Endpoint/domain | Changed factors | Fixed factors | Counterevidence | Allowed wording |
|---|---|---|---|---|---|---|---|

### Evidence classes

`proof > external validation > held-out test > controlled comparison > sensitivity > calibration > observation > heuristic > editorial expectation`

### Tests

- primary endpoint is declared and stable;
- budget mode and denominator are explicit;
- mechanism is separated from association;
- negative and reversed metrics are visible;
- approximation scope and error are stated;
- precision matches identification;
- acceptance criteria predate the result.

### Fail indicators

- final metric superiority becomes general superiority;
- shared and independent budgets are called the same comparison;
- pooled correlation becomes causality;
- one benchmark becomes general validity;
- a limitation sentence substitutes for missing evidence.

Routes: `RES-008`-`RES-017`, `RES-039`.

## 5. Mathematical validity

### Object ledger

| Symbol | Type | Definition | Domain/regularity | Dependence | Allowed operations | Conflict |
|---|---|---|---|---|---|---|

### Transformation ledger

| Step | Before | Operation | Conditions | Lost domain/factor | Added branch | Direction | Back-check |
|---|---|---|---|---|---|---|---|

### Coverage ledger

| Region/index range | Certificate | Assumptions | Endpoint/base handling | Verified |
|---|---|---|---|---|

### Theorem ledger

| Theorem | Required assumptions | Where verified | Conclusion used | Valid |
|---|---|---|---|---|

### High-risk tests

- normalized and original objects retain distinct symbols;
- witnesses keep their dependencies;
- quotient and logarithm zeros are split out;
- signs and inequality directions are recorded;
- local series has a signed remainder and full-domain continuation;
- asymptotic claims include threshold and base cases;
- elimination records direction and back-substitution;
- envelope claims include real recovery, gradients, regularity, and degeneracy;
- nonstandard terminology passes its defining tests;
- CAS output exposes assumptions and factors.

Any failed decisive test is Blocking.

Routes: `RES-025`-`RES-037`.

## 6. Sources and citations

### Proposition table

| Proposition | Citation/source | Exact source statement | Assumptions match | Location | Action |
|---|---|---|---|---|---|

### Tests

- citation sits beside one proposition;
- quoted text is readable and exact;
- paraphrase preserves scope and modality;
- present inference is marked separately;
- search coverage is documented;
- API facts match code or primary authority;
- source metadata is not invented.

### Fail indicators

- nearby OCR presented as exact support;
- paper title used as evidence for a proposition;
- cited work made to endorse the current mechanism;
- polished API table with nonexistent class path;
- performance stars without benchmark evidence.

Routes: `RES-018`-`RES-024`.

## 7. Quantitative consistency

### Fact lock

| Fact/value | Class | Object/unit | Scope | Source export | All locations | Conflict |
|---|---|---|---|---|---|---|

Classify values as observed, calibrated, assumed, simulated, derived, or display-only.

### Tests

- rows and subgroups reconcile with totals;
- denominators remain fixed across percentages;
- exclusions and missing runs are listed;
- seeds and repeats match methods;
- budgets include or exclude preprocessing consistently;
- table, figure, abstract, and conclusion values match;
- displayed digits are justified;
- negative runs are retained.

Routes: `RES-009`-`RES-016`, `RES-023`, `RES-048`.

## 8. Structure and composition

### Section responsibility map

| Section | Reader question | Unique claim | Evidence | Boundary | Duplicates | Action |
|---|---|---|---|---|---|---|

### Paragraph labels

Use `GAP`, `DEF`, `MTH`, `OBS`, `EVD`, `CMP`, `INT`, `BND`, `SYN`, or `TRN`.

### Tests

- introduction derives contribution from a concrete gap;
- related work follows claim dependencies;
- methods do not pre-report favorable results;
- results report counterevidence before interpretation;
- discussion considers alternatives rather than relisting numbers;
- conclusion separates robust, conditional, negative, and unresolved findings;
- decisive evidence receives more space than routine setup;
- repeated claims have one authority location;
- balance reflects evidence rather than a template.

Routes: `RES-038`-`RES-042`, `RES-046`-`RES-048`.

## 9. Rhetorical restraint

### Locator categories

- novelty theater: `first-ever`, `unprecedented`, `groundbreaking`;
- certainty theater: `clearly`, `obviously`, `undeniably`, `fully validates`;
- universal evaluation: `effective`, `robust`, `general`, `state of the art`;
- management voice: `roadmap`, `lock`, `closed loop`, `release-ready`;
- classroom shortcut: `similarly`, `routine`, `straightforward` at a decisive step;
- mechanical symmetry: repeated three-part lists, identical contribution and limitation blocks;
- generic shell: repeated `Importantly`, `Taken together`, `It is worth noting`.

### Diagnosis

For each locator ask whether it hides a missing baseline, criterion, proof step, source, object, or boundary. A zero keyword count is not acceptance.

Routes: `RES-007`, `RES-035`, `RES-040`, `RES-043`-`RES-045`.

## 10. Scoring and delivery

Score only after blockers are reported:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Authority | conflicting | partial | one reconciled authority |
| Provenance | mixed | partly labeled | passage-level clear |
| Novelty | inflated/unknown | bounded but incomplete | explicit baseline and evidence |
| Evidence | claims exceed data | mostly aligned | endpoint/scope/counterevidence explicit |
| Mathematics | invalid | unverified gaps | independently checked |
| Sources | mismatched | incomplete | proposition-level aligned |
| Quantities | contradictory | partly reconciled | locked and reproducible |
| Structure | template-driven | mixed | evidence-shaped and selective |
| Rhetoric | theatrical | occasional | restrained and concrete |
| Versioning | stale conflicts | partial | current authority propagated |

Any Blocking finding means FAIL regardless of score. Do not report a scientific `human-likeness` score.

### Delivery order

1. Blocking findings.
2. Authority/provenance and novelty ledgers.
3. Claim-evidence and proof gaps.
4. Structure and rhetorical findings.
5. Representative rewrites.
6. Evidence requests.
7. Gate summary.
