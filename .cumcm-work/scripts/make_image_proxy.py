#!/usr/bin/env python3
"""Create a JPEG review proxy under a hard byte limit."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-bytes", type=int, default=450_000)
    parser.add_argument("--max-width", type=int, default=1500)
    parser.add_argument("--crop", nargs=4, type=int, metavar=("L", "T", "R", "B"))
    return parser.parse_args()


def encode_under_limit(image: Image.Image, max_bytes: int, max_width: int) -> bytes:
    if image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)

    quality = 88
    while True:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= max_bytes:
            return data
        if quality > 42:
            quality -= 6
            continue
        width = max(640, round(image.width * 0.88))
        height = max(1, round(image.height * width / image.width))
        if width == image.width:
            raise RuntimeError("cannot satisfy byte limit")
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        quality = 76


def main() -> None:
    args = parse_args()
    image = Image.open(args.input).convert("RGB")
    if args.crop:
        image = image.crop(tuple(args.crop))
    data = encode_under_limit(image, args.max_bytes, args.max_width)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}: {len(data)} bytes, source={image.size}")


if __name__ == "__main__":
    main()
