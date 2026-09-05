# Usage

## Codex invocation

The callable skill name is `$baibai-aigc`.

Default behavior:

1. freeze the source facts, terms, structure, and claim strength;
2. read `prompts/baibaiaigc1.md` and `references/checklist.md`;
3. produce one short-block candidate;
4. compare it with the source;
5. accept, locally revert, or keep the source.

Round 2 is optional. Run it only after an explicit user request or explicit
approval of Round 1. It uses `prompts/baibaiaigc2.md` for minimal continuity and
register repair. Do not auto-advance to Round 2 from a history record.

## Recommended prompts

### One conservative candidate

```text
Use $baibai-aigc to produce one conservative candidate for this paragraph.
Preserve facts, numbers, terminology, citations, claim strength, and paragraph
role. Compare it with the source and keep the source if there is no clear gain.
```

### Compare with humanize

```text
Use $deai-academic-writing to freeze this paragraph. Generate candidate H with
$humanize-academic-chinese LIGHT and candidate B with $baibai-aigc Round 1,
both from the unchanged source. Accept at most one. Do not run serial rewrites
or optimize a detector score.
```

### Explicit Round 2

```text
Use $baibai-aigc Round 2 only on the approved Round 1 candidate. Make the
minimum continuity, reference, repetition, and register repairs; preserve all
semantic invariants and leave already natural sentences unchanged.
```

## File mode

For TXT/DOCX work, keep the authority source and every candidate separate.
`scripts/skill_round_helper.py` can prepare paths and manifests;
`scripts/aigc_records.py` can store provenance. A record never authorizes an
automatic next pass.

`scripts/run_aigc_round.py` is only for an explicitly requested command-line or
API batch run. Chat invocation does not require the user to provide an API key.

## Long academic documents

For long DOCX files, prefer FYADR for source hashes, editable-body mapping,
candidate review, and export gates. Use baibai only to provide a candidate for
selected body blocks. For CUMCM TeX papers, draft and audit content with
`$mcm-cup-standard-write` and `$deai-modeling-writing` before any style pass.
