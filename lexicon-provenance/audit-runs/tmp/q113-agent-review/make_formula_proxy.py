from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SOURCE = Path(r"F:\MCM\mcm-skill-work\artifacts\papers\P-B-2016-42745-4dc9ed2b\rendered")
OUTPUT = Path(__file__).resolve().parent / "formula-crops-pages-08-11.jpg"
MAX_BYTES = 450_000
CROPS = {
    8: (120, 560, 1130, 1640),
    9: (120, 820, 1130, 1600),
    10: (120, 180, 1130, 1510),
    11: (120, 400, 1130, 1620),
}


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


if OUTPUT.exists():
    raise FileExistsError(f"refusing to overwrite {OUTPUT}")

tile_width = 720
tile_height = 900
gutter = 28
label_height = 34
canvas = Image.new(
    "RGB",
    (tile_width * 2 + gutter * 3, (tile_height + label_height) * 2 + gutter * 3),
    "#d8d8d8",
)
draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default(size=24)

for slot, (page_number, crop_box) in enumerate(CROPS.items()):
    row, column = divmod(slot, 2)
    x = gutter + column * (tile_width + gutter)
    y = gutter + row * (tile_height + label_height + gutter)
    with Image.open(SOURCE / f"page-{page_number:04d}.png") as opened:
        crop = opened.convert("RGB").crop(crop_box)
        crop.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
    canvas.paste(crop, (x, y + label_height))
    draw.text((x, y), f"PAGE {page_number:02d} FORMULA/TABLE CROP", fill="black", font=font)

result = canvas
quality = 88
encoded = encode(result, quality)
while len(encoded) > MAX_BYTES:
    quality -= 6
    if quality >= 40:
        encoded = encode(result, quality)
        continue
    result = result.resize(
        (round(result.width * 0.88), round(result.height * 0.88)),
        Image.Resampling.LANCZOS,
    )
    quality = 82
    encoded = encode(result, quality)

OUTPUT.write_bytes(encoded)
print(f"{OUTPUT.name}\t{len(encoded)}\t{result.width}x{result.height}\tq={quality}")
