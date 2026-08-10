"""Render auditable corpus statistics into reviewable TeX and Markdown snippets."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
SECTIONS = [
    "摘要", "问题重述", "问题分析", "模型假设", "符号说明", "模型建立", "模型求解",
    "结果分析", "模型检验", "灵敏度分析", "模型评价", "改进方案", "参考文献", "附录",
]


def number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def interval(stats: dict) -> str:
    return f"{number(stats['median'])} [{number(stats['q1'])}, {number(stats['q3'])}]"


def pct(value: float) -> str:
    return f"{100 * value:.1f}"


def main() -> None:
    source = WORK / "corpus_statistics.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    if data["scope"]["papers"] != 59 or data["scope"]["pages"] != 2892:
        raise RuntimeError("Corpus scope is not the required 59 papers / 2892 pages")

    pages = data["paper_pages"]
    lines = data["text_line_density"]["ALL"]
    paragraphs = data["paragraph_candidate_density"]["ALL"]
    sections = data["section_statistics"]["ALL"]
    ocr = data["ocr"]
    layout = data["layout_candidates"]

    section_rows = []
    for name in SECTIONS:
        row = sections[name]
        span = interval(row["page_span"]) if row["page_span"] else "--"
        fraction = interval(row["span_fraction"]) if row["span_fraction"] else "--"
        start = interval(row["start_fraction"]) if row["start_fraction"] else "--"
        section_rows.append(
            f"{name} & {row['detected']}/59 ({pct(row['prevalence'])}\\%) & "
            f"{start} & {span} & {fraction} \\\\"
        )

    type_lines = []
    for kind in ("A", "B", "C"):
        group_counts = data["model_group_paper_counts"][kind]
        top = "、".join(f"{name} {count} 篇" for name, count in list(group_counts.items())[:3])
        type_lines.append(f"{kind} 类总页数 {interval(pages[kind])} 页，模型组检出前三项为 {top}")

    layout_all = layout["by_problem_type"]["ALL"]
    tex = [
        f"\\newcommand{{\\CorpusPageMedian}}{{{number(pages['ALL']['median'])}}}",
        f"\\newcommand{{\\CorpusPageIQR}}{{{number(pages['ALL']['q1'])}--{number(pages['ALL']['q3'])}}}",
        f"\\newcommand{{\\CorpusLineMedian}}{{{number(lines['median'])}}}",
        f"\\newcommand{{\\CorpusParagraphMedian}}{{{number(paragraphs['median'])}}}",
        f"\\newcommand{{\\CorpusFallbackPages}}{{{ocr['fallback_pages']}}}",
        f"\\newcommand{{\\CorpusUnconfirmedPages}}{{{ocr['unconfirmed_pages']}}}",
        "\\newcommand{\\CorpusSectionSummary}{十四类章节的检出率和页级跨度见表~\\ref{tab:section-stats}}",
        (
            "\\newcommand{\\CorpusLayoutSummary}{每篇图表标题候选数的中位数及四分位范围为 "
            f"{interval(layout_all['caption_candidates_per_paper'])}，公式行候选对应为 "
            f"{interval(layout_all['equation_line_candidates_per_paper'])}；两类候选页在全文相对位置的"
            f"中位数分别为 {pct(layout_all['caption_page_fraction']['median'])}\\% 和 "
            f"{pct(layout_all['equation_page_fraction']['median'])}\\%。}}"
        ),
        "\\newcommand{\\CorpusTypeSummary}{" + "；".join(type_lines) + "。}",
        "",
        "\\begin{longtable}{p{2.0cm}p{3.1cm}p{3.0cm}p{3.0cm}p{3.0cm}}",
        "\\caption{十四类章节的全语料检出与页级位置统计}\\label{tab:section-stats}\\\\",
        "\\toprule",
        "章节 & 检出论文 & 首次位置比例中位数 [Q1,Q3] & 跨度页数中位数 [Q1,Q3] & 跨度比例中位数 [Q1,Q3]\\\\",
        "\\midrule",
        "\\endfirsthead",
        "\\toprule",
        "章节 & 检出论文 & 首次位置比例中位数 [Q1,Q3] & 跨度页数中位数 [Q1,Q3] & 跨度比例中位数 [Q1,Q3]\\\\",
        "\\midrule",
        "\\endhead",
        *section_rows,
        "\\bottomrule",
        "\\end{longtable}",
    ]
    (WORK / "statistics-snippet.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    md = [
        "# Corpus statistics review",
        "",
        "- Scope: 2020--2025 A/B/C, 59 papers, 2892 pages.",
        f"- Pages ALL: {interval(pages['ALL'])}; A: {interval(pages['A'])}; B: {interval(pages['B'])}; C: {interval(pages['C'])}.",
        f"- OCR methods: {json.dumps(ocr['page_methods'], ensure_ascii=False)}.",
        f"- Tesseract fallback attempted: {ocr['fallback_pages']} pages; unconfirmed after selection: {ocr['unconfirmed_pages']} pages.",
        f"- Layout candidates: {layout['captions']} captions, {layout['equation_lines']} equation lines, {layout['headings']} headings.",
        "",
        "## Section evidence",
        "",
        "| Section | Detected | Prevalence | Start fraction median [Q1,Q3] | Span pages median [Q1,Q3] | Span fraction median [Q1,Q3] |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in SECTIONS:
        row = sections[name]
        md.append(
            f"| {name} | {row['detected']} | {pct(row['prevalence'])}% | "
            f"{interval(row['start_fraction']) if row['start_fraction'] else '--'} | "
            f"{interval(row['page_span']) if row['page_span'] else '--'} | "
            f"{interval(row['span_fraction']) if row['span_fraction'] else '--'} |"
        )
    (WORK / "statistics-review.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "tex": str(WORK / "statistics-snippet.tex"),
                      "review": str(WORK / "statistics-review.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
