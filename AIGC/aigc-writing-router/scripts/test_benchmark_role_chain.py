#!/usr/bin/env python3
"""Regression checks for source-bound benchmark owner and stack evidence."""

from __future__ import annotations

import tempfile
from pathlib import Path

from adapter_core import sha256_file, write_json
from audit_benchmark_owner_ledger import OWNER_BY_DOCUMENT_TYPE, audit
from prepare_benchmark_stack import build as build_stack
from run_aigc_adapter import execute


DECISION_BY_TYPE = {
    "modeling": {
        "source_anchor": "第1段",
        "problem_object": "资源量",
        "mathematical_change": "把总量变化写成状态变量差值",
        "modeling_decision": "保留原有动力关系，只调整解释顺序",
        "preserved_results": ["1.8倍"],
        "action": "REWRITE",
    },
    "course-notes": {
        "source_anchor": "第1段",
        "source_identity": "NOTE",
        "teaching_function": "解释判断答案所需的转折",
        "decisive_step": "先比较题干对象，再核对选项",
        "preserved_conditions": ["仅在当前题干成立"],
        "action": "REWRITE",
    },
    "research": {
        "source_anchor": "第1段",
        "claim": "候选只重排现有研究主张",
        "evidence_boundary": "不新增实验或文献",
        "claim_strength": "保持原有限定",
        "preserved_objects": ["算法类", "函数类"],
        "action": "REWRITE",
    },
}


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    with tempfile.TemporaryDirectory(prefix="benchmark-role-chain-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        source.write_text("原稿保留 1.8倍 的结果与限定。", encoding="utf-8")
        candidate.write_text("结果仍为 1.8倍，限定条件保持不变。", encoding="utf-8")
        verification_dir = root / "verification"
        verification = execute(
            registry, "humanize-academic-chinese", "verify-candidate",
            source=source, candidate=candidate, output_dir=verification_dir,
        )
        if verification.get("status") != "pass":
            print("FAIL: fixture candidate verification failed", verification)
            return 1
        for document_type, provider in OWNER_BY_DOCUMENT_TYPE.items():
            ledger_path = root / f"ledger-{document_type}.json"
            write_json(ledger_path, {
                "schema": "aigc-benchmark-owner-ledger/v1",
                "document_type": document_type,
                "provider": provider,
                "mode": "REWRITE",
                "source_sha256": sha256_file(source),
                "candidate_sha256": sha256_file(candidate),
                "decisions": [DECISION_BY_TYPE[document_type]],
                "unresolved": [],
                "claims": {
                    "hidden_reasoning_recorded": False,
                    "academic_correctness_proven": False,
                },
            })
            owner_report = audit(ledger_path, source, candidate, document_type)
            if owner_report.get("status") != "pass":
                print("FAIL: valid owner ledger was rejected", owner_report)
                return 1
            owner_report_path = root / f"owner-report-{document_type}.json"
            write_json(owner_report_path, owner_report)
            stack = build_stack(
                document_type, source, candidate,
                verification_dir / "candidate-verification.json",
                owner_report_path, root / f"stack-{document_type}", registry,
            )
            if (
                stack.get("status") != "pass"
                or set(stack.get("required_stage_providers", []))
                != {"deai-academic-writing", provider}
            ):
                print("FAIL: integrated role chain was incomplete", stack)
                return 1

        broken = root / "ledger-broken.json"
        payload = {
            "schema": "aigc-benchmark-owner-ledger/v1",
            "document_type": "research",
            "provider": "deai-research-writing",
            "mode": "REWRITE",
            "source_sha256": sha256_file(source),
            "candidate_sha256": sha256_file(candidate),
            "decisions": [{
                key: value for key, value in DECISION_BY_TYPE["research"].items()
                if key != "evidence_boundary"
            }],
            "unresolved": [],
            "claims": {
                "hidden_reasoning_recorded": False,
                "academic_correctness_proven": False,
            },
        }
        write_json(broken, payload)
        broken_report = audit(broken, source, candidate, "research")
        if broken_report.get("status") != "fail" or not any(
            item.get("code") == "OWNER_LEDGER_DECISION_FIELDS_MISSING"
            for item in broken_report.get("findings", [])
        ):
            print("FAIL: incomplete owner evidence was accepted", broken_report)
            return 1
    print("PASS: modeling, course, and research owner ledgers bind complete stack evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
