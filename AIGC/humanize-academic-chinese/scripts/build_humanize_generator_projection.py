#!/usr/bin/env python3
"""Build a deterministic generator-only view of humanize-academic-chinese."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import load_humanize_negative_guards as negative_guards  # noqa: E402


DEFAULT_SKILL_ROOT = SCRIPT_DIR.parent
DEFAULT_POLICY = DEFAULT_SKILL_ROOT / "references" / "generator-projection-policy.json"
POLICY_SCHEMA = "humanize-generator-projection-policy/v1"
MANIFEST_SCHEMA = "humanize-generator-projection-manifest/v2"
TREE_SCHEMA = "humanize-generator-projection-tree/v1"
PUBLICATION_JOURNAL_SCHEMA = "humanize-generator-projection-publication-journal/v1"
PUBLICATION_STATES = {"ALLOCATED", "PREPARED", "OUTPUT_PUBLISHED", "COMMITTED"}
SKILL_TRANSFORM_ID = "strip-qualification-surface/v1"
FINALIZER_TRANSFORM_ID = "strip-second-pass-control-surface/v1"
LONG_WORKFLOW_TRANSFORM_ID = "strip-second-pass-workflow-surface/v1"
CORPUS_TRANSFORM_ID = "strip-to-negative-guard-registry/v4"
VALIDATOR_TRANSFORM_ID = "strip-paired-quality-policy-binding/v1"
BUILDER_VERSION = "1.56.0"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
CONTROL_ID_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:"
    r"(?:MODE|INT|OUT|DEC|ROUTE|VOICE|ROLE|PATH|LONG)-\d{2}(?:/[A-Za-z0-9_.-]+)*"
    r")(?![A-Za-z0-9_-])"
    ,
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:references|scripts)/[A-Za-z0-9_./-]+\.(?:md|json|py|txt|tex))"
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FORBIDDEN_CONTROL_LITERALS = (
    "oracle_suite_id",
    "qualification_stage",
    "runner_compatible",
    "generation-qualification-fixtures",
)

EXPECTED_INCLUDE = (
    "agents/openai.yaml",
    "references/course-notes.md",
    "references/detector-report-intake.md",
    "references/lexical-signals.json",
    "references/modeling-engineering.md",
    "references/modeling-reasoning-preservation.md",
    "references/operational-contract.md",
    "references/pathology-catalog.md",
    "references/quick-checklist.md",
    "references/research-journal.md",
    "references/rewrite-patterns.md",
    "references/scene-routing-policy.json",
    "references/short-patch-workflow.md",
    "references/style-gates.md",
    "references/structural-rewrite-contract.md",
    "references/source-provenance-trust.json",
    "references/system-prompt-contract.md",
    "references/voice-profile.md",
    "references/workflow.md",
    "scripts/amend_humanize_short_patch.py",
    "scripts/apply_humanize_short_patch.py",
    "scripts/audit_humanize_repetition_guards.py",
    "scripts/build_humanize_rewrite_intent.py",
    "scripts/build_humanize_short_patch.py",
    "scripts/build_humanize_voice_profile.py",
    "scripts/check_humanize_invariants.py",
    "scripts/extract_detector_report_scope.py",
    "scripts/humanize_short_patch_coverage.py",
    "scripts/load_humanize_negative_guards.py",
    "scripts/prepare_humanize_long_document.py",
    "scripts/scaffold_humanize_rewrites.py",
    "scripts/route_humanize_scene.py",
    "scripts/run_humanize_inline.py",
    "scripts/scaffold_humanize_short_patch.py",
    "scripts/scan_humanize_chinese.py",
    "scripts/validate_humanize_voice_profile.py",
    "scripts/verify_humanize_short_patch.py",
)
EXPECTED_TRANSFORM = {
    "SKILL.md": SKILL_TRANSFORM_ID,
    "references/corpus-action-sources.json": CORPUS_TRANSFORM_ID,
    "references/long-document-workflow.md": LONG_WORKFLOW_TRANSFORM_ID,
    "scripts/finalize_humanize_long_document.py": FINALIZER_TRANSFORM_ID,
    "scripts/validate_humanize_output.py": VALIDATOR_TRANSFORM_ID,
}
EXPECTED_EXCLUDE = (
    "references/paired-quality-clearance-contract.md",
    "references/evaluation-contract.md",
    "references/generation-qualification-oracles.json",
    "references/generation-qualification-requirements.json",
    "references/generation-qualification-trust.json",
    "references/generator-projection-policy.json",
    "scripts/audit_humanize_generation_qualification.py",
    "scripts/build_humanize_action_profile.py",
    "scripts/build_humanize_generator_projection.py",
    "scripts/prepare_humanize_candidate_revision.py",
    "scripts/prepare_humanize_second_pass.py",
    "scripts/capture_humanize_validation.py",
    "scripts/replay_humanize_validation_capture.py",
    "scripts/replay_humanize_validation_record.py",
    "scripts/replay_humanize_long_fixture.py",
    "scripts/run_humanize_generation_trial.py",
    "scripts/seal_humanize_public_fixture.py",
    "scripts/test_humanize_generator_projection.py",
    "scripts/validate_humanize_candidate_queue.py",
    "scripts/verify_humanize_second_pass.py",
    "scripts/verify_humanize_paired_quality_response.py",
)
EXPECTED_EXCLUDE_PREFIXES = (
    "build/",
    "references/generation-qualification-fixtures/",
)
EXPECTED_HOUSEKEEPING = (
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    ".pytest_cache/**",
)
EXPECTED_FORBIDDEN_BASENAMES = tuple(Path(item).name for item in EXPECTED_EXCLUDE)
TRANSFORM_REGISTRY = {
    SKILL_TRANSFORM_ID: "builtin/strict-markdown-span-removal/v1",
    FINALIZER_TRANSFORM_ID: "builtin/strict-python-span-replacement/v1",
    LONG_WORKFLOW_TRANSFORM_ID: "builtin/strict-markdown-section-replacement/v1",
    CORPUS_TRANSFORM_ID: "builtin/strict-json-provenance-filter/v1",
    VALIDATOR_TRANSFORM_ID: "builtin/strict-python-span-removal/v1",
}
TRANSFORM_DEPENDENCY_PATHS = (
    "scripts/load_humanize_negative_guards.py",
)


class ProjectionError(ValueError):
    """Raised when a projection cannot be proven to match the fixed policy."""


@dataclass(frozen=True)
class FrozenFile:
    path: str
    absolute: Path
    raw: bytes
    sha256: str
    size: int
    identity: tuple[int, int]
    mtime_ns: int


@dataclass(frozen=True)
class Policy:
    path: Path
    raw_sha256: str
    canonical_sha256: str
    policy_id: str
    policy_version: str
    approved_capability_source_sha256: str
    approved_builder_executable_sha256: str
    approved_transform_registry_sha256: str
    approved_transform_dependency_sha256: str
    include_exact: tuple[str, ...]
    transform_exact: Mapping[str, str]
    exclude_exact: tuple[str, ...]
    exclude_prefixes: tuple[str, ...]
    housekeeping_patterns: tuple[str, ...]
    required_entrypoint: str
    forbidden_reference_basenames: tuple[str, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ProjectionError(f"non-finite JSON number in {label}: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ProjectionError(f"{label} is not strict UTF-8 JSON: {error}") from error


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _same_path(left: Path, right: Path) -> bool:
    """Compare paths without following a path that may not exist yet."""
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _fsync_parent(path: Path) -> None:
    """Best-effort directory durability for platforms that expose it."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_atomic_file(path: Path, raw: bytes) -> None:
    """Atomically replace a small control file and flush its contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.staging-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_parent(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _publication_journal_path(manifest_path: Path) -> Path:
    return manifest_path.with_name(f"{manifest_path.name}.journal")


def _publication_journal_payload(
    *,
    state: str,
    output_root: Path,
    manifest_path: Path,
    staging_root: Path,
    manifest_staging_path: Path,
    projection_tree_sha256: str | None = None,
    manifest_sha256: str | None = None,
    manifest_size: int | None = None,
) -> dict[str, Any]:
    if state not in PUBLICATION_STATES:
        raise ProjectionError(f"unknown publication journal state: {state}")
    return {
        "schema_version": PUBLICATION_JOURNAL_SCHEMA,
        "state": state,
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "staging_root": str(staging_root),
        "manifest_staging_path": str(manifest_staging_path),
        "projection_tree_sha256": projection_tree_sha256,
        "manifest_sha256": manifest_sha256,
        "manifest_size": manifest_size,
    }


def _journal_control_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProjectionError(f"publication journal {label} is invalid")
    return value


def _validate_publication_journal(
    journal_path: Path,
    output_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        info = journal_path.lstat()
    except OSError as error:
        raise ProjectionError(f"publication journal is unreadable: {error}") from error
    if stat.S_ISLNK(info.st_mode) or _is_reparse(journal_path, info) or not stat.S_ISREG(info.st_mode):
        raise ProjectionError("publication journal must be a regular non-reparse file")
    raw = journal_path.read_bytes()
    payload = _strict_json(raw, "publication journal")
    if not isinstance(payload, dict):
        raise ProjectionError("publication journal must be an object")
    _exact_keys(
        payload,
        {
            "schema_version",
            "state",
            "output_root",
            "manifest_path",
            "staging_root",
            "manifest_staging_path",
            "projection_tree_sha256",
            "manifest_sha256",
            "manifest_size",
        },
        "publication journal",
    )
    if payload.get("schema_version") != PUBLICATION_JOURNAL_SCHEMA:
        raise ProjectionError("publication journal schema drifted")
    state = payload.get("state")
    if state not in PUBLICATION_STATES:
        raise ProjectionError("publication journal state is invalid")
    for key, expected in (
        ("output_root", output_root),
        ("manifest_path", manifest_path),
    ):
        value = payload.get(key)
        if not isinstance(value, str) or not _same_path(Path(value), expected):
            raise ProjectionError(f"publication journal {key} does not match this invocation")
    staging = payload.get("staging_root")
    manifest_staging = payload.get("manifest_staging_path")
    if not isinstance(staging, str) or not isinstance(manifest_staging, str):
        raise ProjectionError("publication journal staging paths are invalid")
    staging_path = Path(staging)
    manifest_staging_path = Path(manifest_staging)
    if staging_path.parent != output_root.parent or not staging_path.name.startswith(
        f".{output_root.name}.staging-"
    ):
        raise ProjectionError("publication journal staging root is unsafe")
    if manifest_staging_path.parent != manifest_path.parent or not manifest_staging_path.name.startswith(
        f".{manifest_path.name}.staging-"
    ):
        raise ProjectionError("publication journal manifest staging path is unsafe")
    if _same_path(staging_path, output_root) or _same_path(manifest_staging_path, manifest_path):
        raise ProjectionError("publication journal staging path aliases a final path")
    tree_hash = payload.get("projection_tree_sha256")
    manifest_hash = payload.get("manifest_sha256")
    manifest_size = payload.get("manifest_size")
    if state == "ALLOCATED":
        if any(value is not None for value in (tree_hash, manifest_hash, manifest_size)):
            raise ProjectionError("allocated publication journal must not contain final hashes")
    else:
        _journal_control_hash(tree_hash, "projection_tree_sha256")
        _journal_control_hash(manifest_hash, "manifest_sha256")
        if not isinstance(manifest_size, int) or isinstance(manifest_size, bool) or manifest_size < 0:
            raise ProjectionError("publication journal manifest_size is invalid")
    return payload


def _safe_remove_publication_path(path: Path, *, directory: bool) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or _is_reparse(path, info):
        raise ProjectionError(f"refusing to remove reparse publication path: {path}")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ProjectionError(f"publication staging path is not a directory: {path}")
        for child in path.rglob("*"):
            child_info = child.lstat()
            if stat.S_ISLNK(child_info.st_mode) or _is_reparse(child, child_info):
                raise ProjectionError(f"publication staging contains a reparse path: {child}")
        shutil.rmtree(path)
    else:
        if not stat.S_ISREG(info.st_mode):
            raise ProjectionError(f"publication manifest staging path is not a file: {path}")
        path.unlink()


def _directory_tree_hash(root: Path) -> str:
    if not root.exists():
        raise ProjectionError(f"publication output is missing: {root}")
    info = root.lstat()
    if stat.S_ISLNK(info.st_mode) or _is_reparse(root, info) or not stat.S_ISDIR(info.st_mode):
        raise ProjectionError("publication output must be a regular non-reparse directory")
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().encode("utf-8")):
        item_info = path.lstat()
        if stat.S_ISLNK(item_info.st_mode) or _is_reparse(path, item_info):
            raise ProjectionError(f"publication output contains a reparse path: {path}")
        if path.is_dir():
            continue
        if not stat.S_ISREG(item_info.st_mode):
            raise ProjectionError(f"publication output contains a non-regular file: {path}")
        relative = _safe_relative_path(path.relative_to(root).as_posix(), "publication output path")
        raw = path.read_bytes()
        after = path.lstat()
        if (
            (item_info.st_dev, item_info.st_ino, item_info.st_size, item_info.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or len(raw) != after.st_size
        ):
            raise ProjectionError(f"publication output changed while hashed: {relative}")
        files[relative] = raw
    return _tree_hash(files)


def _recover_publication_journal(
    journal_path: Path,
    output_root: Path,
    manifest_path: Path,
) -> None:
    try:
        journal_path.lstat()
    except FileNotFoundError:
        return
    payload = _validate_publication_journal(journal_path, output_root, manifest_path)
    state = payload["state"]
    staging = Path(payload["staging_root"])
    manifest_staging = Path(payload["manifest_staging_path"])

    def remove_temps() -> None:
        _safe_remove_publication_path(staging, directory=True)
        _safe_remove_publication_path(manifest_staging, directory=False)

    if state == "ALLOCATED":
        if output_root.exists() or manifest_path.exists():
            raise ProjectionError("allocated publication journal conflicts with final paths")
        remove_temps()
    elif state == "PREPARED":
        if manifest_path.exists():
            raise ProjectionError("prepared publication journal has a final manifest")
        if output_root.exists():
            if _directory_tree_hash(output_root) != payload["projection_tree_sha256"]:
                raise ProjectionError("prepared publication output hash does not match journal")
            _safe_remove_publication_path(output_root, directory=True)
        remove_temps()
    elif state == "OUTPUT_PUBLISHED":
        if not output_root.exists():
            if manifest_path.exists():
                raise ProjectionError("published manifest exists without its output directory")
            remove_temps()
        elif _directory_tree_hash(output_root) != payload["projection_tree_sha256"]:
            raise ProjectionError("published output hash does not match journal")
        if manifest_path.exists():
            manifest_raw = manifest_path.read_bytes()
            if len(manifest_raw) != payload["manifest_size"] or _sha256(manifest_raw) != payload["manifest_sha256"]:
                raise ProjectionError("published manifest does not match journal")
            remove_temps()
        else:
            if not manifest_staging.exists():
                raise ProjectionError("published output has no manifest or manifest staging file")
            manifest_raw = manifest_staging.read_bytes()
            if len(manifest_raw) != payload["manifest_size"] or _sha256(manifest_raw) != payload["manifest_sha256"]:
                raise ProjectionError("manifest staging does not match journal")
            os.replace(manifest_staging, manifest_path)
            _fsync_parent(manifest_path.parent)
            _safe_remove_publication_path(staging, directory=True)
    elif state == "COMMITTED":
        if not output_root.exists() or not manifest_path.exists():
            raise ProjectionError("committed publication journal is missing a final path")
        if _directory_tree_hash(output_root) != payload["projection_tree_sha256"]:
            raise ProjectionError("committed output hash does not match journal")
        manifest_raw = manifest_path.read_bytes()
        if len(manifest_raw) != payload["manifest_size"] or _sha256(manifest_raw) != payload["manifest_sha256"]:
            raise ProjectionError("committed manifest does not match journal")
        remove_temps()
    else:  # pragma: no cover - guarded by journal validation
        raise ProjectionError("unhandled publication journal state")
    try:
        journal_path.unlink()
        _fsync_parent(journal_path.parent)
    except FileNotFoundError:
        pass


def _builder_executable_sha256() -> str:
    return _sha256(Path(__file__).resolve().read_bytes())


def _transform_registry_sha256() -> str:
    return _sha256(_canonical_json(TRANSFORM_REGISTRY))


def _transform_dependency_sha256(root: Path = DEFAULT_SKILL_ROOT) -> str:
    records = []
    for relative in TRANSFORM_DEPENDENCY_PATHS:
        raw = (root / PurePosixPath(relative)).read_bytes()
        records.append({"path": relative, "sha256": _sha256(raw), "size": len(raw)})
    return _sha256(_canonical_json(records))


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ProjectionError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProjectionError(f"{label} must be a non-empty POSIX relative path")
    if value != unicodedata.normalize("NFC", value):
        raise ProjectionError(f"{label} must be NFC-normalized")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProjectionError(f"{label} is not a safe relative path")
    for part in path.parts:
        if part.endswith((" ", ".")) or ":" in part:
            raise ProjectionError(f"{label} contains a Windows-unsafe component")
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise ProjectionError(f"{label} contains a reserved device name")
    return path.as_posix()


def _string_array(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProjectionError(f"{label} must be a string array")
    result = tuple(_safe_relative_path(item, f"{label}[]") for item in value)
    if len(result) != len(set(result)):
        raise ProjectionError(f"{label} contains duplicates")
    return result


def _prefix_array(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.endswith("/") for item in value
    ):
        raise ProjectionError(f"{label} must be an array of POSIX directory prefixes")
    result = tuple(
        _safe_relative_path(item[:-1], f"{label}[]") + "/" for item in value
    )
    if len(result) != len(set(result)):
        raise ProjectionError(f"{label} contains duplicates")
    return result


def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    if path.is_symlink():
        raise ProjectionError("projection policy must not be a symlink")
    raw = path.read_bytes()
    payload = _strict_json(raw, "projection policy")
    if not isinstance(payload, dict):
        raise ProjectionError("projection policy must be an object")
    _exact_keys(
        payload,
        {
            "schema_version",
            "policy_id",
            "policy_version",
            "approved_capability_source_sha256",
            "approved_builder_executable_sha256",
            "approved_transform_registry_sha256",
            "approved_transform_dependency_sha256",
            "source_root_basename",
            "include_exact",
            "transform_exact",
            "exclude_exact",
            "exclude_prefixes",
            "housekeeping_patterns",
            "required_entrypoint",
            "forbidden_reference_basenames",
        },
        "projection policy",
    )
    if payload.get("schema_version") != POLICY_SCHEMA:
        raise ProjectionError(f"projection policy schema must be {POLICY_SCHEMA}")
    if payload.get("policy_id") != "humanize-academic-chinese/generator/v1":
        raise ProjectionError("projection policy_id drifted")
    if payload.get("policy_version") != BUILDER_VERSION:
        raise ProjectionError("projection policy_version drifted")
    approved_capability_hash = payload.get("approved_capability_source_sha256")
    if not isinstance(approved_capability_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", approved_capability_hash
    ):
        raise ProjectionError("approved_capability_source_sha256 must be a lowercase SHA-256")
    approval_hashes = {
        "approved_builder_executable_sha256": _builder_executable_sha256(),
        "approved_transform_registry_sha256": _transform_registry_sha256(),
        "approved_transform_dependency_sha256": _transform_dependency_sha256(),
    }
    for key, current in approval_hashes.items():
        value = payload.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ProjectionError(f"{key} must be a lowercase SHA-256")
        if value != current:
            raise ProjectionError(f"{key} does not approve the executing builder semantics")
    if payload.get("source_root_basename") != "humanize-academic-chinese":
        raise ProjectionError("projection source_root_basename drifted")
    include = _string_array(payload.get("include_exact"), "include_exact")
    exclude = _string_array(payload.get("exclude_exact"), "exclude_exact")
    prefixes = _prefix_array(payload.get("exclude_prefixes"), "exclude_prefixes")
    housekeeping = payload.get("housekeeping_patterns")
    if not isinstance(housekeeping, list) or not all(
        isinstance(item, str) and item for item in housekeeping
    ):
        raise ProjectionError("housekeeping_patterns must be a string array")
    transform = payload.get("transform_exact")
    if not isinstance(transform, dict):
        raise ProjectionError("transform_exact must be an object")
    normalized_transform = {
        _safe_relative_path(key, "transform_exact path"): value
        for key, value in transform.items()
    }
    required = _safe_relative_path(payload.get("required_entrypoint"), "required_entrypoint")
    forbidden = payload.get("forbidden_reference_basenames")
    if not isinstance(forbidden, list) or not all(
        isinstance(item, str) and item == Path(item).name for item in forbidden
    ):
        raise ProjectionError("forbidden_reference_basenames is invalid")
    if include != EXPECTED_INCLUDE:
        raise ProjectionError("projection include_exact drifted from the built-in closed set")
    if normalized_transform != EXPECTED_TRANSFORM:
        raise ProjectionError("projection transform_exact drifted")
    if exclude != EXPECTED_EXCLUDE:
        raise ProjectionError("projection exclude_exact drifted from the evaluation surface")
    if prefixes != EXPECTED_EXCLUDE_PREFIXES:
        raise ProjectionError("projection exclude_prefixes drifted")
    if tuple(housekeeping) != EXPECTED_HOUSEKEEPING:
        raise ProjectionError("projection housekeeping_patterns drifted")
    if required != "SKILL.md":
        raise ProjectionError("projection required_entrypoint drifted")
    if tuple(forbidden) != EXPECTED_FORBIDDEN_BASENAMES:
        raise ProjectionError("projection forbidden basenames drifted")
    return Policy(
        path=path.resolve(strict=True),
        raw_sha256=_sha256(raw),
        canonical_sha256=_sha256(_canonical_json(payload)),
        policy_id=str(payload["policy_id"]),
        policy_version=str(payload["policy_version"]),
        approved_capability_source_sha256=approved_capability_hash,
        approved_builder_executable_sha256=str(
            payload["approved_builder_executable_sha256"]
        ),
        approved_transform_registry_sha256=str(
            payload["approved_transform_registry_sha256"]
        ),
        approved_transform_dependency_sha256=str(
            payload["approved_transform_dependency_sha256"]
        ),
        include_exact=include,
        transform_exact=normalized_transform,
        exclude_exact=exclude,
        exclude_prefixes=prefixes,
        housekeeping_patterns=tuple(housekeeping),
        required_entrypoint=required,
        forbidden_reference_basenames=tuple(forbidden),
    )


def _is_reparse(path: Path, info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def _verified_directory_root(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    try:
        supplied_info = absolute.lstat()
    except OSError as error:
        raise ProjectionError(f"{label} is unreadable: {error}") from error
    if (
        stat.S_ISLNK(supplied_info.st_mode)
        or _is_reparse(absolute, supplied_info)
        or not stat.S_ISDIR(supplied_info.st_mode)
    ):
        raise ProjectionError(f"{label} must be a regular non-reparse directory")
    resolved = absolute.resolve(strict=True)
    resolved_info = resolved.lstat()
    if (supplied_info.st_dev, supplied_info.st_ino) != (
        resolved_info.st_dev,
        resolved_info.st_ino,
    ):
        raise ProjectionError(f"{label} identity changed during resolution")
    return resolved


def _read_frozen(path: Path, relative: str) -> FrozenFile:
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or _is_reparse(path, before):
        raise ProjectionError(f"source path is a symlink or reparse point: {relative}")
    if not stat.S_ISREG(before.st_mode):
        raise ProjectionError(f"source path is not a regular file: {relative}")
    raw = path.read_bytes()
    after = path.lstat()
    before_state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_state = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_state != after_state or len(raw) != after.st_size:
        raise ProjectionError(f"source changed while being snapshotted: {relative}")
    return FrozenFile(
        path=relative,
        absolute=path,
        raw=raw,
        sha256=_sha256(raw),
        size=len(raw),
        identity=(after.st_dev, after.st_ino),
        mtime_ns=after.st_mtime_ns,
    )


def _housekeeping(path: str, patterns: Sequence[str]) -> bool:
    parts = PurePosixPath(path).parts
    if "__pycache__" in parts or path.endswith((".pyc", ".pyo")):
        return True
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _classify(path: str, policy: Policy) -> str:
    if path in policy.include_exact:
        return "INCLUDE"
    if path in policy.transform_exact:
        return "TRANSFORM"
    if path in policy.exclude_exact or any(
        path.startswith(prefix) for prefix in policy.exclude_prefixes
    ):
        return "EXCLUDE"
    if _housekeeping(path, policy.housekeeping_patterns):
        return "HOUSEKEEPING"
    return "UNKNOWN"


def _inventory(source_root: Path, policy: Policy) -> tuple[list[FrozenFile], dict[str, str]]:
    if source_root.name != "humanize-academic-chinese":
        raise ProjectionError("source root basename does not match the fixed policy")
    frozen: list[FrozenFile] = []
    dispositions: dict[str, str] = {}
    collision_keys: dict[str, str] = {}
    identities: dict[tuple[int, int], str] = {}
    for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix().encode("utf-8")):
        relative = _safe_relative_path(path.relative_to(source_root).as_posix(), "source path")
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or _is_reparse(path, info):
            raise ProjectionError(f"source contains a symlink or reparse point: {relative}")
        if path.is_dir():
            continue
        folded = unicodedata.normalize("NFC", relative).casefold()
        if folded in collision_keys:
            raise ProjectionError(
                f"source path casefold/NFC collision: {collision_keys[folded]} and {relative}"
            )
        collision_keys[folded] = relative
        disposition = _classify(relative, policy)
        dispositions[relative] = disposition
        if disposition == "UNKNOWN":
            raise ProjectionError(f"unclassified source file: {relative}")
        if disposition == "HOUSEKEEPING":
            continue
        item = _read_frozen(path, relative)
        if item.identity in identities:
            raise ProjectionError(
                f"source hard-link identity is shared by {identities[item.identity]} and {relative}"
            )
        identities[item.identity] = relative
        frozen.append(item)
    expected = set(policy.include_exact) | set(policy.transform_exact) | set(policy.exclude_exact)
    missing = sorted(expected - set(dispositions))
    if missing:
        raise ProjectionError(f"policy paths are absent from source: {missing}")
    return frozen, dispositions


def _line_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        spans.append((offset, end, line))
        offset = end
    if not text.endswith("\n") and (not spans or spans[-1][1] != len(text)):
        spans.append((offset, len(text), text[offset:]))
    return spans


def _markdown_h2_positions(text: str) -> list[tuple[str, int]]:
    positions: list[tuple[str, int]] = []
    fenced: str | None = None
    for start, _end, line in _line_spans(text):
        stripped = line.lstrip()
        fence_match = re.match(r"(```+|~~~+)", stripped)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fenced is None:
                fenced = marker
            elif fenced == marker:
                fenced = None
            continue
        if fenced is None and line.startswith("## "):
            positions.append((line.rstrip("\n"), start))
    if fenced is not None:
        raise ProjectionError("SKILL.md contains an unclosed fenced code block")
    return positions


def _transform_skill(raw: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise ProjectionError(f"SKILL.md is not strict UTF-8: {error}") from error
    if "\ufffd" in text or "\x00" in text:
        raise ProjectionError("SKILL.md contains replacement or NUL characters")
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        raise ProjectionError("SKILL.md contains a bare carriage return")
    if not text.startswith("---\n"):
        raise ProjectionError("SKILL.md must start with YAML frontmatter")
    frontmatter_end = text.find("\n---\n", 4)
    if frontmatter_end < 0:
        raise ProjectionError("SKILL.md frontmatter is not closed")
    frontmatter = text[4:frontmatter_end]
    keys = [line.split(":", 1)[0].strip() for line in frontmatter.splitlines() if ":" in line]
    if keys != ["name", "description"]:
        raise ProjectionError("SKILL.md frontmatter keys drifted")
    required_headings = ("## 引用路由", "## 生成资格采集边界", "## 来源锚定的改写候选")
    heading_positions = _markdown_h2_positions(text)
    for heading in required_headings:
        matches = [offset for label, offset in heading_positions if label == heading]
        if len(matches) != 1 or text.count(heading + "\n") != 1:
            raise ProjectionError(f"SKILL.md requires exactly one unfenced heading: {heading}")
    position_by_heading = dict(heading_positions)
    route_start = position_by_heading["## 引用路由"]
    route_index = next(
        index for index, item in enumerate(heading_positions) if item[1] == route_start
    )
    if route_index + 1 >= len(heading_positions):
        raise ProjectionError("SKILL.md 引用路由 section has no closing heading")
    route_next = heading_positions[route_index + 1][1]
    qualification_start = position_by_heading["## 生成资格采集边界"]
    source_anchor_start = position_by_heading["## 来源锚定的改写候选"]
    qualification_index = next(
        index
        for index, item in enumerate(heading_positions)
        if item[1] == qualification_start
    )
    if (
        qualification_index + 1 >= len(heading_positions)
        or heading_positions[qualification_index + 1]
        != ("## 来源锚定的改写候选", source_anchor_start)
    ):
        raise ProjectionError(
            "SKILL.md 来源锚定 section must be the immediate next H2 after qualification"
        )
    if not (route_start < route_next <= qualification_start < source_anchor_start):
        raise ProjectionError("SKILL.md qualification heading order drifted")
    spans: list[tuple[int, int, str]] = []
    route_text = text[route_start:route_next]
    route_offset = route_start
    for label in ("来源动作候选审计", "验证 Skill", "生成资格审计"):
        matches: list[tuple[int, int]] = []
        for start, end, line in _line_spans(route_text):
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.rstrip("\n").split("|")[1:-1]]
            if cells and cells[0] == label:
                matches.append((route_offset + start, route_offset + end))
        if len(matches) != 1:
            raise ProjectionError(f"SKILL.md route table requires exactly one {label} row")
        spans.append((*matches[0], f"route-row:{label}"))
    source_anchor_index = next(
        index
        for index, item in enumerate(heading_positions)
        if item[1] == source_anchor_start
    )
    if source_anchor_index + 1 >= len(heading_positions):
        raise ProjectionError("SKILL.md 来源锚定 section has no closing heading")
    source_anchor_end = heading_positions[source_anchor_index + 1][1]
    spans.append(
        (
            qualification_start,
            source_anchor_end,
            "sections:生成资格与来源候选审计",
        )
    )
    control_start_marker = "<!-- GENERATOR_PROJECTION_CONTROL_BEGIN:SECOND_PASS -->\n"
    control_end_marker = "<!-- GENERATOR_PROJECTION_CONTROL_END:SECOND_PASS -->\n"
    if text.count(control_start_marker) != 1 or text.count(control_end_marker) != 1:
        raise ProjectionError("SKILL.md second-pass control markers drifted")
    control_start = text.index(control_start_marker)
    control_end = text.index(control_end_marker, control_start) + len(control_end_marker)
    spans.append((control_start, control_end, "control:SECOND_PASS"))
    spans.sort()
    for left, right in zip(spans, spans[1:]):
        if left[1] > right[0]:
            raise ProjectionError("SKILL.md removal spans overlap")
    records: list[dict[str, Any]] = []
    for start, end, label in spans:
        removed = text[start:end].encode("utf-8")
        records.append(
            {
                "label": label,
                "normalized_source_byte_range": [
                    len(text[:start].encode("utf-8")),
                    len(text[:end].encode("utf-8")),
                ],
                "sha256": _sha256(removed),
                "size": len(removed),
            }
        )
    projected = text
    for start, end, _label in reversed(spans):
        projected = projected[:start] + projected[end:]
    if "## 生成资格采集边界" in projected:
        raise ProjectionError("SKILL.md qualification section survived transformation")
    if "## 来源锚定的改写候选" in projected:
        raise ProjectionError("SKILL.md source candidate audit section survived transformation")
    projected_folded = unicodedata.normalize("NFC", projected).casefold()
    for forbidden_route in (
        "build_humanize_generator_projection.py",
        "validate_humanize_candidate_queue.py",
        "prepare_humanize_candidate_revision.py",
    ):
        if forbidden_route.casefold() in projected_folded:
            raise ProjectionError(f"SKILL.md audit-only route survived transformation: {forbidden_route}")
    if "GENERATOR_PROJECTION_CONTROL" in projected:
        raise ProjectionError("SKILL.md second-pass control markers survived transformation")
    return projected.encode("utf-8"), records


def _transform_finalizer(raw: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as error:
        raise ProjectionError(
            f"finalize_humanize_long_document.py is not strict UTF-8: {error}"
        ) from error
    if "\ufffd" in text or "\x00" in text or "\r" in text:
        raise ProjectionError(
            "finalize_humanize_long_document.py contains invalid normalized text"
        )
    start_anchor = "def _second_pass_tree_hash(root: Path) -> str:\n"
    end_anchor = "\n\nVOICE_UNIT_FIELDS = ("
    if text.count(start_anchor) != 1 or text.count(end_anchor) != 1:
        raise ProjectionError("finalizer second-pass control anchors drifted")
    start = text.index(start_anchor)
    end = text.index(end_anchor, start)
    removed = text[start:end]
    replacement = '''def _validate_second_pass_receipt(\n    receipt_path: Path,\n    *,\n    snapshot_id: str,\n    rendered_root: Path,\n    rendered_manifest_path: Path,\n    voice_binding_sha256: str,\n    scene: str,\n) -> dict[str, Any]:\n    raise ValueError(\n        "second-pass control-plane verification is unavailable in generator projection"\n    )\n'''
    projected = text[:start] + replacement + text[end:]
    help_control = "verify_humanize_second_pass.py 产生的当前 rendered 绑定 receipt"
    if projected.count(help_control) != 1:
        raise ProjectionError("finalizer second-pass CLI help anchor drifted")
    projected = projected.replace(
        help_control,
        "控制面 verifier 产生的当前 rendered 绑定 receipt",
        1,
    )
    forbidden = (
        "all_units_no_change",
        "second_output_equals_first",
        "verify_humanize_second_pass.py",
        "expected_outcome_exposed",
    )
    leaked = [token for token in forbidden if token in projected]
    if leaked:
        raise ProjectionError(
            "finalizer second-pass control survived transformation: " + leaked[0]
        )
    record = {
        "label": "python-span:second-pass-control",
        "normalized_source_byte_range": [
            len(text[:start].encode("utf-8")),
            len(text[:end].encode("utf-8")),
        ],
        "sha256": _sha256(removed.encode("utf-8")),
        "size": len(removed.encode("utf-8")),
    }
    return projected.encode("utf-8"), [record]


def _transform_validator(raw: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as error:
        raise ProjectionError(f"validate_humanize_output.py is not strict UTF-8: {error}") from error
    if "\ufffd" in text or "\x00" in text or "\r" in text:
        raise ProjectionError("validate_humanize_output.py contains invalid normalized text")

    removed_blocks = (
        (
            "python-span:paired-quality-path-constants",
            '_PAIRED_QUALITY_CONTRACT_NAME = "paired" + "-quality-clearance-contract.md"\n'
            '_PAIRED_QUALITY_VERIFIER_NAME = "verify" + "_humanize_paired_quality_response.py"\n',
        ),
        (
            "python-span:paired-quality-implementation-hashes",
            '''    paths.update(\n        {\n            "paired_quality_verifier_sha256": skill_root\n            / "scripts"\n            / _PAIRED_QUALITY_VERIFIER_NAME,\n            "paired_quality_contract_sha256": skill_root\n            / "references"\n            / _PAIRED_QUALITY_CONTRACT_NAME,\n        }\n    )\n''',
        ),
        (
            "python-span:paired-quality-contract-hash",
            '''        "paired_quality_clearance_contract": skill_root\n        / "references"\n        / _PAIRED_QUALITY_CONTRACT_NAME,\n''',
        ),
    )
    spans: list[tuple[int, int, str, str]] = []
    for label, block in removed_blocks:
        if text.count(block) != 1:
            raise ProjectionError(f"validator paired-quality policy anchor drifted: {label}")
        start = text.index(block)
        spans.append((start, start + len(block), label, block))
    spans.sort()
    if any(current[1] > following[0] for current, following in zip(spans, spans[1:])):
        raise ProjectionError("validator paired-quality policy spans overlap")

    pieces: list[str] = []
    cursor = 0
    records: list[dict[str, Any]] = []
    for start, end, label, block in spans:
        pieces.append(text[cursor:start])
        records.append(
            {
                "label": label,
                "normalized_source_byte_range": [
                    len(text[:start].encode("utf-8")),
                    len(text[:end].encode("utf-8")),
                ],
                "sha256": _sha256(block.encode("utf-8")),
                "size": len(block.encode("utf-8")),
            }
        )
        cursor = end
    pieces.append(text[cursor:])
    projected = "".join(pieces)
    forbidden = (
        "_PAIRED_QUALITY_CONTRACT_NAME",
        "_PAIRED_QUALITY_VERIFIER_NAME",
        "paired_quality_verifier_sha256",
        "paired_quality_contract_sha256",
        "paired_quality_clearance_contract",
    )
    leaked = [token for token in forbidden if token in projected]
    if leaked:
        raise ProjectionError("validator paired-quality policy binding survived: " + leaked[0])
    return projected.encode("utf-8"), records


def _transform_long_workflow(raw: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError as error:
        raise ProjectionError(f"long-document-workflow.md is not strict UTF-8: {error}") from error
    if "\ufffd" in text or "\x00" in text or "\r" in text:
        raise ProjectionError("long-document-workflow.md contains invalid normalized text")
    section_start = "## 16. 幂等重跑\n"
    section_end = "## 17. 编译与格式检查\n"
    summary_start_marker = (
        "<!-- GENERATOR_PROJECTION_CONTROL_BEGIN:SECOND_PASS_SUMMARY -->\n"
    )
    summary_end_marker = (
        "<!-- GENERATOR_PROJECTION_CONTROL_END:SECOND_PASS_SUMMARY -->\n"
    )
    if (
        text.count(section_start) != 1
        or text.count(section_end) != 1
        or text.count(summary_start_marker) != 1
        or text.count(summary_end_marker) != 1
    ):
        raise ProjectionError("long-document second-pass control anchors drifted")
    start = text.index(section_start)
    end = text.index(section_end, start)
    paragraph_start = text.index(summary_start_marker)
    paragraph_end = (
        text.index(summary_end_marker, paragraph_start)
        + len(summary_end_marker)
    )
    safe_section = (
        "## 16. 独立复读\n\n"
        "把当前候选作为唯一正文重新阅读，并按本 Skill 的普通 REWRITE 合同独立决定是否仍需实质修改。"
        "不要查找旧 diff、旧 decision、验收条件或控制面工件；这些内容在 generator projection 中不可用。\n\n"
    )
    removed_section = text[start:end]
    removed_paragraph = text[paragraph_start:paragraph_end]
    projected = text[:paragraph_start] + text[paragraph_end:]
    projected_section_start = projected.index(section_start)
    projected_section_end = projected.index(section_end, projected_section_start)
    projected = (
        projected[:projected_section_start]
        + safe_section
        + projected[projected_section_end:]
    )
    forbidden = (
        "prepare_humanize_second_pass.py",
        "verify_humanize_second_pass.py",
        "all_units_no_change",
        "second_output_equals_first",
        "GENERATOR_PROJECTION_CONTROL",
    )
    leaked = [token for token in forbidden if token in projected]
    if leaked:
        raise ProjectionError(
            "long-document second-pass control survived transformation: " + leaked[0]
        )
    records = [
        {
            "label": "section:16-second-pass-control",
            "normalized_source_byte_range": [
                len(text[:start].encode("utf-8")),
                len(text[:end].encode("utf-8")),
            ],
            "sha256": _sha256(removed_section.encode("utf-8")),
            "size": len(removed_section.encode("utf-8")),
        },
        {
            "label": "paragraph:paired-quality-second-pass-summary",
            "normalized_source_byte_range": [
                len(text[:paragraph_start].encode("utf-8")),
                len(text[:paragraph_end].encode("utf-8")),
            ],
            "sha256": _sha256(removed_paragraph.encode("utf-8")),
            "size": len(removed_paragraph.encode("utf-8")),
        },
    ]
    return projected.encode("utf-8"), records


def _transform_corpus_action_sources(
    raw: bytes, source_trust_policy_raw: bytes | None = None
) -> tuple[bytes, list[dict[str, Any]]]:
    """Emit the strict runtime registry: guard identity, scene, and detector only."""
    payload = _strict_json(raw, "corpus action source catalog")
    if not isinstance(payload, dict):
        raise ProjectionError("corpus action source catalog must be an object")
    sources = payload.get("sources")
    cards = payload.get("action_cards")
    if not isinstance(sources, list) or not isinstance(cards, list):
        raise ProjectionError("corpus action source catalog must contain source and card arrays")
    if source_trust_policy_raw is None:
        source_trust_policy_raw = (
            DEFAULT_SKILL_ROOT / "references" / "source-provenance-trust.json"
        ).read_bytes()
    try:
        runtime = negative_guards.parse_negative_guard_registry(
            raw,
            label="corpus action source catalog",
            source_trust_policy_raw=source_trust_policy_raw,
        )
    except negative_guards.NegativeGuardRegistryError as error:
        raise ProjectionError(f"corpus negative guards are invalid: {error}") from error
    retained_guards = [
        {
            "id": guard["id"],
            "scene": guard["scene"],
            "detector": guard["detector"],
        }
        for guard in runtime["guards"]
    ]
    removed_cards = [
        card
        for card in cards
        if isinstance(card, dict) and card.get("kind") == "positive_action"
    ]
    projected = {
        "schema_version": negative_guards.REGISTRY_SCHEMA,
        "registry_id": negative_guards.REGISTRY_ID,
        "guards": retained_guards,
    }
    projected_raw = _canonical_json(projected) + b"\n"
    try:
        negative_guards.parse_negative_guard_registry(
            projected_raw, label="projected negative guard registry"
        )
    except negative_guards.NegativeGuardRegistryError as error:
        raise ProjectionError(
            f"projected negative guard registry is invalid: {error}"
        ) from error
    records = [
        {
            "label": "all-positive-actions",
            "count": len(removed_cards),
            "sha256": _sha256(_canonical_json(sorted(card["id"] for card in removed_cards))),
        },
        {
            "label": "all-source-provenance-records",
            "count": len(sources),
            "sha256": _sha256(_canonical_json(sorted(source["id"] for source in sources))),
        },
        {
            "label": "audit-only-negative-guards",
            "count": runtime["summary"]["audit_only_guard_count"],
            "sha256": _sha256(
                _canonical_json(runtime["summary"]["audit_only_guard_ids"])
            ),
        },
        {
            "label": "negative-guard-non-detector-fields",
            "count": len(cards) - len(removed_cards),
            "sha256": _sha256(
                _canonical_json(
                    sorted(
                        set().union(
                            *(
                                set(card) - {"id", "scene", "detector"}
                                for card in cards
                                if card.get("kind") == "negative_guard"
                            )
                        )
                    )
                )
            ),
        },
    ]
    return projected_raw, records


def _transform_file(
    path: str,
    raw: bytes,
    transform_id: str,
    *,
    source_trust_policy_raw: bytes | None = None,
) -> tuple[bytes, list[dict[str, Any]]]:
    if path == "SKILL.md" and transform_id == SKILL_TRANSFORM_ID:
        return _transform_skill(raw)
    if (
        path == "scripts/finalize_humanize_long_document.py"
        and transform_id == FINALIZER_TRANSFORM_ID
    ):
        return _transform_finalizer(raw)
    if (
        path == "scripts/validate_humanize_output.py"
        and transform_id == VALIDATOR_TRANSFORM_ID
    ):
        return _transform_validator(raw)
    if (
        path == "references/long-document-workflow.md"
        and transform_id == LONG_WORKFLOW_TRANSFORM_ID
    ):
        return _transform_long_workflow(raw)
    if (
        path == "references/corpus-action-sources.json"
        and transform_id == CORPUS_TRANSFORM_ID
    ):
        return _transform_corpus_action_sources(raw, source_trust_policy_raw)
    raise ProjectionError(f"unregistered projection transform: {path}:{transform_id}")


def _projection_materials(
    frozen: Sequence[FrozenFile],
    dispositions: Mapping[str, str],
    policy: Policy,
) -> dict[str, Any]:
    frozen_by_path = {item.path: item for item in frozen}
    projected: dict[str, bytes] = {}
    file_records: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    inventory_records: list[dict[str, Any]] = []
    capability_records: list[dict[str, Any]] = []
    evaluation_records: list[dict[str, Any]] = []
    derived_records: list[dict[str, Any]] = []
    for item in sorted(frozen, key=lambda value: value.path.encode("utf-8")):
        disposition = dispositions[item.path]
        inventory_record = {
            "path": item.path,
            "disposition": disposition,
            "source_sha256": item.sha256,
            "size": item.size,
        }
        inventory_records.append(inventory_record)
        if disposition == "EXCLUDE":
            exclusion_class = (
                "DERIVED_ARTIFACT"
                if item.path.startswith("build/")
                else "EVALUATION_SURFACE"
            )
            record = {
                "path": item.path,
                "class": exclusion_class,
                "source_sha256": item.sha256,
                "size": item.size,
            }
            excluded.append(record)
            if exclusion_class == "EVALUATION_SURFACE":
                evaluation_records.append(record)
            else:
                derived_records.append(record)
            continue
        if disposition == "INCLUDE":
            output = item.raw
            transform_id: str | None = None
        elif disposition == "TRANSFORM":
            transform_id = policy.transform_exact[item.path]
            output, removed = _transform_file(
                item.path,
                item.raw,
                transform_id,
                source_trust_policy_raw=frozen_by_path[
                    "references/source-provenance-trust.json"
                ].raw,
            )
            transformations.append(
                {
                    "path": item.path,
                    "transform_id": transform_id,
                    "removed_spans": removed,
                    "source_sha256": item.sha256,
                    "projected_sha256": _sha256(output),
                }
            )
        else:
            raise ProjectionError(
                f"unexpected disposition for frozen file: {item.path}"
            )
        projected[item.path] = output
        file_records.append(
            {
                "path": item.path,
                "disposition": disposition,
                "source_sha256": item.sha256,
                "projected_sha256": _sha256(output),
                "size": len(output),
                "transform_id": transform_id,
            }
        )
        capability_records.append(inventory_record)
    expected_paths = set(policy.include_exact) | set(policy.transform_exact)
    if set(projected) != expected_paths or len(projected) != len(expected_paths):
        raise ProjectionError(
            f"projection file set does not equal the fixed {len(expected_paths)}-file "
            "capability surface"
        )
    return {
        "projected": projected,
        "files": sorted(file_records, key=lambda item: item["path"].encode("utf-8")),
        "excluded": sorted(excluded, key=lambda item: item["path"].encode("utf-8")),
        "transformations": sorted(
            transformations, key=lambda item: item["path"].encode("utf-8")
        ),
        "declared_external_capability_refs": _external_refs(
            projected["references/corpus-action-sources.json"]
        ),
        "source": {
            "root_id": "humanize-academic-chinese",
            "inventory_sha256": _inventory_hash(inventory_records),
            "capability_source_sha256": _inventory_hash(capability_records),
            "evaluation_surface_sha256": _inventory_hash(evaluation_records),
            "derived_artifact_sha256": _inventory_hash(derived_records),
        },
        "inventory_records": inventory_records,
        "capability_records": capability_records,
        "frozen_by_path": frozen_by_path,
    }


def _hidden_control_tokens(frozen_by_path: Mapping[str, FrozenFile]) -> set[str]:
    catalog = _strict_json(
        frozen_by_path["references/generation-qualification-oracles.json"].raw,
        "hidden oracle catalog",
    )
    tokens: set[str] = set()
    if isinstance(catalog, dict):
        for collection in ("checks", "review_rubrics", "suites"):
            entries = catalog.get(collection, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for key in ("id", "atom_id"):
                    value = entry.get(key)
                    if isinstance(value, str) and len(value) >= 5:
                        tokens.add(value)
                for key in ("required_checks", "required_reviews"):
                    values = entry.get(key, [])
                    if isinstance(values, list):
                        tokens.update(
                            value
                            for value in values
                            if isinstance(value, str) and len(value) >= 5
                        )
    requirements = _strict_json(
        frozen_by_path["references/generation-qualification-requirements.json"].raw,
        "hidden qualification requirements",
    )
    if isinstance(requirements, dict):
        globals_raw = requirements.get("global_atoms", [])
        if isinstance(globals_raw, list):
            tokens.update(
                item["id"]
                for item in globals_raw
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and len(item["id"]) >= 5
            )
    return tokens


def _audit_projected_text(
    files: Mapping[str, bytes], policy: Policy, hidden_control_tokens: set[str]
) -> None:
    available = set(files)
    for path, raw in files.items():
        if Path(path).suffix.lower() not in {".md", ".json", ".py", ".yaml", ".txt", ".tex"}:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError as error:
            raise ProjectionError(f"projected text is not UTF-8: {path}: {error}") from error
        folded = unicodedata.normalize("NFC", text).casefold()
        for basename in policy.forbidden_reference_basenames:
            if unicodedata.normalize("NFC", basename).casefold() in folded:
                raise ProjectionError(f"forbidden evaluation basename leaked in {path}: {basename}")
        for literal in FORBIDDEN_CONTROL_LITERALS:
            if unicodedata.normalize("NFC", literal).casefold() in folded:
                raise ProjectionError(f"forbidden qualification control leaked in {path}: {literal}")
        match = CONTROL_ID_RE.search(text)
        if match:
            raise ProjectionError(f"qualification control ID leaked in {path}: {match.group(0)}")
        leaked_tokens = sorted(
            token
            for token in hidden_control_tokens
            if unicodedata.normalize("NFC", token).casefold() in folded
        )
        if leaked_tokens:
            raise ProjectionError(
                f"hidden catalog identifier leaked in {path}: {leaked_tokens[0]}"
            )
        references = set(LOCAL_PATH_RE.findall(text))
        if path.endswith(".md"):
            for target in MARKDOWN_LINK_RE.findall(text):
                target = target.strip().split("#", 1)[0]
                if not target or "://" in target or target.startswith("#"):
                    continue
                if target.startswith(("references/", "scripts/")):
                    references.add(target)
                elif not target.startswith(("/", "<")):
                    resolved = (PurePosixPath(path).parent / target).as_posix()
                    if resolved.startswith(("references/", "scripts/")):
                        references.add(resolved)
        missing = sorted(reference for reference in references if reference not in available)
        if missing:
            raise ProjectionError(f"projected local reference closure failed in {path}: {missing}")


def _verify_python(files: Mapping[str, bytes]) -> None:
    forbidden_imports = {
        Path(path).stem.casefold()
        for path in EXPECTED_EXCLUDE
        if path.startswith("scripts/") and path.endswith(".py")
    }
    for path, raw in files.items():
        if not path.endswith(".py"):
            continue
        try:
            compile(raw, path, "exec")
        except SyntaxError as error:
            raise ProjectionError(f"projected Python does not compile: {path}: {error}") from error
        tree = ast.parse(raw.decode("utf-8"), filename=path)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0].casefold() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0].casefold())
        leaked = sorted(imported & forbidden_imports)
        if leaked:
            raise ProjectionError(
                f"projected Python imports excluded audit module in {path}: {leaked[0]}"
            )


def _verify_python_import_closure(
    projection_root: Path,
    files: Mapping[str, bytes],
) -> None:
    modules = sorted(
        Path(path).stem
        for path in files
        if path.startswith("scripts/") and path.endswith(".py")
    )
    probe = (
        "import importlib,sys;"
        "sys.dont_write_bytecode=True;"
        "sys.path.insert(0,sys.argv[1]);"
        "[importlib.import_module(name) for name in sys.argv[2:]]"
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-X",
                "utf8",
                "-c",
                probe,
                str(projection_root / "scripts"),
                *modules,
            ],
            cwd=projection_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProjectionError("projected Python import probe could not run") from error
    if completed.returncode != 0:
        raise ProjectionError("projected Python import closure failed")


def _quick_validate(projection_root: Path) -> str:
    script = (
        Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "skill-creator"
        / "scripts"
        / "quick_validate.py"
    )
    if not script.is_file():
        return "NOT_AVAILABLE"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(script), str(projection_root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        output = result.stdout.decode("utf-8", errors="replace").strip()
        raise ProjectionError(f"projected Skill quick validation failed: {output}")
    return "PASS"


def _tree_hash(files: Mapping[str, bytes]) -> str:
    entries = [
        {"path": path, "sha256": _sha256(raw), "size": len(raw)}
        for path, raw in sorted(files.items(), key=lambda item: item[0].encode("utf-8"))
    ]
    return _sha256(_canonical_json({"schema_version": TREE_SCHEMA, "files": entries}))


def verify_projection(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    source_root: Path | None = None,
    allow_source_unverified: bool = False,
) -> dict[str, Any]:
    root = _verified_directory_root(root, "projection root")
    if source_root is None and not allow_source_unverified:
        raise ProjectionError(
            "source_root is required for projection verification; "
            "set allow_source_unverified=True only for explicit retained-byte inspection"
        )
    if not isinstance(manifest, dict):
        raise ProjectionError("projection manifest must be an object")
    _exact_keys(
        manifest,
        {
            "schema_version",
            "projection_policy",
            "builder",
            "source",
            "files",
            "excluded",
            "transformations",
            "declared_external_capability_refs",
            "audits",
            "projection_tree_sha256",
        },
        "projection manifest",
    )
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ProjectionError("projection manifest schema drifted")

    verified_source_root = (
        _verified_directory_root(source_root, "source root")
        if source_root is not None
        else None
    )
    policy_root = verified_source_root or DEFAULT_SKILL_ROOT
    policy = load_policy(policy_root / "references" / DEFAULT_POLICY.name)
    expected_policy = {
        "id": policy.policy_id,
        "version": policy.policy_version,
        "sha256": policy.canonical_sha256,
        "raw_sha256": policy.raw_sha256,
    }
    if manifest.get("projection_policy") != expected_policy:
        raise ProjectionError("projection manifest policy does not match current policy bytes")

    expected_builder = {
        "version": BUILDER_VERSION,
        "executable_sha256": _builder_executable_sha256(),
        "transform_registry_sha256": _transform_registry_sha256(),
        "transform_dependency_sha256": _transform_dependency_sha256(),
        "python_implementation": sys.implementation.name,
        "python_version": sys.version.split()[0],
        "unicode_version": unicodedata.unidata_version,
    }
    if manifest.get("builder") != expected_builder:
        raise ProjectionError("projection manifest builder semantics drifted")

    source = manifest.get("source")
    source_fields = {
        "root_id",
        "inventory_sha256",
        "capability_source_sha256",
        "evaluation_surface_sha256",
        "derived_artifact_sha256",
    }
    if not isinstance(source, dict):
        raise ProjectionError("projection manifest source must be an object")
    _exact_keys(source, source_fields, "projection manifest source")
    if source.get("root_id") != "humanize-academic-chinese":
        raise ProjectionError("projection manifest source root drifted")
    for key in source_fields - {"root_id"}:
        if not isinstance(source.get(key), str) or not re.fullmatch(
            r"[0-9a-f]{64}", source[key]
        ):
            raise ProjectionError(f"projection manifest source {key} is invalid")

    records = manifest.get("files")
    expected_file_count = len(EXPECTED_INCLUDE) + len(EXPECTED_TRANSFORM)
    if not isinstance(records, list) or len(records) != expected_file_count:
        raise ProjectionError(
            f"projection manifest must bind exactly {expected_file_count} files"
        )
    expected: dict[str, Mapping[str, Any]] = {}
    fixed_paths = set(EXPECTED_INCLUDE) | set(EXPECTED_TRANSFORM)
    expected_directories = {"."}
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            raise ProjectionError(f"projection manifest file {index} is not an object")
        _exact_keys(
            raw_record,
            {
                "path",
                "disposition",
                "source_sha256",
                "projected_sha256",
                "size",
                "transform_id",
            },
            f"projection manifest file {index}",
        )
        path = _safe_relative_path(raw_record.get("path"), f"manifest.files[{index}].path")
        if path in expected:
            raise ProjectionError(f"projection manifest repeats file: {path}")
        for key in ("source_sha256", "projected_sha256"):
            if not isinstance(raw_record.get(key), str) or not re.fullmatch(
                r"[0-9a-f]{64}", raw_record[key]
            ):
                raise ProjectionError(f"projection manifest has an invalid {key}: {path}")
        expected_disposition = "TRANSFORM" if path in EXPECTED_TRANSFORM else "INCLUDE"
        if (
            raw_record.get("disposition") != expected_disposition
            or raw_record.get("transform_id") != EXPECTED_TRANSFORM.get(path)
        ):
            raise ProjectionError(f"projection manifest disposition drifted: {path}")
        if not isinstance(raw_record.get("size"), int) or isinstance(
            raw_record.get("size"), bool
        ) or raw_record["size"] < 0:
            raise ProjectionError(f"projection manifest has an invalid size: {path}")
        expected[path] = raw_record
        parent = PurePosixPath(path).parent
        while parent.as_posix() != ".":
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    if set(expected) != fixed_paths:
        raise ProjectionError("projection manifest paths differ from the fixed capability surface")

    found: dict[str, bytes] = {}
    identities: dict[tuple[int, int], str] = {}
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as iterator:
            for entry in iterator:
                path = Path(entry.path)
                relative = _safe_relative_path(
                    path.relative_to(root).as_posix(), "projection path"
                )
                info = path.lstat()
                if entry.is_symlink() or _is_reparse(path, info):
                    raise ProjectionError(
                        f"projection contains a symlink or reparse point: {relative}"
                    )
                if stat.S_ISDIR(info.st_mode):
                    if relative not in expected_directories:
                        raise ProjectionError(
                            f"projection contains an unexpected directory: {relative}"
                        )
                    stack.append(path)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise ProjectionError(
                        f"projection contains a non-regular file: {relative}"
                    )
                record = expected.get(relative)
                if record is None:
                    raise ProjectionError(
                        f"projection contains an unexpected file: {relative}"
                    )
                identity = (info.st_dev, info.st_ino)
                if identity in identities:
                    raise ProjectionError(
                        "projection hard-link identity is shared by "
                        f"{identities[identity]} and {relative}"
                    )
                identities[identity] = relative
                raw = path.read_bytes()
                after = path.lstat()
                if (
                    (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    or len(raw) != after.st_size
                ):
                    raise ProjectionError(
                        f"projection file changed while being verified: {relative}"
                    )
                if (
                    len(raw) != record["size"]
                    or _sha256(raw) != record["projected_sha256"]
                ):
                    raise ProjectionError(
                        f"projection file does not match manifest: {relative}"
                    )
                if (
                    record["disposition"] == "INCLUDE"
                    and record["source_sha256"] != record["projected_sha256"]
                ):
                    raise ProjectionError(
                        f"included projection source hash is not self-consistent: {relative}"
                    )
                found[relative] = raw
    missing = sorted(set(expected) - set(found))
    if missing:
        raise ProjectionError(f"projection is missing manifest files: {missing}")

    transformations = manifest.get("transformations")
    if not isinstance(transformations, list):
        raise ProjectionError("projection manifest transformations must be an array")
    transformation_by_path: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(transformations):
        if not isinstance(record, dict):
            raise ProjectionError(f"projection transformation {index} is not an object")
        _exact_keys(
            record,
            {"path", "transform_id", "removed_spans", "source_sha256", "projected_sha256"},
            f"projection transformation {index}",
        )
        path = _safe_relative_path(record.get("path"), f"transformations[{index}].path")
        if path in transformation_by_path:
            raise ProjectionError(f"projection transformation repeats path: {path}")
        file_record = expected.get(path)
        if (
            file_record is None
            or path not in EXPECTED_TRANSFORM
            or record.get("transform_id") != EXPECTED_TRANSFORM[path]
            or record.get("source_sha256") != file_record["source_sha256"]
            or record.get("projected_sha256") != file_record["projected_sha256"]
            or not isinstance(record.get("removed_spans"), list)
            or not record["removed_spans"]
        ):
            raise ProjectionError(f"projection transformation metadata drifted: {path}")
        transformation_by_path[path] = record
    if set(transformation_by_path) != set(EXPECTED_TRANSFORM):
        raise ProjectionError("projection transformation surface is incomplete")

    excluded = manifest.get("excluded")
    if not isinstance(excluded, list):
        raise ProjectionError("projection manifest excluded must be an array")
    excluded_paths: set[str] = set()
    for index, record in enumerate(excluded):
        if not isinstance(record, dict):
            raise ProjectionError(f"projection excluded record {index} is not an object")
        _exact_keys(
            record,
            {"path", "class", "source_sha256", "size"},
            f"projection excluded record {index}",
        )
        path = _safe_relative_path(record.get("path"), f"excluded[{index}].path")
        if path in excluded_paths:
            raise ProjectionError(f"projection excluded path repeats: {path}")
        allowed = path in EXPECTED_EXCLUDE or any(
            path.startswith(prefix) for prefix in EXPECTED_EXCLUDE_PREFIXES
        )
        expected_class = (
            "DERIVED_ARTIFACT" if path.startswith("build/") else "EVALUATION_SURFACE"
        )
        if not allowed or record.get("class") != expected_class:
            raise ProjectionError(f"projection excluded classification drifted: {path}")
        if not isinstance(record.get("source_sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", record["source_sha256"]
        ):
            raise ProjectionError(f"projection excluded source hash is invalid: {path}")
        if not isinstance(record.get("size"), int) or isinstance(record["size"], bool):
            raise ProjectionError(f"projection excluded size is invalid: {path}")
        excluded_paths.add(path)
    if not set(EXPECTED_EXCLUDE).issubset(excluded_paths):
        raise ProjectionError("projection excluded surface omits fixed audit files")

    external_refs = manifest.get("declared_external_capability_refs")
    if external_refs != _external_refs(found["references/corpus-action-sources.json"]):
        raise ProjectionError("projection external capability references drifted")

    _verify_python(found)
    _verify_python_import_closure(root, found)
    quick_validate = _quick_validate(root)
    expected_audits = {
        "unknown_paths": [],
        "reference_closure": "PASS",
        "forbidden_reference_scan": "PASS",
        "secret_control_identifier_scan": "PASS",
        "casefold_collision_scan": "PASS",
        "reparse_point_scan": "PASS",
        "python_compile": "PASS",
        "python_import_closure": "PASS",
        "skill_quick_validate": quick_validate,
        "read_only_marking_is_isolation_proof": False,
    }
    if manifest.get("audits") != expected_audits:
        raise ProjectionError("projection manifest audit claims drifted")

    tree_hash = _tree_hash(found)
    if manifest.get("projection_tree_sha256") != tree_hash:
        raise ProjectionError("projection tree hash does not match manifest")

    source_currentness = "NOT_EVALUATED"
    verification_scope = "PROJECTED_BYTES_CURRENT_BUILDER_ONLY"
    if verified_source_root is not None:
        source_builder = (
            verified_source_root / "scripts" / "build_humanize_generator_projection.py"
        )
        if _sha256(source_builder.read_bytes()) != _builder_executable_sha256():
            raise ProjectionError("source Skill builder differs from the executing builder")
        if _transform_dependency_sha256(verified_source_root) != _transform_dependency_sha256():
            raise ProjectionError("source Skill transform dependency differs from the executing builder")
        frozen, dispositions = _inventory(verified_source_root, policy)
        materials = _projection_materials(frozen, dispositions, policy)
        projected = materials["projected"]
        _audit_projected_text(
            projected,
            policy,
            _hidden_control_tokens(materials["frozen_by_path"]),
        )
        _verify_python(projected)
        capability_hash = materials["source"]["capability_source_sha256"]
        if capability_hash != policy.approved_capability_source_sha256:
            raise ProjectionError(
                "capability source hash is not approved by the fixed projection policy"
            )
        expected_source_bound = {
            "source": materials["source"],
            "files": materials["files"],
            "excluded": materials["excluded"],
            "transformations": materials["transformations"],
            "declared_external_capability_refs": materials[
                "declared_external_capability_refs"
            ],
        }
        for key, value in expected_source_bound.items():
            if manifest.get(key) != value:
                raise ProjectionError(f"projection manifest {key} does not replay from source")
        if projected != found:
            raise ProjectionError("projection bytes do not replay from current source")
        _verify_source_unchanged(frozen)
        source_currentness = "PASS"
        verification_scope = "SOURCE_BOUND_CURRENT"
    return {
        "projection_tree_sha256": tree_hash,
        "files": len(found),
        "verification_scope": verification_scope,
        "source_currentness": source_currentness,
        "historical_authenticity": "NOT_EVALUATED",
        "same_privilege_tamper_resistance": "NOT_EVALUATED",
    }


def _inventory_hash(entries: Sequence[Mapping[str, Any]]) -> str:
    return _sha256(_canonical_json(list(entries)))


def _verify_source_unchanged(frozen: Sequence[FrozenFile]) -> None:
    for item in frozen:
        current = _read_frozen(item.absolute, item.path)
        if (
            current.sha256 != item.sha256
            or current.size != item.size
            or current.identity != item.identity
            or current.mtime_ns != item.mtime_ns
        ):
            raise ProjectionError(f"source changed before projection publication: {item.path}")


def build_projection(
    source_root: Path,
    output_root: Path,
    manifest_path: Path,
    *,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    source_root = _verified_directory_root(source_root, "source root")
    output_root = output_root.resolve(strict=False)
    manifest_path = manifest_path.resolve(strict=False)
    expected_policy = (source_root / "references" / DEFAULT_POLICY.name).resolve(strict=True)
    if policy_path is not None and policy_path.resolve(strict=True) != expected_policy:
        raise ProjectionError("projection policy must use the fixed source Skill path")
    policy = load_policy(expected_policy)
    if source_root == output_root or source_root in output_root.parents or output_root in source_root.parents:
        raise ProjectionError("source and projection roots must not contain each other")
    if manifest_path == source_root or source_root in manifest_path.parents:
        raise ProjectionError("projection manifest must stay outside the source Skill")
    if output_root == manifest_path or output_root in manifest_path.parents:
        raise ProjectionError("projection manifest must remain outside the generator projection")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    journal_path = _publication_journal_path(manifest_path)
    _recover_publication_journal(journal_path, output_root, manifest_path)
    if output_root.exists():
        raise ProjectionError("projection output must not already exist")
    if manifest_path.exists():
        raise ProjectionError("projection manifest must not already exist")
    frozen, dispositions = _inventory(source_root, policy)
    materials = _projection_materials(frozen, dispositions, policy)
    projected = materials["projected"]
    frozen_by_path = materials["frozen_by_path"]
    expected_paths = set(policy.include_exact) | set(policy.transform_exact)
    _audit_projected_text(projected, policy, _hidden_control_tokens(frozen_by_path))
    _verify_python(projected)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent))
    manifest_fd, manifest_staging_name = tempfile.mkstemp(
        prefix=f".{manifest_path.name}.staging-",
        dir=manifest_path.parent,
    )
    os.close(manifest_fd)
    manifest_staging = Path(manifest_staging_name)
    journal = _publication_journal_payload(
        state="ALLOCATED",
        output_root=output_root,
        manifest_path=manifest_path,
        staging_root=staging,
        manifest_staging_path=manifest_staging,
    )
    _write_atomic_file(journal_path, _canonical_json(journal))
    published = False
    committed = False
    try:
        for relative, raw in projected.items():
            target = staging / PurePosixPath(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        staged_paths = {
            path.relative_to(staging).as_posix()
            for path in staging.rglob("*")
            if path.is_file()
        }
        if staged_paths != expected_paths:
            raise ProjectionError("staging projection contains an unexpected file set")
        quick_validate = _quick_validate(staging)
        for relative, raw in projected.items():
            if (staging / PurePosixPath(relative)).read_bytes() != raw:
                raise ProjectionError(f"staging bytes drifted: {relative}")
        _verify_source_unchanged(frozen)
        builder_hash = _builder_executable_sha256()
        tree_hash = _tree_hash(projected)
        capability_hash = materials["source"]["capability_source_sha256"]
        if capability_hash != policy.approved_capability_source_sha256:
            raise ProjectionError(
                "capability source hash is not approved by the fixed projection policy"
            )
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "projection_policy": {
                "id": policy.policy_id,
                "version": policy.policy_version,
                "sha256": policy.canonical_sha256,
                "raw_sha256": policy.raw_sha256,
            },
            "builder": {
                "version": BUILDER_VERSION,
                "executable_sha256": builder_hash,
                "transform_registry_sha256": _transform_registry_sha256(),
                "transform_dependency_sha256": _transform_dependency_sha256(),
                "python_implementation": sys.implementation.name,
                "python_version": sys.version.split()[0],
                "unicode_version": unicodedata.unidata_version,
            },
            "source": materials["source"],
            "files": materials["files"],
            "excluded": materials["excluded"],
            "transformations": materials["transformations"],
            "declared_external_capability_refs": materials[
                "declared_external_capability_refs"
            ],
            "audits": {
                "unknown_paths": [],
                "reference_closure": "PASS",
                "forbidden_reference_scan": "PASS",
                "secret_control_identifier_scan": "PASS",
                "casefold_collision_scan": "PASS",
                "reparse_point_scan": "PASS",
                "python_compile": "PASS",
                "python_import_closure": "PASS",
                "skill_quick_validate": quick_validate,
                "read_only_marking_is_isolation_proof": False,
            },
            "projection_tree_sha256": tree_hash,
        }
        verify_projection(staging, manifest, source_root=source_root)
        manifest_raw = _canonical_json(manifest)
        with manifest_staging.open("wb") as handle:
            handle.write(manifest_raw)
            handle.flush()
            os.fsync(handle.fileno())
        journal = _publication_journal_payload(
            state="PREPARED",
            output_root=output_root,
            manifest_path=manifest_path,
            staging_root=staging,
            manifest_staging_path=manifest_staging,
            projection_tree_sha256=tree_hash,
            manifest_sha256=_sha256(manifest_raw),
            manifest_size=len(manifest_raw),
        )
        _write_atomic_file(journal_path, _canonical_json(journal))
        _verify_source_unchanged(frozen)
        staging.rename(output_root)
        published = True
        journal["state"] = "OUTPUT_PUBLISHED"
        _write_atomic_file(journal_path, _canonical_json(journal))
        os.replace(manifest_staging, manifest_path)
        _fsync_parent(manifest_path.parent)
        committed = True
        journal["state"] = "COMMITTED"
        _write_atomic_file(journal_path, _canonical_json(journal))
        try:
            journal_path.unlink()
            _fsync_parent(journal_path.parent)
        except FileNotFoundError:
            pass
        return {
            **manifest,
            "manifest_sha256": _sha256(manifest_raw),
            "projection_root": str(output_root),
            "manifest_path": str(manifest_path),
        }
    finally:
        if not published:
            _safe_remove_publication_path(staging, directory=True)
            _safe_remove_publication_path(manifest_staging, directory=False)
            try:
                journal_path.unlink()
                _fsync_parent(journal_path.parent)
            except FileNotFoundError:
                pass
        elif committed:
            _safe_remove_publication_path(staging, directory=True)
            _safe_remove_publication_path(manifest_staging, directory=False)


def _external_refs(raw: bytes) -> list[str]:
    payload = _strict_json(raw, "corpus action source catalog")
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
        elif isinstance(value, str) and re.match(r"^[A-Za-z]:[\\/]", value):
            found.add(value)

    walk(payload)
    return sorted(found, key=lambda item: item.encode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the fixed, oracle-free generator projection for this Skill."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SKILL_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        result = build_projection(
            args.source,
            args.output,
            args.manifest,
        )
    except (OSError, ProjectionError, subprocess.SubprocessError) as error:
        if args.format == "json":
            print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"FAIL: {error}")
        return 1
    summary = {
        "status": "PASS",
        "projection_tree_sha256": result["projection_tree_sha256"],
        "manifest_sha256": result["manifest_sha256"],
        "files": len(result["files"]),
        "projection_root": result["projection_root"],
        "manifest_path": result["manifest_path"],
        "evidence_cap": "E2",
    }
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"PASS files={summary['files']} tree={summary['projection_tree_sha256']} "
            "evidence_cap=E2"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
