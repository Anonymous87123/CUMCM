#!/usr/bin/env python
"""Build a reproducible byte-frozen MD/TeX input snapshot.

The snapshot records the effective root set and file-set hashes so a later
run cannot silently reuse a file list discovered under different roots.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


VERSION = "1.0.0"
DOCUMENT_SUFFIXES = frozenset({".md", ".tex"})
DEFAULT_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "$RECYCLE.BIN",
        "System Volume Information",
    }
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def normalized_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(path))


def canonical_path_set_sha256(paths: Iterable[Path | str]) -> str:
    payload = json.dumps(
        sorted({normalized_path(path) for path in paths}),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_set_sha256(files: Iterable[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted(
            (
                normalized_path(str(item["path"])),
                int(item["size"]),
                int(item["mtime_ns"]),
            )
            for item in files
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def under_excluded(path: Path, excluded: set[str]) -> bool:
    value = normalized_path(path)
    return any(value == root or value.startswith(root + os.sep) for root in excluded)


def discover_document_snapshot(
    roots: Iterable[Path], excluded_roots: Iterable[Path]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    effective_roots = [Path(root) for root in roots]
    excluded = {normalized_path(path) for path in excluded_roots}
    found: dict[str, dict[str, Any]] = {}
    root_audit: list[dict[str, Any]] = []

    for root in effective_roots:
        resolved = normalized_path(root)
        if not root.exists():
            root_audit.append(
                {"root": str(root), "normalized_root": resolved, "status": "MISSING"}
            )
            continue
        if under_excluded(root, excluded):
            root_audit.append(
                {"root": str(root), "normalized_root": resolved, "status": "EXCLUDED"}
            )
            continue
        root_audit.append(
            {"root": str(root), "normalized_root": resolved, "status": "SCANNED"}
        )
        for current, dirs, names in os.walk(root):
            current_path = Path(current)
            if under_excluded(current_path, excluded):
                dirs[:] = []
                continue
            dirs[:] = [
                name
                for name in dirs
                if name not in DEFAULT_EXCLUDED_DIR_NAMES
                and not under_excluded(current_path / name, excluded)
            ]
            for name in names:
                path = current_path / name
                suffix = path.suffix.lower()
                if suffix not in DOCUMENT_SUFFIXES:
                    continue
                key = normalized_path(path)
                try:
                    stat = path.stat()
                except OSError:
                    continue
                found[key] = {
                    "path": str(path),
                    "size": int(stat.st_size),
                    "mtime_ns": int(stat.st_mtime_ns),
                    "suffix": suffix,
                }

    files = [found[key] for key in sorted(found)]
    return files, root_audit


def write_manifest(path: Path, files: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "suffix", "size", "mtime_ns"]
        )
        writer.writeheader()
        writer.writerows(files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--exclude-root", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    files, root_audit = discover_document_snapshot(args.root, args.exclude_root)
    roots = [str(path) for path in args.root]
    payload = {
        "schema_version": "humanize-document-snapshot/v2",
        "builder_version": VERSION,
        "created_at": utc_now(),
        "roots": roots,
        "effective_roots": roots,
        "excluded_roots": [str(path) for path in args.exclude_root],
        "root_set_sha256": canonical_path_set_sha256(roots),
        "file_set_sha256": file_set_sha256(files),
        "file_count": len(files),
        "suffix_counts": {
            suffix: sum(item["suffix"] == suffix for item in files)
            for suffix in sorted(DOCUMENT_SUFFIXES)
        },
        "root_audit": root_audit,
        "files": [
            {key: item[key] for key in ("path", "size", "mtime_ns")}
            for item in files
        ],
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = args.manifest or args.output.with_suffix(".csv")
    write_manifest(manifest, files)
    print(json.dumps(payload | {"files": f"<{len(files)} entries>"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
