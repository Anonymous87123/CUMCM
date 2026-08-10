#!/usr/bin/env python3
"""Build auditable corpus statistics after all 59 paper JSONL files exist."""

from __future__ import annotations

import csv
import json
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
PAGES = WORK / "pages"
PAPER_RE = re.compile(r"^[ABC]\d+$")
HAN = re.compile(r"[\u4e00-\u9fff]")

SECTIONS = [
    ("摘要", re.compile(r"^\s*摘\s*要\s*$|摘\s*要\s*[:：]")),
    ("问题重述", re.compile(r"问题(?:的)?重述|问题背景")),
    ("问题分析", re.compile(r"问题分析|建模思路|问题的分析")),
    ("模型假设", re.compile(r"模型假设|基本假设|假设条件")),
    ("符号说明", re.compile(r"符号说明|符号定义|符号与说明")),
    ("模型建立", re.compile(r"模型(?:的)?建立|模型构建|建立模型")),
    ("模型求解", re.compile(r"模型(?:的)?求解|求解过程|算法求解")),
    ("结果分析", re.compile(r"结果分析|结果与分析|求解结果|结果讨论")),
    ("模型检验", re.compile(r"模型检验|模型验证|误差分析|有效性检验")),
    ("灵敏度分析", re.compile(r"灵敏度|敏感性|参数扰动|稳健性")),
    ("模型评价", re.compile(r"模型评价|模型优缺点|优点与不足|模型的评价")),
    ("改进方案", re.compile(r"模型改进|改进方向|进一步改进|改进方案|模型推广")),
    ("参考文献", re.compile(r"参考文献")),
    ("附录", re.compile(r"^\s*附\s*录|附录\s*[:：A-Z一二三四五六七八九十]")),
]

MODEL_GROUPS = {
    "机理与数值": ["微分方程", "偏微分方程", "ODE", "PDE", "RK4", "龙格库塔", "有限差分", "有限元", "守恒", "蒙特卡洛"],
    "规划与智能优化": ["线性规划", "非线性规划", "整数规划", "0-1", "多目标", "遗传算法", "粒子群", "模拟退火", "蚁群", "NSGA", "MOPSO"],
    "图与网络": ["Dijkstra", "Floyd", "最短路", "最小生成树", "最大流", "最小费用流", "二分图", "网络流"],
    "评价决策": ["层次分析", "AHP", "熵权", "CRITIC", "TOPSIS", "VIKOR", "灰色关联", "模糊综合", "物元可拓", "主成分", "因子分析"],
    "统计学习": ["回归", "Logistic", "随机森林", "支持向量", "XGBoost", "LightGBM", "CatBoost", "聚类", "K-Means", "DBSCAN", "PCA", "交叉验证"],
    "时序预测": ["ARIMA", "SARIMA", "指数平滑", "VAR", "灰色预测", "Prophet", "LSTM", "GRU", "TCN", "RNN"],
}

STYLE_TERMS = ["首先", "其次", "进一步", "由此", "可知", "表明", "说明", "验证", "相比", "为了", "从而", "因此"]
CAPTION_RE = re.compile(r"^(?:图|表)\s*[A-Za-z一二三四五六七八九十\d]+(?:[-—.．]\d+)*")
EQUATION_RE = re.compile(r"(?:=|≤|≥|∑|∫|√|\^|_{|\bd[xyzst]/d[xyzst]\b)")
HEADING_RE = re.compile(r"^(?:第?[一二三四五六七八九十百]+[、.]|\d+(?:[.．]\d+){0,3}[、.．\s])")


def run(command: list[str]) -> str:
    proc = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return proc.stdout


def inventory() -> list[dict]:
    papers = []
    for year in range(2020, 2026):
        for path in sorted((ROOT / str(year)).glob("*.pdf")):
            if not PAPER_RE.fullmatch(path.stem):
                continue
            info = run(["pdfinfo", str(path)])
            match = re.search(r"^Pages:\s+(\d+)", info, re.M)
            if not match:
                raise RuntimeError(f"No page count: {path}")
            papers.append({"year": year, "type": path.stem[0], "paper": path.stem,
                           "pages": int(match.group(1)), "path": path})
    if len(papers) != 59 or sum(item["pages"] for item in papers) != 2892:
        raise RuntimeError(f"Inventory mismatch: papers={len(papers)} pages={sum(x['pages'] for x in papers)}")
    return papers


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty percentile")
    position = (len(ordered) - 1) * q
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def descriptive(values: list[float], digits: int = 2) -> dict:
    return {
        "n": len(values),
        "q1": round(percentile(values, 0.25), digits),
        "median": round(percentile(values, 0.5), digits),
        "q3": round(percentile(values, 0.75), digits),
        "min": round(min(values), digits),
        "max": round(max(values), digits),
    }


def load_pages(paper: dict) -> list[dict]:
    source = PAGES / f"{paper['year']}_{paper['paper']}.jsonl"
    if not source.is_file():
        raise RuntimeError(f"Missing OCR: {source.name}")
    with source.open(encoding="utf-8") as stream:
        pages = [json.loads(line) for line in stream if line.strip()]
    numbers = [page.get("page") for page in pages]
    if numbers != list(range(1, paper["pages"] + 1)):
        raise RuntimeError(f"Page continuity mismatch: {source.name}")
    if any(page.get("ocr_schema_version") != 2 for page in pages):
        raise RuntimeError(f"Schema mismatch: {source.name}")
    return pages


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).strip("·.。,:：;；-—_()（）[]【】")


def find_sections(pages: list[dict]) -> dict[str, dict]:
    hits = {}
    for page in pages:
        for line_number, item in enumerate(page["lines"], 1):
            text = normalized(item["text"])
            if not 1 < len(text) <= 45:
                continue
            for section, pattern in SECTIONS:
                if section not in hits and pattern.search(text):
                    hits[section] = {
                        "page": page["page"], "line": line_number, "source_text": item["text"],
                        "confidence": item.get("confidence", page.get("median_confidence", 0)),
                    }
    return hits


def first_term_pages(pages: list[dict]) -> list[dict]:
    seen, found = set(), []
    for page in pages:
        lowered = page["text"].lower()
        for group, terms in MODEL_GROUPS.items():
            for term in terms:
                key = term.lower()
                if key in lowered and (group, term) not in seen:
                    found.append({"group": group, "term": term, "page": page["page"]})
                    seen.add((group, term))
    return sorted(found, key=lambda item: (item["page"], item["group"], item["term"]))


def snippet(pages: list[dict], page_no: int, line_no: int) -> str:
    lines = pages[page_no - 1]["lines"]
    return " / ".join(item["text"] for item in lines[max(0, line_no - 3):min(len(lines), line_no + 2)])[:600]


def paragraph_candidates(page: dict) -> int:
    """Estimate body paragraph starts from OCR indentation and vertical gaps."""
    body = []
    for line in page["lines"]:
        text = re.sub(r"\s+", "", line["text"])
        box = line.get("box") or []
        if len(HAN.findall(text)) < 8 or len(box) < 4:
            continue
        left = min(float(point[0]) for point in box)
        top = min(float(point[1]) for point in box)
        bottom = max(float(point[1]) for point in box)
        if bottom <= top:
            continue
        body.append((top, left, bottom - top, text))
    if not body:
        text_lines = [
            re.sub(r"\s+", "", line["text"])
            for line in page["lines"]
            if len(HAN.findall(line["text"])) >= 8
        ]
        if not text_lines:
            return 0
        enumerated = sum(
            bool(re.match(r"^(?:第?[一二三四五六七八九十]+[、.]|\d+(?:[.．]\d+)*[、.．])", text))
            for text in text_lines
        )
        return max(1, enumerated)
    body.sort()
    left_base = percentile([item[1] for item in body], 0.25)
    median_height = max(1.0, percentile([item[2] for item in body], 0.5))
    candidates = 1
    previous_bottom = body[0][0] + body[0][2]
    for top, left, height, text in body[1:]:
        gap = top - previous_bottom
        indented = left >= left_base + max(12.0, median_height * 0.65)
        enumerated = bool(re.match(r"^(?:第?[一二三四五六七八九十]+[、.]|\d+(?:[.．]\d+)*[、.．])", text))
        if gap >= median_height * 0.65 or indented or enumerated:
            candidates += 1
        previous_bottom = max(previous_bottom, top + height)
    return candidates


def main() -> None:
    papers = inventory()
    summaries, ledger, chains = [], [], []
    section_start = defaultdict(list)
    section_spans = defaultdict(list)
    section_span_fractions = defaultdict(list)
    layout_positions = defaultdict(list)
    all_style = Counter()
    style_by_type = defaultdict(Counter)
    methods = Counter()
    model_term_papers = defaultdict(Counter)
    model_group_papers = defaultdict(Counter)
    section_sequences = defaultdict(Counter)

    for paper in papers:
        pages = load_pages(paper)
        hits = find_sections(pages)
        ordered_hits = sorted(hits.items(), key=lambda item: (item[1]["page"], item[1]["line"]))
        line_counts = [len(page["lines"]) for page in pages]
        han_counts = [page["chinese_chars"] for page in pages]
        paragraph_counts = [paragraph_candidates(page) for page in pages]
        caption_pages = [
            page["page"] for page in pages
            if any(CAPTION_RE.search(normalized(line["text"])) for line in page["lines"])
        ]
        equation_pages = [
            page["page"] for page in pages
            if any(EQUATION_RE.search(line["text"]) for line in page["lines"])
        ]
        captions = sum(bool(CAPTION_RE.search(normalized(line["text"]))) for page in pages for line in page["lines"])
        equation_lines = sum(bool(EQUATION_RE.search(line["text"])) for page in pages for line in page["lines"])
        headings = sum(bool(HEADING_RE.search(normalized(line["text"]))) for page in pages for line in page["lines"])
        full_text = "\n".join(page["text"] for page in pages)
        style_counts = {term: full_text.count(term) for term in STYLE_TERMS}
        all_style.update(style_counts)
        style_by_type[paper["type"]].update(style_counts)
        methods.update(page["method"] for page in pages)
        fallback_pages = sum(bool(page.get("fallback_audit", {}).get("triggered")) for page in pages)
        unconfirmed_pages = sum(bool(page.get("needs_tesseract")) for page in pages)
        model_chain = first_term_pages(pages)
        for item in model_chain:
            model_term_papers["ALL"][item["term"]] += 1
            model_term_papers[paper["type"]][item["term"]] += 1
        for group in {item["group"] for item in model_chain}:
            model_group_papers["ALL"][group] += 1
            model_group_papers[paper["type"]][group] += 1
        sequence = " -> ".join(section for section, _ in ordered_hits) or "未检出章节标题"
        section_sequences["ALL"][sequence] += 1
        section_sequences[paper["type"]][sequence] += 1
        for source_kind in ("ALL", paper["type"]):
            layout_positions[(source_kind, "caption")].extend(page / paper["pages"] for page in caption_pages)
            layout_positions[(source_kind, "equation")].extend(page / paper["pages"] for page in equation_pages)
        model_chain_text = " -> ".join(
            f"{item['term']}@p{item['page']}" for item in model_chain
        ) or "未检出"
        writing_feature_text = "；".join(
            [
                "连接词=" + "、".join(
                    f"{term}:{count}" for term, count in style_counts.items() if count
                ),
                f"页行中位数={round(statistics.median(line_counts), 2)}",
                f"段落候选中位数={round(statistics.median(paragraph_counts), 2)}",
                f"图表候选={captions}",
                f"公式行候选={equation_lines}",
                f"标题候选={headings}",
            ]
        )
        chains.append({"year": paper["year"], "problem": paper["type"], "paper": paper["paper"],
                       "chain": model_chain})
        first_line = next(
            (
                (page["page"], line_number, item)
                for page in pages
                for line_number, item in enumerate(page["lines"], 1)
                if item["text"].strip()
            ),
            (1, 1, {"text": "", "confidence": pages[0].get("median_confidence", 0)}),
        )
        ledger.append({
            "year": paper["year"], "problem": paper["type"], "paper": paper["paper"],
            "evidence_type": "paper_overview", "section": "", "category": "论文总览",
            "page": first_line[0], "line": first_line[1],
            "confidence": first_line[2].get("confidence", pages[0].get("median_confidence", 0)),
            "model_chain": model_chain_text, "writing_feature": writing_feature_text,
            "source_text": first_line[2]["text"],
            "snippet": snippet(pages, first_line[0], first_line[1]),
            "original_position": (
                f"{paper['year']}/{paper['paper']}.pdf"
                f"#page={first_line[0]}:line={first_line[1]}"
            ),
        })

        summary = {
            "year": paper["year"], "problem": paper["type"], "paper": paper["paper"],
            "pages": paper["pages"], "median_text_lines_per_page": round(statistics.median(line_counts), 2),
            "median_paragraph_candidates_per_page": round(statistics.median(paragraph_counts), 2),
            "median_han_per_page": round(statistics.median(han_counts), 2), "heading_candidates": headings,
            "caption_candidates": captions, "equation_line_candidates": equation_lines,
            "caption_pages": "、".join(map(str, caption_pages)),
            "equation_pages": "、".join(map(str, equation_pages)),
            "fallback_pages": fallback_pages, "unconfirmed_pages": unconfirmed_pages,
            "models_in_chain": "、".join(item["term"] for item in model_chain),
            "section_sequence": sequence,
            "detected_section_count": len(ordered_hits),
        }
        for section, _ in SECTIONS:
            hit = hits.get(section)
            summary[f"{section}_page"] = hit["page"] if hit else ""
            if hit:
                section_start[(paper["type"], section)].append(hit["page"] / paper["pages"])
                ledger.append({
                    "year": paper["year"], "problem": paper["type"], "paper": paper["paper"],
                    "evidence_type": "section_heading", "section": section, "category": section,
                    "page": hit["page"], "line": hit["line"],
                    "confidence": hit["confidence"], "source_text": hit["source_text"],
                    "model_chain": model_chain_text, "writing_feature": writing_feature_text,
                    "snippet": snippet(pages, hit["page"], hit["line"]),
                    "original_position": (
                        f"{paper['year']}/{paper['paper']}.pdf"
                        f"#page={hit['page']}:line={hit['line']}"
                    ),
                })
        for index, (section, hit) in enumerate(ordered_hits):
            next_page = ordered_hits[index + 1][1]["page"] if index + 1 < len(ordered_hits) else paper["pages"] + 1
            span = max(1, next_page - hit["page"])
            section_spans[(paper["type"], section)].append(span)
            section_span_fractions[(paper["type"], section)].append(span / paper["pages"])
        summaries.append(summary)

    if len(summaries) != 59 or sum(row["pages"] for row in summaries) != 2892:
        raise RuntimeError("Post-load corpus total mismatch")

    with (WORK / "paper_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader(); writer.writerows(summaries)
    with (WORK / "evidence_ledger.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger[0]))
        writer.writeheader(); writer.writerows(ledger)
    (WORK / "model_chains.json").write_text(json.dumps(chains, ensure_ascii=False, indent=2), encoding="utf-8")

    page_stats = {kind: descriptive([row["pages"] for row in summaries if kind == "ALL" or row["problem"] == kind])
                  for kind in ("ALL", "A", "B", "C")}
    density_stats = {
        kind: descriptive([row["median_text_lines_per_page"] for row in summaries
                           if kind == "ALL" or row["problem"] == kind])
        for kind in ("ALL", "A", "B", "C")
    }
    paragraph_density_stats = {
        kind: descriptive([row["median_paragraph_candidates_per_page"] for row in summaries
                           if kind == "ALL" or row["problem"] == kind])
        for kind in ("ALL", "A", "B", "C")
    }
    section_stats = {}
    for kind in ("ALL", "A", "B", "C"):
        section_stats[kind] = {}
        for section, _ in SECTIONS:
            start_values, span_values, span_fraction_values = [], [], []
            for source_kind in ("A", "B", "C") if kind == "ALL" else (kind,):
                start_values += section_start[(source_kind, section)]
                span_values += section_spans[(source_kind, section)]
                span_fraction_values += section_span_fractions[(source_kind, section)]
            section_stats[kind][section] = {
                "detected": len(start_values),
                "prevalence": round(len(start_values) / sum(row["problem"] == kind for row in summaries), 4)
                if kind != "ALL" else round(len(start_values) / 59, 4),
                "start_fraction": descriptive(start_values, 4) if start_values else None,
                "page_span": descriptive(span_values) if span_values else None,
                "span_fraction": descriptive(span_fraction_values, 4) if span_fraction_values else None,
            }

    layout_stats = {}
    for kind in ("ALL", "A", "B", "C"):
        selected = [row for row in summaries if kind == "ALL" or row["problem"] == kind]
        layout_stats[kind] = {
            "caption_candidates_per_paper": descriptive([row["caption_candidates"] for row in selected]),
            "equation_line_candidates_per_paper": descriptive([row["equation_line_candidates"] for row in selected]),
            "heading_candidates_per_paper": descriptive([row["heading_candidates"] for row in selected]),
            "caption_page_fraction": descriptive(layout_positions[(kind, "caption")], 4)
            if layout_positions[(kind, "caption")] else None,
            "equation_page_fraction": descriptive(layout_positions[(kind, "equation")], 4)
            if layout_positions[(kind, "equation")] else None,
        }

    corpus = {
        "scope": {"years": [2020, 2021, 2022, 2023, 2024, 2025], "problem_types": ["A", "B", "C"],
                  "papers": 59, "pages": 2892, "excludes": ["D", "E", "赛题原文文风统计", "专家评述文风统计"]},
        "paper_pages": page_stats,
        "text_line_density": density_stats,
        "paragraph_candidate_density": paragraph_density_stats,
        "section_statistics": section_stats,
        "layout_candidates": {
            "captions": sum(row["caption_candidates"] for row in summaries),
            "equation_lines": sum(row["equation_line_candidates"] for row in summaries),
            "headings": sum(row["heading_candidates"] for row in summaries),
            "by_problem_type": layout_stats,
        },
        "ocr": {
            "page_methods": dict(methods),
            "fallback_pages": sum(row["fallback_pages"] for row in summaries),
            "unconfirmed_pages": sum(row["unconfirmed_pages"] for row in summaries),
        },
        "style_connectors": {
            "ALL": dict(all_style),
            **{kind: dict(style_by_type[kind]) for kind in ("A", "B", "C")},
        },
        "model_term_paper_counts": {
            kind: dict(model_term_papers[kind].most_common()) for kind in ("ALL", "A", "B", "C")
        },
        "model_group_paper_counts": {
            kind: dict(model_group_papers[kind].most_common()) for kind in ("ALL", "A", "B", "C")
        },
        "section_sequence_patterns": {
            kind: [
                {"sequence": sequence, "papers": count}
                for sequence, count in section_sequences[kind].most_common(10)
            ]
            for kind in ("ALL", "A", "B", "C")
        },
        "limitations": [
            "章节页数来自标题首次命中到下一标题首次命中的页级跨度，跨页标题与 OCR 误差会造成边界偏差。",
            "文本行密度使用 OCR 文本行块/页的中位数，不把它等同于排版软件中的自然段数。",
            "段落候选由正文行的首行缩进和垂直间距估计，复杂公式、表格及多栏页面会造成偏差。",
            "图表、公式为候选行计数；涉及小字号、公式和表格内容的结论须回看原始栅格裁剪。",
        ],
    }
    (WORK / "corpus_statistics.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "papers": 59, "pages": 2892,
                      "ledger_rows": len(ledger), "statistics": str(WORK / 'corpus_statistics.json')},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
