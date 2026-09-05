#!/usr/bin/env python3
"""Audit compiled body-page length and question-level evidence coverage."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


LABEL_PATTERN = r"\\newlabel\{{{label}\}}\{{\{{.*?\}}\{{(?P<page>\d+)\}}"


def label_page(aux_text: str, label: str) -> int | None:
    match = re.search(LABEL_PATTERN.format(label=re.escape(label)), aux_text)
    return int(match.group("page")) if match else None


def normalize_tex(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def question_scope_findings(tex: str, payload: dict) -> list[dict]:
    findings: list[dict] = []
    located: list[dict] = []
    body_start_matches = list(re.finditer(r"\\label\s*\{mcm-body-start\}", tex))
    body_end_matches = list(re.finditer(r"\\label\s*\{mcm-body-end\}", tex))
    body_start = body_start_matches[0] if len(body_start_matches) == 1 else None
    body_end = body_end_matches[0] if len(body_end_matches) == 1 else None
    if len(body_start_matches) != 1 or len(body_end_matches) != 1:
        findings.append({
            "severity": "error",
            "code": "BODY_SCOPE_LABEL_CARDINALITY",
            "start_count": len(body_start_matches),
            "end_count": len(body_end_matches),
        })
    elif body_start.start() >= body_end.start():
        findings.append({"severity": "error", "code": "BODY_SCOPE_REVERSED"})
    for declared_index, question in enumerate(payload.get("questions", [])):
        question_id = str(question.get("id", "unnamed"))
        start_label = str(question.get("start_label", "")).strip()
        end_label = str(question.get("end_label", "")).strip()
        if not start_label and not end_label:
            continue
        start_matches = list(re.finditer(rf"\\label\s*\{{{re.escape(start_label)}\}}", tex))
        end_matches = list(re.finditer(rf"\\label\s*\{{{re.escape(end_label)}\}}", tex))
        if len(start_matches) != 1 or len(end_matches) != 1:
            findings.append({
                "severity": "error",
                "code": "QUESTION_SCOPE_LABEL_CARDINALITY",
                "question": question_id,
                "start_count": len(start_matches),
                "end_count": len(end_matches),
            })
            continue
        start = start_matches[0].start()
        end = end_matches[0].end()
        if start >= end_matches[0].start():
            continue
        if body_start and body_end and not (
            body_start.start() <= start < end <= body_end.end()
        ):
            findings.append({
                "severity": "error",
                "code": "QUESTION_SCOPE_OUTSIDE_BODY",
                "question": question_id,
            })
        located.append({
            "question": question_id,
            "declared_index": declared_index,
            "start": start,
            "end": end,
        })
    declared_positions = [item["start"] for item in located]
    if declared_positions != sorted(declared_positions):
        findings.append({
            "severity": "error",
            "code": "QUESTION_SCOPE_OUT_OF_ORDER",
            "declared_questions": [item["question"] for item in located],
            "source_questions": [
                item["question"] for item in sorted(located, key=lambda row: row["start"])
            ],
        })
    ordered = sorted(located, key=lambda row: row["start"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["start"] < previous["end"]:
            findings.append({
                "severity": "error",
                "code": "QUESTION_SCOPE_OVERLAP",
                "questions": [previous["question"], current["question"]],
            })
    return findings


def coverage_findings(tex: str, payload: dict) -> list[dict]:
    findings: list[dict] = []
    required = (
        "problem_data_basis",
        "variables_scope",
        "mathematical_relation",
        "solver_implementation",
        "result",
        "interpretation",
        "validation",
        "boundary",
    )
    for question in payload.get("questions", []):
        question_id = str(question.get("id", "unnamed"))
        scope = tex
        start_label = str(question.get("start_label", "")).strip()
        end_label = str(question.get("end_label", "")).strip()
        if start_label or end_label:
            start = re.search(rf"\\label\s*\{{{re.escape(start_label)}\}}", tex) if start_label else None
            end = re.search(rf"\\label\s*\{{{re.escape(end_label)}\}}", tex) if end_label else None
            if not start or not end or start.start() >= end.start():
                findings.append({
                    "severity": "error",
                    "code": "QUESTION_SCOPE_UNLOCATED",
                    "question": question_id,
                    "start_label": start_label,
                    "end_label": end_label,
                })
                continue
            scope = tex[start.start():end.end()]
        evidence = question.get("evidence", {})
        waivers = question.get("waivers", {})
        for field in required:
            patterns = evidence.get(field, [])
            if isinstance(patterns, str):
                patterns = [patterns]
            if patterns and any(re.search(pattern, scope, re.I | re.S) for pattern in patterns):
                continue
            waiver = str(waivers.get(field, "")).strip()
            if waiver:
                continue
            findings.append({
                "severity": "error",
                "code": "QUESTION_COVERAGE_MISSING",
                "question": question_id,
                "field": field,
            })
    return findings


def audit(main_tex: Path, aux_path: Path, coverage_path: Path, min_pages: int, max_pages: int) -> dict:
    tex = normalize_tex(main_tex.read_text(encoding="utf-8-sig"))
    aux = aux_path.read_text(encoding="utf-8-sig", errors="replace")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8-sig"))
    findings: list[dict] = []

    start = label_page(aux, "mcm-body-start")
    end = label_page(aux, "mcm-body-end")
    pages = None if start is None or end is None else end - start + 1
    if start is None:
        findings.append({"severity": "error", "code": "BODY_START_LABEL_MISSING"})
    if end is None:
        findings.append({"severity": "error", "code": "BODY_END_LABEL_MISSING"})
    if pages is not None and pages < min_pages:
        findings.append({
            "severity": "error",
            "code": "BODY_TOO_SHORT",
            "pages": pages,
            "minimum": min_pages,
        })
    if pages is not None and pages > max_pages:
        findings.append({
            "severity": "error",
            "code": "BODY_TOO_LONG",
            "pages": pages,
            "maximum": max_pages,
        })

    newpages = len(re.findall(r"\\(?:newpage|clearpage|pagebreak)\b", tex))
    if newpages > int(coverage.get("max_manual_page_breaks", 2)):
        findings.append({
            "severity": "error",
            "code": "MANUAL_PAGE_BREAK_SATURATION",
            "count": newpages,
        })
    if re.search(r"\\vspace\*?\s*\{\s*(?:[2-9]|\d{2,})(?:\.\d+)?\s*(?:cm|mm|em|ex)\s*\}", tex):
        findings.append({"severity": "error", "code": "LARGE_VERTICAL_PADDING"})
    if re.search(r"\\(?:onehalfspacing|doublespacing)\b|\\setstretch\s*\{\s*(?:1\.[6-9]|[2-9])", tex):
        findings.append({"severity": "error", "code": "INFLATED_LINE_SPACING"})

    findings.extend(question_scope_findings(tex, coverage))
    findings.extend(coverage_findings(tex, coverage))
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "file": str(main_tex.resolve()),
        "aux": str(aux_path.resolve()),
        "coverage": str(coverage_path.resolve()),
        "body_start_page": start,
        "body_end_page": end,
        "body_pages": pages,
        "range": [min_pages, max_pages],
        "errors": errors,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--aux", required=True, type=Path)
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--min-pages", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.aux, args.coverage, args.min_pages, args.max_pages)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"COMPETITION LENGTH {report['status'].upper()} errors={report['errors']} "
            f"body_pages={report['body_pages']} range={args.min_pages}-{args.max_pages}"
        )
        for item in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key not in {"severity", "code"})
            print(f"[{item['severity'].upper()}] {item['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
