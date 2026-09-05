#!/usr/bin/env python3
"""Forward tests for source/style separation in section authoring briefs."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from audit_section_authoring_brief import audit
from audit_section_drafting_packets import audit as audit_packets
from audit_section_drafting_usage import audit as audit_usage
from audit_section_judgment_bridges import audit as audit_judgment_bridges
from audit_style_retrieval_plan import audit as audit_style_plan
from prepare_section_authoring_brief import build_brief
from prepare_section_drafting_packets import write_bundle
from prepare_section_drafting_usage import build as build_usage
from prepare_style_retrieval_plan import build_plan


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-section-brief-") as temp:
        root = Path(temp)
        (root / "inputs").mkdir()
        (root / "solver").mkdir()
        problem = root / "inputs" / "problem.txt"
        solver = root / "solver" / "solve.py"
        result = root / "solver" / "result.txt"
        problem.write_text("capacity = 10", encoding="utf-8")
        solver.write_text("capacity = 10", encoding="utf-8")
        result.write_text("最优方案满足容量约束。", encoding="utf-8")
        main_tex = root / "main.tex"
        main_tex.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\begin{abstract}报告离散方案和检验结果。\\end{abstract}\n"
            "\\section{问题分析}\n容量上限限制了方案规模。\n"
            "\\section{问题一模型建立与求解}\n"
            "容量上限必须进入可行域，再由整数规划处理离散选择，设 $x=1$。\n"
            "\\subsection{结果与检验}\n报告最优方案并回代容量约束。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        workbench_path = root / "modeling-workbench.json"
        workbench = {
            "schema": "mcm-modeling-workbench/v1",
            "sources": [
                {"id": "problem", "role": "problem", "path": "inputs/problem.txt", "sha256": digest(problem)},
                {"id": "solver", "role": "code", "path": "solver/solve.py", "sha256": digest(solver)},
                {"id": "result", "role": "result", "path": "solver/result.txt", "sha256": digest(result)},
            ],
            "questions": [{
                "id": "1",
                "anchors": [{"id": "capacity", "kind": "constraint", "terms": ["容量上限"], "source_ref": "题面", "source_ids": ["problem"]}],
                "targets": [{"id": "feasible", "terms": ["可行域"], "source_ref": "容量约束数学化"}],
                "routes": [{"id": "ip", "name": "整数规划", "status": "selected", "terms": ["整数规划"], "anchor_ids": ["capacity"], "target_ids": ["feasible"], "evidence_ids": ["solver"], "evidence_ref": "solver/solve.py"}],
                "checks": [{
                    "id": "replay", "kind": "feasibility", "terms": ["容量约束"],
                    "result": "最优方案满足容量约束", "result_terms": ["最优方案"],
                }],
                "interpretations": [{
                    "id": "active-capacity", "kind": "active_constraint",
                    "observation_terms": ["最优方案"],
                    "explanation_terms": ["容量约束"],
                    "source_ids": ["result"], "source_ref": "solver/result.txt:1",
                }],
                "drafting": {"mode": "relation_then_method", "public_route_id": "ip"},
            }],
        }
        workbench_path.write_text(json.dumps(workbench, ensure_ascii=False), encoding="utf-8")
        preflight_path = root / "reasoning-preflight.json"
        preflight = {
            "schema": "mcm-reasoning-preflight/v1",
            "workbench_sha256": digest(workbench_path),
            "approvals": [{
                "question_id": "1", "reviewer": "队长", "reviewer_kind": "human",
                "anchor_ids": ["capacity"], "target_ids": ["feasible"], "source_ids": ["problem", "solver"],
                "route_id": "ip", "basis_confirmation": "题面的容量上限限制每个离散方案的规模。",
                "transition_confirmation": "容量上限进入可行域后，再用整数规划处理离散选择。",
                "change_trigger": "若容量允许共享，需要重写资源约束后再确定路线。", "decision": "approve",
            }],
        }
        preflight_path.write_text(json.dumps(preflight, ensure_ascii=False), encoding="utf-8")
        style_path = root / "style-retrieval-plan.json"
        style = build_plan(main_tex, "B", minimum=3, limit=3, context_window=1)
        style_path.write_text(json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")
        brief = build_brief(main_tex, "B", style_path, workbench_path, preflight_path)
        brief_path = root / "section-authoring-brief.json"
        brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
        checked = audit(main_tex, brief_path, "B", style_path, workbench_path, preflight_path)
        assert checked["status"] == "pass", checked
        release_dir = root / "release"
        release_dir.mkdir()
        release_tex = release_dir / "main.tex"
        release_tex.write_text(main_tex.read_text(encoding="utf-8"), encoding="utf-8")
        relocated = audit(release_tex, brief_path, "B", style_path, workbench_path, preflight_path)
        assert relocated["status"] == "pass", relocated
        assert brief["status"] == "pass", brief
        question_sections = [item for item in brief["sections"] if item["question_id"] == "1"]
        assert question_sections and all(item["current_problem"]["question_ids"] == ["1"] for item in question_sections)
        assert all(
            item["human_style"]["language_action_profile"]["primary_anchor_id"]
            and item["human_style"]["language_action_profile"]["use_rule"]
            and item["human_style"]["language_action_profile"]["ending_actions"]
            for item in brief["sections"]
        )
        assert all(
            "text" not in ref and "previous_context" not in ref and "next_context" not in ref
            for section in brief["sections"] for ref in section["human_style"]["anchor_refs"]
        )

        packet_dir = root / "section-drafting-packets"
        packet_index, packet_report = write_bundle(
            main_tex, brief_path, style_path, packet_dir
        )
        packet_audit = audit_packets(main_tex, brief_path, style_path, packet_index)
        assert packet_report["packet_count"] == len(brief["sections"]), packet_report
        assert packet_audit["status"] == "pass", packet_audit
        bridge_audit = audit_judgment_bridges(main_tex, packet_index)
        assert bridge_audit["status"] == "pass", bridge_audit
        assert len(packet_audit["dependencies"]) == packet_report["packet_count"], packet_audit
        relocated_packet_audit = audit_packets(
            release_tex, brief_path, style_path, packet_index
        )
        assert relocated_packet_audit["status"] == "pass", relocated_packet_audit
        packet_record = packet_audit["packets"] and json.loads(
            packet_index.read_text(encoding="utf-8")
        )["packets"][0]
        packet_payload = json.loads(
            Path(packet_record["path"]).read_text(encoding="utf-8")
        )
        packet_original_text = Path(packet_record["path"]).read_text(encoding="utf-8")
        passages = packet_payload["human_style"]["passages"]
        assert passages and passages[0]["reading_role"] == "primary"
        assert packet_payload["human_style"]["style_portfolio_summary"]["selection"] == "relevance-bounded-style-portfolio"
        assert packet_payload["human_style"]["style_portfolio_summary"]["anchors"] == len(passages)
        assert all(isinstance(item.get("variation_from_primary"), list) for item in passages)
        assert any(item.get("variation_from_primary") for item in passages[1:])
        assert "Choose one" in packet_payload["human_style"]["selection_rule"]
        assert isinstance(passages[0].get("text"), str) and passages[0]["text"].strip()
        assert "previous_context" in passages[0] and "next_context" in passages[0]
        assert packet_payload["current_problem"]["question_plans"]
        assert packet_payload["drafting_contract"]["facts_from_current_problem_only"] is True
        assert packet_payload["drafting_contract"]["choose_one_evidence_compatible_motion"] is True
        assert packet_payload["drafting_contract"]["copy_surface_mix_from_multiple_passages_forbidden"] is True
        assert "\\" in packet_payload["current_draft_tex"]
        assert packet_payload["current_draft_tex_sha256"] == hashlib.sha256(
            packet_payload["current_draft_tex"].encode("utf-8")
        ).hexdigest()
        assert any(
            "$x=1$" in json.loads(Path(item["path"]).read_text(encoding="utf-8"))["current_draft_tex"]
            for item in json.loads(packet_index.read_text(encoding="utf-8"))["packets"]
        )
        packet_payload["drafting_contract"]["instruction"] += " tampered"
        Path(packet_record["path"]).write_text(
            json.dumps(packet_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        packet_rejected = audit_packets(main_tex, brief_path, style_path, packet_index)
        assert packet_rejected["status"] == "fail", packet_rejected
        assert any(
            item["code"] == "PACKET_FILE_DRIFT"
            for item in packet_rejected["findings"]
        ), packet_rejected
        Path(packet_record["path"]).write_text(packet_original_text, encoding="utf-8")

        scale_tex = root / "scale-main.tex"
        scale_sections = "\n".join(
            f"\\subsection{{模型建立与求解 {index}}}\n"
            f"容量上限决定第 {index} 个局部可行域，整数规划只处理对应离散选择。"
            for index in range(1, 41)
        )
        scale_tex.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一模型建立与求解}\n"
            "容量上限先限制总体方案规模。\n"
            + scale_sections
            + "\n\\end{document}\n",
            encoding="utf-8",
        )
        scale_style_path = root / "scale-style-retrieval-plan.json"
        scale_style = build_plan(scale_tex, "B", minimum=3, limit=4, context_window=1)
        scale_style_path.write_text(
            json.dumps(scale_style, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        scale_brief_path = root / "scale-section-authoring-brief.json"
        scale_brief = build_brief(
            scale_tex, "B", scale_style_path, workbench_path, preflight_path
        )
        scale_brief_path.write_text(
            json.dumps(scale_brief, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        scale_index, scale_report = write_bundle(
            scale_tex, scale_brief_path, scale_style_path, root / "scale-packets"
        )
        scale_audit = audit_packets(
            scale_tex, scale_brief_path, scale_style_path, scale_index
        )
        assert scale_report["packet_count"] >= 40, scale_report
        assert scale_audit["status"] == "pass", scale_audit

        candidate_tex = root / "candidate.tex"
        candidate_tex.write_text(
            main_tex.read_text(encoding="utf-8").replace("容量上限", "容量边界", 1),
            encoding="utf-8",
        )
        usage_path = root / "section-drafting-usage.json"
        usage = build_usage(
            main_tex, candidate_tex, packet_index, "packet-run-1", "model"
        )
        usage_path.write_text(
            json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        usage_audit = audit_usage(main_tex, candidate_tex, packet_index, usage_path)
        assert usage_audit["status"] == "pass", usage_audit
        formula_candidate = root / "candidate-formula.tex"
        formula_candidate.write_text(
            main_tex.read_text(encoding="utf-8").replace("$x=1$", "$x=2$"),
            encoding="utf-8",
        )
        formula_usage_path = root / "section-drafting-usage-formula.json"
        formula_usage = build_usage(
            main_tex, formula_candidate, packet_index, "packet-run-formula", "model"
        )
        formula_usage_path.write_text(
            json.dumps(formula_usage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        formula_changed = next(
            item for item in formula_usage["sections"]
            if item["source_section"]["tex_sha256"] != item["candidate_section"]["tex_sha256"]
        )
        assert formula_changed["disposition"] == "generated"
        assert formula_changed["source_section"]["visible_sha256"] == formula_changed["candidate_section"]["visible_sha256"]
        formula_audit = audit_usage(
            main_tex, formula_candidate, packet_index, formula_usage_path
        )
        assert formula_audit["status"] == "pass", formula_audit
        formula_candidate.write_text(
            formula_candidate.read_text(encoding="utf-8").replace("$x=2$", "$x=3$"),
            encoding="utf-8",
        )
        formula_drift = audit_usage(
            main_tex, formula_candidate, packet_index, formula_usage_path
        )
        assert formula_drift["status"] == "fail", formula_drift
        assert any(
            item["code"] == "USAGE_CANDIDATE_DRIFT"
            for item in formula_drift["findings"]
        ), formula_drift
        reordered_tex = root / "candidate-reordered.tex"
        original_text = main_tex.read_text(encoding="utf-8")
        section_chunks = original_text.split("\\section{")
        assert len(section_chunks) >= 3
        reordered_tex.write_text(
            section_chunks[0] + "\\section{" + section_chunks[2] + "\\section{" + section_chunks[1] + "\\section{" + "\\section{".join(section_chunks[3:]),
            encoding="utf-8",
        )
        try:
            build_usage(main_tex, reordered_tex, packet_index, "packet-run-reordered", "model")
        except ValueError as exc:
            assert "order" in str(exc)
        else:
            raise AssertionError("reordered candidate sections were accepted")
        added_tex = root / "candidate-added.tex"
        added_title = brief["sections"][1]["title"]
        added_tex.write_text(
            main_tex.read_text(encoding="utf-8").replace(
                "\\end{document}",
                f"\\section{{{added_title}}}\nextra candidate section.\n\\end{{document}}",
            ),
            encoding="utf-8",
        )
        try:
            build_usage(main_tex, added_tex, packet_index, "packet-run-added", "model")
        except ValueError as exc:
            assert "target sets" in str(exc) or "order" in str(exc)
        else:
            raise AssertionError("candidate with an added writable section was accepted")

        multi_source = root / "multi-source"
        multi_candidate = root / "multi-candidate"
        multi_source.mkdir()
        multi_candidate.mkdir()
        multi_main = multi_source / "main.tex"
        multi_child = multi_source / "body.tex"
        multi_main.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n\\input{body}\n\\end{document}\n",
            encoding="utf-8",
        )
        multi_child.write_text(
            f"\\section{{{brief['sections'][1]['title']}}}\n"
            "capacity boundary enters the feasible set before discrete selection.\n",
            encoding="utf-8",
        )
        multi_candidate_main = multi_candidate / "main.tex"
        multi_candidate_child = multi_candidate / "body.tex"
        multi_candidate_main.write_text(
            multi_main.read_text(encoding="utf-8"), encoding="utf-8"
        )
        multi_candidate_child.write_text(
            multi_child.read_text(encoding="utf-8").replace("discrete selection", "discrete plan selection"),
            encoding="utf-8",
        )
        multi_style_path = root / "multi-style-retrieval-plan.json"
        multi_style = build_plan(multi_main, "B", minimum=3, limit=3, context_window=1)
        multi_style_path.write_text(
            json.dumps(multi_style, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        multi_style_audit = audit_style_plan(multi_main, multi_style_path, "B")
        assert multi_style_audit["status"] == "pass", multi_style_audit
        multi_brief_path = root / "multi-section-authoring-brief.json"
        multi_brief = build_brief(
            multi_main, "B", multi_style_path, workbench_path, preflight_path
        )
        multi_brief_path.write_text(
            json.dumps(multi_brief, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        multi_packet_index, _ = write_bundle(
            multi_main, multi_brief_path, multi_style_path, root / "multi-packets"
        )
        multi_usage_path = root / "multi-section-drafting-usage.json"
        multi_usage = build_usage(
            multi_main, multi_candidate_main, multi_packet_index, "packet-run-multi", "model"
        )
        multi_usage_path.write_text(
            json.dumps(multi_usage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        multi_audit = audit_usage(
            multi_main, multi_candidate_main, multi_packet_index, multi_usage_path
        )
        assert multi_audit["status"] == "pass", multi_audit
        multi_candidate_child.write_text(
            multi_candidate_child.read_text(encoding="utf-8").replace("feasible set", "feasible region"),
            encoding="utf-8",
        )
        multi_drift = audit_usage(
            multi_main, multi_candidate_main, multi_packet_index, multi_usage_path
        )
        assert multi_drift["status"] == "fail", multi_drift
        assert any(
            item["code"] == "USAGE_CANDIDATE_SECTION_DRIFT"
            for item in multi_drift["findings"]
        ), multi_drift
        overclaim = json.loads(json.dumps(usage, ensure_ascii=False))
        overclaim["execution"]["consumption_proven"] = True
        overclaim_path = root / "section-drafting-usage-overclaim.json"
        overclaim_path.write_text(
            json.dumps(overclaim, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        overclaim_audit = audit_usage(
            main_tex, candidate_tex, packet_index, overclaim_path
        )
        assert any(
            item["code"] == "USAGE_OVERCLAIMS_CONSUMPTION"
            for item in overclaim_audit["findings"]
        ), overclaim_audit
        malformed_usage_path = root / "section-drafting-usage-malformed.json"
        malformed_usage_path.write_text("[]\n", encoding="utf-8")
        malformed_audit = audit_usage(
            main_tex, candidate_tex, packet_index, malformed_usage_path
        )
        assert any(
            item["code"] == "USAGE_NOT_OBJECT"
            for item in malformed_audit["findings"]
        ), malformed_audit
        candidate_tex.write_text(
            candidate_tex.read_text(encoding="utf-8").replace("整数规划", "整数规划方法", 1),
            encoding="utf-8",
        )
        usage_rejected = audit_usage(main_tex, candidate_tex, packet_index, usage_path)
        assert usage_rejected["status"] == "fail", usage_rejected
        assert any(
            item["code"] == "USAGE_CANDIDATE_DRIFT"
            for item in usage_rejected["findings"]
        ), usage_rejected

        tampered = json.loads(json.dumps(brief, ensure_ascii=False))
        tampered["sections"][0]["current_problem"]["question_plans"][0]["selected_route"]["name"] = "虚构路线"
        brief_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        rejected = audit(main_tex, brief_path, "B", style_path, workbench_path, preflight_path)
        assert rejected["status"] == "fail", rejected
        assert any(item["code"] == "SECTION_AUTHORING_BRIEF_SECTION_DRIFT" for item in rejected["findings"]), rejected

        preflight["approvals"][0]["reviewer_kind"] = "model"
        preflight_path.write_text(json.dumps(preflight, ensure_ascii=False), encoding="utf-8")
        model_brief = build_brief(main_tex, "B", style_path, workbench_path, preflight_path)
        assert model_brief["status"] == "fail", model_brief
        assert any(item["code"] == "AUTHORING_BRIEF_PREFLIGHT_NOT_PASSING" for item in model_brief["findings"]), model_brief

    print("SECTION AUTHORING BRIEF TEST PASS: current facts and style-only anchors remain separated and source-bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
