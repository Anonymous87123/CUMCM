# Source-Derived Cases

These cases come from manually read MD/TEX documents in the local corpus. Treat excerpts as diagnostic evidence, not reusable templates.

## Thematic index

- **Composition and voice:** cases 1-10, 20, 22-24, 27, 34-35.
- **Evidence and empirical claims:** cases 3-4, 6, 8, 10-12, 14, 16-17, 31-32, 41-44.
- **Provenance, OCR, and inherited material:** cases 19, 21, 26, 31, 41, 45.
- **Version and document integration:** cases 18-19, 33-34, 51.
- **Mathematical validity:** cases 13, 15, 25, 28-30, 36-40, 45-50.
- **Positive behaviors to preserve:** cases 3, 6, 8, 44-45.

## 1. Meta-writing residue

Source: user-confirmed GPT `main.tex`.

Problem:

> “表格的作用也在于让读者一眼看出……”

The sentence instructs an editor instead of reporting science.

Rewrite:

> “表 2 显示，三个情景的顶级捕食者指标均下降，其中高阻隔情景的降幅最大。”

Rules: `SYN-01`, `MTH-04`.

## 2. Repeated contrast template

Source: user-confirmed GPT `main.tex`, five consecutive summaries.

Problem:

> “本问的优点不在于……而在于……”

The same stem is followed five times by `其局限同样需要写清`, forcing unequal evidence into identical positive/negative slots.

Rewrite one concrete case:

> “问题一仅用 `gain_scale` 对 1.8 倍总量锚点进行校准。CPUE* 未进入目标函数，`H_0` 也未参与拟合，因此两者分别承担一致性检查和反事实比较，而非额外校准条件。”

Rules: `SYN-02`, `SYN-05`, `SYN-08`, `PAR-04`.

## 3. Calibration versus validation

Source: user-confirmed GPT `main.tex`.

Preserve this valuable distinction:

> “硬锚点校准……外推一致性检验，而非独立外部验证。”

State it once at the first method/result boundary, then refer back briefly.

Rules: `EVD-02`, `PAR-03`.

## 4. Repeated limitation

Source: user-confirmed GPT `main.tex`.

The non-universality of a 3.22 threshold is explained in analysis, results, robustness, and advantages/limitations.

Consolidated rewrite:

> “3.20-3.22 的符号跨越只在基准初值和 90 时长窗口中稳定出现；积分延长至 150 或 200 后不再保留。因此本文不把 3.22 解释为普适阈值。”

Rules: `EVD-03`, `LOG-05`, `PAR-03`.

## 5. Management vocabulary

Source: project handover and manuscript-planning MD files.

Examples: `最后收口、唯一主线、必须死守、锁定、回滑`.

These work in internal governance but not in a paper. Convert them:

| Internal wording | Paper wording |
|---|---|
| 锁定主线 | 明确研究问题 |
| 收口 | 完成验证并归档结果 |
| 口径 | 样本范围/变量定义/统计定义 |
| 闭环 | 校准、检验与复现步骤 |
| 回滑 | 恢复已排除的旧假设 |

Rules: `LEX-02`, `LOG-06`, `VOI-01`.

## 6. Strategy strength

Source: `listening_blind_guess_strategy.md`.

Useful excerpt:

> “短项只是弱加分。短要和‘关系完整、能接住题问’一起看，不能因为短就直接选。”

The rule states its strength and dependency instead of pretending to be a law. Transfer this to academic claims by naming the subset, effect strength, and alternative explanation.

Rules: `EVD-01`, `EVD-05`, `SYN-07`.

## 7. Literature-template reuse

Source: five Probet literature-reading MD files.

Repeated excerpt:

> “先讲论文主线，再引用 PDF 原文做精读，最后说明它能怎样支撑我们的数学探针，以及哪些地方不能照搬。”

Move common project background to a series introduction. For each paper, preserve one unique mathematical object, assumption, failure case, and exact proposition it supports.

Rules: `DOC-06`, `PAR-06`, `LOG-05`.

## 8. Evidence-first experiment planning

Source: `sccd_experiment_master_plan_2026-05-21.md`.

Useful excerpts:

> “过去的返工，主要不是因为代码写不出来，而是因为实验设计总在事后才发现缺口。”
>
> “主表必须来自独立预算；shared-budget 只能是边界说明。”

Define claim, required evidence, decision criterion, stopping rule, and artifact before commands. Remove internal labels from published prose.

Rules: `LOG-07`, `DOC-01`, `VOI-01`.

## 9. Teaching redundancy

Source: `cpp_class_object_traps.md`.

Observed structure: map -> rule -> code example -> typical question -> answer -> pitfall -> memorization version.

Keep one explanatory example and one counterexample in the main text. Move additional forms to exercises or an appendix.

Rules: `PAR-06`, `LOG-05`, `DOC-05`.

## 10. Model-to-reality boundary

Source: user-confirmed GPT `main.tex`.

Problem:

> “后文若出现底层资源暂时走低，也应结合消费者增长后的资源压力理解……”

Rewrite:

> “在当前参数设定下，底层资源在禁渔后期继续下降。该模拟结果与鱼类数量恢复并不矛盾：消费者增长可能先于资源补偿。该机制仍需河段观测数据验证。”

Rules: `SYN-01`, `LOG-03`, `MTH-03`, `EVD-01`.

## 11. Method prose contradicts a table

Source: user-confirmed GPT `main.tex`.

The prose says only one food weight changes by `±0.05`, other weights remain fixed, and weights are not renormalized. The table changes all three weights.

Action: Do not choose the smoother wording. Determine whether the experiment is a one-factor perturbation or a weight reallocation, then correct the method, table, and conclusions together.

Rules: `EVD-07`, hard failure.

## 12. Confounded scenario described as one factor

Source: user-confirmed GPT `main.tex`.

The `禁渔+污染` scenario also increases channel obstruction, but later differences are attributed to pollution alone.

Action: Hold obstruction fixed for a pollution-only contrast, or rename the scenario as a combined perturbation and remove single-cause language.

Rules: `EVD-01`, `LOG-03`, `LOG-07`.

## 13. One symbol denotes two biological objects

Source: user-confirmed GPT `main.tex`.

`S(t)` is defined as one rare species and reused inside another fish module for a different object.

Action: Rename module-specific states, update the symbol table and all equations, then rerun textual consistency checks. Do not treat symbol collision as typography.

Rules: `MTH-01`, `LEX-04`, hard failure.

## 14. Candidate interval advertised as a threshold

Source: user-confirmed GPT `main.tex`.

Only 5 of 75 robustness tests retain the reported crossing, and longer integration windows do not. Calling it a universal `混沌阈值` exceeds the evidence.

Rewrite pattern: `基准初值与有限时间窗口下的混沌候选区间`.

Rules: `EVD-01`, `EVD-05`, `SYN-07`.

## 15. Fluent derivation with a changed object or exponent

Source: manually reviewed calculus TeX observation sample.

A center-difference derivation changes `f(x_0-\Delta x)` into `f'(x_0-\Delta x)` inside the numerator; another parametric derivative simplifies `e^{-t}/e^t` as `e^{2t}` instead of `e^{-2t}`. The prose and equality chain remain smooth.

Action: Verify objects, signs, exponents, and denominators line by line. Do not treat stylistic continuity as a correctness signal.

Rule: `MTH-05`, hard failure.

## 16. Proxy error called validation

Source: user-confirmed modeling `main.tex`.

The abstract calls a predicted 1.838-fold change validation against a local 2.2-fold observation. The body reports a 16.47% error and later downgrades the comparison to directional consistency.

Why it matters: the abstract is stronger than the body, and no predeclared validation threshold exists.

Rewrite:

> “The proxy and local observation change in the same direction; the predicted fold change is 16.47% lower. Because the local record is not an independent validation set and no acceptance threshold was specified, this comparison is an out-of-fit directional check.”

Rules: `EVD-01`, `EVD-02`, `DOC-03`.

## 17. Sensitivity category renamed for rhetorical strength

Source: user-confirmed modeling `main.tex`.

The abstract claims 2,000 local parameter perturbations, but the method perturbs only composite-index weights. Weight sensitivity does not establish ecological parameter, solver, initial-state, or structural robustness.

Rewrite:

> “We sampled 2,000 admissible composite-index weight vectors. This tests ranking sensitivity to aggregation weights; model parameters, initial conditions, solver settings, and model structure were not perturbed.”

Rules: `EVD-01`, `LEX-04`.

## 18. Undefined project item propagated across a plan

Source: `sccd_experiment_master_plan_2026-05-21.md`.

The plan defines `P2/P3`, then explains and later references a nonexistent `P4`; data-source and execution-order descriptions drift with the identifiers.

Action: build an ID registry (`ID, claim, data, command, artifact, status`), remove undefined IDs, verify every reference, and regenerate execution order from the registry.

Rules: `DOC-07`, `EVD-07`.

## 19. Historical documents embedded as current README

Source: fully read 6,356-line `Student_Score_Management_System/README.md`.

Chapters 1-18 describe current code; chapter 19 embeds six old Markdown documents and later status material. The file therefore claims six and seven Admin GUI tabs, while a source-level audit finds that the current `AdminWindow.cpp` mounts eight pages including teacher and background settings. It also mixes Qt not implemented/implemented/not manually accepted, and self-test fully read-only/first-run mutating. Teacher-management prose conflicts with menus, header/source lists, and CMake entries.

Action: keep one current truth table for roles, menus, pages, source files, test mutations, and acceptance status. Segment chapter 19 as `HIST`, `PLAN`, `AUD`, or `CURRENT` instead of calling it uniformly stale. Move historical documents to dated/versioned appendices and mark stale fields.

Rules: `DOC-06`, `DOC-07`, `EVD-07`.

## 20. Uniformly narrated algebra hides the insight

Source: conic and calculus textbook families.

Pattern:

```text
define every variable -> explain every role -> narrate every substitution
-> expand every reversible equality -> restate the conclusion -> add a route summary
```

Why it matters: the key construction and routine manipulation receive equal space. Readers cannot identify what makes the proof work.

Action: one paragraph for the idea, one displayed decisive identity, routine calculation compressed or moved to an appendix, and one boundary/counterexample.

Rules: `RHY-04`, `PAR-04`, `RHY-01`.

## 21. Audit clean status mistaken for mathematical correctness

Source: solution-quality batch audit family.

Formatting flags and forbidden-word counts are cleared, but later reviews still find unclosed derivations, Green/area-method cross-contamination, recurrence coefficient errors, sign errors, and an incorrect Hooke-force model.

Action: use independent gates for source completeness, TeX integrity, mathematics, numerical reproduction, and visual output. A release decision must list exactly which gates passed.

Rules: `EVD-11`, `EVD-03`, `MTH-05`, `DOC-05`.

## 22. Four voices mixed in one artifact

Source: cross-family manual reading.

Observed voices:

- research editor: `主线、锁定、收束、门禁`;
- reviewer simulator: claim/evidence/boundary/objection;
- exam coach: `题眼、口诀、弱加分、候选簇`;
- quality manager: `整改口径、复核、放行依据`.

Action: choose the genre authority. Move editor instructions to a plan, reviewer objections to discussion, heuristics to a labeled strategy manual, and QA states to an audit appendix.

Rules: `VOI-01`, `LOG-06`, `DOC-01`.

## 23. Decision-tree teaching repeated at every level

Source: large mathematics textbook families.

Recurring vocabulary (`入口、路线、底座、母式、送回、压回、触发、主路`) makes knowledge searchable, but the same route appears at chapter, section, example, solution, pitfall, and mnemonic levels.

Action: retain the route at the highest useful level. In each example, name only the decision that differs; in the solution, show the decisive calculation.

Rules: `DOC-01`, `PAR-06`, `LOG-05`.

## 24. Small-sample strategy becomes an absolute command

Source: CET-6 Section B report family.

Some conditional patterns occur only 8-12 times, while later text admits they cannot be commands. Other passages use `铁律、永远` or treat negative correlation as absolute non-adjacency.

Action: report denominator and uncertainty, label the signal weak, include a counterexample, and provide an exit rule. Keep statistical observation separate from examination action.

Rules: `EVD-01`, `EVD-05`, `SYN-07`.

## 25. Correct multiple-choice answer from a fragile approximation

Source: manually reviewed probability-exercise TeX observation sample.

The solution uses option clues and a normal third raw moment to explain a binomial third moment. The numerical answer happens to agree for `p=0.5`, but the reasoning is not generally transferable.

Action: Use the exact binomial factorial-moment identity first. If an approximation is pedagogically useful, label it, quantify its error, and keep it separate from proof.

Rules: `MTH-05`, `EVD-01`.

## 26. A file-level write event does not establish sentence authorship

Source: manually reviewed exam, OCR, macro-dictionary, and audit files.

Some assistant-written TeX files contain transcribed questions, OCR text, copied source passages, generated solutions, and audit notes in the same file. Counting the whole file as model prose attributes textbook and source wording to GPT.

Action: label passage identity before extracting style evidence. Use generated solutions and audit prose as model samples; treat questions, quoted papers, OCR text, dictionaries, and data as source material.

Rules: `EVD-08`, `DOC-09`.

## 27. Clean vocabulary with unchanged proof structure

Source: manually reviewed conic-section cleanup checklists and revised chapters.

Words such as `perfect closure`, `collapse`, `affine combination`, and game-like metaphors were removed, but the revised proofs still narrate every substitution, assign a role to every symbol, and give routine algebra the same weight as the decisive construction.

Action: identify the proof's one or two decisive moves, expand those, combine reversible algebra, and keep one verification line for routine steps.

Rules: `RHY-04`, `RHY-05`, `MTH-02`.

## 28. An affine expression called bilinear

Source: `D:\code LateX\圆锥曲线\chapters\chap4.tex`.

The chapter defines `T(M,N)=E(M,N)-1`. The constant term means `T` is not bilinear on position vectors, although it preserves an affine-combination identity when coefficients sum to one. Later passages repeatedly call it a symmetric bilinear form and expand it as if ordinary bilinearity held.

Action: call `E` the bilinear form and `T` its affine polarization expression; state exactly which affine identities are valid.

Rule: `MTH-06`.

## 29. Three special positions used to identify an envelope

Source: `D:\code LateX\圆锥曲线\chapters\chap5.tex`.

After checking three limiting or symmetric positions, the solution concludes that the complete envelope is a particular circle. Those checks show compatibility, not uniqueness for every parameter value.

Action: derive the dual locus of line coefficients or prove that the previously obtained quadratic relation is exactly the dual conic, including non-degeneracy and uniqueness.

Rule: `MTH-07`, hard failure.

## 30. Elimination named but not shown

Source: `D:\code LateX\圆锥曲线\chapters\chap5.tex` and `chap6.tex`.

The text says that eliminating two direction vectors leaves only a quadratic equation in a pole, or that a radius formula follows `after simplification`, but does not show the decisive resultant, factorization, or coefficient identity.

Action: provide the reduced equation and the conditions under which discarded factors are nonzero. Move only routine expansion to an appendix.

Rule: `MTH-08`.

## 31. Nearby OCR treated as an exact supporting quotation

Source: manually reviewed Probet literature-note family.

Some blocks explicitly state that the old short anchor was not matched and that nearby text from the same PDF page is quoted instead. The following paragraph nevertheless says that the project conclusion `is supported`.

Action: mark the claim unverified until a readable sentence matching the proposition is found. Page proximity is a retrieval hint, not evidentiary alignment.

Rule: `EVD-09`, hard failure.

## 32. Complete API documentation with invented identities

Source: `D:\LSGO-platform\docs\zh\api\algorithms.md`.

The page supplies bilingual headings, class directives, examples, parameter tables, star ratings, and use recommendations, while expanding DG2, RDDSM, and CSG incorrectly and pointing to class paths that do not match the repository layout.

Action: generate API facts from importable objects or verified source references. Delete unsourced performance stars and recommendations unless benchmark evidence is cited.

Rule: `EVD-10`, hard failure.

## 33. A late unified statement leaves old instructions active

Source: manually reviewed Section B report versions and long project handover documents.

Later chapters announce a final unified position, but earlier workflows and appendix totals still encode the superseded conclusion. Repetition and disclaimer language create an appearance of control without resolving the document state.

Action: keep a replacement ledger, delete or rewrite every conflicting occurrence, and recompute tables from the same sample definition.

Rules: `DOC-07`, `EVD-07`.

## 34. Heading-number drift after repeated additions

Source: `D:\LSGO-platform\readme_demo_test.md` and `readme_utils.md`.

Top-level sections advance while nested numbers remain one chapter behind; the distinction between `run` and `observer` is then explained again in adjacent chapters. This is not a local numbering typo but evidence that appended material was not reintegrated.

Action: regenerate the outline, assign one responsibility to each section, merge repeated explanations, and verify all cross-references after expansion.

Rules: `DOC-08`, `LOG-05`.

## 35. A zero banned-word count declared the prose clean

Source: `D:\code LateX\简单导数\Gemini残留统计第四轮.md`, `第五轮.md`, and `第六轮.md`.

The fourth-round report says all high-risk patterns reached zero and the remaining prose no longer had an obvious model voice. The sixth-round manual read later says that judgment was optimistic: whole regions still used strategy prefaces, proof-script transitions, uniform step commentary, and unresolved mathematical gaps.

Action: Use banned-word scans only to locate or verify literal residues. Acceptance requires a full argument read covering sentence function, proof responsibility, rhythm, and correctness.

Rules: `LEX-09`, `EVD-11`, `RHY-04`, `DOC-01`, `MTH-05`.

## 36. A stable matrix routine with inconsistent conclusions

Source: `D:\code LateX\简单导数\chapters\chap9.tex`.

One displayed Fibonacci sum is stated with right side `2^n`, while the derivation obtains `2^(n-1)`. A product formula uses `(-1)^(k+1)` in the conclusion but `(-1)^k` in the Cassini step; substituting `k=2` exposes the contradiction immediately.

Action: After a template-based derivation, compare the headline, every intermediate identity, and the final line, then test the smallest admissible indices. Fluency and method familiarity do not establish internal consistency.

Rule: `MTH-05`, hard failure.

## 37. An affine two-point expression advertised as bilinear

Source: `D:\code LateX\圆锥曲线\chapters\chap4.tex:20,693`.

Observed text defines

```text
T(M,N)=E(M,N)-1
```

and later calls `T` a symmetric bilinear form. Symmetry may hold, but ordinary
bilinearity does not: `T(0,N)=-1`, so the zero-vector test already fails. The
identity used later is an affine-combination identity under coefficients whose
sum is one, not unrestricted linearity in each argument.

Why this is high risk: the technical word sounds precise and makes later
distribution steps look licensed. A stylistic replacement cannot repair the
proof because the set of legal algebraic operations has changed.

Audit procedure:

1. State the actual domain: vectors, points, affine coordinates, or homogeneous
   representatives.
2. Run the zero, scalar-multiplication, and addition tests for each argument.
3. Separate symmetry from linearity; one never implies the other.
4. Identify every later step that invokes `linear`, `bilinear`, `affine`,
   `polarized`, or `invariant`.
5. Reprove those steps using only the property that actually holds.

Acceptable repair:

> Let `E` be the symmetric bilinear form associated with the conic and define
> `T(M,N)=E(M,N)-1`. The function `T` is symmetric and affine in each point
> coordinate. If `P=alpha A+beta B` with `alpha+beta=1`, then `T(P,C)` preserves
> that affine combination. The following argument uses only this restricted
> identity, not bilinearity of `T`.

Regression check: search the whole document family for `双线性`, `线性`, `仿射`,
and the symbol `T`; verify the invoked property at every occurrence.

Rules: `MTH-06`, `LEX-08`, hard failure.

## 38. A local Taylor expansion used as a global sign certificate

Source: `D:\code LateX\简单导数\chapters\chap6.tex:184-190`.

Observed failure: several terms of an expansion around zero are listed, after
which the text asserts `H(t)>0` for every `t>0`. The center, remainder, and
uniform domain are not controlled. Replacing `由展开可见` with `显然` merely
hides the same gap. A forward audit also found that a later `t^10` coefficient
is negative, so even the stronger unstated claim “all series coefficients are
positive” is unavailable.

Required proof partition:

| Region | Acceptable certificate |
|---|---|
| `0<t<=delta` | Taylor formula with a signed or absolutely bounded remainder |
| `delta<=t<=T` | derivative monotonicity, interval arithmetic, Sturm/Bernstein certificate, or another reproducible compact-interval proof |
| `t>=T` | explicit dominant-term inequality plus verification that the chosen threshold is valid |

Audit procedure:

1. Record expansion center, order, convergence domain, and remainder form.
2. Mark the exact interval established by the local calculation.
3. Test whether an unexamined middle interval remains.
4. Prove each remaining region separately and reconcile boundary points.
5. Downgrade the conclusion to local positivity if no global certificate exists.

Acceptable wording:

> For `0<t<=delta`, the remainder bound gives `H(t)>0`. For
> `delta<=t<=T`, the derivative has no zero and `H(delta)>0`. For `t>=T`,
> inequality (x) bounds the negative terms by half of the leading positive
> term. These three intervals cover `t>0`.

Rules: `MTH-11`, `MTH-09`, hard failure.

## 39. Elimination output promoted to an exact envelope

Source: `D:\code LateX\圆锥曲线\chapters\chap7.tex`, moving-circle family.

Observed failure: eliminating the parameter from `F(x,y,s)=0` and a derivative
condition yields `G(x,y)=0`; the prose immediately states that `G=0` is the
envelope. Squaring, cubing, denominator cancellation, or a resultant can add
branches, remove exceptional parameters, and replace equivalence with one-way
implication. An eliminated algebraic closure is only a candidate.

Required transformation ledger:

| Step | Input conditions | Operation | Lost factor/domain | Introduced branch | Direction |
|---|---|---|---|---|---|
| 1 | `F=0`, parameter domain | differentiate/eliminate | ... | ... | `=>` or `<=>` |
| 2 | ... | square/cube/divide/resultant | ... | ... | ... |

Acceptance levels:

- **Candidate only:** prove original envelope points satisfy `G=0`.
- **Exact locus:** additionally recover an admissible parameter for every
  claimed regular point of `G=0` and substitute into the original system.
- **Envelope/tangency:** additionally verify repeated-root or parameter
  derivative conditions, real common points, nonzero gradients, gradient
  collinearity, and singular/degenerate cases.

Acceptable restricted conclusion:

> The preceding one-way elimination shows that the envelope is contained in
> the candidate algebraic curve `G=0`. The reverse parameter recovery and the
> singular branches remain unproved, so equality is not claimed here.

Regression check: factor the resultant, list every discarded factor, test
candidate branches against the original equations, and verify the parameter
range rather than accepting a CAS simplification string.

Rules: `MTH-12`, `MTH-13`, `MTH-08`, hard failure.

## 40. A primitive, function, and interpolant exchange identities mid-proof

Source: `D:\code LateX\简单导数\chapters\chap1.tex:72`.

Observed failure: after defining a primitive `F`, the interpolation remainder
is written for `G=f-p`; later steps again use `F'''=p'''`. The notation looks
continuous, but the differentiated object and its regularity have changed.

Build this ledger before repair:

| Symbol | Definition | Object/order | Domain | Parameter dependence | Allowed derivatives |
|---|---|---|---|---|---|
| `f` | ... | original function | ... | ... | ... |
| `F` | primitive of `f` | function | ... | ... | ... |
| `p` | interpolating polynomial | polynomial | ... | nodes | all |
| `G` | difference used by theorem | function | ... | nodes | ... |

Repair decision:

- If the intended object is the primitive, use `G=F-p` consistently and verify
  endpoint/interpolation conditions and the required derivative order.
- If the intended object is `f`, rebuild the interpolation conditions and
  derivative argument from the start. Do not change one letter and retain the
  old conclusion.

Regression check: for every third derivative, trace the symbol back to its
definition and regularity assumption. Repeat for subscripts and parameterized
witnesses.

Rules: `MTH-14`, `MTH-10`, `MTH-05`, hard failure.

## 41. A clean workflow status renamed as content correctness

Source: manually reviewed examination audits, OCR closure reports, and solution
quality ledgers.

Observed failure: statements such as `8 pages covered`, `no placeholders`,
`compiles`, and `all automated flags cleared` are followed by `answers verified`
or `mathematically correct`. The latter is a different claim requiring an
independent content check.

Use a non-collapsible status ladder:

| Status | What it proves | What it does not prove |
|---|---|---|
| `transcribed` | expected pages/items have text | source fidelity or correctness |
| `source-compared` | text/formulas compared with image/source | mathematical validity |
| `mathematically-checked` | independent derivation or recomputation passed | external authority |
| `externally-validated` | matched an authoritative answer/data source under stated criteria | universality outside that source |

Acceptable release statement:

> All eight pages have been transcribed and source-compared. The direction
> integral and two surface-integral solutions have not yet been independently
> recomputed; mathematical acceptance therefore remains open.

Regression check: every completion adjective must name its gate and evidence.
Do not let `closed`, `clean`, or `released` stand without a defined object.

Rules: `EVD-11`, `LEX-01`, hard failure when correctness is claimed.

## 42. Internal numerical precision exceeds the evidence that identifies it

Source: user-confirmed Yangtze ecological modeling `main.tex`.

Observed failure: one approximate `1.8x` calibration anchor and several
hand-selected/normalized parameters produce outputs such as `1.805`, `1.838`,
and `4.213`. Three decimals aid deterministic reproduction, but the prose lets
them look like empirical measurement precision.

Audit procedure:

1. Label each reported number `observed`, `calibrated`, `assumed`, `simulated`,
   `derived index`, or `display-only`.
2. Trace significant digits to the weakest upstream measurement or
   identification step.
3. Separate stored computation precision from displayed inferential precision.
4. Report parameter perturbation or plausible range where identification is
   weak.
5. State explicitly when decimals are retained only to reproduce a run.

Acceptable wording:

> Under this normalized parameter set, the model output is approximately
> `1.81x`. Values in the reproducibility table retain three decimals for rerun
> consistency; they do not represent observational precision.

Rules: `EVD-12`, `MTH-03`, `SYN-07`.

## 43. Ranking stability renamed as model validity

Source: user-confirmed modeling paper, three scenarios evaluated by equal,
entropy, and CRITIC weights plus 2,000 weight perturbations.

Observed failure: the ranking remains stable under nearby aggregation weights,
and the paper calls this model validation or ecological robustness. The test
holds the indicator definitions, scenario sample, model structure, observation
error, and data source fixed.

Required claim decomposition:

```text
tested: ranking sensitivity to admissible weight changes
fixed: indicators, normalization, scenarios, generated outputs, model structure
not tested: indicator validity, causal mechanism, observational error,
            external ecological validity, alternate model classes
```

Acceptable wording:

> Given these four indicators and three simulated scenarios, the ordering is
> stable to the specified local weight perturbations. This analysis does not
> validate the indicator set, the ecological mechanism, or out-of-sample
> predictions.

Rules: `EVD-13`, `EVD-02`, `LEX-04`.

## 44. A negative robustness result correctly downgrades the main claim

Source: user-confirmed Yangtze modeling paper.

Useful behavior: a short window showed a sign crossing near `3.2186`; after the
window and initial conditions were varied, only 5 of 75 runs retained it. The
revision withdrew the unique universal threshold and retained only a weaker
directional statement about increased complexity.

Why preserve it: de-AI revision should not merely make prose less repetitive.
It should allow contrary evidence to alter the central argument.

Required propagation:

1. Methods: define the robustness dimensions and denominator.
2. Results: report `5/75`, not only successful examples.
3. Abstract: remove universal-threshold language.
4. Discussion: explain which inference survives and which fails.
5. Conclusion/recommendation: remove decisions that depend on the rejected
   threshold.

A disclaimer appended to one subsection is insufficient if the old claim
remains in the title, abstract, figure caption, or conclusion.

Rules: `EVD-04`, `DOC-07`, positive case.

## 45. An underdetermined problem is honestly left non-unique

Source: `D:\code LateX\elegantbook\word\past-exams\reviewed\2015-B-draft.tex`.

Useful behavior: the available path-independence condition determines only one
constant. The solution retains a family containing `C_1` and states that a
second independent condition is required instead of inventing one to make the
answer look complete.

Transfer rule:

- count independent constraints and unknown degrees of freedom;
- output the admissible parameter family;
- identify the missing observation/boundary condition;
- do not select a convenient value for narrative closure;
- do not label the problem erroneous unless the expected uniqueness is part of
  an authoritative statement.

Acceptable wording:

> The stated condition fixes `C_2` but leaves `C_1` free. Hence the solution is
> a one-parameter family. A unique answer requires one additional independent
> boundary value.

Rules: `EVD-01`, `MTH-10`, positive case.

## 46. A quotient/log transformation silently deletes zeros

Source: manually reviewed long calculus proof family, including
`D:\code LateX\简单导数\chapters\chap3.tex`.

Observed risk: a differential identity is divided by the unknown function and
integrated as `log|y|`. The transformed argument is then applied on the entire
original interval without treating zeros. The temporary equation is valid only
on connected components where `y` is nonzero; different components may carry
different constants, and zero solutions may have been lost.

Audit procedure:

1. Identify the zero set of every divisor and log argument.
2. Split the domain before dividing or taking logarithms.
3. Solve on each connected nonzero component.
4. Check zero/constant solutions directly in the original equation.
5. Determine whether component constants can be matched across a zero.
6. State the domain of the transformed equation separately from the domain of
   the original problem.

Acceptable wording:

> On each component of `{x:y(x) != 0}`, division by `y` gives
> `log|y|=G(x)+C_j`. The zero solution and any crossing through zero must be
> checked in the original equation; the transformed formula alone does not
> cover them.

Rules: `MTH-15`, `MTH-10`, hard failure when omitted cases affect the claim.

## 47. Branch and orientation data compressed into “up to a constant”

Source: manually reviewed line/surface-integral and differential-equation audit
family under `D:\code LateX\elegantbook\elegantbook2\solution_quality_audit`.

Observed risk: an antiderivative, square root, inverse trigonometric expression,
or oriented integral is simplified without its interval, sign, or orientation.
The prose then says two forms differ only by a constant, even though the
constant changes across branches or an orientation reversal changes the sign.

Audit procedure:

- state the connected interval/branch for every inverse or antiderivative;
- retain absolute values until the sign is established;
- record path/surface orientation and the induced normal/boundary orientation;
- verify any claimed constant difference by differentiating and checking one
  base point on each component;
- state endpoint and branch-cut exclusions.

Acceptable wording:

> On the selected branch `theta in (...)`, the two antiderivatives differ by
> `C_1`. A second branch requires an independent constant. Reversing the curve
> orientation changes the second-kind integral's sign, so the two orientations
> are not interchangeable.

Rules: `MTH-16`, `MTH-15`.

## 48. Sign-sensitive operations leave contradictory inequality directions

Source: `D:\code LateX\简单导数\chapters\chap6.tex:75,78` and related
manually reviewed proofs.

Observed failure: assumptions include `p,q>=0` and `pq<=0`, which nearly force
a boundary/trivial case, while subsequent inequalities are narrated as though
both parameters were freely positive. Elsewhere the same target appears with
both `>=` and `<=` after sign-sensitive transformations.

A direct counterexample from the forward audit exposes the printed direction:
with `x=1`, `y=9`, `p=2`, `q=0`, and equal outer weights,

```text
(M_2+M_0)/2 = (sqrt(41)+3)/2 approximately 4.701 < 5 = M_1.
```

The example satisfies the printed sign conditions, so prose repair is not
available until the proposition itself is corrected.

Audit procedure:

1. Simplify the feasible set implied by the assumptions before proving
   anything.
2. Record the sign of each multiplier/divisor.
3. State whether logarithm, square, reciprocal, or substitution is monotone and
   injective on the current domain.
4. Split cases if the sign is not fixed.
5. Substitute boundary cases into both the original and transformed claims.

Acceptable repair: either state the reduced boundary proposition explicitly or
correct the assumption/sign and rebuild the proof. Do not preserve a richer
looking argument for a feasible set that has collapsed.

Rules: `MTH-17`, `EVD-07`, hard failure.

## 49. “Exponential eventually wins” used to prove every integer case

Source: `D:\code LateX\简单导数\chapters\chap6.tex:152`.

Observed failure: the proof invokes the eventual dominance of an exponential
over a polynomial but claims an inequality from a particular small integer.
Asymptotics supplies neither the finite threshold nor the initial cases.

Required repair:

```text
find a concrete N
-> prove the claim for every stated n below N
-> show a ratio/difference/induction or monotonicity mechanism for n>=N
-> verify the mechanism starts at N
```

For the actual displayed comparison, one valid proof shape is:

```text
a_n = 3^(2n+1)-3
b_n = 4(2n-1)(2n)(2n+1)

check a_3 > b_3;
for n>=3, prove a_(n+1)/a_n > 9 and
b_(n+1)/b_n = ((2n+2)(2n+3))/((2n-1)(2n)) < 9;
conclude by induction that a_n > b_n for every n>=3.
```

Acceptable wording:

> Direct computation verifies `n_0<=n<N`. For `n>=N`, the ratio of successive
> sides is bounded by ..., so once the inequality holds at `N` it persists.

Rules: `MTH-18`, `MTH-09`, hard failure.

## 50. A “dual-variable/virtual-circle” story lacks standard equivalence

Source: `D:\code LateX\简单导数\chapters\chap11.tex:243,245,249`.

Observed failure: a virtual-circle or dual-variable system is introduced with
a differential constraint and then explained as equality of relative change
rates. The story does not supply a standard object, parameter domain, constants,
or a two-way derivation; the interpretation can therefore hide a false
equivalence.

Audit procedure:

1. Write the original standard equations without the coined term.
2. Type every variable and parameter and state its domain.
3. Derive the proposed relation directly by differentiation/algebra.
4. Prove the reverse reconstruction, including integration constants and
   exceptional values.
5. Test a boundary case and a nontrivial numerical/symbolic example.
6. Keep the coined term only if it abbreviates a verified standard structure.

Acceptable repair:

> Equations (x)-(y) define [standard object] on domain D. Under condition C,
> differentiating (x) gives (z). Conversely, integrating (z) recovers (x) only
> after fixing constant K; the zero branch is treated separately. The phrase
> `virtual circle` is mnemonic and carries no additional theorem.

Rules: `MTH-19`, `LEX-08`, `MTH-15`, hard failure if equivalence is used.

## 51. A chapter family exists but is not yet a book-level composition

Source: manually reviewed `D:\code LateX\简单导数\main.tex`,
`D:\code LateX\圆锥曲线\main.tex`, and their chapter directories.

Observed risk: assistant output can create a polished standalone chapter while
the authority main file, prerequisite order, definitions, numbering, and answer
links still describe the earlier book. Counting the file as “finished” confuses
local prose completion with document integration.

Integration audit:

| Layer | Required check |
|---|---|
| Entry point | intended chapter included exactly once in the authority main |
| Prerequisites | every symbol/theorem introduced before use |
| Definition ownership | duplicate definitions reconciled to one authority |
| Difficulty | intended reader can follow the step from prior chapter |
| References | section/equation/exercise/answer links resolve |
| Provenance | inherited problem and generated solution labeled separately |
| Version | superseded chapter family removed or marked historical |

Acceptable release statement:

> Chapter 7 is complete as a standalone draft and compiles in isolation. It is
> not yet integrated into the authority book because prerequisites P and Q and
> the answer cross-references remain unresolved.

Rules: `DOC-10`, `DOC-09`, `EVD-11`.
