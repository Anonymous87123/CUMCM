from pathlib import Path
import subprocess

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "paper" / "build" / "main.pdf"
OUT = ROOT / "paper" / "review"


def save_bounded(page_no: int) -> Path:
    png_prefix = OUT / f"page-{page_no:02d}-source"
    png_path = png_prefix.with_suffix(".png")
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page_no),
            "-l",
            str(page_no),
            "-singlefile",
            "-r",
            "125",
            "-png",
            str(PDF),
            str(png_prefix),
        ],
        check=True,
    )
    image = Image.open(png_path).convert("RGB")
    path = OUT / f"page-{page_no:02d}.jpg"
    quality = 82
    while True:
        image.save(path, "JPEG", quality=quality, optimize=True)
        if path.stat().st_size <= 450_000 or quality <= 45:
            break
        quality -= 7
    png_path.unlink()
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for number in (1, 6, 8, 12):
        path = save_bounded(number)
        print(path, path.stat().st_size)
