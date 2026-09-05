#!/usr/bin/env python3
"""Regression checks for deterministic real-draft improvement suite sampling."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from prepare_draft_improvement_suite import build


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="draft-improvement-suite-") as temp:
        root = Path(temp)
        source = root / "main.tex"
        sections = []
        for index in range(1, 9):
            body = (
                f"第{index}部分记录了本问的数据现象、变量关系和模型选择依据。"
                "原始记录先给出对象之间的差异，再说明该差异怎样进入约束或目标函数。"
                "求解结果返回以后，正文继续解释数值变化对应的实际事件，并保留适用范围。"
                "这一段来自真实工作稿的连续论述，用于检查候选能否改善句群而不改变事实。"
            )
            sections.append(f"\\section{{测试章节{index}}}\n\n{body}\n")
        sections.append(
            "\\section{公式区}\n\n\\begin{align}\n"
            "x&=1\\\\\ny&=2\n\\end{align}\n"
        )
        source.write_text("\n".join(sections), encoding="utf-8")
        first = build(
            source, root / "run-a", "real-draft", "v1", 20260823,
            3, 3, "测试保管人", "release-1", minimum_han=80,
            document_type="course-notes",
        )
        second = build(
            source, root / "run-b", "real-draft", "v1", 20260823,
            3, 3, "测试保管人", "release-1", minimum_han=80,
            document_type="course-notes",
        )
        if first["eligible_paragraphs"] != 8 or second["eligible_paragraphs"] != 8:
            print("FAIL: TeX paragraph eligibility included formulas or lost prose", first, second)
            return 1

        def hashes(run: Path, split: str) -> list[str]:
            suite = json.loads((run / split / "suite.json").read_text(encoding="utf-8"))
            if suite.get("benchmark_goal") != "improvement":
                raise AssertionError("draft suite did not declare improvement")
            if suite.get("required_generation_evidence") != ["stack_evaluation"]:
                raise AssertionError("draft suite did not require integrated stack evidence")
            if any(
                case.get("scene", {}).get("document_type") != "course-notes"
                for case in suite["cases"]
            ):
                raise AssertionError("draft suite lost its requested document type")
            headings = [case["provenance"]["heading"] for case in suite["cases"]]
            if len(set(headings)) != len(headings) or any(
                not heading.startswith("测试章节") for heading in headings
            ):
                raise AssertionError(f"TeX headings were not tracked correctly: {headings}")
            return [case["provenance"]["paragraph_sha256"] for case in suite["cases"]]

        dev_a = hashes(root / "run-a", "dev")
        holdout_a = hashes(root / "run-a", "holdout")
        dev_b = hashes(root / "run-b", "dev")
        holdout_b = hashes(root / "run-b", "holdout")
        if dev_a != dev_b or holdout_a != holdout_b:
            print("FAIL: fixed-seed sampling was not deterministic")
            return 1
        if set(dev_a) & set(holdout_a):
            print("FAIL: dev and holdout reused a source paragraph")
            return 1
        report = json.loads((root / "run-a" / "build-report.json").read_text(encoding="utf-8"))
        if report.get("selection_uses_quality_labels") is not False:
            print("FAIL: suite builder claimed quality-label selection")
            return 1
        excluded = build(
            source, root / "run-excluded", "real-draft-next", "v2", 20260824,
            1, 1, "测试保管人", "release-2", minimum_han=80,
            exclude_suites=[
                root / "run-a" / "dev" / "suite.json",
                root / "run-a" / "holdout" / "suite.json",
            ],
            document_type="course-notes",
        )
        excluded_hashes = set(hashes(root / "run-excluded", "dev")) | set(
            hashes(root / "run-excluded", "holdout")
        )
        if excluded_hashes & (set(dev_a) | set(holdout_a)):
            print("FAIL: excluded historical paragraphs were sampled again")
            return 1
        if excluded.get("excluded_paragraphs") != 6 or len(excluded.get("exclusion_suites", [])) != 2:
            print("FAIL: exclusion provenance was not locked", excluded)
            return 1
    print("PASS: real-draft suites are deterministic, disjoint, and sampled without quality labels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
