#!/usr/bin/env python3
"""Build a sealed public generation fixture from input and prompt snapshots."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "run_humanize_generation_trial.py"


class SealError(ValueError):
    """Raised when a public fixture cannot be sealed safely."""


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "humanize_generation_trial_runner_for_sealer", RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise SealError("cannot load generation trial runner contracts")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_utf8_snapshot(path: Path, label: str) -> bytes:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise SealError(f"{label} must be a file")
    raw = resolved.read_bytes()
    if not raw:
        raise SealError(f"{label} must not be empty")
    try:
        raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise SealError(f"{label} is not UTF-8: {error}") from error
    return raw


def seal_fixture(
    input_path: Path,
    prompt_path: Path,
    output_root: Path,
    *,
    case_id: str,
    mode: str,
    scene: str,
    intensity: str,
    output_format: str,
    report_context: str,
    scope: str,
    title_lock: bool,
    structure_lock: bool,
    operation: str | None = None,
    locked_literals: Sequence[str] = (),
    summary_max_sentences: int | None = None,
    required_output_format: str | None = None,
    preserve_three_groups: bool = False,
    vary_paragraph_rhythm_without_forced_asymmetry: bool = False,
    preserve_numbers_math: bool = False,
) -> dict[str, Any]:
    runner = _load_runner()
    if not runner.SAFE_ID_RE.fullmatch(case_id):
        raise SealError("case_id is unsafe")
    input_source = input_path.resolve(strict=True)
    if input_source.suffix.lower() not in runner.ALLOWED_INPUT_SUFFIXES:
        raise SealError("input must be .md, .tex, or .txt")
    input_raw = _read_utf8_snapshot(input_source, "input")
    prompt_raw = _read_utf8_snapshot(prompt_path, "prompt")
    try:
        runner._public_leak_check(case_id, [input_source, prompt_path.resolve(strict=True)])
    except runner.RunnerError as error:
        raise SealError(str(error)) from error

    output = output_root.resolve(strict=False)
    if output.exists():
        raise SealError("output directory must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    published = False
    try:
        staged_input = staging / f"input{input_source.suffix.lower()}"
        staged_prompt = staging / "prompt.txt"
        staged_input.write_bytes(input_raw)
        staged_prompt.write_bytes(prompt_raw)
        task_options: dict[str, Any] = {}
        if operation is not None:
            task_options["operation"] = operation
        if locked_literals:
            task_options["locked_literals"] = list(locked_literals)
        if summary_max_sentences is not None:
            task_options["summary_max_sentences"] = summary_max_sentences
        if required_output_format is not None:
            task_options["required_output_format"] = required_output_format
        if preserve_three_groups:
            task_options["preserve_three_groups"] = True
        if vary_paragraph_rhythm_without_forced_asymmetry:
            task_options["vary_paragraph_rhythm_without_forced_asymmetry"] = True
        if preserve_numbers_math:
            task_options["preserve_numbers_math"] = True
        public_context = {
            "schema_version": runner.PUBLIC_CONTEXT_SCHEMA,
            "mode": mode,
            "scene": scene,
            "intensity": intensity,
            "output": output_format,
            "report_context": report_context,
            "scope": scope,
            "title_lock": title_lock,
            "structure_lock": structure_lock,
            "task_options": task_options,
        }
        public_context_path = staging / "public-context.json"
        public_context_path.write_bytes(runner._canonical_json(public_context) + b"\n")
        manifest = {
            "schema_version": runner.PUBLIC_SCHEMA,
            "case_id": case_id,
            "input": {
                "path": staged_input.name,
                "sha256": runner._sha256(input_raw),
            },
            "prompt": {
                "path": staged_prompt.name,
                "sha256": runner._sha256(prompt_raw),
            },
            "public_context": {
                "path": public_context_path.name,
                "sha256": runner._file_sha256(public_context_path),
            },
        }
        manifest_path = staging / "public-manifest.json"
        manifest_path.write_bytes(runner._canonical_json(manifest))
        seal = {
            "schema_version": runner.PUBLIC_SEAL_SCHEMA,
            "case_id": case_id,
            "public_manifest_sha256": runner._file_sha256(manifest_path),
            "artifact_sha256": {
                "input": runner._file_sha256(staged_input),
                "prompt": runner._file_sha256(staged_prompt),
                "public_context": runner._file_sha256(public_context_path),
            },
        }
        seal_path = staging / "public-seal.json"
        seal_path.write_bytes(runner._canonical_json(seal))
        runner.load_public_case(staging)
        os.replace(staging, output)
        published = True
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)
    return {
        "status": "SEALED",
        "case_id": case_id,
        "output": str(output),
        "public_manifest_sha256": runner._file_sha256(output / "public-manifest.json"),
        "public_seal_sha256": runner._file_sha256(output / "public-seal.json"),
        "semantic_leakage_review": "NOT_EVALUATED",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a hash-bound public fixture. Exact atom-ID leakage is rejected; "
            "semantic hint leakage still requires an independent review."
        )
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--mode", choices=("DIAGNOSE", "REWRITE", "DRAFT"), required=True)
    parser.add_argument(
        "--scene",
        choices=("AUTO", "COURSE", "MODELING", "RESEARCH", "GENERAL"),
        required=True,
    )
    parser.add_argument(
        "--intensity", choices=("LIGHT", "BALANCED", "STRUCTURAL"), required=True
    )
    parser.add_argument(
        "--output-format", choices=("CLEAN", "ANNOTATED", "PATCH"), required=True
    )
    parser.add_argument(
        "--report-context", choices=("NONE", "REPORT_INFORMED"), default="NONE"
    )
    parser.add_argument("--scope", choices=("selection", "section", "document"), required=True)
    parser.add_argument("--title-lock", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--structure-lock", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--operation",
        choices=("PREPARE_LONG_DOCUMENT", "CLASSIFY_SOURCE_PROVENANCE"),
    )
    parser.add_argument("--locked-literal", action="append", default=[])
    parser.add_argument("--summary-max-sentences", type=int)
    parser.add_argument("--required-output-format", choices=("JSON_INCLUDE_MANIFEST",))
    parser.add_argument("--preserve-three-groups", action="store_true")
    parser.add_argument(
        "--vary-paragraph-rhythm-without-forced-asymmetry", action="store_true"
    )
    parser.add_argument("--preserve-numbers-math", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = seal_fixture(
            args.input,
            args.prompt,
            args.output,
            case_id=args.case_id,
            mode=args.mode,
            scene=args.scene,
            intensity=args.intensity,
            output_format=args.output_format,
            report_context=args.report_context,
            scope=args.scope,
            title_lock=args.title_lock,
            structure_lock=args.structure_lock,
            operation=args.operation,
            locked_literals=args.locked_literal,
            summary_max_sentences=args.summary_max_sentences,
            required_output_format=args.required_output_format,
            preserve_three_groups=args.preserve_three_groups,
            vary_paragraph_rhythm_without_forced_asymmetry=(
                args.vary_paragraph_rhythm_without_forced_asymmetry
            ),
            preserve_numbers_math=args.preserve_numbers_math,
        )
    except (SealError, OSError) as error:
        result = {"status": "FAIL", "error": str(error)}
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"FAIL: {error}")
        return 1
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"SEALED case_id={result['case_id']} "
            f"semantic_leakage_review={result['semantic_leakage_review']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
