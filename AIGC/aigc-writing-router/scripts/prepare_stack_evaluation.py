#!/usr/bin/env python3
"""Create hash-locked stage evidence and stack-evaluation manifests.

Public interfaces:
    python prepare_stack_evaluation.py stage --provider NAME --source SOURCE
        --candidate CANDIDATE --artifact REPORT [--artifact REPORT ...]
        --output STAGE.json
    python prepare_stack_evaluation.py manifest --document-type TYPE
        --document-format FORMAT --source SOURCE --candidate CANDIDATE
        --candidate-id ID --provider NAME --candidate-verification REPORT
        --stage-evidence STAGE.json [--stage-evidence STAGE.json ...]
        [--blind-score REPORT] [--decision pending|accepted|source-retained]
        [--reviewer NAME] [--reason TEXT] --output EVALUATION.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from adapter_core import sha256_file, write_json
from route_aigc_tools import DOCUMENT_FORMATS, DOCUMENT_TYPES, INTENTS
from run_stack_evaluation import evaluate


def _portable_path(path: Path, base: Path) -> str:
    path = path.resolve()
    try:
        return os.path.relpath(path, base.resolve())
    except ValueError:
        return str(path)


def locked(path: Path, base: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": _portable_path(path, base), "sha256": sha256_file(path)}


def build_stage(
    output: Path,
    provider: str,
    source: Path,
    candidate: Path | None,
    artifacts: list[Path],
) -> dict:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if candidate is not None and not candidate.resolve().is_file():
        raise FileNotFoundError(candidate)
    if not artifacts:
        raise ValueError("at least one --artifact is required")
    payload = {
        "schema": "aigc-stage-evidence/v1",
        "provider": provider,
        "status": "pass",
        "source_sha256": sha256_file(source),
        "artifacts": [locked(path, output.parent) for path in artifacts],
    }
    if candidate is not None:
        payload["output_sha256"] = sha256_file(candidate.resolve())
    write_json(output, payload)
    return payload


def build_manifest(
    output: Path,
    document_type: str,
    intent: str,
    document_format: str,
    scope: str,
    source: Path,
    candidate: Path,
    candidate_id: str,
    baseline_id: str,
    provider: str,
    candidate_verification: Path,
    stage_evidence: list[Path],
    blind_score: Path | None,
    decision: str,
    reviewer: str,
    reason: str,
    claims: list[str],
) -> dict:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "aigc-stack-evaluation/v1",
        "scene": {
            "document_type": document_type,
            "intent": intent,
            "document_format": document_format,
            "scope": scope,
        },
        "source": locked(source, output.parent),
        "baseline_id": baseline_id,
        "candidate": {
            **locked(candidate, output.parent),
            "id": candidate_id,
            "provider": provider,
        },
        "stage_evidence": [locked(path, output.parent) for path in stage_evidence],
        "candidate_verification": locked(candidate_verification, output.parent),
        "human_decision": {"status": decision},
        "claims": claims,
    }
    if decision == "accepted":
        payload["human_decision"].update({"reviewer": reviewer, "reason": reason})
    if blind_score is not None:
        payload["blind_score"] = locked(blind_score, output.parent)
    write_json(output, payload)
    return payload


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    stage_parser = sub.add_parser("stage")
    stage_parser.add_argument("--provider", required=True)
    stage_parser.add_argument("--source", type=Path, required=True)
    stage_parser.add_argument("--candidate", type=Path)
    stage_parser.add_argument("--artifact", type=Path, action="append", required=True)
    stage_parser.add_argument("--output", type=Path, required=True)

    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("--document-type", choices=DOCUMENT_TYPES, required=True)
    manifest_parser.add_argument("--intent", choices=INTENTS, default="rewrite")
    manifest_parser.add_argument("--document-format", choices=DOCUMENT_FORMATS, required=True)
    manifest_parser.add_argument("--scope", choices=("document", "local"), default="document")
    manifest_parser.add_argument("--source", type=Path, required=True)
    manifest_parser.add_argument("--candidate", type=Path, required=True)
    manifest_parser.add_argument("--candidate-id", required=True)
    manifest_parser.add_argument("--baseline-id", default="source")
    manifest_parser.add_argument("--provider", required=True)
    manifest_parser.add_argument("--candidate-verification", type=Path, required=True)
    manifest_parser.add_argument("--stage-evidence", type=Path, action="append", default=[])
    manifest_parser.add_argument("--blind-score", type=Path)
    manifest_parser.add_argument(
        "--decision", choices=("pending", "accepted", "source-retained"), default="pending",
    )
    manifest_parser.add_argument("--reviewer", default="")
    manifest_parser.add_argument("--reason", default="")
    manifest_parser.add_argument(
        "--claim", action="append",
        default=["mechanical_fidelity", "role_chain_complete"],
    )
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument("--format", choices=("text", "json"), default="text")

    args = parser.parse_args()
    if args.command == "stage":
        payload = build_stage(
            args.output, args.provider, args.source, args.candidate, args.artifact,
        )
        print(
            f"AIGC STAGE EVIDENCE READY provider={payload['provider']} "
            f"artifacts={len(payload['artifacts'])} output={args.output.resolve()}"
        )
        return 0

    if args.decision == "accepted" and (not args.blind_score or not args.reviewer or not args.reason):
        parser.error("accepted requires --blind-score, --reviewer, and --reason")
    build_manifest(
        args.output, args.document_type, args.intent, args.document_format, args.scope,
        args.source, args.candidate, args.candidate_id, args.baseline_id, args.provider,
        args.candidate_verification, args.stage_evidence, args.blind_score,
        args.decision, args.reviewer, args.reason, args.claim,
    )
    report = evaluate(args.output, registry)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC STACK MANIFEST {report['status']} errors={report['errors']} "
            f"warnings={report['warnings']} output={args.output.resolve()}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
