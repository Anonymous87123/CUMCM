#!/usr/bin/env python3
"""Regression tests for source-bound public judgment bridge auditing."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from audit_section_judgment_bridges import audit
from prepare_style_retrieval_plan import section_target_records


def packet_for(source: Path, packet_path: Path, *, alternative: bool = False) -> Path:
    raw = source.read_text(encoding="utf-8")
    target = section_target_records(raw)[0]
    question = {
        "question_id": "1",
        "drafting_mode": "relation_then_method",
        "basis_nodes": [{"id": "capacity", "terms": ["容量上限"]}],
        "mathematical_change_nodes": [{"id": "feasible", "terms": ["可行域"]}],
        "selected_route": {"id": "ip", "name": "整数规划", "terms": ["整数规划"]},
        "recorded_alternative_routes": (
            [{"id": "greedy", "name": "贪心", "terms": ["贪心"]}] if alternative else []
        ),
        "local_requirements": {
            "basis_term_required": True,
            "mathematical_change_term_required": True,
            "selected_route_term_required": True,
            "bridge_required_if_route_named": True,
            "minimum_basis_groups": 1,
            "minimum_target_groups": 1,
        },
    }
    payload = {
        "schema": "mcm-section-drafting-packet/v1",
        "target": {
            "id": "T01", "title": target["title"], "role": target["role"],
            "question_id": target["question_id"],
        },
        "public_judgment_contract": {
            "schema": "mcm-section-public-judgment-contract/v1",
            "required": True,
            "questions": [question],
            "policy": {"unrecorded_model_comparison_story_forbidden": True},
        },
    }
    packet_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    index_path = packet_path.parent / "packet-index.json"
    index_path.write_text(json.dumps({
        "schema": "mcm-section-drafting-packet-index/v1",
        "status": "pass",
        "packets": [{
            "target_id": "T01", "path": str(packet_path),
            "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return index_path


def evidence_packet_for(source: Path, packet_path: Path, *, role: str) -> Path:
    target = section_target_records(source.read_text(encoding="utf-8"))[0]
    if role == "result":
        question = {
            "question_id": "1",
            "result_interpretations": [{
                "id": "capacity-active", "kind": "active_constraint",
                "observation_terms": ["总成本最低"],
                "explanation_terms": ["容量约束"],
                "source_ids": ["result"], "source_ref": "results/summary.csv:3",
            }],
            "actual_checks": [],
            "local_requirements": {
                "result_interpretation_required": True,
                "validation_conclusion_required": False,
                "model_comparison_guard": False,
            },
        }
    else:
        question = {
            "question_id": "1",
            "result_interpretations": [],
            "actual_checks": [{
                "id": "residual", "kind": "residual",
                "terms": ["残差检验"],
                "result": "误差集中在零附近",
                "result_terms": ["零附近"],
            }],
            "local_requirements": {
                "result_interpretation_required": False,
                "validation_conclusion_required": True,
                "model_comparison_guard": False,
            },
        }
    packet_path.write_text(json.dumps({
        "schema": "mcm-section-drafting-packet/v1",
        "target": {
            "id": "T01", "title": target["title"], "role": target["role"],
            "question_id": target["question_id"],
        },
        "public_judgment_contract": {
            "schema": "mcm-section-public-judgment-contract/v1",
            "required": True,
            "questions": [question],
        },
    }, ensure_ascii=False), encoding="utf-8")
    index_path = packet_path.parent / f"{packet_path.stem}-index.json"
    index_path.write_text(json.dumps({
        "schema": "mcm-section-drafting-packet-index/v1",
        "status": "pass",
        "packets": [{
            "target_id": "T01", "path": str(packet_path),
            "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return index_path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-judgment-bridges-") as temp:
        root = Path(temp)
        good = root / "good.tex"
        good.write_text(
            "\\section{问题一模型建立}\n"
            "题面的容量上限决定方案不能无限扩张。容量上限进入可行域后，"
            "再用整数规划处理离散选择。\n", encoding="utf-8"
        )
        packet_index = packet_for(good, root / "T01.json")
        passing = audit(good, packet_index)
        assert passing["status"] == "pass", passing

        relation_first = root / "relation-first.tex"
        relation_first.write_text(
            "\\section{问题一模型建立}\n"
            "先把设备组合写成可行域，再用整数规划保留离散选择；"
            "其中可行域的边界正是题面给出的容量上限。\n", encoding="utf-8"
        )
        relation_first_index = packet_for(relation_first, root / "T01-relation-first.json")
        relation_first_result = audit(relation_first, relation_first_index)
        assert relation_first_result["status"] == "pass", relation_first_result

        fact_then_method = root / "fact-then-method.tex"
        fact_then_method.write_text(
            "\\section{问题一模型建立}\n"
            "容量上限先排除了无限扩张的组合。整数规划随后承担离散选择，"
            "各项容量约束共同界定可行域。\n", encoding="utf-8"
        )
        fact_then_method_index = packet_for(fact_then_method, root / "T01-fact-first.json")
        fact_then_method_result = audit(fact_then_method, fact_then_method_index)
        assert fact_then_method_result["status"] == "pass", fact_then_method_result

        nested_heading = root / "nested-heading.tex"
        nested_heading.write_text(
            "\\section{闂涓€妯″瀷寤虹珛}\n"
            "\\subsection{鏁存暟瑙勫垝妯″瀷寤虹珛}\n"
            "棰橀潰鐨勫閲忎笂闄愬喅瀹氭柟妗堜笉鑳芥棤闄愭墿寮犮€俓n"
            "\\subsection{鍙鍩熷垎鏋愪笌姹傝В}\n"
            "鍐嶇敤鏁存暟瑙勫垝澶勭悊绂绘暎閫夋嫨銆俓n",
            encoding="utf-8",
        )
        nested_result = audit(nested_heading, packet_index)
        assert nested_result["status"] == "fail", nested_result
        assert any(item["code"] == "SECTION_BRIDGE_TARGET_COUNT_MISMATCH" for item in nested_result["findings"]), nested_result

        bad_order = root / "bad-order.tex"
        bad_order.write_text(
            "\\section{问题一模型建立}\n"
            "直接采用整数规划求解，随后才说明容量上限和可行域。\n", encoding="utf-8"
        )
        bad_order_result = audit(bad_order, packet_index)
        assert bad_order_result["status"] == "fail", bad_order_result
        assert any(item["code"] == "SECTION_BRIDGE_ORDER_INVALID" for item in bad_order_result["findings"]), bad_order_result

        bad_comparison = root / "bad-comparison.tex"
        bad_comparison.write_text(
            "\\section{问题一模型建立}\n"
            "容量上限进入可行域后，经过比较多种模型选择整数规划。\n", encoding="utf-8"
        )
        bad_comparison_index = packet_for(bad_comparison, root / "T01-comparison.json")
        bad_comparison_result = audit(bad_comparison, bad_comparison_index)
        assert bad_comparison_result["status"] == "fail", bad_comparison_result
        assert any(item["code"] == "SECTION_BRIDGE_UNRECORDED_COMPARISON_CLAIM" for item in bad_comparison_result["findings"]), bad_comparison_result

        alternative_source = root / "alternative.tex"
        alternative_source.write_text(
            "\\section{问题一模型建立}\n"
            "容量上限进入可行域后，比较贪心与整数规划，最终保留整数规划。\n", encoding="utf-8"
        )
        alternative_index = packet_for(alternative_source, root / "T01-alternative.json", alternative=True)
        alternative_result = audit(alternative_source, alternative_index)
        assert alternative_result["status"] == "pass", alternative_result

        result_source = root / "result-source.tex"
        result_source.write_text(
            "\\section{问题一结果分析}\n总成本最低出现在方案三。\n",
            encoding="utf-8",
        )
        result_index = evidence_packet_for(
            result_source, root / "T01-result.json", role="result"
        )
        result_missing = audit(result_source, result_index)
        assert result_missing["status"] == "fail", result_missing
        assert any(
            item["code"] == "SECTION_BRIDGE_RESULT_EXPLANATION_MISSING"
            for item in result_missing["findings"]
        ), result_missing
        result_candidate = root / "result-candidate.tex"
        result_candidate.write_text(
            "\\section{问题一结果分析}\n"
            "总成本最低出现在方案三，此时容量约束恰好取到上界。\n",
            encoding="utf-8",
        )
        result_passing = audit(result_candidate, result_index)
        assert result_passing["status"] == "pass", result_passing

        validation_source = root / "validation-source.tex"
        validation_source.write_text(
            "\\section{问题一模型检验}\n采用残差检验复核拟合结果。\n",
            encoding="utf-8",
        )
        validation_index = evidence_packet_for(
            validation_source, root / "T01-validation.json", role="validation"
        )
        validation_missing = audit(validation_source, validation_index)
        assert validation_missing["status"] == "fail", validation_missing
        assert any(
            item["code"] == "SECTION_BRIDGE_CHECK_CONCLUSION_MISSING"
            for item in validation_missing["findings"]
        ), validation_missing
        validation_candidate = root / "validation-candidate.tex"
        validation_candidate.write_text(
            "\\section{问题一模型检验}\n"
            "残差检验显示误差集中在零附近，未见连续偏移。\n",
            encoding="utf-8",
        )
        validation_passing = audit(validation_candidate, validation_index)
        assert validation_passing["status"] == "pass", validation_passing
    print("PASS: public judgment bridges block unsupported model jumps without imposing one prose order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
