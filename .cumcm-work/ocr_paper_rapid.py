from __future__ import annotations

import argparse
import csv
import re
import statistics
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


PAGE_RE = re.compile(r"(\d+)(?=\.[^.]+$)")
ZH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def page_number(path: Path) -> int:
    match = PAGE_RE.search(path.name)
    if not match:
        raise ValueError(f"无法从文件名取得页码：{path.name}")
    return int(match.group(1))


def numeric_total(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return sum(numeric_total(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(numeric_total(item) for item in value)
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="逐页运行 RapidOCR 并生成文本与质量指标。")
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(
        (p for p in args.image_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}),
        key=page_number,
    )
    if not images:
        raise SystemExit(f"未找到页面图像：{args.image_dir}")

    engine = RapidOCR()
    metrics: list[dict[str, object]] = []
    merged: list[str] = []

    for index, image in enumerate(images, start=1):
        page = page_number(image)
        result, elapsed = engine(str(image))
        rows = result or []
        texts = [str(item[1]).strip() for item in rows if len(item) >= 3 and str(item[1]).strip()]
        scores = [float(item[2]) for item in rows if len(item) >= 3]
        page_text = "\n".join(texts)
        chinese_chars = len(ZH_RE.findall(page_text))
        median_confidence = statistics.median(scores) if scores else 0.0
        mean_confidence = statistics.fmean(scores) if scores else 0.0

        text_path = args.output_dir / f"page-{page:03d}.txt"
        text_path.write_text(page_text + "\n", encoding="utf-8")
        merged.append(f"===== PAGE {page:03d} =====\n{page_text}\n")
        metrics.append(
            {
                "page": page,
                "line_count": len(texts),
                "chinese_chars": chinese_chars,
                "median_confidence": f"{median_confidence:.6f}",
                "mean_confidence": f"{mean_confidence:.6f}",
                "elapsed_seconds": f"{numeric_total(elapsed):.3f}",
                "image": image.name,
                "text": text_path.name,
            }
        )
        print(
            f"[{index:03d}/{len(images):03d}] page={page:03d} "
            f"lines={len(texts):03d} zh={chinese_chars:04d} median={median_confidence:.3f}",
            flush=True,
        )

    (args.output_dir / "merged.txt").write_text("\n".join(merged), encoding="utf-8")
    with (args.output_dir / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0].keys()))
        writer.writeheader()
        writer.writerows(metrics)


if __name__ == "__main__":
    main()
