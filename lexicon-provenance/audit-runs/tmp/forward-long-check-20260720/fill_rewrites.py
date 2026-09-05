import hashlib
import json
import sys
from pathlib import Path


rewrite_dir = Path(sys.argv[1])
bundle_path = next(rewrite_dir.glob("U-*.json"))
bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
original = bundle["masked_text"]
needle = "值得注意的是，"
if needle not in original:
    raise SystemExit("expected phrase is absent")
lines = original.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
line_number = next(index for index, line in enumerate(lines, 1) if needle in line)
source_span = {
    "id": "S1",
    "start_line": line_number,
    "end_line": line_number,
    "sha256": hashlib.sha256(lines[line_number - 1].encode("utf-8")).hexdigest(),
}
summary = "删除失去强调作用的程式化提示语"
target_signal = "LEX-EMPH-01"
bundle["masked_text"] = original.replace(needle, "")
bundle["rewrite_intent"] = {
    "summary": summary,
    "operations": [
        {
            "id": "O1",
            "kind": "REWRITE_STYLE_SHELL",
            "source_span_ids": [source_span["id"]],
            "target_signals": [target_signal],
            "summary": summary,
        }
    ],
    "source_spans": [source_span],
    "target_signals": [target_signal],
}
bundle_path.write_text(
    json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
