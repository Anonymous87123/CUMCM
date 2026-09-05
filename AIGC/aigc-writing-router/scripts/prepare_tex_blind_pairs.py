#!/usr/bin/env python3
"""Build hash-bound same-source blind pairs from explicit TeX line ranges.

Public interface:
    python prepare_tex_blind_pairs.py SPEC.json --output pairs.json

The output is consumed by ``blind_pair_evaluation.py prepare``.  The source
and candidate mapping remains in this private preparation artifact; raters see
only the separately randomised A/B packet.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from adapter_core import sha256_file, write_json


SPEC_SCHEMA = "aigc-tex-blind-pair-spec/v1"
PAIR_SCHEMA = "aigc-blind-pairs/v1"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _resolve_file(spec_path: Path, record: object, label: str) -> tuple[Path, str]:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        raise ValueError(f"{label} needs path and sha256")
    path = Path(str(record["path"]))
    if not path.is_absolute():
        path = (spec_path.parent / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual.casefold() != str(record["sha256"]).casefold():
        raise ValueError(f"{label} SHA-256 mismatch")
    return path, actual


def _line_range(record: object, label: str, line_count: int) -> tuple[int, int]:
    if not isinstance(record, dict):
        raise ValueError(f"{label} line range must be an object")
    start, end = record.get("start"), record.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > line_count:
        raise ValueError(f"{label} line range is outside 1..{line_count}")
    return start, end


def _review_text(lines: list[str], start: int, end: int) -> str:
    selected = []
    for line in lines[start - 1:end]:
        selected.append(re.sub(r"(?<!\\)%.*$", "", line))
    text = "\n".join(selected)
    text = re.sub(r"\\noindent\b", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build(spec_path: Path, output_path: Path) -> dict[str, Any]:
    spec_path = spec_path.resolve()
    payload = _read_json(spec_path)
    if payload.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    source, source_sha = _resolve_file(spec_path, payload.get("source"), "source")
    candidate, candidate_sha = _resolve_file(spec_path, payload.get("candidate"), "candidate")
    if source_sha == candidate_sha:
        raise ValueError("source and candidate are byte-identical")
    source_lines = source.read_text(encoding="utf-8-sig").splitlines()
    candidate_lines = candidate.read_text(encoding="utf-8-sig").splitlines()
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("at least one line-range pair is required")
    pairs = []
    seen: set[str] = set()
    for raw in raw_pairs:
        if not isinstance(raw, dict):
            raise ValueError("pair record must be an object")
        pair_id = str(raw.get("id", "")).strip()
        if not pair_id or pair_id in seen:
            raise ValueError("pair ids must be non-empty and unique")
        seen.add(pair_id)
        source_range = _line_range(raw.get("source_lines"), f"{pair_id}.source", len(source_lines))
        candidate_range = _line_range(raw.get("candidate_lines"), f"{pair_id}.candidate", len(candidate_lines))
        source_text = _review_text(source_lines, *source_range)
        candidate_text = _review_text(candidate_lines, *candidate_range)
        if not source_text or not candidate_text:
            raise ValueError(f"pair {pair_id} produced an empty passage")
        pairs.append({
            "id": pair_id,
            "section": str(raw.get("section", "")).strip(),
            "line_binding": {
                "source": {"start": source_range[0], "end": source_range[1]},
                "candidate": {"start": candidate_range[0], "end": candidate_range[1]},
            },
            "variants": [
                {"id": "source", "text": source_text},
                {"id": "candidate", "text": candidate_text},
            ],
        })
    result = {
        "schema": PAIR_SCHEMA,
        "provenance": {
            "spec": {"path": str(spec_path), "sha256": sha256_file(spec_path)},
            "source": {"path": str(source), "sha256": source_sha},
            "candidate": {"path": str(candidate), "sha256": candidate_sha},
            "mapping_visibility": "private-preparation-only",
        },
        "pairs": pairs,
    }
    write_json(output_path.resolve(), result)
    return {
        "schema": "aigc-tex-blind-pair-build/v1",
        "status": "pass",
        "pairs": len(pairs),
        "output": str(output_path.resolve()),
        "output_sha256": sha256_file(output_path.resolve()),
        "source_sha256": source_sha,
        "candidate_sha256": candidate_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build(args.spec, args.output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"schema": "aigc-tex-blind-pair-build/v1", "status": "fail", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"TEX BLIND PAIRS {report['status'].upper()} pairs={report.get('pairs', 0)}")
        if report.get("error"):
            print(f"[ERROR] {report['error']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
