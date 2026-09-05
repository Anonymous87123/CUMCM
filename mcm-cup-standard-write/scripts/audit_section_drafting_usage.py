#!/usr/bin/env python3
"""Audit a packet-to-candidate section drafting lineage receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_section_drafting_packets import sha256_file
from prepare_section_drafting_usage import SCHEMA, _scopes, _signature


AUDIT_SCHEMA = "mcm-section-drafting-usage-audit/v1"


def _locked_matches(record: object, path: Path) -> bool:
    if not isinstance(record, dict) or not path.is_file():
        return False
    return record.get("sha256") == sha256_file(path) and record.get("bytes") == path.stat().st_size


def audit(source: Path, candidate: Path, packet_index: Path, usage_path: Path) -> dict:
    findings: list[dict] = []
    source = source.resolve()
    candidate = candidate.resolve()
    packet_index = packet_index.resolve()
    usage_path = usage_path.resolve()
    try:
        usage = json.loads(usage_path.read_text(encoding="utf-8-sig"))
        index = json.loads(packet_index.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"schema": AUDIT_SCHEMA, "status": "fail", "errors": 1, "findings": [{"code": "USAGE_INPUT_INVALID", "detail": str(exc)}]}
    if not isinstance(usage, dict):
        return {"schema": AUDIT_SCHEMA, "status": "fail", "errors": 1, "findings": [{"code": "USAGE_NOT_OBJECT"}]}
    if usage.get("schema") != SCHEMA or usage.get("status") != "pass":
        findings.append({"code": "USAGE_SCHEMA_OR_STATUS_INVALID"})
    if not isinstance(index, dict) or index.get("schema") != "mcm-section-drafting-packet-index/v1" or index.get("status") != "pass":
        findings.append({"code": "USAGE_PACKET_INDEX_INVALID"})
    if not _locked_matches(usage.get("source"), source):
        findings.append({"code": "USAGE_SOURCE_DRIFT"})
    if not _locked_matches(usage.get("candidate"), candidate):
        findings.append({"code": "USAGE_CANDIDATE_DRIFT"})
    if not _locked_matches(usage.get("packet_index"), packet_index):
        findings.append({"code": "USAGE_PACKET_INDEX_DRIFT"})
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    if execution.get("consumption_proven") is not False:
        findings.append({"code": "USAGE_OVERCLAIMS_CONSUMPTION"})
    if execution.get("mode") != "section_lineage_declared" or execution.get("author_kind") not in {"model", "human", "mixed"} or not str(execution.get("run_id") or "").strip():
        findings.append({"code": "USAGE_EXECUTION_INVALID"})
    claims = usage.get("claims") if isinstance(usage.get("claims"), dict) else {}
    if claims.get("packet_to_candidate_hashes_bound") is not True or claims.get("model_reading_proven") is not False or claims.get("hidden_chain_of_thought_requested") is not False or claims.get("human_naturalness_proven") is not False:
        findings.append({"code": "USAGE_CLAIMS_INVALID"})
    source_scopes = _scopes(source) if source.is_file() else {}
    candidate_scopes = _scopes(candidate) if candidate.is_file() else {}
    if _signature(source_scopes) != _signature(candidate_scopes):
        findings.append({"code": "USAGE_SECTION_ORDER_OR_METADATA_DRIFT"})
    if usage.get("target_signature") != _signature(source_scopes):
        findings.append({"code": "USAGE_TARGET_SIGNATURE_DRIFT"})
    records = index.get("packets") if isinstance(index, dict) and isinstance(index.get("packets"), list) else []
    packet_records = {str(item.get("target_id")): item for item in records if isinstance(item, dict) and item.get("target_id")}
    source_ids = set(source_scopes)
    candidate_ids = set(candidate_scopes)
    packet_ids = set(packet_records)
    if source_ids != candidate_ids or source_ids != packet_ids:
        findings.append({"code": "USAGE_TARGET_SET_MISMATCH", "source": sorted(source_ids), "candidate": sorted(candidate_ids), "packets": sorted(packet_ids)})
    expected_ids = source_ids
    index_source = index.get("source") if isinstance(index, dict) and isinstance(index.get("source"), dict) else {}
    if index_source.get("sha256") != (sha256_file(source) if source.is_file() else None):
        findings.append({"code": "USAGE_PACKET_INDEX_SOURCE_MISMATCH"})
    if index.get("packet_count") != len(records):
        findings.append({"code": "USAGE_PACKET_COUNT_MISMATCH"})
    sections = usage.get("sections") if isinstance(usage.get("sections"), list) else []
    actual_ids = {str(item.get("target_id")) for item in sections if isinstance(item, dict)}
    if actual_ids != expected_ids or len(actual_ids) != len(sections):
        findings.append({"code": "USAGE_SECTION_SET_MISMATCH", "expected": sorted(expected_ids), "actual": sorted(actual_ids)})
    for item in sections:
        if not isinstance(item, dict):
            findings.append({"code": "USAGE_SECTION_INVALID"})
            continue
        target_id = str(item.get("target_id", ""))
        if target_id not in expected_ids:
            continue
        source_scope = source_scopes[target_id]
        candidate_scope = candidate_scopes[target_id]
        packet_record = packet_records[target_id]
        packet = item.get("packet") if isinstance(item.get("packet"), dict) else {}
        packet_path = Path(str(packet.get("path", ""))).resolve()
        if not _locked_matches(packet, packet_path) or packet.get("sha256") != packet_record.get("sha256") or packet.get("bytes") != packet_record.get("bytes"):
            findings.append({"code": "USAGE_PACKET_DRIFT", "target_id": target_id})
        source_section = item.get("source_section") if isinstance(item.get("source_section"), dict) else {}
        candidate_section = item.get("candidate_section") if isinstance(item.get("candidate_section"), dict) else {}
        if (
            source_section.get("tex_sha256") != source_scope["sha256"]
            or source_section.get("tex_chars") != source_scope["chars"]
            or source_section.get("visible_sha256") != source_scope["visible_sha256"]
            or source_section.get("visible_chars") != source_scope["visible_chars"]
        ):
            findings.append({"code": "USAGE_SOURCE_SECTION_DRIFT", "target_id": target_id})
        if (
            candidate_section.get("tex_sha256") != candidate_scope["sha256"]
            or candidate_section.get("tex_chars") != candidate_scope["chars"]
            or candidate_section.get("visible_sha256") != candidate_scope["visible_sha256"]
            or candidate_section.get("visible_chars") != candidate_scope["visible_chars"]
        ):
            findings.append({"code": "USAGE_CANDIDATE_SECTION_DRIFT", "target_id": target_id})
        expected_disposition = "retained" if source_scope["sha256"] == candidate_scope["sha256"] else "generated"
        if item.get("disposition") != expected_disposition:
            findings.append({"code": "USAGE_DISPOSITION_DRIFT", "target_id": target_id})
        for key in ("title", "role", "question_id"):
            if item.get(key) != source_scope[key] or item.get(key) != candidate_scope[key]:
                findings.append({"code": "USAGE_TARGET_METADATA_DRIFT", "target_id": target_id, "field": key})
    errors = len(findings)
    return {
        "schema": AUDIT_SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "sections": len(sections),
        "findings": findings,
        "source": {"path": str(source), "sha256": sha256_file(source) if source.is_file() else None},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate) if candidate.is_file() else None},
        "packet_index": {"path": str(packet_index), "sha256": sha256_file(packet_index) if packet_index.is_file() else None},
        "interpretation": (
            "Passing proves section hashes and packet lineage are consistent. "
            "It does not prove model reading, private reasoning, mathematical correctness, or naturalness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--packet-index", type=Path, required=True)
    parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.source, args.candidate, args.packet_index, args.usage)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SECTION DRAFTING USAGE AUDIT {report['status'].upper()} sections={report['sections']} errors={report['errors']}")
        for finding in report["findings"]:
            print(f"[ERROR] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
