#!/usr/bin/env python3
"""Regression checks for CUMCM dev/holdout benchmark provenance."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from audit_cumcm_style_benchmark import (
    DEFAULT_ROUTER_ROOT,
    DEFAULT_RUNS_REGISTRY,
    RESERVATION_PATH,
    audit,
    resolve_runs_root,
)


def has_code(report: dict, code: str) -> bool:
    return any(item.get("code") == code for item in report["findings"])


def main() -> int:
    benchmark_root = DEFAULT_ROUTER_ROOT / "references" / "benchmarks"
    dev_suite = benchmark_root / "cumcm-v1-dev.json"
    holdout_suite = benchmark_root / "cumcm-v1-holdout.json"
    # Frozen benchmark runs live in the caller's workspace, not inside this
    # installed Skill.  Validate them when the current workspace exposes the
    # expected run root; otherwise keep this regression self-contained and
    # audit suite provenance/reservation only.
    discovered_root = resolve_runs_root(None, DEFAULT_RUNS_REGISTRY)
    runs_root = discovered_root if discovered_root.is_dir() else None
    report = audit(
        dev_suite, holdout_suite, RESERVATION_PATH, runs_root,
        DEFAULT_RUNS_REGISTRY if runs_root is not None else None,
    )
    allowed_legacy_warnings = {
        "BENCHMARK_ACTIVE_RULES_NOT_CURRENT_BOUND",
        "BENCHMARK_ACTIVE_HISTORICAL_CONTENT_INVALID",
    }
    warning_codes = {
        item.get("code") for item in report.get("findings", [])
        if item.get("severity") == "warning"
    }
    if report["status"] != "pass" or (
        runs_root is not None and not warning_codes.issubset(allowed_legacy_warnings)
    ):
        print(report)
        return 1
    if runs_root is not None:
        registry = json.loads(DEFAULT_RUNS_REGISTRY.read_text(encoding="utf-8"))
        expected_current = {
            split: str(item.get("state"))
            for split, item in registry.get("current_rule_suites", {}).items()
        }
        if report.get("current_rule_states") != expected_current:
            print("FAIL: current-rule dev/holdout suites were not audited", report)
            return 1
        expected_improvement = {
            split: str(item.get("state"))
            for split, item in registry.get("current_improvement_suites", {}).items()
            if split in {"dev", "holdout"}
        }
        if report.get("current_improvement_states") != expected_improvement:
            print("FAIL: real-draft improvement dev/holdout suites were not audited", report)
            return 1
        if report.get("preservation_human_quality_status") != "HUMAN_RATINGS_PENDING":
            print("FAIL: preservation ratings were not kept pending", report)
            return 1
        if report.get("improvement_human_quality_status") != "HUMAN_RATINGS_PENDING":
            print("FAIL: improvement ratings were not kept pending", report)
            return 1
        expected_quality = (
            "HUMAN_RESULTS_AVAILABLE"
            if set(expected_current.values()).issubset({"SCORED_DEV", "SCORED_HOLDOUT_SEALED"})
            else "HUMAN_RATINGS_PENDING"
        )
        if report.get("human_quality_status") != expected_quality:
            print("FAIL: human rating status was conflated with transport audit", report)
            return 1

    with tempfile.TemporaryDirectory(prefix="cumcm-style-benchmark-") as temp_dir:
        root = Path(temp_dir)
        copied_benchmarks = root / "benchmarks"
        shutil.copytree(benchmark_root, copied_benchmarks)
        copied_reservation = root / "reservation.json"
        shutil.copy2(RESERVATION_PATH, copied_reservation)
        temporary_registry = root / "runs.json"
        temporary_registry.write_text(
            '{"schema":"cumcm-style-benchmark-runs/v1","active_runs_root":"'
            + str(root).replace("\\", "\\\\") + '"}\n',
            encoding="utf-8",
        )
        if resolve_runs_root(None, temporary_registry) != root.resolve():
            print("FAIL: benchmark run registry did not resolve the active root")
            return 1
        drifted = copied_benchmarks / "cumcm-v1-dev" / "sources" / "a-convergence-repair.txt"
        drifted.write_text(drifted.read_text(encoding="utf-8") + "\nDRIFT.\n", encoding="utf-8")
        drift_report = audit(
            copied_benchmarks / "cumcm-v1-dev.json",
            copied_benchmarks / "cumcm-v1-holdout.json",
            copied_reservation,
            None,
        )
    if drift_report["status"] != "fail" or not has_code(drift_report, "BENCHMARK_SOURCE_TEXT_DRIFT"):
        print(drift_report)
        return 1
    print("PASS: CUMCM suites match corpus provenance, and source drift is rejected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
