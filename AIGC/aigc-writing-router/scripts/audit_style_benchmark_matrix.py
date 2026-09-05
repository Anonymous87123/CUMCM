#!/usr/bin/env python3
"""Audit current-bound real-draft improvement benchmarks across Chinese scenes.

Public interface:
    python audit_style_benchmark_matrix.py MATRIX.json --format text|json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from adapter_core import sha256_file
from run_style_benchmark import audit_manifest


SCHEMA = "aigc-style-benchmark-matrix/v1"
SUITE_SCHEMA = "aigc-style-benchmark-suite/v1"
BUILD_SCHEMA = "aigc-draft-improvement-suite-build/v1"
REQUIRED_DOCUMENT_TYPES = {"modeling", "course-notes", "research"}


def _add(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _locked_path(base: Path, record: object, findings: list[dict], label: str) -> Path | None:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        _add(findings, "MATRIX_LOCK_INVALID", label=label)
        return None
    path = Path(str(record["path"]))
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file():
        _add(findings, "MATRIX_FILE_MISSING", label=label, path=str(path))
        return None
    actual = sha256_file(path)
    if actual != str(record["sha256"]):
        _add(findings, "MATRIX_FILE_DRIFT", label=label, expected=record["sha256"], actual=actual)
        return None
    return path


def _load(path: Path, findings: list[dict], label: str) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _add(findings, "MATRIX_JSON_INVALID", label=label, error=str(exc))
        return None
    if not isinstance(payload, dict):
        _add(findings, "MATRIX_JSON_NOT_OBJECT", label=label)
        return None
    return payload


def _paragraph_hash(text: str) -> str:
    return hashlib.sha256(text.rstrip("\r\n").encode("utf-8")).hexdigest()


def _audit_definition(
    definition_path: Path,
    build: dict,
    source_path: Path,
    document_type: str,
    split: str,
    findings: list[dict],
) -> tuple[dict | None, set[str]]:
    suite = _load(definition_path, findings, f"{document_type}-{split}-definition")
    if suite is None:
        return None, set()
    if (
        suite.get("schema") != SUITE_SCHEMA
        or suite.get("split") != split
        or suite.get("benchmark_goal") != "improvement"
        or suite.get("providers") != ["humanize-academic-chinese"]
        or suite.get("required_trials") != 3
        or suite.get("required_generation_evidence") != ["stack_evaluation"]
    ):
        _add(findings, "MATRIX_SUITE_CONTRACT_INVALID", document_type=document_type, split=split)
    build_split = build.get(split)
    if not isinstance(build_split, dict) or (
        Path(str(build_split.get("suite", ""))).resolve() != definition_path
        or str(build_split.get("sha256", "")) != sha256_file(definition_path)
        or build_split.get("cases") != 3
    ):
        _add(findings, "MATRIX_BUILD_SUITE_LOCK_INVALID", document_type=document_type, split=split)
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        _add(findings, "MATRIX_CASE_COUNT_INVALID", document_type=document_type, split=split)
        return suite, set()
    original_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    source_sha = sha256_file(source_path)
    hashes: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            _add(findings, "MATRIX_CASE_INVALID", document_type=document_type, split=split, index=index)
            continue
        case_id = str(case.get("id", ""))
        scene = case.get("scene")
        if scene != {"document_type": document_type, "document_format": "tex", "scope": "local"}:
            _add(findings, "MATRIX_CASE_SCENE_INVALID", case_id=case_id)
        provenance = case.get("provenance")
        if not isinstance(provenance, dict):
            _add(findings, "MATRIX_CASE_PROVENANCE_MISSING", case_id=case_id)
            continue
        digest = str(provenance.get("paragraph_sha256", ""))
        start = provenance.get("start_line")
        end = provenance.get("end_line")
        if (
            provenance.get("kind") != "real-draft-section"
            or Path(str(provenance.get("source_document", ""))).resolve() != source_path
            or provenance.get("source_document_sha256") != source_sha
            or provenance.get("selection_seed") != build.get("seed")
            or provenance.get("quality_label_used_for_selection") is not False
            or not isinstance(start, int) or not isinstance(end, int)
            or not 1 <= start <= end <= len(original_lines)
            or len(digest) != 64
        ):
            _add(findings, "MATRIX_CASE_PROVENANCE_INVALID", case_id=case_id)
            continue
        snapshot = (definition_path.parent / str(case.get("source", ""))).resolve()
        if not _inside(snapshot, definition_path.parent) or not snapshot.is_file():
            _add(findings, "MATRIX_CASE_SOURCE_INVALID", case_id=case_id)
            continue
        snapshot_text = snapshot.read_text(encoding="utf-8-sig").rstrip("\r\n")
        excerpt = "\n".join(original_lines[start - 1:end]).strip()
        if _paragraph_hash(snapshot_text) != digest or excerpt != snapshot_text:
            _add(findings, "MATRIX_CASE_SOURCE_DRIFT", case_id=case_id)
        if digest in hashes:
            _add(findings, "MATRIX_CASE_DUPLICATE", case_id=case_id)
        hashes.add(digest)
    return suite, hashes


def audit(matrix_path: Path, registry_path: Path) -> dict:
    matrix_path = matrix_path.resolve()
    findings: list[dict] = []
    matrix = _load(matrix_path, findings, "matrix")
    if matrix is None:
        return _report({}, {}, findings)
    if matrix.get("schema") != SCHEMA:
        _add(findings, "MATRIX_SCHEMA_INVALID")
    run_root = Path(str(matrix.get("run_root", ""))).resolve()
    if not run_root.is_dir():
        _add(findings, "MATRIX_RUN_ROOT_INVALID", path=str(run_root))
    entries = matrix.get("entries")
    if not isinstance(entries, list):
        _add(findings, "MATRIX_ENTRIES_INVALID")
        return _report({}, {}, findings)
    document_types: set[str] = set()
    states: dict[str, dict[str, str]] = {}
    entry_status: dict[str, str] = {}
    expected_builder = Path(__file__).resolve().parent / "prepare_draft_improvement_suite.py"
    for entry_index, entry in enumerate(entries):
        before_errors = sum(item["severity"] == "error" for item in findings)
        if not isinstance(entry, dict):
            _add(findings, "MATRIX_ENTRY_INVALID", index=entry_index)
            continue
        document_type = str(entry.get("document_type", ""))
        if document_type not in REQUIRED_DOCUMENT_TYPES or document_type in document_types:
            _add(findings, "MATRIX_DOCUMENT_TYPE_INVALID", index=entry_index, document_type=document_type)
            continue
        document_types.add(document_type)
        source_path = _locked_path(matrix_path.parent, entry.get("source"), findings, f"{document_type}.source")
        build_path = _locked_path(matrix_path.parent, entry.get("build_report"), findings, f"{document_type}.build")
        if source_path is None or build_path is None:
            continue
        if not _inside(build_path, run_root):
            _add(findings, "MATRIX_BUILD_OUTSIDE_RUN_ROOT", document_type=document_type)
            continue
        build = _load(build_path, findings, f"{document_type}.build")
        if build is None:
            continue
        builder = build.get("builder")
        build_source = build.get("source")
        if (
            build.get("schema") != BUILD_SCHEMA
            or build.get("status") != "pass"
            or build.get("document_type") != document_type
            or build.get("required_generation_evidence") != ["stack_evaluation"]
            or build.get("selection_uses_quality_labels") is not False
            or not isinstance(builder, dict)
            or Path(str(builder.get("path", ""))).resolve() != expected_builder.resolve()
            or builder.get("sha256") != sha256_file(expected_builder)
            or not isinstance(build_source, dict)
            or Path(str(build_source.get("path", ""))).resolve() != source_path
            or build_source.get("sha256") != sha256_file(source_path)
        ):
            _add(findings, "MATRIX_BUILD_PROVENANCE_INVALID", document_type=document_type)
        excluded_hashes: set[str] = set()
        exclusions = build.get("exclusion_suites")
        if not isinstance(exclusions, list):
            _add(findings, "MATRIX_EXCLUSIONS_INVALID", document_type=document_type)
            exclusions = []
        for exclusion_index, exclusion in enumerate(exclusions):
            path = _locked_path(
                build_path.parent, exclusion, findings,
                f"{document_type}.exclusion[{exclusion_index}]",
            )
            if path is None:
                continue
            suite = _load(path, findings, f"{document_type}.exclusion[{exclusion_index}]")
            if suite is None:
                continue
            suite_hashes = {
                str(case.get("provenance", {}).get("paragraph_sha256", ""))
                for case in suite.get("cases", [])
                if isinstance(case, dict) and isinstance(case.get("provenance"), dict)
            }
            if "" in suite_hashes or exclusion.get("paragraphs") != len(suite_hashes):
                _add(findings, "MATRIX_EXCLUSION_CONTENT_INVALID", document_type=document_type)
            excluded_hashes.update(suite_hashes)
        split_hashes: dict[str, set[str]] = {}
        states[document_type] = {}
        for split in ("dev", "holdout"):
            split_entry = entry.get(split)
            if not isinstance(split_entry, dict):
                _add(findings, "MATRIX_SPLIT_ENTRY_INVALID", document_type=document_type, split=split)
                continue
            definition_path = _locked_path(
                matrix_path.parent, split_entry.get("definition"), findings,
                f"{document_type}.{split}.definition",
            )
            manifest_path = _locked_path(
                matrix_path.parent, split_entry.get("manifest"), findings,
                f"{document_type}.{split}.manifest",
            )
            if definition_path is None or manifest_path is None:
                continue
            if not _inside(definition_path, run_root) or not _inside(manifest_path, run_root):
                _add(findings, "MATRIX_SPLIT_OUTSIDE_RUN_ROOT", document_type=document_type, split=split)
                continue
            suite, hashes = _audit_definition(
                definition_path, build, source_path, document_type, split, findings,
            )
            split_hashes[split] = hashes
            manifest_report = audit_manifest(manifest_path, registry_path)
            expected_candidates = len(suite.get("cases", [])) * 3 if isinstance(suite, dict) else None
            if (
                manifest_report.get("status") != "pass"
                or manifest_report.get("rule_freshness") != "current-bound"
                or manifest_report.get("benchmark_goal") != "improvement"
                or manifest_report.get("state") != split_entry.get("state")
                or manifest_report.get("candidates") != expected_candidates
            ):
                _add(
                    findings, "MATRIX_MANIFEST_INVALID", document_type=document_type,
                    split=split, report=manifest_report,
                )
                continue
            states[document_type][split] = str(manifest_report["state"])
        overlap = split_hashes.get("dev", set()) & split_hashes.get("holdout", set())
        reused = (split_hashes.get("dev", set()) | split_hashes.get("holdout", set())) & excluded_hashes
        if overlap:
            _add(findings, "MATRIX_DEV_HOLDOUT_OVERLAP", document_type=document_type)
        if reused:
            _add(findings, "MATRIX_EXCLUDED_PARAGRAPH_REUSED", document_type=document_type)
        after_errors = sum(item["severity"] == "error" for item in findings)
        entry_status[document_type] = "pass" if after_errors == before_errors else "fail"
    if document_types != REQUIRED_DOCUMENT_TYPES:
        _add(findings, "MATRIX_DOCUMENT_TYPE_COVERAGE_INVALID", actual=sorted(document_types))
    return _report(states, entry_status, findings)


def _report(states: dict, entry_status: dict, findings: list[dict]) -> dict:
    errors = sum(item.get("severity") == "error" for item in findings)
    complete = all(
        set(split_states) == {"dev", "holdout"}
        for split_states in states.values()
    ) and set(states) == REQUIRED_DOCUMENT_TYPES
    return {
        "schema": "aigc-style-benchmark-matrix-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "warnings": 0,
        "entry_status": entry_status,
        "states": states,
        "human_quality_status": "HUMAN_RATINGS_PENDING" if complete and errors == 0 else "EVIDENCE_INVALID",
        "findings": findings,
        "claims": {
            "mechanical_role_chain_verified": errors == 0,
            "human_style_quality_proven": False,
            "authorship_proven": False,
        },
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    parser.add_argument(
        "--registry", type=Path,
        default=skill_root / "references" / "stack-registry.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.matrix, args.registry.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC STYLE MATRIX {report['status'].upper()} "
            f"human_quality={report['human_quality_status']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            print(f"[ERROR] {finding['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
