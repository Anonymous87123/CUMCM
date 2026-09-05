#!/usr/bin/env python3
"""Regression checks for section-bound retrieval from the verified corpus."""

from __future__ import annotations

import json
import copy
import tempfile
from pathlib import Path

from audit_style_retrieval_plan import audit
from prepare_style_retrieval_plan import (
    STYLE_PORTFOLIO_SCORE_TOLERANCE,
    build_plan,
    heading_roles,
    select_style_portfolio,
)
from query_style_patterns import load_holdout_record_ids


def main() -> int:
    assert heading_roles("问题一结果分析") == ["result"]
    assert heading_roles("问题分析") == ["analysis"]
    assert heading_roles("数据分析") == ["analysis"]
    assert heading_roles("问题一模型建立与求解") == ["model", "solve"]
    ranked = [
        (100, {"id": "A", "paper": "C001", "action_sequence": ["fact", "result"], "opening_family": "直接陈述", "closing_family": "结果落点", "sentence_count": 2, "han_chars": 70}),
        (99, {"id": "B", "paper": "C001", "action_sequence": ["fact", "result"], "opening_family": "直接陈述", "closing_family": "结果落点", "sentence_count": 2, "han_chars": 68}),
        (96, {"id": "C", "paper": "C002", "action_sequence": ["phenomenon", "question", "explanation"], "opening_family": "现象起笔", "closing_family": "条件收束", "sentence_count": 3, "han_chars": 118}),
        (95, {"id": "D", "paper": "C003", "action_sequence": ["comparison", "choice"], "opening_family": "比较起笔", "closing_family": "选择落点", "sentence_count": 1, "han_chars": 42}),
    ]
    portfolio = select_style_portfolio(ranked, minimum=3, limit=3)
    portfolio_ids = [item[1]["id"] for item in portfolio]
    assert portfolio_ids[0] == "A", portfolio_ids
    assert "C" in portfolio_ids and "D" in portfolio_ids, portfolio_ids
    assert "B" not in portfolio_ids, portfolio_ids
    # Use a small synthetic manuscript: the test checks routing and provenance,
    # while all anchor text still comes from the installed 59-paper index.
    tex_text = (
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        "\\begin{abstract}给出数据记录、模型结果和适用范围。\\end{abstract}\n"
        "\\section{问题分析}\n"
        "记录粒度不同，先比较缺失字段，再决定模型接口。\n"
        "\\section{问题一模型建立与求解}\n"
        "\\subsection{模型建立}\n"
        "定义状态变量和约束，说明递推关系。\n"
        "\\subsection{求解与结果}\n"
        "比较候选方案，报告结果并解释变化。\n"
        "\\section{任务二（二）模型建立与求解}\\label{mcm-q3-start}\n"
        "\\subsection{事件调度}\n定义资源时钟并检查可行性。\\label{mcm-q3-end}\n"
        "\\section{模型评价与改进}\n"
        "\\subsection{长期行为展示的适用范围}\n"
        "说明结论的边界、代价和适用条件。\n"
        "\\end{document}\n"
    )
    with tempfile.TemporaryDirectory(prefix="mcm-style-plan-") as temp:
        main_tex = Path(temp) / "main.tex"
        plan_path = Path(temp) / "style-retrieval-plan.json"
        main_tex.write_text(tex_text, encoding="utf-8")
        report = build_plan(main_tex, "C", minimum=3, limit=3, context_window=1)
        plan_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        checked = audit(main_tex, plan_path, "C")
        assert checked["status"] == "pass", checked
        tampered = dict(report)
        tampered["targets"] = [dict(report["targets"][0], anchors=report["targets"][0]["anchors"][:2])] + report["targets"][1:]
        plan_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8")
        rejected = audit(main_tex, plan_path, "C")
        assert rejected["status"] == "fail", rejected
        assert any(item["code"] == "STYLE_ANCHOR_COUNT_INVALID" for item in rejected["findings"]), rejected
        plan_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        duplicate = dict(report)
        duplicate["targets"] = [
            dict(report["targets"][0], anchors=[report["targets"][0]["anchors"][0]] * 3)
        ] + report["targets"][1:]
        plan_path.write_text(json.dumps(duplicate, ensure_ascii=False, indent=2), encoding="utf-8")
        rejected_duplicate = audit(main_tex, plan_path, "C")
        assert rejected_duplicate["status"] == "fail", rejected_duplicate
        assert any(item["code"] == "STYLE_ANCHOR_DUPLICATE" for item in rejected_duplicate["findings"]), rejected_duplicate
        plan_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        tampered_anchor = copy.deepcopy(report)
        tampered_anchor["targets"][0]["anchors"][0]["action_sequence"] = ["invented-action"]
        plan_path.write_text(json.dumps(tampered_anchor, ensure_ascii=False, indent=2), encoding="utf-8")
        rejected_anchor = audit(main_tex, plan_path, "C")
        assert rejected_anchor["status"] == "fail", rejected_anchor
        assert any(item["code"] == "STYLE_PLAN_RETRIEVAL_DRIFT" for item in rejected_anchor["findings"]), rejected_anchor
        plan_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        tree_main = Path(temp) / "tree-main.tex"
        tree_child = Path(temp) / "tree-child.tex"
        tree_child.write_text(
            "\\section{问题一模型建立与求解}\\label{mcm-q1-start}\n"
            "\\subsection{模型建立}\n定义状态变量和约束。\\label{mcm-q1-end}\n",
            encoding="utf-8",
        )
        tree_main.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题分析}\n记录粒度决定样本口径。\n"
            "\\input{tree-child}\n\\end{document}\n",
            encoding="utf-8",
        )
        tree_plan_path = Path(temp) / "tree-plan.json"
        tree_plan = build_plan(tree_main, "C", minimum=3, limit=3, context_window=1)
        tree_plan_path.write_text(json.dumps(tree_plan, ensure_ascii=False), encoding="utf-8")
        assert audit(tree_main, tree_plan_path, "C")["status"] == "pass"
        tree_child.write_text(tree_child.read_text(encoding="utf-8") + "补充一个状态边界。\n", encoding="utf-8")
        tree_drift = audit(tree_main, tree_plan_path, "C")
        assert tree_drift["status"] == "fail", tree_drift
        assert any(item["code"] == "STYLE_PLAN_TEX_TREE_DRIFT" for item in tree_drift["findings"]), tree_drift

        abc_reports = {"C": report}
        for problem_type in ("A", "B"):
            abc_reports[problem_type] = build_plan(
                main_tex, problem_type, minimum=3, limit=4, context_window=1
            )
        for problem_type, typed_report in abc_reports.items():
            assert typed_report["status"] == "pass", (problem_type, typed_report)
            summaries = [item["style_portfolio_summary"] for item in typed_report["targets"]]
            assert summaries and all(item["distinct_action_sequences"] >= 2 for item in summaries), (problem_type, summaries)
            assert all(item["distinct_ending_actions"] >= 1 for item in summaries), (problem_type, summaries)
            assert sum(item["distinct_cadence_bands"] >= 2 for item in summaries) >= max(1, len(summaries) * 3 // 4), (problem_type, summaries)

    assert report["status"] == "pass", report
    assert report["errors"] == 0, report
    assert report["corpus"]["reserved_records_excluded"] > 0, report
    assert all(item["anchor_count"] >= 3 for item in report["targets"]), report
    assert all(item["anchors"] for item in report["targets"]), report
    assert all(
        item["primary_anchor_id"] in {anchor["id"] for anchor in item["anchors"]}
        and item["primary_anchor_selection"]["best_score"]
        - item["primary_anchor_selection"]["selected_score"] <= 2
        for item in report["targets"]
    ), report
    assert report["primary_anchor_summary"]["distinct_primary_anchors"] >= 2, report
    assert report["policy"]["supporting_anchor_selection"] == "relevance-bounded-style-portfolio", report
    assert report["policy"]["supporting_anchor_score_tolerance"] == STYLE_PORTFOLIO_SCORE_TOLERANCE, report
    assert all(
        item["style_portfolio_summary"]["anchors"] == item["anchor_count"]
        and item["style_portfolio_summary"]["distinct_papers"] >= 2
        and item["style_portfolio_summary"]["distinct_ending_actions"] >= 1
        and len(item["style_portfolio_summary"]["shapes"]) == item["anchor_count"]
        for item in report["targets"]
    ), report
    assert all(len({anchor["paper"] for anchor in item["anchors"]}) >= 2 for item in report["targets"]), report
    reserved = load_holdout_record_ids()
    assert all(
        anchor["id"] not in reserved
        for item in report["targets"]
        for anchor in item["anchors"]
    ), report
    roles = [(item["title"], item["role"]) for item in report["targets"]]
    assert ("长期行为展示的适用范围", "evaluation") in roles, roles
    ownership = {(item["title"], item["role"]): item["question_id"] for item in report["targets"]}
    assert ownership[("模型建立", "model")] == "1", ownership
    assert ownership[("求解与结果", "solve")] == "1", ownership
    assert ownership[("求解与结果", "result")] == "1", ownership
    assert ownership[("任务二（二）模型建立与求解", "solve")] == "3", ownership
    assert ownership[("事件调度", "solve")] == "3", ownership
    assert ownership[("问题分析", "analysis")] is None, ownership
    assert ownership[("长期行为展示的适用范围", "evaluation")] is None, ownership
    assert report["source"]["sha256"] and report["source"]["tex_tree_sha256"], report
    assert report["corpus"]["fulltext_index_sha256"], report
    assert report["generator"]["plan_builder"]["sha256"], report
    print(f"STYLE RETRIEVAL PLAN TEST PASS targets={len(report['targets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
