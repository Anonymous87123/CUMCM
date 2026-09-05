#!/usr/bin/env python3
"""Regression tests for the auxiliary role audit."""

from __future__ import annotations

import tempfile
from pathlib import Path

from adapter_core import sha256_file, write_json
from audit_auxiliary_roles import audit


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-auxiliary-audit-test-") as temp:
        root = Path(temp)
        plan = root / "workbench-plan.json"
        forensic = root / "audit-report.json"
        plan_payload = {
            "schema": "aigc-adapter-run/v1",
            "status": "pass",
            "claims": {"authorship_or_detector_verdict": False},
            "embedded_capabilities": {"status": "pass", "count": 16, "selected_count": 1},
            "plan": {"selected_embedded_capability_ids": ["argument-structure-checker"]},
        }
        forensic_payload = {
            "schema": "aigc-adapter-run/v1",
            "status": "pass",
            "claims": {"authorship_or_detector_verdict": False},
        }
        write_json(plan, plan_payload)
        write_json(forensic, forensic_payload)
        report = root / "chain-report.json"
        write_json(report, {
            "schema": "aigc-matrix-dev-chain/v2",
            "status": "pass",
            "mechanical_chain_complete": True,
            "candidates": 1,
            "auxiliary_roles": {
                "AI_paper_workbench_plan": str(plan),
                "AI_paper_workbench_plan_sha256": sha256_file(plan),
                "native_execution_claim": False,
            },
            "records": [{
                "auxiliary_reviews": {
                    "ai_check": {
                        "provider": "ai-check",
                        "adapter_package": "humanize-main",
                        "report": str(forensic),
                        "sha256": sha256_file(forensic),
                        "execution_level": "ADAPTER_DIAGNOSTIC_ONLY",
                        "claims": {
                            "authorship_or_detector_verdict": False,
                            "candidate_selection": False,
                        },
                    },
                    "AI_paper_workbench": {
                        "provider": "AI_paper",
                        "plan": str(plan),
                        "sha256": sha256_file(plan),
                        "execution_level": "WORKBENCH_PLAN_ONLY",
                        "claims": {
                            "candidate_generation": False,
                            "candidate_selection": False,
                        },
                    },
                },
            }],
        })
        passed = audit(report)
        if passed.get("status") != "pass":
            print("FAIL: valid auxiliary evidence was rejected", passed)
            return 1
        forensic.write_text('{"schema":"aigc-adapter-run/v1","status":"pass"}\n', encoding="utf-8")
        drifted = audit(report)
        if drifted.get("status") != "fail" or not any(
            item.get("code") == "AUXILIARY_HASH_DRIFT" for item in drifted.get("findings", [])
        ):
            print("FAIL: auxiliary hash drift was not detected", drifted)
            return 1
    print("auxiliary role audit tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
