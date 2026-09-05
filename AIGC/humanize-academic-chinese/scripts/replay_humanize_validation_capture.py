#!/usr/bin/env python3
"""Verify and replay a parent-observed Humanize validation capture."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import capture_humanize_validation as capture  # noqa: E402
import replay_humanize_validation_record as inner_replay  # noqa: E402


REPLAY_SCHEMA = "humanize-validation-process-capture-replay/v1"
HEX64_RE = re.compile(r"[0-9a-f]{64}")


class CaptureReplayError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _exact_keys(
    value: dict[str, Any],
    required: Iterable[str],
    allowed: Iterable[str],
    label: str,
) -> None:
    required_set = set(required)
    allowed_set = set(allowed)
    missing = sorted(required_set - set(value))
    unknown = sorted(set(value) - allowed_set)
    if missing or unknown:
        raise CaptureReplayError(
            "INVALID_SCHEMA",
            f"{label} keys differ; missing={missing}, unknown={unknown}",
        )


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CaptureReplayError("INVALID_SCHEMA", f"{label} must be an object")
    return value


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CaptureReplayError("UNSAFE_ARTIFACT_PATH", "artifact path is unsafe")
    return path.as_posix()


def _read_regular(path: Path, label: str) -> bytes:
    try:
        capture._assert_no_reparse_ancestors(path)
        info = path.lstat()
    except (OSError, capture.CaptureError) as error:
        raise CaptureReplayError("MISSING_ARTIFACT", f"{label} is missing") from error
    if not stat.S_ISREG(info.st_mode):
        raise CaptureReplayError("NON_REGULAR_ARTIFACT", f"{label} is not a regular file")
    if int(getattr(info, "st_nlink", 1)) != 1:
        raise CaptureReplayError("HARDLINK_REJECTED", f"{label} is a hard link")
    return path.read_bytes()


def _load_record(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = capture._absolute_without_resolving(root)
    try:
        capture._assert_no_reparse_ancestors(root)
    except capture.CaptureError as error:
        raise CaptureReplayError(error.code, str(error)) from error
    if not root.is_dir():
        raise CaptureReplayError("INVALID_RECORD_ROOT", "capture root must be a directory")
    manifest_raw = _read_regular(root / "capture-manifest.json", "capture manifest")
    try:
        manifest = _object(
            capture._strict_json(manifest_raw, "capture manifest"),
            "capture manifest",
        )
    except capture.CaptureError as error:
        raise CaptureReplayError(error.code, str(error)) from error
    if manifest_raw != capture._pretty_json_bytes(manifest):
        raise CaptureReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "capture manifest is not the deterministic JSON rendering",
        )
    fields = {
        "schema",
        "capture_id",
        "record_sha256",
        "integrity_scope",
        "observation_scope",
        "historical_authenticity",
        "external_anchor_status",
        "contains_source_content",
        "status",
        "exit_code",
        "capture_integrity_status",
        "validation_delivery_gate_status",
        "observed_os_exit_code",
        "inner_run_id",
        "inner_record_sha256",
        "artifacts",
        "manifest_sha256",
    }
    _exact_keys(manifest, fields, fields, "capture manifest")
    if manifest.get("schema") != capture.CAPTURE_MANIFEST_SCHEMA:
        raise CaptureReplayError("UNSUPPORTED_SCHEMA", "capture schema is unsupported")
    if (
        manifest.get("integrity_scope")
        != "PARENT_PROCESS_OBSERVATION_SELF_CONSISTENCY"
        or manifest.get("observation_scope")
        != "SAME_HOST_SAME_USER_PARENT_PROCESS"
        or manifest.get("historical_authenticity") != "NOT_EVALUATED"
        or manifest.get("external_anchor_status") != "NOT_PROVIDED"
        or manifest.get("contains_source_content") is not True
    ):
        raise CaptureReplayError(
            "CAPTURE_CLAIM_OVERSTATED",
            "capture scope, authenticity, anchor, or content classification differs",
        )
    body = dict(manifest)
    manifest_sha = body.pop("manifest_sha256", None)
    if not isinstance(manifest_sha, str) or not HEX64_RE.fullmatch(manifest_sha):
        raise CaptureReplayError("INVALID_MANIFEST_HASH", "manifest hash is invalid")
    if capture._sha256(capture._canonical_json_bytes(body)) != manifest_sha:
        raise CaptureReplayError("MANIFEST_HASH_MISMATCH", "manifest self-hash differs")

    records = _object(manifest.get("artifacts"), "capture artifacts")
    artifacts: dict[str, bytes] = {}
    expected_files = {"capture-manifest.json"}
    for raw_name, raw_record in records.items():
        if not isinstance(raw_name, str):
            raise CaptureReplayError("INVALID_SCHEMA", "artifact name must be a string")
        name = _safe_relative(raw_name)
        record = _object(raw_record, f"artifact {name}")
        _exact_keys(record, {"sha256", "size"}, {"sha256", "size"}, name)
        sha = record.get("sha256")
        size = record.get("size")
        if not isinstance(sha, str) or not HEX64_RE.fullmatch(sha):
            raise CaptureReplayError("INVALID_ARTIFACT_HASH", f"invalid hash: {name}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise CaptureReplayError("INVALID_ARTIFACT_SIZE", f"invalid size: {name}")
        raw = _read_regular(root / Path(name), name)
        if len(raw) != size or capture._sha256(raw) != sha:
            raise CaptureReplayError("ARTIFACT_HASH_MISMATCH", f"artifact drifted: {name}")
        artifacts[name] = raw
        expected_files.add(name)

    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        try:
            capture._assert_no_reparse_ancestors(path)
        except capture.CaptureError as error:
            raise CaptureReplayError(error.code, str(error)) from error
        if path.is_symlink():
            raise CaptureReplayError("REPARSE_POINT_REJECTED", "capture contains a symlink")
        if path.is_dir():
            actual_dirs.add(relative)
        elif path.is_file():
            _read_regular(path, relative)
            actual_files.add(relative)
        else:
            raise CaptureReplayError("NON_REGULAR_ARTIFACT", "capture contains a special path")
    expected_dirs = {
        str(PurePosixPath(name).parent)
        for name in expected_files
        if str(PurePosixPath(name).parent) != "."
    }
    expanded_dirs = set(expected_dirs)
    for directory in list(expected_dirs):
        parent = PurePosixPath(directory).parent
        while str(parent) != ".":
            expanded_dirs.add(str(parent))
            parent = parent.parent
    if actual_files != expected_files or actual_dirs != expanded_dirs:
        raise CaptureReplayError(
            "CAPTURE_INVENTORY_MISMATCH",
            "capture contains missing or extra files/directories",
        )

    identity = {"schema": manifest["schema"], "artifacts": records}
    record_sha = capture._sha256(capture._canonical_json_bytes(identity))
    if (
        manifest.get("record_sha256") != record_sha
        or manifest.get("capture_id") != f"hvc1-{record_sha}"
        or root.name != manifest.get("capture_id")
    ):
        raise CaptureReplayError("CAPTURE_ID_MISMATCH", "capture ID is not content-bound")
    artifacts["capture-manifest.json"] = manifest_raw
    return manifest, artifacts


def _validate_invocation(raw: bytes) -> dict[str, Any]:
    try:
        invocation = _object(
            capture._strict_json(raw, "capture invocation"),
            "capture invocation",
        )
    except capture.CaptureError as error:
        raise CaptureReplayError(error.code, str(error)) from error
    if raw != capture._pretty_json_bytes(invocation):
        raise CaptureReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "capture invocation rendering differs",
        )
    fields = {
        "schema",
        "validator_entrypoint",
        "validator_arguments_redacted",
        "validator_evidence_directory_injected_by_parent",
        "raw_argv_archived",
        "raw_argv_digest_archived",
        "source_locator_archived",
        "reviewer_identifier_archived",
        "stable_reviewer_pseudonym_archived",
        "contains_unredacted_proposal_text",
        "policy_hashes_before_execution",
    }
    _exact_keys(invocation, fields, fields, "capture invocation")
    if (
        invocation.get("schema") != capture.CAPTURE_INVOCATION_SCHEMA
        or invocation.get("validator_entrypoint")
        != "scripts/validate_humanize_output.py"
        or invocation.get("validator_evidence_directory_injected_by_parent") is not True
        or invocation.get("raw_argv_archived") is not False
        or invocation.get("raw_argv_digest_archived") is not False
        or invocation.get("source_locator_archived") is not False
        or invocation.get("reviewer_identifier_archived") is not False
        or invocation.get("stable_reviewer_pseudonym_archived") is not False
        or not isinstance(invocation.get("contains_unredacted_proposal_text"), bool)
    ):
        raise CaptureReplayError(
            "INVALID_INVOCATION",
            "capture invocation fixed-entrypoint or privacy contract differs",
        )
    arguments = invocation.get("validator_arguments_redacted")
    if not isinstance(arguments, list) or any(not isinstance(item, str) for item in arguments):
        raise CaptureReplayError("INVALID_INVOCATION", "redacted arguments are invalid")
    policy = _object(
        invocation.get("policy_hashes_before_execution"),
        "capture policy",
    )
    return invocation


def _validate_observation(
    raw: bytes,
    manifest: dict[str, Any],
    artifacts: dict[str, bytes],
    root: Path,
) -> dict[str, Any]:
    try:
        observation = _object(
            capture._strict_json(raw, "process observation"),
            "process observation",
        )
    except capture.CaptureError as error:
        raise CaptureReplayError(error.code, str(error)) from error
    if raw != capture._pretty_json_bytes(observation):
        raise CaptureReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "process observation rendering differs",
        )
    fields = {
        "schema",
        "observation_scope",
        "termination_reason",
        "observed_os_exit_code",
        "process_returncode_after_termination",
        "stdout",
        "stderr",
        "stdout_stderr_interleaving",
        "inner_record",
        "capture_policy_stable_during_execution",
        "capture_integrity_status",
        "validation_delivery_gate_status",
        "failure_reasons",
        "historical_authenticity",
        "external_anchor_status",
        "academic_correctness",
        "paired_quality_clearance_granted",
        "humanize_quality_claim_allowed",
    }
    _exact_keys(observation, fields, fields, "process observation")
    if (
        observation.get("schema") != capture.PROCESS_OBSERVATION_SCHEMA
        or observation.get("observation_scope")
        != "SAME_HOST_SAME_USER_PARENT_PROCESS"
        or observation.get("stdout_stderr_interleaving") != "NOT_CAPTURED"
        or observation.get("historical_authenticity") != "NOT_EVALUATED"
        or observation.get("external_anchor_status") != "NOT_PROVIDED"
        or observation.get("academic_correctness") != "NOT_EVALUATED"
        or observation.get("paired_quality_clearance_granted") is not False
        or observation.get("humanize_quality_claim_allowed") is not False
    ):
        raise CaptureReplayError("CAPTURE_CLAIM_OVERSTATED", "observation claims differ")
    stdout_raw = artifacts.get("observed-stdout.bin")
    stderr_raw = artifacts.get("observed-stderr.bin")
    if stdout_raw is None or stderr_raw is None:
        raise CaptureReplayError("MISSING_ARTIFACT", "observed streams are missing")
    for label, stream, raw_stream in (
        ("stdout", observation.get("stdout"), stdout_raw),
        ("stderr", observation.get("stderr"), stderr_raw),
    ):
        record = _object(stream, label)
        _exact_keys(record, {"sha256", "size"}, {"sha256", "size"}, label)
        if record != {"sha256": capture._sha256(raw_stream), "size": len(raw_stream)}:
            raise CaptureReplayError("STREAM_BINDING_MISMATCH", f"{label} binding differs")

    inner = _object(observation.get("inner_record"), "inner record observation")
    common_inner = {
        "record_status",
        "binding_status",
        "run_id",
        "record_sha256",
        "manifest_file_sha256",
        "validation_delivery_gate_status",
        "validation_exit_code",
    }
    allowed_inner = set(common_inner)
    if inner.get("record_status") == "INVALID":
        allowed_inner.add("error_code")
    _exact_keys(inner, common_inner, allowed_inner, "inner record observation")
    if inner.get("record_status") == "PRESENT":
        recomputed, _ = capture._inner_binding(
            root / "validation-record",
            stdout_raw=stdout_raw,
            stderr_raw=stderr_raw,
            observed_exit=observation.get("observed_os_exit_code"),
        )
        if recomputed != inner:
            raise CaptureReplayError(
                "INNER_OBSERVATION_MISMATCH",
                "inner record no longer matches observed process facts",
            )
    elif any(name.startswith("validation-record/") for name in artifacts):
        raise CaptureReplayError(
            "INNER_OBSERVATION_MISMATCH",
            "inner files exist while observation says no valid inner record",
        )

    if (
        observation.get("capture_integrity_status") != manifest.get("capture_integrity_status")
        or observation.get("validation_delivery_gate_status")
        != manifest.get("validation_delivery_gate_status")
        or observation.get("observed_os_exit_code") != manifest.get("observed_os_exit_code")
        or inner.get("run_id") != manifest.get("inner_run_id")
        or inner.get("record_sha256") != manifest.get("inner_record_sha256")
    ):
        raise CaptureReplayError("MANIFEST_OBSERVATION_MISMATCH", "manifest bindings differ")
    if manifest.get("capture_integrity_status") == "PASS":
        if (
            observation.get("termination_reason") != "EXITED"
            or observation.get("capture_policy_stable_during_execution") is not True
            or inner.get("record_status") != "PRESENT"
            or inner.get("binding_status") != "PASS"
            or manifest.get("status") != inner.get("validation_delivery_gate_status")
            or manifest.get("exit_code") != inner.get("validation_exit_code")
        ):
            raise CaptureReplayError(
                "CAPTURE_INTEGRITY_MISMATCH",
                "capture PASS does not have a fully bound natural child exit",
            )
    elif manifest.get("status") != "FAIL" or manifest.get("exit_code") != 1:
        raise CaptureReplayError(
            "CAPTURE_INTEGRITY_MISMATCH",
            "failed capture was not classified FAIL/1",
        )
    return observation


def replay_capture(root: Path) -> tuple[dict[str, Any], int]:
    root = capture._absolute_without_resolving(root)
    manifest, artifacts = _load_record(root)
    invocation = _validate_invocation(artifacts["capture-invocation.json"])
    observation = _validate_observation(
        artifacts["process-observation.json"],
        manifest,
        artifacts,
        root,
    )
    if manifest["capture_integrity_status"] != "PASS":
        return (
            {
                "schema": REPLAY_SCHEMA,
                "status": "FAIL",
                "exit_code": 1,
                "record_integrity_status": "PASS",
                "capture_integrity_status": "FAIL",
                "reexecution_status": "NOT_RUN",
                "capture_id": manifest["capture_id"],
                "observed_os_exit_code": observation["observed_os_exit_code"],
                "validation_delivery_gate_status": "NOT_AVAILABLE",
                "historical_authenticity": "NOT_EVALUATED",
                "academic_correctness": "NOT_EVALUATED",
                "paired_quality_clearance_granted": False,
                "humanize_quality_claim_allowed": False,
            },
            1,
        )

    recorded_policy = invocation["policy_hashes_before_execution"]
    current_policy = capture._capture_policy_hashes()
    if recorded_policy != current_policy:
        return (
            {
                "schema": REPLAY_SCHEMA,
                "status": "REVIEW",
                "exit_code": 2,
                "record_integrity_status": "PASS",
                "capture_integrity_status": "PASS",
                "reexecution_status": "NOT_RUN",
                "reexecution_reasons": ["CAPTURE_OR_VALIDATOR_POLICY_DRIFT"],
                "capture_id": manifest["capture_id"],
                "observed_os_exit_code": observation["observed_os_exit_code"],
                "validation_delivery_gate_status": manifest[
                    "validation_delivery_gate_status"
                ],
                "historical_authenticity": "NOT_EVALUATED",
                "academic_correctness": "NOT_EVALUATED",
                "paired_quality_clearance_granted": False,
                "humanize_quality_claim_allowed": False,
            },
            2,
        )

    try:
        inner_payload, inner_exit = inner_replay.replay_record(
            root / "validation-record"
        )
    except (inner_replay.ReplayError, OSError) as error:
        raise CaptureReplayError(
            getattr(error, "code", "INNER_REPLAY_IO_ERROR"),
            str(error),
        ) from error
    if inner_exit == 1:
        raise CaptureReplayError("INNER_REPLAY_FAILED", "inner record replay failed")
    if inner_exit == 2:
        return (
            {
                "schema": REPLAY_SCHEMA,
                "status": "REVIEW",
                "exit_code": 2,
                "record_integrity_status": "PASS",
                "capture_integrity_status": "PASS",
                "reexecution_status": "NOT_RUN",
                "reexecution_reasons": inner_payload.get(
                    "reexecution_reasons",
                    ["INNER_REPLAY_REQUIRES_REVIEW"],
                ),
                "capture_id": manifest["capture_id"],
                "observed_os_exit_code": observation["observed_os_exit_code"],
                "validation_delivery_gate_status": manifest[
                    "validation_delivery_gate_status"
                ],
                "historical_authenticity": "NOT_EVALUATED",
                "academic_correctness": "NOT_EVALUATED",
                "paired_quality_clearance_granted": False,
                "humanize_quality_claim_allowed": False,
            },
            2,
        )

    status = str(manifest["validation_delivery_gate_status"])
    exit_code = int(manifest["exit_code"])
    return (
        {
            "schema": REPLAY_SCHEMA,
            "status": status,
            "exit_code": exit_code,
            "record_integrity_status": "PASS",
            "capture_integrity_status": "PASS",
            "reexecution_status": "PASS",
            "parent_observation_binding_status": "PASS",
            "capture_id": manifest["capture_id"],
            "observed_os_exit_code": observation["observed_os_exit_code"],
            "validation_delivery_gate_status": status,
            "integrity_scope": "PARENT_PROCESS_OBSERVATION_SELF_CONSISTENCY",
            "historical_authenticity": "NOT_EVALUATED",
            "academic_correctness": "NOT_EVALUATED",
            "paired_quality_clearance_granted": False,
            "humanize_quality_claim_allowed": False,
        },
        exit_code,
    )


def _error_payload(error: Exception) -> dict[str, Any]:
    return {
        "schema": REPLAY_SCHEMA,
        "status": "FAIL",
        "exit_code": 1,
        "record_integrity_status": "FAIL",
        "capture_integrity_status": "NOT_EVALUATED",
        "reexecution_status": "NOT_RUN",
        "error_code": getattr(error, "code", "CAPTURE_REPLAY_IO_ERROR"),
        "error": str(error),
        "historical_authenticity": "NOT_EVALUATED",
        "academic_correctness": "NOT_EVALUATED",
        "paired_quality_clearance_granted": False,
        "humanize_quality_claim_allowed": False,
    }


def _text_output(payload: dict[str, Any]) -> str:
    lines = [
        f"status: {payload['status']}",
        f"record_integrity_status: {payload['record_integrity_status']}",
        f"capture_integrity_status: {payload['capture_integrity_status']}",
        f"reexecution_status: {payload['reexecution_status']}",
        f"validation_delivery_gate_status: {payload.get('validation_delivery_gate_status', 'NOT_AVAILABLE')}",
        f"capture_id: {payload.get('capture_id', 'NONE')}",
        f"historical_authenticity: {payload['historical_authenticity']}",
        f"academic_correctness: {payload['academic_correctness']}",
        "paired_quality_clearance_granted: "
        + str(payload["paired_quality_clearance_granted"]).upper(),
        "humanize_quality_claim_allowed: "
        + str(payload["humanize_quality_claim_allowed"]).upper(),
    ]
    for reason in payload.get("reexecution_reasons", []):
        lines.append(f"reason: {reason}")
    if payload.get("error_code"):
        lines.append(f"error_code: {payload['error_code']}")
        lines.append(f"error: {payload['error']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a parent-observed Humanize validation capture without upgrading "
            "the captured delivery, quality, authorship, or academic status."
        )
    )
    parser.add_argument("capture", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        payload, exit_code = replay_capture(args.capture)
    except (CaptureReplayError, capture.CaptureError, OSError, ValueError) as error:
        payload = _error_payload(error)
        exit_code = 1
    if args.format == "json":
        sys.stdout.buffer.write(capture._pretty_json_bytes(payload))
    else:
        sys.stdout.write(_text_output(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
