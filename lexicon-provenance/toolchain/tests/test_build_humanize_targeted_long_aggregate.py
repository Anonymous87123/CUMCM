from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "build_humanize_targeted_long_aggregate.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_humanize_targeted_long_aggregate", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def event_line(event: dict[str, object]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def assistant_message(text: str) -> dict[str, object]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        },
    }


def test_targeted_long_scan_keeps_root_family_and_drops_unrelated_window(
    tmp_path: Path, monkeypatch
) -> None:
    aggregate = tmp_path / "broad.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 30, "message_coverage": 20},
                ensure_ascii=False,
            )
            for phrase in (
                "\u6536\u7d27",
                "\u7ee7\u7eed\u6536\u7d27",
                "\u8fdb\u4e00\u6b65\u6536\u7d27",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    lexicon = tmp_path / "lexicon.json"
    lexicon.write_text(
        json.dumps(
            {
                "strict_release": {
                    "discovery_root_only_exact": [],
                    "short_literal_exact": ["\u6536\u7d27"],
                    "high_confidence_style_core_exact": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    session = tmp_path / "session.jsonl"
    wanted = "\u5fc5\u987b\u8fdb\u4e00\u6b65\u6536\u7d27\u4e00\u70b9"
    unrelated = "\u5929\u5730\u7384\u9ec4\u5b87\u5b99\u6d2a\u8352\u65e5\u6708\u76c8\u6634"
    session.write_text(
        event_line(assistant_message(wanted + "\u3002" + unrelated)),
        encoding="utf-8",
    )
    stat = session.stat()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": "test",
                "files": [
                    {
                        "path": str(session),
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--aggregate",
            str(aggregate),
            "--chat-snapshot",
            str(snapshot),
            "--lexicon",
            str(lexicon),
            "--output",
            str(output),
            "--flush-unique-phrases",
            "1000",
        ],
    )

    assert MODULE.main() == 0
    rows = [
        json.loads(line)
        for line in (output / "targeted_long_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    phrases = {row["phrase"] for row in rows}
    assert wanted in phrases
    assert unrelated not in phrases
    metadata = json.loads(
        (output / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["ngram_lengths"] == [9, 12]
    assert metadata["selected_roots"] >= 1


def test_arbitrary_edge_window_is_not_a_complete_long_family() -> None:
    root = "\u6536\u7d27"
    text = "\u5929\u5730\u7384\u9ec4\u5b87\u5b99\u6d2a" + root

    rows = MODULE.targeted_long_ngrams(text, {root}, {root})

    assert rows == {}


def test_targeted_runs_preserve_han_message_denominator() -> None:
    root = "\u6536\u7d27"
    wanted = "\u5fc5\u987b\u8fdb\u4e00\u6b65\u6536\u7d27\u4e00\u70b9"

    assert MODULE.targeted_long_ngrams_from_runs((), {root}, {root}) == {}
    assert MODULE.targeted_long_ngrams_from_runs((wanted,), {root}, {root}) == {
        wanted: 1
    }


def test_immediate_extension_dominance_marks_clipped_root() -> None:
    metrics = MODULE.extension_metrics(
        MODULE.Counter({"right/\u7406": 95, "right/\u7cfb": 3, "left/\u5b50": 2}),
        exact_coverage=100,
    )

    assert metrics["dominant_right_extension"] == "\u7406"
    assert metrics["right_extension_dominance"] == 0.95
    assert metrics["immediate_extension_fragment"] is True


def test_baseline_roots_do_not_create_cross_boundary_windows(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "entries": [
                    {"phrase": "\u5f53\u524d\u4f1a\u8bdd"},
                    {"phrase": "\u6536\u7d27"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert MODULE.load_baseline_roots(inventory) == {"\u6536\u7d27"}


def test_roots_only_writes_audit_without_scanning_chat(
    tmp_path: Path, monkeypatch
) -> None:
    aggregate = tmp_path / "broad.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 30, "message_coverage": 20},
                ensure_ascii=False,
            )
            for phrase in ("\u6536\u7d27", "\u7ee7\u7eed\u6536\u7d27", "\u8fdb\u4e00\u6b65\u6536\u7d27")
        )
        + "\n",
        encoding="utf-8",
    )
    lexicon = tmp_path / "lexicon.json"
    lexicon.write_text(
        json.dumps(
            {
                "strict_release": {
                    "discovery_root_only_exact": ["\u6536\u7d27"],
                    "short_literal_exact": [],
                    "high_confidence_style_core_exact": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    session = tmp_path / "session.jsonl"
    session.write_text(event_line(assistant_message("\u4e0d\u5e94\u8be5\u8bfb\u5230\u8fd9\u91cc")), encoding="utf-8")
    stat = session.stat()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": "test",
                "files": [
                    {"path": str(session), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--aggregate",
            str(aggregate),
            "--chat-snapshot",
            str(snapshot),
            "--lexicon",
            str(lexicon),
            "--output",
            str(output),
            "--roots-only",
        ],
    )

    assert MODULE.main() == 0
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["roots_only"] is True
    assert metadata["selected_roots"] >= 1
    assert not (output / "targeted_long_candidates.jsonl").exists()
    assert not (output / "targeted_long_ngrams.sqlite3").exists()
