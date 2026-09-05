#!/usr/bin/env python3
"""Audit a source-bound section authoring brief for a CUMCM manuscript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_section_authoring_brief import SCHEMA, build_brief, sha256_file


def _finding(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _contains_style_text(value: object) -> bool:
    if isinstance(value, dict):
        if any(key in value for key in ("text", "previous_context", "next_context")):
            return True
        return any(_contains_style_text(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_style_text(item) for item in value)
    return False


def audit(
    main_tex: Path,
    brief_path: Path,
    problem_type: str,
    style_plan: Path,
    workbench: Path,
    preflight: Path,
) -> dict:
    findings: list[dict] = []
    brief_path = brief_path.resolve()
    if not brief_path.is_file():
        _finding(findings, "SECTION_AUTHORING_BRIEF_MISSING", path=str(brief_path))
        return _report(findings, 0, brief_path)
    try:
        actual = json.loads(brief_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, "SECTION_AUTHORING_BRIEF_INVALID_JSON", detail=str(exc))
        return _report(findings, 0, brief_path)
    if not isinstance(actual, dict):
        _finding(findings, "SECTION_AUTHORING_BRIEF_NOT_OBJECT")
        return _report(findings, 0, brief_path)
    expected = build_brief(main_tex, problem_type, style_plan, workbench, preflight)
    if actual.get("schema") != SCHEMA:
        _finding(findings, "SECTION_AUTHORING_BRIEF_SCHEMA_MISMATCH", actual=actual.get("schema"))
    if expected.get("status") != "pass":
        _finding(
            findings,
            "SECTION_AUTHORING_BRIEF_DEPENDENCY_FAILED",
            dependency_findings=expected.get("findings", []),
        )
    if actual.get("status") != "pass" or actual.get("errors") != 0:
        _finding(findings, "SECTION_AUTHORING_BRIEF_NOT_PASSING")
    for key in ("problem_type", "inputs", "dependency_audits", "policy"):
        if actual.get(key) != expected.get(key):
            _finding(findings, "SECTION_AUTHORING_BRIEF_METADATA_DRIFT", field=key)
    actual_source = actual.get("source") if isinstance(actual.get("source"), dict) else {}
    expected_source = expected.get("source") if isinstance(expected.get("source"), dict) else {}
    if any(actual_source.get(key) != expected_source.get(key) for key in ("sha256", "tex_tree_sha256")):
        _finding(findings, "SECTION_AUTHORING_BRIEF_METADATA_DRIFT", field="source-hashes")
    if actual.get("sections") != expected.get("sections"):
        _finding(
            findings,
            "SECTION_AUTHORING_BRIEF_SECTION_DRIFT",
            expected_count=len(expected.get("sections", [])),
            actual_count=len(actual.get("sections", [])) if isinstance(actual.get("sections"), list) else 0,
        )
    if _contains_style_text(actual.get("sections")):
        _finding(findings, "SECTION_AUTHORING_BRIEF_COPIED_STYLE_TEXT")
    report = _report(
        findings,
        len(actual.get("sections", [])) if isinstance(actual.get("sections"), list) else 0,
        brief_path,
    )
    report["manuscript"] = {
        "path": str(main_tex.resolve()),
        "sha256": expected_source.get("sha256"),
        "tex_tree_sha256": expected_source.get("tex_tree_sha256"),
    }
    report["inputs"] = {
        "style_plan": expected.get("inputs", {}).get("style_plan"),
        "workbench": expected.get("inputs", {}).get("workbench"),
        "preflight": expected.get("inputs", {}).get("preflight"),
        "brief": report["brief"],
    }
    return report


def _report(findings: list[dict], sections: int, path: Path) -> dict:
    return {
        "schema": "mcm-section-authoring-brief-audit/v1",
        "status": "pass" if not findings else "fail",
        "brief": {"path": str(path), "sha256": sha256_file(path) if path.is_file() else None},
        "sections": sections,
        "errors": len(findings),
        "findings": findings,
        "interpretation": (
            "Passing confirms that every current TeX section is bound to the current problem's approved evidence route "
            "and to style-only corpus references without embedding corpus prose. It does not generate prose or prove "
            "mathematical correctness, reviewer identity, authorship, or naturalness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--problem-type", choices=("A", "B", "C"), required=True)
    parser.add_argument("--style-plan", type=Path, required=True)
    parser.add_argument("--workbench", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.brief, args.problem_type, args.style_plan, args.workbench, args.preflight)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SECTION AUTHORING BRIEF AUDIT {report['status'].upper()} sections={report['sections']} errors={report['errors']}")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
