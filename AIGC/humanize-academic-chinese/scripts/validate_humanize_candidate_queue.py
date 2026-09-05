#!/usr/bin/env python3
"""Validate a source-action-bound rewrite candidate without exporting corpus prose.

This is a publication gate for a *candidate package*, not a text generator and
not an academic-correctness checker.  It proves only mechanical facts: the
selected action cards are available for the declared scene, declared anchors
survive in the candidate, existing invariant/style gates pass, and the rewrite
does not copy a long Chinese run from the action-card source ranges or retain a
known automatic template.  Claims, evidence roles, and causal explanations
remain explicitly outside automatic verification.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_CATALOG = SKILL_DIR / "references" / "corpus-action-sources.json"
ACTION_PROFILE_SCRIPT = SCRIPT_DIR / "build_humanize_action_profile.py"
OUTPUT_VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_humanize_output.py"
INVARIANT_SCRIPT = SCRIPT_DIR / "check_humanize_invariants.py"
LEXICAL_SCANNER_SCRIPT = SCRIPT_DIR / "scan_humanize_chinese.py"
REPETITION_GUARD_AUDITOR_SCRIPT = SCRIPT_DIR / "audit_humanize_repetition_guards.py"
LEXICON_PATH = SKILL_DIR / "references" / "lexical-signals.json"
CANDIDATE_SCENES = {"COURSE", "MODELING", "RESEARCH", "GENERAL", "REPORT"}
CORPUS_ACTION_SUPPORT_MODES = {"ACTION_CARDS", "NONE"}
CANDIDATE_SCHEMA_VERSION = "2.0"
CANDIDATE_ALLOWED_FIELDS = {
    "schema_version",
    "candidate_id",
    "scene",
    "corpus_action_support",
    "before_path",
    "after_path",
    "action_cards",
    "action_evidence",
    "anchors",
    "keep_reasons",
    "warning_resolutions",
    "warning_review_request_sha256",
    "warning_review",
    "supersedes_candidate_sha256",
}
SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
COPY_JOINERS = frozenset(" \t，。；：、！？,.!?;:（）()[]【】“”‘’—…·-_")
MAX_COPY_JOINER_RUN = 3
COPY_HARD_BOUNDARY = "\0"
COPY_LINE_BREAKS = frozenset("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")
COPY_INVISIBLE_JOINERS = frozenset("\u200b\u200c\u200d\u2060\ufeff")
_QUEUE_LOCKS: dict[str, threading.RLock] = {}
_QUEUE_LOCKS_GUARD = threading.Lock()

# These patterns are deliberately narrow. They reject automatic exits and
# paragraph-shape reuse; they are not a general Chinese-style scoring system.
FUTURE_BRIDGE_RE = re.compile(
    r"(?:为|给|供)(?:后续|未来)(?:研究|分析|检验|工作|探索)?.{0,12}"
    r"(?:提供|奠定|打下|形成).{0,12}(?:基础|支撑|线索|参考|依据|方向)"
)
FORCED_CONTRAST_RE = re.compile(r"不是[^。；！？!?]{1,80}?而是")
SURFACE_RE = re.compile(r"(?:表面|简单).{0,24}(?:解释|现象|问题|误差)")
DEEP_RE = re.compile(r"(?:更深层|深层|内在).{0,24}(?:机制|原因|解释)")
LIMIT_RE = re.compile(r"(?:局限|不能(?:证明|排除|确定)|尚不能|未能)")


class CandidateError(ValueError):
    """Raised for a malformed candidate package."""


class InvalidEvidence(ValueError):
    """Raised when a detector returns evidence outside its fixed schema."""


def _reject_queue_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _reject_queue_nonfinite(value: str) -> Any:
    raise CandidateError(f"non_finite_json_number:{value}")


@contextmanager
def _queue_lock(queue_dir: Path):
    """Serialize queue inspection and publication across threads/processes."""
    queue_dir.mkdir(parents=True, exist_ok=True)
    key = str(queue_dir.resolve()).casefold()
    with _QUEUE_LOCKS_GUARD:
        local_lock = _QUEUE_LOCKS.setdefault(key, threading.RLock())
    with local_lock:
        lock_path = queue_dir / ".queue.lock"
        lock_path.touch(exist_ok=True)
        handle = lock_path.open("r+b")
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                for _attempt in range(600):
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
                else:
                    raise CandidateError("queue_lock_timeout")
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CandidateError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


action_profile = _load_module("humanize_action_profile_for_candidate", ACTION_PROFILE_SCRIPT)
output_validator = _load_module("humanize_output_validator_for_candidate", OUTPUT_VALIDATOR_SCRIPT)
repetition_guards = _load_module(
    "humanize_repetition_guards_for_candidate",
    REPETITION_GUARD_AUDITOR_SCRIPT,
)


def _sha256(value: bytes | str) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stat_identity(stat_result: os.stat_result) -> tuple[int, int, int, int, int]:
    """Return the strongest portable identity tuple exposed by ``stat``."""
    return (
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        int(stat_result.st_ctime_ns),
    )


def _read_stable_bytes(path: Path, label: str) -> tuple[bytes, tuple[int, int, int, int, int]]:
    try:
        stat_before = path.stat()
        raw = path.read_bytes()
        stat_after = path.stat()
    except (OSError, UnicodeError) as error:
        raise CandidateError(f"snapshot_error:{label}:{type(error).__name__}") from error
    before_identity = _stat_identity(stat_before)
    after_identity = _stat_identity(stat_after)
    if before_identity != after_identity or len(raw) != stat_after.st_size:
        raise CandidateError(f"changed_during_snapshot:{label}")
    return raw, after_identity


def _verify_stable_bytes(
    path: Path,
    *,
    label: str,
    expected_raw: bytes,
    expected_stat: tuple[int, int, int, int, int],
) -> None:
    try:
        current_raw, current_stat = _read_stable_bytes(path, label)
    except CandidateError as error:
        raise CandidateError(f"snapshot_changed:{label}:missing_or_unreadable") from error
    if current_raw != expected_raw or current_stat != expected_stat:
        raise CandidateError(f"snapshot_changed:{label}")


def _artifact_snapshot(
    candidate_path: Path,
    parsed: dict[str, Any],
    *,
    candidate_raw: bytes | None = None,
) -> dict[str, Any]:
    """Read all bytes once and bind validation/publication to that snapshot."""
    paths: dict[str, Path] = {"candidate_package": candidate_path}
    for label in ("before", "after"):
        path = parsed[f"{label}_path"]
        if path is not None:
            paths[label] = path
    raw_by_label: dict[str, bytes] = {}
    stat_by_label: dict[str, tuple[int, int, int, int, int]] = {}
    for label, path in paths.items():
        try:
            raw, identity = _read_stable_bytes(path, f"artifact:{label}")
        except CandidateError as error:
            raise CandidateError(f"artifact_snapshot_error:{label}") from error
        if label == "candidate_package" and candidate_raw is not None and raw != candidate_raw:
            raise CandidateError(f"artifact_changed_during_snapshot:{label}")
        raw_by_label[label] = raw
        stat_by_label[label] = identity
    return {"raw": raw_by_label, "stat": stat_by_label}


def _candidate_fingerprint(snapshot: dict[str, Any]) -> dict[str, str]:
    """Bind queue identity to the exact validation snapshot bytes."""
    raw_by_label: dict[str, bytes] = snapshot["raw"]
    components: list[tuple[str, bytes]] = [("candidate_package", raw_by_label["candidate_package"])]
    for label in ("before", "after"):
        components.append((label, raw_by_label.get(label, b"")))
    digest = hashlib.sha256()
    hashes: dict[str, str] = {}
    for label, raw in components:
        hashes[f"{label}_sha256"] = _sha256(raw)
        label_bytes = label.encode("ascii")
        digest.update(len(label_bytes).to_bytes(4, "big"))
        digest.update(label_bytes)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    hashes["artifact_sha256"] = digest.hexdigest()
    return hashes


def _verify_artifact_snapshot(snapshot: dict[str, Any], parsed: dict[str, Any], candidate_path: Path) -> None:
    """Reject publication if any validated artifact changed after validation."""
    paths: dict[str, Path] = {"candidate_package": candidate_path}
    for label in ("before", "after"):
        path = parsed[f"{label}_path"]
        if path is not None:
            paths[label] = path
    for label, path in paths.items():
        try:
            _verify_stable_bytes(
                path,
                label=f"artifact:{label}",
                expected_raw=snapshot["raw"].get(label, b""),
                expected_stat=snapshot["stat"][label],
            )
        except CandidateError as error:
            raise CandidateError(f"artifact_changed_before_publish:{label}")


def _read_json_snapshot(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw, _identity = _read_stable_bytes(path, "candidate_package")
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_queue_duplicate_keys,
            parse_constant=_reject_queue_nonfinite,
        )
    except CandidateError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CandidateError(
            f"candidate_read_error:{type(error).__name__}"
        ) from error
    if not isinstance(value, dict):
        raise CandidateError("candidate package must be a JSON object")
    return value, raw


def _text(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"invalid_{label}")
        return ""
    return value.strip()


def _resolve_path(
    value: Any,
    label: str,
    candidate_path: Path,
    errors: list[str],
    allowed_root: Path | None = None,
) -> Path | None:
    raw = _text(value, label, errors)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = candidate_path.parent / path
    path = path.resolve()
    if allowed_root is not None:
        try:
            path.relative_to(allowed_root)
        except ValueError:
            errors.append(f"{label}_outside_allowed_root")
            return None
    if not path.is_file():
        errors.append(f"missing_{label}")
        return None
    return path


def _string_map(value: Any, label: str, errors: list[str]) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(f"invalid_{label}")
        return {}
    parsed: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            errors.append(f"invalid_{label}_entry")
            continue
        parsed[key] = item
    return parsed


def _parse_warning_review(
    value: Any,
    *,
    present: bool,
    warning_resolutions: dict[str, str],
    warning_review_request_sha256: str,
    errors: list[str],
) -> tuple[str, str]:
    """Validate an identity-free caller proposal; it never grants clearance."""
    if present:
        errors.append("warning_reviewer_identity_metadata_retired")
    if not warning_resolutions:
        if warning_review_request_sha256:
            errors.append("warning_review_request_without_warning_resolutions")
        return "NONE", ""

    if not re.fullmatch(r"[0-9a-f]{64}", warning_review_request_sha256):
        errors.append("invalid_warning_review_request_sha256")
    return "NONE", ""


def _parse_candidate(
    candidate: dict[str, Any],
    candidate_path: Path,
    *,
    allowed_root: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    unknown_fields = sorted(set(candidate) - CANDIDATE_ALLOWED_FIELDS)
    if unknown_fields:
        errors.append("unknown_candidate_fields:" + ",".join(unknown_fields))
    schema_version = candidate.get("schema_version", CANDIDATE_SCHEMA_VERSION)
    if schema_version != CANDIDATE_SCHEMA_VERSION:
        errors.append(f"invalid_candidate_schema_version:{schema_version}")
    if "accepted_warnings" in candidate:
        errors.append("retired_accepted_warnings_field")
    candidate_id = _text(candidate.get("candidate_id"), "candidate_id", errors)
    if candidate_id and not SAFE_ID_RE.fullmatch(candidate_id):
        errors.append("unsafe_candidate_id")
    scene = _text(candidate.get("scene"), "scene", errors).upper()
    if scene and scene not in CANDIDATE_SCENES:
        errors.append(f"invalid_scene:{scene}")
    corpus_action_support = candidate.get("corpus_action_support", "ACTION_CARDS")
    if not isinstance(corpus_action_support, str):
        errors.append("invalid_corpus_action_support")
        corpus_action_support = "ACTION_CARDS"
    corpus_action_support = corpus_action_support.upper()
    if corpus_action_support not in CORPUS_ACTION_SUPPORT_MODES:
        errors.append(f"invalid_corpus_action_support:{corpus_action_support}")
    before_path = _resolve_path(candidate.get("before_path"), "before_path", candidate_path, errors, allowed_root)
    after_path = _resolve_path(candidate.get("after_path"), "after_path", candidate_path, errors, allowed_root)
    supersedes = candidate.get("supersedes_candidate_sha256", "")
    if supersedes is None:
        supersedes = ""
    if not isinstance(supersedes, str) or (supersedes and not re.fullmatch(r"[0-9a-f]{64}", supersedes)):
        errors.append("invalid_supersedes_candidate_sha256")
        supersedes = ""

    cards_value = candidate.get("action_cards")
    action_cards: list[str] = []
    if not isinstance(cards_value, list):
        errors.append("invalid_action_cards")
    else:
        for card_id in cards_value:
            if not isinstance(card_id, str) or not card_id.strip():
                errors.append("invalid_action_card_id")
                continue
            if card_id in action_cards:
                errors.append(f"duplicate_action_card:{card_id}")
                continue
            action_cards.append(card_id)

    anchors_value = candidate.get("anchors")
    anchors: dict[str, dict[str, str]] = {}
    if not isinstance(anchors_value, list) or not anchors_value:
        errors.append("invalid_anchors")
    else:
        for index, raw_anchor in enumerate(anchors_value, start=1):
            if not isinstance(raw_anchor, dict):
                errors.append(f"invalid_anchor:{index}")
                continue
            anchor_id = _text(raw_anchor.get("id"), f"anchor_id:{index}", errors)
            before_text = _text(raw_anchor.get("before_text"), f"anchor_before:{index}", errors)
            after_text = _text(raw_anchor.get("after_text"), f"anchor_after:{index}", errors)
            role = _text(raw_anchor.get("role"), f"anchor_role:{index}", errors)
            if anchor_id:
                if anchor_id in anchors:
                    errors.append(f"duplicate_anchor:{anchor_id}")
                else:
                    anchors[anchor_id] = {
                        "before_text": before_text,
                        "after_text": after_text,
                        "role": role,
                    }

    action_evidence_value = candidate.get("action_evidence")
    action_evidence: dict[str, list[str]] = {}
    if not isinstance(action_evidence_value, dict):
        errors.append("invalid_action_evidence")
    else:
        for card_id, anchor_ids in action_evidence_value.items():
            if not isinstance(card_id, str) or not isinstance(anchor_ids, list) or not anchor_ids:
                errors.append("invalid_action_evidence_entry")
                continue
            parsed_ids: list[str] = []
            for anchor_id in anchor_ids:
                if not isinstance(anchor_id, str) or not anchor_id:
                    errors.append(f"invalid_action_evidence_anchor:{card_id}")
                    continue
                if anchor_id not in parsed_ids:
                    parsed_ids.append(anchor_id)
            action_evidence[card_id] = parsed_ids

    if corpus_action_support == "NONE":
        if action_cards:
            errors.append("corpus_action_support_none_with_action_cards")
        if action_evidence:
            errors.append("corpus_action_support_none_with_action_evidence")
    elif not action_cards:
        errors.append("invalid_action_cards")

    warning_resolutions = _string_map(
        candidate.get("warning_resolutions"), "warning_resolutions", errors
    )
    request_value = candidate.get("warning_review_request_sha256", "")
    if request_value is None:
        request_value = ""
    if not isinstance(request_value, str):
        errors.append("invalid_warning_review_request_sha256")
        request_value = ""
    warning_review_request_sha256 = request_value.strip().lower()
    warning_reviewer_kind, warning_reviewer_id = _parse_warning_review(
        candidate.get("warning_review"),
        present="warning_review" in candidate,
        warning_resolutions=warning_resolutions,
        warning_review_request_sha256=warning_review_request_sha256,
        errors=errors,
    )

    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "scene": scene,
        "corpus_action_support": corpus_action_support,
        "before_path": before_path,
        "after_path": after_path,
        "action_cards": action_cards,
        "anchors": anchors,
        "action_evidence": action_evidence,
        "keep_reasons": _string_map(candidate.get("keep_reasons"), "keep_reasons", errors),
        "warning_resolutions": warning_resolutions,
        "warning_review_request_sha256": warning_review_request_sha256,
        "warning_reviewer_kind": warning_reviewer_kind,
        "warning_reviewer_id": warning_reviewer_id,
        "supersedes_candidate_sha256": supersedes,
    }, errors


def _write_frozen_file(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    try:
        path.chmod(0o444)
    except OSError:
        pass
    return path


def _snapshot_source_state(path: Path, *, label: str, read_content: bool) -> dict[str, Any]:
    """Capture one original source without silently changing missing/unreadable state."""
    if not read_content:
        try:
            identity = _stat_identity(path.stat())
        except FileNotFoundError:
            return {"path": path, "state": "MISSING", "stat": None, "raw": None}
        except OSError:
            return {"path": path, "state": "UNREADABLE", "stat": None, "raw": None}
        return {"path": path, "state": "EXCLUDED_PRESENT", "stat": identity, "raw": None}
    try:
        raw, identity = _read_stable_bytes(path, label)
    except CandidateError as error:
        try:
            path.stat()
        except FileNotFoundError:
            return {"path": path, "state": "MISSING", "stat": None, "raw": None}
        except OSError:
            return {"path": path, "state": "UNREADABLE", "stat": None, "raw": None}
        raise CandidateError(f"source_snapshot_unstable:{label}") from error
    return {"path": path, "state": "CAPTURED", "stat": identity, "raw": raw}


def _snapshot_catalog_bundle(catalog_path: Path, frozen_root: Path) -> dict[str, Any]:
    """Freeze the catalog and every non-excluded registered source once."""
    catalog_path = catalog_path.resolve()
    catalog_raw, catalog_stat = _read_stable_bytes(catalog_path, "catalog")
    original_copy = _write_frozen_file(frozen_root / "catalog-original.json", catalog_raw)
    try:
        original_catalog = action_profile.load_catalog(original_copy)
        original_sources = action_profile._source_index(original_catalog)
    except (action_profile.CatalogError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CandidateError(
            f"catalog_snapshot_runtime_error:{type(error).__name__}"
        ) from error

    frozen_catalog = copy.deepcopy(original_catalog)
    frozen_sources = action_profile._source_index(frozen_catalog)
    source_states: dict[str, dict[str, Any]] = {}
    excluded_roles = set(getattr(action_profile, "EXCLUDED_ROLES", ()))
    for index, (source_id, original_source) in enumerate(original_sources.items(), start=1):
        original_path = Path(str(original_source["path"]))
        if not original_path.is_absolute():
            original_path = (catalog_path.parent / original_path).resolve()
        else:
            original_path = original_path.resolve()
        excluded = str(original_source.get("role", "")) in excluded_roles
        state = _snapshot_source_state(
            original_path,
            label=f"source:{source_id}",
            read_content=not excluded,
        )
        state.update({"source_id": source_id, "excluded": excluded})
        source_states[source_id] = state

        if excluded:
            # build_action_profile never opens excluded roles. Keep the path
            # semantically inert and normalize it out of the fingerprint.
            frozen_sources[source_id]["path"] = str(frozen_root / "excluded" / str(index))
            continue
        suffix = original_path.suffix or ".txt"
        frozen_path = frozen_root / "sources" / f"{index:04d}-{_sha256(source_id)[:12]}{suffix}"
        if state["state"] == "CAPTURED":
            _write_frozen_file(frozen_path, state["raw"])
        elif state["state"] == "UNREADABLE":
            frozen_path.mkdir(parents=True, exist_ok=True)
        frozen_sources[source_id]["path"] = str(frozen_path)

    frozen_catalog_raw = (
        json.dumps(frozen_catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    frozen_catalog_path = _write_frozen_file(frozen_root / "catalog.json", frozen_catalog_raw)
    return {
        "path": catalog_path,
        "raw": catalog_raw,
        "stat": catalog_stat,
        "original_catalog": original_catalog,
        "frozen_catalog_path": frozen_catalog_path,
        "source_states": source_states,
    }


def _verify_catalog_bundle(bundle: dict[str, Any]) -> None:
    try:
        _verify_stable_bytes(
            bundle["path"],
            label="catalog",
            expected_raw=bundle["raw"],
            expected_stat=bundle["stat"],
        )
    except CandidateError as error:
        raise CandidateError("catalog_changed_during_validation") from error
    for source_id, state in bundle["source_states"].items():
        path = state["path"]
        expected_state = state["state"]
        if expected_state == "CAPTURED":
            try:
                _verify_stable_bytes(
                    path,
                    label=f"source:{source_id}",
                    expected_raw=state["raw"],
                    expected_stat=state["stat"],
                )
            except CandidateError as error:
                raise CandidateError(f"source_changed_during_validation:{source_id}") from error
            continue
        if expected_state == "MISSING":
            if path.exists():
                raise CandidateError(f"source_changed_during_validation:{source_id}:READABLE")
            continue
        try:
            current_stat = _stat_identity(path.stat())
        except OSError as error:
            if expected_state == "UNREADABLE":
                continue
            raise CandidateError(f"source_changed_during_validation:{source_id}") from error
        if expected_state == "UNREADABLE":
            try:
                path.read_bytes()
            except OSError:
                continue
            raise CandidateError(f"source_changed_during_validation:{source_id}:READABLE")
        if state["stat"] is not None and current_stat != state["stat"]:
            raise CandidateError(f"source_changed_during_validation:{source_id}")


def _materialize_artifact_snapshot(
    snapshot: dict[str, Any],
    parsed: dict[str, Any],
    frozen_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    frozen_parsed = dict(parsed)
    restore_paths: dict[str, str] = {}
    for label in ("before", "after"):
        original = parsed[f"{label}_path"]
        if original is None or label not in snapshot["raw"]:
            continue
        suffix = original.suffix or ".txt"
        frozen = _write_frozen_file(frozen_root / "artifacts" / f"{label}{suffix}", snapshot["raw"][label])
        frozen_parsed[f"{label}_path"] = frozen
        restore_paths[str(frozen.resolve())] = str(original.resolve())
        restore_paths[str(frozen)] = str(original.resolve())
    return frozen_parsed, restore_paths


def _restore_snapshot_paths(value: Any, path_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _restore_snapshot_paths(item, path_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_snapshot_paths(item, path_map) for item in value]
    if isinstance(value, str):
        return path_map.get(value, value)
    return value


def _policy_snapshot() -> dict[str, Any]:
    paths = {
        "candidate_gate": Path(__file__).resolve(),
        "action_profile_builder": ACTION_PROFILE_SCRIPT,
        "output_validator": OUTPUT_VALIDATOR_SCRIPT,
        "invariant_checker": INVARIANT_SCRIPT,
        "lexical_scanner": LEXICAL_SCANNER_SCRIPT,
        "repetition_guard_auditor": REPETITION_GUARD_AUDITOR_SCRIPT,
        "lexicon": LEXICON_PATH,
        "source_provenance_trust": action_profile.DEFAULT_SOURCE_TRUST_POLICY,
    }
    states: dict[str, dict[str, Any]] = {}
    for label, path in paths.items():
        resolved = path.resolve()
        raw, identity = _read_stable_bytes(resolved, f"policy:{label}")
        states[label] = {"path": resolved, "raw": raw, "stat": identity}
    return {
        "hashes": {label: _sha256(state["raw"]) for label, state in states.items()},
        "states": states,
    }


def _verify_policy_snapshot(bundle: dict[str, Any]) -> None:
    for label, state in bundle["states"].items():
        try:
            _verify_stable_bytes(
                state["path"],
                label=f"policy:{label}",
                expected_raw=state["raw"],
                expected_stat=state["stat"],
            )
        except CandidateError as error:
            raise CandidateError(f"policy_changed_during_validation:{label}") from error


def _profile_fingerprint(profile: dict[str, Any]) -> str:
    normalized = copy.deepcopy(profile)
    normalized["catalog_path"] = "catalog:snapshot"
    normalized["source_trust_policy_path"] = "policy:source-provenance-trust"
    for source in normalized.get("sources", []):
        source["path"] = f"source:{source.get('id', 'UNKNOWN')}"
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(raw)


def _evaluation_fingerprint(
    artifact_hashes: dict[str, str],
    catalog_bundle: dict[str, Any],
    profile: dict[str, Any],
    policy_hashes: dict[str, str],
    parsed: dict[str, Any],
    allowed_root: Path | None,
    catalog_authority: str,
) -> dict[str, Any]:
    sources = {
        source_id: {
            "state": state["state"],
            "sha256": _sha256(state["raw"]) if state["raw"] is not None else None,
            "resolved_path_sha256": _sha256(str(state["path"])),
        }
        for source_id, state in sorted(catalog_bundle["source_states"].items())
    }
    resolved_inputs = {
        label: _sha256(str(parsed[f"{label}_path"].resolve()))
        if parsed.get(f"{label}_path") is not None
        else None
        for label in ("before", "after")
    }
    components = {
        "candidate_artifact_sha256": artifact_hashes["artifact_sha256"],
        "catalog_sha256": _sha256(catalog_bundle["raw"]),
        "source_profile_sha256": _profile_fingerprint(profile),
        "registered_sources": sources,
        "policy_files": dict(sorted(policy_hashes.items())),
        "resolved_input_path_hashes": resolved_inputs,
        "allowed_root_sha256": _sha256(str(allowed_root)) if allowed_root is not None else None,
        "catalog_authority": catalog_authority,
    }
    raw = json.dumps(components, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"evaluation_sha256": _sha256(raw), "components": components}


def _validate_queue_boundary(
    queue_dir: Path,
    *,
    candidate_path: Path,
    parsed: dict[str, Any],
    catalog_bundle: dict[str, Any],
) -> Path:
    queue = queue_dir.resolve()
    inputs: dict[str, Path] = {
        "candidate": candidate_path.resolve(),
        "catalog": catalog_bundle["path"].resolve(),
    }
    for label in ("before", "after"):
        path = parsed.get(f"{label}_path")
        if path is not None:
            inputs[label] = path.resolve()
    for source_id, state in catalog_bundle["source_states"].items():
        inputs[f"source:{source_id}"] = state["path"].resolve()
    for label, path in inputs.items():
        if queue == path:
            raise CandidateError(f"queue_input_alias:{label}")
        try:
            path.relative_to(queue)
        except ValueError:
            continue
        raise CandidateError(f"queue_contains_input:{label}")
    if queue.exists() and not queue.is_dir():
        raise CandidateError("queue_target_not_directory")
    return queue


def _redact_reviewer_label(value: Any, reviewer_id: str) -> Any:
    if not reviewer_id:
        return value
    replacement = "[REVIEWER_ID_REDACTED]"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            redacted_key = key.replace(reviewer_id, replacement) if isinstance(key, str) else key
            redacted[redacted_key] = _redact_reviewer_label(item, reviewer_id)
        return redacted
    if isinstance(value, list):
        return [_redact_reviewer_label(item, reviewer_id) for item in value]
    if isinstance(value, str):
        return value.replace(reviewer_id, replacement)
    return value


def _sanitized_candidate_raw(candidate: dict[str, Any], reviewer_id: str) -> bytes:
    sanitized = _redact_reviewer_label(copy.deepcopy(candidate), reviewer_id)
    warning_review = sanitized.get("warning_review")
    if isinstance(warning_review, dict) and "reviewer_id" in warning_review:
        warning_review.pop("reviewer_id", None)
        warning_review["reviewer_label_present"] = bool(reviewer_id)
        warning_review["raw_reviewer_label_archived"] = False
        warning_review["reviewer_label_digest_archived"] = False
        warning_review["cross_record_reviewer_linkability"] = "NOT_RECORDED"
        warning_review["identity_verified"] = False
    return (json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_catalog_for_copy(catalog_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    catalog = action_profile.load_catalog(catalog_path)
    sources = action_profile._source_index(catalog)
    return catalog, sources


def _verify_source_profile_state(
    profile: dict[str, Any],
    catalog_sources: dict[str, dict[str, Any]],
) -> None:
    """Ensure source files still match the profile used for this validation."""
    expected_by_id = {str(item.get("id")): item for item in profile.get("sources", [])}
    for source_id, expected in expected_by_id.items():
        if expected.get("status") == "EXCLUDED_CONFIG":
            continue
        source = catalog_sources.get(source_id)
        if source is None:
            raise CandidateError(f"source_profile_catalog_mismatch:{source_id}")
        path = Path(str(source.get("path", "")))
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            current_status = "MISSING"
            raw = b""
        except OSError:
            current_status = "UNREADABLE"
            raw = b""
        else:
            decoded, _encoding, _issue = action_profile.decode_source(raw)
            current_status = "READABLE" if decoded is not None else "SKIPPED_UNREADABLE"
        if current_status != expected.get("status"):
            raise CandidateError(f"source_changed_during_validation:{source_id}:{current_status}")
        expected_hash = str(expected.get("sha256", ""))
        if expected_hash and _sha256(raw) != expected_hash:
            raise CandidateError(f"source_changed_during_validation:{source_id}")


def _used_card_contract(
    parsed: dict[str, Any],
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    reviews: list[str] = []
    card_profile = {item["id"]: item for item in profile["action_cards"]}
    catalog_cards = {item["id"]: item for item in catalog["action_cards"]}
    selected: list[dict[str, Any]] = []
    scene = parsed["scene"]
    evidence = parsed["action_evidence"]
    anchors = parsed["anchors"]

    for card_id in parsed["action_cards"]:
        if card_id not in card_profile or card_id not in catalog_cards:
            errors.append(f"unknown_action_card:{card_id}")
            continue
        profile_card = card_profile[card_id]
        catalog_card = catalog_cards[card_id]
        if catalog_card["scene"] not in {"ALL", scene}:
            errors.append(f"scene_mismatch:{card_id}:{catalog_card['scene']}:{scene}")
        if catalog_card["kind"] == "negative_guard":
            errors.append(f"negative_guard_not_selectable:{card_id}")
        if profile_card["status"] != "AVAILABLE":
            reviews.append(f"unavailable_action_card:{card_id}")
        if profile_card.get("origin_assurance") == "PROVISIONAL":
            reviews.append(f"provisional_action_card:{card_id}")
        declared = evidence.get(card_id)
        if not declared:
            errors.append(f"missing_action_evidence:{card_id}")
        else:
            declared_roles: set[str] = set()
            for anchor_id in declared:
                if anchor_id not in anchors:
                    errors.append(f"action_evidence_unknown_anchor:{card_id}:{anchor_id}")
                else:
                    declared_roles.add(anchors[anchor_id]["role"])
            for required_role in catalog_card["required_anchor_roles"]:
                if required_role not in declared_roles:
                    errors.append(f"missing_anchor_role:{card_id}:{required_role}")
        selected.append({
            "id": card_id,
            "scene": catalog_card["scene"],
            "kind": catalog_card["kind"],
            "required_anchor_roles": catalog_card["required_anchor_roles"],
            "status": profile_card["status"],
            "origin_assurance": profile_card.get("origin_assurance", "UNKNOWN"),
            "source_origin_classes": profile_card.get("source_origin_classes", []),
            "source_refs": profile_card["source_refs"],
        })
    for card_id in evidence:
        if card_id not in parsed["action_cards"]:
            errors.append(f"action_evidence_for_unselected_card:{card_id}")
    return selected, errors, reviews, [catalog_cards[item["id"]] for item in selected]


def _anchor_contract(parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    before_path = parsed["before_path"]
    after_path = parsed["after_path"]
    if before_path is None or after_path is None:
        return errors
    try:
        before_text = before_path.read_text(encoding="utf-8-sig")
        after_text = after_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        return [f"candidate_text_read_error:{type(error).__name__}"]
    for anchor_id, anchor in parsed["anchors"].items():
        before_count = before_text.count(anchor["before_text"]) if anchor["before_text"] else 0
        after_count = after_text.count(anchor["after_text"]) if anchor["after_text"] else 0
        if before_count == 0:
            errors.append(f"anchor_before_missing:{anchor_id}")
        elif before_count > 1:
            errors.append(f"anchor_before_ambiguous:{anchor_id}")
        if after_count == 0:
            errors.append(f"anchor_after_missing:{anchor_id}")
        elif after_count > 1:
            errors.append(f"anchor_after_ambiguous:{anchor_id}")
    return errors


def _active_negative_guards(
    profile: dict[str, Any],
    scene: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    guards: list[dict[str, Any]] = []
    reviews: list[str] = []
    for card in profile["action_cards"]:
        if card["kind"] != "negative_guard" or card["scene"] not in {"ALL", scene}:
            continue
        if card.get("status") == "AUDIT_ONLY":
            continue
        guards.append({
            "id": card["id"],
            "scene": card["scene"],
            "status": card["status"],
            "detector": card["detector"],
        })
        if card["status"] != "AVAILABLE":
            reviews.append(f"unavailable_negative_guard:{card['id']}")
    return guards, reviews


def _document_format(path: Path) -> str:
    return "tex" if path.suffix.lower() in {".tex", ".ltx"} else "markdown"


def _author_view(text: str, *, document_format: str = "markdown") -> str:
    """Remove spans already protected from style rewriting before template scans."""
    protected = output_validator.lexical.ProtectedIndex(text, document_format=document_format)
    chars = list(text)
    for start, end, _reason in protected.spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _copy_view(text: str, *, document_format: str = "markdown") -> str:
    """Mask protected spans with an offset-preserving hard boundary."""
    protected = output_validator.lexical.ProtectedIndex(text, document_format=document_format)
    chars = list(text)
    _code_items, code_ranges = output_validator.invariants._code_spans(text)
    ranges = [(start, end) for start, end, _reason in protected.spans]
    ranges.extend(code_ranges)
    # A malformed/unclosed fence or code environment is still protected by the
    # lexical scanner only when it has an explicit span; do not infer a broad
    # range here, because that would hide ordinary prose from the copy gate.
    ranges = sorted(set(ranges))
    for start, end in ranges:
        chars[start:end] = [
            char if char in COPY_LINE_BREAKS else COPY_HARD_BOUNDARY
            for char in chars[start:end]
        ]
    return "".join(chars)


def _is_structural_line(line: str) -> bool:
    if line.startswith("\t") or re.match(r" {4,}", line):
        return True
    stripped = line.lstrip(" \t")
    if not stripped:
        return False
    if re.match(r"#{1,6}(?:[ \t]+|$)", stripped):
        return True
    if re.match(r"(?:[-+*]|\d+[.)])[ \t]+", stripped):
        return True
    if stripped.startswith((">", "```", "~~~", "|", "$$", r"\[", r"\]", "\\")):
        return True
    return False


def _is_copy_joiner(char: str) -> bool:
    return (
        char in COPY_JOINERS
        or char in COPY_INVISIBLE_JOINERS
        or (char.isspace() and char not in COPY_LINE_BREAKS)
    )


def _has_han_at_prose_edge(line: str, *, from_end: bool) -> bool:
    chars: Iterable[str] = reversed(line) if from_end else line
    joiners = 0
    for char in chars:
        if "\u3400" <= char <= "\u9fff":
            return True
        if _is_copy_joiner(char) and joiners < MAX_COPY_JOINER_RUN:
            joiners += 1
            continue
        return False
    return False


def _is_soft_physical_line_break(text: str, offset: int) -> bool:
    """Join a single prose wrap, but never a paragraph or structure boundary."""
    if text[offset] != "\n":
        return False
    previous_start = text.rfind("\n", 0, offset) + 1
    next_end = text.find("\n", offset + 1)
    if next_end < 0:
        next_end = len(text)
    previous_line = text[previous_start:offset].removesuffix("\r")
    next_line = text[offset + 1:next_end].removesuffix("\r")
    if not previous_line.strip(" \t") or not next_line.strip(" \t"):
        return False
    if previous_line.endswith("  ") or previous_line.endswith("\\"):
        return False
    if _is_structural_line(previous_line) or _is_structural_line(next_line):
        return False
    return (
        _has_han_at_prose_edge(previous_line, from_end=True)
        and _has_han_at_prose_edge(next_line, from_end=False)
    )


def _han_windows(text: str, width: int) -> Iterable[tuple[str, str, int]]:
    # Treat short punctuation/spacing insertions as transparent so a copied
    # eight-Han run cannot evade the gate by inserting one comma after seven
    # characters. A single prose-only physical wrap is also transparent;
    # paragraphs, structure lines, protected spans, code-like characters, and
    # long separator runs remain hard boundaries.
    han_chars: list[str] = []
    offsets: list[int] = []
    joiner_run = 0
    for offset, char in enumerate(text):
        if "\u3400" <= char <= "\u9fff":
            han_chars.append(char)
            offsets.append(offset)
            joiner_run = 0
            if len(han_chars) >= width:
                phrase = "".join(han_chars[-width:])
                yield phrase, _sha256(phrase), offsets[-width]
            continue
        if char == "\r" and offset + 1 < len(text) and text[offset + 1] == "\n":
            continue
        if char == "\n" and _is_soft_physical_line_break(text, offset):
            joiner_run += 1
            if joiner_run <= MAX_COPY_JOINER_RUN:
                continue
        if _is_copy_joiner(char):
            joiner_run += 1
            if joiner_run <= MAX_COPY_JOINER_RUN:
                continue
        han_chars.clear()
        offsets.clear()
        joiner_run = 0


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_break = text.rfind("\n", 0, offset)
    return line, offset - last_break


def _source_copy_check(
    parsed: dict[str, Any],
    catalog_sources: dict[str, dict[str, Any]],
    catalog_cards: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    after_path = parsed["after_path"]
    before_path = parsed["before_path"]
    width = 8
    normalization = {
        "inline_joiners": "up_to_3_unicode_spaces_zero_width_joiners_or_listed_punctuation",
        "single_prose_physical_line_break": "transparent",
        "paragraph_or_structural_line_break": "hard_boundary",
        "protected_span": "hard_boundary",
        "source_protection_scope": "full_source_before_registered_line_slice",
    }
    empty = {
        "status": "NOT_RUN",
        "window_han_chars": width,
        "normalization": normalization,
        "match_count": 0,
        "introduced_match_count": 0,
        "inherited_match_count": 0,
        "introduced_matches": [],
        "inherited_matches": [],
    }
    if after_path is None or before_path is None:
        return empty
    after_text = _copy_view(
        after_path.read_text(encoding="utf-8-sig"),
        document_format=_document_format(after_path),
    )
    before_text = _copy_view(
        before_path.read_text(encoding="utf-8-sig"),
        document_format=_document_format(before_path),
    )
    before_windows = Counter(phrase for phrase, _phrase_hash, _offset in _han_windows(before_text, width))
    source_windows: dict[str, list[dict[str, Any]]] = {}
    for card in catalog_cards:
        for ref in card["source_refs"]:
            source_id = ref["source_id"]
            source = catalog_sources[source_id]
            try:
                raw = Path(source["path"]).read_bytes()
            except OSError:
                # The action profile already records this source/card as
                # unavailable; do not turn a reviewable candidate into a
                # process crash while attempting the secondary copy check.
                continue
            text, _encoding, issue = action_profile.decode_source(raw)
            if text is None:
                continue
            # Detect protection on the complete source before slicing by the
            # registered line range. Otherwise a range beginning inside a
            # fence/environment loses its opening delimiter and is misread as
            # author prose. _copy_view preserves all splitlines boundaries.
            lines = _copy_view(
                text,
                document_format=_document_format(Path(source["path"])),
            ).splitlines()
            selected = "\n".join(lines[ref["line_start"] - 1:ref["line_end"]])
            for phrase, phrase_hash, _offset in _han_windows(selected, width):
                source_windows.setdefault(phrase, []).append({
                    "source_id": source_id,
                    "line_start": ref["line_start"],
                    "line_end": ref["line_end"],
                    "source_phrase_sha256": phrase_hash,
                })

    introduced: list[dict[str, Any]] = []
    inherited: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int, int]] = set()
    after_occurrences: Counter[str] = Counter()
    for phrase, phrase_hash, offset in _han_windows(after_text, width):
        after_occurrences[phrase] += 1
        line, column = _line_column(after_text, offset)
        for source_ref in source_windows.get(phrase, []):
            key = (phrase_hash, source_ref["source_id"], source_ref["line_start"], source_ref["line_end"], offset)
            if key in seen:
                continue
            seen.add(key)
            record = {
                **source_ref,
                "candidate_phrase_sha256": phrase_hash,
                "han_char_count": width,
                "candidate_line": line,
                "candidate_column": column,
            }
            if after_occurrences[phrase] <= before_windows[phrase]:
                inherited.append(record)
            else:
                introduced.append(record)
    return {
        "status": "REVIEW" if introduced else "PASS",
        "window_han_chars": width,
        "normalization": normalization,
        "match_count": len(introduced) + len(inherited),
        "introduced_match_count": len(introduced),
        "inherited_match_count": len(inherited),
        "introduced_matches": introduced,
        "inherited_matches": inherited,
    }


def _template_check(
    after_path: Path | None,
    negative_guards: Iterable[dict[str, Any]] = (),
    *,
    resolved_scene: str = "GENERAL",
) -> dict[str, Any]:
    if after_path is None:
        return {"status": "NOT_RUN", "codes": [], "negative_guard_hits": []}
    raw_text = after_path.read_text(encoding="utf-8-sig")
    document_format = _document_format(after_path)
    text = _author_view(raw_text, document_format=document_format)
    codes: list[str] = []
    if FUTURE_BRIDGE_RE.search(text):
        codes.append("automatic_future_bridge")
    if len(FORCED_CONTRAST_RE.findall(text)) >= 2:
        codes.append("repeated_forced_contrast")
    # The fixed explanation chain is only a risk once every stage is present;
    # it remains a review signal rather than an assertion about content quality.
    if SURFACE_RE.search(text) and DEEP_RE.search(text) and LIMIT_RE.search(text) and FUTURE_BRIDGE_RE.search(text):
        codes.append("fixed_escalation_limitation_future_chain")
    guard_hits: list[dict[str, Any]] = []
    for guard in negative_guards:
        guard_id = str(guard.get("id", ""))
        detector = guard.get("detector")
        detector_type = (
            str(detector.get("type", ""))
            if isinstance(detector, dict)
            else ""
        )
        try:
            definition_sha256 = _sha256(json.dumps(
                detector,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"))
            definition_hash_status = "PASS"
        except (TypeError, ValueError):
            definition_sha256 = ""
            definition_hash_status = "UNAVAILABLE"
        common = {
            "card_id": guard_id,
            "card_status": guard.get("status", ""),
            "detector_type": detector_type or "UNKNOWN",
            "definition_sha256": definition_sha256,
            "definition_hash_status": definition_hash_status,
        }
        try:
            if not isinstance(detector, dict):
                raise repetition_guards.DetectorEvaluationReview(
                    "negative guard detector must be an object"
                )
            snapshot_text = (
                text if detector_type == "regex_groups/v1" else raw_text
            )
            evidence = repetition_guards.evaluate_detector_snapshot(
                {
                    "unit_id": "CANDIDATE_AFTER",
                    "document_id": "CANDIDATE_AFTER",
                    "resolved_scene": resolved_scene,
                    "format": document_format,
                    "suffix": after_path.suffix.lower(),
                    "heading_path": "",
                    "text": snapshot_text,
                },
                detector,
            )
            _validate_detector_evidence(detector_type, evidence)
            if not evidence["triggered"]:
                continue
            code = f"negative_guard:{guard_id}"
            if code not in codes:
                codes.append(code)
            hit = {
                **common,
                "evaluation_status": "TRIGGERED",
                "evidence": evidence,
            }
            if detector_type == "regex_groups/v1":
                hit["matched_groups"] = [
                    {
                        "id": item["id"],
                        "occurrences": item["occurrences"],
                    }
                    for item in evidence["group_results"]
                    if item["triggered"]
                ]
            elif detector_type == "structured_repeated_list/v1":
                hit["structured_evidence"] = evidence
            guard_hits.append(hit)
        except repetition_guards.DetectorEvaluationReview as error:
            code = f"negative_guard_detector_review:{guard_id}"
            if code not in codes:
                codes.append(code)
            guard_hits.append({
                **common,
                "evaluation_status": "REVIEW",
                "review_code": "DETECTOR_EVALUATION_REVIEW",
                "error_type": type(error).__name__,
                "evidence": {},
            })
            continue
        except Exception as error:
            raise CandidateError(
                "negative_guard_evaluation_runtime_error:"
                f"{guard_id}:{type(error).__name__}"
            ) from error
    return {
        "status": "REVIEW" if codes else "PASS",
        "codes": codes,
        "negative_guard_hits": guard_hits,
    }


def _validate_detector_evidence(detector_type: str, evidence: Any) -> None:
    if not isinstance(evidence, dict) or type(evidence.get("triggered")) is not bool:
        raise InvalidEvidence

    if detector_type == "regex_groups/v1":
        group_results = evidence.get("group_results")
        matched_units = evidence.get("matched_units")
        if not isinstance(group_results, list) or not isinstance(matched_units, list):
            raise InvalidEvidence
        if not all(isinstance(unit, str) for unit in matched_units):
            raise InvalidEvidence
        for group in group_results:
            if not isinstance(group, dict):
                raise InvalidEvidence
            if not isinstance(group.get("id"), str):
                raise InvalidEvidence
            occurrences = group.get("occurrences")
            minimum_occurrences = group.get("minimum_occurrences")
            if type(occurrences) is not int or occurrences < 0:
                raise InvalidEvidence
            if type(minimum_occurrences) is not int or minimum_occurrences < 1:
                raise InvalidEvidence
            units = group.get("units")
            if not isinstance(units, list) or not all(
                isinstance(unit, str) for unit in units
            ):
                raise InvalidEvidence
            if type(group.get("triggered")) is not bool:
                raise InvalidEvidence
        return

    if detector_type == "structured_repeated_list/v1":
        qualified_block_count = evidence.get("qualified_block_count")
        qualified_blocks = evidence.get("qualified_blocks")
        shared_anchors = evidence.get("shared_anchors")
        if type(qualified_block_count) is not int or qualified_block_count < 0:
            raise InvalidEvidence
        if not isinstance(qualified_blocks, list) or not all(
            isinstance(block, dict) for block in qualified_blocks
        ):
            raise InvalidEvidence
        if not isinstance(shared_anchors, list) or not all(
            isinstance(anchor, dict) for anchor in shared_anchors
        ):
            raise InvalidEvidence
        return

    raise InvalidEvidence


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def _existing_queue_results(queue_dir: Path, candidate_id: str) -> list[tuple[str, Path, dict[str, Any]]]:
    found: list[tuple[str, Path, dict[str, Any]]] = []
    for bucket in ("accepted", "review", "rejected"):
        path = queue_dir / bucket / f"{candidate_id}.result.json"
        if not path.is_file():
            continue
        try:
            _raw, _identity = _read_stable_bytes(path, "queue_state")
            payload = json.loads(
                _raw.decode("utf-8-sig"),
                object_pairs_hook=_reject_queue_duplicate_keys,
                parse_constant=_reject_queue_nonfinite,
            )
        except (CandidateError, OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CandidateError(
                f"queue_state_unreadable:{type(error).__name__}"
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("candidate_sha256"), str):
            raise CandidateError("queue_state_invalid")
        found.append((bucket, path, payload))
    return found


def _queue_storage_id(
    parsed: dict[str, Any],
    result: dict[str, Any],
    reviewer_id: str = "",
) -> str:
    candidate_id = parsed["candidate_id"]
    if (
        candidate_id
        and SAFE_ID_RE.fullmatch(candidate_id)
        and (not reviewer_id or reviewer_id not in candidate_id)
        and len(candidate_id) <= 20
    ):
        return candidate_id
    if candidate_id and SAFE_ID_RE.fullmatch(candidate_id):
        return f"{candidate_id[:8]}-{result['candidate_sha256'][:11]}"
    return f"invalid-{result['candidate_sha256'][:20]}"


def _history_hash_key(label: str, value: str) -> str:
    """Keep nested immutable history paths below legacy Windows path limits."""
    return f"{label}-{value[:20]}"


def _stage_raw(stage_dir: Path, relative: Path, raw: bytes) -> Path:
    # Keep staging names short: Windows legacy path limits can otherwise be
    # exceeded by history/<candidate>/<artifact>/runs/<attestation> paths.
    path = stage_dir / "new" / _sha256(relative.as_posix())[:24]
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, raw)
    return path


def _commit_queue_files(
    queue_dir: Path,
    *,
    stage_dir: Path,
    head_files: dict[Path, bytes],
    immutable_files: dict[Path, bytes],
    stale_head_files: Iterable[Path],
    post_publish_check: Callable[[], None] | None = None,
) -> None:
    """Publish one queue head with rollback; all raw bytes are staged first."""
    staged: dict[Path, Path] = {}
    for destination, raw in [*head_files.items(), *immutable_files.items()]:
        if destination in immutable_files and destination.exists():
            try:
                existing_raw = destination.read_bytes()
            except OSError as error:
                raise CandidateError(
                    f"immutable_history_unreadable:{destination.relative_to(queue_dir)}"
                ) from error
            if existing_raw != raw:
                raise CandidateError(
                    f"immutable_history_conflict:{destination.relative_to(queue_dir)}"
                )
            continue
        relative = destination.relative_to(queue_dir)
        staged[destination] = _stage_raw(stage_dir, relative, raw)

    backup_root = stage_dir / "backup"
    backed_up: dict[Path, Path] = {}
    published: list[Path] = []
    mutable_paths = set(head_files) | set(stale_head_files)
    try:
        for old_path in sorted(mutable_paths, key=str):
            if not old_path.exists():
                continue
            backup = backup_root / old_path.relative_to(queue_dir)
            backup.parent.mkdir(parents=True, exist_ok=True)
            old_path.replace(backup)
            backed_up[old_path] = backup

        # Candidate first, result second: a visible result always has its
        # matching package. The previous head has already been moved aside,
        # so accepted/review/rejected can never expose two complete heads.
        for destination in head_files:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged[destination].replace(destination)
            published.append(destination)
        for destination in immutable_files:
            staged_path = staged.get(destination)
            if staged_path is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged_path.replace(destination)
            published.append(destination)
        for destination, expected_raw in immutable_files.items():
            try:
                current_raw = destination.read_bytes()
            except OSError as error:
                raise CandidateError(
                    f"immutable_history_unreadable:{destination.relative_to(queue_dir)}"
                ) from error
            if current_raw != expected_raw:
                raise CandidateError(
                    f"immutable_history_conflict:{destination.relative_to(queue_dir)}"
                )
        if post_publish_check is not None:
            post_publish_check()
    except Exception:
        for destination in reversed(published):
            if destination.exists():
                destination.unlink()
        for original, backup in backed_up.items():
            original.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                backup.replace(original)
        raise


def _reviewer_label_tokens(reviewer_id: str) -> set[bytes]:
    if not reviewer_id:
        return set()
    return {
        reviewer_id.encode("utf-8"),
        json.dumps(reviewer_id, ensure_ascii=True)[1:-1].encode("ascii"),
    }


def _assert_reviewer_absent(raw_values: Iterable[bytes], reviewer_id: str) -> None:
    for raw in raw_values:
        if any(token and token in raw for token in _reviewer_label_tokens(reviewer_id)):
            raise CandidateError("queue_payload_contains_reviewer_label")


def _verify_queue_tree_redaction(queue_dir: Path, reviewer_id: str) -> None:
    if not reviewer_id:
        return
    tokens = _reviewer_label_tokens(reviewer_id)
    for bucket in ("accepted", "review", "rejected", "history"):
        root = queue_dir / bucket
        if not root.exists():
            continue
        for path in root.rglob("*"):
            relative = str(path.relative_to(queue_dir))
            if reviewer_id in relative:
                raise CandidateError("queue_path_contains_reviewer_label")
            if not path.is_file():
                continue
            try:
                raw = path.read_bytes()
            except OSError as error:
                raise CandidateError(f"queue_state_unreadable:{relative}") from error
            if any(token and token in raw for token in tokens):
                raise CandidateError("queue_tree_contains_reviewer_label")


def _queue_result_unlocked(
    candidate_path: Path,
    parsed: dict[str, Any],
    result: dict[str, Any],
    queue_dir: Path,
    artifact_snapshot: dict[str, Any],
    catalog_bundle: dict[str, Any],
    policy_bundle: dict[str, Any],
) -> None:
    bucket = {
        "PASS": "accepted",
        "REVIEW": "review",
        "FAIL": "rejected",
    }[str(result["status"])]
    destination = queue_dir / bucket
    reviewer_id = parsed.get("warning_reviewer_id", "")
    candidate_id = _queue_storage_id(parsed, result, reviewer_id)
    existing = _existing_queue_results(queue_dir, candidate_id)
    if len(existing) > 1:
        raise CandidateError(f"queue_state_conflict:{candidate_id}")
    existing_hashes = {str(payload["candidate_sha256"]) for _old_bucket, _path, payload in existing}
    if len(existing_hashes) > 1:
        raise CandidateError(f"queue_state_conflict:{candidate_id}")
    current_hash = next(iter(existing_hashes), "")
    incoming_hash = str(result["candidate_sha256"])
    supersedes = parsed["supersedes_candidate_sha256"]
    if current_hash and current_hash != incoming_hash and supersedes != current_hash:
        raise CandidateError(f"candidate_id_collision:{candidate_id}")
    if supersedes and current_hash != incoming_hash and supersedes != current_hash:
        raise CandidateError(f"supersedes_candidate_not_current:{candidate_id}")

    history = queue_dir / "history" / candidate_id
    incoming_evaluation = str(result["evaluation_sha256"])
    artifact_history = history / _history_hash_key("a", incoming_hash)
    evaluation_path = (
        artifact_history
        / "evaluations"
        / f"{_history_hash_key('e', incoming_evaluation)}.result.json"
    )
    same_candidate_artifact = current_hash == incoming_hash
    same_evaluation_run = same_candidate_artifact and evaluation_path.exists()
    result["queue"] = {
        "bucket": bucket,
        "storage_id": candidate_id,
        "same_candidate_artifact": same_candidate_artifact,
        "same_evaluation_run": same_evaluation_run,
        "idempotent_rerun": same_evaluation_run,
        "superseded_candidate_sha256": current_hash if current_hash != incoming_hash else "",
    }
    _verify_artifact_snapshot(artifact_snapshot, parsed, candidate_path)
    _verify_catalog_bundle(catalog_bundle)
    _verify_policy_snapshot(policy_bundle)
    _verify_queue_tree_redaction(queue_dir, reviewer_id)
    candidate_raw = artifact_snapshot["sanitized_candidate_raw"]
    stored_result = _redact_reviewer_label(copy.deepcopy(result), reviewer_id)
    result_raw = (json.dumps(stored_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_record = {
        "candidate_sha256": incoming_hash,
        "artifact_hashes": result["artifact_hashes"],
        "stored_candidate_sha256": _sha256(candidate_raw),
        "storage_format": "SANITIZED_CANDIDATE_PACKAGE",
    }
    artifact_record_raw = (
        json.dumps(artifact_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    evaluation_record = _redact_reviewer_label(copy.deepcopy(result), reviewer_id)
    evaluation_record.pop("queue", None)
    evaluation_record_raw = (
        json.dumps(evaluation_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    result["queue"]["stored_candidate_sha256"] = artifact_record["stored_candidate_sha256"]
    # Re-serialize after adding the storage hash to the public queue metadata.
    stored_result = _redact_reviewer_label(copy.deepcopy(result), reviewer_id)
    result_raw = (json.dumps(stored_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _assert_reviewer_absent(
        (candidate_raw, result_raw, artifact_record_raw, evaluation_record_raw), reviewer_id
    )
    other_buckets = [
        queue_dir / name
        for name in ("accepted", "review", "rejected")
        if name != bucket
    ]
    result_attestation_hash = _sha256(result_raw)
    head_files = {
        destination / f"{candidate_id}.json": candidate_raw,
        destination / f"{candidate_id}.result.json": result_raw,
    }
    immutable_files = {
        history / f"{incoming_hash}.json": candidate_raw,
        history / f"{incoming_hash}.result.json": artifact_record_raw,
        evaluation_path: evaluation_record_raw,
        artifact_history
        / "runs"
        / f"{_history_hash_key('r', result_attestation_hash)}.result.json": result_raw,
    }
    stale_head_files = [
        path
        for other in other_buckets
        for path in (
            other / f"{candidate_id}.json",
            other / f"{candidate_id}.result.json",
        )
    ]
    queue_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".candidate-transaction-", dir=queue_dir))

    def post_publish_check() -> None:
        _verify_artifact_snapshot(artifact_snapshot, parsed, candidate_path)
        _verify_catalog_bundle(catalog_bundle)
        _verify_policy_snapshot(policy_bundle)
        _verify_queue_tree_redaction(queue_dir, reviewer_id)

    try:
        _commit_queue_files(
            queue_dir,
            stage_dir=stage_dir,
            head_files=head_files,
            immutable_files=immutable_files,
            stale_head_files=stale_head_files,
            post_publish_check=post_publish_check,
        )
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def _queue_result(
    candidate_path: Path,
    parsed: dict[str, Any],
    result: dict[str, Any],
    queue_dir: Path,
    artifact_snapshot: dict[str, Any],
    catalog_bundle: dict[str, Any],
    policy_bundle: dict[str, Any],
) -> None:
    try:
        with _queue_lock(queue_dir):
            _queue_result_unlocked(
                candidate_path,
                parsed,
                result,
                queue_dir,
                artifact_snapshot,
                catalog_bundle,
                policy_bundle,
            )
    except CandidateError:
        raise
    except (OSError, PermissionError) as error:
        raise CandidateError(f"queue_publish_error:{type(error).__name__}") from error


def _validate_candidate(
    candidate_path: Path,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    queue_dir: Path | None = None,
    allowed_root: Path | None = None,
) -> dict[str, Any]:
    """Validate one candidate and optionally place it in accepted/review/rejected."""
    candidate_path = candidate_path.resolve()
    catalog_path = catalog_path.resolve()
    try:
        catalog_authority = (
            "INSTALLED_DEFAULT"
            if catalog_path == DEFAULT_CATALOG.resolve(strict=True)
            else "EXTERNAL_UNVERIFIED"
        )
    except OSError:
        catalog_authority = "EXTERNAL_UNVERIFIED"
    candidate, candidate_raw = _read_json_snapshot(candidate_path)
    allowed_root = allowed_root.resolve() if allowed_root is not None else None
    root_errors: list[str] = []
    if allowed_root is not None:
        try:
            candidate_path.relative_to(allowed_root)
        except ValueError:
            root_errors.append("candidate_path_outside_allowed_root")
    parsed, contract_errors = _parse_candidate(candidate, candidate_path, allowed_root=allowed_root)
    contract_errors.extend(root_errors)
    artifact_snapshot: dict[str, Any] | None = None
    try:
        artifact_snapshot = _artifact_snapshot(candidate_path, parsed, candidate_raw=candidate_raw)
    except CandidateError as error:
        contract_errors.append(str(error))
    policy_bundle = _policy_snapshot()
    with tempfile.TemporaryDirectory(prefix="humanize-candidate-snapshot-") as frozen_name:
        frozen_root = Path(frozen_name)
        catalog_bundle = _snapshot_catalog_bundle(catalog_path, frozen_root)
        if queue_dir is not None:
            queue_dir = _validate_queue_boundary(
                queue_dir,
                candidate_path=candidate_path,
                parsed=parsed,
                catalog_bundle=catalog_bundle,
            )
        frozen_parsed, restore_paths = (
            _materialize_artifact_snapshot(artifact_snapshot, parsed, frozen_root)
            if artifact_snapshot is not None
            else (dict(parsed), {})
        )
        try:
            profile = action_profile.build_action_profile(
                catalog_bundle["frozen_catalog_path"],
                invalid_negative_guard_as_review=True,
            )
        except Exception as error:
            raise CandidateError(
                f"action_profile_runtime_error:{type(error).__name__}"
            ) from error
        try:
            catalog, catalog_sources = _load_catalog_for_copy(
                catalog_bundle["frozen_catalog_path"]
            )
        except Exception as error:
            raise CandidateError(
                f"catalog_copy_load_runtime_error:{type(error).__name__}"
            ) from error
        _verify_source_profile_state(profile, catalog_sources)

        selected_cards, card_errors, card_reviews, _selected_catalog_cards = _used_card_contract(
            frozen_parsed, profile, catalog
        )
        negative_guards, negative_guard_reviews = _active_negative_guards(profile, frozen_parsed["scene"])
        card_reviews.extend(negative_guard_reviews)
        contract_errors.extend(card_errors)
        contract_errors.extend(_anchor_contract(frozen_parsed))
        artifact_hashes = _candidate_fingerprint(artifact_snapshot) if artifact_snapshot is not None else {
            "candidate_package_sha256": "",
            "before_sha256": "",
            "after_sha256": "",
            "artifact_sha256": "",
        }
        scene_support = profile["summary"]["scene_corpus_support"].get(frozen_parsed["scene"], {})
        if frozen_parsed["corpus_action_support"] == "NONE":
            if scene_support.get("status") == "SUPPORTED":
                contract_errors.extend([
                    f"corpus_action_support_none_not_allowed:{frozen_parsed['scene']}",
                    "corpus_action_support_none_despite_supported_corpus",
                ])
        elif scene_support.get("status") == "CORPUS_INSUFFICIENT":
            card_reviews.append(f"scene_corpus_insufficient:{frozen_parsed['scene']}")
        elif scene_support.get("status") == "SUPPORTED_PROVISIONAL":
            card_reviews.append(f"scene_corpus_origin_unresolved:{frozen_parsed['scene']}")
        if (
            catalog_authority == "EXTERNAL_UNVERIFIED"
            and frozen_parsed["corpus_action_support"] == "ACTION_CARDS"
        ):
            card_reviews.append("external_catalog_not_production_trusted")

        validation: dict[str, Any] = {"status": "NOT_RUN", "exit_code": None}
        if frozen_parsed["before_path"] is not None and frozen_parsed["after_path"] is not None:
            try:
                validation = output_validator.validate(
                    frozen_parsed["before_path"],
                    frozen_parsed["after_path"],
                    scene="AUTO" if frozen_parsed["scene"] == "REPORT" else frozen_parsed["scene"],
                    keep_reasons=frozen_parsed["keep_reasons"],
                    warning_resolutions=frozen_parsed["warning_resolutions"],
                    warning_review_request_sha256=frozen_parsed[
                        "warning_review_request_sha256"
                    ],
                    warning_reviewer_kind=frozen_parsed["warning_reviewer_kind"],
                    warning_reviewer_id=frozen_parsed["warning_reviewer_id"],
                )
                validation = _restore_snapshot_paths(validation, restore_paths)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
                contract_errors.append(f"style_validator_error:{type(error).__name__}")

        # All four gates below consume the exact same frozen before/after and
        # source bytes. Live paths are only rechecked as publication evidence.
        if not contract_errors:
            try:
                source_copy = _source_copy_check(
                    frozen_parsed, catalog_sources, catalog["action_cards"]
                )
            except CandidateError:
                raise
            except Exception as error:
                raise CandidateError(
                    f"source_copy_check_runtime_error:{type(error).__name__}"
                ) from error
            try:
                template = _template_check(
                    frozen_parsed["after_path"],
                    negative_guards,
                    resolved_scene=frozen_parsed["scene"],
                )
            except CandidateError:
                raise
            except Exception as error:
                raise CandidateError(
                    f"template_check_runtime_error:{type(error).__name__}"
                ) from error
        else:
            source_copy = {
                "status": "NOT_RUN",
                "match_count": 0,
                "introduced_match_count": 0,
                "inherited_match_count": 0,
                "introduced_matches": [],
                "inherited_matches": [],
            }
            template = {
                "status": "NOT_RUN",
                "codes": [],
                "negative_guard_hits": [],
            }

        if artifact_snapshot is not None:
            try:
                _verify_artifact_snapshot(artifact_snapshot, parsed, candidate_path)
            except CandidateError as error:
                contract_errors.append(str(error))
        try:
            _verify_catalog_bundle(catalog_bundle)
        except CandidateError as error:
            contract_errors.append(str(error))
        try:
            _verify_policy_snapshot(policy_bundle)
        except CandidateError as error:
            contract_errors.append(str(error))

        review_reasons = list(card_reviews)
        if validation["status"] == "REVIEW":
            review_reasons.append("style_validator_review")
        if source_copy["status"] == "REVIEW":
            review_reasons.append("source_copy_limit")
        if template["status"] == "REVIEW":
            review_reasons.append("negative_template_detected")

        if contract_errors or validation["status"] == "FAIL":
            status, exit_code = "FAIL", 1
        elif review_reasons or validation["status"] != "PASS":
            status, exit_code = "REVIEW", 2
        else:
            status, exit_code = "PASS", 0

        evaluation = _evaluation_fingerprint(
            artifact_hashes,
            catalog_bundle,
            profile,
            policy_bundle["hashes"],
            parsed,
            allowed_root,
            catalog_authority,
        )
        result = {
            "status": status,
            "exit_code": exit_code,
            "accepted": status == "PASS",
            "queue_disposition": {
                "PASS": "ACCEPTED",
                "REVIEW": "PENDING_REVIEW",
                "FAIL": "REJECTED",
            }[status],
            "candidate_id": parsed["candidate_id"],
            "scene": parsed["scene"],
            "corpus_action_support": parsed["corpus_action_support"],
            "candidate_sha256": artifact_hashes["artifact_sha256"],
            "artifact_hashes": artifact_hashes,
            "evaluation_sha256": evaluation["evaluation_sha256"],
            "evaluation_fingerprint": evaluation,
            "allowed_root": str(allowed_root) if allowed_root is not None else None,
            "catalog_authority": catalog_authority,
            "supersedes_candidate_sha256": parsed["supersedes_candidate_sha256"],
            "action_contract": {
                "status": "STRUCTURAL_PASS" if not contract_errors else "FAIL",
                "semantic_requirements": "NOT_EVALUATED",
                "corpus_action_support": parsed["corpus_action_support"],
                "catalog_authority": catalog_authority,
                "scene_corpus_status": scene_support,
                "note": "Action cards constrain organization and provenance. This gate does not verify claims, factual accuracy, citations, calculations, or causal adequacy.",
                "selected_cards": selected_cards,
                "active_negative_guards": negative_guards,
            },
            "contract_errors": contract_errors,
            "review_reasons": review_reasons,
            "anchors": {anchor_id: {"role": value["role"]} for anchor_id, value in parsed["anchors"].items()},
            "style_validation": validation,
            "source_copy_check": source_copy,
            "template_check": template,
            "source_profile_summary": profile["summary"],
        }
        if queue_dir is not None:
            if artifact_snapshot is None:
                raise CandidateError("cannot_publish_without_artifact_snapshot")
            artifact_snapshot["sanitized_candidate_raw"] = _sanitized_candidate_raw(
                candidate, parsed["warning_reviewer_id"]
            )
            _queue_result(
                candidate_path,
                parsed,
                result,
                queue_dir,
                artifact_snapshot,
                catalog_bundle,
                policy_bundle,
            )
        return result


def validate_candidate(
    candidate_path: Path,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    queue_dir: Path | None = None,
    allowed_root: Path | None = None,
) -> dict[str, Any]:
    """Validate one candidate and redact any unexpected internal failure."""
    try:
        return _validate_candidate(
            candidate_path,
            catalog_path=catalog_path,
            queue_dir=queue_dir,
            allowed_root=allowed_root,
        )
    except CandidateError:
        raise
    except Exception as error:
        raise CandidateError(
            f"candidate_validation_runtime_error:{type(error).__name__}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="candidate package JSON")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--queue-dir",
        type=Path,
        help="write candidate/result into accepted, review, or rejected",
    )
    parser.add_argument("--allowed-root", type=Path, help="optional root containing candidate, before, and after files")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        args = build_parser().parse_args(argv)
        result = validate_candidate(
            args.candidate,
            catalog_path=args.catalog,
            queue_dir=args.queue_dir,
            allowed_root=args.allowed_root,
        )
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"{result['status']}: candidate={result['candidate_id'] or 'INVALID'}; "
                f"cards={len(result['action_contract']['selected_cards'])}; "
                f"copy_matches={result['source_copy_check']['match_count']}; "
                f"reviews={','.join(result['review_reasons']) or 'none'}"
            )
    except CandidateError as error:
        print(f"candidate error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(
            f"candidate error: candidate_cli_runtime_error:{type(error).__name__}",
            file=sys.stderr,
        )
        return 1
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
