# Commands, exits, and friction

All generated files are under `blind-course-postfix-v18/`. The installed Skill and the source file were read-only.

## Authoritative workflow

1. Source snapshot copy and SHA-256 comparison: shell exit `0`; source and snapshot matched at `b28dc286b43b7b581f95482d31d53be57a1d0cf743a0e890f58b1f3121fe934b`.
2. `python scripts/scan_humanize_chinese.py <source> --scene AUTO --format text`: exit `0`; four medium formula-caption candidates.
3. `python scripts/scan_humanize_chinese.py <source> --scene COURSE --format text`: exit `0`; same four medium candidates.
4. `python scripts/scaffold_humanize_short_patch.py create <snapshot> --scene COURSE --source-kind DOCUMENT --suggest-spans CLAUSE_AND_SENTENCE --focus-spec focus.v2.json --output selection.authoring.v3.json --format text`: exit `0`; `NO_HIGH_FINDINGS`, `suggestions=10`, explicit COURSE route.
5. `python scripts/scaffold_humanize_short_patch.py finalize <snapshot> --authoring selection.authoring.v3.json --output selection.final.v2.json --format text`: exit `0`; `FINALIZED hunks=7 selected=7`.
6. `python scripts/build_humanize_short_patch.py <snapshot> --selection-spec selection.final.v2.json --output patch.final.bundle.json --document-format TEX --format text`: exit `0`; bundle ID `88a9ab605f33354aa3081bab81c65514675817247feef887ad4d02b24cca3fc4`.
7. `python scripts/apply_humanize_short_patch.py <snapshot> --bundle patch.final.bundle.json --output review-authoritative --format text`: observed child exit `2`; `DELIVERY REVIEW`, structural validation `PASS`, unified validator `PASS`, coverage `PASS`, paired quality `PENDING_EXTERNAL_REVIEW`.
8. `python scripts/verify_humanize_short_patch.py review-authoritative --format text`: observed child exit `0`; integrity, current-policy replay, and coverage all `PASS`; delivery remains `REVIEW`.
9. Post-scan on `review-authoritative/candidate.review.tex`, AUTO and COURSE: each exit `0`; no candidate finding.

## Non-authoritative trial history

- `review/`: initial six-hunk trial reached hard invariants `PASS` but mechanical `REVIEW/2` because replacing `因此/于是` changed logical-relation marker counts.
- `review-amended/`: retaining the markers cleared the speech-act warning, but changing the four captions without changing their layout introduced four medium style-signal fingerprints; mechanical state remained `REVIEW/2`.
- The authoritative run therefore uses a new source-bound authoring bundle: it preserves the functional captions and removes only the four caption/formula line breaks, plus the bounded Chinese extremum shell.

## Friction and unresolved boundaries

- The scaffold found no high signal and therefore returned `NO_HIGH_FINDINGS/0`; the four medium candidates were bound through advisory spans, and the TeX-overlapping extremum caption was split with strict FOCUS spans.
- The terminal wrapper displayed expected nonzero applicator delivery as a generic failed script during trials. The authoritative invocation captured PowerShell `$LASTEXITCODE` explicitly: child exit `2`, which matches `result.json` and the `DELIVERY REVIEW exit=2` first line.
- No text location is unresolved. The remaining gate is external paired-quality review, which this local workflow cannot grant.
- Academic correctness, semantic entailment beyond encoded checks, author identity, and detector outcomes were not evaluated.
