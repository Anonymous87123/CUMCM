#!/usr/bin/env python3
"""Verify a published short PATCH directory as a closed self-consistency record."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import apply_humanize_short_patch as applicator  # noqa: E402
import build_humanize_short_patch as short_patch  # noqa: E402
import validate_humanize_output as unified_validator  # noqa: E402


ShortPatchError = short_patch.ShortPatchError
coverage_layer = short_patch.coverage_layer
VERIFICATION_SCHEMA = "humanize-short-patch-verification/v3"
MANIFEST_FIELDS = {"schema_version", "integrity_scope", "artifacts", "manifest_sha256"}
ARTIFACT_FIELDS = {"path", "size", "sha256"}
FIXED_ARTIFACTS = {
    "source.snapshot.bin",
    "patch.diff",
    "patch.bundle.json",
    "validation.json",
    "result.json",
}
OPTIONAL_ARTIFACTS = {"coverage.json", "review.md"}
ALLOWED_CANDIDATE_NAMES = {
    "candidate.review.md",
    "candidate.review.tex",
    "candidate.review.txt",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _StrictArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise ShortPatchError("INVALID_ARGUMENTS")


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ShortPatchError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _root(path: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(path)))
    short_patch._assert_no_reparse_chain(root, "evidence directory")
    try:
        metadata = os.stat(root, follow_symlinks=False)
    except OSError as error:
        raise ShortPatchError("evidence directory is missing") from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise ShortPatchError("evidence directory must be a regular directory")
    return root


def _manifest_hash(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    return short_patch.sha256(short_patch.canonical_json(unsigned))


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = short_patch._regular_input(path, label, short_patch.MAX_JSON_BYTES)
    payload = short_patch.strict_json_bytes(raw, label)
    if not isinstance(payload, dict):
        raise ShortPatchError(f"{label} must be an object")
    return payload, raw


def _current_policy_hashes() -> dict[str, str]:
    return unified_validator._policy_hashes()


def _recorded_policy_hashes(validation: Mapping[str, Any]) -> dict[str, str]:
    evidence = validation.get("evidence")
    if not isinstance(evidence, dict):
        raise ShortPatchError("validation evidence is missing")
    policy = evidence.get("policy_hashes")
    if not isinstance(policy, dict) or not policy:
        raise ShortPatchError("validation policy_hashes are missing")
    for key, value in policy.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or not SHA256_RE.fullmatch(value)
        ):
            raise ShortPatchError("validation policy_hashes are invalid")
    return dict(policy)


def _replay_validation(
    source: bytes,
    candidate: bytes,
    candidate_name: str,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="humanize-short-patch-replay-") as temp:
        root = Path(temp)
        source_path = root / "source.snapshot.bin"
        candidate_path = root / candidate_name
        source_path.write_bytes(source)
        candidate_path.write_bytes(candidate)
        replayed, _raw = applicator._run_validator(source_path, candidate_path, bundle)
    return replayed


def _live_source_status(path: Path | None, expected_sha256: str) -> dict[str, Any]:
    if path is None:
        return {
            "status": "NOT_PROVIDED",
            "expected_sha256": expected_sha256,
            "path_binding": "NOT_PROVIDED",
            "freshness_claim_allowed": False,
        }
    try:
        observed = short_patch.read_source(path)
    except (OSError, ShortPatchError):
        return {
            "status": "UNAVAILABLE",
            "expected_sha256": expected_sha256,
            "path_binding": "UNVERIFIED_CALLER_PATH",
            "freshness_claim_allowed": False,
        }
    observed_sha256 = short_patch.sha256(observed)
    return {
        # The evidence package intentionally does not retain an absolute source
        # path.  A caller-supplied path can therefore be compared by bytes, but
        # it cannot prove that it is the work file used to create the record.
        "status": (
            "CALLER_SUPPLIED_MATCH_UNVERIFIED"
            if observed_sha256 == expected_sha256
            else "CALLER_SUPPLIED_NOT_CURRENT"
        ),
        "expected_sha256": expected_sha256,
        "observed_sha256": observed_sha256,
        "path_binding": "UNVERIFIED_CALLER_PATH",
        "freshness_claim_allowed": False,
    }


def _live_source_reasons(status: Mapping[str, Any]) -> list[str]:
    value = status.get("status")
    if value == "NOT_PROVIDED":
        return []
    if value == "UNAVAILABLE":
        return ["LIVE_SOURCE_UNAVAILABLE"]
    if value == "CALLER_SUPPLIED_NOT_CURRENT":
        return ["LIVE_SOURCE_NOT_CURRENT", "LIVE_SOURCE_PATH_BINDING_UNVERIFIED"]
    if value == "CALLER_SUPPLIED_MATCH_UNVERIFIED":
        return ["LIVE_SOURCE_PATH_BINDING_UNVERIFIED"]
    raise ShortPatchError("live_source_status is invalid")


def _review_result(
    base: dict[str, Any],
    *,
    policy_status: str,
    replay_status: str,
    live_status: dict[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        **base,
        "status": "REVIEW",
        "exit_code": 2,
        "current_policy_status": policy_status,
        "current_policy_replay_status": replay_status,
        "live_source_status": live_status,
        "review_reasons": reasons,
    }


def verify_directory(
    path: Path,
    *,
    live_source: Path | None = None,
) -> dict[str, Any]:
    root = _root(path)
    manifest, _manifest_raw = _load_json(
        root / "evidence-manifest.json", "evidence manifest"
    )
    _exact_fields(manifest, MANIFEST_FIELDS, "evidence manifest")
    if manifest.get("schema_version") != applicator.EVIDENCE_MANIFEST_SCHEMA:
        raise ShortPatchError("evidence manifest schema_version is invalid")
    if manifest.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
        raise ShortPatchError("evidence manifest integrity_scope is invalid")
    if manifest.get("manifest_sha256") != _manifest_hash(manifest):
        raise ShortPatchError("evidence manifest_sha256 mismatch")
    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise ShortPatchError("evidence manifest artifacts must be non-empty")
    records: dict[str, dict[str, Any]] = {}
    candidate_names: list[str] = []
    for index, entry in enumerate(entries):
        label = f"evidence manifest.artifacts[{index}]"
        if not isinstance(entry, dict):
            raise ShortPatchError(f"{label} must be an object")
        _exact_fields(entry, ARTIFACT_FIELDS, label)
        name = entry.get("path")
        if not isinstance(name, str) or not name or name in records:
            raise ShortPatchError(f"{label}.path is invalid or duplicate")
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ShortPatchError(f"{label}.path must be a basename")
        if name in ALLOWED_CANDIDATE_NAMES:
            candidate_names.append(name)
        elif name not in FIXED_ARTIFACTS | OPTIONAL_ARTIFACTS:
            raise ShortPatchError(f"{label}.path is not an allowed artifact")
        size = entry.get("size")
        digest = entry.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ShortPatchError(f"{label}.size is invalid")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ShortPatchError(f"{label}.sha256 is invalid")
        records[name] = entry
    record_names = set(records)
    if (
        not FIXED_ARTIFACTS.issubset(record_names)
        or record_names - FIXED_ARTIFACTS - OPTIONAL_ARTIFACTS - set(candidate_names)
        or len(candidate_names) != 1
    ):
        raise ShortPatchError("evidence manifest artifact roles are incomplete")
    actual = {
        child.name
        for child in root.iterdir()
        if child.is_file() or child.is_symlink()
    }
    expected = {*records, "evidence-manifest.json"}
    if actual != expected or any(child.is_dir() for child in root.iterdir()):
        raise ShortPatchError("evidence directory is not a closed file set")
    artifact_bytes: dict[str, bytes] = {}
    for name, record in records.items():
        raw = short_patch._regular_input(root / name, f"artifact {name}")
        if len(raw) != record["size"]:
            raise ShortPatchError(f"artifact_size mismatch: {name}")
        if short_patch.sha256(raw) != record["sha256"]:
            raise ShortPatchError(f"artifact_sha256 mismatch: {name}")
        artifact_bytes[name] = raw

    source = short_patch.read_source(root / "source.snapshot.bin")
    bundle, bundle_raw = short_patch.load_bundle(
        root / "patch.bundle.json",
        source,
        require_current_coverage_policy=False,
    )
    candidate_name = candidate_names[0]
    candidate = artifact_bytes[candidate_name]
    if applicator._apply_bytes(source, bundle) != candidate:
        raise ShortPatchError("candidate is not the deterministic bundle application")
    if applicator._diff(source, candidate) != artifact_bytes["patch.diff"]:
        raise ShortPatchError("patch.diff does not match source and candidate")
    if bundle_raw != artifact_bytes["patch.bundle.json"]:
        raise ShortPatchError("bundle bytes changed during verification")
    coverage_present = bundle.get("schema_version") in {
        short_patch.BUNDLE_SCHEMA_V2,
        short_patch.BUNDLE_SCHEMA_V3,
    }
    if coverage_present != ("coverage.json" in artifact_bytes):
        raise ShortPatchError("coverage artifact role does not match bundle schema")
    coverage_policy_status = "NOT_PROVIDED"
    coverage_replay_status = "NOT_RUN"
    amendment_lineage_policy_status = "NOT_PROVIDED"
    if coverage_present:
        coverage_artifact = short_patch.strict_json_bytes(
            artifact_bytes["coverage.json"], "coverage artifact"
        )
        if coverage_artifact != bundle.get("coverage"):
            raise ShortPatchError("coverage artifact does not match the bound bundle")
        try:
            _coverage_replayed, coverage_replay_status = coverage_layer.replay_coverage(
                source,
                hunks=bundle["hunks"],
                recorded=bundle["coverage"],
            )
        except coverage_layer.CoverageError as error:
            raise ShortPatchError(str(error)) from error
        coverage_policy_status = (
            "PASS" if coverage_replay_status == "PASS" else "DRIFT"
        )
        if coverage_replay_status == "DRIFT":
            coverage_replay_status = "NOT_RUN"
        if bundle.get("schema_version") == short_patch.BUNDLE_SCHEMA_V3:
            amendment_lineage_policy_status = "PASS"
            parent = bundle["amendment"]["parent_bundle"]
            while True:
                _parent_replayed, parent_status = coverage_layer.replay_coverage(
                    source,
                    hunks=parent["hunks"],
                    recorded=parent["coverage"],
                )
                if parent_status != "PASS":
                    amendment_lineage_policy_status = "DRIFT"
                    coverage_policy_status = "DRIFT"
                    break
                if parent.get("schema_version") != short_patch.BUNDLE_SCHEMA_V3:
                    break
                parent = parent["amendment"]["parent_bundle"]

    validation = short_patch.strict_json_bytes(
        artifact_bytes["validation.json"], "validation artifact"
    )
    result = short_patch.strict_json_bytes(artifact_bytes["result.json"], "result artifact")
    if not isinstance(validation, dict) or not isinstance(result, dict):
        raise ShortPatchError("validation and result artifacts must be objects")
    result_fields = set(result)
    if frozenset(result_fields) not in {
        frozenset(applicator.LEGACY_RESULT_FIELDS),
        frozenset(applicator.TRANSITIONAL_RESULT_FIELDS),
        frozenset(applicator.CURRENT_RESULT_FIELDS_V1),
        frozenset(applicator.CURRENT_RESULT_FIELDS),
    }:
        raise ShortPatchError("result fields drifted")
    current_result_v1 = result_fields == applicator.CURRENT_RESULT_FIELDS_V1
    current_result_v2 = result_fields == applicator.CURRENT_RESULT_FIELDS
    scoped_result = current_result_v1 or current_result_v2
    review_present = "review.md" in artifact_bytes
    if current_result_v2 != review_present:
        raise ShortPatchError("review artifact role does not match result schema")
    evidence = validation.get("evidence")
    if not isinstance(evidence, dict):
        raise ShortPatchError("validation evidence is missing")
    if evidence.get("before_sha256") != short_patch.sha256(source):
        raise ShortPatchError("validation before_sha256 mismatch")
    if evidence.get("after_sha256") != short_patch.sha256(candidate):
        raise ShortPatchError("validation after_sha256 mismatch")
    if (
        bundle.get("document_format") is not None
        and evidence.get("document_format") != bundle["document_format"]
    ):
        raise ShortPatchError("validation document_format does not match the bound bundle")
    required_result = {
        "schema_version": (
            applicator.RESULT_SCHEMA
            if current_result_v2
            else applicator.RESULT_SCHEMA_V1
        ),
        "status": "REVIEW",
        "delivery_gate_status": "REVIEW",
        "exit_code": 2,
        "structural_validation_status": "PASS",
        "patch_application_status": "PASS",
        "semantic_judgment": "NOT_EVALUATED",
        "source_sha256": short_patch.sha256(source),
        "candidate_sha256": short_patch.sha256(candidate),
        "bundle_sha256": bundle["bundle_sha256"],
        "candidate_path": candidate_name,
        "diff_path": "patch.diff",
        "bundle_path": "patch.bundle.json",
        "validation_path": "validation.json",
        "source_snapshot_path": "source.snapshot.bin",
        "evidence_manifest_path": "evidence-manifest.json",
        "humanize_quality_claim_allowed": False,
        "completion_claim_allowed": False,
    }
    if scoped_result:
        required_result["delivery_gate_exit_code"] = 2
    if current_result_v2:
        required_result["review_path"] = "review.md"
    coverage_result_fields = {
        "coverage_path": "coverage.json" if coverage_present else None,
        "coverage_status": "PASS" if coverage_present else "NOT_PROVIDED",
        "coverage_completion_claim_allowed": coverage_present,
        "semantic_completeness_claim_allowed": False,
    }
    if coverage_present or any(key in result for key in coverage_result_fields):
        required_result.update(coverage_result_fields)
    if scoped_result:
        required_result.update(
            {
                "coverage_claim_scope": (
                    bundle["coverage"]["coverage_claim_scope"]
                    if coverage_present
                    else None
                ),
                "coverage_scene": (
                    bundle["coverage"]["source"]["scene"]
                    if coverage_present
                    else None
                ),
                "coverage_scan_scene": (
                    bundle["coverage"]["source"]["scan_scene"]
                    if coverage_present
                    else None
                ),
                "coverage_source_kind": (
                    bundle["coverage"]["source"]["source_kind"]
                    if coverage_present
                    else None
                ),
            }
        )
    for key, expected_value in required_result.items():
        if result.get(key) != expected_value:
            raise ShortPatchError(f"result field mismatch: {key}")
    expected_artifacts = [
        candidate_name,
        *(["coverage.json"] if coverage_present else []),
        *(["review.md"] if current_result_v2 else []),
        "patch.diff",
        "patch.bundle.json",
        "source.snapshot.bin",
        "validation.json",
        "result.json",
        "evidence-manifest.json",
    ]
    if result.get("artifacts_written") != expected_artifacts:
        raise ShortPatchError("result artifacts_written does not match the closed file set")
    if result.get("validator_exit_code") != validation.get("exit_code"):
        raise ShortPatchError("result validator_exit_code mismatch")
    if result.get("validator_delivery_gate_status") != validation.get("delivery_gate_status"):
        raise ShortPatchError("result validator_delivery_gate_status mismatch")
    if result.get("unified_validator_status") != validation.get("mechanical_validation_status"):
        raise ShortPatchError("result unified_validator_status mismatch")
    if result.get("hard_invariant_layer_status") != validation.get("hard_invariant_layer_status"):
        raise ShortPatchError("result hard_invariant_layer_status mismatch")
    if result.get("paired_quality_review_status") != validation.get("paired_quality_review_status"):
        raise ShortPatchError("result paired_quality_review_status mismatch")
    expected_counts = {decision: 0 for decision in sorted(short_patch.ALLOWED_DECISIONS)}
    for hunk in bundle["hunks"]:
        expected_counts[hunk["decision"]] += 1
    if result.get("decision_counts") != expected_counts:
        raise ShortPatchError("result decision_counts mismatch")
    if result.get("hunks_total") != len(bundle["hunks"]):
        raise ShortPatchError("result hunks_total mismatch")
    if result.get("unresolved_total") != expected_counts["UNRESOLVED"]:
        raise ShortPatchError("result unresolved_total mismatch")
    if result.get("patch_hunks_source_partition") != "NON_OVERLAPPING":
        raise ShortPatchError("result patch_hunks_source_partition mismatch")
    if result.get("unlisted_source_policy") != "COPY_EXACT":
        raise ShortPatchError("result unlisted_source_policy mismatch")
    if current_result_v2:
        expected_review = applicator._review_markdown(bundle, result, validation)
        if artifact_bytes["review.md"] != expected_review:
            raise ShortPatchError("review artifact does not match bound inputs")
    expected_source_sha256 = short_patch.sha256(source)
    live_status = _live_source_status(live_source, expected_source_sha256)
    base = {
        "schema_version": VERIFICATION_SCHEMA,
        "record_integrity_status": "PASS",
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
        "manifest_sha256": manifest["manifest_sha256"],
        "source_sha256": expected_source_sha256,
        "candidate_sha256": short_patch.sha256(candidate),
        "delivery_gate_status": "REVIEW",
        "delivery_gate_exit_code": 2,
        "coverage_policy_status": coverage_policy_status,
        "coverage_replay_status": coverage_replay_status,
        "coverage_completion_claim_allowed": bool(
            coverage_present
            and coverage_replay_status == "PASS"
            and amendment_lineage_policy_status != "DRIFT"
        ),
        "coverage_claim_scope": (
            bundle["coverage"]["coverage_claim_scope"] if coverage_present else None
        ),
        "coverage_scene": (
            bundle["coverage"]["source"]["scene"] if coverage_present else None
        ),
        "coverage_scan_scene": (
            bundle["coverage"]["source"]["scan_scene"] if coverage_present else None
        ),
        "coverage_source_kind": (
            bundle["coverage"]["source"]["source_kind"] if coverage_present else None
        ),
        "semantic_completeness_claim_allowed": False,
        "humanize_quality_claim_allowed": False,
        "completion_claim_allowed": False,
        "academic_correctness": "NOT_EVALUATED",
        "review_artifact_status": "PASS" if current_result_v2 else "NOT_PROVIDED",
        "amendment_lineage_status": (
            "PASS"
            if bundle.get("schema_version") == short_patch.BUNDLE_SCHEMA_V3
            else "NOT_PROVIDED"
        ),
        "amendment_lineage_policy_status": amendment_lineage_policy_status,
        "amendment_depth": (
            bundle["amendment"]["amendment_depth"]
            if bundle.get("schema_version") == short_patch.BUNDLE_SCHEMA_V3
            else 0
        ),
        "parent_bundle_sha256": (
            bundle["amendment"]["parent_bundle"]["bundle_sha256"]
            if bundle.get("schema_version") == short_patch.BUNDLE_SCHEMA_V3
            else None
        ),
        "amended_hunk_ids": (
            [item["hunk_id"] for item in bundle["amendment"]["changed_hunks"]]
            if bundle.get("schema_version") == short_patch.BUNDLE_SCHEMA_V3
            else []
        ),
    }
    recorded_policy = _recorded_policy_hashes(validation)
    try:
        current_policy = _current_policy_hashes()
    except (OSError, ValueError):
        reasons = ["CURRENT_POLICY_UNAVAILABLE"]
        reasons.extend(_live_source_reasons(live_status))
        return _review_result(
            base,
            policy_status="UNAVAILABLE",
            replay_status="NOT_RUN",
            live_status=live_status,
            reasons=reasons,
        )
    if recorded_policy != current_policy:
        reasons = ["POLICY_DRIFT"]
        if coverage_policy_status == "DRIFT":
            reasons.append("COVERAGE_POLICY_DRIFT")
        if amendment_lineage_policy_status == "DRIFT":
            reasons.append("AMENDMENT_LINEAGE_POLICY_DRIFT")
        reasons.extend(_live_source_reasons(live_status))
        return _review_result(
            base,
            policy_status="DRIFT",
            replay_status="NOT_RUN",
            live_status=live_status,
            reasons=reasons,
        )
    try:
        replayed = _replay_validation(source, candidate, candidate_name, bundle)
    except OSError:
        reasons = ["CURRENT_POLICY_REPLAY_UNAVAILABLE"]
        reasons.extend(_live_source_reasons(live_status))
        return _review_result(
            base,
            policy_status="MATCH",
            replay_status="NOT_RUN",
            live_status=live_status,
            reasons=reasons,
        )
    replay_policy = _recorded_policy_hashes(replayed)
    if replay_policy != current_policy:
        return _review_result(
            base,
            policy_status="CHANGED_DURING_REPLAY",
            replay_status="NOT_RUN",
            live_status=live_status,
            reasons=["POLICY_CHANGED_DURING_REPLAY"],
        )
    if replayed != validation:
        raise ShortPatchError("CURRENT_POLICY_REPLAY_MISMATCH")
    reasons: list[str] = []
    if coverage_policy_status == "DRIFT":
        reasons.append("COVERAGE_POLICY_DRIFT")
    if amendment_lineage_policy_status == "DRIFT":
        reasons.append("AMENDMENT_LINEAGE_POLICY_DRIFT")
    reasons.extend(_live_source_reasons(live_status))
    if reasons:
        return _review_result(
            base,
            policy_status=(
                "PARTIAL_DRIFT" if coverage_policy_status == "DRIFT" else "MATCH"
            ),
            replay_status="PASS",
            live_status=live_status,
            reasons=reasons,
        )
    return {
        **base,
        "status": "PASS",
        "exit_code": 0,
        "current_policy_status": "MATCH",
        "current_policy_replay_status": "PASS",
        "live_source_status": live_status,
        "review_reasons": [],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = _StrictArgumentParser(
        description=(
            "Verify a short PATCH record, replay the current validator policy, and "
            "optionally compare a live source."
        )
    )
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument(
        "--live-source",
        type=Path,
        help=(
            "Optional caller-supplied source for a byte comparison. The path is "
            "not bound into the evidence package, so using it always keeps the "
            "result at REVIEW/2."
        ),
    )
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_requested = any(
        raw_argv[index] == "--format"
        and index + 1 < len(raw_argv)
        and raw_argv[index + 1] == "json"
        for index in range(len(raw_argv))
    )
    try:
        args = build_parser().parse_args(raw_argv)
        result = verify_directory(args.evidence_dir, live_source=args.live_source)
    except (OSError, ShortPatchError) as error:
        failure = {
            "schema_version": VERIFICATION_SCHEMA,
            "status": "FAIL",
            "exit_code": 1,
            "record_integrity_status": "FAIL",
            "integrity_scope": "SELF_CONSISTENCY_ONLY",
            "error": str(error),
            "humanize_quality_claim_allowed": False,
            "completion_claim_allowed": False,
        }
        print(
            json.dumps(failure, ensure_ascii=False)
            if json_requested
            else f"VERIFICATION FAIL exit=1\n{error}"
        )
        return 1
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif result["status"] == "REVIEW":
        print(
            "INTEGRITY PASS scope=SELF_CONSISTENCY_ONLY; "
            f"VERIFICATION REVIEW exit=2 current_policy={result['current_policy_status']} "
            f"replay={result['current_policy_replay_status']} "
            f"coverage_policy={result['coverage_policy_status']} "
            f"coverage_replay={result['coverage_replay_status']} "
            f"coverage_scope={result['coverage_claim_scope']} "
            f"live_source={result['live_source_status']['status']}; DELIVERY REVIEW"
        )
        print("review_reasons=" + ",".join(result["review_reasons"]))
    else:
        print(
            "INTEGRITY PASS exit=0 scope=SELF_CONSISTENCY_ONLY; "
            "CURRENT_POLICY_REPLAY PASS; "
            f"COVERAGE {result['coverage_policy_status']} "
            f"scope={result['coverage_claim_scope']}; DELIVERY REVIEW"
        )
        print("humanize_quality_claim_allowed=false; academic_correctness=NOT_EVALUATED")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
