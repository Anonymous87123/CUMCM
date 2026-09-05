#!/usr/bin/env python3
"""Audit every artifact and rule hash in a sealed TeX blind holdout.

Public interface:
    python audit_tex_blind_holdout.py holdout-seal.json --format text|json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from adapter_core import sha256_file
from render_style_benchmark_review import audit_bundle as audit_review_bundle


SCHEMA = "aigc-tex-blind-holdout-seal/v1"
SCORING_PROTOCOL = "aigc-blind-scoring/v2"
REQUIRED_ARTIFACTS = {
    "spec", "pairs", "key", "packet", "ratings_template", "review_page", "review_bundle",
}


def audit(path: Path) -> dict[str, Any]:
    path = path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA}")
    errors: list[dict[str, Any]] = []
    checked = 0
    artifacts = payload.get("artifacts")
    rules = payload.get("rule_snapshot")
    scoring_rules = payload.get("scoring_rule_snapshot")
    if not isinstance(artifacts, dict) or not artifacts:
        errors.append({"code": "ARTIFACTS_MISSING"})
        artifacts = {}
    missing_artifacts = sorted(REQUIRED_ARTIFACTS - set(artifacts))
    if missing_artifacts:
        errors.append({"code": "REQUIRED_ARTIFACTS_MISSING", "artifacts": missing_artifacts})
    if not isinstance(rules, list) or not rules:
        errors.append({"code": "RULE_SNAPSHOT_MISSING"})
        rules = []
    if not isinstance(scoring_rules, list) or not scoring_rules:
        errors.append({"code": "SCORING_RULE_SNAPSHOT_MISSING"})
        scoring_rules = []
    records = [(f"artifact:{name}", record) for name, record in artifacts.items()]
    records.extend((f"rule:{index}", record) for index, record in enumerate(rules, start=1))
    records.extend((f"scoring-rule:{index}", record) for index, record in enumerate(scoring_rules, start=1))
    for label, record in records:
        if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
            errors.append({"code": "INVALID_RECORD", "label": label})
            continue
        target = Path(str(record["path"])).resolve()
        if not target.is_file():
            errors.append({"code": "FILE_MISSING", "label": label, "path": str(target)})
            continue
        checked += 1
        actual_sha = sha256_file(target)
        if actual_sha.casefold() != str(record["sha256"]).casefold():
            errors.append({
                "code": "SHA256_DRIFT",
                "label": label,
                "path": str(target),
                "expected": record["sha256"],
                "actual": actual_sha,
            })
        expected_bytes = record.get("bytes")
        if isinstance(expected_bytes, int) and target.stat().st_size != expected_bytes:
            errors.append({
                "code": "BYTE_COUNT_DRIFT",
                "label": label,
                "path": str(target),
                "expected": expected_bytes,
                "actual": target.stat().st_size,
            })
    if payload.get("state") not in {"SEALED_UNSCORED", "SCORED_HOLDOUT_SEALED"}:
        errors.append({"code": "INVALID_STATE", "value": payload.get("state")})
    requirements = payload.get("release_requirements")
    if not isinstance(requirements, dict) or requirements.get("model_ratings_are_diagnostic_only") is not True:
        errors.append({"code": "MODEL_BOUNDARY_MISSING"})
    if not isinstance(requirements, dict) or requirements.get("review_page_provenance_free_bundle_required") is not True:
        errors.append({"code": "REVIEW_BUNDLE_REQUIREMENT_MISSING"})
    if payload.get("scoring_protocol") != SCORING_PROTOCOL:
        errors.append({"code": "SCORING_PROTOCOL_INVALID", "value": payload.get("scoring_protocol")})
    if not isinstance(requirements, dict) or requirements.get("scoring_protocol_frozen") is not True:
        errors.append({"code": "SCORING_PROTOCOL_REQUIREMENT_MISSING"})
    bundle_record = artifacts.get("review_bundle") if isinstance(artifacts, dict) else None
    if isinstance(bundle_record, dict) and bundle_record.get("path"):
        bundle_path = Path(str(bundle_record["path"])).resolve()
        if bundle_path.is_file():
            review_report = audit_review_bundle(bundle_path)
            if review_report.get("status") != "pass":
                errors.append({
                    "code": "REVIEW_BUNDLE_INVALID",
                    "findings": review_report.get("findings", []),
                })
            else:
                bundle = json.loads(bundle_path.read_text(encoding="utf-8-sig"))
                for seal_name, bundle_name in (
                    ("packet", "packet"),
                    ("ratings_template", "ratings_template"),
                    ("review_page", "review_page"),
                ):
                    if (
                        str(artifacts.get(seal_name, {}).get("sha256", "")).casefold()
                        != str(bundle.get(bundle_name, {}).get("sha256", "")).casefold()
                    ):
                        errors.append({"code": "REVIEW_BUNDLE_LOCK_MISMATCH", "artifact": seal_name})
    return {
        "schema": "aigc-tex-blind-holdout-audit/v1",
        "status": "pass" if not errors else "fail",
        "seal": str(path),
        "seal_sha256": sha256_file(path),
        "state": payload.get("state"),
        "release_id": payload.get("release_id"),
        "pair_count": payload.get("pair_count"),
        "checked_files": checked,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seal", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = audit(args.seal)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {
            "schema": "aigc-tex-blind-holdout-audit/v1",
            "status": "fail",
            "errors": [{"code": "READ_ERROR", "message": str(exc)}],
        }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"TEX BLIND HOLDOUT AUDIT {report['status'].upper()} "
            f"files={report.get('checked_files', 0)} pairs={report.get('pair_count', 0)}"
        )
        for error in report.get("errors", []):
            print(f"[ERROR] {error.get('code')} {error.get('label', '')} {error.get('path', '')}".rstrip())
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
