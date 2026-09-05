#!/usr/bin/env python3
"""Regression tests for source-bound academic candidate recovery routing."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from audit_academic_candidate import REPORT_SCHEMA, sha256_file
from prepare_academic_recovery import build_plan, materialize_rebase


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def report(source: Path, candidate: Path, contract_status: str, lexical_status: str) -> dict:
    return {
        "schema": REPORT_SCHEMA,
        "source": {"path": str(source), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
        "gates": [
            {
                "id": "humanize-lexical", "required": True, "status": lexical_status,
                "unresolved_findings": 1 if lexical_status != "pass" else 0,
                "unresolved": ([{
                    "signal_id": "LEX-CONTRAST-01", "relative_path": candidate.name,
                    "line": 3, "column": 1, "matched": "不是", "action": "REWRITE",
                    "rationale": "state the local relation directly",
                }] if lexical_status != "pass" else []),
            },
            {
                "id": "protected-rewrite-contract", "required": True, "status": contract_status,
                "findings": ([{
                    "severity": "error", "code": "MATH_CHANGED",
                }] if contract_status == "fail" else []),
            },
            {"id": "section-voice", "required": True, "status": "pass", "findings": []},
            {"id": "paragraph-rhythm", "required": True, "status": "pass", "findings": []},
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-academic-recovery-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source.write_text("line one\nline two\n这里不是误差，而是边界变化。\nline four\n", encoding="utf-8")
        candidate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        local_path = root / "local.json"
        local_path.write_text(json.dumps(report(source, candidate, "pass", "review"), ensure_ascii=False), encoding="utf-8")
        local = build_plan(local_path)
        require(
            local["route"] == "LOCAL_REPAIR_ON_CURRENT_CANDIDATE"
            and local["current_candidate_repair_allowed"]
            and len(local["repair_items"]) == 1
            and "不是误差" in local["repair_items"][0]["context"]["lines"][2]["text"],
            "contract-safe candidate did not receive a position-bound repair item",
            local,
        )

        structure_payload = report(source, candidate, "pass", "pass")
        rhythm_gate = next(item for item in structure_payload["gates"] if item["id"] == "paragraph-rhythm")
        rhythm_gate.update({
            "status": "review",
            "findings": [{
                "code": "REPEATED_PARAGRAPH_OPENING",
                "relative_path": candidate.name,
                "actual_line": 3,
                "section": "问题分析",
                "evidence": {"signature": "因此", "count": 3},
                "suggestion": "回到当前对象重组段落。",
            }],
        })
        structure_path = root / "structure.json"
        structure_path.write_text(json.dumps(structure_payload, ensure_ascii=False), encoding="utf-8")
        structure = build_plan(structure_path)
        require(
            structure["route"] == "LOCAL_REPAIR_ON_CURRENT_CANDIDATE"
            and structure["repair_item_counts"]["RHYTHM_STRUCTURE_REVIEW"] == 1
            and structure["repair_items"][0]["relative_path"] == candidate.name
            and structure["repair_items"][0]["context"] is not None,
            "rhythm finding did not become a source-bound structural repair item",
            structure,
        )

        semantic_payload = report(source, candidate, "review", "pass")
        contract_gate = next(item for item in semantic_payload["gates"] if item["id"] == "protected-rewrite-contract")
        contract_gate["findings"] = [{
            "severity": "warning", "code": "NEGATION_CHANGED",
            "finding_sha256": "a" * 64,
        }]
        contract_gate["unresolved_warnings"] = contract_gate["findings"]
        semantic_path = root / "semantic.json"
        semantic_path.write_text(json.dumps(semantic_payload, ensure_ascii=False), encoding="utf-8")
        semantic = build_plan(semantic_path)
        require(
            semantic["route"] == "SEMANTIC_REVIEW_ON_CURRENT_CANDIDATE"
            and semantic["repair_item_counts"]["SEMANTIC_WARNING_REVIEW"] == 1
            and semantic["repair_items"][0]["finding_sha256"] == "a" * 64,
            "semantic warning did not become an evidence-bound review item",
            semantic,
        )

        rebase_path = root / "rebase.json"
        rebase_path.write_text(json.dumps(report(source, candidate, "fail", "review"), ensure_ascii=False), encoding="utf-8")
        rebase = build_plan(rebase_path)
        require(
            rebase["route"] == "REBASE_FROM_FROZEN_SOURCE"
            and not rebase["current_candidate_repair_allowed"]
            and not rebase["repair_items"]
            and rebase["repair_items_suppressed"] == 1
            and rebase["native_rebase"]["input_must_be"] == "source",
            "protected drift did not force a clean source rebase",
            rebase,
        )
        materialized = materialize_rebase(rebase, root / "materialized")
        state = materialized["materialization"]
        require(
            state["status"] == "AUTHORING_REQUIRED"
            and state["unit_statuses"].get("UNRESOLVED", 0) == 0
            and state["scaffold"]["templates"] >= 1
            and Path(state["execution_receipt"]).is_file()
            and not state["claims"]["prose_rewritten"],
            "source rebase did not materialize a truthful authoring scaffold",
            materialized,
        )

        candidate.write_text(candidate.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
        try:
            build_plan(local_path)
        except ValueError as exc:
            require("drifted after audit" in str(exc), "candidate drift returned the wrong error", str(exc))
        else:
            raise AssertionError("candidate drift was not rejected")

    print("PASS: protected drift rebases from source; safe findings become position-bound local repairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
