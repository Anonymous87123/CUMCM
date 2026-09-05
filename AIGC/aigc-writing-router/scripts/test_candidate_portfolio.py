#!/usr/bin/env python3
"""Positive and negative tests for same-source candidate governance."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_candidate_portfolio import audit, sha256_file


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def candidate(candidate_id: str, provider: str, source_sha: str, output: Path) -> dict:
    item = {
        "id": candidate_id,
        "provider": provider,
        "input_sha256": source_sha,
        "output_path": output.name,
        "output_sha256": sha256_file(output),
        "pass_count": 1,
        "parent_candidate": None,
        "invariant_status": "pass",
        "domain_audit_status": "pass",
        "document_status": "pass",
    }
    if provider == "baibai-aigc":
        item["round"] = 1
    return item


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-portfolio-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        cand_h = root / "candidate-h.tex"
        cand_b = root / "candidate-b.tex"
        source.write_text(
            r"对象 A 在条件 C 下得到结果 3.2，且满足 $x^2=1$，见式 \eqref{eq:a}\cite{r1}。\label{eq:a}" + "\n",
            encoding="utf-8",
        )
        cand_h.write_text(
            r"在条件 C 下，对象 A 的结果为 3.2；$x^2=1$，见式 \eqref{eq:a}\cite{r1}。\label{eq:a}" + "\n",
            encoding="utf-8",
        )
        cand_b.write_text(
            r"条件 C 下对象 A 的计算结果是 3.2，满足 $x^2=1$，见式 \eqref{eq:a}\cite{r1}。\label{eq:a}" + "\n",
            encoding="utf-8",
        )
        identifier_source = root / "identifier-source.tex"
        identifier_candidate = root / "identifier-candidate.tex"
        identifier_source.write_text(r"题号 Q38 与模型_v2 的结果为 3.2。\n", encoding="utf-8")
        identifier_candidate.write_text(r"题号 Q44 与模型_v3 的结果为 3.2。\n", encoding="utf-8")
        from audit_candidate_portfolio import protected_inventory
        if protected_inventory(identifier_source.read_text(encoding="utf-8"))["numbers"] != protected_inventory(identifier_candidate.read_text(encoding="utf-8"))["numbers"]:
            print("FAIL identifier numbers treated as standalone tokens")
            return 1
        source_sha = sha256_file(source)

        payload = {
            "schema": "aigc-candidate-portfolio/v1",
            "document_type": "mcm",
            "source": {"path": source.name, "sha256": source_sha},
            "candidates": [
                candidate("H1", "humanize-academic-chinese", source_sha, cand_h),
                candidate("B1", "baibai-aigc", source_sha, cand_b),
            ],
            "selection": {
                "accepted": "H1",
                "human_review": "accepted",
                "reason": "保留条件和数值，同时把对象提前到主句。",
            },
        }
        manifest = root / "portfolio.json"
        write_manifest(manifest, payload)
        positive = audit(manifest)
        if positive["status"] != "pass" or positive["decision_status"] != "candidate-accepted":
            print("FAIL positive", json.dumps(positive, ensure_ascii=False, indent=2))
            return 1

        chained = json.loads(json.dumps(payload))
        chained["candidates"][1]["input_sha256"] = sha256_file(cand_h)
        chained["candidates"][1]["parent_candidate"] = "H1"
        write_manifest(manifest, chained)
        negative_chain = audit(manifest)
        codes = {item["code"] for item in negative_chain["findings"]}
        if not {"CANDIDATE_NOT_FROM_SOURCE", "SERIAL_CANDIDATE_CHAIN"}.issubset(codes):
            print("FAIL chain", json.dumps(negative_chain, ensure_ascii=False, indent=2))
            return 1

        failed_gate = json.loads(json.dumps(payload))
        failed_gate["candidates"][0]["domain_audit_status"] = "fail"
        write_manifest(manifest, failed_gate)
        negative_gate = audit(manifest)
        if "ACCEPTED_CANDIDATE_GATE_FAILED" not in {item["code"] for item in negative_gate["findings"]}:
            print("FAIL gate", json.dumps(negative_gate, ensure_ascii=False, indent=2))
            return 1

        cand_h.write_text(
            r"在条件 C 下，对象 A 的结果为 3.3；$x^2=1$，见式 \eqref{eq:a}\cite{r1}。\label{eq:a}" + "\n",
            encoding="utf-8",
        )
        number_drift = json.loads(json.dumps(payload))
        number_drift["candidates"][0]["output_sha256"] = sha256_file(cand_h)
        write_manifest(manifest, number_drift)
        negative_number = audit(manifest)
        if "PROTECTED_INVENTORY_DRIFT" not in {item["code"] for item in negative_number["findings"]}:
            print("FAIL number", json.dumps(negative_number, ensure_ascii=False, indent=2))
            return 1

    print("PASS: same-source branching, single-pass limits, human selection, and failed-gate rejection are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
