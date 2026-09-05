#!/usr/bin/env python
"""Analyze the redacted full-style corpus produced by build_full_style_corpus.py."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


HAN_RE = re.compile(r"[\u4e00-\u9fff]")
SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
FEATURE_TERMS = {
    "first_person": ("我先", "我会", "我已经", "我已", "我来", "我把"),
    "second_person": ("你可以", "你需要", "你的", "如果你"),
    "completion": ("已经", "已完成", "已修复", "已更新", "已处理", "完成了"),
    "future_commitment": ("我会", "接下来", "下一步", "随后", "稍后"),
    "state_scope": ("当前", "目前", "现在", "现有", "本次"),
    "recommendation": ("建议", "推荐", "优先", "可以直接", "应当"),
    "invitation": ("如果你愿意", "如果需要", "我可以继续"),
    "evidence": ("确认", "验证", "检查", "测试", "结果", "证据", "显示"),
    "risk_constraint": ("避免", "确保", "风险", "边界", "约束", "回归", "兼容", "局限"),
    "implementation": ("实现", "修改", "代码", "文件", "接口", "配置", "构建", "模型"),
    "conclusion": ("结论", "核心", "关键", "本质上", "摘要", "综上"),
    "hedging": ("可能", "应该", "看起来", "大概率", "暂时", "不一定"),
    "contrast": ("但是", "不过", "但", "而是", "相反"),
    "action": ("直接", "处理", "修复", "补充", "调整", "运行", "定位", "建立"),
    "academic": ("本文", "样本", "口径", "数据", "分析", "图表", "变量", "方法"),
}
PATTERNS = {
    "stepwise": re.compile(r"先.{0,80}再", re.S),
    "contrastive": re.compile(r"不是.{0,80}而是", re.S),
    "risk_purpose": re.compile(r"为了(?:避免|确保).{0,100}", re.S),
    "state_gap": re.compile(r"(?:当前|目前|现在).{0,100}(?:但|不过|但是).{0,100}", re.S),
    "condition_action": re.compile(r"(?:如果|若).{0,100}(?:就|应当|需要|可以|先)", re.S),
    "conclusion_evidence": re.compile(r"(?:结论|核心|关键).{0,100}(?:验证|测试|结果|数据|证据)", re.S),
}
PHRASE_CANDIDATES = (
    "我先", "我会", "我已经", "下一步", "接下来", "当前", "目前", "已经", "直接", "确认", "验证", "核心", "关键", "结论", "建议", "如果你愿意",
    "不是", "而是", "因此", "同时", "为了", "本文", "本报告", "样本", "口径", "数据", "模型", "分析", "图表", "方法", "稳健", "局限", "如果", "只有",
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def classify_markdown_path(path_value: str) -> str:
    normalized = path_value.replace("/", "\\").lower()
    if "node_modules\\" in normalized or "program files\\" in normalized or "microsoft vs code\\" in normalized:
        return "third_party_dependency"
    if "\\.codex\\skills\\" in normalized or "\\.codex\\plugins\\" in normalized or "\\.codex\\.tmp\\" in normalized:
        return "codex_skill"
    if any(part in normalized for part in ("\\draft", "\\report", "\\analysis", "\\docs", "\\notes", "\\manuscript", "\\paper")):
        return "local_report"
    if "readme" in normalized or "changelog" in normalized:
        return "project_documentation"
    return "other_markdown"


def measure_text(text: str) -> dict[str, Any]:
    sentences = [value.strip() for value in SENTENCE_RE.findall(text) if value.strip()]
    metrics: dict[str, Any] = {
        "chars": len(text),
        "han_chars": len(HAN_RE.findall(text)),
        "sentences": len(sentences),
        "paragraphs": max(1, len([part for part in text.split("\n\n") if part.strip()])),
        "colon": text.count("：") + text.count(":"),
        "semicolon": text.count("；") + text.count(";"),
        "comma": text.count("，") + text.count(","),
        "period": text.count("。") + text.count("."),
        "question": text.count("？") + text.count("?"),
        "exclamation": text.count("！") + text.count("!"),
        "sentence_start": sentences[0][:12] if sentences else "",
        "sentence_end": re.sub(r"[。！？!?\s]+$", "", sentences[-1])[-12:] if sentences else "",
    }
    for name, terms in FEATURE_TERMS.items():
        metrics[f"feature_{name}"] = any(term in text for term in terms)
    for name, pattern in PATTERNS.items():
        metrics[f"pattern_{name}"] = bool(pattern.search(text))
    return metrics


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def aggregate_groups(rows: list[dict[str, Any]], group_key: str) -> list[dict[str, Any]]:
    feature_names = [f"feature_{name}" for name in FEATURE_TERMS] + [f"pattern_{name}" for name in PATTERNS]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    output = []
    for group, values in groups.items():
        total = len(values)
        for feature in feature_names:
            successes = sum(bool(value["metrics"].get(feature)) for value in values)
            low, high = wilson_interval(successes, total)
            output.append({"group": group, "feature": feature.removeprefix("feature_").removeprefix("pattern_"), "feature_type": "pattern" if feature.startswith("pattern_") else "lexicon", "records": total, "hits": successes, "rate": round(successes / total, 6), "ci_low": round(low, 6), "ci_high": round(high, 6)})
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def update_accumulator(acc: dict[str, Any], metrics: dict[str, Any]) -> None:
    acc["records"] += 1
    for name in ("chars", "han_chars", "sentences", "paragraphs", "colon", "semicolon", "comma", "period", "question", "exclamation"):
        acc[name] += int(metrics[name])
    for name, value in metrics.items():
        if name.startswith(("feature_", "pattern_")) and value:
            acc[name] += 1


def make_accumulator() -> dict[str, Any]:
    return defaultdict(int)


def accumulator_rows(accumulators: dict[str, dict[str, Any]], dimension: str) -> list[dict[str, Any]]:
    rows = []
    feature_names = [f"feature_{name}" for name in FEATURE_TERMS] + [f"pattern_{name}" for name in PATTERNS]
    for group, acc in accumulators.items():
        records = acc["records"]
        rows.append({"dimension": dimension, "group": group, "feature": "__length__", "feature_type": "numeric", "records": records, "hits": "", "rate": round(acc["chars"] / records, 6) if records else 0, "ci_low": "", "ci_high": "", "han_per_record": round(acc["han_chars"] / records, 6) if records else 0, "sentences_per_record": round(acc["sentences"] / records, 6) if records else 0})
        for feature in feature_names:
            hits = acc[feature]
            low, high = wilson_interval(hits, records)
            rows.append({"dimension": dimension, "group": group, "feature": feature.removeprefix("feature_").removeprefix("pattern_"), "feature_type": "pattern" if feature.startswith("pattern_") else "lexicon", "records": records, "hits": hits, "rate": round(hits / records, 6) if records else 0, "ci_low": round(low, 6), "ci_high": round(high, 6), "han_per_record": "", "sentences_per_record": ""})
    return rows


def run(corpus_dir: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    chat_accumulators: dict[str, dict[str, Any]] = defaultdict(make_accumulator)
    writing_accumulators: dict[str, dict[str, Any]] = defaultdict(make_accumulator)
    writing_cn_accumulators: dict[str, dict[str, Any]] = defaultdict(make_accumulator)
    phrase_counts: dict[str, Counter[str]] = {"chat": Counter(), "writing": Counter(), "writing_chinese": Counter()}
    chat_starts: Counter[str] = Counter()
    writing_starts: Counter[str] = Counter()
    chat_total = 0
    for record in iter_jsonl(corpus_dir / "chat_messages.jsonl"):
        metrics = measure_text(record["text"])
        phase_group = f"phase:{record['phase']}"
        model_group = f"model:{record['model']} | {record['personality']}"
        update_accumulator(chat_accumulators[phase_group], metrics)
        update_accumulator(chat_accumulators[model_group], metrics)
        chat_total += 1
        for phrase in PHRASE_CANDIDATES:
            if phrase in record["text"]:
                phrase_counts["chat"][phrase] += 1
        if metrics["sentence_start"]:
            chat_starts[metrics["sentence_start"]] += 1

    manifest = {row["path"]: row for row in csv.DictReader((corpus_dir / "markdown_manifest.csv").open("r", encoding="utf-8-sig"))}
    document_accumulators: dict[str, dict[str, Any]] = defaultdict(make_accumulator)
    doc_metadata: dict[str, dict[str, str]] = {}
    writing_total = 0
    writing_chinese_total = 0
    for record in iter_jsonl(corpus_dir / "md_paragraphs.jsonl"):
        path = record["path"]
        metadata = manifest.get(path, {})
        if metadata.get("status") != "readable":
            continue
        metrics = measure_text(record["text"])
        doc_type = classify_markdown_path(path)
        update_accumulator(writing_accumulators[f"source:{record['source_label']}"], metrics)
        update_accumulator(writing_accumulators[f"type:{doc_type}"], metrics)
        update_accumulator(document_accumulators[path], metrics)
        doc_metadata[path] = {"source_label": record["source_label"], "doc_type": doc_type, "sha256": metadata.get("sha256", ""), "duplicate_of": metadata.get("duplicate_of", ""), "headings": metadata.get("headings", ""), "manifest_prose_chars": metadata.get("prose_chars", "")}
        writing_total += 1
        for phrase in PHRASE_CANDIDATES:
            if phrase in record["text"]:
                phrase_counts["writing"][phrase] += 1
        if HAN_RE.search(record["text"]):
            update_accumulator(writing_cn_accumulators[f"source:{record['source_label']}"], metrics)
            update_accumulator(writing_cn_accumulators[f"type:{doc_type}"], metrics)
            writing_chinese_total += 1
            for phrase in PHRASE_CANDIDATES:
                if phrase in record["text"]:
                    phrase_counts["writing_chinese"][phrase] += 1
        if metrics["sentence_start"]:
            writing_starts[metrics["sentence_start"]] += 1

    feature_rows = accumulator_rows(chat_accumulators, "chat") + accumulator_rows(writing_accumulators, "writing_all_languages") + accumulator_rows(writing_cn_accumulators, "writing_chinese")
    profiles = []
    for path, acc in document_accumulators.items():
        metadata = doc_metadata[path]
        profiles.append({"path": path, **metadata, "paragraph_records": acc["records"], "chars": acc["chars"], "han_chars": acc["han_chars"], "sentences": acc["sentences"], "avg_paragraph_chars": round(acc["chars"] / max(1, acc["records"]), 4), "first_person_rate": round(acc["feature_first_person"] / max(1, acc["records"]), 6), "academic_rate": round(acc["feature_academic"] / max(1, acc["records"]), 6), "contrastive_rate": round(acc["pattern_contrastive"] / max(1, acc["records"]), 6)})
    profiles.sort(key=lambda row: (-row["han_chars"], row["path"]))
    phrase_rows = []
    for corpus_name, counter in phrase_counts.items():
        denominator = chat_total if corpus_name == "chat" else writing_chinese_total if corpus_name == "writing_chinese" else writing_total
        for phrase, count in counter.most_common():
            phrase_rows.append({"corpus": corpus_name, "phrase": phrase, "paragraph_or_message_hits": count, "rate": round(count / max(1, denominator), 8)})
    start_rows = []
    for corpus_name, counter in (("chat", chat_starts), ("writing", writing_starts)):
        for phrase, count in counter.most_common(200):
            start_rows.append({"corpus": corpus_name, "sentence_start": phrase, "count": count})
    write_csv(output / "feature_by_group.csv", feature_rows)
    write_csv(output / "document_profiles.csv", profiles)
    write_csv(output / "phrase_candidates.csv", phrase_rows)
    write_csv(output / "sentence_starts.csv", start_rows)
    summary = {"chat_records": chat_total, "writing_paragraph_records": writing_total, "writing_chinese_paragraph_records": writing_chinese_total, "document_profiles": len(profiles), "chat_groups": len(chat_accumulators), "writing_groups": len(writing_accumulators), "writing_chinese_groups": len(writing_cn_accumulators), "source_manifest_rows": len(manifest)}
    (output / "analysis_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(run(args.corpus, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
