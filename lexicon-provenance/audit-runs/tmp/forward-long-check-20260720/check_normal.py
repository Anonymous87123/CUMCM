from pathlib import Path

Path("build-side-effect.txt").write_text("ok\n", encoding="utf-8")
