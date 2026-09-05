#!/usr/bin/env python3
"""Locate repetitive paragraph rhythm in Chinese long-form documents.

The audit is deterministic and read-only. It flags passages for human reading;
it neither predicts authorship nor recommends blind synonym replacement.

Public interface:
    python audit_style_rhythm.py <document.tex> --mode auto|prose|mixed
        --format text|json

Exit codes: 0=PASS, 2=REVIEW, 1=input error.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path

from audit_voice_mode import Paragraph, Segment, parse_document


OPENING_MARKERS = (
    "首先", "其次", "再次", "最后", "进一步", "此外", "同时", "综上",
    "由此", "因此", "从而", "具体而言", "需要指出的是", "值得注意的是",
    "在此基础上", "本文", "本题", "本节", "我们",
)
CLOSING_MARKERS = (
    "这说明", "由此可见", "综上可知", "结果表明", "上述结果表明", "可以看出",
)
HIGH_RISK_SENTENCE_SHELLS = (
    (
        "CONTRAST_CORRECTION_SHELL",
        re.compile(r"不是[^。！？!?\n]{0,48}?[，,；;]?\s*而是"),
        "先判断这组排他关系是否属于定义或约束；若只是行文纠偏，直接写对象性质和采用的处理，不保留统一的‘不是……而是……’句壳。",
    ),
)


def compact_han(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def opening_signature(text: str) -> str:
    compact = re.sub(r"^[（(\[【\s]*", "", text)
    for marker in OPENING_MARKERS:
        if compact.startswith(marker):
            return marker
    value = compact_han(compact)
    return value[:8] if len(value) >= 8 else value


def closing_signature(text: str) -> str | None:
    tail = re.sub(r"\s+", "", text)[-32:]
    for marker in CLOSING_MARKERS:
        if marker in tail:
            return marker
    return None


def _selected_segments(segments: list[Segment], mode: str) -> list[tuple[Segment, int]]:
    selected: list[tuple[Segment, int]] = []
    for segment in segments:
        if mode == "auto" and segment.mode != "prose":
            continue
        if mode == "prose":
            threshold_boost = 0
        elif mode == "mixed" and segment.mode != "prose":
            threshold_boost = 2
        else:
            threshold_boost = 0
        selected.append((segment, threshold_boost))
    return selected


def audit(path: Path, mode: str = "auto") -> dict:
    text = path.read_text(encoding="utf-8-sig")
    segments = parse_document(text)
    selected = _selected_segments(segments, mode)
    findings: list[dict] = []
    analyzed_paragraphs = 0

    for segment, boost in selected:
        paragraphs = list(segment.paragraphs)
        analyzed_paragraphs += len(paragraphs)
        if not paragraphs:
            continue

        for code, pattern, suggestion in HIGH_RISK_SENTENCE_SHELLS:
            matches: list[tuple[Paragraph, str]] = []
            for item in paragraphs:
                matches.extend((item, match.group(0)) for match in pattern.finditer(item.text))
            if matches:
                findings.append({
                    "severity": "review", "code": code,
                    "line": matches[0][0].line, "section": segment.title_path,
                    "evidence": {
                        "count": len(matches),
                        "examples": [match for _, match in matches[:3]],
                    },
                    "suggestion": suggestion,
                })

        openings = Counter(opening_signature(item.text) for item in paragraphs)
        for signature, count in openings.items():
            threshold = 3 + boost
            if not signature or count < threshold:
                continue
            first = next(item for item in paragraphs if opening_signature(item.text) == signature)
            examples = [item.text[:42] for item in paragraphs if opening_signature(item.text) == signature][:3]
            findings.append({
                "severity": "review", "code": "REPEATED_PARAGRAPH_OPENING",
                "line": first.line, "section": segment.title_path,
                "evidence": {"signature": signature, "count": count, "examples": examples},
                "suggestion": "先核对事实顺序是否真的相同；需要改时重组段落职责，不做连接词轮换。",
            })

        closings = Counter(filter(None, (closing_signature(item.text) for item in paragraphs)))
        for signature, count in closings.items():
            threshold = 4 + boost
            if count < threshold:
                continue
            first = next(item for item in paragraphs if closing_signature(item.text) == signature)
            findings.append({
                "severity": "review", "code": "REPEATED_PARAGRAPH_CLOSURE",
                "line": first.line, "section": segment.title_path,
                "evidence": {"signature": signature, "count": count},
                "suggestion": "删除不承担新判断的统一收束句，保留真正限定结论范围的句子。",
            })

        window_size = 5 + boost
        for index in range(0, len(paragraphs) - window_size + 1):
            window = paragraphs[index:index + window_size]
            lengths = [item.han_chars for item in window]
            mean = sum(lengths) / len(lengths)
            if mean >= 28 and max(lengths) - min(lengths) <= max(14, int(mean * 0.18)):
                findings.append({
                    "severity": "review", "code": "UNIFORM_PARAGRAPH_RUN",
                    "line": window[0].line, "section": segment.title_path,
                    "evidence": {"han_lengths": lengths},
                    "suggestion": "检查是否把不同轻重的内容修成等长卡片；篇幅应随推导和判断负担变化。",
                })
                break

        short_size = 5 + boost
        for index in range(0, len(paragraphs) - short_size + 1):
            window = paragraphs[index:index + short_size]
            lengths = [item.han_chars for item in window]
            if lengths and max(lengths) <= 45:
                findings.append({
                    "severity": "review", "code": "SHORT_PARAGRAPH_CHAIN",
                    "line": window[0].line, "section": segment.title_path,
                    "evidence": {"han_lengths": lengths},
                    "suggestion": "确认这些短段是否只是标签化拆句；公式接口或真实短判断无需强行合并。",
                })
                break

    return {
        "schema": "aigc-style-rhythm-audit/v1",
        "status": "review" if findings else "pass",
        "document": str(path.resolve()),
        "mode": mode,
        "summary": {
            "segments_total": len(segments),
            "segments_analyzed": len(selected),
            "paragraphs_analyzed": analyzed_paragraphs,
            "findings": len(findings),
        },
        "findings": findings,
        "disclaimer": "Heuristic paragraph-rhythm review only; not an AI-authorship or naturalness judgment.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--mode", choices=("auto", "prose", "mixed"), default="auto")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if not args.document.is_file():
        parser.error(f"document not found: {args.document}")
    report = audit(args.document, args.mode)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["summary"]
        print(
            f"STYLE RHYTHM {report['status'].upper()} mode={report['mode']} "
            f"segments={summary['segments_analyzed']}/{summary['segments_total']} "
            f"paragraphs={summary['paragraphs_analyzed']} findings={summary['findings']}"
        )
        for item in report["findings"]:
            evidence = json.dumps(item["evidence"], ensure_ascii=False)
            print(
                f"[REVIEW] {item['code']} line={item['line']} section={item['section']}: "
                f"{evidence} | {item['suggestion']}"
            )
        print("NOTE: findings locate repetitive rhythm; they do not identify AI authorship.")
    return 2 if report["status"] == "review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
