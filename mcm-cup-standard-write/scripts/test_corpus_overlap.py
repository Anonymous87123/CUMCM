#!/usr/bin/env python3
"""Forward tests for literal CUMCM-corpus overlap review."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_corpus_overlap import audit


SOURCE_TEXT = "日销量中存在大量零值直接把每日记录作为连续响应会掩盖同期变化"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-corpus-overlap-") as temp_dir:
        root = Path(temp_dir)
        index = root / "corpus.jsonl"
        copied = root / "copied.tex"
        unique = root / "unique.tex"
        index.write_text(json.dumps({
            "id": "fixture_C001_P0001",
            "paper": "C001",
            "page_start": 7,
            "section": "model",
            "source": "fixture.pdf#page=7",
            "text": SOURCE_TEXT,
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        copied.write_text(r"\section{问题一模型建立}" + SOURCE_TEXT + "。", encoding="utf-8")
        unique.write_text(r"\section{问题一模型建立}先按每周同类时段汇总订单，再单独处理未观测记录。", encoding="utf-8")
        copied_report = audit(copied, index, 20)
        unique_report = audit(unique, index, 20)
    if copied_report["status"] != "review" or copied_report["literal_overlaps"] != 1:
        print(copied_report)
        return 1
    if copied_report["findings"][0].get("paper") != "C001":
        print(copied_report)
        return 1
    if unique_report["status"] != "pass":
        print(unique_report)
        return 1
    print("PASS: long literal corpus overlap is surfaced for review; distinct prose passes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
