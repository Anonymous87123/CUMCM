#!/usr/bin/env python3
"""Validate and register a frozen external candidate matrix for one holdout suite.

This command never authors or edits candidates.  The caller must provide nine
independent ``CASE-t1.tex`` ... ``CASE-t3.tex`` files created from the frozen
holdout sources after the writing rules were fixed.

Public interface:
    python run_matrix_holdout_chain.py SUITE.json --candidate-dir CANDIDATES \
        --output-dir RUN --document-type modeling|course-notes|research
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import write_json
from audit_auxiliary_roles import audit as audit_auxiliary
from run_matrix_dev_chain import SCENE_BY_TYPE, build_candidate_chain


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--document-type", choices=sorted(SCENE_BY_TYPE), required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument(
        "--registry",
        type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build_candidate_chain(
        args.suite.resolve(),
        args.output_dir.resolve(),
        args.document_type,
        args.registry.resolve(),
        args.seed,
        candidate_dir=args.candidate_dir.resolve(),
        allowed_splits=("holdout",),
    )
    report_path = args.output_dir.resolve() / "chain-report.json"
    write_json(report_path, report)
    auxiliary_audit_path = args.output_dir.resolve() / "auxiliary-audit.json"
    auxiliary_audit = audit_auxiliary(report_path)
    write_json(auxiliary_audit_path, auxiliary_audit)
    if auxiliary_audit.get("status") != "pass":
        raise ValueError(f"auxiliary role audit failed: {auxiliary_audit.get('findings', [])}")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"MATRIX HOLDOUT CHAIN {report['status'].upper()} "
            f"type={report['document_type']} candidates={report['candidates']} "
            f"state={report['manifest_state']} human_quality=PENDING_EXTERNAL_REVIEW"
        )
        print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
