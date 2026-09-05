#!/usr/bin/env python3
"""Audit a reproducibility manifest for a CUMCM manuscript run.

Public interface:
    python audit_repro_manifest.py <manifest.json> --format text|json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime
from pathlib import Path


DEFAULT_REQUIRED_ROLES = ("analysis_script", "result", "figure", "data_config")
RUN_FIELDS = ("command", "python_version", "random_seed", "generated_at", "data_config")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def audit(manifest_path: Path) -> dict:
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    base = manifest_path.parent
    findings: list[dict] = []
    run = payload.get("run")
    if not isinstance(run, dict):
        run = {}
        findings.append({"severity": "error", "code": "RUN_METADATA_MISSING"})
    for field in RUN_FIELDS:
        if field not in run or run[field] in (None, ""):
            findings.append({"severity": "error", "code": "RUN_FIELD_MISSING", "field": field})
    if "generated_at" in run and not valid_timestamp(run.get("generated_at")):
        findings.append({"severity": "error", "code": "RUN_TIMESTAMP_INVALID", "value": run.get("generated_at")})

    packages = run.get("packages")
    if not isinstance(packages, dict):
        findings.append({"severity": "error", "code": "PACKAGE_VERSIONS_MISSING"})
        packages = {}
    elif not packages:
        findings.append({"severity": "warning", "code": "PACKAGE_VERSIONS_EMPTY"})

    if run.get("verify_runtime"):
        expected_python = str(run.get("python_version", ""))
        actual_python = platform.python_version()
        if expected_python and actual_python != expected_python:
            findings.append({
                "severity": "error",
                "code": "PYTHON_VERSION_MISMATCH",
                "expected": expected_python,
                "actual": actual_python,
            })
        for package, expected in packages.items():
            try:
                actual = importlib.metadata.version(str(package))
            except importlib.metadata.PackageNotFoundError:
                findings.append({"severity": "error", "code": "PACKAGE_NOT_INSTALLED", "package": package})
                continue
            if str(expected) != actual:
                findings.append({
                    "severity": "error",
                    "code": "PACKAGE_VERSION_MISMATCH",
                    "package": package,
                    "expected": str(expected),
                    "actual": actual,
                })

    data_config_path: Path | None = None
    if run.get("data_config"):
        data_config_path = Path(str(run["data_config"]))
        if not data_config_path.is_absolute():
            data_config_path = (base / data_config_path).resolve()
        if not data_config_path.is_file():
            findings.append({
                "severity": "error",
                "code": "RUN_DATA_CONFIG_MISSING",
                "path": str(run["data_config"]),
            })

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        artifacts = []
        findings.append({"severity": "error", "code": "ARTIFACTS_MISSING"})
    roles: set[str] = set()
    role_paths: dict[str, set[Path]] = {}
    seen_paths: set[str] = set()
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            findings.append({"severity": "error", "code": "ARTIFACT_INVALID", "index": index})
            continue
        role = str(item.get("role", "")).strip()
        path_literal = str(item.get("path", "")).strip()
        expected = str(item.get("sha256", "")).lower().strip()
        if not role or not path_literal or not expected:
            findings.append({
                "severity": "error",
                "code": "ARTIFACT_FIELD_MISSING",
                "index": index,
                "role": role,
                "path": path_literal,
            })
            continue
        roles.add(role)
        path = Path(path_literal)
        if not path.is_absolute():
            path = (base / path).resolve()
        role_paths.setdefault(role, set()).add(path)
        key = str(path).lower()
        if key in seen_paths:
            findings.append({"severity": "warning", "code": "ARTIFACT_DUPLICATE", "path": path_literal})
        seen_paths.add(key)
        if not path.is_file():
            findings.append({"severity": "error", "code": "ARTIFACT_MISSING", "path": path_literal, "role": role})
            continue
        actual = sha256(path)
        if actual != expected:
            findings.append({
                "severity": "error",
                "code": "ARTIFACT_HASH_MISMATCH",
                "path": path_literal,
                "role": role,
                "expected": expected,
                "actual": actual,
            })

    if data_config_path and data_config_path not in role_paths.get("data_config", set()):
        findings.append({
            "severity": "error",
            "code": "RUN_DATA_CONFIG_UNTRACKED",
            "path": str(run.get("data_config")),
        })

    required_roles = payload.get("required_roles", DEFAULT_REQUIRED_ROLES)
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    for role in required_roles:
        if str(role) not in roles:
            findings.append({"severity": "error", "code": "ARTIFACT_ROLE_MISSING", "role": str(role)})

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "manifest": str(manifest_path.resolve()),
        "artifacts": len(artifacts),
        "roles": sorted(roles),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.manifest)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"REPRO MANIFEST {report['status'].upper()} errors={report['errors']} "
            f"warnings={report['warnings']} artifacts={report['artifacts']}"
        )
        print(f"manifest={report['manifest']}")
        for item in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key not in {"severity", "code"})
            print(f"[{item['severity'].upper()}] {item['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
