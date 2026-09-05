#!/usr/bin/env python3
"""Regression tests for repeated public reasoning-scaffold detection."""

from __future__ import annotations

from pathlib import Path
import tempfile

from audit_reasoning_scaffold import audit


def section(title: str, model: str) -> str:
    return (
        f"\\section{{{title}}}\n"
        "题面数据呈现出明显变化，需要先说明数据依据。\n\n"
        "基线方法存在不足，无法解释本问中受到容量约束后的变化。\n\n"
        "比较候选方案后保留适合本问的路线，并说明舍弃其他方案的原因。\n\n"
        f"建立{model}模型，写出目标函数和约束条件，变量范围来自题面限制。\n\n"
        "采用迭代算法求解，按停止条件更新变量并记录中间结果。\n\n"
        "得到结果后进行误差检验，检查结果是否满足题面给出的约束。\n"
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-scaffold-") as temp:
        root = Path(temp)
        good = root / "good.tex"
        good.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题分析}\n"
            "题面数据先给出观测事实。\n\n"
            "模型建立时将实际约束转成变量域。\n\n"
            "计算得到结果后，比较误差并验证稳定性。\n"
            + section("问题一", "回归")
            + section("问题二", "整数规划")
            + "\\end{document}\n",
            encoding="utf-8",
        )
        report = audit(good)
        assert report["status"] == "pass", report

        bad = root / "bad.tex"
        bad.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            + section("问题一", "回归")
            + section("问题二", "整数规划")
            + section("问题三", "聚类")
            + "\\end{document}\n",
            encoding="utf-8",
        )
        bad_report = audit(bad)
        assert bad_report["status"] == "review", bad_report
        assert any(item["code"] == "REPEATED_REASONING_SCAFFOLD" for item in bad_report["findings"]), bad_report

        mechanical = root / "mechanical.tex"
        mechanical_section = "".join(
            f"\\section{{问题{index}}}\n"
            "核心困难来自题面中的观测变化，需要先说明它对当前问题的实际影响。\n\n"
            "基线方案无法解释当前约束下出现的现象，仍然存在明显不足。\n\n"
            "针对基线不足，我们把几个备选路线放在同一口径下进行候选比较。\n\n"
            "依据比较结果说明选择依据，并保留与本问对象相符的处理路线。\n\n"
            "模型建立后写出变量、目标函数和约束条件等数学关系。\n\n"
            "采用求解算法得到结果，再结合误差指标和题面条件进行验证。\n"
            for index in ("一", "二", "三")
        )
        mechanical.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n" + mechanical_section + "\\end{document}\n",
            encoding="utf-8",
        )
        mechanical_report = audit(mechanical)
        assert mechanical_report["status"] == "review", mechanical_report
        assert any(item["code"] == "REPEATED_REASONING_SCAFFOLD" for item in mechanical_report["findings"]), mechanical_report

        near = root / "near.tex"
        base = section("问题一", "回归")
        with_phenomenon = section("问题二", "整数规划").replace(
            "基线方法存在不足",
            "局部时段出现异常突增，变化幅度随后回落。\n\n基线方法存在不足",
        )
        with_explanation = section("问题三", "聚类").replace(
            "得到结果后进行误差检验",
            "由于容量约束改变了局部机制，这一原因需要单独解释。\n\n得到结果后进行误差检验",
        )
        near.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            + base + with_phenomenon + with_explanation + "\\end{document}\n",
            encoding="utf-8",
        )
        near_report = audit(near)
        assert near_report["status"] == "review", near_report
        assert any(
            item["code"] == "NEAR_REPEATED_REASONING_SCAFFOLD"
            for item in near_report["findings"]
        ), near_report
    print("REASONING SCAFFOLD TEST PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
