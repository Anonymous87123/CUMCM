#!/usr/bin/env python3
"""Positive and negative checks for audit_result_sync.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_result_sync import audit, sha256


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-result-sync-") as temp_dir:
        root = Path(temp_dir)
        source = root / "summary.json"
        manuscript = root / "main.tex"
        manifest = root / "manifest.json"
        source.write_text('{"expected": 5.08}', encoding="utf-8")
        manuscript.write_text("首牌期望为 5.08，区间为 2--9。", encoding="utf-8")
        manifest.write_text(json.dumps({
            "sources": [{"path": "summary.json", "sha256": sha256(source)}],
            "claims": [
                {"id": "expected", "literal": "5.08", "forbidden": ["5.89"]},
                {"id": "interval", "literal": "2--9"},
            ],
        }), encoding="utf-8")

        good = audit(manuscript, manifest)
        if good["status"] != "pass":
            print("FAIL: valid manifest did not pass", good)
            return 1

        source.write_text('{"expected": 6.00}', encoding="utf-8")
        bad_hash = audit(manuscript, manifest)
        if not any(item["code"] == "SOURCE_HASH_MISMATCH" for item in bad_hash["findings"]):
            print("FAIL: changed source hash was not detected", bad_hash)
            return 1

        source.write_text('{"expected": 5.08}', encoding="utf-8")
        manuscript.write_text("首牌期望为 5.89，区间为 2--9。", encoding="utf-8")
        bad_literal = audit(manuscript, manifest)
        codes = {item["code"] for item in bad_literal["findings"]}
        if not {"CLAIM_MISSING", "STALE_LITERAL"} <= codes:
            print("FAIL: stale literal was not detected", bad_literal)
            return 1

    print("PASS: result source changes and stale manuscript literals are blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
