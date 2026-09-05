#!/usr/bin/env python
"""Expand the corpus-derived strict Chinese style lexicon.

The expansion has ten independent discovery routes:

1. contiguous 2-6 Han-character substrings repeatedly embedded in the
   existing strict phrases;
2. previously unseen 4-8 character phrases discovered directly in the
   aggregate Codex assistant n-gram table;
3. comparative/root families such as 更稳, 更好 and 更准;
4. single-character discovery roots whose complete 2-12 character families
   clear the same evidence gates. Bare roots are never emitted.
5. raw 2-3 character cores discovered independently of the old inventory,
   then checked against styled parent shells and live corpus boundaries;
6. corpus-confirmed compound roots such as 收紧, whose exact 2-12 character
   collocations pass a narrow prefix/suffix boundary contract.
7. root-first 2-12 character families expanded from raw short cores without
   requiring an old-inventory marker; live source boundaries decide release.
8. prior candidate CSVs are decomposed again so short phrases hidden inside
   already discovered 4-8 character phrases can become fresh candidates.
9. 2-3 character roots are discovered directly from MD/TeX semantic units,
   independently of the aggregate chat n-gram table.
10. 1-3 character discovery roots are inverted from complete discourse-shell
    parents (for example 再X, 进一步X, X一点 and 更X).  The bare roots are only
    audit keys; complete 2-12 character families are rescanned and published.

Every emitted phrase is then counted again in a byte-frozen snapshot of the
current Codex assistant messages and in a byte-frozen MD/TeX document
snapshot.  The script writes counts and rejection reasons, never raw chat or
document excerpts.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gc
import hashlib
import heapq
import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator


SCRIPT_VERSION = "3.10.2"
STYLE_ANALYSIS_LEXICON_PATH = Path(__file__).with_name("style_analysis_lexicon.json")
HAN_EXACT_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")
HAN_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]{2,}")
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
URL_PATH_RE = re.compile(
    r"(?:https?://\S+|[A-Za-z]:\\[^\s，。；！？]+|/(?:[^\s/]+/){2,}[^\s]*)"
)
TEX_COMMENT_RE = re.compile(r"(?m)(?<!\\)%.*$")
TEX_DISPLAY_MATH_RE = re.compile(
    r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$"
)
TEX_INLINE_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]*?(?<!\\)\$")
TEX_ENV_RE = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|"
    r"tikzpicture|lstlisting|verbatim)\}[\s\S]*?"
    r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?|"
    r"tikzpicture|lstlisting|verbatim)\}"
)
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]\n]*\])?")
UNIT_SPLIT_RE = re.compile(r"(?:[。！？!?；;：:]|\r?\n)+")
MOJIBAKE_RE = re.compile(r"(?:锟斤拷|馃|闂|绾|瀹|鍙|浜|鐨|鈥|銆){3,}")

RAW_SHORT_AUDIT_MIN_COVERAGE = 80
RAW_SHORT_RESCAN_MIN_COVERAGE = {2: 500, 3: 300}
RAW_SHORT_MIN_FAMILY_PARENTS = 3
RAW_SHORT_MIN_CONTEXTS = 2
RAW_SHORT_MAX_CONTEXT_DOMINANCE = 0.95
RAW_SHORT_LIVE_MIN_CONTEXTS = 4
RAW_SHORT_LIVE_MIN_BOUNDARY_RATE = 0.10
RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE = 0.75
RAW_SHORT_LIVE_STRONG_FRAGMENT_DOMINANCE = 0.50
DECOMPOSITION_MIN_PARENT_COVERAGE = 80
DECOMPOSITION_MIN_PARENT_OCCURRENCES = 80
# Prior candidate CSVs are already bounded, structured discovery artifacts.
# Silently truncating them by global frequency is precisely how productive
# long-tail roots disappear, so every eligible parent is decomposed.
DECOMPOSITION_PARENT_LIMIT: int | None = None
# Evidence thresholds, rather than a frequency quota, decide whether a
# document-derived 2/3-gram reaches exact rescan.  A fixed Top-K here used to
# hide 15,197 otherwise eligible roots in the pass-8 corpus.
DOCUMENT_NGRAM_SEED_LIMIT: int | None = None
DOCUMENT_NGRAM_MIN_UNITS = {2: 80, 3: 50}
DOCUMENT_NGRAM_MIN_FILES = {2: 5, 3: 3}
DOCUMENT_NGRAM_MIN_OCCURRENCES = {2: 120, 3: 80}
DOCUMENT_ROOT_AUDIT_MIN_UNITS = {1: 40, 2: 20, 3: 10}
DOCUMENT_ROOT_MIN_FILES = {1: 5, 2: 3, 3: 2}
DOCUMENT_ROOT_MIN_OCCURRENCES = {1: 80, 2: 40, 3: 20}
ROOT_FAMILY_RESERVE_PER_TRIGGER = 12
ROOT_FAMILY_FINAL_RESERVE_PER_BUCKET = 2
DATA_ROOT_MIN_SEED_COVERAGE = 500
DATA_ROOT_MIN_FAMILY_PHRASES = 20
ROOT_INVERSION_PARENT_MIN_COVERAGE = 5
ROOT_INVERSION_MIN_PARENT_COUNT = {1: 10, 2: 6, 3: 5}
ROOT_INVERSION_MIN_SHELL_PARENT_COUNT = {1: 10, 2: 6, 3: 5}
ROOT_INVERSION_MIN_SHELL_TYPE_COUNT = {1: 5, 2: 4, 3: 3}
ROOT_INVERSION_MIN_WEIGHTED_COVERAGE = {1: 1000, 2: 500, 3: 300}
ROOT_INVERSION_CONTEXT_MIN_PARENT_COUNT = {2: 8, 3: 6}
ROOT_INVERSION_CONTEXT_MIN_WEIGHTED_COVERAGE = {2: 1000, 3: 600}
ROOT_INVERSION_CONTEXT_MIN_SIDE_TYPES = 4
ROOT_INVERSION_CONTEXT_MAX_SIDE_DOMINANCE = 0.75
ROOT_INVERSION_FAMILY_MIN_COVERAGE = 5
# Root-family candidates above this deterministic floor are all rescanned.
# Ranking heaps remain useful for unrelated long-phrase routes, but they must
# never decide whether a productive root family is visible to exact counting.
ROOT_INVERSION_FAMILY_RESCAN_MIN_COVERAGE = ROOT_INVERSION_FAMILY_MIN_COVERAGE
ROOT_INVERSION_RESERVE_PER_TRIGGER = 24
ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_PARENTS = 4
ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_TYPES = 4
ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_COVERAGE = 500
ROOT_INVERSION_REJECTION_EXAMPLES_PER_ROOT = 12
ROOT_INVERSION_LONGER_ROOT_MAX_DOMINANCE = 0.80
ROOT_INVERSION_LONGER_ROOT_SUM_DOMINANCE = 0.90
ROOT_INVERSION_LONGER_ROOT_CONTEXT_RATIO = 0.60
ROOT_INVERSION_LONGER_ROOT_CONTEXT_DOMINANCE = 0.60
ROOT_PROBE_MIN_COVERAGE = 1
ROOT_GRAPH_EXACT_MIN_COVERAGE = 5
ROOT_GRAPH_SINGLE_MIN_PARENT_COUNT = 2
ROOT_GRAPH_EMBEDDED_MIN_PARENT_COUNT = 2
ROOT_GRAPH_EMBEDDED_MIN_WEIGHTED_COVERAGE = 10
ROOT_FIRST_PARENT_MIN_COVERAGE = 1
ROOT_FIRST_PARENT_MAX_LENGTH = 12
ROOT_FAMILY_MAX_LENGTH = ROOT_FIRST_PARENT_MAX_LENGTH
ROOT_FIRST_SHORT_SEED_MIN_COVERAGE = ROOT_GRAPH_EXACT_MIN_COVERAGE
ROOT_FIRST_MIN_PARENT_COUNT = {1: 24, 2: 12, 3: 10}
ROOT_FIRST_MIN_WEIGHTED_COVERAGE = {1: 1500, 2: 1000, 3: 600}
ROOT_FIRST_MIN_SIDE_TYPES = 4
ROOT_FIRST_MAX_SIDE_DOMINANCE = 0.80
ROOT_FIRST_MIN_SHELL_PARENT_COUNT = {1: 4, 2: 3, 3: 3}
ROOT_FIRST_MIN_SHELL_TYPE_COUNT = {1: 3, 2: 2, 3: 2}
ROOT_FIRST_MIN_SHELL_WEIGHTED_COVERAGE = {1: 500, 2: 200, 3: 150}
ROOT_FIRST_KNOWN_SHELL_MIN_PARENT_RATIO = {1: 0.10, 2: 0.08, 3: 0.06}
ROOT_FIRST_KNOWN_SHELL_MIN_COVERAGE_RATIO = {1: 0.08, 2: 0.06, 3: 0.05}
ROOT_FIRST_MIN_EMPIRICAL_SHELL_PARENTS = {1: 12, 2: 10, 3: 8}
ROOT_FIRST_MIN_EMPIRICAL_SHELL_TYPES = {1: 8, 2: 7, 3: 6}
ROOT_FIRST_MIN_EMPIRICAL_SHELL_COVERAGE = {1: 1500, 2: 1000, 3: 600}
ROOT_FIRST_EMPIRICAL_EXACT_MIN_COVERAGE = {2: 200, 3: 120}
ROOT_FIRST_STYLE_SHELL_MIN_SEED_ROOTS = 8
ROOT_FIRST_STYLE_SHELL_MIN_SEED_RATIO = 0.025
ROOT_FIRST_STYLE_SHELL_MIN_SEED_LIFT = 10.0
ROOT_FIRST_STYLE_SHELL_GLOBAL_RATE_CAP = 0.05
ROOT_FIRST_STYLE_SHELL_MIN_TYPES = {1: 5, 2: 3, 3: 3}
ROOT_FIRST_STYLE_SHELL_MIN_PARENTS = {1: 10, 2: 6, 3: 5}
ROOT_FIRST_STYLE_SHELL_MIN_COVERAGE = {1: 1000, 2: 300, 3: 200}
ROOT_FIRST_STYLE_SHELL_MIN_SEED_ROOT_UNION = {1: 6, 2: 4, 3: 4}
ROOT_FIRST_STYLE_SHELL_MIN_PARENT_RATIO = {1: 0.08, 2: 0.08, 3: 0.08}
ROOT_FIRST_STYLE_SHELL_MIN_COVERAGE_RATIO = {1: 0.05, 2: 0.05, 3: 0.05}
ROOT_FIRST_SINGLE_MIN_DIRECT_PARENTS = 8
ROOT_FIRST_SINGLE_MIN_DIRECT_COVERAGE = 1200
ROOT_INVERSION_HARD_SINGLE_STOP = frozenset(
    "的一是了在有和与及对把被将为于以从而或并且也都很更最太较不无未可会能要需应已再又"
    "前后内外中上下左右自各每这那其正"
)
ROOT_INVERSION_ELIGIBLE_STATUSES = frozenset({"eligible_root_inversion"})

ROOT_FIRST_CHAT_SOURCES = frozenset(
    {
        "aggregate-root-probe",
        "aggregate-root-window",
        "aggregate-short-seed",
        "aggregate-discourse-shell",
        "raw-short-core-pass4",
        "baseline-v1",
        "csv-decomposition-pass6",
    }
)
ROOT_FIRST_DOCUMENT_SOURCES = frozenset(
    {"document-short-core-pass7", "document-root-graph-pass9"}
)

FAMILY_SOURCE_KINDS = {
    "comparative-root-pass3",
    "single-root-family-pass3",
    "compound-root-pass4",
    "raw-core-family-pass5",
    "root-inversion-family-pass8",
}

SEMANTIC_GATED_SOURCE_KINDS = {
    "raw-short-core-pass4",
    "raw-core-family-pass5",
    "single-root-family-pass3",
    "root-inversion-family-pass8",
}

CHAT_EXACT_BASE_FIELDS = (
    "chat_occurrences",
    "chat_message_coverage",
    "chat_message_coverage_rate",
)
DOCUMENT_EXACT_BASE_FIELDS = (
    "md_occurrences",
    "md_unit_coverage",
    "md_file_coverage",
    "tex_occurrences",
    "tex_unit_coverage",
    "tex_file_coverage",
)
EXACT_CONTEXT_FIELDS = tuple(
    f"{source}_context_{side}_{metric}"
    for source in ("chat", "document")
    for side in ("left", "right")
    for metric in (
        "context_count",
        "boundary_rate",
        "nonboundary_dominance",
        "contexts",
    )
)

SUBPHRASE_SOURCE_KINDS = {
    "parent-subphrase-pass2",
    "csv-decomposition-pass6",
}


def load_strict_release_config(path: Path = STYLE_ANALYSIS_LEXICON_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = payload.get("strict_release")
    if not isinstance(config, dict):
        raise RuntimeError(f"missing strict_release config in {path}")
    required_lists = (
        "protected_content_exact",
        "function_or_generic_exact",
        "discovery_root_only_exact",
        "fragment_exact",
        "high_confidence_style_core_exact",
        "short_literal_exact",
    )
    for key in required_lists:
        values = config.get(key)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise RuntimeError(f"invalid strict_release.{key} in {path}")
    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise RuntimeError(f"invalid strict_release.thresholds in {path}")
    return config


STRICT_RELEASE_CONFIG = load_strict_release_config()
STRICT_RELEASE_PROTECTED_CONTENT = frozenset(
    STRICT_RELEASE_CONFIG["protected_content_exact"]
)
STRICT_RELEASE_FUNCTION_OR_GENERIC = frozenset(
    STRICT_RELEASE_CONFIG["function_or_generic_exact"]
)
STRICT_RELEASE_DISCOVERY_ROOT_ONLY = frozenset(
    STRICT_RELEASE_CONFIG["discovery_root_only_exact"]
)
STRICT_RELEASE_FRAGMENTS = frozenset(STRICT_RELEASE_CONFIG["fragment_exact"])
STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES = frozenset(
    STRICT_RELEASE_CONFIG["high_confidence_style_core_exact"]
)
STRICT_RELEASE_SHORT_LITERALS = frozenset(
    STRICT_RELEASE_CONFIG["short_literal_exact"]
)
STRICT_RELEASE_THRESHOLDS = STRICT_RELEASE_CONFIG["thresholds"]
STRICT_RELEASE_CONFIG_SHA256 = hashlib.sha256(
    STYLE_ANALYSIS_LEXICON_PATH.read_bytes()
).hexdigest()

if STRICT_RELEASE_DISCOVERY_ROOT_ONLY & STRICT_RELEASE_SHORT_LITERALS:
    overlap = sorted(STRICT_RELEASE_DISCOVERY_ROOT_ONLY & STRICT_RELEASE_SHORT_LITERALS)
    raise RuntimeError(
        "strict discovery-only roots overlap hard literals: " + ",".join(overlap)
    )

DISCOURSE_ATTACHMENT_PREFIXES = tuple(
    sorted(
        {
            "再", "继续", "进一步", "必须", "应当", "应该", "可以", "需要", "建议",
            "重新", "再次", "同步", "逐步", "逐渐", "开始", "停止", "已经", "仍然",
            "最终", "最后", "务必", "只需", "无需", "不再", "不能", "不得", "避免",
            "确保", "尝试", "主动", "适当", "统一", "严格", "直接", "一起", "先", "将", "要",
            "会", "应", "可", "不",
        },
        key=lambda item: (-len(item), item),
    )
)
DISCOURSE_ATTACHMENT_SUFFIXES = tuple(
    sorted(
        {
            "一点", "一些", "起来", "下来", "下去", "上来", "为", "成", "到", "了",
            "好", "清楚", "明确", "稳定", "完整", "自然", "妥", "妥当",
        },
        key=lambda item: (-len(item), item),
    )
)

SOURCE_PRIORITY = {
    "baseline-v1": 100,
    "raw-short-core-pass4": 90,
    "document-short-core-pass7": 85,
    "compound-root-pass4": 80,
    "comparative-root-pass3": 70,
    "root-inversion-family-pass8": 65,
    "raw-core-family-pass5": 60,
    "single-root-family-pass3": 50,
    "independent-longphrase-pass2": 40,
    "parent-subphrase-pass2": 30,
}

CATEGORY_ORDER = (
    "process-broadcast",
    "completion-closure",
    "audit-governance",
    "scope-boundary",
    "contrast-correction",
    "transition-roadmap",
    "emphasis-shell",
    "academic-packaging",
    "research-self-proof",
    "recommendation-outlook",
    "certainty-limitation",
    "interaction-invitation",
)

# Regression sentinels turn the user's concrete failure cases into an
# executable release gate.  They do not replace corpus discovery; they stop a
# future threshold or boundary refactor from silently losing the target family
# or reintroducing already diagnosed fixed-width fragments.
REQUIRED_FINAL_PHRASES = {
    "更稳", "会更稳", "这样更稳", "更稳一点", "更稳的说法", "更稳的写法",
    "更好", "更清", "更强", "更准", "更自然",
    "收紧", "再收紧", "收紧一点", "进一步收紧", "必须进一步收紧",
    "要收紧", "再收紧一点", "一起收紧", "口径收紧",
}
FORBIDDEN_FINAL_FRAGMENTS = {
    "成更稳", "文更自然", "前最稳妥", "个更稳", "一个更稳", "用更稳",
    "持久化", "目标值", "续成熟化", "并通过", "次完整", "目标不",
    "完整读取并", "继续压了",
    "步收紧", "径收紧", "收紧一", "再收紧一", "收紧为", "一步收紧",
    "须进一步收紧", "起收紧", "经收紧", "门收紧", "界收紧",
    "界必须进一步收紧",
}

# These hints only route discovery.  A hint never enters the final inventory
# unless the resulting phrase clears the independent chat and document gates.
DISCOVERY_HINTS: dict[str, tuple[str, ...]] = {
    "process-broadcast": (
        "我先", "我会", "先把", "再把", "接下来", "下一步", "当前", "现在",
        "本轮", "本次", "随后", "然后", "继续", "重新", "先确认", "先检查",
        "先处理", "继续推进", "开始处理", "进入下一", "先完成", "马上",
    ),
    "completion-closure": (
        "完成", "已完成", "最终", "正式", "收尾", "闭环", "收口", "定版",
        "锁定", "落地", "交付", "达标", "验收", "成熟", "稳定版", "生产级",
        "全量", "彻底", "覆盖", "解决", "完整", "成果", "成型", "就绪",
    ),
    "audit-governance": (
        "验证", "确认", "证据", "审计", "测试", "复核", "检查", "一致",
        "可复核", "可追溯", "可验证", "可复现", "状态", "资格", "清关",
        "门禁", "通过", "失败", "拒绝", "阻断", "台账", "清单", "哈希",
        "逐字节", "可信", "合规", "留痕", "审阅", "核验", "判定",
    ),
    "scope-boundary": (
        "范围", "边界", "约束", "权限", "授权", "不可", "不得", "不能",
        "不会", "保留", "不改", "不新增", "仅限", "只保留", "明确", "固定",
        "严格", "前提", "条件", "局限", "限制", "禁止", "例外", "口径",
    ),
    "contrast-correction": (
        "不是", "而是", "并非", "不在于", "在于", "并不意味着", "真正",
        "本质", "核心", "关键", "更准确", "准确地说", "换句话说", "需要区分",
        "不能混同", "不能等同", "不等于", "不是简单", "并不是", "与其",
    ),
    "transition-roadmap": (
        "因此", "所以", "从而", "进而", "同时", "此外", "另外", "随后", "于是",
        "由此", "综上", "总之", "总体", "换言之", "也就是说", "具体而言",
        "进一步", "与此同时", "在此基础上", "基于上述", "最后", "首先", "其次",
        "再次", "一方面", "另一方面", "相较之下", "由此可见", "总的来说",
    ),
    "emphasis-shell": (
        "值得注意", "需要指出", "需要说明", "需要强调", "必须强调", "尤其",
        "特别", "显然", "不难发现", "可以看出", "可以发现", "由此可见", "可见",
        "不可忽视", "尤为重要", "值得一提", "关键在于", "核心在于", "务必",
        "毋庸置疑", "显而易见", "不容忽视", "必须指出", "必须说明",
    ),
    "academic-packaging": (
        "系统", "全面", "深入", "综合", "充分", "有效", "显著", "重要", "关键",
        "核心", "机制", "框架", "体系", "路径", "维度", "层面", "逻辑", "结构",
        "作用", "价值", "意义", "优势", "挑战", "目标", "方案", "方法", "策略",
        "模式", "范式", "视角", "脉络", "图景", "支撑", "保障", "推动", "促进",
        "提升", "优化", "强化", "构建", "形成", "实现", "赋能", "揭示", "体现",
        "彰显", "凸显", "确保", "助力", "协同", "打造", "聚焦", "夯实", "释放",
        "驱动", "引领", "多维", "全方位", "高质量", "新格局", "新范式",
    ),
    "research-self-proof": (
        "本文", "本研究", "本章", "本节", "本文将", "本文旨在", "研究表明",
        "结果表明", "分析表明", "结果显示", "研究结果", "主要贡献", "创新点",
        "研究意义", "研究目的", "研究内容", "填补空白", "提供支撑", "奠定基础",
        "有力支撑", "理论意义", "实践意义", "重要意义", "现实意义", "应用价值",
        "理论价值", "本文提出", "本研究提出", "研究价值", "参考价值", "借鉴意义",
    ),
    "recommendation-outlook": (
        "建议", "可以考虑", "可考虑", "应当", "应该", "有必要", "务必", "值得",
        "不妨", "后续可", "未来可", "未来研究", "后续研究", "进一步研究",
        "下一步可以", "可以继续", "有待", "仍需", "还需", "需要进一步",
        "值得进一步", "未来工作", "后续工作", "未来有望", "值得期待",
    ),
    "certainty-limitation": (
        "已经", "当前", "真实", "实际", "确实", "完全", "彻底", "稳定", "成熟",
        "正确", "最终", "正式", "可靠", "无疑", "必然", "一定", "可能", "或许",
        "一定程度", "某种意义", "总体上", "基本上", "相对而言", "尚未", "仍然",
        "仍旧", "大体", "通常", "普遍", "无可否认", "毫无疑问", "更稳",
    ),
    "interaction-invitation": (
        "如果你愿意", "如果需要", "我可以", "你可以", "建议你", "可以继续",
        "下一步可以", "后续可以", "需要的话", "若有需要", "可以再", "我再",
        "告诉我", "你只要", "随时", "需要我", "我也可以", "欢迎",
    ),
}

# Single-character roots are not emitted as unconditional literal bans.  They
# seed phrase families and must be attached to an actual 2-12 character match.
# This prevents a root such as "稳" from silently disappearing while still
# protecting technical terms such as "稳态解" from a bare one-character gate.
SINGLE_ROOT_HINTS: dict[str, tuple[str, ...]] = {
    "certainty-limitation": ("稳", "真", "全", "深", "强", "准", "清", "实"),
    "academic-packaging": ("新", "优", "高", "广", "大", "好", "精", "融", "赋"),
    "completion-closure": ("完", "成", "闭", "熟", "终", "定", "落", "锁"),
    "emphasis-shell": ("显", "重", "特", "必"),
}
COMPARATIVE_STEM_HINTS: dict[str, tuple[str, ...]] = {
    "certainty-limitation": (
        "稳定", "稳妥", "自然", "明确", "清楚", "清晰", "准确", "完整", "成熟",
        "直接", "可靠", "合理", "具体",
    ),
    "academic-packaging": (
        "高效", "全面", "系统", "深入", "综合", "充分", "有效",
    ),
}

# A compound root is a corpus-confirmed complete lexical seed, not an
# arbitrary two-character n-gram.  It exists because the ordinary root route
# deliberately refuses every two-character candidate: lowering that global
# boundary would admit millions of fixed-width fragments.  New seeds belong
# here only after their exact aggregate count has been checked.
COMPOUND_ROOT_HINTS: dict[str, tuple[str, ...]] = {
    "scope-boundary": ("收紧",),
}
COMPOUND_ROOT_PREFIXES = (
    "", "再", "继续", "进一步", "必须进一步", "需要进一步", "要", "需要",
    "一起", "也一起", "同步", "已经", "已", "也", "同时", "被", "要求被",
    "口径", "边界", "阈值", "措辞", "规则", "范围", "条件", "标准", "权限",
    "入口", "表述", "断言",
)
COMPOUND_ROOT_SUFFIXES = ("", "一点")
COMPOUND_ROOT_PATTERNS = {
    phrase: category
    for category, phrases in COMPOUND_ROOT_HINTS.items()
    for phrase in phrases
}
COMPARATIVE_ROOT_PATTERNS = tuple(
    sorted(
        {
        (prefix + stem, category, stem)
        for category in CATEGORY_ORDER
        for stem in (
            *SINGLE_ROOT_HINTS.get(category, ()),
            *COMPARATIVE_STEM_HINTS.get(category, ()),
        )
        for prefix in ("更", "很", "最", "太", "较", "愈")
        },
        key=lambda item: (item[0], CATEGORY_ORDER.index(item[1]), item[2]),
    )
)

# Function characters are never promoted to discovery roots solely because of
# raw frequency.  A retained root must recur inside several already supported
# style phrases and generate complete multi-character families.
SINGLE_ROOT_STOP = set(
    "的一是不了在有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同"
    "工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二"
    "理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那"
    "社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条"
)
SINGLE_ROOT_MANUAL_ALLOW = {
    root
    for roots in SINGLE_ROOT_HINTS.values()
    for root in roots
}

BAD_EDGE = set("的了着过和与或及而被把对从在为于以将则且也都很更最其这那是")
NOISE_EXACT = {
    "一个", "这些", "那些", "什么", "出来", "这里", "这个", "其中", "文件",
    "代码", "公式", "函数", "变量", "数据", "模型", "论文", "章节", "用户",
    "代理", "目录", "版本", "内容", "问题", "结果", "任务", "工作", "部分",
    "一种", "一些", "很多", "所有", "相关", "方面", "过程", "情况", "时候",
    "地方", "东西", "进行", "以及", "由于", "对于", "通过", "作为", "关于",
    "能够", "可以", "需要", "已经", "没有", "还有", "然后", "因为", "如果",
}
ROOT_FAMILY_NOISE_EXACT = {
    "一轮", "收益", "口径", "通常", "成一个", "项测试", "一处", "一份",
    "一个", "一项", "一条", "一遍", "一眼", "一部分", "一方面", "一系列",
}
SUBPHRASE_FRAGMENT_EXACT = {
    "下一", "前不", "本轮已", "当前文", "当前实", "继续保", "当前仍",
    "现在不", "当前正", "续提升", "前已经", "前不能", "当前方", "机器结",
    "已完", "成资格", "成全", "式结", "化目标", "完成全", "后运行",
    "资格仍", "可信外部", "失败不", "审计结", "成生成", "证据支",
    "验证完", "格边界", "测试不", "成模型", "确报告", "固定优",
    "核心结", "关键结", "不是必", "由此可", "因此不", "体而言",
    "尤其不", "结构检", "路径不", "方法不", "定基", "本文不",
    "得继续", "未完", "实际生", "尚未完", "已经明", "实际结",
    "已经生", "真实结", "实际文",
}
ROOT_FAMILY_BAD_PREFIXES = (
    "的", "个", "项", "份", "套", "度", "性", "和", "与", "或", "及", "而",
    "为", "于", "以", "将", "被", "把", "从", "对", "有", "无", "没", "否",
    "并", "且", "次", "前", "后",
)
ROOT_FAMILY_BAD_SUFFIXES = (
    "的", "地", "得", "和", "与", "或", "及", "而", "为", "于", "以", "将",
    "被", "把", "从", "对", "是", "有", "无", "没", "再", "仍", "只", "已",
    "未", "要", "需", "可", "一", "第", "项", "个", "现", "刚", "往",
)
BAD_PREFIXES = {
    "前目", "前结", "后目", "后结", "一方", "二方", "三方", "当前目", "当前结",
    "完整结", "最终结", "具体而", "总体而", "进一步研", "值得注", "需要指",
}
COMPLETE_ENDINGS = (
    "问题", "结果", "状态", "版本", "内容", "结构", "目标", "范围", "边界", "条件",
    "要求", "规则", "策略", "方案", "方法", "过程", "工作", "任务", "测试", "验证",
    "审计", "复核", "报告", "结论", "正文", "系统", "模型", "数据", "文本", "候选",
    "证据", "实现", "完成", "通过", "失败", "修改", "处理", "确认", "保留", "删除",
    "调整", "统一", "一致", "正确", "生效", "清晰", "明确", "稳定", "成熟", "可靠",
    "可信", "推进", "收尾", "闭环", "落地", "定版", "交付", "输出", "输入", "检查",
    "读取", "编译", "运行", "生成", "支持", "支撑", "基础", "意义", "价值", "机制",
    "框架", "体系", "路径", "维度", "层面", "逻辑", "作用", "优势", "挑战", "核心",
    "关键", "建议", "研究", "分析", "说明", "强调", "指出", "注意", "可见", "显示",
    "表明", "提出", "构建", "形成", "提升", "优化", "强化", "保障", "推动", "促进",
    "确保", "助力", "协同", "限制", "局限", "风险", "权限", "授权", "门禁", "清关",
    "资格", "记录", "清单", "台账", "阶段", "场景", "来源", "语境", "原因", "依据",
    "关系", "变化", "差异", "能力", "质量", "效果", "收益", "成本", "方向", "趋势",
    "空间", "水平", "效率", "格局", "范式", "图景", "抓手", "举措", "视角", "脉络",
    "而言", "来说", "来看", "基础上", "前提下", "过程中", "层面上", "意义上",
)
COMPLETE_STARTS = tuple(
    sorted(
        {
            hint
            for hints in DISCOVERY_HINTS.values()
            for hint in hints
            if len(hint) >= 2
        },
        key=len,
        reverse=True,
    )
)

# A candidate may start with a valid process marker while still ending in a
# cut-off fragment.  These are common artefacts of taking a fixed-width n-gram
# from a longer assistant sentence.  The prefixes are deliberately narrow;
# this is a quality gate for discovery, not a ban on the underlying words.
FRAGMENT_PREFIXES = (
    "下一步", "我先", "我再", "接下来", "当前会话实际", "前会话实际",
    "当前会话已经", "前会话已经", "且当前会话", "会话已经实际",
    "不能声称", "失败记录", "进一步", "整已", "当前文件系统",
)
FRAGMENT_ENDINGS = (
    "一", "第", "几", "现", "刚", "这", "那", "两", "值", "合", "顺",
    "权", "文", "支", "基", "审", "测", "配", "继", "提", "看", "把",
    "能", "会", "可", "要", "需", "有", "无", "未", "不", "并", "且", "而",
    "或", "和", "与", "及", "了", "压", "按",
)
COMPLETE_FRAGMENT_SUFFIXES = (
    "一下", "一眼", "一遍", "一个", "一些", "一点", "一条", "一项",
    "一处", "一轮", "一份", "的说法", "的写法", "的做法", "的方式",
    "的处理", "的结果", "的方案", "的建议", "的结论", "的状态",
)
COMPARATIVE_COMPLETE_SUFFIXES = (
    "稳妥", "稳定", "自然", "明确", "清楚", "直接", "准确", "全面",
    "成熟", "可靠",
    "一点", "一些", "的说法", "的写法", "的做法", "的方式", "的处理", "的结果",
    "的结论", "的表述", "的表达", "的方案", "的话",
)
COMPARATIVE_CONTEXT_PREFIXES = (
    "会", "将会", "这样", "这样做", "这样写", "这样说", "可以", "能够",
    "改成", "变得", "写得", "说得", "做得", "显得", "看起来", "反而",
    "明显", "所以", "因此", "现在", "本文", "本研究", "随后", "当前", "最终",
)
ROOT_SHELL_PREFIXES = (
    "不", "会", "这样", "可以", "能够", "很", "最", "较", "太", "更",
    "比较", "已经", "仍然", "是否", "能否", "没有", "达到", "保持", "改成",
    "当前", "最终", "生产",
)
ROOT_SHELL_SUFFIXES = (
    "一点", "妥", "妥的", "性", "版", "化", "度", "的说法", "的写法",
    "的做法", "的方式", "的处理", "的结果", "稳定", "自然", "明确", "准确",
    "清楚", "可靠", "成熟",
)

# Root inversion starts from a complete parent shell and removes only an
# attested discourse attachment.  Single-character suffixes such as 了/为/成
# are deliberately excluded: stripping them creates fixed-width fragments at
# industrial scale.  Prefix/suffix pairs are tested longest first.
ROOT_INVERSION_PREFIXES = tuple(
    sorted(
        set(DISCOURSE_ATTACHMENT_PREFIXES)
        | {
            "更", "很", "最", "太", "较", "愈", "这样", "这样做", "这样写",
            "这样说", "改成", "变得", "写得", "说得", "做得", "显得", "看起来",
            "反而", "明显", "因此", "所以", "现在", "本文", "本研究", "随后",
            "当前", "最终", "必须进一步", "需要进一步",
        },
        key=lambda item: (-len(item), item),
    )
)
ROOT_INVERSION_SUFFIXES = tuple(
    sorted(
        {
            "一点", "一些", "起来", "下来", "下去", "上来", "清楚", "明确",
            "稳定", "完整", "自然", "妥", "妥当", "的说法", "的写法", "的做法",
            "的方式", "的处理", "的结果", "的方案", "的建议", "的结论", "的状态",
            "的表述", "的表达", "的话",
        },
        key=lambda item: (-len(item), item),
    )
)
ROOT_INVERSION_COMPARATIVE_PREFIXES = frozenset({"更", "很", "最", "太", "较", "愈"})
ROOT_INVERSION_PREFIX_INDEX = {
    char: tuple(prefix for prefix in ROOT_INVERSION_PREFIXES if prefix.startswith(char))
    for char in {prefix[0] for prefix in ROOT_INVERSION_PREFIXES}
}
ROOT_INVERSION_SUFFIX_INDEX = {
    char: tuple(suffix for suffix in ROOT_INVERSION_SUFFIXES if suffix.endswith(char))
    for char in {suffix[-1] for suffix in ROOT_INVERSION_SUFFIXES}
}


def has_complete_comparative_boundary(
    phrase: str,
    comparative_hits: Iterable[tuple[str, str, str]],
) -> bool:
    patterns = tuple(pattern for pattern, _category, _root in comparative_hits)
    for pattern in patterns:
        start = 0
        while True:
            index = phrase.find(pattern, start)
            if index < 0:
                break
            before = phrase[:index]
            after = phrase[index + len(pattern) :]
            if not before and not after:
                return True
            prefix_ok = before in COMPARATIVE_CONTEXT_PREFIXES or any(
                before.endswith(item) for item in COMPARATIVE_CONTEXT_PREFIXES
            )
            suffix_ok = not after or after in COMPARATIVE_COMPLETE_SUFFIXES
            # A bare comparative stem may stand at the start, or be attached
            # to a known discourse prefix.  Arbitrary prefixes such as
            # "成更稳" and "文更自然" are fixed-width fragments, even when
            # the final two characters happen to look evaluative.
            if not before and suffix_ok:
                return True
            if prefix_ok and suffix_ok:
                return True
            start = index + 1
    return False


def has_complete_boundary(
    phrase: str,
    *,
    markers: Iterable[str] = (),
    allow_start: bool = True,
) -> bool:
    """Reject fixed-width conversational fragments while keeping full shells."""
    marker_set = tuple(markers)
    if phrase.endswith(COMPLETE_ENDINGS) or phrase.endswith(COMPLETE_FRAGMENT_SUFFIXES):
        return True
    if any(phrase.startswith(prefix) for prefix in FRAGMENT_PREFIXES):
        return False
    if phrase.endswith(FRAGMENT_ENDINGS):
        return False
    if any(phrase == marker or phrase.endswith(marker) for marker in marker_set):
        return True
    if allow_start and phrase.startswith(COMPLETE_STARTS):
        return True
    return False


def classify_compound_root_candidate(
    phrase: str,
    coverage: int,
) -> tuple[str | None, list[str], str]:
    """Admit only exact, auditable collocations around confirmed compound roots."""
    if not 2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH or not HAN_EXACT_RE.fullmatch(phrase):
        return None, [], "invalid_shape"
    if coverage < 20:
        return None, [], "chat_coverage_lt_20"
    if (
        phrase in NOISE_EXACT
        or phrase in FORBIDDEN_FINAL_FRAGMENTS
        or phrase in SUBPHRASE_FRAGMENT_EXACT
        or phrase[0] in BAD_EDGE
        or phrase[-1] in BAD_EDGE
    ):
        return None, [], "compound_root_noise_or_fragment"

    matches: list[tuple[str, str]] = []
    for stem, category in COMPOUND_ROOT_PATTERNS.items():
        start = 0
        while True:
            index = phrase.find(stem, start)
            if index < 0:
                break
            before = phrase[:index]
            after = phrase[index + len(stem) :]
            if before in COMPOUND_ROOT_PREFIXES and after in COMPOUND_ROOT_SUFFIXES:
                matches.append((stem, category))
            start = index + 1
    if not matches:
        return None, [], "compound_root_boundary"

    category = min(
        (item[1] for item in matches),
        key=lambda item: CATEGORY_ORDER.index(item),
    )
    triggers = sorted({item[0] for item in matches}, key=lambda item: (-len(item), item))
    return category, triggers, "eligible_compound_root_family"


def has_raw_core_family_boundary(phrase: str, core_hits: Iterable[str]) -> bool:
    """High-recall shape gate for families seeded by corpus short cores.

    This gate deliberately does not decide lexical completeness.  It removes
    known structural fragments before the expensive rescan; exact left/right
    contexts in current chats and documents make the final decision.
    """
    if not 2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH or not HAN_EXACT_RE.fullmatch(phrase):
        return False
    if (
        phrase in NOISE_EXACT
        or phrase in ROOT_FAMILY_NOISE_EXACT
        or phrase in FORBIDDEN_FINAL_FRAGMENTS
        or phrase in SUBPHRASE_FRAGMENT_EXACT
        or len(set(phrase)) == 1
        or phrase[0] in BAD_EDGE
        or phrase[-1] in BAD_EDGE
        or phrase.startswith(ROOT_FAMILY_BAD_PREFIXES)
        or phrase.endswith(ROOT_FAMILY_BAD_SUFFIXES)
        or any(phrase.startswith(prefix) for prefix in BAD_PREFIXES)
        or phrase.endswith(FRAGMENT_ENDINGS)
    ):
        return False
    roots = tuple(core_hits)
    if not roots:
        return False
    if phrase in roots or has_complete_boundary(phrase, markers=roots):
        return True
    # A core at either edge is a plausible complete family shell.  Fixed
    # n-gram cuts are still rejected later unless live contexts show real
    # boundaries or several independent neighbours.
    return any(phrase.startswith(root) or phrase.endswith(root) for root in roots)


def has_root_family_boundary(
    phrase: str,
    root_hits: Iterable[str],
    markers: dict[str, str],
) -> bool:
    """Require a multi-character style marker or an explicit root shell."""
    if len(phrase) < 3:
        return False
    if phrase.startswith(ROOT_FAMILY_BAD_PREFIXES) or phrase.endswith(
        ROOT_FAMILY_BAD_SUFFIXES
    ):
        return False
    roots = tuple(root_hits)
    if not roots:
        return False
    strong_markers = [
        token
        for token, _category, _start in embedded_markers(phrase, markers)
        if len(token) >= 2 and token != phrase
    ]
    if phrase in ROOT_FAMILY_NOISE_EXACT:
        return False
    rooted_markers = [
        token for token in strong_markers if any(root in token for root in roots)
    ]
    if rooted_markers:
        return has_complete_boundary(phrase, markers=rooted_markers)
    shell_roots = [root for root in roots if root in SINGLE_ROOT_MANUAL_ALLOW]
    return any(
        (
            any(phrase.startswith(prefix + root) for prefix in ROOT_SHELL_PREFIXES)
            or any(phrase.startswith(root) and phrase.endswith(suffix) for suffix in ROOT_SHELL_SUFFIXES)
        )
        for root in shell_roots
    )


def _segment_known_affixes(text: str, affixes: tuple[str, ...]) -> tuple[str, ...] | None:
    """Return a complete left-to-right segmentation, never a partial match."""
    if not text:
        return ()
    paths: dict[int, tuple[str, ...]] = {0: ()}
    for start in range(len(text)):
        path = paths.get(start)
        if path is None:
            continue
        for affix in affixes:
            if text.startswith(affix, start):
                end = start + len(affix)
                candidate = (*path, affix)
                current = paths.get(end)
                if current is None or (len(candidate), candidate) < (len(current), current):
                    paths[end] = candidate
    return paths.get(len(text))


def classify_root_inversion_family_shapes(
    phrase: str,
    root_hits: Iterable[str],
) -> tuple[list[dict[str, Any]], str]:
    """Classify root matches without equating a fixed-width edge with a word.

    `reversible_shell` means the complete candidate can be rebuilt from known
    discourse affixes and the root. `exact_root` is a multi-character root
    standing alone. `edge_context_pending` is only a recall state: exact live
    source contexts must later prove that the unknown modifier is not a clipped
    neighbour. A bare edge is therefore evidence to rescan, never evidence to
    publish.
    """
    if not 2 <= len(phrase) <= 12 or not HAN_EXACT_RE.fullmatch(phrase):
        return [], "invalid_shape"
    if (
        phrase in NOISE_EXACT
        or phrase in ROOT_FAMILY_NOISE_EXACT
        or phrase in FORBIDDEN_FINAL_FRAGMENTS
        or phrase in SUBPHRASE_FRAGMENT_EXACT
        or len(set(phrase)) == 1
        or phrase.startswith(ROOT_FAMILY_BAD_PREFIXES)
        or phrase.endswith(ROOT_FAMILY_BAD_SUFFIXES)
        or any(phrase.startswith(prefix) for prefix in BAD_PREFIXES)
        or phrase.endswith(FRAGMENT_ENDINGS)
    ):
        return [], "known_noise_or_fragment"
    shapes: list[dict[str, Any]] = []
    for root in root_hits:
        start = phrase.find(root)
        while start >= 0:
            end = start + len(root)
            if phrase == root and len(root) >= 2:
                shapes.append(
                    {
                        "root": root,
                        "gate_kind": "exact_root",
                        "prefix": "",
                        "suffix": "",
                        "prefix_parts": [],
                        "suffix_parts": [],
                    }
                )
            else:
                before = phrase[:start]
                after = phrase[end:]
                prefix_parts = _segment_known_affixes(before, ROOT_INVERSION_PREFIXES)
                suffix_parts = _segment_known_affixes(after, ROOT_INVERSION_SUFFIXES)
                if (
                    prefix_parts is not None
                    and suffix_parts is not None
                    and (prefix_parts or suffix_parts)
                ):
                    shapes.append(
                        {
                            "root": root,
                            "gate_kind": "reversible_shell",
                            "prefix": before,
                            "suffix": after,
                            "prefix_parts": list(prefix_parts),
                            "suffix_parts": list(suffix_parts),
                        }
                    )
                elif len(root) >= 2 and (start == 0 or end == len(phrase)):
                    shapes.append(
                        {
                            "root": root,
                            "gate_kind": "edge_context_pending",
                            "prefix": before,
                            "suffix": after,
                            "prefix_parts": list(prefix_parts or ()),
                            "suffix_parts": list(suffix_parts or ()),
                        }
                    )
                elif len(root) >= 2:
                    # High-recall route for a root repeatedly hidden inside
                    # larger phrases.  This state only reaches exact rescan;
                    # publication still requires live boundaries and a complete
                    # style-bearing outer shell.
                    shapes.append(
                        {
                            "root": root,
                            "gate_kind": "context_envelope_pending",
                            "prefix": before,
                            "suffix": after,
                            "prefix_parts": list(prefix_parts or ()),
                            "suffix_parts": list(suffix_parts or ()),
                        }
                    )
            start = phrase.find(root, start + 1)
    if not shapes:
        return [], "root_match_without_complete_shell_or_edge"
    priority = {
        "reversible_shell": 4,
        "exact_root": 3,
        "edge_context_pending": 2,
        "context_envelope_pending": 1,
    }
    shapes.sort(
        key=lambda item: (
            -priority[str(item["gate_kind"])],
            -len(str(item["root"])),
            str(item["root"]),
            str(item["prefix"]),
            str(item["suffix"]),
        )
    )
    return shapes, "eligible_root_inversion_recall"


def has_root_inversion_family_boundary(
    phrase: str,
    root_hits: Iterable[str],
) -> bool:
    """Compatibility wrapper for the staged root-family classifier."""
    shapes, _reason = classify_root_inversion_family_shapes(phrase, root_hits)
    return bool(shapes)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(path))


def canonical_path_set_sha256(paths: Iterable[Path | str]) -> str:
    payload = json.dumps(
        sorted({normalized_path(path) for path in paths}),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload)


def snapshot_file_set_sha256(files: Iterable[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted(
            (
                normalized_path(str(item["path"])),
                int(item["size"]),
                int(item["mtime_ns"]),
            )
            for item in files
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload)


def phrase_score(occurrences: int, coverage: int, phrase: str) -> float:
    return round(2.0 * math.log1p(coverage) + math.log1p(occurrences) + 0.18 * len(phrase), 6)


@dataclass(slots=True)
class Node:
    next: dict[str, int]
    fail: int
    outputs: list[int]


class AhoMatcher:
    def __init__(self, phrases: list[str]) -> None:
        self.phrases = phrases
        self.nodes = [Node({}, 0, [])]
        for index, phrase in enumerate(phrases):
            state = 0
            for char in phrase:
                target = self.nodes[state].next.get(char)
                if target is None:
                    target = len(self.nodes)
                    self.nodes[state].next[char] = target
                    self.nodes.append(Node({}, 0, []))
                state = target
            self.nodes[state].outputs.append(index)
        queue: deque[int] = deque(self.nodes[0].next.values())
        while queue:
            state = queue.popleft()
            for char, target in self.nodes[state].next.items():
                queue.append(target)
                fail = self.nodes[state].fail
                while fail and char not in self.nodes[fail].next:
                    fail = self.nodes[fail].fail
                self.nodes[target].fail = self.nodes[fail].next.get(char, 0)
                self.nodes[target].outputs.extend(self.nodes[self.nodes[target].fail].outputs)

    def matches(self, text: str) -> Iterator[int]:
        for index, _end in self.matches_with_end(text):
            yield index

    def matches_with_end(self, text: str) -> Iterator[tuple[int, int]]:
        state = 0
        for end, char in enumerate(text, start=1):
            while state and char not in self.nodes[state].next:
                state = self.nodes[state].fail
            state = self.nodes[state].next.get(char, 0)
            for index in self.nodes[state].outputs:
                yield index, end


@dataclass
class SubphraseEvidence:
    parents: set[str] = field(default_factory=set)
    source_kinds: set[str] = field(default_factory=set)
    categories: Counter[str] = field(default_factory=Counter)
    weighted_categories: Counter[str] = field(default_factory=Counter)
    left_contexts: Counter[str] = field(default_factory=Counter)
    right_contexts: Counter[str] = field(default_factory=Counter)


@dataclass
class DocumentNgramEvidence:
    occurrences: int = 0
    unit_coverage: int = 0
    file_coverage: int = 0
    left_contexts: Counter[str] = field(default_factory=Counter)
    right_contexts: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class RootProbeEvidence:
    """Lightweight coverage-one evidence retained before context expansion."""

    exact_occurrences: int = 0
    exact_message_coverage: int = 0
    short_parent_count: int = 0
    short_parent_weighted_occurrences: int = 0
    short_parent_weighted_coverage: int = 0
    max_short_parent_coverage: int = 0


@dataclass
class RootInversionEvidence:
    # Exact parent strings are retained only for bounded/confirmed inputs.
    # Aggregate parents are unique rows, so retaining every string in every
    # root set wastes gigabytes without adding evidence.  The counters below
    # preserve the full graph cardinalities while examples remain bounded.
    parents: set[str] = field(default_factory=set)
    shell_parents: set[str] = field(default_factory=set)
    confirmed_parents: set[str] = field(default_factory=set)
    source_parent_pairs: set[tuple[str, str]] = field(default_factory=set)
    sources: Counter[str] = field(default_factory=Counter)
    categories: Counter[str] = field(default_factory=Counter)
    weighted_categories: Counter[str] = field(default_factory=Counter)
    shells: Counter[str] = field(default_factory=Counter)
    comparative_shell_parents: set[str] = field(default_factory=set)
    comparative_shells: Counter[str] = field(default_factory=Counter)
    positions: Counter[str] = field(default_factory=Counter)
    left_contexts: Counter[str] = field(default_factory=Counter)
    right_contexts: Counter[str] = field(default_factory=Counter)
    left_context_windows: Counter[str] = field(default_factory=Counter)
    right_context_windows: Counter[str] = field(default_factory=Counter)
    context_envelopes: Counter[str] = field(default_factory=Counter)
    detailed_context_parent_evidence_count: int = 0
    omitted_detailed_context_parent_evidence_count: int = 0
    weighted_occurrences: int = 0
    weighted_coverage: int = 0
    shell_weighted_occurrences: int = 0
    shell_weighted_coverage: int = 0
    comparative_shell_weighted_occurrences: int = 0
    comparative_shell_weighted_coverage: int = 0
    max_parent_coverage: int = 0
    example_parents: list[tuple[int, int, str]] = field(default_factory=list)
    parent_evidence_count: int = 0
    shell_parent_evidence_count: int = 0
    confirmed_parent_evidence_count: int = 0
    comparative_shell_parent_evidence_count: int = 0
    direct_seed_parents: Counter[str] = field(default_factory=Counter)
    direct_seed_weighted_occurrences: Counter[str] = field(default_factory=Counter)
    direct_seed_weighted_coverage: Counter[str] = field(default_factory=Counter)
    direct_exact_occurrences: Counter[str] = field(default_factory=Counter)
    direct_exact_coverage: Counter[str] = field(default_factory=Counter)
    empirical_shells: Counter[str] = field(default_factory=Counter)
    empirical_shell_weighted_coverages: Counter[str] = field(
        default_factory=Counter
    )
    empirical_shell_parent_count: int = 0
    empirical_shell_type_count: int = 0
    empirical_shell_weighted_coverage: int = 0


class EmpiricalShellStore:
    """Exact, disk-backed root-to-shell counts for the full aggregate graph."""

    FLUSH_KEYS = 200_000
    QUERY_CHUNK = 400

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.unlink(missing_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=FILE;
            PRAGMA cache_size=-32768;
            PRAGMA locking_mode=EXCLUSIVE;
            CREATE TABLE empirical_shells (
                root TEXT NOT NULL,
                shell TEXT NOT NULL,
                parent_count INTEGER NOT NULL,
                weighted_coverage INTEGER NOT NULL,
                PRIMARY KEY (root, shell)
            ) WITHOUT ROWID;
            """
        )
        self.pending: dict[tuple[str, str], tuple[int, int]] = {}
        self.observations = 0
        self.flushes = 0

    @staticmethod
    def _chunks(values: Iterable[str], size: int) -> Iterator[list[str]]:
        chunk: list[str] = []
        for value in values:
            chunk.append(value)
            if len(chunk) == size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def add(
        self,
        root: str,
        shell: str,
        parent_count: int,
        weighted_coverage: int,
    ) -> None:
        key = (root, shell)
        old_parent_count, old_coverage = self.pending.get(key, (0, 0))
        self.pending[key] = (
            old_parent_count + parent_count,
            old_coverage + weighted_coverage,
        )
        self.observations += parent_count
        if len(self.pending) >= self.FLUSH_KEYS:
            self.flush()

    def flush(self) -> None:
        if not self.pending:
            return
        self.connection.executemany(
            """
            INSERT INTO empirical_shells(
                root, shell, parent_count, weighted_coverage
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(root, shell) DO UPDATE SET
                parent_count = parent_count + excluded.parent_count,
                weighted_coverage = weighted_coverage + excluded.weighted_coverage
            """,
            (
                (root, shell, parent_count, weighted_coverage)
                for (root, shell), (parent_count, weighted_coverage)
                in self.pending.items()
            ),
        )
        self.connection.commit()
        self.pending.clear()
        self.flushes += 1

    def finalize(self) -> None:
        self.flush()

    def root_type_counts(self) -> dict[str, int]:
        return {
            str(root): int(count)
            for root, count in self.connection.execute(
                "SELECT root, COUNT(*) FROM empirical_shells GROUP BY root"
            )
        }

    def seed_root_map(self, roots: Iterable[str]) -> dict[str, set[str]]:
        result: dict[str, set[str]] = defaultdict(set)
        for chunk in self._chunks(sorted(set(roots)), self.QUERY_CHUNK):
            placeholders = ",".join("?" for _ in chunk)
            query = (
                "SELECT root, shell FROM empirical_shells "
                f"WHERE root IN ({placeholders})"
            )
            for root, shell in self.connection.execute(query, chunk):
                result[str(shell)].add(str(root))
        return result

    def shell_root_counts(self, shells: Iterable[str]) -> Counter[str]:
        wanted = set(shells)
        result: Counter[str] = Counter()
        for (shell,) in self.connection.execute(
            "SELECT shell FROM empirical_shells"
        ):
            shell = str(shell)
            if shell in wanted:
                result[shell] += 1
        return result

    def hydrate_style_shells(
        self,
        evidence: dict[str, RootInversionEvidence],
        shells: Iterable[str],
    ) -> None:
        wanted = set(shells)
        for root, shell, parent_count, weighted_coverage in (
            self.connection.execute(
                "SELECT root, shell, parent_count, weighted_coverage "
                "FROM empirical_shells"
            )
        ):
            shell = str(shell)
            if shell not in wanted:
                continue
            item = evidence.get(str(root))
            if item is None:
                continue
            item.empirical_shells[shell] = int(parent_count)
            item.empirical_shell_weighted_coverages[shell] = int(
                weighted_coverage
            )

    def row_count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM empirical_shells"
        ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self.connection.close()


@dataclass
class RawShortCoreEvidence:
    phrase: str
    aggregate_occurrences: int
    aggregate_coverage: int
    aggregate_coverage_rate: float
    basic_reason: str
    family_parent_count: int = 0
    styled_parent_count: int = 0
    marker_categories: Counter[str] = field(default_factory=Counter)
    weighted_marker_categories: Counter[str] = field(default_factory=Counter)
    left_contexts: Counter[str] = field(default_factory=Counter)
    right_contexts: Counter[str] = field(default_factory=Counter)
    discourse_prefix_parent_count: int = 0
    discourse_suffix_parent_count: int = 0
    discourse_attachment_parent_count: int = 0
    max_parent_coverage: int = 0
    example_parent_phrases: list[tuple[int, str]] = field(default_factory=list)


def length_bucket(phrase: str) -> str:
    length = len(phrase)
    if length <= 4:
        return str(length)
    if length <= 6:
        return "5-6"
    if length <= 8:
        return "7-8"
    return "9-12"


def candidate_sort_key(row: dict[str, Any]) -> tuple[float, int, int, int, str]:
    return (
        float(row.get("discovery_score", row.get("combined_score", 0.0))),
        int(row.get("aggregate_chat_message_coverage", row.get("combined_coverage", 0))),
        int(row.get("aggregate_chat_occurrences", row.get("combined_occurrences", 0))),
        len(str(row["phrase"])),
        str(row["phrase"]),
    )


def merge_candidate(
    candidates: dict[str, dict[str, Any]], row: dict[str, Any]
) -> None:
    """Keep the strongest discovery route while retaining all route names."""
    phrase = str(row["phrase"])
    incoming = dict(row)
    incoming_sources = set(incoming.get("source_kinds", []))
    incoming_sources.add(str(incoming["source_kind"]))
    current = candidates.get(phrase)
    if current is None:
        incoming["source_kinds"] = sorted(incoming_sources)
        candidates[phrase] = incoming
        return

    current_sources = set(current.get("source_kinds", []))
    current_sources.add(str(current["source_kind"]))
    all_sources = sorted(current_sources | incoming_sources)
    current_rank = SOURCE_PRIORITY.get(str(current["source_kind"]), 0)
    incoming_rank = SOURCE_PRIORITY.get(str(incoming["source_kind"]), 0)
    if (incoming_rank, candidate_sort_key(incoming)) > (
        current_rank,
        candidate_sort_key(current),
    ):
        incoming["source_kinds"] = all_sources
        candidates[phrase] = incoming
    else:
        current["source_kinds"] = all_sources


def publication_candidate_allowed(
    row: dict[str, Any], *, root_closure_only: bool
) -> bool:
    if not root_closure_only:
        return True
    return row.get("source_kind") not in {
        "parent-subphrase-pass2",
        "csv-decomposition-pass6",
        "independent-longphrase-pass2",
    }


def counter_dominance(counter: Counter[str]) -> float:
    total = sum(counter.values())
    return round(max(counter.values(), default=0) / total, 8) if total else 1.0


def counter_entropy(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    return round(
        -sum((count / total) * math.log2(count / total) for count in counter.values()),
        8,
    )


def exact_context_metrics(
    prefix: str,
    left: Counter[str],
    right: Counter[str],
) -> dict[str, Any]:
    left_total = sum(left.values())
    right_total = sum(right.values())
    left_nonboundary = Counter({key: value for key, value in left.items() if key != "^"})
    right_nonboundary = Counter({key: value for key, value in right.items() if key != "$"})
    return {
        f"{prefix}_left_context_count": len(left),
        f"{prefix}_right_context_count": len(right),
        f"{prefix}_left_boundary_rate": round(left.get("^", 0) / left_total, 8)
        if left_total
        else 0.0,
        f"{prefix}_right_boundary_rate": round(right.get("$", 0) / right_total, 8)
        if right_total
        else 0.0,
        f"{prefix}_left_nonboundary_dominance": counter_dominance(left_nonboundary),
        f"{prefix}_right_nonboundary_dominance": counter_dominance(right_nonboundary),
        f"{prefix}_left_contexts": dict(left.most_common(16)),
        f"{prefix}_right_contexts": dict(right.most_common(16)),
    }


def relative_discourse_attachment(
    parent: str,
    start: int,
    end: int,
) -> tuple[bool, bool]:
    """Return whether a core is immediately governed by a discourse shell."""
    before = parent[:start]
    after = parent[end:]
    prefix_attached = any(
        before.endswith(prefix)
        for prefix in (*DISCOURSE_ATTACHMENT_PREFIXES, *ROOT_INVERSION_PREFIXES)
    )
    suffix_attached = any(
        after.startswith(suffix)
        for suffix in (*DISCOURSE_ATTACHMENT_SUFFIXES, *ROOT_INVERSION_SUFFIXES)
    )
    return prefix_attached, suffix_attached


def phrase_has_relative_discourse_attachment(phrase: str, core: str) -> bool:
    """Check every in-phrase occurrence instead of inheriting a root's status."""
    start = phrase.find(core)
    while start >= 0:
        prefix, suffix = relative_discourse_attachment(
            phrase,
            start,
            start + len(core),
        )
        if prefix or suffix:
            return True
        start = phrase.find(core, start + 1)
    return False


def raw_short_basic_reason(phrase: str) -> str:
    if len(phrase) not in {2, 3} or not HAN_EXACT_RE.fullmatch(phrase):
        return "invalid_shape"
    if phrase in NOISE_EXACT or len(set(phrase)) == 1:
        return "function_or_noise_exact"
    if phrase in SUBPHRASE_FRAGMENT_EXACT or phrase in FORBIDDEN_FINAL_FRAGMENTS:
        return "known_fragment"
    if phrase[0] in BAD_EDGE or phrase[-1] in BAD_EDGE:
        return "function_character_edge"
    if any(phrase.startswith(prefix) for prefix in BAD_PREFIXES):
        return "known_fragment_prefix"
    if phrase.endswith(FRAGMENT_ENDINGS):
        return "fragment_ending"
    return "eligible_basic_shape"


def strip_markup(text: str, suffix: str) -> str:
    text = CODE_FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = URL_PATH_RE.sub(" ", text)
    if suffix == ".tex":
        text = TEX_COMMENT_RE.sub("", text)
        text = TEX_ENV_RE.sub(" ", text)
        text = TEX_DISPLAY_MATH_RE.sub(" ", text)
        text = TEX_INLINE_MATH_RE.sub(" ", text)
        text = TEX_COMMAND_RE.sub(" ", text)
        text = text.replace("{", " ").replace("}", " ")
    return text


def semantic_units(text: str, suffix: str) -> Iterator[str]:
    cleaned = strip_markup(text, suffix)
    for coarse in UNIT_SPLIT_RE.split(cleaned):
        coarse = re.sub(r"\s+", "", coarse)
        parts = re.split(r"[，,、]", coarse) if len(coarse) > 120 else [coarse]
        for part in parts:
            # Keep independent Han runs separate. Joining runs would
            # manufacture n-grams across punctuation, ASCII, or removed TeX
            # markup (for example two Han runs becoming one false phrase).
            yield from HAN_RUN_RE.findall(part)


def clean_chat_text(text: str) -> Iterator[str]:
    cleaned = URL_PATH_RE.sub(" ", INLINE_CODE_RE.sub(" ", CODE_FENCE_RE.sub(" ", text)))
    yield from HAN_RUN_RE.findall(cleaned)


def usable_subphrase(phrase: str, evidence: SubphraseEvidence) -> tuple[bool, str]:
    if not 2 <= len(phrase) <= 6 or not HAN_EXACT_RE.fullmatch(phrase):
        return False, "invalid_shape"
    if phrase in NOISE_EXACT or len(set(phrase)) == 1:
        return False, "function_or_noise_exact"
    if phrase in SUBPHRASE_FRAGMENT_EXACT:
        return False, "known_subphrase_fragment"
    if phrase[0] in BAD_EDGE or phrase[-1] in BAD_EDGE:
        return False, "function_character_edge"
    parent_count = len(evidence.parents)
    if len(phrase) == 2 and parent_count < 3:
        return False, "two_char_parent_coverage_lt_3"
    if len(phrase) >= 3 and parent_count < 2:
        return False, "parent_coverage_lt_2"
    left = set(evidence.left_contexts)
    right = set(evidence.right_contexts)
    if "^" not in left and len(left) < 2:
        return False, "fixed_left_fragment"
    if "$" not in right and len(right) < 2:
        return False, "fixed_right_fragment"
    if any(phrase.startswith(prefix) for prefix in BAD_PREFIXES):
        return False, "known_fragment_prefix"
    return True, "eligible"


def generate_subphrase_candidates(entries: list[dict[str, Any]]) -> dict[str, SubphraseEvidence]:
    existing = {str(entry["phrase"]) for entry in entries}
    evidence: dict[str, SubphraseEvidence] = defaultdict(SubphraseEvidence)
    for entry in entries:
        parent = str(entry["phrase"])
        category = str(entry["category"])
        weight = max(1, int(entry.get("combined_occurrences", 1)))
        for start in range(len(parent)):
            for length in range(2, min(6, len(parent) - start) + 1):
                phrase = parent[start : start + length]
                if phrase in existing:
                    continue
                item = evidence[phrase]
                item.source_kinds.add(
                    str(entry.get("_decomposition_source", "baseline-parent"))
                )
                item.parents.add(parent)
                item.categories[category] += 1
                item.weighted_categories[category] += weight
                item.left_contexts[parent[start - 1] if start else "^"] += 1
                end = start + length
                item.right_contexts[parent[end] if end < len(parent) else "$"] += 1
    return evidence


def load_csv_decomposition_parents(
    paths: Iterable[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Read prior candidate CSVs as parent phrases for a second-pass split.

    The CSV is only a discovery source: it contributes parent phrase evidence,
    never a direct strict entry.  Every extracted child is rescanned against
    the current frozen chat/document snapshots later in the pipeline.
    """
    best: dict[str, dict[str, Any]] = {}
    stats = Counter()
    for path in paths:
        stats["csv_files_seen"] += 1
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                stats["csv_rows_scanned"] += 1
                phrase = str(raw.get("phrase", ""))
                if not 4 <= len(phrase) <= 12 or not HAN_EXACT_RE.fullmatch(phrase):
                    stats["rows_rejected_shape"] += 1
                    continue
                try:
                    coverage = int(raw.get("combined_coverage", 0) or 0)
                    occurrences = int(raw.get("combined_occurrences", 0) or 0)
                except (TypeError, ValueError):
                    stats["rows_rejected_numeric"] += 1
                    continue
                if coverage < DECOMPOSITION_MIN_PARENT_COVERAGE:
                    stats["rows_rejected_coverage"] += 1
                    continue
                if occurrences < DECOMPOSITION_MIN_PARENT_OCCURRENCES:
                    stats["rows_rejected_occurrences"] += 1
                    continue
                stats["parents_eligible_before_cap"] += 1
                candidate = {
                    "phrase": phrase,
                    "category": str(raw.get("category", "audit-governance")),
                    "combined_coverage": coverage,
                    "combined_occurrences": occurrences,
                    "_decomposition_source": "csv-decomposition-pass6",
                    "_decomposition_csv": str(path),
                }
                previous = best.get(phrase)
                if previous is None or (
                    coverage,
                    occurrences,
                ) > (
                    int(previous["combined_coverage"]),
                    int(previous["combined_occurrences"]),
                ):
                    best[phrase] = candidate
    parents = sorted(
        best.values(),
        key=lambda row: (
            -int(row["combined_coverage"]),
            -int(row["combined_occurrences"]),
            row["phrase"],
        ),
    )
    stats["parent_phrases_deduplicated"] = len(parents)
    if (
        DECOMPOSITION_PARENT_LIMIT is not None
        and len(parents) > DECOMPOSITION_PARENT_LIMIT
    ):
        stats["parents_truncated_to_limit"] = len(parents) - DECOMPOSITION_PARENT_LIMIT
        parents = parents[:DECOMPOSITION_PARENT_LIMIT]
    else:
        stats["parents_truncated_to_limit"] = 0
    manifest = [
        {
            "path": row["_decomposition_csv"],
            "phrase": row["phrase"],
            "category": row["category"],
            "combined_coverage": row["combined_coverage"],
            "combined_occurrences": row["combined_occurrences"],
            "source_kind": row["_decomposition_source"],
        }
        for row in parents
    ]
    stats["parent_phrases_selected"] = len(parents)
    return parents, manifest, dict(stats)


def root_inversion_category(
    parent: str,
    prefix: str,
    suffix: str,
    markers: dict[str, str],
    fallback: str = "audit-governance",
) -> str:
    if prefix in ROOT_INVERSION_COMPARATIVE_PREFIXES or suffix:
        return "certainty-limitation"
    if prefix in {
        "再", "继续", "重新", "再次", "同步", "逐步", "逐渐", "开始", "停止",
        "先", "随后", "最终", "最后",
    }:
        return "process-broadcast"
    if prefix in {
        "必须", "应当", "应该", "需要", "务必", "只需", "无需", "不再", "不能",
        "不得", "避免", "确保", "严格", "要", "应", "不", "必须进一步",
        "需要进一步",
    }:
        return "scope-boundary"
    if prefix in {"建议", "可以", "尝试", "适当", "可"}:
        return "recommendation-outlook"
    if prefix in {"这样", "这样做", "这样写", "这样说", "会", "将会", "能够"}:
        return "certainty-limitation"
    if prefix in markers:
        return markers[prefix]
    embedded = embedded_markers(parent, markers)
    if embedded:
        scores: Counter[str] = Counter()
        for token, category, _start in embedded:
            scores[category] += len(token) * len(token)
        return min(
            scores,
            key=lambda category: (-scores[category], CATEGORY_ORDER.index(category)),
        )
    return fallback if fallback in CATEGORY_ORDER else "audit-governance"


def root_inversion_residuals(
    parent: str,
    markers: dict[str, str],
    *,
    fallback_category: str = "audit-governance",
) -> list[tuple[str, str, str, str]]:
    """Return 1-3 character roots left after removing complete shells."""
    if not 2 <= len(parent) <= 12 or not HAN_EXACT_RE.fullmatch(parent):
        return []
    prefixes = [""]
    prefixes.extend(
        prefix
        for prefix in ROOT_INVERSION_PREFIX_INDEX.get(parent[0], ())
        if parent.startswith(prefix)
    )
    suffixes = [""]
    suffixes.extend(
        suffix
        for suffix in ROOT_INVERSION_SUFFIX_INDEX.get(parent[-1], ())
        if parent.endswith(suffix)
    )
    found: dict[tuple[str, str, str], str] = {}
    for prefix in prefixes:
        for suffix in suffixes:
            if not prefix and not suffix:
                continue
            start = len(prefix)
            end = len(parent) - len(suffix) if suffix else len(parent)
            if end <= start:
                continue
            root = parent[start:end]
            if not 1 <= len(root) <= 3 or not HAN_EXACT_RE.fullmatch(root):
                continue
            category = root_inversion_category(
                parent, prefix, suffix, markers, fallback_category
            )
            found[(root, prefix, suffix)] = category
    return [
        (root, prefix, suffix, found[(root, prefix, suffix)])
        for root, prefix, suffix in sorted(found)
    ]


def root_window_attachment(
    parent: str,
    root: str,
    markers: dict[str, str],
    *,
    fallback_category: str = "audit-governance",
) -> tuple[str | None, str]:
    """Find the strongest observed discourse attachment around a root window.

    Unlike ``root_inversion_residuals``, this does not require the whole parent
    to be exactly ``prefix + root + suffix``.  A root hidden in a longer phrase
    can therefore be discovered from an immediate attachment such as the
    ``继续`` in ``继续补齐真实样本``.  The returned shell is discovery evidence;
    it never makes the bare root publishable.
    """
    best: tuple[int, str, str, str] | None = None
    start = parent.find(root)
    while start >= 0:
        end = start + len(root)
        before = parent[:start]
        after = parent[end:]
        prefix = next(
            (item for item in ROOT_INVERSION_PREFIXES if before.endswith(item)),
            "",
        )
        suffix = next(
            (item for item in ROOT_INVERSION_SUFFIXES if after.startswith(item)),
            "",
        )
        if prefix or suffix:
            category = root_inversion_category(
                parent,
                prefix,
                suffix,
                markers,
                fallback_category,
            )
            candidate = (len(prefix) + len(suffix), prefix, suffix, category)
            if best is None or candidate > best:
                best = candidate
        start = parent.find(root, start + 1)
    if best is None:
        return None, root_inversion_category(
            parent,
            "",
            "",
            markers,
            fallback_category,
        )
    _length, prefix, suffix, category = best
    return f"{prefix or '^'}|{suffix or '$'}", category


def root_inversion_basic_reason(root: str) -> str:
    if not 1 <= len(root) <= 3 or not HAN_EXACT_RE.fullmatch(root):
        return "invalid_shape"
    if len(set(root)) == 1 and len(root) > 1:
        return "repeated_character_noise"
    if root in STRICT_RELEASE_PROTECTED_CONTENT:
        return "protected_content_exact"
    if root in STRICT_RELEASE_FUNCTION_OR_GENERIC or root in NOISE_EXACT:
        return "function_or_generic_exact"
    if (
        root in STRICT_RELEASE_FRAGMENTS
        or root in SUBPHRASE_FRAGMENT_EXACT
        or root in FORBIDDEN_FINAL_FRAGMENTS
    ):
        return "known_fragment"
    if len(root) == 1 and root in ROOT_INVERSION_HARD_SINGLE_STOP:
        return "hard_function_character_stoplist"
    if len(root) == 1 and root in SINGLE_ROOT_STOP and root not in SINGLE_ROOT_MANUAL_ALLOW:
        return "function_character_stoplist"
    if (
        len(root) > 1
        and (root[0] in BAD_EDGE or root[-1] in BAD_EDGE)
        and not root.startswith(tuple(ROOT_INVERSION_COMPARATIVE_PREFIXES))
    ):
        return "function_character_edge"
    return "eligible_basic_shape"


def _record_root_inversion_parent(
    evidence: dict[str, RootInversionEvidence],
    *,
    root: str,
    parent: str,
    category: str,
    source: str,
    occurrences: int,
    coverage: int,
    shell: str | None,
    confirmed: bool,
    retain_parent_identity: bool = True,
    retain_detailed_contexts: bool = True,
    empirical_shell_store: EmpiricalShellStore | None = None,
) -> None:
    item = evidence[root]
    first_parent = not retain_parent_identity or parent not in item.parents
    source_parent_pair = (source, parent)
    first_source_parent = (
        not retain_parent_identity
        or source_parent_pair not in item.source_parent_pairs
    )
    first_shell_parent = bool(shell) and (
        not retain_parent_identity or parent not in item.shell_parents
    )
    comparative_shell = False
    if shell:
        prefix, _separator, _suffix = shell.partition("|")
        comparative_shell = prefix in ROOT_INVERSION_COMPARATIVE_PREFIXES
    first_comparative_parent = (
        comparative_shell
        and (
            not retain_parent_identity
            or parent not in item.comparative_shell_parents
        )
    )
    if retain_parent_identity:
        item.parents.add(parent)
        item.source_parent_pairs.add(source_parent_pair)
    if shell:
        if retain_parent_identity:
            item.shell_parents.add(parent)
        item.shells[shell] += 1
        if first_shell_parent:
            item.shell_parent_evidence_count += 1
            item.shell_weighted_occurrences += max(1, occurrences)
            item.shell_weighted_coverage += max(1, coverage)
        if comparative_shell:
            if retain_parent_identity:
                item.comparative_shell_parents.add(parent)
            item.comparative_shells[shell] += 1
            if first_comparative_parent:
                item.comparative_shell_parent_evidence_count += 1
                item.comparative_shell_weighted_occurrences += max(1, occurrences)
                item.comparative_shell_weighted_coverage += max(1, coverage)
    if confirmed:
        if retain_parent_identity:
            item.confirmed_parents.add(parent)
        if first_parent:
            item.confirmed_parent_evidence_count += 1
    if first_source_parent:
        item.sources[source] += 1
    if first_parent:
        item.parent_evidence_count += 1
        item.categories[category] += 1
        item.weighted_categories[category] += max(1, coverage)
        item.weighted_occurrences += max(1, occurrences)
        item.weighted_coverage += max(1, coverage)
        item.max_parent_coverage = max(item.max_parent_coverage, coverage)
        example = (coverage, occurrences, parent)
        if len(item.example_parents) < 24:
            heapq.heappush(item.example_parents, example)
        elif example > item.example_parents[0]:
            heapq.heapreplace(item.example_parents, example)
    empirical_shells: set[str] = set()
    start = parent.find(root)
    while start >= 0:
        end = start + len(root)
        before = parent[:start]
        after = parent[end:]
        item.positions[
            "whole" if start == 0 and end == len(parent) else "start" if start == 0 else "end" if end == len(parent) else "middle"
        ] += 1
        item.left_contexts[parent[start - 1] if start else "^"] += 1
        item.right_contexts[parent[end] if end < len(parent) else "$"] += 1
        if retain_detailed_contexts:
            for width in range(1, min(12, len(before)) + 1):
                item.left_context_windows[before[-width:]] += 1
            for width in range(1, min(12, len(after)) + 1):
                item.right_context_windows[after[:width]] += 1
            if before or after:
                envelope = (
                    f"{before[-6:] if before else '^'}|"
                    f"{after[:6] if after else '$'}"
                )
                item.context_envelopes[envelope] += 1
        if before and not after and len(before) <= 6:
            empirical_shells.add(f"L:{before}")
        elif after and not before and len(after) <= 6:
            empirical_shells.add(f"R:{after}")
        elif before and after and len(before) + len(after) <= 6:
            empirical_shells.add(f"B:{before}|{after}")
        start = parent.find(root, start + 1)
    if first_parent:
        if retain_detailed_contexts:
            item.detailed_context_parent_evidence_count += 1
        else:
            item.omitted_detailed_context_parent_evidence_count += 1
    if first_parent and empirical_shells:
        item.empirical_shell_parent_count += 1
        item.empirical_shell_weighted_coverage += max(1, coverage)
        for empirical_shell in empirical_shells:
            if empirical_shell_store is None:
                item.empirical_shells[empirical_shell] += 1
                item.empirical_shell_weighted_coverages[empirical_shell] += max(
                    1, coverage
                )
            else:
                empirical_shell_store.add(
                    root,
                    empirical_shell,
                    1,
                    max(1, coverage),
                )


def discover_aggregate_root_probes(
    aggregate_path: Path,
    *,
    required_roots: set[str] | None = None,
    context_graph_allowlist: set[str] | None = None,
    audit_path: Path | None = None,
) -> tuple[dict[str, RootProbeEvidence], dict[str, int]]:
    """Audit every observed 1-3 character root before graph thresholds.

    The coverage-one probe is deliberately lightweight.  It prevents a graph
    or publication threshold from making a root invisible, while only roots
    with repeated evidence allocate the heavier context counters used later.
    """
    required = required_roots or set()
    probes: dict[str, RootProbeEvidence] = {}
    stats = Counter()
    with aggregate_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stats["aggregate_root_probe_rows_scanned"] += 1
            item = json.loads(raw)
            parent = str(item.get("phrase", ""))
            coverage = int(item.get("message_coverage", 0))
            if (
                coverage < ROOT_PROBE_MIN_COVERAGE
                or not 1 <= len(parent) <= ROOT_FIRST_PARENT_MAX_LENGTH
                or not HAN_EXACT_RE.fullmatch(parent)
            ):
                continue
            occurrences = int(item.get("count", 0))
            if len(parent) <= 3:
                exact = probes.setdefault(parent, RootProbeEvidence())
                exact.exact_occurrences = max(
                    exact.exact_occurrences, occurrences
                )
                exact.exact_message_coverage = max(
                    exact.exact_message_coverage, coverage
                )
                roots = {
                    parent[start : start + length]
                    for length in (1, 2, 3)
                    if len(parent) >= length
                    for start in range(len(parent) - length + 1)
                }
                stats["aggregate_root_probe_short_rows"] += 1
            else:
                # Every long parent creates every 1-3 character root window.
                # Earlier versions only admitted known 2/3-character roots,
                # which made an unseen root impossible to discover from its
                # own collocations (for example, a new root inside a longer
                # process phrase).  Publication gates remain downstream.
                roots = {
                    parent[start : start + length]
                    for length in (1, 2, 3)
                    for start in range(len(parent) - length + 1)
                }
                stats["aggregate_root_probe_long_parent_all_windows_rows"] += 1
            for root in roots:
                probe = probes.setdefault(root, RootProbeEvidence())
                probe.short_parent_count += 1
                probe.short_parent_weighted_occurrences += max(1, occurrences)
                probe.short_parent_weighted_coverage += max(1, coverage)
                probe.max_short_parent_coverage = max(
                    probe.max_short_parent_coverage, coverage
                )

    graph_probes: dict[str, RootProbeEvidence] = {}
    audit_handle = None
    writer = None
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_handle = audit_path.open("w", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(
            audit_handle,
            fieldnames=[
                "root",
                "root_length",
                "basic_reason",
                "exact_chat_occurrences",
                "exact_chat_message_coverage",
                "short_parent_count",
                "short_parent_weighted_occurrences",
                "short_parent_weighted_coverage",
                "max_short_parent_coverage",
                "required_by_prior_evidence",
                "root_graph_selected",
                "root_graph_decision",
            ],
        )
        writer.writeheader()
    try:
        for root, probe in probes.items():
            reason = root_inversion_basic_reason(root)
            required_hint = root in required
            shape_allowed = reason == "eligible_basic_shape" or (
                required_hint
                and reason in {
                    "function_character_edge",
                    "function_character_stoplist",
                }
            )
            exact_ready = (
                probe.exact_message_coverage >= ROOT_GRAPH_EXACT_MIN_COVERAGE
            )
            single_ready = (
                len(root) == 1
                and probe.short_parent_count >= ROOT_GRAPH_SINGLE_MIN_PARENT_COUNT
            )
            embedded_ready = (
                probe.short_parent_count >= ROOT_GRAPH_EMBEDDED_MIN_PARENT_COUNT
                and probe.short_parent_weighted_coverage
                >= ROOT_GRAPH_EMBEDDED_MIN_WEIGHTED_COVERAGE
            )
            selected = shape_allowed and (
                required_hint or exact_ready or single_ready or embedded_ready
            )
            allowlisted = (
                context_graph_allowlist is None
                or root in context_graph_allowlist
                or required_hint
            )
            selected = selected and allowlisted
            status_audit_retained = (
                not selected
                and probe.short_parent_count > 0
                and (
                    len(root) == 1
                    or reason
                    in {
                        "protected_content_exact",
                        "function_or_generic_exact",
                        "known_fragment",
                        "hard_function_character_stoplist",
                        "repeated_character_noise",
                    }
                )
            )
            if selected:
                decision = (
                    "selected_required_prior_evidence"
                    if required_hint
                    else "selected_exact_coverage"
                    if exact_ready
                    else "selected_single_root_parent_diversity"
                    if single_ready
                    else "selected_embedded_short_parent_evidence"
                )
                graph_probes[root] = probe
                stats["aggregate_root_probes_selected_for_context_graph"] += 1
                stats[f"aggregate_root_probe_selected_length/{len(root)}"] += 1
            elif not allowlisted:
                decision = "audit_only:not_in_context_graph_allowlist"
                stats[
                    "aggregate_root_probes_excluded_by_context_graph_allowlist"
                ] += 1
            elif status_audit_retained:
                decision = f"audit_only_retained_for_status:{reason}"
                graph_probes[root] = probe
                stats["aggregate_root_probes_retained_for_status_audit"] += 1
                stats["aggregate_root_probes_audit_only"] += 1
            else:
                decision = (
                    f"audit_only:{reason}"
                    if not shape_allowed
                    else "audit_only:below_context_graph_evidence"
                )
                stats["aggregate_root_probes_audit_only"] += 1
            stats["aggregate_root_probes_observed"] += 1
            stats[f"aggregate_root_probe_basic_reason/{reason}"] += 1
            if writer is not None:
                writer.writerow(
                    {
                        "root": root,
                        "root_length": len(root),
                        "basic_reason": reason,
                        "exact_chat_occurrences": probe.exact_occurrences,
                        "exact_chat_message_coverage": (
                            probe.exact_message_coverage
                        ),
                        "short_parent_count": probe.short_parent_count,
                        "short_parent_weighted_occurrences": (
                            probe.short_parent_weighted_occurrences
                        ),
                        "short_parent_weighted_coverage": (
                            probe.short_parent_weighted_coverage
                        ),
                        "max_short_parent_coverage": (
                            probe.max_short_parent_coverage
                        ),
                        "required_by_prior_evidence": required_hint,
                        "root_graph_selected": selected,
                        "root_graph_decision": decision,
                    }
                )
    finally:
        if audit_handle is not None:
            audit_handle.close()
    stats["aggregate_root_probe_retained_evidence_size"] = len(graph_probes)
    return graph_probes, dict(stats)


def load_root_graph_allowlist(path: Path) -> set[str]:
    """Load selected roots plus generic roots with complete-shell evidence.

    A generic root remains ineligible as a bare strict phrase.  Excluding it
    from the context graph altogether, however, makes families such as
    ``更自然`` depend on a hand-written comparative-stem list.  The rescue
    route is evidence-only and requires the upstream exact/shell gates.
    """
    roots: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"root", "selected_for_targeted_long_scan"}
        if not required_fields <= set(reader.fieldnames or ()):
            raise ValueError(
                f"root selection audit lacks required fields {sorted(required_fields)}: {path}"
            )
        for row in reader:
            explicitly_selected = (
                str(row.get("selected_for_targeted_long_scan", "")).lower()
                == "true"
            )
            generic_complete_shell_rescue = (
                str(row.get("basic_reason", ""))
                == "function_or_generic_exact"
                and str(row.get("shell_ready", "")).lower() == "true"
                and str(row.get("exact_ready_for_long_scan", "")).lower()
                == "true"
                and str(row.get("immediate_extension_fragment", "")).lower()
                != "true"
            )
            if not (explicitly_selected or generic_complete_shell_rescue):
                continue
            root = str(row.get("root", ""))
            if not 1 <= len(root) <= 3 or not HAN_EXACT_RE.fullmatch(root):
                raise ValueError(f"invalid selected discovery root {root!r}: {path}")
            if root in roots:
                raise ValueError(f"duplicate selected discovery root {root!r}: {path}")
            roots.add(root)
    if not roots:
        raise ValueError(f"root selection audit selected no roots: {path}")
    return roots


def load_root_graph_fragment_blocklist(path: Path) -> set[str]:
    """Load roots whose immediate extension proves a clipped n-gram."""
    roots: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"root", "immediate_extension_fragment"}
        if not required_fields <= set(reader.fieldnames or ()):
            raise ValueError(
                f"root selection audit lacks fragment fields {sorted(required_fields)}: {path}"
            )
        for row in reader:
            if str(row.get("immediate_extension_fragment", "")).lower() != "true":
                continue
            root = str(row.get("root", ""))
            if 1 <= len(root) <= 3 and HAN_EXACT_RE.fullmatch(root):
                roots.add(root)
    return roots


def select_confirmed_parent_graph_roots(
    confirmed_parents: list[dict[str, Any]],
    markers: dict[str, str],
    external_allowlist: set[str],
    *,
    fragment_blocklist: set[str] | None = None,
    audit_path: Path | None = None,
) -> tuple[set[str], dict[str, int]]:
    """Promote repeated parent roots before allocating heavy context state."""
    parent_counts: Counter[str] = Counter()
    weighted_coverage: Counter[str] = Counter()
    categories: dict[str, set[str]] = defaultdict(set)
    shell_parent_counts: Counter[str] = Counter()
    shell_weighted_coverage: Counter[str] = Counter()
    trusted_direct_roots: set[str] = set()
    stats: Counter[str] = Counter()
    trusted_sources = {
        "baseline-v1",
        "raw-short-core-pass4",
    }
    for row in confirmed_parents:
        parent = str(row.get("phrase", ""))
        if not 2 <= len(parent) <= 12 or not HAN_EXACT_RE.fullmatch(parent):
            continue
        category = str(row.get("category", "audit-governance"))
        coverage = int(row.get("combined_coverage", 1) or 1)
        source = str(
            row.get("_decomposition_source", row.get("source_kind", "baseline-v1"))
        )
        seen: set[str] = set()
        for length in (1, 2, 3):
            for start in range(len(parent) - length + 1):
                root = parent[start : start + length]
                if root in seen:
                    continue
                seen.add(root)
                parent_counts[root] += 1
                weighted_coverage[root] += max(1, coverage)
                categories[root].add(category)
        if len(parent) <= 3 and source in trusted_sources:
            trusted_direct_roots.add(parent)
        residual_seen: set[str] = set()
        for root, _prefix, _suffix, _shell_category in root_inversion_residuals(
            parent, markers, fallback_category=category
        ):
            if root in residual_seen:
                continue
            residual_seen.add(root)
            shell_parent_counts[root] += 1
            shell_weighted_coverage[root] += max(1, coverage)
        stats["confirmed_parent_probe_rows"] += 1

    selected = set(external_allowlist)
    minimum_parents = {1: 24, 2: 12, 3: 10}
    minimum_categories = {1: 4, 2: 3, 3: 3}
    minimum_weighted_coverage = {1: 1500, 2: 1000, 3: 600}
    minimum_shell_parents = {1: 4, 2: 3, 3: 3}
    minimum_shell_coverage = {1: 500, 2: 200, 3: 100}
    writer = None
    audit_handle = None
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_handle = audit_path.open("w", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(
            audit_handle,
            fieldnames=[
                "root",
                "root_length",
                "basic_reason",
                "parent_count",
                "weighted_parent_coverage",
                "category_count",
                "shell_parent_count",
                "shell_weighted_coverage",
                "immediate_extension_fragment",
                "external_allowlist",
                "trusted_direct_root",
                "repeated_parent_ready",
                "reversible_shell_ready",
                "selected_for_heavy_graph",
                "selection_route",
            ],
        )
        writer.writeheader()
    for root, parent_count in parent_counts.items():
        reason = root_inversion_basic_reason(root)
        external_ready = root in external_allowlist
        extension_fragment = root in (fragment_blocklist or set())
        shape_allowed = external_ready or (
            reason == "eligible_basic_shape" and not extension_fragment
        )
        repeated_parent_ready = (
            shape_allowed
            and parent_count >= minimum_parents[len(root)]
            and len(categories[root]) >= minimum_categories[len(root)]
            and weighted_coverage[root] >= minimum_weighted_coverage[len(root)]
        )
        reversible_shell_ready = (
            shape_allowed
            and shell_parent_counts[root] >= minimum_shell_parents[len(root)]
            and shell_weighted_coverage[root] >= minimum_shell_coverage[len(root)]
        )
        trusted_direct_ready = (
            shape_allowed and root in trusted_direct_roots and len(root) >= 2
        )
        routes = [
            route
            for route, ready in (
                ("external_chat_shell", external_ready),
                ("trusted_short_core", trusted_direct_ready),
                ("repeated_confirmed_parent", repeated_parent_ready),
                ("reversible_confirmed_shell", reversible_shell_ready),
            )
            if ready
        ]
        keep = bool(routes)
        if keep:
            selected.add(root)
            stats[f"confirmed_root_selection_route/{'+'.join(routes)}"] += 1
            stats[f"confirmed_roots_selected_length/{len(root)}"] += 1
        else:
            stats["confirmed_parent_roots_light_audit_only"] += 1
            if extension_fragment:
                stats["confirmed_parent_roots_blocked_as_immediate_fragments"] += 1
        if writer is not None:
            writer.writerow(
                {
                    "root": root,
                    "root_length": len(root),
                    "basic_reason": reason,
                    "parent_count": parent_count,
                    "weighted_parent_coverage": weighted_coverage[root],
                    "category_count": len(categories[root]),
                    "shell_parent_count": shell_parent_counts[root],
                    "shell_weighted_coverage": shell_weighted_coverage[root],
                    "immediate_extension_fragment": extension_fragment,
                    "external_allowlist": external_ready,
                    "trusted_direct_root": trusted_direct_ready,
                    "repeated_parent_ready": repeated_parent_ready,
                    "reversible_shell_ready": reversible_shell_ready,
                    "selected_for_heavy_graph": keep,
                    "selection_route": "+".join(routes) if routes else "light_audit_only",
                }
            )
    if audit_handle is not None:
        audit_handle.close()
    stats["confirmed_parent_roots_observed"] = len(parent_counts)
    stats["confirmed_parent_trusted_direct_roots"] = len(trusted_direct_roots)
    stats["confirmed_parent_roots_selected_for_heavy_graph"] = len(selected)
    stats["confirmed_parent_weighted_coverage_total"] = sum(weighted_coverage.values())
    return selected, dict(stats)


def _record_root_direct_seed(
    evidence: dict[str, RootInversionEvidence],
    *,
    root: str,
    parent: str,
    source: str,
    occurrences: int,
    coverage: int,
) -> None:
    """Record an exact 2/3-gram seed without treating it as a ban.

    The short row establishes that the root is observable independently of a
    hand-written lexicon.  Parent diversity and complete family boundaries are
    evaluated later; summing short-row support here is discovery evidence only.
    """
    item = evidence[root]
    item.direct_seed_parents[source] += 1
    item.direct_seed_weighted_occurrences[source] += max(1, occurrences)
    item.direct_seed_weighted_coverage[source] += max(1, coverage)
    if parent == root:
        item.direct_exact_occurrences[source] = max(
            item.direct_exact_occurrences[source], max(1, occurrences)
        )
        item.direct_exact_coverage[source] = max(
            item.direct_exact_coverage[source], max(1, coverage)
        )


def discover_root_inversion(
    aggregate_path: Path,
    existing_entries: list[dict[str, Any]],
    confirmed_parents: list[dict[str, Any]],
    document_root_rows: list[dict[str, Any]] | None = None,
    *,
    root_probe_audit_path: Path | None = None,
    confirmed_root_probe_audit_path: Path | None = None,
    aggregate_root_allowlist: set[str] | None = None,
    aggregate_root_fragment_blocklist: set[str] | None = None,
    empirical_shell_db_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Invert complete parents into discovery roots without emitting bare roots."""
    markers = marker_map(existing_entries)
    evidence: dict[str, RootInversionEvidence] = defaultdict(RootInversionEvidence)
    stats = Counter()
    empirical_shell_store = (
        EmpiricalShellStore(empirical_shell_db_path)
        if empirical_shell_db_path is not None
        else None
    )
    bounded_graph = aggregate_root_allowlist is not None
    if bounded_graph:
        heavy_graph_roots, confirmed_probe_stats = select_confirmed_parent_graph_roots(
            confirmed_parents,
            markers,
            set(aggregate_root_allowlist or ()),
            fragment_blocklist=set(aggregate_root_fragment_blocklist or ()),
            audit_path=confirmed_root_probe_audit_path,
        )
        stats.update(confirmed_probe_stats)
        stats["external_root_graph_allowlist"] = len(aggregate_root_allowlist or ())
    else:
        heavy_graph_roots = set()

    # Confirmed strict/candidate parents contribute every 1-3 character window.
    # This route is lower-trust than a discourse residual and therefore needs
    # more independent parents at the publication gate below.
    for row in confirmed_parents:
        parent = str(row.get("phrase", ""))
        if not 2 <= len(parent) <= 12 or not HAN_EXACT_RE.fullmatch(parent):
            continue
        category = str(row.get("category", "audit-governance"))
        occurrences = int(row.get("combined_occurrences", 1) or 1)
        coverage = int(row.get("combined_coverage", 1) or 1)
        source = str(row.get("_decomposition_source", row.get("source_kind", "baseline-v1")))
        seen: set[str] = set()
        for length in (1, 2, 3):
            for start in range(len(parent) - length + 1):
                root = parent[start : start + length]
                if root in seen:
                    continue
                seen.add(root)
                if bounded_graph and root not in heavy_graph_roots:
                    continue
                _record_root_inversion_parent(
                    evidence,
                    root=root,
                    parent=parent,
                    category=category,
                    source=source,
                    occurrences=occurrences,
                    coverage=coverage,
                    shell=None,
                    confirmed=True,
                    empirical_shell_store=empirical_shell_store,
                )
        for root, prefix, suffix, shell_category in root_inversion_residuals(
            parent, markers, fallback_category=category
        ):
            if bounded_graph and root not in heavy_graph_roots:
                continue
            _record_root_inversion_parent(
                evidence,
                root=root,
                parent=parent,
                category=shell_category,
                source=source,
                occurrences=occurrences,
                coverage=coverage,
                shell=f"{prefix or '^'}|{suffix or '$'}",
                confirmed=True,
                empirical_shell_store=empirical_shell_store,
            )
        stats["confirmed_parents_scanned"] += 1

    # MD/TeX supplies an independent observation of each root.  It changes
    # source coverage, not the publication decision; a bare root remains an
    # audit key even when it is common in documents.
    for row in document_root_rows or []:
        root = str(row.get("root", row.get("phrase", "")))
        if not 1 <= len(root) <= 3 or not HAN_EXACT_RE.fullmatch(root):
            continue
        if bounded_graph and root not in heavy_graph_roots:
            stats["document_root_rows_retained_in_light_audit_only"] += 1
            continue
        occurrences = int(row.get("document_root_occurrences", 0) or 0)
        coverage = int(row.get("document_root_unit_coverage", 0) or 0)
        _record_root_direct_seed(
            evidence,
            root=root,
            parent=root,
            source="document-root-graph-pass9",
            occurrences=occurrences,
            coverage=coverage,
        )
        _record_root_inversion_parent(
            evidence,
            root=root,
            parent=root,
            category=str(row.get("category", "audit-governance")),
            source="document-root-graph-pass9",
            occurrences=occurrences,
            coverage=coverage,
            shell=None,
            confirmed=True,
            empirical_shell_store=empirical_shell_store,
        )
        stats["document_root_rows_linked"] += 1

    # Coverage-one roots are written to a lightweight audit before any graph
    # gate is applied.  Only repeated or prior-evidenced roots allocate the
    # heavier context counters below; this separates visibility from release.
    graph_probes, probe_stats = discover_aggregate_root_probes(
        aggregate_path,
        required_roots=set(evidence),
        context_graph_allowlist=(heavy_graph_roots if bounded_graph else None),
        audit_path=root_probe_audit_path,
    )
    stats.update(probe_stats)
    for root, probe in graph_probes.items():
        item = evidence[root]
        item.direct_seed_parents["aggregate-root-probe"] += (
            probe.short_parent_count
        )
        item.direct_seed_weighted_occurrences["aggregate-root-probe"] += (
            probe.short_parent_weighted_occurrences
        )
        item.direct_seed_weighted_coverage["aggregate-root-probe"] += (
            probe.short_parent_weighted_coverage
        )
        if probe.exact_message_coverage:
            item.direct_exact_occurrences["aggregate-root-probe"] = (
                probe.exact_occurrences
            )
            item.direct_exact_coverage["aggregate-root-probe"] = (
                probe.exact_message_coverage
            )
        item.sources["aggregate-root-probe"] += 1
        stats["aggregate_direct_root_seed_observations"] += 1

    root_universe = set(evidence)
    stats["root_universe_size_before_parent_graph"] = len(root_universe)

    # Pass B links every high-coverage 2-12 character parent to the root
    # universe.  Parent strings are not retained for aggregate rows; exact
    # edge counts, contexts, empirical shells and bounded examples are.
    with aggregate_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stats["aggregate_rows_scanned"] += 1
            item = json.loads(raw)
            parent = str(item.get("phrase", ""))
            coverage = int(item.get("message_coverage", 0))
            if (
                coverage < ROOT_FIRST_PARENT_MIN_COVERAGE
                or not 2 <= len(parent) <= ROOT_FIRST_PARENT_MAX_LENGTH
                or not HAN_EXACT_RE.fullmatch(parent)
                or not root_universe
            ):
                continue
            occurrences = int(item.get("count", 0))
            roots = {
                parent[start : start + length]
                for length in (1, 2, 3)
                if len(parent) >= length
                for start in range(len(parent) - length + 1)
                if parent[start : start + length] in root_universe
            }
            parent_has_shell = False
            for root in roots:
                shell, category = root_window_attachment(parent, root, markers)
                parent_has_shell = parent_has_shell or shell is not None
                _record_root_inversion_parent(
                    evidence,
                    root=root,
                    parent=parent,
                    category=category,
                    source="aggregate-root-window",
                    occurrences=occurrences,
                    coverage=coverage,
                    shell=shell,
                    confirmed=False,
                    retain_parent_identity=False,
                    retain_detailed_contexts=False,
                    empirical_shell_store=empirical_shell_store,
                )
                stats["aggregate_root_window_observations"] += 1
            stats["aggregate_root_first_parents"] += 1
            if parent_has_shell:
                stats["aggregate_dynamic_shell_parents"] += 1

    style_seed_roots = {
        phrase
        for phrase in (
            set(markers)
            | set(STRICT_RELEASE_DISCOVERY_ROOT_ONLY)
            | set(STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES)
            | set(STRICT_RELEASE_SHORT_LITERALS)
            | set(SINGLE_ROOT_MANUAL_ALLOW)
        )
        if 1 <= len(phrase) <= 3
        and phrase not in STRICT_RELEASE_PROTECTED_CONTENT
        and phrase not in STRICT_RELEASE_FUNCTION_OR_GENERIC
        and phrase not in STRICT_RELEASE_FRAGMENTS
    }
    shell_seed_roots: dict[str, set[str]] = defaultdict(set)
    shell_all_root_counts: Counter[str] = Counter()
    if empirical_shell_store is None:
        for item in evidence.values():
            item.empirical_shell_type_count = len(item.empirical_shells)
            shell_all_root_counts.update(item.empirical_shells.keys())
        for root in style_seed_roots:
            item = evidence.get(root)
            if item is None:
                continue
            for shell in item.empirical_shells:
                shell_seed_roots[shell].add(root)
    else:
        empirical_shell_store.finalize()
        for root, type_count in empirical_shell_store.root_type_counts().items():
            item = evidence.get(root)
            if item is not None:
                item.empirical_shell_type_count = type_count
        shell_seed_roots.update(
            empirical_shell_store.seed_root_map(style_seed_roots)
        )
        shell_all_root_counts.update(
            empirical_shell_store.shell_root_counts(shell_seed_roots)
        )
    observed_style_seed_count = sum(root in evidence for root in style_seed_roots)
    global_style_seed_rate = _ratio(observed_style_seed_count, len(evidence))
    shell_lift_reference_rate = min(
        global_style_seed_rate, ROOT_FIRST_STYLE_SHELL_GLOBAL_RATE_CAP
    )
    style_bearing_shells: set[str] = set()
    style_shell_quality: dict[str, dict[str, float | int]] = {}
    for shell, roots in shell_seed_roots.items():
        all_root_count = shell_all_root_counts[shell]
        seed_root_count = len(roots)
        seed_ratio = _ratio(seed_root_count, all_root_count)
        seed_lift = _ratio(seed_ratio, shell_lift_reference_rate)
        if (
            seed_root_count >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_ROOTS
            and seed_ratio >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_RATIO
            and seed_lift >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_LIFT
        ):
            style_bearing_shells.add(shell)
            style_shell_quality[shell] = {
                "all_root_count": all_root_count,
                "seed_root_count": seed_root_count,
                "seed_ratio": seed_ratio,
                "seed_lift": seed_lift,
            }
    stats["style_seed_roots_configured"] = len(style_seed_roots)
    stats["style_seed_roots_observed"] = observed_style_seed_count
    stats["global_style_seed_rate_ppm"] = round(
        global_style_seed_rate * 1_000_000
    )
    stats["style_shell_lift_reference_rate_ppm"] = round(
        shell_lift_reference_rate * 1_000_000
    )
    stats["empirical_shells_linked_to_style_seeds"] = len(shell_seed_roots)
    stats["style_bearing_empirical_shells"] = len(style_bearing_shells)
    if empirical_shell_store is not None:
        empirical_shell_store.hydrate_style_shells(
            evidence, style_bearing_shells
        )
        stats["empirical_shell_store_rows"] = empirical_shell_store.row_count()
        stats["empirical_shell_store_observations"] = (
            empirical_shell_store.observations
        )
        stats["empirical_shell_store_flushes"] = empirical_shell_store.flushes
        stats["empirical_shell_store_disk_backed"] = 1
        empirical_shell_store.close()
    else:
        stats["empirical_shell_store_disk_backed"] = 0

    rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for root, item in evidence.items():
        parent_count = item.parent_evidence_count
        shell_parent_count = item.shell_parent_evidence_count
        confirmed_parent_count = item.confirmed_parent_evidence_count
        shell_type_count = len(item.shells)
        comparative_shell_parent_count = item.comparative_shell_parent_evidence_count
        comparative_shell_type_count = len(item.comparative_shells)
        empirical_shell_parent_count = item.empirical_shell_parent_count
        empirical_shell_type_count = item.empirical_shell_type_count
        shell_parent_ratio = _ratio(shell_parent_count, parent_count)
        shell_coverage_ratio = _ratio(
            item.shell_weighted_coverage, item.weighted_coverage
        )
        category_count = len(item.categories)
        reason = root_inversion_basic_reason(root)
        general_shell_ready = (
            shell_parent_count >= ROOT_INVERSION_MIN_SHELL_PARENT_COUNT[len(root)]
            and shell_type_count >= ROOT_INVERSION_MIN_SHELL_TYPE_COUNT[len(root)]
            and item.shell_weighted_coverage
            >= ROOT_INVERSION_MIN_WEIGHTED_COVERAGE[len(root)]
            and shell_parent_ratio
            >= ROOT_FIRST_KNOWN_SHELL_MIN_PARENT_RATIO[len(root)]
            and shell_coverage_ratio
            >= ROOT_FIRST_KNOWN_SHELL_MIN_COVERAGE_RATIO[len(root)]
        )
        single_comparative_ready = (
            comparative_shell_parent_count
            >= ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_PARENTS
            and comparative_shell_type_count
            >= ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_TYPES
            and item.comparative_shell_weighted_coverage
            >= ROOT_INVERSION_SINGLE_MIN_COMPARATIVE_COVERAGE
        )
        shell_ready = general_shell_ready and (
            len(root) > 1 or single_comparative_ready
        )
        confirmed_minimum = 8 if len(root) == 1 else 4 if len(root) == 2 else 3
        confirmed_ready = (
            confirmed_parent_count >= confirmed_minimum and category_count >= 2
        )
        chat_source_ready = any(
            item.sources.get(source, 0) > 0 for source in ROOT_FIRST_CHAT_SOURCES
        )
        document_source_ready = any(
            item.sources.get(source, 0) > 0 for source in ROOT_FIRST_DOCUMENT_SOURCES
        )
        cross_source_parent_ready = chat_source_ready and document_source_ready
        independently_sourced_parent_ready = (
            chat_source_ready or document_source_ready
        )
        context_diverse = (
            len(item.left_contexts) >= ROOT_FIRST_MIN_SIDE_TYPES
            and len(item.right_contexts) >= ROOT_FIRST_MIN_SIDE_TYPES
            and counter_dominance(item.left_contexts)
            <= ROOT_FIRST_MAX_SIDE_DOMINANCE
            and counter_dominance(item.right_contexts)
            <= ROOT_FIRST_MAX_SIDE_DOMINANCE
        )
        root_first_shell_ready = (
            shell_parent_count >= ROOT_FIRST_MIN_SHELL_PARENT_COUNT[len(root)]
            and shell_type_count >= ROOT_FIRST_MIN_SHELL_TYPE_COUNT[len(root)]
            and item.shell_weighted_coverage
            >= ROOT_FIRST_MIN_SHELL_WEIGHTED_COVERAGE[len(root)]
            and shell_parent_ratio
            >= ROOT_FIRST_KNOWN_SHELL_MIN_PARENT_RATIO[len(root)]
            and shell_coverage_ratio
            >= ROOT_FIRST_KNOWN_SHELL_MIN_COVERAGE_RATIO[len(root)]
        )
        root_first_counts_ready = (
            parent_count >= ROOT_FIRST_MIN_PARENT_COUNT[len(root)]
            and item.weighted_coverage
            >= ROOT_FIRST_MIN_WEIGHTED_COVERAGE[len(root)]
        )
        empirical_shell_ready = (
            empirical_shell_parent_count
            >= ROOT_FIRST_MIN_EMPIRICAL_SHELL_PARENTS[len(root)]
            and empirical_shell_type_count
            >= ROOT_FIRST_MIN_EMPIRICAL_SHELL_TYPES[len(root)]
            and item.empirical_shell_weighted_coverage
            >= ROOT_FIRST_MIN_EMPIRICAL_SHELL_COVERAGE[len(root)]
        )
        leave_one_out_global_rate = _ratio(
            observed_style_seed_count - int(root in style_seed_roots),
            len(evidence) - 1,
        )
        leave_one_out_lift_reference_rate = min(
            leave_one_out_global_rate,
            ROOT_FIRST_STYLE_SHELL_GLOBAL_RATE_CAP,
        )
        style_shells: list[str] = []
        for shell in sorted(set(item.empirical_shells) & style_bearing_shells):
            seed_count_without_root = int(
                style_shell_quality[shell]["seed_root_count"]
            ) - int(root in shell_seed_roots[shell])
            all_count_without_root = max(
                0,
                int(style_shell_quality[shell]["all_root_count"]) - 1,
            )
            ratio_without_root = _ratio(
                seed_count_without_root, all_count_without_root
            )
            lift_without_root = _ratio(
                ratio_without_root, leave_one_out_lift_reference_rate
            )
            if (
                seed_count_without_root
                >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_ROOTS
                and ratio_without_root >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_RATIO
                and lift_without_root >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_LIFT
            ):
                style_shells.append(shell)
        style_shell_parent_count = sum(
            item.empirical_shells[shell] for shell in style_shells
        )
        style_shell_weighted_coverage = sum(
            item.empirical_shell_weighted_coverages[shell]
            for shell in style_shells
        )
        style_shell_seed_root_union = {
            seed_root
            for shell in style_shells
            for seed_root in shell_seed_roots[shell]
        } - {root}
        style_shell_parent_ratio = _ratio(
            style_shell_parent_count, empirical_shell_parent_count
        )
        style_shell_coverage_ratio = _ratio(
            style_shell_weighted_coverage,
            item.empirical_shell_weighted_coverage,
        )
        style_shell_ready = (
            len(style_shells) >= ROOT_FIRST_STYLE_SHELL_MIN_TYPES[len(root)]
            and style_shell_parent_count
            >= ROOT_FIRST_STYLE_SHELL_MIN_PARENTS[len(root)]
            and style_shell_weighted_coverage
            >= ROOT_FIRST_STYLE_SHELL_MIN_COVERAGE[len(root)]
            and len(style_shell_seed_root_union)
            >= ROOT_FIRST_STYLE_SHELL_MIN_SEED_ROOT_UNION[len(root)]
            and style_shell_parent_ratio
            >= ROOT_FIRST_STYLE_SHELL_MIN_PARENT_RATIO[len(root)]
            and style_shell_coverage_ratio
            >= ROOT_FIRST_STYLE_SHELL_MIN_COVERAGE_RATIO[len(root)]
        )
        direct_seed_parent_count = sum(item.direct_seed_parents.values())
        direct_seed_weighted_coverage = sum(
            item.direct_seed_weighted_coverage.values()
        )
        direct_exact_chat_coverage = int(
            item.direct_exact_coverage.get("aggregate-root-probe", 0)
        )
        direct_exact_document_coverage = int(
            item.direct_exact_coverage.get("document-root-graph-pass9", 0)
        )
        direct_root_observed_without_hint = (
            len(root) == 1
            or direct_exact_chat_coverage
            >= ROOT_GRAPH_EXACT_MIN_COVERAGE
            or direct_exact_document_coverage > 0
        )
        manual_root_hint = (
            root in STRICT_RELEASE_DISCOVERY_ROOT_ONLY
            or root in STRICT_RELEASE_SHORT_LITERALS
            or root in SINGLE_ROOT_MANUAL_ALLOW
        )
        direct_root_observed = direct_root_observed_without_hint or manual_root_hint
        strong_shell_ready = shell_ready and direct_root_observed_without_hint
        root_first_direct_shell_ready = (
            root_first_shell_ready and direct_root_observed_without_hint
        )
        empirical_direct_ready = (
            style_shell_ready
            and len(root) in ROOT_FIRST_EMPIRICAL_EXACT_MIN_COVERAGE
            and direct_exact_chat_coverage
            >= ROOT_FIRST_EMPIRICAL_EXACT_MIN_COVERAGE[len(root)]
        )
        single_empirical_ready = (
            len(root) == 1
            and direct_seed_parent_count >= ROOT_FIRST_SINGLE_MIN_DIRECT_PARENTS
            and direct_seed_weighted_coverage
            >= ROOT_FIRST_SINGLE_MIN_DIRECT_COVERAGE
            and style_shell_ready
        )
        data_only_context_ready = (
            root_first_counts_ready
            and context_diverse
            and (
                (independently_sourced_parent_ready and style_shell_ready)
                or root_first_direct_shell_ready
                or empirical_direct_ready
            )
        )
        manual_hint_context_ready = (
            manual_root_hint
            and root_first_counts_ready
            and context_diverse
        )
        confirmed_context_ready = (
            data_only_context_ready or manual_hint_context_ready
        )
        root_leave_one_out_ready = strong_shell_ready or data_only_context_ready
        root_manual_hint_used = (
            manual_hint_context_ready and not root_leave_one_out_ready
        )
        generic_complete_collocation_ready = (
            reason == "function_or_generic_exact"
            and single_comparative_ready
            and strong_shell_ready
        )
        if generic_complete_collocation_ready:
            reason = "eligible_basic_shape"
        if (
            reason == "function_character_stoplist"
            and len(root) == 1
            and (single_comparative_ready or single_empirical_ready)
        ):
            reason = "eligible_basic_shape"
        if (
            reason == "function_character_edge"
            and len(root) > 1
            and confirmed_context_ready
        ):
            reason = "eligible_basic_shape"
        if reason == "eligible_basic_shape":
            if parent_count < ROOT_INVERSION_MIN_PARENT_COUNT[len(root)]:
                reason = "parent_count_below_root_threshold"
            elif len(root) == 1 and not (
                single_comparative_ready or single_empirical_ready
            ):
                reason = "single_root_lacks_productive_shell_evidence"
            elif not strong_shell_ready and not confirmed_context_ready:
                reason = (
                    "confirmed_parent_only_audit"
                    if confirmed_ready
                    else "insufficient_shell_parent_diversity_or_coverage"
                )
            else:
                reason = "eligible_root_inversion"
        dominant_category = min(
            item.weighted_categories or Counter({"audit-governance": 1}),
            key=lambda category: (
                -item.weighted_categories.get(category, 0),
                CATEGORY_ORDER.index(category),
            ),
        )
        discovery_score = round(
            math.log1p(item.weighted_coverage)
            + 1.5 * math.log1p(parent_count)
            + math.log1p(shell_parent_count)
            + 0.6 * math.log1p(shell_type_count)
            + 0.4 * math.log1p(category_count),
            6,
        )
        row = {
            "root": root,
            "root_length": len(root),
            "root_status": reason,
            "root_discovery_mode": (
                "generic-comparative-shell-context"
                if generic_complete_collocation_ready
                else
                "shell-residual"
                if strong_shell_ready
                else "manual-hint-context"
                if root_manual_hint_used
                else "root-first-cross-source-context"
                if data_only_context_ready and cross_source_parent_ready
                else "root-first-empirical-shell-context"
                if data_only_context_ready and style_shell_ready
                else "root-first-chat-shell-context"
                if data_only_context_ready
                else "confirmed-parent-window"
                if confirmed_ready
                else "audit-only"
            ),
            "dominant_category": dominant_category,
            "parent_phrase_count": parent_count,
            "shell_parent_count": shell_parent_count,
            "confirmed_parent_count": confirmed_parent_count,
            "confirmed_context_ready": confirmed_context_ready,
            "data_only_context_ready": data_only_context_ready,
            "manual_hint_context_ready": manual_hint_context_ready,
            "manual_root_hint": manual_root_hint,
            "root_requires_complete_collocation": (
                root in STRICT_RELEASE_FUNCTION_OR_GENERIC
                or len(root) == 1
            ),
            "generic_complete_collocation_ready": (
                generic_complete_collocation_ready
            ),
            "root_leave_one_out_ready": root_leave_one_out_ready,
            "root_manual_hint_used": root_manual_hint_used,
            "root_first_counts_ready": root_first_counts_ready,
            "root_first_shell_ready": root_first_shell_ready,
            "root_first_direct_shell_ready": root_first_direct_shell_ready,
            "strong_shell_ready": strong_shell_ready,
            "empirical_shell_ready": empirical_shell_ready,
            "style_shell_ready": style_shell_ready,
            "empirical_direct_ready": empirical_direct_ready,
            "single_empirical_ready": single_empirical_ready,
            "chat_source_ready": chat_source_ready,
            "document_source_ready": document_source_ready,
            "cross_source_parent_ready": cross_source_parent_ready,
            "independently_sourced_parent_ready": (
                independently_sourced_parent_ready
            ),
            "context_diverse": context_diverse,
            "shell_type_count": shell_type_count,
            "shell_parent_ratio": shell_parent_ratio,
            "shell_coverage_ratio": shell_coverage_ratio,
            "comparative_shell_parent_count": comparative_shell_parent_count,
            "comparative_shell_type_count": comparative_shell_type_count,
            "parent_category_count": category_count,
            "parent_categories": sorted(item.categories),
            "parent_sources": dict(item.sources),
            "shells": dict(item.shells.most_common(24)),
            "empirical_shell_parent_count": empirical_shell_parent_count,
            "empirical_shell_type_count": empirical_shell_type_count,
            "empirical_shell_weighted_parent_coverage": (
                item.empirical_shell_weighted_coverage
            ),
            "empirical_shells": dict(item.empirical_shells.most_common(32)),
            "empirical_shell_examples_scope": (
                "style_bearing_shells_only"
                if empirical_shell_db_path is not None
                else "all_empirical_shells"
            ),
            "style_shell_type_count": len(style_shells),
            "style_shell_parent_count": style_shell_parent_count,
            "style_shell_weighted_coverage": style_shell_weighted_coverage,
            "style_shell_seed_root_union_count": len(
                style_shell_seed_root_union
            ),
            "style_shell_parent_ratio": style_shell_parent_ratio,
            "style_shell_coverage_ratio": style_shell_coverage_ratio,
            "style_shell_examples": style_shells[:32],
            "style_shell_quality_examples": {
                shell: style_shell_quality[shell]
                for shell in style_shells[:12]
            },
            "direct_seed_parent_count": direct_seed_parent_count,
            "direct_seed_parent_counts": dict(item.direct_seed_parents),
            "direct_seed_weighted_occurrences": dict(
                item.direct_seed_weighted_occurrences
            ),
            "direct_seed_weighted_coverage": dict(
                item.direct_seed_weighted_coverage
            ),
            "direct_exact_occurrences": dict(item.direct_exact_occurrences),
            "direct_exact_coverage": dict(item.direct_exact_coverage),
            "direct_exact_chat_coverage": direct_exact_chat_coverage,
            "direct_exact_document_coverage": direct_exact_document_coverage,
            "direct_root_observed_without_hint": (
                direct_root_observed_without_hint
            ),
            "direct_root_observed": direct_root_observed,
            "positions": dict(item.positions),
            "left_context_count": len(item.left_contexts),
            "right_context_count": len(item.right_contexts),
            "left_context_dominance": counter_dominance(item.left_contexts),
            "right_context_dominance": counter_dominance(item.right_contexts),
            "left_context_entropy": counter_entropy(item.left_contexts),
            "right_context_entropy": counter_entropy(item.right_contexts),
            "left_context_windows": dict(
                item.left_context_windows.most_common(64)
            ),
            "right_context_windows": dict(
                item.right_context_windows.most_common(64)
            ),
            "context_envelopes": dict(item.context_envelopes.most_common(64)),
            "detailed_context_scope": (
                "confirmed_and_document_parents_only"
                if item.omitted_detailed_context_parent_evidence_count
                else "all_recorded_parents"
            ),
            "detailed_context_parent_evidence_count": (
                item.detailed_context_parent_evidence_count
            ),
            "omitted_detailed_context_parent_evidence_count": (
                item.omitted_detailed_context_parent_evidence_count
            ),
            "weighted_parent_occurrences": item.weighted_occurrences,
            "weighted_parent_coverage": item.weighted_coverage,
            "shell_weighted_parent_occurrences": item.shell_weighted_occurrences,
            "shell_weighted_parent_coverage": item.shell_weighted_coverage,
            "comparative_shell_weighted_parent_occurrences": (
                item.comparative_shell_weighted_occurrences
            ),
            "comparative_shell_weighted_parent_coverage": (
                item.comparative_shell_weighted_coverage
            ),
            "max_parent_coverage": item.max_parent_coverage,
            "example_parent_phrases": [
                parent
                for _coverage, _occurrences, parent in sorted(
                    item.example_parents, reverse=True
                )
            ],
            "discovery_score": discovery_score,
        }
        rows.append(row)
        if reason == "eligible_root_inversion":
            selected.append(row)
        stats[f"root_status/{reason}"] += 1

    # Longer roots can explain much of a one-character root's evidence, but
    # that is a precision warning rather than a discovery veto.  Bare roots are
    # never published, so retaining the shorter root lets exact family and
    # technical-context gates decide whether any complete phrase is usable.
    longer_rows = [row for row in rows if int(row["root_length"]) > 1]
    for row in rows:
        if (
            row["root_status"] != "eligible_root_inversion"
            or int(row["root_length"]) != 1
        ):
            continue
        root = str(row["root"])
        explanatory = [
            candidate
            for candidate in longer_rows
            if (
                str(candidate["root"]).startswith(root)
                or str(candidate["root"]).endswith(root)
            )
            and candidate["root_status"]
            not in {
                "invalid_shape",
                "known_fragment",
                "function_character_edge",
                "repeated_character_noise",
            }
            and int(candidate.get("shell_weighted_parent_coverage", 0)) > 0
        ]
        explanatory.sort(
            key=lambda candidate: (
                int(candidate.get("shell_weighted_parent_coverage", 0)),
                len(str(candidate["root"])),
                str(candidate["root"]),
            ),
            reverse=True,
        )
        single_coverage = max(1, int(row["shell_weighted_parent_coverage"]))
        strongest = (
            int(explanatory[0]["shell_weighted_parent_coverage"])
            if explanatory
            else 0
        )
        top_three = sum(
            int(candidate["shell_weighted_parent_coverage"])
            for candidate in explanatory[:3]
        )
        max_ratio = _ratio(strongest, single_coverage)
        sum_ratio = _ratio(top_three, single_coverage)
        row["longer_root_max_coverage_ratio"] = max_ratio
        row["longer_root_top3_coverage_ratio"] = sum_ratio
        row["longer_root_explanations"] = [
            {
                "root": candidate["root"],
                "shell_weighted_parent_coverage": candidate[
                    "shell_weighted_parent_coverage"
                ],
                "root_status": candidate["root_status"],
            }
            for candidate in explanatory[:6]
        ]
        dominance_flag = (
            max_ratio >= ROOT_INVERSION_LONGER_ROOT_MAX_DOMINANCE
            or sum_ratio >= ROOT_INVERSION_LONGER_ROOT_SUM_DOMINANCE
            or (
                root not in SINGLE_ROOT_MANUAL_ALLOW
                and max_ratio >= ROOT_INVERSION_LONGER_ROOT_CONTEXT_RATIO
                and bool(explanatory[0].get("direct_root_observed"))
            )
        )
        row["longer_root_dominance_flag"] = dominance_flag
        if dominance_flag and explanatory:
            row["dominated_by_root"] = str(explanatory[0]["root"])

    selected = [
        row for row in rows if row["root_status"] == "eligible_root_inversion"
    ]
    for key in [key for key in stats if key.startswith("root_status/")]:
        del stats[key]
    for row in rows:
        stats[f"root_status/{row['root_status']}"] += 1
        stats[f"root_discovery_mode/{row['root_discovery_mode']}"] += 1
        if row["root_status"] == "eligible_root_inversion":
            stats[f"selected_root_length/{row['root_length']}"] += 1
            if row.get("style_shell_ready"):
                stats["selected_roots_with_style_shell_graph"] += 1
            if row.get("strong_shell_ready"):
                stats["selected_roots_with_known_shell"] += 1
            if row.get("cross_source_parent_ready"):
                stats["selected_roots_with_cross_source_evidence"] += 1
            if row.get("root_leave_one_out_ready"):
                stats["selected_roots_leave_one_out_ready"] += 1
            if row.get("root_manual_hint_used"):
                stats["selected_roots_dependent_on_manual_hint"] += 1

    rows.sort(
        key=lambda row: (
            row["root_status"] == "eligible_root_inversion",
            float(row["discovery_score"]),
            int(row["parent_phrase_count"]),
            len(str(row["root"])),
            str(row["root"]),
        ),
        reverse=True,
    )
    selected.sort(
        key=lambda row: (
            float(row["discovery_score"]),
            int(row["parent_phrase_count"]),
            len(str(row["root"])),
            str(row["root"]),
        ),
        reverse=True,
    )
    stats["roots_ranked"] = len(rows)
    stats["roots_selected_for_family_scan"] = len(selected)
    return selected, rows, dict(stats)


def build_single_root_evidence(
    entries: list[dict[str, Any]],
    aggregate_path: Path,
    seed_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank one-character roots before expanding their complete phrase families."""
    evidence: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "parent_phrases": set(),
            "categories": Counter(),
            "weighted_occurrences": 0,
            "weighted_coverage": 0,
            "positions": Counter(),
            "aggregate_count": 0,
            "aggregate_coverage": 0,
            "seed_phrases": set(),
            "seed_categories": Counter(),
        }
    )
    for entry in entries:
        phrase = str(entry["phrase"])
        weight = max(1, int(entry.get("combined_occurrences", 1)))
        coverage = max(1, int(entry.get("combined_coverage", 1)))
        category = str(entry["category"])
        for position, char in enumerate(phrase):
            item = evidence[char]
            item["parent_phrases"].add(phrase)
            item["categories"][category] += 1
            item["weighted_occurrences"] += weight
            item["weighted_coverage"] += coverage
            item["positions"]["start" if position == 0 else "end" if position == len(phrase) - 1 else "middle"] += 1

    # New short cores are independent discovery seeds.  Their characters are
    # allowed to enter the root ranking even when they never appeared in the
    # old inventory; this is what prevents the old list from defining the
    # universe of future discoveries.
    for row in seed_rows or []:
        phrase = str(row["phrase"])
        category = str(row["category"])
        weight = max(
            1,
            int(
                row.get(
                    "aggregate_chat_occurrences",
                    row.get("document_ngram_occurrences", 1),
                )
            ),
        )
        coverage = max(
            1,
            int(
                row.get(
                    "aggregate_chat_message_coverage",
                    row.get("document_ngram_unit_coverage", 1),
                )
            ),
        )
        for position, char in enumerate(phrase):
            item = evidence[char]
            item["parent_phrases"].add(phrase)
            item["categories"][category] += 1
            item["weighted_occurrences"] += weight
            item["weighted_coverage"] += coverage
            item["seed_phrases"].add(phrase)
            item["seed_categories"][category] += coverage
            item["document_seed_coverage"] = max(
                int(item.get("document_seed_coverage", 0)),
                int(row.get("document_ngram_unit_coverage", 0)),
            )
            item["document_seed_occurrences"] = max(
                int(item.get("document_seed_occurrences", 0)),
                int(row.get("document_ngram_occurrences", 0)),
            )
            item["document_seed_file_coverage"] = max(
                int(item.get("document_seed_file_coverage", 0)),
                int(row.get("document_ngram_file_coverage", 0)),
            )
            item["positions"][
                "start" if position == 0 else "end" if position == len(phrase) - 1 else "middle"
            ] += 1

    # The compact aggregate table may start at 2-grams, so a root's evidence is
    # the strongest complete family containing it (for example 更稳 and its
    # longer shells), not a fabricated count for the bare character itself.
    root_universe = set(SINGLE_ROOT_MANUAL_ALLOW)
    root_universe.update(
        char
        for entry in entries
        for char in str(entry["phrase"])
        if HAN_EXACT_RE.fullmatch(char)
    )
    root_universe.update(
        char
        for row in (seed_rows or [])
        for char in str(row["phrase"])
        if HAN_EXACT_RE.fullmatch(char)
    )
    with aggregate_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            item = json.loads(raw)
            phrase = str(item.get("phrase", ""))
            if not phrase or not HAN_EXACT_RE.fullmatch(phrase):
                continue
            roots = sorted(set(phrase) & root_universe)
            for root in roots:
                root_item = evidence[root]
                count = int(item.get("count", 0))
                coverage = int(item.get("message_coverage", 0))
                root_item["aggregate_count"] = max(root_item["aggregate_count"], count)
                root_item["aggregate_coverage"] = max(root_item["aggregate_coverage"], coverage)
                root_item.setdefault("family_phrase_count", 0)
                root_item["family_phrase_count"] += 1
                root_item.setdefault("family_occurrences", 0)
                root_item["family_occurrences"] += count
                root_item.setdefault("family_examples", [])
                example = (coverage, count, phrase)
                if len(root_item["family_examples"]) < 24:
                    heapq.heappush(root_item["family_examples"], example)
                elif example > root_item["family_examples"][0]:
                    heapq.heapreplace(root_item["family_examples"], example)

    rows: list[dict[str, Any]] = []
    for root, item in evidence.items():
        parent_count = len(item["parent_phrases"])
        category_count = len(item["categories"])
        seed_phrase_count = len(item["seed_phrases"])
        data_driven = (
            seed_phrase_count > 0
            and max(
                item["aggregate_coverage"],
                int(item.get("document_seed_coverage", 0)),
            )
            >= DATA_ROOT_MIN_SEED_COVERAGE
            and max(
                int(item.get("family_phrase_count", 0)),
                seed_phrase_count,
            )
            >= DATA_ROOT_MIN_FAMILY_PHRASES
        )
        if root in SINGLE_ROOT_STOP and root not in SINGLE_ROOT_MANUAL_ALLOW:
            reason = "function_character_stoplist"
            discovery_mode = "rejected"
        elif data_driven:
            reason = "eligible_root"
            discovery_mode = "raw-short-seed"
        elif parent_count < 3 and root not in SINGLE_ROOT_MANUAL_ALLOW:
            reason = "parent_phrase_count_lt_3"
            discovery_mode = "rejected"
        elif category_count < 2 and root not in SINGLE_ROOT_MANUAL_ALLOW:
            reason = "category_count_lt_2"
            discovery_mode = "rejected"
        elif item["aggregate_coverage"] < 50:
            reason = "family_max_message_coverage_lt_50"
            discovery_mode = "rejected"
        else:
            reason = "eligible_root"
            discovery_mode = (
                "manual-seed" if root in SINGLE_ROOT_MANUAL_ALLOW else "baseline-family"
            )
        rows.append(
            {
                "root": root,
                "parent_phrase_count": parent_count,
                "parent_category_count": category_count,
                "parent_categories": sorted(item["categories"]),
                "dominant_category": (
                    min(
                        item["categories"],
                        key=lambda category: (
                            -item["categories"][category],
                            CATEGORY_ORDER.index(category),
                        ),
                    )
                    if item["categories"]
                    else "certainty-limitation"
                ),
                "example_parent_phrases": sorted(item["parent_phrases"])[:24],
                "seed_phrase_count": seed_phrase_count,
                "seed_phrases": sorted(item["seed_phrases"])[:24],
                "document_seed_coverage": int(item.get("document_seed_coverage", 0)),
                "document_seed_occurrences": int(item.get("document_seed_occurrences", 0)),
                "document_seed_file_coverage": int(item.get("document_seed_file_coverage", 0)),
                "root_discovery_mode": discovery_mode,
                "positions": dict(item["positions"]),
                "weighted_parent_occurrences": item["weighted_occurrences"],
                "weighted_parent_coverage": item["weighted_coverage"],
                "aggregate_occurrences": item["aggregate_count"],
                "aggregate_message_coverage": item["aggregate_coverage"],
                "aggregate_family_phrase_count": item.get("family_phrase_count", 0),
                "aggregate_family_occurrences": item.get("family_occurrences", 0),
                "example_family_phrases": [
                    phrase
                    for _coverage, _count, phrase in sorted(
                        item.get("family_examples", []), reverse=True
                    )
                ],
                "root_status": reason,
            }
        )
    rows.sort(
        key=lambda row: (
            row["root_status"] == "eligible_root",
            max(
                row["aggregate_message_coverage"],
                row.get("document_seed_coverage", 0),
            ),
            row["parent_phrase_count"],
            row["weighted_parent_coverage"],
        ),
        reverse=True,
    )
    return rows


def marker_map(entries: list[dict[str, Any]]) -> dict[str, str]:
    markers: dict[str, tuple[str, int, int]] = {}
    for entry in entries:
        phrase = str(entry["phrase"])
        if not 2 <= len(phrase) <= 6:
            continue
        candidate = (str(entry["category"]), len(phrase), int(entry.get("combined_occurrences", 0)))
        current = markers.get(phrase)
        if current is None or (candidate[1], candidate[2]) > (current[1], current[2]):
            markers[phrase] = candidate
    for category, hints in DISCOVERY_HINTS.items():
        for hint in hints:
            if 2 <= len(hint) <= 6:
                current = markers.get(hint)
                candidate = (category, len(hint), 0)
                if current is None or candidate[1] > current[1]:
                    markers[hint] = candidate
    for phrase, category, _root in COMPARATIVE_ROOT_PATTERNS:
        markers.setdefault(phrase, (category, len(phrase), 0))
    return {phrase: value[0] for phrase, value in markers.items()}


def embedded_markers(phrase: str, markers: dict[str, str]) -> list[tuple[str, str, int]]:
    found: dict[tuple[str, str], int] = {}
    for start in range(len(phrase)):
        for length in range(2, min(6, len(phrase) - start) + 1):
            token = phrase[start : start + length]
            category = markers.get(token)
            if category is not None:
                found[(token, category)] = max(found.get((token, category), -1), start)
    return [(token, category, start) for (token, category), start in found.items()]


def discover_raw_short_cores(
    aggregate_path: Path,
    existing_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Discover high-frequency 2-3 character cores outside the old inventory.

    The first pass is deliberately high recall.  The second pass builds a
    core-to-parent-shell graph from every frequent 4-8 character n-gram; a
    parent does not need to contain an old-inventory marker.  Old markers are
    retained only as category evidence.  Live chat/document boundaries are
    collected later during the exact rescan.
    """
    existing = {str(entry["phrase"]) for entry in existing_entries}
    evidence: dict[str, RawShortCoreEvidence] = {}
    stats = Counter()
    with aggregate_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            item = json.loads(raw)
            phrase = str(item.get("phrase", ""))
            coverage = int(item.get("message_coverage", 0))
            if len(phrase) not in {2, 3} or coverage < RAW_SHORT_AUDIT_MIN_COVERAGE:
                continue
            if not HAN_EXACT_RE.fullmatch(phrase):
                continue
            evidence[phrase] = RawShortCoreEvidence(
                phrase=phrase,
                aggregate_occurrences=int(item.get("count", 0)),
                aggregate_coverage=coverage,
                aggregate_coverage_rate=float(item.get("coverage_rate", 0.0)),
                basic_reason=raw_short_basic_reason(phrase),
            )
            stats["raw_short_audit_candidates"] += 1

    active = {
        phrase
        for phrase, item in evidence.items()
        if item.basic_reason == "eligible_basic_shape" and phrase not in existing
    }
    markers = marker_map(existing_entries)
    marker_phrases = list(markers)
    marker_matcher = AhoMatcher(marker_phrases)
    with aggregate_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            item = json.loads(raw)
            parent = str(item.get("phrase", ""))
            parent_coverage = int(item.get("message_coverage", 0))
            if (
                not 4 <= len(parent) <= 8
                or parent_coverage < 20
                or not HAN_EXACT_RE.fullmatch(parent)
            ):
                continue
            marker_indexes = set(marker_matcher.matches(parent))
            categories = Counter(markers[marker_phrases[index]] for index in marker_indexes)
            seen_in_parent: set[str] = set()
            for length in (2, 3):
                for start in range(len(parent) - length + 1):
                    phrase = parent[start : start + length]
                    if phrase not in active or phrase in seen_in_parent:
                        continue
                    seen_in_parent.add(phrase)
                    candidate = evidence[phrase]
                    candidate.family_parent_count += 1
                    if categories:
                        candidate.styled_parent_count += 1
                        candidate.marker_categories.update(categories)
                        for category, count in categories.items():
                            candidate.weighted_marker_categories[category] += count * parent_coverage
                    candidate.left_contexts[parent[start - 1] if start else "^"] += 1
                    end = start + length
                    candidate.right_contexts[parent[end] if end < len(parent) else "$"] += 1
                    prefix_attached, suffix_attached = relative_discourse_attachment(
                        parent, start, end
                    )
                    candidate.discourse_prefix_parent_count += int(prefix_attached)
                    candidate.discourse_suffix_parent_count += int(suffix_attached)
                    candidate.discourse_attachment_parent_count += int(
                        prefix_attached or suffix_attached
                    )
                    candidate.max_parent_coverage = max(
                        candidate.max_parent_coverage, parent_coverage
                    )
                    example = (parent_coverage, parent)
                    if len(candidate.example_parent_phrases) < 12:
                        heapq.heappush(candidate.example_parent_phrases, example)
                    elif example > candidate.example_parent_phrases[0]:
                        heapq.heapreplace(candidate.example_parent_phrases, example)

    selected: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for phrase, item in evidence.items():
        left_count = len(item.left_contexts)
        right_count = len(item.right_contexts)
        left_dominance = counter_dominance(item.left_contexts)
        right_dominance = counter_dominance(item.right_contexts)
        marker_category_count = len(item.marker_categories)
        reason = item.basic_reason
        if phrase in existing:
            reason = "already_in_baseline"
        elif reason == "eligible_basic_shape":
            minimum_coverage = RAW_SHORT_RESCAN_MIN_COVERAGE[len(phrase)]
            if item.aggregate_coverage < minimum_coverage:
                reason = f"aggregate_chat_coverage_lt_{minimum_coverage}"
            elif item.family_parent_count < RAW_SHORT_MIN_FAMILY_PARENTS:
                reason = f"family_parent_count_lt_{RAW_SHORT_MIN_FAMILY_PARENTS}"
            elif left_count < RAW_SHORT_MIN_CONTEXTS:
                reason = f"left_context_count_lt_{RAW_SHORT_MIN_CONTEXTS}"
            elif right_count < RAW_SHORT_MIN_CONTEXTS:
                reason = f"right_context_count_lt_{RAW_SHORT_MIN_CONTEXTS}"
            elif left_dominance > RAW_SHORT_MAX_CONTEXT_DOMINANCE:
                reason = "left_context_dominance_gt_0_80"
            elif right_dominance > RAW_SHORT_MAX_CONTEXT_DOMINANCE:
                reason = "right_context_dominance_gt_0_80"
            else:
                reason = "eligible_raw_short_core"

        dominant_category = (
            min(
                item.weighted_marker_categories,
                key=lambda category: (
                    -item.weighted_marker_categories[category],
                    CATEGORY_ORDER.index(category),
                ),
            )
            if item.weighted_marker_categories
            else COMPOUND_ROOT_PATTERNS.get(
                phrase, markers.get(phrase, "academic-packaging")
            )
        )
        examples = [
            parent
            for _coverage, parent in sorted(
                item.example_parent_phrases, reverse=True
            )
        ]
        row = {
            "phrase": phrase,
            "category": dominant_category,
            "source_kind": "raw-short-core-pass4",
            "aggregate_chat_occurrences": item.aggregate_occurrences,
            "aggregate_chat_message_coverage": item.aggregate_coverage,
            "aggregate_chat_message_coverage_rate": item.aggregate_coverage_rate,
            "family_parent_count": item.family_parent_count,
            "styled_parent_count": item.styled_parent_count,
            "parent_category_count": marker_category_count,
            "parent_categories": sorted(item.marker_categories),
            "example_parent_phrases": examples,
            "left_contexts": dict(item.left_contexts.most_common(24)),
            "right_contexts": dict(item.right_contexts.most_common(24)),
            "aggregate_left_context_count": left_count,
            "aggregate_right_context_count": right_count,
            "aggregate_left_context_dominance": left_dominance,
            "aggregate_right_context_dominance": right_dominance,
            "aggregate_left_context_entropy": counter_entropy(item.left_contexts),
            "aggregate_right_context_entropy": counter_entropy(item.right_contexts),
            "discourse_prefix_parent_count": item.discourse_prefix_parent_count,
            "discourse_suffix_parent_count": item.discourse_suffix_parent_count,
            "discourse_attachment_parent_count": item.discourse_attachment_parent_count,
            "discourse_attachment_parent_ratio": _ratio(
                item.discourse_attachment_parent_count, item.family_parent_count
            ),
            "max_parent_message_coverage": item.max_parent_coverage,
            "preselection_reason": reason,
        }
        if reason == "eligible_raw_short_core":
            row["discovery_score"] = round(
                phrase_score(
                    item.aggregate_occurrences,
                    item.aggregate_coverage,
                    phrase,
                )
                + 0.8 * math.log1p(item.family_parent_count)
                + 0.5 * math.log1p(marker_category_count)
                + 0.35 * (
                    row["aggregate_left_context_entropy"]
                    + row["aggregate_right_context_entropy"]
                ),
                6,
            )
            selected.append(row)
        audit.append(row)
        stats[f"raw_short_preselection/{reason}"] += 1

    selected.sort(
        key=lambda row: (
            row["discovery_score"],
            row["aggregate_chat_message_coverage"],
            len(row["phrase"]),
            row["phrase"],
        ),
        reverse=True,
    )
    audit.sort(
        key=lambda row: (
            row["preselection_reason"] != "eligible_raw_short_core",
            -int(row["aggregate_chat_message_coverage"]),
            row["phrase"],
        )
    )
    stats["raw_short_selected_for_exact_rescan"] = len(selected)
    return selected, audit, dict(stats)


def classify_long_candidate(
    phrase: str,
    coverage: int,
    markers: dict[str, str],
) -> tuple[str | None, list[str], str]:
    if not 4 <= len(phrase) <= 8 or not HAN_EXACT_RE.fullmatch(phrase):
        return None, [], "invalid_shape"
    if coverage < 20:
        return None, [], "chat_coverage_lt_20"
    if phrase in NOISE_EXACT or phrase[0] in BAD_EDGE or phrase[-1] in BAD_EDGE:
        return None, [], "function_or_noise_edge"
    if any(phrase.startswith(prefix) for prefix in BAD_PREFIXES):
        return None, [], "known_fragment_prefix"
    if len(set(phrase)) == 1:
        return None, [], "repeated_character_noise"
    structural = (
        ("不是" in phrase and "而是" in phrase)
        or ("不仅" in phrase and "而且" in phrase)
        or ("一方面" in phrase and "另一方面" in phrase)
    )
    if not structural and not has_complete_boundary(phrase, markers=markers):
        return None, [], "no_complete_boundary_signal"

    matches = embedded_markers(phrase, markers)
    unique_tokens = sorted({token for token, _category, _start in matches}, key=lambda item: (-len(item), item))
    maximal: list[str] = []
    for token in unique_tokens:
        if any(token in longer for longer in maximal):
            continue
        maximal.append(token)
    strong = [token for token in maximal if len(token) >= 3]
    if not strong and len(maximal) < 2 and not structural:
        return None, maximal, "insufficient_marker_support"

    scores: Counter[str] = Counter()
    for token, category, _start in matches:
        scores[category] += len(token) * len(token)
    if structural:
        scores["contrast-correction"] += 25
    if not scores:
        return None, maximal, "no_category"
    category = min(scores, key=lambda item: (-scores[item], CATEGORY_ORDER.index(item)))
    return category, maximal[:8], "eligible"


def stream_aggregate_candidates(
    path: Path,
    sub_evidence: dict[str, SubphraseEvidence],
    existing_entries: list[dict[str, Any]],
    per_category_pool: int,
    root_rows: list[dict[str, Any]] | None = None,
    raw_short_rows: list[dict[str, Any]] | None = None,
    root_inversion_rows: list[dict[str, Any]] | None = None,
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    existing = {str(entry["phrase"]) for entry in existing_entries}
    sub_lookup = set(sub_evidence)
    markers = marker_map(existing_entries)
    raw_core_rows = {str(row["phrase"]): row for row in (raw_short_rows or [])}
    for phrase, row in raw_core_rows.items():
        markers.setdefault(phrase, str(row["category"]))
    raw_core_phrases = sorted(raw_core_rows, key=lambda item: (-len(item), item))
    raw_core_matcher = AhoMatcher(raw_core_phrases) if raw_core_phrases else None
    root_inversion_by_root = {
        str(row["root"]): row
        for row in (root_inversion_rows or [])
        if row.get("root_status") in ROOT_INVERSION_ELIGIBLE_STATUSES
    }
    root_inversion_roots = sorted(
        root_inversion_by_root, key=lambda item: (-len(item), item)
    )
    root_inversion_matcher = (
        AhoMatcher(root_inversion_roots) if root_inversion_roots else None
    )
    comparative_roots = {phrase: (category, root) for phrase, category, root in COMPARATIVE_ROOT_PATTERNS}
    root_categories = {
        row["root"]: row["dominant_category"]
        for row in (root_rows or [])
        if row.get("root_status") == "eligible_root"
    }
    root_family_markers = {
        root
        for row in (root_rows or [])
        if row.get("root_status") == "eligible_root"
        for root in [row["root"]]
    }
    root_strength = {
        row["root"]: (
            int(row.get("aggregate_message_coverage", 0)),
            int(row.get("seed_phrase_count", 0)),
            int(row.get("parent_phrase_count", 0)),
        )
        for row in (root_rows or [])
        if row.get("root_status") == "eligible_root"
    }
    sub_counts: dict[str, dict[str, Any]] = {}
    heaps: dict[str, list[tuple[float, int, int, str]]] = defaultdict(list)
    family_heaps: dict[
        tuple[str, str, str, str], list[tuple[float, int, int, str]]
    ] = defaultdict(list)
    candidate_rows: dict[str, dict[str, Any]] = {}
    root_inversion_recall_rows: dict[str, dict[str, Any]] = {}
    root_inversion_rejection_examples: dict[
        tuple[str, str], list[tuple[int, int, str]]
    ] = defaultdict(list)
    priority_phrases: set[str] = set()
    stats = Counter()

    def push_bounded(
        heap: list[tuple[float, int, int, str]],
        row: dict[str, Any],
        limit: int,
    ) -> None:
        key = (
            float(row["discovery_score"]),
            int(row["aggregate_chat_message_coverage"]),
            int(row["aggregate_chat_occurrences"]),
            str(row["phrase"]),
        )
        if len(heap) < limit:
            heapq.heappush(heap, key)
        elif key > heap[0]:
            heapq.heapreplace(heap, key)
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stats["aggregate_rows_scanned"] += 1
            item = json.loads(raw)
            phrase = str(item["phrase"])
            count = int(item["count"])
            coverage = int(item["message_coverage"])
            rate = float(item.get("coverage_rate", 0.0))
            if phrase in sub_lookup:
                sub_counts[phrase] = {
                    "aggregate_chat_occurrences": count,
                    "aggregate_chat_message_coverage": coverage,
                    "aggregate_chat_message_coverage_rate": rate,
                }
            if phrase in existing:
                continue
            if phrase in FORBIDDEN_FINAL_FRAGMENTS or phrase in SUBPHRASE_FRAGMENT_EXACT:
                stats["long_rejected/global_known_fragment"] += 1
                continue
            comparative_hits = [
                (pattern, category, root)
                for pattern, (category, root) in comparative_roots.items()
                if pattern in phrase
            ]
            comparative_shape = (
                2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH
                and coverage >= 20
                and comparative_hits
                and HAN_EXACT_RE.fullmatch(phrase)
            )
            raw_core_hits = (
                sorted(
                    {
                        raw_core_phrases[index]
                        for index in raw_core_matcher.matches(phrase)
                    },
                    key=lambda item: (-len(item), item),
                )
                if raw_core_matcher is not None
                else []
            )
            root_inversion_hits = (
                sorted(
                    {
                        root_inversion_roots[index]
                        for index in root_inversion_matcher.matches(phrase)
                    },
                    key=lambda item: (-len(item), item),
                )
                if root_inversion_matcher is not None
                else []
            )
            root_inversion_shapes, root_inversion_shape_reason = (
                classify_root_inversion_family_shapes(
                    phrase,
                    root_inversion_hits,
                )
                if root_inversion_hits
                and coverage >= ROOT_INVERSION_FAMILY_MIN_COVERAGE
                else ([], "no_eligible_root_or_coverage")
            )
            best_inversion_shape: dict[str, Any] | None = None
            best_inversion_root: str | None = None
            if root_inversion_shapes:
                shape_priority = {
                    "reversible_shell": 4,
                    "exact_root": 3,
                    "edge_context_pending": 2,
                    "context_envelope_pending": 1,
                }
                best_inversion_shape = min(
                    root_inversion_shapes,
                    key=lambda shape: (
                        -shape_priority[str(shape["gate_kind"])],
                        -len(str(shape["root"])),
                        -float(
                            root_inversion_by_root[str(shape["root"])].get(
                                "discovery_score", 0.0
                            )
                        ),
                        str(shape["root"]),
                    ),
                )
                best_inversion_root = str(best_inversion_shape["root"])
                root_row = root_inversion_by_root[best_inversion_root]
                root_inversion_recall_rows[phrase] = {
                    "phrase": phrase,
                    "root_inversion_primary_root": best_inversion_root,
                    "root_inversion_gate_kind": str(
                        best_inversion_shape["gate_kind"]
                    ),
                    "root_inversion_prefix": str(best_inversion_shape["prefix"]),
                    "root_inversion_suffix": str(best_inversion_shape["suffix"]),
                    "root_inversion_prefix_parts": list(
                        best_inversion_shape["prefix_parts"]
                    ),
                    "root_inversion_suffix_parts": list(
                        best_inversion_shape["suffix_parts"]
                    ),
                    "root_inversion_shape_roots": sorted(
                        {str(shape["root"]) for shape in root_inversion_shapes},
                        key=lambda item: (-len(item), item),
                    ),
                    "root_inversion_shape_kinds": sorted(
                        {str(shape["gate_kind"]) for shape in root_inversion_shapes}
                    ),
                    "aggregate_chat_occurrences": count,
                    "aggregate_chat_message_coverage": coverage,
                    "aggregate_chat_message_coverage_rate": rate,
                    "root_inversion_discovery_score": float(
                        root_row.get("discovery_score", 0.0)
                    ),
                    "candidate_state": "family_recalled",
                    "boundary_state": (
                        "boundary_verified_by_reversible_shell"
                        if best_inversion_shape["gate_kind"] == "reversible_shell"
                        else "boundary_verified_as_exact_root"
                        if best_inversion_shape["gate_kind"] == "exact_root"
                        else "pending_exact_source_context"
                    ),
                }
                stats[
                    "root_inversion_gate/"
                    + str(best_inversion_shape["gate_kind"])
                ] += 1
            elif root_inversion_hits and coverage >= ROOT_INVERSION_FAMILY_MIN_COVERAGE:
                stats[f"root_inversion_gate_rejected/{root_inversion_shape_reason}"] += 1
                for root in root_inversion_hits:
                    heap = root_inversion_rejection_examples[
                        (root, root_inversion_shape_reason)
                    ]
                    key = (coverage, count, phrase)
                    if len(heap) < ROOT_INVERSION_REJECTION_EXAMPLES_PER_ROOT:
                        heapq.heappush(heap, key)
                    elif key > heap[0]:
                        heapq.heapreplace(heap, key)
            compound_category, compound_triggers, compound_reason = (
                classify_compound_root_candidate(phrase, coverage)
            )
            compound_shape = compound_category is not None
            if comparative_shape and not has_complete_comparative_boundary(
                phrase, comparative_hits
            ):
                stats["long_rejected/comparative_fragment_boundary"] += 1
                # A stray comparative character can occur inside a different
                # complete root (for example the 更 in 更新).  Reject only the
                # comparative route; do not suppress an independently valid
                # root-inversion family discovered on the same phrase.
                comparative_shape = False
            # A phrase may have both parent-subphrase and independent family
            # evidence.  Do not let the first route suppress the others.
            root_hits = sorted(set(phrase) & root_family_markers)
            if (
                2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH
                and coverage >= 20
                and comparative_hits
                and HAN_EXACT_RE.fullmatch(phrase)
                and has_complete_comparative_boundary(phrase, comparative_hits)
            ):
                category = min(
                    (item[1] for item in comparative_hits),
                    key=lambda item: CATEGORY_ORDER.index(item),
                )
                triggers = sorted(
                    {item[0] for item in comparative_hits}, key=lambda item: (-len(item), item)
                )
                reason = "eligible_comparative_root_family"
            elif best_inversion_shape is not None and best_inversion_root is not None:
                root_row = root_inversion_by_root[best_inversion_root]
                category = str(root_row["dominant_category"])
                triggers = sorted(
                    {str(shape["root"]) for shape in root_inversion_shapes},
                    key=lambda item: (-len(item), item),
                )
                reason = "eligible_root_inversion_family"
            elif compound_shape:
                category = compound_category
                triggers = compound_triggers
                reason = compound_reason
            elif (
                2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH
                and coverage >= 20
                and raw_core_hits
                and has_raw_core_family_boundary(phrase, raw_core_hits)
            ):
                best_core = min(
                    raw_core_hits,
                    key=lambda core: (
                        -len(core),
                        -int(
                            raw_core_rows[core].get(
                                "aggregate_chat_message_coverage", 0
                            )
                        ),
                        core,
                    ),
                )
                category = str(raw_core_rows[best_core]["category"])
                triggers = raw_core_hits
                reason = "eligible_raw_core_family"
            elif (
                2 <= len(phrase) <= ROOT_FAMILY_MAX_LENGTH
                and coverage >= 20
                and root_hits
                and HAN_EXACT_RE.fullmatch(phrase)
                and has_root_family_boundary(phrase, root_hits, markers)
            ):
                best_root = min(
                    root_hits,
                    key=lambda root: (
                        -root_strength.get(root, (0, 0, 0))[0],
                        -root_strength.get(root, (0, 0, 0))[1],
                        -root_strength.get(root, (0, 0, 0))[2],
                        root,
                    ),
                )
                category = root_categories[best_root]
                triggers = sorted(root_hits, key=lambda item: (-len(item), item))
                reason = "eligible_single_root_family"
            else:
                category, triggers, reason = classify_long_candidate(phrase, coverage, markers)
            if category is None:
                stats[f"long_rejected/{reason}"] += 1
                continue
            inversion_gate_bonus = (
                3.0
                if best_inversion_shape
                and best_inversion_shape["gate_kind"] == "reversible_shell"
                else 2.0
                if best_inversion_shape
                and best_inversion_shape["gate_kind"] == "exact_root"
                else 0.25
                if best_inversion_shape
                and best_inversion_shape["gate_kind"] == "edge_context_pending"
                else 0.10
                if best_inversion_shape
                and best_inversion_shape["gate_kind"] == "context_envelope_pending"
                else 0.0
            )
            score = (
                phrase_score(count, coverage, phrase)
                + 0.35 * sum(len(token) for token in triggers)
                + inversion_gate_bonus
            )
            source_kind = (
                "compound-root-pass4"
                if reason == "eligible_compound_root_family"
                else "comparative-root-pass3"
                if reason == "eligible_comparative_root_family"
                else "raw-core-family-pass5"
                if reason == "eligible_raw_core_family"
                else "root-inversion-family-pass8"
                if reason == "eligible_root_inversion_family"
                else "single-root-family-pass3"
                if reason == "eligible_single_root_family"
                else "independent-longphrase-pass2"
            )
            candidate = {
                "phrase": phrase,
                "category": category,
                "source_kind": source_kind,
                "discovery_score": round(score, 6),
                "aggregate_chat_occurrences": count,
                "aggregate_chat_message_coverage": coverage,
                "aggregate_chat_message_coverage_rate": rate,
                "trigger_phrases": list(triggers),
                "length_bucket": length_bucket(phrase),
            }
            if source_kind == "root-inversion-family-pass8" and best_inversion_root:
                root_row = root_inversion_by_root[best_inversion_root]
                candidate.update(
                    root_inversion_primary_root=best_inversion_root,
                    root_inversion_parent_count=int(
                        root_row.get("parent_phrase_count", 0)
                    ),
                    root_inversion_shell_parent_count=int(
                        root_row.get("shell_parent_count", 0)
                    ),
                    root_inversion_confirmed_parent_count=int(
                        root_row.get("confirmed_parent_count", 0)
                    ),
                    root_inversion_confirmed_context_ready=bool(
                        root_row.get("confirmed_context_ready", False)
                    ),
                    root_inversion_root_first_counts_ready=bool(
                        root_row.get("root_first_counts_ready", False)
                    ),
                    root_inversion_root_first_shell_ready=bool(
                        root_row.get("root_first_shell_ready", False)
                    ),
                    root_inversion_cross_source_parent_ready=bool(
                        root_row.get("cross_source_parent_ready", False)
                    ),
                    root_inversion_root_status=str(
                        root_row.get("root_status", "")
                    ),
                    root_inversion_discovery_mode=str(
                        root_row.get("root_discovery_mode", "")
                    ),
                    root_inversion_shell_type_count=int(
                        root_row.get("shell_type_count", 0)
                    ),
                    root_inversion_shell_weighted_parent_coverage=int(
                        root_row.get("shell_weighted_parent_coverage", 0)
                    ),
                    root_inversion_discovery_score=float(
                        root_row.get("discovery_score", 0.0)
                    ),
                    root_inversion_examples=list(
                        root_row.get("example_parent_phrases", [])
                    )[:12],
                    root_inversion_gate_kind=str(
                        best_inversion_shape["gate_kind"]
                    ),
                    root_inversion_prefix=str(best_inversion_shape["prefix"]),
                    root_inversion_suffix=str(best_inversion_shape["suffix"]),
                    root_inversion_prefix_parts=list(
                        best_inversion_shape["prefix_parts"]
                    ),
                    root_inversion_suffix_parts=list(
                        best_inversion_shape["suffix_parts"]
                    ),
                )
            if phrase in root_inversion_recall_rows:
                root_inversion_recall_rows[phrase]["selected_discovery_route"] = source_kind
            candidate_rows[phrase] = candidate
            if source_kind == "compound-root-pass4":
                priority_phrases.add(phrase)
                stats["compound_root_eligible_before_exact_rescan"] += 1
                stats["long_eligible_before_heap"] += 1
                continue
            if (
                source_kind in FAMILY_SOURCE_KINDS
                and coverage >= ROOT_INVERSION_FAMILY_MIN_COVERAGE
            ):
                # Every evidenced root family reaches exact rescan. Ranking is
                # useful for reports, never as an eligibility gate; otherwise
                # a productive low-frequency shell disappears merely because
                # another category has more candidates.
                priority_phrases.add(phrase)
                stats["root_family_selected_without_top_k"] += 1
                if phrase in root_inversion_recall_rows:
                    stats["root_inversion_selected_without_top_k"] += 1
                stats["long_eligible_before_heap"] += 1
                continue
            push_bounded(heaps[category], candidate, per_category_pool)
            if source_kind in FAMILY_SOURCE_KINDS:
                for trigger in triggers:
                    family_key = (
                        source_kind,
                        str(trigger),
                        length_bucket(phrase),
                        str(candidate.get("root_inversion_gate_kind", "not_applicable")),
                    )
                    push_bounded(
                        family_heaps[family_key],
                        candidate,
                        ROOT_INVERSION_RESERVE_PER_TRIGGER
                        if source_kind == "root-inversion-family-pass8"
                        else ROOT_FAMILY_RESERVE_PER_TRIGGER,
                    )
            if phrase in REQUIRED_FINAL_PHRASES:
                priority_phrases.add(phrase)
            stats["long_eligible_before_heap"] += 1

    selected_phrases = set(priority_phrases)
    for heap in heaps.values():
        selected_phrases.update(item[3] for item in heap)
    for heap in family_heaps.values():
        selected_phrases.update(item[3] for item in heap)
    long_rows = sorted(
        (candidate_rows[phrase] for phrase in selected_phrases),
        key=lambda row: (
            CATEGORY_ORDER.index(str(row["category"])),
            -float(row["discovery_score"]),
            str(row["phrase"]),
        ),
    )
    stats["compound_root_priority_rows"] = sum(
        row["source_kind"] == "compound-root-pass4" for row in long_rows
    )
    stats["required_priority_rows"] = sum(
        row["phrase"] in REQUIRED_FINAL_PHRASES for row in long_rows
    )
    stats["root_family_reserve_groups"] = len(family_heaps)
    stats["root_family_reserve_unique_rows"] = len(
        {item[3] for heap in family_heaps.values() for item in heap}
    )
    stats["long_heap_rows"] = len(long_rows)
    stats["sub_candidates_with_aggregate_counts"] = len(sub_counts)
    root_inversion_audit = []
    for phrase, recall in root_inversion_recall_rows.items():
        item = dict(recall)
        candidate = candidate_rows.get(phrase, {})
        for key, value in candidate.items():
            item.setdefault(key, value)
        selected = phrase in selected_phrases
        item["selected_for_exact_rescan"] = selected
        selected_route = str(item.get("selected_discovery_route", ""))
        aggregate_coverage = int(item.get("aggregate_chat_message_coverage", 0))
        if (
            selected
            and aggregate_coverage >= ROOT_INVERSION_FAMILY_RESCAN_MIN_COVERAGE
        ):
            decision = "selected_for_exact_rescan_no_top_k"
        elif selected:
            decision = f"selected_via_higher_precision_route:{selected_route}"
        elif aggregate_coverage < ROOT_INVERSION_FAMILY_RESCAN_MIN_COVERAGE:
            decision = (
                "below_root_inversion_exact_rescan_coverage_"
                f"{ROOT_INVERSION_FAMILY_RESCAN_MIN_COVERAGE}"
            )
        elif selected_route and selected_route != "root-inversion-family-pass8":
            decision = f"higher_precision_route_dropped_by_pool:{selected_route}"
        else:
            decision = "invariant_violation_eligible_root_family_not_selected"
        item["pool_decision"] = decision
        root_inversion_audit.append(item)
    for (root, reason), heap in root_inversion_rejection_examples.items():
        for coverage, occurrences, phrase in sorted(heap, reverse=True):
            root_inversion_audit.append(
                {
                    "phrase": phrase,
                    "root_inversion_primary_root": root,
                    "aggregate_chat_occurrences": occurrences,
                    "aggregate_chat_message_coverage": coverage,
                    "candidate_state": "root_discovered_only",
                    "boundary_state": "unverified",
                    "selected_for_exact_rescan": False,
                    "pool_decision": f"rejected_before_pool:{reason}",
                    "audit_scope": "bounded_high_coverage_example",
                }
            )
    root_inversion_audit.sort(
        key=lambda row: (
            not bool(row["selected_for_exact_rescan"]),
            -float(row.get("discovery_score", 0.0)),
            -int(row.get("aggregate_chat_message_coverage", 0)),
            str(row["phrase"]),
        )
    )
    stats["root_inversion_family_candidates"] = len(root_inversion_audit)
    stats["root_inversion_family_selected"] = sum(
        bool(row["selected_for_exact_rescan"]) for row in root_inversion_audit
    )
    stats["root_inversion_family_dropped_by_pool"] = sum(
        str(row.get("pool_decision", "")).startswith(
            ("eligible_dropped", "higher_precision_route_dropped")
        )
        for row in root_inversion_audit
    )
    stats["root_inversion_family_unexpected_selection_gaps"] = sum(
        row.get("pool_decision")
        == "invariant_violation_eligible_root_family_not_selected"
        for row in root_inversion_audit
    )
    return sub_counts, long_rows, root_inversion_audit, dict(stats)


def preselect_subphrases(
    evidence: dict[str, SubphraseEvidence],
    aggregate_counts: dict[str, dict[str, Any]],
    pool_limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for phrase, item in evidence.items():
        usable, reason = usable_subphrase(phrase, item)
        aggregate = aggregate_counts.get(phrase, {})
        coverage = int(aggregate.get("aggregate_chat_message_coverage", 0))
        if usable:
            if len(phrase) == 2 and coverage < 80:
                usable, reason = False, "two_char_chat_coverage_lt_80"
            elif len(phrase) >= 3 and coverage < 30:
                usable, reason = False, "chat_coverage_lt_30"
        category = min(
            item.weighted_categories,
            key=lambda value: (-item.weighted_categories[value], CATEGORY_ORDER.index(value)),
        )
        source_kind = (
            "csv-decomposition-pass6"
            if "csv-decomposition-pass6" in item.source_kinds
            else "parent-subphrase-pass2"
        )
        row = {
            "phrase": phrase,
            "category": category,
            "source_kind": source_kind,
            "parent_source_kinds": sorted(item.source_kinds),
            "parent_phrase_count": len(item.parents),
            "parent_category_count": len(item.categories),
            "parent_categories": sorted(item.categories),
            "example_parent_phrases": sorted(item.parents)[:12],
            "left_contexts": dict(item.left_contexts.most_common(12)),
            "right_contexts": dict(item.right_contexts.most_common(12)),
            **aggregate,
            "preselection_reason": reason,
        }
        if usable:
            row["discovery_score"] = round(
                phrase_score(
                    int(aggregate.get("aggregate_chat_occurrences", 0)),
                    coverage,
                    phrase,
                )
                + 1.8 * math.log1p(len(item.parents))
                + 0.8 * math.log1p(len(item.categories)),
                6,
            )
            eligible.append(row)
        else:
            rejected.append(row)
    eligible.sort(
        key=lambda row: (
            row["discovery_score"],
            row["parent_phrase_count"],
            len(row["phrase"]),
            row["phrase"],
        ),
        reverse=True,
    )
    selected = eligible[:pool_limit]
    dropped = []
    for row in eligible[pool_limit:]:
        item = dict(row)
        item["preselection_reason"] = "eligible_dropped_by_pool"
        dropped.append(item)
    return selected, rejected, dropped


def discover_document_paths(roots: Iterable[Path], excluded: Iterable[Path]) -> list[dict[str, Any]]:
    excluded_norm = {os.path.normcase(os.path.abspath(path)) for path in excluded}
    excluded_dirs = {
        ".git", "node_modules", "__pycache__", ".pytest_cache", "$RECYCLE.BIN",
        "System Volume Information",
    }
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root):
            current_norm = os.path.normcase(os.path.abspath(current))
            if any(current_norm == value or current_norm.startswith(value + os.sep) for value in excluded_norm):
                dirs[:] = []
                continue
            dirs[:] = [name for name in dirs if name not in excluded_dirs]
            for name in files:
                path = Path(current) / name
                if path.suffix.lower() not in {".md", ".tex"}:
                    continue
                key = os.path.normcase(os.path.abspath(path))
                found[key] = path
    snapshot = []
    for key in sorted(found):
        path = found[key]
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot.append({"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return snapshot


def load_snapshot_files(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError(f"snapshot has no files list: {path}")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(files):
        if not isinstance(item, dict) or not {"path", "size", "mtime_ns"} <= set(item):
            raise ValueError(f"invalid snapshot entry {index}: {path}")
        normalized.append(
            {
                "path": str(item["path"]),
                "size": int(item["size"]),
                "mtime_ns": int(item["mtime_ns"]),
            }
        )
    declared_file_set_sha256 = payload.get("file_set_sha256")
    actual_file_set_sha256 = snapshot_file_set_sha256(normalized)
    if (
        declared_file_set_sha256 is not None
        and str(declared_file_set_sha256) != actual_file_set_sha256
    ):
        raise ValueError(
            "snapshot file_set_sha256 mismatch: "
            f"declared={declared_file_set_sha256} actual={actual_file_set_sha256}"
        )
    return normalized, payload


def read_frozen_bytes(entry: dict[str, Any]) -> bytes:
    remaining = int(entry["size"])
    chunks: list[bytes] = []
    with Path(entry["path"]).open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    return b"".join(chunks)


def scan_documents(
    snapshot: list[dict[str, Any]],
    phrases: list[str],
    manifest_path: Path,
    context_phrases: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    matcher = AhoMatcher(phrases)
    context_indexes = {
        index for index, phrase in enumerate(phrases) if phrase in (context_phrases or set())
    }
    occurrence = {suffix: Counter() for suffix in (".md", ".tex")}
    unit_coverage = {suffix: Counter() for suffix in (".md", ".tex")}
    file_coverage = {suffix: Counter() for suffix in (".md", ".tex")}
    exact_left_contexts: dict[int, Counter[str]] = defaultdict(Counter)
    exact_right_contexts: dict[int, Counter[str]] = defaultdict(Counter)
    stats = Counter()
    seen_hashes: set[str] = set()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path", "suffix", "snapshot_bytes", "mtime_ns", "sha256", "status",
                "duplicate", "semantic_units", "changed_after_snapshot",
            ],
        )
        writer.writeheader()
        for file_number, entry in enumerate(snapshot, start=1):
            path = Path(entry["path"])
            suffix = path.suffix.lower()
            status = "INCLUDED"
            digest = ""
            units = 0
            duplicate = False
            try:
                raw = read_frozen_bytes(entry)
                text = raw.decode("utf-8-sig", errors="strict")
            except (OSError, UnicodeError):
                raw = b""
                text = ""
                status = "SKIPPED_GARBLED"
                stats["document_files_skipped_garbled_or_unreadable"] += 1
            changed = False
            try:
                current = path.stat()
                changed = current.st_size != entry["size"] or current.st_mtime_ns != entry["mtime_ns"]
            except OSError:
                changed = True
            if status == "INCLUDED":
                digest = sha256(raw)
                duplicate = digest in seen_hashes
                seen_hashes.add(digest)
                if duplicate:
                    stats["document_files_exact_duplicates"] += 1
                    status = "EXCLUDED_DUPLICATE"
                else:
                    file_seen: set[int] = set()
                    for unit in semantic_units(text, suffix):
                        units += 1
                        stats["semantic_units"] += 1
                        unit_seen: set[int] = set()
                        for index, end in matcher.matches_with_end(unit):
                            occurrence[suffix][index] += 1
                            unit_seen.add(index)
                            file_seen.add(index)
                            if index in context_indexes:
                                start = end - len(phrases[index])
                                exact_left_contexts[index][unit[start - 1] if start else "^"] += 1
                                exact_right_contexts[index][unit[end] if end < len(unit) else "$"] += 1
                        for index in unit_seen:
                            unit_coverage[suffix][index] += 1
                    for index in file_seen:
                        file_coverage[suffix][index] += 1
                    stats[f"{suffix[1:]}_files_read"] += 1
                    stats[f"{suffix[1:]}_bytes_read"] += len(raw)
            writer.writerow(
                {
                    "path": str(path),
                    "suffix": suffix,
                    "snapshot_bytes": entry["size"],
                    "mtime_ns": entry["mtime_ns"],
                    "sha256": digest,
                    "status": status,
                    "duplicate": str(duplicate).lower()
                    if status in {"INCLUDED", "EXCLUDED_DUPLICATE"}
                    else "",
                    "semantic_units": units,
                    "changed_after_snapshot": str(changed).lower(),
                }
            )
            if file_number % 1000 == 0:
                print(f"documents {file_number}/{len(snapshot)}", flush=True)

    result: dict[str, dict[str, int]] = {}
    for index, phrase in enumerate(phrases):
        result[phrase] = {}
        for suffix, label in ((".md", "md"), (".tex", "tex")):
            result[phrase][f"{label}_occurrences"] = occurrence[suffix][index]
            result[phrase][f"{label}_unit_coverage"] = unit_coverage[suffix][index]
            result[phrase][f"{label}_file_coverage"] = file_coverage[suffix][index]
        if index in context_indexes:
            result[phrase].update(
                exact_context_metrics(
                    "document_context",
                    exact_left_contexts[index],
                    exact_right_contexts[index],
                )
            )
    stats["document_files_seen"] = len(snapshot)
    return result, dict(stats)


def discover_document_ngram_seeds(
    snapshot: list[dict[str, Any]],
    existing_entries: list[dict[str, Any]],
    *,
    limit: int | None = DOCUMENT_NGRAM_SEED_LIMIT,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    """Discover short roots directly from frozen MD/TeX semantic units.

    The chat aggregate is intentionally not reused here.  A document-only
    phrase must first be visible in the document corpus before it can enter
    the exact-rescan candidate set.  All 1-3-grams enter the root audit; only
    complete 2/3-gram seeds can enter the direct phrase candidate set.  Every
    phrase is rescanned later against both corpora, so this function is
    discovery evidence, not a ban decision.
    """
    existing = {str(entry["phrase"]) for entry in existing_entries}
    evidence: dict[str, DocumentNgramEvidence] = defaultdict(DocumentNgramEvidence)
    stats = Counter()
    seen_hashes: set[str] = set()

    for file_number, entry in enumerate(snapshot, start=1):
        path = Path(entry["path"])
        suffix = path.suffix.lower()
        try:
            raw = read_frozen_bytes(entry)
            text = raw.decode("utf-8-sig", errors="strict")
        except (OSError, UnicodeError):
            stats["document_ngram_files_skipped_garbled"] += 1
            continue
        if "\ufffd" in text or MOJIBAKE_RE.search(text):
            stats["document_ngram_files_skipped_garbled"] += 1
            continue
        digest = sha256(raw)
        if digest in seen_hashes:
            stats["document_ngram_duplicate_files"] += 1
            continue
        seen_hashes.add(digest)
        file_seen: set[str] = set()
        for unit in semantic_units(text, suffix):
            stats["document_ngram_semantic_units"] += 1
            unit_seen: set[str] = set()
            for run in HAN_RUN_RE.findall(unit):
                for length in (1, 2, 3):
                    if len(run) < length:
                        continue
                    for start in range(len(run) - length + 1):
                        phrase = run[start : start + length]
                        item = evidence[phrase]
                        item.occurrences += 1
                        unit_seen.add(phrase)
                        file_seen.add(phrase)
                        item.left_contexts[run[start - 1] if start else "^"] += 1
                        end = start + length
                        item.right_contexts[run[end] if end < len(run) else "$"] += 1
            for phrase in unit_seen:
                evidence[phrase].unit_coverage += 1
        for phrase in file_seen:
            evidence[phrase].file_coverage += 1
        stats["document_ngram_files_read"] += 1
        stats["document_ngram_bytes_read"] += len(raw)
        if file_number % 1000 == 0:
            print(f"document ngram discovery {file_number}/{len(snapshot)}", flush=True)

    markers = marker_map(existing_entries)
    eligible: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    root_audit: list[dict[str, Any]] = []
    for phrase, item in evidence.items():
        length = len(phrase)
        root_reason = root_inversion_basic_reason(phrase)
        root_minimum_met = (
            item.unit_coverage >= DOCUMENT_ROOT_AUDIT_MIN_UNITS[length]
            and item.file_coverage >= DOCUMENT_ROOT_MIN_FILES[length]
            and item.occurrences >= DOCUMENT_ROOT_MIN_OCCURRENCES[length]
        )
        root_shape_allowed = root_reason in {
            "eligible_basic_shape",
            "function_character_edge",
            "function_character_stoplist",
        } or phrase in STRICT_RELEASE_DISCOVERY_ROOT_ONLY
        if root_minimum_met:
            root_selected = root_shape_allowed
            root_row = {
                "root": phrase,
                "root_length": length,
                "category": markers.get(phrase, "audit-governance"),
                "source_kind": "document-root-graph-pass9",
                "document_root_occurrences": item.occurrences,
                "document_root_unit_coverage": item.unit_coverage,
                "document_root_file_coverage": item.file_coverage,
                "document_root_left_contexts": dict(
                    item.left_contexts.most_common(16)
                ),
                "document_root_right_contexts": dict(
                    item.right_contexts.most_common(16)
                ),
                "document_root_basic_reason": root_reason,
                "root_graph_selected": root_selected,
                "root_graph_decision": (
                    "selected_for_unified_root_graph"
                    if root_selected
                    else f"audit_only:{root_reason}"
                ),
            }
            root_audit.append(root_row)
            stats["document_root_candidates_audited"] += 1
            if root_selected:
                stats["document_root_candidates_selected"] += 1
        else:
            stats["document_root_rejected_below_evidence_floor"] += 1

        if length == 1:
            continue
        if phrase in existing:
            stats["document_ngram_rejected_existing"] += 1
            continue
        if not HAN_EXACT_RE.fullmatch(phrase):
            stats["document_ngram_rejected_shape"] += 1
            continue
        minimum_units = DOCUMENT_NGRAM_MIN_UNITS[length]
        minimum_files = DOCUMENT_NGRAM_MIN_FILES[length]
        minimum_occurrences = DOCUMENT_NGRAM_MIN_OCCURRENCES[length]
        if item.unit_coverage < minimum_units:
            stats["document_ngram_rejected_unit_coverage"] += 1
            continue
        if item.file_coverage < minimum_files:
            stats["document_ngram_rejected_file_coverage"] += 1
            continue
        if item.occurrences < minimum_occurrences:
            stats["document_ngram_rejected_occurrences"] += 1
            continue
        basic_reason = raw_short_basic_reason(phrase)
        is_comparative_seed = any(
            pattern == phrase
            for pattern, _category, _root in COMPARATIVE_ROOT_PATTERNS
        )
        is_compound_seed = phrase in COMPOUND_ROOT_PATTERNS
        if (
            basic_reason != "eligible_basic_shape"
            and not is_comparative_seed
            and not is_compound_seed
        ):
            stats[f"document_ngram_rejected/{basic_reason}"] += 1
            continue
        category, triggers, category_reason = classify_long_candidate(
            phrase, item.unit_coverage, markers
        )
        if phrase in COMPOUND_ROOT_PATTERNS:
            category = COMPOUND_ROOT_PATTERNS[phrase]
            triggers = [phrase]
            category_reason = "document_compound_root_seed"
        if category is None:
            comparative_hits = [
                (pattern, category_name, root)
                for pattern, category_name, root in COMPARATIVE_ROOT_PATTERNS
                if pattern == phrase
            ]
            if comparative_hits:
                category = comparative_hits[0][1]
                triggers = [phrase]
                category_reason = "document_comparative_root_seed"
        if category is None:
            category = "audit-governance"
            triggers = []
            category_reason = "document_unclassified_seed"
        row = {
            "phrase": phrase,
            "category": category,
            "source_kind": "document-short-core-pass7",
            "discovery_score": round(
                phrase_score(item.occurrences, item.unit_coverage, phrase)
                + 0.25 * math.log1p(item.file_coverage),
                6,
            ),
            "document_ngram_occurrences": item.occurrences,
            "document_ngram_unit_coverage": item.unit_coverage,
            "document_ngram_file_coverage": item.file_coverage,
            "trigger_phrases": triggers,
            "document_seed_reason": category_reason,
            "document_seed_left_contexts": dict(item.left_contexts.most_common(16)),
            "document_seed_right_contexts": dict(item.right_contexts.most_common(16)),
            **exact_context_metrics(
                "document_seed_context", item.left_contexts, item.right_contexts
            ),
        }
        eligible.append(row)

    eligible.sort(
        key=lambda row: (
            float(row["discovery_score"]),
            int(row["document_ngram_unit_coverage"]),
            int(row["document_ngram_occurrences"]),
            row["phrase"],
        ),
        reverse=True,
    )
    selected = eligible if limit is None else eligible[:limit]
    selected_phrases = {row["phrase"] for row in selected}
    for row in eligible:
        item = dict(row)
        item["document_seed_selected"] = row["phrase"] in selected_phrases
        audit.append(item)
    stats["document_ngram_candidates_eligible"] = len(eligible)
    stats["document_ngram_candidates_selected"] = len(selected)
    stats["document_ngram_candidates_dropped_by_pool"] = max(
        0, len(eligible) - len(selected)
    )
    stats["document_ngram_selection_policy_no_top_k"] = int(limit is None)
    root_audit.sort(
        key=lambda row: (
            not bool(row["root_graph_selected"]),
            -int(row["document_root_unit_coverage"]),
            -int(row["document_root_occurrences"]),
            str(row["root"]),
        )
    )
    return selected, audit, root_audit, dict(stats)


def discover_chat_snapshot(root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    snapshot: list[dict[str, Any]] = []
    stats = Counter()
    for path in sorted(root.rglob("*.jsonl")):
        if not path.is_file():
            continue
        stats["jsonl_files_seen"] += 1
        try:
            stat = path.stat()
        except OSError:
            stats["jsonl_files_unreadable"] += 1
            continue
        snapshot.append({"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    stats["chat_snapshot_files"] = len(snapshot)
    return snapshot, dict(stats)


def resolve_frozen_chat_path(entry: dict[str, Any]) -> tuple[Path, bool]:
    original = Path(entry["path"])
    if original.is_file():
        return original, False

    codex_root = next(
        (parent for parent in original.parents if parent.name.lower() == ".codex"),
        None,
    )
    if codex_root is not None and "sessions" in {
        part.lower() for part in original.parts
    }:
        archived = codex_root / "archived_sessions" / original.name
        if archived.is_file() and archived.stat().st_size >= int(entry["size"]):
            return archived, True

    raise FileNotFoundError(
        f"frozen chat file is unavailable at its original or archived path: {original}"
    )


def iter_frozen_lines(
    entry: dict[str, Any], resolved_path: Path | None = None
) -> Iterator[bytes]:
    remaining = int(entry["size"])
    buffer = b""
    path = resolved_path or resolve_frozen_chat_path(entry)[0]
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                yield raw
    if buffer:
        yield buffer


def extract_assistant_text(event: dict[str, Any]) -> str:
    if event.get("type") != "response_item":
        return ""
    payload = event.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "message" or payload.get("role") != "assistant":
        return ""
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "output_text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def scan_chats(
    snapshot: list[dict[str, Any]],
    phrases: list[str],
    manifest_path: Path,
    context_phrases: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    matcher = AhoMatcher(phrases)
    context_indexes = {
        index for index, phrase in enumerate(phrases) if phrase in (context_phrases or set())
    }
    occurrence = Counter()
    message_coverage = Counter()
    exact_left_contexts: dict[int, Counter[str]] = defaultdict(Counter)
    exact_right_contexts: dict[int, Counter[str]] = defaultdict(Counter)
    stats = Counter()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path_hash", "resolved_path_hash", "relocated_after_snapshot",
                "snapshot_bytes", "mtime_ns", "status", "lines",
                "assistant_output_messages", "parse_errors", "changed_after_snapshot",
            ],
        )
        writer.writeheader()
        for file_number, entry in enumerate(snapshot, start=1):
            path = Path(entry["path"])
            resolved_path, relocated = resolve_frozen_chat_path(entry)
            local_occurrence = Counter()
            local_coverage = Counter()
            local_left_contexts: dict[int, Counter[str]] = defaultdict(Counter)
            local_right_contexts: dict[int, Counter[str]] = defaultdict(Counter)
            local_lines = 0
            local_messages = 0
            local_errors = 0
            saw_session_meta = False
            for raw in iter_frozen_lines(entry, resolved_path):
                local_lines += 1
                try:
                    event = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    local_errors += 1
                    continue
                if isinstance(event, dict) and event.get("type") == "session_meta":
                    saw_session_meta = True
                if not isinstance(event, dict):
                    continue
                text = extract_assistant_text(event)
                if not text or not HAN_RUN_RE.search(text):
                    continue
                local_messages += 1
                if "\ufffd" in text or MOJIBAKE_RE.search(text):
                    stats["garbled_assistant_messages"] += 1
                    continue
                seen: set[int] = set()
                for run in clean_chat_text(text):
                    for index, end in matcher.matches_with_end(run):
                        local_occurrence[index] += 1
                        seen.add(index)
                        if index in context_indexes:
                            start = end - len(phrases[index])
                            local_left_contexts[index][run[start - 1] if start else "^"] += 1
                            local_right_contexts[index][run[end] if end < len(run) else "$"] += 1
                for index in seen:
                    local_coverage[index] += 1
            status = "INCLUDED" if saw_session_meta else "EXCLUDED_NO_SESSION_META"
            if saw_session_meta:
                occurrence.update(local_occurrence)
                message_coverage.update(local_coverage)
                for index, contexts in local_left_contexts.items():
                    exact_left_contexts[index].update(contexts)
                for index, contexts in local_right_contexts.items():
                    exact_right_contexts[index].update(contexts)
                stats["lines"] += local_lines
                stats["assistant_output_messages"] += local_messages
                stats["parse_errors"] += local_errors
                stats["chat_files_included"] += 1
            changed = False
            try:
                current = resolved_path.stat()
                changed = current.st_size != entry["size"] or current.st_mtime_ns != entry["mtime_ns"]
            except OSError:
                changed = True
            if relocated:
                stats["chat_files_relocated_after_snapshot"] += 1
            writer.writerow(
                {
                    "path_hash": hashlib.blake2b(str(path).encode("utf-8"), digest_size=10).hexdigest(),
                    "resolved_path_hash": hashlib.blake2b(
                        str(resolved_path).encode("utf-8"), digest_size=10
                    ).hexdigest(),
                    "relocated_after_snapshot": str(relocated).lower(),
                    "snapshot_bytes": entry["size"],
                    "mtime_ns": entry["mtime_ns"],
                    "status": status,
                    "lines": local_lines,
                    "assistant_output_messages": local_messages,
                    "parse_errors": local_errors,
                    "changed_after_snapshot": str(changed).lower(),
                }
            )
            if file_number % 100 == 0:
                print(f"chats {file_number}/{len(snapshot)}", flush=True)
    total_messages = max(1, stats["assistant_output_messages"])
    result = {}
    for index, phrase in enumerate(phrases):
        result[phrase] = {
            "chat_occurrences": occurrence[index],
            "chat_message_coverage": message_coverage[index],
            "chat_message_coverage_rate": round(message_coverage[index] / total_messages, 8),
        }
        if index in context_indexes:
            result[phrase].update(
                exact_context_metrics(
                    "chat_context",
                    exact_left_contexts[index],
                    exact_right_contexts[index],
                )
            )
    return result, dict(stats)


def prune_dominated_long(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_phrase = {row["phrase"]: row for row in rows}
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (-len(item["phrase"]), item["phrase"])):
        phrase = row["phrase"]
        if row.get("source_kind") in FAMILY_SOURCE_KINDS or phrase in REQUIRED_FINAL_PHRASES:
            kept.append(row)
            continue
        dominated_by = None
        for longer, longer_row in by_phrase.items():
            if len(longer) <= len(phrase) or phrase not in longer:
                continue
            if (
                int(longer_row["combined_coverage"])
                >= 0.80 * int(row["combined_coverage"])
            ):
                dominated_by = longer
                break
        if dominated_by:
            row = dict(row)
            row["final_rejection_reason"] = f"dominated_fragment_of:{dominated_by}"
            rejected.append(row)
        else:
            kept.append(row)
    return kept, rejected


def select_long_with_family_reserve(
    rows: list[dict[str, Any]], target: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Select within the global budget while preserving productive families."""
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row["combined_score"]),
            int(row["combined_coverage"]),
            int(row["combined_occurrences"]),
            len(str(row["phrase"])),
            str(row["phrase"]),
        ),
        reverse=True,
    )
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        if row.get("source_kind") not in FAMILY_SOURCE_KINDS:
            continue
        for trigger in row.get("trigger_phrases", []):
            groups[(str(trigger), length_bucket(str(row["phrase"])))].append(row)

    group_order = sorted(
        groups,
        key=lambda key: (
            float(groups[key][0]["combined_score"]),
            int(groups[key][0]["combined_coverage"]),
            key,
        ),
        reverse=True,
    )
    reserved: list[dict[str, Any]] = []
    reserved_phrases: set[str] = set()
    # Round-robin by rank: every productive root/bucket receives one slot
    # before any family receives its second slot.
    for rank in range(ROOT_FAMILY_FINAL_RESERVE_PER_BUCKET):
        for key in group_order:
            if len(reserved) >= target or rank >= len(groups[key]):
                continue
            row = groups[key][rank]
            phrase = str(row["phrase"])
            if phrase in reserved_phrases:
                continue
            reserved.append(row)
            reserved_phrases.add(phrase)
    selected_phrases = set(reserved_phrases)
    selected = list(reserved)
    for row in ordered:
        if len(selected) >= target:
            break
        if row["phrase"] in selected_phrases:
            continue
        selected.append(row)
        selected_phrases.add(str(row["phrase"]))
    overflow = [row for row in ordered if row["phrase"] not in selected_phrases]
    return selected, overflow, {
        "family_final_reserve_groups": len(groups),
        "family_final_reserved_rows": len(reserved),
        "family_final_selected_rows": sum(
            row.get("source_kind") in FAMILY_SOURCE_KINDS for row in selected
        ),
    }


def _cached_metric_value(field: str, value: str) -> Any:
    if field.endswith("_contexts"):
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, dict):
            raise ValueError(f"cached {field} must be a dictionary")
        return parsed
    if field.endswith(("_rate", "_dominance")):
        return float(value)
    return int(value)


def load_exact_count_cache(
    path: Path,
    phrases: set[str],
    context_phrases: set[str],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    set[str],
    dict[str, int],
]:
    """Reuse exact counts only when every field needed by this round exists."""
    chat_counts: dict[str, dict[str, Any]] = {}
    document_counts: dict[str, dict[str, Any]] = {}
    cached: set[str] = set()
    stats = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "phrase" not in reader.fieldnames:
            raise ValueError(f"exact count cache has no phrase column: {path}")
        for row in reader:
            stats["rows_read"] += 1
            phrase = str(row.get("phrase", ""))
            if phrase not in phrases or phrase in cached:
                continue
            required = [*CHAT_EXACT_BASE_FIELDS, *DOCUMENT_EXACT_BASE_FIELDS]
            if phrase in context_phrases:
                required.extend(EXACT_CONTEXT_FIELDS)
            if any(not str(row.get(field, "")).strip() for field in required):
                stats["rows_missing_required_metrics"] += 1
                continue
            try:
                chat = {
                    field: _cached_metric_value(field, str(row[field]))
                    for field in CHAT_EXACT_BASE_FIELDS
                }
                document = {
                    field: _cached_metric_value(field, str(row[field]))
                    for field in DOCUMENT_EXACT_BASE_FIELDS
                }
                if phrase in context_phrases:
                    for field in EXACT_CONTEXT_FIELDS:
                        target = chat if field.startswith("chat_") else document
                        target[field] = _cached_metric_value(field, str(row[field]))
            except (SyntaxError, TypeError, ValueError):
                stats["rows_invalid_metrics"] += 1
                continue
            chat_counts[phrase] = chat
            document_counts[phrase] = document
            cached.add(phrase)
    stats["phrases_requested"] = len(phrases)
    stats["phrases_reused"] = len(cached)
    stats["phrases_requiring_rescan"] = len(phrases - cached)
    return chat_counts, document_counts, cached, dict(stats)


def validate_exact_count_cache_binding(
    cache_path: Path,
    *,
    aggregate_sha256: str,
    chat_snapshot: Path,
    document_snapshot: Path,
) -> dict[str, Any]:
    metadata_path = cache_path.with_name("run_metadata.json")
    if not metadata_path.exists():
        raise ValueError(f"exact count cache has no sibling run_metadata.json: {cache_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    def snapshot_files_hash(path: Path) -> str:
        payload = json.loads(path.read_text(encoding="utf-8"))
        files = payload.get("files")
        if not isinstance(files, list):
            raise ValueError(f"snapshot has no files list: {path}")
        return snapshot_file_set_sha256(files)

    cached_chat_snapshot = cache_path.with_name("chat_snapshot.json")
    cached_document_snapshot = cache_path.with_name("document_snapshot.json")
    if not cached_chat_snapshot.exists() or not cached_document_snapshot.exists():
        raise ValueError("exact count cache has no sibling frozen snapshots")
    current_chat_snapshot_sha256 = snapshot_files_hash(chat_snapshot)
    current_document_snapshot_sha256 = snapshot_files_hash(document_snapshot)
    cached_chat_snapshot_sha256 = snapshot_files_hash(cached_chat_snapshot)
    cached_document_snapshot_sha256 = snapshot_files_hash(cached_document_snapshot)
    checks = {
        "aggregate_sha256": metadata.get("aggregate_candidates_sha256")
        == aggregate_sha256,
        "chat_snapshot": cached_chat_snapshot_sha256
        == current_chat_snapshot_sha256,
        "document_snapshot": cached_document_snapshot_sha256
        == current_document_snapshot_sha256,
    }
    if not all(checks.values()):
        raise ValueError(
            "exact count cache is not bound to the current frozen inputs: "
            + json.dumps(checks, sort_keys=True)
        )
    return {
        "cache_path": str(cache_path),
        "cache_sha256": sha256_path(cache_path),
        "metadata_path": str(metadata_path),
        "metadata_sha256": sha256_path(metadata_path),
        "chat_snapshot_file_set_sha256": current_chat_snapshot_sha256,
        "document_snapshot_file_set_sha256": current_document_snapshot_sha256,
        "binding_checks": checks,
    }


def combine_metrics(
    candidates: dict[str, dict[str, Any]],
    chat_counts: dict[str, dict[str, Any]],
    doc_counts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for phrase, metadata in candidates.items():
        row = dict(metadata)
        row.update(chat_counts[phrase])
        row.update(doc_counts[phrase])
        row["combined_occurrences"] = (
            row["chat_occurrences"] + row["md_occurrences"] + row["tex_occurrences"]
        )
        row["combined_coverage"] = (
            row["chat_message_coverage"] + row["md_unit_coverage"] + row["tex_unit_coverage"]
        )
        document_coverage = row["md_unit_coverage"] + row["tex_unit_coverage"]
        if row["chat_message_coverage"] and document_coverage:
            row["evidence_scope"] = "chat-and-document"
        elif row["chat_message_coverage"]:
            row["evidence_scope"] = "chat-only"
        elif document_coverage:
            row["evidence_scope"] = "document-only"
        else:
            row["evidence_scope"] = "none"
        row["combined_score"] = phrase_score(
            row["combined_occurrences"], row["combined_coverage"], phrase
        )
        rows.append(row)
    return rows


def raw_short_live_context_reason(row: dict[str, Any]) -> str | None:
    for side in ("left", "right"):
        context_count = int(row.get(f"chat_context_{side}_context_count", 0))
        boundary_rate = float(row.get(f"chat_context_{side}_boundary_rate", 0.0))
        dominance = float(
            row.get(f"chat_context_{side}_nonboundary_dominance", 1.0)
        )
        if (
            context_count <= RAW_SHORT_LIVE_MIN_CONTEXTS
            and boundary_rate < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        ):
            return f"live_{side}_context_count_lt_{RAW_SHORT_LIVE_MIN_CONTEXTS}"
        if (
            dominance > RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE
            and boundary_rate < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        ):
            return f"live_{side}_context_dominance_gt_{RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE:.2f}"
        if (
            dominance > RAW_SHORT_LIVE_STRONG_FRAGMENT_DOMINANCE
            and boundary_rate < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        ):
            return f"live_{side}_boundary_dominance_gt_{RAW_SHORT_LIVE_STRONG_FRAGMENT_DOMINANCE:.2f}"
    left_boundary = float(row.get("chat_context_left_boundary_rate", 0.0))
    right_boundary = float(row.get("chat_context_right_boundary_rate", 0.0))
    if (
        left_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and right_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
    ):
        return "live_both_sides_boundary_lt_0.10"
    return None


def root_inversion_live_context_reason(row: dict[str, Any]) -> str | None:
    """Use accessor variety to separate a full family from an n-gram cut.

    Chinese words need not sit next to punctuation, so sentence-edge rates are
    not treated as mandatory. A candidate also passes when both sides have
    diverse neighbours. A fixed extension such as 术正确 or 收紧一 instead has
    a dominant missing character on one side and remains audit-only.
    """
    metrics: dict[str, tuple[int, float, float]] = {}
    for side in ("left", "right"):
        context_count = int(row.get(f"chat_context_{side}_context_count", 0))
        boundary_rate = float(row.get(f"chat_context_{side}_boundary_rate", 0.0))
        dominance = float(
            row.get(f"chat_context_{side}_nonboundary_dominance", 1.0)
        )
        metrics[side] = (context_count, boundary_rate, dominance)
        if (
            context_count < RAW_SHORT_LIVE_MIN_CONTEXTS
            and boundary_rate < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        ):
            return f"live_{side}_context_count_lt_{RAW_SHORT_LIVE_MIN_CONTEXTS}"
        if (
            dominance > RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE
            and boundary_rate < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        ):
            return (
                f"live_{side}_context_dominance_gt_"
                f"{RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE:.2f}"
            )
    left = metrics["left"]
    right = metrics["right"]
    if (
        left[1] < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and right[1] < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and (
            left[2] > RAW_SHORT_LIVE_STRONG_FRAGMENT_DOMINANCE
            or right[2] > RAW_SHORT_LIVE_STRONG_FRAGMENT_DOMINANCE
        )
    ):
        return "live_no_sentence_boundary_and_one_side_dominant"
    return None


def root_inversion_edge_modifier_reason(
    row: dict[str, Any],
    phrase_rows: dict[str, dict[str, Any]],
) -> str | None:
    """Reject clipped edge expansions before they become literal bans.

    Live left/right diversity proves that the whole n-gram recurs, but it does
    not prove that the material beside a root is a complete word.  For an edge
    family such as 口径+收紧, the non-root modifier must therefore be at least
    two characters and independently attested as an exact candidate.  This
    blocks fixed-width cuts such as 轮+只做, 化+改写 and 只做+定.
    """
    if str(row.get("root_inversion_gate_kind", "")) != "edge_context_pending":
        return None
    prefix = str(row.get("root_inversion_prefix", ""))
    suffix = str(row.get("root_inversion_suffix", ""))
    modifiers = [part for part in (prefix, suffix) if part]
    if len(modifiers) != 1:
        return "edge_modifier_not_single_complete_side"
    modifier = modifiers[0]
    if len(modifier) < 2:
        return "edge_modifier_length_lt_2"
    if (
        modifier in STRICT_RELEASE_FRAGMENTS
        or modifier in SUBPHRASE_FRAGMENT_EXACT
        or modifier in FORBIDDEN_FINAL_FRAGMENTS
    ):
        return "edge_modifier_known_fragment"
    if modifier in STRICT_RELEASE_PROTECTED_CONTENT:
        return "edge_modifier_protected_content"
    if modifier in STRICT_RELEASE_FUNCTION_OR_GENERIC:
        return "edge_modifier_function_or_generic"
    modifier_row = phrase_rows.get(modifier)
    if modifier_row is None:
        return "edge_modifier_not_independently_attested"

    source = str(modifier_row.get("source_kind", ""))
    if source == "raw-short-core-pass4":
        context_reason = raw_short_live_context_reason(modifier_row)
        if context_reason:
            return f"edge_modifier_{context_reason}"

    md_coverage = int(modifier_row.get("md_unit_coverage", 0))
    tex_coverage = int(modifier_row.get("tex_unit_coverage", 0))
    document_coverage = md_coverage + tex_coverage
    # A TeX-dominant independently attested modifier is more plausibly a
    # technical term than a reusable style shell.  It remains in the audit
    # catalog but cannot drag a neutral domain phrase into the strict list.
    if document_coverage >= 50 and _ratio(tex_coverage, document_coverage) >= 0.70:
        return "edge_modifier_tex_dominant_technical"
    return None


def document_short_semantic_reason(row: dict[str, Any]) -> str | None:
    """Gate document-only short seeds after the exact frozen rescan."""
    phrase = str(row.get("phrase", ""))
    if phrase in STRICT_RELEASE_PROTECTED_CONTENT:
        return "protected_content_exact"
    if phrase in STRICT_RELEASE_FUNCTION_OR_GENERIC or phrase in NOISE_EXACT:
        return "function_or_generic_exact"
    if phrase in STRICT_RELEASE_FRAGMENTS or phrase in SUBPHRASE_FRAGMENT_EXACT:
        return "known_short_fragment"

    # Raw frequency in another corpus is corroboration, not semantic evidence.
    # Unanchored document seeds stay in the discovery/audit tables only.
    if not row.get("trigger_phrases"):
        return "document_style_anchor_missing"

    document_units = int(row.get("md_unit_coverage", 0)) + int(
        row.get("tex_unit_coverage", 0)
    )
    document_files = int(row.get("md_file_coverage", 0)) + int(
        row.get("tex_file_coverage", 0)
    )
    if document_units < DOCUMENT_NGRAM_MIN_UNITS.get(len(phrase), 50):
        return "document_unit_coverage_below_seed_threshold"
    if document_files < DOCUMENT_NGRAM_MIN_FILES.get(len(phrase), 3):
        return "document_file_coverage_below_seed_threshold"
    document_occurrences = int(row.get("md_occurrences", 0)) + int(
        row.get("tex_occurrences", 0)
    )
    if document_occurrences < DOCUMENT_NGRAM_MIN_OCCURRENCES.get(len(phrase), 80):
        return "document_occurrences_below_seed_threshold"

    total_coverage = int(row.get("chat_message_coverage", 0)) + document_units
    tex_share = _ratio(int(row.get("tex_unit_coverage", 0)), document_units)
    chat_share = _ratio(int(row.get("chat_message_coverage", 0)), total_coverage)
    if (
        document_units >= int(STRICT_RELEASE_THRESHOLDS["technical_min_document_units"])
        and tex_share >= float(STRICT_RELEASE_THRESHOLDS["technical_tex_share_min"])
        and chat_share <= float(STRICT_RELEASE_THRESHOLDS["technical_chat_share_max"])
    ):
        return "technical_tex_dominant"

    left_count = int(
        row.get(
            "document_context_left_context_count",
            row.get("document_seed_context_left_context_count", 0),
        )
    )
    right_count = int(
        row.get(
            "document_context_right_context_count",
            row.get("document_seed_context_right_context_count", 0),
        )
    )
    left_boundary = float(
        row.get(
            "document_context_left_boundary_rate",
            row.get("document_seed_context_left_boundary_rate", 0.0),
        )
    )
    right_boundary = float(
        row.get(
            "document_context_right_boundary_rate",
            row.get("document_seed_context_right_boundary_rate", 0.0),
        )
    )
    if left_count < RAW_SHORT_LIVE_MIN_CONTEXTS:
        return "document_left_context_count_lt_4"
    if right_count < RAW_SHORT_LIVE_MIN_CONTEXTS:
        return "document_right_context_count_lt_4"
    left_dominance = float(
        row.get(
            "document_context_left_nonboundary_dominance",
            row.get("document_seed_context_left_nonboundary_dominance", 1.0),
        )
    )
    right_dominance = float(
        row.get(
            "document_context_right_nonboundary_dominance",
            row.get("document_seed_context_right_nonboundary_dominance", 1.0),
        )
    )
    if (
        left_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and left_dominance > RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE
    ):
        return "document_left_context_dominance_gt_0.75"
    if (
        right_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and right_dominance > RAW_SHORT_LIVE_MAX_NONBOUNDARY_DOMINANCE
    ):
        return "document_right_context_dominance_gt_0.75"
    if (
        left_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
        and right_boundary < RAW_SHORT_LIVE_MIN_BOUNDARY_RATE
    ):
        return "document_both_sides_boundary_lt_0.10"

    if int(row.get("chat_message_coverage", 0)) >= 80:
        chat_reason = raw_short_live_context_reason(row)
        if chat_reason:
            return "document_chat_context:" + chat_reason
    return None


def csv_decomposition_semantic_reason(row: dict[str, Any]) -> str | None:
    """Apply a conservative semantic gate to children mined from old CSVs."""
    phrase = str(row.get("phrase", ""))
    if phrase in STRICT_RELEASE_PROTECTED_CONTENT:
        return "protected_content_exact"
    if phrase in STRICT_RELEASE_FUNCTION_OR_GENERIC or phrase in NOISE_EXACT:
        return "function_or_generic_exact"
    if phrase in SUBPHRASE_FRAGMENT_EXACT or phrase in FORBIDDEN_FINAL_FRAGMENTS:
        return "known_short_fragment"
    component_terms = (
        STRICT_RELEASE_PROTECTED_CONTENT
        | STRICT_RELEASE_FUNCTION_OR_GENERIC
        | frozenset(NOISE_EXACT)
        | frozenset(ROOT_FAMILY_NOISE_EXACT)
    )
    embedded = sorted(
        (term for term in component_terms if len(term) >= 2 and term in phrase),
        key=lambda term: (-len(term), term),
    )
    if embedded:
        return "protected_or_generic_component:" + ",".join(embedded[:4])
    return raw_short_live_context_reason(row)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 8) if denominator else 0.0


def strict_literal_release_veto(phrase: str) -> str | None:
    """Return the route-independent reason a literal cannot be a hard ban."""
    if phrase in REQUIRED_FINAL_PHRASES:
        return None
    if phrase in STRICT_RELEASE_DISCOVERY_ROOT_ONLY:
        return "discovery_root_only"
    if (
        phrase in STRICT_RELEASE_FRAGMENTS
        or phrase in SUBPHRASE_FRAGMENT_EXACT
        or phrase in FORBIDDEN_FINAL_FRAGMENTS
    ):
        return "fragment"
    if phrase in STRICT_RELEASE_PROTECTED_CONTENT or any(
        term in phrase for term in STRICT_RELEASE_PROTECTED_CONTENT
    ):
        return "protected_content"
    if phrase in STRICT_RELEASE_FUNCTION_OR_GENERIC or phrase in NOISE_EXACT:
        return "function_or_generic"
    if len(phrase) == 2 and phrase not in STRICT_RELEASE_SHORT_LITERALS:
        return "short_discovery_root_only"
    return None


def classify_raw_short_semantic_publication(row: dict[str, Any]) -> dict[str, Any]:
    """Separate frequent lexical items from style-bearing short cores.

    Frequency, boundary diversity, and repeated parent shells prove that a
    candidate is real; they do not prove that it is an undesirable writing
    habit.  This release classifier is deliberately downstream of discovery.
    It preserves rejected candidates in the audit output while preventing
    technical terms and generic grammar from becoming literal strict bans.
    """
    phrase = str(row["phrase"])
    family_parents = int(row.get("family_parent_count", 0))
    styled_parents = int(row.get("styled_parent_count", 0))
    chat_coverage = int(row.get("chat_message_coverage", 0))
    md_coverage = int(row.get("md_unit_coverage", 0))
    tex_coverage = int(row.get("tex_unit_coverage", 0))
    document_coverage = md_coverage + tex_coverage
    total_coverage = chat_coverage + document_coverage
    style_parent_ratio = _ratio(styled_parents, family_parents)
    discourse_attachment_count = int(
        row.get("discourse_attachment_parent_count", 0)
    )
    discourse_prefix_count = int(row.get("discourse_prefix_parent_count", 0))
    discourse_suffix_count = int(row.get("discourse_suffix_parent_count", 0))
    discourse_attachment_ratio = _ratio(
        discourse_attachment_count, family_parents
    )
    chat_share = _ratio(chat_coverage, total_coverage)
    tex_document_share = _ratio(tex_coverage, document_coverage)
    signals = {
        "style_parent_ratio": style_parent_ratio,
        "chat_coverage_share": chat_share,
        "tex_document_coverage_share": tex_document_share,
        "family_parent_count": family_parents,
        "styled_parent_count": styled_parents,
        "discourse_attachment_parent_count": discourse_attachment_count,
        "discourse_attachment_parent_ratio": discourse_attachment_ratio,
        "discourse_prefix_parent_count": discourse_prefix_count,
        "discourse_suffix_parent_count": discourse_suffix_count,
    }

    if phrase in STRICT_RELEASE_PROTECTED_CONTENT:
        return {
            "semantic_class": "technical_or_content",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "protected_content_exact",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }
    if phrase in STRICT_RELEASE_DISCOVERY_ROOT_ONLY:
        return {
            "semantic_class": "discovery_root_only",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "discovery_root_requires_complete_collocation",
            "semantic_release_roots": [phrase],
            "semantic_signals": {
                **signals,
                "short_baseline_current_policy_recheck": False,
            },
        }
    if phrase in STRICT_RELEASE_FUNCTION_OR_GENERIC or phrase in NOISE_EXACT:
        return {
            "semantic_class": "function_or_generic",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "function_or_generic_exact",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }
    if (
        phrase in STRICT_RELEASE_FRAGMENTS
        or phrase in SUBPHRASE_FRAGMENT_EXACT
        or phrase in FORBIDDEN_FINAL_FRAGMENTS
    ):
        return {
            "semantic_class": "fragment",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "known_short_fragment",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }

    thresholds = STRICT_RELEASE_THRESHOLDS
    style_ratio_min = float(thresholds["style_parent_ratio_min"])
    if (
        document_coverage >= int(thresholds["technical_min_document_units"])
        and tex_document_share >= float(thresholds["technical_tex_share_min"])
        and chat_share <= float(thresholds["technical_chat_share_max"])
        and style_parent_ratio < style_ratio_min
    ):
        return {
            "semantic_class": "technical_or_content",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "technical_tex_dominant",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }

    category = str(row.get("category", ""))
    semantic_class = (
        "evaluation_or_packaging"
        if category
        in {
            "certainty-limitation",
            "academic-packaging",
            "research-self-proof",
            "emphasis-shell",
        }
        else "discourse_or_process"
    )
    if phrase in STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES:
        return {
            "semantic_class": semantic_class,
            "semantic_release_decision": "publish_strict",
            "semantic_release_reason": "high_confidence_style_core",
            "semantic_release_roots": [phrase],
            "semantic_signals": signals,
        }
    if (
        discourse_attachment_count
        >= int(thresholds["discourse_attachment_min_parent_count"])
        and discourse_attachment_ratio
        >= float(thresholds["discourse_attachment_min_parent_ratio"])
        and style_parent_ratio
        >= float(thresholds["discourse_attachment_min_style_parent_ratio"])
        and chat_share >= float(thresholds["chat_dominant_share_min"])
    ):
        return {
            "semantic_class": semantic_class,
            "semantic_release_decision": "publish_strict",
            "semantic_release_reason": "relative_discourse_attachment",
            "semantic_release_roots": [phrase],
            "semantic_signals": signals,
        }
    attachment_ready = (
        discourse_attachment_count
        >= int(thresholds["discourse_attachment_min_parent_count"])
        and discourse_attachment_ratio
        >= float(thresholds["discourse_attachment_min_parent_ratio"])
        and style_parent_ratio
        >= float(thresholds["discourse_attachment_min_style_parent_ratio"])
    )
    return {
        "semantic_class": "ambiguous_frequent_expression",
        "semantic_release_decision": "audit_only",
        "semantic_release_reason": (
            "insufficient_chat_dominant_style_evidence"
            if attachment_ready
            else "insufficient_relative_discourse_attachment"
        ),
        "semantic_release_roots": [],
        "semantic_signals": signals,
    }


def classify_baseline_semantic_publication(row: dict[str, Any]) -> dict[str, Any]:
    """Re-evaluate short inherited literals when the semantic policy changes.

    A prior release is evidence that a phrase was once reviewed, not evidence
    that it still satisfies the current policy.  Long, complete phrases retain
    their baseline release after the route-independent veto.  Short literals
    are re-run through the same family/context classifier used for newly
    discovered cores, so ordinary academic words cannot survive only because
    an older inventory contained them.
    """
    phrase = str(row["phrase"])
    literal_veto = strict_literal_release_veto(phrase)
    if literal_veto is not None:
        return {
            "semantic_class": "baseline_discovery_or_content_only",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": f"baseline_{literal_veto}",
            "semantic_release_roots": [],
            "semantic_signals": {
                "baseline_revalidated": False,
                "literal_veto": literal_veto,
                "short_baseline_current_policy_recheck": len(phrase) <= 4,
            },
        }
    if phrase in REQUIRED_FINAL_PHRASES:
        return {
            "semantic_class": "revalidated_required_family_anchor",
            "semantic_release_decision": "publish_strict",
            "semantic_release_reason": "baseline_required_family_regression_anchor",
            "semantic_release_roots": [phrase],
            "semantic_signals": {
                "baseline_revalidated": True,
                "required_family_regression_anchor": True,
                "short_baseline_current_policy_recheck": len(phrase) <= 4,
            },
        }
    if len(phrase) <= 4:
        decision = classify_raw_short_semantic_publication(row)
        signals = {
            **dict(decision.get("semantic_signals", {})),
            "baseline_revalidated": (
                decision["semantic_release_decision"] == "publish_strict"
            ),
            "short_baseline_current_policy_recheck": True,
        }
        if decision["semantic_release_decision"] == "publish_strict":
            return {
                **decision,
                "semantic_class": f"revalidated_baseline_{decision['semantic_class']}",
                "semantic_release_reason": (
                    "baseline_short_current_policy:"
                    + str(decision["semantic_release_reason"])
                ),
                "semantic_signals": signals,
            }
        return {
            **decision,
            "semantic_class": f"baseline_{decision['semantic_class']}",
            "semantic_release_reason": (
                "baseline_short_current_policy:"
                + str(decision["semantic_release_reason"])
            ),
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }
    anchors = sorted(
        {
            token
            for token in (
                set(STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES)
                | set(STRICT_RELEASE_DISCOVERY_ROOT_ONLY)
                | set(REQUIRED_FINAL_PHRASES)
            )
            if token and token in phrase
        },
        key=lambda token: (-len(token), token),
    )
    signals = {
        "baseline_revalidated": True,
        "short_baseline_current_policy_recheck": False,
        "complete_phrase_anchors": anchors,
    }
    if not anchors:
        return {
            "semantic_class": "baseline_long_unanchored",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "baseline_long_no_style_anchor",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }
    if not has_complete_boundary(phrase, markers=anchors):
        return {
            "semantic_class": "baseline_long_incomplete_shell",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "baseline_long_incomplete_boundary",
            "semantic_release_roots": [],
            "semantic_signals": signals,
        }
    has_live_context_metrics = any(
        key in row
        for key in (
            "chat_context_left_context_count",
            "chat_context_right_context_count",
            "document_context_left_context_count",
            "document_context_right_context_count",
        )
    )
    live_reason = raw_short_live_context_reason(row) if has_live_context_metrics else None
    if live_reason is not None and phrase not in REQUIRED_FINAL_PHRASES:
        return {
            "semantic_class": "baseline_long_fixed_window",
            "semantic_release_decision": "audit_only",
            "semantic_release_reason": "baseline_long_live_context:" + live_reason,
            "semantic_release_roots": [],
            "semantic_signals": {**signals, "live_context_reason": live_reason},
        }
    return {
        "semantic_class": "revalidated_baseline_style",
        "semantic_release_decision": "publish_strict",
        "semantic_release_reason": "baseline_revalidated_complete_phrase",
        "semantic_release_roots": anchors,
        "semantic_signals": signals,
    }


def annotate_raw_short_discovery_audit(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Label high-recall discovery rows before the expensive exact rescan."""
    annotated = []
    for original in rows:
        row = dict(original)
        phrase = str(row["phrase"])
        reason = str(row.get("preselection_reason", ""))
        if phrase in STRICT_RELEASE_PROTECTED_CONTENT:
            row.update(
                semantic_class="technical_or_content",
                semantic_release_decision="audit_only",
                semantic_release_reason="protected_content_exact",
            )
        elif phrase in STRICT_RELEASE_FUNCTION_OR_GENERIC or phrase in NOISE_EXACT:
            row.update(
                semantic_class="function_or_generic",
                semantic_release_decision="audit_only",
                semantic_release_reason="function_or_generic_exact",
            )
        elif phrase in STRICT_RELEASE_DISCOVERY_ROOT_ONLY:
            row.update(
                semantic_class="discovery_root_only",
                semantic_release_decision="audit_only",
                semantic_release_reason="requires_complete_collocation",
            )
        elif phrase in STRICT_RELEASE_FRAGMENTS or reason != "eligible_raw_short_core":
            row.update(
                semantic_class="fragment_or_unqualified",
                semantic_release_decision="audit_only",
                semantic_release_reason=f"discovery_gate:{reason}",
            )
        else:
            row.update(
                semantic_class="pending_exact_context",
                semantic_release_decision="pending_exact_rescan",
                semantic_release_reason="requires_chat_document_semantic_release",
            )
        annotated.append(row)
    return annotated


def annotate_semantic_publication(
    rows: list[dict[str, Any]],
    baseline_semantic_schema: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Annotate exact-rescan rows and propagate released roots to families."""
    annotated = [dict(row) for row in rows]
    raw_decisions: dict[str, dict[str, Any]] = {}
    for row in annotated:
        if row.get("source_kind") != "raw-short-core-pass4":
            continue
        decision = classify_raw_short_semantic_publication(row)
        literal_veto = strict_literal_release_veto(str(row["phrase"]))
        if (
            decision["semantic_release_decision"] == "publish_strict"
            and literal_veto is not None
        ):
            decision = {
                "semantic_class": "route_independent_literal_veto",
                "semantic_release_decision": "audit_only",
                "semantic_release_reason": f"candidate_{literal_veto}",
                "semantic_release_roots": [],
                "semantic_signals": {
                    **dict(decision.get("semantic_signals", {})),
                    "literal_veto": literal_veto,
                },
            }
        row.update(decision)
        raw_decisions[str(row["phrase"])] = decision

    phrase_rows = {str(row["phrase"]): row for row in annotated}

    baseline_style_anchors = {
        str(row["phrase"])
        for row in annotated
        if row.get("source_kind") == "baseline-v1"
        and strict_literal_release_veto(str(row["phrase"])) is None
    }
    annotated_phrases = {str(row.get("phrase", "")) for row in annotated}
    discovery_root_anchors = {
        phrase
        for phrase in STRICT_RELEASE_DISCOVERY_ROOT_ONLY
        if phrase in annotated_phrases
    }

    released_cores = sorted(
        phrase
        for phrase, decision in raw_decisions.items()
        if decision["semantic_release_decision"] == "publish_strict"
    )
    released_matcher = AhoMatcher(released_cores)
    # A protected component vetoes a family even when it is not the complete
    # phrase.  Otherwise a released discourse root could smuggle technical
    # nouns, generic quantifiers, or known noise into a longer strict entry.
    protected_terms = sorted(
        STRICT_RELEASE_PROTECTED_CONTENT
        | STRICT_RELEASE_FUNCTION_OR_GENERIC
        | frozenset(NOISE_EXACT)
        | frozenset(ROOT_FAMILY_NOISE_EXACT)
    )
    protected_matcher = AhoMatcher(protected_terms)
    hard_content_terms = sorted(STRICT_RELEASE_PROTECTED_CONTENT)
    hard_content_matcher = AhoMatcher(hard_content_terms)
    for row in annotated:
        source = str(row.get("source_kind", ""))
        if source == "raw-short-core-pass4":
            continue
        if source == "baseline-v1":
            phrase = str(row["phrase"])
            row.update(classify_baseline_semantic_publication(row))
            row.setdefault("semantic_signals", {})[
                "baseline_input_semantic_schema"
            ] = baseline_semantic_schema or ""
            row["semantic_signals"]["baseline_policy_replayed"] = False
            continue
        if source not in {
            "raw-core-family-pass5",
            "single-root-family-pass3",
            "root-inversion-family-pass8",
        }:
            phrase = str(row["phrase"])
            literal_veto = strict_literal_release_veto(phrase)
            if literal_veto is not None:
                row.update(
                    semantic_class="route_independent_literal_veto",
                    semantic_release_decision="audit_only",
                    semantic_release_reason=f"candidate_{literal_veto}",
                    semantic_release_roots=[],
                    semantic_signals={"literal_veto": literal_veto},
                )
            else:
                row.update(
                    semantic_class="route_evidence_release",
                    semantic_release_decision="publish_strict",
                    semantic_release_reason=f"route_evidence:{source}",
                    semantic_release_roots=list(row.get("trigger_phrases", [])),
                    semantic_signals={"route_evidence_released": True},
                )
            continue

        if source == "raw-core-family-pass5":
            candidate_roots = [
                str(root)
                for root in row.get("trigger_phrases", [])
                if str(root) in raw_decisions
            ]
            released_hits = [
                root
                for root in candidate_roots
                if raw_decisions[root]["semantic_release_decision"] == "publish_strict"
            ]
        else:
            indexes = released_matcher.matches(str(row["phrase"]))
            released_hits = sorted(
                {released_cores[index] for index in indexes},
                key=lambda item: (-len(item), item),
            )
            candidate_roots = [
                phrase for phrase in raw_decisions if phrase in str(row["phrase"])
            ]

        phrase = str(row["phrase"])
        content_hits = sorted(
            {
                protected_terms[index]
                for index in protected_matcher.matches(phrase)
            },
            key=lambda item: (-len(item), item),
        )
        chat_coverage = int(row.get("chat_message_coverage", 0))
        md_coverage = int(row.get("md_unit_coverage", 0))
        tex_coverage = int(row.get("tex_unit_coverage", 0))
        document_coverage = md_coverage + tex_coverage
        total_coverage = chat_coverage + document_coverage
        tex_document_share = _ratio(tex_coverage, document_coverage)
        chat_share = _ratio(chat_coverage, total_coverage)
        technical_distribution = (
            document_coverage
            >= int(STRICT_RELEASE_THRESHOLDS["technical_min_document_units"])
            and tex_document_share
            >= float(STRICT_RELEASE_THRESHOLDS["technical_tex_share_min"])
            and chat_share
            <= float(STRICT_RELEASE_THRESHOLDS["technical_chat_share_max"])
        )
        if source == "root-inversion-family-pass8":
            candidate_roots = [str(root) for root in row.get("trigger_phrases", [])]
            hard_content_hits = sorted(
                {
                    hard_content_terms[index]
                    for index in hard_content_matcher.matches(phrase)
                },
                key=lambda item: (-len(item), item),
            )
            generic_roots = sorted(
                root
                for root in candidate_roots
                if root in STRICT_RELEASE_FUNCTION_OR_GENERIC
                or root in NOISE_EXACT
                or root in STRICT_RELEASE_FRAGMENTS
            )
            primary_root = str(row.get("root_inversion_primary_root", ""))
            family_shapes, family_shape_reason = (
                classify_root_inversion_family_shapes(phrase, candidate_roots)
            )
            generic_primary_comparative_shell = (
                primary_root in STRICT_RELEASE_FUNCTION_OR_GENERIC
                and any(
                    str(shape["root"]) == primary_root
                    and shape["gate_kind"] == "reversible_shell"
                    and str(shape.get("prefix", ""))
                    in ROOT_INVERSION_COMPARATIVE_PREFIXES
                    for shape in family_shapes
                )
            )
            blocking_generic_roots = sorted(
                root
                for root in generic_roots
                if not (
                    root == primary_root
                    and generic_primary_comparative_shell
                )
            )
            reversible_hits = sorted(
                {
                    str(shape["root"])
                    for shape in family_shapes
                    if shape["gate_kind"] == "reversible_shell"
                },
                key=lambda item: (-len(item), item),
            )
            exact_hits = sorted(
                {
                    str(shape["root"])
                    for shape in family_shapes
                    if shape["gate_kind"] == "exact_root"
                },
                key=lambda item: (-len(item), item),
            )
            edge_pending_hits = sorted(
                {
                    str(shape["root"])
                    for shape in family_shapes
                    if shape["gate_kind"] == "edge_context_pending"
                },
                key=lambda item: (-len(item), item),
            )
            context_envelope_hits = sorted(
                {
                    str(shape["root"])
                    for shape in family_shapes
                    if shape["gate_kind"] == "context_envelope_pending"
                },
                key=lambda item: (-len(item), item),
            )
            cross_source_released_roots = sorted(
                ({primary_root} & set(released_cores)) if primary_root else set(),
                key=lambda item: (-len(item), item),
            )
            shell_root_ready = (
                int(row.get("root_inversion_shell_parent_count", 0))
                >= ROOT_INVERSION_MIN_SHELL_PARENT_COUNT.get(len(primary_root), 2)
                and int(row.get("root_inversion_shell_type_count", 0))
                >= ROOT_INVERSION_MIN_SHELL_TYPE_COUNT.get(len(primary_root), 2)
                and int(
                    row.get("root_inversion_shell_weighted_parent_coverage", 0)
                )
                >= ROOT_INVERSION_MIN_WEIGHTED_COVERAGE.get(len(primary_root), 0)
            )
            confirmed_context_ready = bool(
                row.get("root_inversion_confirmed_context_ready", False)
            )
            root_first_shell_ready = bool(
                row.get("root_inversion_root_first_shell_ready", False)
            )
            root_ready = (
                shell_root_ready
                or root_first_shell_ready
                or confirmed_context_ready
            )
            root_first_evidence_anchor = (
                row.get("root_inversion_root_status") == "eligible_root_inversion"
                and root_ready
            )
            primary_root_anchored = (
                primary_root in released_cores
                or primary_root in baseline_style_anchors
                or primary_root in discovery_root_anchors
                or root_first_evidence_anchor
            )
            live_context_reason = root_inversion_live_context_reason(row)
            edge_modifier_reason = root_inversion_edge_modifier_reason(
                row, phrase_rows
            )
            protected_component_hits = sorted(
                hit
                for hit in content_hits
                if (
                    hit in STRICT_RELEASE_PROTECTED_CONTENT
                    or hit in STRICT_RELEASE_FUNCTION_OR_GENERIC
                )
                and hit not in candidate_roots
                and hit != primary_root
            )
            boundary_verified_hits = sorted(
                set(reversible_hits)
                | {
                    root
                    for root in exact_hits
                    if phrase in STRICT_RELEASE_SHORT_LITERALS
                    or phrase in REQUIRED_FINAL_PHRASES
                }
                | (
                    set(edge_pending_hits)
                    if live_context_reason is None and edge_modifier_reason is None
                    else set()
                ),
                key=lambda item: (-len(item), item),
            )
            if (
                context_envelope_hits
                and live_context_reason is None
                and has_complete_boundary(phrase, markers=context_envelope_hits)
            ):
                boundary_verified_hits = sorted(
                    set(boundary_verified_hits) | set(context_envelope_hits),
                    key=lambda item: (-len(item), item),
                )
            semantic_signals = {
                "candidate_roots": candidate_roots,
                "primary_root": primary_root,
                "hard_content_hits": hard_content_hits,
                "protected_component_hits": protected_component_hits,
                "generic_or_fragment_roots": generic_roots,
                "blocking_generic_or_fragment_roots": (
                    blocking_generic_roots
                ),
                "generic_primary_comparative_shell": (
                    generic_primary_comparative_shell
                ),
                "family_reversible_shell_roots": reversible_hits,
                "family_exact_roots": exact_hits,
                "family_exact_roots_discovery_only": sorted(
                    set(exact_hits) - set(boundary_verified_hits)
                ),
                "family_edge_context_pending_roots": edge_pending_hits,
                "family_context_envelope_pending_roots": context_envelope_hits,
                "family_shape_reason": family_shape_reason,
                "live_context_reason": live_context_reason,
                "edge_modifier_reason": edge_modifier_reason,
                "boundary_verified_roots": boundary_verified_hits,
                "cross_source_released_roots": cross_source_released_roots,
                "primary_root_anchored": primary_root_anchored,
                "root_first_evidence_anchor": root_first_evidence_anchor,
                "primary_root_anchor_source": (
                    "raw-short-cross-source"
                    if primary_root in released_cores
                    else "baseline-strict"
                    if primary_root in baseline_style_anchors
                    else "discovery-root-only"
                    if primary_root in discovery_root_anchors
                    else "root-first-evidence"
                    if root_first_evidence_anchor
                    else "none"
                ),
                "root_ready": root_ready,
                "shell_root_ready": shell_root_ready,
                "root_first_shell_ready": root_first_shell_ready,
                "confirmed_context_ready": confirmed_context_ready,
                "chat_coverage_share": chat_share,
                "tex_document_coverage_share": tex_document_share,
            }
            if (
                hard_content_hits
                or protected_component_hits
                or blocking_generic_roots
                or technical_distribution
            ):
                row.update(
                    semantic_class="technical_content_or_generic_root_family",
                    semantic_release_decision="audit_only",
                    semantic_release_reason=(
                        "root_inversion_hard_content"
                        if hard_content_hits
                        else "root_inversion_protected_component"
                        if protected_component_hits
                        else "root_inversion_generic_or_fragment_root"
                        if blocking_generic_roots
                        else "root_inversion_technical_tex_dominant"
                    ),
                    semantic_release_roots=[],
                    semantic_signals=semantic_signals,
                )
            elif not primary_root_anchored:
                row.update(
                    semantic_class="root_inversion_unanchored_family",
                    semantic_release_decision="audit_only",
                    semantic_release_reason=(
                        "root_inversion_primary_root_not_cross_source_anchored"
                    ),
                    semantic_release_roots=[],
                    semantic_signals=semantic_signals,
                )
            elif edge_modifier_reason:
                row.update(
                    semantic_class="root_inversion_incomplete_edge_family",
                    semantic_release_decision="audit_only",
                    semantic_release_reason=(
                        f"root_inversion_edge_modifier:{edge_modifier_reason}"
                    ),
                    semantic_release_roots=[],
                    semantic_signals=semantic_signals,
                )
            elif root_ready and boundary_verified_hits and live_context_reason is None:
                row.update(
                    semantic_class="root_inversion_style_family",
                    semantic_release_decision="publish_strict",
                    semantic_release_reason=(
                        "root_inversion_reversible_shell_and_live_context"
                        if reversible_hits
                        else "root_inversion_exact_root_and_live_context"
                        if exact_hits
                        else "root_inversion_edge_verified_by_live_context"
                        if edge_pending_hits
                        else "root_inversion_context_envelope_verified"
                    ),
                    semantic_release_roots=boundary_verified_hits,
                    semantic_signals=semantic_signals,
                )
            else:
                row.update(
                    semantic_class="root_inversion_unanchored_family",
                    semantic_release_decision="audit_only",
                    semantic_release_reason=(
                        "root_inversion_root_not_shell_ready"
                        if not root_ready
                        else f"root_inversion_live_context:{live_context_reason}"
                        if live_context_reason
                        else "root_inversion_lacks_complete_shell_evidence"
                    ),
                    semantic_release_roots=[],
                    semantic_signals=semantic_signals,
                )
            continue
        discovery_only_hits = sorted(
            root for root in candidate_roots if root in discovery_root_anchors
        )
        family_anchor_hits = sorted(
            set(released_hits) | set(discovery_only_hits),
            key=lambda item: (-len(item), item),
        )
        family_attachment_hits = sorted(
            root
            for root in family_anchor_hits
            if phrase_has_relative_discourse_attachment(phrase, root)
        )
        semantic_signals = {
            "candidate_roots": sorted(candidate_roots),
            "discovery_root_only_hits": discovery_only_hits,
            "family_anchor_roots": family_anchor_hits,
            "protected_content_hits": content_hits,
            "family_relative_attachment_roots": family_attachment_hits,
            "chat_coverage_share": chat_share,
            "tex_document_coverage_share": tex_document_share,
        }

        if family_anchor_hits and (content_hits or technical_distribution):
            row.update(
                semantic_class="technical_or_content_family",
                semantic_release_decision="audit_only",
                semantic_release_reason=(
                    "family_protected_content"
                    if content_hits
                    else "family_technical_tex_dominant"
                ),
                semantic_release_roots=[],
                semantic_signals=semantic_signals,
            )
        elif family_attachment_hits:
            row.update(
                semantic_class="released_style_core_family",
                semantic_release_decision="publish_strict",
                semantic_release_reason="family_relative_discourse_attachment",
                semantic_release_roots=family_attachment_hits,
                semantic_signals=semantic_signals,
            )
        elif family_anchor_hits:
            row.update(
                semantic_class="unanchored_style_core_family",
                semantic_release_decision="audit_only",
                semantic_release_reason="family_lacks_relative_discourse_attachment",
                semantic_release_roots=[],
                semantic_signals=semantic_signals,
            )
        else:
            root_reasons = sorted(
                {
                    str(raw_decisions[root]["semantic_release_reason"])
                    for root in candidate_roots
                }
            )
            row.update(
                semantic_class="unreleased_root_family",
                semantic_release_decision="audit_only",
                semantic_release_reason=(
                    "family_has_no_released_style_core"
                    + (":" + ",".join(root_reasons) if root_reasons else "")
                ),
                semantic_release_roots=[],
                semantic_signals=semantic_signals,
            )

    stats = Counter()
    for row in annotated:
        if row.get("source_kind") not in SEMANTIC_GATED_SOURCE_KINDS:
            continue
        stats[f"decision/{row.get('semantic_release_decision', 'missing')}"] += 1
        stats[f"reason/{row.get('semantic_release_reason', 'missing')}"] += 1
        stats[f"class/{row.get('semantic_class', 'missing')}"] += 1
    stats["released_raw_short_cores"] = len(released_cores)
    return annotated, dict(stats)


def select_final(
    rows: Iterable[dict[str, Any]],
    target_subphrases: int,
    target_longphrases: int,
    *,
    retain_rejected_rows: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    baseline = [
        row
        for row in rows
        if row["source_kind"] == "baseline-v1"
        and row["combined_coverage"] > 0
        and row.get("semantic_release_decision") == "publish_strict"
    ]
    sub = []
    raw_short = []
    document_short = []
    long = []
    priority_long = []
    rejected = []
    rejected_count = 0
    reasons = Counter()

    def record_rejection(row: dict[str, Any]) -> None:
        nonlocal rejected_count
        rejected_count += 1
        if retain_rejected_rows:
            rejected.append(row)
    for row in rows:
        source = row["source_kind"]
        if source == "baseline-v1":
            if row.get("semantic_release_decision") != "publish_strict":
                reason = "semantic_audit_only:" + str(
                    row.get("semantic_release_reason", "missing_baseline_revalidation")
                )
                item = dict(row)
                item["final_rejection_reason"] = reason
                record_rejection(item)
                reasons[reason] += 1
            continue
        semantic_decision = row.get("semantic_release_decision")
        if semantic_decision == "audit_only" or (
            source in SEMANTIC_GATED_SOURCE_KINDS
            and semantic_decision != "publish_strict"
        ):
            reason = "semantic_audit_only:" + str(
                row.get("semantic_release_reason", "missing_semantic_release_decision")
            )
            item = dict(row)
            item["final_rejection_reason"] = reason
            record_rejection(item)
            reasons[reason] += 1
            continue
        doc_coverage = row["md_unit_coverage"] + row["tex_unit_coverage"]
        if source in SUBPHRASE_SOURCE_KINDS:
            minimum_chat = 100 if len(row["phrase"]) == 2 else 50
            minimum_doc = 50 if len(row["phrase"]) == 2 else 20
            reason = None
            if row["chat_message_coverage"] < minimum_chat:
                reason = f"current_chat_coverage_lt_{minimum_chat}"
            elif doc_coverage < minimum_doc:
                reason = f"document_unit_coverage_lt_{minimum_doc}"
            elif row["combined_occurrences"] < 100:
                reason = "combined_occurrences_lt_100"
            elif source == "csv-decomposition-pass6":
                reason = csv_decomposition_semantic_reason(row)
            if reason:
                row = dict(row)
                row["final_rejection_reason"] = reason
                record_rejection(row)
                reasons[reason] += 1
            else:
                sub.append(row)
        elif source == "raw-short-core-pass4":
            minimum_chat = 400 if len(row["phrase"]) == 2 else 250
            minimum_doc = 50 if len(row["phrase"]) == 2 else 30
            minimum_occurrences = 500 if len(row["phrase"]) == 2 else 300
            reason = None
            if row["chat_message_coverage"] < minimum_chat:
                reason = f"current_chat_coverage_lt_{minimum_chat}"
            elif doc_coverage < minimum_doc:
                reason = f"document_unit_coverage_lt_{minimum_doc}"
            elif row["combined_occurrences"] < minimum_occurrences:
                reason = f"combined_occurrences_lt_{minimum_occurrences}"
            else:
                reason = raw_short_live_context_reason(row)
            if reason:
                item = dict(row)
                item["final_rejection_reason"] = reason
                record_rejection(item)
                reasons[reason] += 1
            else:
                raw_short.append(row)
        elif source == "document-short-core-pass7":
            reason = document_short_semantic_reason(row)
            if reason:
                item = dict(row)
                item["final_rejection_reason"] = reason
                record_rejection(item)
                reasons[reason] += 1
            else:
                item = dict(row)
                item["semantic_class"] = "document_style_core"
                item["semantic_release_decision"] = "publish_strict"
                item["semantic_release_reason"] = "document_style_boundary"
                item["semantic_release_roots"] = list(item.get("trigger_phrases", []))
                item["semantic_signals"] = {
                    "document_unit_coverage": int(item.get("md_unit_coverage", 0))
                    + int(item.get("tex_unit_coverage", 0)),
                    "document_file_coverage": int(item.get("md_file_coverage", 0))
                    + int(item.get("tex_file_coverage", 0)),
                }
                document_short.append(item)
        elif source in {
            "independent-longphrase-pass2",
            "comparative-root-pass3",
            "single-root-family-pass3",
            "compound-root-pass4",
            "raw-core-family-pass5",
            "root-inversion-family-pass8",
        }:
            reason = None
            semantic_signals = row.get("semantic_signals", {})
            if not isinstance(semantic_signals, dict):
                semantic_signals = {}
            cross_source_roots = semantic_signals.get(
                "cross_source_released_roots", []
            )
            root_inversion_anchored = (
                source == "root-inversion-family-pass8"
                and (
                    bool(semantic_signals.get("primary_root_anchored"))
                    or (
                        isinstance(cross_source_roots, list)
                        and bool(cross_source_roots)
                    )
                )
            )
            inversion_gate = str(row.get("root_inversion_gate_kind", ""))
            if source in {
                "raw-core-family-pass5",
                "single-root-family-pass3",
                "root-inversion-family-pass8",
            } and row["chat_message_coverage"] < 80:
                reason = "current_chat_coverage_lt_80"
            elif (
                source == "root-inversion-family-pass8"
                and inversion_gate == "edge_context_pending"
                and doc_coverage < 1
            ):
                reason = "root_inversion_edge_document_unit_coverage_lt_1"
            elif source in {
                "raw-core-family-pass5",
                "single-root-family-pass3",
                "root-inversion-family-pass8",
            } and doc_coverage < 20 and not root_inversion_anchored:
                reason = "document_unit_coverage_lt_20"
            elif row["combined_coverage"] < 80:
                reason = "combined_coverage_lt_80"
            elif row["combined_occurrences"] < 80:
                reason = "combined_occurrences_lt_80"
            elif source in {
                "raw-core-family-pass5",
                "single-root-family-pass3",
                "root-inversion-family-pass8",
            }:
                reason = (
                    root_inversion_live_context_reason(row)
                    if source == "root-inversion-family-pass8"
                    else raw_short_live_context_reason(row)
                )
            if reason:
                row = dict(row)
                row["final_rejection_reason"] = reason
                record_rejection(row)
                reasons[reason] += 1
            else:
                if source == "compound-root-pass4" or row["phrase"] in REQUIRED_FINAL_PHRASES:
                    priority_long.append(row)
                else:
                    long.append(row)

    sub.sort(
        key=lambda row: (
            row["combined_score"], row.get("parent_phrase_count", 0), len(row["phrase"]), row["phrase"]
        ),
        reverse=True,
    )
    long, dominated = prune_dominated_long(long)
    rejected_count += len(dominated)
    if retain_rejected_rows:
        rejected.extend(dominated)
    reasons["dominated_fragment"] += len(dominated)
    long.sort(
        key=lambda row: (row["combined_score"], len(row["phrase"]), row["phrase"]),
        reverse=True,
    )
    raw_short.sort(
        key=lambda row: (
            row["combined_score"],
            row.get("family_parent_count", 0),
            len(row["phrase"]),
            row["phrase"],
        ),
        reverse=True,
    )
    priority_long.sort(
        key=lambda row: (row["combined_score"], len(row["phrase"]), row["phrase"]),
        reverse=True,
    )

    selected_sub = sub[:target_subphrases]
    selected_long, long_overflow, reserve_stats = select_long_with_family_reserve(
        long, target_longphrases
    )
    for row in sub[target_subphrases:]:
        item = dict(row)
        item["final_rejection_reason"] = "subphrase_target_cap"
        record_rejection(item)
        reasons["subphrase_target_cap"] += 1
    for row in long_overflow:
        item = dict(row)
        item["final_rejection_reason"] = "longphrase_target_cap"
        record_rejection(item)
        reasons["longphrase_target_cap"] += 1

    final_before_deduplication = (
        baseline
        + selected_sub
        + raw_short
        + document_short
        + selected_long
        + priority_long
    )
    final_by_phrase: dict[str, dict[str, Any]] = {}
    duplicate_final_rows = 0
    for row in final_before_deduplication:
        phrase = str(row["phrase"])
        if phrase not in final_by_phrase:
            final_by_phrase[phrase] = row
            continue
        duplicate_final_rows += 1
        item = dict(row)
        item["final_rejection_reason"] = "duplicate_phrase_already_selected"
        record_rejection(item)
        reasons["duplicate_phrase_already_selected"] += 1
        winner = final_by_phrase[phrase]
        winner["source_kinds"] = sorted(
            {
                str(kind)
                for candidate in (winner, row)
                for kind in [
                    candidate.get("source_kind", ""),
                    *candidate.get("source_kinds", []),
                ]
                if kind
            }
        )
    final = list(final_by_phrase.values())
    final.sort(
        key=lambda row: (
            CATEGORY_ORDER.index(row["category"]),
            -row["combined_score"],
            row["phrase"],
        )
    )
    stats = {
        "baseline_entries": len(baseline),
        "new_subphrase_entries": len(selected_sub),
        "new_csv_decomposition_entries": sum(
            row["source_kind"] == "csv-decomposition-pass6" for row in selected_sub
        ),
        "csv_decomposition_final_overlap_entries": sum(
            "csv-decomposition-pass6" in row.get("source_kinds", [])
            for row in final
        ),
        "new_raw_short_core_entries": len(raw_short),
        "new_document_short_core_entries": len(document_short),
        "new_longphrase_entries": len(selected_long) + len(priority_long),
        "new_compound_root_entries": sum(
            row["source_kind"] == "compound-root-pass4" for row in priority_long
        ),
        "new_raw_core_family_entries": sum(
            row["source_kind"] == "raw-core-family-pass5"
            for row in [*selected_long, *priority_long]
        ),
        "new_root_inversion_family_entries": sum(
            row["source_kind"] == "root-inversion-family-pass8"
            for row in [*selected_long, *priority_long]
        ),
        "strict_inventory_entries": len(final),
        "duplicate_final_rows_removed": duplicate_final_rows,
        "rejected_after_exact_rescan": rejected_count,
        **reserve_stats,
        **{f"rejection/{key}": value for key, value in sorted(reasons.items())},
    }
    return final, rejected, stats


def validate_final_inventory(rows: list[dict[str, Any]]) -> None:
    phrases = {str(row["phrase"]) for row in rows}
    phrase_counts = Counter(str(row["phrase"]) for row in rows)
    duplicate_phrases = sorted(
        phrase for phrase, count in phrase_counts.items() if count > 1
    )
    missing = sorted(REQUIRED_FINAL_PHRASES - phrases)
    forbidden = sorted(
        (FORBIDDEN_FINAL_FRAGMENTS | SUBPHRASE_FRAGMENT_EXACT) & phrases
    )
    bad_shape = sorted(
        phrase
        for phrase in phrases
        if not 2 <= len(phrase) <= 12 or not HAN_EXACT_RE.fullmatch(phrase)
    )
    zero_coverage = sorted(
        str(row["phrase"])
        for row in rows
        if int(row.get("combined_coverage", 0)) <= 0
    )
    semantic_gate_violations = sorted(
        str(row["phrase"])
        for row in rows
        if row.get("source_kind") in SEMANTIC_GATED_SOURCE_KINDS
        and row.get("semantic_release_decision") != "publish_strict"
    )
    document_gate_violations = sorted(
        str(row["phrase"])
        for row in rows
        if row.get("source_kind") == "document-short-core-pass7"
        and row.get("semantic_release_decision") != "publish_strict"
    )
    if (
        duplicate_phrases
        or missing
        or forbidden
        or bad_shape
        or zero_coverage
        or semantic_gate_violations
        or document_gate_violations
    ):
        raise RuntimeError(
            "final inventory quality gate failed: "
            + json.dumps(
                {
                    "duplicate_phrases": duplicate_phrases[:24],
                    "missing_required": missing,
                    "forbidden_fragments": forbidden,
                    "bad_shape": bad_shape[:24],
                    "zero_coverage": zero_coverage[:24],
                    "semantic_gate_violations": semantic_gate_violations[:24],
                    "document_gate_violations": document_gate_violations[:24],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def serializable_entry(row: dict[str, Any]) -> dict[str, Any]:
    order = (
        "phrase", "category", "source_kind", "source_kinds", "score", "discovery_score",
        "evidence_scope",
        "semantic_class", "semantic_release_decision", "semantic_release_reason",
        "semantic_release_roots", "semantic_signals",
        "parent_phrase_count", "parent_category_count", "parent_categories",
        "parent_source_kinds",
        "family_parent_count", "styled_parent_count", "length_bucket",
        "root_inversion_primary_root", "root_inversion_parent_count",
        "root_inversion_shell_parent_count", "root_inversion_confirmed_parent_count",
        "root_inversion_shell_type_count", "root_inversion_discovery_score",
        "root_inversion_shell_weighted_parent_coverage",
        "root_inversion_gate_kind", "root_inversion_prefix", "root_inversion_suffix",
        "root_inversion_prefix_parts", "root_inversion_suffix_parts",
        "root_inversion_examples",
        "discourse_prefix_parent_count", "discourse_suffix_parent_count",
        "discourse_attachment_parent_count", "discourse_attachment_parent_ratio",
        "example_parent_phrases", "left_contexts", "right_contexts", "trigger_phrases",
        "aggregate_left_context_count", "aggregate_right_context_count",
        "aggregate_left_context_dominance", "aggregate_right_context_dominance",
        "aggregate_left_context_entropy", "aggregate_right_context_entropy",
        "max_parent_message_coverage",
        "chat_occurrences", "chat_message_coverage", "chat_message_coverage_rate",
        "chat_context_left_context_count", "chat_context_right_context_count",
        "chat_context_left_boundary_rate", "chat_context_right_boundary_rate",
        "chat_context_left_nonboundary_dominance",
        "chat_context_right_nonboundary_dominance",
        "chat_context_left_contexts", "chat_context_right_contexts",
        "md_occurrences", "md_unit_coverage", "md_file_coverage", "tex_occurrences",
        "tex_unit_coverage", "tex_file_coverage", "combined_occurrences",
        "document_ngram_occurrences", "document_ngram_unit_coverage",
        "document_ngram_file_coverage", "document_seed_reason",
        "document_seed_selected", "document_seed_context_left_context_count",
        "document_seed_context_right_context_count",
        "document_seed_context_left_boundary_rate",
        "document_seed_context_right_boundary_rate",
        "document_context_left_context_count", "document_context_right_context_count",
        "document_context_left_boundary_rate", "document_context_right_boundary_rate",
        "document_context_left_nonboundary_dominance",
        "document_context_right_nonboundary_dominance",
        "document_context_left_contexts", "document_context_right_contexts",
        "combined_coverage", "combined_score",
    )
    return {key: row[key] for key in order if key in row}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    preferred = [
        "phrase", "category", "source_kind", "combined_occurrences", "combined_coverage",
        "evidence_scope",
        "semantic_class", "semantic_release_decision", "semantic_release_reason",
        "semantic_release_roots", "semantic_signals",
        "chat_occurrences", "chat_message_coverage", "md_occurrences", "md_unit_coverage",
        "md_file_coverage", "tex_occurrences", "tex_unit_coverage", "tex_file_coverage",
        "document_ngram_occurrences", "document_ngram_unit_coverage",
        "document_ngram_file_coverage", "document_seed_reason", "document_seed_selected",
        "parent_phrase_count", "styled_parent_count", "parent_category_count", "trigger_phrases",
        "parent_source_kinds",
        "discourse_prefix_parent_count", "discourse_suffix_parent_count",
        "discourse_attachment_parent_count", "discourse_attachment_parent_ratio",
        "example_parent_phrases", "final_rejection_reason", "preselection_reason",
        "combined_score", "discovery_score",
    ]
    fields = preferred + sorted({key for row in rows for key in row} - set(preferred))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            for key, value in rendered.items():
                if isinstance(value, (list, dict)):
                    rendered[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
            writer.writerow(rendered)


def write_report(
    path: Path,
    summary: dict[str, Any],
    final: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> None:
    sub = [row for row in final if row["source_kind"] in SUBPHRASE_SOURCE_KINDS]
    raw_short = [row for row in final if row["source_kind"] == "raw-short-core-pass4"]
    document_short = [
        row
        for row in final
        if row["source_kind"] == "document-short-core-pass7"
    ]
    long = [
        row
        for row in final
        if row["source_kind"] in {
            "independent-longphrase-pass2",
            "comparative-root-pass3",
            "single-root-family-pass3",
            "compound-root-pass4",
            "raw-core-family-pass5",
            "root-inversion-family-pass8",
        }
    ]
    category_counts = Counter(row["category"] for row in final)
    evidence_scope_counts = Counter(row["evidence_scope"] for row in final)
    lines = [
        "# 中文 AI 腔严格词表词根扩充报告",
        "",
        f"生成时间：`{summary['generated_at']}`。本轮脚本版本：`{SCRIPT_VERSION}`。",
        "",
        "## 结论",
        "",
        f"严格词表由 {summary['selection']['baseline_entries']} 条扩充到 "
        f"{summary['selection']['strict_inventory_entries']} 条；新增隐藏小词/小词组 "
        f"{summary['selection']['new_subphrase_entries']} 条（其中 CSV 大词组二次拆解 "
        f"{summary['selection'].get('new_csv_decomposition_entries', 0)} 条），新增 raw 高频短核 "
        f"{summary['selection'].get('new_raw_short_core_entries', 0)} 条，新增独立大词组 "
        f"{summary['selection']['new_longphrase_entries']} 条。父词拆解项必须同时取得聊天和 "
        "MD/TeX 覆盖；独立长词按合并覆盖入选，允许聊天侧或文档侧单独高频，并在 "
        "`evidence_scope` 中明示来源。高频发现库与严格发布库相互独立，纯功能词、专业内容词"
        "和定宽残片只保留审计，不会因为频率高而直接发布。",
        f"本轮 CSV 二次拆解扫描 {summary.get('csv_decomposition', {}).get('csv_rows_scanned', 0)} 行父词，"
        f"筛出 {summary.get('csv_decomposition', {}).get('parent_phrases_selected', 0)} 个完整父词，"
        f"生成 {summary.get('csv_decomposition', {}).get('parent_subphrase_candidates', 0)} 个子词候选；"
        "与其他发现路线重合的词仍保留全部来源标签，未通过门禁的只在 CSV 审计附录中保存。",
        f"CSV 拆分中有 {summary.get('csv_decomposition', {}).get('eligible_dropped_by_pool', 0)} 个"
        "合格候选因精确复扫池上限暂未进入复扫；它们仍完整保存在审计 CSV，而不是静默丢弃。",
        f"文档侧独立审计 {summary.get('document_ngram_discovery', {}).get('document_ngram_candidates_eligible', 0)} 个"
        f"二至三字根候选，选取 {summary.get('document_ngram_discovery', {}).get('document_ngram_candidates_selected', 0)} 个"
        f"进入聊天与文档双重精确复扫，最终新增 {len(document_short)} 个文档短核。",
        "",
        "这里的“严格禁用”仍是文风编辑策略，不是作者身份或 AIGC 检测结论。保护区自动豁免；"
        "正文专业术语只能按位置给出不可替代的功能理由。",
        "",
        f"单字发现根共 {summary['root_discovery'].get('ranked_roots', 0)} 个，"
        f"其中 {summary['root_discovery'].get('status_counts', {}).get('eligible_root', 0)} 个通过家族门槛；"
        "单字只用于定位和扩展候选，永远不作为裸字禁用。旧词表中本次快照已无覆盖的条目："
        f"{summary.get('stale_baseline_zero_coverage', 0)} 条，另存于审计 CSV。",
        "",
        "## 当前语料快照",
        "",
        f"- 聊天：{summary['chat_scan'].get('chat_files_included', 0)} 个结构化会话文件，"
        f"{summary['chat_scan'].get('lines', 0)} 行，"
        f"{summary['chat_scan'].get('assistant_output_messages', 0)} 条 assistant output_text。",
        f"- 文档：{summary['document_scan'].get('md_files_read', 0)} 个 MD、"
        f"{summary['document_scan'].get('tex_files_read', 0)} 个 TeX、"
        f"{summary['document_scan'].get('semantic_units', 0)} 个意群；跳过乱码/不可读 "
        f"{summary['document_scan'].get('document_files_skipped_garbled_or_unreadable', 0)} 个。",
        "- 聊天只取 assistant/output_text；用户消息、system/developer、推理、工具调用、"
        "工具输出、代码围栏和路径未进入词频。",
        "",
        "## 类别规模",
        "",
        "| 类别 | 词条数 |",
        "|---|---:|",
    ]
    lines.extend(f"| {category} | {category_counts[category]} |" for category in CATEGORY_ORDER)
    lines.extend(
        [
            "",
            "## 与旧词表无关的高频短核",
            "",
            f"本轮先审计 {summary.get('raw_short_discovery', {}).get('raw_short_audit_candidates', 0)} 个"
            "覆盖至少 80 条 assistant 消息的二至三字候选；它们不需要先藏在旧禁词中。"
            "只有同时通过全量父壳、左右语境分散度、当前聊天覆盖、MD/TeX 意群覆盖和"
            "原文边界复计的候选才进入语义发布门；发布门还会核验风格父壳占比、聊天/文档"
            "分布、TeX 主导性，以及短核与话语前后缀的紧邻位置。专业内容词与功能词仍保留"
            "完整计数，但只进入审计表。",
            "",
            "| 短核 | 类别 | 全量父壳数 | 聊天消息覆盖 | MD/TEX 意群覆盖 | 左/右语境数 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(raw_short, key=lambda item: item["combined_coverage"], reverse=True)[:300]:
        lines.append(
            f"| {row['phrase']} | {row['category']} | {row.get('family_parent_count', 0)} | "
            f"{row['chat_message_coverage']} | {row['md_unit_coverage'] + row['tex_unit_coverage']} | "
            f"{row.get('chat_context_left_context_count', 0)}/"
            f"{row.get('chat_context_right_context_count', 0)} |"
        )
    semantic_release = summary.get("semantic_release", {})
    lines.extend(
        [
            "",
            "## 高频候选的语义发布门",
            "",
            "词频只负责发现，不负责定罪。二至三字短核先按完整词统计，再区分话语/评价习惯、"
            "专业内容、通用功能词和残片；raw 词族与单字词族必须包含一个已经释放的完整短核。"
            "发布时不再把“出现在风格父壳里”当成充分条件，而要证明短核紧邻 `进一步/必须/再`"
            "等话语前缀，或紧邻 `一点/成/了` 等动作后缀。因此，`收紧`、`收束` 可以凭相对"
            "位置进入严格表，而 `脚本`、`日志`、`方程`、`积分`、"
            "`参数`、`进行` 即使更高频也只能留在审计库。",
            "",
            f"- 语义门审计候选："
            f"{sum(value for key, value in semantic_release.items() if key.startswith('decision/'))} 条。",
            f"- 发布为严格短核/词族：{semantic_release.get('decision/publish_strict', 0)} 条。",
            f"- 仅保留审计：{semantic_release.get('decision/audit_only', 0)} 条。",
            f"- 已释放的二至三字风格核：{semantic_release.get('released_raw_short_cores', 0)} 个。",
            "",
            "全部逐项理由见 `semantic_release_decisions.csv`；发布阈值和保护词表见 "
            "`scripts/style_analysis_lexicon.json` 的 `strict_release` 节。",
        ]
    )
    lines.extend(
        [
            "",
            "## 父词中反复隐藏的小词",
            "",
            "下表按合并覆盖率排序。`父词数` 表示该小词实际藏在多少条父词中，"
            "不是模型猜测的同义词数；父词既包括旧严格词表，也包括通过 `--decompose-csv`"
            "传入的上一轮大词组 CSV。",
            "",
            "| 小词 | 类别 | 父词数 | 聊天消息覆盖 | MD/TEX 意群覆盖 | 合并出现次数 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(sub, key=lambda item: item["combined_coverage"], reverse=True)[:160]:
        lines.append(
            f"| {row['phrase']} | {row['category']} | {row['parent_phrase_count']} | "
            f"{row['chat_message_coverage']} | {row['md_unit_coverage'] + row['tex_unit_coverage']} | "
            f"{row['combined_occurrences']} |"
        )
    lines.extend(
        [
            "",
            "## 继续扩充的大词组",
            "",
            "这些词组不是从旧父词机械截取得到，而是重新从聚合聊天 n-gram 中独立发现；"
            "其中比较级词根（如更稳、更好、更准）和单字根只负责发现家族，最终仍按完整二至八字"
            "片段经当前聊天与文档快照复计。",
            "",
            "| 大词组 | 类别 | 触发词根 | 聊天消息覆盖 | MD/TEX 意群覆盖 | 合并出现次数 |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for row in sorted(long, key=lambda item: item["combined_coverage"], reverse=True)[:240]:
        triggers = "、".join(row.get("trigger_phrases", [])[:4])
        lines.append(
            f"| {row['phrase']} | {row['category']} | {triggers} | "
            f"{row['chat_message_coverage']} | {row['md_unit_coverage'] + row['tex_unit_coverage']} | "
            f"{row['combined_occurrences']} |"
        )
    rejection_counts = Counter(row.get("final_rejection_reason", "unspecified") for row in rejected)
    lines.extend(
        [
            "",
            "## 淘汰审计",
            "",
            "候选没有因为出现在父词中就自动入表。断裂前后缀、功能字边界、跨语料覆盖不足和"
            "被更完整长词支配的片段均被淘汰。",
            "",
            "| 原因 | 数量 |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {reason} | {count} |" for reason, count in rejection_counts.most_common())
    lines.extend(
        [
            "",
            "### 精确复计前的片段门",
            "",
            "父词拆解候选在进入聊天/文档精确复计前还会经过词形和上下文门。"
            "其中 `known_subphrase_fragment` 是人工抽查确认的重复定宽碎片，"
            "频率再高也不得冒充完整词语。",
            "",
            "| 预筛原因 | 数量 |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| {reason} | {count} |"
        for reason, count in sorted(
            summary.get("preselection_rejections", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    lines.extend(
        [
            "",
            "## 复现与产物",
            "",
            "- `strict_ai_phrase_inventory_expanded.json`：可直接写入 Skill 的完整词表。",
            "- `strict_ai_phrase_rankings_expanded.csv`：全部最终词条及三路频次。",
            "- `new_hidden_subphrases.csv`：父词拆解所得小词。",
            "- `csv_decomposition_parent_manifest.csv` 与 `csv_decomposition_subphrase_candidates.csv`："
            "上一轮大词组 CSV 的二次拆解父词和候选审计。",
            "- `raw_short_core_candidate_audit.csv`：全部高频二至三字候选及逐项预筛理由。",
            "- `document_ngram_candidate_audit.csv`：从 MD/TeX 意群直接发现的二至三字根候选、边界和入池状态。",
            "- `document_ngram_selected_for_exact_rescan.csv`：文档发现后进入聊天/文档双重复扫的候选。",
            "- `root_inversion_discovery_audit.csv`：从完整父短语反推的 1–3 字发现根、父词分散度、壳类型和逐项淘汰理由。",
            "- `root_inversion_selected_roots.csv/json`：通过词根图门、进入完整家族扫描的发现根；裸根不进入禁用表。",
            "- `root_inversion_family_candidate_audit.csv`：每个倒排词根扩出的完整家族及入池/掉池决定。",
            "- `root_empirical_shells.sqlite3`：全量发现根与经验句壳的精确磁盘聚合；内存审计表只回填风格句壳示例。",
            "- `new_document_short_cores.csv`：通过双语料、技术词和边界门的文档短核。",
            "- `preselection_pool_drops.csv`：因复扫池上限暂未复扫、但不再静默丢失的合格拆分候选。",
            "- `new_raw_short_cores.csv`：经聊天、文档和边界精确复计后入表的短核。",
            "- `new_independent_longphrases.csv`：独立发现的大词组。",
            "- `new_comparative_root_phrases.csv`：比较级词根（更稳/更好/更准等）通过边界门槛的完整片段。",
            "- `new_single_root_phrases.csv`：单字发现根扩出的完整词族片段。",
            "- `new_compound_root_phrases.csv`：由已确认复合词根保留的完整搭配。",
            "- `new_raw_core_family_phrases.csv`：由无旧表依赖的二至三字短核扩出的完整词族。",
            "- `semantic_release_decisions.csv`：所有高召回短核/词族的语义发布决定、证据和拒绝理由。",
            "- `single_character_root_rankings.csv`：单字发现根的父词、家族覆盖与淘汰理由；单字本身不进入禁用表。",
            "- `rejected_after_exact_rescan.csv`：精确复计后的淘汰项及理由。",
            "- `document_snapshot_manifest.csv` 与 `chat_snapshot_manifest.csv`：快照审计。",
            "",
            "原文未写入本报告；报告只保留连续汉字词项和聚合计数。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-inventory", type=Path, required=True)
    parser.add_argument("--aggregate-chat-candidates", type=Path, required=True)
    parser.add_argument("--codex-root", type=Path, required=True)
    parser.add_argument("--document-root", action="append", type=Path, default=[])
    parser.add_argument("--exclude-root", action="append", type=Path, default=[])
    parser.add_argument(
        "--chat-snapshot",
        type=Path,
        help="Reuse a prior byte-frozen chat snapshot instead of rediscovering files.",
    )
    parser.add_argument(
        "--document-snapshot",
        type=Path,
        help="Reuse a prior byte-frozen MD/TeX snapshot instead of rediscovering files.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--decompose-csv",
        action="append",
        type=Path,
        default=[],
        help=(
            "Optional prior all_candidates_after_exact_rescan.csv files. "
            "Their complete 4-12 character phrases are scanned again for hidden 1-6 character children."
        ),
    )
    parser.add_argument(
        "--exact-count-cache",
        type=Path,
        help=(
            "Prior all_candidates_after_exact_rescan.csv bound to the same "
            "aggregate and frozen snapshots. Only uncached or newly "
            "context-sensitive phrases are rescanned."
        ),
    )
    parser.add_argument(
        "--root-selection-audit",
        type=Path,
        help=(
            "Selected 1-3 character root audit used to bound heavy context-graph "
            "allocation; all other roots remain in the lightweight audit."
        ),
    )
    parser.add_argument(
        "--root-closure-only",
        action="store_true",
        help=(
            "Publish only baseline, independently confirmed short cores, "
            "document short cores, and explicit root-family routes. "
            "Unrooted fixed-width long n-grams remain discovery evidence."
        ),
    )
    parser.add_argument("--subphrase-pool", type=int, default=1800)
    parser.add_argument("--longphrase-pool-per-category", type=int, default=900)
    parser.add_argument("--target-subphrases", type=int, default=1000)
    parser.add_argument("--target-longphrases", type=int, default=2000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.exact_count_cache and (
        args.chat_snapshot is None or args.document_snapshot is None
    ):
        raise ValueError(
            "--exact-count-cache requires --chat-snapshot and --document-snapshot"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    baseline_raw = args.baseline_inventory.read_bytes()
    baseline_inventory = json.loads(baseline_raw.decode("utf-8"))
    baseline_semantic_schema = str(
        baseline_inventory.get("policy", {}).get(
            "semantic_release_config_schema", ""
        )
    )
    aggregate_sha256 = sha256_path(args.aggregate_chat_candidates)
    root_graph_allowlist = (
        load_root_graph_allowlist(args.root_selection_audit)
        if args.root_selection_audit
        else None
    )
    root_graph_fragment_blocklist = (
        load_root_graph_fragment_blocklist(args.root_selection_audit)
        if args.root_selection_audit
        else None
    )
    baseline_entries = baseline_inventory["entries"]
    baseline_phrases = {str(entry["phrase"]) for entry in baseline_entries}
    if len(baseline_phrases) != len(baseline_entries):
        raise RuntimeError("baseline inventory contains duplicate phrases")
    print(f"baseline entries: {len(baseline_entries)}", flush=True)

    excluded = [args.output, *args.exclude_root]
    requested_document_roots = [str(path) for path in args.document_root]
    if args.document_snapshot:
        document_snapshot, prior_document_snapshot = load_snapshot_files(
            args.document_snapshot
        )
        document_snapshot_reused_from = str(args.document_snapshot)
        prior_document_roots = list(
            prior_document_snapshot.get(
                "effective_roots", prior_document_snapshot.get("roots", [])
            )
        )
        if requested_document_roots:
            if not prior_document_roots:
                raise ValueError(
                    "document snapshot does not declare the roots it enumerated"
                )
            if canonical_path_set_sha256(requested_document_roots) != (
                canonical_path_set_sha256(prior_document_roots)
            ):
                raise ValueError(
                    "document snapshot roots do not match --document-root"
                )
        effective_document_roots = (
            prior_document_roots or requested_document_roots
        )
        reused_document_chain = [
            *prior_document_snapshot.get("reused_chain", []),
            str(args.document_snapshot),
        ]
    else:
        document_snapshot = discover_document_paths(args.document_root, excluded)
        prior_document_snapshot = {}
        document_snapshot_reused_from = None
        effective_document_roots = requested_document_roots
        reused_document_chain = []
    (args.output / "document_snapshot.json").write_text(
        json.dumps(
            {
                "created_at": utc_now(),
                "roots": effective_document_roots,
                "effective_roots": effective_document_roots,
                "root_set_sha256": canonical_path_set_sha256(
                    effective_document_roots
                ),
                "file_set_sha256": snapshot_file_set_sha256(
                    document_snapshot
                ),
                "reused_from": document_snapshot_reused_from,
                "reused_chain": reused_document_chain,
                "original_created_at": prior_document_snapshot.get("created_at"),
                "files": document_snapshot,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"document snapshot files: {len(document_snapshot)}", flush=True)
    (
        document_short_pool,
        document_ngram_audit,
        document_root_audit,
        document_ngram_stats,
    ) = (
        discover_document_ngram_seeds(document_snapshot, baseline_entries)
    )
    document_root_rows = [
        row for row in document_root_audit if row.get("root_graph_selected")
    ]
    write_csv(args.output / "document_ngram_candidate_audit.csv", document_ngram_audit)
    write_csv(
        args.output / "document_ngram_selected_for_exact_rescan.csv",
        document_short_pool,
    )
    write_csv(args.output / "document_root_discovery_audit.csv", document_root_audit)
    write_csv(args.output / "document_roots_selected_for_graph.csv", document_root_rows)
    print(
        "document ngram seeds: "
        f"{len(document_short_pool)} selected / {len(document_ngram_audit)} eligible",
        flush=True,
    )
    del document_ngram_audit, document_root_audit
    gc.collect()

    decomposition_parents, decomposition_manifest, decomposition_stats = (
        load_csv_decomposition_parents(args.decompose_csv)
    )
    if decomposition_manifest:
        write_csv(
            args.output / "csv_decomposition_parent_manifest.csv",
            decomposition_manifest,
        )
    del decomposition_manifest
    sub_evidence = generate_subphrase_candidates(
        [*baseline_entries, *decomposition_parents]
    )
    decomposition_stats["parent_subphrase_candidates"] = sum(
        "csv-decomposition-pass6" in item.source_kinds
        for item in sub_evidence.values()
    )
    print(
        f"raw parent substrings: {len(sub_evidence)}; "
        f"CSV decomposition parents: {len(decomposition_parents)}",
        flush=True,
    )
    raw_short_pool, raw_short_audit, raw_short_stats = discover_raw_short_cores(
        args.aggregate_chat_candidates, baseline_entries
    )
    raw_short_audit = annotate_raw_short_discovery_audit(raw_short_audit)
    write_csv(args.output / "raw_short_core_candidate_audit.csv", raw_short_audit)
    print(
        "raw short cores: "
        f"{raw_short_stats.get('raw_short_selected_for_exact_rescan', 0)} exact-rescan / "
        f"{raw_short_stats.get('raw_short_audit_candidates', 0)} audited",
        flush=True,
    )
    del raw_short_audit
    gc.collect()
    # Feed corpus-derived short cores and document-derived cores back into the
    # 1-3 character root graph. Previously the graph was built first and could
    # only learn characters from the old inventory or prior CSVs, which made
    # genuinely new roots depend on manual hints.
    root_inversion_pool, root_inversion_audit, root_inversion_stats = (
        discover_root_inversion(
            args.aggregate_chat_candidates,
            baseline_entries,
            [
                *baseline_entries,
                *decomposition_parents,
                *raw_short_pool,
                *document_short_pool,
            ],
            document_root_rows=document_root_rows,
            root_probe_audit_path=(
                args.output / "aggregate_root_probe_discovery_audit.csv"
            ),
            confirmed_root_probe_audit_path=(
                args.output / "confirmed_parent_root_probe_audit.csv"
            ),
            aggregate_root_allowlist=root_graph_allowlist,
            aggregate_root_fragment_blocklist=root_graph_fragment_blocklist,
            empirical_shell_db_path=(
                args.output / "root_empirical_shells.sqlite3"
            ),
        )
    )
    del decomposition_parents, document_root_rows
    write_csv(args.output / "root_inversion_discovery_audit.csv", root_inversion_audit)
    write_csv(args.output / "root_inversion_selected_roots.csv", root_inversion_pool)
    write_csv(args.output / "root_first_discovery_audit.csv", root_inversion_audit)
    write_csv(args.output / "root_first_selected_roots.csv", root_inversion_pool)
    (args.output / "root_inversion_selected_roots.json").write_text(
        json.dumps(root_inversion_pool, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "root inversion: "
        f"{len(root_inversion_pool)} selected / {len(root_inversion_audit)} audited",
        flush=True,
    )
    del root_inversion_audit
    gc.collect()
    root_rows = build_single_root_evidence(
        baseline_entries,
        args.aggregate_chat_candidates,
        seed_rows=[*raw_short_pool, *document_short_pool],
    )
    write_csv(args.output / "single_character_root_rankings.csv", root_rows)
    (args.output / "single_character_root_rankings.json").write_text(
        json.dumps(root_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    root_stats = Counter(row["root_status"] for row in root_rows)
    print(
        f"single-character roots: {root_stats.get('eligible_root', 0)} eligible / "
        f"{len(root_rows)} ranked",
        flush=True,
    )
    (
        aggregate_counts,
        long_pool,
        root_inversion_family_audit,
        aggregate_stats,
    ) = stream_aggregate_candidates(
        args.aggregate_chat_candidates,
        sub_evidence,
        baseline_entries,
        args.longphrase_pool_per_category,
        root_rows=root_rows,
        raw_short_rows=raw_short_pool,
        root_inversion_rows=root_inversion_pool,
    )
    write_csv(
        args.output / "root_inversion_family_candidate_audit.csv",
        root_inversion_family_audit,
    )
    del root_inversion_family_audit
    sub_pool, pre_rejected, pre_dropped = preselect_subphrases(
        sub_evidence, aggregate_counts, args.subphrase_pool
    )
    del sub_evidence, aggregate_counts
    csv_decomposition_rows = [
        row
        for row in [*sub_pool, *pre_rejected, *pre_dropped]
        if row.get("source_kind") == "csv-decomposition-pass6"
    ]
    if csv_decomposition_rows:
        write_csv(
            args.output / "csv_decomposition_subphrase_candidates.csv",
            csv_decomposition_rows,
        )
    decomposition_stats["eligible_before_pool"] = len(sub_pool) + len(pre_dropped)
    decomposition_stats["eligible_dropped_by_pool"] = len(pre_dropped)
    preselection_rejection_counts = dict(
        Counter(row["preselection_reason"] for row in pre_rejected)
    )
    preselection_pool_drop_counts = dict(
        Counter(row["preselection_reason"] for row in pre_dropped)
    )
    write_csv(args.output / "preselection_rejections.csv", pre_rejected)
    write_csv(args.output / "preselection_pool_drops.csv", pre_dropped)
    sub_pool_count = len(sub_pool)
    print(f"pools: sub={len(sub_pool)} long={len(long_pool)}", flush=True)
    del csv_decomposition_rows, pre_rejected, pre_dropped
    gc.collect()

    candidates: dict[str, dict[str, Any]] = {}
    for entry in baseline_entries:
        item = dict(entry)
        item["source_kind"] = "baseline-v1"
        merge_candidate(candidates, item)
    for row in sub_pool:
        if publication_candidate_allowed(
            row, root_closure_only=args.root_closure_only
        ):
            merge_candidate(candidates, row)
    for row in raw_short_pool:
        merge_candidate(candidates, row)
    for row in document_short_pool:
        merge_candidate(candidates, row)
    skipped_unrooted_long = 0
    for row in long_pool:
        if not publication_candidate_allowed(
            row, root_closure_only=args.root_closure_only
        ):
            skipped_unrooted_long += 1
            continue
        merge_candidate(candidates, row)
    phrases = sorted(candidates)
    print(f"exact-rescan candidate phrases: {len(phrases)}", flush=True)
    del sub_pool, root_inversion_pool
    gc.collect()

    if args.chat_snapshot:
        chat_snapshot, prior_chat_snapshot = load_snapshot_files(args.chat_snapshot)
        chat_discovery_stats = dict(prior_chat_snapshot.get("discovery", {}))
        chat_discovery_stats["snapshot_reused"] = 1
        chat_discovery_stats["chat_snapshot_files"] = len(chat_snapshot)
        chat_snapshot_reused_from = str(args.chat_snapshot)
    else:
        chat_snapshot, chat_discovery_stats = discover_chat_snapshot(args.codex_root)
        prior_chat_snapshot = {}
        chat_snapshot_reused_from = None
    (args.output / "chat_snapshot.json").write_text(
        json.dumps(
            {
                "created_at": utc_now(),
                "root": str(args.codex_root),
                "reused_from": chat_snapshot_reused_from,
                "original_created_at": prior_chat_snapshot.get("created_at"),
                "file_set_sha256": snapshot_file_set_sha256(chat_snapshot),
                "files": chat_snapshot,
                "discovery": chat_discovery_stats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"chat snapshot files: {len(chat_snapshot)}", flush=True)

    context_phrases = {
        str(row["phrase"])
        for row in [*raw_short_pool, *document_short_pool, *long_pool]
        if row.get("source_kind")
        in {
            "raw-short-core-pass4",
            "document-short-core-pass7",
            "compound-root-pass4",
            "raw-core-family-pass5",
            "root-inversion-family-pass8",
        }
    }
    del raw_short_pool, document_short_pool, long_pool
    gc.collect()
    chat_counts: dict[str, dict[str, Any]] = {}
    document_counts: dict[str, dict[str, Any]] = {}
    cached_phrases: set[str] = set()
    exact_cache_stats: dict[str, Any] = {"enabled": False}
    cache_metadata: dict[str, Any] = {}
    if args.exact_count_cache:
        binding = validate_exact_count_cache_binding(
            args.exact_count_cache,
            aggregate_sha256=aggregate_sha256,
            chat_snapshot=args.chat_snapshot,
            document_snapshot=args.document_snapshot,
        )
        (
            chat_counts,
            document_counts,
            cached_phrases,
            cache_counts,
        ) = load_exact_count_cache(
            args.exact_count_cache,
            set(phrases),
            context_phrases,
        )
        cache_metadata = json.loads(
            args.exact_count_cache.with_name("run_metadata.json").read_text(
                encoding="utf-8"
            )
        )
        exact_cache_stats = {
            "enabled": True,
            **binding,
            **cache_counts,
        }
    phrases_to_scan = [phrase for phrase in phrases if phrase not in cached_phrases]
    if phrases_to_scan:
        scan_context_phrases = context_phrases.intersection(phrases_to_scan)
        scanned_document_counts, document_stats = scan_documents(
            document_snapshot,
            phrases_to_scan,
            args.output / "document_snapshot_manifest.csv",
            context_phrases=scan_context_phrases,
        )
        document_counts.update(scanned_document_counts)
        del scanned_document_counts
        gc.collect()
        scanned_chat_counts, chat_stats = scan_chats(
            chat_snapshot,
            phrases_to_scan,
            args.output / "chat_snapshot_manifest.csv",
            context_phrases=scan_context_phrases,
        )
        chat_counts.update(scanned_chat_counts)
        del scanned_chat_counts, scan_context_phrases
        gc.collect()
    else:
        write_csv(args.output / "document_snapshot_manifest.csv", [])
        write_csv(args.output / "chat_snapshot_manifest.csv", [])
        document_stats = dict(cache_metadata.get("document_scan", {}))
        chat_stats = dict(cache_metadata.get("chat_scan", {}))
        document_stats["exact_cache_full_reuse"] = 1
        chat_stats["exact_cache_full_reuse"] = 1
    exact_cache_stats["phrases_scanned"] = len(phrases_to_scan)
    exact_cache_stats["phrases_total"] = len(phrases)
    all_rows = combine_metrics(candidates, chat_counts, document_counts)
    del candidates, chat_counts, document_counts, context_phrases
    del cached_phrases, phrases, phrases_to_scan
    gc.collect()
    all_rows, semantic_release_stats = annotate_semantic_publication(
        all_rows,
        baseline_semantic_schema=baseline_semantic_schema,
    )
    write_csv(args.output / "all_candidates_after_exact_rescan.csv", all_rows)
    write_csv(
        args.output / "semantic_release_decisions.csv",
        [
            row
            for row in all_rows
            if row.get("source_kind") in SEMANTIC_GATED_SOURCE_KINDS
        ],
    )
    stale_baseline = [
        row
        for row in all_rows
        if row["source_kind"] == "baseline-v1" and row["combined_coverage"] <= 0
    ]
    write_csv(args.output / "stale_baseline_zero_coverage.csv", stale_baseline)
    final, rejected, selection_stats = select_final(
        all_rows, args.target_subphrases, args.target_longphrases
    )
    validate_final_inventory(final)
    final_entries = [serializable_entry(row) for row in final]
    category_counts = Counter(row["category"] for row in final)
    evidence_scope_counts = Counter(row["evidence_scope"] for row in final)
    summary = {
        "generated_at": utc_now(),
        "script_version": SCRIPT_VERSION,
        "expander_sha256": sha256_path(Path(__file__)),
        "baseline_inventory": str(args.baseline_inventory),
        "baseline_inventory_sha256": sha256(baseline_raw),
        "aggregate_candidates": str(args.aggregate_chat_candidates),
        "aggregate_candidates_sha256": aggregate_sha256,
        "root_selection_audit": str(args.root_selection_audit)
        if args.root_selection_audit
        else None,
        "root_selection_audit_sha256": sha256_path(args.root_selection_audit)
        if args.root_selection_audit
        else None,
        "root_selection_audit_selected_roots": len(root_graph_allowlist or ()),
        "root_selection_audit_fragment_roots": len(
            root_graph_fragment_blocklist or ()
        ),
        "semantic_release_config": str(STYLE_ANALYSIS_LEXICON_PATH),
        "semantic_release_config_schema": STRICT_RELEASE_CONFIG["schema_version"],
        "semantic_release_config_sha256": STRICT_RELEASE_CONFIG_SHA256,
        "aggregate_discovery": aggregate_stats,
        "csv_decomposition": decomposition_stats,
        "raw_short_discovery": raw_short_stats,
        "document_ngram_discovery": document_ngram_stats,
        "root_inversion_discovery": root_inversion_stats,
        "root_first_discovery": {
            "algorithm": "all_high_coverage_1_3_character_windows_then_family_rescan",
            "bare_roots_publishable": False,
            "family_top_k_gate": False,
            "chat_document_cross_source_is_bonus_not_requirement": True,
            **root_inversion_stats,
        },
        "root_discovery": {
            "ranked_roots": len(root_rows),
            "status_counts": dict(root_stats),
            "eligible_roots": [
                row["root"] for row in root_rows if row["root_status"] == "eligible_root"
            ],
        },
        "semantic_release": semantic_release_stats,
        "stale_baseline_zero_coverage": len(stale_baseline),
        "chat_snapshot_reused_from": chat_snapshot_reused_from,
        "document_snapshot_reused_from": document_snapshot_reused_from,
        "chat_snapshot_discovery": chat_discovery_stats,
        "chat_scan": chat_stats,
        "document_scan": document_stats,
        "exact_count_cache": exact_cache_stats,
        "selection": selection_stats,
        "candidate_publication_policy": {
            "root_closure_only": bool(args.root_closure_only),
            "unrooted_subphrases_skipped": sub_pool_count
            if args.root_closure_only
            else 0,
            "unrooted_independent_longphrases_skipped": skipped_unrooted_long,
        },
        "category_counts": dict(category_counts),
        "evidence_scope_counts": dict(evidence_scope_counts),
        "preselection_rejections": preselection_rejection_counts,
        "preselection_pool_drops": preselection_pool_drop_counts,
    }
    inventory = {
        "schema_version": "humanize-strict-phrase-inventory/v4",
        "generated_at": summary["generated_at"],
        "policy": {
            "meaning": "corpus-derived style editing blocklist, not authorship classification",
            "default_action": "REWRITE_OR_POSITION_BOUND_KEEP",
            "protected_spans_exempt": True,
            "technical_terms_require_position_bound_reason": True,
            "discovery_routes": [
                "parent-subphrase-pass2",
                "csv-decomposition-pass6",
                "independent-longphrase-pass2",
                "comparative-root-pass3",
                "single-root-family-pass3",
                "raw-short-core-pass4",
                "compound-root-pass4",
                "raw-core-family-pass5",
                "document-short-core-pass7",
                "root-inversion-family-pass8",
                "root-first-window-pass9",
            ],
            "semantic_release_config": str(STYLE_ANALYSIS_LEXICON_PATH),
            "semantic_release_config_schema": STRICT_RELEASE_CONFIG["schema_version"],
            "semantic_release_config_sha256": STRICT_RELEASE_CONFIG_SHA256,
        },
        "summary": summary,
        "entries": final_entries,
    }
    inventory_path = args.output / "strict_ai_phrase_inventory_expanded.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(args.output / "strict_ai_phrase_rankings_expanded.csv", final)
    write_csv(
        args.output / "new_hidden_subphrases.csv",
        [row for row in final if row["source_kind"] in SUBPHRASE_SOURCE_KINDS],
    )
    write_csv(
        args.output / "new_raw_short_cores.csv",
        [row for row in final if row["source_kind"] == "raw-short-core-pass4"],
    )
    write_csv(
        args.output / "new_document_short_cores.csv",
        [
            row
            for row in final
            if row["source_kind"] == "document-short-core-pass7"
        ],
    )
    write_csv(
        args.output / "new_independent_longphrases.csv",
        [
            row
            for row in final
            if row["source_kind"]
            in {
                "independent-longphrase-pass2",
                "comparative-root-pass3",
                "compound-root-pass4",
                "raw-core-family-pass5",
                "root-inversion-family-pass8",
            }
        ],
    )
    write_csv(
        args.output / "new_comparative_root_phrases.csv",
        [row for row in final if row["source_kind"] == "comparative-root-pass3"],
    )
    write_csv(
        args.output / "new_single_root_phrases.csv",
        [row for row in final if row["source_kind"] == "single-root-family-pass3"],
    )
    write_csv(
        args.output / "new_compound_root_phrases.csv",
        [row for row in final if row["source_kind"] == "compound-root-pass4"],
    )
    write_csv(
        args.output / "new_raw_core_family_phrases.csv",
        [row for row in final if row["source_kind"] == "raw-core-family-pass5"],
    )
    write_csv(
        args.output / "new_root_inversion_family_phrases.csv",
        [
            row
            for row in final
            if row["source_kind"] == "root-inversion-family-pass8"
        ],
    )
    write_csv(args.output / "rejected_after_exact_rescan.csv", rejected)
    write_report(args.output / "strict_ai_phrase_expansion_report.md", summary, final, rejected)
    (args.output / "run_metadata.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(selection_stats, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
