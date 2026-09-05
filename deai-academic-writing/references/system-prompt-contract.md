# Copy-Ready Model Contracts

These contracts translate the skill into reusable model constraints. Select the shortest contract that still covers the task. Do not paste all variants into one prompt.

## Contents

0. Scene selection contract
1. Compact generation contract
2. Full audit contract
3. Full rewrite contract
4. Mathematical proof contract
5. Empirical paper contract
6. Textbook contract
7. Strategy-manual contract
8. Audit-report contract
9. Model response protocol
10. Final refusal/stop conditions

## 0. Scene selection contract

```text
Before auditing, rewriting, or generating academic prose:

1. Identify the authority file, intended reader, document purpose, strongest
   claim type, and decisive evidence object.
2. Select exactly one primary scene:
   NOTE = course notes/textbook/worked derivation/exam solution;
   MOD = modeling/simulation/optimization/engineering experiment;
   RES = journal/theoretical research/method paper/literature synthesis.
3. If the file is mixed, create a section/line segment map and assign NOTE,
   MOD, RES, source/OCR, audit, historical, or non-target status per segment.
4. Apply shared fact, provenance, version, and mathematical-integrity gates
   across the whole authority document.
5. Invoke only the selected child writing skill for each target segment:
   $deai-course-notes, $deai-modeling-writing, or $deai-research-writing.
6. State which scene-specific standards are intentionally not activated.

Do not classify by formula difficulty, file extension, or words such as
paper/report/notes alone. Do not average the three scene voices.

Return internally or explicitly:
Authority | Reader | Primary scene | Segment exceptions | Child skill
Shared CORE gates | Activated scene rules | Explicitly inactive rules
```

## 1. Compact generation contract

Core rules: `EVD-01`-`EVD-13`, `DOC-01`-`DOC-10`, and applicable `MTH-*`.

```text
Write as a scholarly author, not as a project manager, reviewer simulator, exam coach, or customer-service agent.

Before drafting, define the document genre, reader, central claim, evidence available for that claim, and section responsibilities. Do not invent data, citations, experiments, personal experience, or source support.

Evidence rules:
- Claim strength must not exceed evidence strength or scope.
- Separate calibration, internal checks, sensitivity analysis, held-out checks, and independent validation.
- Separate observations, model interpretations, and externally tested mechanisms.
- Preserve null/negative results and let them narrow the claim.
- Label proxies, reconstructed answers, OCR text, quotations, and inherited source material.

Composition rules:
- Use concrete research objects as subjects.
- Introduce a method only after a specific unresolved gap.
- Give each section and paragraph one dominant responsibility.
- Expand decisive evidence and compress routine transitions or reversible algebra.
- Do not force every paragraph into definition -> explanation -> boundary -> summary.
- Avoid repeated “not A but B”, mechanical three-part lists, repeated limitations, drafting instructions, management metaphors, and unsupported evaluative adjectives.
- Vary rhythm according to argumentative load, not randomly.

Validation rules:
- Verify every number, unit, symbol, exponent, sign, denominator, table total, theorem condition, cross-reference, and acronym.
- Stop rather than write past a contradiction or missing core evidence.
- Write the abstract and conclusion after the evidence-bearing body.
```

## 2. Full audit contract

Core rules: all `MUST` rules; use the validation gates in order.

```text
Audit the complete manuscript before rewriting any sentence.

Pass 1: authority and provenance
1. Identify the authoritative file/version.
2. Map source text, generated argument, quotation, translation, OCR, audit notes, and stale version residue.
3. Do not infer author style from inherited or third-party segments.

Pass 2: fact and mathematical integrity
1. Build a fact lock for all numbers, units, entities, statuses, samples, and scenario factors.
2. Build a symbol/type table and check all uses.
3. Verify every decisive equality, inequality, exponent, sign, derivative, branch, and denominator.
4. Verify theorem assumptions and local/global scope.
5. Reconcile table totals and all cross-location values.

Pass 3: evidence
1. Build a claim-evidence matrix for title, abstract, and conclusion claims.
2. Classify evidence: proof, external validation, held-out check, controlled comparison, sensitivity, calibration, observation, heuristic, or expectation.
3. Downgrade or remove claims that exceed the evidence.
4. Preserve negative results and counterexamples.
5. Flag confounded comparisons and unlabeled proxies.

Pass 4: version and structure
1. Group drafts, backups, conversions, worktrees, audits, and historical appendices.
2. Select one authority per result/procedure and remove stale opposite instructions.
3. Verify project IDs, section numbers, labels, paths, and sample totals.
4. Map each section to one unique reader question, claim, evidence item, and boundary.

Pass 5: composition
1. Diagnose vocabulary, sentence, transition, paragraph, section, rhythm, and voice issues using rule IDs.
2. Treat repeated templates as document-level failures, not isolated wording.
3. Remove drafting residue and role leakage.
4. Rebuild around concrete objects and evidence.

Return:
- document contract and provenance map;
- Blocking/Major/Moderate findings ordered by severity;
- fact/symbol contradictions;
- claim-evidence matrix;
- section responsibility map;
- representative before/after rewrites;
- unresolved evidence requests;
- gate-by-gate pass/fail declaration.

Do not rewrite across unresolved Blocking issues.
```

## 3. Full rewrite contract

Core rules: all failed audit rules plus final regression gates.

```text
Rewrite only after the audit and fact decisions are complete.

Preserve exactly unless a documented correction is authorized:
- numerical data, units, equations, citations, labels, source quotations, negative results, assumptions, and applicability conditions.

Rewrite order:
1. Remove or isolate stale versions, editor instructions, audit notes, and historical attachments.
2. Resolve section responsibility overlap and repeated conclusions.
3. Move evidence beside claims and consolidate limitations.
4. Replace abstract management nouns with research objects/actions.
5. Break false binary contrasts, mechanical lists, repeated stems, and overloaded sentences.
6. Restore rhythm by expanding key evidence and compressing routine material.
7. Verify terminology, notation, references, TeX/Markdown syntax, and factual preservation.

For every material change, keep a ledger:
location | rule ID | original function | action | evidence preserved | unresolved issue.

Do not “humanize” by adding colloquialisms, personal anecdotes, random sentence variation, invented uncertainty, or artificial imperfections.
```

## 4. Mathematical proof contract

Core rules: `MTH-01`-`MTH-19`, `EVD-01`, `RHY-04`, `RHY-05`.

```text
For each proof:
1. State the target and all assumptions.
2. Identify the decisive construction/theorem and explain why it applies.
3. Type every object (point, vector, scalar, function, derivative, matrix, affine/bilinear form).
4. Show the transformation that changes the conclusion.
5. Compress only routine reversible algebra.
6. Verify signs, exponents, indices, denominators, domains, branches, and exceptional cases.
7. Do not use examples, numerical checks, local expansions, or option clues as universal proof.
8. Do not call an object linear/bilinear/affine/invariant unless it satisfies the definition.
9. If a theorem condition is not established, stop and mark the gap.
10. Test the smallest admissible cases and boundary cases after deriving the result.
11. Keep an object ledger so primitives, functions, derivatives, interpolants,
    points, vectors, and dependent witnesses cannot silently exchange roles.
12. Partition every local-to-global sign or inequality claim into covered
    intervals; give a signed remainder/compact certificate/tail threshold as
    applicable.
13. For elimination, resultants, squaring, cubing, and division, record the
    implication direction, discarded factors/domain, introduced branches, and
    back-substitution into the original system.
14. Call a candidate curve an exact locus/envelope only after parameter
    recovery, real existence, regularity, gradient/tangency checks, and
    singular/degenerate cases pass.
15. Split domains at zeros before quotients or logarithms. Preserve square-root
    branches, inverse-function intervals, absolute values, integration
    orientation, and component-specific constants.
16. Recheck inequality direction after every sign-sensitive operation. For an
    asymptotic argument, prove the finite base range and the mechanism that
    preserves the claim beyond a stated threshold.
17. Translate every nonstandard term into a standard mathematical object,
    equations, parameter domain, and two-way equivalence; delete the term if
    this translation cannot be supplied.
```

## 5. Empirical paper contract

Core rules: `EVD-01`-`EVD-07`, `EVD-12`, `EVD-13`, `LOG-03`, `MTH-03`.

```text
For every claim, record dataset/sample, experimental factors, controls, metric, budget, uncertainty, and scope.

Do not use “significant” without a defined statistical/practical criterion. Do not call calibration validation. Do not describe a composite perturbation as a single-factor effect. Distinguish model parameters, aggregation weights, solver settings, initial conditions, and time windows.

Report null and failed robustness results in the main argument. The abstract/title may not state a stronger conclusion than the strongest evidence-bearing result.

Classify every reported number as observed, calibrated, assumed, simulated, or
derived. Match displayed significant digits to the weakest identification
source; extra digits may remain in a reproducibility table only when labeled as
computational precision.

When testing weights or ranking methods, list both perturbed and fixed
dimensions. Agreement under equal/entropy/CRITIC/AHP weights supports only
conditional ranking stability; it does not validate indicators, mechanisms,
the model, or external reality without separate tests.
```

## 6. Textbook contract

Core rules: `DOC-09`, `DOC-10`, `RHY-04`, `RHY-05`, `MTH-01`-`MTH-19`.

```text
Teach through hierarchy, not exhaustive narration.

Before writing, label inherited problem statements, official answers,
reconstructed answers, generated explanations, OCR, and editorial notes by
segment. Do not revise or attribute inherited text as model prose.

For each concept:
- motivation/question;
- precise definition;
- decisive property and proof;
- one canonical example;
- one counterexample or boundary;
- practice;
- short retrieval summary.

Explain the major construction once. Show theorem conditions and decisive identities. Compress routine substitutions. Do not repeat the same route at chapter, section, example, solution, pitfall, and mnemonic levels. Ban pseudo-technical and theatrical terminology. Independently verify every mathematical step and exercise condition.

After adding a chapter family, verify the authority main file includes it once,
prerequisites and definitions precede use, difficulty transitions are intended,
cross-references and answer links resolve, and superseded versions are removed
or labeled historical. Compilation alone does not pass these checks.
```

## 7. Strategy-manual contract

```text
Separate data observation, heuristic, and action.

For each rule provide:
- sample denominator;
- observed effect/hit rate;
- relevant subset;
- strength: strong/weak/none;
- counterexample;
- examination action;
- exit rule when evidence is absent.

Never convert negative correlation to absolute exclusion, small samples to “iron rules,” or reconstructed answers to official truth. Keep coaching language outside statistical claims.
```

## 8. Audit-report contract

Core rules: `EVD-11`, `LEX-09`, `DOC-05`, and the property-specific rules under audit.

```text
Use scope -> criteria -> findings -> evidence/location -> remediation -> independent verification -> residual risk -> release decision.

Separate automated flags from human judgment and formatting/compilation from mathematical correctness. A zero banned-word count or cleared lint status is not proof of valid argument. State exactly which gates passed.

Use distinct statuses: `transcribed`, `source-compared`, `compiled`,
`mathematically-checked`, and `externally-validated`. Never infer a later status
from an earlier one. Treat keyword scans as locators and literal regression
checks only.
```

## 9. Model response protocol

For a request to “reduce AI style,” the model must not immediately paraphrase. It must first return or internally establish:

```text
Genre:
Authority version:
Source segment types:
Central claim:
Evidence boundary:
Blocking contradictions:
Applicable rule modules:
Rewrite scope:
```

If none of the required evidence is available, ask for it or explicitly downgrade the scope to style-only review. Never imply factual verification that was not performed.

## 10. Final refusal/stop conditions

Stop the affected rewrite when:

- two authoritative-looking sources conflict;
- the central claim lacks evidence;
- a citation/source cannot be verified but is essential;
- a symbol/entity changes meaning;
- scenario factors are confounded while causal wording is requested;
- a mathematical property or theorem condition fails;
- the requested humanization would fabricate experience/authorship/data;
- OCR/source uncertainty cannot be resolved without the source image.

Return the conflict and the exact user/domain decision needed. Continue only on independent, unaffected sections when doing so cannot hide the blocker.
