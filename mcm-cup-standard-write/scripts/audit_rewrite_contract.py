#!/usr/bin/env python3
"""Compare protected TeX semantics before and after one academic rewrite pass."""

from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import json
import re
from pathlib import Path

from audit_manuscript import read_tex_tree


MATH_PATTERN = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?"
    r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}"
    r"|\$\$.*?\$\$|\\\[.*?\\\]|(?<!\$)\$(?!\$)(?:\\.|[^$])*\$",
    re.S,
)
HEADING_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\s*\{[^{}]*\}")
REFERENCE_PATTERN = re.compile(r"\\(?:label|ref|eqref|pageref|cite|parencite)\s*(?:\[[^]]*\])?\s*\{[^{}]*\}")
COMMAND_PATTERN = re.compile(r"\\[A-Za-z@]+\*?")
ENV_PATTERN = re.compile(r"\\(?:begin|end)\s*\{[^{}]+\}")
# Keep alphanumeric identifiers such as Q38 and model_v2 atomic; their digits
# are not standalone numeric claims.
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?%?(?![A-Za-z0-9_])")
UNIT_PATTERN = re.compile(
    r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?\s*)"
    r"(?:米|厘米|毫米|千米|秒|分钟|小时|克|千克|枚|人|次|届|项|元|万元|百分比|百分点)"
    r"|(?<![A-Za-z])(?:mm|cm|km|m|kg|g|mg|s|min|h|Hz|Pa|kPa|MPa|N|kN|W|kW|MW|J|K)(?![A-Za-z])"
    r"|(?:℃|°C)"
)
OBJECTIVE_PATTERN = re.compile(
    r"最小化|最大化|极小化|极大化|minimum|maximum|minimi[sz](?:e|ation)|maximi[sz](?:e|ation)",
    re.I,
)
NEGATION_PATTERN = re.compile(
    r"不得|不能|不可|不会|未能|未|没有|无|非|不|never|without|cannot|can't|not|no",
    re.I,
)
CAUSAL_PATTERN = re.compile(
    r"导致|引起|造成|决定|归因于|源于|because|cause[sd]?|lead(?:s|ing)?\s+to|result(?:s|ing)?\s+in",
    re.I,
)
CLAIM_STRENGTH_PATTERN = re.compile(
    r"可能|大致|倾向于|初步表明|表明|说明|支持|证明|必然|显著|"
    r"may|might|could|suggests?|indicates?|supports?|proves?|necessarily|significant(?:ly)?",
    re.I,
)
PUBLIC_REASONING_CUE_PATTERN = re.compile(
    r"因此|但是|然而|由于|若|如果|只能|仅能|仍然|同时|随后|再将|先把|"
    r"意味着|说明|表明|对应|用于|以便|从而|相比|却|并不|不能|前提下"
)
MODELING_JUDGMENT_PATTERNS = {
    "observation_constraint": re.compile(
        r"题面|题设|观测|数据|条件|约束|现象|问题|需求|限制|边界|假设|记录|情景"
    ),
    "mathematical_change": re.compile(
        r"变量|参数|方程|目标函数|边界条件|数学|关系|指标|状态|维度|离散|连续|函数|总量|波动"
    ),
    "method_choice": re.compile(
        r"构建|建立|采用|选用|使用|引入|选择|求解|拟合|标定|优化|仿真|模型|算法|方法"
    ),
    "result_limit": re.compile(
        r"结果|得到|表明|说明|验证|检验|误差|敏感|稳健|适用|局限|不能|仅|可能|范围|失败|后果"
    ),
}
CONSTRAINT_PHRASES = (
    ("not_equal", re.compile(r"不等于|\\neq|!=", re.I)),
    ("upper_nonstrict", re.compile(r"不超过|至多|不高于|不大于|小于等于", re.I)),
    ("lower_nonstrict", re.compile(r"不低于|不少于|至少|不小于|大于等于", re.I)),
    ("strict_upper", re.compile(r"(?<!不)小于|低于", re.I)),
    ("strict_lower", re.compile(r"(?<!不)大于|高于", re.I)),
    ("equal", re.compile(r"(?<!不)等于|相等", re.I)),
)


def normalize_math(value: str) -> str:
    return re.sub(r"\s+", "", value)


def canonical_constraint_directions(text: str) -> list[str]:
    return [item["value"] for item in semantic_mentions(text, "constraint_directions")]


def _location(text: str, start: int, end: int, value: str, matched: str) -> dict:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = text.count("\n", 0, start) + 1
    column = start - line_start + 1
    context = text[line_start:line_end].strip()
    if len(context) > 240:
        relative_start = start - line_start
        window_start = max(0, relative_start - 100)
        window_end = min(len(context), relative_start + len(matched) + 100)
        context = ("..." if window_start else "") + context[window_start:window_end] + ("..." if window_end < len(context) else "")
    return {
        "value": value,
        "matched": matched,
        "line": line,
        "column": column,
        "context": context,
    }


def semantic_mentions(text: str, key: str) -> list[dict]:
    if key == "constraint_directions":
        hits: list[tuple[int, int, str, str]] = []
        occupied: list[tuple[int, int]] = []
        for name, pattern in CONSTRAINT_PHRASES:
            for match in pattern.finditer(text):
                if any(match.start() < right and match.end() > left for left, right in occupied):
                    continue
                hits.append((match.start(), match.end(), name, match.group(0)))
                occupied.append((match.start(), match.end()))
        return [
            _location(text, start, end, name, matched)
            for start, end, name, matched in sorted(hits)
        ]

    patterns = {
        "negations": NEGATION_PATTERN,
        "causal_markers": CAUSAL_PATTERN,
        "claim_strength": CLAIM_STRENGTH_PATTERN,
    }
    pattern = patterns[key]
    return [
        _location(text, match.start(), match.end(), match.group(0).casefold(), match.group(0))
        for match in pattern.finditer(text)
    ]


def _surplus_examples(records: list[dict], other: list[dict], limit: int = 12) -> list[dict]:
    remaining = collections.Counter(item["value"] for item in other)
    output: list[dict] = []
    for item in records:
        value = item["value"]
        if remaining[value]:
            remaining[value] -= 1
            continue
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _finding_sha256(item: dict) -> str:
    evidence = {
        key: item[key]
        for key in (
            "code", "before_count", "after_count", "before_examples", "after_examples",
            "before_sequence_sha256", "after_sequence_sha256",
            "location_method", "compression_ratio", "removed_cues",
            "before_line_range", "after_line_range",
            "before_categories", "after_categories", "missing_categories",
        )
        if key in item
    }
    encoded = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _augment_semantic_finding(item: dict, key: str, before_text: str, after_text: str) -> None:
    before_mentions = semantic_mentions(before_text, key)
    after_mentions = semantic_mentions(after_text, key)
    before_values = [entry["value"] for entry in before_mentions]
    after_values = [entry["value"] for entry in after_mentions]
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    before_examples: list[dict] = []
    after_examples: list[dict] = []
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        before_local = [
            entry for entry in before_mentions
            if left_start + 1 <= entry["line"] <= left_end
        ]
        after_local = [
            entry for entry in after_mentions
            if right_start + 1 <= entry["line"] <= right_end
        ]
        before_examples.extend(_surplus_examples(before_local, after_local, limit=12))
        after_examples.extend(_surplus_examples(after_local, before_local, limit=12))
        before_examples = before_examples[:12]
        after_examples = after_examples[:12]
    if not before_examples and not after_examples and before_values != after_values:
        before_examples = _surplus_examples(before_mentions, after_mentions)
        after_examples = _surplus_examples(after_mentions, before_mentions)
        item["location_method"] = "global-count-fallback"
    else:
        item["location_method"] = "changed-block-delta"
    item["before_examples"] = before_examples
    item["after_examples"] = after_examples
    item["before_sequence_sha256"] = hashlib.sha256(
        json.dumps(before_values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    item["after_sequence_sha256"] = hashlib.sha256(
        json.dumps(after_values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    item["finding_sha256"] = _finding_sha256(item)


def _content_chars(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def _line_example(lines: list[str], start: int, end: int) -> dict:
    context = " ".join(line.strip() for line in lines[start:end] if line.strip())
    if len(context) > 240:
        context = context[:237] + "..."
    return {"line": start + 1, "column": 1, "context": context}


def argument_compression_findings(before_text: str, after_text: str) -> list[dict]:
    """Locate changed blocks whose shorter form may have dropped public reasoning.

    This is deliberately advisory.  Concision can be an improvement, but a
    large reduction that also removes conditions, transitions or scope markers
    needs a paragraph-level decision rather than an automatic pass.
    """
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    findings: list[dict] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal" or left_start == left_end or right_start == right_end:
            continue
        before_block = "\n".join(before_lines[left_start:left_end])
        after_block = "\n".join(after_lines[right_start:right_end])
        before_count = _content_chars(before_block)
        after_count = _content_chars(after_block)
        if before_count < 100 or before_count - after_count < 20:
            continue
        ratio = after_count / before_count if before_count else 1.0
        if ratio > 0.93:
            continue
        before_cues = [match.group(0) for match in PUBLIC_REASONING_CUE_PATTERN.finditer(before_block)]
        after_cues = [match.group(0) for match in PUBLIC_REASONING_CUE_PATTERN.finditer(after_block)]
        if len(before_cues) < 2:
            continue
        removed_cues = list((collections.Counter(before_cues) - collections.Counter(after_cues)).elements())
        if not removed_cues:
            continue
        item = {
            "severity": "warning",
            "code": "ARGUMENT_COMPRESSION_REVIEW",
            "before_count": before_count,
            "after_count": after_count,
            "compression_ratio": round(ratio, 4),
            "removed_cues": removed_cues[:12],
            "before_line_range": [left_start + 1, left_end],
            "after_line_range": [right_start + 1, right_end],
            "before_examples": [_line_example(before_lines, left_start, left_end)],
            "after_examples": [_line_example(after_lines, right_start, right_end)],
            "before_sequence_sha256": hashlib.sha256(before_block.encode("utf-8")).hexdigest(),
            "after_sequence_sha256": hashlib.sha256(after_block.encode("utf-8")).hexdigest(),
            "location_method": "changed-block-compression",
        }
        item["finding_sha256"] = _finding_sha256(item)
        findings.append(item)
    return findings


def modeling_judgment_chain_findings(
    before_text: str, after_text: str, scene: str,
) -> list[dict]:
    """Locate changed modeling blocks that lose an existing public judgment node.

    This is a semantic review signal, not a claim that every paragraph needs
    four fixed moves.  It fires only when the source block already exposes at
    least three distinct node categories and the candidate drops one or more.
    """
    if scene.upper() != "MODELING":
        return []
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    findings: list[dict] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal" or left_start == left_end or right_start == right_end:
            continue
        before_block = "\n".join(before_lines[left_start:left_end])
        after_block = "\n".join(after_lines[right_start:right_end])
        if _content_chars(before_block) < 80:
            continue
        before_categories = [
            name for name, pattern in MODELING_JUDGMENT_PATTERNS.items()
            if pattern.search(before_block)
        ]
        after_categories = [
            name for name, pattern in MODELING_JUDGMENT_PATTERNS.items()
            if pattern.search(after_block)
        ]
        if len(before_categories) < 3:
            continue
        missing = [name for name in before_categories if name not in after_categories]
        if not missing:
            continue
        before_count = _content_chars(before_block)
        after_count = _content_chars(after_block)
        ratio = after_count / before_count if before_count else 1.0
        item = {
            "severity": "warning",
            "code": "MODELING_JUDGMENT_CHAIN_LOSS",
            "before_count": before_count,
            "after_count": after_count,
            "compression_ratio": round(ratio, 4),
            "before_categories": before_categories,
            "after_categories": after_categories,
            "missing_categories": missing,
            "before_line_range": [left_start + 1, left_end],
            "after_line_range": [right_start + 1, right_end],
            "before_examples": [_line_example(before_lines, left_start, left_end)],
            "after_examples": [_line_example(after_lines, right_start, right_end)],
            "before_sequence_sha256": hashlib.sha256(before_block.encode("utf-8")).hexdigest(),
            "after_sequence_sha256": hashlib.sha256(after_block.encode("utf-8")).hexdigest(),
            "location_method": "changed-block-modeling-judgment-chain",
        }
        item["finding_sha256"] = _finding_sha256(item)
        findings.append(item)
    return findings


def protected_view(text: str, terms: list[str]) -> dict:
    return {
        "math": [normalize_math(match.group(0)) for match in MATH_PATTERN.finditer(text)],
        "headings": HEADING_PATTERN.findall(text),
        "references": REFERENCE_PATTERN.findall(text),
        "commands": COMMAND_PATTERN.findall(text),
        "environments": ENV_PATTERN.findall(text),
        "numbers": NUMBER_PATTERN.findall(text),
        "units": UNIT_PATTERN.findall(text),
        "objectives": [match.group(0).casefold() for match in OBJECTIVE_PATTERN.finditer(text)],
        "constraint_directions": canonical_constraint_directions(text),
        "negations": [match.group(0).casefold() for match in NEGATION_PATTERN.finditer(text)],
        "causal_markers": [match.group(0).casefold() for match in CAUSAL_PATTERN.finditer(text)],
        "claim_strength": [match.group(0).casefold() for match in CLAIM_STRENGTH_PATTERN.finditer(text)],
        "terms": {term: text.count(term) for term in terms},
    }


def audit(
    before_path: Path,
    after_path: Path,
    terms_path: Path | None = None,
    scene: str = "GENERAL",
) -> dict:
    before = read_tex_tree(before_path)
    after = read_tex_tree(after_path)
    terms: list[str] = []
    if terms_path:
        terms = [line.strip() for line in terms_path.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    left = protected_view(before, terms)
    right = protected_view(after, terms)
    findings: list[dict] = []
    codes = {
        "math": "MATH_CHANGED",
        "headings": "STRUCTURE_CHANGED",
        "references": "REFERENCE_CHANGED",
        "commands": "TEX_COMMAND_CHANGED",
        "environments": "TEX_ENVIRONMENT_CHANGED",
        "numbers": "NUMBER_CHANGED",
        "units": "UNIT_CHANGED",
        "objectives": "OBJECTIVE_DIRECTION_CHANGED",
        "constraint_directions": "CONSTRAINT_DIRECTION_CHANGED",
        "negations": "NEGATION_CHANGED",
        "causal_markers": "CAUSAL_DIRECTION_MARKER_CHANGED",
        "claim_strength": "CLAIM_STRENGTH_CHANGED",
    }
    advisory_keys = {"negations", "causal_markers", "claim_strength"}
    semantic_keys = {"constraint_directions", "negations", "causal_markers", "claim_strength"}
    for key, code in codes.items():
        if left[key] != right[key]:
            finding = {
                "severity": "warning" if key in advisory_keys else "error",
                "code": code,
                "before_count": len(left[key]),
                "after_count": len(right[key]),
            }
            if key in semantic_keys:
                _augment_semantic_finding(finding, key, before, after)
            findings.append(finding)
    findings.extend(argument_compression_findings(before, after))
    findings.extend(modeling_judgment_chain_findings(before, after, scene))
    for term in terms:
        if left["terms"][term] != right["terms"][term]:
            findings.append({
                "severity": "error",
                "code": "PROTECTED_TERM_CHANGED",
                "term": term,
                "before_count": left["terms"][term],
                "after_count": right["terms"][term],
            })

    # A multiset summary helps locate changes without printing the whole manuscript.
    changed_numbers = sorted((collections.Counter(left["numbers"]) - collections.Counter(right["numbers"])).elements())
    introduced_numbers = sorted((collections.Counter(right["numbers"]) - collections.Counter(left["numbers"])).elements())
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "coverage": "full" if terms_path else "partial",
        "skipped_checks": ([] if terms_path else [{
            "check": "protected-term-inventory",
            "reason": "缺少 --terms；未按词表核对受保护术语",
            "consequence": "本次运行没有检查术语保留，PASS 不代表专有名词未被改动",
        }]),
        "before": str(before_path.resolve()),
        "after": str(after_path.resolve()),
        "scene": scene.upper(),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "number_diff": {
            "removed": changed_numbers[:20],
            "introduced": introduced_numbers[:20],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before_tex", type=Path)
    parser.add_argument("after_tex", type=Path)
    parser.add_argument("--terms", type=Path)
    parser.add_argument("--scene", default="GENERAL")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.before_tex, args.after_tex, args.terms, args.scene)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"REWRITE CONTRACT {report['status'].upper()} coverage={report['coverage']} errors={report['errors']}")
        print(f"before={report['before']}")
        print(f"after={report['after']}")
        for item in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key not in {"severity", "code"})
            print(f"[{item['severity'].upper()}] {item['code']}: {detail}")
        for item in report["skipped_checks"]:
            print(f"[SKIPPED] {item['check']}: {item['reason']}；{item['consequence']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
