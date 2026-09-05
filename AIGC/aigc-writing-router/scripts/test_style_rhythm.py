#!/usr/bin/env python3
"""Positive and negative regression tests for audit_style_rhythm.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_style_rhythm import audit


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-style-rhythm-") as temp_dir:
        root = Path(temp_dir)
        good = root / "good.tex"
        good.write_text(
            r"""
\section{结果分析}
原始记录按题号保存，而窗口表按相邻五题保存。两张表不能合并使用，否则单题频数会被重复计算。

Q37 的变化先出现在第二个窗口。回到样本逐项核对后，可以确认变化来自两个位置交换，并非所有中间位置同时增加。

这一处交换没有改变总体频数，却改变了窗口内部的相邻关系。因此，后续比较保留窗口编号，不再只看全卷合计。

对末段题目，样本量不足以区分稳定偏好和偶然波动。正文只报告观察到的候选位置，把机制解释留作待核问题。
""",
            encoding="utf-8",
        )
        good_report = audit(good)
        if good_report["status"] != "pass":
            print("FAIL: varied evidence-led prose was rejected", good_report)
            return 1

        contrast = root / "contrast.tex"
        contrast.write_text(
            r"""
\section{误差分析}
这里讨论的不是数值误差，而是模型误差。后续计算据此调整误差项。
""",
            encoding="utf-8",
        )
        contrast_report = audit(contrast)
        contrast_codes = {item["code"] for item in contrast_report["findings"]}
        if contrast_report["status"] != "review" or "CONTRAST_CORRECTION_SHELL" not in contrast_codes:
            print("FAIL: contrast-correction shell was not located", contrast_report)
            return 1

        bad = root / "bad.tex"
        bad.write_text(
            "\\section{结果分析}\n" + "\n\n".join([
                "首先分析第一组数据，可以发现位置分布较为集中，这说明当前结果具有参考价值。",
                "首先分析第二组数据，可以发现位置分布较为集中，这说明当前结果具有参考价值。",
                "首先分析第三组数据，可以发现位置分布较为集中，这说明当前结果具有参考价值。",
                "首先分析第四组数据，可以发现位置分布较为集中，这说明当前结果具有参考价值。",
                "首先分析第五组数据，可以发现位置分布较为集中，这说明当前结果具有参考价值。",
            ]),
            encoding="utf-8",
        )
        bad_report = audit(bad)
        codes = {item["code"] for item in bad_report["findings"]}
        required = {"REPEATED_PARAGRAPH_OPENING", "REPEATED_PARAGRAPH_CLOSURE", "UNIFORM_PARAGRAPH_RUN"}
        if bad_report["status"] != "review" or not required.issubset(codes):
            print("FAIL: repeated paragraph rhythm was not located", bad_report)
            return 1

    print("PASS: varied prose passes; contrast shells and repetitive paragraph rhythm are located.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
