#!/usr/bin/env python3
"""Build a source-bound, non-overlapping short Humanize PATCH bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from copy import deepcopy
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import humanize_short_patch_coverage as coverage_layer  # noqa: E402


SELECTION_SCHEMA = "humanize-short-patch-selection/v1"
SELECTION_SCHEMA_V2 = "humanize-short-patch-selection/v2"
BUNDLE_SCHEMA = "humanize-short-patch/v1"
BUNDLE_SCHEMA_V2 = "humanize-short-patch/v2"
BUNDLE_SCHEMA_V3 = "humanize-short-patch/v3"
AMENDMENT_LINEAGE_SCHEMA = "humanize-short-patch-amendment-lineage/v1"
MAX_AMENDMENT_DEPTH = 8
OFFSET_UNIT = "UTF8_BYTES"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = 32
MAX_HUNKS = 1000
# A short PATCH hunk is a local sentence candidate, not a paragraph-sized
# container that can hide an unresolved claim.  The scaffold uses the same
# sentence bound; direct callers must obey it too.
MAX_REWRITE_HUNK_BYTES = 1200
REWRITE_SENTENCE_TERMINATORS = frozenset("。！？!?")
REWRITE_TRAILING_CLOSERS = frozenset("\"'”’》〉】〕）)]}")
HUNK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_DECISIONS = {"DELETE_STYLE_SHELL", "REWRITE", "UNRESOLVED"}
ALLOWED_REQUESTED_OUTPUTS = {"CLEAN", "PATCH"}
ALLOWED_SCENES = {"AUTO", "GENERAL", "COURSE", "MODELING", "RESEARCH"}
ALLOWED_INTENSITIES = {"LIGHT", "BALANCED"}
SELECTION_FIELDS = {
    "schema_version",
    "requested_output",
    "mode",
    "scene",
    "intensity",
    "protected_terms",
    "hunks",
}
SELECTION_FIELDS_V2 = SELECTION_FIELDS | {"coverage"}
SELECTION_HUNK_FIELDS = {
    "hunk_id",
    "decision",
    "source_text",
    "start_byte",
    "replacement",
    "reason",
}
BUNDLE_FIELDS = {
    "schema_version",
    "source_sha256",
    "source_size_bytes",
    "source_encoding",
    "offset_unit",
    "selection_spec_sha256",
    "requested_output",
    "effective_output",
    "mode",
    "scene",
    "intensity",
    "protected_terms",
    "patch_hunks_source_partition",
    "unlisted_source_policy",
    "semantic_judgment",
    "completion_claim_allowed",
    "hunks",
    "bundle_sha256",
}
BUNDLE_FIELDS_V2 = BUNDLE_FIELDS | {"document_format", "coverage"}
BUNDLE_FIELDS_V3 = BUNDLE_FIELDS_V2 | {"amendment"}
BUNDLE_HUNK_FIELDS = {
    "hunk_id",
    "decision",
    "start_byte",
    "end_byte",
    "source_text",
    "source_text_sha256",
    "replacement",
    "replacement_sha256",
    "reason",
}
AMENDMENT_FIELDS = {
    "schema_version",
    "integrity_scope",
    "parent_bundle",
    "parent_manifest_sha256",
    "parent_candidate_sha256",
    "amendment_spec_sha256",
    "amendment_depth",
    "changed_hunks",
    "completion_claim_allowed",
    "humanize_quality_claim_allowed",
    "amendment_sha256",
}
AMENDMENT_CHANGE_FIELDS = {
    "hunk_id",
    "before_hunk_sha256",
    "after_hunk_sha256",
}
GENERIC_REASONS = {
    "todo",
    "待定",
    "保持原样",
    "无需修改",
    "已经自然",
    "没有问题",
}
BIDI_CONTROLS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


class ShortPatchError(ValueError):
    """Raised when a short PATCH cannot be bound without ambiguity."""


def _validate_rewrite_scope(
    decision: str, source_text: str, label: str
) -> None:
    """Keep a direct REWRITE hunk inside one local sentence boundary.

    The scaffold already suppresses sentence suggestions above this bound, but
    hand-authored v1 selections bypass the scaffold.  Rejecting paragraph-sized
    or multi-sentence rewrites prevents a caller from swallowing a separate
    unresolved claim inside an apparently successful hunk.
    """
    if decision != "REWRITE":
        return
    encoded_length = len(source_text.encode("utf-8"))
    if encoded_length > MAX_REWRITE_HUNK_BYTES:
        raise ShortPatchError(
            f"{label} REWRITE span exceeds the {MAX_REWRITE_HUNK_BYTES}-byte "
            "local sentence limit; use long-document PATCH instead"
        )
    if "\n" in source_text or "\r" in source_text:
        raise ShortPatchError(
            f"{label} REWRITE span crosses a line boundary; split it into "
            "local sentence hunks"
        )
    terminator_offsets = [
        index
        for index, character in enumerate(source_text)
        if character in REWRITE_SENTENCE_TERMINATORS
    ]
    trailing_text = (
        source_text[terminator_offsets[0] + 1 :]
        if len(terminator_offsets) == 1
        else ""
    )
    crosses_sentence_boundary = bool(
        len(terminator_offsets) > 1
        or (
            len(terminator_offsets) == 1
            and any(
                not character.isspace() and character not in REWRITE_TRAILING_CLOSERS
                for character in trailing_text
            )
        )
    )
    if crosses_sentence_boundary:
        raise ShortPatchError(
            f"{label} REWRITE span crosses multiple sentence boundaries; "
            "declare unresolved claims as separate hunks"
        )


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ShortPatchError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> Any:
    raise ShortPatchError(f"JSON floating-point number is forbidden: {value}")


def _reject_constant(value: str) -> Any:
    raise ShortPatchError(f"JSON non-finite number is forbidden: {value}")


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ShortPatchError("JSON nesting is too deep")
    if isinstance(value, dict):
        for child in value.values():
            _check_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_depth(child, depth + 1)


def strict_json_bytes(raw: bytes, label: str) -> Any:
    if len(raw) > MAX_JSON_BYTES:
        raise ShortPatchError(f"{label} exceeds {MAX_JSON_BYTES} bytes")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise ShortPatchError(f"{label} is not strict UTF-8 JSON") from error
    if "\ufffd" in text:
        raise ShortPatchError(f"{label} contains a Unicode replacement character")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ShortPatchError(f"{label} is not valid JSON: {error}") from error
    _check_depth(value)
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ShortPatchError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_reparse_chain(path: Path, label: str) -> None:
    absolute = _absolute_without_resolving(path)
    parts = absolute.parts
    current = Path(parts[0])
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0) & reparse_flag
        ):
            raise ShortPatchError(f"{label} path contains a symlink or reparse point")


def safe_input_path(path: Path, label: str) -> Path:
    absolute = _absolute_without_resolving(path)
    _assert_no_reparse_chain(absolute, label)
    try:
        metadata = os.stat(absolute, follow_symlinks=False)
    except OSError as error:
        raise ShortPatchError(f"{label} must be a regular non-symlink file") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise ShortPatchError(f"{label} must be a regular non-symlink file")
    if metadata.st_nlink != 1:
        raise ShortPatchError(f"{label} must not be a hardlink")
    return absolute


def safe_output_path(path: Path, label: str = "output") -> Path:
    absolute = _absolute_without_resolving(path)
    _assert_no_reparse_chain(absolute.parent, label)
    if absolute.exists() or absolute.is_symlink():
        raise ShortPatchError("output_exists")
    return absolute


def _regular_input(path: Path, label: str, limit: int | None = None) -> bytes:
    path = safe_input_path(path, label)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ShortPatchError(f"{label} is unreadable: {type(error).__name__}") from error
    if limit is not None and len(raw) > limit:
        raise ShortPatchError(f"{label} exceeds {limit} bytes")
    return raw


def read_source(path: Path) -> bytes:
    raw = _regular_input(path, "source", MAX_SOURCE_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise ShortPatchError("source is not strict UTF-8") from error
    if "\ufffd" in text:
        raise ShortPatchError("source contains a Unicode replacement character")
    return raw


def _required_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        suffix = "a string" if allow_empty else "a non-empty string"
        raise ShortPatchError(f"{label} must be {suffix}")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ShortPatchError(f"{label} is not valid Unicode") from error
    return value


def _specific_reason(value: Any, label: str) -> str:
    reason = _required_string(value, label).strip()
    normalized = re.sub(r"[\s。！？!?.,，;；:：]+$", "", reason).strip().casefold()
    if normalized in GENERIC_REASONS:
        raise ShortPatchError(f"{label} is generic or unfinished")
    return reason


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ShortPatchError(f"{label} must be an integer >= {minimum}")
    return value


def _protected_terms(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 128:
        raise ShortPatchError(f"{label} must be an array with at most 128 entries")
    terms: list[str] = []
    seen: set[str] = set()
    for index, raw_term in enumerate(value):
        term = _required_string(raw_term, f"{label}[{index}]")
        if len(term) > 512 or any(character in term for character in ("\x00", "\r", "\n")):
            raise ShortPatchError(f"{label}[{index}] is invalid")
        if term in seen:
            raise ShortPatchError(f"{label} contains a duplicate term")
        seen.add(term)
        terms.append(term)
    return terms


def _validate_decision(
    decision: str,
    source_text: str,
    replacement: str,
    label: str,
) -> None:
    if decision not in ALLOWED_DECISIONS:
        raise ShortPatchError(f"{label}.decision is not supported")
    if decision == "DELETE_STYLE_SHELL" and replacement != "":
        raise ShortPatchError(f"{label} DELETE_STYLE_SHELL replacement must be empty")
    if decision == "UNRESOLVED" and replacement != source_text:
        raise ShortPatchError(f"{label} UNRESOLVED replacement must equal source_text")
    if decision == "REWRITE" and (not replacement or replacement == source_text):
        raise ShortPatchError(f"{label} REWRITE replacement must be non-empty and changed")


def _cluster_connector(character: str) -> bool:
    codepoint = ord(character)
    return (
        bool(unicodedata.combining(character))
        or character in {"\u200c", "\u200d"}
        or 0xFE00 <= codepoint <= 0xFE0F
        or 0xE0100 <= codepoint <= 0xE01EF
        or 0x1F3FB <= codepoint <= 0x1F3FF
    )


def _validate_source_boundaries(source: bytes, start: int, end: int, label: str) -> None:
    if (start > 0 and source[start - 1 : start + 1] == b"\r\n") or (
        end < len(source) and source[end - 1 : end + 1] == b"\r\n"
    ):
        raise ShortPatchError(f"{label} splits a CRLF sequence")
    left_start = source[:start].decode("utf-8")
    right_start = source[start:].decode("utf-8")
    left_end = source[:end].decode("utf-8")
    right_end = source[end:].decode("utf-8")
    if (
        (right_start and _cluster_connector(right_start[0]))
        or (left_start and left_start[-1] == "\u200d")
        or (right_end and _cluster_connector(right_end[0]))
        or (left_end and left_end[-1] == "\u200d")
    ):
        raise ShortPatchError(f"{label} splits a grapheme-like sequence")


def _validate_replacement_controls(source_text: str, replacement: str, label: str) -> None:
    source_counts = Counter(source_text)
    replacement_counts = Counter(replacement)
    for character, count in replacement_counts.items():
        if character == "\x00":
            raise ShortPatchError(f"{label} replacement contains NUL")
        if character in BIDI_CONTROLS and count > source_counts[character]:
            raise ShortPatchError(f"{label} replacement introduces a bidi control")
        if (
            unicodedata.category(character) == "Cf"
            and count > source_counts[character]
        ):
            raise ShortPatchError(f"{label} replacement introduces a format control")
        if (
            unicodedata.category(character) == "Cc"
            and character not in {"\t", "\r", "\n"}
            and count > source_counts[character]
        ):
            raise ShortPatchError(f"{label} replacement introduces a control character")


def _locate(source: bytes, source_text: str, requested_start: Any, label: str) -> tuple[int, int]:
    needle = source_text.encode("utf-8")
    if not needle:
        raise ShortPatchError(f"{label}.source_text must not be empty")
    if requested_start is None:
        start = source.find(needle)
        if start < 0:
            raise ShortPatchError(f"{label}.source_text is missing from source")
        positions = [start]
        cursor = start + 1
        while len(positions) <= 16:
            found = source.find(needle, cursor)
            if found < 0:
                break
            positions.append(found)
            cursor = found + 1
        if len(positions) > 1:
            shown = positions[:16]
            suffix = ", ..." if len(positions) > 16 else ""
            raise ShortPatchError(
                f"{label}.source_text is ambiguous; provide start_byte; "
                f"candidate_start_bytes={shown}{suffix}"
            )
    else:
        start = _integer(requested_start, f"{label}.start_byte")
        if source[start : start + len(needle)] != needle:
            raise ShortPatchError(f"{label}.start_byte does not match source_text")
    return start, start + len(needle)


def _bundle_hash(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("bundle_sha256", None)
    return sha256(canonical_json(unsigned))


def hunk_record_hash(hunk: Mapping[str, Any]) -> str:
    return sha256(canonical_json(dict(hunk)))


def _amendment_hash(payload: Mapping[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("amendment_sha256", None)
    return sha256(canonical_json(unsigned))


def _apply_bundle_bytes(source: bytes, bundle: Mapping[str, Any]) -> bytes:
    pieces: list[bytes] = []
    cursor = 0
    for hunk in bundle["hunks"]:
        start = int(hunk["start_byte"])
        end = int(hunk["end_byte"])
        pieces.append(source[cursor:start])
        pieces.append(str(hunk["replacement"]).encode("utf-8"))
        cursor = end
    pieces.append(source[cursor:])
    return b"".join(pieces)


def _coverage_spec_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    declarations = record.get("declarations")
    if not isinstance(declarations, dict):
        raise ShortPatchError("parent coverage declarations are missing")
    try:
        return {
            "source_kind": declarations["source_kind"],
            "lexical_keeps": [
                {
                    "signal_id": item["signal_id"],
                    "source_text": item["source_text"],
                    "start_byte": item["start_byte"],
                    "reason": item["reason"],
                }
                for item in declarations["lexical_keeps"]
            ],
            "selected_spans": [
                {
                    "selection_id": item["selection_id"],
                    "source_text": item["source_text"],
                    "start_byte": item["start_byte"],
                    "decision": item["decision"],
                    "hunk_id": item["hunk_id"],
                    "reason": item["reason"],
                }
                for item in declarations["selected_spans"]
            ],
            "explicit_conflicts": [
                dict(item) for item in declarations["explicit_conflicts"]
            ],
        }
    except (KeyError, TypeError) as error:
        raise ShortPatchError("parent coverage declarations are invalid") from error


def _normalized_amendment_changes(
    changes: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    entries: Sequence[Mapping[str, Any]]
    if isinstance(changes, Mapping):
        entries = [
            {"hunk_id": hunk_id, **dict(value)}
            for hunk_id, value in changes.items()
        ]
    else:
        entries = changes
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ShortPatchError(f"amendment change[{index}] must be an object")
        hunk_id = _required_string(entry.get("hunk_id"), f"amendment change[{index}].hunk_id")
        collision = hunk_id.casefold()
        if collision in {item.casefold() for item in normalized}:
            raise ShortPatchError("amendment changes contain a duplicate hunk_id")
        normalized[hunk_id] = {
            "decision": _required_string(
                entry.get("decision"), f"amendment change[{index}].decision"
            ),
            "replacement": _required_string(
                entry.get("replacement"),
                f"amendment change[{index}].replacement",
                allow_empty=True,
            ),
            "reason": _specific_reason(
                entry.get("reason"), f"amendment change[{index}].reason"
            ),
        }
    if not normalized:
        raise ShortPatchError("amendment changes must be non-empty")
    return normalized


def build_amended_bundle_payload(
    source: bytes,
    parent_bundle: Mapping[str, Any],
    amendment_raw: bytes,
    changes: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive a v3 bundle while preserving the parent's immutable topology."""
    parent = validate_bundle_payload(dict(parent_bundle), source)
    if parent["schema_version"] not in {BUNDLE_SCHEMA_V2, BUNDLE_SCHEMA_V3}:
        raise ShortPatchError("amendment parent must be coverage-aware v2 or v3")
    amendment_spec = strict_json_bytes(amendment_raw, "amendment authoring")
    if not isinstance(amendment_spec, dict):
        raise ShortPatchError("amendment authoring must be an object")
    base = amendment_spec.get("base")
    if not isinstance(base, dict):
        raise ShortPatchError("amendment authoring base is missing")
    parent_manifest_sha256 = base.get("manifest_sha256")
    parent_candidate_sha256 = base.get("candidate_sha256")
    for label, value in (
        ("parent_manifest_sha256", parent_manifest_sha256),
        ("parent_candidate_sha256", parent_candidate_sha256),
    ):
        if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
            raise ShortPatchError(f"{label} must be a lowercase SHA-256")
    actual_parent_candidate = sha256(_apply_bundle_bytes(source, parent))
    if parent_candidate_sha256 != actual_parent_candidate:
        raise ShortPatchError("parent_candidate_sha256 mismatch")
    normalized_changes = _normalized_amendment_changes(changes)
    parent_ids = {str(item["hunk_id"]): item for item in parent["hunks"]}
    for hunk_id in normalized_changes:
        if hunk_id not in parent_ids:
            if hunk_id.casefold() in {item.casefold() for item in parent_ids}:
                raise ShortPatchError("amendment hunk_id case does not match parent")
            raise ShortPatchError(f"unknown amendment hunk_id: {hunk_id}")
    selection_hunks: list[dict[str, Any]] = []
    for item in parent["hunks"]:
        hunk_id = str(item["hunk_id"])
        replacement = normalized_changes.get(hunk_id)
        selection_hunks.append(
            {
                "hunk_id": hunk_id,
                "decision": (
                    replacement["decision"] if replacement is not None else item["decision"]
                ),
                "source_text": item["source_text"],
                "start_byte": item["start_byte"],
                "replacement": (
                    replacement["replacement"]
                    if replacement is not None
                    else item["replacement"]
                ),
                "reason": (
                    replacement["reason"] if replacement is not None else item["reason"]
                ),
            }
        )
    selection = {
        "schema_version": SELECTION_SCHEMA_V2,
        "requested_output": parent["requested_output"],
        "mode": parent["mode"],
        "scene": parent["scene"],
        "intensity": parent["intensity"],
        "protected_terms": deepcopy(parent["protected_terms"]),
        "hunks": selection_hunks,
        "coverage": _coverage_spec_from_record(parent["coverage"]),
    }
    selection_raw = (
        json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    derived = _build_payload(
        source,
        selection_raw,
        selection,
        document_format=str(parent["document_format"]),
    )
    changed_records: list[dict[str, str]] = []
    for before_hunk, after_hunk in zip(parent["hunks"], derived["hunks"]):
        mutable_before = (
            before_hunk["decision"],
            before_hunk["replacement"],
            before_hunk["reason"],
        )
        mutable_after = (
            after_hunk["decision"],
            after_hunk["replacement"],
            after_hunk["reason"],
        )
        if mutable_before == mutable_after:
            continue
        changed_records.append(
            {
                "hunk_id": str(before_hunk["hunk_id"]),
                "before_hunk_sha256": hunk_record_hash(before_hunk),
                "after_hunk_sha256": hunk_record_hash(after_hunk),
            }
        )
    actual_changed = {item["hunk_id"] for item in changed_records}
    if actual_changed != set(normalized_changes):
        unchanged = sorted(set(normalized_changes) - actual_changed)
        raise ShortPatchError(
            "SELECTED_HUNK_NOT_CHANGED"
            + (f": {','.join(unchanged)}" if unchanged else "")
        )
    parent_depth = (
        int(parent["amendment"]["amendment_depth"])
        if parent["schema_version"] == BUNDLE_SCHEMA_V3
        else 0
    )
    amendment_depth = parent_depth + 1
    if amendment_depth > MAX_AMENDMENT_DEPTH:
        raise ShortPatchError("AMENDMENT_CHAIN_LIMIT_REQUIRES_NEW_AUTHORING_RUN")
    amendment: dict[str, Any] = {
        "schema_version": AMENDMENT_LINEAGE_SCHEMA,
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
        "parent_bundle": deepcopy(parent),
        "parent_manifest_sha256": parent_manifest_sha256,
        "parent_candidate_sha256": parent_candidate_sha256,
        "amendment_spec_sha256": sha256(amendment_raw),
        "amendment_depth": amendment_depth,
        "changed_hunks": changed_records,
        "completion_claim_allowed": False,
        "humanize_quality_claim_allowed": False,
        "amendment_sha256": "",
    }
    amendment["amendment_sha256"] = _amendment_hash(amendment)
    payload = dict(derived)
    payload["schema_version"] = BUNDLE_SCHEMA_V3
    payload["amendment"] = amendment
    payload["bundle_sha256"] = ""
    payload["bundle_sha256"] = _bundle_hash(payload)
    validate_bundle_payload(payload, source)
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_JSON_BYTES:
        raise ShortPatchError("AMENDMENT_CHAIN_LIMIT_REQUIRES_NEW_AUTHORING_RUN")
    return payload


def _validate_amendment_lineage(
    payload: Mapping[str, Any],
    source: bytes | None,
    *,
    require_current_coverage_policy: bool,
    lineage_depth: int,
) -> None:
    amendment = payload.get("amendment")
    if not isinstance(amendment, dict):
        raise ShortPatchError("bundle.amendment must be an object")
    _exact_fields(amendment, AMENDMENT_FIELDS, "bundle.amendment")
    if amendment.get("schema_version") != AMENDMENT_LINEAGE_SCHEMA:
        raise ShortPatchError("bundle.amendment schema_version is invalid")
    if amendment.get("integrity_scope") != "SELF_CONSISTENCY_ONLY":
        raise ShortPatchError("bundle.amendment integrity_scope is invalid")
    if amendment.get("completion_claim_allowed") is not False:
        raise ShortPatchError("bundle.amendment completion_claim_allowed must be false")
    if amendment.get("humanize_quality_claim_allowed") is not False:
        raise ShortPatchError("bundle.amendment humanize_quality_claim_allowed must be false")
    for field in (
        "parent_manifest_sha256",
        "parent_candidate_sha256",
        "amendment_spec_sha256",
        "amendment_sha256",
    ):
        value = amendment.get(field)
        if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
            raise ShortPatchError(f"bundle.amendment.{field} is invalid")
    if amendment.get("amendment_sha256") != _amendment_hash(amendment):
        raise ShortPatchError("bundle.amendment_sha256 mismatch")
    depth = _integer(
        amendment.get("amendment_depth"),
        "bundle.amendment.amendment_depth",
        minimum=1,
    )
    if depth > MAX_AMENDMENT_DEPTH or lineage_depth >= MAX_AMENDMENT_DEPTH:
        raise ShortPatchError("AMENDMENT_CHAIN_LIMIT_REQUIRES_NEW_AUTHORING_RUN")
    parent_raw = amendment.get("parent_bundle")
    if not isinstance(parent_raw, dict):
        raise ShortPatchError("bundle.amendment.parent_bundle must be an object")
    parent = validate_bundle_payload(
        parent_raw,
        source,
        require_current_coverage_policy=require_current_coverage_policy,
        _lineage_depth=lineage_depth + 1,
    )
    if parent["schema_version"] not in {BUNDLE_SCHEMA_V2, BUNDLE_SCHEMA_V3}:
        raise ShortPatchError("amendment parent must be coverage-aware v2 or v3")
    expected_depth = (
        int(parent["amendment"]["amendment_depth"]) + 1
        if parent["schema_version"] == BUNDLE_SCHEMA_V3
        else 1
    )
    if depth != expected_depth:
        raise ShortPatchError("bundle.amendment_depth does not extend the parent")
    immutable_fields = (
        "source_sha256",
        "source_size_bytes",
        "source_encoding",
        "offset_unit",
        "requested_output",
        "effective_output",
        "mode",
        "scene",
        "intensity",
        "protected_terms",
        "patch_hunks_source_partition",
        "unlisted_source_policy",
        "semantic_judgment",
        "completion_claim_allowed",
        "document_format",
    )
    for field in immutable_fields:
        if payload.get(field) != parent.get(field):
            raise ShortPatchError(f"amendment changed immutable bundle field: {field}")
    if payload["coverage"].get("declarations") != parent["coverage"].get("declarations"):
        raise ShortPatchError("amendment changed coverage declarations")
    parent_candidate = _apply_bundle_bytes(source, parent) if source is not None else None
    if (
        parent_candidate is not None
        and amendment["parent_candidate_sha256"] != sha256(parent_candidate)
    ):
        raise ShortPatchError("bundle.amendment parent_candidate_sha256 mismatch")
    parent_hunks = parent.get("hunks")
    child_hunks = payload.get("hunks")
    if not isinstance(parent_hunks, list) or not isinstance(child_hunks, list):
        raise ShortPatchError("amendment hunk topology is invalid")
    if len(parent_hunks) != len(child_hunks):
        raise ShortPatchError("amendment changed hunk count")
    actual_changes: list[dict[str, str]] = []
    topology_fields = (
        "hunk_id",
        "start_byte",
        "end_byte",
        "source_text",
        "source_text_sha256",
    )
    for before_hunk, after_hunk in zip(parent_hunks, child_hunks):
        if any(before_hunk.get(field) != after_hunk.get(field) for field in topology_fields):
            raise ShortPatchError("amendment changed hunk topology or source binding")
        mutable_before = (
            before_hunk.get("decision"),
            before_hunk.get("replacement"),
            before_hunk.get("reason"),
        )
        mutable_after = (
            after_hunk.get("decision"),
            after_hunk.get("replacement"),
            after_hunk.get("reason"),
        )
        if mutable_before == mutable_after:
            if before_hunk != after_hunk:
                raise ShortPatchError("amendment changed an undeclared derived hunk field")
            continue
        actual_changes.append(
            {
                "hunk_id": str(before_hunk["hunk_id"]),
                "before_hunk_sha256": hunk_record_hash(before_hunk),
                "after_hunk_sha256": hunk_record_hash(after_hunk),
            }
        )
    declared = amendment.get("changed_hunks")
    if not isinstance(declared, list) or not declared:
        raise ShortPatchError("bundle.amendment.changed_hunks must be non-empty")
    seen: set[str] = set()
    normalized_declared: list[dict[str, str]] = []
    for index, item in enumerate(declared):
        label = f"bundle.amendment.changed_hunks[{index}]"
        if not isinstance(item, dict):
            raise ShortPatchError(f"{label} must be an object")
        _exact_fields(item, AMENDMENT_CHANGE_FIELDS, label)
        hunk_id = _required_string(item.get("hunk_id"), f"{label}.hunk_id")
        if hunk_id.casefold() in seen:
            raise ShortPatchError("bundle.amendment.changed_hunks contains a duplicate hunk_id")
        seen.add(hunk_id.casefold())
        for field in ("before_hunk_sha256", "after_hunk_sha256"):
            value = item.get(field)
            if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
                raise ShortPatchError(f"{label}.{field} is invalid")
        normalized_declared.append(dict(item))
    if normalized_declared != actual_changes:
        raise ShortPatchError("bundle.amendment changed_hunks does not match actual changes")


def validate_bundle_payload(
    payload: Any,
    source: bytes | None = None,
    *,
    require_current_coverage_policy: bool = True,
    _lineage_depth: int = 0,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ShortPatchError("bundle must be a JSON object")
    schema = payload.get("schema_version")
    if schema == BUNDLE_SCHEMA:
        _exact_fields(payload, BUNDLE_FIELDS, "bundle")
    elif schema == BUNDLE_SCHEMA_V2:
        _exact_fields(payload, BUNDLE_FIELDS_V2, "bundle")
        if payload.get("document_format") not in {"markdown", "tex"}:
            raise ShortPatchError("bundle.document_format is invalid")
        if not isinstance(payload.get("coverage"), dict):
            raise ShortPatchError("bundle.coverage must be an object")
    elif schema == BUNDLE_SCHEMA_V3:
        _exact_fields(payload, BUNDLE_FIELDS_V3, "bundle")
        if payload.get("document_format") not in {"markdown", "tex"}:
            raise ShortPatchError("bundle.document_format is invalid")
        if not isinstance(payload.get("coverage"), dict):
            raise ShortPatchError("bundle.coverage must be an object")
    else:
        raise ShortPatchError(
            "bundle.schema_version must be "
            f"{BUNDLE_SCHEMA}, {BUNDLE_SCHEMA_V2}, or {BUNDLE_SCHEMA_V3}"
        )
    if not isinstance(payload.get("source_sha256"), str) or not HEX64_RE.fullmatch(payload["source_sha256"]):
        raise ShortPatchError("bundle.source_sha256 must be a lowercase SHA-256")
    _integer(payload.get("source_size_bytes"), "bundle.source_size_bytes")
    if payload.get("source_encoding") != "utf-8":
        raise ShortPatchError("bundle.source_encoding must be utf-8")
    if payload.get("offset_unit") != OFFSET_UNIT:
        raise ShortPatchError(f"bundle.offset_unit must be {OFFSET_UNIT}")
    if not isinstance(payload.get("selection_spec_sha256"), str) or not HEX64_RE.fullmatch(payload["selection_spec_sha256"]):
        raise ShortPatchError("bundle.selection_spec_sha256 must be a lowercase SHA-256")
    if payload.get("requested_output") not in ALLOWED_REQUESTED_OUTPUTS:
        raise ShortPatchError("bundle.requested_output is invalid")
    if payload.get("effective_output") != "PATCH":
        raise ShortPatchError("bundle.effective_output must be PATCH")
    if payload.get("mode") != "REWRITE":
        raise ShortPatchError("bundle.mode must be REWRITE")
    if payload.get("scene") not in ALLOWED_SCENES:
        raise ShortPatchError("bundle.scene is invalid")
    if payload.get("intensity") not in ALLOWED_INTENSITIES:
        raise ShortPatchError("bundle.intensity is invalid")
    _protected_terms(payload.get("protected_terms"), "bundle.protected_terms")
    if payload.get("patch_hunks_source_partition") != "NON_OVERLAPPING":
        raise ShortPatchError("bundle patch partition must be NON_OVERLAPPING")
    if payload.get("unlisted_source_policy") != "COPY_EXACT":
        raise ShortPatchError("bundle unlisted source policy must be COPY_EXACT")
    if payload.get("semantic_judgment") != "NOT_EVALUATED":
        raise ShortPatchError("bundle semantic_judgment must be NOT_EVALUATED")
    if payload.get("completion_claim_allowed") is not False:
        raise ShortPatchError("bundle completion_claim_allowed must be false")
    hunks = payload.get("hunks")
    if not isinstance(hunks, list) or not hunks or len(hunks) > MAX_HUNKS:
        raise ShortPatchError("bundle.hunks must be a non-empty bounded array")
    seen_ids: set[str] = set()
    previous_start = -1
    previous_end = 0
    for index, raw_hunk in enumerate(hunks):
        label = f"bundle.hunks[{index}]"
        if not isinstance(raw_hunk, dict):
            raise ShortPatchError(f"{label} must be an object")
        _exact_fields(raw_hunk, BUNDLE_HUNK_FIELDS, label)
        hunk_id = _required_string(raw_hunk.get("hunk_id"), f"{label}.hunk_id")
        if not HUNK_ID_RE.fullmatch(hunk_id):
            raise ShortPatchError(f"{label}.hunk_id is invalid")
        collision_key = hunk_id.casefold()
        if collision_key in seen_ids:
            raise ShortPatchError(f"duplicate hunk_id: {hunk_id}")
        seen_ids.add(collision_key)
        start = _integer(raw_hunk.get("start_byte"), f"{label}.start_byte")
        end = _integer(raw_hunk.get("end_byte"), f"{label}.end_byte", minimum=1)
        if end <= start:
            raise ShortPatchError(f"{label} has an empty or reversed source span")
        if start < previous_start:
            raise ShortPatchError(f"{label} is out of source order")
        if start < previous_end:
            raise ShortPatchError(f"{label} overlaps a previous hunk")
        previous_start, previous_end = start, end
        source_text = _required_string(raw_hunk.get("source_text"), f"{label}.source_text")
        replacement = _required_string(raw_hunk.get("replacement"), f"{label}.replacement", allow_empty=True)
        decision = _required_string(raw_hunk.get("decision"), f"{label}.decision")
        _specific_reason(raw_hunk.get("reason"), f"{label}.reason")
        _validate_decision(decision, source_text, replacement, label)
        _validate_rewrite_scope(decision, source_text, label)
        _validate_replacement_controls(source_text, replacement, label)
        source_text_raw = source_text.encode("utf-8")
        replacement_raw = replacement.encode("utf-8")
        if end - start != len(source_text_raw):
            raise ShortPatchError(f"{label} byte span does not match source_text")
        if raw_hunk.get("source_text_sha256") != sha256(source_text_raw):
            raise ShortPatchError(f"{label}.source_text_sha256 mismatch")
        if raw_hunk.get("replacement_sha256") != sha256(replacement_raw):
            raise ShortPatchError(f"{label}.replacement_sha256 mismatch")
        if source is not None:
            if end > len(source) or source[start:end] != source_text_raw:
                raise ShortPatchError(f"{label} does not match current source bytes")
            _validate_source_boundaries(source, start, end, label)
    if payload.get("bundle_sha256") != _bundle_hash(payload):
        raise ShortPatchError("bundle_sha256 mismatch")
    if source is not None:
        if payload["source_sha256"] != sha256(source):
            raise ShortPatchError("source_sha256 mismatch")
        if payload["source_size_bytes"] != len(source):
            raise ShortPatchError("source_size_bytes mismatch")
        if schema in {BUNDLE_SCHEMA_V2, BUNDLE_SCHEMA_V3}:
            try:
                coverage_layer.validate_record_integrity(
                    source,
                    payload["coverage"],
                    hunks=hunks,
                )
                replay_status = "PASS"
                if require_current_coverage_policy:
                    _replayed, replay_status = coverage_layer.replay_coverage(
                        source,
                        hunks=hunks,
                        recorded=payload["coverage"],
                    )
            except coverage_layer.CoverageError as error:
                raise ShortPatchError(str(error)) from error
            if replay_status != "PASS":
                raise ShortPatchError("COVERAGE_POLICY_DRIFT")
    if schema == BUNDLE_SCHEMA_V3:
        _validate_amendment_lineage(
            payload,
            source,
            require_current_coverage_policy=require_current_coverage_policy,
            lineage_depth=_lineage_depth,
        )
    return dict(payload)


def _build_payload(
    source: bytes,
    spec_raw: bytes,
    spec: Any,
    *,
    document_format: str,
) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ShortPatchError("selection spec must be a JSON object")
    selection_schema = spec.get("schema_version")
    if selection_schema == SELECTION_SCHEMA:
        _exact_fields(spec, SELECTION_FIELDS, "selection spec")
    elif selection_schema == SELECTION_SCHEMA_V2:
        _exact_fields(spec, SELECTION_FIELDS_V2, "selection spec")
        if not isinstance(spec.get("coverage"), dict):
            raise ShortPatchError("selection spec.coverage must be an object")
    else:
        raise ShortPatchError(
            f"selection spec schema_version must be {SELECTION_SCHEMA} or {SELECTION_SCHEMA_V2}"
        )
    requested_output = spec.get("requested_output")
    if requested_output not in ALLOWED_REQUESTED_OUTPUTS:
        raise ShortPatchError("selection spec requested_output must be CLEAN or PATCH")
    if spec.get("mode") != "REWRITE":
        raise ShortPatchError("selection spec mode must be REWRITE")
    scene = spec.get("scene")
    if scene not in ALLOWED_SCENES:
        raise ShortPatchError("selection spec scene is invalid")
    intensity = spec.get("intensity")
    if intensity not in ALLOWED_INTENSITIES:
        raise ShortPatchError("selection spec intensity must be LIGHT or BALANCED")
    protected_terms = _protected_terms(
        spec.get("protected_terms"), "selection spec.protected_terms"
    )
    raw_hunks = spec.get("hunks")
    if not isinstance(raw_hunks, list) or not raw_hunks or len(raw_hunks) > MAX_HUNKS:
        raise ShortPatchError("selection spec hunks must be a non-empty bounded array")
    hunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    previous_start = -1
    previous_end = 0
    for index, raw_hunk in enumerate(raw_hunks):
        label = f"selection spec.hunks[{index}]"
        if not isinstance(raw_hunk, dict):
            raise ShortPatchError(f"{label} must be an object")
        _exact_fields(raw_hunk, SELECTION_HUNK_FIELDS, label)
        hunk_id = _required_string(raw_hunk.get("hunk_id"), f"{label}.hunk_id")
        if not HUNK_ID_RE.fullmatch(hunk_id):
            raise ShortPatchError(f"{label}.hunk_id is invalid")
        collision_key = hunk_id.casefold()
        if collision_key in seen_ids:
            raise ShortPatchError(f"duplicate hunk_id: {hunk_id}")
        seen_ids.add(collision_key)
        decision = _required_string(raw_hunk.get("decision"), f"{label}.decision")
        source_text = _required_string(raw_hunk.get("source_text"), f"{label}.source_text")
        replacement = _required_string(raw_hunk.get("replacement"), f"{label}.replacement", allow_empty=True)
        reason = _specific_reason(raw_hunk.get("reason"), f"{label}.reason")
        _validate_decision(decision, source_text, replacement, label)
        _validate_rewrite_scope(decision, source_text, label)
        start, end = _locate(source, source_text, raw_hunk.get("start_byte"), label)
        _validate_replacement_controls(source_text, replacement, label)
        _validate_source_boundaries(source, start, end, label)
        if start < previous_start:
            raise ShortPatchError(f"{label} is out of source order")
        if start < previous_end:
            raise ShortPatchError(f"{label} overlaps a previous hunk")
        previous_start, previous_end = start, end
        source_text_raw = source_text.encode("utf-8")
        replacement_raw = replacement.encode("utf-8")
        hunks.append(
            {
                "hunk_id": hunk_id,
                "decision": decision,
                "start_byte": start,
                "end_byte": end,
                "source_text": source_text,
                "source_text_sha256": sha256(source_text_raw),
                "replacement": replacement,
                "replacement_sha256": sha256(replacement_raw),
                "reason": reason,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": (
            BUNDLE_SCHEMA_V2 if selection_schema == SELECTION_SCHEMA_V2 else BUNDLE_SCHEMA
        ),
        "source_sha256": sha256(source),
        "source_size_bytes": len(source),
        "source_encoding": "utf-8",
        "offset_unit": OFFSET_UNIT,
        "selection_spec_sha256": sha256(spec_raw),
        "requested_output": requested_output,
        "effective_output": "PATCH",
        "mode": "REWRITE",
        "scene": scene,
        "intensity": intensity,
        "protected_terms": protected_terms,
        "patch_hunks_source_partition": "NON_OVERLAPPING",
        "unlisted_source_policy": "COPY_EXACT",
        "semantic_judgment": "NOT_EVALUATED",
        "completion_claim_allowed": False,
        "hunks": hunks,
        "bundle_sha256": "",
    }
    if selection_schema == SELECTION_SCHEMA_V2:
        try:
            payload["document_format"] = document_format
            payload["coverage"] = coverage_layer.build_coverage(
                source,
                scene=str(scene),
                document_format=document_format,
                hunks=hunks,
                coverage_spec=spec["coverage"],
            )
        except coverage_layer.CoverageError as error:
            raise ShortPatchError(str(error)) from error
    payload["bundle_sha256"] = _bundle_hash(payload)
    validate_bundle_payload(payload, source)
    return payload


def _atomic_write_new(path: Path, raw: bytes) -> None:
    path = safe_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.staging-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise ShortPatchError("output_exists") from error
    finally:
        temporary.unlink(missing_ok=True)


def build_bundle(
    source_path: Path,
    spec_path: Path,
    output_path: Path,
    *,
    document_format: str | None = None,
) -> dict[str, Any]:
    source_path = safe_input_path(source_path, "source")
    spec_path = safe_input_path(spec_path, "selection spec")
    output_path = safe_output_path(output_path)
    source = read_source(source_path)
    spec_raw = _regular_input(spec_path, "selection spec", MAX_JSON_BYTES)
    spec = strict_json_bytes(spec_raw, "selection spec")
    if document_format is None or document_format.casefold() == "auto":
        document_format = (
            "tex"
            if source_path.suffix.casefold() in {".tex", ".ltx"}
            else "markdown"
        )
    else:
        document_format = document_format.casefold()
        if document_format not in {"markdown", "tex"}:
            raise ShortPatchError("document_format is invalid")
    payload = _build_payload(
        source,
        spec_raw,
        spec,
        document_format=document_format,
    )
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if read_source(source_path) != source:
        raise ShortPatchError("source changed while building bundle")
    if _regular_input(spec_path, "selection spec", MAX_JSON_BYTES) != spec_raw:
        raise ShortPatchError("selection spec changed while building bundle")
    _atomic_write_new(output_path, encoded)
    return payload


def load_bundle(
    path: Path,
    source: bytes | None = None,
    *,
    require_current_coverage_policy: bool = True,
) -> tuple[dict[str, Any], bytes]:
    raw = _regular_input(path, "bundle", MAX_JSON_BYTES)
    payload = strict_json_bytes(raw, "bundle")
    return validate_bundle_payload(
        payload,
        source,
        require_current_coverage_policy=require_current_coverage_policy,
    ), raw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a strict source-bound short Humanize PATCH bundle; never modify the source."
    )
    parser.add_argument("source", type=Path, help="strict UTF-8 source file")
    parser.add_argument(
        "--selection-spec",
        required=True,
        type=Path,
        help="humanize-short-patch-selection/v1 or coverage-aware v2 JSON",
    )
    parser.add_argument("--output", required=True, type=Path, help="new bundle path")
    parser.add_argument(
        "--document-format", choices=("AUTO", "MARKDOWN", "TEX"), default="AUTO"
    )
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        payload = build_bundle(
            args.source,
            args.selection_spec,
            args.output,
            document_format=(
                None if args.document_format == "AUTO" else args.document_format
            ),
        )
    except (OSError, ShortPatchError) as error:
        result = {
            "schema_version": BUNDLE_SCHEMA,
            "status": "FAIL",
            "error": str(error),
            "completion_claim_allowed": False,
        }
        print(json.dumps(result, ensure_ascii=False) if args.format == "json" else f"FAIL: {error}")
        return 1
    result = {
        "schema_version": payload["schema_version"],
        "status": "BUNDLED",
        "hunks_total": len(payload["hunks"]),
        "bundle_sha256": payload["bundle_sha256"],
        "patch_hunks_source_partition": "NON_OVERLAPPING",
        "semantic_judgment": "NOT_EVALUATED",
        "coverage_status": (
            payload["coverage"]["mechanical_coverage_status"]
            if "coverage" in payload
            else "NOT_PROVIDED"
        ),
        "coverage_completion_claim_allowed": bool(
            "coverage" in payload
            and payload["coverage"]["coverage_completion_claim_allowed"] is True
        ),
        "coverage_claim_scope": (
            payload["coverage"]["coverage_claim_scope"]
            if "coverage" in payload
            else None
        ),
        "coverage_scene": (
            payload["coverage"]["source"]["scene"]
            if "coverage" in payload
            else None
        ),
        "coverage_scan_scene": (
            payload["coverage"]["source"]["scan_scene"]
            if "coverage" in payload
            else None
        ),
        "coverage_source_kind": (
            payload["coverage"]["source"]["source_kind"]
            if "coverage" in payload
            else None
        ),
        "completion_claim_allowed": False,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"BUNDLED hunks={result['hunks_total']} bundle={result['bundle_sha256']}")
        print("completion_claim_allowed=false; run apply_humanize_short_patch.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
