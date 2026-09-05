#!/usr/bin/env python3
"""Build a complete-role plan for the local AIGC writing portfolio.

Public interface:
    python route_aigc_tools.py --document-type TYPE --intent INTENT
        [--document-format FORMAT] [--scope document|local]
        [--requested-editor NAME] [--requested-reviewer NAME]
        [--requested-app NAME] [--format text|json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DOCUMENT_TYPES = (
    "mcm",
    "modeling",
    "research",
    "course-notes",
    "academic-mixed",
    "academic-en",
    "medical-en",
    "technical",
    "general-en",
    "general-zh",
    "external-app",
)
INTENTS = ("draft", "generate", "audit", "rewrite", "compare")
DOCUMENT_FORMATS = ("tex", "markdown", "docx", "txt", "plain", "pdf")
EDITORS = (
    "humanize-academic-chinese",
    "baibai-aigc",
    "academic-humanizer",
    "humanizer-medical-academic",
    "humanizer",
    "humanizer-zh",
    "humanizer-brandonwise",
    "humanizer-voice-profile",
    "humanize-chinese-copy-lab",
    "humanize-english-editor",
    "patina",
)
REVIEWERS = ("ai-check", "patina", "humanizer-brandonwise")
APPLICATIONS = (
    "AI-Cleaner",
    "AI-content-detector",
    "AI_paper",
    "FYADR",
    "BypassAIGC",
    "GankAIGC",
    "ai-humanizer",
    "humanize-text",
    "humanize-ai",
    "humanize-main-Tiany",
)
CHINESE_ACADEMIC_TYPES = {"mcm", "modeling", "research", "course-notes", "academic-mixed"}
ENGLISH_ACADEMIC_TYPES = {"academic-en", "medical-en"}
ACADEMIC_TYPES = CHINESE_ACADEMIC_TYPES | ENGLISH_ACADEMIC_TYPES


SCENE_CONFIG = {
    "mcm": {
        "scene": "MODELING",
        "content": [
            ("competition-genre", "mcm-cup-standard-write", "complete CUMCM A/B/C manuscript responsibility"),
            ("model-integrity", "deai-modeling-writing", "complete model-code-result and protocol gates"),
        ],
        "final_gates": [
            "generation-input-lock", "evidence-bundle", "mcm-manuscript", "model-code-result", "result-sync", "math-semantics",
            "reproducibility", "style-retrieval-plan", "section-authoring-brief", "section-drafting-packets", "section-drafting-usage", "judgment-ledger", "public-judgment-bridges", "public-reasoning-scaffold", "content-density",
            "human-blind-selection-v2", "xelatex-compile", "rendered-page-review",
        ],
    },
    "modeling": {
        "scene": "MODELING",
        "content": [("modeling-owner", "deai-modeling-writing", "complete modeling and engineering responsibility")],
        "final_gates": ["model-code-result", "protocol", "numerical-claims", "document-integrity"],
    },
    "research": {
        "scene": "RESEARCH",
        "content": [("research-owner", "deai-research-writing", "complete research, evidence, proof, and novelty responsibility")],
        "final_gates": ["claim-evidence", "proof", "citation-alignment", "version-reconciliation", "document-integrity"],
    },
    "course-notes": {
        "scene": "COURSE",
        "content": [("course-owner", "deai-course-notes", "complete teaching, source-identity, derivation, and answer responsibility")],
        "final_gates": ["source-identity", "mathematics", "answer-identity", "teaching-structure", "document-integrity"],
    },
    "academic-mixed": {
        "scene": "AUTO",
        "content": [
            ("conditional-modeling-owner", "deai-modeling-writing", "complete responsibility for MOD segments"),
            ("conditional-research-owner", "deai-research-writing", "complete responsibility for RES segments"),
            ("conditional-course-owner", "deai-course-notes", "complete responsibility for NOTE segments"),
        ],
        "final_gates": ["shared-fact-lock", "segment-gates", "cross-segment-versions", "document-integrity"],
    },
    "academic-en": {
        "scene": "ENGLISH_ACADEMIC",
        "content": [("research-integrity", "deai-research-writing", "complete claim, evidence, citation, and version responsibility")],
        "final_gates": ["claim-evidence", "citation-alignment", "version-reconciliation", "document-integrity"],
    },
    "medical-en": {
        "scene": "MEDICAL_ENGLISH",
        "content": [("research-integrity", "deai-research-writing", "complete claim, evidence, citation, and version responsibility")],
        "final_gates": ["claim-evidence", "citation-alignment", "construct-consistency", "document-integrity"],
    },
}


APP_CONFIG = {
    "AI-Cleaner": {
        "role": "diagnostic-laboratory",
        "responsibility": "run the complete local report and diff workbench; never write the authority file",
    },
    "AI-content-detector": {
        "role": "english-pdf-diagnostic-workbench",
        "responsibility": "run sentence analysis and annotated-PDF review as advisory evidence only",
    },
    "AI_paper": {
        "role": "manual-review-workspace",
        "responsibility": "run grammar, format, annotation, project history, and export under manual adoption",
        "embedded_capability_plan_required": True,
        "embedded_capability_catalog": "references/folder-utilization.json",
        "embedded_activation_command": "python scripts/run_aigc_adapter.py --package AI_paper --action workbench-plan --document-type mcm --format json",
        "embedded_scope": "activate only scene-matched workbench units; no serial rewrite and no maintenance/research unit as CUMCM authority",
    },
    "FYADR": {
        "role": "document-governance",
        "responsibility": "run DOCX/TXT snapshot, body map, block review, and export gate",
    },
    "BypassAIGC": {
        "role": "legacy-regression",
        "responsibility": "run compatibility and old two-stage behavior comparison only",
    },
    "GankAIGC": {
        "role": "deployment-workbench",
        "responsibility": "run an explicit multi-user, BYOK, project-history, or feedback experiment",
    },
    "ai-humanizer": {
        "role": "external-api-demo",
        "responsibility": "exercise the Raycast/Rephrasy clipboard flow as a black-box comparison only",
    },
    "humanize-text": {
        "role": "translation-chain-baseline",
        "responsibility": "run the complete multi-engine trace as a research baseline, never on authority TeX",
    },
    "humanize-ai": {
        "role": "transformation-reference-workbench",
        "responsibility": "run low-risk transformation, change-trace, and cache experiments with random Markov edits disabled",
    },
    "humanize-main-Tiany": {
        "role": "same-source-candidate-lab",
        "responsibility": "run the reconstructed protected candidate comparison and evidence-based repair record",
    },
}


REVIEWER_CONFIG = {
    "ai-check": {
        "role": "forensic-style-reviewer",
        "mode": "REPORT_ONLY",
        "responsibility": "run the complete evidence-citing signal report without authorship or acceptance verdicts",
    },
    "patina": {
        "role": "multilingual-semantic-reviewer",
        "mode": "AUDIT",
        "responsibility": "run the complete pattern, semantic-anchor, MPS, and fidelity audit on a prose copy",
    },
    "humanizer-brandonwise": {
        "role": "english-statistical-reviewer",
        "mode": "ANALYZE",
        "responsibility": "run the complete English CLI pattern and statistical report as advisory evidence",
    },
}


ROLE_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "references" / "role-contracts.json"


def _load_provider_contracts() -> dict[str, dict]:
    payload = json.loads(ROLE_CONTRACT_PATH.read_text(encoding="utf-8-sig"))
    contracts: dict[str, dict] = {}
    for contract in payload.get("packages", []):
        for provider in contract.get("providers", []):
            contracts[str(provider)] = contract
    return contracts


def _provider_contract(provider: str) -> dict | None:
    return _load_provider_contracts().get(provider)


def _provider_allows_scene(provider: str, document_type: str) -> bool:
    contract = _provider_contract(provider)
    return contract is not None and document_type in set(contract.get("scenes", []))


def stage(order: int, role: str, provider: str, mode: str, responsibility: str, **extra: object) -> dict:
    item = {
        "order": order,
        "role": role,
        "provider": provider,
        "mode": mode,
        "responsibility": responsibility,
        "writes_authority_file": False,
    }
    item.update(extra)
    return item


def content_mode(intent: str) -> str:
    if intent in {"draft", "generate"}:
        return "GENERATE"
    if intent == "audit":
        return "AUDIT"
    return "REWRITE_OR_RECONCILE"


def _add_workbench(
    stages: list[dict], findings: list[dict], final_gates: list[str], order: int,
    workbench: str, *, plan_only: bool = False,
) -> int:
    config = APP_CONFIG[workbench]
    extra = {"manual": not plan_only}
    if config.get("embedded_capability_plan_required"):
        extra.update({
            "embedded_capability_plan_required": True,
            "embedded_capability_catalog": config.get("embedded_capability_catalog"),
            "embedded_activation_command": config.get("embedded_activation_command"),
            "embedded_scope": config.get("embedded_scope"),
        })
    stages.append(stage(
        order,
        str(config["role"]),
        workbench,
        "WORKBENCH_PLAN_READ_ONLY" if plan_only else "MANUAL",
        (
            "run the scene-filtered offline embedded-capability plan and record read-only findings; "
            "do not start the GUI or create another candidate"
            if plan_only else str(config["responsibility"])
        ),
        **extra,
    ))
    final_gates.append(
        f"offline-{config['role']}-plan" if plan_only
        else f"manual-{config['role']}-review"
    )
    if workbench in {
        "AI-Cleaner", "AI-content-detector", "BypassAIGC", "GankAIGC",
        "ai-humanizer", "humanize-text", "humanize-ai", "humanize-main-Tiany",
    }:
        findings.append({
            "severity": "warning",
            "code": "WORKBENCH_OUTPUT_REQUIRES_CANDIDATE_REENTRY",
            "application": workbench,
        })
    return order + 1


def select_route(
    document_type: str,
    intent: str,
    document_format: str = "plain",
    scope: str = "document",
    requested_editor: str | None = None,
    requested_app: str | None = None,
    requested_reviewer: str | None = None,
) -> dict:
    findings: list[dict] = []
    stages: list[dict] = []
    candidate_providers: list[str] = []
    final_gates: list[str] = []
    order = 1
    default_workbench_plan_only = False

    # A competition one-call should not stop after the sole rewrite provider.
    # The default MCM TeX route adds one report-only style reviewer and the
    # scene-filtered AI_paper workbench plan.  Neither may author a second
    # candidate or select the accepted text.
    if document_type == "mcm" and document_format == "tex":
        if requested_reviewer is None:
            requested_reviewer = "ai-check"
            findings.append({
                "severity": "note",
                "code": "DEFAULT_FORENSIC_REVIEWER_ENABLED",
                "reviewer": requested_reviewer,
            })
        if requested_app is None:
            requested_app = "AI_paper"
            default_workbench_plan_only = True
            findings.append({
                "severity": "note",
                "code": "DEFAULT_SCENE_WORKBENCH_ENABLED",
                "application": requested_app,
            })

    if document_type == "external-app":
        if not requested_app:
            findings.append({"severity": "error", "code": "EXTERNAL_APP_REQUIRES_NAME"})
        elif not _provider_allows_scene(requested_app, document_type):
            findings.append({
                "severity": "error",
                "code": "WORKBENCH_DOES_NOT_OWN_SCENE",
                "application": requested_app,
                "document_type": document_type,
            })
        else:
            order = _add_workbench(stages, findings, final_gates, order, requested_app)
        return _report(
            document_type, intent, document_format, scope, stages, candidate_providers,
            final_gates or ["manual-source-diff", "manual-export-approval"], findings,
            requested_app, requested_reviewer,
        )

    if document_type in ACADEMIC_TYPES:
        config = SCENE_CONFIG[document_type]
        if document_type in CHINESE_ACADEMIC_TYPES:
            stages.append(stage(
                order,
                "academic-scene-orchestration",
                "deai-academic-writing",
                "SEGMENT_AND_LOCK" if document_type == "academic-mixed" else "ROUTE_AND_LOCK",
                "own authority, provenance, scene contract, shared locks, and child-skill dispatch",
            ))
            order += 1

        for role, provider, responsibility in config["content"]:
            extra: dict[str, object] = {}
            if document_type == "mcm" and provider == "mcm-cup-standard-write":
                extra = {
                    "style_retrieval_required": True,
                    "style_retrieval_script": (
                        "python scripts/prepare_style_retrieval_plan.py <main.tex> "
                        "--problem-type A|B|C --output style-retrieval-plan.json "
                        "--minimum 3 --limit 8 --context-window 1"
                    ),
                    "style_retrieval_policy": (
                        "bind 3-8 verified paragraphs per writable section; observe function and stopping point; "
                        "do not copy sentences or import facts"
                    ),
                    "section_authoring_brief_required": True,
                    "section_authoring_brief_script": (
                        "python scripts/prepare_section_authoring_brief.py <main.tex> --problem-type A|B|C "
                        "--style-plan style-retrieval-plan.json --workbench modeling-workbench.json "
                        "--preflight reasoning-preflight.json --output section-authoring-brief.json"
                    ),
                    "section_authoring_brief_policy": (
                        "bind current-problem facts and human-approved routes to each section; keep corpus paragraphs style-only; "
                        "do not render workbench fields as a fixed prose template"
                    ),
                    "section_drafting_packets_required": True,
                    "section_drafting_packets_script": (
                        "python scripts/prepare_section_drafting_packets.py <main.tex> "
                        "--brief section-authoring-brief.json --style-plan style-retrieval-plan.json "
                        "--output-dir section-drafting-packets"
                    ),
                    "section_drafting_packets_policy": (
                        "before drafting each writable section, read its complete Txx packet: current-problem facts, "
                        "the selected full human paragraph and context, relevance-bounded alternatives with different "
                        "action/opening/surface-closing/ending-action/cadence shapes, and the drafting contract; choose one evidence-compatible "
                        "motion instead of blending surfaces; the packet materializes inputs but cannot prove consumption"
                    ),
                    "generation_input_lock_required": True,
                    "generation_input_lock_script": (
                        "python scripts/run_longform_portfolio.py lock-generation <manifest.json> "
                        "--workbench modeling-workbench.json --preflight reasoning-preflight.json "
                        "--style-retrieval-plan style-retrieval-plan.json --authoring-brief section-authoring-brief.json "
                        "--drafting-packet-index section-drafting-packets/packet-index.json"
                    ),
                    "generation_input_lock_policy": (
                        "run and freeze all source-bound drafting gates before candidate registration; "
                        "release must reuse the exact locked hashes"
                    ),
                    "section_drafting_usage_required": True,
                    "section_drafting_usage_script": (
                        "python scripts/prepare_section_drafting_usage.py <frozen-source.tex> <candidate.tex> "
                        "--packet-index section-drafting-packets/packet-index.json --run-id RUN_ID "
                        "--author-kind model --output section-drafting-usage.json"
                    ),
                    "section_drafting_usage_policy": (
                        "record each target section's source, packet, and candidate hashes plus retained/generated disposition; "
                        "declare lineage without exposing or inventing private chain-of-thought"
                    ),
                }
            stages.append(stage(order, role, provider, content_mode(intent), responsibility, **extra))
            order += 1

        if document_type in CHINESE_ACADEMIC_TYPES:
            allowed_editors = {"humanize-academic-chinese", "baibai-aigc"}
            default_editor = "humanize-academic-chinese"
        elif document_type == "medical-en":
            allowed_editors = {"humanizer-medical-academic", "academic-humanizer"}
            default_editor = "humanizer-medical-academic"
        else:
            allowed_editors = {"academic-humanizer"}
            default_editor = "academic-humanizer"

        if requested_editor and requested_editor not in allowed_editors:
            findings.append({
                "severity": "error",
                "code": "EDITOR_DOES_NOT_OWN_SCENE",
                "allowed": sorted(allowed_editors),
                "requested": requested_editor,
            })
        if requested_editor == "baibai-aigc" and scope != "local":
            findings.append({
                "severity": "error",
                "code": "BAIBAI_REQUIRES_LOCAL_SCOPE",
                "detail": "Use --scope local; Baibai is not the full-document academic owner.",
            })

        editor = requested_editor or default_editor
        if editor in allowed_editors and not _provider_allows_scene(editor, document_type):
            findings.append({
                "severity": "error",
                "code": "EDITOR_ROLE_CONTRACT_MISMATCH",
                "requested": editor,
                "document_type": document_type,
            })
        scene = str(config["scene"])
        if document_type in CHINESE_ACADEMIC_TYPES and intent == "compare":
            stages.append(stage(
                order, "candidate-H", "humanize-academic-chinese", f"{scene}/PROTECTED_REWRITE",
                "run the complete protected academic candidate workflow", branch_from="SOURCE",
            ))
            order += 1
            stages.append(stage(
                order, "candidate-B", "baibai-aigc", "ROUND_1",
                "run the complete conservative candidate workflow on a short authorized block",
                branch_from="SOURCE", scope="local",
            ))
            candidate_providers.extend(["humanize-academic-chinese", "baibai-aigc"])
        else:
            if editor == "humanize-academic-chinese":
                mode = f"{scene}/DIAGNOSE" if intent == "audit" else f"{scene}/PROTECTED_REWRITE"
                responsibility = "run the complete diagnose, protected candidate, mechanical validation, and emit workflow"
            elif editor == "baibai-aigc":
                mode = "AUDIT" if intent == "audit" else "ROUND_1"
                responsibility = "run the complete conservative candidate workflow on a short authorized block"
            elif editor == "academic-humanizer":
                mode = "AUDIT" if intent == "audit" else "AUDIT_REWRITE_REPORT"
                responsibility = "run the complete English academic audit, rewrite, invariant check, and change report"
            else:
                mode = "SELF_AUDIT" if intent == "audit" else "TWO_PASS_EDIT"
                responsibility = "run the complete medical-English author-profile and two-pass academic workflow"
            stages.append(stage(
                order, "academic-style-engine", editor, mode, responsibility,
                branch_from="SOURCE", scope=scope,
            ))
            if intent != "audit":
                candidate_providers.append(editor)
        order += 1
        final_gates = list(config["final_gates"])
    else:
        if intent in {"draft", "generate"}:
            findings.append({
                "severity": "error",
                "code": "GENERAL_EDITOR_REQUIRES_SOURCE_TEXT",
                "detail": "Create a source-bound draft with an appropriate content owner before editing it.",
            })

        if document_type == "general-zh":
            default_editor = "humanizer-zh"
            allowed_editors = {"humanizer-zh", "humanize-chinese-copy-lab", "patina"}
            responsibility = "own one complete general Chinese source-preserving edit"
        else:
            default_editor = "humanizer"
            allowed_editors = {
                "humanizer", "humanizer-brandonwise", "humanizer-voice-profile",
                "humanize-english-editor", "patina",
            }
            responsibility = "own one complete general English or nonacademic technical edit"
        editor = requested_editor or default_editor
        if editor not in allowed_editors:
            findings.append({
                "severity": "error",
                "code": "EDITOR_DOES_NOT_OWN_SCENE",
                "allowed": sorted(allowed_editors),
                "requested": editor,
            })
        elif not _provider_allows_scene(editor, document_type):
            findings.append({
                "severity": "error",
                "code": "EDITOR_ROLE_CONTRACT_MISMATCH",
                "requested": editor,
                "document_type": document_type,
            })
        if document_type == "technical" and document_format == "tex":
            findings.append({
                "severity": "error",
                "code": "TECHNICAL_TEX_REQUIRES_ACADEMIC_RECLASSIFICATION",
                "detail": "Reclassify as modeling, research, course-notes, academic-en, or academic-mixed.",
            })
        mode = "AUDIT" if intent == "audit" else "REWRITE"
        stages.append(stage(
            order, "general-prose-owner", editor, mode, responsibility,
            branch_from="SOURCE",
        ))
        order += 1
        if intent != "audit":
            candidate_providers.append(editor)
        final_gates = ["fact-preservation", "voice-match", "format-protection"]

    if requested_reviewer:
        reviewer = REVIEWER_CONFIG[requested_reviewer]
        if not _provider_allows_scene(requested_reviewer, document_type):
            findings.append({
                "severity": "error",
                "code": "REVIEWER_DOES_NOT_OWN_SCENE",
                "reviewer": requested_reviewer,
                "document_type": document_type,
            })
        elif requested_reviewer == "humanizer-brandonwise" and document_type in {
            "mcm", "modeling", "research", "course-notes", "academic-mixed", "general-zh",
        }:
            findings.append({
                "severity": "error",
                "code": "ENGLISH_REVIEWER_NOT_ALLOWED_FOR_CHINESE",
                "reviewer": requested_reviewer,
            })
        else:
            mode = str(reviewer["mode"])
            extra: dict[str, object] = {"read_only": True}
            if requested_reviewer == "patina" and document_format == "tex":
                mode = "AUDIT_EXTRACTED_PROSE_ONLY"
                extra["input_contract"] = "plain-text body proxy; TeX authority remains untouched"
            stages.append(stage(
                order, str(reviewer["role"]), requested_reviewer, mode,
                str(reviewer["responsibility"]), **extra,
            ))
            order += 1
            final_gates.append("reviewer-report-manual-interpretation")

    workbench = requested_app
    if not workbench and document_format == "docx":
        workbench = "FYADR"
    if workbench:
        if not _provider_allows_scene(workbench, document_type):
            findings.append({
                "severity": "error",
                "code": "WORKBENCH_DOES_NOT_OWN_SCENE",
                "application": workbench,
                "document_type": document_type,
            })
        else:
            order = _add_workbench(
                stages, findings, final_gates, order, workbench,
                plan_only=default_workbench_plan_only,
            )

    if intent == "compare" and document_type not in CHINESE_ACADEMIC_TYPES:
        findings.append({
            "severity": "note",
            "code": "COMPARE_USES_SOURCE_AND_EXPLICIT_CANDIDATE",
        })

    return _report(
        document_type, intent, document_format, scope, stages, candidate_providers,
        final_gates, findings, workbench, requested_reviewer,
    )


def _report(
    document_type: str,
    intent: str,
    document_format: str,
    scope: str,
    stages: list[dict],
    candidate_providers: list[str],
    final_gates: list[str],
    findings: list[dict],
    workbench: str | None,
    reviewer: str | None,
) -> dict:
    errors = sum(item["severity"] == "error" for item in findings)
    enriched_stages: list[dict] = []
    for item in stages:
        enriched = dict(item)
        contract = _provider_contract(str(item.get("provider", "")))
        if contract is not None:
            enriched["role_contract"] = {
                "package": contract.get("directory"),
                "role_class": contract.get("role_class"),
                "deliverables": contract.get("deliverables", []),
                "completion_evidence": contract.get("completion_evidence", []),
                "fallback": contract.get("fallback"),
                "must_not_claim": contract.get("must_not_claim", []),
            }
        else:
            enriched["role_contract"] = {
                "authority": "external-scene-owner",
                "completion_evidence": ["source-hash", "release-gates"],
            }
        enriched_stages.append(enriched)
    return {
        "schema": "aigc-writing-plan/v3",
        "status": "pass" if errors == 0 else "blocked",
        "document_type": document_type,
        "intent": intent,
        "document_format": document_format,
        "scope": scope,
        "authority_must_be_frozen": intent != "audit",
        "accepted_rewrite_candidates_max": 0 if intent == "audit" or errors else 1,
        "candidate_policy": {
            "providers": candidate_providers if errors == 0 else [],
            "branch_from_frozen_source": True,
            "serial_rewrite_allowed": False,
            "source_remains_candidate": True,
        },
        "reviewer": reviewer,
        "reviewer_can_select_candidate": False,
        "workbench": workbench,
        "manual_confirmation_required": any(item.get("manual") is True for item in stages),
        "stages": enriched_stages if errors == 0 else [],
        "final_gates": final_gates,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-type", choices=DOCUMENT_TYPES, required=True)
    parser.add_argument("--intent", choices=INTENTS, required=True)
    parser.add_argument("--document-format", choices=DOCUMENT_FORMATS, default="plain")
    parser.add_argument("--scope", choices=("document", "local"), default="document")
    parser.add_argument("--requested-editor", choices=EDITORS)
    parser.add_argument("--requested-reviewer", choices=REVIEWERS)
    parser.add_argument("--requested-app", choices=APPLICATIONS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = select_route(
        args.document_type,
        args.intent,
        args.document_format,
        args.scope,
        args.requested_editor,
        args.requested_app,
        args.requested_reviewer,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"AIGC PORTFOLIO {report['status'].upper()}")
        print(
            f"document_type={report['document_type']} intent={report['intent']} "
            f"format={report['document_format']} scope={report['scope']}"
        )
        for item in report["stages"]:
            manual = " manual" if item.get("manual") else ""
            print(
                f"{item['order']}. {item['role']} -> {item['provider']} "
                f"[{item['mode']}]{manual}: {item['responsibility']}"
            )
            contract = item.get("role_contract", {})
            evidence = contract.get("completion_evidence", [])
            if evidence:
                print("   requires=" + ",".join(str(value) for value in evidence))
        print("candidate_providers=" + ",".join(report["candidate_policy"]["providers"]))
        print("reviewer=" + str(report["reviewer"] or ""))
        print("final_gates=" + ",".join(report["final_gates"]))
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
