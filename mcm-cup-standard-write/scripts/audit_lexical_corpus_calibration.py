#!/usr/bin/env python3
"""Calibrate strict lexical phrases against the verified CUMCM human corpus.

Public interface:
    python audit_lexical_corpus_calibration.py --format text|json

The report never labels a phrase as human-authored or automatically acceptable.
It only identifies phrases whose single occurrence cannot be treated as an
AI-specific hard blocker because the phrase is attested across multiple verified
competition papers.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL_ROOT.parent
DEFAULT_LEXICON = (
    SKILLS_ROOT / "AIGC" / "humanize-academic-chinese" / "references" / "lexical-signals.json"
)
DEFAULT_INDEX = SKILL_ROOT / "references" / "fulltext-style-index.jsonl"
SCHEMA = "mcm-lexical-corpus-calibration/v1"


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def audit(lexicon_path: Path, index_path: Path, minimum_papers: int = 5) -> dict:
    lexicon_path = lexicon_path.resolve()
    index_path = index_path.resolve()
    lexicon = _load_json(lexicon_path)
    inventory = lexicon.get("strict_phrase_inventory")
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("strict phrase inventory is missing")
    records = []
    with index_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise ValueError(f"invalid full-text record at line {line_number}")
            records.append(row)
    papers = {str(row.get("paper")) for row in records if row.get("paper")}
    if len(papers) != 59:
        raise ValueError(f"verified CUMCM corpus must contain 59 papers, got {len(papers)}")

    phrase_rows = []
    category_counts: dict[str, int] = defaultdict(int)
    contextual = 0
    observed = 0
    for entry in inventory:
        if not isinstance(entry, dict) or not isinstance(entry.get("phrase"), str):
            raise ValueError("strict phrase inventory contains an invalid row")
        phrase = entry["phrase"]
        hits = [row for row in records if phrase in row["text"]]
        paper_count = len({str(row.get("paper")) for row in hits})
        paragraph_count = len(hits)
        if paper_count >= minimum_papers:
            disposition = "contextual-human-attested"
            contextual += 1
            category_counts[str(entry.get("category", "unknown"))] += 1
        elif paper_count:
            disposition = "observed-not-calibrated"
            observed += 1
        else:
            disposition = "strict-unattested"
        phrase_rows.append({
            "phrase": phrase,
            "category": entry.get("category"),
            "paper_count": paper_count,
            "paragraph_count": paragraph_count,
            "disposition": disposition,
        })
    return {
        "schema": SCHEMA,
        "status": "pass",
        "minimum_papers": minimum_papers,
        "papers": len(papers),
        "paragraphs": len(records),
        "strict_inventory_entries": len(inventory),
        "contextual_human_attested": contextual,
        "observed_not_calibrated": observed,
        "category_counts": dict(sorted(category_counts.items())),
        "phrases": phrase_rows,
        "inputs": {
            "lexicon": str(lexicon_path),
            "fulltext_index": str(index_path),
        },
        "interpretation": (
            "A contextual-human-attested phrase remains visible for rhythm and context review, but one occurrence "
            "is not an AI-specific hard blocker. This report does not prove authorship or endorse every use."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON)
    parser.add_argument("--fulltext-index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--minimum-papers", type=int, default=5)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = audit(args.lexicon, args.fulltext_index, args.minimum_papers)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"schema": SCHEMA, "status": "fail", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["status"] == "pass":
        print(
            "MCM LEXICAL CORPUS CALIBRATION PASS "
            f"papers={report['papers']} inventory={report['strict_inventory_entries']} "
            f"contextual={report['contextual_human_attested']}"
        )
    else:
        print(f"MCM LEXICAL CORPUS CALIBRATION FAIL error={report['error']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
