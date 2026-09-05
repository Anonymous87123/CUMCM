#!/usr/bin/env python3
"""Build a section-bound human-writing retrieval plan for a CUMCM TeX draft.

Public interface:
    python prepare_style_retrieval_plan.py <main.tex> --problem-type A|B|C
        --output <style-retrieval-plan.json> [--limit 4] [--minimum 3]
        [--context-window 1] [--format text|json]

The plan retrieves verified full-text paragraphs from the 59-paper corpus. It
does not rewrite the manuscript and never reads benchmark-reserved passages.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path

from audit_content_density import headings, normalize_tex, visible_prose
from audit_manuscript import QUESTION_TITLE_PATTERN, normalise_question_id, read_tex_tree
from query_style_patterns import (
    ACTION_RULES,
    FULLTEXT_INDEX,
    HOLDOUT_RESERVATIONS,
    SECTION_RULES,
    _fulltext_payload,
    load_fulltext_records,
    load_holdout_record_ids,
    select_fulltext_records,
)


SCHEMA = "mcm-style-retrieval-plan/v1"
GENERATOR_PATH = Path(__file__).resolve()
RETRIEVAL_ENGINE_PATH = Path(__file__).with_name("query_style_patterns.py").resolve()
PRIMARY_SCORE_TOLERANCE = 2
STYLE_PORTFOLIO_SCORE_TOLERANCE = 8
RETRIEVAL_POOL_MULTIPLIER = 5
SKIP_TITLES = re.compile(r"参考文献|附录|代码|完整默认参数")
# A heading such as “问题一模型建立与求解” is a writable model section,
# not a container. Only a bare question label suppresses parent handling.
QUESTION_PARENT = re.compile(
    r"^(?:问题\s*[0-9一二三四五六七八九十]+|第\s*[0-9一二三四五六七八九十]+\s*问)$"
)
TASK_TITLE_PATTERN = re.compile(
    r"(?:任务|分问题|分问)\s*[（(]?\s*(?P<task>[一二三四五六七八九十百]+|\d+)\s*[）)]?",
    re.I,
)
QUESTION_LABEL_PATTERN = re.compile(
    r"\\label\{(?:mcm[-_:])?q(?P<question>\d+)[-_:](?P<state>start|end)\}",
    re.I,
)
HEADING_COMMAND_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\s*\{[^{}]*\}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def heading_roles(title: str) -> list[str]:
    compact = re.sub(r"\s+", "", title)
    if SKIP_TITLES.search(compact):
        return []
    if "问题重述" in compact or compact == "重述":
        return ["restatement"]
    if "问题分析" in compact or compact == "总体分析":
        return ["analysis"]
    if "模型假设" in compact or compact == "假设":
        return ["assumptions"]
    if "符号" in compact or "变量说明" in compact:
        return ["symbols"]
    if any(token in compact for token in ("灵敏度", "敏感性")):
        return ["sensitivity"]
    if any(token in compact for token in ("检验", "验证", "稳健", "误差", "复算")):
        return ["validation"]
    if any(token in compact for token in ("评价", "改进", "局限", "可信度", "边界", "适用范围")):
        return ["evaluation"]
    has_model = any(token in compact for token in ("模型建立", "模型构建", "方程", "约束"))
    has_solve = any(token in compact for token in ("求解", "算法", "计算", "标定", "搜索", "仿真"))
    has_result = any(token in compact for token in ("结果", "对照", "讨论", "解释", "结论", "建议"))
    if has_model and has_solve:
        return ["model", "solve"]
    if has_solve and has_result:
        return ["solve", "result"]
    if has_solve:
        return ["solve"]
    if has_result:
        return ["result"]
    if has_model:
        return ["model"]
    if compact.endswith("分析"):
        return ["analysis"]
    return []


def local_actions(text: str) -> list[str]:
    return [
        action for action, cues in ACTION_RULES.items()
        if any(cue in text for cue in cues)
    ]


def model_vocabulary(records: list[dict[str, object]]) -> list[str]:
    names = {
        str(name).strip()
        for record in records
        for name in record.get("models", [])
        if str(name).strip()
    }
    return sorted(
        names,
        key=lambda value: (-len(re.sub(r"\s+", "", value)), value.casefold()),
    )


def local_model(text: str, vocabulary: list[str]) -> str | None:
    lowered = re.sub(r"\s+", "", text).casefold()
    for name in vocabulary:
        compact = re.sub(r"\s+", "", name).casefold()
        if len(compact) < 3:
            continue
        if compact in lowered:
            return name
    return None


def query_tokens(role: str, title: str, text: str, actions: list[str]) -> list[str]:
    tokens = list(actions)
    for cue in SECTION_RULES[role]:
        if cue in text and cue not in tokens:
            tokens.append(cue)
    for token in re.split(r"[、，,：:（）()\s]+", title):
        if len(token) >= 2 and token not in tokens:
            tokens.append(token)
    return tokens[:10]


def abstract_target(raw: str) -> tuple[str, str] | None:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", raw, re.S)
    if not match:
        return None
    return "摘要", visible_prose(match.group(1)).strip()


def question_id_from_title(title: str) -> str | None:
    match = QUESTION_TITLE_PATTERN.search(title) or TASK_TITLE_PATTERN.search(title)
    if not match:
        return None
    raw_id = next(group for group in match.groups() if group is not None)
    return normalise_question_id(raw_id)


def _label_question_before(raw: str, position: int) -> str | None:
    active: str | None = None
    for match in QUESTION_LABEL_PATTERN.finditer(raw, 0, position):
        question_id = str(int(match.group("question")))
        if match.group("state").casefold() == "start":
            active = question_id
        elif active == question_id:
            active = None
    return active


def _near_heading_start_label(raw: str, content_start: int) -> str | None:
    # Coverage labels normally appear immediately after a heading.  Stop before
    # looking deep into the section so a later nested question cannot claim its
    # parent heading.
    prefix = raw[content_start:content_start + 320]
    match = QUESTION_LABEL_PATTERN.search(prefix)
    if not match or match.group("state").casefold() != "start":
        return None
    before = prefix[:match.start()]
    if visible_prose(before).strip():
        return None
    return str(int(match.group("question")))


def section_target_records(raw: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", raw, re.S)
    if abstract_match:
        raw_scope = abstract_match.group(0)
        output.append({
            "title": "摘要",
            "role": "abstract",
            "visible_prose": visible_prose(abstract_match.group(1)).strip(),
            "tex_source": raw_scope,
            "line": raw.count("\n", 0, abstract_match.start()) + 1,
            "question_id": None,
        })
    parent_roles: list[str] = []
    current_question: str | None = None
    for item in headings(raw):
        label_question = _label_question_before(raw, item.start)
        heading_command = HEADING_COMMAND_PATTERN.match(raw, item.start)
        content_start = heading_command.end() if heading_command else item.start
        near_label_question = _near_heading_start_label(raw, content_start)
        heading_question = near_label_question or question_id_from_title(item.title) or label_question
        is_question_parent = bool(QUESTION_PARENT.match(re.sub(r"\s+", "", item.title)))
        if item.level == "section":
            current_question = heading_question
            parent_roles = [] if is_question_parent else heading_roles(item.title)
        elif heading_question is not None:
            current_question = heading_question
        if is_question_parent:
            continue
        roles = heading_roles(item.title)
        if not roles and item.level != "section":
            roles = parent_roles
        if not roles:
            continue
        tex_source = raw[item.start:item.end]
        scope = visible_prose(tex_source).strip()
        line = raw.count("\n", 0, item.start) + 1
        for role in roles:
            output.append({
                "title": item.title,
                "role": role,
                "visible_prose": scope,
                "tex_source": tex_source,
                "line": line,
                "question_id": current_question,
            })
    return output


def section_targets(raw: str) -> list[tuple[str, str, str, int, str | None]]:
    return [
        (
            str(item["title"]),
            str(item["role"]),
            str(item["visible_prose"]),
            int(item["line"]),
            str(item["question_id"]) if item["question_id"] is not None else None,
        )
        for item in section_target_records(raw)
    ]


def retrieve(
    records_high: list[dict[str, object]],
    records_usable: list[dict[str, object]],
    problem_type: str,
    role: str,
    tokens: list[str],
    model: str | None,
    minimum: int,
    limit: int,
    context_window: int,
) -> tuple[list[dict[str, object]], str]:
    pool_limit = min(40, max(limit * RETRIEVAL_POOL_MULTIPLIER, minimum, limit))
    selected = select_fulltext_records(
        records_high, problem_type, None, role, tokens, model, pool_limit
    )
    quality = "high"
    if len(selected) < minimum and model:
        selected = select_fulltext_records(
            records_high, problem_type, None, role, tokens, None, pool_limit
        )
    if len(selected) < minimum:
        selected = select_fulltext_records(
            records_usable, problem_type, None, role, tokens, model, pool_limit
        )
        quality = "usable-fallback"
    if len(selected) < minimum and model:
        selected = select_fulltext_records(
            records_usable, problem_type, None, role, tokens, None, pool_limit
        )
    selected = select_style_portfolio(selected, minimum, limit)
    if quality == "high" and _portfolio_relevance_key(selected, minimum)[0] > 0:
        expanded = select_fulltext_records(
            records_usable, problem_type, None, role, tokens, model, pool_limit
        )
        if len(expanded) < minimum and model:
            expanded = select_fulltext_records(
                records_usable, problem_type, None, role, tokens, None, pool_limit
            )
        expanded = select_style_portfolio(expanded, minimum, limit)
        if _portfolio_relevance_key(expanded, minimum) < _portfolio_relevance_key(selected, minimum):
            selected = expanded
            quality = "usable-relevance-fallback"
    payload = [
        _fulltext_payload(score, record, records_usable, context_window)
        for score, record in selected[:limit]
    ]
    for rank, anchor in enumerate(payload, 1):
        anchor["style_portfolio_rank"] = rank
        anchor["cadence_band"] = _cadence_band(anchor)
        anchor["ending_action"] = _ending_action(anchor)
    return payload, quality


def _action_sequence_key(anchor: dict[str, object]) -> tuple[str, ...]:
    raw = anchor.get("action_sequence")
    return tuple(str(item) for item in raw) if isinstance(raw, list) else tuple()


def _style_value(anchor: dict[str, object], key: str) -> str:
    value = str(anchor.get(key) or "").strip()
    return value if value else "unspecified"


def _cadence_band(anchor: dict[str, object]) -> str:
    try:
        sentences = int(anchor.get("sentence_count") or 0)
    except (TypeError, ValueError):
        sentences = 0
    try:
        han_chars = int(anchor.get("han_chars") or 0)
    except (TypeError, ValueError):
        han_chars = 0
    sentence_band = "one-sentence" if sentences <= 1 else "two-sentence" if sentences == 2 else "multi-sentence"
    length_band = "short" if han_chars < 50 else "medium" if han_chars <= 100 else "long"
    return f"{sentence_band}:{length_band}"


def _ending_action(anchor: dict[str, object]) -> str:
    sequence = _action_sequence_key(anchor)
    return sequence[-1] if sequence else "unspecified"


def _style_shape(anchor: dict[str, object]) -> dict[str, object]:
    return {
        "action_sequence": list(_action_sequence_key(anchor)),
        "opening_family": _style_value(anchor, "opening_family"),
        "closing_family": _style_value(anchor, "closing_family"),
        "ending_action": _ending_action(anchor),
        "cadence_band": _cadence_band(anchor),
        "paper": _style_value(anchor, "paper"),
        "formula_nearby": bool(anchor.get("formula_nearby")),
        "visual_nearby": bool(anchor.get("visual_nearby")),
    }


def _novelty_gain(anchor: dict[str, object], selected: list[tuple[int, dict[str, object]]]) -> int:
    shapes = [_style_shape(item) for _score, item in selected]
    shape = _style_shape(anchor)
    gain = 0
    if shape["paper"] not in {item["paper"] for item in shapes}:
        gain += 5
    if tuple(shape["action_sequence"]) not in {tuple(item["action_sequence"]) for item in shapes}:
        gain += 5
    if shape["opening_family"] != "unspecified" and shape["opening_family"] not in {item["opening_family"] for item in shapes}:
        gain += 3
    if shape["closing_family"] != "unspecified" and shape["closing_family"] not in {item["closing_family"] for item in shapes}:
        gain += 3
    if shape["ending_action"] != "unspecified" and shape["ending_action"] not in {item["ending_action"] for item in shapes}:
        gain += 4
    if shape["cadence_band"] not in {item["cadence_band"] for item in shapes}:
        gain += 2
    if shape["formula_nearby"] not in {item["formula_nearby"] for item in shapes}:
        gain += 1
    if shape["visual_nearby"] not in {item["visual_nearby"] for item in shapes}:
        gain += 1
    return gain


def select_style_portfolio(
    ranked: list[tuple[int, dict[str, object]]],
    minimum: int,
    limit: int,
    score_tolerance: int = STYLE_PORTFOLIO_SCORE_TOLERANCE,
) -> list[tuple[int, dict[str, object]]]:
    """Keep relevance first, then expose genuinely different human motions."""
    if len(ranked) <= limit:
        return list(ranked)
    chosen = [ranked[0]]
    remaining = list(ranked[1:])
    best_score = ranked[0][0]
    while remaining and len(chosen) < limit:
        eligible = [item for item in remaining if item[0] >= best_score - score_tolerance]
        if not eligible and len(chosen) >= minimum:
            break
        pool = eligible if eligible else remaining
        selected = max(
            pool,
            key=lambda item: (
                _novelty_gain(item[1], chosen),
                item[0],
                -ranked.index(item),
            ),
        )
        chosen.append(selected)
        remaining.remove(selected)
    while remaining and len(chosen) < minimum:
        chosen.append(remaining.pop(0))
    return chosen[:limit]


def _portfolio_relevance_key(
    ranked: list[tuple[int, dict[str, object]]], minimum: int,
) -> tuple[int, int, int, int]:
    if not ranked:
        return (minimum, 10**9, 10**9, 0)
    scores = [score for score, _record in ranked]
    best_score = max(scores)
    deltas = [best_score - score for score in scores]
    return (
        sum(delta > STYLE_PORTFOLIO_SCORE_TOLERANCE for delta in deltas),
        max(0, minimum - len(ranked)),
        max(deltas, default=0),
        -len(ranked),
    )


def _portfolio_summary(anchors: list[dict[str, object]]) -> dict[str, object]:
    scores = [int(item.get("score", 0)) for item in anchors]
    best_score = max(scores, default=0)
    deltas = [best_score - score for score in scores]
    return {
        "selection": "relevance-bounded-style-portfolio",
        "score_tolerance": STYLE_PORTFOLIO_SCORE_TOLERANCE,
        "anchors": len(anchors),
        "best_score": best_score,
        "score_deltas": deltas,
        "outside_score_tolerance": sum(delta > STYLE_PORTFOLIO_SCORE_TOLERANCE for delta in deltas),
        "distinct_papers": len({_style_value(item, "paper") for item in anchors}),
        "distinct_action_sequences": len({_action_sequence_key(item) for item in anchors}),
        "distinct_opening_families": len({_style_value(item, "opening_family") for item in anchors if _style_value(item, "opening_family") != "unspecified"}),
        "distinct_closing_families": len({_style_value(item, "closing_family") for item in anchors if _style_value(item, "closing_family") != "unspecified"}),
        "distinct_ending_actions": len({_ending_action(item) for item in anchors if _ending_action(item) != "unspecified"}),
        "distinct_cadence_bands": len({_cadence_band(item) for item in anchors}),
        "shapes": [{"id": item.get("id"), **_style_shape(item)} for item in anchors],
    }


def assign_primary_anchors(
    targets: list[dict[str, object]],
    score_tolerance: int = PRIMARY_SCORE_TOLERANCE,
) -> dict[str, object]:
    anchor_usage: Counter[str] = Counter()
    sequence_usage: Counter[tuple[str, ...]] = Counter()
    opening_usage: Counter[str] = Counter()
    closing_usage: Counter[str] = Counter()
    ending_action_usage: Counter[str] = Counter()
    cadence_usage: Counter[str] = Counter()
    paper_usage: Counter[str] = Counter()
    previous_anchor: str | None = None
    previous_sequence: tuple[str, ...] | None = None
    previous_opening: str | None = None
    previous_closing: str | None = None
    previous_ending_action: str | None = None
    previous_cadence: str | None = None
    previous_paper: str | None = None
    for target in targets:
        anchors = [item for item in target.get("anchors", []) if isinstance(item, dict)]
        if not anchors:
            continue
        best_score = max(int(item.get("score", 0)) for item in anchors)
        eligible = [
            (index, item) for index, item in enumerate(anchors)
            if int(item.get("score", 0)) >= best_score - score_tolerance
        ]
        index, selected = min(
            eligible,
            key=lambda pair: (
                anchor_usage[str(pair[1].get("id", ""))],
                str(pair[1].get("id", "")) == previous_anchor,
                sequence_usage[_action_sequence_key(pair[1])],
                _action_sequence_key(pair[1]) == previous_sequence,
                opening_usage[_style_value(pair[1], "opening_family")],
                _style_value(pair[1], "opening_family") == previous_opening,
                closing_usage[_style_value(pair[1], "closing_family")],
                _style_value(pair[1], "closing_family") == previous_closing,
                ending_action_usage[_ending_action(pair[1])],
                _ending_action(pair[1]) == previous_ending_action,
                cadence_usage[_cadence_band(pair[1])],
                _cadence_band(pair[1]) == previous_cadence,
                paper_usage[_style_value(pair[1], "paper")],
                _style_value(pair[1], "paper") == previous_paper,
                -int(pair[1].get("score", 0)),
                pair[0],
            ),
        )
        selected_id = str(selected.get("id", ""))
        selected_sequence = _action_sequence_key(selected)
        selected_opening = _style_value(selected, "opening_family")
        selected_closing = _style_value(selected, "closing_family")
        selected_ending_action = _ending_action(selected)
        selected_cadence = _cadence_band(selected)
        selected_paper = _style_value(selected, "paper")
        target["primary_anchor_id"] = selected_id
        target["primary_anchor_selection"] = {
            "policy": "relevance-bounded-low-reuse",
            "score_tolerance": score_tolerance,
            "best_score": best_score,
            "selected_score": int(selected.get("score", 0)),
            "selected_original_rank": index + 1,
            "eligible_anchor_ids": [str(item.get("id", "")) for _, item in eligible],
            "prior_anchor_use_count": anchor_usage[selected_id],
            "prior_sequence_use_count": sequence_usage[selected_sequence],
            "same_as_previous_primary": selected_id == previous_anchor,
            "same_sequence_as_previous_primary": selected_sequence == previous_sequence,
            "prior_opening_use_count": opening_usage[selected_opening],
            "prior_closing_use_count": closing_usage[selected_closing],
            "prior_ending_action_use_count": ending_action_usage[selected_ending_action],
            "prior_cadence_use_count": cadence_usage[selected_cadence],
            "prior_paper_use_count": paper_usage[selected_paper],
            "same_opening_as_previous_primary": selected_opening == previous_opening,
            "same_closing_as_previous_primary": selected_closing == previous_closing,
            "same_ending_action_as_previous_primary": selected_ending_action == previous_ending_action,
            "same_cadence_as_previous_primary": selected_cadence == previous_cadence,
            "same_paper_as_previous_primary": selected_paper == previous_paper,
            "rule": (
                "Choose only among already retrieved anchors within the score tolerance; reduce reuse when "
                "relevance permits, but never import a less relevant paragraph merely for variety."
            ),
        }
        anchor_usage[selected_id] += 1
        sequence_usage[selected_sequence] += 1
        opening_usage[selected_opening] += 1
        closing_usage[selected_closing] += 1
        ending_action_usage[selected_ending_action] += 1
        cadence_usage[selected_cadence] += 1
        paper_usage[selected_paper] += 1
        previous_anchor = selected_id
        previous_sequence = selected_sequence
        previous_opening = selected_opening
        previous_closing = selected_closing
        previous_ending_action = selected_ending_action
        previous_cadence = selected_cadence
        previous_paper = selected_paper
    return {
        "score_tolerance": score_tolerance,
        "distinct_primary_anchors": len(anchor_usage),
        "maximum_primary_anchor_reuse": max(anchor_usage.values(), default=0),
        "distinct_primary_action_sequences": len(sequence_usage),
        "maximum_primary_sequence_reuse": max(sequence_usage.values(), default=0),
        "distinct_primary_opening_families": len(opening_usage),
        "maximum_primary_opening_reuse": max(opening_usage.values(), default=0),
        "distinct_primary_closing_families": len(closing_usage),
        "maximum_primary_closing_reuse": max(closing_usage.values(), default=0),
        "distinct_primary_ending_actions": len(ending_action_usage),
        "maximum_primary_ending_action_reuse": max(ending_action_usage.values(), default=0),
        "distinct_primary_cadence_bands": len(cadence_usage),
        "maximum_primary_cadence_reuse": max(cadence_usage.values(), default=0),
        "distinct_primary_papers": len(paper_usage),
        "maximum_primary_paper_reuse": max(paper_usage.values(), default=0),
    }


def build_plan(
    main_tex: Path,
    problem_type: str,
    minimum: int,
    limit: int,
    context_window: int,
) -> dict[str, object]:
    main_tex = main_tex.resolve()
    raw = normalize_tex(read_tex_tree(main_tex))
    high = load_fulltext_records("high")
    usable = load_fulltext_records("usable")
    vocabulary = model_vocabulary(usable)
    reserved = load_holdout_record_ids()
    targets: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    for index, (title, role, scope, line, question_id) in enumerate(section_targets(raw), 1):
        actions = local_actions(scope)
        model = local_model(scope, vocabulary)
        tokens = query_tokens(role, title, scope, actions)
        anchors, quality = retrieve(
            high, usable, problem_type, role, tokens, model,
            minimum, limit, context_window,
        )
        leaked = [item["id"] for item in anchors if item["id"] in reserved]
        if leaked:
            findings.append({
                "severity": "error", "code": "RESERVED_HOLDOUT_LEAK",
                "target": f"T{index:02d}", "record_ids": leaked,
            })
        if len(anchors) < minimum:
            findings.append({
                "severity": "error", "code": "STYLE_ANCHOR_COVERAGE_THIN",
                "target": f"T{index:02d}", "title": title,
                "role": role, "found": len(anchors), "minimum": minimum,
            })
        anchor_ids = [str(item.get("id", "")) for item in anchors]
        if len(anchor_ids) != len(set(anchor_ids)):
            findings.append({
                "severity": "error", "code": "STYLE_ANCHOR_DUPLICATE",
                "target": f"T{index:02d}", "record_ids": anchor_ids,
            })
        distinct_papers = {str(item.get("paper", "")) for item in anchors if item.get("paper")}
        if len(distinct_papers) < 2:
            findings.append({
                "severity": "error", "code": "STYLE_ANCHOR_PAPER_DIVERSITY_THIN",
                "target": f"T{index:02d}", "distinct_papers": sorted(distinct_papers),
                "minimum": 2,
            })
        portfolio_summary = _portfolio_summary(anchors)
        if portfolio_summary["outside_score_tolerance"]:
            findings.append({
                "severity": "warning", "code": "STYLE_PORTFOLIO_RELEVANCE_FALLBACK",
                "target": f"T{index:02d}",
                "count": portfolio_summary["outside_score_tolerance"],
                "reason": "minimum anchor coverage required a lower-scoring human passage",
            })
        targets.append({
            "id": f"T{index:02d}",
            "title": title,
            "line": line,
            "role": role,
            "question_id": question_id,
            "actions": actions,
            "model": model,
            "query_tokens": tokens,
            "retrieval_quality": quality,
            "anchor_count": len(anchors),
            "anchors": anchors,
            "style_portfolio_summary": portfolio_summary,
            "usage_rule": (
                "Read the paragraph and adjacent context for functional wording, evidence order, "
                "formula/figure interfaces, and stopping point. Do not copy sentences or import facts."
            ),
        })
    if not targets:
        findings.append({"severity": "error", "code": "NO_WRITABLE_SECTION_TARGETS"})
    primary_summary = assign_primary_anchors(targets)
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "problem_type": problem_type,
        "source": {
            "path": str(main_tex),
            "sha256": sha256_file(main_tex),
            "tex_tree_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        },
        "generator": {
            "plan_builder": {"path": str(GENERATOR_PATH), "sha256": sha256_file(GENERATOR_PATH)},
            "retrieval_engine": {
                "path": str(RETRIEVAL_ENGINE_PATH),
                "sha256": sha256_file(RETRIEVAL_ENGINE_PATH),
            },
        },
        "corpus": {
            "fulltext_index": str(FULLTEXT_INDEX),
            "fulltext_index_sha256": sha256_file(FULLTEXT_INDEX),
            "holdout_reservations": str(HOLDOUT_RESERVATIONS),
            "holdout_reservations_sha256": sha256_file(HOLDOUT_RESERVATIONS),
            "high_records_available": len(high),
            "usable_records_available": len(usable),
            "reserved_records_excluded": len(reserved),
        },
        "policy": {
            "minimum_anchors_per_target": minimum,
            "maximum_anchors_per_target": limit,
            "minimum_distinct_papers_per_target": 2,
            "context_window": context_window,
            "primary_anchor_selection": "relevance-bounded-low-reuse",
            "primary_anchor_score_tolerance": PRIMARY_SCORE_TOLERANCE,
            "supporting_anchor_selection": "relevance-bounded-style-portfolio",
            "supporting_anchor_score_tolerance": STYLE_PORTFOLIO_SCORE_TOLERANCE,
            "supporting_anchor_dimensions": [
                "paper", "action_sequence", "opening_family", "closing_family", "ending_action",
                "cadence_band", "formula_nearby", "visual_nearby",
            ],
            "copying_forbidden": True,
            "facts_must_come_from_current_problem": True,
        },
        "primary_anchor_summary": primary_summary,
        "targets": targets,
        "errors": errors,
        "warnings": sum(item["severity"] == "warning" for item in findings),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--problem-type", choices=("A", "B", "C"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum", type=int, default=3)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--context-window", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if not 1 <= args.minimum <= args.limit <= 8:
        parser.error("require 1 <= --minimum <= --limit <= 8")
    report = build_plan(
        args.main_tex, args.problem_type, args.minimum, args.limit, args.context_window
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"STYLE RETRIEVAL PLAN {report['status'].upper()} "
            f"targets={len(report['targets'])} errors={report['errors']} "
            f"output={args.output.resolve()}"
        )
        for target in report["targets"]:
            print(
                f"[{target['id']}] line={target['line']} role={target['role']} "
                f"question={target['question_id']} anchors={target['anchor_count']} title={target['title']}"
            )
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
