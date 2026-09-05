#!/usr/bin/env python3
"""Build and evaluate an integrated scene-owner benchmark stack.

Public interface:
    python prepare_benchmark_stack.py --document-type modeling|course-notes|research \
        --source SOURCE --candidate CANDIDATE --candidate-verification REPORT \
        --owner-report OWNER-AUDIT.json --output-dir RUN --format text|json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file, write_json
from audit_benchmark_owner_ledger import OWNER_BY_DOCUMENT_TYPE, REPORT_SCHEMA
from prepare_stack_evaluation import build_manifest, build_stage
from route_aigc_tools import select_route
from run_stack_evaluation import evaluate


def build(
    document_type: str,
    source: Path,
    candidate: Path,
    candidate_verification: Path,
    owner_report: Path,
    output_dir: Path,
    registry: Path,
) -> dict:
    source = source.resolve()
    candidate = candidate.resolve()
    candidate_verification = candidate_verification.resolve()
    owner_report = owner_report.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    for path in (source, candidate, candidate_verification, owner_report, registry):
        if not path.is_file():
            raise FileNotFoundError(path)
    owner = json.loads(owner_report.read_text(encoding="utf-8-sig"))
    expected_owner = OWNER_BY_DOCUMENT_TYPE[document_type]
    if (
        owner.get("schema") != REPORT_SCHEMA
        or owner.get("status") != "pass"
        or owner.get("errors") != 0
        or owner.get("provider") != expected_owner
        or owner.get("source", {}).get("sha256") != sha256_file(source)
        or owner.get("candidate", {}).get("sha256") != sha256_file(candidate)
    ):
        raise ValueError("owner audit does not bind a passing scene-owner ledger")
    route = select_route(
        document_type, "rewrite", "tex", "local",
        requested_editor="humanize-academic-chinese",
    )
    if route.get("status") != "pass":
        raise ValueError(f"writing route is blocked: {route.get('findings', [])}")
    required = {
        str(stage.get("provider")) for stage in route.get("stages", [])
        if isinstance(stage, dict) and stage.get("provider") != "humanize-academic-chinese"
    }
    if required != {"deai-academic-writing", expected_owner}:
        raise ValueError(f"unexpected benchmark role chain: {sorted(required)}")

    output_dir.mkdir(parents=True)
    route_path = output_dir / "route-plan.json"
    write_json(route_path, route)
    academic_stage = output_dir / "stage-academic.json"
    owner_stage = output_dir / "stage-owner.json"
    build_stage(
        academic_stage, "deai-academic-writing", source, candidate, [route_path],
    )
    build_stage(owner_stage, expected_owner, source, candidate, [owner_report])
    manifest_path = output_dir / "stack-manifest.json"
    build_manifest(
        manifest_path, document_type, "rewrite", "tex", "local",
        source, candidate, "H1", "source", "humanize-academic-chinese",
        candidate_verification, [academic_stage, owner_stage], None,
        "pending", "", "", ["mechanical_fidelity", "role_chain_complete"],
    )
    report = evaluate(manifest_path, registry)
    report_path = output_dir / "stack-report.json"
    write_json(report_path, report)
    if report.get("status") != "MECHANICAL_PASS_HUMAN_PENDING" or report.get("errors") != 0:
        raise ValueError(f"integrated benchmark stack failed: {report.get('findings', [])}")
    return {
        "schema": "aigc-benchmark-stack-build/v1",
        "status": "pass",
        "document_type": document_type,
        "source_sha256": sha256_file(source),
        "candidate_sha256": sha256_file(candidate),
        "required_stage_providers": sorted(required),
        "manifest": {"path": str(manifest_path), "sha256": sha256_file(manifest_path)},
        "report": {"path": str(report_path), "sha256": sha256_file(report_path)},
        "human_quality_status": "PENDING_EXTERNAL_REVIEW",
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-type", choices=sorted(OWNER_BY_DOCUMENT_TYPE), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-verification", type=Path, required=True)
    parser.add_argument("--owner-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--registry", type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build(
        args.document_type, args.source, args.candidate,
        args.candidate_verification, args.owner_report,
        args.output_dir, args.registry.resolve(),
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"BENCHMARK STACK PASS document_type={report['document_type']} "
            f"providers={','.join(report['required_stage_providers'])} "
            f"report={report['report']['path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
