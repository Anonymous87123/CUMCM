#!/usr/bin/env python3
"""Create bounded, source-derived development candidates for the scene matrix.

This is a fixture builder for the local benchmark, not a general humanizer. It
only applies case-specific edits recorded below and never reads another
candidate as input.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"fixture anchor not found: {old[:80]}")
    return text.replace(old, new, 1)


def _replace_many(text: str, replacements: list[tuple[str, str]]) -> str:
    """Apply several independently checked, single-use fixture edits."""
    result = text
    for old, new in replacements:
        result = _replace_once(result, old, new)
    return result


def rewrite(document_type: str, stem: str, trial: int, text: str) -> str:
    if trial not in (1, 2, 3):
        raise ValueError("trial must be 1, 2, or 3")

    if document_type == "modeling":
        if stem.startswith("draft-dev-01-"):
            old = "按我们的分析框架看，禁渔只是恢复链条的起点，后面能不能把收益留在系统内部，最终还得看水质、连通性、放流和入侵控制能不能跟上。"
            variants = [
                "按我们的分析框架看，禁渔只是让恢复链条重新启动的起点。链条启动以后，收益能不能留在系统内部，最终还得看水质、连通性、放流和入侵控制能不能跟上。",
                "按我们的分析框架看，禁渔只是恢复链条的起点。链条恢复以后，收益能不能留在系统内部，最终还得看水质、连通性、放流和入侵控制能不能跟上。",
                "按我们的分析框架看，禁渔只是恢复链条的起点；后续收益能不能留在系统内部，最终还得看四方面：水质、连通性、放流和入侵控制能不能跟上。",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-02-"):
            old = "熵权、CRITIC、等权和组合赋权得到的排序完全一致，围绕组合权重做 2000 次 $[0.85,1.15]$ 重归一扰动后，完整排序稳定率和“入侵情景最差”稳定率均为 100\\%。不同赋权下比较关系都没有改变，因此污染削弱禁渔收益、入侵进一步恶化系统状态的次序判断并不依赖某一套特定赋权。"
            variants = [
                "熵权、CRITIC、等权和组合赋权四种方法分别给出的排序完全一致。围绕组合权重做 2000 次 $[0.85,1.15]$ 重归一扰动后，完整排序稳定率和“入侵情景最差”稳定率均为 100\\%。不同赋权下比较关系都没有改变，因此污染削弱禁渔收益、入侵进一步恶化系统状态的次序判断并不依赖某一套特定赋权。",
                "熵权、CRITIC、等权和组合赋权得到的排序完全一致。对组合权重进行 2000 次 $[0.85,1.15]$ 重归一扰动后，完整排序以及“入侵情景最差”的稳定率均为 100\\%。不同赋权下比较关系都没有改变，因此污染削弱禁渔收益、入侵进一步恶化系统状态的次序判断并不依赖某一套特定赋权。",
                "熵权、CRITIC、等权和组合赋权给出的排序彼此相同。围绕组合权重做 2000 次 $[0.85,1.15]$ 重归一扰动后，完整排序稳定率和“入侵情景最差”稳定率均为 100\\%。不同赋权下各组比较关系都没有改变，因此污染削弱禁渔收益、入侵进一步恶化系统状态的次序判断并不依赖某一套特定赋权。",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-03-"):
            old = "我们在问题一中采用流域平均单区框架。2025 年四大家鱼恢复约 1.8 倍用于约束总量尺度，湖北段单网次捕获量提升 120\\% 保留为局地对照。当前能稳定约束模型的是全流域平均恢复事实，因此我们先在统一尺度下观测禁渔的直接效应。观测事实与模型变量的对应关系如表 \\ref{tab:q1_anchor} 所示。"
            variants = [
                "问题一继续采用流域平均单区框架。我们以 2025 年四大家鱼恢复约 1.8 倍约束总量尺度，把湖北段单网次捕获量提升 120\\% 留作局地对照。当前能稳定约束模型的是全流域平均恢复事实，因此我们先在统一尺度下观测禁渔的直接效应。观测事实与模型变量的对应关系如表 \\ref{tab:q1_anchor} 所示。",
                "问题一中，我们仍采用流域平均单区框架。2025 年四大家鱼恢复约 1.8 倍用来约束总量尺度；湖北段单网次捕获量提升 120\\% 则用作局地对照。当前能稳定约束模型的是全流域平均恢复事实，因此我们先在统一尺度下观测禁渔的直接效应。观测事实与模型变量的对应关系如表 \\ref{tab:q1_anchor} 所示。",
                "我们在问题一中采用流域平均单区框架。2025 年四大家鱼恢复约 1.8 倍用于约束总量尺度，湖北段单网次捕获量提升 120\\% 保留为局地对照。当前，全流域平均恢复事实能稳定约束模型，因此我们先在统一尺度下观测禁渔的直接效应。观测事实与模型变量的对应关系如表 \\ref{tab:q1_anchor} 所示。",
            ]
            return _replace_once(text, old, variants[trial - 1])

    if document_type == "course-notes":
        if stem.startswith("draft-dev-01-"):
            old = "为降低阅读混乱，本文将第 1-14 章作为最终主报告，第 15-21 章作为附录证据与操作手册。后文出现的“信息增益最大”“残余熵最低”等统计模型结论，只解释辅助价值，不替代第 14.1 节的最终实战口径。"
            variants = [
                "为避免主报告和附录混在一起，本文将第 1-14 章作为最终主报告，第 15-21 章作为附录证据与操作手册。后文出现的“信息增益最大”“残余熵最低”等统计模型结论，只解释辅助价值，不替代第 14.1 节的最终实战口径。",
                "本文将第 1-14 章作为最终主报告，第 15-21 章作为附录证据与操作手册，以降低阅读混乱。后文出现的“信息增益最大”“残余熵最低”等统计模型结论，只解释辅助价值，不替代第 14.1 节的最终实战口径。",
                "为降低阅读混乱，本文将文档分成两部分：第 1-14 章作为最终主报告，第 15-21 章作为附录证据与操作手册。后文出现的“信息增益最大”“残余熵最低”等统计模型结论，只解释辅助价值，不替代第 14.1 节的最终实战口径。",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-02-"):
            old = "**先看单题粗分布，再记容量，再找锚点；边缘带一出现就高度重视；\\CodeInline{Q36} 用来定区，\\CodeInline{Q44} 用来放大，\\CodeInline{Q38} 用来反推；前段看 \\CodeInline{Q37/Q39}，后段看 \\CodeInline{Q41/Q45}，中间靠条件规则缩窗，不要再按 \\CodeInline{36 -> 37 -> ... -> 45} 线性平推。**"
            variants = [
                "**处理顺序为：判断单题粗分布、登记容量、确定锚点；边缘带一出现就高度重视；\\CodeInline{Q36} 用来定区，\\CodeInline{Q44} 用来放大，\\CodeInline{Q38} 用来反推；前段看 \\CodeInline{Q37/Q39}，后段看 \\CodeInline{Q41/Q45}，中间靠条件规则缩窗，不要再按 \\CodeInline{36 -> 37 -> ... -> 45} 线性平推。**",
                "**单题粗分布、容量和锚点仍按既定次序处理。边缘带一出现就高度重视；\\CodeInline{Q36} 用来定区，\\CodeInline{Q44} 用来放大，\\CodeInline{Q38} 用来反推；前段看 \\CodeInline{Q37/Q39}，后段看 \\CodeInline{Q41/Q45}，中间靠条件规则缩窗，不要再按 \\CodeInline{36 -> 37 -> ... -> 45} 线性平推。**",
                "**先看单题粗分布，再记容量，再找锚点；边缘带一出现就高度重视。定区看 \\CodeInline{Q36}，放大看 \\CodeInline{Q44}，反推看 \\CodeInline{Q38}；前段看 \\CodeInline{Q37/Q39}，后段看 \\CodeInline{Q41/Q45}，中间靠条件规则缩窗，不要再按 \\CodeInline{36 -> 37 -> ... -> 45} 线性平推。**",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-03-"):
            old = "旧版本分析里之所以必须区分两层口径，是因为当时有\\CodeInline{3}篇 2024 年 6 月文章只有人工复核后的答案字母，没有可靠的标准化段落位置百分比。"
            if old not in text:
                old = "旧版本分析里之所以必须区分两层口径，是因为当时有 \\CodeInline{3} 篇 2024 年 6 月文章只有人工复核后的答案字母，没有可靠的标准化段落位置百分比。"
            variants = [
                "当时有 \\CodeInline{3} 篇 2024 年 6 月文章只有人工复核后的答案字母，没有可靠的标准化段落位置百分比；基于这一数据边界，旧版本分析所以必须区分两层口径。",
                "当时有 \\CodeInline{3} 篇 2024 年 6 月文章只有人工复核后的答案字母，没有可靠的标准化段落位置百分比；这正是旧版本分析之所以必须分别保留两层口径的原因。",
                "旧版本分析之所以必须将统计口径分成两层，数据边界在于：当时有 \\CodeInline{3} 篇 2024 年 6 月文章只有人工复核后的答案字母，没有可靠的标准化段落位置百分比。",
            ]
            return _replace_once(text, old, variants[trial - 1])

    if document_type == "research":
        if stem.startswith("draft-dev-01-"):
            old = "§4.3 建立了几何指标与终点的统计关联，但关联不等于归因。一个更强的检验是：当两种分组器在结构纯度与局部条件性上产生方向相反的排序时，终点究竟跟随哪一方？"
            variants = [
                "§4.3 建立了几何指标与终点的统计关联，但关联不等于归因。一个更强的检验是把两种排序正面放在一起：当两种分组器在结构纯度与局部条件性上产生方向相反的排序时，终点究竟跟随哪一方？",
                "§4.3 建立了几何指标与终点的统计关联，但关联不等于归因。一个更强的检验是把两种排序的冲突单独拿出来观察：当两种分组器在结构纯度与局部条件性上产生方向相反的排序时，终点究竟跟随哪一方？",
                "§4.3 建立了几何指标与终点的统计关联，但关联不等于归因。一个更强的检验是直接比较相反排序：当两种分组器在结构纯度与局部条件性上产生方向相反的排序时，终点究竟跟随哪一方？",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-02-"):
            old = "前文在数学层面建立了\"分组即子空间选择\"的映射（式~\\eqref{eq:subspace_hessian}--\\eqref{eq:elliptic_group_condition}），但这一映射是否在实际优化中产生可观测的后果，需要从最简单的可精确验证情形开始。"
            variants = [
                "式~\\eqref{eq:subspace_hessian}--\\eqref{eq:elliptic_group_condition} 在数学层面建立了\"分组即子空间选择\"的映射，但这一映射是否在实际优化中产生可观测的后果，需要从最简单的可精确验证情形开始。",
                "前文通过式~\\eqref{eq:subspace_hessian}--\\eqref{eq:elliptic_group_condition} 在数学层面建立了\"分组即子空间选择\"的映射。这一映射在实际优化中是否产生可观测的后果，需要从最简单的可精确验证情形开始判断。",
                "前文在数学层面建立了\"分组即子空间选择\"的映射（式~\\eqref{eq:subspace_hessian}--\\eqref{eq:elliptic_group_condition}）。要判断这一映射是否在实际优化中产生可观测的后果，需要先处理最简单而且可精确验证的情形。",
            ]
            return _replace_once(text, old, variants[trial - 1])
        if stem.startswith("draft-dev-03-"):
            opening = "本文的核心判断是：协同进化中的变量组不仅是交互集合，也是后端必须实际求解的诱导子问题。"
            closing = "由此得到的设计含义不是用几何替代交互，而是在保持交互结构之后，继续检查分组留给后端的局部条件性，并据此进行后续细化。"
            opening_variants = [
                "本文考察这样一个判断：协同进化中的变量组既是交互集合，也对应后端必须实际求解的诱导子问题。",
                "这里关注的判断是，协同进化中的变量组在构成交互集合的同时，也规定了后端必须实际求解的诱导子问题。",
                "协同进化中的变量组同时承担多重作用：它划定交互集合，也给后端规定了必须实际求解的诱导子问题。",
            ]
            closing_variants = [
                "由此得到的设计含义是，几何诊断不替代交互保持；交互结构得到保持后，还要检查分组留给后端的局部条件性，并据此继续细化。",
                "由此得到的设计含义是，设计时仍须先保持交互结构，随后检查分组留给后端的局部条件性。几何诊断用于补充这一检查，不代替交互信息。",
                "由此得到的设计含义是，交互保持与几何诊断承担不同职责：前者保留交互结构，后者检查分组留给后端的局部条件性，后续细化据此展开。",
            ]
            return _replace_many(
                text,
                [
                    (opening, opening_variants[trial - 1]),
                    (closing, closing_variants[trial - 1]),
                ],
            )

    raise ValueError(f"no fixture rewrite for {document_type} {stem}")


def build(input_dir: Path, output_dir: Path, document_type: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    for source in sorted(input_dir.glob("*.tex")):
        source_text = source.read_text(encoding="utf-8-sig")
        case_candidates: list[str] = []
        for trial in (1, 2, 3):
            target = output_dir / f"{source.stem}-t{trial}.tex"
            candidate = rewrite(document_type, source.stem, trial, source_text)
            if candidate == source_text:
                raise ValueError(f"candidate did not change source: {source.stem} t{trial}")
            case_candidates.append(candidate)
            target.write_text(candidate, encoding="utf-8")
            results.append(target)
        if len(set(case_candidates)) != 3:
            raise ValueError(f"candidate trials are not independent: {source.stem}")
    if len(results) != 9:
        raise ValueError(f"expected 9 candidates, produced {len(results)}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--document-type", choices=("modeling", "course-notes", "research"), required=True)
    args = parser.parse_args()
    results = build(args.input_dir.resolve(), args.output_dir.resolve(), args.document_type)
    print(f"MATRIX CANDIDATES READY document_type={args.document_type} candidates={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
