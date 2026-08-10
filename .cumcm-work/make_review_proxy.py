from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description="生成受字节上限约束的 JPEG 视觉核验代理。")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--max-bytes", type=int, default=450_000)
    parser.add_argument("--max-dimension", type=int, default=1800)
    args = parser.parse_args()

    with Image.open(args.source) as opened:
        image = opened.convert("RGB")
    image.thumbnail((args.max_dimension, args.max_dimension), Image.Resampling.LANCZOS)

    encoded = b""
    for quality in range(90, 34, -5):
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        encoded = buffer.getvalue()
        if len(encoded) <= args.max_bytes:
            break
    while len(encoded) > args.max_bytes and min(image.size) > 700:
        image = image.resize(
            (int(image.width * 0.9), int(image.height * 0.9)),
            Image.Resampling.LANCZOS,
        )
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=70, optimize=True, progressive=True)
        encoded = buffer.getvalue()

    if len(encoded) > args.max_bytes:
        raise SystemExit(f"无法满足字节上限：{len(encoded)} > {args.max_bytes}")
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_bytes(encoded)
    print(f"{args.target}\t{image.width}x{image.height}\t{len(encoded)} bytes")


if __name__ == "__main__":
    main()
