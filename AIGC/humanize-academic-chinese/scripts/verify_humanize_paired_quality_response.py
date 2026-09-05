#!/usr/bin/env python3
"""Verify an externally signed paired-quality clearance response.

This verifier is deliberately narrower than the humanize validator.  It checks
the cryptographic and artifact bindings of an external review response; it does
not assess academic correctness, authorship, Voice, structure, or second-pass
quality.  A keyset read from the repository is never a trust root by itself.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import difflib
import hashlib
import json
import math
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


SCHEMA = "humanize-paired-quality-clearance-verification/v1"
REQUEST_SCHEMA = "humanize-paired-quality-review-request/v1"
CHALLENGE_SCHEMA = "humanize-paired-quality-clearance-challenge/v1"
RESPONSE_SCHEMA = "humanize-paired-quality-clearance-response/v1"
REVIEW_RECORD_SCHEMA = "humanize-paired-quality-review-record/v1"
KEYSET_SCHEMA = "humanize-paired-quality-clearance-keyset/v1"
ANCHOR_SCHEMA = "humanize-paired-quality-clearance-trust-anchor/v1"
REDEMPTION_SCHEMA = "humanize-paired-quality-clearance-redemption-ledger/v1"
EXPECTED_AUDIENCE = "humanize-academic-chinese/paired-quality"
EXPECTED_ISSUER = "configured-review-service"
EXPECTED_ALG = "EdDSA"
EXPECTED_TYP = "humanize-paired-quality-clearance+jws"
EXTERNAL_ANCHOR_ENV = "HUMANIZE_EXTERNAL_TRUST_ANCHOR"
MAX_CLOCK_SKEW = 300
MAX_TTL = 86_400
HEX64 = re.compile(r"^[0-9a-f]{64}$")
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
DIMENSIONS = (
    "actionable_pathology_remaining",
    "no_change_is_best_available_decision",
    "problem_span_binding",
    "independent_reading_benefit",
    "subject_and_modifier_alignment",
    "verb_object_collocation",
    "logical_relation_preservation",
    "information_density_and_rhythm",
    "author_voice_non_regression",
)
TEMPLATE_FIELD_DIMENSION = "template_field_role_and_authorization"
TEMPLATE_FIELD_AWARE_DIMENSIONS = (
    *DIMENSIONS[:7],
    TEMPLATE_FIELD_DIMENSION,
    *DIMENSIONS[7:],
)
TEMPLATE_FIELD_SOURCE_ROLE = "TEMPLATE_FIELD"
TEMPLATE_FIELD_PERMISSION = "PAYLOAD_ONLY"
TEMPLATE_FIELD_LABEL_ROLES = {
    "适用题目": "EDITORIAL_PAYLOAD/APPLICABILITY_CLASSIFICATION",
    "逻辑链条": "EDITORIAL_PAYLOAD/TEACHING_REASONING",
    "给定首句": "READER_FACING_ARTIFACT_ROLE/PROMPT_STEM",
    "用词建议": "EDITORIAL_PAYLOAD/LEXICAL_GUIDANCE",
}
TEMPLATE_FIELD_ROLE_CHANGE_TYPES = {
    "ASSERTION_FORCE_WEAKENED",
    "ASSERTION_FORCE_STRENGTHENED",
    "NEGATION_SCOPE_CHANGED",
    "CAUSAL_OR_CONDITION_RELATION_CHANGED",
    "APPLICABILITY_OBJECT_CHANGED",
    "APPLICABILITY_PREDICATE_CHANGED",
    "CLASSIFICATION_TO_READER_INSTRUCTION_DRIFT",
    "APPLICABILITY_RANGE_CHANGED",
}
TEMPLATE_FIELD_HEADER_CHANGE_TYPE = "FIELD_HEADER_OR_POSITION_CHANGED"
TEMPLATE_FIELD_PAYLOAD_CODES = {
    "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED",
    "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT",
    "TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED",
}
GENERIC_REVIEW_TEXT = {
    "人工审核",
    "人工审核通过",
    "已人工审核",
    "已确认",
    "已经确认",
    "符合要求",
    "没有问题",
    "无问题",
    "可以通过",
    "更好",
    "更自然",
    "表达自然",
    "质量良好",
}


class VerificationError(Exception):
    """A deterministic, user-facing verification failure."""

    def __init__(self, code: str, message: str, *, status: str = "FAIL") -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, label: str) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise VerificationError("NON_CANONICAL_JSON", f"{label} contains a UTF-8 BOM")
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise VerificationError("INVALID_JSON", f"invalid {label}: {exc}") from exc


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_safe_path(path: Path, label: str) -> Path:
    path = _absolute(path)
    current = path
    while True:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            attrs = int(getattr(info, "st_file_attributes", 0))
            if current.is_symlink() or attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise VerificationError(
                    "UNSAFE_PATH", f"{label} crosses a symlink or reparse point: {current}"
                )
        parent = current.parent
        if parent == current:
            break
        current = parent
    return path


def _read_bytes(path_value: str | Path, label: str) -> tuple[Path, bytes]:
    path = _assert_safe_path(Path(path_value), label)
    try:
        if not path.is_file():
            raise VerificationError("MISSING_ARTIFACT", f"{label} is not a regular file: {path}")
        return path, path.read_bytes()
    except VerificationError:
        raise
    except OSError as exc:
        raise VerificationError("ARTIFACT_READ_FAILED", f"cannot read {label}: {exc}") from exc


def _b64url(segment: str, label: str) -> bytes:
    if not isinstance(segment, str) or not segment or not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise VerificationError("NON_CANONICAL_BASE64URL", f"invalid {label} base64url")
    if len(segment) % 4 == 1:
        raise VerificationError("NON_CANONICAL_BASE64URL", f"invalid {label} base64url length")
    padded = segment + "=" * ((4 - len(segment) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise VerificationError("NON_CANONICAL_BASE64URL", f"invalid {label} base64url") from exc
    if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != segment:
        raise VerificationError("NON_CANONICAL_BASE64URL", f"non-canonical {label} base64url")
    return decoded


def _b64url_32(value: Any, label: str) -> bytes:
    decoded = _b64url(value, label)
    if len(decoded) != 32:
        raise VerificationError("INVALID_IDENTIFIER", f"{label} must encode exactly 32 bytes")
    return decoded


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError("INVALID_SCHEMA", f"{label} must be an object")
    return value


def _require_keys(obj: dict[str, Any], required: Iterable[str], allowed: Iterable[str], label: str) -> None:
    required_set = set(required)
    allowed_set = set(allowed)
    missing = sorted(required_set - obj.keys())
    unknown = sorted(set(obj) - allowed_set)
    if missing:
        raise VerificationError("INVALID_SCHEMA", f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise VerificationError("UNKNOWN_FIELD", f"{label} has unknown keys: {', '.join(unknown)}")


def _string(obj: dict[str, Any], key: str, label: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise VerificationError("INVALID_SCHEMA", f"{label}.{key} must be a non-empty string")
    return value


def _hex64(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise VerificationError("INVALID_HASH", f"{label} must be 64 lowercase hex characters")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VerificationError("INVALID_SCHEMA", f"{label} must be an integer")
    return value


def _positive_integer(value: Any, label: str) -> int:
    integer = _integer(value, label)
    if integer < 1:
        raise VerificationError("INVALID_SCHEMA", f"{label} must be positive")
    return integer


def _request_quality_dimensions(request: dict[str, Any]) -> tuple[str, ...]:
    """Select the exact v1 review contract without breaking legacy requests."""
    if "template_field_changes" in request:
        return TEMPLATE_FIELD_AWARE_DIMENSIONS
    return DIMENSIONS


def _validate_template_field_span(
    value: Any,
    label: str,
    *,
    expected_line: int,
) -> dict[str, Any]:
    span = _require_object(value, label)
    required = {"line", "payload_sha256", "line_sha256"}
    _require_keys(span, required, required, label)
    line = _positive_integer(span["line"], f"{label}.line")
    if line != expected_line:
        raise VerificationError(
            "INVALID_TEMPLATE_FIELD_CHANGE",
            f"{label}.line does not match its enclosing template-field record",
        )
    _hex64(span["payload_sha256"], f"{label}.payload_sha256")
    _hex64(span["line_sha256"], f"{label}.line_sha256")
    return span


def _validate_template_field_header_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise VerificationError("INVALID_SCHEMA", f"{label} must be an array")
    normalized: list[dict[str, Any]] = []
    prior_line = 0
    for ordinal, item in enumerate(value, 1):
        item_label = f"{label}[{ordinal}]"
        header = _require_object(item, item_label)
        required = {"line", "label", "separator", "line_sha256"}
        _require_keys(header, required, required, item_label)
        line = _positive_integer(header["line"], f"{item_label}.line")
        if line <= prior_line:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label} lines must be strictly increasing",
            )
        prior_line = line
        if header["label"] not in TEMPLATE_FIELD_LABEL_ROLES:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{item_label}.label is not a recognized template field",
            )
        if header["separator"] not in {"：", ":"}:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{item_label}.separator is invalid",
            )
        _hex64(header["line_sha256"], f"{item_label}.line_sha256")
        normalized.append(header)
    return normalized


def _validate_template_field_change_record(
    value: Any,
    label: str,
    *,
    request_change_ids: set[str],
) -> tuple[dict[str, Any], bool]:
    change = _require_object(value, label)
    code = change.get("code")
    if code == "TEMPLATE_FIELD_HEADER_CHANGED":
        required = {
            "code",
            "severity",
            "change_id",
            "source_role",
            "authorization_status",
            "change_types",
            "before_headers",
            "after_headers",
            "permission_boundary",
            "scope_provided",
        }
        # Header findings are mechanically blocking and older producers did not
        # emit this redundant flag.  If present it is nevertheless fail-closed.
        allowed = required | {"local_clearance_supported"}
        _require_keys(change, required, allowed, label)
        if change["severity"] != "error":
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label}.severity must be error for a header change",
            )
        if change["source_role"] != TEMPLATE_FIELD_SOURCE_ROLE:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label}.source_role is invalid",
            )
        if change["authorization_status"] != "HEADER_CHANGE_NOT_AUTHORIZABLE":
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                f"{label} falsely authorizes a protected template-field header",
            )
        if change["permission_boundary"] != TEMPLATE_FIELD_PERMISSION:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                f"{label}.permission_boundary must be {TEMPLATE_FIELD_PERMISSION}",
            )
        if not isinstance(change["scope_provided"], bool):
            raise VerificationError(
                "INVALID_SCHEMA", f"{label}.scope_provided must be a boolean"
            )
        if (
            "local_clearance_supported" in change
            and change["local_clearance_supported"] is not False
        ):
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                f"{label}.local_clearance_supported must be false",
            )
        if change["change_types"] != [TEMPLATE_FIELD_HEADER_CHANGE_TYPE]:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE_TYPES",
                f"{label}.change_types is invalid for a header change",
            )
        before_headers = _validate_template_field_header_list(
            change["before_headers"], f"{label}.before_headers"
        )
        after_headers = _validate_template_field_header_list(
            change["after_headers"], f"{label}.after_headers"
        )
        if not before_headers and not after_headers:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label} must bind at least one changed header",
            )
        if before_headers == after_headers:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label} does not describe a header change",
            )
        clearance_eligible = False
    elif code in TEMPLATE_FIELD_PAYLOAD_CODES:
        required = {
            "code",
            "severity",
            "change_id",
            "field_label",
            "source_role",
            "payload_role",
            "source_line",
            "after_line",
            "authorization_status",
            "permission",
            "authorization_reason",
            "change_types",
            "before_span",
            "after_span",
            "local_clearance_supported",
        }
        _require_keys(change, required, required, label)
        field_label = change["field_label"]
        if field_label not in TEMPLATE_FIELD_LABEL_ROLES:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label}.field_label is not recognized",
            )
        if change["source_role"] != TEMPLATE_FIELD_SOURCE_ROLE:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label}.source_role is invalid",
            )
        if change["payload_role"] != TEMPLATE_FIELD_LABEL_ROLES[field_label]:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE",
                f"{label}.payload_role does not match the field label",
            )
        source_line = _positive_integer(change["source_line"], f"{label}.source_line")
        after_line = _positive_integer(change["after_line"], f"{label}.after_line")
        _validate_template_field_span(
            change["before_span"],
            f"{label}.before_span",
            expected_line=source_line,
        )
        _validate_template_field_span(
            change["after_span"],
            f"{label}.after_span",
            expected_line=after_line,
        )
        if change["local_clearance_supported"] is not False:
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                f"{label}.local_clearance_supported must be false",
            )
        change_types = change["change_types"]
        if (
            not isinstance(change_types, list)
            or any(not isinstance(item, str) for item in change_types)
            or len(change_types) != len(set(change_types))
            or change_types != sorted(change_types)
            or any(item not in TEMPLATE_FIELD_ROLE_CHANGE_TYPES for item in change_types)
        ):
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_CHANGE_TYPES",
                f"{label}.change_types is not a canonical recognized list",
            )
        authorized = code != "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED"
        if authorized:
            reason = change["authorization_reason"]
            if (
                change["authorization_status"] != "AUTHORIZED_PAYLOAD_ONLY"
                or change["permission"] != TEMPLATE_FIELD_PERMISSION
                or not isinstance(reason, str)
                or not reason
                or reason != reason.strip()
                or len(reason.encode("utf-8")) > 1024
                or any(ord(char) < 32 or ord(char) == 127 for char in reason)
            ):
                raise VerificationError(
                    "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                    f"{label} has an invalid PAYLOAD_ONLY authorization",
                )
        elif (
            change["authorization_status"] != "NOT_AUTHORIZED"
            or change["permission"] is not None
            or change["authorization_reason"] is not None
        ):
            raise VerificationError(
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
                f"{label} carries authorization on an unauthorized edit",
            )
        if code == "TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED":
            if change["severity"] != "info" or change_types:
                raise VerificationError(
                    "INVALID_TEMPLATE_FIELD_CHANGE_TYPES",
                    f"{label} is not a role-preserving authorized payload edit",
                )
            clearance_eligible = True
        elif code == "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT":
            if change["severity"] != "warning" or not change_types:
                raise VerificationError(
                    "INVALID_TEMPLATE_FIELD_CHANGE_TYPES",
                    f"{label} must identify at least one role or force drift",
                )
            clearance_eligible = False
        else:
            if change["severity"] != "warning":
                raise VerificationError(
                    "INVALID_TEMPLATE_FIELD_CHANGE",
                    f"{label}.severity must be warning for an unauthorized edit",
                )
            clearance_eligible = False
    else:
        raise VerificationError(
            "INVALID_TEMPLATE_FIELD_CHANGE",
            f"{label}.code is not recognized",
        )

    change_id = change.get("change_id")
    if not isinstance(change_id, str) or change_id not in request_change_ids:
        raise VerificationError(
            "TEMPLATE_FIELD_CHANGE_TARGET_MISMATCH",
            f"{label}.change_id does not bind a request change",
        )
    return change, clearance_eligible


def _validate_template_field_changes(
    value: Any,
    *,
    request_change_ids: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(value, list):
        raise VerificationError(
            "INVALID_SCHEMA", "request.template_field_changes must be an array"
        )
    normalized: list[dict[str, Any]] = []
    all_clearance_eligible = True
    seen: set[bytes] = set()
    for ordinal, item in enumerate(value, 1):
        change, clearance_eligible = _validate_template_field_change_record(
            item,
            f"request.template_field_changes[{ordinal}]",
            request_change_ids=request_change_ids,
        )
        canonical = _canonical_json(change)
        if canonical in seen:
            raise VerificationError(
                "DUPLICATE_TEMPLATE_FIELD_CHANGE",
                "request contains a duplicate template-field change",
            )
        seen.add(canonical)
        normalized.append(change)
        all_clearance_eligible = all_clearance_eligible and clearance_eligible
    return normalized, all_clearance_eligible


def _current_policy_hashes() -> dict[str, str]:
    """Recompute the validator-owned policy surface instead of trusting a request."""
    try:
        import validate_humanize_output as output_validator
    except (ImportError, OSError) as exc:
        raise VerificationError(
            "POLICY_RUNTIME_UNAVAILABLE",
            f"cannot load the current validator policy: {exc}",
        ) from exc
    return dict(output_validator._policy_hashes())


def _changed_line_records(before_text: str, after_text: str) -> list[dict[str, Any]]:
    """Rebuild the exact hunk records emitted by validate_humanize_output."""
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    records: list[dict[str, Any]] = []
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for ordinal, (tag, before_start, before_end, after_start, after_end) in enumerate(
        (item for item in matcher.get_opcodes() if item[0] != "equal"), 1
    ):
        before_block = "".join(before_lines[before_start:before_end])
        after_block = "".join(after_lines[after_start:after_end])
        record: dict[str, Any] = {
            "ordinal": ordinal,
            "operation": tag.upper(),
            "before": {
                "start_line": before_start + 1 if before_end > before_start else None,
                "end_line": before_end if before_end > before_start else None,
                "line_count": before_end - before_start,
                "han_chars": len(re.findall(r"[\u3400-\u9fff]", before_block)),
                "sha256": _sha256(before_block.encode("utf-8")),
            },
            "after": {
                "start_line": after_start + 1 if after_end > after_start else None,
                "end_line": after_end if after_end > after_start else None,
                "line_count": after_end - after_start,
                "han_chars": len(re.findall(r"[\u3400-\u9fff]", after_block)),
                "sha256": _sha256(after_block.encode("utf-8")),
            },
        }
        record["change_id"] = "QCH-" + _sha256(_canonical_json(record))[:20]
        records.append(record)
    return records


def _parse_jws(raw: bytes) -> tuple[dict[str, Any], dict[str, Any], bytes, str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise VerificationError("INVALID_JWS", "JWS must be ASCII") from exc
    if text.endswith("\n") or text.endswith("\r"):
        raise VerificationError("INVALID_JWS", "JWS must not contain trailing data")
    parts = text.split(".")
    if len(parts) != 3:
        # A plain response JSON is an explicitly unsupported, unsigned
        # diagnostic input.  The contract treats this as pending review rather
        # than as cryptographic evidence.
        try:
            unsigned = _strict_json(raw, "unsigned response")
        except VerificationError:
            unsigned = None
        if isinstance(unsigned, dict) and unsigned.get("schema") == RESPONSE_SCHEMA:
            raise VerificationError("UNSIGNED_RESPONSE", "response is not wrapped in a JWS", status="REVIEW")
        raise VerificationError("INVALID_JWS", "JWS Compact must contain three segments")
    if len(parts) != 3 or any(not part for part in parts):
        raise VerificationError("INVALID_JWS", "JWS Compact must contain three non-empty segments")
    protected_raw = _b64url(parts[0], "protected header")
    payload_raw = _b64url(parts[1], "payload")
    signature = _b64url(parts[2], "signature")
    if len(signature) != 64:
        raise VerificationError("INVALID_SIGNATURE", "Ed25519 signature must be 64 bytes")
    protected = _require_object(_strict_json(protected_raw, "protected header"), "protected header")
    _require_keys(protected, ("alg", "kid", "typ"), ("alg", "kid", "typ"), "protected header")
    if protected.get("alg") != EXPECTED_ALG or protected.get("typ") != EXPECTED_TYP:
        raise VerificationError("UNSUPPORTED_ALGORITHM", "only EdDSA with the paired-quality typ is accepted")
    kid = _string(protected, "kid", "protected header")
    payload = _require_object(_strict_json(payload_raw, "response payload"), "response payload")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    return protected, payload, signature, kid, signing_input.decode("ascii")


def _validate_change_record(change: dict[str, Any], label: str) -> None:
    _require_keys(
        change,
        ("ordinal", "operation", "before", "after", "change_id"),
        ("ordinal", "operation", "before", "after", "change_id"),
        label,
    )
    ordinal = _integer(change["ordinal"], f"{label}.ordinal")
    if ordinal < 1:
        raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.ordinal must be positive")
    if change["operation"] not in {"REPLACE", "DELETE", "INSERT"}:
        raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.operation is invalid")
    for side in ("before", "after"):
        block = _require_object(change[side], f"{label}.{side}")
        _require_keys(
            block,
            ("start_line", "end_line", "line_count", "han_chars", "sha256"),
            ("start_line", "end_line", "line_count", "han_chars", "sha256"),
            f"{label}.{side}",
        )
        line_count = _integer(block["line_count"], f"{label}.{side}.line_count")
        han_chars = _integer(block["han_chars"], f"{label}.{side}.han_chars")
        if line_count < 0 or han_chars < 0:
            raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.{side} counts cannot be negative")
        start_line = block["start_line"]
        end_line = block["end_line"]
        if line_count == 0:
            if start_line is not None or end_line is not None:
                raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.{side} empty range must be null")
        else:
            if (
                isinstance(start_line, bool)
                or not isinstance(start_line, int)
                or isinstance(end_line, bool)
                or not isinstance(end_line, int)
                or start_line < 1
                or end_line < start_line
                or end_line - start_line + 1 != line_count
            ):
                raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.{side} line range is invalid")
        _hex64(block["sha256"], f"{label}.{side}.sha256")
    expected_id = "QCH-" + _sha256(
        _canonical_json({key: change[key] for key in ("ordinal", "operation", "before", "after")})
    )[:20]
    if change["change_id"] != expected_id:
        raise VerificationError("INVALID_CHANGE_HUNK", f"{label}.change_id is not content-bound")


def _validate_request(raw: bytes) -> tuple[dict[str, Any], str, set[str], str]:
    request = _require_object(_strict_json(raw, "request"), "request")
    allowed = {
        "schema", "status", "artifact", "validation_context", "policy_hashes",
        "changes", "template_field_changes", "review_contract", "limitations",
        "request_sha256",
    }
    _require_keys(
        request,
        (
            "schema",
            "status",
            "artifact",
            "validation_context",
            "policy_hashes",
            "changes",
            "review_contract",
            "limitations",
            "request_sha256",
        ),
        allowed,
        "request",
    )
    if request["schema"] != REQUEST_SCHEMA:
        raise VerificationError("INVALID_SCHEMA", "request schema is not v1")
    if request["status"] not in {"PENDING_EXTERNAL_REVIEW", "BLOCKED_BY_MECHANICAL_GATE"}:
        raise VerificationError("INVALID_SCHEMA", "request.status is invalid")
    request_hash = _hex64(request["request_sha256"], "request.request_sha256")
    body = dict(request)
    del body["request_sha256"]
    if _sha256(_canonical_json(body)) != request_hash:
        raise VerificationError("REQUEST_HASH_MISMATCH", "request_sha256 does not match canonical request")
    artifact = _require_object(request["artifact"], "request.artifact")
    _require_keys(artifact, ("before_sha256", "after_sha256"), ("before_sha256", "after_sha256"), "request.artifact")
    before_hash = _hex64(artifact["before_sha256"], "request.artifact.before_sha256")
    after_hash = _hex64(artifact["after_sha256"], "request.artifact.after_sha256")
    policy_hashes = _require_object(request["policy_hashes"], "request.policy_hashes")
    _require_keys(
        policy_hashes,
        REQUIRED_POLICY_HASHES,
        REQUIRED_POLICY_HASHES,
        "request.policy_hashes",
    )
    for key, value in policy_hashes.items():
        _hex64(value, f"request.policy_hashes.{key}")
    context = _require_object(request["validation_context"], "request.validation_context")
    context_keys = {
        "mode", "decision", "scene", "document_format", "document_scope",
        "mechanical_validation_status", "report_scope_binding",
    }
    _require_keys(
        context,
        ("mode", "decision", "scene", "document_format", "document_scope", "mechanical_validation_status"),
        context_keys,
        "request.validation_context",
    )
    if not all(isinstance(context.get(key), str) and context[key] for key in (
        "mode", "decision", "scene", "document_format", "document_scope", "mechanical_validation_status"
    )):
        raise VerificationError("INVALID_SCHEMA", "request.validation_context fields must be non-empty strings")
    if context.get("report_scope_binding") is not None:
        binding = _require_object(context["report_scope_binding"], "request.validation_context.report_scope_binding")
        _require_keys(
            binding,
            ("scope_semantic_sha256", "report_sha256", "source_sha256", "fragment_count", "editable_ranges"),
            ("scope_semantic_sha256", "report_sha256", "source_sha256", "fragment_count", "editable_ranges"),
            "request.validation_context.report_scope_binding",
        )
        for key in ("scope_semantic_sha256", "report_sha256", "source_sha256"):
            _hex64(binding[key], f"request.validation_context.report_scope_binding.{key}")
        if isinstance(binding["fragment_count"], bool) or not isinstance(binding["fragment_count"], int) or binding["fragment_count"] < 1:
            raise VerificationError("INVALID_SCHEMA", "report_scope_binding.fragment_count is invalid")
        if not isinstance(binding["editable_ranges"], list) or not binding["editable_ranges"]:
            raise VerificationError("INVALID_SCHEMA", "report_scope_binding.editable_ranges is invalid")
    if context.get("mode") != "REWRITE":
        raise VerificationError("MECHANICAL_GATE_BLOCKED", "paired-quality clearance only applies to REWRITE requests", status="REVIEW")
    changes = request["changes"]
    if not isinstance(changes, list):
        raise VerificationError("INVALID_SCHEMA", "request.changes must be an array")
    ids: list[str] = []
    for item in changes:
        change = _require_object(item, "request change")
        _validate_change_record(change, "request change")
        ids.append(change["change_id"])
    if len(set(ids)) != len(ids):
        raise VerificationError("DUPLICATE_CHANGE_ID", "request contains duplicate change_id values")
    template_field_clearance_eligible = True
    if "template_field_changes" in request:
        _, template_field_clearance_eligible = _validate_template_field_changes(
            request["template_field_changes"],
            request_change_ids=set(ids),
        )
    review_contract = _require_object(request["review_contract"], "request.review_contract")
    required_dimensions = list(_request_quality_dimensions(request))
    expected_contract = {
        "required_per_change_verdicts": ["ACCEPT", "REVISE", "REVERT"],
        "required_dimensions": required_dimensions,
        "empty_or_generic_benefit_is_clearance": False,
        "local_model_or_caller_assertion_is_clearance": False,
        "validator_pass_is_quality_clearance": False,
    }
    _require_keys(review_contract, expected_contract, expected_contract, "request.review_contract")
    if review_contract != expected_contract:
        raise VerificationError("INVALID_REVIEW_CONTRACT", "review contract is not the fixed v1 contract")
    limitations = _require_object(request["limitations"], "request.limitations")
    _require_keys(
        limitations,
        ("academic_correctness", "authorship", "quality_clearance_granted"),
        ("academic_correctness", "authorship", "quality_clearance_granted"),
        "request.limitations",
    )
    if limitations != {
        "academic_correctness": "NOT_EVALUATED",
        "authorship": "NOT_EVALUATED",
        "quality_clearance_granted": False,
    }:
        raise VerificationError("INVALID_SCHEMA", "request.limitations must remain non-claiming")
    decision = context.get("decision")
    if decision == "NO_CHANGE":
        if ids:
            raise VerificationError("INVALID_NO_CHANGE_REQUEST", "NO_CHANGE request must have no changes")
        targets = {"NO_CHANGE"}
    elif decision == "REWRITE":
        if not ids:
            raise VerificationError("INVALID_REWRITE_REQUEST", "REWRITE request must contain at least one change")
        targets = set(ids)
    else:
        raise VerificationError("INVALID_SCHEMA", "request decision must be REWRITE or NO_CHANGE")
    expected_status = "PENDING_EXTERNAL_REVIEW" if context["mechanical_validation_status"] == "PASS" else "BLOCKED_BY_MECHANICAL_GATE"
    if request["status"] != expected_status:
        raise VerificationError("INVALID_SCHEMA", "request.status does not match mechanical gate")
    if context.get("mechanical_validation_status") != "PASS":
        raise VerificationError(
            "MECHANICAL_GATE_BLOCKED",
            "mechanical validation is not PASS",
            status="REVIEW",
        )
    if not template_field_clearance_eligible:
        raise VerificationError(
            "MECHANICAL_GATE_BLOCKED",
            "template-field authorization or role drift blocks paired-quality clearance",
            status="REVIEW",
        )
    return request, request_hash, targets, before_hash + ":" + after_hash


def _change_contains_line(change: dict[str, Any], side: str, line: int) -> bool:
    block = change[side]
    return bool(
        block["line_count"]
        and block["start_line"] <= line <= block["end_line"]
    )


def _validate_template_field_changes_against_artifacts(
    request: dict[str, Any],
    before_raw: bytes,
    after_raw: bytes,
) -> None:
    if "template_field_changes" not in request:
        return
    try:
        before_text = before_raw.decode("utf-8")
        after_text = after_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(
            "ARTIFACT_ENCODING_UNSUPPORTED",
            "template-field artifacts must be strict UTF-8",
        ) from exc
    document_format = request["validation_context"]["document_format"]
    if document_format not in {"markdown", "tex"}:
        raise VerificationError(
            "INVALID_SCHEMA",
            "template-field requests require document_format markdown or tex",
        )
    try:
        import validate_humanize_output as output_validator

        before_fields = output_validator._template_field_records(
            before_text,
            artifact_role="before",
            artifact_raw=before_raw,
            document_format=document_format,
        )
        after_fields = output_validator._template_field_records(
            after_text,
            artifact_role="after",
            artifact_raw=after_raw,
            document_format=document_format,
        )
    except (ImportError, OSError, ValueError) as exc:
        raise VerificationError(
            "TEMPLATE_FIELD_POLICY_UNAVAILABLE",
            f"cannot replay the current template-field policy: {exc}",
        ) from exc

    before_by_line = {int(item["line"]): item for item in before_fields}
    after_by_line = {int(item["line"]): item for item in after_fields}
    changes_by_id = {item["change_id"]: item for item in request["changes"]}

    def projected_header(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "line": item["line"],
            "label": item["label"],
            "separator": item["separator"],
            "line_sha256": item["line_sha256"],
        }

    for ordinal, finding in enumerate(request["template_field_changes"], 1):
        label = f"request.template_field_changes[{ordinal}]"
        request_change = changes_by_id[finding["change_id"]]
        if finding["code"] == "TEMPLATE_FIELD_HEADER_CHANGED":
            expected_before = [
                projected_header(item)
                for item in before_fields
                if _change_contains_line(request_change, "before", int(item["line"]))
            ]
            expected_after = [
                projected_header(item)
                for item in after_fields
                if _change_contains_line(request_change, "after", int(item["line"]))
            ]
            if (
                finding["before_headers"] != expected_before
                or finding["after_headers"] != expected_after
            ):
                raise VerificationError(
                    "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
                    f"{label} header hashes or hunk binding do not match the artifacts",
                )
            continue

        source_line = int(finding["source_line"])
        after_line = int(finding["after_line"])
        if not _change_contains_line(request_change, "before", source_line) or not _change_contains_line(
            request_change, "after", after_line
        ):
            raise VerificationError(
                "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
                f"{label} line binding is outside its request change",
            )
        before_field = before_by_line.get(source_line)
        after_field = after_by_line.get(after_line)
        if before_field is None or after_field is None:
            raise VerificationError(
                "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
                f"{label} does not bind live template fields in both artifacts",
            )
        if (
            before_field["label"] != finding["field_label"]
            or after_field["label"] != finding["field_label"]
            or before_field["separator"] != after_field["separator"]
            or before_field["payload_role"] != finding["payload_role"]
            or after_field["payload_role"] != finding["payload_role"]
        ):
            raise VerificationError(
                "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
                f"{label} field identity or role does not match the artifacts",
            )
        expected_before_span = {
            "line": source_line,
            "payload_sha256": before_field["payload_sha256"],
            "line_sha256": before_field["line_sha256"],
        }
        expected_after_span = {
            "line": after_line,
            "payload_sha256": after_field["payload_sha256"],
            "line_sha256": after_field["line_sha256"],
        }
        if (
            finding["before_span"] != expected_before_span
            or finding["after_span"] != expected_after_span
        ):
            raise VerificationError(
                "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
                f"{label} payload or line hashes do not match the artifacts",
            )
        expected_change_types = output_validator._template_field_change_types(
            str(before_field["label"]),
            str(before_field["payload"]),
            str(after_field["payload"]),
        )
        if finding["change_types"] != expected_change_types:
            raise VerificationError(
                "TEMPLATE_FIELD_CHANGE_TYPES_MISMATCH",
                f"{label}.change_types does not match the current template-field policy",
            )


def _validate_request_hunks_against_artifacts(
    request: dict[str, Any], before_raw: bytes, after_raw: bytes
) -> None:
    try:
        before_text = before_raw.decode("utf-8")
        after_text = after_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(
            "ARTIFACT_ENCODING_UNSUPPORTED",
            "paired-quality artifacts must be strict UTF-8 for hunk verification",
        ) from exc
    expected = _changed_line_records(before_text, after_text)
    if request["changes"] != expected:
        raise VerificationError(
            "ARTIFACT_HUNK_MISMATCH",
            "request change hunks do not match the current before/after bytes",
        )
    _validate_template_field_changes_against_artifacts(
        request,
        before_raw,
        after_raw,
    )


def _validate_challenge(raw: bytes, request_hash: str, before_hash: str, after_hash: str, request: dict[str, Any], now: float, skew: int, max_ttl: int) -> tuple[dict[str, Any], str]:
    challenge = _require_object(_strict_json(raw, "challenge"), "challenge")
    allowed = {"schema", "challenge_id", "request_sha256", "subject_binding", "issued_at", "expires_at", "challenge_sha256"}
    _require_keys(challenge, allowed, allowed, "challenge")
    if challenge["schema"] != CHALLENGE_SCHEMA:
        raise VerificationError("INVALID_SCHEMA", "challenge schema is not v1")
    challenge_id = _b64url_32(challenge["challenge_id"], "challenge_id")
    if challenge["request_sha256"] != request_hash:
        raise VerificationError("CHALLENGE_REQUEST_MISMATCH", "challenge request_sha256 does not match request")
    subject = _require_object(challenge["subject_binding"], "challenge.subject_binding")
    required = {"kind", "before_sha256", "after_sha256", "scene", "document_scope"}
    if set(subject) - (required | {"snapshot_id", "unit_id", "chunk_binding_sha256", "voice_binding_sha256"}) or not required <= set(subject):
        raise VerificationError("INVALID_SCHEMA", "challenge.subject_binding has invalid keys")
    if subject["kind"] != "SINGLE_DOCUMENT":
        raise VerificationError("INVALID_SCHEMA", "only SINGLE_DOCUMENT challenges are supported")
    if subject["before_sha256"] != before_hash or subject["after_sha256"] != after_hash:
        raise VerificationError("CHALLENGE_ARTIFACT_MISMATCH", "challenge artifact hashes do not match request")
    context = request["validation_context"]
    if subject["scene"] != context.get("scene") or subject["document_scope"] != context.get("document_scope"):
        raise VerificationError("CHALLENGE_SCOPE_MISMATCH", "challenge scene or document_scope does not match request")
    for key in ("chunk_binding_sha256", "voice_binding_sha256"):
        if key in subject and (not isinstance(subject[key], str) or not HEX64.fullmatch(subject[key])):
            raise VerificationError("INVALID_HASH", f"challenge.subject_binding.{key} is invalid")
    issued = _integer(challenge["issued_at"], "challenge.issued_at")
    expires = _integer(challenge["expires_at"], "challenge.expires_at")
    if expires <= issued or expires - issued > max_ttl:
        raise VerificationError("INVALID_TIME_WINDOW", "challenge TTL is invalid")
    if issued > now + skew or expires < now - skew:
        raise VerificationError("CHALLENGE_EXPIRED", "challenge is outside the current time window")
    challenge_hash = _hex64(challenge["challenge_sha256"], "challenge.challenge_sha256")
    body = dict(challenge)
    del body["challenge_sha256"]
    if _sha256(_canonical_json(body)) != challenge_hash:
        raise VerificationError("CHALLENGE_HASH_MISMATCH", "challenge_sha256 does not match canonical challenge")
    return challenge, challenge_hash


def _validate_response_payload(payload: dict[str, Any], request: dict[str, Any], request_hash: str, challenge: dict[str, Any], challenge_hash: str, targets: set[str], now: float, skew: int, max_ttl: int, expected_issuer: str) -> tuple[dict[str, Any], bool]:
    required = {
        "schema", "iss", "aud", "response_id", "challenge_id", "challenge_sha256", "request_sha256",
        "review_contract_sha256", "review_items", "overall_verdict", "review_record_sha256",
        "issued_at", "not_before", "expires_at", "trust_epoch",
    }
    _require_keys(payload, required, required, "response payload")
    if payload["schema"] != RESPONSE_SCHEMA:
        raise VerificationError("INVALID_SCHEMA", "response schema is not v1")
    if payload["iss"] != expected_issuer or payload["aud"] != EXPECTED_AUDIENCE:
        raise VerificationError("AUDIENCE_ISSUER_MISMATCH", "response issuer or audience is not configured")
    _b64url_32(payload["response_id"], "response_id")
    if payload["challenge_id"] != challenge["challenge_id"] or payload["challenge_sha256"] != challenge_hash:
        raise VerificationError("RESPONSE_CHALLENGE_MISMATCH", "response is bound to a different challenge")
    if payload["request_sha256"] != request_hash:
        raise VerificationError("RESPONSE_REQUEST_MISMATCH", "response request_sha256 does not match request")
    contract = request["review_contract"]
    expected_contract_hash = _sha256(_canonical_json(contract))
    if payload["review_contract_sha256"] != expected_contract_hash:
        raise VerificationError("REVIEW_CONTRACT_MISMATCH", "response review contract hash does not match request")
    _hex64(payload["review_record_sha256"], "response.review_record_sha256")
    trust_epoch = _integer(payload["trust_epoch"], "response.trust_epoch")
    if trust_epoch < 0:
        raise VerificationError("INVALID_SCHEMA", "trust_epoch cannot be negative")
    issued = _integer(payload["issued_at"], "response.issued_at")
    not_before = _integer(payload["not_before"], "response.not_before")
    expires = _integer(payload["expires_at"], "response.expires_at")
    if not (issued <= not_before <= expires) or expires - issued > max_ttl:
        raise VerificationError("INVALID_TIME_WINDOW", "response time window is invalid")
    if not_before > now + skew or expires < now - skew:
        raise VerificationError("RESPONSE_EXPIRED", "response is outside the current time window")
    if issued < int(challenge["issued_at"]) - skew or expires > int(challenge["expires_at"]) + skew:
        raise VerificationError("RESPONSE_OUTSIDE_CHALLENGE", "response is outside challenge lifetime")
    items = payload["review_items"]
    if not isinstance(items, list):
        raise VerificationError("INVALID_SCHEMA", "response.review_items must be an array")
    dimensions = _request_quality_dimensions(request)
    item_targets: list[str] = []
    for item in items:
        review = _require_object(item, "response review item")
        required_item_keys = {"target", "verdict", *dimensions}
        unknown_item_keys = sorted(set(review) - required_item_keys)
        if unknown_item_keys:
            raise VerificationError(
                "UNKNOWN_FIELD",
                "response review item has unknown keys: "
                + ", ".join(unknown_item_keys),
            )
        missing_item_keys = sorted(required_item_keys - set(review))
        if missing_item_keys:
            raise VerificationError(
                "QUALITY_REVIEW_INCOMPLETE",
                "response review item is missing required quality fields: "
                + ", ".join(missing_item_keys),
                status="REVIEW",
            )
        if not isinstance(review["target"], str) or not review["target"]:
            raise VerificationError("INVALID_SCHEMA", "review item target must be a string")
        item_targets.append(review["target"])
        if review["verdict"] not in {"ACCEPT", "REVISE", "REVERT"}:
            raise VerificationError("INVALID_REVIEW_VERDICT", "review item verdict is invalid")
        for dimension in dimensions:
            if review[dimension] not in {"PASS", "FAIL", "REVIEW"}:
                raise VerificationError("INVALID_REVIEW_DIMENSION", f"invalid quality dimension: {dimension}")
    if len(item_targets) != len(set(item_targets)) or set(item_targets) != targets:
        raise VerificationError("CHANGE_TARGET_MISMATCH", "review targets must exactly cover request changes")
    quality_pass = (
        payload["overall_verdict"] == "CLEAR"
        and all(
            item["verdict"] == "ACCEPT"
            and all(item[dimension] == "PASS" for dimension in dimensions)
            for item in items
        )
    )
    if payload["overall_verdict"] not in {"CLEAR", "REVIEW", "REJECT"}:
        raise VerificationError("INVALID_OVERALL_VERDICT", "overall_verdict is invalid")
    return payload, quality_pass


def _concrete_review_text(value: Any, label: str, *, minimum_han: int) -> str:
    if not isinstance(value, str):
        raise VerificationError("INVALID_REVIEW_RECORD", f"{label} must be a string")
    normalized = re.sub(r"\s+", "", value)
    han_count = len(re.findall(r"[\u3400-\u9fff]", normalized))
    if not normalized or han_count < minimum_han:
        raise VerificationError(
            "GENERIC_REVIEW_RATIONALE",
            f"{label} is too short to identify a concrete reading decision",
            status="REVIEW",
        )
    if normalized in GENERIC_REVIEW_TEXT:
        raise VerificationError(
            "GENERIC_REVIEW_RATIONALE",
            f"{label} is a generic approval phrase",
            status="REVIEW",
        )
    return value


def _validate_review_record(
    raw: bytes,
    *,
    payload: dict[str, Any],
    request_hash: str,
    challenge_hash: str,
    targets: set[str],
) -> None:
    expected_hash = _hex64(
        payload["review_record_sha256"], "response.review_record_sha256"
    )
    if _sha256(raw) != expected_hash:
        raise VerificationError(
            "REVIEW_RECORD_HASH_MISMATCH",
            "review record bytes do not match response.review_record_sha256",
        )
    record = _require_object(_strict_json(raw, "review record"), "review record")
    required = {
        "schema",
        "request_sha256",
        "challenge_sha256",
        "response_id",
        "items",
    }
    _require_keys(record, required, required, "review record")
    if record["schema"] != REVIEW_RECORD_SCHEMA:
        raise VerificationError("INVALID_REVIEW_RECORD", "review record schema is not v1")
    if record["request_sha256"] != request_hash:
        raise VerificationError(
            "REVIEW_RECORD_REQUEST_MISMATCH", "review record binds another request"
        )
    if record["challenge_sha256"] != challenge_hash:
        raise VerificationError(
            "REVIEW_RECORD_CHALLENGE_MISMATCH", "review record binds another challenge"
        )
    if record["response_id"] != payload["response_id"]:
        raise VerificationError(
            "REVIEW_RECORD_RESPONSE_MISMATCH", "review record binds another response"
        )
    items = record["items"]
    if not isinstance(items, list):
        raise VerificationError("INVALID_REVIEW_RECORD", "review record items must be an array")
    actual_targets: list[str] = []
    item_keys = {"target", "problem_span", "reading_effect", "decision_rationale"}
    for index, raw_item in enumerate(items):
        item = _require_object(raw_item, f"review record item {index}")
        _require_keys(item, item_keys, item_keys, f"review record item {index}")
        target = _string(item, "target", f"review record item {index}")
        actual_targets.append(target)
        _concrete_review_text(
            item["problem_span"],
            f"review record item {index}.problem_span",
            minimum_han=3,
        )
        _concrete_review_text(
            item["reading_effect"],
            f"review record item {index}.reading_effect",
            minimum_han=6,
        )
        _concrete_review_text(
            item["decision_rationale"],
            f"review record item {index}.decision_rationale",
            minimum_han=6,
        )
    if len(actual_targets) != len(set(actual_targets)) or set(actual_targets) != targets:
        raise VerificationError(
            "REVIEW_RECORD_TARGET_MISMATCH",
            "review record targets must exactly cover response targets",
        )


def _load_keyset(raw: bytes, now: float, expected_issuer: str) -> dict[str, Any]:
    keyset = _require_object(_strict_json(raw, "keyset"), "keyset")
    allowed = {"schema", "sequence", "issued_at", "next_update", "issuer", "audience", "keys", "revocations"}
    _require_keys(keyset, allowed, allowed, "keyset")
    if keyset["schema"] != KEYSET_SCHEMA:
        raise VerificationError("INVALID_KEYSET", "keyset schema is not v1")
    sequence = _integer(keyset["sequence"], "keyset.sequence")
    if sequence < 0 or keyset["issuer"] != expected_issuer or keyset["audience"] != EXPECTED_AUDIENCE:
        raise VerificationError("INVALID_KEYSET", "keyset identity or sequence is invalid")
    issued = _integer(keyset["issued_at"], "keyset.issued_at")
    next_update = _integer(keyset["next_update"], "keyset.next_update")
    if next_update <= issued:
        raise VerificationError("INVALID_KEYSET", "keyset next_update must follow issued_at")
    if next_update < now - MAX_CLOCK_SKEW:
        raise VerificationError("KEYSET_EXPIRED", "keyset is expired")
    keys = keyset["keys"]
    if not isinstance(keys, list) or not keys:
        raise VerificationError("INVALID_KEYSET", "keyset.keys must be a non-empty array")
    seen: set[str] = set()
    for item in keys:
        key = _require_object(item, "keyset key")
        _require_keys(key, {"kid", "alg", "public_key", "not_before", "not_after", "status", "usages"}, {"kid", "alg", "public_key", "not_before", "not_after", "status", "usages"}, "keyset key")
        kid = _string(key, "kid", "keyset key")
        if kid in seen:
            raise VerificationError("INVALID_KEYSET", f"duplicate key id: {kid}")
        seen.add(kid)
        if key["alg"] != EXPECTED_ALG:
            raise VerificationError("INVALID_KEYSET", f"unsupported key algorithm for {kid}")
        public = _b64url(key["public_key"], f"keyset public key {kid}")
        if len(public) != 32:
            raise VerificationError("INVALID_KEYSET", f"public key {kid} must be 32 bytes")
        _integer(key["not_before"], f"keyset key {kid}.not_before")
        _integer(key["not_after"], f"keyset key {kid}.not_after")
        if key["not_after"] <= key["not_before"] or key["status"] not in {"ACTIVE", "RETIRED", "REVOKED"}:
            raise VerificationError("INVALID_KEYSET", f"invalid lifecycle for key {kid}")
        if not isinstance(key["usages"], list) or any(not isinstance(x, str) for x in key["usages"]):
            raise VerificationError("INVALID_KEYSET", f"invalid usages for key {kid}")
    revocations = keyset["revocations"]
    if not isinstance(revocations, list):
        raise VerificationError("INVALID_KEYSET", "keyset.revocations must be an array")
    for index, raw_revocation in enumerate(revocations):
        try:
            item = _require_object(raw_revocation, f"keyset revocation {index}")
            mode = item.get("mode")
            if mode == "ALL_SIGNATURES":
                _require_keys(
                    item,
                    {"kid", "mode"},
                    {"kid", "mode"},
                    f"keyset revocation {index}",
                )
            elif mode == "ISSUED_AT_OR_AFTER":
                _require_keys(
                    item,
                    {"kid", "mode", "issued_at"},
                    {"kid", "mode", "issued_at"},
                    f"keyset revocation {index}",
                )
                issued_at = _integer(
                    item["issued_at"], f"keyset revocation {index}.issued_at"
                )
                if issued_at < 0:
                    raise VerificationError(
                        "INVALID_KEYSET",
                        f"keyset revocation {index}.issued_at cannot be negative",
                    )
            else:
                raise VerificationError(
                    "INVALID_KEYSET",
                    f"keyset revocation {index}.mode is invalid",
                )
            _string(item, "kid", f"keyset revocation {index}")
        except VerificationError as error:
            if error.code == "INVALID_KEYSET":
                raise
            raise VerificationError("INVALID_KEYSET", str(error)) from error
    return keyset


def _check_trust_anchor(raw: bytes, keyset_raw: bytes, keyset: dict[str, Any], expected_issuer: str) -> None:
    anchor = _require_object(_strict_json(raw, "trust anchor"), "trust anchor")
    allowed = {"schema", "keyset_sha256", "sequence", "issuer", "audience"}
    _require_keys(anchor, allowed, allowed, "trust anchor")
    if anchor["schema"] != ANCHOR_SCHEMA:
        raise VerificationError("INVALID_TRUST_ANCHOR", "trust anchor schema is not v1")
    if anchor["keyset_sha256"] != _sha256(keyset_raw):
        raise VerificationError("TRUST_ANCHOR_MISMATCH", "trust anchor does not bind the supplied keyset")
    if anchor["sequence"] != keyset["sequence"] or anchor["issuer"] != expected_issuer or anchor["audience"] != EXPECTED_AUDIENCE:
        raise VerificationError("TRUST_ANCHOR_MISMATCH", "trust anchor identity or sequence does not match keyset")


def _verify_signature(signature: bytes, signing_input: str, kid: str, keyset: dict[str, Any], response_issued: int) -> None:
    match = next((item for item in keyset["keys"] if item.get("kid") == kid), None)
    if match is None:
        raise VerificationError("UNKNOWN_KEY", f"unknown key id: {kid}")
    if match["status"] != "ACTIVE" or "paired-quality-clearance" not in match["usages"]:
        raise VerificationError("KEY_NOT_ACTIVE", f"key is not active for paired-quality clearance: {kid}")
    if not (match["not_before"] <= response_issued <= match["not_after"]):
        raise VerificationError("KEY_OUTSIDE_VALIDITY", f"key is outside validity at response issued_at: {kid}")
    for revocation in keyset["revocations"]:
        item = _require_object(revocation, "keyset revocation")
        if item.get("kid") != kid:
            continue
        mode = item.get("mode")
        if mode == "ALL_SIGNATURES" or (mode == "ISSUED_AT_OR_AFTER" and isinstance(item.get("issued_at"), int) and response_issued >= item["issued_at"]):
            raise VerificationError("KEY_REVOKED", f"key has been revoked: {kid}")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception as exc:
        raise VerificationError("CRYPTOGRAPHY_UNAVAILABLE", "cryptography Ed25519 dependency is unavailable", status="REVIEW") from exc
    public = _b64url(match["public_key"], f"keyset public key {kid}")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, signing_input.encode("ascii"))
    except Exception as exc:
        raise VerificationError("SIGNATURE_INVALID", "Ed25519 signature verification failed") from exc


def _trust_anchor_is_protected(path: Path) -> bool:
    """Return true only when the local platform can prove a protected anchor.

    Windows ACL verification is intentionally not guessed from mode bits. A
    production launcher should replace this boundary with an ACL-aware check;
    until then the normal Windows CLI cannot grant external clearance.
    """
    try:
        info = path.stat()
    except OSError:
        return False
    if os.name == "nt":
        return False
    # A root process can create or replace a root-owned file itself, so it is
    # not an independent trust boundary either.
    if getattr(os, "getuid", lambda: -1)() == 0:
        return False
    owner_is_privileged = getattr(info, "st_uid", None) == 0
    return bool(owner_is_privileged and not (stat.S_IMODE(info.st_mode) & 0o022))


def _require_unchanged(path: Path, label: str, expected: bytes, code: str) -> None:
    _, current = _read_bytes(path, label)
    if current != expected:
        raise VerificationError(code, f"{label} changed after verification")


def _redeem_response(
    ledger_path: Path,
    *,
    response_id: str,
    request_hash: str,
    challenge_hash: str,
    before_hash: str,
    after_hash: str,
    redeemed_at: float,
) -> None:
    """Atomically consume a response id; a second redemption never grants again."""
    ledger_path = _assert_safe_path(ledger_path, "redemption ledger")
    parent = ledger_path.parent
    if not parent.is_dir():
        raise VerificationError("REDEMPTION_LEDGER_UNAVAILABLE", "redemption ledger parent is missing", status="REVIEW")
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    lock_path = _assert_safe_path(lock_path, "redemption ledger lock")
    try:
        fd = os.open(os.fspath(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise VerificationError("REDEMPTION_LEDGER_BUSY", "redemption ledger is locked", status="REVIEW") from exc
    try:
        os.close(fd)
        if ledger_path.exists():
            _, raw = _read_bytes(ledger_path, "redemption ledger")
            ledger = _strict_json(raw, "redemption ledger")
        else:
            ledger = {"schema": REDEMPTION_SCHEMA, "entries": {}}
        ledger = _require_object(ledger, "redemption ledger")
        _require_keys(ledger, ("schema", "entries"), ("schema", "entries"), "redemption ledger")
        if ledger["schema"] != REDEMPTION_SCHEMA:
            raise VerificationError("INVALID_REDEMPTION_LEDGER", "redemption ledger schema is invalid")
        entries = _require_object(ledger["entries"], "redemption ledger.entries")
        existing = entries.get(response_id)
        if existing is not None:
            if not isinstance(existing, dict):
                raise VerificationError("INVALID_REDEMPTION_LEDGER", "redemption entry is invalid")
            if (
                existing.get("request_sha256") == request_hash
                and existing.get("challenge_sha256") == challenge_hash
                and existing.get("before_sha256") == before_hash
                and existing.get("after_sha256") == after_hash
            ):
                raise VerificationError("REDEMPTION_ALREADY_USED", "response has already been redeemed", status="REVIEW")
            raise VerificationError("REDEMPTION_KEY_COLLISION", "response id is bound to another artifact", status="FAIL")
        entries[response_id] = {
            "request_sha256": request_hash,
            "challenge_sha256": challenge_hash,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "redeemed_at": int(redeemed_at),
        }
        payload = json.dumps(ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        temp_path = parent / (ledger_path.name + f".tmp-{os.getpid()}-{time.time_ns()}")
        temp_path = _assert_safe_path(temp_path, "redemption ledger staging")
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, ledger_path)
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def verify(
    *,
    request_path: Path,
    challenge_path: Path | None,
    response_path: Path | None,
    before_path: Path | None,
    after_path: Path | None,
    keyset_path: Path | None,
    trust_anchor_path: Path | None,
    review_record_path: Path | None = None,
    redemption_ledger_path: Path | None = None,
    now: float | None = None,
    clock_skew: int = MAX_CLOCK_SKEW,
    max_ttl: int = MAX_TTL,
    expected_issuer: str = EXPECTED_ISSUER,
) -> dict[str, Any]:
    now = time.time() if now is None else float(now)
    if not math.isfinite(now):
        raise ValueError("now must be finite")
    if (
        isinstance(clock_skew, bool)
        or not isinstance(clock_skew, (int, float))
        or not math.isfinite(float(clock_skew))
    ):
        raise ValueError("clock_skew must be finite")
    if (
        isinstance(max_ttl, bool)
        or not isinstance(max_ttl, (int, float))
        or not math.isfinite(float(max_ttl))
    ):
        raise ValueError("max_ttl must be finite")
    if clock_skew < 0 or clock_skew > MAX_CLOCK_SKEW:
        raise ValueError(f"clock_skew must be between 0 and maximum {MAX_CLOCK_SKEW}")
    if max_ttl <= 0 or max_ttl > MAX_TTL:
        raise ValueError(f"max_ttl must be positive and no greater than maximum {MAX_TTL}")
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "REVIEW",
        "verification_status": "NOT_EVALUATED",
        "paired_quality_gate_status": "NOT_EVALUATED",
        "delivery_gate_status": "NOT_EVALUATED",
        "exit_code": 2,
        "paired_quality_clearance_granted": False,
        "quality_clearance_granted": False,
        "cryptographic_signature_status": "NOT_CHECKED",
        "review_record_status": "NOT_CHECKED",
        "redemption_status": "NOT_CHECKED",
        "trust_root_status": "UNTRUSTED_LOCAL_KEYSET",
        "academic_correctness": "NOT_EVALUATED",
        "authorship": "NOT_EVALUATED",
        "independent_gates": {"structure": "NOT_EVALUATED", "voice": "NOT_EVALUATED", "second_pass": "NOT_EVALUATED"},
        "reasons": [],
    }

    def fail(error: VerificationError) -> dict[str, Any]:
        result["status"] = error.status
        result["verification_status"] = error.status
        result["paired_quality_gate_status"] = "NOT_EVALUATED"
        result["delivery_gate_status"] = "NOT_EVALUATED"
        result["exit_code"] = 1 if error.status == "FAIL" else 2
        result["reasons"].append({"code": error.code, "message": str(error)})
        return result

    try:
        _, request_raw = _read_bytes(request_path, "request")
        request, request_hash, targets, artifact_pair = _validate_request(request_raw)
        before_hash, after_hash = artifact_pair.split(":")
        result["request_sha256"] = request_hash
        result["expected_change_targets"] = sorted(targets)
        current_policy_hashes = _current_policy_hashes()
        result["current_policy_hashes"] = current_policy_hashes
        if request["policy_hashes"] != current_policy_hashes:
            return fail(
                VerificationError(
                    "POLICY_HASH_DRIFT",
                    "request policy hashes do not match the current validator policy",
                    status="FAIL",
                )
            )
        if challenge_path is None or response_path is None:
            return fail(VerificationError("MISSING_CHALLENGE_OR_RESPONSE", "challenge and signed response are required", status="REVIEW"))
        _, challenge_raw = _read_bytes(challenge_path, "challenge")
        challenge, challenge_hash = _validate_challenge(challenge_raw, request_hash, before_hash, after_hash, request, now, clock_skew, max_ttl)
        result["challenge_sha256"] = challenge_hash
        _, response_raw = _read_bytes(response_path, "response")
        protected, payload, signature, kid, signing_input = _parse_jws(response_raw)
        result["response_id"] = payload.get("response_id")
        result["key_id"] = kid
        _validate_response_payload(payload, request, request_hash, challenge, challenge_hash, targets, now, clock_skew, max_ttl, expected_issuer)
        if keyset_path is None:
            return fail(VerificationError("MISSING_KEYSET", "an independent keyset is required for signature verification", status="REVIEW"))
        _, keyset_raw = _read_bytes(keyset_path, "keyset")
        keyset = _load_keyset(keyset_raw, now, expected_issuer)
        if payload["trust_epoch"] != keyset["sequence"]:
            return fail(VerificationError("TRUST_EPOCH_MISMATCH", "response trust_epoch does not match the anchored keyset sequence", status="FAIL"))
        # A path supplied by the ordinary caller is diagnostic material only.
        # The independent launcher must pin the anchor through an environment
        # boundary that this CLI does not set or derive from repository files.
        external_anchor = os.environ.get(EXTERNAL_ANCHOR_ENV, "").strip()
        anchor_selected = bool(
            trust_anchor_path is not None
            and external_anchor
            and _absolute(Path(external_anchor)) == _absolute(trust_anchor_path)
        )
        anchor_authorized = bool(
            anchor_selected
            and trust_anchor_path is not None
            and _trust_anchor_is_protected(_absolute(trust_anchor_path))
        )
        anchor_raw_verified: bytes | None = None
        if trust_anchor_path is None:
            # We intentionally verify the signature below, but the local keyset
            # remains an untrusted diagnostic input and can never grant clearance.
            trust_status = "UNTRUSTED_LOCAL_KEYSET"
        else:
            if anchor_authorized:
                _, anchor_raw = _read_bytes(trust_anchor_path, "trust anchor")
                _check_trust_anchor(anchor_raw, keyset_raw, keyset, expected_issuer)
                anchor_raw_verified = anchor_raw
                trust_status = "EXTERNALLY_ANCHORED"
            else:
                # Do not parse caller-supplied anchor content as a trust root.
                # This is intentionally indistinguishable from a missing root
                # for the grant decision, while still allowing signature
                # diagnostics below.
                trust_status = "UNTRUSTED_LOCAL_KEYSET"
        _verify_signature(signature, signing_input, kid, keyset, int(payload["issued_at"]))
        result["cryptographic_signature_status"] = "PASS"
        result["trust_root_status"] = trust_status
        if before_path is None or after_path is None:
            return fail(VerificationError("MISSING_ARTIFACT_INPUT", "current before and after artifacts are required", status="REVIEW"))
        _, before_raw = _read_bytes(before_path, "before artifact")
        _, after_raw = _read_bytes(after_path, "after artifact")
        if _sha256(before_raw) != before_hash or _sha256(after_raw) != after_hash:
            return fail(VerificationError("ARTIFACT_BINDING_MISMATCH", "current artifacts do not match the request", status="FAIL"))
        _validate_request_hunks_against_artifacts(request, before_raw, after_raw)
        # Re-read immediately before granting to detect a post-signature edit.
        _, before_again = _read_bytes(before_path, "before artifact")
        _, after_again = _read_bytes(after_path, "after artifact")
        if before_again != before_raw or after_again != after_raw:
            return fail(VerificationError("ARTIFACT_DRIFT_AFTER_VERIFY", "artifact changed after signature verification", status="FAIL"))
        if anchor_selected and not anchor_authorized:
            return fail(
                VerificationError(
                    "UNPROTECTED_TRUST_ANCHOR",
                    "the selected trust anchor is not proven to be protected by the host",
                    status="REVIEW",
                )
            )
        if trust_status != "EXTERNALLY_ANCHORED":
            return fail(VerificationError("UNTRUSTED_LOCAL_KEYSET", "signature is valid, but the keyset has no external trust anchor", status="REVIEW"))
        # The payload quality predicate is recomputed after all bindings pass.
        _, quality_pass = _validate_response_payload(payload, request, request_hash, challenge, challenge_hash, targets, now, clock_skew, max_ttl, expected_issuer)
        if not quality_pass:
            return fail(VerificationError("QUALITY_REVIEW_NOT_CLEAR", "response does not CLEAR every change and quality dimension", status="REVIEW"))
        if review_record_path is None:
            return fail(
                VerificationError(
                    "MISSING_REVIEW_RECORD",
                    "the signed review_record_sha256 requires the current review record artifact",
                    status="REVIEW",
                )
            )
        _, review_record_raw = _read_bytes(review_record_path, "review record")
        _validate_review_record(
            review_record_raw,
            payload=payload,
            request_hash=request_hash,
            challenge_hash=challenge_hash,
            targets=targets,
        )
        result["review_record_status"] = "PASS"
        _require_unchanged(
            request_path, "request", request_raw, "EVIDENCE_DRIFT_AFTER_VERIFY"
        )
        _require_unchanged(
            challenge_path,
            "challenge",
            challenge_raw,
            "EVIDENCE_DRIFT_AFTER_VERIFY",
        )
        _require_unchanged(
            response_path, "response", response_raw, "EVIDENCE_DRIFT_AFTER_VERIFY"
        )
        _require_unchanged(
            keyset_path, "keyset", keyset_raw, "EVIDENCE_DRIFT_AFTER_VERIFY"
        )
        _require_unchanged(
            review_record_path,
            "review record",
            review_record_raw,
            "EVIDENCE_DRIFT_AFTER_VERIFY",
        )
        if trust_anchor_path is not None and anchor_raw_verified is not None:
            _require_unchanged(
                trust_anchor_path,
                "trust anchor",
                anchor_raw_verified,
                "EVIDENCE_DRIFT_AFTER_VERIFY",
            )
        _require_unchanged(
            before_path,
            "before artifact",
            before_raw,
            "ARTIFACT_DRIFT_AFTER_VERIFY",
        )
        _require_unchanged(
            after_path,
            "after artifact",
            after_raw,
            "ARTIFACT_DRIFT_AFTER_VERIFY",
        )
        if _current_policy_hashes() != current_policy_hashes:
            return fail(
                VerificationError(
                    "POLICY_DRIFT_AFTER_VERIFY",
                    "validator policy changed during verification",
                    status="FAIL",
                )
            )
        result["redemption_status"] = (
            "CALLER_PROVIDED_DIAGNOSTIC_ONLY"
            if redemption_ledger_path is not None
            else "NOT_PROVIDED"
        )
        result.update({
            "status": "REVIEW",
            "verification_status": "PASS",
            "paired_quality_gate_status": "PASS",
            "delivery_gate_status": "REVIEW",
            "exit_code": 2,
            "paired_quality_clearance_granted": False,
            "quality_clearance_granted": False,
            "reasons": [{
                "code": "STANDALONE_VERIFICATION_PASS",
                "message": (
                    "signature, request, artifacts, and paired-quality dimensions verify, "
                    "but this standalone process has no delivery or redemption authority"
                ),
            }],
        })
        return result
    except VerificationError as exc:
        return fail(exc)
    except OSError as exc:
        return fail(VerificationError("IO_ERROR", str(exc), status="FAIL"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--challenge", type=Path)
    parser.add_argument("--response", "--response-jws", dest="response", type=Path)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--keyset", type=Path)
    parser.add_argument("--trust-anchor", type=Path)
    parser.add_argument("--review-record", type=Path)
    parser.add_argument("--redemption-ledger", type=Path)
    parser.add_argument("--issuer", default=EXPECTED_ISSUER)
    parser.add_argument("--now", type=float)
    parser.add_argument("--clock-skew", type=int, default=MAX_CLOCK_SKEW)
    parser.add_argument("--max-ttl", type=int, default=MAX_TTL)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def _text(result: dict[str, Any]) -> str:
    lines = [
        f"status: {result.get('status')}",
        f"verification_status: {result.get('verification_status')}",
        f"paired_quality_gate_status: {result.get('paired_quality_gate_status')}",
        f"delivery_gate_status: {result.get('delivery_gate_status')}",
        f"exit_code: {result.get('exit_code')}",
        f"cryptographic_signature_status: {result.get('cryptographic_signature_status')}",
        f"trust_root_status: {result.get('trust_root_status')}",
        f"redemption_status: {result.get('redemption_status')}",
        f"paired_quality_clearance_granted: {str(result.get('paired_quality_clearance_granted', False)).upper()}",
    ]
    for reason in result.get("reasons", []):
        lines.append(f"reason: {reason.get('code')} - {reason.get('message')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = verify(
        request_path=args.request,
        challenge_path=args.challenge,
        response_path=args.response,
        before_path=args.before,
        after_path=args.after,
        keyset_path=args.keyset,
        trust_anchor_path=args.trust_anchor,
        review_record_path=args.review_record,
        redemption_ledger_path=args.redemption_ledger,
        now=args.now,
        clock_skew=args.clock_skew,
        max_ttl=args.max_ttl,
        expected_issuer=args.issuer,
    )
    if args.format == "text":
        sys.stdout.write(_text(result))
    else:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
