#!/usr/bin/env python3
"""Materialize one source-bound drafting packet for every writable section.

Public interface:
    python prepare_section_drafting_packets.py main.tex \
        --brief section-authoring-brief.json \
        --style-plan style-retrieval-plan.json \
        --output-dir drafting-packets --format text|json

Each packet is an internal model input. It combines current-problem evidence
with full human-corpus passages for one section; it is never manuscript prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_content_density import normalize_tex
from audit_manuscript import read_tex_tree
from audit_section_authoring_brief import audit as audit_brief
from prepare_style_retrieval_plan import section_target_records, sha256_file


SCHEMA = "mcm-section-drafting-packet/v1"
INDEX_SCHEMA = "mcm-section-drafting-packet-index/v1"
BUILDER_PATH = Path(__file__).resolve()


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _locked(path: Path) -> dict:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _variation_dimensions(primary: dict, anchor: dict) -> list[str]:
    dimensions = (
        "action_sequence", "opening_family", "closing_family", "ending_action", "cadence_band",
        "paper", "formula_nearby", "visual_nearby",
    )
    return [key for key in dimensions if anchor.get(key) != primary.get(key)]


def _passage(anchor: dict, role: str, primary: dict) -> dict:
    return {
        "reading_role": role,
        "id": anchor.get("id"),
        "year": anchor.get("year"),
        "problem_type": anchor.get("problem_type"),
        "paper": anchor.get("paper"),
        "page_start": anchor.get("page_start"),
        "page_end": anchor.get("page_end"),
        "section": anchor.get("section"),
        "source": anchor.get("source"),
        "index_source": anchor.get("index_source"),
        "quality": anchor.get("quality"),
        "score": anchor.get("score"),
        "actions": anchor.get("actions", []),
        "action_sequence": anchor.get("action_sequence", []),
        "opening_family": anchor.get("opening_family"),
        "closing_family": anchor.get("closing_family"),
        "ending_action": anchor.get("ending_action"),
        "han_chars": anchor.get("han_chars"),
        "sentence_count": anchor.get("sentence_count"),
        "cadence_band": anchor.get("cadence_band"),
        "style_portfolio_rank": anchor.get("style_portfolio_rank"),
        "variation_from_primary": [] if role == "primary" else _variation_dimensions(primary, anchor),
        "formula_nearby": anchor.get("formula_nearby"),
        "visual_nearby": anchor.get("visual_nearby"),
        "models": anchor.get("models", []),
        "previous_context": anchor.get("previous_context", []),
        "text": anchor.get("text"),
        "next_context": anchor.get("next_context", []),
    }


def build_packets(
    main_tex: Path,
    brief_path: Path,
    style_plan_path: Path,
) -> dict[str, dict]:
    main_tex = main_tex.resolve()
    brief_path = brief_path.resolve()
    style_plan_path = style_plan_path.resolve()
    brief = _load(brief_path)
    style_plan = _load(style_plan_path)
    problem_type = str(brief.get("problem_type", ""))
    brief_inputs = brief.get("inputs") if isinstance(brief.get("inputs"), dict) else {}
    workbench_path = Path(str(brief_inputs.get("workbench", {}).get("path", ""))).resolve()
    preflight_path = Path(str(brief_inputs.get("preflight", {}).get("path", ""))).resolve()
    validation = audit_brief(
        main_tex, brief_path, problem_type, style_plan_path, workbench_path, preflight_path
    )
    if validation.get("status") != "pass":
        raise ValueError(f"section authoring brief is not valid: {validation.get('findings', [])}")

    raw_tree = normalize_tex(read_tex_tree(main_tex))
    scope_rows = section_target_records(raw_tree)
    scopes = {
        f"T{index:02d}": {
            "title": item["title"],
            "role": item["role"],
            "visible_prose": item["visible_prose"],
            "tex_source": item["tex_source"],
            "line": item["line"],
            "question_id": item["question_id"],
        }
        for index, item in enumerate(scope_rows, 1)
    }
    style_targets = {
        str(item.get("id")): item
        for item in style_plan.get("targets", [])
        if isinstance(item, dict) and item.get("id")
    }
    packets: dict[str, dict] = {}
    for section in brief.get("sections", []):
        if not isinstance(section, dict):
            continue
        target_id = str(section.get("target_id", ""))
        target = style_targets.get(target_id)
        scope = scopes.get(target_id)
        if target is None or scope is None:
            raise ValueError(f"brief target is absent from current style plan or TeX tree: {target_id}")
        anchors = [item for item in target.get("anchors", []) if isinstance(item, dict)]
        primary_id = str(target.get("primary_anchor_id", ""))
        primary = next((item for item in anchors if str(item.get("id")) == primary_id), None)
        if primary is None:
            raise ValueError(f"primary style anchor is missing: {target_id} {primary_id}")
        ordered = [primary] + [item for item in anchors if item is not primary]
        passages = [
            _passage(item, "primary" if index == 0 else "supporting", primary)
            for index, item in enumerate(ordered)
        ]
        packets[target_id] = {
            "schema": SCHEMA,
            "target": {
                "id": target_id,
                "title": section.get("title"),
                "line": section.get("line"),
                "role": section.get("role"),
                "question_id": section.get("question_id"),
                "section_job": section.get("section_job"),
            },
            "current_draft": scope["visible_prose"],
            "current_draft_tex": scope["tex_source"],
            "current_draft_tex_sha256": hashlib.sha256(
                str(scope["tex_source"]).encode("utf-8")
            ).hexdigest(),
            "current_problem": section.get("current_problem"),
            "public_judgment_contract": section.get("public_judgment_contract"),
            "human_style": {
                "language_action_profile": section.get("human_style", {}).get("language_action_profile"),
                "style_portfolio_summary": section.get("human_style", {}).get("style_portfolio_summary"),
                "reading_order": [item.get("id") for item in ordered],
                "passages": passages,
                "selection_rule": (
                    "Choose one evidence-compatible rhetorical motion for this section. Use supporting passages "
                    "to see real alternatives in opening, action order, cadence, interfaces, or stopping point; "
                    "do not average their surfaces into a composite paragraph."
                ),
            },
            "drafting_contract": {
                "facts_from_current_problem_only": True,
                "read_primary_passage_and_context_before_writing": True,
                "read_supporting_passages_for_variation_not_blending": True,
                "choose_one_evidence_compatible_motion": True,
                "copy_surface_mix_from_multiple_passages_forbidden": True,
                "edit_against_current_draft_tex": True,
                "preserve_tex_commands_math_labels_citations": True,
                "preserve_actual_evidence_order": True,
                "fixed_step_template_forbidden": True,
                "invented_comparison_trial_or_failure_forbidden": True,
                "copy_corpus_sentence_forbidden": True,
                "import_corpus_fact_model_number_or_conclusion_forbidden": True,
                "public_judgment_bridge_required_when_declared": True,
                "unrecorded_model_comparison_story_forbidden": True,
                "model_name_before_all_local_precursors_forbidden": True,
                "hidden_chain_of_thought_not_requested": True,
                "output_scope": "target-section-only",
                "instruction": (
                    "Read this packet completely. Treat current_draft_tex as the exact structural authority "
                    "and use current_problem as the only factual authority. "
                    "Use the primary passage to observe one human rhetorical motion and the supporting "
                    "passages to check alternatives and stopping points. Draft or revise only the target "
                    "section in the actual TeX source. Do not translate packet field order into prose, and do "
                    "not force basis, mathematical change, method, result, and check into one repeated order."
                ),
            },
            "inputs": {
                "main_tex": _locked(main_tex),
                "brief": _locked(brief_path),
                "style_plan": _locked(style_plan_path),
                "workbench": _locked(workbench_path),
                "preflight": _locked(preflight_path),
                "builder": _locked(BUILDER_PATH),
            },
        }
    if not packets:
        raise ValueError("section authoring brief has no writable sections")
    return packets


def write_bundle(
    main_tex: Path,
    brief_path: Path,
    style_plan_path: Path,
    output_dir: Path,
) -> tuple[Path, dict]:
    output_dir = output_dir.resolve()
    index_path = output_dir / "packet-index.json"
    if index_path.exists() or (output_dir.exists() and any(output_dir.glob("T*.json"))):
        raise FileExistsError(f"drafting packet bundle already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(main_tex, brief_path, style_plan_path)
    records = []
    for target_id, payload in packets.items():
        path = output_dir / f"{target_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append({"target_id": target_id, **_locked(path)})
    index = {
        "schema": INDEX_SCHEMA,
        "status": "pass",
        "source": _locked(main_tex),
        "inputs": {
            "brief": _locked(brief_path),
            "style_plan": _locked(style_plan_path),
            "builder": _locked(BUILDER_PATH),
        },
        "packet_count": len(records),
        "packets": records,
        "interpretation": (
            "The bundle materializes complete section-local model inputs. It does not prove that a model "
            "read them, that generated prose is natural, or that the mathematics is correct."
        ),
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index_path, index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--style-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        index_path, report = write_bundle(
            args.main_tex, args.brief, args.style_plan, args.output_dir
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.format == "json":
            print(json.dumps({"schema": INDEX_SCHEMA, "status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"SECTION DRAFTING PACKETS FAIL: {exc}")
        return 1
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"SECTION DRAFTING PACKETS PASS packets={report['packet_count']} "
            f"index={index_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
