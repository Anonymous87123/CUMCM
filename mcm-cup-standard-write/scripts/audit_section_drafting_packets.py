#!/usr/bin/env python3
"""Audit a source-bound section drafting packet bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from prepare_section_drafting_packets import (
    BUILDER_PATH,
    INDEX_SCHEMA,
    SCHEMA,
    build_packets,
    sha256_file,
)


def audit(
    main_tex: Path,
    brief: Path,
    style_plan: Path,
    index_path: Path,
) -> dict:
    findings: list[dict] = []
    main_tex = main_tex.resolve()
    brief = brief.resolve()
    style_plan = style_plan.resolve()
    index_path = index_path.resolve()
    try:
        index = json.loads(index_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "mcm-section-drafting-packet-audit/v1",
            "status": "fail",
            "errors": 1,
            "findings": [{"severity": "error", "code": "PACKET_INDEX_INVALID", "detail": str(exc)}],
        }
    if index.get("schema") != INDEX_SCHEMA or index.get("status") != "pass":
        findings.append({"severity": "error", "code": "PACKET_INDEX_SCHEMA_OR_STATUS_INVALID"})
    index_source = index.get("source") if isinstance(index.get("source"), dict) else {}
    if not main_tex.is_file():
        findings.append({"severity": "error", "code": "PACKET_SOURCE_MISSING", "path": str(main_tex)})
    else:
        main_sha = sha256_file(main_tex)
        if index_source.get("sha256") != main_sha or index_source.get("bytes") != main_tex.stat().st_size:
            findings.append({
                "severity": "error", "code": "PACKET_SOURCE_DRIFT",
                "expected_sha256": main_sha,
                "actual_sha256": index_source.get("sha256"),
            })
    index_inputs = index.get("inputs") if isinstance(index.get("inputs"), dict) else {}
    for key, path in (("brief", brief), ("style_plan", style_plan)):
        record = index_inputs.get(key) if isinstance(index_inputs.get(key), dict) else {}
        if not path.is_file() or record.get("sha256") != sha256_file(path) or record.get("bytes") != path.stat().st_size:
            findings.append({"severity": "error", "code": "PACKET_INPUT_DRIFT", "input": key})
    builder_record = index_inputs.get("builder") if isinstance(index_inputs.get("builder"), dict) else {}
    if builder_record.get("sha256") != sha256_file(BUILDER_PATH):
        findings.append({"severity": "error", "code": "PACKET_BUILDER_DRIFT"})
    try:
        expected = build_packets(main_tex, brief, style_plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append({"severity": "error", "code": "PACKET_REBUILD_FAILED", "detail": str(exc)})
        expected = {}
    records = index.get("packets") if isinstance(index.get("packets"), list) else []
    if index.get("packet_count") != len(records):
        findings.append({"severity": "error", "code": "PACKET_COUNT_MISMATCH"})
    actual_ids = {str(item.get("target_id")) for item in records if isinstance(item, dict)}
    if len(actual_ids) != len(records):
        findings.append({"severity": "error", "code": "PACKET_TARGET_DUPLICATE"})
    expected_ids = set(expected)
    if actual_ids != expected_ids:
        findings.append({
            "severity": "error", "code": "PACKET_TARGET_SET_MISMATCH",
            "expected": sorted(expected_ids), "actual": sorted(actual_ids),
        })
    for record in records:
        if not isinstance(record, dict):
            findings.append({"severity": "error", "code": "PACKET_RECORD_INVALID"})
            continue
        target_id = str(record.get("target_id", ""))
        path = Path(str(record.get("path", ""))).resolve()
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            findings.append({"severity": "error", "code": "PACKET_FILE_DRIFT", "target_id": target_id})
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append({"severity": "error", "code": "PACKET_JSON_INVALID", "target_id": target_id, "detail": str(exc)})
            continue
        expected_payload = expected.get(target_id)
        # The release runner audits the source snapshot, while the packet was
        # usually built beside the authority source. The source path may move;
        # its byte hash and every other locked input must remain identical.
        if isinstance(expected_payload, dict):
            expected_payload = json.loads(json.dumps(expected_payload, ensure_ascii=False))
            expected_main = expected_payload.get("inputs", {}).get("main_tex", {})
            actual_main = payload.get("inputs", {}).get("main_tex", {})
            if isinstance(expected_main, dict) and isinstance(actual_main, dict):
                expected_main["path"] = actual_main.get("path")
        if payload != expected_payload:
            findings.append({"severity": "error", "code": "PACKET_CONTENT_DRIFT", "target_id": target_id})
        if payload.get("schema") != SCHEMA:
            findings.append({"severity": "error", "code": "PACKET_SCHEMA_INVALID", "target_id": target_id})
        tex_source = payload.get("current_draft_tex")
        if (
            not isinstance(tex_source, str)
            or not tex_source.strip()
            or payload.get("current_draft_tex_sha256")
            != hashlib.sha256(tex_source.encode("utf-8")).hexdigest()
        ):
            findings.append({"severity": "error", "code": "PACKET_TEX_SCOPE_INVALID", "target_id": target_id})
        human_style = payload.get("human_style") if isinstance(payload.get("human_style"), dict) else {}
        passages = human_style.get("passages") if isinstance(human_style.get("passages"), list) else []
        portfolio = human_style.get("style_portfolio_summary") if isinstance(human_style.get("style_portfolio_summary"), dict) else {}
        supporting = [item for item in passages[1:] if isinstance(item, dict)]
        if (
            not passages
            or not isinstance(passages[0], dict)
            or passages[0].get("reading_role") != "primary"
            or portfolio.get("selection") != "relevance-bounded-style-portfolio"
            or portfolio.get("anchors") != len(passages)
            or len(portfolio.get("shapes", [])) != len(passages)
            or not supporting
            or any(not isinstance(item.get("variation_from_primary"), list) for item in supporting)
            or not any(item.get("variation_from_primary") for item in supporting)
            or "Choose one" not in str(human_style.get("selection_rule", ""))
        ):
            findings.append({"severity": "error", "code": "PACKET_STYLE_PORTFOLIO_INVALID", "target_id": target_id})
        bridge = payload.get("public_judgment_contract")
        target_role = payload.get("target", {}).get("role") if isinstance(payload.get("target"), dict) else None
        bridge_required = target_role in {"analysis", "model"}
        if bridge_required:
            questions = bridge.get("questions") if isinstance(bridge, dict) else None
            if (
                not isinstance(bridge, dict)
                or bridge.get("schema") != "mcm-section-public-judgment-contract/v1"
                or bridge.get("required") is not True
                or not isinstance(questions, list)
                or not questions
                or any(
                    not isinstance(item, dict)
                    or not item.get("basis_nodes")
                    or not item.get("mathematical_change_nodes")
                    or not isinstance(item.get("selected_route"), dict)
                    or not item["selected_route"].get("id")
                    or not item.get("local_requirements", {}).get("bridge_required_if_route_named")
                    for item in questions
                )
                or not bridge.get("policy", {}).get("unrecorded_model_comparison_story_forbidden")
            ):
                findings.append({"severity": "error", "code": "PACKET_PUBLIC_JUDGMENT_CONTRACT_INVALID", "target_id": target_id})
        elif bridge is not None and (
            not isinstance(bridge, dict)
            or bridge.get("schema") != "mcm-section-public-judgment-contract/v1"
        ):
            findings.append({"severity": "error", "code": "PACKET_PUBLIC_JUDGMENT_CONTRACT_INVALID", "target_id": target_id})
        contract = payload.get("drafting_contract") if isinstance(payload.get("drafting_contract"), dict) else {}
        required_flags = (
            "facts_from_current_problem_only", "read_primary_passage_and_context_before_writing",
            "copy_corpus_sentence_forbidden", "import_corpus_fact_model_number_or_conclusion_forbidden",
            "fixed_step_template_forbidden", "edit_against_current_draft_tex",
            "preserve_tex_commands_math_labels_citations",
            "choose_one_evidence_compatible_motion",
            "copy_surface_mix_from_multiple_passages_forbidden",
            "public_judgment_bridge_required_when_declared",
            "unrecorded_model_comparison_story_forbidden",
            "model_name_before_all_local_precursors_forbidden",
        )
        if any(contract.get(flag) is not True for flag in required_flags):
            findings.append({"severity": "error", "code": "PACKET_CONTRACT_WEAK", "target_id": target_id})
    errors = sum(item.get("severity") == "error" for item in findings)
    return {
        "schema": "mcm-section-drafting-packet-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "index": {"path": str(index_path), "sha256": sha256_file(index_path) if index_path.is_file() else None},
        "packets": len(records),
        "errors": errors,
        "warnings": 0,
        "findings": findings,
        "dependencies": [
            {
                "role": f"section-packet:{item.get('target_id')}",
                "path": str(Path(str(item.get("path", ""))).resolve()) if isinstance(item, dict) else "",
                "sha256": item.get("sha256") if isinstance(item, dict) else None,
            }
            for item in records
            if isinstance(item, dict)
        ],
        "interpretation": (
            "Passing proves that section packets are deterministic, source-bound, and contract-complete. "
            "It does not prove that a writer consumed them or that the resulting prose is natural."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--style-plan", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.brief, args.style_plan, args.index)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SECTION DRAFTING PACKETS AUDIT {report['status'].upper()} packets={report['packets']} errors={report['errors']}")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
