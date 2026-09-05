# Modeling Diagnostic Matrix

Use for full audits. Record each finding as:

```text
Rule | severity | exact location | excerpt/artifact
tested object | evidence | fixed dimensions | problem
consequence | repair | evidence still needed
```

## Severity

| Level | Definition |
|---|---|
| Blocking | Contradiction, model-code mismatch, hidden confounding, invalid mathematics, or missing definition that prevents interpretation/reproduction |
| Major | Other `MUST` failure affecting evidence, precision, parameter role, protocol, or claim strength |
| Moderate | Repeated structure, voice, hierarchy, or section-responsibility failure |
| Minor | Local polish without evidentiary effect |

## 1. Provenance and Authority

| Check | Pass evidence | Failure locator |
|---|---|---|
| Authority manuscript | one named current file/version | backups or summaries conflict |
| Result owner | script/config/data/artifact for each result | table cannot be traced |
| External fact | exact source/page/section | paragraph-end citation cluster |
| Segment identity | problem/source/argument/code/audit separated | inherited text counted as authored argument |

## 2. Evidence-Class Matrix

Label every material value:

| Class | Meaning | Allowed prose |
|---|---|---|
| Observed | measured under stated protocol | report with uncertainty/scope |
| Calibrated | chosen to match target | fit, not validation |
| Estimated | inferred with method/uncertainty | estimate within model |
| Assumed | selected without identification | scenario/structural assumption |
| Normalized | transformed scale | relative/internal value |
| Simulated | numerical output | under parameterization/protocol |
| Derived | score/statistic from inputs | conditional comparison |
| Display-only | extra digits/format | reproduction only |

Flag drift when one value changes class between methods, results, and conclusion.

## 3. Parameter and Identifiability Matrix

| Parameter | Value/range | Unit/domain | Role | Source | Anchors | Correlated parameters | Identified? |
|---|---|---|---|---|---|---|---|

Questions:

- How many independent anchors constrain how many free parameters?
- Can multiple parameter sets produce the same observable?
- Was a fixed normalization later interpreted empirically?
- Does sensitivity cover the plausible non-identifiability family?
- Does literature support the value itself or only the model form?

## 4. Equation-Code Matrix

| Paper object | Code object | Terms/signs | Parameter map | Defaults/overrides | Events/clipping | Status |
|---|---|---|---|---|---|---|

Check state order, unit conversion, interpolation, missing terms, hidden clipping, numerical floors, stochastic draws, data preprocessing, and post-processing. Compare executed configuration, not only class defaults.

## 5. Scenario and Factor Matrix

| Scenario | Changed factors | Fixed factors | Data/input | Initial state | Solver/window | Valid contrast |
|---|---|---|---|---|---|---|

Fail when a scenario name implies one factor but the configuration changes several. A factorial or isolating contrast is required for single-factor attribution.

## 6. Protocol Matrix

| Run family | Experimental unit | Budget | Seed/repeats | Cache/reuse | Stop rule | Post-process | Missing runs |
|---|---|---|---|---|---|---|---|

Verify budget charging, seed independence, nested checkpoints, excluded failures, and whether post-processing uses future information.

## 7. Sensitivity Matrix

| Claim | Parameter | Weight | Seed | Data split | Initial state | Solver/step | Window | Structure |
|---|---|---|---|---|---|---|---|---|

Use `tested`, `fixed`, or `not tested`. Never summarize a single checked column as full robustness.

## 8. Quantitative and Approximation Matrix

| Value/approximation | Upstream precision | Digits shown | Error metric | Range/CI | Decision threshold | Justified? |
|---|---|---|---|---|---|---|

Check totals, denominators, rounding, units, missing seeds, numerical tolerances, condition numbers, and whether approximation error could cross the claimed decision boundary.

## 9. Claim-Evidence Matrix

| Claim | Verb | Evidence level | Scope | Counterevidence | Fixed dimensions | Supported wording |
|---|---|---|---|---|---|---|

Evidence ladder:

```text
formal proof under assumptions
independent external validation
held-out prediction
controlled comparative experiment
sensitivity/stress test
calibration
simulation observation
heuristic/analogy
editorial expectation
```

Do not promote a lower level through confident prose.

## 10. Structure and Voice

| Section | Unique job | Main evidence | Boundary | Duplicate locations | Action |
|---|---|---|---|---|---|

Scan for mechanical per-subproblem summaries, repeated limitations, project-management language, universal significance statements, and abstract claims stronger than the body.

## Scoring

Do not compute a human-likeness score. A document fails while any Blocking issue remains. Optional 0-2 readiness scoring may cover provenance, model-code equivalence, parameter identity, protocol isolation, numerical honesty, validation, structure, and reproducibility, but it never overrides a failed gate.
