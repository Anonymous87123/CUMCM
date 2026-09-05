from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SOURCE = Path(r"F:\MCM\mcm-skill-work\artifacts\papers\P-B-2016-42745-4dc9ed2b\rendered")
OUTPUT = Path(__file__).resolve().parent
GROUPS = [(1, 4), (5, 8), (9, 12), (13, 16), (17, 20), (21, 24), (25, 26)]
MAX_BYTES = 450_000


def encode(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling=0,
    )
    return buffer.getvalue()


def make_group(first: int, last: int) -> tuple[Path, int, tuple[int, int], int]:
    page_width = 720
    page_height = round(page_width * 1684 / 1191)
    gutter = 28
    label_height = 34
    canvas = Image.new(
        "RGB",
        (page_width * 2 + gutter * 3, (page_height + label_height) * 2 + gutter * 3),
        "#d8d8d8",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)

    for slot, page_number in enumerate(range(first, last + 1)):
        row, column = divmod(slot, 2)
        x = gutter + column * (page_width + gutter)
        y = gutter + row * (page_height + label_height + gutter)
        path = SOURCE / f"page-{page_number:04d}.png"
        with Image.open(path) as opened:
            page = ImageOps.exif_transpose(opened).convert("RGB")
            page.thumbnail((page_width, page_height), Image.Resampling.LANCZOS)
        canvas.paste(page, (x, y + label_height))
        draw.text((x, y), f"PAGE {page_number:02d}", fill="black", font=font)

    result = canvas
    quality = 86
    encoded = encode(result, quality)
    while len(encoded) > MAX_BYTES:
        quality -= 6
        if quality >= 38:
            encoded = encode(result, quality)
            continue
        width = round(result.width * 0.88)
        height = round(result.height * 0.88)
        result = result.resize((width, height), Image.Resampling.LANCZOS)
        quality = 80
        encoded = encode(result, quality)

    output = OUTPUT / f"pages-{first:02d}-{last:02d}.jpg"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.write_bytes(encoded)
    return output, len(encoded), result.size, quality


for start, end in GROUPS:
    path, byte_count, size, quality = make_group(start, end)
    print(f"{path.name}\t{byte_count}\t{size[0]}x{size[1]}\tq={quality}")
