#!/usr/bin/env python3
"""Positive and negative tests for blind pair preparation and scoring."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile

from blind_pair_evaluation import prepare, score


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-blind-pair-") as temp:
        root = Path(temp)
        pairs_path = root / "pairs.json"
        pairs_path.write_text(json.dumps({
            "schema": "aigc-blind-pairs/v1",
            "pairs": [
                {"id": "p1", "variants": [
                    {"id": "source", "text": "基线模型能够拟合趋势。"},
                    {"id": "candidate", "text": "先按基线拟合后，残差仍随边界变量成组偏移。"},
                ]},
                {"id": "p2", "variants": [
                    {"id": "source", "text": "调整参数后结果发生变化。"},
                    {"id": "candidate", "text": "参数跨过阈值后，首次触发对象由 A 换成了 B。"},
                ]},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        prep = prepare(pairs_path, root / "run", 2026)
        packet_text = Path(prep["packet"]).read_text(encoding="utf-8")
        require('"source"' not in packet_text and '"candidate"' not in packet_text, "packet leaked provenance", prep)
        key = json.loads(Path(prep["key"]).read_text(encoding="utf-8"))
        ratings = root / "ratings.csv"
        with ratings.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "pair_id", "rater_id", "rater_kind", "naturalness", "judgment_trajectory",
                "specificity", "content_density", "semantic_fidelity", "notes",
            ))
            writer.writeheader()
            for pair in key["pairs"]:
                chosen = "A" if pair["A"] == "candidate" else "B"
                for rater in ("R1", "R2"):
                    writer.writerow({
                        "pair_id": pair["pair_id"], "rater_id": rater,
                        "rater_kind": "human",
                        "naturalness": chosen, "judgment_trajectory": chosen,
                        "specificity": chosen, "content_density": chosen,
                        "semantic_fidelity": "TIE",
                        "notes": "候选把变化对象写得更具体" if rater == "R1" else "",
                    })
        result = score(Path(prep["key"]), ratings)
        require(result["status"] == "pass", "valid ratings failed", result)
        require(result["formal_human_ready"] is True, "two human raters did not produce formal coverage", result)
        require(result["counts"]["naturalness"].get("candidate") == 4, "candidate preferences were mapped incorrectly", result)
        require(
            result["per_pair_counts"]["p1"]["naturalness"].get("candidate") == 2
            and len(result["rater_notes"]) == 2,
            "per-pair votes or rater notes were not retained",
            result,
        )

        model_ratings = root / "model-ratings.csv"
        with model_ratings.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "pair_id", "rater_id", "rater_kind", "naturalness", "judgment_trajectory",
                "specificity", "content_density", "semantic_fidelity", "notes",
            ))
            writer.writeheader()
            for pair in key["pairs"]:
                for rater in ("M1", "M2"):
                    writer.writerow({
                        "pair_id": pair["pair_id"], "rater_id": rater, "rater_kind": "model",
                        "naturalness": "TIE", "judgment_trajectory": "TIE",
                        "specificity": "TIE", "content_density": "TIE",
                        "semantic_fidelity": "TIE", "notes": "diagnostic model probe",
                    })
        model_result = score(Path(prep["key"]), model_ratings)
        require(
            model_result["status"] == "pass"
            and model_result["formal_human_ready"] is False
            and all(value == 0 for value in model_result["human_coverage"].values())
            and all(value == 2 for value in model_result["model_coverage"].values()),
            "model probes were mistaken for human clearance", model_result,
        )

        def write_uniform(path: Path, votes: tuple[tuple[str, str], ...]) -> None:
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=(
                    "pair_id", "rater_id", "rater_kind", "naturalness", "judgment_trajectory",
                    "specificity", "content_density", "semantic_fidelity", "notes",
                ))
                writer.writeheader()
                for pair in key["pairs"]:
                    for rater_id, choice in votes:
                        writer.writerow({
                            "pair_id": pair["pair_id"], "rater_id": rater_id, "rater_kind": "human",
                            "naturalness": choice, "judgment_trajectory": choice,
                            "specificity": choice, "content_density": choice,
                            "semantic_fidelity": choice, "notes": "",
                        })

        skipped = root / "skipped.csv"
        write_uniform(skipped, (("R1", "SKIP"), ("R2", "SKIP")))
        skipped_result = score(Path(prep["key"]), skipped)
        require(
            skipped_result["status"] == "pass"
            and skipped_result["formal_human_ready"] is False
            and all(value == 0 for value in skipped_result["effective_human_coverage"].values())
            and any(
                item["code"] == "DIMENSION_LACKS_TWO_EFFECTIVE_HUMAN_VOTES"
                for item in skipped_result["findings"]
            ),
            "two all-SKIP rows were accepted as formal human evidence", skipped_result,
        )

        split = root / "split.csv"
        write_uniform(split, (("R1", "A"), ("R2", "B")))
        split_result = score(Path(prep["key"]), split)
        require(
            split_result["status"] == "pass"
            and split_result["formal_human_ready"] is False
            and split_result["unresolved_human_dimensions"] == len(key["pairs"]) * 5
            and any(item["code"] == "DIMENSION_NO_HUMAN_MAJORITY" for item in split_result["findings"]),
            "two opposing human ratings were treated as resolved", split_result,
        )

        tiebreak = root / "tiebreak.csv"
        write_uniform(tiebreak, (("R1", "A"), ("R2", "B"), ("R3", "A")))
        tiebreak_result = score(Path(prep["key"]), tiebreak)
        require(
            tiebreak_result["status"] == "pass"
            and tiebreak_result["formal_human_ready"] is True
            and tiebreak_result["unresolved_human_dimensions"] == 0
            and tiebreak_result["pairwise_exact_agreement"] == 0.3333,
            "an appended third human rating did not resolve the split without erasing disagreement",
            tiebreak_result,
        )

        packet_path = Path(prep["packet"])
        frozen_packet = packet_path.read_text(encoding="utf-8")
        packet_path.write_text(frozen_packet + "\n", encoding="utf-8")
        packet_drift = score(Path(prep["key"]), ratings)
        require(
            packet_drift["status"] == "fail"
            and any(item["code"] == "PACKET_DRIFT" for item in packet_drift["findings"]),
            "packet drift was not rejected", packet_drift,
        )
        packet_path.write_text(frozen_packet, encoding="utf-8")

        invalid = root / "invalid.csv"
        invalid.write_text(
            "pair_id,rater_id,naturalness,judgment_trajectory,specificity,content_density,semantic_fidelity\n"
            "unknown,R1,A,A,A,A,A\n",
            encoding="utf-8",
        )
        rejected = score(Path(prep["key"]), invalid)
        require(
            rejected["status"] == "fail" and any(item["code"] == "UNKNOWN_PAIR" for item in rejected["findings"]),
            "unknown pair was not rejected", rejected,
        )
    print("PASS: blind scoring separates model probes, SKIP rows, unresolved splits, and majority-backed human evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
