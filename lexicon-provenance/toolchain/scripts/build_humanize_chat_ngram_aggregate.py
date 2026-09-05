#!/usr/bin/env python
"""Build a byte-frozen assistant Chinese n-gram aggregate from Codex sessions.

Only structurally valid sessions and assistant ``output_text`` messages enter
the corpus.  Counts are accumulated in SQLite so the full 1-8 character
inventory does not need to fit in memory.  No message text is written out.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator


VERSION = "1.1.0"
DEFAULT_MAX_NGRAM_LENGTH = 8
SUPPORTED_MAX_NGRAM_LENGTH = 12
HAN_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```|~~~[\s\S]*?~~~")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
URL_PATH_RE = re.compile(
    r"(?:https?://\S+|[A-Za-z]:\\[^\s，。；！？]+|/(?:[^\s/]+/){2,}[^\s]*)"
)
TEX_COMMENT_RE = re.compile(r"(?m)(?<!\\)%.*$")
TEX_DISPLAY_MATH_RE = re.compile(
    r"\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$"
)
TEX_INLINE_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]*?(?<!\\)\$")
TEX_ENV_RE = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|"
    r"tikzpicture|lstlisting|verbatim)\}[\s\S]*?"
    r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?|"
    r"tikzpicture|lstlisting|verbatim)\}"
)
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]\n]*\])?")
UNIT_SPLIT_RE = re.compile(r"(?:[。！？!?；;：:]|\r?\n)+")
MOJIBAKE_RE = re.compile(r"(?:锟斤拷|馃|闂|绾|瀹|鍙|浜|鐨|鈥|銆){3,}")

# These trees contain derived reports, fixtures, and scanner outputs rather
# than first-party Codex sessions.  They remain visible in the file manifest.
DERIVED_TOP_LEVEL = frozenset({"reports", "tmp", ".tmp", "skills", "plugins"})
QUICK_SESSION_META = b"session_meta"
QUICK_RESPONSE_ITEM = b"response_item"
QUICK_OUTPUT_TEXT = b"output_text"
QUICK_ASSISTANT = b"assistant"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def snapshot_file_set_sha256(files: Iterable[dict[str, Any]]) -> str:
    rows = sorted(
        (
            normalized_path(Path(item["path"])),
            int(item["size"]),
            int(item["mtime_ns"]),
        )
        for item in files
    )
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relative_top_level(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return ""
    return relative.parts[0] if relative.parts else ""


def discover_jsonl_snapshot(root: Path) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for current, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(".jsonl"):
                continue
            path = Path(current) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot.append(
                {
                    "path": str(path),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "top_level": relative_top_level(root, path),
                }
            )
    snapshot.sort(key=lambda item: normalized_path(Path(item["path"])))
    return snapshot


def load_snapshot(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError(f"snapshot has no files list: {path}")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(files):
        if not isinstance(item, dict) or not {"path", "size", "mtime_ns"} <= set(item):
            raise ValueError(f"invalid snapshot entry {index}: {path}")
        normalized.append(
            {
                "path": str(item["path"]),
                "size": int(item["size"]),
                "mtime_ns": int(item["mtime_ns"]),
                "top_level": str(item.get("top_level", "")),
            }
        )
    return normalized, payload


def iter_frozen_lines(entry: dict[str, Any]) -> Iterator[bytes]:
    remaining = int(entry["size"])
    with Path(entry["path"]).open("rb") as handle:
        while remaining > 0:
            raw = handle.readline(remaining)
            if not raw:
                break
            remaining -= len(raw)
            yield raw


def session_identity(entry: dict[str, Any], max_lines: int = 64) -> tuple[str | None, str]:
    try:
        for line_number, raw in enumerate(iter_frozen_lines(entry), start=1):
            if line_number > max_lines:
                break
            if QUICK_SESSION_META not in raw:
                continue
            try:
                event = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            payload = event.get("payload")
            if event.get("type") != "session_meta" or not isinstance(payload, dict):
                continue
            session_id = payload.get("id")
            if isinstance(session_id, str) and session_id:
                return session_id, str(payload.get("originator") or "unknown")
    except OSError:
        return None, "unreadable"
    return None, "missing_session_meta"


def classify_snapshot(
    root: Path, snapshot: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for entry in snapshot:
        item = dict(entry)
        top_level = item.get("top_level") or relative_top_level(root, Path(item["path"]))
        item["top_level"] = top_level
        if top_level in DERIVED_TOP_LEVEL:
            item.update(
                session_id="",
                originator="",
                recognition="EXCLUDED",
                reason="derived_or_fixture_tree",
            )
            manifest.append(item)
            continue
        session_id, originator = session_identity(item)
        if session_id is None:
            item.update(
                session_id="",
                originator=originator,
                recognition="EXCLUDED",
                reason="no_structural_session_meta",
            )
            manifest.append(item)
            continue
        item.update(
            session_id=session_id,
            originator=originator,
            recognition="CANDIDATE",
            reason="structural_session_meta",
        )
        candidates.append(item)
        manifest.append(item)

    by_session: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_session.setdefault(str(item["session_id"]), []).append(item)
    selected: list[dict[str, Any]] = []
    for session_id, group in by_session.items():
        winner = max(
            group,
            key=lambda item: (
                int(item["size"]),
                int(item["mtime_ns"]),
                normalized_path(Path(item["path"])),
            ),
        )
        winner["recognition"] = "INCLUDED"
        winner["reason"] = "unique_structural_session"
        selected.append(winner)
        for item in group:
            if item is winner:
                continue
            item["recognition"] = "EXCLUDED"
            item["reason"] = f"duplicate_session_id:{session_id}"
    selected.sort(key=lambda item: normalized_path(Path(item["path"])))
    return selected, manifest


def strip_non_prose(text: str) -> str:
    text = CODE_FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = URL_PATH_RE.sub(" ", text)
    text = TEX_COMMENT_RE.sub("", text)
    text = TEX_ENV_RE.sub(" ", text)
    text = TEX_DISPLAY_MATH_RE.sub(" ", text)
    text = TEX_INLINE_MATH_RE.sub(" ", text)
    text = TEX_COMMAND_RE.sub(" ", text)
    return text.replace("{", " ").replace("}", " ")


def prose_han_runs(text: str) -> Iterator[str]:
    cleaned = strip_non_prose(text)
    for unit in UNIT_SPLIT_RE.split(cleaned):
        for run in HAN_RUN_RE.findall(unit):
            yield run


def extract_assistant_text(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return ""
    if (
        event.get("type") != "response_item"
        or payload.get("type") != "message"
        or payload.get("role") != "assistant"
    ):
        return ""
    parts: list[str] = []
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    for item in content:
        if (
            isinstance(item, dict)
            and item.get("type") == "output_text"
            and isinstance(item.get("text"), str)
        ):
            parts.append(item["text"])
    return "\n".join(parts)


def message_ngrams(
    text: str, *, minimum: int = 1, maximum: int = DEFAULT_MAX_NGRAM_LENGTH
) -> Counter[str]:
    result: Counter[str] = Counter()
    for run in prose_han_runs(text):
        upper = min(maximum, len(run))
        for length in range(minimum, upper + 1):
            for start in range(len(run) - length + 1):
                result[run[start : start + length]] += 1
    return result


def initialize_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA cache_size=-262144")
    connection.execute(
        """
        CREATE TABLE ngrams (
            phrase TEXT PRIMARY KEY,
            occurrences INTEGER NOT NULL,
            message_coverage INTEGER NOT NULL
        ) WITHOUT ROWID
        """
    )
    return connection


def flush_counts(
    connection: sqlite3.Connection,
    occurrences: Counter[str],
    coverage: Counter[str],
) -> int:
    if not occurrences:
        return 0
    rows = [
        (phrase, count, coverage.get(phrase, 0))
        for phrase, count in occurrences.items()
    ]
    with connection:
        connection.executemany(
            """
            INSERT INTO ngrams(phrase, occurrences, message_coverage)
            VALUES (?, ?, ?)
            ON CONFLICT(phrase) DO UPDATE SET
              occurrences = occurrences + excluded.occurrences,
              message_coverage = message_coverage + excluded.message_coverage
            """,
            rows,
        )
    occurrences.clear()
    coverage.clear()
    return len(rows)


def scan_sessions(
    entries: list[dict[str, Any]],
    connection: sqlite3.Connection,
    *,
    flush_unique_phrases: int,
    maximum_ngram_length: int = DEFAULT_MAX_NGRAM_LENGTH,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    chunk_occurrences: Counter[str] = Counter()
    chunk_coverage: Counter[str] = Counter()
    audits: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    for file_number, entry in enumerate(entries, start=1):
        digest = hashlib.sha256()
        audit: Counter[str] = Counter()
        audit["frozen_bytes"] = int(entry["size"])
        try:
            for raw in iter_frozen_lines(entry):
                digest.update(raw)
                audit["lines"] += 1
                if (
                    QUICK_RESPONSE_ITEM not in raw
                    or QUICK_OUTPUT_TEXT not in raw
                    or QUICK_ASSISTANT not in raw
                ):
                    continue
                audit["response_lines_considered"] += 1
                try:
                    event = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    audit["parse_errors"] += 1
                    continue
                text = extract_assistant_text(event)
                if not text:
                    continue
                if "\ufffd" in text or MOJIBAKE_RE.search(text):
                    audit["garbled_messages"] += 1
                    continue
                local = message_ngrams(text, maximum=maximum_ngram_length)
                if not local:
                    audit["assistant_messages_without_han"] += 1
                    continue
                audit["assistant_output_messages"] += 1
                audit["ngram_occurrences"] += sum(local.values())
                chunk_occurrences.update(local)
                chunk_coverage.update(local.keys())
                if len(chunk_occurrences) >= flush_unique_phrases:
                    totals["sqlite_rows_flushed"] += flush_counts(
                        connection, chunk_occurrences, chunk_coverage
                    )
                    totals["sqlite_flushes"] += 1
        except OSError:
            audit["read_errors"] += 1

        audit_row = dict(entry)
        audit_row.update(dict(audit))
        audit_row["sha256_frozen_prefix"] = digest.hexdigest()
        audit_row["recognition"] = (
            "INCLUDED" if not audit["read_errors"] else "READ_ERROR"
        )
        audit_row["reason"] = (
            "assistant_output_scanned" if not audit["read_errors"] else "read_error"
        )
        audits.append(audit_row)
        totals.update(audit)
        totals["session_files_scanned"] += 1
        if file_number % 25 == 0 or file_number == len(entries):
            print(
                f"chat scan {file_number}/{len(entries)}; "
                f"assistant messages={totals['assistant_output_messages']}; "
                f"pending phrases={len(chunk_occurrences)}",
                flush=True,
            )

    totals["sqlite_rows_flushed"] += flush_counts(
        connection, chunk_occurrences, chunk_coverage
    )
    totals["sqlite_flushes"] += 1
    return audits, dict(totals)


def write_manifest(
    path: Path,
    snapshot_manifest: list[dict[str, Any]],
    included_audits: list[dict[str, Any]],
) -> None:
    by_path = {normalized_path(Path(row["path"])): row for row in included_audits}
    rows: list[dict[str, Any]] = []
    for item in snapshot_manifest:
        row = dict(item)
        audit = by_path.get(normalized_path(Path(item["path"])))
        if audit:
            row.update(audit)
        rows.append(row)
    fieldnames = [
        "path",
        "top_level",
        "size",
        "mtime_ns",
        "session_id",
        "originator",
        "recognition",
        "reason",
        "frozen_bytes",
        "sha256_frozen_prefix",
        "lines",
        "response_lines_considered",
        "assistant_output_messages",
        "assistant_messages_without_han",
        "garbled_messages",
        "parse_errors",
        "read_errors",
        "ngram_occurrences",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_aggregate(
    connection: sqlite3.Connection,
    path: Path,
    *,
    assistant_messages: int,
) -> int:
    connection.execute(
        "CREATE INDEX IF NOT EXISTS ngrams_rank ON ngrams(message_coverage DESC, occurrences DESC)"
    )
    rows = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        cursor = connection.execute(
            """
            SELECT phrase, occurrences, message_coverage
            FROM ngrams
            ORDER BY message_coverage DESC, occurrences DESC, phrase ASC
            """
        )
        for phrase, occurrences, coverage in cursor:
            payload = {
                "phrase": phrase,
                "count": occurrences,
                "message_coverage": coverage,
                "coverage_rate": round(coverage / max(1, assistant_messages), 8),
            }
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            rows += 1
            if rows % 1_000_000 == 0:
                print(f"aggregate export rows={rows}", flush=True)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reuse-snapshot",
        type=Path,
        help="Reuse byte lengths from an earlier input_snapshot.json.",
    )
    parser.add_argument("--limit-files", type=int)
    parser.add_argument("--flush-unique-phrases", type=int, default=400_000)
    parser.add_argument(
        "--max-ngram-length",
        type=int,
        default=DEFAULT_MAX_NGRAM_LENGTH,
        help="Largest contiguous Han n-gram to aggregate (2-12).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit_files is not None and args.limit_files < 1:
        raise SystemExit("--limit-files must be positive")
    if args.flush_unique_phrases < 1_000:
        raise SystemExit("--flush-unique-phrases must be at least 1000")
    if not 2 <= args.max_ngram_length <= SUPPORTED_MAX_NGRAM_LENGTH:
        raise SystemExit("--max-ngram-length must be between 2 and 12")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output}")

    started_at = utc_now()
    if args.reuse_snapshot:
        snapshot, prior = load_snapshot(args.reuse_snapshot)
        snapshot_source = str(args.reuse_snapshot)
        original_created_at = prior.get("created_at")
    else:
        snapshot = discover_jsonl_snapshot(args.root)
        snapshot_source = None
        original_created_at = started_at
    snapshot_payload = {
        "schema_version": "humanize-chat-snapshot/v1",
        "created_at": started_at,
        "original_created_at": original_created_at,
        "root": str(args.root),
        "reused_from": snapshot_source,
        "files": snapshot,
    }
    snapshot_path = args.output / "input_snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    included, manifest = classify_snapshot(args.root, snapshot)
    if args.limit_files is not None:
        allowed = {
            normalized_path(Path(item["path"]))
            for item in included[: args.limit_files]
        }
        for item in manifest:
            if (
                item.get("recognition") == "INCLUDED"
                and normalized_path(Path(item["path"])) not in allowed
            ):
                item["recognition"] = "EXCLUDED"
                item["reason"] = "limit_files"
        included = included[: args.limit_files]

    chat_snapshot_payload = {
        "schema_version": "humanize-chat-structural-snapshot/v1",
        "created_at": started_at,
        "original_created_at": original_created_at,
        "root": str(args.root),
        "source_input_snapshot": str(snapshot_path),
        "file_set_sha256": snapshot_file_set_sha256(included),
        "files": included,
    }
    chat_snapshot_path = args.output / "chat_snapshot.json"
    chat_snapshot_path.write_text(
        json.dumps(chat_snapshot_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    database_path = args.output / "chat_ngrams.sqlite3"
    connection = initialize_database(database_path)
    try:
        audits, stats = scan_sessions(
            included,
            connection,
            flush_unique_phrases=args.flush_unique_phrases,
            maximum_ngram_length=args.max_ngram_length,
        )
        aggregate_path = args.output / "chat_candidates.jsonl"
        unique_candidates = export_aggregate(
            connection,
            aggregate_path,
            assistant_messages=int(stats.get("assistant_output_messages", 0)),
        )
    finally:
        connection.close()

    write_manifest(args.output / "file_manifest.csv", manifest, audits)
    metadata = {
        "schema_version": "humanize-chat-ngram-run/v1",
        "version": VERSION,
        "started_at": started_at,
        "finished_at": utc_now(),
        "root": str(args.root),
        "snapshot": str(snapshot_path),
        "snapshot_sha256": sha256_path(snapshot_path),
        "snapshot_files": len(snapshot),
        "chat_snapshot": str(chat_snapshot_path),
        "chat_snapshot_sha256": sha256_path(chat_snapshot_path),
        "chat_snapshot_file_set_sha256": snapshot_file_set_sha256(included),
        "structural_sessions_included": len(included),
        "structural_files_excluded": len(snapshot) - len(included),
        "ngram_lengths": [1, args.max_ngram_length],
        "unique_candidates": unique_candidates,
        "aggregate": str(aggregate_path),
        "aggregate_sha256": sha256_path(aggregate_path),
        "database": str(database_path),
        "stats": stats,
        "privacy": {
            "raw_message_text_written": False,
            "assistant_output_text_only": True,
            "code_and_math_removed_before_ngrams": True,
        },
        "script_sha256": sha256_path(Path(__file__)),
    }
    (args.output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
