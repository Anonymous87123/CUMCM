#!/usr/bin/env python3
"""Build the auditable 59-paper manual deep-review progress index."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
SKILL = Path.home() / ".codex" / "skills" / "mcm-cup-standard-write"
CARDS = SKILL / "references" / "paper-cards"
RASTER = WORK / "deep-evidence" / "raster-review"
OUTPUT = WORK / "deep-evidence" / "manual-review-progress.csv"
SKILL_INDEX = SKILL / "references" / "corpus-index.md"

SECTION_NAMES = [
    "摘要", "问题重述", "模型假设", "符号说明", "建模思路", "模型构建", "求解过程",
    "结果分析", "模型检验", "灵敏度分析", "模型评价", "改进方案", "参考文献", "附录",
]
REQUIRED_HEADINGS = [
    "## 审读状态", "## 十四类章节证据", "## 模型链及各环节作用", "## 已核结果",
    "## 创新与可迁移写法", "## 缺陷、风险与失分点", "## 原始栅格核验记录",
    "## 对报告、模板与审计规则的增量",
]


def inventory() -> list[dict]:
    path = WORK / "paper_feature_matrix.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    rows.sort(key=lambda row: (int(row["year"]), row["problem"], row["paper"]))
    if len(rows) != 59 or sum(int(row["pages"]) for row in rows) != 2892:
        raise RuntimeError("inventory must remain 59 papers / 2892 pages")
    return rows


def raster_status(paper_id: str) -> tuple[int, int]:
    metadata = sorted((RASTER / paper_id).glob("*.json")) if (RASTER / paper_id).is_dir() else []
    verified = 0
    for path in metadata:
        item = json.loads(path.read_text(encoding="utf-8"))
        proxy = ROOT / item["review_proxy"]
        if item.get("review_status") == "verified" and proxy.is_file() and proxy.stat().st_size <= 450_000:
            verified += 1
    return len(metadata), verified


def assess(row: dict) -> dict:
    paper_id = f"{row['year']}_{row['paper']}"
    card = CARDS / f"{paper_id}.md"
    text = card.read_text(encoding="utf-8") if card.is_file() else ""
    section_count = sum(f"| {name} |" in text for name in SECTION_NAMES)
    heading_count = sum(heading in text for heading in REQUIRED_HEADINGS)
    full_text = f"已按页通读 1--{row['pages']} 页" in text
    raster_total, raster_verified = raster_status(paper_id)
    complete = (
        full_text and section_count == 14 and heading_count == len(REQUIRED_HEADINGS)
        and raster_verified >= 3
    )
    return {
        "year": row["year"],
        "problem": row["problem"],
        "paper": row["paper"],
        "pages": row["pages"],
        "full_text_review": "verified" if full_text else "pending",
        "section_categories_verified": section_count,
        "required_blocks_verified": heading_count,
        "raster_items_total": raster_total,
        "raster_items_verified": raster_verified,
        "deep_review_status": "verified" if complete else "pending",
        "skill_card": card.relative_to(SKILL).as_posix() if card.is_file() else "",
    }


def write_csv(rows: list[dict]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_skill_index(rows: list[dict]) -> None:
    verified = sum(row["deep_review_status"] == "verified" for row in rows)
    lines = [
        "# 2020--2025 A/B/C 编号论文精读索引",
        "",
        f"当前人工精读门禁通过：{verified}/59。总页数固定为 2892。`pending` 不得用于统计结论。",
        "",
        "通过条件：逐页文本通读、十四类章节齐全、八个必需分析块齐全，并至少完成三项关键原始栅格核验。自动 OCR 定位不等于通过。",
        "",
        "| 年份 | 题型 | 编号 | 页数 | 全文 | 十四类 | 栅格已核 | 状态 | 论文卡 |",
        "|---:|:---:|:---:|---:|:---:|---:|---:|:---:|---|",
    ]
    for row in rows:
        card = f"[查看](paper-cards/{row['year']}_{row['paper']}.md)" if row["skill_card"] else "待建"
        lines.append(
            f"| {row['year']} | {row['problem']} | {row['paper']} | {row['pages']} | "
            f"{row['full_text_review']} | {row['section_categories_verified']}/14 | "
            f"{row['raster_items_verified']} | {row['deep_review_status']} | {card} |"
        )
    SKILL_INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    rows = [assess(row) for row in inventory()]
    write_csv(rows)
    write_skill_index(rows)
    verified = [f"{row['year']}_{row['paper']}" for row in rows if row["deep_review_status"] == "verified"]
    print(json.dumps({"papers": len(rows), "pages": sum(int(row["pages"]) for row in rows),
                      "verified": len(verified), "verified_ids": verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
