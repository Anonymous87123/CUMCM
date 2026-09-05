#!/usr/bin/env python3
"""Regression tests for offline blind-review rendering and rating merge."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile

from blind_pair_evaluation import prepare, score
from merge_style_benchmark_ratings import audit_merge_report, merge_ratings
from render_style_benchmark_review import CSV_FIELDS, audit_bundle, load_packet


def require(condition: bool, message: str, payload: object = None) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def write_rating(path: Path, pair_ids: list[str], rater: str, kind: str = "human") -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for pair_id in pair_ids:
            writer.writerow({
                "pair_id": pair_id,
                "rater_id": rater,
                "rater_kind": kind,
                "naturalness": "A",
                "judgment_trajectory": "B",
                "specificity": "TIE",
                "content_density": "A",
                "semantic_fidelity": "TIE",
                "notes": "独立记录",
            })


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-review-page-") as temp:
        root = Path(temp)
        pairs_path = root / "pairs.json"
        pairs_path.write_text(json.dumps({
            "schema": "aigc-blind-pairs/v1",
            "pairs": [
                {"id": "p1", "variants": [
                    {"id": "source", "text": "现象出现后再核对边界。"},
                    {"id": "candidate", "text": "</script><script>window.leak=true</script>"},
                ]},
                {"id": "p2", "variants": [
                    {"id": "source", "text": "基线可以解释总体趋势。"},
                    {"id": "candidate", "text": "分层残差仍随水深偏移，因此补入边界项。"},
                ]},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        prep = prepare(pairs_path, root / "run", 20260818)
        packet = load_packet(Path(prep["packet"]))
        pair_ids = [pair["pair_id"] for pair in packet["pairs"]]
        page = Path(prep["review_page"]).read_text(encoding="utf-8")
        require(page.count("<script>") == 1, "visible passage broke out of the embedded packet", None)
        require("window.leak=true" not in page, "visible passage was embedded as executable markup", None)
        require("candidate_id" not in page and "pair-map" not in page, "review page leaked provenance", None)
        require('/[",\\r\\n]/.test(text)' in page, "CSV escaping regex was corrupted by template rendering", None)
        require('lines.join("\\r\\n")' in page, "CSV line ending literal was corrupted", None)
        bundle = audit_bundle(Path(prep["review_bundle"]))
        require(bundle["status"] == "pass", "fresh review bundle failed audit", bundle)

        r1 = root / "r1.csv"
        r2 = root / "r2.csv"
        write_rating(r1, pair_ids, "R1")
        write_rating(r2, pair_ids, "R2")
        merged_path = root / "ratings-merged.csv"
        merge_report_path = root / "ratings-merge.json"
        merged = merge_ratings(Path(prep["packet"]), [r1, r2], merged_path, merge_report_path)
        require(
            merged["rows"] == 4
            and merged["raters"] == ["R1", "R2"]
            and merged["formal_coverage_proven"] is False,
            "valid ratings did not merge or the merge overclaimed formal coverage",
            merged,
        )
        merge_audit = audit_merge_report(merge_report_path)
        require(merge_audit["status"] == "pass", "fresh merge report failed audit", merge_audit)
        scored = score(Path(prep["key"]), merged_path)
        require(scored["status"] == "pass" and scored["formal_human_ready"], "merged ratings lack formal coverage", scored)

        forged_report = root / "ratings-merge-forged.json"
        forged = json.loads(merge_report_path.read_text(encoding="utf-8"))
        forged["output"]["sha256"] = "0" * 64
        forged_report.write_text(json.dumps(forged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        forged_audit = audit_merge_report(forged_report)
        require(
            forged_audit["status"] == "fail"
            and any(item["code"] == "MERGE_FILE_DRIFT" for item in forged_audit["findings"]),
            "forged merge output hash was accepted",
            forged_audit,
        )

        duplicate = root / "duplicate.csv"
        write_rating(duplicate, pair_ids, "R1")
        try:
            merge_ratings(Path(prep["packet"]), [r1, duplicate], root / "duplicate-out.csv")
        except ValueError as exc:
            require("reused" in str(exc), "duplicate reviewer failed for the wrong reason", str(exc))
        else:
            raise AssertionError("duplicate reviewer was accepted")

        incomplete = root / "incomplete.csv"
        write_rating(incomplete, pair_ids[:1], "R3")
        try:
            merge_ratings(Path(prep["packet"]), [r1, incomplete], root / "incomplete-out.csv")
        except ValueError as exc:
            require("every packet pair" in str(exc), "incomplete coverage failed for the wrong reason", str(exc))
        else:
            raise AssertionError("incomplete rating file was accepted")

        model = root / "model.csv"
        write_rating(model, pair_ids, "M1", "model")
        try:
            merge_ratings(Path(prep["packet"]), [r1, model], root / "model-out.csv")
        except ValueError as exc:
            require("rater_kind=human" in str(exc), "model rating failed for the wrong reason", str(exc))
        else:
            raise AssertionError("model rating was accepted as formal human evidence")

        page_path = Path(prep["review_page"])
        frozen = page_path.read_text(encoding="utf-8")
        page_path.write_text(frozen + "\n", encoding="utf-8")
        drift = audit_bundle(Path(prep["review_bundle"]))
        require(
            drift["status"] == "fail" and any(item["code"] == "REVIEW_FILE_DRIFT" for item in drift["findings"]),
            "review-page drift was not rejected",
            drift,
        )

        leaked_packet = root / "leaked-packet.json"
        leaked = json.loads(Path(prep["packet"]).read_text(encoding="utf-8"))
        leaked["provider"] = "hidden-provider"
        leaked_packet.write_text(json.dumps(leaked, ensure_ascii=False), encoding="utf-8")
        try:
            load_packet(leaked_packet)
        except ValueError as exc:
            require("non-review fields" in str(exc), "provenance field failed for the wrong reason", str(exc))
        else:
            raise AssertionError("packet with provenance fields was accepted")
    print("PASS: offline blind review is provenance-free, drift-bound, and mergeable only as complete human ratings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
