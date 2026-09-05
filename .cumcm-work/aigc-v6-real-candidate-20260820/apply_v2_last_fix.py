import json
from pathlib import Path


path = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\rewrites-v2\U-706e53781d8d.json")
bundle = json.loads(path.read_text(encoding="utf-8"))
lines = bundle["masked_text"].splitlines(keepends=True)
replacement = (
    "基准短时间窗下，[[PROTECTED:F00001-P00567:79ea035e4a4b]]附近出现局部跨越；"
    "积分时长和数值设置放宽后，这个跨越难以保持，不能说明起点固定，因此"
    "[[PROTECTED:F00001-P00568:79ea035e4a4b]]不能作为唯一临界点。本文据此只保留"
    "[[PROTECTED:F00001-P00569:e9e04c2a63fe]]的方向性判断；若要定位分岔值，仍须采用更长积分时长（"
    "[[PROTECTED:F00001-P00570:a2c261c51172]]）并配合分岔图。图"
    "[[PROTECTED:F00001-P00571:9ade67a4bf97]]给出不同积分时长下的有限时间指数。"
)
lines[23] = replacement + ("\n" if lines[23].endswith("\n") else "")
bundle["masked_text"] = "".join(lines)
path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("U-706e53781d8d line 24 updated")
