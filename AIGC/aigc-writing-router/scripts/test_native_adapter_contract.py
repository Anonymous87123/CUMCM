#!/usr/bin/env python3
"""Negative and positive tests for declared offline native audit evidence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from adapter_core import compare_inventory, protected_inventory
from run_aigc_adapter import _run_native, execute


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def entry(command: list[str], timeout: int = 10) -> dict:
    return {
        "directory": "pkg",
        "kind": "application",
        "aliases": ["pkg"],
        "adapter": {
            "interfaces": ["audit"],
            "offline_action": "audit",
            "document_formats": ["txt"],
            "native_entrypoints": [],
            "native_audit_command": command,
            "native_audit_contract": {
                "stdout_format": "json",
                "required_keys": ["score", "issues"],
                "fingerprint_keys": ["score", "issues", "optional"],
                "timeout_seconds": timeout,
            },
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-native-contract-") as temp:
        root = Path(temp)
        (root / "pkg").mkdir()
        source = root / "source.txt"
        source.write_text("content-bound source\n", encoding="utf-8")
        valid = entry([
            sys.executable, "-c",
            "import json,sys; s=open(sys.argv[1],encoding='utf-8').read(); print(json.dumps({'score':len(s),'issues':[s[:1]]}))",
            "{source}",
        ])
        report = _run_native(root, valid, source)
        require(
            report["status"] == "pass" and report["source_unchanged"] is True
            and report.get("semantic_fingerprint_sha256"),
            "valid source-bound native audit failed", report,
        )

        missing_source = entry([sys.executable, "-c", "print('{}')"])
        report = _run_native(root, missing_source, source)
        require(report.get("code") == "NATIVE_SOURCE_PLACEHOLDER_MISSING", "source-free command passed", report)

        nonzero = entry([sys.executable, "-c", "import sys; sys.exit(7)", "{source}"])
        report = _run_native(root, nonzero, source)
        require(report.get("code") == "NATIVE_NONZERO_EXIT", "nonzero command passed", report)

        invalid_json = entry([sys.executable, "-c", "print('not-json')", "{source}"])
        report = _run_native(root, invalid_json, source)
        require(report.get("code") == "NATIVE_OUTPUT_INVALID_JSON", "invalid JSON passed", report)

        missing_keys = entry([sys.executable, "-c", "print('{}')", "{source}"])
        report = _run_native(root, missing_keys, source)
        require(report.get("code") == "NATIVE_OUTPUT_KEYS_MISSING", "missing output keys passed", report)

        mutating_source = root / "mutating.txt"
        mutating_source.write_text("authority\n", encoding="utf-8")
        mutating = entry([
            sys.executable, "-c",
            "import json,sys; open(sys.argv[1],'w',encoding='utf-8').write('changed'); print(json.dumps({'score':1,'issues':[]}))",
            "{source}",
        ])
        report = _run_native(root, mutating, mutating_source)
        require(report.get("code") == "NATIVE_SOURCE_MODIFIED", "source mutation passed", report)

        timeout = entry([
            sys.executable, "-c", "import time; time.sleep(2)", "{source}",
        ], timeout=1)
        report = _run_native(root, timeout, source)
        require(report.get("code") == "NATIVE_EXECUTION_FAILED", "timeout passed", report)

        registry_dir = root / "router" / "references"
        registry_dir.mkdir(parents=True)
        registry = registry_dir / "registry.json"
        registry.write_text(json.dumps({
            "schema": "aigc-capability-portfolio/v5",
            "packages": [nonzero],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        executed = execute(
            registry, "pkg", "audit", source=source,
            output_dir=root / "adapter-output", execute_native=True,
        )
        require(
            executed["status"] == "partial"
            and executed["native_executed"] is False
            and executed["native"]["status"] == "blocked",
            "failed native command was reported as executed", executed,
        )

        tex_source = "% prose example has one unmatched $ delimiter\n模型采用 $x+y$，随后解释边界条件。\n"
        tex_candidate = "% prose example has one unmatched $ delimiter\n模型采用 $x+y$，随后说明边界条件。\n"
        require(
            not compare_inventory(
                protected_inventory(tex_source), protected_inventory(tex_candidate)
            ),
            "an unmatched comment dollar swallowed later TeX prose",
            {"source": tex_source, "candidate": tex_candidate},
        )
        tex_drift = tex_candidate.replace("$x+y$", "$x-y$")
        formula_findings = compare_inventory(
            protected_inventory(tex_source), protected_inventory(tex_drift)
        )
        require(
            any(item.get("category") == "inline_math" for item in formula_findings),
            "a real inline-math change was not detected",
            formula_findings,
        )

    print("PASS: native evidence requires a source, immutable input, successful exit, valid JSON contract and content fingerprint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
