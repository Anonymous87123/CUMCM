#!/usr/bin/env python3
"""Create a source-hash-bound dev/holdout matrix manifest.

The command only reads declared build reports, suites, source files and
manifests.  It does not inspect paragraph text beyond the hashes already
recorded by the suite builder, and it does not assign quality ratings.

Public interface:
    python build_style_benchmark_matrix.py --root MATRIX_ROOT \
        --output MATRIX.json --modeling-source SOURCE --modeling-build BUILD \
        --modeling-dev-manifest MANIFEST --modeling-holdout-manifest MANIFEST \
        ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import sha256_file, write_json


def _lock(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256_file(path)}


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _entry(root: Path, document_type: str, source: Path, build: Path, dev: Path, holdout: Path) -> dict:
    build_payload = _load(build)
    for split, manifest in (("dev", dev), ("holdout", holdout)):
        suite_record = build_payload.get(split)
        if not isinstance(suite_record, dict):
            raise ValueError(f"build report has no {split} suite: {build}")
        suite = Path(str(suite_record.get("suite", ""))).resolve()
        if not suite.is_file():
            raise FileNotFoundError(suite)
        if suite_record.get("sha256") != sha256_file(suite):
            raise ValueError(f"build report {split} suite hash is stale: {suite}")
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
    return {
        "document_type": document_type,
        "source": _lock(source),
        "build_report": _lock(build),
        "dev": {
            "definition": _lock(Path(str(build_payload["dev"]["suite"]))),
            "manifest": _lock(dev),
            "state": _load(dev).get("state"),
        },
        "holdout": {
            "definition": _lock(Path(str(build_payload["holdout"]["suite"]))),
            "manifest": _lock(holdout),
            "state": _load(holdout).get("state"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for document_type in ("modeling", "course-notes", "research"):
        prefix = document_type.replace("-", "_")
        parser.add_argument(f"--{prefix}-source", type=Path, required=True)
        parser.add_argument(f"--{prefix}-build", type=Path, required=True)
        parser.add_argument(f"--{prefix}-dev-manifest", type=Path, required=True)
        parser.add_argument(f"--{prefix}-holdout-manifest", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    entries = []
    for document_type in ("modeling", "course-notes", "research"):
        prefix = document_type.replace("-", "_")
        entries.append(_entry(
            root,
            document_type,
            getattr(args, f"{prefix}_source").resolve(),
            getattr(args, f"{prefix}_build").resolve(),
            getattr(args, f"{prefix}_dev_manifest").resolve(),
            getattr(args, f"{prefix}_holdout_manifest").resolve(),
        ))
    payload = {
        "schema": "aigc-style-benchmark-matrix/v1",
        "run_root": str(root),
        "entries": entries,
        "claims": {
            "human_style_quality_proven": False,
            "authorship_proven": False,
            "detector_outcome_predicted": False,
        },
    }
    output = args.output.resolve()
    write_json(output, payload)
    print(f"STYLE MATRIX READY entries={len(entries)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
