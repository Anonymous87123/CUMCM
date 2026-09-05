# Modeling Paper Playbook

## Contents

1. Document contract
2. Audit mode
3. Rewrite mode
4. Generate mode
5. Mathematical-modeling competitions
6. Simulation and dynamical systems
7. Optimization and algorithm benchmarks
8. Engineering approximation reports
9. Abstract and conclusion contracts

## 1. Document Contract

Before writing, state:

```text
decision or question
real system and modeled object
observed data and measurement scope
states, units, assumptions, omitted mechanisms
parameters and identification source
equations and implementation artifact
experiment protocol and budget
validation level
supported and unsupported decisions
```

Treat a manuscript and its executed artifacts as one evidence system. The paper is incomplete when code changes a term, default, cache, scenario factor, or post-processing rule that the paper omits.

## 2. Audit Mode

Read the entire argument and supporting artifacts. Create:

- source/provenance map;
- observed/calibrated/assumed/simulated fact lock;
- parameter and identifiability ledger;
- equation-code mapping;
- scenario/factor matrix;
- sensitivity-dimension matrix;
- claim-evidence matrix;
- section-responsibility map.

Diagnose in this order:

```text
contradiction -> code equivalence -> factor isolation -> parameter role
-> numerical validity -> validation label -> scope -> precision
-> structure -> paragraph -> sentence
```

Do not assign a human-likeness score. Report observable failures and their engineering consequence.

## 3. Rewrite Mode

Lock facts and artifacts first. Do not silently correct results by changing a number, parameter, or equation. When evidence is missing:

- weaken the claim;
- rename the scenario;
- expose the parameter as assumed;
- mark the test not run;
- request a rerun or source location.

Keep reproducibility details once in methods or an appendix. Keep the full validity boundary at first use and summarize it once in the conclusion.

## 4. Generate Mode

Draft in this order:

1. Model contract and assumptions.
2. Parameter table with roles and sources.
3. Equations plus code mapping.
4. Scenario and experiment protocol.
5. Results with uncertainty and negative evidence.
6. Discussion with alternatives.
7. Limitations tied to decisions.
8. Abstract and conclusion.

Never invent a result to fill a conventional section. Use placeholders only in a private plan, not a publication draft.

## 5. Mathematical-Modeling Competitions

### Keep

- explicit simplification and why it preserves the decision of interest;
- dimensionless normalization with a reverse interpretation boundary;
- complete parameter roles and scenario controls;
- one reproducible pipeline from input to table/figure;
- conditional policy advice tied to modeled comparisons.

### Reject

- hand-set coefficients narrated as measured ecology or engineering constants;
- a calibration anchor called model validation;
- composite scenarios used for single-cause recommendations;
- three selected scenarios called comprehensive robustness;
- normalized scores presented as absolute health, safety, or quality;
- more decimals than the problem data support.

### Completion gate

The paper must say what a decision-maker may compare and what cannot be inferred about the real system.

## 6. Simulation and Dynamical Systems

Record solver, version, tolerances, step policy, event handling, clipping, time span, burn-in, observation window, initial states, and convergence/stationarity criteria.

Separate:

- trajectory description;
- finite-time numerical diagnostic;
- asymptotic or invariant claim;
- real-world mechanism.

A finite-time Lyapunov estimate, local bifurcation scan, or coarse grid does not establish a unique global threshold. Test window, solver/step, and initial-state effects separately. Report failed settings.

## 7. Optimization and Algorithm Benchmarks

Define the unit: function-seed pair, fold, instance, or run. State evaluation budget, detector/preprocessing cost, stopping rule, cache reuse, initialization, optimizer, post-processing, hardware, and missing runs.

Use independent-budget and shared-budget results for their distinct questions. Keep nested budget milestones as dependent checkpoints. An ablation must isolate one component. A mechanism claim needs an intermediate object or controlled contrast, not only final performance.

Performance adjectives require a benchmark artifact. Verify algorithm names, class paths, defaults, and complexity against code/tests or primary sources.

## 8. Engineering Approximation Reports

For every approximation, provide:

```text
target quantity | approximation | domain | reference
error metric | tolerance | sensitivity | protected decision
```

Include units and dimensional checks. Report numerical conditioning and failure regimes. `Reasonable` means the error is below a decision-relevant threshold under stated conditions, not that a curve looks plausible.

Do not borrow classroom permission to omit conditions or journal-proof language to overstate numerical evidence.

## 9. Abstract and Conclusion Contracts

### Abstract

Include the question, model identity, central result, validation level, and one material boundary. Do not list every module or fill the abstract with reproducibility decimals.

### Conclusion

Separate:

```text
robust under tested dimensions
conditional on one parameterization/protocol
rejected by negative robustness
unresolved or not tested
engineering implication supported by the above
```

Do not introduce new numbers, evidence, or recommendations.
