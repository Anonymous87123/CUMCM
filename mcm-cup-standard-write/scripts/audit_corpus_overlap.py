#!/usr/bin/env python3
"""Flag long literal overlaps between a CUMCM manuscript and the 59-paper corpus.

Public interface:
    python audit_corpus_overlap.py main.tex [--corpus-index fulltext-style-index.jsonl] \
        [--min-chars 20] [--fail-on-overlap] --format text|json

An overlap is a review signal, not a plagiarism or authorship finding.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

from audit_manuscript import read_tex_tree, visible_prose


DEFAULT_CORPUS_INDEX = Path(__file__).resolve().parent.parent / "references" / "fulltext-style-index.jsonl"
KEEP = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")


def _normalise(text: str) -> str:
    return KEEP.sub("", text).casefold()


def _paragraphs(tex_path: Path) -> list[dict]:
    prose = visible_prose(read_tex_tree(tex_path.resolve()))
    paragraphs = []
    for ordinal, raw in enumerate(re.split(r"\n\s*\n", prose), start=1):
        normalized = _normalise(raw)
        if normalized:
            paragraphs.append({"ordinal": ordinal, "text": raw.strip(), "normalized": normalized})
    return paragraphs


def _load_corpus(index_path: Path, min_chars: int) -> list[dict]:
    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        text = raw.get("text")
        if not isinstance(text, str):
            continue
        normalized = _normalise(text)
        if len(normalized) >= min_chars:
            records.append({**raw, "normalized": normalized})
    return records


def audit(tex_path: Path, corpus_index: Path = DEFAULT_CORPUS_INDEX, min_chars: int = 20) -> dict:
    findings: list[dict] = []
    tex_path = tex_path.resolve()
    corpus_index = corpus_index.resolve()
    if min_chars < 12:
        return _report("fail", [{"severity": "error", "code": "OVERLAP_THRESHOLD_TOO_LOW", "min_chars": min_chars}], 0, 0, min_chars)
    if not tex_path.is_file():
        return _report("fail", [{"severity": "error", "code": "OVERLAP_MANUSCRIPT_MISSING", "path": str(tex_path)}], 0, 0, min_chars)
    if not corpus_index.is_file():
        return _report("fail", [{"severity": "error", "code": "OVERLAP_CORPUS_INDEX_MISSING", "path": str(corpus_index)}], 0, 0, min_chars)
    try:
        manuscript = _paragraphs(tex_path)
        corpus = _load_corpus(corpus_index, min_chars)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _report("fail", [{"severity": "error", "code": "OVERLAP_INPUT_INVALID", "error": str(exc)}], 0, 0, min_chars)

    manuscript_ngrams: dict[str, set[int]] = defaultdict(set)
    for index, paragraph in enumerate(manuscript):
        text = paragraph["normalized"]
        for start in range(len(text) - min_chars + 1):
            manuscript_ngrams[text[start:start + min_chars]].add(index)

    seen: set[tuple[int, str, str]] = set()
    for corpus_record in corpus:
        candidates: set[int] = set()
        corpus_text = corpus_record["normalized"]
        for start in range(len(corpus_text) - min_chars + 1):
            candidates.update(manuscript_ngrams.get(corpus_text[start:start + min_chars], ()))
        for manuscript_index in candidates:
            manuscript_record = manuscript[manuscript_index]
            block = max(
                difflib.SequenceMatcher(
                    None, manuscript_record["normalized"], corpus_text, autojunk=False
                ).get_matching_blocks(),
                key=lambda item: item.size,
            )
            if block.size < min_chars:
                continue
            fragment = manuscript_record["normalized"][block.a:block.a + block.size]
            key = (manuscript_record["ordinal"], str(corpus_record.get("id", "")), fragment)
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "severity": "review",
                "code": "LITERAL_CORPUS_OVERLAP",
                "manuscript_paragraph": manuscript_record["ordinal"],
                "chars": block.size,
                "fragment": fragment,
                "corpus_id": corpus_record.get("id"),
                "paper": corpus_record.get("paper"),
                "page_start": corpus_record.get("page_start"),
                "section": corpus_record.get("section"),
                "source": corpus_record.get("source"),
            })
    status = "review" if findings else "pass"
    return _report(status, sorted(findings, key=lambda item: (-item["chars"], item["manuscript_paragraph"])), len(manuscript), len(corpus), min_chars)


def _report(status: str, findings: list[dict], manuscript_paragraphs: int, corpus_paragraphs: int, min_chars: int) -> dict:
    return {
        "schema": "mcm-corpus-overlap-audit/v1",
        "status": status,
        "literal_overlaps": len(findings) if status != "fail" else 0,
        "manuscript_paragraphs": manuscript_paragraphs,
        "corpus_paragraphs": corpus_paragraphs,
        "min_chars": min_chars,
        "findings": findings,
        "interpretation": (
            "A finding is a long literal character overlap requiring human source review. "
            "It is not a plagiarism, authorship, or style-quality conclusion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--corpus-index", type=Path, default=DEFAULT_CORPUS_INDEX)
    parser.add_argument("--min-chars", type=int, default=20)
    parser.add_argument("--fail-on-overlap", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.corpus_index, args.min_chars)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"CORPUS OVERLAP {report['status'].upper()} overlaps={report['literal_overlaps']} "
            f"manuscript_paragraphs={report['manuscript_paragraphs']} corpus_paragraphs={report['corpus_paragraphs']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    if report["status"] == "fail" or (args.fail_on_overlap and report["literal_overlaps"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
