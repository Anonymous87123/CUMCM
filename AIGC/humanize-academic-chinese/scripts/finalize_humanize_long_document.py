#!/usr/bin/env python3
"""Validate and assemble long-document humanization units without touching sources."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_humanize_invariants as invariants  # noqa: E402
import prepare_humanize_long_document as preparer  # noqa: E402
import validate_humanize_output as output_validator  # noqa: E402
import build_humanize_voice_profile as voice_profiles  # noqa: E402
import load_humanize_negative_guards as negative_guards  # noqa: E402
import audit_humanize_repetition_guards as repetition_guards  # noqa: E402


DEFAULT_COMPILE_CHECK_TIMEOUT_SECONDS = 300.0
COMPILE_STATUS_READ_TIMEOUT_SECONDS = 2.0
COMPILE_STATUS_MAX_BYTES = 65536


PLACEHOLDER_RE = re.compile(r"\[\[PROTECTED:(?P<id>[^:\]]+):(?P<hash>[0-9a-f]{12})\]\]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
SAFE_UNIT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
TEX_COMMAND_TOKEN_RE = re.compile(r"\\[A-Za-z@]+\*?|\\[^A-Za-z\s]")
TERMINAL_STATUSES = {
    "DONE",
    "NO_CHANGE",
    "SKIPPED_PROTECTED",
    "SKIPPED_GARBLED",
    "UNRESOLVED",
    "CHANGED_AFTER_SNAPSHOT",
}
SECOND_PASS_RECEIPT_SCHEMA = "humanize-second-pass-convergence-receipt/v2"
STRUCTURAL_SEMANTIC_REVIEW_REQUEST_SCHEMA = (
    "humanize-structural-semantic-review-request/v1"
)
STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V1 = "humanize-structural-transaction-bundle/v1"
STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V2 = "humanize-structural-transaction-bundle/v2"
STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA = "humanize-structural-transaction-bundle/v3"
STRUCTURAL_TRANSACTION_BUNDLE_SCHEMAS = {
    STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V1,
    STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V2,
    STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA,
}
STRUCTURAL_TRANSACTION_BUNDLE_LOCAL_INTENT_SCHEMAS = {
    STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V2,
    STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA,
}
STRUCTURAL_TRANSACTION_DECLINE_SCHEMA = "humanize-structural-transaction-decline/v1"
STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA_V1 = (
    "humanize-structural-transaction-review-request/v1"
)
STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA = (
    "humanize-structural-transaction-review-request/v2"
)
UNIT_REWRITE_BUNDLE_SCHEMA_V2 = "humanize-unit-rewrite-bundle/v2"
UNIT_REWRITE_BUNDLE_SCHEMA_V3 = "humanize-unit-rewrite-bundle/v3"
UNIT_REWRITE_BUNDLE_SCHEMA = "humanize-unit-rewrite-bundle/v4"
UNIT_REWRITE_BUNDLE_SCHEMAS = {
    UNIT_REWRITE_BUNDLE_SCHEMA_V2,
    UNIT_REWRITE_BUNDLE_SCHEMA_V3,
    UNIT_REWRITE_BUNDLE_SCHEMA,
}
UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA = (
    "humanize-unit-template-field-edit-scope/v1"
)
LONG_AUTHORING_BINDING_SCHEMA = "humanize-long-authoring-binding/v1"
LONG_AUTHORING_PREFLIGHT_SCHEMA = "humanize-long-authoring-preflight/v1"
LONG_AUTHORING_BINDING_FIELDS = {
    "schema_version",
    "integrity_scope",
    "snapshot_id",
    "prepare_integrity_sha256",
    "run_metadata_sha256",
    "policy_snapshot_sha256",
    "source_binding",
    "scene_route",
    "voice_binding",
    "mode",
    "intensity",
    "authoring_allowed",
    "completion_claim_allowed",
    "humanize_quality_claim_allowed",
    "authoring_binding_sha256",
}
LONG_AUTHORING_SOURCE_BINDING_FIELDS = {
    "file_id",
    "source_file_sha256",
    "unit_id",
    "offset_unit",
    "start",
    "end",
    "start_line",
    "end_line",
    "source_span_sha256",
    "masked_text_sha256",
    "chunk_binding_sha256",
}
LONG_AUTHORING_SCENE_ROUTE_FIELDS = {
    "requested_scene",
    "resolved_scene",
    "status",
    "reason_code",
    "document_prior_scene",
    "scores",
    "top_score",
    "margin",
    "ambiguous_scenes",
    "evidence",
    "policy_sha256",
    "policy_revision",
    "heading_path_sha256",
    "routing_input_sha256",
}
LONG_AUTHORING_VOICE_BINDING_FIELDS = {
    "profile_id",
    "profile_revision",
    "profile_kind",
    "binding_scene",
    "profile_sha256",
}
REWRITE_INTENT_EVIDENCE_SCHEMA = "humanize-rewrite-intent-evidence/v1"
TRANSACTION_FRAGMENT_REWRITE_INTENT_EVIDENCE_SCHEMA = (
    "humanize-transaction-fragment-rewrite-intent-evidence/v1"
)
STRUCTURAL_TRANSACTION_DECLINE_REASON_CODES = {
    "NO_CROSS_UNIT_STYLE_GAIN",
    "DEPENDENCY_OR_REFERENT_RISK",
    "CLAIM_EVIDENCE_ORDER_RISK",
    "QUESTION_ANSWER_PAIRING_RISK",
    "PROTECTED_BOUNDARY_RISK",
    "USER_SCOPE_LOCK",
    "MEMBER_COMMITTED_TO_OTHER_TRANSACTION",
    "OTHER_REVIEWED_NO_CHANGE",
}
SCAFFOLD_METADATA_NAME = "scaffold_metadata.json"
SCAFFOLD_UNCOMMITTED_MARKER_NAME = ".humanize-scaffold-uncommitted"
SCAFFOLD_COMMITTED_MARKER_NAME = ".humanize-scaffold-committed"
SCAFFOLD_PUBLICATION_COMMIT_SCHEMA = "humanize-scaffold-publication-commit/v1"
REWRITE_INTENT_TODO = (
    "TODO: edit masked_text, then replace this placeholder and populate "
    "operations, source_spans, and target_signals before finalize"
)
NO_CHANGE_REASON_TODO = (
    "TODO: replace this placeholder with a specific function-preservation "
    "reason and add at least one hash-bound evidence_span before finalize"
)
SCAFFOLD_METADATA_SCHEMAS = {
    "humanize-rewrite-scaffold/v1",
    "humanize-rewrite-scaffold/v2",
    "humanize-rewrite-scaffold/v3",
    "humanize-rewrite-scaffold/v4",
    "humanize-rewrite-scaffold/v5",
}

BOUNDARY_TEMPLATE_CUE_RE = re.compile(
    r"^(?:本文|本节|本研究|这里|这一|首先|其次|最后|综上|因此|由此|需要|值得|关键|更直接|换言|在此基础|进一步)"
)
PURE_TEX_STRUCTURE_LINE_RE = re.compile(
    r"^\s*\\(?:begin|end|part|chapter|section|subsection|subsubsection|paragraph|subparagraph|label|input|include)\b.*$"
)
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
HAN_GAP_RE = re.compile(r"(?<=[\u3400-\u9fff])[ \t\u00a0\u3000]+(?=[\u3400-\u9fff])")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def _run_lock(run_dir: Path):
    """Serialize finalization for one run directory across threads/processes."""
    lock_path = run_dir / ".finalize.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if _path_lexists(lock_path):
        if _is_link_or_reparse(lock_path) or not lock_path.is_file():
            raise ValueError("finalize lock must be a regular file")
        if lock_path.stat(follow_symlinks=False).st_nlink != 1:
            raise ValueError("finalize lock must not be a hard link")
    handle = lock_path.open("a+b")
    try:
        opened = os.fstat(handle.fileno())
        current = lock_path.stat(follow_symlinks=False)
        if (
            opened.st_nlink != 1
            or _is_link_or_reparse(lock_path)
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise ValueError("finalize lock changed during secure open")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            # LK_NBLCK has a deterministic retry loop; LK_LOCK gives up after
            # a platform-defined number of attempts under sustained contention.
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _verify_prepare_integrity(run_dir: Path) -> None:
    manifest_path = run_dir / "prepare_integrity.json"
    if not manifest_path.is_file():
        raise ValueError("missing prepare_integrity.json; refuse unverifiable finalize")
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("invalid prepare_integrity.json")
    if manifest.get("schema_version") == preparer.PREPARE_INTEGRITY_SCHEMA_VERSION:
        preparer.validate_integrity_manifest(run_dir, manifest)
        return
    if manifest.get("schema_version") != 1:
        raise ValueError("invalid prepare_integrity.json")
    if set(manifest) != {"schema_version", "artifacts"}:
        raise ValueError("invalid legacy prepare_integrity.json")
    if (run_dir / "structural_transaction_inventory.json").exists():
        raise ValueError("legacy prepare integrity cannot authorize transactions")
    if (run_dir / "source_role_overrides.json").exists():
        raise ValueError("legacy prepare integrity cannot authorize source role overrides")
    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.is_file():
        legacy_metadata = _load_json(metadata_path)
        if isinstance(legacy_metadata, dict) and any(
            str(key).startswith("structural_transaction_") for key in legacy_metadata
        ):
            raise ValueError("legacy prepare metadata cannot authorize transactions")
        if isinstance(legacy_metadata, dict) and any(
            str(key).startswith("source_role_override") for key in legacy_metadata
        ):
            raise ValueError("legacy prepare metadata cannot authorize source role overrides")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("prepare_integrity.json has no artifacts")
    expected_paths = {str(item.get("path", "")) for item in artifacts if isinstance(item, dict)}
    actual_paths = {
        str(path.relative_to(run_dir)).replace("\\", "/")
        for path in [
            run_dir / "snapshot.json",
            run_dir / "file_manifest.csv",
            run_dir / "protected_spans.jsonl",
            run_dir / "units.jsonl",
            run_dir / "coverage_ledger.csv",
            run_dir / "run_metadata.json",
            run_dir / "scene_routing_policy.json",
            *[
                path
                for path in (
                    run_dir / "voice_profile.json",
                    run_dir / "voice_profile_set.json",
                    run_dir / "voice_sample_manifest.json",
                    run_dir / "voice_sample_spec.json",
                )
                if path.is_file()
            ],
            *(
                sorted(
                    (run_dir / "voice_profiles").glob("*.json"),
                    key=lambda item: item.name.casefold(),
                )
                if (run_dir / "voice_profiles").is_dir()
                else []
            ),
            *sorted((run_dir / "chunks").glob("*.json"), key=lambda item: item.name.casefold()),
        ]
        if path.is_file()
    }
    if expected_paths != actual_paths:
        raise ValueError("prepare artifact set changed after snapshot")
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("invalid prepare integrity artifact")
        path = run_dir / item["path"]
        if not path.is_file() or sha256(path.read_bytes()) != item.get("sha256"):
            raise ValueError(f"prepare artifact changed after snapshot: {item['path']}")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json_strict(text: str, label: str) -> Any:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"invalid number {token}")
            ),
        )
        voice_profiles._reject_floats_and_depth(value)
        return value
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"invalid strict JSON {label}: {error}") from error


def _load_json(path: Path) -> Any:
    # PowerShell's UTF-8 output commonly includes a BOM; rewrite bundles are
    # user-facing interchange files and should accept both UTF-8 variants.
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read strict JSON {path}: {error}") from error
    return _parse_json_strict(text, str(path))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(_parse_json_strict(line, f"{path}:{line_number}"))
                except ValueError as error:
                    raise ValueError(f"{path}:{line_number}: {error}") from error
    return rows


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if (
            fields is None
            or not fields
            or any(not isinstance(field, str) or not field.strip() for field in fields)
            or len(fields) != len(set(fields))
        ):
            raise ValueError(f"CSV header is empty, blank, or duplicated: {path}")
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, 2):
            if None in row or set(row) != set(fields) or any(value is None for value in row.values()):
                raise ValueError(f"CSV row width does not match header: {path}:{line_number}")
            rows.append(row)
        return rows


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replace_bytes_atomic(
    path: Path, raw: bytes, *, temporary_prefix: str | None = None
) -> None:
    """Replace one regular file from a same-directory staged byte image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=temporary_prefix or f".{path.name}.",
        suffix=".staging",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


AUTHORITY_GROUP_JOURNAL_SCHEMA = "humanize-authority-group-journal/v2"
AUTHORITY_GROUP_JOURNAL_NAME = ".humanize-authority-group-journal.json"
AUTHORITY_GROUP_TRANSACTION_PREFIX = ".humanize-authority-group-"
AUTHORITY_GROUP_JOURNAL_STAGING_PREFIX = ".humanize-authority-journal-staging-"
AUTHORITY_GROUP_COMMIT_SCHEMA = "humanize-authority-group-commit/v1"
AUTHORITY_GROUP_COMMIT_NAME = ".humanize-authority-group-commit.json"
AUTHORITY_GROUP_COMMIT_STAGING_PREFIX = ".humanize-authority-commit-staging-"
AUTHORITY_GROUP_TARGET_STAGING_PREFIX = ".humanize-authority-target-staging-"
AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX = ".humanize-authority-transaction-staging-"
AUTHORITY_GROUP_TARGET_NAMES = (
    "finalization_metadata.json",
    "last_failed_attempt_metadata.json",
    "latest_attempt_metadata.json",
)
RUN_STATE_JOURNAL_SCHEMA = "humanize-run-state-journal/v2"
RUN_STATE_JOURNAL_NAME = ".humanize-run-state-journal.json"
RUN_STATE_TRANSACTION_PREFIX = ".humanize-run-state-"
RUN_STATE_JOURNAL_STAGING_PREFIX = ".humanize-run-state-journal-staging-"
RUN_STATE_CLEANUP_SCHEMA = "humanize-run-state-cleanup/v1"
RUN_STATE_CLEANUP_PREFIX = ".humanize-run-state-cleanup-"
RUN_STATE_CLEANUP_STAGING_PREFIX = ".humanize-run-state-cleanup-staging-"
AUTHORITY_GROUP_ALLOWED_TARGET_SETS = frozenset(
    {
        frozenset({"finalization_metadata.json", "latest_attempt_metadata.json"}),
        frozenset({"last_failed_attempt_metadata.json", "latest_attempt_metadata.json"}),
    }
)


def _authority_group_transaction_id() -> str:
    seed = f"{os.getpid()}:{time.time_ns()}:{id(object())}".encode("ascii")
    return hashlib.sha256(seed).hexdigest()[:24]


def _path_lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _authority_regular_file_bytes(path: Path, label: str) -> bytes:
    if _is_link_or_reparse(path):
        raise ValueError(f"{label} must not be a link or reparse point")
    if not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    if path.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError(f"{label} must not be a hard link")
    return path.read_bytes()


def _validate_authority_target_names(target_names: set[str]) -> None:
    if frozenset(target_names) not in AUTHORITY_GROUP_ALLOWED_TARGET_SETS:
        raise ValueError("authority group target set is invalid")


def _canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _authority_member_descriptor(name: str, raw: bytes | None) -> dict[str, Any]:
    return {
        "target": name,
        "exists": raw is not None,
        "bytes": len(raw) if raw is not None else 0,
        "sha256": sha256(raw) if raw is not None else None,
    }


def _authority_commit_payload(
    *, generation: int, transaction_id: str, role: str, members: dict[str, bytes | None]
) -> dict[str, Any]:
    return {
        "schema_version": AUTHORITY_GROUP_COMMIT_SCHEMA,
        "generation": generation,
        "transaction_id": transaction_id,
        "role": role,
        "members": [
            _authority_member_descriptor(name, members[name])
            for name in AUTHORITY_GROUP_TARGET_NAMES
        ],
    }


def _parse_authority_commit(raw: bytes) -> dict[str, Any]:
    commit = _parse_json_strict(raw.decode("utf-8"), AUTHORITY_GROUP_COMMIT_NAME)
    if not isinstance(commit, dict) or set(commit) != {
        "schema_version",
        "generation",
        "transaction_id",
        "role",
        "members",
    }:
        raise ValueError("authority commit fields are invalid")
    if (
        commit.get("schema_version") != AUTHORITY_GROUP_COMMIT_SCHEMA
        or not isinstance(commit.get("generation"), int)
        or isinstance(commit.get("generation"), bool)
        or commit["generation"] < 0
        or not isinstance(commit.get("transaction_id"), str)
        or re.fullmatch(r"(?:BOOTSTRAP|[0-9a-f]{24})", commit["transaction_id"])
        is None
        or commit.get("role") not in {"LEGACY_BASELINE", "SUCCESS", "FAILED_ATTEMPT"}
        or not isinstance(commit.get("members"), list)
        or len(commit["members"]) != len(AUTHORITY_GROUP_TARGET_NAMES)
    ):
        raise ValueError("authority commit schema is invalid")
    for expected_name, member in zip(AUTHORITY_GROUP_TARGET_NAMES, commit["members"]):
        if not isinstance(member, dict) or set(member) != {
            "target",
            "exists",
            "bytes",
            "sha256",
        }:
            raise ValueError("authority commit member fields are invalid")
        exists = member.get("exists")
        size = member.get("bytes")
        digest = member.get("sha256")
        if (
            member.get("target") != expected_name
            or not isinstance(exists, bool)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or (
                exists
                and (
                    not isinstance(digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                )
            )
            or (not exists and (digest is not None or size != 0))
        ):
            raise ValueError("authority commit member binding is invalid")
    by_name = {member["target"]: member for member in commit["members"]}
    if commit["role"] == "SUCCESS":
        left = by_name["finalization_metadata.json"]
        right = by_name["latest_attempt_metadata.json"]
    elif commit["role"] == "FAILED_ATTEMPT":
        left = by_name["last_failed_attempt_metadata.json"]
        right = by_name["latest_attempt_metadata.json"]
    else:
        left = right = None
    if left is not None and (
        not left["exists"]
        or not right["exists"]
        or (left["bytes"], left["sha256"]) != (right["bytes"], right["sha256"])
    ):
        raise ValueError("authority commit active pair is not byte-identical")
    return commit


def _authority_closure_bytes(parent: Path) -> dict[str, bytes | None]:
    closure: dict[str, bytes | None] = {}
    for name in AUTHORITY_GROUP_TARGET_NAMES:
        path = parent / name
        closure[name] = (
            _authority_regular_file_bytes(path, "authority group target")
            if _path_lexists(path)
            else None
        )
    return closure


def _validate_authority_closure(
    parent: Path, commit: dict[str, Any]
) -> dict[str, bytes | None]:
    closure = _authority_closure_bytes(parent)
    for member in commit["members"]:
        raw = closure[member["target"]]
        if member["exists"] != (raw is not None):
            raise RuntimeError("authority closure presence does not match commit")
        if raw is not None and (
            len(raw) != member["bytes"] or sha256(raw) != member["sha256"]
        ):
            raise RuntimeError("authority closure bytes do not match commit")
    role = commit["role"]
    if role == "SUCCESS":
        if (
            closure["finalization_metadata.json"] is None
            or closure["latest_attempt_metadata.json"] is None
            or closure["finalization_metadata.json"]
            != closure["latest_attempt_metadata.json"]
        ):
            raise RuntimeError("SUCCESS authority pair is not byte-identical")
    elif role == "FAILED_ATTEMPT":
        if (
            closure["last_failed_attempt_metadata.json"] is None
            or closure["latest_attempt_metadata.json"] is None
            or closure["last_failed_attempt_metadata.json"]
            != closure["latest_attempt_metadata.json"]
        ):
            raise RuntimeError("FAILED_ATTEMPT authority pair is not byte-identical")
    return closure


def _load_or_bootstrap_authority_commit(parent: Path) -> tuple[bytes, dict[str, Any]]:
    commit_path = parent / AUTHORITY_GROUP_COMMIT_NAME
    if _path_lexists(commit_path):
        raw = _authority_regular_file_bytes(commit_path, "authority group commit")
        commit = _parse_authority_commit(raw)
        return raw, commit
    if _path_lexists(parent / AUTHORITY_GROUP_JOURNAL_NAME) or any(
        parent.glob(AUTHORITY_GROUP_TRANSACTION_PREFIX + "*")
    ):
        raise RuntimeError("authority commit is missing while transaction state exists")
    closure = _authority_closure_bytes(parent)
    present = {name for name, raw in closure.items() if raw is not None}
    allowed_legacy_shapes = {
        frozenset(),
        frozenset({"finalization_metadata.json"}),
        frozenset({"finalization_metadata.json", "latest_attempt_metadata.json"}),
        frozenset({"last_failed_attempt_metadata.json", "latest_attempt_metadata.json"}),
        frozenset(AUTHORITY_GROUP_TARGET_NAMES),
    }
    if frozenset(present) not in allowed_legacy_shapes:
        raise RuntimeError("partial authority closure cannot be bootstrapped")
    if "latest_attempt_metadata.json" in present:
        success_pair = (
            closure["finalization_metadata.json"] is not None
            and closure["finalization_metadata.json"]
            == closure["latest_attempt_metadata.json"]
        )
        failed_pair = (
            closure["last_failed_attempt_metadata.json"] is not None
            and closure["last_failed_attempt_metadata.json"]
            == closure["latest_attempt_metadata.json"]
        )
        if success_pair == failed_pair:
            raise RuntimeError("legacy authority active role is ambiguous")
    commit = _authority_commit_payload(
        generation=0,
        transaction_id="BOOTSTRAP",
        role="LEGACY_BASELINE",
        members=closure,
    )
    raw = _canonical_json_bytes(commit)
    _replace_bytes_atomic(
        commit_path,
        raw,
        temporary_prefix=AUTHORITY_GROUP_COMMIT_STAGING_PREFIX,
    )
    persisted = _authority_regular_file_bytes(commit_path, "authority group commit")
    if persisted != raw:
        raise RuntimeError("authority commit bootstrap verification failed")
    return raw, commit


def _validate_orphan_authority_transaction(path: Path) -> None:
    suffix = path.name.removeprefix(AUTHORITY_GROUP_TRANSACTION_PREFIX)
    if re.fullmatch(r"[0-9a-f]{24}", suffix) is None:
        raise ValueError("authority transaction residue name is invalid")
    if _is_link_or_reparse(path) or not path.is_dir():
        raise ValueError("authority transaction residue has an unsafe type")
    for child in list(path.iterdir()):
        if child.name.startswith(AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX):
            _authority_regular_file_bytes(child, "authority transaction staging residue")
            child.unlink()
            continue
        if (
            re.fullmatch(r"member-[0-9]+\.(?:old|new)", child.name) is None
            and child.name != "commit.new"
        ):
            raise ValueError("authority transaction residue contains an unknown member")
        _authority_regular_file_bytes(child, "authority transaction residue member")


def _cleanup_orphan_authority_journal_staging(parent: Path) -> None:
    for prefix, label in (
        (AUTHORITY_GROUP_JOURNAL_STAGING_PREFIX, "authority journal staging residue"),
        (AUTHORITY_GROUP_COMMIT_STAGING_PREFIX, "authority commit staging residue"),
        (AUTHORITY_GROUP_TARGET_STAGING_PREFIX, "authority target staging residue"),
    ):
        for path in sorted(parent.glob(prefix + "*")):
            _authority_regular_file_bytes(path, label)
            path.unlink()


def _cleanup_orphan_authority_group_transactions(parent: Path) -> None:
    for path in sorted(parent.glob(AUTHORITY_GROUP_TRANSACTION_PREFIX + "*")):
        if path.name in {AUTHORITY_GROUP_JOURNAL_NAME, AUTHORITY_GROUP_COMMIT_NAME}:
            continue
        _validate_orphan_authority_transaction(path)
        shutil.rmtree(path)


def _recover_authority_group_journal(parent: Path) -> bool:
    """Recover the complete authority closure according to its commit pointer."""
    _cleanup_orphan_authority_journal_staging(parent)
    journal_path = parent / AUTHORITY_GROUP_JOURNAL_NAME
    if not _path_lexists(journal_path):
        _cleanup_orphan_authority_group_transactions(parent)
        _commit_raw, commit = _load_or_bootstrap_authority_commit(parent)
        _validate_authority_closure(parent, commit)
        return False
    raw = _authority_regular_file_bytes(journal_path, "authority group journal")
    journal = _parse_json_strict(raw.decode("utf-8"), AUTHORITY_GROUP_JOURNAL_NAME)
    expected_fields = {
        "schema_version",
        "transaction_id",
        "state",
        "role",
        "base_generation",
        "next_generation",
        "base_commit_sha256",
        "next_commit_sha256",
        "members",
    }
    if not isinstance(journal, dict) or set(journal) != expected_fields:
        raise ValueError("authority group journal fields are invalid")
    transaction_id = journal.get("transaction_id")
    if (
        journal.get("schema_version") != AUTHORITY_GROUP_JOURNAL_SCHEMA
        or journal.get("state") != "PREPARED"
        or journal.get("role") not in {"SUCCESS", "FAILED_ATTEMPT"}
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None
        or re.fullmatch(r"[0-9a-f]{64}", str(journal.get("base_commit_sha256", "")))
        is None
        or re.fullmatch(r"[0-9a-f]{64}", str(journal.get("next_commit_sha256", "")))
        is None
        or not isinstance(journal.get("base_generation"), int)
        or isinstance(journal.get("base_generation"), bool)
        or journal["base_generation"] < 0
        or journal.get("next_generation") != journal["base_generation"] + 1
        or not isinstance(journal.get("members"), list)
        or len(journal["members"]) != len(AUTHORITY_GROUP_TARGET_NAMES)
    ):
        raise ValueError("authority group journal schema or state is invalid")
    transaction_dir = parent / (
        AUTHORITY_GROUP_TRANSACTION_PREFIX + transaction_id
    )
    if _is_link_or_reparse(transaction_dir) or not transaction_dir.is_dir():
        raise ValueError("authority group transaction directory is unavailable")
    seen_artifacts: set[str] = set()
    members: list[tuple[Path, bytes | None, bytes | None, str, str]] = []
    member_fields = {
        "target",
        "old_exists",
        "old_sha256",
        "old_bytes",
        "new_exists",
        "new_sha256",
        "new_bytes",
        "backup",
        "staging",
    }
    for index, (expected_target, member) in enumerate(
        zip(AUTHORITY_GROUP_TARGET_NAMES, journal["members"])
    ):
        if not isinstance(member, dict) or set(member) != member_fields:
            raise ValueError("authority group journal member fields are invalid")
        target_name = member.get("target")
        backup_name = member.get("backup")
        staging_name = member.get("staging")
        if (
            not isinstance(target_name, str)
            or target_name != expected_target
            or not isinstance(backup_name, str)
            or Path(backup_name).name != backup_name
            or not isinstance(staging_name, str)
            or Path(staging_name).name != staging_name
            or backup_name != f"member-{index}.old"
            or staging_name != f"member-{index}.new"
            or backup_name in seen_artifacts
            or staging_name in seen_artifacts
            or not isinstance(member.get("old_exists"), bool)
            or not isinstance(member.get("new_exists"), bool)
            or not isinstance(member.get("old_bytes"), int)
            or isinstance(member.get("old_bytes"), bool)
            or member["old_bytes"] < 0
            or not isinstance(member.get("new_bytes"), int)
            or isinstance(member.get("new_bytes"), bool)
            or member["new_bytes"] < 0
        ):
            raise ValueError("authority group journal member binding is invalid")
        old_raw: bytes | None = None
        old_sha = member.get("old_sha256")
        if member["old_exists"]:
            if not isinstance(old_sha, str) or re.fullmatch(r"[0-9a-f]{64}", old_sha) is None:
                raise ValueError("authority group old hash is invalid")
            old_raw = _authority_regular_file_bytes(
                transaction_dir / backup_name, "authority group backup"
            )
            if len(old_raw) != member["old_bytes"] or sha256(old_raw) != old_sha:
                raise ValueError("authority group backup hash mismatch")
            seen_artifacts.add(backup_name)
        else:
            if old_sha is not None or member["old_bytes"] != 0:
                raise ValueError("authority group absent member has an old hash")
            if _path_lexists(transaction_dir / backup_name):
                raise ValueError("authority group absent member has a backup")
        new_raw: bytes | None = None
        new_sha = member.get("new_sha256")
        staging_path = transaction_dir / staging_name
        if member["new_exists"]:
            if not isinstance(new_sha, str) or re.fullmatch(r"[0-9a-f]{64}", new_sha) is None:
                raise ValueError("authority group new hash is invalid")
            new_raw = _authority_regular_file_bytes(
                staging_path, "authority group staging member"
            )
            if len(new_raw) != member["new_bytes"] or sha256(new_raw) != new_sha:
                raise ValueError("authority group staging hash mismatch")
            seen_artifacts.add(staging_name)
        elif new_sha is not None or member["new_bytes"] != 0 or _path_lexists(staging_path):
            raise ValueError("authority group absent new member has staging bytes")
        target = parent / target_name
        target_sha = ""
        if _path_lexists(target):
            target_sha = sha256(
                _authority_regular_file_bytes(target, "authority group target")
            )
            permitted_hashes: set[str] = set()
            if new_raw is not None:
                permitted_hashes.add(str(new_sha))
            if old_raw is not None:
                permitted_hashes.add(str(old_sha))
            if target_sha not in permitted_hashes:
                raise ValueError("authority group target hash is outside journal state")
        else:
            if old_raw is not None:
                raise ValueError("authority group missing target is outside journal state")
            target_sha = ""
        members.append((target, old_raw, new_raw, str(old_sha or ""), str(new_sha or "")))
    actual_artifacts = {child.name for child in transaction_dir.iterdir()}
    expected_artifacts = seen_artifacts | {"commit.new"}
    if actual_artifacts != expected_artifacts:
        raise ValueError("authority group transaction contains unknown artifacts")
    next_commit_raw = _authority_regular_file_bytes(
        transaction_dir / "commit.new", "authority next commit"
    )
    next_commit = _parse_authority_commit(next_commit_raw)
    if (
        sha256(next_commit_raw) != journal["next_commit_sha256"]
        or next_commit["transaction_id"] != transaction_id
        or next_commit["role"] != journal["role"]
        or next_commit["generation"] != journal["next_generation"]
    ):
        raise ValueError("authority next commit binding is invalid")
    journal_old_descriptors = [
        {
            "target": member["target"],
            "exists": member["old_exists"],
            "bytes": member["old_bytes"],
            "sha256": member["old_sha256"],
        }
        for member in journal["members"]
    ]
    journal_new_descriptors = [
        {
            "target": member["target"],
            "exists": member["new_exists"],
            "bytes": member["new_bytes"],
            "sha256": member["new_sha256"],
        }
        for member in journal["members"]
    ]
    if next_commit["members"] != journal_new_descriptors:
        raise ValueError("authority next commit members do not match journal")
    commit_path = parent / AUTHORITY_GROUP_COMMIT_NAME
    current_commit_raw = _authority_regular_file_bytes(
        commit_path, "authority group commit"
    )
    current_commit = _parse_authority_commit(current_commit_raw)
    current_commit_sha = sha256(current_commit_raw)
    if current_commit_sha == journal["base_commit_sha256"]:
        if (
            current_commit["generation"] != journal["base_generation"]
            or current_commit["members"] != journal_old_descriptors
        ):
            raise ValueError("authority base commit does not match journal")
        desired_index = 1
        desired_commit = current_commit
    elif current_commit_sha == journal["next_commit_sha256"]:
        if current_commit != next_commit:
            raise ValueError("authority committed pointer does not match staged commit")
        desired_index = 2
        desired_commit = next_commit
    else:
        raise RuntimeError("authority commit pointer is outside journal state")
    for target, old_raw, new_raw, _old_sha, _new_sha in members:
        desired_raw = old_raw if desired_index == 1 else new_raw
        if desired_raw is None:
            if _path_lexists(target):
                target.unlink()
        else:
            _replace_bytes_atomic(
                target,
                desired_raw,
                temporary_prefix=AUTHORITY_GROUP_TARGET_STAGING_PREFIX,
            )
    for target, old_raw, new_raw, old_sha, new_sha in members:
        desired_raw = old_raw if desired_index == 1 else new_raw
        desired_sha = old_sha if desired_index == 1 else new_sha
        if desired_raw is None:
            if _path_lexists(target):
                raise RuntimeError("authority group recovery did not remove target")
        elif sha256(_authority_regular_file_bytes(target, "authority group target")) != desired_sha:
            raise RuntimeError("authority group recovery hash mismatch")
    _validate_authority_closure(parent, desired_commit)
    journal_path.unlink()
    shutil.rmtree(transaction_dir)
    _cleanup_orphan_authority_group_transactions(parent)
    return True


def load_authoritative_metadata_member(parent: Path, name: str) -> dict[str, Any]:
    """Read one committed metadata member without repairing or bootstrapping state."""
    parent = Path(parent)
    if name not in AUTHORITY_GROUP_TARGET_NAMES:
        raise ValueError("unknown authority metadata member")
    if _is_link_or_reparse(parent) or not parent.is_dir():
        raise ValueError("authority parent must be an existing real directory")
    if _path_lexists(parent / AUTHORITY_GROUP_JOURNAL_NAME):
        raise RuntimeError("authority journal requires recovery before metadata consumption")
    if any(
        path.name not in {AUTHORITY_GROUP_JOURNAL_NAME, AUTHORITY_GROUP_COMMIT_NAME}
        for path in parent.glob(AUTHORITY_GROUP_TRANSACTION_PREFIX + "*")
    ):
        raise RuntimeError("authority transaction residue blocks metadata consumption")
    for prefix in (
        AUTHORITY_GROUP_JOURNAL_STAGING_PREFIX,
        AUTHORITY_GROUP_COMMIT_STAGING_PREFIX,
        AUTHORITY_GROUP_TARGET_STAGING_PREFIX,
    ):
        if any(parent.glob(prefix + "*")):
            raise RuntimeError("authority staging residue blocks metadata consumption")
    commit_path = parent / AUTHORITY_GROUP_COMMIT_NAME
    if not _path_lexists(commit_path):
        raise RuntimeError("authority commit is missing; explicit finalize migration is required")
    commit = _parse_authority_commit(
        _authority_regular_file_bytes(commit_path, "authority group commit")
    )
    closure = _validate_authority_closure(parent, commit)
    raw = closure[name]
    if raw is None:
        raise RuntimeError("requested authority metadata member is absent")
    payload = _parse_json_strict(raw.decode("utf-8"), name)
    if not isinstance(payload, dict):
        raise ValueError("authority metadata member must contain a JSON object")
    return payload


def _write_json_group_atomic(
    entries: Sequence[tuple[Path, Any]],
    *,
    transaction_id: str | None = None,
    require_run_state_binding: bool = False,
) -> None:
    """Commit the complete authority closure through one generation pointer."""
    normalized = [(Path(path), payload) for path, payload in entries]
    if not normalized:
        raise ValueError("metadata authority group must not be empty")
    parents = {path.parent.resolve(strict=True) for path, _payload in normalized}
    if len(parents) != 1:
        raise ValueError("metadata authority group must share one parent directory")
    parent = next(iter(parents))
    if require_run_state_binding:
        if (
            not isinstance(transaction_id, str)
            or re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None
        ):
            raise ValueError("required run-state transaction ID is invalid")
        run_journal_path = parent / RUN_STATE_JOURNAL_NAME
        if not _path_lexists(run_journal_path):
            raise RuntimeError("required run-state journal is missing")
        run_journal = _parse_run_state_journal(
            _authority_regular_file_bytes(
                run_journal_path, "required run-state journal"
            )
        )
        if (
            run_journal["transaction_id"] != transaction_id
            or run_journal["state"] != "PREPARED"
        ):
            raise RuntimeError("required run-state journal binding mismatch")
    _recover_authority_group_journal(parent)
    _validate_authority_target_names({path.name for path, _payload in normalized})
    base_commit_raw, base_commit = _load_or_bootstrap_authority_commit(parent)
    old_members = _validate_authority_closure(parent, base_commit)
    requested_payloads = {path.name: payload for path, payload in normalized}
    requested_raw = {
        name: _canonical_json_bytes(payload)
        for name, payload in requested_payloads.items()
    }
    if len(set(requested_raw.values())) != 1:
        raise ValueError("active authority pair payloads must be byte-identical")
    new_members = dict(old_members)
    for path, _payload in normalized:
        if path.parent.resolve(strict=True) != parent:
            raise ValueError("metadata authority group parent drifted")
        if len([candidate for candidate, _ in normalized if candidate == path]) != 1:
            raise ValueError("metadata authority group repeats a path")
        new_members[path.name] = requested_raw[path.name]
    role = (
        "SUCCESS"
        if {path.name for path, _payload in normalized}
        == {"finalization_metadata.json", "latest_attempt_metadata.json"}
        else "FAILED_ATTEMPT"
    )
    transaction_id = transaction_id or _authority_group_transaction_id()
    if re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None:
        raise ValueError("authority transaction ID is invalid")
    transaction_dir = parent / (AUTHORITY_GROUP_TRANSACTION_PREFIX + transaction_id)
    transaction_dir.mkdir()
    journal_members: list[dict[str, Any]] = []
    try:
        for index, target_name in enumerate(AUTHORITY_GROUP_TARGET_NAMES):
            old_raw = old_members[target_name]
            new_raw = new_members[target_name]
            backup_name = f"member-{index}.old"
            staging_name = f"member-{index}.new"
            if old_raw is not None:
                _replace_bytes_atomic(
                    transaction_dir / backup_name,
                    old_raw,
                    temporary_prefix=AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX,
                )
            if new_raw is not None:
                _replace_bytes_atomic(
                    transaction_dir / staging_name,
                    new_raw,
                    temporary_prefix=AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX,
                )
            journal_members.append(
                {
                    "target": target_name,
                    "old_exists": old_raw is not None,
                    "old_sha256": sha256(old_raw) if old_raw is not None else None,
                    "old_bytes": len(old_raw) if old_raw is not None else 0,
                    "new_exists": new_raw is not None,
                    "new_sha256": sha256(new_raw) if new_raw is not None else None,
                    "new_bytes": len(new_raw) if new_raw is not None else 0,
                    "backup": backup_name,
                    "staging": staging_name,
                }
            )
        next_commit = _authority_commit_payload(
            generation=int(base_commit["generation"]) + 1,
            transaction_id=transaction_id,
            role=role,
            members=new_members,
        )
        next_commit_raw = _canonical_json_bytes(next_commit)
        _replace_bytes_atomic(
            transaction_dir / "commit.new",
            next_commit_raw,
            temporary_prefix=AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX,
        )
        _bind_run_state_next(
            parent,
            transaction_id,
            next_commit_raw,
            next_commit,
            require_journal=require_run_state_binding,
        )
        journal = {
            "schema_version": AUTHORITY_GROUP_JOURNAL_SCHEMA,
            "transaction_id": transaction_id,
            "state": "PREPARED",
            "role": role,
            "base_generation": base_commit["generation"],
            "next_generation": next_commit["generation"],
            "base_commit_sha256": sha256(base_commit_raw),
            "next_commit_sha256": sha256(next_commit_raw),
            "members": journal_members,
        }
        _replace_bytes_atomic(
            parent / AUTHORITY_GROUP_JOURNAL_NAME,
            (json.dumps(journal, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                "utf-8"
            ),
            temporary_prefix=AUTHORITY_GROUP_JOURNAL_STAGING_PREFIX,
        )
        for target_name in AUTHORITY_GROUP_TARGET_NAMES:
            target = parent / target_name
            new_raw = new_members[target_name]
            if new_raw is None:
                if _path_lexists(target):
                    target.unlink()
            else:
                _replace_bytes_atomic(
                    target,
                    new_raw,
                    temporary_prefix=AUTHORITY_GROUP_TARGET_STAGING_PREFIX,
                )
        for target_name in AUTHORITY_GROUP_TARGET_NAMES:
            target = parent / target_name
            new_raw = new_members[target_name]
            if new_raw is None:
                if _path_lexists(target):
                    raise RuntimeError("metadata authority group publish presence mismatch")
            elif sha256(_authority_regular_file_bytes(target, "metadata authority member")) != sha256(new_raw):
                raise RuntimeError("metadata authority group publish hash mismatch")
        _replace_bytes_atomic(
            parent / AUTHORITY_GROUP_COMMIT_NAME,
            next_commit_raw,
            temporary_prefix=AUTHORITY_GROUP_COMMIT_STAGING_PREFIX,
        )
        _validate_authority_closure(parent, next_commit)
        (parent / AUTHORITY_GROUP_JOURNAL_NAME).unlink()
        try:
            shutil.rmtree(transaction_dir)
        except OSError:
            pass
    except BaseException as publication_error:
        committed = False
        try:
            _recover_authority_group_journal(parent)
            if _path_lexists(parent / AUTHORITY_GROUP_COMMIT_NAME):
                recovered_commit = _parse_authority_commit(
                    _authority_regular_file_bytes(
                        parent / AUTHORITY_GROUP_COMMIT_NAME,
                        "authority group commit",
                    )
                )
                committed = (
                    recovered_commit["transaction_id"] == transaction_id
                    and recovered_commit["generation"] == next_commit["generation"]
                )
        except BaseException as rollback_error:
            raise RuntimeError("metadata authority group rollback failed") from rollback_error
        try:
            setattr(
                publication_error,
                "_humanize_authority_generation_committed",
                committed,
            )
        except Exception:
            pass
        raise


def _spreadsheet_safe_csv_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution without altering ordinary cells."""
    if not isinstance(value, str) or not value:
        return value
    if value[0] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {
                field: _spreadsheet_safe_csv_cell(row.get(field, ""))
                for field in fields
            }
            for row in rows
        )


def _load_previous_accepted_units(path: Path) -> set[str]:
    """Read current or explicit legacy final-ledger rows without heuristics."""
    rows = _load_csv(path)
    if not rows:
        return set()
    required = {"unit_id", "status"}
    fields = set(rows[0])
    missing = sorted(required - fields)
    if missing:
        raise ValueError(
            "legacy final ledger requires reprepare: missing columns "
            + ",".join(missing)
        )
    seen: set[str] = set()
    accepted: set[str] = set()
    allowed_statuses = {
        "PENDING",
        "IN_PROGRESS",
        "DONE",
        "NO_CHANGE",
        "SKIPPED_PROTECTED",
        "SKIPPED_GARBLED",
        "UNRESOLVED",
        "CHANGED_AFTER_SNAPSHOT",
    }
    for row in rows:
        unit_id = row["unit_id"]
        status = row["status"]
        if not unit_id or unit_id in seen:
            raise ValueError("final ledger unit_id is blank or duplicated")
        seen.add(unit_id)
        if status not in allowed_statuses:
            raise ValueError("final ledger contains an unsupported status")
        if status in {"DONE", "NO_CHANGE"}:
            accepted.add(unit_id)
    return accepted


def _second_pass_tree_hash(root: Path) -> str:
    records = [
        {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256(path.read_bytes()),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file()
    ]
    if not records:
        raise ValueError("second-pass convergence cannot bind an empty rendered tree")
    return sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _load_second_pass_verifier() -> Any:
    path = SCRIPT_DIR / "verify_humanize_second_pass.py"
    raw = path.read_bytes()
    module_name = "_humanize_second_pass_verifier_runtime_" + sha256(raw)[:16]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load the second-pass verifier")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def _validate_second_pass_receipt(
    receipt_path: Path,
    *,
    snapshot_id: str,
    rendered_root: Path,
    rendered_manifest_path: Path,
    voice_binding_sha256: str,
    scene: str,
) -> dict[str, Any]:
    receipt = _load_json(receipt_path)
    if not isinstance(receipt, dict):
        raise ValueError("second-pass receipt must be a strict JSON object")
    expected_keys = {
        "schema_version",
        "status",
        "first_run_snapshot_id",
        "second_run_snapshot_id",
        "first_rendered_manifest_sha256",
        "first_rendered_tree_sha256",
        "second_rendered_tree_sha256",
        "second_prepare_integrity_sha256",
        "second_finalization_metadata_sha256",
        "voice_binding_sha256",
        "scene",
        "units_total",
        "all_units_no_change",
        "second_output_equals_first",
        "generator_projection_tree_sha256",
        "evidence_roots",
        "evidence_artifacts",
        "fresh_processes",
        "evidence_cap",
        "claims",
        "receipt_sha256",
    }
    if set(receipt) != expected_keys:
        raise ValueError("second-pass receipt fields mismatch")
    if receipt.get("schema_version") != SECOND_PASS_RECEIPT_SCHEMA:
        raise ValueError("second-pass receipt schema mismatch")
    payload = dict(receipt)
    stored_hash = payload.pop("receipt_sha256", None)
    rebuilt_hash = sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
    if stored_hash != rebuilt_hash:
        raise ValueError("second-pass receipt self-hash mismatch")
    if receipt.get("status") != "PASS" or receipt.get("evidence_cap") != "E2":
        raise ValueError("second-pass receipt is not a PASS/E2 receipt")
    if receipt.get("first_run_snapshot_id") != snapshot_id:
        raise ValueError("second-pass receipt snapshot binding mismatch")
    if receipt.get("first_rendered_manifest_sha256") != sha256(
        rendered_manifest_path.read_bytes()
    ):
        raise ValueError("second-pass receipt rendered manifest binding mismatch")
    current_tree = _second_pass_tree_hash(rendered_root)
    if (
        receipt.get("first_rendered_tree_sha256") != current_tree
        or receipt.get("second_rendered_tree_sha256") != current_tree
    ):
        raise ValueError("second-pass receipt rendered tree binding mismatch")
    if receipt.get("voice_binding_sha256") != voice_binding_sha256:
        raise ValueError("second-pass receipt Voice binding mismatch")
    if str(receipt.get("scene", "")).upper() != str(scene).upper():
        raise ValueError("second-pass receipt scene binding mismatch")
    units_total = receipt.get("units_total")
    processes = receipt.get("fresh_processes")
    if (
        not isinstance(units_total, int)
        or isinstance(units_total, bool)
        or units_total < 1
        or not isinstance(processes, list)
        or len(processes) != units_total
        or receipt.get("all_units_no_change") is not True
        or receipt.get("second_output_equals_first") is not True
    ):
        raise ValueError("second-pass receipt convergence counters are invalid")
    unit_ids: set[str] = set()
    for index, process in enumerate(processes):
        if not isinstance(process, dict):
            raise ValueError(f"second-pass fresh_processes[{index}] is invalid")
        unit_id = process.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in unit_ids:
            raise ValueError("second-pass receipt repeats or omits a unit id")
        unit_ids.add(unit_id)
        if (
            process.get("decision") != "NO_CHANGE"
            or process.get("fresh_context") is not True
            or process.get("new_process_observed") is not True
            or process.get("filesystem_isolation_verified") is not False
            or process.get("evidence_cap") != "E2"
        ):
            raise ValueError(f"second-pass process evidence is not converged/fresh: {unit_id}")
        for field in (
            "runner_receipt_sha256",
            "run_record_sha256",
            "run_seal_sha256",
            "output_sha256",
            "projection_tree_sha256",
        ):
            if not isinstance(process.get(field), str) or not re.fullmatch(
                r"[0-9a-f]{64}", str(process.get(field))
            ):
                raise ValueError(f"second-pass process hash is invalid: {unit_id}:{field}")
    claims = receipt.get("claims")
    if claims != {
        "fresh_process_per_unit_observed": True,
        "expected_outcome_exposed": False,
        "filesystem_isolation_verified": False,
        "oracle_unreachable_verified": False,
        "human_identity_verified": False,
        "academic_correctness": "NOT_EVALUATED",
    }:
        raise ValueError("second-pass receipt claims exceed the local trust boundary")
    roots = receipt.get("evidence_roots")
    if not isinstance(roots, dict) or set(roots) != {
        "first_run",
        "second_run",
        "cases_root",
        "trials_root",
        "rewrites_root",
    }:
        raise ValueError("second-pass receipt evidence roots are invalid")
    resolved_roots: dict[str, Path] = {}
    for key, value in roots.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"second-pass receipt evidence root is invalid: {key}")
        resolved_roots[key] = Path(value).resolve(strict=True)
    if resolved_roots["first_run"] != rendered_manifest_path.parent.resolve(strict=True):
        raise ValueError("second-pass receipt first-run evidence root mismatch")
    evidence_artifacts = receipt.get("evidence_artifacts")
    if not isinstance(evidence_artifacts, dict) or set(evidence_artifacts) != {
        "plan_sha256",
        "collection_sha256",
        "cases_tree_sha256",
        "trials_tree_sha256",
        "rewrites_tree_sha256",
    }:
        raise ValueError("second-pass receipt evidence artifact fields are invalid")
    for key, value in evidence_artifacts.items():
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"second-pass receipt evidence artifact hash is invalid: {key}")
    verifier = _load_second_pass_verifier()
    live_receipt = verifier.verify_second_pass(
        resolved_roots["first_run"],
        resolved_roots["second_run"],
        resolved_roots["cases_root"],
        resolved_roots["trials_root"],
        resolved_roots["rewrites_root"],
    )
    if live_receipt != receipt:
        raise ValueError("second-pass receipt does not match live revalidated evidence")
    return {
        "status": "PASS",
        "receipt_sha256": stored_hash,
        "path": str(receipt_path.resolve()),
        "units_total": units_total,
        "evidence_cap": "E2",
        "filesystem_isolation_verified": False,
        "oracle_unreachable_verified": False,
    }


VOICE_UNIT_FIELDS = (
    "voice_profile_id",
    "voice_profile_revision",
    "voice_profile_confidence",
    "voice_profile_kind",
    "voice_profile_source",
    "voice_profile_binding_scene",
    "voice_profile_sha256",
    "voice_default_disclosure",
)

AUTO_VOICE_BINDING_FIELDS = {
    "mode",
    "requested_scene",
    "scene_binding_status",
    "profile_source",
    "profile_set_sha256",
    "voice_default_disclosure",
    "voice_evidence_status",
    "profiles",
}
PROFILE_SET_ENTRY_FIELDS = {
    "path",
    "profile_id",
    "revision",
    "profile_kind",
    "binding_scene",
    "profile_sha256",
}
SINGLE_VOICE_BINDING_FIELDS = {
    "profile_source",
    "source_path",
    "binding_scene",
    "profile_binding_scene",
    "voice_profile_binding_scene",
    "requested_scene",
    "scene_binding_status",
    "voice_profile_id",
    "voice_profile_revision",
    "voice_profile_confidence",
    "voice_profile_kind",
    "voice_profile_sha256",
    "voice_default_disclosure",
    "voice_evidence_status",
}


def _validate_frozen_voice_evidence(
    profile: dict[str, Any],
    manifest_path: Path,
    spec_path: Path,
) -> dict[str, Any]:
    manifest = preparer.voice_profile_validator.validate_manifest_object(
        voice_profiles._load_json_strict(manifest_path)
    )
    preparer.voice_profile_validator.validate_profile_manifest_binding(profile, manifest)
    spec = voice_profiles._load_json_strict(spec_path)
    voice_profiles._validate_spec(spec)
    spec_sha256 = voice_profiles._sha256_bytes(
        voice_profiles._canonical_json_bytes(spec)
    )
    if spec_sha256 != manifest["sample_spec_sha256"]:
        raise ValueError("frozen voice sample spec does not match manifest")
    return manifest


def _validate_voice_profile_binding(
    run_dir: Path,
    metadata: dict[str, Any],
    units: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Validate frozen single/Profile-set bindings independently of the seal."""
    requested_scene = str(metadata.get("scene", "")).upper()
    if requested_scene not in {"AUTO", "COURSE", "MODELING", "RESEARCH", "GENERAL"}:
        raise ValueError("run metadata scene is invalid")
    metadata_binding = metadata.get("voice_binding")
    if not isinstance(metadata_binding, dict):
        raise ValueError("run_metadata.json has no voice_binding")

    if requested_scene == "AUTO":
        if set(metadata_binding) != AUTO_VOICE_BINDING_FIELDS:
            raise ValueError("voice Profile set metadata keys mismatch")
        profile_set_path = run_dir / "voice_profile_set.json"
        if not profile_set_path.is_file():
            raise ValueError("missing voice_profile_set.json")
        profile_set = _load_json(profile_set_path)
        if not isinstance(profile_set, dict):
            raise ValueError("voice Profile set must be an object")
        expected_set_keys = {
            "schema_version",
            "requested_scene",
            "profile_source",
            "profiles",
            "claims",
            "profile_set_sha256",
        }
        if set(profile_set) != expected_set_keys:
            raise ValueError("voice Profile set keys mismatch")
        if (
            profile_set.get("schema_version") != "humanize-voice-profile-set/v1"
            or profile_set.get("requested_scene") != "AUTO"
            or profile_set.get("profile_source") != "SCENE_DEFAULT_SET"
        ):
            raise ValueError("voice Profile set identity is invalid")
        if profile_set.get("claims") != {
            "personal_voice_claim_allowed": False,
            "identity_verified": False,
        }:
            raise ValueError("voice Profile set claims exceed the local trust boundary")
        set_payload = dict(profile_set)
        declared_set_sha = set_payload.pop("profile_set_sha256", None)
        actual_set_sha = sha256(_canonical_json(set_payload).encode("utf-8"))
        if declared_set_sha != actual_set_sha:
            raise ValueError("voice Profile set self-hash mismatch")
        if (
            metadata_binding.get("mode") != "PROFILE_SET"
            or metadata_binding.get("requested_scene") != "AUTO"
            or metadata_binding.get("scene_binding_status") != "UNIT_ROUTED"
            or metadata_binding.get("profile_source") != "SCENE_DEFAULT_SET"
            or metadata_binding.get("profile_set_sha256") != actual_set_sha
            or metadata_binding.get("voice_evidence_status") != "DETERMINISTIC_DEFAULT_SET"
        ):
            raise ValueError("voice Profile set metadata mismatch")
        entries = profile_set.get("profiles")
        expected_scenes = {"GENERAL", "COURSE", "MODELING", "RESEARCH"}
        if not isinstance(entries, dict) or set(entries) != expected_scenes:
            raise ValueError("voice Profile set scenes mismatch")
        binding_entries = metadata_binding.get("profiles")
        if not isinstance(binding_entries, dict) or set(binding_entries) != expected_scenes:
            raise ValueError("voice Profile set binding entries mismatch")
        profiles: dict[str, dict[str, Any]] = {}
        bindings: dict[str, dict[str, Any]] = {}
        for scene in sorted(expected_scenes):
            entry = entries[scene]
            if not isinstance(entry, dict):
                raise ValueError(f"voice Profile set entry is invalid: {scene}")
            if set(entry) != PROFILE_SET_ENTRY_FIELDS:
                raise ValueError(f"voice Profile set entry keys mismatch: {scene}")
            expected_path = f"voice_profiles/{scene.lower()}.json"
            if entry.get("path") != expected_path:
                raise ValueError(f"voice Profile set path mismatch: {scene}")
            profile = voice_profiles.load_and_validate_profile(run_dir / expected_path)
            if profile.get("validation_status") != "PASS":
                raise ValueError(f"frozen voice Profile status is not PASS: {scene}")
            if (
                str(profile.get("binding_scene", "")).upper() != scene
                or profile.get("profile_kind") != "DEFAULT"
                or profile.get("profile_sha256") != entry.get("profile_sha256")
                or profile.get("profile_id") != entry.get("profile_id")
                or profile.get("revision") != entry.get("revision")
                or profile.get("profile_kind") != entry.get("profile_kind")
                or profile.get("binding_scene") != entry.get("binding_scene")
            ):
                raise ValueError(f"voice Profile set entry mismatch: {scene}")
            rebuilt = voice_profiles.build_scene_default_profile(scene)
            if _canonical_json(rebuilt) != _canonical_json(profile):
                raise ValueError(f"scene default voice profile differs from registry: {scene}")
            binding = binding_entries[scene]
            if not isinstance(binding, dict):
                raise ValueError(f"voice Profile binding is invalid: {scene}")
            expected_binding = preparer._voice_binding_from_profile(
                profile,
                requested_scene="AUTO",
                profile_source="SCENE_DEFAULT",
                source_path=expected_path,
                evidence_status="DETERMINISTIC_DEFAULT",
            )
            if _canonical_json(binding) != _canonical_json(expected_binding):
                raise ValueError(f"voice Profile binding mismatch: {scene}")
            profiles[scene] = profile
            bindings[scene] = binding
        for unit in units:
            scene = str(unit.get("scene", "")).upper()
            if scene not in bindings:
                raise ValueError(f"voice binding unit has invalid scene: {unit.get('unit_id', '')}")
            binding = bindings[scene]
            for key in VOICE_UNIT_FIELDS:
                expected = (
                    binding["profile_source"]
                    if key == "voice_profile_source"
                    else binding.get(key)
                )
                if unit.get(key) != expected:
                    raise ValueError(
                        f"voice binding unit mismatch: {unit.get('unit_id', '')}:{key}"
                    )
        return profiles, bindings, {
            "mode": "PROFILE_SET",
            "identity_sha256": actual_set_sha,
            "profile_set_sha256": actual_set_sha,
            "voice_profile_sha256": "",
            "voice_profile_manifest_sha256": "0" * 64,
            "voice_default_disclosure": True,
        }

    profile_path = run_dir / "voice_profile.json"
    if not profile_path.is_file():
        raise ValueError("missing voice_profile.json")
    profile = voice_profiles.load_and_validate_profile(profile_path)
    if profile.get("validation_status") != "PASS":
        raise ValueError("frozen voice Profile status is not PASS")
    binding = metadata_binding
    if set(binding) != SINGLE_VOICE_BINDING_FIELDS:
        raise ValueError("voice binding metadata keys mismatch")
    expected_binding = {
        "voice_profile_id": profile.get("profile_id"),
        "voice_profile_revision": profile.get("revision"),
        "voice_profile_confidence": profile.get("confidence"),
        "voice_profile_kind": profile.get("profile_kind"),
        "voice_profile_binding_scene": profile.get("binding_scene"),
        "voice_profile_sha256": profile.get("profile_sha256"),
        "voice_default_disclosure": bool(profile.get("defaults", {}).get("disclosure_required", False)),
    }
    for key, expected in expected_binding.items():
        if binding.get(key) != expected:
            raise ValueError(f"voice binding metadata mismatch: {key}")
    profile_source = str(binding.get("profile_source", ""))
    if profile_source not in {"SCENE_DEFAULT", "SUPPLIED"}:
        raise ValueError("invalid voice profile source")
    profile_scene = str(profile.get("binding_scene", "")).upper()
    if (
        str(binding.get("requested_scene", "")).upper() != requested_scene
        or str(binding.get("scene_binding_status", ""))
        != "BOUND"
        or str(binding.get("profile_binding_scene", "")).upper() != profile_scene
        or str(binding.get("voice_profile_binding_scene", "")).upper() != profile_scene
        or str(binding.get("binding_scene", "")).upper() != profile_scene
        or profile_scene != requested_scene
    ):
        raise ValueError("voice Profile scene binding mismatch")
    if profile.get("profile_kind") == "DEFAULT":
        scene = str(profile.get("binding_scene", "")).upper()
        evidence_status = binding.get("voice_evidence_status")
        if evidence_status == "DETERMINISTIC_DEFAULT":
            rebuilt = voice_profiles.build_scene_default_profile(scene)
            if _canonical_json(rebuilt) != _canonical_json(profile):
                raise ValueError("scene default voice profile differs from deterministic registry")
        elif evidence_status == "REBUILT_DEFAULT_PASS":
            manifest_path = run_dir / "voice_sample_manifest.json"
            spec_path = run_dir / "voice_sample_spec.json"
            if not manifest_path.is_file() or not spec_path.is_file():
                raise ValueError("evidence-bound default Profile artifact is missing")
            _validate_frozen_voice_evidence(profile, manifest_path, spec_path)
        else:
            raise ValueError("default voice evidence status is invalid")
    else:
        if profile_source != "SUPPLIED" or binding.get("voice_evidence_status") != "REBUILT_PASS":
            raise ValueError("personal voice profile lacks rebuilt evidence status")
        manifest_path = run_dir / "voice_sample_manifest.json"
        spec_path = run_dir / "voice_sample_spec.json"
        if not manifest_path.is_file() or not spec_path.is_file():
            raise ValueError("personal voice profile evidence artifact is missing")
        _validate_frozen_voice_evidence(profile, manifest_path, spec_path)
    for unit in units:
        for key in VOICE_UNIT_FIELDS:
            metadata_key = key
            if key == "voice_profile_source":
                expected = profile_source
            else:
                expected = binding.get(metadata_key)
            if unit.get(key) != expected:
                raise ValueError(f"voice binding unit mismatch: {unit.get('unit_id', '')}:{key}")
    return {requested_scene: profile}, {requested_scene: binding}, {
        "mode": "SINGLE",
        "identity_sha256": str(profile["profile_sha256"]),
        "profile_set_sha256": "",
        "voice_profile_sha256": str(profile["profile_sha256"]),
        "voice_profile_manifest_sha256": str(
            profile.get("sample_binding", {}).get("manifest_sha256", "")
        ),
        "voice_default_disclosure": bool(binding.get("voice_default_disclosure")),
    }


def _bundle_voice_binding_error(bundle: dict[str, Any], expected_sha256: str) -> str | None:
    if "voice_profile_sha256" not in bundle:
        return "voice_profile_hash_missing"
    value = bundle.get("voice_profile_sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        return "voice_profile_hash_invalid"
    if value != expected_sha256:
        return "voice_profile_hash_mismatch"
    return None


def _validate_scene_routing_policy(run_dir: Path, metadata: dict[str, Any]) -> Path:
    frozen_path = run_dir / "scene_routing_policy.json"
    frozen, frozen_sha = preparer.scene_router.load_policy(frozen_path)
    current, current_sha = preparer.scene_router.load_policy()
    if _canonical_json(frozen) != _canonical_json(current) or frozen_sha != current_sha:
        raise ValueError("scene routing policy changed after prepare")
    if (
        metadata.get("scene_routing_policy_sha256") != current_sha
        or metadata.get("scene_routing_policy_revision") != current.get("revision")
    ):
        raise ValueError("scene routing policy metadata mismatch")
    return preparer.scene_router.DEFAULT_POLICY


def _validate_structural_transaction_inventory(
    run_dir: Path,
    metadata: dict[str, Any],
    snapshot: dict[str, Any],
    file_manifest: Sequence[dict[str, str]],
    units: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    path = run_dir / "structural_transaction_inventory.json"
    if not path.is_file():
        if any(str(key).startswith("structural_transaction_") for key in metadata):
            raise ValueError("structural transaction metadata exists without inventory")
        return None
    inventory = _load_json(path)
    if not isinstance(inventory, dict):
        raise ValueError("invalid structural transaction inventory")
    rebuilt = preparer.build_structural_transaction_inventory(
        units,
        snapshot_id=str(snapshot.get("snapshot_id", "")),
        snapshot_sha256=sha256((run_dir / "snapshot.json").read_bytes()),
        file_sha256_by_id={
            str(record.get("file_id", "")): str(record.get("sha256", ""))
            for record in file_manifest
            if str(record.get("file_id", "")) and str(record.get("sha256", ""))
        },
        intensity=str(metadata.get("intensity", "")),
        scope=str(metadata.get("structural_transaction_scope", "NONE")),
    )
    if _canonical_json(inventory) != _canonical_json(rebuilt):
        raise ValueError("structural transaction inventory rebuild mismatch")
    return inventory


def _bundle_chunk_binding_error(bundle: dict[str, Any], unit: dict[str, Any]) -> str | None:
    if "unit_id" not in bundle:
        return "bundle_unit_id_missing"
    bundle_unit_id = bundle.get("unit_id")
    if not isinstance(bundle_unit_id, str) or not bundle_unit_id:
        return "bundle_unit_id_invalid"
    if bundle_unit_id != unit.get("unit_id"):
        return "bundle_unit_id_mismatch"
    if "chunk_binding_sha256" not in bundle:
        return "chunk_binding_hash_missing"
    binding_hash = bundle.get("chunk_binding_sha256")
    if not isinstance(binding_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", binding_hash):
        return "chunk_binding_hash_invalid"
    if binding_hash != unit.get("chunk_binding_sha256"):
        return "chunk_binding_hash_mismatch"
    return None


def _decode(raw: bytes, encoding: str) -> str:
    if encoding in {"utf-8", "utf-8-sig"}:
        return raw.decode("utf-8-sig")
    if encoding == "gb18030":
        return raw.decode("gb18030")
    raise ValueError(f"unsupported snapshot encoding: {encoding}")


def _encode(text: str, encoding: str, original_raw: bytes) -> bytes:
    if encoding == "utf-8-sig":
        return text.encode("utf-8-sig")
    if encoding == "utf-8":
        return text.encode("utf-8")
    if encoding == "gb18030":
        return text.encode("gb18030")
    return original_raw


def _rewrite_bundle(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        payload = _load_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"rewrite bundle must be an object: {path}")
        return payload
    return {
        "decision": "REWRITE",
        "masked_text": path.read_text(encoding="utf-8-sig"),
        "keep_reasons": {},
    }


def build_pristine_unit_rewrite_bundle(
    chunk: dict[str, Any],
    binding: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    """Rebuild the exact editable v4 template authorized by a frozen run."""

    if decision not in {"REWRITE", "NO_CHANGE"}:
        raise ValueError("pristine rewrite decision must be REWRITE or NO_CHANGE")
    unit_id = chunk.get("unit_id")
    if not isinstance(unit_id, str) or not SAFE_UNIT_ID_RE.fullmatch(unit_id):
        raise ValueError("pristine rewrite unit_id is invalid")
    if chunk.get("status") != "PENDING":
        raise ValueError(f"pristine rewrite unit is not PENDING: {unit_id}")
    if not isinstance(chunk.get("masked_text"), str):
        raise ValueError(f"pristine rewrite masked_text is invalid: {unit_id}")
    _validate_long_authoring_binding_shape(binding)
    source_binding = binding["source_binding"]
    voice_binding = binding["voice_binding"]
    if source_binding.get("chunk_binding_sha256") != chunk.get(
        "chunk_binding_sha256"
    ):
        raise ValueError(f"pristine rewrite chunk binding mismatch: {unit_id}")
    if voice_binding.get("profile_sha256") != chunk.get("voice_profile_sha256"):
        raise ValueError(f"pristine rewrite voice binding mismatch: {unit_id}")

    bundle: dict[str, Any] = {
        "schema_version": UNIT_REWRITE_BUNDLE_SCHEMA,
        "unit_id": unit_id,
        "chunk_binding_sha256": chunk["chunk_binding_sha256"],
        "decision": decision,
        "voice_profile_sha256": chunk["voice_profile_sha256"],
        "authoring_binding": binding,
        "keep_reasons": {},
        "template_field_edit_scope": None,
    }
    if decision == "REWRITE":
        bundle["masked_text"] = chunk["masked_text"]
        bundle["rewrite_intent"] = {
            "summary": REWRITE_INTENT_TODO,
            "operations": [],
            "source_spans": [],
            "target_signals": [],
        }
    else:
        bundle["reason"] = NO_CHANGE_REASON_TODO
        bundle["evidence_spans"] = []
    return bundle


def encode_pristine_unit_rewrite_bundle(
    chunk: dict[str, Any],
    binding: dict[str, Any],
    decision: str,
) -> bytes:
    """Encode pristine templates once so scaffold and finalizer cannot drift."""

    return (
        json.dumps(
            build_pristine_unit_rewrite_bundle(chunk, binding, decision),
            ensure_ascii=False,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def _validate_scaffold_preflight_summary(payload: Any, path: Path) -> None:
    expected = {
        "schema_version",
        "status",
        "integrity_status",
        "policy_status",
        "route_replay_status",
        "voice_binding_status",
        "live_source_status",
        "snapshot_id",
        "run_state_sha256",
        "prepare_integrity_sha256",
        "run_metadata_sha256",
        "policy_snapshot_sha256",
        "scene_routing_policy_sha256",
        "pending_units_total",
        "eligible_units_total",
        "source_change_units",
        "completion_claim_allowed",
        "preflight_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ValueError(f"invalid scaffold preflight summary: {path.name}")
    if payload.get("schema_version") != LONG_AUTHORING_PREFLIGHT_SCHEMA:
        raise ValueError(f"invalid scaffold preflight schema: {path.name}")
    if payload.get("status") != "PASS":
        raise ValueError(f"scaffold preflight did not pass: {path.name}")
    for field in (
        "integrity_status",
        "policy_status",
        "route_replay_status",
        "voice_binding_status",
    ):
        if payload.get(field) != "PASS":
            raise ValueError(f"invalid scaffold preflight gate: {path.name}")
    if payload.get("live_source_status") != "MATCH":
        raise ValueError(f"invalid scaffold live source status: {path.name}")
    for field in (
        "run_state_sha256",
        "prepare_integrity_sha256",
        "run_metadata_sha256",
        "policy_snapshot_sha256",
        "scene_routing_policy_sha256",
        "preflight_sha256",
    ):
        if not isinstance(payload.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", payload[field]
        ):
            raise ValueError(f"invalid scaffold preflight hash: {path.name}")
    if not isinstance(payload.get("snapshot_id"), str) or not payload["snapshot_id"]:
        raise ValueError(f"invalid scaffold preflight snapshot: {path.name}")
    for field in ("pending_units_total", "eligible_units_total"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid scaffold preflight count: {path.name}")
    if payload["eligible_units_total"] != payload["pending_units_total"]:
        raise ValueError(f"scaffold preflight eligibility mismatch: {path.name}")
    if payload.get("source_change_units") != []:
        raise ValueError(f"scaffold preflight contains source drift: {path.name}")
    if payload.get("completion_claim_allowed") is not False:
        raise ValueError(f"scaffold preflight completion claim is invalid: {path.name}")
    canonical = dict(payload)
    recorded_hash = canonical.pop("preflight_sha256")
    expected_hash = sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if recorded_hash != expected_hash:
        raise ValueError(f"scaffold preflight hash mismatch: {path.name}")


def _validate_scaffold_metadata(payload: Any, path: Path) -> None:
    """Validate, then ignore the metadata sidecar emitted by the scaffold tool.

    The sidecar is not a rewrite bundle.  It is nevertheless parsed strictly so
    a damaged or forged sidecar cannot be silently treated as harmless noise.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"invalid scaffold metadata: {path.name}")
    schema_version = payload.get("schema_version")
    if schema_version not in SCAFFOLD_METADATA_SCHEMAS:
        raise ValueError(f"invalid scaffold metadata schema: {path.name}")
    expected = {
        "schema_version",
        "run_dir_name",
        "decision",
        "pending_units_total",
        "templates_total",
        "completion_claim_allowed",
        "requires_manual_completion",
        "records",
    }
    if schema_version in {
        "humanize-rewrite-scaffold/v2",
        "humanize-rewrite-scaffold/v3",
        "humanize-rewrite-scaffold/v4",
        "humanize-rewrite-scaffold/v5",
    }:
        expected.add("decision_map")
    if schema_version in {
        "humanize-rewrite-scaffold/v3",
        "humanize-rewrite-scaffold/v4",
        "humanize-rewrite-scaffold/v5",
    }:
        expected.update({"metadata_scope", "template_hash_scope"})
    if schema_version == "humanize-rewrite-scaffold/v5":
        expected.add("preflight")
    if set(payload) != expected:
        raise ValueError(f"invalid scaffold metadata fields: {path.name}")
    if not isinstance(payload.get("run_dir_name"), str) or not payload["run_dir_name"]:
        raise ValueError(f"invalid scaffold metadata run_dir_name: {path.name}")
    if payload.get("decision") not in {"REWRITE", "NO_CHANGE", "MIXED", "EMPTY"}:
        raise ValueError(f"invalid scaffold metadata decision: {path.name}")
    for field in ("pending_units_total", "templates_total"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"invalid scaffold metadata count: {path.name}")
    if payload.get("completion_claim_allowed") is not False:
        raise ValueError(f"scaffold metadata completion claim must be false: {path.name}")
    if payload.get("requires_manual_completion") is not True:
        raise ValueError(f"scaffold metadata must require manual completion: {path.name}")
    if schema_version in {
        "humanize-rewrite-scaffold/v3",
        "humanize-rewrite-scaffold/v4",
        "humanize-rewrite-scaffold/v5",
    }:
        if payload.get("metadata_scope") != "SCAFFOLD_CREATION_TIME":
            raise ValueError(f"invalid scaffold metadata scope: {path.name}")
        if payload.get("template_hash_scope") != "ORIGINAL_TEMPLATE_BYTES":
            raise ValueError(f"invalid scaffold template hash scope: {path.name}")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"invalid scaffold metadata records: {path.name}")
    if payload["templates_total"] != len(records) or payload["pending_units_total"] != len(records):
        raise ValueError(f"scaffold metadata counts do not match records: {path.name}")
    decision_map = payload.get("decision_map")
    if schema_version in {
        "humanize-rewrite-scaffold/v2",
        "humanize-rewrite-scaffold/v3",
        "humanize-rewrite-scaffold/v4",
        "humanize-rewrite-scaffold/v5",
    }:
        if not isinstance(decision_map, dict):
            raise ValueError(f"invalid scaffold metadata decision_map: {path.name}")
    else:
        if payload["decision"] in {"MIXED", "EMPTY"}:
            raise ValueError(f"v1 scaffold metadata cannot use MIXED decision: {path.name}")
        decision_map = None
    seen: set[str] = set()
    seen_exact: set[str] = set()
    preflight = payload.get("preflight")
    if schema_version == "humanize-rewrite-scaffold/v5":
        _validate_scaffold_preflight_summary(preflight, path)
    for record in records:
        expected_record_fields = {
            "unit_id",
            "path",
            "decision",
            "template_sha256",
        }
        if schema_version == "humanize-rewrite-scaffold/v5":
            expected_record_fields.update(
                {
                    "authoring_binding_sha256",
                    "scene_requested",
                    "scene_resolved",
                    "scene_routing_decision",
                    "scene_routing_top_score",
                    "scene_routing_margin",
                    "source_span_sha256",
                    "chunk_binding_sha256",
                }
            )
        if not isinstance(record, dict) or set(record) != expected_record_fields:
            raise ValueError(f"invalid scaffold metadata record: {path.name}")
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or not SAFE_UNIT_ID_RE.fullmatch(unit_id):
            raise ValueError(f"invalid scaffold metadata unit_id: {path.name}")
        key = unit_id.casefold()
        if key in seen:
            raise ValueError(f"duplicate scaffold metadata unit_id: {path.name}")
        seen.add(key)
        seen_exact.add(unit_id)
        if decision_map is not None and decision_map.get(unit_id) != record.get("decision"):
            raise ValueError(f"scaffold metadata decision_map mismatch: {path.name}")
        if record.get("path") != f"{unit_id}.json":
            raise ValueError(f"scaffold metadata path mismatch: {path.name}")
        if record.get("decision") not in {"REWRITE", "NO_CHANGE"}:
            raise ValueError(f"invalid scaffold metadata record decision: {path.name}")
        if payload["decision"] != "MIXED" and record.get("decision") != payload["decision"]:
            raise ValueError(f"scaffold metadata decision mismatch: {path.name}")
        if not isinstance(record.get("template_sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", record["template_sha256"]
        ):
            raise ValueError(f"invalid scaffold metadata template hash: {path.name}")
        if schema_version == "humanize-rewrite-scaffold/v5":
            for hash_field in (
                "authoring_binding_sha256",
                "source_span_sha256",
                "chunk_binding_sha256",
            ):
                if not isinstance(record.get(hash_field), str) or not re.fullmatch(
                    r"[0-9a-f]{64}", record[hash_field]
                ):
                    raise ValueError(
                        f"invalid scaffold metadata binding hash: {path.name}"
                    )
            if record.get("scene_requested") not in {
                "AUTO",
                "GENERAL",
                "COURSE",
                "MODELING",
                "RESEARCH",
            } or record.get("scene_resolved") not in {
                "GENERAL",
                "COURSE",
                "MODELING",
                "RESEARCH",
            }:
                raise ValueError(f"invalid scaffold metadata scene: {path.name}")
            if record.get("scene_routing_decision") not in {
                "EXPLICIT",
                "ROUTED",
                "ROUTED_DOCUMENT_PRIOR",
                "FALLBACK_GENERAL",
            }:
                raise ValueError(
                    f"invalid scaffold metadata route decision: {path.name}"
                )
            for score_field in ("scene_routing_top_score", "scene_routing_margin"):
                score = record.get(score_field)
                if isinstance(score, bool) or not isinstance(score, int) or score < 0:
                    raise ValueError(
                        f"invalid scaffold metadata route score: {path.name}"
                    )
    if decision_map is not None and set(decision_map) != seen_exact:
        raise ValueError(f"scaffold metadata decision_map coverage mismatch: {path.name}")
    if payload["decision"] == "MIXED" and len(set(decision_map.values())) < 2:
        raise ValueError(f"scaffold metadata MIXED decision is not mixed: {path.name}")
    if payload["decision"] == "EMPTY" and records:
        raise ValueError(f"scaffold metadata EMPTY decision has records: {path.name}")


def _validate_scaffold_publication_commit(
    payload: Any,
    path: Path,
    metadata: dict[str, Any],
    metadata_path: Path,
) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "scaffold_schema_version",
        "scaffold_metadata_sha256",
        "completion_claim_allowed",
    }:
        raise ValueError(f"invalid scaffold publication commit: {path.name}")
    if payload.get("schema_version") != SCAFFOLD_PUBLICATION_COMMIT_SCHEMA:
        raise ValueError(f"invalid scaffold publication commit schema: {path.name}")
    if payload.get("scaffold_schema_version") != metadata.get("schema_version"):
        raise ValueError(f"scaffold publication commit schema mismatch: {path.name}")
    if payload.get("completion_claim_allowed") is not False:
        raise ValueError(f"scaffold publication commit cannot claim completion: {path.name}")
    recorded_hash = payload.get("scaffold_metadata_sha256")
    if not isinstance(recorded_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_hash):
        raise ValueError(f"invalid scaffold publication metadata hash: {path.name}")
    if sha256(metadata_path.read_bytes()) != recorded_hash:
        raise ValueError(f"scaffold publication metadata hash mismatch: {path.name}")


def _validate_scaffold_bundle_consistency(
    metadata: dict[str, Any],
    rewrites: dict[str, dict[str, Any]],
    path: Path,
    run_dir: Path | None = None,
    transactions: dict[str, dict[str, Any]] | None = None,
) -> None:
    records = metadata["records"]
    record_by_unit = {str(item["unit_id"]): item for item in records}
    schema_version = metadata["schema_version"]
    transaction_units: set[str] = set()
    if schema_version == "humanize-rewrite-scaffold/v5":
        for bundle in (transactions or {}).values():
            transaction_units.update(
                str(item["unit_id"]) for item in bundle["unit_bindings"]
            )
        overlap = sorted(set(rewrites) & transaction_units)
        if overlap:
            raise ValueError(
                "scaffold transaction member also has standalone bundle: "
                + ",".join(overlap)
            )
        submitted_units = set(rewrites) | transaction_units
    else:
        submitted_units = set(rewrites)
    if set(record_by_unit) != submitted_units:
        raise ValueError(f"scaffold metadata bundle coverage mismatch: {path.name}")
    preflight = metadata.get("preflight")
    authoritative: dict[str, Any] | None = None
    if schema_version == "humanize-rewrite-scaffold/v5" and run_dir is not None:
        authoritative = _validate_scaffold_run_binding(metadata, path, run_dir)
    for unit_id, record in record_by_unit.items():
        bundle = rewrites.get(unit_id)
        if bundle is None:
            if (
                schema_version != "humanize-rewrite-scaffold/v5"
                or unit_id not in transaction_units
            ):
                raise ValueError(
                    f"scaffold metadata bundle coverage mismatch: {unit_id}"
                )
            if record.get("decision") != "REWRITE":
                raise ValueError(
                    "scaffold transaction substitution requires REWRITE decision: "
                    + unit_id
                )
            continue
        if bundle.get("decision") != record["decision"]:
            raise ValueError(f"scaffold metadata bundle decision mismatch: {unit_id}")
        if "unit_id" in bundle and bundle.get("unit_id") != unit_id:
            raise ValueError(f"scaffold metadata bundle unit mismatch: {unit_id}")
        if schema_version != "humanize-rewrite-scaffold/v5":
            continue
        if bundle.get("schema_version") != UNIT_REWRITE_BUNDLE_SCHEMA:
            raise ValueError(f"v5 scaffold bundle schema mismatch: {unit_id}")
        binding = bundle.get("authoring_binding")
        _validate_long_authoring_binding_shape(binding)
        source = binding["source_binding"]
        route = binding["scene_route"]
        expected_record = {
            "authoring_binding_sha256": binding["authoring_binding_sha256"],
            "scene_requested": route["requested_scene"],
            "scene_resolved": route["resolved_scene"],
            "scene_routing_decision": route["status"],
            "scene_routing_top_score": route["top_score"],
            "scene_routing_margin": route["margin"],
            "source_span_sha256": source["source_span_sha256"],
            "chunk_binding_sha256": source["chunk_binding_sha256"],
        }
        mismatches = [
            field
            for field, expected in expected_record.items()
            if record.get(field) != expected
        ]
        if mismatches:
            raise ValueError(
                "scaffold metadata authoring binding mismatch: "
                + unit_id
                + ":"
                + ",".join(sorted(mismatches))
            )
        if bundle.get("chunk_binding_sha256") != source["chunk_binding_sha256"]:
            raise ValueError(f"scaffold bundle chunk binding mismatch: {unit_id}")
        if bundle.get("voice_profile_sha256") != binding["voice_binding"][
            "profile_sha256"
        ]:
            raise ValueError(f"scaffold bundle voice binding mismatch: {unit_id}")
        if authoritative is not None:
            expected_binding = authoritative["bindings"][unit_id]
            _validate_long_authoring_binding(binding, expected_binding)
            expected_chunk = authoritative["chunks"][unit_id]
            if bundle.get("chunk_binding_sha256") != expected_chunk.get(
                "chunk_binding_sha256"
            ):
                raise ValueError(
                    f"scaffold bundle prepared chunk binding mismatch: {unit_id}"
                )
            if bundle.get("voice_profile_sha256") != expected_chunk.get(
                "voice_profile_sha256"
            ):
                raise ValueError(
                    f"scaffold bundle prepared voice binding mismatch: {unit_id}"
                )
        assert isinstance(preflight, dict)
        global_mismatches = []
        for binding_field, preflight_field in (
            ("snapshot_id", "snapshot_id"),
            ("prepare_integrity_sha256", "prepare_integrity_sha256"),
            ("run_metadata_sha256", "run_metadata_sha256"),
            ("policy_snapshot_sha256", "policy_snapshot_sha256"),
        ):
            if binding.get(binding_field) != preflight.get(preflight_field):
                global_mismatches.append(binding_field)
        if route["policy_sha256"] != preflight.get("scene_routing_policy_sha256"):
            global_mismatches.append("scene_routing_policy_sha256")
        if global_mismatches:
            raise ValueError(
                "scaffold preflight binding mismatch: "
                + unit_id
                + ":"
                + ",".join(sorted(global_mismatches))
            )


def _validate_scaffold_run_binding(
    metadata: dict[str, Any],
    path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Rebind v5 creation-time globals to the authoritative prepared run."""

    run_dir = Path(run_dir).resolve(strict=True)
    if metadata.get("run_dir_name") != run_dir.name:
        raise ValueError(f"scaffold run directory binding mismatch: {path.name}")
    preflight = metadata.get("preflight")
    assert isinstance(preflight, dict)
    authoritative = validate_long_authoring_snapshot(run_dir)
    expected_summary = authoritative.get("summary")
    bindings = authoritative.get("bindings")
    chunks = authoritative.get("chunks")
    if (
        not isinstance(expected_summary, dict)
        or not isinstance(bindings, dict)
        or not isinstance(chunks, dict)
    ):
        raise ValueError(f"scaffold run binding source is invalid: {path.name}")
    immutable_summary_fields = (
        "schema_version",
        "integrity_status",
        "policy_status",
        "route_replay_status",
        "voice_binding_status",
        "snapshot_id",
        "run_state_sha256",
        "prepare_integrity_sha256",
        "run_metadata_sha256",
        "policy_snapshot_sha256",
        "scene_routing_policy_sha256",
        "pending_units_total",
        "eligible_units_total",
        "completion_claim_allowed",
    )
    mismatches = [
        field
        for field in immutable_summary_fields
        if preflight.get(field) != expected_summary.get(field)
    ]
    if mismatches:
        raise ValueError(
            "scaffold prepared-run binding mismatch: "
            + path.name
            + ":"
            + ",".join(sorted(mismatches))
        )
    pending_ids = set(bindings)
    record_by_unit = {
        str(record["unit_id"]): record for record in metadata["records"]
    }
    if set(record_by_unit) != pending_ids:
        raise ValueError(
            f"scaffold prepared-run unit coverage mismatch: {path.name}"
        )
    expected_count = len(pending_ids)
    if any(
        value != expected_count
        for value in (
            metadata.get("pending_units_total"),
            metadata.get("templates_total"),
            preflight.get("pending_units_total"),
            preflight.get("eligible_units_total"),
        )
    ):
        raise ValueError(
            f"scaffold prepared-run count mismatch: {path.name}"
        )

    for unit_id in sorted(pending_ids, key=str.casefold):
        record = record_by_unit[unit_id]
        binding = bindings[unit_id]
        chunk = chunks[unit_id]
        source = binding["source_binding"]
        route = binding["scene_route"]
        expected_record = {
            "authoring_binding_sha256": binding["authoring_binding_sha256"],
            "scene_requested": route["requested_scene"],
            "scene_resolved": route["resolved_scene"],
            "scene_routing_decision": route["status"],
            "scene_routing_top_score": route["top_score"],
            "scene_routing_margin": route["margin"],
            "source_span_sha256": source["source_span_sha256"],
            "chunk_binding_sha256": source["chunk_binding_sha256"],
            "template_sha256": sha256(
                encode_pristine_unit_rewrite_bundle(
                    chunk,
                    binding,
                    str(record["decision"]),
                )
            ),
        }
        record_mismatches = [
            field
            for field, expected_value in expected_record.items()
            if record.get(field) != expected_value
        ]
        if record_mismatches:
            raise ValueError(
                "scaffold prepared-run record mismatch: "
                + unit_id
                + ":"
                + ",".join(sorted(record_mismatches))
            )
    return authoritative


def _normalized_author_block(lines: Sequence[str]) -> dict[str, Any] | None:
    normalized = " ".join(" ".join(lines).split())
    han_chars = len(re.findall(r"[\u3400-\u9fff]", normalized))
    if han_chars < 8:
        return None
    return {
        "kind": "AUTHOR",
        "identity": sha256(normalized.encode("utf-8")),
        "text": normalized,
        "han_chars": han_chars,
    }


def _paragraph_order_elements(masked_text: str) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    for paragraph in preparer.structural_paragraph_blocks(masked_text):
        current: list[str] = []
        for line in paragraph.splitlines():
            stripped = line.strip()
            protected_ids = [
                match.group("id")
                for match in preparer.PROTECTED_PLACEHOLDER_RE.finditer(stripped)
            ]
            protected_only = bool(protected_ids) and not preparer.PROTECTED_PLACEHOLDER_RE.sub(
                "", stripped
            ).strip()
            if protected_only:
                author = _normalized_author_block(current)
                if author is not None:
                    elements.append(author)
                current = []
                elements.append(
                    {
                        "kind": "PROTECTED",
                        "identity": "|".join(protected_ids),
                        "text": "",
                        "han_chars": 0,
                    }
                )
                continue
            current.append(line)
        author = _normalized_author_block(current)
        if author is not None:
            elements.append(author)
    return elements


def _author_paragraph_count(masked_text: str) -> int:
    count = 0
    for paragraph in preparer.structural_paragraph_blocks(masked_text):
        visible_lines = [
            line
            for line in paragraph.splitlines()
            if not PURE_TEX_STRUCTURE_LINE_RE.match(line)
        ]
        visible = preparer.PROTECTED_PLACEHOLDER_RE.sub(
            "", "\n".join(visible_lines)
        )
        if HAN_RE.search(visible):
            count += 1
    return count


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    length_ratio = min(len(left), len(right)) / max(len(left), len(right))
    if length_ratio < 0.65:
        return 0.0
    return difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()


def _element_matches(
    before: Sequence[dict[str, Any]],
    after: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    used_before: set[int] = set()
    used_after: set[int] = set()
    for kind in ("PROTECTED", "AUTHOR"):
        before_counts = Counter(
            item["identity"] for item in before if item["kind"] == kind
        )
        after_counts = Counter(
            item["identity"] for item in after if item["kind"] == kind
        )
        after_positions = {
            item["identity"]: index
            for index, item in enumerate(after)
            if item["kind"] == kind and after_counts[item["identity"]] == 1
        }
        for before_index, item in enumerate(before):
            identity = item["identity"]
            if (
                item["kind"] == kind
                and before_counts[identity] == 1
                and identity in after_positions
            ):
                after_index = after_positions[identity]
                used_before.add(before_index)
                used_after.add(after_index)
                matches.append(
                    {
                        "before_index": before_index,
                        "after_index": after_index,
                        "kind": kind,
                        "method": "EXACT",
                        "similarity": 1.0,
                        "before_sha256": identity if kind == "AUTHOR" else "",
                        "protected_ids": identity.split("|") if kind == "PROTECTED" else [],
                    }
                )

    before_authors = [
        index
        for index, item in enumerate(before)
        if item["kind"] == "AUTHOR" and index not in used_before
    ]
    after_authors = [
        index
        for index, item in enumerate(after)
        if item["kind"] == "AUTHOR" and index not in used_after
    ]
    scores = {
        (left, right): _similarity(before[left]["text"], after[right]["text"])
        for left in before_authors
        for right in after_authors
    }
    for left in before_authors:
        ranked_right = sorted(
            ((scores[(left, right)], right) for right in after_authors),
            reverse=True,
        )
        if not ranked_right:
            continue
        score, right = ranked_right[0]
        second_score = ranked_right[1][0] if len(ranked_right) > 1 else 0.0
        ranked_left = sorted(
            ((scores[(other, right)], other) for other in before_authors),
            reverse=True,
        )
        if not ranked_left or ranked_left[0][1] != left:
            continue
        reverse_second = ranked_left[1][0] if len(ranked_left) > 1 else 0.0
        unambiguous = score >= 0.93 or (
            score >= 0.82
            and score - second_score >= 0.12
            and score - reverse_second >= 0.12
        )
        if not unambiguous or right in used_after:
            continue
        used_before.add(left)
        used_after.add(right)
        matches.append(
            {
                "before_index": left,
                "after_index": right,
                "kind": "AUTHOR",
                "method": "NEAR_EXACT",
                "similarity": round(score, 6),
                "before_sha256": before[left]["identity"],
                "protected_ids": [],
            }
        )
    return sorted(matches, key=lambda item: int(item["before_index"]))


def _sentence_order_changed(before_text: str, after_text: str) -> bool:
    def sentences(text: str) -> list[dict[str, Any]]:
        parts = re.split(r"(?<=[。！？!?；;])", text)
        return [
            item
            for part in parts
            if (item := _normalized_author_block([part])) is not None
        ]

    before = sentences(before_text)
    after = sentences(after_text)
    matches = _element_matches(before, after)
    author_matches = [item for item in matches if item["kind"] == "AUTHOR"]
    observed = [int(item["after_index"]) for item in author_matches]
    if len(observed) < 2:
        return False
    # Require most sentences on both sides to match. This keeps the LIGHT gate
    # focused on sentence movement instead of ordinary paragraph rewrites.
    if len(author_matches) * 4 < len(before) * 3:
        return False
    if len(author_matches) * 4 < len(after) * 3:
        return False
    return observed != sorted(observed)


def _author_paragraph_regions(masked_text: str) -> list[dict[str, Any]]:
    normalized = masked_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines:
        lines = [""]
    regions: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break
        block_start = index
        while index < len(lines) and lines[index].strip():
            index += 1
        block_end = index
        author_line_indexes: list[int] = []
        visible_parts: list[str] = []
        for line_index in range(block_start, block_end):
            line = lines[line_index]
            if PURE_TEX_STRUCTURE_LINE_RE.match(line):
                continue
            without_protected = preparer.PROTECTED_PLACEHOLDER_RE.sub("", line)
            if not without_protected.strip():
                continue
            author_line_indexes.append(line_index)
            visible_parts.append(without_protected)
        visible = "".join(visible_parts)
        if author_line_indexes and HAN_RE.search(visible):
            regions.append(
                {
                    "ordinal": len(regions) + 1,
                    "start_line": author_line_indexes[0] + 1,
                    "end_line": author_line_indexes[-1] + 1,
                    "block_start_line": block_start + 1,
                    "block_end_line": block_end,
                    "text": visible,
                }
            )
    return regions


def _standalone_protected_lines(masked_text: str) -> set[int]:
    normalized = masked_text.replace("\r\n", "\n").replace("\r", "\n")
    result: set[int] = set()
    for line_number, line in enumerate(normalized.splitlines(), 1):
        protected = list(preparer.PROTECTED_PLACEHOLDER_RE.finditer(line))
        if protected and not preparer.PROTECTED_PLACEHOLDER_RE.sub("", line).strip():
            result.add(line_number)
    return result


def _sentence_paragraph_topology(
    before_masked: str,
    after_masked: str,
) -> dict[str, list[dict[str, Any]]]:
    def sentence_elements(masked_text: str) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for region in _author_paragraph_regions(masked_text):
            for part in re.split(r"(?<=[。！？!?；;])", str(region["text"])):
                element = _normalized_author_block([part])
                if element is None:
                    continue
                element["paragraph_ordinal"] = int(region["ordinal"])
                elements.append(element)
        return elements

    before = sentence_elements(before_masked)
    after = sentence_elements(after_masked)
    matches = [
        item for item in _element_matches(before, after) if item["kind"] == "AUTHOR"
    ]
    before_to_after: dict[int, set[int]] = defaultdict(set)
    after_to_before: dict[int, set[int]] = defaultdict(set)
    for match in matches:
        before_ordinal = int(before[int(match["before_index"])]["paragraph_ordinal"])
        after_ordinal = int(after[int(match["after_index"])]["paragraph_ordinal"])
        before_to_after[before_ordinal].add(after_ordinal)
        after_to_before[after_ordinal].add(before_ordinal)
    splits = [
        {
            "source_paragraph_ordinal": source,
            "target_paragraph_ordinals": sorted(targets),
        }
        for source, targets in sorted(before_to_after.items())
        if len(targets) > 1
    ]
    merges = [
        {
            "source_paragraph_ordinals": sorted(sources),
            "target_paragraph_ordinal": target,
        }
        for target, sources in sorted(after_to_before.items())
        if len(sources) > 1
    ]
    return {"detected_splits": splits, "detected_merges": merges}


def _mapped_after_line_range(
    before_masked: str,
    after_masked: str,
    start_line: int,
    end_line: int,
) -> tuple[int, int] | None:
    before_lines = before_masked.replace("\r\n", "\n").replace(
        "\r", "\n"
    ).splitlines(keepends=True)
    after_lines = after_masked.replace("\r\n", "\n").replace(
        "\r", "\n"
    ).splitlines(keepends=True)
    before_start = start_line - 1
    before_end = end_line
    mapped_ranges: list[tuple[int, int]] = []
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "insert":
            if before_start <= left_start <= before_end:
                mapped_ranges.append((right_start, right_end))
            continue
        overlap_start = max(left_start, before_start)
        overlap_end = min(left_end, before_end)
        if overlap_start >= overlap_end:
            continue
        if tag == "equal":
            mapped_ranges.append(
                (
                    right_start + overlap_start - left_start,
                    right_start + overlap_end - left_start,
                )
            )
        elif right_end > right_start:
            mapped_ranges.append((right_start, right_end))
    nonempty = [item for item in mapped_ranges if item[1] > item[0]]
    if not nonempty:
        return None
    return min(item[0] for item in nonempty) + 1, max(item[1] for item in nonempty)


def _balanced_topology_authorization(
    before_masked: str,
    after_masked: str,
    bundle: dict[str, Any] | None,
    rewrite_intent_schema_status: str,
    topology_changed: bool,
    author_paragraphs_before: int,
    author_paragraphs_after: int,
    sentence_topology: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    intent = bundle.get("rewrite_intent") if isinstance(bundle, dict) else None
    operations = intent.get("operations", []) if isinstance(intent, dict) else []
    topology_operations = [
        item
        for item in operations
        if isinstance(item, dict)
        and item.get("kind")
        in {"MERGE_ADJACENT_REDUNDANCY", "SPLIT_OVERLOADED_PARAGRAPH"}
    ]
    if not topology_changed and not topology_operations:
        return {
            "status": "NOT_REQUIRED",
            "authorized_topology_operations": 0,
            "operation_evidence": [],
            "error": "",
        }
    if rewrite_intent_schema_status != "PASS" or not isinstance(intent, dict):
        return {
            "status": "REVIEW",
            "authorized_topology_operations": 0,
            "operation_evidence": [],
            "error": "",
            "reason": "BOUND_V2_TOPOLOGY_INTENT_REQUIRED",
        }
    if topology_changed and not topology_operations:
        return {
            "status": "REVIEW",
            "authorized_topology_operations": 0,
            "operation_evidence": [],
            "error": "",
            "reason": "DECLARED_TOPOLOGY_OPERATION_REQUIRED",
        }

    expected_delta = sum(
        1 if item["kind"] == "SPLIT_OVERLOADED_PARAGRAPH" else -1
        for item in topology_operations
    )
    actual_delta = author_paragraphs_after - author_paragraphs_before
    if expected_delta != actual_delta:
        return {
            "status": "REVIEW",
            "authorized_topology_operations": 0,
            "operation_evidence": [],
            "error": "balanced_topology_operation_kind_mismatch",
            "expected_paragraph_delta": expected_delta,
            "actual_paragraph_delta": actual_delta,
        }

    source_spans = {
        str(item["id"]): item for item in intent.get("source_spans", [])
    }
    before_regions = _author_paragraph_regions(before_masked)
    after_regions = _author_paragraph_regions(after_masked)
    after_regions_by_ordinal = {
        int(item["ordinal"]): item for item in after_regions
    }
    before_protected = _standalone_protected_lines(before_masked)
    after_protected = _standalone_protected_lines(after_masked)
    after_lines = after_masked.replace("\r\n", "\n").replace(
        "\r", "\n"
    ).splitlines(keepends=True)
    used_source_spans: set[str] = set()
    mapped_target_ranges: list[tuple[int, int]] = []
    evidence: list[dict[str, Any]] = []
    required_signals = {
        "MERGE_ADJACENT_REDUNDANCY": "HIERARCHY-ADJACENT-REDUNDANCY",
        "SPLIT_OVERLOADED_PARAGRAPH": "HIERARCHY-OVERLOADED-PARAGRAPH",
    }
    for operation in topology_operations:
        operation_kind = str(operation["kind"])
        span_ids = operation.get("source_span_ids")
        if not isinstance(span_ids, list) or len(span_ids) != 1:
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_operation_requires_one_exact_span",
            }
        span_id = str(span_ids[0])
        if span_id in used_source_spans or span_id not in source_spans:
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_source_span_reused_or_unknown",
            }
        used_source_spans.add(span_id)
        if required_signals[operation_kind] not in operation.get(
            "target_signals", []
        ):
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_target_signal_invalid",
            }
        span = source_spans[span_id]
        start_line = int(span["start_line"])
        end_line = int(span["end_line"])
        intersecting = [
            region
            for region in before_regions
            if start_line <= int(region["end_line"])
            and int(region["start_line"]) <= end_line
        ]
        expected_sources = 2 if operation_kind == "MERGE_ADJACENT_REDUNDANCY" else 1
        if len(intersecting) != expected_sources:
            error = (
                "balanced_merge_source_paragraph_count_invalid"
                if operation_kind == "MERGE_ADJACENT_REDUNDANCY"
                else "balanced_split_source_paragraph_count_invalid"
            )
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": error,
            }
        if (
            start_line != int(intersecting[0]["start_line"])
            or end_line != int(intersecting[-1]["end_line"])
            or any(
                int(right["ordinal"]) != int(left["ordinal"]) + 1
                for left, right in zip(intersecting, intersecting[1:])
            )
        ):
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_source_span_not_exact",
            }
        if any(start_line <= line_number <= end_line for line_number in before_protected):
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_standalone_protected_anchor_in_source",
            }
        source_ordinals = [int(item["ordinal"]) for item in intersecting]
        detected_target_ordinals: list[int] = []
        if operation_kind == "MERGE_ADJACENT_REDUNDANCY":
            detected = [
                item
                for item in sentence_topology["detected_merges"]
                if item["source_paragraph_ordinals"] == source_ordinals
            ]
            if len(detected) == 1:
                detected_target_ordinals = [
                    int(detected[0]["target_paragraph_ordinal"])
                ]
        else:
            detected = [
                item
                for item in sentence_topology["detected_splits"]
                if int(item["source_paragraph_ordinal"]) == source_ordinals[0]
            ]
            if len(detected) == 1:
                detected_target_ordinals = [
                    int(item) for item in detected[0]["target_paragraph_ordinals"]
                ]
        if detected_target_ordinals and all(
            ordinal in after_regions_by_ordinal
            for ordinal in detected_target_ordinals
        ):
            detected_regions = [
                after_regions_by_ordinal[ordinal]
                for ordinal in detected_target_ordinals
            ]
            target_range = (
                int(detected_regions[0]["start_line"]),
                int(detected_regions[-1]["end_line"]),
            )
        else:
            target_range = _mapped_after_line_range(
                before_masked, after_masked, start_line, end_line
            )
        if target_range is None:
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_target_range_unmapped",
            }
        if any(
            max(target_range[0], existing[0]) <= min(target_range[1], existing[1])
            for existing in mapped_target_ranges
        ):
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_target_ranges_overlap",
            }
        mapped_target_ranges.append(target_range)
        if any(
            target_range[0] <= line_number <= target_range[1]
            for line_number in after_protected
        ):
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_standalone_protected_anchor_in_target",
            }
        target_text = "".join(after_lines[target_range[0] - 1 : target_range[1]])
        target_paragraphs = (
            len(detected_target_ordinals)
            if detected_target_ordinals
            else _author_paragraph_count(target_text)
        )
        expected_targets = 1 if operation_kind == "MERGE_ADJACENT_REDUNDANCY" else 2
        if target_paragraphs != expected_targets:
            return {
                "status": "REVIEW",
                "authorized_topology_operations": 0,
                "operation_evidence": evidence,
                "error": "balanced_topology_target_paragraph_count_invalid",
            }
        evidence.append(
            {
                "operation_id": str(operation.get("id", "")),
                "kind": operation_kind,
                "source_span_id": span_id,
                "source_line_range": [start_line, end_line],
                "source_paragraph_ordinals": source_ordinals,
                "target_line_range": [target_range[0], target_range[1]],
                "target_paragraph_ordinals": detected_target_ordinals,
                "target_paragraphs": target_paragraphs,
                "mapping_method": (
                    "SENTENCE_PARAGRAPH_MEMBERSHIP"
                    if detected_target_ordinals
                    else "LINE_DIFF_FALLBACK"
                ),
            }
        )
    return {
        "status": "PASS",
        "authorized_topology_operations": len(evidence),
        "operation_evidence": evidence,
        "error": "",
        "expected_paragraph_delta": expected_delta,
        "actual_paragraph_delta": actual_delta,
    }


def _non_structural_paragraph_order_check(
    before_masked: str,
    after_masked: str,
    intensity: str,
    bundle: dict[str, Any] | None = None,
    rewrite_intent_schema_status: str = "REVIEW",
) -> dict[str, Any]:
    if intensity.upper() == "STRUCTURAL":
        return {"status": "NOT_APPLICABLE", "reason": "STRUCTURAL plan owns paragraph order"}
    before_elements = _paragraph_order_elements(before_masked)
    after_elements = _paragraph_order_elements(after_masked)
    matches = _element_matches(before_elements, after_elements)
    observed_order = [int(item["after_index"]) for item in matches]
    reordered = len(observed_order) >= 2 and observed_order != sorted(observed_order)
    author_before = [item for item in before_elements if item["kind"] == "AUTHOR"]
    author_after = [item for item in after_elements if item["kind"] == "AUTHOR"]
    author_paragraphs_before = _author_paragraph_count(before_masked)
    author_paragraphs_after = _author_paragraph_count(after_masked)
    sentence_topology = _sentence_paragraph_topology(before_masked, after_masked)
    topology_changed = (
        author_paragraphs_before != author_paragraphs_after
        or bool(sentence_topology["detected_splits"])
        or bool(sentence_topology["detected_merges"])
    )
    protected_anchor_reordered = any(
        (
            int(left["before_index"]) - int(right["before_index"])
        )
        * (
            int(left["after_index"]) - int(right["after_index"])
        )
        < 0
        and (left["kind"] == "PROTECTED" or right["kind"] == "PROTECTED")
        for left_index, left in enumerate(matches)
        for right in matches[left_index + 1 :]
    )
    near_exact_reordered = reordered and any(
        item["method"] == "NEAR_EXACT" for item in matches
    )
    light_sentence_reorder = False
    if intensity.upper() == "LIGHT" and not reordered and not topology_changed:
        for match in matches:
            if match["kind"] != "AUTHOR":
                continue
            before_item = before_elements[int(match["before_index"])]
            after_item = after_elements[int(match["after_index"])]
            if _sentence_order_changed(before_item["text"], after_item["text"]):
                light_sentence_reorder = True
                break
        # Moving sentences can lower whole-paragraph similarity enough that the
        # paragraph has no exact/near-exact match. Compare the remaining author
        # blocks by their sentence coverage before accepting a LIGHT rewrite.
        if not light_sentence_reorder:
            light_sentence_reorder = any(
                _sentence_order_changed(before_item["text"], after_item["text"])
                for before_item in author_before
                for after_item in author_after
            )
    topology_authorization = {
        "status": "NOT_APPLICABLE",
        "authorized_topology_operations": 0,
        "operation_evidence": [],
        "error": "",
    }
    topology_authorized = False
    if intensity.upper() == "BALANCED":
        topology_authorization = _balanced_topology_authorization(
            before_masked,
            after_masked,
            bundle,
            rewrite_intent_schema_status,
            topology_changed,
            author_paragraphs_before,
            author_paragraphs_after,
            sentence_topology,
        )
        topology_authorized = topology_authorization["status"] in {
            "PASS",
            "NOT_REQUIRED",
        }
    review = (
        reordered
        or (topology_changed and not topology_authorized)
        or light_sentence_reorder
        or bool(topology_authorization.get("error"))
    )
    return {
        "status": "REVIEW" if review else "PASS",
        "matched_elements": len(matches),
        "matched_author_paragraphs": sum(item["kind"] == "AUTHOR" for item in matches),
        "matched_protected_anchors": sum(item["kind"] == "PROTECTED" for item in matches),
        "reordered": reordered,
        "paragraph_topology_changed": topology_changed,
        "detected_paragraph_splits": sentence_topology["detected_splits"],
        "detected_paragraph_merges": sentence_topology["detected_merges"],
        "author_paragraphs_before": author_paragraphs_before,
        "author_paragraphs_after": author_paragraphs_after,
        "topology_authorization_status": topology_authorization["status"],
        "topology_authorization_error": topology_authorization.get("error", ""),
        "authorized_topology_operations": topology_authorization[
            "authorized_topology_operations"
        ],
        "topology_operation_evidence": topology_authorization[
            "operation_evidence"
        ],
        "protected_anchor_reordered": protected_anchor_reordered,
        "near_exact_reordered": near_exact_reordered,
        "light_sentence_reorder": light_sentence_reorder,
        "moved_paragraph_sha256": [
            item["before_sha256"]
            for item in matches
            if reordered and item["kind"] == "AUTHOR"
        ],
        "match_evidence": matches[:16],
        "scope": "NON_STRUCTURAL_PARAGRAPH_TOPOLOGY_AND_ORDER",
    }


def _warning_review_bundle(
    bundle: dict[str, Any],
) -> tuple[dict[str, str], str, str, str]:
    if "accepted_warnings" in bundle:
        raise ValueError("retired_accepted_warnings_field")
    resolutions = bundle.get("warning_resolutions", {})
    if not isinstance(resolutions, dict):
        raise ValueError("warning_resolutions must be an object")
    warning_resolutions = {str(key): str(value) for key, value in resolutions.items()}
    request_value = bundle.get("warning_review_request_sha256", "")
    if request_value is None:
        request_value = ""
    if not isinstance(request_value, str):
        raise ValueError("invalid_warning_review_request_sha256")
    request_sha256 = request_value.strip().lower()
    review_present = "warning_review" in bundle
    if review_present:
        raise ValueError("warning_reviewer_identity_metadata_retired")

    if not warning_resolutions:
        if request_sha256:
            raise ValueError("warning_review_request_without_warning_resolutions")
        return warning_resolutions, "", "NONE", ""

    if not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
        raise ValueError("invalid_warning_review_request_sha256")
    return warning_resolutions, request_sha256, "NONE", ""


def _validate_intent_span_shape(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field}_must_be_nonempty")
    if len(value) > 64:
        raise ValueError(f"{field}_too_many_items")
    seen_ids: set[str] = set()
    seen_ranges: set[tuple[int, int]] = set()
    previous_start = 0
    previous_end = 0
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "start_line",
            "end_line",
            "sha256",
        }:
            raise ValueError(f"{field}_fields_invalid")
        span_id = item.get("id")
        if not isinstance(span_id, str) or not re.fullmatch(
            r"S[0-9]{1,3}", span_id
        ):
            raise ValueError(f"{field}_id_invalid")
        if span_id in seen_ids:
            raise ValueError(f"{field}_id_duplicate")
        seen_ids.add(span_id)
        start_line = item.get("start_line")
        end_line = item.get("end_line")
        if (
            isinstance(start_line, bool)
            or not isinstance(start_line, int)
            or isinstance(end_line, bool)
            or not isinstance(end_line, int)
            or start_line < 1
            or end_line < start_line
        ):
            raise ValueError(f"{field}_line_range_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError(f"{field}_sha256_invalid")
        line_range = (start_line, end_line)
        if line_range in seen_ranges:
            raise ValueError(f"{field}_range_duplicate")
        if seen_ranges and start_line < previous_start:
            raise ValueError(f"{field}_out_of_order")
        if seen_ranges and start_line <= previous_end:
            raise ValueError(f"{field}_overlap")
        seen_ranges.add(line_range)
        previous_start = start_line
        previous_end = end_line


REWRITE_INTENT_TARGET_SIGNAL_PREFIXES = (
    "LEX",
    "HUM",
    "VOICE",
    "STYLE",
    "SCENE",
    "USER",
    "REPETITION",
    "COLLOCATION",
    "RHYTHM",
    "HIERARCHY",
)
REWRITE_INTENT_TARGET_SIGNAL_RE = re.compile(
    r"(?:" + "|".join(REWRITE_INTENT_TARGET_SIGNAL_PREFIXES) + r")[A-Za-z0-9_.:-]{1,70}"
)


def _validate_rewrite_intent_shape(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "summary",
        "operations",
        "source_spans",
        "target_signals",
    }:
        raise ValueError("rewrite_intent_fields_invalid")
    summary = value.get("summary")
    if not isinstance(summary, str):
        raise ValueError("rewrite_intent_summary_invalid")
    _validate_intent_span_shape(value.get("source_spans"), "rewrite_intent_source_spans")
    source_ids = {str(item["id"]) for item in value["source_spans"]}
    operations = value.get("operations")
    if not isinstance(operations, list) or not operations or len(operations) > 32:
        raise ValueError("rewrite_intent_operations_invalid")
    operation_ids: set[str] = set()
    covered_source_ids: set[str] = set()
    covered_signals: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {
            "id",
            "kind",
            "source_span_ids",
            "target_signals",
            "summary",
        }:
            raise ValueError("rewrite_intent_operation_fields_invalid")
        operation_id = operation.get("id")
        if not isinstance(operation_id, str) or not re.fullmatch(
            r"O[0-9]{1,3}", operation_id
        ):
            raise ValueError("rewrite_intent_operation_id_invalid")
        if operation_id in operation_ids:
            raise ValueError("rewrite_intent_operation_id_duplicate")
        operation_ids.add(operation_id)
        if not re.fullmatch(r"[A-Z][A-Z0-9_.-]{1,63}", str(operation.get("kind", ""))):
            raise ValueError("rewrite_intent_operation_kind_invalid")
        refs = operation.get("source_span_ids")
        if (
            not isinstance(refs, list)
            or not refs
            or any(not isinstance(item, str) for item in refs)
            or len(set(refs)) != len(refs)
            or not set(refs).issubset(source_ids)
        ):
            raise ValueError("rewrite_intent_operation_source_spans_invalid")
        covered_source_ids.update(refs)
        if not isinstance(operation.get("summary"), str):
            raise ValueError("rewrite_intent_operation_summary_invalid")
    signals = value.get("target_signals")
    if (
        not isinstance(signals, list)
        or not signals
        or len(signals) > 32
        or any(
            not isinstance(item, str)
            or not REWRITE_INTENT_TARGET_SIGNAL_RE.fullmatch(item)
            for item in signals
        )
        or len(set(signals)) != len(signals)
    ):
        raise ValueError("rewrite_intent_target_signals_invalid")
    signal_set = set(signals)
    for operation in operations:
        refs = operation["target_signals"]
        if (
            not isinstance(refs, list)
            or not refs
            or any(not isinstance(item, str) for item in refs)
            or len(set(refs)) != len(refs)
            or not set(refs).issubset(signal_set)
        ):
            raise ValueError("rewrite_intent_operation_target_signals_invalid")
        covered_signals.update(refs)
    if covered_source_ids != source_ids:
        raise ValueError("rewrite_intent_source_span_coverage_incomplete")
    if covered_signals != signal_set:
        raise ValueError("rewrite_intent_target_signal_coverage_incomplete")


def _validate_long_authoring_binding_shape(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != LONG_AUTHORING_BINDING_FIELDS:
        raise ValueError("long_authoring_binding_fields_invalid")
    if value.get("schema_version") != LONG_AUTHORING_BINDING_SCHEMA:
        raise ValueError("long_authoring_binding_schema_invalid")
    if value.get("integrity_scope") != "CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY":
        raise ValueError("long_authoring_binding_integrity_scope_invalid")
    for field in (
        "prepare_integrity_sha256",
        "run_metadata_sha256",
        "policy_snapshot_sha256",
        "authoring_binding_sha256",
    ):
        if not isinstance(value.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", value[field]
        ):
            raise ValueError("long_authoring_binding_hash_invalid")
    if not isinstance(value.get("snapshot_id"), str) or not value["snapshot_id"]:
        raise ValueError("long_authoring_binding_snapshot_invalid")
    if value.get("mode") != "REWRITE" or value.get("intensity") not in {
        "LIGHT",
        "BALANCED",
        "STRUCTURAL",
    }:
        raise ValueError("long_authoring_binding_configuration_invalid")
    if value.get("authoring_allowed") is not True:
        raise ValueError("long_authoring_binding_not_authorized")
    if (
        value.get("completion_claim_allowed") is not False
        or value.get("humanize_quality_claim_allowed") is not False
    ):
        raise ValueError("long_authoring_binding_claim_flags_invalid")

    source = value.get("source_binding")
    if not isinstance(source, dict) or set(source) != LONG_AUTHORING_SOURCE_BINDING_FIELDS:
        raise ValueError("long_authoring_source_binding_fields_invalid")
    for field in (
        "source_file_sha256",
        "source_span_sha256",
        "masked_text_sha256",
        "chunk_binding_sha256",
    ):
        if not isinstance(source.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", source[field]
        ):
            raise ValueError("long_authoring_source_binding_hash_invalid")
    if source.get("offset_unit") != "PYTHON_UNICODE_CODEPOINT_INDEX":
        raise ValueError("long_authoring_source_binding_offset_unit_invalid")
    for field in ("file_id", "unit_id"):
        if not isinstance(source.get(field), str) or not source[field]:
            raise ValueError("long_authoring_source_binding_identifier_invalid")
    for field in ("start", "end", "start_line", "end_line"):
        number = source.get(field)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError("long_authoring_source_binding_range_invalid")
    if source["end"] <= source["start"] or source["end_line"] < source["start_line"]:
        raise ValueError("long_authoring_source_binding_range_invalid")

    route = value.get("scene_route")
    if not isinstance(route, dict) or set(route) != LONG_AUTHORING_SCENE_ROUTE_FIELDS:
        raise ValueError("long_authoring_scene_route_fields_invalid")
    if route.get("requested_scene") not in {
        "AUTO",
        "GENERAL",
        "COURSE",
        "MODELING",
        "RESEARCH",
    } or route.get("resolved_scene") not in {
        "GENERAL",
        "COURSE",
        "MODELING",
        "RESEARCH",
    }:
        raise ValueError("long_authoring_scene_route_scene_invalid")
    if route.get("status") not in {
        "EXPLICIT",
        "ROUTED",
        "ROUTED_DOCUMENT_PRIOR",
        "FALLBACK_GENERAL",
    }:
        raise ValueError("long_authoring_scene_route_status_invalid")
    reason_by_status = {
        "EXPLICIT": "USER_EXPLICIT_SCENE",
        "ROUTED": "AUTO_UNIQUE_SCORE_ABOVE_THRESHOLD",
        "ROUTED_DOCUMENT_PRIOR": "AUTO_DOCUMENT_PRIOR_WITH_LOCAL_SUPPORT",
        "FALLBACK_GENERAL": "AUTO_INSUFFICIENT_SCENE_EVIDENCE",
    }
    if route.get("reason_code") != reason_by_status[route["status"]]:
        raise ValueError("long_authoring_scene_route_reason_invalid")
    if route["status"] == "EXPLICIT" and (
        route["requested_scene"] == "AUTO"
        or route["requested_scene"] != route["resolved_scene"]
    ):
        raise ValueError("long_authoring_explicit_scene_binding_invalid")
    if route["status"] != "EXPLICIT" and route["requested_scene"] != "AUTO":
        raise ValueError("long_authoring_auto_scene_binding_invalid")
    scores = route.get("scores")
    if not isinstance(scores, dict) or set(scores) != {
        "COURSE",
        "MODELING",
        "RESEARCH",
    } or any(
        isinstance(score, bool) or not isinstance(score, int) or score < 0
        for score in scores.values()
    ):
        raise ValueError("long_authoring_scene_route_scores_invalid")
    for field in ("top_score", "margin", "policy_revision"):
        number = route.get(field)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError("long_authoring_scene_route_number_invalid")
    for field in (
        "policy_sha256",
        "heading_path_sha256",
        "routing_input_sha256",
    ):
        if not isinstance(route.get(field), str) or not re.fullmatch(
            r"[0-9a-f]{64}", route[field]
        ):
            raise ValueError("long_authoring_scene_route_hash_invalid")
    ambiguous = route.get("ambiguous_scenes")
    if not isinstance(ambiguous, list) or ambiguous:
        raise ValueError("long_authoring_scene_route_ambiguity_invalid")
    evidence = route.get("evidence")
    evidence_fields = {
        "scene",
        "rule_id",
        "scope",
        "occurrences",
        "bounded_occurrences",
        "contribution",
    }
    if not isinstance(evidence, list):
        raise ValueError("long_authoring_scene_route_evidence_invalid")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != evidence_fields:
            raise ValueError("long_authoring_scene_route_evidence_invalid")
        if item.get("scene") not in {"COURSE", "MODELING", "RESEARCH"}:
            raise ValueError("long_authoring_scene_route_evidence_invalid")
        if item.get("scope") not in {"heading", "body"}:
            raise ValueError("long_authoring_scene_route_evidence_invalid")
        if not isinstance(item.get("rule_id"), str) or not item["rule_id"]:
            raise ValueError("long_authoring_scene_route_evidence_invalid")
        for field in ("occurrences", "bounded_occurrences", "contribution"):
            number = item.get(field)
            if isinstance(number, bool) or not isinstance(number, int) or number < 0:
                raise ValueError("long_authoring_scene_route_evidence_invalid")

    voice = value.get("voice_binding")
    if not isinstance(voice, dict) or set(voice) != LONG_AUTHORING_VOICE_BINDING_FIELDS:
        raise ValueError("long_authoring_voice_binding_fields_invalid")
    if not isinstance(voice.get("profile_id"), str) or not voice["profile_id"]:
        raise ValueError("long_authoring_voice_binding_identifier_invalid")
    if not isinstance(voice.get("profile_revision"), int) or isinstance(
        voice["profile_revision"], bool
    ):
        raise ValueError("long_authoring_voice_binding_revision_invalid")
    if voice.get("profile_kind") not in {"DEFAULT", "PERSONAL"}:
        raise ValueError("long_authoring_voice_binding_kind_invalid")
    if voice.get("binding_scene") != route["resolved_scene"]:
        raise ValueError("long_authoring_voice_binding_scene_invalid")
    if not isinstance(voice.get("profile_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", voice["profile_sha256"]
    ):
        raise ValueError("long_authoring_voice_binding_hash_invalid")

    canonical = dict(value)
    recorded_hash = canonical.pop("authoring_binding_sha256")
    if sha256(_canonical_json(canonical).encode("utf-8")) != recorded_hash:
        raise ValueError("long_authoring_binding_hash_mismatch")


def _validate_unit_template_field_edit_scope_shape(
    value: Any,
    *,
    decision: str,
) -> None:
    if value is None:
        return
    if decision != "REWRITE":
        raise ValueError("template_field_edit_scope_forbidden_for_no_change")
    expected = {"schema_version", "permission_boundary", "edits"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("unit_template_field_edit_scope_fields_invalid")
    if value.get("schema_version") != UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA:
        raise ValueError("unit_template_field_edit_scope_schema_invalid")
    if value.get("permission_boundary") != output_validator.TEMPLATE_FIELD_PERMISSION:
        raise ValueError("unit_template_field_edit_scope_permission_invalid")
    edits = value.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("unit_template_field_edit_scope_edits_invalid")
    seen_lines: set[int] = set()
    expected_edit_fields = {"line", "label", "permission", "reason"}
    for ordinal, edit in enumerate(edits, 1):
        if not isinstance(edit, dict) or set(edit) != expected_edit_fields:
            raise ValueError(
                f"unit_template_field_edit_scope_edit_fields_invalid:{ordinal}"
            )
        line = edit.get("line")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ValueError(
                f"unit_template_field_edit_scope_line_invalid:{ordinal}"
            )
        if line in seen_lines:
            raise ValueError(f"unit_template_field_edit_scope_line_duplicate:{line}")
        seen_lines.add(line)
        if edit.get("label") not in output_validator.TEMPLATE_FIELD_LABELS:
            raise ValueError(
                f"unit_template_field_edit_scope_label_invalid:{ordinal}"
            )
        if edit.get("permission") != output_validator.TEMPLATE_FIELD_PERMISSION:
            raise ValueError(
                f"unit_template_field_edit_scope_edit_permission_invalid:{ordinal}"
            )
        reason = edit.get("reason")
        if not isinstance(reason, str):
            raise ValueError(
                f"unit_template_field_edit_scope_reason_invalid:{ordinal}"
            )
        output_validator._validate_reason(
            reason,
            f"unit template field edit scope line {line} reason",
        )


def _materialize_unit_template_field_edit_scope(
    bundle: Mapping[str, Any],
    *,
    decision: str,
    before_path: Path,
    validation_dir: Path,
    unit_id: str,
) -> Path | None:
    embedded = bundle.get("template_field_edit_scope")
    _validate_unit_template_field_edit_scope_shape(embedded, decision=decision)
    if embedded is None:
        return None
    before_raw = before_path.read_bytes()
    direct_scope = {
        "schema_version": output_validator.TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
        "source_sha256": sha256(before_raw),
        "edits": embedded["edits"],
    }
    scope_path = validation_dir / f"{unit_id}.template-field-edit-scope.json"
    _write_json(scope_path, direct_scope)
    output_validator._load_template_field_edit_scope(
        scope_path,
        before_raw=before_raw,
        before_text=before_raw.decode("utf-8-sig"),
        document_format=(
            "tex" if before_path.suffix.lower() in {".tex", ".ltx"} else "markdown"
        ),
    )
    return scope_path


def _validate_rewrite_bundle_fields(bundle: dict[str, Any], decision: str) -> str:
    legacy_common = {
        "decision",
        "bundle_path",
        "unit_id",
        "chunk_binding_sha256",
        "keep_reasons",
        "warning_resolutions",
        "warning_review_request_sha256",
        "warning_review",
        "voice_profile_sha256",
        "structural_plan",
    }
    if "schema_version" not in bundle:
        allowed = legacy_common | (
            {"masked_text"} if decision == "REWRITE" else {"reason"}
        )
        unknown = sorted(set(bundle) - allowed)
        if unknown:
            raise ValueError("unknown_rewrite_bundle_fields:" + ",".join(unknown))
        return "REVIEW"
    schema_version = bundle.get("schema_version")
    if schema_version not in UNIT_REWRITE_BUNDLE_SCHEMAS:
        raise ValueError("unit_rewrite_bundle_schema_invalid")
    common = legacy_common | {"schema_version"}
    if schema_version in {UNIT_REWRITE_BUNDLE_SCHEMA_V3, UNIT_REWRITE_BUNDLE_SCHEMA}:
        common.add("authoring_binding")
    if schema_version == UNIT_REWRITE_BUNDLE_SCHEMA:
        common.add("template_field_edit_scope")
    if decision == "REWRITE":
        allowed = common | {"masked_text", "rewrite_intent"}
        required = {
            "schema_version",
            "decision",
            "bundle_path",
            "unit_id",
            "chunk_binding_sha256",
            "voice_profile_sha256",
            "keep_reasons",
            "masked_text",
            "rewrite_intent",
        }
    else:
        allowed = common | {"reason", "evidence_spans"}
        required = {
            "schema_version",
            "decision",
            "bundle_path",
            "unit_id",
            "chunk_binding_sha256",
            "voice_profile_sha256",
            "keep_reasons",
            "reason",
            "evidence_spans",
        }
    if schema_version in {UNIT_REWRITE_BUNDLE_SCHEMA_V3, UNIT_REWRITE_BUNDLE_SCHEMA}:
        required.add("authoring_binding")
    if schema_version == UNIT_REWRITE_BUNDLE_SCHEMA:
        required.add("template_field_edit_scope")
    unknown = sorted(set(bundle) - allowed)
    if unknown:
        raise ValueError("unknown_rewrite_bundle_fields:" + ",".join(unknown))
    missing = sorted(required - set(bundle))
    if missing:
        raise ValueError("missing_rewrite_bundle_fields:" + ",".join(missing))
    if decision == "REWRITE":
        _validate_rewrite_intent_shape(bundle.get("rewrite_intent"))
    else:
        _validate_intent_span_shape(bundle.get("evidence_spans"), "no_change_evidence_spans")
    if schema_version in {UNIT_REWRITE_BUNDLE_SCHEMA_V3, UNIT_REWRITE_BUNDLE_SCHEMA}:
        _validate_long_authoring_binding_shape(bundle.get("authoring_binding"))
    if schema_version == UNIT_REWRITE_BUNDLE_SCHEMA:
        _validate_unit_template_field_edit_scope_shape(
            bundle.get("template_field_edit_scope"),
            decision=decision,
        )
        return "PASS"
    return "REVIEW"


def _validate_transaction_fragment_local_intent_shape(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("structural_transaction_local_rewrite_intent_invalid")
    decision = value.get("decision")
    if decision == "REWRITE":
        if set(value) != {"decision", "rewrite_intent"}:
            raise ValueError(
                "structural_transaction_local_rewrite_intent_fields_invalid"
            )
        _validate_rewrite_intent_shape(value.get("rewrite_intent"))
        return
    if decision == "NO_CHANGE":
        if set(value) != {"decision", "reason", "evidence_spans"}:
            raise ValueError(
                "structural_transaction_local_no_change_fields_invalid"
            )
        if not isinstance(value.get("reason"), str):
            raise ValueError("structural_transaction_local_no_change_reason_invalid")
        _validate_intent_span_shape(
            value.get("evidence_spans"),
            "structural_transaction_local_no_change_evidence_spans",
        )
        return
    raise ValueError("structural_transaction_local_rewrite_decision_invalid")


def _validate_structural_transaction_bundle_fields(bundle: dict[str, Any]) -> str:
    expected = {
        "schema_version",
        "transaction_id",
        "transaction_binding_sha256",
        "transaction_inventory_sha256",
        "unit_bindings",
        "fragments",
        "bundle_path",
    }
    if set(bundle) != expected:
        raise ValueError("structural_transaction_bundle_fields_invalid")
    schema_version = bundle.get("schema_version")
    if schema_version not in STRUCTURAL_TRANSACTION_BUNDLE_SCHEMAS:
        raise ValueError("structural_transaction_bundle_schema_invalid")
    if not re.fullmatch(r"STX-[0-9a-f]{24}", str(bundle.get("transaction_id", ""))):
        raise ValueError("structural_transaction_id_invalid")
    for field in ("transaction_binding_sha256", "transaction_inventory_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(bundle.get(field, ""))):
            raise ValueError(f"{field}_invalid")
    bindings = bundle.get("unit_bindings")
    if not isinstance(bindings, list) or len(bindings) != 2:
        raise ValueError("structural_transaction_unit_bindings_invalid")
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {
            "unit_id",
            "chunk_binding_sha256",
            "voice_profile_sha256",
        }:
            raise ValueError("structural_transaction_unit_binding_fields_invalid")
        if not isinstance(binding.get("unit_id"), str) or not binding["unit_id"]:
            raise ValueError("structural_transaction_unit_id_invalid")
        for field in ("chunk_binding_sha256", "voice_profile_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(binding.get(field, ""))):
                raise ValueError(f"structural_transaction_{field}_invalid")
    fragments = bundle.get("fragments")
    if not isinstance(fragments, list) or len(fragments) != 2:
        raise ValueError("structural_transaction_fragments_invalid")
    for fragment in fragments:
        expected_fragment_fields = {
            "target_unit_id",
            "masked_text",
            "keep_reasons",
            "target_groups",
        }
        if schema_version in STRUCTURAL_TRANSACTION_BUNDLE_LOCAL_INTENT_SCHEMAS:
            expected_fragment_fields.add("local_rewrite_intent")
        if schema_version == STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA:
            expected_fragment_fields.add("template_field_edit_scope")
        if not isinstance(fragment, dict) or set(fragment) != expected_fragment_fields:
            raise ValueError("structural_transaction_fragment_fields_invalid")
        if not isinstance(fragment.get("target_unit_id"), str) or not fragment[
            "target_unit_id"
        ]:
            raise ValueError("structural_transaction_target_unit_id_invalid")
        if not isinstance(fragment.get("masked_text"), str):
            raise ValueError("structural_transaction_masked_text_invalid")
        if not isinstance(fragment.get("keep_reasons"), dict):
            raise ValueError("structural_transaction_keep_reasons_invalid")
        groups = fragment.get("target_groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError("structural_transaction_target_groups_invalid")
        for group in groups:
            if not isinstance(group, dict) or set(group) != {
                "source_refs",
                "target_paragraph_sha256",
                "responsibility",
                "reason",
            }:
                raise ValueError("structural_transaction_target_group_fields_invalid")
            refs = group.get("source_refs")
            if not isinstance(refs, list) or not refs:
                raise ValueError("structural_transaction_source_refs_invalid")
            for source_ref in refs:
                if not isinstance(source_ref, dict) or set(source_ref) != {
                    "unit_id",
                    "paragraph_id",
                }:
                    raise ValueError("structural_transaction_source_ref_fields_invalid")
                if not all(
                    isinstance(source_ref.get(field), str) and source_ref[field]
                    for field in ("unit_id", "paragraph_id")
                ):
                    raise ValueError("structural_transaction_source_ref_invalid")
        if schema_version in STRUCTURAL_TRANSACTION_BUNDLE_LOCAL_INTENT_SCHEMAS:
            _validate_transaction_fragment_local_intent_shape(
                fragment.get("local_rewrite_intent")
            )
    binding_ids = [str(binding["unit_id"]) for binding in bindings]
    fragment_ids = [str(fragment["target_unit_id"]) for fragment in fragments]
    if len(set(binding_ids)) != 2:
        raise ValueError("structural_transaction_unit_binding_duplicate")
    if len(set(fragment_ids)) != 2:
        raise ValueError("structural_transaction_fragment_target_duplicate")
    if set(binding_ids) != set(fragment_ids):
        raise ValueError("structural_transaction_member_coverage_mismatch")
    return "PASS" if schema_version == STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA else "REVIEW"


def _validate_structural_transaction_decline_fields(bundle: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "decision",
        "transaction_id",
        "transaction_binding_sha256",
        "transaction_inventory_sha256",
        "unit_bindings",
        "reason_code",
        "reason",
        "evidence_refs",
        "bundle_path",
    }
    if set(bundle) != expected:
        raise ValueError("structural_transaction_decline_fields_invalid")
    if bundle.get("schema_version") != STRUCTURAL_TRANSACTION_DECLINE_SCHEMA:
        raise ValueError("structural_transaction_decline_schema_invalid")
    if bundle.get("decision") != "DECLINE":
        raise ValueError("structural_transaction_decline_decision_invalid")
    if not re.fullmatch(r"STX-[0-9a-f]{24}", str(bundle.get("transaction_id", ""))):
        raise ValueError("structural_transaction_decline_id_invalid")
    for field in ("transaction_binding_sha256", "transaction_inventory_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(bundle.get(field, ""))):
            raise ValueError(f"structural_transaction_decline_{field}_invalid")
    bindings = bundle.get("unit_bindings")
    if not isinstance(bindings, list) or len(bindings) != 2:
        raise ValueError("structural_transaction_decline_unit_bindings_invalid")
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {
            "unit_id",
            "chunk_binding_sha256",
            "voice_profile_sha256",
        }:
            raise ValueError("structural_transaction_decline_unit_binding_fields_invalid")
        if not isinstance(binding.get("unit_id"), str) or not binding["unit_id"]:
            raise ValueError("structural_transaction_decline_unit_id_invalid")
        for field in ("chunk_binding_sha256", "voice_profile_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(binding.get(field, ""))):
                raise ValueError(f"structural_transaction_decline_{field}_invalid")
    if bundle.get("reason_code") not in STRUCTURAL_TRANSACTION_DECLINE_REASON_CODES:
        raise ValueError("structural_transaction_decline_reason_code_invalid")
    if not _specific_decline_reason(str(bundle.get("reason", ""))):
        raise ValueError("structural_transaction_decline_reason_not_specific")
    evidence_refs = bundle.get("evidence_refs")
    if not isinstance(evidence_refs, list) or len(evidence_refs) < 2:
        raise ValueError("structural_transaction_decline_evidence_refs_invalid")
    normalized_refs: list[tuple[str, str]] = []
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, dict) or set(evidence_ref) != {
            "unit_id",
            "paragraph_id",
        }:
            raise ValueError("structural_transaction_decline_evidence_ref_fields_invalid")
        if not all(
            isinstance(evidence_ref.get(field), str) and evidence_ref[field]
            for field in ("unit_id", "paragraph_id")
        ):
            raise ValueError("structural_transaction_decline_evidence_ref_invalid")
        normalized_refs.append(
            (str(evidence_ref["unit_id"]), str(evidence_ref["paragraph_id"]))
        )
    if len(normalized_refs) != len(set(normalized_refs)):
        raise ValueError("structural_transaction_decline_evidence_ref_duplicate")


def _structural_transaction_unit_ids(bundle: dict[str, Any]) -> list[str]:
    _validate_structural_transaction_bundle_fields(bundle)
    return [str(item["unit_id"]) for item in bundle["unit_bindings"]]


def _structural_transaction_atomic_counts(
    result: dict[str, Any],
    unit_map: dict[str, dict[str, Any]],
    *,
    published: bool,
) -> dict[str, int]:
    """Reject any half-accepted or half-published two-member transaction."""

    unit_ids = result.get("unit_ids")
    if (
        not isinstance(unit_ids, list)
        or len(unit_ids) != 2
        or len(set(unit_ids)) != 2
        or any(unit_id not in unit_map for unit_id in unit_ids)
    ):
        raise ValueError("structural_transaction_atomic_member_set_invalid")
    accepted = sum(
        1 for unit_id in unit_ids if unit_map[unit_id].get("status") == "DONE"
    )
    gate = result.get("atomic_gate_status")
    if gate == "PASS":
        if accepted != 2:
            raise ValueError("structural_transaction_atomic_acceptance_partial")
    elif gate == "ROLLED_BACK":
        if accepted != 0:
            raise ValueError("structural_transaction_rollback_retained_member")
    else:
        raise ValueError("structural_transaction_atomic_gate_status_invalid")
    published_count = accepted if published else 0
    if accepted not in {0, 2} or published_count not in {0, 2}:
        raise ValueError("structural_transaction_atomic_count_invalid")
    return {
        "atomic_member_count": 2,
        "accepted_member_count": accepted,
        "published_member_count": published_count,
    }


def _validate_structural_plan(
    bundle: dict[str, Any],
    unit: dict[str, Any],
    chunk: dict[str, Any],
    masked_text: str,
    suffix: str,
    span_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    intensity = str(unit.get("intensity", "")).upper()
    plan = bundle.get("structural_plan")
    if intensity != "STRUCTURAL":
        if plan is not None:
            raise ValueError("structural_plan_not_allowed_for_non_structural_run")
        return {
            "status": "NOT_APPLICABLE",
            "change_applied": False,
            "limitations": "non-STRUCTURAL run",
        }
    if not isinstance(plan, dict):
        raise ValueError("structural_plan_missing")
    expected_plan_fields = {
        "schema_version",
        "source_inventory_sha256",
        "target_groups",
    }
    if set(plan) != expected_plan_fields:
        raise ValueError("structural_plan_fields_invalid")
    if plan.get("schema_version") != preparer.STRUCTURAL_PLAN_SCHEMA:
        raise ValueError("structural_plan_schema_invalid")

    source_inventory = chunk.get("structural_paragraphs")
    if not isinstance(source_inventory, list) or not source_inventory:
        raise ValueError("structural_source_inventory_missing")
    rebuilt_source = preparer.structural_paragraph_inventory(
        str(chunk.get("masked_text", "")),
        suffix.lower(),
        {
            protected_id: str(span_map.get(protected_id, {}).get("reason", ""))
            for protected_id in chunk.get("protected_ids", [])
        },
    )
    if _canonical_json(source_inventory) != _canonical_json(rebuilt_source):
        raise ValueError("structural_source_inventory_rebuild_mismatch")
    source_inventory_sha256 = preparer.structural_inventory_sha256(source_inventory)
    if (
        chunk.get("structural_inventory_sha256") != source_inventory_sha256
        or plan.get("source_inventory_sha256") != source_inventory_sha256
    ):
        raise ValueError("structural_source_inventory_hash_mismatch")

    source_ids = [str(item["paragraph_id"]) for item in source_inventory]
    source_by_id = {str(item["paragraph_id"]): item for item in source_inventory}
    source_blocks = preparer.structural_paragraph_blocks(
        str(chunk.get("masked_text", ""))
    )
    source_block_by_id = {
        str(item["paragraph_id"]): source_blocks[int(item["ordinal"]) - 1]
        for item in source_inventory
    }
    target_groups = plan.get("target_groups")
    target_blocks = preparer.structural_paragraph_blocks(masked_text)
    if not isinstance(target_groups, list) or len(target_groups) != len(target_blocks):
        raise ValueError("structural_target_group_count_mismatch")

    flattened: list[str] = []
    moved = 0
    merged = 0
    normalized_groups: list[list[str]] = []
    for target_index, (group, target_block) in enumerate(
        zip(target_groups, target_blocks), 1
    ):
        if not isinstance(group, dict) or set(group) != {
            "source_paragraph_ids",
            "target_paragraph_sha256",
            "responsibility",
            "reason",
        }:
            raise ValueError("structural_target_group_fields_invalid")
        group_ids = group.get("source_paragraph_ids")
        if (
            not isinstance(group_ids, list)
            or not group_ids
            or any(not isinstance(item, str) for item in group_ids)
        ):
            raise ValueError("structural_target_group_sources_invalid")
        if any(item not in source_by_id for item in group_ids):
            raise ValueError("structural_target_group_source_unknown")
        ordinals = [int(source_by_id[item]["ordinal"]) for item in group_ids]
        if ordinals != list(range(min(ordinals), max(ordinals) + 1)):
            raise ValueError("structural_merge_sources_must_be_adjacent_and_ordered")
        responsibilities = {
            str(source_by_id[item]["responsibility"]) for item in group_ids
        }
        if len(responsibilities) != 1:
            raise ValueError("structural_merge_changes_paragraph_responsibility")
        responsibility = next(iter(responsibilities))
        if group.get("responsibility") != responsibility:
            raise ValueError("structural_responsibility_claim_mismatch")
        if preparer._paragraph_responsibility(target_block) != responsibility:
            raise ValueError("structural_target_responsibility_drift")
        if not _specific_reason(str(group.get("reason", ""))):
            raise ValueError("structural_target_group_reason_not_specific")
        target_sha256 = sha256(target_block.encode("utf-8"))
        if group.get("target_paragraph_sha256") != target_sha256:
            raise ValueError("structural_target_paragraph_hash_mismatch")
        expected_protected_ids = [
            protected_id
            for source_id in group_ids
            for protected_id in source_by_id[source_id].get("protected_ids", [])
        ]
        target_protected_ids = [
            match.group("id")
            for match in preparer.PROTECTED_PLACEHOLDER_RE.finditer(target_block)
        ]
        if target_protected_ids != expected_protected_ids:
            raise ValueError("structural_protected_span_left_source_paragraph")
        for source_id in group_ids:
            source = source_by_id[source_id]
            if not bool(source.get("movable")) and (
                len(group_ids) != 1 or target_index != int(source["ordinal"])
            ):
                raise ValueError("structural_locked_paragraph_moved_or_merged")
        if len(group_ids) > 1:
            merged += len(group_ids) - 1
        expected_singleton = (
            [source_ids[target_index - 1]]
            if target_index <= len(source_ids)
            else []
        )
        if group_ids != expected_singleton:
            moved += 1
        flattened.extend(group_ids)
        normalized_groups.append(list(group_ids))

    if len(flattened) != len(set(flattened)) or sorted(flattened) != sorted(source_ids):
        raise ValueError("structural_source_paragraph_coverage_mismatch")
    default_groups = [[item] for item in source_ids]
    change_applied = normalized_groups != default_groups
    structural_baseline_groups = [
        " ".join(source_block_by_id[source_id].strip() for source_id in group_ids)
        for group_ids in normalized_groups
    ]
    structural_baseline = "\n\n".join(structural_baseline_groups)
    if masked_text.endswith(("\n", "\r")):
        structural_baseline += "\n"
    return {
        "status": "PASS",
        "schema_version": preparer.STRUCTURAL_PLAN_SCHEMA,
        "source_inventory_sha256": source_inventory_sha256,
        "source_paragraphs": len(source_ids),
        "target_paragraphs": len(target_blocks),
        "change_applied": change_applied,
        "moved_or_regrouped_targets": moved,
        "merged_source_paragraphs": merged,
        "title_lock": bool(chunk.get("structural_title_lock")),
        "scope": str(chunk.get("structural_scope", "")),
        "cross_unit_moves_allowed": bool(
            chunk.get("structural_cross_unit_moves_allowed")
        ),
        "semantic_mapping": "NOT_EVALUATED",
        "_baseline_masked_text": structural_baseline,
    }


def _structural_transaction_bundle_sha256(bundle: dict[str, Any]) -> str:
    return sha256(
        _canonical_json(
            {key: value for key, value in bundle.items() if key != "bundle_path"}
        ).encode("utf-8")
    )


def _bound_structural_transaction_candidate_envelope(
    bundle: dict[str, Any],
    inventory: dict[str, Any] | None,
    unit_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    if inventory is None:
        raise ValueError("structural_transaction_inventory_missing")
    if bundle["transaction_inventory_sha256"] != inventory.get("inventory_sha256"):
        raise ValueError("structural_transaction_inventory_hash_mismatch")
    authorization = inventory.get("scope_authorization")
    claims = inventory.get("claims")
    if not isinstance(authorization, dict) or not isinstance(claims, dict):
        raise ValueError("structural_transaction_inventory_authority_invalid")
    if (
        authorization.get("mechanical_scope_permission_granted") is not True
        or authorization.get("bound_transaction_bundle_required") is not True
        or authorization.get("candidate_inventory_is_execution_request") is not False
        or authorization.get("semantic_clearance_granted") is not False
        or claims.get("inventory_alone_execution_authorized") is not False
        or claims.get("semantic_mapping") != "NOT_EVALUATED"
    ):
        raise ValueError("structural_transaction_scope_not_authorized")
    candidates = inventory.get("transactions")
    if not isinstance(candidates, list):
        raise ValueError("structural_transaction_candidates_invalid")
    matches = [
        item
        for item in candidates
        if isinstance(item, dict)
        and item.get("transaction_id") == bundle["transaction_id"]
    ]
    if len(matches) != 1:
        raise ValueError("structural_transaction_candidate_not_unique")
    candidate = matches[0]
    if candidate.get("transaction_binding_sha256") != bundle[
        "transaction_binding_sha256"
    ]:
        raise ValueError("structural_transaction_binding_hash_mismatch")
    constraints = candidate.get("constraints")
    if not isinstance(constraints, dict) or (
        constraints.get("mechanical_scope_permission_granted") is not True
        or constraints.get("bound_transaction_bundle_required") is not True
        or constraints.get("candidate_inventory_is_execution_request") is not False
        or constraints.get("inventory_alone_execution_authorized") is not False
        or constraints.get("semantic_clearance_granted") is not False
        or constraints.get("atomic_pair_required") is not True
        or constraints.get("title_lock") is not True
        or constraints.get("cross_file") is not False
        or constraints.get("cross_heading") is not False
        or constraints.get("participant_split_or_delete") is not False
    ):
        raise ValueError("structural_transaction_candidate_constraints_invalid")
    compound_refs = candidate.get("compound_refs")
    if not isinstance(compound_refs, list) or len(compound_refs) != 2:
        raise ValueError("structural_transaction_compound_refs_invalid")
    candidate_unit_ids = [str(item.get("unit_id", "")) for item in compound_refs]
    binding_unit_ids = [str(item["unit_id"]) for item in bundle["unit_bindings"]]
    if binding_unit_ids != candidate_unit_ids or len(set(binding_unit_ids)) != 2:
        raise ValueError("structural_transaction_participant_mismatch")
    for binding, compound_ref in zip(bundle["unit_bindings"], compound_refs):
        unit_id = str(binding["unit_id"])
        unit = unit_map.get(unit_id)
        if unit is None:
            raise ValueError("structural_transaction_participant_unknown")
        if unit.get("status") != "PENDING" or str(unit.get("intensity", "")).upper() != "STRUCTURAL":
            raise ValueError("structural_transaction_participant_not_pending_structural")
        if (
            binding["chunk_binding_sha256"] != unit.get("chunk_binding_sha256")
            or binding["chunk_binding_sha256"]
            != compound_ref.get("chunk_binding_sha256")
        ):
            raise ValueError("structural_transaction_chunk_binding_mismatch")
        if binding["voice_profile_sha256"] != unit.get("voice_profile_sha256"):
            raise ValueError("structural_transaction_voice_binding_mismatch")
        if compound_ref.get("structural_inventory_sha256") != unit.get(
            "structural_inventory_sha256"
        ):
            raise ValueError("structural_transaction_source_inventory_mismatch")
    return candidate, candidate_unit_ids


def _bound_structural_transaction_candidate(
    bundle: dict[str, Any],
    inventory: dict[str, Any] | None,
    unit_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    _validate_structural_transaction_bundle_fields(bundle)
    candidate, candidate_unit_ids = _bound_structural_transaction_candidate_envelope(
        bundle, inventory, unit_map
    )
    fragment_unit_ids = [
        str(item["target_unit_id"]) for item in bundle["fragments"]
    ]
    if fragment_unit_ids != candidate_unit_ids:
        raise ValueError("structural_transaction_fragment_order_mismatch")
    return candidate


def _bound_structural_transaction_decline_candidate(
    bundle: dict[str, Any],
    inventory: dict[str, Any] | None,
    unit_map: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    _validate_structural_transaction_decline_fields(bundle)
    candidate, candidate_unit_ids = _bound_structural_transaction_candidate_envelope(
        bundle, inventory, unit_map
    )
    valid_refs = {
        (
            unit_id,
            str(paragraph.get("paragraph_id", "")),
        )
        for unit_id in candidate_unit_ids
        for paragraph in chunks[unit_id].get("structural_paragraphs", [])
        if isinstance(paragraph, dict) and paragraph.get("paragraph_id")
    }
    evidence_refs = [
        (str(item["unit_id"]), str(item["paragraph_id"]))
        for item in bundle["evidence_refs"]
    ]
    if any(item not in valid_refs for item in evidence_refs):
        raise ValueError("structural_transaction_decline_evidence_ref_unknown")
    evidenced_units = {unit_id for unit_id, _paragraph_id in evidence_refs}
    if evidenced_units != set(candidate_unit_ids):
        raise ValueError("structural_transaction_decline_evidence_member_coverage_mismatch")
    return candidate


def _transaction_source_inventory(
    unit_ids: Sequence[str],
    chunks: dict[str, dict[str, Any]],
) -> tuple[
    list[tuple[str, str]],
    dict[tuple[str, str], dict[str, Any]],
]:
    ordered_refs: list[tuple[str, str]] = []
    source_map: dict[tuple[str, str], dict[str, Any]] = {}
    for unit_id in unit_ids:
        chunk = chunks[unit_id]
        inventory = chunk.get("structural_paragraphs")
        if not isinstance(inventory, list) or not inventory:
            raise ValueError("structural_transaction_source_inventory_missing")
        blocks = preparer.structural_paragraph_blocks(str(chunk.get("masked_text", "")))
        if len(blocks) != len(inventory):
            raise ValueError("structural_transaction_source_blocks_mismatch")
        for item, block in zip(inventory, blocks):
            paragraph_id = str(item.get("paragraph_id", ""))
            ref = (unit_id, paragraph_id)
            if not paragraph_id or ref in source_map:
                raise ValueError("structural_transaction_source_ref_identity_invalid")
            record = dict(item)
            record["unit_id"] = unit_id
            record["block"] = block
            source_map[ref] = record
            ordered_refs.append(ref)
    return ordered_refs, source_map


def _validate_structural_transaction_fragment_plan(
    fragment: dict[str, Any],
    *,
    target_unit_id: str,
    ordered_source_refs: Sequence[tuple[str, str]],
    source_map: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    target_blocks = preparer.structural_paragraph_blocks(fragment["masked_text"])
    target_groups = fragment["target_groups"]
    if len(target_blocks) != len(target_groups):
        raise ValueError("structural_transaction_target_group_count_mismatch")
    source_positions = {
        source_ref: index for index, source_ref in enumerate(ordered_source_refs)
    }
    claimed_refs: list[tuple[str, str]] = []
    normalized_groups: list[list[tuple[str, str]]] = []
    baseline_blocks: list[str] = []
    target_protected_ids: list[str] = []
    cross_unit_moves = 0
    moved_or_regrouped_targets = 0
    structural_deltas: list[dict[str, Any]] = []
    for target_ordinal, (group, target_block) in enumerate(
        zip(target_groups, target_blocks), 1
    ):
        refs = [
            (str(item["unit_id"]), str(item["paragraph_id"]))
            for item in group["source_refs"]
        ]
        if any(source_ref not in source_map for source_ref in refs):
            raise ValueError("structural_transaction_source_ref_unknown")
        positions = [source_positions[source_ref] for source_ref in refs]
        if positions != list(range(min(positions), max(positions) + 1)):
            raise ValueError(
                "structural_transaction_merge_sources_must_be_adjacent_and_ordered"
            )
        responsibilities = {
            str(source_map[source_ref]["responsibility"]) for source_ref in refs
        }
        if len(responsibilities) != 1:
            raise ValueError("structural_transaction_merge_changes_responsibility")
        responsibility = next(iter(responsibilities))
        if group.get("responsibility") != responsibility:
            raise ValueError("structural_transaction_responsibility_claim_mismatch")
        if preparer._paragraph_responsibility(target_block) != responsibility:
            raise ValueError("structural_transaction_target_responsibility_drift")
        if not _specific_reason(str(group.get("reason", ""))):
            raise ValueError("structural_transaction_target_reason_not_specific")
        if group.get("target_paragraph_sha256") != sha256(
            target_block.encode("utf-8")
        ):
            raise ValueError("structural_transaction_target_paragraph_hash_mismatch")
        expected_protected_ids = [
            protected_id
            for source_ref in refs
            for protected_id in source_map[source_ref].get("protected_ids", [])
        ]
        actual_protected_ids = [
            match.group("id")
            for match in preparer.PROTECTED_PLACEHOLDER_RE.finditer(target_block)
        ]
        if actual_protected_ids != expected_protected_ids:
            raise ValueError(
                "structural_transaction_protected_span_left_source_paragraph"
            )
        for source_ref in refs:
            source = source_map[source_ref]
            if source_ref[0] != target_unit_id:
                cross_unit_moves += 1
            if not bool(source.get("movable")) and (
                source_ref[0] != target_unit_id
                or len(refs) != 1
                or target_ordinal != int(source["ordinal"])
            ):
                raise ValueError(
                    "structural_transaction_locked_paragraph_moved_or_merged"
                )
            change_kinds: list[str] = []
            if source_ref[0] != target_unit_id:
                change_kinds.append("CROSS_UNIT_MOVE")
            if int(source["ordinal"]) != target_ordinal or len(refs) > 1:
                change_kinds.append("MOVE_OR_REGROUP_SOURCE_PARAGRAPH")
            if change_kinds:
                structural_deltas.append(
                    {
                        "from_unit_id": source_ref[0],
                        "to_unit_id": target_unit_id,
                        "paragraph_id": source_ref[1],
                        "source_ordinal": int(source["ordinal"]),
                        "target_ordinal": target_ordinal,
                        "change_kinds": change_kinds,
                        "responsibility": responsibility,
                        "target_paragraph_sha256": str(
                            group["target_paragraph_sha256"]
                        ),
                        "reason": str(group["reason"]),
                    }
                )
        if len(refs) != 1 or refs[0][0] != target_unit_id or int(
            source_map[refs[0]]["ordinal"]
        ) != target_ordinal:
            moved_or_regrouped_targets += 1
        claimed_refs.extend(refs)
        normalized_groups.append(refs)
        target_protected_ids.extend(expected_protected_ids)
        baseline_blocks.append(
            " ".join(str(source_map[source_ref]["block"]).strip() for source_ref in refs)
        )
    baseline_masked_text = "\n\n".join(baseline_blocks)
    if str(fragment["masked_text"]).endswith(("\n", "\r")):
        baseline_masked_text += "\n"
    return {
        "status": "PASS",
        "target_unit_id": target_unit_id,
        "claimed_refs": claimed_refs,
        "normalized_groups": normalized_groups,
        "target_protected_ids": target_protected_ids,
        "cross_unit_moves": cross_unit_moves,
        "moved_or_regrouped_targets": moved_or_regrouped_targets,
        "target_paragraphs": len(target_blocks),
        "structural_deltas": structural_deltas,
        "semantic_mapping": "NOT_EVALUATED",
        "_baseline_masked_text": baseline_masked_text,
    }


def _public_transaction_plan_check(plan_check: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: value
        for key, value in plan_check.items()
        if not key.startswith("_") and key not in {"claimed_refs", "normalized_groups"}
    }
    public["claimed_refs"] = [
        {"unit_id": unit_id, "paragraph_id": paragraph_id}
        for unit_id, paragraph_id in plan_check.get("claimed_refs", [])
    ]
    public["normalized_groups"] = [
        [
            {"unit_id": unit_id, "paragraph_id": paragraph_id}
            for unit_id, paragraph_id in group
        ]
        for group in plan_check.get("normalized_groups", [])
    ]
    return public


def _build_structural_transaction_review_request(
    *,
    snapshot_id: str,
    bundle: dict[str, Any],
    candidate: dict[str, Any],
    transaction_result: dict[str, Any],
    fragment_results: dict[str, dict[str, Any]],
    document_gate: dict[str, Any],
) -> dict[str, Any]:
    unit_ids = [str(item["unit_id"]) for item in bundle["unit_bindings"]]
    artifact_fragments: dict[str, Any] = {}
    for unit_id in unit_ids:
        fragment = fragment_results[unit_id]
        artifact_fragments[unit_id] = {
            "chunk_binding_sha256": fragment["chunk_binding_sha256"],
            "voice_profile_sha256": fragment["voice_profile_sha256"],
            "source_before_sha256": sha256(fragment["original"].encode("utf-8")),
            "mechanical_baseline_sha256": sha256(
                fragment["invariant_before"].encode("utf-8")
            ),
            "candidate_after_sha256": sha256(fragment["restored"].encode("utf-8")),
            "plan_check_sha256": sha256(
                _canonical_json(fragment["plan_check_public"]).encode("utf-8")
            ),
            "validator_sha256": sha256(
                _canonical_json(fragment["validation_payload"]).encode("utf-8")
            ),
        }
    policy_hashes = {
        **output_validator._policy_hashes(),
        "finalizer_sha256": sha256(Path(__file__).resolve().read_bytes()),
        "preparer_sha256": sha256(Path(preparer.__file__).resolve().read_bytes()),
        "transaction_eligibility_policy_sha256": str(
            candidate.get("eligibility_policy_sha256", "")
        ),
    }
    source_mapping = [
        {
            "target_unit_id": str(fragment["target_unit_id"]),
            "target_groups": fragment["target_groups"],
        }
        for fragment in bundle["fragments"]
    ]
    structural_deltas: list[dict[str, Any]] = []
    for unit_id in unit_ids:
        for index, delta in enumerate(
            fragment_results[unit_id]["plan_check"].get(
                "structural_deltas", []
            ),
            1,
        ):
            structural_deltas.append(
                {
                    "delta_id": f"{bundle['transaction_id']}:{unit_id}:D{index:03d}",
                    **delta,
                }
            )
    context_hashes = {
        "outer_before_sha256": sha256(
            fragment_results[unit_ids[0]]["context_before"].encode("utf-8")
        ),
        "internal_left_after_sha256": sha256(
            fragment_results[unit_ids[0]]["context_after"].encode("utf-8")
        ),
        "internal_right_before_sha256": sha256(
            fragment_results[unit_ids[1]]["context_before"].encode("utf-8")
        ),
        "outer_after_sha256": sha256(
            fragment_results[unit_ids[1]]["context_after"].encode("utf-8")
        ),
    }
    transaction_bundle_has_fragment_intent = (
        bundle.get("schema_version")
        in STRUCTURAL_TRANSACTION_BUNDLE_LOCAL_INTENT_SCHEMAS
    )
    request_body = {
        "schema": (
            STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA
            if transaction_bundle_has_fragment_intent
            else STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA_V1
        ),
        "status": "PENDING_EXTERNAL_REVIEW",
        "snapshot_id": snapshot_id,
        "transaction_id": bundle["transaction_id"],
        "unit_ids": unit_ids,
        "transaction_bundle_sha256": transaction_result["bundle_sha256"],
        "transaction_binding_sha256": bundle["transaction_binding_sha256"],
        "transaction_inventory_sha256": bundle["transaction_inventory_sha256"],
        "source_member_claim_sha256": transaction_result[
            "source_member_claim_sha256"
        ],
        "frozen_pair": {
            "candidate_scope": candidate.get("candidate_scope"),
            "file_id": candidate.get("file_id"),
            "heading_path": candidate.get("heading_path"),
            "scene": candidate.get("scene"),
            "boundary": candidate.get("boundary"),
            "compound_refs": candidate.get("compound_refs"),
            "constraints": candidate.get("constraints"),
        },
        "context_hashes": context_hashes,
        "source_mapping": source_mapping,
        "structural_deltas": structural_deltas,
        "artifacts": {
            "fragments": artifact_fragments,
            "document": {
                "mechanical_baseline_sha256": document_gate[
                    "mechanical_baseline_sha256"
                ],
                "candidate_after_sha256": document_gate["candidate_after_sha256"],
                "gate_evidence_sha256": document_gate["evidence_sha256"],
            },
        },
        "artifact_refs": {
            unit_id: {
                "before": f"validation/{unit_id}.before{fragment_results[unit_id]['suffix']}",
                "after": f"validation/{unit_id}.after{fragment_results[unit_id]['suffix']}",
                "validator": f"validation/{unit_id}.validation.json",
                "mechanical_plan": f"validation/{unit_id}.structural.json",
            }
            for unit_id in unit_ids
        },
        "document_gate": {
            "status": document_gate["status"],
            "format": document_gate["document_format"],
            "error_count": document_gate["error_count"],
        },
        "required_review_dimensions": [
            "CROSS_UNIT_PARAGRAPH_DEPENDENCY_AND_REFERENT_PRESERVED",
            "CLAIM_EVIDENCE_AND_CAUSAL_SCOPE_PRESERVED",
            "NEGATION_MODALITY_FOCUS_AND_CONDITION_PRESERVED",
            "TARGET_FRAGMENT_BOUNDARY_AND_READING_ORDER_ACCEPTABLE",
        ],
        "policy_hashes": policy_hashes,
        "trust_boundary": {
            "semantic_mapping": "NOT_EVALUATED",
            "academic_correctness": "NOT_EVALUATED",
            "local_clearance_supported": False,
            "external_signature_verified": False,
            "completion_claim_allowed": False,
        },
    }
    if transaction_bundle_has_fragment_intent:
        fragments_by_unit = {
            str(item["target_unit_id"]): item for item in bundle["fragments"]
        }
        request_body["fragment_rewrite_intents"] = {
            unit_id: {
                "status": str(fragment_results[unit_id]["rewrite_intent_status"]),
                "decision": str(
                    fragment_results[unit_id]["rewrite_intent_decision"]
                ),
                "fragment_sha256": sha256(
                    _canonical_json(fragments_by_unit[unit_id]).encode("utf-8")
                ),
                "local_rewrite_intent_sha256": sha256(
                    _canonical_json(
                        fragments_by_unit[unit_id]["local_rewrite_intent"]
                    ).encode("utf-8")
                ),
                "intent_diff_binding_sha256": sha256(
                    _canonical_json(
                        fragment_results[unit_id]["rewrite_intent_diff_binding"]
                    ).encode("utf-8")
                ),
            }
            for unit_id in unit_ids
        }
    return {
        **request_body,
        "request_sha256": sha256(_canonical_json(request_body).encode("utf-8")),
    }


def _validate_structural_transaction(
    *,
    bundle: dict[str, Any],
    candidate: dict[str, Any],
    snapshot_id: str,
    unit_map: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    file_texts: dict[str, str],
    file_suffixes: dict[str, str],
    span_map: dict[str, dict[str, Any]],
    validation_dir: Path,
    editable_style_wrappers: Sequence[str] = (),
) -> dict[str, Any]:
    unit_ids = [str(item["unit_id"]) for item in bundle["unit_bindings"]]
    transaction_intent_schema_status = _validate_structural_transaction_bundle_fields(
        bundle
    )
    transaction_bundle_has_fragment_intent = (
        bundle.get("schema_version")
        in STRUCTURAL_TRANSACTION_BUNDLE_LOCAL_INTENT_SCHEMAS
    )
    ordered_source_refs, source_map = _transaction_source_inventory(unit_ids, chunks)
    fragment_gate_statuses = {unit_id: "NOT_RUN" for unit_id in unit_ids}
    fragment_intent_statuses = {
        unit_id: "NOT_RUN" for unit_id in unit_ids
    }
    fragment_results: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    claimed_refs: list[tuple[str, str]] = []
    total_cross_unit_moves = 0
    for binding, fragment in zip(bundle["unit_bindings"], bundle["fragments"]):
        unit_id = str(binding["unit_id"])
        unit = unit_map[unit_id]
        suffix = file_suffixes.get(str(unit["file_id"]), ".txt") or ".txt"
        source_text = file_texts[str(unit["file_id"])]
        original = source_text[int(unit["start"]):int(unit["end"])]
        try:
            plan_check = _validate_structural_transaction_fragment_plan(
                fragment,
                target_unit_id=unit_id,
                ordered_source_refs=ordered_source_refs,
                source_map=source_map,
            )
            baseline_masked = str(plan_check.pop("_baseline_masked_text"))
            local_intent_check = _validate_transaction_fragment_local_intent(
                fragment,
                baseline_masked,
                str(fragment["masked_text"]),
                transaction_intent_schema_status,
            )
            fragment_intent_statuses[unit_id] = str(
                local_intent_check["status"]
            )
            target_protected_ids = list(plan_check["target_protected_ids"])
            invariant_before, baseline_errors = restore_protected(
                baseline_masked, target_protected_ids, span_map
            )
            if invariant_before is None:
                raise ValueError(
                    "structural_transaction_baseline_restore:"
                    + "|".join(baseline_errors)
                )
            restored, restore_errors = restore_protected(
                str(fragment["masked_text"]), target_protected_ids, span_map
            )
            if restored is None:
                raise ValueError(
                    "structural_transaction_candidate_restore:"
                    + "|".join(restore_errors)
                )
            keep_reasons = output_validator._parse_keep_reasons(
                [f"{key}={value}" for key, value in fragment["keep_reasons"].items()],
                {
                    item["id"]
                    for item in output_validator.lexical.load_lexicon()["signals"]
                },
            )
            before_path = validation_dir / f"{unit_id}.before{suffix}"
            after_path = validation_dir / f"{unit_id}.after{suffix}"
            before_path.write_text(invariant_before, encoding="utf-8", newline="")
            after_path.write_text(restored, encoding="utf-8", newline="")
            try:
                template_field_edit_scope_path = (
                    _materialize_unit_template_field_edit_scope(
                        fragment,
                        decision=str(local_intent_check["decision"]),
                        before_path=before_path,
                        validation_dir=validation_dir,
                        unit_id=unit_id,
                    )
                )
            except (OSError, ValueError) as error:
                raise ValueError(
                    f"invalid_template_field_edit_scope:{error}"
                ) from error
            validation_payload = output_validator.validate(
                before_path,
                after_path,
                scene=str(unit["scene"]),
                keep_reasons=keep_reasons,
                fragment_mode=True,
                template_field_edit_scope_path=template_field_edit_scope_path,
                editable_style_wrappers=editable_style_wrappers,
            )
            _stabilize_validation_evidence_refs(validation_payload, unit_id, suffix)
            paired_quality_request = _persist_paired_quality_review_request(
                validation_payload, validation_dir, unit_id
            )
            plan_check_public = _public_transaction_plan_check(plan_check)
            plan_check_public["rewrite_intent_status"] = str(
                local_intent_check["status"]
            )
            plan_check_public["rewrite_intent_decision"] = str(
                local_intent_check["decision"]
            )
            validation_payload["structural_plan_check"] = plan_check_public
            _write_json(
                validation_dir / f"{unit_id}.validation.json", validation_payload
            )
            _write_json(
                validation_dir / f"{unit_id}.structural.json", plan_check_public
            )
            fragment_gate_statuses[unit_id] = str(
                validation_payload["mechanical_validation_status"]
            )
            fragment_results[unit_id] = {
                "unit_id": unit_id,
                "suffix": suffix,
                "original": original,
                "baseline_masked": baseline_masked,
                "invariant_before": invariant_before,
                "restored": restored,
                "plan_check": plan_check,
                "plan_check_public": plan_check_public,
                "validation_payload": validation_payload,
                "paired_quality_review_request": paired_quality_request,
                "rewrite_intent_status": str(local_intent_check["status"]),
                "rewrite_intent_decision": str(local_intent_check["decision"]),
                "rewrite_intent_reason_code": str(
                    local_intent_check["reason_code"]
                ),
                "rewrite_intent_diff_binding": local_intent_check[
                    "intent_diff_binding"
                ],
                "chunk_binding_sha256": str(binding["chunk_binding_sha256"]),
                "voice_profile_sha256": str(binding["voice_profile_sha256"]),
                "context_before": str(
                    chunks[unit_id].get("read_only_context_before", "")
                ),
                "context_after": str(
                    chunks[unit_id].get("read_only_context_after", "")
                ),
            }
            claimed_refs.extend(plan_check["claimed_refs"])
            total_cross_unit_moves += int(plan_check["cross_unit_moves"])
            if validation_payload["mechanical_validation_status"] != "PASS":
                errors.append(
                    f"{unit_id}:fragment_validator:"
                    f"{validation_payload['mechanical_validation_status']}"
                )
            elif not _quality_review_only(validation_payload):
                errors.append(f"{unit_id}:paired_quality_review_request_missing")
        except (KeyError, TypeError, ValueError) as error:
            error_text = str(error)
            fragment_gate_statuses[unit_id] = (
                "REVIEW"
                if error_text.startswith("invalid_template_field_edit_scope:")
                else "FAIL"
            )
            if transaction_bundle_has_fragment_intent and (
                "rewrite_intent" in error_text
                or "NO_CHANGE" in error_text
                or "local_rewrite" in error_text
            ):
                fragment_intent_statuses[unit_id] = "FAIL"
            errors.append(f"{unit_id}:{error_text}")

    bundle_sha256 = _structural_transaction_bundle_sha256(bundle)
    fragment_gate_blocked = bool(
        errors
        or any(status != "PASS" for status in fragment_gate_statuses.values())
    )
    current_schema_blocked = transaction_intent_schema_status != "PASS"
    if current_schema_blocked:
        errors.append("structural_transaction_current_v3_schema_required")
    transaction_result: dict[str, Any] = {
        "transaction_id": bundle["transaction_id"],
        "bundle_sha256": bundle_sha256,
        "unit_ids": unit_ids,
        "status": "REVIEW",
        "atomic_gate_status": "ROLLED_BACK",
        "source_member_claim_status": "NOT_RUN",
        "source_member_claim_sha256": "",
        "fragment_gate_statuses": fragment_gate_statuses,
        "fragment_rewrite_intent_statuses": fragment_intent_statuses,
        "rewrite_intent_schema_status": transaction_intent_schema_status,
        "document_gate_status": "NOT_RUN",
        "change_applied": False,
        "cross_unit_moves_applied": 0,
        "rollback_reason": (
            "FRAGMENT_GATE"
            if fragment_gate_blocked
            else "SCHEMA_GATE"
            if current_schema_blocked
            else ""
        ),
        "errors": errors,
        "review_request": {},
    }
    if fragment_gate_blocked or current_schema_blocked:
        return {**transaction_result, "_fragment_results": fragment_results}

    expected_set = set(ordered_source_refs)
    claimed_set = set(claimed_refs)
    claim_payload = [
        {"unit_id": unit_id, "paragraph_id": paragraph_id}
        for unit_id, paragraph_id in claimed_refs
    ]
    transaction_result["source_member_claim_sha256"] = sha256(
        _canonical_json(claim_payload).encode("utf-8")
    )
    if (
        len(claimed_refs) != len(ordered_source_refs)
        or len(claimed_set) != len(claimed_refs)
        or claimed_set != expected_set
    ):
        transaction_result["source_member_claim_status"] = "FAIL"
        transaction_result["rollback_reason"] = "SOURCE_MEMBER_CLAIM"
        transaction_result["errors"].append(
            "structural_transaction_source_member_claim_mismatch"
        )
        return {**transaction_result, "_fragment_results": fragment_results}
    transaction_result["source_member_claim_status"] = "PASS"
    if total_cross_unit_moves <= 0:
        transaction_result["rollback_reason"] = "NO_CROSS_UNIT_MOVE"
        transaction_result["errors"].append(
            "structural_transaction_requires_real_cross_unit_move"
        )
        return {**transaction_result, "_fragment_results": fragment_results}

    first_chunk = chunks[unit_ids[0]]
    second_chunk = chunks[unit_ids[1]]
    pair_original = "".join(fragment_results[unit_id]["original"] for unit_id in unit_ids)
    pair_candidate = "".join(fragment_results[unit_id]["restored"] for unit_id in unit_ids)
    transaction_protected_ids = [
        protected_id
        for source_ref in ordered_source_refs
        for protected_id in source_map[source_ref].get("protected_ids", [])
    ]
    protected_count_changes = _protected_content_count_changes(
        pair_original,
        pair_candidate,
        transaction_protected_ids,
        span_map,
    )
    if protected_count_changes:
        transaction_result["rollback_reason"] = "PROTECTED_CONTENT_COUNT"
        transaction_result["errors"].append(
            "structural_transaction_protected_content_count_changed:"
            + ",".join(protected_count_changes)
        )
        return {**transaction_result, "_fragment_results": fragment_results}
    copied_context = _copied_read_only_context(
        pair_original,
        pair_candidate,
        {
            "read_only_context_before": first_chunk.get(
                "read_only_context_before", ""
            ),
            "read_only_context_after": second_chunk.get(
                "read_only_context_after", ""
            ),
        },
    )
    if copied_context:
        transaction_result["rollback_reason"] = "READ_ONLY_CONTEXT"
        transaction_result["errors"].append(
            "structural_transaction_read_only_context_copied:"
            + ",".join(copied_context)
        )
        return {**transaction_result, "_fragment_results": fragment_results}

    file_id = str(unit_map[unit_ids[0]]["file_id"])
    source_text = file_texts[file_id]
    mechanical_document = source_text
    candidate_document = source_text
    replacements = [
        (
            int(unit_map[unit_id]["start"]),
            int(unit_map[unit_id]["end"]),
            fragment_results[unit_id]["invariant_before"],
            fragment_results[unit_id]["restored"],
        )
        for unit_id in unit_ids
    ]
    for start, end, baseline, restored in sorted(
        replacements, key=lambda item: item[0], reverse=True
    ):
        mechanical_document = mechanical_document[:start] + baseline + mechanical_document[end:]
        candidate_document = candidate_document[:start] + restored + candidate_document[end:]
    suffix = file_suffixes.get(file_id, "")
    document_format = "tex" if suffix.lower() in {".tex", ".ltx"} else "markdown"
    full_check = invariants.check_documents(
        mechanical_document,
        candidate_document,
        document_format=document_format,
        editable_style_wrappers=editable_style_wrappers,
    )
    full_check_payload = full_check.to_dict()
    document_gate = {
        "status": "FAIL" if full_check.errors else "PASS",
        "document_format": document_format,
        "error_count": len(full_check.errors),
        "mechanical_baseline_sha256": sha256(mechanical_document.encode("utf-8")),
        "candidate_after_sha256": sha256(candidate_document.encode("utf-8")),
        "evidence_sha256": sha256(
            _canonical_json(full_check_payload).encode("utf-8")
        ),
        "evidence": full_check_payload,
    }
    transaction_result["document_gate_status"] = document_gate["status"]
    if full_check.errors:
        transaction_result["rollback_reason"] = "DOCUMENT_GATE"
        transaction_result["errors"].append(
            "structural_transaction_document_gate_failed"
        )
        return {
            **transaction_result,
            "_fragment_results": fragment_results,
            "_document_gate": document_gate,
        }

    transaction_result.update(
        {
            "status": "PASS",
            "atomic_gate_status": "PASS",
            "change_applied": True,
            "cross_unit_moves_applied": total_cross_unit_moves,
            "rollback_reason": "",
        }
    )
    review_request = _build_structural_transaction_review_request(
        snapshot_id=snapshot_id,
        bundle=bundle,
        candidate=candidate,
        transaction_result=transaction_result,
        fragment_results=fragment_results,
        document_gate=document_gate,
    )
    return {
        **transaction_result,
        "_fragment_results": fragment_results,
        "_document_gate": document_gate,
        "_review_request": review_request,
    }


def _build_structural_semantic_review_request(
    *,
    snapshot_id: str,
    unit_id: str,
    unit: dict[str, Any],
    chunk: dict[str, Any],
    bundle: dict[str, Any],
    structural_plan_check: dict[str, Any],
    original: str,
    invariant_before: str,
    restored: str,
    validation_payload: dict[str, Any],
    suffix: str,
) -> dict[str, Any] | None:
    """Build a review-only request for one mechanically valid structural change.

    The request deliberately has no local clearance field. It binds the candidate and
    mechanical evidence for an external reviewer, but cannot upgrade semantic status.
    """

    actual_content_changed = invariant_before != restored
    declared_structural_change = structural_plan_check.get("change_applied") is True
    if (
        structural_plan_check.get("status") != "PASS"
        or not (actual_content_changed or declared_structural_change)
        or validation_payload.get("hard_invariant_layer_status") != "PASS"
    ):
        return None
    plan = bundle.get("structural_plan")
    if not isinstance(plan, dict):
        return None
    source_inventory = chunk.get("structural_paragraphs")
    if not isinstance(source_inventory, list):
        return None
    source_by_id = {
        str(item.get("paragraph_id")): item
        for item in source_inventory
        if isinstance(item, dict)
    }
    target_groups = plan.get("target_groups")
    if not isinstance(target_groups, list):
        return None

    structural_deltas: list[dict[str, Any]] = []
    for target_ordinal, group in enumerate(target_groups, 1):
        if not isinstance(group, dict):
            continue
        source_ids = [str(item) for item in group.get("source_paragraph_ids", [])]
        source_ordinals = [
            int(source_by_id[item]["ordinal"])
            for item in source_ids
            if item in source_by_id
        ]
        change_kinds: list[str] = []
        if len(source_ids) > 1:
            change_kinds.append("MERGE_ADJACENT_SOURCE_PARAGRAPHS")
        if source_ordinals and source_ordinals[0] != target_ordinal:
            change_kinds.append("MOVE_OR_REGROUP_SOURCE_PARAGRAPHS")
        if not change_kinds:
            continue
        structural_deltas.append(
            {
                "delta_id": f"SD-{target_ordinal:03d}",
                "change_kinds": change_kinds,
                "target_ordinal": target_ordinal,
                "source_paragraph_ids": source_ids,
                "source_ordinals": source_ordinals,
                "responsibility": str(group.get("responsibility", "")),
                "reason": str(group.get("reason", "")),
                "target_paragraph_sha256": str(
                    group.get("target_paragraph_sha256", "")
                ),
            }
        )

    # A STRUCTURAL rewrite that changes text while declaring the default
    # one-to-one paragraph mapping is still semantically unaccounted for.  Do
    # not infer that it was merely local style editing: bind an explicit
    # reviewer delta so hidden payload swaps cannot become a PASS by omission.
    if not structural_deltas and structural_plan_check.get("change_applied") is not True:
        structural_deltas.append(
            {
                "delta_id": "SD-UNDECLARED-001",
                "change_kinds": ["UNDECLARED_CONTENT_CHANGE"],
                "target_ordinal": None,
                "source_paragraph_ids": [
                    str(item.get("paragraph_id", ""))
                    for item in source_inventory
                    if isinstance(item, dict)
                ],
                "source_ordinals": [
                    int(item.get("ordinal", 0))
                    for item in source_inventory
                    if isinstance(item, dict)
                ],
                "responsibility": "UNRESOLVED",
                "reason": "STRUCTURAL 文本发生变化，但 plan 未声明段落移动或合并；需要外部语义复核。",
                "target_paragraph_sha256": "",
            }
        )

    warning_request = validation_payload.get("warning_review_request")
    speech_act_warnings = (
        warning_request.get("warnings", [])
        if isinstance(warning_request, dict)
        else []
    )
    policy_hashes = {
        **output_validator._policy_hashes(),
        "finalizer_sha256": sha256(Path(__file__).resolve().read_bytes()),
        "preparer_sha256": sha256(Path(preparer.__file__).resolve().read_bytes()),
    }
    artifact_stem = f"validation/{unit_id}"
    request_body = {
        "schema": STRUCTURAL_SEMANTIC_REVIEW_REQUEST_SCHEMA,
        "status": "PENDING_EXTERNAL_REVIEW",
        "snapshot_id": snapshot_id,
        "unit_id": unit_id,
        "artifact": {
            "chunk_binding_sha256": str(unit.get("chunk_binding_sha256", "")),
            "voice_profile_sha256": str(unit.get("voice_profile_sha256", "")),
            "source_inventory_sha256": str(
                structural_plan_check.get("source_inventory_sha256", "")
            ),
            "structural_plan_sha256": sha256(
                _canonical_json(plan).encode("utf-8")
            ),
            "source_before_sha256": sha256(original.encode("utf-8")),
            "structural_baseline_masked_sha256": str(
                structural_plan_check.get("invariant_baseline_sha256", "")
            ),
            "structural_baseline_restored_sha256": sha256(
                invariant_before.encode("utf-8")
            ),
            "candidate_after_sha256": sha256(restored.encode("utf-8")),
            "context_before_sha256": sha256(
                str(chunk.get("read_only_context_before", "")).encode("utf-8")
            ),
            "context_after_sha256": sha256(
                str(chunk.get("read_only_context_after", "")).encode("utf-8")
            ),
        },
        "artifact_refs": {
            "before": f"{artifact_stem}.before{suffix}",
            "after": f"{artifact_stem}.after{suffix}",
            "mechanical_plan": f"{artifact_stem}.structural.json",
            "validator": f"{artifact_stem}.validation.json",
        },
        "mechanical_status": {
            "structural_plan_status": "PASS",
            "hard_invariant_layer_status": "PASS",
            "change_applied": actual_content_changed,
            "scope": str(structural_plan_check.get("scope", "")),
            "title_lock": bool(structural_plan_check.get("title_lock")),
            "cross_unit_moves_allowed": bool(
                structural_plan_check.get("cross_unit_moves_allowed")
            ),
        },
        "structural_deltas": structural_deltas,
        "speech_act_warnings": speech_act_warnings,
        "required_review_dimensions": [
            "PARAGRAPH_DEPENDENCY_AND_REFERENT_PRESERVED",
            "CLAIM_EVIDENCE_AND_CAUSAL_SCOPE_PRESERVED",
            "NEGATION_MODALITY_FOCUS_AND_CONDITION_PRESERVED",
            "PARAGRAPH_RESPONSIBILITY_AND_READING_ORDER_ACCEPTABLE",
        ],
        "policy_hashes": policy_hashes,
        "trust_boundary": {
            "semantic_mapping": "NOT_EVALUATED",
            "academic_correctness": "NOT_EVALUATED",
            "local_clearance_supported": False,
            "external_signature_verified": False,
            "completion_claim_allowed": False,
        },
    }
    return {
        **request_body,
        "request_sha256": sha256(_canonical_json(request_body).encode("utf-8")),
    }


def _stabilize_validation_evidence_refs(
    payload: dict[str, Any], unit_id: str, suffix: str
) -> None:
    """Replace transient staging paths with committed run-relative artifact refs."""

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return
    evidence["before_path"] = f"validation/{unit_id}.before{suffix}"
    evidence["after_path"] = f"validation/{unit_id}.after{suffix}"


def _persist_paired_quality_review_request(
    payload: dict[str, Any],
    validation_dir: Path,
    unit_id: str,
) -> dict[str, Any] | None:
    request = payload.get("paired_quality_review_request")
    if not isinstance(request, dict):
        return None
    request_name = f"{unit_id}.paired-quality-review-request.json"
    _write_json(validation_dir / request_name, request)
    return {
        "status": str(request.get("status", "NOT_EVALUATED")),
        "path": str(Path("validation") / request_name).replace("\\", "/"),
        "request_sha256": str(request.get("request_sha256", "")),
        "decision": str(
            request.get("validation_context", {}).get("decision", "")
        ),
        "changes_total": len(request.get("changes", [])),
        "quality_clearance_granted": False,
    }


def _quality_review_only(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("mechanical_validation_status") == "PASS"
        and payload.get("paired_quality_review_status")
        == "PENDING_EXTERNAL_REVIEW"
        and payload.get("status") == "REVIEW"
        and set(payload.get("review_reasons", []))
        == {"paired_quality_not_evaluated"}
    )


def _discard_paired_quality_review_request(
    requests: dict[str, dict[str, Any]],
    validation_dir: Path,
    unit_id: str,
) -> None:
    record = requests.pop(unit_id, None)
    request_name = f"{unit_id}.paired-quality-review-request.json"
    if isinstance(record, dict):
        relative_path = str(record.get("path", ""))
        if relative_path:
            request_name = Path(relative_path).name
    # Fragment validation persists this file before the transaction-wide gate
    # is known, so a rolled-back pair may not yet have a public request record.
    path = validation_dir / request_name
    if path.is_file():
        path.unlink()


def collect_rewrites(
    directory: Path,
    *,
    run_dir: Path | None = None,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    rewrites: dict[str, dict[str, Any]] = {}
    transactions: dict[str, dict[str, Any]] = {}
    declines: dict[str, dict[str, Any]] = {}
    scaffold_metadata: dict[str, Any] | None = None
    scaffold_metadata_path: Path | None = None
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    uncommitted_marker = directory / SCAFFOLD_UNCOMMITTED_MARKER_NAME
    if os.path.lexists(uncommitted_marker):
        raise ValueError(
            "rewrite scaffold publication is uncommitted; refuse incomplete output"
        )
    committed_marker_path = directory / SCAFFOLD_COMMITTED_MARKER_NAME
    committed_marker: Any | None = None
    if os.path.lexists(committed_marker_path):
        if _is_link_or_reparse(committed_marker_path):
            raise ValueError("scaffold publication commit must not be a link")
        marker_stat = committed_marker_path.stat(follow_symlinks=False)
        if not stat.S_ISREG(marker_stat.st_mode) or marker_stat.st_nlink != 1:
            raise ValueError(
                "scaffold publication commit must be a standalone regular file"
            )
        committed_marker = _load_json(committed_marker_path)
    for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.lower() not in {".json", ".txt"}:
            continue
        if path.name == SCAFFOLD_METADATA_NAME:
            if path.suffix.lower() != ".json":
                raise ValueError("scaffold metadata must be JSON")
            if scaffold_metadata is not None:
                raise ValueError("duplicate scaffold metadata")
            loaded_metadata = _load_json(path)
            _validate_scaffold_metadata(loaded_metadata, path)
            scaffold_metadata = loaded_metadata
            scaffold_metadata_path = path
            continue
        unit_id = path.stem
        payload = _rewrite_bundle(path)
        payload["bundle_path"] = str(path.resolve())
        if (
            {"transaction_id", "unit_bindings", "fragments"}.issubset(payload)
            and payload.get("schema_version")
            not in STRUCTURAL_TRANSACTION_BUNDLE_SCHEMAS
        ):
            raise ValueError("structural_transaction_bundle_schema_invalid")
        if payload.get("schema_version") in STRUCTURAL_TRANSACTION_BUNDLE_SCHEMAS:
            if path.suffix.lower() != ".json":
                raise ValueError("structural transaction bundle must be JSON")
            _validate_structural_transaction_bundle_fields(payload)
            transaction_id = str(payload["transaction_id"])
            if transaction_id in transactions:
                raise ValueError(
                    f"duplicate structural transaction for {transaction_id}"
                )
            transactions[transaction_id] = payload
            continue
        if payload.get("schema_version") == STRUCTURAL_TRANSACTION_DECLINE_SCHEMA:
            if path.suffix.lower() != ".json":
                raise ValueError("structural transaction decline must be JSON")
            _validate_structural_transaction_decline_fields(payload)
            transaction_id = str(payload["transaction_id"])
            if transaction_id in declines:
                raise ValueError(
                    f"duplicate structural transaction decline for {transaction_id}"
                )
            declines[transaction_id] = payload
            continue
        if unit_id in rewrites:
            raise ValueError(f"duplicate rewrite for {unit_id}")
        rewrites[unit_id] = payload
    if scaffold_metadata is not None:
        assert scaffold_metadata_path is not None
        _validate_scaffold_bundle_consistency(
            scaffold_metadata,
            rewrites,
            scaffold_metadata_path,
            run_dir,
            transactions,
        )
        if scaffold_metadata.get("schema_version") == "humanize-rewrite-scaffold/v5":
            if committed_marker is None:
                raise ValueError("v5 rewrite scaffold is missing publication commit")
            _validate_scaffold_publication_commit(
                committed_marker,
                committed_marker_path,
                scaffold_metadata,
                scaffold_metadata_path,
            )
        elif committed_marker is not None:
            raise ValueError(
                "scaffold publication commit is unsupported for legacy metadata"
            )
    elif committed_marker is not None:
        raise ValueError("scaffold publication commit has no scaffold metadata")
    return rewrites, transactions, declines


def _placeholder_token(span: dict[str, Any]) -> str:
    return f"[[PROTECTED:{span['protected_id']}:{span['sha256'][:12]}]]"


def restore_protected(
    masked_text: str,
    expected_ids: Sequence[str],
    span_map: dict[str, dict[str, Any]],
) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    expected = set(expected_ids)
    seen_matches = list(PLACEHOLDER_RE.finditer(masked_text))
    seen_ids = [match.group("id") for match in seen_matches]
    unknown = sorted(set(seen_ids) - expected)
    missing = sorted(expected - set(seen_ids))
    duplicates = sorted(item for item, count in Counter(seen_ids).items() if count != 1)
    if unknown:
        errors.append("unknown_placeholders:" + ",".join(unknown))
    if missing:
        errors.append("missing_placeholders:" + ",".join(missing))
    if duplicates:
        errors.append("duplicate_placeholders:" + ",".join(duplicates))
    for match in seen_matches:
        protected_id = match.group("id")
        span = span_map.get(protected_id)
        if span and match.group("hash") != span["sha256"][:12]:
            errors.append(f"placeholder_hash_mismatch:{protected_id}")
    if errors:
        return None, errors
    restored = masked_text
    for protected_id in expected_ids:
        span = span_map[protected_id]
        restored = restored.replace(_placeholder_token(span), span["content"])
    if "[[PROTECTED:" in restored:
        errors.append("placeholder_remained_after_restore")
        return None, errors
    return restored, []


def _specific_reason(reason: str) -> bool:
    return len(re.findall(r"[\u3400-\u9fff]", reason)) >= 4


def _specific_intent_summary(summary: str) -> bool:
    han = "".join(re.findall(r"[\u3400-\u9fff]", summary))
    if len(han) < 6:
        return False
    return han not in {
        "进行改写",
        "改写该段",
        "优化表达",
        "提升文风",
        "让表达更自然",
        "使表达更加自然",
        "按照要求修改",
    }


def _incomplete_authoring_code(
    bundle: Mapping[str, Any], decision: str
) -> str | None:
    """Identify an unfilled scaffold without weakening bundle validation."""

    if decision == "REWRITE":
        intent = bundle.get("rewrite_intent")
        if not isinstance(intent, dict):
            return None
        if (
            intent.get("summary") in {"TODO", REWRITE_INTENT_TODO}
            or intent.get("operations") == []
            or intent.get("source_spans") == []
            or intent.get("target_signals") == []
        ):
            return "REWRITE_INTENT_AUTHORING_INCOMPLETE"
        return None
    if decision == "NO_CHANGE" and (
        bundle.get("reason") in {"TODO", NO_CHANGE_REASON_TODO}
        or bundle.get("evidence_spans") == []
    ):
        return "NO_CHANGE_AUTHORING_INCOMPLETE"
    return None


def _no_change_reason_issue(reason: str) -> str | None:
    han = "".join(re.findall(r"[\u3400-\u9fff]", reason))
    if len(han) < 8:
        return "too_short_han"
    if han in {
        "保持原样",
        "无需修改",
        "符合要求",
        "已经自然",
        "没有问题",
        "原文结构自然",
        "该段保持原有自然表达",
        "原句已经直接",
        "题解表达已经直接",
        "该段属于自然简短陈述",
    }:
        return "generic_template"
    if not re.search(
        r"定义|段落|原句|标题|引语|公式|术语|结构|职责|对象|范围|条件|"
        r"指代|否定|模态|因果|并列|题干|题解|用户|锁定|证据|主张|顺序|层级",
        reason,
    ):
        return "missing_function_anchor"
    return None


def _specific_no_change_reason(reason: str) -> bool:
    return _no_change_reason_issue(reason) is None


def _no_change_reason_error(reason: str) -> str:
    issue = _no_change_reason_issue(reason)
    if issue is None:
        return ""
    return (
        f"NO_CHANGE_reason_invalid:{issue};"
        "required=min_han_8+specific_function_anchor;"
        "reason_redacted=true"
    )


UNRESOLVED_CODE_SCHEMA = "humanize-unresolved-code/v1"
UNRESOLVED_CODE_VALUES = frozenset(
    {
        "PREPARE_UNRESOLVED",
        "STRUCTURAL_TRANSACTION_ROLLED_BACK",
        "REWRITE_SUBMITTED_FOR_NON_PENDING_UNIT",
        "REWRITE_DECISION_UNSUPPORTED",
        "CHUNK_BINDING_INVALID",
        "VOICE_PROFILE_BINDING_INVALID",
        "REWRITE_BUNDLE_INVALID",
        "REWRITE_INTENT_OPERATION_FIELDS_INVALID",
        "REWRITE_INTENT_SOURCE_SPANS_FIELDS_INVALID",
        "REWRITE_INTENT_SOURCE_SPANS_HASH_MISMATCH",
        "REWRITE_INTENT_OPERATION_SOURCE_SPANS_INVALID",
        "REWRITE_INTENT_OPERATION_TARGET_SIGNALS_INVALID",
        "REWRITE_INTENT_SOURCE_SPAN_COVERAGE_INCOMPLETE",
        "REWRITE_INTENT_TARGET_SIGNAL_COVERAGE_INCOMPLETE",
        "REWRITE_INTENT_SOURCE_SPANS_OUTSIDE_DIFF",
        "REWRITE_INTENT_DIFF_OUTSIDE_DECLARED_SPANS",
        "REWRITE_INTENT_AUTHORING_INCOMPLETE",
        "NO_CHANGE_AUTHORING_INCOMPLETE",
        "NO_CHANGE_STRUCTURAL_PLAN_FORBIDDEN",
        "NO_CHANGE_REASON_TOO_SHORT_HAN",
        "NO_CHANGE_REASON_GENERIC_TEMPLATE",
        "NO_CHANGE_REASON_MISSING_FUNCTION_ANCHOR",
        "NO_CHANGE_REASON_INVALID_LEGACY",
        "NO_CHANGE_INTENT_INVALID",
        "NO_CHANGE_EVIDENCE_SPANS_EMPTY",
        "NO_CHANGE_KEEP_REASONS_TYPE_INVALID",
        "NO_CHANGE_KEEP_REASON_INVALID",
        "WARNING_PROPOSAL_INVALID",
        "NO_CHANGE_VALIDATOR_NOT_PASS",
        "NO_CHANGE_PAIRED_QUALITY_REQUEST_MISSING",
        "REWRITE_MASKED_TEXT_MISSING",
        "STRUCTURAL_PLAN_INVALID",
        "PROTECTED_PLACEHOLDER_RESTORE_FAILED",
        "STRUCTURAL_BASELINE_RESTORE_FAILED",
        "READ_ONLY_CONTEXT_COPIED",
        "REWRITE_INTENT_INVALID",
        "REWRITE_INTENT_SOURCE_SPANS_EMPTY",
        "NON_STRUCTURAL_SCOPE_VIOLATION",
        "PROTECTED_CONTENT_COUNT_CHANGED",
        "REWRITE_IDENTICAL_TO_SOURCE",
        "KEEP_REASONS_TYPE_INVALID",
        "KEEP_REASON_INVALID",
        "TEMPLATE_FIELD_EDIT_SCOPE_INVALID",
        "VALIDATOR_NOT_PASS",
        "PAIRED_QUALITY_REQUEST_MISSING",
        "STRUCTURAL_TRANSACTION_INCOMPLETE_DOCUMENT_COVERAGE",
        "CROSS_UNIT_REPETITION_INTRODUCED_TEMPLATE_FAMILY",
    }
)


def _rewrite_authoring_error_code(error: str) -> str | None:
    """Map safe, closed rewrite-intent diagnostics to actionable unit codes."""

    token = error.split(":", 1)[0]
    return {
        "rewrite_intent_operation_fields_invalid": (
            "REWRITE_INTENT_OPERATION_FIELDS_INVALID"
        ),
        "rewrite_intent_source_spans_fields_invalid": (
            "REWRITE_INTENT_SOURCE_SPANS_FIELDS_INVALID"
        ),
        "rewrite_intent_source_spans_sha256_mismatch": (
            "REWRITE_INTENT_SOURCE_SPANS_HASH_MISMATCH"
        ),
        "rewrite_intent_operation_source_spans_invalid": (
            "REWRITE_INTENT_OPERATION_SOURCE_SPANS_INVALID"
        ),
        "rewrite_intent_operation_target_signals_invalid": (
            "REWRITE_INTENT_OPERATION_TARGET_SIGNALS_INVALID"
        ),
        "rewrite_intent_source_span_coverage_incomplete": (
            "REWRITE_INTENT_SOURCE_SPAN_COVERAGE_INCOMPLETE"
        ),
        "rewrite_intent_target_signal_coverage_incomplete": (
            "REWRITE_INTENT_TARGET_SIGNAL_COVERAGE_INCOMPLETE"
        ),
        "rewrite_intent_source_spans_outside_diff": (
            "REWRITE_INTENT_SOURCE_SPANS_OUTSIDE_DIFF"
        ),
        "rewrite_intent_diff_outside_declared_spans": (
            "REWRITE_INTENT_DIFF_OUTSIDE_DECLARED_SPANS"
        ),
    }.get(token)


def _add_unresolved_code(unit: dict[str, Any], code: str) -> None:
    if code not in UNRESOLVED_CODE_VALUES:
        raise AssertionError("unknown internal unresolved code")
    codes = unit.setdefault("unresolved_codes", [])
    if not isinstance(codes, list):
        raise AssertionError("unit unresolved_codes must be a list")
    if code not in codes:
        codes.append(code)


def _unresolved_reason_summary(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    codes: Counter[str] = Counter()
    structured_codes: Counter[str] = Counter()
    total = 0
    structured_classified = 0
    legacy_classified = 0
    structured_sources: set[str] = set()
    legacy_aliases = {
        "NO_CHANGE_REASON_TOO_SHORT_HAN": "too_short_han",
        "NO_CHANGE_REASON_GENERIC_TEMPLATE": "generic_template",
        "NO_CHANGE_REASON_MISSING_FUNCTION_ANCHOR": "missing_function_anchor",
        "NO_CHANGE_EVIDENCE_SPANS_EMPTY": "no_change_evidence_spans_must_be_nonempty",
        "REWRITE_INTENT_SOURCE_SPANS_EMPTY": "rewrite_intent_source_spans_must_be_nonempty",
    }
    for unit in units:
        if str(unit.get("status", "")) != "UNRESOLVED":
            continue
        total += 1
        has_structured_codes = "unresolved_codes" in unit
        raw_codes = unit.get("unresolved_codes", [])
        valid_codes = sorted(
            {
                str(code)
                for code in raw_codes
                if isinstance(code, str) and code in UNRESOLVED_CODE_VALUES
            }
        ) if isinstance(raw_codes, list) else []
        if has_structured_codes:
            structured_sources.add("UNIT_UNRESOLVED_CODES")
        else:
            notes = str(unit.get("notes", ""))
            legacy_match = re.search(
                r"^(?:invalid_rewrite_bundle:|rewrite_intent:)?"
                r"NO_CHANGE_reason_invalid:"
                r"(too_short_han|generic_template|missing_function_anchor)"
                r"(?:;|$)",
                notes,
            )
            legacy_code_map = {
                "too_short_han": "NO_CHANGE_REASON_TOO_SHORT_HAN",
                "generic_template": "NO_CHANGE_REASON_GENERIC_TEMPLATE",
                "missing_function_anchor": (
                    "NO_CHANGE_REASON_MISSING_FUNCTION_ANCHOR"
                ),
            }
            if legacy_match:
                valid_codes = [legacy_code_map[legacy_match.group(1)]]
            else:
                empty_match = re.search(
                    r"^invalid_rewrite_bundle:"
                    r"(no_change_evidence_spans_must_be_nonempty|"
                    r"rewrite_intent_source_spans_must_be_nonempty)"
                    r"(?:\s|;|$)",
                    notes,
                )
                if empty_match:
                    valid_codes = [
                        (
                            "NO_CHANGE_EVIDENCE_SPANS_EMPTY"
                            if empty_match.group(1).startswith("no_change_")
                            else "REWRITE_INTENT_SOURCE_SPANS_EMPTY"
                        )
                    ]
            structured_sources.add("LEGACY_ANCHORED_NOTES")
        if valid_codes:
            structured_classified += 1
        unit_has_legacy_alias = False
        for code in valid_codes:
            structured_codes[code] += 1
            alias = legacy_aliases.get(code)
            if alias:
                codes[alias] += 1
                unit_has_legacy_alias = True
        if unit_has_legacy_alias:
            legacy_classified += 1
    action_by_code = {
        "REWRITE_BUNDLE_INVALID": (
            "FIX_REWRITE_BUNDLE_WITH_SCAFFOLD_REWRITE_INTENT_AUTHORING_CONTRACT"
        ),
        "REWRITE_INTENT_OPERATION_FIELDS_INVALID": (
            "USE_OPERATION_EXACT_FIELDS_ID_KIND_SOURCE_SPAN_IDS_TARGET_SIGNALS_SUMMARY"
        ),
        "REWRITE_INTENT_SOURCE_SPANS_FIELDS_INVALID": (
            "USE_SOURCE_SPAN_EXACT_FIELDS_ID_START_LINE_END_LINE_SHA256"
        ),
        "REWRITE_INTENT_SOURCE_SPANS_HASH_MISMATCH": (
            "RECOMPUTE_SHA256_FROM_NORMALIZED_LF_FROZEN_MASKED_SOURCE_LINES_WITH_LINE_ENDINGS"
        ),
        "REWRITE_INTENT_OPERATION_SOURCE_SPANS_INVALID": (
            "REFERENCE_NONEMPTY_UNIQUE_DECLARED_SOURCE_SPAN_IDS_FROM_EACH_OPERATION"
        ),
        "REWRITE_INTENT_OPERATION_TARGET_SIGNALS_INVALID": (
            "REFERENCE_NONEMPTY_UNIQUE_DECLARED_TARGET_SIGNALS_FROM_EACH_OPERATION"
        ),
        "REWRITE_INTENT_SOURCE_SPAN_COVERAGE_INCOMPLETE": (
            "REFERENCE_EVERY_DECLARED_SOURCE_SPAN_FROM_AT_LEAST_ONE_OPERATION"
        ),
        "REWRITE_INTENT_TARGET_SIGNAL_COVERAGE_INCOMPLETE": (
            "REFERENCE_EVERY_DECLARED_TARGET_SIGNAL_FROM_AT_LEAST_ONE_OPERATION"
        ),
        "REWRITE_INTENT_SOURCE_SPANS_OUTSIDE_DIFF": (
            "REMOVE_OR_MOVE_SOURCE_SPANS_SO_EACH_INTERSECTS_THE_MASKED_DIFF"
        ),
        "REWRITE_INTENT_DIFF_OUTSIDE_DECLARED_SPANS": (
            "ADD_HASH_BOUND_SOURCE_SPANS_COVERING_EVERY_CHANGED_SOURCE_LINE"
        ),
        "REWRITE_INTENT_AUTHORING_INCOMPLETE": (
            "EDIT_MASKED_TEXT_AND_POPULATE_SUMMARY_OPERATIONS_SOURCE_SPANS_TARGET_SIGNALS"
        ),
        "REWRITE_INTENT_SOURCE_SPANS_EMPTY": (
            "ADD_HASH_BOUND_SOURCE_SPANS_FOR_EVERY_CHANGED_SOURCE_LINE"
        ),
        "NO_CHANGE_AUTHORING_INCOMPLETE": (
            "REPLACE_TODO_REASON_AND_ADD_HASH_BOUND_EVIDENCE_SPAN"
        ),
        "NO_CHANGE_EVIDENCE_SPANS_EMPTY": "ADD_HASH_BOUND_EVIDENCE_SPAN",
        "REWRITE_INTENT_INVALID": (
            "FIX_BOUND_REWRITE_INTENT_USING_FINALIZER_ERROR_AND_SCAFFOLD_CONTRACT"
        ),
    }
    actionable_next_actions = [
        {"reason_code": code, "action": action_by_code[code]}
        for code in sorted(structured_codes)
        if code in action_by_code
    ]
    return {
        "total": total,
        "classified": legacy_classified,
        "unclassified": total - legacy_classified,
        "codes": dict(sorted(codes.items())),
        "structured_code_schema": UNRESOLVED_CODE_SCHEMA,
        "structured_code_source": (
            next(iter(structured_sources))
            if len(structured_sources) == 1
            else "MIXED"
            if structured_sources
            else "NONE"
        ),
        "structured_classified": structured_classified,
        "structured_unclassified": total - structured_classified,
        "structured_code_counts": dict(sorted(structured_codes.items())),
        "actionable_next_actions": actionable_next_actions,
        "details_artifact": "coverage_ledger.final.csv" if total else "",
        "content_redacted": True,
    }


def _validate_intent_span_bindings(
    spans: Sequence[dict[str, Any]],
    masked_before: str,
    field: str,
) -> None:
    lines = masked_before.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )
    if not lines:
        lines = [""]
    for item in spans:
        start_line = int(item["start_line"])
        end_line = int(item["end_line"])
        if end_line > len(lines):
            raise ValueError(f"{field}_line_range_out_of_bounds:{item['id']}")
        block = "".join(lines[start_line - 1 : end_line])
        if sha256(block.encode("utf-8")) != item["sha256"]:
            raise ValueError(f"{field}_sha256_mismatch:{item['id']}")


def _validate_bound_rewrite_intent(
    bundle: dict[str, Any],
    decision: str,
    masked_before: str,
    schema_status: str,
) -> None:
    if schema_status != "PASS":
        return
    if decision == "REWRITE":
        intent = bundle["rewrite_intent"]
        if not _specific_intent_summary(str(intent["summary"])):
            raise ValueError("rewrite_intent_summary_generic")
        for operation in intent["operations"]:
            if not _specific_intent_summary(str(operation["summary"])):
                raise ValueError("rewrite_intent_operation_summary_generic")
        _validate_intent_span_bindings(
            intent["source_spans"], masked_before, "rewrite_intent_source_spans"
        )
        return
    reason_error = _no_change_reason_error(str(bundle.get("reason", "")))
    if reason_error:
        raise ValueError(reason_error)
    _validate_intent_span_bindings(
        bundle["evidence_spans"], masked_before, "no_change_evidence_spans"
    )


def _rewrite_intent_diff_binding(
    bundle: dict[str, Any],
    masked_before: str,
    masked_after: str,
    schema_status: str,
) -> dict[str, Any]:
    if schema_status != "PASS":
        return {
            "status": "REVIEW",
            "reason": "LEGACY_BUNDLE_WITHOUT_INTENT_SCHEMA",
            "changed_source_ranges": [],
        }
    intent = bundle["rewrite_intent"]
    before_lines = masked_before.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )
    after_lines = masked_after.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )
    matcher = difflib.SequenceMatcher(
        a=before_lines, b=after_lines, autojunk=False
    )
    changed_ranges: list[dict[str, int | str]] = []
    for tag, before_start, before_end, _after_start, _after_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if before_end > before_start:
            start_line = before_start + 1
            end_line = before_end
        else:
            start_line = max(1, before_start)
            end_line = start_line
        changed_ranges.append(
            {"operation": tag.upper(), "start_line": start_line, "end_line": end_line}
        )
    uncovered: list[str] = []
    covered_lines: set[int] = set()
    for span in intent["source_spans"]:
        covered_lines.update(
            range(int(span["start_line"]), int(span["end_line"]) + 1)
        )
        if not any(
            int(span["start_line"]) <= int(change["end_line"])
            and int(change["start_line"]) <= int(span["end_line"])
            for change in changed_ranges
        ):
            uncovered.append(str(span["id"]))
    if uncovered:
        raise ValueError(
            "rewrite_intent_source_spans_outside_diff:" + ",".join(uncovered)
        )
    uncovered_changed_lines = sorted(
        {
            line
            for change in changed_ranges
            for line in range(
                int(change["start_line"]), int(change["end_line"]) + 1
            )
            if line not in covered_lines
        }
    )
    if uncovered_changed_lines:
        raise ValueError(
            "rewrite_intent_diff_outside_declared_spans:"
            + ",".join(str(item) for item in uncovered_changed_lines)
        )
    return {
        "status": "PASS",
        "source_spans_total": len(intent["source_spans"]),
        "source_spans_covered": len(intent["source_spans"]),
        "changed_source_ranges": changed_ranges,
        "masked_before_sha256": sha256(masked_before.encode("utf-8")),
        "masked_after_sha256": sha256(masked_after.encode("utf-8")),
    }


def _validate_transaction_fragment_local_intent(
    fragment: dict[str, Any],
    baseline_masked: str,
    candidate_masked: str,
    transaction_schema_status: str,
) -> dict[str, Any]:
    local = fragment.get("local_rewrite_intent")
    if not isinstance(local, dict):
        return {
            "status": "REVIEW",
            "decision": "NOT_DECLARED",
            "reason_code": "LEGACY_TRANSACTION_BUNDLE_WITHOUT_FRAGMENT_INTENT",
            "intent_diff_binding": {
                "status": "REVIEW",
                "reason": "LEGACY_TRANSACTION_BUNDLE_WITHOUT_FRAGMENT_INTENT",
                "changed_source_ranges": [],
            },
        }
    current_contract = transaction_schema_status == "PASS"
    decision = str(local["decision"])
    if decision == "REWRITE":
        pseudo_bundle = {"rewrite_intent": local["rewrite_intent"]}
        _validate_bound_rewrite_intent(
            pseudo_bundle,
            "REWRITE",
            baseline_masked,
            "PASS",
        )
        diff_binding = _rewrite_intent_diff_binding(
            pseudo_bundle,
            baseline_masked,
            candidate_masked,
            "PASS",
        )
        return {
            "status": "PASS" if current_contract else "REVIEW",
            "decision": decision,
            "reason_code": (
                "BOUND_TRANSACTION_FRAGMENT_REWRITE_INTENT"
                if current_contract
                else "LEGACY_TRANSACTION_FRAGMENT_REWRITE_INTENT_VALIDATED"
            ),
            "intent_diff_binding": diff_binding,
        }
    pseudo_bundle = {
        "reason": local["reason"],
        "evidence_spans": local["evidence_spans"],
    }
    _validate_bound_rewrite_intent(
        pseudo_bundle,
        "NO_CHANGE",
        baseline_masked,
        "PASS",
    )
    if candidate_masked != baseline_masked:
        raise ValueError("transaction_fragment_NO_CHANGE_has_local_diff")
    return {
        "status": "PASS" if current_contract else "REVIEW",
        "decision": decision,
        "reason_code": (
            "BOUND_TRANSACTION_FRAGMENT_LOCAL_NO_CHANGE"
            if current_contract
            else "LEGACY_TRANSACTION_FRAGMENT_LOCAL_NO_CHANGE_VALIDATED"
        ),
        "intent_diff_binding": {
            "status": "NOT_APPLICABLE",
            "reason": "NO_CHANGE_AGAINST_STRUCTURAL_BASELINE",
            "changed_source_ranges": [],
            "masked_before_sha256": sha256(baseline_masked.encode("utf-8")),
            "masked_after_sha256": sha256(candidate_masked.encode("utf-8")),
        },
    }


def _specific_decline_reason(reason: str) -> bool:
    han = "".join(re.findall(r"[\u3400-\u9fff]", reason))
    if len(han) < 8:
        return False
    generic = {
        "候选已经审阅无需调整",
        "已经审阅无需结构调整",
        "当前无需进行结构调整",
        "现有结构已经比较合理",
        "保持不变即可无需调整",
        "这个候选不需要执行",
        "没有必要进行结构调整",
        "暂时不需要进行结构调整",
    }
    if han in generic:
        return False
    return bool(
        re.search(
            r"段落|职责|对象|依赖|指代|题干|题解|证据|主张|结论|顺序|对应|"
            r"保护|公式|引语|标题|用户|锁定|收益|范围|边界|条件|因果|模态|成员",
            reason,
        )
    )


def _rewrite_bundle_sha256(bundle: dict[str, Any]) -> str:
    public = {key: value for key, value in bundle.items() if key != "bundle_path"}
    return sha256(_canonical_json(public).encode("utf-8"))


def _persist_rewrite_intent_evidence(
    *,
    validation_dir: Path,
    unit_id: str,
    decision: str,
    bundle: dict[str, Any],
    schema_status: str,
    before_sha256: str,
    after_sha256: str,
    diff_path: str,
    diff_sha256: str,
    paired_quality_request_sha256: str,
    diff_binding: dict[str, Any],
) -> dict[str, Any]:
    intent_payload: Any
    if decision == "REWRITE":
        intent_payload = bundle.get("rewrite_intent")
    else:
        intent_payload = {
            "reason": bundle.get("reason"),
            "evidence_spans": bundle.get("evidence_spans"),
        }
    body = {
        "schema_version": REWRITE_INTENT_EVIDENCE_SCHEMA,
        "status": schema_status,
        "reason_code": (
            "BOUND_INTENT_PRESENT"
            if schema_status == "PASS"
            else "LEGACY_BUNDLE_WITHOUT_INTENT_SCHEMA"
        ),
        "unit_id": unit_id,
        "decision": decision,
        "bundle_schema_version": bundle.get("schema_version"),
        "bundle_sha256": _rewrite_bundle_sha256(bundle),
        "chunk_binding_sha256": str(bundle.get("chunk_binding_sha256", "")),
        "artifact": {
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
        },
        "diff": {
            "path": diff_path,
            "sha256": diff_sha256,
        },
        "paired_quality_review_request_sha256": paired_quality_request_sha256,
        "intent_diff_binding": diff_binding,
        "intent": intent_payload,
        "limitations": {
            "intent_truthfulness_verified": False,
            "independent_reading_benefit_verified": False,
            "academic_correctness": "NOT_EVALUATED",
        },
    }
    payload = {
        **body,
        "evidence_sha256": sha256(_canonical_json(body).encode("utf-8")),
    }
    name = f"{unit_id}.rewrite-intent.json"
    _write_json(validation_dir / name, payload)
    return {
        "status": schema_status,
        "path": str(Path("validation") / name).replace("\\", "/"),
        "evidence_sha256": payload["evidence_sha256"],
        "bundle_sha256": payload["bundle_sha256"],
        "paired_quality_review_request_sha256": paired_quality_request_sha256,
    }


def _persist_transaction_fragment_rewrite_intent_evidence(
    *,
    validation_dir: Path,
    unit_id: str,
    bundle: dict[str, Any],
    fragment: dict[str, Any],
    fragment_result: dict[str, Any],
    diff_path: str,
    diff_sha256: str,
    paired_quality_review_request_sha256: str,
    structural_transaction_review_request_sha256: str,
) -> dict[str, Any]:
    status = str(fragment_result["rewrite_intent_status"])
    decision = str(fragment_result["rewrite_intent_decision"])
    local_intent = fragment.get("local_rewrite_intent")
    body = {
        "schema_version": TRANSACTION_FRAGMENT_REWRITE_INTENT_EVIDENCE_SCHEMA,
        "status": status,
        "reason_code": str(fragment_result["rewrite_intent_reason_code"]),
        "unit_id": unit_id,
        "decision": decision,
        "bundle_schema_version": bundle.get("schema_version"),
        "bundle_sha256": _structural_transaction_bundle_sha256(bundle),
        "fragment_sha256": sha256(
            _canonical_json(fragment).encode("utf-8")
        ),
        "transaction": {
            "transaction_id": str(bundle["transaction_id"]),
            "transaction_binding_sha256": str(
                bundle["transaction_binding_sha256"]
            ),
            "transaction_inventory_sha256": str(
                bundle["transaction_inventory_sha256"]
            ),
        },
        "chunk_binding_sha256": str(fragment_result["chunk_binding_sha256"]),
        "voice_profile_sha256": str(fragment_result["voice_profile_sha256"]),
        "artifact": {
            "source_member_before_sha256": sha256(
                str(fragment_result["original"]).encode("utf-8")
            ),
            "structural_baseline_masked_sha256": sha256(
                str(fragment_result["baseline_masked"]).encode("utf-8")
            ),
            "structural_baseline_before_sha256": sha256(
                str(fragment_result["invariant_before"]).encode("utf-8")
            ),
            "candidate_masked_sha256": sha256(
                str(fragment["masked_text"]).encode("utf-8")
            ),
            "candidate_after_sha256": sha256(
                str(fragment_result["restored"]).encode("utf-8")
            ),
        },
        "diff": {"path": diff_path, "sha256": diff_sha256},
        "paired_quality_review_request_sha256": (
            paired_quality_review_request_sha256
        ),
        "structural_transaction_review_request_sha256": (
            structural_transaction_review_request_sha256
        ),
        "intent_diff_binding": fragment_result["rewrite_intent_diff_binding"],
        "intent": local_intent,
        "limitations": {
            "intent_truthfulness_verified": False,
            "structural_semantic_mapping": "NOT_EVALUATED",
            "independent_reading_benefit_verified": False,
            "academic_correctness": "NOT_EVALUATED",
        },
    }
    payload = {
        **body,
        "evidence_sha256": sha256(_canonical_json(body).encode("utf-8")),
    }
    name = f"{unit_id}.rewrite-intent.json"
    _write_json(validation_dir / name, payload)
    return {
        "status": status,
        "path": str(Path("validation") / name).replace("\\", "/"),
        "evidence_sha256": payload["evidence_sha256"],
        "bundle_sha256": payload["bundle_sha256"],
        "paired_quality_review_request_sha256": (
            paired_quality_review_request_sha256
        ),
        "structural_transaction_review_request_sha256": (
            structural_transaction_review_request_sha256
        ),
    }


def _discard_rewrite_intent_evidence(
    records: dict[str, dict[str, Any]],
    validation_dir: Path,
    unit_id: str,
) -> None:
    record = records.pop(unit_id, None)
    name = f"{unit_id}.rewrite-intent.json"
    if isinstance(record, dict):
        path = validation_dir / Path(str(record.get("path", name))).name
    else:
        path = validation_dir / name
    if path.is_file():
        path.unlink()


def _normalize_context(text: str) -> str:
    without_placeholders = PLACEHOLDER_RE.sub("", text)
    return re.sub(r"\s+", "", without_placeholders)


def _logical_document_ids(
    file_manifest: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Resolve every manifest row to one include-root without guessing."""
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in file_manifest:
        file_id = str(record.get("file_id", "")).strip()
        if not file_id:
            raise ValueError("file manifest contains an empty file_id")
        if file_id in by_id:
            raise ValueError(f"file manifest contains duplicate file_id: {file_id}")
        by_id[file_id] = record

    resolved: dict[str, str] = {}
    for file_id in sorted(by_id):
        chain: list[str] = []
        positions: dict[str, int] = {}
        current = file_id
        while current not in resolved:
            if current in positions:
                cycle = chain[positions[current] :] + [current]
                raise ValueError(
                    "file manifest parent cycle: " + " -> ".join(cycle)
                )
            positions[current] = len(chain)
            chain.append(current)
            parent = str(by_id[current].get("parent_file_id", "")).strip()
            if not parent:
                root = current
                break
            if parent not in by_id:
                raise ValueError(
                    f"file manifest parent is missing: {current} -> {parent}"
                )
            current = parent
        else:
            root = resolved[current]
        for member in chain:
            resolved[member] = root
    return resolved


def _classify_tex_list_structure(content: str) -> dict[str, str] | None:
    """Project only list structure; never expose a protected TeX payload."""
    return repetition_guards.classify_tex_list_structure_content(content)


def _protected_structure_tokens(
    masked_text: str,
    *,
    file_id: str,
    document_format: str,
    span_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, str]]:
    """Build a validated, payload-free side channel for masked TeX lists."""
    output: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for match in PLACEHOLDER_RE.finditer(masked_text):
        protected_id = match.group("id")
        if protected_id in seen:
            raise ValueError(
                f"duplicate protected placeholder in style record: {protected_id}"
            )
        seen.add(protected_id)
        span = span_map.get(protected_id)
        if not isinstance(span, Mapping):
            raise ValueError(f"unknown protected placeholder: {protected_id}")
        if str(span.get("file_id", "")) != file_id:
            raise ValueError(
                f"protected placeholder file mismatch: {protected_id}"
            )
        declared_sha256 = str(span.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", declared_sha256):
            raise ValueError(f"invalid protected span hash: {protected_id}")
        if match.group("hash") != declared_sha256[:12]:
            raise ValueError(f"protected placeholder hash mismatch: {protected_id}")
        if document_format != "tex":
            continue
        token = _classify_tex_list_structure(str(span.get("content", "")))
        if token is not None:
            output[protected_id] = token
    return output


def _style_blocks(
    masked_text: str,
    unit_id: str,
    resolved_scene: str,
    document_id: str,
) -> list[dict[str, Any]]:
    """Return author-facing paragraph blocks without protected payload bytes."""
    text = masked_text.replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[dict[str, Any]] = []
    paragraph_index = 0
    for visible_segment in PLACEHOLDER_RE.split(text):
        for raw_block in re.split(r"\n[ \t]*\n+", visible_segment):
            paragraph_index += 1
            lines = [
                line
                for line in raw_block.splitlines()
                if not PURE_TEX_STRUCTURE_LINE_RE.match(line)
            ]
            block = "\n".join(lines).strip()
            han = "".join(HAN_RE.findall(block))
            if len(han) < 4:
                continue
            blocks.append(
                {
                    "unit_id": unit_id,
                    "document_id": document_id,
                    "resolved_scene": str(resolved_scene).upper(),
                    "paragraph_index": paragraph_index,
                    "text": block,
                    "han": han,
                }
            )
    return blocks


def _feature_support(blocks: Sequence[dict[str, Any]], code: str) -> int:
    extractor = voice_profiles.FEATURE_EXTRACTORS.get(code)
    if extractor is None:
        raise ValueError(f"unsupported Voice feature code: {code}")
    pattern = extractor["pattern"]
    return sum(1 for block in blocks if pattern.search(str(block["text"])))


def _ratio_ppm(numerator: int, denominator: int) -> int:
    return numerator * 1_000_000 // denominator if denominator else 0


def _opening_groups(
    blocks: Sequence[dict[str, Any]],
    *,
    width: int,
    require_template_cue: bool,
) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for block in blocks:
        han = str(block["han"])
        if len(han) < width:
            continue
        key = han[:width]
        if require_template_cue and not BOUNDARY_TEMPLATE_CUE_RE.match(key):
            continue
        groups[key].add(str(block["unit_id"]))
    return groups


def _voice_negative_result(
    control: dict[str, Any],
    before_blocks: Sequence[dict[str, Any]],
    after_blocks: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    code = str(control.get("value", {}).get("code", ""))
    result: dict[str, Any] = {
        "feature_key": str(control.get("feature_key", "")),
        "code": code,
        "status": "PASS",
        "before_occurrences": 0,
        "after_occurrences": 0,
        "before_units": 0,
        "after_units": 0,
        "amplified_keys": [],
    }
    if code == "KNOWN_AI_TEMPLATE_SHELL":
        before_hits = [
            block for block in before_blocks if voice_profiles.AI_SHELL_RE.search(str(block["text"]))
        ]
        after_hits = [
            block for block in after_blocks if voice_profiles.AI_SHELL_RE.search(str(block["text"]))
        ]
        result.update(
            {
                "before_occurrences": sum(
                    len(voice_profiles.AI_SHELL_RE.findall(str(block["text"]))) for block in before_blocks
                ),
                "after_occurrences": sum(
                    len(voice_profiles.AI_SHELL_RE.findall(str(block["text"]))) for block in after_blocks
                ),
                "before_units": len({str(block["unit_id"]) for block in before_hits}),
                "after_units": len({str(block["unit_id"]) for block in after_hits}),
            }
        )
        if (
            result["after_occurrences"] > result["before_occurrences"]
            or result["after_units"] > result["before_units"]
        ):
            result["status"] = "REVIEW"
        return result
    if code == "REPEATED_PARAGRAPH_OPENING":
        before_groups = _opening_groups(
            before_blocks, width=4, require_template_cue=False
        )
        after_groups = _opening_groups(
            after_blocks, width=4, require_template_cue=False
        )
        amplified = [
            {
                "opening": key,
                "before_units": len(before_groups.get(key, set())),
                "after_units": len(unit_ids),
                "unit_ids": sorted(unit_ids),
            }
            for key, unit_ids in sorted(after_groups.items())
            if len(unit_ids) >= 3 and len(unit_ids) > len(before_groups.get(key, set()))
        ]
        result.update(
            {
                "before_occurrences": sum(len(value) for value in before_groups.values()),
                "after_occurrences": sum(len(value) for value in after_groups.values()),
                "before_units": len({unit for values in before_groups.values() for unit in values}),
                "after_units": len({unit for values in after_groups.values() for unit in values}),
                "amplified_keys": amplified[:20],
            }
        )
        if amplified:
            result["status"] = "REVIEW"
        return result
    result["status"] = "REVIEW"
    result["reason"] = "UNSUPPORTED_NEGATIVE_CONTROL"
    return result


def _audit_voice_conformance(
    profile: dict[str, Any],
    records: Sequence[dict[str, Any]],
    *,
    scene_routing_status: str,
) -> dict[str, Any]:
    evaluated = [
        record
        for record in records
        if record.get("state") in {"DONE", "NO_CHANGE"}
        and isinstance(record.get("after_masked"), str)
    ]
    expected = [record for record in records if record.get("expected")]
    before_blocks = [
        block
        for record in evaluated
        for block in _style_blocks(
            str(record["before_masked"]),
            str(record["unit_id"]),
            str(record["resolved_scene"]),
            str(record["document_id"]),
        )
    ]
    after_blocks = [
        block
        for record in evaluated
        for block in _style_blocks(
            str(record["after_masked"]),
            str(record["unit_id"]),
            str(record["resolved_scene"]),
            str(record["document_id"]),
        )
    ]
    reasons: list[str] = []
    if len(evaluated) != len(expected):
        reasons.append("INCOMPLETE_EDITABLE_UNITS")
    if scene_routing_status != "PASS":
        reasons.append("SCENE_ROUTING_NOT_PASS")
    if any(str(record.get("style_validation")) != "PASS" for record in evaluated):
        reasons.append("UNIT_STYLE_VALIDATION_NOT_PASS")

    profile_kind = str(profile.get("profile_kind", ""))
    feature_results: list[dict[str, Any]] = []
    negative_results: list[dict[str, Any]] = []
    if profile_kind == "DEFAULT":
        status = "PASS" if not reasons else "REVIEW"
        return {
            "schema_version": "humanize-document-voice-conformance/v1",
            "status": status,
            "basis": "SCENE_DEFAULT_UNIT_VALIDATION",
            "profile_kind": profile_kind,
            "profile_sha256": profile.get("profile_sha256"),
            "feature_extractor_policy_sha256": voice_profiles.FEATURE_EXTRACTOR_POLICY_SHA256,
            "identity_verified": False,
            "personal_voice_claim_allowed": False,
            "personal_voice_conformance_status": "NOT_APPLICABLE",
            "expected_units": len(expected),
            "evaluated_units": len(evaluated),
            "before_blocks": len(before_blocks),
            "after_blocks": len(after_blocks),
            "feature_results": feature_results,
            "negative_results": negative_results,
            "review_reasons": sorted(set(reasons)),
            "limitations": [
                "PASS confirms deterministic scene-default binding and unit validator coverage only.",
                "It does not reproduce or verify a personal author identity.",
            ],
        }

    if profile_kind != "PERSONAL":
        reasons.append("UNSUPPORTED_PROFILE_KIND")
    if len(after_blocks) < 6:
        reasons.append("INSUFFICIENT_TARGET_BLOCKS")

    for feature in profile.get("features", []):
        code = str(feature.get("value", {}).get("code", ""))
        scope = {str(item).upper() for item in feature.get("scope", [])}
        scoped_before = [
            block
            for block in before_blocks
            if "GLOBAL" in scope or str(block["resolved_scene"]).upper() in scope
        ]
        scoped_after = [
            block
            for block in after_blocks
            if "GLOBAL" in scope or str(block["resolved_scene"]).upper() in scope
        ]
        result: dict[str, Any] = {
            "feature_key": str(feature.get("feature_key", "")),
            "code": code,
            "disposition": str(feature.get("disposition", "")),
            "status": "PASS",
            "profile_ratio_ppm": int(feature.get("evidence", {}).get("support_ratio_ppm", 0)),
            "before_opportunities": len(scoped_before),
            "after_opportunities": len(scoped_after),
        }
        extractor = voice_profiles.FEATURE_EXTRACTORS.get(code)
        if extractor is None:
            current_extractor_sha256 = ""
        else:
            current_extractor_sha256 = voice_profiles._stable_hash(
                {
                    "rule_id": extractor["rule_id"],
                    "pattern": extractor["pattern"].pattern,
                    "flags": extractor["pattern"].flags,
                    "code": code,
                }
            )
        declared_extractor_sha256 = str(
            feature.get("evidence", {}).get("extractor_sha256", "")
        )
        result["declared_extractor_sha256"] = declared_extractor_sha256
        result["current_extractor_sha256"] = current_extractor_sha256
        if declared_extractor_sha256 != current_extractor_sha256:
            result.update(
                {
                    "before_support": 0,
                    "after_support": 0,
                    "before_ratio_ppm": 0,
                    "after_ratio_ppm": 0,
                    "status": "REVIEW",
                    "reason": "FEATURE_EXTRACTOR_BINDING_MISMATCH",
                }
            )
            feature_results.append(result)
            reasons.append("FEATURE_EXTRACTOR_BINDING_MISMATCH")
            continue
        try:
            before_support = _feature_support(scoped_before, code)
            after_support = _feature_support(scoped_after, code)
        except ValueError:
            result.update(
                {
                    "before_support": 0,
                    "after_support": 0,
                    "before_ratio_ppm": 0,
                    "after_ratio_ppm": 0,
                    "status": "REVIEW",
                    "reason": "UNSUPPORTED_FEATURE_CODE",
                }
            )
            feature_results.append(result)
            reasons.append("UNSUPPORTED_FEATURE_CODE")
            continue
        before_ratio = _ratio_ppm(before_support, len(scoped_before))
        after_ratio = _ratio_ppm(after_support, len(scoped_after))
        tolerance = max(
            250_000,
            _ratio_ppm(1, max(len(scoped_before), len(scoped_after), 1)),
        )
        support_drop = before_support - after_support
        ratio_drop = before_ratio - after_ratio
        material_regression = (
            len(scoped_after) >= 6
            and support_drop >= 2
            and ratio_drop >= 250_000
            and after_ratio < result["profile_ratio_ppm"]
        )
        severe_absolute_gap = (
            code in {"EXPLICIT_TERMINAL_PUNCTUATION", "NON_LIST_PROSE"}
            and
            len(scoped_after) >= 12
            and result["profile_ratio_ppm"] - after_ratio >= 600_000
        )
        structural_floor = max(300_000, result["profile_ratio_ppm"] - 400_000)
        structural_regression = (
            code in {"EXPLICIT_TERMINAL_PUNCTUATION", "NON_LIST_PROSE"}
            and len(scoped_after) >= 8
            and after_ratio < structural_floor
            and after_ratio < before_ratio
        )
        result.update(
            {
                "before_support": before_support,
                "after_support": after_support,
                "before_ratio_ppm": before_ratio,
                "after_ratio_ppm": after_ratio,
                "tolerance_ppm": tolerance,
                "support_drop": support_drop,
                "ratio_drop_ppm": ratio_drop,
                "material_regression": material_regression,
                "severe_absolute_gap": severe_absolute_gap,
                "structural_floor_ppm": structural_floor,
                "structural_regression": structural_regression,
            }
        )
        if len(scoped_after) < 6:
            result["status"] = "REVIEW"
            result["reason"] = "INSUFFICIENT_SCOPED_TARGET_BLOCKS"
            reasons.append("INSUFFICIENT_SCOPED_TARGET_BLOCKS")
        elif material_regression or severe_absolute_gap or structural_regression:
            result["status"] = "REVIEW"
            result["reason"] = (
                "MATERIAL_PREFERRED_FEATURE_REGRESSION"
                if material_regression
                else "SEVERE_PROFILE_FEATURE_GAP"
                if severe_absolute_gap
                else "STRUCTURAL_VOICE_FEATURE_REGRESSION"
            )
            reasons.append("MATERIAL_PREFERRED_FEATURE_REGRESSION")
        feature_results.append(result)

    for control in profile.get("negative_controls", []):
        result = _voice_negative_result(control, before_blocks, after_blocks)
        negative_results.append(result)
        if result["status"] != "PASS":
            reasons.append("VOICE_NEGATIVE_CONTROL_AMPLIFIED")

    status = "PASS" if not reasons else "REVIEW"
    return {
        "schema_version": "humanize-document-voice-conformance/v1",
        "status": status,
        "basis": "PERSONAL_PROFILE_NON_REGRESSION",
        "profile_kind": profile_kind,
        "profile_sha256": profile.get("profile_sha256"),
        "identity_verified": False,
        "personal_voice_claim_allowed": bool(
            profile.get("defaults", {}).get("personal_voice_claim_allowed", False)
        ),
        "personal_voice_conformance_status": status,
        "expected_units": len(expected),
        "evaluated_units": len(evaluated),
        "before_blocks": len(before_blocks),
        "after_blocks": len(after_blocks),
        "feature_results": feature_results,
        "negative_results": negative_results,
        "feature_extractor_policy_sha256": voice_profiles.FEATURE_EXTRACTOR_POLICY_SHA256,
        "review_reasons": sorted(set(reasons)),
        "limitations": [
            "Feature ratios are conservative non-regression checks, not authorship proof.",
            "Unencoded semantic voice choices remain outside deterministic evaluation.",
        ],
    }


def _audit_voice_conformance_set(
    profiles: dict[str, dict[str, Any]],
    records: Sequence[dict[str, Any]],
    *,
    scene_routing_status: str,
) -> dict[str, Any]:
    if len(profiles) == 1:
        return _audit_voice_conformance(
            next(iter(profiles.values())),
            records,
            scene_routing_status=scene_routing_status,
        )
    per_scene: dict[str, dict[str, Any]] = {}
    for scene, profile in sorted(profiles.items()):
        scene_records = [
            record
            for record in records
            if str(record.get("resolved_scene", "")).upper() == scene
        ]
        if not scene_records:
            continue
        per_scene[scene] = _audit_voice_conformance(
            profile,
            scene_records,
            scene_routing_status=scene_routing_status,
        )
    status = (
        "PASS"
        if per_scene
        and scene_routing_status == "PASS"
        and all(result.get("status") == "PASS" for result in per_scene.values())
        else "REVIEW"
    )
    return {
        "schema_version": "humanize-document-voice-conformance-set/v1",
        "status": status,
        "basis": "SCENE_DEFAULT_PROFILE_SET_UNIT_VALIDATION",
        "profile_kind": "DEFAULT_SET",
        "identity_verified": False,
        "personal_voice_claim_allowed": False,
        "personal_voice_conformance_status": "NOT_APPLICABLE",
        "expected_units": sum(
            int(result.get("expected_units", 0)) for result in per_scene.values()
        ),
        "evaluated_units": sum(
            int(result.get("evaluated_units", 0)) for result in per_scene.values()
        ),
        "per_scene": per_scene,
        "review_reasons": (
            []
            if status == "PASS"
            else ["SCENE_PROFILE_SET_CONFORMANCE_NOT_PASS"]
        ),
        "limitations": [
            "PASS confirms per-unit deterministic scene-default binding and validator coverage only.",
            "It does not reproduce or verify a personal author identity.",
        ],
    }


def _template_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = ZERO_WIDTH_RE.sub("", normalized)
    return HAN_GAP_RE.sub("", normalized)


def _signal_occurrences(
    signal: dict[str, Any], blocks: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    occurrences: list[dict[str, Any]] = []
    for block in blocks:
        match_text = _template_match_text(str(block["text"]))
        raw_matches: list[re.Match[str]] = []
        for pattern in output_validator.lexical._signal_patterns(signal):
            raw_matches.extend(pattern.finditer(match_text))
        for start, end, matched in output_validator.lexical._deduplicate_matches(raw_matches):
            if output_validator.lexical._exclusion_reason(
                match_text, start, end, signal
            ):
                continue
            occurrences.append(
                {
                    "unit_id": str(block["unit_id"]),
                    "paragraph_index": int(block["paragraph_index"]),
                    "matched": matched,
                }
            )
    return occurrences


def _guard_group_occurrences(
    group: dict[str, Any], blocks: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    pattern = re.compile(str(group["regex"]))
    occurrences: list[dict[str, Any]] = []
    for block in blocks:
        match_text = _template_match_text(str(block["text"]))
        for match in pattern.finditer(match_text):
            occurrences.append(
                {
                    "unit_id": str(block["unit_id"]),
                    "paragraph_index": int(block["paragraph_index"]),
                    "matched": match.group(0),
                    "matched_sha256": sha256(match.group(0).encode("utf-8")),
                }
            )
    return occurrences


def _audit_cross_unit_repetition(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [
        record
        for record in records
        if record.get("state") in {"DONE", "NO_CHANGE"}
        and isinstance(record.get("after_masked"), str)
    ]
    expected = [record for record in records if record.get("expected")]
    findings: list[dict[str, Any]] = []
    inherited_findings: list[dict[str, Any]] = []
    blocking_unit_ids: set[str] = set()
    guard_review_reasons: list[str] = []
    negative_guard_registry: dict[str, Any] | None = None
    negative_guard_registry_sha256 = ""
    negative_guard_registry_source_sha256 = ""
    negative_guard_registry_source_format = "NOT_AVAILABLE"
    active_detector_definition_sha256: list[str] = []
    all_grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    try:
        all_grouped = repetition_guards.group_records_by_partition(records)
        grouped = repetition_guards.group_records_by_partition(evaluated)
    except repetition_guards.DetectorEvaluationReview as error:
        guard_review_reasons.append(
            f"CROSS_UNIT_PARTITION_METADATA_REVIEW:{error}"
        )

    def partition_blocks(
        partition_records: Sequence[dict[str, Any]], field: str
    ) -> list[dict[str, Any]]:
        return [
            block
            for record in partition_records
            for block in _style_blocks(
                str(record[field]),
                str(record["unit_id"]),
                str(record["resolved_scene"]),
                str(record["document_id"]),
            )
        ]

    before_blocks: list[dict[str, Any]] = []
    after_blocks: list[dict[str, Any]] = []
    lexicon = output_validator.lexical.load_lexicon()
    for (document_id, scene), partition_records in sorted(grouped.items()):
        partition_before = partition_blocks(partition_records, "before_masked")
        partition_after = partition_blocks(partition_records, "after_masked")
        before_blocks.extend(partition_before)
        after_blocks.extend(partition_after)
        for signal in lexicon["signals"]:
            if signal.get("category") != "repair-template-repetition":
                continue
            before_hits = _signal_occurrences(signal, partition_before)
            after_hits = _signal_occurrences(signal, partition_after)
            before_by_unit = Counter(item["unit_id"] for item in before_hits)
            after_by_unit = Counter(item["unit_id"] for item in after_hits)
            after_units = sorted({item["unit_id"] for item in after_hits})
            introduced_units = sorted(
                unit_id
                for unit_id, count in after_by_unit.items()
                if count > before_by_unit.get(unit_id, 0)
            )
            minimum = int(signal.get("threshold", {}).get("min_occurrences", 1))
            common = {
                "kind": "REPAIR_SIGNAL_FAMILY",
                "signal_id": str(signal.get("id", "")),
                "document_id": document_id,
                "evaluated_scene": scene,
                "before_occurrences": len(before_hits),
                "after_occurrences": len(after_hits),
            }
            if (
                len(after_hits) >= minimum
                and len(after_units) >= 2
                and introduced_units
            ):
                blocking_unit_ids.update(introduced_units)
                findings.append(
                    {
                        **common,
                        "before_units": sorted(
                            {item["unit_id"] for item in before_hits}
                        ),
                        "after_units": after_units,
                        "introduced_unit_ids": introduced_units,
                        "matches": [item["matched"] for item in after_hits[:20]],
                    }
                )
            elif len(after_hits) >= minimum and len(after_units) >= 2:
                inherited_findings.append({**common, "units": after_units})

        before_openings = _opening_groups(
            partition_before, width=6, require_template_cue=True
        )
        after_openings = _opening_groups(
            partition_after, width=6, require_template_cue=True
        )
        for opening, unit_ids in sorted(after_openings.items()):
            before_units = before_openings.get(opening, set())
            common = {
                "kind": "REPEATED_TEMPLATE_OPENING",
                "opening": opening,
                "document_id": document_id,
                "evaluated_scene": scene,
            }
            if len(unit_ids) >= 3 and len(unit_ids) > len(before_units):
                introduced_units = sorted(unit_ids - before_units)
                blocking_unit_ids.update(introduced_units)
                findings.append(
                    {
                        **common,
                        "before_unit_count": len(before_units),
                        "after_unit_count": len(unit_ids),
                        "before_units": sorted(before_units),
                        "after_units": sorted(unit_ids),
                        "introduced_unit_ids": introduced_units,
                    }
                )
            elif len(unit_ids) >= 3:
                inherited_findings.append(
                    {
                        **common,
                        "unit_count": len(unit_ids),
                        "units": sorted(unit_ids),
                    }
                )

    try:
        negative_guard_registry = negative_guards.load_negative_guard_registry()
        negative_guard_registry_sha256 = str(
            negative_guard_registry["registry_sha256"]
        )
        negative_guard_registry_source_sha256 = str(
            negative_guard_registry["source_sha256"]
        )
        negative_guard_registry_source_format = str(
            negative_guard_registry["source_format"]
        )
    except (
        OSError,
        UnicodeError,
        negative_guards.NegativeGuardRegistryError,
        ValueError,
    ) as error:
        guard_review_reasons.append(
            f"NEGATIVE_GUARD_REGISTRY_UNAVAILABLE:{type(error).__name__}"
        )

    if negative_guard_registry is not None:
        try:
            guard_result = repetition_guards.audit_negative_guards(
                evaluated, list(negative_guard_registry.get("guards", []))
            )
        except repetition_guards.DetectorEvaluationReview as error:
            guard_review_reasons.append(
                f"NEGATIVE_GUARD_EVALUATION_REVIEW:{type(error).__name__}"
            )
        else:
            findings.extend(guard_result["findings"])
            inherited_findings.extend(guard_result["inherited_findings"])
            blocking_unit_ids.update(guard_result["blocking_unit_ids"])
            guard_review_reasons.extend(guard_result["review_reasons"])
            active_detector_definition_sha256.extend(
                guard_result["active_detector_definition_sha256"]
            )

    incomplete = len(evaluated) != len(expected)
    status = (
        "PASS"
        if not incomplete and not findings and not guard_review_reasons
        else "REVIEW"
    )
    policy = {
        "version": "cross-unit-repetition/v3",
        "author_view": "masked_text_without_protected_payload",
        "partition_key": ["logical_document_id", "resolved_scene"],
        "scene_all_semantics": "evaluate_each_resolved_scene_separately",
        "repair_signal_categories": ["repair-template-repetition"],
        "boundary_opening_han_chars": 6,
        "boundary_minimum_units": 3,
        "comparison": "after must not introduce additional cross-unit coverage",
        "template_normalization": "NFKC+remove-zero-width+remove-Han-internal-space",
        "corpus_negative_guards": [
            "regex_groups/v1",
            "structured_repeated_list/v1",
        ],
        "structured_tex_projection": ["LIST_BEGIN", "LIST_ITEM", "LIST_END"],
    }
    for collection in (findings, inherited_findings):
        for finding in collection:
            if "finding_fingerprint" in finding:
                continue
            finding["finding_fingerprint"] = sha256(
                json.dumps(
                    finding,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
    findings.sort(key=lambda item: str(item["finding_fingerprint"]))
    inherited_findings.sort(
        key=lambda item: str(item["finding_fingerprint"])
    )
    unit_inventory = [
        {
            "unit_id": str(record.get("unit_id", "")),
            "document_id": str(record.get("document_id", "")),
            "resolved_scene": str(record.get("resolved_scene", "")),
            "expected": bool(record.get("expected")),
            "state": str(record.get("state", "")),
        }
        for record in records
    ]
    records_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records_by_partition: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (document_id, scene), partition_records in all_grouped.items():
        records_by_document[document_id].extend(partition_records)
        records_by_partition[(document_id, scene)].extend(partition_records)

    def view_sha256(
        selected: Sequence[dict[str, Any]], field: str
    ) -> str:
        view = [
            {
                "unit_id": str(record.get("unit_id", "")),
                "sha256": (
                    sha256(str(record.get(field, "")).encode("utf-8"))
                    if isinstance(record.get(field), str)
                    else ""
                ),
            }
            for record in selected
        ]
        return sha256(
            json.dumps(
                view,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    logical_document_hashes = [
        {
            "document_id": document_id,
            "unit_ids": [str(item.get("unit_id", "")) for item in selected],
            "before_sha256": view_sha256(selected, "before_masked"),
            "candidate_sha256": view_sha256(selected, "after_masked"),
        }
        for document_id, selected in sorted(records_by_document.items())
    ]
    evaluation_partitions = [
        {
            "document_id": document_id,
            "resolved_scene": scene,
            "unit_ids": [str(item.get("unit_id", "")) for item in selected],
            "before_sha256": view_sha256(selected, "before_masked"),
            "candidate_sha256": view_sha256(selected, "after_masked"),
        }
        for (document_id, scene), selected in sorted(records_by_partition.items())
    ]
    before_document_view = [
        {
            "document_id": item["document_id"],
            "sha256": item["before_sha256"],
        }
        for item in logical_document_hashes
    ]
    after_document_view = [
        {
            "document_id": item["document_id"],
            "sha256": item["candidate_sha256"],
        }
        for item in logical_document_hashes
    ]
    return {
        "schema_version": "humanize-cross-unit-repetition/v3",
        "status": status,
        "expected_units": len(expected),
        "evaluated_units": len(evaluated),
        "before_blocks": len(before_blocks),
        "after_blocks": len(after_blocks),
        "findings": findings[:40],
        "finding_count": len(findings),
        "inherited_findings": inherited_findings[:40],
        "inherited_finding_count": len(inherited_findings),
        "blocking_unit_ids": sorted(blocking_unit_ids),
        "review_reasons": (
            (["INCOMPLETE_EDITABLE_UNITS"] if incomplete else [])
            + sorted(set(guard_review_reasons))
        ),
        "negative_guard_registry_source_sha256": negative_guard_registry_source_sha256,
        "negative_guard_registry_sha256": negative_guard_registry_sha256,
        "negative_guard_registry_status": (
            str(negative_guard_registry.get("status", ""))
            if negative_guard_registry is not None
            else "NOT_AVAILABLE"
        ),
        "negative_guard_registry_source_format": negative_guard_registry_source_format,
        "negative_guard_loader_version": negative_guards.LOADER_VERSION,
        # Compatibility aliases for v17 receipts. These hashes now bind only
        # the detector registry, never an executable positive-action profile.
        "action_catalog_sha256": negative_guard_registry_source_sha256,
        "action_profile_sha256": negative_guard_registry_sha256,
        "action_profile_status": (
            str(negative_guard_registry.get("status", ""))
            if negative_guard_registry is not None
            else "NOT_AVAILABLE"
        ),
        "active_detector_definition_sha256": sorted(
            set(active_detector_definition_sha256)
        ),
        "logical_document_hashes": logical_document_hashes,
        "evaluation_partitions": evaluation_partitions,
        "lexical_policy_sha256": sha256(
            output_validator.lexical.DEFAULT_LEXICON.read_bytes()
        ),
        "unit_inventory_sha256": sha256(
            json.dumps(
                unit_inventory,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "before_logical_document_sha256": sha256(
            json.dumps(
                before_document_view,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "candidate_logical_document_sha256": sha256(
            json.dumps(
                after_document_view,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "evaluation_scope": "PARTIAL" if incomplete else "FULL",
        "policy": policy,
        "policy_sha256": sha256(
            json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
    }


def _copied_read_only_context(original: str, restored: str, chunk: dict[str, Any]) -> list[str]:
    original_normalized = _normalize_context(original)
    restored_normalized = _normalize_context(restored)
    copied: list[str] = []
    for field in ("read_only_context_before", "read_only_context_after"):
        context = _normalize_context(str(chunk.get(field, "")))
        if len(context) < 4 or context in original_normalized:
            continue
        if context in restored_normalized:
            copied.append(field)
    return copied


def _protected_content_count_changes(
    original: str,
    restored: str,
    expected_ids: Sequence[str],
    span_map: dict[str, dict[str, Any]],
) -> list[str]:
    def canonical_newlines(value: str) -> str:
        return value.replace("\r\n", "\n").replace("\r", "\n")

    canonical_original = canonical_newlines(original)
    canonical_restored = canonical_newlines(restored)
    changed: list[str] = []
    for protected_id in expected_ids:
        content = canonical_newlines(str(span_map[protected_id]["content"]))
        if content and canonical_original.count(content) != canonical_restored.count(content):
            changed.append(protected_id)
    return changed


def _relative_render_paths(files: Sequence[dict[str, Any]]) -> dict[str, Path]:
    existing_paths = [
        Path(item["path"])
        for item in files
        if item["status"] not in {"UNRESOLVED", "UNRESOLVED_INCLUDE", "SKIPPED_GARBLED"}
    ]
    parents = [str(path.parent) for path in existing_paths]
    common: Path | None = None
    if parents:
        try:
            common = Path(os.path.commonpath(parents))
        except ValueError:
            common = None
    output: dict[str, Path] = {}
    for item in files:
        path = Path(item["path"])
        if common is not None:
            try:
                relative = path.relative_to(common)
            except ValueError:
                relative = Path(f"{item['file_id']}{path.suffix or '.txt'}")
        else:
            relative = Path(f"{item['file_id']}{path.suffix or '.txt'}")
        output[item["file_id"]] = relative
    return output


def _directory_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): sha256(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


TRANSIENT_FINALIZE_NAMES = {
    ".validation_staging",
    ".diffs_staging",
    ".rendered_staging",
    ".compile_check_staging",
    ".finalize.lock",
    AUTHORITY_GROUP_JOURNAL_NAME,
    AUTHORITY_GROUP_COMMIT_NAME,
    *AUTHORITY_GROUP_TARGET_NAMES,
    RUN_STATE_JOURNAL_NAME,
}


def _is_transient_finalize_relative(relative: Path) -> bool:
    if not relative.parts:
        return False
    name = relative.parts[0]
    return (
        name in TRANSIENT_FINALIZE_NAMES
        or name.startswith(AUTHORITY_GROUP_TRANSACTION_PREFIX)
        or name.startswith(AUTHORITY_GROUP_JOURNAL_STAGING_PREFIX)
        or name.startswith(AUTHORITY_GROUP_COMMIT_STAGING_PREFIX)
        or name.startswith(AUTHORITY_GROUP_TARGET_STAGING_PREFIX)
        or name.startswith(RUN_STATE_TRANSACTION_PREFIX)
        or name.startswith(RUN_STATE_JOURNAL_STAGING_PREFIX)
        or name.startswith(RUN_STATE_CLEANUP_PREFIX)
        or name.startswith(RUN_STATE_CLEANUP_STAGING_PREFIX)
    )

FAILED_ATTEMPT_METADATA_SCHEMA = "humanize-finalization-failed-attempt/v1"


def _run_state_hashes(run_dir: Path) -> dict[str, str]:
    """Hash all pre-existing run artifacts that a check command must not mutate."""
    if not run_dir.is_dir():
        return {}
    output: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(run_dir)
        if _is_transient_finalize_relative(relative):
            continue
        output[str(relative).replace("\\", "/")] = sha256(path.read_bytes())
    return output


def _run_state_closure(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Describe the exact non-transient file/directory closure of a run image."""
    if _is_link_or_reparse(run_dir) or not run_dir.is_dir():
        raise ValueError("run-state image must be an existing real directory")
    _validate_transaction_source_tree(run_dir)
    output: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.rglob("*")):
        relative = path.relative_to(run_dir)
        if _is_transient_finalize_relative(relative):
            continue
        key = relative.as_posix()
        if path.is_dir():
            output[key] = {"type": "directory"}
        elif path.is_file():
            raw = path.read_bytes()
            output[key] = {
                "type": "file",
                "bytes": len(raw),
                "sha256": sha256(raw),
            }
        else:
            raise ValueError("unsupported run-state image member: " + key)
    return output


def _immutable_prepare_state_hashes(run_dir: Path) -> dict[str, str]:
    """Hash only the sealed prepare closure, including its manifest bytes."""

    _verify_prepare_integrity(run_dir)
    manifest_path = run_dir / "prepare_integrity.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = _parse_json_strict(
        manifest_raw.decode("utf-8-sig"),
        "prepare_integrity.json",
    )
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("artifacts"), list
    ):
        raise ValueError("invalid prepare state manifest")
    output = {"prepare_integrity.json": sha256(manifest_raw)}
    for item in manifest["artifacts"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("invalid prepare state artifact")
        relative = item["path"]
        artifact = run_dir / relative
        raw = artifact.read_bytes()
        digest = sha256(raw)
        if digest != item.get("sha256"):
            raise ValueError(f"prepare state artifact hash mismatch: {relative}")
        output[relative] = digest
    return dict(sorted(output.items()))


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    if callable(is_junction) and is_junction(path):
        return True
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _validate_transaction_source_tree(run_dir: Path) -> None:
    if _is_link_or_reparse(run_dir):
        raise ValueError("run directory must not be a symlink or reparse point")
    stack = [run_dir]
    while stack:
        parent = stack.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(run_dir)
                if _is_transient_finalize_relative(relative):
                    continue
                if _is_link_or_reparse(path):
                    raise ValueError(
                        "run artifact must not be a symlink or reparse point: "
                        + relative.as_posix()
                    )
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    if path.stat(follow_symlinks=False).st_nlink != 1:
                        raise ValueError(
                            "run artifact hard link is not supported: "
                            + relative.as_posix()
                        )
                else:
                    raise ValueError(
                        "unsupported run artifact type: " + relative.as_posix()
                    )


def _copy_run_state(run_dir: Path, backup_dir: Path) -> None:
    """Copy every non-transient run artifact before publication starts."""
    _validate_transaction_source_tree(run_dir)
    state_before = _run_state_closure(run_dir)
    backup_dir.mkdir(parents=True, exist_ok=False)
    for source in sorted(run_dir.iterdir()):
        if _is_transient_finalize_relative(Path(source.name)):
            continue
        destination = backup_dir / source.name
        if source.is_symlink():
            raise ValueError(f"run artifact symlink is not supported: {source.name}")
        if source.is_dir():
            shutil.copytree(source, destination)
        elif source.is_file():
            shutil.copy2(source, destination)
        else:
            raise ValueError(f"unsupported run artifact type: {source.name}")
    state_after = _run_state_closure(run_dir)
    backup_state = _run_state_closure(backup_dir)
    if state_before != state_after or state_before != backup_state:
        raise ValueError("run state changed while transaction backup was created")


def _remove_run_artifact(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _restore_run_state(run_dir: Path, backup_dir: Path) -> None:
    """Restore the exact pre-attempt run state while retaining the held lock."""
    for current in sorted(run_dir.iterdir()):
        if _is_transient_finalize_relative(Path(current.name)):
            continue
        _remove_run_artifact(current)
    for source in sorted(backup_dir.iterdir()):
        destination = run_dir / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def _run_state_transaction_path(run_dir: Path, transaction_id: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None:
        raise ValueError("run-state transaction ID is invalid")
    return run_dir / (RUN_STATE_TRANSACTION_PREFIX + transaction_id)


def _parse_run_state_journal(raw: bytes) -> dict[str, Any]:
    journal = _parse_json_strict(raw.decode("utf-8"), RUN_STATE_JOURNAL_NAME)
    fields = {
        "schema_version",
        "transaction_id",
        "state",
        "base_authority_commit_sha256",
        "base_authority_generation",
        "base_state_closure",
        "next_authority_commit_sha256",
        "next_authority_generation",
        "next_state_closure",
    }
    if not isinstance(journal, dict) or set(journal) != fields:
        raise ValueError("run-state journal fields are invalid")
    transaction_id = journal.get("transaction_id")
    base_closure = journal.get("base_state_closure")
    next_closure = journal.get("next_state_closure")
    if (
        journal.get("schema_version") != RUN_STATE_JOURNAL_SCHEMA
        or journal.get("state") not in {"PREPARED", "CLEANUP"}
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None
        or re.fullmatch(
            r"[0-9a-f]{64}", str(journal.get("base_authority_commit_sha256", ""))
        )
        is None
        or not isinstance(journal.get("base_authority_generation"), int)
        or isinstance(journal.get("base_authority_generation"), bool)
        or journal["base_authority_generation"] < 0
        or not isinstance(base_closure, dict)
        or (
            journal.get("next_authority_commit_sha256") is not None
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(journal.get("next_authority_commit_sha256", "")),
            )
            is None
        )
        or (
            journal.get("next_authority_generation") is not None
            and (
                not isinstance(journal.get("next_authority_generation"), int)
                or isinstance(journal.get("next_authority_generation"), bool)
                or journal["next_authority_generation"]
                != journal["base_authority_generation"] + 1
            )
        )
        or (next_closure is not None and not isinstance(next_closure, dict))
    ):
        raise ValueError("run-state journal schema is invalid")
    next_values = (
        journal.get("next_authority_commit_sha256"),
        journal.get("next_authority_generation"),
        next_closure,
    )
    if any(value is None for value in next_values) and not all(
        value is None for value in next_values
    ):
        raise ValueError("run-state next closure binding is partial")
    for closure in (base_closure, next_closure):
        if closure is None:
            continue
        folded: set[str] = set()
        for relative, descriptor in closure.items():
            pure = PurePosixPath(relative) if isinstance(relative, str) else None
            if (
                pure is None
                or not relative
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in relative
                or relative.casefold() in folded
                or not isinstance(descriptor, dict)
            ):
                raise ValueError("run-state journal closure path is invalid")
            folded.add(relative.casefold())
            if descriptor == {"type": "directory"}:
                continue
            if set(descriptor) != {"type", "bytes", "sha256"} or (
                descriptor.get("type") != "file"
                or not isinstance(descriptor.get("bytes"), int)
                or isinstance(descriptor.get("bytes"), bool)
                or descriptor["bytes"] < 0
                or not isinstance(descriptor.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is None
            ):
                raise ValueError("run-state journal closure member is invalid")
    return journal


def _bind_run_state_next(
    run_dir: Path,
    transaction_id: str,
    next_commit_raw: bytes,
    next_commit: dict[str, Any],
    *,
    require_journal: bool = False,
) -> None:
    """Seal the complete next run image before the authority pointer can move."""
    journal_path = run_dir / RUN_STATE_JOURNAL_NAME
    if not _path_lexists(journal_path):
        if require_journal:
            raise RuntimeError("required run-state journal is missing")
        return
    journal = _parse_run_state_journal(
        _authority_regular_file_bytes(journal_path, "run-state journal")
    )
    if journal["transaction_id"] != transaction_id:
        raise RuntimeError("run-state next binding transaction mismatch")
    expected_sha = journal.get("next_authority_commit_sha256")
    if expected_sha is not None:
        if (
            expected_sha != sha256(next_commit_raw)
            or journal["next_authority_generation"] != next_commit["generation"]
        ):
            raise RuntimeError("run-state next authority binding changed")
        return
    transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
    next_dir = transaction_dir / "next"
    _copy_run_state(run_dir, next_dir)
    journal["next_authority_commit_sha256"] = sha256(next_commit_raw)
    journal["next_authority_generation"] = next_commit["generation"]
    journal["next_state_closure"] = _run_state_closure(next_dir)
    _replace_bytes_atomic(
        journal_path,
        _canonical_json_bytes(journal),
        temporary_prefix=RUN_STATE_JOURNAL_STAGING_PREFIX,
    )
    if _parse_run_state_journal(
        _authority_regular_file_bytes(journal_path, "run-state journal")
    ) != journal:
        raise RuntimeError("run-state next binding verification failed")


def _cleanup_run_state_transaction(
    run_dir: Path, transaction_id: str, *, require_journal: bool = True
) -> None:
    journal_path = run_dir / RUN_STATE_JOURNAL_NAME
    transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
    if require_journal and not _path_lexists(journal_path):
        raise RuntimeError("run-state journal disappeared before cleanup")
    if _path_lexists(journal_path):
        journal = _parse_run_state_journal(
            _authority_regular_file_bytes(journal_path, "run-state journal")
        )
        if journal["transaction_id"] != transaction_id:
            raise RuntimeError("run-state cleanup transaction binding mismatch")
        if journal["state"] != "CLEANUP":
            journal["state"] = "CLEANUP"
            _replace_bytes_atomic(
                journal_path,
                _canonical_json_bytes(journal),
                temporary_prefix=RUN_STATE_JOURNAL_STAGING_PREFIX,
            )
        pointer_sha, selected_closure = _recover_selected_run_state(run_dir, journal)
        cleanup_marker = {
            "schema_version": RUN_STATE_CLEANUP_SCHEMA,
            "transaction_id": transaction_id,
            "authority_commit_sha256": pointer_sha,
            "selected_state_closure": selected_closure,
        }
        marker_path = run_dir / (RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json")
        _replace_bytes_atomic(
            marker_path,
            _canonical_json_bytes(cleanup_marker),
            temporary_prefix=RUN_STATE_CLEANUP_STAGING_PREFIX,
        )
    if _path_lexists(journal_path):
        journal_path.unlink()
    if _path_lexists(transaction_dir):
        if _is_link_or_reparse(transaction_dir) or not transaction_dir.is_dir():
            raise ValueError("run-state transaction has an unsafe type")
        shutil.rmtree(transaction_dir)
    marker_path = run_dir / (RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json")
    if _path_lexists(marker_path):
        marker_path.unlink()


def _recover_selected_run_state(
    run_dir: Path, journal: dict[str, Any]
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Install and verify the image selected by the sole authority pointer."""
    transaction_id = journal["transaction_id"]
    transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
    commit_path = run_dir / AUTHORITY_GROUP_COMMIT_NAME
    commit_raw = _authority_regular_file_bytes(commit_path, "authority group commit")
    commit = _parse_authority_commit(commit_raw)
    if (
        sha256(commit_raw) == journal["base_authority_commit_sha256"]
        and commit["generation"] == journal["base_authority_generation"]
    ):
        side = "base"
        expected = journal["base_state_closure"]
    elif (
        journal.get("next_authority_commit_sha256") is not None
        and sha256(commit_raw) == journal["next_authority_commit_sha256"]
        and commit["transaction_id"] == transaction_id
        and commit["generation"] == journal["next_authority_generation"]
    ):
        side = "next"
        expected = journal["next_state_closure"]
    else:
        raise RuntimeError("authority pointer is outside run-state journal state")
    image_dir = transaction_dir / side
    if (
        _is_link_or_reparse(transaction_dir)
        or not transaction_dir.is_dir()
        or _is_link_or_reparse(image_dir)
        or not image_dir.is_dir()
    ):
        raise ValueError("selected run-state image is unavailable")
    actual_image = _run_state_closure(image_dir)
    if actual_image != expected:
        raise RuntimeError("selected run-state image does not match journal closure")
    _restore_run_state(run_dir, image_dir)
    if _run_state_closure(run_dir) != expected:
        raise RuntimeError("run-state recovery verification failed")
    return sha256(commit_raw), expected


def _parse_run_state_cleanup_marker(raw: bytes) -> dict[str, Any]:
    marker = _parse_json_strict(raw.decode("utf-8"), "run-state cleanup marker")
    if not isinstance(marker, dict) or set(marker) != {
        "schema_version",
        "transaction_id",
        "authority_commit_sha256",
        "selected_state_closure",
    }:
        raise ValueError("run-state cleanup marker fields are invalid")
    transaction_id = marker.get("transaction_id")
    if (
        marker.get("schema_version") != RUN_STATE_CLEANUP_SCHEMA
        or not isinstance(transaction_id, str)
        or re.fullmatch(r"[0-9a-f]{24}", transaction_id) is None
        or re.fullmatch(
            r"[0-9a-f]{64}", str(marker.get("authority_commit_sha256", ""))
        )
        is None
        or not isinstance(marker.get("selected_state_closure"), dict)
    ):
        raise ValueError("run-state cleanup marker schema is invalid")
    probe = {
        "schema_version": RUN_STATE_JOURNAL_SCHEMA,
        "transaction_id": transaction_id,
        "state": "PREPARED",
        "base_authority_commit_sha256": marker["authority_commit_sha256"],
        "base_authority_generation": 0,
        "base_state_closure": marker["selected_state_closure"],
        "next_authority_commit_sha256": None,
        "next_authority_generation": None,
        "next_state_closure": None,
    }
    _parse_run_state_journal(_canonical_json_bytes(probe))
    return marker


def _recover_run_state_cleanup_markers(run_dir: Path) -> bool:
    recovered = False
    for residue in sorted(run_dir.glob(RUN_STATE_CLEANUP_STAGING_PREFIX + "*")):
        _authority_regular_file_bytes(residue, "run-state cleanup staging residue")
        raise RuntimeError(
            "untrusted run-state cleanup staging residue requires manual audit"
        )
    for marker_path in sorted(run_dir.glob(RUN_STATE_CLEANUP_PREFIX + "*.json")):
        marker = _parse_run_state_cleanup_marker(
            _authority_regular_file_bytes(marker_path, "run-state cleanup marker")
        )
        transaction_id = marker["transaction_id"]
        if marker_path.name != RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json":
            raise ValueError("run-state cleanup marker name is invalid")
        commit_raw = _authority_regular_file_bytes(
            run_dir / AUTHORITY_GROUP_COMMIT_NAME, "authority group commit"
        )
        if sha256(commit_raw) != marker["authority_commit_sha256"]:
            raise RuntimeError("cleanup marker authority pointer changed")
        if _run_state_closure(run_dir) != marker["selected_state_closure"]:
            raise RuntimeError("cleanup marker live closure changed")
        transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
        if _path_lexists(transaction_dir):
            if _is_link_or_reparse(transaction_dir) or not transaction_dir.is_dir():
                raise ValueError("run-state cleanup transaction has an unsafe type")
            shutil.rmtree(transaction_dir)
        marker_path.unlink()
        recovered = True
    return recovered


def _recover_run_state_journal(run_dir: Path) -> bool:
    for residue in sorted(run_dir.glob(RUN_STATE_JOURNAL_STAGING_PREFIX + "*")):
        _authority_regular_file_bytes(residue, "run-state journal staging residue")
        raise RuntimeError(
            "untrusted run-state journal staging residue requires manual audit"
        )
    journal_path = run_dir / RUN_STATE_JOURNAL_NAME
    if not _path_lexists(journal_path):
        if _recover_run_state_cleanup_markers(run_dir):
            return True
        orphaned = [
            path
            for path in run_dir.glob(RUN_STATE_TRANSACTION_PREFIX + "*")
            if re.fullmatch(
                re.escape(RUN_STATE_TRANSACTION_PREFIX) + r"[0-9a-f]{24}",
                path.name,
            )
            is not None
        ]
        if orphaned:
            raise RuntimeError("orphan run-state transaction requires manual audit")
        return False
    raw = _authority_regular_file_bytes(journal_path, "run-state journal")
    journal = _parse_run_state_journal(raw)
    transaction_id = journal["transaction_id"]
    transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
    _recover_selected_run_state(run_dir, journal)
    _cleanup_run_state_transaction(run_dir, transaction_id)
    return True


def _begin_run_state_transaction(run_dir: Path) -> tuple[str, Path]:
    if _path_lexists(run_dir / RUN_STATE_JOURNAL_NAME):
        raise RuntimeError("run-state transaction is already active")
    transaction_id = _authority_group_transaction_id()
    transaction_dir = _run_state_transaction_path(run_dir, transaction_id)
    transaction_dir.mkdir()
    backup_dir = transaction_dir / "base"
    try:
        _copy_run_state(run_dir, backup_dir)
        commit_raw = _authority_regular_file_bytes(
            run_dir / AUTHORITY_GROUP_COMMIT_NAME, "authority group commit"
        )
        commit = _parse_authority_commit(commit_raw)
        journal = {
            "schema_version": RUN_STATE_JOURNAL_SCHEMA,
            "transaction_id": transaction_id,
            "state": "PREPARED",
            "base_authority_commit_sha256": sha256(commit_raw),
            "base_authority_generation": commit["generation"],
            "base_state_closure": _run_state_closure(backup_dir),
            "next_authority_commit_sha256": None,
            "next_authority_generation": None,
            "next_state_closure": None,
        }
        _replace_bytes_atomic(
            run_dir / RUN_STATE_JOURNAL_NAME,
            _canonical_json_bytes(journal),
            temporary_prefix=RUN_STATE_JOURNAL_STAGING_PREFIX,
        )
        persisted = _parse_run_state_journal(
            _authority_regular_file_bytes(
                run_dir / RUN_STATE_JOURNAL_NAME, "run-state journal"
            )
        )
        if persisted != journal:
            raise RuntimeError("run-state journal verification failed")
        return transaction_id, backup_dir
    except BaseException:
        if not _path_lexists(run_dir / RUN_STATE_JOURNAL_NAME):
            shutil.rmtree(transaction_dir, ignore_errors=True)
        raise


def _published_evidence_exists(root: Path) -> bool:
    return any(
        (root / name).exists()
        for name in (
            "rendered",
            "rendered_review",
            "rendered_partial",
            "validation",
            "diffs",
            "coverage_ledger.final.csv",
            "rendered_manifest.csv",
            "rollback_manifest.json",
            "finalization_metadata.json",
        )
    )


def _runtime_error_code(error: BaseException) -> str:
    if isinstance(error, FileNotFoundError):
        return "FILE_NOT_FOUND"
    if isinstance(error, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(error, UnicodeError):
        return "INVALID_ENCODING"
    if isinstance(error, ValueError):
        return "VALIDATION_ERROR"
    if isinstance(error, RuntimeError):
        return "RUNTIME_ERROR"
    if isinstance(error, OSError):
        return "OS_ERROR"
    return "INTERNAL_ERROR"


def _runtime_failure_metadata(
    error: BaseException,
    *,
    run_dir: Path,
    run_state_restored: bool,
    finalization_metadata_preserved: bool,
    published_evidence_preserved: bool,
) -> dict[str, Any]:
    return {
        "schema_version": FAILED_ATTEMPT_METADATA_SCHEMA,
        "tool": "finalize_humanize_long_document.py",
        "created_at": utc_now(),
        "status": "FAIL",
        "exit_code": 1,
        "candidate_assembly_status": "FAIL",
        "delivery_gate_status": "FAIL",
        "publish_state": "FAILED",
        "runtime_error": True,
        "failed_attempt": True,
        "error_type": type(error).__name__,
        "error_code": _runtime_error_code(error),
        "error_message_redacted": True,
        "paths_redacted": True,
        "run_dir_scope": "CURRENT_RUN_DIR",
        "run_state_restored_after_failure": run_state_restored,
        "finalization_metadata_preserved": finalization_metadata_preserved,
        "published_evidence_preserved": published_evidence_preserved,
        "failed_attempt_metadata_path": "last_failed_attempt_metadata.json",
        "latest_attempt_metadata_path": "latest_attempt_metadata.json",
        "attempt_metadata_role": "LATEST_FAILED_ATTEMPT_AUTHORITY",
        "attempt_metadata_persistence_status": "PASS",
        "attempt_metadata_group_atomic": True,
        "attempt_metadata_paths_authoritative": True,
        "failed_attempt_evidence_status": "NOT_RETAINED_AFTER_ROLLBACK",
        "failed_attempt_evidence_paths_reusable": False,
        "humanize_completion_claim_allowed": False,
        "full_completion_claim_allowed": False,
        "academic_correctness": "NOT_EVALUATED",
    }


def _failed_attempt_record(
    metadata: dict[str, Any],
    *,
    run_dir: Path,
    finalization_metadata_preserved: bool,
    published_evidence_preserved: bool,
) -> dict[str, Any]:
    """Detach failed-attempt hashes from restored evidence namespaces."""
    record = json.loads(json.dumps(metadata, ensure_ascii=False))
    del run_dir

    redacted_text_keys = {
        "command",
        "cwd",
        "stderr",
        "stdout",
    }
    redacted_path_keys = {
        "after_path",
        "before_path",
        "diff_path",
        "path",
        "published_path",
        "rewrite_intent_evidence_path",
        "run_dir",
        "source_path",
    }

    def looks_absolute_path(value: str) -> bool:
        if re.match(r"^[A-Za-z]:[\\/]", value):
            return True
        if value.startswith(("/", "\\\\")):
            return True
        return False

    def detach(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {
                item_key: detach(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [detach(item, key) for item in value]
        if isinstance(value, str):
            if key in redacted_text_keys or key in redacted_path_keys:
                return ""
            if looks_absolute_path(value):
                return ""
        return value

    record = detach(record)
    unresolved = record.get("unresolved_reason_summary")
    if isinstance(unresolved, dict):
        unresolved["details_artifact"] = ""
        unresolved["details_artifact_status"] = "NOT_RETAINED_AFTER_ROLLBACK"
    record.update(
        {
            "schema_version": FAILED_ATTEMPT_METADATA_SCHEMA,
            "failed_attempt": True,
            "run_state_restored_after_failure": True,
            "finalization_metadata_preserved": finalization_metadata_preserved,
            "published_evidence_preserved": published_evidence_preserved,
            "failed_attempt_metadata_path": "last_failed_attempt_metadata.json",
            "latest_attempt_metadata_path": "latest_attempt_metadata.json",
            "attempt_metadata_role": "LATEST_FAILED_ATTEMPT_AUTHORITY",
            "attempt_metadata_persistence_status": "PASS",
            "attempt_metadata_group_atomic": True,
            "attempt_metadata_paths_authoritative": True,
            "failed_attempt_evidence_status": "NOT_RETAINED_AFTER_ROLLBACK",
            "failed_attempt_evidence_paths_reusable": False,
            "failed_attempt_sensitive_fields_redacted": True,
        }
    )
    return record


def _copy_for_check(source: Path, destination: Path) -> None:
    """Create a disposable check workspace without exposing the publish tree."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _commit_evidence_directory(staged: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    staged.rename(destination)


def _source_changes(file_manifest: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for record in file_manifest:
        if not record["sha256"]:
            continue
        source = Path(record["path"])
        if not source.exists():
            changes.append(
                {
                    "file_id": record["file_id"],
                    "path": record["path"],
                    "snapshot_sha256": record["sha256"],
                    "current_sha256": "",
                    "current_state": "MISSING",
                }
            )
            continue
        if not source.is_file():
            changes.append(
                {
                    "file_id": record["file_id"],
                    "path": record["path"],
                    "snapshot_sha256": record["sha256"],
                    "current_sha256": "",
                    "current_state": "NOT_FILE",
                }
            )
            continue
        current_hash = sha256(source.read_bytes())
        if current_hash != record["sha256"]:
            changes.append(
                {
                    "file_id": record["file_id"],
                    "path": record["path"],
                    "snapshot_sha256": record["sha256"],
                    "current_sha256": current_hash,
                    "current_state": "MODIFIED",
                }
            )
    return changes


def _compile_check_result(
    *,
    status: str,
    command: str = "",
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    cwd: Path | None = None,
    integrity_status: str = "NOT_RUN",
    integrity_changes: dict[str, Any] | None = None,
    process_containment: str = "NOT_RUN",
    descendant_cleanup: str = "NOT_RUN",
    timed_out: bool = False,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Build one stable compile-check payload for executed and skipped checks."""
    return {
        "status": status,
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "cwd": str(cwd.resolve()) if cwd is not None else None,
        "integrity_status": integrity_status,
        "integrity_changes": dict(integrity_changes or {}),
        "process_containment": process_containment,
        "descendant_cleanup": descendant_cleanup,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
    }


def _assign_windows_kill_on_close_job(process: subprocess.Popen[str]) -> Any:
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        information = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        information.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(information), ctypes.sizeof(information)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.AssignProcessToJobObject(
            job, wintypes.HANDLE(int(process._handle))
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return job, kernel32
    except BaseException:
        try:
            kernel32.CloseHandle(job)
        except BaseException:
            pass
        raise


def _terminate_compile_process_tree(
    process: subprocess.Popen[str], containment: Any
) -> str:
    if os.name == "nt":
        if containment is None:
            return _kill_uncontained_compile_process(process)
        job, kernel32 = containment
        terminated = False
        closed = False
        try:
            terminated = bool(kernel32.TerminateJobObject(job, 1))
        except BaseException:
            # Cleanup must continue even when a second interrupt arrives.
            terminated = False
        finally:
            try:
                closed = bool(kernel32.CloseHandle(job))
            except BaseException:
                closed = False
        return "PASS" if terminated and closed else "FAIL"
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        return "FAIL"
    return "PASS"


def _kill_uncontained_compile_process(process: subprocess.Popen[str]) -> str:
    """Best-effort direct kill for a process that never entered containment."""
    for _attempt in range(3):
        try:
            if process.poll() is not None:
                return "PASS"
        except BaseException:
            pass
        try:
            process.kill()
        except BaseException:
            # A repeated interrupt must not skip the bounded retry loop.
            continue
        try:
            process.wait(timeout=1.0)
        except BaseException:
            pass
        try:
            if process.poll() is not None:
                return "PASS"
        except BaseException:
            pass
    return "FAIL"


def _linux_process_children() -> dict[int, list[int]] | None:
    """Return the current Linux parent/child map without shelling out."""
    if not sys.platform.startswith("linux"):
        return None
    children: dict[int, list[int]] = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    for name in names:
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            stat_line = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            fields = stat_line.rsplit(")", 1)[1].split()
            ppid = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(pid)
    return children


def _linux_process_descendants(root_pid: int) -> set[int] | None:
    children = _linux_process_children()
    if children is None:
        return None
    found: set[int] = set()
    pending = list(children.get(root_pid, ()))
    while pending:
        pid = pending.pop()
        if pid in found or pid == root_pid:
            continue
        found.add(pid)
        pending.extend(children.get(pid, ()))
    return found


def _kill_linux_descendants_before_supervisor_exit(
    process: subprocess.Popen[str],
) -> str:
    """Kill descendants while the wrapper still owns their ancestry.

    This is only the timeout fallback.  The wrapper's subreaper protocol is
    the primary cleanup path because it can also see descendants that detach
    with ``setsid()`` and are subsequently adopted by the wrapper.
    """
    if not sys.platform.startswith("linux"):
        return "FAIL"
    seen: set[int] = set()
    for _attempt in range(25):
        try:
            if process.poll() is not None:
                return "FAIL"
        except BaseException:
            return "FAIL"
        current = _linux_process_descendants(process.pid)
        if current is None:
            return "FAIL"
        if not current:
            try:
                return "PASS" if process.poll() is None else "FAIL"
            except BaseException:
                return "FAIL"
        seen.update(current)
        for pid in sorted(current, reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                return "FAIL"
        try:
            time.sleep(0.02)
        except BaseException:
            # Continue immediately: preserving the original caller exception
            # is secondary to finishing the bounded cleanup attempt.
            pass
    try:
        if process.poll() is not None:
            return "FAIL"
    except BaseException:
        return "FAIL"
    remaining = _linux_process_descendants(process.pid)
    if remaining is None:
        return "FAIL"
    try:
        if process.poll() is not None:
            return "FAIL"
    except BaseException:
        return "FAIL"
    return "PASS" if remaining == set() else "FAIL"


def _stop_posix_compile_supervisor(
    process: subprocess.Popen[str], *, graceful_timeout: float = 5.0
) -> str:
    """Ask the live wrapper to clean its adopted tree before killing it."""
    try:
        process.terminate()
    except BaseException:
        pass
    try:
        process.wait(timeout=graceful_timeout)
        return "PASS"
    except BaseException:
        # Timeout, a second interrupt, and wait failures all enter the same
        # fail-closed fallback.  Descendants must be enumerated before the
        # subreaper wrapper is killed or their ancestry becomes unobservable.
        pass

    try:
        descendants_cleanup = _kill_linux_descendants_before_supervisor_exit(process)
    except BaseException:
        descendants_cleanup = "FAIL"
    try:
        process.kill()
    except BaseException:
        pass
    try:
        process.wait(timeout=1.0)
    except BaseException:
        pass
    try:
        group_cleanup = _terminate_compile_process_tree(process, None)
    except BaseException:
        group_cleanup = "FAIL"
    return (
        "PASS"
        if descendants_cleanup == "PASS" and group_cleanup == "PASS"
        else "FAIL"
    )


def _posix_process_containment_label(
    *, supervisor_cleanup: str, return_code: int | None
) -> str:
    if not sys.platform.startswith("linux"):
        return "POSIX_SUBREAPER_UNSUPPORTED"
    if supervisor_cleanup != "PASS" and return_code == 125:
        return "LINUX_SUBREAPER_UNAVAILABLE"
    return "LINUX_SUBREAPER_PROCESS_GROUP"


def _posix_compile_wrapper_source() -> str:
    """Return a POSIX supervisor that can reap detached descendants on Linux.

    A process group alone does not contain a child that calls ``setsid``.  On
    Linux the wrapper therefore becomes a child subreaper, waits for the
    requested command, and kills/reaps every process subsequently adopted by
    it.  The result is sent through a dedicated inherited descriptor so user
    stdout cannot forge the cleanup status.  Non-Linux POSIX hosts fail closed
    because this implementation cannot make the same detached-descendant
    guarantee there.
    """
    return r'''
import ctypes
import json
import os
import signal
import subprocess
import sys
import time

STATUS_FD = int(os.environ.get("CODEX_COMPILE_STATUS_FD", "-1"))


class SupervisorSignal(BaseException):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


def emit(payload):
    if STATUS_FD < 0:
        return
    try:
        data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        os.write(STATUS_FD, data)
    except OSError:
        pass


def enable_subreaper():
    if not sys.platform.startswith("linux"):
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        # Linux PR_SET_CHILD_SUBREAPER; ctypes keeps this call dependency-free.
        return libc.prctl(36, 1, 0, 0, 0) == 0
    except (AttributeError, OSError):
        return False


def process_children():
    children = {}
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    for name in names:
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            with open("/proc/%d/stat" % pid, "r", encoding="ascii") as stream:
                stat_line = stream.read()
            # The comm field may contain spaces and ')' characters.  The last
            # ')' is the stable delimiter before state and parent PID.
            fields = stat_line.rsplit(")", 1)[1].split()
            ppid = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(pid)
    return children


def descendants(root_pid):
    children = process_children()
    if children is None:
        return None
    found = set()
    pending = list(children.get(root_pid, ()))
    while pending:
        pid = pending.pop()
        if pid in found or pid == root_pid:
            continue
        found.add(pid)
        pending.extend(children.get(pid, ()))
    return found


def reap_children():
    while True:
        try:
            pid, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        except OSError:
            return
        if pid == 0:
            return


def cleanup_adopted_descendants(subreaper_enabled):
    if not subreaper_enabled:
        return False
    root_pid = os.getpid()
    for _attempt in range(25):
        reap_children()
        current = descendants(root_pid)
        if current is None:
            return False
        if not current:
            return True
        for pid in sorted(current, reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                return False
        time.sleep(0.02)
    reap_children()
    remaining = descendants(root_pid)
    return remaining == set()


def stop_direct_child(child):
    if child is None:
        return True
    try:
        if child.poll() is None:
            child.terminate()
    except (OSError, ProcessLookupError):
        pass
    try:
        child.wait(timeout=1.0)
        return True
    except subprocess.TimeoutExpired:
        pass
    except (OSError, ProcessLookupError):
        return child.poll() is not None
    try:
        child.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        child.wait()
    except (OSError, ProcessLookupError):
        pass
    return child.poll() is not None


def raise_supervisor_signal(signum, _frame):
    raise SupervisorSignal(signum)


def ignore_supervisor_signals():
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, signal.SIG_IGN)


command = sys.stdin.read()
subreaper_enabled = enable_subreaper()
if not subreaper_enabled:
    # Do not execute an uncontained command.  A process-group-only fallback
    # cannot make a truthful guarantee for a child that calls setsid().
    emit({"cleanup": "FAIL", "command_exit": None})
    raise SystemExit(125)
for watched_signal in (signal.SIGTERM, signal.SIGINT):
    signal.signal(watched_signal, raise_supervisor_signal)
command_exit = 125
child = None
try:
    child = subprocess.Popen(command, shell=True, close_fds=True)
    command_exit = child.wait()
    cleanup_ok = cleanup_adopted_descendants(subreaper_enabled)
except SupervisorSignal as interruption:
    # Keep the subreaper alive until the direct shell has stopped and every
    # adopted descendant has been killed and reaped.  A second catchable
    # signal must not interrupt that critical section.
    ignore_supervisor_signals()
    direct_child_stopped = stop_direct_child(child)
    cleanup_ok = cleanup_adopted_descendants(subreaper_enabled)
    emit({
        "cleanup": "PASS" if direct_child_stopped and cleanup_ok else "FAIL",
        "command_exit": 128 + interruption.signum,
    })
    raise SystemExit(128 + interruption.signum)
except BaseException:
    ignore_supervisor_signals()
    direct_child_stopped = stop_direct_child(child)
    cleanup_ok = cleanup_adopted_descendants(subreaper_enabled)
    emit({
        "cleanup": "PASS" if direct_child_stopped and cleanup_ok else "FAIL",
        "command_exit": command_exit,
    })
    raise

emit({"cleanup": "PASS" if cleanup_ok else "FAIL", "command_exit": command_exit})
raise SystemExit(command_exit)
'''


def _read_posix_compile_status(
    fd: int | None,
    *,
    timeout_seconds: float = COMPILE_STATUS_READ_TIMEOUT_SECONDS,
    max_bytes: int = COMPILE_STATUS_MAX_BYTES,
    expected_command_exit: int | None = None,
) -> str:
    """Read one bounded supervisor cleanup result from its dedicated pipe."""
    if fd is None:
        return "FAIL"
    try:
        os.set_blocking(fd, False)
        deadline = time.monotonic() + timeout_seconds
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(fd, min(65536, max_bytes - total + 1))
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return "FAIL"
                time.sleep(0.01)
                continue
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return "FAIL"
            chunks.append(chunk)
    except (OSError, ValueError):
        return "FAIL"
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        records = [
            _parse_json_strict(line, "compile supervisor status")
            for line in b"".join(chunks).decode("utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeDecodeError, ValueError, TypeError):
        return "FAIL"
    # More than one record means the supervisor protocol was polluted.  Do
    # not accept a later PASS over an earlier conflicting or forged record.
    if len(records) != 1 or not isinstance(records[0], dict):
        return "FAIL"
    record = records[0]
    if set(record) != {"cleanup", "command_exit"}:
        return "FAIL"
    cleanup = record.get("cleanup")
    command_exit = record.get("command_exit")
    if cleanup not in {"PASS", "FAIL"}:
        return "FAIL"
    if command_exit is not None and (
        isinstance(command_exit, bool) or not isinstance(command_exit, int)
    ):
        return "FAIL"
    if expected_command_exit is not None and command_exit != expected_command_exit:
        return "FAIL"
    return "PASS" if cleanup == "PASS" else "FAIL"


def _validated_compile_timeout_seconds(value: float) -> float:
    timeout_seconds = float(value)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("compile check timeout must be a finite positive number")
    return timeout_seconds


def _run_compile(
    command: str | None,
    cwd: Path,
    *,
    timeout_seconds: float = DEFAULT_COMPILE_CHECK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if not command:
        return _compile_check_result(status="NOT_RUN")
    timeout_seconds = _validated_compile_timeout_seconds(timeout_seconds)
    wrapper = (
        "import subprocess,sys; "
        "command=sys.stdin.read(); "
        "raise SystemExit(subprocess.call(command, shell=True))"
    )
    status_read_fd: int | None = None
    status_write_fd: int | None = None
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        popen_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdin": subprocess.PIPE,
            "stdout": stdout_file,
            "stderr": stderr_file,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            process_containment = "WINDOWS_JOB_OBJECT"
        else:
            wrapper = _posix_compile_wrapper_source()
            try:
                status_read_fd, status_write_fd = os.pipe()
                os.set_inheritable(status_write_fd, True)
                environment = os.environ.copy()
                environment["CODEX_COMPILE_STATUS_FD"] = str(status_write_fd)
                popen_kwargs["env"] = environment
                popen_kwargs["pass_fds"] = (status_write_fd,)
            except BaseException:
                for descriptor in (status_read_fd, status_write_fd):
                    if descriptor is not None:
                        try:
                            os.close(descriptor)
                        except OSError:
                            pass
                status_read_fd = None
                status_write_fd = None
                raise
            popen_kwargs["start_new_session"] = True
            process_containment = "LINUX_SUBREAPER_PROCESS_GROUP"
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-X", "utf8", "-c", wrapper],
                **popen_kwargs,
            )
        except BaseException:
            if status_read_fd is not None:
                try:
                    os.close(status_read_fd)
                except OSError:
                    pass
                status_read_fd = None
            raise
        finally:
            if status_write_fd is not None:
                try:
                    os.close(status_write_fd)
                except OSError:
                    pass
                status_write_fd = None
        containment: Any = None
        timed_out = False
        timeout_cleanup = "NOT_RUN"
        try:
            if os.name == "nt":
                containment = _assign_windows_kill_on_close_job(process)
            process.communicate(command, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                if os.name != "nt":
                    timeout_cleanup = _stop_posix_compile_supervisor(process)
                else:
                    timeout_cleanup = _terminate_compile_process_tree(
                        process, containment
                    )
                    try:
                        process.wait(timeout=1.0)
                    except BaseException:
                        timeout_cleanup = "FAIL"
            except BaseException:
                timeout_cleanup = "FAIL"
        except BaseException:
            try:
                if os.name != "nt":
                    _stop_posix_compile_supervisor(process)
                elif containment is not None:
                    _terminate_compile_process_tree(process, containment)
                else:
                    _terminate_compile_process_tree(process, None)
            except BaseException:
                # Preserve the interruption or caller exception; cleanup is
                # best-effort and the compile gate remains a hard failure.
                pass
            if status_read_fd is not None:
                supervisor_alive = False
                if os.name != "nt":
                    try:
                        supervisor_alive = process.poll() is None
                    except BaseException:
                        supervisor_alive = True
                if supervisor_alive:
                    try:
                        os.close(status_read_fd)
                    except OSError:
                        pass
                else:
                    cleanup_status = _read_posix_compile_status(
                        status_read_fd,
                        expected_command_exit=process.returncode,
                    )
                    if os.name != "nt" and cleanup_status != "PASS":
                        try:
                            _terminate_compile_process_tree(process, None)
                        except BaseException:
                            pass
                status_read_fd = None
            raise
        supervisor_cleanup = (
            _read_posix_compile_status(
                status_read_fd,
                expected_command_exit=process.returncode,
            )
            if os.name != "nt"
            else "PASS"
        )
        status_read_fd = None
        if os.name != "nt":
            process_containment = _posix_process_containment_label(
                supervisor_cleanup=supervisor_cleanup,
                return_code=process.returncode,
            )
        if timed_out and os.name == "nt":
            group_cleanup = timeout_cleanup
        else:
            group_cleanup = _terminate_compile_process_tree(
                process,
                containment,
            )
        descendant_cleanup = (
            "PASS"
            if supervisor_cleanup == "PASS"
            and group_cleanup == "PASS"
            and (not timed_out or timeout_cleanup == "PASS")
            else "FAIL"
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")
    status = "PASS" if not timed_out and process.returncode == 0 and descendant_cleanup == "PASS" else "FAIL"
    exit_code = 124 if timed_out else process.returncode
    if timed_out:
        stderr = (
            stderr
            + f"\ncompile check timed out after {timeout_seconds:g} seconds"
        ).strip()
    if descendant_cleanup != "PASS":
        stderr = (stderr + "\ncompile descendant cleanup failed").strip()
    return _compile_check_result(
        status=status,
        command=command,
        exit_code=exit_code,
        stdout=stdout[-8000:],
        stderr=stderr[-8000:],
        cwd=cwd,
        process_containment=process_containment,
        descendant_cleanup=descendant_cleanup,
        timed_out=timed_out,
        timeout_seconds=timeout_seconds,
    )


LEDGER_FIELDS = (
    "unit_id",
    "file_id",
    "heading_path",
    "part",
    "start_line",
    "end_line",
    "line_count",
    "scene",
    "scene_requested",
    "scene_document_prior",
    "scene_routing_decision",
    "scene_routing_policy_sha256",
    "scene_routing_policy_revision",
    "scene_routing_top_score",
    "scene_routing_margin",
    "voice_profile_id",
    "voice_profile_revision",
    "voice_profile_confidence",
    "voice_profile_kind",
    "voice_profile_source",
    "voice_profile_binding_scene",
    "voice_profile_sha256",
    "voice_default_disclosure",
    "chunk_binding_sha256",
    "mode",
    "intensity",
    "structural_plan_status",
    "structural_semantic_review_status",
    "paired_quality_review_status",
    "rewrite_intent_status",
    "transaction_id",
    "transaction_status",
    "owner_chunk",
    "context_before_unit",
    "context_after_unit",
    "author_chars",
    "protected_spans",
    "status",
    "hash_before",
    "hash_after",
    "diff_path",
    "protected_hashes_ok",
    "style_validation",
    "notes",
    "unresolved_codes_json",
)

INITIAL_UNIT_STATUSES = {
    "PENDING",
    "SKIPPED_PROTECTED",
    "UNRESOLVED",
    "SKIPPED_GARBLED",
    "CHANGED_AFTER_SNAPSHOT",
}


def _without_prepare_private_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Return the public initial-unit representation emitted by prepare."""
    return {
        key: value
        for key, value in row.items()
        if key not in {"masked_text", "read_only_context_before", "read_only_context_after"}
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rebuild_prepare_state(
    run_dir: Path,
    snapshot: dict[str, Any],
    file_manifest: Sequence[dict[str, str]],
    metadata: dict[str, Any],
    units: Sequence[dict[str, Any]],
    spans: Sequence[dict[str, Any]],
    voice_bindings: dict[str, dict[str, Any]],
    scene_policy_path: Path,
) -> None:
    """Reconstruct prepare output from frozen source copies before trusting any ledger state.

    The integrity manifest detects ordinary tampering. This independent rebuild also detects an
    attacker who edits both ``units.jsonl`` and the manifest: initial statuses, offsets, hashes,
    masks, and read-only context must still be derivable from the frozen source bytes.
    """
    budgets = metadata.get("budgets")
    if not isinstance(budgets, dict):
        raise ValueError("run_metadata.json has no prepare budgets")
    scene = str(metadata.get("scene", "AUTO")).upper()
    intensity = str(metadata.get("intensity", "")).upper()
    if intensity not in preparer.REWRITE_INTENSITIES:
        raise ValueError("run_metadata.json has invalid rewrite intensity")
    wrappers = frozenset(str(item) for item in metadata.get("editable_style_wrappers", []))
    expected_units: list[dict[str, Any]] = []
    expected_spans: list[dict[str, Any]] = []
    frozen_texts: dict[str, str] = {}
    spans_by_file: dict[str, list[dict[str, Any]]] = {}
    for record in file_manifest:
        snapshot_copy = str(record.get("snapshot_copy", ""))
        status = str(record.get("status", ""))
        if not snapshot_copy or status in {"UNRESOLVED", "UNRESOLVED_INCLUDE", "SKIPPED_GARBLED"}:
            continue
        copy_path = run_dir / snapshot_copy
        if not copy_path.is_file():
            raise ValueError(f"missing prepare source copy: {snapshot_copy}")
        raw = copy_path.read_bytes()
        if sha256(raw) != str(record.get("sha256", "")):
            raise ValueError(f"prepare source copy hash mismatch: {record.get('file_id', '')}")
        text = _decode(raw, str(record.get("encoding", "")))
        file_id = str(record.get("file_id", ""))
        frozen_texts[file_id] = text
    override_artifact = _load_json(run_dir / "source_role_overrides.json")
    expected_file_records = [dict(record) for record in file_manifest]
    preparer.assign_source_roles(
        expected_file_records,
        frozen_texts,
        override_artifact,
    )
    for actual, expected in zip(file_manifest, expected_file_records, strict=True):
        for field in (
            "source_role",
            "source_role_evidence",
            "source_processing_status",
        ):
            if str(actual.get(field, "")) != str(expected.get(field, "")):
                raise ValueError(
                    "initial prepare state mismatch: source-role manifest differs "
                    f"for {actual.get('file_id', '')}"
                )
    for record in expected_file_records:
        file_id = str(record.get("file_id", ""))
        text = frozen_texts.get(file_id)
        if text is None or not str(record.get("source_processing_status", "")).startswith(
            "AUTHORING_QUEUE"
        ):
            continue
        local_spans = preparer.protected_spans(
            text,
            str(record.get("suffix", "")),
            file_id,
            wrappers,
        )
        spans_by_file[file_id] = local_spans
        expected_spans.extend(local_spans)
    document_priors = preparer.build_logical_document_priors(
        expected_file_records,
        frozen_texts,
        spans_by_file,
        requested_scene=scene,
        scene_policy_path=scene_policy_path,
    )
    for record in expected_file_records:
        file_id = str(record.get("file_id", ""))
        text = frozen_texts.get(file_id)
        if text is None or not str(record.get("source_processing_status", "")).startswith(
            "AUTHORING_QUEUE"
        ):
            continue
        local_spans = spans_by_file[file_id]
        file_units = preparer.build_units(
            dict(record),
            text,
            local_spans,
            requested_scene=scene,
            voice_bindings=voice_bindings,
            scene_policy_path=scene_policy_path,
            document_prior_scene=document_priors.get(file_id, ""),
            intensity=intensity,
            max_author_chars=int(budgets.get("max_author_chars", 7000)),
            max_lines=int(budgets.get("max_lines", 600)),
            min_author_chars=int(budgets.get("min_author_chars", 1200)),
        )
        if str(record.get("changed_after_snapshot", "")).lower() == "true":
            for unit in file_units:
                unit["status"] = "CHANGED_AFTER_SNAPSHOT"
                unit["notes"] = (
                    (unit["notes"] + "; ") if unit.get("notes") else ""
                ) + "source_changed_after_snapshot"
        expected_units.extend(file_units)
    preparer.attach_read_only_context(expected_units)
    for unit in expected_units:
        unit["chunk_binding_sha256"] = preparer.materialize_chunk_payload(unit)[
            "chunk_binding_sha256"
        ]
    expected_public_units = [_without_prepare_private_fields(item) for item in expected_units]
    actual_public_units = [_without_prepare_private_fields(dict(item)) for item in units]
    if _canonical_json(actual_public_units) != _canonical_json(expected_public_units):
        raise ValueError("initial prepare state mismatch: units.jsonl does not match reconstructed source")
    if _canonical_json(list(spans)) != _canonical_json(expected_spans):
        raise ValueError("initial prepare state mismatch: protected_spans.jsonl does not match reconstructed source")

    ledger_path = run_dir / "coverage_ledger.csv"
    if not ledger_path.is_file():
        raise ValueError("missing coverage_ledger.csv")
    actual_ledger = _load_csv(ledger_path)
    ledger_fields = (
        "unit_id", "file_id", "heading_path", "part", "start_line", "end_line", "line_count",
        "scene", "scene_requested", "scene_document_prior", "scene_routing_decision", "scene_routing_policy_sha256",
        "scene_routing_policy_revision", "scene_routing_top_score", "scene_routing_margin",
        "voice_profile_id", "voice_profile_revision", "voice_profile_confidence",
        "voice_profile_kind", "voice_profile_source", "voice_profile_binding_scene",
        "voice_profile_sha256", "voice_default_disclosure", "chunk_binding_sha256",
        "mode", "intensity", "structural_plan_status", "owner_chunk", "context_before_unit", "context_after_unit",
        "author_chars", "protected_spans", "status", "hash_before", "hash_after", "diff_path",
        "protected_hashes_ok", "style_validation", "notes",
    )
    expected_ledger = [
        {field: str(item.get(field, "")) for field in ledger_fields}
        for item in expected_public_units
    ]
    actual_ledger_normalized = [
        {field: item.get(field, "") for field in ledger_fields}
        for item in actual_ledger
    ]
    if _canonical_json(actual_ledger_normalized) != _canonical_json(expected_ledger):
        raise ValueError("initial prepare state mismatch: coverage_ledger.csv does not match reconstructed source")

    expected_snapshot_files = snapshot.get("files")
    manifest_projection = [
        {
            key: (
                int(record.get(key, "0") or 0)
                if key in {"bytes", "readable_bytes"}
                else str(record.get(key, "")).lower() == "true"
                if key == "changed_after_snapshot"
                else record.get(key, "")
            )
            for key in (
                "file_id", "path", "parent_file_id", "relation", "suffix", "bytes", "readable_bytes", "encoding", "sha256", "modified_at",
                "changed_after_snapshot", "snapshot_copy", "status", "reason",
                "source_role", "source_role_evidence", "source_processing_status",
            )
        }
        for record in file_manifest
    ]
    if _canonical_json(expected_snapshot_files) != _canonical_json(manifest_projection):
        raise ValueError("initial prepare state mismatch: snapshot and file manifest disagree")

    # Chunks carry the masked text and adjacent read-only context used by the validator.
    for expected in expected_units:
        unit_id = str(expected["unit_id"])
        chunk_path = run_dir / "chunks" / f"{unit_id}.json"
        if not chunk_path.is_file():
            raise ValueError(f"missing prepare chunk: {unit_id}")
        expected_chunk = {
            key: value
            for key, value in expected.items()
            if key not in {"masked_text", "read_only_context_before", "read_only_context_after"}
        }
        expected_chunk["masked_text"] = expected["masked_text"]
        expected_chunk["read_only_context_before"] = expected["read_only_context_before"]
        expected_chunk["read_only_context_after"] = expected["read_only_context_after"]
        actual_chunk = _load_json(chunk_path)
        if _canonical_json(actual_chunk) != _canonical_json(expected_chunk):
            raise ValueError(f"initial prepare state mismatch: chunk {unit_id} differs from reconstructed source")


def _validate_initial_unit_states(units: Sequence[dict[str, Any]]) -> None:
    """Reject terminal status injection before any rewrite is considered."""
    seen: set[str] = set()
    for unit in units:
        unit_id = str(unit.get("unit_id", ""))
        if not unit_id or unit_id in seen:
            raise ValueError("invalid or duplicate initial unit_id")
        seen.add(unit_id)
        status = str(unit.get("status", ""))
        if status not in INITIAL_UNIT_STATUSES:
            raise ValueError(f"invalid initial unit status for {unit_id}: {status}")
        if status == "PENDING" and str(unit.get("hash_after", "")):
            raise ValueError(f"initial PENDING unit has hash_after: {unit_id}")


def _public_chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    """Return the prepare-time unit record embedded in an immutable chunk."""
    return {
        key: value
        for key, value in chunk.items()
        if key not in {"masked_text", "read_only_context_before", "read_only_context_after"}
    }


def _visible_author_chars(masked_text: str, suffix: str) -> int:
    visible = PLACEHOLDER_RE.sub("", masked_text)
    if suffix.lower() in {".tex", ".ltx"}:
        visible = TEX_COMMAND_TOKEN_RE.sub("", visible)
        visible = re.sub(r"[{}\[\]$&_^~]", " ", visible)
    else:
        visible = re.sub(r"[#>*_`|~-]", " ", visible)
    return len(HAN_RE.findall(visible))


def _validate_units_against_chunks(
    units: Sequence[dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    file_texts: dict[str, str],
    file_suffixes: dict[str, str],
    span_map: dict[str, dict[str, Any]],
) -> None:
    """Rebuild the initial unit identity instead of trusting a mutable ledger.

    ``prepare_integrity.json`` is deliberately treated as an audit aid, not as
    an independent trust anchor.  The chunk payloads are the canonical
    prepare-time records; each one is also checked against the frozen source
    substring and protected-span restoration.  A forged ``units.jsonl`` row
    therefore cannot turn editable content into a terminal state, even when a
    caller also rewrites the integrity manifest.
    """
    unit_ids = {str(item.get("unit_id", "")) for item in units}
    chunk_ids = set(chunks)
    if unit_ids != chunk_ids:
        raise ValueError("units.jsonl does not match canonical chunk set")

    for unit in units:
        unit_id = str(unit["unit_id"])
        chunk = chunks[unit_id]
        canonical = _public_chunk_payload(chunk)
        if unit != canonical:
            raise ValueError(f"units.jsonl does not match canonical chunk: {unit_id}")
        binding_hash = chunk.get("chunk_binding_sha256")
        if (
            not isinstance(binding_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", binding_hash)
            or binding_hash != preparer.chunk_binding_sha256(chunk)
        ):
            raise ValueError(f"canonical chunk binding hash mismatch: {unit_id}")

        status = str(chunk.get("status", ""))
        if status not in INITIAL_UNIT_STATUSES:
            raise ValueError(f"invalid canonical chunk status for {unit_id}: {status}")
        if str(chunk.get("hash_after", "")):
            raise ValueError(f"canonical initial chunk has hash_after: {unit_id}")

        file_id = str(chunk.get("file_id", ""))
        source_text = file_texts.get(file_id)
        if source_text is None:
            raise ValueError(f"canonical chunk references unavailable file: {unit_id}")
        try:
            start = int(chunk["start"])
            end = int(chunk["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"invalid canonical chunk range: {unit_id}") from error
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError(f"invalid canonical chunk range: {unit_id}")
        original = source_text[start:end]
        if sha256(original.encode("utf-8")) != str(chunk.get("hash_before", "")):
            raise ValueError(f"canonical chunk hash_before mismatch: {unit_id}")

        masked_text = chunk.get("masked_text")
        protected_ids = chunk.get("protected_ids", [])
        if not isinstance(masked_text, str) or not isinstance(protected_ids, list):
            raise ValueError(f"invalid canonical chunk payload: {unit_id}")
        restored, restore_errors = restore_protected(masked_text, protected_ids, span_map)
        if restore_errors or restored != original:
            detail = ",".join(restore_errors) or "restored_text_mismatch"
            raise ValueError(f"canonical chunk source mismatch: {unit_id}:{detail}")

        derived_author_chars = _visible_author_chars(
            masked_text,
            file_suffixes.get(file_id, ""),
        )
        try:
            declared_author_chars = int(chunk.get("author_chars", -1))
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid canonical author_chars: {unit_id}") from error
        if declared_author_chars != derived_author_chars:
            raise ValueError(f"canonical author_chars mismatch: {unit_id}")
        if status == "SKIPPED_PROTECTED" and derived_author_chars != 0:
            raise ValueError(f"SKIPPED_PROTECTED has editable content: {unit_id}")
        if status == "PENDING" and derived_author_chars == 0:
            raise ValueError(f"PENDING has no editable content: {unit_id}")


def _validate_prepare_metadata_derivations(
    run_dir: Path,
    metadata: dict[str, Any],
    snapshot: dict[str, Any],
    file_manifest: Sequence[dict[str, str]],
    units: Sequence[dict[str, Any]],
    spans: Sequence[dict[str, Any]],
    transaction_inventory: dict[str, Any] | None,
) -> None:
    expected_fields = {
        "tool",
        "created_at",
        "snapshot_id",
        "status",
        "scene",
        "intensity",
        "voice_binding",
        "scene_routing_status",
        "scene_routing_policy_sha256",
        "scene_routing_policy_revision",
        "scene_routing_summary",
        "budgets",
        "editable_style_wrappers",
        "files_total",
        "units_total",
        "protected_spans_total",
        "file_statuses",
        "source_role_summary",
        "source_processing_status_summary",
        "source_role_override_status",
        "source_role_overrides",
        "source_role_overrides_sha256",
        "unit_statuses",
        "processable_editable_units",
        "no_editable_scope",
        "completion_claim_allowed",
        "next_action",
        "integrity_manifest",
        "policy_snapshot",
        "policy_snapshot_sha256",
    }
    if transaction_inventory is not None:
        expected_fields.update(
            {
                "structural_transaction_scope",
                "structural_transaction_candidates",
                "structural_transaction_inventory",
                "structural_transaction_inventory_sha256",
                "structural_transaction_policy_revision",
                "structural_transaction_policy_sha256",
            }
        )
    if set(metadata) != expected_fields:
        raise ValueError("run metadata fields mismatch")
    preparer.validate_policy_snapshot(
        metadata.get("policy_snapshot"),
        metadata.get("policy_snapshot_sha256"),
    )
    if metadata.get("tool") != "prepare_humanize_long_document.py":
        raise ValueError("run metadata tool mismatch")
    created_at = metadata.get("created_at")
    if not isinstance(created_at, str):
        raise ValueError("run metadata created_at is invalid")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("run metadata created_at is invalid") from error
    if metadata.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise ValueError("run metadata snapshot binding mismatch")
    intensity = str(metadata.get("intensity", "")).upper()
    if intensity not in preparer.REWRITE_INTENSITIES:
        raise ValueError("run metadata intensity is invalid")
    if any(str(unit.get("intensity", "")).upper() != intensity for unit in units):
        raise ValueError("run metadata intensity does not match units")

    budgets = metadata.get("budgets")
    if not isinstance(budgets, dict) or set(budgets) != {
        "max_author_chars",
        "max_lines",
        "min_author_chars",
    }:
        raise ValueError("run metadata budgets mismatch")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in budgets.values()
    ):
        raise ValueError("run metadata budgets are invalid")
    wrappers = metadata.get("editable_style_wrappers")
    if (
        not isinstance(wrappers, list)
        or wrappers != sorted(set(wrappers))
        or any(item not in preparer.EDITABLE_STYLE_WRAPPERS for item in wrappers)
    ):
        raise ValueError("run metadata editable wrappers mismatch")

    if metadata.get("source_role_overrides") != "source_role_overrides.json":
        raise ValueError("run metadata source-role override artifact mismatch")
    override_path = run_dir / "source_role_overrides.json"
    override_artifact = _load_json(override_path)
    preparer.validate_source_role_override_artifact(override_artifact)
    override_status = "APPLIED" if override_artifact["overrides"] else "NOT_SUPPLIED"
    override_sha256 = sha256(override_path.read_bytes())

    file_statuses = Counter(str(record.get("status", "")) for record in file_manifest)
    source_roles = Counter(str(record.get("source_role", "")) for record in file_manifest)
    source_processing_statuses = Counter(
        str(record.get("source_processing_status", "")) for record in file_manifest
    )
    unit_statuses = Counter(str(unit.get("status", "")) for unit in units)
    routing_decisions = Counter(
        str(unit.get("scene_routing_decision", ""))
        for unit in units
        if int(unit.get("author_chars", 0)) > 0
    )
    if not routing_decisions:
        scene_routing_status = "NOT_EVALUATED"
    elif routing_decisions.get("AMBIGUOUS"):
        scene_routing_status = "REVIEW"
    else:
        scene_routing_status = "PASS"
    processable = unit_statuses.get("PENDING", 0)
    run_status = (
        "REVIEW"
        if any(
            status in unit_statuses
            for status in ("UNRESOLVED", "SKIPPED_GARBLED", "CHANGED_AFTER_SNAPSHOT")
        )
        or any(
            status in file_statuses
            for status in (
                "UNRESOLVED",
                "UNRESOLVED_INCLUDE",
                "SKIPPED_GARBLED",
                "CHANGED_AFTER_SNAPSHOT",
            )
        )
        or source_roles.get("UNRESOLVED", 0) > 0
        or processable == 0
        else "READY"
    )
    expected_values = {
        "status": run_status,
        "scene_routing_status": scene_routing_status,
        "scene_routing_summary": dict(sorted(routing_decisions.items())),
        "files_total": len(file_manifest),
        "units_total": len(units),
        "protected_spans_total": len(spans),
        "file_statuses": dict(sorted(file_statuses.items())),
        "source_role_summary": dict(sorted(source_roles.items())),
        "source_processing_status_summary": dict(
            sorted(source_processing_statuses.items())
        ),
        "source_role_override_status": (
            override_status
        ),
        "source_role_overrides": "source_role_overrides.json",
        "source_role_overrides_sha256": override_sha256,
        "unit_statuses": dict(sorted(unit_statuses.items())),
        "processable_editable_units": processable,
        "no_editable_scope": processable == 0,
        "completion_claim_allowed": False,
        "next_action": (
            "No editable author-text units were found; review protected/garbled/unresolved "
            "scope and do not start authoring."
            if processable == 0
            else "Rewrite only PENDING chunk files, then validate and finalize them."
        ),
        "integrity_manifest": "prepare_integrity.json",
    }
    if transaction_inventory is not None:
        expected_values.update(
            {
                "structural_transaction_scope": transaction_inventory[
                    "candidate_scope"
                ],
                "structural_transaction_candidates": len(
                    transaction_inventory["transactions"]
                ),
                "structural_transaction_inventory": (
                    "structural_transaction_inventory.json"
                ),
                "structural_transaction_inventory_sha256": transaction_inventory[
                    "inventory_sha256"
                ],
                "structural_transaction_policy_revision": transaction_inventory[
                    "eligibility_policy_revision"
                ],
                "structural_transaction_policy_sha256": transaction_inventory[
                    "eligibility_policy_sha256"
                ],
            }
        )
    mismatches = [
        key for key, expected in expected_values.items() if metadata.get(key) != expected
    ]
    if mismatches:
        raise ValueError(
            "run metadata derived fields mismatch: " + ",".join(sorted(mismatches))
        )


def _long_authoring_route_reason(status: str) -> str:
    reasons = {
        "EXPLICIT": "USER_EXPLICIT_SCENE",
        "ROUTED": "AUTO_UNIQUE_SCORE_ABOVE_THRESHOLD",
        "ROUTED_DOCUMENT_PRIOR": "AUTO_DOCUMENT_PRIOR_WITH_LOCAL_SUPPORT",
        "FALLBACK_GENERAL": "AUTO_INSUFFICIENT_SCENE_EVIDENCE",
    }
    try:
        return reasons[status]
    except KeyError as error:
        raise ValueError("long authoring route is not eligible") from error


def _stable_live_file_sha256(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", "MISSING"
    if _is_link_or_reparse(path):
        return "", "LINK_OR_REPARSE"
    if not path.is_file():
        return "", "NOT_FILE"
    before = path.stat(follow_symlinks=False)
    if before.st_nlink != 1:
        return "", "HARDLINK"
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError:
        return "", "UNREADABLE"
    after = path.stat(follow_symlinks=False)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        return "", "CHANGED_DURING_READ"
    return digest.hexdigest(), "MATCH"


def _long_authoring_live_source_changes(
    file_manifest: Sequence[dict[str, Any]],
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for record in file_manifest:
        snapshot_sha256 = str(record.get("sha256", ""))
        if not snapshot_sha256:
            continue
        current_sha256, state = _stable_live_file_sha256(Path(str(record.get("path", ""))))
        if state == "MATCH" and current_sha256 == snapshot_sha256:
            continue
        changes.append(
            {
                "file_id": str(record.get("file_id", "")),
                "snapshot_sha256": snapshot_sha256,
                "current_sha256": current_sha256,
                "current_state": "MODIFIED" if state == "MATCH" else state,
            }
        )
    return changes


def build_long_authoring_binding(
    run_dir: Path,
    snapshot: dict[str, Any],
    run_metadata: dict[str, Any],
    file_by_id: dict[str, dict[str, Any]],
    unit: dict[str, Any],
    chunk: dict[str, Any],
) -> dict[str, Any]:
    file_id = str(unit.get("file_id", ""))
    file_record = file_by_id.get(file_id)
    if file_record is None:
        raise ValueError("long authoring unit has no source file binding")
    route_status = str(unit.get("scene_routing_decision", ""))
    authoring_allowed = str(unit.get("status", "")) == "PENDING" and route_status != "AMBIGUOUS"
    binding: dict[str, Any] = {
        "schema_version": LONG_AUTHORING_BINDING_SCHEMA,
        "integrity_scope": "CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY",
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "prepare_integrity_sha256": sha256(
            (run_dir / "prepare_integrity.json").read_bytes()
        ),
        "run_metadata_sha256": sha256((run_dir / "run_metadata.json").read_bytes()),
        "policy_snapshot_sha256": str(run_metadata.get("policy_snapshot_sha256", "")),
        "source_binding": {
            "file_id": file_id,
            "source_file_sha256": str(file_record.get("sha256", "")),
            "unit_id": str(unit.get("unit_id", "")),
            "offset_unit": "PYTHON_UNICODE_CODEPOINT_INDEX",
            "start": int(unit.get("start", 0)),
            "end": int(unit.get("end", 0)),
            "start_line": int(unit.get("start_line", 0)),
            "end_line": int(unit.get("end_line", 0)),
            "source_span_sha256": str(unit.get("hash_before", "")),
            "masked_text_sha256": sha256(str(chunk.get("masked_text", "")).encode("utf-8")),
            "chunk_binding_sha256": str(unit.get("chunk_binding_sha256", "")),
        },
        "scene_route": {
            "requested_scene": str(unit.get("scene_requested", "")),
            "resolved_scene": str(unit.get("scene", "")),
            "status": route_status,
            "reason_code": _long_authoring_route_reason(route_status),
            "document_prior_scene": str(unit.get("scene_document_prior", "")),
            "scores": dict(unit.get("scene_routing_scores", {})),
            "top_score": int(unit.get("scene_routing_top_score", 0)),
            "margin": int(unit.get("scene_routing_margin", 0)),
            "ambiguous_scenes": list(unit.get("scene_routing_ambiguous_scenes", [])),
            "evidence": list(unit.get("scene_routing_evidence", [])),
            "policy_sha256": str(unit.get("scene_routing_policy_sha256", "")),
            "policy_revision": int(unit.get("scene_routing_policy_revision", 0)),
            "heading_path_sha256": sha256(
                str(unit.get("heading_path", "")).encode("utf-8")
            ),
            "routing_input_sha256": sha256(
                _canonical_json(
                    {
                        "heading_path": str(unit.get("heading_path", "")),
                        "masked_text": str(chunk.get("masked_text", "")),
                    }
                ).encode("utf-8")
            ),
        },
        "voice_binding": {
            "profile_id": str(unit.get("voice_profile_id", "")),
            "profile_revision": int(unit.get("voice_profile_revision", 0)),
            "profile_kind": str(unit.get("voice_profile_kind", "")),
            "binding_scene": str(unit.get("voice_profile_binding_scene", "")),
            "profile_sha256": str(unit.get("voice_profile_sha256", "")),
        },
        "mode": str(unit.get("mode", "")),
        "intensity": str(unit.get("intensity", "")),
        "authoring_allowed": authoring_allowed,
        "completion_claim_allowed": False,
        "humanize_quality_claim_allowed": False,
    }
    binding["authoring_binding_sha256"] = sha256(
        _canonical_json(binding).encode("utf-8")
    )
    _validate_long_authoring_binding_shape(binding)
    return binding


def _validate_long_authoring_binding(
    recorded: Any,
    expected: dict[str, Any],
) -> None:
    _validate_long_authoring_binding_shape(recorded)
    if _canonical_json(recorded) != _canonical_json(expected):
        raise ValueError("long_authoring_binding_drift")


def _long_authoring_preflight_summary(
    *,
    status: str,
    run_dir: Path,
    snapshot: dict[str, Any],
    run_metadata: dict[str, Any],
    run_state_sha256: str,
    pending_units_total: int,
    eligible_units_total: int,
    source_changes: Sequence[dict[str, str]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema_version": LONG_AUTHORING_PREFLIGHT_SCHEMA,
        "status": status,
        "integrity_status": "PASS",
        "policy_status": "PASS",
        "route_replay_status": "PASS",
        "voice_binding_status": "PASS",
        "live_source_status": "MATCH" if not source_changes else "NOT_CURRENT",
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "run_state_sha256": run_state_sha256,
        "prepare_integrity_sha256": sha256(
            (run_dir / "prepare_integrity.json").read_bytes()
        ),
        "run_metadata_sha256": sha256((run_dir / "run_metadata.json").read_bytes()),
        "policy_snapshot_sha256": str(run_metadata.get("policy_snapshot_sha256", "")),
        "scene_routing_policy_sha256": str(
            run_metadata.get("scene_routing_policy_sha256", "")
        ),
        "pending_units_total": pending_units_total,
        "eligible_units_total": eligible_units_total,
        "source_change_units": [dict(item) for item in source_changes],
        "completion_claim_allowed": False,
    }
    summary["preflight_sha256"] = sha256(_canonical_json(summary).encode("utf-8"))
    return summary


def validate_long_authoring_snapshot(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve(strict=True)
    if not run_dir.is_dir():
        raise ValueError("run_dir must be a directory")
    _validate_transaction_source_tree(run_dir)
    state_before = _run_state_hashes(run_dir)
    _verify_prepare_integrity(run_dir)
    prepare_integrity = _load_json(run_dir / "prepare_integrity.json")
    if prepare_integrity.get("schema_version") != (
        preparer.PREPARE_INTEGRITY_SCHEMA_VERSION
    ):
        raise ValueError(
            "legacy prepare integrity requires a new prepare run for v5 authoring"
        )
    snapshot = _load_json(run_dir / "snapshot.json")
    file_manifest = _load_csv(run_dir / "file_manifest.csv")
    units = _load_jsonl(run_dir / "units.jsonl")
    spans = _load_jsonl(run_dir / "protected_spans.jsonl")
    run_metadata = _load_json(run_dir / "run_metadata.json")
    preparer.validate_policy_snapshot(
        run_metadata.get("policy_snapshot"),
        run_metadata.get("policy_snapshot_sha256"),
    )
    scene_policy_path = _validate_scene_routing_policy(run_dir, run_metadata)
    _profiles, voice_bindings, _voice_identity = _validate_voice_profile_binding(
        run_dir, run_metadata, units
    )
    _rebuild_prepare_state(
        run_dir,
        snapshot,
        file_manifest,
        run_metadata,
        units,
        spans,
        voice_bindings,
        scene_policy_path,
    )
    _validate_initial_unit_states(units)
    transaction_inventory = _validate_structural_transaction_inventory(
        run_dir,
        run_metadata,
        snapshot,
        file_manifest,
        units,
    )
    _validate_prepare_metadata_derivations(
        run_dir,
        run_metadata,
        snapshot,
        file_manifest,
        units,
        spans,
        transaction_inventory,
    )
    file_by_id = {str(item.get("file_id", "")): dict(item) for item in file_manifest}
    chunks: dict[str, dict[str, Any]] = {}
    bindings: dict[str, dict[str, Any]] = {}
    pending_units = [item for item in units if str(item.get("status", "")) == "PENDING"]
    for unit in pending_units:
        unit_id = str(unit.get("unit_id", ""))
        chunk = _load_json(run_dir / "chunks" / f"{unit_id}.json")
        if not isinstance(chunk, dict) or chunk.get("unit_id") != unit_id:
            raise ValueError(f"invalid chunk payload for {unit_id}")
        chunks[unit_id] = chunk
        binding = build_long_authoring_binding(
            run_dir,
            snapshot,
            run_metadata,
            file_by_id,
            unit,
            chunk,
        )
        if binding["authoring_allowed"] is not True:
            raise ValueError(f"pending unit is not authoring eligible: {unit_id}")
        bindings[unit_id] = binding
    source_changes_before = _long_authoring_live_source_changes(file_manifest)
    state_after = _run_state_hashes(run_dir)
    source_changes_after = _long_authoring_live_source_changes(file_manifest)
    if state_before != state_after:
        raise ValueError("run state changed during authoring preflight")
    if source_changes_before != source_changes_after:
        raise ValueError("live source state changed during authoring preflight")
    source_changes = source_changes_after
    status = "PASS" if not source_changes and pending_units else "REVIEW"
    run_state_sha256 = sha256(
        _canonical_json(_immutable_prepare_state_hashes(run_dir)).encode("utf-8")
    )
    summary = _long_authoring_preflight_summary(
        status=status,
        run_dir=run_dir,
        snapshot=snapshot,
        run_metadata=run_metadata,
        run_state_sha256=run_state_sha256,
        pending_units_total=len(pending_units),
        eligible_units_total=len(bindings),
        source_changes=source_changes,
    )
    return {
        "summary": summary,
        "bindings": bindings,
        "chunks": chunks,
    }


def _finalize_locked(
    run_dir: Path,
    rewrites_dir: Path,
    *,
    check_command: str | None = None,
    check_timeout_seconds: float = DEFAULT_COMPILE_CHECK_TIMEOUT_SECONDS,
    second_pass_receipt: Path | None = None,
) -> dict[str, Any]:
    validated_check_timeout = _validated_compile_timeout_seconds(check_timeout_seconds)
    result_timeout_seconds = validated_check_timeout if check_command else None
    _verify_prepare_integrity(run_dir)
    snapshot = _load_json(run_dir / "snapshot.json")
    file_manifest = _load_csv(run_dir / "file_manifest.csv")
    units = _load_jsonl(run_dir / "units.jsonl")
    spans = _load_jsonl(run_dir / "protected_spans.jsonl")
    run_metadata = _load_json(run_dir / "run_metadata.json")
    preparer.validate_policy_snapshot(
        run_metadata.get("policy_snapshot"),
        run_metadata.get("policy_snapshot_sha256"),
    )
    scene_policy_path = _validate_scene_routing_policy(run_dir, run_metadata)
    frozen_voice_profiles, voice_bindings, voice_identity = _validate_voice_profile_binding(
        run_dir, run_metadata, units
    )
    _rebuild_prepare_state(
        run_dir,
        snapshot,
        file_manifest,
        run_metadata,
        units,
        spans,
        voice_bindings,
        scene_policy_path,
    )
    _validate_initial_unit_states(units)
    transaction_inventory = _validate_structural_transaction_inventory(
        run_dir,
        run_metadata,
        snapshot,
        file_manifest,
        units,
    )
    _validate_prepare_metadata_derivations(
        run_dir,
        run_metadata,
        snapshot,
        file_manifest,
        units,
        spans,
        transaction_inventory,
    )
    span_map = {item["protected_id"]: item for item in spans}
    unit_map = {item["unit_id"]: item for item in units}
    document_id_by_file = _logical_document_ids(file_manifest)
    file_by_id = {
        str(item.get("file_id", "")): dict(item) for item in file_manifest
    }
    chunks: dict[str, dict[str, Any]] = {}
    for unit_id in unit_map:
        chunk = _load_json(run_dir / "chunks" / f"{unit_id}.json")
        if not isinstance(chunk, dict) or chunk.get("unit_id") != unit_id:
            raise ValueError(f"invalid chunk payload for {unit_id}")
        chunks[unit_id] = chunk
    rewrites, transaction_bundles, transaction_declines = collect_rewrites(
        rewrites_dir,
        run_dir=run_dir,
    )
    unknown_units = sorted(set(rewrites) - set(unit_map))
    if unknown_units:
        raise ValueError("unknown rewrite units: " + ",".join(unknown_units))
    transaction_decision_conflicts = sorted(
        set(transaction_bundles) & set(transaction_declines)
    )
    if transaction_decision_conflicts:
        raise ValueError(
            "structural transaction execution and decline conflict: "
            + ",".join(transaction_decision_conflicts)
        )
    bound_transaction_declines: dict[str, dict[str, Any]] = {}
    for transaction_id, bundle in transaction_declines.items():
        candidate = _bound_structural_transaction_decline_candidate(
            bundle, transaction_inventory, unit_map, chunks
        )
        unit_ids = [str(item["unit_id"]) for item in bundle["unit_bindings"]]
        bound_transaction_declines[transaction_id] = {
            "schema_version": STRUCTURAL_TRANSACTION_DECLINE_SCHEMA,
            "status": "PASS",
            "disposition": "DECLINED",
            "transaction_id": transaction_id,
            "transaction_binding_sha256": candidate[
                "transaction_binding_sha256"
            ],
            "transaction_inventory_sha256": bundle[
                "transaction_inventory_sha256"
            ],
            "unit_ids": unit_ids,
            "bundle_sha256": _structural_transaction_bundle_sha256(bundle),
            "reason_code": bundle["reason_code"],
            "reason": bundle["reason"],
            "evidence_refs": bundle["evidence_refs"],
            "evidence_member_coverage": "PASS",
            "path": str(
                Path("validation") / f"{transaction_id}.decline.json"
            ).replace("\\", "/"),
        }
    unit_to_transaction: dict[str, str] = {}
    for transaction_id, bundle in transaction_bundles.items():
        participant_ids = _structural_transaction_unit_ids(bundle)
        unknown_participants = sorted(set(participant_ids) - set(unit_map))
        if unknown_participants:
            raise ValueError(
                "unknown structural transaction units: "
                + ",".join(unknown_participants)
            )
        overlap = sorted(set(participant_ids) & set(rewrites))
        if overlap:
            raise ValueError(
                "structural transaction member also has standalone rewrite: "
                + ",".join(overlap)
            )
        for unit_id in participant_ids:
            existing = unit_to_transaction.get(unit_id)
            if existing is not None:
                raise ValueError(
                    "structural transaction member claimed twice: "
                    f"{unit_id}:{existing},{transaction_id}"
                )
            unit_to_transaction[unit_id] = transaction_id

    validation_dir = run_dir / ".validation_staging"
    diffs_dir = run_dir / ".diffs_staging"
    staging_dir = run_dir / ".rendered_staging"
    for temporary in (validation_dir, diffs_dir, staging_dir):
        if temporary.exists():
            shutil.rmtree(temporary)
    validation_dir.mkdir()
    diffs_dir.mkdir()
    staging_dir.mkdir()
    for transaction_id, decline_record in sorted(
        bound_transaction_declines.items()
    ):
        _write_json(
            validation_dir / f"{transaction_id}.decline.json", decline_record
        )

    existing_rendered_before = (run_dir / "rendered").is_dir()
    existing_partial_before = (run_dir / "rendered_partial").is_dir()
    existing_review_before = (run_dir / "rendered_review").is_dir()
    previous_accepted_units: set[str] = set()
    previous_ledger_path = run_dir / "coverage_ledger.final.csv"
    previous_partial_state_missing = (
        existing_partial_before or existing_review_before
    ) and not previous_ledger_path.is_file()
    if (existing_partial_before or existing_review_before) and previous_ledger_path.is_file():
        previous_accepted_units = _load_previous_accepted_units(previous_ledger_path)

    file_texts: dict[str, str] = {}
    file_raw: dict[str, bytes] = {}
    file_encoding: dict[str, str] = {}
    file_suffixes: dict[str, str] = {
        str(record["file_id"]): str(record.get("suffix", ""))
        for record in file_manifest
    }
    for record in file_manifest:
        if not record["snapshot_copy"] or record["status"] in {
            "UNRESOLVED",
            "UNRESOLVED_INCLUDE",
            "SKIPPED_GARBLED",
        }:
            continue
        raw = (run_dir / record["snapshot_copy"]).read_bytes()
        if sha256(raw) != record["sha256"]:
            raise ValueError(f"snapshot copy hash mismatch: {record['file_id']}")
        file_raw[record["file_id"]] = raw
        file_encoding[record["file_id"]] = record["encoding"]
        file_texts[record["file_id"]] = _decode(raw, record["encoding"])

    _validate_units_against_chunks(
        units,
        chunks,
        file_texts,
        file_suffixes,
        span_map,
    )
    # Keep the immutable prepare artifacts byte-equivalent until their
    # canonical chunk/source binding has been verified.  Structured runtime
    # diagnostics belong to the final ledger, not to the prepare authority.
    for unit in units:
        if str(unit.get("status", "")) == "UNRESOLVED":
            _add_unresolved_code(unit, "PREPARE_UNRESOLVED")
    expected_voice_units = {
        unit_id for unit_id, chunk in chunks.items() if str(chunk.get("status")) == "PENDING"
    }
    initial_processable_editable_units = len(expected_voice_units)
    voice_hash_matched_units: set[str] = set()
    voice_hash_missing_units: set[str] = set()
    voice_hash_mismatched_units: set[str] = set()
    chunk_binding_matched_units: set[str] = set()
    chunk_binding_missing_units: set[str] = set()
    chunk_binding_mismatched_units: set[str] = set()
    authoring_binding_matched_units: set[str] = set()
    authoring_binding_missing_units: set[str] = set()
    authoring_binding_mismatched_units: set[str] = set()

    accepted_by_file: dict[str, list[tuple[int, int, str, str]]] = {}
    invariant_baseline_by_file: dict[str, list[tuple[int, int, str, str]]] = {}
    validation_payloads: dict[str, dict[str, Any]] = {}
    structural_plan_payloads: dict[str, dict[str, Any]] = {}
    structural_semantic_review_requests: dict[str, dict[str, Any]] = {}
    paired_quality_review_requests: dict[str, dict[str, Any]] = {}
    rewrite_intent_evidence_records: dict[str, dict[str, Any]] = {}
    accepted_masked_by_unit: dict[str, str] = {}
    structural_transaction_results: dict[str, dict[str, Any]] = {}
    structural_transaction_review_requests: dict[str, dict[str, Any]] = {}
    bound_transaction_execution_ids: set[str] = set()
    for transaction_id, bundle in transaction_bundles.items():
        participant_ids = [str(item["unit_id"]) for item in bundle["unit_bindings"]]
        bundle_sha256 = _structural_transaction_bundle_sha256(bundle)
        try:
            candidate = _bound_structural_transaction_candidate(
                bundle, transaction_inventory, unit_map
            )
        except ValueError as error:
            transaction_result = {
                "transaction_id": transaction_id,
                "bundle_sha256": bundle_sha256,
                "unit_ids": participant_ids,
                "status": "REVIEW",
                "atomic_gate_status": "ROLLED_BACK",
                "source_member_claim_status": "NOT_RUN",
                "source_member_claim_sha256": "",
                "fragment_gate_statuses": {
                    unit_id: "NOT_RUN" for unit_id in participant_ids
                },
                "document_gate_status": "NOT_RUN",
                "change_applied": False,
                "cross_unit_moves_applied": 0,
                "rollback_reason": "AUTHORITY_BINDING",
                "errors": [str(error)],
                "review_request": {},
            }
        else:
            bound_transaction_execution_ids.add(transaction_id)
            chunk_binding_matched_units.update(participant_ids)
            voice_hash_matched_units.update(participant_ids)
            transaction_result = _validate_structural_transaction(
                bundle=bundle,
                candidate=candidate,
                snapshot_id=str(snapshot["snapshot_id"]),
                unit_map=unit_map,
                chunks=chunks,
                file_texts=file_texts,
                file_suffixes=file_suffixes,
                span_map=span_map,
                validation_dir=validation_dir,
                editable_style_wrappers=run_metadata["editable_style_wrappers"],
            )

        fragment_results = transaction_result.pop("_fragment_results", {})
        document_gate = transaction_result.pop("_document_gate", None)
        review_request = transaction_result.pop("_review_request", None)
        if document_gate is not None:
            _write_json(
                validation_dir / f"{transaction_id}.document-gate.json",
                document_gate,
            )
        if transaction_result["atomic_gate_status"] == "PASS":
            if not isinstance(review_request, dict):
                raise ValueError(
                    "structural transaction PASS without semantic review request"
                )
            request_name = (
                f"{transaction_id}.structural-transaction-review-request.json"
            )
            _write_json(validation_dir / request_name, review_request)
            request_record = {
                "status": "PENDING_EXTERNAL_REVIEW",
                "path": str(Path("validation") / request_name).replace("\\", "/"),
                "request_sha256": review_request["request_sha256"],
            }
            transaction_result["review_request"] = request_record
            structural_transaction_review_requests[transaction_id] = request_record
            for unit_id in participant_ids:
                unit = unit_map[unit_id]
                fragment_result = fragment_results[unit_id]
                transaction_fragment = next(
                    item
                    for item in bundle["fragments"]
                    if item["target_unit_id"] == unit_id
                )
                accepted_masked_by_unit[unit_id] = str(
                    transaction_fragment["masked_text"]
                )
                plan_payload = dict(fragment_result["plan_check_public"])
                plan_payload.update(
                    {
                        "status": "PASS",
                        "change_applied": True,
                        "transaction_id": transaction_id,
                        "transaction_atomic_gate_status": "PASS",
                        "semantic_mapping": "NOT_EVALUATED",
                        "semantic_review_status": "PENDING_EXTERNAL_REVIEW",
                        "semantic_review": request_record,
                    }
                )
                structural_plan_payloads[unit_id] = plan_payload
                _write_json(
                    validation_dir / f"{unit_id}.structural.json", plan_payload
                )
                validation_payloads[unit_id] = fragment_result[
                    "validation_payload"
                ]
                paired_quality_request = fragment_result.get(
                    "paired_quality_review_request"
                )
                if isinstance(paired_quality_request, dict):
                    paired_quality_review_requests[unit_id] = (
                        paired_quality_request
                    )
                structural_semantic_review_requests[unit_id] = request_record
                unit["status"] = "DONE"
                unit["structural_plan_status"] = "PASS"
                unit["structural_semantic_review_status"] = (
                    "PENDING_EXTERNAL_REVIEW"
                )
                unit["style_validation"] = "PASS"
                unit["paired_quality_review_status"] = (
                    paired_quality_request.get("status", "NOT_EVALUATED")
                    if isinstance(paired_quality_request, dict)
                    else "NOT_EVALUATED"
                )
                unit["protected_hashes_ok"] = "PASS"
                unit["hash_after"] = sha256(
                    fragment_result["restored"].encode("utf-8")
                )
                diff = "".join(
                    difflib.unified_diff(
                        fragment_result["original"].splitlines(keepends=True),
                        fragment_result["restored"].splitlines(keepends=True),
                        fromfile=f"{unit_id}.before",
                        tofile=f"{unit_id}.after",
                    )
                )
                diff_path = diffs_dir / f"{unit_id}.diff"
                diff_path.write_text(diff, encoding="utf-8")
                unit["diff_path"] = str(Path("diffs") / diff_path.name)
                paired_request_sha256 = (
                    str(paired_quality_request.get("request_sha256", ""))
                    if isinstance(paired_quality_request, dict)
                    else ""
                )
                rewrite_intent_evidence_records[unit_id] = (
                    _persist_transaction_fragment_rewrite_intent_evidence(
                        validation_dir=validation_dir,
                        unit_id=unit_id,
                        bundle=bundle,
                        fragment=transaction_fragment,
                        fragment_result=fragment_result,
                        diff_path=str(Path("diffs") / diff_path.name).replace(
                            "\\", "/"
                        ),
                        diff_sha256=sha256(diff.encode("utf-8")),
                        paired_quality_review_request_sha256=(
                            paired_request_sha256
                        ),
                        structural_transaction_review_request_sha256=str(
                            request_record["request_sha256"]
                        ),
                    )
                )
                unit["transaction_id"] = transaction_id
                unit["transaction_status"] = "ATOMIC_PASS"
                unit["notes"] = "bound_structural_transaction_review_candidate"
                unit["rewrite_intent_status"] = str(
                    fragment_result["rewrite_intent_status"]
                )
                accepted_by_file.setdefault(str(unit["file_id"]), []).append(
                    (
                        int(unit["start"]),
                        int(unit["end"]),
                        fragment_result["restored"],
                        unit_id,
                    )
                )
                invariant_baseline_by_file.setdefault(
                    str(unit["file_id"]), []
                ).append(
                    (
                        int(unit["start"]),
                        int(unit["end"]),
                        fragment_result["invariant_before"],
                        unit_id,
                    )
                )
        else:
            for unit_id in participant_ids:
                _discard_paired_quality_review_request(
                    paired_quality_review_requests, validation_dir, unit_id
                )
                unit = unit_map[unit_id]
                fragment_result = fragment_results.get(unit_id, {})
                fragment_status = transaction_result[
                    "fragment_gate_statuses"
                ].get(unit_id, "NOT_RUN")
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "STRUCTURAL_TRANSACTION_ROLLED_BACK")
                unit["structural_plan_status"] = "REVIEW"
                unit["structural_semantic_review_status"] = "NOT_ISSUED"
                unit["style_validation"] = fragment_status
                unit["protected_hashes_ok"] = (
                    "FAIL"
                    if any("protected" in item for item in transaction_result["errors"])
                    else "NOT_RUN"
                )
                unit["hash_after"] = ""
                unit["diff_path"] = ""
                unit["transaction_id"] = transaction_id
                unit["transaction_status"] = "ROLLED_BACK"
                unit["notes"] = (
                    "structural_transaction_rolled_back:"
                    + str(transaction_result["rollback_reason"])
                )
                plan_payload = {
                    "status": "REVIEW",
                    "change_applied": False,
                    "transaction_id": transaction_id,
                    "transaction_atomic_gate_status": "ROLLED_BACK",
                    "fragment_plan_status": (
                        fragment_result.get("plan_check_public", {}).get(
                            "status", "NOT_RUN"
                        )
                    ),
                    "semantic_mapping": "NOT_EVALUATED",
                    "semantic_review_status": "NOT_ISSUED",
                    "error": unit["notes"],
                }
                structural_plan_payloads[unit_id] = plan_payload
                _write_json(
                    validation_dir / f"{unit_id}.structural.json", plan_payload
                )
                if "validation_payload" in fragment_result:
                    validation_payloads[unit_id] = fragment_result[
                        "validation_payload"
                    ]
        structural_transaction_results[transaction_id] = transaction_result
        _write_json(
            validation_dir / f"{transaction_id}.transaction.json",
            transaction_result,
        )

    transaction_candidates = (
        transaction_inventory.get("transactions", [])
        if isinstance(transaction_inventory, dict)
        else []
    )
    structural_transaction_candidate_dispositions: dict[str, dict[str, Any]] = {}
    for candidate in transaction_candidates:
        transaction_id = str(candidate["transaction_id"])
        unit_ids = [
            str(item["unit_id"]) for item in candidate.get("compound_refs", [])
        ]
        common = {
            "transaction_id": transaction_id,
            "transaction_binding_sha256": candidate[
                "transaction_binding_sha256"
            ],
            "unit_ids": unit_ids,
        }
        if transaction_id in bound_transaction_execution_ids:
            transaction_result = structural_transaction_results[transaction_id]
            disposition = {
                **common,
                "disposition": "EXECUTED",
                "bundle_sha256": transaction_result["bundle_sha256"],
                "execution_status": transaction_result["atomic_gate_status"],
                "rollback_reason": transaction_result["rollback_reason"],
            }
        elif transaction_id in bound_transaction_declines:
            decline_record = bound_transaction_declines[transaction_id]
            disposition = {
                **common,
                "disposition": "DECLINED",
                "bundle_sha256": decline_record["bundle_sha256"],
                "reason_code": decline_record["reason_code"],
                "reason": decline_record["reason"],
                "evidence_refs": decline_record["evidence_refs"],
                "evidence_member_coverage": "PASS",
                "path": decline_record["path"],
            }
        else:
            disposition = {
                **common,
                "disposition": "PENDING",
                "reason": "no bound execution or decline artifact",
            }
        structural_transaction_candidate_dispositions[transaction_id] = disposition

    structural_transaction_candidates_total = len(
        structural_transaction_candidate_dispositions
    )
    structural_transaction_candidates_executed = sum(
        item["disposition"] == "EXECUTED"
        for item in structural_transaction_candidate_dispositions.values()
    )
    structural_transaction_candidates_declined = sum(
        item["disposition"] == "DECLINED"
        for item in structural_transaction_candidate_dispositions.values()
    )
    structural_transaction_candidates_pending = sum(
        item["disposition"] == "PENDING"
        for item in structural_transaction_candidate_dispositions.values()
    )
    transaction_inventory_status = (
        str(transaction_inventory.get("status", ""))
        if isinstance(transaction_inventory, dict)
        else "NOT_APPLICABLE"
    )
    if transaction_inventory_status in {"NOT_APPLICABLE", "DISABLED"}:
        structural_transaction_candidate_coverage_status = "NOT_APPLICABLE"
        structural_transaction_scope_complete: bool | None = None
    elif transaction_inventory_status == "EMPTY":
        structural_transaction_candidate_coverage_status = "PASS"
        structural_transaction_scope_complete = True
    elif structural_transaction_candidates_pending:
        structural_transaction_candidate_coverage_status = "REVIEW"
        structural_transaction_scope_complete = False
    else:
        structural_transaction_candidate_coverage_status = "PASS"
        structural_transaction_scope_complete = True

    for unit_id, bundle in rewrites.items():
        unit = unit_map[unit_id]
        rewrite_intent_schema_status = "REVIEW"
        if unit["status"] != "PENDING":
            unit["notes"] = (unit.get("notes", "") + "; " if unit.get("notes") else "") + "rewrite_submitted_for_non_pending_unit"
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "REWRITE_SUBMITTED_FOR_NON_PENDING_UNIT")
            continue
        decision = str(bundle.get("decision", "REWRITE")).upper()
        if decision not in {"REWRITE", "NO_CHANGE"}:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "REWRITE_DECISION_UNSUPPORTED")
            unit["notes"] = f"unsupported_decision:{decision}"
            continue
        authoring_binding_verified = False
        try:
            rewrite_intent_schema_status = _validate_rewrite_bundle_fields(
                bundle, decision
            )
            chunk_error = _bundle_chunk_binding_error(bundle, unit)
            if chunk_error:
                if chunk_error in {"bundle_unit_id_missing", "chunk_binding_hash_missing"}:
                    chunk_binding_missing_units.add(unit_id)
                else:
                    chunk_binding_mismatched_units.add(unit_id)
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "CHUNK_BINDING_INVALID")
                unit["notes"] = chunk_error
                continue
            chunk_binding_matched_units.add(unit_id)
            voice_error = _bundle_voice_binding_error(
                bundle, str(unit.get("voice_profile_sha256", ""))
            )
            if voice_error:
                if voice_error == "voice_profile_hash_missing":
                    voice_hash_missing_units.add(unit_id)
                else:
                    voice_hash_mismatched_units.add(unit_id)
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "VOICE_PROFILE_BINDING_INVALID")
                unit["notes"] = voice_error
                continue
            voice_hash_matched_units.add(unit_id)
            if bundle.get("schema_version") == UNIT_REWRITE_BUNDLE_SCHEMA:
                expected_authoring_binding = build_long_authoring_binding(
                    run_dir,
                    snapshot,
                    run_metadata,
                    file_by_id,
                    unit,
                    chunks[unit_id],
                )
                _validate_long_authoring_binding(
                    bundle.get("authoring_binding"),
                    expected_authoring_binding,
                )
                authoring_binding_matched_units.add(unit_id)
                authoring_binding_verified = True
            else:
                authoring_binding_missing_units.add(unit_id)
            (
                warning_resolutions,
                warning_review_request_sha256,
                warning_reviewer_kind,
                warning_reviewer_id,
            ) = _warning_review_bundle(bundle)
        except ValueError as error:
            if (
                bundle.get("schema_version") == UNIT_REWRITE_BUNDLE_SCHEMA
                and not authoring_binding_verified
            ):
                authoring_binding_mismatched_units.add(unit_id)
            elif bundle.get("schema_version") in {
                None,
                UNIT_REWRITE_BUNDLE_SCHEMA_V2,
            }:
                authoring_binding_missing_units.add(unit_id)
            unit["status"] = "UNRESOLVED"
            bundle_error_code = {
                "no_change_evidence_spans_must_be_nonempty": (
                    "NO_CHANGE_EVIDENCE_SPANS_EMPTY"
                ),
                "rewrite_intent_source_spans_must_be_nonempty": (
                    "REWRITE_INTENT_SOURCE_SPANS_EMPTY"
                ),
            }.get(str(error), "REWRITE_BUNDLE_INVALID")
            incomplete_authoring_code = _incomplete_authoring_code(bundle, decision)
            if incomplete_authoring_code:
                _add_unresolved_code(unit, incomplete_authoring_code)
            authoring_error_code = _rewrite_authoring_error_code(str(error))
            if authoring_error_code:
                _add_unresolved_code(unit, authoring_error_code)
            _add_unresolved_code(unit, bundle_error_code)
            unit["rewrite_intent_status"] = (
                "FAIL" if "schema_version" in bundle else "REVIEW"
            )
            unit["notes"] = f"invalid_rewrite_bundle:{error}"
            continue
        source_text = file_texts[unit["file_id"]]
        original = source_text[int(unit["start"]):int(unit["end"])]
        if sha256(original.encode("utf-8")) != unit["hash_before"]:
            unit["status"] = "CHANGED_AFTER_SNAPSHOT"
            unit["notes"] = "unit_source_hash_mismatch"
            continue
        if decision == "NO_CHANGE":
            if bundle.get("structural_plan") is not None:
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "NO_CHANGE_STRUCTURAL_PLAN_FORBIDDEN")
                unit["structural_plan_status"] = "FAIL"
                unit["notes"] = "structural_plan_not_allowed_for_NO_CHANGE"
                structural_plan_payloads[unit_id] = {
                    "status": "FAIL",
                    "error": unit["notes"],
                }
                _write_json(
                    validation_dir / f"{unit_id}.structural.json",
                    structural_plan_payloads[unit_id],
                )
                continue
            reason = str(bundle.get("reason", "")).strip()
            if rewrite_intent_schema_status == "PASS":
                reason_error = _no_change_reason_error(reason)
                if reason_error:
                    unit["status"] = "UNRESOLVED"
                    issue = _no_change_reason_issue(reason)
                    reason_code = {
                        "too_short_han": "NO_CHANGE_REASON_TOO_SHORT_HAN",
                        "generic_template": "NO_CHANGE_REASON_GENERIC_TEMPLATE",
                        "missing_function_anchor": (
                            "NO_CHANGE_REASON_MISSING_FUNCTION_ANCHOR"
                        ),
                    }.get(str(issue))
                    if reason_code is None:
                        raise AssertionError("unknown NO_CHANGE reason issue")
                    _add_unresolved_code(unit, reason_code)
                    unit["rewrite_intent_status"] = "FAIL"
                    unit["notes"] = f"rewrite_intent:{reason_error}"
                    continue
            elif not _specific_reason(reason):
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "NO_CHANGE_REASON_INVALID_LEGACY")
                unit["notes"] = "NO_CHANGE requires a reason with at least 4 Chinese characters"
                continue
            try:
                _validate_bound_rewrite_intent(
                    bundle,
                    decision,
                    str(chunks[unit_id].get("masked_text", "")),
                    rewrite_intent_schema_status,
                )
            except ValueError as error:
                unit["status"] = "UNRESOLVED"
                intent_code = (
                    "NO_CHANGE_EVIDENCE_SPANS_EMPTY"
                    if str(error) == "no_change_evidence_spans_must_be_nonempty"
                    else "NO_CHANGE_INTENT_INVALID"
                )
                _add_unresolved_code(unit, intent_code)
                unit["rewrite_intent_status"] = "FAIL"
                unit["notes"] = f"rewrite_intent:{error}"
                continue
            no_change_keep = bundle.get("keep_reasons", {})
            if not isinstance(no_change_keep, dict):
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "NO_CHANGE_KEEP_REASONS_TYPE_INVALID")
                unit["notes"] = "NO_CHANGE keep_reasons must be an object"
                continue
            try:
                valid_signal_ids = {
                    item["id"] for item in output_validator.lexical.load_lexicon()["signals"]
                }
                no_change_keep = output_validator._parse_keep_reasons(
                    [f"{key}={value}" for key, value in no_change_keep.items()],
                    valid_signal_ids,
                )
            except ValueError as error:
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "NO_CHANGE_KEEP_REASON_INVALID")
                unit["notes"] = f"invalid_NO_CHANGE_keep_reason:{error}"
                continue
            suffix = Path(next(item["path"] for item in file_manifest if item["file_id"] == unit["file_id"])).suffix or ".txt"
            before_path = validation_dir / f"{unit_id}.before{suffix}"
            after_path = validation_dir / f"{unit_id}.after{suffix}"
            before_path.write_text(original, encoding="utf-8", newline="")
            after_path.write_text(original, encoding="utf-8", newline="")
            try:
                no_change_payload = output_validator.validate(
                    before_path,
                    after_path,
                    scene=unit["scene"],
                    keep_reasons=no_change_keep,
                    warning_resolutions=warning_resolutions,
                    warning_review_request_sha256=warning_review_request_sha256,
                    warning_reviewer_kind=warning_reviewer_kind,
                    warning_reviewer_id=warning_reviewer_id,
                    fragment_mode=True,
                    editable_style_wrappers=run_metadata["editable_style_wrappers"],
                )
            except ValueError as error:
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "WARNING_PROPOSAL_INVALID")
                unit["notes"] = f"invalid_warning_proposal:{error}"
                continue
            _stabilize_validation_evidence_refs(
                no_change_payload, unit_id, suffix
            )
            paired_quality_request = _persist_paired_quality_review_request(
                no_change_payload, validation_dir, unit_id
            )
            if isinstance(paired_quality_request, dict):
                paired_quality_review_requests[unit_id] = paired_quality_request
                unit["paired_quality_review_status"] = paired_quality_request[
                    "status"
                ]
            else:
                unit["paired_quality_review_status"] = "NOT_EVALUATED"
            no_change_structural = {
                "status": (
                    "PASS"
                    if str(unit.get("intensity", "")).upper() == "STRUCTURAL"
                    else "NOT_APPLICABLE"
                ),
                "change_applied": False,
                "decision": "NO_CHANGE",
                "semantic_mapping": (
                    "PASS"
                    if str(unit.get("intensity", "")).upper() == "STRUCTURAL"
                    else "NOT_APPLICABLE"
                ),
                "semantic_review_status": "NOT_REQUIRED",
            }
            unit["structural_plan_status"] = no_change_structural["status"]
            unit["structural_semantic_review_status"] = no_change_structural[
                "semantic_review_status"
            ]
            structural_plan_payloads[unit_id] = no_change_structural
            no_change_payload["structural_plan_check"] = no_change_structural
            validation_payloads[unit_id] = no_change_payload
            _write_json(validation_dir / f"{unit_id}.validation.json", no_change_payload)
            _write_json(
                validation_dir / f"{unit_id}.structural.json",
                no_change_structural,
            )
            if no_change_payload["mechanical_validation_status"] != "PASS":
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(unit, "NO_CHANGE_VALIDATOR_NOT_PASS")
                unit["style_validation"] = no_change_payload[
                    "mechanical_validation_status"
                ]
                unit["notes"] = (
                    "NO_CHANGE validator:"
                    + no_change_payload["mechanical_validation_status"]
                )
                continue
            if not _quality_review_only(no_change_payload):
                unit["status"] = "UNRESOLVED"
                _add_unresolved_code(
                    unit, "NO_CHANGE_PAIRED_QUALITY_REQUEST_MISSING"
                )
                unit["style_validation"] = "REVIEW"
                unit["notes"] = "NO_CHANGE paired quality request missing"
                continue
            empty_diff_path = diffs_dir / f"{unit_id}.diff"
            empty_diff_path.write_text("", encoding="utf-8")
            request_sha256 = str(
                (paired_quality_request or {}).get("request_sha256", "")
            )
            rewrite_intent_evidence_records[unit_id] = (
                _persist_rewrite_intent_evidence(
                    validation_dir=validation_dir,
                    unit_id=unit_id,
                    decision=decision,
                    bundle=bundle,
                    schema_status=rewrite_intent_schema_status,
                    before_sha256=str(
                        no_change_payload.get("evidence", {}).get(
                            "before_sha256", ""
                        )
                    ),
                    after_sha256=str(
                        no_change_payload.get("evidence", {}).get(
                            "after_sha256", ""
                        )
                    ),
                    diff_path=str(Path("diffs") / empty_diff_path.name).replace(
                        "\\", "/"
                    ),
                    diff_sha256=sha256(b""),
                    paired_quality_request_sha256=request_sha256,
                    diff_binding={
                        "status": "NOT_APPLICABLE",
                        "reason": "NO_CHANGE",
                        "changed_source_ranges": [],
                    },
                )
            )
            unit["status"] = "NO_CHANGE"
            unit["hash_after"] = unit["hash_before"]
            unit["protected_hashes_ok"] = "PASS"
            unit["style_validation"] = "PASS"
            unit["rewrite_intent_status"] = rewrite_intent_schema_status
            unit["notes"] = reason
            continue

        masked_text = bundle.get("masked_text")
        if not isinstance(masked_text, str):
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "REWRITE_MASKED_TEXT_MISSING")
            unit["notes"] = "missing masked_text"
            continue
        suffix = file_suffixes.get(str(unit["file_id"]), ".txt") or ".txt"
        try:
            structural_plan_check = _validate_structural_plan(
                bundle,
                unit,
                chunks[unit_id],
                masked_text,
                suffix,
                span_map,
            )
        except ValueError as error:
            structural_plan_check = {
                "status": "FAIL",
                "error": str(error),
                "semantic_mapping": "NOT_EVALUATED",
            }
            structural_plan_payloads[unit_id] = structural_plan_check
            _write_json(
                validation_dir / f"{unit_id}.structural.json",
                structural_plan_check,
            )
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "STRUCTURAL_PLAN_INVALID")
            unit["structural_plan_status"] = "FAIL"
            unit["structural_semantic_review_status"] = "NOT_ISSUED"
            unit["notes"] = "structural_plan:" + str(error)
            continue
        structural_baseline_masked = str(
            structural_plan_check.pop(
                "_baseline_masked_text",
                chunks[unit_id].get("masked_text", ""),
            )
        )
        structural_plan_check["invariant_baseline_sha256"] = sha256(
            structural_baseline_masked.encode("utf-8")
        )
        structural_plan_payloads[unit_id] = structural_plan_check
        _write_json(
            validation_dir / f"{unit_id}.structural.json",
            structural_plan_check,
        )
        unit["structural_plan_status"] = structural_plan_check["status"]
        unit["structural_semantic_review_status"] = (
            "NOT_ISSUED"
            if structural_plan_check.get("change_applied") is True
            else "NOT_REQUIRED"
        )
        restored, restore_errors = restore_protected(masked_text, unit["protected_ids"], span_map)
        if restored is None:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "PROTECTED_PLACEHOLDER_RESTORE_FAILED")
            unit["protected_hashes_ok"] = "FAIL"
            unit["notes"] = " | ".join(restore_errors)
            continue
        invariant_before, invariant_restore_errors = restore_protected(
            structural_baseline_masked,
            unit["protected_ids"],
            span_map,
        )
        if invariant_before is None:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "STRUCTURAL_BASELINE_RESTORE_FAILED")
            unit["protected_hashes_ok"] = "FAIL"
            unit["notes"] = "structural_baseline_restore:" + " | ".join(
                invariant_restore_errors
            )
            continue
        copied_context = _copied_read_only_context(original, restored, chunks[unit_id])
        if copied_context:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "READ_ONLY_CONTEXT_COPIED")
            unit["notes"] = "read_only_context_copied:" + ",".join(copied_context)
            continue
        try:
            _validate_bound_rewrite_intent(
                bundle,
                decision,
                structural_baseline_masked,
                rewrite_intent_schema_status,
            )
            rewrite_intent_diff_binding = _rewrite_intent_diff_binding(
                bundle,
                structural_baseline_masked,
                masked_text,
                rewrite_intent_schema_status,
            )
        except ValueError as error:
            unit["status"] = "UNRESOLVED"
            intent_code = (
                "REWRITE_INTENT_SOURCE_SPANS_EMPTY"
                if str(error) == "rewrite_intent_source_spans_must_be_nonempty"
                else "REWRITE_INTENT_INVALID"
            )
            _add_unresolved_code(unit, intent_code)
            authoring_error_code = _rewrite_authoring_error_code(str(error))
            if authoring_error_code:
                _add_unresolved_code(unit, authoring_error_code)
            unit["rewrite_intent_status"] = "FAIL"
            unit["notes"] = f"rewrite_intent:{error}"
            continue
        actual_structural_content_changed = restored != invariant_before
        structural_plan_check["actual_content_changed"] = (
            actual_structural_content_changed
        )
        paragraph_order_check = _non_structural_paragraph_order_check(
            structural_baseline_masked,
            masked_text,
            str(unit.get("intensity", "")),
            bundle,
            rewrite_intent_schema_status,
        )
        structural_plan_check["non_structural_paragraph_order_check"] = (
            paragraph_order_check
        )
        if paragraph_order_check["status"] == "REVIEW":
            if paragraph_order_check.get("topology_authorization_error"):
                scope_error = str(
                    paragraph_order_check["topology_authorization_error"]
                )
            elif paragraph_order_check.get("paragraph_topology_changed"):
                scope_error = "non_structural_paragraph_topology_changed"
            elif paragraph_order_check.get("protected_anchor_reordered"):
                scope_error = "non_structural_protected_anchor_reordered"
            elif paragraph_order_check.get("light_sentence_reorder"):
                scope_error = "light_sentence_reorder_not_allowed"
            else:
                scope_error = "non_structural_paragraph_reorder_detected"
            structural_plan_check.update(
                {
                    "status": "REVIEW",
                    "semantic_mapping": "NOT_EVALUATED",
                    "semantic_review_status": "BLOCKED_BY_SCOPE_VIOLATION",
                    "error": scope_error,
                }
            )
            structural_plan_payloads[unit_id] = structural_plan_check
            _write_json(
                validation_dir / f"{unit_id}.structural.json",
                structural_plan_check,
            )
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "NON_STRUCTURAL_SCOPE_VIOLATION")
            unit["structural_plan_status"] = "REVIEW"
            unit["structural_semantic_review_status"] = "BLOCKED_BY_SCOPE_VIOLATION"
            unit["notes"] = scope_error
            continue
        if (
            str(unit.get("intensity", "")).upper() == "STRUCTURAL"
            and actual_structural_content_changed
            and structural_plan_check.get("change_applied") is not True
        ):
            structural_plan_check["semantic_mapping"] = "NOT_EVALUATED"
            structural_plan_check["semantic_review_status"] = (
                "PENDING_EXTERNAL_REVIEW"
            )
        protected_count_changes = _protected_content_count_changes(
            original,
            restored,
            unit["protected_ids"],
            span_map,
        )
        if protected_count_changes:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "PROTECTED_CONTENT_COUNT_CHANGED")
            unit["protected_hashes_ok"] = "FAIL"
            unit["notes"] = "protected_content_count_changed:" + ",".join(protected_count_changes)
            continue
        if restored == original:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "REWRITE_IDENTICAL_TO_SOURCE")
            unit["notes"] = "REWRITE bundle is identical; use explicit NO_CHANGE with reason"
            continue

        suffix = Path(next(item["path"] for item in file_manifest if item["file_id"] == unit["file_id"])).suffix or ".txt"
        before_path = validation_dir / f"{unit_id}.before{suffix}"
        after_path = validation_dir / f"{unit_id}.after{suffix}"
        before_path.write_text(invariant_before, encoding="utf-8", newline="")
        after_path.write_text(restored, encoding="utf-8", newline="")
        keep_reasons = bundle.get("keep_reasons", {})
        if not isinstance(keep_reasons, dict):
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "KEEP_REASONS_TYPE_INVALID")
            unit["notes"] = "keep_reasons must be an object"
            continue
        try:
            valid_signal_ids = {
                item["id"] for item in output_validator.lexical.load_lexicon()["signals"]
            }
            keep_reasons = output_validator._parse_keep_reasons(
                [f"{key}={value}" for key, value in keep_reasons.items()],
                valid_signal_ids,
            )
        except ValueError as error:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "KEEP_REASON_INVALID")
            unit["notes"] = f"invalid_keep_reason:{error}"
            continue
        try:
            template_field_edit_scope_path = (
                _materialize_unit_template_field_edit_scope(
                    bundle,
                    decision=decision,
                    before_path=before_path,
                    validation_dir=validation_dir,
                    unit_id=unit_id,
                )
            )
        except (OSError, ValueError) as error:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "TEMPLATE_FIELD_EDIT_SCOPE_INVALID")
            unit["notes"] = f"invalid_template_field_edit_scope:{error}"
            continue
        try:
            payload = output_validator.validate(
                before_path,
                after_path,
                scene=unit["scene"],
                keep_reasons=keep_reasons,
                warning_resolutions=warning_resolutions,
                warning_review_request_sha256=warning_review_request_sha256,
                warning_reviewer_kind=warning_reviewer_kind,
                warning_reviewer_id=warning_reviewer_id,
                fragment_mode=True,
                template_field_edit_scope_path=template_field_edit_scope_path,
                editable_style_wrappers=run_metadata["editable_style_wrappers"],
            )
        except ValueError as error:
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "WARNING_PROPOSAL_INVALID")
            unit["notes"] = f"invalid_warning_proposal:{error}"
            continue
        _stabilize_validation_evidence_refs(payload, unit_id, suffix)
        paired_quality_request = _persist_paired_quality_review_request(
            payload, validation_dir, unit_id
        )
        if isinstance(paired_quality_request, dict):
            paired_quality_review_requests[unit_id] = paired_quality_request
            unit["paired_quality_review_status"] = paired_quality_request["status"]
        else:
            unit["paired_quality_review_status"] = "NOT_EVALUATED"
        validation_payloads[unit_id] = payload
        payload["structural_plan_check"] = structural_plan_check
        semantic_review_request = _build_structural_semantic_review_request(
            snapshot_id=str(snapshot["snapshot_id"]),
            unit_id=unit_id,
            unit=unit,
            chunk=chunks[unit_id],
            bundle=bundle,
            structural_plan_check=structural_plan_check,
            original=original,
            invariant_before=invariant_before,
            restored=restored,
            validation_payload=payload,
            suffix=suffix,
        )
        if semantic_review_request is not None:
            request_name = f"{unit_id}.structural-semantic-review-request.json"
            request_path = validation_dir / request_name
            _write_json(request_path, semantic_review_request)
            request_record = {
                "status": "PENDING_EXTERNAL_REVIEW",
                "path": str(Path("validation") / request_name).replace("\\", "/"),
                "request_sha256": semantic_review_request["request_sha256"],
            }
            structural_semantic_review_requests[unit_id] = request_record
            structural_plan_check["semantic_review"] = request_record
            structural_plan_check["semantic_review_status"] = (
                "PENDING_EXTERNAL_REVIEW"
            )
            unit["structural_semantic_review_status"] = (
                "PENDING_EXTERNAL_REVIEW"
            )
        elif (
            structural_plan_check.get("change_applied") is True
            or structural_plan_check.get("actual_content_changed") is True
        ):
            structural_plan_check["semantic_review_status"] = (
                "BLOCKED_BY_HARD_INVARIANT"
                if payload.get("hard_invariant_layer_status") != "PASS"
                else "NOT_ISSUED"
            )
            unit["structural_semantic_review_status"] = structural_plan_check[
                "semantic_review_status"
            ]
        else:
            structural_plan_check["semantic_review_status"] = "NOT_REQUIRED"
            unit["structural_semantic_review_status"] = "NOT_REQUIRED"
        structural_plan_payloads[unit_id] = structural_plan_check
        _write_json(
            validation_dir / f"{unit_id}.structural.json",
            structural_plan_check,
        )
        _write_json(validation_dir / f"{unit_id}.validation.json", payload)
        unit["style_validation"] = payload["mechanical_validation_status"]
        unit["protected_hashes_ok"] = "PASS" if not payload["invariants"]["hard_failure"] else "FAIL"
        if payload["mechanical_validation_status"] != "PASS":
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "VALIDATOR_NOT_PASS")
            unit["notes"] = (
                "validator:"
                + payload["mechanical_validation_status"]
                + ":"
                + ",".join(payload["review_reasons"])
            )
            continue
        if not _quality_review_only(payload):
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(unit, "PAIRED_QUALITY_REQUEST_MISSING")
            unit["style_validation"] = "REVIEW"
            unit["notes"] = "paired quality request missing"
            continue

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                restored.splitlines(keepends=True),
                fromfile=f"{unit_id}.before",
                tofile=f"{unit_id}.after",
            )
        )
        diff_path = diffs_dir / f"{unit_id}.diff"
        diff_path.write_text(diff, encoding="utf-8")
        request_sha256 = str(
            (paired_quality_request or {}).get("request_sha256", "")
        )
        rewrite_intent_evidence_records[unit_id] = (
            _persist_rewrite_intent_evidence(
                validation_dir=validation_dir,
                unit_id=unit_id,
                decision=decision,
                bundle=bundle,
                schema_status=rewrite_intent_schema_status,
                before_sha256=str(
                    payload.get("evidence", {}).get("before_sha256", "")
                ),
                after_sha256=str(
                    payload.get("evidence", {}).get("after_sha256", "")
                ),
                diff_path=str(Path("diffs") / diff_path.name).replace("\\", "/"),
                diff_sha256=sha256(diff_path.read_bytes()),
                paired_quality_request_sha256=request_sha256,
                diff_binding=rewrite_intent_diff_binding,
            )
        )
        unit["status"] = "DONE"
        accepted_masked_by_unit[unit_id] = masked_text
        unit["hash_after"] = sha256(restored.encode("utf-8"))
        unit["diff_path"] = str(Path("diffs") / diff_path.name)
        unit["rewrite_intent_status"] = rewrite_intent_schema_status
        accepted_by_file.setdefault(unit["file_id"], []).append(
            (int(unit["start"]), int(unit["end"]), restored, unit_id)
        )
        invariant_baseline_by_file.setdefault(unit["file_id"], []).append(
            (int(unit["start"]), int(unit["end"]), invariant_before, unit_id)
        )

    file_level_coverage_gap = any(
        str(record.get("status", ""))
        in {
            "UNRESOLVED",
            "UNRESOLVED_INCLUDE",
            "SKIPPED_GARBLED",
            "CHANGED_AFTER_SNAPSHOT",
        }
        for record in file_manifest
    )
    for transaction_id, transaction in sorted(
        structural_transaction_results.items()
    ):
        if transaction.get("atomic_gate_status") != "PASS":
            continue
        participant_ids = set(transaction["unit_ids"])
        independent_coverage_gap = any(
            unit_id not in participant_ids
            and unit_map[unit_id].get("status") not in {
                "DONE",
                "NO_CHANGE",
                "SKIPPED_PROTECTED",
            }
            for unit_id in expected_voice_units
        )
        if not file_level_coverage_gap and not independent_coverage_gap:
            continue
        transaction.update(
            {
                "status": "REVIEW",
                "atomic_gate_status": "ROLLED_BACK",
                "change_applied": False,
                "rollback_reason": "INCOMPLETE_DOCUMENT_COVERAGE",
                "review_request": {},
                "errors": [
                    *transaction.get("errors", []),
                    "structural_transaction_review_only_publication_blocked",
                ],
            }
        )
        request_record = structural_transaction_review_requests.pop(
            transaction_id, None
        )
        if isinstance(request_record, dict):
            staged_request_path = validation_dir / Path(
                str(request_record.get("path", ""))
            ).name
            if staged_request_path.is_file():
                staged_request_path.unlink()
        for unit_id in transaction["unit_ids"]:
            structural_semantic_review_requests.pop(unit_id, None)
            _discard_paired_quality_review_request(
                paired_quality_review_requests, validation_dir, unit_id
            )
            _discard_rewrite_intent_evidence(
                rewrite_intent_evidence_records, validation_dir, unit_id
            )
            accepted_masked_by_unit.pop(unit_id, None)
            unit = unit_map[unit_id]
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(
                unit, "STRUCTURAL_TRANSACTION_INCOMPLETE_DOCUMENT_COVERAGE"
            )
            unit["hash_after"] = ""
            unit["diff_path"] = ""
            unit["structural_plan_status"] = "REVIEW"
            unit["structural_semantic_review_status"] = "NOT_ISSUED"
            unit["transaction_status"] = "ROLLED_BACK"
            unit["notes"] = (
                "structural_transaction_rolled_back:INCOMPLETE_DOCUMENT_COVERAGE"
            )
            diff_path = diffs_dir / f"{unit_id}.diff"
            if diff_path.is_file():
                diff_path.unlink()
            plan_payload = structural_plan_payloads[unit_id]
            plan_payload.update(
                {
                    "status": "REVIEW",
                    "change_applied": False,
                    "transaction_atomic_gate_status": "ROLLED_BACK",
                    "semantic_review_status": "NOT_ISSUED",
                }
            )
            plan_payload.pop("semantic_review", None)
            _write_json(
                validation_dir / f"{unit_id}.structural.json", plan_payload
            )
        for file_id, changes in list(accepted_by_file.items()):
            remaining = [
                item for item in changes if item[3] not in participant_ids
            ]
            if remaining:
                accepted_by_file[file_id] = remaining
            else:
                accepted_by_file.pop(file_id, None)
        for file_id, changes in list(invariant_baseline_by_file.items()):
            remaining = [
                item for item in changes if item[3] not in participant_ids
            ]
            if remaining:
                invariant_baseline_by_file[file_id] = remaining
            else:
                invariant_baseline_by_file.pop(file_id, None)
        _write_json(
            validation_dir / f"{transaction_id}.transaction.json", transaction
        )

    preliminary_style_records: list[dict[str, Any]] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        if unit_id not in expected_voice_units:
            continue
        file_id = str(unit.get("file_id", ""))
        file_record = file_by_id.get(file_id)
        if file_record is None or file_id not in document_id_by_file:
            raise ValueError(f"style audit unit references unknown file_id: {file_id}")
        suffix = str(file_record.get("suffix", "")).lower()
        document_format = "tex" if suffix in {".tex", ".ltx"} else "markdown"
        before_masked = str(chunks[unit_id].get("masked_text", ""))
        preliminary_style_records.append(
            {
                "unit_id": unit_id,
                "file_id": file_id,
                "document_id": document_id_by_file[file_id],
                "resolved_scene": unit.get("scene", ""),
                "heading_path": unit.get("heading_path", ""),
                "part": unit.get("part"),
                "start": unit.get("start"),
                "end": unit.get("end"),
                "format": document_format,
                "expected": True,
                "state": unit.get("status", ""),
                "style_validation": unit.get("style_validation", ""),
                "before_masked": before_masked,
                "after_masked": (
                    before_masked
                    if unit.get("status") == "NO_CHANGE"
                    else accepted_masked_by_unit.get(unit_id)
                    if unit.get("status") == "DONE"
                    else None
                ),
                "protected_structure_tokens": _protected_structure_tokens(
                    before_masked,
                    file_id=file_id,
                    document_format=document_format,
                    span_map=span_map,
                ),
            }
        )
    cross_unit_repetition = _audit_cross_unit_repetition(preliminary_style_records)
    _write_json(validation_dir / "cross_unit_repetition.json", cross_unit_repetition)
    blocked_by_repetition = set(cross_unit_repetition["blocking_unit_ids"])
    repetition_rolled_back_transactions = {
        unit_to_transaction[unit_id]
        for unit_id in blocked_by_repetition
        if unit_id in unit_to_transaction
    }
    for transaction_id in sorted(repetition_rolled_back_transactions):
        transaction = structural_transaction_results.get(transaction_id)
        if not isinstance(transaction, dict) or transaction.get(
            "atomic_gate_status"
        ) != "PASS":
            continue
        blocked_by_repetition.update(transaction["unit_ids"])
        transaction.update(
            {
                "status": "REVIEW",
                "atomic_gate_status": "ROLLED_BACK",
                "change_applied": False,
                "rollback_reason": "CROSS_UNIT_REPETITION",
                "review_request": {},
            }
        )
        transaction["errors"] = [
            *transaction.get("errors", []),
            "structural_transaction_cross_unit_repetition",
        ]
        request_record = structural_transaction_review_requests.pop(
            transaction_id, None
        )
        if isinstance(request_record, dict):
            request_path = run_dir / str(request_record.get("path", ""))
            staged_request_path = validation_dir / request_path.name
            if staged_request_path.is_file():
                staged_request_path.unlink()
        for member_id in transaction["unit_ids"]:
            structural_semantic_review_requests.pop(member_id, None)
            _discard_paired_quality_review_request(
                paired_quality_review_requests, validation_dir, member_id
            )
            _discard_rewrite_intent_evidence(
                rewrite_intent_evidence_records, validation_dir, member_id
            )
            plan_payload = structural_plan_payloads.get(member_id)
            if isinstance(plan_payload, dict):
                plan_payload.update(
                    {
                        "status": "REVIEW",
                        "change_applied": False,
                        "transaction_atomic_gate_status": "ROLLED_BACK",
                        "semantic_review_status": "NOT_ISSUED",
                    }
                )
                plan_payload.pop("semantic_review", None)
                _write_json(
                    validation_dir / f"{member_id}.structural.json",
                    plan_payload,
                )
        _write_json(
            validation_dir / f"{transaction_id}.transaction.json", transaction
        )
    if blocked_by_repetition:
        for unit_id in sorted(blocked_by_repetition):
            unit = unit_map[unit_id]
            if unit.get("status") not in {"DONE", "NO_CHANGE"}:
                continue
            unit["status"] = "UNRESOLVED"
            _add_unresolved_code(
                unit, "CROSS_UNIT_REPETITION_INTRODUCED_TEMPLATE_FAMILY"
            )
            unit["hash_after"] = ""
            unit["diff_path"] = ""
            accepted_masked_by_unit.pop(unit_id, None)
            _discard_paired_quality_review_request(
                paired_quality_review_requests, validation_dir, unit_id
            )
            _discard_rewrite_intent_evidence(
                rewrite_intent_evidence_records, validation_dir, unit_id
            )
            if unit_id in unit_to_transaction:
                unit["transaction_status"] = "ROLLED_BACK"
                unit["structural_plan_status"] = "REVIEW"
                unit["structural_semantic_review_status"] = "NOT_ISSUED"
            unit["notes"] = (
                (str(unit.get("notes", "")) + "; ") if unit.get("notes") else ""
            ) + "cross_unit_repetition:introduced_template_family"
            diff_path = diffs_dir / f"{unit_id}.diff"
            if diff_path.exists():
                diff_path.unlink()
        for file_id, changes in list(accepted_by_file.items()):
            remaining = [item for item in changes if item[3] not in blocked_by_repetition]
            if remaining:
                accepted_by_file[file_id] = remaining
            else:
                accepted_by_file.pop(file_id, None)
        for file_id, changes in list(invariant_baseline_by_file.items()):
            remaining = [item for item in changes if item[3] not in blocked_by_repetition]
            if remaining:
                invariant_baseline_by_file[file_id] = remaining
            else:
                invariant_baseline_by_file.pop(file_id, None)

    rendered_texts: dict[str, str] = dict(file_texts)
    invariant_baseline_texts: dict[str, str] = dict(file_texts)
    for file_id, changes in accepted_by_file.items():
        text = rendered_texts[file_id]
        for start, end, replacement, _ in sorted(changes, key=lambda item: item[0], reverse=True):
            text = text[:start] + replacement + text[end:]
        rendered_texts[file_id] = text
    for file_id, changes in invariant_baseline_by_file.items():
        text = invariant_baseline_texts[file_id]
        for start, end, replacement, _ in sorted(
            changes, key=lambda item: item[0], reverse=True
        ):
            text = text[:start] + replacement + text[end:]
        invariant_baseline_texts[file_id] = text

    relative_paths = _relative_render_paths(file_manifest)
    rendered_manifest: list[dict[str, Any]] = []
    full_format_errors: list[dict[str, Any]] = []
    for record in file_manifest:
        file_id = record["file_id"]
        if file_id not in rendered_texts:
            continue
        relative = relative_paths[file_id]
        destination = staging_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = _encode(rendered_texts[file_id], file_encoding[file_id], file_raw[file_id])
        destination.write_bytes(raw)
        document_format = "tex" if Path(record["path"]).suffix.lower() in {".tex", ".ltx"} else "markdown"
        full_check = invariants.check_documents(
            invariant_baseline_texts[file_id],
            rendered_texts[file_id],
            document_format=document_format,
            editable_style_wrappers=run_metadata["editable_style_wrappers"],
        )
        if full_check.errors:
            full_format_errors.append({"file_id": file_id, "errors": full_check.to_dict()["errors"]})
        rendered_manifest.append(
            {
                "file_id": file_id,
                "source_role": record.get("source_role", ""),
                "source_processing_status": record.get(
                    "source_processing_status", ""
                ),
                "source_path": record["path"],
                "source_path_scope": "LIVE_LOCATION_LABEL_NOT_HASH_TARGET",
                "source_snapshot_copy": record.get("snapshot_copy", ""),
                "source_snapshot_sha256": record.get("sha256", ""),
                "rendered_path": str(relative).replace("\\", "/"),
                "sha256": sha256(raw),
                "sha256_scope": "RENDERED_CANDIDATE_BYTES",
                "rendered_sha256": sha256(raw),
                "bytes": len(raw),
                "format_check": "FAIL" if full_check.errors else "PASS",
            }
        )

    statuses = Counter(str(unit["status"]) for unit in units)
    file_statuses = Counter(str(record["status"]) for record in file_manifest)
    pending = statuses.get("PENDING", 0) + statuses.get("IN_PROGRESS", 0)
    unresolved_units = sum(statuses.get(status, 0) for status in ("UNRESOLVED", "SKIPPED_GARBLED", "CHANGED_AFTER_SNAPSHOT"))
    unresolved_files = sum(
        file_statuses.get(status, 0)
        for status in ("UNRESOLVED", "UNRESOLVED_INCLUDE", "SKIPPED_GARBLED", "CHANGED_AFTER_SNAPSHOT")
    ) + sum(
        1
        for record in file_manifest
        if str(record.get("source_role", "")) == "UNRESOLVED"
        and str(record.get("status", ""))
        not in {"UNRESOLVED", "UNRESOLVED_INCLUDE", "SKIPPED_GARBLED"}
    )
    source_changes_before_compile = _source_changes(file_manifest)
    run_state_before_compile = _run_state_hashes(run_dir)
    staging_hashes_before_compile = _directory_hashes(staging_dir)
    evidence_staging_hashes_before_compile = {
        "validation": _directory_hashes(validation_dir),
        "diffs": _directory_hashes(diffs_dir),
    }
    if source_changes_before_compile:
        compile_result = _compile_check_result(
            status="NOT_RUN_DUE_TO_SOURCE_CHANGE",
            command=check_command or "",
            timeout_seconds=result_timeout_seconds,
        )
    elif full_format_errors:
        compile_result = _compile_check_result(
            status="NOT_RUN_DUE_TO_FORMAT_FAILURE",
            command=check_command or "",
            timeout_seconds=result_timeout_seconds,
        )
    else:
        compile_workspace = run_dir / ".compile_check_staging"
        _copy_for_check(staging_dir, compile_workspace)
        try:
            compile_result = _run_compile(
                check_command,
                compile_workspace,
                timeout_seconds=validated_check_timeout,
            )
        except Exception as error:
            compile_result = _compile_check_result(
                status="FAIL",
                command=check_command or "",
                stderr=(
                    "compile check setup/runtime failure: "
                    f"{type(error).__name__}: {error}"
                ),
                cwd=compile_workspace,
                process_containment="UNAVAILABLE",
                descendant_cleanup="FAIL",
                timed_out=False,
                timeout_seconds=validated_check_timeout,
            )
        finally:
            shutil.rmtree(compile_workspace, ignore_errors=True)

        staging_hashes_after_compile = _directory_hashes(staging_dir)
        evidence_staging_hashes_after_compile = {
            "validation": _directory_hashes(validation_dir),
            "diffs": _directory_hashes(diffs_dir),
        }
        run_state_after_compile = _run_state_hashes(run_dir)
        integrity_changes: dict[str, Any] = {}
        if staging_hashes_after_compile != staging_hashes_before_compile:
            integrity_changes["staging"] = {
                "before": staging_hashes_before_compile,
                "after": staging_hashes_after_compile,
            }
        if evidence_staging_hashes_after_compile != evidence_staging_hashes_before_compile:
            integrity_changes["evidence_staging"] = {
                "before": evidence_staging_hashes_before_compile,
                "after": evidence_staging_hashes_after_compile,
            }
        if run_state_after_compile != run_state_before_compile:
            integrity_changes["run_dir"] = {
                "before": run_state_before_compile,
                "after": run_state_after_compile,
            }
        if integrity_changes:
            compile_result["status"] = "FAIL"
            compile_result["integrity_status"] = "FAIL"
            compile_result["integrity_changes"] = integrity_changes
        else:
            compile_result["integrity_status"] = "PASS"
    source_changes = _source_changes(file_manifest)
    compile_or_concurrent_source_change = not source_changes_before_compile and bool(source_changes)
    second_pass_evidence: dict[str, Any] = {
        "status": "NOT_RUN",
        "receipt_sha256": "",
        "path": "",
        "units_total": 0,
        "evidence_cap": "E0",
        "filesystem_isolation_verified": False,
        "oracle_unreachable_verified": False,
    }
    review_only_transaction_present = any(
        result.get("atomic_gate_status") == "PASS"
        and result.get("change_applied") is True
        for result in structural_transaction_results.values()
    )
    # Every editable long-document unit requires a paired-quality request.
    # Missing request artifacts must block second-pass downgrade just as
    # pending requests do; otherwise a persistence failure could erase the
    # very gate that the receipt is forbidden to clear.
    review_only_quality_present = bool(expected_voice_units)
    if second_pass_receipt is not None and (
        review_only_transaction_present or review_only_quality_present
    ):
        second_pass_evidence = {
            "status": "FAIL",
            "receipt_sha256": "",
            "path": str(second_pass_receipt.resolve(strict=False)),
            "units_total": 0,
            "evidence_cap": "E0",
            "filesystem_isolation_verified": False,
            "oracle_unreachable_verified": False,
            "error": (
                "second_pass_receipt_not_allowed_for_review_candidate:"
                + (
                    "STRUCTURAL_TRANSACTION"
                    if review_only_transaction_present
                    else "PAIRED_QUALITY"
                )
            ),
        }
    elif second_pass_receipt is not None:
        try:
            second_pass_evidence = _validate_second_pass_receipt(
                second_pass_receipt.resolve(strict=True),
                snapshot_id=str(snapshot["snapshot_id"]),
                rendered_root=staging_dir,
                rendered_manifest_path=run_dir / "rendered_manifest.csv",
                voice_binding_sha256=str(voice_identity["identity_sha256"]),
                scene=str(run_metadata.get("scene", "")),
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
            second_pass_evidence = {
                "status": "FAIL",
                "receipt_sha256": "",
                "path": str(second_pass_receipt.resolve(strict=False)),
                "units_total": 0,
                "evidence_cap": "E0",
                "filesystem_isolation_verified": False,
                "oracle_unreachable_verified": False,
                "error": str(error),
            }
    processable_editable_units = initial_processable_editable_units
    empty_processable_scope = not file_manifest or not units or processable_editable_units == 0
    unresolved = unresolved_units + unresolved_files + len(source_changes) + (1 if empty_processable_scope else 0)

    run_intensity = str(run_metadata.get("intensity", "")).upper()
    if run_intensity != "STRUCTURAL":
        structural_plan_status = "NOT_APPLICABLE"
    elif not expected_voice_units:
        structural_plan_status = "NOT_EVALUATED"
    elif all(
        str(unit_map[unit_id].get("structural_plan_status", "")) == "PASS"
        for unit_id in expected_voice_units
    ):
        structural_plan_status = "PASS"
    else:
        structural_plan_status = "REVIEW"
    structural_changes_applied = sum(
        1
        for payload in structural_plan_payloads.values()
        if payload.get("status") == "PASS"
        and (
            payload.get("change_applied") is True
            or payload.get("actual_content_changed") is True
        )
    )
    if structural_plan_status == "NOT_APPLICABLE":
        structural_semantic_mapping = "NOT_APPLICABLE"
    elif structural_plan_status != "PASS":
        structural_semantic_mapping = "NOT_EVALUATED"
    elif structural_changes_applied:
        structural_semantic_mapping = "NOT_EVALUATED"
    else:
        structural_semantic_mapping = "PASS"
    if run_intensity != "STRUCTURAL":
        structural_semantic_review_status = "NOT_APPLICABLE"
    elif not structural_changes_applied:
        structural_semantic_review_status = (
            "NOT_REQUIRED"
            if structural_plan_status == "PASS"
            else "NOT_EVALUATED"
        )
    elif len(structural_semantic_review_requests) == structural_changes_applied:
        structural_semantic_review_status = "PENDING_EXTERNAL_REVIEW"
    else:
        structural_semantic_review_status = "BLOCKED"

    paired_quality_units = {
        str(unit["unit_id"])
        for unit in units
        if str(unit.get("unit_id", "")) in expected_voice_units
        and str(unit.get("status", "")) in {"DONE", "NO_CHANGE"}
    }
    paired_quality_pending_units = {
        unit_id
        for unit_id in paired_quality_units
        if str(paired_quality_review_requests.get(unit_id, {}).get("status", ""))
        == "PENDING_EXTERNAL_REVIEW"
    }
    paired_quality_missing_units = paired_quality_units - set(
        paired_quality_review_requests
    )
    if not expected_voice_units:
        paired_quality_review_request_coverage_status = "NOT_APPLICABLE"
        paired_quality_gate_status = "NOT_APPLICABLE"
    elif paired_quality_missing_units or paired_quality_units != expected_voice_units:
        paired_quality_review_request_coverage_status = "REVIEW"
        paired_quality_gate_status = "BLOCKED"
    elif paired_quality_pending_units == expected_voice_units:
        paired_quality_review_request_coverage_status = "PASS"
        paired_quality_gate_status = "PENDING_EXTERNAL_REVIEW"
    else:
        paired_quality_review_request_coverage_status = "REVIEW"
        paired_quality_gate_status = "BLOCKED"
    paired_quality_clearance_granted = False
    rewrite_intent_pass_units = {
        unit_id
        for unit_id, record in rewrite_intent_evidence_records.items()
        if record.get("status") == "PASS"
        and unit_map.get(unit_id, {}).get("status") in {"DONE", "NO_CHANGE"}
    }
    rewrite_intent_review_units = {
        unit_id
        for unit_id, record in rewrite_intent_evidence_records.items()
        if record.get("status") == "REVIEW"
        and unit_map.get(unit_id, {}).get("status") in {"DONE", "NO_CHANGE"}
    }
    rewrite_intent_missing_units = expected_voice_units - set(
        rewrite_intent_evidence_records
    )
    if not expected_voice_units:
        rewrite_intent_coverage_status = "NOT_APPLICABLE"
    elif rewrite_intent_pass_units == expected_voice_units:
        rewrite_intent_coverage_status = "PASS"
    else:
        rewrite_intent_coverage_status = "REVIEW"
    for unit_id, record in rewrite_intent_evidence_records.items():
        paired_record = paired_quality_review_requests.get(unit_id)
        if isinstance(paired_record, dict):
            paired_record["rewrite_intent_evidence_path"] = record["path"]
            paired_record["rewrite_intent_evidence_sha256"] = record[
                "evidence_sha256"
            ]

    hard_failure = (
        bool(full_format_errors)
        or compile_result["status"] == "FAIL"
        or compile_or_concurrent_source_change
        or second_pass_evidence["status"] == "FAIL"
    )
    discard_staged_evidence = bool(
        compile_result.get("integrity_changes", {}).get("evidence_staging")
    )
    current_accepted_units = {
        unit["unit_id"] for unit in units if unit["status"] in {"DONE", "NO_CHANGE"}
    }
    partial_regression_units = sorted(previous_accepted_units - current_accepted_units)
    partial_regression = (existing_partial_before or existing_review_before) and (
        previous_partial_state_missing or bool(partial_regression_units)
    )
    if partial_regression:
        hard_failure = True
    complete = pending == 0 and not empty_processable_scope
    if hard_failure:
        candidate_assembly_status, candidate_assembly_exit_code = "FAIL", 1
    elif pending or unresolved or structural_transaction_candidates_pending:
        candidate_assembly_status, candidate_assembly_exit_code = "REVIEW", 2
    else:
        candidate_assembly_status, candidate_assembly_exit_code = "PASS", 0
    structural_semantic_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and structural_changes_applied
        and structural_semantic_mapping == "NOT_EVALUATED"
    )
    paired_quality_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and paired_quality_gate_status
        in {"PENDING_EXTERNAL_REVIEW", "BLOCKED"}
    )
    rewrite_intent_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and rewrite_intent_coverage_status != "PASS"
    )
    review_candidate_blocks_delivery = bool(
        structural_semantic_review_blocks_delivery
        or paired_quality_review_blocks_delivery
        or rewrite_intent_review_blocks_delivery
    )
    if review_candidate_blocks_delivery:
        status, exit_code = "REVIEW", 2
    else:
        status, exit_code = candidate_assembly_status, candidate_assembly_exit_code
    delivery_gate_status = status
    if candidate_assembly_status == "PASS":
        publish_name = (
            "rendered_review"
            if review_candidate_blocks_delivery
            else "rendered"
        )
    else:
        publish_name = "rendered_partial"
    publish_dir = run_dir / publish_name
    published_namespace_conflict = bool(
        (publish_name == "rendered_review" and existing_rendered_before)
        or (publish_name == "rendered" and existing_review_before)
    )
    if published_namespace_conflict:
        hard_failure = True
    idempotency = "NOT_RUN"
    preserve_published_evidence = False
    if partial_regression:
        rejected_dir = run_dir / "non_cumulative_staging"
        if rejected_dir.exists():
            shutil.rmtree(rejected_dir)
        staging_dir.rename(rejected_dir)
        published_path = str(run_dir / "rendered_partial")
        idempotency = "FAIL"
        preserve_published_evidence = True
    elif hard_failure:
        failed_dir = run_dir / "failed_staging"
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        staging_dir.rename(failed_dir)
        published_path = ""
        preserve_published_evidence = (
            existing_rendered_before
            or existing_partial_before
            or existing_review_before
        )
    elif publish_dir.exists():
        if _directory_hashes(publish_dir) == _directory_hashes(staging_dir):
            idempotency = "PASS"
            shutil.rmtree(staging_dir)
            published_path = str(publish_dir)
        elif publish_name in {"rendered_partial", "rendered_review"}:
            history_path = run_dir / "partial_history.jsonl"
            history = {
                "replaced_at": utc_now(),
                "old_hashes": _directory_hashes(publish_dir),
                "new_hashes": _directory_hashes(staging_dir),
                "reason": (
                    "revised_review_candidate"
                    if publish_name == "rendered_review"
                    else "additional_or_revised_unit_bundles"
                ),
            }
            with history_path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(json.dumps(history, ensure_ascii=False, sort_keys=True) + "\n")
            shutil.rmtree(publish_dir)
            staging_dir.rename(publish_dir)
            idempotency = "NOT_APPLICABLE_PROGRESS"
            published_path = str(publish_dir)
        else:
            different_dir = run_dir / "non_idempotent_staging"
            if different_dir.exists():
                shutil.rmtree(different_dir)
            staging_dir.rename(different_dir)
            idempotency = "FAIL"
            hard_failure = True
            published_path = str(publish_dir)
            preserve_published_evidence = True
    else:
        staging_dir.rename(publish_dir)
        published_path = str(publish_dir)

    stale_partial = run_dir / "rendered_partial"
    if (
        not hard_failure
        and publish_name in {"rendered", "rendered_review"}
        and stale_partial.exists()
    ):
        history_path = run_dir / "partial_history.jsonl"
        history = {
            "replaced_at": utc_now(),
            "old_hashes": _directory_hashes(stale_partial),
            "new_hashes": _directory_hashes(publish_dir),
            "reason": (
                "full_review_candidate_published"
                if publish_name == "rendered_review"
                else "full_terminal_coverage_published"
            ),
        }
        with history_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(history, ensure_ascii=False, sort_keys=True) + "\n")
        shutil.rmtree(stale_partial)

    if preserve_published_evidence or discard_staged_evidence:
        shutil.rmtree(validation_dir)
        shutil.rmtree(diffs_dir)
    else:
        _commit_evidence_directory(validation_dir, run_dir / "validation")
        _commit_evidence_directory(diffs_dir, run_dir / "diffs")
        for unit in units:
            raw_codes = unit.get("unresolved_codes", [])
            unit["unresolved_codes_json"] = _canonical_json(
                sorted(set(raw_codes)) if isinstance(raw_codes, list) else []
            )
        _write_csv(run_dir / "coverage_ledger.final.csv", units, LEDGER_FIELDS)
        _write_csv(
            run_dir / "rendered_manifest.csv",
            rendered_manifest,
            (
                "file_id",
                "source_path",
                "source_path_scope",
                "source_snapshot_copy",
                "source_snapshot_sha256",
                "rendered_path",
                "sha256",
                "sha256_scope",
                "rendered_sha256",
                "bytes",
                "format_check",
            ),
        )
    rollback = {
        "source_untouched": True,
        "snapshot_id": snapshot["snapshot_id"],
        "rollback_basis": "source/ snapshot copies and per-unit diffs",
        "published_path": published_path,
        "hard_failure": hard_failure,
        "action_on_failure": "Discard failed_staging/non_idempotent_staging; no source restoration is required.",
        "atomic_transactions": {
            transaction_id: {
                "unit_ids": list(result["unit_ids"]),
                "atomic_gate_status": result["atomic_gate_status"],
                "failure_gate": result["rollback_reason"],
                **_structural_transaction_atomic_counts(
                    result,
                    unit_map,
                    published=bool(published_path and not hard_failure),
                ),
            }
            for transaction_id, result in sorted(
                structural_transaction_results.items()
            )
        },
    }
    if not preserve_published_evidence and not discard_staged_evidence:
        _write_json(run_dir / "rollback_manifest.json", rollback)

    # Publication can still discover a non-idempotent candidate and upgrade the
    # assembly result to FAIL, so finalize the public statuses only afterwards.
    if hard_failure:
        candidate_assembly_status, candidate_assembly_exit_code = "FAIL", 1
    elif pending or unresolved or structural_transaction_candidates_pending:
        candidate_assembly_status, candidate_assembly_exit_code = "REVIEW", 2
    else:
        candidate_assembly_status, candidate_assembly_exit_code = "PASS", 0
    structural_semantic_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and structural_changes_applied
        and structural_semantic_mapping == "NOT_EVALUATED"
    )
    paired_quality_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and paired_quality_gate_status
        in {"PENDING_EXTERNAL_REVIEW", "BLOCKED"}
    )
    rewrite_intent_review_blocks_delivery = bool(
        candidate_assembly_status == "PASS"
        and rewrite_intent_coverage_status != "PASS"
    )
    review_candidate_blocks_delivery = bool(
        structural_semantic_review_blocks_delivery
        or paired_quality_review_blocks_delivery
        or rewrite_intent_review_blocks_delivery
    )
    if review_candidate_blocks_delivery:
        status, exit_code = "REVIEW", 2
    else:
        status, exit_code = candidate_assembly_status, candidate_assembly_exit_code
    delivery_gate_status = status

    coverage_completion_claim_allowed = bool(
        complete
        and unresolved == 0
        and not hard_failure
        and structural_transaction_candidate_coverage_status
        in {"PASS", "NOT_APPLICABLE"}
    )
    routed_units = [unit for unit in units if int(unit.get("author_chars", 0)) > 0]
    if not routed_units:
        scene_routing_status = "NOT_EVALUATED"
    elif (
        run_metadata.get("scene_routing_status") == "PASS"
        and all(
            str(unit.get("scene", "")).upper()
            in {"GENERAL", "COURSE", "MODELING", "RESEARCH"}
            and str(unit.get("scene_routing_decision", ""))
            in {"EXPLICIT", "ROUTED", "ROUTED_DOCUMENT_PRIOR", "FALLBACK_GENERAL"}
            and unit.get("scene_routing_policy_sha256")
            == run_metadata.get("scene_routing_policy_sha256")
            for unit in routed_units
        )
    ):
        scene_routing_status = "PASS"
    else:
        scene_routing_status = "REVIEW"
    voice_hash_missing_units.update(
        expected_voice_units - voice_hash_matched_units - voice_hash_mismatched_units
    )
    chunk_binding_missing_units.update(
        expected_voice_units
        - chunk_binding_matched_units
        - chunk_binding_mismatched_units
    )
    expected_authoring_binding_units = expected_voice_units - set(unit_to_transaction)
    authoring_binding_missing_units.update(
        expected_authoring_binding_units
        - authoring_binding_matched_units
        - authoring_binding_mismatched_units
    )
    if not expected_voice_units:
        voice_binding_status = "NOT_EVALUATED"
    elif voice_hash_matched_units == expected_voice_units:
        voice_binding_status = "PASS"
    else:
        voice_binding_status = "REVIEW"
    if not expected_voice_units:
        rewrite_binding_status = "NOT_EVALUATED"
    elif chunk_binding_matched_units == expected_voice_units:
        rewrite_binding_status = "PASS"
    else:
        rewrite_binding_status = "REVIEW"
    if not expected_authoring_binding_units:
        authoring_binding_status = "NOT_APPLICABLE"
    elif authoring_binding_matched_units == expected_authoring_binding_units:
        authoring_binding_status = "PASS"
    else:
        authoring_binding_status = "REVIEW"
    style_records = [
        {
            "unit_id": unit_id,
            "resolved_scene": unit.get("scene", ""),
            "document_id": document_id_by_file[str(unit.get("file_id", ""))],
            "expected": unit_id in expected_voice_units,
            "state": unit.get("status", ""),
            "style_validation": unit.get("style_validation", ""),
            "before_masked": chunks[unit_id].get("masked_text", ""),
            "after_masked": (
                chunks[unit_id].get("masked_text", "")
                if unit.get("status") == "NO_CHANGE"
                else accepted_masked_by_unit.get(unit_id)
                if unit.get("status") == "DONE"
                else None
            ),
        }
        for unit in units
        for unit_id in [str(unit["unit_id"])]
        if unit_id in expected_voice_units
    ]
    voice_conformance = _audit_voice_conformance_set(
        frozen_voice_profiles,
        style_records,
        scene_routing_status=scene_routing_status,
    )
    voice_conformance_status = str(voice_conformance["status"])
    cross_unit_repetition_status = str(cross_unit_repetition["status"])
    humanize_second_pass_convergence = str(second_pass_evidence["status"])
    second_pass_stability_status = {
        "PASS": "CONVERGENCE_OBSERVED",
        "REVIEW": "DISAGREEMENT_OR_INCOMPLETE",
        "FAIL": "INVALID_EVIDENCE",
        "NOT_RUN": "NOT_RUN",
    }.get(humanize_second_pass_convergence, "NOT_EVALUATED")
    voice_completion_claim_allowed = bool(
        coverage_completion_claim_allowed
        and scene_routing_status == "PASS"
        and voice_binding_status == "PASS"
        and rewrite_binding_status == "PASS"
        and authoring_binding_status in {"PASS", "NOT_APPLICABLE"}
        and voice_conformance_status == "PASS"
        and structural_plan_status in {"PASS", "NOT_APPLICABLE"}
        and structural_semantic_mapping in {"PASS", "NOT_APPLICABLE"}
    )
    humanize_completion_claim_allowed = bool(
        voice_completion_claim_allowed
        and rewrite_intent_coverage_status == "PASS"
        and cross_unit_repetition_status == "PASS"
        and humanize_second_pass_convergence == "PASS"
        and paired_quality_clearance_granted
    )
    metadata = {
        "tool": "finalize_humanize_long_document.py",
        "created_at": utc_now(),
        "snapshot_id": snapshot["snapshot_id"],
        "status": status,
        "exit_code": exit_code,
        "candidate_assembly_status": candidate_assembly_status,
        "candidate_assembly_exit_code": candidate_assembly_exit_code,
        "delivery_gate_status": delivery_gate_status,
        "publish_state": (
            "FAILED"
            if candidate_assembly_status == "FAIL"
            else "PARTIAL"
            if candidate_assembly_status == "REVIEW"
            else "REVIEW_CANDIDATE"
            if review_candidate_blocks_delivery
            else "FINAL"
        ),
        "units_total": len(units),
        "processable_editable_units": processable_editable_units,
        "unit_statuses": dict(sorted(statuses.items())),
        "unit_status_scope": "CANDIDATE_ASSEMBLY_NOT_DELIVERY",
        "unresolved_reason_summary": _unresolved_reason_summary(units),
        "file_statuses": dict(sorted(file_statuses.items())),
        "rewrites_submitted": len(rewrites) + sum(
            len(result["unit_ids"])
            for result in structural_transaction_results.values()
        ),
        "validation_results": {
            key: value["status"] for key, value in sorted(validation_payloads.items())
        },
        "mechanical_validation_results": {
            key: value.get("mechanical_validation_status", "NOT_RUN")
            for key, value in sorted(validation_payloads.items())
        },
        "full_format_errors": full_format_errors,
        "compile_check": compile_result,
        "published_path": published_path,
        "idempotency": idempotency,
        "assembly_replay_idempotency": idempotency,
        "humanize_second_pass_convergence": humanize_second_pass_convergence,
        "second_pass_stability_status": second_pass_stability_status,
        "second_pass_quality_clearance_granted": False,
        "humanize_second_pass_evidence": second_pass_evidence,
        "processable_scope_complete": complete,
        "processable_scope_complete_scope": "PROCESSABLE_UNIT_ACCOUNTING_ONLY",
        "processable_scope_complete_does_not_mean_resolved_or_deliverable": True,
        "empty_processable_scope": empty_processable_scope,
        "coverage_completion_claim_allowed": coverage_completion_claim_allowed,
        "paired_quality_review_request_coverage_status": (
            paired_quality_review_request_coverage_status
        ),
        "paired_quality_gate_status": paired_quality_gate_status,
        "paired_quality_review_requests": dict(
            sorted(paired_quality_review_requests.items())
        ),
        "paired_quality_units_total": len(paired_quality_units),
        "paired_quality_units_pending": len(paired_quality_pending_units),
        "paired_quality_units_missing": len(paired_quality_missing_units),
        "paired_quality_clearance_granted": paired_quality_clearance_granted,
        "paired_quality_local_clearance_supported": False,
        "paired_quality_limitations": (
            "request binding and coverage are deterministic; naturalness, independent "
            "benefit, collocation, hierarchy, and author-voice improvement remain "
            "PENDING_EXTERNAL_REVIEW"
        ),
        "rewrite_intent_coverage_status": rewrite_intent_coverage_status,
        "rewrite_intent_evidence": dict(
            sorted(rewrite_intent_evidence_records.items())
        ),
        "rewrite_intent_units_pass": len(rewrite_intent_pass_units),
        "rewrite_intent_units_review": len(rewrite_intent_review_units),
        "rewrite_intent_units_missing": len(rewrite_intent_missing_units),
        "rewrite_intent_blocks_delivery": rewrite_intent_review_blocks_delivery,
        "rewrite_intent_limitations": (
            "PASS binds declared intent, source line spans, masked diff coverage, bundle, "
            "before/after, diff, and paired-quality request hashes; it does not verify "
            "the truth of the rationale or independent reading benefit"
        ),
        "scene_routing_status": scene_routing_status,
        "intensity": run_intensity,
        "scene_routing_policy_sha256": run_metadata.get("scene_routing_policy_sha256", ""),
        "voice_binding_sha256": voice_identity["identity_sha256"],
        "voice_profile_sha256": voice_identity["voice_profile_sha256"],
        "voice_profile_set_sha256": voice_identity["profile_set_sha256"],
        "voice_profile_manifest_sha256": voice_identity["voice_profile_manifest_sha256"],
        "voice_profile_bindings_total": len(expected_voice_units),
        "voice_profile_bindings_matched": len(voice_hash_matched_units),
        "voice_profile_bindings_missing": len(voice_hash_missing_units),
        "voice_profile_bindings_mismatched": len(voice_hash_mismatched_units),
        "voice_profile_default_units": sum(
            1 for unit in units if str(unit.get("voice_profile_source")) == "SCENE_DEFAULT"
        ),
        "voice_profile_default_scenes": sorted(
            {
                str(unit.get("scene", ""))
                for unit in units
                if str(unit.get("voice_profile_source")) == "SCENE_DEFAULT"
            }
        ),
        "voice_default_disclosure_required": bool(voice_identity["voice_default_disclosure"]),
        "voice_binding_status": voice_binding_status,
        "rewrite_binding_status": rewrite_binding_status,
        "rewrite_bindings_total": len(expected_voice_units),
        "rewrite_bindings_matched": len(chunk_binding_matched_units),
        "rewrite_bindings_missing": len(chunk_binding_missing_units),
        "rewrite_bindings_mismatched": len(chunk_binding_mismatched_units),
        "authoring_binding_schema": LONG_AUTHORING_BINDING_SCHEMA,
        "authoring_binding_integrity_scope": (
            "CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY"
        ),
        "authoring_binding_status": authoring_binding_status,
        "authoring_bindings_total": len(expected_authoring_binding_units),
        "authoring_bindings_matched": len(authoring_binding_matched_units),
        "authoring_bindings_missing": len(authoring_binding_missing_units),
        "authoring_bindings_mismatched": len(authoring_binding_mismatched_units),
        "authoring_binding_transaction_units_not_applicable": len(
            expected_voice_units & set(unit_to_transaction)
        ),
        "structural_plan_status": structural_plan_status,
        "structural_plan_results": {
            key: value.get("status", "NOT_RUN")
            for key, value in sorted(structural_plan_payloads.items())
        },
        "structural_changes_applied": structural_changes_applied,
        "structural_semantic_mapping": structural_semantic_mapping,
        "structural_semantic_review_status": structural_semantic_review_status,
        "structural_semantic_review_requests": dict(
            sorted(structural_semantic_review_requests.items())
        ),
        "structural_transactions_total": len(structural_transaction_results),
        "structural_transaction_declines_total": len(
            bound_transaction_declines
        ),
        "structural_transaction_decline_results": dict(
            sorted(bound_transaction_declines.items())
        ),
        "structural_transaction_candidate_dispositions": dict(
            sorted(structural_transaction_candidate_dispositions.items())
        ),
        "structural_transaction_candidates_total": (
            structural_transaction_candidates_total
        ),
        "structural_transaction_candidates_executed": (
            structural_transaction_candidates_executed
        ),
        "structural_transaction_candidates_declined": (
            structural_transaction_candidates_declined
        ),
        "structural_transaction_candidates_pending": (
            structural_transaction_candidates_pending
        ),
        "structural_transaction_candidate_coverage_status": (
            structural_transaction_candidate_coverage_status
        ),
        "structural_transaction_scope_complete": (
            structural_transaction_scope_complete
        ),
        "structural_transaction_results": dict(
            sorted(structural_transaction_results.items())
        ),
        "structural_transaction_review_requests": dict(
            sorted(structural_transaction_review_requests.items())
        ),
        "structural_transaction_rolled_back_ids": sorted(
            transaction_id
            for transaction_id, result in structural_transaction_results.items()
            if result.get("atomic_gate_status") == "ROLLED_BACK"
        ),
        "structural_semantic_review_local_clearance_supported": False,
        "voice_conformance_status": voice_conformance_status,
        "cross_unit_repetition_status": cross_unit_repetition_status,
        "voice_conformance": voice_conformance,
        "cross_unit_repetition": cross_unit_repetition,
        "voice_completion_claim_allowed": voice_completion_claim_allowed,
        "humanize_completion_claim_allowed": humanize_completion_claim_allowed,
        "full_completion_claim_allowed": humanize_completion_claim_allowed,
        "source_files_modified": len(source_changes),
        "source_files_modified_by_tool": 0 if not source_changes else None,
        "source_files_changed_since_snapshot": len(source_changes),
        "source_change_details": source_changes,
        "source_changes_before_compile": len(source_changes_before_compile),
        "source_changed_during_compile_or_finalize": compile_or_concurrent_source_change,
        "run_artifacts_changed_during_check": bool(compile_result.get("integrity_changes", {}).get("run_dir")),
        "staging_artifacts_changed_during_check": bool(compile_result.get("integrity_changes", {}).get("staging")),
        "evidence_artifacts_changed_during_check": bool(
            compile_result.get("integrity_changes", {}).get("evidence_staging")
        ),
        "partial_regression_units": partial_regression_units,
        "previous_partial_state_missing": previous_partial_state_missing,
        "published_evidence_preserved": preserve_published_evidence,
        "staged_evidence_discarded": discard_staged_evidence,
        "published_namespace_conflict": published_namespace_conflict,
        "latest_attempt_metadata_path": "latest_attempt_metadata.json",
        "attempt_metadata_role": "CURRENT_AND_LATEST_ATTEMPT_AUTHORITY",
    }
    return metadata


def finalize(
    run_dir: Path,
    rewrites_dir: Path,
    *,
    check_command: str | None = None,
    check_timeout_seconds: float = DEFAULT_COMPILE_CHECK_TIMEOUT_SECONDS,
    second_pass_receipt: Path | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    rewrites_dir = Path(rewrites_dir)
    if _is_link_or_reparse(run_dir) or not run_dir.is_dir():
        raise ValueError("run directory must be an existing real directory")
    with _run_lock(run_dir):
        _recover_authority_group_journal(run_dir)
        _recover_run_state_journal(run_dir)
        with tempfile.TemporaryDirectory(
            prefix="humanize-finalize-transaction-"
        ) as temporary:
            transaction_id, backup_dir = _begin_run_state_transaction(run_dir)
            previous_finalization_metadata = (
                run_dir / "finalization_metadata.json"
            ).is_file()
            previous_published_evidence = _published_evidence_exists(run_dir)
            try:
                metadata = _finalize_locked(
                    run_dir,
                    rewrites_dir,
                    check_command=check_command,
                    check_timeout_seconds=check_timeout_seconds,
                    second_pass_receipt=second_pass_receipt,
                )
                restore_previous_state = bool(
                    metadata.get("published_evidence_preserved")
                    or metadata.get("run_artifacts_changed_during_check")
                )
                if restore_previous_state:
                    try:
                        _restore_run_state(run_dir, backup_dir)
                    except Exception as restore_error:
                        failure = _runtime_failure_metadata(
                            restore_error,
                            run_dir=run_dir,
                            run_state_restored=False,
                            finalization_metadata_preserved=False,
                            published_evidence_preserved=False,
                        )
                        failure.update(
                            {
                                "run_state_restore_status": "FAILED",
                                "run_state_restore_error_code": "RUN_STATE_RESTORE_FAILED",
                                "attempt_metadata_persistence_status": "FAILED",
                                "attempt_metadata_paths_authoritative": False,
                            }
                        )
                        try:
                            setattr(restore_error, "_humanize_failure_metadata", failure)
                        except Exception:
                            pass
                        raise
                    metadata = _failed_attempt_record(
                        metadata,
                        run_dir=run_dir,
                        finalization_metadata_preserved=(
                            previous_finalization_metadata
                        ),
                        published_evidence_preserved=previous_published_evidence,
                    )
                    _write_json_group_atomic(
                        (
                            (
                                run_dir / "last_failed_attempt_metadata.json",
                                metadata,
                            ),
                            (run_dir / "latest_attempt_metadata.json", metadata),
                        ),
                        transaction_id=transaction_id,
                        require_run_state_binding=True,
                    )
                    _cleanup_run_state_transaction(run_dir, transaction_id)
                    return metadata

                metadata.update(
                    {
                        "failed_attempt": False,
                        "run_state_restored_after_failure": False,
                        "finalization_metadata_preserved": False,
                        "failed_attempt_metadata_path": "",
                        "attempt_metadata_persistence_status": "PASS",
                        "attempt_metadata_group_atomic": True,
                        "attempt_metadata_paths_authoritative": True,
                    }
                )
                _write_json_group_atomic(
                    (
                        (run_dir / "finalization_metadata.json", metadata),
                        (run_dir / "latest_attempt_metadata.json", metadata),
                    ),
                    transaction_id=transaction_id,
                    require_run_state_binding=True,
                )
                _cleanup_run_state_transaction(run_dir, transaction_id)
                return metadata
            except BaseException as error:
                if bool(
                    getattr(error, "_humanize_authority_generation_committed", False)
                ):
                    try:
                        _cleanup_run_state_transaction(run_dir, transaction_id)
                    except BaseException:
                        pass
                    failure = _runtime_failure_metadata(
                        error,
                        run_dir=run_dir,
                        run_state_restored=False,
                        finalization_metadata_preserved=True,
                        published_evidence_preserved=True,
                    )
                    failure.update(
                        {
                            "run_state_restore_status": "NOT_ATTEMPTED_AFTER_AUTHORITY_COMMIT",
                            "attempt_metadata_persistence_status": "PASS",
                            "attempt_metadata_paths_authoritative": True,
                            "authority_generation_committed_before_interruption": True,
                        }
                    )
                    try:
                        setattr(error, "_humanize_failure_metadata", failure)
                    except Exception:
                        pass
                    raise
                try:
                    _restore_run_state(run_dir, backup_dir)
                except BaseException as restore_error:
                    failure = _runtime_failure_metadata(
                        error,
                        run_dir=run_dir,
                        run_state_restored=False,
                        finalization_metadata_preserved=False,
                        published_evidence_preserved=False,
                    )
                    failure.update(
                        {
                            "run_state_restore_status": "FAILED",
                            "run_state_restore_error_code": "RUN_STATE_RESTORE_FAILED",
                            "attempt_metadata_persistence_status": "FAILED",
                            "attempt_metadata_paths_authoritative": False,
                        }
                    )
                    try:
                        setattr(restore_error, "_humanize_failure_metadata", failure)
                    except Exception:
                        pass
                    raise restore_error from error
                failure = _runtime_failure_metadata(
                    error,
                    run_dir=run_dir,
                    run_state_restored=True,
                    finalization_metadata_preserved=(
                        previous_finalization_metadata
                    ),
                    published_evidence_preserved=previous_published_evidence,
                )
                try:
                    _write_json_group_atomic(
                        (
                            (
                                run_dir / "last_failed_attempt_metadata.json",
                                failure,
                            ),
                            (run_dir / "latest_attempt_metadata.json", failure),
                        ),
                        transaction_id=transaction_id,
                        require_run_state_binding=True,
                    )
                    _cleanup_run_state_transaction(run_dir, transaction_id)
                except BaseException:
                    failure["attempt_metadata_persistence_status"] = "FAILED"
                    failure["attempt_metadata_paths_authoritative"] = False
                try:
                    setattr(error, "_humanize_failure_metadata", failure)
                except Exception:
                    pass
                raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证长文单元改写、恢复保护区、生成逐节 diff 与派生稿；从不覆盖源文件。"
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="prepare 命令的输出目录")
    parser.add_argument(
        "--rewrites",
        type=Path,
        required=True,
        help="按 unit_id 命名的 .json/.txt，或绑定 STX inventory 的 transaction bundle 目录",
    )
    parser.add_argument("--check-command", help="可选项目编译/格式命令，在 staging 根目录执行")
    parser.add_argument(
        "--check-timeout-seconds",
        type=_validated_compile_timeout_seconds,
        default=DEFAULT_COMPILE_CHECK_TIMEOUT_SECONDS,
        help="编译/格式检查的正超时秒数（默认 300）",
    )
    parser.add_argument(
        "--second-pass-receipt",
        type=Path,
        help="verify_humanize_second_pass.py 产生的当前 rendered 绑定 receipt",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="stdout 格式；text 只显示权威交付状态和关键未决项",
    )
    return parser


def _render_text_summary(metadata: dict[str, Any]) -> str:
    delivery = metadata.get("delivery_gate_status", metadata.get("status", "UNKNOWN"))
    exit_code = metadata.get("exit_code", 1)
    publish_state = metadata.get("publish_state", "UNKNOWN")
    lines = [
        f"DELIVERY {delivery} exit={exit_code} publish={publish_state}",
        "status_authority=delivery_gate_status+process_exit_code",
    ]
    if metadata.get("runtime_error"):
        lines.append(
            "runtime_error="
            + str(metadata.get("error_type", "ERROR"))
            + ":"
            + str(metadata.get("error_code", "INTERNAL_ERROR"))
            + "; details=latest_attempt_metadata.json; content_redacted=true"
        )
        lines.append(
            "attempt_metadata_persistence="
            + str(metadata.get("attempt_metadata_persistence_status", "UNKNOWN"))
            + "; paths_authoritative="
            + str(
                bool(metadata.get("attempt_metadata_paths_authoritative"))
            ).lower()
        )
        return "\n".join(lines)
    lines.append(
        "candidate_assembly="
        + str(metadata.get("candidate_assembly_status", "NOT_RUN"))
        + "; paired_quality="
        + str(metadata.get("paired_quality_gate_status", "NOT_EVALUATED"))
    )
    lines.append(
        "latest_attempt=latest_attempt_metadata.json; "
        "canonical_candidate=finalization_metadata.json"
    )
    source_changes = metadata.get("source_files_changed_since_snapshot", 0)
    if isinstance(source_changes, int) and not isinstance(source_changes, bool) and source_changes:
        lines.append(
            f"source_snapshot=CHANGED count={source_changes}; "
            "unit_statuses_do_not_establish_current_source_coverage=true"
        )
    statuses = metadata.get("unit_statuses", {})
    if isinstance(statuses, dict):
        rendered_statuses = ",".join(
            f"{key}={value}" for key, value in sorted(statuses.items())
        )
        lines.append(
            f"units[{rendered_statuses}]; scope=CANDIDATE_ASSEMBLY_NOT_DELIVERY"
        )
    unresolved = metadata.get("unresolved_reason_summary", {})
    if isinstance(unresolved, dict) and unresolved.get("total", 0):
        codes = unresolved.get("codes", {})
        rendered_codes = ""
        if isinstance(codes, dict) and codes:
            rendered_codes = "; reason_codes[" + ",".join(
                f"{key}={value}" for key, value in sorted(codes.items())
            ) + "]"
        lines.append(
            "unresolved_details="
            + str(unresolved.get("details_artifact", "coverage_ledger.final.csv"))
            + rendered_codes
            + "; content_redacted=true"
        )
        structured_counts = unresolved.get("structured_code_counts", {})
        if isinstance(structured_counts, dict) and structured_counts:
            lines.append(
                "unresolved_code_counts["
                + ",".join(
                    f"{key}={value}"
                    for key, value in sorted(structured_counts.items())
                )
                + "]; schema="
                + str(
                    unresolved.get(
                        "structured_code_schema", UNRESOLVED_CODE_SCHEMA
                    )
                )
            )
        next_actions = unresolved.get("actionable_next_actions", [])
        if isinstance(next_actions, list) and next_actions:
            rendered_actions = []
            for item in next_actions:
                if not isinstance(item, dict):
                    continue
                reason_code = str(item.get("reason_code", ""))
                action = str(item.get("action", ""))
                if reason_code and action:
                    rendered_actions.append(f"{reason_code}={action}")
            if rendered_actions:
                lines.append("next_actions[" + ",".join(rendered_actions) + "]")
    published_path = str(metadata.get("published_path", ""))
    if published_path:
        label = "review_candidate" if publish_state == "REVIEW_CANDIDATE" else "published"
        lines.append(f"{label}={published_path}")
    compile_check = metadata.get("compile_check", {})
    if isinstance(compile_check, dict):
        lines.append(f"compile_check={compile_check.get('status', 'NOT_RUN')}")
    lines.append(
        "humanize_completion_claim_allowed="
        + str(bool(metadata.get("humanize_completion_claim_allowed"))).lower()
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        metadata = finalize(
            args.run_dir.resolve(),
            args.rewrites.resolve(),
            check_command=args.check_command,
            check_timeout_seconds=args.check_timeout_seconds,
            second_pass_receipt=args.second_pass_receipt,
        )
    except Exception as error:
        run_dir = args.run_dir.resolve(strict=False)
        metadata: dict[str, Any] | None = getattr(
            error, "_humanize_failure_metadata", None
        )
        if metadata is None:
            metadata = _runtime_failure_metadata(
                error,
                run_dir=run_dir,
                run_state_restored=False,
                finalization_metadata_preserved=False,
                published_evidence_preserved=False,
            )
        if args.format == "text":
            print(_render_text_summary(metadata))
        else:
            print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if args.format == "text":
        print(_render_text_summary(metadata))
    else:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return int(metadata["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
