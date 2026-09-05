#!/usr/bin/env python3
"""Create fail-closed rewrite bundle scaffolds from a prepared long-document run.

The generated files contain frozen bindings and the masked text, but are not
completion artifacts.  ``PENDING`` is intentionally unsupported by finalize;
the caller must choose ``REWRITE`` or ``NO_CHANGE`` and supply the corresponding
body/reason before the normal gates can run.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import stat
import sys
import uuid
import warnings
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402


HEX64 = re.compile(r"^[0-9a-f]{64}$")
UNIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ALLOWED_DECISIONS = {"REWRITE", "NO_CHANGE"}
ROUTE_REASON_BY_STATUS = {
    "EXPLICIT": "USER_EXPLICIT_SCENE",
    "ROUTED": "AUTO_UNIQUE_SCORE_ABOVE_THRESHOLD",
    "ROUTED_DOCUMENT_PRIOR": "AUTO_DOCUMENT_PRIOR_WITH_LOCAL_SUPPORT",
    "FALLBACK_GENERAL": "AUTO_INSUFFICIENT_SCENE_EVIDENCE",
}
UNIT_BUNDLE_SCHEMA = finalizer.UNIT_REWRITE_BUNDLE_SCHEMA
SCAFFOLD_SCHEMA = "humanize-rewrite-scaffold/v5"
AUTHORING_GATE_SCHEMA = "humanize-scaffold-authoring-gate/v1"
PUBLICATION_COMMIT_SCHEMA = "humanize-scaffold-publication-commit/v1"
UNCOMMITTED_MARKER_NAME = ".humanize-scaffold-uncommitted"
COMMITTED_MARKER_NAME = ".humanize-scaffold-committed"
MAX_JSON_DEPTH = 64


if os.name == "nt":
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    class _FileRenameInformation(ctypes.Structure):
        _fields_ = [
            ("ReplaceIfExists", wintypes.BOOL),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),
            ("FileName", wintypes.WCHAR * 1),
        ]

    class _FileDispositionInformation(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]

    class _FileRemoteProtocolInformation(ctypes.Structure):
        _fields_ = [
            ("StructureVersion", wintypes.USHORT),
            ("StructureSize", wintypes.USHORT),
            ("Protocol", wintypes.ULONG),
            ("ProtocolMajorVersion", wintypes.USHORT),
            ("ProtocolMinorVersion", wintypes.USHORT),
            ("ProtocolRevision", wintypes.USHORT),
            ("Reserved", wintypes.USHORT),
            ("Flags", wintypes.ULONG),
            ("GenericReserved", wintypes.ULONG * 8),
            ("ProtocolSpecificReserved", wintypes.ULONG * 16),
        ]

    class _NtIoStatusBlock(ctypes.Structure):
        _fields_ = [
            ("Status", ctypes.c_ssize_t),
            ("Information", ctypes.c_size_t),
        ]


_WIN_DELETE = 0x00010000
_WIN_GENERIC_READ = 0x80000000
_WIN_FILE_LIST_DIRECTORY = 0x0001
_WIN_FILE_READ_ATTRIBUTES = 0x0080
_WIN_FILE_SHARE_READ = 0x00000001
_WIN_FILE_SHARE_WRITE = 0x00000002
_WIN_FILE_SHARE_DELETE = 0x00000004
_WIN_OPEN_EXISTING = 3
_WIN_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_WIN_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_WIN_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_WIN_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_WIN_FILE_RENAME_INFO = 3
_WIN_FILE_DISPOSITION_INFO = 4
_WIN_FILE_REMOTE_PROTOCOL_INFO = 13
_WIN_FILE_RENAME_INFORMATION_CLASS = 10
_WIN_ERROR_INVALID_PARAMETER = 87
_WIN_READ_CHUNK_BYTES = 64 * 1024
_MAX_PUBLICATION_MARKER_BYTES = 64 * 1024


class ScaffoldReview(RuntimeError):
    """Expected authoring stop that must not be reported as corruption."""

    def __init__(self, reason: str, preflight: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.preflight = preflight


class ScaffoldInputFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ScaffoldDirtyFailure(RuntimeError):
    """Publication failed after the final name may have become visible."""

    def __init__(self, message: str, output: Path) -> None:
        super().__init__(message)
        self.output = output
        self.output_may_exist = True


class ScaffoldResult(dict[str, Any]):
    """Persisted v5 metadata plus a non-persisted authoring gate verdict."""

    def __init__(self, metadata: dict[str, Any], authoring_gate: dict[str, Any]) -> None:
        super().__init__(metadata)
        self.authoring_gate = authoring_gate


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> Any:
    raise ValueError(f"floating-point JSON number is forbidden: {value}")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON nesting is too deep")
    if isinstance(value, dict):
        for child in value.values():
            _check_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_depth(child, depth + 1)


def _strict_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not valid JSON: {error}") from error
    _check_depth(value)
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = _strict_json(raw, path.name)
    if not isinstance(value, dict):
        raise ValueError(f"chunk is not an object: {path.name}")
    return value


def _review_reason(summary: dict[str, Any]) -> str:
    if summary.get("source_change_units"):
        return "live_source_not_current"
    if summary.get("pending_units_total") == 0:
        return "no_authoring_eligible_units"
    return "long_authoring_preflight_review"


def _validated_preflight(run_dir: Path) -> dict[str, Any]:
    try:
        preflight = finalizer.validate_long_authoring_snapshot(run_dir)
    except ValueError as error:
        if str(error) == (
            "legacy prepare integrity requires a new prepare run for v5 authoring"
        ):
            raise ScaffoldReview("legacy_prepare_requires_reprepare") from error
        raise
    if not isinstance(preflight, dict) or set(preflight) != {
        "summary",
        "bindings",
        "chunks",
    }:
        raise ValueError("invalid long authoring preflight result")
    summary = preflight.get("summary")
    bindings = preflight.get("bindings")
    chunks = preflight.get("chunks")
    if not isinstance(summary, dict):
        raise ValueError("invalid long authoring preflight summary")
    if summary.get("status") != "PASS":
        raise ScaffoldReview(_review_reason(summary), dict(summary))
    if not isinstance(bindings, dict) or not isinstance(chunks, dict):
        raise ValueError("invalid long authoring preflight unit maps")
    if set(bindings) != set(chunks):
        raise ValueError("long authoring preflight binding coverage mismatch")
    if summary.get("eligible_units_total") != len(bindings):
        raise ValueError("long authoring preflight eligibility count mismatch")
    if not bindings:
        raise ScaffoldReview("no_authoring_eligible_units", dict(summary))
    seen: set[str] = set()
    for unit_id in sorted(bindings, key=str.casefold):
        if not isinstance(unit_id, str) or not UNIT_ID.fullmatch(unit_id):
            raise ValueError(f"invalid pending unit_id: {unit_id!r}")
        collision_key = unit_id.casefold()
        if collision_key in seen:
            raise ValueError(f"duplicate pending unit_id: {unit_id}")
        seen.add(collision_key)
        chunk = chunks[unit_id]
        binding = bindings[unit_id]
        if not isinstance(chunk, dict) or chunk.get("unit_id") != unit_id:
            raise ValueError(f"invalid preflight chunk: {unit_id}")
        if chunk.get("status") != "PENDING":
            raise ValueError(f"preflight chunk is not PENDING: {unit_id}")
        if not isinstance(chunk.get("masked_text"), str):
            raise ValueError(f"pending chunk has invalid masked_text: {unit_id}")
        finalizer._validate_long_authoring_binding_shape(binding)
        source_binding = binding.get("source_binding", {})
        voice_binding = binding.get("voice_binding", {})
        if source_binding.get("chunk_binding_sha256") != chunk.get(
            "chunk_binding_sha256"
        ):
            raise ValueError(f"preflight chunk binding mismatch: {unit_id}")
        if voice_binding.get("profile_sha256") != chunk.get("voice_profile_sha256"):
            raise ValueError(f"preflight voice binding mismatch: {unit_id}")
    return preflight


def _bundle(
    chunk: dict[str, Any], binding: dict[str, Any], decision: str
) -> dict[str, Any]:
    return finalizer.build_pristine_unit_rewrite_bundle(chunk, binding, decision)


def _rewrite_intent_authoring_contract() -> dict[str, Any]:
    """Expose the exact finalizer contract needed to complete a REWRITE template."""

    example_source = "第一行保持不变。\n示例来源行。\n"
    example_selected_line = "示例来源行。\n"
    example_summary = "删除空泛收尾并保留材料范围"
    example_signal = "STYLE-EMPTY-ENDING"
    return {
        "rewrite_intent_exact_fields": [
            "summary",
            "operations",
            "source_spans",
            "target_signals",
        ],
        "operation_contract": {
            "exact_fields": [
                "id",
                "kind",
                "source_span_ids",
                "target_signals",
                "summary",
            ],
            "id_pattern": r"^O[0-9]{1,3}$",
            "kind_pattern": r"^[A-Z][A-Z0-9_.-]{1,63}$",
            "non_topology_example_kind": "REWRITE_STYLE_SHELL",
            "balanced_topology_kinds": [
                "MERGE_ADJACENT_REDUNDANCY",
                "SPLIT_OVERLOADED_PARAGRAPH",
            ],
            "topology_kind_rule": (
                "DECLARE_THE_MATCHING_BALANCED_TOPOLOGY_KIND_ONLY_WHEN_PARAGRAPH_"
                "TOPOLOGY_ACTUALLY_CHANGES"
            ),
            "source_span_ids": "NONEMPTY_UNIQUE_DECLARED_SOURCE_SPAN_IDS",
            "target_signals": "NONEMPTY_UNIQUE_DECLARED_TARGET_SIGNALS",
            "summary": "SPECIFIC_NON_TEMPLATE_CHINESE_ACTION_AND_PRESERVED_SCOPE",
        },
        "source_span_contract": {
            "exact_fields": ["id", "start_line", "end_line", "sha256"],
            "id_pattern": r"^S[0-9]{1,3}$",
            "line_numbering": "ONE_BASED_INCLUSIVE",
            "ordering": "ASCENDING_NON_OVERLAPPING_UNIQUE_RANGES",
            "sha256_pattern": r"^[0-9a-f]{64}$",
            "hash_algorithm": [
                "NORMALIZE_CRLF_AND_CR_TO_LF",
                "SPLIT_PHYSICAL_LINES_WITH_KEEPENDS_TRUE",
                "CONCATENATE_LINES_START_LINE_THROUGH_END_LINE_INCLUSIVE",
                "ENCODE_UTF8_WITHOUT_BOM",
                "SHA256_LOWERCASE_HEX",
            ],
            "line_endings_are_hashed": True,
            "whole_unit_hash_is_invalid_for_a_partial_span": True,
        },
        "coverage_contract": {
            "every_declared_source_span_referenced_by_an_operation": True,
            "every_declared_target_signal_referenced_by_an_operation": True,
            "every_declared_source_span_must_intersect_the_masked_diff": True,
            "every_changed_source_line_must_be_covered_by_a_source_span": True,
        },
        "target_signal_prefixes": list(
            finalizer.REWRITE_INTENT_TARGET_SIGNAL_PREFIXES
        ),
        "target_signal_examples": [
            "STYLE-EMPTY-ENDING",
            "SCENE-COURSE-RHYTHM",
        ],
        "required_rewrite_fields": [
            "masked_text",
            "rewrite_intent.summary",
            "rewrite_intent.operations",
            "rewrite_intent.source_spans",
            "rewrite_intent.target_signals",
        ],
        "hash_example_context": {
            "normalized_lf_frozen_masked_source": example_source,
            "selected_start_line": 2,
            "selected_end_line": 2,
            "selected_line_including_line_ending": example_selected_line,
            "selected_line_sha256": sha256(example_selected_line.encode("utf-8")),
        },
        "valid_rewrite_intent_example": {
            "summary": example_summary,
            "operations": [
                {
                    "id": "O1",
                    "kind": "REWRITE_STYLE_SHELL",
                    "source_span_ids": ["S1"],
                    "target_signals": [example_signal],
                    "summary": example_summary,
                }
            ],
            "source_spans": [
                {
                    "id": "S1",
                    "start_line": 2,
                    "end_line": 2,
                    "sha256": sha256(example_selected_line.encode("utf-8")),
                }
            ],
            "target_signals": [example_signal],
        },
        "placeholder_templates_must_be_replaced": True,
        "scope": "AUTHORING_SYNTAX_ONLY_NOT_QUALITY_CLEARANCE",
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _preflight_equal(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return _canonical_json(first) == _canonical_json(second)


def _authoring_gate_state(
    run_dir: Path,
    preflight_summary: dict[str, Any],
) -> dict[str, Any]:
    """Derive review state only from the integrity-checked prepared run."""

    metadata_raw = (run_dir / "run_metadata.json").read_bytes()
    if sha256(metadata_raw) != preflight_summary.get("run_metadata_sha256"):
        raise ValueError("authoring gate run metadata drift")
    metadata = _strict_json(metadata_raw, "run_metadata.json")
    if not isinstance(metadata, dict):
        raise ValueError("authoring gate run metadata is not an object")
    inventory_name = metadata.get("structural_transaction_inventory")
    if inventory_name != "structural_transaction_inventory.json":
        raise ValueError("authoring gate structural inventory path invalid")
    inventory = _load_json(run_dir / inventory_name)
    transactions = inventory.get("transactions")
    candidates = metadata.get("structural_transaction_candidates")
    if (
        not isinstance(transactions, list)
        or isinstance(candidates, bool)
        or not isinstance(candidates, int)
        or candidates < 0
        or len(transactions) != candidates
    ):
        raise ValueError("authoring gate structural candidate count mismatch")
    if inventory.get("inventory_sha256") != metadata.get(
        "structural_transaction_inventory_sha256"
    ):
        raise ValueError("authoring gate structural inventory binding mismatch")
    inventory_status = str(inventory.get("status", ""))
    if candidates and (
        str(metadata.get("intensity", "")) != "STRUCTURAL"
        or str(metadata.get("structural_transaction_scope", ""))
        != "ADJACENT_PAIR"
        or inventory_status != "READY"
    ):
        raise ValueError("authoring gate structural candidate state invalid")
    review_reasons = (
        ["structural_transaction_candidates_require_explicit_disposition"]
        if candidates
        else []
    )
    return {
        "schema_version": AUTHORING_GATE_SCHEMA,
        "status": "REVIEW" if review_reasons else "PASS",
        "review_reasons": review_reasons,
        "structural_transaction_inventory_status": inventory_status,
        "structural_transaction_candidates_pending": candidates,
        "caller_reason_trusted": False,
        "caller_selection_trusted": False,
        "completion_claim_allowed": False,
    }


def _cli_route_summary(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str, str, str], int] = {}
    for record in metadata["records"]:
        status = str(record["scene_routing_decision"])
        key = (
            str(record["scene_requested"]),
            str(record["scene_resolved"]),
            status,
            ROUTE_REASON_BY_STATUS[status],
        )
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "requested_scene": key[0],
            "resolved_scene": key[1],
            "route_status": key[2],
            "reason_code": key[3],
            "units": count,
        }
        for key, count in sorted(counts.items())
    ]


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _reject_link_components(path: Path, label: str) -> None:
    """Reject an alias before ``resolve`` can erase evidence of the alias."""

    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute before link validation")
    current = Path(path.anchor)
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            break
        if finalizer._is_link_or_reparse(current):
            raise ValueError(f"{label} must not contain a link or reparse component")


def _path_identity(path: Path) -> tuple[int, int, int, int]:
    """Return replacement-sensitive identity without mutable directory times."""

    item = path.stat(follow_symlinks=False)
    return (
        int(item.st_dev),
        int(item.st_ino),
        int(item.st_mode),
        int(getattr(item, "st_file_attributes", 0)),
    )


def _win_kernel32() -> Any:
    if os.name != "nt":
        raise RuntimeError("Windows handle operations are unavailable")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetVolumeInformationByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeInformationByHandleW.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    return kernel32


def _win_ntdll() -> Any:
    if os.name != "nt":
        raise RuntimeError("Windows native handle operations are unavailable")
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    ntdll.NtSetInformationFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_NtIoStatusBlock),
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    ntdll.NtSetInformationFile.restype = ctypes.c_long
    ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG
    return ntdll


def _win_close_handle(handle: int | None) -> None:
    if handle is None:
        return
    kernel32 = _win_kernel32()
    if not kernel32.CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _win_open_path_handle(
    path: Path,
    *,
    desired_access: int,
    share_mode: int,
    directory: bool,
) -> int:
    kernel32 = _win_kernel32()
    flags = _WIN_FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        flags |= _WIN_FILE_FLAG_BACKUP_SEMANTICS
    ctypes.set_last_error(0)
    handle = kernel32.CreateFileW(
        os.fspath(path),
        desired_access,
        share_mode,
        None,
        _WIN_OPEN_EXISTING,
        flags,
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _win_handle_information(handle: int) -> dict[str, int]:
    kernel32 = _win_kernel32()
    value = _ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {
        "attributes": int(value.dwFileAttributes),
        "volume_serial": int(value.dwVolumeSerialNumber),
        "file_index": (int(value.nFileIndexHigh) << 32)
        | int(value.nFileIndexLow),
        "size": (int(value.nFileSizeHigh) << 32) | int(value.nFileSizeLow),
        "links": int(value.nNumberOfLinks),
    }


def _win_read_handle_bytes(handle: int) -> bytes:
    """Read one bounded payload from its already pinned file handle."""

    size = _win_handle_information(handle)["size"]
    if size > _MAX_PUBLICATION_MARKER_BYTES:
        raise ValueError("publication marker exceeds the bounded read limit")
    chunks: list[bytes] = []
    remaining = size
    kernel32 = _win_kernel32()
    while remaining:
        requested = min(remaining, _WIN_READ_CHUNK_BYTES)
        buffer = ctypes.create_string_buffer(requested)
        transferred = wintypes.DWORD()
        ctypes.set_last_error(0)
        if not kernel32.ReadFile(
            handle,
            buffer,
            requested,
            ctypes.byref(transferred),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        count = int(transferred.value)
        if count <= 0:
            raise RuntimeError("publication marker handle produced a short read")
        if count > requested or count > remaining:
            raise RuntimeError("publication marker handle produced an oversized read")
        chunks.append(buffer.raw[:count])
        remaining -= count

    probe = ctypes.create_string_buffer(1)
    transferred = wintypes.DWORD()
    ctypes.set_last_error(0)
    if not kernel32.ReadFile(
        handle,
        probe,
        1,
        ctypes.byref(transferred),
        None,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if transferred.value != 0:
        raise RuntimeError("publication marker handle exceeded its reported size")
    raw = b"".join(chunks)
    if len(raw) != size:
        raise RuntimeError("publication marker handle length changed while reading")
    return raw


def _win_filesystem_name(handle: int) -> str:
    kernel32 = _win_kernel32()
    volume_name = ctypes.create_unicode_buffer(261)
    filesystem_name = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    maximum_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not kernel32.GetVolumeInformationByHandleW(
        handle,
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(maximum_component),
        ctypes.byref(flags),
        filesystem_name,
        len(filesystem_name),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return filesystem_name.value.upper()


def _win_remote_protocol(handle: int) -> dict[str, int] | None:
    """Return remote protocol details, or ``None`` for a local handle."""

    kernel32 = _win_kernel32()
    value = _FileRemoteProtocolInformation()
    ctypes.set_last_error(0)
    if kernel32.GetFileInformationByHandleEx(
        handle,
        _WIN_FILE_REMOTE_PROTOCOL_INFO,
        ctypes.byref(value),
        ctypes.sizeof(value),
    ):
        return {
            "protocol": int(value.Protocol),
            "major": int(value.ProtocolMajorVersion),
            "minor": int(value.ProtocolMinorVersion),
            "revision": int(value.ProtocolRevision),
            "flags": int(value.Flags),
        }
    error = ctypes.get_last_error()
    if error == _WIN_ERROR_INVALID_PARAMETER:
        return None
    raise ctypes.WinError(error)


def _win_open_directory_guard(
    path: Path,
    expected_identity: tuple[int, ...],
    label: str,
    *,
    deletable: bool = False,
) -> int:
    access = _WIN_FILE_READ_ATTRIBUTES | _WIN_FILE_LIST_DIRECTORY
    if deletable:
        access |= _WIN_DELETE
    handle = _win_open_path_handle(
        path,
        desired_access=access,
        share_mode=_WIN_FILE_SHARE_READ | _WIN_FILE_SHARE_WRITE,
        directory=True,
    )
    try:
        info = _win_handle_information(handle)
        if not info["attributes"] & _WIN_FILE_ATTRIBUTE_DIRECTORY:
            raise ValueError(f"{label} must be a directory")
        if info["attributes"] & _WIN_FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"{label} must not be a reparse point")
        filesystem = _win_filesystem_name(handle)
        if filesystem != "NTFS":
            raise RuntimeError(
                f"{label} requires tested NTFS handle semantics; got {filesystem}"
            )
        if _win_remote_protocol(handle) is not None:
            raise RuntimeError(
                f"{label} requires local NTFS handle semantics; remote protocol detected"
            )
        if _path_identity(path) != expected_identity:
            raise ValueError(f"{label} identity changed while acquiring guard")
    except BaseException:
        _win_close_handle(handle)
        raise
    return handle


def _win_set_directory_name(
    handle: int,
    destination: Path | str,
    root_handle: int | None = None,
) -> None:
    kernel32 = _win_kernel32()
    name = os.fspath(destination)
    if root_handle is not None:
        if name in {"", ".", ".."} or Path(name).name != name:
            raise ValueError("handle-relative rename destination must be one leaf name")
    encoded = name.encode("utf-16-le")
    encoded_bytes = len(encoded)
    # Windows validates the full ABI structure size, including WCHAR[1] and
    # trailing alignment, even though FileNameLength excludes the terminator.
    size = ctypes.sizeof(_FileRenameInformation) + encoded_bytes
    buffer = ctypes.create_string_buffer(size)
    info = ctypes.cast(
        buffer, ctypes.POINTER(_FileRenameInformation)
    ).contents
    info.ReplaceIfExists = False
    info.RootDirectory = root_handle
    info.FileNameLength = encoded_bytes
    ctypes.memmove(
        ctypes.addressof(buffer) + _FileRenameInformation.FileName.offset,
        encoded,
        encoded_bytes,
    )
    if root_handle is not None:
        ntdll = _win_ntdll()
        io_status = _NtIoStatusBlock()
        status = ntdll.NtSetInformationFile(
            handle,
            ctypes.byref(io_status),
            buffer,
            size,
            _WIN_FILE_RENAME_INFORMATION_CLASS,
        )
        if status < 0:
            raise ctypes.WinError(int(ntdll.RtlNtStatusToDosError(status)))
        return
    ctypes.set_last_error(0)
    if not kernel32.SetFileInformationByHandle(
        handle,
        _WIN_FILE_RENAME_INFO,
        buffer,
        size,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _win_mark_handle_for_deletion(handle: int) -> None:
    kernel32 = _win_kernel32()
    disposition = _FileDispositionInformation(True)
    ctypes.set_last_error(0)
    if not kernel32.SetFileInformationByHandle(
        handle,
        _WIN_FILE_DISPOSITION_INFO,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


class _WindowsStagingLease:
    """Pin a staging directory and its validated members by NTFS handles."""

    def __init__(
        self,
        path: Path,
        identity: tuple[int, ...],
        directory_handle: int,
        parent_handle: int | None,
    ) -> None:
        self.path = path
        self.identity = identity
        self.directory_handle: int | None = directory_handle
        self.parent_handle = parent_handle
        self.member_handles: dict[str, tuple[int, dict[str, int]]] = {}
        self.mutable_names: set[str] = set()

    @classmethod
    def acquire(
        cls,
        path: Path,
        identity: tuple[int, ...],
        parent_handle: int | None = None,
    ) -> "_WindowsStagingLease":
        handle = _win_open_directory_guard(
            path,
            identity,
            "scaffold staging",
            deletable=True,
        )
        return cls(path, identity, handle, parent_handle)

    def close_members(self) -> None:
        errors: list[BaseException] = []
        for name, (handle, _info) in list(self.member_handles.items()):
            try:
                _win_close_handle(handle)
            except BaseException as error:
                errors.append(error)
            else:
                del self.member_handles[name]
        if errors:
            failure = RuntimeError(
                f"failed to close {len(errors)} scaffold member handle(s)"
            )
            for error in errors:
                failure.add_note(repr(error))
            raise failure
        self.mutable_names.clear()

    def close(self) -> None:
        errors: list[BaseException] = []
        try:
            self.close_members()
        except BaseException as error:
            errors.append(error)
        handle = self.directory_handle
        try:
            _win_close_handle(handle)
        except BaseException as error:
            errors.append(error)
        else:
            self.directory_handle = None
        if errors:
            failure = RuntimeError(
                f"failed to close {len(errors)} scaffold lease resource(s)"
            )
            for error in errors:
                failure.add_note(repr(error))
            raise failure

    def assert_directory_path(self, path: Path) -> None:
        if self.directory_handle is None:
            raise RuntimeError("scaffold staging lease is closed")
        if finalizer._is_link_or_reparse(path):
            raise ValueError("scaffold staging path became a link or reparse point")
        if _path_identity(path) != self.identity:
            raise ValueError("scaffold staging path identity changed")

    def lock_members(
        self,
        path: Path,
        expected_names: set[str],
        *,
        mutable_names: set[str] | None = None,
    ) -> None:
        self.close_members()
        self.assert_directory_path(path)
        mutable = mutable_names or set()
        if not mutable <= expected_names:
            raise ValueError("mutable scaffold member is outside expected closure")
        entries = list(os.scandir(path))
        actual_names = {entry.name for entry in entries}
        if len(actual_names) != len(entries) or actual_names != expected_names:
            raise ValueError("scaffold staging file closure changed before locking")
        opened: dict[str, tuple[int, dict[str, int]]] = {}
        try:
            for entry in entries:
                member = Path(entry.path)
                is_mutable = entry.name in mutable
                if is_mutable:
                    if finalizer._is_link_or_reparse(member):
                        raise ValueError(
                            f"mutable staged member is a link or reparse point: {entry.name}"
                        )
                    item = member.stat(follow_symlinks=False)
                    if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
                        raise ValueError(
                            f"mutable staged member is not standalone: {entry.name}"
                        )
                    continue
                handle = _win_open_path_handle(
                    member,
                    desired_access=_WIN_GENERIC_READ | _WIN_FILE_READ_ATTRIBUTES,
                    share_mode=_WIN_FILE_SHARE_READ,
                    directory=False,
                )
                try:
                    info = _win_handle_information(handle)
                    attributes = info["attributes"]
                    if attributes & _WIN_FILE_ATTRIBUTE_DIRECTORY:
                        raise ValueError(
                            f"staged member became a directory: {entry.name}"
                        )
                    if attributes & _WIN_FILE_ATTRIBUTE_REPARSE_POINT:
                        raise ValueError(
                            f"staged member became a reparse point: {entry.name}"
                        )
                    if info["links"] != 1:
                        raise ValueError(
                            f"staged member is hardlinked: {entry.name}"
                        )
                    item = member.stat(follow_symlinks=False)
                    if (
                        not stat.S_ISREG(item.st_mode)
                        or item.st_nlink != 1
                        or int(item.st_ino) != info["file_index"]
                        or int(item.st_size) != info["size"]
                    ):
                        raise ValueError(
                            f"staged member identity changed while locking: {entry.name}"
                        )
                except BaseException:
                    _win_close_handle(handle)
                    raise
                opened[entry.name] = (handle, info)
        except BaseException:
            for handle, _info in opened.values():
                _win_close_handle(handle)
            raise
        self.member_handles = opened
        self.mutable_names = set(mutable)
        self.assert_members(path, expected_names)

    def assert_members(self, path: Path, expected_names: set[str]) -> None:
        self.assert_directory_path(path)
        entries = list(os.scandir(path))
        actual_names = {entry.name for entry in entries}
        if len(actual_names) != len(entries) or actual_names != expected_names:
            raise ValueError("scaffold staging file closure changed while locked")
        if set(self.member_handles) != expected_names - self.mutable_names:
            raise ValueError("scaffold staging member lock coverage mismatch")
        for entry in entries:
            member = Path(entry.path)
            if finalizer._is_link_or_reparse(member):
                raise ValueError(
                    f"staged member became a link or reparse point: {entry.name}"
                )
            item = member.stat(follow_symlinks=False)
            if entry.name in self.mutable_names:
                if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
                    raise ValueError(
                        f"mutable staged member is not standalone: {entry.name}"
                    )
                continue
            info = self.member_handles[entry.name][1]
            if (
                not stat.S_ISREG(item.st_mode)
                or item.st_nlink != 1
                or int(item.st_ino) != info["file_index"]
                or int(item.st_size) != info["size"]
            ):
                raise ValueError(
                    f"staged member identity changed while locked: {entry.name}"
                )

    def rename(self, destination: Path) -> None:
        if self.directory_handle is None:
            raise RuntimeError("scaffold staging lease is closed")
        if self.parent_handle is None:
            raise RuntimeError("scaffold staging lease has no pinned parent handle")
        _win_set_directory_name(
            self.directory_handle,
            destination.name,
            self.parent_handle,
        )
        self.path = destination

    def commit_marker(self, path: Path, expected_sha256: str) -> None:
        if self.directory_handle is None:
            raise RuntimeError("scaffold staging lease is closed")
        if not HEX64.fullmatch(expected_sha256):
            raise ValueError("expected publication marker SHA-256 is invalid")
        if UNCOMMITTED_MARKER_NAME not in self.mutable_names:
            raise RuntimeError("uncommitted marker is not registered as mutable")
        if UNCOMMITTED_MARKER_NAME in self.member_handles:
            raise RuntimeError("uncommitted marker was locked before final validation")
        if COMMITTED_MARKER_NAME in self.member_handles:
            raise RuntimeError("committed marker already exists")
        marker = path / UNCOMMITTED_MARKER_NAME
        handle = _win_open_path_handle(
            marker,
            desired_access=(
                _WIN_GENERIC_READ | _WIN_FILE_READ_ATTRIBUTES | _WIN_DELETE
            ),
            share_mode=_WIN_FILE_SHARE_READ,
            directory=False,
        )
        try:
            info = _win_handle_information(handle)
            attributes = info["attributes"]
            if attributes & _WIN_FILE_ATTRIBUTE_DIRECTORY:
                raise ValueError("uncommitted marker became a directory")
            if attributes & _WIN_FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("uncommitted marker became a reparse point")
            if info["links"] != 1:
                raise ValueError("uncommitted marker became hardlinked")
            item = marker.stat(follow_symlinks=False)
            if (
                finalizer._is_link_or_reparse(marker)
                or not stat.S_ISREG(item.st_mode)
                or item.st_nlink != 1
                or int(item.st_ino) != info["file_index"]
                or int(item.st_size) != info["size"]
            ):
                raise ValueError("uncommitted marker identity changed while freezing")
            if sha256(_win_read_handle_bytes(handle)) != expected_sha256:
                raise ValueError("uncommitted marker bytes changed before commit")
            item = marker.stat(follow_symlinks=False)
            if (
                finalizer._is_link_or_reparse(marker)
                or not stat.S_ISREG(item.st_mode)
                or item.st_nlink != 1
                or int(item.st_ino) != info["file_index"]
                or int(item.st_size) != info["size"]
            ):
                raise ValueError("uncommitted marker identity changed after freezing")
        except BaseException:
            _win_close_handle(handle)
            raise
        marker_record = (handle, info)
        self.member_handles[UNCOMMITTED_MARKER_NAME] = marker_record
        try:
            _win_set_directory_name(
                handle,
                COMMITTED_MARKER_NAME,
                self.directory_handle,
            )
        except BaseException:
            raise
        del self.member_handles[UNCOMMITTED_MARKER_NAME]
        self.member_handles[COMMITTED_MARKER_NAME] = (handle, info)
        self.mutable_names.discard(UNCOMMITTED_MARKER_NAME)
        self.assert_directory_path(path)
        if os.path.lexists(path / UNCOMMITTED_MARKER_NAME):
            raise RuntimeError("uncommitted marker remained after commit")
        committed = path / COMMITTED_MARKER_NAME
        item = committed.stat(follow_symlinks=False)
        if int(item.st_ino) != info["file_index"] or item.st_nlink != 1:
            raise RuntimeError("committed marker identity mismatch")
        self.assert_members(path, set(self.member_handles))

    def delete_tree(self) -> None:
        """Delete only entries opened beneath the pinned directory handle."""

        self.close_members()
        self.assert_directory_path(self.path)
        for _round in range(4):
            entries = list(os.scandir(self.path))
            if not entries:
                assert self.directory_handle is not None
                _win_mark_handle_for_deletion(self.directory_handle)
                return
            handles: list[tuple[int, Path, dict[str, int]]] = []
            try:
                for entry in entries:
                    member = Path(entry.path)
                    handle = _win_open_path_handle(
                        member,
                        desired_access=_WIN_FILE_READ_ATTRIBUTES | _WIN_DELETE,
                        share_mode=(
                            _WIN_FILE_SHARE_READ
                            | _WIN_FILE_SHARE_WRITE
                            | _WIN_FILE_SHARE_DELETE
                        ),
                        directory=entry.is_dir(follow_symlinks=False),
                    )
                    try:
                        info = _win_handle_information(handle)
                        if info["attributes"] & _WIN_FILE_ATTRIBUTE_DIRECTORY:
                            raise RuntimeError(
                                "refuse recursive staging cleanup"
                            )
                    except BaseException:
                        _win_close_handle(handle)
                        raise
                    handles.append((handle, member, info))
                for handle, member, info in handles:
                    try:
                        item = member.stat(follow_symlinks=False)
                        still_named = int(item.st_ino) == info["file_index"]
                    except OSError:
                        still_named = False
                    if still_named:
                        try:
                            _win_mark_handle_for_deletion(handle)
                        except OSError:
                            try:
                                current = member.stat(follow_symlinks=False)
                                still_named = (
                                    int(current.st_ino) == info["file_index"]
                                )
                            except OSError:
                                still_named = False
                            if still_named:
                                raise
            finally:
                close_errors: list[BaseException] = []
                for handle, _member, _info in handles:
                    try:
                        _win_close_handle(handle)
                    except BaseException as error:
                        close_errors.append(error)
                if close_errors:
                    failure = RuntimeError(
                        f"failed to close {len(close_errors)} cleanup handle(s)"
                    )
                    for error in close_errors:
                        failure.add_note(repr(error))
                    raise failure
        raise RuntimeError("staging cleanup did not reach an empty directory")


def _stable_file_bytes(path: Path, label: str) -> tuple[bytes, tuple[int, ...]]:
    if finalizer._is_link_or_reparse(path):
        raise ValueError(f"{label} must not be a link or reparse point")
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} must be a standalone regular file")
    raw = path.read_bytes()
    after = path.stat(follow_symlinks=False)
    if (
        finalizer._is_link_or_reparse(path)
        or not stat.S_ISREG(after.st_mode)
        or after.st_nlink != 1
    ):
        raise ValueError(f"{label} changed into a linked or non-regular file")
    before_identity = _path_identity_from_stat(before)
    after_identity = _path_identity_from_stat(after)
    if before_identity != after_identity:
        raise ValueError(f"{label} changed while being read")
    return raw, before_identity


def _path_identity_from_stat(item: os.stat_result) -> tuple[int, ...]:
    return (
        int(item.st_dev),
        int(item.st_ino),
        int(item.st_mode),
        int(item.st_size),
        int(item.st_mtime_ns),
        int(item.st_ctime_ns),
        int(item.st_nlink),
        int(getattr(item, "st_file_attributes", 0)),
    )


def _ensure_publish_target(run_dir: Path, output: Path) -> tuple[int, ...]:
    try:
        output.relative_to(run_dir)
    except ValueError:
        pass
    else:
        raise ValueError("output must be outside run_dir")
    parent = output.parent
    if not parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    if finalizer._is_link_or_reparse(parent):
        raise ValueError("output parent must not be a link or reparse point")
    parent_identity = _path_identity(parent)
    if os.path.lexists(output):
        raise ValueError("output must not already exist")
    return parent_identity


def _exclusive_write(
    path: Path,
    raw: bytes,
    staging: Path,
    staging_identity: tuple[int, ...],
) -> None:
    if (
        finalizer._is_link_or_reparse(staging)
        or _path_identity(staging) != staging_identity
    ):
        raise ValueError("scaffold staging identity changed before write")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags, 0o600)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError("staged output is not a standalone regular file")
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write while creating scaffold")
            view = view[written:]
        os.fsync(descriptor)
        closed_state = os.fstat(descriptor)
        if (
            not stat.S_ISREG(closed_state.st_mode)
            or closed_state.st_nlink != 1
            or closed_state.st_size != len(raw)
        ):
            raise ValueError("staged output identity changed during write")
    finally:
        os.close(descriptor)
    if (
        finalizer._is_link_or_reparse(staging)
        or _path_identity(staging) != staging_identity
    ):
        raise ValueError("scaffold staging identity changed after write")


def _validate_staged_scaffold(
    staging: Path,
    expected_metadata: dict[str, Any],
    staging_identity: tuple[int, ...],
) -> str:
    if (
        finalizer._is_link_or_reparse(staging)
        or not staging.is_dir()
        or _path_identity(staging) != staging_identity
    ):
        raise ValueError("scaffold staging must be a standalone directory")
    records = expected_metadata["records"]
    expected_names = {
        "scaffold_metadata.json",
        UNCOMMITTED_MARKER_NAME,
    } | {
        str(record["path"]) for record in records
    }
    entries = list(os.scandir(staging))
    actual_names = {entry.name for entry in entries}
    if len(actual_names) != len(entries) or actual_names != expected_names:
        raise ValueError("scaffold staging file closure mismatch")
    if len({name.casefold() for name in actual_names}) != len(actual_names):
        raise ValueError("scaffold staging contains case-colliding files")

    raw_by_name: dict[str, bytes] = {}
    identities: dict[str, tuple[int, ...]] = {}
    for entry in entries:
        path = Path(entry.path)
        raw, identity = _stable_file_bytes(path, f"staged file {entry.name}")
        raw_by_name[entry.name] = raw
        identities[entry.name] = identity

    metadata = _strict_json(
        raw_by_name["scaffold_metadata.json"], "scaffold_metadata.json"
    )
    finalizer._validate_scaffold_metadata(metadata, staging / "scaffold_metadata.json")
    if _canonical_json(metadata) != _canonical_json(expected_metadata):
        raise ValueError("staged scaffold metadata differs from generated metadata")

    rewrites: dict[str, dict[str, Any]] = {}
    for record in metadata["records"]:
        unit_id = str(record["unit_id"])
        name = str(record["path"])
        raw = raw_by_name[name]
        if sha256(raw) != record["template_sha256"]:
            raise ValueError(f"staged template hash mismatch: {unit_id}")
        payload = _strict_json(raw, name)
        if not isinstance(payload, dict):
            raise ValueError(f"staged rewrite bundle is not an object: {unit_id}")
        rewrites[unit_id] = payload
    finalizer._validate_scaffold_bundle_consistency(
        metadata,
        rewrites,
        staging / "scaffold_metadata.json",
    )
    if _path_identity(staging) != staging_identity:
        raise ValueError("scaffold staging identity changed during validation")
    fingerprint = [
        {
            "name": name,
            "sha256": sha256(raw_by_name[name]),
            "identity": list(identities[name]),
        }
        for name in sorted(actual_names, key=str.casefold)
    ]
    return sha256(_canonical_json(fingerprint))


def _publish_directory_exclusive(
    staging: Path,
    output: Path,
    staging_lease: _WindowsStagingLease | None = None,
) -> None:
    """Publish without replacement; Windows callers perform locked post-validation."""

    if os.name == "nt":
        if staging_lease is None:
            raise RuntimeError("Windows publication requires a pinned staging handle")
        staging_lease.assert_directory_path(staging)
        staging_lease.rename(output)
        return
    raise RuntimeError(
        "secure scaffold publication requires tested Windows NTFS handle semantics"
    )


def _safe_remove_staging(
    staging: Path,
    parent: Path,
    staging_identity: tuple[int, ...] | None,
    staging_lease: _WindowsStagingLease | None = None,
) -> None:
    if not os.path.lexists(staging):
        return
    if staging.parent != parent or not staging.name.startswith(".humanize-scaffold-"):
        raise RuntimeError("refuse unsafe staging cleanup")
    if finalizer._is_link_or_reparse(staging):
        raise RuntimeError("refuse linked staging cleanup")
    if staging_identity is None or _path_identity(staging) != staging_identity:
        raise RuntimeError("refuse replaced staging cleanup")
    if os.name == "nt":
        owned_lease = staging_lease is None
        lease = staging_lease or _WindowsStagingLease.acquire(
            staging, staging_identity
        )
        try:
            lease.path = staging
            lease.delete_tree()
        finally:
            if owned_lease:
                lease.close()
        return
    entries = list(os.scandir(staging))
    for entry in entries:
        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            raise RuntimeError("refuse recursive staging cleanup")
        # Unlinking a link removes only the directory entry.  Never open or
        # recurse through an untrusted cleanup member.
        path.unlink()
        if _path_identity(staging) != staging_identity:
            raise RuntimeError("staging identity changed during cleanup")
    staging.rmdir()


def _normalize_decisions(
    chunks: list[dict[str, Any]],
    decision: str | None,
    decision_map: dict[str, str] | None,
) -> dict[str, str]:
    if (decision is None) == (decision_map is None):
        raise ValueError("provide exactly one of decision or decision_map")
    unit_ids = {str(chunk["unit_id"]) for chunk in chunks}
    if decision is not None:
        normalized = decision.upper()
        if normalized not in ALLOWED_DECISIONS:
            raise ValueError("decision must be REWRITE or NO_CHANGE")
        return {unit_id: normalized for unit_id in unit_ids}
    assert decision_map is not None
    if set(decision_map) != unit_ids:
        raise ValueError("decision_map must contain exactly every pending unit_id")
    normalized_map: dict[str, str] = {}
    for unit_id, value in decision_map.items():
        if not isinstance(unit_id, str) or not UNIT_ID.fullmatch(unit_id):
            raise ValueError("decision_map contains invalid unit_id")
        if not isinstance(value, str) or value.upper() not in ALLOWED_DECISIONS:
            raise ValueError("decision_map values must be REWRITE or NO_CHANGE")
        normalized_map[unit_id] = value.upper()
    return normalized_map


def scaffold(
    run_dir: Path,
    output: Path,
    decision: str | None = None,
    decision_map: dict[str, str] | None = None,
) -> ScaffoldResult:
    if os.name != "nt":
        raise RuntimeError(
            "secure scaffold publication requires tested Windows NTFS handle semantics"
        )
    raw_run_dir = _absolute_without_resolving(Path(run_dir))
    raw_output = _absolute_without_resolving(Path(output))
    _reject_link_components(raw_run_dir, "run_dir")
    _reject_link_components(raw_output, "output")
    if not raw_run_dir.is_dir():
        raise ValueError("run_dir must be a directory")
    raw_parent = raw_output.parent
    if not raw_parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    raw_run_identity = _path_identity(raw_run_dir)
    raw_parent_identity = _path_identity(raw_parent)
    run_guard: int | None = None
    parent_guard: int | None = None
    staging_lease: _WindowsStagingLease | None = None
    staging: Path | None = None
    parent: Path | None = None
    published = False
    staging_identity: tuple[int, ...] | None = None
    try:
        if os.name == "nt":
            run_guard = _win_open_directory_guard(
                raw_run_dir,
                raw_run_identity,
                "run_dir",
            )
            parent_guard = _win_open_directory_guard(
                raw_parent,
                raw_parent_identity,
                "output parent",
            )
        run_dir = raw_run_dir.resolve(strict=True)
        parent = raw_parent.resolve(strict=True)
        output = parent / raw_output.name
        if (
            _path_identity(run_dir) != raw_run_identity
            or _path_identity(parent) != raw_parent_identity
        ):
            raise ValueError("run_dir or output parent changed during path binding")
        parent_identity = _ensure_publish_target(run_dir, output)
        if parent_identity != raw_parent_identity:
            raise ValueError("output parent changed during path binding")
        staging = (
            parent
            / f".humanize-scaffold-{output.name}-{uuid.uuid4().hex}.tmp"
        )
        if os.path.lexists(staging):
            raise ValueError("unexpected scaffold staging collision")
        with finalizer._run_lock(run_dir):
            first = _validated_preflight(run_dir)
            authoring_gate = _authoring_gate_state(run_dir, first["summary"])
            chunks_by_id = first["chunks"]
            bindings = first["bindings"]
            chunks = [
                chunks_by_id[unit_id]
                for unit_id in sorted(chunks_by_id, key=str.casefold)
            ]
            decisions = _normalize_decisions(chunks, decision, decision_map)
            staging.mkdir(mode=0o700)
            staging_identity = _path_identity(staging)
            if os.name == "nt":
                staging_lease = _WindowsStagingLease.acquire(
                    staging, staging_identity, parent_guard
                )
            records: list[dict[str, Any]] = []
            for chunk in chunks:
                unit_id = str(chunk["unit_id"])
                path = staging / f"{unit_id}.json"
                unit_decision = decisions[unit_id]
                binding = bindings[unit_id]
                encoded = finalizer.encode_pristine_unit_rewrite_bundle(
                    chunk,
                    binding,
                    unit_decision,
                )
                _exclusive_write(path, encoded, staging, staging_identity)
                route = binding["scene_route"]
                source = binding["source_binding"]
                records.append(
                    {
                        "unit_id": unit_id,
                        "path": path.name,
                        "decision": unit_decision,
                        "template_sha256": sha256(encoded),
                        "authoring_binding_sha256": binding[
                            "authoring_binding_sha256"
                        ],
                        "scene_requested": route["requested_scene"],
                        "scene_resolved": route["resolved_scene"],
                        "scene_routing_decision": route["status"],
                        "scene_routing_top_score": route["top_score"],
                        "scene_routing_margin": route["margin"],
                        "source_span_sha256": source["source_span_sha256"],
                        "chunk_binding_sha256": source["chunk_binding_sha256"],
                    }
                )
            metadata = {
                "schema_version": SCAFFOLD_SCHEMA,
                "run_dir_name": run_dir.name,
                "decision": (
                    next(iter(set(decisions.values())))
                    if len(set(decisions.values())) == 1
                    else "MIXED"
                ),
                "decision_map": dict(sorted(decisions.items())),
                "pending_units_total": len(chunks),
                "templates_total": len(records),
                "completion_claim_allowed": False,
                "requires_manual_completion": True,
                "metadata_scope": "SCAFFOLD_CREATION_TIME",
                "template_hash_scope": "ORIGINAL_TEMPLATE_BYTES",
                "preflight": first["summary"],
                "records": records,
            }
            metadata_bytes = (
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            _exclusive_write(
                staging / "scaffold_metadata.json",
                metadata_bytes,
                staging,
                staging_identity,
            )
            commit_payload = {
                "schema_version": PUBLICATION_COMMIT_SCHEMA,
                "scaffold_schema_version": SCAFFOLD_SCHEMA,
                "scaffold_metadata_sha256": sha256(metadata_bytes),
                "completion_claim_allowed": False,
            }
            commit_bytes = (
                json.dumps(commit_payload, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            _exclusive_write(
                staging / UNCOMMITTED_MARKER_NAME,
                commit_bytes,
                staging,
                staging_identity,
            )
            finalizer._validate_scaffold_metadata(
                metadata, staging / "scaffold_metadata.json"
            )
            staged_fingerprint = _validate_staged_scaffold(
                staging, metadata, staging_identity
            )
            second = _validated_preflight(run_dir)
            if not _preflight_equal(first, second):
                raise ValueError("long authoring state changed before scaffold commit")
            if not _preflight_equal(
                authoring_gate,
                _authoring_gate_state(run_dir, second["summary"]),
            ):
                raise ValueError("long authoring gate changed before scaffold commit")
            if (
                _validate_staged_scaffold(staging, metadata, staging_identity)
                != staged_fingerprint
            ):
                raise ValueError("scaffold staging changed before commit")
            if (
                finalizer._is_link_or_reparse(parent)
                or _path_identity(parent) != parent_identity
            ):
                raise ValueError("output parent changed before scaffold commit")
            # Recheck the destination only after every staged byte has been
            # reread.  Publication itself is exclusive and cannot replace a
            # path that appears after this check.
            if os.path.lexists(output):
                raise ValueError("output appeared before scaffold commit")
            if _path_identity(staging) != staging_identity:
                raise ValueError("scaffold staging changed before publication")
            expected_names = {
                "scaffold_metadata.json",
                UNCOMMITTED_MARKER_NAME,
            } | {
                str(record["path"]) for record in records
            }
            moved_to_output = False
            try:
                _publish_directory_exclusive(
                    staging,
                    output,
                    staging_lease,
                )
                moved_to_output = True
                if staging_lease is not None:
                    staging_lease.lock_members(
                        output,
                        expected_names,
                        mutable_names={UNCOMMITTED_MARKER_NAME},
                    )
                    staging_lease.assert_members(output, expected_names)
                    published_fingerprint = _validate_staged_scaffold(
                        output, metadata, staging_identity
                    )
                    staging_lease.assert_members(output, expected_names)
                    if published_fingerprint != staged_fingerprint:
                        raise ValueError(
                            "published scaffold differs from locked staging"
                        )
                    staging_lease.commit_marker(output, sha256(commit_bytes))
            except BaseException as publish_error:
                if moved_to_output and staging_lease is not None:
                    try:
                        staging_lease.close_members()
                        staging_lease.rename(staging)
                        moved_to_output = False
                    except BaseException as rollback_error:
                        published = True
                        raise ScaffoldDirtyFailure(
                            "scaffold publication verification failed and "
                            f"handle rollback failed: {rollback_error}",
                            output,
                        ) from publish_error
                raise
            published = True
            return ScaffoldResult(metadata, authoring_gate)
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error: BaseException | None = None
        if not published and staging is not None and parent is not None:
            try:
                _safe_remove_staging(
                    staging,
                    parent,
                    staging_identity,
                    staging_lease,
                )
            except BaseException as error:
                cleanup_error = error
        if staging_lease is not None:
            try:
                staging_lease.close()
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
        for guard in (parent_guard, run_guard):
            try:
                _win_close_handle(guard)
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
        if cleanup_error is not None:
            if active_error is not None:
                active_error.add_note(f"resource cleanup also failed: {cleanup_error}")
            elif published:
                warnings.warn(
                    f"committed scaffold resource cleanup failed: {cleanup_error}",
                    ResourceWarning,
                    stacklevel=2,
                )
            else:
                raise cleanup_error


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="为 prepare 长文运行生成带冻结 binding 的安全改写包骨架；骨架不是完成态。"
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="新的 rewrites 目标路径；该路径必须尚不存在",
    )
    decision_group = parser.add_mutually_exclusive_group(required=True)
    decision_group.add_argument("--decision", choices=sorted(ALLOWED_DECISIONS))
    decision_group.add_argument(
        "--decision-map",
        type=Path,
        help="UTF-8 JSON object mapping every pending unit_id to REWRITE or NO_CHANGE",
    )
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    try:
        decision_map = None
        if args.decision_map is not None:
            try:
                decision_map_raw = args.decision_map.read_bytes()
            except FileNotFoundError as error:
                raise ScaffoldInputFailure(
                    "DECISION_MAP_NOT_FOUND",
                    "decision_map file was not found",
                ) from error
            except PermissionError as error:
                raise ScaffoldInputFailure(
                    "DECISION_MAP_PERMISSION_DENIED",
                    "decision_map file could not be read due to permissions",
                ) from error
            except OSError as error:
                raise ScaffoldInputFailure(
                    "DECISION_MAP_READ_FAILED",
                    "decision_map file could not be read",
                ) from error
            try:
                parsed = _strict_json(decision_map_raw, "decision_map")
            except ValueError as error:
                message = str(error)
                code = (
                    "DECISION_MAP_ENCODING_INVALID"
                    if "strict UTF-8" in message
                    else "DECISION_MAP_JSON_INVALID"
                )
                raise ScaffoldInputFailure(
                    code,
                    "decision_map is not valid strict UTF-8 JSON",
                ) from error
            if not isinstance(parsed, dict):
                raise ScaffoldInputFailure(
                    "DECISION_MAP_CONTRACT_INVALID",
                    "decision_map JSON must be an object",
                )
            decision_map = parsed
        result = scaffold(args.run_dir, args.output, args.decision, decision_map)
    except ScaffoldInputFailure as error:
        payload = {
            "schema_version": SCAFFOLD_SCHEMA,
            "status": "FAIL",
            "error_code": error.code,
            "error": str(error),
            "paths_redacted": True,
            "completion_claim_allowed": False,
        }
        print(json.dumps(payload, ensure_ascii=False) if args.format == "json" else f"FAIL {error.code}: {error}")
        return 1
    except ScaffoldReview as error:
        payload = {
            "schema_version": SCAFFOLD_SCHEMA,
            "status": "REVIEW",
            "review_reasons": [error.reason],
            "preflight": error.preflight,
            "completion_claim_allowed": False,
        }
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"REVIEW: {error.reason}")
        return 2
    except ScaffoldDirtyFailure as error:
        payload = {
            "schema_version": SCAFFOLD_SCHEMA,
            "status": "FAIL_DIRTY",
            "error": str(error),
            "output": str(error.output),
            "output_may_exist": True,
            "uncommitted_marker": UNCOMMITTED_MARKER_NAME,
            "completion_claim_allowed": False,
        }
        print(
            json.dumps(payload, ensure_ascii=False)
            if args.format == "json"
            else f"FAIL_DIRTY output_may_exist=true: {error}"
        )
        return 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        payload = {
            "schema_version": SCAFFOLD_SCHEMA,
            "status": "FAIL",
            "error": str(error),
            "completion_claim_allowed": False,
        }
        print(json.dumps(payload, ensure_ascii=False) if args.format == "json" else f"FAIL: {error}")
        return 1
    route_summary = _cli_route_summary(result)
    payload = dict(result)
    payload["authoring_gate"] = dict(result.authoring_gate)
    payload["authoring_route_summary"] = route_summary
    payload["authoring_binding_visibility"] = {
        "template_field": "authoring_binding",
        "metadata_hash_field": "authoring_binding_sha256",
        "scope": "FROZEN_PREPARED_RUN_BINDING",
    }
    rewrite_contract = _rewrite_intent_authoring_contract()
    payload["rewrite_intent_authoring_contract"] = rewrite_contract
    payload["template_field_edit_scope_authoring_contract"] = {
        "bundle_field": "template_field_edit_scope",
        "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
        "permission_boundary": finalizer.output_validator.TEMPLATE_FIELD_PERMISSION,
        "default": None,
        "source_binding": "MATERIALIZED_FROM_FROZEN_UNIT_AT_FINALIZE",
        "quality_clearance_granted": False,
        "role_or_force_drift_still_reviews": True,
    }
    authoring_review = result.authoring_gate["status"] == "REVIEW"
    payload["authoring_state"] = "PENDING_TEMPLATE_COMPLETION"
    payload["do_not_finalize_pristine_scaffold"] = True
    payload["next_action"] = {
        "action": "COMPLETE_EVERY_TEMPLATE_BEFORE_FINALIZE",
        "rewrite": (
            "edit masked_text; replace rewrite_intent.summary; populate operations, "
            "source_spans, and target_signals; cover every changed source line"
        ),
        "no_change": (
            "replace reason; add at least one hash-bound evidence_span; add any "
            "required high-signal keep_reasons"
        ),
    }
    payload["status"] = "REVIEW" if authoring_review else "SCAFFOLDED"
    payload["scaffold_publication_status"] = "SCAFFOLDED"
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        label = "SCAFFOLDED_REVIEW" if authoring_review else "SCAFFOLDED"
        print(f"{label} decision={result['decision']} templates={result['templates_total']}")
        for route in route_summary:
            print(
                "frozen_route "
                f"requested={route['requested_scene']} "
                f"resolved={route['resolved_scene']} "
                f"status={route['route_status']} "
                f"reason={route['reason_code']} units={route['units']}"
            )
        print(
            "frozen_binding=template.authoring_binding; "
            "metadata_hash=records[*].authoring_binding_sha256"
        )
        print(
            "target_signal_prefixes="
            + ",".join(finalizer.REWRITE_INTENT_TARGET_SIGNAL_PREFIXES)
            + "; examples=STYLE-EMPTY-ENDING,SCENE-COURSE-RHYTHM"
        )
        print(
            "rewrite_intent_exact_fields="
            + ",".join(rewrite_contract["rewrite_intent_exact_fields"])
        )
        print(
            "operation_exact_fields="
            + ",".join(rewrite_contract["operation_contract"]["exact_fields"])
            + "; kind_pattern="
            + rewrite_contract["operation_contract"]["kind_pattern"]
        )
        print(
            "source_span_exact_fields="
            + ",".join(rewrite_contract["source_span_contract"]["exact_fields"])
            + "; line_numbering=ONE_BASED_INCLUSIVE; "
            "ordering=ASCENDING_NON_OVERLAPPING_UNIQUE_RANGES"
        )
        print(
            "source_span_hash_steps="
            + ">".join(rewrite_contract["source_span_contract"]["hash_algorithm"])
            + "; line_endings_are_hashed=true"
        )
        print(
            "valid_rewrite_intent_example="
            + json.dumps(
                rewrite_contract["valid_rewrite_intent_example"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        print(
            "template_field_edit_scope=null unless exact field payload editing is "
            "authorized; permission=PAYLOAD_ONLY; quality_clearance=false"
        )
        print(
            "authoring_state=PENDING_TEMPLATE_COMPLETION; "
            "do_not_finalize_pristine_scaffold=true"
        )
        print(
            "REWRITE: edit masked_text; replace rewrite_intent.summary; populate "
            "operations,source_spans,target_signals; cover every changed source line"
        )
        print(
            "NO_CHANGE: replace reason; add hash-bound evidence_spans and required "
            "high-signal keep_reasons"
        )
        print(
            "completion_claim_allowed=false; metadata_scope=scaffold_creation_time; "
            "next_action=COMPLETE_EVERY_TEMPLATE_BEFORE_FINALIZE"
        )
        if authoring_review:
            print(
                "REVIEW: structural_transaction_candidates_require_explicit_disposition "
                f"pending={result.authoring_gate['structural_transaction_candidates_pending']}"
            )
    return 2 if authoring_review else 0


if __name__ == "__main__":
    raise SystemExit(main())
