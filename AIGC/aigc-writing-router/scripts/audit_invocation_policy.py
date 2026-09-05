#!/usr/bin/env python3
"""Audit AIGC Skill metadata so component editors cannot stack implicitly.

Public interface:
    python audit_invocation_policy.py [--format text|json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from adapter_core import read_registry


NAME_RE = re.compile(r"^name:\s*([^\r\n]+)$", re.MULTILINE)
PROMPT_RE = re.compile(r'^\s*default_prompt:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
IMPLICIT_RE = re.compile(r"^\s*allow_implicit_invocation:\s*(true|false)\s*$", re.MULTILINE | re.IGNORECASE)


def _skill_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None
    match = NAME_RE.search(text.split("---", 2)[1])
    return match.group(1).strip().strip('"\'') if match else None


def audit(registry_path: Path) -> dict:
    registry_path = registry_path.resolve()
    payload = read_registry(registry_path)
    root = registry_path.parents[2]
    findings: list[dict] = []
    entries: list[dict] = []
    for package in payload.get("packages", []):
        kind = package.get("kind")
        if kind in {"skill", "router"}:
            skill_specs = [{"path": "SKILL.md", "expected": package.get("skill_name")}]
        elif kind == "imported-skill":
            skill_specs = [
                {"path": item.get("path"), "expected": item.get("skill_name")}
                for item in package.get("skill_entrypoints", [])
            ]
        else:
            continue
        for spec in skill_specs:
            skill_path = root / str(package["directory"]) / str(spec["path"])
            actual_name = _skill_name(skill_path) if skill_path.is_file() else None
            agent_path = skill_path.parent / "agents" / "openai.yaml"
            expected_implicit = kind == "router"
            record = {
                "directory": package["directory"],
                "skill": actual_name,
                "skill_path": str(skill_path),
                "agent_path": str(agent_path),
                "expected_implicit": expected_implicit,
            }
            entries.append(record)
            if not skill_path.is_file():
                findings.append({"severity": "error", "code": "SKILL_MISSING", **record})
                continue
            if actual_name != spec["expected"]:
                findings.append({
                    "severity": "error", "code": "SKILL_NAME_MISMATCH",
                    "expected": spec["expected"], **record,
                })
            if not agent_path.is_file():
                findings.append({"severity": "error", "code": "OPENAI_METADATA_MISSING", **record})
                continue
            metadata = agent_path.read_text(encoding="utf-8-sig")
            prompt = PROMPT_RE.search(metadata)
            implicit = IMPLICIT_RE.search(metadata)
            if not prompt or not actual_name or f"${actual_name}" not in prompt.group(1):
                findings.append({"severity": "error", "code": "DEFAULT_PROMPT_CALL_MISMATCH", **record})
            if not implicit:
                findings.append({"severity": "error", "code": "IMPLICIT_POLICY_MISSING", **record})
            else:
                actual_implicit = implicit.group(1).casefold() == "true"
                record["actual_implicit"] = actual_implicit
                if actual_implicit != expected_implicit:
                    findings.append({
                        "severity": "error", "code": "IMPLICIT_POLICY_MISMATCH",
                        "actual_implicit": actual_implicit, **record,
                    })
    implicit_entries = [item for item in entries if item.get("actual_implicit")]
    if len(implicit_entries) != 1 or implicit_entries[0].get("skill") != "aigc-writing-router":
        findings.append({
            "severity": "error", "code": "IMPLICIT_ROUTER_CARDINALITY",
            "skills": [item.get("skill") for item in implicit_entries],
        })
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "aigc-invocation-policy-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "skill_entries": len(entries),
        "implicit_entries": len(implicit_entries),
        "explicit_only_entries": len(entries) - len(implicit_entries),
        "errors": errors,
        "findings": findings,
        "entries": entries,
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.registry)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC INVOCATION POLICY {report['status'].upper()} "
            f"skills={report['skill_entries']} implicit={report['implicit_entries']} "
            f"explicit_only={report['explicit_only_entries']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
