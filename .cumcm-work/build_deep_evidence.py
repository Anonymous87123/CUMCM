#!/usr/bin/env python3
"""Build source-anchored deep evidence records for all 59 CUMCM papers.

The script is deliberately conservative: it records missing or low-confidence
evidence instead of inferring prose that is not present in the OCR corpus.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
PAGES_DIR = WORK / "pages"
OUTPUT = WORK / "deep-evidence"
CARDS_DIR = OUTPUT / "paper-cards"

HAN_RE = re.compile(r"[\u4e00-\u9fff]")
NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?")
NUMBERED_HEADING_RE = re.compile(
    r"^(?:第?[一二三四五六七八九十百]+[、.．]|\d+(?:[.．]\d+){0,3}[、.．\s])"
)


@dataclass(frozen=True)
class SectionSpec:
    name: str
    heading: re.Pattern[str]
    function: re.Pattern[str]


SECTION_SPECS = [
    SectionSpec("摘要", re.compile(r"^摘\s*要(?:[:：]|$)"), re.compile(r"关键词|本文|针对")),
    SectionSpec("问题重述", re.compile(r"问题(?:的)?重述|问题背景"), re.compile(r"要求|需要|给定|任务")),
    SectionSpec("模型假设", re.compile(r"模型假设|基本假设|假设条件|模型的假设"), re.compile(r"假设|忽略|视为|认为")),
    SectionSpec("符号说明", re.compile(r"符号说明|符号定义|符号与说明|符号及说明"), re.compile(r"符号|变量|参数|单位")),
    SectionSpec("建模思路", re.compile(r"问题分析|建模思路|问题的分析|模型思路"), re.compile(r"分析|思路|首先|分为|关键")),
    SectionSpec("模型构建", re.compile(r"模型(?:的)?建立|模型构建|建立模型|模型准备"), re.compile(r"令|建立|目标函数|约束条件|由.*可得")),
    SectionSpec("求解过程", re.compile(r"模型(?:的)?求解|求解过程|算法求解|求解方法|模型解法"), re.compile(r"求解|算法|迭代|初始化|步长|停止")),
    SectionSpec("结果分析", re.compile(r"结果分析|结果与分析|求解结果|结果讨论|结果的分析"), re.compile(r"结果|由[图表]|可见|表明|得到|最优")),
    SectionSpec("模型检验", re.compile(r"模型检验|模型验证|误差分析|有效性检验|结果检验|模型的检验"), re.compile(r"检验|验证|误差|残差|回代|收敛")),
    SectionSpec("灵敏度分析", re.compile(r"灵敏度|敏感性|参数扰动|稳健性|鲁棒性"), re.compile(r"扰动|变化|稳定|敏感|鲁棒")),
    SectionSpec("模型评价", re.compile(r"模型评价|模型优缺点|优点与不足|模型的评价|模型分析"), re.compile(r"优点|优势|缺点|不足|评价")),
    SectionSpec("改进方案", re.compile(r"模型改进|改进方向|进一步改进|改进方案|模型推广|推广与改进"), re.compile(r"改进|推广|进一步|有待")),
    SectionSpec("参考文献", re.compile(r"参考文献"), re.compile(r"参考文献")),
    SectionSpec("附录", re.compile(r"^附\s*录(?:[:：A-Z一二三四五六七八九十]|$)|程序代码"), re.compile(r"附录|代码|支撑材料|文件清单")),
]

SECTION_NAMES = [spec.name for spec in SECTION_SPECS]


MODEL_TERMS: list[tuple[str, str, re.Pattern[str]]] = [
    ("数据处理", "缺失值处理", re.compile(r"缺失值|缺失数据|数据缺失")),
    ("数据处理", "异常值处理", re.compile(r"异常值|离群值|箱线图|3\s*[σs]")),
    ("数据处理", "标准化", re.compile(r"Z[- ]?score|标准化|归一化", re.I)),
    ("数据处理", "插值", re.compile(r"插值|三次样条|Kriging|拉格朗日")),
    ("特征与评价", "相关分析", re.compile(r"Pearson|Spearman|Kendall|相关分析", re.I)),
    ("特征与评价", "PCA", re.compile(r"主成分|\bPCA\b", re.I)),
    ("特征与评价", "聚类", re.compile(r"K[- ]?Means|DBSCAN|层次聚类|聚类分析", re.I)),
    ("特征与评价", "AHP", re.compile(r"层次分析|\bAHP\b", re.I)),
    ("特征与评价", "熵权", re.compile(r"熵权")),
    ("特征与评价", "TOPSIS", re.compile(r"TOPSIS", re.I)),
    ("特征与评价", "VIKOR", re.compile(r"VIKOR", re.I)),
    ("特征与评价", "灰色关联", re.compile(r"灰色关联")),
    ("机理模型", "几何模型", re.compile(r"几何模型|几何关系|坐标变换|空间几何")),
    ("机理模型", "守恒模型", re.compile(r"质量守恒|能量守恒|动量守恒|守恒方程")),
    ("机理模型", "ODE", re.compile(r"常微分方程|微分方程组|\bODE\b", re.I)),
    ("机理模型", "PDE", re.compile(r"偏微分方程|\bPDE\b", re.I)),
    ("机理模型", "热传导", re.compile(r"热传导|传热方程|牛顿冷却")),
    ("机理模型", "刚体与运动学", re.compile(r"刚体|运动学|牛顿第二定律|动力学方程")),
    ("机理模型", "蒙特卡洛", re.compile(r"蒙特卡洛|Monte\s*Carlo", re.I)),
    ("规划模型", "线性规划", re.compile(r"线性规划|\bLP\b", re.I)),
    ("规划模型", "非线性规划", re.compile(r"非线性规划|\bNLP\b", re.I)),
    ("规划模型", "整数规划", re.compile(r"整数规划|混合整数|0[-—]?1\s*规划|\bMILP\b", re.I)),
    ("规划模型", "动态规划", re.compile(r"动态规划")),
    ("规划模型", "多目标规划", re.compile(r"多目标|Pareto|帕累托", re.I)),
    ("规划模型", "鲁棒优化", re.compile(r"鲁棒优化|稳健优化|机会约束")),
    ("图网络模型", "最短路", re.compile(r"Dijkstra|Floyd|最短路|SPFA", re.I)),
    ("图网络模型", "网络流", re.compile(r"最大流|最小费用流|网络流")),
    ("图网络模型", "图匹配", re.compile(r"二分图匹配|匈牙利算法|节点重要性")),
    ("统计模型", "线性回归", re.compile(r"多元线性回归|线性回归|最小二乘")),
    ("统计模型", "Logistic", re.compile(r"Logistic\s*回归|逻辑回归|Logit", re.I)),
    ("统计模型", "方差分析", re.compile(r"方差分析|ANOVA", re.I)),
    ("统计模型", "灰色预测", re.compile(r"GM\s*\(\s*1\s*,\s*1\s*\)|灰色预测|灰色模型", re.I)),
    ("预测模型", "ARIMA", re.compile(r"SARIMA|ARIMA", re.I)),
    ("预测模型", "VAR", re.compile(r"\bVAR\b|向量自回归", re.I)),
    ("预测模型", "Prophet", re.compile(r"Prophet", re.I)),
    ("预测模型", "神经网络", re.compile(r"神经网络|BP\s*网络|CNN|RNN|LSTM|GRU|TCN", re.I)),
    ("预测模型", "支持向量机", re.compile(r"支持向量|\bSVM\b|\bSVR\b", re.I)),
    ("预测模型", "树模型", re.compile(r"随机森林|决策树|XGBoost|LightGBM|CatBoost|AdaBoost", re.I)),
    ("求解算法", "RK4", re.compile(r"Runge[-— ]?Kutta|龙格库塔|\bRK4\b", re.I)),
    ("求解算法", "有限差分", re.compile(r"有限差分|差分格式|\bFDM\b", re.I)),
    ("求解算法", "有限元", re.compile(r"有限元|\bFEM\b", re.I)),
    ("求解算法", "遗传算法", re.compile(r"遗传算法|Genetic\s*Algorithm|\bGA\b", re.I)),
    ("求解算法", "粒子群", re.compile(r"粒子群|\bPSO\b", re.I)),
    ("求解算法", "模拟退火", re.compile(r"模拟退火|Simulated\s*Annealing|\bSA\b", re.I)),
    ("求解算法", "蚁群算法", re.compile(r"蚁群|\bACO\b", re.I)),
    ("求解算法", "差分进化", re.compile(r"差分进化|\bDE\b", re.I)),
    ("求解算法", "多目标智能优化", re.compile(r"NSGA[-— ]?II|MOPSO", re.I)),
    ("求解算法", "贪心与搜索", re.compile(r"贪心|二分查找|遍历|回溯|启发式搜索")),
    ("检验方法", "误差指标", re.compile(r"MAE|MSE|RMSE|MAPE|相对误差|绝对误差", re.I)),
    ("检验方法", "交叉验证", re.compile(r"交叉验证|K\s*折|留出法", re.I)),
    ("检验方法", "残差检验", re.compile(r"残差|拟合优度|R\s*\^?2", re.I)),
    ("检验方法", "灵敏度检验", re.compile(r"灵敏度|敏感性|参数扰动|稳健性")),
]

SEMANTIC_CUES = {
    "result": re.compile(r"结果|得到|求得|最优|由[图表]|可见|表明|说明|相比|提高|降低|误差"),
    "validation": re.compile(r"检验|验证|回代|残差|误差|收敛|拟合优度|交叉验证|对照|守恒|置信区间"),
    "sensitivity": re.compile(r"灵敏度|敏感性|稳健性|鲁棒性|扰动|参数变化|稳定区间"),
    "innovation": re.compile(r"创新|改进|修正|引入|耦合|分层|自适应|融合|重新设计|优化了"),
    "defect": re.compile(r"不足|缺点|局限|误差来源|未考虑|忽略|有待|受限|难以|缺陷"),
}

VISUAL_PATTERNS = {
    "table_caption": re.compile(r"^表\s*[A-Za-z一二三四五六七八九十\d]+(?:[-—.．]\d+)*"),
    "figure_caption": re.compile(r"^图\s*[A-Za-z一二三四五六七八九十\d]+(?:[-—.．]\d+)*"),
    "formula": re.compile(r"=|≤|≥|∑|∫|√|\^|_[{(]|\b(?:max|min|argmin|argmax)\b", re.I),
}

STAGE_ORDER = {name: index for index, name in enumerate(
    ["数据处理", "特征与评价", "机理模型", "规划模型", "图网络模型", "统计模型", "预测模型", "求解算法", "检验方法"]
)}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).strip("·.。,:：;；-—_()（）[]【】")


def clean_excerpt(text: str, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def load_inventory() -> list[dict]:
    matrix = list(csv.DictReader((WORK / "paper_feature_matrix.csv").open(encoding="utf-8-sig")))
    if len(matrix) != 59 or sum(int(row["pages"]) for row in matrix) != 2892:
        raise RuntimeError("paper_feature_matrix inventory is not 59 papers / 2892 pages")
    return matrix


def load_pages(row: dict) -> list[dict]:
    path = PAGES_DIR / f"{row['year']}_{row['paper']}.jsonl"
    pages = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = list(range(1, int(row["pages"]) + 1))
    if [page["page"] for page in pages] != expected:
        raise RuntimeError(f"page continuity failed: {path.name}")
    return pages


def line_ref(pages: list[dict], page_index: int, line_index: int) -> dict:
    page = pages[page_index]
    line = page["lines"][line_index]
    return {
        "page_index": page_index,
        "line_index": line_index,
        "page": page["page"],
        "line": line_index + 1,
        "text": clean_excerpt(str(line.get("text", "")), 300),
        "normalized": normalize(str(line.get("text", ""))),
        "confidence": float(line.get("confidence", page.get("median_confidence", 0)) or 0),
        "unconfirmed": bool(page.get("needs_tesseract")),
        "method": page.get("method", ""),
        "box": line.get("box") or [],
    }


def all_lines(pages: list[dict]) -> list[dict]:
    return [
        line_ref(pages, page_index, line_index)
        for page_index, page in enumerate(pages)
        for line_index, _ in enumerate(page["lines"])
    ]


def context(pages: list[dict], ref: dict, radius: int = 2) -> str:
    lines = pages[ref["page_index"]]["lines"]
    start = max(0, ref["line_index"] - radius)
    end = min(len(lines), ref["line_index"] + radius + 1)
    return clean_excerpt(" / ".join(str(item.get("text", "")) for item in lines[start:end]))


def is_toc_like(pages: list[dict], page_index: int) -> bool:
    page = pages[page_index]
    normalized_lines = [normalize(str(line.get("text", ""))) for line in page["lines"]]
    if any(text == "目录" for text in normalized_lines):
        return True
    matches = 0
    for text in normalized_lines:
        if any(spec.heading.search(text) for spec in SECTION_SPECS):
            matches += 1
    return matches >= 7


def heading_score(spec: SectionSpec, ref: dict, pages: list[dict]) -> float:
    text = ref["normalized"]
    if not text or len(text) > 65 or not spec.heading.search(text):
        return float("-inf")
    score = 2.0
    if NUMBERED_HEADING_RE.search(text):
        score += 2.0
    if len(text) <= 18:
        score += 2.0
    if text == spec.name or text.endswith(spec.name):
        score += 3.0
    if ref["confidence"] >= 0.85:
        score += 0.5
    if ref["unconfirmed"]:
        score -= 1.0
    if is_toc_like(pages, ref["page_index"]):
        score -= 5.0
    if spec.name == "摘要" and ref["page"] == 1:
        score += 5.0
    elif spec.name != "摘要" and ref["page"] == 1:
        score -= 2.0
    return score


def choose_sections(pages: list[dict], lines: list[dict]) -> dict[str, dict | None]:
    selected: dict[str, dict | None] = {}
    for spec in SECTION_SPECS:
        scored = [(heading_score(spec, ref, pages), ref) for ref in lines]
        scored = [item for item in scored if item[0] != float("-inf")]
        scored.sort(key=lambda item: (-item[0], item[1]["page"], item[1]["line"]))
        selected[spec.name] = scored[0][1] if scored and scored[0][0] >= 1 else None
    return selected


def classify_position(ref: dict, selected: dict[str, dict | None]) -> str:
    candidates = []
    position = (ref["page"], ref["line"])
    for category, heading in selected.items():
        if heading and (heading["page"], heading["line"]) <= position:
            candidates.append(((heading["page"], heading["line"]), category))
    return max(candidates)[1] if candidates else "前置内容"


def functional_candidate(spec: SectionSpec, lines: list[dict], pages: list[dict]) -> dict | None:
    candidates = []
    for ref in lines:
        text = ref["normalized"]
        if not 8 <= len(text) <= 180 or not spec.function.search(text):
            continue
        score = 1.0 + (1.0 if NUMBER_RE.search(text) else 0.0)
        score += min(len(HAN_RE.findall(text)) / 80.0, 1.5)
        if ref["unconfirmed"]:
            score -= 0.75
        if is_toc_like(pages, ref["page_index"]):
            score -= 3.0
        candidates.append((score, ref))
    candidates.sort(key=lambda item: (-item[0], item[1]["page"], item[1]["line"]))
    return candidates[0][1] if candidates and candidates[0][0] > 0 else None


def paragraph_pattern(text: str) -> str:
    patterns = []
    if re.search(r"首先|其次|然后|最后", text):
        patterns.append("顺序展开")
    if re.search(r"令|记|设.+为", text):
        patterns.append("变量定义")
    if re.search(r"由于|因为|因此|从而", text):
        patterns.append("依据-推论")
    if re.search(r"由[图表式].*可见|表明|说明", text):
        patterns.append("读数-解释")
    if re.search(r"优点|不足|局限|改进", text):
        patterns.append("能力-边界")
    return "、".join(patterns) or "功能陈述"


def section_rows(row: dict, pages: list[dict], lines: list[dict], selected: dict[str, dict | None]) -> list[dict]:
    rows = []
    chosen_positions = sorted(
        (heading["page"], heading["line"], category)
        for category, heading in selected.items() if heading
    )
    for spec in SECTION_SPECS:
        heading = selected[spec.name]
        status = "heading_located"
        evidence = heading
        if not evidence:
            evidence = functional_candidate(spec, lines, pages)
            status = "functional_evidence" if evidence else "not_detected"
        if not evidence:
            rows.append({
                "year": row["year"], "problem": row["problem"], "paper": row["paper"],
                "pages": row["pages"], "category": spec.name, "status": status,
                "heading_text": "", "page": "", "line": "", "end_page": "",
                "confidence": "", "ocr_status": "missing", "method": "",
                "excerpt": "", "paragraph_pattern": "", "original_position": "",
            })
            continue
        end_page = evidence["page"]
        for page, line, _ in chosen_positions:
            if (page, line) > (evidence["page"], evidence["line"]):
                end_page = page
                break
        else:
            end_page = min(int(row["pages"]), evidence["page"] + 3)
        excerpt = context(pages, evidence, radius=3)
        rows.append({
            "year": row["year"], "problem": row["problem"], "paper": row["paper"],
            "pages": row["pages"], "category": spec.name, "status": status,
            "heading_text": heading["text"] if heading else "",
            "page": evidence["page"], "line": evidence["line"], "end_page": end_page,
            "confidence": round(evidence["confidence"], 6),
            "ocr_status": "unconfirmed" if evidence["unconfirmed"] else "confirmed",
            "method": evidence["method"], "excerpt": excerpt,
            "paragraph_pattern": paragraph_pattern(excerpt),
            "original_position": f"{row['year']}/{row['paper']}.pdf#page={evidence['page']}:line={evidence['line']}",
        })
    return rows


def semantic_rows(row: dict, pages: list[dict], lines: list[dict], selected: dict[str, dict | None]) -> list[dict]:
    output = []
    for kind, cue in SEMANTIC_CUES.items():
        scored = []
        for ref in lines:
            text = ref["normalized"]
            if not 10 <= len(text) <= 220 or not cue.search(text):
                continue
            category = classify_position(ref, selected)
            if category in {"参考文献", "附录"}:
                continue
            score = min(len(HAN_RE.findall(text)) / 60.0, 2.0)
            if NUMBER_RE.search(text):
                score += 1.5
            if kind == "validation" and re.search(r"误差|残差|收敛|交叉验证|回代", text):
                score += 2.0
            if kind in {"innovation", "defect"} and re.search(r"本文|模型|方法", text):
                score += 1.0
            if ref["unconfirmed"]:
                score -= 0.75
            scored.append((score, ref, category))
        scored.sort(key=lambda item: (-item[0], item[1]["page"], item[1]["line"]))
        used_pages = set()
        rank = 0
        for score, ref, category in scored:
            if ref["page"] in used_pages and len(used_pages) < 2:
                continue
            rank += 1
            used_pages.add(ref["page"])
            output.append({
                "year": row["year"], "problem": row["problem"], "paper": row["paper"],
                "evidence_kind": kind, "rank": rank, "section": category,
                "page": ref["page"], "line": ref["line"],
                "confidence": round(ref["confidence"], 6),
                "ocr_status": "unconfirmed" if ref["unconfirmed"] else "confirmed",
                "excerpt": context(pages, ref, radius=2),
                "original_position": f"{row['year']}/{row['paper']}.pdf#page={ref['page']}:line={ref['line']}",
            })
            if rank == 3:
                break
        if rank == 0:
            output.append({
                "year": row["year"], "problem": row["problem"], "paper": row["paper"],
                "evidence_kind": kind, "rank": 0, "section": "", "page": "", "line": "",
                "confidence": "", "ocr_status": "missing", "excerpt": "",
                "original_position": "",
            })
    return output


def model_rows(row: dict, pages: list[dict], lines: list[dict], selected: dict[str, dict | None]) -> list[dict]:
    reference_heading = selected.get("参考文献")
    reference_page = reference_heading["page"] if reference_heading else int(row["pages"]) + 1
    found = []
    for stage, canonical, pattern in MODEL_TERMS:
        matches = []
        for ref in lines:
            if ref["page"] >= reference_page:
                continue
            text = ref["normalized"]
            if not pattern.search(text):
                continue
            category = classify_position(ref, selected)
            score = 1.0
            if category in {"摘要", "建模思路", "模型构建", "求解过程", "结果分析", "模型检验"}:
                score += 2.0
            if re.search(r"建立|采用|利用|提出|求解|检验|模型", text):
                score += 1.5
            if ref["unconfirmed"]:
                score -= 0.75
            matches.append((score, ref, category))
        if not matches:
            continue
        matches.sort(key=lambda item: (-item[0], item[1]["page"], item[1]["line"]))
        score, ref, category = matches[0]
        found.append({
            "year": row["year"], "problem": row["problem"], "paper": row["paper"],
            "stage": stage, "model": canonical, "role_section": category,
            "page": ref["page"], "line": ref["line"],
            "confidence": round(ref["confidence"], 6),
            "ocr_status": "unconfirmed" if ref["unconfirmed"] else "confirmed",
            "excerpt": context(pages, ref, radius=2),
            "original_position": f"{row['year']}/{row['paper']}.pdf#page={ref['page']}:line={ref['line']}",
        })
    found.sort(key=lambda item: (STAGE_ORDER[item["stage"]], int(item["page"]), item["model"]))
    return found


def visual_rows(row: dict, pages: list[dict], lines: list[dict]) -> list[dict]:
    output = []
    for kind, pattern in VISUAL_PATTERNS.items():
        candidates = []
        for ref in lines:
            text = ref["normalized"]
            if not text or len(text) > 140 or not pattern.search(text):
                continue
            if kind == "formula" and len(text) < 3:
                continue
            score = ref["confidence"]
            if ref["box"]:
                score += 1.0
            if ref["unconfirmed"]:
                score -= 0.5
            if kind != "formula" and len(text) <= 60:
                score += 1.0
            if kind == "formula" and NUMBER_RE.search(text):
                score += 0.5
            candidates.append((score, ref))
        candidates.sort(key=lambda item: (-item[0], item[1]["page"], item[1]["line"]))
        if not candidates:
            output.append({
                "year": row["year"], "problem": row["problem"], "paper": row["paper"],
                "kind": kind, "status": "not_detected", "page": "", "line": "",
                "method": "", "ocr_status": "missing", "box_json": "[]", "text": "",
                "context": "", "original_position": "", "review_proxy": "", "review_status": "pending",
            })
            continue
        ref = candidates[0][1]
        output.append({
            "year": row["year"], "problem": row["problem"], "paper": row["paper"],
            "kind": kind, "status": "candidate", "page": ref["page"], "line": ref["line"],
            "method": ref["method"],
            "ocr_status": "unconfirmed" if ref["unconfirmed"] else "confirmed",
            "box_json": json.dumps(ref["box"], ensure_ascii=False, separators=(",", ":")),
            "text": ref["text"], "context": context(pages, ref, radius=2),
            "original_position": f"{row['year']}/{row['paper']}.pdf#page={ref['page']}:line={ref['line']}",
            "review_proxy": "", "review_status": "pending",
        })
    return output


def semantic_chain(models: list[dict]) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in models:
        grouped[item["stage"]].append(item["model"])
    return " -> ".join(
        f"{stage}: {'、'.join(dict.fromkeys(grouped[stage]))}"
        for stage in sorted(grouped, key=STAGE_ORDER.get)
    ) or "未从正文语境稳定定位模型链"


def first_semantic(semantic: list[dict], kind: str) -> dict | None:
    return next((item for item in semantic if item["evidence_kind"] == kind and item["rank"] == 1), None)


def card_markdown(row: dict, sections: list[dict], models: list[dict], semantic: list[dict]) -> str:
    located = sum(item["status"] != "not_detected" for item in sections)
    unconfirmed = int(row["unconfirmed_pages"])
    lines = [
        f"# {row['year']} {row['paper']} 证据卡",
        "",
        f"- 范围：{row['problem']} 题，{row['pages']} 页；严格未确认页 {unconfirmed}。",
        f"- 十四类证据：{located}/14 有定位或功能证据。",
        f"- 模型链（语境定位）：{semantic_chain(models)}",
        "- 限制：模型链按正文语境定位，仍需结合公式、表格和原始页复核，不代表已复算模型。",
        "",
        "## 十四类章节证据",
        "",
        "| 类别 | 状态 | 位置 | 段落结构 | 证据摘录 |",
        "|---|---|---|---|---|",
    ]
    for item in sections:
        excerpt = item["excerpt"].replace("|", "\\|")
        position = item["original_position"] or "未定位"
        lines.append(f"| {item['category']} | {item['status']}/{item['ocr_status']} | {position} | {item['paragraph_pattern']} | {excerpt} |")
    lines.extend(["", "## 模型语境证据", ""])
    if models:
        for item in models:
            lines.append(f"- {item['stage']} / {item['model']} / {item['role_section']}：{item['excerpt']}（{item['original_position']}，{item['ocr_status']}）")
    else:
        lines.append("- 未稳定定位；禁止补造。")
    lines.extend(["", "## 结果、检验、创新与缺陷", ""])
    for kind, label in [("result", "结果"), ("validation", "检验"), ("sensitivity", "灵敏度/稳健性"), ("innovation", "创新/改进"), ("defect", "缺陷/局限")]:
        matches = [item for item in semantic if item["evidence_kind"] == kind and item["rank"] > 0]
        if not matches:
            lines.append(f"- {label}：未稳定定位。")
        else:
            for item in matches:
                lines.append(f"- {label} {item['rank']}：{item['excerpt']}（{item['original_position']}，{item['ocr_status']}）")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    inventory = load_inventory()
    all_sections: list[dict] = []
    all_models: list[dict] = []
    all_semantic: list[dict] = []
    all_visual: list[dict] = []
    paper_cards: list[dict] = []

    for row in inventory:
        pages = load_pages(row)
        lines = all_lines(pages)
        selected = choose_sections(pages, lines)
        sections = section_rows(row, pages, lines, selected)
        models = model_rows(row, pages, lines, selected)
        semantic = semantic_rows(row, pages, lines, selected)
        visual = visual_rows(row, pages, lines)
        all_sections.extend(sections)
        all_models.extend(models)
        all_semantic.extend(semantic)
        all_visual.extend(visual)

        by_status = Counter(item["status"] for item in sections)
        paper_cards.append({
            "year": row["year"], "problem": row["problem"], "paper": row["paper"],
            "pages": row["pages"], "unconfirmed_pages": row["unconfirmed_pages"],
            "sections_located": 14 - by_status["not_detected"],
            "sections_missing": by_status["not_detected"],
            "models_located": len(models), "semantic_chain": semantic_chain(models),
            "result_excerpt": (first_semantic(semantic, "result") or {}).get("excerpt", ""),
            "result_position": (first_semantic(semantic, "result") or {}).get("original_position", ""),
            "validation_excerpt": (first_semantic(semantic, "validation") or {}).get("excerpt", ""),
            "validation_position": (first_semantic(semantic, "validation") or {}).get("original_position", ""),
            "innovation_excerpt": (first_semantic(semantic, "innovation") or {}).get("excerpt", ""),
            "innovation_position": (first_semantic(semantic, "innovation") or {}).get("original_position", ""),
            "defect_excerpt": (first_semantic(semantic, "defect") or {}).get("excerpt", ""),
            "defect_position": (first_semantic(semantic, "defect") or {}).get("original_position", ""),
        })
        (CARDS_DIR / f"{row['year']}_{row['paper']}.md").write_text(
            card_markdown(row, sections, models, semantic), encoding="utf-8", newline="\n"
        )

    if len(all_sections) != 59 * 14:
        raise RuntimeError(f"section ledger must contain 826 rows, found {len(all_sections)}")
    if len(paper_cards) != 59:
        raise RuntimeError("paper card count mismatch")

    write_csv(OUTPUT / "section_evidence.csv", all_sections)
    write_csv(OUTPUT / "model_evidence.csv", all_models)
    write_csv(OUTPUT / "semantic_evidence.csv", all_semantic)
    write_csv(OUTPUT / "visual_candidates.csv", all_visual)
    write_csv(OUTPUT / "paper_cards.csv", paper_cards)

    category_coverage = {}
    for category in SECTION_NAMES:
        rows = [item for item in all_sections if item["category"] == category]
        category_coverage[category] = {
            "papers": len(rows),
            "heading_located": sum(item["status"] == "heading_located" for item in rows),
            "functional_evidence": sum(item["status"] == "functional_evidence" for item in rows),
            "not_detected": sum(item["status"] == "not_detected" for item in rows),
            "unconfirmed_evidence": sum(item["ocr_status"] == "unconfirmed" for item in rows),
        }
    summary = {
        "schema_version": "cumcm-deep-evidence/v1",
        "papers": len(paper_cards),
        "pages": sum(int(row["pages"]) for row in inventory),
        "section_rows": len(all_sections),
        "model_rows": len(all_models),
        "semantic_rows": len(all_semantic),
        "visual_candidate_rows": len(all_visual),
        "papers_with_result_evidence": len({row["paper"] for row in all_semantic if row["evidence_kind"] == "result" and row["rank"]}),
        "papers_with_validation_evidence": len({row["paper"] for row in all_semantic if row["evidence_kind"] == "validation" and row["rank"]}),
        "papers_with_innovation_evidence": len({row["paper"] for row in all_semantic if row["evidence_kind"] == "innovation" and row["rank"]}),
        "papers_with_defect_evidence": len({row["paper"] for row in all_semantic if row["evidence_kind"] == "defect" and row["rank"]}),
        "category_coverage": category_coverage,
        "limitations": [
            "OCR excerpts are locators, not substitutes for formula/table/image verification.",
            "Model roles are selected from explicit term contexts and require paper-card review.",
            "Missing evidence remains explicit and is never filled from surrounding context.",
        ],
    }
    (OUTPUT / "coverage.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
