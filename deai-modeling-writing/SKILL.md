---
name: deai-modeling-writing
description: Audit, rewrite, and generate mathematical-modeling, simulation, optimization, engineering-analysis, and data-driven competition papers with reproducible model-code equivalence, calibrated numerical precision, explicit parameter provenance, honest validation labels, and evidence-preserving prose. Use for TeX/Markdown manuscripts, experiment plans, model reports, sensitivity studies, scenario analyses, algorithm benchmarks, and reviewer responses when claims may overstate calibration, proxies, robustness, causality, solver evidence, or engineering readiness.
---

# De-AI Modeling Writing

Produce modeling prose that is useful to an engineer and defensible to a reviewer. Treat natural writing as a consequence of explicit objects, protocols, results, and limits. Do not humanize by inventing data, experience, citations, or uncertainty.

## Required References

Always read [rules.md](references/rules.md). Then load:

| Task | Required references |
|---|---|
| Full audit | [diagnostic-matrix.md](references/diagnostic-matrix.md), [validation-gates.md](references/validation-gates.md), [cases.md](references/cases.md) |
| Rewrite | [rewrite-patterns.md](references/rewrite-patterns.md), [validation-gates.md](references/validation-gates.md) |
| Generate | [playbook.md](references/playbook.md), [validation-gates.md](references/validation-gates.md) |
| Reusable model prompt | [system-prompt-contract.md](references/system-prompt-contract.md) |
| Scenario, sensitivity, benchmark, or solver claim | [playbook.md](references/playbook.md), [cases.md](references/cases.md) |

Read selected files completely. On Windows, read as UTF-8. Keep reference depth at one level.

## Non-Negotiable Boundary

Use this skill for research and engineering modeling, not as a substitute for:

- journal-proof mathematics: simulation, finite grids, or numerical agreement never prove a theorem, global sign, exact locus, convergence rate, or universal optimum;
- classroom looseness: intuitive analogies, omitted units, hand-waved algebra, and convenient parameters are not acceptable merely because a model is pedagogical;
- software verification: compilation, a runnable script, or matching screenshots do not establish equation-code equivalence or scientific validity;
- authorship evasion: do not optimize for detector scores or claim human authorship.

## Workflow

### 1. Establish the contract

Record the authority manuscript, code/data artifacts, intended reader, central decisions, observation boundary, and requested mode: `audit`, `rewrite`, or `generate`.

Classify every material item:

```text
observed | calibrated | estimated | assumed | normalized
simulated | derived | display-only | externally validated
```

### 2. Build four ledgers before prose work

1. **Claim ledger:** claim, verb, evidence, scope, counterevidence.
2. **Parameter ledger:** symbol, value, unit/domain, role, source, identification.
3. **Protocol ledger:** changed factors, fixed factors, seed, budget, cache, solver, window, initial state, post-processing.
4. **Equation-code ledger:** paper equation, implementation path, parameter mapping, clipping/events/defaults, equivalence status.

Do not style-edit around a contradiction in these ledgers.

### 3. Run gates in order

Apply [validation-gates.md](references/validation-gates.md): authority -> provenance -> model-code equivalence -> quantitative reconciliation -> identifiability -> experiment isolation -> numerical robustness -> claim-evidence -> composition -> regression.

An unresolved `MOD-* MUST` issue is Blocking when it invalidates interpretation or reproduction. Continue collecting all audit findings, but stop an affected rewrite or generation claim.

### 4. Preserve useful engineering detail

Keep reproducible inputs and outputs, units, parameter roles, solver settings, seeds, budgets, stopping rules, negative results, failed sensitivity, and operational limitations. Compress duplicated narration, not evidence.

### 5. Rewrite around the tested object

Prefer:

```text
under protocol P -> output O -> comparison C -> supported claim S
-> fixed dimensions F -> unresolved boundary B
```

Use the weakest accurate verb. Distinguish directional agreement, calibration fit, held-out consistency, external validation, and formal proof.

### 6. Validate the delivered artifact

Check numbers, units, equations, tables, code defaults, scenario factors, denominators, precision, seeds, negative results, and citations. Name each passed property. Never collapse `runs`, `reproduces`, `fits`, `is robust`, and `is valid` into one status.

## Modes

### Audit

Return a severity-ordered table with `Rule | Location | Evidence | Consequence | Action`. Include source map, four ledgers, blocking contradictions, claim-evidence matrix, representative rewrites, unresolved evidence requests, and gate summary.

### Rewrite

Preserve facts, equations, labels, citations, and negative results. Repair in this order: contradiction -> model-code mismatch -> factor isolation -> evidence verb -> precision -> section responsibility -> sentence style. Add a change ledger and leave unresolved claims explicitly open.

### Generate

Define model object, units, assumptions, data roles, parameter identification, protocol, acceptance criteria, and validation boundary before drafting. Write methods and results before abstract and conclusion. Do not generate polished numerical claims without an artifact that produces them.

## Hard Failures

Flag and stop the affected claim when:

- manuscript equations and executed code differ materially;
- a named scenario changes undeclared factors;
- calibration data are reused as validation without disclosure;
- a proxy is presented as ground truth;
- displayed precision exceeds measurement or identification strength;
- weight perturbation is called parameter or model robustness;
- failed solver/window/initial-state tests are hidden;
- an empirical parameter is not identified but is narrated as measured;
- cached, shared-budget, or post-processed results are presented under another protocol;
- a simulation is written as real-world causation or journal-level proof.

## Final Standard

Pass only when another competent reader can reconstruct what was observed, assumed, fitted, computed, perturbed, held fixed, and not tested. Concision is desirable; missing evidence is not.
