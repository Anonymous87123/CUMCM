#!/usr/bin/env python3
"""Audit discoverability and coverage of the 59-paper style evidence layer."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from build_fulltext_style_corpus import SUSPICIOUS_OCR_FRAGMENTS
from query_style_patterns import (
    FULLTEXT_INDEX,
    HUMAN_STYLE,
    PAPER_CARDS,
    STYLE_INDEX,
    load_records,
)


SKILL_ROOT = Path(__file__).resolve().parents[1]
CORPUS_INDEX = SKILL_ROOT / "references" / "corpus-index.md"
FULLTEXT_STATS = SKILL_ROOT / "references" / "fulltext-style-stats.json"
FULLTEXT_USAGE = SKILL_ROOT / "references" / "fulltext-language-usage.md"
WORKSPACE_PROGRESS_CANDIDATES = (
    Path.cwd() / ".cumcm-work" / "deep-evidence" / "manual-review-progress.csv",
    Path("F:/CUMCM/.cumcm-work/deep-evidence/manual-review-progress.csv"),
)

FINE_GRAINED_SUPPLEMENTS = {
    "A070", "A147", "A195", "A212", "A028", "A115",
    "B078", "B108", "B125", "B175",
    "C109", "C142", "C170", "C227", "C305",
}


def audit() -> dict[str, object]:
    records = load_records()
    human_text = HUMAN_STYLE.read_text(encoding="utf-8")
    human_lines = human_text.splitlines()
    corpus_text = CORPUS_INDEX.read_text(encoding="utf-8")
    errors: list[str] = []
    verified_progress = 0
    verified_pages = 0
    fulltext_records: list[dict] = []

    papers = [record.paper for record in records]
    evidence_ids = [record.evidence_id for record in records]
    if len(records) != 59:
        errors.append(f"style index contains {len(records)} records, expected 59")
    if len(set(papers)) != len(papers):
        errors.append("duplicate paper ids in style index")
    if len(set(evidence_ids)) != len(evidence_ids):
        errors.append("duplicate STYLE evidence ids")

    for record in records:
        evidence_match = re.search(
            rf"^####\s+{re.escape(record.evidence_id)}\s*$\n"
            rf"(?P<body>.*?)(?=^####\s+EV-|^###\s+|\Z)",
            human_text,
            re.M | re.S,
        )
        if record.evidence_id not in human_text:
            errors.append(f"missing evidence block: {record.evidence_id}")
            evidence_context = ""
        elif evidence_match:
            evidence_context = evidence_match.group("body")
        elif record.evidence_line is not None:
            start = max(0, record.evidence_line - 1)
            evidence_context = "\n".join(human_lines[start:start + 3])
        else:
            evidence_context = ""
        if evidence_context and not re.search(
            r"(?:p\.|pp\.|page|页|页面|物理页)", evidence_context, re.I
        ):
            errors.append(f"evidence block misses page range: {record.evidence_id}")
        if record.evidence_line is None:
            errors.append(f"evidence block is not line-addressable: {record.evidence_id}")
        if len(record.reasoning_trace.strip()) < 12:
            errors.append(f"reasoning trace is too thin: {record.paper}")
        if len(record.rejected_cliche.strip()) < 4:
            errors.append(f"rejected empty wording is missing: {record.paper}")
        if not record.trigger_tags:
            errors.append(f"no evidence trigger tag: {record.paper}")
        if not record.action_tags:
            errors.append(f"no modeling action tag: {record.paper}")
        if not Path(record.paper_card).is_file():
            errors.append(f"missing paper card: {record.paper_card}")
        else:
            card_text = Path(record.paper_card).read_text(encoding="utf-8")
            if record.evidence_id not in card_text:
                errors.append(
                    f"paper card misses STYLE evidence id: {record.year}_{record.paper}"
                )
            if not re.search(r"(?:p\.|page|页|页面|物理页)", card_text, re.I):
                errors.append(
                    f"paper card misses page-location signal: {record.year}_{record.paper}"
                )
        if f"{record.year}_{record.paper}.md" not in corpus_text:
            errors.append(f"paper absent from corpus index: {record.year}_{record.paper}")
        if len(record.language_notes) < 3:
            errors.append(
                f"paper has only {len(record.language_notes)} retrievable language notes: "
                f"{record.paper}"
            )
        elif any(len(note.strip()) < 12 for note in record.language_notes):
            errors.append(f"paper has a content-thin language note: {record.paper}")
        elif len(set(record.language_notes)) != len(record.language_notes):
            errors.append(f"paper repeats a retrievable language note: {record.paper}")
        if record.paper in FINE_GRAINED_SUPPLEMENTS:
            missing_fields = [
                label for label, value in (
                    ("词语功能", record.language_functions),
                    ("节奏与接口", record.rhythm_interface),
                    ("停止位置", record.stopping_point),
                )
                if not value
            ]
            if missing_fields:
                errors.append(
                    f"fine-grained supplement {record.paper} misses: "
                    + ", ".join(missing_fields)
                )

    card_count = len(list(PAPER_CARDS.glob("*.md")))
    if card_count != 59:
        errors.append(f"paper-card directory contains {card_count} markdown files, expected 59")

    distribution = Counter(record.problem_type for record in records)
    expected = {"A": 20, "B": 19, "C": 20}
    if dict(distribution) != expected:
        errors.append(f"problem distribution is {dict(distribution)}, expected {expected}")

    if not FULLTEXT_INDEX.is_file():
        errors.append("fulltext-style-index.jsonl is missing")
    else:
        with FULLTEXT_INDEX.open(encoding="utf-8") as stream:
            fulltext_records = [json.loads(line) for line in stream if line.strip()]
        fulltext_papers = {record["paper"] for record in fulltext_records}
        fulltext_distribution = Counter(
            paper[0] for paper in fulltext_papers
        )
        fulltext_quality = Counter(record["quality"] for record in fulltext_records)
        if len(fulltext_records) < 8000:
            errors.append(f"full-text index contains only {len(fulltext_records)} reconstructed paragraphs")
        if fulltext_papers != set(papers):
            errors.append("full-text paragraph index paper set differs from style index")
        if dict(fulltext_distribution) != expected:
            errors.append(
                f"full-text paragraph distribution covers {dict(fulltext_distribution)}, expected paper set {expected}"
            )
        if fulltext_quality["high"] < 2800:
            errors.append(f"only {fulltext_quality['high']} high-quality full-text paragraphs")
        default_retrieval = sum(
            bool(record.get("retrieval_eligible"))
            for record in fulltext_records
        )
        if default_retrieval < 1600:
            errors.append(f"only {default_retrieval} paragraphs pass the default retrieval gate")
        if sum(value for key, value in fulltext_quality.items() if key != "low") < 7500:
            errors.append("fewer than 7500 usable full-text paragraphs")
        watermark = re.compile(r"学生在线|大学生在线|中国大学|数学建模竞赛")
        if any(watermark.search(record["text"]) for record in fulltext_records):
            errors.append("watermark text remains in full-text paragraph index")
        if any(
            re.search(r"关键词|关键字", record["text"]) and record["quality"] != "low"
            for record in fulltext_records
        ):
            errors.append("keyword list is admitted as a prose-quality paragraph")
        retrieval_rows = [record for record in fulltext_records if record.get("retrieval_eligible")]
        retrieval_by_type = Counter(record["problem_type"] for record in retrieval_rows)
        for problem_type, minimum in {"A": 400, "B": 500, "C": 600}.items():
            if retrieval_by_type[problem_type] < minimum:
                errors.append(
                    f"only {retrieval_by_type[problem_type]} clean retrieval paragraphs for type {problem_type}"
                )
        retrieval_by_section = Counter(record["section"] for record in retrieval_rows)
        for section, minimum in {
            "analysis": 200, "model": 450, "solve": 120,
            "result": 100, "validation": 50,
        }.items():
            if retrieval_by_section[section] < minimum:
                errors.append(
                    f"only {retrieval_by_section[section]} clean retrieval paragraphs for section {section}"
                )
        polluted = [
            record["id"] for record in retrieval_rows
            if any(fragment in record["text"] for fragment in SUSPICIOUS_OCR_FRAGMENTS)
            or re.search(r"[。！？；]{2,}", record["text"])
        ]
        if polluted:
            errors.append(f"OCR-polluted paragraphs remain retrievable: {polluted[:8]}")

    if not FULLTEXT_STATS.is_file():
        errors.append("fulltext-style-stats.json is missing")
        fulltext_stats = {}
    else:
        fulltext_stats = json.loads(FULLTEXT_STATS.read_text(encoding="utf-8"))
        scope = fulltext_stats.get("scope", {})
        if scope.get("papers") != 59 or scope.get("pages") != 2892:
            errors.append("full-text statistics scope is not 59 papers / 2892 pages")
        if fulltext_records and scope.get("paragraphs_reconstructed") != len(fulltext_records):
            errors.append("full-text statistics paragraph count differs from the paragraph index")
        if fulltext_records and scope.get("quality") != dict(fulltext_quality):
            errors.append("full-text statistics quality distribution differs from the paragraph index")
        style_ocr220 = scope.get("style_ocr220", {})
        if style_ocr220.get("generated") != 448:
            errors.append(f"220 DPI style OCR covers {style_ocr220.get('generated', 0)}/448 target pages")
        if style_ocr220.get("accepted", 0) < 300:
            errors.append("fewer than 300 high-resolution OCR pages passed the conservative replacement gate")
        if style_ocr220.get("accepted", 0) + style_ocr220.get("rejected", 0) != style_ocr220.get("generated", 0):
            errors.append("220 DPI style OCR acceptance accounting is inconsistent")
        introductions = fulltext_stats.get("model_introductions", [])
        if any(re.search(r"关键词|关键字", item.get("introduction", "")) for item in introductions):
            errors.append("model-introduction memory contains a keyword list")
        if not fulltext_stats.get("section_by_problem_type"):
            errors.append("A/B/C by-section language statistics are missing")
        if not fulltext_stats.get("model_introduction_pathways"):
            errors.append("model-introduction pathway statistics are missing")

    if not FULLTEXT_USAGE.is_file() or len(FULLTEXT_USAGE.read_text(encoding="utf-8")) < 6000:
        errors.append("full-text language usage protocol is missing or content-thin")

    progress_path = next(
        (path for path in WORKSPACE_PROGRESS_CANDIDATES if path.is_file()), None
    )
    if progress_path is None:
        errors.append("manual-review-progress.csv not found; full-page review is unverified")
    else:
        with progress_path.open(encoding="utf-8-sig", newline="") as handle:
            progress_rows = list(csv.DictReader(handle))
        if len(progress_rows) != 59:
            errors.append(
                f"manual review ledger contains {len(progress_rows)} rows, expected 59"
            )
        ledger_papers = {row["paper"] for row in progress_rows}
        if ledger_papers != set(papers):
            errors.append("manual review ledger paper set differs from style index")
        for row in progress_rows:
            if row["full_text_review"] != "verified":
                errors.append(f"full-text review not verified: {row['year']}_{row['paper']}")
                continue
            if row["deep_review_status"] != "verified":
                errors.append(f"deep review not verified: {row['year']}_{row['paper']}")
            if int(row["section_categories_verified"]) != 14:
                errors.append(f"14-section review incomplete: {row['year']}_{row['paper']}")
            if int(row["raster_items_total"]) != int(row["raster_items_verified"]):
                errors.append(f"raster review incomplete: {row['year']}_{row['paper']}")
            verified_progress += 1
            verified_pages += int(row["pages"])
        if verified_pages != 2892:
            errors.append(
                f"verified page total is {verified_pages}, expected 2892"
            )

    return {
        "ok": not errors,
        "records": len(records),
        "unique_papers": len(set(papers)),
        "unique_evidence_ids": len(set(evidence_ids)),
        "paper_cards": card_count,
        "problem_distribution": dict(sorted(distribution.items())),
        "fine_grained_supplements": sum(
            bool(
                record.paper in FINE_GRAINED_SUPPLEMENTS
                and record.language_functions
                and record.rhythm_interface
                and record.stopping_point
            )
            for record in records
        ),
        "retrievable_language_notes": sum(bool(record.language_notes) for record in records),
        "language_pattern_ready": sum(
            bool(
                len(record.reasoning_trace.strip()) >= 12
                and len(record.rejected_cliche.strip()) >= 4
                and record.trigger_tags
                and record.action_tags
                and record.evidence_line is not None
                and len(record.language_notes) >= 3
                and all(len(note.strip()) >= 12 for note in record.language_notes)
                and len(set(record.language_notes)) == len(record.language_notes)
            )
            for record in records
        ),
        "verified_full_text_reviews": verified_progress,
        "verified_pages": verified_pages,
        "fulltext_paragraphs": len(fulltext_records),
        "fulltext_usable_paragraphs": sum(
            record.get("quality") != "low" for record in fulltext_records
        ),
        "fulltext_high_quality_paragraphs": sum(
            record.get("quality") == "high" for record in fulltext_records
        ),
        "fulltext_default_retrieval_paragraphs": sum(
            bool(record.get("retrieval_eligible"))
            for record in fulltext_records
        ),
        "style_ocr220": fulltext_stats.get("scope", {}).get("style_ocr220", {}),
        "style_index": str(STYLE_INDEX),
        "human_style": str(HUMAN_STYLE),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    result = audit()
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"style records: {result['records']}/59")
        print(f"unique papers: {result['unique_papers']}/59")
        print(f"STYLE evidence ids: {result['unique_evidence_ids']}/59")
        print(f"paper cards: {result['paper_cards']}/59")
        print(f"fine-grained supplements: {result['fine_grained_supplements']}/15")
        print(f"retrievable language notes: {result['retrievable_language_notes']}/59")
        print(f"language-pattern ready records: {result['language_pattern_ready']}/59")
        print(f"verified full-text reviews: {result['verified_full_text_reviews']}/59")
        print(f"verified pages: {result['verified_pages']}/2892")
        print(f"full-text paragraphs: {result['fulltext_paragraphs']}")
        print(f"usable full-text paragraphs: {result['fulltext_usable_paragraphs']}")
        print(f"high-quality retrieval paragraphs: {result['fulltext_high_quality_paragraphs']}")
        print(f"default full-text retrieval paragraphs: {result['fulltext_default_retrieval_paragraphs']}")
        print(f"220 DPI style OCR: {result['style_ocr220']}")
        print(f"A/B/C: {result['problem_distribution']}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"ERROR: {error}")
        else:
            print("PASS")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
