#!/usr/bin/env python3
"""Build one hash-bound rewrite-intent operation from a frozen long-doc unit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402


OUTPUT_SCHEMA = "humanize-rewrite-intent-authoring-helper/v1"
OPERATION_KIND_RE = re.compile(r"[A-Z][A-Z0-9_.-]{1,63}")


def _normalized_source_lines(masked_text: str) -> list[str]:
    lines = masked_text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )
    return lines or [""]


def build_intent(
    run_dir: Path,
    unit_id: str,
    start_line: int,
    end_line: int,
    operation_kind: str,
    target_signals: Sequence[str],
    summary: str,
) -> dict[str, Any]:
    preflight = finalizer.validate_long_authoring_snapshot(run_dir)
    summary_state = preflight.get("summary")
    chunks = preflight.get("chunks")
    if not isinstance(summary_state, dict) or summary_state.get("status") != "PASS":
        raise ValueError("long_authoring_preflight_not_pass")
    if not isinstance(chunks, dict) or unit_id not in chunks:
        raise ValueError("unit_id_not_authoring_eligible")
    chunk = chunks[unit_id]
    if not isinstance(chunk, dict) or chunk.get("status") != "PENDING":
        raise ValueError("unit_not_pending")
    masked_text = chunk.get("masked_text")
    if not isinstance(masked_text, str):
        raise ValueError("unit_masked_text_invalid")
    if (
        isinstance(start_line, bool)
        or isinstance(end_line, bool)
        or start_line < 1
        or end_line < start_line
    ):
        raise ValueError("source_line_range_invalid")
    source_lines = _normalized_source_lines(masked_text)
    if end_line > len(source_lines):
        raise ValueError("source_line_range_out_of_bounds")
    if not OPERATION_KIND_RE.fullmatch(operation_kind):
        raise ValueError("operation_kind_invalid")
    signals = list(target_signals)
    if (
        not signals
        or len(signals) > 32
        or len(set(signals)) != len(signals)
        or any(
            not isinstance(signal, str)
            or not finalizer.REWRITE_INTENT_TARGET_SIGNAL_RE.fullmatch(signal)
            for signal in signals
        )
    ):
        raise ValueError("target_signals_invalid")
    if not finalizer._specific_intent_summary(summary):
        raise ValueError("summary_must_be_specific")

    selected = "".join(source_lines[start_line - 1 : end_line])
    intent = {
        "summary": summary,
        "operations": [
            {
                "id": "O1",
                "kind": operation_kind,
                "source_span_ids": ["S1"],
                "target_signals": signals,
                "summary": summary,
            }
        ],
        "source_spans": [
            {
                "id": "S1",
                "start_line": start_line,
                "end_line": end_line,
                "sha256": finalizer.sha256(selected.encode("utf-8")),
            }
        ],
        "target_signals": signals,
    }
    finalizer._validate_rewrite_intent_shape(intent)
    finalizer._validate_intent_span_bindings(
        intent["source_spans"],
        masked_text,
        "rewrite_intent_source_spans",
    )
    return {
        "schema_version": OUTPUT_SCHEMA,
        "status": "GENERATED_AUTHORING_FRAGMENT",
        "unit_id": unit_id,
        "source_line_count": len(source_lines),
        "selected_start_line": start_line,
        "selected_end_line": end_line,
        "frozen_masked_text_sha256": finalizer.sha256(masked_text.encode("utf-8")),
        "rewrite_intent": intent,
        "hash_rule": "NORMALIZED_LF_SPLITLINES_KEEPENDS_UTF8_SHA256_LOWERCASE_HEX",
        "writes_performed": False,
        "completion_claim_allowed": False,
        "next_action": (
            "EDIT_THE_SCAFFOLDED_MASKED_TEXT_THEN_INSERT_THIS_REWRITE_INTENT_AND_FINALIZE"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "从冻结长文 unit 生成一个合法、hash-bound 的单跨度 rewrite_intent；"
            "不修改任何文件，也不授予完成态。"
        )
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--start-line", required=True, type=int)
    parser.add_argument("--end-line", required=True, type=int)
    parser.add_argument("--operation-kind", required=True)
    parser.add_argument(
        "--target-signal",
        required=True,
        action="append",
        dest="target_signals",
        help="可重复传入；必须使用 LEX/HUM/VOICE/STYLE/SCENE/USER 等合法前缀",
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = build_intent(
            args.run_dir.resolve(),
            args.unit_id,
            args.start_line,
            args.end_line,
            args.operation_kind,
            args.target_signals,
            args.summary,
        )
    except (OSError, ValueError) as error:
        failure = {
            "schema_version": OUTPUT_SCHEMA,
            "status": "FAIL",
            "error_code": str(error).split(":", 1)[0],
            "writes_performed": False,
            "completion_claim_allowed": False,
        }
        if args.format == "json":
            print(json.dumps(failure, ensure_ascii=False, indent=2))
        else:
            print(f"FAIL {failure['error_code']}")
        return 1
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "GENERATED_AUTHORING_FRAGMENT "
            f"unit={payload['unit_id']} "
            f"lines={payload['selected_start_line']}-{payload['selected_end_line']}"
        )
        print(
            "rewrite_intent="
            + json.dumps(
                payload["rewrite_intent"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        print("writes_performed=false; completion_claim_allowed=false")
        print("next_action=" + payload["next_action"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
