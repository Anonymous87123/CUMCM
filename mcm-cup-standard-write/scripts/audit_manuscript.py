#!/usr/bin/env python3
"""Rule-based structural audit for a CUMCM LaTeX manuscript."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SECTION_RULES = {
    "abstract": ("摘要", [r"\\begin\s*\{abstract\}"]),
    "keywords": ("关键词", [r"\\keywords?\s*\{"]),
    "restatement": ("问题重述", [r"问题(?:的)?重述", r"问题背景"]),
    "analysis": ("问题分析", [r"问题分析", r"建模思路"]),
    "assumptions": ("模型假设", [r"模型假设", r"基本假设", r"假设条件"]),
    "symbols": ("符号说明", [r"符号说明", r"符号(?:与|及)定义"]),
    "modeling": ("分问题模型建立与求解", [r"模型(?:的)?(?:建立|构建)", r"模型(?:的)?求解", r"分问题"]),
    "results": ("结果分析", [
        r"结果分析", r"结果与分析", r"求解结果", r"求解与结果",
        r"结果与机制(?:解释|讨论)", r"情景结果与机制讨论", r"结果对照",
    ]),
    "validation": ("模型检验", [
        r"模型检验", r"模型验证", r"误差分析", r"有效性检验",
        r"结果对照", r"定性核验", r"交叉核对", r"鲁棒性检验",
    ]),
    "robustness": ("灵敏度或稳健性分析", [r"灵敏度", r"敏感性", r"稳健性", r"参数扰动"]),
    "evaluation": ("模型评价与改进", [r"模型评价", r"优缺点", r"模型改进", r"改进方案"]),
    "references": ("参考文献", [
        r"\\begin\s*\{thebibliography\}", r"\\bibliography\s*\{",
        r"\\printbibliography\b", r"\\section\*?\s*\{[^}]*参考文献[^}]*\}",
    ]),
    "appendix": ("附录", [r"\\appendix\b", r"\\begin\s*\{appendices\}", r"\\section\*?\s*\{[^}]*附录"]),
}

HEADING_PATTERN = re.compile(
    r"\\(?P<command>section|subsection|subsubsection|paragraph)\*?\s*\{(?P<title>[^{}]*)\}",
    re.I,
)

HEADING_LEVEL = {"section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4}

PROBLEM_HINTS = {
    "A": ["机理", "微分方程", "几何", "物理", "数值求解", "守恒", "误差"],
    "B": ["优化", "目标函数", "约束", "决策变量", "算法", "仿真", "敏感"],
    "C": ["数据", "清洗", "描述统计", "特征", "评价", "预测", "交叉验证"],
}

INPUT_PATTERN = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}", re.I)


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    line: int | None = None
    suggestion: str | None = None


def strip_comments(text: str) -> str:
    cleaned = []
    for line in text.splitlines(keepends=True):
        kept = []
        for index, char in enumerate(line):
            slash_count = 0
            probe = index - 1
            while probe >= 0 and line[probe] == "\\":
                slash_count += 1
                probe -= 1
            if char == "%" and slash_count % 2 == 0:
                if line.endswith("\n"):
                    kept.append("\n")
                break
            kept.append(char)
        cleaned.append("".join(kept))
    return "".join(cleaned)


def read_tex_tree(path: Path, stack: tuple[Path, ...] = ()) -> str:
    """Read a TeX entry file and inline literal input/include targets."""
    resolved = path.resolve()
    if resolved in stack:
        chain = " -> ".join(str(item) for item in (*stack, resolved))
        raise ValueError(f"cyclic TeX input: {chain}")

    source = strip_comments(resolved.read_text(encoding="utf-8-sig"))

    def expand(match: re.Match[str]) -> str:
        target = Path(match.group(1).strip())
        if target.suffix == "":
            target = target.with_suffix(".tex")
        included = (resolved.parent / target).resolve()
        if not included.is_file():
            raise FileNotFoundError(
                f"TeX input not found: {match.group(1).strip()} (from {resolved})"
            )
        return read_tex_tree(included, (*stack, resolved))

    return INPUT_PATTERN.sub(expand, source)


def line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def first_match(text: str, patterns: list[str]) -> re.Match[str] | None:
    matches = [re.search(pattern, text, re.I | re.S) for pattern in patterns]
    return min((m for m in matches if m), key=lambda m: m.start(), default=None)


def structural_section_match(text: str, key: str, patterns: list[str]) -> re.Match[str] | None:
    """Find sections only in TeX structure, not in ordinary prose."""
    if key in {"abstract", "keywords", "references", "appendix"}:
        return first_match(text, patterns)

    matches = []
    for heading in HEADING_PATTERN.finditer(text):
        if any(re.search(pattern, heading.group("title"), re.I) for pattern in patterns):
            matches.append(heading)
    return min(matches, key=lambda match: match.start(), default=None)


def required_sections(text: str) -> list[Finding]:
    findings, positions = [], []
    for key, (label, patterns) in SECTION_RULES.items():
        match = structural_section_match(text, key, patterns)
        if match:
            positions.append((key, match.start()))
        else:
            findings.append(Finding(
                f"MISSING_{key.upper()}", "error", f"缺少“{label}”结构。",
                suggestion=f"补充独立的“{label}”章节或环境，并写入与结果相互对应的内容。",
            ))
    # Class metadata such as \keyword{...} may be declared before the abstract
    # and rendered below it. Its source offset is therefore not a reading-order
    # signal; all substantive manuscript sections remain ordered here.
    expected = [key for key in SECTION_RULES if key != "keywords"]
    observed = [
        key for key, _ in sorted(positions, key=lambda item: item[1])
        if key != "keywords"
    ]
    ranks = [expected.index(key) for key in observed]
    if ranks != sorted(ranks):
        findings.append(Finding(
            "SECTION_ORDER", "warning",
            "主要章节首次出现顺序偏离摘要—重述—分析—假设—符号—建模求解—结果检验—评价—文献—附录链条。",
            suggestion="若因分问题交织而调整顺序，请确认评阅者仍能沿模型链阅读。",
        ))
    return findings


def placeholders(text: str) -> list[Finding]:
    patterns = [r"\bTODO\b", r"\bTBD\b", r"\bXXX+\b", r"待(?:填写|补充|完善|替换|计算|核验)",
                r"此处(?:填写|插入|补充)", r"\?\?\?+", r"\\placeholder\b", r"\[PLACEHOLDER[^]]*\]"]
    findings = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            findings.append(Finding(
                "PLACEHOLDER", "error", f"发现未决占位符：{match.group(0)[:60]}",
                line_at(text, match.start()), "提交前替换为可复算结果、正式文字或删除该占位。",
            ))
    return findings


def environment_blocks(text: str, name: str):
    escaped_name = re.escape(name)
    yield from re.finditer(
        rf"\\begin\s*\{{{escaped_name}\}}(?P<body>.*?)\\end\s*\{{{escaped_name}\}}", text, re.I | re.S
    )


def floats(text: str) -> list[Finding]:
    findings = []
    for name in ("figure", "figure*", "table", "table*", "longtable"):
        for block in environment_blocks(text, name):
            body, line = block.group("body"), line_at(text, block.start())
            caption = re.search(r"\\caption(?:\[[^]]*\])?\s*\{", body)
            caption_title = re.search(
                r"\\caption(?:\[[^]]*\])?\s*\{(?P<title>[^{}]*)\}", body
            )
            label = re.search(r"\\label\s*\{[^}]+\}", body)
            if not caption:
                findings.append(Finding(f"{name.upper()}_CAPTION", "error", f"{name} 环境缺少 caption。", line))
            symbol_table = (
                name in {"table", "table*", "longtable"}
                and caption_title is not None
                and re.search(r"(?:主要)?(?:符号|记号)(?:说明|表)?", caption_title.group("title"))
            )
            if not label and not symbol_table:
                findings.append(Finding(f"{name.upper()}_LABEL", "error", f"{name} 环境缺少 label。", line))
            if caption and label and label.start() < caption.start():
                findings.append(Finding(
                    f"{name.upper()}_LABEL_ORDER", "warning", f"{name} 的 label 位于 caption 之前。", line,
                    "把 \\label 紧跟在 \\caption 之后。",
                ))
    return findings


def _bibliography_declarations(text: str) -> list[tuple[str, int]]:
    declarations: list[tuple[str, int]] = []
    for match in re.finditer(
        r"\\addbibresource(?:\[[^]]*\])?\s*\{([^{}]+)\}", text, re.I
    ):
        declarations.append((match.group(1).strip(), match.start()))
    for match in re.finditer(r"\\bibliography\s*\{([^{}]+)\}", text, re.I):
        declarations.extend(
            (part.strip(), match.start())
            for part in match.group(1).split(",") if part.strip()
        )
    return declarations


def _resolve_bibliography(
    declared: str,
    main_path: Path,
    resource_roots: tuple[Path, ...],
) -> Path | None:
    relative = Path(declared)
    if relative.suffix == "":
        relative = relative.with_suffix(".bib")
    if relative.is_absolute():
        return relative.resolve() if relative.is_file() else None
    roots = (main_path.resolve().parent, *resource_roots)
    for root in roots:
        candidate = (root.resolve() / relative).resolve()
        if candidate.is_file():
            return candidate
    return None


def cross_references(
    text: str,
    main_path: Path,
    resource_roots: tuple[Path, ...] = (),
) -> list[Finding]:
    findings = []
    label_list = re.findall(r"\\label\s*\{([^}]+)\}", text)
    labels = set(label_list)
    for label in sorted({item for item in label_list if label_list.count(item) > 1}):
        match = re.search(rf"\\label\s*\{{{re.escape(label)}\}}", text)
        findings.append(Finding(
            "DUPLICATE_LABEL", "error", f"标签“{label}”被重复定义。",
            line_at(text, match.start()) if match else None,
            "为每个图、表和公式分配唯一标签，并同步更新引用。",
        ))
    refs = set()
    for match in re.finditer(r"\\(?:ref|eqref|autoref|cref|Cref)\s*\{([^}]+)\}", text):
        refs.update(part.strip() for part in match.group(1).split(",") if part.strip())
    for ref in sorted(refs - labels):
        match = re.search(rf"\\(?:ref|eqref|autoref|cref|Cref)\s*\{{[^}}]*{re.escape(ref)}", text)
        findings.append(Finding("UNDEFINED_LABEL", "error", f"引用了未定义标签“{ref}”。",
                                line_at(text, match.start()) if match else None))
    citations = set()
    citation_lines: dict[str, int] = {}
    for match in re.finditer(r"\\cite\w*\s*\{([^}]+)\}", text):
        for part in match.group(1).split(","):
            key = part.strip()
            if key and key != "*":
                citations.add(key)
                citation_lines.setdefault(key, line_at(text, match.start()))

    declarations = _bibliography_declarations(text)
    bibliography_keys: set[str] = set()
    for declared, offset in declarations:
        resource = _resolve_bibliography(declared, main_path, resource_roots)
        if resource is None:
            findings.append(Finding(
                "BIB_RESOURCE_NOT_FOUND", "error",
                f"参考文献资源“{declared}”无法从主文件目录或显式资源根解析。",
                line_at(text, offset),
                "把 .bib 纳入候选资源树，或用 --resource-root 指向已冻结并参与编译的资源根。",
            ))
            continue
        bib_text = strip_comments(resource.read_text(encoding="utf-8-sig"))
        bibliography_keys.update(
            match.group(1).strip()
            for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib_text, re.I)
        )

    if declarations:
        for citation in sorted(citations - bibliography_keys):
            findings.append(Finding(
                "UNDEFINED_CITATION", "error",
                f"引用键“{citation}”没有出现在已解析的 .bib 资源中。",
                citation_lines.get(citation),
            ))
    elif citations:
        bibitems = set(re.findall(r"\\bibitem(?:\[[^]]*\])?\s*\{([^}]+)\}", text))
        for citation in sorted(citations - bibitems):
            findings.append(Finding(
                "UNDEFINED_CITATION", "error", f"引用键“{citation}”没有对应 bibitem 或 .bib 声明。",
                citation_lines.get(citation),
            ))
    return findings


def section_body(text: str, title: str) -> str:
    heading = re.search(
        rf"\\(?P<command>section|subsection|subsubsection)\*?\s*\{{[^}}]*{title}[^}}]*\}}",
        text,
        re.I,
    )
    if not heading:
        return ""
    current_level = HEADING_LEVEL[heading.group("command").lower()]
    end = len(text)
    for following in HEADING_PATTERN.finditer(text, heading.end()):
        following_level = HEADING_LEVEL[following.group("command").lower()]
        if following_level <= current_level:
            end = following.start()
            break
    return text[heading.end():end]


AI_CLICHE_PATTERNS = [
    ("综合性/系统性框架", r"综合(?:性|化)?(?:框架|体系)|系统性(?:框架|体系)|多维(?:度)?(?:框架|体系)"),
    ("充分利用/深入挖掘", r"充分(?:利用|挖掘)|深入挖掘(?:数据|信息|规律)"),
    ("显著提升但未给证据", r"显著(?:提升|提高|改善)(?:了)?(?:性能|效果|精度|效率)"),
    ("无边界鲁棒性/普适性", r"(?:较强|很强|良好)(?:的)?(?:鲁棒性|普适性|泛化性)|(?:鲁棒性|普适性|泛化性)(?:较强|很强|良好)"),
    ("空泛验证/证明", r"验证(?:了)?模型(?:的)?(?:有效性|合理性)|证明(?:了)?模型(?:的)?(?:有效性|合理性)"),
    ("空泛意义", r"为(?:后续|未来).{0,18}(?:奠定|打下)(?:坚实)?基础|具有重要意义"),
    ("先进/智能算法", r"采用(?:先进|智能)(?:的)?算法(?:进行)?求解"),
    ("从而提高精度/效率", r"从而(?:显著)?(?:提高|提升)(?:了)?(?:精度|效率|性能)"),
]


def ai_cliche_signals(text: str) -> list[Finding]:
    """Warn when a stock phrase has no nearby object, evidence, or boundary."""
    findings = []
    evidence = (
        r"\d|%|表|图|式|基线|样本|字段|变量|对象|条件|范围|约束|误差|"
        r"指标|回代|复算|交叉验证|MAE|MSE|RMSE|R\^2|区间|步长|单位|"
        r"保留|舍弃|仅在|不支持|上界|下界"
    )
    for label, pattern in AI_CLICHE_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            # Do not let a later paragraph's evidence launder an empty sentence.
            left_breaks = [text.rfind(mark, 0, match.start()) for mark in "。！？；\n"]
            right_breaks = [
                index for mark in "。！？；\n"
                for index in [text.find(mark, match.end())]
                if index >= 0
            ]
            start = max(left_breaks, default=-1) + 1
            end = min(right_breaks, default=len(text))
            context = text[start:end]
            meta_start = max(
                (text.rfind(mark, 0, match.start()) for mark in "。！？；"),
                default=-1,
            ) + 1
            meta_right = [
                index for mark in "。！？；"
                for index in [text.find(mark, match.end())]
                if index >= 0
            ]
            meta_end = min(meta_right, default=len(text))
            meta_context = text[meta_start:meta_end]
            if re.search(
                r"AI|套语|惯用语|空泛|禁用|反制|不写|不用|不得用|不能写|"
                r"避免|删除|改写|比直接写|示例|反例",
                meta_context,
                re.I,
            ):
                continue
            if re.search(evidence, context, re.I):
                continue
            findings.append(Finding(
                "AI_CLICHE_WITHOUT_EVIDENCE",
                "warning",
                f"发现可能空泛的 AI 套语“{match.group(0)}”（{label}），附近未见对象、依据、数值或结论边界。",
                line_at(text, match.start()),
                "改写为具体对象、依据（式/图/表/字段/基线）、实际动作、数值比较和适用范围；若删去后信息不损失则直接删除。",
            ))
    return findings


MODEL_INTRO_PATTERN = re.compile(
    r"(?:采用|选用|选择|建立|构建|引入|改用|使用)(?:了)?"
    r"[^。！？；\n]{0,45}?(?:模型|算法|方法|回归|规划|网络|求解器)",
    re.I,
)

LOCAL_REASONING_EVIDENCE = re.compile(
    r"图|表|式|附件|数据|字段|散点|分布|周期|峰值|残差|误差|边界|上界|下界|"
    r"约束|变量|样本|状态|维数|节点|路径|网格|计算量|函数评估|量纲|守恒|"
    r"非线性|整数|连续|单调|缺失|不足|不能|难以|冲突|超限|试算|比较|回代|"
    r"由于|因为|发现|显示|表明|可见|满足|违反|导致|仅有|达到",
    re.I,
)

QUESTION_HEADING_PATTERN = re.compile(
    r"\\(?P<command>section|subsection|subsubsection)\*?\s*\{(?P<title>[^{}]*)\}",
    re.I,
)

QUESTION_TITLE_PATTERN = re.compile(
    r"(?:问题\s*[（(]?\s*(?P<problem>[一二三四五六七八九十百]+|\d+)\s*[）)]?"
    r"|第\s*(?P<ordinal>[一二三四五六七八九十百]+|\d+)\s*问"
    r"|(?<![A-Za-z])Q\s*(?P<q>\d+))",
    re.I,
)

QUESTION_LEVEL = {"section": 1, "subsection": 2, "subsubsection": 3}
CN_QUESTION_NUMBER = {
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
}

# This pattern also catches a method named in a nested heading, for example
# ``\subsubsection{基于 Logistic 模型的拟合}``.  A generic heading such as
# “模型建立与求解” is deliberately excluded.
BASED_METHOD_PATTERN = re.compile(
    r"(?:基于|采用|选用|选择|使用|引入|改用|借助)"
    r"[^{}。！？；\n]{1,50}?(?:模型|算法|方法|回归|规划|网络|求解器)",
    re.I,
)

# Evidence here is intentionally stricter than LOCAL_REASONING_EVIDENCE.  A
# bare “由于问题复杂” must not satisfy the per-question check.  The check
# accepts a question-specific observation, an inherited interface, a
# mathematical landing, a boundary/failed trial, or an explicit TeX result.
QUESTION_LOCAL_BASIS = re.compile(
    r"图\s*[\\~]*\s*(?:ref)?|表\s*[\\~]*\s*(?:ref)?|式\s*[（(]?\s*\d|附件|字段|"
    r"散点|分布|周期|峰值|残差|误差|零值|缺失值|不正态|相关系数|"
    r"边界|上界|下界|阈值|量纲|守恒|平衡位置|多根|物理解|"
    r"目标函数|约束式|约束条件|决策变量|状态变量|整数变量|连续变量|"
    r"节点|路径|网格|反馈环|决策点|维数|计算量|函数评估|"
    r"试算|粗搜|细搜|枚举|遍历|回代|反证|反例|"
    r"(?:前一问|上一问|前问|问题\s*[一二三四五六七八九十百\d]+|"
    r"沿用|承接|继续使用)[^。！？；\n]{0,45}"
    r"(?:函数|变量|参数|状态|约束|输出|候选集?|轨迹|路径|位置|速度|"
    r"成本|利润|库存|预测量?|矩阵|递推|判定|核算|目标值)|"
    r"保持[^。！？；\n]{0,30}不变",
    re.I,
)

QUESTION_RELATION_BASIS = re.compile(
    r"(?:根据|由|从|当|若|因|由于)[^。！？；\n]{0,90}"
    r"(?:固定|相等|超过|小于|大于|不超过|不少于|仅|不能|必须|存在|"
    r"缺失|呈现|增加|下降|波动|周期|相关|线性|非线性|单调|"
    r"多根|反馈|层级|先后|滞后|饱和|上限|下限)",
    re.I,
)

TEX_LOCAL_BASIS = re.compile(
    r"\\(?:ref|eqref)\s*\{|\\begin\s*\{(?:equation|align|gather)|"
    r"\\\[|\$[^$\n]{3,}\$",
    re.I,
)


def visible_prose(text: str) -> str:
    text = re.sub(r"\\(?:begin|end)\s*\{[^}]+\}", " ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection)\*?\s*\{[^}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
    return re.sub(r"[\s{}$&_^~]+", "", text)


def prose_paragraphs(text: str) -> list[tuple[int, str]]:
    # TeX authors do not always leave a blank line after headings. Treat a
    # heading as a prose boundary so style checks do not collapse the whole
    # manuscript into one paragraph.
    document_start = re.search(r"\\begin\s*\{document\}", text, re.I)
    if document_start:
        prefix = text[:document_start.end()]
        text = re.sub(r"[^\n]", " ", prefix) + text[document_start.end():]

    boundary_pattern = re.compile(
        r"\\(?:section|subsection|subsubsection|paragraph)\*?\s*\{[^{}]*\}|"
        r"\\(?:begin|end)\s*\{(?:abstract|document|thebibliography)\}|"
        r"\\appendix\b",
        re.I,
    )

    def preserve_offset_boundary(match: re.Match[str]) -> str:
        original = match.group(0)
        if len(original) < 2:
            return original
        return "\n\n" + " " * (len(original) - 2)

    text = boundary_pattern.sub(preserve_offset_boundary, text)
    paragraphs = []
    for block in re.finditer(r"(?:\A|\n\s*\n)(?P<body>.*?)(?=\n\s*\n|\Z)", text, re.S):
        body = block.group("body").strip()
        if not body or re.search(
            r"\\begin\s*\{(?:table|longtable|figure|equation|align|verbatim|lstlisting)",
            body,
            re.I,
        ):
            continue
        cleaned = visible_prose(body)
        if len(cleaned) >= 25:
            paragraphs.append((block.start("body"), cleaned))
    return paragraphs


def normalise_question_id(raw: str) -> str:
    raw = raw.strip()
    if raw.isdigit():
        return str(int(raw))
    if raw in CN_QUESTION_NUMBER:
        return CN_QUESTION_NUMBER[raw]
    if "十" in raw:
        tens, ones = raw.split("十", 1)
        tens_value = 1 if tens == "" else int(CN_QUESTION_NUMBER.get(tens, "0"))
        ones_value = 0 if ones == "" else int(CN_QUESTION_NUMBER.get(ones, "0"))
        value = tens_value * 10 + ones_value
        if value:
            return str(value)
    return raw


def question_sections(text: str) -> list[tuple[str, str, int, int, str]]:
    """Return numbered-question heading blocks without swallowing the next peer."""
    headings = list(QUESTION_HEADING_PATTERN.finditer(text))
    sections = []
    for index, heading in enumerate(headings):
        number = QUESTION_TITLE_PATTERN.search(heading.group("title"))
        if not number:
            continue
        raw_id = next(group for group in number.groups() if group is not None)
        question_id = normalise_question_id(raw_id)
        level = QUESTION_LEVEL[heading.group("command").lower()]
        end = len(text)
        for following in headings[index + 1:]:
            following_level = QUESTION_LEVEL[following.group("command").lower()]
            if following_level <= level:
                end = following.start()
                break
        sections.append((
            question_id,
            heading.group("title"),
            heading.start(),
            heading.end(),
            text[heading.end():end],
        ))
    return sections


def first_method_introduction(title: str, body: str) -> tuple[int, str] | None:
    """Locate the first explicit method/model introduction in one question block."""
    title_match = BASED_METHOD_PATTERN.search(title)
    candidates = []
    if title_match:
        candidates.append((-1, title_match.group(0)))
    for pattern in (MODEL_INTRO_PATTERN, BASED_METHOD_PATTERN):
        match = pattern.search(body)
        if match:
            candidates.append((match.start(), match.group(0)))
    return min(candidates, key=lambda item: item[0]) if candidates else None


def has_question_local_basis(prefix: str) -> bool:
    # Keep the nearby question-specific material.  Earlier fragments of the
    # same numbered question are included, while a general “问题分析” paragraph
    # with no numbered heading is not.
    nearby = prefix[-2400:]
    return bool(
        QUESTION_LOCAL_BASIS.search(nearby)
        or QUESTION_RELATION_BASIS.search(nearby)
        or TEX_LOCAL_BASIS.search(nearby)
    )


def question_model_introduction_signals(text: str) -> list[Finding]:
    """Check the first explicit method name for each numbered question.

    This is not a request for hidden chain-of-thought and it does not require a
    fixed model-comparison paragraph.  It only checks whether the manuscript
    has left a public, verifiable bridge from this question's material to its
    first named method.
    """
    grouped: dict[str, list[tuple[str, int, int, str]]] = {}
    for question_id, title, heading_start, content_start, body in question_sections(text):
        grouped.setdefault(question_id, []).append(
            (title, heading_start, content_start, body)
        )

    findings = []
    for question_id, blocks in grouped.items():
        previous_question_material = []
        for title, heading_start, content_start, body in blocks:
            introduction = first_method_introduction(title, body)
            if introduction is None:
                previous_question_material.append(body)
                continue

            relative, wording = introduction
            current_prefix = "" if relative < 0 else body[:relative]
            prefix = "\n".join((*previous_question_material, current_prefix))
            if not has_question_local_basis(prefix):
                absolute = heading_start if relative < 0 else content_start + relative
                findings.append(Finding(
                    "QUESTION_MODEL_WITHOUT_LOCAL_BASIS",
                    "warning",
                    f"问题{question_id}首次出现方法“{visible_prose(wording)[:60]}”前，未见本问特有的题面关系、前问接口、数据读数、边界、试算或数学结构。",
                    line_at(text, absolute),
                    "不要补统一的选型段：若题面关系直接决定数学入口，就先把关系列出来；若沿用前问，就写清保留的接口和本问新增量；若确有比较，只保留实际做过的比较。",
                ))
            break
    return findings


def reasoning_narrative_signals(text: str) -> list[Finding]:
    """Warn about missing selection grounds and exposed internal reasoning scaffolds."""
    findings = []
    analysis = section_body(text, r"(?:问题分析|建模思路)")
    analysis_visible = visible_prose(analysis)
    if analysis and len(analysis_visible) < 160:
        findings.append(Finding(
            "THIN_PROBLEM_ANALYSIS",
            "warning",
            "问题分析正文较短，可能只给模型结论而没有呈现影响选型的题面、数据、边界或接口。",
            suggestion=(
                "补充真正改变变量、近似、模型或算法的局部依据；不要按“困难—基线—不足—候选—选择”"
                "补齐固定链条，也不要虚构未运行的比较。"
            ),
        ))

    if analysis:
        for match in MODEL_INTRO_PATTERN.finditer(analysis):
            sentence_start = max(
                analysis.rfind(mark, 0, match.start()) for mark in "。！？；\n"
            ) + 1
            context_start = max(sentence_start, match.start() - 240)
            before = analysis[context_start:match.start()]
            if not LOCAL_REASONING_EVIDENCE.search(before):
                absolute = text.find(analysis) + match.start()
                findings.append(Finding(
                    "MODEL_SELECTION_WITHOUT_LOCAL_BASIS",
                    "warning",
                    f"问题分析中模型或方法“{match.group(0)[:60]}”出现前，当前判断单元未见本题特有的观察、约束、边界、试算或计算负担。",
                    line_at(text, absolute) if absolute >= 0 else None,
                    "从真正触发选择的材料自然引出模型；不必罗列多个候选，也不要用“问题复杂，故采用”补理由。",
                ))
                break

    findings.extend(question_model_introduction_signals(text))

    ledger_headings = []
    ledger_pattern = re.compile(
        r"核心困难|基线(?:模型|方案)?|模型(?:不足|缺陷)|候选(?:模型|方案)|"
        r"选择依据|模型改进|改进模型"
    )
    for heading in re.finditer(
        r"\\(?:section|subsection|subsubsection)\*?\s*\{(?P<title>[^}]*)\}",
        text,
        re.I,
    ):
        if ledger_pattern.search(heading.group("title")):
            ledger_headings.append(heading)
    if len(ledger_headings) >= 3:
        findings.append(Finding(
            "EXPOSED_REASONING_LEDGER",
            "warning",
            "发现三个及以上“基线/不足/候选/选择/改进”式标题，内部判断账本可能被直接写成了正文结构。",
            line_at(text, ledger_headings[0].start()),
            "把判断放回触发它的数据、公式、边界、试算或结果附近；保留自然章节标题和读者所需的局部因果。",
        ))

    paragraphs = prose_paragraphs(text)
    opener_patterns = [
        ("核心困难在于", re.compile(r"^核心困难在于")),
        ("由上述分析可知", re.compile(r"^由上述分析可知")),
        ("考虑到", re.compile(r"^考虑到")),
        ("针对", re.compile(r"^针对")),
        ("为了", re.compile(r"^为了")),
        ("首先", re.compile(r"^首先")),
        ("本问", re.compile(r"^本问")),
    ]
    opener_hits: dict[str, list[int]] = {label: [] for label, _ in opener_patterns}
    fixed_chain_hits = []
    for offset, paragraph in paragraphs:
        for label, pattern in opener_patterns:
            if pattern.search(paragraph):
                opener_hits[label].append(offset)
                break
        if (
            re.search(r"核心困难.{0,80}(?:故|因此).{0,40}先.{0,120}再", paragraph)
            or re.search(r"首先.{0,180}其次.{0,220}(?:再次|最后)", paragraph)
        ):
            fixed_chain_hits.append(offset)

    repeated = [(label, hits) for label, hits in opener_hits.items() if len(hits) >= 4]
    if repeated:
        label, hits = max(repeated, key=lambda item: len(item[1]))
        findings.append(Finding(
            "REPEATED_PARAGRAPH_OPENER",
            "warning",
            f"发现 {len(hits)} 个正文段落以“{label}”起笔，段首节奏可能机械重复。",
            line_at(text, hits[0]),
            "让段落从各自的具体对象、读数、公式、边界或上一段结论起笔；不要只轮换连接词。",
        ))
    if len(fixed_chain_hits) >= 2:
        findings.append(Finding(
            "REPEATED_REASONING_CHAIN",
            "warning",
            "多个段落重复使用“核心困难—先—再”或“首先—其次—最后”的完整推理句架。",
            line_at(text, fixed_chain_hits[0]),
            "保留实际改变路线的局部判断，把内部完整性清单留在草稿区；正文不要求每问复现同一顺序。",
        ))

    if len(paragraphs) >= 6:
        summary_pattern = re.compile(
            r"(?:这|由此)(?:说明|表明|可见)|综上(?:所述)?|因此可见|"
            r"从而(?:说明|表明)|可见该(?:模型|方法|方案)"
        )
        summary_hits = [
            offset for offset, paragraph in paragraphs
            if summary_pattern.search(paragraph[-90:])
        ]
        if len(summary_hits) >= 4 and len(summary_hits) / len(paragraphs) >= 0.25:
            findings.append(Finding(
                "PARAGRAPH_SUMMARY_OVERUSE",
                "warning",
                f"{len(summary_hits)} 个正文段落在末尾使用总结性收束，段落可能被统一修成“做法—结果—这说明”的标准答案。",
                line_at(text, summary_hits[0]),
                "逐段删除不增加新判断的末句；只有紧邻公式、图表或试算确实需要裁决时才保留“说明/表明”。",
            ))

        connector_pattern = re.compile(
            r"首先|其次|再次|最后|此外|同时|进一步|因此|从而|综上|"
            r"值得注意的是|需要指出的是|具体而言|一方面|另一方面"
        )
        connector_counts = [len(connector_pattern.findall(paragraph)) for _, paragraph in paragraphs]
        connector_total = sum(connector_counts)
        connector_heavy = sum(count >= 3 for count in connector_counts)
        if connector_total >= 14 and connector_heavy >= 3:
            first_offset = next(
                offset for (offset, _), count in zip(paragraphs, connector_counts) if count >= 3
            )
            findings.append(Finding(
                "CONNECTOR_SATURATION",
                "warning",
                f"正文共发现 {connector_total} 处显式推进词，其中 {connector_heavy} 个段落含三处以上；逻辑关系可能主要靠连接词而非对象、公式和时间顺序承接。",
                line_at(text, first_offset),
                "先删除能够由相同对象、符号、图表或程序顺序自然承接的连接词；不要用同义词轮换。",
            ))

        triad_pattern = re.compile(
            r"[一-鿿]{1,8}性[、，,]"
            r"[一-鿿]{1,8}性(?:和|与|及|、)"
            r"[一-鿿]{1,8}性"
        )
        triad_hits = [
            (offset, match.group(0))
            for offset, paragraph in paragraphs
            for match in triad_pattern.finditer(paragraph)
        ]
        if len(triad_hits) >= 2:
            findings.append(Finding(
                "ABSTRACT_TRIAD_OVERUSE",
                "warning",
                f"发现 {len(triad_hits)} 处三项抽象“性”评价，可能以排比替代可核对指标。",
                line_at(text, triad_hits[0][0]),
                "保留有证据的一项并给出指标、对象和范围；其余项分别证明或删除，不为句式完整凑成三项。",
            ))
    return findings


def semantic_signals(text: str, problem_type: str) -> list[Finding]:
    findings = []
    result = section_body(
        text,
        r"(?:结果(?:分析|与分析|与机制(?:解释|讨论))|情景结果与机制讨论|求解(?:结果|与结果)|结果对照)",
    )
    if not result:
        result = section_body(text, r"求解结果")
    visible = re.sub(r"\\\w+|\s|[{}]", "", result)
    if result and len(visible) < 80:
        findings.append(Finding(
            "THIN_RESULT_EXPLANATION", "warning",
            "结果分析正文过短，可能只列数值而未解释方向、数量级、约束活跃性或业务含义。",
        ))
    if result and not re.search(r"表明|说明|意味着|原因|由于|因此|相比|误差|满足|约束", result):
        findings.append(Finding(
            "RESULT_WITHOUT_INTERPRETATION", "warning",
            "结果分析未发现解释性信号，需人工确认“数值—机制/决策含义”闭环。",
        ))
    validation = first_match(text, SECTION_RULES["validation"][1])
    if validation and not re.search(
        r"误差|残差|对照|基准|复算|回代|交叉验证|拟合优度|MAE|MSE|RMSE|MAPE|R\^2|置信区间",
        text[validation.start():], re.I,
    ):
        findings.append(Finding(
            "VALIDATION_WITHOUT_METRIC", "warning",
            "模型检验后未发现误差指标、对照、回代或交叉验证证据。",
        ))
    if re.search(r"蒙特卡洛|Monte[ -]?Carlo|随机模拟", text, re.I):
        protocol_signals = {
            "样本数": (
                r"样本(?:量|数)|\bn\s*=\s*\d+|10\s*\^\s*\{?\d+\}?|"
                r"(?:\d+(?:\.\d+)?\s*(?:万|千)?|[一二三四五六七八九十百千万]+)"
                r"\s*次(?:\s*(?:独立)?(?:抽样|模拟|试验|实验|重复|迭代|仿真))?"
            ),
            "独立重复": r"独立重复|重复(?:运行|试验|实验)?|多次运行|rep(?:eat|lication)s?",
            "种子": r"随机种子|种子策略|\bseed\b|rng\s*\(",
            "不确定性区间": r"标准差|方差|分位数|置信区间|置信限|误差条|std\s*\(|quantile|percentile",
        }
        missing = [name for name, pattern in protocol_signals.items()
                   if not re.search(pattern, text, re.I)]
        if missing:
            findings.append(Finding(
                "MONTE_CARLO_PROTOCOL", "warning",
                "随机模拟协议缺少可定位信号：" + "、".join(missing) + "。",
                suggestion="正文、代码和结果表统一样本数，并报告独立重复、种子及标准差/分位数/置信区间；一条随机轨迹只称示例。",
            ))
    if not any(hint.lower() in text.lower() for hint in PROBLEM_HINTS[problem_type]):
        findings.append(Finding(
            "PROBLEM_TYPE_SIGNAL", "warning",
            f"全文未发现明显的 {problem_type} 类题型方法信号，需人工确认选型与题型一致。",
        ))
    return findings


def implementation_signals(text: str) -> list[Finding]:
    findings = []
    checks = [
        (
            "LOGICAL_LENGTH",
            r"\blength\s*\(\s*[^)\n]*(?:==|~=|<=|>=|<|>)",
            "发现用 length 统计逻辑掩码；它返回数组长度，不返回真值个数。",
            "改用 sum(mask)、nnz(mask) 或等价真值计数，并用手算样例核对。",
        ),
        (
            "ZERO_PROBABILITY_TO_INFINITY",
            r"(?im)^[^\n]*(?:find\s*\([^\n]*==\s*0|==\s*0)[^\n]*(?:=\s*(?:inf|Inf)|\binf\b)",
            "发现把零值/零概率改为无穷后继续计算的代码信号。",
            "保留零概率；若用于最短路不可达标记，应使用独立掩码并禁止其进入概率或期望运算。",
        ),
        (
            "DOMINANCE_AGAINST_MAX",
            r">\s*(?:max|nanmax)\s*\(",
            "发现用严格大于 max(...) 判定支配关系的代码信号。",
            "对同一玩家的两个策略按对手每个动作逐列比较，再分别判断严格或弱支配。",
        ),
        (
            "ACCUMULATOR_LITERAL_OVERWRITE",
            r"(?im)^[ \t]*(?P<acc>[A-Za-z_]\w*)\s*=\s*(?P=acc)\s*\+[^;\n]*;\s*"
            r"(?:\n[^\n]*){0,8}?\n[ \t]*(?P=acc)\s*=\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*;",
            "发现累计变量在短距离内被无说明的数字常量覆盖。",
            "删除覆盖并从输入和状态更新重算；若常量是标定值，改用独立命名并记录来源、单位和验证。",
        ),
    ]
    for code, pattern, message, suggestion in checks:
        for match in re.finditer(pattern, text, re.I):
            findings.append(Finding(
                code, "error", message, line_at(text, match.start()), suggestion,
            ))

    warning_checks = [
        (
            "TRAINING_RESUBSTITUTION_METRIC",
            r"(?is)\b(?P<model>[A-Za-z_]\w*)\.fit\s*\(\s*"
            r"(?P<data>[A-Za-z_]\w*)(?:\[[^\]\n]+\])?[^)]*\)"
            r".{0,3000}?(?P=model)\.predict(?:_proba)?\s*\(\s*"
            r"(?P=data)(?:\[[^\]\n]+\])?\s*\)",
            "发现模型在同名数据对象上拟合后又预测/计分的训练集回代信号。",
            "若只用于训练诊断，请明确标为训练指标；预测能力必须在未参与预处理、调参和拟合的独立测试集报告。",
        ),
        (
            "POST_SOLVE_DECISION_MUTATION",
            r"(?is)\[\s*(?P<solution>[A-Za-z_]\w*)\s*,[^\]]+\]\s*=\s*"
            r"(?:fmincon|intlinprog|linprog|quadprog|ga|particleswarm)\s*\([^;]*\)\s*;?"
            r".{0,5000}?(?P=solution)\s*\([^\)\n]+\)\s*=\s*"
            r"(?P=solution)\s*\([^\)\n]+\)\s*[*/+-]\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)",
            "发现求解器返回后又直接修改解向量元素的信号。",
            "说明这是单位换算还是决策后处理；若改变真实决策，须重新检查变量域、预算、逻辑约束和目标值，不能沿用原最优性结论。",
        ),
        (
            "ROW_ORDER_SYNTHETIC_LABELS",
            r"(?is)\b(?P<label>[A-Za-z_]\w*)\s*\(\s*1\s*:\s*\d+"
            r"(?:\s*,[^)]*)?\)\s*=\s*0\s*;?.{0,1200}?"
            r"\b(?P=label)\s*\(\s*\d+\s*:\s*\d+"
            r"(?:\s*,[^)]*)?\)\s*=\s*1",
            "发现按样本行号区间直接生成 0/1 标签的信号。",
            "标签须逐行追溯到附件字段或明确规则，并保存实体索引与类计数；若这里只是测试夹具，请与正式训练入口隔离。",
        ),
        (
            "LINEAR_REGRESSION_FOR_LOGISTIC",
            r"(?is)\b(?:logistic|logstic)\w*.{0,2500}?\bregress\s*\(",
            "发现 Logistic/Logstic 命名上下文调用普通 regress 的信号。",
            "核对所用函数的统计目标；二分类 Logistic 应使用二项似然或等价分类接口，并报告标签、链接函数和输出概率。",
        ),
        (
            "MINIMAX_EXTREME_DIRECTION",
            r"(?im)^\s*[A-Za-z_]\w*\s*=\s*find\s*\(\s*"
            r"(?P<extreme>[A-Za-z_]\w*Max\w*)\s*==\s*max\s*\(\s*(?P=extreme)\s*\)\s*\)",
            "发现从名称含 Max 的候选指标中选择全局最大值所在索引的信号。",
            "若目标是最小化最大偏差，应以手算小例核对内外层极值方向，并确认导出索引使用 argmin；若确实求最大值，请在正文明确目标方向。",
        ),
        (
            "NESTED_LOOP_INDEX_MISMATCH",
            r"(?is)(?:if|elseif)\s*\([^)]*Position\s*\(\s*j\s*,\s*1\s*\)[^)]*\)"
            r".{0,500}?Position\s*\(\s*i\s*,\s*2\s*:\s*4\s*\)",
            "发现分支条件使用 Position(j,1)，随后在同一短代码段读取 Position(i,2:4) 的信号。",
            "核对 i/j 的循环角色，并用非方阵、非对称手算数据触发每个分支；若两个索引有意不同，请写明映射。",
        ),
        (
            "HARD_CONSTRAINT_PARTIAL_PASS",
            r"(?is)(?:不超过|不得超过|小于等于|\\leq|≤)"
            r"[^。；\n]{0,120}?\d+(?:\.\d+)?\s*\\?%"
            r".{0,1200}?(?:仅|只有)[^。；\n]{0,100}?\d+(?:\.\d+)?\s*\\?%",
            "发现硬阈值附近同时出现只有部分对象通过的信号，需确认结果是否仍被称为可行方案。",
            "区分硬/软约束；硬约束超限时标为不可行或近似可行，并报告最大违约、通过率、超限位置、松弛依据和修复代价。",
        ),
        (
            "UNSOLVED_MODEL_IN_CHAIN",
            r"(?is)(?:模型|方法)\s*(?:[一二三四五六]|[ⅠⅡⅢⅣⅤ]|[A-Z]|\d+)?"
            r"[^。；\n]{0,100}?(?:未(?:求解|计算|实现)|没有(?:求解|计算|实现))",
            "发现模型被明确标为未求解/未实现的信号，需确认它没有共享其他模型的结果或被写成已完成主链。",
            "为每个备选模型记录提出、推导、实现、求解和验证状态；未完成模型只作讨论，不并入结果、摘要或模型数量。",
        ),
        (
            "DETERMINISTIC_OUTPUT_AS_STABILITY",
            r"(?is)(?:每次|各次|每个(?:参数|扰动|取值))"
            r"[^。；\n]{0,140}?(?:得到|得出|输出|求得|产生)"
            r"[^。；\n]{0,140}?(?:稳定|稳健)",
            "发现以每次计算都能得到数值作为稳定性依据的信号。",
            "预先定义稳定判据、可行域和失稳边界，区分固定方案复算与逐点重求解；程序有确定输出不等于模型或策略稳健。",
        ),
    ]
    for code, pattern, message, suggestion in warning_checks:
        for match in re.finditer(pattern, text, re.I):
            findings.append(Finding(
                code, "warning", message, line_at(text, match.start()), suggestion,
            ))

    coefficient = re.search(r"经验(?:修正)?系数|修正系数|校正系数", text, re.I)
    if coefficient:
        context = text[max(0, coefficient.start() - 600):coefficient.end() + 600]
        if not re.search(r"来源|标定|校准|拟合|回归|样本|区间|置信|不确定|敏感", context, re.I):
            findings.append(Finding(
                "UNCALIBRATED_EMPIRICAL_COEFFICIENT", "warning",
                "发现经验/修正系数，但附近未见来源、标定样本、区间或不确定性信号。",
                line_at(text, coefficient.start()),
                "记录系数定义、来源、标定数据和适用工况，并报告区间/敏感性；无标定常数只能作为假设情景。",
            ))

    if re.search(r"\btrain_test_split\s*\(", text, re.I):
        transformer_pattern = re.compile(
            r"(?im)^[ \t]*(?P<var>[A-Za-z_]\w*)\s*=\s*"
            r"(?:StandardScaler|MinMaxScaler|MaxAbsScaler|RobustScaler|PowerTransformer|QuantileTransformer)"
            r"\s*\([^\n;]*\)"
        )
        for assignment in transformer_pattern.finditer(text):
            var = assignment.group("var")
            tail = text[assignment.end():assignment.end() + 6000]
            call = re.search(
                rf"\b{re.escape(var)}\.fit_transform\s*\(\s*(?P<data>[A-Za-z_]\w*)",
                tail, re.I,
            )
            if call and not re.search(r"train|fold|inner|fit", call.group("data"), re.I):
                offset = assignment.end() + call.start()
                findings.append(Finding(
                    "PREPROCESSOR_FIT_ON_UNSPLIT_DATA", "warning",
                    f"发现数据切分后，预处理器 {var} 在非训练命名对象“{call.group('data')}”上 fit_transform 的信号。",
                    line_at(text, offset),
                    "核对实际索引；补全、缩放、降维和选特征只在训练/内层折拟合，外层测试只能 transform。",
                ))

    estimator_pattern = re.compile(
        r"(?im)^[ \t]*(?P<var>[A-Za-z_]\w*)\s*=\s*(?:[A-Za-z_]\w*\.)?"
        r"(?P<class>[A-Za-z_]\w*(?:Classifier|Regressor)|SVC|SVR|LogisticRegression|LinearRegression|KMeans)"
        r"\s*\("
    )
    for assignment in estimator_pattern.finditer(text):
        var = assignment.group("var")
        tail_end = min(len(text), assignment.end() + 10000)
        next_assignment = re.search(
            rf"(?im)^[ \t]*{re.escape(var)}\s*=", text[assignment.end():tail_end]
        )
        if next_assignment:
            tail_end = assignment.end() + next_assignment.start()
        tail = text[assignment.end():tail_end]
        first_call = re.search(
            rf"\b{re.escape(var)}\.(?P<method>fit|partial_fit|predict|predict_proba|decision_function)\s*\(",
            tail, re.I,
        )
        if first_call and first_call.group("method").lower().startswith("predict"):
            offset = assignment.end() + first_call.start()
            findings.append(Finding(
                "PREDICT_BEFORE_FIT", "warning",
                f"估计器 {var}（{assignment.group('class')}）构造后的首个可见模型调用是 {first_call.group('method')}。",
                line_at(text, offset),
                "在首次预测前执行 fit 或显式载入已拟合模型，并保存模型文件、数据角色和调用顺序。",
            ))

    if re.search(r"\bXGBClassifier\s*\(", text, re.I):
        for match in re.finditer(r"(?i)(?:['\"]estimator['\"]|\bestimator\b)\s*[:=]", text):
            findings.append(Finding(
                "LIKELY_XGB_ESTIMATOR_PARAMETER", "warning",
                "XGBClassifier 上下文出现参数键 estimator；常见树数量参数为 n_estimators，需按实际库版本确认该键是否生效。",
                line_at(text, match.start()),
                "输出 estimator.get_params() 或构造器签名，核对参数名、实际值、库版本和训练日志。",
            ))

    for match in re.finditer(
        r"(?is)\b(?:roc_auc_score|roc_curve)\s*\([^,\n]+,\s*"
        r"(?:[A-Za-z_]\w*\.)?predict\s*\(", text,
    ):
        findings.append(Finding(
            "HARD_LABEL_ROC_AUC", "warning",
            "发现 ROC/AUC 直接读取 predict 硬标签的信号，无法完整评价排序能力。",
            line_at(text, match.start()),
            "二分类使用正类 predict_proba 或 decision_function 连续分数；硬标签结果仅作标签一致性描述。",
        ))

    feature_aliases: dict[tuple[str, str], tuple[str, int]] = {}
    for match in re.finditer(
        r"(?im)^[ \t]*(?P<alias>x\d+)\s*=\s*(?P<matrix>[A-Za-z_]\w*)"
        r"\s*\(\s*:\s*,\s*(?P<column>\d+)\s*\)\s*;?",
        text,
    ):
        key = (match.group("matrix").lower(), match.group("column"))
        alias = match.group("alias").lower()
        previous = feature_aliases.get(key)
        if previous and previous[0] != alias:
            findings.append(Finding(
                "DUPLICATE_FEATURE_COLUMN", "warning",
                f"发现特征别名 {previous[0]} 与 {alias} 都读取 {match.group('matrix')}(:,{match.group('column')})。",
                line_at(text, match.start()),
                "核对特征--列映射；若有意复用同一列，请在数据字典和消融结果中说明，避免复制粘贴造成特征缺失。",
            ))
        else:
            feature_aliases[key] = (alias, line_at(text, match.start()))
    return findings


def audit(
    path: Path,
    problem_type: str,
    resource_roots: tuple[Path, ...] = (),
) -> dict:
    text = read_tex_tree(path)
    findings = (required_sections(text) + placeholders(text) + floats(text)
                + cross_references(text, path, resource_roots) + semantic_signals(text, problem_type)
                + ai_cliche_signals(text) + reasoning_narrative_signals(text)
                + implementation_signals(text))
    findings.sort(key=lambda item: (item.line is None, item.line or 0, item.severity, item.code))
    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    return {
        "schema_version": 1,
        "file": str(path.resolve()),
        "source": {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.resolve().read_bytes()).hexdigest(),
        },
        "problem_type": problem_type,
        "status": "PASS" if errors == 0 else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "findings": [asdict(item) for item in findings],
        "limitations": [
            "规则审计只检查结构和可定位写作信号，不证明模型、数据、公式或结论正确。",
            "逐问首次方法检查只寻找公开可复核的局部依据，不要求也不能推断作者的隐藏思维链；直接列式或沿用前问的分问可以没有候选模型比较。",
            "已声明且可解析的 .bib 会检查引用键；动态生成的章节、标签和编译期行为仍需结合最终日志核验。",
            "训练集回代、求解后变量修改、按行号标签、模型名--拟合接口、重复特征列、预处理拟合域、首次预测调用、参数名、硬标签 AUC、嵌套极值方向、循环索引、蒙特卡洛协议、部分硬约束通过、未求解模型、经验系数和稳定性表述采用保守静态匹配，命中后仍须结合目标方向、索引角色、数据角色、库版本、单位与约束日志人工裁决。",
        ],
    }


def render_text(result: dict) -> str:
    lines = [f"AUDIT {result['status']} errors={result['errors']} warnings={result['warnings']}",
             f"file={result['file']}", f"problem_type={result['problem_type']}"]
    for item in result["findings"]:
        where = f" line={item['line']}" if item["line"] else ""
        lines.append(f"[{item['severity'].upper()}] {item['code']}{where}: {item['message']}")
        if item["suggestion"]:
            lines.append(f"  建议：{item['suggestion']}")
    lines.append("限制：" + "；".join(result["limitations"]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a CUMCM LaTeX manuscript.")
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--problem-type", required=True, choices=["A", "B", "C"])
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument(
        "--resource-root", type=Path, action="append", default=[],
        help="额外的已冻结编译资源根，可重复；用于解析候选目录之外的 .bib。",
    )
    args = parser.parse_args()
    if not args.main_tex.is_file():
        parser.error(f"file not found: {args.main_tex}")
    try:
        result = audit(args.main_tex, args.problem_type, tuple(args.resource_root))
    except UnicodeDecodeError as exc:
        print(json.dumps({"status": "FAIL", "error": f"UTF-8 decode failed: {exc}"}, ensure_ascii=False))
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json" else render_text(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
