#!/usr/bin/env python3
"""Run the complete three-role evidence chain for one development suite.

This helper is deliberately limited to the source-derived local development
fixtures built by ``build_matrix_dev_candidates.py``.  It does not score
human-likeness, infer authorship, or clear academic correctness.

Public interface:
    python run_matrix_dev_chain.py SUITE.json --output-dir RUN \
        --document-type modeling|course-notes|research [--seed N]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from adapter_core import sha256_file, write_json
from audit_auxiliary_roles import audit as audit_auxiliary
from audit_benchmark_owner_ledger import (
    OWNER_BY_DOCUMENT_TYPE,
    SCHEMA as OWNER_SCHEMA,
    audit as audit_owner,
)
from build_matrix_dev_candidates import build as build_candidates
from prepare_benchmark_generation import build as build_generation
from prepare_benchmark_stack import build as build_stack
from run_aigc_adapter import execute as run_adapter
from run_style_benchmark import (
    audit_manifest,
    init_suite,
    prepare_benchmark,
    register_candidate,
)


REPORT_SCHEMA = "aigc-matrix-dev-chain/v2"
PROVIDER = "humanize-academic-chinese"
FORENSIC_PACKAGE = "humanize-main"
WORKBENCH_PACKAGE = "AI_paper"
SCENE_BY_TYPE = {
    "modeling": "MODELING",
    "course-notes": "COURSE",
    "research": "RESEARCH",
}
KEEP_REASON_BY_PHRASE = {
    "完全一致": "源稿已用该词准确描述四种赋权排序逐项相同；候选只调整句序，没有提高结论强度。",
    "能稳定": "源稿已将该事实限定为当前可约束模型的证据；候选保留同一限定，没有新增确定性主张。",
    "先看": "该位置的原句上下文用这个表达标示真实答题操作顺序；候选不把它用作空泛连接词。",
    "按这个顺序": "该表达在原句上下文中指向已经列明的判题次序；保留操作语气，不承担研究结论。",
    "更强": "源稿用该词比较两种已明示检验的辨别力；候选没有新增实验或提高证据等级。",
    "需要先": "该表达在原句上下文中限定验证从最简单的可精确情形开始；候选保留原验证次序和主张力度。",
}
CANDIDATE_RE = re.compile(r"^(?P<case>.+)-t(?P<trial>[1-9][0-9]*)$")


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _run_humanize_command(command: list[str]) -> dict:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Humanize runner did not emit a single JSON object: "
            f"exit={completed.returncode} stderr={completed.stderr[-1200:]}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Humanize runner JSON root is not an object")
    run_dir = Path(str(payload.get("run_dir", ""))).resolve()
    run_json = run_dir / "run.json"
    if not run_json.is_file():
        raise FileNotFoundError(run_json)
    persisted = _load_json(run_json)
    if persisted.get("run_id") != payload.get("run_id"):
        raise ValueError("Humanize stdout and persisted run disagree")
    persisted["_run_json"] = str(run_json)
    persisted["_process_exit_code"] = completed.returncode
    return persisted


def _keep_arguments(run: dict) -> list[str]:
    findings = run.get("diagnostics", {}).get("actionable_findings", [])
    if not isinstance(findings, list) or not findings:
        raise ValueError("mechanical REVIEW has no actionable strict finding to bind")
    arguments: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("invalid Humanize actionable finding")
        phrase = str(finding.get("matched", ""))
        reason = KEEP_REASON_BY_PHRASE.get(phrase)
        signal_id = str(finding.get("signal_id", ""))
        line = finding.get("line")
        column = finding.get("column")
        if not reason or not signal_id or not isinstance(line, int) or not isinstance(column, int):
            raise ValueError(
                "strict finding is not an approved source-inherited development fixture: "
                f"{finding}"
            )
        arguments.extend(["--keep-reason", f"{signal_id}@{line}:{column}={reason}"])
    return arguments


def run_humanize(source: Path, candidate: Path, document_type: str, output_dir: Path) -> dict:
    runner = Path(__file__).resolve().parents[2] / "humanize-academic-chinese" / "scripts" / "run_humanize_inline.py"
    base = [
        sys.executable,
        str(runner),
        "run",
        "--mode", "REWRITE",
        "--scene", SCENE_BY_TYPE[document_type],
        "--document-format", "tex",
        "--strict-speech-acts",
        "--fragment",
    ]
    initial = _run_humanize_command(
        base + ["--output-root", str(output_dir / "initial"), str(source), str(candidate)]
    )
    status = initial.get("mechanical_validation_status")
    if status == "PASS" and initial.get("body_emission_allowed") is True:
        return initial
    if status != "REVIEW" or initial.get("diagnostics", {}).get("hard_error_count", 0):
        raise ValueError(
            f"Humanize hard gate failed for {candidate.name}: "
            f"status={status} hard={initial.get('diagnostics', {}).get('hard_error_codes', [])}"
        )
    kept = _run_humanize_command(
        base
        + ["--output-root", str(output_dir / "accepted")]
        + _keep_arguments(initial)
        + [str(source), str(candidate)]
    )
    if kept.get("mechanical_validation_status") != "PASS" or kept.get("body_emission_allowed") is not True:
        raise ValueError(
            f"position-bound keep did not clear the mechanical gate for {candidate.name}: "
            f"{kept.get('diagnostics', {})}"
        )
    return kept


def _source_preview(path: Path) -> str:
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8-sig")).strip()
    return text[:120] + ("…" if len(text) > 120 else "")


def owner_ledger(document_type: str, source: Path, candidate: Path) -> dict:
    common = {
        "source_anchor": f"{source.name}; frozen excerpt: {_source_preview(source)}",
        "action": f"REWRITE local prose candidate {candidate.name}; no second humanizer pass",
    }
    if document_type == "modeling":
        decision = {
            **common,
            "problem_object": "The model object, evidence scale, comparison object, and result already named in the frozen paragraph.",
            "mathematical_change": "No formula, number, unit, label, reference, objective direction, or constraint is changed; only local clause order or connection is revised.",
            "modeling_decision": "Keep the source model and evidence-to-conclusion relation, while making the stated scale or comparison responsibility easier to follow.",
            "preserved_results": ["All source numbers, units, formulas, labels, references, comparison directions, and stated limitations."],
        }
    elif document_type == "course-notes":
        decision = {
            **common,
            "source_identity": "A frozen local excerpt from the user-supplied course-note report, not an invented teaching example.",
            "teaching_function": "Preserve the operational rule, data-scope distinction, or evidence/appendix responsibility expressed by the source paragraph.",
            "decisive_step": "Keep the actual question order, source boundary, and named CodeInline anchors; revise only how the instruction is presented.",
            "preserved_conditions": ["All numbers, dates, CodeInline tokens, scope limitations, and do-not-replace qualifications in the frozen source."],
        }
    else:
        decision = {
            **common,
            "claim": "Retain the existing research claim and expose its comparison or design implication without adding a new result.",
            "evidence_boundary": "No experiment, citation, theorem, causal claim, or evidence grade is added; the candidate remains bounded by the frozen excerpt.",
            "claim_strength": "The source modality, negation, comparison direction, scope qualifier, and empirical/theoretical status are unchanged.",
            "preserved_objects": ["All equations, references, algorithm names, result labels, condition qualifiers, and claim objects in the frozen source."],
        }
    return {
        "schema": OWNER_SCHEMA,
        "document_type": document_type,
        "provider": OWNER_BY_DOCUMENT_TYPE[document_type],
        "mode": "REWRITE",
        "source_sha256": sha256_file(source),
        "candidate_sha256": sha256_file(candidate),
        "decisions": [decision],
        "unresolved": [],
        "claims": {
            "hidden_reasoning_recorded": False,
            "academic_correctness_proven": False,
        },
    }


def run_auxiliary_reviews(
    registry: Path,
    document_type: str,
    candidate: Path,
    output_dir: Path,
    workbench_plan: Path,
) -> dict:
    """Run report-only auxiliary roles and return source-bound evidence paths."""
    forensic_dir = output_dir / "ai-check-adapter"
    forensic = run_adapter(
        registry,
        FORENSIC_PACKAGE,
        "audit",
        source=candidate,
        output_dir=forensic_dir,
        document_type=document_type,
    )
    forensic_report = forensic_dir / "audit-report.json"
    if forensic.get("status") != "pass" or not forensic_report.is_file():
        raise ValueError(f"forensic auxiliary audit failed for {candidate.name}: {forensic}")
    forensic_payload = _load_json(forensic_report)
    forensic_claims = forensic_payload.get("claims")
    if (
        forensic_payload.get("schema") != "aigc-adapter-run/v1"
        or forensic_payload.get("status") != "pass"
        or not isinstance(forensic_claims, dict)
        or forensic_claims.get("authorship_or_detector_verdict") is not False
    ):
        raise ValueError(f"forensic auxiliary report is not bounded: {forensic_report}")
    if not workbench_plan.is_file():
        raise FileNotFoundError(workbench_plan)
    return {
        "ai_check": {
            "provider": "ai-check",
            "adapter_package": FORENSIC_PACKAGE,
            "report": str(forensic_report.resolve()),
            "sha256": sha256_file(forensic_report),
            "execution_level": "ADAPTER_DIAGNOSTIC_ONLY",
            "native_executed": bool(forensic.get("native_executed", False)),
            "claims": {
                "authorship_or_detector_verdict": False,
                "candidate_selection": False,
            },
        },
        "AI_paper_workbench": {
            "provider": WORKBENCH_PACKAGE,
            "plan": str(workbench_plan.resolve()),
            "sha256": sha256_file(workbench_plan),
            "execution_level": "WORKBENCH_PLAN_ONLY",
            "native_executed": False,
            "claims": {
                "candidate_generation": False,
                "candidate_selection": False,
            },
        },
    }


def _stage_external_candidates(
    suite: dict,
    candidate_dir: Path,
    authoring_dir: Path,
) -> list[Path]:
    candidate_dir = candidate_dir.resolve()
    if not candidate_dir.is_dir():
        raise FileNotFoundError(candidate_dir)
    expected = {
        f"{case['id']}-t{trial}.tex"
        for case in suite.get("cases", [])
        if isinstance(case, dict) and case.get("id")
        for trial in (1, 2, 3)
    }
    actual = {path.name for path in candidate_dir.glob("*.tex")}
    if len(expected) != 9 or actual != expected:
        raise ValueError(
            "external candidate matrix is incomplete or contains undeclared files: "
            f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )
    authoring_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for name in sorted(expected):
        source = candidate_dir / name
        target = authoring_dir / name
        shutil.copy2(source, target)
        staged.append(target)
    return staged


def build_candidate_chain(
    suite_path: Path,
    output_dir: Path,
    document_type: str,
    registry: Path,
    seed: int,
    *,
    candidate_dir: Path | None = None,
    allowed_splits: tuple[str, ...] = ("dev",),
) -> dict:
    suite = _load_json(suite_path)
    split = str(suite.get("split", ""))
    if split not in allowed_splits:
        raise ValueError(f"suite split {split!r} is not allowed by this runner")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    _, current_manifest = init_suite(suite_path, output_dir, registry)
    if candidate_dir is None:
        candidates = build_candidates(output_dir / "sources", output_dir / "authoring", document_type)
    else:
        candidates = _stage_external_candidates(suite, candidate_dir, output_dir / "authoring")
    records: list[dict] = []
    registration_dir = output_dir / "registration"
    workbench_dir = output_dir / "auxiliary" / "AI_paper"
    workbench = run_adapter(
        registry,
        WORKBENCH_PACKAGE,
        "workbench-plan",
        output_dir=workbench_dir,
        document_type="mcm",
    )
    workbench_plan = workbench_dir / "workbench-plan.json"
    if workbench.get("status") != "pass" or not workbench_plan.is_file():
        raise ValueError(f"AI_paper workbench plan failed: {workbench}")
    workbench_payload = _load_json(workbench_plan)
    embedded = workbench_payload.get("embedded_capabilities")
    plan = workbench_payload.get("plan")
    selected = plan.get("selected_embedded_capability_ids") if isinstance(plan, dict) else None
    if (
        workbench_payload.get("schema") != "aigc-adapter-run/v1"
        or workbench_payload.get("status") != "pass"
        or not isinstance(embedded, dict)
        or embedded.get("status") != "pass"
        or embedded.get("count") != 16
        or not isinstance(selected, list)
        or len(selected) != embedded.get("selected_count")
        or len(set(selected)) != len(selected)
        or not isinstance(workbench_payload.get("claims"), dict)
        or workbench_payload["claims"].get("authorship_or_detector_verdict") is not False
    ):
        raise ValueError(f"AI_paper workbench plan is incomplete or unbounded: {workbench_plan}")

    for ordinal, candidate in enumerate(sorted(candidates), start=1):
        match = CANDIDATE_RE.fullmatch(candidate.stem)
        if not match:
            raise ValueError(f"candidate filename does not declare case and trial: {candidate.name}")
        case_id = match.group("case")
        trial = int(match.group("trial"))
        source = output_dir / "sources" / f"{case_id}{candidate.suffix}"
        if not source.is_file():
            raise FileNotFoundError(source)

        humanize = run_humanize(
            source, candidate, document_type, output_dir / "humanize" / candidate.stem,
        )
        native_report = Path(str(humanize["_run_json"]))

        verification_dir = output_dir / "verification" / candidate.stem
        verification = run_adapter(
            registry,
            PROVIDER,
            "verify-candidate",
            source=source,
            candidate=candidate,
            output_dir=verification_dir,
            document_type=document_type,
        )
        verification_path = verification_dir / "candidate-verification.json"
        if verification.get("status") != "pass" or not verification_path.is_file():
            raise ValueError(f"candidate verification failed for {candidate.name}: {verification}")

        owner_dir = output_dir / "owner" / candidate.stem
        owner_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = owner_dir / "ledger.json"
        write_json(ledger_path, owner_ledger(document_type, source, candidate))
        owner_report = audit_owner(ledger_path, source, candidate, document_type)
        owner_report_path = owner_dir / "audit.json"
        write_json(owner_report_path, owner_report)
        if owner_report.get("status") != "pass":
            raise ValueError(f"scene-owner ledger failed for {candidate.name}: {owner_report}")

        auxiliary = run_auxiliary_reviews(
            registry,
            document_type,
            candidate,
            output_dir / "auxiliary" / candidate.stem,
            workbench_plan,
        )

        stack_dir = output_dir / "stack" / candidate.stem
        build_stack(
            document_type,
            source,
            candidate,
            verification_path,
            owner_report_path,
            stack_dir,
            registry,
        )
        stack_report = stack_dir / "stack-report.json"

        generation = build_generation(
            PROVIDER,
            source,
            candidate,
            native_report,
            "model",
            "REWRITE",
            run_id=str(humanize.get("run_id")),
            stack_report=stack_report,
        )
        generation["auxiliary_reviews"] = auxiliary
        generation_dir = output_dir / "generation" / candidate.stem
        generation_dir.mkdir(parents=True, exist_ok=True)
        generation_path = generation_dir / "generation.json"
        write_json(generation_path, generation)

        next_manifest = registration_dir / f"r{ordinal:02d}.json"
        _, current_manifest = register_candidate(
            current_manifest,
            case_id,
            PROVIDER,
            trial,
            candidate,
            verification_path,
            next_manifest,
            registry,
            generation_path,
        )
        records.append({
            "case_id": case_id,
            "trial": trial,
            "candidate": str(candidate),
            "candidate_sha256": sha256_file(candidate),
            "humanize_run": str(native_report),
            "humanize_run_id": humanize.get("run_id"),
            "mechanical_validation_status": humanize.get("mechanical_validation_status"),
            "strict_accepted_count": humanize.get("diagnostics", {}).get("strict_accepted_count", 0),
            "verification": str(verification_path),
            "owner_audit": str(owner_report_path),
            "stack_report": str(stack_report),
            "generation": str(generation_path),
            "auxiliary_reviews": auxiliary,
            "registration_manifest": str(current_manifest),
        })

    blind_manifest = output_dir / "benchmark-blind-ready.json"
    _, current_manifest = prepare_benchmark(current_manifest, seed, blind_manifest, registry)
    manifest_report = audit_manifest(current_manifest, registry)
    if manifest_report.get("status") != "pass":
        raise ValueError(f"final {split} manifest failed audit: {manifest_report}")
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass",
        "split": split,
        "document_type": document_type,
        "suite": str(suite_path),
        "suite_id": suite.get("suite_id"),
        "candidates": len(records),
        "records": records,
        "auxiliary_roles": {
            "AI_paper_workbench_plan": str(workbench_plan),
            "AI_paper_workbench_plan_sha256": sha256_file(workbench_plan),
            "forensic_reviewer": "ai-check via humanize-main adapter",
            "native_execution_claim": False,
        },
        "manifest": str(current_manifest),
        "manifest_state": "BLIND_READY",
        "mechanical_chain_complete": True,
        "paired_human_quality_status": "PENDING_EXTERNAL_REVIEW",
        "claims": {
            "human_authorship_proven": False,
            "academic_correctness_proven": False,
            "detector_outcome_predicted": False,
            "human_style_clearance_granted": False,
        },
    }


def build_chain(
    suite_path: Path,
    output_dir: Path,
    document_type: str,
    registry: Path,
    seed: int,
) -> dict:
    return build_candidate_chain(
        suite_path,
        output_dir,
        document_type,
        registry,
        seed,
        candidate_dir=None,
        allowed_splits=("dev",),
    )


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--document-type", choices=sorted(SCENE_BY_TYPE), required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument(
        "--registry",
        type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build_chain(
        args.suite.resolve(),
        args.output_dir.resolve(),
        args.document_type,
        args.registry.resolve(),
        args.seed,
    )
    report_path = args.output_dir.resolve() / "chain-report.json"
    write_json(report_path, report)
    auxiliary_audit_path = args.output_dir.resolve() / "auxiliary-audit.json"
    auxiliary_audit = audit_auxiliary(report_path)
    write_json(auxiliary_audit_path, auxiliary_audit)
    if auxiliary_audit.get("status") != "pass":
        raise ValueError(f"auxiliary role audit failed: {auxiliary_audit.get('findings', [])}")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"MATRIX DEV CHAIN {report['status'].upper()} "
            f"type={report['document_type']} candidates={report['candidates']} "
            f"state={report['manifest_state']} human_quality=PENDING_EXTERNAL_REVIEW"
        )
        print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
