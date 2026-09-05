#!/usr/bin/env python3
"""Turn an academic candidate audit into a source-bound recovery packet.

This tool never rewrites prose.  A protected-content failure routes back to the
frozen source and suppresses lexical repair tasks.  Only a contract-safe
candidate receives position-bound local repair items.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from audit_academic_candidate import REPORT_SCHEMA, build_recovery, sha256_file


RECOVERY_SCHEMA = "aigc-academic-recovery-plan/v1"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = Path(__file__).resolve().parents[3]
HUMANIZE_ROOT = SKILLS_ROOT / "AIGC" / "humanize-academic-chinese"


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != REPORT_SCHEMA:
        raise ValueError("academic candidate audit schema mismatch")
    return payload


def _verify_artifact(record: dict[str, Any], role: str) -> Path:
    path = Path(str(record.get("path", ""))).resolve()
    expected = str(record.get("sha256", ""))
    if not path.is_file():
        raise FileNotFoundError(f"{role} artifact is missing")
    if not expected or sha256_file(path) != expected:
        raise ValueError(f"{role} artifact drifted after audit")
    return path


def _safe_candidate_file(candidate_main: Path, relative_path: str) -> Path:
    root = candidate_main.parent.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("finding path escapes the candidate tree") from exc
    if not path.is_file():
        raise FileNotFoundError("finding file is missing")
    return path


def _line_context(path: Path, line: int, radius: int) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if line < 1 or line > len(lines):
        raise ValueError("finding line is outside the candidate file")
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return {
        "start_line": start,
        "end_line": end,
        "lines": [
            {"line": index, "text": lines[index - 1]}
            for index in range(start, end + 1)
        ],
    }


def _gate(report: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(
        (item for item in report.get("gates", []) if item.get("id") == gate_id),
        {},
    )


def build_plan(report_path: Path, scene: str = "MODELING", context_lines: int = 2) -> dict[str, Any]:
    report_path = report_path.resolve()
    report = _load_report(report_path)
    source = _verify_artifact(report.get("source", {}), "source")
    candidate = _verify_artifact(report.get("candidate", {}), "candidate")
    recovery = report.get("recovery")
    if not isinstance(recovery, dict):
        recovery = build_recovery(list(report.get("gates", [])))

    repair_items: list[dict[str, Any]] = []
    if recovery.get("lexical_findings_actionable_now"):
        lexical = _gate(report, "humanize-lexical")
        for index, item in enumerate(lexical.get("unresolved", []), start=1):
            if not isinstance(item, dict):
                continue
            relative_path = str(item.get("relative_path", ""))
            line = int(item.get("line", 0))
            finding_file = _safe_candidate_file(candidate, relative_path)
            repair_items.append({
                "repair_id": f"LEX-{index:04d}",
                "kind": "POSITION_BOUND_PROSE_REPAIR",
                "signal_id": item.get("signal_id"),
                "relative_path": relative_path,
                "line": line,
                "column": item.get("column"),
                "matched": item.get("matched"),
                "action": item.get("action"),
                "rationale": item.get("rationale"),
                "context": _line_context(finding_file, line, context_lines),
                "required_record": {
                    "source_fact_or_derivation": "FILL_WITH_LOCAL_EVIDENCE",
                    "replacement_or_keep_decision": "FILL",
                    "reviewer_kind": "HUMAN_REQUIRED_FOR_KEEP",
                    "semantic_check": "PENDING",
                },
            })

    if recovery.get("current_candidate_repair_allowed"):
        contract = _gate(report, "protected-rewrite-contract")
        for item in contract.get("unresolved_warnings", []):
            if not isinstance(item, dict):
                continue
            repair_items.append({
                "repair_id": f"SEM-{len(repair_items) + 1:04d}",
                "kind": "SEMANTIC_WARNING_REVIEW",
                "code": item.get("code"),
                "finding_sha256": item.get("finding_sha256"),
                "before_line_range": item.get("before_line_range"),
                "after_line_range": item.get("after_line_range"),
                "before_examples": item.get("before_examples", []),
                "candidate_examples": item.get("after_examples", []),
                "required_record": {
                    "source_fact_or_derivation": "FILL_WITH_LOCAL_EVIDENCE",
                    "decision": "ACCEPT_OR_REPAIR_OR_REBASE",
                    "reason": "FILL",
                    "reviewer": "FILL",
                    "reviewer_kind": "HUMAN_REQUIRED",
                    "semantic_check": "PENDING",
                },
            })

        for gate_id, kind in (
            ("section-voice", "VOICE_STRUCTURE_REVIEW"),
            ("paragraph-rhythm", "RHYTHM_STRUCTURE_REVIEW"),
        ):
            gate = _gate(report, gate_id)
            for item in gate.get("findings", []):
                if not isinstance(item, dict):
                    continue
                relative_path = str(item.get("relative_path", ""))
                line = int(item.get("actual_line", 0) or 0)
                context = None
                if relative_path and line > 0:
                    finding_file = _safe_candidate_file(candidate, relative_path)
                    context = _line_context(finding_file, line, context_lines)
                repair_items.append({
                    "repair_id": f"STR-{len(repair_items) + 1:04d}",
                    "kind": kind,
                    "code": item.get("code"),
                    "relative_path": relative_path or None,
                    "line": line or None,
                    "section": item.get("section"),
                    "evidence": item.get("evidence"),
                    "suggestion": item.get("suggestion"),
                    "context": context,
                    "required_record": {
                        "source_fact_or_derivation": "FILL_WITH_LOCAL_EVIDENCE",
                        "structural_decision": "KEEP_OR_REWRITE",
                        "replacement_or_keep_reason": "FILL",
                        "reviewer_kind": "HUMAN_REQUIRED_FOR_KEEP",
                        "semantic_check": "PENDING",
                    },
                })

    candidate_issue_count = (
        int(_gate(report, "humanize-lexical").get("unresolved_findings", 0) or 0)
        + len(_gate(report, "protected-rewrite-contract").get("unresolved_warnings", []))
        + len(_gate(report, "section-voice").get("findings", []))
        + len(_gate(report, "paragraph-rhythm").get("findings", []))
    )

    route = str(recovery.get("route", "UNRESOLVED"))
    plan: dict[str, Any] = {
        "schema": RECOVERY_SCHEMA,
        "audit": {"path": str(report_path), "sha256": sha256_file(report_path)},
        "source": {"path": str(source), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
        "scene": scene,
        "route": route,
        "current_candidate_repair_allowed": bool(recovery.get("current_candidate_repair_allowed")),
        "source_rebase_required": bool(recovery.get("source_rebase_required")),
        "blocking_gate_ids": list(recovery.get("blocking_gate_ids", [])),
        "reason_codes": list(recovery.get("reason_codes", [])),
        "repair_items": repair_items,
        "repair_item_counts": {
            kind: sum(item.get("kind") == kind for item in repair_items)
            for kind in (
                "POSITION_BOUND_PROSE_REPAIR", "SEMANTIC_WARNING_REVIEW",
                "VOICE_STRUCTURE_REVIEW", "RHYTHM_STRUCTURE_REVIEW",
            )
        },
        "repair_items_suppressed": (
            candidate_issue_count if not recovery.get("current_candidate_repair_allowed") else 0
        ),
        "completion_claim_allowed": False,
        "claims": {
            "prose_rewritten": False,
            "candidate_release_ready": False,
            "authorship_or_detector_verdict": False,
        },
    }
    if route == "REBASE_FROM_FROZEN_SOURCE":
        plan["native_rebase"] = {
            "input_must_be": "source",
            "forbidden_input": "candidate",
            "prepare_command": [
                str(Path(sys.executable).resolve()),
                str(HUMANIZE_ROOT / "scripts" / "prepare_humanize_long_document.py"),
                str(source), "--output", "<RECOVERY_ROOT>/humanize-run",
                "--scene", scene, "--intensity", "BALANCED",
            ],
            "scaffold_command": [
                str(Path(sys.executable).resolve()),
                str(HUMANIZE_ROOT / "scripts" / "scaffold_humanize_rewrites.py"),
                "--run-dir", "<RECOVERY_ROOT>/humanize-run",
                "--output", "<RECOVERY_ROOT>/rewrites",
                "--decision", "REWRITE", "--format", "text",
            ],
            "authoring_rule": (
                "Complete each frozen unit from the source. Restore protected spans byte-for-byte; "
                "do not copy changed formulas, numbers, units, citations, or TeX from the rejected candidate."
            ),
        }
    elif repair_items:
        plan["local_repair_rule"] = (
            "Edit only the listed spans, bind every change to a local fact or derivation, "
            "then rerun the same protected validation. Do not invoke another Humanizer."
        )
    return plan


def _run_json_command(command: list[str], accepted: set[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    completed = subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=300, check=False,
    )
    execution = {
        "command": command,
        "returncode": completed.returncode,
        "stderr": completed.stderr[-2000:],
    }
    if completed.returncode not in accepted:
        raise RuntimeError(
            f"recovery command exited {completed.returncode}: {completed.stderr[-600:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("recovery command returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("recovery command JSON root must be an object")
    return payload, execution


def materialize_rebase(plan: dict[str, Any], materialize_root: Path) -> dict[str, Any]:
    if plan.get("route") != "REBASE_FROM_FROZEN_SOURCE":
        raise ValueError("materialization is only valid for a source rebase")
    materialize_root = materialize_root.resolve()
    if materialize_root.exists():
        raise FileExistsError("materialize-root must not already exist")
    materialize_root.mkdir(parents=True)
    run_dir = materialize_root / "humanize-run"
    rewrites_dir = materialize_root / "rewrites"
    source = Path(str(plan["source"]["path"])).resolve()
    scene = str(plan["scene"])

    prepare_command = [
        str(Path(sys.executable).resolve()),
        str(HUMANIZE_ROOT / "scripts" / "prepare_humanize_long_document.py"),
        str(source), "--output", str(run_dir),
        "--scene", scene, "--intensity", "BALANCED",
    ]
    prepare, prepare_execution = _run_json_command(prepare_command, {0, 2})
    ledger_path = run_dir / "coverage_ledger.csv"
    integrity_path = run_dir / "prepare_integrity.json"
    if not ledger_path.is_file() or not integrity_path.is_file():
        raise RuntimeError("long-document prepare did not publish its required artifacts")
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = {
        status: sum(row.get("status") == status for row in rows)
        for status in {str(row.get("status", "")) for row in rows}
    }
    unresolved = counts.get("UNRESOLVED", 0)
    pending = counts.get("PENDING", 0)
    materialization: dict[str, Any] = {
        "status": "PREPARE_REVIEW" if unresolved else "AUTHORING_REQUIRED",
        "root": str(materialize_root),
        "run_dir": str(run_dir),
        "prepare": prepare_execution,
        "prepare_status": prepare.get("status"),
        "unit_statuses": dict(sorted(counts.items())),
        "prepare_integrity": {
            "path": str(integrity_path), "sha256": sha256_file(integrity_path),
        },
        "scaffold": None,
        "claims": {
            "prose_rewritten": False,
            "candidate_assembled": False,
            "candidate_release_ready": False,
        },
    }
    if not unresolved and pending:
        scaffold_command = [
            str(Path(sys.executable).resolve()),
            str(HUMANIZE_ROOT / "scripts" / "scaffold_humanize_rewrites.py"),
            "--run-dir", str(run_dir), "--output", str(rewrites_dir),
            "--decision", "REWRITE", "--format", "json",
        ]
        scaffold, scaffold_execution = _run_json_command(scaffold_command, {0})
        metadata_path = rewrites_dir / "scaffold_metadata.json"
        marker_path = rewrites_dir / ".humanize-scaffold-committed"
        if not metadata_path.is_file() or not marker_path.is_file():
            raise RuntimeError("rewrite scaffold did not publish committed metadata")
        materialization["scaffold"] = {
            "execution": scaffold_execution,
            "status": scaffold.get("status"),
            "templates": pending,
            "metadata": {"path": str(metadata_path), "sha256": sha256_file(metadata_path)},
            "commit_marker": {"path": str(marker_path), "sha256": sha256_file(marker_path)},
        }
    execution_path = materialize_root / "recovery-execution.json"
    materialization["execution_receipt"] = str(execution_path)
    result = dict(plan)
    result["materialization"] = materialization
    execution_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--scene", choices=("GENERAL", "COURSE", "MODELING", "RESEARCH"), default="MODELING")
    parser.add_argument("--context-lines", type=int, default=2)
    parser.add_argument("--materialize-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        if args.context_lines < 0 or args.context_lines > 8:
            raise ValueError("context-lines must be between 0 and 8")
        plan = build_plan(args.audit, args.scene, args.context_lines)
        if args.materialize_root:
            plan = materialize_rebase(plan, args.materialize_root)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        rendered = (
            json.dumps({"schema": RECOVERY_SCHEMA, "status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json" else f"ACADEMIC RECOVERY FAIL: {exc}\n"
        )
        if args.output:
            args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
            args.output.resolve().write_text(rendered, encoding="utf-8", newline="")
        else:
            sys.stdout.write(rendered)
        return 1
    rendered = (
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else (
            f"ACADEMIC RECOVERY {plan['route']} "
            f"repairs={len(plan['repair_items'])} suppressed={plan['repair_items_suppressed']}\n"
        )
    )
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(rendered, encoding="utf-8", newline="")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
