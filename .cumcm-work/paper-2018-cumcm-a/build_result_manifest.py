#!/usr/bin/env python3
"""Build result-sync-manifest.json: freeze the result sources and pin the manuscript claims.

`sources` locks the files the numbers came from by SHA-256, so regenerating the
solver output without rewriting the manuscript fails the gate. `claims` pins the
literals the manuscript actually asserts, and `forbidden` lists the stale values
that must never reappear -- including the reference paper's reported thicknesses,
which this manuscript only ever cites as infeasible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

W = Path(__file__).resolve().parent
SOURCES = ("results/run-report.json", "results/conclusions.json",
           "solver/simulator.py", "inputs/attachment.xlsx")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    manifest = {
        "schema": "mcm-result-sync-manifest/v1",
        "note": "正文数值与 solver 输出同源的锁。sources 用哈希钉住来源文件；"
                "claims 钉住正文实际断言的字面量；forbidden 列出不得出现的过期值。",
        "sources": [{"path": rel, "sha256": sha256(W / rel)} for rel in SOURCES],
        "claims": [
            {"id": "calibration-two-routes", "literal": "8.6124", "min_occurrences": 1},
            {"id": "calibration-selected", "literal": "8.7739", "min_occurrences": 2},
            {"id": "calibration-gap", "literal": "1.88", "min_occurrences": 1},
            {"id": "q1-rmse", "literal": "0.4517", "min_occurrences": 2},
            {"id": "q1-last-30min", "literal": "0.1453", "min_occurrences": 2},
            {"id": "q1-first-10min", "literal": "1.2798", "min_occurrences": 2},
            {"id": "q1-steady-agreement", "literal": "47.934716682526", "min_occurrences": 1},
            {"id": "grid-convergence", "literal": "2.7e-9", "min_occurrences": 2},
            {"id": "air-diffusivity", "literal": "2.361e-5", "min_occurrences": 3},
            {"id": "stack-resistance", "literal": "0.282105", "min_occurrences": 1},
            {"id": "air-layer-drop", "literal": "17.040", "min_occurrences": 2},
            {"id": "q2-optimum", "literal": "18.16", "min_occurrences": 3},
            {"id": "q2-peak", "literal": "44.045", "min_occurrences": 2},
            {"id": "q2-crossing-second", "literal": "3302", "min_occurrences": 1},
            {"id": "q2-crossing-minute", "literal": "55.0", "min_occurrences": 1},
            {"id": "q3-boundary", "literal": "3.8", "min_occurrences": 2},
            {"id": "q3-thinnest-d2", "literal": "21.188", "min_occurrences": 3},
            {"id": "q3-total", "literal": "27.588", "min_occurrences": 1},
            {"id": "sens-minus-2", "literal": "19.19", "min_occurrences": 2},
            {"id": "sens-plus-2", "literal": "17.04", "min_occurrences": 2},
            {"id": "sens-plateau", "literal": "44.1425", "min_occurrences": 1},
            {"id": "sens-slope-55min", "literal": "0.0112", "min_occurrences": 2},
            # 参考论文报告值：正文只在“代入本模型后不可行”这一处引用，
            # 不得作为本文结论出现在摘要或结果小结里。
            {"id": "reference-q2-value", "literal": "3256", "min_occurrences": 1},
            {"id": "reference-q3-peak-a", "literal": "48.97", "min_occurrences": 1},
            {"id": "reference-q3-peak-b", "literal": "48.01", "min_occurrences": 1},
            # 审查阶段已证伪的值不得作为本文结论复现。
            {"id": "no-stale-diffusivity", "literal": "扩散系数", "min_occurrences": 3,
             "forbidden": ["2.6311", "a =0.082", "a=0.082"]},
            {"id": "no-stale-optimum", "literal": "最小可行厚度", "min_occurrences": 2,
             "forbidden": ["最优厚度为 5.5", "最优厚度为 5.6"]},
        ],
    }
    out = W / "result-sync-manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  sources={len(manifest['sources'])} claims={len(manifest['claims'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
