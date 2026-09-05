#!/usr/bin/env python3
"""Positive and negative tests for the resumable long-form ledger."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from run_longform_portfolio import (
    audit_manifest,
    initialise,
    lock_generation_inputs,
    register_candidate,
)


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def passing_executor(command: list[str], cwd: Path, gate_id: str, run_dir: Path) -> dict:
    del command, cwd, gate_id, run_dir
    return {"returncode": 0, "stdout": json.dumps({"status": "pass"}), "stderr": ""}


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    with tempfile.TemporaryDirectory(prefix="aigc-longform-") as temp:
        root = Path(temp)
        main_tex = root / "main.tex"
        q1 = root / "q1.tex"
        run_dir = root / "run"
        main_tex.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题分析}\n由题面可知目标为最小化总成本。\n"
            "\\input{q1}\n\\end{document}\n",
            encoding="utf-8",
        )
        q1.write_text(
            "\\section{问题一模型}\n容量不低于 8 m，令 $x=3.2$。\\label{eq:q1}\n",
            encoding="utf-8",
        )
        manifest_path, manifest = initialise(
            main_tex, run_dir, "mcm", "A", registry,
        )
        require(len(manifest["authority"]["files"]) == 2, "included TeX file was not frozen", manifest)
        require(len(manifest["chunks"]) >= 3, "section chunks were not indexed", manifest)
        require(
            any(item["id"] == "style-retrieval-plan" and item["required"] is True for item in manifest["gates"]),
            "long-form manifest omitted the required style retrieval gate",
            manifest,
        )
        require(
            any(item["id"] == "section-authoring-brief" and item["required"] is True for item in manifest["gates"]),
            "long-form manifest omitted the required section authoring brief gate",
            manifest,
        )
        require(
            any(item["id"] == "judgment-ledger" and item["required"] is True for item in manifest["gates"]),
            "long-form manifest omitted the required public judgment ledger gate",
            manifest,
        )
        require(
            any(item["id"] == "public-judgment-bridges" and item["required"] is True for item in manifest["gates"]),
            "long-form manifest omitted the required public judgment bridge gate",
            manifest,
        )
        require(
            any(item["id"] == "public-reasoning-scaffold" and item["required"] is True for item in manifest["gates"]),
            "long-form manifest omitted the required public reasoning scaffold gate",
            manifest,
        )
        initial_audit = audit_manifest(manifest_path)
        require(initial_audit["status"] == "pass", "fresh ledger failed", initial_audit)

        candidate_dir = root / "candidate"
        candidate_dir.mkdir()
        candidate = candidate_dir / "main.tex"
        candidate.write_text(main_tex.read_text(encoding="utf-8"), encoding="utf-8")
        (candidate_dir / "q1.tex").write_text(q1.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            register_candidate(
                manifest_path, candidate, "humanize-academic-chinese", "H-unlocked",
                root / "unlocked.json",
            )
        except ValueError as exc:
            require("generation-input lock" in str(exc), "wrong unlocked-candidate error", str(exc))
        else:
            raise AssertionError("MCM candidate registered before generation inputs were locked")
        generation_inputs = {}
        for name in ("workbench", "preflight", "style", "brief", "packets"):
            path = root / f"{name}.json"
            path.write_text(json.dumps({"fixture": name}), encoding="utf-8")
            generation_inputs[name] = path
        locked_path, locked_manifest, lock_report = lock_generation_inputs(
            manifest_path,
            generation_inputs["workbench"], generation_inputs["preflight"],
            generation_inputs["style"], generation_inputs["brief"],
            generation_inputs["packets"], executor=passing_executor,
        )
        require(lock_report["status"] == "pass", "generation input lock failed", lock_report)
        require(locked_manifest["state"] == "GENERATION_INPUTS_LOCKED", "generation lock state is wrong", locked_manifest)
        rules = lock_report.get("writing_rules", {})
        require(
            rules.get("status") == "current-bound" and int(rules.get("count", 0)) >= 6,
            "generation lock omitted the active writing-rule owners", lock_report,
        )
        rule_snapshot = Path(rules["files"][0]["snapshot_path"])
        frozen_rule_snapshot = rule_snapshot.read_bytes()
        rule_snapshot.write_bytes(frozen_rule_snapshot + b"\n")
        rule_drift = audit_manifest(locked_path)
        require(
            rule_drift["status"] == "fail"
            and any(item["code"] == "GENERATION_WRITING_RULE_SNAPSHOT_DRIFT" for item in rule_drift["findings"]),
            "generation writing-rule snapshot drift was not detected", rule_drift,
        )
        rule_snapshot.write_bytes(frozen_rule_snapshot)
        require(
            audit_manifest(locked_path).get("writing_rule_freshness") == "current-bound",
            "restored generation rules were not current-bound", audit_manifest(locked_path),
        )
        registered_path, registered, verification = register_candidate(
            locked_path, candidate, "humanize-academic-chinese", "H1",
        )
        require(verification["status"] == "pass", "unchanged candidate failed", verification)
        require(audit_manifest(registered_path)["status"] == "pass", "registered ledger failed", registered)
        verification_path = Path(registered["candidates"][0]["verification_report"])
        frozen_verification = verification_path.read_text(encoding="utf-8")
        verification_path.write_text(frozen_verification + "\n", encoding="utf-8")
        verification_drift = audit_manifest(registered_path)
        require(
            verification_drift["status"] == "fail"
            and any(item["code"] == "CANDIDATE_VERIFICATION_REPORT_DRIFT" for item in verification_drift["findings"]),
            "verification-report drift was not detected",
            verification_drift,
        )
        verification_path.write_text(frozen_verification, encoding="utf-8")
        frozen_preflight = generation_inputs["preflight"].read_text(encoding="utf-8")
        generation_inputs["preflight"].write_text(frozen_preflight + "\n", encoding="utf-8")
        generation_drift = audit_manifest(registered_path)
        require(
            generation_drift["status"] == "fail"
            and any(item["code"] == "GENERATION_INPUT_DRIFT" for item in generation_drift["findings"]),
            "pre-candidate generation input drift was not detected", generation_drift,
        )
        generation_inputs["preflight"].write_text(frozen_preflight, encoding="utf-8")

        include_drift_dir = root / "include-drift"
        include_drift_dir.mkdir()
        include_drift = include_drift_dir / "main.tex"
        include_drift.write_text(main_tex.read_text(encoding="utf-8"), encoding="utf-8")
        (include_drift_dir / "q1.tex").write_text(
            q1.read_text(encoding="utf-8").replace("3.2", "3.3"), encoding="utf-8",
        )
        _, _, include_rejected = register_candidate(
            locked_path, include_drift, "humanize-academic-chinese", "H-include",
            root / "include-rejected.json",
        )
        require(
            include_rejected["status"] == "fail"
            and any(
                item["code"] == "PROTECTED_INVENTORY_DRIFT"
                and item.get("source_file") == "q1.tex"
                for item in include_rejected["findings"]
            ),
            "included candidate drift was not rejected",
            include_rejected,
        )

        drifted_dir = root / "drifted"
        drifted_dir.mkdir()
        drifted = drifted_dir / "main.tex"
        drifted.write_text(
            main_tex.read_text(encoding="utf-8").replace("最小化", "最大化"),
            encoding="utf-8",
        )
        (drifted_dir / "q1.tex").write_text(q1.read_text(encoding="utf-8"), encoding="utf-8")
        _, _, rejected = register_candidate(
            locked_path, drifted, "humanize-academic-chinese", "H2",
            root / "rejected.json",
        )
        require(
            rejected["status"] == "fail"
            and any(item["code"] == "OBJECTIVE_DIRECTION_CHANGED" for item in rejected["findings"]),
            "objective-direction drift was not rejected",
            rejected,
        )

        q1.write_text(q1.read_text(encoding="utf-8").replace("8 m", "9 m"), encoding="utf-8")
        drift_audit = audit_manifest(manifest_path)
        require(
            drift_audit["status"] == "fail"
            and any(item["code"] == "AUTHORITY_FILE_DRIFT" for item in drift_audit["findings"]),
            "included source drift was not detected",
            drift_audit,
        )

    print("PASS: TeX tree freeze, chunk ledger, candidate lineage, semantic rejection and source drift are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
