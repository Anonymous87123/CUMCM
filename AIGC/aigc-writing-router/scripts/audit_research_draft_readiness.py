#!/usr/bin/env python3
"""Block prose humanization when a research TeX draft is still a paper shell.

Public interface:
    python audit_research_draft_readiness.py MAIN.tex --format text|json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


REPORT_SCHEMA = "aigc-research-draft-readiness/v1"
INCLUDE_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
SECTION_RE = re.compile(r"\\section\*?\s*\{([^{}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
REF_RE = re.compile(r"\\(?:eqref|ref|autoref|cref|Cref)\s*\{([^{}]+)\}")
ABSTRACT_RE = re.compile(
    r"\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}", re.DOTALL | re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"(?i)(?<![A-Za-z])(?:todo|tbd|fixme|placeholder|xxx)(?![A-Za-z])"
    r"|\u5f85\u8865(?:\u5145|\u5199)?|\u5f85\u5b8c\u5584|\u5f85\u786e\u8ba4|\u540e\u7eed\u8865\u5145",
)
CONTRIBUTION_PROMISE_RE = re.compile(
    r"(?i)(?:main|primary|key)\s+contributions?.{0,80}(?:as follows|summari[sz]ed)"
    r"|\u4e3b\u8981\u8d21\u732e.{0,30}(?:\u5982\u4e0b|\u603b\u7ed3)",
    re.DOTALL,
)
ROADMAP_RE = re.compile(
    r"(?i)the remainder of (?:this|the) paper|the rest of (?:this|the) paper"
    r"|\u672c\u6587\u5176\u4f59\u90e8\u5206|\u4e0b\u6587\u7ed3\u6784|\\section\*?\s*\{",
)
TEMPLATE_PATTERNS = {
    "IEEE_SAMPLE_AUTHOR": re.compile(r"IEEE Publication Technology|Staff,\s*IEEE", re.IGNORECASE),
    "IEEE_SAMPLE_THANKS": re.compile(r"This paper was produced by the IEEE Publication Technology Group", re.IGNORECASE),
    "IEEE_SAMPLE_HEADER": re.compile(r"A Sample Article Using IEEEtran\.cls|Journal of \\LaTeX\\ Class Files", re.IGNORECASE),
    "IEEE_SAMPLE_HISTORY": re.compile(r"Manuscript received April 19, 2021; revised August 16, 2021", re.IGNORECASE),
}
MATH_ENV_RE = re.compile(
    r"\\begin\s*\{(?:equation\*?|align\*?|gather\*?|multline\*?|array|cases|matrix|"
    r"figure\*?|table\*?|algorithm\*?|verbatim|lstlisting)\}.*?"
    r"\\end\s*\{(?:equation\*?|align\*?|gather\*?|multline\*?|array|cases|matrix|"
    r"figure\*?|table\*?|algorithm\*?|verbatim|lstlisting)\}",
    re.DOTALL | re.IGNORECASE,
)


def _strip_comment(line: str) -> str:
    for index, char in enumerate(line):
        if char != "%":
            continue
        slashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            slashes += 1
            cursor -= 1
        if slashes % 2 == 0:
            return line[:index]
    return line


def _read_tree(main_path: Path) -> tuple[dict[Path, str], str, list[dict]]:
    files: dict[Path, str] = {}
    findings: list[dict] = []
    project_root = main_path.parent.resolve()

    def expand(path: Path, stack: tuple[Path, ...]) -> str:
        path = path.resolve()
        if path in stack:
            findings.append({
                "severity": "error", "code": "TEX_INCLUDE_CYCLE", "path": str(path),
            })
            return ""
        if path in files:
            return "\n".join(_strip_comment(line) for line in files[path].splitlines())
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            findings.append({
                "severity": "error", "code": "TEX_SOURCE_UNREADABLE",
                "path": str(path), "detail": str(exc),
            })
            return ""
        files[path] = raw
        output: list[str] = []
        for line in raw.splitlines():
            clean = _strip_comment(line)
            cursor = 0
            for match in INCLUDE_RE.finditer(clean):
                output.append(clean[cursor:match.start()])
                target = Path(match.group(1).strip())
                if not target.suffix:
                    target = target.with_suffix(".tex")
                resolved = (path.parent / target).resolve()
                try:
                    resolved.relative_to(project_root)
                except ValueError:
                    findings.append({
                        "severity": "error", "code": "TEX_INCLUDE_OUTSIDE_PROJECT",
                        "path": str(path), "target": str(resolved),
                    })
                else:
                    output.append(expand(resolved, stack + (path,)))
                cursor = match.end()
            output.append(clean[cursor:])
        return "\n".join(output)

    return files, expand(main_path, ()), findings


def _prose_metrics(text: str) -> dict[str, int]:
    prose = MATH_ENV_RE.sub(" ", text)
    prose = re.sub(r"\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\]", " ", prose, flags=re.DOTALL)
    prose = re.sub(r"\\(?:cite|citep|citet|ref|eqref|autoref|cref|Cref|label)\s*\{[^{}]*\}", " ", prose)
    prose = re.sub(r"\\[A-Za-z@]+\*?(?:\s*\[[^\]]*\])?", " ", prose)
    prose = re.sub(r"[{}~_^&]", " ", prose)
    cjk = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", prose)
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", prose)
    return {"english_words": len(words), "cjk_chars": len(cjk), "meaningful_units": len(words) + len(cjk)}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def audit(main_path: Path) -> dict:
    main_path = main_path.resolve()
    files, expanded, findings = _read_tree(main_path)
    if not main_path.is_file():
        findings.append({"severity": "error", "code": "MAIN_TEX_MISSING", "path": str(main_path)})
        return _report(main_path, files, {}, findings)

    all_raw = "\n".join(files.values())
    abstract_match = ABSTRACT_RE.search(expanded)
    abstract_metrics = _prose_metrics(abstract_match.group(1)) if abstract_match else {
        "english_words": 0, "cjk_chars": 0, "meaningful_units": 0,
    }
    if abstract_match is None:
        findings.append({"severity": "error", "code": "ABSTRACT_MISSING"})
    elif abstract_metrics["english_words"] < 80 and abstract_metrics["cjk_chars"] < 120:
        findings.append({
            "severity": "error", "code": "ABSTRACT_INCOMPLETE",
            **abstract_metrics, "minimum": "80 English words or 120 CJK characters",
        })

    sections = list(SECTION_RE.finditer(expanded))
    section_metrics: list[dict] = []
    for index, match in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(expanded)
        body = expanded[match.end():end]
        metrics = _prose_metrics(body)
        record = {
            "title": match.group(1).strip(), "line": _line_number(expanded, match.start()), **metrics,
        }
        section_metrics.append(record)
        if metrics["meaningful_units"] < 20:
            findings.append({
                "severity": "error", "code": "SECTION_EMPTY_OR_SHELL", **record,
            })
    if not sections:
        findings.append({"severity": "error", "code": "TOP_LEVEL_SECTIONS_MISSING"})

    placeholder_locations: list[dict] = []
    for path, raw in files.items():
        for line_no, line in enumerate(raw.splitlines(), start=1):
            if PLACEHOLDER_RE.search(line):
                placeholder_locations.append({"path": str(path), "line": line_no, "excerpt": line.strip()[:160]})
    if placeholder_locations:
        findings.append({
            "severity": "error", "code": "UNRESOLVED_PLACEHOLDER",
            "count": len(placeholder_locations), "locations": placeholder_locations,
        })

    label_locations: dict[str, list[int]] = defaultdict(list)
    for match in LABEL_RE.finditer(expanded):
        label_locations[match.group(1).strip()].append(_line_number(expanded, match.start()))
    duplicate_labels = {key: value for key, value in label_locations.items() if len(value) > 1}
    if duplicate_labels:
        findings.append({
            "severity": "error", "code": "DUPLICATE_LABELS", "labels": duplicate_labels,
        })
    references = {match.group(1).strip() for match in REF_RE.finditer(expanded)}
    unresolved_refs = sorted(references - set(label_locations))
    if unresolved_refs:
        findings.append({
            "severity": "error", "code": "UNRESOLVED_INTERNAL_REFERENCES", "labels": unresolved_refs,
        })

    for code, pattern in TEMPLATE_PATTERNS.items():
        matches = list(pattern.finditer(all_raw))
        if matches:
            findings.append({
                "severity": "error", "code": "TEMPLATE_IDENTITY_RESIDUE",
                "pattern": code, "count": len(matches),
            })

    contribution_match = CONTRIBUTION_PROMISE_RE.search(expanded)
    if contribution_match:
        tail = expanded[contribution_match.end():]
        boundary = ROADMAP_RE.search(tail)
        promised_body = tail[:boundary.start()] if boundary else tail[:1200]
        promised_metrics = _prose_metrics(promised_body)
        if promised_metrics["meaningful_units"] < 20:
            findings.append({
                "severity": "error", "code": "CONTRIBUTION_PROMISE_EMPTY", **promised_metrics,
            })

    metrics = {
        "tex_files": len(files),
        "sections": len(section_metrics),
        "abstract": abstract_metrics,
        "section_content": section_metrics,
        "placeholders": len(placeholder_locations),
        "duplicate_labels": len(duplicate_labels),
        "unresolved_references": len(unresolved_refs),
    }
    return _report(main_path, files, metrics, findings)


def _report(main_path: Path, files: dict[Path, str], metrics: dict, findings: list[dict]) -> dict:
    errors = sum(item.get("severity") == "error" for item in findings)
    warnings = sum(item.get("severity") == "warning" for item in findings)
    return {
        "schema": REPORT_SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "humanization_decision": "READY_FOR_PROTECTED_REWRITE" if errors == 0 else "BLOCKED_CONTENT_INCOMPLETE",
        "source": str(main_path),
        "source_files": [str(path) for path in sorted(files, key=str)],
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "findings": findings,
        "claims": {
            "paper_shell_checks_passed": errors == 0,
            "research_correctness_proven": False,
            "mathematical_validity_proven": False,
            "human_authorship_proven": False,
            "detector_outcome_predicted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.main_tex)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"RESEARCH DRAFT READINESS {report['status'].upper()} "
            f"decision={report['humanization_decision']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
