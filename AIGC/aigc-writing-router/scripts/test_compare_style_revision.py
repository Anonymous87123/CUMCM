#!/usr/bin/env python3
"""Regression tests for source/candidate style comparison."""

from __future__ import annotations

from pathlib import Path
import tempfile

from compare_style_revision import compare


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    noisy = r"""\documentclass{ctexart}
\begin{document}
\section{问题分析}
\begin{itemize}\item 结论：首先考虑已有数据。\end{itemize}
\begin{itemize}\item 解释：首先建立对应模型。\end{itemize}
\begin{itemize}\item 建议：首先给出计算结果。\end{itemize}
\begin{itemize}\item 判断：首先完成结果分析。\end{itemize}
\end{document}
"""
    improved = r"""\documentclass{ctexart}
\begin{document}
\section{问题分析}
两张记录表的时间粒度不同：日表适合判断总体波动，小时表用于确认峰值出现的具体时段。因此，我们先用日表确定异常日期，再回到小时记录比较峰值前后的变化。

这一处理保留了两张表各自能回答的问题，也避免把不同粒度的数据直接拼接。模型建立时分别定义日尺度指标和小时尺度指标，最后只在异常日期这一共同索引上汇合。
\end{document}
"""
    regressed = noisy.replace("\n\\end{document}", "\n\\begin{itemize}\\item 注意：最后完成检查。\\end{itemize}\n\\end{document}")
    with tempfile.TemporaryDirectory(prefix="aigc-style-comparison-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        better = root / "better.tex"
        worse = root / "worse.tex"
        source.write_text(noisy, encoding="utf-8")
        better.write_text(improved, encoding="utf-8")
        worse.write_text(regressed, encoding="utf-8")
        better_report = compare(source, better)
        worse_report = compare(source, worse)
        require(better_report["status"] == "improved", "clear structural improvement was not recognized")
        require(worse_report["status"] == "review", "structural regression was not blocked")
    print("PASS: relative improvements are recorded and structural regressions remain review-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
