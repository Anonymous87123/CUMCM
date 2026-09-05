#!/usr/bin/env python3
"""Audit a team review record for visible CUMCM reasoning bridges.

Public interface:
    python audit_reasoning_review.py main.tex --review reasoning-review.json \
        --format text|json

The record captures concise human explanations of visible manuscript reasoning.
It must not contain hidden chain-of-thought or claim to prove reviewer identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from audit_manuscript import question_sections, read_tex_tree, visible_prose


SCHEMA = "mcm-reasoning-review/v1"
DECISIONS = {"pass", "revise"}
HUMAN_REVIEWER_KIND = "human"


def _finding(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def manuscript_hash(path: Path) -> str:
    return hashlib.sha256(read_tex_tree(path.resolve()).encode("utf-8")).hexdigest()


def _nonempty_strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _searchable(text: str) -> str:
    return "".join(text.casefold().split())


def _has_term(text: str, terms: list[str]) -> bool:
    scope = _searchable(text)
    return any(_searchable(term) in scope for term in terms)


def _scopes(tex: str) -> dict[str, str]:
    scopes: dict[str, list[str]] = defaultdict(list)
    for question_id, title, _start, _content_start, body in question_sections(tex):
        scopes[question_id].append("\n".join((visible_prose(title), visible_prose(body))))
    return {question_id: "\n".join(parts) for question_id, parts in scopes.items()}


def audit(tex_path: Path, review_path: Path) -> dict:
    findings: list[dict] = []
    tex_path = tex_path.resolve()
    if not tex_path.is_file():
        _finding(findings, "REASONING_REVIEW_MANUSCRIPT_MISSING", path=str(tex_path))
        return _report(findings, 0, 0)
    if not review_path.is_file():
        _finding(findings, "REASONING_REVIEW_FILE_MISSING", path=str(review_path))
        return _report(findings, 0, 0)
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, "REASONING_REVIEW_JSON_INVALID", error=str(exc))
        return _report(findings, 0, 0)
    if not isinstance(payload, dict):
        _finding(findings, "REASONING_REVIEW_JSON_NOT_OBJECT")
        return _report(findings, 0, 0)
    if payload.get("schema") != SCHEMA:
        _finding(findings, "REASONING_REVIEW_SCHEMA_MISMATCH", expected=SCHEMA, actual=payload.get("schema"))
    try:
        flattened = read_tex_tree(tex_path)
    except (OSError, ValueError) as exc:
        _finding(findings, "REASONING_REVIEW_TEX_TREE_INVALID", error=str(exc))
        return _report(findings, 0, 0)
    expected_hash = hashlib.sha256(flattened.encode("utf-8")).hexdigest()
    if payload.get("manuscript_sha256") != expected_hash:
        _finding(findings, "REASONING_REVIEW_MANUSCRIPT_HASH_MISMATCH")
    scopes = _scopes(flattened)
    raw_reviews = payload.get("reviews")
    if not isinstance(raw_reviews, list) or not raw_reviews:
        _finding(findings, "REASONING_REVIEW_ENTRIES_INVALID")
        return _report(findings, len(scopes), 0)

    reviewers_by_question: dict[str, set[str]] = defaultdict(set)
    valid_entries = 0
    for raw in raw_reviews:
        if not isinstance(raw, dict):
            _finding(findings, "REASONING_REVIEW_ENTRY_INVALID")
            continue
        question_id = str(raw.get("question_id", "")).strip()
        reviewer = raw.get("reviewer")
        reviewer_kind = raw.get("reviewer_kind")
        terms = _nonempty_strings(raw.get("bridge_terms"))
        text_fields = (raw.get("anchor_explanation"), raw.get("transition_explanation"), raw.get("condition_change"))
        if reviewer_kind != HUMAN_REVIEWER_KIND:
            _finding(
                findings,
                "REASONING_REVIEWER_KIND_NOT_HUMAN",
                question_id=question_id,
                reviewer_kind=reviewer_kind,
            )
            continue
        if (
            question_id not in scopes
            or not isinstance(reviewer, str) or len(reviewer.strip()) < 2
            or terms is None
            or raw.get("decision") not in DECISIONS
            or not all(isinstance(value, str) and len(value.strip()) >= 8 for value in text_fields)
        ):
            _finding(findings, "REASONING_REVIEW_FIELDS_INVALID", question_id=question_id)
            continue
        if not _has_term(scopes[question_id], terms):
            _finding(findings, "REASONING_REVIEW_TERMS_NOT_IN_SCOPE", question_id=question_id, reviewer=reviewer)
        if raw["decision"] != "pass":
            _finding(findings, "REASONING_REVIEW_REVISE_REQUIRED", question_id=question_id, reviewer=reviewer)
        reviewers_by_question[question_id].add(reviewer.strip())
        valid_entries += 1
    for question_id in sorted(scopes):
        if len(reviewers_by_question[question_id]) < 2:
            _finding(
                findings,
                "REASONING_REVIEWER_COUNT_INSUFFICIENT",
                question_id=question_id,
                reviewers=len(reviewers_by_question[question_id]),
            )
    return _report(findings, len(scopes), valid_entries)


def _report(findings: list[dict], manuscript_questions: int, review_entries: int) -> dict:
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "mcm-reasoning-review-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "manuscript_questions": manuscript_questions,
        "review_entries": review_entries,
        "findings": findings,
        "interpretation": (
            "Passing confirms a locked manuscript has two concise, in-scope review records explicitly marked as human "
            "per question. "
            "It does not prove reviewer identity, mathematical correctness, authorship, or prose naturalness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.review)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"REASONING REVIEW {report['status'].upper()} questions={report['manuscript_questions']} "
            f"entries={report['review_entries']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
