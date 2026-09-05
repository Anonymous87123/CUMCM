#!/usr/bin/env python3
"""Classify and safely exercise native capabilities in the AIGC portfolio.

Public interface:
    python test_native_integrations.py [--execute-safe] [--format text|json]

This test never starts a GUI, calls a remote API, or treats an adapter artifact
as proof that the upstream package ran. Native execution is limited to declared
offline audit commands and the local Tiany comparator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from adapter_core import package_preflight, read_registry
from run_aigc_adapter import execute


TIERS = ("native_executed", "syntax_checked", "prompt_contract", "entrypoint_only", "blocked")


def _typescript_syntax_check(package_root: Path, paths: list[Path]) -> tuple[bool | None, dict]:
    node = shutil.which("node")
    compiler = package_root / "node_modules" / "typescript"
    if not node or not compiler.is_dir():
        return None, {
            "kind": "typescript-transpile",
            "status": "entrypoint-only",
            "error": "local TypeScript compiler is not installed",
        }
    program = r"""
const fs = require('fs');
const path = require('path');
const packageRoot = process.argv[1];
const files = JSON.parse(process.argv[2]);
const ts = require(path.join(packageRoot, 'node_modules', 'typescript'));
const errors = [];
for (const file of files) {
  const source = fs.readFileSync(file, 'utf8');
  const result = ts.transpileModule(source, {
    fileName: file,
    reportDiagnostics: true,
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      jsx: ts.JsxEmit.ReactJSX,
    },
  });
  for (const diagnostic of result.diagnostics || []) {
    if (diagnostic.category !== ts.DiagnosticCategory.Error) continue;
    errors.push({
      file,
      code: diagnostic.code,
      message: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
    });
  }
}
process.stdout.write(JSON.stringify({errors}));
process.exit(errors.length ? 1 : 0);
"""
    completed = subprocess.run(
        [node, "-e", program, str(package_root.resolve()), json.dumps([str(path) for path in paths])],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        timeout=60, check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"errors": [{"message": "TypeScript checker returned invalid JSON"}]}
    return completed.returncode == 0, {
        "kind": "typescript-transpile",
        "status": "pass" if completed.returncode == 0 else "fail",
        "paths": [str(path) for path in paths],
        "diagnostics": payload.get("errors", [])[:20],
        "stderr": completed.stderr[-2000:],
    }


def _syntax_check(package_root: Path, paths: list[Path]) -> tuple[bool | None, list[dict]]:
    checks: list[dict] = []
    typescript_paths = [path for path in paths if path.suffix.casefold() in {".ts", ".tsx"}]
    for path in [item for item in paths if item not in typescript_paths]:
        suffix = path.suffix.casefold()
        if suffix == ".py":
            try:
                compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
                checks.append({"path": str(path), "kind": "python-compile", "status": "pass"})
            except (OSError, SyntaxError, UnicodeError) as exc:
                checks.append({"path": str(path), "kind": "python-compile", "status": "fail", "error": str(exc)})
                return False, checks
        elif suffix == ".js":
            node = shutil.which("node")
            if not node:
                checks.append({"path": str(path), "kind": "node-check", "status": "blocked", "error": "node runtime missing"})
                return False, checks
            completed = subprocess.run(
                [node, "--check", str(path)], text=True, encoding="utf-8", errors="replace",
                capture_output=True, timeout=30, check=False,
            )
            checks.append({
                "path": str(path), "kind": "node-check",
                "status": "pass" if completed.returncode == 0 else "fail",
                "stderr": completed.stderr[-2000:],
            })
            if completed.returncode != 0:
                return False, checks
    if typescript_paths:
        passed, check = _typescript_syntax_check(package_root, typescript_paths)
        checks.append(check)
        if passed is None:
            return None, checks
        if not passed:
            return False, checks
    return True, checks


def _run_tiany(package_root: Path, source: Path, candidate: Path) -> dict:
    script = package_root / "scripts" / "compare_candidates.py"
    completed = subprocess.run(
        ["python", str(script), str(source), str(candidate), "--format", "json"],
        cwd=package_root, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=30, check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None
    return {
        "status": "pass" if completed.returncode == 0 and isinstance(payload, dict) else "blocked",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-2000:],
    }


def audit(registry_path: Path, execute_safe: bool) -> dict:
    registry_path = registry_path.resolve()
    payload = read_registry(registry_path)
    root = registry_path.parents[2]
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="aigc-native-integrations-") as temp:
        temp_root = Path(temp)
        source = temp_root / "source.txt"
        candidate = temp_root / "candidate.txt"
        contrast_source = temp_root / "contrast-source.txt"
        sample = (
            "当参数由 0.35 调整为 0.36 时，首次触发对象由 A 转为 B，"
            "因此这里只能解释为事件类型切换，不能据此断言存在因果关系。\n\n"
            "The baseline explains the observed trend, but it does not identify a causal effect.\n"
        )
        source.write_text(sample, encoding="utf-8")
        candidate.write_text(sample, encoding="utf-8")
        contrast_source.write_text(
            "首先需要全面考虑相关问题。其次需要进一步深入分析。"
            "此外还应从多个维度不断优化。综上所述，该方案具有重要意义。\n" * 8,
            encoding="utf-8",
        )

        for entry in payload.get("packages", []):
            directory = str(entry["directory"])
            package_root = root / directory
            preflight = package_preflight(root, entry)
            record = {
                "directory": directory,
                "kind": entry.get("kind"),
                "tier": None,
                "evidence": [],
            }
            if not preflight["entrypoints_present"]:
                record["tier"] = "blocked"
                record["evidence"].append({"kind": "preflight", "status": "fail", "detail": preflight})
                results.append(record)
                continue

            native_declared = isinstance(entry.get("adapter", {}).get("native_audit_command"), list)
            if execute_safe and native_declared:
                native = execute(
                    registry_path, directory, "audit", source=source,
                    output_dir=temp_root / "native" / directory, execute_native=True,
                ).get("native", {})
                record["evidence"].append({"kind": "declared-offline-native", **native})
                contrast_native = execute(
                    registry_path, directory, "audit", source=contrast_source,
                    output_dir=temp_root / "native-contrast" / directory, execute_native=True,
                ).get("native", {})
                record["evidence"].append({"kind": "declared-offline-native-contrast", **contrast_native})
                source_sensitive = (
                    native.get("status") == "pass"
                    and contrast_native.get("status") == "pass"
                    and native.get("source_unchanged") is True
                    and contrast_native.get("source_unchanged") is True
                    and native.get("output_contract", {}).get("status") == "pass"
                    and contrast_native.get("output_contract", {}).get("status") == "pass"
                    and native.get("semantic_fingerprint_sha256")
                    != contrast_native.get("semantic_fingerprint_sha256")
                )
                if source_sensitive:
                    record["tier"] = "native_executed"
                    results.append(record)
                    continue
                record["evidence"].append({
                    "kind": "source-sensitivity", "status": "fail",
                    "detail": "native output contract failed or semantic fingerprint did not change across distinct inputs",
                })
                record["tier"] = "blocked"
                results.append(record)
                continue

            if execute_safe and directory == "humanize-main(Tiany)":
                native = _run_tiany(package_root, source, candidate)
                record["evidence"].append({"kind": "tiany-comparator", **native})
                record["tier"] = "native_executed" if native["status"] == "pass" else "blocked"
                results.append(record)
                continue

            entrypoints = [
                package_root / str(relative)
                for relative in entry.get("adapter", {}).get("native_entrypoints", [])
            ]
            syntax_paths = [
                path for path in entrypoints
                if path.suffix.casefold() in {".py", ".js", ".ts", ".tsx"}
            ]
            if syntax_paths:
                passed, checks = _syntax_check(package_root, syntax_paths)
                record["evidence"].extend(checks)
                record["tier"] = (
                    "syntax_checked" if passed is True
                    else "entrypoint_only" if passed is None
                    else "blocked"
                )
            elif entry.get("kind") in {"skill", "imported-skill", "router"} and all(
                path.name.casefold() == "skill.md" for path in entrypoints
            ):
                record["tier"] = "prompt_contract"
                record["evidence"].append({"kind": "skill-entrypoint", "status": "pass"})
            else:
                record["tier"] = "entrypoint_only"
                record["evidence"].append({
                    "kind": "entrypoint-presence", "status": "pass",
                    "detail": "runtime was not started because it is a GUI, server, remote client, or build-dependent entrypoint",
                })
            results.append(record)

    counts = {tier: sum(item["tier"] == tier for item in results) for tier in TIERS}
    status = "fail" if counts["blocked"] else "pass" if execute_safe else "review"
    return {
        "schema": "aigc-native-integration-test/v1",
        "status": status,
        "execute_safe": execute_safe,
        "packages": len(results),
        "counts": counts,
        "execution_coverage": "partial" if counts["native_executed"] < len(results) else "complete",
        "all_packages_natively_executed": counts["native_executed"] == len(results),
        "results": results,
        "interpretation": (
            "native_executed proves only the listed offline command ran; syntax_checked, "
            "prompt_contract and entrypoint_only are deliberately weaker evidence. "
            "Without --execute-safe this report is static preflight and must remain REVIEW."
        ),
    }


def main() -> int:
    # Imported projects may surface replacement characters that cannot be
    # encoded by the Windows GBK console. Keep JSON machine-readable instead
    # of letting the reporting layer fail after all probes have completed.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--execute-safe", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.registry, args.execute_safe)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        counts = " ".join(f"{key}={value}" for key, value in report["counts"].items())
        print(
            f"AIGC INTEGRATION TIERS {report['status'].upper()} packages={report['packages']} "
            f"execution_coverage={report['execution_coverage']} {counts}"
        )
        for item in report["results"]:
            print(f"[{item['tier'].upper()}] {item['directory']}")
        if not args.execute_safe:
            print("NOTE: static syntax/entrypoint checks are not native execution evidence; rerun with --execute-safe.")
    return 0 if report["status"] == "pass" else 2 if report["status"] == "review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
