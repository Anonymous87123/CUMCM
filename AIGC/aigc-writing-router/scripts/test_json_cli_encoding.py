#!/usr/bin/env python3
"""Regression test for machine-readable JSON under a Windows GBK locale."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    script = Path(__file__).with_name("test_native_integrations.py")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp936"
    completed = subprocess.run(
        [sys.executable, str(script), "--execute-safe", "--format", "json"],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="strict",
        env=env,
        timeout=180,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"native JSON CLI failed with exit {completed.returncode}\n"
            f"stderr:\n{completed.stderr[-2000:]}"
        )
    report = json.loads(completed.stdout)
    if report.get("status") != "pass" or report.get("packages") != 21:
        raise AssertionError(json.dumps(report, ensure_ascii=True, indent=2))
    counts = report.get("counts", {})
    if counts.get("blocked") != 0 or report.get("execution_coverage") != "partial":
        raise AssertionError(json.dumps(report, ensure_ascii=True, indent=2))
    print("PASS: native integration JSON remains UTF-8 and parseable under cp936.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
