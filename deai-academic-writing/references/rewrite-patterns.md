# Rewrite Pattern Library

Use these patterns after facts and evidence pass validation. Each pattern gives a trigger, diagnosis, operation, example, and guardrail. Do not apply a pattern mechanically; confirm the sentence's function in its paragraph.

## Contents

1. Remove drafting residue
2. Repair false binary contrast
3. Break mechanical enumeration
4. Replace abstract management nouns
5. Evidence-gate evaluation words
6. Split overloaded sentences
7. Replace connector chains with object continuity
8. Consolidate repeated boundaries
9. Rebuild an overfull paragraph
10. Break symmetric subsection templates
11. Derive a method from a concrete gap
12. Separate calibration and validation
13. Separate simulation and reality
14. Name proxies honestly
15. Use negative results as evidence
16. Reconcile version residue
17. Separate source text and generated prose
18. Remove pseudo-technical terminology
19. Remove theatrical teaching language
20. Compress algebra without hiding the decisive step
21. Expand a black-box simplification
22. Repair mathematical object/type drift
23. Replace option-guessing with proof
24. Rewrite abstracts and conclusions
25. Attach citations to propositions
26. Calibrate strategy strength
27. Convert audit voice to research voice
28. Repair a generic English shell
29. Create information exit
30. Restore argumentative rhythm
31. Convert workflow completion into a scoped status
32. Repair local-to-global proof coverage
33. Restore reversibility after elimination
34. Validate envelope and tangency language
35. Split at zeros and preserve branches
36. Repair sign-sensitive inequalities and asymptotic bases
37. Calibrate numerical precision
38. Downgrade ranking stability correctly
39. Translate nonstandard mathematics
40. Reintegrate an appended chapter family

## 1. Remove drafting residue

**Trigger:** `后文将、后文若、正文里要、这一问更适合、表格的作用、这样写、放到图上、参数扫描的写法`.

**Diagnosis:** The sentence speaks to the writer/editor instead of the reader of the final paper.

**Operation:** Identify whether the sentence intends to report a method, result, interpretation, or limitation. Write that content directly. Delete purely editorial instructions.

**Before:**

> 表格的作用也在于让读者一眼看出不同情景的差异。

**After:**

> 表 4 显示，高阻隔情景下顶级捕食者指标的降幅最大。

**Guardrail:** Do not invent a result merely to replace the instruction; read the table first.

Rules: `SYN-01`, `MTH-04`.

## 2. Repair false binary contrast

**Trigger:** repeated `不是 A，而是 B` or `关键不在 A，而在 B`.

**Diagnosis:** The form implies exclusion even when A and B coexist or have unequal evidence.

**Operations:**

- If A is false and B correct, retain one contrast.
- If A is secondary, write `不宜仅归因于 A；B 也...`.
- If B is the main point, delete A and state B.
- If the sentence is a repeated section stem, remove the template and rebuild around section-specific evidence.

**Before:**

> 本问的优点不在于给出一个数值，而在于建立完整闭环。

**After:**

> 问题一只用 `gain_scale` 拟合总量锚点；CPUE* 和 `H_0` 分别用于拟合外一致性检查和反事实比较。

**Guardrail:** A useful conceptual distinction should not be deleted merely because the form is common.

Rules: `SYN-02`, `SYN-05`.

## 3. Break mechanical enumeration

**Trigger:** `首先、其次、再次、最后`; forced three-part lists; unrelated paragraphs share identical number of clauses.

**Diagnosis:** The outline determines the reasoning instead of the material.

**Operation:** Classify list items as ordered steps, exhaustive categories, independent findings, or mixed content. Keep numbering only for the first two. Reorder by evidence importance and convert secondary items to prose or a table.

**Before:**

> 首先建立模型，其次完成校准，再次进行模拟，最后提出建议。

**After:**

> 模型用 1.8 倍总量锚点校准 `gain_scale`。在该参数下，五种情景的长期轨道出现两类稳定排序；建议只基于这一条件性结果。

**Guardrail:** Reproducible procedures still need explicit ordered steps.

Rule: `SYN-03`.

## 4. Replace abstract management nouns

**Trigger:** `主线、口径、闭环、收口、落地、门禁、抓手、台账、路线图` in publishable prose.

**Diagnosis:** Internal workflow language replaces the scientific object or operation.

**Mapping:**

| Abstract control word | Ask | Possible replacement |
|---|---|---|
| 口径 | Which definition/scope? | sample range, metric definition |
| 闭环 | Which operations? | calibration, test, reproduction |
| 主线 | Which question/claim? | research question, central hypothesis |
| 门禁 | Which criterion? | acceptance threshold, stopping rule |
| 收口 | What completion? | validated result, archived artifact |
| 落地 | Which implementation? | code path, experiment, deployment |

**Before:**

> 本文形成了从数据到结论的完整闭环。

**After:**

> 原始记录经过去重和独立预算实验后生成主表；脚本、配置和汇总表保存在同一实验目录中。

**Guardrail:** In an internal plan, these words may remain when they name a real governance state.

Rule: `LEX-02`.

## 5. Evidence-gate evaluation words

**Trigger:** `显著、有效、准确、完整、稳健、全面、深入、合理、清晰`.

**Diagnosis:** The author evaluates the work before presenting a criterion.

**Operation:** For each word, demand a comparison, threshold, test, error, or scope. Replace with the evidence or weaken the claim.

**Before:**

> 模型准确验证了局地 CPUE 的恢复趋势。

**After:**

> 模型预测的恢复倍数为 1.838，低于局地观测的 2.2，误差为 16.47%；两者方向一致，但该比较不是独立外部验证。

**Guardrail:** Do not retain “accurate” merely because the error looks small; define an acceptance criterion.

Rules: `LEX-01`, `EVD-01`, `EVD-02`.

## 6. Split overloaded sentences

**Trigger:** one sentence includes background, method, result, interpretation, limitation, and significance; three or more semicolons; nested parentheticals.

**Diagnosis:** All information receives summary-level emphasis.

**Operation:** Identify the central claim. Give the evidence its own sentence. Attach only the condition governing that evidence. Move implications and limitations to later sentences if needed.

**Before:**

> 本文首先构建多层模型，并在多种情景下进行全面模拟，从而揭示了复杂机制，同时考虑到数据有限，结果仍需后续验证。

**After:**

> 模型包含底层资源、中层鱼群和顶级捕食者三个状态变量。五种阻隔情景产生两类长期轨道。由于参数只由一个总量锚点校准，这一排序仍需独立观测验证。

**Guardrail:** Keep tightly coupled mathematical conditions in the same sentence.

Rule: `SYN-04`.

## 7. Replace connector chains with object continuity

**Trigger:** consecutive `因此、同时、进一步、另一方面、换言之`.

**Diagnosis:** The connector announces continuation but does not identify what continues.

**Operation:** Make the preceding object/result the subject.

**Before:**

> 进一步，我们考虑珍稀物种。另一方面，还需要分析复杂食物链。

**After:**

> 问题一得到的 `E(t)` 进入珍稀物种方程，决定其时变承载力。该承载力随后作为复合食物链情景的输入。

**Guardrail:** Retain connectors when the logical relation itself is important and unambiguous.

Rules: `LOG-02`, `LOG-04`.

## 8. Consolidate repeated boundaries

**Trigger:** the same limitation appears in analysis, results, advantages, limitations, and conclusion.

**Diagnosis:** Repetition simulates rigor and blocks information exit.

**Operation:** Choose the first evidence-bearing location for full detail. Keep one synthesis in the conclusion. Replace all other repetitions with deletion or a short reference.

**Consolidated example:**

> 3.20-3.22 的符号跨越只在基准初值和 90 时长窗口中稳定出现；积分延长至 150 或 200 后不再保留。因此本文不把该区间解释为普适阈值。

**Guardrail:** Do not remove a scope condition from a standalone table/figure caption if it is needed to prevent misreading.

Rules: `EVD-03`, `PAR-03`, `LOG-05`.

## 9. Rebuild an overfull paragraph

**Trigger:** paragraph performs four or more functions; similar length to every other paragraph; evidence appears at the end.

**Operation:** Label sentences by function. Keep one dominant function per paragraph. Move evidence beside the claim. Let a short transition remain short.

**Rebuild:**

```text
Paragraph A: define the parameter and why it is needed.
Paragraph B: report the calibration result and error.
Paragraph C: interpret the result and state one evidence-bound limitation.
```

**Guardrail:** Do not split a mathematical proof at a point where assumptions and conclusion must be read together.

Rules: `PAR-01`, `PAR-02`, `PAR-04`.

## 10. Break symmetric subsection templates

**Trigger:** every subsection has identical `背景-方法-优点-局限-小结`, regardless of evidence.

**Diagnosis:** Formal equality hides evidentiary inequality.

**Operation:** Build a responsibility map. Merge repeated limitations into one section. Give each subsection only the structure needed by its unique evidence.

**Example:** Replace five `优点/局限` pairs with one uncertainty section organized by calibration, identifiability, scenario confounding, and external validity.

Rules: `SYN-08`, `DOC-01`, `PAR-04`.

## 11. Derive a method from a concrete gap

**Trigger:** `为解决上述问题，本文提出...`.

**Operation:** State existing capability, missing decision/measurement, and consequence. Then introduce the method as the operation that supplies the missing capability.

**Before:**

> 为解决上述问题，本文提出 SCCD。

**After:**

> 现有分组方法能够识别变量交互，却不能判断一次细分在结构上是否安全、在数值上是否值得。SCCD 因此把选择性细分写成受结构条件约束的决策。

**Guardrail:** Verify that the actual algorithm implements the claimed decision.

Rule: `LOG-01`.

## 12. Separate calibration and validation

**Trigger:** fitted target later called validation; direction-only match called consistency without criterion.

**Operation:** Label each evidence item as fit anchor, internal check, out-of-fit check, held-out validation, external validation, or sensitivity. State the criterion and result.

**After:**

> `gain_scale` 由总量锚点拟合。CPUE* 未进入目标函数，因此只提供拟合外方向检查；其 16.47% 误差未达到预先定义的外部验证标准，因为本研究没有独立验证集。

Rules: `EVD-02`, `EVD-01`.

## 13. Separate simulation and reality

**Trigger:** model output stated as real causal mechanism.

**Operation:** Start with `在该参数设定下，模型...`; state interpretation as compatible mechanism; name external data required.

**Before:**

> 消费者增长导致底层资源下降。

**After:**

> 在当前参数设定下，中层鱼群增加与底层资源下降同时出现。该模式与消费者压力解释相容，但仍需河段观测区分它与承载力变化等替代机制。

Rules: `MTH-03`, `LOG-03`, `EVD-06`.

## 14. Name proxies honestly

**Trigger:** internal score, official benchmark accuracy, local indicator, or model output described as ground truth.

**Operation:** Name what the proxy calculates, why it is used, and what it cannot replace.

**After:**

> 综合健康指数由三类标准化状态量加权得到，只用于当前情景之间的内部比较；它不替代外部生态健康评价。

Rules: `EVD-05`, `LEX-04`.

## 15. Use negative results as evidence

**Trigger:** failed robustness hidden in limitations or overridden by positive title.

**Operation:** Move the negative result beside the claim and use it to reclassify the claim.

**Before:** `存在稳定混沌阈值。`

**After:**

> 75 组压力测试中只有 5 组保留符号跨越，且更长积分窗口不再保留。因此 3.20-3.22 只能称为基准设定下的有限时间候选区间。

Rules: `EVD-04`, `EVD-05`, `SYN-07`.

## 16. Reconcile version residue

**Trigger:** `最终统一版` coexists with contradictory old actions, stale IDs, or old appendix totals.

**Operation:** Build a claim ledger:

```text
old claim | new claim | keep/delete/replace | authority | all locations
```

Delete stale text, update cross-references, and recompute totals. Do not add another disclaimer.

Rules: `DOC-06`, `DOC-07`.

## 17. Separate source text and generated prose

**Trigger:** assistant-created file contains OCR, examination question, quotation, or lexical database.

**Operation:** Mark source segments; preserve them; analyze/rewrite only generated explanation unless instructed. Label reconstructed answers as reconstructed, not official.

**Guardrail:** File provenance is not sentence provenance.

Rules: `EVD-08`, `DOC-09`.

## 18. Remove pseudo-technical terminology

**Trigger:** mathematical term used for prestige but property not verified.

**Operation:** Test the definition. If valid, define it and use consistently. If invalid, replace with a literal description.

**Before:** `T(M,N)=E(M,N)-1 是对称双线性式。`

**After option A:** Define a genuinely homogeneous polarized form and prove bilinearity.  
**After option B:** Call `T` an affine two-point expression and state the restricted affine-combination property.

Rules: `LEX-08`, `MTH-06`, `MTH-19`.

## 19. Remove theatrical teaching language

**Trigger:** `宇宙级纯净、奇迹般、闭着眼、魔法、爆出、铁证如山、灰飞烟灭、锁死、吐出`.

**Operation:** Replace with the exact observation, operation, or failure.

**Before:** `这个代换会奇迹般地把三次项灰飞烟灭。`

**After:** `代入后，三次项的系数相消，只剩二次项；相消条件为...`

Rule: `LEX-08`.

## 20. Compress algebra without hiding the decisive step

**Trigger:** every reversible step narrated; key idea has no visual emphasis.

**Operation:** State objective, show one representative transformation, compress routine continuation, display the decisive factorization/sign.

**Pattern:**

```text
为消去 y，将第二式代入第一式。
整理同类项后，决定符号的因子为 (...).
其余因子在给定域内为正，因此...
```

**Guardrail:** Never compress branch selection, exceptional values, domain restrictions, or theorem assumptions.

Rules: `RHY-04`, `RHY-05`, `PAR-04`.

## 21. Expand a black-box simplification

**Trigger:** `经过化简可得` hides a large elimination, envelope argument, or factorization.

**Operation:** Show the invariant intermediate expression and decisive factor. If too long, provide a numbered appendix or symbolic verification script and cite it.

**Guardrail:** A CAS output without assumptions and factor interpretation is not enough.

Rules: `MTH-02`, `MTH-08`.

## 22. Repair mathematical object/type drift

**Trigger:** point becomes vector; function becomes derivative; affine expression used as bilinear; local expansion used globally.

**Operation:** Write the type beside each object. Verify operations are defined. Split overloaded notation and restate the domain.

**Example:** rename `S(t)` for two species; distinguish `T(P,X)` for points from a homogeneous form applied to vectors.

Rules: `MTH-01`, `MTH-05`, `MTH-06`, `MTH-10`, `MTH-14`.

## 23. Replace option-guessing with proof

**Trigger:** `选项有马脚`, numerical intuition, or approximation used as the formal solution.

**Operation:** Give the exact identity first. Put heuristic intuition in a labeled note.

**Example for binomial third moment:** use factorial moments to derive the exact value; only then mention normal approximation as intuition with error conditions.

Rules: `MTH-05`, `EVD-01`.

## 24. Rewrite abstracts and conclusions

### Abstract

Keep one research question, identifying method, central evidence-bearing result, and material boundary. Remove the table of contents and unsupported value claims.

### Conclusion

Organize:

```text
robust findings
conditional findings
unresolved questions
implications supported by those findings
```

Do not repeat all sections or introduce new evidence.

Rules: `DOC-03`, `DOC-04`.

## 25. Attach citations to propositions

**Trigger:** citation cluster at paragraph end after multiple factual/causal claims.

**Operation:** Split propositions and attach each source to the supported one. Mark your inference separately.

**Before:**

> 禁渔显著修复了底层资源并促进了顶级物种恢复[1-4]。

**After:**

> 监测资料显示，禁渔后局地鱼类 CPUE 上升[1]。本模型进一步预测顶级物种指标改善，但底层资源的变化缺少独立观测，因此不据此声称现实中的底层资源已修复。

Rules: `EVD-06`, `LOG-03`.

## 26. Calibrate strategy strength

**Trigger:** heuristic presented as rule or command.

**Operation:** State denominator, effect, subset, strength, counterexample, and exit rule.

**Before:** `短选项更可能正确。`

**After:**

> 短项只提供弱提示；该趋势在 Section C 子样本中更稳定，但仍需检查选项是否完整回应题问。找不到关系证据时，不以长度单独作答。

Rules: `EVD-01`, `EVD-05`.

## 27. Convert audit voice to research voice

**Trigger:** `本轮、整改、复核、清零、放行、残留、落点` in a paper.

**Operation:** Convert status to evidence/result; move remediation process to methods or appendix.

**Before:** `本轮已完成异常项清零并具备放行条件。`

**After:** `复核发现的 12 处符号错误已更正；独立计算与更新后的表 3 一致。`

Rule: `VOI-01`.

## 28. Repair a generic English shell

**Trigger:** `This practice/shift/trend/phenomenon` plus universal significance and `individual + institution` ending.

**Operation:** Name the concrete actor/change, give one evidence-bearing consequence, and derive only the recommendation supported by that evidence.

**Before:** `This shift represents a profound awakening and requires joint efforts from individuals and institutions.`

**After:** `The survey records a rise in daily AI-assisted writing among first-year students. Universities can respond by requiring source disclosure in assessed work; the data do not show whether general restrictions improve learning.`

Rules: `LEX-01`, `SYN-03`, `EVD-01`.

## 29. Create information exit

**Trigger:** the same claim has five paraphrases.

**Operation:** Choose authority location, keep one full statement, turn later occurrences into either new evidence, a short cross-reference, or deletion.

**Checklist:**

- Does this repetition add a new number, condition, mechanism, or consequence?
- If not, delete it.
- If the passage is a standalone summary, compress to one clause and point to the main result.

Rules: `LOG-05`, `PAR-03`, `DOC-07`.

## 30. Restore argumentative rhythm

**Trigger:** every paragraph has equal length, every sentence is a summary, every section ends with `因此`.

**Operation:** Mark central evidence, supporting calculation, transition, and boundary. Expand the first; compress the second and third; state the boundary once. Use short sentences for the finding and longer sentences for inseparable conditions.

**Guardrail:** Do not vary sentence length randomly or inject colloquialisms. Rhythm follows evidence weight.

Rules: `RHY-01`, `RHY-02`, `RHY-03`.

## 31. Convert workflow completion into a scoped status

**Trigger:** `已清零、已覆盖、已闭环、已放行、验证完成、答案正确`
appears after compilation, transcription, a keyword scan, or an automated
check.

**Diagnosis:** The sentence jumps from a workflow property to content
correctness. The verb has no named test object.

**Operation:** Write four fields explicitly:

```text
artifact/property checked -> method -> result -> property not checked
```

**Before:** `八页内容已全部录入并通过编译，答案验证完成。`

**After:**

> Eight pages were transcribed and the TeX build completed without syntax
> errors. Source-image comparison is complete for six pages; the remaining two
> formula pages and all mathematical solutions have not been independently
> checked.

**Guardrail:** Do not weaken all statuses into vague uncertainty. Preserve the
specific property that really passed. A lexical zero remains a useful literal
regression result, but it cannot be the acceptance gate for prose or proofs.

Rules: `EVD-11`, `LEX-09`.

## 32. Repair local-to-global proof coverage

**Trigger:** `由 Taylor 展开可知对所有...`, `数值检验表明恒正`, or one
asymptotic term is used for an entire interval.

**Diagnosis:** Evidence has a local or tail domain, while the conclusion has a
universal quantifier.

**Operation:** Replace the single bridge sentence with a domain coverage plan:

```text
near the expansion point -> signed remainder
compact middle interval -> monotonicity/Sturm/Bernstein/interval certificate
tail -> explicit dominant-term inequality and threshold
endpoints -> direct check or limit
```

**Before:** `展开前三项均为正，因此 H(t)>0 (t>0)。`

**After:**

> The expansion with remainder proves positivity only for `0<t<=delta`.
> On `[delta,T]`, equation (x) shows that `H'` has no zero and `H(delta)>0`.
> For `t>=T`, bound (y) makes the leading positive term exceed the sum of the
> negative terms. These intervals cover the stated domain.

**Guardrail:** If no middle-interval certificate exists, keep only the local
claim. Do not replace the missing proof with `显然`, denser algebra, or more
sample points.

Rules: `MTH-11`, `MTH-09`.

## 33. Restore reversibility after elimination

**Trigger:** `消元可得`, a resultant, squaring/cubing, division, or factor
cancellation is followed by `轨迹就是/等价于`.

**Diagnosis:** The derivation may establish only necessity. Algebraic closure,
discarded factors, forbidden denominators, and introduced roots are hidden.

**Operation:** Write a transformation ledger before revising the conclusion:

```text
original conditions
-> operation and implication direction
-> discarded factor/domain
-> candidate branches
-> parameter recovery
-> back-substitution
-> exact locus or restricted candidate statement
```

**Restricted rewrite when only one direction is proved:**

> Every admissible solution of the original system satisfies `G=0`; hence the
> locus is contained in this candidate algebraic curve. Equality remains open
> until each regular branch admits an original parameter and passes
> back-substitution.

**Full rewrite when both directions pass:** State the excluded singular points,
parameter range, and why each retained branch is recovered.

**Guardrail:** A CAS factorization is evidence only after assumptions, factors,
and parameter domains are interpreted. Do not silently delete factors called
`irrelevant`.

Rules: `MTH-12`, `MTH-08`.

## 34. Validate envelope and tangency language

**Trigger:** a few special positions, a discriminant, or `F=F_s=0` is used to
state that a line/curve family has an exact envelope or persistent tangency.

**Diagnosis:** Algebraic compatibility is weaker than a real regular envelope.

**Operation:** Check and state:

1. smooth parameter dependence and parameter domain;
2. existence of a real common point for the original family;
3. repeated-root or parameter-derivative condition;
4. nonzero gradients and gradient collinearity at regular points;
5. recovery of the corresponding parameter for each claimed envelope point;
6. singular, degenerate, endpoint, and extra algebraic branches.

**Before:** `消去参数后得到 G=0，因此包络为 G。`

**After:**

> Elimination gives the candidate `G=0`. For every regular point on branch
> `G_1`, equation (x) recovers a unique admissible parameter, and substitution
> yields `F=F_s=0`; moreover `nabla F` and `nabla G_1` are nonzero and parallel.
> Branch `G_2` has no real admissible parameter and is excluded. The degenerate
> endpoint is treated separately.

**Guardrail:** If any item is unproved, use `candidate curve` or `contained in`
instead of `the envelope is`.

Rules: `MTH-13`, `MTH-12`, `MTH-07`.

## 35. Split at zeros and preserve branches

**Trigger:** `f''/f`, `log f`, reciprocals, square roots, inverse trigonometric
functions, indefinite integrals, line/surface integrals, or normalized vectors.

**Diagnosis:** The temporary expression may have a narrower domain than the
original problem; absolute values and constants may change across components.

**Operation:**

- locate all zeros and branch points;
- split the domain into connected components;
- record sign, branch, and orientation on each component;
- derive the formula separately;
- compare limits or matching conditions at excluded points;
- state whether constants are component-specific.

**Before:** `积分得 ln|f(x)|=g(x)+C，对整个区间成立。`

**After:**

> On each connected component of `{x:f(x) != 0}`, integration gives
> `ln|f(x)|=g(x)+C_j`. The original equation must be checked separately at the
> zeros of `f`; the constants need not agree across components.

**Guardrail:** `|f|` permits logarithms for nonzero negative values; it does not
define the logarithm at `f=0`.

Rules: `MTH-15`, `MTH-16`, `MTH-10`.

## 36. Repair sign-sensitive inequalities and asymptotic bases

**Trigger:** a proof multiplies/divides by a variable-sign quantity, takes a
log or square, or says `指数增长快于多项式` to prove a claim from a specific
integer.

**Diagnosis:** Direction, equivalence, equality cases, or finite initial values
are missing.

**Operation:**

1. Partition by sign before multiplication/division.
2. State monotonicity and domain before applying a nonlinear transformation.
3. Check whether assumptions make the case empty or force a boundary value.
4. For integer tails, prove a threshold and a preservation mechanism (ratio,
   difference, induction, or monotonicity).
5. Verify every integer below the threshold but inside the claimed range.

**After pattern:**

> Direct calculation proves the claim for `n_0<=n<N`. For `n>=N`, the ratio of
> the left side to the right side decreases and is below one at `N`; hence the
> inequality persists. The sign of the divisor is positive by assumption (x),
> so the inequality direction is unchanged.

**Guardrail:** `eventually` cannot establish a named base case, and squaring may
add solutions unless signs are known.

Rules: `MTH-17`, `MTH-18`.

## 37. Calibrate numerical precision

**Trigger:** empirical or calibrated prose reports more digits than the input,
anchor, sample, or identification design can support.

**Diagnosis:** Reproducibility precision is being read as inferential precision.

**Operation:** Label the value, trace its weakest upstream evidence, select a
display precision, and separate the reproducibility table from the narrative.

**Before:** `模型精确预测增长倍数为 1.838。`

**After:**

> Under the normalized parameter set, the simulated increase is approximately
> `1.84x`. The run table retains `1.838` so the calculation can be reproduced;
> the extra digit does not represent observational precision.

**Guardrail:** Do not round away a meaningful sign change or threshold crossing.
When rounding affects interpretation, report an interval and sensitivity.

Rules: `EVD-12`, `MTH-03`.

## 38. Downgrade ranking stability correctly

**Trigger:** equal, entropy, CRITIC, AHP, or perturbed weights produce the same
ordering and the prose says `模型得到验证/指标体系稳健/机制可靠`.

**Diagnosis:** Only one aggregation component varied. The indicator matrix,
scenario sample, model outputs, and external truth remained fixed.

**Operation:** Name the conditional object and list untested dimensions.

**Before:** `多种赋权方法结论一致，验证了模型的生态有效性。`

**After:**

> For the fixed four-indicator matrix and three scenarios, the ordering is
> unchanged under the tested weighting methods and local weight perturbations.
> This does not test indicator selection, model structure, causal mechanism, or
> external ecological validity.

**Guardrail:** Do not call the result meaningless. It is valid evidence about
aggregation-weight sensitivity, provided the admissible perturbation range is
defined.

Rules: `EVD-13`, `EVD-02`, `LEX-04`.

## 39. Translate nonstandard mathematics

**Trigger:** an in-house label such as `dual-variable system`, `virtual circle`,
`operator`, `probe`, or `invariant` carries a proof without a standard
definition.

**Diagnosis:** Narrative terminology is hiding the actual equations, parameter
domain, or a one-way analogy.

**Operation:**

```text
invented term -> standard object/type -> defining equations
-> constants and parameter domain -> forward map -> inverse map
-> exceptional cases -> property actually used
```

**Acceptable rewrite:** Introduce the standard object first. Keep the coined
term only as an optional mnemonic after exact equivalence has been proved.

**Guardrail:** Similar-looking diagrams or matching derivatives do not establish
equivalence. Verify the map in both directions and remove the label if it adds
no operation beyond the standard formulation.

Rules: `MTH-19`, `LEX-08`.

## 40. Reintegrate an appended chapter family

**Trigger:** a new chapter/exercise/appendix compiles alone, but the authority
book, prerequisite order, definitions, numbering, or answers still describe an
older composition.

**Diagnosis:** Local file completion has been mistaken for book-level
integration.

**Operation:**

1. Designate the authority entry point and include the family exactly once.
2. Build a prerequisite map from every first-used symbol/theorem to its defining
   section; move or cross-reference definitions as needed.
3. Select one authoritative definition for repeated objects and replace local
   redefinitions with references.
4. Compare intended reader and difficulty with the preceding and following
   chapters; add only the bridge actually required.
5. Regenerate section, theorem, equation, exercise, and answer references.
6. Label inherited problem statements, official answers, reconstructed answers,
   generated solutions, OCR, and editorial notes by segment.
7. Remove or archive superseded chapter families and search the whole book for
   conflicting old statements.
8. Compile the authority book, then independently run mathematical and answer
   checks; compilation is only one gate.

**Delivery statement:**

```text
standalone status:
authority inclusion:
prerequisites/definitions:
references/answers:
source identities:
mathematical check:
remaining integration blockers:
```

**Guardrail:** Do not duplicate definitions or add a generic overview merely to
smooth a difficulty jump. Repair the exact dependency.

Rules: `DOC-10`, `DOC-09`, `DOC-07`, `EVD-11`.
