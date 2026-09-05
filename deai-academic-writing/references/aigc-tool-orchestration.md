# Local AIGC Tool Orchestration

## Purpose

This reference coordinates the local writing tools under
`C:\Users\Lenovo\.codex\skills\AIGC`. It is a quality workflow, not a promise
to evade a detector. The final standard is that the author can defend the
facts, modeling choices, intermediate judgments, equations, code, and results.

`$aigc-writing-router` is the portfolio front door. Once it classifies an
academic document, this Skill owns the academic scene contract and dispatches
whole responsibilities to the scene children below; the portfolio router does
not duplicate their rules.

Audit baseline: 2026-08-15. Re-audit a project after replacing its directory or
changing its prompts. Only directories with a valid `SKILL.md` are directly
invocable Codex skills; the other directories are standalone applications.

## Capability map

| Local item | Type | Useful capability | Recommended role | Do not use it for |
|---|---|---|---|---|
| `aigc-writing-router` | Codex Skill | Whole-portfolio scene plan, complete-role assignment, candidate provenance, workbench routing | Common entry before multi-tool work | Writing content or copying child rules into a composite prompt |
| `humanize-academic-chinese` | Codex Skill | Protected-span rewrite, scene routing, strict lexical scan, TeX/long-document evidence, minimal patch | Final style diagnosis and tightly scoped repair | Determining academic correctness or forcing every strict hit into a synonym |
| `baibaiAIGC` | Codex Skill | Short-block alternative phrasing; first pass can expose overly compact or uniform syntax | Optional candidate B from the frozen baseline | Mandatory second pass on modeling prose; serial rewriting after another humanizer |
| `humanizer` | Codex Skill | Complete general English and nonacademic technical-prose edit with fact preservation | Primary editor outside academic scenes | Academic evidence, TeX/math/result files, or a second pass after an academic editor |
| `Humanizer-zh-main` | Codex Skill | Complete general Chinese edit with a Chinese pattern set and source-fact lock | Primary editor for nonacademic Chinese prose | CUMCM, research, course derivations, technical results, or TeX |
| `academic-humanizer-main` | Imported Codex Skill | English academic audit, rewrite, claim-evidence calibration, and equation/number/citation checks | Primary style editor for `academic-en` | Chinese or CUMCM style transfer |
| `humanizer_academic-main` | Imported Codex Skill | English medical author profile and two-pass manuscript edit | Primary style editor for `medical-en` | Chinese, nonmedical templates, or CUMCM |
| `patina-7.0.0` | Imported Codex Skill | Multilingual pattern, semantic-anchor, MPS, and fidelity audit | Read-only academic reviewer on a prose copy; explicit general-prose candidate | Raw authority TeX or automatic candidate selection |
| `humanizer-main(brandonwise)` | Imported Codex Skill | English CLI pattern and statistical report | Explicit general-English editor or advisory English reviewer | Chinese, academic correctness, or TeX |
| `humanizer-skill-0.1.0` | Imported Codex Skill | Five complete voice-profile routes | Explicit general-English candidate | Academic evidence or citations |
| `humanize-main` | Imported multi-Skill package | Chinese copy candidate lab, `ai-check` report, and source-bound English editor | Explicit general-copy experiments and read-only reports | Academic, mathematical, or TeX authority files |
| `AI-Cleaner` | Standalone app | Local heuristic report, sentence-level risk hints, diff UI, iterative LLM workflow | Detector-like diagnostic sandbox; report-only by default | Automatic NLP post-processing of formulas, terminology, citations, or final modeling prose |
| `AI-content-detector-Humanizer-main` | Standalone app | English PDF sentence analysis and annotated-PDF output | Advisory English PDF workbench | CUMCM Chinese or automatic authorship verdicts |
| `AI_paper` / Paper Research Society | Standalone desktop app | Paragraph annotations, grammar checks, correction UI, model routing, local workspace | Grammar/format review and manually selected paragraph suggestions | Its generic logic/full-polish prompts as an authority for missing reasoning or evidence |
| `fuck-your-ai-detection-rate-main` / FYADR | Standalone app | Source hashes, protected regions, candidate fallback, DOCX body map, per-block review, export gates | Preferred long-DOCX review and provenance harness | Treating a passed local check as proof of truth, originality, or detector outcome |
| `BypassAIGC` | Standalone app | Older two-stage paragraph polish/enhance workflow | Legacy comparison only when an existing installation depends on it | Running before or after GankAIGC; its expand-and-replace enhancement pass on a technical final |
| `GankAIGC-2.1.0` | Standalone service | Newer multi-user workflow, BYOK, project history, Zhuque feedback loop, DOCX/Markdown export | Optional UI deployment or external-feedback experiment | Default local editor; repeated optimization against a detector score |
| `ai-humanizer-main` | Standalone API client | Raycast/Rephrasy clipboard flow | Black-box interaction demo | Sensitive, academic, mathematical, or authority text |
| `humanize-text` | Standalone research pipeline | Translation chain, multiple engines, and step trace | Research baseline | TeX, citations, or fact-dense authority text |
| `humanize-ai-main` | Source library | Transformation use case, low-confidence filtering, change trace, and cache interface | Implementation reference only | Direct production editing |
| `humanize-main(Tiany)` | Incomplete import | Documents a candidate/repair loop | Design record only | Execution; the runtime files are absent |

## What is actually independent

The twenty-one registered directories do not provide twenty-one interchangeable editing opinions. They
form a portfolio of scene owners, candidate engines, general editors, document
governors, and manual workbenches.

- `baibaiAIGC` round 1 and AI-Cleaner's `weipu` path share the same expansion,
  phrase-substitution, and mild colloquialization family.
- `baibaiAIGC` round 2 and AI-Cleaner's `zhuque` path share the same
  redundancy/slow-information/"expert explanation" family.
- BypassAIGC and GankAIGC share the same polish/enhance architecture and much
  of the same default prompt lineage. GankAIGC is the later operational system;
  do not count both as separate quality passes.
- AI-Cleaner bundles a rule-based `humanize-chinese` detector/rewrite engine.
  That engine optimizes heuristic features such as phrase hits, sentence-length
  variance, and perplexity. It is independent as a detector implementation,
  not as an academic truth oracle.
- FYADR contributes the most independent value at the document-control layer:
  it retains the source as authority, admits the original as a candidate, and
  blocks unsafe DOCX export when its evidence chain drifts.

## Default pipeline

### 1. Freeze the source contract

Record the authority file and preserve:

```text
numbers and units | equations and symbols | citations and labels
negation and modality | model assumptions | parameter sources
code/result correspondence | section and paragraph roles
```

For a long DOCX, FYADR may supply the snapshot, body map, hashes, candidate
comparison, and export gate. For TeX/Markdown, use the domain skill's ledgers
and the humanize protected-span workflow.

### 2. Build or repair content with one domain route

| Document | Primary content route |
|---|---|
| CUMCM A/B/C paper | `$mcm-cup-standard-write`, then `$deai-modeling-writing` integrity gates |
| Other modeling/simulation/optimization report | `$deai-modeling-writing` |
| Course note or worked derivation | `$deai-course-notes` |
| Journal/research paper | `$deai-research-writing` |
| Mixed or unclear academic file | `$deai-academic-writing` segment router |
| General Chinese prose without specialist evidence claims | `$humanizer-zh` as the complete editor |
| General English or nonacademic technical prose | `$humanizer` as the complete editor |

Do not start with a ban list. A modeling draft first needs the public,
reader-facing judgment that supports its choices: the observed feature, the
failed or weaker alternative, the constraint or data fact that matters, and
the consequence of the chosen formulation. This is not hidden private chain of
thought; it is the argument and reproducible rationale owed to the reader.

### 3. Diagnose style before rewriting

Use `$humanize-academic-chinese` in `DIAGNOSE` mode with the resolved scene.
Classify each finding as:

- content gap: return to the domain skill;
- style shell: eligible for a local patch;
- protected or functional language: keep with a specific reason;
- ambiguous: leave unresolved for human review.

AI-Cleaner or AI_paper may provide a second diagnostic report. Their counts and
scores only prioritize reading; a hit is not an automatic edit instruction.

### 4. Branch candidates from the same baseline

For a passage that genuinely needs rewriting, create no more than two
candidates:

- Candidate H: `$humanize-academic-chinese`, normally `LIGHT` or a minimal
  `PATCH`; use `BALANCED` only for a paragraph with a structural problem.
- Candidate B: `baibaiAIGC` first-pass prompt only, limited to a short ordinary
  prose block whose facts and terms are frozen.

Generate H and B from the same frozen source. Never use `source -> H -> B` or
`source -> B -> AI-Cleaner NLP -> H`. Prefer the unchanged source when neither
candidate is a clear improvement.

### 5. Select by invariants and reading quality

Reject a candidate if it changes any protected item, strengthens or weakens a
claim, invents a bridge, deletes a necessary condition, changes a model choice,
or shifts a paragraph's job. Then compare the survivors on:

```text
specific subject and action
visible but non-mechanical judgment
natural sentence boundaries
unequal explanation density where the argument demands it
disciplinary register
absence of editor/chat/meta language
```

The comparison is against the frozen source, not against a detector score. A
teammate should be able to explain why each accepted sentence exists.

### 6. Re-run domain and document gates

After selecting candidates:

1. Re-run the scene-specific fact, equation, code, citation, and result checks.
2. Re-run the humanize lexical/style scan as a diagnostic.
3. Compile TeX or validate DOCX structure.
4. Inspect the actual figures, tables, equations, references, and page flow.
5. Record unresolved items. Do not call a mechanical pass a quality clearance.

## CUMCM-specific route

Use this route for a competition paper or template-derived manuscript:

```text
problem statement + data + code + result artifacts
-> $mcm-cup-standard-write evidence/genre draft
-> $deai-modeling-writing model-code and claim gates
-> $humanize-academic-chinese DIAGNOSE, scene=MODELING
-> local PATCH on confirmed style shells
-> modeling audit + TeX compile + page inspection
```

在这条链上必须额外建立组合器回执，不得以“调用过一个 Skill”代替完整交接：

```text
content-owner receipts (scene + evidence ledgers)
-> candidate receipt (candidate hash + hard-gate results)
-> reviewer receipt (review target hash + native/read-only report)
-> workbench receipt (mapping/diff/export evidence, when selected)
-> human-decision receipt
```

使用 `$aigc-writing-router/scripts/orchestrate_portfolio.py` 的
`attach-role`、`waive-role` 和 `select` 命令登记这些事件。每个回执必须符合
`aigc-role-receipt/v1`，证据条目提供文件路径和 SHA-256；组合器会重新计算哈希并拒绝
缺项、候选父子链、硬门未通过、TeX 代理冒充完整稿和回执漂移。缺少回执时最高只能报告
`MECHANICAL_PASS_HUMAN_PENDING`；能力不可用时记录具体 fallback，不能把它写成完整协同。

The middle of a modeling argument should not be a fixed sequence of labels such
as "difficulty -> baseline -> deficiency -> alternatives -> choice". Write the
actual episode that occurred. Depending on the problem, this may be a physical
constraint excluding a root, a baseline violating a global condition, a
parameter change switching the first event, a counterexample defeating a
shortcut, or a computation exposing a local mechanism. Different subproblems
should therefore have different paragraph shapes and explanation lengths.

For CUMCM prose, do not run baibai round 2 by default. Its instructions favor
redundancy, colloquialization, looser logical links, and an artificial
"thinking aloud" effect. These can reduce technical density and make the
paper less like the award-paper register learned by
`$mcm-cup-standard-write`. Use round 1 only as an alternative for a confirmed
local syntax problem, then select against the source.

## Standalone application usage

### AI-Cleaner

Use it when an interactive diff and local risk report are useful. In an
academic/modeling workflow, set the practical policy to report first, one LLM
candidate at most, and manual adoption. Avoid its automatic rule-based rewrite
on the canonical paper: the bundled engine can choose variants by perplexity
and deliberately randomize sentence lengths, which is not a semantic-quality
criterion.

### AI_paper

Use paragraph annotations, grammar correction, citation/format hints, and its
history workspace. Prefer `light` or a manually selected paragraph operation.
Do not let `logic`, `full`, or `academic vocabulary` prompts automatically add
transitions, missing reasoning, "significant" results, or expected-goal
language; those changes require source evidence. Its local scanner also has
conflicting heuristics around transition density, so its score is advisory.

### FYADR

Use it for long TXT/DOCX when layout preservation and auditable acceptance
matter. Keep the original as an eligible candidate, review every changed block,
and export only after the source/snapshot/body-map/manifest/review hashes agree.
This application can host candidates generated by the approved domain/style
route; its own multi-round prompts are optional, not mandatory.

### BypassAIGC and GankAIGC

Choose at most one. Prefer GankAIGC when its deployment, user/project history,
or external Zhuque feedback is specifically needed. Treat BypassAIGC as the
older workflow. In either application, avoid `polish + enhance` as a default:
the enhance prompt expands phrases and systematically replaces vocabulary,
which can undo a sound academic edit. Never loop until an external score
crosses a target; inspect a single candidate against the frozen source.

## Direct invocation recipes

### CUMCM draft or revision

```text
Use $deai-academic-writing for this CUMCM manuscript. Route content through
$mcm-cup-standard-write and $deai-modeling-writing, then run
$humanize-academic-chinese in MODELING/DIAGNOSE mode and apply only verified
local patches. Preserve TeX, equations, numbers, citations, and model-code
equivalence. Do not run serial full rewrites.
```

### General academic paper

```text
Use $deai-academic-writing to classify the scene, lock facts and citations,
repair the argument with the selected scene skill, and then use
$humanize-academic-chinese for a LIGHT final style pass. Return unresolved
evidence gaps instead of inventing bridges.
```

### General Chinese prose

```text
Use $aigc-writing-router to confirm this is nonacademic general Chinese, then
let $humanizer-zh perform one complete fact-preserving edit. Keep the source as
an eligible candidate and do not send the result through an academic editor.
```

### General English or nonacademic technical prose

```text
Use $aigc-writing-router to confirm that the text has no academic evidence,
modeling, or TeX obligations, then let $humanizer perform the complete edit.
Reclassify before editing if formulas, result claims, or research evidence are
material to the document.
```

### Compare baibai with humanize

```text
Freeze this paragraph. Produce candidate H with
$humanize-academic-chinese LIGHT and candidate B with baibaiAIGC round 1, both
from the unchanged source. Compare facts, claim strength, terminology,
paragraph role, disciplinary register, and reading quality. Accept at most one;
keep the source if neither is clearly better. Do not run baibai round 2.
```

## Hard stops

- No serial full rewrites across humanize, baibai, AI-Cleaner, AI_paper, Gank,
  or Bypass.
- No automatic adoption based on AIGC percentage, perplexity, burstiness,
  sentence-length variance, or banned-word count.
- No invented personal experience, failed experiment, model comparison,
  parameter source, citation, result, limitation, or "human hesitation".
- No deliberate errors, awkward translation, random fragments, or colloquial
  filler as proof of human style.
- No claim that a local mechanical check establishes human authorship,
  originality, academic correctness, or acceptance by an external service.
