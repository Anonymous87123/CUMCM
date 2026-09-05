#!/usr/bin/env python3
"""Verify fresh per-unit second-pass evidence and issue a convergence receipt."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402
import prepare_humanize_second_pass as second_pass  # noqa: E402
import run_humanize_generation_trial as runner  # noqa: E402


RECEIPT_SCHEMA = "humanize-second-pass-convergence-receipt/v2"
RUN_RECORD_SCHEMA = "humanize-generation-run-record/v2"


class SecondPassVerificationError(ValueError):
    """Hard evidence mismatch or malformed artifact."""


class SecondPassNotConverged(ValueError):
    """Valid but incomplete or non-converged second pass."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _self_hash(value: dict[str, Any], field: str) -> str:
    payload = dict(value)
    payload.pop(field, None)
    return _sha256(_canonical_json(payload))


def _load_json(path: Path) -> dict[str, Any]:
    value = finalizer._load_json(path)
    if not isinstance(value, dict):
        raise SecondPassVerificationError(f"JSON artifact must be an object: {path}")
    return value


def _load_csv(path: Path) -> list[dict[str, str]]:
    try:
        return finalizer._load_csv(path)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        raise SecondPassVerificationError(f"CSV artifact is malformed: {path}: {error}") from error


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        raise SecondPassVerificationError(f"missing directory: {root}")
    records = [
        {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": _sha256(path.read_bytes()),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file()
    ]
    if not records:
        raise SecondPassVerificationError(f"empty directory: {root}")
    return _sha256(_canonical_json(records))


def _verify_self_hash(value: dict[str, Any], field: str, label: str) -> None:
    stored = value.get(field)
    rebuilt = _self_hash(value, field)
    if stored != rebuilt:
        raise SecondPassVerificationError(f"{label} self-hash mismatch")


def _verify_plan(
    plan: dict[str, Any],
    first_run: Path,
    second_run: Path,
    cases_root: Path,
) -> None:
    try:
        second_pass._verify_plan_for_collection(
            plan,
            second_run=second_run,
            cases_root=cases_root,
        )
    except second_pass.SecondPassPreparationError as error:
        raise SecondPassVerificationError(str(error)) from error
    if Path(str(plan.get("first_run", ""))).resolve() != first_run.resolve():
        raise SecondPassVerificationError("plan first_run binding mismatch")


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SecondPassVerificationError(f"{label} is not a lowercase SHA-256")
    return value


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    missing = [label for label, path in paths.items() if not path.is_file()]
    if missing:
        raise SecondPassNotConverged(
            "missing fresh trial artifacts: " + ",".join(sorted(missing))
        )
    return {label: _sha256(path.read_bytes()) for label, path in paths.items()}


def _verify_collection(
    *,
    plan: dict[str, Any],
    second_run: Path,
    trials_root: Path,
    rewrites_root: Path,
) -> dict[str, Any]:
    collection_path = trials_root / "second-pass-collection.json"
    if not collection_path.is_file():
        raise SecondPassNotConverged("second-pass collection is missing")
    collection = _load_json(collection_path)
    if collection.get("schema_version") != second_pass.COLLECTION_SCHEMA:
        raise SecondPassVerificationError("second-pass collection schema is invalid")
    _verify_self_hash(collection, "collection_sha256", "second-pass collection")
    if collection.get("plan_sha256") != plan.get("plan_sha256"):
        raise SecondPassVerificationError("collection plan binding mismatch")
    expected_paths = {
        "second_run": second_run.resolve(),
        "trials_root": trials_root.resolve(),
        "rewrites_root": rewrites_root.resolve(),
    }
    for field, expected in expected_paths.items():
        if Path(str(collection.get(field, ""))).resolve() != expected:
            raise SecondPassVerificationError(f"collection {field} binding mismatch")
    bundles = collection.get("bundles")
    if not isinstance(bundles, list):
        raise SecondPassVerificationError("collection bundles must be an array")
    return collection


def _safe_case_path(cases_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise SecondPassVerificationError(f"unsafe case path: {relative}")
    path = cases_root.joinpath(*pure.parts).resolve(strict=True)
    try:
        path.relative_to(cases_root.resolve(strict=True))
    except ValueError as error:
        raise SecondPassVerificationError(f"case path escapes root: {relative}") from error
    return path


def _verify_trial(
    *,
    item: dict[str, Any],
    second_run: Path,
    cases_root: Path,
    trials_root: Path,
    rewrites_root: Path,
) -> dict[str, Any]:
    unit_id = str(item.get("unit_id", ""))
    chunk_path = second_run / "chunks" / f"{unit_id}.json"
    chunk = _load_json(chunk_path)
    if _sha256(chunk_path.read_bytes()) != item.get("chunk_file_sha256"):
        raise SecondPassVerificationError(f"plan chunk hash mismatch: {unit_id}")
    case_root = _safe_case_path(cases_root, str(item.get("case_path", "")))
    case = runner.load_public_case(case_root)
    if case.case_id != f"SECOND-{unit_id}":
        raise SecondPassVerificationError(f"case id mismatch: {unit_id}")
    intensity = str(chunk.get("intensity", "")).upper()
    if intensity not in second_pass.preparer.REWRITE_INTENSITIES:
        raise SecondPassVerificationError(f"chunk intensity is invalid: {unit_id}")
    expected_params = {
        "mode": "REWRITE",
        "scene": str(chunk.get("scene", "")),
        "intensity": intensity,
        "output": "PATCH",
        "report_context": "NONE",
    }
    expected_locks = {
        "scope": "section",
        "title_lock": True,
        "structure_lock": intensity != "STRUCTURAL",
    }
    if (
        case.params != expected_params
        or case.locks != expected_locks
        or case.task_options
    ):
        raise SecondPassVerificationError(f"sealed case context mismatch: {unit_id}")
    requested_scene = str(_load_json(second_run / "run_metadata.json").get("scene", "")).upper()
    try:
        generation_profile = second_pass._generation_voice_profile(
            second_run,
            chunk,
            requested_scene,
        )
    except second_pass.SecondPassPreparationError as error:
        raise SecondPassVerificationError(str(error)) from error
    expected_input = second_pass._generation_input_bytes(chunk, generation_profile)
    if (
        case.input_path.read_bytes() != expected_input
        or item.get("case_input_sha256") != _sha256(expected_input)
        or item.get("voice_context_sha256") != _sha256(_canonical_json(generation_profile))
    ):
        raise SecondPassVerificationError(
            f"sealed input does not bind the exact chunk and Voice Profile: {unit_id}"
        )
    if case.prompt_path.read_text(encoding="utf-8-sig") != second_pass.CANONICAL_PROMPT:
        raise SecondPassVerificationError(f"canonical second-pass prompt mismatch: {unit_id}")
    trial = trials_root / unit_id
    receipt_path = trial / "runner-receipt.json"
    record_path = trial / "run-record.json"
    seal_path = trial / "run-seal.json"
    output_path = trial / "response" / "output.txt"
    request_input_path = trial / "request" / case.input_path.name
    public_prompt_path = trial / "request" / "public-prompt.txt"
    public_context_path = trial / "request" / "public-context.json"
    prompt_path = trial / "request" / "prompt.txt"
    context_path = trial / "request" / "context.json"
    invocation_path = trial / "request" / "invocation.json"
    runner_source_path = trial / "request" / "runner-source.py"
    events_path = trial / "transcript" / "events.jsonl"
    stderr_path = trial / "transcript" / "stderr.txt"
    observation_path = trial / "transcript" / "observation.json"
    projection_root = trial / "execution" / "skill"
    projection_manifest_path = trial / "request" / "generator-projection-manifest.json"
    for path in (
        receipt_path,
        record_path,
        seal_path,
        output_path,
        request_input_path,
        public_prompt_path,
        public_context_path,
        prompt_path,
        context_path,
        invocation_path,
        runner_source_path,
        events_path,
        stderr_path,
        observation_path,
        projection_manifest_path,
    ):
        if not path.is_file():
            raise SecondPassNotConverged(f"missing fresh trial artifact for {unit_id}: {path.name}")
    receipt = _load_json(receipt_path)
    record = _load_json(record_path)
    seal = _load_json(seal_path)
    invocation_observation = _load_json(observation_path)
    invocation_request = _load_json(invocation_path)
    if receipt.get("schema_version") != runner.RECEIPT_SCHEMA:
        raise SecondPassVerificationError(f"runner receipt schema mismatch: {unit_id}")
    if receipt.get("runner_status") != "CAPTURED_E2":
        raise SecondPassNotConverged(f"fresh trial is not captured E2: {unit_id}")
    if (
        invocation_request.get("schema_version") != runner.INVOCATION_SCHEMA
        or invocation_request.get("timeout_seconds", 0)
        < runner.QUALIFICATION_MINIMUM_TIMEOUT_SECONDS
        or invocation_request.get("qualification_timing_eligible") is not True
        or invocation_request.get("retry_policy") != "NO_AUTOMATIC_RETRY"
        or invocation_observation.get("schema_version") != runner.OBSERVATION_SCHEMA
        or invocation_observation.get("evidence_attained") != "E2"
        or invocation_observation.get("failure_domain") is not None
        or invocation_observation.get("failure_phase") is not None
        or invocation_observation.get("model_behavior_evaluated") is not False
        or invocation_observation.get("model_output_captured") is not True
        or invocation_observation.get("timed_out") is not False
        or invocation_observation.get("output_present") is not True
        or invocation_observation.get("runner_source_unchanged") is not True
        or _sha256(runner_source_path.read_bytes())
        != receipt.get("runner_executable_sha256")
    ):
        raise SecondPassVerificationError(
            f"runner invocation observation mismatch: {unit_id}"
        )
    if (
        receipt.get("case_id") != case.case_id
        or receipt.get("sandbox") != "read-only"
        or receipt.get("process_identity", {}).get("new_process_observed") is not True
        or receipt.get("exit_status", {}).get("returncode") != 0
        or receipt.get("exit_status", {}).get("timed_out") is not False
    ):
        raise SecondPassVerificationError(f"runner process evidence mismatch: {unit_id}")
    if (
        receipt.get("evidence_cap") != "E2"
        or receipt.get("filesystem_isolation_verified") is not False
        or receipt.get("excluded_roots_unreachable_verified") is not False
        or receipt.get("oracle_catalog_visible_to_generator") is not None
        or receipt.get("public_manifest_sha256") != case.manifest_sha256
        or receipt.get("public_seal_sha256") != case.seal_sha256
        or receipt.get("public_manifest_sha256") != item.get("public_manifest_sha256")
        or receipt.get("public_seal_sha256") != item.get("public_seal_sha256")
    ):
        raise SecondPassVerificationError(f"local runner overclaims filesystem isolation: {unit_id}")
    expected_isolation = {
        "filesystem_isolation_verified": False,
        "host_excluded_roots_unreachable_verified": False,
        "oracle_catalog_present_in_projection": False,
        "oracle_catalog_unreachable_to_generator": "UNVERIFIED",
        "verification_source": "LOCAL_COPY_ONLY",
        "evidence_cap": "E2",
    }
    if receipt.get("isolation") != expected_isolation:
        raise SecondPassVerificationError(f"runner isolation evidence mismatch: {unit_id}")
    if record.get("schema_version") != RUN_RECORD_SCHEMA:
        raise SecondPassVerificationError(f"run record schema mismatch: {unit_id}")
    if record.get("fresh_context") is not True:
        raise SecondPassVerificationError(f"run record does not attest fresh context: {unit_id}")
    if receipt.get("run_id") != record.get("run_id"):
        raise SecondPassVerificationError(f"runner receipt/run record run id mismatch: {unit_id}")
    if record.get("runner_receipt_sha256") != _sha256(receipt_path.read_bytes()):
        raise SecondPassVerificationError(f"run record receipt binding mismatch: {unit_id}")
    if seal.get("schema_version") != runner.RUN_SEAL_SCHEMA:
        raise SecondPassVerificationError(f"run seal schema mismatch: {unit_id}")
    if (
        seal.get("run_id") != record.get("run_id")
        or seal.get("case_id") != case.case_id
        or seal.get("run_record_sha256") != _sha256(record_path.read_bytes())
        or seal.get("runner_receipt_sha256") != _sha256(receipt_path.read_bytes())
    ):
        raise SecondPassVerificationError(f"run seal binding mismatch: {unit_id}")
    receipt_artifacts = _artifact_hashes(
        {
            "input": request_input_path,
            "public_context": public_context_path,
            "prompt": prompt_path,
            "context": context_path,
            "events": events_path,
            "stderr": stderr_path,
            "invocation": invocation_path,
            "invocation_observation": observation_path,
            "runner_source": runner_source_path,
            "output": output_path,
        }
    )
    record_artifacts = {
        key: receipt_artifacts[key] for key in ("input", "output", "prompt", "context")
    }
    public_artifacts = _artifact_hashes(
        {
            "input": request_input_path,
            "prompt": public_prompt_path,
            "public_context": public_context_path,
        }
    )
    if (
        receipt.get("artifact_sha256") != receipt_artifacts
        or record.get("artifact_sha256") != record_artifacts
        or record.get("public_artifact_sha256") != public_artifacts
        or seal.get("artifact_sha256") != record_artifacts
        or seal.get("public_artifact_sha256") != public_artifacts
        or receipt_artifacts["input"] != _sha256(case.input_path.read_bytes())
        or public_artifacts["prompt"] != _sha256(case.prompt_path.read_bytes())
        or public_artifacts["public_context"] != _sha256(case.public_context_path.read_bytes())
    ):
        raise SecondPassVerificationError(f"fresh trial artifact binding mismatch: {unit_id}")
    receipt_projection = receipt.get("generator_projection")
    if not isinstance(receipt_projection, dict):
        raise SecondPassVerificationError(f"runner projection evidence is missing: {unit_id}")
    projection_tree = _require_sha256(
        receipt_projection.get("tree_sha256"),
        f"runner projection tree for {unit_id}",
    )
    projection_manifest = _load_json(projection_manifest_path)
    if receipt_projection.get("manifest_sha256") != _sha256(
        projection_manifest_path.read_bytes()
    ):
        raise SecondPassVerificationError(
            f"generator projection manifest hash mismatch: {unit_id}"
        )
    try:
        projection_builder = runner._load_projection_builder()
        rebuilt_projection = projection_builder.verify_projection(
            projection_root,
            projection_manifest,
            source_root=projection_builder.DEFAULT_SKILL_ROOT,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SecondPassVerificationError(
            f"live generator projection verification failed: {unit_id}: {error}"
        ) from error
    if (
        rebuilt_projection.get("projection_tree_sha256") != projection_tree
        or projection_manifest.get("projection_tree_sha256") != projection_tree
        or projection_manifest.get("projection_policy", {}).get("sha256")
        != receipt_projection.get("policy_sha256")
        or projection_manifest.get("builder", {}).get("executable_sha256")
        != receipt_projection.get("builder_sha256")
        or projection_manifest.get("source", {}).get("inventory_sha256")
        != receipt_projection.get("source_inventory_sha256")
        or projection_manifest.get("source", {}).get("evaluation_surface_sha256")
        != receipt_projection.get("evaluation_surface_sha256")
    ):
        raise SecondPassVerificationError(
            f"live generator projection binding mismatch: {unit_id}"
        )
    if (
        record.get("generator_projection") != receipt_projection
        or seal.get("generator_projection")
        != {
            "manifest_sha256": receipt_projection.get("manifest_sha256"),
            "tree_sha256": projection_tree,
        }
        or receipt_projection.get("projection_audit_status") != "PASS"
        or receipt_projection.get("evaluation_surface_present_in_projection") is not False
        or record.get("qualification_bindings") != receipt.get("qualification_bindings")
    ):
        raise SecondPassVerificationError(f"generator projection evidence mismatch: {unit_id}")
    expected_execution_provenance = {
        "source": "HARNESS_OWNED_LOCAL_RUNNER",
        "process_boundary_observed": True,
        "filesystem_isolation_verified": False,
        "oracle_catalog_present_in_projection": False,
        "oracle_catalog_unreachable_to_generator": "UNVERIFIED",
        "evidence_cap": "E2",
    }
    generator_context = record.get("generator_context")
    if (
        record.get("blindness_attestation") != "CALLER_ATTESTED_STAGED_CONTEXT"
        or record.get("oracle_catalog_visible_to_generator") is not None
        or record.get("filesystem_isolation_verified") is not False
        or record.get("isolation_verification_source") != "LOCAL_COPY_ONLY"
        or record.get("execution_provenance") != expected_execution_provenance
        or not isinstance(generator_context, dict)
        or generator_context.get("complete") is not False
        or generator_context.get("capture_context_generator_visible") is not False
        or generator_context.get("system_messages") != "UNAVAILABLE_FROM_CODEX_EXEC_CLI"
        or generator_context.get("developer_messages") != "UNAVAILABLE_FROM_CODEX_EXEC_CLI"
        or generator_context.get("stdin_prompt_sha256") != receipt_artifacts["prompt"]
        or generator_context.get("capture_context_sha256") != receipt_artifacts["context"]
    ):
        raise SecondPassVerificationError(f"generator context evidence mismatch: {unit_id}")
    staged_case = trial / "execution" / "case"
    expected_staged_case = {
        case.input_path.name: _sha256(case.input_path.read_bytes()),
        "prompt.txt": _sha256(case.prompt_path.read_bytes()),
        "public-context.json": _sha256(case.public_context_path.read_bytes()),
    }
    try:
        staged_case_hashes = runner._verified_staged_case(
            staged_case, expected_staged_case
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise SecondPassVerificationError(
            f"generator staged case verification failed: {unit_id}: {error}"
        ) from error
    if generator_context.get("staged_case_sha256") != staged_case_hashes:
        raise SecondPassVerificationError(f"generator context staged case mismatch: {unit_id}")
    rewrite_path = rewrites_root / f"{unit_id}.json"
    if not rewrite_path.is_file() or rewrite_path.read_bytes() != output_path.read_bytes():
        raise SecondPassVerificationError(f"second-pass rewrite is not exact runner output: {unit_id}")
    output_text = output_path.read_text(encoding="utf-8", errors="strict")
    bundle = finalizer._parse_json_strict(output_text, f"second-pass trial {unit_id}")
    if not isinstance(bundle, dict):
        raise SecondPassVerificationError(f"fresh trial output is not a JSON object: {unit_id}")
    if (
        bundle.get("unit_id") != unit_id
        or bundle.get("chunk_binding_sha256") != chunk.get("chunk_binding_sha256")
        or bundle.get("voice_profile_sha256") != chunk.get("voice_profile_sha256")
    ):
        raise SecondPassVerificationError(f"fresh bundle identity mismatch: {unit_id}")
    return {
        "unit_id": unit_id,
        "decision": str(bundle.get("decision", "")),
        "run_id": record.get("run_id"),
        "runner_receipt_sha256": _sha256(receipt_path.read_bytes()),
        "run_record_sha256": _sha256(record_path.read_bytes()),
        "run_seal_sha256": _sha256(seal_path.read_bytes()),
        "output_sha256": _sha256(output_path.read_bytes()),
        "projection_tree_sha256": projection_tree,
        "fresh_context": True,
        "new_process_observed": True,
        "filesystem_isolation_verified": False,
        "evidence_cap": "E2",
    }


def _verify_second_run_relation(first_run: Path, second_run: Path) -> dict[str, Any]:
    first_finalization = finalizer.load_authoritative_metadata_member(
        first_run, "finalization_metadata.json"
    )
    second_prepare = _load_json(second_run / "run_metadata.json")
    second_finalization = finalizer.load_authoritative_metadata_member(
        second_run, "finalization_metadata.json"
    )
    required_second = {
        "status": "PASS",
        "coverage_completion_claim_allowed": True,
        "scene_routing_status": "PASS",
        "voice_binding_status": "PASS",
        "rewrite_binding_status": "PASS",
        "voice_conformance_status": "PASS",
        "cross_unit_repetition_status": "PASS",
    }
    for key, expected in required_second.items():
        if second_finalization.get(key) != expected:
            raise SecondPassNotConverged(
                f"second pass is incomplete or unresolved: {key}={second_finalization.get(key)!r}"
            )
    if first_finalization.get("voice_binding_sha256") != second_finalization.get(
        "voice_binding_sha256"
    ):
        raise SecondPassVerificationError("Voice binding changed between passes")
    first_prepare = _load_json(first_run / "run_metadata.json")
    if first_prepare.get("scene") != second_prepare.get("scene"):
        raise SecondPassVerificationError("scene changed between passes")
    if (first_run / "scene_routing_policy.json").read_bytes() != (
        second_run / "scene_routing_policy.json"
    ).read_bytes():
        raise SecondPassVerificationError("scene routing policy changed between passes")
    if str(first_prepare.get("scene", "")).upper() == "AUTO":
        if (first_run / "voice_profile_set.json").read_bytes() != (
            second_run / "voice_profile_set.json"
        ).read_bytes():
            raise SecondPassVerificationError("Voice Profile set changed between passes")
        first_profile_files = {
            path.name: path.read_bytes()
            for path in (first_run / "voice_profiles").glob("*.json")
        }
        second_profile_files = {
            path.name: path.read_bytes()
            for path in (second_run / "voice_profiles").glob("*.json")
        }
        if first_profile_files != second_profile_files:
            raise SecondPassVerificationError("scene Voice Profile bytes changed between passes")
    else:
        first_profile = _load_json(first_run / "voice_profile.json")
        second_profile = _load_json(second_run / "voice_profile.json")
        if first_profile != second_profile:
            raise SecondPassVerificationError("Voice Profile bytes changed between passes")

    first_rendered = first_run / "rendered"
    second_rendered = second_run / "rendered"
    first_tree = _tree_hash(first_rendered)
    second_tree = _tree_hash(second_rendered)
    if first_tree != second_tree:
        raise SecondPassNotConverged("second-pass rendered bytes differ from first-pass clean output")

    first_rows = _load_csv(first_run / "rendered_manifest.csv")
    second_source_rows = _load_csv(second_run / "file_manifest.csv")
    expected_sources = {
        str((first_rendered / PurePosixPath(row["rendered_path"])).resolve()): row["sha256"]
        for row in first_rows
    }
    actual_sources = {
        str(Path(row["path"]).resolve()): row["sha256"]
        for row in second_source_rows
        if row.get("sha256")
    }
    if actual_sources != expected_sources:
        raise SecondPassVerificationError(
            "second-pass source snapshot is not the exact first-pass rendered file set"
        )

    initial_units = finalizer._load_jsonl(second_run / "units.jsonl")
    first_units = finalizer._load_jsonl(first_run / "units.jsonl")
    def route_projection(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            (item for item in items if int(item.get("author_chars", 0)) > 0),
            key=lambda item: (str(item.get("file_id", "")), int(item.get("start", 0))),
        )
        projected: list[dict[str, Any]] = []
        for item in ordered:
            route = {
                "file_id": item.get("file_id"),
                "scene": item.get("scene"),
                "scene_document_prior": item.get("scene_document_prior"),
                "scene_routing_decision": item.get("scene_routing_decision"),
                "scene_routing_policy_sha256": item.get("scene_routing_policy_sha256"),
                "voice_profile_binding_scene": item.get("voice_profile_binding_scene"),
                "voice_profile_sha256": item.get("voice_profile_sha256"),
            }
            if not projected or projected[-1] != route:
                projected.append(route)
        return projected
    if route_projection(first_units) != route_projection(initial_units):
        raise SecondPassVerificationError(
            "unit scene routing or Voice binding changed between passes"
        )
    pending_ids = {
        str(unit["unit_id"]) for unit in initial_units if unit.get("status") == "PENDING"
    }
    final_rows = _load_csv(second_run / "coverage_ledger.final.csv")
    final_status = {row["unit_id"]: row["status"] for row in final_rows}
    missing = sorted(pending_ids - set(final_status))
    non_no_change = sorted(
        unit_id for unit_id in pending_ids if final_status.get(unit_id) != "NO_CHANGE"
    )
    if missing or non_no_change:
        raise SecondPassNotConverged(
            f"fresh second pass did not converge to all NO_CHANGE; missing={missing}, non_no_change={non_no_change}"
        )
    return {
        "first_snapshot_id": first_finalization["snapshot_id"],
        "second_snapshot_id": second_finalization["snapshot_id"],
        "first_rendered_tree_sha256": first_tree,
        "second_rendered_tree_sha256": second_tree,
        "second_finalization_metadata_sha256": _sha256(
            _canonical_json(second_finalization)
        ),
        "voice_binding_sha256": first_finalization["voice_binding_sha256"],
        "scene": first_prepare["scene"],
        "pending_unit_ids": sorted(pending_ids),
    }


def verify_second_pass(
    first_run: Path,
    second_run: Path,
    cases_root: Path,
    trials_root: Path,
    rewrites_root: Path,
) -> dict[str, Any]:
    first_run = first_run.resolve(strict=True)
    second_run = second_run.resolve(strict=True)
    cases_root = cases_root.resolve(strict=True)
    trials_root = trials_root.resolve(strict=True)
    rewrites_root = rewrites_root.resolve(strict=True)
    plan = _load_json(cases_root / "second-pass-plan.json")
    _verify_plan(plan, first_run, second_run, cases_root)
    relation = _verify_second_run_relation(first_run, second_run)
    collection = _verify_collection(
        plan=plan,
        second_run=second_run,
        trials_root=trials_root,
        rewrites_root=rewrites_root,
    )
    planned = {str(item["unit_id"]): item for item in plan.get("cases", [])}
    if set(planned) != set(relation["pending_unit_ids"]):
        raise SecondPassVerificationError("plan case inventory differs from second-pass PENDING units")
    trials = [
        _verify_trial(
            item=planned[unit_id],
            second_run=second_run,
            cases_root=cases_root,
            trials_root=trials_root,
            rewrites_root=rewrites_root,
        )
        for unit_id in relation["pending_unit_ids"]
    ]
    non_no_change = [item["unit_id"] for item in trials if item["decision"] != "NO_CHANGE"]
    if non_no_change:
        raise SecondPassNotConverged(
            "fresh trial outputs contain substantive rewrites: " + ",".join(non_no_change)
        )
    projection_trees = sorted({str(item["projection_tree_sha256"]) for item in trials})
    if len(projection_trees) != 1:
        raise SecondPassVerificationError("fresh trials used different generator projections")
    run_ids = [str(item["run_id"]) for item in trials]
    if len(run_ids) != len(set(run_ids)):
        raise SecondPassVerificationError("fresh trials contain a duplicate run id")
    collection_bundles = {
        str(item.get("unit_id", "")): item for item in collection.get("bundles", [])
    }
    if set(collection_bundles) != set(relation["pending_unit_ids"]):
        raise SecondPassVerificationError("collection bundle inventory differs from PENDING units")
    for trial in trials:
        item = collection_bundles[trial["unit_id"]]
        if (
            item.get("decision") != trial["decision"]
            or item.get("output_sha256") != trial["output_sha256"]
        ):
            raise SecondPassVerificationError(
                f"collection output binding mismatch: {trial['unit_id']}"
            )
    evidence_roots = {
        "first_run": str(first_run),
        "second_run": str(second_run),
        "cases_root": str(cases_root),
        "trials_root": str(trials_root),
        "rewrites_root": str(rewrites_root),
    }
    evidence_artifacts = {
        "plan_sha256": _sha256((cases_root / "second-pass-plan.json").read_bytes()),
        "collection_sha256": _sha256(
            (trials_root / "second-pass-collection.json").read_bytes()
        ),
        "cases_tree_sha256": _tree_hash(cases_root),
        "trials_tree_sha256": _tree_hash(trials_root),
        "rewrites_tree_sha256": _tree_hash(rewrites_root),
    }
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "PASS",
        "first_run_snapshot_id": relation["first_snapshot_id"],
        "second_run_snapshot_id": relation["second_snapshot_id"],
        "first_rendered_manifest_sha256": _sha256(
            (first_run / "rendered_manifest.csv").read_bytes()
        ),
        "first_rendered_tree_sha256": relation["first_rendered_tree_sha256"],
        "second_rendered_tree_sha256": relation["second_rendered_tree_sha256"],
        "second_prepare_integrity_sha256": _sha256(
            (second_run / "prepare_integrity.json").read_bytes()
        ),
        "second_finalization_metadata_sha256": relation[
            "second_finalization_metadata_sha256"
        ],
        "voice_binding_sha256": relation["voice_binding_sha256"],
        "scene": relation["scene"],
        "units_total": len(trials),
        "all_units_no_change": True,
        "second_output_equals_first": True,
        "generator_projection_tree_sha256": projection_trees[0],
        "evidence_roots": evidence_roots,
        "evidence_artifacts": evidence_artifacts,
        "fresh_processes": trials,
        "evidence_cap": "E2",
        "claims": {
            "fresh_process_per_unit_observed": True,
            "expected_outcome_exposed": False,
            "filesystem_isolation_verified": False,
            "oracle_unreachable_verified": False,
            "human_identity_verified": False,
            "academic_correctness": "NOT_EVALUATED",
        },
    }
    receipt["receipt_sha256"] = _self_hash(receipt, "receipt_sha256")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-run", type=Path, required=True)
    parser.add_argument("--second-run", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--rewrites", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = verify_second_pass(
            args.first_run,
            args.second_run,
            args.cases,
            args.trials,
            args.rewrites,
        )
    except SecondPassNotConverged as error:
        result = {"status": "REVIEW", "error": str(error), "exit_code": 2}
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"REVIEW: {error}")
        return 2
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        result = {"status": "FAIL", "error": str(error), "exit_code": 1}
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "PASS",
        "exit_code": 0,
        "receipt_sha256": receipt["receipt_sha256"],
        "units": receipt["units_total"],
        "output": str(args.output),
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"PASS units={result['units']} receipt_sha256={result['receipt_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
