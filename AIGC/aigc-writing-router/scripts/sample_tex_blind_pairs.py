#!/usr/bin/env python3
"""Deterministically stratify changed TeX prose into an unseen blind-pair spec.

Public interface:
    python sample_tex_blind_pairs.py SOURCE.tex CANDIDATE.tex \
        --output-spec holdout-spec.json --total 12 --seed 20260818 \
        [--exclude-spec development-spec.json ...]

The sampler is quality-label blind: it uses only line equality, visible prose
length, section membership and a fixed seed.  It never scores either variant.
Line-preserving long-document candidates are required; otherwise use an
explicit ``prepare_tex_blind_pairs.py`` spec.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from adapter_core import sha256_file, write_json


SPEC_SCHEMA = "aigc-tex-blind-pair-spec/v1"
HEADING = re.compile(r"\\(section|subsection|subsubsection)\*?\s*\{([^{}]*)\}")
NON_PROSE = re.compile(
    r"\\(?:begin|end|label|caption|includegraphics|input|include|bibliography|addbibresource|"
    r"printbibliography|item)\b"
)


def _read(path: Path) -> list[str]:
    return path.resolve().read_text(encoding="utf-8-sig").splitlines()


def _visible_line(line: str) -> str:
    line = re.sub(r"(?<!\\)%.*$", "", line).strip()
    line = re.sub(r"^\\noindent\b", "", line).strip()
    return line


def _eligible(line: str, min_han: int) -> bool:
    visible = _visible_line(line)
    if not visible or HEADING.search(visible) or NON_PROSE.search(visible):
        return False
    if visible.startswith("\\") and not visible.startswith(("\\text", "\\emph")):
        return False
    return len(re.findall(r"[\u3400-\u9fff]", visible)) >= min_han


def _section_title(raw: str) -> str:
    value = re.sub(r"\\[A-Za-z@]+\*?", "", raw)
    return re.sub(r"[{}~]", "", value).strip() or "untitled"


def _exclude_paths(value: Path | list[Path] | None) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, Path):
        return [value]
    return list(value)


def _excluded_lines(value: Path | list[Path] | None) -> set[int]:
    paths = _exclude_paths(value)
    if not paths:
        return set()
    excluded: set[int] = set()
    for path in paths:
        payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
        if payload.get("schema") != SPEC_SCHEMA:
            raise ValueError(f"exclude spec must use {SPEC_SCHEMA}")
        for pair in payload.get("pairs", []):
            record = pair.get("source_lines", {})
            start, end = record.get("start"), record.get("end")
            if isinstance(start, int) and isinstance(end, int):
                excluded.update(range(start, end + 1))
    return excluded


def sample(
    source: Path, candidate: Path, output_spec: Path, total: int, seed: int,
    exclude_spec: Path | list[Path] | None = None, min_han: int = 60,
) -> dict[str, Any]:
    source, candidate = source.resolve(), candidate.resolve()
    if not source.is_file() or not candidate.is_file():
        raise FileNotFoundError(source if not source.is_file() else candidate)
    if total < 2 or min_han < 20:
        raise ValueError("total must be at least 2 and min_han at least 20")
    source_lines, candidate_lines = _read(source), _read(candidate)
    if len(source_lines) != len(candidate_lines):
        raise ValueError("automatic sampling requires line-preserving candidates")
    exclude_paths = _exclude_paths(exclude_spec)
    excluded = _excluded_lines(exclude_paths)
    exclude_records = [
        {"path": str(path.resolve()), "sha256": sha256_file(path.resolve())}
        for path in exclude_paths
    ]
    current_section = "preamble"
    in_abstract = False
    records: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(source_lines, candidate_lines), start=1):
        if "\\begin{abstract}" in left:
            in_abstract = True
            current_section = "摘要"
        heading = HEADING.search(left)
        if heading:
            current_section = _section_title(heading.group(2))
        if left != right and index not in excluded and _eligible(left, min_han) and _eligible(right, min_han):
            records.append({
                "line": index,
                "section": "摘要" if in_abstract else current_section,
                "source_han": len(re.findall(r"[\u3400-\u9fff]", _visible_line(left))),
                "candidate_han": len(re.findall(r"[\u3400-\u9fff]", _visible_line(right))),
            })
        if "\\end{abstract}" in left:
            in_abstract = False
            current_section = "preamble"
    if len(records) < total:
        raise ValueError(f"only {len(records)} eligible unseen changed lines; requested {total}")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["section"]].append(record)
    rng = random.Random(seed)
    strata = sorted(groups)
    rng.shuffle(strata)
    for group in groups.values():
        rng.shuffle(group)
    selected: list[dict[str, Any]] = []
    round_index = 0
    while len(selected) < total:
        added = False
        for stratum in strata:
            if round_index < len(groups[stratum]):
                selected.append(groups[stratum][round_index])
                added = True
                if len(selected) == total:
                    break
        if not added:
            break
        round_index += 1
    selected.sort(key=lambda item: item["line"])
    spec = {
        "schema": SPEC_SCHEMA,
        "source": {"path": str(source), "sha256": sha256_file(source)},
        "candidate": {"path": str(candidate), "sha256": sha256_file(candidate)},
        "sampling": {
            "method": "seeded-section-round-robin/v1",
            "seed": seed,
            "requested": total,
            "eligible": len(records),
            "selected": len(selected),
            "min_han": min_han,
            "excluded_source_lines": sorted(excluded),
            "exclude_spec": exclude_records[0] if len(exclude_records) == 1 else None,
            "quality_labels_used": False,
        },
        "pairs": [
            {
                "id": f"holdout-{position:02d}-line-{item['line']}",
                "section": item["section"],
                "source_lines": {"start": item["line"], "end": item["line"]},
                "candidate_lines": {"start": item["line"], "end": item["line"]},
                "sampling_metrics": {
                    "source_han": item["source_han"],
                    "candidate_han": item["candidate_han"],
                },
            }
            for position, item in enumerate(selected, start=1)
        ],
    }
    if len(exclude_records) > 1:
        spec["sampling"]["exclude_specs"] = exclude_records
    output_spec = output_spec.resolve()
    write_json(output_spec, spec)
    return {
        "schema": "aigc-tex-blind-sampling-report/v1",
        "status": "pass",
        "eligible": len(records),
        "selected": len(selected),
        "strata": len({item["section"] for item in selected}),
        "output_spec": str(output_spec),
        "output_sha256": sha256_file(output_spec),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output-spec", type=Path, required=True)
    parser.add_argument("--total", type=int, default=12)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--exclude-spec", type=Path, action="append")
    parser.add_argument("--min-han", type=int, default=60)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = sample(
            args.source, args.candidate, args.output_spec, args.total,
            args.seed, args.exclude_spec, args.min_han,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"schema": "aigc-tex-blind-sampling-report/v1", "status": "fail", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"TEX BLIND SAMPLE {report['status'].upper()} "
            f"eligible={report.get('eligible', 0)} selected={report.get('selected', 0)} "
            f"strata={report.get('strata', 0)}"
        )
        if report.get("error"):
            print(f"[ERROR] {report['error']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
