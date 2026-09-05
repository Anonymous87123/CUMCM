#!/usr/bin/env python3
"""Forward tests for the locked team reasoning-review record."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_reasoning_review import audit, manuscript_hash


TEX = r"""
\section{问题一模型建立}
日销量中存在大量零值，直接把每日记录作为连续响应会掩盖同期变化。于是先按同期平均重构训练输入，
再用 Bayesian 模型刻画各时段的销售分布。
"""


def review(path: Path, reviewers: list[str]) -> dict:
    return {
        "schema": "mcm-reasoning-review/v1",
        "manuscript_sha256": manuscript_hash(path),
        "reviews": [{
            "question_id": "1",
            "reviewer": reviewer,
            "reviewer_kind": "human",
            "bridge_terms": ["大量零值", "同期平均", "Bayesian 模型"],
            "anchor_explanation": "零值会改变每日记录作为响应量的含义。",
            "transition_explanation": "先按同期平均重构输入，才与时段分布匹配。",
            "condition_change": "若零值主要来自缺报，需先补查记录而非直接汇总。",
            "decision": "pass",
        } for reviewer in reviewers],
    }


def has_code(report: dict, code: str) -> bool:
    return any(item.get("code") == code for item in report["findings"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-reasoning-review-") as temp_dir:
        root = Path(temp_dir)
        tex_path = root / "main.tex"
        good_path = root / "good.json"
        bad_path = root / "bad.json"
        tex_path.write_text(TEX, encoding="utf-8")
        good_path.write_text(json.dumps(review(tex_path, ["队长", "组员1"]), ensure_ascii=False), encoding="utf-8")
        bad_path.write_text(json.dumps(review(tex_path, ["队长"]), ensure_ascii=False), encoding="utf-8")
        good_report = audit(tex_path, good_path)
        bad_report = audit(tex_path, bad_path)
        model_payload = review(tex_path, ["队长", "组员1"])
        model_payload["reviews"][0]["reviewer_kind"] = "model"
        model_path = root / "model.json"
        model_path.write_text(json.dumps(model_payload, ensure_ascii=False), encoding="utf-8")
        model_report = audit(tex_path, model_path)
        tex_path.write_text(TEX + "\n补充一项新条件。", encoding="utf-8")
        drift_report = audit(tex_path, good_path)
    if good_report["status"] != "pass":
        print(good_report)
        return 1
    if bad_report["status"] != "fail" or not has_code(bad_report, "REASONING_REVIEWER_COUNT_INSUFFICIENT"):
        print(bad_report)
        return 1
    if model_report["status"] != "fail" or not has_code(model_report, "REASONING_REVIEWER_KIND_NOT_HUMAN"):
        print(model_report)
        return 1
    if drift_report["status"] != "fail" or not has_code(drift_report, "REASONING_REVIEW_MANUSCRIPT_HASH_MISMATCH"):
        print(drift_report)
        return 1
    print("PASS: two locked in-scope human team explanations are required for every question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
