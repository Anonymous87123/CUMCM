#!/usr/bin/env python3
"""Audit a source-bound scene-owner ledger for one benchmark candidate.

Public interface:
    python audit_benchmark_owner_ledger.py LEDGER.json --source SOURCE \
        --candidate CANDIDATE --document-type modeling|course-notes|research \
        --format text|json [--output REPORT.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file


SCHEMA = "aigc-benchmark-owner-ledger/v1"
REPORT_SCHEMA = "aigc-benchmark-owner-ledger-audit/v1"
OWNER_BY_DOCUMENT_TYPE = {
    "modeling": "deai-modeling-writing",
    "course-notes": "deai-course-notes",
    "research": "deai-research-writing",
}
REQUIRED_DECISION_FIELDS = {
    "modeling": {
        "source_anchor", "problem_object", "mathematical_change",
        "modeling_decision", "preserved_results", "action",
    },
    "course-notes": {
        "source_anchor", "source_identity", "teaching_function",
        "decisive_step", "preserved_conditions", "action",
    },
    "research": {
        "source_anchor", "claim", "evidence_boundary",
        "claim_strength", "preserved_objects", "action",
    },
}
FORBIDDEN_KEYS = {
    "detector_score", "ai_probability", "aigc_rate", "human_score",
    "authorship_probability", "hidden_chain_of_thought", "chain_of_thought",
}


def _nonempty(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(_nonempty(item) for item in value)
    return value is not None


def _forbidden(value: object, trail: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            location = f"{trail}.{key}"
            if str(key).casefold() in FORBIDDEN_KEYS:
                found.append(location)
            found.extend(_forbidden(item, location))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden(item, f"{trail}[{index}]"))
    return found


def audit(
    ledger_path: Path,
    source: Path,
    candidate: Path,
    document_type: str,
) -> dict:
    ledger_path = ledger_path.resolve()
    source = source.resolve()
    candidate = candidate.resolve()
    findings: list[dict] = []
    for label, path in (("ledger", ledger_path), ("source", source), ("candidate", candidate)):
        if not path.is_file():
            findings.append({"severity": "error", "code": "OWNER_FILE_MISSING", "label": label})
    if findings:
        return _report(ledger_path, source, candidate, document_type, {}, findings)
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_JSON_INVALID", "error": str(exc)})
        return _report(ledger_path, source, candidate, document_type, {}, findings)
    if not isinstance(ledger, dict) or ledger.get("schema") != SCHEMA:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_SCHEMA_INVALID"})
        ledger = ledger if isinstance(ledger, dict) else {}
    expected_owner = OWNER_BY_DOCUMENT_TYPE[document_type]
    if ledger.get("document_type") != document_type or ledger.get("provider") != expected_owner:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_SCENE_OR_PROVIDER_INVALID"})
    source_sha = sha256_file(source)
    candidate_sha = sha256_file(candidate)
    if ledger.get("source_sha256") != source_sha or ledger.get("candidate_sha256") != candidate_sha:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_SOURCE_BINDING_INVALID"})
    if ledger.get("mode") != "REWRITE":
        findings.append({"severity": "error", "code": "OWNER_LEDGER_MODE_INVALID"})
    claims = ledger.get("claims")
    if not isinstance(claims, dict) or claims.get("hidden_reasoning_recorded") is not False \
            or claims.get("academic_correctness_proven") is not False:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_CLAIMS_INVALID"})
    forbidden = _forbidden(ledger)
    if forbidden:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_FORBIDDEN_KEYS", "paths": forbidden})
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        findings.append({"severity": "error", "code": "OWNER_LEDGER_DECISIONS_MISSING"})
        decisions = []
    required = REQUIRED_DECISION_FIELDS[document_type]
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            findings.append({"severity": "error", "code": "OWNER_LEDGER_DECISION_INVALID", "index": index})
            continue
        missing = sorted(field for field in required if not _nonempty(decision.get(field)))
        if missing:
            findings.append({
                "severity": "error", "code": "OWNER_LEDGER_DECISION_FIELDS_MISSING",
                "index": index, "fields": missing,
            })
    unresolved = ledger.get("unresolved")
    if not isinstance(unresolved, list):
        findings.append({"severity": "error", "code": "OWNER_LEDGER_UNRESOLVED_INVALID"})
    elif unresolved:
        findings.append({
            "severity": "error", "code": "OWNER_LEDGER_UNRESOLVED_REMAINS",
            "count": len(unresolved),
        })
    return _report(ledger_path, source, candidate, document_type, ledger, findings)


def _report(
    ledger_path: Path,
    source: Path,
    candidate: Path,
    document_type: str,
    ledger: dict,
    findings: list[dict],
) -> dict:
    errors = sum(item.get("severity") == "error" for item in findings)
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "document_type": document_type,
        "provider": OWNER_BY_DOCUMENT_TYPE[document_type],
        "ledger": {
            "path": str(ledger_path),
            "sha256": sha256_file(ledger_path) if ledger_path.is_file() else None,
        },
        "source": {
            "path": str(source),
            "sha256": sha256_file(source) if source.is_file() else None,
        },
        "candidate": {
            "path": str(candidate),
            "sha256": sha256_file(candidate) if candidate.is_file() else None,
        },
        "decisions": len(ledger.get("decisions", [])) if isinstance(ledger.get("decisions"), list) else 0,
        "errors": errors,
        "findings": findings,
        "claims": {
            "role_execution_evidenced": errors == 0,
            "human_authorship_proven": False,
            "academic_correctness_proven": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--document-type", choices=sorted(OWNER_BY_DOCUMENT_TYPE), required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.ledger, args.source, args.candidate, args.document_type)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"BENCHMARK OWNER LEDGER {report['status'].upper()} "
            f"provider={report['provider']} decisions={report['decisions']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            print(f"[ERROR] {finding['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
