#!/usr/bin/env python3
"""Regression checks for benchmark generation envelopes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import run_style_benchmark as style_benchmark
from adapter_core import write_json
from prepare_benchmark_generation import build
from prepare_stack_evaluation import build_manifest, build_stage
from run_aigc_adapter import execute
from run_stack_evaluation import evaluate
from run_style_benchmark import (
    _snapshot_stack_bundle,
    _validate_generation,
    _writing_rule_snapshot,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="benchmark-generation-") as temp:
        root = Path(temp)
        source = root / "source.txt"
        candidate = root / "candidate.txt"
        native = root / "run.json"
        source.write_text("源文。", encoding="utf-8")
        candidate.write_text("候选。", encoding="utf-8")
        native.write_text(
            json.dumps({"run_id": "run-1", "mechanical_validation_status": "PASS"}),
            encoding="utf-8",
        )
        skill_root = Path(__file__).resolve().parents[1]
        registry = skill_root / "references" / "stack-registry.json"
        verification_dir = root / "verification"
        verification = execute(
            registry, "humanize-academic-chinese", "verify-candidate",
            source=source, candidate=candidate, output_dir=verification_dir,
        )
        if verification.get("status") != "pass":
            print("FAIL: fixture candidate verification failed", verification)
            return 1
        route_artifact = root / "route.json"
        owner_artifact = root / "owner.json"
        write_json(route_artifact, {"status": "pass", "scene": "research"})
        write_json(owner_artifact, {"status": "pass", "claims_checked": ["fixture"]})
        academic_stage = root / "academic-stage.json"
        research_stage = root / "research-stage.json"
        build_stage(academic_stage, "deai-academic-writing", source, candidate, [route_artifact])
        build_stage(research_stage, "deai-research-writing", source, candidate, [owner_artifact])
        stack_manifest = root / "stack-manifest.json"
        build_manifest(
            stack_manifest, "research", "rewrite", "tex", "local",
            source, candidate, "H1", "source", "humanize-academic-chinese",
            verification_dir / "candidate-verification.json",
            [academic_stage, research_stage], None, "pending", "", "",
            ["mechanical_fidelity", "role_chain_complete"],
        )
        stack_report = root / "stack-report.json"
        stack_payload = evaluate(stack_manifest, registry)
        write_json(stack_report, stack_payload)
        if stack_payload.get("status") != "MECHANICAL_PASS_HUMAN_PENDING":
            print("FAIL: fixture role chain did not pass", stack_payload)
            return 1
        payload = build(
            "humanize-academic-chinese", source, candidate, native, "model", "REWRITE",
            stack_report=stack_report,
        )
        snapshot_paths = {
            str(item["path"]).replace("\\", "/") for item in _writing_rule_snapshot()
        }
        required_rule_suffixes = {
            "/AIGC/aigc-writing-router/SKILL.md",
            "/skills/deai-academic-writing/SKILL.md",
            "/skills/deai-modeling-writing/SKILL.md",
            "/skills/deai-research-writing/SKILL.md",
            "/skills/deai-course-notes/SKILL.md",
            "/mcm-cup-standard-write/SKILL.md",
            "/mcm-cup-standard-write/references/decision-moves.md",
            "/mcm-cup-standard-write/references/competition-longform.md",
            "/mcm-cup-standard-write/references/quality-gates.md",
            "/mcm-cup-standard-write/references/modeling-workbench.md",
            "/mcm-cup-standard-write/references/template-contract.md",
            "/mcm-cup-standard-write/references/contest-rules-2026.md",
            "/AIGC/humanize-academic-chinese/references/lexical-signals.json",
        }
        if not all(any(path.endswith(suffix) for path in snapshot_paths) for suffix in required_rule_suffixes):
            print("FAIL: generation envelope did not cover every canonical writing rule owner")
            return 1
        if any(path.endswith("/mcm-cup-standard-write/references/style-benchmark-runs.json") for path in snapshot_paths):
            print("FAIL: mutable benchmark run registry entered the writing-rule snapshot")
            return 1
        original_select_route = style_benchmark.select_route
        try:
            style_benchmark.select_route = lambda *_args, **_kwargs: {
                "status": "pass", "findings": [],
                "stages": [{"provider": "future-unregistered-owner"}],
            }
            try:
                style_benchmark._writing_rule_snapshot()
            except ValueError as exc:
                if "lack writing-rule owners" not in str(exc):
                    print("FAIL: unregistered route owner failed for the wrong reason", exc)
                    return 1
            else:
                print("FAIL: an unregistered MCM route owner escaped the writing-rule snapshot")
                return 1
        finally:
            style_benchmark.select_route = original_select_route
        if (
            payload["execution"]["mode"] != "model_authored_native_validated"
            or payload["claims"]["native_generation_proven"] is not False
            or payload.get("writing_rule_snapshot", [{}])[0].get("sha256", "") == ""
        ):
            print("FAIL: model-authored candidate was mislabeled or lacked a writing-rule snapshot")
            return 1
        frozen_stack = _snapshot_stack_bundle(
            payload, source, candidate,
            verification_dir / "candidate-verification.json",
            root / "frozen-evidence", "humanize-academic-chinese", 1, registry,
        )
        frozen_envelope = root / "generation-frozen-stack.json"
        frozen_envelope.write_text(json.dumps(frozen_stack, ensure_ascii=False), encoding="utf-8")
        original_owner_bytes = owner_artifact.read_bytes()
        owner_artifact.write_text("ORIGINAL-STAGE-DRIFT", encoding="utf-8")
        try:
            _validate_generation(
                frozen_envelope, "humanize-academic-chinese",
                payload["source"]["sha256"], payload["candidate"]["sha256"],
                require_stack_evaluation=True, registry_path=registry,
            )
        except ValueError as exc:
            print("FAIL: snapshotted stack bundle still depended on original stage artifacts", exc)
            return 1
        finally:
            owner_artifact.write_bytes(original_owner_bytes)
        envelope = root / "generation.json"
        envelope.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _, run_id, decision = _validate_generation(
            envelope, "humanize-academic-chinese",
            payload["source"]["sha256"], payload["candidate"]["sha256"],
            require_stack_evaluation=True, registry_path=registry,
        )
        if run_id != "run-1" or decision != "REWRITE":
            print("FAIL: generation run id or authoring decision was not preserved")
            return 1
        owner_bytes = owner_artifact.read_bytes()
        owner_artifact.write_text("DRIFT", encoding="utf-8")
        try:
            _validate_generation(
                envelope, "humanize-academic-chinese",
                payload["source"]["sha256"], payload["candidate"]["sha256"],
                require_stack_evaluation=True, registry_path=registry,
            )
        except ValueError:
            pass
        else:
            print("FAIL: drifted content-owner evidence was accepted")
            return 1
        owner_artifact.write_bytes(owner_bytes)
        missing_decision = dict(payload)
        missing_decision.pop("authoring_decision", None)
        envelope.write_text(json.dumps(missing_decision, ensure_ascii=False), encoding="utf-8")
        try:
            _validate_generation(
                envelope, "humanize-academic-chinese",
                payload["source"]["sha256"], payload["candidate"]["sha256"],
                require_stack_evaluation=True, registry_path=registry,
            )
        except ValueError:
            pass
        else:
            print("FAIL: a current generation envelope without authoring_decision was accepted")
            return 1
        payload["claims"]["human_authorship_proven"] = True
        envelope.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            _validate_generation(
                envelope, "humanize-academic-chinese",
                payload["source"]["sha256"], payload["candidate"]["sha256"],
                require_stack_evaluation=True, registry_path=registry,
            )
        except ValueError:
            pass
        else:
            print("FAIL: a generation envelope claiming human authorship was accepted")
            return 1
    print("PASS: benchmark generation envelopes bind native runs without claiming human authorship.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
