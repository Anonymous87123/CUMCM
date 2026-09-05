#!/usr/bin/env python3
"""Validate one source-bound role-evidence artifact.

The validator distinguishes an artifact that merely exists from evidence that
has the expected type, producer, source binding and minimum useful structure.
It cannot prove that a human judgment is good, but it prevents arbitrary text
files and unrelated JSON from completing an AIGC portfolio role.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "aigc-role-evidence-audit/v1"
MANUAL_SCHEMA = "aigc-role-evidence/v1"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

# Prompt-only content Skills do not have executable report generators.  Their
# evidence therefore uses one common envelope plus a type-specific collection.
# Requiring different fields keeps a renamed generic note from satisfying every
# role in the chain.
MANUAL_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "authority-map": ("authorities", ("id", "path", "sha256", "purpose")),
    "whole-argument-map": ("sections", ("id", "claim", "evidence_refs")),
    "scene-dispatch": ("decisions", ("selected_scene", "reason", "excluded_scenes")),
    "fact-lock": ("facts", ("id", "value", "source_refs")),
    "rule-findings": ("findings", ("rule_id", "location", "severity", "disposition")),
    "gate-summary": ("gates", ("gate_id", "status", "evidence_refs")),
    "problem-fact-map": ("questions", ("question_id", "facts", "mathematical_effect", "source_refs")),
    "claim-ledger": ("claims", ("id", "statement", "status", "source_refs")),
    "parameter-ledger": ("parameters", ("symbol", "value", "unit", "source_refs")),
    "protocol-ledger": ("protocols", ("id", "operation", "order", "implementation_ref")),
    "equation-code-ledger": ("mappings", ("equation", "code_ref", "variables")),
    "quantitative-reconciliation": ("checks", ("id", "manuscript_value", "result_value", "status")),
    "novelty-ledger": ("novelties", ("id", "baseline", "delta", "evidence_refs")),
    "claim-evidence-matrix": ("claims", ("id", "claim", "evidence_refs", "strength")),
    "proof-citation-version-gates": ("gates", ("gate_id", "status", "evidence_refs")),
    "source-segment-map": ("segments", ("id", "source_ref", "text_role", "confidence")),
    "fact-symbol-lock": ("symbols", ("symbol", "meaning", "domain", "source_refs")),
    "teaching-spine": ("steps", ("id", "prompt", "decisive_step", "answer")),
    "mathematics-answer-gates": ("gates", ("gate_id", "status", "evidence_refs")),
    "teaching-readthrough": ("observations", ("location", "issue", "disposition")),
    "document-map": ("documents", ("id", "source_ref", "working_ref", "mapping_status")),
    "diff-report": ("changes", ("location", "before_ref", "after_ref", "disposition")),
    "deployment-record": ("deployments", ("id", "target", "status", "evidence_refs")),
    "step-trace": ("steps", ("id", "action", "input_ref", "output_ref")),
    "comparison-report": ("comparisons", ("id", "variants", "criteria", "decision")),
    "change-report": ("changes", ("location", "before_ref", "after_ref", "reason")),
    "source-hash": ("sources", ("path", "sha256", "role")),
}

NATIVE_MCM_RULES = {
    "modeling-workbench": ("mcm-modeling-workbench-audit/v1", "pass"),
    "reasoning-preflight": ("mcm-reasoning-preflight-audit/v1", "pass"),
    "judgment-ledger": ("mcm-public-judgment-ledger-audit/v1", "pass"),
    "style-retrieval-plan": ("mcm-style-retrieval-audit/v1", "pass"),
    "section-authoring-brief": ("mcm-section-authoring-brief-audit/v1", "pass"),
    "section-drafting-packets": ("mcm-section-drafting-packet-audit/v1", "pass"),
    "section-drafting-usage": ("mcm-section-drafting-usage-audit/v1", "pass"),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _validated_input_hash(report: dict[str, Any], key: str, errors: list[str]) -> str | None:
    item = report.get("inputs", {}).get(key)
    if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
        errors.append(f"NATIVE_EVIDENCE_INPUT_MISSING:{key}")
        return None
    path = Path(str(item["path"])).resolve()
    declared = str(item["sha256"])
    if not path.is_file() or not HEX64.fullmatch(declared) or _sha256_file(path) != declared:
        errors.append(f"NATIVE_EVIDENCE_INPUT_INVALID:{key}")
        return None
    return declared.lower()


def _validate_manual(
    report: dict[str, Any], evidence_type: str, provider: str, role: str,
    source_sha256: str, candidate_id: str | None, candidate_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != MANUAL_SCHEMA:
        errors.append("MANUAL_EVIDENCE_SCHEMA_MISMATCH")
    if report.get("evidence_type") != evidence_type:
        errors.append("MANUAL_EVIDENCE_TYPE_MISMATCH")
    if report.get("provider") != provider:
        errors.append("MANUAL_EVIDENCE_PROVIDER_MISMATCH")
    if report.get("role") != role:
        errors.append("MANUAL_EVIDENCE_ROLE_MISMATCH")
    if report.get("status") != "pass":
        errors.append("MANUAL_EVIDENCE_NOT_PASS")
    if report.get("authority_source_sha256") != source_sha256:
        errors.append("MANUAL_EVIDENCE_SOURCE_MISMATCH")
    if candidate_sha256 is not None:
        if report.get("candidate_id") != candidate_id:
            errors.append("MANUAL_EVIDENCE_CANDIDATE_ID_MISMATCH")
        if report.get("candidate_sha256") != candidate_sha256:
            errors.append("MANUAL_EVIDENCE_CANDIDATE_HASH_MISMATCH")
    execution = report.get("execution")
    if not isinstance(execution, dict) or not _present(execution.get("run_id")):
        errors.append("MANUAL_EVIDENCE_EXECUTION_MISSING")
    elif execution.get("mode") in {None, "", "pending", "template", "detector_only"}:
        errors.append("MANUAL_EVIDENCE_EXECUTION_MODE_INVALID")
    inputs = report.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append("MANUAL_EVIDENCE_INPUTS_MISSING")
    else:
        bound_hashes: set[str] = set()
        for index, item in enumerate(inputs):
            if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
                errors.append(f"MANUAL_EVIDENCE_INPUT_INVALID:{index}")
                continue
            path = Path(str(item["path"])).resolve()
            declared = str(item["sha256"])
            if not path.is_file():
                errors.append(f"MANUAL_EVIDENCE_INPUT_MISSING:{index}")
            elif not HEX64.fullmatch(declared) or _sha256_file(path) != declared:
                errors.append(f"MANUAL_EVIDENCE_INPUT_HASH_MISMATCH:{index}")
            else:
                bound_hashes.add(declared.lower())
        if source_sha256.lower() not in bound_hashes:
            errors.append("MANUAL_EVIDENCE_AUTHORITY_INPUT_NOT_BOUND")
        if candidate_sha256 is not None and candidate_sha256.lower() not in bound_hashes:
            errors.append("MANUAL_EVIDENCE_CANDIDATE_INPUT_NOT_BOUND")
    spec = MANUAL_SPECS.get(evidence_type)
    if spec is None:
        errors.append("MANUAL_EVIDENCE_TYPE_UNSUPPORTED")
        return errors
    collection_name, required_fields = spec
    records = report.get(collection_name)
    if not isinstance(records, list) or not records:
        errors.append(f"MANUAL_EVIDENCE_COLLECTION_EMPTY:{collection_name}")
        return errors
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            errors.append(f"MANUAL_EVIDENCE_RECORD_INVALID:{collection_name}:{index}")
            continue
        for field in required_fields:
            if not _present(item.get(field)):
                errors.append(f"MANUAL_EVIDENCE_FIELD_MISSING:{collection_name}:{index}:{field}")
            elif field == "sha256" and not HEX64.fullmatch(str(item.get(field))):
                errors.append(f"MANUAL_EVIDENCE_SHA256_INVALID:{collection_name}:{index}:{field}")
            elif (
                field.endswith("_refs")
                or field in {"facts", "variables", "variants", "criteria", "excluded_scenes"}
            ) and not isinstance(item.get(field), list):
                errors.append(f"MANUAL_EVIDENCE_LIST_FIELD_INVALID:{collection_name}:{index}:{field}")
    return errors


def _validate_adapter(
    report: dict[str, Any], *, action: str, provider: str,
    source_sha256: str | None = None, candidate_sha256: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != "aigc-adapter-run/v1":
        errors.append("ADAPTER_EVIDENCE_SCHEMA_MISMATCH")
    if report.get("action") != action:
        errors.append("ADAPTER_EVIDENCE_ACTION_MISMATCH")
    package = str(report.get("package", ""))
    normalized_provider = re.sub(r"[^a-z0-9]+", "", provider.casefold())
    normalized_package = re.sub(r"[^a-z0-9]+", "", package.casefold())
    if not (
        normalized_provider == normalized_package
        or normalized_provider in normalized_package
        or normalized_package in normalized_provider
    ):
        errors.append("ADAPTER_EVIDENCE_PROVIDER_MISMATCH")
    if report.get("status") not in {"pass", "ready"}:
        errors.append("ADAPTER_EVIDENCE_NOT_PASS")
    if source_sha256 is not None and report.get("source", {}).get("sha256") != source_sha256:
        errors.append("ADAPTER_EVIDENCE_SOURCE_MISMATCH")
    if candidate_sha256 is not None and report.get("candidate", {}).get("sha256") != candidate_sha256:
        errors.append("ADAPTER_EVIDENCE_CANDIDATE_MISMATCH")
    return errors


def audit(
    artifact: Path, evidence_type: str, provider: str, role: str,
    source_sha256: str, candidate_id: str | None = None,
    candidate_sha256: str | None = None,
) -> dict[str, Any]:
    artifact = artifact.resolve()
    errors: list[str] = []
    report = _load_json(artifact)

    if evidence_type in {"candidate-file", "export-artifact"}:
        if not artifact.is_file() or artifact.stat().st_size == 0:
            errors.append("BINARY_OR_DOCUMENT_ARTIFACT_EMPTY")
        if evidence_type == "candidate-file" and candidate_sha256 is None:
            errors.append("CANDIDATE_FILE_TARGET_MISSING")
        if evidence_type == "export-artifact" and artifact.suffix.casefold() not in {
            ".docx", ".tex", ".pdf", ".md", ".markdown"
        }:
            errors.append("EXPORT_ARTIFACT_FORMAT_UNSUPPORTED")
    elif report is None:
        errors.append("EVIDENCE_JSON_REQUIRED")
    elif evidence_type == "change-report" and provider == "humanize-academic-chinese":
        # The Humanize inline/long validator binds this file to its native run.
        pass
    elif evidence_type in MANUAL_SPECS:
        errors.extend(_validate_manual(
            report, evidence_type, provider, role, source_sha256,
            candidate_id, candidate_sha256,
        ))
    elif evidence_type in NATIVE_MCM_RULES:
        schema, status = NATIVE_MCM_RULES[evidence_type]
        if report.get("schema") != schema:
            errors.append(f"NATIVE_EVIDENCE_SCHEMA_MISMATCH:{evidence_type}")
        if report.get("status") != status or report.get("errors") not in {0, None}:
            errors.append(f"NATIVE_EVIDENCE_NOT_PASS:{evidence_type}")
        if evidence_type == "reasoning-preflight" and not (
            isinstance(report.get("questions"), int)
            and report.get("questions", 0) > 0
            and report.get("questions") == report.get("approvals")
        ):
            errors.append("REASONING_PREFLIGHT_COVERAGE_INCOMPLETE")
        if evidence_type == "modeling-workbench" and report.get("workbench_questions", 0) <= 0:
            errors.append("MODELING_WORKBENCH_COVERAGE_EMPTY")
        if evidence_type == "judgment-ledger" and not (
            report.get("ledger_questions", 0) > 0
            and report.get("ledger_questions") == report.get("manuscript_questions")
        ):
            errors.append("JUDGMENT_LEDGER_COVERAGE_INCOMPLETE")
        if evidence_type == "modeling-workbench":
            main_sha = _validated_input_hash(report, "main_tex", errors)
            _validated_input_hash(report, "workbench", errors)
            if main_sha is not None and main_sha != source_sha256.lower():
                errors.append("MODELING_WORKBENCH_SOURCE_MISMATCH")
        elif evidence_type == "reasoning-preflight":
            _validated_input_hash(report, "workbench", errors)
            _validated_input_hash(report, "approval", errors)
        elif evidence_type == "judgment-ledger":
            main_sha = _validated_input_hash(report, "main_tex", errors)
            _validated_input_hash(report, "ledger", errors)
            if main_sha is not None and main_sha != source_sha256.lower():
                errors.append("JUDGMENT_LEDGER_SOURCE_MISMATCH")
        elif evidence_type == "style-retrieval-plan":
            manuscript = report.get("manuscript")
            if not isinstance(manuscript, dict) or manuscript.get("sha256") != source_sha256.lower():
                errors.append("STYLE_RETRIEVAL_SOURCE_MISMATCH")
            if not isinstance(report.get("target_count"), int) or report.get("target_count", 0) <= 0:
                errors.append("STYLE_RETRIEVAL_TARGET_COVERAGE_EMPTY")
            if not isinstance(report.get("reserved_records_excluded"), int) or report.get("reserved_records_excluded", 0) <= 0:
                errors.append("STYLE_RETRIEVAL_HOLDOUT_POLICY_MISSING")
            if report.get("minimum_distinct_papers") != 2:
                errors.append("STYLE_RETRIEVAL_DIVERSITY_POLICY_MISSING")
        elif evidence_type == "section-authoring-brief":
            manuscript = report.get("manuscript")
            if not isinstance(manuscript, dict) or manuscript.get("sha256") != source_sha256.lower():
                errors.append("SECTION_AUTHORING_BRIEF_SOURCE_MISMATCH")
            if not isinstance(report.get("sections"), int) or report.get("sections", 0) <= 0:
                errors.append("SECTION_AUTHORING_BRIEF_COVERAGE_EMPTY")
            for key in ("brief", "style_plan", "workbench", "preflight"):
                _validated_input_hash(report, key, errors)
        elif evidence_type == "section-drafting-packets":
            if not isinstance(report.get("packets"), int) or report.get("packets", 0) <= 0:
                errors.append("SECTION_DRAFTING_PACKETS_COVERAGE_EMPTY")
            index = report.get("index")
            if not isinstance(index, dict) or not index.get("path") or not index.get("sha256"):
                errors.append("SECTION_DRAFTING_PACKETS_INDEX_MISSING")
            else:
                index_path = Path(str(index["path"])).resolve()
                if not index_path.is_file() or _sha256_file(index_path) != str(index["sha256"]):
                    errors.append("SECTION_DRAFTING_PACKETS_INDEX_INVALID")
                else:
                    try:
                        index_payload = json.loads(index_path.read_text(encoding="utf-8-sig"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        errors.append("SECTION_DRAFTING_PACKETS_INDEX_JSON_INVALID")
                    else:
                        if not isinstance(index_payload, dict) or index_payload.get("schema") != "mcm-section-drafting-packet-index/v1":
                            errors.append("SECTION_DRAFTING_PACKETS_INDEX_SCHEMA_MISMATCH")
                        if not isinstance(index_payload, dict) or index_payload.get("status") != "pass":
                            errors.append("SECTION_DRAFTING_PACKETS_INDEX_NOT_PASS")
                        records = index_payload.get("packets") if isinstance(index_payload, dict) else None
                        if not isinstance(records, list) or not records or index_payload.get("packet_count") != len(records):
                            errors.append("SECTION_DRAFTING_PACKETS_INDEX_COVERAGE_INVALID")
                            records = []
                        if report.get("packets") != len(records):
                            errors.append("SECTION_DRAFTING_PACKETS_REPORT_COUNT_MISMATCH")
                        source = index_payload.get("source") if isinstance(index_payload, dict) else None
                        if not isinstance(source, dict) or source.get("sha256") != source_sha256.lower():
                            errors.append("SECTION_DRAFTING_PACKETS_SOURCE_MISMATCH")
                        for item in records:
                            if not isinstance(item, dict):
                                errors.append("SECTION_DRAFTING_PACKETS_RECORD_INVALID")
                                continue
                            packet_path = Path(str(item.get("path", ""))).resolve()
                            if not packet_path.is_file() or _sha256_file(packet_path) != item.get("sha256"):
                                errors.append("SECTION_DRAFTING_PACKETS_FILE_INVALID")
                                continue
                            try:
                                packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
                            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                                errors.append("SECTION_DRAFTING_PACKETS_JSON_INVALID")
                                continue
                            if not isinstance(packet, dict) or packet.get("schema") != "mcm-section-drafting-packet/v1":
                                errors.append("SECTION_DRAFTING_PACKETS_SCHEMA_MISMATCH")
                                continue
                            if packet.get("target", {}).get("id") != item.get("target_id"):
                                errors.append("SECTION_DRAFTING_PACKETS_TARGET_MISMATCH")
                            target_payload = packet.get("target") if isinstance(packet.get("target"), dict) else {}
                            if target_payload.get("role") in {"analysis", "model"}:
                                bridge = packet.get("public_judgment_contract")
                                bridge_questions = bridge.get("questions") if isinstance(bridge, dict) else None
                                if (
                                    not isinstance(bridge, dict)
                                    or bridge.get("schema") != "mcm-section-public-judgment-contract/v1"
                                    or bridge.get("required") is not True
                                    or not isinstance(bridge_questions, list)
                                    or not bridge_questions
                                ):
                                    errors.append("SECTION_DRAFTING_PACKETS_PUBLIC_JUDGMENT_CONTRACT_INVALID")
                            tex_source = packet.get("current_draft_tex")
                            if (
                                not isinstance(tex_source, str)
                                or not tex_source.strip()
                                or packet.get("current_draft_tex_sha256")
                                != hashlib.sha256(tex_source.encode("utf-8")).hexdigest()
                            ):
                                errors.append("SECTION_DRAFTING_PACKETS_TEX_SCOPE_INVALID")
                            current_problem = packet.get("current_problem")
                            if not isinstance(current_problem, dict) or not current_problem.get("question_ids"):
                                errors.append("SECTION_DRAFTING_PACKETS_FACTS_EMPTY")
                            human_style = packet.get("human_style")
                            passages = human_style.get("passages") if isinstance(human_style, dict) else None
                            if not isinstance(passages, list) or not passages or passages[0].get("reading_role") != "primary" or not str(passages[0].get("text") or "").strip():
                                errors.append("SECTION_DRAFTING_PACKETS_PRIMARY_PASSAGE_MISSING")
                            portfolio = human_style.get("style_portfolio_summary") if isinstance(human_style, dict) else None
                            supporting = passages[1:] if isinstance(passages, list) else []
                            if (
                                not isinstance(portfolio, dict)
                                or portfolio.get("selection") != "relevance-bounded-style-portfolio"
                                or portfolio.get("anchors") != len(passages or [])
                                or not supporting
                                or not any(
                                    isinstance(item, dict) and item.get("variation_from_primary")
                                    for item in supporting
                                )
                                or "Choose one" not in str(human_style.get("selection_rule", ""))
                            ):
                                errors.append("SECTION_DRAFTING_PACKETS_STYLE_PORTFOLIO_INVALID")
                            contract = packet.get("drafting_contract")
                            required_flags = (
                                "facts_from_current_problem_only",
                                "read_primary_passage_and_context_before_writing",
                                "edit_against_current_draft_tex",
                                "preserve_tex_commands_math_labels_citations",
                                "fixed_step_template_forbidden",
                                "copy_corpus_sentence_forbidden",
                                "import_corpus_fact_model_number_or_conclusion_forbidden",
                                "choose_one_evidence_compatible_motion",
                                "copy_surface_mix_from_multiple_passages_forbidden",
                            )
                            if not isinstance(contract, dict) or any(contract.get(flag) is not True for flag in required_flags):
                                errors.append("SECTION_DRAFTING_PACKETS_CONTRACT_WEAK")
        elif evidence_type == "section-drafting-usage":
            if not isinstance(report.get("sections"), int) or report.get("sections", 0) <= 0:
                errors.append("SECTION_DRAFTING_USAGE_COVERAGE_EMPTY")
            source = report.get("source")
            if not isinstance(source, dict) or source.get("sha256") != source_sha256.lower():
                errors.append("SECTION_DRAFTING_USAGE_SOURCE_MISMATCH")
            else:
                source_path = Path(str(source.get("path", ""))).resolve()
                if not source_path.is_file() or _sha256_file(source_path) != source_sha256.lower():
                    errors.append("SECTION_DRAFTING_USAGE_SOURCE_INVALID")
            candidate = report.get("candidate")
            if not isinstance(candidate, dict) or not candidate.get("path") or not candidate.get("sha256"):
                errors.append("SECTION_DRAFTING_USAGE_CANDIDATE_MISSING")
            else:
                candidate_path = Path(str(candidate["path"])).resolve()
                if not candidate_path.is_file() or _sha256_file(candidate_path) != candidate.get("sha256"):
                    errors.append("SECTION_DRAFTING_USAGE_CANDIDATE_INVALID")
            packet_index = report.get("packet_index")
            if not isinstance(packet_index, dict) or not packet_index.get("path") or not packet_index.get("sha256"):
                errors.append("SECTION_DRAFTING_USAGE_PACKET_INDEX_MISSING")
            else:
                packet_index_path = Path(str(packet_index["path"])).resolve()
                if not packet_index_path.is_file() or _sha256_file(packet_index_path) != packet_index.get("sha256"):
                    errors.append("SECTION_DRAFTING_USAGE_PACKET_INDEX_INVALID")
    elif evidence_type == "content-density-report":
        if report.get("status") != "pass" or report.get("errors") not in {0, None}:
            errors.append("CONTENT_DENSITY_NOT_PASS")
        body = report.get("body")
        if not isinstance(body, dict) or body.get("paragraphs", 0) <= 0 or body.get("han_chars", 0) <= 0:
            errors.append("CONTENT_DENSITY_BODY_EMPTY")
        if not isinstance(report.get("questions"), list) or not report.get("questions"):
            errors.append("CONTENT_DENSITY_QUESTION_COVERAGE_EMPTY")
        source = report.get("source")
        if not isinstance(source, dict) or source.get("sha256") != source_sha256:
            errors.append("CONTENT_DENSITY_SOURCE_MISMATCH")
        elif not Path(str(source.get("path", ""))).is_file() or _sha256_file(Path(str(source["path"]))) != source_sha256:
            errors.append("CONTENT_DENSITY_SOURCE_INVALID")
    elif evidence_type == "manuscript-audit":
        if report.get("schema_version") != 1:
            errors.append("MANUSCRIPT_AUDIT_SCHEMA_MISMATCH")
        if report.get("status") != "PASS" or report.get("errors") != 0:
            errors.append("MANUSCRIPT_AUDIT_NOT_PASS")
        source = report.get("source")
        if not isinstance(source, dict) or source.get("sha256") != source_sha256:
            errors.append("MANUSCRIPT_AUDIT_SOURCE_MISMATCH")
        elif not Path(str(source.get("path", ""))).is_file() or _sha256_file(Path(str(source["path"]))) != source_sha256:
            errors.append("MANUSCRIPT_AUDIT_SOURCE_INVALID")
    elif evidence_type == "candidate-task":
        if report.get("schema") != "aigc-candidate-task/v1":
            errors.append("CANDIDATE_TASK_SCHEMA_MISMATCH")
        if report.get("source_sha256") != source_sha256:
            errors.append("CANDIDATE_TASK_SOURCE_MISMATCH")
        if report.get("human_review_required") is not True:
            errors.append("CANDIDATE_TASK_REVIEW_FLAG_MISSING")
    elif evidence_type == "candidate-verification":
        errors.extend(_validate_adapter(
            report, action="verify-candidate", provider=provider,
            source_sha256=source_sha256, candidate_sha256=candidate_sha256,
        ))
    elif evidence_type == "workbench-plan":
        target_sha = (
            candidate_sha256
            if role in {"reviewer", "workbench"} and candidate_sha256
            else source_sha256
        )
        errors.extend(_validate_adapter(
            report, action="workbench-plan", provider=provider,
            source_sha256=target_sha,
        ))
        if report.get("plan", {}).get("serial_rewrite_forbidden") is not True:
            errors.append("WORKBENCH_SERIAL_REWRITE_BOUNDARY_MISSING")
    elif evidence_type == "audit-report":
        # Humanize academic uses a stronger validator in the orchestrator.
        if report.get("schema") == "aigc-academic-candidate-audit/v1":
            if report.get("status") != "pass":
                errors.append("ACADEMIC_AUDIT_NOT_PASS")
        else:
            target_sha = candidate_sha256 if role in {"reviewer", "workbench"} and candidate_sha256 else source_sha256
            errors.extend(_validate_adapter(
                report, action="audit", provider=provider,
                source_sha256=target_sha,
            ))
    elif evidence_type == "native-run-report":
        # Humanize native runs have dedicated source-tree revalidation.  Other
        # native roles must at least provide an executed adapter audit bound to
        # the reviewed target.
        if provider == "humanize-academic-chinese":
            pass
        else:
            target_sha = candidate_sha256 if role in {"reviewer", "workbench"} and candidate_sha256 else source_sha256
            errors.extend(_validate_adapter(
                report, action="audit", provider=provider,
                source_sha256=target_sha,
            ))
            if report.get("native_executed") is not True:
                errors.append("NATIVE_RUN_NOT_EXECUTED")
    else:
        errors.append("EVIDENCE_TYPE_WITHOUT_VALIDATOR")

    return {
        "schema": SCHEMA,
        "status": "pass" if not errors else "fail",
        "artifact": str(artifact),
        "evidence_type": evidence_type,
        "provider": provider,
        "role": role,
        "authority_source_sha256": source_sha256,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--evidence-type", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--candidate-id")
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    result = audit(
        args.artifact, args.evidence_type, args.provider, args.role,
        args.source_sha256, args.candidate_id, args.candidate_sha256,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"ROLE EVIDENCE {result['status'].upper()} "
            f"provider={args.provider} role={args.role} type={args.evidence_type}"
        )
        for error in result["errors"]:
            print(f"[ERROR] {error}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
