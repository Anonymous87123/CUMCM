#!/usr/bin/env python3
"""Cross-type forward regression gate for A/B/C CUMCM long-form rules.

This compact fixture test catches cross-type regression quickly.  It does not
replace the separately recorded 25--30 page formal blind tests.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from audit_content_density import audit as audit_density
from audit_manuscript import audit as audit_manuscript


TYPE_CONTRACTS = {
    "A": {
        "mechanism": r"机理|守恒|受力|运动关系",
        "boundary": r"边界|初值",
        "discretization": r"离散|有限差分|有限元|网格",
        "error": r"截断误差|离散误差|网格收敛|误差",
    },
    "B": {
        "variable_domain": r"决策变量|变量域|整数变量|0--1变量|非负变量",
        "constraint_source": r"约束.*(?:来自|对应|由)|题面.*约束|容量限制|预算上限",
        "feasibility": r"可行解|可行性|约束余量|违约量",
        "strategy_switch": r"策略切换|方案切换|活跃约束|切换为",
    },
    "C": {
        "record_grain": r"记录粒度|样本单位|一行.*(?:表示|对应)|重复键",
        "set_isolation": r"训练集|测试集|滚动验证|时间切分|数据泄漏",
        "calibration": r"校准|概率修正|区间覆盖|可靠性曲线",
        "interpretation": r"结果.*(?:说明|意味着)|业务含义|不能称为因果|解释",
    },
}


TYPE_BODY = {
    "A": r"""
题面给出的相邻节点距离保持不变，这一运动关系决定了状态不能逐点独立计算。我们先沿构件方向建立局部坐标，把长度守恒写成递推约束。

边界条件取入口处的已知位姿，初值由题面时刻直接给出。接近首次接触时，事件函数的变化明显快于其他区间，固定大步长会越过真实触发点。

因此只在事件函数接近零的区间采用有限差分局部加密，而不是在全时段统一缩小网格。状态更新为
\begin{equation}\label{eq:main}x_{k+1}=x_k+h f(x_k),\qquad g(x_k)\ge 0.\end{equation}

计算中先用粗网格确定事件所在时间段，再在该段二分缩短步长。最后把解代回长度约束，最大残差为 $2.1\times10^{-4}$，并比较三组网格下的首次事件时刻。
""",
    "B": r"""
每个候选站点只能选择一种建设等级，因此把站点选择和等级选择合并为0--1决策变量，变量域由题面的互斥关系直接得到。

容量限制来自各站点的设备上限，预算上限对应给定总投资；服务覆盖不是附加评分，而是每个需求点都必须满足的硬约束。目标函数计入建设成本和未满足需求惩罚：
\begin{equation}\label{eq:main}\min C=\sum_i c_i x_i+\lambda\sum_j u_j.\end{equation}

先求不含软惩罚的小规模整数规划，用它核对成本会计和约束方向，再扩大到全部站点。最终方案的容量约束余量均为非负，因此是可行解。

当预算下降到临界值以下时，活跃约束由站点容量切换为总预算，原来的三级站点随之切换为两个二级站点；这里报告的是策略切换，不把离散跳变解释为连续敏感性。
""",
    "C": r"""
附件中一行对应一名运动员在一个项目中的一次参赛记录，同一运动员会跨项目重复出现。这个记录粒度不能直接当作国家样本，因此运动员表只负责构造项目特征，国家--届次表承担预测目标。

数据按届次做时间切分，滚动验证的测试届始终晚于训练集；缺失值口径和类别编码只在当轮训练集上拟合，避免把未来届信息带回模型。

模型输出先给未校准概率，再在验证届上做概率校准，并用区间覆盖率检查不确定性：
\begin{equation}\label{eq:main}\hat p_i=\frac{1}{1+\exp(-\beta^Tz_i)}.\end{equation}

结果说明高参赛规模国家的排序较稳定，但对首次参赛的小国仍有较宽区间。该结果用于确定核查顺序，不能称为项目投入对获奖的因果效应。
""",
}


def missing_type_signals(text: str, problem_type: str) -> list[str]:
    return [
        name
        for name, pattern in TYPE_CONTRACTS[problem_type].items()
        if not re.search(pattern, text, re.S)
    ]


def fixture(problem_type: str) -> str:
    return rf"""
\begin{{abstract}}
本文围绕题目给定对象建立可复算模型，摘要只报告主要结果及其适用边界。
\end{{abstract}}
\keywords{{数学建模\quad 结果检验\quad {problem_type}类问题}}
\label{{mcm-body-start}}
\section{{问题重述}}
题目要求根据给定条件完成分问计算，并报告能够由数据和模型支持的有限结论。

\section{{问题分析}}
各分问沿用同一对象定义，但新增量不同，后问只接收前问已经确定的状态或参数。

\section{{模型假设}}
题面未说明的外部条件在计算时保持不变；所有数值均使用附件给出的统一单位。

\section{{符号说明}}
记 $x$ 为状态或决策量，$k$ 为离散索引，其余符号在首次出现的公式附近定义。

\label{{mcm-q1-start}}
\section{{分问题模型建立与求解}}
\subsection{{问题一的对象、模型与计算}}
{TYPE_BODY[problem_type]}

\section{{结果分析}}
式\eqref{{eq:main}}的计算结果与题面约束逐项核对。数值变化只在当前样本、边界和参数范围内解释，不外推为普遍规律。

\section{{模型检验}}
我们对关键关系做回代，并报告误差、约束余量或留出集指标；该检查不冒充独立外部验证。

\section{{灵敏度分析}}
扰动一个关键参数并固定其余输入，记录结果是否连续变化以及事件或策略对象是否发生切换。
\label{{mcm-q1-end}}

\section{{模型评价与改进}}
现有模型能够复算正文结果，但结论受题面边界和附件字段限制，新增数据应优先核查这一缺口。
\label{{mcm-body-end}}

\begin{{thebibliography}}{{1}}
\bibitem{{ref}} 全国大学生数学建模竞赛相关资料.
\end{{thebibliography}}
\appendix
\section{{附录}}
附录保存执行入口、参数表和正文图表对应的结果文件。
"""


def main() -> int:
    references = Path(__file__).resolve().parent.parent / "references"
    formal_records = [
        references / "blind-test-2019-cumcm-a.md",
        references / "blind-test-2018-cumcm-b.md",
        references / "blind-test-2025-mcm-c.md",
    ]
    missing_records = [path.name for path in formal_records if not path.is_file()]
    if missing_records:
        print("FAIL: formal A/B/C blind-test records are missing", missing_records)
        return 1
    formal_requirements = {
        "A": ("正文 25 页", ("机理", "边界", "离散", "误差")),
        "B": ("正文 25 页", ("并发", "资源", "策略", "故障")),
        "C": ("正文 25 页", ("记录粒度", "逐期向前验证", "校准", "因果")),
    }
    for problem_type, record_path in zip("ABC", formal_records):
        record_text = record_path.read_text(encoding="utf-8-sig")
        page_marker, signals = formal_requirements[problem_type]
        missing = [signal for signal in (page_marker, *signals) if signal not in record_text]
        if missing:
            print(f"FAIL: {problem_type} formal blind-test record is incomplete", missing)
            return 1

    with tempfile.TemporaryDirectory(prefix="mcm-abc-") as temp_dir:
        root = Path(temp_dir)
        aux = root / "main.aux"
        coverage = root / "coverage.json"
        aux.write_text(
            r"\newlabel{mcm-body-start}{{1}{3}{正文}{section.1}{}}" "\n"
            r"\newlabel{mcm-q1-start}{{2}{6}{问题一}{section.5}{}}" "\n"
            r"\newlabel{mcm-q1-end}{{3}{13}{问题一结束}{section.9}{}}" "\n"
            r"\newlabel{mcm-body-end}{{4}{28}{正文结束}{section.10}{}}",
            encoding="utf-8",
        )
        coverage.write_text(
            json.dumps(
                {
                    "questions": [
                        {
                            "id": "Q1",
                            "start_label": "mcm-q1-start",
                            "end_label": "mcm-q1-end",
                            "section_titles": ["分问题模型建立与求解", "问题一", "结果分析", "模型检验", "灵敏度分析"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        for problem_type in "ABC":
            tex = root / f"{problem_type}.tex"
            text = fixture(problem_type)
            tex.write_text(text, encoding="utf-8")
            structural = audit_manuscript(tex, problem_type)
            density = audit_density(tex, aux, coverage, problem_type, None)
            missing = missing_type_signals(text, problem_type)
            if structural["status"] != "PASS":
                print(f"FAIL: {problem_type} structural fixture failed", structural)
                return 1
            if density["status"] != "pass" or density["questions"][0]["pages"] != 8:
                print(f"FAIL: {problem_type} density fixture failed", density)
                return 1
            if density["questions"][0]["paragraphs"] < 4 or density["questions"][0]["formulas"] < 1:
                print(f"FAIL: {problem_type} fixture is not substantively located", density["questions"][0])
                return 1
            if missing:
                print(f"FAIL: {problem_type} positive fixture misses type signals", missing)
                return 1

            generic = "本问题较为复杂，因此采用常用模型进行求解，最后得到较好的结果。"
            missed = missing_type_signals(generic, problem_type)
            if len(missed) != len(TYPE_CONTRACTS[problem_type]):
                print(f"FAIL: {problem_type} generic model jump unexpectedly passed", missed)
                return 1

    print("PASS: A/B/C compact forward fixtures preserve distinct modeling interfaces.")
    print("NOTE: compact fixtures do not replace the separately recorded 25--30 page A/B/C blind tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
