#!/usr/bin/env python3
"""Forward checks for evidence-led A/B/C modeling prose.

The fixtures are new prose, not excerpts from corpus papers.  They exercise
the public bridge from problem material to the first named method and the
guard against turning an internal selection ledger into manuscript headings.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from audit_manuscript import audit
from build_fulltext_style_corpus import SUSPICIOUS_OCR_FRAGMENTS
from query_style_patterns import (
    _fulltext_payload,
    _query_tokens,
    load_fulltext_records,
    load_holdout_record_ids,
    load_records,
    select_fulltext_records,
    select_records,
)


STYLE_FAILURE_CODES = {
    "MODEL_SELECTION_WITHOUT_LOCAL_BASIS",
    "QUESTION_MODEL_WITHOUT_LOCAL_BASIS",
    "EXPOSED_REASONING_LEDGER",
    "REPEATED_REASONING_CHAIN",
}

SKILL_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION = SKILL_ROOT / "references" / "forward-writing-calibration.md"
FULLTEXT_INDEX = SKILL_ROOT / "references" / "fulltext-style-index.jsonl"


def manuscript(analysis: str, modeling: str, result: str, extra: str = "") -> str:
    return rf"""\documentclass{{ctexart}}
\begin{{document}}
\begin{{abstract}}
本文围绕给定对象建立可复算模型，报告变量、约束、求解结果及适用边界。模型链与正文一致，结果仅限当前题设和给定数据。
\end{{abstract}}
\keywords{{数学建模；结果检验；约束}}
\section{{问题重述}}
题目给出对象、观测量和限制条件，要求确定相应参数并解释所得结果。
\section{{问题分析}}
{analysis}
\section{{模型假设}}
在题面规定的时间和空间范围内保持给定边界不变；未观测因素不作额外补造。
\section{{符号说明}}
记 $x$ 为待求状态，$t$ 为离散时刻，$J$ 为题面目标量；其余符号在首次列式处定义。
\section{{问题一模型建立与求解}}
{modeling}
\section{{结果分析与模型检验}}
{result}
\section{{灵敏度与稳健性分析}}
固定题面其余参数，只在给定范围内改变一个输入，并记录目标值、约束余量和决策是否切换。该检查只支持当前扰动范围。
\section{{模型评价与改进}}
现有模型保留了题面直接给出的结构，但未覆盖范围外的机制。若取得新增观测，应先更新对应参数，再按同一口径复算约束和结果。
{extra}
\begin{{thebibliography}}{{9}}
\bibitem{{fixture}} 测试资料编写组. 前向测试资料, 2026.
\end{{thebibliography}}
\appendix
\section{{附录}}
输入按题面顺序读取，主程序依次完成变量初始化、状态更新、约束检查和结果导出；测试使用固定参数，不声称复现真实赛题数值。
\end{{document}}
"""


GOOD_CASES = {
    "A": manuscript(
        analysis=(
            "相邻构件之间的距离始终保持不变，因此各构件的位置不能独立求取。"
            "给定前一构件末端后，下一端点是轨迹与定长圆的交点；交点可能不止一个，"
            "还要结合构件先后次序和运动方向筛选。首次越界只会发生在判据由负变正的相邻时段，"
            "没有必要从头以极小步长扫描。由此，本问先逐件递推位置，再在首次变号区间内加密时间。"
            "这里的数学入口由定长几何关系直接给出，不需要另造一段候选模型比较。"
        ),
        modeling=(
            "令第 $i$ 个端点为 $x_i(t)$。由相邻距离固定，有"
            "$\\lVert x_i(t)-x_{i-1}(t)\\rVert=L_i$。先求轨迹与定长圆的全部交点，"
            "再按构件次序、前进方向和局部连续性保留最近的可行根，逐件得到整条链的位置。"
            "越界判据在粗扫所得区间内单调变化，故只在该区间采用二分法确定首次事件时刻；"
            "区间宽度低于给定时间误差后停止。"
        ),
        result=(
            "粗扫把首次越界限制在两个相邻时刻之间，二分后区间宽度降到规定误差以内。"
            "将最终位置代回定长关系，各相邻距离残差均低于阈值。边界附近只有最先触发的构件改变符号，"
            "后续构件仍保留余量，因此该时刻可作为当前离散和筛根规则下的首次事件结果；"
            "这一检查不支持其他轨迹族。"
        ),
    ),
    "B": manuscript(
        analysis=(
            "每天的行动会同时改变节点、库存和现金，前一天的期末量正是下一天的初值。"
            "题面还规定负载上限、补给价格和终点期限，因此单独比较当天收益会漏掉后续可行性。"
            "在同一日期、节点和库存下，现金较少的方案不会优于现金较多的方案，可以据此删去被支配状态。"
            "本问先写完整状态更新，再在每一步检查负载、现金和期限；天气尚未发生时不读取未来序列。"
        ),
        modeling=(
            "令状态 $s_t=(v_t,w_t,f_t,c_t)$ 分别记录节点、水、食物和现金。"
            "由题面给出的行动消耗与购买价格可直接写出状态转移和可行动作集；"
            "终点期限及负载限制作为硬约束。状态满足逐期递推且具有重复子问题，"
            "因此采用动态规划保存每个状态的最大现金。对同一 $(t,v,w,f)$ 只保留现金最大的记录，"
            "并在下一日更新前删除违反硬约束的动作。"
        ),
        result=(
            "所得路线在所有日期上均满足负载和现金约束，终点库存与目标中的残值使用同一计价口径。"
            "与不作状态支配的完整枚举相比，终点现金一致，而保留状态数明显减少。"
            "沙暴日附近库存约束处于活跃状态，这解释了方案提前补给而不是临近耗尽再购买的原因。"
            "该结果是当前信息集下的策略，不把预先知道完整天气的离线解写成可实施决策。"
        ),
    ),
    "C": manuscript(
        analysis=(
            "附件以企业为记录单位，发票金额、作废标记和交易日期需要先按企业聚合；"
            "信誉等级是待预测标签，不能混入输入特征。部分企业缺少完整月份，若直接把半年合计与全年合计比较，"
            "企业规模差异会被缺失时长放大。先统一观察窗口并保存缺失月份数，再从训练企业中划出独立测试集。"
            "题目最终需要违约概率而不是硬分类，因此评价时同时查看概率排序和少数类召回。"
        ),
        modeling=(
            "按企业汇总有效进项、有效销项、交易月份数和作废比例，并在训练集内完成缺失处理与标准化。"
            "标签只有违约与未违约两类，目标输出要求落在 $[0,1]$，故采用 Logistic 回归估计违约概率。"
            "预处理参数只在训练折拟合，测试集仅作变换；分类阈值在验证折按题面误判代价确定，"
            "最终冻结后再计算测试指标。"
        ),
        result=(
            "测试集上的概率输出均位于零与一之间。混淆矩阵显示少数类仍有漏判，因而正文分别报告总体准确率、"
            "少数类召回和概率排序指标，不以单一准确率概括模型。高风险企业主要同时具有交易月份短和作废比例高的特征，"
            "这一解释来自同一拟合模型的系数方向，只在当前字段口径内成立；它不构成违约原因的因果判断。"
        ),
    ),
}


BAD_CASES = {
    "airdrop": manuscript(
        analysis=(
            "问题涉及多个因素，求解过程较为复杂。为了得到较好的结果，本文采用粒子群优化算法求解。"
        ),
        modeling="采用粒子群优化算法得到最优方案。",
        result="计算得到一个数值结果，并据此给出方案。该结果可供本题决策使用。",
    ),
    "ledger": manuscript(
        analysis="题目给出若干变量和目标，本文将按照下列步骤完成建模。",
        modeling="采用遗传算法求解。",
        result="算法输出当前候选解，结果列于正文。",
        extra=(
            "\\subsection{核心困难}变量较多。"
            "\\subsection{基线方案}先考虑线性规划。"
            "\\subsection{模型不足}基线精度不够。"
            "\\subsection{候选方案}比较多个算法。"
            "\\subsection{选择依据}遗传算法求解方便。"
        ),
    ),
}


RETRIEVAL_CASES = (
    {
        "label": "A-analysis",
        "problem_type": "A",
        "section": "analysis",
        "queries": ["coarse-to-fine", "多根"],
        "expected_action": "coarse-to-fine",
    },
    {
        "label": "A-model",
        "problem_type": "A",
        "section": "model",
        "queries": ["constraint-translation", "守恒"],
        "expected_action": "constraint-translation",
    },
    {
        "label": "A-result",
        "problem_type": "A",
        "section": "result",
        "queries": ["result-explanation", "事件"],
        "expected_action": "result-explanation",
    },
    {
        "label": "A-validation",
        "problem_type": "A",
        "section": "validation",
        "queries": ["validation", "误差"],
        "expected_action": "validation",
    },
    {
        "label": "B-analysis",
        "problem_type": "B",
        "section": "analysis",
        "queries": ["model-selection", "信息"],
        "expected_action": "model-selection",
    },
    {
        "label": "B-model",
        "problem_type": "B",
        "section": "model",
        "queries": ["constraint-translation", "可行"],
        "expected_action": "constraint-translation",
    },
    {
        "label": "B-solve",
        "problem_type": "B",
        "section": "solve",
        "queries": ["state-progression", "库存"],
        "expected_action": "state-progression",
    },
    {
        "label": "B-validation",
        "problem_type": "B",
        "section": "validation",
        "queries": ["validation", "扰动"],
        "expected_action": "validation",
    },
    {
        "label": "C-analysis",
        "problem_type": "C",
        "section": "analysis",
        "queries": ["interface-reuse", "缺失"],
        "expected_action": "interface-reuse",
    },
    {
        "label": "C-model",
        "problem_type": "C",
        "section": "model",
        "queries": ["constraint-translation", "字段"],
        "expected_action": "constraint-translation",
    },
    {
        "label": "C-result",
        "problem_type": "C",
        "section": "result",
        "queries": ["result-explanation", "字段"],
        "expected_action": "result-explanation",
    },
    {
        "label": "C-validation",
        "problem_type": "C",
        "section": "validation",
        "queries": ["validation", "样本"],
        "expected_action": "validation",
    },
)


FULLTEXT_RETRIEVAL_CASES = (
    {"label": "A-solve-fdm", "problem_type": "A", "section": "solve", "model": "有限差分", "query": "解析解", "action": "choice"},
    {"label": "A-model-boundary", "problem_type": "A", "section": "model", "model": None, "query": "边界", "action": "derivation"},
    {"label": "B-analysis-feasible", "problem_type": "B", "section": "analysis", "model": None, "query": "约束", "action": "choice"},
    {"label": "B-solve-state", "problem_type": "B", "section": "solve", "model": None, "query": "状态", "action": "algorithm"},
    {"label": "C-model-logistic", "problem_type": "C", "section": "model", "model": "Logistic回归", "query": "概率", "action": "choice"},
    {"label": "C-result-residual", "problem_type": "C", "section": "result", "model": None, "query": "残差", "action": "explanation"},
)


def clean_retrieval_payload(item: dict) -> bool:
    texts = [str(item.get("text", ""))]
    for key in ("previous_context", "next_context"):
        texts.extend(str(row.get("text", "")) for row in item.get(key, []))
    joined = "\n".join(texts)
    return bool(
        item.get("quality") == "high"
        and item.get("retrieval_eligible")
        and len(str(item.get("text", ""))) >= 30
        and "关键词" not in joined
        and "关键字" not in joined
        and not any(fragment in joined for fragment in SUSPICIOUS_OCR_FRAGMENTS)
    )


def finding_codes(tex: str, problem_type: str) -> tuple[dict, set[str]]:
    with tempfile.TemporaryDirectory(prefix="mcm-style-forward-") as temp_dir:
        path = Path(temp_dir) / "main.tex"
        path.write_text(tex, encoding="utf-8")
        report = audit(path, problem_type)
    return report, {item["code"] for item in report["findings"]}


def han_text(text: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fff]", text))


def calibration_checks() -> list[str]:
    failures: list[str] = []
    if not CALIBRATION.is_file():
        return ["forward-writing calibration document is missing"]
    text = CALIBRATION.read_text(encoding="utf-8")
    case_markers = {
        "A": ("## A 类：", "## B 类：", "三个测点", "由能量收支"),
        "B": ("## B 类：", "## C 类：", "最近点试排", "混合整数规划"),
        "C": ("## C 类：", "## 校准结论", "预测对象是企业", "Logistic 回归"),
    }
    for problem_type, (start, end, basis, method) in case_markers.items():
        if start not in text or end not in text:
            failures.append(f"CALIBRATION-{problem_type}: case boundary is missing")
            continue
        section = text.split(start, 1)[1].split(end, 1)[0]
        if basis not in section or method not in section or section.index(basis) >= section.index(method):
            failures.append(f"CALIBRATION-{problem_type}: method appears before local problem evidence")
        prose_paragraphs = [
            han_text(paragraph)
            for paragraph in re.split(r"\n\s*\n", section)
            if len(han_text(paragraph)) >= 45 and not paragraph.lstrip().startswith(("检索锚点", "测试事实"))
        ]
        if len(prose_paragraphs) < 3 or len({len(paragraph) // 20 for paragraph in prose_paragraphs}) < 2:
            failures.append(f"CALIBRATION-{problem_type}: paragraph rhythm is artificially uniform")

    mechanical = ("核心困难", "基线方案", "基线不足", "候选比较", "选择依据")
    if any(f"### {heading}" in text or f"## {heading}" in text for heading in mechanical):
        failures.append("CALIBRATION: exposed reasoning-ledger headings remain")

    corpus = "\n".join(
        json.loads(line)["text"]
        for line in FULLTEXT_INDEX.open(encoding="utf-8")
        if line.strip()
    )
    calibration_han = han_text(text)
    copied = next(
        (
            calibration_han[index:index + 20]
            for index in range(max(0, len(calibration_han) - 19))
            if calibration_han[index:index + 20] in corpus
        ),
        None,
    )
    if copied:
        failures.append(f"CALIBRATION: contains a 20-Han-character corpus copy: {copied}")
    return failures


def main() -> int:
    failures: list[str] = []
    calibration_failures = calibration_checks()
    print(
        "CALIBRATION-A/B/C: "
        + ("PASS: evidence precedes methods, rhythm varies, no 20-character corpus copy"
           if not calibration_failures else "FAIL")
    )
    failures.extend(calibration_failures)
    records = load_records()
    for case in RETRIEVAL_CASES:
        label = case["label"]
        problem_type = case["problem_type"]
        selected = select_records(
            records,
            problem_type,
            None,
            case["section"],
            _query_tokens(case["queries"], ""),
            3,
        )
        anchors = [record.paper for _, record in selected]
        correct_type = all(record.problem_type == problem_type for _, record in selected)
        retrievable = bool(selected) and all(
            record.language_notes for _, record in selected
        )
        action_hit = any(
            case["expected_action"] in record.action_tags for _, record in selected
        )
        print(
            f"RETRIEVE-{label}: anchors={anchors} type_ok={correct_type} "
            f"action_hit={action_hit} language_notes={retrievable}"
        )
        if not selected or not correct_type or not action_hit or not retrievable:
            failures.append(
                f"RETRIEVE-{label}: no usable anchor for "
                f"{case['section']}/{case['expected_action']}"
            )

    fulltext_records = load_fulltext_records("high")
    heldout_ids = load_holdout_record_ids()
    fulltext_with_holdout = load_fulltext_records("high", include_reserved_holdout=True)
    default_ids = {str(record["id"]) for record in fulltext_records}
    all_ids = {str(record["id"]) for record in fulltext_with_holdout}
    holdout_ok = bool(heldout_ids) and not (default_ids & heldout_ids) and heldout_ids <= all_ids
    print(
        f"HOLDOUT-RETRIEVAL: reserved={len(heldout_ids)} "
        f"default_visible={len(default_ids & heldout_ids)} "
        f"explicit_visible={len(all_ids & heldout_ids)}"
    )
    if not holdout_ok:
        failures.append("HOLDOUT-RETRIEVAL: default retrieval leaked a sealed benchmark record")
    for case in FULLTEXT_RETRIEVAL_CASES:
        selected = select_fulltext_records(
            fulltext_records,
            case["problem_type"],
            None,
            case["section"],
            _query_tokens([case["action"]], case["query"]),
            case["model"],
            3,
        )
        payloads = [
            _fulltext_payload(score, record, fulltext_records, 1)
            for score, record in selected
        ]
        correct = bool(payloads) and all(
            item["problem_type"] == case["problem_type"]
            and clean_retrieval_payload(item)
            for item in payloads
        )
        contextual = any(
            item.get("previous_context") or item.get("next_context")
            for item in payloads
        )
        action_hit = any(case["action"] in item.get("actions", []) for item in payloads)
        print(
            f"FULLTEXT-{case['label']}: anchors={[item['paper'] for item in payloads]} "
            f"clean={correct} context={contextual} action_hit={action_hit}"
        )
        if not correct or not contextual or not action_hit:
            failures.append(
                f"FULLTEXT-{case['label']}: no clean contextual paragraph with the requested public action"
            )

    for problem_type, tex in GOOD_CASES.items():
        report, codes = finding_codes(tex, problem_type)
        unexpected = sorted(codes & STYLE_FAILURE_CODES)
        print(
            f"GOOD-{problem_type}: status={report['status']} "
            f"errors={report['errors']} warnings={report['warnings']} "
            f"style_failures={unexpected}"
        )
        if report["errors"] or unexpected:
            failures.append(f"GOOD-{problem_type}: errors={report['errors']} {unexpected}")

    _, airdrop_codes = finding_codes(BAD_CASES["airdrop"], "A")
    airdrop_expected = {
        "MODEL_SELECTION_WITHOUT_LOCAL_BASIS",
        "QUESTION_MODEL_WITHOUT_LOCAL_BASIS",
    }
    print(f"BAD-airdrop: detected={sorted(airdrop_codes & airdrop_expected)}")
    if not airdrop_expected <= airdrop_codes:
        failures.append("BAD-airdrop did not trigger both model-airdrop checks")

    _, ledger_codes = finding_codes(BAD_CASES["ledger"], "B")
    print(f"BAD-ledger: detected={sorted(ledger_codes & {'EXPOSED_REASONING_LEDGER'})}")
    if "EXPOSED_REASONING_LEDGER" not in ledger_codes:
        failures.append("BAD-ledger did not trigger EXPOSED_REASONING_LEDGER")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: A/B/C evidence-led prose accepted; two mechanical counterexamples rejected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
