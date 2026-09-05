#!/usr/bin/env python
"""Build an auditable, redacted corpus from Codex JSONL logs and MD/TEX trees.

The collection layer deliberately does not infer authorship or writing style.  It
only preserves a reviewable inventory and prose-oriented text views for later
human analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


VERSION = "1.1.0"
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
CODE_FENCE_RE = re.compile(r"(^|\n)```.*?```", re.S)
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.S)
MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
MARKDOWN_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
WINDOWS_MD_PATH_RE = re.compile(r"(?i)(?:[a-z]:[\\/])[^<>:\"|?*\r\n`']*?\.md\b")
RELATIVE_MD_PATH_RE = re.compile(r"(?i)(?<![\w.])(?:\.{1,2}[\\/])[^<>:\"|?*\r\n`']*?\.md\b")
BARE_MD_PATH_RE = re.compile(r"(?i)(?<![\w\\/.-])[\w][\w ._-]{0,160}\.md\b")
WINDOWS_DOCUMENT_PATH_RE = re.compile(r"(?i)(?:[a-z]:[\\/])[^<>:\"|?*\r\n`']*?\.(?:md|tex)\b")
RELATIVE_DOCUMENT_PATH_RE = re.compile(r"(?i)(?<![\w.])(?:\.{1,2}[\\/])[^<>:\"|?*\r\n`']*?\.(?:md|tex)\b")
BARE_DOCUMENT_PATH_RE = re.compile(r"(?i)(?<![\w\\/.-])[\w][\w ._-]{0,160}\.(?:md|tex)\b")
TEX_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
TEX_DISPLAY_MATH_RE = re.compile(r"\\\[.*?\\\]|\$\$.*?\$\$", re.S)
TEX_ENVIRONMENT_RE = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|aligned|gather\*?|figure\*?|table\*?|tikzpicture|lstlisting|verbatim)\}.*?"
    r"\\end\{(?:equation\*?|align\*?|aligned|gather\*?|figure\*?|table\*?|tikzpicture|lstlisting|verbatim)\}",
    re.S,
)
TEX_HEADING_RE = re.compile(r"\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?(?:\[[^\]]*\])?\{([^{}]+)\}")
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")

REDACTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.I | re.S)),
    # Real API keys include an opaque identifier with digits; requiring one avoids
    # redacting ordinary skill filenames such as `sk-abstraction-and-chart-selection`.
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("CONNECTION_STRING", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s`]+", re.I)),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b", re.I)),
    ("PASSWORD", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*[^\s,;]+")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d[- ]?\d{4}[- ]?\d{4}(?!\d)")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("HOME_PATH", re.compile(r"(?i)(?:[A-Z]:\\Users\\[^\\\s`]+|/home/[^/\s`]+|/Users/[^/\s`]+)(?:[\\/][^\s`]+)*")),
]


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def short_hash(value: str) -> str:
    return hashlib.blake2b(value.encode("utf-8"), digest_size=10).hexdigest()


def redact_sensitive(text: str) -> str:
    for label, pattern in REDACTION_RULES:
        text = pattern.sub(f"[{label}]", text)
    return text


def decode_text(data: bytes) -> tuple[str | None, str]:
    if b"\x00" in data:
        return None, "binary"
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return None, "undecodable"


def extract_markdown_paths(text: str) -> list[str]:
    values = []
    for pattern in (WINDOWS_MD_PATH_RE, RELATIVE_MD_PATH_RE, BARE_MD_PATH_RE):
        values.extend(match.group(0).strip() for match in pattern.finditer(text))
    return list(dict.fromkeys(value for value in values if value.lower().endswith(".md")))


def extract_document_paths(text: str) -> list[str]:
    """Return literal MD/TEX mentions without treating a mention as authorship."""
    values = []
    for pattern in (WINDOWS_DOCUMENT_PATH_RE, RELATIVE_DOCUMENT_PATH_RE, BARE_DOCUMENT_PATH_RE):
        values.extend(match.group(0).strip() for match in pattern.finditer(text))
    return list(dict.fromkeys(value for value in values if value.lower().endswith((".md", ".tex"))))


def sentence_records(text: str) -> list[str]:
    return [segment.strip() for segment in SENTENCE_RE.findall(text) if HAN_RE.search(segment) or len(segment.strip()) >= 16]


def extract_markdown_document(source: str) -> dict[str, Any]:
    without_front_matter = FRONT_MATTER_RE.sub("", source)
    without_code = CODE_FENCE_RE.sub("\n", without_front_matter)
    headings: list[str] = []
    paragraphs: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            paragraph = re.sub(r"\s+", " ", " ".join(pending)).strip()
            if paragraph:
                paragraphs.append(paragraph)
            pending.clear()

    for raw_line in without_code.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        heading = MARKDOWN_HEADING_RE.match(line)
        if heading:
            flush()
            headings.append(heading.group(1).strip())
            continue
        if MARKDOWN_TABLE_DIVIDER_RE.match(line):
            continue
        line = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        line = re.sub(r"^>\s?", "", line)
        line = line.replace("|", " ")
        if line:
            pending.append(line)
    flush()
    prose = "\n\n".join(paragraphs)
    sentences = [sentence for paragraph in paragraphs for sentence in sentence_records(paragraph)]
    return {"headings": headings, "paragraphs": paragraphs, "sentences": sentences, "prose": prose, "code_chars": len(source) - len(without_code)}


def extract_tex_document(source: str) -> dict[str, Any]:
    """Make a prose view of a TeX document while excluding equations and code-like blocks.

    This is an indexing view, not a TeX renderer: headings and ordinary prose are
    preserved for human reading, while mathematical display environments are not
    allowed to dominate the language corpus.
    """
    without_math = TEX_DISPLAY_MATH_RE.sub("\n", source)
    without_math = TEX_ENVIRONMENT_RE.sub("\n", without_math)
    headings = [re.sub(r"\s+", " ", value).strip() for value in TEX_HEADING_RE.findall(without_math)]
    paragraphs: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            paragraph = re.sub(r"\s+", " ", " ".join(pending)).strip()
            if paragraph:
                paragraphs.append(paragraph)
            pending.clear()

    for raw_line in without_math.splitlines():
        line = TEX_COMMENT_RE.sub("", raw_line).strip()
        if not line:
            flush()
            continue
        if TEX_HEADING_RE.fullmatch(line):
            flush()
            continue
        line = line.replace(r"\\", " ")
        line = re.sub(r"\$[^$]*\$", " ", line)
        line = TEX_COMMAND_RE.sub("", line)
        line = line.replace("{", " ").replace("}", " ").replace("~", " ")
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            pending.append(line)
    flush()
    prose = "\n\n".join(paragraphs)
    sentences = [sentence for paragraph in paragraphs for sentence in sentence_records(paragraph)]
    return {"headings": headings, "paragraphs": paragraphs, "sentences": sentences, "prose": prose, "code_chars": len(source) - len(without_math)}


def extract_output_text(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "output_text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def flatten_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from flatten_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from flatten_strings(child)


def scan_jsonl_file(path: Path, timezone_name: str = "Asia/Shanghai") -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    metadata = {"session_id": None, "originator": "unknown", "source": "unknown", "model": "unknown", "personality": "unknown"}
    audit = {"path": str(path), "json_errors": 0, "records": 0, "assistant_messages": 0, "file_hash": ""}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            digest.update(raw_line)
            audit["records"] += 1
            try:
                line_text = raw_line.decode("utf-8")
                event = json.loads(line_text)
            except (UnicodeDecodeError, json.JSONDecodeError):
                audit["json_errors"] += 1
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if event.get("type") == "session_meta":
                metadata["session_id"] = payload.get("id") or metadata["session_id"]
                metadata["originator"] = payload.get("originator") or metadata["originator"]
                metadata["source"] = payload.get("source") or metadata["source"]
            elif event.get("type") == "turn_context":
                metadata["model"] = payload.get("model") or metadata["model"]
                metadata["personality"] = payload.get("personality") or metadata["personality"]

            role = str(payload.get("role") or "")
            # Keep literal path mentions as provenance hints only.  A path in a log
            # may have come from a prompt, tool call or third-party document.
            for mentioned_path in extract_document_paths(line_text) if (b".md" in raw_line.lower() or b".tex" in raw_line.lower()) else []:
                mentioned_path = mentioned_path.replace("\\\\", "\\")
                confidence = "explicit_assistant_output" if role == "assistant" and event.get("type") == "response_item" else "referenced_in_log"
                provenance.append(
                    {
                        "log_path": str(path),
                        "line_number": line_number,
                        "session_hash": short_hash(str(metadata["session_id"] or path)),
                        "role": role or "none",
                        "event_type": event.get("type", "unknown"),
                        "mentioned_path": mentioned_path,
                        "document_format": Path(mentioned_path).suffix.lower().lstrip("."),
                        "confidence": confidence,
                    }
                )
            if event.get("type") == "response_item" and payload.get("type") == "message" and role == "assistant":
                text = extract_output_text(payload)
                if text and HAN_RE.search(text):
                    timestamp = event.get("timestamp")
                    date = "unknown"
                    if isinstance(timestamp, str):
                        try:
                            date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(ZoneInfo(timezone_name)).date().isoformat()
                        except ValueError:
                            pass
                    messages.append(
                        {
                            "record_id": short_hash(f"{path}:{line_number}"),
                            "session_hash": short_hash(str(metadata["session_id"] or path)),
                            "date": date,
                            "model": str(metadata["model"]),
                            "personality": str(metadata["personality"]),
                            "originator": str(metadata["originator"]),
                            "source": str(metadata["source"]),
                            "phase": str(payload.get("phase") or "unspecified"),
                            "text": redact_sensitive(text),
                        }
                    )
                    audit["assistant_messages"] += 1
    audit["file_hash"] = digest.hexdigest()
    return messages, provenance, audit


def scan_document_tree(root: Path, source_label: str, extension: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    paragraphs: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []
    seen_hashes: dict[str, str] = {}
    extractor = extract_markdown_document if extension == ".md" else extract_tex_document
    for path in sorted(root.rglob(f"*{extension}")):
        base = {"path": str(path), "source_label": source_label, "document_format": extension.lstrip("."), "size": None, "mtime_ns": None, "sha256": "", "status": "unknown", "encoding": "", "duplicate_of": ""}
        try:
            stat = path.stat()
            base["size"] = stat.st_size
            base["mtime_ns"] = stat.st_mtime_ns
            data = path.read_bytes()
        except OSError as error:
            base["status"] = "unreadable"
            base["error"] = type(error).__name__
            rows.append(base)
            continue
        base["sha256"] = sha256_bytes(data)
        if not data.strip():
            base["status"] = "empty"
            rows.append(base)
            continue
        text, encoding = decode_text(data)
        base["encoding"] = encoding
        if text is None:
            base["status"] = encoding
            rows.append(base)
            continue
        document = extractor(text)
        base.update(
            {
                "status": "readable",
                "duplicate_of": seen_hashes.get(base["sha256"], ""),
                "headings": len(document["headings"]),
                "paragraph_count": len(document["paragraphs"]),
                "sentence_count": len(document["sentences"]),
                "prose_chars": len(document["prose"]),
                "han_chars": len(HAN_RE.findall(document["prose"])),
                "code_chars": document["code_chars"],
            }
        )
        if not base["duplicate_of"]:
            seen_hashes[base["sha256"]] = str(path)
        document_id = short_hash(str(path))
        for index, paragraph in enumerate(document["paragraphs"], start=1):
            paragraphs.append({"document_id": document_id, "path": str(path), "source_label": source_label, "document_format": extension.lstrip("."), "paragraph_index": index, "text": redact_sensitive(paragraph)})
        for index, sentence in enumerate(document["sentences"], start=1):
            sentences.append({"document_id": document_id, "path": str(path), "source_label": source_label, "document_format": extension.lstrip("."), "sentence_index": index, "text": redact_sensitive(sentence)})
        rows.append(base)
    return rows, paragraphs, sentences


def scan_markdown_tree(root: Path, source_label: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Backward-compatible Markdown-only entry point used by existing callers."""
    return scan_document_tree(root, source_label, ".md")


def scan_tex_tree(root: Path, source_label: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return scan_document_tree(root, source_label, ".tex")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(codex_root: Path, d_root: Path, output: Path, timezone_name: str = "Asia/Shanghai") -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    jsonl_files = sorted(codex_root.rglob("*.jsonl"))
    jsonl_manifest: list[dict[str, Any]] = []
    chat_count = 0
    provenance_count = 0
    # JSONL is the large input (about 10 GB). Persist each file's records before
    # continuing, so the full conversation corpus is never accumulated in memory.
    with (output / "chat_messages.jsonl").open("w", encoding="utf-8") as chat_handle, (output / "document_provenance.jsonl").open("w", encoding="utf-8") as provenance_handle:
        for path in jsonl_files:
            messages, references, audit = scan_jsonl_file(path, timezone_name)
            for message in messages:
                chat_handle.write(json.dumps(message, ensure_ascii=False) + "\n")
                chat_count += 1
            for reference in references:
                provenance_handle.write(json.dumps(reference, ensure_ascii=False) + "\n")
                provenance_count += 1
            chat_handle.flush()
            provenance_handle.flush()
            stat = path.stat()
            jsonl_manifest.append({"path": str(path), "source_label": "codex_jsonl", "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, **audit})

    # Preserve the original Markdown outputs for backward compatibility, and add
    # a separate combined MD/TEX academic-document inventory for the core review.
    codex_md_rows, codex_paragraphs, codex_sentences = scan_markdown_tree(codex_root, "codex_markdown")
    d_md_rows, d_paragraphs, d_sentences = scan_markdown_tree(d_root, "d_drive_markdown")
    codex_tex_rows, codex_tex_paragraphs, codex_tex_sentences = scan_tex_tree(codex_root, "codex_tex")
    d_tex_rows, d_tex_paragraphs, d_tex_sentences = scan_tex_tree(d_root, "d_drive_tex")
    write_jsonl(output / "md_paragraphs.jsonl", [*codex_paragraphs, *d_paragraphs])
    write_jsonl(output / "md_sentences.jsonl", [*codex_sentences, *d_sentences])
    write_jsonl(output / "tex_paragraphs.jsonl", [*codex_tex_paragraphs, *d_tex_paragraphs])
    write_jsonl(output / "tex_sentences.jsonl", [*codex_tex_sentences, *d_tex_sentences])
    write_jsonl(output / "academic_document_paragraphs.jsonl", [*codex_paragraphs, *d_paragraphs, *codex_tex_paragraphs, *d_tex_paragraphs])
    write_jsonl(output / "academic_document_sentences.jsonl", [*codex_sentences, *d_sentences, *codex_tex_sentences, *d_tex_sentences])
    write_csv(output / "jsonl_manifest.csv", jsonl_manifest)
    write_csv(output / "markdown_manifest.csv", [*codex_md_rows, *d_md_rows])
    write_csv(output / "tex_manifest.csv", [*codex_tex_rows, *d_tex_rows])
    write_csv(output / "academic_document_manifest.csv", [*codex_md_rows, *d_md_rows, *codex_tex_rows, *d_tex_rows])
    audit = {
        "version": VERSION,
        "created_at": now_utc(),
        "codex_root": str(codex_root),
        "d_root": str(d_root),
        "jsonl_files": len(jsonl_files),
        "chat_messages": chat_count,
        "document_path_references": provenance_count,
        "codex_markdown_files": len(codex_md_rows),
        "d_markdown_files": len(d_md_rows),
        "codex_tex_files": len(codex_tex_rows),
        "d_tex_files": len(d_tex_rows),
        "markdown_readable": sum(row["status"] == "readable" for row in [*codex_md_rows, *d_md_rows]),
        "markdown_unreadable": sum(row["status"] == "unreadable" for row in [*codex_md_rows, *d_md_rows]),
        "markdown_empty": sum(row["status"] == "empty" for row in [*codex_md_rows, *d_md_rows]),
        "paragraphs": len(codex_paragraphs) + len(d_paragraphs),
        "sentences": len(codex_sentences) + len(d_sentences),
        "tex_paragraphs": len(codex_tex_paragraphs) + len(d_tex_paragraphs),
        "tex_sentences": len(codex_tex_sentences) + len(d_tex_sentences),
    }
    (output / "corpus_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-root", type=Path, required=True)
    parser.add_argument("--d-root", type=Path, default=Path("D:\\"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = run(args.codex_root, args.d_root, args.output, args.timezone)
    print(json.dumps(audit, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
