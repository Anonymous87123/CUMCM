---
name: baibai-aigc
description: Produce a conservative alternative rewrite for Chinese academic or technical prose while preserving facts, terminology, structure, and claim strength. Use when the user explicitly asks for baibaiAIGC, wants a same-source comparison against another style editor, or needs a short local passage repaired for uniform syntax. Round 1 is the default candidate pass; Round 2 is optional, explicit, and limited to final continuity repair. Do not use as an automatic detector-evasion loop or as the content authority for mathematical-modeling papers.
---

# Baibai AIGC Candidate Editor

Use this skill as a candidate editor, not as a detector-score optimizer. Its
output remains a proposal until it has been compared with the frozen source.

## Required files

- Default candidate pass: [baibaiaigc1.md](prompts/baibaiaigc1.md)
- Optional final repair: [baibaiaigc2.md](prompts/baibaiaigc2.md)
- Acceptance gate: [checklist.md](references/checklist.md)

Read the selected prompt and the checklist completely before rewriting.

## When to use

Use this skill when:

- the user explicitly names baibaiAIGC or `$baibai-aigc`;
- a short academic/technical passage is overly compressed or syntactically
  uniform and the user wants an alternative rendering;
- `$deai-academic-writing` requests candidate B from a frozen baseline.

Do not activate it merely because a paper should sound natural. Route the
document's academic content first. For CUMCM work, `$mcm-cup-standard-write`
and `$deai-modeling-writing` own the modeling argument; this skill may only
suggest a local prose alternative.

## Invariants

Before editing, freeze:

```text
facts and conclusions | numbers and units | terms and symbol names
equations, TeX commands, labels, and citations | negation and modality
causal/comparative direction | heading, list, and paragraph roles
```

Never add a fact, model rationale, experiment, citation, result, limitation,
personal experience, or author's hesitation. Do not delete a conclusion merely
because it begins with a common transition. Do not manufacture errors,
fragments, colloquial fillers, or awkward translation.

## Round policy

Each invocation performs at most one pass.

### Round 1: default candidate

Read `prompts/baibaiaigc1.md`. Use it for a short local passage, but subordinate
its vocabulary suggestions to the invariants and disciplinary register.
Systematic synonym replacement is never mandatory. If the source is already
natural, retain it.

Round 1 output is a candidate, not an intermediate that must proceed to Round
2. In a combined workflow, compare it with the unchanged source and any
`$humanize-academic-chinese` candidate before accepting it.

### Round 2: optional final repair

Run Round 2 only when the user explicitly requests it or explicitly approves
it after reviewing Round 1. A record that Round 1 exists is not sufficient
authorization. Read `prompts/baibaiaigc2.md` and make only necessary continuity,
reference, repetition, and register repairs.

Do not run Round 2 by default for mathematical modeling, engineering,
proof-heavy, legal, or medical prose. Never treat redundancy, weaker logical
links, colloquialization, or "thinking aloud" as human style.

## Chunking

- Preserve the original paragraph order and roles.
- Process natural paragraphs separately.
- If a paragraph exceeds 850 Chinese characters, split only at complete
  sentence boundaries.
- Never split inside TeX, equations, code, citations, identifiers, quoted
  material, or a numbered item.
- Restore chunks to their original paragraph positions.

For a long file, keep the source and candidate as separate files. Do not
overwrite the authority manuscript until the candidate passes review.

## Candidate acceptance

Apply `references/checklist.md`. Compare against the frozen source, not against
an AIGC score. Reject or locally revert a candidate when it:

- changes an invariant;
- adds an unsupported explanation or removes a necessary condition;
- weakens the academic register;
- replaces stable terminology for surface variation;
- makes the passage longer without making an existing relation clearer;
- turns a specific modeling action into generic "expert explanation" prose.

At most one rewrite candidate may become the accepted base for a passage. Do
not automatically pass a baibai result into another full rewriter.

## Optional records

For file-based work, `scripts/skill_round_helper.py` and
`scripts/aigc_records.py` may maintain `finish/aigc_records.json` and
`finish/intermediate/` artifacts. Records provide provenance; they do not make
Round 2 mandatory.

Recommended fields:

```json
{
  "document": {
    "origin_path": "origin/document.txt",
    "rounds": [
      {
        "round": 1,
        "prompt": "prompts/baibaiaigc1.md",
        "input_path": "origin/document.txt",
        "output_path": "finish/intermediate/document_round1.txt",
        "manifest_path": "finish/intermediate/document_round1_manifest.json"
      }
    ]
  }
}
```

In chat mode, perform the rewrite directly; do not ask for an external API key.
Use `scripts/run_aigc_round.py` only when the user explicitly requests the
script/API batch mode.

## Output

For direct text, return the candidate and a concise unresolved-risk note unless
the user requests body-only output. For file work, write the candidate to a new
file and report its path. Do not call it a final human-quality clearance.
