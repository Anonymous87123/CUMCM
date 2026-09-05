#!/usr/bin/env python3
"""End-to-end regression for source-bound MCM content gains."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = Path(__file__).resolve().parents[3]
MCM_SCRIPTS = SKILLS_ROOT / "mcm-cup-standard-write" / "scripts"
if str(MCM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(MCM_SCRIPTS))

from audit_academic_candidate import audit as audit_academic
from audit_modeling_workbench import audit as audit_workbench
from audit_reasoning_preflight import audit as audit_preflight
from audit_section_drafting_usage import audit as audit_usage
from audit_section_judgment_bridges import audit as audit_bridges
from prepare_section_authoring_brief import build_brief
from prepare_section_drafting_packets import write_bundle
from prepare_section_drafting_usage import build as build_usage
from prepare_style_retrieval_plan import build_plan


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-source-bound-gain-") as temp:
        root = Path(temp)
        inputs = root / "inputs"
        inputs.mkdir()
        problem = inputs / "problem.txt"
        solver = inputs / "solver.py"
        result = inputs / "result.txt"
        log = inputs / "residual.log"
        problem.write_text("每个方案受到容量上限约束。", encoding="utf-8")
        solver.write_text("# integer-program fixture\n", encoding="utf-8")
        result.write_text("方案三总成本取最小值，容量约束取到上界。", encoding="utf-8")
        log.write_text("残差集中在零附近并保持对称。", encoding="utf-8")

        source = root / "source.tex"
        source.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一模型建立与求解}\n"
            "直接采用整数规划求解，随后才说明容量上限和可行域。\n"
            "\\section{问题一结果分析}\n"
            "总成本在方案三取最小值。\n"
            "\\section{问题一模型检验}\n"
            "采用残差检验说明拟合误差。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        candidate = root / "candidate.tex"
        candidate.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一模型建立与求解}\n"
            "题面的容量上限写入可行域，先说明这一关系，再用整数规划处理离散选择。\n"
            "\\section{问题一结果分析}\n"
            "总成本在方案三取最小值，容量约束在该方案取到上界。\n"
            "\\section{问题一模型检验}\n"
            "残差检验说明误差集中在零附近，分布保持对称。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )

        workbench_path = root / "modeling-workbench.json"
        workbench = {
            "schema": "mcm-modeling-workbench/v1",
            "sources": [
                {"id": "problem", "role": "problem", "path": "inputs/problem.txt", "sha256": digest(problem)},
                {"id": "solver", "role": "code", "path": "inputs/solver.py", "sha256": digest(solver)},
                {"id": "result", "role": "result", "path": "inputs/result.txt", "sha256": digest(result)},
                {"id": "residual-log", "role": "log", "path": "inputs/residual.log", "sha256": digest(log)},
            ],
            "questions": [{
                "id": "1",
                "anchors": [{
                    "id": "capacity", "kind": "constraint", "terms": ["容量上限"],
                    "source_ref": "inputs/problem.txt:1", "source_ids": ["problem"],
                }],
                "targets": [{
                    "id": "feasible", "terms": ["可行域"],
                    "source_ref": "容量上限对应的方案边界",
                }],
                "routes": [{
                    "id": "ip", "name": "整数规划", "status": "selected",
                    "terms": ["整数规划"], "anchor_ids": ["capacity"],
                    "target_ids": ["feasible"], "evidence_ids": ["solver"],
                    "evidence_ref": "inputs/solver.py:1",
                }],
                "checks": [{
                    "id": "residual", "kind": "residual", "terms": ["残差检验"],
                    "result": "误差集中在零附近并保持对称",
                    "result_terms": ["零附近"],
                    "artifact": {"path": "inputs/residual.log", "sha256": digest(log)},
                }],
                "interpretations": [{
                    "id": "capacity-active", "kind": "active_constraint",
                    "observation_terms": ["总成本"],
                    "explanation_terms": ["容量约束"],
                    "source_ids": ["result"], "source_ref": "inputs/result.txt:1",
                }],
                "drafting": {
                    "mode": "relation_then_method", "public_route_id": "ip",
                    "keep_out_of_manuscript": "常规求解器日志",
                },
            }],
        }
        write_json(workbench_path, workbench)

        preflight_path = root / "reasoning-preflight.json"
        preflight = {
            "schema": "mcm-reasoning-preflight/v1",
            "workbench_sha256": digest(workbench_path),
            "approvals": [{
                "question_id": "1", "reviewer": "测试队员", "reviewer_kind": "human",
                "anchor_ids": ["capacity"], "target_ids": ["feasible"],
                "source_ids": ["problem", "solver"], "route_id": "ip",
                "basis_confirmation": "题面的容量上限限制方案规模并参与可行性判断。",
                "transition_confirmation": "容量上限写入可行域后，再用整数规划处理离散选择。",
                "change_trigger": "若容量允许跨期共享，需要重写约束后重新确认路线。",
                "decision": "approve",
            }],
        }
        write_json(preflight_path, preflight)

        source_preflight = audit_workbench(source, workbench_path, phase="preflight")
        source_release = audit_workbench(source, workbench_path, phase="release")
        candidate_release = audit_workbench(candidate, workbench_path, phase="release")
        require(source_preflight["status"] == "pass", "source could not enter drafting", source_preflight)
        require(
            source_release["status"] == "fail"
            and any(item["code"] == "WORKBENCH_REASONING_BRIDGE_MISSING" for item in source_release["findings"]),
            "source unexpectedly passed the completed-prose workbench gate",
            source_release,
        )
        require(candidate_release["status"] == "pass", "candidate workbench did not land", candidate_release)
        preflight_report = audit_preflight(workbench_path, preflight_path)
        require(preflight_report["status"] == "pass", "team preflight fixture failed", preflight_report)

        style_path = root / "style-retrieval-plan.json"
        style = build_plan(source, "B", minimum=3, limit=3, context_window=1)
        write_json(style_path, style)
        brief_path = root / "section-authoring-brief.json"
        brief = build_brief(source, "B", style_path, workbench_path, preflight_path)
        write_json(brief_path, brief)
        require(brief["status"] == "pass", "authoring brief did not build from the flawed source", brief)

        packet_index, packet_report = write_bundle(
            source, brief_path, style_path, root / "section-drafting-packets"
        )
        require(packet_report["packet_count"] >= 3, "section packets are incomplete", packet_report)
        source_bridges = audit_bridges(source, packet_index)
        candidate_bridges = audit_bridges(candidate, packet_index)
        require(source_bridges["status"] == "fail", "source bridge defects were not visible", source_bridges)
        require(candidate_bridges["status"] == "pass", "candidate did not repair packet contracts", candidate_bridges)

        usage_path = root / "section-drafting-usage.json"
        write_json(usage_path, build_usage(source, candidate, packet_index, "gain-flow-r1", "model"))
        usage_report = audit_usage(source, candidate, packet_index, usage_path)
        require(usage_report["status"] == "pass", "packet lineage did not bind", usage_report)

        academic = audit_academic(
            source, candidate, scene="MODELING", require_style_gain=True,
            packet_index_path=packet_index,
        )
        gain = next(item for item in academic["gates"] if item["id"] == "style-gain")
        gain_codes = {item["code"] for item in gain["source_bound_improvements"]}
        require(
            academic["status"] == "pass"
            and {
                "SECTION_BRIDGE_ORDER_INVALID",
                "SECTION_BRIDGE_RESULT_EXPLANATION_MISSING",
                "SECTION_BRIDGE_CHECK_CONCLUSION_MISSING",
            } <= gain_codes,
            "the unified release did not recognize all three source-bound content gains",
            academic,
        )

    print("PASS: a flawed MCM source reaches drafting, while only the packet-bound repaired candidate reaches release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
