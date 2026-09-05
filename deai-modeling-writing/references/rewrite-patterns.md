# Modeling Rewrite Patterns

Apply only after contradictions and evidence gaps are identified. A rewrite must not create support that the experiment lacks.

## 1. Calibration to Scoped Fit

**Trigger:** `accurately validates the observed value` after fitting that value.

**Rewrite:** `Parameter p was calibrated to anchor a. The fitted output is b; this residual measures calibration fit and is not an independent validation result.`

## 2. Validation to Directional Check

**Trigger:** local, differently measured, or non-held-out evidence called validation.

**Rewrite:** `The proxy and external record move in the same direction. Because their spatial and measurement scopes differ and no threshold was predeclared, the comparison is a directional consistency check.`

## 3. Reproducibility Precision to Inferential Precision

**Trigger:** long decimals from approximate anchors.

**Rewrite:** `The simulated value is about 1.84. The run table retains 1.838 for deterministic reproduction; the third decimal is not observational precision.`

## 4. Proxy to Explicit Measurement Gap

**Trigger:** state score presented as a real-world metric.

**Rewrite:** `P* is the weighted sum ... and is used only for internal comparison. It omits catchability, effort standardization, and observation error, so it does not equal measured CPUE.`

## 5. Composite Scenario to Honest Name

**Trigger:** named scenario changes several factors.

**Rewrite:** `This composite stress setting changes pollution, barrier loss, and mortality parameters together. Its endpoint difference is a joint response and cannot isolate pollution.`

## 6. Model Output to Mechanism Hypothesis

**Trigger:** `X causes Y` from one simulation.

**Rewrite:** `Under parameterization P, X and Y change together. This pattern is compatible with mechanism M encoded in equation q; observations or an isolating experiment are needed to distinguish M from alternatives.`

## 7. Weight Robustness to Ranking Sensitivity

**Trigger:** `the model is robust under 2,000 perturbations` where only weights vary.

**Rewrite:** `For the fixed indicator matrix and scenarios, the ordering is unchanged under the tested weight methods and perturbation range. Model structure and external validity were not tested.`

## 8. Deterministic Grid to Stress Test

**Trigger:** `statistically robust in 75 tests` from a designed grid.

**Rewrite:** `The crossing appears in 5 of 75 tested configurations. This deterministic stress grid shows sensitivity to numerical settings; it is not a population-frequency estimate.`

## 9. Robust Trend, Unstable Threshold

**Trigger:** one sentence conflates direction and breakpoint.

**Rewrite:** `The direction of change persists across the tested range, but the crossing location shifts with window and initial state. We retain the directional result and do not claim a unique threshold.`

## 10. Equation-Code Mismatch Disclosure

**Trigger:** executed terms absent from paper.

**Rewrite:** `The reported polluted run used the implementation in artifact A, which additionally includes terms ... . Until the printed equations are synchronized and results rerun, this scenario is not reproducible from the manuscript alone.`

## 11. Weak Identification to Parameter Family

**Trigger:** many free parameters and few anchors.

**Rewrite:** `The available anchors identify the aggregate scale but not each structural coefficient. We therefore treat these coefficients as a plausible parameter set and report sensitivity over range R rather than unique estimates.`

## 12. Shared-Budget Boundary

**Trigger:** shared-budget result used as method-logic proof.

**Rewrite:** `Independent-budget runs isolate the grouping decision. Shared-budget runs additionally charge detection cost and therefore measure end-to-end deployability under budget B.`

## 13. Nested Milestones

**Trigger:** checkpoints from one run called independent experiments.

**Rewrite:** `The 1e6 and 2e6 values are checkpoints from the same 3e6 trajectory. They support within-run budget trends but not independent cross-budget replication.`

## 14. Cache Policy Disclosure

**Trigger:** reuse hidden behind generic reproducibility language.

**Rewrite:** `Grouping artifacts are cached by data version, method config, and seed. Cache hits reuse detection output and their cost is [included/excluded] from the reported budget.`

## 15. Approximation With Error Contract

**Trigger:** `reasonable approximation` without a criterion.

**Rewrite:** `On domain D, approximation A differs from reference R by at most e under metric m. This is below decision margin tau, so the reported ordering is unchanged; no claim is made outside D.`

## 16. Workflow State to Scientific State

**Trigger:** `the model is verified because code ran and figures match`.

**Rewrite:** `The script completed and regenerated tables T1-T3 from config C. Equation-code equivalence and external validation are separate gates and remain [passed/not run].`

## 17. Unsupported Performance Rating

**Trigger:** stars or adjectives for speed, memory, convergence, scalability.

**Rewrite:** replace the rating with `Under benchmark B, hardware H, budget Q, and seed set S, method M used x time/y memory and obtained metric z.` Delete the claim if those artifacts do not exist.

## 18. Overloaded Abstract Result

**Trigger:** every subproblem contributes multiple decimals and a universal conclusion.

**Rewrite order:** question -> model identity -> one or two decision-relevant outputs -> strongest negative/validity boundary. Move reproduction decimals to tables.
