---
name: deai-academic-writing
description: Route Chinese academic-writing audits, rewrites, generation, and multi-tool de-AI workflows to the correct scene-specific standard while enforcing shared evidence, provenance, mathematical-integrity, and semantic-drift gates. Use when the document scene is unknown or mixed; for course notes, worked derivations, mathematical modeling, CUMCM papers, engineering simulation, journal research, or technical reports; and whenever the user asks how to combine baibaiAIGC, humanize-academic-chinese, AI-Cleaner, AI_paper, FYADR, BypassAIGC, or GankAIGC. Dispatch content work to the scene skill and keep detector-oriented tools advisory.
---

# De-AI Academic Writing

Use this skill as the common integrity layer and scene router. Do not apply one
uniform prose standard to every academic artifact.

## Core principle

Treat "less AI-like" as an evidence and composition problem, not a banned-word exercise. Preserve valid technical content. Remove language only when it is redundant, unsupported, structurally mechanical, or misplaced.

Do not derive academic rules from chat messages. Use the manuscript, its sources, tables, equations, figures, and methods as authority.

## Multi-tool de-AI requests

When the user asks to combine local AIGC tools, always read
[aigc-tool-orchestration.md](references/aigc-tool-orchestration.md). The tools
have overlapping prompts but different responsibilities; directory count is
not independent capability count.

Never send one passage through several full-document rewriters in series. Use
this order instead:

```text
source and evidence lock -> scene-specific content draft/audit
-> style diagnosis -> parallel local candidates from the same baseline
-> invariant comparison and human selection -> final scene audit
```

Use at most one rewrite candidate as the accepted base for a passage. A second
tool may diagnose or produce an alternative from the frozen source, but it may
not automatically rewrite the first tool's output. Detector scores and lexical
counts are review signals, never optimization targets or evidence of authorship.

For a CUMCM A/B/C paper, use `$mcm-cup-standard-write` as the competition genre
and evidence layer, `$deai-modeling-writing` for model/code/result integrity,
and `$humanize-academic-chinese` only for a final `MODELING` style diagnosis and
minimal patch. Do not use colloquial expansion to manufacture the missing
public reasoning between problem and model choice.

## Scene dispatch

Always read [scenario-router.md](references/scenario-router.md) before a full
audit, rewrite, or generation task. Route stable single-scene work to exactly
one child skill:

| Scene | Child skill | Primary contract |
|---|---|---|
| Course notes, textbook chapters, worked derivations, exam solutions | `$deai-course-notes` | teach clearly; preserve useful explanation without journal theater |
| Mathematical modeling, simulation, optimization, engineering analysis | `$deai-modeling-writing` | align data, parameters, equations, code, protocols, and claims |
| Journal papers, theoretical research, advanced method papers, literature synthesis | `$deai-research-writing` | make selective novelty and proof/evidence claims at publication level |

`$mcm-cup-standard-write` is a domain layer inside the modeling scene, not a
fourth academic scene. Activate it only for CUMCM-style A/B/C competition work.

For mixed files, classify segments and apply each child skill only to its own
segment. Keep the shared fact/provenance lock across the whole document.

Read [scenario-rule-map.md](references/scenario-rule-map.md) when deciding which
base rules may activate. Read [scenario-case-map.md](references/scenario-case-map.md)
when selecting evidence examples. Read [scenario-pattern-map.md](references/scenario-pattern-map.md)
and [scenario-playbook-map.md](references/scenario-playbook-map.md) before
reusing a base transformation or genre manual. `CORE` rules are shared integrity
gates, not a generic writing voice.

## Load references

Always read [rules.md](references/rules.md) for rule IDs and severity before editing. Load additional references by task:

| Need | Read |
|---|---|
| Full document diagnosis or scoring | [diagnostic-matrix.md](references/diagnostic-matrix.md) |
| Genre-specific generation/rewrite | [genre-playbooks.md](references/genre-playbooks.md) |
| Sentence/paragraph transformation | [rewrite-patterns.md](references/rewrite-patterns.md) |
| Fact, math, provenance, version, citation validation | [validation-gates.md](references/validation-gates.md) |
| Source-derived examples and failure modes | [cases.md](references/cases.md) |
| Copy-ready model constraints and prompt contracts | [system-prompt-contract.md](references/system-prompt-contract.md) |

On Windows, explicitly read all selected files as UTF-8; do not accept mojibake as source text. Do not load every reference for a small local edit, but load the five diagnostic/genre/rewrite/validation/case references for a full manuscript audit or generation task. Load the system-prompt contract when the user wants reusable instructions for another model.

For a mathematical proof, textbook chapter, answer key, modeling derivation, or
claim involving an envelope/locus/global sign, always load `validation-gates.md`,
`rewrite-patterns.md`, and `cases.md` in addition to `rules.md`. These tasks
require object, domain, reversibility, and proof-coverage checks before style.

## Workflow

### 1. Identify the document contract

Establish document type, intended reader, central claim, available evidence, required terminology/equations/citations, and whether the task is generation, audit, or rewrite. If the venue or evidence boundary is unknown, infer conservatively and state the assumption. Do not invent a target journal or style guide.

If one file mixes genres (for example current README, historical plans, architecture atlas, QA ledger, demo tutorial, and acceptance report), segment it first and apply the relevant playbook to each segment. Do not force one voice or acceptance criterion over the whole file.

Classify the source segments before style work:

- author-generated argument;
- assistant-generated explanation or solution;
- inherited problem statement/data/table;
- quotation or translation;
- OCR/transcription;
- editorial instruction, audit note, or version residue.

Only attributable prose supports style conclusions. Preserve inherited source text unless the task authorizes editing it.

### 2. Read the whole argument

Read the complete document before sentence-level rewriting. Build a compact map:

```text
section -> purpose -> main claim -> evidence -> limitation -> dependency
```

Identify duplicate sections, version residue, editor instructions, and contradictions. Do not polish a sentence that should be deleted or moved.

### 3. Lock facts and evidence

Create a fact lock for numbers, units, sample sizes, parameter values, equations, symbol definitions, citations, reported positive/null/negative results, scope conditions, and known limitations.

Never change a fact merely to improve flow. Flag contradictions before stylistic revision. If evidence is missing, weaken or remove the claim; do not fabricate support.

### 4. Diagnose in four passes

Apply the rules in this order:

1. **Document**: section responsibilities, duplicated conclusions, missing synthesis.
2. **Argument**: claim-evidence alignment, causal strength, external validity, method motivation.
3. **Paragraph**: one dominant job, evidence position, transition, repeated disclaimer.
4. **Sentence**: vague words, false contrasts, mechanical lists, overload, meta-writing.

Record findings with rule IDs. Prioritize `MUST` before `SHOULD`; do not spend time varying sentence length while a result is unsupported.

Within each pass, use this order:

```text
contradiction -> provenance -> evidence strength -> mathematical validity
-> section responsibility -> paragraph hierarchy -> sentence style -> cosmetic polish
```

Do not allow a lower-priority improvement to hide or normalize a higher-priority failure.

### 5. Rewrite around objects and evidence

Prefer concrete subjects such as the sample, model, parameter, experiment, figure, or observed mechanism. Replace generic management nouns with the research object and action.

Use this paragraph pattern only when it fits the evidence, not as a universal template:

```text
claim or observation -> evidence -> interpretation -> necessary boundary
```

Allow paragraphs to have unequal length. Give decisive evidence more space and routine transitions less space. Do not force every paragraph to end with a summary.

For mathematical or algorithmic prose, preserve three levels:

1. state the object and decisive idea;
2. show the transformation that changes the conclusion;
3. compress routine reversible algebra or move it to an appendix.

Never compress a theorem condition, sign choice, exceptional case, factorization, convergence argument, or experimental contrast that the conclusion depends on.

### 6. Preserve useful AI strengths

Retain these features when supported:

- explicit distinction between calibration and independent validation;
- honest reporting of failed robustness or negative results;
- clear separation of method, benchmark post-processing, and external validity;
- parameter roles, evidence levels, and applicability conditions;
- reproducible input/output definitions and audit trails.

Compress repeated explanations; do not delete the underlying boundary.

### 7. Validate after rewriting

Check that facts match the draft, strong adjectives and causal verbs have evidence, sections perform distinct jobs, terminology stays stable, limitations are not copied into every section, transitions name the continued object, rhythm follows argumentative load, and no citation/result/confidence level was invented.

Do not use a keyword-zero result, clean compilation, completed transcription,
or closed audit as a substitute for this validation. Name each passed property
separately. For empirical values, distinguish storage precision from inferential
precision. For mathematical claims, require complete domain coverage and
reversible transformations before declaring correctness.

## Output modes

### Audit

Return a severity-ordered table:

| Rule | Location | Problem | Why it matters | Revision action |
|---|---|---|---|---|

Then give a document-level diagnosis and a prioritized revision sequence.

For a full manuscript, include:

1. source/provenance map;
2. fact and notation lock;
3. blocking contradiction list;
4. claim-evidence matrix;
5. section responsibility map;
6. rule-ID findings;
7. representative rewrites;
8. unresolved evidence requests;
9. pass/fail gate summary.

Map rule severity to audit severity as follows:

- `Blocking`: unresolved contradiction or any `MUST` issue that invalidates interpretation/reproducibility;
- `Major`: other `MUST` evidence, terminology, or section-responsibility failure;
- `Moderate`: `SHOULD` composition or style failure;
- `Minor`: optional local polish with no effect on claims.

### Rewrite

Provide the revised text, followed by a short change ledger containing rule IDs and unresolved evidence issues. Preserve LaTeX commands, labels, citations, equations, and Markdown structure unless the user requests structural changes.

For long documents, revise in this order: authority/version cleanup, section movement/deletion, paragraph reconstruction, sentence rewrite, terminology consistency, TeX/Markdown cleanup. Keep a change ledger for deleted duplicate claims and relocated boundaries.

### Generate

Define the section contract and evidence boundary before drafting. Draft the central claim and evidence-bearing paragraphs first; write the abstract and conclusion after the body. Do not prefill every conventional heading if the content does not require it.

Before delivery, run the genre playbook and all applicable validation gates. A generated paper must not contain planning language, placeholder evidence, invented citations, unverified numerical claims, or a section whose only purpose is to make the outline look complete.

### Local sentence repair

Read enough surrounding paragraphs to identify the sentence's function and evidence. Apply a rewrite pattern, then check that the local improvement does not strengthen the claim, change the term, delete a necessary condition, or duplicate a boundary elsewhere.

## Hard failures

In audit mode, continue collecting all hard failures so the user receives a complete diagnosis. In rewrite or generation mode, stop the affected rewrite and flag the issue instead of silently writing past it when:

- two source passages report contradictory values;
- a claim has no identifiable evidence;
- a citation cannot support the attached proposition;
- a parameter is called both fixed and varied;
- a local simulation is written as a real-world causal fact;
- "humanization" would require fabricating experience, data, or personal authorship.

## Final quality gate

The output passes only if it is more precise and less repetitive while preserving or improving evidentiary honesty. A text that merely removes transition words, inserts colloquialisms, or varies sentence length at random does not pass.
