#!/usr/bin/env python3
"""Build a paragraph-level language corpus from the 59 CUMCM paper OCR files."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


HAN_RE = re.compile(r"[\u4e00-\u9fff]")
KNOWN_UPPER_TOKENS = {
    "AHP", "ARIMA", "BFGS", "BMI", "BP", "CRITIC", "CVAR", "DBSCAN", "DE", "DEGA",
    "FDM", "FEM", "FFT", "FLOYD", "GA", "GPR", "GRU", "ICC", "LIGHTGBM", "LINGO",
    "LMM", "LSTM", "MATLAB", "MLP", "MOPSO", "NSGA", "ODE", "PCA", "PDE", "PID",
    "PSO", "REML", "RFE", "RK", "RK4", "SPSS", "SPSSPRO", "SVM", "TOPSIS", "VAR",
    "VIKOR", "XGBOOST",
}
KNOWN_LATIN_TOKENS = {
    # Software, named methods, and common English terms that legitimately occur
    # inside Chinese modeling prose. Unknown runs are treated as OCR noise.
    "matlab", "python", "excel", "spss", "spsspro", "lingo", "origin", "cad", "simca",
    "pandas", "cftool", "fmincon", "quadprog", "trapz", "rand", "logistic", "logit",
    "probit", "sigmoid", "boosting", "adaboost", "xgboost", "lightgbm", "randomforest",
    "svm", "knn", "kmeans", "k-means", "dbscan", "arima", "lstm", "gru", "pca", "ahp",
    "topsis", "critic", "vikor", "cvar", "bayesian", "pearson", "spearman", "wilcoxon",
    "dirichlet", "aitchison", "drude", "fresnel", "cauchy", "metropolis", "floyd",
    "runge-kutta", "markov", "monte-carlo", "montecarlo", "newton", "fourier", "bayes",
    "mann-whitney", "kruskal", "shapiro", "wilks", "origin", "result", "optimal", "actions",
    "hardvoting", "softvoting", "voting", "boosting", "recal", "precision", "accuracy",
    "adjustedr-square", "adjustedr", "curvefitting", "field", "independent", "controlled",
    "under", "probit", "fresnel", "cauchy", "sigmoid", "constant", "deviation", "fitter",
    "pbest", "gbest", "pche", "tmax", "end", "baseincome", "strategy", "desert", "game",
    "step", "resultxlsx", "z-score", "result1", "result3", "result4", "origin", "min",
}
SUSPICIOUS_OCR_FRAGMENTS = (
    "图9Pras", "图8KAW", "问向题", "坡线由直线", "焉海域", "重登", "被积男数",
    "博奔", "自已", "邻接窍阵", "裁种", "间题", "药束", "养麦", "可普代性",
    "种秆成本", "相关因囊", "考虑祖关性", "完关成分", "片续分析", "铅锁玻璃",
    "玻现", "负饥玻璃", "大学生在药", "主网节点", "理想掀物面", "主过节点",
    "分析步又", "广圭刻", "获得的收益二", "歼村庄", "光村庄", "到达/的概率",
    "缺服说服力", "概率”我们", "幕成正比", "食用茵类",
    "丫染色体", "纳人最终", "土5°", "士要因素", "损火", "覆瘟", "SO家",
    "再此基础", "仅仅使根据", ";:JS", "值得注意的时", "间隅", "主测线回",
    "提过足够", "温速率越大的理论", "T(T。", "M。",
    "士10", "锅炉速度", "控矿", "的的",
    "考综合考虑", "同时合现实情况", "纹饰、“", "式中,为", "再考虑供货商",
    "计算除了新方案", "会应约束条件", "工作箱",
)
SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])")
NUMBERING_RE = re.compile(
    r"^(?:第?[一二三四五六七八九十百]+[、.．]|[（(]?[一二三四五六七八九十\d]+[)）、.．]|"
    r"\d+(?:[.．]\d+){0,4}[、.．]?)"
)
WATERMARK_RE = re.compile(
    r"中国大学生(?:在线)?|国大学生(?:在线)?|大学生在线|学生在线|数学建模竞赛|"
    r"中国大堂生|中国大学牛|中国大学"
)
CAPTION_RE = re.compile(r"^(?:图|表)\s*[A-Za-z一二三四五六七八九十\d]+(?:[-—.．]\d+)*")
FORMULA_RE = re.compile(r"(?:[=≤≥≈≠∑∫√]|\\(?:frac|sum|int|begin)|\b(?:min|max|argmin|argmax)\b)", re.I)
CODE_RE = re.compile(
    r"(?:^|\s)(?:function|def|class|import|from|for|while|if|else|elseif|end|return|printf|disp|"
    r"plot|figure|subplot|clear|clc|include)\b|[{}]{1,}|//|:=|==",
    re.I,
)


ROLE_ALIASES = {
    "摘要": "abstract",
    "摘要与关键词": "abstract",
    "问题重述": "restatement",
    "问题分析": "analysis",
    "建模思路": "analysis",
    "模型假设": "assumption",
    "符号说明": "notation",
    "分问题模型建立": "model",
    "模型构建": "model",
    "模型建立": "model",
    "分问题求解": "solve",
    "求解过程": "solve",
    "模型求解": "solve",
    "结果分析": "result",
    "模型检验": "validation",
    "灵敏度/稳健性": "sensitivity",
    "灵敏度分析": "sensitivity",
    "模型评价": "evaluation",
    "改进方案": "improvement",
    "参考文献": "reference",
    "附录": "appendix",
}

ROLE_ZH = {
    "abstract": "摘要",
    "restatement": "问题重述",
    "analysis": "问题分析",
    "assumption": "模型假设",
    "notation": "符号说明",
    "model": "模型建立",
    "solve": "模型求解",
    "result": "结果分析",
    "validation": "模型检验",
    "sensitivity": "灵敏度/稳健性",
    "evaluation": "模型评价",
    "improvement": "改进方案",
    "other": "其他正文",
}

ROLE_PRIORITY = [
    "abstract", "restatement", "analysis", "assumption", "notation", "model", "solve",
    "result", "validation", "sensitivity", "evaluation", "improvement", "other",
]

HEADING_PATTERNS = [
    ("reference", re.compile(r"^参考文献$")),
    ("appendix", re.compile(r"^附录(?:[A-Z一二三四五六七八九十].*)?$")),
    ("abstract", re.compile(r"^摘要$")),
    ("restatement", re.compile(r"^(?:问题(?:的)?重述|问题背景|背景与问题)$")),
    ("analysis", re.compile(r"^(?:问题分析|建模思路|问题的分析|模型准备|问题剖析).*$")),
    ("assumption", re.compile(r"^(?:模型假设|基本假设|假设条件|模型的假设).*$")),
    ("notation", re.compile(r"^(?:符号说明|符号定义|符号与说明|名词解释).*$")),
    ("sensitivity", re.compile(r".*(?:灵敏度|敏感性|稳健性|鲁棒性).*(?:分析|检验|测试)?$")),
    ("validation", re.compile(r".*(?:模型检验|模型验证|误差分析|有效性检验|结果检验|精度检验).*$")),
    ("improvement", re.compile(r".*(?:模型改进|改进方案|改进方向|进一步改进|模型推广).*$")),
    ("evaluation", re.compile(r".*(?:模型评价|模型评估|优缺点|优点与不足|模型的评价).*$")),
    ("result", re.compile(r".*(?:结果分析|结果与分析|求解结果|结果讨论|结果展示).*$")),
    ("solve", re.compile(r".*(?:模型求解|求解过程|算法求解|求解方法|求解步骤|模型的求解).*$")),
    ("model", re.compile(r".*(?:模型建立|模型构建|建立模型|模型的建立|建模过程).*$")),
]


ACTION_PATTERNS = {
    "problem_translation": re.compile(r"由题意|根据题意|题目要求|需要求出|目标是|已知条件|转化为"),
    "observation": re.compile(r"由图|由表|从图|从表|观察到|可以看出|可看出|可见|数据显示|结果显示"),
    "definition": re.compile(r"(?:^|[，。；])(?:令|设|记|定义)|表示为|记为|其中.+表示"),
    "assumption": re.compile(r"假设|假定|忽略|不考虑|暂不考虑|视为|近似认为|认为.+不变"),
    "derivation": re.compile(r"由.+可得|根据.+可得|代入|联立|整理得|化简得|推导得|解得|可写为|得到方程"),
    "choice": re.compile(r"选择|选取|选用|采用|改用|取.+作为|确定.+方法|相比之下|综合考虑"),
    "constraint": re.compile(r"满足.+约束|约束条件|限制条件|上限|下限|取值范围|可行域|不得|至少|至多"),
    "algorithm": re.compile(r"初始化|迭代|更新|搜索|遍历|二分|步长|收敛|停止|终止|循环|求解器|伪代码"),
    "result": re.compile(r"结果(?:为|如|见|表明)|最终得到|求得|最优(?:值|解|方案)|分别为|计算得到|输出为"),
    "explanation": re.compile(r"其原因|原因在于|这是因为|说明|表明|意味着|导致|归因于|与.+有关"),
    "validation": re.compile(r"检验|验证|误差|残差|回代|拟合|对比|比较|扰动|稳定性|稳健性|灵敏度|交叉验证"),
    "limitation": re.compile(r"不足|局限|缺点|未考虑|尚未|有待|误差来源|适用范围|不能推广"),
    "continuation": re.compile(r"在问题.+基础上|在前问.+基础上|由前文|类似地|同理|进一步|随后|接着"),
    "boundary": re.compile(r"仅|只需|只考虑|在.+范围内|不代表|不能说明|局限于|适用于"),
    "equation_interface": re.compile(r"由式|根据式|代入式|联立式|式中|上式|下式"),
    "figure_table_interface": re.compile(r"由图|由表|如图|如表|见图|见表|图中|表中"),
    "reality_to_math": re.compile(r"(?:实际|现实|物理|工程|业务|生产).{0,18}(?:约束|上限|下限|边界|可行|假设)"),
    "failure_revision": re.compile(r"(?:不满足|无法|偏差|超出|失效|不足).{0,24}(?:因此|故|重新|调整|改用|修正|缩小|放宽)"),
}

PRIMARY_ACTION_ORDER = [
    "failure_revision", "reality_to_math", "observation", "definition", "assumption",
    "choice", "equation_interface", "algorithm", "result", "explanation", "validation",
    "limitation", "continuation", "constraint", "derivation", "problem_translation", "boundary",
]

PHRASE_GROUPS = {
    "题意入口": ["由题意", "根据题意", "题目要求", "针对问题", "对于问题", "本题要求"],
    "观察入口": ["由图可知", "由表可知", "从图中可以看出", "从表中可以看出", "可以看出", "可见"],
    "定义动作": ["不妨设", "令", "设", "记", "定义为", "记为", "表示为"],
    "依据与推导": ["根据上述分析", "由以上分析", "由此可得", "由式可得", "联立可得", "代入可得", "整理得", "化简得"],
    "条件与边界": ["在满足", "当且仅当", "若", "当", "在此条件下", "取值范围", "上限", "下限"],
    "模型选择": ["选择", "选取", "选用", "采用", "相比之下", "故采用", "因此选用", "综合考虑"],
    "前问衔接": ["在问题一的基础上", "在问题二的基础上", "在前问的基础上", "由前文可知", "类似地", "同理", "进一步"],
    "求解动作": ["初始化", "进行迭代", "更新", "遍历", "二分搜索", "逐步缩小", "步长", "停止条件", "终止条件"],
    "公式接口": ["由式", "根据式", "代入式", "联立式", "式中", "将其代入", "可写成", "可化为"],
    "图表接口": ["如图所示", "如表所示", "结果见图", "结果见表", "由图", "由表", "图中", "表中"],
    "结果报告": ["计算得到", "求解得到", "最终得到", "结果为", "分别为", "最优方案", "最优值"],
    "结果解释": ["其原因在于", "这是因为", "说明", "表明", "意味着", "导致", "主要原因是", "可以解释"],
    "检验动作": ["回代", "残差", "误差", "进行对比", "比较可知", "扰动", "灵敏度", "交叉验证", "重复实验"],
    "结论边界": ["仅说明", "不能说明", "在一定范围内", "适用于", "未考虑", "尚未", "仍有", "有待进一步"],
}

OPENING_PATTERNS = [
    ("题意", re.compile(r"^(?:由题意|根据题意|题目要求|本题要求)")),
    ("对象", re.compile(r"^(?:对于|针对|关于|对)(?:问题|第|该|上述|每个|不同)")),
    ("条件", re.compile(r"^(?:若|如果|当|在.+条件下|在.+情况下)")),
    ("依据", re.compile(r"^(?:根据|依据|结合|由)")),
    ("因果", re.compile(r"^(?:由于|考虑到|鉴于|为了)")),
    ("定义", re.compile(r"^(?:不妨设|令|设|记|定义)")),
    ("观察", re.compile(r"^(?:由图|由表|从图|从表|观察)")),
    ("前问", re.compile(r"^(?:在问题.+基础上|在前问.+基础上|由前文|类似地|同理|进一步)")),
    ("动作", re.compile(r"^(?:将|利用|采用|选择|选取|通过|建立|构造|求解)")),
    ("顺序", re.compile(r"^(?:首先|其次|然后|随后|最后|接着)")),
    ("直接陈述", re.compile(r"^(?:本文|本模型|该模型|问题[一二三四五六\d])")),
]

CLOSING_PATTERNS = [
    ("推出", re.compile(r"(?:可得|可知|得证|成立)[。！？]?$")),
    ("结果", re.compile(r"(?:结果|最优解|最优方案|数值)[。！？]?$")),
    ("图表承接", re.compile(r"(?:如下图|如下表|见图\d*|见表\d*)[。！？：:]?$")),
    ("解释", re.compile(r"(?:说明|表明|意味着|原因)[^。！？]{0,20}[。！？]?$")),
    ("条件", re.compile(r"(?:约束|条件|范围|上限|下限|可行)[^。！？]{0,12}[。！？]?$")),
    ("后文接口", re.compile(r"(?:为后文|为下一问|作为.+输入|用于后续)[^。！？]{0,20}[。！？]?$")),
]

MODEL_TERMS = [
    "微分方程", "偏微分方程", "热传导方程", "牛顿冷却", "有限差分", "有限元", "RK4",
    "龙格库塔", "线性规划", "非线性规划", "整数规划", "0-1规划", "动态规划", "多目标优化",
    "遗传算法", "粒子群", "模拟退火", "差分进化", "蚁群算法", "NSGA", "MOPSO", "蒙特卡洛",
    "Dijkstra", "Floyd", "最短路", "最小生成树", "最大流", "网络流", "层次分析", "AHP",
    "熵权", "CRITIC", "TOPSIS", "VIKOR", "灰色关联", "模糊综合评价", "主成分分析", "因子分析",
    "PCA", "K-Means", "DBSCAN", "聚类", "线性回归", "Logistic回归", "支持向量机", "随机森林",
    "XGBoost", "LightGBM", "决策树", "神经网络", "BP神经网络", "LSTM", "GRU", "ARIMA",
    "指数平滑", "灰色预测", "马尔可夫", "交叉验证", "最小二乘", "响应面", "博弈论",
]

SPECIAL_PHRASE_PATTERNS = {
    "令": re.compile(r"(?:^|[，。；：,:;])令(?=[A-Za-z\u4e00-\u9fff])"),
    "设": re.compile(r"(?:^|[，。；：,:;])(?:不妨)?设(?=[A-Za-z\u4e00-\u9fff])"),
    "记": re.compile(r"(?:^|[，。；：,:;])记(?=[A-Za-z\u4e00-\u9fff])"),
    "若": re.compile(r"(?:^|[，。；：,:;])若(?=[A-Za-z\u4e00-\u9fff])"),
    "当": re.compile(r"(?:^|[，。；：,:;])当(?=[A-Za-z\u4e00-\u9fff])"),
}


@dataclass
class Paragraph:
    year: int
    problem_type: str
    paper: str
    page_start: int
    page_end: int
    section: str
    text: str
    confidences: list[float] = field(default_factory=list)
    source_methods: set[str] = field(default_factory=set)
    suspicious_pages: set[int] = field(default_factory=set)
    formula_nearby: bool = False
    visual_nearby: bool = False
    starts_indented: bool = False


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def describe(values: list[float], digits: int = 2) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "q1": round(percentile(values, 0.25), digits),
        "median": round(percentile(values, 0.5), digits),
        "q3": round(percentile(values, 0.75), digits),
        "min": round(min(values), digits),
        "max": round(max(values), digits),
    }


def compact_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\ufeff", "")
    text = re.sub(r"\s+", "", text)
    text = WATERMARK_RE.sub("", text)
    text = text.replace("|", "")
    return text.strip()


def han_count(text: str) -> int:
    return len(HAN_RE.findall(text))


def line_box(line: dict) -> tuple[float | None, float | None, float | None]:
    box = line.get("box") or []
    if len(box) < 4:
        return None, None, None
    xs = [float(point[0]) for point in box]
    ys = [float(point[1]) for point in box]
    return min(xs), min(ys), max(ys) - min(ys)


def strip_numbering(text: str) -> str:
    return NUMBERING_RE.sub("", text, count=1).strip("、.．:：()（）")


def heading_role(text: str) -> str | None:
    candidate = strip_numbering(compact_text(text))
    if not 1 < len(candidate) <= 34:
        return None
    # OCR often breaks an abstract sentence into a short line containing words
    # such as "结果分析" or "灵敏度分析". Sentence punctuation is therefore a
    # hard signal that the line is prose rather than a section heading.
    if re.search(r"[，。；！？,;!?]", candidate):
        return None
    for role, pattern in HEADING_PATTERNS:
        if pattern.fullmatch(candidate):
            return role
    return None


def is_watermark(text: str) -> bool:
    return not text or (len(text) <= 20 and bool(WATERMARK_RE.search(text)))


def is_formula_or_table(text: str) -> bool:
    h = han_count(text)
    if CAPTION_RE.match(text):
        return True
    if h < 4 and FORMULA_RE.search(text):
        return True
    if h < 6 and len(re.findall(r"\d", text)) >= 3:
        return True
    return False


def is_code(text: str) -> bool:
    h = han_count(text)
    ascii_chars = sum(ord(ch) < 128 for ch in text)
    return bool(CODE_RE.search(text)) and (h < 8 or ascii_chars / max(1, len(text)) > 0.55)


def parse_page_expression(location: str) -> set[int]:
    pages: set[int] = set()
    matches = re.findall(r"(?:#page=|p\.)\s*([\d,、\-—–]+)", location, re.I)
    for expression in matches:
        expression = expression.replace("—", "-").replace("–", "-").replace("--", "-").replace("、", ",")
        for part in expression.split(","):
            part = part.strip("- ")
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                if start_text.isdigit() and end_text.isdigit():
                    start, end = int(start_text), int(end_text)
                    pages.update(range(min(start, end), max(start, end) + 1))
            elif part.isdigit():
                pages.add(int(part))
    return pages


def parse_card(path: Path) -> dict[str, set[int]]:
    roles: dict[str, set[int]] = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        role = ROLE_ALIASES.get(cells[0])
        if role:
            roles[role].update(parse_page_expression(cells[1]))
    return dict(roles)


def load_progress(workspace: Path) -> list[dict]:
    path = workspace / ".cumcm-work" / "deep-evidence" / "manual-review-progress.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    papers = [
        {
            "year": int(row["year"]),
            "problem_type": row["problem"],
            "paper": row["paper"],
            "pages": int(row["pages"]),
        }
        for row in rows
        if row["problem"] in {"A", "B", "C"}
    ]
    if len(papers) != 59 or sum(item["pages"] for item in papers) != 2892:
        raise RuntimeError("manual-review-progress.csv is not the 59-paper, 2892-page corpus")
    return papers


def style_override_is_acceptable(original: dict, override: dict) -> bool:
    old_confidence = float(original.get("median_confidence", 0) or 0)
    new_confidence = float(override.get("median_confidence", 0) or 0)
    old_han = int(original.get("chinese_chars", 0) or 0)
    new_han = int(override.get("chinese_chars", 0) or 0)
    confidence_floor = max(0.82, old_confidence - 0.08)
    coverage_floor = max(80, int(old_han * 0.65))
    return new_confidence >= confidence_floor and new_han >= coverage_floor


def load_pages(workspace: Path, paper: dict) -> tuple[list[dict], dict[str, int]]:
    path = workspace / ".cumcm-work" / "pages" / f"{paper['year']}_{paper['paper']}.jsonl"
    with path.open(encoding="utf-8") as stream:
        pages = [json.loads(line) for line in stream if line.strip()]
    if [page.get("page") for page in pages] != list(range(1, paper["pages"] + 1)):
        raise RuntimeError(f"page continuity mismatch: {path.name}")
    override_root = workspace / ".cumcm-work" / "style-ocr220" / f"{paper['year']}_{paper['paper']}"
    override_summary = {"generated": 0, "accepted": 0, "rejected": 0}
    for index, original in enumerate(pages):
        override_path = override_root / f"page-{int(original['page']):03d}.json"
        if not override_path.is_file():
            continue
        override_summary["generated"] += 1
        override = json.loads(override_path.read_text(encoding="utf-8"))
        if style_override_is_acceptable(original, override):
            override["style_override_original_method"] = original.get("method", "unknown")
            pages[index] = override
            override_summary["accepted"] += 1
        else:
            override_summary["rejected"] += 1
    return pages, override_summary


def manual_role_for_page(role_pages: dict[str, set[int]], page: int, current: str) -> str:
    candidates = [role for role in ROLE_PRIORITY if page in role_pages.get(role, set())]
    if current in candidates:
        return current
    for preferred in ("abstract", "restatement", "analysis", "assumption", "notation", "model", "solve", "result", "validation", "sensitivity", "evaluation", "improvement"):
        if preferred in candidates:
            return preferred
    return current if current not in {"reference", "appendix"} else "other"


def infer_section(text: str, current: str, role_pages: dict[str, set[int]], page: int) -> str:
    candidates = {role for role, pages in role_pages.items() if page in pages}
    # These sections are normally delimited by explicit headings.  A page may
    # also be cited in a card as a result or validation evidence page, but that
    # must not relabel abstract prose before the next heading is encountered.
    if current in {"abstract", "restatement", "assumption", "notation"}:
        return current
    if "sensitivity" in candidates and re.search(r"灵敏|敏感|扰动|稳健|鲁棒", text):
        return "sensitivity"
    if "validation" in candidates and ACTION_PATTERNS["validation"].search(text):
        return "validation"
    if "result" in candidates and (ACTION_PATTERNS["result"].search(text) or ACTION_PATTERNS["observation"].search(text)):
        return "result"
    if "solve" in candidates and ACTION_PATTERNS["algorithm"].search(text):
        return "solve"
    if "analysis" in candidates and (ACTION_PATTERNS["choice"].search(text) or ACTION_PATTERNS["problem_translation"].search(text)):
        return "analysis"
    if current in ROLE_ZH:
        return current
    return manual_role_for_page(role_pages, page, "other")


def reconstruct_paper(workspace: Path, skill_root: Path, paper: dict) -> tuple[list[Paragraph], dict]:
    card_path = skill_root / "references" / "paper-cards" / f"{paper['year']}_{paper['paper']}.md"
    if not card_path.is_file():
        raise RuntimeError(f"missing paper card: {card_path.name}")
    role_pages = parse_card(card_path)
    pages, override_summary = load_pages(workspace, paper)
    stop_candidates = [min(role_pages[role]) for role in ("reference", "appendix") if role_pages.get(role)]
    stop_page = min(stop_candidates) if stop_candidates else paper["pages"] + 1
    current = "abstract" if paper["pages"] else "other"
    paragraphs: list[Paragraph] = []
    buffer: list[str] = []
    buffer_conf: list[float] = []
    buffer_methods: set[str] = set()
    buffer_suspicious: set[int] = set()
    buffer_start_page = 1
    buffer_end_page = 1
    buffer_section = current
    buffer_formula = False
    buffer_visual = False
    buffer_indented = False
    pending_formula = False
    pending_visual = False
    excluded = Counter()

    def flush() -> None:
        nonlocal buffer, buffer_conf, buffer_methods, buffer_suspicious
        nonlocal buffer_formula, buffer_visual, buffer_indented
        if not buffer:
            return
        text = "".join(buffer)
        text = re.split(r"(?:关键词|关键字)\s*[:：]?", text, maxsplit=1)[0]
        h = han_count(text)
        if h < 18:
            excluded["too_short"] += 1
        elif is_code(text):
            excluded["code"] += 1
        else:
            paragraphs.append(
                Paragraph(
                    year=paper["year"], problem_type=paper["problem_type"], paper=paper["paper"],
                    page_start=buffer_start_page, page_end=buffer_end_page,
                    section=infer_section(text, buffer_section, role_pages, buffer_start_page), text=text,
                    confidences=list(buffer_conf), source_methods=set(buffer_methods),
                    suspicious_pages=set(buffer_suspicious), formula_nearby=buffer_formula,
                    visual_nearby=buffer_visual, starts_indented=buffer_indented,
                )
            )
        buffer = []
        buffer_conf = []
        buffer_methods = set()
        buffer_suspicious = set()
        buffer_formula = False
        buffer_visual = False
        buffer_indented = False

    hard_stop = False
    for page in pages:
        page_no = int(page["page"])
        if page_no > stop_page or hard_stop:
            excluded["after_body"] += 1
            continue
        current = manual_role_for_page(role_pages, page_no, current)
        candidates = []
        for raw_line in page.get("lines", []):
            text = compact_text(str(raw_line.get("text", "")))
            left, top, height = line_box(raw_line)
            if text and not is_watermark(text):
                candidates.append((raw_line, text, left, top, height))
        body_geometry = [(left, height) for _, text, left, _, height in candidates if left is not None and height and han_count(text) >= 6 and not is_formula_or_table(text)]
        base_left = percentile([left for left, _ in body_geometry], 0.2) if body_geometry else 0
        median_height = max(1.0, percentile([height for _, height in body_geometry], 0.5)) if body_geometry else 1.0

        for raw_line, text, left, top, height in candidates:
            role = heading_role(text)
            if role in {"reference", "appendix"} and page_no >= stop_page:
                flush()
                hard_stop = True
                excluded[role] += 1
                break
            if role:
                flush()
                current = role
                excluded["heading"] += 1
                continue
            if page_no == stop_page and ("参考文献" in text or strip_numbering(text).startswith("附录")):
                flush()
                hard_stop = True
                excluded["body_boundary"] += 1
                break
            if is_watermark(text):
                excluded["watermark"] += 1
                continue
            if CAPTION_RE.match(text):
                if buffer:
                    buffer_visual = True
                pending_visual = True
                excluded["caption"] += 1
                continue
            if is_formula_or_table(text):
                if buffer:
                    buffer_formula = True
                pending_formula = True
                excluded["formula_table"] += 1
                continue
            if is_code(text):
                flush()
                excluded["code"] += 1
                continue
            if re.match(r"^(?:关键词|关键字)\s*[:：]?", text):
                flush()
                excluded["keyword"] += 1
                continue
            if han_count(text) < 4:
                excluded["low_han_line"] += 1
                continue

            indented = bool(left is not None and left >= base_left + max(9.0, median_height * 0.55))
            enumerated = bool(NUMBERING_RE.match(text))
            strong_start = bool(
                re.match(r"^(?:首先|其次|然后|最后|对于|针对|由题意|根据|由于|为了|考虑到|若|当|令|设|记|不妨)", strip_numbering(text))
            )
            if buffer and (indented or enumerated or (len("".join(buffer)) >= 560 and strong_start)):
                flush()
            if not buffer:
                buffer_start_page = page_no
                buffer_section = current if current in ROLE_ZH else manual_role_for_page(role_pages, page_no, "other")
                buffer_formula = pending_formula
                buffer_visual = pending_visual
                buffer_indented = indented
                pending_formula = False
                pending_visual = False
            buffer.append(text)
            buffer_conf.append(float(raw_line.get("confidence", page.get("median_confidence", 0)) or 0))
            buffer_methods.add(str(page.get("method", "unknown")))
            if page.get("needs_tesseract"):
                buffer_suspicious.add(page_no)
            buffer_end_page = page_no
            if len("".join(buffer)) >= 900 and re.search(r"[。！？]$", text):
                flush()
        flush()

    merged: list[Paragraph] = []
    for paragraph in paragraphs:
        if (
            merged
            and merged[-1].page_end + 1 == paragraph.page_start
            and merged[-1].section == paragraph.section
            and not re.search(r"[。！？]$", merged[-1].text)
            and not paragraph.starts_indented
            and len(merged[-1].text) + len(paragraph.text) <= 1000
        ):
            previous = merged[-1]
            previous.text += paragraph.text
            previous.page_end = paragraph.page_end
            previous.confidences.extend(paragraph.confidences)
            previous.source_methods.update(paragraph.source_methods)
            previous.suspicious_pages.update(paragraph.suspicious_pages)
            previous.formula_nearby = previous.formula_nearby or paragraph.formula_nearby
            previous.visual_nearby = previous.visual_nearby or paragraph.visual_nearby
        else:
            merged.append(paragraph)

    metadata = {
        "role_pages": {role: sorted(values) for role, values in role_pages.items()},
        "stop_page": stop_page,
        "excluded": dict(excluded),
        "style_ocr220": override_summary,
    }
    return merged, metadata


def split_sentences(text: str) -> list[str]:
    return [part for part in SENTENCE_RE.split(text) if han_count(part) >= 5]


def sentence_actions(sentence: str) -> list[str]:
    actions = [name for name, pattern in ACTION_PATTERNS.items() if pattern.search(sentence)]
    if re.search(r"\d", sentence) and re.search(r"(?:得到|求得|结果|最优|分别为|为[:：]?)", sentence):
        if "result" not in actions:
            actions.append("result")
    return actions or ["statement"]


def primary_action(actions: list[str]) -> str:
    for action in PRIMARY_ACTION_ORDER:
        if action in actions:
            return action
    return "statement"


def action_sequence(sentences: list[str]) -> tuple[list[str], list[str]]:
    all_actions: list[str] = []
    sequence: list[str] = []
    for sentence in sentences:
        actions = sentence_actions(sentence)
        all_actions.extend(actions)
        primary = primary_action(actions)
        if not sequence or sequence[-1] != primary:
            sequence.append(primary)
    return sorted(set(all_actions)), sequence


def opening_family(text: str) -> str:
    start = strip_numbering(text)
    for name, pattern in OPENING_PATTERNS:
        if pattern.search(start):
            return name
    return "其他"


def closing_family(text: str) -> str:
    for name, pattern in CLOSING_PATTERNS:
        if pattern.search(text):
            return name
    return "其他"


def quality_label(paragraph: Paragraph) -> tuple[str, float]:
    confidence = statistics.median(paragraph.confidences) if paragraph.confidences else 0.0
    suspicious = bool(paragraph.suspicious_pages)
    text = paragraph.text
    h = han_count(text)
    ascii_count = sum(ord(character) < 128 for character in text)
    long_ascii = re.findall(r"[A-Za-z0-9@#$%^&*_+=<>]{14,}", text)
    has_prose_punctuation = bool(re.search(r"[，。；：！？,.!?;:]", text))
    keyword_line = bool(re.search(r"(?:关键词|关键字)\s*[:：]?", text))
    lexical_damage = text.count("?") >= 2 or text.count("〈") + text.count("〉") >= 3
    incomplete = not bool(re.search(r"[。！？；：.!?;:]$", text))
    if (
        keyword_line
        or (not has_prose_punctuation and h < 36)
        or (long_ascii and h < 55)
        or (len(long_ascii) >= 2 and h < 120)
        or ascii_count / max(1, len(text)) > 0.62
        or lexical_damage
    ):
        return "low", round(confidence, 4)
    lexical_warning = bool(long_ascii) or incomplete
    if confidence >= 0.88 and not suspicious:
        return ("medium" if lexical_warning else "high"), round(confidence, 4)
    if confidence >= 0.78:
        return "medium", round(confidence, 4)
    return "low", round(confidence, 4)


def model_mentions(text: str) -> list[str]:
    lowered = text.lower()
    occupied: list[tuple[int, int]] = []
    found = []
    for term in sorted(MODEL_TERMS, key=len, reverse=True):
        start = lowered.find(term.lower())
        if start < 0:
            continue
        span = (start, start + len(term))
        if any(not (span[1] <= old[0] or span[0] >= old[1]) for old in occupied):
            continue
        found.append(term)
        occupied.append(span)
    return sorted(found, key=lambda term: lowered.find(term.lower()))


def phrase_occurrences(text: str, phrase: str) -> int:
    pattern = SPECIAL_PHRASE_PATTERNS.get(phrase)
    return len(pattern.findall(text)) if pattern else text.count(phrase)


def safe_excerpt(text: str, limit: int) -> str:
    """Cut at a sentence boundary so examples do not look like OCR fragments."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    boundaries = [match.end() for match in re.finditer(r"[。！？；]", head)]
    if boundaries and boundaries[-1] >= int(limit * 0.55):
        return head[:boundaries[-1]] + "……"
    return head.rstrip("，、；： ") + "……"


def clean_prose_record(record: dict, *, min_han: int = 40) -> bool:
    text = record["text"]
    ascii_count = sum(ord(character) < 128 for character in text)
    long_ascii = re.findall(r"[A-Za-z0-9@#$%^&*_+=<>]{12,}", text)
    unknown_upper = [
        token for token in re.findall(r"[A-Z]{4,}[A-Za-z0-9]*", text)
        if token.upper() not in KNOWN_UPPER_TOKENS
    ]
    unknown_latin = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text):
        lowered = token.lower()
        if lowered in KNOWN_LATIN_TOKENS or token.upper() in KNOWN_UPPER_TOKENS:
            continue
        # Short identifiers and chemical formulas are usually variables, not
        # prose; retain them when they are visibly compact and structured.
        if re.fullmatch(r"[A-Z]{2,}\d*", token) or re.fullmatch(r"[A-Z][a-z]?\d+(?:[A-Z][a-z]?\d+)*", token):
            continue
        unknown_latin.append(token)
    return bool(
        record["quality"] == "high"
        and record["han_chars"] >= min_han
        and re.search(r"[，。；：！？]", text)
        and not re.search(r"(?:关键词|关键字)\s*[:：]?", text)
        and len(long_ascii) <= 1
        and not unknown_upper
        and not unknown_latin
        and ascii_count / max(1, len(text)) < 0.35
        and "?" not in text
        and not re.search(r"[。！？；]{2,}", text)
        and not re.search(r",,{1,}|，，", text)
        and not any(fragment in text for fragment in SUSPICIOUS_OCR_FRAGMENTS)
        and "Step" not in text
        and bool(re.search(r"[。！？；：.!?;:]$", text))
    )


def introduction_pathway(record: dict, previous: dict | None) -> str:
    """Describe the public textual route by which a model enters the paper."""
    lead_actions = set(previous["actions"] if previous else [])
    current_actions = set(record["actions"])
    combined = (previous["text"] if previous else "") + record["text"]
    if re.search(r"在(?:问题[一二三四五六\d]+|前问).{0,12}基础上|由前(?:文|问)|沿用前问|同理", combined):
        return "前问结果承接"
    if "failure_revision" in lead_actions | current_actions:
        return "试算或失败结果触发修正"
    if "observation" in lead_actions | current_actions:
        return "数据或图表观察引入"
    if re.search(r"(?:解析解|计算量|运算量|维数|变量较多|解空间|组合爆炸|难以直接|无法直接).{0,28}(?:求解|计算|遍历|获得|处理)", combined):
        return "解析或计算困难促成替代"
    if "reality_to_math" in lead_actions | current_actions:
        return "现实后果转化为数学边界"
    if "constraint" in lead_actions | current_actions:
        return "约束结构导出模型"
    if "choice" in current_actions:
        return "显式依据后选用"
    if "derivation" in lead_actions | current_actions or "equation_interface" in current_actions:
        return "关系推导后自然落式"
    if "problem_translation" in lead_actions | current_actions:
        return "由题意对象直接建模"
    return "局部陈述中直接出现"


def fragment_candidates(text: str, from_end: bool = False) -> list[str]:
    cleaned = strip_numbering(text)
    cleaned = re.sub(r"[，。；：！？,.!?:;].*", "", cleaned) if not from_end else cleaned
    if from_end:
        pieces = [piece for piece in re.split(r"[。！？；]", cleaned) if piece]
        cleaned = pieces[-1] if pieces else cleaned
    han_only = "".join(HAN_RE.findall(cleaned))
    values = []
    for length in (4, 6, 8):
        if len(han_only) >= length:
            values.append(han_only[-length:] if from_end else han_only[:length])
    return values


def build_records(paragraphs: list[Paragraph]) -> list[dict]:
    records = []
    for index, paragraph in enumerate(paragraphs, 1):
        sentences = split_sentences(paragraph.text)
        actions, sequence = action_sequence(sentences)
        quality, confidence = quality_label(paragraph)
        record = {
                "id": f"{paragraph.year}_{paragraph.paper}_P{index:04d}",
                "year": paragraph.year,
                "problem_type": paragraph.problem_type,
                "paper": paragraph.paper,
                "page_start": paragraph.page_start,
                "page_end": paragraph.page_end,
                "section": paragraph.section,
                "quality": quality,
                "median_confidence": confidence,
                "han_chars": han_count(paragraph.text),
                "sentence_count": len(sentences),
                "actions": actions,
                "action_sequence": sequence,
                "opening_family": opening_family(paragraph.text),
                "closing_family": closing_family(paragraph.text),
                "formula_nearby": paragraph.formula_nearby,
                "visual_nearby": paragraph.visual_nearby,
                "models": model_mentions(paragraph.text),
                "source_methods": sorted(paragraph.source_methods),
                "source": f"{paragraph.year}/{paragraph.paper}.pdf#page={paragraph.page_start}",
                "text": paragraph.text[:1000],
            }
        record["retrieval_eligible"] = clean_prose_record(record, min_han=30)
        records.append(record)
    return records


def aggregate(records: list[dict], metadata: dict[str, dict]) -> dict:
    usable = [record for record in records if record["quality"] != "low"]
    paper_han_totals = Counter()
    for record in usable:
        paper_han_totals[record["paper"]] += record["han_chars"]

    def section_metrics(selected: list[dict]) -> dict:
        by_paper_rows = defaultdict(list)
        for record in selected:
            by_paper_rows[record["paper"]].append(record)
        shares = []
        page_footprints = []
        for paper, paper_rows in by_paper_rows.items():
            shares.append(sum(row["han_chars"] for row in paper_rows) / max(1, paper_han_totals[paper]))
            pages = {
                page
                for row in paper_rows
                for page in range(row["page_start"], row["page_end"] + 1)
            }
            page_footprints.append(len(pages))
        actions = Counter(action for record in selected for action in record["actions"])
        sequences = Counter(
            " -> ".join(record["action_sequence"])
            for record in selected if record["action_sequence"]
        )
        return {
            "paragraphs": len(selected),
            "papers": len(by_paper_rows),
            "han_chars": sum(record["han_chars"] for record in selected),
            "paragraph_han": describe([record["han_chars"] for record in selected]),
            "sentence_han": describe([
                han_count(sentence)
                for record in selected
                for sentence in split_sentences(record["text"])
            ]),
            "share_of_paper_han": describe(shares, 4),
            "page_footprint": describe(page_footprints),
            "top_actions": dict(actions.most_common(12)),
            "top_sequences": [
                {"sequence": sequence, "paragraphs": count}
                for sequence, count in sequences.most_common(10)
            ],
            "formula_nearby_rate": round(sum(record["formula_nearby"] for record in selected) / max(1, len(selected)), 4),
            "visual_nearby_rate": round(sum(record["visual_nearby"] for record in selected) / max(1, len(selected)), 4),
        }
    by_type = {}
    for kind in ("ALL", "A", "B", "C"):
        selected = [record for record in usable if kind == "ALL" or record["problem_type"] == kind]
        by_type[kind] = {
            "paragraphs": len(selected),
            "papers": len({record["paper"] for record in selected}),
            "han_chars": sum(record["han_chars"] for record in selected),
            "sentence_count": sum(record["sentence_count"] for record in selected),
            "paragraph_han": describe([record["han_chars"] for record in selected]),
            "sentence_han": describe([
                han_count(sentence)
                for record in selected
                for sentence in split_sentences(record["text"])
            ]),
        }

    by_section = {}
    for section in ROLE_ZH:
        selected = [record for record in usable if record["section"] == section]
        if not selected:
            continue
        by_section[section] = section_metrics(selected)

    section_by_problem_type = {}
    for kind in ("A", "B", "C"):
        section_by_problem_type[kind] = {}
        for section in ROLE_ZH:
            selected = [
                record for record in usable
                if record["problem_type"] == kind and record["section"] == section
            ]
            if selected:
                section_by_problem_type[kind][section] = section_metrics(selected)

    phrase_stats = {}
    for group, phrases in PHRASE_GROUPS.items():
        group_rows = []
        for phrase in phrases:
            matching = [record for record in usable if phrase_occurrences(record["text"], phrase)]
            occurrences = sum(phrase_occurrences(record["text"], phrase) for record in matching)
            group_rows.append(
                {
                    "phrase": phrase,
                    "occurrences": occurrences,
                    "papers": len({record["paper"] for record in matching}),
                    "sections": dict(Counter(record["section"] for record in matching).most_common()),
                    "problem_types": dict(Counter(record["problem_type"] for record in matching).most_common()),
                }
            )
        phrase_stats[group] = sorted(group_rows, key=lambda row: (-row["papers"], -row["occurrences"], row["phrase"]))

    opening_stats = {}
    closing_stats = {}
    sequence_stats = {}
    for key, selected in [("ALL", usable)] + [
        (f"type:{kind}", [record for record in usable if record["problem_type"] == kind])
        for kind in ("A", "B", "C")
    ] + [
        (f"section:{section}", [record for record in usable if record["section"] == section])
        for section in ROLE_ZH
    ]:
        if not selected:
            continue
        opening_stats[key] = dict(Counter(record["opening_family"] for record in selected).most_common())
        closing_stats[key] = dict(Counter(record["closing_family"] for record in selected).most_common())
        sequences = Counter(" -> ".join(record["action_sequence"]) for record in selected if record["action_sequence"])
        support = defaultdict(set)
        for record in selected:
            if record["action_sequence"]:
                support[" -> ".join(record["action_sequence"])].add(record["paper"])
        sequence_stats[key] = [
            {"sequence": sequence, "paragraphs": count, "papers": len(support[sequence])}
            for sequence, count in sequences.most_common(20)
        ]

    open_fragments = Counter()
    close_fragments = Counter()
    open_support = defaultdict(set)
    close_support = defaultdict(set)
    for record in usable:
        for fragment in fragment_candidates(record["text"]):
            open_fragments[fragment] += 1
            open_support[fragment].add(record["paper"])
        for fragment in fragment_candidates(record["text"], from_end=True):
            close_fragments[fragment] += 1
            close_support[fragment].add(record["paper"])
    mined_openings = [
        {"fragment": fragment, "occurrences": count, "papers": len(open_support[fragment])}
        for fragment, count in open_fragments.most_common()
        if count >= 5 and len(open_support[fragment]) >= 3
    ][:100]
    mined_closings = [
        {"fragment": fragment, "occurrences": count, "papers": len(close_support[fragment])}
        for fragment, count in close_fragments.most_common()
        if count >= 5 and len(close_support[fragment]) >= 3
    ][:100]

    introductions = []
    seen_models: dict[str, set[str]] = defaultdict(set)
    previous_by_paper: dict[str, dict] = {}
    for record in records:
        if not clean_prose_record(record):
            continue
        if record["section"] in {"abstract", "restatement", "notation"}:
            continue
        for model in record["models"]:
            if model in seen_models[record["paper"]]:
                continue
            previous = previous_by_paper.get(record["paper"])
            introductions.append(
                {
                    "paper": record["paper"], "year": record["year"], "problem_type": record["problem_type"],
                    "model": model, "section": record["section"], "page": record["page_start"],
                    "pathway": introduction_pathway(record, previous),
                    "lead_in_actions": previous["actions"] if previous else [],
                    "lead_in": safe_excerpt(previous["text"], 300) if previous else "",
                    "introduction": safe_excerpt(record["text"], 460),
                    "source": record["source"],
                }
            )
            seen_models[record["paper"]].add(model)
        previous_by_paper[record["paper"]] = record

    pathway_stats = {}
    for kind in ("ALL", "A", "B", "C"):
        selected = [item for item in introductions if kind == "ALL" or item["problem_type"] == kind]
        pathway_stats[kind] = {
            "introductions": len(selected),
            "papers": len({item["paper"] for item in selected}),
            "counts": dict(Counter(item["pathway"] for item in selected).most_common()),
        }

    return {
        "scope": {
            "papers": len({record["paper"] for record in records}),
            "paragraphs_reconstructed": len(records),
            "paragraphs_used_for_patterns": len(usable),
            "pages": 2892,
            "quality": dict(Counter(record["quality"] for record in records)),
            "excluded_line_groups": dict(sum((Counter(item["excluded"]) for item in metadata.values()), Counter())),
            "style_ocr220": {
                key: sum(item.get("style_ocr220", {}).get(key, 0) for item in metadata.values())
                for key in ("generated", "accepted", "rejected")
            },
        },
        "by_problem_type": by_type,
        "by_section": by_section,
        "section_by_problem_type": section_by_problem_type,
        "phrase_functions": phrase_stats,
        "opening_families": opening_stats,
        "closing_families": closing_stats,
        "action_sequences": sequence_stats,
        "mined_opening_fragments": mined_openings,
        "mined_closing_fragments": mined_closings,
        "model_introductions": introductions,
        "model_introduction_pathways": pathway_stats,
        "paper_boundaries": metadata,
        "limitations": [
            "本索引来自 OCR 正文重建；公式、数值、表格和小字号图注仍以原始栅格为准。",
            "参考文献与附录代码不进入语言频率；与正文同页时以标题行为边界。",
            "low 质量段落保留在索引中供定位，但不进入短语、句长和功能序列统计。",
            "功能标签允许一条句子多标签；动作序列是公开写作功能的描述，不是固定写作模板。",
        ],
    }


def representative_examples(records: list[dict], section: str, limit: int = 3) -> list[dict]:
    selected = [
        record for record in records
        if record["section"] == section and 45 <= record["han_chars"] <= 380
        and clean_prose_record(record, min_han=45)
    ]
    selected.sort(key=lambda record: (-len(record["actions"]), record["year"], record["paper"], record["page_start"]))
    result = []
    used_papers = set()
    used_types = set()
    for record in selected:
        if record["paper"] in used_papers:
            continue
        if len(result) < 3 and record["problem_type"] in used_types:
            continue
        result.append(record)
        used_papers.add(record["paper"])
        used_types.add(record["problem_type"])
        if len(result) >= limit:
            break
    return result


def write_summary(path: Path, stats: dict, records: list[dict]) -> None:
    lines = [
        "# 59 篇论文全文语言分析",
        "",
        "## 1. 这份资料做了什么",
        "",
        "本资料以 59 篇编号获奖论文的 2892 页页级文本为输入，重建正文段落，并在进入统计前剔除页眉水印、参考文献、附录代码、公式表格行和低信息噪声。它分析的是实际正文中的句子与段落，不用论文卡的概括代替原文语言。OCR 质量为 `low` 的段落只保留定位，不参加模式统计。",
        "",
        f"共重建 {stats['scope']['paragraphs_reconstructed']} 个正文段落，其中 {stats['scope']['paragraphs_used_for_patterns']} 个进入语言模式统计；质量分布为 `{stats['scope']['quality']}`。",
        "",
        "这仍不是模型权重训练。它是 Skill 的持久语言记忆：写作时按题型、章节、动作和模型检索真实上下文，再据当前问题重新组织。",
        "",
        "## 2. 题型差异",
        "",
        "| 范围 | 论文 | 段落 | 句子 | 正文字数 | 段落字数中位数 [Q1,Q3] | 句长中位数 [Q1,Q3] |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for kind in ("ALL", "A", "B", "C"):
        row = stats["by_problem_type"][kind]
        ph, sh = row["paragraph_han"], row["sentence_han"]
        lines.append(
            f"| {kind} | {row['papers']} | {row['paragraphs']} | {row['sentence_count']} | {row['han_chars']} | "
            f"{ph.get('median', 0)} [{ph.get('q1', 0)},{ph.get('q3', 0)}] | {sh.get('median', 0)} [{sh.get('q1', 0)},{sh.get('q3', 0)}] |"
        )
    lines += [
        "", "## 3. 章节语言负担", "",
        "| 章节 | 覆盖论文 | 段落 | 正文字数 | 单篇正文字数占比中位数 [Q1,Q3] | 页面足迹中位数 [Q1,Q3] | 段落字数中位数 [Q1,Q3] |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for section in ROLE_PRIORITY:
        row = stats["by_section"].get(section)
        if not row:
            continue
        ph = row["paragraph_han"]
        share = row["share_of_paper_han"]
        pages = row["page_footprint"]
        lines.append(
            f"| {ROLE_ZH.get(section, section)} | {row['papers']} | {row['paragraphs']} | {row['han_chars']} | "
            f"{share.get('median', 0):.1%} [{share.get('q1', 0):.1%},{share.get('q3', 0):.1%}] | "
            f"{pages.get('median', 0)} [{pages.get('q1', 0)},{pages.get('q3', 0)}] | "
            f"{ph.get('median', 0)} [{ph.get('q1', 0)},{ph.get('q3', 0)}] |"
        )
    lines += [
        "",
        "篇幅数据描述作者实际展开到哪里，不规定每段必须同长。模型建立和结果解释需要多少篇幅，取决于公式接口、约束来源、异常与检验对象；不能拿中位数机械扩写。",
        "",
        "### A/B/C 同一章节的写法差异",
        "",
        "| 题型 | 章节 | 覆盖论文 | 单篇字数占比中位数 | 公式邻近率 | 图表邻近率 | 高频公开动作 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for kind in ("A", "B", "C"):
        for section in ROLE_PRIORITY:
            row = stats["section_by_problem_type"][kind].get(section)
            if not row:
                continue
            share = row["share_of_paper_han"]
            actions = "、".join(f"{name} {count}" for name, count in list(row["top_actions"].items())[:5])
            lines.append(
                f"| {kind} | {ROLE_ZH.get(section, section)} | {row['papers']} | {share.get('median', 0):.1%} | "
                f"{row['formula_nearby_rate']:.1%} | {row['visual_nearby_rate']:.1%} | {actions} |"
            )
    lines += [
        "",
        "## 4. 惯用词的功能分布",
        "",
        "下表只列同时出现在多篇论文中的表达。词语本身不是人味；只有后面接上相应的题意关系、定义、证据、推导或边界时才成立。",
        "",
        "| 功能 | 高频表达（出现次数/论文数） |",
        "|---|---|",
    ]
    for group, rows in stats["phrase_functions"].items():
        shown = [row for row in rows if row["papers"] >= 2 and row["occurrences"] > 0][:10]
        text = "；".join(f"{row['phrase']} {row['occurrences']}/{row['papers']}" for row in shown) or "未形成跨篇稳定表达"
        lines.append(f"| {group} | {text} |")
    lines += [
        "",
        "## 5. 段落起笔与收束",
        "",
        "起笔不是统一使用“针对……本文……”。不同章节允许直接从对象、条件、定义、图表或前问接口开始。下面给出实际分布，写作时应先看当前段落承担什么动作，再选入口。",
        "",
    ]
    for key in ("ALL", "type:A", "type:B", "type:C"):
        opening = stats["opening_families"].get(key, {})
        closing = stats["closing_families"].get(key, {})
        lines.append(f"- `{key}` 起笔：" + "，".join(f"{name} {count}" for name, count in list(opening.items())[:8]))
        lines.append(f"- `{key}` 收束：" + "，".join(f"{name} {count}" for name, count in list(closing.items())[:8]))
    lines += [
        "",
        "自动挖掘的跨篇开头片段见 `fulltext-style-stats.json` 的 `mined_opening_fragments`；不能把其中任何一个片段轮换粘贴成模板。",
        "",
        "## 6. 公开判断过程如何进入正文",
        "",
        "`action_sequences` 记录每个自然段实际出现的功能顺序。它用来观察差异，不用于强制生成同一链条。常见情况包括直接定义后进公式、图表读数后解释原因、约束不满足后局部修正、前问输出进入新目标，以及求解动作后立即给停止条件。",
        "",
        "模型第一次出现的前一段和当前段保存在 `fulltext-style-stats.json` 的 `model_introductions`。获奖论文并不存在统一的‘先比较三个模型再选择’写法；公开判断往往散在公式前后、试算结果后或下一问开头。写作时应检索与当前问题相同的触发情形，只展开实际发生的判断。",
        "",
        "| 范围 | 模型首次出现次数 | 涉及论文 | 公开引入路径 |",
        "|---|---:|---:|---|",
    ]
    for kind in ("ALL", "A", "B", "C"):
        row = stats["model_introduction_pathways"][kind]
        counts = "；".join(f"{name} {count}" for name, count in row["counts"].items())
        lines.append(f"| {kind} | {row['introductions']} | {row['papers']} | {counts} |")
    lines += [
        "",
        "这些路径是对原文可见论证动作的归纳，不是要求每个模型都补齐的固定步骤。例如，前问已经给出状态量时，可以直接改写目标函数；物理关系足以唯一确定方程时，不必虚构候选比较；只有试算确实暴露不可行或误差结构时，才写局部修正。",
        "",
        "## 7. 分章节真实段落样本",
        "",
        "以下短样本用于显示节奏和接口，原文位置随条目给出。写作时迁移动作，不照抄对象、数字或结论。",
        "",
    ]
    for section in ROLE_PRIORITY:
        if section == "other":
            continue
        examples = representative_examples(records, section)
        if not examples:
            continue
        lines.append(f"### {ROLE_ZH[section]}")
        lines.append("")
        for record in examples:
            excerpt = safe_excerpt(record["text"], 260)
            lines.append(
                f"- `{record['problem_type']} / {record['paper']} / p.{record['page_start']}` "
                f"动作 `{' -> '.join(record['action_sequence'])}`：{excerpt}"
            )
        lines.append("")
    lines += [
        "## 8. 使用边界",
        "",
        *[f"- {item}" for item in stats["limitations"]],
        "- 全量逐段记录在 `fulltext-style-index.jsonl`；不要把整库一次性塞进上下文，应使用查询脚本按任务取 3--8 个相近段落。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_profiles(path: Path, records: list[dict], stats: dict) -> None:
    lines = ["# 59 篇单篇语言画像", "", "每篇画像都由正文段落索引计算，低质量 OCR 段落不进入高频模式。", ""]
    by_paper = defaultdict(list)
    for record in records:
        by_paper[record["paper"]].append(record)
    introductions = defaultdict(list)
    for item in stats["model_introductions"]:
        introductions[item["paper"]].append(item)
    for paper in sorted(by_paper, key=lambda value: (next(r["year"] for r in by_paper[value]), value)):
        rows = by_paper[paper]
        usable = [row for row in rows if row["quality"] != "low"]
        first = rows[0]
        actions = Counter(action for row in usable for action in row["actions"])
        phrases = Counter()
        for group in PHRASE_GROUPS.values():
            for phrase in group:
                phrases[phrase] += sum(phrase_occurrences(row["text"], phrase) for row in usable)
        sections = Counter(row["section"] for row in usable)
        sequences = Counter(" -> ".join(row["action_sequence"]) for row in usable if row["action_sequence"])
        lines += [
            f"## {first['year']} {paper} ({first['problem_type']})",
            "",
            f"- 正文段落：{len(rows)}；进入模式统计：{len(usable)}；正文字数：{sum(row['han_chars'] for row in usable)}。",
            "- 章节分布：" + "，".join(f"{ROLE_ZH.get(role, role)} {count}" for role, count in sections.most_common()),
            "- 高频动作：" + "，".join(f"{name} {count}" for name, count in actions.most_common(8)),
            "- 高频功能词：" + "，".join(f"{name} {count}" for name, count in phrases.most_common(10) if count),
            "- 常见段内推进：" + "；".join(f"{seq} ({count})" for seq, count in sequences.most_common(5)),
        ]
        model_rows = introductions.get(paper, [])[:8]
        if model_rows:
            lines.append("- 模型首次出现：" + "；".join(f"{item['model']}@p.{item['page']}" for item in model_rows))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    skill_root = args.skill_root.resolve()
    papers = load_progress(workspace)
    all_paragraphs: list[Paragraph] = []
    metadata: dict[str, dict] = {}
    for paper in papers:
        paragraphs, paper_metadata = reconstruct_paper(workspace, skill_root, paper)
        all_paragraphs.extend(paragraphs)
        metadata[f"{paper['year']}_{paper['paper']}"] = paper_metadata
    records = build_records(all_paragraphs)
    stats = aggregate(records, metadata)

    references = skill_root / "references"
    index_path = references / "fulltext-style-index.jsonl"
    with index_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    stats_path = references / "fulltext-style-stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    write_summary(references / "fulltext-language-analysis.md", stats, records)
    write_profiles(references / "paper-language-profiles.md", records, stats)
    print(json.dumps({
        "status": "PASS",
        "papers": stats["scope"]["papers"],
        "pages": stats["scope"]["pages"],
        "paragraphs": stats["scope"]["paragraphs_reconstructed"],
        "usable_paragraphs": stats["scope"]["paragraphs_used_for_patterns"],
        "quality": stats["scope"]["quality"],
        "index": str(index_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
