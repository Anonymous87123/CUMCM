#!/usr/bin/env python3
"""Bind current-problem evidence and corpus style references to TeX sections.

Public interface:
    python prepare_section_authoring_brief.py <main.tex> --problem-type A|B|C
        --style-plan style-retrieval-plan.json
        --workbench modeling-workbench.json
        --preflight reasoning-preflight.json
        --output section-authoring-brief.json --format text|json

The brief is an internal drafting input. It does not generate prose, expose a
hidden chain of thought, or permit facts from the 59-paper style corpus.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from audit_manuscript import read_tex_tree
from audit_reasoning_preflight import audit as audit_preflight
from audit_style_retrieval_plan import audit as audit_style_plan
from prepare_style_retrieval_plan import sha256_file


SCHEMA = "mcm-section-authoring-brief/v1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _input(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def _question_sort(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _style_anchor_ref(anchor: dict) -> dict:
    keys = (
        "id", "year", "problem_type", "paper", "page_start", "page_end",
        "section", "source", "index_source", "actions", "action_sequence",
        "opening_family", "closing_family", "formula_nearby", "visual_nearby",
        "models", "quality", "han_chars", "sentence_count", "cadence_band", "ending_action",
        "style_portfolio_rank",
    )
    return {key: anchor.get(key) for key in keys}


def _language_action_profile(
    anchors: list[dict],
    primary_anchor_id: str | None,
    primary_selection: dict | None,
) -> dict:
    valid = [item for item in anchors if isinstance(item, dict) and item.get("id")]
    primary = next(
        (item for item in valid if str(item.get("id")) == str(primary_anchor_id)),
        valid[0] if valid else None,
    )
    supporting = [item for item in valid if primary is None or item.get("id") != primary.get("id")]
    action_sequences: list[list[str]] = []
    seen_sequences: set[tuple[str, ...]] = set()
    for anchor in valid:
        raw = anchor.get("action_sequence")
        sequence = tuple(str(item) for item in raw) if isinstance(raw, list) else tuple()
        if sequence and sequence not in seen_sequences:
            seen_sequences.add(sequence)
            action_sequences.append(list(sequence))
    openings = Counter(
        str(item.get("opening_family")) for item in valid if item.get("opening_family")
    )
    closings = Counter(
        str(item.get("closing_family")) for item in valid if item.get("closing_family")
    )
    character_counts = [
        int(item.get("han_chars") or len(re.sub(r"\s+", "", str(item.get("text", "")))))
        for item in valid if str(item.get("text", "")).strip()
    ]
    sentence_counts = [int(item.get("sentence_count") or 0) for item in valid]
    cadence_bands = Counter(
        str(item.get("cadence_band")) for item in valid if item.get("cadence_band")
    )
    ending_actions = Counter(
        str(item.get("ending_action")) for item in valid if item.get("ending_action")
    )
    supporting_variations = []
    if primary:
        dimensions = (
            "action_sequence", "opening_family", "closing_family", "ending_action", "cadence_band",
            "paper", "formula_nearby", "visual_nearby",
        )
        for item in supporting:
            different = [
                key for key in dimensions
                if item.get(key) != primary.get(key)
            ]
            supporting_variations.append({"id": item["id"], "different_on": different})
    return {
        "primary_anchor_id": primary.get("id") if primary else None,
        "primary_action_sequence": (
            list(primary.get("action_sequence", []))
            if primary and isinstance(primary.get("action_sequence"), list) else []
        ),
        "primary_opening_family": primary.get("opening_family") if primary else None,
        "primary_closing_family": primary.get("closing_family") if primary else None,
        "primary_ending_action": primary.get("ending_action") if primary else None,
        "primary_han_chars": primary.get("han_chars") if primary else None,
        "primary_sentence_count": primary.get("sentence_count") if primary else None,
        "primary_cadence_band": primary.get("cadence_band") if primary else None,
        "primary_selection": primary_selection,
        "supporting_anchor_ids": [item["id"] for item in supporting],
        "observed_action_sequences": action_sequences,
        "opening_families": dict(sorted(openings.items())),
        "closing_families": dict(sorted(closings.items())),
        "ending_actions": dict(sorted(ending_actions.items())),
        "cadence_bands": dict(sorted(cadence_bands.items())),
        "formula_interface_anchor_ids": [item["id"] for item in valid if item.get("formula_nearby")],
        "visual_interface_anchor_ids": [item["id"] for item in valid if item.get("visual_nearby")],
        "paragraph_character_counts": character_counts,
        "sentence_counts": sentence_counts,
        "supporting_variations": supporting_variations,
        "context_anchor_ids": [
            item["id"] for item in valid
            if item.get("previous_context") or item.get("next_context")
        ],
        "use_rule": (
            "Read every bound paragraph in the style plan. Use the primary anchor for the section's main "
            "rhetorical motion and the others only to check variation, interfaces, and stopping points. "
            "Select actions supported by current-problem evidence; do not blend every observed sequence."
        ),
    }


def _question_plan(workbench: dict, preflight: dict, question_id: str) -> dict:
    question = next(
        item for item in workbench["questions"]
        if isinstance(item, dict) and str(item.get("id", "")).strip() == question_id
    )
    approval = next(
        item for item in preflight["approvals"]
        if isinstance(item, dict) and str(item.get("question_id", "")).strip() == question_id
    )
    anchors_by_id = {
        item["id"]: item for item in question.get("anchors", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    targets_by_id = {
        item["id"]: item for item in question.get("targets", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    route = next(
        item for item in question.get("routes", [])
        if isinstance(item, dict) and item.get("status") == "selected"
    )
    alternative_routes = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "status": item.get("status"),
            "terms": item.get("terms", []),
            "anchor_ids": item.get("anchor_ids", []),
            "target_ids": item.get("target_ids", []),
            "evidence_ids": item.get("evidence_ids", []),
            "evidence_ref": item.get("evidence_ref"),
            "reason": item.get("reason"),
        }
        for item in question.get("routes", [])
        if isinstance(item, dict) and item.get("status") in {"rejected", "deferred"}
    ]
    selected_anchors = [anchors_by_id[item] for item in route["anchor_ids"]]
    selected_targets = [targets_by_id[item] for item in route["target_ids"]]
    source_ids = set(route["evidence_ids"])
    for anchor in selected_anchors:
        source_ids.update(anchor["source_ids"])
    for interpretation in question.get("interpretations", []):
        if isinstance(interpretation, dict):
            source_ids.update(
                item for item in interpretation.get("source_ids", [])
                if isinstance(item, str)
            )
    source_records = [
        {
            "id": item.get("id"),
            "role": item.get("role"),
            "path": item.get("path"),
            "sha256": item.get("sha256"),
        }
        for item in workbench["sources"]
        if isinstance(item, dict) and item.get("id") in source_ids
    ]
    return {
        "question_id": question_id,
        "current_problem_sources": source_records,
        "fact_anchors": selected_anchors,
        "mathematical_targets": selected_targets,
        "selected_route": route,
        "recorded_alternative_routes": alternative_routes,
        "declared_checks": question.get("checks", []),
        "result_interpretations": question.get("interpretations", []),
        "drafting_mode": question.get("drafting", {}),
        "human_preflight": {
            "reviewer": approval.get("reviewer"),
            "reviewer_kind": approval.get("reviewer_kind"),
            "basis_confirmation": approval.get("basis_confirmation"),
            "transition_confirmation": approval.get("transition_confirmation"),
            "change_trigger": approval.get("change_trigger"),
            "decision": approval.get("decision"),
        },
    }


def _public_judgment_contract(role: str, plans: list[dict]) -> dict:
    bridge_roles = {"analysis", "model"}
    question_contracts = []
    for plan in plans:
        route = plan.get("selected_route") if isinstance(plan.get("selected_route"), dict) else {}
        drafting = plan.get("drafting_mode") if isinstance(plan.get("drafting_mode"), dict) else {}
        mode = str(drafting.get("mode", ""))
        alternatives = [
            item for item in plan.get("recorded_alternative_routes", [])
            if isinstance(item, dict)
        ]
        interpretations = [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "observation_terms": item.get("observation_terms", []),
                "explanation_terms": item.get("explanation_terms", []),
                "source_ids": item.get("source_ids", []),
                "source_ref": item.get("source_ref"),
            }
            for item in plan.get("result_interpretations", [])
            if isinstance(item, dict)
        ]
        checks = [
            item for item in plan.get("declared_checks", [])
            if isinstance(item, dict)
        ]
        validation_checks = [
            item for item in checks
            if isinstance(item.get("terms"), list) and item.get("terms")
            and isinstance(item.get("result_terms"), list) and item.get("result_terms")
        ]
        basis_nodes = [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "terms": item.get("terms", []),
                "source_ref": item.get("source_ref"),
                "source_ids": item.get("source_ids", []),
            }
            for item in plan.get("fact_anchors", [])
            if isinstance(item, dict)
        ]
        target_nodes = [
            {
                "id": item.get("id"),
                "terms": item.get("terms", []),
                "source_ref": item.get("source_ref"),
            }
            for item in plan.get("mathematical_targets", [])
            if isinstance(item, dict)
        ]
        question_contracts.append({
            "question_id": plan.get("question_id"),
            "drafting_mode": mode,
            "basis_nodes": basis_nodes,
            "mathematical_change_nodes": target_nodes,
            "selected_route": {
                "id": route.get("id"),
                "name": route.get("name"),
                "terms": route.get("terms", []),
                "anchor_ids": route.get("anchor_ids", []),
                "target_ids": route.get("target_ids", []),
                "evidence_ids": route.get("evidence_ids", []),
                "evidence_ref": route.get("evidence_ref"),
            },
            "recorded_alternative_routes": alternatives,
            "result_interpretations": interpretations,
            "actual_checks": checks,
            "human_confirmation": plan.get("human_preflight", {}),
            "local_requirements": {
                "basis_term_required": role in bridge_roles,
                "mathematical_change_term_required": role in bridge_roles,
                "selected_route_term_required": role == "model",
                "bridge_required_if_route_named": role in bridge_roles,
                "order_rule": "route-cannot-precede-both-basis-and-mathematical-change",
                "minimum_basis_groups": 1 if role in bridge_roles else 0,
                "minimum_target_groups": 1 if role in bridge_roles else 0,
                "result_interpretation_required": role == "result" and bool(interpretations),
                "validation_conclusion_required": role == "validation" and bool(validation_checks),
                "model_comparison_guard": role in bridge_roles,
            },
        })
    required = bool(
        question_contracts and (
            role in bridge_roles
            or role == "result" and any(item.get("result_interpretations") for item in question_contracts)
            or role == "validation" and any(
                any(
                    check.get("terms") and check.get("result_terms")
                    for check in item.get("actual_checks", [])
                )
                for item in question_contracts
            )
        )
    )
    return {
        "schema": "mcm-section-public-judgment-contract/v1",
        "role": role,
        "section_local": True,
        "required": required,
        "questions": question_contracts,
        "policy": {
            "use_current_problem_terms_not_stock_model_praise": True,
            "unrecorded_model_comparison_story_forbidden": True,
            "recorded_alternative_must_be_named_when_comparison_is_claimed": True,
            "hidden_chain_of_thought_not_requested": True,
            "fixed_sentence_order_forbidden": True,
            "verbatim_human_confirmation_not_required": True,
        },
        "instruction": (
            "Expose only the local, fact-backed relation needed by this section. Before a model name appears, "
            "the prose must already expose either the problem fact or a mathematical relation derived for this "
            "question; the other node may occur where the actual explanation needs it. If no alternative route is "
            "recorded, do not invent a comparison story. Preserve the actual evidence order without rendering "
            "these fields as a fixed prose sequence."
        ),
    }


def _section_job(role: str) -> str:
    jobs = {
        "abstract": "Select only the problem route, numerical result, and check that the completed work supports.",
        "restatement": "Preserve the task objects, conditions, and requested outputs without importing solution claims.",
        "analysis": "Let a local fact, data feature, prior interface, or actual trial expose the mathematical issue before naming a method.",
        "assumptions": "Keep only assumptions that enter an equation, constraint, data scope, or interpretation boundary.",
        "symbols": "Define symbols used by the current equations and code; do not expand this into model exposition.",
        "model": "Move from the attached current-problem anchors to mathematical targets and then to the selected route in the order the work actually requires.",
        "solve": "Report the implemented computation, stopping rule, and output interface at the level supported by code or logs.",
        "result": "Use current result files to explain a change, exception, active constraint, or comparison; do not narrate every table cell.",
        "validation": "Name only the check that was actually run and state what it establishes and what it does not.",
        "sensitivity": "Tie the perturbation, fixed quantities, output change, and any decision switch to actual runs.",
        "evaluation": "Derive limitations and improvements from identified evidence, approximation, data, or computation limits.",
    }
    return jobs.get(role, "Write only what this section's current-problem evidence supports.")


def build_brief(
    main_tex: Path,
    problem_type: str,
    style_plan_path: Path,
    workbench_path: Path,
    preflight_path: Path,
) -> dict:
    main_tex = main_tex.resolve()
    style_plan_path = style_plan_path.resolve()
    workbench_path = workbench_path.resolve()
    preflight_path = preflight_path.resolve()
    findings: list[dict] = []
    try:
        style_plan = _load(style_plan_path)
        workbench = _load(workbench_path)
        preflight = _load(preflight_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "schema": SCHEMA,
            "status": "fail",
            "problem_type": problem_type,
            "errors": 1,
            "findings": [{"severity": "error", "code": "AUTHORING_BRIEF_INPUT_INVALID", "detail": str(exc)}],
        }

    style_report = audit_style_plan(main_tex, style_plan_path, problem_type)
    preflight_report = audit_preflight(workbench_path, preflight_path)
    if style_report.get("status") != "pass":
        findings.append({"severity": "error", "code": "AUTHORING_BRIEF_STYLE_PLAN_NOT_PASSING"})
    if preflight_report.get("status") != "pass":
        findings.append({"severity": "error", "code": "AUTHORING_BRIEF_PREFLIGHT_NOT_PASSING"})

    if findings:
        raw_tree = read_tex_tree(main_tex) if main_tex.is_file() else ""
        return {
            "schema": SCHEMA,
            "status": "fail",
            "problem_type": problem_type,
            "source": {
                "path": str(main_tex),
                "sha256": sha256_file(main_tex) if main_tex.is_file() else None,
                "tex_tree_sha256": hashlib.sha256(raw_tree.encode("utf-8")).hexdigest() if raw_tree else None,
            },
            "inputs": {
                "style_plan": _input(style_plan_path),
                "workbench": _input(workbench_path),
                "preflight": _input(preflight_path),
            },
            "dependency_audits": {
                "style_plan_status": style_report.get("status"),
                "preflight_status": preflight_report.get("status"),
            },
            "policy": {
                "facts_from_current_problem_only": True,
                "corpus_for_style_only": True,
                "human_preflight_required": True,
                "fixed_step_template_forbidden": True,
                "copying_forbidden": True,
                "brief_is_not_manuscript_prose": True,
            },
            "sections": [],
            "errors": len(findings),
            "warnings": 0,
            "findings": findings,
        }

    question_ids = sorted(
        {
            str(item.get("id", "")).strip()
            for item in workbench.get("questions", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        },
        key=_question_sort,
    )
    approved_ids = {
        str(item.get("question_id", "")).strip()
        for item in preflight.get("approvals", [])
        if isinstance(item, dict)
        and item.get("decision") == "approve"
        and item.get("reviewer_kind") == "human"
    }
    sections: list[dict] = []
    for target in style_plan.get("targets", []):
        if not isinstance(target, dict):
            continue
        question_id = target.get("question_id")
        attached_ids = [question_id] if isinstance(question_id, str) and question_id else question_ids
        missing = [item for item in attached_ids if item not in approved_ids]
        if missing:
            findings.append({
                "severity": "error",
                "code": "AUTHORING_BRIEF_QUESTION_NOT_HUMAN_APPROVED",
                "target_id": target.get("id"),
                "question_ids": missing,
            })
            plans: list[dict] = []
        else:
            plans = [_question_plan(workbench, preflight, item) for item in attached_ids]
        style_anchors = [item for item in target.get("anchors", []) if isinstance(item, dict)]
        sections.append({
            "target_id": target.get("id"),
            "title": target.get("title"),
            "line": target.get("line"),
            "role": target.get("role"),
            "question_id": question_id,
            "section_job": _section_job(str(target.get("role", ""))),
            "current_problem": {
                "scope": "question" if question_id else "all-approved-questions",
                "question_ids": attached_ids,
                "question_plans": plans,
            },
            "public_judgment_contract": _public_judgment_contract(
                str(target.get("role", "")), plans
            ),
            "human_style": {
                "style_plan_target_id": target.get("id"),
                "anchor_ids": [item.get("id") for item in style_anchors],
                "anchor_refs": [_style_anchor_ref(item) for item in style_anchors],
                "language_action_profile": _language_action_profile(
                    style_anchors,
                    str(target.get("primary_anchor_id")) if target.get("primary_anchor_id") else None,
                    target.get("primary_anchor_selection") if isinstance(target.get("primary_anchor_selection"), dict) else None,
                ),
                "style_portfolio_summary": target.get("style_portfolio_summary"),
                "read_full_text_from_style_plan": True,
                "observe": [
                    "fact entry and local judgment action",
                    "model/formula/figure interface",
                    "paragraph length variation and stopping point",
                ],
            },
            "drafting_guard": {
                "follow_local_evidence_order": True,
                "render_json_field_order_as_prose": False,
                "fixed_step_template_forbidden": True,
                "invented_comparison_or_trial_forbidden": True,
                "copy_style_anchor_sentence_forbidden": True,
                "import_style_anchor_fact_forbidden": True,
            },
        })

    raw_tree = read_tex_tree(main_tex)
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "problem_type": problem_type,
        "source": {
            "path": str(main_tex),
            "sha256": sha256_file(main_tex),
            "tex_tree_sha256": hashlib.sha256(raw_tree.encode("utf-8")).hexdigest(),
        },
        "inputs": {
            "style_plan": _input(style_plan_path),
            "workbench": _input(workbench_path),
            "preflight": _input(preflight_path),
        },
        "dependency_audits": {
            "style_plan_status": style_report.get("status"),
            "preflight_status": preflight_report.get("status"),
        },
        "policy": {
            "facts_from_current_problem_only": True,
            "corpus_for_style_only": True,
            "human_preflight_required": True,
            "fixed_step_template_forbidden": True,
            "copying_forbidden": True,
            "brief_is_not_manuscript_prose": True,
        },
        "sections": sections,
        "errors": errors,
        "warnings": 0,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--problem-type", choices=("A", "B", "C"), required=True)
    parser.add_argument("--style-plan", type=Path, required=True)
    parser.add_argument("--workbench", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build_brief(args.main_tex, args.problem_type, args.style_plan, args.workbench, args.preflight)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"SECTION AUTHORING BRIEF {report['status'].upper()} "
            f"sections={len(report.get('sections', []))} errors={report['errors']} "
            f"output={args.output.resolve()}"
        )
        for finding in report.get("findings", []):
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
