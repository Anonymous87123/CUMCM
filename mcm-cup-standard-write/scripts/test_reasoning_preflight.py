#!/usr/bin/env python3
"""Forward tests for the CUMCM reasoning preflight gate."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from audit_reasoning_preflight import audit


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workbench(root: Path) -> dict:
    problem = root / "inputs" / "problem.txt"
    solver = root / "solver" / "plan.py"
    return {
        "schema": "mcm-modeling-workbench/v1",
        "sources": [
            {"id": "problem", "role": "problem", "path": "inputs/problem.txt", "sha256": digest(problem)},
            {"id": "solver", "role": "code", "path": "solver/plan.py", "sha256": digest(solver)},
        ],
        "questions": [{
            "id": "1",
            "anchors": [{
                "id": "capacity", "kind": "constraint", "terms": ["容量上限"],
                "source_ref": "题面第 2 条", "source_ids": ["problem"],
            }],
            "targets": [{
                "id": "feasible-set", "terms": ["可行域"], "source_ref": "容量约束的数学化",
            }],
            "routes": [{
                "id": "integer-plan", "name": "整数规划", "status": "selected", "terms": ["整数规划"],
                "anchor_ids": ["capacity"], "target_ids": ["feasible-set"], "evidence_ids": ["solver"],
                "evidence_ref": "solver/plan.py:12-31",
            }],
            "drafting": {"mode": "relation_then_method", "public_route_id": "integer-plan"},
        }],
    }


def approval(workbench_path: Path) -> dict:
    return {
        "schema": "mcm-reasoning-preflight/v1",
        "workbench_sha256": digest(workbench_path),
        "approvals": [{
            "question_id": "1",
            "reviewer": "队长",
            "reviewer_kind": "human",
            "anchor_ids": ["capacity"],
            "target_ids": ["feasible-set"],
            "source_ids": ["problem", "solver"],
            "route_id": "integer-plan",
            "basis_confirmation": "题面的容量上限使每个方案都必须保留剩余容量。",
            "transition_confirmation": "把容量上限写入可行域后，再由整数规划统一处理离散选择。",
            "change_trigger": "若容量可以临时共享，应改写资源约束而不是沿用当前路线。",
            "decision": "approve",
        }],
    }


def has_code(report: dict, code: str) -> bool:
    return any(item.get("code") == code for item in report["findings"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-reasoning-preflight-") as temp_dir:
        root = Path(temp_dir)
        (root / "inputs").mkdir()
        (root / "solver").mkdir()
        (root / "inputs" / "problem.txt").write_text("capacity = 10", encoding="utf-8")
        (root / "solver" / "plan.py").write_text("capacity = 10", encoding="utf-8")
        workbench_path = root / "modeling-workbench.json"
        approval_path = root / "reasoning-preflight.json"
        workbench_path.write_text(json.dumps(workbench(root), ensure_ascii=False), encoding="utf-8")
        approval_path.write_text(json.dumps(approval(workbench_path), ensure_ascii=False), encoding="utf-8")
        good_report = audit(workbench_path, approval_path)

        model_approval = approval(workbench_path)
        model_approval["approvals"][0]["reviewer_kind"] = "model"
        model_path = root / "model-preflight.json"
        model_path.write_text(json.dumps(model_approval, ensure_ascii=False), encoding="utf-8")
        model_report = audit(workbench_path, model_path)

        stale_plan = audit(workbench_path, approval_path)
        (root / "solver" / "plan.py").write_text("capacity = 12", encoding="utf-8")
        source_drift = audit(workbench_path, approval_path)
        workbench_path.write_text(workbench_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        workbench_drift = audit(workbench_path, approval_path)
    if good_report["status"] != "pass" or stale_plan["status"] != "pass":
        print(good_report)
        return 1
    if source_drift["status"] != "fail" or not has_code(source_drift, "PREFLIGHT_SOURCE_HASH_MISMATCH"):
        print(source_drift)
        return 1
    if model_report["status"] != "fail" or not has_code(model_report, "PREFLIGHT_REVIEWER_KIND_NOT_HUMAN"):
        print(model_report)
        return 1
    if workbench_drift["status"] != "fail" or not has_code(workbench_drift, "PREFLIGHT_WORKBENCH_HASH_MISMATCH"):
        print(workbench_drift)
        return 1
    print("PASS: compact human, source-bound question approval is required before long-form drafting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
