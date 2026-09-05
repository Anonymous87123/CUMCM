#!/usr/bin/env python3
"""Audit repeated public reasoning scaffolds across long-form sections.

This is a conservative, read-only review signal.  It looks for the same
coarse sequence of visible paragraph actions in several substantive sections,
because a paper can avoid repeated words while still repeating one empty
argument skeleton.  It does not infer, expose, or request private chain of
thought, and it does not judge authorship or naturalness by itself.

Public interface:
    python audit_reasoning_scaffold.py <document.tex> --format text|json

Exit codes: 0=PASS, 2=REVIEW, 1=input error.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path
from typing import Iterable

from audit_voice_mode import Segment, parse_document


REPORT_SCHEMA = "aigc-reasoning-scaffold-audit/v1"

# These are public paragraph actions, not a prescribed drafting order.  The
# cues deliberately overlap a little; classification chooses the first action
# in ACTION_ORDER that occurs in a paragraph.
ACTION_CUES: dict[str, tuple[str, ...]] = {
    "basis": ("题面", "题目要求", "根据", "由图", "由表", "数据显示", "实测", "观测"),
    "phenomenon": ("现象", "趋势", "突增", "下降", "上升", "变化", "异常", "核心困难", "难点在于", "关键困难"),
    "limitation": ("不足", "局限", "缺点", "无法", "难以", "误差较大", "不适用", "不能解释", "基线不足", "基线方法的不足"),
    "comparison": ("候选", "备选", "基线", "比较", "对比", "多种方法", "不同模型", "候选比较", "候选模型", "方案比较", "基线方案"),
    "choice": ("选择", "选取", "采用", "确定", "保留", "舍弃", "改用", "选择依据", "选择原因", "据此选择", "最终选用"),
    "translation": ("变量", "参数", "目标函数", "约束", "可行域", "边界条件", "转化为", "数学化", "数学落点"),
    "model": ("建立模型", "构建模型", "模型建立", "模型为", "方程", "目标函数", "约束条件", "模型建立过程"),
    "solve": ("求解", "迭代", "遍历", "搜索", "算法", "计算得到", "数值解"),
    "result": ("结果", "得到", "求得", "最优值", "预测值", "拟合值", "输出"),
    "explanation": ("原因", "解释", "说明", "表明", "由于", "机制", "反映"),
    "validation": ("检验", "验证", "误差", "残差", "扰动", "敏感性", "稳健"),
    "interface": ("问题一", "问题二", "前一问", "后一问", "沿用", "复用", "输入"),
}
ACTION_ORDER = (
    "basis", "phenomenon", "limitation", "comparison", "choice", "translation",
    "model", "solve", "result", "explanation", "validation", "interface",
)
EXCLUDED_TITLE_TERMS = (
    "摘要", "关键词", "符号说明", "模型假设", "参考文献", "附录", "模型评价", "模型改进",
)
QUESTION_TITLE_RE = re.compile(r"问题|第[一二三四五六七八九十0-9]+问")


def _action(text: str) -> str | None:
    scores = {
        name: sum(text.count(cue) for cue in cues)
        for name, cues in ACTION_CUES.items()
    }
    # Specific public actions outrank broad words such as “约束” or “得到”.
    # This keeps “建立模型并求解” from being reduced to a generic
    # translation/result label.
    bonuses = {
        "model": ("建立模型", "构建模型", "模型建立", "模型为"),
        "solve": ("求解", "迭代求解", "数值求解", "搜索算法"),
        "validation": ("模型检验", "模型验证", "交叉验证", "敏感性分析"),
        "result": ("得到结果", "结果表明", "最终得到", "求得最优"),
        "comparison": ("候选方案", "备选方案", "基线方法", "不同模型"),
    }
    for name, phrases in bonuses.items():
        scores[name] += 3 * sum(text.count(phrase) for phrase in phrases)
    scores["model"] += 3 * len(re.findall(r"建立[^。；，,]{0,12}模型|构建[^。；，,]{0,12}模型", text))
    ranked = sorted(
        ((score, -ACTION_ORDER.index(name), name) for name, score in scores.items() if score),
        reverse=True,
    )
    return ranked[0][2] if ranked else None


def _sequence(segment: Segment) -> list[str]:
    sequence: list[str] = []
    for paragraph in segment.paragraphs:
        action = _action(paragraph.text)
        if action and (not sequence or sequence[-1] != action):
            sequence.append(action)
    return sequence


def _selected(segments: Iterable[Segment], mode: str) -> list[Segment]:
    output: list[Segment] = []
    for segment in segments:
        if mode == "auto" and segment.mode != "prose":
            continue
        title = segment.title_path.replace(" ", "")
        if any(term in title for term in EXCLUDED_TITLE_TERMS):
            continue
        if len(segment.paragraphs) < 3:
            continue
        sequence = _sequence(segment)
        if len(sequence) < 3:
            continue
        # Question/model sections are the intended target.  For a general
        # document, a sufficiently long prose section remains eligible.
        if QUESTION_TITLE_RE.search(title) or len(segment.paragraphs) >= 5:
            output.append(segment)
    return output


def _machine_like(sequence: tuple[str, ...]) -> bool:
    """Require a meaningful decision chain before raising a review signal."""
    has_decision = "comparison" in sequence
    has_model_path = "model" in sequence and ("solve" in sequence or "result" in sequence)
    has_basis_path = "basis" in sequence and ("translation" in sequence or "model" in sequence)
    return (has_decision and has_model_path) or (has_basis_path and "result" in sequence and "validation" in sequence)


def _lcs_length(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _sequence_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left or not right:
        return 0.0
    return _lcs_length(left, right) / max(len(left), len(right))


def audit(path: Path, mode: str = "auto") -> dict:
    text = path.read_text(encoding="utf-8-sig")
    segments = parse_document(text)
    selected = _selected(segments, mode)
    records: list[dict] = []
    grouped: dict[tuple[str, ...], list[dict]] = {}
    for segment in selected:
        sequence = tuple(_sequence(segment))
        record = {
            "section": segment.title_path,
            "line": segment.line,
            "paragraphs": len(segment.paragraphs),
            "action_sequence": list(sequence),
        }
        records.append(record)
        grouped.setdefault(sequence, []).append(record)

    findings: list[dict] = []
    for sequence, matches in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(matches) < 3 or not _machine_like(sequence):
            continue
        share = len(matches) / max(1, len(selected))
        # Three repetitions are required even in a short paper.  A larger
        # document must also have the sequence in a clear majority of eligible
        # sections before it is called a structural repetition.
        if len(selected) >= 5 and share < 0.6:
            continue
        findings.append({
            "severity": "review",
            "code": "REPEATED_REASONING_SCAFFOLD",
            "line": matches[0]["line"],
            "section": matches[0]["section"],
            "evidence": {
                "sequence": list(sequence),
                "repeated_sections": [item["section"] for item in matches],
                "repeat_count": len(matches),
                "eligible_sections": len(selected),
                "share": round(share, 3),
            },
            "suggestion": (
                "回到每一问的实际数据、失败尝试或推导转折，重组段落职责；"
                "不要只替换模型名称，也不要让所有分问按同一固定顺序推进。"
            ),
        })

    seen_near_groups: set[frozenset[str]] = set()
    record_sequences = [tuple(item["action_sequence"]) for item in records]
    for index, anchor in enumerate(record_sequences):
        if not _machine_like(anchor):
            continue
        matched_indices = [
            other_index
            for other_index, sequence in enumerate(record_sequences)
            if _sequence_similarity(anchor, sequence) >= 0.8
        ]
        if len(matched_indices) < 3:
            continue
        distinct = {record_sequences[item] for item in matched_indices}
        if len(distinct) < 2:
            continue
        group_key = frozenset(str(records[item]["section"]) for item in matched_indices)
        if group_key in seen_near_groups:
            continue
        share = len(matched_indices) / max(1, len(selected))
        if len(selected) >= 5 and share < 0.6:
            continue
        seen_near_groups.add(group_key)
        matches = [records[item] for item in matched_indices]
        findings.append({
            "severity": "review",
            "code": "NEAR_REPEATED_REASONING_SCAFFOLD",
            "line": records[index]["line"],
            "section": records[index]["section"],
            "evidence": {
                "anchor_sequence": list(anchor),
                "matched_sections": [item["section"] for item in matches],
                "sequences": [item["action_sequence"] for item in matches],
                "minimum_similarity": round(
                    min(_sequence_similarity(anchor, record_sequences[item]) for item in matched_indices), 3
                ),
                "repeat_count": len(matches),
                "eligible_sections": len(selected),
                "share": round(share, 3),
            },
            "suggestion": (
                "这些分问虽增删了个别动作，主体推进仍近似同一骨架。回到各问实际发生的观察、"
                "推导、试算或结果转折，改变段落职责和停止位置，不要只增删一段来制造差异。"
            ),
        })

    return {
        "schema": REPORT_SCHEMA,
        "status": "review" if findings else "pass",
        "document": str(path.resolve()),
        "mode": mode,
        "summary": {
            "segments_total": len(segments),
            "segments_eligible": len(selected),
            "distinct_sequences": len(grouped),
            "findings": len(findings),
        },
        "sections": records,
        "findings": findings,
        "disclaimer": (
            "Public structural review only; it does not identify AI authorship, "
            "measure naturalness, or reconstruct hidden chain-of-thought."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--mode", choices=("auto", "prose", "mixed"), default="auto")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if not args.document.is_file():
        parser.error(f"document not found: {args.document}")
    report = audit(args.document, args.mode)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["summary"]
        print(
            f"REASONING SCAFFOLD {report['status'].upper()} "
            f"eligible={summary['segments_eligible']} sequences={summary['distinct_sequences']} "
            f"findings={summary['findings']}"
        )
        for item in report["findings"]:
            print(
                f"[REVIEW] {item['code']} line={item['line']} section={item['section']}: "
                f"{json.dumps(item['evidence'], ensure_ascii=False)} | {item['suggestion']}"
            )
        print("NOTE: this checks visible paragraph structure only; it does not inspect private reasoning.")
    return 2 if report["status"] == "review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
