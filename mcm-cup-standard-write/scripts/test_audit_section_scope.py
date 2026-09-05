#!/usr/bin/env python3
"""Regression checks for section scope and Monte Carlo protocol detection."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_manuscript import audit, section_body


TEX = r"""\documentclass{ctexart}
\begin{document}
\begin{abstract}摘要正文。\end{abstract}
\keywords{预测；检验}
\section{问题重述}题目要求预测结果。
\section{问题分析：数据口径与模型接口}
\subsection{数据口径}团队项目会把同一枚奖牌记在多名运动员名下，因此国家目标采用官方汇总表，运动员记录只承担项目归属和参赛规模统计。项目表若缺少预测年份，则不从上下文补造正式赛程，只保留为单独情景。
\subsection{方法接口}上一届成绩保留历史状态，东道主变量只修正局部偏移。全体国家平均误差容易被大量零值样本稀释，所以模型选择还要检查奖牌榜前部国家，并保留上一届成绩作为必须超过的基线。
\section{模型假设}项目总量按给定基准处理。
\section{符号说明}记 $Y$ 为奖牌数。
\section{问题一模型的建立与求解}使用历史窗口拟合并逐届前推。
\section{结果与分析：预测结果}
\subsection{点预测}美国点预测较高，这是主场修正与近期成绩共同作用的结果；法国退出主场周期后回落，变化来自状态切换，而不是树模型凭空生成的趋势。
\subsection{区间解释}区间重叠意味着相邻名次不能写成确定排序。点预测用于比较中心位置，历史残差区间则约束结论强度，两种结果不能混写成确定名次。
\section{模型检验}滚动验证的 MAE 为 1.44。
\section{灵敏度与稳健性分析}
以随机种子 20250814 独立重复 50000 次 Bernoulli 抽样，报告 5\% 与 95\% 分位数。
\section{模型评价与改进}结论只适用于当前项目口径。
\begin{thebibliography}{9}\bibitem{x} 测试资料。\end{thebibliography}
\appendix\section{附录}给出复算接口。
\end{document}
"""


def main() -> int:
    analysis = section_body(TEX, r"(?:问题分析|建模思路)")
    result = section_body(TEX, r"结果(?:分析|与分析)?")
    assert "团队项目会把同一枚奖牌" in analysis
    assert "上一届成绩保留历史状态" in analysis
    assert "美国点预测较高" in result
    assert "区间重叠意味着" in result

    with tempfile.TemporaryDirectory(prefix="mcm-audit-scope-") as temp_dir:
        path = Path(temp_dir) / "main.tex"
        path.write_text(TEX, encoding="utf-8")
        report = audit(path, "C")
    codes = {item["code"] for item in report["findings"]}
    forbidden = {
        "THIN_PROBLEM_ANALYSIS",
        "THIN_RESULT_EXPLANATION",
        "RESULT_WITHOUT_INTERPRETATION",
        "MONTE_CARLO_PROTOCOL",
    }
    unexpected = sorted(codes & forbidden)
    if unexpected:
        print("FAIL:", unexpected)
        return 1
    print("PASS: section scope includes child headings; 50000 次 is a sample-count signal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
