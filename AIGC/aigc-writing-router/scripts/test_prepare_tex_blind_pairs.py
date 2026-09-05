#!/usr/bin/env python3
"""Tests for hash-bound TeX blind-pair extraction."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from adapter_core import sha256_file
from prepare_tex_blind_pairs import build


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-tex-blind-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source.write_text("标题\n\\noindent 源段 3.2。 % comment\n尾行\n", encoding="utf-8")
        candidate.write_text("标题\n候选段 3.2。\n尾行\n", encoding="utf-8")
        spec = root / "spec.json"
        payload = {
            "schema": "aigc-tex-blind-pair-spec/v1",
            "source": {"path": str(source), "sha256": sha256_file(source)},
            "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
            "pairs": [{
                "id": "p1", "section": "摘要",
                "source_lines": {"start": 2, "end": 2},
                "candidate_lines": {"start": 2, "end": 2},
            }],
        }
        spec.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output = root / "pairs.json"
        report = build(spec, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        require(report["status"] == "pass" and report["pairs"] == 1, "valid pair build failed", report)
        require(result["pairs"][0]["variants"][0]["text"] == "源段 3.2。", "TeX/comment cleanup failed", result)
        require(result["provenance"]["source"]["sha256"] == sha256_file(source), "source binding missing", result)

        payload["source"]["sha256"] = "0" * 64
        spec.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            build(spec, root / "bad.json")
        except ValueError as exc:
            require("SHA-256 mismatch" in str(exc), "wrong hash raised the wrong error", str(exc))
        else:
            raise AssertionError("wrong source hash passed")

        payload["source"]["sha256"] = sha256_file(source)
        payload["pairs"][0]["source_lines"] = {"start": 2, "end": 99}
        spec.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            build(spec, root / "bad-range.json")
        except ValueError as exc:
            require("outside" in str(exc), "bad range raised the wrong error", str(exc))
        else:
            raise AssertionError("out-of-range line binding passed")

    print("PASS: TeX blind pairs bind both file hashes and exact line ranges before A/B randomisation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
