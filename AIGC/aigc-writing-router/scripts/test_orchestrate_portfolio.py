#!/usr/bin/env python3
"""Positive and negative tests for receipt-driven portfolio collaboration."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from audit_portfolio_selection import audit as audit_portfolio_selection
from orchestrate_portfolio import (
    attach_role,
    init_plan,
    register_candidate,
    run_adapter,
    select_candidate,
    sha256_file,
    status,
)
from validate_role_evidence import MANUAL_SPECS


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def _field_value(field: str, source_path: Path, source_sha: str) -> object:
    if field == "path":
        return str(source_path.resolve())
    if field == "sha256":
        return source_sha
    if field in {"evidence_refs", "source_refs", "facts", "variables", "variants", "criteria", "excluded_scenes"}:
        return ["fixture-ref"]
    if field == "order":
        return 1
    if field == "confidence":
        return 1.0
    if field == "status":
        return "pass"
    return f"fixture-{field}"


def artifact_map(
    root: Path, tokens: list[str], prefix: str, *, provider: str, role: str,
    source_path: Path, source_sha: str, candidate_id: str | None = None,
    candidate_path: Path | None = None, candidate_sha: str | None = None,
) -> dict[str, dict[str, str]]:
    evidence: dict[str, dict[str, str]] = {}
    for index, token in enumerate(tokens):
        if token in MANUAL_SPECS:
            collection, required_fields = MANUAL_SPECS[token]
            path = root / f"{prefix}-{index:02d}-{token}.json"
            inputs = [{"path": str(source_path.resolve()), "sha256": source_sha, "role": "authority"}]
            if candidate_path is not None and candidate_sha is not None:
                inputs.append({"path": str(candidate_path.resolve()), "sha256": candidate_sha, "role": "candidate"})
            payload = {
                "schema": "aigc-role-evidence/v1",
                "evidence_type": token,
                "provider": provider,
                "role": role,
                "status": "pass",
                "authority_source_sha256": source_sha,
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_sha,
                "execution": {"mode": "manual_skill", "run_id": f"fixture-{prefix}-{token}"},
                "inputs": inputs,
                collection: [{field: _field_value(field, source_path, source_sha) for field in required_fields}],
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            path = root / f"{prefix}-{index:02d}-{token}.txt"
            path.write_text(f"non-contract fixture for {prefix}:{token}\n", encoding="utf-8")
        evidence[token] = {"path": str(path), "sha256": sha256_file(path)}
    return evidence


def make_receipt(root: Path, provider: str, role: str, source_path: Path, source_sha: str, required: list[str], prefix: str, *, candidate_id: str | None = None, candidate_path: Path | None = None, candidate_sha: str | None = None, gates: dict[str, str] | None = None, omit: str | None = None, evidence_override: dict[str, dict[str, str]] | None = None, run_id: str | None = None) -> Path:
    tokens = [token for token in required if token != omit]
    receipt = {
        "schema": "aigc-role-receipt/v1",
        "provider": provider,
        "role": role,
        "status": "pass",
        "authority_source_sha256": source_sha,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha,
        "gate_results": gates or {},
        "execution": {
            "mode": "manual_skill" if role == "content-owner" else "native_executed" if role == "reviewer" else "protected_candidate" if role == "candidate" else "manual_workbench",
            "run_id": run_id or f"test-{prefix}",
            "references_read": ["rules.md", "validation-gates.md"] if role == "content-owner" else [],
            "pass_count": 1,
        },
        "evidence": {
            **artifact_map(
                root, [token for token in tokens if token not in (evidence_override or {})], prefix,
                provider=provider, role=role, source_path=source_path, source_sha=source_sha,
                candidate_id=candidate_id, candidate_path=candidate_path, candidate_sha=candidate_sha,
            ),
            **{token: value for token, value in (evidence_override or {}).items() if token in tokens},
        },
        "unresolved": [],
    }
    path = root / f"{prefix}-receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_humanize_inline(before: Path, after: Path, output_root: Path) -> Path:
    runner = (
        Path(__file__).resolve().parents[1].parent
        / "humanize-academic-chinese" / "scripts" / "run_humanize_inline.py"
    )
    completed = subprocess.run(
        [
            sys.executable, str(runner), "run", str(before), str(after),
            "--output-root", str(output_root), "--mode", "REWRITE",
            "--scene", "RESEARCH", "--document-format", "tex",
            "--visible-output", "BODY_ONLY", "--strict-speech-acts",
        ],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        timeout=300, check=False,
    )
    require(completed.returncode in {0, 2}, "humanize inline fixture did not produce a reviewable run", {"returncode": completed.returncode, "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:]})
    payload = json.loads(completed.stdout)
    require(payload.get("mechanical_validation_status") == "PASS", "humanize inline fixture failed mechanical validation", payload)
    return Path(payload["run_dir"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-orchestrator-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        proxy = root / "source-prose.txt"
        source.write_text(r"\section{A} 参数 0.35 下结果为 3.2。", encoding="utf-8")
        proxy.write_text("参数 0.35 下结果为 3.2。\n", encoding="utf-8")

        # A blocked B1 branch without a prose proxy is explicit, never silently converted.
        blocked_plan = init_plan(source, "research", "tex", root / "blocked", [], candidate_providers=["humanize-academic-chinese", "baibai-aigc"])
        blocked = {item["provider"]: item for item in blocked_plan["branches"]}
        require(blocked["baibai-aigc"]["status"] == "blocked", "raw TeX must block Baibai", blocked)

        plan_dir = root / "plan"
        plan = init_plan(
            source, "research", "tex", plan_dir,
            ["patina"], proxy=proxy, candidate_providers=["humanize-academic-chinese", "baibai-aigc"], workbenches=["AI_paper"],
        )
        require(all(item["status"] == "requires_evidence" for item in plan["stages"]), "content stages must await real receipts", plan["stages"])
        require(next(item for item in plan["branches"] if item["provider"] == "baibai-aigc")["scope"] == "local-proxy", "B1 must be marked local-only", plan["branches"])

        # Missing one content artifact is a hard negative.
        academic = next(item for item in plan["stages"] if item["provider"] == "deai-academic-writing")
        authority_snapshot = Path(plan["source"]["snapshot"])
        bad_receipt = make_receipt(root, academic["provider"], "content-owner", authority_snapshot, plan["source"]["sha256"], academic["required_evidence"], "academic-bad", omit=academic["required_evidence"][-1])
        bad = attach_role(plan_dir, "content-owner", academic["provider"], bad_receipt)
        require(bad["status"] == "blocked" and any("EVIDENCE_MISSING" in item for item in bad["errors"]), "missing role evidence must block", bad)

        # A complete token list backed by arbitrary text must also fail.
        spoof = root / "spoof.txt"
        spoof.write_text("evidence for everything\n", encoding="utf-8")
        spoof_token = academic["required_evidence"][0]
        spoof_receipt = make_receipt(
            root, academic["provider"], "content-owner", authority_snapshot,
            plan["source"]["sha256"], academic["required_evidence"], "academic-spoof",
            evidence_override={spoof_token: {"path": str(spoof), "sha256": sha256_file(spoof)}},
        )
        spoof_result = attach_role(plan_dir, "content-owner", academic["provider"], spoof_receipt)
        require(
            spoof_result["status"] == "blocked"
            and any("EVIDENCE_JSON_REQUIRED" in item for item in spoof_result["errors"]),
            "plain text evidence must not complete a role", spoof_result,
        )

        # Complete every mandatory content owner with source-bound receipts.
        plan = json.loads((plan_dir / "portfolio-plan.json").read_text(encoding="utf-8"))
        for stage in plan["stages"]:
            receipt = make_receipt(root, stage["provider"], "content-owner", authority_snapshot, plan["source"]["sha256"], stage["required_evidence"], stage["provider"])
            result = attach_role(plan_dir, "content-owner", stage["provider"], receipt)
            require(result["status"] == "complete", "content owner did not complete", result)

        h1 = root / "candidate-h1.tex"
        h1.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        registered = register_candidate(plan_dir, "humanize-academic-chinese", h1)
        require(registered["status"] == "registered", "H1 candidate should pass invariants", registered)
        plan = json.loads((plan_dir / "portfolio-plan.json").read_text(encoding="utf-8"))
        h1_record = next(item for item in plan["branches"] if item["id"] == "H1")
        # A candidate receipt without the native Humanize run cannot pass.
        bad_candidate = make_receipt(root, "humanize-academic-chinese", "candidate", Path(h1_record["input_path"]), plan["source"]["sha256"], h1_record["required_evidence"], "h1-bad", candidate_id="H1", candidate_path=h1, candidate_sha=h1_record["output_sha256"], omit="native-run-report", evidence_override=h1_record["evidence"])
        bad_result = attach_role(plan_dir, "candidate", "humanize-academic-chinese", bad_candidate)
        require(bad_result["status"] == "blocked" and any("HUMANIZE_NATIVE_RUN_REPORT_MISSING" in item for item in bad_result["errors"]), "missing native Humanize execution must block", bad_result)

        inline_run = run_humanize_inline(Path(h1_record["input_path"]), h1, root / "humanize-runs")
        native_evidence = {
            **h1_record["evidence"],
            "native-run-report": {"path": str(inline_run / "run.json"), "sha256": sha256_file(inline_run / "run.json")},
            "change-report": {"path": str(inline_run / "validation.json"), "sha256": sha256_file(inline_run / "validation.json")},
        }
        good_candidate = make_receipt(root, "humanize-academic-chinese", "candidate", Path(h1_record["input_path"]), plan["source"]["sha256"], h1_record["required_evidence"], "h1-good", candidate_id="H1", candidate_path=h1, candidate_sha=h1_record["output_sha256"], gates=h1_record["gate_results"], evidence_override=native_evidence, run_id=inline_run.name)
        h1_attached = attach_role(plan_dir, "candidate", "humanize-academic-chinese", good_candidate)
        require(h1_attached["status"] == "eligible", "H1 should become eligible", h1_attached)

        # Register the local B1 branch but do not allow it to become a document baseline.
        b1 = root / "candidate-b1.txt"
        b1.write_text(proxy.read_text(encoding="utf-8"), encoding="utf-8")
        require(register_candidate(plan_dir, "baibai-aigc", b1)["status"] == "registered", "B1 proxy candidate should verify", b1)
        plan = json.loads((plan_dir / "portfolio-plan.json").read_text(encoding="utf-8"))
        b1_record = next(item for item in plan["branches"] if item["id"] == "B1")
        skill_root = Path(__file__).resolve().parents[1]
        b1_audit_dir = root / "b1-audit"
        require(run_adapter(skill_root, "baibai-aigc", "audit", Path(b1_record["input_path"]), b1_audit_dir).get("status") == "pass", "B1 audit fixture failed", b1_audit_dir)
        b1_plan_dir = root / "b1-workbench"
        require(run_adapter(skill_root, "baibai-aigc", "workbench-plan", Path(b1_record["input_path"]), b1_plan_dir).get("status") == "pass", "B1 workbench fixture failed", b1_plan_dir)
        b1_evidence = {
            **b1_record["evidence"],
            "audit-report": {"path": str(b1_audit_dir / "audit-report.json"), "sha256": sha256_file(b1_audit_dir / "audit-report.json")},
            "workbench-plan": {"path": str(b1_plan_dir / "workbench-plan.json"), "sha256": sha256_file(b1_plan_dir / "workbench-plan.json")},
        }
        b1_receipt = make_receipt(root, "baibai-aigc", "candidate", Path(b1_record["input_path"]), plan["source"]["sha256"], b1_record["required_evidence"], "b1", candidate_id="B1", candidate_path=b1, candidate_sha=b1_record["output_sha256"], gates={gate: "pass" for gate in b1_record["required_hard_gates"]}, evidence_override=b1_evidence)
        b1_attached = attach_role(plan_dir, "candidate", "baibai-aigc", b1_receipt)
        require(b1_attached["status"] == "complete", "B1 local candidate should be recorded but not document-eligible", b1_attached)

        # Reviewer and workbench receipts target H1 and are independent reports.
        plan = json.loads((plan_dir / "portfolio-plan.json").read_text(encoding="utf-8"))
        reviewer = next(item for item in plan["reviewers"] if item["provider"] == "patina")
        h1_sha = next(item for item in plan["branches"] if item["id"] == "H1")["output_sha256"]
        patina_dir = root / "patina-native"
        patina_report = run_adapter(skill_root, "patina", "audit", h1, patina_dir, execute_native=True)
        require(patina_report.get("status") == "pass" and patina_report.get("native_executed") is True, "Patina native fixture failed", patina_report)
        patina_evidence = {
            token: {"path": str(patina_dir / "audit-report.json"), "sha256": sha256_file(patina_dir / "audit-report.json")}
            for token in reviewer["required_evidence"]
        }
        review_receipt = make_receipt(root, "patina", "reviewer", authority_snapshot, plan["source"]["sha256"], reviewer["required_evidence"], "patina", candidate_id="H1", candidate_path=h1, candidate_sha=h1_sha, evidence_override=patina_evidence)
        reviewer_attached = attach_role(plan_dir, "reviewer", "patina", review_receipt)
        require(reviewer_attached["status"] == "complete", "reviewer receipt should complete", reviewer_attached)
        workbench = next(item for item in plan["workbenches"] if item["provider"] == "AI_paper")
        paper_audit_dir = root / "paper-audit"
        require(run_adapter(skill_root, "AI_paper", "audit", h1, paper_audit_dir).get("status") == "pass", "AI_paper audit fixture failed", paper_audit_dir)
        paper_verify_dir = root / "paper-verify"
        require(run_adapter(skill_root, "AI_paper", "verify-candidate", authority_snapshot, paper_verify_dir, candidate=h1).get("status") == "pass", "AI_paper verification fixture failed", paper_verify_dir)
        wb_evidence = {
            "workbench-plan": workbench["evidence"]["workbench-plan"],
            "audit-report": {"path": str(paper_audit_dir / "audit-report.json"), "sha256": sha256_file(paper_audit_dir / "audit-report.json")},
            "export-artifact": {"path": str(h1), "sha256": sha256_file(h1)},
            "candidate-verification": {"path": str(paper_verify_dir / "candidate-verification.json"), "sha256": sha256_file(paper_verify_dir / "candidate-verification.json")},
        }
        wb_receipt = make_receipt(root, "AI_paper", "workbench", authority_snapshot, plan["source"]["sha256"], workbench["required_evidence"], "paper-workbench", candidate_id="H1", candidate_path=h1, candidate_sha=h1_sha, evidence_override=wb_evidence)
        workbench_attached = attach_role(plan_dir, "workbench", "AI_paper", wb_receipt)
        require(workbench_attached["status"] == "complete", "workbench receipt should complete", workbench_attached)

        ready = status(plan_dir)
        require(ready["ready_for_selection"] is True, "all receipts should unlock selection", ready)
        selected = select_candidate(plan_dir, "H1", "队长", "H1 保留公式和约束，结果段的比较对象更清楚")
        require(selected["collaboration_status"] == "COMPLETE", "complete receipts should produce a complete collaboration record", selected)
        selection_audit = audit_portfolio_selection(
            plan_dir / "portfolio-plan.json", h1, "H1", plan["source"]["sha256"]
        )
        require(selection_audit["status"] == "pass", "fresh role receipts were not accepted by the release bridge", selection_audit)

        # Freshness is independently checked after adoption.
        selected_plan = json.loads((plan_dir / "portfolio-plan.json").read_text(encoding="utf-8"))
        selected_h1 = next(item for item in selected_plan["branches"] if item["id"] == "H1")
        legacy_stage = selected_plan["stages"][0]
        saved_contract = legacy_stage.pop("receipt_contract")
        (plan_dir / "portfolio-plan.json").write_text(
            json.dumps(selected_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        legacy = status(plan_dir)
        require(
            any("receipt-contract" in item for item in legacy["stale_artifacts"]),
            "a pre-v2 receipt remained fresh", legacy,
        )
        legacy_stage["receipt_contract"] = saved_contract
        (plan_dir / "portfolio-plan.json").write_text(
            json.dumps(selected_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        Path(selected_h1["evidence"]["native-run-report"]["path"]).write_text("tampered\n", encoding="utf-8")
        stale = status(plan_dir)
        require(stale["stale_artifacts"], "mutating an evidence file must invalidate the receipt", stale)
        stale_selection = audit_portfolio_selection(
            plan_dir / "portfolio-plan.json", h1, "H1", plan["source"]["sha256"]
        )
        require(stale_selection["status"] == "fail", "stale receipt passed the release bridge", stale_selection)
    print("PASS: explicit content, candidate, reviewer, workbench and human-decision receipts; format, missing-evidence, hard-gate and hash-drift negatives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
