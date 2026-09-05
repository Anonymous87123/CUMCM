# Validation Gates

Run gates in order. A later style pass cannot override an earlier failure. Store results in a change ledger so the user can distinguish corrected prose from unresolved evidence.

## Gate -1: scene selection

Before Gate 0, verify:

| Question | Pass evidence |
|---|---|
| Who is the reader? | learner/instructor, model reviewer/engineer, or research reviewer |
| What does the document owe? | teaching clarity, reproducible model decision, or novel research inference |
| What is the decisive evidence object? | derivation/example, data/code/protocol, or proposition/source/experiment |
| Is the file mixed? | segment map with NOTE/MOD/RES/SRC/OCR/AUD/HIST/N-A labels |
| Which child skill is active? | exactly one per target segment |
| Which standards are inactive? | explicit list preventing cross-scene overreach |

Fail this gate when a journal novelty requirement is imposed on course notes,
classroom looseness is applied to a modeling/research claim, engineering
approximation is used as theorem proof, or one average voice is assigned to a
mixed document.

## Contents

0. Gate -1: scene selection
1. Gate 0: task and authority
2. Gate 1: provenance
3. Gate 2: fact lock
4. Gate 3: notation and mathematics
5. Gate 4: quantitative reconciliation
6. Gate 5: claim-evidence matrix
7. Gate 6: version and cross-references
8. Gate 7: section responsibilities
9. Gate 8: paragraph and sentence composition
10. Gate 9: citations and external claims
11. Gate 10: genre and voice
12. Gate 11: final regression
13. Reusable audit forms

## 1. Gate 0: task and authority

### Questions

- What is the requested operation: audit, rewrite, generate, translate, transcribe, or summarize?
- Which file/version is authoritative?
- Which files are source data, references, drafts, audits, backups, conversions, or historical attachments?
- What facts/formatting must remain unchanged?
- What target reader and genre apply?

### Fail conditions

- no authority version;
- user asks to rewrite one file but evidence comes from another conflicting draft;
- historical appendix is treated as current state;
- third-party source is assumed model-authored;
- publication prose and internal planning notes are intentionally mixed without labels.

### Output

```text
Task:
Authority file/version:
Supporting sources:
Historical/non-authoritative files:
Preserve exactly:
Target reader/genre:
```

## 2. Gate 1: provenance

### Segment provenance table

| Location | Content label | State | Source | Attribution confidence | Editable? | Notes |
|---|---|---|---|---|---|---|
| section/lines | ARG/SRC/QUO/TRN/OCR/AUD/VER | CURRENT/HIST/PLAN/DRAFT | path/page | A1/A2/B/C/D | yes/no | |

`VER` means stale version residue at the passage level. `HIST` means intentionally preserved historical material and is not automatically an error; it must still be prevented from masquerading as current authority.

### Checks

- inherited questions excluded from model-style conclusions;
- OCR artifacts not interpreted as author voice;
- translation compared with source where available;
- reconstructed answer labeled, not called official;
- audit notes not copied into paper prose;
- assistant write event not treated as proof every sentence is original.

### Fail conditions

- source identity unknown for a core quotation or fact;
- generated explanation alters quoted/source content silently;
- OCR uncertainty is resolved by guessing without a marker;
- style conclusion relies on C/D material.

## 3. Gate 2: fact lock

Create before rewriting:

| Fact ID | Object | Value/statement | Unit | Scope/time | Source | All locations | Locked? |
|---|---|---|---|---|---|---|---|

Include:

- numbers and denominators;
- species/entity names;
- algorithm names and acronym expansions;
- data-source paths and versions;
- scenario factors;
- role/permission/menu/page counts in technical documents;
- reported errors and negative results;
- status (`planned`, `implemented`, `tested`, `manually accepted`).

### Cross-location check

Compare title, abstract, introduction, methods, tables, figures, results, discussion, conclusion, appendix, README, and audit logs.

### Corpus-derived examples to catch

- `中华鲟` versus `长江鲟`;
- six versus seven versus eight GUI tabs;
- Qt “not implemented” versus “implemented” versus “not manually accepted”;
- self-test “fully read-only” versus first-run seed mutation;
- 59 total cases versus appendix rows totaling 56;
- P2/P3 defined while P4 is later referenced;
- 413/419/425 question-version drift.

### Fail policy

Do not select the newest-looking value automatically. Identify authority or ask the user. Preserve the contradiction in the audit until resolved.

## 4. Gate 3: notation and mathematics

### Symbol/type table

| Symbol | Object type | Definition | Domain | Unit | First line | Other uses | Conflict? |
|---|---|---|---|---|---|---|---|

Object types include scalar, vector, point, affine coordinate, function, derivative, matrix, bilinear form, probability variable, index, set, parameter, and observed quantity.

Also record quantifier/dependency type: fixed, universal, existential, locally chosen, or dependent witness (`\xi=\xi(x,y)`).

### Equation audit

For every decisive transformation:

1. Copy the pre-expression and post-expression.
2. State the operation.
3. Verify object identity.
4. Verify sign/exponent/coefficient.
5. Verify denominator and domain.
6. Verify branch/absolute value.
7. Verify equivalence direction.
8. Verify exceptional cases.
9. Verify quantifier and witness dependence.
10. Verify the domain of temporary transformations (`\log`, reciprocal, square root, inverse function).

### Theorem audit

| Theorem | Needed assumptions | Where established | Conclusion used | Valid? |
|---|---|---|---|---|

Check especially:

- Rolle/mean-value conditions;
- Taylor remainder and local/global scope;
- Green/Stokes domain, orientation, and regularity;
- Poncelet closure assumptions;
- convergence and interchange of limits/integrals;
- convexity composition conditions;
- asymptotic dominance with base cases or monotonic ratios;
- exact versus approximate distribution moments.
- L'Hopital's rule: indeterminate form, differentiability interval, denominator-derivative condition, and limit hypotheses;
- inverse-function derivative theorem: local invertibility and nonzero derivative at the inverse point;
- Cauchy/ordinary mean-value theorems: independent witnesses must not be silently merged.

### Known failure patterns

- `f(x_0-Δx)` changes to `f'(x_0-Δx)`;
- `e^{-t}/e^t` becomes `e^{2t}`;
- Hooke force written as `-k||r||r`;
- affine expression called bilinear;
- local expansion used to prove global positivity;
- three special configurations used to identify a full envelope;
- “after simplification” hides the decisive elimination.

### Fragile transformation gate

Apply this table to every proof step whose reversal, domain, or object type is
not automatic. A checked cell needs an equation, theorem condition, or explicit
case analysis; prose confidence is not evidence.

| Risk | Required record | Reject when | Rules |
|---|---|---|---|
| Object identity | symbol, definition, type, domain, derivative order, parameter dependence | `f/F/f'`, point/vector, or interpolant/original object changes without redefinition | `MTH-14` |
| Local to global | local interval, remainder/bound, middle-region certificate, tail threshold | a series, sample, or leading term is used on an uncovered interval | `MTH-11` |
| Elimination | original system, operation, factors divided out, branches added, implication direction, back-substitution | the eliminated equation is called equivalent without recovering all original variables/parameters | `MTH-12` |
| Envelope/tangency | parameter domain, real common point, repeated-root/derivative condition, nonzero gradients, gradient collinearity, singular cases | an algebraic candidate is called the exact envelope from one-way elimination or special positions | `MTH-13` |
| Quotient/log | zero set, sign of log argument, split intervals, limiting treatment | a denominator or log argument can vanish in the stated domain | `MTH-15` |
| Branch/orientation | branch interval, absolute value, path/surface orientation, cross-branch constants | a single antiderivative or sign is asserted across incompatible branches/orientations | `MTH-16` |
| Inequality | sign of multiplier/divisor, monotonicity of transformation, equality cases | direction changes silently or assumptions reduce the case to empty/trivial | `MTH-17` |
| Asymptotic claim | finite base range, tail threshold, preservation mechanism | “eventually dominates” is used to prove a claim from a named finite index | `MTH-18` |
| Nonstandard term | standard object, defining equations, constants, parameter domain, two-way equivalence | a geometric story or invented name substitutes for a mathematical definition | `MTH-19` |

For local-to-global sign claims, create a coverage row for every interval:

| Interval | Certificate | Assumptions | Endpoint handling | Verified? |
|---|---|---|---|---|

For elimination/envelope claims, create a candidate ledger:

| Candidate branch | How produced | Original parameter recovered? | Back-substitution | Regular? | Keep/exclude |
|---|---|---|---|---|---|

### Fail policy

Mark `Blocking`; do not improve prose around the invalid step until corrected.

## 5. Gate 4: quantitative reconciliation

### Sample/count checks

- row totals equal declared total;
- subgroup overlap/independence stated;
- denominator stays constant where percentages are compared;
- missing/excluded cases listed;
- version additions/deletions reconcile old and new totals;
- small-N rules labeled weak.

### Sensitivity checks

Build a matrix:

| Run | Changed factors | Fixed factors | Renormalized? | Solver/window/initial state | Claim supported |
|---|---|---|---|---|---|

Do not collapse:

- local parameter perturbation;
- weight perturbation;
- combined scenario;
- solver sensitivity;
- time-window sensitivity;
- initial-condition sensitivity.

### Statistical language checks

- define test and alpha/interval where `显著` is used;
- distinguish effect size from statistical significance;
- report uncertainty and multiple comparisons where relevant;
- negative correlation is not absolute exclusion;
- 0 observed events is not proof of impossibility;
- a benchmark's official accuracy is not OOD validity.

### Empirical claim and precision gate

| Reported item | Evidence class | Identification source | Display precision | Sensitivity/range | What was fixed | Allowed claim |
|---|---|---|---|---|---|---|
| number/parameter/ranking | observed/calibrated/assumed/simulated/derived | instrument, sample, anchor, normalization, or formula | digits shown | perturbation/CI/range | indicators, model, scenarios, data | exact wording |

Checks:

- Store high computational precision if reproducibility needs it, but display
  only the precision supported by the weakest upstream measurement or
  identification step (`EVD-12`).
- Label a multi-decimal value from a single approximate anchor as an internal
  simulation output, not an empirically identified parameter (`EVD-12`).
- For ranking experiments, list exactly which dimensions were perturbed and
  which remained fixed. Weight stability supports only ranking stability under
  that indicator matrix (`EVD-13`).
- Do not call agreement across equal, entropy, and CRITIC weights model
  validation, indicator validity, mechanism evidence, or external validity
  unless those targets have independent tests (`EVD-13`).
- Let null, contradictory, and failed robustness results modify the title,
  abstract, discussion, conclusion, and recommendation wherever affected
  (`EVD-04`, `DOC-07`).

### Acceptance criteria

If text says “consistent,” “passes,” or “validated,” record the threshold defined before seeing the result. If no threshold exists, report the values without pass language.

## 6. Gate 5: claim-evidence matrix

Create for every abstract/conclusion claim:

| Claim ID | Exact claim | Strength verb | Evidence | Evidence level | Scope | Counterevidence | Revision |
|---|---|---|---|---|---|---|---|

### Evidence level

`proof > external validation > held-out check > controlled comparison > sensitivity > calibration > observation > heuristic > expectation`

### Checks

- abstract claim exists in matrix;
- title does not exceed matrix;
- negative result changes claim strength;
- proxy is labeled;
- mechanism separated from observation;
- causal alternatives addressed;
- limitations bind to a specific claim/evidence item;
- no conclusion supported only by editorial language.

### Fail examples

- candidate bracket titled universal threshold;
- directional match called exact validation;
- combined pollution/obstruction scenario attributed to pollution;
- exploratory geometry asserted as performance mechanism;
- star ratings presented without benchmark evidence.

## 7. Gate 6: version and cross-references

### Version family table

| Family | Files | Authority | Duplicates/conversions | Historical claims | Active claims |
|---|---|---|---|---|---|

### Claim migration table

| Old claim/action | New claim/action | Keep/delete/replace | Locations updated | Verified? |
|---|---|---|---|---|

### Cross-reference checks

- section/chapter numbers exist;
- figure/table/equation labels resolve;
- project IDs (`P1/P2/P3/P4`) are defined exactly once;
- data-source paths point to the intended artifact;
- old jump stubs redirect correctly;
- appendices use current totals;
- README menu/page/source lists match code/build files;
- historical attachments labeled with date/branch/status.

### Textbook/chapter-family integration gate

Apply after adding or revising a group of chapters, examples, or appendices:

| Check | Evidence required | Failure example | Rule |
|---|---|---|---|
| Authority inclusion | `main.tex`/book entry point includes the intended chapter exactly once | polished chapter exists but is never compiled into the book | `DOC-10` |
| Prerequisite order | definitions/theorems appear before first use | advanced construction appears before its object is defined | `DOC-10` |
| Definition ownership | one authoritative definition and explicit cross-references | each chapter independently redefines the same operator | `DOC-10`, `LEX-04` |
| Difficulty progression | intended reader and prerequisite jump recorded | a chapter silently moves from elementary derivation to research-level certificates | `DOC-10` |
| Numbering/labels | section, theorem, equation, exercise, and answer links resolve | appended family preserves old local numbers | `DOC-08`, `DOC-10` |
| Answer/source identity | inherited question, official answer, reconstruction, and generated solution labeled | reconstructed answer presented as official | `DOC-09` |
| Version replacement | old duplicate/superseded family removed or marked historical | two conflicting chapter families remain active | `DOC-06`, `DOC-07` |

Compilation is necessary but does not pass prerequisite, definition,
authorship, difficulty, or correctness checks.

### Fail policy

Do not add `以最新版本为准` as the only repair. Remove/reconcile stale content and designate an authority.

## 8. Gate 7: section responsibilities

### Section map

| Section | Reader question | Unique claim | Evidence | Boundary | Duplicate locations | Action |
|---|---|---|---|---|---|---|

### Standard responsibilities

- Abstract: question, method identity, central result, material boundary.
- Introduction: problem, existing capability, concrete gap, contribution.
- Methods: objects, assumptions, procedure, decision criteria, reproducibility.
- Results: observations and uncertainty.
- Discussion: interpretation, alternatives, relation to prior work.
- Limitations: inference constraints and their consequences.
- Conclusion: robust/conditional/unresolved synthesis.

### Checks

- no method section written as workflow report;
- no results hidden inside methods;
- no discussion that repeats all results;
- no five identical advantage/limitation subsections;
- no project plan commands in publication;
- no heading with only one restated sentence;
- historical appendices do not masquerade as current state.

## 9. Gate 8: paragraph and sentence composition

### Paragraph labels

Assign one dominant label: `DEF`, `OBS`, `EVD`, `EXP`, `CMP`, `BND`, `SYN`, `TRN`.

### Paragraph checks

- evidence adjacent to claim;
- decisive idea receives more space than routine algebra;
- no identical function sequence in every paragraph;
- one full limitation statement, not many;
- no forced local conclusion after every paragraph;
- examples not repeated at three instructional levels.

### Sentence checks

- subject is a research object rather than `本文/这一点/这种情况` where possible;
- `不是 A，而是 B` is genuine;
- list order is real;
- one central claim per sentence;
- modality matches evidence;
- terminology stable;
- no drafting/editorial residue;
- no management/game/marketing voice;
- no universal English shell.

### Rhythm checks

- key finding can be short;
- dependent conditions stay together;
- paragraph lengths reflect evidence weight;
- connectors do not form a drumbeat;
- some paragraphs may end with evidence rather than a summary.
- decisive constructions, theorem conditions, sign/branch choices, and failure
  cases receive more explanation than reversible substitution (`RHY-05`).

## 10. Gate 9: citations and external claims

### Citation table

| Proposition | Citation | Source actually says | Match? | Page/section | Action |
|---|---|---|---|---|---|

### Checks

- citation beside proposition;
- no paragraph-end cluster supporting five different claims;
- source identity/bibliography accurate;
- translated quotation faithful;
- literature review distinguishes source result from current interpretation;
- current file's internal result not presented as external evidence;
- official/primary source preferred for facts and API definitions.

### API/technical documentation gate

Verify algorithm names, acronym expansions, inputs/outputs, and performance against code or primary documentation. Corpus failures included invented expansions for DG2/RDDSM/CSG and unsupported star ratings.

## 11. Gate 10: genre and voice

Read the relevant genre playbook. Check:

- paper speaks as researcher, not quality manager;
- textbook speaks as teacher, not game commentator;
- strategy manual labels heuristics;
- audit retains traceability without entering paper voice;
- README distinguishes implemented/tested/manual-accepted;
- research plan remains internal;
- OCR remains faithful rather than stylistically polished.

### Voice leakage list

- research editor: `主线/锁定/收束/回滑`;
- reviewer simulator: repeated objection/defense;
- quality manager: `整改/清零/放行/口径`;
- exam coach: `满仓/收割/死磨/题眼`;
- marketing writer: `亮点/赋能/未来愿景`;
- theatrical teacher: `魔法/奇迹/灰飞烟灭`.

Use only where the genre explicitly permits.

## 12. Gate 11: final regression

After rewrite, compare original and revised documents.

### Preservation

- numbers, units, equations, citations, labels, and negative results unchanged unless a documented correction was authorized;
- no condition or exception lost;
- no source quote altered;
- no claim strengthened;
- no new citation/fact invented.

### Improvement

- contradictions resolved or listed;
- one authority version;
- repeated claims removed;
- section responsibilities distinct;
- concrete objects replace abstractions;
- decisive steps visible;
- routine operations compressed;
- voice matches genre;
- abstract/conclusion match evidence.

### Acceptance-language regression

- Every `complete`, `clean`, `verified`, `validated`, `correct`, `released`, or
  `closed` statement names the object and the passed gate (`EVD-11`).
- A zero banned-word count is recorded as a lexical search result only; whole
  argument, rhythm, evidence, and mathematics still receive their own checks
  (`LEX-09`).
- An automated detector or linter does not validate the property it was not
  designed to test (`EVD-11`, `LEX-09`).
- `raw`, `compiled`, `transcribed`, `source-compared`,
  `mathematically-checked`, and `externally-validated` remain distinct states.

### Mechanical integrity

- TeX compiles or syntax remains balanced when compilation is out of scope;
- labels/citations resolve;
- Markdown markers not leaked into TeX;
- headings and numbering coherent;
- tables totals and units correct;
- UTF-8 text not mojibake.

## 13. Reusable audit forms

### 13.1 Full audit summary

```markdown
## Document contract
- Authority:
- Genre/reader:
- Central claim:
- Evidence boundary:
- Source segment types:

## Blocking findings
| Rule | Location | Contradiction/invalidity | Consequence | Needed decision |

## Claim-evidence findings
| Claim | Evidence level | Scope | Problem | Revision |

## Structure findings
| Section | Current job | Intended job | Duplicate/missing | Action |

## Style findings
| Rule | Location | Observable feature | Consequence | Rewrite |

## Gate result
| Gate | Pass/fail | Evidence |
```

### 13.2 Rewrite change ledger

```markdown
| Change ID | Location | Rule | Original function | Action |
|---|---|---|---|---|
| C-01 | ... | LOG-05 | repeated limitation | deleted; authority at Results 3.2 |
| C-02 | ... | EVD-01 | overclaim | weakened to directional consistency |
| C-03 | ... | DOC-07 | stale version | replaced with authority v3 |
```

### 13.3 Fact decision request

```markdown
| Conflict | Source A | Source B | Why style cannot decide | User/domain decision needed |
|---|---|---|---|---|
```

### 13.4 Final gate declaration

```text
Provenance: PASS/FAIL
Facts/math: PASS/FAIL
Quantitative reconciliation: PASS/FAIL
Evidence alignment: PASS/FAIL
Version/cross-reference: PASS/FAIL
Structure: PASS/FAIL
Composition: PASS/FAIL
Citations: PASS/FAIL/NOT CHECKED
Mechanical integrity: PASS/FAIL/NOT RUN
Unresolved blockers: ...
```

Do not declare the document complete while any `MUST` gate fails.

### 13.5 Mathematical object ledger

```markdown
| Symbol | Definition | Type/order | Domain | Dependency | Allowed operations | First use | Conflicts |
|---|---|---|---|---|---|---|---|
```

### 13.6 Fragile transformation ledger

```markdown
| Step | Before | Operation | Conditions | Lost factor/domain | Added branch | Direction | Back-check |
|---|---|---|---|---|---|---|---|
```

Do not write `<=>` unless both directions are proved under the same domain.

### 13.7 Completion-state ledger

```markdown
| Artifact/section | Transcribed | Source-compared | Compiled | Mathematically checked | Externally validated | Evidence | Residual risk |
|---|---|---|---|---|---|---|---|
```

Use `PASS`, `FAIL`, or `NOT RUN`; never infer a later column from an earlier one.

### 13.8 Precision and ranking ledger

```markdown
| Claim/value | Observed/calibrated/assumed/simulated | Identification strength | Digits justified | Perturbed dimensions | Fixed dimensions | Exact supported wording |
|---|---|---|---|---|---|---|
```
