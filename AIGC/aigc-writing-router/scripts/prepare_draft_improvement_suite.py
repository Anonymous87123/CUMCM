#!/usr/bin/env python3
"""Build deterministic dev/holdout improvement suites from a real TeX draft.

Public interface:
    python prepare_draft_improvement_suite.py SOURCE.tex --output-dir RUN \
        --suite-prefix ID --version VERSION --seed N \
        --dev-count 3 --holdout-count 3 --curator NAME --release-id ID \
        [--exclude-suite PREVIOUS_SUITE.json ...] \
        [--document-type modeling|course-notes|research]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import re

from adapter_core import sha256_file, write_json


EXCLUDED_ENVIRONMENTS = {
    "equation", "equation*", "align", "align*", "gather", "gather*",
    "table", "table*", "figure", "figure*", "itemize", "enumerate",
    "lstlisting", "minted", "verbatim", "thebibliography",
}
HEADING_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]*)\}")
BEGIN_RE = re.compile(r"\\begin\{([^{}]+)\}")
END_RE = re.compile(r"\\end\{([^{}]+)\}")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")
SUPPORTED_DOCUMENT_TYPES = {"mcm", "modeling", "course-notes", "research"}


def _strip_comment(line: str) -> str:
    output: list[str] = []
    for index, char in enumerate(line):
        if char == "%" and (index == 0 or line[index - 1] != "\\"):
            break
        output.append(char)
    return "".join(output)


def _visible_text(tex: str) -> str:
    text = COMMAND_RE.sub("", tex)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\$[^$]*\$", "", text)
    return " ".join(text.split())


def _paragraphs(source: Path, minimum_han: int, maximum_han: int) -> list[dict]:
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    heading = "未命名正文"
    stack: list[str] = []
    buffer: list[str] = []
    start_line = 0
    records: list[dict] = []

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line
        if not buffer:
            return
        raw = "\n".join(buffer).strip()
        buffer = []
        visible = _visible_text(raw)
        han = len(HAN_RE.findall(visible))
        forbidden = (
            "\\begin" in raw or "\\end" in raw or "\\item" in raw
            or "\\includegraphics" in raw or "\\bibitem" in raw
        )
        math_markers = len(re.findall(r"\$|\\\[|\\\]|\\\(|\\\)", raw))
        if forbidden or math_markers > 2 or han < minimum_han or han > maximum_han:
            return
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        records.append({
            "text": raw + "\n",
            "start_line": start_line,
            "end_line": end_line,
            "heading": heading,
            "han_chars": han,
            "sha256": digest,
        })

    for line_number, original in enumerate(lines, start=1):
        line = _strip_comment(original)
        heading_match = HEADING_RE.search(line)
        inside_excluded_environment = any(
            environment in EXCLUDED_ENVIRONMENTS for environment in stack
        )
        if heading_match and not inside_excluded_environment:
            flush(line_number - 1)
            heading = " ".join(heading_match.group(1).split()) or heading
            continue
        for match in BEGIN_RE.finditer(line):
            stack.append(match.group(1))
        excluded = any(environment in EXCLUDED_ENVIRONMENTS for environment in stack)
        if excluded:
            flush(line_number - 1)
        elif not line.strip():
            flush(line_number - 1)
        else:
            if not buffer:
                start_line = line_number
            buffer.append(line.rstrip())
        for match in END_RE.finditer(line):
            environment = match.group(1)
            if environment in stack:
                reverse_index = stack[::-1].index(environment)
                del stack[len(stack) - reverse_index - 1]
    flush(len(lines))
    return records


def _select(records: list[dict], total: int, seed: int) -> list[dict]:
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    selected: list[dict] = []
    used_headings: set[str] = set()
    for record in shuffled:
        if record["heading"] in used_headings:
            continue
        selected.append(record)
        used_headings.add(record["heading"])
        if len(selected) == total:
            return selected
    for record in shuffled:
        if record in selected:
            continue
        selected.append(record)
        if len(selected) == total:
            return selected
    raise ValueError(f"only {len(selected)} eligible paragraphs are available; need {total}")


def _load_exclusions(paths: list[Path]) -> tuple[set[str], list[dict]]:
    hashes: set[str] = set()
    locks: list[dict] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise ValueError(f"excluded suite has no cases array: {path}")
        suite_hashes: set[str] = set()
        for case in cases:
            provenance = case.get("provenance") if isinstance(case, dict) else None
            digest = provenance.get("paragraph_sha256") if isinstance(provenance, dict) else None
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"excluded suite case lacks paragraph_sha256: {path}")
            suite_hashes.add(digest)
        hashes.update(suite_hashes)
        locks.append({
            "path": str(path),
            "sha256": sha256_file(path),
            "paragraphs": len(suite_hashes),
        })
    return hashes, locks


def build(
    source: Path,
    output_dir: Path,
    suite_prefix: str,
    version: str,
    seed: int,
    dev_count: int,
    holdout_count: int,
    curator: str,
    release_id: str,
    minimum_han: int = 100,
    maximum_han: int = 900,
    exclude_suites: list[Path] | None = None,
    document_type: str = "mcm",
    require_stack_evaluation: bool = True,
) -> dict:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    if dev_count < 1 or holdout_count < 1:
        raise ValueError("dev_count and holdout_count must both be positive")
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError(f"unsupported document_type: {document_type}")
    records_before_exclusions = _paragraphs(source, minimum_han, maximum_han)
    excluded_hashes, exclusion_locks = _load_exclusions(exclude_suites or [])
    records = [record for record in records_before_exclusions if record["sha256"] not in excluded_hashes]
    selected = _select(records, dev_count + holdout_count, seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = sha256_file(source)
    suites: dict[str, dict] = {}
    for split, subset in (
        ("dev", selected[:dev_count]),
        ("holdout", selected[dev_count:]),
    ):
        source_dir = output_dir / split / "sources"
        source_dir.mkdir(parents=True)
        cases = []
        for index, record in enumerate(subset, start=1):
            case_id = f"draft-{split}-{index:02d}-{record['sha256'][:8]}"
            target = source_dir / f"{case_id}.tex"
            target.write_text(record["text"], encoding="utf-8")
            cases.append({
                "id": case_id,
                "scene": {
                    "document_type": document_type,
                    "document_format": "tex",
                    "scope": "local",
                },
                "source": str(target.relative_to(output_dir / split)).replace("\\", "/"),
                "challenge_tags": [
                    "public-judgment", "specificity", "content-density",
                    "semantic-fidelity", "paragraph-rhythm",
                ],
                "provenance": {
                    "kind": "real-draft-section",
                    "source_document": str(source),
                    "source_document_sha256": source_hash,
                    "start_line": record["start_line"],
                    "end_line": record["end_line"],
                    "heading": record["heading"],
                    "paragraph_sha256": record["sha256"],
                    "selection_seed": seed,
                    "quality_label_used_for_selection": False,
                },
            })
        suite = {
            "schema": "aigc-style-benchmark-suite/v1",
            "suite_id": f"{suite_prefix}-{split}",
            "version": version,
            "split": split,
            "benchmark_goal": "improvement",
            "providers": ["humanize-academic-chinese"],
            "required_trials": 3,
            "required_generation_evidence": ["stack_evaluation"] if require_stack_evaluation else [],
            "purpose": "Forward draft-to-candidate benchmark sampled without quality labels.",
            "cases": cases,
        }
        if split == "holdout":
            suite["holdout_policy"] = {"curator": curator, "release_id": release_id}
        suite_path = output_dir / split / "suite.json"
        write_json(suite_path, suite)
        suites[split] = {
            "suite": str(suite_path),
            "suite_sha256": sha256_file(suite_path),
            "cases": cases,
        }
    builder = Path(__file__).resolve()
    report = {
        "schema": "aigc-draft-improvement-suite-build/v1",
        "status": "pass",
        "source": {"path": str(source), "sha256": source_hash},
        "builder": {"path": str(builder), "sha256": sha256_file(builder)},
        "seed": seed,
        "document_type": document_type,
        "required_generation_evidence": ["stack_evaluation"] if require_stack_evaluation else [],
        "eligible_paragraphs_before_exclusions": len(records_before_exclusions),
        "eligible_paragraphs": len(records),
        "excluded_paragraphs": len(records_before_exclusions) - len(records),
        "exclusion_suites": exclusion_locks,
        "selection_uses_quality_labels": False,
        "dev": {
            "suite": suites["dev"]["suite"],
            "sha256": suites["dev"]["suite_sha256"],
            "cases": len(suites["dev"]["cases"]),
        },
        "holdout": {
            "suite": suites["holdout"]["suite"],
            "sha256": suites["holdout"]["suite_sha256"],
            "cases": len(suites["holdout"]["cases"]),
        },
    }
    write_json(output_dir / "build-report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite-prefix", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--dev-count", type=int, default=3)
    parser.add_argument("--holdout-count", type=int, default=3)
    parser.add_argument("--curator", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--minimum-han", type=int, default=100)
    parser.add_argument("--maximum-han", type=int, default=900)
    parser.add_argument("--exclude-suite", type=Path, action="append", default=[])
    parser.add_argument(
        "--document-type", choices=sorted(SUPPORTED_DOCUMENT_TYPES), default="mcm",
    )
    parser.add_argument("--without-stack-evaluation", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = build(
        args.source, args.output_dir, args.suite_prefix, args.version, args.seed,
        args.dev_count, args.holdout_count, args.curator, args.release_id,
        args.minimum_han, args.maximum_han, args.exclude_suite,
        args.document_type, not args.without_stack_evaluation,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"DRAFT IMPROVEMENT SUITES PASS eligible={report['eligible_paragraphs']} "
            f"dev={report['dev']['cases']} holdout={report['holdout']['cases']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
