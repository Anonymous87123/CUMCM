#!/usr/bin/env python3
"""Compare section-role and paragraph-rhythm signals for a source/candidate pair.

This is a relative regression guard. It does not detect AI authorship or prove
that a candidate is natural.

Public interface:
    python compare_style_revision.py <source.tex> <candidate.tex> --format text|json

Exit codes: 0=IMPROVED, 2=UNCHANGED/REVIEW, 1=input error.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_style_rhythm import audit as audit_rhythm
from audit_voice_mode import audit as audit_voice, parse_document


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prose_inventory(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    segments = [item for item in parse_document(text) if item.mode == "prose"]
    return {
        "segments": len(segments),
        "paragraphs": sum(len(item.paragraphs) for item in segments),
        "list_blocks": sum(item.list_blocks for item in segments),
        "list_items": sum(item.list_items for item in segments),
        "one_item_lists": sum(item.one_item_lists for item in segments),
        "labeled_list_items": sum(item.labeled_list_items for item in segments),
    }


def finding_counts(report: dict) -> dict:
    return dict(sorted(Counter(item["code"] for item in report["findings"]).items()))


def compare(source: Path, candidate: Path) -> dict:
    source_voice = audit_voice(source)
    candidate_voice = audit_voice(candidate)
    source_rhythm = audit_rhythm(source, "auto")
    candidate_rhythm = audit_rhythm(candidate, "auto")
    source_inventory = prose_inventory(source)
    candidate_inventory = prose_inventory(candidate)

    regressions: list[dict] = []
    improvements: list[dict] = []
    metrics = {
        "voice_findings": (
            source_voice["summary"]["findings"], candidate_voice["summary"]["findings"]
        ),
        "rhythm_findings": (
            source_rhythm["summary"]["findings"], candidate_rhythm["summary"]["findings"]
        ),
        "one_item_lists": (
            source_inventory["one_item_lists"], candidate_inventory["one_item_lists"]
        ),
        "labeled_list_items": (
            source_inventory["labeled_list_items"], candidate_inventory["labeled_list_items"]
        ),
    }
    for name, (before, after) in metrics.items():
        record = {"metric": name, "source": before, "candidate": after, "delta": after - before}
        if after > before:
            regressions.append(record)
        elif after < before:
            improvements.append(record)

    same_bytes = sha256_file(source) == sha256_file(candidate)
    if regressions:
        verdict = "review"
    elif improvements:
        verdict = "improved"
    else:
        verdict = "unchanged"
    return {
        "schema": "aigc-style-revision-comparison/v1",
        "status": verdict,
        "source": {"path": str(source.resolve()), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate.resolve()), "sha256": sha256_file(candidate)},
        "same_bytes": same_bytes,
        "source_signals": {
            "voice": finding_counts(source_voice),
            "rhythm": finding_counts(source_rhythm),
            "prose_inventory": source_inventory,
        },
        "candidate_signals": {
            "voice": finding_counts(candidate_voice),
            "rhythm": finding_counts(candidate_rhythm),
            "prose_inventory": candidate_inventory,
        },
        "improvements": improvements,
        "regressions": regressions,
        "interpretation": (
            "Relative structural signal only. Adoption still requires semantic, mathematical, "
            "document, and source-bound paragraph review."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    for label, path in (("source", args.source), ("candidate", args.candidate)):
        if not path.is_file():
            parser.error(f"{label} not found: {path}")
    report = compare(args.source, args.candidate)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"STYLE REVISION {report['status'].upper()} "
            f"improvements={len(report['improvements'])} regressions={len(report['regressions'])}"
        )
        for item in report["improvements"]:
            print(f"[BETTER] {item['metric']}: {item['source']} -> {item['candidate']}")
        for item in report["regressions"]:
            print(f"[REVIEW] {item['metric']}: {item['source']} -> {item['candidate']}")
        print("NOTE: relative structural signal only; not an AI-authorship or naturalness verdict.")
    return 0 if report["status"] == "improved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
