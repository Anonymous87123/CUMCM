#!/usr/bin/env python3
"""Record section-level drafting lineage from packets to a candidate TeX tree.

This is an execution receipt, not a claim about hidden model state. It binds
the frozen source section, packet file, and candidate section by content hashes
so a later release audit can detect missing, shifted, or stale section work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_content_density import normalize_tex
from audit_manuscript import read_tex_tree
from prepare_section_drafting_packets import sha256_file
from prepare_style_retrieval_plan import section_target_records


SCHEMA = "mcm-section-drafting-usage/v1"
USAGE_AUDIT_SCHEMA = "mcm-section-drafting-usage-audit/v1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _locked(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _scope_hash(scope: str) -> str:
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()


def _scopes(path: Path) -> dict[str, dict]:
    rows = section_target_records(normalize_tex(read_tex_tree(path)))
    return {
        f"T{index:02d}": {
            "title": str(item["title"]),
            "role": str(item["role"]),
            "question_id": str(item["question_id"]) if item["question_id"] is not None else None,
            "line": int(item["line"]),
            "sha256": _scope_hash(str(item["tex_source"])),
            "chars": len(str(item["tex_source"])),
            "visible_sha256": _scope_hash(str(item["visible_prose"])),
            "visible_chars": len(str(item["visible_prose"])),
        }
        for index, item in enumerate(rows, 1)
    }


def _signature(scopes: dict[str, dict]) -> list[dict]:
    return [
        {
            "id": target_id,
            "title": item["title"],
            "role": item["role"],
            "question_id": item["question_id"],
        }
        for target_id, item in scopes.items()
    ]


def build(
    source: Path,
    candidate: Path,
    packet_index: Path,
    run_id: str,
    author_kind: str,
) -> dict:
    source = source.resolve()
    candidate = candidate.resolve()
    packet_index = packet_index.resolve()
    if not run_id.strip():
        raise ValueError("run_id is required")
    index = _load(packet_index)
    if not isinstance(index, dict) or index.get("schema") != "mcm-section-drafting-packet-index/v1" or index.get("status") != "pass":
        raise ValueError("packet index must be passing")
    index_source = index.get("source") if isinstance(index.get("source"), dict) else {}
    if index_source.get("sha256") != sha256_file(source):
        raise ValueError("packet index is not bound to the frozen source")
    source_scopes = _scopes(source)
    candidate_scopes = _scopes(candidate)
    if _signature(source_scopes) != _signature(candidate_scopes):
        raise ValueError("candidate section order or target metadata changed")
    records = index.get("packets") if isinstance(index.get("packets"), list) else []
    packet_records = {
        str(item.get("target_id")): item
        for item in records
        if isinstance(item, dict) and item.get("target_id")
    }
    if set(source_scopes) != set(candidate_scopes) or set(source_scopes) != set(packet_records):
        raise ValueError("source, candidate, and packet target sets do not match")
    for target_id in source_scopes:
        for field in ("title", "role", "question_id"):
            if source_scopes[target_id][field] != candidate_scopes[target_id][field]:
                raise ValueError(f"candidate target metadata changed: {target_id} {field}")
        packet_path = Path(str(packet_records[target_id].get("path", ""))).resolve()
        if not packet_path.is_file() or sha256_file(packet_path) != packet_records[target_id].get("sha256"):
            raise ValueError(f"packet file is missing or drifted: {target_id}")
    sections = []
    for target_id in source_scopes:
        source_section = source_scopes[target_id]
        candidate_section = candidate_scopes[target_id]
        packet = packet_records[target_id]
        disposition = "retained" if source_section["sha256"] == candidate_section["sha256"] else "generated"
        sections.append({
            "target_id": target_id,
            "title": source_section["title"],
            "role": source_section["role"],
            "question_id": source_section["question_id"],
            "packet": {
                "path": str(Path(str(packet["path"])).resolve()),
                "sha256": packet.get("sha256"),
                "bytes": Path(str(packet["path"])).resolve().stat().st_size,
            },
            "source_section": {
                "tex_sha256": source_section["sha256"], "tex_chars": source_section["chars"],
                "visible_sha256": source_section["visible_sha256"], "visible_chars": source_section["visible_chars"],
            },
            "candidate_section": {
                "tex_sha256": candidate_section["sha256"], "tex_chars": candidate_section["chars"],
                "visible_sha256": candidate_section["visible_sha256"], "visible_chars": candidate_section["visible_chars"],
            },
            "disposition": disposition,
        })
    return {
        "schema": SCHEMA,
        "status": "pass",
        "execution": {
            "mode": "section_lineage_declared",
            "run_id": run_id.strip(),
            "author_kind": author_kind,
            "consumption_proven": False,
        },
        "source": _locked(source),
        "candidate": _locked(candidate),
        "packet_index": _locked(packet_index),
        "target_signature": _signature(source_scopes),
        "sections": sections,
        "claims": {
            "packet_to_candidate_hashes_bound": True,
            "model_reading_proven": False,
            "hidden_chain_of_thought_requested": False,
            "human_naturalness_proven": False,
        },
        "interpretation": (
            "This receipt records declared section lineage and content hashes. "
            "It does not prove that a model read a packet or expose private reasoning."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--packet-index", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--author-kind", choices=("model", "human", "mixed"), default="model")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = build(args.source, args.candidate, args.packet_index, args.run_id, args.author_kind)
        output = args.output.resolve()
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.format == "json":
            print(json.dumps({"schema": SCHEMA, "status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"SECTION DRAFTING USAGE FAIL: {exc}")
        return 1
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SECTION DRAFTING USAGE PASS sections={len(report['sections'])} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
