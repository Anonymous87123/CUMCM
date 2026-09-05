#!/usr/bin/env python3
"""Audit complete role contracts and scene coverage for the AIGC portfolio.

Public interface:
    python audit_role_contracts.py [--registry PATH] [--contracts PATH]
        [--content-contracts PATH] [--format text|json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import read_registry
from route_aigc_tools import select_route
from validate_role_evidence import MANUAL_SPECS, NATIVE_MCM_RULES


CONTRACT_SCHEMA = "aigc-role-contracts/v1"
CONTENT_CONTRACT_SCHEMA = "aigc-content-role-contracts/v1"
KNOWN_SCENES = {
    "portfolio", "mcm", "modeling", "research", "course-notes",
    "academic-mixed", "academic-en", "medical-en", "technical",
    "general-en", "general-zh", "external-app",
}
KNOWN_ROLE_CLASSES = {
    "orchestrator", "protected-editor", "independent-candidate",
    "primary-editor", "domain-editor", "semantic-reviewer",
    "diagnostic-reviewer", "voice-editor", "candidate-and-review-lab",
    "diagnostic-workbench", "pdf-review-workbench", "authoring-workbench",
    "legacy-baseline", "deployment-workbench", "document-governance",
    "remote-candidate-lab", "research-baseline", "reference-workbench",
    "comparison-lab",
}
KNOWN_INTERFACES = {"audit", "candidate", "workbench"}
WORKBENCH_ROLES = {
    "diagnostic-workbench", "pdf-review-workbench", "authoring-workbench",
    "legacy-baseline", "deployment-workbench", "document-governance",
    "remote-candidate-lab", "research-baseline", "reference-workbench",
    "comparison-lab",
}
RECEIPT_EVIDENCE_VALIDATORS = set(MANUAL_SPECS) | set(NATIVE_MCM_RULES) | {
    "audit-report", "candidate-task", "candidate-file", "candidate-verification",
    "native-run-report", "workbench-plan", "export-artifact",
    "content-density-report", "manuscript-audit",
}
PORTFOLIO_LEVEL_EVIDENCE = {"route-plan", "human-decision", "blind-score", "release-gates"}


def _registry_providers(entry: dict) -> set[str]:
    providers: set[str] = set()
    if entry.get("skill_name"):
        providers.add(str(entry["skill_name"]))
    providers.update(str(value) for value in entry.get("aliases", []) if value)
    providers.update(
        str(item.get("skill_name"))
        for item in entry.get("skill_entrypoints", [])
        if item.get("skill_name")
    )
    return providers


def _provider_index(contracts: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for contract in contracts:
        for provider in contract.get("providers", []):
            if provider not in index:
                index[str(provider)] = contract
    return index


def _external_provider_index(registry: dict) -> set[str]:
    return {
        str(item.get("skill_name"))
        for item in registry.get("external_authorities", [])
        if item.get("skill_name")
    }


def _add(findings: list[dict], severity: str, code: str, **detail: object) -> None:
    findings.append({"severity": severity, "code": code, **detail})


def _audit_content_contracts(path: Path, registry: dict, scenarios: list[dict], findings: list[dict]) -> int:
    """Validate the scene-owner contracts that live outside the 21-package table."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _add(findings, "error", "CONTENT_CONTRACTS_UNREADABLE", path=str(path), detail=str(exc))
        return 0
    if payload.get("schema") != CONTENT_CONTRACT_SCHEMA:
        _add(findings, "error", "CONTENT_CONTRACT_SCHEMA_MISMATCH", actual=payload.get("schema"))
    evidence_types = set(payload.get("evidence_types", []))
    external = {
        str(item.get("skill_name"))
        for item in registry.get("external_authorities", [])
        if item.get("skill_name")
    }
    roles = payload.get("roles", [])
    seen: set[str] = set()
    for role in roles if isinstance(roles, list) else []:
        provider = str(role.get("provider", ""))
        if not provider or provider in seen:
            _add(findings, "error", "CONTENT_ROLE_DUPLICATE_OR_EMPTY", provider=provider)
        seen.add(provider)
        if provider not in external:
            _add(findings, "error", "CONTENT_ROLE_NOT_EXTERNAL_AUTHORITY", provider=provider)
        scenes = set(role.get("scenes", []))
        if not scenes or scenes - KNOWN_SCENES:
            _add(findings, "error", "CONTENT_ROLE_SCENES_INVALID", provider=provider, unknown=sorted(scenes - KNOWN_SCENES))
        required = role.get("required_evidence", [])
        unknown = set(required) - evidence_types
        if not required or unknown:
            _add(findings, "error", "CONTENT_ROLE_EVIDENCE_INVALID", provider=provider, unknown=sorted(unknown))
        unvalidated = set(required) - RECEIPT_EVIDENCE_VALIDATORS
        if unvalidated:
            _add(
                findings, "error", "CONTENT_ROLE_EVIDENCE_UNVALIDATED",
                provider=provider, evidence=sorted(unvalidated),
            )
        if not isinstance(role.get("deliverables"), list) or not role.get("deliverables"):
            _add(findings, "error", "CONTENT_ROLE_DELIVERABLES_MISSING", provider=provider)
    expected_by_scene = {
        "mcm": {"deai-academic-writing", "mcm-cup-standard-write", "deai-modeling-writing"},
        "modeling": {"deai-academic-writing", "deai-modeling-writing"},
        "research": {"deai-academic-writing", "deai-research-writing"},
        "course-notes": {"deai-academic-writing", "deai-course-notes"},
        "academic-mixed": {"deai-academic-writing", "deai-modeling-writing", "deai-research-writing", "deai-course-notes"},
    }
    for scene, expected in expected_by_scene.items():
        scenario = next((item for item in scenarios if item.get("document_type") == scene), {})
        actual = set(scenario.get("default_providers", [])) & expected
        if actual != expected:
            _add(findings, "error", "CONTENT_ROLE_SCENE_CHAIN_MISMATCH", scene=scene, expected=sorted(expected), actual=sorted(actual))
    return len(seen)


def audit(registry_path: Path, contracts_path: Path, content_contracts_path: Path | None = None) -> dict:
    registry = read_registry(registry_path)
    payload = json.loads(contracts_path.read_text(encoding="utf-8-sig"))
    findings: list[dict] = []
    if payload.get("schema") != CONTRACT_SCHEMA:
        _add(findings, "error", "ROLE_CONTRACT_SCHEMA_MISMATCH", actual=payload.get("schema"))

    registry_entries = {
        str(entry.get("directory")): entry for entry in registry.get("packages", [])
    }
    contracts = payload.get("packages", [])
    if not isinstance(contracts, list):
        contracts = []
        _add(findings, "error", "ROLE_CONTRACT_PACKAGE_LIST_INVALID")
    contract_entries = {
        str(item.get("directory")): item for item in contracts if isinstance(item, dict)
    }
    if len(contract_entries) != len(contracts):
        _add(findings, "error", "ROLE_CONTRACT_DIRECTORY_DUPLICATE_OR_EMPTY")
    for missing in sorted(set(registry_entries) - set(contract_entries)):
        _add(findings, "error", "ROLE_CONTRACT_MISSING", directory=missing)
    for unknown in sorted(set(contract_entries) - set(registry_entries)):
        _add(findings, "error", "ROLE_CONTRACT_UNKNOWN_PACKAGE", directory=unknown)

    evidence_types = set(payload.get("evidence_types", []))
    provider_seen: dict[str, str] = {}
    for directory, contract in contract_entries.items():
        entry = registry_entries.get(directory)
        if entry is None:
            continue
        providers = contract.get("providers", [])
        if not isinstance(providers, list) or not providers:
            _add(findings, "error", "ROLE_PROVIDERS_MISSING", directory=directory)
            providers = []
        actual_providers = {str(item) for item in providers}
        expected_providers = _registry_providers(entry)
        if actual_providers != expected_providers:
            _add(
                findings, "error", "ROLE_PROVIDER_SET_MISMATCH", directory=directory,
                expected=sorted(expected_providers), actual=sorted(actual_providers),
            )
        for provider in actual_providers:
            if provider in provider_seen:
                _add(
                    findings, "error", "ROLE_PROVIDER_DUPLICATE", provider=provider,
                    directories=[provider_seen[provider], directory],
                )
            provider_seen[provider] = directory

        role_class = str(contract.get("role_class", ""))
        if role_class not in KNOWN_ROLE_CLASSES:
            _add(findings, "error", "ROLE_CLASS_INVALID", directory=directory, value=role_class)
        scenes = set(contract.get("scenes", []))
        if not scenes or scenes - KNOWN_SCENES:
            _add(
                findings, "error", "ROLE_SCENES_INVALID", directory=directory,
                unknown=sorted(scenes - KNOWN_SCENES),
            )
        required_interfaces = set(contract.get("required_interfaces", []))
        adapter_interfaces = set(entry.get("adapter", {}).get("interfaces", []))
        if not required_interfaces or required_interfaces - KNOWN_INTERFACES:
            _add(
                findings, "error", "ROLE_REQUIRED_INTERFACES_INVALID", directory=directory,
                value=sorted(required_interfaces),
            )
        if required_interfaces - adapter_interfaces:
            _add(
                findings, "error", "ROLE_INTERFACE_NOT_IMPLEMENTED", directory=directory,
                missing=sorted(required_interfaces - adapter_interfaces),
            )
        completion = set(contract.get("completion_evidence", []))
        unknown_evidence = completion - evidence_types
        if not completion or unknown_evidence:
            _add(
                findings, "error", "ROLE_COMPLETION_EVIDENCE_INVALID", directory=directory,
                unknown=sorted(unknown_evidence),
            )
        unvalidated_evidence = completion - RECEIPT_EVIDENCE_VALIDATORS - PORTFOLIO_LEVEL_EVIDENCE
        if unvalidated_evidence:
            _add(
                findings, "error", "ROLE_COMPLETION_EVIDENCE_UNVALIDATED",
                directory=directory, evidence=sorted(unvalidated_evidence),
            )
        if "audit" in required_interfaces and role_class != "orchestrator" and "audit-report" not in completion:
            _add(findings, "error", "ROLE_AUDIT_EVIDENCE_MISSING", directory=directory)
        if "candidate" in required_interfaces:
            for item in ("candidate-task", "candidate-verification", "human-decision"):
                if item not in completion:
                    _add(
                        findings, "error", "ROLE_CANDIDATE_EVIDENCE_MISSING",
                        directory=directory, evidence=item,
                    )
        if "workbench" in required_interfaces and role_class != "orchestrator" and "workbench-plan" not in completion:
            _add(findings, "error", "ROLE_WORKBENCH_EVIDENCE_MISSING", directory=directory)
        if role_class in WORKBENCH_ROLES and "workbench" not in required_interfaces:
            _add(findings, "error", "ROLE_WORKBENCH_INTERFACE_MISSING", directory=directory)
        for field in ("deliverables", "must_not_claim"):
            value = contract.get(field, [])
            if not isinstance(value, list) or not value or any(not str(item).strip() for item in value):
                _add(findings, "error", "ROLE_TEXT_LIST_MISSING", directory=directory, field=field)
        if not str(contract.get("fallback", "")).strip():
            _add(findings, "error", "ROLE_FALLBACK_MISSING", directory=directory)

    provider_index = _provider_index(contracts)
    external_providers = _external_provider_index(registry)
    scenarios = payload.get("scenarios", [])
    scenario_types: set[str] = set()
    covered_directories: set[str] = set()
    for scenario in scenarios if isinstance(scenarios, list) else []:
        document_type = str(scenario.get("document_type", ""))
        if document_type in scenario_types:
            _add(findings, "error", "ROLE_SCENARIO_DUPLICATE", document_type=document_type)
        scenario_types.add(document_type)
        if document_type not in KNOWN_SCENES - {"portfolio"}:
            _add(findings, "error", "ROLE_SCENARIO_UNKNOWN", document_type=document_type)
            continue
        entry_provider = str(scenario.get("entry_provider", ""))
        groups = (
            [entry_provider]
            + list(scenario.get("default_providers", []))
            + list(scenario.get("allowed_editors", []))
            + list(scenario.get("allowed_reviewers", []))
            + list(scenario.get("allowed_workbenches", []))
        )
        for provider in groups:
            provider = str(provider)
            contract = provider_index.get(provider)
            if contract is None:
                if provider not in external_providers:
                    _add(
                        findings, "error", "ROLE_SCENARIO_PROVIDER_UNKNOWN",
                        document_type=document_type, provider=provider,
                    )
                continue
            covered_directories.add(str(contract["directory"]))
            if document_type not in set(contract.get("scenes", [])):
                _add(
                    findings, "error", "ROLE_SCENE_NOT_ALLOWED",
                    document_type=document_type, provider=provider,
                )

        if not scenario.get("hard_gates") or not scenario.get("human_gates"):
            _add(findings, "error", "ROLE_SCENARIO_GATES_MISSING", document_type=document_type)

        if document_type == "external-app":
            for provider in scenario.get("allowed_workbenches", []):
                report = select_route("external-app", "audit", requested_app=str(provider))
                if report.get("status") != "pass":
                    _add(
                        findings, "error", "ROLE_EXTERNAL_ROUTE_FAILED",
                        provider=provider, route_findings=report.get("findings", []),
                    )
            continue

        report = select_route(
            document_type,
            str(scenario.get("intent", "rewrite")),
            str(scenario.get("document_format", "plain")),
            str(scenario.get("scope", "document")),
        )
        route_providers = [str(item.get("provider")) for item in report.get("stages", [])]
        expected = [str(item) for item in scenario.get("default_providers", [])]
        if report.get("status") != "pass" or route_providers != expected:
            _add(
                findings, "error", "ROLE_DEFAULT_ROUTE_MISMATCH",
                document_type=document_type, expected=expected, actual=route_providers,
                     route_findings=report.get("findings", []),
                 )

        for editor in scenario.get("allowed_editors", []):
            editor_scope = "local" if editor == "baibai-aigc" else str(scenario.get("scope", "document"))
            edited = select_route(
                document_type, str(scenario.get("intent", "rewrite")),
                str(scenario.get("document_format", "plain")), editor_scope,
                requested_editor=str(editor),
            )
            if edited.get("status") != "pass" or str(editor) not in [
                str(item.get("provider")) for item in edited.get("stages", [])
            ]:
                _add(
                    findings, "error", "ROLE_EDITOR_ROUTE_FAILED",
                    document_type=document_type, provider=editor,
                    route_findings=edited.get("findings", []),
                )
        for reviewer in scenario.get("allowed_reviewers", []):
            reviewed = select_route(
                document_type, "audit", str(scenario.get("document_format", "plain")),
                str(scenario.get("scope", "document")), requested_reviewer=str(reviewer),
            )
            if reviewed.get("status") != "pass" or str(reviewer) not in [
                str(item.get("provider")) for item in reviewed.get("stages", [])
            ]:
                _add(
                    findings, "error", "ROLE_REVIEWER_ROUTE_FAILED",
                    document_type=document_type, provider=reviewer,
                    route_findings=reviewed.get("findings", []),
                )
        for workbench in scenario.get("allowed_workbenches", []):
            planned = select_route(
                document_type, "audit", str(scenario.get("document_format", "plain")),
                str(scenario.get("scope", "document")), requested_app=str(workbench),
            )
            if planned.get("status") != "pass" or str(workbench) not in [
                str(item.get("provider")) for item in planned.get("stages", [])
            ]:
                _add(
                    findings, "error", "ROLE_WORKBENCH_ROUTE_FAILED",
                    document_type=document_type, provider=workbench,
                    route_findings=planned.get("findings", []),
                )

    content_path = content_contracts_path or registry_path.parent / "content-role-contracts.json"
    content_roles = _audit_content_contracts(content_path, registry, scenarios if isinstance(scenarios, list) else [], findings)

    expected_scenarios = KNOWN_SCENES - {"portfolio"}
    for missing in sorted(expected_scenarios - scenario_types):
        _add(findings, "error", "ROLE_SCENARIO_MISSING", document_type=missing)
    for directory in sorted(set(contract_entries) - covered_directories):
        _add(findings, "error", "ROLE_PACKAGE_UNUSED_IN_SCENARIOS", directory=directory)

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "schema": "aigc-role-contract-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "packages": len(contract_entries),
        "providers": len(provider_seen),
        "scenarios": len(scenario_types),
        "covered_packages": len(covered_directories),
        "content_roles": content_roles,
        "receipt_evidence_validators": len(RECEIPT_EVIDENCE_VALIDATORS),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument(
        "--contracts", type=Path,
        default=skill_root / "references" / "role-contracts.json",
    )
    parser.add_argument(
        "--content-contracts", type=Path,
        default=skill_root / "references" / "content-role-contracts.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.registry.resolve(), args.contracts.resolve(), args.content_contracts.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC ROLE CONTRACTS {report['status'].upper()} "
            f"packages={report['packages']} providers={report['providers']} "
            f"scenarios={report['scenarios']} covered={report['covered_packages']} "
            f"errors={report['errors']} warnings={report['warnings']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
