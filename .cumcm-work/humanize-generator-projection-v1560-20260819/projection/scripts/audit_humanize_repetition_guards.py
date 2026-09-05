#!/usr/bin/env python3
"""Evaluate versioned negative repetition guards on masked long-document records."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
import sys
import unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import load_humanize_negative_guards as negative_guard_loader  # noqa: E402
import scan_humanize_chinese as lexical  # noqa: E402


PROTECTED_RE = re.compile(
    r"\[\[PROTECTED:(?P<id>[^:\]]+):(?P<hash>[0-9a-f]{12})\]\]"
)
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
HAN_GAP_RE = re.compile(
    r"(?<=[\u3400-\u9fff])[ \t\u00a0\u3000]+(?=[\u3400-\u9fff])"
)
HAN_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
PURE_TEX_STRUCTURE_LINE_RE = re.compile(
    r"^\s*\\(?:begin|end|part|chapter|section|subsection|subsubsection|"
    r"paragraph|subparagraph|label|input|include)\b.*$"
)
MD_HEADING_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$")
MD_TOP_LEVEL_ITEM_RE = re.compile(r"^(?:[-+*]|\d+[.)])[ \t]+(?P<text>\S.*)$")
MD_NESTED_ITEM_RE = re.compile(r"^[ \t]+(?:[-+*]|\d+[.)])[ \t]+")
MD_FENCE_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})")
TEX_CONTROL_WORD_RE = re.compile(r"\\(?P<name>[A-Za-z@]+)(?P<star>\*)?")
TEX_HEADING_COMMANDS = frozenset(
    {
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    }
)
TEX_VISIBLE_HEADING_WRAPPERS = frozenset({"emph", "textbf", "textit"})
TEX_CODE_BEGIN_RE = re.compile(r"\\begin\{(?P<env>verbatim\*?|lstlisting|minted)\}")
TEX_CODE_END_RE = re.compile(r"\\end\{(?P<env>verbatim\*?|lstlisting|minted)\}")
TEX_VERB_RE = re.compile(r"\\verb\*?(?P<delimiter>[^A-Za-z0-9\s]).*?(?P=delimiter)")
PROTECTED_BOUNDARY_LINE = "\u241eHUMANIZE_PROTECTED_BOUNDARY\u241e"
MAX_ATTRIBUTION_CANDIDATES = 12
MAX_NGRAM_CANDIDATES = 250_000
RESOLVED_SCENES = frozenset({"COURSE", "MODELING", "RESEARCH", "GENERAL"})


class DetectorEvaluationReview(ValueError):
    """Raised when a detector input cannot be evaluated without guessing."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalized_visible_segments(text: str) -> list[str]:
    segments: list[str] = []
    for raw in PROTECTED_RE.split(text):
        normalized = unicodedata.normalize("NFKC", raw)
        normalized = ZERO_WIDTH_RE.sub("", normalized)
        normalized = HAN_GAP_RE.sub("", normalized)
        if normalized:
            segments.append(normalized)
    return segments


def _paragraph_blocks(record: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    value = record.get(field)
    if not isinstance(value, str):
        return []
    blocks: list[dict[str, Any]] = []
    paragraph_index = 0
    for protected_segment in PROTECTED_RE.split(
        value.replace("\r\n", "\n").replace("\r", "\n")
    ):
        for raw_block in re.split(r"\n[ \t]*\n+", protected_segment):
            paragraph_index += 1
            lines = [
                line
                for line in raw_block.splitlines()
                if not PURE_TEX_STRUCTURE_LINE_RE.match(line)
            ]
            block = "\n".join(lines).strip()
            if len("".join(HAN_RUN_RE.findall(block))) < 4:
                continue
            blocks.append(
                {
                    "unit_id": str(record.get("unit_id", "")),
                    "paragraph_index": paragraph_index,
                    "text": block,
                }
            )
    return blocks


def _record_format(record: Mapping[str, Any]) -> str:
    declared = str(record.get("format", "")).strip().lower()
    if declared in {"tex", "markdown"}:
        return declared
    suffix = str(record.get("suffix", "")).strip().lower()
    return "tex" if suffix in {".tex", ".ltx"} else "markdown"


def _heading_leaf(record: Mapping[str, Any]) -> str:
    heading_path = str(record.get("heading_path", "")).strip()
    if not heading_path or heading_path == "(front-matter)":
        return ""
    return heading_path.rsplit(" / ", 1)[-1].strip()


def _protected_boundaries(
    record: Mapping[str, Any], text: str, *, expose_tex_structure: bool = False
) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_tokens = record.get("protected_structure_tokens", {})
    if raw_tokens is None:
        raw_tokens = {}
    if not isinstance(raw_tokens, Mapping):
        raise DetectorEvaluationReview("protected_structure_tokens must be an object")
    seen_ids: set[str] = set()

    def replacement(match: re.Match[str]) -> str:
        protected_id = match.group("id")
        token = raw_tokens.get(protected_id)
        if token is None:
            return f"\n{PROTECTED_BOUNDARY_LINE}\n"
        seen_ids.add(protected_id)
        if not isinstance(token, Mapping):
            raise DetectorEvaluationReview(
                f"protected structure token {protected_id} must be an object"
            )
        kind = token.get("kind")
        expected_keys = {"kind", "list_kind"}
        if kind == "LIST_ITEM":
            expected_keys = (
                {"kind", "item_prefix"}
                if "item_prefix" in token
                else {"kind"}
            )
        if set(token) != expected_keys:
            raise DetectorEvaluationReview(
                f"protected structure token {protected_id} fields are invalid"
            )
        if kind not in {"LIST_BEGIN", "LIST_ITEM", "LIST_END"}:
            raise DetectorEvaluationReview(
                f"protected structure token {protected_id} kind is unsupported"
            )
        if not expose_tex_structure:
            raise DetectorEvaluationReview(
                "TeX protected structure tokens cannot be applied to Markdown"
            )
        if kind == "LIST_ITEM":
            item_prefix = token.get("item_prefix", "")
            if item_prefix not in {"", "*"}:
                raise DetectorEvaluationReview(
                    f"protected structure token {protected_id} item prefix is unsupported"
                )
            rendered = r"\item" + str(item_prefix)
        else:
            list_kind = token.get("list_kind")
            if list_kind not in {"itemize", "enumerate"}:
                raise DetectorEvaluationReview(
                    f"protected structure token {protected_id} list kind is unsupported"
                )
            command = "begin" if kind == "LIST_BEGIN" else "end"
            rendered = f"\\{command}{{{list_kind}}}"
        return f"\n{rendered}\n"

    rendered = PROTECTED_RE.sub(replacement, normalized)
    unused_ids = sorted(set(str(item) for item in raw_tokens) - seen_ids)
    if unused_ids:
        raise DetectorEvaluationReview(
            "protected structure token IDs are absent from the masked text: "
            + ",".join(unused_ids)
        )
    return rendered


def _item_segments(text: str) -> list[str]:
    return [segment.strip() for segment in _normalized_visible_segments(text) if segment.strip()]


def _blank_spans(
    text: str, spans: Sequence[tuple[int, int, str]]
) -> list[str]:
    chars = list(text)
    for start, end, _reason in spans:
        if not 0 <= start <= end <= len(chars):
            raise DetectorEvaluationReview("protected span is outside the snapshot")
        for index in range(start, end):
            if chars[index] not in {"\r", "\n"}:
                chars[index] = " "
    return chars


def _inside_span(offset: int, spans: Sequence[tuple[int, int, str]]) -> bool:
    return any(start <= offset < end for start, end, _reason in spans)


def _tex_trivia_end(structure: str, start: int) -> int:
    cursor = start
    while cursor < len(structure) and structure[cursor].isspace():
        cursor += 1
    return cursor


def _tex_group_end(structure: str, start: int) -> int | None:
    """Return a TeX-aware group end on a length-preserving structure view."""
    if start >= len(structure) or structure[start] not in "[{":
        return None
    opening = structure[start]
    brace_depth = 1 if opening == "{" else 0
    cursor = start + 1
    while cursor < len(structure):
        char = structure[cursor]
        if char == "\\":
            command = TEX_CONTROL_WORD_RE.match(structure, cursor)
            cursor = command.end() if command else min(cursor + 2, len(structure))
            continue
        if char == "{":
            brace_depth += 1
        elif char == "}" and brace_depth:
            brace_depth -= 1
            if opening == "{" and brace_depth == 0:
                return cursor + 1
        elif opening == "[" and char == "]" and brace_depth == 0:
            return cursor + 1
        cursor += 1
    return None


def _tex_group(
    text: str, structure: str, start: int, opening: str
) -> tuple[str, int] | None:
    if start >= len(structure) or structure[start] != opening:
        return None
    end = _tex_group_end(structure, start)
    if end is None:
        return None
    return text[start + 1 : end - 1], end


def classify_tex_list_structure_content(content: str) -> dict[str, str] | None:
    """Classify one complete protected TeX command call without exposing payload."""
    structure = lexical._tex_structure_view(content)
    command = TEX_CONTROL_WORD_RE.match(structure)
    if command is None or command.start() != 0:
        return None
    name = command.group("name")
    star = command.group("star") or ""
    cursor = _tex_trivia_end(structure, command.end())

    if name == "item":
        if cursor < len(structure) and structure[cursor] == "[":
            optional = _tex_group(content, structure, cursor, "[")
            if optional is None:
                raise DetectorEvaluationReview(
                    "TeX list item optional argument is unbalanced"
                )
            _label, cursor = optional
            cursor = _tex_trivia_end(structure, cursor)
        if cursor != len(structure):
            return None
        token = {"kind": "LIST_ITEM"}
        if star:
            token["item_prefix"] = "*"
        return token

    if name not in {"begin", "end"} or star:
        return None
    required = _tex_group(content, structure, cursor, "{")
    if required is None:
        return None
    environment, cursor = required
    environment = lexical._tex_structure_view(environment).strip()
    if environment not in {"itemize", "enumerate"}:
        return None
    cursor = _tex_trivia_end(structure, cursor)
    if name == "begin" and cursor < len(structure) and structure[cursor] == "[":
        optional = _tex_group(content, structure, cursor, "[")
        if optional is None:
            raise DetectorEvaluationReview(
                "TeX list environment optional argument is unbalanced"
            )
        _options, cursor = optional
        cursor = _tex_trivia_end(structure, cursor)
    if cursor != len(structure):
        return None
    return {
        "kind": "LIST_BEGIN" if name == "begin" else "LIST_END",
        "list_kind": environment,
    }


def _tex_list_structure_tokens(
    text: str,
    *,
    protected_spans: Sequence[tuple[int, int, str]] | None = None,
    command_spans: Sequence[tuple[int, int, str]] | None = None,
) -> list[dict[str, Any]]:
    structure = lexical._tex_structure_view(text)
    protected = list(protected_spans or ())
    commands = list(
        command_spans
        if command_spans is not None
        else lexical._tex_command_call_spans(text, structure_view=structure)
    )
    output: list[dict[str, Any]] = []
    for start, end, _reason in commands:
        command = TEX_CONTROL_WORD_RE.match(structure, start)
        if command is None or command.group("name") not in {"begin", "end", "item"}:
            continue
        if _inside_span(start, protected):
            continue
        if any(
            outer_start < start and end <= outer_end
            for outer_start, outer_end, _outer_reason in commands
        ):
            continue
        if command.group("name") == "item":
            cursor = _tex_trivia_end(structure, end)
            if (
                cursor < len(structure)
                and structure[cursor] == "["
                and _tex_group_end(structure, cursor) is None
            ):
                raise DetectorEvaluationReview(
                    "TeX list item optional argument is unbalanced"
                )
        token = classify_tex_list_structure_content(text[start:end])
        if token is not None:
            output.append({**token, "start": start, "end": end})
            continue
    output.sort(key=lambda item: (int(item["start"]), int(item["end"])))
    return output


def _tex_structured_author_view(text: str) -> str:
    """Expose only list controls and unprotected author prose from raw TeX."""
    protected_spans = list(lexical.ProtectedIndex(text, document_format="tex").spans)
    structure = lexical._tex_structure_view(text)
    command_spans = lexical._tex_command_call_spans(text, structure_view=structure)
    chars = _blank_spans(
        text,
        lexical._merge_spans([*protected_spans, *command_spans]),
    )
    for token in _tex_list_structure_tokens(
        text,
        protected_spans=protected_spans,
        command_spans=command_spans,
    ):
        kind = str(token["kind"])
        if kind == "LIST_BEGIN":
            rendered = rf"\begin{{{token['list_kind']}}}"
        elif kind == "LIST_END":
            rendered = rf"\end{{{token['list_kind']}}}"
        else:
            rendered = r"\item" + str(token.get("item_prefix", ""))
        token_start = int(token["start"])
        token_end = int(token["end"])
        if len(rendered) > token_end - token_start:
            raise DetectorEvaluationReview("canonical TeX list token exceeds source span")
        chars[token_start : token_start + len(rendered)] = rendered
    return "".join(chars)


def _tex_visible_heading_text(title: str) -> str:
    """Recover rendered title text only through an allowlist of style wrappers."""
    structure = lexical._tex_structure_view(title)
    protected_spans = list(
        lexical.ProtectedIndex(title, document_format="tex").spans
    )
    opaque_command_spans = lexical._tex_command_call_spans(
        title,
        editable_style_wrappers=TEX_VISIBLE_HEADING_WRAPPERS,
        structure_view=structure,
    )
    opaque_spans = lexical._merge_spans(
        [*protected_spans, *opaque_command_spans]
    )
    visible = _blank_spans(title, opaque_spans)

    for command in TEX_CONTROL_WORD_RE.finditer(structure):
        if command.group("name") not in TEX_VISIBLE_HEADING_WRAPPERS:
            continue
        if _inside_span(command.start(), opaque_spans):
            continue
        if command.group("star"):
            return ""
        cursor = _tex_trivia_end(structure, command.end())
        if cursor >= len(structure) or structure[cursor] != "{":
            return ""
        group_end = _tex_group_end(structure, cursor)
        if group_end is None:
            return ""
        for index in range(command.start(), cursor + 1):
            if visible[index] not in {"\r", "\n"}:
                visible[index] = " "
        visible[group_end - 1] = " "

    rendered = "".join(visible).replace("~", " ")
    rendered = rendered.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", rendered).strip()


def _tex_heading_leaf_from_content(content: str) -> str | None:
    structure = lexical._tex_structure_view(content)
    command = TEX_CONTROL_WORD_RE.match(structure)
    if (
        command is None
        or command.start() != 0
        or command.group("name") not in TEX_HEADING_COMMANDS
    ):
        return None
    cursor = _tex_trivia_end(structure, command.end())
    if cursor < len(structure) and structure[cursor] == "[":
        optional = _tex_group(content, structure, cursor, "[")
        if optional is None:
            return None
        _short_title, cursor = optional
        cursor = _tex_trivia_end(structure, cursor)
    required = _tex_group(content, structure, cursor, "{")
    if required is None:
        return None
    title, cursor = required
    if _tex_trivia_end(structure, cursor) != len(structure):
        return None
    return _tex_visible_heading_text(title)


def _tex_heading_fallback(level: str, start_line: int, start_offset: int) -> str:
    return f"(tex-{level}-title-line-{start_line}-offset-{start_offset})"


def _tex_line_starts(text: str) -> list[int]:
    return [0, *(match.end() for match in re.finditer(r"\n", text))]


def _tex_brace_depths(structure: str) -> list[int]:
    """Return brace depth before each offset in the masked structure view."""
    depths = [0] * (len(structure) + 1)
    depth = 0
    cursor = 0
    while cursor < len(structure):
        depths[cursor] = depth
        char = structure[cursor]
        if char == "\\":
            command = TEX_CONTROL_WORD_RE.match(structure, cursor)
            end = command.end() if command else min(cursor + 2, len(structure))
            for index in range(cursor + 1, end):
                depths[index] = depth
            cursor = end
            continue
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        cursor += 1
    depths[len(structure)] = depth
    return depths


def _tex_dynamic_syntax_kind(command_name: str) -> tuple[str, str] | None:
    if command_name in {"csname", "endcsname"}:
        return (
            "TEX_DYNAMIC_CONTROL_SEQUENCE_UNSUPPORTED",
            "dynamic TeX control-sequence construction cannot be authenticated",
        )
    if command_name.startswith("if") or command_name in {"else", "or", "fi", "unless"}:
        return (
            "TEX_CONDITIONAL_BRANCH_UNSUPPORTED",
            "TeX conditional branches cannot be authenticated statically",
        )
    if command_name == "catcode":
        return (
            "TEX_CATCODE_MUTATION_UNSUPPORTED",
            "TeX catcode mutation cannot be authenticated statically",
        )
    if command_name in {
        "def",
        "gdef",
        "edef",
        "xdef",
        "let",
        "futurelet",
        "newcommand",
        "renewcommand",
        "providecommand",
        "DeclareRobustCommand",
        "NewDocumentCommand",
        "RenewDocumentCommand",
        "ProvideDocumentCommand",
        "DeclareDocumentCommand",
        "newenvironment",
        "renewenvironment",
    }:
        return (
            "TEX_MACRO_DEFINITION_UNSUPPORTED",
            "TeX macro definitions cannot be authenticated statically",
        )
    return None


def _tex_definition_end(structure: str, command: re.Match[str]) -> int | None:
    name = command.group("name")
    cursor = _tex_trivia_end(structure, command.end())

    if name in {"def", "gdef", "edef", "xdef"}:
        target = TEX_CONTROL_WORD_RE.match(structure, cursor)
        if target is not None:
            cursor = target.end()
        elif cursor < len(structure) and structure[cursor] == "\\":
            cursor += 2
        else:
            return None
        while cursor < len(structure):
            if structure[cursor] == "\\":
                token = TEX_CONTROL_WORD_RE.match(structure, cursor)
                cursor = token.end() if token else min(cursor + 2, len(structure))
                continue
            if structure[cursor] == "{":
                return _tex_group_end(structure, cursor)
            cursor += 1
        return None

    if name in {"let", "futurelet"}:
        newline = structure.find("\n", cursor)
        return len(structure) if newline < 0 else newline

    def consume_required_group(offset: int) -> int | None:
        offset = _tex_trivia_end(structure, offset)
        if offset >= len(structure) or structure[offset] != "{":
            return None
        return _tex_group_end(structure, offset)

    target_end = consume_required_group(cursor)
    if target_end is None:
        target = TEX_CONTROL_WORD_RE.match(structure, cursor)
        if target is None:
            return None
        target_end = target.end()
    cursor = _tex_trivia_end(structure, target_end)

    if name in {
        "newcommand",
        "renewcommand",
        "providecommand",
        "DeclareRobustCommand",
    }:
        for _index in range(2):
            if cursor >= len(structure) or structure[cursor] != "[":
                break
            optional_end = _tex_group_end(structure, cursor)
            if optional_end is None:
                return None
            cursor = _tex_trivia_end(structure, optional_end)
        return consume_required_group(cursor)

    if name in {"newenvironment", "renewenvironment"}:
        for _index in range(2):
            if cursor >= len(structure) or structure[cursor] != "[":
                break
            optional_end = _tex_group_end(structure, cursor)
            if optional_end is None:
                return None
            cursor = _tex_trivia_end(structure, optional_end)
        begin_end = consume_required_group(cursor)
        return None if begin_end is None else consume_required_group(begin_end)

    if name in {
        "NewDocumentCommand",
        "RenewDocumentCommand",
        "ProvideDocumentCommand",
        "DeclareDocumentCommand",
    }:
        argument_spec_end = consume_required_group(cursor)
        return (
            None
            if argument_spec_end is None
            else consume_required_group(argument_spec_end)
        )
    return None


def analyze_tex_headings(
    text: str,
    *,
    protected_spans: Sequence[tuple[int, int, str]] | None = None,
    command_spans: Sequence[tuple[int, int, str]] | None = None,
) -> dict[str, list[Any]]:
    """Analyze authenticated global headings and fail-closed malformed calls."""
    structure = lexical._tex_structure_view(text)
    protected = list(
        protected_spans
        if protected_spans is not None
        else lexical.ProtectedIndex(text, document_format="tex").spans
    )
    commands = list(
        command_spans
        if command_spans is not None
        else lexical._tex_command_call_spans(text, structure_view=structure)
    )
    line_starts = _tex_line_starts(text)
    brace_depths = _tex_brace_depths(structure)
    headings: list[dict[str, Any]] = []
    problems: list[str] = []
    malformed_spans: list[dict[str, Any]] = []

    control_words = list(TEX_CONTROL_WORD_RE.finditer(structure))
    balanced_definition_ends: dict[int, int] = {}
    for command in control_words:
        command_start = command.start()
        if _inside_span(command_start, protected):
            continue
        dynamic_kind = _tex_dynamic_syntax_kind(command.group("name"))
        if dynamic_kind is None or dynamic_kind[0] != "TEX_MACRO_DEFINITION_UNSUPPORTED":
            continue
        definition_end = _tex_definition_end(structure, command)
        if definition_end is not None:
            balanced_definition_ends[command_start] = definition_end

    dynamic_start = len(text) + 1
    seen_dynamic_problem_codes: set[str] = set()
    for command in control_words:
        command_start = command.start()
        if _inside_span(command_start, protected):
            continue
        if any(
            definition_start < command_start < definition_end
            for definition_start, definition_end in balanced_definition_ends.items()
        ):
            continue
        dynamic_kind = _tex_dynamic_syntax_kind(command.group("name"))
        if dynamic_kind is None:
            continue
        problem_code, problem_message = dynamic_kind
        if problem_code == "TEX_MACRO_DEFINITION_UNSUPPORTED":
            protected_end = balanced_definition_ends.get(command_start)
            if protected_end is None:
                protected_end = len(text)
                dynamic_start = min(dynamic_start, command_start)
        else:
            protected_end = len(text)
            dynamic_start = min(dynamic_start, command_start)
        start_index = bisect_right(line_starts, command_start) - 1
        problem = f"{problem_code}: {problem_message}"
        if problem_code not in seen_dynamic_problem_codes:
            seen_dynamic_problem_codes.add(problem_code)
            problems.append(problem)
        end_index = bisect_right(
            line_starts, max(command_start, protected_end - 1)
        ) - 1
        malformed_spans.append(
            {
                "start": command_start,
                "end": protected_end,
                "start_line": start_index + 1,
                "end_line": end_index + 1,
                "level": "",
                "problem_code": problem_code,
                "problem": problem,
            }
        )

    for command in control_words:
        level = command.group("name")
        if level not in TEX_HEADING_COMMANDS:
            continue
        command_start = command.start()
        if brace_depths[command_start] != 0 or _inside_span(command_start, protected):
            continue
        if command_start >= dynamic_start:
            continue
        start_index = bisect_right(line_starts, command_start) - 1
        line_start = line_starts[start_index]
        if structure[line_start:command_start].strip():
            problem_code = "TEX_HEADING_POSITION_UNSUPPORTED"
            problem_message = "TeX heading is not at the start of a physical line"
            problem = f"{problem_code}: {problem_message}"
            problems.append(problem)
            malformed_spans.append(
                {
                    "start": command_start,
                    "end": len(text),
                    "start_line": start_index + 1,
                    "end_line": len(line_starts),
                    "level": level,
                    "problem_code": problem_code,
                    "problem": problem,
                }
            )
            continue

        cursor = _tex_trivia_end(structure, command.end())
        problem_code = ""
        problem_message = ""
        if cursor < len(structure) and structure[cursor] == "[":
            optional_end = _tex_group_end(structure, cursor)
            if optional_end is None:
                problem_code = "TEX_HEADING_OPTIONAL_ARGUMENT_UNBALANCED"
                problem_message = "TeX heading optional argument is unbalanced"
            else:
                cursor = _tex_trivia_end(structure, optional_end)
        if not problem_code:
            if cursor >= len(structure) or structure[cursor] != "{":
                problem_code = "TEX_HEADING_REQUIRED_ARGUMENT_UNSUPPORTED"
                problem_message = (
                    "TeX heading required argument is not a balanced group"
                )
            else:
                required_end = _tex_group_end(structure, cursor)
                if required_end is None:
                    problem_code = "TEX_HEADING_REQUIRED_ARGUMENT_UNBALANCED"
                    problem_message = "TeX heading required argument is unbalanced"
                else:
                    command_end = required_end

        if problem_code:
            problem = f"{problem_code}: {problem_message}"
            problems.append(problem)
            malformed_spans.append(
                {
                    "start": command_start,
                    "end": len(text),
                    "start_line": start_index + 1,
                    "end_line": len(line_starts),
                    "level": level,
                    "problem_code": problem_code,
                    "problem": problem,
                }
            )
            continue

        if any(
            start < command_start and command_end <= end
            for start, end, _outer_reason in commands
        ):
            continue
        leaf = _tex_heading_leaf_from_content(text[command_start:command_end])
        if leaf is None:
            continue
        end_index = bisect_right(line_starts, max(command_start, command_end - 1)) - 1
        line_end = (
            line_starts[end_index + 1]
            if end_index + 1 < len(line_starts)
            else len(text)
        )
        headings.append(
            {
                "start": command_start,
                "end": command_end,
                "line_start": line_start,
                "line_end": line_end,
                "start_line": start_index + 1,
                "end_line": end_index + 1,
                "level": level,
                "heading_leaf": leaf
                or _tex_heading_fallback(level, start_index + 1, command_start),
            }
        )
    return {
        "headings": headings,
        "problems": list(dict.fromkeys(problems)),
        "malformed_spans": malformed_spans,
    }


def authenticated_tex_headings(
    text: str,
    *,
    protected_spans: Sequence[tuple[int, int, str]] | None = None,
    command_spans: Sequence[tuple[int, int, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return authenticated global TeX heading spans and payload-masked leaves."""
    analysis = analyze_tex_headings(
        text,
        protected_spans=protected_spans,
        command_spans=command_spans,
    )
    return list(analysis["headings"])


def _tex_heading_leaves_by_line(
    text: str,
    *,
    protected_spans: Sequence[tuple[int, int, str]],
    command_spans: Sequence[tuple[int, int, str]],
) -> dict[int, str]:
    """Authenticate global heading spans and return payload-masked role metadata."""
    analysis = analyze_tex_headings(
        text,
        protected_spans=protected_spans,
        command_spans=command_spans,
    )
    if analysis["problems"]:
        raise DetectorEvaluationReview(str(analysis["problems"][0]))
    return {
        int(heading["start_line"]): str(heading["heading_leaf"])
        for heading in analysis["headings"]
    }


def _markdown_structured_author_view(text: str) -> str:
    """Keep Markdown list syntax while masking protected inline payloads."""
    spans = list(lexical.ProtectedIndex(text, document_format="markdown").spans)
    return "".join(_blank_spans(text, spans))


def _append_list_block(
    output: list[dict[str, Any]],
    record: Mapping[str, Any],
    *,
    document_format: str,
    heading_leaf: str,
    start_line: int,
    items: Sequence[Sequence[str]],
) -> None:
    normalized_items = [list(item) for item in items if any(segment for segment in item)]
    if not normalized_items:
        return
    output.append(
        {
            "unit_id": str(record.get("unit_id", "")),
            "format": document_format,
            "heading_leaf": heading_leaf,
            "start_line": start_line,
            "items": normalized_items,
            "item_count": len(normalized_items),
        }
    )


def _markdown_list_blocks(record: Mapping[str, Any], text: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    current_heading = _heading_leaf(record)
    current_items: list[list[str]] = []
    current_start = 0
    fence_marker = ""

    def flush() -> None:
        nonlocal current_items, current_start
        if current_items:
            _append_list_block(
                output,
                record,
                document_format="markdown",
                heading_leaf=current_heading,
                start_line=current_start,
                items=current_items,
            )
        current_items = []
        current_start = 0

    visible_text = _markdown_structured_author_view(
        _protected_boundaries(record, text)
    )
    for line_number, line in enumerate(visible_text.splitlines(), 1):
        fence = MD_FENCE_RE.match(line)
        if fence:
            marker = fence.group("marker")
            if not fence_marker:
                flush()
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                fence_marker = ""
            continue
        if fence_marker:
            continue
        if line == PROTECTED_BOUNDARY_LINE:
            flush()
            continue
        if re.match(r"^ {0,3}>", line):
            flush()
            continue
        heading = MD_HEADING_RE.match(line)
        if heading:
            flush()
            current_heading = heading.group("title").strip()
            continue
        item = MD_TOP_LEVEL_ITEM_RE.match(line)
        if item:
            if not current_items:
                current_start = line_number
            current_items.append(_item_segments(item.group("text")))
            continue
        if MD_NESTED_ITEM_RE.match(line):
            continue
        if not line.strip():
            continue
        if current_items and line[:1].isspace():
            continue
        flush()
    flush()
    return output


def _strip_tex_comment(line: str) -> str:
    for index, char in enumerate(line):
        if char != "%":
            continue
        slash_count = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            slash_count += 1
            cursor -= 1
        if slash_count % 2 == 0:
            return line[:index]
    return line


def _tex_list_blocks(record: Mapping[str, Any], text: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    current_heading = _heading_leaf(record)
    list_stack: list[str] = []
    current_items: list[list[str]] = []
    current_start = 0
    ignored_environment = ""

    structural_text = _protected_boundaries(
        record, text, expose_tex_structure=True
    )
    structural_protected_spans = list(
        lexical.ProtectedIndex(
            structural_text, document_format="tex"
        ).spans
    )
    structural_command_spans = lexical._tex_command_call_spans(
        structural_text
    )
    heading_leaves_by_line = _tex_heading_leaves_by_line(
        structural_text,
        protected_spans=structural_protected_spans,
        command_spans=structural_command_spans,
    )
    visible_text = _tex_structured_author_view(structural_text)
    structural_lines = structural_text.splitlines(keepends=True)
    visible_lines = visible_text.splitlines(keepends=True)
    if len(structural_lines) != len(visible_lines):
        raise DetectorEvaluationReview("TeX structured masking changed line count")
    line_starts: list[int] = []
    cursor = 0
    for structural_line in structural_lines:
        line_starts.append(cursor)
        cursor += len(structural_line)
    for line_number, (line_start, structural_line, visible_line) in enumerate(
        zip(line_starts, structural_lines, visible_lines), 1
    ):
        structural_line = structural_line.removesuffix("\n")
        visible_line = visible_line.removesuffix("\n")
        if structural_line == PROTECTED_BOUNDARY_LINE:
            continue
        if ignored_environment:
            end = TEX_CODE_END_RE.search(visible_line)
            if end and end.group("env") == ignored_environment:
                ignored_environment = ""
            continue
        code_begin = TEX_CODE_BEGIN_RE.search(visible_line)
        if code_begin:
            ignored_environment = code_begin.group("env")
            continue
        line = _strip_tex_comment(visible_line)
        if not list_stack:
            heading_leaf = heading_leaves_by_line.get(line_number, "")
            if heading_leaf:
                current_heading = heading_leaf
                continue
        tokens = _tex_list_structure_tokens(line)
        for token_index, token in enumerate(tokens):
            kind = str(token["kind"])
            if kind == "LIST_BEGIN":
                if not list_stack:
                    current_items = []
                    current_start = line_number
                list_stack.append(str(token["list_kind"]))
                continue
            if kind == "LIST_END":
                if not list_stack or list_stack[-1] != token["list_kind"]:
                    raise DetectorEvaluationReview(
                        "TeX list environment is unbalanced"
                    )
                if len(list_stack) == 1:
                    _append_list_block(
                        output,
                        record,
                        document_format="tex",
                        heading_leaf=current_heading,
                        start_line=current_start,
                        items=current_items,
                    )
                    current_items = []
                    current_start = 0
                list_stack.pop()
                continue
            if kind == "LIST_ITEM" and len(list_stack) == 1:
                end = (
                    int(tokens[token_index + 1]["start"])
                    if token_index + 1 < len(tokens)
                    else len(line)
                )
                item_prefix = str(token.get("item_prefix", ""))
                item_text = TEX_VERB_RE.sub(
                    f" {PROTECTED_BOUNDARY_LINE} ",
                    item_prefix + line[int(token["end"]) : end],
                )
                current_items.append(_item_segments(item_text))
            elif kind == "LIST_ITEM" and not list_stack:
                raise DetectorEvaluationReview("TeX list item occurs outside a list")
        if not tokens and len(list_stack) == 1 and current_items and line.strip():
            current_items[-1].extend(_item_segments(TEX_VERB_RE.sub(
                f" {PROTECTED_BOUNDARY_LINE} ", line
            )))
    if ignored_environment:
        raise DetectorEvaluationReview("TeX code environment is unbalanced")
    if list_stack:
        raise DetectorEvaluationReview("TeX list environment is unbalanced")
    return output


def _finalize_block_ids(
    record: Mapping[str, Any], blocks: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    output: list[dict[str, Any]] = []
    for block in blocks:
        semantic = {
            "format": block["format"],
            "heading_leaf": block["heading_leaf"],
            "items": block["items"],
        }
        signature = _sha256(_canonical_json(semantic))
        counts[signature] += 1
        output.append(
            {
                **block,
                "block_id": (
                    f"{record.get('unit_id', '')}:{block['format']}:"
                    f"{signature[:16]}:{counts[signature]:03d}"
                ),
                "content_sha256": signature,
            }
        )
    return output


def _structured_blocks(record: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    value = record.get(field)
    if not isinstance(value, str):
        return []
    blocks = (
        _tex_list_blocks(record, value)
        if _record_format(record) == "tex"
        else _markdown_list_blocks(record, value)
    )
    return _finalize_block_ids(record, blocks)


def _item_han_runs(item: Sequence[str]) -> list[str]:
    runs: list[str] = []
    for segment in item:
        normalized = unicodedata.normalize("NFKC", segment)
        normalized = ZERO_WIDTH_RE.sub("", normalized)
        normalized = HAN_GAP_RE.sub("", normalized)
        runs.extend(HAN_RUN_RE.findall(normalized))
    return runs


def _block_ngrams(block: Mapping[str, Any], minimum: int, maximum: int) -> set[str]:
    ngrams: set[str] = set()
    for item in block["items"]:
        for run in _item_han_runs(item):
            for width in range(minimum, min(maximum, len(run)) + 1):
                ngrams.update(run[index : index + width] for index in range(len(run) - width + 1))
                if len(ngrams) > MAX_NGRAM_CANDIDATES:
                    raise DetectorEvaluationReview(
                        "structured n-gram candidate limit exceeded"
                    )
    return ngrams


def _evaluate_structured(
    detector: Mapping[str, Any], blocks: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    heading_pattern = re.compile(str(detector["block_role"]["heading_leaf_regex"]))
    minimum_blocks = int(detector["thresholds"]["minimum_blocks"])
    minimum_items = int(detector["thresholds"]["minimum_items_per_block"])
    minimum_han = int(detector["shared_anchor"]["minimum_han_chars"])
    maximum_han = int(detector["shared_anchor"]["maximum_han_chars"])
    minimum_coverage = int(detector["shared_anchor"]["minimum_block_coverage"])
    qualified = [
        block
        for block in blocks
        if int(block["item_count"]) >= minimum_items
        and heading_pattern.search(str(block["heading_leaf"])) is not None
    ]
    coverage: dict[str, set[str]] = defaultdict(set)
    block_by_id = {str(block["block_id"]): block for block in qualified}
    for block in qualified:
        for ngram in _block_ngrams(block, minimum_han, maximum_han):
            coverage[ngram].add(str(block["block_id"]))
    candidates = [
        (ngram, block_ids)
        for ngram, block_ids in coverage.items()
        if len(block_ids) >= minimum_coverage
    ]
    candidates.sort(key=lambda item: (-len(item[0]), -len(item[1]), item[0].encode("utf-8")))
    maximal: list[tuple[str, set[str]]] = []
    for ngram, block_ids in candidates:
        if any(
            ngram in longer and longer_ids.issuperset(block_ids)
            for longer, longer_ids in maximal
        ):
            continue
        maximal.append((ngram, block_ids))
    anchors = [
        {
            "anchor": ngram,
            "coverage": len(block_ids),
            "block_ids": sorted(block_ids),
            "unit_ids": sorted({str(block_by_id[item]["unit_id"]) for item in block_ids}),
        }
        for ngram, block_ids in maximal[:40]
    ]
    evidence_blocks = [
        {
            "block_id": str(block["block_id"]),
            "unit_id": str(block["unit_id"]),
            "format": str(block["format"]),
            "heading_leaf": str(block["heading_leaf"]),
            "start_line": int(block["start_line"]),
            "item_count": int(block["item_count"]),
            "content_sha256": str(block["content_sha256"]),
        }
        for block in qualified
    ]
    return {
        "triggered": len(qualified) >= minimum_blocks and bool(maximal),
        "qualified_block_count": len(qualified),
        "qualified_blocks": evidence_blocks,
        "shared_anchors": anchors,
    }


def _regex_group_occurrences(
    group: Mapping[str, Any], blocks: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    pattern = re.compile(str(group["regex"]))
    occurrences: list[dict[str, Any]] = []
    for block in blocks:
        for segment in _normalized_visible_segments(str(block["text"])):
            for match in pattern.finditer(segment):
                occurrences.append(
                    {
                        "unit_id": str(block["unit_id"]),
                        "paragraph_index": int(block["paragraph_index"]),
                        "matched_sha256": _sha256(match.group(0).encode("utf-8")),
                    }
                )
    return occurrences


def _evaluate_regex(
    detector: Mapping[str, Any],
    blocks: Sequence[dict[str, Any]],
    *,
    minimum_units: int = 2,
) -> dict[str, Any]:
    group_results: list[dict[str, Any]] = []
    for group in detector["pattern_groups"]:
        hits = _regex_group_occurrences(group, blocks)
        by_unit = Counter(item["unit_id"] for item in hits)
        minimum = int(group["minimum_occurrences"])
        group_results.append(
            {
                "id": str(group["id"]),
                "occurrences": len(hits),
                "minimum_occurrences": minimum,
                "units": sorted(by_unit),
                "triggered": len(hits) >= minimum,
            }
        )
    triggered_groups = [item for item in group_results if item["triggered"]]
    matched_units = {unit_id for item in triggered_groups for unit_id in item["units"]}
    return {
        "triggered": (
            len(triggered_groups) >= int(detector["minimum_groups"])
            and len(matched_units) >= minimum_units
        ),
        "group_results": group_results,
        "matched_units": sorted(matched_units),
    }


def _unique_minimal_revert_set(
    candidates: Sequence[str],
    remains_triggered: Callable[[set[str]], bool],
) -> dict[str, Any]:
    ordered = sorted(set(candidates))
    if not ordered:
        return {"status": "UNAVAILABLE", "unit_ids": [], "minimal_set_count": 0}
    if len(ordered) > MAX_ATTRIBUTION_CANDIDATES:
        return {
            "status": "AMBIGUOUS_TOO_MANY_CANDIDATES",
            "unit_ids": [],
            "minimal_set_count": 0,
        }
    for width in range(1, len(ordered) + 1):
        resolving: list[tuple[str, ...]] = []
        for candidate in itertools.combinations(ordered, width):
            if not remains_triggered(set(candidate)):
                resolving.append(candidate)
                if len(resolving) > 1:
                    break
        if not resolving:
            continue
        if len(resolving) == 1:
            return {
                "status": "UNIQUE_MINIMAL_REVERT_SET",
                "unit_ids": list(resolving[0]),
                "minimal_set_count": 1,
            }
        return {
            "status": "AMBIGUOUS_MINIMAL_REVERT_SETS",
            "unit_ids": [],
            "minimal_set_count": len(resolving),
        }
    return {"status": "UNRESOLVED", "unit_ids": [], "minimal_set_count": 0}


def _partition_key(record: Mapping[str, Any]) -> tuple[str, str]:
    unit_id = record.get("unit_id")
    if not isinstance(unit_id, str) or not unit_id.strip():
        raise DetectorEvaluationReview("PARTITION_UNIT_ID_MISSING")
    document_id = record.get("document_id")
    if not isinstance(document_id, str) or not document_id.strip():
        raise DetectorEvaluationReview("PARTITION_DOCUMENT_ID_MISSING")
    scene_value = record.get("resolved_scene")
    if not isinstance(scene_value, str) or not scene_value.strip():
        raise DetectorEvaluationReview("PARTITION_RESOLVED_SCENE_MISSING")
    resolved_scene = scene_value.strip().upper()
    if resolved_scene not in RESOLVED_SCENES:
        raise DetectorEvaluationReview("PARTITION_RESOLVED_SCENE_INVALID")
    if "scene" in record:
        compatibility_scene = record.get("scene")
        if not isinstance(compatibility_scene, str) or not compatibility_scene.strip():
            raise DetectorEvaluationReview("PARTITION_SCENE_COMPATIBILITY_INVALID")
        if compatibility_scene.strip().upper() != resolved_scene:
            raise DetectorEvaluationReview("PARTITION_SCENE_CONFLICT")
    return document_id.strip(), resolved_scene


def group_records_by_partition(
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    """Group records only when logical document and resolved scene are explicit."""
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, Mapping):
            raise DetectorEvaluationReview("PARTITION_RECORD_NOT_OBJECT")
        document_id, resolved_scene = _partition_key(record)
        grouped[(document_id, resolved_scene)].append(record)
    return dict(grouped)


def _blocks_by_unit(
    records: Sequence[Mapping[str, Any]],
    field: str,
    builder: Callable[[Mapping[str, Any], str], list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        output[str(record.get("unit_id", ""))].extend(builder(record, field))
    return dict(output)


def evaluate_detector_snapshot(
    record: Mapping[str, Any], detector: Mapping[str, Any]
) -> dict[str, Any]:
    """Evaluate one detector on one immutable document snapshot."""
    _partition_key(record)
    try:
        normalized = negative_guard_loader.normalize_detector(
            detector,
            "SNAPSHOT-EVALUATION",
            allow_legacy_regex=False,
        )
    except negative_guard_loader.NegativeGuardRegistryError as error:
        raise DetectorEvaluationReview("DETECTOR_SCHEMA_INVALID") from error
    detector_type = str(normalized["type"])
    if detector_type == "structured_repeated_list/v1":
        return _evaluate_structured(normalized, _structured_blocks(record, "text"))
    if detector_type == "regex_groups/v1":
        return _evaluate_regex(
            normalized, _paragraph_blocks(record, "text"), minimum_units=1
        )
    raise DetectorEvaluationReview(
        f"unsupported negative guard detector: {detector_type or 'missing'}"
    )


def _flatten_selected(
    unit_ids: Sequence[str],
    before: Mapping[str, Sequence[dict[str, Any]]],
    after: Mapping[str, Sequence[dict[str, Any]]],
    reverted: set[str] | None = None,
) -> list[dict[str, Any]]:
    reverted = reverted or set()
    return [
        block
        for unit_id in unit_ids
        for block in (before[unit_id] if unit_id in reverted else after[unit_id])
    ]


def audit_negative_guards(
    records: Sequence[Mapping[str, Any]],
    guards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return block-level findings without widening an ambiguous rollback set."""
    findings: list[dict[str, Any]] = []
    inherited: list[dict[str, Any]] = []
    blocking: set[str] = set()
    review_reasons: set[str] = set()
    detector_hashes: set[str] = set()
    try:
        grouped = group_records_by_partition(records)
    except DetectorEvaluationReview as error:
        return {
            "findings": [],
            "inherited_findings": [],
            "blocking_unit_ids": [],
            "review_reasons": [
                f"NEGATIVE_GUARD_PARTITION_METADATA_REVIEW:{error}"
            ],
            "active_detector_definition_sha256": [],
        }

    for guard in sorted(guards, key=lambda item: str(item.get("id", "")).encode("utf-8")):
        guard_id = str(guard.get("id", ""))
        guard_scene = str(guard.get("scene", "")).upper()
        applicable = sorted(
            [
            (key, group_records)
            for key, group_records in grouped.items()
            if guard_scene == "ALL" or guard_scene == key[1]
            ],
            key=lambda item: (item[0][0].encode("utf-8"), item[0][1]),
        )
        if not applicable:
            continue
        if guard.get("status") != "AVAILABLE":
            review_reasons.add(f"NEGATIVE_GUARD_UNAVAILABLE:{guard_id}")
            continue
        raw_detector = guard.get("detector")
        if not isinstance(raw_detector, Mapping):
            review_reasons.add(f"NEGATIVE_GUARD_DETECTOR_UNAVAILABLE:{guard_id}")
            continue
        try:
            detector = negative_guard_loader.normalize_detector(
                raw_detector,
                guard_id or "UNNAMED-GUARD",
                allow_legacy_regex=False,
            )
        except negative_guard_loader.NegativeGuardRegistryError:
            review_reasons.add(f"NEGATIVE_GUARD_DETECTOR_UNAVAILABLE:{guard_id}")
            continue
        detector_type = str(detector["type"])
        detector_sha256 = _sha256(_canonical_json(detector))
        detector_hashes.add(detector_sha256)
        if detector_type not in {"regex_groups/v1", "structured_repeated_list/v1"}:
            review_reasons.add(f"NEGATIVE_GUARD_DETECTOR_UNAVAILABLE:{guard_id}")
            continue

        for (document_id, scene), group_records in applicable:
            unit_ids = sorted(str(record.get("unit_id", "")) for record in group_records)
            builder = _structured_blocks if detector_type == "structured_repeated_list/v1" else _paragraph_blocks
            if detector_type == "structured_repeated_list/v1":
                evaluate = _evaluate_structured
            else:
                evaluate = lambda definition, blocks: _evaluate_regex(
                    definition, blocks, minimum_units=2
                )
            try:
                before_by_unit = _blocks_by_unit(
                    group_records, "before_masked", builder
                )
                after_by_unit = _blocks_by_unit(
                    group_records, "after_masked", builder
                )
                before_result = evaluate(
                    detector, _flatten_selected(unit_ids, before_by_unit, before_by_unit)
                )
                after_result = evaluate(
                    detector, _flatten_selected(unit_ids, before_by_unit, after_by_unit)
                )
            except DetectorEvaluationReview:
                review_reasons.add(
                    f"NEGATIVE_GUARD_DETECTOR_EVALUATION_REVIEW:{guard_id}:{document_id}:{scene}"
                )
                continue
            if not after_result["triggered"]:
                continue
            common = {
                "kind": "CORPUS_NEGATIVE_GUARD",
                "card_id": guard_id,
                "scene": guard_scene,
                "evaluated_scene": scene,
                "document_id": document_id,
                "detector_type": detector_type,
                "definition_sha256": detector_sha256,
            }
            if before_result["triggered"]:
                inherited.append(
                    {
                        **common,
                        "before": before_result,
                        "after": after_result,
                        "attribution_status": "INHERITED_BEFORE_THRESHOLD",
                        "units": unit_ids,
                    }
                )
                continue

            changed_units = [
                unit_id
                for unit_id in unit_ids
                if _canonical_json(before_by_unit[unit_id])
                != _canonical_json(after_by_unit[unit_id])
            ]

            def remains_triggered(reverted: set[str]) -> bool:
                return bool(
                    evaluate(
                        detector,
                        _flatten_selected(
                            unit_ids, before_by_unit, after_by_unit, reverted
                        ),
                    )["triggered"]
                )

            try:
                attribution = _unique_minimal_revert_set(
                    changed_units, remains_triggered
                )
            except DetectorEvaluationReview:
                attribution = {
                    "status": "UNRESOLVED",
                    "unit_ids": [],
                    "minimal_set_count": 0,
                }
            introduced_units = list(attribution["unit_ids"])
            finding: dict[str, Any] = {
                **common,
                "before": before_result,
                "after": after_result,
                "candidate_changed_unit_ids": changed_units,
                "introduced_unit_ids": introduced_units,
                "attribution_status": attribution["status"],
                "minimal_revert_set_count": attribution["minimal_set_count"],
            }
            if detector_type == "regex_groups/v1":
                finding.update(
                    {
                        "minimum_groups": int(detector["minimum_groups"]),
                        "before_groups": before_result["group_results"],
                        "after_groups": after_result["group_results"],
                    }
                )
            findings.append(finding)
            if attribution["status"] == "UNIQUE_MINIMAL_REVERT_SET":
                blocking.update(introduced_units)
            else:
                review_reasons.add(
                    f"NEGATIVE_GUARD_ATTRIBUTION_{attribution['status']}:"
                    f"{guard_id}:{document_id}:{scene}"
                )

    for collection in (findings, inherited):
        for finding in collection:
            finding["finding_fingerprint"] = _sha256(_canonical_json(finding))
    findings.sort(key=lambda item: item["finding_fingerprint"])
    inherited.sort(key=lambda item: item["finding_fingerprint"])
    return {
        "findings": findings,
        "inherited_findings": inherited,
        "blocking_unit_ids": sorted(blocking),
        "review_reasons": sorted(review_reasons),
        "active_detector_definition_sha256": sorted(detector_hashes),
    }
