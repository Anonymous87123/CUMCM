#!/usr/bin/env python3
"""Create and apply a run-scoped amendment to a verified short PATCH review."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import apply_humanize_short_patch as applicator  # noqa: E402
import build_humanize_short_patch as short_patch  # noqa: E402
import verify_humanize_short_patch as verifier  # noqa: E402


AUTHORING_SCHEMA = "humanize-short-patch-amend-authoring/v1"
OPERATION_SCHEMA = "humanize-short-patch-amend-operation/v1"
AUTHORING_INTEGRITY_SCOPE = "CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY"
AUTHORING_FIELDS = {
    "schema_version",
    "base",
    "policy_hashes",
    "changes",
    "authoring_integrity_scope",
    "completion_claim_allowed",
    "humanize_quality_claim_allowed",
}
BASE_FIELDS = {
    "manifest_sha256",
    "bundle_sha256",
    "selection_spec_sha256",
    "source_sha256",
    "candidate_sha256",
    "coverage_sha256",
    "bundle_schema_version",
    "live_source_required",
}
CHANGE_FIELDS = {"hunk_id", "before", "after"}
AFTER_FIELDS = {"decision", "replacement", "reason"}
TOOL_POLICY_FILES = {
    "amend_tool_sha256": Path(__file__).resolve(),
    "builder_sha256": SCRIPT_DIR / "build_humanize_short_patch.py",
    "applicator_sha256": SCRIPT_DIR / "apply_humanize_short_patch.py",
    "verifier_sha256": SCRIPT_DIR / "verify_humanize_short_patch.py",
}
POLICY_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*_sha256$")


ShortPatchError = short_patch.ShortPatchError


class AmendError(ValueError):
    """Raised when an amendment is malformed or its immutable anchors fail."""


class AmendReview(RuntimeError):
    """Raised when mutable external state prevents safe amendment publication."""

    def __init__(self, reason: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = dict(details or {})


class _StrictArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise AmendError("INVALID_ARGUMENTS")


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise AmendError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _sha_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or not short_patch.HEX64_RE.fullmatch(value):
        raise AmendError(f"{label} must be a lowercase SHA-256")
    return value


def _policy_file_hash(path: Path, label: str) -> str:
    try:
        raw = short_patch._regular_input(path, label, short_patch.MAX_JSON_BYTES)
    except (OSError, ShortPatchError) as error:
        raise AmendReview("CURRENT_POLICY_UNAVAILABLE") from error
    return short_patch.sha256(raw)


def current_policy_hashes() -> dict[str, str]:
    """Return every policy and executable hash that an amend run freezes."""
    try:
        policy = verifier._current_policy_hashes()
    except (OSError, ValueError, ShortPatchError) as error:
        raise AmendReview("CURRENT_POLICY_UNAVAILABLE") from error
    if not isinstance(policy, dict) or not policy:
        raise AmendReview("CURRENT_POLICY_UNAVAILABLE")
    result: dict[str, str] = {}
    for key, value in policy.items():
        if (
            not isinstance(key, str)
            or not POLICY_KEY_RE.fullmatch(key)
            or not isinstance(value, str)
            or not short_patch.HEX64_RE.fullmatch(value)
        ):
            raise AmendReview("CURRENT_POLICY_UNAVAILABLE")
        result[key] = value
    for key, path in TOOL_POLICY_FILES.items():
        if key in result:
            raise AmendReview("CURRENT_POLICY_KEY_COLLISION")
        result[key] = _policy_file_hash(path, key)
    return dict(sorted(result.items()))


def _manifest_artifact(
    manifest: Mapping[str, Any], name: str
) -> Mapping[str, Any]:
    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        raise AmendError("parent evidence manifest artifacts are invalid")
    matches = [item for item in entries if isinstance(item, dict) and item.get("path") == name]
    if len(matches) != 1:
        raise AmendError(f"parent artifact is missing or duplicate: {name}")
    return matches[0]


def _bound_artifact(root: Path, manifest: Mapping[str, Any], name: str) -> bytes:
    entry = _manifest_artifact(manifest, name)
    raw = short_patch._regular_input(root / name, f"parent artifact {name}")
    if entry.get("size") != len(raw) or entry.get("sha256") != short_patch.sha256(raw):
        raise AmendError(f"parent artifact drifted after verification: {name}")
    return raw


def _review_reason(verification: Mapping[str, Any]) -> str:
    reasons = verification.get("review_reasons")
    if isinstance(reasons, list) and reasons and all(isinstance(item, str) for item in reasons):
        return ",".join(reasons)
    return "PARENT_REVIEW_NOT_CURRENT"


def _load_verified_parent(
    base_review_dir: Path,
    *,
    live_source: Path | None,
) -> dict[str, Any]:
    try:
        # Verify the closed parent record independently from caller-supplied
        # mutable state.  The optional path is checked below as an explicitly
        # untrusted byte comparison and can never upgrade record integrity.
        verification = verifier.verify_directory(base_review_dir)
    except (OSError, ShortPatchError, ValueError) as error:
        raise AmendError(f"PARENT_VERIFICATION_FAILED: {error}") from error
    if verification.get("status") != "PASS" or verification.get("exit_code") != 0:
        raise AmendReview(_review_reason(verification), verification)
    required = {
        "record_integrity_status": "PASS",
        "current_policy_status": "MATCH",
        "current_policy_replay_status": "PASS",
        "coverage_policy_status": "PASS",
        "coverage_replay_status": "PASS",
        "review_artifact_status": "PASS",
    }
    for key, expected in required.items():
        if verification.get(key) != expected:
            if key.startswith("current_policy") or key.startswith("coverage_"):
                raise AmendReview(f"PARENT_{key.upper()}_NOT_CURRENT", verification)
            raise AmendError(f"parent verification field mismatch: {key}")
    root = verifier._root(base_review_dir)
    manifest_raw = short_patch._regular_input(
        root / "evidence-manifest.json",
        "parent evidence manifest",
        short_patch.MAX_JSON_BYTES,
    )
    manifest = short_patch.strict_json_bytes(manifest_raw, "parent evidence manifest")
    if not isinstance(manifest, dict):
        raise AmendError("parent evidence manifest must be an object")
    if manifest.get("manifest_sha256") != verification.get("manifest_sha256"):
        raise AmendError("parent manifest anchor mismatch")
    source = _bound_artifact(root, manifest, "source.snapshot.bin")
    bundle_raw = _bound_artifact(root, manifest, "patch.bundle.json")
    bundle_payload = short_patch.strict_json_bytes(bundle_raw, "parent bundle")
    try:
        bundle = short_patch.validate_bundle_payload(bundle_payload, source)
    except ShortPatchError as error:
        raise AmendError(str(error)) from error
    if bundle.get("schema_version") not in {
        short_patch.BUNDLE_SCHEMA_V2,
        short_patch.BUNDLE_SCHEMA_V3,
    }:
        raise AmendError("amendment parent must be coverage-aware v2 or v3")
    candidate_names = [
        str(item.get("path"))
        for item in manifest.get("artifacts", [])
        if isinstance(item, dict) and item.get("path") in verifier.ALLOWED_CANDIDATE_NAMES
    ]
    if len(candidate_names) != 1:
        raise AmendError("parent candidate artifact is missing or duplicate")
    candidate = _bound_artifact(root, manifest, candidate_names[0])
    coverage_raw = _bound_artifact(root, manifest, "coverage.json")
    if short_patch.sha256(candidate) != verification.get("candidate_sha256"):
        raise AmendError("parent candidate anchor mismatch")
    if short_patch.sha256(source) != verification.get("source_sha256"):
        raise AmendError("parent source anchor mismatch")
    if short_patch._apply_bundle_bytes(source, bundle) != candidate:
        raise AmendError("parent candidate is not the deterministic bundle application")
    if short_patch._regular_input(
        root / "evidence-manifest.json",
        "parent evidence manifest",
        short_patch.MAX_JSON_BYTES,
    ) != manifest_raw:
        raise AmendError("parent manifest changed while loading amendment base")
    live_source_status = _assert_live_source(
        live_source,
        bundle["source_sha256"],
        required=live_source is not None,
    )
    return {
        "root": root,
        "manifest": manifest,
        "manifest_raw": manifest_raw,
        "source": source,
        "bundle": bundle,
        "bundle_raw": bundle_raw,
        "candidate": candidate,
        "coverage_raw": coverage_raw,
        "verification": verification,
        "live_source_status": live_source_status,
    }


def _base_record(parent: Mapping[str, Any], *, live_source_required: bool) -> dict[str, Any]:
    bundle = parent["bundle"]
    manifest = parent["manifest"]
    return {
        "manifest_sha256": manifest["manifest_sha256"],
        "bundle_sha256": bundle["bundle_sha256"],
        "selection_spec_sha256": bundle["selection_spec_sha256"],
        "source_sha256": bundle["source_sha256"],
        "candidate_sha256": short_patch.sha256(parent["candidate"]),
        "coverage_sha256": short_patch.sha256(parent["coverage_raw"]),
        "bundle_schema_version": bundle["schema_version"],
        "live_source_required": live_source_required,
    }


def _assert_live_source(
    path: Path | None, expected_sha256: str, *, required: bool
) -> dict[str, Any]:
    if path is None:
        if required:
            raise AmendReview("LIVE_SOURCE_REQUIRED")
        return {
            "status": "NOT_PROVIDED",
            "expected_sha256": expected_sha256,
            "path_binding": "NOT_PROVIDED",
            "freshness_claim_allowed": False,
            "review_reasons": [],
        }
    status = verifier._live_source_status(path, expected_sha256)
    try:
        reasons = verifier._live_source_reasons(status)
    except ShortPatchError as error:
        raise AmendError("live source status contract is invalid") from error
    details = {**status, "review_reasons": reasons}
    # A byte match is useful only as caller-controlled self-consistency.  The
    # evidence package intentionally has no trusted path binding, so it must
    # never be reported as MATCH/current or clear a freshness gate.
    blocking = [
        reason
        for reason in reasons
        if reason in {"LIVE_SOURCE_NOT_CURRENT", "LIVE_SOURCE_UNAVAILABLE"}
    ]
    if blocking:
        raise AmendReview(blocking[0], details)
    return details


def _assert_parent_stable(parent: Mapping[str, Any]) -> None:
    current = short_patch._regular_input(
        parent["root"] / "evidence-manifest.json",
        "parent evidence manifest",
        short_patch.MAX_JSON_BYTES,
    )
    if current != parent["manifest_raw"]:
        raise AmendError("parent manifest changed during amendment operation")


def _select_hunks(bundle: Mapping[str, Any], hunk_ids: Sequence[str]) -> list[dict[str, Any]]:
    if not hunk_ids or len(hunk_ids) > short_patch.MAX_HUNKS:
        raise AmendError("--hunk must select a non-empty bounded set")
    requested: dict[str, str] = {}
    for index, value in enumerate(hunk_ids):
        hunk_id = short_patch._required_string(value, f"hunk[{index}]")
        if not short_patch.HUNK_ID_RE.fullmatch(hunk_id):
            raise AmendError(f"invalid hunk_id: {hunk_id}")
        key = hunk_id.casefold()
        if key in requested:
            raise AmendError("duplicate hunk_id")
        requested[key] = hunk_id
    parent_by_case = {str(item["hunk_id"]).casefold(): item for item in bundle["hunks"]}
    missing = sorted(value for key, value in requested.items() if key not in parent_by_case)
    if missing:
        raise AmendError("unknown hunk_id: " + ",".join(missing))
    for key, requested_id in requested.items():
        if parent_by_case[key]["hunk_id"] != requested_id:
            raise AmendError("hunk_id case does not match parent")
    selected: list[dict[str, Any]] = []
    for hunk in bundle["hunks"]:
        if str(hunk["hunk_id"]).casefold() not in requested:
            continue
        selected.append(
            {
                "hunk_id": hunk["hunk_id"],
                "before": dict(hunk),
                "after": {
                    "decision": hunk["decision"],
                    "replacement": hunk["replacement"],
                    "reason": hunk["reason"],
                },
            }
        )
    return selected


def create_authoring(
    base_review_dir: Path,
    hunk_ids: Sequence[str],
    output_path: Path,
    *,
    live_source: Path | None = None,
) -> dict[str, Any]:
    """Create a caller-editable amendment scaffold from a current verified review."""
    output_path = short_patch.safe_output_path(output_path)
    policy_before = current_policy_hashes()
    parent = _load_verified_parent(base_review_dir, live_source=live_source)
    payload: dict[str, Any] = {
        "schema_version": AUTHORING_SCHEMA,
        "base": _base_record(parent, live_source_required=live_source is not None),
        "policy_hashes": policy_before,
        "changes": _select_hunks(parent["bundle"], hunk_ids),
        "authoring_integrity_scope": AUTHORING_INTEGRITY_SCOPE,
        "completion_claim_allowed": False,
        "humanize_quality_claim_allowed": False,
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > short_patch.MAX_JSON_BYTES:
        raise AmendError("AMENDMENT_AUTHORING_EXCEEDS_LIMIT")
    _assert_parent_stable(parent)
    _assert_live_source(
        live_source,
        payload["base"]["source_sha256"],
        required=payload["base"]["live_source_required"],
    )
    if current_policy_hashes() != policy_before:
        raise AmendReview("POLICY_CHANGED_DURING_CREATE")
    short_patch._atomic_write_new(output_path, encoded)
    return payload


def _validate_authoring(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AmendError("amendment authoring must be an object")
    _exact_fields(payload, AUTHORING_FIELDS, "amendment authoring")
    if payload.get("schema_version") != AUTHORING_SCHEMA:
        raise AmendError("amendment authoring schema_version is invalid")
    if payload.get("authoring_integrity_scope") != AUTHORING_INTEGRITY_SCOPE:
        raise AmendError("amendment authoring integrity scope is invalid")
    if payload.get("completion_claim_allowed") is not False:
        raise AmendError("completion_claim_allowed must be false")
    if payload.get("humanize_quality_claim_allowed") is not False:
        raise AmendError("humanize_quality_claim_allowed must be false")
    base = payload.get("base")
    if not isinstance(base, dict):
        raise AmendError("amendment authoring base must be an object")
    _exact_fields(base, BASE_FIELDS, "amendment authoring base")
    for field in BASE_FIELDS - {"bundle_schema_version", "live_source_required"}:
        _sha_field(base.get(field), f"base.{field}")
    if base.get("bundle_schema_version") not in {
        short_patch.BUNDLE_SCHEMA_V2,
        short_patch.BUNDLE_SCHEMA_V3,
    }:
        raise AmendError("base.bundle_schema_version must be v2 or v3")
    if not isinstance(base.get("live_source_required"), bool):
        raise AmendError("base.live_source_required must be boolean")
    policy = payload.get("policy_hashes")
    if not isinstance(policy, dict) or not policy:
        raise AmendError("policy_hashes must be a non-empty object")
    for key, value in policy.items():
        if not isinstance(key, str) or not POLICY_KEY_RE.fullmatch(key):
            raise AmendError("policy_hashes contains an invalid key")
        _sha_field(value, f"policy_hashes.{key}")
    if not set(TOOL_POLICY_FILES).issubset(policy):
        raise AmendError("policy_hashes is missing amend tool-chain anchors")
    changes = payload.get("changes")
    if not isinstance(changes, list) or not changes or len(changes) > short_patch.MAX_HUNKS:
        raise AmendError("changes must be a non-empty bounded array")
    seen: set[str] = set()
    for index, change in enumerate(changes):
        label = f"changes[{index}]"
        if not isinstance(change, dict):
            raise AmendError(f"{label} must be an object")
        _exact_fields(change, CHANGE_FIELDS, label)
        hunk_id = short_patch._required_string(change.get("hunk_id"), f"{label}.hunk_id")
        if not short_patch.HUNK_ID_RE.fullmatch(hunk_id):
            raise AmendError(f"{label}.hunk_id is invalid")
        if hunk_id.casefold() in seen:
            raise AmendError("changes contains a duplicate hunk_id")
        seen.add(hunk_id.casefold())
        before = change.get("before")
        if not isinstance(before, dict):
            raise AmendError(f"{label}.before must be an object")
        _exact_fields(before, short_patch.BUNDLE_HUNK_FIELDS, f"{label}.before")
        after = change.get("after")
        if not isinstance(after, dict):
            raise AmendError(f"{label}.after must be an object")
        _exact_fields(after, AFTER_FIELDS, f"{label}.after")
        decision = short_patch._required_string(after.get("decision"), f"{label}.after.decision")
        replacement = short_patch._required_string(
            after.get("replacement"),
            f"{label}.after.replacement",
            allow_empty=True,
        )
        reason = short_patch._specific_reason(after.get("reason"), f"{label}.after.reason")
        source_text = short_patch._required_string(
            before.get("source_text"), f"{label}.before.source_text"
        )
        try:
            short_patch._validate_decision(decision, source_text, replacement, label)
            short_patch._validate_replacement_controls(source_text, replacement, label)
        except ShortPatchError as error:
            raise AmendError(str(error)) from error
        after["reason"] = reason
    return dict(payload)


def _assert_authoring_matches_parent(
    authoring: Mapping[str, Any], parent: Mapping[str, Any]
) -> list[dict[str, str]]:
    expected_base = _base_record(
        parent,
        live_source_required=bool(authoring["base"]["live_source_required"]),
    )
    if authoring["base"] != expected_base:
        raise AmendError("amendment base anchors do not match parent review")
    parent_hunks = {str(item["hunk_id"]): item for item in parent["bundle"]["hunks"]}
    parent_order = {str(item["hunk_id"]): index for index, item in enumerate(parent["bundle"]["hunks"])}
    changes: list[dict[str, str]] = []
    order: list[int] = []
    for item in authoring["changes"]:
        hunk_id = str(item["hunk_id"])
        before = parent_hunks.get(hunk_id)
        if before is None:
            if hunk_id.casefold() in {key.casefold() for key in parent_hunks}:
                raise AmendError("amendment hunk_id case does not match parent")
            raise AmendError(f"unknown amendment hunk_id: {hunk_id}")
        if item["before"] != before:
            raise AmendError(f"amendment before anchor mismatch: {hunk_id}")
        after = item["after"]
        if (
            after["decision"],
            after["replacement"],
            after["reason"],
        ) == (
            before["decision"],
            before["replacement"],
            before["reason"],
        ):
            raise AmendError(f"SELECTED_HUNK_NOT_CHANGED: {hunk_id}")
        changes.append({"hunk_id": hunk_id, **after})
        order.append(parent_order[hunk_id])
    if order != sorted(order):
        raise AmendError("amendment changes must remain in parent source order")
    return changes


def _review_result(reason: str, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": OPERATION_SCHEMA,
        "status": "REVIEW",
        "delivery_gate_status": "REVIEW",
        "exit_code": 2,
        "reason": reason,
        "details": dict(details or {}),
        "humanize_quality_claim_allowed": False,
        "completion_claim_allowed": False,
    }


def apply_amendment(
    base_review_dir: Path,
    amendment_path: Path,
    output_dir: Path,
    *,
    live_source: Path | None = None,
) -> dict[str, Any]:
    """Apply an edited amend scaffold and atomically publish a new closed review."""
    amendment_path = short_patch.safe_input_path(amendment_path, "amendment authoring")
    output_dir = short_patch.safe_output_path(output_dir)
    amendment_raw = short_patch._regular_input(
        amendment_path,
        "amendment authoring",
        short_patch.MAX_JSON_BYTES,
    )
    authoring = _validate_authoring(
        short_patch.strict_json_bytes(amendment_raw, "amendment authoring")
    )
    if authoring["base"]["live_source_required"] and live_source is None:
        raise AmendReview("LIVE_SOURCE_REQUIRED")
    policy_before = current_policy_hashes()
    if authoring["policy_hashes"] != policy_before:
        raise AmendReview("POLICY_DRIFT")
    parent = _load_verified_parent(base_review_dir, live_source=live_source)
    changes = _assert_authoring_matches_parent(authoring, parent)
    try:
        bundle = short_patch.build_amended_bundle_payload(
            parent["source"],
            parent["bundle"],
            amendment_raw,
            changes,
        )
    except ShortPatchError as error:
        raise AmendError(str(error)) from error
    bundle_raw = (
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() or output_dir.is_symlink():
        raise AmendError("output_exists")
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.amend-staging-", dir=output_dir.parent)
    )
    review_staging = staging_root / "review"
    try:
        source_snapshot = staging_root / (
            "source.snapshot.tex"
            if parent["bundle"]["document_format"] == "tex"
            else "source.snapshot.md"
        )
        source_snapshot.write_bytes(parent["source"])
        bundle_path = staging_root / "patch.bundle.json"
        bundle_path.write_bytes(bundle_raw)
        result = applicator.apply_patch(source_snapshot, bundle_path, review_staging)
        if result.get("delivery_gate_status") != "REVIEW" or result.get("exit_code") != 2:
            raise AmendError("amended review did not preserve DELIVERY REVIEW/2")
        verification = verifier.verify_directory(review_staging)
        if verification.get("status") != "PASS" or verification.get("exit_code") != 0:
            raise AmendReview("AMENDED_REVIEW_NOT_CURRENT", verification)
        if short_patch._regular_input(
            amendment_path,
            "amendment authoring",
            short_patch.MAX_JSON_BYTES,
        ) != amendment_raw:
            raise AmendError("amendment authoring changed during apply")
        _assert_parent_stable(parent)
        final_live_source_status = _assert_live_source(
            live_source,
            authoring["base"]["source_sha256"],
            required=bool(authoring["base"]["live_source_required"]),
        )
        if current_policy_hashes() != policy_before:
            raise AmendReview("POLICY_CHANGED_DURING_APPLY")
        if output_dir.exists() or output_dir.is_symlink():
            raise AmendError("output_exists")
        short_patch._assert_no_reparse_chain(output_dir.parent, "output")
        os.rename(review_staging, output_dir)
        operation_result = dict(result)
        operation_result["live_source_status"] = final_live_source_status
        operation_result["freshness_claim_allowed"] = False
        operation_result["review_reasons"] = list(
            final_live_source_status.get("review_reasons", [])
        )
        return operation_result
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)


def build_parser() -> argparse.ArgumentParser:
    parser = _StrictArgumentParser(
        description="Amend selected hunks from a verified short PATCH review without rebuilding authoring."
    )
    subparsers = parser.add_subparsers(
        dest="operation", required=True, parser_class=_StrictArgumentParser
    )
    create = subparsers.add_parser("create")
    create.add_argument("base_review_dir", type=Path)
    create.add_argument("--hunk", action="append", required=True)
    create.add_argument("--output", required=True, type=Path)
    create.add_argument("--live-source", type=Path)
    create.add_argument("--format", choices=("json", "text"), default="text")
    apply = subparsers.add_parser("apply")
    apply.add_argument("base_review_dir", type=Path)
    apply.add_argument("--amendment", required=True, type=Path)
    apply.add_argument("--output", required=True, type=Path)
    apply.add_argument("--live-source", type=Path)
    apply.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def _print(payload: Mapping[str, Any], *, output_format: str, text: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(text)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    requested_format = "json" if "--format" in raw_argv and "json" in raw_argv else "text"
    try:
        args = build_parser().parse_args(raw_argv)
        if args.operation == "create":
            payload = create_authoring(
                args.base_review_dir,
                args.hunk,
                args.output,
                live_source=args.live_source,
            )
            summary = {
                "schema_version": AUTHORING_SCHEMA,
                "status": "PENDING_AMENDMENT",
                "exit_code": 0,
                "hunks_total": len(payload["changes"]),
                "manifest_sha256": payload["base"]["manifest_sha256"],
                "completion_claim_allowed": False,
                "humanize_quality_claim_allowed": False,
            }
            if payload["base"]["live_source_required"]:
                # create only reaches this point after an exact byte match.
                # The match is still caller-supplied and cannot establish
                # current-work-file freshness.
                summary.update(
                    {
                        "status": "REVIEW",
                        "delivery_gate_status": "REVIEW",
                        "exit_code": 2,
                        "authoring_status": "PENDING_AMENDMENT",
                        "live_source_status": "CALLER_SUPPLIED_MATCH_UNVERIFIED",
                        "path_binding": "UNVERIFIED_CALLER_PATH",
                        "freshness_claim_allowed": False,
                        "review_reasons": ["LIVE_SOURCE_PATH_BINDING_UNVERIFIED"],
                    }
                )
            _print(
                summary,
                output_format=args.format,
                text=(
                    f"REVIEW exit=2 authoring=PENDING_AMENDMENT "
                    f"hunks={summary['hunks_total']} "
                    "live_source=CALLER_SUPPLIED_MATCH_UNVERIFIED"
                    if payload["base"]["live_source_required"]
                    else f"PENDING AMENDMENT exit=0 hunks={summary['hunks_total']}"
                ),
            )
            return 2 if payload["base"]["live_source_required"] else 0
        result = apply_amendment(
            args.base_review_dir,
            args.amendment,
            args.output,
            live_source=args.live_source,
        )
        _print(result, output_format=args.format, text="DELIVERY REVIEW exit=2")
        return 2
    except AmendReview as review:
        payload = _review_result(review.reason, review.details)
        _print(
            payload,
            output_format=getattr(locals().get("args", None), "format", requested_format),
            text=f"DELIVERY REVIEW exit=2\n{review.reason}",
        )
        return 2
    except (OSError, AmendError, ShortPatchError, ValueError) as error:
        payload = {
            "schema_version": OPERATION_SCHEMA,
            "status": "FAIL",
            "delivery_gate_status": "FAIL",
            "exit_code": 1,
            "error": str(error),
            "humanize_quality_claim_allowed": False,
            "completion_claim_allowed": False,
        }
        _print(
            payload,
            output_format=getattr(locals().get("args", None), "format", requested_format),
            text=f"DELIVERY FAIL exit=1\n{error}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
