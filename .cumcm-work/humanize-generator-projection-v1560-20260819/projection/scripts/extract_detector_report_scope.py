#!/usr/bin/env python3
"""Extract style-editing scope hints from a static detector HTML report.

The parser never opens links or executes active content. Detector annotations
are only candidate scope selectors. A fragment is usable automatically only
when it has one exact match in the normalized source document.
"""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "1.1.0"
MARKER_KEYWORDS = (
    "aigc",
    "risk",
    "highlight",
    "suspicious",
    "detected",
    "flagged",
)
UI_SCORE_METADATA_RE = re.compile(
    r"^(?=.{1,80}$)(?:综合|总体|文本|AIGC|AI)?(?:风险|概率|评分|分数|占比|疑似率)"
    r"[^。！？!?]{0,24}?(?:\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?分?)$",
    re.IGNORECASE,
)
IGNORED_TAGS = {"script", "style", "noscript"}
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


@dataclass
class _Candidate:
    sequence: int
    tag: str
    depth: int
    line: int
    column: int
    triggers: list[str]
    parts: list[str] = field(default_factory=list)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    """Normalize compatibility characters and collapse whitespace."""
    return _collapse_whitespace(unicodedata.normalize("NFKC", text))


def _normalization_with_offsets(text: str) -> tuple[str, list[int]]:
    """Return normalized source text and a normalized-to-original offset map."""
    output: list[str] = []
    offsets: list[int] = []
    pending_space: int | None = None
    for original_offset, raw_character in enumerate(text):
        for character in unicodedata.normalize("NFKC", raw_character):
            if character.isspace():
                if output and output[-1] != " ":
                    pending_space = original_offset
                continue
            if pending_space is not None:
                output.append(" ")
                offsets.append(pending_space)
                pending_space = None
            output.append(character)
            offsets.append(original_offset)
    return "".join(output), offsets


def _marker_triggers(tag: str, attrs: Sequence[tuple[str, str | None]]) -> list[str]:
    triggers: list[str] = []
    if tag == "mark":
        triggers.append("tag:mark")
    for raw_name, raw_value in attrs:
        name = raw_name.casefold()
        value = (raw_value or "").casefold()
        if name in {"class", "id"} and any(keyword in value for keyword in MARKER_KEYWORDS):
            triggers.append(f"{name}={raw_value or ''}")
        elif name.startswith("data-") and any(
            keyword in name or keyword in value for keyword in MARKER_KEYWORDS
        ):
            triggers.append(f"{raw_name}={raw_value or ''}")
    return list(dict.fromkeys(triggers))


class DetectorScopeHTMLParser(HTMLParser):
    """Collect visible text from marked or detector-labelled elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open_tags: list[str] = []
        self.ignored_tags: list[str] = []
        self.active: list[_Candidate] = []
        self.completed: list[_Candidate] = []
        self.sequence = 0

    def _append_to_active(self, value: str) -> None:
        for candidate in self.active:
            candidate.parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if self.ignored_tags:
            if lowered in IGNORED_TAGS:
                self.ignored_tags.append(lowered)
            return
        if lowered in IGNORED_TAGS:
            self.ignored_tags.append(lowered)
            return

        if lowered == "br" or lowered in BLOCK_TAGS:
            self._append_to_active("\n")

        triggers = _marker_triggers(lowered, attrs)
        if triggers:
            line, column = self.getpos()
            self.sequence += 1
            candidate = _Candidate(
                sequence=self.sequence,
                tag=lowered,
                depth=len(self.open_tags),
                line=line,
                column=column + 1,
                triggers=triggers,
            )
            self.active.append(candidate)

        if lowered not in VOID_TAGS:
            self.open_tags.append(lowered)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Empty elements have no visible fragment. A line break still separates
        # text belonging to an already active marked ancestor.
        if not self.ignored_tags and tag.casefold() in {"br", "hr"}:
            self._append_to_active("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_tags:
            self._append_to_active(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if self.ignored_tags:
            if lowered == self.ignored_tags[-1]:
                self.ignored_tags.pop()
            return

        if lowered in BLOCK_TAGS:
            self._append_to_active("\n")

        matching_depth = None
        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index] == lowered:
                matching_depth = index
                break
        if matching_depth is None:
            return

        remaining: list[_Candidate] = []
        for candidate in self.active:
            if candidate.depth >= matching_depth:
                self.completed.append(candidate)
            else:
                remaining.append(candidate)
        self.active = remaining
        del self.open_tags[matching_depth:]

    def close(self) -> None:
        super().close()
        self.completed.extend(self.active)
        self.active = []


def extract_report_fragments(html: str) -> list[dict[str, Any]]:
    """Extract and normalize visible detector-labelled fragments."""
    parser = DetectorScopeHTMLParser()
    parser.feed(html)
    parser.close()

    deduplicated: dict[str, dict[str, Any]] = {}
    for candidate in sorted(parser.completed, key=lambda item: item.sequence):
        text = _collapse_whitespace("".join(candidate.parts))
        normalized = normalize_text(text)
        if not normalized:
            continue
        if "tag:mark" not in candidate.triggers and UI_SCORE_METADATA_RE.fullmatch(normalized):
            continue
        location = {
            "line": candidate.line,
            "column": candidate.column,
            "tag": candidate.tag,
            "triggers": candidate.triggers,
        }
        if normalized in deduplicated:
            existing = deduplicated[normalized]
            existing["report_occurrences"] += 1
            existing["report_locations"].append(location)
            for trigger in candidate.triggers:
                if trigger not in existing["triggers"]:
                    existing["triggers"].append(trigger)
            continue
        deduplicated[normalized] = {
            "text": text,
            "normalized_text": normalized,
            "report_line": candidate.line,
            "report_column": candidate.column,
            "tag": candidate.tag,
            "triggers": list(candidate.triggers),
            "report_occurrences": 1,
            "report_locations": [location],
        }

    fragments: list[dict[str, Any]] = []
    for index, fragment in enumerate(deduplicated.values(), 1):
        fragment["index"] = index
        fragments.append(fragment)
    return fragments


def _declared_html_encoding(raw: bytes) -> str | None:
    header = raw[:4096].decode("latin-1", errors="ignore")
    match = re.search(
        r"(?is)<meta[^>]+charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)",
        header,
    )
    if match is None:
        match = re.search(
            r"(?is)<meta[^>]+content\s*=\s*['\"][^'\"]*charset\s*=\s*([A-Za-z0-9._-]+)",
            header,
        )
    return match.group(1) if match else None


def _decode_bytes(raw: bytes, *, html: bool) -> tuple[str, str]:
    candidates = ["utf-8-sig"]
    if html:
        declared = _declared_html_encoding(raw)
        if declared:
            candidates.append(declared)
    candidates.append("gb18030")
    attempted: list[str] = []
    for candidate in candidates:
        try:
            canonical = codecs.lookup(candidate).name
        except LookupError:
            continue
        if canonical in attempted:
            continue
        attempted.append(canonical)
        try:
            return raw.decode(candidate), canonical
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", raw, 0, len(raw), "unsupported or unreadable encoding")


def _all_occurrences(text: str, query: str) -> list[int]:
    positions: list[int] = []
    cursor = 0
    while query and cursor <= len(text) - len(query):
        position = text.find(query, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + 1
    return positions


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    previous_break = text.rfind("\n", 0, offset)
    return line, offset - previous_break


def _map_fragments(fragments: list[dict[str, Any]], source_text: str) -> None:
    normalized_source, offsets = _normalization_with_offsets(source_text)
    for fragment in fragments:
        query = fragment["normalized_text"]
        positions = _all_occurrences(normalized_source, query)
        fragment["source_occurrences"] = len(positions)
        fragment["source_start"] = None
        fragment["source_end"] = None
        fragment["source_line"] = None
        fragment["source_column"] = None
        if not positions:
            fragment["mapping_status"] = "MISSING"
            continue
        if len(positions) > 1:
            fragment["mapping_status"] = "AMBIGUOUS"
            continue
        normalized_start = positions[0]
        normalized_end = normalized_start + len(query)
        original_start = offsets[normalized_start]
        original_end = offsets[normalized_end - 1] + 1
        line, column = _line_column(source_text, original_start)
        fragment.update(
            {
                "mapping_status": "UNIQUE",
                "source_start": original_start,
                "source_end": original_end,
                "source_line": line,
                "source_column": column,
            }
        )


def _coverage(fragments: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "UNIQUE": 0,
        "MISSING": 0,
        "AMBIGUOUS": 0,
        "NOT_MAPPED_NO_SOURCE": 0,
        "NOT_MAPPED_SOURCE_ERROR": 0,
    }
    for fragment in fragments:
        status = fragment.get("mapping_status")
        if status in counts:
            counts[status] += 1
    total = len(fragments)
    unique = counts["UNIQUE"]
    return {
        "total_fragments": total,
        "uniquely_mapped": unique,
        "missing": counts["MISSING"],
        "ambiguous": counts["AMBIGUOUS"],
        "not_mapped_no_source": counts["NOT_MAPPED_NO_SOURCE"],
        "source_errors": counts["NOT_MAPPED_SOURCE_ERROR"],
        "ratio": unique / total if total else 0.0,
    }


def analyze_report(report: Path | str, source: Path | str | None = None) -> dict[str, Any]:
    """Analyze a report and optionally map every fragment to a source file."""
    report_path = Path(report)
    report_raw = report_path.read_bytes()
    report_sha256 = hashlib.sha256(report_raw).hexdigest()
    report_text, report_encoding = _decode_bytes(report_raw, html=True)
    fragments = extract_report_fragments(report_text)

    source_path = Path(source) if source is not None else None
    source_sha256: str | None = None
    source_encoding: str | None = None
    review_reasons: list[dict[str, Any]] = []

    if not fragments:
        review_reasons.append(
            {
                "code": "NO_FLAGGED_VISIBLE_TEXT",
                "message": "The report contains no visible text in supported detector markers.",
            }
        )
    elif source_path is None:
        for fragment in fragments:
            fragment.update(
                {
                    "mapping_status": "NOT_MAPPED_NO_SOURCE",
                    "source_occurrences": None,
                    "source_start": None,
                    "source_end": None,
                    "source_line": None,
                    "source_column": None,
                }
            )
        review_reasons.append(
            {
                "code": "SOURCE_NOT_PROVIDED",
                "message": "Report annotations cannot become an edit scope without a source document.",
            }
        )
    else:
        source_raw = source_path.read_bytes()
        source_sha256 = hashlib.sha256(source_raw).hexdigest()
        try:
            source_text, source_encoding = _decode_bytes(source_raw, html=False)
        except UnicodeDecodeError:
            for fragment in fragments:
                fragment.update(
                    {
                        "mapping_status": "NOT_MAPPED_SOURCE_ERROR",
                        "source_occurrences": None,
                        "source_start": None,
                        "source_end": None,
                        "source_line": None,
                        "source_column": None,
                    }
                )
            review_reasons.append(
                {
                    "code": "SOURCE_DECODE_FAILED",
                    "message": "The source is not readable as UTF-8 or GB18030; no mapping was attempted.",
                }
            )
        else:
            _map_fragments(fragments, source_text)
            missing = sum(item["mapping_status"] == "MISSING" for item in fragments)
            ambiguous = sum(item["mapping_status"] == "AMBIGUOUS" for item in fragments)
            if missing:
                review_reasons.append(
                    {
                        "code": "FRAGMENTS_MISSING_FROM_SOURCE",
                        "count": missing,
                        "message": "One or more normalized report fragments are absent from the source.",
                    }
                )
            if ambiguous:
                review_reasons.append(
                    {
                        "code": "FRAGMENTS_AMBIGUOUS_IN_SOURCE",
                        "count": ambiguous,
                        "message": "One or more normalized report fragments occur more than once in the source.",
                    }
                )

    coverage = _coverage(fragments)
    passed = bool(fragments) and source_path is not None and coverage["uniquely_mapped"] == len(fragments)
    status = "PASS" if passed else "REVIEW"
    exit_code = 0 if passed else 2
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "detector_report_scope_extraction",
        "status": status,
        "exit_code": exit_code,
        "report_path": str(report_path.resolve()),
        "report_sha256": report_sha256,
        "report_encoding": report_encoding,
        "source_path": str(source_path.resolve()) if source_path is not None else None,
        "source_sha256": source_sha256,
        "source_encoding": source_encoding,
        "coverage": coverage,
        "review_reasons": review_reasons,
        "fragments": fragments,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract static detector-report annotations as style-editing scope hints."
    )
    parser.add_argument("report", type=Path, help="Local HTML detector report")
    parser.add_argument(
        "--source",
        type=Path,
        help="Optional source document used for unique exact normalized mapping",
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (currently only json)",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the JSON result")
    return parser


def _portable_scope_paths(
    payload: dict[str, Any],
    *,
    report: Path,
    source: Path | None,
    output: Path | None,
) -> dict[str, Any]:
    portable = dict(payload)
    if output is None:
        portable["report_path"] = "<LOCAL_REPORT_NOT_PERSISTED>"
        portable["source_path"] = (
            "<LOCAL_SOURCE_NOT_PERSISTED>" if source is not None else None
        )
        portable["path_base"] = "NOT_PERSISTED"
        return portable
    base = output.resolve(strict=False).parent
    for field, path in (("report_path", report), ("source_path", source)):
        if path is None:
            portable[field] = None
            continue
        try:
            relative = path.resolve(strict=False).relative_to(base)
        except ValueError as exc:
            raise ValueError(
                "scope output directory must contain the report and source artifacts"
            ) from exc
        portable[field] = relative.as_posix()
    portable["path_base"] = "SCOPE_ARTIFACT_PARENT"
    return portable


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = analyze_report(args.report, args.source)
        payload = _portable_scope_paths(
            payload,
            report=args.report,
            source=args.source,
            output=args.output,
        )
    except (OSError, UnicodeError) as error:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "operation": "detector_report_scope_extraction",
            "status": "FAIL",
            "exit_code": 1,
            "report_path": "<LOCAL_REPORT_UNAVAILABLE>",
            "report_sha256": None,
            "source_path": "<LOCAL_SOURCE_UNAVAILABLE>" if args.source else None,
            "source_sha256": None,
            "coverage": {
                "total_fragments": 0,
                "uniquely_mapped": 0,
                "missing": 0,
                "ambiguous": 0,
                "not_mapped_no_source": 0,
                "source_errors": 1,
                "ratio": 0.0,
            },
            "review_reasons": [
                {
                    "code": "INPUT_READ_FAILED",
                    "message": "Detector-report input could not be read; inspect the local invocation and files.",
                }
            ],
            "fragments": [],
        }
    except ValueError:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "operation": "detector_report_scope_extraction",
            "status": "FAIL",
            "exit_code": 1,
            "report_path": "<LOCAL_REPORT_NOT_PERSISTED>",
            "report_sha256": None,
            "source_path": "<LOCAL_SOURCE_NOT_PERSISTED>" if args.source else None,
            "source_sha256": None,
            "coverage": {
                "total_fragments": 0,
                "uniquely_mapped": 0,
                "missing": 0,
                "ambiguous": 0,
                "not_mapped_no_source": 0,
                "source_errors": 1,
                "ratio": 0.0,
            },
            "review_reasons": [
                {
                    "code": "SCOPE_OUTPUT_BOUNDARY_INVALID",
                    "message": "Place the scope output at a common parent of the local report and source artifacts.",
                }
            ],
            "fragments": [],
        }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except (OSError, UnicodeError):
            payload = {
                "schema_version": SCHEMA_VERSION,
                "operation": "detector_report_scope_extraction",
                "status": "FAIL",
                "exit_code": 1,
                "report_path": "<LOCAL_REPORT_NOT_PERSISTED>",
                "report_sha256": None,
                "source_path": "<LOCAL_SOURCE_NOT_PERSISTED>" if args.source else None,
                "source_sha256": None,
                "coverage": {
                    "total_fragments": 0,
                    "uniquely_mapped": 0,
                    "missing": 0,
                    "ambiguous": 0,
                    "not_mapped_no_source": 0,
                    "source_errors": 1,
                    "ratio": 0.0,
                },
                "review_reasons": [
                    {
                        "code": "SCOPE_OUTPUT_WRITE_FAILED",
                        "message": "Scope artifact could not be persisted; inspect the local output destination.",
                    }
                ],
                "fragments": [],
            }
            rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.write(rendered)
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
