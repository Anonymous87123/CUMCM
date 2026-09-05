#!/usr/bin/env python3
"""Run a deterministic adapter action for any registered AIGC package.

Public interface:
    python run_aigc_adapter.py --package NAME --action ACTION
        [--source PATH] [--candidate PATH] [--output-dir DIR]
        [--document-type TYPE] [--execute-native] [--format text|json]

The adapter never claims that a remote model or GUI ran when it did not. It
freezes sources, prepares protected task bundles, verifies returned candidates,
and exposes native preflight information for all registered packages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from adapter_core import (
    compare_inventory,
    find_package,
    package_preflight,
    protect_text,
    protected_inventory,
    read_registry,
    read_source_text,
    serialise_inventory,
    sha256_file,
    text_diagnostics,
    write_json,
)
from audit_folder_utilization import audit as audit_folder_utilization


ACTIONS = ("preflight", "audit", "prepare-candidate", "verify-candidate", "workbench-plan")
DOCUMENT_TYPES = (
    "mcm", "modeling", "research", "course-notes", "academic-mixed",
    "academic-en", "medical-en", "technical", "general-en", "general-zh",
    "external-app",
)


def _artifact_dir(output_dir: Path | None, package: str, action: str) -> Path:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir.resolve()
    return Path(tempfile.mkdtemp(prefix=f"aigc-{package}-{action}-"))


def _source_record(source: Path) -> dict:
    return {
        "path": str(source.resolve()),
        "sha256": sha256_file(source),
        "bytes": source.stat().st_size,
        "suffix": source.suffix.casefold(),
    }


def _run_native(root: Path, entry: dict, source: Path) -> dict:
    adapter = entry.get("adapter", {})
    raw = adapter.get("native_audit_command")
    if not isinstance(raw, list) or not raw:
        return {"status": "not-declared", "command": None}
    if not any("{source}" in str(value) for value in raw):
        return {
            "status": "blocked", "command": raw,
            "error": "native audit command does not consume {source}",
            "code": "NATIVE_SOURCE_PLACEHOLDER_MISSING",
        }
    contract = adapter.get("native_audit_contract")
    if not isinstance(contract, dict):
        return {
            "status": "blocked", "command": raw,
            "error": "native_audit_contract is required",
            "code": "NATIVE_OUTPUT_CONTRACT_MISSING",
        }
    required_keys = contract.get("required_keys")
    fingerprint_keys = contract.get("fingerprint_keys")
    if (
        contract.get("stdout_format") != "json"
        or not isinstance(required_keys, list) or not required_keys
        or not isinstance(fingerprint_keys, list) or not fingerprint_keys
        or any(not isinstance(value, str) or not value for value in required_keys + fingerprint_keys)
    ):
        return {
            "status": "blocked", "command": raw,
            "error": "native JSON contract requires non-empty required_keys and fingerprint_keys",
            "code": "NATIVE_OUTPUT_CONTRACT_INVALID",
        }
    timeout = contract.get("timeout_seconds", 120)
    if not isinstance(timeout, int) or not 1 <= timeout <= 120:
        return {
            "status": "blocked", "command": raw,
            "error": "native timeout_seconds must be an integer from 1 to 120",
            "code": "NATIVE_TIMEOUT_INVALID",
        }
    package_root = root / str(entry["directory"])
    command = [
        str(value).replace("{source}", str(source.resolve())).replace(
            "{package_root}", str(package_root.resolve())
        )
        for value in raw
    ]
    source_before = sha256_file(source)
    try:
        completed = subprocess.run(
            command,
            cwd=package_root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        source_after = sha256_file(source) if source.is_file() else None
        return {
            "status": "blocked", "command": command, "error": str(exc),
            "code": "NATIVE_EXECUTION_FAILED",
            "source_sha256_before": source_before,
            "source_sha256_after": source_after,
            "source_unchanged": source_after == source_before,
        }
    source_after = sha256_file(source) if source.is_file() else None
    result = {
        "status": "blocked",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "source_sha256_before": source_before,
        "source_sha256_after": source_after,
        "source_unchanged": source_after == source_before,
    }
    if source_after != source_before:
        result.update(code="NATIVE_SOURCE_MODIFIED", error="native audit modified the source")
        return result
    if completed.returncode != 0:
        result.update(code="NATIVE_NONZERO_EXIT", error=f"native audit returned {completed.returncode}")
        return result
    try:
        native_payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result.update(code="NATIVE_OUTPUT_INVALID_JSON", error="native stdout is not one JSON document")
        return result
    if not isinstance(native_payload, dict):
        result.update(code="NATIVE_OUTPUT_NOT_OBJECT", error="native JSON output must be an object")
        return result
    missing = sorted(set(required_keys) - set(native_payload))
    if missing:
        result.update(code="NATIVE_OUTPUT_KEYS_MISSING", error=f"missing native JSON keys: {missing}")
        return result
    fingerprint_payload = {key: native_payload.get(key) for key in fingerprint_keys}
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result.update(
        status="pass",
        output_contract={
            "status": "pass", "stdout_format": "json",
            "required_keys": required_keys,
            "fingerprint_keys": fingerprint_keys,
        },
        semantic_fingerprint_sha256=fingerprint,
    )
    return result


def _run_tex_semantic_contract(root: Path, source: Path, candidate: Path) -> dict:
    script = root.parent / "mcm-cup-standard-write" / "scripts" / "audit_rewrite_contract.py"
    if not script.is_file():
        return {"status": "unavailable", "findings": [{
            "severity": "warning",
            "code": "TEX_SEMANTIC_CONTRACT_UNAVAILABLE",
            "path": str(script),
        }]}
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        ["python", str(script), str(source), str(candidate), "--format", "json"],
        cwd=script.parent,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=child_env,
        capture_output=True,
        timeout=120,
        check=False,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"status": "unavailable", "findings": [{
            "severity": "warning",
            "code": "TEX_SEMANTIC_CONTRACT_INVALID_OUTPUT",
            "returncode": completed.returncode,
            "stderr": completed.stderr[-2000:],
        }]}


def _embedded_capability_plan(
    root: Path,
    registry_path: Path,
    entry: dict,
    document_type: str | None = None,
) -> dict:
    """Return the reviewed embedded-unit plan for a workbench package.

    The plan is deliberately generated from the folder audit rather than
    copied into each adapter.  This makes every nested ``skill.json`` or
    ``SKILL.md`` discoverable, hash-bound, and visible to the package's
    workbench action.  A failed audit blocks the workbench plan.
    """
    catalog_path = registry_path.parent / "folder-utilization.json"
    if not catalog_path.is_file():
        return {
            "status": "blocked",
            "catalog": str(catalog_path),
            "findings": [{"severity": "error", "code": "FOLDER_UTILIZATION_CATALOG_MISSING"}],
            "records": [],
        }
    audit_report = audit_folder_utilization(root, registry_path, catalog_path)
    owner = str(entry.get("directory", ""))
    records = [item for item in audit_report.get("records", []) if item.get("owner") == owner]
    selected = records
    if document_type is not None:
        allowed_dispositions = {
            "workbench-capability", "routed-reviewer", "canonical-entry",
        }
        selected = [
            item for item in records
            if document_type in set(item.get("scenes", []))
            and item.get("disposition") in allowed_dispositions
        ]
    return {
        "status": audit_report.get("status"),
        "catalog": str(catalog_path),
        "tree_sha256": audit_report.get("embedded_manifest_tree_sha256"),
        "package": owner,
        "count": len(records),
        "records": records,
        "document_type": document_type,
        "selected_count": len(selected),
        "selected_records": selected,
        "deferred_count": len(records) - len(selected),
        "findings": audit_report.get("findings", []),
        "activation_rule": "select only the declared scene/disposition; maintenance-only and research-only units cannot author CUMCM prose",
    }
def execute(
    registry_path: Path,
    package_name: str,
    action: str,
    source: Path | None = None,
    candidate: Path | None = None,
    output_dir: Path | None = None,
    execute_native: bool = False,
    document_type: str | None = None,
) -> dict:
    payload = read_registry(registry_path)
    entry = find_package(payload, package_name)
    root = registry_path.resolve().parents[2]
    adapter = entry.get("adapter", {})
    interfaces = set(adapter.get("interfaces", []))
    report: dict = {
        "schema": "aigc-adapter-run/v1",
        "package": entry.get("directory"),
        "action": action,
        "status": "pass",
        "native_executed": False,
        "claims": {
            "remote_generation_ran": False,
            "gui_workbench_ran": False,
            "authorship_or_detector_verdict": False,
        },
        "findings": [],
    }
    artifacts = _artifact_dir(output_dir, str(entry["directory"]), action)
    report["artifact_dir"] = str(artifacts)

    if action == "preflight":
        report["preflight"] = package_preflight(root, entry)
        if not report["preflight"]["entrypoints_present"]:
            report["status"] = "blocked"
            report["findings"].append({"severity": "error", "code": "ENTRYPOINT_MISSING"})
        write_json(artifacts / "preflight.json", report)
        return report

    required_interface = {
        "audit": "audit",
        "prepare-candidate": "candidate",
        "verify-candidate": "candidate",
        "workbench-plan": "workbench",
    }[action]
    if required_interface not in interfaces:
        report["status"] = "blocked"
        report["findings"].append({
            "severity": "error",
            "code": "INTERFACE_NOT_SUPPORTED",
            "required": required_interface,
            "available": sorted(interfaces),
        })
        write_json(artifacts / "adapter-report.json", report)
        return report

    if action != "workbench-plan" and source is None:
        raise ValueError(f"--source is required for {action}")
    if source is not None:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        report["source"] = _source_record(source)

    if action == "workbench-plan":
        report["preflight"] = package_preflight(root, entry)
        embedded = _embedded_capability_plan(
            root, registry_path.resolve(), entry, document_type=document_type
        )
        report["embedded_capabilities"] = embedded
        if embedded.get("status") != "pass":
            report["status"] = "blocked"
            report["findings"].append({
                "severity": "error",
                "code": "FOLDER_UTILIZATION_AUDIT_FAILED",
                "detail": f"{embedded.get('catalog')}: {embedded.get('status')}",
            })
        report["plan"] = {
            "native_command": adapter.get("native_command"),
            "document_formats": adapter.get("document_formats", []),
            "offline_use": adapter.get("offline_use"),
            "network_for_generation": bool(adapter.get("network_for_generation")),
            "safe_boundary": adapter.get("safe_boundary"),
            "authority_rule": "import a copy; never overwrite the frozen authority file",
            "adoption_rule": "export as a candidate, verify it, then require human accept/reject",
            "embedded_capability_plan_required": True,
            "embedded_capability_catalog": str(registry_path.parent / "folder-utilization.json"),
            "document_type": document_type,
            "selected_embedded_capability_ids": [
                item.get("id") for item in embedded.get("selected_records", [])
            ],
            "serial_rewrite_forbidden": True,
        }
        write_json(artifacts / "workbench-plan.json", report)
        return report

    assert source is not None
    source_text = read_source_text(source)
    if source_text is None:
        report["status"] = "blocked"
        report["findings"].append({
            "severity": "error",
            "code": "TEXT_EXTRACTION_REQUIRED",
            "detail": "Use the package workbench or provide a UTF-8 text/prose proxy.",
        })
        write_json(artifacts / "adapter-report.json", report)
        return report

    source_inventory = protected_inventory(source_text)
    report["protected_inventory"] = serialise_inventory(source_inventory)

    if action == "audit":
        report["diagnostics"] = text_diagnostics(source_text)
        report["interpretation"] = (
            "Deterministic signals locate review targets only; they do not identify the author, "
            "prove academic quality, or predict an external detector."
        )
        if execute_native:
            report["native"] = _run_native(root, entry, source)
            report["native_executed"] = report["native"]["status"] == "pass"
            if report["native"]["status"] == "blocked":
                report["status"] = "partial"
                report["findings"].append({
                    "severity": "warning", "code": "NATIVE_AUDIT_BLOCKED",
                    "detail": report["native"].get("error") or report["native"].get("stderr", ""),
                })
        write_json(artifacts / "audit-report.json", report)
        return report

    if action == "prepare-candidate":
        snapshot = artifacts / f"source.snapshot{source.suffix}"
        shutil.copy2(source, snapshot)
        prose_proxy, spans = protect_text(source_text)
        proxy_path = artifacts / "source.protected-proxy.txt"
        proxy_path.write_text(prose_proxy, encoding="utf-8")
        write_json(artifacts / "protected-spans.json", spans)
        contract = {
            "schema": "aigc-candidate-task/v1",
            "provider": entry.get("skill_name") or entry.get("directory"),
            "source_sha256": report["source"]["sha256"],
            "source_snapshot": str(snapshot),
            "protected_proxy": str(proxy_path),
            "protected_spans": str(artifacts / "protected-spans.json"),
            "native_command": adapter.get("native_command"),
            "rules": [
                "Run the package's complete native workflow, not a borrowed phrase list.",
                "Generate one candidate directly from this frozen source branch.",
                "Do not resolve or rewrite AIGC_LOCK tokens.",
                "Do not add facts, citations, results, author experiences, or causal claims.",
                "Restore protected spans byte-for-byte before candidate verification.",
                "Do not overwrite the source snapshot.",
            ],
            "required_next_action": "verify-candidate",
            "human_review_required": True,
        }
        write_json(artifacts / "candidate-task.json", contract)
        report["task"] = contract
        report["status"] = "ready"
        write_json(artifacts / "prepare-report.json", report)
        return report

    if candidate is None:
        raise ValueError("--candidate is required for verify-candidate")
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    candidate_text = read_source_text(candidate)
    if candidate_text is None:
        raise ValueError("candidate must be UTF-8 text, Markdown, or TeX")
    findings = compare_inventory(source_inventory, protected_inventory(candidate_text))
    if source.suffix.casefold() == ".tex" and candidate.suffix.casefold() == ".tex":
        semantic = _run_tex_semantic_contract(root, source, candidate)
        report["tex_semantic_contract"] = semantic
        findings.extend(semantic.get("findings", []))
    unresolved = text_diagnostics(candidate_text)["unresolved_placeholders"]
    if unresolved:
        findings.append({
            "severity": "error",
            "code": "UNRESOLVED_PROTECTED_PLACEHOLDER",
            "tokens": unresolved,
        })
    report["candidate"] = _source_record(candidate)
    report["findings"].extend(findings)
    report["status"] = "pass" if not any(
        item["severity"] == "error" for item in report["findings"]
    ) else "fail"
    report["human_review_required"] = True
    write_json(artifacts / "candidate-verification.json", report)
    return report


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--execute-native", action="store_true")
    parser.add_argument("--document-type", choices=DOCUMENT_TYPES)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = execute(
        args.registry.resolve(), args.package, args.action, args.source, args.candidate,
        args.output_dir, args.execute_native, args.document_type,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC ADAPTER {report['status'].upper()} "
            f"package={report['package']} action={report['action']}"
        )
        print(f"artifacts={report['artifact_dir']}")
        if "source" in report:
            print(f"source_sha256={report['source']['sha256']}")
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] in {"pass", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
