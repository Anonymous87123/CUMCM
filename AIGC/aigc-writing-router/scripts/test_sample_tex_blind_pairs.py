#!/usr/bin/env python3
"""Tests for deterministic, quality-label-blind TeX holdout sampling."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from adapter_core import sha256_file
from sample_tex_blind_pairs import SPEC_SCHEMA, sample


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def prose(label: str, suffix: str) -> str:
    return f"{label}这是一段用于留出盲评的中文建模正文，其中保留数据条件、模型依据和结果解释，避免依靠质量标签选段{suffix}。"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-tex-sample-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source_lines = [
            r"\section{问题分析}",
            prose("第一段", "原稿"),
            prose("第二段", "原稿"),
            prose("第三段", "原稿"),
            r"\section{模型检验}",
            prose("第四段", "原稿"),
            prose("第五段", "原稿"),
            prose("第六段", "原稿"),
        ]
        candidate_lines = [
            source_lines[0],
            prose("第一段", "候选"),
            prose("第二段", "候选"),
            prose("第三段", "候选"),
            source_lines[4],
            prose("第四段", "候选"),
            prose("第五段", "候选"),
            prose("第六段", "候选"),
        ]
        source.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
        candidate.write_text("\n".join(candidate_lines) + "\n", encoding="utf-8")

        exclude = root / "development-spec.json"
        exclude_payload = {
            "schema": SPEC_SCHEMA,
            "source": {"path": str(source), "sha256": sha256_file(source)},
            "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
            "pairs": [{
                "id": "dev-line-2",
                "section": "问题分析",
                "source_lines": {"start": 2, "end": 2},
                "candidate_lines": {"start": 2, "end": 2},
            }],
        }
        exclude.write_text(json.dumps(exclude_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        first = root / "holdout-a.json"
        second = root / "holdout-b.json"
        report = sample(source, candidate, first, total=4, seed=20260818, exclude_spec=exclude, min_han=20)
        repeated = sample(source, candidate, second, total=4, seed=20260818, exclude_spec=exclude, min_han=20)
        payload = json.loads(first.read_text(encoding="utf-8"))
        repeat_payload = json.loads(second.read_text(encoding="utf-8"))

        require(report["status"] == "pass" and repeated["status"] == "pass", "valid sampling failed", report)
        require(payload == repeat_payload, "same seed did not produce identical specs", payload)
        require(payload["sampling"]["quality_labels_used"] is False, "quality-label blindness not recorded", payload)
        require(payload["sampling"]["exclude_spec"]["sha256"] == sha256_file(exclude), "exclude spec is not hash-bound", payload)
        require(payload["source"]["sha256"] == sha256_file(source), "source hash missing", payload)
        require(payload["candidate"]["sha256"] == sha256_file(candidate), "candidate hash missing", payload)
        selected = {pair["source_lines"]["start"] for pair in payload["pairs"]}
        require(2 not in selected and len(selected) == 4, "development line was selected or count is wrong", payload)
        require(len({pair["section"] for pair in payload["pairs"]}) == 2, "section stratification failed", payload)

        second_exclude = root / "second-development-spec.json"
        second_payload = dict(exclude_payload)
        second_payload["pairs"] = [{
            "id": "dev-line-3",
            "section": "问题分析",
            "source_lines": {"start": 3, "end": 3},
            "candidate_lines": {"start": 3, "end": 3},
        }]
        second_exclude.write_text(json.dumps(second_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        multi_output = root / "holdout-multi.json"
        sample(
            source, candidate, multi_output, total=4, seed=20260818,
            exclude_spec=[exclude, second_exclude], min_han=20,
        )
        multi_payload = json.loads(multi_output.read_text(encoding="utf-8"))
        multi_lines = {pair["source_lines"]["start"] for pair in multi_payload["pairs"]}
        require(
            2 not in multi_lines and 3 not in multi_lines
            and len(multi_payload["sampling"].get("exclude_specs", [])) == 2,
            "multiple development specs were not excluded and bound",
            multi_payload,
        )

        short_candidate = root / "short.tex"
        short_candidate.write_text("\n".join(candidate_lines[:-1]) + "\n", encoding="utf-8")
        try:
            sample(source, short_candidate, root / "bad-lines.json", total=2, seed=1, min_han=20)
        except ValueError as exc:
            require("line-preserving" in str(exc), "line mismatch raised the wrong error", str(exc))
        else:
            raise AssertionError("line-count mismatch passed")

        try:
            sample(source, candidate, root / "too-many.json", total=6, seed=1, exclude_spec=exclude, min_han=20)
        except ValueError as exc:
            require("eligible unseen" in str(exc), "insufficient pool raised the wrong error", str(exc))
        else:
            raise AssertionError("insufficient unseen pool passed")

        bad_exclude = root / "bad-exclude.json"
        bad_exclude.write_text('{"schema":"wrong","pairs":[]}\n', encoding="utf-8")
        try:
            sample(source, candidate, root / "bad-exclude-output.json", total=2, seed=1, exclude_spec=bad_exclude, min_han=20)
        except ValueError as exc:
            require(SPEC_SCHEMA in str(exc), "bad exclude schema raised the wrong error", str(exc))
        else:
            raise AssertionError("bad exclude schema passed")

    print("PASS: holdout sampling is deterministic, section-stratified, hash-bound and excludes development lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
