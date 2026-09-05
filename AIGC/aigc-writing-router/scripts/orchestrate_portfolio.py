#!/usr/bin/env python3
"""Run a source-bound AIGC portfolio without serial rewrite laundering.

The portfolio is a receipt-driven state machine. A route, candidate task,
native audit, candidate verification, workbench plan and human selection are
different events; the command never infers one event from another.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_role_evidence import audit as audit_role_evidence


SCHEMA = "aigc-portfolio-orchestration/v1"
RECEIPT_SCHEMA = "aigc-role-receipt/v1"
ACADEMIC_TYPES = {"mcm", "modeling", "research", "course-notes", "academic-mixed"}
CONTENT_ROLES = {
    "mcm": ["deai-academic-writing", "mcm-cup-standard-write", "deai-modeling-writing"],
    "modeling": ["deai-academic-writing", "deai-modeling-writing"],
    "research": ["deai-academic-writing", "deai-research-writing"],
    "course-notes": ["deai-academic-writing", "deai-course-notes"],
    "academic-mixed": ["deai-academic-writing", "deai-modeling-writing", "deai-research-writing", "deai-course-notes"],
}
BRANCH_IDS = {"humanize-academic-chinese": "H1", "baibai-aigc": "B1"}
DEFAULT_BRANCH = "humanize-academic-chinese"
REVIEWER_EVIDENCE = {
    "patina": ["audit-report", "native-run-report"],
    "ai-check": ["audit-report"],
    "humanizer-brandonwise": ["audit-report", "native-run-report"],
}
WORKBENCH_EVIDENCE = {
    "AI_paper": ["workbench-plan", "audit-report", "document-map", "diff-report", "export-artifact", "candidate-verification"],
    "FYADR": ["source-hash", "workbench-plan", "audit-report", "document-map", "diff-report", "export-artifact", "candidate-verification"],
    "GankAIGC": ["workbench-plan", "audit-report", "deployment-record", "document-map", "export-artifact", "candidate-verification"],
    "humanize-main-Tiany": ["workbench-plan", "audit-report", "comparison-report"],
    "AI-Cleaner": ["workbench-plan", "audit-report", "candidate-verification", "diff-report"],
    "BypassAIGC": ["workbench-plan", "audit-report", "candidate-task", "candidate-verification", "comparison-report"],
    "humanize-text": ["workbench-plan", "candidate-task", "step-trace", "candidate-file", "candidate-verification", "comparison-report"],
    "humanize-ai": ["workbench-plan", "audit-report", "candidate-task", "step-trace", "candidate-verification"],
}
HUMANIZE_LOCAL_GATES = ["candidate-verification", "academic-style-release"]
ROLE_EVIDENCE_CONTRACT_VERSION = 2
ROLE_EVIDENCE_VALIDATOR = Path(__file__).resolve().with_name("validate_role_evidence.py")
ROLE_EXECUTION_MODES = {
    "content-owner": {"manual_skill", "native_executed", "hybrid_verified"},
    "candidate": {"protected_candidate", "native_executed"},
    "reviewer": {"native_executed", "manual_review"},
    "workbench": {"manual_workbench", "native_executed", "hybrid_workbench"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def load_registry(skill_root: Path) -> dict[str, Any]:
    return read_json(skill_root / "references" / "stack-registry.json")


def load_role_contracts(skill_root: Path) -> dict[str, Any]:
    return read_json(skill_root / "references" / "role-contracts.json")


def load_content_contracts(skill_root: Path) -> dict[str, Any]:
    return read_json(skill_root / "references" / "content-role-contracts.json")


def registry_entry(registry: dict[str, Any], provider: str) -> dict[str, Any] | None:
    for entry in registry.get("packages", []):
        names = {
            entry.get("directory"), entry.get("skill_name"),
            *entry.get("aliases", []), *entry.get("providers", []),
            *[item.get("skill_name") for item in entry.get("skill_entrypoints", []) if isinstance(item, dict)],
        }
        if provider in names:
            return entry
    return None


def provider_contract(skill_root: Path, provider: str) -> dict[str, Any] | None:
    for contract in load_role_contracts(skill_root).get("packages", []):
        if provider in contract.get("providers", []):
            return contract
    for contract in load_content_contracts(skill_root).get("roles", []):
        if provider == contract.get("provider"):
            return contract
    return None


def scenario_contract(skill_root: Path, document_type: str, document_format: str) -> dict[str, Any]:
    scenarios = load_role_contracts(skill_root).get("scenarios", [])
    exact = [item for item in scenarios if item.get("document_type") == document_type and item.get("document_format") == document_format]
    if exact:
        return exact[0]
    matches = [item for item in scenarios if item.get("document_type") == document_type]
    return matches[0] if matches else {"hard_gates": [], "human_gates": []}


def run_adapter(
    skill_root: Path, provider: str, action: str, source: Path | None, output: Path,
    candidate: Path | None = None, execute_native: bool = False,
) -> dict[str, Any]:
    command = [sys.executable, str(skill_root / "scripts" / "run_aigc_adapter.py"), "--package", provider, "--action", action, "--output-dir", str(output), "--format", "json"]
    if source is not None:
        command.extend(["--source", str(source)])
    if candidate is not None:
        command.extend(["--candidate", str(candidate)])
    if execute_native:
        command.append("--execute-native")
    completed = subprocess.run(command, cwd=skill_root / "scripts", text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=180, check=False)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        report = {"schema": "aigc-adapter-run/v1", "package": provider, "action": action, "status": "blocked", "findings": [{"severity": "error", "code": "ADAPTER_INVALID_OUTPUT", "returncode": completed.returncode, "stderr": completed.stderr[-2000:]}]}
    report["orchestrator_returncode"] = completed.returncode
    return report


def _format_supported(entry: dict[str, Any] | None, document_format: str) -> bool:
    if not entry:
        return False
    formats = entry.get("adapter", {}).get("document_formats", [])
    return document_format in formats or document_format == "plain" and "txt" in formats


def _stage(provider: str, role: str, status: str, **extra: Any) -> dict[str, Any]:
    result = {"provider": provider, "role": role, "status": status}
    result.update(extra)
    return result


def _required_evidence(skill_root: Path, provider: str, role: str) -> list[str]:
    if role == "content-owner":
        contract = provider_contract(skill_root, provider) or {}
        return [str(item) for item in contract.get("required_evidence", [])]
    if role == "candidate":
        contract = provider_contract(skill_root, provider) or {}
        return [str(item) for item in contract.get("completion_evidence", []) if item != "human-decision"]
    if role == "reviewer":
        return REVIEWER_EVIDENCE.get(provider, ["audit-report"])
    if role == "workbench":
        return WORKBENCH_EVIDENCE.get(provider, ["workbench-plan", "audit-report"])
    raise ValueError(f"unknown role: {role}")


def _evidence_entry(path: Path) -> dict[str, str]:
    path = path.resolve()
    return {"path": str(path), "sha256": sha256_file(path)}


def _branch_source(provider: str, authority: Path, authority_format: str, proxy: Path | None, proxy_format: str | None) -> tuple[Path | None, str, str]:
    supported = {"humanize-academic-chinese": {"tex", "txt", "markdown"}, "baibai-aigc": {"txt", "docx", "markdown"}}
    if authority_format in supported.get(provider, set()):
        return authority, authority_format, "document"
    if provider == "baibai-aigc" and proxy is not None:
        fmt = proxy_format or ("markdown" if proxy.suffix.casefold() in {".md", ".markdown"} else "txt")
        if fmt in supported[provider]:
            return proxy, fmt, "local-proxy"
    return None, authority_format, "blocked"


def init_plan(
    source: Path, document_type: str, document_format: str, output_dir: Path,
    reviewers: list[str], proxy: Path | None = None, proxy_format: str | None = None,
    candidate_providers: list[str] | None = None, workbenches: list[str] | None = None,
) -> dict[str, Any]:
    source, output_dir = source.resolve(), output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if document_type not in ACADEMIC_TYPES:
        raise ValueError("portfolio orchestration currently targets Chinese academic scenes")
    candidate_providers = candidate_providers or [DEFAULT_BRANCH]
    workbenches = workbenches or []
    unknown = set(candidate_providers) - set(BRANCH_IDS)
    if unknown:
        raise ValueError(f"unsupported candidate providers: {sorted(unknown)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = output_dir / f"source.snapshot{source.suffix}"
    shutil.copy2(source, snapshot)
    source_sha = sha256_file(snapshot)
    proxy_snapshot: Path | None = None
    if proxy is not None:
        proxy = proxy.resolve()
        if not proxy.is_file():
            raise FileNotFoundError(proxy)
        inferred = proxy_format or ({".md": "markdown", ".markdown": "markdown"}.get(proxy.suffix.casefold(), "txt"))
        if inferred not in {"txt", "markdown"}:
            raise ValueError("proxy format must be txt or markdown")
        proxy_snapshot = output_dir / f"proxy.snapshot{proxy.suffix or '.txt'}"
        shutil.copy2(proxy, proxy_snapshot)
    skill_root = Path(__file__).resolve().parents[1]
    registry = load_registry(skill_root)
    scenario = scenario_contract(skill_root, document_type, document_format)
    stages = [
        _stage(provider, "content-owner", "requires_evidence", mandatory=True, required_evidence=_required_evidence(skill_root, provider, "content-owner"), note="Read the complete scene Skill and attach a source-bound role receipt; routing alone is not execution.")
        for provider in CONTENT_ROLES[document_type]
    ]
    branches: list[dict[str, Any]] = []
    for provider in candidate_providers:
        branch_id = BRANCH_IDS[provider]
        entry = registry_entry(registry, provider)
        branch_source, branch_format, scope = _branch_source(provider, snapshot, document_format, proxy_snapshot, proxy_format)
        branch: dict[str, Any] = {
            "id": branch_id, "provider": provider, "role": "candidate", "authority_source_sha256": source_sha,
            "parent_candidate": None, "pass_count": 1, "mandatory": provider == DEFAULT_BRANCH, "scope": scope,
            "selection_eligible": scope == "document", "required_evidence": _required_evidence(skill_root, provider, "candidate"),
            # Candidate-local checks run before selection.  Scenario release gates
            # run against the selected immutable tree and therefore cannot be
            # claimed by a pre-selection candidate receipt.
            "required_hard_gates": (
                list(HUMANIZE_LOCAL_GATES)
                if provider == "humanize-academic-chinese" and scope == "document" and document_format == "tex"
                else ["candidate-verification"]
                if scope == "document"
                else []
            ),
            "release_hard_gates": [str(item) for item in scenario.get("hard_gates", [])] if scope == "document" else [],
        }
        if branch_source is None or entry is None:
            branch.update(status="blocked", code="FORMAT_NOT_SUPPORTED" if entry else "PROVIDER_NOT_REGISTERED", input_sha256=None, input_path=None, input_format=branch_format)
        else:
            branch.update(input_sha256=sha256_file(branch_source), input_path=str(branch_source), input_format=branch_format, status="planned", evidence={}, gate_results={})
            prep_dir = output_dir / "branches" / branch_id / "prepare"
            prep = run_adapter(skill_root, provider, "prepare-candidate", branch_source, prep_dir)
            branch.update(status="ready" if prep.get("status") == "ready" else "blocked", code=None if prep.get("status") == "ready" else "PREPARE_FAILED", preparation_report=str((prep_dir / "prepare-report.json").resolve()))
        branches.append(branch)
    reviewer_records: list[dict[str, Any]] = []
    for reviewer in reviewers:
        entry = registry_entry(registry, reviewer)
        record = _stage(reviewer, "reviewer", "planned", mandatory=True, required_evidence=_required_evidence(skill_root, reviewer, "reviewer"))
        if not entry:
            record.update(status="blocked", code="REVIEWER_NOT_REGISTERED")
        elif document_format == "tex" and proxy_snapshot is None:
            record.update(status="requires_prose_proxy", code="RAW_TEX_FORBIDDEN", note="Reviewers receive extracted prose only; TeX remains authoritative.")
        else:
            review_input = proxy_snapshot or snapshot
            record.update(status="ready_read_only", input_path=str(review_input), input_sha256=sha256_file(review_input), note="Run the reviewer's complete read-only audit and attach its native/report evidence.")
        reviewer_records.append(record)
    workbench_records: list[dict[str, Any]] = []
    for workbench in workbenches:
        entry = registry_entry(registry, workbench)
        record = _stage(workbench, "workbench", "planned", mandatory=True, required_evidence=_required_evidence(skill_root, workbench, "workbench"))
        if not entry:
            record.update(status="blocked", code="WORKBENCH_NOT_REGISTERED")
        elif not _format_supported(entry, document_format):
            record.update(status="blocked", code="FORMAT_NOT_SUPPORTED", supported_formats=entry.get("adapter", {}).get("document_formats", []))
        else:
            plan_dir = output_dir / "workbenches" / workbench / "plan"
            plan_report = run_adapter(skill_root, workbench, "workbench-plan", snapshot, plan_dir)
            evidence = {"workbench-plan": _evidence_entry(plan_dir / "workbench-plan.json")} if (plan_dir / "workbench-plan.json").is_file() else {}
            record.update(status="prepared" if plan_report.get("status") == "pass" else "blocked", code=None if plan_report.get("status") == "pass" else "WORKBENCH_PREFLIGHT_FAILED", plan_report=str((plan_dir / "workbench-plan.json").resolve()), evidence=evidence)
        workbench_records.append(record)
    payload: dict[str, Any] = {
        "schema": SCHEMA, "version": 2,
        "source": {"path": str(source), "snapshot": str(snapshot), "sha256": source_sha, "bytes": snapshot.stat().st_size},
        "proxy": ({"snapshot": str(proxy_snapshot), "sha256": sha256_file(proxy_snapshot), "format": proxy_format or "txt", "scope": "style-only"} if proxy_snapshot else None),
        "scene": {"document_type": document_type, "document_format": document_format, "intent": "compare", "candidate_policy": "independent_same_source_branches", "hard_gates": [str(item) for item in scenario.get("hard_gates", [])], "human_gates": [str(item) for item in scenario.get("human_gates", [])]},
        "stages": stages, "branches": branches, "reviewers": reviewer_records, "workbenches": workbench_records,
        "selection": {"status": "pending", "accepted": None, "reason": None, "reviewer": None},
        "claims": {"native_generation_ran": False, "all_roles_complete": False, "all_roles_resolved": False, "human_quality_clearance": False, "candidate_files_registered": 0},
        "next_actions": ["Read each selected content Skill completely and attach a role receipt with every required evidence artifact.", "Register each independent candidate from its recorded input branch; never use another candidate as input.", "Run selected reviewers/workbenches and attach their source-bound receipts; waive only with an explicit fallback record."],
    }
    write_json(output_dir / "portfolio-plan.json", payload)
    return payload


def _load_plan(output_dir: Path) -> tuple[Path, dict[str, Any]]:
    plan_path = output_dir.resolve() / "portfolio-plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    return plan_path, read_json(plan_path)


def _find_role(payload: dict[str, Any], role: str, provider: str, candidate_id: str | None = None) -> dict[str, Any]:
    group = {"content-owner": "stages", "candidate": "branches", "reviewer": "reviewers", "workbench": "workbenches"}[role]
    for item in payload.get(group, []):
        if item.get("provider") == provider and (role != "candidate" or not candidate_id or item.get("id") == candidate_id):
            return item
    raise ValueError(f"planned {role} not found: {provider}")


def _validate_humanize_audit(record: dict[str, Any], evidence: dict[str, dict[str, str]]) -> list[str]:
    entry = evidence.get("audit-report")
    if not entry:
        return ["HUMANIZE_AUDIT_REPORT_MISSING"]
    try:
        report = read_json(Path(entry["path"]))
    except ValueError:
        return ["HUMANIZE_AUDIT_REPORT_INVALID"]
    errors: list[str] = []
    if report.get("schema") != "aigc-academic-candidate-audit/v1":
        errors.append("HUMANIZE_AUDIT_SCHEMA_MISMATCH")
    if report.get("status") != "pass":
        errors.append("HUMANIZE_AUDIT_NOT_PASS")
    if report.get("source", {}).get("sha256") != record.get("input_sha256"):
        errors.append("HUMANIZE_AUDIT_SOURCE_MISMATCH")
    if report.get("candidate", {}).get("sha256") != record.get("output_sha256"):
        errors.append("HUMANIZE_AUDIT_CANDIDATE_MISMATCH")
    required_roles = {
        "humanize-lexical-scanner", "humanize-lexical-signals",
        "protected-rewrite-contract", "section-voice-audit",
        "paragraph-rhythm-audit", "relative-style-comparison",
    }
    roles = {item.get("role") for item in report.get("dependencies", []) if isinstance(item, dict)}
    if not required_roles <= roles:
        errors.append("HUMANIZE_AUDIT_DEPENDENCIES_INCOMPLETE")
    return errors


def _validate_candidate_verification(record: dict[str, Any], evidence: dict[str, dict[str, str]]) -> list[str]:
    entry = evidence.get("candidate-verification")
    if not entry:
        return ["CANDIDATE_VERIFICATION_REPORT_MISSING"]
    try:
        report = read_json(Path(entry["path"]))
    except ValueError:
        return ["CANDIDATE_VERIFICATION_REPORT_INVALID"]
    errors: list[str] = []
    if report.get("status") != "pass":
        errors.append("CANDIDATE_VERIFICATION_NOT_PASS")
    if report.get("source", {}).get("sha256") != record.get("input_sha256"):
        errors.append("CANDIDATE_VERIFICATION_SOURCE_MISMATCH")
    if report.get("candidate", {}).get("sha256") != record.get("output_sha256"):
        errors.append("CANDIDATE_VERIFICATION_OUTPUT_MISMATCH")
    return errors


def _artifact_matches(run_dir: Path, item: dict[str, Any], expected_sha: str) -> bool:
    try:
        path = (run_dir / str(item.get("path", ""))).resolve()
        path.relative_to(run_dir.resolve())
    except (OSError, ValueError):
        return False
    declared = str(item.get("sha256", ""))
    return (
        declared == expected_sha
        and path.is_file()
        and sha256_file(path) == declared
    )


def _validate_inline_humanize_run(
    report_path: Path,
    report: dict[str, Any],
    record: dict[str, Any],
    evidence: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    run_dir = report_path.parent.resolve()
    if report.get("schema_version") not in {"humanize-inline-run/v2", "humanize-inline-run/v3"}:
        errors.append("HUMANIZE_INLINE_SCHEMA_MISMATCH")
    if report.get("mechanical_validation_status") != "PASS":
        errors.append("HUMANIZE_INLINE_MECHANICAL_NOT_PASS")
    artifacts = report.get("artifacts", {})
    if not _artifact_matches(run_dir, artifacts.get("before", {}), str(record.get("input_sha256", ""))):
        errors.append("HUMANIZE_INLINE_SOURCE_MISMATCH")
    if not _artifact_matches(run_dir, artifacts.get("after", {}), str(record.get("output_sha256", ""))):
        errors.append("HUMANIZE_INLINE_CANDIDATE_MISMATCH")
    change = evidence.get("change-report")
    validation = artifacts.get("validation", {})
    if (
        not change
        or Path(change["path"]).resolve() != (run_dir / str(validation.get("path", ""))).resolve()
        or change.get("sha256") != validation.get("sha256")
    ):
        errors.append("HUMANIZE_INLINE_CHANGE_REPORT_MISMATCH")
    verifier = Path(__file__).resolve().parents[1].parent / "humanize-academic-chinese" / "scripts" / "run_humanize_inline.py"
    completed = subprocess.run(
        [sys.executable, str(verifier), "emit", str(run_dir), "--format", "json"],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        timeout=300, check=False,
    )
    if completed.returncode not in {0, 2}:
        errors.append("HUMANIZE_INLINE_REVERIFY_FAILED")
    else:
        try:
            verified = json.loads(completed.stdout)
        except json.JSONDecodeError:
            errors.append("HUMANIZE_INLINE_REVERIFY_INVALID")
        else:
            if verified.get("mechanical_validation_status") != "PASS":
                errors.append("HUMANIZE_INLINE_REVERIFY_NOT_PASS")
    return errors


def _validate_long_humanize_run(
    report_path: Path,
    report: dict[str, Any],
    record: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if report.get("tool") != "finalize_humanize_long_document.py":
        errors.append("HUMANIZE_LONG_TOOL_MISMATCH")
    if report.get("candidate_assembly_status") != "PASS":
        errors.append("HUMANIZE_LONG_ASSEMBLY_NOT_PASS")
    if report.get("source_files_modified") != 0:
        errors.append("HUMANIZE_LONG_SOURCE_MODIFIED")
    manifest_path = report_path.parent / "rendered_manifest.csv"
    if not manifest_path.is_file():
        errors.append("HUMANIZE_LONG_RENDERED_MANIFEST_MISSING")
        return errors
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        errors.append("HUMANIZE_LONG_RENDERED_MANIFEST_INVALID")
        return errors
    matched = any(
        row.get("source_snapshot_sha256") == record.get("input_sha256")
        and row.get("rendered_sha256") == record.get("output_sha256")
        and row.get("format_check") == "PASS"
        for row in rows
    )
    if not matched:
        errors.append("HUMANIZE_LONG_SOURCE_CANDIDATE_BINDING_MISMATCH")
    return errors


def _validate_humanize_native_run(record: dict[str, Any], evidence: dict[str, dict[str, str]]) -> list[str]:
    entry = evidence.get("native-run-report")
    if not entry:
        return ["HUMANIZE_NATIVE_RUN_REPORT_MISSING"]
    report_path = Path(entry["path"]).resolve()
    try:
        report = read_json(report_path)
    except ValueError:
        return ["HUMANIZE_NATIVE_RUN_REPORT_INVALID"]
    if "schema_version" in report:
        return _validate_inline_humanize_run(report_path, report, record, evidence)
    return _validate_long_humanize_run(report_path, report, record)


def _receipt_errors(receipt: dict[str, Any], record: dict[str, Any], payload: dict[str, Any], role: str, artifact: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    errors: list[str] = []
    if receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("provider") != record.get("provider"):
        errors.append("RECEIPT_PROVIDER_MISMATCH")
    if receipt.get("role") != role:
        errors.append("RECEIPT_ROLE_MISMATCH")
    if (receipt.get("authority_source_sha256") or receipt.get("source_sha256")) != payload.get("source", {}).get("sha256"):
        errors.append("RECEIPT_SOURCE_MISMATCH")
    if receipt.get("status") != "pass":
        errors.append("RECEIPT_NOT_PASS")
    execution = receipt.get("execution")
    if not isinstance(execution, dict) or not execution.get("mode") or not execution.get("run_id"):
        errors.append("EXECUTION_RECORD_MISSING")
    else:
        mode = str(execution.get("mode"))
        if mode not in ROLE_EXECUTION_MODES.get(role, set()):
            errors.append("EXECUTION_MODE_NOT_EVIDENCE")
        if role == "content-owner":
            references_read = execution.get("references_read")
            if (
                not isinstance(references_read, list)
                or not references_read
                or any(not isinstance(item, str) or not item.strip() for item in references_read)
            ):
                errors.append("CONTENT_REFERENCES_READ_MISSING")
        if role == "candidate" and execution.get("pass_count") != 1:
            errors.append("CANDIDATE_PASS_COUNT_NOT_ONE")
    unresolved = receipt.get("unresolved")
    if not isinstance(unresolved, list):
        errors.append("RECEIPT_UNRESOLVED_LIST_MISSING")
    elif unresolved:
        errors.append("RECEIPT_HAS_UNRESOLVED_ITEMS")
    candidate_id = receipt.get("candidate_id")
    if role == "candidate":
        if candidate_id != record.get("id"):
            errors.append("RECEIPT_CANDIDATE_ID_MISMATCH")
        if receipt.get("candidate_sha256") != record.get("output_sha256"):
            errors.append("RECEIPT_CANDIDATE_HASH_MISMATCH")
    elif role == "reviewer":
        branch = next((item for item in payload.get("branches", []) if item.get("id") == candidate_id), None)
        if branch is None or branch.get("status") not in {"registered", "eligible", "complete", "complete_local"}:
            errors.append("REVIEW_TARGET_NOT_REGISTERED")
        elif receipt.get("candidate_sha256") != branch.get("output_sha256"):
            errors.append("REVIEW_TARGET_HASH_MISMATCH")
    elif role == "workbench" and "candidate-verification" in record.get("required_evidence", []):
        branch = next((item for item in payload.get("branches", []) if item.get("id") == candidate_id), None)
        if branch is None or branch.get("status") not in {"registered", "eligible", "complete", "complete_local"}:
            errors.append("WORKBENCH_TARGET_NOT_REGISTERED")
        elif receipt.get("candidate_sha256") != branch.get("output_sha256"):
            errors.append("WORKBENCH_TARGET_HASH_MISMATCH")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("RECEIPT_EVIDENCE_MAP_MISSING")
        return errors, {}
    normalized: dict[str, dict[str, str]] = {}
    for token, item in evidence.items():
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            errors.append(f"EVIDENCE_ENTRY_INVALID:{token}")
            continue
        path = Path(str(item["path"]))
        if not path.is_absolute():
            path = (artifact.parent / path).resolve()
        if not path.is_file():
            errors.append(f"EVIDENCE_FILE_MISSING:{token}")
            continue
        actual = sha256_file(path)
        if actual != item.get("sha256"):
            errors.append(f"EVIDENCE_HASH_MISMATCH:{token}")
            continue
        normalized[str(token)] = {"path": str(path), "sha256": actual}
    required = set(record.get("required_evidence", []))
    errors.extend(f"EVIDENCE_MISSING:{token}" for token in sorted(required - set(normalized)))
    errors.extend(f"EVIDENCE_UNDECLARED:{token}" for token in sorted(set(normalized) - required))

    if role == "candidate":
        evidence_source_sha = str(record.get("input_sha256", ""))
        evidence_candidate_id = str(record.get("id", ""))
        evidence_candidate_sha = str(record.get("output_sha256", ""))
    elif role in {"reviewer", "workbench"} and candidate_id:
        evidence_source_sha = str(payload.get("source", {}).get("sha256", ""))
        evidence_candidate_id = str(candidate_id or "")
        evidence_candidate_sha = str(receipt.get("candidate_sha256") or "")
    else:
        evidence_source_sha = str(payload.get("source", {}).get("sha256", ""))
        evidence_candidate_id = ""
        evidence_candidate_sha = ""

    for token in sorted(required & set(normalized)):
        validation = audit_role_evidence(
            Path(normalized[token]["path"]), token, str(record.get("provider", "")), role,
            evidence_source_sha,
            evidence_candidate_id or None,
            evidence_candidate_sha or None,
        )
        errors.extend(
            f"EVIDENCE_CONTRACT:{token}:{error}"
            for error in validation.get("errors", [])
        )
        if token == "candidate-file" and normalized[token]["sha256"] != evidence_candidate_sha:
            errors.append("EVIDENCE_CONTRACT:candidate-file:CANDIDATE_FILE_HASH_MISMATCH")
        if token == "export-artifact" and evidence_candidate_sha and normalized[token]["sha256"] != evidence_candidate_sha:
            errors.append("EVIDENCE_CONTRACT:export-artifact:EXPORT_ARTIFACT_HASH_MISMATCH")
    if record.get("provider") == "mcm-cup-standard-write" and {
        "modeling-workbench", "reasoning-preflight"
    } <= set(normalized):
        try:
            workbench_report = read_json(Path(normalized["modeling-workbench"]["path"]))
            preflight_report = read_json(Path(normalized["reasoning-preflight"]["path"]))
        except ValueError:
            errors.append("EVIDENCE_CROSS_BINDING:MCM_REPORT_INVALID")
        else:
            workbench_sha = workbench_report.get("inputs", {}).get("workbench", {}).get("sha256")
            preflight_sha = preflight_report.get("inputs", {}).get("workbench", {}).get("sha256")
            if not workbench_sha or workbench_sha != preflight_sha:
                errors.append("EVIDENCE_CROSS_BINDING:MCM_WORKBENCH_PREFLIGHT_MISMATCH")
    if role == "candidate":
        for gate in record.get("required_hard_gates", []):
            if record.get("gate_results", {}).get(gate) != "pass":
                errors.append(f"HARD_GATE_NOT_PASS:{gate}")
        errors.extend(_validate_candidate_verification(record, normalized))
        if record.get("provider") == "humanize-academic-chinese":
            errors.extend(_validate_humanize_audit(record, normalized))
            errors.extend(_validate_humanize_native_run(record, normalized))
    return errors, normalized


def attach_role(output_dir: Path, role: str, provider: str, artifact: Path, candidate_id: str | None = None) -> dict[str, Any]:
    plan_path, payload = _load_plan(output_dir)
    artifact = artifact.resolve()
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    record = _find_role(payload, role, provider, candidate_id)
    receipt = read_json(artifact)
    errors, normalized = _receipt_errors(receipt, record, payload, role, artifact)
    if errors:
        record.update(status="blocked", code="ROLE_RECEIPT_INVALID", receipt_path=str(artifact), receipt_errors=errors)
        write_json(plan_path, payload)
        return {"provider": provider, "role": role, "status": "blocked", "errors": errors, "plan": str(plan_path)}
    record.update(
        status="eligible" if role == "candidate" and record.get("selection_eligible") else "complete",
        receipt_path=str(artifact), receipt_sha256=sha256_file(artifact),
        evidence=normalized, evidence_status="pass", completed_evidence=sorted(normalized),
        unresolved=receipt.get("unresolved", []),
        receipt_contract={
            "version": ROLE_EVIDENCE_CONTRACT_VERSION,
            "validator": str(ROLE_EVIDENCE_VALIDATOR),
            "validator_sha256": sha256_file(ROLE_EVIDENCE_VALIDATOR),
        },
    )
    if role == "candidate":
        record["domain_audit_status"], record["document_status"] = "pass", "pass" if record.get("selection_eligible") else "local-only"
        if "native-run-report" in normalized:
            payload.setdefault("claims", {})["native_generation_ran"] = True
    write_json(plan_path, payload)
    return {"provider": provider, "role": role, "status": record["status"], "plan": str(plan_path), "receipt_sha256": record["receipt_sha256"]}


def attach_stage(output_dir: Path, provider: str, artifact: Path) -> dict[str, Any]:
    return attach_role(output_dir, "content-owner", provider, artifact)


def role_template(output_dir: Path, role: str, provider: str, output: Path, candidate_id: str | None = None) -> dict[str, Any]:
    """Emit a non-passing receipt template; placeholders can never complete a role."""
    _, payload = _load_plan(output_dir)
    record = _find_role(payload, role, provider, candidate_id)
    evidence = {
        token: {"path": f"FILL:{token}", "sha256": "FILL_WITH_SHA256"}
        for token in record.get("required_evidence", [])
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "provider": provider,
        "role": role,
        "status": "pending",
        "authority_source_sha256": payload.get("source", {}).get("sha256"),
        "evidence": evidence,
        "unresolved": ["Replace every FILL placeholder and set status=pass only after the role actually ran."],
        "execution": {"mode": "template", "run_id": "FILL_WITH_RUN_ID", "references_read": [], "pass_count": 1},
    }
    if role in {"candidate", "reviewer"}:
        receipt["candidate_id"] = candidate_id or (record.get("id") if role == "candidate" else "H1")
        receipt["candidate_sha256"] = record.get("output_sha256") if role == "candidate" else "FILL_WITH_CANDIDATE_SHA256"
    if role == "candidate":
        receipt["observed_gate_results"] = dict(record.get("gate_results", {}))
    output = output.resolve()
    write_json(output, receipt)
    return {"status": "template_only", "provider": provider, "role": role, "output": str(output), "required_evidence": record.get("required_evidence", [])}


def register_candidate(
    output_dir: Path,
    provider: str,
    candidate: Path,
    style_decisions: Path | None = None,
) -> dict[str, Any]:
    plan_path, payload = _load_plan(output_dir)
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    branch = _find_role(payload, "candidate", provider)
    if branch.get("status") == "blocked":
        raise ValueError(f"candidate branch is blocked: {branch.get('code', 'UNKNOWN')}")
    source = Path(str(branch["input_path"]))
    verify_dir = output_dir.resolve() / "branches" / str(branch["id"]) / "verify"
    skill_root = Path(__file__).resolve().parents[1]
    report = run_adapter(skill_root, provider, "verify-candidate", source, verify_dir, candidate=candidate)
    gate_results = {"candidate-verification": "pass" if report.get("status") == "pass" else "fail"}
    style_report: dict[str, Any] | None = None
    if (
        report.get("status") == "pass"
        and provider == "humanize-academic-chinese"
        and source.suffix.casefold() == ".tex"
        and candidate.suffix.casefold() == ".tex"
    ):
        from audit_academic_candidate import audit as audit_academic_candidate

        scene = {
            "mcm": "MODELING", "modeling": "MODELING", "research": "RESEARCH",
            "course-notes": "COURSE", "academic-mixed": "AUTO",
        }.get(str(payload.get("scene", {}).get("document_type")), "AUTO")
        style_report = audit_academic_candidate(source, candidate, scene, style_decisions)
        style_path = verify_dir / "academic-style-audit.json"
        write_json(style_path, style_report)
        gate_results["academic-style-release"] = "pass" if style_report.get("status") == "pass" else "fail"
    if report.get("status") != "pass" or any(
        gate_results.get(gate) != "pass" for gate in branch.get("required_hard_gates", [])
    ):
        style_path = verify_dir / "academic-style-audit.json"
        branch.update(
            status="blocked",
            code=(
                "CANDIDATE_VERIFICATION_FAILED"
                if report.get("status") != "pass"
                else "ACADEMIC_STYLE_GATE_FAILED"
            ),
            verification_report=str((verify_dir / "candidate-verification.json").resolve()),
            academic_style_report=str(style_path.resolve()) if style_path.is_file() else None,
            rejected_candidate_path=str(candidate),
            rejected_candidate_sha256=sha256_file(candidate),
            gate_results=gate_results,
        )
    else:
        prep_dir = output_dir.resolve() / "branches" / str(branch["id"]) / "prepare"
        evidence: dict[str, dict[str, str]] = {}
        for token, path in (("candidate-task", prep_dir / "candidate-task.json"), ("candidate-file", candidate), ("candidate-verification", verify_dir / "candidate-verification.json")):
            if path.is_file():
                evidence[token] = _evidence_entry(path)
        style_path = verify_dir / "academic-style-audit.json"
        if style_path.is_file():
            evidence["audit-report"] = _evidence_entry(style_path)
        branch.update(status="registered", output_path=str(candidate), output_sha256=sha256_file(candidate), verification_report=str((verify_dir / "candidate-verification.json").resolve()), invariant_status="pass", domain_audit_status="pending", document_status="pending", evidence=evidence, gate_results=gate_results)
    payload["claims"]["candidate_files_registered"] = sum(item.get("output_path") is not None for item in payload.get("branches", []))
    write_json(plan_path, payload)
    return {
        "provider": provider,
        "status": branch["status"],
        "verification": report.get("status"),
        "academic_style": style_report.get("status") if style_report else "not-applicable",
        "gate_results": gate_results,
        "plan": str(plan_path),
    }


def waive_role(output_dir: Path, role: str, provider: str, reviewer: str, reason: str, candidate_id: str | None = None) -> dict[str, Any]:
    if len(reason.strip()) < 12:
        raise ValueError("fallback reason must state the unavailable capability (at least 12 characters)")
    plan_path, payload = _load_plan(output_dir)
    if role == "content-owner":
        raise ValueError("content-owner stages cannot be waived")
    record = _find_role(payload, role, provider, candidate_id)
    record.update(status="waived", fallback={"reviewer": reviewer, "reason": reason.strip()})
    write_json(plan_path, payload)
    return {"provider": provider, "role": role, "status": "waived", "plan": str(plan_path)}


def _role_resolved(item: dict[str, Any]) -> bool:
    return item.get("status") in {"complete", "eligible", "complete_local", "waived"}


def _ready_for_selection(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    failures.extend(f"content:{item.get('provider')}:{item.get('status')}" for item in payload.get("stages", []) if item.get("status") != "complete")
    for item in payload.get("branches", []):
        if item.get("mandatory") and item.get("status") not in {"eligible", "waived"}:
            failures.append(f"candidate:{item.get('provider')}:{item.get('status')}")
        elif not item.get("mandatory") and not _role_resolved(item):
            failures.append(f"optional-candidate:{item.get('provider')}:{item.get('status')}")
    for group in (payload.get("reviewers", []), payload.get("workbenches", [])):
        failures.extend(f"{item.get('role')}:{item.get('provider')}:{item.get('status')}" for item in group if not _role_resolved(item))
    eligible = [item for item in payload.get("branches", []) if item.get("status") == "eligible" and item.get("selection_eligible")]
    if not eligible and not any(item.get("status") == "waived" and item.get("mandatory") for item in payload.get("branches", [])):
        failures.append("no_document_candidate_or_explicit_source-retain_fallback")
    return not failures, failures


def select_candidate(output_dir: Path, accepted: str, reviewer: str, reason: str) -> dict[str, Any]:
    if len(reason.strip()) < 12:
        raise ValueError("selection reason must identify a concrete textual or technical benefit")
    plan_path, payload = _load_plan(output_dir)
    if payload.get("selection", {}).get("status") != "pending":
        raise ValueError("selection is already recorded and cannot be overwritten")
    ready, failures = _ready_for_selection(payload)
    if not ready:
        return {"status": "blocked", "code": "ROLES_NOT_RESOLVED", "failures": failures, "plan": str(plan_path)}
    selected = None
    accepted_id = accepted.upper()
    if accepted_id not in {"SOURCE", "ORIGINAL"}:
        selected = next((item for item in payload.get("branches", []) if item.get("id") == accepted_id), None)
        if selected is None or selected.get("status") != "eligible" or not selected.get("selection_eligible"):
            return {"status": "blocked", "code": "CANDIDATE_NOT_ELIGIBLE", "plan": str(plan_path)}
    else:
        accepted_id = "SOURCE"
    decision_path = output_dir.resolve() / "human-decision.json"
    write_json(decision_path, {"schema": "aigc-human-decision/v1", "authority_source_sha256": payload.get("source", {}).get("sha256"), "accepted": accepted_id, "reviewer": reviewer, "reason": reason.strip(), "candidate_sha256": selected.get("output_sha256") if selected else None})
    payload["selection"] = {"status": "accepted" if accepted_id != "SOURCE" else "source_retained", "accepted": accepted_id, "reason": reason.strip(), "reviewer": reviewer, "decision_path": str(decision_path), "decision_sha256": sha256_file(decision_path)}
    if selected is not None:
        selected.setdefault("evidence", {})["human-decision"] = _evidence_entry(decision_path)
    groups = (payload.get("stages", []), payload.get("branches", []), payload.get("reviewers", []), payload.get("workbenches", []))
    all_complete = all(item.get("status") in {"complete", "eligible", "complete_local"} for group in groups for item in group)
    all_resolved = all(_role_resolved(item) for group in groups for item in group)
    payload["claims"].update(all_roles_complete=all_complete, all_roles_resolved=all_resolved, human_quality_clearance=False, collaboration_status="COMPLETE" if all_complete else "COMPLETE_WITH_FALLBACKS" if all_resolved else "INCOMPLETE")
    write_json(plan_path, payload)
    return {"status": payload["selection"]["status"], "accepted": accepted_id, "collaboration_status": payload["claims"]["collaboration_status"], "plan": str(plan_path)}


def _freshness(payload: dict[str, Any]) -> list[str]:
    stale: list[str] = []
    source = Path(str(payload.get("source", {}).get("snapshot", "")))
    if not source.is_file() or sha256_file(source) != payload.get("source", {}).get("sha256"):
        stale.append("authority-source")
    for group_name in ("stages", "branches", "reviewers", "workbenches"):
        for item in payload.get(group_name, []):
            receipt_path = item.get("receipt_path")
            if receipt_path:
                contract = item.get("receipt_contract")
                if (
                    not isinstance(contract, dict)
                    or contract.get("version") != ROLE_EVIDENCE_CONTRACT_VERSION
                    or contract.get("validator") != str(ROLE_EVIDENCE_VALIDATOR)
                    or contract.get("validator_sha256") != sha256_file(ROLE_EVIDENCE_VALIDATOR)
                ):
                    stale.append(f"{group_name}:{item.get('provider')}:receipt-contract")
            if receipt_path and item.get("receipt_sha256") and Path(str(receipt_path)).is_file() and sha256_file(Path(str(receipt_path))) != item.get("receipt_sha256"):
                stale.append(f"{group_name}:{item.get('provider')}:receipt")
            if item.get("output_path") and item.get("output_sha256"):
                path = Path(str(item["output_path"]))
                if not path.is_file() or sha256_file(path) != item["output_sha256"]:
                    stale.append(f"candidate:{item.get('id')}:file")
            for token, evidence in item.get("evidence", {}).items():
                if not isinstance(evidence, dict) or not evidence.get("path"):
                    stale.append(f"{group_name}:{item.get('provider')}:{token}")
                    continue
                evidence_path = Path(str(evidence["path"]))
                if not evidence_path.is_file() or sha256_file(evidence_path) != evidence.get("sha256"):
                    stale.append(f"{group_name}:{item.get('provider')}:{token}")
    return stale


def status(output_dir: Path) -> dict[str, Any]:
    plan_path, payload = _load_plan(output_dir)
    all_items = payload.get("stages", []) + payload.get("branches", []) + payload.get("reviewers", []) + payload.get("workbenches", [])
    counts: dict[str, int] = {}
    for item in all_items:
        key = str(item.get("status", "unknown")); counts[key] = counts.get(key, 0) + 1
    ready, failures = _ready_for_selection(payload)
    stale = _freshness(payload)
    if stale:
        ready = False; failures.extend(f"stale:{item}" for item in stale)
    result = {
        "schema": SCHEMA, "plan": str(plan_path), "source_sha256": payload.get("source", {}).get("sha256"),
        "status_counts": counts, "selection": payload.get("selection"), "claims": payload.get("claims"),
        "ready_for_selection": ready and payload.get("selection", {}).get("status") == "pending", "stale_artifacts": stale, "blocking_reasons": failures,
        "roles": [{"role": item.get("role"), "provider": item.get("provider"), "status": item.get("status"), "required_evidence": item.get("required_evidence", []), "completed_evidence": sorted(item.get("evidence", {}).keys())} for item in all_items],
        "next_actions": payload.get("next_actions", []),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--source", type=Path, required=True); init.add_argument("--document-type", choices=sorted(ACADEMIC_TYPES), required=True); init.add_argument("--document-format", choices=("tex", "markdown", "txt", "docx", "plain"), required=True); init.add_argument("--output-dir", type=Path, required=True)
    init.add_argument("--reviewer", action="append", default=[]); init.add_argument("--workbench", action="append", default=[]); init.add_argument("--candidate-provider", action="append", default=[]); init.add_argument("--proxy", type=Path); init.add_argument("--proxy-format", choices=("txt", "markdown"))
    show = sub.add_parser("status"); show.add_argument("output_dir", type=Path)
    register = sub.add_parser("register"); register.add_argument("output_dir", type=Path); register.add_argument("--provider", required=True); register.add_argument("--candidate", type=Path, required=True); register.add_argument("--style-decisions", type=Path)
    attach = sub.add_parser("attach-role"); attach.add_argument("output_dir", type=Path); attach.add_argument("--role", choices=("content-owner", "candidate", "reviewer", "workbench"), required=True); attach.add_argument("--provider", required=True); attach.add_argument("--artifact", type=Path, required=True); attach.add_argument("--candidate-id")
    attach_stage_parser = sub.add_parser("attach-stage"); attach_stage_parser.add_argument("output_dir", type=Path); attach_stage_parser.add_argument("--provider", required=True); attach_stage_parser.add_argument("--artifact", type=Path, required=True)
    template = sub.add_parser("template-role"); template.add_argument("output_dir", type=Path); template.add_argument("--role", choices=("content-owner", "candidate", "reviewer", "workbench"), required=True); template.add_argument("--provider", required=True); template.add_argument("--output", type=Path, required=True); template.add_argument("--candidate-id")
    waive = sub.add_parser("waive-role"); waive.add_argument("output_dir", type=Path); waive.add_argument("--role", choices=("candidate", "reviewer", "workbench"), required=True); waive.add_argument("--provider", required=True); waive.add_argument("--reviewer", required=True); waive.add_argument("--reason", required=True); waive.add_argument("--candidate-id")
    select = sub.add_parser("select"); select.add_argument("output_dir", type=Path); select.add_argument("--accepted", required=True); select.add_argument("--reviewer", required=True); select.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init_plan(args.source, args.document_type, args.document_format, args.output_dir, args.reviewer, args.proxy, args.proxy_format, args.candidate_provider or None, args.workbench); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        if args.command == "status":
            result = status(args.output_dir); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["ready_for_selection"] or result["selection"].get("status") != "pending" else 2
        if args.command == "register":
            result = register_candidate(args.output_dir, args.provider, args.candidate, args.style_decisions); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] == "registered" else 1
        if args.command in {"attach-role", "attach-stage"}:
            result = attach_stage(args.output_dir, args.provider, args.artifact) if args.command == "attach-stage" else attach_role(args.output_dir, args.role, args.provider, args.artifact, args.candidate_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] in {"complete", "eligible"} else 1
        if args.command == "template-role":
            result = role_template(args.output_dir, args.role, args.provider, args.output, args.candidate_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        if args.command == "waive-role":
            result = waive_role(args.output_dir, args.role, args.provider, args.reviewer, args.reason, args.candidate_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        result = select_candidate(args.output_dir, args.accepted, args.reviewer, args.reason); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] in {"accepted", "source_retained"} else 1
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
