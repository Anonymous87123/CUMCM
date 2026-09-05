from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "merge_humanize_chat_aggregates.py"
SPEC = importlib.util.spec_from_file_location("merge_humanize_chat_aggregates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_aggregate(directory: Path, lengths: list[int], phrase: str) -> Path:
    directory.mkdir()
    aggregate = directory / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": phrase, "count": 1, "message_coverage": 1},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(aggregate.read_bytes()).hexdigest()
    (directory / "run_metadata.json").write_text(
        json.dumps(
            {
                "ngram_lengths": lengths,
                "unique_candidates": 1,
                "aggregate_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return aggregate


def test_merge_accepts_disjoint_length_ranges(tmp_path: Path, monkeypatch) -> None:
    short = make_aggregate(tmp_path / "short", [1, 8], "\u66f4\u7a33")
    long = make_aggregate(
        tmp_path / "long", [9, 12], "\u5fc5\u987b\u8fdb\u4e00\u6b65\u6536\u7d27\u4e00\u70b9"
    )
    output = tmp_path / "merged.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--input",
            str(short),
            "--input",
            str(long),
            "--output",
            str(output),
        ],
    )

    assert MODULE.main() == 0
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2
    metadata = json.loads(
        output.with_suffix(".metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["ngram_lengths"] == [1, 12]
    assert metadata["unique_candidates"] == 2


def test_merge_rejects_overlapping_ranges(tmp_path: Path, monkeypatch) -> None:
    first = make_aggregate(tmp_path / "first", [1, 8], "\u66f4\u7a33")
    second = make_aggregate(tmp_path / "second", [8, 12], "\u7ee7\u7eed\u6536\u7d27")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--input",
            str(first),
            "--input",
            str(second),
            "--output",
            str(tmp_path / "merged.jsonl"),
        ],
    )

    with pytest.raises(ValueError, match="overlap"):
        MODULE.main()
