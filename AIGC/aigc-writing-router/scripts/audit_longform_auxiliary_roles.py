#!/usr/bin/env python3
"""Execute and audit the read-only auxiliary roles for one long-form release.

This gate is intentionally not a writer.  It runs the local ``humanize-main``
adapter's ``audit`` action on the selected candidate and the offline
scene-filtered ``AI_paper`` workbench plan.  Both outputs are hash-locked in a
single report and explicitly cannot select or generate a candidate.

Public interface:
    python audit_longform_auxiliary_roles.py --source SOURCE.tex
        --candidate CANDIDATE.tex --output-dir RUN --registry REGISTRY.json
        --format text|json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file, write_json
from run_aigc_adapter import execute as run_adapter


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def build(source: Path, candidate: Path, output_dir: Path, registry: Path, document_type: str = "mcm") -> dict:
    source = source.resolve()
    candidate = candidate.resolve()
    output_dir = output_dir.resolve()
    registry = registry.resolve()
    for path in (source, candidate, registry):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    ai_check_dir = output_dir / "ai-check"
    ai_check = run_adapter(
        registry, "humanize-main", "audit", source=candidate,
        output_dir=ai_check_dir, document_type=document_type,
    )
    ai_check_report = ai_check_dir / "audit-report.json"
    if ai_check.get("status") != "pass" or not ai_check_report.is_file():
        raise ValueError(f"ai-check adapter failed: {ai_check}")
    ai_check_payload = _load(ai_check_report)
    ai_check_claims = ai_check_payload.get("claims")
    if (
        ai_check_payload.get("schema") != "aigc-adapter-run/v1"
        or ai_check_payload.get("status") != "pass"
        or not isinstance(ai_check_claims, dict)
        or ai_check_claims.get("authorship_or_detector_verdict") is not False
    ):
        raise ValueError("ai-check report has an invalid authorship/detector boundary")

    workbench_dir = output_dir / "AI_paper"
    workbench = run_adapter(
        registry, "AI_paper", "workbench-plan", output_dir=workbench_dir,
        document_type=document_type,
    )
    workbench_plan = workbench_dir / "workbench-plan.json"
    if workbench.get("status") != "pass" or not workbench_plan.is_file():
        raise ValueError(f"AI_paper workbench plan failed: {workbench}")
    plan_payload = _load(workbench_plan)
    embedded = plan_payload.get("embedded_capabilities")
    plan = plan_payload.get("plan")
    selected = plan.get("selected_embedded_capability_ids") if isinstance(plan, dict) else None
    plan_claims = plan_payload.get("claims")
    if (
        plan_payload.get("schema") != "aigc-adapter-run/v1"
        or plan_payload.get("status") != "pass"
        or not isinstance(embedded, dict)
        or embedded.get("status") != "pass"
        or embedded.get("count") != 16
        or not isinstance(selected, list)
        or len(selected) != embedded.get("selected_count")
        or len(set(selected)) != len(selected)
        or not isinstance(plan_claims, dict)
        or plan_claims.get("authorship_or_detector_verdict") is not False
    ):
        raise ValueError("AI_paper workbench plan is incomplete or unbounded")

    report = {
        "schema": "aigc-longform-auxiliary-roles/v1",
        "status": "pass",
        "document_type": document_type,
        "authority_source": {"path": str(source), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
        "ai_check": {
            "provider": "ai-check",
            "adapter_package": "humanize-main",
            "report": {"path": str(ai_check_report), "sha256": sha256_file(ai_check_report)},
            "execution_level": "ADAPTER_DIAGNOSTIC_ONLY",
            "claims": {"authorship_or_detector_verdict": False, "candidate_selection": False},
        },
        "AI_paper_workbench": {
            "provider": "AI_paper",
            "plan": {"path": str(workbench_plan), "sha256": sha256_file(workbench_plan)},
            "execution_level": "WORKBENCH_PLAN_ONLY",
            "claims": {"candidate_generation": False, "candidate_selection": False},
        },
        "claims": {
            "human_style_quality_proven": False,
            "authorship_proven": False,
            "detector_outcome_predicted": False,
        },
    }
    report_path = output_dir / "auxiliary-report.json"
    report["report_path"] = str(report_path)
    write_json(report_path, report)
    return report


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--document-type", default="mcm")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build(args.source, args.candidate, args.output_dir, args.registry, args.document_type)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("LONGFORM AUXILIARY ROLES PASS ai-check=diagnostic AI_paper=workbench-plan")
        print(f"report={report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
