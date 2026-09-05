#!/usr/bin/env python3
"""Tests for hash-bound TeX blind holdout sealing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from adapter_core import sha256_file
from blind_pair_evaluation import prepare
from prepare_tex_blind_pairs import build
from seal_tex_blind_holdout import seal


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-holdout-seal-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source.write_text("原始段落包含条件和结果解释。\n", encoding="utf-8")
        candidate.write_text("候选段落保留条件并重写结果解释。\n", encoding="utf-8")
        spec = root / "spec.json"
        spec_payload = {
            "schema": "aigc-tex-blind-pair-spec/v1",
            "source": {"path": str(source), "sha256": sha256_file(source)},
            "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
            "sampling": {
                "method": "seeded-section-round-robin/v1",
                "seed": 9,
                "eligible": 1,
                "selected": 1,
                "quality_labels_used": False,
                "exclude_spec": None,
            },
            "pairs": [{
                "id": "p1", "section": "分析",
                "source_lines": {"start": 1, "end": 1},
                "candidate_lines": {"start": 1, "end": 1},
            }],
        }
        spec.write_text(json.dumps(spec_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pairs = root / "pairs.json"
        build(spec, pairs)
        blind = root / "blind"
        prepare(pairs, blind, seed=9)
        rule = root / "rule.py"
        rule.write_text("RULE_VERSION = 1\n", encoding="utf-8")
        output = root / "seal.json"
        report = seal(
            spec, pairs, blind / "evaluation-key.json", blind / "evaluation-packet.json",
            blind / "ratings-template.csv", blind / "review.html", blind / "review-bundle.json",
            [rule], "test-release", output,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        require(report["status"] == "pass" and payload["state"] == "SEALED_UNSCORED", "valid seal failed", report)
        require(payload["pair_count"] == 1 and payload["rule_snapshot"][0]["sha256"] == sha256_file(rule), "seal is incomplete", payload)
        require(
            payload["scoring_protocol"] == "aigc-blind-scoring/v2"
            and payload["scoring_rule_snapshot"][0]["sha256"]
            == sha256_file(Path(__file__).with_name("blind_pair_evaluation.py")),
            "seal did not freeze the blind scoring semantics",
            payload,
        )

        packet = blind / "evaluation-packet.json"
        packet.write_text(packet.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            seal(
                spec, pairs, blind / "evaluation-key.json", packet,
                blind / "ratings-template.csv", blind / "review.html", blind / "review-bundle.json",
                [rule], "test-release", root / "bad.json",
            )
        except ValueError as exc:
            require("packet" in str(exc), "packet drift raised the wrong error", str(exc))
        else:
            raise AssertionError("packet drift passed")

    print("PASS: holdout sealing binds every blind artifact and the frozen rule snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
