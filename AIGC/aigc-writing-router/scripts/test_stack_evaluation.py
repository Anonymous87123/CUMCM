#!/usr/bin/env python3
"""Positive and negative regression tests for stack-level evaluation bundles."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile

from adapter_core import sha256_file, write_json
from blind_pair_evaluation import prepare, score
from merge_style_benchmark_ratings import merge_ratings
from prepare_stack_evaluation import build_manifest, build_stage
from run_aigc_adapter import execute
from run_stack_evaluation import evaluate


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def locked(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    with tempfile.TemporaryDirectory(prefix="aigc-stack-evaluation-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source_text = (
            "\\section{问题二}\n"
            "参数 0.35 改变后，首次触发对象由 A 转为 B。"
            "由 $x^2=1$ 可得结果 3.2，见式 \\eqref{eq:a} 与文献 \\cite{r1}。"
            "\\label{eq:a}\n"
        )
        source.write_text(source_text, encoding="utf-8")
        candidate.write_text(source_text, encoding="utf-8")
        verification = execute(
            registry,
            "humanize-academic-chinese",
            "verify-candidate",
            source=source,
            candidate=candidate,
            output_dir=root / "verification",
        )
        require(verification["status"] == "pass", "fixture verification failed", verification)
        verification_path = root / "verification" / "candidate-verification.json"

        stage_records = []
        stage_dir = root / "stages"
        for provider in (
            "deai-academic-writing", "mcm-cup-standard-write", "deai-modeling-writing",
            "ai-check", "AI_paper",
        ):
            artifact = root / f"{provider}.txt"
            artifact.write_text(f"{provider} gate evidence\n", encoding="utf-8")
            report = stage_dir / f"{provider}.json"
            build_stage(report, provider, source, candidate, [artifact])
            stage_records.append(locked(report))

        base_manifest = {
            "schema": "aigc-stack-evaluation/v1",
            "scene": {
                "document_type": "mcm",
                "intent": "rewrite",
                "document_format": "tex",
                "scope": "document",
            },
            "source": locked(source),
            "baseline_id": "source",
            "candidate": {
                **locked(candidate),
                "id": "H1",
                "provider": "humanize-academic-chinese",
            },
            "stage_evidence": stage_records,
            "candidate_verification": locked(verification_path),
            "human_decision": {"status": "pending"},
            "claims": ["mechanical_fidelity", "role_chain_complete"],
        }
        pending_path = root / "pending.json"
        build_manifest(
            pending_path, "mcm", "rewrite", "tex", "document",
            source, candidate, "H1", "source", "humanize-academic-chinese",
            verification_path,
            [Path(item["path"]) for item in stage_records],
            None, "pending", "", "",
            ["mechanical_fidelity", "role_chain_complete"],
        )
        pending = evaluate(pending_path, registry)
        require(
            pending["status"] == "MECHANICAL_PASS_HUMAN_PENDING",
            "mechanically valid bundle did not remain human-pending",
            pending,
        )
        prepared_manifest = json.loads(pending_path.read_text(encoding="utf-8"))
        require(
            not Path(prepared_manifest["source"]["path"]).is_absolute(),
            "manifest builder did not produce a portable relative source path",
            prepared_manifest,
        )

        pairs_path = root / "pairs.json"
        write_json(pairs_path, {
            "schema": "aigc-blind-pairs/v1",
            "pairs": [{
                "id": "p1",
                "variants": [
                    {"id": "source", "text": "调整参数后结果发生变化。"},
                    {"id": "H1", "text": "参数越过阈值后，首次触发对象由 A 换成了 B。"},
                ],
            }],
        })
        prepared = prepare(pairs_path, root / "blind", 2026)
        key = json.loads(Path(prepared["key"]).read_text(encoding="utf-8"))
        raw_ratings = root / "ratings-raw.csv"
        with raw_ratings.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "pair_id", "rater_id", "rater_kind", "naturalness", "judgment_trajectory",
                "specificity", "content_density", "semantic_fidelity", "notes",
            ))
            writer.writeheader()
            mapping = key["pairs"][0]
            chosen = "A" if mapping["A"] == "H1" else "B"
            for rater in ("R1", "R2"):
                writer.writerow({
                    "pair_id": "p1", "rater_id": rater, "rater_kind": "human",
                    "naturalness": chosen, "judgment_trajectory": chosen,
                    "specificity": chosen, "content_density": chosen,
                    "semantic_fidelity": "TIE", "notes": "",
                })
        with raw_ratings.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rating_fields = tuple(reader.fieldnames or ())
            rating_rows = list(reader)
        human_ratings = []
        for rater_id in ("R1", "R2"):
            path = root / f"ratings-{rater_id}.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rating_fields)
                writer.writeheader()
                writer.writerows(row for row in rating_rows if row["rater_id"] == rater_id)
            human_ratings.append(path)
        ratings = root / "ratings.csv"
        merge_report = root / "ratings-merge.json"
        merge_ratings(Path(prepared["packet"]), human_ratings, ratings, merge_report)
        blind_report = score(Path(prepared["key"]), ratings, merge_report)
        blind_path = root / "blind-score.json"
        write_json(blind_path, blind_report)
        accepted_manifest = json.loads(json.dumps(base_manifest, ensure_ascii=False))
        accepted_manifest["human_decision"] = {
            "status": "accepted",
            "reviewer": "R1+R2 后由队长裁决",
            "reason": "盲评中候选把参数变化与首次触发对象切换写得更具体。",
        }
        accepted_manifest["blind_score"] = locked(blind_path)
        accepted_manifest["claims"].append("human_preference_observed")
        accepted_path = root / "accepted.json"
        write_json(accepted_path, accepted_manifest)
        accepted = evaluate(accepted_path, registry)
        require(
            accepted["status"] == "HUMAN_EVALUATED_PASS",
            "locked blind evidence and human decision did not pass",
            accepted,
        )

        alternate_ratings = root / "ratings-alternate.csv"
        alternate_ratings.write_bytes(ratings.read_bytes())
        mismatched_blind = json.loads(blind_path.read_text(encoding="utf-8"))
        mismatched_blind["evidence"]["ratings"] = locked(alternate_ratings)
        mismatched_blind_path = root / "blind-score-mismatched.json"
        write_json(mismatched_blind_path, mismatched_blind)
        mismatched_manifest = json.loads(json.dumps(accepted_manifest, ensure_ascii=False))
        mismatched_manifest["blind_score"] = locked(mismatched_blind_path)
        mismatched_path = root / "accepted-mismatched.json"
        write_json(mismatched_path, mismatched_manifest)
        mismatched = evaluate(mismatched_path, registry)
        require(
            mismatched["status"] == "FAIL"
            and any(item["code"] == "BLIND_SCORE_MERGE_BINDING_MISMATCH" for item in mismatched["findings"]),
            "individually valid but cross-mismatched score evidence was accepted",
            mismatched,
        )

        missing_stage = json.loads(json.dumps(base_manifest, ensure_ascii=False))
        missing_stage["stage_evidence"] = missing_stage["stage_evidence"][:-1]
        missing_path = root / "missing-stage.json"
        write_json(missing_path, missing_stage)
        missing = evaluate(missing_path, registry)
        require(
            missing["status"] == "FAIL"
            and any(item["code"] == "STAGE_EVIDENCE_MISSING" for item in missing["findings"]),
            "missing content-owner evidence was not rejected",
            missing,
        )

        detector_manifest = json.loads(json.dumps(base_manifest, ensure_ascii=False))
        detector_manifest["detector_score"] = 0.01
        detector_path = root / "detector.json"
        write_json(detector_path, detector_manifest)
        detector = evaluate(detector_path, registry)
        require(
            detector["status"] == "FAIL"
            and any(
                item["code"] == "DETECTOR_OR_AUTHORSHIP_METRIC_FORBIDDEN"
                for item in detector["findings"]
            ),
            "detector score was allowed into the release claim bundle",
            detector,
        )

    print(
        "PASS: stack evaluation distinguishes mechanical readiness, locked human review, "
        "missing role evidence, and forbidden detector claims."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
