# Enforceable Rule Library

Severity: `MUST` means failure invalidates the revision. `SHOULD` is the default unless the genre supplies a reason. `MAY` is optional.

## Contents

1. Evidence and factual integrity (`EVD`)
2. Lexicon (`LEX`)
3. Sentence form (`SYN`)
4. Logic and transitions (`LOG`)
5. Paragraphs (`PAR`)
6. Document structure (`DOC`)
7. Rhythm and voice (`RHY`, `VOI`)
8. Mathematics and technical prose (`MTH`)
9. Self-check contract

## 1. Evidence and factual integrity

### EVD-01 Claim strength follows evidence (`MUST`)

Do not use `证明、表明、决定、必然、普遍、稳健` when the evidence only supports association, a local simulation, one parameter setting, or an exploratory pattern. Name the evidence type and scope.

### EVD-02 Calibration is not validation (`MUST`)

Separate fitted anchors, internal consistency checks, sensitivity analysis, out-of-fit checks, and independent external validation. Never rename one as another for rhetorical strength.

### EVD-03 A limitation sentence is not evidence (`MUST`)

Do not treat repeated caution as proof of rigor. Bind limitations to a method, data source, parameter range, or failed test.

### EVD-04 Preserve negative results (`MUST`)

Report failed robustness, null effects, and contradictory cases. Use them to narrow the claim rather than hiding them.

### EVD-05 Avoid universal extrapolation (`MUST`)

Do not extend one function family, optimizer, data set, region, time window, or metric to all contexts. State the observed domain before interpretation.

### EVD-06 Cite propositions, not paragraphs (`MUST`)

Place a citation beside the factual or theoretical proposition it supports. Never invent bibliographic details.

### EVD-07 Resolve contradictions before style (`MUST`)

If a parameter is described as unchanged but a table varies it, flag and resolve the inconsistency. Stylistic polish cannot repair factual contradiction.

### EVD-08 Verify passage-level provenance (`MUST`)

Classify source passages as generated explanation, reconstructed answer, translation, transcription/OCR, quoted source, code/data, or human revision before attributing their style to a model. A file-level assistant write event does not make every sentence model-authored.

### EVD-09 Align quoted evidence with the proposition (`MUST`)

A quotation must contain readable language that supports the attached proposition. A matching page number, nearby OCR text, title keyword, or approximate anchor is not enough. Mark a passage `unverified` when the exact supporting sentence cannot be located; do not continue with `therefore this is supported`.

### EVD-10 Verify documentation facts against authority (`MUST`)

Check algorithm names, class paths, parameters, defaults, return values, performance claims, and citations against source code, tests, or the cited paper. A complete API layout, runnable-looking example, or polished comparison table is not evidence that the facts are real.

### EVD-11 Separate workflow completion from content correctness (`MUST`)

`Covered`, `transcribed`, `compiled`, `no placeholders`, `lint clean`, and `closed` prove only their named workflow states. Claim mathematical correctness, OCR fidelity, answer validity, or model validity only after an independent content-specific check.

### EVD-12 Match numeric precision to identification strength (`MUST`)

Do not report excessive decimal precision for empirical parameters, single-anchor calibrations, normalized proxies, or weakly identified outputs. Match significant digits to measurement/identification strength, report sensitivity intervals, or label values as internal simulation values.

### EVD-13 Do not rename ranking stability as model validation (`MUST`)

Agreement across equal weighting, entropy weighting, CRITIC, or weight perturbations only tests ranking stability for the given indicator matrix. It does not validate indicator choice, model truth, causal mechanism, or external ecological validity.

## 2. Lexicon

### LEX-01 Evidence-gate evaluative adjectives (`MUST`)

Words such as `显著、有效、完整、准确、合理、稳健、全面、深入` require a test, comparison, criterion, or concrete scope.

### LEX-02 Replace management metaphors (`SHOULD`)

Replace `闭环、抓手、落地、主线、口径、赋能、收口、路线图` with the actual research operation. Keep them only in internal plans when they name a real workflow.

### LEX-03 Replace universal nouns (`SHOULD`)

Audit `机制、框架、体系、路径、模式、维度、层面`. Replace them with a variable relation, algorithm stage, causal hypothesis, or measurement when possible.

### LEX-04 Keep one term per concept (`MUST`)

Do not rotate among synonyms to appear varied. Define a term once and reuse it.

### LEX-05 Limit unexplained English (`SHOULD`)

Introduce an English term only when standard or ambiguity-reducing. Define it at first use.

### LEX-06 Remove vague deixis (`SHOULD`)

Replace `这一点、上述内容、相关问题、这种情况` when the antecedent is not unique.

### LEX-07 Avoid ornamental academic phrases (`SHOULD`)

Delete `具有重要意义、值得注意的是、从某种程度上说、不可忽视的是` unless the following sentence cannot stand alone.

### LEX-08 Reject pseudo-technical and theatrical intensifiers (`MUST`)

Use `泛函、同构、仿射、齐次化、探针、系统不变量` only when their mathematical definitions apply. Remove theatrical phrases such as `宇宙级纯净、完美归零、奇迹般、铁证如山、灰飞烟灭、锁死、吐出` from academic prose.

### LEX-09 Keyword scans are locators, never acceptance gates (`MUST`)

A zero count for selected words proves only that those literal strings are absent. Do not infer human authorship, non-template reasoning, mathematical correctness, or completed de-AI revision. Acceptance requires whole-argument reading and the applicable validation gates.

## 3. Sentence form

### SYN-01 Remove drafting instructions (`MUST`)

Convert `后文将、正文里要、表格的作用是、这样写、这里需要强调、对论文写作而言` into the actual method, result, or boundary.

### SYN-02 Limit false binary contrast (`SHOULD`)

Use `不是 A，而是 B` only when A and B are genuine alternatives. Otherwise state B directly or use a non-exclusive correction.

### SYN-03 Break mechanical enumeration (`SHOULD`)

Do not default to `首先、其次、再次、最后` or three parallel clauses. Keep enumeration only when order or exhaustive categories matter.

### SYN-04 Split overloaded sentences (`SHOULD`)

Split a sentence that combines background, method, result, interpretation, limitation, and significance. Let numbers and research objects serve as subjects.

### SYN-05 Avoid repeated sentence stems (`SHOULD`)

Do not begin adjacent sections with an identical template such as repeated `本问的优点不在于...而在于...`.

### SYN-06 Prefer verbs to nominalization stacks (`SHOULD`)

Replace chains of `性、化、度、机制` nouns with the concrete operation and agent.

### SYN-07 Use modality precisely (`MUST`)

Distinguish `可能、可、倾向、支持、提示、表明、证明`. Select the weakest verb that reflects the evidence.

### SYN-08 Do not manufacture symmetry (`SHOULD`)

Parallel form must correspond to parallel concepts. Unequal evidence deserves unequal syntax and length.

## 4. Logic and transitions

### LOG-01 Derive the method from a concrete gap (`MUST`)

Before a method name, specify what existing approaches fail to decide, measure, or explain. Avoid a generic `为解决上述问题，本文提出...` bridge.

### LOG-02 Continue through objects (`SHOULD`)

Prefer `该参数、这一轨道、表 2 的误差、问题一得到的 E(t)` over repeated generic connectors.

### LOG-03 Separate observation and mechanism (`MUST`)

Report the pattern first. Mark the mechanism as interpretation, hypothesis, or tested explanation.

### LOG-04 Give each transition a job (`SHOULD`)

Use a connector only when the relation is identifiable: cause, contrast, concession, sequence, or scope shift.

### LOG-05 Establish an information exit (`SHOULD`)

Once a claim and boundary are established, do not restate them in analysis, results, advantages, limitations, and conclusion.

### LOG-06 Separate research from editorial control (`MUST`)

Keep version labels, `锁定主线`, and writing instructions in plans. Convert them to research reasoning before publication.

### LOG-07 State what would change the conclusion (`SHOULD`)

For critical experiments, state the decision criterion or how an opposite result would narrow the claim.

## 5. Paragraphs

### PAR-01 One dominant job (`SHOULD`)

A paragraph should mainly define, report, explain, compare, qualify, or synthesize. Split paragraphs performing four or more functions.

### PAR-02 Put evidence next to the claim (`MUST`)

Place numbers, citations, or equations immediately after or within the claim they support.

### PAR-03 Consolidate disclaimers (`SHOULD`)

State a calibration or validity boundary at first use and refer back briefly. Do not copy it into every section.

### PAR-04 Allow asymmetric length (`SHOULD`)

Give key mechanisms and conflicting results more space than routine context.

### PAR-05 Do not close every paragraph (`SHOULD`)

Avoid a summary sentence after every small point. End with evidence or a qualified inference when appropriate.

### PAR-06 Use examples as evidence units (`SHOULD`)

Keep one primary example and one counterexample in the main text. Move repeated encodings into exercises or appendices.

## 6. Document structure

### DOC-01 Assign distinct section responsibilities (`MUST`)

Methods explain what was done and why; results report observations; discussion interprets them; limitations delimit inference.

### DOC-02 Reduce heading inflation (`SHOULD`)

A heading must group a meaningful block of evidence or reasoning. Merge headings whose body only restates the title.

### DOC-03 Write the abstract after the body (`SHOULD`)

Preserve the question, method, central result, and boundary. Do not compress every subsection into one overloaded sentence.

### DOC-04 Synthesize in the conclusion (`MUST`)

Separate robust conclusions, conditional conclusions, unresolved questions, and implications; do not list every section again.

### DOC-05 Move audit detail to appendices (`SHOULD`)

Keep line-level ledgers and full checks available without making the paper body speak like an audit log.

### DOC-06 Treat version families as one composition (`MUST`)

Distinguish genuine revisions from duplicate files. Do not infer prevalence from copied templates or worktree versions.

### DOC-07 Replace superseded claims across the document (`MUST`)

When a new section changes a conclusion, list what is deleted, retained, and replaced, then search the whole document for the old claim. A late disclaimer or `unified position` section does not neutralize contradictory instructions that remain in earlier chapters or appendices.

### DOC-08 Recheck global structure after incremental expansion (`SHOULD`)

After appending chapters, verify heading numbers, cross-references, repeated explanations, and the single authoritative location of each conclusion. Do not let an onboarding guide or report grow by dated additions without reintegrating its earlier structure.

### DOC-09 Separate inherited statements from generated solutions (`MUST`)

When one TeX/MD file contains source questions, OCR text, official answers, reconstructed answers, and generated explanations, label provenance by segment. Derive model style only from attributable generated prose; do not count source or publisher wording.

### DOC-10 Reintegrate appended textbook families (`MUST`)

After adding a chapter family, verify that the authority main file includes it, prerequisites are introduced, difficulty changes are intentional, definitions are not duplicated, and cross-references resolve. An unattached chapter is not automatically part of the published book.

## 7. Rhythm and voice

### RHY-01 Vary rhythm by argumentative load (`SHOULD`)

Use short sentences for central findings or distinctions; longer sentences only when relations must be read together.

### RHY-02 Create emphasis through detail (`SHOULD`)

Give the central result concrete numbers, variables, or cases. Do not make every sentence sound like a conclusion.

### RHY-03 Reduce repeated high-density summaries (`SHOULD`)

If every paragraph has a chain, list, quoted term, and final judgment, reduce compression and let evidence carry emphasis.

### RHY-04 Preserve hierarchy inside derivations (`SHOULD`)

Give decisive constructions, non-obvious transformations, and failure cases more space than reversible algebra. Do not narrate every substitution at the same intensity; uniform step-by-step commentary hides the proof's actual idea.

### RHY-05 Weight derivations by proof importance (`SHOULD`)

Compress reversible substitution and expansion; expand the construction, sign decision, branch exclusion, and theorem condition that carry the proof. A line-by-line `substitute-expand-simplify` rhythm can make an incomplete proof look exhaustive.

### VOI-01 Use the appropriate author role (`MUST`)

Do not let a paper speak as a project manager, reviewer, customer-service agent, or editor.

### VOI-02 Remove commands from published prose (`SHOULD`)

Convert `必须、绝对不要、死守、锁定` into conditions or definitions. Preserve necessity only when technical.

### VOI-03 Avoid marketing and coaching tone (`SHOULD`)

Remove `亮点、赋能、秒杀、救命、翻盘、各说各话` unless the genre requires it.

## 8. Mathematics and technical prose

### MTH-01 Define symbols before use (`MUST`)

State what a symbol represents, its domain/unit when relevant, and why it enters the model.

### MTH-02 Explain non-obvious transformations (`MUST`)

State the purpose and operation of every transformation that changes the conclusion, introduces a restriction, selects a branch, or enables a theorem. This rule governs logical completeness; use `RHY-04` to decide how much routine reversible algebra to narrate.

### MTH-03 Distinguish simulation from reality (`MUST`)

Write `under this parameterization, the model produces...`; do not state simulation as real-world causation without evidence.

### MTH-04 Keep tables and figures evidentiary (`SHOULD`)

Do not explain how a table helps the reader. Report what it shows, the comparison basis, and uncertainty.

### MTH-05 Verify symbolic steps independently (`MUST`)

Check every changed object, sign, exponent, derivative, index, and denominator independently of prose fluency. A continuous equality chain is not evidence that each transformation is valid. Prefer an exact formula over an approximation when available; if approximation is necessary, state its error and applicability conditions.

### MTH-06 Type-check mathematical objects (`MUST`)

Before using linearity, identify whether the object is linear, bilinear, affine, quadratic, symmetric, invariant, equivalent, or a polarized form, and test the defining properties on its actual domain. Constant terms matter: an expression such as `E(M,N)-1` is not an ordinary bilinear form, even if an affine combination with coefficients summing to one preserves a related identity.

### MTH-07 Do not promote special cases to a global locus (`MUST`)

Checking several parameter values, symmetric positions, or numerical samples cannot establish a complete locus, envelope, tangency family, or universal identity. Derive the general equation or prove the required uniqueness/degree argument.

### MTH-08 Expose decisive elimination and factorization (`MUST`)

Phrases such as `after elimination`, `after simplification`, or `there exists a constant such that` must be followed by the key resulting equation, factor, coefficient relation, and non-degeneracy conditions. Put long routine algebra in an appendix, but never omit the step that carries the conclusion.

### MTH-09 State theorem conditions at the point of use (`MUST`)

When invoking Poncelet closure, polarity, a curve pencil, Taylor expansion, Rolle's theorem, or an asymptotic comparison, state and verify the conditions needed in the current problem. A familiar theorem name cannot bridge an unproved change of domain, multiplicity, regularity, or parameter range.

### MTH-10 Preserve quantifiers and witness dependence (`MUST`)

Do not reuse independent existential witnesses as one common value. Record dependencies such as `\xi=\xi(x,y)` and keep them through the conclusion. A statement `for each x there exists \xi_x` does not imply that one fixed `\xi` works for all x. Verify the domain of temporary transformations such as `\log|y|`; it may be narrower than the original problem.

### MTH-11 Local evidence cannot prove a global sign (`MUST`)

A Taylor/Pade expansion near one point, finite samples, or a leading asymptotic term cannot establish sign on an entire interval. Supply a signed remainder, interval monotonicity, global bound, Sturm/Bernstein certificate, or a theorem whose assumptions are verified.

### MTH-12 Make elimination reversible (`MUST`)

For elimination, squaring/cubing, denominator cancellation, or resultants, record original conditions, lost factors, introduced branches, and equivalence direction. Substitute all candidates back into the original system. An implication from the original system to an eliminated equation does not make the equation the exact locus/envelope.

### MTH-13 Prove envelope and tangency regularity (`MUST`)

For an envelope or persistent tangency, verify parameter smoothness, real common points, repeated-root/parameter derivative conditions, regularity and nonzero gradients, gradient collinearity, parameter correspondence, and all singular/degenerate cases. Exclude extra branches of the target equation.

### MTH-14 Lock mathematical object identity through a proof (`MUST`)

Maintain an object ledger for `f,F,p,G,h` and similar symbols. Interpolants, primitives, original functions, and derivatives cannot silently exchange roles. Each derivative order must map back to the defined object.

### MTH-15 Check quotients and logarithms at zeros (`MUST`)

Before using `f''/f`, `log f`, a reciprocal, normalized gradient, or division by a parameter/discriminant, prove the denominator/non-log argument is valid on the selected domain. Split at zeros, use limits, or revise the claim; absolute values do not make undefined points disappear.

### MTH-16 Keep branch and orientation data explicit (`MUST`)

Square roots, inverse trigonometric functions, indefinite integrals, line/surface integrals, and projective/affine parameterizations must retain branch, interval, orientation, and absolute-value information. “Differs by a constant” cannot hide a cross-branch jump.

### MTH-17 Recheck inequality direction after sign-sensitive operations (`MUST`)

Record the sign when multiplying/dividing, taking logs, squaring, or substituting parameters. If one proof contains both `>=` and `<=` for the same statement, or assumptions nearly force an empty/trivial set (for example `p,q>=0` and `pq<=0`), repair the proposition before rewriting prose.

### MTH-18 Asymptotic dominance is not a base-case proof (`MUST`)

To prove an inequality from a specific integer onward, verify the initial range and show a ratio, difference, induction step, or monotonic property preserves it. “Exponential eventually grows faster than cubic” only describes the tail.

### MTH-19 Translate nonstandard terminology to standard mathematics (`MUST`)

When introducing an in-house system such as `dual-variable`, `virtual circle`, or `operator`, give the standard object, equations, constants, parameter domain, and exact equivalence. Verify every geometric story by direct algebra/differentiation. Remove the terminology if no standard translation exists.

## 9. Self-check contract

Before delivery, answer yes/no:

1. Are all strong claims tied to evidence and scope?
2. Were contradictions resolved or flagged?
3. Are numbers, equations, citations, and negative results preserved?
4. Does each section have a distinct responsibility?
5. Does each paragraph have one dominant job?
6. Are repeated disclaimers consolidated?
7. Are method names derived from concrete gaps?
8. Are generic management nouns replaced where possible?
9. Are false binary contrasts and mechanical lists reduced?
10. Does rhythm reflect importance rather than symmetry?
11. Are planning instructions absent from final prose?
12. Could any sentence imply stronger evidence than the study has?
13. Are theorem witnesses, quantifiers, and temporary transformation domains preserved?
14. Are workflow states (`transcribed`, `compiled`, `lint clean`) kept separate from content correctness?
15. Is every displayed precision justified by measurement or parameter identification strength?
16. Is ranking stability named without implying indicator, mechanism, or external validation?
17. Were keyword scans used only to locate passages, followed by whole-argument review?
18. Are inherited statements, OCR, quotations, official answers, and generated solutions separated by segment?
19. Is every appended textbook/chapter family included in the authority entry point with prerequisites and valid cross-references?
20. For every local-to-global argument, is the entire domain covered by explicit certificates?
21. For elimination, squaring, division, and resultants, were lost conditions, added branches, and reverse substitution checked?
22. For envelope/tangency claims, were regularity, real existence, parameter recovery, gradients, and degeneracies checked?
23. Does an object ledger prevent functions, primitives, interpolants, derivatives, points, and vectors from changing roles?
24. Were zeros, logarithm domains, branches, orientation, inequality direction, and finite base cases preserved?
25. Can every nonstandard mathematical term be translated into a standard object and a verified equivalence?

Any `no` on a `MUST` rule blocks delivery.
