#!/usr/bin/env python3
"""Audit the read-only auxiliary evidence attached to a matrix chain report.

The audit deliberately checks evidence boundaries rather than quality.  It
verifies that every candidate has a hash-locked ``ai-check`` diagnostic and a
hash-locked ``AI_paper`` MCM workbench plan, and that neither artifact claims
authorship, detector verdicts, candidate generation, or candidate selection.

Public interface:
    python audit_auxiliary_roles.py CHAIN-REPORT.json --format text|json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file


REPORT_SCHEMA = "aigc-auxiliary-role-audit/v1"
CHAIN_SCHEMA = "aigc-matrix-dev-chain/v2"
ADAPTER_SCHEMA = "aigc-adapter-run/v1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _locked(path_value: object, expected_sha: object, label: str, errors: list[dict]) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        errors.append({"code": "AUXILIARY_PATH_MISSING", "label": label})
        return None
    path = Path(path_value).resolve()
    if not path.is_file():
        errors.append({"code": "AUXILIARY_FILE_MISSING", "label": label, "path": str(path)})
        return None
    actual = sha256_file(path)
    if not isinstance(expected_sha, str) or actual != expected_sha:
        errors.append({
            "code": "AUXILIARY_HASH_DRIFT",
            "label": label,
            "path": str(path),
            "expected": expected_sha,
            "actual": actual,
        })
    return path


def audit_payload(payload: dict) -> dict:
    errors: list[dict] = []
    if payload.get("schema") != CHAIN_SCHEMA:
        errors.append({"code": "CHAIN_SCHEMA_MISMATCH", "actual": payload.get("schema")})
    if payload.get("status") != "pass":
        errors.append({"code": "CHAIN_NOT_PASS", "actual": payload.get("status")})
    if payload.get("mechanical_chain_complete") is not True:
        errors.append({"code": "CHAIN_COMPLETENESS_NOT_DECLARED"})
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        errors.append({"code": "CHAIN_RECORDS_MISSING"})
        records = []
    if payload.get("candidates") != len(records):
        errors.append({"code": "CHAIN_CANDIDATE_COUNT_MISMATCH"})

    auxiliary_roles = payload.get("auxiliary_roles")
    if not isinstance(auxiliary_roles, dict):
        errors.append({"code": "CHAIN_AUXILIARY_ROLES_MISSING"})
        auxiliary_roles = {}
    if auxiliary_roles.get("native_execution_claim") is not False:
        errors.append({"code": "CHAIN_NATIVE_AUXILIARY_CLAIM_UNBOUNDED"})
    workbench_plan = _locked(
        auxiliary_roles.get("AI_paper_workbench_plan"),
        auxiliary_roles.get("AI_paper_workbench_plan_sha256"),
        "chain.AI_paper_workbench_plan",
        errors,
    )

    if workbench_plan is not None:
        plan = _load(workbench_plan)
        embedded = plan.get("embedded_capabilities")
        plan_data = plan.get("plan")
        selected = plan_data.get("selected_embedded_capability_ids") if isinstance(plan_data, dict) else None
        claims = plan.get("claims")
        if (
            plan.get("schema") != ADAPTER_SCHEMA
            or plan.get("status") != "pass"
            or not isinstance(embedded, dict)
            or embedded.get("status") != "pass"
            or embedded.get("count") != 16
            or not isinstance(selected, list)
            or len(selected) != embedded.get("selected_count")
            or len(set(selected)) != len(selected)
            or not isinstance(claims, dict)
            or claims.get("authorship_or_detector_verdict") is not False
        ):
            errors.append({"code": "AI_PAPER_PLAN_UNBOUNDED_OR_INCOMPLETE"})

    for index, record in enumerate(records):
        label = f"records[{index}]"
        auxiliary = record.get("auxiliary_reviews") if isinstance(record, dict) else None
        if not isinstance(auxiliary, dict):
            errors.append({"code": "CANDIDATE_AUXILIARY_MISSING", "label": label})
            continue
        ai_check = auxiliary.get("ai_check")
        if not isinstance(ai_check, dict):
            errors.append({"code": "AI_CHECK_EVIDENCE_MISSING", "label": label})
        else:
            if ai_check.get("execution_level") != "ADAPTER_DIAGNOSTIC_ONLY":
                errors.append({"code": "AI_CHECK_EXECUTION_LEVEL_INVALID", "label": label})
            claims = ai_check.get("claims")
            if (
                ai_check.get("provider") != "ai-check"
                or ai_check.get("adapter_package") != "humanize-main"
                or not isinstance(claims, dict)
                or claims.get("authorship_or_detector_verdict") is not False
                or claims.get("candidate_selection") is not False
            ):
                errors.append({"code": "AI_CHECK_CLAIMS_UNBOUNDED", "label": label})
            report_path = _locked(
                ai_check.get("report"), ai_check.get("sha256"), f"{label}.ai_check.report", errors,
            )
            if report_path is not None:
                report = _load(report_path)
                report_claims = report.get("claims")
                if (
                    report.get("schema") != ADAPTER_SCHEMA
                    or report.get("status") != "pass"
                    or not isinstance(report_claims, dict)
                    or report_claims.get("authorship_or_detector_verdict") is not False
                ):
                    errors.append({"code": "AI_CHECK_REPORT_UNBOUNDED", "label": label})

        workbench = auxiliary.get("AI_paper_workbench")
        if not isinstance(workbench, dict):
            errors.append({"code": "AI_PAPER_CANDIDATE_EVIDENCE_MISSING", "label": label})
        else:
            if (
                workbench.get("provider") != "AI_paper"
                or workbench.get("execution_level") != "WORKBENCH_PLAN_ONLY"
                or workbench.get("plan") != auxiliary_roles.get("AI_paper_workbench_plan")
                or workbench.get("sha256") != auxiliary_roles.get("AI_paper_workbench_plan_sha256")
            ):
                errors.append({"code": "AI_PAPER_CANDIDATE_PLAN_DRIFT", "label": label})
            claims = workbench.get("claims")
            if (
                not isinstance(claims, dict)
                or claims.get("candidate_generation") is not False
                or claims.get("candidate_selection") is not False
            ):
                errors.append({"code": "AI_PAPER_CLAIMS_UNBOUNDED", "label": label})

    return {
        "schema": REPORT_SCHEMA,
        "status": "pass" if not errors else "fail",
        "chain_schema": payload.get("schema"),
        "candidates_checked": len(records),
        "errors": len(errors),
        "findings": errors,
        "claims": {
            "auxiliary_evidence_hashes_verified": not bool(errors),
            "human_style_quality_proven": False,
            "authorship_proven": False,
            "detector_outcome_predicted": False,
        },
    }


def audit(path: Path) -> dict:
    return audit_payload(_load(path.resolve()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chain_report", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.chain_report)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AUXILIARY ROLE AUDIT {report['status'].upper()} "
            f"candidates={report['candidates_checked']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            print(f"[{finding['code']}] {finding.get('label', '')}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
