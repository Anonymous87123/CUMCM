# Academic De-AI Diagnostic Matrix

Use this matrix for full-document audits. Diagnose top-down. Do not infer a style problem from frequency alone; confirm it in context and explain what argumentative function the passage performs.

## Contents

0. Scene mismatch diagnosis
1. Severity and evidence format
2. Source and authorship
3. Facts, notation, and quantitative consistency
4. Claim-evidence alignment
5. Vocabulary and terminology
6. Sentence form
7. Logic and transitions
8. Paragraph architecture
9. Section and document architecture
10. Rhythm, voice, and reader relation
11. Version and cross-reference integrity
12. Scoring and delivery

## 0. Scene mismatch diagnosis

Diagnose routing before prose. Record:

```text
reader | purpose | strongest claim | evidence object | primary scene
segment exceptions | selected child skill | standards not activated
```

Scene mismatch is `Major` when it makes the prose mechanically inappropriate
but leaves claims intact. It is `Blocking` when the wrong scene standard changes
evidence or correctness, for example:

- a classroom heuristic is used as research proof;
- a modeling approximation loses its error/domain and becomes a theorem;
- a course note is forced to invent novelty or external validation;
- a weight-sensitivity result is rewritten as theoretical robustness;
- a mixed README lets historical plans masquerade as current engineering fact.

Use [scenario-router.md](scenario-router.md) to repair the route before applying
sentence or paragraph diagnostics.

## 1. Severity and evidence format

Record every finding as:

```text
Rule ID | severity | exact location | excerpt | context/function
problem | consequence | revision action | evidence still needed
```

Severity:

- `Blocking`: contradiction, invalid mathematics, wrong object, confounded experiment, unsupported core claim, broken provenance, or missing definition that prevents interpretation.
- `Major`: other `MUST` failure that materially changes evidence, reproducibility, terminology, or section responsibility.
- `Moderate`: repeated template, paragraph hierarchy, voice, or rhythm failure that damages scholarly quality but not factual interpretation.
- `Minor`: local wording or formatting issue with no argumentative consequence.

Do not call a passage “AI-like” without naming the observable feature and its consequence.

## 2. Source and authorship

### SRC-01 File identity

Ask:

- Was the file generated, edited, converted, copied, OCR-transcribed, or only referenced by the assistant?
- Is it a current authority, draft, backup, worktree copy, audit ledger, or third-party source?
- Does one file mix inherited text with generated explanation?

Fail examples from the corpus:

- a TeX word database created by an assistant but containing lexical data rather than authored prose;
- OCR textbook pages mixed with generated closure reports;
- examination questions inherited from source papers and generated solutions in the same TeX;
- external requirement text later used as if it were model-authored style evidence.

Required action: create a segment provenance map. Only attributable segments enter style analysis.

### SRC-02 Segment identity

Label each major segment:

| Label | Meaning | Edit policy |
|---|---|---|
| `ARG` | generated argument/explanation | style and evidence audit |
| `SRC` | inherited source/problem/data | preserve; verify citation/source |
| `QUO` | quotation | preserve accurately; cite |
| `TRN` | translation | compare with source if available |
| `OCR` | transcription | correct against image/source, not stylistically invent |
| `AUD` | audit/editorial note | keep outside publishable prose |
| `VER` | stale version residue | remove or reconcile |

### SRC-03 Attribution confidence

Use:

- A1: user explicitly confirms model generation;
- A2: assistant write event and file/time/content correspond;
- B: strong project/history match without one write-event closure;
- C: path mention only;
- D: third-party/template/dependency.

Never turn C/D into a model-style claim.

## 3. Facts, notation, and quantitative consistency

### FAC-01 Numeric identity

Check each number across abstract, body, table, figure, appendix, and conclusion:

- same value and unit;
- same object and time point;
- same sample denominator;
- same rounding rule;
- same interpretation.

Corpus failures include a result `0.204` assigned to different ecological objects and a report claiming 59 cases while an old appendix sums to 56.

### FAC-02 Experimental factor identity

For each scenario or ablation, list every changed factor. If two factors change, prohibit single-factor causal language. Distinguish:

- parameter sensitivity;
- weight reallocation;
- numerical solver sensitivity;
- initial-condition sensitivity;
- time-window sensitivity;
- combined scenario stress.

Do not call 2,000 weight perturbations “local model-parameter perturbations.”

### FAC-03 Symbol identity

Build a symbol table with object, type, domain, unit, first definition, and all uses. Fail when:

- one symbol denotes two species or variables;
- a point symbol is later used as a vector without an explicit conversion;
- an affine expression is treated as a bilinear form;
- an index changes meaning across chapters.

### FAC-04 Algebraic step audit

For each decisive equality/inequality, independently verify:

- object did not change (`f` to `f'`);
- sign and exponent are correct;
- denominator is nonzero;
- direction of inequality is justified;
- domain and branch are preserved;
- limit/interchange conditions hold;
- claimed theorem assumptions are present.

Fluent prose and aligned equations do not count as verification.

### FAC-05 Table reconciliation

Recompute row/column totals and compare table entries with the prose. A table cannot be treated as correct because it looks complete. For weight tables, verify whether totals are preserved and whether “no renormalization” matches the entries.

### FAC-06 Cross-document authority

When multiple drafts exist, state which value/definition/result is authoritative. Do not average conflicting versions or let a disclaimer hide old instructions.

### FAC-07 Object-identity continuity

For every proof longer than one local calculation, record the object behind each
symbol, its domain, differentiability/order, and parameter dependence. Flag a
Blocking failure when a primitive becomes the original function, a function
becomes its derivative, a point becomes a vector, or independently chosen
witnesses are reused as one common value. Repair through an object ledger and
then recompute the affected proof; a one-character rename is not sufficient.

Rule route: `MTH-10`, `MTH-14`.

### FAC-08 Reversibility and branch accounting

For elimination, resultants, squaring/cubing, division, logarithms, and inverse
functions, record:

```text
original system/domain -> operation -> discarded conditions/factors
-> introduced candidates -> implication direction -> back-substitution
```

Flag Blocking when an implication is printed as equivalence, a denominator can
vanish, a branch/orientation disappears, or an exact envelope/locus contains
unchecked algebraic branches. For tangency, also require real parameter
recovery, repeated-root/parameter-derivative conditions, regular gradients,
and singular-case analysis.

Rule route: `MTH-12`, `MTH-13`, `MTH-15`, `MTH-16`.

### FAC-09 Numerical precision and identification

Classify each value as observed, calibrated, assumed, normalized, simulated,
or derived. Compare displayed significant digits with the weakest upstream
measurement or identification source. Report computational precision
separately when extra digits exist only to reproduce a run. Flag Major when a
single approximate anchor or hand-set parameterization is narrated with
measurement-like precision.

Rule route: `EVD-12`.

## 4. Claim-evidence alignment

### CLM-01 Evidence ladder

Classify evidence before choosing verbs:

1. formal proof under explicit assumptions;
2. independent external validation;
3. held-out or out-of-fit consistency check;
4. controlled comparative experiment;
5. sensitivity/robustness analysis;
6. in-sample calibration;
7. exploratory observation;
8. heuristic/analogy;
9. editorial expectation.

Do not promote a lower level through prose. A proxy prediction 16.47% from a local observation can support directional consistency, not exact validation.

### CLM-02 Verb gate

| Verb | Minimum expectation |
|---|---|
| `证明` | formal derivation/theorem or established proof |
| `验证` | predefined criterion and independent/held-out test |
| `表明` | direct evidence with clear scope |
| `支持` | compatible evidence, alternatives remain |
| `提示` | exploratory pattern |
| `可能` | plausible interpretation, not established |

### CLM-03 Scope gate

Attach every material claim to the relevant scope: data set, function family, optimizer, region, period, parameter range, budget, metric, or theorem assumptions.

### CLM-04 Negative evidence

Check whether failed robustness, null results, or counterexamples are present in the main argument. Do not bury a result such as “5 of 75 settings retain the crossing” while the title advertises a universal threshold.

### CLM-05 Proxy and ground truth

Name a proxy as a proxy. State what it measures and what it cannot establish. Local observations, internal scores, official benchmark accuracy, and external generalization are different claims.

### CLM-06 Causal gate

For causal wording, require a design or argument that excludes relevant alternatives. Scenario ranking in one model does not establish a real ecological mechanism.

### CLM-07 Significance gate

`显著` requires a defined statistical, practical, or mathematical threshold. A percentage difference from an expectation is not automatically statistical significance.

### CLM-08 Workflow-state gate

Ask exactly which property was checked. `Transcribed`, `covered`, `compiled`,
`lint clean`, `no placeholders`, and `keyword count zero` are independent
workflow results. They do not establish source fidelity, mathematical
correctness, answer authority, or external validity. Require a named
content-specific test before using `verified`, `correct`, or `released`.

Rule route: `EVD-11`.

### CLM-09 Ranking-stability gate

List perturbed and fixed dimensions. If only aggregation weights vary, the
result supports ranking stability conditional on the fixed indicator matrix
and scenarios. It does not validate indicator selection, model structure,
causal mechanism, observational error, or out-of-sample behavior.

Rule route: `EVD-13`.

### CLM-10 Negative-result propagation

When a robustness or counterexample rejects a central claim, trace the old
claim through title, abstract, method decision criteria, results, captions,
discussion, conclusion, and recommendations. Flag Major if only one local
disclaimer changes while stronger claims survive elsewhere.

Rule route: `EVD-04`, `DOC-07`.

## 5. Vocabulary and terminology

### LEX-D1 Unsupported evaluation

Flag `显著、有效、全面、深入、完整、准确、稳健、合理、清晰、优异` when no adjacent criterion or evidence exists.

### LEX-D2 Management leakage

Flag `主线、收口、落地、闭环、门禁、抓手、口径、台账、放行、清零、落点` in publishable prose. Replace with research objects and actions, not random synonyms.

### LEX-D3 Universal academic nouns

Inspect `机制、框架、体系、路径、模式、维度、层面`. Ask: which variable relation, algorithm step, measurement, or hypothesis is meant?

### LEX-D4 Pseudo-technical language

Terms such as `泛函、同构、齐次化、仿射、联合二次多项式算子方程、系统不变量、探针` require exact definitions. If the mathematical property is absent, remove the term.

For coined systems, additionally require a standard object, defining equations,
parameter domain, forward map, inverse recovery, and exceptional cases. Route
unproved equivalence to `MTH-19`.

### LEX-D5 Theatrical language

Remove `宇宙级纯净、完美归零、奇迹般、闭着眼就能写出、梦寐以求、魔法、爆出、铁证如山、灰飞烟灭、锁死、吐出` from academic prose. In teaching, replace with the exact mistake or shortcut.

### LEX-D6 Decision-tree vocabulary

`入口、路线、底座、母式、送回、压回、触发、主路` reveals a useful decision-tree teaching style. Keep only when it names an actual decision; avoid repeating it at chapter, section, example, and solution levels.

### LEX-D7 Terminology drift

Do not vary terms for elegance. Verify species names, algorithm names, metrics, section labels, and acronym expansions exactly. Corpus failures included distinct species names and fabricated/incorrect algorithm expansions.

### LEX-D8 Keyword-zero false acceptance

Treat a banned-word search as a locator and literal regression check only.
After a zero result, still inspect repeated sentence functions, paragraph
symmetry, proof responsibility, evidence alignment, and mathematical validity.
Flag Major when a lexical scan is used to declare human authorship, no AI
residue, or completed revision.

Rule route: `LEX-09`, `EVD-11`.

## 6. Sentence form

### SYN-D1 False binary

Flag repeated `不是 A，而是 B` and `关键不在 A，而在 B`. Keep when A/B are genuine alternatives; otherwise state B or use a non-exclusive correction.

### SYN-D2 Mechanical sequence

Flag `首先/其次/再次/最后` when the list is neither ordered nor exhaustive. Check whether the same four-stage sequence appears in unrelated topics.

### SYN-D3 Repeated stems

Compare adjacent subsections. Five identical `本问的优点不在于...` stems are a document-level template, not five local sentence issues.

### SYN-D4 Overloaded sentence

Split when a sentence contains more than one central claim or combines background, method, result, interpretation, limitation, and significance. Preserve conditions with the claim they govern.

### SYN-D5 Empty academic framing

Delete `值得注意的是、不可忽视的是、从某种程度上说、具有重要意义` if the following proposition can stand alone.

### SYN-D6 Drafting residue

Remove `后文若、正文里要、表格的作用、这样写、这里需要强调、对论文写作而言、放到图上`. Convert to research content.

### SYN-D7 Modal calibration

Audit `必须、可以、可能、倾向、支持、表明、证明`. Do not use forceful modality for editorial preference or weak evidence.

### SYN-D8 Translation/English shell

Flag `This practice/shift/trend/phenomenon` as a universal subject and interchangeable `Ultimately/In conclusion/Taken together/On balance` endings. Replace with the actual object and relation.

## 7. Logic and transitions

### LOG-D1 Concrete gap before method

Reject `为解决上述问题，本文提出...` unless the preceding text names a measurable or decidable gap.

### LOG-D2 Object continuity

Prefer the preceding parameter, equation, data subset, or figure as subject. Generic connectors cannot substitute for reference continuity.

### LOG-D3 Observation-mechanism separation

Require three labels where relevant: observation, interpretation, independent test. Do not let an explanatory verb collapse them.

### LOG-D4 Information exit

Track each major conclusion across abstract, analysis, results, advantages, limitations, and conclusion. Designate one full statement, then short references only.

### LOG-D5 Theorem applicability

Before invoking Poncelet closure, Rolle's theorem, Green/Stokes, Taylor expansion, or asymptotic dominance, list the needed conditions and show they hold in the current domain.

### LOG-D6 Local-to-global jump

Flag local expansion used for all-domain positivity, a few special configurations used to identify an entire envelope, or finite numerical examples used as a universal proof.

### LOG-D7 Hidden decisive algebra

`经过化简可得` is acceptable only for routine reversible algebra. If the conclusion depends on factorization, elimination, a sign, or branch selection, show it or cite a reproducible appendix.

### LOG-D8 Proof-coverage table

For every all-domain sign, inequality, or integer-range claim, partition the
domain and name one certificate per region. A Taylor expansion near one point
and an asymptotic comparison in the tail leave a middle interval; `eventually`
also does not establish the stated base cases. Flag Blocking if any interval,
endpoint, or finite initial range is uncovered.

Rule route: `MTH-11`, `MTH-17`, `MTH-18`.

## 8. Paragraph architecture

### PAR-D1 One dominant task

Label each paragraph as define, report, explain, compare, qualify, synthesize, or transition. A paragraph may support another task but should not perform all seven.

### PAR-D2 Evidence proximity

Place numbers, equations, tables, and citations beside the claim. Do not let a long rhetorical preface precede the evidence.

### PAR-D3 Hierarchy of detail

Check whether decisive ideas receive more space than reversible algebra. Over-complete textbooks often narrate every substitution and flatten the key insight.

### PAR-D4 Boundary placement

State each material limitation at first relevant use and synthesize once. Do not copy a full disclaimer into every section.

### PAR-D5 Ending diversity

Not every paragraph needs `因此/由此可见/这说明`. A result paragraph can end with a value; a proof can end with the decisive identity; a transition can end with a question.

### PAR-D6 Example economy

Keep one explanatory example and one counterexample in the main text. Move repeated encodings to exercises or appendices.

## 9. Section and document architecture

### DOC-D1 Responsibility map

Create:

```text
section | unique job | central evidence | prohibited duplication
```

Methods do not pre-report results; results do not repeat methods; discussion does not relist every number; limitations do not become a second results section.

### DOC-D2 Abstract ceiling

The abstract cannot make a stronger claim than the strongest supported body result. It must not call weight perturbation parameter robustness or directional agreement validation.

### DOC-D3 Conclusion synthesis

Separate robust conclusions, conditional conclusions, unresolved questions, and implications. Do not repeat the table of contents.

### DOC-D4 Heading density

Merge headings that contain only a restated judgment. A document with 100+ headings can be searchable yet still avoid argumentative paragraphs.

### DOC-D5 Audit versus paper

Move status codes, per-line ledgers, version labels, and remediation logs out of the paper body. Preserve them in appendices or project records.

### DOC-D6 Teaching recursion

Avoid repeating the same route at chapter overview, section overview, example setup, solution steps, pitfall, and memorization summary. Choose the level where the route adds new information.

### DOC-D7 Chapter-family integration

After a textbook family is appended, verify the authority entry point includes
it exactly once, definitions and prerequisites precede use, difficulty jumps
are intentional, exercise/answer links resolve, and inherited questions are
separated from reconstructed or generated answers. A readable standalone TeX
file or successful compilation does not prove that the chapter is integrated
or correctly attributed.

Rule route: `DOC-09`, `DOC-10`, `EVD-11`.

## 10. Rhythm, voice, and reader relation

### VOI-D1 Voice identity

Identify the active role:

- researcher;
- research editor;
- reviewer simulator;
- project/quality manager;
- exam coach;
- teacher;
- customer-service assistant.

Keep one role per publication context. Internal documents may switch roles only with explicit section labels.

### VOI-D2 Four observed model voices

The corpus shows four recurring attributable voices:

1. research editor: `主线、锁定、收束、停止条件`;
2. reviewer simulator: `claim -> evidence -> boundary -> objection`;
3. exam coach: `口诀、题眼、候选簇、弱加分`;
4. quality manager: `整改口径、逐题复核、验证记录、放行依据`.

Do not average them into one “GPT tone.” Select or suppress by genre.

### RHY-D1 Unequal weight

Key evidence can have long paragraphs; routine transitions should be short. Equal paragraph length is not neutrality.

### RHY-D2 Short verdict, long reason

Use a short sentence for a central finding or hard distinction. Use a longer sentence for conditions that must stay together. Do not alternate randomly.

### RHY-D3 Remove repeated closure

If every paragraph is fully closed, the document feels generated. Allow continuity through objects and evidence without a local summary at every stop.

### RHY-D4 Proof-importance weighting

Compare space and explanatory intensity assigned to the construction, theorem
condition, sign/branch decision, reversible algebra, and verification. Flag
Moderate when every substitution receives narration while the decisive step is
compressed into `化简可得`; escalate to Blocking when that compression hides an
unproved condition or invalid step. Route repair through `RHY-05`, `MTH-02`,
and the applicable mathematical rule.

## 11. Version and cross-reference integrity

### VER-01 Version family map

Group drafts, backups, worktrees, Markdown/TeX conversions, audit notes, and final documents. Count a family once for prevalence.

### VER-02 Authority declaration

Choose one authority per result/procedure. Record replaced, retained, and deleted claims.

### VER-03 Stale instruction search

Search all versions for opposite actions. A sentence “use the unified version” does not remove a stale Q36-first instruction later in the file.

### VER-04 Cross-reference audit

Verify section numbers, table/figure labels, project IDs, data-source paths, and appendix counts. Corpus failures included undefined P4 references and outdated jump-stub section numbers.

### VER-05 Conversion residue

After MD-to-TeX conversion, check Markdown bold markers, missing spaces, orphan fragments, unmatched environments, labels, and citations.

## 12. Scoring and delivery

Score only after resolving blockers:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Provenance | mixed/unknown | partly labeled | segment-level clear |
| Facts/math | contradiction | unverified gap | independently checked |
| Evidence | claims exceed evidence | mostly aligned | explicit ladder/scope |
| Terminology | drift/pseudo-term | minor inconsistency | stable and defined |
| Logic | jumps/templates | understandable | object-driven and complete |
| Paragraphs | flat/overfull | mixed | hierarchical and purposeful |
| Structure | repeated roles | some overlap | distinct responsibilities |
| Rhythm/voice | uniform/role leak | occasional | genre-appropriate |
| Versioning | stale conflict | partial cleanup | one authority, valid refs |

Any unresolved `Blocking` issue means fail regardless of score. Do not report a numerical “human-likeness” score as scientific detection; the matrix is a revision checklist, not an AI detector.
