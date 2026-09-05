#!/usr/bin/env python3
"""End-to-end positive and negative tests for the dev/holdout style benchmark."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile

from adapter_core import sha256_file, write_json
from blind_pair_evaluation import DIMENSIONS
from merge_style_benchmark_ratings import merge_ratings
from run_aigc_adapter import execute
from run_style_benchmark import (
    aggregate,
    audit_manifest,
    init_suite,
    prepare_benchmark,
    probe_benchmark,
    register_candidate,
    score_benchmark,
    _writing_rule_snapshot,
)


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def make_candidate_evidence(
    root: Path,
    registry: Path,
    suite_id: str,
    case_id: str,
    label: str,
    source: Path,
    candidate: Path,
    authoring_decision: str = "REWRITE",
) -> tuple[Path, Path]:
    verification_dir = root / f"verify-{suite_id}-{case_id}-{label}"
    verification = execute(
        registry,
        "humanizer-zh",
        "verify-candidate",
        source=source,
        candidate=candidate,
        output_dir=verification_dir,
    )
    require(verification["status"] == "pass", "fixture verification failed", verification)
    require(
        "\ufffd" not in json.dumps(verification, ensure_ascii=False),
        "candidate verification contains Unicode replacement characters",
        verification,
    )
    native_report = root / f"native-{suite_id}-{case_id}-{label}.json"
    write_json(native_report, {"status": "pass", "provider": "humanizer-zh", "label": label})
    generation = root / f"generation-{suite_id}-{case_id}-{label}.json"
    write_json(generation, {
        "schema": "aigc-benchmark-generation/v1",
        "provider": "humanizer-zh",
        "status": "pass",
        "authoring_actor": "model",
        "authoring_decision": authoring_decision,
        "source": {"sha256": sha256_file(source)},
        "candidate": {"sha256": sha256_file(candidate)},
        "execution": {
            "mode": "model_authored_native_validated",
            "run_id": f"{suite_id}-{case_id}-{label}",
        },
        "native_report": {"path": str(native_report), "sha256": sha256_file(native_report)},
        "writing_rule_snapshot": _writing_rule_snapshot(),
        "claims": {
            "human_authorship_proven": False,
            "native_generation_proven": False,
            "validation_executed": True,
        },
    })
    return verification_dir / "candidate-verification.json", generation


def write_ratings(
    manifest_path: Path,
    ratings_path: Path,
    bad_case: str | None = None,
    rater_kind: str = "human",
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    key = json.loads(Path(manifest["blind"]["key"]["path"]).read_text(encoding="utf-8"))
    pair_map = json.loads(Path(manifest["blind"]["pair_map"]["path"]).read_text(encoding="utf-8"))["pairs"]
    with ratings_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("pair_id", "rater_id", "rater_kind", *DIMENSIONS, "notes"))
        writer.writeheader()
        for pair in key["pairs"]:
            meta = pair_map[pair["pair_id"]]
            candidate_side = "A" if pair["A"] == meta["candidate_id"] else "B"
            source_side = "B" if candidate_side == "A" else "A"
            is_bad = meta["case_id"] == bad_case
            raters = ("R1", "R2") if rater_kind == "human" else ("M1",)
            for rater in raters:
                row = {
                    "pair_id": pair["pair_id"],
                    "rater_id": rater,
                    "rater_kind": rater_kind,
                    "naturalness": candidate_side,
                    "judgment_trajectory": source_side if is_bad else candidate_side,
                    "specificity": candidate_side,
                    "content_density": candidate_side,
                    "semantic_fidelity": source_side if is_bad else "TIE",
                    "notes": (
                        "候选把相关现象改成了因果结论，应保留原有边界。"
                        if is_bad and rater == "R1"
                        else "候选补出了参数变化后的具体事件对象。" if rater == "R1" else ""
                    ),
                }
                writer.writerow(row)


def run_suite(
    root: Path,
    registry: Path,
    suite_id: str,
    split: str,
    include_bad_case: bool,
) -> Path:
    source_dir = root / f"{suite_id}-sources"
    source_dir.mkdir()
    event_case = {
        "id": "event-switch",
        "source_text": "参数 0.35 改变后，结果发生变化。",
        "candidate_prefix": "参数从 0.35 跨过阈值后，首次触发对象由 A 切换为 B，输出因而出现跃变。",
        "tags": ["public-judgment", "specificity", "result-explanation"],
    }
    if split == "holdout":
        event_case = {
            "id": "event-switch",
            "source_text": "控制系数为 0.35 时，终止事件的归属尚不清楚。",
            "candidate_prefix": "控制系数保持为 0.35 时，逐项检查触发次序可知终止事件先由构件 B 引起。",
            "tags": ["public-judgment", "specificity", "result-explanation"],
        }
    cases = [event_case]
    if include_bad_case:
        cases.append({
            "id": "causal-boundary",
            "source_text": "温度与故障同步上升只能作为相关现象，尚不能据此判断因果。",
            "candidate_prefix": "温度与故障同步上升，因此温度升高必然导致故障。",
            "tags": ["causal-calibration", "semantic-fidelity", "public-judgment"],
        })
    suite_cases = []
    for case in cases:
        source = source_dir / f"{case['id']}.txt"
        source.write_text(case["source_text"], encoding="utf-8")
        suite_cases.append({
            "id": case["id"],
            "scene": {"document_type": "general-zh", "document_format": "plain", "scope": "document"},
            "source": str(source),
            "challenge_tags": case["tags"],
        })
    suite = {
        "schema": "aigc-style-benchmark-suite/v1",
        "suite_id": suite_id,
        "version": "v1",
        "split": split,
        "providers": ["humanizer-zh"],
        "benchmark_goal": "improvement",
        "required_trials": 3,
        "cases": suite_cases,
    }
    if split == "holdout":
        suite["holdout_policy"] = {"curator": "评测保管人", "release_id": "release-2026"}
    suite_path = root / f"{suite_id}.json"
    write_json(suite_path, suite)
    _, manifest = init_suite(suite_path, root / f"{suite_id}-run", registry)
    current = manifest
    first_case = cases[0]
    first_source = source_dir / f"{first_case['id']}.txt"
    whitespace_only = root / f"{suite_id}-{first_case['id']}-whitespace-only.txt"
    whitespace_only.write_text(first_source.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    whitespace_verification, whitespace_generation = make_candidate_evidence(
        root, registry, suite_id, first_case["id"], "whitespace-only",
        first_source, whitespace_only,
    )
    try:
        register_candidate(
            current, first_case["id"], "humanizer-zh", 1, whitespace_only,
            whitespace_verification, root / f"{suite_id}-whitespace-accepted.json",
            registry, whitespace_generation,
        )
    except ValueError as exc:
        require(
            "substantive content change" in str(exc),
            "whitespace-only candidate was rejected for the wrong reason", str(exc),
        )
    else:
        raise AssertionError("whitespace-only candidate was accepted as a benchmark trial")

    improvement_no_change = root / f"{suite_id}-{first_case['id']}-no-change.txt"
    improvement_no_change.write_text(first_source.read_text(encoding="utf-8"), encoding="utf-8")
    no_change_verification, no_change_generation = make_candidate_evidence(
        root, registry, suite_id, first_case["id"], "no-change",
        first_source, improvement_no_change, "NO_CHANGE",
    )
    try:
        register_candidate(
            current, first_case["id"], "humanizer-zh", 1, improvement_no_change,
            no_change_verification, root / f"{suite_id}-no-change-accepted.json",
            registry, no_change_generation,
        )
    except ValueError as exc:
        require(
            "improvement benchmarks require" in str(exc),
            "improvement NO_CHANGE was rejected for the wrong reason", str(exc),
        )
    else:
        raise AssertionError("improvement benchmark accepted NO_CHANGE")

    trial_suffixes = (
        "这里保留原参数，并把触发对象和结论边界写在同一句群中。",
        "复核原记录后，参数值不变；变化发生在事件归属，而非数值口径。",
        "该判断只适用于当前阈值附近，越过区间后需要重新检查触发次序。",
    )
    candidate_paths: dict[tuple[str, int], Path] = {}
    for case in cases:
        for trial in range(1, 4):
            candidate = root / f"{suite_id}-{case['id']}-t{trial}.txt"
            candidate.write_text(
                case["candidate_prefix"] + " " + trial_suffixes[trial - 1],
                encoding="utf-8",
            )
            source_path = source_dir / f"{case['id']}.txt"
            verification_path, generation = make_candidate_evidence(
                root, registry, suite_id, case["id"], f"t{trial}", source_path, candidate,
            )
            candidate_paths[(case["id"], trial)] = candidate
            if case["id"] == cases[0]["id"] and trial == 1:
                try:
                    register_candidate(
                        current, case["id"], "humanizer-zh", trial, candidate,
                        verification_path,
                        root / f"{suite_id}-missing-generation.json", registry,
                        root / "missing-generation.json",
                    )
                except FileNotFoundError:
                    pass
                else:
                    raise AssertionError("candidate without native generation evidence was accepted")
            if case["id"] == cases[0]["id"] and trial == 2:
                duplicate_content = root / f"{suite_id}-{case['id']}-t2-content-duplicate.txt"
                duplicate_content.write_text(
                    candidate_paths[(case["id"], 1)].read_text(encoding="utf-8") + "\n\n",
                    encoding="utf-8",
                )
                duplicate_verification, duplicate_content_generation = make_candidate_evidence(
                    root, registry, suite_id, case["id"], "t2-content-duplicate",
                    source_path, duplicate_content,
                )
                try:
                    register_candidate(
                        current, case["id"], "humanizer-zh", trial, duplicate_content,
                        duplicate_verification, root / f"{suite_id}-duplicate-content.json",
                        registry, duplicate_content_generation,
                    )
                except ValueError as exc:
                    require(
                        "normalized duplicate or near-duplicate" in str(exc),
                        "duplicate trial content was rejected for the wrong reason", str(exc),
                    )
                else:
                    raise AssertionError("normalized duplicate trial content was accepted")
                duplicate_generation = root / f"generation-{suite_id}-{case['id']}-t{trial}-duplicate.json"
                duplicate_payload = json.loads(generation.read_text(encoding="utf-8"))
                duplicate_payload["execution"]["run_id"] = f"{suite_id}-{case['id']}-t1"
                write_json(duplicate_generation, duplicate_payload)
                try:
                    register_candidate(
                        current, case["id"], "humanizer-zh", trial, candidate,
                        verification_path,
                        root / f"{suite_id}-duplicate-run.json", registry, duplicate_generation,
                    )
                except ValueError as exc:
                    require("run_id already registered" in str(exc), "wrong duplicate run rejection", str(exc))
                else:
                    raise AssertionError("duplicate generation run_id was accepted")
            output = root / f"{suite_id}-{case['id']}-t{trial}-registered.json"
            _, current = register_candidate(
                current, case["id"], "humanizer-zh", trial, candidate,
                verification_path, output, registry, generation,
            )
            if case["id"] == cases[0]["id"] and trial == 1:
                try:
                    register_candidate(
                        current, case["id"], "humanizer-zh", trial, candidate,
                        verification_path,
                        root / f"{suite_id}-duplicate.json", registry, generation,
                    )
                except ValueError:
                    pass
                else:
                    raise AssertionError("duplicate trial registration was accepted")
    _, blind_ready = prepare_benchmark(current, 2026, root / f"{suite_id}-blind-ready.json", registry)
    ready_audit = audit_manifest(blind_ready, registry)
    require(
        ready_audit["status"] == "pass" and ready_audit["rule_freshness"] == "current-bound",
        "new benchmark did not bind the current writing rules", ready_audit,
    )
    historical_path = root / f"{suite_id}-historical-unbound.json"
    historical_payload = json.loads(blind_ready.read_text(encoding="utf-8"))
    historical_payload["suite"].pop("writing_rule_snapshot", None)
    write_json(historical_path, historical_payload)
    historical_audit = audit_manifest(historical_path, registry)
    require(
        historical_audit["status"] == "pass"
        and historical_audit["rule_freshness"] == "historical-unbound"
        and any(item["code"] == "BENCHMARK_WRITING_RULE_SNAPSHOT_MISSING" for item in historical_audit["findings"]),
        "legacy benchmark was not marked historical-unbound", historical_audit,
    )
    protocol_drift = root / f"{suite_id}-scoring-protocol-drift.json"
    protocol_payload = json.loads(blind_ready.read_text(encoding="utf-8"))
    protocol_payload["blind"]["scoring_rules"][0]["sha256"] = "0" * 64
    write_json(protocol_drift, protocol_payload)
    protocol_audit = audit_manifest(protocol_drift, registry)
    require(
        protocol_audit["status"] == "fail"
        and any(
            item["code"] == "BENCHMARK_FILE_DRIFT" and item.get("label") == "blind.scoring_rules[0]"
            for item in protocol_audit["findings"]
        ),
        "scoring-rule drift was not rejected",
        protocol_audit,
    )
    packet_text = Path(json.loads(blind_ready.read_text(encoding="utf-8"))["blind"]["packet"]["path"]).read_text(encoding="utf-8")
    require("humanizer-zh" not in packet_text and "::t" not in packet_text, "blind packet leaked provider metadata", packet_text)
    model_ratings = root / f"{suite_id}-model-ratings.csv"
    write_ratings(blind_ready, model_ratings, rater_kind="model")
    probe = probe_benchmark(
        blind_ready, model_ratings, root / f"{suite_id}-model-probe.json", registry,
    )
    require(
        probe["evaluation_level"] == "MODEL_PROBE_ONLY"
        and probe["formal_human_ready"] is False
        and all(value == 0 for value in probe["human_coverage"].values()),
        "model probe contaminated formal human coverage", probe,
    )
    unmerged = root / f"{suite_id}-ratings-unmerged.csv"
    write_ratings(blind_ready, unmerged, "causal-boundary" if include_bad_case else None)
    with unmerged.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        rating_rows = list(reader)
    single_files = []
    for rater_id in ("R1", "R2"):
        single = root / f"{suite_id}-ratings-{rater_id}.csv"
        with single.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(row for row in rating_rows if row["rater_id"] == rater_id)
        single_files.append(single)
    ratings = root / f"{suite_id}-ratings.csv"
    merge_report = root / f"{suite_id}-ratings-merge.json"
    manifest_payload = json.loads(blind_ready.read_text(encoding="utf-8"))
    merge_ratings(
        Path(manifest_payload["blind"]["packet"]["path"]),
        single_files,
        ratings,
        merge_report,
    )
    try:
        score_benchmark(
            historical_path, ratings, merge_report,
            root / f"{suite_id}-historical-score.json", registry,
        )
    except ValueError as exc:
        require(
            "current-bound writing-rule snapshot" in str(exc),
            "historical benchmark was rejected for the wrong reason", str(exc),
        )
    else:
        raise AssertionError("historical-unbound benchmark was accepted for formal scoring")
    forged_merge = root / f"{suite_id}-ratings-merge-forged.json"
    forged_payload = json.loads(merge_report.read_text(encoding="utf-8"))
    forged_payload["output"]["sha256"] = "0" * 64
    write_json(forged_merge, forged_payload)
    try:
        score_benchmark(
            blind_ready, ratings, forged_merge,
            root / f"{suite_id}-forged-score.json", registry,
        )
    except ValueError as exc:
        require("merge audit failed" in str(exc), "forged merge failed for the wrong reason", str(exc))
    else:
        raise AssertionError("forged ratings merge report was accepted")
    _, scored = score_benchmark(
        blind_ready, ratings, merge_report, root / f"{suite_id}-scored.json", registry,
    )
    final = json.loads(scored.read_text(encoding="utf-8"))
    expected_state = "SCORED_HOLDOUT_SEALED" if split == "holdout" else "SCORED_DEV"
    require(final["state"] == expected_state, "scored state is incorrect", final)
    audited = audit_manifest(scored, registry)
    require(audited["status"] == "pass", "scored manifest failed audit", audited)
    if include_bad_case:
        failures = json.loads(Path(final["score"]["failure_capsules"]["path"]).read_text(encoding="utf-8"))
        require(
            any(
                item["case_id"] == "causal-boundary" and item["dimension"] == "semantic_fidelity"
                and item["severity"] == "error"
                for item in failures["failures"]
            ),
            "semantic loss did not become a high-severity failure capsule",
            failures,
        )
        consistency = final["score"]["summary"]["consistency"]
        require(
            any(item["case_id"] == "event-switch" for item in consistency),
            "per-case multi-trial consistency was not recorded",
            consistency,
        )
    return scored


def run_preservation_suite(root: Path, registry: Path) -> None:
    source = root / "preservation-source.txt"
    source.write_text("参数跨过阈值后，首次触发对象由构件 A 切换为构件 B。", encoding="utf-8")
    suite = {
        "schema": "aigc-style-benchmark-suite/v1",
        "suite_id": "preservation-dev",
        "version": "v1",
        "split": "dev",
        "benchmark_goal": "preservation",
        "providers": ["humanizer-zh"],
        "required_trials": 3,
        "cases": [{
            "id": "event-object",
            "scene": {"document_type": "general-zh", "document_format": "plain", "scope": "document"},
            "source": str(source),
            "challenge_tags": ["public-judgment", "semantic-fidelity"],
        }],
    }
    suite_path = root / "preservation-suite.json"
    write_json(suite_path, suite)
    _, current = init_suite(suite_path, root / "preservation-run", registry)
    variants = (
        ("NO_CHANGE", source.read_text(encoding="utf-8")),
        ("NO_CHANGE", source.read_text(encoding="utf-8") + "\n\n"),
        ("REWRITE", "参数越过阈值前，构件 A 首先触发；越过阈值后，首次触发对象转为构件 B。"),
    )
    for trial, (decision, text_value) in enumerate(variants, start=1):
        candidate = root / f"preservation-t{trial}.txt"
        candidate.write_text(text_value, encoding="utf-8")
        verification, generation = make_candidate_evidence(
            root, registry, "preservation", "event-object", f"t{trial}",
            source, candidate, decision,
        )
        output = root / f"preservation-r{trial}.json"
        _, current = register_candidate(
            current, "event-object", "humanizer-zh", trial, candidate,
            verification, output, registry, generation,
        )
    _, ready = prepare_benchmark(
        current, 2027, root / "preservation-blind-ready.json", registry,
    )
    report = audit_manifest(ready, registry)
    require(
        report["status"] == "pass" and report["benchmark_goal"] == "preservation",
        "preservation suite rejected valid NO_CHANGE decisions", report,
    )

    mismatch = root / "preservation-mismatch.txt"
    mismatch.write_text("阈值变化后触发对象发生切换，原有对象不再保持。", encoding="utf-8")
    verification, generation = make_candidate_evidence(
        root, registry, "preservation-mismatch", "event-object", "mismatch",
        source, mismatch, "NO_CHANGE",
    )
    _, fresh = init_suite(suite_path, root / "preservation-mismatch-run", registry)
    try:
        register_candidate(
            fresh, "event-object", "humanizer-zh", 1, mismatch,
            verification, root / "preservation-mismatch-accepted.json", registry, generation,
        )
    except ValueError as exc:
        require(
            "NO_CHANGE decision does not match" in str(exc),
            "mismatched NO_CHANGE failed for the wrong reason", str(exc),
        )
    else:
        raise AssertionError("NO_CHANGE was accepted for substantively changed content")


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    with tempfile.TemporaryDirectory(prefix="aigc-style-benchmark-") as temp:
        root = Path(temp)
        run_preservation_suite(root, registry)
        dev = run_suite(root, registry, "general-zh-dev", "dev", True)
        holdout = run_suite(root, registry, "general-zh-holdout", "holdout", False)
        portfolio_path = root / "portfolio.json"
        portfolio = aggregate([dev, holdout], portfolio_path, registry)
        require(
            portfolio["status"] == "HUMAN_EVIDENCE_AGGREGATED"
            and len(portfolio["suites"]) == 2
            and "general-zh" in portfolio["by_scene"],
            "dev and holdout results were not aggregated", portfolio,
        )

        duplicate_payload = json.loads(dev.read_text(encoding="utf-8"))
        duplicate_payload["suite"]["id"] = "general-zh-dev-copy"
        duplicate = root / "duplicate-source-scored.json"
        write_json(duplicate, duplicate_payload)
        duplicate_audit = audit_manifest(duplicate, registry)
        require(duplicate_audit["status"] == "pass", "duplicate fixture became invalid", duplicate_audit)
        try:
            aggregate([dev, duplicate], root / "duplicate-source-portfolio.json", registry)
        except ValueError as exc:
            require("must not reuse text" in str(exc), "wrong duplicate-source rejection", str(exc))
        else:
            raise AssertionError("aggregate accepted a dev/holdout source reuse")

        final = json.loads(holdout.read_text(encoding="utf-8"))
        try:
            register_candidate(
                holdout, "event-switch", "humanizer-zh", 1,
                Path(final["candidates"][0]["candidate"]["path"]),
                Path(final["candidates"][0]["verification"]["path"]),
                root / "post-seal-register.json", registry,
                Path(final["candidates"][0]["generation"]["path"]),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("sealed holdout accepted a new candidate")

        drifted = Path(final["candidates"][0]["candidate"]["path"])
        original = drifted.read_text(encoding="utf-8")
        drifted.write_text(original + " 漂移。", encoding="utf-8")
        drift_report = audit_manifest(holdout, registry)
        require(
            drift_report["status"] == "fail"
            and any(item["code"] == "BENCHMARK_FILE_DRIFT" for item in drift_report["findings"]),
            "candidate drift was not detected in the sealed benchmark", drift_report,
        )
    print(
        "PASS: dev/holdout suites require substantive independent trials, hide provenance, retain "
        "per-case failures, seal holdout after scoring, and reject post-score drift."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
