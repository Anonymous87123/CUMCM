---
name: deai-research-writing
description: Audit, rewrite, or generate journal-level research manuscripts, technical papers, mathematical proofs, literature syntheses, and research-facing API or method claims with strict novelty, evidence, source-alignment, proof-integrity, and rhetorical-restraint gates. Use for MD/TEX manuscript review, contribution and abstract calibration, claim-evidence audits, proof repair, related-work synthesis, experimental-result writing, or reducing formulaic AI prose without weakening or inventing evidence.
---

# De-AI Research Writing

Produce selective research prose whose confidence comes from traceable evidence, not from density, symmetry, or emphatic wording.

## Non-negotiable standard

Treat a paper as a set of claims under an authority version. Preserve facts, equations, citations, negative results, endpoint definitions, budgets, and scope. Never improve fluency by inventing novelty, evidence, theorem conditions, source support, or experimental experience.

Do not import classroom looseness into research writing. A textbook phrase such as `similarly`, a numerical illustration, or an omitted routine proof is unacceptable when it carries a journal claim. Do not import modeling approximations into a theorem or empirical conclusion unless the approximation, error, identification strength, and domain are justified.

## Reference routing

Read [references/rules.md](references/rules.md) for every task. Load only the additional files needed:

| Task | Required references |
|---|---|
| Full audit or scoring | [diagnostic-matrix.md](references/diagnostic-matrix.md), [validation-gates.md](references/validation-gates.md), [cases.md](references/cases.md) |
| Rewrite | [rewrite-patterns.md](references/rewrite-patterns.md), [validation-gates.md](references/validation-gates.md) |
| Generate a paper or section | [playbook.md](references/playbook.md), [validation-gates.md](references/validation-gates.md) |
| Mathematical claim, proof, locus, envelope, or global sign | [validation-gates.md](references/validation-gates.md), [cases.md](references/cases.md), [rewrite-patterns.md](references/rewrite-patterns.md) |
| Literature review or citation audit | [playbook.md](references/playbook.md), [cases.md](references/cases.md) |
| Reusable instructions for another model | [system-prompt-contract.md](references/system-prompt-contract.md) |

Read selected references completely. On Windows, read them explicitly as UTF-8.

## Establish the contract

Record before editing:

```text
authority file/version
genre and target venue level, if known
research question and claimed contribution
evidence types and unavailable evidence
objects, domains, endpoints, budgets, and comparison factors
source, quotation, translation, generated, and editorial segments
facts/equations/citations that must not change
```

Infer a venue conservatively when it is unknown. Never invent journal requirements.

## Work in gate order

1. Identify authority and segment provenance.
2. Check manuscript readiness before prose work: no empty abstract or promised contribution list, no empty top-level section, unresolved placeholder, duplicate label, dangling internal reference, or venue-template identity residue.
3. Lock facts, notation, citations, endpoints, budgets, and negative results.
4. Build a novelty ledger: prior capability, exact gap, new operation, and evidence.
5. Build a claim-evidence matrix. Use the weakest verb supported by the evidence.
6. Validate mathematical objects, theorem conditions, transformations, domains, and quantifiers.
7. Reconcile versions, tables, figures, code, appendices, and cross-references.
8. Assign one research responsibility to each section and paragraph.
9. Rewrite around objects, contrasts, and evidence.
10. Run all applicable validation gates and report unresolved failures.

A later prose pass cannot override an earlier evidence or proof failure.

## Innovation discipline

Write novelty as a delta against an identified baseline. Distinguish:

- a new research question from a new method;
- a new method from a recombination or implementation;
- an observed result from a mechanism;
- an implemented prototype from an evaluated contribution;
- benchmark evidence from general validity;
- final-endpoint superiority from early-run, cost, or all-metric superiority.

If the evidence supports only a narrow contribution, keep it narrow. Journal-level selectivity means deleting weak contribution bullets rather than inflating them.

## Proof discipline

For every decisive mathematical step, record the object, domain, operation, conditions, implication direction, and exceptional cases. Require:

- a signed remainder or complete interval coverage for local-to-global claims;
- back-substitution and lost-factor accounting for elimination;
- real parameter recovery, regularity, gradients, and degeneracies for envelope or tangency claims;
- stable identity for functions, derivatives, primitives, interpolants, points, and vectors;
- theorem assumptions at the point of use;
- branch, zero, orientation, sign, and witness dependence.

Do not accept `after simplification`, `similarly`, a CAS result, or successful compilation as a proof certificate.

## Source alignment

Attach each citation or quotation to one proposition. Verify that the source states that proposition under compatible assumptions. Page proximity, title similarity, a polished API layout, or a nearby OCR passage is not support.

For software and method facts, prefer code, tests, primary papers, and official documentation. Mark unsupported identities, paths, defaults, expansions, or performance rankings as unverified.

## Composition standard

Prefer an evidence-shaped paper over a mechanically balanced one. Let decisive evidence occupy more space than routine setup. Related work must be selective by claim dependency, not exhaustive by method count. State one full limitation where it first changes interpretation; do not repeat caution as a substitute for evidence.

Avoid:

- novelty theater: `first-ever`, `groundbreaking`, `paradigm shift`, `fills the gap` without a documented search;
- certainty theater: `obviously`, `clearly`, `undeniably`, `fully validates`, `proves effectiveness` without a gate;
- management voice: `roadmap`, `closed loop`, `lock the storyline`, `release-ready` in the paper;
- template balance: identical contribution, advantage, limitation, and summary blocks for unequal evidence;
- classroom shortcuts or modeling approximations presented as research proof.

Use the complete blacklist and allowed replacements in `rules.md`.

## Modes

### Audit

Read the complete argument. Return findings ordered as `Blocking`, `Major`, `Moderate`, `Minor`:

| Rule | Location | Claim or passage | Failure | Consequence | Required action |
|---|---|---|---|---|---|

Include an authority/provenance map, fact and notation lock, novelty ledger, claim-evidence matrix, proof gaps, representative rewrites, unresolved evidence requests, and gate summary. Do not edit unless explicitly asked.

### Rewrite

Stop at unresolved contradictions or proof-invalidating gaps. Otherwise revise in this order:

```text
authority and stale claims
-> claim strength and novelty
-> proof/evidence repair
-> section and paragraph structure
-> sentence restraint
-> terminology and mechanical cleanup
```

Preserve LaTeX commands, labels, citations, equations, and negative results unless a documented correction is authorized. Return the revision plus a concise change ledger using rule IDs.

### Generate

Define the section contract and evidence boundary before drafting. Draft claims and evidence-bearing paragraphs first; write title, abstract, contributions, and conclusion last. Use explicit placeholders only in a planning artifact, never in submission prose. Do not fabricate citations, experiments, novelty searches, reviewer reactions, or theorem proofs.

## Hard stops

Stop the affected rewrite or generation and report the issue when:

- authority versions conflict;
- the submission artifact is still a paper shell: core sections, abstract, or promised contributions are empty, or editorial placeholders/template identities remain;
- a novelty claim lacks a baseline or search boundary;
- a core claim has no identifiable evidence;
- a citation does not support its proposition;
- experiment factors or budgets are confounded;
- a proof changes objects, loses branches, or jumps from local evidence to a global conclusion;
- an approximation has no error/domain justification;
- humanization would require invented data, experience, authorship, or source support.

Continue collecting findings in audit mode so the user receives a complete diagnosis.

## Final declaration

Report each gate separately: authority, provenance, facts/notation, novelty, mathematics, quantitative reconciliation, evidence alignment, citations, versions, structure, composition, and mechanical integrity. A manuscript fails while any blocking `RES-*` rule remains unresolved. Never infer research correctness from compilation, formatting, citation count, lexical scans, or polished prose.
