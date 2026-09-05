#!/usr/bin/env python3
"""Regression tests for legacy holdout review-transport addenda."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from adapter_core import sha256_file, write_json
from attach_legacy_blind_review import attach, audit
from blind_pair_evaluation import prepare


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def record(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-legacy-review-") as temp:
        root = Path(temp)
        spec = root / "spec.json"
        spec.write_text('{"schema":"fixture-spec"}\n', encoding="utf-8")
        pairs = root / "pairs.json"
        pairs.write_text(json.dumps({
            "schema": "aigc-blind-pairs/v1",
            "pairs": [{"id": "p1", "variants": [
                {"id": "source", "text": "基线只能说明总体趋势。"},
                {"id": "candidate", "text": "残差随边界变量成组偏移，因此补入分层项。"},
            ]}],
        }, ensure_ascii=False), encoding="utf-8")
        blind = root / "blind"
        prepared = prepare(pairs, blind, 9)
        rule = root / "historical-rule.md"
        rule.write_text("historical rule v1\n", encoding="utf-8")
        seal = root / "holdout-seal.json"
        write_json(seal, {
            "schema": "aigc-tex-blind-holdout-seal/v1",
            "state": "SEALED_UNSCORED",
            "release_id": "historical-v1",
            "pair_count": 1,
            "artifacts": {
                "spec": record(spec),
                "pairs": record(pairs),
                "key": record(Path(prepared["key"])),
                "packet": record(Path(prepared["packet"])),
                "ratings_template": record(Path(prepared["ratings_template"])),
            },
            "rule_snapshot": [record(rule)],
            "release_requirements": {"model_ratings_are_diagnostic_only": True},
        })
        rule.write_text("historical rule changed later\n", encoding="utf-8")
        addendum = root / "review-addendum.json"
        attached = attach(seal, addendum)
        require(
            attached["status"] == "pass" and attached["rule_drift"] == 1,
            "rule drift prevented an honest transport-only addendum",
            attached,
        )
        result = audit(addendum)
        require(
            result["status"] == "pass" and result["current_rule_drift"] == 1,
            "fresh legacy review addendum failed audit",
            result,
        )
        payload = json.loads(addendum.read_text(encoding="utf-8"))
        require(
            payload["claims"]["current_release_validation"] is False
            and payload["historical_rule_snapshot"][0]["sha256"] != sha256_file(rule),
            "addendum relabelled current rules as historical generation evidence",
            payload,
        )
        page = Path(payload["review_page"]["path"])
        page.write_text(page.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        drift = audit(addendum)
        require(
            drift["status"] == "fail"
            and any(item["code"] == "LEGACY_FILE_DRIFT" for item in drift["findings"]),
            "review-page drift was not rejected",
            drift,
        )
    print("PASS: legacy holdouts gain current review transport without rewriting historical rule evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
