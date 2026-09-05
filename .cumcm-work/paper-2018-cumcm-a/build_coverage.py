#!/usr/bin/env python3
"""Build coverage.json: the per-question eight-interface checklist for the length gate.

Every evidence pattern must be findable inside that question's own label range, so a
question that skipped an interface cannot borrow another question's text to pass.
"""
from __future__ import annotations

import json
from pathlib import Path

W = Path(__file__).resolve().parent

QUESTIONS = [
    {
        "id": "Q1",
        "title": "在附件 2 的条件下算出温度分布并输出 Excel",
        "start_label": "mcm-q1-start",
        "end_label": "mcm-q1-end",
        "section_titles": [r"问题一模型建立与求解", r"模型建立", r"求解方法与实现", r"标定与本问结果"],
        "evidence": {
            "problem_data_basis": [r"附件 2 的 \$t=0\$ 读数", r"附件 1"],
            "variables_scope": [r"设四层总厚 \$L=", r"格心控制体"],
            "mathematical_relation": [r"\\label\{eq:pde\}", r"\\label\{eq:interface\}", r"\\label\{eq:robin\}"],
            "solver_implementation": [r"\\label\{eq:implicit\}", r"三对角系统", r"带状矩阵"],
            "result": [r"47\.9347", r"稳态界面温度依次为"],
            "interpretation": [r"空气层单独承担了总温降的六成", r"偏差集中在最初十分钟"],
            "validation": [r"两条互不依赖的路线", r"相差 \\SI\{1\.88\}"],
            "boundary": [r"该假设在升温初段偏强", r"残差结构如实报告"],
        },
    },
    {
        "id": "Q2",
        "title": "定第 II 层最优厚度（65 °C，60 min）",
        "start_label": "mcm-q2-start",
        "end_label": "mcm-q2-end",
        "section_titles": [r"问题二模型建立与求解", r"约束的瞬态表达", r"搜索层与求解", r"本问结果与小结"],
        "evidence": {
            "problem_data_basis": [r"附件 1 给定为", r"环境温度改为 \\SI\{65\}"],
            "variables_scope": [r"唯一新开放的量是 \$d_2\$", r"0\.6\\le d_2\\le 25"],
            "mathematical_relation": [r"\\label\{eq:crit\}", r"\\label\{eq:opt2\}"],
            "solver_implementation": [r"一维二分求得", r"最小可行厚度可由"],
            "result": [r"18\.16", r"44\.045", r"3302"],
            "interpretation": [r"紧的是五分钟预算", r"可行性不是由峰值直接决定"],
            "validation": [r"表~\\ref\{tab:mono\}", r"峰值随厚度单调不增"],
            "boundary": [r"可辨识性有严重限制", r"不把它当作可直接使用的设计值"],
        },
    },
    {
        "id": "Q3",
        "title": "同时定第 II、IV 层最优厚度（80 °C，30 min）",
        "start_label": "mcm-q3-start",
        "end_label": "mcm-q3-end",
        "section_titles": [r"问题三模型建立与求解", r"双目标的处理", r"可行性边界与前沿", r"本问结果与小结"],
        "evidence": {
            "problem_data_basis": [r"范围分别是", r"环境温度升到 \\SI\{80\}"],
            "variables_scope": [r"\$d_2\$ 与 \$d_4\$ 同时开放", r"\\label\{eq:feas3\}"],
            "mathematical_relation": [r"\\label\{eq:front3\}", r"d_2\^\{\*\}\(d_4\)=\\min"],
            "solver_implementation": [r"用问题二的二分求最小可行", r"扫描 \$d_4\$"],
            "result": [r"21\.188", r"27\.588", r"表~\\ref\{tab:front\}"],
            "interpretation": [r"空气层承担了总温降的六成", r"前沿单调"],
            "validation": [r"当 \$d_4\\le\\SI\{3\.6\}\{mm\}\$ 时", r"仍低于 \\SI\{47\}"],
            "boundary": [r"可交付结论是一条前沿与一条可行性边界", r"同一条可辨识性限制"],
        },
        "waivers": {
            "solver_implementation": "本问完整沿用问题一仿真器与问题二的二分，只新增第 IV 层为外层扫描量，"
                                     "不重复叙述离散与推进实现。",
        },
    },
]


def main() -> int:
    coverage = {
        "schema": "mcm-question-coverage/v1",
        "body_start_label": "mcm-body-start",
        "body_end_label": "mcm-body-end",
        "max_manual_page_breaks": 2,
        "questions": QUESTIONS,
    }
    out = W / "coverage.json"
    out.write_text(json.dumps(coverage, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}")
    for question in QUESTIONS:
        interfaces = question["evidence"]
        total = sum(len(v) for v in interfaces.values())
        print(f"  {question['id']}: {len(interfaces)} 类接口 / {total} 条锚点"
              f"{' / waiver ' + ','.join(question.get('waivers', {})) if question.get('waivers') else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
