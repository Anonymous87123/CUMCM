#!/usr/bin/env python3
"""Shared deterministic protection and capability helpers for AIGC adapters."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil


TEXT_SUFFIXES = {".txt", ".tex", ".md", ".markdown", ".rst", ".csv", ".json"}
# Keep alphanumeric identifiers (Q38, model_v2, A1) atomic during protection checks.
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?![A-Za-z0-9_])")
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?")
TEX_KEY_RE = re.compile(
    r"\\(?:label|ref|eqref|autoref|pageref|cite|citep|citet|includegraphics)\{[^{}]+\}"
)
# Inline math cannot cross a TeX source line here.  Restricting the scanner
# prevents an unmatched dollar in a comment or prose example from pairing with
# the next paragraph's opening delimiter and turning ordinary prose into a
# giant false protected span. Escaped characters remain part of the formula.
INLINE_MATH_RE = re.compile(
    r"(?<![\\$])\$(?!\$)((?:\\.|[^$\\\r\n])*)(?<![\\$])\$(?!\$)"
)
DOLLAR_DISPLAY_RE = re.compile(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", re.DOTALL)
DISPLAY_MATH_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
MATH_ENV_RE = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|cases|array)\}(.*?)"
    r"\\end\{\1\}",
    re.DOTALL,
)
CODE_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
URL_RE = re.compile(r"https?://[^\s<>{}\[\]]+")
PLACEHOLDER_RE = re.compile(r"\[\[AIGC_LOCK_\d{5}\]\]")
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
BOILERPLATE = (
    "综上所述", "值得注意的是", "不难发现", "毋庸置疑", "显而易见",
    "在当今社会", "随着社会的发展", "具有重要意义", "提供了有力支撑",
    "为后续研究奠定了基础", "it is worth noting", "in conclusion",
    "it is important to note", "in today's rapidly evolving",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_package(payload: dict, name: str) -> dict:
    matches: list[dict] = []
    key = name.casefold()
    for entry in payload.get("packages", []):
        aliases = {str(entry.get("directory", "")), str(entry.get("skill_name", ""))}
        aliases.update(str(value) for value in entry.get("aliases", []))
        aliases.update(
            str(item.get("skill_name", "")) for item in entry.get("skill_entrypoints", [])
        )
        if key in {value.casefold() for value in aliases if value}:
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError(f"package must resolve exactly once: {name!r}; matches={len(matches)}")
    return matches[0]


def read_source_text(path: Path) -> str | None:
    if path.suffix.casefold() not in TEXT_SUFFIXES:
        return None
    return path.read_text(encoding="utf-8-sig")


def _counter(pattern: re.Pattern[str], text: str, group: int | None = None) -> Counter[str]:
    if group is None:
        return Counter(pattern.findall(text))
    return Counter(match.group(group) for match in pattern.finditer(text))


def protected_inventory(text: str) -> dict[str, Counter[str]]:
    return {
        "numbers": _counter(NUMBER_RE, text),
        "tex_commands": _counter(TEX_COMMAND_RE, text),
        "tex_keys": _counter(TEX_KEY_RE, text),
        "inline_math": _counter(INLINE_MATH_RE, text, 1),
        "dollar_display_math": _counter(DOLLAR_DISPLAY_RE, text, 1),
        "display_math": _counter(DISPLAY_MATH_RE, text, 1),
        "math_environments": Counter(
            f"{match.group(1)}\n{match.group(2)}" for match in MATH_ENV_RE.finditer(text)
        ),
        "code_fences": _counter(CODE_FENCE_RE, text),
        "urls": _counter(URL_RE, text),
    }


def serialise_inventory(inventory: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        key: dict(sorted(values.items(), key=lambda item: item[0]))
        for key, values in inventory.items()
    }


def compare_inventory(
    source: dict[str, Counter[str]], candidate: dict[str, Counter[str]]
) -> list[dict]:
    findings: list[dict] = []
    for category in sorted(set(source) | set(candidate)):
        expected = source.get(category, Counter())
        actual = candidate.get(category, Counter())
        missing = expected - actual
        added = actual - expected
        if missing or added:
            findings.append({
                "severity": "error",
                "code": "PROTECTED_INVENTORY_DRIFT",
                "category": category,
                "missing": dict(missing),
                "added": dict(added),
            })
    return findings


def protect_text(text: str) -> tuple[str, list[dict]]:
    """Replace protected spans with stable tokens for a prose-only candidate branch."""
    patterns = (
        CODE_FENCE_RE, MATH_ENV_RE, DOLLAR_DISPLAY_RE, DISPLAY_MATH_RE,
        INLINE_MATH_RE, TEX_KEY_RE, URL_RE, NUMBER_RE, TEX_COMMAND_RE,
    )
    candidates: list[tuple[int, int, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.end(), match.group(0)))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, value in candidates:
        if start < last_end:
            continue
        selected.append((start, end, value))
        last_end = end

    output: list[str] = []
    spans: list[dict] = []
    cursor = 0
    for index, (start, end, value) in enumerate(selected, start=1):
        token = f"[[AIGC_LOCK_{index:05d}]]"
        output.append(text[cursor:start])
        output.append(token)
        spans.append({
            "token": token,
            "start": start,
            "end": end,
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "text": value,
        })
        cursor = end
    output.append(text[cursor:])
    return "".join(output), spans


def text_diagnostics(text: str) -> dict:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    paragraph_counts = Counter(paragraphs)
    duplicates = [
        {"count": count, "preview": paragraph[:160]}
        for paragraph, count in paragraph_counts.items()
        if count > 1 and len(paragraph) >= 30
    ]
    sentences = [item.group(0).strip() for item in SENTENCE_RE.finditer(text) if item.group(0).strip()]
    lengths = [len(re.sub(r"\s+", "", sentence)) for sentence in sentences]
    boilerplate = {
        phrase: text.casefold().count(phrase.casefold())
        for phrase in BOILERPLATE
        if phrase.casefold() in text.casefold()
    }
    return {
        "characters": len(text),
        "non_whitespace_characters": len(re.sub(r"\s+", "", text)),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "sentence_length_min": min(lengths) if lengths else 0,
        "sentence_length_max": max(lengths) if lengths else 0,
        "sentence_length_mean": round(sum(lengths) / len(lengths), 2) if lengths else 0.0,
        "duplicate_paragraphs": duplicates,
        "boilerplate_hits": boilerplate,
        "unresolved_placeholders": PLACEHOLDER_RE.findall(text),
    }


def package_preflight(root: Path, entry: dict) -> dict:
    adapter = entry.get("adapter", {})
    entrypoints = []
    for relative in adapter.get("native_entrypoints", []):
        path = root / str(entry["directory"]) / str(relative)
        entrypoints.append({"path": str(path), "exists": path.is_file()})
    runtimes = [
        {"name": str(name), "available": shutil.which(str(name)) is not None}
        for name in adapter.get("runtimes", [])
    ]
    return {
        "directory": entry.get("directory"),
        "interfaces": adapter.get("interfaces", []),
        "offline_action": adapter.get("offline_action"),
        "native_entrypoints": entrypoints,
        "runtimes": runtimes,
        "network_for_generation": bool(adapter.get("network_for_generation")),
        "native_command": adapter.get("native_command"),
        "safe_boundary": adapter.get("safe_boundary"),
        "entrypoints_present": all(item["exists"] for item in entrypoints),
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
