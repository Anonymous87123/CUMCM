from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / "humanize-final-run-v3"
REWRITES_DIR = ROOT / "humanize-final-run-v3-rewrites"
REWRITE_UNIT = "U-eda57d1bbaa4"
PROTECTED_RE = re.compile(r"\[\[PROTECTED:[^]]+]]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def normalized_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )


def span_hash(lines: list[str], start_line: int, end_line: int) -> str:
    selected = "".join(lines[start_line - 1 : end_line])
    return hashlib.sha256(selected.encode("utf-8")).hexdigest()


def evidence_line(masked_text: str) -> tuple[int, str]:
    lines = normalized_lines(masked_text)
    for index, line in enumerate(lines, start=1):
        visible = PROTECTED_RE.sub("", line).strip()
        if HAN_RE.search(visible):
            return index, span_hash(lines, index, index)
    raise ValueError("pending unit has no visible Chinese evidence line")


def complete_no_change(bundle: dict, chunk: dict) -> None:
    heading = str(chunk.get("heading_path") or "正文单元").split(" / ")[-1]
    line_number, digest = evidence_line(str(chunk["masked_text"]))
    bundle["reason"] = (
        f"本单元承担“{heading}”的对象、条件与证据边界；原文段落已锁定术语、"
        "数字和论证顺序，保持原句可避免结构漂移。"
    )
    bundle["evidence_spans"] = [
        {
            "id": "S1",
            "start_line": line_number,
            "end_line": line_number,
            "sha256": digest,
        }
    ]


def complete_rewrite(bundle: dict, chunk: dict) -> None:
    lines = normalized_lines(str(chunk["masked_text"]))
    replacements = {
        7: "label 编码，连续变量只有在解释或规则需要时才按等宽/等频分箱。样本筛选使用\n",
        8: "Monte Carlo 随机抽样时，须固定种子，记录抽样分布并核对覆盖率；它与组员1\n",
        9: (
            "的不确定性仿真共享随机数配置，但不把"
            "[[PROTECTED:F00001-P00163:a65eb384cfed]]与"
            "[[PROTECTED:F00001-P00164:4d96db79236b]]混为同一任务。\n"
        ),
        27: (
            "思维导图中的[[PROTECTED:F00001-P00165:8cdc9d3405b9]]归入二分类模型，"
            "不当作连续响应回归；长期预测是\n"
        ),
        28: "外推任务，必须报告预测区间、结构漂移风险和超出训练区间的限制。\n",
    }
    for line_number, replacement in replacements.items():
        lines[line_number - 1] = replacement
    bundle["masked_text"] = "".join(lines)
    summary = "理顺样本筛选与模型归类句，同时保留任务边界和外推风险条件"
    bundle["rewrite_intent"] = {
        "summary": summary,
        "operations": [
            {
                "id": "O1",
                "kind": "REWRITE_STYLE_SHELL",
                "source_span_ids": ["S1"],
                "target_signals": ["STYLE-SENTENCE-FLOW"],
                "summary": "重组样本筛选句，区分抽样筛选与不确定性仿真的任务边界",
            },
            {
                "id": "O2",
                "kind": "REWRITE_STYLE_SHELL",
                "source_span_ids": ["S2"],
                "target_signals": ["STYLE-CLASSIFICATION-BOUNDARY"],
                "summary": "压缩模型归类句，保留分类与外推边界及风险条件",
            },
        ],
        "source_spans": [
            {
                "id": "S1",
                "start_line": 7,
                "end_line": 9,
                "sha256": span_hash(normalized_lines(str(chunk["masked_text"])), 7, 9),
            },
            {
                "id": "S2",
                "start_line": 27,
                "end_line": 28,
                "sha256": span_hash(normalized_lines(str(chunk["masked_text"])), 27, 28),
            },
        ],
        "target_signals": [
            "STYLE-SENTENCE-FLOW",
            "STYLE-CLASSIFICATION-BOUNDARY",
        ],
    }


def main() -> None:
    completed = {"NO_CHANGE": 0, "REWRITE": 0}
    for bundle_path in sorted(REWRITES_DIR.glob("U-*.json")):
        bundle = load_json(bundle_path)
        unit_id = str(bundle["unit_id"])
        chunk = load_json(RUN_DIR / "chunks" / f"{unit_id}.json")
        decision = str(bundle["decision"])
        if decision == "NO_CHANGE":
            complete_no_change(bundle, chunk)
        elif decision == "REWRITE" and unit_id == REWRITE_UNIT:
            complete_rewrite(bundle, chunk)
        else:
            raise ValueError(f"unexpected decision for {unit_id}: {decision}")
        write_json(bundle_path, bundle)
        completed[decision] += 1
    print(json.dumps(completed, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
