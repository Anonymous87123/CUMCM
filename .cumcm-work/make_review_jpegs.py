from pathlib import Path

from PIL import Image


PROXY_DIR = Path(__file__).resolve().parent / "review-proxies"
LIMIT = 450_000


for source in sorted(PROXY_DIR.glob("*.png")):
    target = source.with_suffix(".jpg")
    with Image.open(source) as image:
        image.convert("RGB").save(target, format="JPEG", quality=82, optimize=True)
    size = target.stat().st_size
    if size > LIMIT:
        raise RuntimeError(f"proxy exceeds byte limit: {target.name}={size}")
    print(f"{target.name}\t{size}")
