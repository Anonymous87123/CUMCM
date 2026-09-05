#!/usr/bin/env python3
"""Strictly validate a humanize-academic-chinese Voice Profile artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_humanize_voice_profile import (  # noqa: E402
    DEDUP_POLICY_SHA256,
    ELIGIBLE_ORIGINS,
    MANIFEST_SCHEMA_VERSION,
    ROLE_POLICY_SHA256,
    SCENES,
    SHA256_RE,
    _expect_exact_keys,
    _is_int,
    _load_json_strict,
    _manifest_self_hash,
    _require_int,
    build_scene_default_profile,
    build_voice_profile,
    load_and_validate_profile,
)


SAMPLE_KEYS = {
    "sample_id",
    "locator",
    "origin",
    "scene",
    "complete_unit",
    "encoding",
    "decode_status",
    "file_size",
    "file_sha256",
    "role_map_sha256",
    "author_view_sha256",
    "complete_unit_sha256",
    "complete_unit_dedup_cluster_id",
    "complete_unit_dedup_relation",
    "complete_unit_is_representative",
    "analysis_unit_ids",
    "readable_author_chars_before_dedup",
    "readable_author_chars_after_dedup",
}
UNIT_KEYS = {
    "unit_id",
    "sample_id",
    "byte_start",
    "byte_end",
    "canonical_author_sha256",
    "dedup_sha256",
    "dedup_cluster_id",
    "dedup_relation",
    "is_representative",
    "readable_author_chars",
}


def _require_sha(value: Any, where: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{where} must be a lowercase SHA-256")
    return value


def validate_manifest_object(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("voice sample manifest must be an object")
    _expect_exact_keys(
        manifest,
        {
            "schema_version",
            "source_date_epoch",
            "allowed_root_id",
            "hash_spec",
            "sample_spec_sha256",
            "policy_binding",
            "samples",
            "role_ranges",
            "analysis_units",
            "aggregate",
            "manifest_sha256",
        },
        "manifest",
    )
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported voice sample manifest schema_version")
    epoch = manifest["source_date_epoch"]
    if epoch is not None and (not _is_int(epoch) or epoch < 0):
        raise ValueError("manifest.source_date_epoch must be null or a non-negative integer")
    if not isinstance(manifest["allowed_root_id"], str) or not re.fullmatch(r"[0-9a-f]{16}", manifest["allowed_root_id"]):
        raise ValueError("manifest.allowed_root_id is invalid")
    if manifest["hash_spec"] != {
        "algorithm": "SHA-256",
        "json_canonicalization": "PYTHON-SORTED-UTF8/v1",
        "text_integrity_view": "UTF8-NFC-LF/v1",
        "dedup_view": "VOICE-DEDUP/v1",
        "sample_spec_view": "STRICT-JSON-CANONICAL/v1",
    }:
        raise ValueError("manifest.hash_spec is stale or unknown")
    _require_sha(manifest["sample_spec_sha256"], "manifest.sample_spec_sha256")
    policies = manifest["policy_binding"]
    if not isinstance(policies, dict):
        raise ValueError("manifest.policy_binding must be an object")
    _expect_exact_keys(
        policies,
        {"role_policy_sha256", "dedup_policy_sha256", "unitizer_sha256"},
        "manifest.policy_binding",
    )
    if policies["role_policy_sha256"] != ROLE_POLICY_SHA256 or policies["dedup_policy_sha256"] != DEDUP_POLICY_SHA256:
        raise ValueError("manifest role/dedup policy binding is stale")
    _require_sha(policies["unitizer_sha256"], "manifest.policy_binding.unitizer_sha256")

    samples = manifest["samples"]
    if not isinstance(samples, list):
        raise ValueError("manifest.samples must be a list")
    sample_ids: set[str] = set()
    sample_by_id: dict[str, dict[str, Any]] = {}
    listed_unit_ids: list[str] = []
    complete_cluster_representatives: dict[str, str] = {}
    complete_cluster_ids: list[str] = []
    for index, sample in enumerate(samples):
        where = f"manifest.samples[{index}]"
        if not isinstance(sample, dict):
            raise ValueError(f"{where} must be an object")
        _expect_exact_keys(sample, SAMPLE_KEYS, where)
        sample_id = sample["sample_id"]
        if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
            raise ValueError(f"{where}.sample_id is invalid or duplicated")
        sample_ids.add(sample_id)
        sample_by_id[sample_id] = sample
        if not isinstance(sample["locator"], str) or not sample["locator"] or "\\" in sample["locator"]:
            raise ValueError(f"{where}.locator is invalid")
        if sample["origin"] not in {"USER_CONFIRMED_AUTHOR", "USER_CONFIRMED_ADOPTED", "UNKNOWN", "MODEL_GENERATED"}:
            raise ValueError(f"{where}.origin is invalid")
        if sample["scene"] not in SCENES or not isinstance(sample["complete_unit"], bool):
            raise ValueError(f"{where}.scene/complete_unit is invalid")
        if sample["encoding"] not in {"UTF-8", "UNKNOWN"}:
            raise ValueError(f"{where}.encoding is invalid")
        if sample["decode_status"] not in {
            "PASS",
            "SKIPPED_INVALID_UTF8",
            "SKIPPED_OCR_OR_MOJIBAKE",
            "SKIPPED_NFC_INDEX_DRIFT",
        }:
            raise ValueError(f"{where}.decode_status is invalid")
        _require_int(sample["file_size"], f"{where}.file_size")
        for field in ("file_sha256", "role_map_sha256", "author_view_sha256", "complete_unit_sha256"):
            _require_sha(sample[field], f"{where}.{field}")
        complete_cluster = sample["complete_unit_dedup_cluster_id"]
        complete_relation = sample["complete_unit_dedup_relation"]
        complete_representative = sample["complete_unit_is_representative"]
        if not isinstance(complete_representative, bool):
            raise ValueError(f"{where}.complete_unit_is_representative is invalid")
        has_complete_evidence = (
            sample["complete_unit"]
            and sample["origin"] in ELIGIBLE_ORIGINS
            and sample["decode_status"] == "PASS"
            and sample["complete_unit_sha256"] != "0" * 64
        )
        if has_complete_evidence:
            if not isinstance(complete_cluster, str) or not re.fullmatch(r"cluster-[0-9]{6}", complete_cluster):
                raise ValueError(f"{where}.complete_unit_dedup_cluster_id is invalid")
            if complete_relation not in {"UNIQUE", "EXACT", "NEAR"}:
                raise ValueError(f"{where}.complete_unit_dedup_relation is invalid")
            if complete_representative != (complete_relation == "UNIQUE"):
                raise ValueError(f"{where} complete-unit representative/relation disagree")
            complete_cluster_ids.append(complete_cluster)
            if complete_representative:
                if complete_cluster in complete_cluster_representatives:
                    raise ValueError(f"{where} duplicates a complete-unit cluster representative")
                complete_cluster_representatives[complete_cluster] = sample_id
        elif complete_cluster != "" or complete_relation != "NONE" or complete_representative:
            raise ValueError(f"{where} has complete-unit dedup evidence outside eligible scope")
        unit_ids = sample["analysis_unit_ids"]
        if not isinstance(unit_ids, list) or len(unit_ids) != len(set(unit_ids)) or any(not isinstance(item, str) for item in unit_ids):
            raise ValueError(f"{where}.analysis_unit_ids is invalid")
        listed_unit_ids.extend(unit_ids)
        before = _require_int(sample["readable_author_chars_before_dedup"], f"{where}.chars_before")
        after = _require_int(sample["readable_author_chars_after_dedup"], f"{where}.chars_after")
        if after > before:
            raise ValueError(f"{where} gains characters after dedup")
        if sample["decode_status"] != "PASS" and (before or after or unit_ids):
            raise ValueError(f"{where} skipped decoding but still contributes author evidence")
        if sample["origin"] not in ELIGIBLE_ORIGINS and (before or after or unit_ids):
            raise ValueError(f"{where} untrusted origin contributes author evidence")

    role_ranges = manifest["role_ranges"]
    if not isinstance(role_ranges, list):
        raise ValueError("manifest.role_ranges must be a list")
    previous_by_sample: dict[str, int] = defaultdict_int()
    for index, role_range in enumerate(role_ranges):
        where = f"manifest.role_ranges[{index}]"
        if not isinstance(role_range, dict):
            raise ValueError(f"{where} must be an object")
        _expect_exact_keys(role_range, {"sample_id", "byte_start", "byte_end", "role", "range_sha256"}, where)
        sample_id = role_range["sample_id"]
        if sample_id not in sample_ids:
            raise ValueError(f"{where} references an unknown sample")
        start = _require_int(role_range["byte_start"], f"{where}.byte_start")
        end = _require_int(role_range["byte_end"], f"{where}.byte_end")
        if end <= start or end > sample_by_id[sample_id]["file_size"]:
            raise ValueError(f"{where} byte interval is invalid")
        if start < previous_by_sample[sample_id]:
            raise ValueError(f"{where} role ranges overlap or are unsorted")
        previous_by_sample[sample_id] = end
        if role_range["role"] not in {"author", "quoted", "exam-original", "ocr", "code", "math", "template", "unknown"}:
            raise ValueError(f"{where}.role is invalid")
        _require_sha(role_range["range_sha256"], f"{where}.range_sha256")

    units = manifest["analysis_units"]
    if not isinstance(units, list):
        raise ValueError("manifest.analysis_units must be a list")
    unit_ids: set[str] = set()
    representative_ids: set[str] = set()
    cluster_representatives: dict[str, str] = {}
    exact_duplicates = 0
    near_duplicates = 0
    representative_chars = 0
    after_by_sample: dict[str, int] = defaultdict_int()
    for index, unit in enumerate(units):
        where = f"manifest.analysis_units[{index}]"
        if not isinstance(unit, dict):
            raise ValueError(f"{where} must be an object")
        _expect_exact_keys(unit, UNIT_KEYS, where)
        unit_id = unit["unit_id"]
        if not isinstance(unit_id, str) or not unit_id or unit_id in unit_ids:
            raise ValueError(f"{where}.unit_id is invalid or duplicated")
        unit_ids.add(unit_id)
        sample_id = unit["sample_id"]
        if sample_id not in sample_ids:
            raise ValueError(f"{where} references an unknown sample")
        start = _require_int(unit["byte_start"], f"{where}.byte_start")
        end = _require_int(unit["byte_end"], f"{where}.byte_end")
        if end <= start or end > sample_by_id[sample_id]["file_size"]:
            raise ValueError(f"{where} byte interval is invalid")
        for field in ("canonical_author_sha256", "dedup_sha256"):
            _require_sha(unit[field], f"{where}.{field}")
        if not isinstance(unit["dedup_cluster_id"], str) or not re.fullmatch(r"cluster-[0-9]{6}", unit["dedup_cluster_id"]):
            raise ValueError(f"{where}.dedup_cluster_id is invalid")
        relation = unit["dedup_relation"]
        if relation not in {"UNIQUE", "EXACT", "NEAR"} or not isinstance(unit["is_representative"], bool):
            raise ValueError(f"{where}.dedup relation is invalid")
        chars = _require_int(unit["readable_author_chars"], f"{where}.readable_author_chars", minimum=1)
        if unit["is_representative"]:
            if relation != "UNIQUE" or unit["dedup_cluster_id"] in cluster_representatives:
                raise ValueError(f"{where} has an invalid cluster representative")
            cluster_representatives[unit["dedup_cluster_id"]] = unit_id
            representative_ids.add(unit_id)
            representative_chars += chars
            after_by_sample[sample_id] += chars
        else:
            if relation == "UNIQUE":
                raise ValueError(f"{where} non-representative is marked UNIQUE")
            exact_duplicates += relation == "EXACT"
            near_duplicates += relation == "NEAR"
    if sorted(listed_unit_ids) != sorted(unit_ids):
        raise ValueError("manifest sample unit indexes do not reconstruct analysis_units")
    if any(unit["dedup_cluster_id"] not in cluster_representatives for unit in units):
        raise ValueError("manifest contains a cluster without a representative")
    for sample_id, sample in sample_by_id.items():
        if sample["readable_author_chars_after_dedup"] != after_by_sample[sample_id]:
            raise ValueError(f"sample {sample_id} after-dedup count is inconsistent")

    aggregate = manifest["aggregate"]
    if not isinstance(aggregate, dict):
        raise ValueError("manifest.aggregate must be an object")
    _expect_exact_keys(
        aggregate,
        {
            "requested_samples",
            "accepted_samples",
            "rejected_samples",
            "readable_author_chars",
            "unique_analysis_units",
            "unique_complete_units",
            "protected_ranges",
            "excluded_ranges",
            "exact_duplicate_units",
            "near_duplicate_units",
        },
        "manifest.aggregate",
    )
    values = {key: _require_int(value, f"manifest.aggregate.{key}") for key, value in aggregate.items()}
    if values["requested_samples"] != len(samples):
        raise ValueError("manifest requested_samples is inconsistent")
    rebuilt_accepted = sum(
        1
        for sample in samples
        if sample["decode_status"] == "PASS"
        and sample["origin"] in ELIGIBLE_ORIGINS
        and sample["readable_author_chars_before_dedup"] > 0
    )
    if values["accepted_samples"] != rebuilt_accepted or values["rejected_samples"] != len(samples) - rebuilt_accepted:
        raise ValueError("manifest accepted/rejected sample counts are inconsistent")
    if values["readable_author_chars"] != representative_chars:
        raise ValueError("manifest readable_author_chars is inconsistent")
    if values["unique_analysis_units"] != len(representative_ids):
        raise ValueError("manifest unique_analysis_units is inconsistent")
    if any(cluster not in complete_cluster_representatives for cluster in complete_cluster_ids):
        raise ValueError("manifest contains a complete-unit cluster without a representative")
    rebuilt_complete_units = len(complete_cluster_representatives)
    if values["unique_complete_units"] != rebuilt_complete_units:
        raise ValueError("manifest unique_complete_units is inconsistent")
    if values["exact_duplicate_units"] != exact_duplicates or values["near_duplicate_units"] != near_duplicates:
        raise ValueError("manifest duplicate counts are inconsistent")
    if values["protected_ranges"] != sum(1 for item in role_ranges if item["role"] not in {"author", "unknown"}):
        raise ValueError("manifest protected_ranges is inconsistent")
    if values["excluded_ranges"] != sum(1 for item in role_ranges if item["role"] == "unknown"):
        raise ValueError("manifest excluded_ranges is inconsistent")

    stored_hash = _require_sha(manifest["manifest_sha256"], "manifest.manifest_sha256")
    rebuilt_hash = _manifest_self_hash(manifest)
    if stored_hash != rebuilt_hash:
        raise ValueError(f"manifest self-hash mismatch: expected {stored_hash}, rebuilt {rebuilt_hash}")
    return manifest


def defaultdict_int() -> dict[str, int]:
    """Small typed defaultdict factory without exposing mutable globals."""

    from collections import defaultdict

    return defaultdict(int)


def validate_profile_manifest_binding(profile: dict[str, Any], manifest: dict[str, Any]) -> None:
    if profile["sample_binding"]["manifest_sha256"] != manifest["manifest_sha256"]:
        raise ValueError("profile is bound to a different sample manifest")
    aggregate = manifest["aggregate"]
    binding = profile["sample_binding"]
    comparisons = {
        "readable_author_chars": "readable_author_chars",
        "unique_analysis_units": "unique_analysis_units",
        "unique_complete_units": "unique_complete_units",
    }
    for profile_field, manifest_field in comparisons.items():
        if binding[profile_field] != aggregate[manifest_field]:
            raise ValueError(f"profile/manifest {profile_field} mismatch")
    sample_scenes = sorted(
        {
            sample["scene"]
            for sample in manifest["samples"]
            if sample["origin"] in ELIGIBLE_ORIGINS and sample["readable_author_chars_after_dedup"] > 0
        }
    )
    if binding["sample_scenes"] != sample_scenes:
        raise ValueError("profile/manifest sample_scenes mismatch")


def rebuild_profile_evidence(
    profile: dict[str, Any],
    manifest: dict[str, Any],
    *,
    sample_spec: Path,
    allowed_root: Path,
    max_file_bytes: int = 8 * 1024 * 1024,
    max_total_bytes: int = 32 * 1024 * 1024,
    max_units: int = 5000,
) -> None:
    """Rebuild the manifest/Profile pair from the pinned source specification."""
    rebuilt_manifest, rebuilt_profile = build_voice_profile(
        sample_spec=sample_spec,
        allowed_root=allowed_root,
        profile_id=profile["profile_id"],
        scene=profile["binding_scene"],
        revision=profile["revision"],
        source_date_epoch=manifest["source_date_epoch"],
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        max_units=max_units,
    )
    if rebuilt_manifest != manifest:
        raise ValueError("rebuilt sample evidence differs from voice sample manifest")
    if rebuilt_profile != profile:
        raise ValueError("rebuilt Voice Profile differs from supplied profile")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--sample-spec", type=Path)
    parser.add_argument("--allowed-root", type=Path)
    parser.add_argument("--rebuild-evidence", action="store_true")
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=32 * 1024 * 1024)
    parser.add_argument("--max-units", type=int, default=5000)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rebuild_inputs = (args.sample_spec is not None, args.allowed_root is not None)
        if rebuild_inputs[0] != rebuild_inputs[1]:
            raise ValueError("--sample-spec and --allowed-root must be supplied together")
        if args.rebuild_evidence and (args.manifest is None or not all(rebuild_inputs)):
            raise ValueError("--rebuild-evidence requires --manifest, --sample-spec and --allowed-root")
        profile = load_and_validate_profile(args.profile)
        manifest = None
        if args.manifest is not None:
            manifest = validate_manifest_object(_load_json_strict(args.manifest))
            validate_profile_manifest_binding(profile, manifest)
        if args.rebuild_evidence:
            rebuild_profile_evidence(
                profile,
                manifest,
                sample_spec=args.sample_spec,
                allowed_root=args.allowed_root,
                max_file_bytes=args.max_file_bytes,
                max_total_bytes=args.max_total_bytes,
                max_units=args.max_units,
            )
    except (OSError, ValueError) as exc:
        result = {"status": "FAIL", "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.format == "json" else f"FAIL: {exc}")
        return 1
    deterministic_default = (
        profile["profile_kind"] == "DEFAULT"
        and profile == build_scene_default_profile(profile["binding_scene"])
    )
    if profile["validation_status"] != "PASS":
        admission_status = "REVIEW"
        admission_reason = "PROFILE_STATUS_NOT_PASS"
    elif deterministic_default:
        admission_status = "PASS"
        admission_reason = "DETERMINISTIC_DEFAULT"
    elif args.rebuild_evidence:
        admission_status = "PASS"
        admission_reason = "EVIDENCE_REBUILT"
    else:
        admission_status = "REVIEW"
        admission_reason = "EVIDENCE_REBUILD_REQUIRED"
    result = {
        "status": admission_status,
        "profile_validation_status": profile["validation_status"],
        "production_admission_status": admission_status,
        "production_admission_reason": admission_reason,
        "profile_kind": profile["profile_kind"],
        "confidence": profile["confidence"],
        "profile_sha256": profile["profile_sha256"],
        "manifest_sha256": manifest["manifest_sha256"] if manifest else profile["sample_binding"]["manifest_sha256"],
        "manifest_validated": manifest is not None,
        "evidence_rebuilt": bool(args.rebuild_evidence),
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"{result['status']}: {result['profile_kind']} {result['confidence']} "
            f"profile_sha256={result['profile_sha256']} manifest_validated={result['manifest_validated']}"
        )
    return 0 if admission_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
