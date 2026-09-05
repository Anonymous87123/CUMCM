#!/usr/bin/env python3
"""Positive and negative regression tests for audit_voice_mode.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_voice_mode import audit


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-voice-mode-") as temp_dir:
        root = Path(temp_dir)
        good = root / "good.tex"
        good.write_text(
            r"""
\section{样本与结果分析}
抽样表保留了题号、答案位置和窗口编号。两个窗口的记录粒度不同，因此前者用于描述单题位置，后者只承担相邻题的联合比较。

位置变化最明显的是中段，但这一现象没有直接给出因果解释。这里只把它作为后续分组比较的入口。

\appendix
\section{证据文件索引}
\begin{itemize}
  \item raw.csv：原始题目记录。
  \item windows.csv：窗口统计结果。
\end{itemize}

\section{操作手册}
\begin{enumerate}
  \item 先打开题目页并标出五个选项。
  \item 再按窗口表核对相邻位置。
  \item 不要用总体频数替代当前题的语义判断。
\end{enumerate}
""",
            encoding="utf-8",
        )
        good_report = audit(good)
        if good_report["status"] != "pass":
            print("FAIL: valid mixed voices were rejected", good_report)
            return 1

        bad = root / "bad.tex"
        bad.write_text(
            r"""
\section{结果分析}
\begin{itemize}\item 结论：中段位置较集中。\end{itemize}
\begin{itemize}\item 解释：这一分布具有一定规律。\end{itemize}
\begin{itemize}\item 建议：答题时关注中段。\end{itemize}
\begin{itemize}\item 注意：不要忽略其他选项。\end{itemize}
""",
            encoding="utf-8",
        )
        bad_report = audit(bad)
        codes = {item["code"] for item in bad_report["findings"]}
        required = {"PROSE_ONE_ITEM_LIST_CHAIN", "PROSE_LIST_DOMINANCE", "PROSE_LABEL_CARD_CHAIN"}
        if bad_report["status"] != "review" or not required.issubset(codes):
            print("FAIL: card-like prose was not located", bad_report)
            return 1

    print("PASS: prose, evidence, and operator voices are separated; card-like prose is reviewable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
