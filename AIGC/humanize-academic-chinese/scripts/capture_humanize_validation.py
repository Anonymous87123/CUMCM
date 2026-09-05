#!/usr/bin/env python3
"""Capture a Humanize validator process from an independent parent process."""

from __future__ import annotations

import argparse
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
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
VALIDATOR = SCRIPT_DIR / "validate_humanize_output.py"
INNER_REPLAYER = SCRIPT_DIR / "replay_humanize_validation_record.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import replay_humanize_validation_record as inner_replay  # noqa: E402
import validate_humanize_output as validator  # noqa: E402


CAPTURE_INVOCATION_SCHEMA = "humanize-validation-process-capture-invocation/v1"
PROCESS_OBSERVATION_SCHEMA = "humanize-validation-process-observation/v1"
CAPTURE_MANIFEST_SCHEMA = "humanize-validation-process-capture-manifest/v1"
CAPTURE_ERROR_SCHEMA = "humanize-validation-process-capture-error/v1"
RUNTIME_SCHEMA = "humanize-validation-process-capture-runtime/v1"
HEX64_RE = re.compile(r"[0-9a-f]{64}")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
DEFAULT_STREAM_LIMIT = 16 * 1024 * 1024
VALUE_OPTIONS = {
    "--mode",
    "--scene",
    "--document-format",
    "--format",
    "--keep-reason",
    "--report-scope",
    "--template-field-edit-scope",
    "--accept-warning",
    "--propose-warning-resolution",
    "--warning-review-request-sha256",
    "--warning-reviewer-kind",
    "--warning-reviewer-id",
    "--term",
}
FLAG_OPTIONS = {"--strict-speech-acts", "--fragment"}
HELP_OPTIONS = {"-h", "--help"}
PATH_OPTIONS = {"--report-scope", "--template-field-edit-scope"}
RETIRED_PRIVATE_OPTIONS = {"--warning-reviewer-id"}
SAFE_UNEXPECTED_ERROR_MESSAGES = {
    "CAPTURE_IO_ERROR": "capture failed during a filesystem or process operation",
    "CAPTURE_ENCODING_ERROR": "capture failed while processing encoded text",
    "CAPTURE_VALUE_ERROR": "capture failed because an internal value was invalid",
}


class CaptureError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        _absolute_without_resolving(path).relative_to(_absolute_without_resolving(parent))
    except ValueError:
        return False
    return True


def _assert_no_reparse_ancestors(path: Path) -> None:
    current = _absolute_without_resolving(path)
    while True:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            attributes = int(getattr(info, "st_file_attributes", 0))
            if current.is_symlink() or attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise CaptureError(
                    "REPARSE_POINT_REJECTED",
                    "capture path crosses a symlink or reparse point",
                )
        parent = current.parent
        if parent == current:
            return
        current = parent


def _read_regular_single_link(path: Path, *, missing_ok: bool = False) -> bytes | None:
    absolute = _absolute_without_resolving(path)
    _assert_no_reparse_ancestors(absolute)
    try:
        info = absolute.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise CaptureError("MISSING_ARTIFACT", "capture input is missing")
    if not stat.S_ISREG(info.st_mode):
        raise CaptureError("NON_REGULAR_ARTIFACT", "capture input is not a regular file")
    if int(getattr(info, "st_nlink", 1)) != 1:
        raise CaptureError("HARDLINK_REJECTED", "capture input must not be a hard link")
    return absolute.read_bytes()


def _write_exclusive(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _safe_suffix(path_text: str, fallback: str = ".txt") -> str:
    suffix = Path(path_text).suffix
    if re.fullmatch(r"\.[A-Za-z0-9]{1,16}", suffix or ""):
        return suffix.lower()
    return fallback


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CaptureError("DUPLICATE_JSON_KEY", f"{label} contains duplicate keys")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CaptureError("NON_FINITE_JSON", f"{label} contains {value}")
            ),
        )
    except UnicodeDecodeError as error:
        raise CaptureError("NON_UTF8_JSON", f"{label} is not UTF-8") from error
    except json.JSONDecodeError as error:
        raise CaptureError("INVALID_JSON", f"{label} is invalid JSON") from error


def _runtime_contract() -> dict[str, Any]:
    return {
        "schema": RUNTIME_SCHEMA,
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "python_version": list(sys.version_info[:3]),
        "unicode_version": unicodedata.unidata_version,
        "os_name": os.name,
        "python_utf8_mode": bool(sys.flags.utf8_mode),
    }


def _capture_policy_hashes() -> dict[str, Any]:
    runtime = _runtime_contract()
    return {
        "capture_script_sha256": _sha256(Path(__file__).resolve().read_bytes()),
        "validator_script_sha256": _sha256(VALIDATOR.read_bytes()),
        "inner_replayer_script_sha256": _sha256(INNER_REPLAYER.read_bytes()),
        "runtime_contract_sha256": _sha256(_canonical_json_bytes(runtime)),
        "validator_policy_hashes": validator._policy_hashes(),
    }


def _option_name(token: str) -> str:
    return token.split("=", 1)[0]


def _argument_layout(arguments: Sequence[str]) -> tuple[list[int], dict[str, list[int]]]:
    positionals: list[int] = []
    option_values: dict[str, list[int]] = {}
    help_requested = False
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            raise CaptureError(
                "VALIDATOR_SEPARATOR_REJECTED",
                "a nested -- separator would bypass evidence option control",
            )
        name = _option_name(token)
        if name in VALUE_OPTIONS:
            if "=" in token:
                option_values.setdefault(name, []).append(index)
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("-"):
                raise CaptureError(
                    "MISSING_VALIDATOR_OPTION_VALUE",
                    "a known validator option is missing its value",
                )
            option_values.setdefault(name, []).append(index + 1)
            index += 2
            continue
        if name in FLAG_OPTIONS or name in HELP_OPTIONS:
            if "=" in token:
                raise CaptureError(
                    "UNKNOWN_VALIDATOR_OPTION",
                    "unknown or abbreviated validator options are rejected",
                )
            help_requested = help_requested or name in HELP_OPTIONS
            index += 1
            continue
        if token.startswith("-"):
            raise CaptureError(
                "UNKNOWN_VALIDATOR_OPTION",
                "unknown or abbreviated validator options are rejected",
            )
        positionals.append(index)
        index += 1
    if help_requested:
        if len(arguments) != 1:
            raise CaptureError(
                "INVALID_VALIDATOR_POSITIONAL_COUNT",
                "validator help must be requested without additional arguments",
            )
    if len(positionals) != 2:
        raise CaptureError(
            "INVALID_VALIDATOR_POSITIONAL_COUNT",
            "the validator requires exactly two source artifacts",
        )
    return positionals, option_values


def _pathlike_token(token: str) -> bool:
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", token)
        or token.startswith(("/", "\\\\"))
        or "\\" in token
        or Path(token).exists()
    )


def _redacted_argument_shape(arguments: Sequence[str]) -> tuple[list[str], list[bytes]]:
    positionals, option_values = _argument_layout(arguments)
    positional_roles: dict[int, str] = {}
    if positionals:
        positional_roles[positionals[0]] = "<BEFORE_ARTIFACT>"
    if len(positionals) > 1:
        positional_roles[positionals[1]] = "<AFTER_ARTIFACT>"
    path_value_indexes = {
        index for option in PATH_OPTIONS for index in option_values.get(option, [])
    }
    private_value_indexes = {
        index
        for option in RETIRED_PRIVATE_OPTIONS
        for index in option_values.get(option, [])
    }
    private_tokens: list[bytes] = []
    redacted: list[str] = []
    for index, token in enumerate(arguments):
        name = _option_name(token)
        if name in RETIRED_PRIVATE_OPTIONS and "=" in token:
            value = token.split("=", 1)[1]
            if value:
                private_tokens.append(value.encode("utf-8"))
            redacted.append("<RETIRED_REVIEWER_IDENTIFIER_OPTION_OMITTED>")
        elif index in private_value_indexes:
            if token:
                private_tokens.append(token.encode("utf-8"))
            redacted.append("<RETIRED_PRIVATE_VALUE_OMITTED>")
        elif name in RETIRED_PRIVATE_OPTIONS:
            redacted.append("<RETIRED_REVIEWER_IDENTIFIER_OPTION_OMITTED>")
        elif index in positional_roles:
            private_tokens.append(token.encode("utf-8"))
            private_tokens.append(str(_absolute_without_resolving(Path(token))).encode("utf-8"))
            redacted.append(positional_roles[index])
        elif index in path_value_indexes or _pathlike_token(token):
            private_tokens.append(token.encode("utf-8"))
            private_tokens.append(str(_absolute_without_resolving(Path(token))).encode("utf-8"))
            redacted.append("<PATH_VALUE>")
        else:
            redacted.append(token)
    return redacted, [item for item in private_tokens if item]


def _copy_launch_input(
    original_token: str,
    destination: Path,
    private_tokens: list[bytes],
) -> None:
    original = _absolute_without_resolving(Path(original_token))
    private_tokens.extend((original_token.encode("utf-8"), str(original).encode("utf-8")))
    raw = _read_regular_single_link(original, missing_ok=True)
    if raw is not None:
        _write_exclusive(destination, raw)


def _prepare_child_arguments(
    arguments: Sequence[str],
    launch_dir: Path,
) -> tuple[list[str], list[bytes]]:
    child = list(arguments)
    positionals, option_values = _argument_layout(child)
    private_tokens: list[bytes] = []
    synthetic_sources: dict[str, Path] = {}
    for role, position in zip(("before", "after"), positionals[:2]):
        suffix = _safe_suffix(child[position])
        destination = launch_dir / f"{role}{suffix}"
        _copy_launch_input(child[position], destination, private_tokens)
        child[position] = str(destination)
        synthetic_sources[role] = destination

    report_indexes = option_values.get("--report-scope", [])
    for position in report_indexes:
        token = child[position]
        if token.startswith("--report-scope="):
            raw_token = token.split("=", 1)[1]
        else:
            raw_token = token
        original = _absolute_without_resolving(Path(raw_token))
        private_tokens.extend((raw_token.encode("utf-8"), str(original).encode("utf-8")))
        raw_scope = _read_regular_single_link(original, missing_ok=True)
        synthetic_scope = launch_dir / "report-scope.json"
        if raw_scope is not None:
            try:
                scope = _strict_json(raw_scope, "report scope")
            except CaptureError:
                _write_exclusive(synthetic_scope, raw_scope)
            else:
                if isinstance(scope, dict):
                    report_value = scope.get("report_path")
                    report_destination = launch_dir / "detector-report.html"
                    if isinstance(report_value, str) and report_value:
                        report_original = _absolute_without_resolving(Path(report_value))
                        private_tokens.extend(
                            (
                                report_value.encode("utf-8"),
                                str(report_original).encode("utf-8"),
                            )
                        )
                        report_destination = launch_dir / (
                            "detector-report" + _safe_suffix(report_value, ".html")
                        )
                        report_raw = _read_regular_single_link(
                            report_original,
                            missing_ok=True,
                        )
                        if report_raw is not None:
                            _write_exclusive(report_destination, report_raw)
                    scope["report_path"] = str(report_destination)
                    if "before" in synthetic_sources:
                        scope["source_path"] = str(synthetic_sources["before"])
                    _write_exclusive(synthetic_scope, _pretty_json_bytes(scope))
                else:
                    _write_exclusive(synthetic_scope, raw_scope)
        if token.startswith("--report-scope="):
            child[position] = f"--report-scope={synthetic_scope}"
        else:
            child[position] = str(synthetic_scope)

    template_scope_indexes = option_values.get("--template-field-edit-scope", [])
    for position in template_scope_indexes:
        token = child[position]
        if token.startswith("--template-field-edit-scope="):
            raw_token = token.split("=", 1)[1]
        else:
            raw_token = token
        original = _absolute_without_resolving(Path(raw_token))
        private_tokens.extend((raw_token.encode("utf-8"), str(original).encode("utf-8")))
        raw_scope = _read_regular_single_link(original, missing_ok=True)
        synthetic_scope = launch_dir / "template-field-edit-scope.json"
        if raw_scope is not None:
            _write_exclusive(synthetic_scope, raw_scope)
        if token.startswith("--template-field-edit-scope="):
            child[position] = f"--template-field-edit-scope={synthetic_scope}"
        else:
            child[position] = str(synthetic_scope)
    return child, [item for item in private_tokens if item]


def _private_variants(tokens: Iterable[bytes]) -> set[bytes]:
    variants: set[bytes] = set()
    for raw in tokens:
        if not raw:
            continue
        variants.add(raw)
        variants.add(_sha256(raw).encode("ascii"))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        variants.add(json.dumps(text, ensure_ascii=True)[1:-1].encode("ascii"))
        variants.add(json.dumps(text, ensure_ascii=False)[1:-1].encode("utf-8"))
    return {item for item in variants if item}


def _assert_private_tokens_absent(artifacts: dict[str, bytes], tokens: Iterable[bytes]) -> None:
    variants = _private_variants(tokens)
    for name, raw in artifacts.items():
        if any(value in raw for value in variants):
            raise CaptureError(
                "PRIVATE_VALUE_ARCHIVE_REJECTED",
                f"capture artifact contains a retired identity or source locator: {name}",
            )


def _run_validator(
    validator_arguments: Sequence[str],
    *,
    inner_dir: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(VALIDATOR),
        "--evidence-dir",
        str(inner_dir),
        *validator_arguments,
    ]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process: subprocess.Popen[bytes] | None = None
    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
        try:
            process = subprocess.Popen(
                command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=env,
            )
        except OSError:
            return {
                "termination_reason": "SPAWN_FAILED",
                "observed_os_exit_code": None,
                "process_returncode_after_termination": None,
            }
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
            return {
                "termination_reason": "TIMEOUT",
                "observed_os_exit_code": None,
                "process_returncode_after_termination": returncode,
            }
    return {
        "termination_reason": "EXITED",
        "observed_os_exit_code": returncode,
        "process_returncode_after_termination": returncode,
    }


def _inner_binding(
    inner_dir: Path,
    *,
    stdout_raw: bytes,
    stderr_raw: bytes,
    observed_exit: int | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    if not inner_dir.exists():
        return (
            {
                "record_status": "ABSENT",
                "binding_status": "NOT_APPLICABLE",
                "run_id": None,
                "record_sha256": None,
                "manifest_file_sha256": None,
                "validation_delivery_gate_status": "NOT_AVAILABLE",
                "validation_exit_code": None,
            },
            {},
        )
    try:
        manifest, artifacts = inner_replay._load_record(inner_dir)
        invocation = inner_replay._validate_invocation(manifest, artifacts)
        result = inner_replay._validate_cross_artifact_consistency(
            manifest,
            artifacts,
            invocation,
        )
    except (inner_replay.ReplayError, OSError) as error:
        return (
            {
                "record_status": "INVALID",
                "binding_status": "FAIL",
                "error_code": getattr(error, "code", "INNER_RECORD_IO_ERROR"),
                "run_id": None,
                "record_sha256": None,
                "manifest_file_sha256": None,
                "validation_delivery_gate_status": "NOT_AVAILABLE",
                "validation_exit_code": None,
            },
            {},
        )
    binding_status = "PASS"
    if (
        artifacts.get("rendered-output.txt") != stdout_raw
        or artifacts.get("stderr.txt") != stderr_raw
        or manifest.get("exit_code") != observed_exit
        or result.get("exit_code") != observed_exit
    ):
        binding_status = "FAIL"
    return (
        {
            "record_status": "PRESENT",
            "binding_status": binding_status,
            "run_id": manifest.get("run_id"),
            "record_sha256": manifest.get("record_sha256"),
            "manifest_file_sha256": _sha256(artifacts["evidence-manifest.json"]),
            "validation_delivery_gate_status": result.get("delivery_gate_status"),
            "validation_exit_code": result.get("exit_code"),
        },
        artifacts,
    )


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise CaptureError("UNSAFE_ARTIFACT_PATH", "capture artifact path is unsafe")
    return path.as_posix()


def _tree_artifacts(root: Path) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    for path in root.rglob("*"):
        _assert_no_reparse_ancestors(path)
        if path.is_symlink():
            raise CaptureError("REPARSE_POINT_REJECTED", "capture tree contains a symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CaptureError("NON_REGULAR_ARTIFACT", "capture tree contains a special file")
        info = path.lstat()
        if int(getattr(info, "st_nlink", 1)) != 1:
            raise CaptureError("HARDLINK_REJECTED", "capture tree contains a hard link")
        relative = _safe_relative(path.relative_to(root).as_posix())
        artifacts[relative] = path.read_bytes()
    return artifacts


def _verify_exact_tree(root: Path, expected: dict[str, bytes]) -> None:
    actual = _tree_artifacts(root)
    if set(actual) != set(expected):
        raise CaptureError("CAPTURE_INVENTORY_MISMATCH", "capture inventory differs")
    for name, raw in expected.items():
        if actual[name] != raw:
            raise CaptureError("CAPTURE_BYTES_MISMATCH", f"capture bytes differ: {name}")


def _publish_staging(
    staging: Path,
    output_root: Path,
    manifest: dict[str, Any],
) -> str:
    capture_id = str(manifest["capture_id"])
    final = output_root / capture_id
    expected = _tree_artifacts(staging)
    lock = output_root / f".{capture_id}.publish.lock"
    lock_fd: int | None = None
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        if final.exists() or final.is_symlink():
            _assert_no_reparse_ancestors(final)
            if not final.is_dir():
                raise CaptureError("CAPTURE_ID_CONFLICT", "capture ID target is not a directory")
            _verify_exact_tree(final, expected)
            _verify_exact_tree(final, expected)
            return "IDEMPOTENT_REPLAY"
        _verify_exact_tree(staging, expected)
        staging.rename(final)
        _verify_exact_tree(final, expected)
        return "PUBLISHED"
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                lock.unlink()
            except OSError:
                pass


def capture_validation(
    validator_arguments: Sequence[str],
    *,
    output_root: Path,
    timeout_seconds: float = 120.0,
    stream_limit_bytes: int = DEFAULT_STREAM_LIMIT,
) -> tuple[dict[str, Any], int]:
    if not validator_arguments:
        validator_arguments = []
    if any(_option_name(token) == "--evidence-dir" for token in validator_arguments):
        raise CaptureError(
            "CALLER_EVIDENCE_DIR_REJECTED",
            "the parent process exclusively controls the validator evidence directory",
        )
    _argument_layout(validator_arguments)
    if timeout_seconds <= 0 or timeout_seconds > 3600:
        raise CaptureError("INVALID_TIMEOUT", "timeout must be between 0 and 3600 seconds")
    if stream_limit_bytes < 1024 or stream_limit_bytes > 256 * 1024 * 1024:
        raise CaptureError("INVALID_STREAM_LIMIT", "stream limit is outside the supported range")

    output_root = _absolute_without_resolving(output_root)
    if _is_within(output_root, SKILL_ROOT):
        raise CaptureError(
            "OUTPUT_INSIDE_SKILL_REJECTED",
            "capture output must not pollute the installed Skill tree",
        )
    _assert_no_reparse_ancestors(output_root.parent)
    output_root.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_ancestors(output_root)

    redacted_arguments, private_tokens = _redacted_argument_shape(validator_arguments)
    policy_before = _capture_policy_hashes()
    staging = Path(
        tempfile.mkdtemp(prefix=".humanize-capture-staging-", dir=output_root)
    )
    published = False
    try:
        launch_dir = staging / "launch-inputs"
        launch_dir.mkdir()
        child_arguments, launch_private = _prepare_child_arguments(
            validator_arguments,
            launch_dir,
        )
        private_tokens.extend(launch_private)
        inner_dir = staging / "validation-record"
        raw_stdout_path = staging / ".child-stdout.tmp"
        raw_stderr_path = staging / ".child-stderr.tmp"
        process_state = _run_validator(
            child_arguments,
            inner_dir=inner_dir,
            stdout_path=raw_stdout_path,
            stderr_path=raw_stderr_path,
            timeout_seconds=timeout_seconds,
        )
        stdout_raw = raw_stdout_path.read_bytes()
        stderr_raw = raw_stderr_path.read_bytes()
        if len(stdout_raw) > stream_limit_bytes or len(stderr_raw) > stream_limit_bytes:
            raise CaptureError(
                "STREAM_LIMIT_EXCEEDED",
                "validator stdout or stderr exceeded the capture limit",
            )
        raw_stdout_path.unlink()
        raw_stderr_path.unlink()
        shutil.rmtree(launch_dir)

        policy_after = _capture_policy_hashes()
        policy_stable = policy_before == policy_after
        inner_state, _inner_artifacts = _inner_binding(
            inner_dir,
            stdout_raw=stdout_raw,
            stderr_raw=stderr_raw,
            observed_exit=process_state["observed_os_exit_code"],
        )
        capture_integrity = "PASS"
        failure_reasons: list[str] = []
        if not policy_stable:
            capture_integrity = "FAIL"
            failure_reasons.append("CAPTURE_OR_VALIDATOR_POLICY_DRIFT")
        if process_state["termination_reason"] != "EXITED":
            capture_integrity = "FAIL"
            failure_reasons.append(process_state["termination_reason"])
        if inner_state["record_status"] != "PRESENT":
            capture_integrity = "FAIL"
            failure_reasons.append("INNER_VALIDATION_RECORD_NOT_AVAILABLE")
        elif inner_state["binding_status"] != "PASS":
            capture_integrity = "FAIL"
            failure_reasons.append("INNER_PROCESS_OBSERVATION_MISMATCH")

        if capture_integrity == "PASS":
            status = str(inner_state["validation_delivery_gate_status"])
            exit_code = int(inner_state["validation_exit_code"])
        else:
            status = "FAIL"
            exit_code = 1

        invocation = {
            "schema": CAPTURE_INVOCATION_SCHEMA,
            "validator_entrypoint": "scripts/validate_humanize_output.py",
            "validator_arguments_redacted": redacted_arguments,
            "validator_evidence_directory_injected_by_parent": True,
            "raw_argv_archived": False,
            "raw_argv_digest_archived": False,
            "source_locator_archived": False,
            "reviewer_identifier_archived": False,
            "stable_reviewer_pseudonym_archived": False,
            "contains_unredacted_proposal_text": any(
                _option_name(token) == "--propose-warning-resolution"
                for token in validator_arguments
            ),
            "policy_hashes_before_execution": policy_before,
        }
        observation = {
            "schema": PROCESS_OBSERVATION_SCHEMA,
            "observation_scope": "SAME_HOST_SAME_USER_PARENT_PROCESS",
            "termination_reason": process_state["termination_reason"],
            "observed_os_exit_code": process_state["observed_os_exit_code"],
            "process_returncode_after_termination": process_state[
                "process_returncode_after_termination"
            ],
            "stdout": {"sha256": _sha256(stdout_raw), "size": len(stdout_raw)},
            "stderr": {"sha256": _sha256(stderr_raw), "size": len(stderr_raw)},
            "stdout_stderr_interleaving": "NOT_CAPTURED",
            "inner_record": inner_state,
            "capture_policy_stable_during_execution": policy_stable,
            "capture_integrity_status": capture_integrity,
            "validation_delivery_gate_status": inner_state[
                "validation_delivery_gate_status"
            ],
            "failure_reasons": sorted(set(failure_reasons)),
            "historical_authenticity": "NOT_EVALUATED",
            "external_anchor_status": "NOT_PROVIDED",
            "academic_correctness": "NOT_EVALUATED",
            "paired_quality_clearance_granted": False,
            "humanize_quality_claim_allowed": False,
        }
        _write_exclusive(staging / "capture-invocation.json", _pretty_json_bytes(invocation))
        _write_exclusive(staging / "process-observation.json", _pretty_json_bytes(observation))
        _write_exclusive(staging / "observed-stdout.bin", stdout_raw)
        _write_exclusive(staging / "observed-stderr.bin", stderr_raw)

        artifacts = _tree_artifacts(staging)
        _assert_private_tokens_absent(artifacts, private_tokens)
        artifact_records = {
            name: {"sha256": _sha256(raw), "size": len(raw)}
            for name, raw in sorted(artifacts.items())
        }
        record_identity = {
            "schema": CAPTURE_MANIFEST_SCHEMA,
            "artifacts": artifact_records,
        }
        record_sha = _sha256(_canonical_json_bytes(record_identity))
        capture_id = f"hvc1-{record_sha}"
        manifest_body = {
            "schema": CAPTURE_MANIFEST_SCHEMA,
            "capture_id": capture_id,
            "record_sha256": record_sha,
            "integrity_scope": "PARENT_PROCESS_OBSERVATION_SELF_CONSISTENCY",
            "observation_scope": "SAME_HOST_SAME_USER_PARENT_PROCESS",
            "historical_authenticity": "NOT_EVALUATED",
            "external_anchor_status": "NOT_PROVIDED",
            "contains_source_content": True,
            "status": status,
            "exit_code": exit_code,
            "capture_integrity_status": capture_integrity,
            "validation_delivery_gate_status": inner_state[
                "validation_delivery_gate_status"
            ],
            "observed_os_exit_code": process_state["observed_os_exit_code"],
            "inner_run_id": inner_state["run_id"],
            "inner_record_sha256": inner_state["record_sha256"],
            "artifacts": artifact_records,
        }
        manifest = {
            **manifest_body,
            "manifest_sha256": _sha256(_canonical_json_bytes(manifest_body)),
        }
        _write_exclusive(staging / "capture-manifest.json", _pretty_json_bytes(manifest))
        publication_status = _publish_staging(staging, output_root, manifest)
        published = publication_status == "PUBLISHED"
        payload = {
            "schema": CAPTURE_MANIFEST_SCHEMA,
            "status": status,
            "exit_code": exit_code,
            "capture_integrity_status": capture_integrity,
            "validation_delivery_gate_status": inner_state[
                "validation_delivery_gate_status"
            ],
            "observed_os_exit_code": process_state["observed_os_exit_code"],
            "capture_id": capture_id,
            "capture_record": str(output_root / capture_id),
            "publication_status": publication_status,
            "historical_authenticity": "NOT_EVALUATED",
            "academic_correctness": "NOT_EVALUATED",
            "paired_quality_clearance_granted": False,
            "humanize_quality_claim_allowed": False,
        }
        return payload, exit_code
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, CaptureError):
        error_code = error.code
        safe_message = str(error)
    elif isinstance(error, OSError):
        error_code = "CAPTURE_IO_ERROR"
        safe_message = SAFE_UNEXPECTED_ERROR_MESSAGES[error_code]
    elif isinstance(error, UnicodeError):
        error_code = "CAPTURE_ENCODING_ERROR"
        safe_message = SAFE_UNEXPECTED_ERROR_MESSAGES[error_code]
    else:
        error_code = "CAPTURE_VALUE_ERROR"
        safe_message = SAFE_UNEXPECTED_ERROR_MESSAGES[error_code]
    return {
        "schema": CAPTURE_ERROR_SCHEMA,
        "status": "FAIL",
        "exit_code": 1,
        "capture_integrity_status": "FAIL",
        "error_code": error_code,
        "error": safe_message,
        "historical_authenticity": "NOT_EVALUATED",
        "academic_correctness": "NOT_EVALUATED",
        "paired_quality_clearance_granted": False,
        "humanize_quality_claim_allowed": False,
    }


def _text_output(payload: dict[str, Any]) -> str:
    lines = [
        f"status: {payload['status']}",
        f"capture_integrity_status: {payload['capture_integrity_status']}",
        f"validation_delivery_gate_status: {payload.get('validation_delivery_gate_status', 'NOT_AVAILABLE')}",
        f"observed_os_exit_code: {payload.get('observed_os_exit_code', 'NOT_AVAILABLE')}",
        f"capture_id: {payload.get('capture_id', 'NONE')}",
        f"capture_record: {payload.get('capture_record', 'NONE')}",
        f"historical_authenticity: {payload['historical_authenticity']}",
        f"academic_correctness: {payload['academic_correctness']}",
        "paired_quality_clearance_granted: "
        + str(payload["paired_quality_clearance_granted"]).upper(),
        "humanize_quality_claim_allowed: "
        + str(payload["humanize_quality_claim_allowed"]).upper(),
    ]
    if payload.get("error_code"):
        lines.append(f"error_code: {payload['error_code']}")
        lines.append(f"error: {payload['error']}")
    return "\n".join(lines) + "\n"


def _capture_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the fixed Humanize validator from an independent parent process.",
        usage=(
            "%(prog)s --output-root OUTPUT_ROOT [capture-options] "
            "-- <validator-arguments>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        epilog=(
            "Required invocation form:\n"
            "  python scripts/capture_humanize_validation.py "
            "--output-root <outside-skill> -- <validator-arguments>\n\n"
            "Complete examples:\n"
            "  python scripts/capture_humanize_validation.py "
            "--output-root ..\\humanize-captures -- before.md after.md "
            "--scene GENERAL --format json\n"
            "  python scripts/capture_humanize_validation.py "
            "--output-root ..\\humanize-captures -- supplied.md draft.md "
            "--mode DRAFT --scene COURSE --format json\n\n"
            "The literal -- separator is required; every argument after it is passed "
            "to validate_humanize_output.py."
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--stream-limit-bytes",
        type=int,
        default=DEFAULT_STREAM_LIMIT,
    )
    parser.add_argument(
        "--capture-format",
        choices=("json", "text"),
        default="json",
    )
    return parser


def _split_arguments(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    values = list(argv)
    separator = values.index("--") if "--" in values else len(values)
    if any(token in {"-h", "--help"} for token in values[:separator]):
        _capture_argument_parser().print_help()
        raise SystemExit(0)
    if separator == len(values):
        raise CaptureError(
            "MISSING_VALIDATOR_SEPARATOR",
            "capture options and validator arguments must be separated by --",
        )
    return _capture_argument_parser().parse_args(values[:separator]), values[separator + 1 :]


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        args, validator_arguments = _split_arguments(
            list(argv) if argv is not None else sys.argv[1:]
        )
        payload, exit_code = capture_validation(
            validator_arguments,
            output_root=args.output_root,
            timeout_seconds=args.timeout_seconds,
            stream_limit_bytes=args.stream_limit_bytes,
        )
        output_format = args.capture_format
    except (CaptureError, OSError, UnicodeError, ValueError) as error:
        payload = _error_payload(error)
        exit_code = 1
        output_format = "json"
    if output_format == "json":
        sys.stdout.buffer.write(_pretty_json_bytes(payload))
    else:
        sys.stdout.write(_text_output(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
