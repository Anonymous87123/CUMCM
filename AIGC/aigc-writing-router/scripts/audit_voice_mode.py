#!/usr/bin/env python3
"""Audit whether mixed long-form documents use section-appropriate voices.

The scanner separates research prose, evidence appendices, and operator manuals.
Its findings are review signals, never AI-authorship or naturalness judgments.

Public interface:
    python audit_voice_mode.py <document.tex> --format text|json

Exit codes: 0=PASS, 2=REVIEW, 1=input error.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path


HEADING_RE = re.compile(
    r"\\(section|subsection|subsubsection)\*?\s*(?:\[[^]]*\])?\s*\{([^{}]*)\}"
)
LIST_RE = re.compile(
    r"\\begin\{(itemize|enumerate|description)\}(.*?)\\end\{\1\}", re.S
)
MASK_ENVS = (
    "itemize", "enumerate", "description", "figure", "figure*", "table", "table*",
    "tabular", "tabularx", "longtable", "equation", "equation*", "align", "align*",
    "gather", "gather*", "multline", "multline*", "verbatim", "lstlisting", "minted",
    "thebibliography",
)
OPERATOR_TERMS = (
    "操作手册", "使用手册", "使用说明", "运行步骤", "操作步骤", "实战步骤",
    "答题动作", "执行清单", "检查清单", "工作流程", "速查", "速记", "动作卡",
)
EVIDENCE_TERMS = (
    "附录", "证据", "文件索引", "文件清单", "原始记录", "复核记录", "运行日志",
    "数据口径", "字段说明", "明细表", "来源表", "哈希",
)
IMPERATIVE_RE = re.compile(
    r"^(?:先|再|然后|请|不要|避免|检查|打开|运行|把|选择|填写|确认|记录|读取|比较|观察|计算|使用)"
)
LABEL_RE = re.compile(
    r"^(?:结论|解释|判断|依据|原因|建议|正确用法|错误用法|操作|步骤|目的|方法|提示|注意)[：:]"
)


@dataclass(frozen=True)
class Paragraph:
    line: int
    text: str
    han_chars: int


@dataclass(frozen=True)
class Segment:
    title: str
    title_path: str
    mode: str
    line: int
    start: int
    end: int
    paragraphs: tuple[Paragraph, ...]
    list_blocks: int
    list_items: int
    one_item_lists: int
    labeled_list_items: int


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def visible_tex(text: str) -> str:
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " ", text, flags=re.S)
    text = re.sub(r"\$(?:\\.|[^$])*\$", " ", text)
    text = re.sub(
        r"\\(?:cite|parencite|ref|eqref|autoref|label|url|href)\s*"
        r"(?:\[[^]]*\])?\s*\{[^{}]*\}",
        " ", text,
    )
    for _ in range(3):
        text = re.sub(r"\\[A-Za-z@]+\*?\s*(?:\[[^]]*\])?\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_mode(title_path: str) -> str:
    compact = re.sub(r"\s+", "", title_path)
    if any(term in compact for term in OPERATOR_TERMS):
        return "operator"
    if any(term in compact for term in EVIDENCE_TERMS):
        return "evidence"
    return "prose"


def _mask_environments(text: str) -> str:
    for env in MASK_ENVS:
        pattern = re.compile(
            rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}", re.S
        )
        text = pattern.sub(_blank, text)
    return text


def _paragraphs(full_text: str, body: str, offset: int) -> tuple[Paragraph, ...]:
    masked = _mask_environments(body)
    masked = HEADING_RE.sub(_blank, masked)
    chunks = re.finditer(r"(?:\A|\n[ \t]*\n)(.*?)(?=\n[ \t]*\n|\Z)", masked, re.S)
    output: list[Paragraph] = []
    for match in chunks:
        raw = match.group(1)
        value = visible_tex(raw)
        han = len(re.findall(r"[\u3400-\u9fff]", value))
        # This portfolio audit targets Chinese long-form writing.  File names,
        # generated TOC fragments, and code-only chunks are not prose rhythm.
        if han < 12:
            continue
        first_visible = re.search(r"\S", raw)
        start = offset + match.start(1) + (first_visible.start() if first_visible else 0)
        output.append(Paragraph(line_number(full_text, start), value, han))
    return tuple(output)


def parse_document(text: str) -> list[Segment]:
    clean = strip_comments(text)
    matches = list(HEADING_RE.finditer(clean))
    if not matches:
        paragraphs = _paragraphs(clean, clean, 0)
        return [Segment(
            title="(document)", title_path="(document)", mode="prose", line=1,
            start=0, end=len(clean), paragraphs=paragraphs,
            list_blocks=0, list_items=0, one_item_lists=0, labeled_list_items=0,
        )]

    segments: list[Segment] = []
    top_title = ""
    for index, match in enumerate(matches):
        level = match.group(1)
        title = visible_tex(match.group(2)) or "(untitled)"
        if level == "section":
            top_title = title
        title_path = title if not top_title or top_title == title else f"{top_title} / {title}"
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        body = clean[start:end]
        list_blocks = 0
        list_items = 0
        one_item_lists = 0
        labeled_items = 0
        for list_match in LIST_RE.finditer(body):
            list_blocks += 1
            items = re.split(r"\\item(?:\[[^]]*\])?", list_match.group(2))[1:]
            item_texts = [visible_tex(item) for item in items if visible_tex(item)]
            list_items += len(item_texts)
            one_item_lists += len(item_texts) == 1
            labeled_items += sum(bool(LABEL_RE.match(item)) for item in item_texts)
        segments.append(Segment(
            title=title,
            title_path=title_path,
            mode=classify_mode(title_path),
            line=line_number(clean, match.start()),
            start=start,
            end=end,
            paragraphs=_paragraphs(clean, body, start),
            list_blocks=list_blocks,
            list_items=list_items,
            one_item_lists=one_item_lists,
            labeled_list_items=labeled_items,
        ))
    return segments


def audit(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    segments = parse_document(text)
    findings: list[dict] = []

    for segment in segments:
        paragraph_count = len(segment.paragraphs)
        if segment.mode == "prose":
            if segment.one_item_lists >= 2:
                findings.append({
                    "severity": "review", "code": "PROSE_ONE_ITEM_LIST_CHAIN",
                    "line": segment.line, "section": segment.title_path,
                    "evidence": f"one_item_lists={segment.one_item_lists}",
                    "suggestion": "确认这些单项列表是否应恢复为连续论述；真实清单可以保留。",
                })
            if segment.list_blocks >= 3 and (
                segment.list_blocks >= max(3, paragraph_count) or
                segment.list_items >= 8 and segment.list_blocks * 2 >= max(1, paragraph_count)
            ):
                findings.append({
                    "severity": "review", "code": "PROSE_LIST_DOMINANCE",
                    "line": segment.line, "section": segment.title_path,
                    "evidence": (
                        f"list_blocks={segment.list_blocks}, list_items={segment.list_items}, "
                        f"prose_paragraphs={paragraph_count}"
                    ),
                    "suggestion": "保留真并列项，把承担同一判断的卡片式列表改成有起落的正文。",
                })
            if segment.labeled_list_items >= 3:
                findings.append({
                    "severity": "review", "code": "PROSE_LABEL_CARD_CHAIN",
                    "line": segment.line, "section": segment.title_path,
                    "evidence": f"labeled_list_items={segment.labeled_list_items}",
                    "suggestion": "检查“结论/解释/建议”等标签是否只是重复模板，而非真实层级。",
                })
            imperative = sum(bool(IMPERATIVE_RE.match(item.text)) for item in segment.paragraphs)
            if paragraph_count >= 4 and imperative >= 3 and imperative / paragraph_count >= 0.6:
                findings.append({
                    "severity": "review", "code": "PROSE_IMPERATIVE_DOMINANCE",
                    "line": segment.line, "section": segment.title_path,
                    "evidence": f"imperative_paragraphs={imperative}/{paragraph_count}",
                    "suggestion": "研究正文应解释材料和判断；把真正的操作命令移入手册或改写其论证职责。",
                })
        elif segment.mode == "operator":
            for paragraph in segment.paragraphs:
                if paragraph.han_chars > 300:
                    findings.append({
                        "severity": "review", "code": "OPERATOR_DENSE_PARAGRAPH",
                        "line": paragraph.line, "section": segment.title_path,
                        "evidence": f"han_chars={paragraph.han_chars}",
                        "suggestion": "操作区可拆成可执行步骤；无需把命令式语言改成研究正文。",
                    })

    mode_counts = {mode: 0 for mode in ("prose", "evidence", "operator")}
    for segment in segments:
        mode_counts[segment.mode] += 1
    return {
        "schema": "aigc-voice-mode-audit/v1",
        "status": "review" if findings else "pass",
        "document": str(path.resolve()),
        "summary": {
            "segments": len(segments),
            "modes": mode_counts,
            "findings": len(findings),
        },
        "segments": [
            {
                **{key: value for key, value in asdict(segment).items() if key != "paragraphs"},
                "paragraph_count": len(segment.paragraphs),
            }
            for segment in segments
        ],
        "findings": findings,
        "disclaimer": "Heuristic section-role review only; not an AI-authorship or naturalness judgment.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if not args.document.is_file():
        parser.error(f"document not found: {args.document}")
    report = audit(args.document)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["summary"]
        print(
            f"VOICE MODE {report['status'].upper()} segments={summary['segments']} "
            f"prose={summary['modes']['prose']} evidence={summary['modes']['evidence']} "
            f"operator={summary['modes']['operator']} findings={summary['findings']}"
        )
        for item in report["findings"]:
            print(
                f"[REVIEW] {item['code']} line={item['line']} section={item['section']}: "
                f"{item['evidence']} | {item['suggestion']}"
            )
        print("NOTE: findings locate section-role tension; they do not identify AI authorship.")
    return 2 if report["status"] == "review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
