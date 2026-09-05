#!/usr/bin/env python3
"""Prepare and score provenance-hidden paired writing evaluations.

Public interface:
    python blind_pair_evaluation.py prepare pairs.json --output-dir RUN --seed 2026
    python blind_pair_evaluation.py score evaluation-key.json ratings.csv --format text|json
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import random

from adapter_core import sha256_file, write_json
from merge_style_benchmark_ratings import audit_merge_report
from render_style_benchmark_review import render_review


PAIR_SCHEMA = "aigc-blind-pairs/v1"
PACKET_SCHEMA = "aigc-blind-packet/v1"
KEY_SCHEMA = "aigc-blind-key/v1"
DIMENSIONS = (
    "naturalness",
    "judgment_trajectory",
    "specificity",
    "content_density",
    "semantic_fidelity",
)
CHOICES = {"A", "B", "TIE", "SKIP"}
RATER_KINDS = {"human", "model"}


def prepare(pairs_path: Path, output_dir: Path, seed: int) -> dict:
    payload = json.loads(pairs_path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != PAIR_SCHEMA:
        raise ValueError(f"expected schema {PAIR_SCHEMA}")
    pairs = payload.get("pairs", [])
    if not pairs:
        raise ValueError("at least one pair is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    packet_pairs = []
    key_pairs = []
    seen: set[str] = set()
    for pair in pairs:
        pair_id = str(pair.get("id", "")).strip()
        variants = pair.get("variants", [])
        if not pair_id or pair_id in seen or len(variants) != 2:
            raise ValueError("each pair needs a unique id and exactly two variants")
        if any(not str(item.get("id", "")).strip() or not str(item.get("text", "")).strip() for item in variants):
            raise ValueError(f"pair {pair_id} has an empty variant id or text")
        if variants[0]["id"] == variants[1]["id"]:
            raise ValueError(f"pair {pair_id} reuses a variant id")
        seen.add(pair_id)
        order = list(variants)
        rng.shuffle(order)
        packet_pairs.append({
            "pair_id": pair_id,
            "A": order[0]["text"],
            "B": order[1]["text"],
        })
        key_pairs.append({
            "pair_id": pair_id,
            "A": order[0]["id"],
            "B": order[1]["id"],
        })
    packet = {
        "schema": PACKET_SCHEMA,
        "instructions": "Judge only the visible passages. Do not infer authorship or use an AI detector.",
        "dimensions": list(DIMENSIONS),
        "choices": ["A", "B", "TIE", "SKIP"],
        "pairs": packet_pairs,
    }
    key = {"schema": KEY_SCHEMA, "seed": seed, "dimensions": list(DIMENSIONS), "pairs": key_pairs}
    packet_path = output_dir / "evaluation-packet.json"
    key_path = output_dir / "evaluation-key.json"
    ratings_path = output_dir / "ratings-template.csv"
    write_json(packet_path, packet)
    key["packet_path"] = str(packet_path.resolve())
    key["packet_sha256"] = sha256_file(packet_path)
    key["source_pairs_path"] = str(pairs_path.resolve())
    key["source_pairs_sha256"] = sha256_file(pairs_path)
    write_json(key_path, key)
    with ratings_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("pair_id", "rater_id", "rater_kind", *DIMENSIONS, "notes"),
        )
        writer.writeheader()
        for pair in packet_pairs:
            writer.writerow({"pair_id": pair["pair_id"]})
    review_path = output_dir / "review.html"
    review_bundle_path = output_dir / "review-bundle.json"
    review = render_review(packet_path, review_path, ratings_path, review_bundle_path)
    return {
        "schema": "aigc-blind-prepare-report/v1",
        "status": "pass",
        "pairs": len(packet_pairs),
        "packet": str(packet_path.resolve()),
        "key": str(key_path.resolve()),
        "ratings_template": str(ratings_path.resolve()),
        "review_page": review["review_page"],
        "review_bundle": review["bundle"],
    }


def score(
    key_path: Path,
    ratings_path: Path,
    merge_report_path: Path | None = None,
) -> dict:
    key_path = key_path.resolve()
    ratings_path = ratings_path.resolve()
    key = json.loads(key_path.read_text(encoding="utf-8-sig"))
    findings: list[dict] = []
    if key.get("schema") != KEY_SCHEMA:
        findings.append({"severity": "error", "code": "KEY_SCHEMA_MISMATCH"})
    packet_path = Path(key.get("packet_path", ""))
    if not packet_path.is_file() or sha256_file(packet_path) != key.get("packet_sha256"):
        findings.append({"severity": "error", "code": "PACKET_DRIFT", "path": str(packet_path)})
    source_pairs_path = Path(key.get("source_pairs_path", ""))
    if not source_pairs_path.is_file() or sha256_file(source_pairs_path) != key.get("source_pairs_sha256"):
        findings.append({"severity": "error", "code": "SOURCE_PAIRS_DRIFT", "path": str(source_pairs_path)})
    mappings = {item["pair_id"]: item for item in key.get("pairs", [])}
    rows = []
    with ratings_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = {"pair_id", "rater_id", *DIMENSIONS} - set(reader.fieldnames or [])
        if missing_columns:
            findings.append({
                "severity": "error", "code": "RATING_COLUMNS_MISSING",
                "columns": sorted(missing_columns),
            })
        rows = list(reader)

    counts = {dimension: {} for dimension in DIMENSIONS}
    per_pair_counts = {
        pair_id: {dimension: {} for dimension in DIMENSIONS}
        for pair_id in mappings
    }
    rater_notes: list[dict] = []
    pair_raters = {pair_id: set() for pair_id in mappings}
    pair_raters_by_kind = {
        pair_id: {kind: set() for kind in (*sorted(RATER_KINDS), "unspecified")}
        for pair_id in mappings
    }
    effective_human_raters = {pair_id: set() for pair_id in mappings}
    human_votes = {
        pair_id: {dimension: [] for dimension in DIMENSIONS}
        for pair_id in mappings
    }
    counts_by_rater_kind: dict[str, dict[str, dict[str, int]]] = {}
    seen_rows: set[tuple[str, str]] = set()
    has_rater_kind_column = "rater_kind" in set(reader.fieldnames or [])
    if not has_rater_kind_column:
        findings.append({"severity": "warning", "code": "RATER_KIND_COLUMN_MISSING"})
    for row_number, row in enumerate(rows, start=2):
        pair_id = str(row.get("pair_id", "")).strip()
        rater_id = str(row.get("rater_id", "")).strip()
        if pair_id not in mappings:
            findings.append({"severity": "error", "code": "UNKNOWN_PAIR", "row": row_number, "pair_id": pair_id})
            continue
        if not rater_id:
            findings.append({"severity": "error", "code": "RATER_ID_MISSING", "row": row_number})
            continue
        rater_kind = str(row.get("rater_kind", "")).strip().casefold()
        if not rater_kind:
            rater_kind = "unspecified"
        elif rater_kind not in RATER_KINDS:
            findings.append({
                "severity": "error", "code": "RATER_KIND_INVALID",
                "row": row_number, "rater_kind": rater_kind,
            })
            continue
        row_key = (pair_id, rater_id)
        if row_key in seen_rows:
            findings.append({"severity": "error", "code": "DUPLICATE_RATING", "row": row_number, "pair_id": pair_id, "rater_id": rater_id})
            continue
        seen_rows.add(row_key)
        pair_raters[pair_id].add(rater_id)
        pair_raters_by_kind[pair_id][rater_kind].add(rater_id)
        kind_counts = counts_by_rater_kind.setdefault(
            rater_kind, {dimension: {} for dimension in DIMENSIONS}
        )
        note = str(row.get("notes", "")).strip()
        if note:
            rater_notes.append({"pair_id": pair_id, "rater_id": rater_id, "rater_kind": rater_kind, "text": note})
        human_row_effective = rater_kind == "human"
        for dimension in DIMENSIONS:
            choice = str(row.get(dimension, "")).strip().upper()
            if choice not in CHOICES:
                findings.append({
                    "severity": "error", "code": "INVALID_CHOICE", "row": row_number,
                    "dimension": dimension, "choice": choice,
                })
                human_row_effective = False
                continue
            winner = choice if choice in {"TIE", "SKIP"} else mappings[pair_id][choice]
            counts[dimension][winner] = counts[dimension].get(winner, 0) + 1
            kind_counts[dimension][winner] = kind_counts[dimension].get(winner, 0) + 1
            pair_counts = per_pair_counts[pair_id][dimension]
            pair_counts[winner] = pair_counts.get(winner, 0) + 1
            if rater_kind == "human":
                if choice == "SKIP":
                    human_row_effective = False
                else:
                    human_votes[pair_id][dimension].append({"rater_id": rater_id, "vote": winner})
        if human_row_effective:
            effective_human_raters[pair_id].add(rater_id)

    for pair_id, raters in pair_raters.items():
        if not raters:
            findings.append({"severity": "error", "code": "PAIR_UNRATED", "pair_id": pair_id})
        elif len(raters) < 2:
            findings.append({"severity": "warning", "code": "PAIR_HAS_ONE_RATER", "pair_id": pair_id})
        if len(pair_raters_by_kind[pair_id]["human"]) < 2:
            findings.append({
                "severity": "warning", "code": "PAIR_LACKS_TWO_HUMAN_RATERS",
                "pair_id": pair_id,
                "human_raters": len(pair_raters_by_kind[pair_id]["human"]),
            })
    human_decisions: dict[str, dict[str, dict]] = {}
    agreement_pairs = 0
    agreement_pairs_matching = 0
    unresolved_dimensions = 0
    for pair_id, dimensions in human_votes.items():
        human_decisions[pair_id] = {}
        declared_humans = len(pair_raters_by_kind[pair_id]["human"])
        for dimension, votes in dimensions.items():
            vote_counts = Counter(str(item["vote"]) for item in votes)
            effective_votes = len(votes)
            matching_pairs = sum(count * (count - 1) // 2 for count in vote_counts.values())
            possible_pairs = effective_votes * (effective_votes - 1) // 2
            agreement_pairs_matching += matching_pairs
            agreement_pairs += possible_pairs
            leader = None
            majority = False
            if vote_counts:
                top = max(vote_counts.values())
                leaders = [choice for choice, count in vote_counts.items() if count == top]
                majority = len(leaders) == 1 and top * 2 > effective_votes
                leader = leaders[0] if majority else None
            if declared_humans >= 2 and effective_votes < 2:
                unresolved_dimensions += 1
                findings.append({
                    "severity": "warning",
                    "code": "DIMENSION_LACKS_TWO_EFFECTIVE_HUMAN_VOTES",
                    "pair_id": pair_id,
                    "dimension": dimension,
                    "effective_votes": effective_votes,
                })
            elif effective_votes >= 2 and not majority:
                unresolved_dimensions += 1
                findings.append({
                    "severity": "warning",
                    "code": "DIMENSION_NO_HUMAN_MAJORITY",
                    "pair_id": pair_id,
                    "dimension": dimension,
                    "vote_counts": dict(sorted(vote_counts.items())),
                    "required_action": "append an independent human tiebreak rating; do not overwrite prior rows",
                })
            human_decisions[pair_id][dimension] = {
                "effective_votes": effective_votes,
                "vote_counts": dict(sorted(vote_counts.items())),
                "majority_ready": majority,
                "decision": leader,
            }
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    variants = sorted({
        str(mapping[side])
        for mapping in mappings.values()
        for side in ("A", "B")
    })
    human_coverage = {
        pair_id: len(kinds["human"])
        for pair_id, kinds in pair_raters_by_kind.items()
    }
    effective_human_coverage = {
        pair_id: len(raters)
        for pair_id, raters in effective_human_raters.items()
    }
    model_coverage = {
        pair_id: len(kinds["model"])
        for pair_id, kinds in pair_raters_by_kind.items()
    }
    unspecified_coverage = {
        pair_id: len(kinds["unspecified"])
        for pair_id, kinds in pair_raters_by_kind.items()
    }
    formal_human_ready = (
        errors == 0
        and all(value >= 2 for value in effective_human_coverage.values())
        and unresolved_dimensions == 0
    )
    pairwise_agreement = (
        round(agreement_pairs_matching / agreement_pairs, 4)
        if agreement_pairs else None
    )
    evidence = {
        "key": {"path": str(key_path), "sha256": sha256_file(key_path)},
        "ratings": {"path": str(ratings_path), "sha256": sha256_file(ratings_path)},
        "packet": {"path": str(packet_path.resolve()), "sha256": key.get("packet_sha256")},
        "source_pairs": {"path": str(source_pairs_path.resolve()), "sha256": key.get("source_pairs_sha256")},
    }
    if merge_report_path is not None:
        merge_report_path = merge_report_path.resolve()
        merge_audit = audit_merge_report(merge_report_path)
        if merge_audit.get("status") != "pass":
            findings.append({
                "severity": "error",
                "code": "MERGE_REPORT_INVALID",
                "merge_findings": merge_audit.get("findings", []),
            })
        else:
            merge_payload = json.loads(merge_report_path.read_text(encoding="utf-8-sig"))
            if Path(str(merge_payload.get("output", {}).get("path", ""))).resolve() != ratings_path:
                findings.append({"severity": "error", "code": "MERGE_REPORT_RATINGS_MISMATCH"})
            evidence["merge_report"] = {
                "path": str(merge_report_path),
                "sha256": sha256_file(merge_report_path),
            }
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    formal_human_ready = formal_human_ready and errors == 0
    return {
        "schema": "aigc-blind-score/v1",
        "scoring_protocol": "aigc-blind-scoring/v2",
        "status": "pass" if errors == 0 else "fail",
        "pairs": len(mappings),
        "ratings": len(seen_rows),
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "counts_by_rater_kind": counts_by_rater_kind,
        "per_pair_counts": per_pair_counts,
        "rater_notes": rater_notes,
        "variants": variants,
        "coverage": {pair_id: len(raters) for pair_id, raters in pair_raters.items()},
        "human_coverage": human_coverage,
        "effective_human_coverage": effective_human_coverage,
        "human_decisions": human_decisions,
        "unresolved_human_dimensions": unresolved_dimensions,
        "pairwise_exact_agreement": pairwise_agreement,
        "model_coverage": model_coverage,
        "unspecified_coverage": unspecified_coverage,
        "formal_human_ready": formal_human_ready,
        "evaluation_level": "FORMAL_HUMAN_READY" if formal_human_ready else "PROBE_OR_HUMAN_PENDING",
        "evidence": evidence,
        "findings": findings,
        "interpretation": (
            "Counts report preferences from the declared rater kinds. Formal release requires at least two "
            "effective human ratings and a strict human majority on every pair-dimension; SKIP is not an "
            "effective vote, and unresolved disagreement requires an appended independent tiebreak rating. "
            "No count proves authorship or detector performance."
        ),
    }


def _print(report: dict, fmt: str, label: str) -> None:
    if fmt == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"{label} {report['status'].upper()} pairs={report.get('pairs', 0)}")
    if "ratings" in report:
        print(f"ratings={report['ratings']} errors={report['errors']} warnings={report['warnings']}")
        for dimension, counts in report["counts"].items():
            summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
            print(f"{dimension}: {summary}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("pairs", type=Path)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument("--seed", type=int, required=True)
    prepare_parser.add_argument("--format", choices=("text", "json"), default="text")
    score_parser = sub.add_parser("score")
    score_parser.add_argument("key", type=Path)
    score_parser.add_argument("ratings", type=Path)
    score_parser.add_argument("--merge-report", type=Path)
    score_parser.add_argument("--output", type=Path)
    score_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.command == "prepare":
        report = prepare(args.pairs, args.output_dir, args.seed)
        _print(report, args.format, "BLIND PREPARE")
        return 0
    report = score(args.key, args.ratings, args.merge_report)
    if args.output:
        write_json(args.output.resolve(), report)
    _print(report, args.format, "BLIND SCORE")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
