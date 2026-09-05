#!/usr/bin/env python3
"""Compare a source document with its humanized rewrite.

This checker deliberately audits preservation, not academic correctness.  It
protects deterministic Markdown/LaTeX spans and reports changes to Chinese
speech-act markers that can silently alter an author's claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import scan_humanize_chinese as lexical  # noqa: E402


MATH_ENVIRONMENTS = {
    "align",
    "align*",
    "alignat",
    "alignat*",
    "aligned",
    "alignedat",
    "array",
    "cases",
    "displaymath",
    "equation",
    "equation*",
    "gather",
    "gather*",
    "math",
    "matrix",
    "multline",
    "multline*",
    "pmatrix",
    "smallmatrix",
    "split",
    "vmatrix",
    "Vmatrix",
}
QUOTE_ENVIRONMENTS = {"quote", "quotation"}
CODE_ENVIRONMENTS = set(lexical.TEX_CODE_ENVIRONMENT_NAMES)
FORMAL_STATEMENT_ENVIRONMENTS = {
    f"{name}{suffix}"
    for name in (
        "corollary",
        "definition",
        "example",
        "exercise",
        "lemma",
        "problem",
        "proposition",
        "question",
        "theorem",
    )
    for suffix in ("", "*")
}
CRITICAL_COMMANDS = {
    "autoref",
    "cite",
    "citealp",
    "citeauthor",
    "citep",
    "citeyear",
    "citet",
    "cref",
    "Cref",
    "eqref",
    "includegraphics",
    "label",
    "pageref",
    "ref",
    "url",
}

SPEECH_ACT_MARKERS: dict[str, tuple[str, ...]] = {
    "negation": (
        "并不意味着",
        "并非",
        "不能",
        "不再",
        "未曾",
        "没有",
        "不",
        "未",
        "无",
        "非",
    ),
    "modality_scope": (
        "默认",
        "不一定",
        "在一定程度上",
        "有必要",
        "必须",
        "应当",
        "需要",
        "可能",
        "或许",
        "可以",
        "仅仅",
        "仅",
        "只",
        "可",
        "应",
    ),
    "focus_scope": (
        "最主要",
        "首要",
        "优先",
        "重点",
        "主要",
    ),
    "definition_naming": (
        "以下简称",
        "称之为",
        "定义为",
        "记作",
        "记为",
        "称为",
        "简称",
        "所谓",
        "定义",
    ),
    "assumption": ("不妨设", "假定", "假设", "设"),
    "reporting_observation": (
        "研究结果表明",
        "实验结果表明",
        "结果表明",
        "结果显示",
        "可以观察到",
        "可以看到",
        "观察到",
        "我们发现",
        "表明",
        "显示",
        "发现",
    ),
    "attribution_source": (
        "已有研究",
        "既有研究",
        "相关研究",
        "已有文献",
        "既有文献",
        "相关文献",
        "业内普遍认为",
        "一些学者指出",
        "有观点认为",
        "研究者认为",
        "研究者指出",
        "专家认为",
        "专家指出",
        "学者认为",
        "学者指出",
        "文献认为",
        "文献指出",
        "本研究证实",
        "本研究证明",
        "本研究表明",
        "本文证实",
        "本文证明",
        "本文表明",
    ),
    # Preserve explicit causal and inferential links.  These are semantic
    # relations, not style defects: a structural scanner may nominate a run
    # of short formula captions for review, but it cannot authorize deleting
    # the relation and leaving adjacent formulas to imply it.
    "logical_relation": (
        "由此可见",
        "由此得到",
        "由此可得",
        "据此可得",
        "因此",
        "所以",
        "于是",
        "从而",
        "因而",
    ),
    "condition": ("当且仅当", "只有当", "除非", "仅当", "只要", "如果", "若", "当"),
}

# An explicit section-navigation shell does not assert a source-to-conclusion
# relation inside the editable passage.  Keep this exemption deliberately
# narrow: it does not cover standalone formula captions or ordinary
# sentence-level inferences.
LOGICAL_RELATION_ROUTE_SHELL_RE = re.compile(
    r"^\s*(?P<marker>由此可见|由此得到|由此可得|据此可得|因此|所以|于是|从而|因而)"
    r"[，,]?\s*(?:本节|本章|本文|下文)"
    r"(?:首先|随后|接着|将|主要)?"
    r"(?:讨论|介绍|说明|分析|阐述|展开|给出|研究)"
)

# Exempt only markers that are part of enumerated style shells. Later markers
# in the same sentence remain protected.
MODALITY_STYLE_SHELL_RE = re.compile(
    r"^\s*(?:"
    r"(?P<marker>需要|必须|有必要)(?:指出|说明|强调|注意)的?是"
    r"|(?:(?:本(?:问|研究|文|模型)|其)(?:的)?局限\s*)"
    r"(?P<editorial_marker>需要|应当|应该|必须|仍需)"
    r"(?:在(?:正文|论文)(?:里|中)?|)"
    r"(?:写清|说明|交代)"
    r")[，,:：]?"
)
LOGICAL_FUTURE_BRIDGE_SHELL_RE = re.compile(
    r"^\s*(?:[^。！？!?；;]{0,160}?[，,])?\s*"
    r"(?P<marker>因此|所以|于是|从而|因而)"
    r"(?:为|给|供)(?:后续|未来)(?:研究|分析|检验|工作|探索)?"
    r"[^。！？!?；;]{0,24}?(?:提供|奠定|打下|形成)"
    r"[^。！？!?；;]{0,16}?(?:基础|支撑|线索|参考|依据|方向|起点)"
)

# Markers require marker-specific lexical-span exclusions.  Without these, a
# useful signal such as "应" also fires inside technical words such as "响应"
# and "对应", while a global union can incorrectly hide a real "不" merely
# because another marker is lexical inside the same word.  Keep every entry
# narrow and auditable; a word that excludes two markers must be registered
# explicitly under both markers.
MARKER_SPAN_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    # These are lexical/technical compounds, not sentence-level negation.
    # Keep the list explicit so a new domain term is reviewed rather than
    # silently broadening a generic boundary heuristic.
    "不": (
        "不仅",
        "不但",
        "不变量",
        "不锈钢",
        "不可压缩流",
        "不可约",
    ),
    "非": ("非常",),
    "仅": ("不仅",),
    # "应" is also a productive character inside ordinary technical nouns
    # and verbs.  These compounds must be screened as whole lexical units;
    # they are not sentence-level obligations.  Keep this explicit rather
    # than dropping the single-character marker, because standalone forms
    # such as "应当" and "应开展" still carry a speech-act change.
    "应": (
        "对应",
        "相应",
        "响应",
        "呼应",
        "回应",
        "感应",
        "顺应",
        "反应",
        "效应",
        "适应",
        "应用",
        "供应",
        "应急",
        "应激",
        "应力",
        "应变",
        "应答",
    ),
    "设": ("设备", "设施", "建设", "设计"),
    "若": ("若干",),
    "当": ("相当", "恰当", "适当", "当量", "当代"),
    "可": (
        "不可压缩流",
        "不可约",
        "可靠",
        "许可",
        "认可",
        "可视化",
        "可微",
        "可积",
        "可导",
        "可逆",
    ),
    "所以": ("所以然",),
}

# These checks cover a narrow class of source-to-rewrite transitions that a
# token inventory cannot see.  They are intentionally conservative: a warning
# is emitted only when the risky predicate is absent from the source and the
# source contains the corresponding directive or support shell.
SEMANTIC_TRANSITION_RULES: tuple[
    tuple[str, str, tuple[str, ...], tuple[str, ...]], ...
] = (
    (
        "SPEECH_ACT_DIRECTIVE_TO_COMPLETION",
        "An editing directive or artifact purpose was rewritten as a completed artifact assertion.",
        (
            r"表格的作用(?:是|在于)",
            r"正文(?:里|中)?(?:要|需要|应当|应该)",
            r"如果放到图上",
            r"图上应当",
        ),
        (
            r"表格[^。！？\n]{0,16}(?:列出|展示|包含|给出)",
            r"图(?:中|上)[^。！？\n]{0,16}(?:标出|展示|包含|给出)",
        ),
    ),
    (
        "SPEECH_ACT_EDITORIAL_TO_EVIDENCE",
        "An editorial instruction to retain or present evidence was rewritten as an evidence claim.",
        (
            r"(?:正文|文中)[^。！？\n]{0,96}(?:要|需|需要|应当|应该|必须)[^。！？\n]{0,96}(?:保留|呈现|写成|说明)",
        ),
        (
            r"(?:粗扫|加密扫描|两类扫描|扫描结果)[^。！？\n]{0,32}(?:共同)?(?:支持|表明|显示|证明)[^。！？\n]{0,48}(?:结论|判断|区间)",
        ),
    ),
    (
        "SPEECH_ACT_SUPPORT_TO_ACTUAL_USE",
        "A support, value, or closure claim was rewritten as actual engineering use or a completed decision.",
        (
            r"为工程应用提供[^。！？\n]{0,12}(?:支撑|依据|参考)",
            r"从数据到决策[^。！？\n]{0,16}闭环",
            r"形成[^。！？\n]{0,16}闭环",
        ),
        (
            r"(?:用于|用来|服务于|指导|影响)[^。！？\n]{0,16}(?:工程决策|方案选择)",
            r"(?:工程决策|方案选择)[^。！？\n]{0,12}(?:已经|已被|完成|落地)",
        ),
    ),
    (
        "SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE",
        "Missing content or an absent analysis layer was rewritten as missing linkage or transition.",
        (
            r"缺少[^。！？\n]{1,48}(?:层面|层|内容|分析|讨论)",
        ),
        (
            r"缺少[^。！？\n]{1,56}(?:衔接|联系|连接|过渡)",
        ),
    ),
    (
        "SPEECH_ACT_ABSENCE_TO_FAILURE",
        "An absent or ungenerated artifact was rewritten as an artifact that existed and failed validation.",
        (
            r"(?:没法|未能|没有|尚未|无法)[^。！？\n]{0,24}(?:生成|产生|形成|得到|输出)",
        ),
        (
            r"(?:字段|结果|输出|工件)[^。！？\n]{0,16}(?:验证|校验|测试|生成)[^。！？\n]{0,8}(?:失败|有误|错误)",
        ),
    ),
    (
        "SPEECH_ACT_PURPOSE_TO_RESULT",
        "A stated purpose or comparison role was rewritten as an observed result or proof.",
        (
            r"(?:用于|用来|作用在于)[^。！？\n]{0,24}(?:比较|校准|检验|拆分|说明|分析)",
        ),
        (
            r"(?:结果|实验|测试)[^。！？\n]{0,8}(?:表明|显示|证明)",
            r"(?:验证|证明)了",
        ),
    ),
    (
        "SPEECH_ACT_PENDING_CHECK_TO_COMPLETION",
        "A pending check, rerun, or validation was rewritten as a completed or effective state.",
        (
            r"(?:需要|仍需|待|尚待)[^。！？\n]{0,20}(?:实测|验证|确认|重跑|复核|证明)",
        ),
        (
            r"(?:已经|已)[^，,；;：:。！？\n]{0,20}(?:生效|完成|验证|确认|关闭|证明|通过)",
        ),
    ),
    (
        "SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION",
        "An explicitly internal indicator or projection was rewritten as external or real-world validation.",
        (
            r"(?:内部|情景)[^。！？\n]{0,40}(?:不是|不构成)[^。！？\n]{0,20}(?:外部|实际)[^。！？\n]{0,12}(?:验证|观测|事实)",
        ),
        (
            r"(?:验证|证明)了[^。！？\n]{0,24}(?:实际|真实|外部|长期|生态健康)",
        ),
    ),
    (
        "SPEECH_ACT_CANDIDATE_TO_CONFIRMED",
        "A conditional candidate, bracket, or unstable ordering was rewritten as a verified threshold or stable conclusion.",
        (
            r"(?:候选(?:括号|区间|阈值|路线|解释)|并非完全稳健|可能[^。！？\n]{0,12}交换)",
        ),
        (
            r"(?:经[^。！？\n]{0,12}验证的[^。！？\n]{0,16}(?:阈值|结论|排序)|稳健[^。！？\n]{0,12}(?:临界阈值|阈值|结论)|稳定排序|已经?证明|已证明)",
        ),
    ),
)

HEDGE_MARKERS = ("可能", "或许", "在一定程度上")
DEGREE_CLAIM_PATTERN = re.compile(
    r"(?:影响程度[^。！？\n]{0,8}(?:有限|较小|轻微|显著|较大)|"
    r"影响[^。！？\n]{0,5}(?:有限|较小|轻微|显著|较大))"
)

DIRECT_PERMISSION_PATTERN = re.compile(
    r"(?<![不未没无非])(?:可以|能够|能|可)[^。！？!?；;\n]{0,40}?直接"
)
DIRECT_PROHIBITION_PATTERN = re.compile(
    r"(?:不可以|不能|不可|不得|不应|不宜|不要)[^。！？!?；;\n]{0,40}?直接"
)
POLARITY_ANCHOR_STRIP_PATTERN = re.compile(
    r"不可以|可以|能够|不能|不可|不得|不应|不宜|不要|能|可|直接"
)
POLARITY_ANCHOR_STOP = {
    "不满",
    "不能",
    "不可",
    "不要",
    "不得",
    "不应",
    "不宜",
    "可以",
    "能够",
    "直接",
    "因为",
    "如果",
    "即使",
    "据此",
    "时候",
    "条件",
    "满足",
    "进行",
    "需要",
    "应当",
    "相关",
}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class CheckResult:
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    advisories: list[Diagnostic] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)

    @property
    def hard_failure(self) -> bool:
        return bool(self.errors)

    @property
    def status(self) -> str:
        return "fail" if self.hard_failure else "pass"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "hard_failure": self.hard_failure,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "advisories": len(self.advisories),
            },
            "errors": [asdict(item) for item in self.errors],
            "warnings": [asdict(item) for item in self.warnings],
            "advisories": [asdict(item) for item in self.advisories],
            "evidence": self.evidence,
        }


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def strip_tex_comments(text: str) -> str:
    """Remove unescaped TeX comments while preserving line boundaries."""
    output: list[str] = []
    for line in text.splitlines(keepends=True):
        cut = None
        for index, char in enumerate(line):
            if char == "%" and not _is_escaped(line, index):
                cut = index
                break
        if cut is None:
            output.append(line)
            continue
        prefix = line[:cut]
        if prefix.endswith("\r"):
            prefix = prefix[:-1]
        # TeX comments consume the physical newline as well.  Removing both
        # makes comment-only line insertion invisible while retaining any
        # intentional space before the percent sign.
        output.append(prefix)
    return "".join(output)


def _tex_comment_spans(text: str) -> list[str]:
    """Return unescaped TeX comments exactly, including a bare continuation percent."""
    comments: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        for index, char in enumerate(line):
            if char == "%" and not _is_escaped(line, index):
                comments.append(line[index:])
                break
    return comments


def _canonical_span(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.strip().split("\n"))


def _mask_ranges(text: str, ranges: Iterable[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in ranges:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _tex_comment_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        for index, char in enumerate(line):
            if char == "%" and not _is_escaped(line, index):
                ranges.append((offset + index, offset + len(line)))
                break
        offset += len(line)
    return ranges


def _named_environment_ranges(
    text: str,
    names: set[str],
    excluded_ranges: Sequence[tuple[int, int]] = (),
) -> list[tuple[int, int]]:
    if not names:
        return []
    masked = _mask_ranges(text, excluded_ranges)
    alternatives = "|".join(
        sorted((re.escape(name) for name in names), key=len, reverse=True)
    )
    pattern = re.compile(
        rf"(?s)\\begin\s*\{{(?P<name>{alternatives})\}}.*?"
        rf"\\end\s*\{{(?P=name)\}}"
    )
    return [(match.start(), match.end()) for match in pattern.finditer(masked)]


def _math_ranges_for_speech(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    occupied = list(excluded_ranges)
    ranges = _named_environment_ranges(text, MATH_ENVIRONMENTS, occupied)
    occupied.extend(ranges)
    masked = _mask_ranges(text, occupied)
    for pattern in (re.compile(r"(?s)\\\[.*?\\\]"), re.compile(r"(?s)\\\(.*?\\\)")):
        found = [(match.start(), match.end()) for match in pattern.finditer(masked)]
        ranges.extend(found)
        occupied.extend(found)
        masked = _mask_ranges(text, occupied)

    index = 0
    while index < len(masked):
        if masked[index] != "$" or _is_escaped(masked, index):
            index += 1
            continue
        delimiter = "$$" if masked.startswith("$$", index) else "$"
        search = index + len(delimiter)
        closing = -1
        while search < len(masked):
            candidate = masked.find(delimiter, search)
            if candidate < 0:
                break
            if not _is_escaped(masked, candidate):
                closing = candidate
                break
            search = candidate + len(delimiter)
        if closing < 0:
            index += len(delimiter)
            continue
        end = closing + len(delimiter)
        ranges.append((index, end))
        masked = _mask_ranges(masked, [(index, end)])
        index = end
    return _merge_ranges(ranges)


def _quotation_ranges_for_speech(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    masked = _mask_ranges(text, excluded_ranges)
    ranges: list[tuple[int, int]] = []
    for pattern in (
        re.compile(r"“[^”]*”"),
        re.compile(r"‘[^’]*’"),
        re.compile(r"「[^」]*」"),
        re.compile(r"『[^』]*』"),
        re.compile(r'"[^"\n]+"'),
        re.compile(r"(?<!`)``[^\n]*?''"),
        re.compile(r"(?m)^(?:[ \t]*>[^\n]*(?:\n|$))+"),
    ):
        ranges.extend((match.start(), match.end()) for match in pattern.finditer(masked))

    command_quote_re = re.compile(r"\\(?:enquote|textquote)\s*(?P<brace>\{)")
    for match in command_quote_re.finditer(masked):
        parsed = _balanced_group(text, match.start("brace"), "{", "}")
        if parsed is not None:
            ranges.append((match.start(), parsed[1]))
    ranges.extend(
        _named_environment_ranges(text, QUOTE_ENVIRONMENTS, excluded_ranges)
    )
    return _merge_ranges(ranges)


def _critical_command_ranges_for_speech(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    masked = _mask_ranges(text, excluded_ranges)
    ranges: list[tuple[int, int]] = []
    command_re = re.compile(r"\\(?P<name>[A-Za-z@]+)(?P<star>\*)?")
    for match in command_re.finditer(masked):
        name = match.group("name")
        if name not in CRITICAL_COMMANDS and not _is_citation_command(name):
            continue
        index = match.end()
        while True:
            while index < len(masked) and masked[index].isspace():
                index += 1
            if index < len(masked) and masked[index] == "[":
                parsed = _balanced_group(masked, index, "[", "]")
                if parsed is None:
                    break
                _, index = parsed
                continue
            break
        while index < len(masked) and masked[index].isspace():
            index += 1
        parsed = _balanced_group(masked, index, "{", "}")
        ranges.append((match.start(), parsed[1] if parsed is not None else match.end()))
    return ranges


def _speech_surface(
    text: str,
    document_format: str,
    protect_quotes: bool,
) -> tuple[str, list[tuple[int, int]]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    _, code_ranges = _code_spans(normalized)
    ranges = list(code_ranges)
    ranges.extend(_math_ranges_for_speech(normalized, ranges))
    if document_format == "tex":
        ranges.extend(_tex_comment_ranges(normalized))
        ranges.extend(
            _named_environment_ranges(
                normalized, FORMAL_STATEMENT_ENVIRONMENTS, ranges
            )
        )
        ranges.extend(_critical_command_ranges_for_speech(normalized, ranges))
    if protect_quotes:
        ranges.extend(_quotation_ranges_for_speech(normalized, ranges))
    merged = _merge_ranges(ranges)
    return _mask_ranges(normalized, merged), merged


def _markdown_fence_spans(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]] = (),
    *,
    exact: bool = False,
) -> list[tuple[int, int, str]]:
    """Return CommonMark fences, whose closer may be longer than the opener."""
    masked = _mask_ranges(text, excluded_ranges)
    opening_re = re.compile(
        r"(?m)^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^\n]*(?:\n|$)"
    )
    spans: list[tuple[int, int, str]] = []
    normalize = (lambda value: value) if exact else _canonical_span
    cursor = 0
    while cursor < len(masked):
        opening = opening_re.search(masked, cursor)
        if opening is None:
            break
        fence = opening.group("fence")
        closing_re = re.compile(
            rf"(?m)^[ \t]{{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*(?:\n|$)"
        )
        closing = closing_re.search(masked, opening.end())
        end = closing.end() if closing is not None else len(masked)
        spans.append((opening.start(), end, normalize(text[opening.start():end])))
        cursor = end
    return spans


def _code_spans(
    text: str,
    *,
    exact: bool = False,
) -> tuple[list[str], list[tuple[int, int]]]:
    items: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    normalize = (lambda value: value) if exact else _canonical_span
    tex_code_spans, _problems = lexical._tex_code_like_spans(text)
    for start, end, _reason in lexical._merge_spans(tex_code_spans):
        items.append((start, end, normalize(text[start:end])))
        occupied.append((start, end))

    for start, end, canonical in _markdown_fence_spans(text, occupied, exact=exact):
        items.append((start, end, canonical))
        occupied.append((start, end))

    masked = _mask_ranges(text, occupied)

    index = 0
    while index < len(masked):
        if masked[index] != "`":
            index += 1
            continue
        end_ticks = index
        while end_ticks < len(masked) and masked[end_ticks] == "`":
            end_ticks += 1
        delimiter = masked[index:end_ticks]
        closing = masked.find(delimiter, end_ticks)
        if closing < 0 or "\n" in masked[end_ticks:closing]:
            index = end_ticks
            continue
        end = closing + len(delimiter)
        items.append((index, end, normalize(text[index:end])))
        occupied.append((index, end))
        index = end

    items.sort(key=lambda item: item[0])
    occupied.sort()
    return [item[2] for item in items], occupied


def _extract_environment_spans(text: str, names: set[str]) -> list[str]:
    if not names:
        return []
    alternatives = "|".join(sorted((re.escape(name) for name in names), key=len, reverse=True))
    pattern = re.compile(
        rf"(?s)\\begin\s*\{{(?P<name>{alternatives})\}}.*?"
        rf"\\end\s*\{{(?P=name)\}}"
    )
    return [_canonical_span(match.group(0)) for match in pattern.finditer(text)]


def _math_spans(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]],
    *,
    exact: bool = False,
    tex_comments: bool = False,
) -> list[str]:
    occupied = list(excluded_ranges)
    if tex_comments:
        occupied.extend(lexical._tex_comment_ranges(text, occupied))
    masked = _mask_ranges(text, occupied)
    spans: list[tuple[int, int, str]] = []
    normalize = (lambda value: value) if exact else _canonical_span

    alternatives = "|".join(
        sorted((re.escape(name) for name in MATH_ENVIRONMENTS), key=len, reverse=True)
    )
    env_re = re.compile(
        rf"(?s)\\begin\s*\{{(?P<name>{alternatives})\}}.*?"
        rf"\\end\s*\{{(?P=name)\}}"
    )
    for match in env_re.finditer(masked):
        spans.append((match.start(), match.end(), normalize(text[match.start():match.end()])))
        occupied.append((match.start(), match.end()))

    masked = _mask_ranges(masked, occupied)
    for pattern in (re.compile(r"(?s)\\\[.*?\\\]"), re.compile(r"(?s)\\\(.*?\\\)")):
        matches = list(pattern.finditer(masked))
        for match in matches:
            spans.append((match.start(), match.end(), normalize(text[match.start():match.end()])))
            occupied.append((match.start(), match.end()))
        masked = _mask_ranges(masked, [(match.start(), match.end()) for match in matches])

    index = 0
    while index < len(masked):
        if masked[index] != "$" or _is_escaped(masked, index):
            index += 1
            continue
        delimiter = "$$" if masked.startswith("$$", index) else "$"
        search = index + len(delimiter)
        closing = -1
        while search < len(masked):
            candidate = masked.find(delimiter, search)
            if candidate < 0:
                break
            if not _is_escaped(masked, candidate):
                closing = candidate
                break
            search = candidate + len(delimiter)
        if closing < 0:
            index += len(delimiter)
            continue
        end = closing + len(delimiter)
        spans.append((index, end, normalize(text[index:end])))
        index = end

    unclosed_math, _problems = lexical._tex_unclosed_math_spans(text)
    for start, end, _reason in lexical._merge_spans(unclosed_math):
        if any(left < end and start < right for left, right in excluded_ranges):
            continue
        spans.append((start, end, normalize(text[start:end])))

    spans.sort(key=lambda item: item[0])
    return [item[2] for item in spans]


def _quotation_spans(text: str, excluded_ranges: Sequence[tuple[int, int]]) -> list[str]:
    masked = _mask_ranges(text, excluded_ranges)
    spans: list[tuple[int, str]] = []
    patterns = (
        re.compile(r"“[^”]*”"),
        re.compile(r"‘[^’]*’"),
        re.compile(r"「[^」]*」"),
        re.compile(r"『[^』]*』"),
        re.compile(r'"[^"\n]+"'),
        re.compile(r"(?<!`)``[^\n]*?''"),
        re.compile(r"(?m)^(?:[ \t]*>[^\n]*(?:\n|$))+"),
    )
    for pattern in patterns:
        for match in pattern.finditer(masked):
            spans.append((match.start(), _canonical_span(text[match.start():match.end()])))

    command_quote_re = re.compile(r"\\(?:enquote|textquote)\s*(?P<brace>\{)")
    for match in command_quote_re.finditer(masked):
        parsed = _balanced_group(text, match.start("brace"), "{", "}")
        if parsed is None:
            continue
        _, end = parsed
        spans.append((match.start(), _canonical_span(text[match.start():end])))

    quote_env_re = re.compile(
        r"(?s)\\begin\s*\{(?P<name>quote|quotation)\}.*?"
        r"\\end\s*\{(?P=name)\}"
    )
    for match in quote_env_re.finditer(masked):
        spans.append((match.start(), _canonical_span(text[match.start():match.end()])))
    spans.sort(key=lambda item: item[0])
    return [item[1] for item in spans]


def _balanced_group(text: str, start: int, opening: str, closing: str) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != opening:
        return None
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == opening and not _is_escaped(text, index):
            depth += 1
        elif char == closing and not _is_escaped(text, index):
            depth -= 1
            if depth == 0:
                return text[start:index + 1], index + 1
        index += 1
    return None


def _critical_commands(
    text: str,
    excluded_ranges: Sequence[tuple[int, int]],
    editable_style_wrappers: Sequence[str] = (),
) -> list[str]:
    masked = _mask_ranges(text, excluded_ranges)
    editable = frozenset(editable_style_wrappers)
    output: list[tuple[int, str]] = []
    command_re = re.compile(r"\\(?P<name>[A-Za-z@]+)(?P<star>\*)?")
    for match in command_re.finditer(masked):
        name = match.group("name")
        if name in editable:
            continue
        index = match.end()
        groups: list[str] = []
        while True:
            while index < len(masked) and masked[index].isspace():
                index += 1
            if index >= len(masked) or masked[index] not in "[{":
                break
            opening = masked[index]
            parsed = _balanced_group(
                masked,
                index,
                opening,
                "]" if opening == "[" else "}",
            )
            if parsed is None:
                break
            group, index = parsed
            groups.append(_canonical_span(group))
        if not groups:
            if name not in CRITICAL_COMMANDS and not _is_citation_command(name):
                continue
            canonical = f"\\{name}{match.group('star') or ''}<MISSING_ARGUMENT>"
        else:
            canonical = f"\\{name}{match.group('star') or ''}" + "".join(groups)
        output.append((match.start(), canonical))
    output.sort(key=lambda item: item[0])
    return [item[1] for item in output]


def _is_citation_command(name: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:cite(?:alp|alt|author|p|t|year|yearpar)?|"
            r"(?:auto|foot|full|no|paren|smart|super|text)cite|"
            r"(?:[A-Za-z@]*[A-Za-z@])cite)",
            name,
        )
    )


NUMBER_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?"
    r"(?:\s*(?:~|～|–|—|至)\s*[-+]?(?:\d+(?:\.\d+)?))?"
    r"\s*(?:\\%|%|‰|℃|°[CF]|"
    r"(?:[kMGTmunμ]?(?:m|s|g|A|K|mol|Hz|Pa|J|W|V|N|L|l|B|bps))"
    r"(?:\^?\{?-?\d+\}?|[²³])?(?:/[A-Za-zμ]+(?:\^?\{?-?\d+\}?|[²³])?)?|"
    r"年|月|日|小时|分钟|秒|千米|公里|厘米|毫米|微米|纳米|米|千克|公斤|克|毫克|人|次|项|组|倍)?"
)
CHINESE_NUMBER_RE = re.compile(
    r"(?:"
    r"第[零〇一二两三四五六七八九十百千万亿廿卅]+"
    r"(?:位|名|篇|章|节|级|轮|次|项|组|倍)?"
    r"|[零〇一二两三四五六七八九十百千万亿廿卅]+"
    r"(?:年|月|日|小时|分钟|秒|千米|公里|厘米|毫米|微米|纳米|米|千克|公斤|克|毫克|"
    r"人|位|名|篇|章|节|级|轮|次|项|组|倍)"
    r")"
)
GARBLED_MARKER_RE = re.compile(
    r"(?:\ufffd|[\ue000-\uf8ff]|锛岋|銆俾|鈥濃|â(?:€|€™|€œ|€“|€”))"
)
GARBLED_SPAN_RE = re.compile(
    rf"[^，。！？；;\s]*(?:{GARBLED_MARKER_RE.pattern})[^，。！？；;\s]*"
)


def _numbers_and_units(text: str, excluded_ranges: Sequence[tuple[int, int]]) -> list[str]:
    masked = _mask_ranges(text, excluded_ranges)
    output: list[tuple[int, str]] = []
    for match in NUMBER_UNIT_RE.finditer(masked):
        token = re.sub(r"\s+", "", match.group(0)).replace("\\%", "%")
        output.append((match.start(), token))
    output.extend((match.start(), match.group(0)) for match in CHINESE_NUMBER_RE.finditer(masked))
    return [token for _, token in sorted(output)]


def _garbled_spans(text: str) -> list[str]:
    return [_canonical_span(match.group(0)) for match in GARBLED_SPAN_RE.finditer(text)]


def _environment_events(text: str, excluded_ranges: Sequence[tuple[int, int]]) -> list[tuple[str, str]]:
    masked = _mask_ranges(text, excluded_ranges)
    pattern = re.compile(r"\\(?P<kind>begin|end)\s*\{(?P<name>[^{}\s]+)\}")
    return [(match.group("kind"), match.group("name")) for match in pattern.finditer(masked)]


def _validate_environment_nesting(events: Sequence[tuple[str, str]]) -> list[str]:
    stack: list[str] = []
    problems: list[str] = []
    for kind, name in events:
        if kind == "begin":
            stack.append(name)
        elif not stack:
            problems.append(f"end{{{name}}} has no matching begin")
        elif stack[-1] != name:
            problems.append(f"end{{{name}}} closes begin{{{stack[-1]}}}")
            stack.pop()
        else:
            stack.pop()
    problems.extend(f"begin{{{name}}} has no matching end" for name in reversed(stack))
    return problems


def _brace_problems(text: str, excluded_ranges: Sequence[tuple[int, int]]) -> list[str]:
    masked = _mask_ranges(text, excluded_ranges)
    stack: list[int] = []
    problems: list[str] = []
    for index, char in enumerate(masked):
        if char == "{" and not _is_escaped(masked, index):
            stack.append(index)
        elif char == "}" and not _is_escaped(masked, index):
            if stack:
                stack.pop()
            else:
                problems.append(f"unmatched closing brace at offset {index}")
    problems.extend(f"unmatched opening brace at offset {index}" for index in stack[:10])
    if len(stack) > 10:
        problems.append(f"{len(stack) - 10} additional unmatched opening braces")
    return problems


def _marker_counts(text: str) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = {}
    for category, markers in SPEECH_ACT_MARKERS.items():
        ordered = sorted(markers, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(marker) for marker in ordered))
        counts: Counter[str] = Counter()
        for match in pattern.finditer(text):
            marker = match.group(0)
            if _inside_excluded_word(text, match.start(), marker):
                continue
            counts[marker] += 1
        result[category] = counts
    return result


def _segment_spans(text: str, pattern: str, prefix: str) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    start = 0
    for match in re.finditer(pattern, text):
        if match.start() > start and text[start : match.start()].strip():
            spans.append(
                {
                    "id": f"{prefix}{len(spans) + 1:04d}",
                    "start": start,
                    "end": match.start(),
                    "text": text[start : match.start()],
                }
            )
        start = match.end()
    if start < len(text) and text[start:].strip():
        spans.append(
            {
                "id": f"{prefix}{len(spans) + 1:04d}",
                "start": start,
                "end": len(text),
                "text": text[start:],
            }
        )
    return spans


def _containing_span(
    spans: Sequence[dict[str, object]], offset: int
) -> dict[str, object] | None:
    return next(
        (
            item
            for item in spans
            if int(item["start"]) <= offset < int(item["end"])
        ),
        None,
    )


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    previous_newline = text.rfind("\n", 0, offset)
    return line, offset - previous_newline


def _collect_speech_occurrences(
    text: str,
    side: str,
) -> tuple[
    dict[str, list[dict[str, object]]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    sentence_spans = _segment_spans(text, r"[。！？!?；;\n]+", "T")
    claim_spans = _segment_spans(text, r"[，,：:；;。！？!?\n]+", "C")
    occurrences: dict[str, list[dict[str, object]]] = {}
    for category, markers in SPEECH_ACT_MARKERS.items():
        ordered = sorted(markers, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(marker) for marker in ordered))
        category_occurrences: list[dict[str, object]] = []
        for match in pattern.finditer(text):
            marker = match.group(0)
            if _inside_excluded_word(text, match.start(), marker):
                continue
            sentence = _containing_span(sentence_spans, match.start())
            claim = _containing_span(claim_spans, match.start())
            if sentence is None or claim is None:
                continue
            if category == "logical_relation":
                sentence_text = str(sentence["text"])
                route_shell = LOGICAL_RELATION_ROUTE_SHELL_RE.match(sentence_text)
                future_bridge_shell = LOGICAL_FUTURE_BRIDGE_SHELL_RE.match(sentence_text)
                relative_marker_span = (
                    match.start() - int(sentence["start"]),
                    match.end() - int(sentence["start"]),
                )
                if (
                    route_shell is not None
                    and route_shell.span("marker") == relative_marker_span
                ):
                    continue
                if (
                    future_bridge_shell is not None
                    and future_bridge_shell.span("marker") == relative_marker_span
                ):
                    continue
            if category == "modality_scope":
                style_shell = MODALITY_STYLE_SHELL_RE.match(str(sentence["text"]))
                relative_marker_span = (
                    match.start() - int(sentence["start"]),
                    match.end() - int(sentence["start"]),
                )
                if (
                    style_shell is not None
                    and (
                        style_shell.span("marker") == relative_marker_span
                        or style_shell.span("editorial_marker") == relative_marker_span
                    )
                ):
                    continue
            line, column = _line_column(text, match.start())
            end_line, end_column = _line_column(text, match.end())
            category_occurrences.append(
                {
                    "side": side,
                    "category": category,
                    "marker": marker,
                    "start": match.start(),
                    "end": match.end(),
                    "line": line,
                    "column": column,
                    "end_line": end_line,
                    "end_column": end_column,
                    "sentence_id": sentence["id"],
                    "claim_id": claim["id"],
                    "sentence_context": re.sub(
                        r"\s+", " ", str(sentence["text"])
                    ).strip()[:240],
                }
            )
        occurrences[category] = category_occurrences
    return occurrences, sentence_spans, claim_spans


def _claim_records(
    text: str,
    claims: Sequence[dict[str, object]],
    occurrences: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    all_occurrences = [
        occurrence
        for category_occurrences in occurrences.values()
        for occurrence in category_occurrences
    ]
    records: list[dict[str, object]] = []
    for claim in claims:
        claim_id = str(claim["id"])
        claim_start = int(claim["start"])
        claim_text = str(claim["text"])
        marker_ranges = _merge_ranges(
            (
                int(item["start"]) - claim_start,
                int(item["end"]) - claim_start,
            )
            for item in all_occurrences
            if item["claim_id"] == claim_id
        )
        key = re.sub(
            r"[\s，,、:：;；]+", "", _mask_ranges(claim_text, marker_ranges)
        )
        records.append(
            {
                **claim,
                "key": key,
                "key_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest()
                if key
                else "",
                "category_counts": {
                    category: Counter(
                        str(item["marker"])
                        for item in category_occurrences
                        if item["claim_id"] == claim_id
                    )
                    for category, category_occurrences in occurrences.items()
                },
            }
        )
    return records


def _counter_delta(before: Counter[str], after: Counter[str]) -> dict[str, dict[str, int]]:
    return {
        "removed": dict(sorted((before - after).items())),
        "added": dict(sorted((after - before).items())),
    }


def _possibility_allowance(
    before_claim: dict[str, object],
    after_claim: dict[str, object],
) -> dict[str, object] | None:
    category = "modality_scope"
    before_counts = Counter(before_claim["category_counts"][category])
    after_counts = Counter(after_claim["category_counts"][category])
    core = {"可能", "或许"}
    eligible = {"可能", "或许", "在一定程度上"}
    before_core = sum(before_counts.get(item, 0) for item in core)
    after_core = sum(after_counts.get(item, 0) for item in core)
    before_eligible = sum(before_counts.get(item, 0) for item in eligible)
    after_eligible = sum(after_counts.get(item, 0) for item in eligible)
    before_other = Counter(
        {key: value for key, value in before_counts.items() if key not in eligible}
    )
    after_other = Counter(
        {key: value for key, value in after_counts.items() if key not in eligible}
    )
    if before_core < 2 or after_core != 1 or after_eligible != 1:
        return None
    if before_other != after_other or before_eligible <= after_eligible:
        return None
    delta = _counter_delta(before_counts, after_counts)
    budget = before_eligible - 1
    consumed = sum(delta["removed"].values()) - sum(delta["added"].values())
    if consumed != budget:
        return None
    return {
        "before_claim_id": before_claim["id"],
        "after_claim_id": after_claim["id"],
        "claim_key_sha256": before_claim["key_sha256"],
        "budget": budget,
        "consumed": consumed,
        "remaining": budget - consumed,
        "explained_removed": delta["removed"],
        "explained_added": delta["added"],
    }


def _claim_occurrences(
    occurrences: Sequence[dict[str, object]], claim_id: str
) -> list[dict[str, object]]:
    return [item for item in occurrences if item["claim_id"] == claim_id]


def _speech_act_audit(
    before_text: str,
    after_text: str,
) -> tuple[dict[str, object], list[tuple[str, dict[str, object]]], list[dict[str, object]], list[dict[str, object]]]:
    before_occurrences, _before_sentences, before_claim_spans = (
        _collect_speech_occurrences(before_text, "before")
    )
    after_occurrences, _after_sentences, after_claim_spans = (
        _collect_speech_occurrences(after_text, "after")
    )
    before_claims = _claim_records(
        before_text, before_claim_spans, before_occurrences
    )
    after_claims = _claim_records(after_text, after_claim_spans, after_occurrences)
    before_by_key: dict[str, list[dict[str, object]]] = {}
    after_by_key: dict[str, list[dict[str, object]]] = {}
    for claim in before_claims:
        if claim["key"]:
            before_by_key.setdefault(str(claim["key"]), []).append(claim)
    for claim in after_claims:
        if claim["key"]:
            after_by_key.setdefault(str(claim["key"]), []).append(claim)
    pairs = [
        (items[0], after_by_key[key][0])
        for key, items in before_by_key.items()
        if len(items) == 1 and len(after_by_key.get(key, [])) == 1
    ]
    paired_before_ids = {str(before_claim["id"]) for before_claim, _ in pairs}
    paired_after_ids = {str(after_claim["id"]) for _, after_claim in pairs}

    audit: dict[str, object] = {"categories": {}}
    warnings: list[tuple[str, dict[str, object]]] = []
    for category in SPEECH_ACT_MARKERS:
        before_items = before_occurrences[category]
        after_items = after_occurrences[category]
        before_counts = Counter(str(item["marker"]) for item in before_items)
        after_counts = Counter(str(item["marker"]) for item in after_items)
        allowances: list[dict[str, object]] = []
        residuals: list[dict[str, object]] = []
        for before_claim, after_claim in pairs:
            claim_before = Counter(before_claim["category_counts"][category])
            claim_after = Counter(after_claim["category_counts"][category])
            if claim_before == claim_after:
                continue
            allowance = (
                _possibility_allowance(before_claim, after_claim)
                if category == "modality_scope"
                else None
            )
            if allowance is not None:
                allowances.append(allowance)
                continue
            residuals.append(
                {
                    "scope": "CLAIM",
                    "before_claim_id": before_claim["id"],
                    "after_claim_id": after_claim["id"],
                    **_counter_delta(claim_before, claim_after),
                    "before_occurrences": _claim_occurrences(
                        before_items, str(before_claim["id"])
                    ),
                    "after_occurrences": _claim_occurrences(
                        after_items, str(after_claim["id"])
                    ),
                }
            )
        unpaired_before = [
            item for item in before_items if item["claim_id"] not in paired_before_ids
        ]
        unpaired_after = [
            item for item in after_items if item["claim_id"] not in paired_after_ids
        ]
        unpaired_before_counts = Counter(
            str(item["marker"]) for item in unpaired_before
        )
        unpaired_after_counts = Counter(str(item["marker"]) for item in unpaired_after)
        if unpaired_before_counts != unpaired_after_counts:
            residuals.append(
                {
                    "scope": "UNALIGNED_POOL",
                    "before_claim_id": None,
                    "after_claim_id": None,
                    **_counter_delta(unpaired_before_counts, unpaired_after_counts),
                    "before_occurrences": unpaired_before,
                    "after_occurrences": unpaired_after,
                }
            )
        details = {
            "before": dict(sorted(before_counts.items())),
            "after": dict(sorted(after_counts.items())),
            "before_occurrences": before_items,
            "after_occurrences": after_items,
            "raw_delta": _counter_delta(before_counts, after_counts),
            "safe_compression_allowances": allowances,
            "residual_delta": residuals,
        }
        audit["categories"][category] = details
        if residuals:
            warnings.append((category, details))
    audit["claim_pairing"] = {
        "before_claims": len(before_claims),
        "after_claims": len(after_claims),
        "unique_exact_pairs": len(pairs),
        "unpaired_before_claims": len(before_claims) - len(paired_before_ids),
        "unpaired_after_claims": len(after_claims) - len(paired_after_ids),
    }
    return audit, warnings, before_claims, after_claims


def _claim_strength_tension(claim_text: str) -> dict[str, list[str]] | None:
    hedges = [
        marker
        for marker in ("可能", "或许", "在一定程度上", "不一定", "未必")
        if marker in claim_text
    ]
    if not hedges:
        return None
    strong = [
        match.group(0)
        for match in re.finditer(
            r"证实|证明|必然|显著(?:提升|提高|降低|改善|增强|差异)",
            claim_text,
        )
    ]
    if re.search(r"(?:不能|尚不能|未能|无法)[^，,。！？!?；;]{0,6}(?:证实|证明)", claim_text):
        strong = [item for item in strong if item not in {"证实", "证明"}]
    if not strong:
        return None
    return {"hedges": hedges, "strong_markers": strong}


def _inherited_claim_strength_advisories(
    before_claims: Sequence[dict[str, object]],
    after_claims: Sequence[dict[str, object]],
) -> list[Diagnostic]:
    before_budget = Counter(
        re.sub(r"\s+", " ", str(claim["text"])).strip()
        for claim in before_claims
        if _claim_strength_tension(str(claim["text"])) is not None
    )
    advisories: list[Diagnostic] = []
    for claim in after_claims:
        text = re.sub(r"\s+", " ", str(claim["text"])).strip()
        tension = _claim_strength_tension(text)
        if tension is None or before_budget[text] <= 0:
            continue
        before_budget[text] -= 1
        advisories.append(
            Diagnostic(
                code="SPEECH_ACT_INHERITED_CLAIM_STRENGTH_TENSION",
                severity="advisory",
                message=(
                    "The source already combines hedging and a strong claim marker; "
                    "manual semantic review may be useful."
                ),
                details={
                    "inherited": True,
                    "source_occurrences": tension,
                    "rewrite_occurrences": tension,
                    "claim_id": claim["id"],
                    "claim_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "claim_context": text[:240],
                    "automatic_decision": "NONE",
                    "semantic_judgment": "NOT_EVALUATED",
                    "blocking": False,
                },
            )
        )
    return advisories


def _matched_patterns(text: str, patterns: Sequence[str]) -> list[str]:
    matches: list[str] = []
    for raw_pattern in patterns:
        match = re.search(raw_pattern, text)
        if match:
            matches.append(match.group(0)[:240])
    return matches


def _first_person_inventory(text: str) -> dict[str, int]:
    """Count only explicit first-person references likely to change author voice."""
    singular = re.findall(r"(?<![自他本])我(?!们)", text)
    plural = re.findall(r"我们", text)
    return {"singular": len(singular), "plural": len(plural)}


def _first_person_introduction_diagnostic(
    before: str,
    after: str,
    *,
    severity: str,
) -> Diagnostic | None:
    before_counts = _first_person_inventory(before)
    after_counts = _first_person_inventory(after)
    added = {
        key: after_counts[key] - before_counts[key]
        for key in before_counts
        if after_counts[key] > before_counts[key]
    }
    if not added:
        return None
    return Diagnostic(
        code="SPEECH_ACT_FIRST_PERSON_REFERENCE_INTRODUCED",
        severity=severity,
        message=(
            "The rewrite introduces additional singular or plural first-person references; "
            "preserve the source speaker stance unless the change is explicitly reviewed."
        ),
        details={
            "source_counts": before_counts,
            "rewrite_counts": after_counts,
            "added_counts": added,
            "required_action": "PRESERVE_SOURCE_SPEAKER_STANCE_OR_REVIEW",
            "semantic_judgment": "NOT_EVALUATED",
        },
    )


EDITORIAL_SCOPE_MARKERS = ("正文里", "正文中", "文中")
EDITORIAL_SCOPE_ACTION_RE = re.compile(
    r"(?:要|需|需要|应当|应该|必须)[^。！？!?；;\n]{0,96}"
    r"(?:保留|呈现|写成|说明|报告|包括)"
)


def _editorial_scope_drop_diagnostic(
    before: str,
    after: str,
    *,
    severity: str,
) -> Diagnostic | None:
    """Flag a narrow edit that drops where an editorial action must occur."""
    source_spans: list[str] = []
    retained_actions: list[str] = []
    after_sentences = [
        str(item["text"])
        for item in _segment_spans(after, r"[。！？!?；;\n]+", "E")
    ]
    for item in _segment_spans(before, r"[。！？!?；;\n]+", "E"):
        sentence = str(item["text"])
        action = EDITORIAL_SCOPE_ACTION_RE.search(sentence)
        if action is None:
            continue
        for marker in EDITORIAL_SCOPE_MARKERS:
            marker_start = sentence.find(marker)
            if marker_start < 0:
                continue
            without_scope = (
                sentence[:marker_start]
                + sentence[marker_start + len(marker) :]
            )
            # This is intentionally a narrow detector: the corresponding
            # sentence must survive verbatim except for the location marker.
            # Broader paraphrases stay outside the deterministic claim surface.
            if without_scope in after_sentences:
                source_spans.append(sentence[:240])
                retained_actions.append(action.group(0)[:240])
                break
    if not source_spans:
        return None
    return Diagnostic(
        code="SPEECH_ACT_EDITORIAL_SCOPE_DROPPED",
        severity=severity,
        message=(
            "The rewrite removes an explicit document-location scope while retaining "
            "the corresponding editorial action."
        ),
        details={
            "source_scoped_directives": source_spans[:8],
            "retained_editorial_actions": retained_actions[:8],
            "removed_scope_markers": [
                marker
                for marker in EDITORIAL_SCOPE_MARKERS
                if marker in before and marker not in after
            ],
            "required_action": "PRESERVE_OR_EXPLICITLY_RELOCATE_EDITORIAL_SCOPE",
            "semantic_judgment": "NOT_EVALUATED",
            "detector_scope": "VERBATIM_RETAINED_EDITORIAL_ACTION_ONLY",
        },
    )


def _polarity_anchors(sentence: str) -> set[str]:
    stripped = POLARITY_ANCHOR_STRIP_PATTERN.sub(" ", sentence)
    anchors: set[str] = set()
    for run in re.findall(r"[\u3400-\u9fff]+", stripped):
        for size in (2, 3, 4):
            for index in range(max(0, len(run) - size + 1)):
                value = run[index : index + size]
                if value not in POLARITY_ANCHOR_STOP:
                    anchors.add(value)
    return anchors


def _direct_polarity_spans(
    text: str,
    *,
    side: str,
    pattern: re.Pattern[str],
) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    for sentence in _segment_spans(text, r"[。！？!?；;\n]+", "P"):
        sentence_text = str(sentence["text"])
        match = pattern.search(sentence_text)
        if match is None:
            continue
        absolute_start = int(sentence["start"]) + match.start()
        line, column = _line_column(text, absolute_start)
        spans.append(
            {
                "side": side,
                "sentence_id": sentence["id"],
                "line": line,
                "column": column,
                "marker": match.group(0)[:80],
                "sentence_context": re.sub(r"\s+", " ", sentence_text).strip()[:240],
                "anchors": sorted(_polarity_anchors(sentence_text)),
            }
        )
    return spans


def _source_polarity_tension_diagnostic(
    before: str,
    after: str,
    *,
    severity: str,
) -> Diagnostic | None:
    source_positive = _direct_polarity_spans(
        before,
        side="before",
        pattern=DIRECT_PERMISSION_PATTERN,
    )
    source_negative = _direct_polarity_spans(
        before,
        side="before",
        pattern=DIRECT_PROHIBITION_PATTERN,
    )
    if not source_positive or not source_negative:
        return None

    paired_anchors: set[str] = set()
    paired_positive: list[dict[str, object]] = []
    paired_negative: list[dict[str, object]] = []
    for positive in source_positive:
        positive_anchors = set(positive["anchors"])
        for negative in source_negative:
            shared = positive_anchors & set(negative["anchors"])
            if not shared:
                continue
            paired_anchors.update(shared)
            if positive not in paired_positive:
                paired_positive.append(positive)
            if negative not in paired_negative:
                paired_negative.append(negative)
    if not paired_anchors:
        return None

    rewrite_positive_all = _direct_polarity_spans(
        after,
        side="after",
        pattern=DIRECT_PERMISSION_PATTERN,
    )
    rewrite_negative_all = _direct_polarity_spans(
        after,
        side="after",
        pattern=DIRECT_PROHIBITION_PATTERN,
    )

    def shares_source_anchor(item: dict[str, object]) -> bool:
        return bool(set(item["anchors"]) & paired_anchors)

    rewrite_positive = [item for item in rewrite_positive_all if shares_source_anchor(item)]
    rewrite_negative = [item for item in rewrite_negative_all if shares_source_anchor(item)]
    if bool(rewrite_positive) == bool(rewrite_negative):
        return None

    # Prefer the longest anchors so details stay useful without presenting every
    # overlapping character n-gram as independent evidence.
    longest_anchors = [
        anchor
        for anchor in sorted(paired_anchors, key=lambda item: (-len(item), item))
        if not any(anchor in prior for prior in paired_anchors if len(prior) > len(anchor))
    ][:12]
    return Diagnostic(
        code="SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
        severity=severity,
        message=(
            "The source contains lexically anchored direct permission and prohibition "
            "spans, but the rewrite preserves only one surface polarity; preserve both "
            "and escalate instead of choosing a domain claim."
        ),
        details={
            "shared_anchors": longest_anchors,
            "source_positive_spans": paired_positive,
            "source_negative_spans": paired_negative,
            "rewrite_positive_spans": rewrite_positive,
            "rewrite_negative_spans": rewrite_negative,
            "required_action": "PRESERVE_BOTH_AND_ESCALATE",
            "academic_correctness": "NOT_EVALUATED",
            "detector_scope": "LEXICALLY_ANCHORED_DIRECT_PERMISSION_POLARITY_ONLY",
        },
    )


def _semantic_transition_diagnostics(
    before: str,
    after: str,
    *,
    severity: str,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for code, message, before_patterns, after_patterns in SEMANTIC_TRANSITION_RULES:
        before_trigger = _matched_patterns(before, before_patterns)
        after_predicate = _matched_patterns(after, after_patterns)
        source_predicate = _matched_patterns(before, after_patterns)
        if not before_trigger or not after_predicate or source_predicate:
            continue
        diagnostics.append(
            Diagnostic(
                code=code,
                severity=severity,
                message=message,
                details={
                    "source_triggers": before_trigger,
                    "rewrite_predicates": after_predicate,
                    "source_contains_rewrite_predicate": False,
                    "semantic_judgment": "NOT_EVALUATED",
                    "required_action": "PRESERVE_SOURCE_PREDICATE_AND_STATUS",
                },
            )
        )

    hedge_count = sum(marker in before for marker in HEDGE_MARKERS)
    source_degree_claims = [match.group(0) for match in DEGREE_CLAIM_PATTERN.finditer(before)]
    rewrite_degree_claims = [match.group(0) for match in DEGREE_CLAIM_PATTERN.finditer(after)]
    if hedge_count >= 2 and rewrite_degree_claims and not source_degree_claims:
        diagnostics.append(
            Diagnostic(
                code="SPEECH_ACT_MODALITY_TO_DEGREE",
                severity=severity,
                message="Stacked uncertainty markers were rewritten as a new degree claim.",
                details={
                    "source_hedges": [marker for marker in HEDGE_MARKERS if marker in before],
                    "rewrite_degree_claims": rewrite_degree_claims[:8],
                    "source_degree_claims": [],
                },
            )
        )
    polarity_diagnostic = _source_polarity_tension_diagnostic(
        before,
        after,
        severity=severity,
    )
    if polarity_diagnostic is not None:
        diagnostics.append(polarity_diagnostic)
    person_diagnostic = _first_person_introduction_diagnostic(
        before,
        after,
        severity=severity,
    )
    if person_diagnostic is not None:
        diagnostics.append(person_diagnostic)
    editorial_scope_diagnostic = _editorial_scope_drop_diagnostic(
        before,
        after,
        severity=severity,
    )
    if editorial_scope_diagnostic is not None:
        diagnostics.append(editorial_scope_diagnostic)
    return diagnostics


def _inside_excluded_word(text: str, index: int, marker: str) -> bool:
    for word in MARKER_SPAN_EXCLUSIONS.get(marker, ()):
        first_start = max(0, index - len(word) + 1)
        last_start = min(index, len(text) - len(word))
        for position in range(first_start, last_start + 1):
            if (
                text.startswith(word, position)
                and position <= index
                and index + len(marker) <= position + len(word)
            ):
                return True
    return False


def _sequence_details(before: Sequence[str], after: Sequence[str]) -> dict[str, object]:
    before_counter = Counter(before)
    after_counter = Counter(after)
    first_difference = None
    for index, pair in enumerate(zip(before, after)):
        if pair[0] != pair[1]:
            first_difference = index
            break
    if first_difference is None and len(before) != len(after):
        first_difference = min(len(before), len(after))

    def limited(counter: Counter[str]) -> list[dict[str, object]]:
        return [
            {"value": value[:240], "count": count}
            for value, count in counter.most_common(8)
            if count > 0
        ]

    return {
        "before_count": len(before),
        "after_count": len(after),
        "first_difference": first_difference,
        "removed": limited(before_counter - after_counter),
        "added": limited(after_counter - before_counter),
    }


def normalize_protected_terms(terms: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        term = raw.strip()
        if not term:
            raise ValueError("protected term must not be empty")
        if term not in seen:
            seen.add(term)
            normalized.append(term)
    return normalized


def _term_evidence(terms: Sequence[str]) -> dict[str, object]:
    raw = json.dumps(list(terms), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "status": "CHECKED" if terms else "NOT_PROVIDED",
        "count": len(terms),
        "sha256": hashlib.sha256(raw).hexdigest() if terms else None,
    }


def _term_occurrences(text: str, terms: Sequence[str]) -> list[str]:
    occurrences: list[tuple[int, str]] = []
    for term in terms:
        cursor = 0
        while True:
            position = text.find(term, cursor)
            if position < 0:
                break
            occurrences.append((position, term))
            cursor = position + len(term)
    return [term for _, term in sorted(occurrences)]


def _compare_sequence(
    result: CheckResult,
    code: str,
    label: str,
    before: Sequence[str],
    after: Sequence[str],
) -> None:
    if list(before) == list(after):
        return
    result.errors.append(
        Diagnostic(
            code=code,
            severity="error",
            message=f"{label} changed in count, content, or order.",
            details=_sequence_details(before, after),
        )
    )


def _prepare(text: str, document_format: str) -> tuple[str, list[str], list[tuple[int, int]]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if document_format == "tex":
        normalized = strip_tex_comments(normalized)
    code, ranges = _code_spans(normalized)
    return normalized, code, ranges


def check_documents(
    before: str,
    after: str,
    *,
    document_format: str = "markdown",
    protect_quotes: bool = True,
    strict_speech_acts: bool = False,
    protected_terms: Sequence[str] = (),
    fragment_mode: bool = False,
    editable_style_wrappers: Sequence[str] = (),
) -> CheckResult:
    """Check deterministic preservation invariants for a style-only rewrite."""
    if document_format not in {"markdown", "tex"}:
        raise ValueError("document_format must be 'markdown' or 'tex'")

    terms = normalize_protected_terms(protected_terms)
    result = CheckResult(
        evidence={
            "protected_terms": _term_evidence(terms),
            "document_scope": "FRAGMENT" if fragment_mode else "DOCUMENT",
        }
    )
    if terms:
        _compare_sequence(
            result,
            "PROTECTED_TERM_CHANGED",
            "Explicitly supplied protected terms",
            _term_occurrences(before, terms),
            _term_occurrences(after, terms),
        )
    _compare_sequence(
        result,
        "GARBLED_TEXT_CHANGED",
        "Replacement characters or obvious mojibake spans",
        _garbled_spans(before),
        _garbled_spans(after),
    )
    if document_format == "tex":
        _compare_sequence(
            result,
            "TEX_COMMENT_CHANGED",
            "TeX comments or line-continuation percent markers",
            _tex_comment_spans(before),
            _tex_comment_spans(after),
        )
    before_text, before_code, before_code_ranges = _prepare(before, document_format)
    after_text, after_code, after_code_ranges = _prepare(after, document_format)
    # Compare protected code and mathematics from the original source, not from
    # the normalized/comment-stripped analysis view.  TeX treats line endings
    # and trailing whitespace inside verbatim-like spans as source data.
    before_exact_code, before_exact_code_ranges = _code_spans(before, exact=True)
    after_exact_code, after_exact_code_ranges = _code_spans(after, exact=True)

    if document_format == "tex":
        before_problems = lexical._tex_protection_problems(before, "tex")
        after_problems = lexical._tex_protection_problems(after, "tex")
        if before_problems or after_problems:
            result.warnings.append(
                Diagnostic(
                    code="TEX_PROTECTION_PARSE_REVIEW",
                    severity="warning",
                    message=(
                        "Unclosed TeX verbatim or code syntax prevents complete "
                        "protection verification."
                    ),
                    details={
                        "before": before_problems[:20],
                        "after": after_problems[:20],
                    },
                )
            )

    _compare_sequence(
        result,
        "PROTECTED_CODE_CHANGED",
        "Code spans or fences",
        before_exact_code,
        after_exact_code,
    )

    before_formal = _extract_environment_spans(before_text, FORMAL_STATEMENT_ENVIRONMENTS)
    after_formal = _extract_environment_spans(after_text, FORMAL_STATEMENT_ENVIRONMENTS)
    _compare_sequence(
        result,
        "PROTECTED_FORMAL_STATEMENT_CHANGED",
        "Exam prompts or formal statement environments",
        before_formal,
        after_formal,
    )

    before_exact_math = _math_spans(
        before,
        before_exact_code_ranges,
        exact=True,
        tex_comments=document_format == "tex",
    )
    after_exact_math = _math_spans(
        after,
        after_exact_code_ranges,
        exact=True,
        tex_comments=document_format == "tex",
    )
    _compare_sequence(
        result,
        "PROTECTED_MATH_CHANGED",
        "Math spans or environments",
        before_exact_math,
        after_exact_math,
    )

    # These normalized spans are deliberately separate: subsequent speech-act,
    # command and brace checks need coordinates in the analysis view, whereas
    # the two hard protection comparisons above must retain raw formatting.
    before_math = _math_spans(before_text, before_code_ranges)
    after_math = _math_spans(after_text, after_code_ranges)

    before_math_ranges = _locate_exact_spans(before_text, before_math)
    after_math_ranges = _locate_exact_spans(after_text, after_math)
    before_excluded = sorted(before_code_ranges + before_math_ranges)
    after_excluded = sorted(after_code_ranges + after_math_ranges)

    before_commands = _critical_commands(
        before_text,
        before_code_ranges,
        editable_style_wrappers,
    )
    after_commands = _critical_commands(
        after_text,
        after_code_ranges,
        editable_style_wrappers,
    )
    _compare_sequence(
        result,
        "CRITICAL_LATEX_COMMAND_CHANGED",
        "Critical LaTeX commands or arguments",
        before_commands,
        after_commands,
    )

    if protect_quotes:
        before_quotes = _quotation_spans(before_text, before_excluded)
        after_quotes = _quotation_spans(after_text, after_excluded)
        _compare_sequence(
            result,
            "DIRECT_QUOTATION_CHANGED",
            "Direct quotations",
            before_quotes,
            after_quotes,
        )

    before_numbers = _numbers_and_units(before_text, before_code_ranges)
    after_numbers = _numbers_and_units(after_text, after_code_ranges)
    _compare_sequence(
        result,
        "NUMBER_OR_UNIT_CHANGED",
        "Numbers or units",
        before_numbers,
        after_numbers,
    )

    before_events = _environment_events(before_text, before_code_ranges)
    after_events = _environment_events(after_text, after_code_ranges)
    if before_events != after_events:
        result.errors.append(
            Diagnostic(
                code="LATEX_ENVIRONMENT_ORDER_CHANGED",
                severity="error",
                message="LaTeX environment names or order changed.",
                details=_sequence_details(
                    [f"{kind}:{name}" for kind, name in before_events],
                    [f"{kind}:{name}" for kind, name in after_events],
                ),
            )
        )
    before_environment_problems = _validate_environment_nesting(before_events)
    after_environment_problems = _validate_environment_nesting(after_events)
    if fragment_mode:
        if before_environment_problems != after_environment_problems:
            result.errors.append(
                Diagnostic(
                    code="LATEX_ENVIRONMENT_FRAGMENT_BALANCE_CHANGED",
                    severity="error",
                    message="LaTeX fragment boundary balance changed.",
                    details={
                        "before": before_environment_problems[:20],
                        "after": after_environment_problems[:20],
                    },
                )
            )
    else:
        for side, problems in (
            ("before", before_environment_problems),
            ("after", after_environment_problems),
        ):
            if problems:
                result.errors.append(
                    Diagnostic(
                        code="LATEX_ENVIRONMENT_UNBALANCED",
                        severity="error",
                        message=f"LaTeX environments are unbalanced in {side} document.",
                        details={"side": side, "problems": problems[:20]},
                    )
                )

    before_brace_problems = _brace_problems(before_text, before_code_ranges)
    after_brace_problems = _brace_problems(after_text, after_code_ranges)
    if fragment_mode:
        if before_brace_problems != after_brace_problems:
            result.errors.append(
                Diagnostic(
                    code="LATEX_BRACE_FRAGMENT_BALANCE_CHANGED",
                    severity="error",
                    message="LaTeX fragment brace balance changed.",
                    details={
                        "before": before_brace_problems[:20],
                        "after": after_brace_problems[:20],
                    },
                )
            )
    else:
        for side, problems in (
            ("before", before_brace_problems),
            ("after", after_brace_problems),
        ):
            if problems:
                result.errors.append(
                    Diagnostic(
                        code="LATEX_BRACES_UNBALANCED",
                        severity="error",
                        message=f"Unescaped braces are unbalanced in {side} document.",
                        details={"side": side, "problems": problems[:20]},
                    )
                )

    before_speech_text, before_speech_protected = _speech_surface(
        before, document_format, protect_quotes
    )
    after_speech_text, after_speech_protected = _speech_surface(
        after, document_format, protect_quotes
    )
    speech_audit, speech_warnings, before_claims, after_claims = _speech_act_audit(
        before_speech_text, after_speech_text
    )
    speech_audit["protection"] = {
        "before_ranges": len(before_speech_protected),
        "after_ranges": len(after_speech_protected),
        "masking": "LENGTH_PRESERVING",
        "line_column_basis": "NORMALIZED_LF_1_BASED_UNICODE_CODEPOINT",
    }
    result.evidence["speech_act_audit"] = speech_audit
    for category, details in speech_warnings:
        severity = "error" if strict_speech_acts else "warning"
        diagnostic = Diagnostic(
            code=f"SPEECH_ACT_{category.upper()}_CHANGED",
            severity=severity,
            message=f"Speech-act markers changed in category '{category}'; review semantic force manually.",
            details=details,
        )
        (result.errors if strict_speech_acts else result.warnings).append(diagnostic)

    result.advisories.extend(
        _inherited_claim_strength_advisories(before_claims, after_claims)
    )

    transition_severity = "error" if strict_speech_acts else "warning"
    for diagnostic in _semantic_transition_diagnostics(
        before_speech_text,
        after_speech_text,
        severity=transition_severity,
    ):
        (result.errors if strict_speech_acts else result.warnings).append(diagnostic)

    return result


def _locate_exact_spans(text: str, spans: Sequence[str]) -> list[tuple[int, int]]:
    """Best-effort locations for already canonicalized spans, used only for masking."""
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for span in spans:
        position = text.find(span, cursor)
        if position < 0:
            # Canonicalization may have removed outer/trailing whitespace.  Searching
            # from the start still masks the meaningful span in ordinary documents.
            position = text.find(span)
        if position >= 0:
            ranges.append((position, position + len(span)))
            cursor = position + len(span)
    return ranges


def _infer_format(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    return "tex" if path.suffix.lower() in {".tex", ".ltx"} else "markdown"


def _text_output(result: CheckResult) -> str:
    term_evidence = result.evidence.get("protected_terms", {})
    lines = [
        f"status: {result.status}",
        f"hard errors: {len(result.errors)}",
        f"warnings: {len(result.warnings)}",
        f"advisories: {len(result.advisories)}",
        f"protected terms: {term_evidence.get('status', 'NOT_PROVIDED')}",
        f"protected term count: {term_evidence.get('count', 0)}",
        f"protected term sha256: {term_evidence.get('sha256') or 'NONE'}",
    ]
    for diagnostic in [*result.errors, *result.warnings, *result.advisories]:
        lines.append(f"[{diagnostic.severity.upper()}] {diagnostic.code}: {diagnostic.message}")
        if diagnostic.details:
            lines.append("  " + json.dumps(diagnostic.details, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check preservation invariants between original and humanized Markdown/TeX."
    )
    parser.add_argument("before", type=Path, help="Original UTF-8 Markdown or TeX file")
    parser.add_argument("after", type=Path, help="Humanized UTF-8 Markdown or TeX file")
    parser.add_argument("--format", choices=("auto", "markdown", "tex"), default="auto")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--allow-quote-edits",
        action="store_true",
        help="Do not protect direct quotations (off by default)",
    )
    parser.add_argument(
        "--strict-speech-acts",
        action="store_true",
        help="Treat changes to negation/modality/focus/definition/reporting markers as hard errors",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help=(
            "Validate a document fragment: unchanged boundary imbalance is allowed, "
            "but any environment or brace-balance drift still fails"
        ),
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        metavar="TERM",
        help="Protect an exact method, material, or glossary term; repeat for multiple terms",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        before = args.before.read_text(encoding="utf-8-sig")
        after = args.after.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    result = check_documents(
        before,
        after,
        document_format=_infer_format(args.before, args.format),
        protect_quotes=not args.allow_quote_edits,
        strict_speech_acts=args.strict_speech_acts,
        protected_terms=args.term,
        fragment_mode=args.fragment,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_text_output(result))
    return 1 if result.hard_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
