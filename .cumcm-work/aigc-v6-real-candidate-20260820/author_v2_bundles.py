from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUN = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\humanize-run")
REWRITES = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\rewrites-v2")
HELPER = Path(r"C:\Users\Lenovo\.codex\skills\AIGC\humanize-academic-chinese\scripts\build_humanize_rewrite_intent.py")


SET_LINES: dict[str, dict[int, str]] = {
    "U-e276c4b22163": {
        3: "长江十年禁渔实施后，四大家鱼资源量回升，长江江豚和长江鲟种群亦呈恢复态势；资源枯竭、江湖连通性受阻、水体污染与外来物种入侵却仍同时存在。为回答[[PROTECTED:F00001-P00020:1bf922abc75b]]，本文把流域平均食物网、珍稀物种响应、Hastings-Powell三级食物链和综合情景评价置于同一分层动力学模型中，考察禁渔收益从基础资源层向经济鱼类、珍稀物种及长期动力学行为传递时发生的变化。",
        5: "问题一按食性保留四类基础资源与四大家鱼功能群的配对关系，用2025年四大家鱼资源量恢复至禁渔前1.8倍标定唯一增益参数，湖北江段单网次渔获量提升120[[PROTECTED:F00001-P00021:fed3f9917a84]]作为局地对照。结果显示：2025年四大家鱼总生物量为禁渔前的1.805倍，单位捕捞努力量渔获量([[PROTECTED:F00001-P00022:23f77b65545d]])为1.838倍；摄食压力指数升至4.213时，基础资源量末值降至0.204。鱼群恢复与基础资源承压由此同时出现。",
        7: "问题二接收问题一的资源--鱼群轨迹，以综合生态状态指数调节中层猎物承载力，并设置高阻隔、无人工放流和污染三种对照情景。基线情景下，长江江豚与长江鲟种群末值为禁渔前的1.133倍和1.140倍；高阻隔情景降至0.901倍和0.856倍，无人工放流时长江鲟降至0.519倍，污染情景下二者为0.610倍和0.704倍。结果显示，通道阻隔同时压低两类物种，放流变化则主要作用于长江鲟。",
        9: "问题三、四共用Hastings-Powell三级食物链。承载力参数[[PROTECTED:F00001-P00023:68e2c657635f]]增大时，轨道由规则有界振荡转为复杂非线性波动；代表点[[PROTECTED:F00001-P00024:8abaee131413]]、[[PROTECTED:F00001-P00025:5ff9d8c4624c]]、[[PROTECTED:F00001-P00026:347344e4b868]]的峰谷差和峰间隔离散程度均增大。短时间窗分析显示，首个连续正李雅普诺夫指数区间位于[[PROTECTED:F00001-P00027:79ea035e4a4b]]附近，但75组扩展测试中仅5组在[[PROTECTED:F00001-P00028:168e50c07661]]区间保留由负转正。故本文仅保留[[PROTECTED:F00001-P00029:835020a288b6]]的方向性结论。",
        11: "问题五在同一积分后期时间窗内比较饵料资源、长江江豚、长江鲟和入侵压力，熵权与CRITIC权重取平均后得到三种情景得分0.662、0.423和0.155。组合权重经2000次局部扰动，情景排序稳定率仍为100[[PROTECTED:F00001-P00030:fed3f9917a84]]。这一递减次序对应[[PROTECTED:F00001-P00031:62879cc62c2c]]。",
        13: "十年禁渔已经带来资源恢复，但资源量回升并不等同于系统整体健康改善。若不同步推进水质治理、江湖连通性修复、珍稀物种定向放流与入侵防控，禁渔收益在向高营养级传递及多重压力叠加过程中仍可能逐步减弱。",
    },
    "U-b1bac710ec42": {
        2: "长江流域淡水渔业发达，生物多样性丰富，长期过度捕捞、工业废水、水域塑料污染以及葛洲坝、三峡大坝等水利工程也在这里叠加。洄游通道受阻后，渔业资源持续衰退，典型食物链随之退化。长江流域自2021年1月1日实施十年禁渔，局部水域水质和水生植被已有恢复；2025年监测数据显示，青、草、鲢、鳙四大家鱼资源量约为禁渔前的1.8倍，表明禁渔已带来资源恢复。",
        4: "生态系统的恢复并非总是朝着良性方向发展。部分水域鱼类数量增长过快，水生植物和浮游动物受到过度摄食，水体浑浊、底栖植被减少，甚至出现[[PROTECTED:F00001-P00034:63ff7ce174e2]]。长江江豚数量已回升至约1249头，2024年又发现长江鲟自然繁殖产卵场；鳄雀鳝、巴西龟等外来物种则已在鄱阳湖等支流湖泊定殖。十年禁渔后的系统未必更加健康，营养级失衡、连通性不足与入侵扩散同时存在，因此有必要分别衡量[[PROTECTED:F00001-P00035:b23235f6f26a]]和[[PROTECTED:F00001-P00036:606b83393623]]。[[PROTECTED:F00001-P00037:d8bd05442937]]。",
        6: "题目提出的五个子问题依次为：",
        14: "全文的时间口径统一为：2021年作为政策启动基准年，2022年采用公报基准，2025年用于对照恢复效果[[PROTECTED:F00001-P00045:a643eb0599d3]]。",
    },
    "U-3644a855b083": {
        2: "四大家鱼回升、江豚回暖和长江鲟产卵场重现都指向禁渔后的恢复；[[PROTECTED:F00001-P00048:548f0dae3d29]]、通道受阻和入侵扩散又说明，单项资源量不足以解释收益在不同营养级和不同外部压力下的去向。我们因此不把注意力停在单项资源量上，分析转向收益所处的层级和压力来源。",
        4: "五问并不彼此独立。问题一定位恢复发生在哪一层，问题二考察资源端的变化能否传到珍稀物种；问题三把短期响应压缩成Hastings-Powell食物链，问题四用初值敏感性检验其长期行为；问题五把污染和入侵加入已有状态方程，比较剩余收益。全文因此把[[PROTECTED:F00001-P00049:79320a5a864f]]与[[PROTECTED:F00001-P00050:2fcb00ec96a9]]分别落在对应的计算环节。",
    },
    "U-c530201b41a9": {
        2: "若把四大家鱼合并为单一消费者，并把水草、浮游植物、浮游动物和底栖饵料压成一个资源总量，2025年的1.8倍总量仍能匹配，但无法区分[[PROTECTED:F00001-P00052:58402c67cc2e]]背后的[[PROTECTED:F00001-P00053:db1a17b596e9]]和[[PROTECTED:F00001-P00054:85bcf7648871]]，也难以解释[[PROTECTED:F00001-P00055:63ff7ce174e2]]为何同时出现。因此，食性配对必须留在模型中，用各自的资源轨迹判断哪一层较早承压。",
    },
    "U-769818cb13c6": {
        2: "在2022公报归一化口径下，基线情景的江豚和长江鲟末值为1.133和1.140。若只增强通道阻隔、暂不叠加额外污染，二者降至0.901和0.856。把长江鲟放流项置为[[PROTECTED:F00001-P00327:9525c29eb6c7]]后，长江鲟降至0.519，而江豚仅变为1.145；污染情景下，两者又降至0.610和0.704。通道约束同时压低两类物种，放流变化主要落在长江鲟上。表中报告江豚和长江鲟终态，[[PROTECTED:F00001-P00328:297422400257]]与[[PROTECTED:F00001-P00329:da8c27c394be]]留作后文解释过程差异。",
        19: "这些对照对应的机制各有差异。无放流时，长江鲟大幅下降而江豚变化很小，说明人工补偿主要作用于鲟类而不是江豚；高阻隔与污染情景同时压低两类物种，说明连通性和环境质量属于共性约束。作为定性验证，模型在[[PROTECTED:F00001-P00353:6c771f33ef65]]（对应2024年）时已有[[PROTECTED:F00001-P00354:1206f8584523]]，与题目所述[[PROTECTED:F00001-P00355:769a72493158]]这一事实方向一致。",
    },
    "U-706e53781d8d": {
        2: "基准时间窗下，[[PROTECTED:F00001-P00527:9f29cf8b0723]]先在1.4--4.8粗网格上扫描，再在3.0--3.4加密。首个连续正区间位于[[PROTECTED:F00001-P00528:79ea035e4a4b]]附近，3.22--3.40保持为正。表[[PROTECTED:F00001-P00529:717636cdb304]]表明，在总积分时长为90时，[[PROTECTED:F00001-P00530:1eb5f6b24dc1]]与[[PROTECTED:F00001-P00531:b01b2de0eb38]]之间的符号跨越在相邻步长和微扰初值下仍可保留。",
        22: "积分时长改变后，短窗口给出的起点发生移动。时长150时，3.0--3.4加密区间全部为正；时长200时，连续正区间从3.11开始，[[PROTECTED:F00001-P00563:09e4c7b48116]]、[[PROTECTED:F00001-P00564:dd38aaeb36eb]]也都为正。由5组初值、5个步长和3个积分时长组成的75组测试中，仅5组（6.7[[PROTECTED:F00001-P00565:fed3f9917a84]]）保留[[PROTECTED:F00001-P00566:fc0de2237c09]]。该局部跨越在扩展设置下不具备统计稳健性。",
        24: "基准短时间窗下，[[PROTECTED:F00001-P00567:79ea035e4a4b]]附近出现局部跨越；积分时长和数值设置放宽后，这个跨越不能稳定保持，因此[[PROTECTED:F00001-P00568:79ea035e4a4b]]不能作为唯一临界点。本文据此只保留[[PROTECTED:F00001-P00569:e9e04c2a63fe]]的方向性判断；若要定位分岔值，仍须采用更长积分时长（[[PROTECTED:F00001-P00570:a2c261c51172]]）并配合分岔图。图[[PROTECTED:F00001-P00571:9ade67a4bf97]]给出不同积分时长下的有限时间指数。",
    },
    "U-0801ec99dfa8": {
        2: "表[[PROTECTED:F00001-P00593:d1b423f13441]]列出[[PROTECTED:F00001-P00590:482dd270ef0d]]、[[PROTECTED:F00001-P00591:b3d11737c110]]和[[PROTECTED:F00001-P00592:90e55c9bb796]]的尾窗均值。三类指标并不同步：综合得分依次为0.662、0.423和0.155；与仅禁渔相比，污染情景的食源由0.407升至0.692，江豚和长江鲟却降至0.636和0.716；污染上再加入侵后，入侵压力达到0.641，综合得分继续下降。",
        36: "污染情景中食源指标抬升而江豚、长江鲟同步下降，反映的是当前参数组下的捕食释放机制。方程中，[[PROTECTED:F00001-P00645:a924f6a91c69]]一方面下压[[PROTECTED:F00001-P00646:7ea51720f73f]]，另一方面以较大幅度抬升两类珍稀物种的死亡项；后者造成的捕食减少在尾窗内超过了承载损失，于是[[PROTECTED:F00001-P00647:297422400257]]均值短时回升。这个回升只对应过程量的再分配，不意味着污染改善了系统健康。",
        38: "熵权、CRITIC、等权和组合赋权得到同一排序，组合权重经2000次[[PROTECTED:F00001-P00648:ee02ca822908]]重归一扰动后，完整排序稳定率与[[PROTECTED:F00001-P00649:cccd32f92b9d]]稳定率均为100[[PROTECTED:F00001-P00650:fed3f9917a84]]。不同赋权下比较关系都没有改变，因此污染削弱禁渔收益、入侵继续增加压力的次序判断并不依赖某一套特定赋权。",
    },
    "U-8f28215ff44b": {
        2: "问题一中，四大家鱼恢复上升，水草、浮游动物和底栖饵料却可能下降；问题二中，江豚与长江鲟对通道和放流的响应又不一样。治理重点不能只停留在捕捞约束本身。后续监测最好同时列出四大家鱼总量、底层资源指标和食压指数；鱼道修复、产卵场连通及放流节律也不宜按同一办法处理。",
        4: "更迫切的，是把污染治理和入侵控制往前提。问题五中，污染情景的部分食源过程量短时上升，珍稀物种终态和综合得分却在下降，所以局部过程变好并不等于系统整体好转。对入侵物种，可把鄱阳湖等支流湖泊作为高风险前沿，优先布设早期监测、拦截和清除，避免其沿食物网空档扩散。禁渔只是减轻了捕捞压力；如果水质治理、通道修复、放流优化和入侵防控接不上，恢复收益仍留不住。",
    },
}


REPLACE_OPS: dict[str, dict[int, list[tuple[str, str]]]] = {
    "U-d92f7920cc9c": {2: [("更直接依赖", "直接依赖")]},
    "U-b39b5bae86b9": {2: [("能稳定约束模型", "能够约束模型")]},
    "U-ab841ce78d7e": {19: [("并未同步改善基础资源状况", "并未随基础资源状况一同改善"), ("需要说明的是，", "")]},
    "U-d5ace5fbd128": {2: [("变量[[PROTECTED:F00001-P00259:297422400257]]不再直接对应四大家鱼", "变量[[PROTECTED:F00001-P00259:297422400257]]不再以四大家鱼作为对应对象")], 27: [("会更接近单纯的鱼群恢复指标", "会趋近于单纯的鱼群恢复指标")]},
    "U-e0a2391b9668": {2: [("进行归一化", "进行一次归一化")]},
    "U-1c40fab058d2": {2: [("需要重新由问题一积分得到", "需要再次由问题一积分得到")], 4: [("会诱发更明显的波动", "会诱发幅度较大的波动")]},
    "U-f7a8bf218cc3": {2: [("这是最先看到的正向结果；但继续往下看", "这是较早看到的正向结果；但同时看到")]},
    "U-a04d7bcfaa34": {2: [("这一结构更接近按食性配对的并联系统", "这一结构接近按食性配对的并联系统")]},
    "U-0a061a5b1e24": {2: [("基准设置下，我们首先看到", "基准设置下，我们看到")]},
    "U-015593fe61e9": {4: [("排序结论的外推边界会更清楚", "排序结论的外推边界会得到明确界定")], 6: [("还能保留多少", "还能留下多少")], 8: [("可以继续推进到分段比较", "可以扩展为分段比较"), ("建立更稳定的对应关系", "建立较为稳固的对应关系")]},
}


NO_CHANGE: dict[str, tuple[str, tuple[int, int]]] = {
    "U-05e9265c162b": ("问题三分析保留了降维原因和后期统计判据，段落职责是说明模型简化的依据。", (2, 4)),
    "U-88f91474a945": ("该段落中的条件句限定积分时长、步长和初值，保留其范围说明与数值判别职责。", (2, 4)),
    "U-deaaf69e6551": ("问题五分析区分四类指标与赋权复核，原段承担情景评价范围说明。", (2, 4)),
    "U-274fd3d47e04": ("模型假设逐项限定时间尺度、功能群、扰动方式和归一化范围，列表承担边界声明。", (2, 8)),
    "U-aa70d7ac67ab": ("符号表按变量逐行给出定义和口径，等权表格结构便于后文查找。", (7, 20)),
    "U-46fd651c1f35": ("该段落区分观测约束、反事实参数和局地对照，保留参数说明职责与反事实条件。", (2, 6)),
    "U-e405341c61e6": ("敏感性段落紧邻参数表解释响应对象和幅度，现有结构承担数值结果读取。", (2, 22)),
    "U-e2ef47edd600": ("三级食物链段保留营养级映射与参数来源，现有结构承担模型定义职责。", (2, 8)),
    "U-812ffef31ba1": ("问题三结果按时间窗、统计表和轨道解释展开，现有顺序承担数值比较职责。", (2, 23)),
    "U-7da5048ae9fc": ("珍稀物种评价同时给出参数响应和结构限制，原段承担归因边界说明。", (2, 4)),
    "U-70772ee7e6a7": ("长期行为评价区分营养级映射和河段阈值，原段承担适用范围限定。", (2, 4)),
    "U-39b744730e0f": ("参考文献命令与附录标题属于文档结构接口，保持原有位置和排版职责。", (1, 7)),
    "U-b8766a969759": ("参数附表按来源、默认值和角色逐项列示，表格结构承担复现查询职责。", (10, 33)),
}


KEEP_REASONS: dict[str, dict[str, str]] = {
    "U-8f28215ff44b": {
        "LEX-STRICT-CORPUS-OUTLOOK-01": "该命中位于受保护的正式章节标题“治理建议”，标题对应题目要求并承担目录定位功能。"
    }
}


def helper_intent(unit_id: str, start: int, end: int, summary: str, signals: list[str]) -> dict:
    cmd = [sys.executable, str(HELPER), "--run-dir", str(RUN), "--unit-id", unit_id,
           "--start-line", str(start), "--end-line", str(end), "--operation-kind", "REWRITE_MODELING_PROSE"]
    for signal in signals:
        cmd.extend(["--target-signal", signal])
    cmd.extend(["--summary", summary, "--format", "json"])
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(proc.stdout)["rewrite_intent"]


def combine_intents(unit_id: str, lines: list[int]) -> dict:
    summary = "按冻结事实调整段落组织或词壳，并保留原有限定与判断关系"
    signals = ["SCENE-MODELING-JUDGMENT-PRESERVE", "RHYTHM-VARY-SECTION-ACTION"]
    operations: list[dict] = []
    spans: list[dict] = []
    for index, line_no in enumerate(sorted(lines), start=1):
        fragment = helper_intent(unit_id, line_no, line_no, summary, signals)
        span = fragment["source_spans"][0]
        span["id"] = f"S{index}"
        operation = fragment["operations"][0]
        operation["id"] = f"O{index}"
        operation["source_span_ids"] = [f"S{index}"]
        spans.append(span)
        operations.append(operation)
    return {"summary": summary, "operations": operations, "source_spans": spans, "target_signals": signals}


def evidence_span(unit_id: str, start: int, end: int) -> dict:
    fragment = helper_intent(unit_id, start, end, "绑定保留段落的具体职责与原文范围", ["STYLE-FUNCTIONAL-NO-CHANGE"])
    span = fragment["source_spans"][0]
    span["id"] = "S1"
    return span


def edit_bundle(unit_id: str, set_lines: dict[int, str] | None = None, replacements: dict[int, list[tuple[str, str]]] | None = None) -> None:
    path = REWRITES / f"{unit_id}.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    lines = bundle["masked_text"].splitlines(keepends=True)
    changed_lines: set[int] = set()
    for line_no, value in (set_lines or {}).items():
        suffix = "\n" if lines[line_no - 1].endswith("\n") else ""
        lines[line_no - 1] = value + suffix
        changed_lines.add(line_no)
    for line_no, pairs in (replacements or {}).items():
        text = lines[line_no - 1]
        for old, new in pairs:
            if text.count(old) == 1:
                text = text.replace(old, new)
            elif new == "" and text.count(old) == 0:
                pass
            elif text.count(new) == 1:
                pass
            else:
                raise RuntimeError(f"{unit_id}:{line_no} expected old or new text for {old!r}")
        lines[line_no - 1] = text
        changed_lines.add(line_no)
    bundle["masked_text"] = "".join(lines)
    bundle["rewrite_intent"] = combine_intents(unit_id, sorted(changed_lines))
    bundle["keep_reasons"] = KEEP_REASONS.get(unit_id, {})
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    touched: set[str] = set()
    for unit_id, edits in SET_LINES.items():
        edit_bundle(unit_id, set_lines=edits)
        touched.add(unit_id)
    for unit_id, replacements in REPLACE_OPS.items():
        edit_bundle(unit_id, replacements=replacements)
        touched.add(unit_id)
    for unit_id, (reason, (start, end)) in NO_CHANGE.items():
        path = REWRITES / f"{unit_id}.json"
        bundle = json.loads(path.read_text(encoding="utf-8"))
        bundle["reason"] = reason
        bundle["evidence_spans"] = [evidence_span(unit_id, start, end)]
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        touched.add(unit_id)
    expected = {path.stem for path in REWRITES.glob("U-*.json")}
    if touched != expected:
        raise RuntimeError(f"coverage mismatch missing={sorted(expected-touched)} extra={sorted(touched-expected)}")
    print(json.dumps({"status": "AUTHORED_V2", "bundles": len(touched)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
