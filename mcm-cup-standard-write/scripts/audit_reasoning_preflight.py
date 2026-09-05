#!/usr/bin/env python3
"""Audit compact, team-approved CUMCM question plans before long-form drafting.

Public interface:
    python audit_reasoning_preflight.py modeling-workbench.json \
        --approval reasoning-preflight.json --format text|json

The approval records a team's public, question-level confirmation of the
fact-to-mathematics-to-route plan. It is not a hidden chain-of-thought record,
and passing cannot prove reviewer identity, mathematical correctness, or that
the prose will be natural.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


WORKBENCH_SCHEMA = "mcm-modeling-workbench/v1"
SCHEMA = "mcm-reasoning-preflight/v1"
SOURCE_ROLES = {"problem", "data", "code", "result", "figure", "log", "prior-output"}
DECISIONS = {"approve", "revise"}
HUMAN_REVIEWER_KIND = "human"


def _finding(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _load(path: Path, findings: list[dict], prefix: str) -> dict | None:
    if not path.is_file():
        _finding(findings, f"{prefix}_FILE_MISSING", path=str(path))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, f"{prefix}_JSON_INVALID", error=str(exc))
        return None
    if not isinstance(payload, dict):
        _finding(findings, f"{prefix}_JSON_NOT_OBJECT")
        return None
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_record(path: Path) -> dict:
    path = path.resolve()
    return {
        "path": str(path),
        "sha256": _sha256(path) if path.is_file() else None,
    }


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _contains_any(text: str, terms: list[str]) -> bool:
    normalized = "".join(text.casefold().split())
    return any("".join(term.casefold().split()) in normalized for term in terms)


def _parse_sources(workbench: dict, root: Path, findings: list[dict]) -> set[str]:
    raw_sources = workbench.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        _finding(findings, "PREFLIGHT_SOURCES_INVALID")
        return set()
    source_ids: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, dict):
            _finding(findings, "PREFLIGHT_SOURCE_INVALID")
            continue
        source_id = raw.get("id")
        relative = raw.get("path")
        declared_hash = raw.get("sha256")
        if (
            not isinstance(source_id, str) or not source_id.strip() or source_id in source_ids
            or raw.get("role") not in SOURCE_ROLES
            or not isinstance(relative, str) or not relative.strip()
            or not isinstance(declared_hash, str) or len(declared_hash) != 64
        ):
            _finding(findings, "PREFLIGHT_SOURCE_FIELDS_INVALID")
            continue
        source_path = (root / relative).resolve()
        try:
            source_path.relative_to(root.resolve())
        except ValueError:
            _finding(findings, "PREFLIGHT_SOURCE_OUTSIDE_ROOT", source_id=source_id)
            continue
        if not source_path.is_file():
            _finding(findings, "PREFLIGHT_SOURCE_MISSING", source_id=source_id)
            continue
        if _sha256(source_path).casefold() != declared_hash.casefold():
            _finding(findings, "PREFLIGHT_SOURCE_HASH_MISMATCH", source_id=source_id)
            continue
        source_ids.add(source_id)
    return source_ids


def _question_plans(workbench: dict, source_ids: set[str], findings: list[dict]) -> dict[str, dict]:
    raw_questions = workbench.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        _finding(findings, "PREFLIGHT_WORKBENCH_QUESTIONS_INVALID")
        return {}
    plans: dict[str, dict] = {}
    for raw in raw_questions:
        if not isinstance(raw, dict):
            _finding(findings, "PREFLIGHT_WORKBENCH_QUESTION_INVALID")
            continue
        question_id = str(raw.get("id", "")).strip()
        if not question_id or question_id in plans:
            _finding(findings, "PREFLIGHT_WORKBENCH_QUESTION_ID_INVALID", question_id=question_id)
            continue
        anchors: dict[str, dict] = {}
        for anchor in raw.get("anchors", []):
            if not isinstance(anchor, dict):
                continue
            anchor_id = anchor.get("id")
            terms = _strings(anchor.get("terms"))
            linked_sources = _strings(anchor.get("source_ids"))
            if (
                isinstance(anchor_id, str) and anchor_id.strip() and terms is not None
                and linked_sources is not None and all(item in source_ids for item in linked_sources)
            ):
                anchors[anchor_id] = {"terms": terms, "source_ids": set(linked_sources)}
        targets: dict[str, dict] = {}
        for target in raw.get("targets", []):
            if not isinstance(target, dict):
                continue
            target_id = target.get("id")
            terms = _strings(target.get("terms"))
            if isinstance(target_id, str) and target_id.strip() and terms is not None:
                targets[target_id] = {"terms": terms}
        selected = []
        for route in raw.get("routes", []):
            if not isinstance(route, dict) or route.get("status") != "selected":
                continue
            route_id = route.get("id")
            terms = _strings(route.get("terms"))
            anchor_ids = _strings(route.get("anchor_ids"))
            target_ids = _strings(route.get("target_ids"))
            evidence_ids = _strings(route.get("evidence_ids"))
            if (
                isinstance(route_id, str) and route_id.strip() and terms is not None
                and anchor_ids is not None and target_ids is not None and evidence_ids is not None
                and all(item in anchors for item in anchor_ids)
                and all(item in targets for item in target_ids)
                and all(item in source_ids for item in evidence_ids)
            ):
                selected.append({
                    "id": route_id,
                    "terms": terms,
                    "anchor_ids": set(anchor_ids),
                    "target_ids": set(target_ids),
                    "source_ids": set(evidence_ids).union(*(anchors[item]["source_ids"] for item in anchor_ids)),
                })
        if len(selected) != 1:
            _finding(findings, "PREFLIGHT_SELECTED_ROUTE_COUNT_INVALID", question_id=question_id, count=len(selected))
            continue
        plans[question_id] = {"anchors": anchors, "targets": targets, "route": selected[0]}
    return plans


def audit(workbench_path: Path, approval_path: Path) -> dict:
    findings: list[dict] = []
    workbench_path = workbench_path.resolve()
    approval_path = approval_path.resolve()
    inputs = {
        "workbench": _input_record(workbench_path),
        "approval": _input_record(approval_path),
    }
    workbench = _load(workbench_path, findings, "PREFLIGHT_WORKBENCH")
    approval = _load(approval_path, findings, "PREFLIGHT")
    if workbench is None or approval is None:
        return _report(findings, 0, 0, inputs)
    if workbench.get("schema") != WORKBENCH_SCHEMA:
        _finding(findings, "PREFLIGHT_WORKBENCH_SCHEMA_MISMATCH", expected=WORKBENCH_SCHEMA)
    if approval.get("schema") != SCHEMA:
        _finding(findings, "PREFLIGHT_SCHEMA_MISMATCH", expected=SCHEMA, actual=approval.get("schema"))
    if approval.get("workbench_sha256") != _sha256(workbench_path):
        _finding(findings, "PREFLIGHT_WORKBENCH_HASH_MISMATCH")
    sources = _parse_sources(workbench, workbench_path.parent, findings)
    plans = _question_plans(workbench, sources, findings)
    raw_approvals = approval.get("approvals")
    if not isinstance(raw_approvals, list) or not raw_approvals:
        _finding(findings, "PREFLIGHT_APPROVALS_INVALID")
        return _report(findings, len(plans), 0, inputs)

    approved: set[str] = set()
    valid_entries = 0
    for raw in raw_approvals:
        if not isinstance(raw, dict):
            _finding(findings, "PREFLIGHT_APPROVAL_INVALID")
            continue
        question_id = str(raw.get("question_id", "")).strip()
        reviewer = raw.get("reviewer")
        reviewer_kind = raw.get("reviewer_kind")
        anchor_ids = _strings(raw.get("anchor_ids"))
        target_ids = _strings(raw.get("target_ids"))
        source_ids = _strings(raw.get("source_ids"))
        route_id = raw.get("route_id")
        text_fields = (
            raw.get("basis_confirmation"),
            raw.get("transition_confirmation"),
            raw.get("change_trigger"),
        )
        if reviewer_kind != HUMAN_REVIEWER_KIND:
            _finding(
                findings,
                "PREFLIGHT_REVIEWER_KIND_NOT_HUMAN",
                question_id=question_id,
                reviewer_kind=reviewer_kind,
            )
            continue
        if (
            question_id not in plans or question_id in approved
            or not isinstance(reviewer, str) or len(reviewer.strip()) < 2
            or anchor_ids is None or target_ids is None or source_ids is None
            or not isinstance(route_id, str) or not route_id.strip()
            or raw.get("decision") not in DECISIONS
            or not all(isinstance(value, str) and len(value.strip()) >= 12 for value in text_fields)
        ):
            _finding(findings, "PREFLIGHT_APPROVAL_FIELDS_INVALID", question_id=question_id)
            continue
        plan = plans[question_id]
        route = plan["route"]
        if set(anchor_ids) != route["anchor_ids"] or set(target_ids) != route["target_ids"]:
            _finding(findings, "PREFLIGHT_APPROVAL_PLAN_LINK_MISMATCH", question_id=question_id)
        if set(source_ids) != route["source_ids"] or route_id != route["id"]:
            _finding(findings, "PREFLIGHT_APPROVAL_SOURCE_OR_ROUTE_MISMATCH", question_id=question_id)
        anchor_terms = [term for item in route["anchor_ids"] for term in plan["anchors"][item]["terms"]]
        target_terms = [term for item in route["target_ids"] for term in plan["targets"][item]["terms"]]
        if not _contains_any(raw["basis_confirmation"], anchor_terms):
            _finding(findings, "PREFLIGHT_BASIS_NOT_LINKED_TO_ANCHOR", question_id=question_id)
        if not _contains_any(raw["transition_confirmation"], target_terms):
            _finding(findings, "PREFLIGHT_TRANSITION_NOT_LINKED_TO_TARGET", question_id=question_id)
        if not _contains_any(raw["transition_confirmation"], route["terms"]):
            _finding(findings, "PREFLIGHT_TRANSITION_NOT_LINKED_TO_ROUTE", question_id=question_id)
        if raw["decision"] != "approve":
            _finding(findings, "PREFLIGHT_REVISE_REQUIRED", question_id=question_id, reviewer=reviewer)
        approved.add(question_id)
        valid_entries += 1
    for question_id in sorted(set(plans) - approved):
        _finding(findings, "PREFLIGHT_QUESTION_UNAPPROVED", question_id=question_id)
    return _report(findings, len(plans), valid_entries, inputs)


def _report(findings: list[dict], questions: int, approvals: int, inputs: dict) -> dict:
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "mcm-reasoning-preflight-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "questions": questions,
        "approvals": approvals,
        "inputs": inputs,
        "findings": findings,
        "interpretation": (
            "Passing confirms each workbench question has one compact, hash-locked approval explicitly marked as human "
            "that names the same "
            "frozen sources, anchors, mathematical targets, and selected route. It does not prove identity, mathematics, "
            "private reasoning, or final prose quality; post-draft correspondence must still be audited."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbench", type=Path)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.workbench, args.approval)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"REASONING PREFLIGHT {report['status'].upper()} questions={report['questions']} "
            f"approvals={report['approvals']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"})
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
