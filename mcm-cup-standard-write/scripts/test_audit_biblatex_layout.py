#!/usr/bin/env python3
"""Regression checks for real CUMCM class conventions and BibLaTeX resources."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_manuscript import audit


TEX = r"""\documentclass{ctexart}
\addbibresource{ref.bib}
\begin{document}
\begin{abstract}本文建立微分方程并报告结果。\end{abstract}
\keyword{机理；微分方程；验证}
\section{问题重述}题目要求计算状态变化。
\section{问题分析}边界条件决定状态变量和离散范围。
\section{模型假设}参数在给定时段内保持不变。
\section{符号说明}
\begin{table}[htbp]\centering\caption{主要符号}
\begin{tabular}{ll}$x$ & 状态量\\\end{tabular}\end{table}
\section{问题一的模型建立与求解}
\subsection{模型建立}由守恒关系建立微分方程 $x'=f(x)$\cite{known}。
\subsection{参数标定与结果对照}回代误差为 0.12，外部对照方向一致。
\subsection{结果与机制解释}状态量上升，原因是边界输入增加。
\paragraph{参数敏感性分析}参数作正负扰动后，结果排序保持不变。
\section{模型评价与改进}结论仅适用于当前边界范围。
\section{参考文献}\printbibliography[heading=none]
\appendix\section{附录}给出复算代码。
\end{document}
"""


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["findings"]}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-audit-biblatex-") as temp:
        root = Path(temp)
        manuscript_root = root / "candidate"
        resource_root = root / "resources"
        manuscript_root.mkdir()
        resource_root.mkdir()
        main_tex = manuscript_root / "main.tex"
        main_tex.write_text(TEX, encoding="utf-8")
        (resource_root / "ref.bib").write_text(
            "@article{known, title={Known source}, author={A}, year={2026}}\n",
            encoding="utf-8",
        )

        good = audit(main_tex, "A", (resource_root,))
        forbidden = {
            "MISSING_KEYWORDS", "MISSING_REFERENCES", "MISSING_RESULTS",
            "MISSING_VALIDATION", "MISSING_ROBUSTNESS", "TABLE_LABEL",
            "BIB_RESOURCE_NOT_FOUND", "UNDEFINED_CITATION", "SECTION_ORDER",
        }
        if codes(good) & forbidden or good["status"] != "PASS":
            print("FAIL: valid BibLaTeX/custom-class manuscript was rejected", good)
            return 1

        missing_resource = audit(main_tex, "A")
        if "BIB_RESOURCE_NOT_FOUND" not in codes(missing_resource):
            print("FAIL: missing BibLaTeX resource was not rejected", missing_resource)
            return 1

        unknown_tex = manuscript_root / "unknown.tex"
        unknown_tex.write_text(TEX.replace("{known}", "{unknown}"), encoding="utf-8")
        unknown = audit(unknown_tex, "A", (resource_root,))
        if "UNDEFINED_CITATION" not in codes(unknown):
            print("FAIL: unknown BibLaTeX key was not rejected", unknown)
            return 1

        unlabeled_tex = manuscript_root / "unlabeled.tex"
        unlabeled_tex.write_text(
            TEX.replace(
                "\\section{模型评价与改进}",
                "\\begin{table}[htbp]\\caption{普通结果表}\\begin{tabular}{l}1\\\\\\end{tabular}\\end{table}\n"
                "\\section{模型评价与改进}",
            ),
            encoding="utf-8",
        )
        unlabeled = audit(unlabeled_tex, "A", (resource_root,))
        if "TABLE_LABEL" not in codes(unlabeled):
            print("FAIL: ordinary unlabeled result table was not rejected", unlabeled)
            return 1

    print("PASS: custom keyword, integrated result/validation/robustness headings and BibLaTeX resources are audited without weakening ordinary table or citation gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
