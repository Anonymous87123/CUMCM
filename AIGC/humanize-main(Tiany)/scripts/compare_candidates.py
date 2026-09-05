#!/usr/bin/env python3
"""Compare independent candidates against one frozen source."""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re


NUMBER_RE = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?")
KEY_RE = re.compile(r"\\(?:label|ref|eqref|autoref|cite|citep|citet)\{[^{}]+\}")
MATH_RES = (
    re.compile(r"(?<![\\$])\$(?!\$)(.*?)(?<![\\$])\$(?!\$)", re.DOTALL),
    re.compile(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", re.DOTALL),
    re.compile(r"\\\[(.*?)\\\]", re.DOTALL),
)
BOILERPLATE = (
    "综上所述", "值得注意的是", "不难发现", "显而易见", "具有重要意义",
    "提供了有力支撑", "为后续研究奠定了基础", "随着社会的发展",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(text: str) -> dict[str, Counter[str]]:
    values = {
        "numbers": Counter(NUMBER_RE.findall(text)),
        "tex_commands": Counter(COMMAND_RE.findall(text)),
        "tex_keys": Counter(KEY_RE.findall(text)),
    }
    for index, pattern in enumerate(MATH_RES, start=1):
        values[f"math_{index}"] = Counter(match.group(1) for match in pattern.finditer(text))
    return values


def drift(source: dict[str, Counter[str]], candidate: dict[str, Counter[str]]) -> list[dict]:
    findings = []
    for category in sorted(source):
        missing = source[category] - candidate.get(category, Counter())
        added = candidate.get(category, Counter()) - source[category]
        if missing or added:
            findings.append({
                "category": category,
                "missing": dict(missing),
                "added": dict(added),
            })
    return findings


def ngram_repetition(text: str, size: int = 4) -> float:
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text.casefold())
    grams = [tuple(tokens[index:index + size]) for index in range(max(0, len(tokens) - size + 1))]
    if not grams:
        return 0.0
    counts = Counter(grams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return round(repeated / len(grams), 6)


def analyse(source_text: str, candidate_path: Path, source_inventory: dict) -> dict:
    text = candidate_path.read_text(encoding="utf-8-sig")
    changes = 1.0 - SequenceMatcher(None, source_text, text).ratio()
    protected_drift = drift(source_inventory, inventory(text))
    boilerplate = {phrase: text.count(phrase) for phrase in BOILERPLATE if phrase in text}
    return {
        "path": str(candidate_path.resolve()),
        "sha256": sha256_file(candidate_path),
        "protected_status": "pass" if not protected_drift else "fail",
        "protected_drift": protected_drift,
        "change_ratio": round(changes, 6),
        "four_gram_repetition": ngram_repetition(text),
        "boilerplate_hits": boilerplate,
        "characters": len(text),
    }


def compare(source: Path, candidates: list[Path], max_change_ratio: float) -> dict:
    source_text = source.read_text(encoding="utf-8-sig")
    source_inventory = inventory(source_text)
    results = [analyse(source_text, path.resolve(), source_inventory) for path in candidates]
    eligible = [
        item for item in results
        if item["protected_status"] == "pass" and item["change_ratio"] <= max_change_ratio
    ]
    eligible.sort(key=lambda item: (
        sum(item["boilerplate_hits"].values()),
        item["four_gram_repetition"],
        item["change_ratio"],
    ))
    return {
        "schema": "tiany-candidate-comparison/v1",
        "source": {"path": str(source.resolve()), "sha256": sha256_file(source)},
        "max_change_ratio": max_change_ratio,
        "candidates": results,
        "recommended_for_human_review": eligible[0]["path"] if eligible else None,
        "human_review_required": True,
        "automatic_acceptance": False,
        "status": "pass" if eligible else "blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidates", type=Path, nargs="+")
    parser.add_argument("--max-change-ratio", type=float, default=0.45)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.source.resolve(), args.candidates, args.max_change_ratio)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.format == "json":
        print(rendered)
    else:
        print(f"TIANY CANDIDATE LAB {report['status'].upper()}")
        print(f"source_sha256={report['source']['sha256']}")
        for item in report["candidates"]:
            print(
                f"{item['path']}: protected={item['protected_status']} "
                f"change={item['change_ratio']:.3f} repeat={item['four_gram_repetition']:.3f}"
            )
        print(f"recommended_for_human_review={report['recommended_for_human_review'] or ''}")
        print("automatic_acceptance=false")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

