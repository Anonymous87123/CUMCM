#!/usr/bin/env python3
"""Create and audit a CUMCM evidence bundle for an AIGC rewrite.

The bundle binds the manuscript to the problem statement, data, code and
generated results.  It records hashes and provenance; it never executes
untrusted code and never invents a missing result.

Public interface:
    python prepare_competition_evidence.py init --source main.tex
        --output-dir run --problem-type A --problem-file problem.pdf
        --data-file data.xlsx --code-file solve.py --result-file result.csv
        [--provenance provenance.json] [--repro-manifest repro.json]
        [--copy] [--format text|json]
    python prepare_competition_evidence.py audit evidence-manifest.json
        [--require-materials] [--require-execution] [--format text|json]
    python prepare_competition_evidence.py attach-execution evidence-manifest.json
        --repro-manifest repro.json [--output evidence-executed.json]
        [--format text|json]

Exit codes: 0=PASS, 2=REVIEW (missing material or execution record),
1=input/manifest error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA = "aigc-competition-evidence/v1"
KINDS = ("problem", "data", "code", "result")
TEXT_SUFFIXES = {".txt", ".md", ".tex", ".csv", ".json", ".py", ".m", ".r"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _path_list(values: Iterable[Path], excluded: Path | None = None) -> list[Path]:
    """Expand files/directories deterministically and remove duplicates."""
    result: dict[str, Path] = {}
    excluded_resolved = excluded.resolve() if excluded else None
    for value in values:
        path = value.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        paths = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
        for item in paths:
            item = item.resolve()
            if excluded_resolved and (item == excluded_resolved or excluded_resolved in item.parents):
                continue
            result[str(item).casefold()] = item
    return sorted(result.values(), key=lambda item: str(item).casefold())


def _provenance_map(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    payload = _read_json(path.resolve())
    # Accept either {"/absolute/file": {...}} or {"files": [{"path":...}]}.
    raw = payload.get("files", payload)
    records: list[dict]
    if isinstance(raw, dict):
        records = [{"path": key, **(value if isinstance(value, dict) else {})} for key, value in raw.items()]
    elif isinstance(raw, list):
        records = [item for item in raw if isinstance(item, dict)]
    else:
        raise ValueError("provenance JSON must be a mapping or a files list")
    result: dict[str, dict] = {}
    for item in records:
        literal = str(item.get("path", "")).strip()
        if not literal:
            continue
        result[str(Path(literal).expanduser().resolve()).casefold()] = {
            key: value for key, value in item.items() if key != "path"
        }
    return result


def _record(path: Path, kind: str, provenance: dict[str, dict], *, stored_path: Path | None = None) -> dict:
    actual = path.resolve()
    record = {
        "kind": kind,
        "path": str((stored_path or actual).resolve()),
        "origin_path": str(actual),
        "bytes": actual.stat().st_size,
        "sha256": sha256(actual),
        "suffix": actual.suffix.casefold(),
    }
    record["provenance"] = provenance.get(str(actual).casefold(), {"source": "provided-local"})
    if actual.suffix.casefold() in TEXT_SUFFIXES and actual.stat().st_size <= 2 * 1024 * 1024:
        try:
            text = actual.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            text = ""
        record["text_chars"] = len(text)
    return record


def _copy_material(path: Path, root: Path, kind: str, index: int) -> Path:
    destination = root / "materials" / kind / f"{index:03d}-{path.name}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination


def _material_args(parser: argparse.ArgumentParser) -> None:
    for kind in KINDS:
        parser.add_argument(f"--{kind}-file", action="append", type=Path, default=[])
        parser.add_argument(f"--{kind}-dir", action="append", type=Path, default=[])


def init_bundle(args: argparse.Namespace) -> tuple[Path, dict]:
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "evidence-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite {manifest_path}")
    provenance = _provenance_map(args.provenance)
    materials: list[dict] = []
    counts: dict[str, int] = {}
    for kind in KINDS:
        values = [*getattr(args, f"{kind}_file"), *getattr(args, f"{kind}_dir")]
        paths = _path_list(values, excluded=output_dir)
        counts[kind] = len(paths)
        for index, path in enumerate(paths, start=1):
            stored = _copy_material(path, output_dir, kind, index) if args.copy else None
            materials.append(_record(path, kind, provenance, stored_path=stored))

    manuscript = {
        "kind": "manuscript",
        "path": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha256(source),
        "suffix": source.suffix.casefold(),
    }
    execution: dict = {"status": "pending", "repro_manifest": None}
    if args.repro_manifest:
        repro = args.repro_manifest.expanduser().resolve()
        if not repro.is_file():
            raise FileNotFoundError(repro)
        execution = {
            "status": "recorded",
            "repro_manifest": {
                "path": str(repro),
                "bytes": repro.stat().st_size,
                "sha256": sha256(repro),
            },
            "instruction": "Run audit_repro_manifest.py and replace status with verified only after it passes.",
        }
    payload = {
        "schema": SCHEMA,
        "created_at": utc_now(),
        "problem_type": args.problem_type,
        "authority": {"manuscript": manuscript},
        "materials": materials,
        "execution": execution,
        "policy": {
            "source_is_read_only": True,
            "results_must_be_generated": True,
            "untrusted_code_is_not_executed_by_this_script": True,
            "network_data_requires_provenance": True,
        },
        "completeness": {
            "counts": counts,
            "missing_kinds": [kind for kind in KINDS if counts[kind] == 0],
            "provenance_missing_data": sum(
                1 for item in materials
                if item["kind"] == "data" and not item.get("provenance", {}).get("source_url")
            ),
        },
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, payload


def audit_bundle(
    manifest_path: Path,
    require_execution: bool = False,
    require_materials: bool = False,
) -> dict:
    payload = _read_json(manifest_path.resolve())
    findings: list[dict] = []
    if payload.get("schema") != SCHEMA:
        findings.append({"severity": "error", "code": "SCHEMA_MISMATCH", "actual": payload.get("schema")})
    authority = payload.get("authority", {})
    manuscript = authority.get("manuscript", {}) if isinstance(authority, dict) else {}
    if not isinstance(manuscript, dict) or not manuscript.get("path"):
        findings.append({"severity": "error", "code": "MANUSCRIPT_MISSING"})
    elif _check_record(manuscript, findings, manifest_path.parent, "MANUSCRIPT") is None:
        pass
    materials = payload.get("materials")
    if not isinstance(materials, list):
        findings.append({"severity": "error", "code": "MATERIALS_MISSING"})
        materials = []
    counts = {kind: 0 for kind in KINDS}
    for index, item in enumerate(materials):
        if not isinstance(item, dict):
            findings.append({"severity": "error", "code": "MATERIAL_INVALID", "index": index})
            continue
        kind = str(item.get("kind", ""))
        if kind not in KINDS:
            findings.append({"severity": "error", "code": "MATERIAL_KIND_INVALID", "index": index, "kind": kind})
            continue
        counts[kind] += 1
        _check_record(item, findings, manifest_path.parent, "MATERIAL")
        if kind == "data":
            provenance = item.get("provenance", {})
            source_kind = provenance.get("source_kind") if isinstance(provenance, dict) else None
            if not source_kind:
                findings.append({"severity": "warning", "code": "DATA_PROVENANCE_KIND_MISSING", "path": item.get("path")})
            elif source_kind == "network":
                for field in ("source_url", "fetched_at"):
                    if not provenance.get(field):
                        findings.append({
                            "severity": "warning",
                            "code": "NETWORK_DATA_PROVENANCE_FIELD_MISSING",
                            "path": item.get("path"),
                            "field": field,
                        })
    for kind, count in counts.items():
        if count == 0:
            findings.append({
                "severity": "error" if require_materials else "warning",
                "code": "MATERIAL_KIND_MISSING",
                "kind": kind,
            })
    execution = payload.get("execution", {})
    if not isinstance(execution, dict):
        execution = {}
    repro = execution.get("repro_manifest")
    if require_execution and not isinstance(repro, dict):
        findings.append({"severity": "error", "code": "EXECUTION_RECORD_MISSING"})
    elif not isinstance(repro, dict):
        findings.append({"severity": "warning", "code": "EXECUTION_RECORD_PENDING"})
    elif not _check_record(repro, findings, manifest_path.parent, "REPRO_MANIFEST"):
        pass
    elif execution.get("status") != "verified":
        findings.append({"severity": "warning", "code": "REPRO_MANIFEST_NOT_VERIFIED", "status": execution.get("status")})
    audit_record = execution.get("audit_report") if isinstance(execution, dict) else None
    if execution.get("status") == "verified" and not isinstance(audit_record, dict):
        findings.append({"severity": "error", "code": "REPRO_AUDIT_REPORT_MISSING"})
    elif isinstance(audit_record, dict):
        _check_record(audit_record, findings, manifest_path.parent, "REPRO_AUDIT_REPORT")
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    status = "pass" if errors == 0 and warnings == 0 else ("review" if errors == 0 else "fail")
    return {
        "schema": "aigc-competition-evidence-audit/v1",
        "status": status,
        "manifest": str(manifest_path.resolve()),
        "problem_type": payload.get("problem_type"),
        "counts": counts,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def attach_execution(
    manifest_path: Path,
    repro_manifest: Path,
    output_path: Path | None = None,
) -> tuple[Path, dict, dict]:
    """Audit a reproduction manifest and append an immutable receipt."""
    manifest_path = manifest_path.expanduser().resolve()
    repro_manifest = repro_manifest.expanduser().resolve()
    payload = _read_json(manifest_path)
    if payload.get("schema") != SCHEMA:
        raise ValueError("evidence manifest schema mismatch")
    if not repro_manifest.is_file():
        raise FileNotFoundError(repro_manifest)
    skill_root = Path(__file__).resolve().parents[3]
    audit_script = skill_root / "mcm-cup-standard-write" / "scripts" / "audit_repro_manifest.py"
    if not audit_script.is_file():
        raise FileNotFoundError(audit_script)
    process = subprocess.run(
        [sys.executable, str(audit_script), str(repro_manifest), "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        audit_report = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"reproducibility audit returned invalid JSON: {process.stdout[:200]}"
        ) from exc
    destination = (
        output_path.expanduser().resolve()
        if output_path
        else manifest_path.with_name(f"{manifest_path.stem}-executed.json")
    )
    if destination == manifest_path:
        raise ValueError("write execution evidence to a new manifest; the source manifest is immutable")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    audit_path = destination.with_name(f"{destination.stem}-repro-audit.json")
    if audit_path.exists():
        raise FileExistsError(f"refusing to overwrite {audit_path}")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    payload["execution"] = {
        "status": "verified" if process.returncode == 0 and audit_report.get("status") == "pass" else "failed",
        "verified_at": utc_now(),
        "repro_manifest": {
            "path": str(repro_manifest),
            "bytes": repro_manifest.stat().st_size,
            "sha256": sha256(repro_manifest),
        },
        "audit_tool": {
            "path": str(audit_script.resolve()),
            "sha256": sha256(audit_script),
        },
        "audit_report": {
            "path": str(audit_path),
            "bytes": audit_path.stat().st_size,
            "sha256": sha256(audit_path),
        },
        "audit_returncode": process.returncode,
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination, payload, audit_report


def _check_record(item: dict, findings: list[dict], base: Path, label: str) -> dict | None:
    literal = str(item.get("path", "")).strip()
    expected = str(item.get("sha256", "")).lower().strip()
    if not literal or not expected:
        findings.append({"severity": "error", "code": f"{label}_RECORD_FIELDS_MISSING", "path": literal})
        return None
    path = Path(literal)
    if not path.is_absolute():
        path = (base / path).resolve()
    if not path.is_file():
        findings.append({"severity": "error", "code": f"{label}_MISSING", "path": literal})
        return None
    actual = sha256(path)
    if actual != expected:
        findings.append({"severity": "error", "code": f"{label}_HASH_MISMATCH", "path": literal, "expected": expected, "actual": actual})
    return item


def print_report(report: dict, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(
        f"EVIDENCE BUNDLE {report['status'].upper()} "
        f"problem_type={report.get('problem_type')} errors={report['errors']} "
        f"warnings={report['warnings']} counts={report.get('counts')}"
    )
    print(f"manifest={report['manifest']}")
    for finding in report.get("findings", []):
        detail = ", ".join(f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"})
        print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--output-dir", type=Path, required=True)
    init.add_argument("--problem-type", choices=("A", "B", "C"), required=True)
    _material_args(init)
    init.add_argument("--provenance", type=Path)
    init.add_argument("--repro-manifest", type=Path)
    init.add_argument("--copy", action="store_true")
    init.add_argument("--format", choices=("text", "json"), default="text")
    audit = sub.add_parser("audit")
    audit.add_argument("manifest", type=Path)
    audit.add_argument("--require-materials", action="store_true")
    audit.add_argument("--require-execution", action="store_true")
    audit.add_argument("--format", choices=("text", "json"), default="text")
    attach = sub.add_parser("attach-execution")
    attach.add_argument("manifest", type=Path)
    attach.add_argument("--repro-manifest", type=Path, required=True)
    attach.add_argument("--output", type=Path)
    attach.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        if args.command == "init":
            path, payload = init_bundle(args)
            report = audit_bundle(path)
            report["created"] = str(path)
            print_report(report, args.format)
            if report["status"] == "pass":
                return 0
            if report["status"] == "review":
                return 2
            return 1
        if args.command == "attach-execution":
            destination, _, repro_report = attach_execution(
                args.manifest, args.repro_manifest, args.output,
            )
            report = audit_bundle(destination, require_execution=True, require_materials=True)
            report["repro_status"] = repro_report.get("status")
            print_report(report, args.format)
            if report["status"] == "pass":
                return 0
            if report["status"] == "review":
                return 2
            return 1
        report = audit_bundle(args.manifest, args.require_execution, args.require_materials)
        print_report(report, args.format)
        if report["status"] == "pass":
            return 0
        if report["status"] == "review":
            return 2
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"EVIDENCE BUNDLE ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
