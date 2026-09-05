#!/usr/bin/env python3
"""Audit the local AIGC package registry and Skill entry points.

Public interface:
    python audit_aigc_stack.py [--root <AIGC-directory>] [--format text|json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from audit_role_contracts import audit as audit_role_contracts
from audit_folder_utilization import audit as audit_folder_utilization


SKILL_NAME_RE = re.compile(r"^name:\s*([^\r\n]+)$", re.MULTILINE)
DEFAULT_PROMPT_RE = re.compile(r'^\s*default_prompt:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)


def read_skill_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None
    match = SKILL_NAME_RE.search(text.split("---", 2)[1])
    return match.group(1).strip().strip('"\'') if match else None


def read_default_prompt(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    match = DEFAULT_PROMPT_RE.search(text)
    return match.group(1).strip() if match else None


def audit(root: Path, registry_path: Path) -> dict:
    payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    entries = payload.get("packages", [])
    findings: list[dict] = []
    if payload.get("schema") != "aigc-capability-portfolio/v5":
        findings.append({"severity": "error", "code": "REGISTRY_SCHEMA_MISMATCH"})
    registered = {str(entry.get("directory", "")) for entry in entries}
    actual = {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}

    for missing in sorted(registered - actual):
        findings.append({"severity": "error", "code": "REGISTERED_PACKAGE_MISSING", "directory": missing})
    for unknown in sorted(actual - registered):
        findings.append({"severity": "warning", "code": "UNREGISTERED_PACKAGE", "directory": unknown})

    names: dict[str, str] = {}
    for entry in entries:
        directory = str(entry.get("directory", ""))
        kind = str(entry.get("kind", ""))
        package_path = root / directory
        if not package_path.is_dir():
            continue
        capabilities = entry.get("capabilities", [])
        if not isinstance(capabilities, list) or not capabilities:
            findings.append({
                "severity": "error",
                "code": "CAPABILITY_LIST_MISSING",
                "directory": directory,
            })
        adapter = entry.get("adapter")
        if not isinstance(adapter, dict):
            findings.append({
                "severity": "error",
                "code": "ADAPTER_CONTRACT_MISSING",
                "directory": directory,
            })
        else:
            interfaces = adapter.get("interfaces", [])
            offline_action = adapter.get("offline_action")
            action_interface = {
                "audit": "audit",
                "prepare-candidate": "candidate",
                "workbench-plan": "workbench",
            }
            if not isinstance(interfaces, list) or not interfaces:
                findings.append({
                    "severity": "error",
                    "code": "ADAPTER_INTERFACES_MISSING",
                    "directory": directory,
                })
            if offline_action not in action_interface:
                findings.append({
                    "severity": "error",
                    "code": "ADAPTER_OFFLINE_ACTION_INVALID",
                    "directory": directory,
                    "value": offline_action,
                })
            elif action_interface[offline_action] not in interfaces:
                findings.append({
                    "severity": "error",
                    "code": "ADAPTER_OFFLINE_INTERFACE_MISMATCH",
                    "directory": directory,
                    "action": offline_action,
                })
            native_entrypoints = adapter.get("native_entrypoints", [])
            if not isinstance(native_entrypoints, list) or not native_entrypoints:
                findings.append({
                    "severity": "error",
                    "code": "ADAPTER_NATIVE_ENTRYPOINTS_MISSING",
                    "directory": directory,
                })
            else:
                for relative in native_entrypoints:
                    native_path = package_path / str(relative)
                    if not native_path.is_file():
                        findings.append({
                            "severity": "error",
                            "code": "ADAPTER_NATIVE_ENTRYPOINT_MISSING",
                            "directory": directory,
                            "path": str(relative),
                        })
            if not adapter.get("safe_boundary"):
                findings.append({
                    "severity": "error",
                    "code": "ADAPTER_SAFE_BOUNDARY_MISSING",
                    "directory": directory,
                })
        if kind in {"skill", "router"}:
            skill_path = package_path / "SKILL.md"
            if not skill_path.is_file():
                findings.append({"severity": "error", "code": "SKILL_ENTRY_MISSING", "directory": directory})
                continue
            actual_name = read_skill_name(skill_path)
            expected_name = str(entry.get("skill_name", ""))
            if actual_name != expected_name:
                findings.append({
                    "severity": "error",
                    "code": "SKILL_NAME_MISMATCH",
                    "directory": directory,
                    "expected": expected_name,
                    "actual": actual_name,
                })
            if actual_name:
                if actual_name in names:
                    findings.append({
                        "severity": "error",
                        "code": "DUPLICATE_SKILL_NAME",
                        "name": actual_name,
                        "directories": [names[actual_name], directory],
                    })
                names[actual_name] = directory
                agent_path = package_path / "agents" / "openai.yaml"
                if not agent_path.is_file():
                    findings.append({
                        "severity": "warning",
                        "code": "OPENAI_ENTRY_MISSING",
                        "directory": directory,
                    })
                else:
                    default_prompt = read_default_prompt(agent_path)
                    expected_call = f"${actual_name}"
                    if not default_prompt or expected_call not in default_prompt:
                        findings.append({
                            "severity": "error",
                            "code": "OPENAI_CALL_NAME_MISMATCH",
                            "directory": directory,
                            "expected": expected_call,
                            "actual": default_prompt,
                        })

        if kind == "imported-skill":
            entrypoints = entry.get("skill_entrypoints", [])
            if not isinstance(entrypoints, list) or not entrypoints:
                findings.append({
                    "severity": "error",
                    "code": "IMPORTED_SKILL_ENTRYPOINTS_MISSING",
                    "directory": directory,
                })
            for imported in entrypoints:
                relative = str(imported.get("path", ""))
                skill_path = package_path / relative
                expected_name = str(imported.get("skill_name", ""))
                if not skill_path.is_file():
                    findings.append({
                        "severity": "error",
                        "code": "IMPORTED_SKILL_ENTRYPOINT_MISSING",
                        "directory": directory,
                        "path": relative,
                    })
                    continue
                actual_name = read_skill_name(skill_path)
                if actual_name != expected_name:
                    findings.append({
                        "severity": "error",
                        "code": "IMPORTED_SKILL_NAME_MISMATCH",
                        "directory": directory,
                        "path": relative,
                        "expected": expected_name,
                        "actual": actual_name,
                    })
                if actual_name:
                    location = f"{directory}/{relative}"
                    if actual_name in names:
                        findings.append({
                            "severity": "error",
                            "code": "DUPLICATE_SKILL_NAME",
                            "name": actual_name,
                            "directories": [names[actual_name], location],
                        })
                    names[actual_name] = location

        if kind == "application" and entry.get("route") != "manual_external_app":
            findings.append({
                "severity": "error",
                "code": "APPLICATION_ROUTE_MUST_BE_MANUAL",
                "directory": directory,
                "route": entry.get("route"),
            })
        if entry.get("status") == "unavailable":
            findings.append({
                "severity": "error",
                "code": "REGISTERED_PACKAGE_LEFT_UNAVAILABLE",
                "directory": directory,
            })
        if kind == "library" and entry.get("route") != "adapted_reference_implementation":
            findings.append({
                "severity": "error",
                "code": "LIBRARY_ROUTE_MISMATCH",
                "directory": directory,
                "route": entry.get("route"),
            })

    required_routes = {
        "portfolio_orchestrator": (1, "active"),
        "academic_style_engine": (1, "active"),
        "independent_academic_candidate": (1, "explicit_only"),
        "primary_general_english_editor": (1, "active"),
        "primary_general_chinese_editor": (1, "active"),
        "english_academic_style_engine": (1, "explicit_only"),
        "medical_english_academic_editor": (1, "explicit_only"),
        "multilingual_semantic_auditor": (1, "explicit_only"),
        "general_english_diagnostic_editor": (1, "explicit_only"),
        "general_english_voice_candidate": (1, "explicit_only"),
        "general_copy_candidate_lab": (1, "explicit_only"),
        "adapted_reference_implementation": (1, "adapted"),
        "reconstructed_candidate_lab": (1, "explicit_only"),
    }
    for route, (expected_count, expected_status) in required_routes.items():
        matched = [entry for entry in entries if entry.get("route") == route]
        actual_count = len(matched)
        if actual_count != expected_count:
            findings.append({
                "severity": "error",
                "code": "CAPABILITY_ROUTE_COUNT",
                "route": route,
                "expected": expected_count,
                "actual": actual_count,
            })
        for entry in matched:
            if entry.get("status") != expected_status:
                findings.append({
                    "severity": "error",
                    "code": "CAPABILITY_ROUTE_STATUS",
                    "route": route,
                    "expected": expected_status,
                    "actual": entry.get("status"),
                })
    routers = [entry for entry in entries if entry.get("kind") == "router" and entry.get("status") == "active"]
    if len(routers) != 1:
        findings.append({"severity": "error", "code": "ACTIVE_ROUTER_COUNT", "actual": len(routers)})

    expected_external_routes = {
        "academic_scene_orchestrator",
        "modeling_scene_owner",
        "research_scene_owner",
        "course_scene_owner",
        "cumcm_genre_owner",
    }
    external_routes = {str(item.get("route", "")) for item in payload.get("external_authorities", [])}
    for missing_route in sorted(expected_external_routes - external_routes):
        findings.append({
            "severity": "error",
            "code": "EXTERNAL_AUTHORITY_ROUTE_MISSING",
            "route": missing_route,
        })

    for external in payload.get("external_authorities", []):
        path = (root / str(external.get("path", ""))).resolve()
        skill_path = path / "SKILL.md"
        if not skill_path.is_file():
            findings.append({"severity": "error", "code": "EXTERNAL_AUTHORITY_MISSING", "path": str(path)})
            continue
        actual_name = read_skill_name(skill_path)
        if actual_name != external.get("skill_name"):
            findings.append({
                "severity": "error",
                "code": "EXTERNAL_AUTHORITY_NAME_MISMATCH",
                "path": str(path),
                "expected": external.get("skill_name"),
                "actual": actual_name,
            })
        if external.get("status") != "active":
            findings.append({
                "severity": "error",
                "code": "EXTERNAL_AUTHORITY_INACTIVE",
                "path": str(path),
                "status": external.get("status"),
            })

    role_contract_path = registry_path.parent / "role-contracts.json"
    if not role_contract_path.is_file():
        findings.append({"severity": "error", "code": "ROLE_CONTRACT_FILE_MISSING"})
        role_report = None
    else:
        role_report = audit_role_contracts(registry_path, role_contract_path)
        for item in role_report.get("findings", []):
            findings.append({**item, "source": "role-contracts"})

    folder_catalog_path = registry_path.parent / "folder-utilization.json"
    if not folder_catalog_path.is_file():
        findings.append({"severity": "error", "code": "FOLDER_UTILIZATION_CATALOG_MISSING"})
        folder_report = None
    else:
        folder_report = audit_folder_utilization(root, registry_path, folder_catalog_path)
        for item in folder_report.get("findings", []):
            findings.append({**item, "source": "folder-utilization"})

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "root": str(root.resolve()),
        "registered_packages": len(entries),
        "discovered_directories": len(actual),
        "skill_entries": len(names),
        "adapted_packages": sum(isinstance(entry.get("adapter"), dict) for entry in entries),
        "role_contracts": None if role_report is None else {
            "status": role_report.get("status"),
            "packages": role_report.get("packages"),
            "providers": role_report.get("providers"),
            "scenarios": role_report.get("scenarios"),
            "covered_packages": role_report.get("covered_packages"),
            "content_roles": role_report.get("content_roles"),
        },
        "folder_utilization": None if folder_report is None else {
            "status": folder_report.get("status"),
            "top_level_registered": folder_report.get("top_level_registered"),
            "top_level_discovered": folder_report.get("top_level_discovered"),
            "embedded_manifests_discovered": folder_report.get("embedded_manifests_discovered"),
            "embedded_manifests_declared": folder_report.get("embedded_manifests_declared"),
            "embedded_manifest_tree_sha256": folder_report.get("embedded_manifest_tree_sha256"),
            "catalog_sha256": folder_report.get("catalog_sha256"),
            "ai_paper_entry_classes_verified": folder_report.get("ai_paper_entry_classes_verified"),
            "dispositions": folder_report.get("dispositions"),
        },
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    default_root = skill_root.parent
    default_registry = skill_root / "references" / "stack-registry.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--registry", type=Path, default=default_registry)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.root.resolve(), args.registry.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC STACK {report['status'].upper()} errors={report['errors']} "
            f"warnings={report['warnings']} registered={report['registered_packages']} "
            f"skills={report['skill_entries']} adapted={report['adapted_packages']}"
        )
        print(f"root={report['root']}")
        role_contracts = report.get("role_contracts")
        if role_contracts:
            print(
                f"role_contracts={role_contracts['status']} "
                f"packages={role_contracts['packages']} providers={role_contracts['providers']} "
                f"scenarios={role_contracts['scenarios']} "
                f"covered={role_contracts['covered_packages']} "
                f"content_roles={role_contracts.get('content_roles', 0)}"
            )
        folder_utilization = report.get("folder_utilization")
        if folder_utilization:
            print(
                f"folder_utilization={folder_utilization['status']} "
                f"top_level={folder_utilization['top_level_registered']}/{folder_utilization['top_level_discovered']} "
                f"embedded={folder_utilization['embedded_manifests_declared']}/{folder_utilization['embedded_manifests_discovered']} "
                f"AI_paper_classes={folder_utilization['ai_paper_entry_classes_verified']} "
                f"dispositions={folder_utilization['dispositions']}"
            )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
