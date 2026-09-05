#!/usr/bin/env python3
"""Forward tests for the pre-draft CUMCM modeling workbench."""

from __future__ import annotations

import json
import hashlib
import tempfile
from pathlib import Path

from audit_modeling_workbench import audit


GOOD_TEX = r"""
\section{问题一模型建立}
题面给出相邻构件的距离固定。为保证构件的先后次序，候选根还需满足极角递增。
据此建立定长递推，并用二分法求取满足方向条件的可行根。
"""

BAD_BRIDGE_TEX = r"""
\section{问题一模型建立}
题面给出相邻构件的距离固定，据此直接用二分法求取可行根。随后再讨论候选根的极角递增条件。
"""

DIRECT_TEX = r"""
\section{问题一模型建立}
题面给出相邻构件的距离固定，故令相邻端点满足定长关系，并逐项递推位置。
"""

TYPE_CASES = {
    "B": {
        "tex": r"""
\section{问题一模型建立}
返工费用并不固定，它取决于检测开关是否触发。故先将检测动作编码为 0--1 决策变量，
并把返工成本写入状态转移。在此结构下，采用动态规划比较可行策略。
""",
        "anchor": ("cost-trigger", "structure", "返工费用", "fixture: rework cost trigger"),
        "target": ("inspection-switch", "检测开关", "fixture: decision variable"),
        "route": ("state-dp", "dynamic programming", "动态规划", "method_after_structure"),
    },
    "C": {
        "tex": r"""
\section{问题一模型建立}
日销量中存在大量零值，直接把每日记录作为连续响应会掩盖同期变化。于是先按同期平均重构训练输入，
再用 Bayesian 模型刻画各时段的销售分布。
""",
        "anchor": ("zero-inflation", "data", "大量零值", "fixture: zero-inflated sales"),
        "target": ("seasonal-aggregation", "同期平均", "fixture: input reconstruction"),
        "route": ("bayesian-model", "Bayesian model", "Bayesian 模型", "relation_then_method"),
    },
}


def sources(root: Path) -> list[dict]:
    inputs = root / "inputs"
    inputs.mkdir(exist_ok=True)
    problem = inputs / "problem.txt"
    solver = inputs / "solver.txt"
    result = inputs / "result.txt"
    problem.write_text("相邻构件距离固定；返工费用受检测动作影响；日销量存在大量零值。", encoding="utf-8")
    solver.write_text("fixture solver implementation", encoding="utf-8")
    result.write_text("候选根满足极角递增，方向检查通过。", encoding="utf-8")
    return [
        {"id": "problem", "role": "problem", "path": "inputs/problem.txt", "sha256": hashlib.sha256(problem.read_bytes()).hexdigest()},
        {"id": "solver", "role": "code", "path": "inputs/solver.txt", "sha256": hashlib.sha256(solver.read_bytes()).hexdigest()},
        {"id": "result", "role": "result", "path": "inputs/result.txt", "sha256": hashlib.sha256(result.read_bytes()).hexdigest()},
    ]


def workbench(root: Path, anchor_term: str = "距离固定") -> dict:
    return {
        "schema": "mcm-modeling-workbench/v1",
        "sources": sources(root),
        "questions": [{
            "id": "1",
            "anchors": [{
                "id": "fixed-distance",
                "kind": "relation",
                "terms": [anchor_term],
                "source_ref": "fixture: fixed-distance condition",
                "source_ids": ["problem"],
            }],
            "targets": [{
                "id": "root-order",
                "terms": ["极角递增"],
                "source_ref": "fixture: component order",
            }],
            "routes": [{
                "id": "fixed-length-recurrence",
                "name": "fixed-length recurrence and bisection",
                "status": "selected",
                "terms": ["二分法"],
                "anchor_ids": ["fixed-distance"],
                "target_ids": ["root-order"],
                "evidence_ids": ["solver"],
                "evidence_ref": "fixture solver:42-68",
            }],
            "checks": [{
                "id": "root-direction",
                "kind": "feasibility",
                "terms": ["极角递增"],
                "result": "only roots respecting component order are retained",
                "result_terms": ["极角递增"],
            }],
            "interpretations": [{
                "id": "root-order-explanation",
                "kind": "active_constraint",
                "observation_terms": ["可行根"],
                "explanation_terms": ["极角递增"],
                "source_ids": ["result"],
                "source_ref": "inputs/result.txt:1",
            }],
            "drafting": {
                "mode": "relation_then_method",
                "public_route_id": "fixed-length-recurrence",
                "keep_out_of_manuscript": "ordinary iteration details",
            },
        }],
    }


def has_code(report: dict, code: str) -> bool:
    return any(item.get("code") == code for item in report["findings"])


def type_workbench(root: Path, case: dict) -> dict:
    anchor_id, anchor_kind, anchor_term, anchor_ref = case["anchor"]
    target_id, target_term, target_ref = case["target"]
    route_id, route_name, route_term, mode = case["route"]
    return {
        "schema": "mcm-modeling-workbench/v1",
        "sources": sources(root),
        "questions": [{
            "id": "1",
            "anchors": [{
                "id": anchor_id,
                "kind": anchor_kind,
                "terms": [anchor_term],
                "source_ref": anchor_ref,
                "source_ids": ["problem"],
            }],
            "targets": [{
                "id": target_id,
                "terms": [target_term],
                "source_ref": target_ref,
            }],
            "routes": [{
                "id": route_id,
                "name": route_name,
                "status": "selected",
                "terms": [route_term],
                "anchor_ids": [anchor_id],
                "target_ids": [target_id],
                "evidence_ids": ["solver"],
                "evidence_ref": "fixture: implemented route",
            }],
            "drafting": {"mode": mode, "public_route_id": route_id},
        }],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-modeling-workbench-") as temp_dir:
        root = Path(temp_dir)
        tex_path = root / "main.tex"
        good_path = root / "good.json"
        bad_path = root / "bad.json"
        bridge_path = root / "bridge.json"
        direct_path = root / "direct.json"
        tex_path.write_text(GOOD_TEX, encoding="utf-8")
        good_path.write_text(json.dumps(workbench(root), ensure_ascii=False), encoding="utf-8")
        bad_path.write_text(json.dumps(workbench(root, "负载上限"), ensure_ascii=False), encoding="utf-8")
        good_report = audit(tex_path, good_path)
        (root / "inputs" / "problem.txt").write_text("fixture source drift", encoding="utf-8")
        drift_report = audit(tex_path, good_path)
        sources(root)
        bad_report = audit(tex_path, bad_path)
        tex_path.write_text(BAD_BRIDGE_TEX, encoding="utf-8")
        bridge_path.write_text(json.dumps(workbench(root), ensure_ascii=False), encoding="utf-8")
        bridge_report = audit(tex_path, bridge_path)
        bridge_preflight_report = audit(tex_path, bridge_path, phase="preflight")
        direct = workbench(root)
        direct_question = direct["questions"][0]
        direct_question["targets"][0]["terms"] = ["定长关系"]
        direct_question["routes"][0]["terms"] = ["定长关系"]
        direct_question["checks"] = []
        direct_question["interpretations"] = []
        direct_question["drafting"]["mode"] = "direct_derivation"
        tex_path.write_text(DIRECT_TEX, encoding="utf-8")
        direct_path.write_text(json.dumps(direct, ensure_ascii=False), encoding="utf-8")
        direct_report = audit(tex_path, direct_path)
        invalid_interpretation = workbench(root)
        invalid_interpretation["questions"][0]["interpretations"][0]["source_ids"] = ["problem"]
        invalid_interpretation_path = root / "invalid-interpretation.json"
        invalid_interpretation_path.write_text(
            json.dumps(invalid_interpretation, ensure_ascii=False), encoding="utf-8"
        )
        invalid_interpretation_report = audit(tex_path, invalid_interpretation_path)
        type_reports = {}
        for problem_type, case in TYPE_CASES.items():
            tex_path.write_text(case["tex"], encoding="utf-8")
            type_path = root / f"{problem_type}.json"
            type_path.write_text(json.dumps(type_workbench(root, case), ensure_ascii=False), encoding="utf-8")
            type_reports[problem_type] = audit(tex_path, type_path)
    if good_report["status"] != "pass":
        print(good_report)
        return 1
    if bad_report["status"] != "fail" or not has_code(bad_report, "WORKBENCH_ANCHOR_NOT_IN_SCOPE"):
        print(bad_report)
        return 1
    if drift_report["status"] != "fail" or not has_code(drift_report, "WORKBENCH_SOURCE_HASH_MISMATCH"):
        print(drift_report)
        return 1
    if bridge_report["status"] != "fail" or not has_code(bridge_report, "WORKBENCH_REASONING_BRIDGE_MISSING"):
        print(bridge_report)
        return 1
    if bridge_preflight_report["status"] != "pass" or bridge_preflight_report["phase"] != "preflight":
        print(bridge_preflight_report)
        return 1
    if direct_report["status"] != "pass":
        print(direct_report)
        return 1
    if (
        invalid_interpretation_report["status"] != "fail"
        or not has_code(
            invalid_interpretation_report,
            "WORKBENCH_INTERPRETATION_WITHOUT_RESULT_SOURCE",
        )
    ):
        print(invalid_interpretation_report)
        return 1
    for problem_type, report in type_reports.items():
        if report["status"] != "pass":
            print(problem_type, report)
            return 1
    print("PASS: A/B/C reasoning bridges differ; direct derivation remains permitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
