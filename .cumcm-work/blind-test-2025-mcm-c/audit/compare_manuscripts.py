#!/usr/bin/env python3
"""Reproducible structural comparison for the Skill draft and prompt baseline."""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path


SIGNALS = {
    "actual_attachment_boundary": r"(?:实际只|本地附件|不补造|沿用 2024)",
    "simple_baseline_retained": r"上一届(?:成绩|基线)",
    "failed_complex_model_reported": r"随机森林.{0,80}(?:MAE|误差)|(?:MAE|误差).{0,80}随机森林",
    "probability_calibration": r"(?:实际首牌率|实际发生率).{0,100}校准|校准.{0,100}(?:首牌率|发生率)",
    "causal_boundary": r"(?:不能|不等同于|不得).{0,40}因果|因果.{0,40}(?:不能|不等同于|不得)",
    "result_mechanism": r"(?:来自|状态切换|区间重叠|原因|意味着)",
    "reproduction_interface": r"(?:入口脚本|目录结构|结果文件|复算接口)",
}


def strip_tex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\(?:begin|end)\s*\{[^}]+\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
    return re.sub(r"[{}$&_^~\\]", " ", text)


def metrics(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    prose = strip_tex(raw)
    paragraphs = [
        "".join(re.findall(r"[\u4e00-\u9fff]", item))
        for item in re.split(r"\n\s*\n", prose)
    ]
    lengths = [len(item) for item in paragraphs if len(item) >= 20]
    return {
        "file": str(path.resolve()),
        "han_chars": len(re.findall(r"[\u4e00-\u9fff]", prose)),
        "prose_paragraphs": len(lengths),
        "paragraph_median_han": statistics.median(lengths) if lengths else 0,
        "paragraph_length_stdev": round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0,
        "sections": len(re.findall(r"\\section\*?\s*\{", raw)),
        "subsections": len(re.findall(r"\\subsection\*?\s*\{", raw)),
        "subsubsections": len(re.findall(r"\\subsubsection\*?\s*\{", raw)),
        "equation_blocks": len(re.findall(r"\\begin\s*\{(?:equation|align|gather|multline)\*?\}", raw)),
        "figures": len(re.findall(r"\\begin\s*\{figure\*?\}", raw)),
        "tables": len(re.findall(r"\\begin\s*\{(?:table\*?|longtable)\}", raw)),
        "signals": {name: bool(re.search(pattern, prose, re.S)) for name, pattern in SIGNALS.items()},
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: compare_manuscripts.py <skill.tex> <baseline.tex>", file=sys.stderr)
        return 2
    report = {
        "scope": "same-model prompt ablation; not model-isolated and not an AI detector",
        "skill": metrics(Path(sys.argv[1])),
        "baseline": metrics(Path(sys.argv[2])),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
