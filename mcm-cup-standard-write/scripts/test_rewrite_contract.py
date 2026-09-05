#!/usr/bin/env python3
"""Positive and negative tests for one-pass protected rewriting."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_rewrite_contract import audit


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-rewrite-") as temp_dir:
        root = Path(temp_dir)
        before = root / "before.tex"
        after = root / "after.tex"
        terms = root / "terms.txt"
        terms.write_text("滚动验证\n平均绝对误差\n", encoding="utf-8")
        before.write_text(
            r"""\section{模型检验}\label{sec:check}
我们采用滚动验证检查预测误差，平均绝对误差为 1.25 枚。
\begin{equation}\label{eq:mae}\mathrm{MAE}=\frac{1}{n}\sum_i|y_i-\hat y_i|\end{equation}
由式\eqref{eq:mae}可见，本次计算只评价留出届。
""",
            encoding="utf-8",
        )
        after.write_text(
            r"""\section{模型检验}\label{sec:check}
预测时按届次向前滚动验证；留出届的平均绝对误差为 1.25 枚。
\begin{equation}\label{eq:mae}\mathrm{MAE}=\frac{1}{n}\sum_i|y_i-\hat y_i|\end{equation}
式\eqref{eq:mae}只对应没有参与拟合的届次。
""",
            encoding="utf-8",
        )
        good = audit(before, after, terms)
        if good["status"] != "pass":
            print("FAIL: protected prose rewrite failed", good)
            return 1

        before.write_text("题号 Q38 对应模型_v2，结果为 3.2。\n", encoding="utf-8")
        after.write_text("题号 Q44 对应模型_v3，结果为 3.2。\n", encoding="utf-8")
        identifiers = audit(before, after)
        if identifiers["status"] != "pass":
            print("FAIL: identifier digits were treated as standalone numbers", identifiers)
            return 1

        after.write_text(
            r"""\section{模型验证}\label{sec:validation}
预测时按届次向前滚动验证；留出届的平均误差为 1.52 届。
\begin{equation}\label{eq:rmse}\mathrm{RMSE}=\sqrt{\frac{1}{n}\sum_i(y_i-\hat y_i)^2}\end{equation}
式\eqref{eq:rmse}只对应没有参与拟合的届次。
""",
            encoding="utf-8",
        )
        bad = audit(before, after, terms)
        codes = {item["code"] for item in bad["findings"]}
        required = {"MATH_CHANGED", "STRUCTURE_CHANGED", "REFERENCE_CHANGED", "NUMBER_CHANGED", "UNIT_CHANGED", "PROTECTED_TERM_CHANGED"}
        if not required.issubset(codes):
            print("FAIL: semantic drift during rewriting was not rejected", bad)
            return 1

        before.write_text(
            "目标是最小化成本，容量不低于 8 m。当前结果未显著变化，只能表明该因素可能导致局部波动。\n",
            encoding="utf-8",
        )
        after.write_text(
            "目标是最大化成本，容量不超过 8 m。当前结果显著变化，可以证明该因素必然造成局部波动。\n",
            encoding="utf-8",
        )
        semantic = audit(before, after)
        semantic_codes = {item["code"] for item in semantic["findings"]}
        required_semantic = {
            "OBJECTIVE_DIRECTION_CHANGED",
            "CONSTRAINT_DIRECTION_CHANGED",
            "NEGATION_CHANGED",
            "CAUSAL_DIRECTION_MARKER_CHANGED",
            "CLAIM_STRENGTH_CHANGED",
        }
        if not required_semantic.issubset(semantic_codes):
            print("FAIL: high-risk semantic drift was not rejected", semantic)
            return 1
        for item in semantic["findings"]:
            if item["code"] in {
                "CONSTRAINT_DIRECTION_CHANGED", "NEGATION_CHANGED",
                "CAUSAL_DIRECTION_MARKER_CHANGED", "CLAIM_STRENGTH_CHANGED",
            }:
                if not item.get("finding_sha256") or not (
                    item.get("before_examples") or item.get("after_examples")
                ):
                    print("FAIL: semantic drift lacks hash-bound locations", item)
                    return 1

        before.write_text(
            "由于两类观测分别对应全流域和局部江段，因此先用全流域数据约束系统总量。"
            "但是局部单网次记录仍可检验空间差异，随后再将这种差异放入结果解释。"
            "如果直接把两类数据合并，参数会同时承担总量和局部波动两种职责，只能得到含混的标定结果。\n",
            encoding="utf-8",
        )
        after.write_text(
            "两类数据用于模型标定和结果分析。全流域数据受到约束，局部记录反映空间差异。\n",
            encoding="utf-8",
        )
        compressed = audit(before, after, scene="MODELING")
        compression = [
            item for item in compressed["findings"]
            if item["code"] == "ARGUMENT_COMPRESSION_REVIEW"
        ]
        chain_loss = [
            item for item in compressed["findings"]
            if item["code"] == "MODELING_JUDGMENT_CHAIN_LOSS"
        ]
        if (
            compressed["status"] != "pass" or len(compression) != 1
            or not compression[0].get("finding_sha256")
            or compression[0].get("location_method") != "changed-block-compression"
            or len(chain_loss) != 1
            or chain_loss[0].get("missing_categories") != ["mathematical_change"]
            or not chain_loss[0].get("finding_sha256")
        ):
            print("FAIL: modeling judgment-chain loss was not located as an advisory warning", compressed)
            return 1

        general = audit(before, after, scene="GENERAL")
        if any(
            item["code"] == "MODELING_JUDGMENT_CHAIN_LOSS"
            for item in general["findings"]
        ):
            print("FAIL: modeling judgment gate leaked into the GENERAL scene", general)
            return 1

    print("PASS: one-pass rewriting preserves hard semantics and locates paragraph-level public-reasoning compression.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
