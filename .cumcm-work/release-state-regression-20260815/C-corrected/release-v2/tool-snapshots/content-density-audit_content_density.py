#!/usr/bin/env python3
"""Audit substantive content density in a compiled CUMCM manuscript.

The audit is deliberately conservative.  Page counts and structural signals can
surface thin or padded sections, but they cannot prove mathematical correctness
or human authorship.  Corpus comparisons are returned as soft hints only.

Public interface:
    python audit_content_density.py <main.tex> --aux <build/main.aux>
        [--coverage coverage.json] [--problem-type A|B|C]
        [--corpus-stats references/fulltext-style-stats.json]
        [--format text|json]
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from audit_competition_length import question_scope_findings

from audit_manuscript import read_tex_tree


LABEL_PATTERN = r"\\newlabel\{{{label}\}}\{{\{{.*?\}}\{{(?P<page>\d+)\}}"
ENV_BLOCKS = (
    "equation", "equation*", "align", "align*", "gather", "gather*",
    "multline", "multline*", "figure", "figure*", "table", "table*",
    "tabular", "tabularx", "longtable", "verbatim", "lstlisting",
    "thebibliography", "itemize", "enumerate", "description",
)
FORMULA_ENVS = r"equation\*?|align\*?|gather\*?|multline\*?"
FIGURE_ENVS = r"figure\*?"
TABLE_FLOAT_ENVS = r"table\*?"
TABULAR_ENVS = r"tabular\*?|tabularx|longtable"
RESULT_CUES = re.compile(
    r"(?:结果|表\s*[0-9一二三四五六七八九十]+|图\s*[0-9一二三四五六七八九十]+|"
    r"高于|低于|相比|增加|减少|变化|误差|稳定|敏感|说明|意味着|原因|边界|约束)"
)
GENERIC_ONLY = re.compile(
    r"^(?:由此可知|综上所述|因此|从而|进一步地|此外|同时|最后|总的来说|"
    r"可以看出|结果表明|这说明|上述分析表明)[，,。；;：: ]*$"
)
SECTION_CATEGORIES = {
    "background": ("问题重述", "问题分析", "模型假设", "符号说明", "摘要"),
    "model": ("模型建立", "模型构建", "模型假设", "符号说明", "模型分析"),
    "solve": ("求解", "算法", "计算", "优化", "训练", "滚动验证", "数值"),
    "result": ("结果", "预测", "分析", "建议", "结论"),
    "validation": ("检验", "验证", "灵敏度", "敏感性", "稳健性", "误差"),
    "evaluation": ("评价", "改进", "复现", "局限"),
}
CORPUS_GROUPS = {
    "background": ("restatement", "analysis", "assumption", "notation"),
    "model": ("model",),
    "solve": ("solve",),
    "result": ("result",),
    "validation": ("validation", "sensitivity"),
    "evaluation": ("evaluation", "improvement"),
}


@dataclass(frozen=True)
class Heading:
    level: str
    title: str
    start: int
    end: int


def label_page(aux_text: str, label: str) -> int | None:
    match = re.search(LABEL_PATTERN.format(label=re.escape(label)), aux_text)
    return int(match.group("page")) if match else None


def normalize_tex(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def _remove_environment(text: str, env: str) -> str:
    pattern = re.compile(
        rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}",
        re.S,
    )
    return pattern.sub("\n\n", text)


def _blank_preserving_newlines(match: re.Match[str]) -> str:
    """Mask a non-prose block without changing offsets in the TeX source."""
    return re.sub(r"[^\n]", " ", match.group(0))


def masked_prose_source(text: str) -> str:
    """Blank display/code/list blocks while preserving source positions."""
    for env in ENV_BLOCKS:
        pattern = re.compile(
            rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}",
            re.S,
        )
        text = pattern.sub(_blank_preserving_newlines, text)
    text = re.sub(
        r"\$\$.*?\$\$|\\\[.*?\\\]",
        _blank_preserving_newlines,
        text,
        flags=re.S,
    )
    return text


def visible_prose(text: str) -> str:
    """Remove display/code blocks while retaining ordinary command arguments."""
    for env in ENV_BLOCKS:
        text = _remove_environment(text, env)
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", "\n\n", text, flags=re.S)
    text = re.sub(r"\$(?:\\.|[^$])*\$", " ", text)
    text = re.sub(r"\\(?:cite|parencite|ref|eqref|label|url|href)\s*(?:\[[^]]*\])?\s*\{[^{}]*\}", " ", text)
    # Keep the argument of common formatting commands, then remove residual commands.
    for _ in range(3):
        text = re.sub(r"\\[A-Za-z@]+\*?\s*(?:\[[^]]*\])?\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?", " ", text)
    text = re.sub(r"\{[^{}]*\}", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return re.sub(r"[ \t\r]+", " ", text)


def headings(text: str) -> list[Heading]:
    found: list[Heading] = []
    pattern = re.compile(r"\\(section|subsection|subsubsection)\*?\s*\{([^{}]*)\}")
    for match in pattern.finditer(text):
        found.append(Heading(match.group(1), visible_prose(match.group(2)).strip(), match.start(), match.end()))
    for index, item in enumerate(found):
        end = found[index + 1].start if index + 1 < len(found) else len(text)
        found[index] = Heading(item.level, item.title, item.start, end)
    return found


def active_titles(items: list[Heading], position: int) -> list[str]:
    """Return the latest active heading at each TeX level."""
    latest: dict[str, str] = {}
    lower = {"section": ("subsection", "subsubsection"), "subsection": ("subsubsection",), "subsubsection": ()}
    for item in items:
        if item.start > position:
            break
        for level in lower[item.level]:
            latest.pop(level, None)
        latest[item.level] = item.title
    return [latest[level] for level in ("section", "subsection", "subsubsection") if level in latest]


def category_for(titles: list[str]) -> str:
    if not titles:
        return "other"
    joined = " ".join(titles)
    top = titles[0]
    child = " ".join(titles[1:])
    # A concrete child heading describes the local paragraph more accurately
    # than a combined parent such as “结果分析、模型检验与跨问复核”.
    if child:
        if any(token in child for token in ("评价", "改进", "复现", "局限")):
            return "evaluation"
        if any(token in child for token in ("检验", "验证", "灵敏度", "敏感性", "稳健性", "误差", "闭合", "复核", "对照")):
            return "validation"
        if any(token in child for token in ("结果", "预测", "结论", "比较", "差异", "输出", "解释")):
            return "result"
        if any(token in child for token in ("求解", "算法", "计算", "优化", "训练", "数值", "搜索", "仿真", "回放")):
            return "solve"
        if any(token in child for token in ("模型", "方程", "变量", "约束", "特征", "目标函数", "状态关系")):
            return "model"
    if any(token in top for token in ("模型评价", "进一步数据", "改进", "复现说明")):
        return "evaluation"
    has_result = any(token in top for token in ("结果", "结论", "预测", "建议", "输出"))
    has_validation = any(token in top for token in ("检验", "验证", "灵敏度", "敏感性", "稳健性", "误差"))
    if has_result and has_validation:
        return "result"
    if has_validation:
        return "validation"
    if has_result:
        return "result"
    if re.search(r"模型(?:的)?(?:建立|构建).*求解", top):
        if any(token in child for token in ("模型", "特征", "方程", "变量", "约束", "目标函数")):
            return "model"
        if any(token in child for token in ("求解", "算法", "计算", "优化", "训练", "验证", "数值", "搜索", "仿真", "回放")):
            return "solve"
        return "model"
    if any(token in joined for token in ("求解", "算法", "计算", "优化", "训练", "数值", "搜索", "仿真", "回放")):
        return "solve"
    if any(token in top for token in ("问题重述", "问题分析", "模型假设", "符号说明", "摘要")):
        return "background"
    if any(token in joined for token in ("模型", "方程", "变量", "约束", "特征", "目标函数")):
        return "model"
    return "other"


def paragraphs(text: str, start: int, end: int) -> list[tuple[int, str]]:
    source = text[start:end]
    prose = masked_prose_source(source)
    output: list[tuple[int, str]] = []
    chunk_pattern = re.compile(
        r"(?:\A|\n[ \t]*\n)(?P<chunk>.*?)(?=\n[ \t]*\n|\Z)",
        re.S,
    )
    heading_pattern = re.compile(
        r"\\(?:section|subsection|subsubsection)\*?\s*\{[^{}]*\}"
    )
    for match in chunk_pattern.finditer(prose):
        chunk = match.group("chunk")
        chunk_start = match.start("chunk")
        raw_chunk = source[chunk_start:match.end("chunk")]
        value = re.sub(r"\s+", " ", visible_prose(chunk)).strip()
        if len(re.findall(r"[\u3400-\u9fff]", value)) < 18:
            continue
        position = start + chunk_start
        local_headings = list(heading_pattern.finditer(raw_chunk))
        if local_headings:
            position += local_headings[-1].end()
        output.append((position, value))
    return output


def han_chars(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def tex_count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.S))


def normalize_paragraph(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    return re.sub(r"[，。；：、,.!?！？()（）【】\[\]{}]", "", value)


def duplicate_findings(values: list[str]) -> dict:
    normalized = [normalize_paragraph(value) for value in values]
    counts: dict[str, int] = {}
    for value in normalized:
        if len(value) >= 30:
            counts[value] = counts.get(value, 0) + 1
    exact = {key: count for key, count in counts.items() if count > 1}
    near = 0
    candidates = [value for value in normalized if len(value) >= 40]
    for index, value in enumerate(candidates):
        for other in candidates[index + 1:]:
            if value == other:
                continue
            if value[:36] == other[:36] and difflib.SequenceMatcher(None, value, other).ratio() >= 0.92:
                near += 1
    return {"exact_groups": len(exact), "exact_repeats": sum(count - 1 for count in exact.values()), "near_pairs": near}


def low_information(values: list[str]) -> dict:
    generic = 0
    for value in values:
        compact = re.sub(r"\s+", "", value)
        if GENERIC_ONLY.match(compact) or (len(compact) < 32 and not re.search(r"[0-9A-Za-z]|公式|方程|约束|误差|结果", compact)):
            generic += 1
    return {"count": generic, "ratio": round(generic / len(values), 4) if values else 0.0}


def corpus_hints(metrics: dict, stats_path: Path | None, problem_type: str | None) -> list[str]:
    if stats_path is None or not stats_path.is_file() or problem_type not in {"A", "B", "C"}:
        return []
    payload = json.loads(stats_path.read_text(encoding="utf-8-sig"))
    hints: list[str] = []
    sections = payload.get("section_by_problem_type", {}).get(problem_type, {})
    for category, names in CORPUS_GROUPS.items():
        current = metrics["categories"].get(category, {})
        chars = current.get("han_chars", 0)
        total = metrics.get("han_chars", 0) or 1
        share = chars / total
        observed = []
        for name in names:
            entry = sections.get(name) or payload.get("by_section", {}).get(name)
            if entry and entry.get("share_of_paper_han"):
                observed.append(entry["share_of_paper_han"])
        if not observed:
            continue
        q1 = min(item.get("q1", 0) for item in observed)
        q3 = max(item.get("q3", 1) for item in observed)
        if share > q3 * 1.35:
            hints.append(f"{category} 篇幅占比 {share:.1%} 高于语料四分位上沿 {q3:.1%}，检查是否背景或通用评价过长")
        elif share < q1 * 0.65:
            hints.append(f"{category} 篇幅占比 {share:.1%} 低于语料四分位下沿 {q1:.1%}，检查是否缺少真实推导、求解或解释")
    return hints


def question_metrics(text: str, aux: str, question: dict, headings_list: list[Heading]) -> dict:
    question_id = str(question.get("id", "unnamed"))
    start_label = question.get("start_label")
    end_label = question.get("end_label")
    start_page = label_page(aux, str(start_label)) if start_label else None
    end_page = label_page(aux, str(end_label)) if end_label else None
    source_start = re.search(rf"\\label\s*\{{{re.escape(str(start_label))}\}}", text) if start_label else None
    source_end = re.search(rf"\\label\s*\{{{re.escape(str(end_label))}\}}", text) if end_label else None
    if source_start and source_end and source_start.start() < source_end.start():
        spans = [(source_start.start(), source_end.end())]
    else:
        title_patterns = question.get("section_titles", [])
        if isinstance(title_patterns, str):
            title_patterns = [title_patterns]
        selected = [
            item for item in headings_list
            if any(re.search(pattern, item.title, re.I) for pattern in title_patterns)
        ]
        spans = [(item.start, item.end) for item in selected]
    if not spans:
        return {
            "id": question_id,
            "pages": None if start_page is None or end_page is None else end_page - start_page + 1,
            "paragraphs": 0,
            "han_chars": 0,
            "formulas": 0,
            "figures": 0,
            "tables": 0,
            "tabular_blocks": 0,
            "result_explanations": 0,
            "status": "unlocated",
        }
    blocks = [text[start:end] for start, end in spans]
    values = [value for start, end in spans for _, value in paragraphs(text, start, end)]
    return {
        "id": question_id,
        "pages": None if start_page is None or end_page is None else end_page - start_page + 1,
        "paragraphs": len(values),
        "han_chars": sum(han_chars(value) for value in values),
        "formulas": sum(tex_count(block, rf"\\begin\{{{FORMULA_ENVS}\}}|\\\[") for block in blocks),
        "figures": sum(tex_count(block, rf"\\begin\{{{FIGURE_ENVS}\}}") for block in blocks),
        "tables": sum(tex_count(block, rf"\\begin\{{{TABLE_FLOAT_ENVS}\}}") for block in blocks),
        "tabular_blocks": sum(tex_count(block, rf"\\begin\{{{TABULAR_ENVS}\}}") for block in blocks),
        "result_explanations": sum(bool(RESULT_CUES.search(value)) for value in values),
        "status": "located",
    }


def audit(
    main_tex: Path,
    aux_path: Path | None = None,
    coverage_path: Path | None = None,
    problem_type: str | None = None,
    corpus_stats_path: Path | None = None,
) -> dict:
    raw = normalize_tex(read_tex_tree(main_tex))
    start_marker = raw.find(r"\label{mcm-body-start}")
    end_marker = raw.find(r"\label{mcm-body-end}")
    body_start = start_marker if start_marker >= 0 else 0
    body_end = end_marker if end_marker >= 0 else len(raw)
    body = raw[body_start:body_end]
    heading_list = headings(raw)
    body_headings = [item for item in heading_list if body_start <= item.start < body_end]
    values = [value for _, value in paragraphs(raw, body_start, body_end)]
    category_values: dict[str, list[str]] = {key: [] for key in (*SECTION_CATEGORIES.keys(), "other")}
    for position, value in paragraphs(raw, body_start, body_end):
        category_values[category_for(active_titles(heading_list, position))].append(value)
    categories = {
        key: {
            "paragraphs": len(items),
            "han_chars": sum(han_chars(item) for item in items),
            "share": round(sum(han_chars(item) for item in items) / (sum(han_chars(v) for v in values) or 1), 4),
            "result_explanations": sum(bool(RESULT_CUES.search(item)) for item in items),
        }
        for key, items in category_values.items()
    }
    metrics = {
        "paragraphs": len(values),
        "han_chars": sum(han_chars(value) for value in values),
        "formulas": tex_count(body, rf"\\begin\{{{FORMULA_ENVS}\}}|\\\["),
        "figures": tex_count(body, rf"\\begin\{{{FIGURE_ENVS}\}}"),
        "tables": tex_count(body, rf"\\begin\{{{TABLE_FLOAT_ENVS}\}}"),
        "tabular_blocks": tex_count(body, rf"\\begin\{{{TABULAR_ENVS}\}}"),
        "result_explanations": sum(bool(RESULT_CUES.search(value)) for value in values),
        "categories": categories,
    }
    duplicates = duplicate_findings(values)
    low_info = low_information(values)
    findings: list[dict] = []
    if start_marker < 0 or end_marker < 0:
        findings.append({"severity": "warning", "code": "BODY_MARKER_MISSING"})
    if duplicates["exact_repeats"] or duplicates["near_pairs"]:
        findings.append({"severity": "warning", "code": "REPEATED_PROSE", **duplicates})
    if low_info["ratio"] > 0.08:
        findings.append({"severity": "warning", "code": "LOW_INFORMATION_PROSE", **low_info})
    padding = {
        "manual_breaks": len(re.findall(r"\\(?:newpage|clearpage|pagebreak)\b", body)),
        "vertical_space_commands": len(re.findall(r"\\vspace\*?\s*\{", body)),
        "fill_commands": len(re.findall(r"\\(?:vfill|hfill|phantom)\b", body)),
    }
    if padding["vertical_space_commands"] or padding["fill_commands"]:
        findings.append({"severity": "warning", "code": "LAYOUT_PADDING_SIGNAL", **padding})
    aux = aux_path.read_text(encoding="utf-8-sig", errors="replace") if aux_path and aux_path.is_file() else ""
    questions = []
    if coverage_path and coverage_path.is_file():
        payload = json.loads(coverage_path.read_text(encoding="utf-8-sig"))
        findings.extend(question_scope_findings(raw, payload))
        questions = [question_metrics(raw, aux, question, body_headings) for question in payload.get("questions", [])]
    corpus_hints_list = corpus_hints(metrics, corpus_stats_path, problem_type)
    return {
        "status": "pass" if not any(item["severity"] == "error" for item in findings) else "fail",
        "file": str(main_tex.resolve()),
        "problem_type": problem_type,
        "body": metrics,
        "questions": questions,
        "duplicates": duplicates,
        "low_information": low_info,
        "padding": padding,
        "soft_hints": corpus_hints_list,
        "findings": findings,
        "errors": sum(item["severity"] == "error" for item in findings),
        "warnings": sum(item["severity"] == "warning" for item in findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--aux", type=Path)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--problem-type", choices=("A", "B", "C"))
    parser.add_argument("--corpus-stats", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.corpus_stats is None:
        args.corpus_stats = Path(__file__).resolve().parents[1] / "references" / "fulltext-style-stats.json"
    report = audit(args.main_tex, args.aux, args.coverage, args.problem_type, args.corpus_stats)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        body = report["body"]
        print(
            f"CONTENT DENSITY {report['status'].upper()} errors={report['errors']} warnings={report['warnings']} "
            f"paragraphs={body['paragraphs']} han_chars={body['han_chars']} formulas={body['formulas']} "
            f"figures={body['figures']} table_floats={body['tables']} tabular_blocks={body['tabular_blocks']} "
            f"result_explanations={body['result_explanations']}"
        )
        for question in report["questions"]:
            print(
                f"QUESTION {question['id']} pages={question['pages']} paragraphs={question['paragraphs']} "
                f"formulas={question['formulas']} visuals={question['figures'] + question['tables']} "
                f"result_explanations={question['result_explanations']}"
            )
        for item in report["findings"]:
            print(f"[{item['severity'].upper()}] {item['code']}: " + ", ".join(f"{k}={v}" for k, v in item.items() if k not in {"severity", "code"}))
        for hint in report["soft_hints"]:
            print(f"[SOFT] {hint}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
