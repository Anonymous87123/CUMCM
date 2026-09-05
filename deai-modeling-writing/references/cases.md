# Source-Derived Modeling Cases

Use these cases as diagnostic evidence. Do not copy their conclusions into a new manuscript without checking the new artifacts.

## Contents

1. Calibration anchor called validation
2. Reproducibility digits presented as empirical precision
3. Weight perturbation called model robustness
4. Negative threshold robustness retained honestly
5. Pollution scenario hides four changed factors
6. Paper equation differs from executed code
7. Proxy state sum called CPUE
8. Initial anchor called external validation
9. Independent and shared budgets answer different questions
10. Cache reuse changes protocol fairness
11. Milestones from one trajectory called independent runs
12. Mechanism narrative outruns ablation evidence
13. Undefined experiment ID breaks evidence provenance
14. API page invents algorithm identity and performance
15. Successful workflow called scientific correctness
16. Approximation has no error contract

## 1. Calibration Anchor Called Validation

**Source:** Yangtze ecological modeling manuscript.

One approximate `1.8x` aggregate-fish observation fits `gain_scale`. The fitted output is `1.805`, and the prose calls the agreement accurate validation. A local `2.2x` catch record, with different spatial and gear scope, is also called independent external validation despite no acceptance threshold.

**Failure:** fitting success and directional consistency are promoted up the evidence ladder.

**Repair:** call `1.8x` a calibration anchor; call the local proxy a post-fit directional check; state the scope mismatch and absence of an independent validation set.

**Rules:** `MOD-EVD-01`, `MOD-EVD-02`, `MOD-NUM-02`.

## 2. Reproducibility Digits Presented as Empirical Precision

**Source:** Yangtze ecological modeling manuscript.

An approximate anchor and hand-set normalized coefficients produce `1.805`, `1.838`, `4.213`, and `0.204`. Three decimals help rerun a deterministic script but do not reflect measurement or parameter-identification precision.

**Repair:** use about `1.81`, `1.84`, `4.21`, and `0.20` in interpretation; retain full outputs in a reproducibility table with an explicit precision note.

**Rules:** `MOD-NUM-01`, `MOD-NUM-02`, `MOD-PAR-02`.

## 3. Weight Perturbation Called Model Robustness

**Source:** Yangtze three-scenario health ranking.

Entropy, CRITIC, equal, and 2,000 locally perturbed weight vectors preserve one ordering. Indicators, normalization, scenarios, model equations, observations, and outputs remain fixed.

**Supported:** ranking stability conditional on the fixed indicator matrix and admissible weight range.

**Unsupported:** model validity, indicator validity, ecological mechanism, parameter robustness, or out-of-sample prediction.

**Rules:** `MOD-ROB-01`, `MOD-ROB-02`, `MOD-EVD-03`.

## 4. Negative Threshold Robustness Retained Honestly

**Source:** Yangtze finite-time Lyapunov scan.

A sign crossing near `3.2186` appears in a short window. Only `5/75` initial-state, step-size, and window combinations retain the `3.20-3.22` crossing. The manuscript correctly withdraws a unique threshold while retaining a weaker directional complexity claim.

**Preserve:** the denominator, failed settings, and claim downgrade.

**Further repair:** call the 75 settings a deterministic stress grid, not a statistical sample.

**Rules:** `MOD-EVD-05`, `MOD-ROB-03`, `MOD-ROB-04`, `MOD-ROB-06`.

## 5. Pollution Scenario Hides Four Changed Factors

**Source:** Yangtze manuscript plus `model_pipeline.py`.

The paper says the pollution scenario raises only `u`. The executed configuration also raises barrier loss and changes porpoise conversion and natural loss. Later prose attributes all endpoint changes to pollution.

**Failure:** scenario name, method description, code, and causal interpretation disagree.

**Repair:** rerun a pollution-only contrast or rename the scenario as a composite stress setting and remove single-factor causality.

**Rules:** `MOD-EXP-01`, `MOD-EXP-02`, `MOD-CODE-02`, `MOD-EVD-04`.

## 6. Paper Equation Differs From Executed Code

**Source:** Yangtze polluted food-web rerun.

The manuscript puts pollution only in a resource-loss term. The script also scales resource growth, uses resource-specific pollution coefficients, and adds fish pollution mortality. The baseline with `u=0` hides the mismatch; question-five results with `u>0` expose it.

**Consequence:** the reported scenario cannot be reproduced from the printed model.

**Rules:** `MOD-CODE-01`, `MOD-CODE-02`, `MOD-CODE-04`.

## 7. Proxy State Sum Called CPUE

**Source:** Yangtze food-web model.

`CPUE*` is a weighted sum of normalized fish states with a heuristic black-carp weight. It contains no catchability, effort, gear, or observation-error model. Calling it actual catch per unit effort hides the measurement gap.

**Repair:** call it a CPUE-oriented state proxy, print the formula, and state what standardization data would be needed.

**Rules:** `MOD-EVD-03`, `MOD-PAR-04`.

## 8. Initial Anchor Called External Validation

**Source:** rare-species results table.

Observed porpoise and sturgeon counts initialize the normalized model, then a table marks them as external validation. A later spawning-site observation is treated as validation of simulated population growth, although the objects differ.

**Repair:** label counts as initial-state anchors and the spawning observation as directionally compatible external context.

**Rules:** `MOD-EVD-02`, `MOD-EVD-03`.

## 9. Independent and Shared Budgets Answer Different Questions

**Source:** BYD/SCCD experiment master plan.

Independent-budget runs place decomposition cost outside the downstream optimization budget to isolate grouping logic. Shared-budget runs charge both stages to test deployability under a unified budget.

**Failure mode:** presenting shared-budget degradation as failure of grouping logic, or independent-budget wins as end-to-end production advantage.

**Rules:** `MOD-EXP-04`, `MOD-ENG-02`, `MOD-EVD-01`.

## 10. Cache Reuse Changes Protocol Fairness

**Source:** optimization experiment planning and run manifests.

One method reuses detection or grouping artifacts while another regenerates them. If the paper says every run includes fresh grouping, cache reuse changes cost, randomness, and effective budget.

**Repair:** disclose cache keys, invalidation, reuse scope, charged cost, and whether cached artifacts cross seeds or budgets.

**Rules:** `MOD-EXP-05`, `MOD-ENG-02`, `MOD-CODE-05`.

## 11. Milestones From One Trajectory Called Independent Runs

**Source:** SCCD plan extracting `1e6` and `2e6` milestones from a `3e6` trajectory.

This is efficient and valid for budget-curve analysis, but milestones share seed, initialization, optimizer history, and early evaluations. They are not independent replications at three budgets.

**Repair:** call them nested checkpoints and preserve the repeated-measures dependency in statistics.

**Rules:** `MOD-EXP-03`, `MOD-EXP-07`.

## 12. Mechanism Narrative Outruns Ablation Evidence

**Source:** SCCD grouping manuscript and experiment plans.

Local geometry, block classification, size control, and downstream optimization all change around the proposed method. Performance improvement alone cannot establish that condition-number improvement is the operative mechanism.

**Repair:** isolate one component per ablation, report the intermediate geometric object, and retain alternative explanations when the evidence is observational.

**Rules:** `MOD-EXP-06`, `MOD-EVD-04`, `MOD-PAR-02`.

## 13. Undefined Experiment ID Breaks Evidence Provenance

**Source:** SCCD experiment master plan.

The plan defines `P1-P3`, later explains and cites `P4`, while figure sources map `P3/P4` inconsistently. A polished result cannot be tied to one authority protocol.

**Repair:** maintain an ID registry with claim, command, config, data, artifact, budget, status, and superseded IDs.

**Rules:** `MOD-CODE-05`, `MOD-ENG-01`.

## 14. API Page Invents Algorithm Identity and Performance

**Source:** LSGO Platform `docs/zh/api/algorithms.md`.

The page expands DG2, RDDSM, and CSG, lists class paths, gives memory/convergence star ratings, and recommends use cases without matching repository paths or benchmark artifacts.

**Repair:** derive names and signatures from importable code and tests; attach performance claims to a reproducible benchmark or remove them.

**Rules:** `MOD-ENG-03`, `MOD-CODE-05`, `MOD-EVD-06`.

## 15. Successful Workflow Called Scientific Correctness

**Source:** modeling and solution-quality ledgers.

`Compiled`, `all seeds completed`, `no placeholders`, and `figure generated` are followed by `model verified`. Each workflow result is useful but tests a different property.

**Repair:** use a state ladder: generated -> ran -> artifact-reproduced -> equation-matched -> numerically checked -> externally validated.

**Rules:** `MOD-ENG-05`, `MOD-CODE-04`.

## 16. Approximation Has No Error Contract

**Source:** engineering modeling prose using interpolation, normalization, finite windows, and coarse grids.

The paper calls an approximation reasonable because curves look similar or rankings remain unchanged at a few points. No error metric, tolerance, domain, or decision boundary is stated.

**Repair:** define approximation target, reference calculation, error measure, admissible domain, tolerance, and the conclusion protected by that tolerance.

**Rules:** `MOD-ENG-04`, `MOD-EVD-01`.
