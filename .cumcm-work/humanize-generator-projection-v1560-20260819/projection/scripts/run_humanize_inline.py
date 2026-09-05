#!/usr/bin/env python3
"""Materialize, validate, and emit an inline humanize candidate.

This wrapper does not generate prose. It gives ordinary INLINE_TEXT REWRITE and
DRAFT calls one short, auditable path around the unified validator. The emitted
body is always read from the validated snapshot; a later artifact mutation is
fail-closed.
"""

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
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_VALIDATOR = SCRIPT_DIR / "validate_humanize_output.py"
RUN_SCHEMA = "humanize-inline-run/v3"
LEGACY_RUN_SCHEMA = "humanize-inline-run/v2"
INVOCATION_SCHEMA = "humanize-inline-invocation/v2"
LEGACY_INVOCATION_SCHEMA = "humanize-inline-invocation/v1"
VERIFY_SCHEMA = "humanize-inline-verification/v3"
VISIBLE_ATTESTATION_SCHEMA = "humanize-visible-delivery-attestation/v1"
EVIDENCE_SCHEMA = "humanize-direct-validation-evidence/v5"
VALIDATION_INVOCATION_SCHEMA = "humanize-validation-invocation/v4"
TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA = "humanize-template-field-edit-scope/v1"
TEMPLATE_FIELD_PERMISSION = "PAYLOAD_ONLY"
VALID_MODES = ("REWRITE", "DRAFT")
VALID_SCENES = ("AUTO", "GENERAL", "COURSE", "MODELING", "RESEARCH")
VALID_DOCUMENT_FORMATS = ("markdown", "tex")
VALID_VISIBLE_OUTPUTS = ("BODY_ONLY", "BODY_WITH_SUMMARY")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_INLINE_BYTES = 8 * 1024 * 1024
MAX_DIAGNOSTIC_CODES = 32
MAX_ACTIONABLE_FINDINGS = 12
MAX_DIAGNOSTIC_MATCH_CHARS = 240
MAX_DIAGNOSTIC_RATIONALE_CHARS = 480

EVIDENCE_MANIFEST_KEYS = {
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
REQUIRED_EVIDENCE_ARTIFACTS = {
    "execution-record.json",
    "inputs/after.bin",
    "inputs/before.bin",
    "invocation-request.json",
    "rendered-output.txt",
    "stderr.txt",
    "validation-result.json",
}


class InlineRunError(ValueError):
    """Raised when an inline run or its evidence cannot be trusted."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InlineRunError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise InlineRunError(f"non_finite_json_number:{value}")


def _load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise InlineRunError(f"invalid_json:{label}:{type(error).__name__}") from error


def _canonical_json_compact(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return _canonical_json_compact(value) + b"\n"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_stable(path: Path, label: str) -> bytes:
    try:
        stat_before = path.stat()
        raw = path.read_bytes()
        stat_after = path.stat()
    except OSError as error:
        raise InlineRunError(f"input_unavailable:{label}:{type(error).__name__}") from error
    before = (
        stat_before.st_dev,
        stat_before.st_ino,
        stat_before.st_size,
        stat_before.st_mtime_ns,
        stat_before.st_ctime_ns,
    )
    after = (
        stat_after.st_dev,
        stat_after.st_ino,
        stat_after.st_size,
        stat_after.st_mtime_ns,
        stat_after.st_ctime_ns,
    )
    if before != after or len(raw) != stat_after.st_size:
        raise InlineRunError(f"input_changed_during_snapshot:{label}")
    if len(raw) > MAX_INLINE_BYTES:
        raise InlineRunError(f"input_too_large_for_inline_path:{label}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise InlineRunError(f"input_not_utf8:{label}") from error
    if "\x00" in text:
        raise InlineRunError(f"input_contains_nul:{label}")
    return raw


def _template_scope_descriptor(
    raw: bytes | None,
    *,
    before_sha256: str,
    artifact_path: str | None,
) -> dict[str, Any]:
    if raw is None:
        return {
            "provided": False,
            "path": None,
            "sha256": None,
            "size_bytes": 0,
            "source_sha256": before_sha256,
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "local_clearance_supported": False,
        }
    payload = _load_json_bytes(raw, "template_field_edit_scope")
    if not isinstance(payload, dict):
        raise InlineRunError("template_field_edit_scope_is_not_an_object")
    if set(payload) != {"schema_version", "source_sha256", "edits"}:
        raise InlineRunError("template_field_edit_scope_keys_are_invalid")
    if payload.get("schema_version") != TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA:
        raise InlineRunError("template_field_edit_scope_schema_is_invalid")
    source_sha256 = payload.get("source_sha256")
    if not isinstance(source_sha256, str) or not HEX64_RE.fullmatch(source_sha256):
        raise InlineRunError("template_field_edit_scope_source_sha256_is_invalid")
    if source_sha256 != before_sha256:
        raise InlineRunError("template_field_edit_scope_source_sha256_mismatch")
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise InlineRunError("template_field_edit_scope_edits_are_empty")
    if not isinstance(artifact_path, str) or not artifact_path:
        raise InlineRunError("template_field_edit_scope_artifact_path_is_invalid")
    return {
        "provided": True,
        "path": artifact_path,
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
        "source_sha256": source_sha256,
        "permission_boundary": TEMPLATE_FIELD_PERMISSION,
        "local_clearance_supported": False,
    }


def _is_reparse(stat_result: os.stat_result) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0))
    marker = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & marker)


def _read_regular_single_link(path: Path, label: str) -> bytes:
    try:
        link_stat = path.lstat()
    except OSError as error:
        raise InlineRunError(
            f"evidence_artifact_unavailable:{label}:{type(error).__name__}"
        ) from error
    if not stat.S_ISREG(link_stat.st_mode) or _is_reparse(link_stat):
        raise InlineRunError(f"evidence_artifact_is_not_regular:{label}")
    if int(getattr(link_stat, "st_nlink", 1)) != 1:
        raise InlineRunError(f"evidence_artifact_is_hardlinked:{label}")
    return _read_stable(path, f"evidence:{label}")


def _safe_evidence_name(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InlineRunError("evidence_artifact_name_is_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InlineRunError(f"evidence_artifact_name_is_unsafe:{value}")
    if path.as_posix() != value:
        raise InlineRunError(f"evidence_artifact_name_is_noncanonical:{value}")
    return value


def _diagnostic_codes(items: Any) -> tuple[list[str], int]:
    if not isinstance(items, list):
        return [], 0
    codes: list[str] = []
    for item in items:
        value: Any = item
        if isinstance(item, dict):
            value = next(
                (
                    item.get(key)
                    for key in ("code", "signal_id", "id")
                    if item.get(key) is not None
                ),
                None,
            )
        if isinstance(value, str) and value and value not in codes:
            codes.append(value)
    return codes[:MAX_DIAGNOSTIC_CODES], len(items)


def _diagnostic_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _warning_delta_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        marker: count
        for marker, count in value.items()
        if isinstance(marker, str)
        and marker
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count > 0
    }


def _speech_warning_actionable_candidates(items: Any) -> list[dict[str, Any]]:
    """Turn speech-act deltas into bounded, location-aware repair candidates."""

    if not isinstance(items, list):
        return []
    candidates: list[dict[str, Any]] = []
    for warning in items:
        if not isinstance(warning, dict):
            continue
        code = warning.get("code")
        if not isinstance(code, str) or not code.startswith("SPEECH_ACT_"):
            continue
        details = warning.get("details")
        residuals = details.get("residual_delta") if isinstance(details, dict) else None
        if not isinstance(residuals, list):
            continue
        fingerprint = warning.get("warning_fingerprint")
        for residual in residuals:
            if not isinstance(residual, dict):
                continue
            for source_side, delta_key, occurrences_key, action, rationale in (
                (
                    "before",
                    "removed",
                    "before_occurrences",
                    "RESTORE_SOURCE_FORCE",
                    "A source speech-act marker has no retained counterpart. Restore the "
                    "source wording or an explicit marker with the same force, then rerun; "
                    "otherwise downgrade to PATCH/UNRESOLVED.",
                ),
                (
                    "after",
                    "added",
                    "after_occurrences",
                    "REMOVE_NEW_FORCE",
                    "The candidate introduces a speech-act marker absent from the source. "
                    "Remove the new force or restore the source clause, then rerun; otherwise "
                    "downgrade to PATCH/UNRESOLVED.",
                ),
            ):
                remaining = _warning_delta_counts(residual.get(delta_key))
                occurrences = residual.get(occurrences_key)
                if not remaining or not isinstance(occurrences, list):
                    continue
                for occurrence in occurrences:
                    if not isinstance(occurrence, dict):
                        continue
                    marker = occurrence.get("marker")
                    if not isinstance(marker, str) or remaining.get(marker, 0) <= 0:
                        continue
                    line = occurrence.get("line")
                    column = occurrence.get("column")
                    context = occurrence.get("sentence_context")
                    identity = {
                        "code": code,
                        "warning_fingerprint": fingerprint,
                        "source_side": source_side,
                        "marker": marker,
                        "line": line,
                        "column": column,
                    }
                    candidates.append(
                        {
                            "signal_id": code,
                            "finding_hash": _sha256(_canonical_json_compact(identity)),
                            "action": action,
                            "severity": warning.get("severity", "warning"),
                            "file": source_side,
                            "matched": marker,
                            "rationale": rationale,
                            "line": line,
                            "column": column,
                            "source_side": source_side,
                            "sentence_context": context,
                            "warning_fingerprint": fingerprint,
                        }
                    )
                    remaining[marker] -= 1
    return candidates


def _template_field_actionable_candidates(items: Any) -> list[dict[str, Any]]:
    """Turn unresolved template-field changes into bounded repair candidates."""

    if not isinstance(items, list):
        return []
    actions = {
        "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED": (
            "RESTORE_OR_AUTHORIZE_PAYLOAD",
            "Restore the original template-field payload, or provide a source-bound "
            "PAYLOAD_ONLY authorization with an explicit field scope, then rerun.",
        ),
        "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT": (
            "RESTORE_FIELD_ROLE_OR_FORCE",
            "Restore the field's original duty, applicability, logical relation, and "
            "assertion force. PAYLOAD_ONLY authorization cannot clear role or force drift.",
        ),
        "TEMPLATE_FIELD_HEADER_CHANGED": (
            "RESTORE_TEMPLATE_FIELD_HEADER",
            "Restore the protected template-field label, separator, and position. Header "
            "changes are not locally authorizable.",
        ),
    }
    candidates: list[dict[str, Any]] = []
    for finding in items:
        if not isinstance(finding, dict):
            continue
        code = finding.get("code")
        severity = finding.get("severity")
        if (
            not isinstance(code, str)
            or not code
            or severity not in {"warning", "error"}
        ):
            continue

        field_label = finding.get("field_label")
        source_line = finding.get("source_line")
        after_line = finding.get("after_line")
        if code == "TEMPLATE_FIELD_HEADER_CHANGED":
            before_headers = finding.get("before_headers")
            after_headers = finding.get("after_headers")
            header_records = [
                item
                for group in (before_headers, after_headers)
                if isinstance(group, list)
                for item in group
                if isinstance(item, dict)
            ]
            labels = [
                item["label"]
                for item in header_records
                if isinstance(item.get("label"), str) and item["label"]
            ]
            if not isinstance(field_label, str) or not field_label:
                field_label = " / ".join(dict.fromkeys(labels)) or "TEMPLATE_FIELD_HEADER"
            if not isinstance(source_line, int) or isinstance(source_line, bool):
                source_line = next(
                    (
                        item.get("line")
                        for item in before_headers or []
                        if isinstance(item, dict)
                        and isinstance(item.get("line"), int)
                        and not isinstance(item.get("line"), bool)
                    ),
                    None,
                )
            if not isinstance(after_line, int) or isinstance(after_line, bool):
                after_line = next(
                    (
                        item.get("line")
                        for item in after_headers or []
                        if isinstance(item, dict)
                        and isinstance(item.get("line"), int)
                        and not isinstance(item.get("line"), bool)
                    ),
                    None,
                )

        if not isinstance(field_label, str) or not field_label:
            field_label = "TEMPLATE_FIELD"
        source_line = (
            source_line
            if isinstance(source_line, int) and not isinstance(source_line, bool)
            else None
        )
        after_line = (
            after_line
            if isinstance(after_line, int) and not isinstance(after_line, bool)
            else None
        )
        source_side = "after" if after_line is not None else "before"
        line = after_line if after_line is not None else source_line
        action, rationale = actions.get(
            code,
            (
                "REVIEW_TEMPLATE_FIELD_CHANGE",
                "Review this template-field change against the frozen source role and "
                "authorization scope, restore unsupported edits, then rerun.",
            ),
        )
        identity = {
            key: finding.get(key)
            for key in (
                "code",
                "change_id",
                "field_label",
                "source_line",
                "after_line",
                "payload_role",
                "authorization_status",
            )
        }
        candidates.append(
            {
                "signal_id": code,
                "error_code": code,
                "finding_hash": _sha256(_canonical_json_compact(identity)),
                "action": action,
                "severity": severity,
                "file": source_side,
                "matched": field_label,
                "rationale": rationale,
                "line": line,
                "column": 1 if line is not None else None,
                "source_side": source_side,
                "field_label": field_label,
                "source_line": source_line,
                "after_line": after_line,
                "payload_role": finding.get("payload_role"),
                "authorization_status": finding.get("authorization_status"),
                "change_types": finding.get("change_types"),
            }
        )
    return candidates


def _actionable_finding_summaries(
    *groups: tuple[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    summaries: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    unique_count = 0
    for role, items in groups:
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            signal_id = item.get("signal_id")
            if not isinstance(signal_id, str) or not signal_id:
                continue
            finding_hash = item.get("finding_hash")
            identity = (
                finding_hash
                if isinstance(finding_hash, str) and HEX64_RE.fullmatch(finding_hash)
                else _sha256(
                    _canonical_json_compact(
                        {
                            key: item.get(key)
                            for key in ("signal_id", "file", "line", "column", "matched")
                        }
                    )
                )
            )
            existing = positions.get(identity)
            if existing is not None:
                roles = summaries[existing]["diagnostic_roles"]
                if role not in roles:
                    roles.append(role)
                continue
            unique_count += 1
            if len(summaries) >= MAX_ACTIONABLE_FINDINGS:
                continue
            summary: dict[str, Any] = {
                "signal_id": signal_id,
                "diagnostic_roles": [role],
                "action": _diagnostic_text(item.get("action"), 40),
                "severity": _diagnostic_text(item.get("severity"), 40),
                "file": _diagnostic_text(item.get("file"), 80),
                "matched": _diagnostic_text(
                    item.get("matched"), MAX_DIAGNOSTIC_MATCH_CHARS
                ),
                "rationale": _diagnostic_text(
                    item.get("rationale"), MAX_DIAGNOSTIC_RATIONALE_CHARS
                ),
            }
            for key in ("line", "column"):
                value = item.get(key)
                summary[key] = value if isinstance(value, int) and not isinstance(value, bool) else None
            for key in ("source_line", "after_line"):
                value = item.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    summary[key] = value
            for key, limit in (
                ("source_side", 16),
                ("sentence_context", MAX_DIAGNOSTIC_MATCH_CHARS),
                ("error_code", 80),
                ("field_label", 80),
                ("payload_role", 160),
                ("authorization_status", 80),
            ):
                value = _diagnostic_text(item.get(key), limit)
                if value:
                    summary[key] = value
            change_types = item.get("change_types")
            if isinstance(change_types, list):
                bounded_change_types = [
                    value
                    for value in change_types
                    if isinstance(value, str) and value
                ][:MAX_DIAGNOSTIC_CODES]
                if bounded_change_types:
                    summary["change_types"] = bounded_change_types
            warning_fingerprint = item.get("warning_fingerprint")
            if isinstance(warning_fingerprint, str) and HEX64_RE.fullmatch(
                warning_fingerprint
            ):
                summary["warning_fingerprint"] = warning_fingerprint
            if isinstance(finding_hash, str) and HEX64_RE.fullmatch(finding_hash):
                summary["finding_hash"] = finding_hash
            positions[identity] = len(summaries)
            summaries.append(summary)
    return summaries, unique_count


def _summarize_validation(payload: Mapping[str, Any]) -> dict[str, Any]:
    invariants = payload.get("invariants")
    invariant_errors = invariants.get("errors", []) if isinstance(invariants, dict) else []
    hard_codes, hard_count = _diagnostic_codes(invariant_errors)
    warning_codes, warning_count = _diagnostic_codes(
        payload.get("warnings_without_resolution_proposal")
    )
    high_codes, high_count = _diagnostic_codes(payload.get("unexplained_high_findings"))
    introduced_codes, introduced_count = _diagnostic_codes(
        payload.get("introduced_findings")
    )
    template_codes, template_count = _diagnostic_codes(
        payload.get("template_field_findings")
    )
    strict_summary = payload.get("strict_corpus_summary")
    if not isinstance(strict_summary, dict):
        strict_summary = {}
    warning_actionables = _speech_warning_actionable_candidates(
        payload.get("warnings_without_resolution_proposal")
    )
    template_actionables = _template_field_actionable_candidates(
        payload.get("template_field_findings")
    )
    actionable_findings, actionable_count = _actionable_finding_summaries(
        ("pending_warning", warning_actionables),
        ("unexplained_high", payload.get("unexplained_high_findings")),
        ("introduced", payload.get("introduced_findings")),
        ("template_field", template_actionables),
    )
    raw_reasons = payload.get("review_reasons")
    review_reasons = (
        [value for value in raw_reasons if isinstance(value, str)][:MAX_DIAGNOSTIC_CODES]
        if isinstance(raw_reasons, list)
        else []
    )
    mechanical = str(payload.get("mechanical_validation_status", "FAIL"))
    if mechanical == "PASS":
        next_action = "EMIT_VERIFIED_SNAPSHOT"
    elif mechanical == "FAIL":
        next_action = "STOP_HARD_FAILURE"
    else:
        next_action = "REVISE_CANDIDATE_AND_RERUN"
    return {
        "next_action": next_action,
        "detail_source": "validation.json",
        "review_reasons": review_reasons,
        "hard_error_codes": hard_codes,
        "hard_error_count": hard_count,
        "pending_warning_codes": warning_codes,
        "pending_warning_count": warning_count,
        "unexplained_high_signal_ids": high_codes,
        "unexplained_high_count": high_count,
        "strict_corpus_enabled": bool(strict_summary.get("enabled", False)),
        "strict_before_count": int(strict_summary.get("before_candidates", 0)),
        "strict_after_count": int(strict_summary.get("after_candidates", 0)),
        "strict_unexplained_count": int(
            strict_summary.get("unexplained_candidates", 0)
        ),
        "strict_accepted_count": int(strict_summary.get("accepted_candidates", 0)),
        "strict_no_change_allowed": bool(
            strict_summary.get("no_change_allowed", False)
        ),
        "introduced_signal_ids": introduced_codes,
        "introduced_signal_count": introduced_count,
        "template_field_codes": template_codes,
        "template_field_count": template_count,
        "actionable_findings": actionable_findings,
        "actionable_finding_count": actionable_count,
        "actionable_findings_truncated": actionable_count > MAX_ACTIONABLE_FINDINGS,
        "diagnostic_lists_truncated": any(
            count > MAX_DIAGNOSTIC_CODES
            for count in (
                hard_count,
                warning_count,
                high_count,
                introduced_count,
                template_count,
            )
        )
        or actionable_count > MAX_ACTIONABLE_FINDINGS,
    }


def _default_output_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home) if codex_home else Path.home() / ".codex"
    return root / "tmp" / "humanize-inline"


def _relative_artifact(path: Path, run_dir: Path) -> str:
    try:
        relative = path.relative_to(run_dir).as_posix()
    except ValueError as error:
        raise InlineRunError("artifact_outside_run_dir") from error
    if relative.startswith("../") or relative in {"", "."}:
        raise InlineRunError("artifact_path_is_not_safe")
    return relative


def _not_run_payload(reason: str) -> dict[str, Any]:
    return {
        "status": "REVIEW",
        "exit_code": 2,
        "mechanical_validation_status": "NOT_RUN",
        "mechanical_validation_exit_code": 2,
        "delivery_gate_status": "REVIEW",
        "paired_quality_review_status": "NOT_RUN",
        "paired_quality_clearance_granted": False,
        "humanize_quality_claim_allowed": False,
        "completion_claim_allowed": False,
        "review_reasons": [reason],
        "evidence": {"checker_executed": False},
    }


def _integrity_failure(reason: str) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "exit_code": 1,
        "mechanical_validation_status": "FAIL",
        "mechanical_validation_exit_code": 1,
        "delivery_gate_status": "FAIL",
        "paired_quality_review_status": "BLOCKED_BY_MECHANICAL_GATE",
        "paired_quality_clearance_granted": False,
        "humanize_quality_claim_allowed": False,
        "completion_claim_allowed": False,
        "review_reasons": [reason],
        "evidence": {"checker_executed": False},
    }


def _validate_payload(
    payload: Any,
    *,
    process_exit_code: int,
    before_sha256: str,
    after_sha256: str,
    mode: str,
    scene: str,
    template_scope: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InlineRunError("validator_payload_is_not_an_object")
    required = {
        "status",
        "exit_code",
        "delivery_gate_exit_code",
        "mechanical_validation_status",
        "mechanical_validation_exit_code",
        "delivery_gate_status",
        "paired_quality_review_status",
        "paired_quality_clearance_granted",
        "humanize_quality_claim_allowed",
        "mode",
        "scene",
        "evidence",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise InlineRunError(f"validator_payload_missing:{missing[0]}")
    exit_code = payload["exit_code"]
    if isinstance(exit_code, bool) or exit_code not in {0, 1, 2}:
        raise InlineRunError("validator_exit_code_is_invalid")
    if exit_code != process_exit_code:
        raise InlineRunError("validator_process_exit_code_mismatch")
    mechanical = payload["mechanical_validation_status"]
    delivery = payload["delivery_gate_status"]
    if mechanical not in {"PASS", "FAIL", "REVIEW"}:
        raise InlineRunError("validator_mechanical_status_is_invalid")
    if delivery not in {"PASS", "FAIL", "REVIEW"}:
        raise InlineRunError("validator_delivery_status_is_invalid")
    if payload["status"] != delivery:
        raise InlineRunError("validator_status_delivery_mismatch")
    expected_delivery_exit = {"PASS": 0, "FAIL": 1, "REVIEW": 2}[delivery]
    delivery_exit = payload["delivery_gate_exit_code"]
    if isinstance(delivery_exit, bool) or delivery_exit != expected_delivery_exit:
        raise InlineRunError("validator_delivery_exit_code_mismatch")
    if exit_code != expected_delivery_exit:
        raise InlineRunError("validator_exit_code_delivery_mismatch")
    expected_mechanical_exit = {"PASS": 0, "FAIL": 1, "REVIEW": 2}[mechanical]
    mechanical_exit = payload["mechanical_validation_exit_code"]
    if isinstance(mechanical_exit, bool) or mechanical_exit != expected_mechanical_exit:
        raise InlineRunError("validator_mechanical_exit_code_mismatch")
    if mechanical == "FAIL" and delivery != "FAIL":
        raise InlineRunError("validator_failure_gate_mismatch")
    if mechanical == "REVIEW" and delivery != "REVIEW":
        raise InlineRunError("validator_review_gate_mismatch")
    if payload["mode"] != mode or payload["scene"] != scene:
        raise InlineRunError("validator_invocation_context_mismatch")
    clearance = payload["paired_quality_clearance_granted"]
    quality_claim = payload["humanize_quality_claim_allowed"]
    if not isinstance(clearance, bool) or not isinstance(quality_claim, bool):
        raise InlineRunError("validator_quality_permission_is_invalid")
    if quality_claim and not clearance:
        raise InlineRunError("validator_quality_claim_without_clearance")
    evidence = payload["evidence"]
    if not isinstance(evidence, dict) or evidence.get("checker_executed") is not True:
        raise InlineRunError("validator_checker_execution_is_unproven")
    if evidence.get("before_sha256") != before_sha256:
        raise InlineRunError("validator_before_sha256_mismatch")
    if evidence.get("after_sha256") != after_sha256:
        raise InlineRunError("validator_after_sha256_mismatch")
    scope_check = payload.get("template_field_edit_scope_check")
    if not isinstance(scope_check, dict):
        raise InlineRunError("validator_template_field_scope_check_is_missing")
    expected_scope_fields = {
        "provided": template_scope.get("provided"),
        "source_sha256": before_sha256,
        "permission_boundary": TEMPLATE_FIELD_PERMISSION,
        "local_clearance_supported": False,
    }
    for key, expected in expected_scope_fields.items():
        if scope_check.get(key) != expected:
            raise InlineRunError(f"validator_template_field_scope_mismatch:{key}")
    if template_scope.get("provided") is True:
        if scope_check.get("status") != "PASS":
            raise InlineRunError("validator_template_field_scope_was_not_validated")
        if scope_check.get("schema_version") != TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA:
            raise InlineRunError("validator_template_field_scope_schema_mismatch")
        if scope_check.get("scope_sha256") != template_scope.get("sha256"):
            raise InlineRunError("validator_template_field_scope_sha256_mismatch")
        authorized_count = scope_check.get("authorized_edit_count")
        if (
            isinstance(authorized_count, bool)
            or not isinstance(authorized_count, int)
            or authorized_count < 1
        ):
            raise InlineRunError("validator_template_field_scope_authorization_is_empty")
    else:
        if scope_check.get("status") != "N/A":
            raise InlineRunError("validator_unprovided_template_field_scope_status_mismatch")
        if scope_check.get("scope_sha256") is not None:
            raise InlineRunError("validator_unprovided_template_field_scope_has_sha256")
        if scope_check.get("authorized_edit_count") != 0:
            raise InlineRunError("validator_unprovided_template_field_scope_has_authorization")
    return payload


def run_inline(
    before_path: Path,
    after_path: Path,
    *,
    output_root: Path,
    mode: str,
    scene: str,
    document_format: str,
    visible_output: str,
    keep_reasons: Sequence[str] = (),
    protected_terms: Sequence[str] = (),
    strict_speech_acts: bool = False,
    fragment: bool = False,
    template_field_edit_scope_path: Path | None = None,
    validator_path: Path = DEFAULT_VALIDATOR,
) -> tuple[dict[str, Any], Path]:
    mode = mode.upper()
    scene = scene.upper()
    document_format = document_format.lower()
    visible_output = visible_output.upper()
    if mode not in VALID_MODES:
        raise InlineRunError("invalid_mode")
    if scene not in VALID_SCENES:
        raise InlineRunError("invalid_scene")
    if document_format not in VALID_DOCUMENT_FORMATS:
        raise InlineRunError("invalid_document_format")
    if visible_output not in VALID_VISIBLE_OUTPUTS:
        raise InlineRunError("invalid_visible_output")
    if fragment and mode != "REWRITE":
        raise InlineRunError("fragment_requires_rewrite")
    if template_field_edit_scope_path is not None and mode != "REWRITE":
        raise InlineRunError("template_field_edit_scope_requires_rewrite")

    before_raw = _read_stable(before_path, "before")
    after_raw = _read_stable(after_path, "after")
    before_sha256 = _sha256(before_raw)
    after_sha256 = _sha256(after_raw)
    template_scope_raw = (
        _read_stable(template_field_edit_scope_path, "template_field_edit_scope")
        if template_field_edit_scope_path is not None
        else None
    )
    template_scope_artifact_path = (
        "artifacts/template-field-edit-scope.json"
        if template_scope_raw is not None
        else None
    )
    template_scope = _template_scope_descriptor(
        template_scope_raw,
        before_sha256=before_sha256,
        artifact_path=template_scope_artifact_path,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="hir1-", dir=output_root))
    suffix = ".tex" if document_format == "tex" else ".md"
    before_snapshot = run_dir / "artifacts" / f"before{suffix}"
    after_snapshot = run_dir / "artifacts" / f"after{suffix}"
    validation_stdout = run_dir / "validator.stdout.json"
    validation_stderr = run_dir / "validator.stderr.txt"
    evidence_dir = run_dir / "evidence"
    _atomic_write(before_snapshot, before_raw)
    _atomic_write(after_snapshot, after_raw)
    template_scope_snapshot: Path | None = None
    if template_scope_raw is not None:
        template_scope_snapshot = run_dir / str(template_scope_artifact_path)
        _atomic_write(template_scope_snapshot, template_scope_raw)

    command = [
        sys.executable,
        str(validator_path),
        str(before_snapshot),
        str(after_snapshot),
        "--mode",
        mode,
        "--scene",
        scene,
        "--document-format",
        document_format,
        "--format",
        "json",
        "--evidence-dir",
        str(evidence_dir),
    ]
    if strict_speech_acts:
        command.append("--strict-speech-acts")
    if fragment:
        command.append("--fragment")
    if template_scope_snapshot is not None:
        command.extend(("--template-field-edit-scope", str(template_scope_snapshot)))
    for reason in keep_reasons:
        command.extend(("--keep-reason", reason))
    for term in protected_terms:
        command.extend(("--term", term))

    invocation = {
        "schema_version": INVOCATION_SCHEMA,
        "source_kind": "INLINE_TEXT",
        "mode": mode,
        "scene": scene,
        "document_format": document_format,
        "visible_output": visible_output,
        "strict_speech_acts": strict_speech_acts,
        "fragment": fragment,
        "keep_reasons": list(keep_reasons),
        "protected_terms": list(protected_terms),
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "template_field_edit_scope": template_scope,
    }
    invocation_raw = _canonical_json(invocation)
    _atomic_write(run_dir / "invocation.json", invocation_raw)

    try:
        if not validator_path.is_file():
            raise FileNotFoundError("validator entrypoint is unavailable")
        completed = subprocess.run(command, check=False, capture_output=True)
    except OSError as error:
        stdout_raw = b""
        stderr_raw = f"{type(error).__name__}\n".encode("ascii")
        validation = _not_run_payload("validator_process_not_started")
        process_exit_code = None
        execution_status = "NOT_RUN"
    else:
        stdout_raw = completed.stdout
        stderr_raw = completed.stderr
        process_exit_code = completed.returncode
        try:
            candidate_payload = _load_json_bytes(stdout_raw, "validator_stdout")
            validation = _validate_payload(
                candidate_payload,
                process_exit_code=process_exit_code,
                before_sha256=before_sha256,
                after_sha256=after_sha256,
                mode=mode,
                scene=scene,
                template_scope=template_scope,
            )
        except InlineRunError as error:
            validation = _integrity_failure(str(error))
            execution_status = "VALIDATOR_EVIDENCE_INVALID"
        else:
            execution_status = "VALIDATED"

    evidence_manifest_raw: bytes | None = None
    if execution_status == "VALIDATED":
        try:
            evidence_manifest_raw = _read_regular_single_link(
                evidence_dir / "evidence-manifest.json", "evidence_manifest"
            )
            evidence_manifest = _load_json_bytes(
                evidence_manifest_raw, "evidence_manifest"
            )
            _validate_evidence_manifest(
                evidence_manifest,
                evidence_dir=evidence_dir,
                before_raw=before_raw,
                after_raw=after_raw,
                validator_stdout=stdout_raw,
                validator_stderr=stderr_raw,
                mode=mode,
                scene=scene,
                validation=validation,
                template_scope_raw=template_scope_raw,
            )
        except (OSError, InlineRunError) as error:
            validation = _integrity_failure(str(error))
            execution_status = "VALIDATOR_EVIDENCE_INVALID"
            evidence_manifest_raw = None

    _atomic_write(validation_stdout, stdout_raw)
    _atomic_write(validation_stderr, stderr_raw)
    validation_raw = _canonical_json(validation)
    _atomic_write(run_dir / "validation.json", validation_raw)
    mechanical = str(validation["mechanical_validation_status"])
    delivery = str(validation["delivery_gate_status"])
    body_emission_allowed = mechanical == "PASS" and delivery in {"PASS", "REVIEW"}
    diagnostics = _summarize_validation(validation)
    record = {
        "schema_version": RUN_SCHEMA,
        "run_id": run_dir.name,
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
        "external_anchor_status": "NOT_PROVIDED",
        "source_kind": "INLINE_TEXT",
        "mode": mode,
        "scene": scene,
        "document_format": document_format,
        "visible_output": visible_output,
        "execution_status": execution_status,
        "mechanical_validation_status": mechanical,
        "delivery_gate_status": delivery,
        "validator_process_exit_code": process_exit_code,
        "exit_code": int(validation["exit_code"]),
        "paired_quality_review_status": str(
            validation.get("paired_quality_review_status", "NOT_RUN")
        ),
        "humanize_quality_claim_allowed": bool(
            validation.get("humanize_quality_claim_allowed", False)
        ),
        "completion_claim_allowed": False,
        "body_emission_allowed": body_emission_allowed,
        "diagnostics": diagnostics,
        "artifacts": {
            "before": {
                "path": _relative_artifact(before_snapshot, run_dir),
                "sha256": before_sha256,
                "size_bytes": len(before_raw),
            },
            "after": {
                "path": _relative_artifact(after_snapshot, run_dir),
                "sha256": after_sha256,
                "size_bytes": len(after_raw),
            },
            "validation": {
                "path": "validation.json",
                "sha256": _sha256(validation_raw),
                "size_bytes": len(validation_raw),
            },
            "invocation": {
                "path": "invocation.json",
                "sha256": _sha256(invocation_raw),
                "size_bytes": len(invocation_raw),
            },
            "validator_stdout": {
                "path": "validator.stdout.json",
                "sha256": _sha256(stdout_raw),
                "size_bytes": len(stdout_raw),
            },
            "validator_stderr": {
                "path": "validator.stderr.txt",
                "sha256": _sha256(stderr_raw),
                "size_bytes": len(stderr_raw),
            },
            "evidence_manifest": {
                "path": "evidence/evidence-manifest.json",
                "required": execution_status == "VALIDATED",
                "sha256": (
                    _sha256(evidence_manifest_raw)
                    if evidence_manifest_raw is not None
                    else None
                ),
                "size_bytes": (
                    len(evidence_manifest_raw)
                    if evidence_manifest_raw is not None
                    else None
                ),
            },
            "template_field_edit_scope": template_scope,
        },
        "response_contract": {
            "body_source": _relative_artifact(after_snapshot, run_dir),
            "body_must_be_emitted_verbatim": True,
            "body_only_hides_audit_display_not_audit_execution": True,
            "any_post_validation_mutation_requires_rerun": True,
            "stdout_byte_identity_scope": "LOCAL_PROCESS_STDOUT_ONLY",
            "chat_transport_byte_identity_status": "NOT_EVALUATED",
            "terminal_line_ending_is_candidate_content": after_raw.endswith(
                (b"\n", b"\r")
            ),
        },
    }
    _atomic_write(run_dir / "run.json", _canonical_json(record))
    return record, run_dir


def _require_hex64(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        raise InlineRunError(f"invalid_sha256:{label}")
    return value


def _validate_evidence_manifest(
    payload: Any,
    *,
    evidence_dir: Path,
    before_raw: bytes,
    after_raw: bytes,
    validator_stdout: bytes,
    validator_stderr: bytes,
    mode: str,
    scene: str,
    validation: Mapping[str, Any],
    template_scope_raw: bytes | None,
) -> None:
    if not isinstance(payload, dict) or payload.get("schema") != EVIDENCE_SCHEMA:
        raise InlineRunError("evidence_manifest_schema_is_invalid")
    if set(payload) != EVIDENCE_MANIFEST_KEYS:
        raise InlineRunError("evidence_manifest_keys_are_invalid")
    if payload.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
        raise InlineRunError("evidence_manifest_integrity_scope_is_invalid")
    if payload.get("external_anchor_status") != "NOT_PROVIDED":
        raise InlineRunError("evidence_manifest_external_anchor_is_untrusted")
    if payload.get("contains_source_content") is not True:
        raise InlineRunError("evidence_manifest_content_disclosure_is_invalid")
    manifest_sha256 = _require_hex64(
        payload.get("manifest_sha256"), "evidence_manifest_self"
    )
    manifest_body = dict(payload)
    manifest_body.pop("manifest_sha256", None)
    if _sha256(_canonical_json_compact(manifest_body)) != manifest_sha256:
        raise InlineRunError("evidence_manifest_self_hash_mismatch")
    bindings = payload.get("source_bindings")
    if not isinstance(bindings, dict):
        raise InlineRunError("evidence_manifest_source_bindings_are_invalid")
    if set(bindings) != {"before", "after"}:
        raise InlineRunError("evidence_manifest_source_binding_keys_are_invalid")
    expected_bindings = {
        "before": (_sha256(before_raw), len(before_raw)),
        "after": (_sha256(after_raw), len(after_raw)),
    }
    for label, (expected_sha, expected_size) in expected_bindings.items():
        item = bindings.get(label)
        if not isinstance(item, dict):
            raise InlineRunError(f"evidence_manifest_source_binding_missing:{label}")
        if item.get("sha256") != expected_sha or item.get("size") != expected_size:
            raise InlineRunError(f"evidence_manifest_source_binding_mismatch:{label}")
    expected_fields = {
        "mode": mode,
        "scene": scene,
        "status": validation.get("status"),
        "delivery_gate_status": validation.get("delivery_gate_status"),
        "exit_code": validation.get("exit_code"),
        "paired_quality_review_status": validation.get(
            "paired_quality_review_status"
        ),
    }
    for key, expected in expected_fields.items():
        if payload.get(key) != expected:
            raise InlineRunError(f"evidence_manifest_field_mismatch:{key}")

    try:
        evidence_stat = evidence_dir.lstat()
    except OSError as error:
        raise InlineRunError(
            f"evidence_directory_unavailable:{type(error).__name__}"
        ) from error
    if not stat.S_ISDIR(evidence_stat.st_mode) or _is_reparse(evidence_stat):
        raise InlineRunError("evidence_directory_is_not_regular")

    artifact_records = payload.get("artifacts")
    if not isinstance(artifact_records, dict):
        raise InlineRunError("evidence_artifact_records_are_invalid")
    if not REQUIRED_EVIDENCE_ARTIFACTS.issubset(artifact_records):
        raise InlineRunError("evidence_required_artifact_is_missing")
    artifact_bytes: dict[str, bytes] = {}
    expected_files = {"evidence-manifest.json"}
    expected_dirs: set[str] = set()
    for raw_name, record in artifact_records.items():
        name = _safe_evidence_name(raw_name)
        if not isinstance(record, dict) or set(record) != {"sha256", "size"}:
            raise InlineRunError(f"evidence_artifact_record_is_invalid:{name}")
        expected_sha = _require_hex64(record.get("sha256"), f"evidence:{name}")
        expected_size = record.get("size")
        if (
            isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
            or expected_size < 0
        ):
            raise InlineRunError(f"evidence_artifact_size_is_invalid:{name}")
        path = evidence_dir.joinpath(*PurePosixPath(name).parts)
        raw = _read_regular_single_link(path, name)
        if len(raw) != expected_size or _sha256(raw) != expected_sha:
            raise InlineRunError(f"evidence_artifact_hash_mismatch:{name}")
        artifact_bytes[name] = raw
        expected_files.add(name)
        parent = PurePosixPath(name).parent
        while str(parent) != ".":
            expected_dirs.add(parent.as_posix())
            parent = parent.parent

    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for path in evidence_dir.rglob("*"):
        relative = path.relative_to(evidence_dir).as_posix()
        item_stat = path.lstat()
        if _is_reparse(item_stat):
            raise InlineRunError(f"evidence_reparse_point_rejected:{relative}")
        if stat.S_ISDIR(item_stat.st_mode):
            actual_dirs.add(relative)
        elif stat.S_ISREG(item_stat.st_mode):
            actual_files.add(relative)
        else:
            raise InlineRunError(f"evidence_special_path_rejected:{relative}")
    if actual_files != expected_files or actual_dirs != expected_dirs:
        raise InlineRunError("evidence_inventory_mismatch")

    scope_artifact_name = "inputs/template-field-edit-scope.json"
    if template_scope_raw is None:
        if scope_artifact_name in artifact_bytes:
            raise InlineRunError("evidence_unexpected_template_field_scope_artifact")
    else:
        if artifact_bytes.get(scope_artifact_name) != template_scope_raw:
            raise InlineRunError("evidence_template_field_scope_bytes_mismatch")

    validator_invocation = _load_json_bytes(
        artifact_bytes["invocation-request.json"], "evidence_invocation_request"
    )
    if (
        not isinstance(validator_invocation, dict)
        or validator_invocation.get("schema") != VALIDATION_INVOCATION_SCHEMA
    ):
        raise InlineRunError("evidence_invocation_schema_is_invalid")
    invocation_body = dict(validator_invocation)
    invocation_sha256 = _require_hex64(
        invocation_body.pop("invocation_sha256", None), "evidence_invocation_request"
    )
    invocation_run_id = invocation_body.pop("run_id", None)
    if _sha256(_canonical_json_compact(invocation_body)) != invocation_sha256:
        raise InlineRunError("evidence_invocation_self_hash_mismatch")
    if payload.get("invocation_request_sha256") != invocation_sha256:
        raise InlineRunError("evidence_invocation_manifest_hash_mismatch")
    if invocation_run_id != payload.get("run_id"):
        raise InlineRunError("evidence_invocation_run_id_mismatch")
    invocation_arguments = validator_invocation.get("arguments")
    invocation_inputs = validator_invocation.get("inputs")
    if not isinstance(invocation_arguments, dict) or not isinstance(invocation_inputs, dict):
        raise InlineRunError("evidence_invocation_scope_container_is_invalid")
    recorded_scope = invocation_arguments.get("template_field_edit_scope")
    if template_scope_raw is None:
        if recorded_scope != {"provided": False}:
            raise InlineRunError("evidence_invocation_unprovided_scope_mismatch")
        if "template_field_edit_scope" in invocation_inputs:
            raise InlineRunError("evidence_invocation_has_unexpected_scope_input")
    else:
        expected_scope_sha256 = _sha256(template_scope_raw)
        expected_scope = {
            "provided": True,
            "archive_path": scope_artifact_name,
            "sha256": expected_scope_sha256,
            "source_sha256": _sha256(before_raw),
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "local_clearance_supported": False,
        }
        if recorded_scope != expected_scope:
            raise InlineRunError("evidence_invocation_template_field_scope_mismatch")
        expected_scope_input = {
            "archive_path": scope_artifact_name,
            "original_suffix": ".json",
            "sha256": expected_scope_sha256,
            "size": len(template_scope_raw),
        }
        if invocation_inputs.get("template_field_edit_scope") != expected_scope_input:
            raise InlineRunError("evidence_invocation_template_field_scope_input_mismatch")

    identity = {
        "schema": EVIDENCE_SCHEMA,
        "run_id": payload.get("run_id"),
        "artifacts": artifact_records,
    }
    if _sha256(_canonical_json_compact(identity)) != payload.get("record_sha256"):
        raise InlineRunError("evidence_record_hash_mismatch")
    if artifact_bytes["inputs/before.bin"] != before_raw:
        raise InlineRunError("evidence_before_bytes_mismatch")
    if artifact_bytes["inputs/after.bin"] != after_raw:
        raise InlineRunError("evidence_after_bytes_mismatch")
    if artifact_bytes["validation-result.json"] != validator_stdout:
        raise InlineRunError("evidence_validation_stdout_mismatch")
    if artifact_bytes["rendered-output.txt"] != validator_stdout:
        raise InlineRunError("evidence_rendered_stdout_mismatch")
    if artifact_bytes["stderr.txt"] != validator_stderr:
        raise InlineRunError("evidence_stderr_mismatch")
    archived_validation = _load_json_bytes(
        artifact_bytes["validation-result.json"], "evidence_validation_result"
    )
    if archived_validation != dict(validation):
        raise InlineRunError("evidence_validation_payload_mismatch")
    execution = _load_json_bytes(
        artifact_bytes["execution-record.json"], "evidence_execution_record"
    )
    if not isinstance(execution, dict):
        raise InlineRunError("evidence_execution_record_is_invalid")
    execution_expectations = {
        "schema": "humanize-validation-execution-record/v1",
        "intended_exit_code": validation.get("exit_code"),
        "rendered_stdout_sha256": _sha256(validator_stdout),
        "rendered_stderr_sha256": _sha256(validator_stderr),
        "process_exit_observation": "NOT_EXTERNALLY_OBSERVED",
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
    }
    for key, expected in execution_expectations.items():
        if execution.get(key) != expected:
            raise InlineRunError(f"evidence_execution_record_mismatch:{key}")


def _artifact_path(run_dir: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InlineRunError(f"invalid_artifact_path:{label}")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise InlineRunError(f"unsafe_artifact_path:{label}")
    resolved = (run_dir / path).resolve(strict=False)
    if run_dir.resolve(strict=True) not in resolved.parents:
        raise InlineRunError(f"artifact_outside_run:{label}")
    return resolved


def verify_run(run_dir: Path) -> tuple[dict[str, Any], bytes | None]:
    try:
        run_stat = run_dir.lstat()
        if not stat.S_ISDIR(run_stat.st_mode) or _is_reparse(run_stat):
            raise InlineRunError("run_directory_is_not_regular")
        run_dir = run_dir.resolve(strict=True)
        record_raw = _read_regular_single_link(run_dir / "run.json", "run_record")
        record = _load_json_bytes(record_raw, "run_record")
        if not isinstance(record, dict) or record.get("schema_version") not in {
            RUN_SCHEMA,
            LEGACY_RUN_SCHEMA,
        }:
            raise InlineRunError("run_schema_is_invalid")
        current_schema = record.get("schema_version") == RUN_SCHEMA
        if record.get("run_id") != run_dir.name:
            raise InlineRunError("run_id_directory_mismatch")
        if record.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
            raise InlineRunError("run_integrity_scope_is_invalid")
        if record.get("external_anchor_status") != "NOT_PROVIDED":
            raise InlineRunError("run_external_anchor_is_untrusted")
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, dict):
            raise InlineRunError("run_artifacts_are_invalid")
        base_artifact_keys = {
            "before",
            "after",
            "invocation",
            "validation",
            "validator_stdout",
            "validator_stderr",
            "evidence_manifest",
        }
        expected_artifact_keys = base_artifact_keys | (
            {"template_field_edit_scope"} if current_schema else set()
        )
        if set(artifacts) != expected_artifact_keys:
            raise InlineRunError("run_artifact_keys_are_invalid")
        loaded: dict[str, bytes] = {}
        for label in (
            "before",
            "after",
            "invocation",
            "validation",
            "validator_stdout",
            "validator_stderr",
        ):
            item = artifacts.get(label)
            if not isinstance(item, dict):
                raise InlineRunError(f"artifact_record_missing:{label}")
            path = _artifact_path(run_dir, item.get("path"), label)
            raw = _read_regular_single_link(path, label)
            expected = _require_hex64(item.get("sha256"), label)
            if _sha256(raw) != expected:
                raise InlineRunError(f"artifact_sha256_mismatch:{label}")
            size_bytes = item.get("size_bytes")
            if (
                isinstance(size_bytes, bool)
                or not isinstance(size_bytes, int)
                or size_bytes != len(raw)
            ):
                raise InlineRunError(f"artifact_size_mismatch:{label}")
            loaded[label] = raw
        template_scope_raw: bytes | None = None
        if current_schema:
            scope_item = artifacts.get("template_field_edit_scope")
            if not isinstance(scope_item, dict):
                raise InlineRunError("artifact_record_missing:template_field_edit_scope")
            if scope_item.get("provided") is True:
                scope_path = _artifact_path(
                    run_dir,
                    scope_item.get("path"),
                    "template_field_edit_scope",
                )
                template_scope_raw = _read_regular_single_link(
                    scope_path, "template_field_edit_scope"
                )
                recorded_scope_sha256 = _require_hex64(
                    scope_item.get("sha256"), "template_field_edit_scope"
                )
                if _sha256(template_scope_raw) != recorded_scope_sha256:
                    raise InlineRunError(
                        "artifact_sha256_mismatch:template_field_edit_scope"
                    )
                if scope_item.get("size_bytes") != len(template_scope_raw):
                    raise InlineRunError(
                        "artifact_size_mismatch:template_field_edit_scope"
                    )
                expected_scope = _template_scope_descriptor(
                    template_scope_raw,
                    before_sha256=artifacts["before"]["sha256"],
                    artifact_path=scope_item.get("path"),
                )
            elif scope_item.get("provided") is False:
                expected_scope = _template_scope_descriptor(
                    None,
                    before_sha256=artifacts["before"]["sha256"],
                    artifact_path=None,
                )
            else:
                raise InlineRunError("template_field_edit_scope_provided_is_invalid")
            if scope_item != expected_scope:
                raise InlineRunError("template_field_edit_scope_record_mismatch")
            template_scope = expected_scope
        else:
            template_scope = _template_scope_descriptor(
                None,
                before_sha256=artifacts["before"]["sha256"],
                artifact_path=None,
            )
        validation = _load_json_bytes(loaded["validation"], "validation")
        if not isinstance(validation, dict):
            raise InlineRunError("validation_is_not_an_object")
        if validation.get("mechanical_validation_status") != record.get(
            "mechanical_validation_status"
        ):
            raise InlineRunError("mechanical_status_record_mismatch")
        if validation.get("delivery_gate_status") != record.get("delivery_gate_status"):
            raise InlineRunError("delivery_status_record_mismatch")
        if validation.get("exit_code") != record.get("exit_code"):
            raise InlineRunError("delivery_exit_code_record_mismatch")
        process_exit_code = record.get("validator_process_exit_code")
        execution_status = record.get("execution_status")
        if execution_status == "VALIDATED":
            if isinstance(process_exit_code, bool) or process_exit_code not in {0, 1, 2}:
                raise InlineRunError("validator_process_exit_code_record_is_invalid")
            _validate_payload(
                validation,
                process_exit_code=process_exit_code,
                before_sha256=artifacts["before"]["sha256"],
                after_sha256=artifacts["after"]["sha256"],
                mode=str(record.get("mode")),
                scene=str(record.get("scene")),
                template_scope=template_scope,
            )
        elif execution_status not in {"NOT_RUN", "VALIDATOR_EVIDENCE_INVALID"}:
            raise InlineRunError("execution_status_is_invalid")
        if record.get("diagnostics") != _summarize_validation(validation):
            raise InlineRunError("validation_diagnostics_record_mismatch")
        invocation = _load_json_bytes(loaded["invocation"], "invocation")
        expected_invocation_schema = (
            INVOCATION_SCHEMA if current_schema else LEGACY_INVOCATION_SCHEMA
        )
        if (
            not isinstance(invocation, dict)
            or invocation.get("schema_version") != expected_invocation_schema
        ):
            raise InlineRunError("invocation_schema_is_invalid")
        base_invocation_keys = {
            "schema_version",
            "source_kind",
            "mode",
            "scene",
            "document_format",
            "visible_output",
            "strict_speech_acts",
            "fragment",
            "keep_reasons",
            "protected_terms",
            "before_sha256",
            "after_sha256",
        }
        expected_invocation_keys = base_invocation_keys | (
            {"template_field_edit_scope"} if current_schema else set()
        )
        if set(invocation) != expected_invocation_keys:
            raise InlineRunError("invocation_keys_are_invalid")
        invocation_fields = {
            "mode": record.get("mode"),
            "scene": record.get("scene"),
            "document_format": record.get("document_format"),
            "visible_output": record.get("visible_output"),
            "before_sha256": artifacts["before"]["sha256"],
            "after_sha256": artifacts["after"]["sha256"],
        }
        for key, expected in invocation_fields.items():
            if invocation.get(key) != expected:
                raise InlineRunError(f"invocation_record_mismatch:{key}")
        if current_schema:
            if invocation.get("template_field_edit_scope") != template_scope:
                raise InlineRunError("invocation_template_field_scope_mismatch")
        evidence_manifest = artifacts.get("evidence_manifest")
        if not isinstance(evidence_manifest, dict):
            raise InlineRunError("evidence_manifest_record_missing")
        evidence_required = execution_status == "VALIDATED"
        if evidence_manifest.get("required") is not evidence_required:
            raise InlineRunError("evidence_manifest_requirement_mismatch")
        if evidence_required:
            manifest_path = _artifact_path(
                run_dir, evidence_manifest.get("path"), "evidence_manifest"
            )
            manifest_raw = _read_regular_single_link(
                manifest_path, "evidence_manifest"
            )
            expected_manifest_sha = _require_hex64(
                evidence_manifest.get("sha256"), "evidence_manifest"
            )
            if _sha256(manifest_raw) != expected_manifest_sha:
                raise InlineRunError("artifact_sha256_mismatch:evidence_manifest")
            if evidence_manifest.get("size_bytes") != len(manifest_raw):
                raise InlineRunError("artifact_size_mismatch:evidence_manifest")
            manifest_payload = _load_json_bytes(manifest_raw, "evidence_manifest")
            _validate_evidence_manifest(
                manifest_payload,
                evidence_dir=manifest_path.parent,
                before_raw=loaded["before"],
                after_raw=loaded["after"],
                validator_stdout=loaded["validator_stdout"],
                validator_stderr=loaded["validator_stderr"],
                mode=str(record.get("mode")),
                scene=str(record.get("scene")),
                validation=validation,
                template_scope_raw=template_scope_raw,
            )
        expected_emission_allowed = (
            execution_status == "VALIDATED"
            and validation.get("mechanical_validation_status") == "PASS"
            and validation.get("delivery_gate_status") in {"PASS", "REVIEW"}
        )
        if record.get("body_emission_allowed") is not expected_emission_allowed:
            raise InlineRunError("body_emission_permission_mismatch")
        if record.get("completion_claim_allowed") is not False:
            raise InlineRunError("completion_claim_permission_mismatch")
        response_contract = record.get("response_contract")
        expected_response_contract = {
            "body_source": artifacts["after"].get("path"),
            "body_must_be_emitted_verbatim": True,
            "body_only_hides_audit_display_not_audit_execution": True,
            "any_post_validation_mutation_requires_rerun": True,
            "stdout_byte_identity_scope": "LOCAL_PROCESS_STDOUT_ONLY",
            "chat_transport_byte_identity_status": "NOT_EVALUATED",
            "terminal_line_ending_is_candidate_content": loaded["after"].endswith(
                (b"\n", b"\r")
            ),
        }
        if response_contract != expected_response_contract:
            raise InlineRunError("response_contract_mismatch")
        if not expected_emission_allowed:
            return (
                {
                    "schema_version": VERIFY_SCHEMA,
                    "status": "REVIEW",
                    "exit_code": 2,
                    "run_id": run_dir.name,
                    "delivery_gate_status": record.get("delivery_gate_status"),
                    "mechanical_validation_status": record.get(
                        "mechanical_validation_status"
                    ),
                    "body_emission_allowed": False,
                    "diagnostics": record.get("diagnostics"),
                    "chat_transport_byte_identity_status": "NOT_EVALUATED",
                    "reason": "validated_candidate_is_not_mechanically_clear",
                },
                None,
            )
        return (
            {
                "schema_version": VERIFY_SCHEMA,
                "status": "PASS",
                "exit_code": int(record["exit_code"]),
                "run_id": run_dir.name,
                "delivery_gate_status": record["delivery_gate_status"],
                "mechanical_validation_status": record["mechanical_validation_status"],
                "body_emission_allowed": True,
                "after_sha256": artifacts["after"]["sha256"],
                "body_size_bytes": len(loaded["after"]),
                "body_must_be_emitted_verbatim": True,
                "stdout_byte_identity_scope": "LOCAL_PROCESS_STDOUT_ONLY",
                "chat_transport_byte_identity_status": "NOT_EVALUATED",
                "terminal_line_ending_is_candidate_content": loaded["after"].endswith(
                    (b"\n", b"\r")
                ),
            },
            loaded["after"],
        )
    except (OSError, InlineRunError) as error:
        return (
            {
                "schema_version": VERIFY_SCHEMA,
                "status": "FAIL",
                "exit_code": 1,
                "delivery_gate_status": "FAIL",
                "mechanical_validation_status": "FAIL",
                "body_emission_allowed": False,
                "reason": str(error),
            },
            None,
        )


def attest_visible_body(run_dir: Path, visible_body_path: Path) -> dict[str, Any]:
    """Compare caller-supplied response bytes with the frozen candidate body."""

    verification, expected = verify_run(run_dir)
    candidate_exit_code = verification.get("exit_code")
    base = {
        "schema_version": VISIBLE_ATTESTATION_SCHEMA,
        "attestation_scope": "CALLER_SUPPLIED_RESPONSE_BYTES_ONLY",
        "run_id": verification.get("run_id"),
        "candidate_delivery_gate_status": verification.get(
            "delivery_gate_status", "FAIL"
        ),
        "candidate_delivery_gate_exit_code": candidate_exit_code,
        "candidate_mechanical_validation_status": verification.get(
            "mechanical_validation_status", "FAIL"
        ),
        "candidate_completion_claim_allowed": False,
        "chat_transport_byte_identity_status": "NOT_EVALUATED",
        "ui_rendering_status": "NOT_EVALUATED",
    }
    if expected is None:
        status = str(verification.get("status", "FAIL"))
        if status not in {"FAIL", "REVIEW"}:
            status = "FAIL"
        exit_code = 2 if status == "REVIEW" else 1
        return {
            **base,
            "status": status,
            "exit_code": exit_code,
            "attestation_status": status,
            "byte_identity": False,
            "reason": "candidate_body_is_not_emittable",
            "verification_reason": verification.get("reason"),
        }

    try:
        observed = _read_stable(visible_body_path, "caller_supplied_visible_body")
    except InlineRunError as error:
        return {
            **base,
            "status": "FAIL",
            "exit_code": 1,
            "attestation_status": "FAIL",
            "byte_identity": False,
            "expected_sha256": _sha256(expected),
            "expected_size_bytes": len(expected),
            "reason": str(error),
        }

    expected_sha256 = _sha256(expected)
    observed_sha256 = _sha256(observed)
    common = {
        **base,
        "expected_sha256": expected_sha256,
        "expected_size_bytes": len(expected),
        "observed_sha256": observed_sha256,
        "observed_size_bytes": len(observed),
        "terminal_line_ending_matches": observed.endswith((b"\n", b"\r"))
        == expected.endswith((b"\n", b"\r")),
    }
    if observed != expected:
        return {
            **common,
            "status": "FAIL",
            "exit_code": 1,
            "attestation_status": "FAIL",
            "byte_identity": False,
            "reason": "caller_supplied_response_bytes_mismatch",
        }
    return {
        **common,
        "status": "PASS",
        "exit_code": 0,
        "attestation_status": "PASS",
        "byte_identity": True,
        "reason": None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="snapshot and validate an inline candidate")
    run_parser.add_argument("before", type=Path)
    run_parser.add_argument("after", type=Path)
    run_parser.add_argument("--output-root", type=Path, default=_default_output_root())
    run_parser.add_argument("--mode", type=str.upper, choices=VALID_MODES, default="REWRITE")
    run_parser.add_argument("--scene", type=str.upper, choices=VALID_SCENES, default="AUTO")
    run_parser.add_argument(
        "--document-format", choices=VALID_DOCUMENT_FORMATS, required=True
    )
    run_parser.add_argument(
        "--visible-output",
        type=str.upper,
        choices=VALID_VISIBLE_OUTPUTS,
        default="BODY_WITH_SUMMARY",
    )
    run_parser.add_argument("--keep-reason", action="append", default=[])
    run_parser.add_argument("--term", action="append", default=[])
    run_parser.add_argument("--strict-speech-acts", action="store_true")
    run_parser.add_argument("--fragment", action="store_true")
    run_parser.add_argument(
        "--template-field-edit-scope",
        type=Path,
        help=(
            "Bind exact template-field payload edits to a source-bound "
            "humanize-template-field-edit-scope/v1 artifact. REWRITE only."
        ),
    )
    emit_parser = subparsers.add_parser(
        "emit", help="recheck the frozen run and emit JSON or the exact candidate body"
    )
    emit_parser.add_argument("run_dir", type=Path)
    emit_parser.add_argument("--format", choices=("json", "body"), default="json")
    attest_parser = subparsers.add_parser(
        "attest",
        help="compare a caller-supplied response file with the frozen candidate body",
    )
    attest_parser.add_argument("run_dir", type=Path)
    attest_parser.add_argument("visible_body", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "run":
        try:
            record, run_dir = run_inline(
                args.before,
                args.after,
                output_root=args.output_root,
                mode=args.mode,
                scene=args.scene,
                document_format=args.document_format,
                visible_output=args.visible_output,
                keep_reasons=args.keep_reason,
                protected_terms=args.term,
                strict_speech_acts=args.strict_speech_acts,
                fragment=args.fragment,
                template_field_edit_scope_path=args.template_field_edit_scope,
            )
        except (OSError, InlineRunError) as error:
            payload = _integrity_failure(str(error))
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 1
        response = dict(record)
        response["run_dir"] = str(run_dir)
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
        return int(record["exit_code"])

    if args.command == "attest":
        attestation = attest_visible_body(args.run_dir, args.visible_body)
        print(json.dumps(attestation, ensure_ascii=False, sort_keys=True))
        return int(attestation["exit_code"])

    verification, body = verify_run(args.run_dir)
    if args.format == "body":
        if body is None:
            print(json.dumps(verification, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        else:
            sys.stdout.buffer.write(body)
            sys.stdout.buffer.flush()
    else:
        print(json.dumps(verification, ensure_ascii=False, sort_keys=True))
    return int(verification["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
