#!/usr/bin/env python3
"""Focused regression tests for the development matrix chain helper."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_benchmark_owner_ledger import audit
import run_matrix_dev_chain as chain
from run_matrix_dev_chain import (
    KEEP_REASON_BY_PHRASE,
    REPORT_SCHEMA,
    _keep_arguments,
    _stage_external_candidates,
    owner_ledger,
)
from adapter_core import write_json


def main() -> int:
    if REPORT_SCHEMA != "aigc-matrix-dev-chain/v2":
        print("FAIL: matrix chain schema was not bumped for auxiliary evidence")
        return 1
    arguments = _keep_arguments({
        "diagnostics": {
            "actionable_findings": [{
                "matched": "能稳定",
                "signal_id": "LEX-STRICT-CORPUS-CERTAINTY-01",
                "line": 2,
                "column": 17,
            }],
        },
    })
    if arguments[:1] != ["--keep-reason"] or "@2:17=" not in arguments[1]:
        print("FAIL: position-bound KEEP argument was not built")
        return 1
    sys_path_added = False
    humanize_scripts = (
        Path(__file__).resolve().parents[2]
        / "humanize-academic-chinese"
        / "scripts"
    )
    import sys
    if str(humanize_scripts) not in sys.path:
        sys.path.insert(0, str(humanize_scripts))
        sys_path_added = True
    import validate_humanize_output as validator
    for phrase, reason in KEEP_REASON_BY_PHRASE.items():
        try:
            validator._validate_reason(reason, f"fixture {phrase}")
        except ValueError as exc:
            print(f"FAIL: KEEP reason violates Humanize input contract: {phrase}: {exc}")
            return 1
    if sys_path_added:
        sys.path.remove(str(humanize_scripts))
    try:
        _keep_arguments({
            "diagnostics": {
                "actionable_findings": [{
                    "matched": "unknown fixture phrase",
                    "signal_id": "X",
                    "line": 1,
                    "column": 1,
                }],
            },
        })
    except ValueError:
        pass
    else:
        print("FAIL: unknown strict phrase escaped the approved fixture map")
        return 1

    with tempfile.TemporaryDirectory(prefix="aigc-matrix-chain-test-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source.write_text("在现有证据下，结果保持稳定。\n", encoding="utf-8")
        candidate.write_text("现有证据表明，结果保持稳定。\n", encoding="utf-8")
        for document_type in ("modeling", "course-notes", "research"):
            ledger_path = root / f"{document_type}.json"
            write_json(ledger_path, owner_ledger(document_type, source, candidate))
            report = audit(ledger_path, source, candidate, document_type)
            if report.get("status") != "pass":
                print(f"FAIL: {document_type} owner ledger did not pass", report)
                return 1
        workbench_plan = root / "workbench-plan.json"
        workbench_plan.write_text('{"status":"pass","selected_count":10}\n', encoding="utf-8")
        calls = []
        original_adapter = chain.run_adapter

        def fake_adapter(registry, package, action, **kwargs):
            calls.append((package, action))
            if package == "humanize-main" and action == "audit":
                report_dir = Path(kwargs["output_dir"])
                report_dir.mkdir(parents=True, exist_ok=True)
                (report_dir / "audit-report.json").write_text(
                    '{"schema":"aigc-adapter-run/v1","status":"pass",'
                    '"claims":{"authorship_or_detector_verdict":false}}\n',
                    encoding="utf-8",
                )
            return {"status": "pass", "native_executed": False}

        chain.run_adapter = fake_adapter
        try:
            auxiliary = chain.run_auxiliary_reviews(
                root / "registry.json",
                "modeling",
                candidate,
                root / "auxiliary",
                workbench_plan,
            )
        finally:
            chain.run_adapter = original_adapter
        if calls != [("humanize-main", "audit")]:
            print("FAIL: auxiliary audit did not execute exactly once", calls)
            return 1
        if auxiliary["ai_check"]["execution_level"] != "ADAPTER_DIAGNOSTIC_ONLY":
            print("FAIL: ai-check execution level was not bounded")
            return 1
        if auxiliary["AI_paper_workbench"]["execution_level"] != "WORKBENCH_PLAN_ONLY":
            print("FAIL: AI_paper workbench execution level was not bounded")
            return 1
        if auxiliary["ai_check"]["claims"]["candidate_selection"]:
            print("FAIL: forensic reviewer was allowed to select candidates")
            return 1
        candidate_dir = root / "external"
        candidate_dir.mkdir()
        suite = {"cases": [{"id": f"case-{index}"} for index in range(1, 4)]}
        for index in range(1, 4):
            for trial in range(1, 4):
                (candidate_dir / f"case-{index}-t{trial}.tex").write_text(
                    f"case {index} trial {trial}\n", encoding="utf-8",
                )
        staged = _stage_external_candidates(suite, candidate_dir, root / "staged")
        if len(staged) != 9 or any(not path.is_file() for path in staged):
            print("FAIL: external holdout candidate matrix was not staged exactly")
            return 1
        (candidate_dir / "case-3-t3.tex").unlink()
        try:
            _stage_external_candidates(suite, candidate_dir, root / "bad-stage")
        except ValueError:
            pass
        else:
            print("FAIL: incomplete external candidate matrix was accepted")
            return 1
    print("matrix development chain tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
