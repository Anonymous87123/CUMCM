# Modeling Writing Rule Library

Severity: `MUST` failures invalidate the affected claim or reproduction path. `SHOULD` failures damage composition or engineering usefulness. `MAY` items are optional improvements.

## Scene ownership and prohibited use

Every `MOD-*` rule has the unique owner `modeling_engineering`. It applies to a
modeling/engineering segment or to a local numerical/protocol claim explicitly
borrowed by another scene. It is prohibited as a replacement for:

- NOTE teaching standards: do not remove learner-facing explanation or demand
  parameter identification from a purely illustrative classroom example;
- RES proof/novelty standards: finite simulations, engineering tolerances, and
  practical approximation do not prove a theorem or establish novelty;
- CORE integrity: a `MOD-*` rewrite never relaxes facts, provenance, units,
  version authority, or mathematical validity.

Each rule below inherits this owner and prohibition even when the individual
entry does not repeat it.

## Evidence and Claims

### MOD-EVD-01 Claim strength follows the evidence (`MUST`)
Use `proves`, `validates`, `accurate`, `robust`, `causes`, and `optimal` only with a named criterion and suitable evidence. A local simulation supports a conditional model output.

### MOD-EVD-02 Calibration is not validation (`MUST`)
Label fitted anchors, in-sample residuals, post-fit checks, held-out tests, and independent external validation separately. Reusing a calibration target cannot validate the fitted model.

### MOD-EVD-03 Proxies remain proxies (`MUST`)
State the proxy formula, measurement relation, and missing link to the target. A weighted state sum is not CPUE, ecological health, quality, safety, or ground truth without a measurement model.

### MOD-EVD-04 Observation and mechanism stay separate (`MUST`)
Report the numerical pattern first. Mark mechanisms as encoded model behavior, interpretation, hypothesis, or externally tested explanation.

### MOD-EVD-05 Negative robustness changes the claim (`MUST`)
Preserve null results, sign reversals, failed seeds, solver drift, and counterexamples. Propagate the downgrade through title, abstract, captions, conclusion, and recommendations.

### MOD-EVD-06 External claims attach to exact sources (`MUST`)
Place a citation or source location beside the proposition. A nearby report, attachment title, or general API page is not passage-level support.

## Numbers and Parameters

### MOD-NUM-01 Match precision to identification (`MUST`)
Display no more significant digits than the weakest observation, calibration anchor, or identification design supports. Retain extra digits only in a labeled reproducibility table.

### MOD-NUM-02 Separate computational and inferential precision (`MUST`)
Solver tolerances and deterministic output digits describe computation, not measurement certainty. Do not use a close fitted value as evidence of predictive accuracy.

### MOD-NUM-03 Reconcile every denominator and total (`MUST`)
Verify sample counts, excluded runs, subgroup overlap, percentages, table totals, and missing seeds. Report `5/75`, not only `6.7%` or successful examples.

### MOD-PAR-01 Assign one role per parameter (`MUST`)
Classify each parameter as observed, calibrated, estimated, assumed, normalized, scenario control, or numerical control. Do not rotate roles across sections.

### MOD-PAR-02 State identifiability limits (`MUST`)
Count independent anchors against free parameters. If parameters are weakly identified or hand-set, report a family/range and avoid unique empirical interpretation.

### MOD-PAR-03 Give units, domains, and transformations (`MUST`)
Define units or explicit dimensionless normalization, admissible range, sign, and any log/scale transform before use.

### MOD-PAR-04 Do not justify one coefficient by analogy alone (`MUST`)
A distance ratio, literature range, visual resemblance, or domain story does not identify a mortality multiplier or coupling coefficient. Label the mapping as heuristic and test it.

## Model and Code

### MOD-CODE-01 Paper equations equal executed equations (`MUST`)
Match every term, coefficient, state order, sign, clipping rule, event, forcing function, and initial condition between manuscript and executed code.

### MOD-CODE-02 Defaults and overrides are evidence (`MUST`)
Record dataclass/config defaults and runtime overrides. A table that omits an override does not describe the experiment.

### MOD-CODE-03 Preserve transformation direction (`MUST`)
For normalization, interpolation, aggregation, clipping, and post-processing, state input, operation, output, lost information, and whether reversal is possible.

### MOD-CODE-04 Runnable is not equivalent (`MUST`)
Compilation, successful execution, or matching figure filenames do not establish scientific or equation-code correctness. Require independent mapping or tests.

### MOD-CODE-05 One artifact owns each result (`MUST`)
Name the script, config, data version, seed manifest, and output artifact that produce each table or figure. Do not mix stale summaries with current code.

## Scenarios and Experiments

### MOD-EXP-01 Enumerate every changed and fixed factor (`MUST`)
Build a scenario matrix. If two or more factors change, prohibit single-factor causal language unless a separate isolating contrast exists.

### MOD-EXP-02 Scenario names cannot hide confounding (`MUST`)
Names such as `pollution`, `policy`, `ablation`, or `method-only` must match the actual configuration. Otherwise rename the scenario as composite.

### MOD-EXP-03 Define the experimental unit and independence (`MUST`)
State whether units are seeds, functions, folds, sites, time windows, or parameter settings. Repeated measurements on one artifact are not independent replicates.

### MOD-EXP-04 Separate independent and shared budgets (`MUST`)
Independent-budget experiments isolate method logic; shared-budget experiments test end-to-end deployability. Do not use one to answer the other.

### MOD-EXP-05 Disclose cache and reuse policy (`MUST`)
State whether detection, grouping, initialization, preprocessing, or trajectories are cached or reused. Cache asymmetry can invalidate fairness claims.

### MOD-EXP-06 Ablations remove one component (`MUST`)
An ablation must change one declared component while holding initialization, budget, data, solver, and downstream processing fixed, or be labeled composite.

### MOD-EXP-07 Post-processing does not create new independent evidence (`MUST`)
Milestones extracted from one long run share randomness and history. Label them repeated-budget observations, not separately replicated experiments.

### MOD-EXP-08 Predeclare criteria and stopping rules (`SHOULD`)
State metric, comparison, threshold, budget, exclusions, and opposite-result interpretation before inspection when confirmatory language is planned.

## Sensitivity and Robustness

### MOD-ROB-01 Name the perturbed dimension (`MUST`)
Distinguish parameter, weight, seed, data split, initial state, solver, step size, time window, structural, and scenario sensitivity.

### MOD-ROB-02 Weight stability is only ranking stability (`MUST`)
Agreement across entropy, CRITIC, equal, or perturbed weights does not validate indicator choice, model structure, mechanism, observations, or external ecology.

### MOD-ROB-03 Solver, window, and initial state require separate checks (`MUST`)
Do not merge these into generic robustness. Report each grid, result, and fixed dimension; expose interactions when they matter.

### MOD-ROB-04 Deterministic grids are not statistical samples (`MUST`)
Do not call a hand-selected grid `statistical robustness` or attach population probabilities without a sampling design.

### MOD-ROB-05 Local sensitivity does not establish structural robustness (`MUST`)
Small perturbations around one parameterization cannot exclude alternate model classes, indicator definitions, or omitted mechanisms.

### MOD-ROB-06 Robust direction does not imply a robust threshold (`MUST`)
A trend may survive while a crossing, optimum, bifurcation, or rank gap moves. State these as separate claims.

## Engineering Reproducibility

### MOD-ENG-01 Record the executable protocol (`MUST`)
Include environment, dependency versions, command/config, random seeds, budget accounting, solver/tolerances, hardware when performance-relevant, and artifact path.

### MOD-ENG-02 Define budget accounting (`MUST`)
State what consumes evaluations, wall time, memory, tokens, or samples. Detector and optimizer costs cannot silently move outside the budget.

### MOD-ENG-03 Performance claims need measurements (`MUST`)
Complexity adjectives, star ratings, scalability, convergence, memory, and parallelism claims require code paths and benchmark evidence.

### MOD-ENG-04 Reasonable approximation requires an error contract (`MUST`)
State why approximation is used, its domain, tolerance or error bound, and what decision remains unchanged. `Close enough` is not a criterion.

### MOD-ENG-05 Workflow completion is scoped (`MUST`)
Keep `compiled`, `ran`, `reproduced`, `source-matched`, `numerically checked`, and `externally validated` as distinct states.

## Composition and Voice

### MOD-WRT-01 Let sections perform distinct jobs (`SHOULD`)
Methods define objects and protocol; results report outputs; discussion interprets alternatives; limitations delimit use; conclusion classifies robust and conditional findings.

### MOD-WRT-02 Replace template summaries with evidence hierarchy (`SHOULD`)
Do not force every subproblem into identical `method-result-advantage-limitation` paragraphs. Give decisive evidence more space.

### MOD-WRT-03 Use research objects as subjects (`SHOULD`)
Prefer the parameter, sample, solver, table, or scenario over `this framework`, `it is worth noting`, or project-management language.

### MOD-WRT-04 Remove engineering theater (`SHOULD`)
Replace `closed loop`, `production-ready`, `comprehensive`, `seamless`, `breakthrough`, and `fully verified` with the operation and passed criterion.

## Modeling-Specific Blacklist

Treat these as audit triggers, not automatic deletions:

```text
精确预测 准确验证 全面验证 外部验证 模型稳健 参数稳健
统计稳健 显著提升 作用机制 直接导致 唯一阈值 普适阈值
最优 完全收敛 工程可用 生产就绪 端到端闭环 合理参数
realistic parameters validated framework robust mechanism
state-of-the-art scalable efficient excellent production-ready
```

Acceptance requires evidence and scope, not a zero keyword count.
