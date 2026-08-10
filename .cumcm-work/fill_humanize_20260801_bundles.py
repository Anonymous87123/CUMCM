from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(r"F:\CUMCM")
RUN_DIR = ROOT / ".cumcm-work" / "humanize-20260801-final-run-v2"
REWRITES_DIR = ROOT / ".cumcm-work" / "humanize-20260801-final-rewrites-v2"


REWRITES = {
    "U-dc1d4fead1f5": {
        "start": 4,
        "end": 6,
        "lines": [
            "证据流水线。[[PROTECTED:F00001-P00200:490892b3d680]]不在本轮评价范围内；可取之处仍是每条主责线都要求基线、约束、",
            "独立检验和下游接口。复杂模型必须与简单模型公平比较，模型、代码和论文中的",
            "变量名可以追到相应结果文件。",
        ],
        "signal": "STYLE-EMPTY-CONTRAST",
        "summary": "去掉阶段总结中的对举壳，保留责任线、比较口径和追溯关系",
    },
    "U-1f6c0b78c643": {
        "start": 3,
        "end": 5,
        "lines": [
            "59 篇论文的自动页级候选给出篇幅与标题统计；59 张人工证据卡确认逐篇模型链、",
            "章节写法、结果解释、检验和创新结论。自动候选只标出页级位置，人工卡用于判断",
            "段落功能和真实行文动作，两类证据不互相替代。",
        ],
        "signal": "STYLE-SECTION-ROUTE-NARRATION",
        "summary": "让证据对象直接起句，并保留自动定位与人工判断的职责边界",
    },
    "U-6dc12cef7031": {
        "start": 4,
        "end": 6,
        "lines": [
            "[[PROTECTED:F00001-P00386:964ad09b50fb]]。推导篇幅不必刻意拉长，",
            "假设、方程、初边值和数值格式仍要彼此闭合。结果解释需回到物理量、数量级和机制；",
            "一条平滑曲线本身不足以说明模型正确。",
        ],
        "signal": "STYLE-META-EMPHASIS",
        "summary": "把模板化的关键强调改成对推导篇幅和闭合关系的直接判断",
    },
    "U-cbabc9654d82": {
        "start": 158,
        "end": 158,
        "lines": [
            "周末采购和上下班节奏；图形不作孤立展示，随后用于确定预测窗口，并解释相应的经营现象。",
        ],
        "signal": "STYLE-FIGURE-DISCLAIMER",
        "summary": "删除图形不是装饰的防御壳，直接写图形承担的预测和解释作用",
    },
    "U-50a463208c00": {
        "start": 3,
        "end": 9,
        "lines": [
            "以[[PROTECTED:F00001-P01009:2664540b80f4]]为起点，模型、代码和写作链才是本轮可验收的产物。三名成员分别",
            "承担机理连续模型、综合优化和数据决策的首责，编程、误差分析和选题判断则共同承担；",
            "18 道真题分别提供练习入口。论文研究以 59 篇编号语料为限，59 张可追溯的正式证据卡覆盖",
            "2892 页；赛题和专家评述不混入文风样本，A/B/C 三类分别完成 20/19/20 篇人工门禁。",
            "模板与 Skill 可随本轮 59 篇证据增量修改；四周计划把尚无实证的能力落实为代码、图表、",
            "论文和复现产物，并逐项验收。后续限时演练不增加算法名称，重点检验基线建立、约束书写、",
            "关键结果复算和文字说明能否在时限内完成。",
        ],
        "signal": "STYLE-CHECKLIST-CONCLUSION",
        "summary": "按证据、分工和下一次演练重写结论，删去算法清单式对举和空泛闭环收尾",
    },
}


def normalized_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)


def line_hash(lines: list[str], start: int, end: int) -> str:
    payload = "".join(lines[start - 1 : end]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


with (RUN_DIR / "coverage_ledger.csv").open("r", encoding="utf-8-sig", newline="") as handle:
    ledger = {row["unit_id"]: row for row in csv.DictReader(handle)}

completed_no_change = 0
completed_rewrite = 0

for bundle_path in sorted(REWRITES_DIR.glob("U-*.json")):
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    unit_id = bundle["unit_id"]
    chunk = json.loads((RUN_DIR / "chunks" / f"{unit_id}.json").read_text(encoding="utf-8"))
    source_lines = normalized_lines(chunk["masked_text"])

    if bundle["decision"] == "NO_CHANGE":
        evidence_line = next(
            index
            for index, line in enumerate(source_lines, start=1)
            if re.search(r"[\u3400-\u9fff]", re.sub(r"\[\[PROTECTED:[^]]+\]\]", "", line))
        )
        heading = ledger[unit_id]["heading_path"].split(" / ")[-1]
        bundle["reason"] = (
            f"该段落承担“{heading}”中的对象、条件与证据次序，现有结构已区分定义、判断和结果范围，"
            "继续改写会削弱这些功能关系。"
        )
        bundle["evidence_spans"] = [
            {
                "id": "S1",
                "start_line": evidence_line,
                "end_line": evidence_line,
                "sha256": line_hash(source_lines, evidence_line, evidence_line),
            }
        ]
        completed_no_change += 1
    else:
        spec = REWRITES[unit_id]
        if spec["end"] - spec["start"] + 1 != len(spec["lines"]):
            raise ValueError(f"replacement line count mismatch for {unit_id}")
        output_lines = list(source_lines)
        for offset, replacement in enumerate(spec["lines"]):
            source_index = spec["start"] - 1 + offset
            ending = "\n" if output_lines[source_index].endswith("\n") else ""
            output_lines[source_index] = replacement + ending
        bundle["masked_text"] = "".join(output_lines)
        span = {
            "id": "S1",
            "start_line": spec["start"],
            "end_line": spec["end"],
            "sha256": line_hash(source_lines, spec["start"], spec["end"]),
        }
        bundle["rewrite_intent"] = {
            "summary": spec["summary"],
            "operations": [
                {
                    "id": "O1",
                    "kind": "REWRITE_STYLE_SHELL",
                    "source_span_ids": ["S1"],
                    "target_signals": [spec["signal"]],
                    "summary": spec["summary"],
                }
            ],
            "source_spans": [span],
            "target_signals": [spec["signal"]],
        }
        completed_rewrite += 1

    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

if completed_rewrite != len(REWRITES):
    raise RuntimeError(f"expected {len(REWRITES)} rewrites, completed {completed_rewrite}")

print(
    json.dumps(
        {
            "rewrites": completed_rewrite,
            "no_change": completed_no_change,
            "total": completed_rewrite + completed_no_change,
        },
        ensure_ascii=False,
    )
)
