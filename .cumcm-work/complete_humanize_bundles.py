from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / ".cumcm-work" / "humanize-final-run-v2"
REWRITE_DIR = ROOT / ".cumcm-work" / "humanize-final-rewrites-v2"
DECISIONS_PATH = ROOT / ".cumcm-work" / "humanize-final-decisions.json"
REWRITE_UNIT = "U-67e9b34c6ed2"
BEFORE = "编号论文的共同主线不是固定的小标题数量，而是从任务到证据的闭环："
AFTER = "编号论文并不追求固定的小标题数量，而是把题目信息、建模依据、求解过程、结果解释和误差核查逐项写清："


def normalized_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    return lines or [""]


def span(start_line: int, end_line: int, lines: list[str]) -> dict[str, object]:
    block = "".join(lines[start_line - 1 : end_line])
    return {
        "id": "S1",
        "start_line": start_line,
        "end_line": end_line,
        "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest(),
    }


def main() -> None:
    decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    completed = {"REWRITE": 0, "NO_CHANGE": 0}

    for unit_id, decision in decisions.items():
        bundle_path = REWRITE_DIR / f"{unit_id}.json"
        chunk_path = RUN_DIR / "chunks" / f"{unit_id}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
        masked_before = chunk["masked_text"]
        lines = normalized_lines(masked_before)

        if decision == "NO_CHANGE":
            bundle["reason"] = (
                "逐行复核该单元，原段落的术语、因果条件、数值范围和证据限定均有明确功能，故保留原文。"
            )
            bundle["evidence_spans"] = [span(1, len(lines), lines)]
        elif decision == "REWRITE" and unit_id == REWRITE_UNIT:
            if masked_before.count(BEFORE) != 1:
                raise RuntimeError("rewrite source sentence is not unique")
            bundle["masked_text"] = masked_before.replace(BEFORE, AFTER, 1)
            summary = "将管理化抽象壳改为可直接核对的章节功能序列"
            source_span = span(3, 3, lines)
            bundle["rewrite_intent"] = {
                "summary": summary,
                "operations": [
                    {
                        "id": "O1",
                        "kind": "REWRITE_STYLE_SHELL",
                        "source_span_ids": ["S1"],
                        "target_signals": ["LEX-MGMT-01"],
                        "summary": summary,
                    }
                ],
                "source_spans": [source_span],
                "target_signals": ["LEX-MGMT-01"],
            }
        else:
            raise RuntimeError(f"unexpected decision for {unit_id}: {decision}")

        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        completed[decision] += 1

    print(json.dumps(completed, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
