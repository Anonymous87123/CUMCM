#!/usr/bin/env python3
"""Render one paper and build page-level RapidOCR evidence artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import time
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


PAGE_NUMBER_RE = re.compile(r"(\d+)$")
CHINESE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def page_number(path: Path) -> int:
    match = PAGE_NUMBER_RE.search(path.stem)
    if not match:
        raise ValueError(f"cannot read page number from {path.name}")
    return int(match.group(1))


def render(pdf: Path, image_dir: Path, dpi: int) -> list[Path]:
    image_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(image_dir.glob("page-*.png"), key=page_number)
    if images:
        return images

    prefix = image_dir / "page"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(prefix)],
        check=True,
    )
    return sorted(image_dir.glob("page-*.png"), key=page_number)


def normalize_box(box: object) -> list[list[float]]:
    if hasattr(box, "tolist"):
        box = box.tolist()
    return [[float(x), float(y)] for x, y in box]  # type: ignore[arg-type]


def recognize_page(engine: RapidOCR, image: Path, page: int) -> dict[str, object]:
    started = time.perf_counter()
    result, _ = engine(str(image))
    elapsed = time.perf_counter() - started
    lines: list[dict[str, object]] = []
    for item in result or []:
        box, text, confidence = item
        lines.append(
            {
                "text": str(text),
                "confidence": float(confidence),
                "box": normalize_box(box),
            }
        )

    text = "\n".join(str(line["text"]) for line in lines)
    confidences = [float(line["confidence"]) for line in lines]
    median_confidence = statistics.median(confidences) if confidences else 0.0
    mean_confidence = statistics.fmean(confidences) if confidences else 0.0
    chinese_chars = len(CHINESE_RE.findall(text))
    return {
        "page": page,
        "image": image.name,
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "chinese_chars": chinese_chars,
        "median_confidence": median_confidence,
        "mean_confidence": mean_confidence,
        "elapsed_seconds": elapsed,
        "needs_review": median_confidence < 0.75 or chinese_chars < 100,
        "method": "rapidocr-180dpi",
    }


def load_or_recognize(
    engine: RapidOCR,
    image: Path,
    page: int,
    json_dir: Path,
) -> dict[str, object]:
    json_path = json_dir / f"page-{page:03d}.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
    record = recognize_page(engine, image, page)
    json_path.write_text(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return record


def write_outputs(records: list[dict[str, object]], text_dir: Path) -> None:
    text_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        page = int(record["page"])
        (text_dir / f"page-{page:03d}.txt").write_text(
            str(record["text"]), encoding="utf-8"
        )

    with (text_dir / "merged.txt").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(f"\n===== PAGE {int(record['page']):03d} =====\n")
            stream.write(str(record["text"]))
            stream.write("\n")

    fields = [
        "page",
        "line_count",
        "chinese_chars",
        "median_confidence",
        "mean_confidence",
        "elapsed_seconds",
        "needs_review",
        "image",
        "text_file",
    ]
    with (text_dir / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            page = int(record["page"])
            writer.writerow(
                {
                    "page": page,
                    "line_count": record["line_count"],
                    "chinese_chars": record["chinese_chars"],
                    "median_confidence": f"{float(record['median_confidence']):.6f}",
                    "mean_confidence": f"{float(record['mean_confidence']):.6f}",
                    "elapsed_seconds": f"{float(record['elapsed_seconds']):.3f}",
                    "needs_review": str(record["needs_review"]).lower(),
                    "image": record["image"],
                    "text_file": f"page-{page:03d}.txt",
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dpi", type=int, default=180)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf = args.pdf.resolve()
    output = args.output.resolve()
    if not pdf.is_file():
        raise SystemExit(f"missing PDF: {pdf}")

    image_dir = output / f"rapid-images-{args.dpi}dpi"
    json_dir = output / "rapid-json"
    text_dir = output / "rapid-text"
    json_dir.mkdir(parents=True, exist_ok=True)
    images = render(pdf, image_dir, args.dpi)
    if not images:
        raise SystemExit("pdftoppm produced no page images")

    engine = RapidOCR()
    records: list[dict[str, object]] = []
    for image in images:
        page = page_number(image)
        record = load_or_recognize(engine, image, page, json_dir)
        records.append(record)
        print(
            f"page {page}/{len(images)}: chars={record['chinese_chars']} "
            f"median={float(record['median_confidence']):.3f}",
            flush=True,
        )

    records.sort(key=lambda item: int(item["page"]))
    write_outputs(records, text_dir)
    print(f"wrote {len(records)} pages to {text_dir}")


if __name__ == "__main__":
    main()
