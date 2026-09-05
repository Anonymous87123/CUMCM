import json
from pathlib import Path


root = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\rewrites-v2")

for unit_id, line_no, old, new in [
    ("U-e276c4b22163", 11, "取两组权重平均后", "取二者平均后"),
    ("U-c530201b41a9", 2, "2025年的1.8倍总量是一项观测事实", "2025年的1.8倍总量来自观测"),
]:
    path = root / f"{unit_id}.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    lines = bundle["masked_text"].splitlines(keepends=True)
    if lines[line_no - 1].count(old) != 1:
        raise RuntimeError(f"{unit_id}:{line_no}: expected {old!r}")
    lines[line_no - 1] = lines[line_no - 1].replace(old, new)
    bundle["masked_text"] = "".join(lines)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("reasoning hard invariants restored")
