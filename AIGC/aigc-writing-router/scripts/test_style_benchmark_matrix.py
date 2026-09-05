#!/usr/bin/env python3
"""Regression tests for the multi-scene style benchmark matrix."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import audit_style_benchmark_matrix as matrix_module
from adapter_core import sha256_file


DOCUMENT_TYPES = ("modeling", "course-notes", "research")


def _lock(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _suite(root: Path, document_type: str, split: str, source: Path, offset: int) -> Path:
    suite_root = root / document_type / split
    cases = []
    lines = source.read_text(encoding="utf-8").splitlines()
    for local_index in range(3):
        line_no = offset + local_index + 1
        text = lines[line_no - 1]
        snapshot = suite_root / "sources" / f"case-{local_index + 1}.tex"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        cases.append({
            "id": f"{document_type}-{split}-{local_index + 1}",
            "scene": {"document_type": document_type, "document_format": "tex", "scope": "local"},
            "source": str(snapshot.relative_to(suite_root)),
            "provenance": {
                "kind": "real-draft-section",
                "source_document": str(source.resolve()),
                "source_document_sha256": sha256_file(source),
                "selection_seed": 20260820,
                "quality_label_used_for_selection": False,
                "start_line": line_no,
                "end_line": line_no,
                "paragraph_sha256": sha256_file(snapshot),
            },
        })
    definition = suite_root / "suite.json"
    _write_json(definition, {
        "schema": "aigc-style-benchmark-suite/v1",
        "split": split,
        "benchmark_goal": "improvement",
        "providers": ["humanize-academic-chinese"],
        "required_trials": 3,
        "required_generation_evidence": ["stack_evaluation"],
        "cases": cases,
    })
    return definition


def _build_matrix(root: Path) -> Path:
    entries = []
    builder = Path(matrix_module.__file__).with_name("prepare_draft_improvement_suite.py")
    for document_type in DOCUMENT_TYPES:
        scene_root = root / document_type
        source = scene_root / "source.tex"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "\n".join(
                f"Paragraph {index} for {document_type} records a distinct source observation, a bounded claim, "
                "and the evidence that controls the stated interpretation."
                for index in range(1, 7)
            ) + "\n",
            encoding="utf-8",
        )
        dev = _suite(root, document_type, "dev", source, 0)
        holdout = _suite(root, document_type, "holdout", source, 3)
        build = scene_root / "build.json"
        _write_json(build, {
            "schema": "aigc-draft-improvement-suite-build/v1",
            "status": "pass",
            "document_type": document_type,
            "required_generation_evidence": ["stack_evaluation"],
            "selection_uses_quality_labels": False,
            "seed": 20260820,
            "builder": _lock(builder),
            "source": _lock(source),
            "exclusion_suites": [],
            "dev": {"suite": str(dev.resolve()), "sha256": sha256_file(dev), "cases": 3},
            "holdout": {"suite": str(holdout.resolve()), "sha256": sha256_file(holdout), "cases": 3},
        })
        split_records = {}
        for split, definition in (("dev", dev), ("holdout", holdout)):
            manifest = scene_root / split / "manifest.json"
            _write_json(manifest, {"document_type": document_type, "split": split})
            split_records[split] = {
                "definition": _lock(definition),
                "manifest": _lock(manifest),
                "state": "BLIND_READY",
            }
        entries.append({
            "document_type": document_type,
            "source": _lock(source),
            "build_report": _lock(build),
            **split_records,
        })
    matrix = root / "matrix.json"
    _write_json(matrix, {
        "schema": "aigc-style-benchmark-matrix/v1",
        "run_root": str(root.resolve()),
        "entries": entries,
    })
    return matrix


def main() -> int:
    original = matrix_module.audit_manifest
    try:
        matrix_module.audit_manifest = lambda path, _registry: {
            "status": "pass",
            "rule_freshness": "current-bound",
            "benchmark_goal": "improvement",
            "state": "BLIND_READY",
            "candidates": 9,
        }
        with tempfile.TemporaryDirectory(prefix="style-matrix-") as temp:
            root = Path(temp)
            matrix = _build_matrix(root)
            passed = matrix_module.audit(matrix, root / "registry.json")
            assert passed["status"] == "pass", passed
            assert passed["human_quality_status"] == "HUMAN_RATINGS_PENDING"
            assert set(passed["entry_status"]) == set(DOCUMENT_TYPES)
            assert passed["claims"]["human_style_quality_proven"] is False

            research_source = root / "research" / "source.tex"
            research_source.write_text(
                research_source.read_text(encoding="utf-8") + "drift\n", encoding="utf-8",
            )
            failed = matrix_module.audit(matrix, root / "registry.json")
            codes = {item["code"] for item in failed["findings"]}
            assert failed["status"] == "fail", failed
            assert "MATRIX_FILE_DRIFT" in codes
            assert failed["human_quality_status"] == "EVIDENCE_INVALID"
    finally:
        matrix_module.audit_manifest = original
    print("style benchmark matrix tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
