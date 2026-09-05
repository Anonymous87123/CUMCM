#!/usr/bin/env python
"""Stream Codex JSONL chat logs into an auditable Chinese style analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - exercised only on minimal Python installs
    plt = None


SCRIPT_VERSION = "1.0.0"
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
HAN_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
MARKDOWN_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+")
MARKDOWN_BULLET_RE = re.compile(r"(?m)^\s*[-*+]\s+")
MARKDOWN_QUOTE_RE = re.compile(r"(?m)^\s*>\s?")
MARKDOWN_TABLE_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")
URL_RE = re.compile(r"https?://\S+", re.I)

REDACTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.I | re.S)),
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("CONNECTION_STRING", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s`]+", re.I)),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.I)),
    ("PASSWORD", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*[^\s,;]+")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d[- ]?\d{4}[- ]?\d{4}(?!\d)")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("HOME_PATH", re.compile(r"(?i)(?:[A-Z]:\\Users\\[^\\\s`]+|/home/[^/\s`]+|/Users/[^/\s`]+)(?:[\\/][^\s`]+)*")),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_lexicon() -> dict[str, Any]:
    path = Path(__file__).with_name("style_analysis_lexicon.json")
    return json.loads(path.read_text(encoding="utf-8"))


def path_hash(value: str) -> str:
    return hashlib.blake2b(value.encode("utf-8"), digest_size=10).hexdigest()


def normalise_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def redact_sensitive(text: str) -> str:
    for label, pattern in REDACTION_RULES:
        text = pattern.sub(f"[{label}]", text)
    return text


def prose_view(text: str) -> str:
    text = CODE_BLOCK_RE.sub("\n", text)
    # Inline Markdown often carries a file, symbol, or command name that is essential
    # to a readable evidence excerpt. Keep its text while dropping only the backticks.
    text = INLINE_CODE_RE.sub(lambda match: match.group(0)[1:-1], text)
    text = URL_RE.sub("[URL]", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def has_chinese(text: str) -> bool:
    return bool(HAN_RE.search(text))


def extract_content(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "output_text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def extract_input_text(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") in {"input_text", "output_text"} and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def is_context_only_user_message(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped.startswith(("<environment_context>", "<permissions", "<collaboration_mode>", "<skills_instructions>", "<plugins_instructions>"))


def classify_task(text: str, lexicon: dict[str, Any]) -> tuple[str, list[str], dict[str, int]]:
    lower = text.lower()
    scores: dict[str, int] = {}
    for label, terms in lexicon["task_rules"].items():
        score = sum(1 for term in terms if term.lower() in lower)
        if score:
            scores[label] = score
    if not scores:
        return "unknown", ["unknown"], {}
    priority = {name: index for index, name in enumerate(lexicon["task_priority"])}
    labels = sorted(scores, key=lambda item: (-scores[item], priority.get(item, 99), item))
    return labels[0], labels, scores


def build_snapshot(root: Path, limit_files: int | None = None) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*.jsonl") if path.is_file())
    if limit_files is not None:
        files = files[:limit_files]
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            {
                "path": str(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "path_hash": path_hash(str(path)),
                "status": "pending",
            }
        )
    return {"version": 1, "created_at": utc_now(), "root": str(root), "files": entries}


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def iter_snapshot_lines(entry: dict[str, Any]) -> Iterable[tuple[int, str]]:
    """Yield only complete UTF-8 lines inside the snapshot's original byte length."""
    remaining = int(entry["size"])
    line_number = 0
    buffer = b""
    with Path(entry["path"]).open("rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                line_number += 1
                yield line_number, raw.decode("utf-8", errors="replace")
    # The byte limit is fixed by the snapshot. A final complete JSON record need not end in a newline;
    # malformed partial data is still rejected and counted by the JSON parser above the iterator.
    if buffer:
        line_number += 1
        yield line_number, buffer.decode("utf-8", errors="replace")


def parse_timestamp(value: Any, timezone_name: str) -> tuple[str, str, str]:
    if not isinstance(value, str):
        return "unknown", "unknown", "unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        local = parsed.astimezone(ZoneInfo(timezone_name))
        return local.date().isoformat(), f"{local:%G}-W{local:%V}", f"{local:%Y-%m}"
    except ValueError:
        return "unknown", "unknown", "unknown"


def collect_records(snapshot: dict[str, Any], lexicon: dict[str, Any] | None = None, timezone_name: str = "Asia/Shanghai") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lexicon = lexicon or load_lexicon()
    records: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "files_total": len(snapshot["files"]),
        "files_chat": 0,
        "files_excluded_no_session_meta": 0,
        "json_parse_errors": 0,
        "unknown_schema_records": 0,
        "assistant_chinese_messages": 0,
        "assistant_non_chinese_messages": 0,
        "files_changed_since_snapshot": 0,
    }
    for entry in snapshot["files"]:
        path = Path(entry["path"])
        if not path.exists():
            entry["status"] = "missing"
            continue
        try:
            stat = path.stat()
            entry["changed_since_snapshot"] = stat.st_size != entry["size"] or stat.st_mtime_ns != entry["mtime_ns"]
            if entry["changed_since_snapshot"]:
                audit["files_changed_since_snapshot"] += 1
        except OSError:
            entry["status"] = "unreadable"
            continue

        metadata = {"session_id": None, "originator": "unknown", "source": "unknown", "model_provider": "unknown", "model": "unknown", "personality": "unknown", "collaboration": "unknown"}
        last_task = ("unknown", ["unknown"], {})
        candidates: list[dict[str, Any]] = []
        saw_session_meta = False
        for line_number, line in iter_snapshot_lines(entry):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                audit["json_parse_errors"] += 1
                continue
            event_type = event.get("type")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if event_type == "session_meta":
                saw_session_meta = True
                metadata.update(
                    {
                        "session_id": payload.get("id") or metadata["session_id"],
                        "originator": payload.get("originator") or metadata["originator"],
                        "source": payload.get("source") or metadata["source"],
                        "model_provider": payload.get("model_provider") or metadata["model_provider"],
                    }
                )
            elif event_type == "turn_context":
                metadata.update(
                    {
                        "model": payload.get("model") or metadata["model"],
                        "personality": payload.get("personality") or metadata["personality"],
                        "collaboration": (payload.get("collaboration_mode") or {}).get("kind", metadata["collaboration"]),
                    }
                )
            elif event_type == "response_item" and payload.get("type") == "message":
                role = payload.get("role")
                if role == "user":
                    user_text = extract_input_text(payload)
                    if not is_context_only_user_message(user_text):
                        last_task = classify_task(user_text, lexicon)
                elif role == "assistant":
                    text = extract_content(payload)
                    if not text:
                        continue
                    if not has_chinese(text):
                        audit["assistant_non_chinese_messages"] += 1
                        continue
                    date, week, month = parse_timestamp(event.get("timestamp"), timezone_name)
                    candidates.append(
                        {
                            "record_id": path_hash(f"{entry['path']}:{line_number}"),
                            "session_hash": path_hash(str(metadata["session_id"] or entry["path"])),
                            "date": date,
                            "week": week,
                            "month": month,
                            "model": str(metadata["model"]),
                            "personality": str(metadata["personality"]),
                            "originator": str(metadata["originator"]),
                            "source": str(metadata["source"]),
                            "model_provider": str(metadata["model_provider"]),
                            "collaboration": str(metadata["collaboration"]),
                            "phase": str(payload.get("phase") or "unspecified"),
                            "task_primary": last_task[0],
                            "task_labels": last_task[1],
                            "task_scores": last_task[2],
                            "raw_text": text,
                            "prose": prose_view(text),
                        }
                    )
            elif event_type not in {"event_msg", "world_state", "response_item", "session_meta", "turn_context"}:
                audit["unknown_schema_records"] += 1

        if not saw_session_meta:
            entry["status"] = "excluded_no_session_meta"
            audit["files_excluded_no_session_meta"] += 1
            continue
        entry["status"] = "included_chat"
        entry["assistant_messages"] = len(candidates)
        audit["files_chat"] += 1
        records.extend(candidates)
        audit["assistant_chinese_messages"] += len(candidates)
    return records, audit


def text_features(record: dict[str, Any], lexicon: dict[str, Any]) -> dict[str, Any]:
    raw = record["raw_text"]
    prose = record["prose"]
    sentences = [part.strip() for part in SENTENCE_RE.findall(prose) if HAN_RE.search(part)]
    features: dict[str, Any] = {
        "raw_chars": len(raw),
        "prose_chars": len(prose),
        "han_chars": len(HAN_RE.findall(prose)),
        "paragraphs": len([line for line in prose.splitlines() if line.strip()]),
        "sentences": len(sentences),
        "has_heading": bool(MARKDOWN_HEADING_RE.search(raw)),
        "has_bullet": bool(MARKDOWN_BULLET_RE.search(raw)),
        "has_quote": bool(MARKDOWN_QUOTE_RE.search(raw)),
        "has_table": bool(MARKDOWN_TABLE_RE.search(raw)),
        "has_code": "```" in raw,
        "has_inline_code": "`" in raw,
        "has_link": bool(URL_RE.search(raw)),
        "colon": raw.count("：") + raw.count(":"),
        "semicolon": raw.count("；") + raw.count(";"),
        "comma": raw.count("，") + raw.count(","),
        "period": raw.count("。") + raw.count("."),
        "question": raw.count("？") + raw.count("?"),
        "exclamation": raw.count("！") + raw.count("!"),
        "ellipsis": raw.count("…"),
        "parenthesis": raw.count("（") + raw.count("(") + raw.count("）") + raw.count(")"),
        "sentence_start": sentences[0][:12] if sentences else "",
        "sentence_end": re.sub(r"[。！？!?\s]+$", "", sentences[-1])[-12:] if sentences else "",
    }
    for label, terms in lexicon["feature_groups"].items():
        features[f"feature_{label}"] = any(term in prose for term in terms)
    for label, pattern in lexicon["patterns"].items():
        features[f"pattern_{label}"] = bool(re.search(pattern, prose, re.S))
    return features


def valid_ngram(value: str, stop_chars: set[str]) -> bool:
    return len(value) >= 2 and not all(char in stop_chars for char in value)


def trim_counter(counter: Counter[str], maximum: int = 150_000) -> None:
    if len(counter) <= maximum:
        return
    cutoff = 2
    retained = {key: count for key, count in counter.items() if count >= cutoff}
    if len(retained) > maximum:
        retained = dict(sorted(retained.items(), key=lambda item: (-item[1], item[0]))[:maximum])
    counter.clear()
    counter.update(retained)


def collect_ngrams(records: list[dict[str, Any]], lexicon: dict[str, Any]) -> tuple[Counter[str], Counter[str], dict[str, Counter[str]]]:
    occurrences: Counter[str] = Counter()
    documents: Counter[str] = Counter()
    by_model: dict[str, Counter[str]] = defaultdict(Counter)
    stop_chars = set(lexicon["ngram_stop_chars"])
    for index, record in enumerate(records, start=1):
        seen: set[str] = set()
        for run in HAN_RUN_RE.findall(record["prose"]):
            capped = run[:600]
            for width in (2, 3, 4):
                for start in range(max(0, len(capped) - width + 1)):
                    gram = capped[start : start + width]
                    if valid_ngram(gram, stop_chars):
                        occurrences[gram] += 1
                        seen.add(gram)
        for gram in seen:
            documents[gram] += 1
            by_model[record["model"]][gram] += 1
        if index % 500 == 0:
            trim_counter(occurrences)
            trim_counter(documents)
            for counter in by_model.values():
                trim_counter(counter, 40_000)
    return occurrences, documents, by_model


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if not total:
        return 0.0, 0.0
    z = 1.96
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def group_counts(records: list[dict[str, Any]], feature_names: list[str]) -> list[dict[str, Any]]:
    global_total = len(records)
    global_hits = {feature: sum(bool(record["features"].get(feature)) for record in records) for feature in feature_names}
    dimensions = {"phase": "phase", "model": "model", "personality": "personality", "model_personality": None, "month": "month", "week": "week", "task": "task_primary", "source": "source"}
    rows = []
    for dimension, key in dimensions.items():
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            label = f"{record['model']} | {record['personality']}" if dimension == "model_personality" else str(record[key])
            groups[label].append(record)
        for label, items in groups.items():
            total = len(items)
            for feature in feature_names:
                hits = sum(bool(item["features"].get(feature)) for item in items)
                rate = hits / total if total else 0.0
                global_rate = global_hits[feature] / global_total if global_total else 0.0
                low, high = wilson_interval(hits, total)
                rows.append(
                    {
                        "dimension": dimension,
                        "group": label,
                        "feature": feature.removeprefix("feature_").removeprefix("pattern_"),
                        "feature_type": "pattern" if feature.startswith("pattern_") else "lexicon",
                        "messages": total,
                        "hits": hits,
                        "rate": round(rate, 6),
                        "ci_low": round(low, 6),
                        "ci_high": round(high, 6),
                        "global_rate": round(global_rate, 6),
                        "difference": round(rate - global_rate, 6),
                        "material_difference": total >= 500 and abs(rate - global_rate) >= 0.03,
                    }
                )
    return rows


def task_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = Counter(record["task_primary"] for record in records)
    multi = Counter(label for record in records for label in record["task_labels"])
    return [
        {"task": task, "primary_messages": primary[task], "multi_label_messages": multi[task], "primary_rate": round(primary[task] / len(records), 6)}
        for task in sorted(set(primary) | set(multi))
    ]


def select_examples(records: list[dict[str, Any]], evidence: str, maximum: int = 120) -> list[dict[str, Any]]:
    if evidence == "none":
        return []
    selected: list[dict[str, Any]] = []
    seen = set()
    buckets: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        text = redact_sensitive(record["prose"])
        if 60 <= len(text) <= 240 and text not in seen:
            bucket = (record["model"], record["phase"], record["task_primary"], record["month"])
            score = sum(record["features"].get(name, False) for name in record["features"] if name.startswith(("feature_", "pattern_")))
            record = {**record, "evidence_text": text, "evidence_score": score}
            buckets[bucket].append(record)
    for bucket in sorted(buckets):
        best = max(buckets[bucket], key=lambda item: (item["evidence_score"], item["prose_chars"], item["record_id"]))
        selected.append(best)
        seen.add(best["evidence_text"])
        if len(selected) >= maximum:
            return selected
    remaining = sorted(
        (item for items in buckets.values() for item in items if item["evidence_text"] not in seen),
        key=lambda item: (-item["evidence_score"], -item["prose_chars"], item["record_id"]),
    )
    for item in remaining:
        selected.append(item)
        seen.add(item["evidence_text"])
        if len(selected) >= maximum:
            break
    return selected


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def draw_figures(output: Path, records: list[dict[str, Any]], comparison_rows: list[dict[str, Any]]) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    if plt is None:
        for name in ("phase_length_distribution.svg", "model_personality_heatmap.svg", "monthly_trend.svg", "pattern_comparison.svg"):
            (figures / name).write_text("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='80'><text x='10' y='40'>matplotlib unavailable</text></svg>", encoding="utf-8")
        return
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    def save(name: str) -> None:
        plt.tight_layout()
        plt.savefig(figures / name, format="svg")
        plt.close()

    by_phase: dict[str, list[int]] = defaultdict(list)
    for record in records:
        by_phase[record["phase"]].append(record["features"]["prose_chars"])
    plt.figure(figsize=(8, 4))
    labels = sorted(by_phase)
    plt.bar(labels, [sum(by_phase[label]) / len(by_phase[label]) for label in labels], color="#2f6f9f")
    plt.title("Average prose characters by phase")
    plt.ylabel("characters")
    save("phase_length_distribution.svg")

    model_phase = defaultdict(lambda: [0, 0])
    for record in records:
        key = f"{record['model']} | {record['personality']}"
        model_phase[key][0] += int(record["features"].get("feature_evidence", False))
        model_phase[key][1] += 1
    labels = sorted(model_phase)[:20]
    plt.figure(figsize=(max(8, len(labels) * 0.65), 4))
    plt.bar(labels, [model_phase[label][0] / model_phase[label][1] for label in labels], color="#c45c36")
    plt.xticks(rotation=35, ha="right")
    plt.ylim(0, 1)
    plt.title("Evidence-language coverage by model and personality")
    plt.ylabel("message coverage")
    save("model_personality_heatmap.svg")

    by_month = defaultdict(lambda: [0, 0])
    for record in records:
        if record["month"] != "unknown":
            by_month[record["month"]][0] += int(record["features"].get("feature_first_person", False))
            by_month[record["month"]][1] += 1
    labels = sorted(by_month)
    plt.figure(figsize=(8, 4))
    plt.plot(labels, [by_month[label][0] / by_month[label][1] for label in labels], marker="o", color="#4c956c")
    plt.ylim(0, 1)
    plt.title("Monthly first-person action coverage")
    plt.ylabel("message coverage")
    save("monthly_trend.svg")

    patterns = [row for row in comparison_rows if row["dimension"] == "phase" and row["group"] == "final_answer" and row["feature_type"] == "pattern"]
    plt.figure(figsize=(8, 4))
    labels = [row["feature"] for row in patterns]
    plt.bar(labels, [row["rate"] for row in patterns], color="#8e6c8a")
    plt.ylim(0, 1)
    plt.title("Rhetorical patterns in final answers")
    plt.ylabel("message coverage")
    save("pattern_comparison.svg")


def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int | None = None) -> str:
    rows = rows[:limit] if limit else rows
    if not rows:
        return "无可用数据。"
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def report_text(metrics: dict[str, Any], phrase_rows: list[dict[str, Any]], comparisons: list[dict[str, Any]], tasks: list[dict[str, Any]], examples: list[dict[str, Any]], output: Path) -> str:
    total = metrics["messages"]
    phase_rows = [{"阶段": key, "消息数": value} for key, value in metrics["by_phase"].items()]
    model_rows = [{"模型 | 人格": key, "消息数": value} for key, value in metrics["by_model_personality"].items()]
    top_phrases = [{"短语": row["phrase"], "消息覆盖率": f"{row['document_rate']:.1%}", "出现次数": row["occurrences"]} for row in phrase_rows[:30]]
    material = [row for row in comparisons if row["material_difference"]]
    material_rows = [{"维度": row["dimension"], "分组": row["group"], "特征": row["feature"], "覆盖率": f"{row['rate']:.1%}", "相对总体": f"{row['difference']:+.1%}", "样本": row["messages"]} for row in material[:50]]
    task_rows = [{"任务类别": row["task"], "主标签消息": row["primary_messages"], "占比": f"{row['primary_rate']:.1%}"} for row in tasks]
    example_blocks = []
    for index, example in enumerate(examples, start=1):
        tags = f"{example['date']} | {example['model']} | {example['personality']} | {example['phase']} | {example['task_primary']} | session:{example['session_hash']}"
        example_blocks.append(f"### 证据 {index}\n\n`{tags}`\n\n> {example['evidence_text'].replace(chr(10), ' ')}\n")
    return f"""# GPT/Codex 中文风格深度语料报告

生成时间：{metrics['generated_at']}  
输入快照：`{metrics['snapshot_path']}`  
详细数据目录：`{output}`

## 1. 执行摘要

本报告从 {metrics['files_chat']} 个真实聊天文件中提取了 **{total:,}** 条中文 assistant 正文（共 {metrics['prose_chars']:,} 个去代码正文字符）。与简版报告不同，本次结果同时按模型、人设、时间、消息阶段、来源与任务类型统计，并保留可复现的输入快照、CSV 与 SVG 图表。

观察对象是 Codex 工程代理环境中的 GPT 输出，不是脱离系统提示和任务构成的“裸模型人格”。因此，所有模型差异均只描述本地语料中的可观察差异，不做能力或因果归因。

## 2. 数据审计与隐私处理

| 指标 | 数值 |
|---|---:|
| 扫描 JSONL 文件 | {metrics['files_total']:,} |
| 识别为聊天文件 | {metrics['files_chat']:,} |
| 无 session 元数据而排除 | {metrics['files_excluded_no_session_meta']:,} |
| 中文 assistant 消息 | {total:,} |
| 非中文 assistant 消息 | {metrics['assistant_non_chinese_messages']:,} |
| JSON 解析错误 | {metrics['json_parse_errors']:,} |
| 快照后发生变化的文件 | {metrics['files_changed_since_snapshot']:,} |
| 精确重复正文 | {metrics['duplicate_text_messages']:,} |
| 证据节选数量 | {len(examples):,} |

仅 assistant 的 `output_text` 进入语料。用户、system、developer、reasoning、工具调用与工具输出没有进入统计或证据附录。所有节选均已执行密钥、Token、JWT、私钥、密码、连接串、邮箱、手机号、IP 与用户目录路径脱敏。

## 3. 样本构成

### 消息阶段

{markdown_table(phase_rows, ['阶段', '消息数'])}

### 模型与人格

{markdown_table(model_rows, ['模型 | 人格', '消息数'], 30)}

任务类型是依据最近有效用户任务的中英文规则词典推定，仅保存类别而不保存用户正文；未分类和多标签情况均保留在 `task_classification_summary.csv`。

{markdown_table(task_rows, ['任务类别', '主标签消息', '占比'])}

## 4. 全局语言画像

平均每条去代码正文 {metrics['avg_prose_chars']:.1f} 字符，平均 {metrics['avg_sentences']:.1f} 个句子，汉字占去代码正文的 {metrics['han_ratio']:.1%}。Markdown 格式、标点和句法特征见 `metrics.json`；阶段长度分布见 `figures/phase_length_distribution.svg`。

这批文本的主要味道仍然是工程代理式的“动作 - 状态 - 证据 - 下一步”：中间消息偏短，频繁播报检查和确认；最终答复偏长，更集中使用结论、限制、验证、建议和收尾邀请。`group_comparisons.csv` 给出每个说法的样本量、Wilson 95% 区间和相对总体差值。

## 5. 数据驱动高频短语

以下短语来自去代码正文的连续汉字 2-4 gram，按消息覆盖率排序；它们不是中文分词结果，且已过滤纯功能字串。

{markdown_table(top_phrases, ['短语', '消息覆盖率', '出现次数'])}

完整排行、出现次数、文档覆盖数、模型区分度和搭配数据见 `phrase_rankings.csv`。这部分比人工指定的“我先、下一步、核心、关键”等词表更能显示实际反复出现的短语。

## 6. 修辞结构与功能词簇

脚本分别统计第一/第二人称、完成态、未来承诺、状态限定、建议、邀请、证据、风险约束、实现、结论、保守限定、对比和行动词簇，并用规则识别以下结构：

- `先……再……`：步骤化与过程可预期性。
- `不是……而是……`：根因澄清和对照论证。
- `为了避免/确保……`：风险控制的理由前置。
- `当前/目前/现在……但……`：已有结果与残余缺口并置。
- `结论/核心/关键……验证/测试/结果……`：结论与证据联结。

模型通常不是单纯“爱说某个词”，而是在反复使用一整套工程沟通框架：先安排动作，随后给状态和证据，最后限定边界并提出下一步。证据型词簇、风险型词簇和行动型词簇共同构成了这种可靠但略带工单感的中文。

## 7. 分组差异

只有分组样本至少 500 条且与总体差异至少 3 个百分点的项才被标为“明显差异”。这样可避免小样本模型、人设或月份被过度解释。

{markdown_table(material_rows, ['维度', '分组', '特征', '覆盖率', '相对总体', '样本'], 50)}

阶段长度、模型/人格的证据用语、月度第一人称行动用语、最终答复修辞结构分别对应：

- `figures/phase_length_distribution.svg`
- `figures/model_personality_heatmap.svg`
- `figures/monthly_trend.svg`
- `figures/pattern_comparison.svg`

时间变化必须与模型、人设和任务构成一起理解。某月某个表达升高，可能来自当月任务集中于代码排错或切换到不同人格配置，而不能单独归因为模型语言能力变化。

## 8. 模板化与 AI 痕迹

从精确正文重复、句首/句尾短语和高覆盖 n-gram 可以区分两类重复：一类是工程任务需要的稳定交付模板，例如“确认、验证、下一步”；另一类是可能影响自然度的固定路标，例如反复的“我先”“我已经”“如果你愿意”。

较自然的改写原则是：简单任务省略过程播报；用具体测试或文件事实替换抽象“闭环/落地”；只在确实互斥时使用“不是 A，而是 B”；有明确后续价值时再使用邀请式收尾。保留证据和边界意识，但减少重复的状态词，通常能让文本更像经验丰富的人类工程师。

## 9. 真实脱敏原文证据

以下是从 assistant 正文中分层抽样的真实节选。它们用于展示统计项在原始语言中的实际形态，不代表所有对话，也不包含用户消息或工具输出。

{chr(10).join(example_blocks) if example_blocks else '本次运行未请求证据节选。'}

完整最多 120 条证据见 `evidence_raw_redacted.md` 与 `examples.jsonl`。

## 10. 复现与限制

复现命令、输入路径、脚本版本、快照、运行时间和核心计数均记录在 `run_metadata.json`。同一 `snapshot.json` 重跑会读取相同文件的同一字节范围，避免活动会话追加内容改变结果。

局限包括：任务类型采用可审计但不完美的规则分类；2-4 gram 不等于中文语义分词；工程任务本身会提高“验证、风险、边界、下一步”等词的频率；不同模型、人格和时间段的样本量可能不均衡。报告因此描述本地语料的风格分布，而不是对某个 GPT 版本做普遍性断言。
"""


def run_analysis(root: Path, snapshot_path: Path, output: Path, evidence: str = "raw", timezone_name: str = "Asia/Shanghai", limit_files: int | None = None, workspace_report: Path | None = None) -> dict[str, Any]:
    lexicon = load_lexicon()
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        snapshot = build_snapshot(root, limit_files)
        save_json(snapshot_path, snapshot)
    output.mkdir(parents=True, exist_ok=True)
    records, audit = collect_records(snapshot, lexicon, timezone_name)
    save_json(snapshot_path, snapshot)
    for record in records:
        record["features"] = text_features(record, lexicon)
        record.update(record["features"])
    occurrences, documents, by_model = collect_ngrams(records, lexicon)
    phrase_rows = []
    for phrase, document_count in documents.items():
        if document_count < max(5, len(records) // 5000):
            continue
        model_counts = [counter[phrase] for counter in by_model.values() if counter[phrase]]
        phrase_rows.append(
            {
                "phrase": phrase,
                "occurrences": occurrences[phrase],
                "document_messages": document_count,
                "document_rate": round(document_count / len(records), 8) if records else 0,
                "models_present": len(model_counts),
                "max_model_document_rate": round(max(model_counts) / len(records), 8) if model_counts and records else 0,
            }
        )
    phrase_rows.sort(key=lambda row: (-row["document_messages"], -row["occurrences"], row["phrase"]))
    feature_names = sorted(name for name in records[0]["features"] if name.startswith(("feature_", "pattern_"))) if records else []
    comparisons = group_counts(records, feature_names)
    tasks = task_summary(records)
    examples = select_examples(records, evidence)
    duplicate_text_messages = len(records) - len({normalise_text(record["prose"]) for record in records})
    average = lambda values: sum(values) / len(values) if values else 0.0
    metrics = {
        **audit,
        "generated_at": utc_now(),
        "script_version": SCRIPT_VERSION,
        "snapshot_path": str(snapshot_path),
        "messages": len(records),
        "prose_chars": sum(record["prose_chars"] for record in records),
        "avg_prose_chars": round(average([record["prose_chars"] for record in records]), 3),
        "avg_sentences": round(average([record["sentences"] for record in records]), 3),
        "han_ratio": round(sum(record["han_chars"] for record in records) / max(1, sum(record["prose_chars"] for record in records)), 6),
        "duplicate_text_messages": duplicate_text_messages,
        "by_phase": dict(Counter(record["phase"] for record in records)),
        "by_model_personality": dict(Counter(f"{record['model']} | {record['personality']}" for record in records)),
        "feature_message_coverage": {name: round(sum(bool(record["features"].get(name)) for record in records) / max(1, len(records)), 6) for name in feature_names},
        "format_message_coverage": {name: round(sum(bool(record["features"].get(name)) for record in records) / max(1, len(records)), 6) for name in ["has_heading", "has_bullet", "has_quote", "has_table", "has_code", "has_inline_code", "has_link"]},
        "collocations": {},
    }
    for anchor in ("我先", "下一步"):
        following = Counter()
        anchor_total = 0
        for record in records:
            for match in re.finditer(re.escape(anchor) + r"([\u4e00-\u9fff]{2,4})", record["prose"]):
                following[match.group(1)] += 1
                anchor_total += 1
        metrics["collocations"][anchor] = [{"following": phrase, "count": count, "share": round(count / anchor_total, 6)} for phrase, count in following.most_common(20)]

    manifest_rows = [{key: value for key, value in entry.items() if key != "path"} | {"path": entry["path"]} for entry in snapshot["files"]]
    write_csv(output / "file_manifest.csv", manifest_rows)
    write_csv(output / "phrase_rankings.csv", phrase_rows)
    write_csv(output / "group_comparisons.csv", comparisons)
    write_csv(output / "task_classification_summary.csv", tasks)
    save_json(output / "metrics.json", metrics)
    save_json(output / "run_metadata.json", {"script_version": SCRIPT_VERSION, "generated_at": metrics["generated_at"], "root": str(root), "snapshot": str(snapshot_path), "evidence": evidence, "timezone": timezone_name, "messages": len(records), "audit": audit})
    with (output / "examples.jsonl").open("w", encoding="utf-8") as handle:
        for example in examples:
            public = {key: example[key] for key in ["record_id", "session_hash", "date", "model", "personality", "phase", "task_primary", "evidence_text"]}
            handle.write(json.dumps(public, ensure_ascii=False) + "\n")
    evidence_lines = ["# GPT assistant 原文证据附录（已脱敏）", "", "只包含 assistant 的 output_text；不含用户、工具或系统内容。", ""]
    for index, example in enumerate(examples, start=1):
        evidence_lines.extend([f"## {index}. {example['model']} | {example['personality']} | {example['phase']}", "", f"- 日期：{example['date']}", f"- 任务：{example['task_primary']}", f"- 会话哈希：`{example['session_hash']}`", "", "> " + example["evidence_text"].replace("\n", " "), ""])
    (output / "evidence_raw_redacted.md").write_text("\n".join(evidence_lines), encoding="utf-8")
    draw_figures(output, records, comparisons)
    detailed = report_text(metrics, phrase_rows, comparisons, tasks, examples, output)
    (output / "gpt_chinese_style_report_detailed.md").write_text(detailed, encoding="utf-8")
    if workspace_report:
        workspace_report.write_text(detailed, encoding="utf-8")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Codex JSONL root directory")
    parser.add_argument("--snapshot", type=Path, required=True, help="Create or reuse a deterministic input manifest")
    parser.add_argument("--output", type=Path, required=True, help="Private analysis output directory")
    parser.add_argument("--evidence", choices=("none", "anonymized", "raw"), default="raw")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--limit-files", type=int)
    parser.add_argument("--workspace-report", type=Path, default=Path.cwd() / "gpt_chinese_style_report_detailed.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics = run_analysis(args.root, args.snapshot, args.output, args.evidence, args.timezone, args.limit_files, args.workspace_report)
    print(json.dumps({"messages": metrics["messages"], "files_chat": metrics["files_chat"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
