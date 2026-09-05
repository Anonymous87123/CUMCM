#!/usr/bin/env python3
"""Attach the current anonymous review transport to a historical holdout seal.

This does not reseal the candidate under current writing rules. It preserves the
historical rule hashes and explicitly refuses a current-release validation claim.

Public interface:
    python attach_legacy_blind_review.py attach holdout-seal.json --output addendum.json
    python attach_legacy_blind_review.py audit addendum.json --format text|json
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from adapter_core import sha256_file, write_json
from render_style_benchmark_review import audit_bundle, render_review


SEAL_SCHEMA = "aigc-tex-blind-holdout-seal/v1"
ADDENDUM_SCHEMA = "aigc-tex-blind-review-addendum/v1"
INHERITED = ("spec", "pairs", "key", "packet", "ratings_template")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _locked(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _verify_record(record: object, label: str) -> tuple[Path, list[dict]]:
    findings: list[dict] = []
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        return Path(), [{"severity": "error", "code": "LEGACY_RECORD_INVALID", "artifact": label}]
    path = Path(str(record["path"])).resolve()
    if not path.is_file():
        findings.append({"severity": "error", "code": "LEGACY_FILE_MISSING", "artifact": label, "path": str(path)})
        return path, findings
    actual = sha256_file(path)
    if actual.casefold() != str(record["sha256"]).casefold():
        findings.append({
            "severity": "error", "code": "LEGACY_FILE_DRIFT", "artifact": label,
            "path": str(path), "expected": record["sha256"], "actual": actual,
        })
    if isinstance(record.get("bytes"), int) and path.stat().st_size != record["bytes"]:
        findings.append({"severity": "error", "code": "LEGACY_BYTE_DRIFT", "artifact": label})
    return path, findings


def _rule_observations(rules: object) -> list[dict]:
    observations: list[dict] = []
    for index, record in enumerate(rules if isinstance(rules, list) else [], start=1):
        path = Path(str(record.get("path", ""))).resolve() if isinstance(record, dict) else Path()
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        expected = str(record.get("sha256", "")) if isinstance(record, dict) else ""
        observations.append({
            "index": index,
            "path": str(path),
            "expected_sha256": expected,
            "current_sha256": actual,
            "state": "unchanged" if exists and actual.casefold() == expected.casefold() else (
                "drifted" if exists else "missing"
            ),
        })
    return observations


def attach(seal_path: Path, output: Path) -> dict:
    seal_path = seal_path.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    seal = _load(seal_path)
    if seal.get("schema") != SEAL_SCHEMA or seal.get("state") != "SEALED_UNSCORED":
        raise ValueError("historical input must be an unscored TeX blind holdout seal")
    artifacts = seal.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("historical seal has no artifact map")
    inherited: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    findings: list[dict] = []
    for name in INHERITED:
        path, item_findings = _verify_record(artifacts.get(name), name)
        findings.extend(item_findings)
        paths[name] = path
        if isinstance(artifacts.get(name), dict):
            inherited[name] = copy.deepcopy(artifacts[name])
    if findings:
        raise ValueError(f"historical review inputs drifted: {findings}")
    page_path = paths["packet"].with_name("review-legacy.html")
    bundle_path = paths["packet"].with_name("review-bundle-legacy.json")
    rendered = render_review(paths["packet"], page_path, paths["ratings_template"], bundle_path)
    rules = copy.deepcopy(seal.get("rule_snapshot", []))
    observations = _rule_observations(rules)
    payload = {
        "schema": ADDENDUM_SCHEMA,
        "state": "LEGACY_SEAL_REVIEW_READY",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "release_id": seal.get("release_id"),
        "pair_count": seal.get("pair_count"),
        "parent_seal": _locked(seal_path),
        "inherited_artifacts": inherited,
        "review_page": _locked(Path(rendered["review_page"])),
        "review_bundle": _locked(Path(rendered["bundle"])),
        "historical_rule_snapshot": rules,
        "rule_state_observed_at_attachment": observations,
        "claims": {
            "pairs_resampled": False,
            "packet_changed": False,
            "candidate_regenerated": False,
            "historical_rule_hashes_replaced": False,
            "current_release_validation": False,
            "human_rating_completed": False,
        },
        "interpretation": (
            "This addendum upgrades only the anonymous review transport. It preserves the historical "
            "candidate, pair sample, packet, and recorded rule hashes; it is not evidence that the candidate "
            "was generated by the current rules."
        ),
    }
    write_json(output, payload)
    return {
        "schema": "aigc-tex-blind-review-attach-report/v1",
        "status": "pass",
        "pairs": payload["pair_count"],
        "rule_drift": sum(item["state"] != "unchanged" for item in observations),
        "review_page": rendered["review_page"],
        "output": str(output),
        "output_sha256": sha256_file(output),
    }


def audit(addendum_path: Path) -> dict:
    addendum_path = addendum_path.resolve()
    findings: list[dict] = []
    payload = _load(addendum_path)
    if payload.get("schema") != ADDENDUM_SCHEMA or payload.get("state") != "LEGACY_SEAL_REVIEW_READY":
        findings.append({"severity": "error", "code": "LEGACY_ADDENDUM_SCHEMA_OR_STATE_INVALID"})
    parent_path, parent_findings = _verify_record(payload.get("parent_seal"), "parent_seal")
    findings.extend(parent_findings)
    parent = None
    if not parent_findings:
        parent = _load(parent_path)
        if parent.get("schema") != SEAL_SCHEMA:
            findings.append({"severity": "error", "code": "LEGACY_PARENT_SCHEMA_INVALID"})
    inherited = payload.get("inherited_artifacts")
    if not isinstance(inherited, dict):
        findings.append({"severity": "error", "code": "LEGACY_INHERITED_ARTIFACTS_MISSING"})
        inherited = {}
    inherited_paths: dict[str, Path] = {}
    for name in INHERITED:
        path, item_findings = _verify_record(inherited.get(name), name)
        findings.extend(item_findings)
        inherited_paths[name] = path
        if parent is not None and inherited.get(name) != parent.get("artifacts", {}).get(name):
            findings.append({"severity": "error", "code": "LEGACY_PARENT_ARTIFACT_MISMATCH", "artifact": name})
    page_path, page_findings = _verify_record(payload.get("review_page"), "review_page")
    bundle_path, bundle_findings = _verify_record(payload.get("review_bundle"), "review_bundle")
    findings.extend(page_findings)
    findings.extend(bundle_findings)
    if not bundle_findings:
        review_report = audit_bundle(bundle_path)
        if review_report.get("status") != "pass":
            findings.append({
                "severity": "error", "code": "LEGACY_REVIEW_BUNDLE_INVALID",
                "review_findings": review_report.get("findings", []),
            })
        else:
            bundle = _load(bundle_path)
            if (
                bundle.get("packet", {}).get("sha256") != inherited.get("packet", {}).get("sha256")
                or bundle.get("ratings_template", {}).get("sha256")
                != inherited.get("ratings_template", {}).get("sha256")
                or bundle.get("review_page", {}).get("sha256") != payload.get("review_page", {}).get("sha256")
            ):
                findings.append({"severity": "error", "code": "LEGACY_REVIEW_LOCK_MISMATCH"})
    if parent is not None:
        if payload.get("release_id") != parent.get("release_id") or payload.get("pair_count") != parent.get("pair_count"):
            findings.append({"severity": "error", "code": "LEGACY_PARENT_METADATA_MISMATCH"})
        if payload.get("historical_rule_snapshot") != parent.get("rule_snapshot"):
            findings.append({"severity": "error", "code": "LEGACY_RULE_SNAPSHOT_REPLACED"})
    claims = payload.get("claims", {})
    required_false = (
        "pairs_resampled", "packet_changed", "candidate_regenerated",
        "historical_rule_hashes_replaced", "current_release_validation", "human_rating_completed",
    )
    if not isinstance(claims, dict) or any(claims.get(key) is not False for key in required_false):
        findings.append({"severity": "error", "code": "LEGACY_ADDENDUM_CLAIMS_INVALID"})
    current_rule_state = _rule_observations(payload.get("historical_rule_snapshot", []))
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "aigc-tex-blind-review-addendum-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "warnings": 0,
        "pairs": payload.get("pair_count"),
        "current_rule_drift": sum(item["state"] != "unchanged" for item in current_rule_state),
        "current_rule_state": current_rule_state,
        "findings": findings,
        "interpretation": (
            "PASS proves review-transport and historical-artifact integrity only. Rule drift is reported "
            "without relabelling the historical candidate as a current-release run."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    attach_parser = sub.add_parser("attach")
    attach_parser.add_argument("seal", type=Path)
    attach_parser.add_argument("--output", type=Path, required=True)
    attach_parser.add_argument("--format", choices=("text", "json"), default="text")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("addendum", type=Path)
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = attach(args.seal, args.output) if args.command == "attach" else audit(args.addendum)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"schema": "aigc-tex-blind-review-addendum-report/v1", "status": "fail", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"LEGACY BLIND REVIEW {args.command.upper()} {report['status'].upper()} "
            f"pairs={report.get('pairs', 0)} rule_drift={report.get('rule_drift', report.get('current_rule_drift', 0))}"
        )
        if report.get("review_page"):
            print(f"review_page={report['review_page']}")
        if report.get("error"):
            print(f"[ERROR] {report['error']}")
        for finding in report.get("findings", []):
            print(f"[{finding['severity'].upper()}] {finding['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
