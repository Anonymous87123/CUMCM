#!/usr/bin/env python3
"""Forward checks for the fact-backed public-judgment ledger."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_judgment_ledger import audit
from test_style_forward import BAD_CASES, GOOD_CASES


def ledger(problem_type: str) -> dict:
    fixtures = {
        "A": {
            "basis": [{
                "id": "fixed-distance",
                "kind": "relation",
                "terms": ["相邻距离固定"],
                "source_ref": "fixture A: fixed-distance condition",
            }],
            "methods": [{
                "name": "bisection",
                "terms": ["二分法"],
                "basis_ids": ["fixed-distance"],
            }],
        },
        "B": {
            "basis": [{
                "id": "state-update",
                "kind": "structure",
                "terms": ["状态满足逐期递推"],
                "source_ref": "fixture B: state update",
            }],
            "methods": [{
                "name": "dynamic-programming",
                "terms": ["动态规划"],
                "basis_ids": ["state-update"],
            }],
        },
        "C": {
            "basis": [{
                "id": "label-definition",
                "kind": "data",
                "terms": ["标签只有违约"],
                "source_ref": "fixture C: target label",
            }],
            "methods": [{
                "name": "logistic-regression",
                "terms": ["Logistic 回归"],
                "basis_ids": ["label-definition"],
            }],
        },
    }
    return {"schema": "mcm-public-judgment-ledger/v1", "questions": [{"id": "1", **fixtures[problem_type]}]}


def has_code(report: dict, code: str) -> bool:
    return any(item.get("code") == code for item in report["findings"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-judgment-ledger-") as temp_dir:
        root = Path(temp_dir)
        for problem_type, tex in GOOD_CASES.items():
            tex_path = root / f"good-{problem_type}.tex"
            ledger_path = root / f"good-{problem_type}.json"
            tex_path.write_text(tex, encoding="utf-8")
            ledger_path.write_text(json.dumps(ledger(problem_type), ensure_ascii=False), encoding="utf-8")
            report = audit(tex_path, ledger_path)
            if report["status"] != "pass":
                print(report)
                return 1

        bound_tex = root / "bound.tex"
        bound_ledger = root / "bound.json"
        workbench = root / "modeling-workbench.json"
        bound_tex.write_text(GOOD_CASES["A"], encoding="utf-8")
        bound_payload = ledger("A")
        bound_payload["questions"][0]["basis"][0]["source_ids"] = ["problem"]
        bound_ledger.write_text(json.dumps(bound_payload, ensure_ascii=False), encoding="utf-8")
        workbench.write_text(json.dumps({
            "schema": "mcm-modeling-workbench/v1",
            "sources": [{"id": "problem"}],
            "questions": [{
                "id": "1",
                "anchors": [{
                    "id": "fixed-distance", "kind": "relation",
                    "terms": ["相邻距离固定"], "source_ids": ["problem"],
                }],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        bound_report = audit(bound_tex, bound_ledger, workbench)
        if bound_report["status"] != "pass":
            print(bound_report)
            return 1
        bound_payload["questions"][0]["basis"][0]["source_ids"] = ["invented-source"]
        bound_ledger.write_text(json.dumps(bound_payload, ensure_ascii=False), encoding="utf-8")
        rejected_binding = audit(bound_tex, bound_ledger, workbench)
        bound_payload["questions"][0]["basis"][0]["source_ids"] = ["problem"]
        bound_payload["questions"][0]["basis"][0]["terms"] = ["极角条件"]
        bound_ledger.write_text(json.dumps(bound_payload, ensure_ascii=False), encoding="utf-8")
        rejected_terms = audit(bound_tex, bound_ledger, workbench)

        undeclared_tex = root / "undeclared-method.tex"
        undeclared_ledger = root / "undeclared-method.json"
        undeclared_tex.write_text(
            "\\section{问题一模型建立}相邻距离固定，因此采用二分法求根。随后采用粒子群优化算法搜索参数。",
            encoding="utf-8",
        )
        undeclared_ledger.write_text(json.dumps({
            "schema": "mcm-public-judgment-ledger/v1",
            "questions": [{
                "id": "1",
                "basis": [{
                    "id": "fixed-distance", "kind": "relation",
                    "terms": ["相邻距离固定"], "source_ref": "fixture: relation",
                }],
                "methods": [{
                    "name": "bisection", "terms": ["二分法"],
                    "basis_ids": ["fixed-distance"],
                }],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        undeclared_report = audit(undeclared_tex, undeclared_ledger)

        bad_tex = root / "bad.tex"
        bad_ledger = root / "bad.json"
        bad_tex.write_text(BAD_CASES["airdrop"], encoding="utf-8")
        bad_ledger.write_text(json.dumps({
            "schema": "mcm-public-judgment-ledger/v1",
            "questions": [{
                "id": "1",
                "basis": [{
                    "id": "missing-fact",
                    "kind": "constraint",
                    "terms": ["负载上限"],
                    "source_ref": "fixture: absent constraint",
                }],
                "methods": [{
                    "name": "particle-swarm",
                    "terms": ["粒子群优化"],
                    "basis_ids": ["missing-fact"],
                }],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        report = audit(bad_tex, bad_ledger)
        direct_tex = root / "direct.tex"
        direct_ledger = root / "direct.json"
        direct_tex.write_text(
            r"\section{问题一模型建立}相邻构件的距离固定，因此令相邻端点满足定长关系，并在给定边界内逐项递推位置。",
            encoding="utf-8",
        )
        direct_ledger.write_text(json.dumps({
            "schema": "mcm-public-judgment-ledger/v1",
            "questions": [{
                "id": "1",
                "direct_relation": True,
                "basis": [{
                    "id": "fixed-distance",
                    "kind": "relation",
                    "terms": ["距离固定"],
                    "source_ref": "fixture: fixed-distance relation",
                }],
                "methods": [],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        direct_report = audit(direct_tex, direct_ledger)
    if report["status"] != "fail" or not has_code(report, "LEDGER_BASIS_NOT_IN_SCOPE"):
        print(report)
        return 1
    if direct_report["status"] != "pass":
        print(direct_report)
        return 1
    if rejected_binding["status"] != "fail" or not has_code(rejected_binding, "LEDGER_BASIS_SOURCE_IDS_UNKNOWN"):
        print(rejected_binding)
        return 1
    if rejected_terms["status"] != "fail" or not has_code(rejected_terms, "LEDGER_BASIS_TERMS_BINDING_MISMATCH"):
        print(rejected_terms)
        return 1
    if undeclared_report["status"] != "fail" or not has_code(undeclared_report, "LEDGER_EXPLICIT_METHOD_UNDECLARED"):
        print(undeclared_report)
        return 1
    print("PASS: public bases precede declared methods; missing factual bases are rejected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
