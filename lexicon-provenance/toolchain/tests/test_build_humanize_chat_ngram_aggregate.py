from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "build_humanize_chat_ngram_aggregate.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_humanize_chat_ngram_aggregate", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def event_line(event: dict[str, object]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def session_meta(session_id: str = "session-1") -> dict[str, object]:
    return {
        "type": "session_meta",
        "payload": {"id": session_id, "originator": "codex"},
    }


def message(role: str, text: str) -> dict[str, object]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "output_text", "text": text}],
        },
    }


def snapshot_entry(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "top_level": "sessions",
        "session_id": "session-1",
        "originator": "codex",
    }


def test_message_ngrams_include_single_roots_and_remove_code_math() -> None:
    counts = MODULE.message_ngrams(
        "这样更稳。```python\n代码污染\n``` $公式污染$ 然后更稳"
    )

    assert counts["稳"] == 2
    assert counts["更稳"] == 2
    assert counts["这样更稳"] == 1
    assert "代码" not in counts
    assert "公式" not in counts


def test_message_ngrams_cover_complete_twelve_character_families() -> None:
    text = "abcdefghijkl"  # ASCII must not enter the Han inventory.
    han = "\u7ee7\u7eed\u628a\u5f53\u524d\u5199\u6cd5\u518d\u6536\u7d27\u4e00\u70b9"
    counts = MODULE.message_ngrams(text + han, maximum=12)

    assert len(han) == 12
    assert counts[han] == 1


def test_classification_requires_session_meta_and_excludes_derived_trees(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    real = root / "sessions" / "real.jsonl"
    derived = root / "reports" / "fake.jsonl"
    index = root / "session_index.jsonl"
    real.parent.mkdir(parents=True)
    derived.parent.mkdir(parents=True)
    real.write_text(event_line(session_meta()), encoding="utf-8")
    derived.write_text(
        event_line(session_meta("fake")) + event_line(message("assistant", "伪造会话")),
        encoding="utf-8",
    )
    index.write_text('{"thread":"not-a-session"}\n', encoding="utf-8")

    snapshot = MODULE.discover_jsonl_snapshot(root)
    included, manifest = MODULE.classify_snapshot(root, snapshot)
    by_name = {Path(row["path"]).name: row for row in manifest}

    assert [Path(row["path"]).name for row in included] == ["real.jsonl"]
    assert by_name["fake.jsonl"]["reason"] == "derived_or_fixture_tree"
    assert by_name["session_index.jsonl"]["reason"] == "no_structural_session_meta"


def test_scan_uses_frozen_length_and_only_assistant_output_text(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    session.write_text(
        event_line(session_meta())
        + event_line(message("user", "用户文本不得采集"))
        + event_line(message("assistant", "这样更稳。这样更稳"))
        + '{"type":"response_item","payload":{"role":"assistant","type":"message","content":[{"type":"output_text","text":"截断"}]}\n',
        encoding="utf-8",
    )
    entry = snapshot_entry(session)
    with session.open("a", encoding="utf-8") as handle:
        handle.write(event_line(message("assistant", "快照之后追加")))

    database = tmp_path / "ngrams.sqlite3"
    connection = MODULE.initialize_database(database)
    try:
        audits, stats = MODULE.scan_sessions(
            [entry], connection, flush_unique_phrases=1_000
        )
        rows = {
            phrase: (occurrences, coverage)
            for phrase, occurrences, coverage in connection.execute(
                "SELECT phrase, occurrences, message_coverage FROM ngrams"
            )
        }
    finally:
        connection.close()

    assert stats["assistant_output_messages"] == 1
    assert audits[0]["parse_errors"] == 1
    assert rows["稳"] == (2, 1)
    assert rows["更稳"] == (2, 1)
    assert "用户" not in rows
    assert "追加" not in rows


def test_main_writes_reproducible_structured_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / ".codex"
    session = root / "sessions" / "one.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        event_line(session_meta())
        + event_line(message("assistant", "这样更稳"))
        + event_line(message("assistant", "这样更稳")),
        encoding="utf-8",
    )
    output = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--root",
            str(root),
            "--output",
            str(output),
            "--flush-unique-phrases",
            "1000",
        ],
    )

    assert MODULE.main() == 0
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (output / "chat_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    by_phrase = {row["phrase"]: row for row in rows}

    assert metadata["structural_sessions_included"] == 1
    assert metadata["stats"]["assistant_output_messages"] == 2
    assert metadata["ngram_lengths"] == [1, 8]
    assert metadata["privacy"]["raw_message_text_written"] is False
    assert by_phrase["更稳"]["message_coverage"] == 2
    assert by_phrase["更稳"]["count"] == 2
    assert (output / "input_snapshot.json").exists()
    chat_snapshot = json.loads(
        (output / "chat_snapshot.json").read_text(encoding="utf-8")
    )
    assert len(chat_snapshot["files"]) == 1
    assert chat_snapshot["file_set_sha256"] == (
        metadata["chat_snapshot_file_set_sha256"]
    )
    assert (output / "file_manifest.csv").exists()
    assert (output / "chat_ngrams.sqlite3").exists()
