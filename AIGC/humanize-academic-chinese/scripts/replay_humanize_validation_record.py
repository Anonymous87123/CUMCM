#!/usr/bin/env python3
"""Verify and replay a self-contained short-form Humanize validation record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_DIR / "validate_humanize_output.py"
INVARIANT_CHECKER = SCRIPT_DIR / "check_humanize_invariants.py"
SCANNER = SCRIPT_DIR / "scan_humanize_chinese.py"
REPORT_EXTRACTOR = SCRIPT_DIR / "extract_detector_report_scope.py"
LEXICON = SCRIPT_DIR.parent / "references" / "lexical-signals.json"
PAIRED_QUALITY_VERIFIER = SCRIPT_DIR / ("verify" + "_humanize_paired_quality_response.py")
PAIRED_QUALITY_CONTRACT = SCRIPT_DIR.parent / "references" / (
    "paired" + "-quality-clearance-contract.md"
)
EVIDENCE_SCHEMAS = {
    "humanize-direct-validation-evidence/v2": "v2",
    "humanize-direct-validation-evidence/v3": "v3",
    "humanize-direct-validation-evidence/v4": "v4",
    "humanize-direct-validation-evidence/v5": "v5",
}
INVOCATION_SCHEMAS = {
    "humanize-validation-invocation/v1": ("v2", "hvr1"),
    "humanize-validation-invocation/v2": ("v3", "hvr2"),
    "humanize-validation-invocation/v3": ("v4", "hvr3"),
    "humanize-validation-invocation/v4": ("v5", "hvr4"),
}
REPLAY_SCHEMA = "humanize-validation-replay/v2"
HEX64_RE = re.compile(r"[0-9a-f]{64}")
STATUS_EXIT_CODES = {"PASS": 0, "FAIL": 1, "REVIEW": 2}
TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA = "humanize-template-field-edit-scope/v1"
TEMPLATE_FIELD_PERMISSION = "PAYLOAD_ONLY"
TEMPLATE_FIELD_SOURCE_ROLE = "TEMPLATE_FIELD"
TEMPLATE_FIELD_PAYLOAD_ROLES = {
    "适用题目": "EDITORIAL_PAYLOAD/APPLICABILITY_CLASSIFICATION",
    "逻辑链条": "EDITORIAL_PAYLOAD/TEACHING_REASONING",
    "给定首句": "READER_FACING_ARTIFACT_ROLE/PROMPT_STEM",
    "用词建议": "EDITORIAL_PAYLOAD/LEXICAL_GUIDANCE",
}
TEMPLATE_FIELD_LINE_RE = re.compile(
    r"^[ \t]*(?P<label>适用题目|逻辑链条|给定首句|用词建议)"
    r"(?P<separator>[：:])(?P<payload>.*)$"
)
REQUIRED_POLICY_HASHES = {
    "validator_sha256",
    "invariant_checker_sha256",
    "scanner_sha256",
    "lexicon_sha256",
    "report_extractor_sha256",
    "runtime_contract_sha256",
    "paired_quality_verifier_sha256",
    "paired_quality_contract_sha256",
}
LEGACY_POLICY_HASHES = REQUIRED_POLICY_HASHES - {
    "paired_quality_verifier_sha256",
    "paired_quality_contract_sha256",
}


class ReplayError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_status_exit_pair(
    status: Any,
    exit_code: Any,
    *,
    code: str,
    label: str,
) -> None:
    if (
        not isinstance(status, str)
        or status not in STATUS_EXIT_CODES
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
        or exit_code != STATUS_EXIT_CODES[status]
    ):
        raise ReplayError(code, f"{label} status and exit code violate the fixed mapping")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReplayError("DUPLICATE_JSON_KEY", f"{label} duplicates key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ReplayError("NON_FINITE_JSON", f"{label} contains {value}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReplayError("NON_UTF8_JSON", f"{label} is not UTF-8") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ReplayError("INVALID_JSON", f"{label}: {error.msg}") from error


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReplayError("INVALID_SCHEMA", f"{label} must be an object")
    return value


def _template_field_scope_payload(
    raw: bytes,
    *,
    before_raw: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _object(
        _strict_json(raw, "archived template field edit scope"),
        "archived template field edit scope",
    )
    top_fields = {"schema_version", "source_sha256", "edits"}
    _exact_keys(payload, top_fields, top_fields, "archived template field edit scope")
    if payload.get("schema_version") != TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA:
        raise ReplayError(
            "INVALID_TEMPLATE_FIELD_SCOPE",
            "template field edit scope schema_version is invalid",
        )
    source_sha = payload.get("source_sha256")
    if not isinstance(source_sha, str) or not HEX64_RE.fullmatch(source_sha):
        raise ReplayError(
            "INVALID_INPUT_HASH",
            "template field edit scope source_sha256 is invalid",
        )
    if source_sha != _sha256(before_raw):
        raise ReplayError(
            "INPUT_BINDING_MISMATCH",
            "template field edit scope source_sha256 differs from before",
        )
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ReplayError(
            "INVALID_TEMPLATE_FIELD_SCOPE",
            "template field edit scope edits must be a non-empty array",
        )
    try:
        before_text = before_raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ReplayError("NON_UTF8_INPUT", "archived before input is not UTF-8") from error
    before_lines = before_text.splitlines()
    normalized_edits: list[dict[str, Any]] = []
    seen_lines: set[int] = set()
    edit_fields = {"line", "label", "permission", "reason"}
    for ordinal, raw_edit in enumerate(edits, 1):
        edit = _object(raw_edit, f"template field edit scope edits[{ordinal}]")
        _exact_keys(
            edit,
            edit_fields,
            edit_fields,
            f"template field edit scope edits[{ordinal}]",
        )
        line = edit.get("line")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope edits[{ordinal}].line is invalid",
            )
        if line in seen_lines:
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope duplicates source line {line}",
            )
        seen_lines.add(line)
        label = edit.get("label")
        if label not in TEMPLATE_FIELD_PAYLOAD_ROLES:
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope edits[{ordinal}].label is unknown",
            )
        if edit.get("permission") != TEMPLATE_FIELD_PERMISSION:
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope edits[{ordinal}].permission is invalid",
            )
        reason = edit.get("reason")
        if not isinstance(reason, str):
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope edits[{ordinal}].reason is invalid",
            )
        normalized_reason = reason.strip()
        if (
            not normalized_reason
            or len(normalized_reason.encode("utf-8")) > 1024
            or any(ord(char) < 32 or ord(char) == 127 for char in normalized_reason)
        ):
            raise ReplayError(
                "INVALID_TEMPLATE_FIELD_SCOPE",
                f"template field edit scope edits[{ordinal}].reason is invalid",
            )
        if line > len(before_lines):
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                f"template field edit scope line {line} is outside before",
            )
        source_match = TEMPLATE_FIELD_LINE_RE.fullmatch(before_lines[line - 1])
        if source_match is None or source_match.group("label") != label:
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                f"template field edit scope line {line} does not identify {label} in before",
            )
        normalized_edits.append(
            {
                "line": line,
                "label": label,
                "permission": TEMPLATE_FIELD_PERMISSION,
                "reason": normalized_reason,
                "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
                "payload_role": TEMPLATE_FIELD_PAYLOAD_ROLES[label],
                "before_payload_sha256": _sha256(
                    source_match.group("payload").encode("utf-8")
                ),
            }
        )
    return payload, sorted(normalized_edits, key=lambda item: item["line"])


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
        raise ReplayError(
            "INVALID_SCHEMA",
            f"{label} keys differ; missing={missing}, unknown={unknown}",
        )


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_reparse_ancestors(path: Path) -> None:
    current = _absolute_without_resolving(path)
    while True:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            attributes = int(getattr(info, "st_file_attributes", 0))
            if current.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ReplayError(
                    "REPARSE_POINT_REJECTED",
                    f"record path crosses a symlink or reparse point: {current}",
                )
        parent = current.parent
        if parent == current:
            return
        current = parent


def _read_regular_single_link(path: Path, label: str) -> bytes:
    _assert_no_reparse_ancestors(path)
    try:
        info = path.lstat()
    except OSError as error:
        raise ReplayError("MISSING_ARTIFACT", f"{label} is missing") from error
    if not stat.S_ISREG(info.st_mode):
        raise ReplayError("NON_REGULAR_ARTIFACT", f"{label} is not a regular file")
    if int(getattr(info, "st_nlink", 1)) != 1:
        raise ReplayError("HARDLINK_REJECTED", f"{label} is a hard link")
    return path.read_bytes()


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReplayError("UNSAFE_ARTIFACT_PATH", f"unsafe artifact path: {value}")
    return path.as_posix()


def _current_policy_hashes() -> dict[str, str]:
    paths = {
        "validator_sha256": VALIDATOR,
        "invariant_checker_sha256": INVARIANT_CHECKER,
        "scanner_sha256": SCANNER,
        "lexicon_sha256": LEXICON,
        "report_extractor_sha256": REPORT_EXTRACTOR,
        "paired_quality_verifier_sha256": PAIRED_QUALITY_VERIFIER,
        "paired_quality_contract_sha256": PAIRED_QUALITY_CONTRACT,
    }
    result = {name: _sha256(path.read_bytes()) for name, path in paths.items()}
    runtime_contract = {
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "python_version": list(sys.version_info[:3]),
        "unicode_version": unicodedata.unidata_version,
        "os_name": os.name,
        "policy_reference_hashes": {
            name: _sha256(path.read_bytes())
            for name, path in sorted(
                {
                    "skill_md": SCRIPT_DIR.parent / "SKILL.md",
                    "operational_contract": SCRIPT_DIR.parent / "references" / "operational-contract.md",
                    "workflow": SCRIPT_DIR.parent / "references" / "workflow.md",
                    "scene_routing_policy": SCRIPT_DIR.parent / "references" / "scene-routing-policy.json",
                    "source_provenance_trust": SCRIPT_DIR.parent / "references" / "source-provenance-trust.json",
                    "paired_quality_clearance_contract": PAIRED_QUALITY_CONTRACT,
                }.items()
            )
        },
    }
    result["runtime_contract_sha256"] = _sha256(
        _canonical_json_bytes(runtime_contract)
    )
    return result


def _load_record(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = _absolute_without_resolving(root)
    _assert_no_reparse_ancestors(root)
    if not root.is_dir():
        raise ReplayError("INVALID_RECORD_ROOT", "record root must be a directory")
    manifest_path = root / "evidence-manifest.json"
    manifest_raw = _read_regular_single_link(manifest_path, "evidence manifest")
    manifest = _object(_strict_json(manifest_raw, "evidence manifest"), "manifest")
    if manifest_raw != _pretty_json_bytes(manifest):
        raise ReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "evidence manifest bytes are not the required deterministic rendering",
        )
    required_manifest = {
        "schema",
        "run_id",
        "integrity_scope",
        "external_anchor_status",
        "contains_source_content",
        "invocation_request_sha256",
        "status",
        "delivery_gate_status",
        "exit_code",
        "mode",
        "scene",
        "paired_quality_review_status",
        "paired_quality_review_request_sha256",
        "source_bindings",
        "artifacts",
        "record_sha256",
        "manifest_sha256",
    }
    _exact_keys(manifest, required_manifest, required_manifest, "manifest")
    evidence_schema = manifest.get("schema")
    if evidence_schema not in EVIDENCE_SCHEMAS:
        raise ReplayError("UNSUPPORTED_SCHEMA", "evidence schema is not a supported v2-v5 schema")
    if manifest.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
        raise ReplayError("INVALID_INTEGRITY_SCOPE", "integrity scope was overstated")
    if manifest.get("external_anchor_status") != "NOT_PROVIDED":
        raise ReplayError("UNVERIFIED_EXTERNAL_ANCHOR", "unsupported external anchor claim")
    if manifest.get("contains_source_content") is not True:
        raise ReplayError(
            "INVALID_CONTENT_CLASSIFICATION",
            "evidence must disclose that source content is archived",
        )
    manifest_body = dict(manifest)
    manifest_sha = manifest_body.pop("manifest_sha256")
    if not isinstance(manifest_sha, str) or not HEX64_RE.fullmatch(manifest_sha):
        raise ReplayError("INVALID_MANIFEST_HASH", "manifest_sha256 is invalid")
    if _sha256(_canonical_json_bytes(manifest_body)) != manifest_sha:
        raise ReplayError("MANIFEST_HASH_MISMATCH", "manifest self-hash does not match")

    artifact_records = _object(manifest.get("artifacts"), "manifest.artifacts")
    expected_files = {"evidence-manifest.json"}
    artifacts: dict[str, bytes] = {}
    for raw_name, raw_record in artifact_records.items():
        if not isinstance(raw_name, str):
            raise ReplayError("INVALID_SCHEMA", "artifact name must be a string")
        name = _safe_relative(raw_name)
        record = _object(raw_record, f"artifact record {name}")
        _exact_keys(record, {"sha256", "size"}, {"sha256", "size"}, name)
        sha = record.get("sha256")
        size = record.get("size")
        if not isinstance(sha, str) or not HEX64_RE.fullmatch(sha):
            raise ReplayError("INVALID_ARTIFACT_HASH", f"invalid hash for {name}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReplayError("INVALID_ARTIFACT_SIZE", f"invalid size for {name}")
        raw = _read_regular_single_link(root / Path(name), name)
        if len(raw) != size or _sha256(raw) != sha:
            raise ReplayError("ARTIFACT_HASH_MISMATCH", f"artifact drifted: {name}")
        artifacts[name] = raw
        expected_files.add(name)

    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        _assert_no_reparse_ancestors(path)
        if path.is_symlink():
            raise ReplayError("REPARSE_POINT_REJECTED", f"symlink in record: {relative}")
        if path.is_dir():
            actual_dirs.add(relative)
        elif path.is_file():
            actual_files.add(relative)
        else:
            raise ReplayError("NON_REGULAR_ARTIFACT", f"special path in record: {relative}")
    expected_dirs = {
        str(PurePosixPath(name).parent)
        for name in expected_files
        if str(PurePosixPath(name).parent) != "."
    }
    if actual_files != expected_files or actual_dirs != expected_dirs:
        raise ReplayError(
            "RECORD_INVENTORY_MISMATCH",
            "record contains missing, extra, or unexpected directory entries",
        )

    identity = {
        "schema": evidence_schema,
        "run_id": manifest["run_id"],
        "artifacts": artifact_records,
    }
    if _sha256(_canonical_json_bytes(identity)) != manifest.get("record_sha256"):
        raise ReplayError("RECORD_HASH_MISMATCH", "record_sha256 does not match artifacts")
    artifacts["evidence-manifest.json"] = manifest_raw
    return manifest, artifacts


def _validate_invocation(
    manifest: dict[str, Any], artifacts: dict[str, bytes]
) -> dict[str, Any]:
    raw = artifacts.get("invocation-request.json")
    if raw is None:
        raise ReplayError("MISSING_INVOCATION", "invocation-request.json is missing")
    invocation = _object(_strict_json(raw, "invocation request"), "invocation")
    if raw != _pretty_json_bytes(invocation):
        raise ReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "invocation request bytes are not the required deterministic rendering",
        )
    required = {
        "schema",
        "validator_entrypoint",
        "arguments",
        "inputs",
        "policy_hashes",
        "expected",
        "reexecution",
        "privacy",
        "invocation_sha256",
        "run_id",
    }
    _exact_keys(invocation, required, required, "invocation")
    invocation_schema = invocation.get("schema")
    if invocation_schema not in INVOCATION_SCHEMAS:
        raise ReplayError("UNSUPPORTED_INVOCATION", "invocation schema is unsupported")
    expected_evidence_version, run_prefix = INVOCATION_SCHEMAS[invocation_schema]
    if EVIDENCE_SCHEMAS.get(manifest.get("schema")) != expected_evidence_version:
        raise ReplayError(
            "UNSUPPORTED_INVOCATION",
            "invocation and evidence schema versions do not match",
        )
    if invocation.get("validator_entrypoint") != "scripts/validate_humanize_output.py":
        raise ReplayError("INVALID_ENTRYPOINT", "validator entrypoint is not fixed")
    body = dict(invocation)
    invocation_sha = body.pop("invocation_sha256", None)
    run_id = body.pop("run_id", None)
    if not isinstance(invocation_sha, str) or not HEX64_RE.fullmatch(invocation_sha):
        raise ReplayError("INVALID_INVOCATION_HASH", "invocation_sha256 is invalid")
    if _sha256(_canonical_json_bytes(body)) != invocation_sha:
        raise ReplayError("INVOCATION_HASH_MISMATCH", "invocation self-hash does not match")
    if run_id != f"{run_prefix}-{invocation_sha}" or run_id != manifest.get("run_id"):
        raise ReplayError("RUN_ID_MISMATCH", "run_id is not bound to the invocation")
    if invocation_sha != manifest.get("invocation_request_sha256"):
        raise ReplayError("INVOCATION_MANIFEST_MISMATCH", "manifest invocation binding differs")

    arguments = _object(invocation.get("arguments"), "invocation.arguments")
    argument_keys = {
        "mode",
        "scene",
        "output_format",
        "strict_speech_acts",
        "fragment_mode",
        "protected_terms",
        "keep_reasons",
        "warning_resolutions",
        "warning_review_request_sha256",
        "report_scope",
    }
    if invocation_schema in {
        "humanize-validation-invocation/v3",
        "humanize-validation-invocation/v4",
    }:
        argument_keys.add("document_format")
    if invocation_schema == "humanize-validation-invocation/v4":
        argument_keys.add("template_field_edit_scope")
    if invocation_schema == "humanize-validation-invocation/v1":
        argument_keys.add("warning_reviewer_kind")
        argument_keys.add("warning_reviewer_id_sha256")
    _exact_keys(arguments, argument_keys, argument_keys, "invocation.arguments")
    if arguments.get("mode") not in {"REWRITE", "DRAFT"}:
        raise ReplayError("INVALID_ARGUMENT", "recorded mode is invalid")
    if arguments.get("scene") not in {"AUTO", "GENERAL", "COURSE", "MODELING", "RESEARCH"}:
        raise ReplayError("INVALID_ARGUMENT", "recorded scene is invalid")
    if arguments.get("output_format") not in {"json", "text"}:
        raise ReplayError("INVALID_ARGUMENT", "recorded output format is invalid")
    if invocation_schema in {
        "humanize-validation-invocation/v3",
        "humanize-validation-invocation/v4",
    } and arguments.get("document_format") not in {"markdown", "tex"}:
        raise ReplayError("INVALID_ARGUMENT", "recorded document format is invalid")
    for key in ("strict_speech_acts", "fragment_mode"):
        if not isinstance(arguments.get(key), bool):
            raise ReplayError("INVALID_ARGUMENT", f"{key} must be boolean")
    terms = arguments.get("protected_terms")
    if not isinstance(terms, list) or any(not isinstance(item, str) for item in terms):
        raise ReplayError("INVALID_ARGUMENT", "protected_terms must be a string array")
    if len(terms) != len(set(terms)):
        raise ReplayError("INVALID_ARGUMENT", "protected_terms contains duplicates")
    for key in ("keep_reasons", "warning_resolutions"):
        mapping = arguments.get(key)
        if not isinstance(mapping, dict) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in mapping.items()
        ):
            raise ReplayError("INVALID_ARGUMENT", f"{key} must be a string map")

    report_scope = _object(arguments.get("report_scope"), "arguments.report_scope")
    if report_scope.get("provided") is True:
        report_fields = {
            "provided",
            "scope_archive_path",
            "report_archive_path",
            "report_original_suffix",
        }
        if invocation_schema in {
            "humanize-validation-invocation/v2",
            "humanize-validation-invocation/v3",
            "humanize-validation-invocation/v4",
        }:
            report_fields.add("scope_semantic_sha256")
        _exact_keys(report_scope, report_fields, report_fields, "arguments.report_scope")
    elif report_scope.get("provided") is False:
        _exact_keys(report_scope, {"provided"}, {"provided"}, "arguments.report_scope")
    else:
        raise ReplayError("INVALID_ARGUMENT", "report_scope.provided must be boolean")

    template_field_edit_scope: dict[str, Any] = {"provided": False}
    if invocation_schema == "humanize-validation-invocation/v4":
        template_field_edit_scope = _object(
            arguments.get("template_field_edit_scope"),
            "arguments.template_field_edit_scope",
        )
        if template_field_edit_scope.get("provided") is True:
            template_scope_fields = {
                "provided",
                "archive_path",
                "sha256",
                "source_sha256",
                "permission_boundary",
                "local_clearance_supported",
            }
            _exact_keys(
                template_field_edit_scope,
                template_scope_fields,
                template_scope_fields,
                "arguments.template_field_edit_scope",
            )
        elif template_field_edit_scope.get("provided") is False:
            _exact_keys(
                template_field_edit_scope,
                {"provided"},
                {"provided"},
                "arguments.template_field_edit_scope",
            )
        else:
            raise ReplayError(
                "INVALID_ARGUMENT",
                "template_field_edit_scope.provided must be boolean",
            )

    inputs = _object(invocation.get("inputs"), "invocation.inputs")
    expected_inputs = {"before", "after"}
    if report_scope["provided"]:
        expected_inputs.update({"report_scope", "report"})
    if template_field_edit_scope["provided"]:
        expected_inputs.add("template_field_edit_scope")
    if set(inputs) != expected_inputs:
        raise ReplayError("INVALID_INPUT_SET", "invocation input set is not closed")
    expected_archives = {
        "before": "inputs/before.bin",
        "after": "inputs/after.bin",
        "report_scope": "inputs/report-scope.json",
        "report": "inputs/report.bin",
        "template_field_edit_scope": "inputs/template-field-edit-scope.json",
    }
    for role, value in inputs.items():
        record = _object(value, f"invocation input {role}")
        if invocation_schema == "humanize-validation-invocation/v1":
            fields = {
                "archive_path",
                "original_name",
                "original_suffix",
                "original_path_sha256",
                "sha256",
                "size",
            }
        else:
            fields = {
                "archive_path",
                "original_suffix",
                "sha256",
                "size",
            }
        _exact_keys(record, fields, fields, f"invocation input {role}")
        archive = _safe_relative(str(record.get("archive_path", "")))
        if archive != expected_archives[role]:
            raise ReplayError("INPUT_BINDING_MISMATCH", f"unexpected archive path: {role}")
        suffix = record.get("original_suffix")
        if not isinstance(suffix, str) or (
            suffix and not re.fullmatch(r"\.[A-Za-z0-9]{1,16}", suffix)
        ):
            raise ReplayError("INVALID_INPUT_SUFFIX", f"unsafe original suffix: {role}")
        if invocation_schema == "humanize-validation-invocation/v1":
            original_name = record.get("original_name")
            if (
                not isinstance(original_name, str)
                or not original_name
                or Path(original_name).name != original_name
            ):
                raise ReplayError("INVALID_INPUT_NAME", f"unsafe original name: {role}")
            hash_keys = ("original_path_sha256", "sha256")
        else:
            hash_keys = ("sha256",)
        for hash_key in hash_keys:
            value_hash = record.get(hash_key)
            if not isinstance(value_hash, str) or not HEX64_RE.fullmatch(value_hash):
                raise ReplayError("INVALID_INPUT_HASH", f"invalid {hash_key}: {role}")
        size = record.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReplayError("INVALID_INPUT_SIZE", f"invalid input size: {role}")
        raw_input = artifacts.get(archive)
        if raw_input is None:
            raise ReplayError("MISSING_INPUT", f"archived input missing: {role}")
        if _sha256(raw_input) != record.get("sha256") or len(raw_input) != record.get("size"):
            raise ReplayError("INPUT_BINDING_MISMATCH", f"input binding differs: {role}")

    if template_field_edit_scope["provided"]:
        if arguments.get("mode") != "REWRITE":
            raise ReplayError(
                "INVALID_ARGUMENT",
                "template field edit scope is only valid for REWRITE",
            )
        archive = _safe_relative(
            str(template_field_edit_scope.get("archive_path", ""))
        )
        if archive != expected_archives["template_field_edit_scope"]:
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "template field edit scope archive path differs",
            )
        scope_sha = template_field_edit_scope.get("sha256")
        source_sha = template_field_edit_scope.get("source_sha256")
        if not isinstance(scope_sha, str) or not HEX64_RE.fullmatch(scope_sha):
            raise ReplayError("INVALID_INPUT_HASH", "template field scope hash is invalid")
        if not isinstance(source_sha, str) or not HEX64_RE.fullmatch(source_sha):
            raise ReplayError("INVALID_INPUT_HASH", "template field source hash is invalid")
        scope_input = _object(
            inputs.get("template_field_edit_scope"),
            "template field edit scope input",
        )
        if scope_sha != scope_input.get("sha256"):
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "template field edit scope hashes differ",
            )
        if source_sha != inputs["before"].get("sha256"):
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "template field edit scope source hash differs",
            )
        if template_field_edit_scope.get("permission_boundary") != TEMPLATE_FIELD_PERMISSION:
            raise ReplayError(
                "INVALID_ARGUMENT",
                "template field edit scope permission boundary differs",
            )
        if template_field_edit_scope.get("local_clearance_supported") is not False:
            raise ReplayError(
                "INVALID_ARGUMENT",
                "template field edit scope cannot grant local clearance",
            )
        scope_raw = artifacts.get(archive)
        if scope_raw is None or _sha256(scope_raw) != scope_sha:
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "archived template field edit scope hash differs",
            )
        _template_field_scope_payload(
            scope_raw,
            before_raw=artifacts[inputs["before"]["archive_path"]],
        )

    privacy = _object(invocation.get("privacy"), "invocation.privacy")
    reviewer_hash: Any = None
    reviewer_label_present = False
    if invocation_schema == "humanize-validation-invocation/v1":
        privacy_fields = {
            "raw_warning_reviewer_id_archived",
            "warning_reviewer_id_sha256",
        }
        _exact_keys(privacy, privacy_fields, privacy_fields, "invocation.privacy")
        if privacy.get("raw_warning_reviewer_id_archived") is not False:
            raise ReplayError("REVIEWER_PRIVACY_BREACH", "raw reviewer identity was archived")
        reviewer_hash = arguments.get("warning_reviewer_id_sha256")
        if reviewer_hash and (
            not isinstance(reviewer_hash, str) or not HEX64_RE.fullmatch(reviewer_hash)
        ):
            raise ReplayError("INVALID_REVIEWER_HASH", "reviewer pseudonym hash is invalid")
        if privacy.get("warning_reviewer_id_sha256") != reviewer_hash:
            raise ReplayError("REVIEWER_PRIVACY_MISMATCH", "reviewer hash bindings differ")
        reviewer_label_present = bool(reviewer_hash)
    else:
        privacy_fields = {
            "reviewer_identifier_collected",
            "stable_reviewer_pseudonym_archived",
            "source_locator_archived",
            "contains_unredacted_proposal_text",
        }
        _exact_keys(privacy, privacy_fields, privacy_fields, "invocation.privacy")
        if (
            privacy.get("reviewer_identifier_collected") is not False
            or privacy.get("stable_reviewer_pseudonym_archived") is not False
            or privacy.get("source_locator_archived") is not False
            or privacy.get("contains_unredacted_proposal_text")
            is not bool(arguments.get("warning_resolutions"))
        ):
            raise ReplayError(
                "REVIEWER_PRIVACY_MISMATCH",
                "reviewer label minimization bindings differ",
            )

    policy_hashes = _object(invocation.get("policy_hashes"), "invocation.policy_hashes")
    required_policy_hashes = (
        REQUIRED_POLICY_HASHES
        if invocation_schema
        in {
            "humanize-validation-invocation/v3",
            "humanize-validation-invocation/v4",
        }
        else LEGACY_POLICY_HASHES
    )
    _exact_keys(
        policy_hashes,
        required_policy_hashes,
        required_policy_hashes,
        "invocation.policy_hashes",
    )
    for key, value in policy_hashes.items():
        if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
            raise ReplayError("INVALID_POLICY_HASH", f"invalid policy hash: {key}")

    expected = _object(invocation.get("expected"), "invocation.expected")
    expected_fields = {
        "delivery_gate_status",
        "exit_code",
        "paired_quality_review_request_sha256",
    }
    _exact_keys(expected, expected_fields, expected_fields, "invocation.expected")
    _require_status_exit_pair(
        expected.get("delivery_gate_status"),
        expected.get("exit_code"),
        code="INVALID_EXPECTED_STATUS",
        label="expected delivery",
    )

    reexecution = _object(invocation.get("reexecution"), "invocation.reexecution")
    _exact_keys(
        reexecution,
        {"status", "reasons"},
        {"status", "reasons"},
        "invocation.reexecution",
    )
    if not isinstance(reexecution.get("reasons"), list) or any(
        not isinstance(item, str) for item in reexecution.get("reasons", [])
    ):
        raise ReplayError("INVALID_REEXECUTION_STATUS", "reexecution reasons are invalid")
    warning_resolutions = arguments["warning_resolutions"]
    reviewer_kind = arguments.get("warning_reviewer_kind", "NONE")
    reviewer_request = arguments.get("warning_review_request_sha256")
    expected_replay_reasons = (
        ["WARNING_REVIEWER_ID_NOT_ARCHIVED"]
        if invocation_schema == "humanize-validation-invocation/v1"
        and (warning_resolutions or reviewer_label_present)
        else []
    )
    expected_replay_status = (
        "REEXECUTION_NOT_SUPPORTED" if expected_replay_reasons else "SUPPORTED"
    )
    if (
        reexecution.get("status") != expected_replay_status
        or reexecution.get("reasons") != expected_replay_reasons
    ):
        raise ReplayError("INVALID_REEXECUTION_STATUS", "reexecution contract is inconsistent")
    if warning_resolutions:
        if not reviewer_request:
            raise ReplayError("REVIEWER_BINDING_MISMATCH", "proposal request binding is incomplete")
        if invocation_schema == "humanize-validation-invocation/v1" and (
            reviewer_kind != "HUMAN" or not reviewer_label_present
        ):
            raise ReplayError("REVIEWER_BINDING_MISMATCH", "legacy proposal reviewer binding is incomplete")
    elif reviewer_kind != "NONE" or reviewer_label_present or reviewer_request:
        raise ReplayError("REVIEWER_BINDING_MISMATCH", "reviewer metadata exists without proposal")
    if report_scope["provided"]:
        if (
            report_scope.get("scope_archive_path") != "inputs/report-scope.json"
            or report_scope.get("report_archive_path") != "inputs/report.bin"
        ):
            raise ReplayError("INPUT_BINDING_MISMATCH", "report archive paths differ")
        report_suffix = report_scope.get("report_original_suffix")
        if not isinstance(report_suffix, str) or (
            report_suffix and not re.fullmatch(r"\.[A-Za-z0-9]{1,16}", report_suffix)
        ):
            raise ReplayError("INVALID_INPUT_SUFFIX", "unsafe report suffix")
        if invocation_schema in {
            "humanize-validation-invocation/v2",
            "humanize-validation-invocation/v3",
            "humanize-validation-invocation/v4",
        }:
            semantic_sha = report_scope.get("scope_semantic_sha256")
            if not isinstance(semantic_sha, str) or not HEX64_RE.fullmatch(semantic_sha):
                raise ReplayError("INVALID_INPUT_HASH", "scope semantic hash is invalid")
    return invocation


def _validate_cross_artifact_consistency(
    manifest: dict[str, Any],
    artifacts: dict[str, bytes],
    invocation: dict[str, Any],
) -> dict[str, Any]:
    result_raw = artifacts["validation-result.json"]
    result = _object(
        _strict_json(result_raw, "validation result"),
        "validation result",
    )
    if result_raw != _pretty_json_bytes(result):
        raise ReplayError(
            "NON_CANONICAL_JSON_BYTES",
            "validation result bytes are not the required deterministic rendering",
        )
    expected = _object(invocation.get("expected"), "invocation.expected")
    _require_status_exit_pair(
        manifest.get("delivery_gate_status"),
        manifest.get("exit_code"),
        code="RESULT_STATUS_MISMATCH",
        label="manifest delivery",
    )
    _require_status_exit_pair(
        result.get("delivery_gate_status"),
        result.get("exit_code"),
        code="RESULT_STATUS_MISMATCH",
        label="validation result delivery",
    )
    for field in ("delivery_gate_status", "exit_code"):
        if result.get(field) != manifest.get(field) or result.get(field) != expected.get(field):
            raise ReplayError("RESULT_STATUS_MISMATCH", f"result binding differs: {field}")
    if result.get("status") != manifest.get("status") or result.get(
        "status"
    ) != result.get("delivery_gate_status"):
        raise ReplayError("RESULT_STATUS_MISMATCH", "result status bindings differ")
    for field in ("mode", "scene", "paired_quality_review_status"):
        if result.get(field) != manifest.get(field):
            raise ReplayError("RESULT_STATUS_MISMATCH", f"manifest differs: {field}")
    evidence = _object(result.get("evidence"), "validation result evidence")
    policy_hashes = _object(invocation.get("policy_hashes"), "invocation policy hashes")
    if evidence.get("policy_hashes") != policy_hashes:
        raise ReplayError("POLICY_BINDING_MISMATCH", "result policy hashes differ")
    source_bindings = _object(manifest.get("source_bindings"), "source_bindings")
    for role, evidence_key in (("before", "before_sha256"), ("after", "after_sha256")):
        source = _object(source_bindings.get(role), f"source binding {role}")
        invocation_input = _object(invocation["inputs"].get(role), f"input {role}")
        expected_source_fields = (
            {"name", "path_sha256", "sha256", "size"}
            if invocation.get("schema") == "humanize-validation-invocation/v1"
            else {"sha256", "size"}
        )
        _exact_keys(
            source,
            expected_source_fields,
            expected_source_fields,
            f"source binding {role}",
        )
        if not (
            source.get("sha256")
            == invocation_input.get("sha256")
            == evidence.get(evidence_key)
        ):
            raise ReplayError("SOURCE_BINDING_MISMATCH", f"source binding differs: {role}")

    paired = result.get("paired_quality_review_request")
    paired_raw = artifacts.get("paired-quality-review-request.json")
    paired_sha = ""
    if isinstance(paired, dict):
        paired_sha = str(paired.get("request_sha256", ""))
        if paired_raw != _pretty_json_bytes(paired):
            raise ReplayError("PAIRED_REQUEST_MISMATCH", "paired request artifact differs")
        if paired.get("policy_hashes") != policy_hashes:
            raise ReplayError("POLICY_BINDING_MISMATCH", "paired request policy differs")
    elif paired_raw is not None:
        raise ReplayError("UNEXPECTED_PAIRED_REQUEST", "paired request file is unexpected")
    if not (
        paired_sha
        == manifest.get("paired_quality_review_request_sha256")
        == expected.get("paired_quality_review_request_sha256")
    ):
        raise ReplayError("PAIRED_REQUEST_HASH_MISMATCH", "paired request hashes differ")

    warning = result.get("warning_review_request")
    warning_raw = artifacts.get("warning-review-request.json")
    if isinstance(warning, dict):
        if warning_raw != _pretty_json_bytes(warning):
            raise ReplayError("WARNING_REQUEST_MISMATCH", "warning request artifact differs")
        if warning.get("policy_hashes") != policy_hashes:
            raise ReplayError("POLICY_BINDING_MISMATCH", "warning request policy differs")
    elif warning_raw is not None:
        raise ReplayError("UNEXPECTED_WARNING_REQUEST", "warning request file is unexpected")

    report_scope = _object(invocation["arguments"].get("report_scope"), "report scope")
    if report_scope.get("provided") and "scope_semantic_sha256" in report_scope:
        result_scope = _object(result.get("report_scope_check"), "result report scope")
        if result_scope.get("scope_semantic_sha256") != report_scope.get(
            "scope_semantic_sha256"
        ):
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "report scope semantic hash differs from the validation result",
            )

    if invocation.get("schema") == "humanize-validation-invocation/v4":
        template_scope = _object(
            invocation["arguments"].get("template_field_edit_scope"),
            "template field edit scope",
        )
        result_scope = _object(
            result.get("template_field_edit_scope_check"),
            "result template field edit scope",
        )
        result_scope_fields = {
            "status",
            "provided",
            "schema_version",
            "scope_sha256",
            "source_sha256",
            "permission_boundary",
            "authorized_edit_count",
            "authorized_edits",
            "local_clearance_supported",
        }
        _exact_keys(
            result_scope,
            result_scope_fields,
            result_scope_fields,
            "result template field edit scope",
        )
        before_sha = invocation["inputs"]["before"].get("sha256")
        if template_scope.get("provided"):
            archive = str(template_scope["archive_path"])
            _scope_payload, expected_authorized_edits = _template_field_scope_payload(
                artifacts[archive],
                before_raw=artifacts[invocation["inputs"]["before"]["archive_path"]],
            )
            authorized_count = result_scope.get("authorized_edit_count")
            if (
                result_scope.get("status") != "PASS"
                or result_scope.get("provided") is not True
                or result_scope.get("schema_version")
                != TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA
                or result_scope.get("scope_sha256") != template_scope.get("sha256")
                or result_scope.get("source_sha256")
                != template_scope.get("source_sha256")
                or result_scope.get("source_sha256") != before_sha
                or result_scope.get("permission_boundary")
                != TEMPLATE_FIELD_PERMISSION
                or result_scope.get("local_clearance_supported") is not False
                or isinstance(authorized_count, bool)
                or not isinstance(authorized_count, int)
                or authorized_count != len(expected_authorized_edits)
                or result_scope.get("authorized_edits") != expected_authorized_edits
            ):
                raise ReplayError(
                    "INPUT_BINDING_MISMATCH",
                    "template field edit scope result binding differs",
                )
        elif result_scope != {
            "status": "N/A",
            "provided": False,
            "schema_version": None,
            "scope_sha256": None,
            "source_sha256": before_sha,
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "authorized_edit_count": 0,
            "authorized_edits": [],
            "local_clearance_supported": False,
        }:
            raise ReplayError(
                "INPUT_BINDING_MISMATCH",
                "absent template field edit scope result binding differs",
            )
        if result.get("paired_quality_review_local_clearance_supported") is not False:
            raise ReplayError(
                "RESULT_STATUS_MISMATCH",
                "paired quality review cannot claim local clearance support",
            )

    output_format = invocation["arguments"].get("output_format")
    rendered = artifacts.get("rendered-output.txt", b"")
    if output_format == "json":
        if rendered != _pretty_json_bytes(result):
            raise ReplayError("STDOUT_RESULT_MISMATCH", "JSON stdout differs from result")
    elif output_format == "text":
        if rendered != _recorded_text_output(
            result,
            legacy=invocation.get("schema") == "humanize-validation-invocation/v1",
            template_fields=(
                invocation.get("schema") == "humanize-validation-invocation/v4"
            ),
        ).encode("utf-8"):
            raise ReplayError("STDOUT_RESULT_MISMATCH", "text stdout differs from result")
    else:
        raise ReplayError("INVALID_OUTPUT_FORMAT", "recorded output format is invalid")
    if artifacts.get("stderr.txt") != b"":
        raise ReplayError("UNEXPECTED_STDERR", "successful evidence record has non-empty stderr")

    execution = _object(
        _strict_json(artifacts["execution-record.json"], "execution record"),
        "execution record",
    )
    execution_fields = {
        "schema",
        "run_id",
        "intended_exit_code",
        "rendered_stdout_sha256",
        "rendered_stderr_sha256",
        "process_exit_observation",
        "integrity_scope",
        "limitations",
    }
    _exact_keys(execution, execution_fields, execution_fields, "execution record")
    if execution.get("schema") != "humanize-validation-execution-record/v1":
        raise ReplayError("EXECUTION_RECORD_MISMATCH", "execution schema differs")
    if execution.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
        raise ReplayError("EXECUTION_CLAIM_OVERSTATED", "execution integrity scope differs")
    if execution.get("run_id") != manifest.get("run_id"):
        raise ReplayError("EXECUTION_RECORD_MISMATCH", "execution run_id differs")
    if execution.get("intended_exit_code") != result.get("exit_code"):
        raise ReplayError("EXECUTION_RECORD_MISMATCH", "intended exit code differs")
    if execution.get("rendered_stdout_sha256") != _sha256(rendered):
        raise ReplayError("EXECUTION_RECORD_MISMATCH", "stdout hash differs")
    if execution.get("rendered_stderr_sha256") != _sha256(artifacts["stderr.txt"]):
        raise ReplayError("EXECUTION_RECORD_MISMATCH", "stderr hash differs")
    if execution.get("process_exit_observation") != "NOT_EXTERNALLY_OBSERVED":
        raise ReplayError("EXECUTION_CLAIM_OVERSTATED", "process exit claim is unsupported")
    if execution.get("limitations") != [
        "NO_EXTERNAL_TIMESTAMP_OR_SIGNATURE",
        "OS_PROCESS_EXIT_NOT_OBSERVED_BY_AN_INDEPENDENT_PARENT",
        "NO_ACADEMIC_CORRECTNESS_OR_QUALITY_CLEARANCE",
    ]:
        raise ReplayError("EXECUTION_CLAIM_OVERSTATED", "execution limitations differ")

    if invocation.get("schema") in {
        "humanize-validation-invocation/v2",
        "humanize-validation-invocation/v3",
        "humanize-validation-invocation/v4",
    }:
        if "warning_review" in result:
            raise ReplayError(
                "REVIEWER_PRIVACY_BREACH",
                "v3 result contains a retired reviewer-bearing field",
            )
        proposal = _object(
            result.get("warning_proposal_state"),
            "warning proposal state",
        )
        proposal_fields = {
            "proposal_source",
            "reviewer_identifier_collected",
            "stable_reviewer_pseudonym_recorded",
            "cross_record_reviewer_linkability",
            "identity_verified",
            "review_clearance_granted",
            "attestation_status",
            "warning_review_request_sha256",
            "proposed_warning_fingerprints",
        }
        _exact_keys(proposal, proposal_fields, proposal_fields, "warning proposal state")
        proposal_source = proposal.get("proposal_source")
        expected_attestation = (
            "NOT_APPLICABLE"
            if proposal_source == "UNVERIFIED_CALLER_PROPOSAL"
            else "NOT_PROVIDED"
            if proposal_source == "NOT_PROVIDED"
            else None
        )
        if (
            expected_attestation is None
            or
            proposal.get("reviewer_identifier_collected") is not False
            or proposal.get("stable_reviewer_pseudonym_recorded") is not False
            or proposal.get("cross_record_reviewer_linkability") != "NOT_RECORDED"
            or proposal.get("identity_verified") is not False
            or proposal.get("review_clearance_granted") is not False
            or proposal.get("attestation_status") != expected_attestation
        ):
            raise ReplayError(
                "REVIEWER_PRIVACY_BREACH",
                "warning proposal identity or clearance fields are overstated",
            )
        resolutions = invocation["arguments"].get("warning_resolutions", {})
        if bool(resolutions) != (proposal_source == "UNVERIFIED_CALLER_PROPOSAL"):
            raise ReplayError(
                "REVIEWER_BINDING_MISMATCH",
                "warning proposal presence differs from invocation",
            )
        if resolutions:
            if (
                proposal.get("warning_review_request_sha256")
                != invocation["arguments"].get("warning_review_request_sha256")
                or proposal.get("proposed_warning_fingerprints")
                != sorted(resolutions)
            ):
                raise ReplayError(
                    "REVIEWER_BINDING_MISMATCH",
                    "warning proposal request or fingerprints differ",
                )
        elif (
            proposal.get("warning_review_request_sha256") is not None
            or proposal.get("proposed_warning_fingerprints") != []
        ):
            raise ReplayError(
                "REVIEWER_BINDING_MISMATCH",
                "empty warning proposal contains request metadata",
            )
    return result


def _recorded_text_output(
    payload: dict[str, Any],
    *,
    legacy: bool,
    template_fields: bool = False,
) -> str:
    evidence = _object(payload.get("evidence"), "validation result evidence")
    summary = _object(payload.get("lexical_summary"), "validation lexical summary")
    lines = [
        f"status: {payload['status']}",
        f"delivery_gate_status: {payload['delivery_gate_status']}",
        f"hard_invariant_layer_status: {payload['hard_invariant_layer_status']}",
        f"speech_act_layer_status: {payload['speech_act_layer_status']}",
        f"style_signal_layer_status: {payload['style_signal_layer_status']}",
    ]
    if template_fields:
        lines.append(
            "template_field_layer_status: "
            + str(payload["template_field_layer_status"])
        )
    if not legacy:
        lines.append(
            "paired_style_delta_layer_status: "
            + str(payload["paired_style_delta_layer_status"])
        )
    lines.extend(
        (
        f"candidate_assembly_status: {payload['candidate_assembly_status']}",
        f"mechanical_validation_status: {payload['mechanical_validation_status']}",
        f"paired_quality_review_status: {payload['paired_quality_review_status']}",
        "paired_quality_review_request_sha256: "
        + (
            payload["paired_quality_review_request"]["request_sha256"]
            if payload.get("paired_quality_review_request")
            else "NONE"
        ),
        "paired_quality_clearance_granted: "
        + str(payload["paired_quality_clearance_granted"]).upper(),
        "humanize_quality_claim_allowed: "
        + str(payload["humanize_quality_claim_allowed"]).upper(),
        f"academic_correctness: {payload['academic_correctness']}",
        f"mode: {payload['mode']}",
        f"document_scope: {evidence['document_scope']}",
        f"draft_surface_source_check: {payload['draft_surface_source_check']['status']}",
        f"report_scope_check: {payload['report_scope_check']['status']}",
        )
    )
    if template_fields:
        lines.append(
            "template_field_edit_scope_check: "
            + str(payload["template_field_edit_scope_check"]["status"])
        )
    lines.append(f"semantic_source_check: {payload['semantic_source_check']}")
    if legacy:
        review = _object(payload.get("warning_review"), "legacy warning review")
        lines.extend(
            (
                f"warning_reviewer_kind: {review['reviewer_kind']}",
                f"warning_review_attestation_status: {review['attestation_status']}",
                "warning_reviewer_identity_verified: "
                + str(review["identity_verified"]).upper(),
                "warning_review_clearance_granted: "
                + str(review["review_clearance_granted"]).upper(),
                f"warning_reviewer_id_sha256: {review['reviewer_id_sha256'] or 'NONE'}",
            )
        )
    else:
        proposal = _object(
            payload.get("warning_proposal_state"),
            "warning proposal state",
        )
        lines.extend(
            (
                f"warning_proposal_source: {proposal['proposal_source']}",
                f"warning_proposal_attestation_status: {proposal['attestation_status']}",
                "warning_proposal_identity_verified: "
                + str(proposal["identity_verified"]).upper(),
                "warning_proposal_clearance_granted: "
                + str(proposal["review_clearance_granted"]).upper(),
                "warning_reviewer_identifier_collected: "
                + str(proposal["reviewer_identifier_collected"]).upper(),
                "warning_stable_reviewer_pseudonym_recorded: "
                + str(proposal["stable_reviewer_pseudonym_recorded"]).upper(),
            )
        )
    lines.extend(
        (
            "warning_review_request_sha256: "
            + (
                payload["warning_review_request"]["request_sha256"]
                if payload.get("warning_review_request")
                else "NONE"
            ),
            f"before_sha256: {evidence['before_sha256']}",
            f"after_sha256: {evidence['after_sha256']}",
            f"protected_terms: {evidence['protected_terms']['status']}",
            f"protected_term_count: {evidence['protected_terms']['count']}",
            f"protected_term_sha256: {evidence['protected_terms']['sha256'] or 'NONE'}",
            f"invariant_errors: {payload['invariants']['summary']['errors']}",
            f"invariant_warnings: {payload['invariants']['summary']['warnings']}",
            f"after_candidates: {summary['after_candidates']}",
            f"introduced_candidates: {summary['introduced_candidates']}",
            f"unexplained_high_candidates: {summary['unexplained_high_candidates']}",
            f"accepted_candidates: {summary['accepted_candidates']}",
        )
    )
    if not legacy:
        paired_summary = _object(
            payload.get("paired_style_delta_summary"),
            "paired style delta summary",
        )
        lines.append(
            "paired_style_delta_findings: "
            + str(paired_summary["finding_count"])
        )
    if template_fields:
        template_summary = _object(
            payload.get("template_field_summary"),
            "template field summary",
        )
        lines.append(
            "template_field_findings: "
            + str(template_summary["finding_count"])
        )
    for reason in payload.get("review_reasons", []):
        lines.append(f"review: {reason}")
    for warning in payload.get("unaccepted_warnings", []):
        lines.append(
            f"warning: {warning['code']} [{warning['severity']}] {warning['message']}"
        )
    for finding in payload.get("unexplained_high_findings", []):
        display_file = Path(str(finding["file"])).name
        lines.append(
            f"[{finding['signal_id']}/{finding['severity']}] "
            f"{display_file}:{finding['line']}:{finding['column']} {finding['matched']}"
        )
    if not legacy:
        for finding in payload.get("paired_style_delta_findings", []):
            lines.append(
                f"paired-style: {finding['code']} [{finding['severity']}] "
                f"transitions={finding['observed']['distinct_transition_count']} "
                f"hunks={finding['observed']['changed_hunk_count']}"
            )
            for transition in finding["transitions"]:
                removed = transition["removed"]
                introduced = transition["introduced"]
                lines.append(
                    f"paired-style-span: {transition['transition_id']} "
                    f"before:{removed['line']}:{removed['column']}={removed['text']} "
                    f"after:{introduced['line']}:{introduced['column']}={introduced['text']}"
                )
    if template_fields:
        for finding in payload.get("template_field_findings", []):
            lines.append(
                "template-field: "
                f"{finding['code']} [{finding['severity']}] "
                f"line={finding.get('source_line', 'N/A')} "
                f"label={finding.get('field_label', 'HEADER')} "
                f"authorization={finding['authorization_status']} "
                f"types={','.join(finding['change_types']) or 'NONE'}"
            )
    return "\n".join(lines) + "\n"


def _normalized_core(payload: dict[str, Any]) -> Any:
    path_keys = {
        "before_path",
        "after_path",
        "scope_path",
        "report_path",
        "source_path",
        "file",
    }

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: ("<PATH>" if key in path_keys else normalize(item))
                for key, item in value.items()
                if key != "evidence_bundle"
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    fields = (
        "status",
        "exit_code",
        "candidate_assembly_status",
        "candidate_assembly_exit_code",
        "mechanical_validation_status",
        "mechanical_validation_exit_code",
        "delivery_gate_status",
        "delivery_gate_exit_code",
        "hard_invariant_layer_status",
        "speech_act_layer_status",
        "speech_act_diagnostics",
        "style_signal_layer_status",
        "template_field_layer_status",
        "template_field_findings",
        "template_field_edit_scope_check",
        "template_field_summary",
        "paired_style_delta_layer_status",
        "paired_style_delta_findings",
        "paired_style_delta_summary",
        "paired_quality_review_status",
        "paired_quality_review_request",
        "paired_quality_review_local_clearance_supported",
        "paired_quality_clearance_granted",
        "humanize_quality_claim_allowed",
        "academic_correctness",
        "mode",
        "scene",
        "draft_surface_source_check",
        "report_scope_check",
        "semantic_source_check",
        "evidence",
        "invariants",
        "lexical_summary",
        "review_reasons",
        "keep_reasons",
        "accepted_warning_reasons",
        "warning_resolutions",
        "warning_review_request",
        "warning_proposal_state",
        "accepted_findings",
        "accepted_warnings",
        "proposed_warning_resolutions",
        "pending_warnings",
        "warnings_without_resolution_proposal",
        "unaccepted_warnings",
        "unexplained_high_findings",
        "introduced_findings",
    )
    return normalize({field: payload.get(field) for field in fields})


def _replay_command(
    invocation: dict[str, Any],
    temp_root: Path,
    artifacts: dict[str, bytes],
    *,
    output_format: str,
) -> list[str]:
    arguments = invocation["arguments"]
    inputs = invocation["inputs"]
    before_suffix = str(inputs["before"].get("original_suffix") or ".txt")
    after_suffix = str(inputs["after"].get("original_suffix") or ".txt")
    before_path = temp_root / (
        str(inputs["before"].get("original_name"))
        if inputs["before"].get("original_name")
        else f"before{before_suffix}"
    )
    after_path = temp_root / (
        str(inputs["after"].get("original_name"))
        if inputs["after"].get("original_name")
        else f"after{after_suffix}"
    )
    before_path.write_bytes(artifacts[inputs["before"]["archive_path"]])
    after_path.write_bytes(artifacts[inputs["after"]["archive_path"]])
    command = [
        sys.executable,
        str(VALIDATOR),
        str(before_path),
        str(after_path),
        "--mode",
        str(arguments["mode"]),
        "--scene",
        str(arguments["scene"]),
        "--format",
        output_format,
    ]
    if invocation.get("schema") in {
        "humanize-validation-invocation/v3",
        "humanize-validation-invocation/v4",
    }:
        command.extend(("--document-format", str(arguments["document_format"])))
    if arguments.get("strict_speech_acts"):
        command.append("--strict-speech-acts")
    if arguments.get("fragment_mode"):
        command.append("--fragment")
    for term in arguments.get("protected_terms", []):
        command.extend(("--term", str(term)))
    for key, reason in arguments.get("keep_reasons", {}).items():
        command.extend(("--keep-reason", f"{key}={reason}"))
    if invocation.get("schema") in {
        "humanize-validation-invocation/v2",
        "humanize-validation-invocation/v3",
        "humanize-validation-invocation/v4",
    }:
        for fingerprint, reason in arguments.get("warning_resolutions", {}).items():
            command.extend(
                ("--propose-warning-resolution", f"{fingerprint}={reason}")
            )
        if arguments.get("warning_resolutions"):
            command.extend(
                (
                    "--warning-review-request-sha256",
                    str(arguments["warning_review_request_sha256"]),
                )
            )

    if invocation.get("schema") == "humanize-validation-invocation/v4":
        template_scope = _object(
            arguments.get("template_field_edit_scope"),
            "template field edit scope arguments",
        )
        if template_scope.get("provided"):
            replay_template_scope = temp_root / "template-field-edit-scope.json"
            replay_template_scope.write_bytes(
                artifacts[str(template_scope["archive_path"])]
            )
            command.extend(
                ("--template-field-edit-scope", str(replay_template_scope))
            )

    report_scope = _object(arguments.get("report_scope"), "report scope arguments")
    if report_scope.get("provided"):
        report_suffix = str(report_scope.get("report_original_suffix") or ".html")
        report_path = temp_root / f"detector-report{report_suffix}"
        report_path.write_bytes(artifacts[report_scope["report_archive_path"]])
        scope_payload = _object(
            _strict_json(
                artifacts[report_scope["scope_archive_path"]],
                "archived report scope",
            ),
            "archived report scope",
        )
        scope_payload["report_path"] = str(report_path.resolve())
        scope_payload["source_path"] = str(before_path.resolve())
        replay_scope = temp_root / "report-scope.json"
        replay_scope.write_bytes(_pretty_json_bytes(scope_payload))
        command.extend(("--report-scope", str(replay_scope)))
    return command


def _live_source_status(
    result: dict[str, Any],
    *,
    live_before: Path | None = None,
    live_after: Path | None = None,
) -> dict[str, Any]:
    evidence = _object(result.get("evidence"), "validation result evidence")
    explicit = {"before": live_before, "after": live_after}
    if live_before is None and live_after is None:
        legacy_paths = {
            "before": evidence.get("before_path"),
            "after": evidence.get("after_path"),
        }
        if not all(isinstance(value, str) and value for value in legacy_paths.values()):
            return {"status": "NOT_REQUESTED", "artifacts": {}}
        explicit = {role: Path(str(value)) for role, value in legacy_paths.items()}
    elif live_before is None or live_after is None:
        raise ReplayError(
            "INCOMPLETE_LIVE_SOURCE_ARGUMENTS",
            "live_before and live_after must be provided together",
        )
    records: dict[str, str] = {}
    for role, sha_key in (("before", "before_sha256"), ("after", "after_sha256")):
        expected_sha = evidence.get(sha_key)
        path = explicit[role]
        assert path is not None
        try:
            current = path.read_bytes()
        except OSError:
            records[role] = "MISSING"
        else:
            records[role] = "MATCH" if _sha256(current) == expected_sha else "DRIFTED"
    overall = "MATCH" if all(value == "MATCH" for value in records.values()) else "NOT_CURRENT"
    return {"status": overall, "artifacts": records}


def _replay_payload(
    *,
    replay_status: str,
    replay_exit_code: int,
    archived_result: dict[str, Any] | None,
    **fields: Any,
) -> dict[str, Any]:
    """Build an unambiguous replay envelope without upgrading the recorded gate."""
    payload = dict(fields)
    payload.update(
        {
            "schema": REPLAY_SCHEMA,
            "replay_status": replay_status,
            "replay_exit_code": replay_exit_code,
            "recorded_delivery_gate_status": (
                archived_result.get("delivery_gate_status")
                if archived_result is not None
                else None
            ),
            "recorded_exit_code": (
                archived_result.get("exit_code")
                if archived_result is not None
                else None
            ),
            "scope": "SELF_CONSISTENCY_ONLY",
            "integrity_scope": "SELF_CONSISTENCY_ONLY",
            "historical_authenticity": "NOT_EVALUATED",
            "academic_correctness": "NOT_EVALUATED",
            "paired_quality_clearance_granted": False,
            "humanize_quality_claim_allowed": False,
            # v1 compatibility aliases. New consumers must use replay_* fields.
            "status": replay_status,
            "exit_code": replay_exit_code,
            "status_compatibility": "DEPRECATED_ALIAS_OF_REPLAY_STATUS",
            "exit_code_compatibility": "DEPRECATED_ALIAS_OF_REPLAY_EXIT_CODE",
        }
    )
    return payload


def replay_record(
    root: Path,
    *,
    require_live_source_match: bool = False,
    live_before: Path | None = None,
    live_after: Path | None = None,
) -> tuple[dict[str, Any], int]:
    manifest, artifacts = _load_record(root)
    invocation = _validate_invocation(manifest, artifacts)
    archived_result = _validate_cross_artifact_consistency(
        manifest,
        artifacts,
        invocation,
    )
    initial_hashes = {name: _sha256(raw) for name, raw in artifacts.items()}
    live_status = _live_source_status(
        archived_result,
        live_before=live_before,
        live_after=live_after,
    )

    reexecution = _object(invocation.get("reexecution"), "invocation.reexecution")
    if reexecution.get("status") == "REEXECUTION_NOT_SUPPORTED":
        payload = _replay_payload(
            replay_status="REVIEW",
            replay_exit_code=2,
            archived_result=archived_result,
            record_integrity_status="PASS",
            reexecution_status="NOT_RUN",
            reexecution_reasons=reexecution.get("reasons", []),
            run_id=manifest["run_id"],
            live_source_status=live_status,
        )
        return payload, 2
    if reexecution.get("status") != "SUPPORTED":
        raise ReplayError("INVALID_REEXECUTION_STATUS", "unknown reexecution status")

    recorded_policy = _object(invocation.get("policy_hashes"), "recorded policy")
    current_policy = _current_policy_hashes()
    if recorded_policy != current_policy:
        return (
            _replay_payload(
                replay_status="REVIEW",
                replay_exit_code=2,
                archived_result=archived_result,
                record_integrity_status="PASS",
                reexecution_status="NOT_RUN",
                reexecution_reasons=["POLICY_DRIFT"],
                run_id=manifest["run_id"],
                recorded_policy_hashes=recorded_policy,
                current_policy_hashes=current_policy,
                live_source_status=live_status,
            ),
            2,
        )

    with tempfile.TemporaryDirectory(prefix="humanize-validation-replay-") as raw_temp:
        temp_root = Path(raw_temp)
        json_command = _replay_command(
            invocation,
            temp_root,
            artifacts,
            output_format="json",
        )
        completed = subprocess.run(
            json_command,
            check=False,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        replayed_result = _object(
            _strict_json(completed.stdout, "replayed validator output"),
            "replayed validator output",
        )
        expected_exit = int(invocation["expected"]["exit_code"])
        if completed.returncode != expected_exit or replayed_result.get("exit_code") != expected_exit:
            raise ReplayError("REPLAY_EXIT_MISMATCH", "replayed exit code differs")
        if completed.stderr != artifacts["stderr.txt"]:
            raise ReplayError("REPLAY_STDERR_MISMATCH", "replayed stderr differs")
        if _normalized_core(replayed_result) != _normalized_core(archived_result):
            raise ReplayError("REPLAY_CORE_MISMATCH", "replayed core result differs")

        if invocation["arguments"]["output_format"] == "text":
            text_command = _replay_command(
                invocation,
                temp_root,
                artifacts,
                output_format="text",
            )
            text_run = subprocess.run(
                text_command,
                check=False,
                capture_output=True,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            if text_run.returncode != expected_exit:
                raise ReplayError("REPLAY_EXIT_MISMATCH", "text replay exit differs")
            if text_run.stdout != artifacts["rendered-output.txt"]:
                raise ReplayError("REPLAY_STDOUT_MISMATCH", "text replay stdout differs")
            if text_run.stderr != artifacts["stderr.txt"]:
                raise ReplayError("REPLAY_STDERR_MISMATCH", "text replay stderr differs")

    reread_manifest, reread_artifacts = _load_record(root)
    if reread_manifest != manifest or {
        name: _sha256(raw) for name, raw in reread_artifacts.items()
    } != initial_hashes:
        raise ReplayError("EVIDENCE_DRIFT_DURING_REPLAY", "record changed during replay")

    if require_live_source_match and live_status["status"] != "MATCH":
        return (
            _replay_payload(
                replay_status="REVIEW",
                replay_exit_code=2,
                archived_result=archived_result,
                record_integrity_status="PASS",
                reexecution_status="PASS",
                replay_core_match=True,
                run_id=manifest["run_id"],
                live_source_status=live_status,
                review_reasons=["LIVE_SOURCE_NOT_CURRENT"],
            ),
            2,
        )
    return (
        _replay_payload(
            replay_status="PASS",
            replay_exit_code=0,
            archived_result=archived_result,
            record_integrity_status="PASS",
            reexecution_status="PASS",
            replay_core_match=True,
            run_id=manifest["run_id"],
            live_source_status=live_status,
        ),
        0,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a supported short-form Humanize evidence record and replay the validator "
            "without upgrading quality or academic claims."
        )
    )
    parser.add_argument("record", type=Path, help="Evidence directory created by --evidence-dir")
    parser.add_argument("--format", choices=("json", "text"), default="json", dest="output_format")
    parser.add_argument(
        "--require-live-source-match",
        action="store_true",
        help="Return REVIEW/2 when original source paths are missing or have drifted",
    )
    parser.add_argument(
        "--live-before",
        type=Path,
        help="Explicit current before artifact; paths are never written back into the record",
    )
    parser.add_argument(
        "--live-after",
        type=Path,
        help="Explicit current after artifact; must be paired with --live-before",
    )
    return parser


def _text_output(payload: dict[str, Any]) -> str:
    recorded_delivery = payload.get("recorded_delivery_gate_status")
    recorded_exit = payload.get("recorded_exit_code")
    lines = [
        f"replay_status: {payload['replay_status']}",
        f"scope: {payload['scope']}",
        "recorded_delivery_gate_status: "
        + (str(recorded_delivery) if recorded_delivery is not None else "NOT_AVAILABLE"),
        "recorded_exit_code: "
        + (str(recorded_exit) if recorded_exit is not None else "NOT_AVAILABLE"),
        f"replay_exit_code: {payload['replay_exit_code']}",
        f"status_compatibility: {payload['status_compatibility']}",
        f"exit_code_compatibility: {payload['exit_code_compatibility']}",
        f"record_integrity_status: {payload.get('record_integrity_status', 'FAIL')}",
        f"reexecution_status: {payload.get('reexecution_status', 'NOT_RUN')}",
        f"run_id: {payload.get('run_id', 'NONE')}",
        f"academic_correctness: {payload.get('academic_correctness', 'NOT_EVALUATED')}",
        "paired_quality_clearance_granted: "
        + str(payload.get("paired_quality_clearance_granted", False)).upper(),
        "humanize_quality_claim_allowed: "
        + str(payload.get("humanize_quality_claim_allowed", False)).upper(),
    ]
    for reason in payload.get("reexecution_reasons", payload.get("review_reasons", [])):
        lines.append(f"reason: {reason}")
    if payload.get("error_code"):
        lines.append(f"error_code: {payload['error_code']}")
        lines.append(f"error: {payload['error']}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, exit_code = replay_record(
            args.record,
            require_live_source_match=args.require_live_source_match,
            live_before=args.live_before,
            live_after=args.live_after,
        )
    except ReplayError as error:
        payload = _replay_payload(
            replay_status="FAIL",
            replay_exit_code=1,
            archived_result=None,
            record_integrity_status="FAIL",
            reexecution_status="NOT_RUN",
            error_code=error.code,
            error=str(error),
        )
        exit_code = 1
    except OSError as error:
        payload = _replay_payload(
            replay_status="FAIL",
            replay_exit_code=1,
            archived_result=None,
            record_integrity_status="FAIL",
            reexecution_status="NOT_RUN",
            error_code="REPLAY_IO_ERROR",
            error=str(error),
        )
        exit_code = 1
    if args.output_format == "json":
        sys.stdout.buffer.write(_pretty_json_bytes(payload))
    else:
        sys.stdout.write(_text_output(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
