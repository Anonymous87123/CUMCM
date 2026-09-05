from __future__ import annotations

import argparse
import csv
import json
import ntpath
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCENES = {"course_notes", "modeling_engineering", "research_journal", "not_applicable"}


def normalize_path(value: str) -> str:
    normalized = ntpath.normpath(value.replace("/", "\\"))
    if normalized.startswith("\\\\?\\"):
        normalized = normalized[4:]
    return normalized.casefold()


def contains_any(path: str, needles: Iterable[str]) -> bool:
    return any(needle.casefold() in path for needle in needles)


def load_taxonomy(path: Path) -> dict[str, Any]:
    taxonomy = json.loads(path.read_text(encoding="utf-8"))
    labels = set(taxonomy["scene_labels"])
    if labels != SCENES:
        raise ValueError(f"taxonomy scenes {sorted(labels)} do not match {sorted(SCENES)}")
    return taxonomy


def load_explicit_assistant_paths(path: Path | None) -> set[str]:
    if path is None:
        return set()
    result: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"confidence": "explicit_assistant_output"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            mentioned = record.get("mentioned_path")
            if mentioned:
                result.add(normalize_path(str(mentioned)))
    return result


def classify_path(path: str, taxonomy: dict[str, Any]) -> dict[str, str]:
    normalized = normalize_path(path)

    for rule in taxonomy["exclusion_rules"]:
        if contains_any(normalized, rule["contains"]):
            return {
                "scene": "not_applicable",
                "eligibility": rule["eligibility"],
                "rule_id": rule["id"],
                "classification_basis": "curated exclusion rule",
                "note": rule["note"],
            }

    for rule in taxonomy["override_rules"]:
        if contains_any(normalized, rule["contains"]):
            return {
                "scene": rule["scene"],
                "eligibility": rule["eligibility"],
                "rule_id": rule["id"],
                "classification_basis": "manual corpus override",
                "note": rule["note"],
            }

    for rule in taxonomy["scene_rules"]:
        if contains_any(normalized, rule["contains"]):
            return {
                "scene": rule["scene"],
                "eligibility": "target",
                "rule_id": rule["id"],
                "classification_basis": "curated folder family",
                "note": rule["note"],
            }

    return {
        "scene": "not_applicable",
        "eligibility": "unresolved_non_target",
        "rule_id": "UNRESOLVED",
        "classification_basis": "no curated academic family match",
        "note": "Retained for no-omission audit; requires manual promotion before style use.",
    }


def refine_role(row: dict[str, str], classification: dict[str, str], taxonomy: dict[str, Any]) -> str:
    normalized = normalize_path(row["path"])
    if row.get("duplicate_of"):
        return "duplicate_version"
    if classification["scene"] == "not_applicable":
        return classification["eligibility"]
    if contains_any(normalized, taxonomy["archive_markers"]):
        return "archive_or_worktree"
    if contains_any(normalized, taxonomy["non_prose_markers"]):
        return "structured_record_or_build_artifact"
    if int(row.get("han_chars") or 0) == 0:
        return "non_chinese_target_document"
    return "primary_style_candidate"


def classify_manifest(
    manifest_path: Path,
    taxonomy: dict[str, Any],
    explicit_paths: set[str],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "readable":
                continue
            classification = classify_path(row["path"], taxonomy)
            normalized = normalize_path(row["path"])
            core = normalized in explicit_paths and int(row.get("han_chars") or 0) > 0
            role = refine_role(row, classification, taxonomy)
            confidence = "manual-family-high" if classification["rule_id"].startswith(("OVR-", "SCN-")) else "audit-only"
            output.append(
                {
                    "path": row["path"],
                    "document_format": row["document_format"],
                    "han_chars": row["han_chars"],
                    "source_label": row["source_label"],
                    "sha256": row["sha256"],
                    "duplicate_of": row.get("duplicate_of", ""),
                    "scene": classification["scene"],
                    "eligibility": classification["eligibility"],
                    "evidence_role": role,
                    "rule_id": classification["rule_id"],
                    "classification_basis": classification["classification_basis"],
                    "confidence": confidence,
                    "core_207_candidate": "yes" if core else "no",
                    "manual_review_status": (
                        "manually_read_and_scene_reviewed_core"
                        if core
                        else "folder_routed_full_index"
                    ),
                    "note": classification["note"],
                }
            )
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]], taxonomy: dict[str, Any]) -> dict[str, Any]:
    scene_counts = Counter(row["scene"] for row in rows)
    role_counts = Counter(row["evidence_role"] for row in rows)
    core_counts = Counter(row["scene"] for row in rows if row["core_207_candidate"] == "yes")
    target_counts = Counter(
        row["scene"]
        for row in rows
        if row["scene"] != "not_applicable" and row["evidence_role"] == "primary_style_candidate"
    )
    unresolved = sum(row["rule_id"] == "UNRESOLVED" for row in rows)
    return {
        "taxonomy_version": taxonomy["version"],
        "readable_manifest_rows": len(rows),
        "scene_counts_all_decisions": dict(sorted(scene_counts.items())),
        "primary_chinese_style_candidates": dict(sorted(target_counts.items())),
        "core_207_scene_counts": dict(sorted(core_counts.items())),
        "evidence_role_counts": dict(sorted(role_counts.items())),
        "core_candidate_count": sum(core_counts.values()),
        "unresolved_non_target_count": unresolved,
        "invariants": {
            "all_rows_have_decision": sum(scene_counts.values()) == len(rows),
            "target_scenes_are_only_three": all(
                row["scene"] in SCENES for row in rows
            ),
            "non_target_never_primary_style_evidence": all(
                row["scene"] != "not_applicable" or row["evidence_role"] != "primary_style_candidate"
                for row in rows
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route the full academic manifest into audited writing scenes.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-readable", type=int)
    parser.add_argument("--expected-core", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    taxonomy = load_taxonomy(args.taxonomy)
    explicit_paths = load_explicit_assistant_paths(args.provenance)
    rows = classify_manifest(args.manifest, taxonomy, explicit_paths)
    summary = summarize(rows, taxonomy)

    if args.expected_readable is not None and len(rows) != args.expected_readable:
        raise SystemExit(f"expected {args.expected_readable} readable rows, found {len(rows)}")
    if args.expected_core is not None and summary["core_candidate_count"] != args.expected_core:
        raise SystemExit(
            f"expected {args.expected_core} core rows, found {summary['core_candidate_count']}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "academic_scenario_manifest.csv", rows)
    write_csv(
        args.output / "core_207_scenario_manifest.csv",
        [row for row in rows if row["core_207_candidate"] == "yes"],
    )
    (args.output / "academic_scenario_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
