# Base Rule Scene Ownership

Every base rule has one owner. `CORE` is the shared integrity layer; `NOTE`,
`MOD`, and `RES` are scene owners. Ownership prevents a rule from silently
becoming a universal prose standard.

## Ownership summary

| Owner | Count | Meaning |
|---|---:|---|
| CORE | 62 | Evidence, provenance, correctness, terminology, and composition gates shared when relevant |
| NOTE | 6 | Course-note teaching and textbook integration rules |
| MOD | 6 | Modeling evidence, precision, sensitivity, and audit-placement rules |
| RES | 6 | Research abstraction, novelty framing, syntax, and abstract rules |
| Total | 80 | Each rule appears once |

## CORE (62)

| Rules | Activation boundary |
|---|---|
| `EVD-01`-`EVD-11` | Activate for claims, sources, contradictions, provenance, and workflow status in any scene |
| `LEX-01`, `LEX-02`, `LEX-04`-`LEX-06`, `LEX-08`, `LEX-09` | Activate when the named lexical failure occurs; do not ban literal words without context |
| `SYN-01`-`SYN-05`, `SYN-07` | Shared sentence-function gates; severity follows scene |
| `LOG-02`, `LOG-04`-`LOG-06` | Shared object continuity, relation, information exit, and editorial-boundary gates |
| `PAR-01`, `PAR-02`, `PAR-04`, `PAR-05` | Shared paragraph responsibility; NOTE may tolerate more explanation, not more duplication |
| `DOC-01`, `DOC-02`, `DOC-04`, `DOC-06`, `DOC-07` | Shared section, version, and conclusion authority |
| `RHY-01`-`RHY-03` | Shared evidence-weighted rhythm; actual compression target is scene-specific |
| `VOI-01`-`VOI-03` | Shared role and publication-voice boundary |
| `MTH-01`-`MTH-19` | Activate whenever the mathematical object occurs; correctness is never relaxed by scene |

CORE rules must not be used as a generic prose template. For example,
`PAR-01` does not require a classroom explanation and a journal result paragraph
to have the same length or internal shape.

## NOTE (6)

| Rule | Why NOTE owns it | Prohibited use |
|---|---|---|
| `PAR-06` | Main-text example economy depends on teaching level | Do not limit research evidence to “one example and one counterexample” |
| `DOC-08` | Incremental textbook/manual expansion creates repeated routes | Do not treat every journal revision as textbook chapter growth |
| `DOC-09` | Inherited question, OCR, official answer, and generated solution coexist in teaching files | Still apply provenance mapping in other scenes through CORE `EVD-08` |
| `DOC-10` | Chapter-family reintegration is a book-level responsibility | Do not require chapter prerequisites in an ordinary modeling report |
| `RHY-04` | Teaching derivations must expose hierarchy between idea and routine algebra | Research proof detail is governed by RES rules and CORE math gates |
| `RHY-05` | Learner-facing derivation weight differs from journal proof compression | Do not use it to justify omitting research proof obligations |

## MOD (6)

| Rule | Why MOD owns it | Prohibited use |
|---|---|---|
| `EVD-12` | Display precision versus parameter identification is central to modeling | Do not infer that all theoretical constants should be rounded |
| `EVD-13` | Ranking-weight stability is a modeling/decision-analysis claim | Do not apply to a theorem's structural stability without translation |
| `LOG-03` | Observation, model interpretation, and tested mechanism must be separated | Do not force this three-part wording into every classroom explanation |
| `LOG-07` | Decision criteria and opposite-result interpretation belong to experiments | Do not demand an “opposite result” for a pure definition |
| `PAR-03` | Repeated calibration/validity boundaries are common in modeling reports | Research limitations use the RES evidence architecture |
| `DOC-05` | Audit ledgers and run detail often need engineering appendices | Do not exile a decisive research proof merely because it is technical |

## RES (6)

| Rule | Why RES owns it | Prohibited use |
|---|---|---|
| `LEX-03` | Universal abstract nouns often hide the research contribution | Do not purge useful organizing nouns from basic notes by default |
| `LEX-07` | Ornamental academic framing is especially damaging in journal prose | A classroom transition may remain if it genuinely guides learning |
| `SYN-06` | Nominalization stacks often hide research actions and agents | Do not force colloquial verbs into standard mathematical definitions |
| `SYN-08` | Symmetric syntax can falsely equalize unequal research evidence | Classroom parallelism may aid retrieval when concepts are truly parallel |
| `LOG-01` | A research method must arise from a concrete unresolved gap | Notes may introduce a known method from a learning objective |
| `DOC-03` | Journal abstract strength must follow the completed body | Notes and engineering logs need not have a journal abstract |

## Misuse gate

Before applying a non-CORE base rule, record its owner and the active segment.
If they differ, either route to the correct child skill or state the exact local
object that justifies borrowing the rule. Borrowing never changes the primary
scene contract.
