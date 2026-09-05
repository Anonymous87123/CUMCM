#!/usr/bin/env python
"""Merge disjoint-length chat n-gram aggregates without loading them in memory."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


VERSION = "1.0.0"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_metadata(path: Path) -> tuple[dict[str, Any], Path]:
    metadata_path = path.with_name("run_metadata.json")
    if not metadata_path.exists():
        raise ValueError(f"aggregate has no sibling run_metadata.json: {path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    lengths = metadata.get("ngram_lengths")
    if (
        not isinstance(lengths, list)
        or len(lengths) != 2
        or not all(isinstance(value, int) for value in lengths)
        or lengths[0] > lengths[1]
    ):
        raise ValueError(f"invalid ngram_lengths metadata: {metadata_path}")
    declared = metadata.get("aggregate_sha256")
    actual = sha256_path(path)
    if declared != actual:
        raise ValueError(f"aggregate hash mismatch: {path}")
    return metadata, metadata_path


def copy_with_hash(source: Path, target, digest: hashlib._Hash) -> int:
    copied = 0
    last = b""
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            target.write(chunk)
            digest.update(chunk)
            copied += len(chunk)
            last = chunk[-1:]
    if copied and last != b"\n":
        target.write(b"\n")
        digest.update(b"\n")
        copied += 1
    return copied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if len(args.input) < 2:
        raise SystemExit("at least two --input aggregates are required")
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    sources: list[dict[str, Any]] = []
    occupied_lengths: set[int] = set()
    for path in args.input:
        metadata, metadata_path = source_metadata(path)
        lower, upper = metadata["ngram_lengths"]
        lengths = set(range(lower, upper + 1))
        overlap = occupied_lengths & lengths
        if overlap:
            raise ValueError(
                f"aggregate ngram length ranges overlap: {sorted(overlap)}"
            )
        occupied_lengths.update(lengths)
        sources.append(
            {
                "path": str(path),
                "sha256": metadata["aggregate_sha256"],
                "metadata": str(metadata_path),
                "ngram_lengths": [lower, upper],
                "unique_candidates": int(metadata.get("unique_candidates", 0)),
            }
        )

    digest = hashlib.sha256()
    bytes_written = 0
    with args.output.open("xb") as handle:
        for path in args.input:
            bytes_written += copy_with_hash(path, handle, digest)

    metadata = {
        "schema_version": "humanize-merged-chat-ngram/v1",
        "version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "sources": sources,
        "ngram_lengths": [min(occupied_lengths), max(occupied_lengths)],
        "unique_candidates": sum(item["unique_candidates"] for item in sources),
        "bytes": bytes_written,
        "aggregate": str(args.output),
        "aggregate_sha256": digest.hexdigest(),
        "disjoint_length_ranges_verified": True,
    }
    metadata_path = args.metadata or args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
