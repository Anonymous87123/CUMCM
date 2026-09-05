#!/usr/bin/env python3
"""Prepare sealed fresh-review cases and collect their exact rewrite bundles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402
import prepare_humanize_long_document as preparer  # noqa: E402
import seal_humanize_public_fixture as sealer  # noqa: E402


PLAN_SCHEMA = "humanize-second-pass-plan/v4"
COLLECTION_SCHEMA = "humanize-second-pass-collection/v1"
GENERATION_INPUT_SCHEMA = "humanize-second-pass-generation-input/v1"
CANONICAL_PROMPT = """Use $humanize-academic-chinese to perform a fresh second-pass review of the single masked long-document chunk in input.txt.

The input is a strict JSON object with `chunk` and `voice_profile`. Treat this as a new review from the current chunk, its read-only context, its bound Voice Profile, and the installed generator projection only. Apply the supplied Voice Profile to the review; it contains abstract features, not author sample prose. Do not look for or reuse any first-pass rewrite, diff, validation result, expected answer, or convergence decision.

Return exactly one strict JSON object and no code fence or commentary. Echo unit_id, chunk_binding_sha256, and voice_profile_sha256 exactly from the chunk. If a substantive style change is still necessary, return decision=REWRITE with the complete masked_text and keep_reasons. If no substantive change is necessary, return decision=NO_CHANGE with a concrete Chinese reason of at least four Chinese characters and keep_reasons. Never remove, duplicate, rename, reorder, or edit a [[PROTECTED:...]] placeholder.

Obey the chunk's frozen intensity. A STRUCTURAL REWRITE must also return structural_plan using the schema and source paragraph inventory embedded in the chunk; LIGHT or BALANCED output must not include structural_plan. Do not move locked paragraphs or cross the current unit boundary.
"""


class SecondPassPreparationError(ValueError):
    """Raised when a first-pass result cannot seed a fresh second pass."""


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


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = finalizer._load_json(path)
    if not isinstance(value, dict):
        raise SecondPassPreparationError(f"JSON artifact must be an object: {path}")
    return value


def _load_csv(path: Path) -> list[dict[str, str]]:
    try:
        return finalizer._load_csv(path)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        raise SecondPassPreparationError(f"CSV artifact is malformed: {path}: {error}") from error


def _generation_voice_profile(
    run_dir: Path,
    chunk: dict[str, Any],
    requested_scene: str,
) -> dict[str, Any]:
    scene = str(chunk.get("scene", "")).upper()
    profile_path = (
        run_dir / "voice_profiles" / f"{scene.lower()}.json"
        if requested_scene == "AUTO"
        else run_dir / "voice_profile.json"
    )
    try:
        profile = preparer.voice_profiles.load_and_validate_profile(profile_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SecondPassPreparationError(
            f"second-pass Voice Profile is invalid for {chunk.get('unit_id', '')}: {error}"
        ) from error
    claims = profile.get("claims")
    if (
        profile.get("validation_status") != "PASS"
        or str(profile.get("binding_scene", "")).upper() != scene
        or profile.get("profile_sha256") != chunk.get("voice_profile_sha256")
        or not isinstance(claims, dict)
        or claims.get("identity_verified") is not False
        or claims.get("sample_text_embedded") is not False
    ):
        raise SecondPassPreparationError(
            f"second-pass Voice Profile binding or trust claims are invalid: {chunk.get('unit_id', '')}"
        )
    return profile


def _generation_input_bytes(
    chunk: dict[str, Any],
    profile: dict[str, Any],
) -> bytes:
    return _canonical_json(
        {
            "schema_version": GENERATION_INPUT_SCHEMA,
            "chunk": chunk,
            "voice_profile": profile,
        }
    ) + b"\n"


def _safe_rendered_path(rendered_root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise SecondPassPreparationError(f"unsafe rendered path: {relative}")
    candidate = rendered_root.joinpath(*pure.parts).resolve(strict=True)
    try:
        candidate.relative_to(rendered_root.resolve(strict=True))
    except ValueError as error:
        raise SecondPassPreparationError(f"rendered path escapes root: {relative}") from error
    if not candidate.is_file():
        raise SecondPassPreparationError(f"rendered path is not a file: {relative}")
    return candidate


def _safe_snapshot_path(first_run: Path, relative: str) -> Path:
    pure = PurePosixPath(relative.replace("\\", "/"))
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.parts[0] != "source"
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise SecondPassPreparationError(f"unsafe source snapshot path: {relative}")
    candidate = first_run.joinpath(*pure.parts).resolve(strict=True)
    try:
        candidate.relative_to(first_run.resolve(strict=True))
    except ValueError as error:
        raise SecondPassPreparationError(
            f"source snapshot path escapes first run: {relative}"
        ) from error
    if not candidate.is_file():
        raise SecondPassPreparationError(
            f"source snapshot path is not a file: {relative}"
        )
    return candidate


def _first_pass_inputs(first_run: Path) -> tuple[list[Path], list[dict[str, str]], dict[str, Any]]:
    first_run = first_run.resolve(strict=True)
    try:
        finalizer._verify_prepare_integrity(first_run)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise SecondPassPreparationError(
            f"first pass prepare integrity is invalid: {error}"
        ) from error
    metadata = finalizer.load_authoritative_metadata_member(
        first_run, "finalization_metadata.json"
    )
    required_pass = {
        "status": "PASS",
        "coverage_completion_claim_allowed": True,
        "scene_routing_status": "PASS",
        "voice_binding_status": "PASS",
        "rewrite_binding_status": "PASS",
        "voice_conformance_status": "PASS",
        "cross_unit_repetition_status": "PASS",
    }
    for key, expected in required_pass.items():
        if metadata.get(key) != expected:
            raise SecondPassPreparationError(
                f"first pass is not eligible for fresh convergence: {key}={metadata.get(key)!r}"
            )
    if metadata.get("source_files_modified_by_tool") not in {0, None}:
        raise SecondPassPreparationError("first pass reports source modification by the tool")
    rendered_root = first_run / "rendered"
    if not rendered_root.is_dir() or (first_run / "rendered_partial").exists():
        raise SecondPassPreparationError("first pass must publish only a complete rendered directory")
    rows = _load_csv(first_run / "rendered_manifest.csv")
    if not rows:
        raise SecondPassPreparationError("first rendered manifest is empty")
    expected_fields = {
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
    }
    if any(set(row) != expected_fields for row in rows):
        raise SecondPassPreparationError("first rendered manifest fields are invalid")
    rendered_paths = [row["rendered_path"] for row in rows]
    file_ids = [row["file_id"] for row in rows]
    if len(rendered_paths) != len(set(rendered_paths)) or len(file_ids) != len(set(file_ids)):
        raise SecondPassPreparationError("first rendered manifest contains duplicate identities")
    actual_paths = {
        path.relative_to(rendered_root).as_posix()
        for path in rendered_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != set(rendered_paths):
        raise SecondPassPreparationError(
            "first rendered tree does not equal its manifest file inventory"
        )
    first_file_manifest = _load_csv(first_run / "file_manifest.csv")
    seed_file_ids = {
        row.get("file_id", "")
        for row in first_file_manifest
        if row.get("relation") == "seed" and row.get("status") == "READY"
    }
    if not seed_file_ids:
        raise SecondPassPreparationError("first pass has no readable seed files")
    inputs: list[Path] = []
    for row in rows:
        if row.get("source_path_scope") != "LIVE_LOCATION_LABEL_NOT_HASH_TARGET":
            raise SecondPassPreparationError(
                "first rendered manifest source path scope is invalid"
            )
        if row.get("sha256_scope") != "RENDERED_CANDIDATE_BYTES":
            raise SecondPassPreparationError(
                "first rendered manifest rendered hash scope is invalid"
            )
        snapshot_sha = row.get("source_snapshot_sha256", "")
        rendered_sha = row.get("rendered_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_sha):
            raise SecondPassPreparationError(
                "first rendered manifest source snapshot hash is invalid"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", rendered_sha):
            raise SecondPassPreparationError(
                "first rendered manifest rendered hash is invalid"
            )
        if row.get("sha256") != rendered_sha:
            raise SecondPassPreparationError(
                "first rendered manifest rendered hash aliases disagree"
            )
        snapshot_path = _safe_snapshot_path(
            first_run, row.get("source_snapshot_copy", "")
        )
        if _sha256(snapshot_path.read_bytes()) != snapshot_sha:
            raise SecondPassPreparationError(
                "first rendered source snapshot does not match manifest"
            )
        path = _safe_rendered_path(rendered_root, row.get("rendered_path", ""))
        raw = path.read_bytes()
        if _sha256(raw) != rendered_sha or len(raw) != int(row.get("bytes", -1)):
            raise SecondPassPreparationError(
                f"first rendered artifact does not match manifest: {row.get('rendered_path', '')}"
            )
        if row.get("file_id") in seed_file_ids:
            inputs.append(path)
    if len(inputs) != len(seed_file_ids):
        raise SecondPassPreparationError(
            "first rendered manifest does not contain every readable seed file"
        )
    return inputs, rows, metadata


def _verify_plan_for_collection(
    plan: dict[str, Any],
    *,
    second_run: Path,
    cases_root: Path,
) -> None:
    expected_fields = {
        "schema_version",
        "first_run",
        "second_run",
        "first_snapshot_id",
        "second_snapshot_id",
        "first_rendered_manifest_sha256",
        "first_rendered_files",
        "voice_binding_sha256",
        "scene",
        "intensity",
        "canonical_prompt_sha256",
        "cases",
        "trial_command",
        "claims",
        "plan_sha256",
    }
    if set(plan) != expected_fields or plan.get("schema_version") != PLAN_SCHEMA:
        raise SecondPassPreparationError("second-pass plan fields or schema are invalid")
    unsigned = dict(plan)
    stored_hash = unsigned.pop("plan_sha256", None)
    if stored_hash != _sha256(_canonical_json(unsigned)):
        raise SecondPassPreparationError("second-pass plan self-hash mismatch")
    if Path(str(plan.get("second_run", ""))).resolve() != second_run.resolve():
        raise SecondPassPreparationError("second-pass plan run binding mismatch")
    intensity = str(plan.get("intensity", "")).upper()
    if intensity not in preparer.REWRITE_INTENSITIES:
        raise SecondPassPreparationError("second-pass plan intensity is invalid")
    second_metadata = _load_json(second_run / "run_metadata.json")
    if intensity != str(second_metadata.get("intensity", "")).upper():
        raise SecondPassPreparationError("second-pass plan intensity binding mismatch")
    expected_claims = {
        "expected_outcome_exposed": False,
        "fresh_process_not_yet_run": True,
        "filesystem_isolation_verified": False,
        "evidence_cap": "E0",
    }
    if plan.get("claims") != expected_claims:
        raise SecondPassPreparationError(
            "second-pass plan expected outcome or trust claims are invalid"
        )
    prompt_path = cases_root / "canonical-prompt.txt"
    if (
        not prompt_path.is_file()
        or prompt_path.read_text(encoding="utf-8-sig") != CANONICAL_PROMPT
        or plan.get("canonical_prompt_sha256") != _sha256(prompt_path.read_bytes())
    ):
        raise SecondPassPreparationError("second-pass canonical prompt binding mismatch")
    cases = plan.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SecondPassPreparationError("second-pass plan case inventory is empty")
    unit_ids: set[str] = set()
    expected_case_fields = {
        "unit_id",
        "chunk_binding_sha256",
        "voice_profile_sha256",
        "chunk_file_sha256",
        "case_input_sha256",
        "voice_context_sha256",
        "case_path",
        "public_manifest_sha256",
        "public_seal_sha256",
    }
    for item in cases:
        if not isinstance(item, dict) or set(item) != expected_case_fields:
            raise SecondPassPreparationError("second-pass plan case fields are invalid")
        unit_id = item.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in unit_ids:
            raise SecondPassPreparationError("second-pass plan repeats or omits a unit id")
        unit_ids.add(unit_id)


def prepare_second_pass(
    first_run: Path,
    second_run: Path,
    cases_root: Path,
    *,
    voice_allowed_root: Path | None = None,
) -> dict[str, Any]:
    first_run = first_run.resolve(strict=True)
    second_run = second_run.resolve(strict=False)
    cases_root = cases_root.resolve(strict=False)
    if second_run.exists() or cases_root.exists():
        raise SecondPassPreparationError("second run and cases directories must not already exist")
    inputs, rendered_rows, first_finalization = _first_pass_inputs(first_run)
    first_prepare = _load_json(first_run / "run_metadata.json")
    binding = first_prepare.get("voice_binding")
    budgets = first_prepare.get("budgets")
    if not isinstance(binding, dict) or not isinstance(budgets, dict):
        raise SecondPassPreparationError("first run lacks Voice binding or chunk budgets")
    requested_scene = str(first_prepare.get("scene", "")).upper()
    requested_intensity = str(first_prepare.get("intensity", "")).upper()
    if requested_intensity not in preparer.REWRITE_INTENSITIES:
        raise SecondPassPreparationError("first run lacks a valid rewrite intensity")
    binding_identity = str(first_finalization.get("voice_binding_sha256", ""))
    if not binding_identity or len(binding_identity) != 64:
        raise SecondPassPreparationError("first pass lacks a valid Voice binding identity")
    prepare_options: dict[str, Any] = {
        "scene": requested_scene,
        "intensity": requested_intensity,
        "max_author_chars": int(budgets["max_author_chars"]),
        "max_lines": int(budgets["max_lines"]),
        "min_author_chars": int(budgets["min_author_chars"]),
        "editable_style_wrappers": first_prepare.get("editable_style_wrappers", []),
    }
    evidence_status = str(binding.get("voice_evidence_status", ""))
    if requested_scene == "AUTO":
        if (
            binding.get("mode") != "PROFILE_SET"
            or evidence_status != "DETERMINISTIC_DEFAULT_SET"
            or binding.get("profile_set_sha256") != binding_identity
        ):
            raise SecondPassPreparationError("first AUTO run lacks a valid Profile set binding")
    else:
        profile_path = first_run / "voice_profile.json"
        profile = _load_json(profile_path)
        profile_hash = str(profile.get("profile_sha256", ""))
        if profile_hash != binding_identity:
            raise SecondPassPreparationError("first single Profile identity mismatch")
        prepare_options.update(
            {
                "voice_profile": profile_path,
                "voice_profile_sha256": profile_hash,
            }
        )
    if evidence_status in {"REBUILT_PASS", "REBUILT_DEFAULT_PASS"}:
        if voice_allowed_root is None:
            raise SecondPassPreparationError(
                "evidence-bound Voice Profile requires --voice-allowed-root for second-pass rebuild"
            )
        prepare_options.update(
            {
                "voice_manifest": first_run / "voice_sample_manifest.json",
                "voice_sample_spec": first_run / "voice_sample_spec.json",
                "voice_allowed_root": voice_allowed_root,
            }
        )
    elif evidence_status not in {"DETERMINISTIC_DEFAULT", "DETERMINISTIC_DEFAULT_SET"}:
        raise SecondPassPreparationError(f"unsupported Voice evidence status: {evidence_status}")

    second_metadata = preparer.prepare(inputs, second_run, **prepare_options)
    if second_metadata.get("status") != "READY":
        raise SecondPassPreparationError("second pass prepare did not produce a READY run")
    second_binding = second_metadata.get("voice_binding", {})
    second_identity = (
        second_binding.get("profile_set_sha256")
        if requested_scene == "AUTO"
        else second_binding.get("voice_profile_sha256")
    )
    if second_identity != binding_identity:
        raise SecondPassPreparationError("second pass changed the Voice Profile identity")
    if second_metadata.get("scene_routing_policy_sha256") != first_prepare.get(
        "scene_routing_policy_sha256"
    ):
        raise SecondPassPreparationError("second pass changed the scene routing policy")

    cases_root.mkdir(parents=True)
    prompt_path = cases_root / "canonical-prompt.txt"
    prompt_path.write_text(CANONICAL_PROMPT, encoding="utf-8", newline="\n")
    chunks = [
        _load_json(path)
        for path in sorted((second_run / "chunks").glob("*.json"), key=lambda item: item.name)
    ]
    pending = [chunk for chunk in chunks if chunk.get("status") == "PENDING"]
    if not pending:
        raise SecondPassPreparationError("second pass has no editable PENDING chunks")
    cases: list[dict[str, Any]] = []
    input_dir = cases_root / "inputs"
    input_dir.mkdir()
    sealed_dir = cases_root / "sealed"
    sealed_dir.mkdir()
    for chunk in pending:
        unit_id = str(chunk["unit_id"])
        source_chunk = second_run / "chunks" / f"{unit_id}.json"
        generation_profile = _generation_voice_profile(
            second_run,
            chunk,
            requested_scene,
        )
        generation_input = _generation_input_bytes(chunk, generation_profile)
        input_path = input_dir / f"{unit_id}.txt"
        input_path.write_bytes(generation_input)
        case_root = sealed_dir / unit_id
        result = sealer.seal_fixture(
            input_path,
            prompt_path,
            case_root,
            case_id=f"SECOND-{unit_id}",
            mode="REWRITE",
            scene=str(chunk["scene"]),
            intensity=requested_intensity,
            output_format="PATCH",
            report_context="NONE",
            scope="section",
            title_lock=True,
            structure_lock=requested_intensity != "STRUCTURAL",
        )
        cases.append(
            {
                "unit_id": unit_id,
                "chunk_binding_sha256": chunk["chunk_binding_sha256"],
                "voice_profile_sha256": chunk["voice_profile_sha256"],
                "chunk_file_sha256": _sha256(source_chunk.read_bytes()),
                "case_input_sha256": _sha256(generation_input),
                "voice_context_sha256": _sha256(_canonical_json(generation_profile)),
                "case_path": str(case_root.relative_to(cases_root)).replace("\\", "/"),
                "public_manifest_sha256": result["public_manifest_sha256"],
                "public_seal_sha256": result["public_seal_sha256"],
            }
        )
    plan = {
        "schema_version": PLAN_SCHEMA,
        "first_run": str(first_run),
        "second_run": str(second_run),
        "first_snapshot_id": first_finalization["snapshot_id"],
        "second_snapshot_id": second_metadata["snapshot_id"],
        "first_rendered_manifest_sha256": _sha256(
            (first_run / "rendered_manifest.csv").read_bytes()
        ),
        "first_rendered_files": len(rendered_rows),
        "voice_binding_sha256": binding_identity,
        "scene": first_prepare["scene"],
        "intensity": requested_intensity,
        "canonical_prompt_sha256": _sha256(prompt_path.read_bytes()),
        "cases": cases,
        "trial_command": (
            "python scripts/run_humanize_generation_trial.py "
            "<cases-root>/sealed/<unit-id> --output <trials-root>/<unit-id> --format json"
        ),
        "claims": {
            "expected_outcome_exposed": False,
            "fresh_process_not_yet_run": True,
            "filesystem_isolation_verified": False,
            "evidence_cap": "E0",
        },
    }
    plan["plan_sha256"] = _sha256(_canonical_json(plan))
    _write_json(cases_root / "second-pass-plan.json", plan)
    return plan


def collect_trial_outputs(
    second_run: Path,
    cases_root: Path,
    trials_root: Path,
    rewrites_root: Path,
) -> dict[str, Any]:
    second_run = second_run.resolve(strict=True)
    cases_root = cases_root.resolve(strict=True)
    trials_root = trials_root.resolve(strict=True)
    rewrites_root = rewrites_root.resolve(strict=False)
    if rewrites_root.exists() and any(rewrites_root.iterdir()):
        raise SecondPassPreparationError("rewrites output must be new or empty")
    rewrites_root.mkdir(parents=True, exist_ok=True)
    plan = _load_json(cases_root / "second-pass-plan.json")
    _verify_plan_for_collection(
        plan,
        second_run=second_run,
        cases_root=cases_root,
    )
    copied: list[dict[str, Any]] = []
    for item in plan.get("cases", []):
        unit_id = str(item["unit_id"])
        chunk = _load_json(second_run / "chunks" / f"{unit_id}.json")
        output_path = trials_root / unit_id / "response" / "output.txt"
        if not output_path.is_file():
            raise SecondPassPreparationError(f"missing trial output for {unit_id}")
        raw = output_path.read_bytes()
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise SecondPassPreparationError(f"trial output is not UTF-8: {unit_id}") from error
        bundle = finalizer._parse_json_strict(text, f"trial output {unit_id}")
        if not isinstance(bundle, dict):
            raise SecondPassPreparationError(f"trial output is not a JSON object: {unit_id}")
        if bundle.get("decision") not in {"REWRITE", "NO_CHANGE"}:
            raise SecondPassPreparationError(f"trial decision is invalid: {unit_id}")
        if (
            bundle.get("unit_id") != unit_id
            or bundle.get("chunk_binding_sha256") != chunk.get("chunk_binding_sha256")
            or bundle.get("voice_profile_sha256") != chunk.get("voice_profile_sha256")
        ):
            raise SecondPassPreparationError(f"trial bundle binding mismatch: {unit_id}")
        destination = rewrites_root / f"{unit_id}.json"
        destination.write_bytes(raw)
        copied.append(
            {
                "unit_id": unit_id,
                "decision": bundle["decision"],
                "output_sha256": _sha256(raw),
                "rewrite_path": str(destination),
            }
        )
    collection = {
        "schema_version": COLLECTION_SCHEMA,
        "plan_sha256": plan.get("plan_sha256"),
        "second_run": str(second_run),
        "trials_root": str(trials_root),
        "rewrites_root": str(rewrites_root),
        "bundles": copied,
    }
    collection["collection_sha256"] = _sha256(_canonical_json(collection))
    _write_json(trials_root / "second-pass-collection.json", collection)
    return collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--first-run", type=Path, required=True)
    prepare_parser.add_argument("--second-run", type=Path, required=True)
    prepare_parser.add_argument("--cases", type=Path, required=True)
    prepare_parser.add_argument("--voice-allowed-root", type=Path)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--second-run", type=Path, required=True)
    collect_parser.add_argument("--cases", type=Path, required=True)
    collect_parser.add_argument("--trials", type=Path, required=True)
    collect_parser.add_argument("--rewrites", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_second_pass(
                args.first_run,
                args.second_run,
                args.cases,
                voice_allowed_root=args.voice_allowed_root,
            )
            summary = {
                "status": "READY",
                "cases": len(result["cases"]),
                "plan_sha256": result["plan_sha256"],
            }
        else:
            result = collect_trial_outputs(
                args.second_run,
                args.cases,
                args.trials,
                args.rewrites,
            )
            summary = {
                "status": "COLLECTED",
                "bundles": len(result["bundles"]),
                "collection_sha256": result["collection_sha256"],
            }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        summary = {"status": "FAIL", "error": str(error)}
        if args.format == "json":
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        else:
            print(f"FAIL: {error}")
        return 1
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(" ".join(f"{key}={value}" for key, value in summary.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
