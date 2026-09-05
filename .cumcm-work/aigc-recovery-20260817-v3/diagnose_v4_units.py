from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(r"F:\CUMCM\.cumcm-work\aigc-recovery-20260817-v3")
RUN = ROOT / "humanize-run"
SCRIPT_DIR = Path(r"C:\Users\Lenovo\.codex\skills\AIGC\humanize-academic-chinese\scripts")
sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402
import validate_humanize_output as validator  # noqa: E402


UNIT_IDS = (
    "U-3644a855b083",
    "U-8f28215ff44b",
    "U-d92f7920cc9c",
    "U-deaaf69e6551",
    "U-e276c4b22163",
    "U-f7a8bf218cc3",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    spans = finalizer._load_jsonl(RUN / "protected_spans.jsonl")
    span_map = {item["protected_id"]: item for item in spans}
    metadata = load_json(RUN / "run_metadata.json")
    valid_signal_ids = {item["id"] for item in validator.lexical.load_lexicon()["signals"]}
    reports = []
    with tempfile.TemporaryDirectory(prefix="humanize-v4-diagnose-") as temp:
        temp_root = Path(temp)
        for unit_id in UNIT_IDS:
            chunk = load_json(RUN / "chunks" / f"{unit_id}.json")
            bundle = load_json(ROOT / "rewrites-v4" / f"{unit_id}.json")
            before, before_errors = finalizer.restore_protected(
                chunk["masked_text"], chunk["protected_ids"], span_map
            )
            after, after_errors = finalizer.restore_protected(
                bundle["masked_text"], chunk["protected_ids"], span_map
            )
            if before is None or after is None:
                raise RuntimeError({"unit": unit_id, "before": before_errors, "after": after_errors})
            before_path = temp_root / f"{unit_id}.before.tex"
            after_path = temp_root / f"{unit_id}.after.tex"
            before_path.write_text(before, encoding="utf-8", newline="")
            after_path.write_text(after, encoding="utf-8", newline="")
            keep_reasons = validator._parse_keep_reasons(
                [f"{key}={value}" for key, value in bundle.get("keep_reasons", {}).items()],
                valid_signal_ids,
            )
            payload = validator.validate(
                before_path,
                after_path,
                scene=chunk["scene"],
                keep_reasons=keep_reasons,
                fragment_mode=True,
                editable_style_wrappers=metadata["editable_style_wrappers"],
            )
            reports.append(
                {
                    "unit_id": unit_id,
                    "mechanical_validation_status": payload["mechanical_validation_status"],
                    "hard_invariant_layer_status": payload["hard_invariant_layer_status"],
                    "invariant_errors": payload["invariants"].get("errors", []),
                    "invariant_hard_failure": payload["invariants"].get("hard_failure"),
                    "review_reasons": payload["review_reasons"],
                    "pending_warnings": [
                        {
                            "code": item["code"],
                            "before": item.get("details", {}).get("before", {}),
                            "after": item.get("details", {}).get("after", {}),
                            "raw_delta": item.get("details", {}).get("raw_delta", {}),
                        }
                        for item in payload["pending_warnings"]
                    ],
                    "unexplained_strict_findings": [
                        {"signal_id": item["signal_id"], "matched": item["matched"], "line": item["line"]}
                        for item in payload["unexplained_strict_findings"]
                    ],
                    "unexplained_high_findings": [
                        {"signal_id": item["signal_id"], "matched": item["matched"], "line": item["line"]}
                        for item in payload["unexplained_high_findings"]
                    ],
                    "introduced_findings": [
                        {"signal_id": item["signal_id"], "matched": item["matched"], "line": item["line"]}
                        for item in payload["introduced_findings"]
                    ],
                }
            )
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
