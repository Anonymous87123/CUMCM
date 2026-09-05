#!/usr/bin/env python3
"""Regression tests for typed, source-bound role evidence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from orchestrate_portfolio import _receipt_errors, sha256_file
from validate_role_evidence import MANUAL_SPECS, audit


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def field_value(field: str, source: Path, source_sha: str) -> object:
    if field == "path":
        return str(source)
    if field == "sha256":
        return source_sha
    if field.endswith("_refs") or field in {
        "facts", "variables", "variants", "criteria", "excluded_scenes"
    }:
        return ["source:1"]
    if field == "status":
        return "pass"
    if field == "order":
        return 1
    if field == "confidence":
        return 0.95
    return f"value-{field}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-role-evidence-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        source.write_text("source\n", encoding="utf-8")
        candidate = root / "candidate.tex"
        candidate.write_text("candidate\n", encoding="utf-8")
        import hashlib

        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        workbench_input = root / "modeling-workbench.json"
        workbench_input.write_text('{"schema":"mcm-modeling-workbench/v1"}\n', encoding="utf-8")
        approval_input = root / "reasoning-preflight.json"
        approval_input.write_text('{"schema":"mcm-reasoning-preflight/v1"}\n', encoding="utf-8")
        ledger_input = root / "judgment-ledger.json"
        ledger_input.write_text('{"schema":"mcm-public-judgment-ledger/v1"}\n', encoding="utf-8")
        style_input = root / "style-retrieval-plan.json"
        style_input.write_text('{"schema":"mcm-style-retrieval-plan/v1"}\n', encoding="utf-8")
        brief_input = root / "section-authoring-brief.json"
        brief_input.write_text('{"schema":"mcm-section-authoring-brief/v1"}\n', encoding="utf-8")
        packet_input = root / "T01.json"
        packet_tex = "\\section{模型建立}\\n设 $x=1$。\\n"
        packet_input.write_text(json.dumps({
            "schema": "mcm-section-drafting-packet/v1",
            "target": {"id": "T01"},
            "current_draft_tex": packet_tex,
            "current_draft_tex_sha256": hashlib.sha256(packet_tex.encode("utf-8")).hexdigest(),
            "current_problem": {"question_ids": ["1"], "question_plans": [{"id": "1"}]},
            "human_style": {
                "style_portfolio_summary": {
                    "selection": "relevance-bounded-style-portfolio",
                    "anchors": 2,
                    "shapes": [{"id": "P1"}, {"id": "P2"}],
                },
                "selection_rule": "Choose one evidence-compatible rhetorical motion; do not blend surfaces.",
                "passages": [
                    {"reading_role": "primary", "text": "人类段落观察样本。", "variation_from_primary": []},
                    {"reading_role": "supporting", "text": "另一种真实段落写法。", "variation_from_primary": ["opening_family"]},
                ],
            },
            "drafting_contract": {
                "facts_from_current_problem_only": True,
                "read_primary_passage_and_context_before_writing": True,
                "edit_against_current_draft_tex": True,
                "preserve_tex_commands_math_labels_citations": True,
                "fixed_step_template_forbidden": True,
                "copy_corpus_sentence_forbidden": True,
                "import_corpus_fact_model_number_or_conclusion_forbidden": True,
                "choose_one_evidence_compatible_motion": True,
                "copy_surface_mix_from_multiple_passages_forbidden": True,
            },
        }, ensure_ascii=False), encoding="utf-8")
        workbench_sha = hashlib.sha256(workbench_input.read_bytes()).hexdigest()
        approval_sha = hashlib.sha256(approval_input.read_bytes()).hexdigest()
        ledger_sha = hashlib.sha256(ledger_input.read_bytes()).hexdigest()
        style_sha = hashlib.sha256(style_input.read_bytes()).hexdigest()
        brief_sha = hashlib.sha256(brief_input.read_bytes()).hexdigest()
        packet_sha = hashlib.sha256(packet_input.read_bytes()).hexdigest()
        packet_index_input = root / "packet-index.json"
        packet_index_input.write_text(json.dumps({
            "schema": "mcm-section-drafting-packet-index/v1",
            "status": "pass",
            "source": {"path": str(source), "sha256": source_sha, "bytes": source.stat().st_size},
            "packet_count": 1,
            "packets": [{"target_id": "T01", "path": str(packet_input), "sha256": packet_sha, "bytes": packet_input.stat().st_size}],
        }, ensure_ascii=False), encoding="utf-8")
        packet_index_sha = hashlib.sha256(packet_index_input.read_bytes()).hexdigest()

        collection, fields = MANUAL_SPECS["authority-map"]
        valid_manual = write(root / "authority.json", {
            "schema": "aigc-role-evidence/v1",
            "evidence_type": "authority-map",
            "provider": "deai-academic-writing",
            "role": "content-owner",
            "status": "pass",
            "authority_source_sha256": source_sha,
            "execution": {"mode": "manual_skill", "run_id": "run-1"},
            "inputs": [{"path": str(source), "sha256": source_sha, "role": "authority"}],
            collection: [{field: field_value(field, source, source_sha) for field in fields}],
        })
        result = audit(
            valid_manual, "authority-map", "deai-academic-writing",
            "content-owner", source_sha,
        )
        require(result["status"] == "pass", "valid manual evidence failed", result)

        candidate_workbench = write(root / "candidate-workbench.json", {
            "schema": "aigc-adapter-run/v1",
            "package": "AI_paper",
            "action": "workbench-plan",
            "status": "pass",
            "source": {"path": str(candidate), "sha256": candidate_sha},
            "plan": {"serial_rewrite_forbidden": True},
        })
        result = audit(
            candidate_workbench, "workbench-plan", "AI_paper", "workbench",
            source_sha, "H1", candidate_sha,
        )
        require(
            result["status"] == "pass",
            "candidate-bound read-only workbench plan was not accepted",
            result,
        )

        plain = root / "plain.txt"
        plain.write_text("evidence\n", encoding="utf-8")
        result = audit(
            plain, "authority-map", "deai-academic-writing",
            "content-owner", source_sha,
        )
        require("EVIDENCE_JSON_REQUIRED" in result["errors"], "plain text evidence passed", result)

        wrong_source = json.loads(valid_manual.read_text(encoding="utf-8"))
        wrong_source["authority_source_sha256"] = "0" * 64
        result = audit(
            write(root / "wrong-source.json", wrong_source), "authority-map",
            "deai-academic-writing", "content-owner", source_sha,
        )
        require(
            "MANUAL_EVIDENCE_SOURCE_MISMATCH" in result["errors"],
            "wrong source binding passed", result,
        )

        empty_map = json.loads(valid_manual.read_text(encoding="utf-8"))
        empty_map[collection] = []
        result = audit(
            write(root / "empty-map.json", empty_map), "authority-map",
            "deai-academic-writing", "content-owner", source_sha,
        )
        require(
            any(item.startswith("MANUAL_EVIDENCE_COLLECTION_EMPTY") for item in result["errors"]),
            "empty typed evidence passed", result,
        )

        native_reports = {
            "modeling-workbench": {
                "schema": "mcm-modeling-workbench-audit/v1", "status": "pass",
                "errors": 0, "manuscript_questions": 3, "workbench_questions": 3,
                "inputs": {
                    "main_tex": {"path": str(source), "sha256": source_sha},
                    "workbench": {"path": str(workbench_input), "sha256": workbench_sha},
                },
            },
            "reasoning-preflight": {
                "schema": "mcm-reasoning-preflight-audit/v1", "status": "pass",
                "errors": 0, "questions": 3, "approvals": 3,
                "inputs": {
                    "workbench": {"path": str(workbench_input), "sha256": workbench_sha},
                    "approval": {"path": str(approval_input), "sha256": approval_sha},
                },
            },
            "judgment-ledger": {
                "schema": "mcm-public-judgment-ledger-audit/v1", "status": "pass",
                "errors": 0, "manuscript_questions": 3, "ledger_questions": 3,
                "inputs": {
                    "main_tex": {"path": str(source), "sha256": source_sha},
                    "ledger": {"path": str(ledger_input), "sha256": ledger_sha},
                },
            },
            "style-retrieval-plan": {
                "schema": "mcm-style-retrieval-audit/v1", "status": "pass",
                "errors": 0, "target_count": 12, "minimum_distinct_papers": 2, "reserved_records_excluded": 3,
                "manuscript": {"path": str(source), "sha256": source_sha},
            },
            "section-authoring-brief": {
                "schema": "mcm-section-authoring-brief-audit/v1", "status": "pass",
                "errors": 0, "sections": 12,
                "manuscript": {"path": str(source), "sha256": source_sha},
                "inputs": {
                    "brief": {"path": str(brief_input), "sha256": brief_sha},
                    "style_plan": {"path": str(style_input), "sha256": style_sha},
                    "workbench": {"path": str(workbench_input), "sha256": workbench_sha},
                    "preflight": {"path": str(approval_input), "sha256": approval_sha},
                },
            },
            "section-drafting-packets": {
                "schema": "mcm-section-drafting-packet-audit/v1", "status": "pass",
                "errors": 0, "packets": 1,
                "index": {"path": str(packet_index_input), "sha256": packet_index_sha},
            },
        }
        for token, payload in native_reports.items():
            result = audit(
                write(root / f"report-{token}.json", payload), token,
                "mcm-cup-standard-write", "content-owner", source_sha,
            )
            require(result["status"] == "pass", f"valid native {token} failed", result)

        weak_packet_payload = json.loads(packet_input.read_text(encoding="utf-8"))
        weak_packet_payload["human_style"]["passages"] = []
        weak_packet = root / "T01-weak.json"
        weak_packet.write_text(json.dumps(weak_packet_payload, ensure_ascii=False), encoding="utf-8")
        weak_packet_sha = hashlib.sha256(weak_packet.read_bytes()).hexdigest()
        weak_index = root / "packet-index-weak.json"
        weak_index.write_text(json.dumps({
            "schema": "mcm-section-drafting-packet-index/v1",
            "status": "pass",
            "source": {"path": str(source), "sha256": source_sha, "bytes": source.stat().st_size},
            "packet_count": 1,
            "packets": [{"target_id": "T01", "path": str(weak_packet), "sha256": weak_packet_sha, "bytes": weak_packet.stat().st_size}],
        }, ensure_ascii=False), encoding="utf-8")
        weak_index_sha = hashlib.sha256(weak_index.read_bytes()).hexdigest()
        weak_packet_report = write(root / "report-section-drafting-packets-weak.json", {
            "schema": "mcm-section-drafting-packet-audit/v1", "status": "pass",
            "errors": 0, "packets": 1,
            "index": {"path": str(weak_index), "sha256": weak_index_sha},
        })
        result = audit(
            weak_packet_report, "section-drafting-packets",
            "mcm-cup-standard-write", "content-owner", source_sha,
        )
        require(
            "SECTION_DRAFTING_PACKETS_PRIMARY_PASSAGE_MISSING" in result["errors"],
            "a packet without its human primary passage passed native evidence validation",
            result,
        )

        density = write(root / "density.json", {
            "status": "pass", "errors": 0,
            "source": {"path": str(source), "sha256": source_sha},
            "body": {"paragraphs": 80, "han_chars": 12000},
            "questions": [{"id": "1", "paragraphs": 20}],
        })
        result = audit(
            density, "content-density-report", "mcm-cup-standard-write",
            "content-owner", source_sha,
        )
        require(result["status"] == "pass", "valid density report failed", result)

        manuscript = write(root / "manuscript.json", {
            "schema_version": 1, "status": "PASS", "errors": 0,
            "source": {"path": str(source), "sha256": source_sha},
            "warnings": 0, "findings": [],
        })
        result = audit(
            manuscript, "manuscript-audit", "mcm-cup-standard-write",
            "content-owner", source_sha,
        )
        require(result["status"] == "pass", "valid manuscript report failed", result)

        weak_preflight = dict(native_reports["reasoning-preflight"])
        weak_preflight["approvals"] = 2
        result = audit(
            write(root / "weak-preflight.json", weak_preflight),
            "reasoning-preflight", "mcm-cup-standard-write",
            "content-owner", source_sha,
        )
        require(
            "REASONING_PREFLIGHT_COVERAGE_INCOMPLETE" in result["errors"],
            "partial preflight passed", result,
        )

        other_workbench = root / "other-workbench.json"
        other_workbench.write_text('{"schema":"mcm-modeling-workbench/v1","other":true}\n', encoding="utf-8")
        other_workbench_sha = hashlib.sha256(other_workbench.read_bytes()).hexdigest()
        mismatched_preflight = dict(native_reports["reasoning-preflight"])
        mismatched_preflight["inputs"] = {
            "workbench": {"path": str(other_workbench), "sha256": other_workbench_sha},
            "approval": {"path": str(approval_input), "sha256": approval_sha},
        }
        model_report_path = write(root / "cross-model.json", native_reports["modeling-workbench"])
        preflight_report_path = write(root / "cross-preflight.json", mismatched_preflight)
        receipt_path = root / "mcm-receipt.json"
        receipt = {
            "schema": "aigc-role-receipt/v1",
            "provider": "mcm-cup-standard-write",
            "role": "content-owner",
            "status": "pass",
            "authority_source_sha256": source_sha,
            "execution": {
                "mode": "native_executed", "run_id": "cross-binding",
                "references_read": ["SKILL.md"],
            },
            "evidence": {
                "modeling-workbench": {"path": str(model_report_path), "sha256": sha256_file(model_report_path)},
                "reasoning-preflight": {"path": str(preflight_report_path), "sha256": sha256_file(preflight_report_path)},
            },
            "unresolved": [],
        }
        write(receipt_path, receipt)
        errors, _ = _receipt_errors(
            receipt,
            {
                "provider": "mcm-cup-standard-write",
                "required_evidence": ["modeling-workbench", "reasoning-preflight"],
            },
            {"source": {"sha256": source_sha}},
            "content-owner", receipt_path,
        )
        require(
            "EVIDENCE_CROSS_BINDING:MCM_WORKBENCH_PREFLIGHT_MISMATCH" in errors,
            "mismatched workbench and preflight reports passed", errors,
        )

    print("PASS: typed manual evidence, native MCM reports, source binding, coverage and plain-text spoof negatives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
