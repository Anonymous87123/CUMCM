#!/usr/bin/env python3
"""Check manuscript literals against a frozen result-source manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(main_tex: Path, manifest_path: Path) -> dict:
    text = main_tex.read_text(encoding="utf-8-sig")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    base = manifest_path.parent
    findings: list[dict] = []

    for item in manifest.get("sources", []):
        source = Path(item["path"])
        if not source.is_absolute():
            source = (base / source).resolve()
        if not source.is_file():
            findings.append({"severity": "error", "code": "SOURCE_MISSING", "item": item["path"]})
            continue
        expected = str(item.get("sha256", "")).lower()
        actual = sha256(source)
        if expected and actual != expected:
            findings.append({
                "severity": "error",
                "code": "SOURCE_HASH_MISMATCH",
                "item": item["path"],
                "expected": expected,
                "actual": actual,
            })

    for claim in manifest.get("claims", []):
        claim_id = str(claim.get("id", "unnamed"))
        minimum = int(claim.get("min_occurrences", 1))
        if "pattern" in claim:
            count = len(re.findall(str(claim["pattern"]), text, re.I | re.S))
        else:
            count = text.count(str(claim.get("literal", "")))
        if count < minimum:
            findings.append({
                "severity": "error",
                "code": "CLAIM_MISSING",
                "item": claim_id,
                "expected_occurrences": minimum,
                "actual_occurrences": count,
            })
        for forbidden in claim.get("forbidden", []):
            forbidden_count = text.count(str(forbidden))
            if forbidden_count:
                findings.append({
                    "severity": "error",
                    "code": "STALE_LITERAL",
                    "item": claim_id,
                    "literal": str(forbidden),
                    "actual_occurrences": forbidden_count,
                })

    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "status": "pass" if errors == 0 else "fail",
        "file": str(main_tex.resolve()),
        "manifest": str(manifest_path.resolve()),
        "errors": errors,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    report = audit(args.main_tex, args.manifest)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"RESULT SYNC {report['status'].upper()} errors={report['errors']}")
        print(f"file={report['file']}")
        print(f"manifest={report['manifest']}")
        for item in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key not in {"severity", "code"})
            print(f"[{item['severity'].upper()}] {item['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
