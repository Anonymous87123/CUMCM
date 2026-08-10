from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
PAGES_DIR = WORK / "pages"
RENDER_ROOT = WORK / "render"
TESSDATA_DIR = WORK / "tessdata"
PAPER_RE = re.compile(r"^[ABC]\d+$")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
HEADING_RE = re.compile(
    r"^(?:第?[一二三四五六七八九十百]+[、.]|\d+(?:\.\d+){0,3}[、.\s])?"
    r"(?:摘要|关键词|问题(?:重述|分析)|模型(?:假设|建立|构建|求解|检验|评价|改进)|"
    r"符号说明|结果(?:分析|检验)|灵敏度分析|稳健性分析|参考文献|附录)"
)

SECTION_PATTERNS = {
    "摘要": re.compile(r"^摘\s*要$|摘\s*要[:：]"),
    "问题重述": re.compile(r"问题重述|问题的重述|问题背景"),
    "模型假设": re.compile(r"模型假设|基本假设|假设条件"),
    "符号说明": re.compile(r"符号说明|符号定义|符号与说明"),
    "建模思路": re.compile(r"问题分析|建模思路|模型思路"),
    "模型构建": re.compile(r"模型建立|模型构建|建立模型|模型的建立"),
    "求解过程": re.compile(r"模型求解|求解过程|算法求解|模型的求解"),
    "结果分析": re.compile(r"结果分析|求解结果|结果与分析|结果讨论"),
    "模型检验": re.compile(r"模型检验|模型验证|误差分析|有效性检验"),
    "灵敏度分析": re.compile(r"灵敏度|敏感性|参数扰动"),
    "模型评价": re.compile(r"模型评价|模型优缺点|优点与不足|模型的评价"),
    "改进方案": re.compile(r"模型改进|改进方向|进一步改进|模型推广"),
    "参考文献": re.compile(r"参考文献"),
    "附录": re.compile(r"^附\s*录|附录[:：A-Z一二三四五六七八九十]"),
}

MODEL_TERMS = [
    "牛顿运动定律", "微分方程", "偏微分方程", "热传导", "冷却定律", "SIR",
    "Logistic", "捕食者", "伯努利", "刚体", "龙格库塔", "RK4", "有限差分",
    "有限元", "线性规划", "非线性规划", "二次规划", "整数规划", "0-1规划",
    "动态规划", "多目标", "遗传算法", "粒子群", "模拟退火", "蚁群", "差分进化",
    "NSGA", "MOPSO", "鲸鱼优化", "麻雀搜索", "蒙特卡洛", "Dijkstra", "Floyd",
    "最小生成树", "最大流", "最小费用流", "二分图", "路径规划", "层次分析",
    "AHP", "模糊综合评价", "灰色关联", "主成分", "因子分析", "熵权", "CRITIC",
    "TOPSIS", "VIKOR", "物元可拓", "K-Means", "DBSCAN", "层次聚类", "谱聚类",
    "拉格朗日插值", "三次样条", "克里金", "PCA", "t-SNE", "UMAP", "孤立森林",
    "ARIMA", "SARIMA", "指数平滑", "VAR", "灰色预测", "灰色马尔可夫", "Prophet",
    "神经网络", "RNN", "LSTM", "TCN", "GRU", "Logistic回归", "多元线性回归",
    "岭回归", "Lasso", "支持向量", "随机森林", "XGBoost", "LightGBM", "CatBoost",
    "朴素贝叶斯", "决策树", "AdaBoost", "卷积神经网络", "交叉验证", "留出法",
    "MAE", "MSE", "RMSE", "MAPE", "T检验", "F检验", "残差", "灵敏度",
]

THREAD_STATE = threading.local()


def run(cmd: list[str], *, text: bool = False, timeout: int | None = None):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
    )


def paper_inventory() -> list[dict]:
    papers = []
    for year in range(2020, 2026):
        for path in sorted((ROOT / str(year)).glob("*.pdf")):
            if not PAPER_RE.fullmatch(path.stem):
                continue
            info = run(["pdfinfo", str(path)], text=True)
            match = re.search(r"^Pages:\s+(\d+)", info.stdout, re.MULTILINE)
            if not match:
                raise RuntimeError(f"Cannot determine page count: {path}")
            papers.append(
                {
                    "year": year,
                    "problem": path.stem[0],
                    "code": path.stem,
                    "path": path,
                    "pages": int(match.group(1)),
                }
            )
    return papers


def direct_text_usable(path: Path) -> bool:
    proc = run(
        ["pdftotext", "-f", "1", "-l", "3", "-layout", "-enc", "UTF-8", str(path), "-"],
        text=True,
    )
    return len(re.sub(r"\s", "", proc.stdout)) > 500


def get_engine() -> RapidOCR:
    if not hasattr(THREAD_STATE, "engine"):
        THREAD_STATE.engine = RapidOCR()
    return THREAD_STATE.engine


def ocr_image(path: Path) -> dict:
    result, _ = get_engine()(str(path))
    lines = []
    confidences = []
    for item in result or []:
        box, text, confidence = item
        text = text.strip()
        if not text:
            continue
        lines.append(
            {
                "text": text,
                "confidence": round(float(confidence), 6),
                "box": [[round(float(x), 2), round(float(y), 2)] for x, y in box],
            }
        )
        confidences.append(float(confidence))
    text = "\n".join(line["text"] for line in lines)
    return {
        "text": text,
        "lines": lines,
        "median_confidence": round(statistics.median(confidences), 6) if confidences else 0.0,
        "chinese_chars": len(CHINESE_RE.findall(text)),
    }


def pdftotext_page(path: Path, page: int) -> dict:
    proc = run(
        [
            "pdftotext", "-f", str(page), "-l", str(page), "-layout", "-enc", "UTF-8",
            str(path), "-",
        ],
        text=True,
    )
    text = proc.stdout.replace("\x0c", "").strip()
    return {
        "text": text,
        "lines": [{"text": line.strip(), "confidence": 1.0, "box": []} for line in text.splitlines() if line.strip()],
        "median_confidence": 1.0 if text else 0.0,
        "chinese_chars": len(CHINESE_RE.findall(text)),
    }


def render_pdf(path: Path, target: Path, expected_pages: int, dpi: int = 120) -> list[Path]:
    if target.exists():
        existing = sorted(
            target.glob("page-*.png"),
            key=lambda p: int(re.search(r"(\d+)$", p.stem).group(1)),
        )
        if existing and [int(re.search(r"(\d+)$", p.stem).group(1)) for p in existing] == list(
            range(1, expected_pages + 1)
        ):
            return existing
        shutil.rmtree(target)
    target.mkdir(parents=True)
    prefix = target / "page"
    proc = run(["pdftoppm", "-q", "-r", str(dpi), "-png", str(path), str(prefix)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return sorted(target.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)$", p.stem).group(1)))


def render_one(path: Path, page: int, target: Path, dpi: int) -> Path:
    prefix = target / f"fallback-{page}"
    proc = run(
        [
            "pdftoppm", "-q", "-f", str(page), "-l", str(page), "-r", str(dpi),
            "-png", "-singlefile", str(path), str(prefix),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return prefix.with_suffix(".png")


def quality_score(record: dict) -> float:
    return record["median_confidence"] + min(record["chinese_chars"] / 800.0, 0.3)


def visibly_fragmented(record: dict) -> bool:
    texts = [line["text"].strip() for line in record["lines"] if line["text"].strip()]
    if len(texts) < 12:
        return False
    compact_lengths = [len(re.sub(r"\s", "", text)) for text in texts]
    short_ratio = sum(length <= 4 for length in compact_lengths) / len(compact_lengths)
    dangling_number = any(
        re.fullmatch(r"(?:第?[一二三四五六七八九十]+|\d+(?:\.\d+)*)[、.]?", text)
        for text in texts
    )
    return short_ratio >= 0.35 or dangling_number


def is_suspicious(record: dict) -> bool:
    line_count = len(record["lines"])
    return line_count >= 12 and (
        record["median_confidence"] < 0.75
        or record["chinese_chars"] < 100
        or visibly_fragmented(record)
    )


def tesseract_executable() -> str:
    candidates = [
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("Tesseract is required for suspicious OCR pages but was not found")


def tesseract_image(path: Path) -> dict:
    proc = run(
        [
            tesseract_executable(), str(path), "stdout", "--tessdata-dir", str(TESSDATA_DIR),
            "-l", "chi_sim+eng",
            "--oem", "1", "--psm", "6", "-c", "tessedit_create_tsv=1",
        ],
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Tesseract failed for {path}: {proc.stderr.strip()}")
    rows = list(csv.DictReader(proc.stdout.splitlines(), delimiter="\t"))
    lines_by_key: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    confidences = []
    for row in rows:
        text = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1) / 100.0
        except ValueError:
            confidence = -1.0
        if not text or confidence < 0:
            continue
        left = float(row.get("left") or 0)
        top = float(row.get("top") or 0)
        width = float(row.get("width") or 0)
        height = float(row.get("height") or 0)
        key = (row.get("block_num", ""), row.get("par_num", ""), row.get("line_num", ""), row.get("page_num", ""))
        lines_by_key[key].append(
            {"text": text, "confidence": confidence, "left": left, "top": top, "right": left + width, "bottom": top + height}
        )
        confidences.append(confidence)
    lines = []
    for words in lines_by_key.values():
        lines.append(
            {
                "text": " ".join(word["text"] for word in words),
                "confidence": round(statistics.median(word["confidence"] for word in words), 6),
                "box": [
                    [round(min(word["left"] for word in words), 2), round(min(word["top"] for word in words), 2)],
                    [round(max(word["right"] for word in words), 2), round(min(word["top"] for word in words), 2)],
                    [round(max(word["right"] for word in words), 2), round(max(word["bottom"] for word in words), 2)],
                    [round(min(word["left"] for word in words), 2), round(max(word["bottom"] for word in words), 2)],
                ],
            }
        )
    text = "\n".join(line["text"] for line in lines)
    return {
        "text": text,
        "lines": lines,
        "median_confidence": round(statistics.median(confidences), 6) if confidences else 0.0,
        "chinese_chars": len(CHINESE_RE.findall(text)),
    }


def page_records_complete(path: Path, expected: int) -> bool:
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]
        pages = [record["page"] for record in records]
        return pages == list(range(1, expected + 1)) and all(
            record.get("ocr_schema_version") == 2 for record in records
        )
    except (OSError, ValueError, KeyError):
        return False


def process_paper(paper: dict) -> dict:
    output = PAGES_DIR / f"{paper['year']}_{paper['code']}.jsonl"
    if page_records_complete(output, paper["pages"]):
        return {"paper": paper["code"], "year": paper["year"], "status": "cached", "seconds": 0}

    started = time.time()
    render_dir = RENDER_ROOT / f"{paper['year']}_{paper['code']}"
    text_layer = direct_text_usable(paper["path"])
    images = [] if text_layer else render_pdf(
        paper["path"], render_dir, expected_pages=paper["pages"], dpi=120
    )
    if not text_layer and len(images) != paper["pages"]:
        raise RuntimeError(f"Rendered {len(images)} of {paper['pages']} pages for {paper['code']}")

    records = []
    fallback_count = 0
    for index in range(1, paper["pages"] + 1):
        if text_layer:
            record = pdftotext_page(paper["path"], index)
            method = "pdftotext"
        else:
            record = ocr_image(images[index - 1])
            method = "rapidocr-120dpi"
            if is_suspicious(record):
                primary_metrics = {
                    "method": "rapidocr-120dpi",
                    "median_confidence": record["median_confidence"],
                    "chinese_chars": record["chinese_chars"],
                    "line_count": len(record["lines"]),
                    "fragmented": visibly_fragmented(record),
                }
                fallback_image = render_one(paper["path"], index, render_dir, 220)
                retry = tesseract_image(fallback_image)
                retry_metrics = {
                    "method": "tesseract-chi_sim+eng-220dpi",
                    "median_confidence": retry["median_confidence"],
                    "chinese_chars": retry["chinese_chars"],
                    "line_count": len(retry["lines"]),
                    "fragmented": visibly_fragmented(retry),
                }
                if quality_score(retry) > quality_score(record):
                    record = retry
                    method = "tesseract-chi_sim+eng-220dpi"
                record["fallback_audit"] = {
                    "triggered": True,
                    "primary": primary_metrics,
                    "retry": retry_metrics,
                    "selected_method": method,
                }
                fallback_image.unlink(missing_ok=True)
                fallback_count += 1
        record.update(
            {
                "ocr_schema_version": 2,
                "year": paper["year"],
                "problem": paper["problem"],
                "paper": paper["code"],
                "page": index,
                "method": method,
                "needs_tesseract": is_suspicious(record),
            }
        )
        records.append(record)

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_suffix(".jsonl.tmp")
    with temp_output.open("w", encoding="utf-8", newline="\n") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(temp_output, output)
    if render_dir.exists():
        shutil.rmtree(render_dir)
    return {
        "paper": paper["code"],
        "year": paper["year"],
        "status": "processed",
        "seconds": round(time.time() - started, 1),
        "fallback_pages": fallback_count,
    }


def load_paper_pages(paper: dict) -> list[dict]:
    path = PAGES_DIR / f"{paper['year']}_{paper['code']}.jsonl"
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", "", text).strip("·.。,:：;；-—_()（）[]【】")


def section_hits(pages: list[dict]) -> dict[str, list[dict]]:
    hits = {name: [] for name in SECTION_PATTERNS}
    for page in pages:
        for line_no, item in enumerate(page["lines"], 1):
            text = normalize_line(item["text"])
            if not text or len(text) > 35:
                continue
            for name, pattern in SECTION_PATTERNS.items():
                if pattern.search(text):
                    hits[name].append(
                        {
                            "page": page["page"],
                            "line": line_no,
                            "text": item["text"],
                            "confidence": item.get("confidence", page["median_confidence"]),
                        }
                    )
    return hits


def extract_headings(pages: list[dict]) -> list[dict]:
    headings = []
    for page in pages:
        for line_no, item in enumerate(page["lines"], 1):
            text = normalize_line(item["text"])
            if 2 <= len(text) <= 38 and HEADING_RE.search(text):
                headings.append({"page": page["page"], "line": line_no, "text": item["text"]})
    return headings


def model_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in MODEL_TERMS if term.lower() in lowered]


def context_snippet(pages: list[dict], page_num: int, line_num: int, radius: int = 2) -> str:
    page = pages[page_num - 1]
    start = max(0, line_num - 1 - radius)
    end = min(len(page["lines"]), line_num + radius)
    return " / ".join(item["text"] for item in page["lines"][start:end])[:500]


def summarize() -> None:
    papers = paper_inventory()
    summaries = []
    ledger_rows = []
    question_groups = defaultdict(list)
    all_section_positions = defaultdict(list)

    for paper in papers:
        pages = load_paper_pages(paper)
        text = "\n".join(page["text"] for page in pages)
        hits = section_hits(pages)
        headings = extract_headings(pages)
        terms = model_terms(text)
        confs = [p["median_confidence"] for p in pages if p["median_confidence"] > 0]
        unconfirmed = sum(bool(p["needs_tesseract"]) for p in pages)
        fallback_attempted = sum(bool(p.get("fallback_audit", {}).get("triggered")) for p in pages)
        summary = {
            "year": paper["year"],
            "problem": paper["problem"],
            "paper": paper["code"],
            "pages": paper["pages"],
            "text_layer": pages[0]["method"] == "pdftotext",
            "median_page_confidence": round(statistics.median(confs), 4) if confs else 0,
            "chinese_chars": sum(p["chinese_chars"] for p in pages),
            "tesseract_fallback_pages": fallback_attempted,
            "ocr_unconfirmed_pages": unconfirmed,
            "headings_found": len(headings),
            "model_terms": "、".join(terms),
        }
        for section, section_records in hits.items():
            first = section_records[0] if section_records else None
            summary[f"{section}_page"] = first["page"] if first else ""
            if first:
                all_section_positions[section].append(first["page"] / paper["pages"])
                ledger_rows.append(
                    {
                        "year": paper["year"],
                        "problem": paper["problem"],
                        "paper": paper["code"],
                        "category": section,
                        "page": first["page"],
                        "line": first["line"],
                        "source_text": first["text"],
                        "snippet": context_snippet(pages, first["page"], first["line"]),
                    }
                )
        summaries.append(summary)
        question_groups[(paper["year"], paper["problem"])].append(
            {"paper": paper["code"], "pages": paper["pages"], "terms": terms, "headings": headings[:20]}
        )

    summary_fields = list(summaries[0].keys())
    with (WORK / "paper_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summaries)

    ledger_fields = ["year", "problem", "paper", "category", "page", "line", "source_text", "snippet"]
    with (WORK / "evidence_ledger.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ledger_fields)
        writer.writeheader()
        writer.writerows(ledger_rows)

    corpus = {
        "papers": len(papers),
        "pages": sum(p["pages"] for p in papers),
        "by_year_problem": {
            f"{year}{problem}": {
                "papers": len(items),
                "pages": sum(item["pages"] for item in items),
            }
            for (year, problem), items in sorted(question_groups.items())
        },
        "section_detection": {
            section: {
                "papers": sum(bool(s[f"{section}_page"]) for s in summaries),
                "median_relative_page": round(statistics.median(values), 4) if values else None,
                "q1_relative_page": round(statistics.quantiles(values, n=4)[0], 4) if len(values) >= 4 else None,
                "q3_relative_page": round(statistics.quantiles(values, n=4)[2], 4) if len(values) >= 4 else None,
            }
            for section, values in all_section_positions.items()
        },
        "tesseract_fallback_pages": sum(s["tesseract_fallback_pages"] for s in summaries),
        "ocr_unconfirmed_pages": sum(s["ocr_unconfirmed_pages"] for s in summaries),
    }
    (WORK / "corpus_summary.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (WORK / "question_summary.md").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 2020--2025 A/B/C 编号论文提取摘要\n\n")
        for (year, problem), items in sorted(question_groups.items()):
            fh.write(f"## {year} {problem} 题\n\n")
            for item in items:
                heading_text = "；".join(f"p.{h['page']} {h['text']}" for h in item["headings"])
                fh.write(
                    f"- {item['paper']}（{item['pages']} 页）模型词："
                    f"{'、'.join(item['terms']) or '未从词表稳定识别'}。"
                    f"标题线索：{heading_text or '未稳定识别'}。\n"
                )
            fh.write("\n")

    print(json.dumps(corpus, ensure_ascii=False, indent=2), flush=True)


def full(workers: int) -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)
    papers = paper_inventory()
    print(
        f"START papers={len(papers)} pages={sum(p['pages'] for p in papers)} workers={workers}",
        flush=True,
    )
    completed = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr") as pool:
        futures = {pool.submit(process_paper, paper): paper for paper in papers}
        for future in as_completed(futures):
            paper = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                print(f"ERROR {paper['year']} {paper['code']} {type(exc).__name__}: {exc}", flush=True)
                raise
            completed += 1
            print(f"DONE {completed}/{len(papers)} {json.dumps(result, ensure_ascii=False)}", flush=True)
    summarize()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["full", "summarize"])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.mode == "full":
        full(max(1, min(args.workers, 8)))
    else:
        summarize()


if __name__ == "__main__":
    main()
