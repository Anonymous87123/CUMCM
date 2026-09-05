#!/usr/bin/env python3
"""Exercise every offline interface required by every AIGC role contract."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from adapter_core import read_registry
from audit_role_contracts import audit
from run_aigc_adapter import execute


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry_path = skill_root / "references" / "stack-registry.json"
    contracts_path = skill_root / "references" / "role-contracts.json"
    contract_audit = audit(registry_path, contracts_path)
    require(contract_audit["status"] == "pass", "role contracts are not closed", contract_audit)
    require(contract_audit.get("content_roles") == 5, "scene-owner content contracts are not closed", contract_audit)
    registry = read_registry(registry_path)
    contracts = json.loads(contracts_path.read_text(encoding="utf-8-sig"))
    entries = {str(item["directory"]): item for item in registry["packages"]}
    exercised: list[tuple[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="aigc-role-contracts-") as temp:
        root = Path(temp)
        bogus_contracts = json.loads(json.dumps(contracts))
        bogus_contracts["evidence_types"].append("unvalidated-proof")
        bogus_contracts["packages"][0]["completion_evidence"].append("unvalidated-proof")
        bogus_path = root / "bogus-role-contracts.json"
        bogus_path.write_text(
            json.dumps(bogus_contracts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        bogus_audit = audit(registry_path, bogus_path)
        require(
            any(item["code"] == "ROLE_COMPLETION_EVIDENCE_UNVALIDATED" for item in bogus_audit["findings"]),
            "a declared evidence token without a validator passed the role audit", bogus_audit,
        )
        source = root / "source.txt"
        candidate = root / "candidate.txt"
        drifted = root / "candidate-drifted.txt"
        sample = (
            "参数 0.35 改变后，首次触发对象由 A 转为 B。\n\n"
            "The baseline leaves a boundary-dependent residual at 3.2 units.\n"
            "Reference: https://example.invalid/evidence\n"
        )
        source.write_text(sample, encoding="utf-8")
        candidate.write_text(sample, encoding="utf-8")
        drifted.write_text(sample.replace("3.2", "3.3"), encoding="utf-8")

        for contract in contracts["packages"]:
            directory = str(contract["directory"])
            require(directory in entries, "contract package missing from registry", contract)
            for interface in contract["required_interfaces"]:
                output = root / "runs" / directory / str(interface)
                if interface == "audit":
                    report = execute(
                        registry_path, directory, "audit", source=source, output_dir=output,
                    )
                    require(report["status"] == "pass", f"audit failed for {directory}", report)
                    require(
                        "diagnostics" in report and "interpretation" in report
                        and report["claims"]["authorship_or_detector_verdict"] is False,
                        f"audit contract incomplete for {directory}", report,
                    )
                    require((output / "audit-report.json").is_file(), f"audit artifact missing for {directory}", report)
                elif interface == "candidate":
                    prepared = execute(
                        registry_path, directory, "prepare-candidate",
                        source=source, output_dir=output / "prepare",
                    )
                    require(prepared["status"] == "ready", f"candidate task failed for {directory}", prepared)
                    rules = prepared.get("task", {}).get("rules", [])
                    require(
                        prepared.get("task", {}).get("human_review_required") is True
                        and prepared.get("task", {}).get("required_next_action") == "verify-candidate"
                        and any("frozen source" in str(rule) for rule in rules),
                        f"candidate task contract incomplete for {directory}", prepared,
                    )
                    verified = execute(
                        registry_path, directory, "verify-candidate",
                        source=source, candidate=candidate, output_dir=output / "verify-pass",
                    )
                    require(verified["status"] == "pass", f"valid candidate failed for {directory}", verified)
                    rejected = execute(
                        registry_path, directory, "verify-candidate",
                        source=source, candidate=drifted, output_dir=output / "verify-fail",
                    )
                    require(
                        rejected["status"] == "fail"
                        and any(
                            item["code"] == "PROTECTED_INVENTORY_DRIFT"
                            for item in rejected["findings"]
                        ),
                        f"numeric drift was not rejected for {directory}", rejected,
                    )
                elif interface == "workbench":
                    report = execute(
                        registry_path, directory, "workbench-plan", output_dir=output,
                    )
                    plan = report.get("plan", {})
                    require(report["status"] == "pass", f"workbench plan failed for {directory}", report)
                    require(
                        plan.get("native_command") and plan.get("safe_boundary")
                        and plan.get("authority_rule") and plan.get("adoption_rule")
                        and report.get("preflight", {}).get("entrypoints_present") is True,
                        f"workbench contract incomplete for {directory}", report,
                    )
                else:
                    raise AssertionError(f"unknown interface {interface!r}")
                exercised.append((directory, str(interface)))

    expected = sum(len(item["required_interfaces"]) for item in contracts["packages"])
    require(len(exercised) == expected, "not all declared interfaces were exercised", exercised)
    print(
        f"PASS: {len(contracts['packages'])}/21 packages exercised all {len(exercised)} "
        "declared offline role interfaces, including candidate drift negatives."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
