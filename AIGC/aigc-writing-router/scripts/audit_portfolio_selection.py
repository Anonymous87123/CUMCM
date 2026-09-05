#!/usr/bin/env python3
"""Verify that a selected long-form target is backed by fresh role receipts.

Public interface:
    python audit_portfolio_selection.py <portfolio-plan.json> <candidate>
        --candidate-id H1|SOURCE --source-sha256 HEX --format text|json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PLAN_SCHEMA = "aigc-portfolio-orchestration/v1"
REPORT_SCHEMA = "aigc-portfolio-selection-audit/v1"
RESOLVED = {"complete", "eligible", "complete_local", "waived"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dependency(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def audit(plan_path: Path, candidate: Path, candidate_id: str, source_sha256: str) -> dict[str, Any]:
    plan_path = plan_path.resolve()
    candidate = candidate.resolve()
    payload = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    findings: list[dict[str, Any]] = []
    if payload.get("schema") != PLAN_SCHEMA:
        findings.append({"code": "PORTFOLIO_SCHEMA_MISMATCH"})
    if payload.get("source", {}).get("sha256") != source_sha256:
        findings.append({"code": "PORTFOLIO_SOURCE_MISMATCH"})

    selection = payload.get("selection", {})
    expected_status = "source_retained" if candidate_id == "SOURCE" else "accepted"
    if selection.get("status") != expected_status or selection.get("accepted") != candidate_id:
        findings.append({"code": "PORTFOLIO_SELECTION_MISMATCH"})
    decision_path = Path(str(selection.get("decision_path", "")))
    if (
        not decision_path.is_file()
        or sha256_file(decision_path) != selection.get("decision_sha256")
    ):
        findings.append({"code": "PORTFOLIO_DECISION_DRIFT", "path": str(decision_path)})

    branches = payload.get("branches", [])
    selected = None
    expected_candidate_hash = source_sha256
    if candidate_id != "SOURCE":
        selected = next((item for item in branches if item.get("id") == candidate_id), None)
        if selected is None or selected.get("status") != "eligible":
            findings.append({"code": "PORTFOLIO_CANDIDATE_NOT_ELIGIBLE"})
        else:
            expected_candidate_hash = str(selected.get("output_sha256", ""))
            if selected.get("provider") == "humanize-academic-chinese" and not payload.get("claims", {}).get("native_generation_ran"):
                findings.append({"code": "HUMANIZE_NATIVE_EXECUTION_NOT_PROVEN"})
    if not candidate.is_file() or sha256_file(candidate) != expected_candidate_hash:
        findings.append({"code": "PORTFOLIO_TARGET_HASH_MISMATCH", "path": str(candidate)})

    for group_name in ("stages", "branches", "reviewers", "workbenches"):
        for item in payload.get(group_name, []):
            if item.get("mandatory") and item.get("status") not in RESOLVED:
                findings.append({
                    "code": "PORTFOLIO_REQUIRED_ROLE_UNRESOLVED",
                    "group": group_name, "provider": item.get("provider"),
                    "status": item.get("status"),
                })
            receipt_path = item.get("receipt_path")
            receipt_sha = item.get("receipt_sha256")
            if receipt_path or receipt_sha:
                path = Path(str(receipt_path or ""))
                if not path.is_file() or sha256_file(path) != receipt_sha:
                    findings.append({
                        "code": "PORTFOLIO_RECEIPT_DRIFT",
                        "group": group_name, "provider": item.get("provider"),
                        "path": str(path),
                    })
            output_path = item.get("output_path")
            output_sha = item.get("output_sha256")
            if output_path or output_sha:
                path = Path(str(output_path or ""))
                if not path.is_file() or sha256_file(path) != output_sha:
                    findings.append({
                        "code": "PORTFOLIO_CANDIDATE_DRIFT",
                        "provider": item.get("provider"), "path": str(path),
                    })
            for token, evidence in item.get("evidence", {}).items():
                if not isinstance(evidence, dict):
                    findings.append({"code": "PORTFOLIO_EVIDENCE_INVALID", "token": token})
                    continue
                path = Path(str(evidence.get("path", "")))
                if not path.is_file() or sha256_file(path) != evidence.get("sha256"):
                    findings.append({
                        "code": "PORTFOLIO_EVIDENCE_DRIFT",
                        "provider": item.get("provider"), "token": token, "path": str(path),
                    })

    required_claims = payload.get("claims", {})
    if not required_claims.get("all_roles_resolved"):
        findings.append({"code": "PORTFOLIO_ROLE_RESOLUTION_NOT_RECORDED"})
    if candidate_id != "SOURCE" and not required_claims.get("all_roles_complete"):
        findings.append({"code": "PORTFOLIO_ROLE_COMPLETION_NOT_RECORDED"})

    dependencies = [
        _dependency(Path(__file__).resolve().parent / "orchestrate_portfolio.py", "portfolio-state-machine"),
        _dependency(Path(__file__).resolve().parents[1] / "references" / "role-contracts.json", "role-contracts"),
    ]
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass" if not findings else "fail",
        "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
        "source_sha256": source_sha256,
        "candidate": {
            "id": candidate_id, "path": str(candidate),
            "sha256": sha256_file(candidate) if candidate.is_file() else None,
        },
        "roles": {
            "content": len(payload.get("stages", [])),
            "candidates": len(branches),
            "reviewers": len(payload.get("reviewers", [])),
            "workbenches": len(payload.get("workbenches", [])),
        },
        "dependencies": dependencies,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = audit(args.plan, args.candidate, args.candidate_id, args.source_sha256)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"schema": REPORT_SCHEMA, "status": "fail", "error": str(exc), "findings": []}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"PORTFOLIO SELECTION {report['status'].upper()}")
        for item in report.get("findings", []):
            print(f"[FAIL] {item['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
