#!/usr/bin/env python3
"""Re-OCR prose-bearing corpus pages at 220 DPI for language retrieval.

The base page corpus remains untouched. Results are checkpointed under
``.cumcm-work/style-ocr220`` and are admitted by the corpus builder only when
they pass conservative confidence and character-coverage gates.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ENGINE: RapidOCR | None = None


def init_worker() -> None:
    global ENGINE
    ENGINE = RapidOCR()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list-only", action="store_true")
    return parser.parse_args()


def target_pages(index_path: Path) -> list[tuple[int, str, int]]:
    targets: set[tuple[int, str, int]] = set()
    with index_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("quality") != "high":
                continue
            if not any("rapidocr" in method for method in record.get("source_methods", [])):
                continue
            for page in range(int(record["page_start"]), int(record["page_end"]) + 1):
                targets.add((int(record["year"]), str(record["paper"]), page))
    return sorted(targets)


def recognize_page(task: tuple[str, str, str, int]) -> tuple[str, str]:
    workspace_raw, output_root_raw, paper_key, page = task
    workspace = Path(workspace_raw)
    output_root = Path(output_root_raw)
    year_raw, paper = paper_key.split("_", 1)
    year = int(year_raw)
    problem = paper[0]
    pdf = workspace / str(year) / f"{paper}.pdf"
    destination = output_root / paper_key / f"page-{page:03d}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)

    temp_root = output_root / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{paper_key}-{page:03d}-", dir=temp_root) as temp_raw:
        temp = Path(temp_raw)
        prefix = temp / "page"
        subprocess.run(
            [
                "pdftoppm", "-q", "-f", str(page), "-l", str(page), "-r", "220",
                "-png", str(pdf), str(prefix),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        images = sorted(temp.glob("page-*.png"))
        if len(images) != 1:
            raise RuntimeError(f"pdftoppm produced {len(images)} images for {paper_key} p.{page}")
        if ENGINE is None:
            init_worker()
        result, elapsed = ENGINE(str(images[0]))

    items = result or []
    lines = []
    scores = []
    for item in items:
        text = str(item[1]).strip()
        if not text:
            continue
        score = float(item[2])
        box = [[float(value) for value in point] for point in item[0]]
        lines.append({"text": text, "confidence": score, "box": box})
        scores.append(score)
    text = "\n".join(line["text"] for line in lines)
    record = {
        "text": text,
        "lines": lines,
        "median_confidence": round(statistics.median(scores), 6) if scores else 0.0,
        "chinese_chars": len(HAN_RE.findall(text)),
        "year": year,
        "problem": problem,
        "paper": paper,
        "page": page,
        "method": "rapidocr-220dpi-style",
        "needs_tesseract": False,
        "style_ocr_schema_version": 1,
        "elapsed": elapsed,
    }
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination)
    return paper_key, f"p{page:03d} lines={len(lines)} zh={record['chinese_chars']} med={record['median_confidence']}"


def main() -> int:
    args = parse_args()
    if not shutil.which("pdftoppm"):
        raise SystemExit("pdftoppm is required")
    index_path = args.skill_root / "references" / "fulltext-style-index.jsonl"
    output_root = args.workspace / ".cumcm-work" / "style-ocr220"
    targets = target_pages(index_path)
    if args.limit:
        targets = targets[: args.limit]
    pending = []
    for year, paper, page in targets:
        destination = output_root / f"{year}_{paper}" / f"page-{page:03d}.json"
        if args.force or not destination.is_file():
            pending.append((year, paper, page))
    print(json.dumps({"targets": len(targets), "pending": len(pending), "output": str(output_root)}, ensure_ascii=False))
    if args.list_only or not pending:
        return 0

    tasks = [
        (str(args.workspace), str(output_root), f"{year}_{paper}", page)
        for year, paper, page in pending
    ]
    completed = 0
    with ProcessPoolExecutor(max_workers=max(1, args.workers), initializer=init_worker) as pool:
        futures = {pool.submit(recognize_page, task): task for task in tasks}
        for future in as_completed(futures):
            completed += 1
            paper_key, summary = future.result()
            print(f"[{completed:03d}/{len(tasks):03d}] {paper_key} {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
