# Academic Scene Router

## Contents

1. Routing order
2. Three scene contracts
3. Mixed documents
4. Ambiguity rules
5. Prohibited cross-scene transfers
6. Output contract

## 1. Routing order

Classify by the reader and document obligation, not by formula difficulty or
file extension.

```text
authority and segment provenance
-> intended reader
-> document purpose
-> strongest claim type
-> evidence object
-> required child skill
```

Ask these questions:

1. Is the reader trying to learn/review a known idea, execute/evaluate a model,
   or assess a new research contribution?
2. Does the document owe teaching clarity, engineering reproducibility, or
   journal-level novelty and inference?
3. Are its decisive objects exercises and derivations, data/code/protocols, or
   propositions/mechanisms/literature gaps?
4. Would failure mean learner confusion, an unreproducible engineering claim,
   or an unsupported contribution/theorem?

Path/folder labels may suggest a scene but never override the actual contract.

## 2. Three scene contracts

### NOTE: course notes and worked derivations

Route to `$deai-course-notes` when the main obligation is to teach, review, or
solve established material. Typical artifacts:

- lecture and revision notes;
- textbook chapters;
- worked exercises and exam solutions;
- formula summaries with explanation;
- OCR/source reconstruction plus generated explanation;
- learning strategy notes.

Do not require a literature gap, original contribution, held-out validation,
or journal abstract. Do require correct objects, domains, theorem conditions,
source identity, and honest heuristic strength.

### MOD: modeling and engineering simulation

Route to `$deai-modeling-writing` when claims depend on data roles, parameters,
code, simulation, optimization, solver settings, scenarios, sensitivity,
benchmarks, or operational decisions. Typical artifacts:

- mathematical-modeling competition papers;
- simulation and numerical-analysis reports;
- algorithm benchmark and experiment plans;
- parameter calibration and sensitivity studies;
- engineering API/README claims tied to implementation;
- model-based policy or design recommendations.

Allow justified approximation. Require parameter provenance, model-code
equivalence, protocol identity, precision calibration, and explicit untested
dimensions. Do not treat finite simulation as theorem proof.

### RES: research and journal manuscripts

Route to `$deai-research-writing` when the main obligation is a new scholarly
contribution, advanced theoretical claim, research mechanism, journal method,
or literature synthesis. Typical artifacts:

- journal/arXiv manuscripts;
- theoretical-method papers;
- proof-heavy original research;
- research-level algorithm papers;
- literature reviews and source-to-project research notes;
- reviewer response and contribution revision.

Require precise novelty, proposition-level evidence, theorem applicability,
object identity, reversible decisive transformations, and selective structure.
Do not inherit classroom mnemonics or engineering approximation as proof.

## 3. Mixed documents

Do not choose one average voice for a mixed file. Build a segment map:

| Segment | Current function | Scene | Authority | Editable? | Child skill |
|---|---|---|---|---|---|
| lines/section | note/model/report/research/audit/source | NOTE/MOD/RES/N-A | path | yes/no | skill |

Common mixed forms:

- textbook question (`SRC`) + generated solution (`NOTE`);
- modeling paper (`MOD`) + proof appendix (`RES` for proof gates only);
- research README (`RES`) + reproduction instructions (`MOD`);
- current engineering guide (`MOD`) + archived proposals (`N-A/HIST`);
- literature quotation (`SRC`) + research synthesis (`RES`).

Apply one shared fact/version lock before segment-specific style work. A child
skill may borrow another scene's correctness gate for a local object, but may
not replace the segment's primary writing contract.

## 4. Ambiguity rules

Use the strongest observable obligation:

| Ambiguity | Decision |
|---|---|
| Hard mathematics in a textbook | NOTE; difficulty alone does not create a journal paper |
| Journal paper with simulations | RES primary; invoke MOD gates for protocol and numerical claims |
| Modeling competition paper with a theorem | MOD primary; invoke RES proof gates for the theorem only |
| Research plan with no publishable prose | RES planning segment; do not rewrite as a finished paper |
| Engineering README for a research algorithm | MOD for operational claims, RES for novelty/mechanism claims |
| No reader/purpose information | infer from authority structure; if a material choice remains, ask one concise question |

Never use filename words such as `paper`, `report`, `main`, or `notes` alone.

## 5. Prohibited cross-scene transfers

- Do not impose novelty and literature-gap requirements on ordinary notes.
- Do not remove useful teaching steps merely to imitate journal compression.
- Do not use classroom intuition, option clues, or mnemonics as model evidence
  or research proof.
- Do not let “engineering approximation” excuse missing parameter source,
  unknown error, or manuscript-code mismatch.
- Do not call modeling weight sensitivity theoretical robustness.
- Do not force research paragraphs into a uniform claim/evidence/boundary grid.
- Do not use journal hedging to make an incorrect classroom derivation look
  sophisticated.
- Do not transfer audit release language into any public academic scene.

## 6. Output contract

Before editing, record:

```text
Authority:
Reader:
Primary scene:
Segment exceptions:
Child skill:
Shared CORE gates:
Scene-specific rules:
Rules explicitly not activated:
```

If the request is a corpus-wide policy or an unknown/mixed document, keep this
router active. For a stable single scene, invoke the selected child skill and
do not load the other two scene libraries.
