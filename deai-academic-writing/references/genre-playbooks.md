# Genre Playbooks

Select the playbook matching the document. Do not apply one genre's desirable voice to another. Each playbook defines the document contract, evidence order, common corpus-derived failures, and completion gate.

For a mixed-genre file, build a segment map and apply multiple playbooks. Select one current authority segment; mark historical, plan, audit, and tutorial segments explicitly. Never average their voices or status claims.

## Contents

1. Mathematical modeling paper
2. Algorithm/method paper
3. Experimental results and robustness report
4. Literature review and paper-to-project note
5. Textbook chapter
6. Examination solution and strategy manual
7. Audit/quality/closure report
8. Engineering README and operation manual
9. OCR/transcription reconstruction
10. Research plan and manuscript blueprint
11. Product or competition presentation

## 1. Mathematical modeling paper

### Contract

Explain a real problem through explicit assumptions, variables, equations, calibration/estimation, results, sensitivity, limitations, and implications. Keep simulated behavior separate from observed reality.

### Required map

```text
real question
-> retained mechanisms and omitted mechanisms
-> state variables/parameters/units
-> equations and assumptions
-> calibration data and objective
-> non-calibration checks
-> scenario definitions
-> robustness dimensions
-> robust/conditional/unresolved conclusions
```

### Keep

- explicit distinction between hard anchors, fitted values, consistency checks, and external validation;
- parameter roles and units;
- negative robustness results;
- scenario-specific rather than universal conclusions;
- model limitations tied to omitted variables and data.

### Remove or repair

- `后文若、正文里要、表格的作用、这样写`;
- one symbol for two objects;
- a composite scenario described as a single-factor effect;
- weight perturbation described as parameter sensitivity;
- local observations called external validation;
- a candidate interval advertised as a universal threshold;
- identical advantage/limitation paragraphs for each subproblem;
- missing final synthesis.

### Evidence order

1. State the observable target.
2. Define what is fitted and what is not.
3. Report calibration error without calling it validation.
4. Present a held-out or external check if available.
5. Report scenario results as model outputs.
6. Test initial conditions, parameters, weights, solver, and time window separately.
7. Classify conclusions by robustness.

### Paragraph model

Prefer:

```text
Under parameterization P, variable X changes from a to b.
This pattern is compatible with mechanism M because...
The comparison does not isolate M from factor Z, so it remains a model interpretation.
```

Avoid opening with “the table helps the reader see” or closing every paragraph with governance advice.

### Gate

- all scenario factors enumerated;
- all symbols unique and typed;
- equations reproducible;
- calibration/validation labels correct;
- abstract no stronger than body;
- conclusion separates robust and conditional findings.

## 2. Algorithm/method paper

### Contract

Demonstrate a concrete decision, measurement, or optimization gap; define the method; justify design choices; compare against appropriate baselines; report cost, failure modes, and scope.

### Required map

```text
existing capability
-> specific unresolved decision/gap
-> formal input/output
-> invariants/assumptions
-> algorithm stages
-> complexity/cost
-> baselines and ablations
-> results
-> hostile/failure cases
```

### Corpus-derived risks

- a draft says the method keeps hostile blocks intact while another stage splits oversized groups;
- the abstract claims adaptive size control not fully present in the algorithm body;
- cache reuse in an experiment protocol conflicts with the paper's claim that grouping is regenerated each run;
- exploratory geometry is written as if its link to performance were already proven;
- old CAG/SCCD definitions coexist and inflate apparent consistency.

### Rules

- Define one authoritative algorithm version.
- Derive the method name only after the precise gap.
- Keep “method itself” separate from benchmark post-processing.
- For each stage, state input, output, decision criterion, and abstention/failure behavior.
- Verify that prose, pseudocode, equations, and implementation describe the same stages.
- An ablation must remove one component while holding others fixed.
- Report computational budget and cache policy.

### Voice

Use researcher voice. Remove internal commands such as `锁定主线、绝对不要回滑、LOCK、APPX、RESERVE` from the paper. They may remain in the project plan.

### Gate

- one method definition;
- pseudocode/body/implementation consistency;
- size, cache, and fallback semantics aligned;
- baselines answer the claimed gap;
- no geometric or statistical term used without its property/assumptions.

## 3. Experimental results and robustness report

### Contract

Connect each claim to a predeclared comparison, metric, data source, and decision criterion. Preserve null and failed results.

### Claim-evidence table

```text
claim | experiment | independent variables | controls | metric
sample/budget | expected decision | opposite-result interpretation | artifact
```

### Keep

- independent budget for main results;
- shared-budget results as a separate boundary analysis;
- stopping rules;
- per-family/per-metric conclusions when behavior differs;
- explicit “proved/not proved” boundaries when attached to evidence.

### Remove or repair

- `显著` without a test;
- `铁律/永远/100%` from small samples;
- negative correlation interpreted as absolute non-adjacency;
- 8-12 observations promoted to commands;
- summary tables whose groups do not add to total N;
- P2/P3/P4 references that drift across versions;
- a long planning matrix copied into results prose.

### Gate

- sample totals reconcile;
- comparison factors are isolated or the confounding is named;
- significance/practical threshold defined;
- every figure/table has a unique claim;
- failed robustness changes the conclusion;
- one authority version and valid project IDs.
- every reported value is labeled observed/calibrated/assumed/simulated/derived,
  and displayed precision matches identification strength (`EVD-12`);
- weight perturbation is reported as ranking sensitivity only, with fixed
  indicators, scenarios, data, and model structure listed (`EVD-13`);
- workflow success, reproducibility success, and scientific validity remain
  separate states (`EVD-11`).

## 4. Literature review and paper-to-project note

### Contract

Represent each source accurately, identify the exact proposition it supports, explain transfer limits, and preserve differences between sources.

### Required fields per paper

- research question;
- mathematical/statistical object;
- assumptions;
- method and data;
- central result;
- one failure/limitation;
- exact proposition useful to the current work;
- non-transferable condition;
- citation location.

### Corpus-derived template risk

Five literature notes reused:

```text
paper summary -> project background -> PDF reading
-> how it supports our probe -> what cannot be copied
```

The structure is useful but common background diluted each paper's unique contribution.

### Rules

- Put shared project background in one series introduction.
- Do not call a citation “important support” without the supported proposition.
- Distinguish source quotation, translation, and your interpretation.
- Do not force all papers into the current project's preferred narrative.
- Compare assumptions and objects, not only conclusions.
- Keep one paper-specific counterexample or limitation.

### Gate

- every source claim traceable;
- no invented citation metadata;
- repeated boilerplate removed;
- each source retains a unique object/assumption/result;
- transfer limits explicit.

## 5. Textbook chapter

### Contract

Teach concepts, methods, examples, and exceptions with correct mathematics and a visible hierarchy between key ideas and routine operations.

### Recommended hierarchy

```text
motivation or question
-> precise definition
-> one decisive property and proof
-> canonical example
-> counterexample or boundary
-> practice set
-> short retrieval summary
```

### Observed strength

The corpus often organizes knowledge as a decision tree using `入口、路线、底座、母式、送回标准模型`. This improves retrieval when the decision is real.

### Observed failures

- chapter overview, section route, example route, solution steps, pitfall, and memorization table repeat the same idea;
- every substitution and variable receives narration;
- key geometry and reversible algebra receive equal space;
- pseudo-technical terms (`同构、泛函、仿射`) are used without definitions;
- theorem conditions are skipped while routine algebra is expanded;
- fluent derivations contain wrong derivatives, exponents, signs, or methods from another topic;
- “after simplification” hides the only decisive step.

### Rules

- Explain a major construction once.
- Show the theorem condition and decisive identity.
- Compress reversible algebra after one model calculation.
- Use one primary example and one counterexample; move variants to exercises.
- Do not make formulas characters in a story through theatrical metaphors.
- Validate every equality independently.
- Label advanced tools and prerequisites for the intended reader.
- A short retrieval summary cannot introduce new claims.

### Gate

- definitions typed and consistent;
- proofs validate assumptions;
- exercises solvable from stated conditions;
- answer key independent checked;
- no method cross-contamination;
- narrative hierarchy visible.
- inherited questions, official answers, reconstructed answers, generated
  solutions, OCR, and editorial notes are labeled by segment (`DOC-09`);
- the authority main includes each intended chapter exactly once; prerequisites,
  definitions, difficulty, labels, and answers are reintegrated (`DOC-10`);
- local expansions cover only their proved domain (`MTH-11`);
- elimination and envelope claims pass reversibility, parameter recovery,
  regularity, and extra-branch checks (`MTH-12`, `MTH-13`);
- object, zero-domain, branch, sign, base-case, and nonstandard-term checks pass
  (`MTH-14`-`MTH-19`).

## 6. Examination solution and strategy manual

### Contract

For a solution, provide a valid route from given conditions to answer. For a strategy manual, separate statistical tendency, heuristic strength, and examination action.

### Solution format

```text
given/target
-> selected theorem or construction and why it applies
-> decisive calculation
-> answer and condition check
```

Do not repeat the question, narrate every algebraic step, or choose a result because “the options show a clue” when a proof is required.

### Strategy format

```text
rule | sample denominator | hit rate/effect | section/subset
strength (strong/weak/none) | counterexample | action | exit rule
```

### Corpus-derived risks

- position rules with only 8-12 cases become commands;
- negative correlation becomes “never adjacent”;
- one result appears in summary, chapter, action card, memorization card, and conclusion;
- `满仓、减仓、收割、死磨` mixes coaching with statistics;
- normal approximation and option clues substitute for an exact binomial moment;
- questions inherited from source papers are counted as generated prose.

### Gate

- exact solution separated from heuristic;
- official answer versus reconstructed answer labeled;
- sample size and uncertainty present;
- no absolute command from small N;
- one authoritative rule location;
- source question excluded from model-style evidence.

## 7. Audit/quality/closure report

### Contract

Record scope, method, evidence, defect, status, remediation, verification, residual risk, and release decision in a traceable form.

### Useful structure

```text
scope and authority
-> acceptance criteria
-> findings by severity
-> exact evidence/location
-> remediation
-> independent verification
-> unresolved risk
-> release decision
```

### Keep

- line/page/question identifiers;
- evidence excerpts;
- fixed status vocabulary;
- separation of automated flags and human judgment;
- explicit residual risk.

### Do not transfer into a paper

`本轮、当前、口径、复核、核对、落点、清零、放行、状态、闭环` are valid audit workflow terms. They become management leakage in academic argument.

### Corpus-derived risks

- each batch repeats the same scope and release language;
- a quality ledger is mistaken for continuous prose;
- “all flags cleared” is mistaken for mathematical correctness;
- validation is performed by the same heuristic that raised the flag;
- old batch findings remain active after repair.

### Gate

- acceptance criteria defined before findings;
- automated and human evidence separated;
- mathematical correctness not inferred from formatting/compilation;
- status changes traceable;
- unresolved risk not hidden by `放行`.
- `transcribed`, `source-compared`, `compiled`, `mathematically-checked`, and
  `externally-validated` are separate columns (`EVD-11`);
- banned-word and linter results are locators/regression checks, never the final
  content gate (`LEX-09`);
- every completion claim names the property, method, evidence, and residual
  unchecked property.

## 8. Engineering README and operation manual

### Contract

Help a new user understand purpose, responsibility boundary, prerequisites, minimal success path, outputs, failure diagnosis, and interpretation limits.

### Structure

```text
what this component is/is not
-> prerequisites
-> minimal command
-> inputs/outputs
-> formal workflow
-> failure attribution
-> interpretation boundary
-> troubleshooting
```

### Strength

The corpus often combines “route + misuse boundary,” preventing a user from blaming an entry script for an optimizer or benchmark failure.

### Risks

- every concept receives an anti-definition;
- quick start expands into architecture review;
- warnings repeat in introduction, workflow, FAQ, and conclusion;
- generic algorithm descriptions contain factual hallucinations or invented expansions;
- star ratings claim convergence/memory/parallel performance without evidence.

### Gate

- minimal path remains minimal;
- responsibilities centralized in one table;
- API names and acronym expansions verified against code/source;
- performance claims linked to benchmark evidence;
- official accuracy not presented as out-of-distribution validity.

## 9. OCR/transcription reconstruction

### Contract

Reproduce source content faithfully, mark unreadable regions, separate reconstruction from interpretation, and maintain page/line provenance.

### Rules

- Do not “improve” source wording while transcribing.
- Mark uncertain text and image/page location.
- Keep OCR output, manual correction, generated explanation, and closure report separate.
- A readable TeX result does not prove source completeness.
- Do not use OCR errors as model-style evidence.
- Compare equations and symbols against the image, not neighboring prose expectations.

### Gate

- page coverage complete or gaps listed;
- uncertain characters marked;
- source and generated additions labeled;
- formulas visually checked;
- closure report states residual risk.

## 10. Research plan and manuscript blueprint

### Contract

Translate research intent into claims, evidence needs, section responsibilities, decisions, and stopping criteria. It is not publishable prose.

### Keep internally

- `LOCK/APPX/RESERVE`;
- claim-evidence matrix;
- prohibited old narrative;
- paragraph responsibilities;
- expected reviewer objections;
- output artifacts and checkpoints.

### Convert before publication

- `主线、锁定、死守、回滑` -> research question, assumptions, or excluded hypothesis;
- `这一段必须...` -> actual argument;
- `图表作用是...` -> result demonstrated by the figure;
- `不要写...` -> remove, do not paraphrase into final prose.

### Version gate

Research plans are highly vulnerable to stale IDs, undefined P4-type items, changed data sources, and old section numbers. Reconcile the plan with the current paper and experiment registry before execution.

## 11. Product or competition presentation

### Contract

Explain problem, user, evidence, solution, implementation, limitations, and next decision. Do not borrow its marketing voice for academic prose.

### Risks

- three pain points map to three features regardless of evidence;
- metrics decorate claims without a source;
- repeated “personal responsibility + institutional support” endings;
- all topics become crisis, opportunity, and future vision;
- feature coverage outruns de-duplication.

### Gate

- each pain point supported by user/data evidence;
- metrics sourced;
- feature list deduplicated;
- limitations and current capability separated from roadmap;
- no academic conclusion inferred from product rhetoric.
