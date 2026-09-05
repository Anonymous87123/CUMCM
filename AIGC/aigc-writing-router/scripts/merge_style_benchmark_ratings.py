#!/usr/bin/env python3
"""Merge independent human blind-review CSV files after strict validation.

Public interface:
    python merge_style_benchmark_ratings.py evaluation-packet.json rater-1.csv rater-2.csv \
        --output ratings-merged.csv --report ratings-merge.json --format text|json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from adapter_core import sha256_file, write_json
from render_style_benchmark_review import CHOICES, CSV_FIELDS, DIMENSIONS, load_packet


def _collect(
    packet_path: Path,
    rating_paths: list[Path],
) -> tuple[dict, list[str], set[str], list[dict[str, str]], list[dict]]:
    packet = load_packet(packet_path)
    expected_ids = [str(pair["pair_id"]) for pair in packet["pairs"]]
    expected_set = set(expected_ids)
    raters: set[str] = set()
    rows: list[dict[str, str]] = []
    inputs: list[dict] = []
    for raw_path in rating_paths:
        path = raw_path.resolve()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                raise ValueError(f"rating header mismatch: {path}")
            current = [{field: str(row.get(field, "")).strip() for field in CSV_FIELDS} for row in reader]
        ids = [row["pair_id"] for row in current]
        if len(ids) != len(expected_ids) or set(ids) != expected_set or len(set(ids)) != len(ids):
            raise ValueError(f"rating file must cover every packet pair exactly once: {path}")
        file_raters = {row["rater_id"] for row in current if row["rater_id"]}
        if len(file_raters) != 1:
            raise ValueError(f"rating file must contain exactly one non-empty rater_id: {path}")
        rater_id = next(iter(file_raters))
        if rater_id in raters:
            raise ValueError(f"rater_id is reused across files: {rater_id}")
        raters.add(rater_id)
        for row in current:
            if row["rater_id"] != rater_id:
                raise ValueError(f"rating file mixes rater ids: {path}")
            if row["rater_kind"].casefold() != "human":
                raise ValueError(f"formal rating file must declare rater_kind=human: {path}")
            row["rater_kind"] = "human"
            for dimension in DIMENSIONS:
                row[dimension] = row[dimension].upper()
                if row[dimension] not in CHOICES:
                    raise ValueError(
                        f"invalid choice {row[dimension]!r} for {row['pair_id']} {dimension}: {path}"
                    )
        by_id = {row["pair_id"]: row for row in current}
        rows.extend(by_id[pair_id] for pair_id in expected_ids)
        inputs.append({"path": str(path), "sha256": sha256_file(path), "rater_id": rater_id})
    order = {pair_id: index for index, pair_id in enumerate(expected_ids)}
    rows.sort(key=lambda row: (order[row["pair_id"]], row["rater_id"]))
    return packet, expected_ids, raters, rows, inputs


def merge_ratings(
    packet_path: Path,
    rating_paths: list[Path],
    output_path: Path,
    report_path: Path | None = None,
) -> dict:
    if len(rating_paths) < 2:
        raise ValueError("formal blind review requires at least two independent rating files")
    packet_path = packet_path.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(output_path)
    if report_path is not None:
        report_path = report_path.resolve()
        if report_path.exists():
            raise FileExistsError(report_path)
    _, expected_ids, raters, rows, inputs = _collect(packet_path, rating_paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "schema": "aigc-blind-ratings-merge/v1",
        "status": "pass",
        "packet": {"path": str(packet_path), "sha256": sha256_file(packet_path)},
        "inputs": inputs,
        "raters": sorted(raters),
        "pairs": len(expected_ids),
        "rows": len(rows),
        "output": {"path": str(output_path), "sha256": sha256_file(output_path)},
        "declared_human_files": len(raters),
        "formal_coverage_proven": False,
        "requires_effective_vote_and_majority_scoring": True,
        "interpretation": (
            "This report proves complete declared-human CSV file coverage only. The blind scorer must still "
            "exclude SKIP votes, resolve every pair-dimension by strict human majority, and report agreement; "
            "the merge does not prove independence or passage quality."
        ),
    }
    if report_path is not None:
        write_json(report_path, report)
    return report


def audit_merge_report(report_path: Path) -> dict:
    report_path = report_path.resolve()
    findings: list[dict] = []
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "aigc-blind-ratings-merge-audit/v1",
            "status": "fail",
            "errors": 1,
            "findings": [{"severity": "error", "code": "MERGE_REPORT_INVALID", "error": str(exc)}],
        }
    if payload.get("schema") != "aigc-blind-ratings-merge/v1" or payload.get("status") != "pass":
        findings.append({"severity": "error", "code": "MERGE_REPORT_SCHEMA_OR_STATUS_INVALID"})
    packet_record = payload.get("packet", {})
    output_record = payload.get("output", {})
    input_records = payload.get("inputs", [])
    locked = [("packet", packet_record), ("output", output_record)]
    locked.extend((f"input:{index}", record) for index, record in enumerate(input_records, start=1))
    for label, record in locked:
        if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
            findings.append({"severity": "error", "code": "MERGE_LOCK_INVALID", "artifact": label})
            continue
        path = Path(str(record["path"])).resolve()
        if not path.is_file():
            findings.append({"severity": "error", "code": "MERGE_FILE_MISSING", "artifact": label})
        elif sha256_file(path) != str(record["sha256"]):
            findings.append({"severity": "error", "code": "MERGE_FILE_DRIFT", "artifact": label})
    if not findings:
        try:
            packet_path = Path(str(packet_record["path"])).resolve()
            rating_paths = [Path(str(record["path"])).resolve() for record in input_records]
            _, expected_ids, raters, expected_rows, expected_inputs = _collect(packet_path, rating_paths)
            output_path = Path(str(output_record["path"])).resolve()
            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                    raise ValueError("merged ratings header mismatch")
                actual_rows = [
                    {field: str(row.get(field, "")).strip() for field in CSV_FIELDS}
                    for row in reader
                ]
            if actual_rows != expected_rows:
                findings.append({"severity": "error", "code": "MERGE_OUTPUT_ROWS_MISMATCH"})
            if payload.get("inputs") != expected_inputs:
                findings.append({"severity": "error", "code": "MERGE_INPUT_RECORDS_MISMATCH"})
            if payload.get("raters") != sorted(raters):
                findings.append({"severity": "error", "code": "MERGE_RATER_SET_MISMATCH"})
            if payload.get("pairs") != len(expected_ids) or payload.get("rows") != len(expected_rows):
                findings.append({"severity": "error", "code": "MERGE_COUNT_MISMATCH"})
            if (
                payload.get("declared_human_files") != len(raters)
                or payload.get("formal_coverage_proven") is not False
                or payload.get("requires_effective_vote_and_majority_scoring") is not True
            ):
                findings.append({"severity": "error", "code": "MERGE_CLAIMS_INVALID"})
        except (OSError, ValueError, csv.Error) as exc:
            findings.append({"severity": "error", "code": "MERGE_RECOMPUTE_FAILED", "error": str(exc)})
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "aigc-blind-ratings-merge-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "warnings": 0,
        "pairs": payload.get("pairs"),
        "raters": payload.get("raters", []),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("ratings", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = merge_ratings(args.packet, args.ratings, args.output, args.report)
    except (OSError, ValueError, csv.Error) as exc:
        if args.format == "json":
            print(json.dumps({"schema": "aigc-blind-ratings-merge/v1", "status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"BLIND RATINGS MERGE FAIL: {exc}")
        return 1
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"BLIND RATINGS MERGE PASS pairs={report['pairs']} "
            f"raters={len(report['raters'])} rows={report['rows']}"
        )
        print(f"output={report['output']['path']}")
        print(f"report={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
