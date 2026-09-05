# Modeling Validation Gates

Run in order. A later prose pass cannot override an earlier failure.

## Gate 0: Task and Authority

Record operation, authority manuscript, code/data sources, historical artifacts, target reader, and facts that must be preserved.

**Fail:** no authority version or result artifacts come from an unknown/stale protocol.

## Gate 1: Provenance and Fact Lock

Build a source map and classify values as observed, calibrated, estimated, assumed, normalized, simulated, derived, or display-only.

**Fail:** a core external fact has no locatable source; a value changes evidence class across sections.

## Gate 2: Model-Code Equivalence

For every result-bearing model:

1. Map states and order.
2. Compare every equation term and sign.
3. Map parameter names, defaults, and runtime overrides.
4. Record interpolation, clipping, floors, events, and stochastic draws.
5. Compare initial conditions and forcing inputs.
6. Trace table/figure post-processing.

**Fail:** executed behavior differs materially from the printed model or cannot be reconstructed.

## Gate 3: Parameter Identity and Identifiability

Create a parameter ledger. Count anchors and free degrees of freedom. Check units, domains, transformations, source support, correlated effects, and plausible ranges.

**Fail:** assumed parameters are presented as observed/estimated; one weak anchor supports many uniquely interpreted coefficients; missing parameter values prevent rerun.

## Gate 4: Scenario and Experiment Isolation

Build changed/fixed factor matrices. Verify ablations, experimental units, independence, budget accounting, cache policy, seeds, stopping rules, and missing runs.

**Fail:** a single-factor or causal claim comes from a composite setting; independent/shared budget semantics are mixed; cache or reuse changes fairness without disclosure.

## Gate 5: Quantitative Reconciliation

Recompute totals, denominators, percentages, table values, units, rounding, and seed counts. Trace each displayed value to an artifact.

For precision, compare digits with the weakest upstream observation or identification source. Store full floats when useful; display only justified digits in prose.

**Fail:** conflicting values, unexplained exclusions, or precision that implies unsupported inference.

## Gate 6: Numerical and Approximation Validity

Record solver, tolerances, step policy, time span, burn-in, observation window, initial states, convergence criterion, approximation domain, reference, error metric, and tolerance.

Run or inspect separate checks for:

| Dimension | Required report |
|---|---|
| Solver/step | grid and output drift |
| Window/burn-in | stability of summary/threshold |
| Initial state | basin or transient dependence |
| Seed | distribution and failures |
| Parameter | local/global range and re-identification policy |
| Structure | alternate equations/indicators when material |

**Fail:** a finite or local diagnostic is written as asymptotic/global truth; approximation lacks an error contract.

## Gate 7: Robustness Decomposition

List perturbed and fixed dimensions for every robustness claim. Separate stable ranking, stable direction, stable magnitude, stable threshold, and stable mechanism.

**Fail:** weight stability becomes model validity; deterministic grids become statistical probability; negative robustness does not downgrade the claim.

## Gate 8: Claim-Evidence and External Validation

Build a claim-evidence matrix for title, abstract, result headings, captions, conclusion, and recommendations. Verify acceptance thresholds and external source alignment.

**Fail:** calibration is validation, proxy is ground truth, simulation is reality, or a recommendation depends on a confounded scenario.

## Gate 9: Composition

Check distinct section jobs, evidence proximity, information exit, stable terminology, one dominant paragraph function, and research voice. Remove planning language and unsupported adjectives only after earlier gates.

**Fail:** structure hides evidence boundaries or contradictory claims survive in summaries.

## Gate 10: Regression and Release

Confirm:

- numbers, units, equations, citations, labels, seeds, and negative results are preserved or documented;
- no claim is strengthened;
- paper equations match executed code;
- tables and figures trace to current artifacts;
- workflow states remain separate;
- mechanical build status is named independently.

Release declaration:

```text
Authority/provenance: PASS/FAIL
Model-code equivalence: PASS/FAIL/NOT RUN
Parameter identifiability: PASS/FAIL
Scenario isolation: PASS/FAIL
Quantitative reconciliation: PASS/FAIL
Numerical/approximation validity: PASS/FAIL/NOT RUN
Robustness labeling: PASS/FAIL
Claim-evidence alignment: PASS/FAIL
Composition: PASS/FAIL
Mechanical integrity: PASS/FAIL/NOT RUN
Unresolved blockers: ...
```

Do not declare completion while a `MUST` gate fails.

## Reusable Ledgers

### Equation-Code Ledger

```markdown
| Result | Paper equation | Code path | Config | Difference | Recomputed? |
|---|---|---|---|---|---|
```

### Protocol Ledger

```markdown
| Run | Changed | Fixed | Unit | Budget/cache | Seed | Solver/window | Artifact |
|---|---|---|---|---|---|---|---|
```

### Precision Ledger

```markdown
| Value | Class | Identification | Stored digits | Display digits | Range/error | Wording |
|---|---|---|---|---|---|---|
```

### Completion-State Ledger

```markdown
| Artifact | Ran | Reproduced | Equation-matched | Numerically checked | Externally validated | Evidence |
|---|---|---|---|---|---|---|
```
