#!/usr/bin/env python3
"""Audit explicit manuscript/code mathematics contracts.

The contract makes selected semantic obligations machine-checkable; it does not
prove the model.  Public interface:
    python audit_math_semantics.py <main.tex> --contract <contract.json>
        --format text|json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

from audit_manuscript import read_tex_tree


def patterns_missing(text: str, patterns: object) -> list[str]:
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, list):
        return []
    return [str(pattern) for pattern in patterns if not re.search(str(pattern), text, re.I | re.S)]


def resolve_text(base: Path, path_literal: object, cache: dict[Path, str]) -> str:
    path = Path(str(path_literal))
    if not path.is_absolute():
        path = (base / path).resolve()
    if path not in cache:
        cache[path] = path.read_text(encoding="utf-8-sig", errors="replace")
    return cache[path]


def recompute(operation: str, values: list[float]) -> float:
    if not values:
        raise ValueError("recheck values cannot be empty")
    if operation == "literal":
        if len(values) != 1:
            raise ValueError("literal recheck requires exactly one value")
        return values[0]
    if operation == "sum":
        return sum(values)
    if operation == "mean":
        return sum(values) / len(values)
    if operation == "rmse":
        return math.sqrt(sum(value * value for value in values) / len(values))
    if operation == "max_abs":
        return max(abs(value) for value in values)
    raise ValueError(f"unsupported recheck operation: {operation}")


def recheck_values(item: dict, base: Path) -> list[float]:
    if "values" in item:
        return [float(value) for value in item.get("values", [])]
    source_literal = item.get("source")
    if not source_literal:
        return []
    source = Path(str(source_literal))
    if not source.is_absolute():
        source = (base / source).resolve()
    if item.get("csv_column"):
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        filters = item.get("csv_filters", {})
        if filters:
            if not isinstance(filters, dict):
                raise ValueError("csv_filters must be an object")
            rows = [
                row for row in rows
                if all(str(row.get(str(key), "")) == str(expected) for key, expected in filters.items())
            ]
        return [float(row[str(item["csv_column"])]) for row in rows]
    if item.get("json_path"):
        value: object = json.loads(source.read_text(encoding="utf-8-sig"))
        for key in str(item["json_path"]).split("."):
            value = value[int(key)] if isinstance(value, list) else value[key]  # type: ignore[index]
        return [float(entry) for entry in value] if isinstance(value, list) else [float(value)]
    raise ValueError("source recheck requires csv_column or json_path")


def audit(main_tex: Path, contract_path: Path) -> dict:
    text = read_tex_tree(main_tex)
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    base = contract_path.parent
    cache: dict[Path, str] = {}
    findings: list[dict] = []

    for symbol in contract.get("symbols", []):
        name = str(symbol.get("name", "unnamed"))
        definition_pattern = str(symbol.get("definition_pattern", ""))
        use_pattern = str(symbol.get("use_pattern", ""))
        definition = re.search(definition_pattern, text, re.I | re.S) if definition_pattern else None
        if not definition:
            findings.append({"severity": "error", "code": "SYMBOL_DEFINITION_MISSING", "item": name})
            continue
        if use_pattern:
            uses = list(re.finditer(use_pattern, text, re.I | re.S))
            # A use regex can include TeX delimiters while the definition regex
            # starts at the symbol itself (for example ``$H=28800$``).  Treat
            # overlapping matches as the same defining occurrence; only a use
            # that ends before the definition is genuinely out of order.
            if uses and uses[0].end() <= definition.start():
                findings.append({
                    "severity": "error",
                    "code": "SYMBOL_USED_BEFORE_DEFINITION",
                    "item": name,
                })

    for group_name in ("units", "objectives"):
        for item in contract.get(group_name, []):
            name = str(item.get("name", "unnamed"))
            missing = patterns_missing(text, item.get("manuscript_patterns", []))
            for pattern in missing:
                findings.append({
                    "severity": "error",
                    "code": f"{group_name[:-1].upper()}_MANUSCRIPT_PATTERN_MISSING",
                    "item": name,
                    "pattern": pattern,
                })
            for pattern in item.get("forbidden_patterns", []):
                if re.search(str(pattern), text, re.I | re.S):
                    findings.append({
                        "severity": "error",
                        "code": f"{group_name[:-1].upper()}_FORBIDDEN_PATTERN",
                        "item": name,
                        "pattern": str(pattern),
                    })
            if item.get("code_path"):
                try:
                    code = resolve_text(base, item["code_path"], cache)
                except FileNotFoundError:
                    findings.append({"severity": "error", "code": "CODE_FILE_MISSING", "item": name, "path": item["code_path"]})
                    continue
                for pattern in patterns_missing(code, item.get("code_patterns", [])):
                    findings.append({"severity": "error", "code": "CODE_PATTERN_MISSING", "item": name, "pattern": pattern})

    for item in contract.get("constraints", []):
        name = str(item.get("name", "unnamed"))
        for pattern in patterns_missing(text, item.get("manuscript_patterns", [])):
            findings.append({"severity": "error", "code": "CONSTRAINT_MANUSCRIPT_PATTERN_MISSING", "item": name, "pattern": pattern})
        path_literal = item.get("code_path")
        if not path_literal:
            findings.append({"severity": "error", "code": "CONSTRAINT_CODE_PATH_MISSING", "item": name})
            continue
        try:
            code = resolve_text(base, path_literal, cache)
        except FileNotFoundError:
            findings.append({"severity": "error", "code": "CODE_FILE_MISSING", "item": name, "path": path_literal})
            continue
        for pattern in patterns_missing(code, item.get("code_patterns", [])):
            findings.append({"severity": "error", "code": "CONSTRAINT_CODE_PATTERN_MISSING", "item": name, "pattern": pattern})

    for item in contract.get("code_map", []):
        name = str(item.get("name", "unnamed"))
        for pattern in patterns_missing(text, item.get("manuscript_patterns", [])):
            findings.append({"severity": "error", "code": "CODE_MAP_MANUSCRIPT_MISSING", "item": name, "pattern": pattern})
        try:
            code = resolve_text(base, item.get("code_path", ""), cache)
        except (FileNotFoundError, IsADirectoryError):
            findings.append({"severity": "error", "code": "CODE_FILE_MISSING", "item": name, "path": item.get("code_path", "")})
            continue
        for pattern in patterns_missing(code, item.get("code_patterns", [])):
            findings.append({"severity": "error", "code": "CODE_MAP_CODE_MISSING", "item": name, "pattern": pattern})

    for item in contract.get("rechecks", []):
        name = str(item.get("name", "unnamed"))
        try:
            values = recheck_values(item, base)
            actual = recompute(str(item.get("operation", "literal")), values)
            expected = float(item["expected"])
            tolerance = float(item.get("tolerance", 1e-9))
        except (KeyError, TypeError, ValueError, OSError) as exc:
            findings.append({"severity": "error", "code": "RECHECK_INVALID", "item": name, "detail": str(exc)})
            continue
        if not math.isfinite(actual) or abs(actual - expected) > tolerance:
            findings.append({
                "severity": "error",
                "code": "RECHECK_MISMATCH",
                "item": name,
                "expected": expected,
                "actual": actual,
                "tolerance": tolerance,
            })
        literal = item.get("manuscript_literal")
        if literal is not None and str(literal) not in text:
            findings.append({"severity": "error", "code": "RECHECK_LITERAL_MISSING", "item": name, "literal": str(literal)})

    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "file": str(main_tex.resolve()),
        "contract": str(contract_path.resolve()),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.contract)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MATH SEMANTICS {report['status'].upper()} errors={report['errors']} warnings={report['warnings']}")
        print(f"file={report['file']}")
        print(f"contract={report['contract']}")
        for item in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key not in {"severity", "code"})
            print(f"[{item['severity'].upper()}] {item['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
