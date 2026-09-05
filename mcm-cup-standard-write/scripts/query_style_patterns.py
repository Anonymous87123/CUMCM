#!/usr/bin/env python3
"""Query the 59-paper CUMCM style evidence without loading the full corpus."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
STYLE_INDEX = REFERENCES / "style-pass2-all-papers.md"
HUMAN_STYLE = REFERENCES / "human-style.md"
PAPER_CARDS = REFERENCES / "paper-cards"
FULLTEXT_INDEX = REFERENCES / "fulltext-style-index.jsonl"
HOLDOUT_RESERVATIONS = REFERENCES / "style-benchmark-holdout.json"


@dataclass(frozen=True)
class StyleRecord:
    year: int
    problem_type: str
    paper: str
    evidence_id: str
    reasoning_trace: str
    rejected_cliche: str
    trigger_tags: tuple[str, ...]
    action_tags: tuple[str, ...]
    index_line: int
    evidence_line: int | None
    paper_card: str
    language_functions: str | None
    rhythm_interface: str | None
    stopping_point: str | None
    language_notes: tuple[str, ...]


TRIGGER_RULES = {
    "data": ("数据", "附件", "字段", "样本", "曲线", "图", "表", "读数", "残差", "相关"),
    "equation": ("方程", "公式", "守恒", "几何", "单调", "对称", "根", "曲率", "边界", "证明"),
    "consequence": ("现实", "业务", "成本", "风险", "生存", "倒退", "负担", "不可接受", "超限", "硬约束"),
    "trial": ("试算", "比较", "对照", "失败", "不满足", "落选", "异常", "扰动", "回查"),
    "computation": ("规模", "枚举", "搜索", "步长", "预算", "状态", "变量", "网格", "递推", "遍历"),
    "interface": ("前问", "后问", "沿用", "复用", "输入", "输出", "接回", "冻结", "开放", "替换"),
    "direct-relation": ("题面", "直接", "已知", "只剩", "唯一", "性质"),
}

ACTION_RULES = {
    "model-selection": ("选型", "选择", "决定", "裁决", "换法", "换路", "算法切换"),
    "model-reduction": ("降阶", "降维", "压成", "缩到", "简化", "缩域"),
    "interface-reuse": ("前问", "后问", "沿用", "复用", "接回", "冻结", "开放", "替换输入"),
    "local-repair": ("局部", "只修", "修正", "残差", "失败区", "异常", "新增关系"),
    "coarse-to-fine": ("粗", "细", "二分", "加密", "缩步", "精搜", "三分"),
    "constraint-translation": ("约束", "下界", "上界", "变量域", "可行", "动作状态", "分段条件"),
    "state-progression": ("状态", "递推", "逐期", "轮末", "下一轮", "停止", "终止"),
    "candidate-comparison": ("候选", "同指标", "同口径", "比较", "复评", "舍弃", "落选"),
    "result-explanation": ("解释", "突增", "反转", "趋势", "机制", "幅度", "优先级", "读图"),
    "validation": ("检验", "验证", "扰动", "误差", "残差", "回查", "反例", "收敛"),
    "bounded-claim": ("有限", "上界", "下界", "候选", "接近", "不能", "不外推", "范围内"),
}

# The short index intentionally uses varied wording.  These additions preserve
# recall for seven records whose action is clear from the verified paper card
# but whose compressed trace does not contain one of the generic tag words.
PAPER_ACTION_OVERRIDES = {
    "A028": ("model-reduction", "constraint-translation"),
    "A0127": ("model-reduction", "candidate-comparison"),
    "A0165": ("model-reduction", "candidate-comparison", "interface-reuse"),
    "B175": ("constraint-translation", "state-progression"),
    "B030": ("model-reduction", "state-progression"),
    "C109": ("interface-reuse", "state-progression"),
    "C227": ("interface-reuse", "state-progression"),
}

SECTION_ALIASES = {
    "any": "any",
    "abstract": "abstract",
    "摘要": "abstract",
    "restatement": "restatement",
    "重述": "restatement",
    "analysis": "analysis",
    "问题分析": "analysis",
    "assumptions": "assumptions",
    "假设": "assumptions",
    "symbols": "symbols",
    "符号": "symbols",
    "model": "model",
    "建模": "model",
    "solve": "solve",
    "求解": "solve",
    "result": "result",
    "结果": "result",
    "validation": "validation",
    "检验": "validation",
    "sensitivity": "sensitivity",
    "灵敏度": "sensitivity",
    "evaluation": "evaluation",
    "评价": "evaluation",
    "appendix": "appendix",
    "附录": "appendix",
}

SECTION_RULES = {
    "abstract": ("结果", "数值", "输出", "完整链", "分问", "对照"),
    "restatement": ("目标", "已知", "约束", "问题", "输入", "输出"),
    "analysis": ("不能", "缺口", "不足", "失败", "决定", "裁决", "为何", "触发", "信息"),
    "assumptions": ("近似", "假设", "上界", "下界", "共线", "边界", "现实", "信息不可见"),
    "symbols": ("命名", "变量", "状态", "字段", "索引", "参数", "对象"),
    "model": ("方程", "守恒", "几何", "约束", "递推", "损失", "指标", "函数", "变量域"),
    "solve": ("搜索", "遍历", "二分", "步长", "算法", "动态规划", "遗传", "贪心", "状态", "枚举"),
    "result": ("结果", "解释", "异常", "突增", "反转", "趋势", "读图", "误差", "幅度"),
    "validation": ("检验", "验证", "回查", "扰动", "误差", "残差", "收敛", "复评", "反例"),
    "sensitivity": ("扰动", "参数", "敏感", "范围", "幅度", "优先级", "切换", "固定"),
    "evaluation": ("不足", "不能", "有限", "代价", "落选", "边界", "负担", "不外推"),
    "appendix": ("代码", "状态", "实现", "步长", "循环", "输出", "生成", "记录"),
}

FULLTEXT_SECTION_MAP = {
    "any": "any",
    "abstract": "abstract",
    "restatement": "restatement",
    "analysis": "analysis",
    "assumptions": "assumption",
    "symbols": "notation",
    "model": "model",
    "solve": "solve",
    "result": "result",
    "validation": "validation",
    "sensitivity": "sensitivity",
    "evaluation": "evaluation",
    "appendix": "appendix",
}


def _find_line(lines: list[str], needle: str) -> int | None:
    for number, line in enumerate(lines, 1):
        if needle in line:
            return number
    return None


def _evidence_block(human_text: str, evidence_id: str) -> str:
    """Return one dedicated evidence block when the corpus has one."""
    match = re.search(
        rf"^####\s+{re.escape(evidence_id)}\s*$\n(?P<body>.*?)(?=^####\s+EV-|^###\s+|\Z)",
        human_text,
        re.M | re.S,
    )
    return match.group("body") if match else ""


def _block_field(block: str, label: str) -> str | None:
    match = re.search(rf"^-\s*{re.escape(label)}：\s*(.+)$", block, re.M)
    return match.group(1).strip() if match else None


STYLE_SECTION_PRIORITY = (
    r"Human-style evidence",
    r"Human style rules extracted",
    r"Human-writing actions",
    r"人类作者文风与段落组织样本",
    r"人类惯用词及段落骨架",
    r"人类文风与判断轨迹",
    r"人类文风与高分机制",
    r"可调用的人类写作动作",
    r"可调用的模型与写作动作",
    r"可迁移写作动作",
    r"更接近本篇的人类惯用承接",
    r"功能性惯用句",
    r"可迁移句式(?:与去 AI 味)?",
)


def _card_sections(card_text: str) -> list[tuple[str, str]]:
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", card_text, re.M))
    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(card_text)
        sections.append((heading.group(1).strip(), card_text[heading.end():end].strip()))
    return sections


def _language_notes(card: Path, block: str) -> tuple[str, ...]:
    """Expose a bounded set of verified language notes for every paper."""
    dedicated = [
        value for label in ("词语功能", "节奏与接口", "停止位置")
        if (value := _block_field(block, label))
    ]
    if dedicated:
        return tuple(dedicated)

    card_text = card.read_text(encoding="utf-8")
    sections = _card_sections(card_text)
    selected: list[str] = []
    for pattern in STYLE_SECTION_PRIORITY:
        for heading, body in sections:
            if not re.fullmatch(pattern, heading, re.I):
                continue
            for line in body.splitlines():
                cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                if len(cleaned) < 12:
                    continue
                selected.append(cleaned)
                if len(selected) == 5:
                    return tuple(selected)
        if selected:
            break
    return tuple(selected)


def _tags(text: str, rules: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(name for name, words in rules.items() if any(word in text for word in words))


def load_records() -> list[StyleRecord]:
    index_lines = STYLE_INDEX.read_text(encoding="utf-8").splitlines()
    human_text = HUMAN_STYLE.read_text(encoding="utf-8")
    human_lines = human_text.splitlines()
    row_pattern = re.compile(
        r"^\|\s*(\d{4})\s+([ABC]\d+)\s*/\s*(EV-\d{8}-[ABC]\d+-STYLE-01)\s*"
        r"\|\s*(.*?)\s*\|\s*(.*?)\s*\|$"
    )
    records: list[StyleRecord] = []
    for line_number, line in enumerate(index_lines, 1):
        match = row_pattern.match(line)
        if not match:
            continue
        year_text, paper, evidence_id, trace, rejected = match.groups()
        combined = f"{trace} {rejected}"
        card = PAPER_CARDS / f"{year_text}_{paper}.md"
        action_tags = list(_tags(combined, ACTION_RULES))
        for tag in PAPER_ACTION_OVERRIDES.get(paper, ()):
            if tag not in action_tags:
                action_tags.append(tag)
        block = _evidence_block(human_text, evidence_id)
        records.append(
            StyleRecord(
                year=int(year_text),
                problem_type=paper[0],
                paper=paper,
                evidence_id=evidence_id,
                reasoning_trace=trace,
                rejected_cliche=rejected,
                trigger_tags=_tags(combined, TRIGGER_RULES),
                action_tags=tuple(action_tags),
                index_line=line_number,
                evidence_line=_find_line(human_lines, evidence_id),
                paper_card=str(card),
                language_functions=_block_field(block, "词语功能"),
                rhythm_interface=_block_field(block, "节奏与接口"),
                stopping_point=_block_field(block, "停止位置"),
                language_notes=_language_notes(card, block),
            )
        )
    return records


def _query_tokens(action: list[str], query: str) -> list[str]:
    text = " ".join(action + [query])
    return [token for token in re.split(r"[\s,，;/]+", text.strip()) if token]


def _score(record: StyleRecord, section: str, tokens: list[str]) -> int:
    haystack = " ".join(
        [
            record.reasoning_trace,
            record.rejected_cliche,
            *record.trigger_tags,
            *record.action_tags,
        ]
    ).lower()
    score = 0
    for token in tokens:
        lowered = token.lower()
        if lowered in record.trigger_tags or lowered in record.action_tags:
            score += 8
        elif lowered in haystack:
            score += 4
    if section != "any":
        for word in SECTION_RULES[section]:
            if word in haystack:
                score += 2
    score += min(record.reasoning_trace.count("->"), 4)
    return score


def select_records(
    records: list[StyleRecord],
    problem_type: str | None,
    paper: str | None,
    section: str,
    tokens: list[str],
    limit: int,
) -> list[tuple[int, StyleRecord]]:
    candidates = records
    if problem_type:
        candidates = [record for record in candidates if record.problem_type == problem_type]
    if paper:
        candidates = [record for record in candidates if record.paper == paper]
    ranked = [(_score(record, section, tokens), record) for record in candidates]
    ranked.sort(key=lambda item: (-item[0], item[1].year, item[1].paper))
    if tokens or section != "any":
        positive = [item for item in ranked if item[0] > 0]
        if positive:
            ranked = positive
    return ranked[:limit]


def _record_payload(score: int, record: StyleRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["score"] = score
    payload["source_type"] = "card"
    payload["index_source"] = f"{STYLE_INDEX}:{record.index_line}"
    payload["evidence_source"] = (
        f"{HUMAN_STYLE}:{record.evidence_line}" if record.evidence_line else None
    )
    return payload


def load_holdout_record_ids() -> set[str]:
    """Load passage ids reserved for sealed style-benchmark evaluation."""
    if not HOLDOUT_RESERVATIONS.is_file():
        return set()
    payload = json.loads(HOLDOUT_RESERVATIONS.read_text(encoding="utf-8"))
    if payload.get("schema") not in {
        "cumcm-style-holdout-reservations/v1",
        "cumcm-style-holdout-reservations/v2",
    }:
        raise ValueError(f"unsupported holdout reservation schema: {HOLDOUT_RESERVATIONS}")
    records = payload.get("reserved_record_ids", [])
    if not isinstance(records, list) or not all(isinstance(item, str) and item for item in records):
        raise ValueError(f"invalid reserved_record_ids: {HOLDOUT_RESERVATIONS}")
    return set(records)


def load_fulltext_records(
    quality: str,
    include_reserved_holdout: bool = False,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    reserved_ids = set() if include_reserved_holdout else load_holdout_record_ids()
    with FULLTEXT_INDEX.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record["id"] in reserved_ids:
                continue
            if quality == "high" and record["quality"] != "high":
                continue
            if quality == "high" and not record.get("retrieval_eligible", False):
                continue
            if quality == "usable" and record["quality"] == "low":
                continue
            if record["han_chars"] < 30:
                continue
            record["index_line"] = line_number
            records.append(record)
    return records


def _fulltext_score(record: dict[str, object], tokens: list[str], model: str | None) -> int:
    text = str(record["text"])
    lowered = text.lower()
    actions = {str(action).lower() for action in record.get("actions", [])}
    models = {str(name).lower() for name in record.get("models", [])}
    score = min(len(record.get("action_sequence", [])), 5)
    for token in tokens:
        lowered_token = token.lower()
        if lowered_token in actions:
            score += 10
        elif lowered_token in models:
            score += 9
        elif lowered_token in lowered:
            score += 5 + min(lowered.count(lowered_token), 3)
    if model:
        lowered_model = model.lower()
        if lowered_model in models:
            score += 16
        elif lowered_model in lowered:
            score += 8
        else:
            return -1
    if record.get("formula_nearby"):
        score += 1
    if record.get("visual_nearby"):
        score += 1
    return score


def select_fulltext_records(
    records: list[dict[str, object]],
    problem_type: str | None,
    paper: str | None,
    section: str,
    tokens: list[str],
    model: str | None,
    limit: int,
) -> list[tuple[int, dict[str, object]]]:
    expected_section = FULLTEXT_SECTION_MAP[section]
    candidates = [
        record for record in records
        if (not problem_type or record["problem_type"] == problem_type)
        and (not paper or record["paper"] == paper)
        and (expected_section == "any" or record["section"] == expected_section)
    ]
    ranked = [(_fulltext_score(record, tokens, model), record) for record in candidates]
    ranked = [item for item in ranked if item[0] >= 0]
    ranked.sort(key=lambda item: (-item[0], item[1]["year"], item[1]["paper"], item[1]["page_start"]))
    if tokens or model:
        positives = [item for item in ranked if item[0] > 0]
        if positives:
            ranked = positives
    selected: list[tuple[int, dict[str, object]]] = []
    paper_counts: dict[str, int] = {}
    for item in ranked:
        paper_name = str(item[1]["paper"])
        if paper_counts.get(paper_name, 0) >= 2 and len({str(row[1]["paper"]) for row in ranked}) > 2:
            continue
        selected.append(item)
        paper_counts[paper_name] = paper_counts.get(paper_name, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def _fulltext_payload(
    score: int,
    record: dict[str, object],
    all_records: list[dict[str, object]],
    context_window: int,
) -> dict[str, object]:
    payload = dict(record)
    payload["score"] = score
    payload["source_type"] = "fulltext"
    payload["index_source"] = f"{FULLTEXT_INDEX}:{record['index_line']}"
    if context_window:
        position = next(index for index, item in enumerate(all_records) if item["id"] == record["id"])
        previous = []
        following = []
        for offset in range(1, context_window + 1):
            if position - offset >= 0:
                item = all_records[position - offset]
                if item["paper"] == record["paper"]:
                    previous.insert(0, {"source": item["source"], "section": item["section"], "text": item["text"]})
            if position + offset < len(all_records):
                item = all_records[position + offset]
                if item["paper"] == record["paper"]:
                    following.append({"source": item["source"], "section": item["section"], "text": item["text"]})
        payload["previous_context"] = previous
        payload["next_context"] = following
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query local human-writing anchors from the verified 59-paper CUMCM corpus."
    )
    parser.add_argument("--problem-type", choices=("A", "B", "C"))
    parser.add_argument("--paper", help="Exact paper id, for example A053.")
    parser.add_argument(
        "--section",
        default="any",
        help="any/abstract/analysis/model/solve/result/validation/sensitivity/evaluation, or Chinese aliases.",
    )
    parser.add_argument(
        "--action",
        action="append",
        default=[],
        help="Repeatable action/tag/keyword, for example --action local-repair --action 残差.",
    )
    parser.add_argument("--query", default="", help="Additional free-text keywords.")
    parser.add_argument("--model", help="Model or algorithm name used to filter full-text paragraphs.")
    parser.add_argument(
        "--source", choices=("card", "fulltext", "both"), default="card",
        help="card keeps the compact 59-paper anchors; fulltext returns original reconstructed prose.",
    )
    parser.add_argument(
        "--quality", choices=("high", "usable"), default="high",
        help="OCR quality admitted by full-text retrieval.",
    )
    parser.add_argument(
        "--context-window", type=int, choices=(0, 1, 2), default=1,
        help="Number of neighboring full-text paragraphs to include on each side.",
    )
    parser.add_argument(
        "--include-reserved-holdout",
        action="store_true",
        help="Read benchmark-heldout records. Use only to run the frozen style benchmark, never for drafting.",
    )
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    section = SECTION_ALIASES.get(args.section)
    if section is None:
        parser.error(f"unknown section: {args.section}")
    if args.limit < 1 or args.limit > 20:
        parser.error("--limit must be between 1 and 20")

    tokens = _query_tokens(args.action, args.query)
    paper = args.paper.upper() if args.paper else None
    payload: list[dict[str, object]] = []
    if args.source in {"card", "both"}:
        records = load_records()
        selected = select_records(records, args.problem_type, paper, section, tokens, args.limit)
        payload.extend(_record_payload(score, record) for score, record in selected)
    if args.source in {"fulltext", "both"}:
        fulltext_records = load_fulltext_records(
            args.quality,
            include_reserved_holdout=args.include_reserved_holdout,
        )
        selected_fulltext = select_fulltext_records(
            fulltext_records, args.problem_type, paper, section, tokens, args.model, args.limit
        )
        payload.extend(
            _fulltext_payload(score, record, fulltext_records, args.context_window)
            for score, record in selected_fulltext
        )

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not payload:
        print("No matching style anchor found.")
        return 1
    for item in payload:
        if item["source_type"] == "fulltext":
            print(
                f"[{item['paper']}] score={item['score']} section={item['section']} "
                f"pages={item['page_start']}-{item['page_end']} quality={item['quality']}"
            )
            print(f"  actions: {', '.join(item['actions']) or '-'}")
            print(f"  sequence: {' -> '.join(item['action_sequence']) or '-'}")
            print(f"  models: {', '.join(item['models']) or '-'}")
            for context in item.get("previous_context", []):
                print(f"  previous ({context['section']}, {context['source']}): {context['text']}")
            print(f"  paragraph: {item['text']}")
            for context in item.get("next_context", []):
                print(f"  next ({context['section']}, {context['source']}): {context['text']}")
            print(f"  index: {item['index_source']}")
            continue
        print(f"[{item['paper']}] score={item['score']} evidence={item['evidence_id']}")
        print(f"  trigger: {', '.join(item['trigger_tags']) or '-'}")
        print(f"  actions: {', '.join(item['action_tags']) or '-'}")
        print(f"  trace: {item['reasoning_trace']}")
        if item["language_functions"]:
            print(f"  wording: {item['language_functions']}")
        if item["rhythm_interface"]:
            print(f"  rhythm: {item['rhythm_interface']}")
        if item["stopping_point"]:
            print(f"  stop: {item['stopping_point']}")
        if item["language_notes"] and not item["language_functions"]:
            print("  language notes:")
            for note in item["language_notes"]:
                print(f"    - {note}")
        print(f"  reject: {item['rejected_cliche']}")
        print(f"  card: {item['paper_card']}")
        print(f"  index: {item['index_source']}")
        print(f"  evidence: {item['evidence_source'] or 'not located'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
