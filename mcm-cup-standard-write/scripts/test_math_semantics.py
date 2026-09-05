#!/usr/bin/env python3
"""Positive and negative tests for explicit mathematics contracts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_math_semantics import audit


def contract_payload() -> dict:
    return {
        "symbols": [
            {
                "name": "x_i",
                "definition_pattern": r"其中，?\s*\$x_i\$[^。]*0--1决策变量",
                "use_pattern": r"x_i",
            }
        ],
        "units": [
            {
                "name": "distance",
                "manuscript_patterns": [r"距离单位为\s*m"],
                "forbidden_patterns": [r"距离单位为\s*cm"],
            }
        ],
        "objectives": [
            {
                "name": "total_cost",
                "manuscript_patterns": [r"最小化总成本", r"\\min"],
                "code_path": "model.py",
                "code_patterns": [r"sense\s*=\s*['\"]minimize['\"]"],
            }
        ],
        "constraints": [
            {
                "name": "capacity",
                "manuscript_patterns": [r"需求量不超过容量"],
                "code_path": "model.py",
                "code_patterns": [r"demand\s*<=\s*capacity"],
            }
        ],
        "code_map": [
            {
                "name": "decision_vector",
                "manuscript_patterns": [r"0--1决策变量"],
                "code_path": "model.py",
                "code_patterns": [r"decision_x"],
            }
        ],
        "rechecks": [
            {
                "name": "mean_cost",
                "operation": "mean",
                "values": [10, 12, 14],
                "expected": 12,
                "tolerance": 1e-12,
                "manuscript_literal": "12.00",
            },
            {
                "name": "filtered_mean",
                "operation": "mean",
                "source": "runs.csv",
                "csv_column": "completed",
                "csv_filters": {"case": "two"},
                "expected": 11,
                "tolerance": 1e-12,
                "manuscript_literal": "11.00",
            }
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-math-") as temp_dir:
        root = Path(temp_dir)
        tex = root / "main.tex"
        code = root / "model.py"
        runs = root / "runs.csv"
        contract = root / "math-contract.json"
        tex.write_text(
            r"""
其中，$x_i$ 表示站点是否启用的0--1决策变量。距离单位为 m，目标为最小化总成本。
\begin{equation}\min \sum_i c_i x_i\end{equation}
题面要求需求量不超过容量。三组同口径成本的均值为 12.00，筛选后均值为 11.00。
""",
            encoding="utf-8",
        )
        code.write_text(
            "sense = 'minimize'\ndecision_x = [0, 1]\ndemand <= capacity\n",
            encoding="utf-8",
        )
        runs.write_text("case,completed\none,99\ntwo,10\ntwo,12\n", encoding="utf-8")
        payload = contract_payload()
        contract.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        good = audit(tex, contract)
        if good["status"] != "pass":
            print("FAIL: consistent mathematics contract failed", good)
            return 1

        # The TeX delimiter may make the use match start one character before
        # the definition match at the same occurrence.  This is still a valid
        # define-on-first-use pattern, not a prior use.
        tex.write_text(
            r"""班次在 $H=28800$ s 截止，后文使用 $H$ 表示班次上界。""",
            encoding="utf-8",
        )
        overlap_contract = {
            "symbols": [{
                "name": "H",
                "definition_pattern": r"H=28800",
                "use_pattern": r"\$H(?:=|\$)",
            }]
        }
        contract.write_text(json.dumps(overlap_contract, ensure_ascii=False), encoding="utf-8")
        overlap = audit(tex, contract)
        if overlap["status"] != "pass":
            print("FAIL: define-on-first-use was rejected", overlap)
            return 1

        tex.write_text(
            r"""
\begin{equation}\min \sum_i c_i x_i\end{equation}
其中，$x_i$ 表示站点是否启用的0--1决策变量。距离单位为 cm，目标为最小化总成本。
题面要求需求量不超过容量。正文遗漏了复算值。
""",
            encoding="utf-8",
        )
        code.write_text("sense = 'maximize'\ndecision_x = [0, 1]\ndemand >= capacity\n", encoding="utf-8")
        payload["rechecks"][0]["expected"] = 99
        contract.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        bad = audit(tex, contract)
        codes = {item["code"] for item in bad["findings"]}
        required = {
            "SYMBOL_USED_BEFORE_DEFINITION",
            "UNIT_MANUSCRIPT_PATTERN_MISSING",
            "UNIT_FORBIDDEN_PATTERN",
            "CODE_PATTERN_MISSING",
            "CONSTRAINT_CODE_PATTERN_MISSING",
            "RECHECK_MISMATCH",
            "RECHECK_LITERAL_MISSING",
        }
        if not required.issubset(codes):
            print("FAIL: inconsistent mathematics was not rejected", bad)
            return 1

    print("PASS: symbol order, units, objective direction, constraints and rechecks are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
