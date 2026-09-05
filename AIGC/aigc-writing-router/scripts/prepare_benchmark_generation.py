#!/usr/bin/env python3
"""Create a source-bound generation envelope for one style benchmark trial."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file, write_json
from run_style_benchmark import _writing_rule_snapshot


SCHEMA = "aigc-benchmark-generation/v1"
STACK_REPORT_SCHEMA = "aigc-stack-evaluation-report/v1"
STACK_MANIFEST_SCHEMA = "aigc-stack-evaluation/v1"


def _resolve_locked(base: Path, record: object, label: str) -> Path:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        raise ValueError(f"{label} lock is missing or invalid")
    path = Path(str(record["path"]))
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or sha256_file(path) != str(record["sha256"]):
        raise ValueError(f"{label} lock drifted")
    return path


def _validate_stack_report(
    stack_report: Path,
    provider: str,
    source_sha256: str,
    candidate_sha256: str,
) -> tuple[dict, Path]:
    report = json.loads(stack_report.read_text(encoding="utf-8-sig"))
    if not isinstance(report, dict) or report.get("schema") != STACK_REPORT_SCHEMA:
        raise ValueError("stack evaluation report schema mismatch")
    if (
        report.get("status") not in {"MECHANICAL_PASS_HUMAN_PENDING", "HUMAN_EVALUATED_PASS"}
        or report.get("errors") != 0
        or report.get("candidate", {}).get("provider") != provider
        or report.get("required_stage_providers") != report.get("covered_stage_providers")
    ):
        raise ValueError("stack evaluation report does not prove a complete mechanical role chain")
    manifest_path = _resolve_locked(stack_report.parent, report.get("manifest"), "stack manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("schema") != STACK_MANIFEST_SCHEMA:
        raise ValueError("stack evaluation manifest schema mismatch")
    source_path = _resolve_locked(manifest_path.parent, manifest.get("source"), "stack source")
    candidate_path = _resolve_locked(
        manifest_path.parent, manifest.get("candidate"), "stack candidate",
    )
    if sha256_file(source_path) != source_sha256 or sha256_file(candidate_path) != candidate_sha256:
        raise ValueError("stack evaluation source or candidate does not match the generation trial")
    if manifest.get("candidate", {}).get("provider") != provider:
        raise ValueError("stack evaluation candidate provider mismatch")
    return report, manifest_path


def build(
    provider: str,
    source: Path,
    candidate: Path,
    native_report: Path,
    authoring_actor: str,
    authoring_decision: str,
    run_id: str | None = None,
    stack_report: Path | None = None,
) -> dict:
    source = source.resolve()
    candidate = candidate.resolve()
    native_report = native_report.resolve()
    for path in (source, candidate, native_report):
        if not path.is_file():
            raise FileNotFoundError(path)
    native = json.loads(native_report.read_text(encoding="utf-8-sig"))
    if not isinstance(native, dict):
        raise ValueError("native report root must be an object")
    successful = (
        native.get("status") == "pass"
        or native.get("candidate_assembly_status") == "PASS"
        or native.get("mechanical_validation_status") == "PASS"
    )
    if not successful:
        raise ValueError("native report does not declare a mechanically successful run")
    native_run_id = str(native.get("run_id", "")).strip()
    effective_run_id = str(run_id or native_run_id).strip()
    if not effective_run_id:
        raise ValueError("run_id is missing from both the native report and command")
    if authoring_decision not in {"NO_CHANGE", "REWRITE"}:
        raise ValueError("authoring_decision must be NO_CHANGE or REWRITE")
    payload = {
        "schema": SCHEMA,
        "provider": provider,
        "status": "pass",
        "authoring_actor": authoring_actor,
        "authoring_decision": authoring_decision,
        "source": {"path": str(source), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
        "execution": {
            "mode": "model_authored_native_validated" if authoring_actor == "model" else "native_executed",
            "native_action": "validate_and_emit_frozen_candidate",
            "run_id": effective_run_id,
        },
        "native_report": {
            "path": str(native_report),
            "sha256": sha256_file(native_report),
        },
        "writing_rule_snapshot": _writing_rule_snapshot(),
        "claims": {
            "human_authorship_proven": False,
            "native_generation_proven": False,
            "validation_executed": True,
            "external_style_clearance": False,
            "mechanical_validation_only": True,
        },
    }
    if stack_report is not None:
        stack_report = stack_report.resolve()
        if not stack_report.is_file():
            raise FileNotFoundError(stack_report)
        stack, stack_manifest = _validate_stack_report(
            stack_report, provider, payload["source"]["sha256"], payload["candidate"]["sha256"],
        )
        payload["stack_evaluation"] = {
            "report": {"path": str(stack_report), "sha256": sha256_file(stack_report)},
            "manifest": {"path": str(stack_manifest), "sha256": sha256_file(stack_manifest)},
            "document_type": stack.get("scene", {}).get("document_type"),
            "required_stage_providers": stack.get("required_stage_providers", []),
        }
        payload["execution"]["role_chain_bound"] = True
    else:
        payload["execution"]["role_chain_bound"] = False
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--authoring-actor", choices=("model", "human", "external_tool"), required=True)
    parser.add_argument("--authoring-decision", choices=("NO_CHANGE", "REWRITE"), required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--stack-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build(
        args.provider, args.source, args.candidate, args.native_report,
        args.authoring_actor, args.authoring_decision, args.run_id, args.stack_report,
    )
    write_json(args.output.resolve(), report)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"BENCHMARK GENERATION PASS provider={report['provider']} "
            f"run_id={report['execution']['run_id']} actor={report['authoring_actor']} "
            f"decision={report['authoring_decision']} "
            f"output={args.output.resolve()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
