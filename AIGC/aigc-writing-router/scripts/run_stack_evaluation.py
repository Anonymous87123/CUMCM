#!/usr/bin/env python3
"""Audit one complete AIGC writing-stack evaluation bundle.

Public interface:
    python run_stack_evaluation.py <evaluation.json> --format text|json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import find_package, read_registry, sha256_file
from merge_style_benchmark_ratings import audit_merge_report
from route_aigc_tools import select_route


SCHEMA = "aigc-stack-evaluation/v1"
STAGE_SCHEMA = "aigc-stage-evidence/v1"
BLIND_SCHEMA = "aigc-blind-score/v1"
ALLOWED_CLAIMS = {
    "mechanical_fidelity",
    "role_chain_complete",
    "human_preference_observed",
}
FORBIDDEN_KEYS = {
    "detector_score", "detector_scores", "ai_probability", "aigc_rate",
    "authorship_probability", "human_score", "human_probability",
}


def _add(findings: list[dict], severity: str, code: str, **detail: object) -> None:
    findings.append({"severity": severity, "code": code, **detail})


def _resolve(base: Path, raw: object) -> Path:
    path = Path(str(raw))
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _load_locked_json(
    base: Path,
    record: object,
    findings: list[dict],
    label: str,
) -> tuple[dict | None, Path | None]:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        _add(findings, "error", "LOCKED_REPORT_RECORD_INVALID", label=label)
        return None, None
    path = _resolve(base, record["path"])
    if not path.is_file():
        _add(findings, "error", "LOCKED_REPORT_MISSING", label=label, path=str(path))
        return None, path
    actual = sha256_file(path)
    if actual != record.get("sha256"):
        _add(
            findings, "error", "LOCKED_REPORT_DRIFT", label=label,
            expected=record.get("sha256"), actual=actual, path=str(path),
        )
        return None, path
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), path
    except json.JSONDecodeError as exc:
        _add(findings, "error", "LOCKED_REPORT_JSON_INVALID", label=label, error=str(exc))
        return None, path


def _verify_file_record(
    base: Path,
    record: object,
    findings: list[dict],
    label: str,
) -> Path | None:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        _add(findings, "error", "FILE_RECORD_INVALID", label=label)
        return None
    path = _resolve(base, record["path"])
    if not path.is_file():
        _add(findings, "error", "FILE_RECORD_MISSING", label=label, path=str(path))
        return None
    actual = sha256_file(path)
    if actual != record.get("sha256"):
        _add(
            findings, "error", "FILE_RECORD_DRIFT", label=label,
            expected=record.get("sha256"), actual=actual, path=str(path),
        )
        return None
    return path


def _walk_forbidden_keys(value: object, trail: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            location = f"{trail}.{key}"
            if str(key).casefold() in FORBIDDEN_KEYS:
                found.append(location)
            found.extend(_walk_forbidden_keys(item, location))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_forbidden_keys(item, f"{trail}[{index}]"))
    return found


def _verify_stage_evidence(
    base: Path,
    records: object,
    required_providers: set[str],
    source_sha256: str,
    candidate_sha256: str,
    findings: list[dict],
) -> set[str]:
    covered: set[str] = set()
    if not isinstance(records, list):
        _add(findings, "error", "STAGE_EVIDENCE_LIST_INVALID")
        return covered
    for index, record in enumerate(records):
        label = f"stage_evidence[{index}]"
        payload, stage_path = _load_locked_json(base, record, findings, label)
        if payload is None:
            continue
        provider = str(payload.get("provider", ""))
        if payload.get("schema") != STAGE_SCHEMA:
            _add(findings, "error", "STAGE_EVIDENCE_SCHEMA_MISMATCH", label=label)
        if provider not in required_providers:
            _add(findings, "error", "STAGE_EVIDENCE_PROVIDER_UNEXPECTED", provider=provider)
        if provider in covered:
            _add(findings, "error", "STAGE_EVIDENCE_PROVIDER_DUPLICATE", provider=provider)
        if payload.get("status") != "pass":
            _add(
                findings, "error", "STAGE_EVIDENCE_NOT_PASS",
                provider=provider, status=payload.get("status"),
            )
        if payload.get("source_sha256") != source_sha256:
            _add(findings, "error", "STAGE_EVIDENCE_SOURCE_MISMATCH", provider=provider)
        output_sha256 = payload.get("output_sha256")
        if output_sha256 is not None and output_sha256 != candidate_sha256:
            _add(findings, "error", "STAGE_EVIDENCE_OUTPUT_MISMATCH", provider=provider)
        artifacts = payload.get("artifacts", [])
        if not isinstance(artifacts, list) or not artifacts:
            _add(findings, "error", "STAGE_EVIDENCE_ARTIFACTS_MISSING", provider=provider)
        else:
            artifact_base = stage_path.parent if stage_path is not None else base
            for artifact_index, artifact in enumerate(artifacts):
                _verify_file_record(
                    artifact_base, artifact, findings,
                    f"stage_evidence[{index}].artifacts[{artifact_index}]",
                )
        covered.add(provider)
    for missing in sorted(required_providers - covered):
        _add(findings, "error", "STAGE_EVIDENCE_MISSING", provider=missing)
    return covered


def _verify_candidate_report(
    base: Path,
    record: object,
    registry: dict,
    provider: str,
    source_sha256: str,
    candidate_sha256: str,
    findings: list[dict],
) -> dict | None:
    payload, _ = _load_locked_json(base, record, findings, "candidate_verification")
    if payload is None:
        return None
    try:
        package = find_package(registry, provider)
    except ValueError as exc:
        _add(findings, "error", "CANDIDATE_PROVIDER_UNKNOWN", provider=provider, error=str(exc))
        return payload
    expected_package = str(package.get("directory"))
    checks = {
        "schema": payload.get("schema") == "aigc-adapter-run/v1",
        "package": payload.get("package") == expected_package,
        "action": payload.get("action") == "verify-candidate",
        "status": payload.get("status") == "pass",
        "source": payload.get("source", {}).get("sha256") == source_sha256,
        "candidate": payload.get("candidate", {}).get("sha256") == candidate_sha256,
        "human_review": payload.get("human_review_required") is True,
    }
    for field, passed in checks.items():
        if not passed:
            _add(
                findings, "error", "CANDIDATE_VERIFICATION_CONTRACT_FAILED",
                field=field, provider=provider,
            )
    return payload


def _verify_blind_score(
    base: Path,
    record: object,
    candidate_id: str,
    baseline_id: str,
    findings: list[dict],
) -> dict | None:
    payload, _ = _load_locked_json(base, record, findings, "blind_score")
    if payload is None:
        return None
    if (
        payload.get("schema") != BLIND_SCHEMA
        or payload.get("status") != "pass"
        or payload.get("scoring_protocol") != "aigc-blind-scoring/v2"
    ):
        _add(findings, "error", "BLIND_SCORE_NOT_PASS")
    if payload.get("errors") != 0 or payload.get("warnings") != 0:
        _add(
            findings, "error", "BLIND_SCORE_COVERAGE_NOT_FORMAL",
            errors=payload.get("errors"), warnings=payload.get("warnings"),
        )
    coverage = payload.get("effective_human_coverage", {})
    if payload.get("formal_human_ready") is not True:
        _add(findings, "error", "BLIND_SCORE_NOT_FORMAL_HUMAN")
    if not isinstance(coverage, dict) or not coverage or any(
        not isinstance(value, int) or value < 2 for value in coverage.values()
    ):
        _add(findings, "error", "BLIND_SCORE_EFFECTIVE_HUMAN_COVERAGE_INSUFFICIENT")
    if int(payload.get("unresolved_human_dimensions", 1)) != 0:
        _add(findings, "error", "BLIND_SCORE_HUMAN_MAJORITY_UNRESOLVED")
    if payload.get("pairwise_exact_agreement") is None:
        _add(findings, "error", "BLIND_SCORE_AGREEMENT_MISSING")
    variants = set(str(value) for value in payload.get("variants", []))
    expected = {candidate_id, baseline_id}
    if not expected.issubset(variants):
        _add(
            findings, "error", "BLIND_SCORE_VARIANTS_MISMATCH",
            expected=sorted(expected), actual=sorted(variants),
        )
    evidence = payload.get("evidence", {})
    for label in ("key", "ratings", "packet", "source_pairs", "merge_report"):
        record = evidence.get(label, {}) if isinstance(evidence, dict) else {}
        evidence_path = _resolve(base, record.get("path", ""))
        if not evidence_path.is_file() or sha256_file(evidence_path) != record.get("sha256"):
            _add(findings, "error", "BLIND_SCORE_EVIDENCE_DRIFT", artifact=label, path=str(evidence_path))
    merge_record = evidence.get("merge_report", {}) if isinstance(evidence, dict) else {}
    merge_path = _resolve(base, merge_record.get("path", ""))
    if merge_path.is_file():
        merge_audit = audit_merge_report(merge_path)
        if merge_audit.get("status") != "pass":
            _add(
                findings, "error", "BLIND_SCORE_MERGE_REPORT_INVALID",
                merge_findings=merge_audit.get("findings", []),
            )
        else:
            merge_payload = json.loads(merge_path.read_text(encoding="utf-8-sig"))
            if (
                _resolve(base, merge_payload.get("output", {}).get("path", ""))
                != _resolve(base, evidence.get("ratings", {}).get("path", ""))
                or _resolve(base, merge_payload.get("packet", {}).get("path", ""))
                != _resolve(base, evidence.get("packet", {}).get("path", ""))
            ):
                _add(findings, "error", "BLIND_SCORE_MERGE_BINDING_MISMATCH")
    return payload


def evaluate(manifest_path: Path, registry_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    base = manifest_path.parent
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    registry = read_registry(registry_path)
    findings: list[dict] = []
    if payload.get("schema") != SCHEMA:
        _add(findings, "error", "EVALUATION_SCHEMA_MISMATCH", actual=payload.get("schema"))
    for location in _walk_forbidden_keys(payload):
        _add(findings, "error", "DETECTOR_OR_AUTHORSHIP_METRIC_FORBIDDEN", location=location)
    raw_claims = payload.get("claims", [])
    if not isinstance(raw_claims, list):
        _add(findings, "error", "EVALUATION_CLAIMS_INVALID")
        raw_claims = []
    claims = set(str(value) for value in raw_claims)
    for claim in sorted(claims - ALLOWED_CLAIMS):
        _add(findings, "error", "EVALUATION_CLAIM_FORBIDDEN", claim=claim)

    source_record = payload.get("source", {})
    if not isinstance(source_record, dict):
        source_record = {}
    source_path = _verify_file_record(base, source_record, findings, "source")
    candidate = payload.get("candidate", {})
    if not isinstance(candidate, dict):
        candidate = {}
    candidate_path = _verify_file_record(base, candidate, findings, "candidate")
    source_sha256 = str(source_record.get("sha256", ""))
    candidate_sha256 = str(candidate.get("sha256", ""))
    candidate_provider = str(candidate.get("provider", ""))
    candidate_id = str(candidate.get("id", "")).strip()
    baseline_id = str(payload.get("baseline_id", "source")).strip()
    if not candidate_id or not baseline_id or candidate_id == baseline_id:
        _add(findings, "error", "EVALUATION_VARIANT_IDS_INVALID")

    scene = payload.get("scene", {})
    if not isinstance(scene, dict):
        scene = {}
        _add(findings, "error", "EVALUATION_SCENE_INVALID")
    document_type = str(scene.get("document_type", ""))
    intent = str(scene.get("intent", "rewrite"))
    document_format = str(scene.get("document_format", "plain"))
    scope = str(scene.get("scope", "document"))
    try:
        route = select_route(
            document_type, intent, document_format, scope,
            requested_editor=candidate_provider or None,
        )
    except (KeyError, ValueError) as exc:
        route = {"status": "blocked", "stages": [], "candidate_policy": {"providers": []}}
        _add(findings, "error", "EVALUATION_SCENE_UNSUPPORTED", error=str(exc))
    if route.get("status") != "pass":
        _add(findings, "error", "EVALUATION_ROUTE_BLOCKED", route_findings=route.get("findings", []))
    allowed_candidates = set(route.get("candidate_policy", {}).get("providers", []))
    if candidate_provider not in allowed_candidates:
        _add(
            findings, "error", "EVALUATION_CANDIDATE_PROVIDER_NOT_ALLOWED",
            provider=candidate_provider, allowed=sorted(allowed_candidates),
        )
    route_providers = [str(item.get("provider")) for item in route.get("stages", [])]
    required_stage_providers = set(route_providers) - {candidate_provider}
    covered = _verify_stage_evidence(
        base, payload.get("stage_evidence"), required_stage_providers,
        source_sha256, candidate_sha256, findings,
    )
    candidate_report = _verify_candidate_report(
        base, payload.get("candidate_verification"), registry, candidate_provider,
        source_sha256, candidate_sha256, findings,
    )

    decision = payload.get("human_decision", {})
    decision_status = str(decision.get("status", "pending")) if isinstance(decision, dict) else "pending"
    if decision_status not in {"pending", "accepted", "source-retained"}:
        _add(findings, "error", "HUMAN_DECISION_STATUS_INVALID", status=decision_status)
    blind_score: dict | None = None
    if decision_status == "accepted":
        if not str(decision.get("reviewer", "")).strip() or len(str(decision.get("reason", "")).strip()) < 10:
            _add(findings, "error", "HUMAN_DECISION_EVIDENCE_WEAK")
        blind_score = _verify_blind_score(
            base, payload.get("blind_score"), candidate_id, baseline_id, findings,
        )
    elif payload.get("blind_score") is not None:
        blind_score = _verify_blind_score(
            base, payload.get("blind_score"), candidate_id, baseline_id, findings,
        )
    if "human_preference_observed" in claims:
        if decision_status != "accepted" or blind_score is None:
            _add(findings, "error", "HUMAN_PREFERENCE_CLAIM_UNSUPPORTED")
        else:
            counts = blind_score.get("counts", {}).get("naturalness", {})
            if counts.get(candidate_id, 0) <= counts.get(baseline_id, 0):
                _add(findings, "error", "HUMAN_PREFERENCE_CLAIM_NOT_OBSERVED")

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    if errors:
        status = "FAIL"
    elif decision_status == "accepted":
        status = "HUMAN_EVALUATED_PASS"
    elif decision_status == "source-retained":
        status = "SOURCE_RETAINED"
    else:
        status = "MECHANICAL_PASS_HUMAN_PENDING"
    return {
        "schema": "aigc-stack-evaluation-report/v1",
        "status": status,
        "manifest": {"path": str(manifest_path), "sha256": sha256_file(manifest_path)},
        "scene": {
            "document_type": document_type,
            "intent": intent,
            "document_format": document_format,
            "scope": scope,
        },
        "candidate": {
            "id": candidate_id,
            "provider": candidate_provider,
            "source_present": source_path is not None,
            "candidate_present": candidate_path is not None,
            "verification_present": candidate_report is not None,
        },
        "required_stage_providers": sorted(required_stage_providers),
        "covered_stage_providers": sorted(covered),
        "decision_status": decision_status,
        "claims": sorted(claims),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "interpretation": (
            "Mechanical PASS proves frozen-source, role-evidence and protected-candidate contracts only. "
            "HUMAN_EVALUATED_PASS additionally records a locked blind comparison and an explicit human decision; "
            "neither status proves human authorship, detector performance, or academic correctness."
        ),
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--registry", type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = evaluate(args.manifest, args.registry.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC STACK EVALUATION {report['status']} "
            f"errors={report['errors']} warnings={report['warnings']}"
        )
        print(
            f"scene={report['scene']['document_type']} "
            f"provider={report['candidate']['provider']} decision={report['decision_status']}"
        )
        print("required_stages=" + ",".join(report["required_stage_providers"]))
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
