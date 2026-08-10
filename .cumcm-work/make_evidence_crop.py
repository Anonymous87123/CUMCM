#!/usr/bin/env python3
"""Render one PDF page and create a byte-bounded evidence crop.

The full-page PNG and lossless crop stay on disk. Only the JPEG proxy is
intended for model-visible review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".cumcm-work" / "deep-evidence" / "raster-review"
BYTE_LIMIT = 450_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_page(pdf: Path, paper_id: str, page: int, dpi: int) -> Path:
    paper_dir = OUTPUT / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    target = paper_dir / f"page-{page:03d}-{dpi}dpi.png"
    if target.exists():
        return target
    binary = shutil.which("pdftoppm")
    if not binary:
        raise RuntimeError("pdftoppm is required")
    prefix = target.with_suffix("")
    subprocess.run(
        [binary, "-f", str(page), "-l", str(page), "-r", str(dpi),
         "-png", "-singlefile", str(pdf), str(prefix)],
        check=True,
    )
    if not target.exists():
        raise RuntimeError(f"render output missing: {target}")
    return target


def bounded_jpeg(image: Image.Image, target: Path) -> tuple[int, int]:
    work = image.convert("RGB")
    if work.width > 1800:
        height = round(work.height * 1800 / work.width)
        work = work.resize((1800, height), Image.Resampling.LANCZOS)
    for quality in (88, 82, 76, 70, 64, 58, 52, 46, 40):
        work.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
        if target.stat().st_size <= BYTE_LIMIT:
            return quality, target.stat().st_size
    scale = 0.85
    while target.stat().st_size > BYTE_LIMIT and work.width > 600:
        work = work.resize(
            (round(work.width * scale), round(work.height * scale)),
            Image.Resampling.LANCZOS,
        )
        work.save(target, "JPEG", quality=40, optimize=True, progressive=True)
    if target.stat().st_size > BYTE_LIMIT:
        raise RuntimeError(f"cannot bound JPEG below {BYTE_LIMIT} bytes")
    return 40, target.stat().st_size


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--crop", type=int, nargs=4, metavar=("L", "T", "R", "B"), required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--dpi", type=int, default=220)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf = args.pdf if args.pdf.is_absolute() else ROOT / args.pdf
    pdf = pdf.resolve()
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    full_page = render_page(pdf, args.paper_id, args.page, args.dpi)
    with Image.open(full_page) as page_image:
        width, height = page_image.size
        left, top, right, bottom = args.crop
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError(f"crop {args.crop} outside page {width}x{height}")
        crop = page_image.crop((left, top, right, bottom))
        paper_dir = OUTPUT / args.paper_id
        lossless = paper_dir / f"p{args.page:03d}-{args.label}.png"
        proxy = paper_dir / f"p{args.page:03d}-{args.label}.jpg"
        crop.save(lossless, "PNG", optimize=True)
        quality, proxy_bytes = bounded_jpeg(crop, proxy)
    metadata = {
        "paper_id": args.paper_id,
        "pdf": pdf.relative_to(ROOT).as_posix(),
        "page": args.page,
        "dpi": args.dpi,
        "page_pixels": [width, height],
        "crop_pixels": list(args.crop),
        "label": args.label,
        "full_page_png": full_page.relative_to(ROOT).as_posix(),
        "full_page_sha256": sha256(full_page),
        "lossless_crop": lossless.relative_to(ROOT).as_posix(),
        "lossless_crop_sha256": sha256(lossless),
        "review_proxy": proxy.relative_to(ROOT).as_posix(),
        "review_proxy_sha256": sha256(proxy),
        "review_proxy_bytes": proxy_bytes,
        "jpeg_quality": quality,
        "review_status": "pending",
    }
    meta_path = paper_dir / f"p{args.page:03d}-{args.label}.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(metadata, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
