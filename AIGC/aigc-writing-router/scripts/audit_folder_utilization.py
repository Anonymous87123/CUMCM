#!/usr/bin/env python3
"""Audit every embedded AIGC Skill manifest and its declared utilization.

Public interface:
    python audit_folder_utilization.py [--root AIGC] [--format text|json]

The audit is deliberately stricter than a package-directory check.  It finds
nested ``SKILL.md`` and AI_paper ``skill.json`` files, binds their bytes to a
reviewed manifest-tree hash, and requires each one to be routed, explicitly
alternative, canonical, or development-only.  "Not needed for this document"
is a valid declared disposition; silently undiscovered is not.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "aigc-folder-utilization/v1"
IGNORED_DIRECTORIES = {"node_modules", "target", ".git", "__pycache__", ".pytest_cache"}
DISPOSITIONS = {
    "workbench-capability",
    "independent-alternative",
    "research-only",
    "routed-reviewer",
    "canonical-entry",
    "maintenance-only",
}
NAME_RE = re.compile(r"^name:\s*([^\r\n]+)$", re.MULTILINE)


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _ignored(path: Path, root: Path) -> bool:
    return bool(set(path.resolve().relative_to(root.resolve()).parts) & IGNORED_DIRECTORIES)


def _iter_manifest_files(root: Path, names: set[str]) -> list[Path]:
    """Discover manifests without descending into dependency/build trees."""
    discovered: list[Path] = []
    for current, directories, files in os.walk(root):
        directories[:] = [
            name for name in directories
            if name not in IGNORED_DIRECTORIES
        ]
        current_path = Path(current)
        discovered.extend(current_path / name for name in files if name in names)
    return sorted(discovered, key=lambda path: _relative(path, root).casefold())


def _discover(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in _iter_manifest_files(root, {"SKILL.md"}):
        relative = _relative(path, root)
        parts = relative.split("/")
        # Top-level package SKILL.md files are already owned by stack-registry.
        if len(parts) == 2 and parts[1] == "SKILL.md":
            continue
        raw = path.read_bytes()
        records.append({"path": relative, "sha256": _sha256(raw), "bytes": len(raw)})

    # ``skill.json`` is not limited to the current AI_paper location.  Scan
    # every non-ignored nested manifest so a newly imported package cannot
    # silently add a second kind of Skill entrypoint.
    for path in _iter_manifest_files(root, {"skill.json"}):
        raw = path.read_bytes()
        records.append({
            "path": _relative(path, root),
            "sha256": _sha256(raw),
            "bytes": len(raw),
        })
    return sorted(records, key=lambda item: str(item["path"]).encode("utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _skill_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None
    frontmatter = text.split("---", 2)[1]
    match = NAME_RE.search(frontmatter)
    return match.group(1).strip().strip("\"'") if match else None


def _registry_provider_set(registry: dict[str, Any]) -> set[str]:
    providers: set[str] = set()
    for package in registry.get("packages", []):
        if isinstance(package, dict):
            providers.update(str(item) for item in package.get("providers", []))
    return providers


def _role_contract_provider_set(role_contracts_path: Path) -> set[str]:
    """Collect provider names from package and scenario role contracts."""
    if not role_contracts_path.is_file():
        return set()
    payload = _load_json(role_contracts_path)
    providers: set[str] = set()
    for package in payload.get("packages", []):
        if isinstance(package, dict):
            providers.update(str(item) for item in package.get("providers", []))
    for scenario in payload.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        for field in ("entry_provider", "default_providers", "allowed_editors", "allowed_reviewers", "allowed_workbenches"):
            value = scenario.get(field)
            if isinstance(value, list):
                providers.update(str(item) for item in value)
            elif isinstance(value, str) and value:
                providers.add(value)
    return providers


def audit(root: Path, registry_path: Path, catalog_path: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    registry_path = registry_path.resolve(strict=True)
    catalog_path = catalog_path.resolve(strict=True)
    registry = _load_json(registry_path)
    catalog = _load_json(catalog_path)
    findings: list[dict[str, Any]] = []
    catalog_sha256 = _sha256(catalog_path.read_bytes())

    if catalog.get("schema") != SCHEMA:
        findings.append({"severity": "error", "code": "FOLDER_CATALOG_SCHEMA_MISMATCH"})
    declared_registry = str(catalog.get("source_registry", ""))
    declared_registry_path = (catalog_path.parent / declared_registry).resolve() if declared_registry else None
    if declared_registry_path != registry_path:
        findings.append({
            "severity": "error",
            "code": "FOLDER_CATALOG_REGISTRY_BINDING_MISMATCH",
            "expected": str(registry_path),
            "actual": str(declared_registry_path) if declared_registry_path else declared_registry,
        })
    expected_catalog_sha256 = str(registry.get("folder_utilization_catalog_sha256", ""))
    if expected_catalog_sha256 != catalog_sha256:
        findings.append({
            "severity": "error",
            "code": "FOLDER_CATALOG_HASH_DRIFT",
            "expected": expected_catalog_sha256 or None,
            "actual": catalog_sha256,
        })

    packages = registry.get("packages", [])
    registered = {str(item.get("directory", "")) for item in packages if isinstance(item, dict)}
    actual = {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}
    for directory in sorted(registered - actual):
        findings.append({"severity": "error", "code": "TOP_LEVEL_PACKAGE_MISSING", "directory": directory})
    for directory in sorted(actual - registered):
        findings.append({"severity": "error", "code": "TOP_LEVEL_PACKAGE_UNREGISTERED", "directory": directory})

    discovered = _discover(root)
    discovered_by_path = {str(item["path"]): item for item in discovered}
    declared = catalog.get("embedded_manifests", [])
    if not isinstance(declared, list):
        declared = []
        findings.append({"severity": "error", "code": "EMBEDDED_MANIFEST_LIST_MISSING"})
    declared_by_path: dict[str, dict[str, Any]] = {}
    for item in declared:
        if not isinstance(item, dict):
            findings.append({"severity": "error", "code": "EMBEDDED_RECORD_NOT_OBJECT"})
            continue
        path = str(item.get("path", ""))
        if not path or path in declared_by_path:
            findings.append({"severity": "error", "code": "EMBEDDED_RECORD_DUPLICATE_OR_EMPTY", "path": path})
            continue
        declared_by_path[path] = item

    for path in sorted(set(discovered_by_path) - set(declared_by_path)):
        findings.append({"severity": "error", "code": "EMBEDDED_MANIFEST_UNREGISTERED", "path": path})
    for path in sorted(set(declared_by_path) - set(discovered_by_path)):
        findings.append({"severity": "error", "code": "CATALOG_PATH_NOT_DISCOVERED", "path": path})

    current_tree_hash = _sha256(_canonical(discovered))
    if catalog.get("expected_embedded_manifest_tree_sha256") != current_tree_hash:
        findings.append({
            "severity": "error",
            "code": "EMBEDDED_MANIFEST_TREE_DRIFT",
            "expected": catalog.get("expected_embedded_manifest_tree_sha256"),
            "actual": current_tree_hash,
        })

    package_by_directory = {str(item.get("directory", "")): item for item in packages if isinstance(item, dict)}
    provider_set = _registry_provider_set(registry)
    provider_set.update(_role_contract_provider_set(registry_path.parent / "role-contracts.json"))
    dispositions: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    required_fields = {"path", "owner", "kind", "id", "disposition", "activation", "scenes", "entrypoint"}
    for path, item in sorted(declared_by_path.items()):
        missing = sorted(required_fields - set(item))
        if missing:
            findings.append({"severity": "error", "code": "EMBEDDED_RECORD_FIELDS_MISSING", "path": path, "fields": missing})
            continue
        disposition = str(item.get("disposition"))
        dispositions[disposition] += 1
        if disposition not in DISPOSITIONS:
            findings.append({"severity": "error", "code": "EMBEDDED_DISPOSITION_INVALID", "path": path, "value": disposition})
        owner = str(item.get("owner"))
        if owner not in package_by_directory:
            findings.append({"severity": "error", "code": "EMBEDDED_OWNER_NOT_REGISTERED", "path": path, "owner": owner})
        if not isinstance(item.get("activation"), str) or not item["activation"].strip():
            findings.append({"severity": "error", "code": "EMBEDDED_ACTIVATION_MISSING", "path": path})
        scenes = item.get("scenes")
        if not isinstance(scenes, list) or not scenes or not all(isinstance(scene, str) and scene for scene in scenes):
            findings.append({"severity": "error", "code": "EMBEDDED_SCENES_MISSING", "path": path})
        actual_path = root / Path(path)
        if not actual_path.is_file():
            findings.append({"severity": "error", "code": "EMBEDDED_FILE_MISSING", "path": path})
            continue
        if str(item.get("entrypoint", "")) and not (root / Path(str(item["entrypoint"]))).is_file():
            findings.append({"severity": "error", "code": "EMBEDDED_ENTRYPOINT_MISSING", "path": path, "entrypoint": item.get("entrypoint")})
        discovered_item = discovered_by_path.get(path, {})
        entry_class_verified = None
        if item.get("sha256") is not None or item.get("bytes") is not None:
            findings.append({"severity": "error", "code": "EMBEDDED_RECORD_MUST_USE_TREE_BINDING", "path": path})

        if path.startswith("AI_paper/Management/skills_src/"):
            if item.get("kind") != "ai-paper-skill-json" or owner != "AI_paper":
                findings.append({"severity": "error", "code": "AI_PAPER_EMBEDDED_CLASSIFICATION_INVALID", "path": path})
            try:
                manifest = _load_json(actual_path)
                if manifest.get("id") != item.get("id"):
                    findings.append({"severity": "error", "code": "AI_PAPER_SKILL_ID_MISMATCH", "path": path, "expected": item.get("id"), "actual": manifest.get("id")})
                entry = manifest.get("entry")
                if not isinstance(entry, dict) or not entry.get("module") or not entry.get("class"):
                    findings.append({"severity": "error", "code": "AI_PAPER_ENTRY_DECLARATION_INVALID", "path": path})
                else:
                    module_name = str(entry.get("module"))
                    module_path = actual_path.parent / (module_name.replace(".", "/") + ".py")
                    if not module_path.is_file():
                        findings.append({"severity": "error", "code": "AI_PAPER_ENTRY_MODULE_MISSING", "path": path, "module": module_name})
                    else:
                        try:
                            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
                            entry_class_verified = any(
                                isinstance(node, ast.ClassDef) and node.name == str(entry.get("class"))
                                for node in ast.walk(tree)
                            )
                            if not entry_class_verified:
                                findings.append({
                                    "severity": "error",
                                    "code": "AI_PAPER_ENTRY_CLASS_MISSING",
                                    "path": path,
                                    "class": entry.get("class"),
                                    "module": str(module_path),
                                })
                        except (OSError, UnicodeError, SyntaxError) as exc:
                            findings.append({
                                "severity": "error",
                                "code": "AI_PAPER_ENTRY_SYNTAX_INVALID",
                                "path": path,
                                "module": str(module_path),
                                "detail": str(exc),
                            })
            except (OSError, UnicodeError, ValueError) as exc:
                findings.append({"severity": "error", "code": "AI_PAPER_MANIFEST_INVALID", "path": path, "detail": str(exc)})
        else:
            try:
                actual_name = _skill_name(actual_path)
            except (OSError, UnicodeError) as exc:
                actual_name = None
                findings.append({"severity": "error", "code": "EMBEDDED_SKILL_UNREADABLE", "path": path, "detail": str(exc)})
            if actual_name != item.get("id"):
                findings.append({"severity": "error", "code": "EMBEDDED_SKILL_NAME_MISMATCH", "path": path, "expected": item.get("id"), "actual": actual_name})

        if disposition == "maintenance-only":
            if owner != "GankAIGC-2.1.0" or "package-maintenance" not in scenes or ".agents/skills/" not in path:
                findings.append({"severity": "error", "code": "MAINTENANCE_CAPABILITY_BOUNDARY_INVALID", "path": path})
            if any(scene in {"mcm", "modeling", "research", "course-notes", "academic-en"} for scene in scenes):
                findings.append({"severity": "error", "code": "MAINTENANCE_CAPABILITY_LEAKS_TO_WRITING", "path": path})
        if disposition == "routed-reviewer" and str(item.get("provider", "")) not in provider_set:
            findings.append({"severity": "error", "code": "EMBEDDED_PROVIDER_NOT_IN_ROLE_CONTRACTS", "path": path, "provider": item.get("provider")})
        if disposition == "canonical-entry":
            package = package_by_directory.get(owner, {})
            native = ((package.get("adapter") or {}).get("native_entrypoints") or []) if isinstance(package, dict) else []
            owner_prefix = owner.rstrip("/") + "/"
            owner_relative = path[len(owner_prefix):] if path.startswith(owner_prefix) else ""
            if owner_relative not in native:
                findings.append({"severity": "error", "code": "CANONICAL_ENTRY_NOT_BOUND_TO_REGISTRY", "path": path, "owner_relative": owner_relative})

        records.append({
            "path": path,
            "owner": owner,
            "id": str(item.get("id")),
            "disposition": disposition,
            "activation": item.get("activation"),
            "scenes": item.get("scenes"),
            "source_sha256": discovered_item.get("sha256"),
            "source_bytes": discovered_item.get("bytes"),
            "entrypoint_class_verified": entry_class_verified,
        })

    errors = sum(item.get("severity") == "error" for item in findings)
    warnings = sum(item.get("severity") == "warning" for item in findings)
    return {
        "schema": "aigc-folder-utilization-report/v1",
        "status": "pass" if errors == 0 else "fail",
        "root": str(root),
        "top_level_registered": len(registered),
        "top_level_discovered": len(actual),
        "embedded_manifests_discovered": len(discovered),
        "embedded_manifests_declared": len(declared_by_path),
        "embedded_manifest_tree_sha256": current_tree_hash,
        "catalog_sha256": catalog_sha256,
        "ai_paper_entry_classes_verified": sum(
            1 for item in records
            if item.get("owner") == "AI_paper" and item.get("entrypoint_class_verified") is True
        ),
        "dispositions": dict(sorted(dispositions.items())),
        "errors": errors,
        "warnings": warnings,
        "records": records,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    skill_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=skill_root.parent)
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--catalog", type=Path, default=skill_root / "references" / "folder-utilization.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = audit(args.root, args.registry, args.catalog)
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        report = {"schema": "aigc-folder-utilization-report/v1", "status": "fail", "errors": 1, "warnings": 0, "findings": [{"severity": "error", "code": "FOLDER_AUDIT_EXCEPTION", "detail": str(exc)}]}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"AIGC FOLDER UTILIZATION {report['status'].upper()} errors={report['errors']} warnings={report['warnings']} top_level={report.get('top_level_discovered', 0)}/{report.get('top_level_registered', 0)} embedded={report.get('embedded_manifests_discovered', 0)}/{report.get('embedded_manifests_declared', 0)}")
        if report.get("dispositions"):
            print("dispositions=" + ",".join(f"{key}:{value}" for key, value in report["dispositions"].items()))
        for finding in report.get("findings", []):
            detail = ", ".join(f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"})
            print(f"[{finding.get('severity', 'error').upper()}] {finding.get('code')}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
