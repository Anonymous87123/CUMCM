from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SKILL = Path(r"C:\Users\Lenovo\.codex\skills\humanize-academic-chinese")
BUILDER_PATH = SKILL / "scripts" / "build_humanize_generator_projection.py"


def run(*args: str, cwd: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-B", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    parsed: object = None
    if completed.stdout.strip().startswith("{"):
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            pass
    return {
        "rc": completed.returncode,
        "json": parsed,
        "stdout_tail": completed.stdout[-500:],
        "stderr_tail": completed.stderr[-500:],
    }


spec = importlib.util.spec_from_file_location("projection_builder_audit", BUILDER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import projection builder")
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


with tempfile.TemporaryDirectory(prefix="humanize-projection-redteam-") as temporary:
    root = Path(temporary)
    source = root / "humanize-academic-chinese"
    shutil.copytree(SKILL, source)
    policy_path = source / "references" / "generator-projection-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["approved_builder_executable_sha256"] = builder._builder_executable_sha256()
    policy["approved_transform_registry_sha256"] = builder._transform_registry_sha256()
    policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    loaded = builder.load_policy(policy_path)
    frozen, dispositions = builder._inventory(source, loaded)
    policy["approved_capability_source_sha256"] = builder._projection_materials(
        frozen, dispositions, loaded
    )["source"]["capability_source_sha256"]
    policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    projection = root / "projection"
    manifest_path = root / "manifest.json"
    manifest = builder.build_projection(source, projection, manifest_path)
    projected_files = sorted(path.relative_to(projection).as_posix() for path in projection.rglob("*") if path.is_file())
    forbidden = set(policy["forbidden_reference_basenames"])
    forbidden_hits = [path for path in projected_files if Path(path).name in forbidden]
    projection_bytes = b"\n".join(path.read_bytes() for path in projection.rglob("*") if path.is_file())
    explicit_hidden = [
        b"paragraphs-not-equal-weight",
        b"scene-formality-preserved",
    ]
    hidden_hits = [token.decode("ascii") for token in explicit_hidden if token in projection_bytes]

    help_results: dict[str, object] = {}
    for script in sorted((projection / "scripts").glob("*.py")):
        result = run(str(script), "--help", cwd=projection)
        if result["rc"] != 0:
            help_results[script.name] = result

    seed = root / "generated.tex"
    seed.write_text("% Auto-generated file; do not edit.\nGenerated body.\n", encoding="utf-8")
    base_run = root / "base-run"
    prepare_no_scope = run(
        str(projection / "scripts" / "prepare_humanize_long_document.py"),
        str(seed), "--output", str(base_run), "--scene", "GENERAL", cwd=projection,
    )
    receipt_inputs: dict[str, Path] = {}
    (root / "empty.json").write_text("{}\n", encoding="utf-8")
    receipt_inputs["empty_object"] = root / "empty.json"
    (root / "receipt-directory").mkdir()
    receipt_inputs["directory"] = root / "receipt-directory"
    receipt_inputs["missing"] = root / "missing.json"
    (root / "invalid-utf8.json").write_bytes(b"\xff\xfe")
    receipt_inputs["invalid_utf8"] = root / "invalid-utf8.json"
    (root / "duplicate.json").write_text('{"a":1,"a":2}\n', encoding="utf-8")
    receipt_inputs["duplicate_key"] = root / "duplicate.json"
    (root / "deep.json").write_text("[" * 1500 + "]" * 1500, encoding="utf-8")
    receipt_inputs["deep_json"] = root / "deep.json"

    receipt_results: dict[str, object] = {}
    for label, receipt in receipt_inputs.items():
        case_run = root / f"run-{label}"
        shutil.copytree(base_run, case_run)
        rewrites = root / f"rewrites-{label}"
        rewrites.mkdir()
        result = run(
            str(projection / "scripts" / "finalize_humanize_long_document.py"),
            "--run-dir", str(case_run), "--rewrites", str(rewrites),
            "--second-pass-receipt", str(receipt), "--format", "json", cwd=projection,
        )
        payload = result.get("json") if isinstance(result.get("json"), dict) else {}
        receipt_results[label] = {
            "rc": result["rc"],
            "runtime_error": payload.get("runtime_error"),
            "completion": payload.get("humanize_completion_claim_allowed"),
            "clearance": payload.get("paired_quality_clearance_granted"),
            "evidence": payload.get("humanize_second_pass_evidence"),
            "stderr_tail": result["stderr_tail"],
        }

    editable = root / "editable.txt"
    editable.write_text(
        "需要指出的是，这一问题是十分重要的。综上所述，我们可以看出，这一结论具有重要意义。\n",
        encoding="utf-8",
    )
    editable_run = root / "editable-run"
    prepare_editable = run(
        str(projection / "scripts" / "prepare_humanize_long_document.py"),
        str(editable), "--output", str(editable_run), "--scene", "GENERAL", cwd=projection,
    )
    editable_rewrites = root / "editable-rewrites"
    scaffold_editable = run(
        str(projection / "scripts" / "scaffold_humanize_rewrites.py"),
        "--run-dir", str(editable_run), "--output", str(editable_rewrites),
        "--decision", "NO_CHANGE", "--format", "json", cwd=projection,
    )
    editable_finalize = run(
        str(projection / "scripts" / "finalize_humanize_long_document.py"),
        "--run-dir", str(editable_run), "--rewrites", str(editable_rewrites),
        "--second-pass-receipt", str(root / "empty.json"), "--format", "json", cwd=projection,
    )

    editable_payload = editable_finalize.get("json") if isinstance(editable_finalize.get("json"), dict) else {}
    result = {
        "manifest": {
            "files_field": len(manifest["files"]),
            "tree_files": len(projected_files),
            "transformations": len(manifest["transformations"]),
            "forbidden_basename_hits": forbidden_hits,
            "explicit_hidden_token_hits": hidden_hits,
        },
        "cli_help_nonzero": help_results,
        "prepare_no_scope": prepare_no_scope,
        "receipt_matrix": receipt_results,
        "editable": {
            "prepare": prepare_editable,
            "scaffold": scaffold_editable,
            "finalize_rc": editable_finalize["rc"],
            "runtime_error": editable_payload.get("runtime_error"),
            "completion": editable_payload.get("humanize_completion_claim_allowed"),
            "clearance": editable_payload.get("paired_quality_clearance_granted"),
            "evidence": editable_payload.get("humanize_second_pass_evidence"),
            "stderr_tail": editable_finalize["stderr_tail"],
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
