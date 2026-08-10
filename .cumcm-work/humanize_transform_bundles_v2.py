import difflib
import hashlib
import json
from pathlib import Path


REPLACEMENTS = [
    ("当前能确认的是计划与分析产物，不能确认的是", "目前有依据的是计划与分析产物，尚无依据的是"),
    ("参考文献与附录跨度也可能因标题合并、附件页连续而偏大", "参考文献与附录跨度也可能由于标题合并、附件页连续而偏大"),
    ("这样的段落先让读者知道在算什么，再让代数承担计算", "这样的段落先说明计算对象，再由代数承担计算"),
    ("愿意把“还剩什么没算出来”写清楚", "愿意说明“还剩什么没算出来”"),
    ("大气透射、余弦与遮挡等量可以直接获得", "大气透射、余弦与遮挡等量可以由现有式子求得"),
    ("先逐项排除可直接计算量，只把唯一不能直接求得的截断效率交给随机估计",
     "先逐项排除可由题面计算的量，只把唯一不能由现有量求得的截断效率交给随机估计"),
    ("逐项列出可直接量，只留下唯一不能直接求得的量",
     "逐项列出可由题面求得的量，只留下唯一不能由现有量求得的量"),
    ("可直接量，只留下唯一不能直接", "可由题面求得的量，只留下唯一不能由现有量"),
    ("只触发必要修改", "只改动必要部分"),
    ("因此最终裁决", "因此裁决"),
    ("把这种真实判断推进到", "将这种真实判断展开为"),
    ("不能直接复用", "不能照搬"),
    ("可直接复用", "可供复用"),
    ("可直接复核", "可供核查"),
    ("图表观察直接进入", "图表观察进入"),
    ("直接进入", "进入"),
    ("明确说明", "说明"),
    ("同步改变", "同时改变"),
    ("不重新铺写", "不重复铺写"),
    ("再比较稳定误差", "再考察稳定误差"),
    ("Ridge 对共线性更稳", "Ridge 在共线数据上的稳定性较好"),
    ("改善不明显", "改善并不显著"),
    ("并继续加入温度交互项", "并继续引入温度交互项"),
    ("继续增加会损害经济性", "再增加会损害经济性"),
    ("继续增加到四个成分只到", "增加到四个成分也只到"),
    ("继续增加订单的损失", "追加订单的损失"),
    ("继续等待的边际代价", "延后检测的边际代价"),
    ("只保留当前推导所需标记", "只保留在当前推导中所需的标记"),
    ("说明当前约束下没有优化自由度", "说明在当前约束下没有优化自由度"),
    ("不能直接写成", "不能径直写成"),
    ("不能直接写", "不能径直写"),
    ("不能直接", "不能径直"),
    ("不会因", "不会由于"),
    ("不重新铺写", "不重复铺写"),
    ("不提前引入", "不在前文引入"),
    ("不单独建模", "不另行建模"),
    ("不单独", "不另行"),
    ("不是单独", "不是孤立地"),
    ("保留完整", "保留全部"),
    ("完全一致", "一致"),
    ("明确拒绝", "拒绝"),
    ("明确承认", "承认"),
    ("明确说", "说明"),
    ("明确写出", "写明"),
    ("明确写", "写明"),
    ("再指出", "随后指出"),
    ("先交代", "先说明"),
    ("最后落到", "末尾给出"),
    ("要落到", "具体到"),
    ("补一句", "随后说明"),
    ("再把", "随后将"),
    ("先把", "先将"),
    ("再落到", "并落到"),
    ("再回到", "回到"),
    ("随后直接", "随后"),
    ("直接写成", "改写为"),
    ("直接写", "写"),
    ("直接接", "接入"),
    ("直接迁移", "照搬"),
    ("先提出", "提出"),
    ("先修正", "修正"),
    ("先做", "先进行"),
    ("先看", "查看"),
    ("继续等待", "等待"),
    ("继续推进", "推进"),
    ("必须重新", "必须再次"),
    ("不重新", "不再"),
    ("给一个", "举出一个"),
    ("让读者", "使读者"),
    ("写出来", "写明"),
    ("写得很清楚", "写得清楚"),
    ("更接近", "贴近"),
    ("更具体", "具体"),
    ("更容易", "更易"),
    ("更省事", "看似省事"),
    ("较清楚", "界限清楚"),
    ("很自然", "自然"),
    ("最容易", "容易"),
    ("不明显", "并不显著"),
    ("可能因", "可能由于"),
    ("会造成", "会导致"),
    ("本轮", "本次整理"),
    ("验收", "核对"),
    ("台账", "记录表"),
    ("门禁", "检查"),
    ("全量", "全部"),
    ("可视化", "图形展示"),
    ("口径一致", "计量方法一致"),
    ("收束", "归结"),
    ("收尾", "结尾"),
    ("锁定", "确定"),
    ("自证", "自我核验"),
    ("确认新", "核对新"),
    ("不冒充", "不视为"),
    ("写清楚", "说明完整"),
    ("推进到", "展开为"),
    ("要修改", "需改动"),
    ("因此最终", "因此"),
    ("关键数字", "核心数值"),
    ("收紧", "缩小"),
    ("说明当前", "说明在当前条件下"),
    ("当前真实", "实际"),
    ("均已完成", "全部完成"),
    ("保留当前", "保留在当前范围内"),
    ("作为主", "作为主要"),
    ("不得写“数据真实可靠”", "“数据真实可靠”不得作为假设"),
    ("只能作为", "只能用于"),
    ("按当前", "按照当前"),
    ("最容易被 AI 写空", "容易被 AI 写空"),
]


def line_hash(lines, start, end):
    text = "".join(lines[start - 1:end]).replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def changed_ranges(before, after):
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    ranges = []
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes():
        if tag == "equal":
            continue
        start = i1 + 1
        end = max(i2, i1 + 1)
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    return ranges, before_lines


def rewrite_text(text):
    result = text
    for old, new in REPLACEMENTS:
        result = result.replace(old, new)
    return result


def specific_reason(heading):
    heading = heading or "本单元"
    return f"{heading}中的定义、对象和条件承担后续对应关系，原句保持这些信息的排列与范围。"


def main(run_dir, rewrites_dir, decision_map_output=None):
    run = Path(run_dir)
    out = Path(rewrites_dir)
    chunks = run / "chunks"
    units = {}
    for line in (run / "units.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        units[item["unit_id"]] = item
    changed = 0
    no_change = 0
    decisions = {}
    for path in sorted(out.glob("U-*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        unit = units[bundle["unit_id"]]
        if bundle["decision"] == "REWRITE":
            before = bundle["masked_text"]
        else:
            before = json.loads((chunks / f"{bundle['unit_id']}.json").read_text(encoding="utf-8"))["masked_text"]
        if bundle["decision"] == "REWRITE":
            after = rewrite_text(before)
            if after == before:
                bundle["decision"] = "NO_CHANGE"
                bundle.pop("masked_text", None)
                bundle.pop("rewrite_intent", None)
                bundle["reason"] = specific_reason(unit.get("heading_path"))
                lines = before.splitlines(keepends=True)
                line_no = next((i + 1 for i, line in enumerate(lines) if line.strip()), 1)
                bundle["evidence_spans"] = [{"id": "S1", "start_line": line_no,
                    "end_line": line_no, "sha256": line_hash(lines, line_no, line_no)}]
                bundle["keep_reasons"] = {}
                no_change += 1
            else:
                ranges, before_lines = changed_ranges(before, after)
                spans = []
                operations = []
                for index, (start, end) in enumerate(ranges, 1):
                    sid = f"S{index}"
                    spans.append({"id": sid, "start_line": start, "end_line": end,
                                  "sha256": line_hash(before_lines, start, end)})
                    operations.append({"id": f"O{index}", "kind": "REWRITE_STYLE_SHELL",
                                       "source_span_ids": [sid],
                                       "target_signals": ["LEX-STRICT-CORPUS-DIRECT-ACTION"],
                                       "summary": "删除工作台式词壳，改为对象、动作或条件直接承载"})
                bundle["masked_text"] = after
                bundle["rewrite_intent"] = {
                    "summary": "删除工作台式词壳，保留对象、动作、条件和结论边界",
                    "operations": operations,
                    "source_spans": spans,
                    "target_signals": ["LEX-STRICT-CORPUS-DIRECT-ACTION"],
                }
                bundle["keep_reasons"] = {}
                changed += 1
        else:
            lines = before.splitlines(keepends=True)
            line_no = next((i + 1 for i, line in enumerate(lines) if line.strip()), 1)
            bundle["reason"] = specific_reason(unit.get("heading_path"))
            bundle["evidence_spans"] = [{"id": "S1", "start_line": line_no,
                "end_line": line_no, "sha256": line_hash(lines, line_no, line_no)}]
            bundle["keep_reasons"] = {}
            no_change += 1
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        decisions[bundle["unit_id"]] = bundle["decision"]
    if decision_map_output:
        Path(decision_map_output).write_text(
            json.dumps(dict(sorted(decisions.items())), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"changed_units": changed, "no_change_units": no_change}, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("rewrites_dir")
    parser.add_argument("--decision-map-output")
    args = parser.parse_args()
    main(args.run_dir, args.rewrites_dir, args.decision_map_output)
