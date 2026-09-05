#!/usr/bin/env python3
"""Locate reviewable Chinese academic-style signals without classifying authorship."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from bisect import bisect_right
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_LEXICON = Path(__file__).resolve().parents[1] / "references" / "lexical-signals.json"
DEFAULT_EXTENSIONS = {".md", ".markdown", ".tex", ".txt"}
SENTENCE_BREAKS = "。！？!?；;\n"
SCENE_CHOICES = ("ALL", "AUTO", "GENERAL", "COURSE", "MODELING", "RESEARCH")
COURSE_FORMULA_CAPTION_MATCHER = "course-short-caption-formula-run-v1"
SELF_AUDIT_TRIPLET_MATCHER = "section-self-audit-triplet-v1"
QUESTION_ANALYSIS_CONTRAST_MATCHER = "question-analysis-opening-contrast-v1"
QUESTION_AVOID_MISREAD_MATCHER = "question-opening-avoid-misread-v1"
QUESTION_BENEFIT_SELF_PROOF_MATCHER = "question-benefit-self-proof-v1"
STRICT_CORPUS_POLICY_SCHEMA = "humanize-strict-corpus-policy/v4"
STRICT_SIGNAL_PREFIX = "LEX-STRICT-CORPUS-"
STRICT_ENFORCEMENT = "BLOCK_CLEAN_UNLESS_REWRITTEN_OR_POSITION_KEEP"
STRICT_TECHNICAL_EXCEPTION = "POSITION_BOUND_KEEP_REASON_REQUIRED"
STRICT_PHRASE_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]{2,12}$")
EXPECTED_STRICT_INVENTORY_ENTRIES = 1423
EXPECTED_STRICT_INVENTORY_SHA256 = (
    "3dc5cab0eefe2331707de4115bdae5f45ca3997ba6a96bae8a453d16394b9941"
)

# TeX's verbatim family is intentionally finite here.  Unknown environments
# are not guessed as code; the prepare stage's balance check will keep those
# inputs out of editable scope when they are malformed.
TEX_CODE_ENVIRONMENT_NAMES = frozenset(
    {
        "verbatim",
        "verbatim*",
        "Verbatim",
        "Verbatim*",
        "BVerbatim",
        "BVerbatim*",
        "LVerbatim",
        "LVerbatim*",
        "lstlisting",
        "minted",
        "alltt",
    }
)
TEX_NONRENDERING_ENVIRONMENT_NAMES = frozenset(
    {
        "comment",
        "filecontents",
        "filecontents*",
    }
)
TEX_OPAQUE_ENVIRONMENT_NAMES = (
    TEX_CODE_ENVIRONMENT_NAMES | TEX_NONRENDERING_ENVIRONMENT_NAMES
)
TEX_MATH_ENVIRONMENT_NAMES = frozenset(
    {
        "align",
        "align*",
        "alignat",
        "alignat*",
        "aligned",
        "alignedat",
        "array",
        "cases",
        "displaymath",
        "equation",
        "equation*",
        "gather",
        "gather*",
        "math",
        "matrix",
        "multline",
        "multline*",
        "pmatrix",
        "smallmatrix",
        "split",
        "vmatrix",
        "Vmatrix",
    }
)

_TEX_VERB_TOKEN_RE = re.compile(
    r"\\(?P<command>(?:lstinline|[A-Za-z@]*[Vv]erb))"
    r"\*?(?:\[(?:\\.|[^\]\n])*\])?"
    r"(?![A-Za-z@])"
)
_TEX_SHORT_VERB_DECL_RE = re.compile(
    r"\\(?P<command>DefineShortVerb|MakeShortVerb)\s*\{\s*\\(?P<delimiter>[^\w\s])\s*\}"
)
_TEX_SHORT_VERB_UNDECL_RE = re.compile(
    r"\\(?P<command>UndefineShortVerb|DeleteShortVerb)\s*\{\s*\\(?P<delimiter>[^\w\s])\s*\}"
)
_TEX_CUSTOM_VERB_COMMAND_DECL_RE = re.compile(
    r"\\(?:CustomVerbatimCommand|RecustomVerbatimCommand)\s*"
    r"\{\s*\\(?P<command>[A-Za-z@]+)\s*\}\s*"
    r"\{\s*(?:Verb|Verbatim)\s*\}",
    re.IGNORECASE,
)
_TEX_COMMAND_NAME_RE = re.compile(r"\\(?P<command>[A-Za-z@]+)")
_TEX_COMMAND_TOKEN_RE = re.compile(r"\\[A-Za-z@]+\*?|\\[^A-Za-z\s]")
_TEX_ENV_EVENT_RE = re.compile(
    r"\\(?P<kind>begin|end)\s*\{(?P<name>[^{}\s]+)\}", re.IGNORECASE
)
_TEX_CODE_BEGIN_RE = re.compile(
    r"\\begin\s*\{(?P<name>[^{}\s]+)\}", re.IGNORECASE
)
_TEX_SHORT_VERB_DECLARATION_COMMANDS = {
    "DefineShortVerb",
    "MakeShortVerb",
    "UndefineShortVerb",
    "DeleteShortVerb",
}


def _is_escaped(text: str, index: int) -> bool:
    slash_count = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        slash_count += 1
        index -= 1
    return slash_count % 2 == 1


def _find_unescaped_delimiter(text: str, start: int, delimiter: str) -> int | None:
    cursor = start
    while cursor < len(text):
        if text[cursor] == delimiter and not _is_escaped(text, cursor):
            return cursor
        cursor += 1
    return None


def _line_end(text: str, start: int) -> int:
    newline = text.find("\n", start)
    return len(text) if newline < 0 else newline


def _tex_comment_ranges(
    text: str,
    ignored: Sequence[tuple[int, int]] = (),
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in re.finditer("%", text):
        if _inside_ranges(match.start(), ignored)[0]:
            continue
        if _is_escaped(text, match.start()):
            continue
        ranges.append((match.start(), _line_end(text, match.start())))
    return ranges


def _tex_inline_verbatim_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Parse built-in and verb-like inline commands conservatively.

    A command whose delimiter is missing or not closed is still masked through
    its physical line and reported as a problem.  This prevents a malformed
    TeX source from exposing code to authoring while retaining later prose for
    a human review.
    """
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []
    for match in _TEX_VERB_TOKEN_RE.finditer(text):
        parsed_ranges = [(start, end) for start, end, _reason in spans]
        inside, _range_end = _inside_ranges(
            match.start(), [*occupied, *parsed_ranges]
        )
        if inside:
            continue
        if match.group("command") in _TEX_SHORT_VERB_DECLARATION_COMMANDS:
            continue
        delimiter_start = match.end()
        if delimiter_start >= len(text) or text[delimiter_start].isspace():
            end = _line_end(text, match.start())
            spans.append((match.start(), end, "latex-unclosed-inline-verbatim"))
            problems.append(f"unclosed_inline_verbatim@{match.start()}")
            continue
        delimiter = text[delimiter_start]
        command = match.group("command")
        if command not in {"verb", "Verb", "lstinline"} and delimiter in "{[(":
            # Suffix-based custom verb commands use punctuation delimiters.
            # Treating a normal braced macro such as \Adverb{...} as verbatim
            # would silently hide ordinary prose from every downstream gate.
            continue
        closing = _find_unescaped_delimiter(text, delimiter_start + 1, delimiter)
        if closing is None or "\n" in text[delimiter_start + 1 : closing if closing is not None else len(text)]:
            end = _line_end(text, match.start())
            spans.append((match.start(), end, "latex-unclosed-inline-verbatim"))
            problems.append(f"unclosed_inline_verbatim@{match.start()}")
            continue
        spans.append((match.start(), closing + 1, "latex-inline-verbatim"))
    return spans, problems


def _tex_dynamic_verbatim_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Parse scoped short-verb and declared custom-verb syntax in one pass.

    A single state machine is required because declarations inside an active
    verbatim payload are literal bytes, not executable TeX.  Group snapshots
    prevent local declarations from leaking past braces or TeX group commands.
    """
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []
    active_short: set[str] = set()
    active_custom: set[str] = set()
    groups: list[dict[str, Any]] = []
    index = 0

    def push_group(kind: str, name: str | None = None) -> None:
        groups.append(
            {
                "kind": kind,
                "name": name,
                "short": set(active_short),
                "custom": set(active_custom),
            }
        )

    def pop_group(kind: str, name: str | None = None) -> None:
        nonlocal active_short, active_custom
        if not groups:
            return
        group = groups[-1]
        if group["kind"] != kind or group["name"] != name:
            return
        groups.pop()
        active_short = set(group["short"])
        active_custom = set(group["custom"])

    def apply_global_short(delimiter: str, *, enabled: bool) -> None:
        if enabled:
            active_short.add(delimiter)
        else:
            active_short.discard(delimiter)
        # MakeShortVerb/DeleteShortVerb are explicitly global.  A group
        # snapshot therefore has to observe the new state as well, otherwise
        # popping the group would silently resurrect an old delimiter.
        for group in groups:
            saved = group["short"]
            if enabled:
                saved.add(delimiter)
            else:
                saved.discard(delimiter)

    while index < len(text):
        inside, range_end = _inside_ranges(index, occupied)
        if inside:
            index = range_end
            continue

        delimiter = text[index]
        if delimiter in active_short and not _is_escaped(text, index):
            line_end = _line_end(text, index)
            closing = index + 1
            while closing < line_end:
                if text[closing] == delimiter and not _is_escaped(text, closing):
                    break
                closing += 1
            if closing >= line_end:
                spans.append((index, line_end, "latex-short-verbatim-unclosed"))
                problems.append(f"unclosed_short_verbatim@{index}")
                index = line_end + (line_end < len(text) and text[line_end] == "\n")
            else:
                spans.append((index, closing + 1, "latex-short-verbatim"))
                index = closing + 1
            continue

        short_decl = _TEX_SHORT_VERB_DECL_RE.match(text, index)
        if short_decl is not None:
            declared_delimiter = short_decl.group("delimiter")
            if short_decl.group("command") == "MakeShortVerb":
                apply_global_short(declared_delimiter, enabled=True)
            else:
                active_short.add(declared_delimiter)
            index = short_decl.end()
            continue
        short_undecl = _TEX_SHORT_VERB_UNDECL_RE.match(text, index)
        if short_undecl is not None:
            removed_delimiter = short_undecl.group("delimiter")
            if short_undecl.group("command") == "DeleteShortVerb":
                apply_global_short(removed_delimiter, enabled=False)
            else:
                active_short.discard(removed_delimiter)
            index = short_undecl.end()
            continue
        custom_decl = _TEX_CUSTOM_VERB_COMMAND_DECL_RE.match(text, index)
        if custom_decl is not None:
            active_custom.add(custom_decl.group("command"))
            index = custom_decl.end()
            continue

        env_event = _TEX_ENV_EVENT_RE.match(text, index)
        if env_event is not None:
            environment_name = env_event.group("name")
            if env_event.group("kind").casefold() == "begin":
                push_group("environment", environment_name)
            else:
                pop_group("environment", environment_name)
            index = env_event.end()
            continue

        command_match = _TEX_COMMAND_NAME_RE.match(text, index)
        if command_match is not None:
            command = command_match.group("command")
            if command in {"begingroup", "bgroup"}:
                push_group("tex-group", command)
                index = command_match.end()
                continue
            if command in {"endgroup", "egroup"}:
                matching = "begingroup" if command == "endgroup" else "bgroup"
                pop_group("tex-group", matching)
                index = command_match.end()
                continue
            if command in active_custom:
                delimiter_start = command_match.end()
                if delimiter_start < len(text) and text[delimiter_start] == "*":
                    delimiter_start += 1
                if delimiter_start < len(text) and text[delimiter_start] == "[":
                    option_end = delimiter_start + 1
                    while option_end < len(text):
                        if (
                            text[option_end] == "]"
                            and not _is_escaped(text, option_end)
                        ):
                            option_end += 1
                            break
                        if text[option_end] == "\n":
                            break
                        option_end += 1
                    delimiter_start = option_end
                line_end = _line_end(text, index)
                if (
                    delimiter_start >= len(text)
                    or delimiter_start >= line_end
                    or text[delimiter_start].isspace()
                ):
                    spans.append(
                        (
                            index,
                            line_end,
                            "latex-unclosed-declared-inline-verbatim",
                        )
                    )
                    problems.append(f"unclosed_declared_inline_verbatim@{index}")
                    index = line_end + (
                        line_end < len(text) and text[line_end] == "\n"
                    )
                    continue
                custom_delimiter = text[delimiter_start]
                closing = delimiter_start + 1
                while closing < line_end:
                    if (
                        text[closing] == custom_delimiter
                        and not _is_escaped(text, closing)
                    ):
                        break
                    closing += 1
                if closing >= line_end:
                    spans.append(
                        (
                            index,
                            line_end,
                            "latex-unclosed-declared-inline-verbatim",
                        )
                    )
                    problems.append(f"unclosed_declared_inline_verbatim@{index}")
                    index = line_end + (
                        line_end < len(text) and text[line_end] == "\n"
                    )
                else:
                    spans.append(
                        (index, closing + 1, "latex-declared-inline-verbatim")
                    )
                    index = closing + 1
                continue
            index = command_match.end()
            continue

        if delimiter == "{" and not _is_escaped(text, index):
            push_group("brace")
        elif delimiter == "}" and not _is_escaped(text, index):
            pop_group("brace")
        index += 1

    return spans, problems


def _tex_declared_verbatim_command_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    spans, problems = _tex_dynamic_verbatim_spans(text, occupied)
    return (
        [item for item in spans if "declared-inline-verbatim" in item[2]],
        [item for item in problems if "declared_inline_verbatim" in item],
    )


def _tex_short_verbatim_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    spans, problems = _tex_dynamic_verbatim_spans(text, occupied)
    return (
        [item for item in spans if "short-verbatim" in item[2]],
        [item for item in problems if "short_verbatim" in item],
    )


def _tex_opaque_environment_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []
    cursor = 0
    while cursor < len(text):
        begin = _TEX_CODE_BEGIN_RE.search(text, cursor)
        if begin is None:
            break
        inside, range_end = _inside_ranges(begin.start(), occupied)
        if inside:
            cursor = range_end
            continue
        name = begin.group("name")
        if name not in TEX_OPAQUE_ENVIRONMENT_NAMES:
            cursor = begin.end()
            continue
        if name in TEX_CODE_ENVIRONMENT_NAMES:
            complete_reason = "latex-code-environment"
            incomplete_reason = "latex-unclosed-code-environment"
            problem_prefix = "unclosed_code_environment"
        else:
            complete_reason = "latex-nonrendering-environment"
            incomplete_reason = "latex-unclosed-nonrendering-environment"
            problem_prefix = "unclosed_nonrendering_environment"
        end_re = re.compile(rf"\\end\s*\{{{re.escape(name)}\}}")
        closing = next(
            (
                candidate
                for candidate in end_re.finditer(text, begin.end())
                if (
                    not _inside_ranges(candidate.start(), occupied)[0]
                    and not text[text.rfind("\n", 0, candidate.start()) + 1 : candidate.start()].strip(" \t\r")
                )
            ),
            None,
        )
        if closing is None:
            spans.append((begin.start(), len(text), incomplete_reason))
            problems.append(f"{problem_prefix}:{name}@{begin.start()}")
            break
        spans.append((begin.start(), closing.end(), complete_reason))
        cursor = closing.end()
    return spans, problems


def _tex_unclosed_code_environment_spans(
    text: str,
) -> tuple[list[tuple[int, int, str]], list[str]]:
    return _tex_unclosed_environment_spans(
        text,
        TEX_CODE_ENVIRONMENT_NAMES,
        "latex-unclosed-code-environment",
        "unclosed_code_environment",
        closing_must_start_line=True,
    )


def _tex_unclosed_environment_spans(
    text: str,
    names: frozenset[str],
    reason: str,
    problem_prefix: str,
    occupied: Sequence[tuple[int, int]] = (),
    *,
    closing_must_start_line: bool = False,
) -> tuple[list[tuple[int, int, str]], list[str]]:
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []
    for begin in _TEX_CODE_BEGIN_RE.finditer(text):
        if _inside_ranges(begin.start(), occupied)[0]:
            continue
        name = begin.group("name")
        if name not in names:
            continue
        end_re = re.compile(rf"\\end\s*\{{{re.escape(name)}\}}")
        closing = next(
            (
                candidate
                for candidate in end_re.finditer(text, begin.end())
                if (
                    not _inside_ranges(candidate.start(), occupied)[0]
                    and (
                        not closing_must_start_line
                        or not text[
                            text.rfind("\n", 0, candidate.start()) + 1 : candidate.start()
                        ].strip(" \t\r")
                    )
                )
            ),
            None,
        )
        if closing is None:
            spans.append((begin.start(), len(text), reason))
            problems.append(f"{problem_prefix}:{name}@{begin.start()}")
    return spans, problems


def _inside_ranges(offset: int, ranges: Sequence[tuple[int, int]]) -> tuple[bool, int]:
    for start, end in ranges:
        if start <= offset < end:
            return True, end
    return False, offset + 1


def _find_math_closing(
    text: str,
    start: int,
    delimiter: str,
    occupied: Sequence[tuple[int, int]],
) -> int | None:
    cursor = start
    while cursor < len(text):
        candidate = text.find(delimiter, cursor)
        if candidate < 0:
            return None
        inside, range_end = _inside_ranges(candidate, occupied)
        if inside:
            cursor = range_end
            continue
        if _is_escaped(text, candidate):
            cursor = candidate + len(delimiter)
            continue
        if delimiter == "$" and (
            (candidate > 0 and text[candidate - 1] == "$")
            or (candidate + 1 < len(text) and text[candidate + 1] == "$")
        ):
            cursor = candidate + 1
            continue
        return candidate
    return None


def _tex_unclosed_math_spans(
    text: str,
) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Find incomplete TeX math constructs and mask them through EOF."""
    code_spans, _code_problems = _tex_code_like_spans(text)
    occupied = [(start, end) for start, end, _reason in _merge_spans(code_spans)]
    occupied.extend(_tex_comment_ranges(text, occupied))
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []

    for opener, closer in ((r"\[", r"\]"), (r"\(", r"\)")):
        cursor = 0
        while cursor < len(text):
            start = text.find(opener, cursor)
            if start < 0:
                break
            inside, range_end = _inside_ranges(start, occupied)
            if inside or _is_escaped(text, start):
                cursor = range_end if inside else start + len(opener)
                continue
            closing = _find_math_closing(text, start + len(opener), closer, occupied)
            if closing is None:
                spans.append((start, len(text), "latex-unclosed-math"))
                problems.append(f"unclosed_math:{opener}@{start}")
                occupied.append((start, len(text)))
                break
            occupied.append((start, closing + len(closer)))
            cursor = closing + len(closer)

    index = 0
    while index < len(text):
        inside, range_end = _inside_ranges(index, occupied)
        if inside:
            index = range_end
            continue
        if text[index] != "$" or _is_escaped(text, index):
            index += 1
            continue
        delimiter = "$$" if text.startswith("$$", index) else "$"
        closing = _find_math_closing(
            text, index + len(delimiter), delimiter, occupied
        )
        if closing is None:
            spans.append((index, len(text), "latex-unclosed-math"))
            problems.append(f"unclosed_math:{delimiter}@{index}")
            break
        occupied.append((index, closing + len(delimiter)))
        index = closing + len(delimiter)

    math_env_spans, math_env_problems = _tex_unclosed_environment_spans(
        text,
        TEX_MATH_ENVIRONMENT_NAMES,
        "latex-unclosed-math-environment",
        "unclosed_math_environment",
        occupied,
    )
    spans.extend(math_env_spans)
    problems.extend(math_env_problems)
    return spans, problems


def _tex_math_like_spans(
    text: str,
    occupied: Sequence[tuple[int, int]] = (),
) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Parse complete and incomplete TeX mathematics with comment masking."""
    working = list(occupied)
    working.extend(_tex_comment_ranges(text, working))
    spans: list[tuple[int, int, str]] = []
    problems: list[str] = []

    def add(start: int, end: int, reason: str) -> None:
        spans.append((start, end, reason))
        working.append((start, end))

    environment_names = sorted(TEX_MATH_ENVIRONMENT_NAMES, key=len, reverse=True)
    environment_alternatives = "|".join(
        re.escape(name) for name in environment_names
    )
    environment_re = re.compile(
        rf"\\begin\s*\{{(?P<name>{environment_alternatives})\}}"
    )
    for begin in environment_re.finditer(text):
        if _inside_ranges(begin.start(), working)[0]:
            continue
        name = begin.group("name")
        end_re = re.compile(rf"\\end\s*\{{{re.escape(name)}\}}")
        closing = next(
            (
                candidate
                for candidate in end_re.finditer(text, begin.end())
                if not _inside_ranges(candidate.start(), working)[0]
            ),
            None,
        )
        if closing is None:
            add(begin.start(), len(text), "latex-unclosed-math-environment")
            problems.append(f"unclosed_math_environment:{name}@{begin.start()}")
        else:
            add(begin.start(), closing.end(), "latex-math-environment")

    for opener, closer, reason in (
        (r"\[", r"\]", "latex-display-math"),
        (r"\(", r"\)", "latex-inline-math"),
    ):
        cursor = 0
        while cursor < len(text):
            start = text.find(opener, cursor)
            if start < 0:
                break
            inside, range_end = _inside_ranges(start, working)
            if inside or _is_escaped(text, start):
                cursor = range_end if inside else start + len(opener)
                continue
            closing = _find_math_closing(text, start + len(opener), closer, working)
            if closing is None:
                add(start, len(text), "latex-unclosed-math")
                problems.append(f"unclosed_math:{opener}@{start}")
                break
            add(start, closing + len(closer), reason)
            cursor = closing + len(closer)

    index = 0
    while index < len(text):
        inside, range_end = _inside_ranges(index, working)
        if inside:
            index = range_end
            continue
        if text[index] != "$" or _is_escaped(text, index):
            index += 1
            continue
        delimiter = "$$" if text.startswith("$$", index) else "$"
        closing = _find_math_closing(text, index + len(delimiter), delimiter, working)
        if closing is None:
            add(index, len(text), "latex-unclosed-math")
            problems.append(f"unclosed_math:{delimiter}@{index}")
            break
        add(index, closing + len(delimiter), "latex-display-math" if delimiter == "$$" else "latex-inline-math")
        index = closing + len(delimiter)

    return spans, list(dict.fromkeys(problems))


def _tex_code_like_spans(text: str) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Return opaque TeX spans shared by scanner, prepare and invariants."""
    # The three TeX protection grammars are mutually recursive: a verb payload
    # can contain a fake environment, while a real code environment can contain
    # fake declarations.  Iterate a length-preserving mask to a fixed point so
    # each parser only sees syntax that remains executable TeX.
    def ranges(items: Sequence[tuple[int, int, str]]) -> list[tuple[int, int]]:
        return [(start, end) for start, end, _reason in _merge_spans(items)]

    comments = _tex_comment_ranges(text)
    inline_spans, inline_problems = _tex_inline_verbatim_spans(text, comments)
    dynamic_spans, dynamic_problems = _tex_dynamic_verbatim_spans(
        text, [*comments, *ranges(inline_spans)]
    )
    environment_spans, environment_problems = _tex_opaque_environment_spans(
        text, [*comments, *ranges(inline_spans), *ranges(dynamic_spans)]
    )

    for _ in range(8):
        next_comments = _tex_comment_ranges(
            text, [*ranges(inline_spans), *ranges(dynamic_spans), *ranges(environment_spans)]
        )
        next_inline, next_inline_problems = _tex_inline_verbatim_spans(
            text, [*next_comments, *ranges(dynamic_spans), *ranges(environment_spans)]
        )
        next_dynamic, next_dynamic_problems = _tex_dynamic_verbatim_spans(
            text, [*next_comments, *ranges(next_inline), *ranges(environment_spans)]
        )
        next_environment, next_environment_problems = _tex_opaque_environment_spans(
            text, [*next_comments, *ranges(next_inline), *ranges(next_dynamic)]
        )
        previous = (comments, inline_spans, dynamic_spans, environment_spans)
        current = (next_comments, next_inline, next_dynamic, next_environment)
        comments, inline_spans, dynamic_spans, environment_spans = current
        inline_problems = next_inline_problems
        dynamic_problems = next_dynamic_problems
        environment_problems = next_environment_problems
        if current == previous:
            break

    spans = [*inline_spans, *dynamic_spans, *environment_spans]
    problems = [*inline_problems, *dynamic_problems, *environment_problems]
    return spans, list(dict.fromkeys(problems))


def _tex_structure_view(text: str) -> str:
    """Mask TeX code and comments without changing source offsets."""
    code_spans, _problems = _tex_code_like_spans(text)
    code_ranges = [
        (start, end)
        for start, end, _reason in _merge_spans(code_spans)
    ]
    comment_ranges = _tex_comment_ranges(text, code_ranges)
    chars = list(text)
    for start, end in [*code_ranges, *comment_ranges]:
        for index in range(start, end):
            if chars[index] not in {"\r", "\n"}:
                chars[index] = " "
    return "".join(chars)


def _tex_group_end(
    text: str,
    start: int,
    opening: str,
    closing: str,
) -> int | None:
    if start >= len(text) or text[start] != opening:
        return None
    depth = 0
    index = start
    while index < len(text):
        if text[index] == opening and not _is_escaped(text, index):
            depth += 1
        elif text[index] == closing and not _is_escaped(text, index):
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _tex_command_call_spans(
    text: str,
    editable_style_wrappers: frozenset[str] = frozenset(),
    *,
    structure_view: str | None = None,
) -> list[tuple[int, int, str]]:
    """Return complete TeX command calls, including nested arguments.

    The structure view is parser-backed and length preserving, so commands in
    comments or verbatim payloads never become executable protection anchors.
    Explicitly editable style wrappers remain outside this protection layer.
    """
    structure = structure_view if structure_view is not None else _tex_structure_view(text)
    spans: list[tuple[int, int, str]] = []
    for match in _TEX_COMMAND_TOKEN_RE.finditer(structure):
        command = match.group(0)
        name_match = re.fullmatch(r"\\([A-Za-z@]+)\*?", command)
        if name_match and name_match.group(1) in editable_style_wrappers:
            continue
        end = match.end()
        while True:
            cursor = end
            while cursor < len(structure) and structure[cursor].isspace():
                cursor += 1
            if (
                cursor < len(structure)
                and structure[cursor] == "%"
                and not _is_escaped(structure, cursor)
            ):
                newline = structure.find("\n", cursor)
                if newline < 0:
                    end = len(structure)
                    break
                end = newline + 1
                continue
            if cursor >= len(structure) or structure[cursor] not in "[{":
                break
            opening = text[cursor]
            group_end = _tex_group_end(
                structure,
                cursor,
                opening,
                "]" if opening == "[" else "}",
            )
            if group_end is None:
                break
            end = group_end
        spans.append((match.start(), end, "tex-command-call"))
    return spans


def _tex_protection_problems(text: str, document_format: str = "markdown") -> list[str]:
    if document_format != "tex":
        return []
    _spans, code_problems = _tex_code_like_spans(text)
    _math_spans, math_problems = _tex_unclosed_math_spans(text)
    return [*code_problems, *math_problems]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def _canonical_inventory_sha256(entries: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted(entries, key=lambda entry: entry["phrase"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_strict_corpus_contract(data: dict[str, Any]) -> None:
    """Fail closed when the corpus-derived strict gate drifts or is truncated."""
    policy = data.get("strict_corpus_policy")
    inventory = data.get("strict_phrase_inventory")
    if not isinstance(policy, dict):
        raise ValueError("strict_corpus_policy must be an object")
    if not isinstance(inventory, list):
        raise ValueError("strict_phrase_inventory must be an array")
    if policy.get("schema_version") != STRICT_CORPUS_POLICY_SCHEMA:
        raise ValueError("unsupported strict_corpus_policy schema")
    if policy.get("enabled_by_default") is not True:
        raise ValueError("strict corpus policy must remain enabled by default")
    if policy.get("enforcement") != STRICT_ENFORCEMENT:
        raise ValueError("strict corpus enforcement was weakened")
    if policy.get("no_change_allowed_with_unresolved_match") is not False:
        raise ValueError("strict corpus policy must reject unresolved NO_CHANGE")
    if policy.get("protected_spans_are_exempt") is not True:
        raise ValueError("strict corpus policy must preserve protected spans")
    if policy.get("technical_term_exception") != STRICT_TECHNICAL_EXCEPTION:
        raise ValueError("strict technical-term exception must stay position-bound")
    minimum = policy.get("minimum_inventory_entries")
    declared = policy.get("inventory_entries")
    if minimum != EXPECTED_STRICT_INVENTORY_ENTRIES:
        raise ValueError(
            "strict inventory minimum does not match the reviewed release"
        )
    if declared != len(inventory) or len(inventory) != minimum:
        raise ValueError(
            f"strict inventory truncated: declared={declared} actual={len(inventory)} minimum={minimum}"
        )

    phrases: set[str] = set()
    categories: dict[str, set[str]] = {}
    numeric_fields = {
        "chat_occurrences",
        "chat_message_coverage",
        "md_occurrences",
        "md_unit_coverage",
        "md_file_coverage",
        "tex_occurrences",
        "tex_unit_coverage",
        "tex_file_coverage",
        "combined_occurrences",
        "combined_coverage",
    }
    for position, entry in enumerate(inventory, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"strict_phrase_inventory[{position}] must be an object")
        phrase = entry.get("phrase")
        category = entry.get("category")
        if not isinstance(phrase, str) or not STRICT_PHRASE_RE.fullmatch(phrase):
            raise ValueError(f"invalid strict phrase at position {position}: {phrase!r}")
        if phrase in phrases:
            raise ValueError(f"duplicate strict phrase: {phrase}")
        if not isinstance(category, str) or not category:
            raise ValueError(f"strict phrase {phrase} has no category")
        for field in numeric_fields:
            value = entry.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"strict phrase {phrase} has invalid {field}")
        if entry["combined_occurrences"] <= 0 or entry["combined_coverage"] <= 0:
            raise ValueError(f"strict phrase {phrase} has no corpus support")
        phrases.add(phrase)
        categories.setdefault(category, set()).add(phrase)

    signal_ids = policy.get("signal_ids")
    if not isinstance(signal_ids, list) or not signal_ids:
        raise ValueError("strict corpus policy has no signal ids")
    strict_signals = {
        signal.get("id"): signal
        for signal in data.get("signals", [])
        if isinstance(signal, dict)
        and isinstance(signal.get("id"), str)
        and signal["id"].startswith(STRICT_SIGNAL_PREFIX)
    }
    if set(signal_ids) != set(strict_signals):
        raise ValueError("strict signal ids do not match the policy binding")
    bound_phrases: set[str] = set()
    for signal_id, signal in strict_signals.items():
        if signal.get("severity") != "high" or signal.get("action") != "REWRITE":
            raise ValueError(f"strict signal {signal_id} must remain high/REWRITE")
        threshold = signal.get("threshold")
        if threshold != {
            "min_occurrences": 1,
            "window": "document",
            "window_chars": 0,
        }:
            raise ValueError(f"strict signal {signal_id} threshold was weakened")
        variants = signal.get("variants")
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"strict signal {signal_id} has no variants")
        signal_phrases = set(variants)
        if len(signal_phrases) != len(variants):
            raise ValueError(f"strict signal {signal_id} repeats variants")
        bound_phrases.update(signal_phrases)
    if bound_phrases != phrases:
        raise ValueError(
            "strict signal variants and strict_phrase_inventory differ: "
            f"missing={len(phrases - bound_phrases)} extra={len(bound_phrases - phrases)}"
        )
    actual_manifest = _canonical_inventory_sha256(inventory)
    declared_manifest = policy.get("inventory_manifest_sha256")
    if declared_manifest != EXPECTED_STRICT_INVENTORY_SHA256:
        raise ValueError("strict inventory policy is not bound to the reviewed release")
    if actual_manifest != EXPECTED_STRICT_INVENTORY_SHA256:
        raise ValueError("strict inventory content differs from the reviewed release")


def load_lexicon(path: str | Path = DEFAULT_LEXICON) -> dict[str, Any]:
    """Load and minimally validate the lexical signal contract."""
    lexicon_path = Path(path)
    with lexicon_path.open("r", encoding="utf-8") as handle:
        data = json.load(
            handle,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )

    _validate_strict_corpus_contract(data)

    if not isinstance(data.get("signals"), list) or not data["signals"]:
        raise ValueError("lexicon must contain a non-empty signals list")

    seen: set[str] = set()
    required = {
        "id",
        "category",
        "label",
        "variants",
        "regex",
        "scenes",
        "severity",
        "threshold",
        "exclusions",
        "action",
        "rationale",
        "positive_examples",
        "negative_examples",
        "provenance",
    }
    for signal in data["signals"]:
        missing = required - signal.keys()
        if missing:
            raise ValueError(f"{signal.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        signal_id = signal["id"]
        if signal_id in seen:
            raise ValueError(f"duplicate signal id: {signal_id}")
        seen.add(signal_id)
        if signal["action"] not in {"KEEP", "DELETE", "REWRITE", "REVIEW"}:
            raise ValueError(f"invalid action for {signal_id}: {signal['action']}")
        threshold = signal["threshold"]
        if threshold.get("window") not in {"document", "paragraph", "sentence", "line"}:
            raise ValueError(f"invalid threshold window for {signal_id}")
        if int(threshold.get("min_occurrences", 0)) < 1:
            raise ValueError(f"invalid min_occurrences for {signal_id}")
        for pattern in signal["regex"]:
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        structural_matcher = signal.get("structural_matcher")
        if structural_matcher is not None:
            if not isinstance(structural_matcher, dict):
                raise ValueError(f"invalid structural_matcher for {signal_id}")
            matcher_kind = structural_matcher.get("kind")
            course_required_matcher = {
                "kind",
                "min_pairs",
                "max_caption_hanzi",
                "max_blank_lines_before_formula",
                "caption_regex",
                "caption_exclusion_regex",
                "formula_environments",
            }
            triplet_required_matcher = {
                "kind",
                "min_sections",
                "heading_regex",
                "self_validation_regex",
                "limitation_regex",
                "outlook_regex",
            }
            question_analysis_required_matcher = {
                "kind",
                "min_sections",
                "max_opening_chars",
                "heading_regex",
                "opening_contrast_regex",
            }
            question_avoid_misread_required_matcher = {
                "kind",
                "min_sections",
                "max_opening_chars",
                "heading_regex",
                "opening_avoid_regex",
            }
            question_benefit_self_proof_required_matcher = {
                "kind",
                "min_sections",
                "max_section_chars",
                "heading_regex",
                "benefit_regex",
            }
            if matcher_kind == COURSE_FORMULA_CAPTION_MATCHER:
                if set(structural_matcher) != course_required_matcher:
                    raise ValueError(f"invalid structural_matcher contract for {signal_id}")
                if int(structural_matcher["min_pairs"]) < 2:
                    raise ValueError(f"invalid structural min_pairs for {signal_id}")
                if int(structural_matcher["max_caption_hanzi"]) < 2:
                    raise ValueError(f"invalid max_caption_hanzi for {signal_id}")
                if int(structural_matcher["max_blank_lines_before_formula"]) < 0:
                    raise ValueError(f"invalid formula adjacency for {signal_id}")
                re.compile(structural_matcher["caption_regex"])
                re.compile(structural_matcher["caption_exclusion_regex"])
                environments = structural_matcher["formula_environments"]
                if not isinstance(environments, list) or not environments:
                    raise ValueError(f"invalid formula_environments for {signal_id}")
                if any(not isinstance(item, str) or not item for item in environments):
                    raise ValueError(f"invalid formula environment for {signal_id}")
            elif matcher_kind == SELF_AUDIT_TRIPLET_MATCHER:
                if set(structural_matcher) != triplet_required_matcher:
                    raise ValueError(f"invalid structural_matcher contract for {signal_id}")
                if int(structural_matcher["min_sections"]) < 2:
                    raise ValueError(f"invalid structural min_sections for {signal_id}")
                for field in (
                    "heading_regex",
                    "self_validation_regex",
                    "limitation_regex",
                    "outlook_regex",
                ):
                    re.compile(str(structural_matcher[field]), re.IGNORECASE | re.MULTILINE)
            elif matcher_kind == QUESTION_ANALYSIS_CONTRAST_MATCHER:
                if set(structural_matcher) != question_analysis_required_matcher:
                    raise ValueError(f"invalid structural_matcher contract for {signal_id}")
                if int(structural_matcher["min_sections"]) < 3:
                    raise ValueError(f"invalid structural min_sections for {signal_id}")
                if int(structural_matcher["max_opening_chars"]) < 80:
                    raise ValueError(f"invalid structural max_opening_chars for {signal_id}")
                for field in ("heading_regex", "opening_contrast_regex"):
                    re.compile(str(structural_matcher[field]), re.IGNORECASE | re.MULTILINE)
            elif matcher_kind == QUESTION_AVOID_MISREAD_MATCHER:
                if set(structural_matcher) != question_avoid_misread_required_matcher:
                    raise ValueError(f"invalid structural_matcher contract for {signal_id}")
                if int(structural_matcher["min_sections"]) < 3:
                    raise ValueError(f"invalid structural min_sections for {signal_id}")
                if int(structural_matcher["max_opening_chars"]) < 200:
                    raise ValueError(f"invalid structural max_opening_chars for {signal_id}")
                for field in ("heading_regex", "opening_avoid_regex"):
                    re.compile(str(structural_matcher[field]), re.IGNORECASE | re.MULTILINE)
            elif matcher_kind == QUESTION_BENEFIT_SELF_PROOF_MATCHER:
                if set(structural_matcher) != question_benefit_self_proof_required_matcher:
                    raise ValueError(f"invalid structural_matcher contract for {signal_id}")
                if int(structural_matcher["min_sections"]) < 3:
                    raise ValueError(f"invalid structural min_sections for {signal_id}")
                if int(structural_matcher["max_section_chars"]) < 400:
                    raise ValueError(f"invalid structural max_section_chars for {signal_id}")
                for field in ("heading_regex", "benefit_regex"):
                    re.compile(str(structural_matcher[field]), re.IGNORECASE | re.MULTILINE)
            else:
                raise ValueError(f"unsupported structural matcher for {signal_id}")
        for exclusion in signal["exclusions"]:
            if set(exclusion) != {"scope", "regex", "reason"}:
                raise ValueError(f"invalid exclusion contract for {signal_id}")
            re.compile(exclusion["regex"], re.IGNORECASE | re.MULTILINE)
    return data


def _markdown_fence_spans(text: str) -> list[tuple[int, int, str]]:
    opening_re = re.compile(
        r"(?m)^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^\n]*(?:\n|$)"
    )
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    while cursor < len(text):
        opening = opening_re.search(text, cursor)
        if opening is None:
            break
        fence = opening.group("fence")
        closing_re = re.compile(
            rf"(?m)^[ \t]{{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*(?:\n|$)"
        )
        closing = closing_re.search(text, opening.end())
        end = closing.end() if closing is not None else len(text)
        spans.append((opening.start(), end, "markdown-fence"))
        cursor = end
    return spans


_MARKDOWN_YAML_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n.*?\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)
_MARKDOWN_INLINE_LINK_TARGET_RE = re.compile(
    r"!?\[[^\]\n]*\]\((?P<target>[^)\n]+)\)"
)
_MARKDOWN_REFERENCE_LINK_TARGET_RE = re.compile(
    r"(?m)^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?P<target><[^>\n]+>|\S+)"
)
_MARKDOWN_HEADING_STRUCTURE_RE = re.compile(
    r"(?m)^[ \t]{0,3}#{1,6}[ \t]+[^\n]+$"
)
_MARKDOWN_HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?(?:-->|\Z)")
_MARKDOWN_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^<>\n]*>")


def _markdown_structure_spans(text: str) -> list[tuple[int, int, str]]:
    """Return non-prose Markdown spans shared by preparation and validation."""

    spans: list[tuple[int, int, str]] = []
    frontmatter = _MARKDOWN_YAML_FRONTMATTER_RE.match(text)
    if frontmatter:
        spans.append((frontmatter.start(), frontmatter.end(), "yaml-frontmatter"))
    for pattern, reason in (
        (_MARKDOWN_INLINE_LINK_TARGET_RE, "markdown-link-target"),
        (_MARKDOWN_REFERENCE_LINK_TARGET_RE, "markdown-link-target"),
    ):
        spans.extend(
            (match.start("target"), match.end("target"), reason)
            for match in pattern.finditer(text)
        )
    spans.extend(
        (match.start(), match.end(), "locked-heading")
        for match in _MARKDOWN_HEADING_STRUCTURE_RE.finditer(text)
    )
    spans.extend(
        (match.start(), match.end(), "markdown-html-comment")
        for match in _MARKDOWN_HTML_COMMENT_RE.finditer(text)
    )
    spans.extend(
        (match.start(), match.end(), "markdown-html-tag")
        for match in _MARKDOWN_HTML_TAG_RE.finditer(text)
    )
    return spans


def _raw_protected_spans(
    text: str,
    document_format: str = "markdown",
) -> list[tuple[int, int, str]]:
    if document_format not in {"markdown", "tex"}:
        raise ValueError("document_format must be 'markdown' or 'tex'")
    patterns = [
        (
            "latex-verbatim-or-math-environment",
            re.compile(
                r"(?is)\\begin\{(equation\*?|align\*?|alignat\*?|alignedat|gather\*?|multline\*?|"
                r"displaymath|math|verbatim\*?|lstlisting|minted)\}.*?\\end\{\1\}"
            ),
        ),
        (
            "latex-exam-or-formal-statement-environment",
            re.compile(
                r"(?is)\\begin\{(example\*?|exercise\*?|problem\*?|question\*?|"
                r"theorem\*?|lemma\*?|proposition\*?|corollary\*?|definition\*?)\}"
                r".*?\\end\{\1\}"
            ),
        ),
        ("display-math", re.compile(r"(?s)(?<!\\)\$\$.*?(?<!\\)\$\$|\\\[.*?\\\]")),
        (
            "inline-math",
            re.compile(
                r"(?s)\\\(.*?\\\)|(?<![\\$])\$(?!\$)(?:\\.|[^$])+?(?<!\\)\$(?!\$)"
            ),
        ),
        (
            "latex-inline-math-even-escape",
            re.compile(
                r"(?s)(?<!\\)(?:\\\\)+\$(?!\$)(?:\\.|[^$])+?(?<!\\)\$(?!\$)"
            ),
        ),
        (
            "latex-inline-verbatim",
            re.compile(
                r"(?:"
                r"\\(?:verb|Verb)\*?(?P<verb_delimiter>[^\w\s]).*?(?P=verb_delimiter)"
                r"|"
                r"\\lstinline\*?(?:\[(?:\\.|[^\]\n])*\])?"
                r"(?P<lst_delimiter>[^\w\s]).*?(?P=lst_delimiter)"
                r")"
            ),
        ),
        ("inline-code", re.compile(r"(?<!`)`[^`\n]+`(?!`)")),
        ("markdown-quote", re.compile(r"(?m)^\s*>[^\n]*")),
        ("chinese-double-quote", re.compile(r"“[^”]*”|「[^」]*」|『[^』]*』")),
        ("chinese-single-quote", re.compile(r"‘[^’]*’")),
        (
            "latex-quote",
            re.compile(
                r"``[^\n]*?''|\\(?:enquote|textquote)\{(?:[^{}\n]|\{[^{}\n]*\})*\}"
            ),
        ),
        ("ascii-quote", re.compile(r'(?<!\\)"[^"\n]*?(?<!\\)"')),
    ]
    code_like: list[tuple[int, int, str]] = []
    tex_math_like: list[tuple[int, int, str]] = []
    tex_ignored: list[tuple[int, int]] = []
    tex_comments: list[tuple[int, int]] = []
    if document_format == "tex":
        code_like, _problems = _tex_code_like_spans(text)
        tex_ignored = [
            (start, end)
            for start, end, _reason in _merge_spans(code_like)
        ]
        tex_comments = _tex_comment_ranges(text, tex_ignored)
        tex_ignored.extend(tex_comments)
        tex_math_like, _math_problems = _tex_math_like_spans(text, tex_ignored)
        tex_ignored.extend(
            (start, end)
            for start, end, _reason in _merge_spans(tex_math_like)
        )

    spans = _markdown_fence_spans(text)
    for reason, pattern in patterns:
        if document_format == "tex" and reason in {
            "latex-verbatim-or-math-environment",
            "display-math",
            "inline-math",
            "latex-inline-math-even-escape",
            "latex-inline-verbatim",
        }:
            continue
        spans.extend(
            (match.start(), match.end(), reason)
            for match in pattern.finditer(text)
            if document_format != "tex"
            or not _inside_ranges(match.start(), tex_ignored)[0]
        )
    # Add the parser-backed code/verb spans, including short-verb payloads and
    # fail-closed spans for incomplete constructs.  The regexes above remain
    # useful for the broader math/quote surface; merging keeps their reasons
    # visible without exposing verbatim payloads to lexical matching.
    if document_format == "tex":
        spans.extend(
            (start, end, "latex-comment")
            for start, end in tex_comments
        )
        spans.extend(code_like)
        spans.extend(tex_math_like)
    return spans


def _merge_spans(spans: Iterable[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    merged: list[list[Any]] = []
    for start, end, reason in sorted(spans, key=lambda item: (item[0], item[1])):
        if not merged or start >= merged[-1][1]:
            merged.append([start, end, {reason}])
            continue
        merged[-1][1] = max(merged[-1][1], end)
        merged[-1][2].add(reason)
    return [(start, end, "+".join(sorted(reasons))) for start, end, reasons in merged]


class ProtectedIndex:
    """Find whether an offset falls inside code, math, comments, or quotations."""

    def __init__(
        self,
        text: str,
        document_format: str = "markdown",
        *,
        extra_spans: Sequence[tuple[int, int, str]] = (),
    ) -> None:
        self.spans = _merge_spans(
            [*_raw_protected_spans(text, document_format), *extra_spans]
        )
        self.starts = [span[0] for span in self.spans]

    def reason_at(self, offset: int) -> str | None:
        index = bisect_right(self.starts, offset) - 1
        if index >= 0:
            start, end, reason = self.spans[index]
            if start <= offset < end:
                return reason
        return None

    def reason_for_span(self, start: int, end: int) -> str | None:
        index = bisect_right(self.starts, start) - 1
        if index >= 0:
            protected_start, protected_end, reason = self.spans[index]
            if protected_start <= start and end <= protected_end:
                return reason
        return None

    def overlap_reason_for_span(self, start: int, end: int) -> str | None:
        """Return a reason when any part of a non-empty span is protected."""
        if end <= start:
            return None
        index = max(0, bisect_right(self.starts, start) - 1)
        while index < len(self.spans):
            protected_start, protected_end, reason = self.spans[index]
            if protected_start >= end:
                break
            if protected_end > start:
                return reason
            index += 1
        return None


def _signal_patterns(signal: dict[str, Any]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    if signal["variants"]:
        variants = sorted(set(signal["variants"]), key=len, reverse=True)
        patterns.append(re.compile("|".join(re.escape(item) for item in variants), re.IGNORECASE))
    patterns.extend(
        re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        for pattern in signal["regex"]
    )
    return patterns


def _deduplicate_matches(matches: Iterable[re.Match[str]]) -> list[tuple[int, int, str]]:
    raw = sorted(
        ((match.start(), match.end(), match.group(0)) for match in matches),
        key=lambda item: (item[0], -(item[1] - item[0])),
    )
    kept: list[tuple[int, int, str]] = []
    for candidate in raw:
        start, end, _ = candidate
        if any(start < old_end and end > old_start for old_start, old_end, _ in kept):
            continue
        kept.append(candidate)
    return sorted(kept)


def _physical_lines(text: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        lines.append(
            {
                "start": offset,
                "content_end": offset + len(content),
                "end": offset + len(raw),
                "content": content,
            }
        )
        offset += len(raw)
    if offset < len(text) or (text and not lines):
        lines.append(
            {
                "start": offset,
                "content_end": len(text),
                "end": len(text),
                "content": text[offset:],
            }
        )
    return lines


def _standalone_formula_end(
    lines: Sequence[dict[str, Any]],
    start_index: int,
    environments: set[str],
) -> int | None:
    stripped = str(lines[start_index]["content"]).strip()
    if stripped.startswith(r"\("):
        closing_at = stripped.find(r"\)", 2)
        if closing_at > 2 and not stripped[closing_at + 2 :].strip():
            return start_index
        return None
    if re.fullmatch(r"\$(?!\$)(?:\\.|[^$])+\$", stripped):
        return start_index

    delimiters = (("$$", "$$"), (r"\[", r"\]"))
    for opening, closing in delimiters:
        if not stripped.startswith(opening):
            continue
        remainder = stripped[len(opening):]
        closing_at = remainder.find(closing)
        if closing_at >= 0:
            if not remainder[closing_at + len(closing) :].strip():
                return start_index
            return None
        for index in range(start_index + 1, len(lines)):
            content = str(lines[index]["content"]).strip()
            closing_at = content.find(closing)
            if closing_at < 0:
                continue
            if not content[closing_at + len(closing) :].strip():
                return index
            return None
        return None

    opening = re.fullmatch(r"\\begin\{([A-Za-z*]+)\}", stripped)
    if opening is None or opening.group(1) not in environments:
        return None
    closing = rf"\end{{{opening.group(1)}}}"
    for index in range(start_index + 1, len(lines)):
        if str(lines[index]["content"]).strip() == closing:
            return index
    return None


def _course_formula_caption_occurrences(
    text: str,
    matcher: dict[str, Any],
) -> list[tuple[int, int, str]]:
    lines = _physical_lines(text)
    caption_pattern = re.compile(str(matcher["caption_regex"]))
    exclusion_pattern = re.compile(str(matcher["caption_exclusion_regex"]))
    max_hanzi = int(matcher["max_caption_hanzi"])
    max_blanks = int(matcher["max_blank_lines_before_formula"])
    environments = {str(item) for item in matcher["formula_environments"]}
    pairs: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        content = str(line["content"])
        caption = content.strip()
        if not caption_pattern.fullmatch(caption):
            continue
        hanzi_count = len(re.findall(r"[\u3400-\u9fff]", caption))
        if hanzi_count < 2 or hanzi_count > max_hanzi:
            continue
        if exclusion_pattern.search(caption):
            continue

        formula_index = index + 1
        blank_count = 0
        while formula_index < len(lines) and not str(lines[formula_index]["content"]).strip():
            blank_count += 1
            formula_index += 1
        if blank_count > max_blanks or formula_index >= len(lines):
            continue
        formula_end_index = _standalone_formula_end(lines, formula_index, environments)
        if formula_end_index is None:
            continue

        leading = len(content) - len(content.lstrip())
        trailing = len(content.rstrip())
        start = int(line["start"]) + leading
        end = int(line["start"]) + trailing
        pairs.append(
            {
                "start": start,
                "end": end,
                "matched": text[start:end],
                "formula_end": int(lines[formula_end_index]["end"]),
            }
        )

    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for pair in pairs:
        if not current:
            current = [pair]
            continue
        between = text[int(current[-1]["formula_end"]):int(pair["start"])]
        if not between.strip():
            current.append(pair)
        else:
            runs.append(current)
            current = [pair]
    if current:
        runs.append(current)

    minimum = int(matcher["min_pairs"])
    return [
        (int(pair["start"]), int(pair["end"]), str(pair["matched"]))
        for run in runs
        if len(run) >= minimum
        for pair in run
    ]


def _first_unprotected_match(
    text: str,
    pattern: re.Pattern[str],
    start: int,
    end: int,
    protected_index: ProtectedIndex,
) -> re.Match[str] | None:
    """Find a component of a compound template without borrowing protected text."""
    for match in pattern.finditer(text, start, end):
        if protected_index.overlap_reason_for_span(match.start(), match.end()) is None:
            return match
    return None


def _section_self_audit_triplet_occurrences(
    text: str,
    matcher: dict[str, Any],
    protected_index: ProtectedIndex,
) -> list[tuple[int, int, str]]:
    """Locate repeated section-level self-evaluation/limitation/outlook bundles.

    This is intentionally narrower than three independent phrase findings.  A
    section only qualifies when it contains the three ordered editorial roles,
    and the document must repeat that complete structure across sections.
    """
    heading_pattern = re.compile(str(matcher["heading_regex"]), re.IGNORECASE | re.MULTILINE)
    self_validation_pattern = re.compile(
        str(matcher["self_validation_regex"]), re.IGNORECASE | re.MULTILINE
    )
    limitation_pattern = re.compile(
        str(matcher["limitation_regex"]), re.IGNORECASE | re.MULTILINE
    )
    outlook_pattern = re.compile(str(matcher["outlook_regex"]), re.IGNORECASE | re.MULTILINE)
    headings = list(heading_pattern.finditer(text))
    complete_sections: list[tuple[int, int, str]] = []

    for index, heading in enumerate(headings):
        section_start = heading.end()
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        self_validation = _first_unprotected_match(
            text, self_validation_pattern, section_start, section_end, protected_index
        )
        if self_validation is None:
            continue
        limitation = _first_unprotected_match(
            text, limitation_pattern, self_validation.end(), section_end, protected_index
        )
        if limitation is None:
            continue
        outlook = _first_unprotected_match(
            text, outlook_pattern, limitation.end(), section_end, protected_index
        )
        if outlook is None:
            continue
        complete_sections.append(
            (self_validation.start(), self_validation.end(), self_validation.group(0))
        )

    if len(complete_sections) < int(matcher["min_sections"]):
        return []
    return complete_sections


def _question_analysis_opening_contrast_occurrences(
    text: str,
    matcher: dict[str, Any],
    protected_index: ProtectedIndex,
) -> list[tuple[int, int, str]]:
    """Locate repeated question-analysis openings built from one correction shell.

    The matcher deliberately treats this as a section-role pattern, not as a
    general ban on `不是……而是……`: a real correction is common in both
    research writing and course explanations.
    """
    heading_pattern = re.compile(str(matcher["heading_regex"]), re.IGNORECASE | re.MULTILINE)
    contrast_pattern = re.compile(
        str(matcher["opening_contrast_regex"]), re.IGNORECASE | re.MULTILINE
    )
    headings = list(heading_pattern.finditer(text))
    complete_sections: list[tuple[int, int, str]] = []
    max_opening_chars = int(matcher["max_opening_chars"])

    for index, heading in enumerate(headings):
        section_start = heading.end()
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        opening_end = min(section_end, section_start + max_opening_chars)
        contrast = _first_unprotected_match(
            text, contrast_pattern, section_start, opening_end, protected_index
        )
        if contrast is not None:
            complete_sections.append((contrast.start(), contrast.end(), contrast.group(0)))

    if len(complete_sections) < int(matcher["min_sections"]):
        return []
    return complete_sections


def _question_opening_avoid_misread_occurrences(
    text: str,
    matcher: dict[str, Any],
    protected_index: ProtectedIndex,
) -> list[tuple[int, int, str]]:
    """Locate repeated ``为避免...`` shells at problem-model openings.

    The section role and opening limit are intentional.  A single safety
    qualification is often substantive; only repeated problem openings are
    returned for review.
    """
    heading_pattern = re.compile(str(matcher["heading_regex"]), re.IGNORECASE | re.MULTILINE)
    avoid_pattern = re.compile(
        str(matcher["opening_avoid_regex"]), re.IGNORECASE | re.MULTILINE
    )
    headings = list(heading_pattern.finditer(text))
    complete_sections: list[tuple[int, int, str]] = []
    max_opening_chars = int(matcher["max_opening_chars"])

    for index, heading in enumerate(headings):
        section_start = heading.end()
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        opening_end = min(section_end, section_start + max_opening_chars)
        avoid = _first_unprotected_match(
            text, avoid_pattern, section_start, opening_end, protected_index
        )
        if avoid is not None:
            complete_sections.append((avoid.start(), avoid.end(), avoid.group(0)))

    if len(complete_sections) < int(matcher["min_sections"]):
        return []
    return complete_sections


def _question_benefit_self_proof_occurrences(
    text: str,
    matcher: dict[str, Any],
    protected_index: ProtectedIndex,
) -> list[tuple[int, int, str]]:
    """Locate repeated ``这样写/这样处理`` benefit or completion shells.

    This is a document-level structural warning, not a deletion rule: the
    matched span is only the editorial-looking wrapper and the underlying
    result, limitation, or recommendation remains for human review.
    """
    heading_pattern = re.compile(str(matcher["heading_regex"]), re.IGNORECASE | re.MULTILINE)
    benefit_pattern = re.compile(
        str(matcher["benefit_regex"]), re.IGNORECASE | re.MULTILINE
    )
    headings = list(heading_pattern.finditer(text))
    complete_sections: list[tuple[int, int, str]] = []
    max_section_chars = int(matcher["max_section_chars"])

    for index, heading in enumerate(headings):
        section_start = heading.end()
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        bounded_end = min(section_end, section_start + max_section_chars)
        benefit = _first_unprotected_match(
            text, benefit_pattern, section_start, bounded_end, protected_index
        )
        if benefit is not None:
            complete_sections.append((benefit.start(), benefit.end(), benefit.group(0)))

    if len(complete_sections) < int(matcher["min_sections"]):
        return []
    return complete_sections


def _structural_matches(
    text: str,
    matcher: dict[str, Any],
    protected_index: ProtectedIndex,
) -> list[tuple[int, int, str]]:
    if matcher["kind"] == COURSE_FORMULA_CAPTION_MATCHER:
        return _course_formula_caption_occurrences(text, matcher)
    if matcher["kind"] == SELF_AUDIT_TRIPLET_MATCHER:
        return _section_self_audit_triplet_occurrences(text, matcher, protected_index)
    if matcher["kind"] == QUESTION_ANALYSIS_CONTRAST_MATCHER:
        return _question_analysis_opening_contrast_occurrences(text, matcher, protected_index)
    if matcher["kind"] == QUESTION_AVOID_MISREAD_MATCHER:
        return _question_opening_avoid_misread_occurrences(text, matcher, protected_index)
    if matcher["kind"] == QUESTION_BENEFIT_SELF_PROOF_MATCHER:
        return _question_benefit_self_proof_occurrences(text, matcher, protected_index)
    raise ValueError(f"unsupported structural matcher: {matcher['kind']}")


def _bounded_span(text: str, offset: int, separators: str) -> tuple[int, int]:
    left = max((text.rfind(char, 0, offset) for char in separators), default=-1) + 1
    right_candidates = [text.find(char, offset) for char in separators]
    right_candidates = [position for position in right_candidates if position >= 0]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return left, right


def _paragraph_span(text: str, offset: int) -> tuple[int, int]:
    separators = list(re.finditer(r"(?:\r?\n\s*){2,}", text))
    start = 0
    end = len(text)
    for separator in separators:
        if separator.end() <= offset:
            start = separator.end()
        elif separator.start() >= offset:
            end = separator.start()
            break
    return start, end


def _scope_span(text: str, offset: int, scope: str) -> tuple[int, int]:
    if scope == "document":
        return 0, len(text)
    if scope == "paragraph":
        return _paragraph_span(text, offset)
    if scope == "sentence":
        return _bounded_span(text, offset, SENTENCE_BREAKS)
    if scope == "line":
        return _bounded_span(text, offset, "\n")
    raise ValueError(f"unsupported scope: {scope}")


def _scope_bounds(text: str, start: int, end: int, scope: str) -> tuple[int, int]:
    if scope == "match":
        return start, end
    if scope == "context":
        return max(0, start - 100), min(len(text), end + 100)
    return _scope_span(text, start, scope)


def _exclusion_reason(
    text: str,
    start: int,
    end: int,
    signal: dict[str, Any],
) -> str | None:
    for exclusion in signal["exclusions"]:
        scope_start, scope_end = _scope_bounds(text, start, end, exclusion["scope"])
        scoped = text[scope_start:scope_end]
        for match in re.finditer(exclusion["regex"], scoped, re.IGNORECASE | re.MULTILINE):
            absolute_start = scope_start + match.start()
            absolute_end = scope_start + match.end()
            if absolute_start < end and absolute_end > start:
                return exclusion["reason"]
    return None


def _line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_break = text.rfind("\n", 0, offset)
    column = offset - last_break
    return line, column


def _context(text: str, start: int, end: int, radius: int = 70) -> str:
    snippet = text[max(0, start - radius):min(len(text), end + radius)]
    return re.sub(r"\s+", " ", snippet).strip()


def _window_key(text: str, offset: int, scope: str) -> tuple[int, int]:
    return _scope_span(text, offset, scope)


def _qualifying_counts(
    text: str,
    occurrences: Sequence[dict[str, Any]],
    threshold: dict[str, Any],
) -> list[int]:
    scope = threshold["window"]
    max_chars = int(threshold.get("window_chars", 0) or 0)
    distinct_scope = threshold.get("count_distinct_by")
    if distinct_scope not in {None, "paragraph", "sentence", "line"}:
        raise ValueError(f"unsupported count_distinct_by: {distinct_scope}")
    keys = [_window_key(text, item["start"], scope) for item in occurrences]
    counts: list[int] = []
    for index, occurrence in enumerate(occurrences):
        key = keys[index]
        neighbors = [
            item
            for other_index, item in enumerate(occurrences)
            if keys[other_index] == key
            and (not max_chars or abs(item["start"] - occurrence["start"]) <= max_chars)
        ]
        if distinct_scope:
            counts.append(
                len({_window_key(text, item["start"], distinct_scope) for item in neighbors})
            )
        else:
            counts.append(len(neighbors))
    return counts


def _finding(
    *,
    text: str,
    file: str,
    scene: str,
    signal: dict[str, Any],
    occurrence: dict[str, Any],
    count: int,
    protected: bool,
    protection: str | None,
    excluded: bool = False,
    exclusion: str | None = None,
) -> dict[str, Any]:
    line, column = _line_column(text, occurrence["start"])
    return {
        "start_char": occurrence["start"],
        "end_char": occurrence["end"],
        "file": file,
        "line": line,
        "column": column,
        "matched": occurrence["matched"],
        "context": _context(text, occurrence["start"], occurrence["end"]),
        "count": count,
        "action": "KEEP" if protected or excluded else signal["action"],
        "signal_id": signal["id"],
        "category": signal["category"],
        "label": signal["label"],
        "scene": scene,
        "severity": signal["severity"],
        "candidate": not protected and not excluded,
        "protected": protected,
        "protection": protection,
        "excluded": excluded,
        "exclusion": exclusion,
        "rationale": signal["rationale"],
        # Keep structural diagnostics visible when an exact span is also
        # matched by a broader phrase signal.  This is removed before the
        # public result is returned.
        "_structural": signal.get("structural_matcher") is not None,
    }


def _span_contains_or_equals(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return true only for nested/equal spans, not merely touching spans."""
    return (
        left["start_char"] <= right["start_char"]
        and left["end_char"] >= right["end_char"]
    ) or (
        right["start_char"] <= left["start_char"]
        and right["end_char"] >= left["end_char"]
    )


def _deduplicate_cross_signal_findings(
    findings: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge nested findings while retaining every signal as provenance.

    A strict phrase is often nested in a longer ordinary signal (for example a
    legacy ``值得注意`` finding inside ``值得注意的是``).  Returning both makes
    the caller perform the same edit twice; dropping the strict signal loses the
    hard-rewrite obligation.  Keep the longest candidate as the visible finding,
    attach all nested signal IDs/matches, and promote the action to ``REWRITE``
    whenever any merged member is a strict candidate.  Protected/excluded hits
    stay independent because they describe a different decision surface.
    """
    candidates = [
        dict(item)
        for item in findings
        if not item.get("protected") and not item.get("excluded")
    ]
    untouched = [
        dict(item)
        for item in findings
        if item.get("protected") or item.get("excluded")
    ]
    candidates.sort(
        key=lambda item: (
            int(item["start_char"]),
            -int(item["end_char"] - item["start_char"]),
            str(item.get("signal_id", "")),
        )
    )
    components: list[list[dict[str, Any]]] = []
    for finding in candidates:
        matching: list[int] = []
        for index, component in enumerate(components):
            if any(
                _span_contains_or_equals(finding, member) for member in component
            ):
                matching.append(index)
        if not matching:
            components.append([finding])
            continue
        target = components[matching[0]]
        target.append(finding)
        for index in reversed(matching[1:]):
            target.extend(components.pop(index))

    merged: list[dict[str, Any]] = []
    for component in components:
        winner = max(
            component,
            key=lambda item: (
                int(item["end_char"] - item["start_char"]),
                int(item.get("_structural", False)),
                int(str(item.get("signal_id", "")).startswith(STRICT_SIGNAL_PREFIX)),
                int(item.get("severity") == "high"),
                str(item.get("signal_id", "")),
            ),
        )
        signal_ids = sorted({str(item.get("signal_id", "")) for item in component})
        strict_present = any(
            str(item.get("signal_id", "")).startswith(STRICT_SIGNAL_PREFIX)
            and item.get("candidate")
            for item in component
        )
        if len(component) > 1:
            winner["merged_signal_ids"] = signal_ids
            winner["merged_matches"] = sorted(
                {
                    str(item.get("matched", ""))
                    for item in component
                },
                key=lambda item: (-len(item), item),
            )
            winner["merged_finding_count"] = len(component)
            winner["merged_strict_signal_ids"] = sorted(
                signal_id
                for signal_id in signal_ids
                if signal_id.startswith(STRICT_SIGNAL_PREFIX)
            )
        if strict_present:
            winner["action"] = "REWRITE"
            winner["severity"] = "high"
            winner["strict_overlap_requires_rewrite"] = True
        winner["count"] = max(int(item.get("count", 1)) for item in component)
        merged.append(winner)
    result = [*merged, *untouched]
    for item in result:
        item.pop("_structural", None)
    return sorted(
        result,
        key=lambda item: (
            str(item.get("file", "")),
            int(item.get("line", 0)),
            int(item.get("column", 0)),
            int(item.get("start_char", 0)),
            str(item.get("signal_id", "")),
        ),
    )


def scan_text_with_offsets(
    text: str,
    *,
    file: str = "<memory>",
    scene: str = "ALL",
    lexicon: dict[str, Any] | None = None,
    include_protected: bool = False,
    include_excluded: bool = False,
    document_format: str | None = None,
) -> list[dict[str, Any]]:
    """Return candidates with exact internal character offsets."""
    scene = scene.upper()
    if scene not in SCENE_CHOICES:
        raise ValueError(f"unsupported scene: {scene}")
    lexicon = lexicon or load_lexicon()
    if document_format is None:
        suffix = Path(file).suffix.lower() if file and file != "<memory>" else ""
        document_format = "tex" if suffix in {".tex", ".ltx"} else "markdown"
    elif document_format not in {"markdown", "tex"}:
        raise ValueError("document_format must be 'markdown' or 'tex'")
    protected_index = ProtectedIndex(text, document_format=document_format)
    findings: list[dict[str, Any]] = []

    for signal in lexicon["signals"]:
        if (
            scene not in {"ALL", "AUTO"}
            and "ALL" not in signal["scenes"]
            and scene not in signal["scenes"]
        ):
            continue
        structural_matcher = signal.get("structural_matcher")
        if structural_matcher is not None:
            matches = _structural_matches(text, structural_matcher, protected_index)
        else:
            raw_matches: list[re.Match[str]] = []
            for pattern in _signal_patterns(signal):
                raw_matches.extend(pattern.finditer(text))
            matches = _deduplicate_matches(raw_matches)

        candidates: list[dict[str, Any]] = []
        protected_hits: list[tuple[dict[str, Any], str]] = []
        excluded_hits: list[tuple[dict[str, Any], str]] = []
        for start, end, matched in matches:
            occurrence = {"start": start, "end": end, "matched": matched}
            protection = protected_index.reason_for_span(start, end)
            if protection:
                protected_hits.append((occurrence, protection))
                continue
            exclusion = _exclusion_reason(text, start, end, signal)
            if exclusion:
                excluded_hits.append((occurrence, exclusion))
                continue
            candidates.append(occurrence)

        counts = _qualifying_counts(text, candidates, signal["threshold"])
        minimum = int(signal["threshold"]["min_occurrences"])
        for occurrence, count in zip(candidates, counts):
            if count >= minimum:
                findings.append(
                    _finding(
                        text=text,
                        file=file,
                        scene=scene,
                        signal=signal,
                        occurrence=occurrence,
                        count=count,
                        protected=False,
                        protection=None,
                    )
                )
        if include_protected:
            for occurrence, protection in protected_hits:
                findings.append(
                    _finding(
                        text=text,
                        file=file,
                        scene=scene,
                        signal=signal,
                        occurrence=occurrence,
                        count=1,
                        protected=True,
                        protection=protection,
                    )
                )
        if include_excluded:
            for occurrence, exclusion in excluded_hits:
                findings.append(
                    _finding(
                        text=text,
                        file=file,
                        scene=scene,
                        signal=signal,
                        occurrence=occurrence,
                        count=1,
                        protected=False,
                        protection=None,
                        excluded=True,
                        exclusion=exclusion,
                    )
                )

    return _deduplicate_cross_signal_findings(findings)


def scan_text(
    text: str,
    *,
    file: str = "<memory>",
    scene: str = "ALL",
    lexicon: dict[str, Any] | None = None,
    include_protected: bool = False,
    include_excluded: bool = False,
    document_format: str | None = None,
) -> list[dict[str, Any]]:
    """Return the stable public finding view without internal offsets."""
    findings = scan_text_with_offsets(
        text,
        file=file,
        scene=scene,
        lexicon=lexicon,
        include_protected=include_protected,
        include_excluded=include_excluded,
        document_format=document_format,
    )
    return [
        {key: value for key, value in finding.items() if key not in {"start_char", "end_char"}}
        for finding in findings
    ]


def scan_file(
    path: str | Path,
    *,
    scene: str = "ALL",
    lexicon: dict[str, Any] | None = None,
    include_protected: bool = False,
    include_excluded: bool = False,
) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8-sig")
    return scan_text(
        text,
        file=str(source),
        scene=scene,
        lexicon=lexicon,
        include_protected=include_protected,
        include_excluded=include_excluded,
    )


def collect_paths(paths: Sequence[str], extensions: set[str] | None = None) -> list[Path]:
    extensions = extensions or DEFAULT_EXTENSIONS
    collected: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            collected.add(path.resolve())
        elif path.is_dir():
            collected.update(
                item.resolve()
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in extensions
            )
        else:
            raise FileNotFoundError(raw)
    return sorted(collected, key=lambda item: str(item).lower())


OUTPUT_FIELDS = (
    "file",
    "line",
    "column",
    "matched",
    "context",
    "count",
    "action",
    "signal_id",
    "category",
    "label",
    "scene",
    "severity",
    "candidate",
    "protected",
    "protection",
    "excluded",
    "exclusion",
    "rationale",
)


def render_output(
    findings: Sequence[dict[str, Any]],
    *,
    output_format: str,
    notice: str,
    coverage: dict[str, Any] | None = None,
) -> str:
    if output_format == "json":
        payload = {
            "notice": notice,
            "finding_count": len(findings),
            "candidate_count": sum(bool(item["candidate"]) for item in findings),
            "findings": list(findings),
            "coverage": coverage
            or {
                "status": "NOT_REPORTED",
                "requested_count": 0,
                "scanned_count": 0,
                "skipped_count": 0,
                "requested_files": [],
                "scanned_files": [],
                "skipped_files": [],
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(findings)
        return buffer.getvalue()
    if output_format == "text":
        lines = [f"说明：{notice}"]
        for item in findings:
            state = "受保护" if item["protected"] else "已豁免" if item["excluded"] else "候选"
            lines.append(
                f"{item['file']}:{item['line']}:{item['column']} "
                f"[{item['signal_id']}/{item['severity']}/{item['action']}/{state}] "
                f"{item['matched']} | count={item['count']} | {item['context']}"
            )
        return "\n".join(lines) + "\n"
    raise ValueError(f"unsupported output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="定位中文学术文本中的模板词和句壳候选；不判断作者身份。"
    )
    parser.add_argument("paths", nargs="+", help="UTF-8 文本文件或目录")
    parser.add_argument(
        "--scene",
        type=str.upper,
        choices=SCENE_CHOICES,
        default="ALL",
        help="大小写不敏感；AUTO 扫描全部场景信号，GENERAL 只扫描通用信号",
    )
    parser.add_argument("--format", choices=("json", "csv", "text"), default="text", dest="output_format")
    parser.add_argument("--output", help="输出文件；省略时写到标准输出")
    parser.add_argument("--lexicon", default=str(DEFAULT_LEXICON), help="lexical-signals.json 路径")
    parser.add_argument("--include-protected", action="store_true", help="显示代码、数学、注释和引文中的受保护命中")
    parser.add_argument("--include-excluded", action="store_true", help="显示因技术上下文而豁免的命中")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        lexicon = load_lexicon(args.lexicon)
        paths = collect_paths(args.paths)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    findings: list[dict[str, Any]] = []
    scanned: list[str] = []
    skipped: list[str] = []
    for path in paths:
        try:
            findings.extend(
                scan_file(
                    path,
                    scene=args.scene,
                    lexicon=lexicon,
                    include_protected=args.include_protected,
                    include_excluded=args.include_excluded,
                )
            )
            scanned.append(str(path))
        except UnicodeDecodeError:
            skipped.append(str(path))

    coverage = {
        "status": "REVIEW" if skipped else "PASS",
        "requested_count": len(paths),
        "scanned_count": len(scanned),
        "skipped_count": len(skipped),
        "requested_files": [str(path) for path in paths],
        "scanned_files": scanned,
        "skipped_files": skipped,
    }
    rendered = render_output(
        findings,
        output_format=args.output_format,
        notice=lexicon["output_policy"],
        coverage=coverage,
    )
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="")
    else:
        sys.stdout.write(rendered)
    for path in skipped:
        print(f"跳过非 UTF-8 或乱码文件：{path}", file=sys.stderr)
    return 2 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
