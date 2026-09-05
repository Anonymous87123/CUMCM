#!/usr/bin/env python3
"""Audit public, source-bound judgment bridges in a CUMCM candidate.

Public interface:
    python audit_section_judgment_bridges.py candidate.tex \
        --packet-index section-drafting-packets/packet-index.json --format text|json

This is deliberately a local prose audit. It checks that a section does not
introduce a named method before every local problem or mathematical precursor, and
that comparison language has a recorded alternative route. It never asks for
or reconstructs hidden chain-of-thought.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from audit_content_density import normalize_tex, visible_prose
from audit_manuscript import read_tex_tree
from prepare_style_retrieval_plan import section_target_records


SCHEMA = "mcm-section-judgment-bridge-audit/v1"
COMPARISON_CLAIM = re.compile(
    r"(?:经过|通过|对(?:多种|若干|不同)|比较|对比).{0,28}"
    r"(?:模型|方法|算法|方案|策略|规划|回归|预测).{0,28}"
    r"(?:选择|选用|选取|采用|确定|优于|最优)"
    r"|(?:多种|若干|不同).{0,12}(?:模型|方法|算法|方案|策略).{0,20}"
    r"(?:比较|对比|筛选|选择)"
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _compact(text: str) -> str:
    return "".join(str(text).casefold().split())


def _first_position(text: str, terms: object) -> int | None:
    if not isinstance(terms, list):
        return None
    haystack = _compact(text)
    positions = []
    for term in terms:
        if not isinstance(term, str) or not term.strip():
            continue
        needle = _compact(term)
        if needle:
            position = haystack.find(needle)
            if position >= 0:
                positions.append(position)
    return min(positions) if positions else None


def _body(tex_source: str) -> str:
    # Section targets may contain nested headings.  None of those headings is
    # a public reasoning bridge; leaving one in place could satisfy a route
    # term before the first factual paragraph and mask a model jump.
    body = re.sub(
        r"\\(?:section|subsection|subsubsection)\*?\s*(?:\[[^]]*\])?\s*\{[^{}]*\}",
        " ",
        tex_source,
    )
    body = re.sub(r"\\label\{[^{}]*\}", "", body)
    return visible_prose(body).strip()


def _node_positions(text: str, nodes: object) -> list[int]:
    if not isinstance(nodes, list):
        return []
    positions = []
    for node in nodes:
        if isinstance(node, dict):
            position = _first_position(text, node.get("terms"))
            if position is not None:
                positions.append(position)
    return positions


def _finding(findings: list[dict], code: str, target_id: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, "target_id": target_id, **detail})


def _near(left: int, right: int, maximum_gap: int = 180) -> bool:
    return abs(left - right) <= maximum_gap


def _audit_result_question(
    target_id: str, text: str, question: dict, findings: list[dict], enforce: bool,
) -> bool:
    interpretations = question.get("result_interpretations")
    if not isinstance(interpretations, list):
        interpretations = []
    covered = False
    for interpretation in interpretations:
        if not isinstance(interpretation, dict):
            continue
        observation = _first_position(text, interpretation.get("observation_terms"))
        explanation = _first_position(text, interpretation.get("explanation_terms"))
        interpretation_id = interpretation.get("id")
        if enforce and observation is None:
            _finding(
                findings, "SECTION_BRIDGE_RESULT_OBSERVATION_MISSING", target_id,
                question_id=question.get("question_id"), interpretation_id=interpretation_id,
            )
        if enforce and explanation is None:
            _finding(
                findings, "SECTION_BRIDGE_RESULT_EXPLANATION_MISSING", target_id,
                question_id=question.get("question_id"), interpretation_id=interpretation_id,
            )
        if observation is not None and explanation is not None:
            covered = True
            if enforce and not _near(observation, explanation):
                _finding(
                    findings, "SECTION_BRIDGE_RESULT_LINK_MISSING", target_id,
                    question_id=question.get("question_id"),
                    interpretation_id=interpretation_id,
                    observation_position=observation, explanation_position=explanation,
                )
    return covered


def _audit_validation_question(
    target_id: str, text: str, question: dict, findings: list[dict], enforce: bool,
) -> bool:
    checks = question.get("actual_checks")
    if not isinstance(checks, list):
        checks = []
    covered = False
    for check in checks:
        if not isinstance(check, dict) or not check.get("terms") or not check.get("result_terms"):
            continue
        method = _first_position(text, check.get("terms"))
        conclusion = _first_position(text, check.get("result_terms"))
        check_id = check.get("id")
        if enforce and method is None:
            _finding(
                findings, "SECTION_BRIDGE_CHECK_TERM_MISSING", target_id,
                question_id=question.get("question_id"), check_id=check_id,
            )
        if enforce and conclusion is None:
            _finding(
                findings, "SECTION_BRIDGE_CHECK_CONCLUSION_MISSING", target_id,
                question_id=question.get("question_id"), check_id=check_id,
            )
        if method is not None and conclusion is not None:
            covered = True
            if enforce and not _near(method, conclusion):
                _finding(
                    findings, "SECTION_BRIDGE_CHECK_LINK_MISSING", target_id,
                    question_id=question.get("question_id"), check_id=check_id,
                    check_position=method, conclusion_position=conclusion,
                )
    return covered


def _audit_question(
    target_id: str,
    role: str,
    text: str,
    question: dict,
    findings: list[dict],
    enforce: bool = True,
) -> bool:
    requirements = question.get("local_requirements") if isinstance(question.get("local_requirements"), dict) else {}
    if role == "result" and requirements.get("result_interpretation_required") is True:
        return _audit_result_question(target_id, text, question, findings, enforce)
    if role == "validation" and requirements.get("validation_conclusion_required") is True:
        return _audit_validation_question(target_id, text, question, findings, enforce)
    basis = question.get("basis_nodes")
    targets = question.get("mathematical_change_nodes")
    route = question.get("selected_route") if isinstance(question.get("selected_route"), dict) else {}
    basis_positions = _node_positions(text, basis)
    target_positions = _node_positions(text, targets)
    route_position = _first_position(text, route.get("terms"))
    basis_required = enforce and requirements.get("basis_term_required") is True
    target_required = enforce and requirements.get("mathematical_change_term_required") is True
    route_required = enforce and requirements.get("selected_route_term_required") is True
    if basis_required and len(basis_positions) < int(requirements.get("minimum_basis_groups", 1)):
        _finding(findings, "SECTION_BRIDGE_BASIS_MISSING", target_id, question_id=question.get("question_id"))
    if target_required and len(target_positions) < int(requirements.get("minimum_target_groups", 1)):
        _finding(findings, "SECTION_BRIDGE_MATHEMATICAL_CHANGE_MISSING", target_id, question_id=question.get("question_id"))
    if route_required and route_position is None:
        _finding(findings, "SECTION_BRIDGE_SELECTED_ROUTE_MISSING", target_id, question_id=question.get("question_id"), route_id=route.get("id"))
    if basis_positions and target_positions and route_position is not None:
        basis_position = min(basis_positions)
        target_position = min(target_positions)
        # Real papers do not share one basis -> relation -> model sentence order.
        # A named method only needs one question-specific precursor before it;
        # the other node may be explained later where the derivation requires it.
        if min(basis_position, target_position) >= route_position:
            _finding(
                findings,
                "SECTION_BRIDGE_ORDER_INVALID",
                target_id,
                question_id=question.get("question_id"),
                order_rule="route-cannot-precede-both-basis-and-mathematical-change",
                basis_position=basis_position,
                target_position=target_position,
                route_position=route_position,
            )
    comparison_guard = requirements.get("model_comparison_guard", role in {"analysis", "model"})
    comparison = COMPARISON_CLAIM.search(text) if comparison_guard else None
    alternatives = question.get("recorded_alternative_routes")
    if comparison and isinstance(alternatives, list):
        if not alternatives:
            _finding(
                findings,
                "SECTION_BRIDGE_UNRECORDED_COMPARISON_CLAIM",
                target_id,
                question_id=question.get("question_id"),
                excerpt=comparison.group(0),
            )
        else:
            alternative_terms = [
                term
                for item in alternatives
                if isinstance(item, dict)
                for term in item.get("terms", [])
                if isinstance(term, str)
            ]
            if _first_position(text, alternative_terms) is None:
                _finding(
                    findings,
                    "SECTION_BRIDGE_ALTERNATIVE_NOT_NAMED",
                    target_id,
                    question_id=question.get("question_id"),
                )
    return bool((basis_positions and target_positions) if enforce else (basis_positions or target_positions or route_position is not None))


def audit(candidate: Path, packet_index: Path) -> dict:
    findings: list[dict] = []
    candidate = candidate.resolve()
    packet_index = packet_index.resolve()
    if not candidate.is_file():
        findings.append({"severity": "error", "code": "SECTION_BRIDGE_CANDIDATE_MISSING", "path": str(candidate)})
        return _report(candidate, packet_index, findings, 0)
    try:
        index = _load(packet_index)
        raw = normalize_tex(read_tex_tree(candidate))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append({"severity": "error", "code": "SECTION_BRIDGE_INPUT_INVALID", "detail": str(exc)})
        return _report(candidate, packet_index, findings, 0)
    if index.get("schema") != "mcm-section-drafting-packet-index/v1" or index.get("status") != "pass":
        findings.append({"severity": "error", "code": "SECTION_BRIDGE_PACKET_INDEX_INVALID"})
    records = index.get("packets") if isinstance(index.get("packets"), list) else []
    targets = section_target_records(raw)
    if len(records) != len(targets):
        findings.append({
            "severity": "error", "code": "SECTION_BRIDGE_TARGET_COUNT_MISMATCH",
            "packets": len(records), "candidate_targets": len(targets),
        })
    checked = 0
    for record, target in zip(records, targets):
        target_id = str(record.get("target_id", "")) if isinstance(record, dict) else ""
        packet_path = Path(str(record.get("path", ""))).resolve() if isinstance(record, dict) else Path()
        if not packet_path.is_file():
            _finding(findings, "SECTION_BRIDGE_PACKET_MISSING", target_id)
            continue
        declared_packet_sha = record.get("sha256") if isinstance(record, dict) else None
        if not isinstance(declared_packet_sha, str) or hashlib.sha256(packet_path.read_bytes()).hexdigest() != declared_packet_sha:
            _finding(findings, "SECTION_BRIDGE_PACKET_DRIFT", target_id)
            continue
        try:
            packet = _load(packet_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _finding(findings, "SECTION_BRIDGE_PACKET_INVALID", target_id, detail=str(exc))
            continue
        packet_target = packet.get("target") if isinstance(packet.get("target"), dict) else {}
        if (
            packet_target.get("title") != target.get("title")
            or packet_target.get("role") != target.get("role")
            or packet_target.get("question_id") != target.get("question_id")
        ):
            _finding(findings, "SECTION_BRIDGE_TARGET_SIGNATURE_MISMATCH", target_id)
            continue
        contract = packet.get("public_judgment_contract")
        if not isinstance(contract, dict):
            _finding(findings, "SECTION_BRIDGE_CONTRACT_MISSING", target_id)
            continue
        role = str(packet_target.get("role", ""))
        if contract.get("required") is not True:
            continue
        questions = contract.get("questions") if isinstance(contract.get("questions"), list) else []
        section_text = _body(str(target.get("tex_source", "")))
        if role == "analysis" and packet_target.get("question_id") is None:
            covered = sum(_audit_question(target_id, role, section_text, item, findings, enforce=False) for item in questions)
            if covered == 0:
                _finding(findings, "SECTION_BRIDGE_ANALYSIS_HAS_NO_LOCAL_BRIDGE", target_id)
        else:
            for question in questions:
                _audit_question(target_id, role, section_text, question, findings, enforce=True)
        checked += 1
    return _report(candidate, packet_index, findings, checked)


def _report(candidate: Path, packet_index: Path, findings: list[dict], checked: int) -> dict:
    errors = sum(item.get("severity") == "error" for item in findings)
    return {
        "schema": SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "candidate": {"path": str(candidate)},
        "packet_index": {"path": str(packet_index)},
        "sections_checked": checked,
        "errors": errors,
        "findings": findings,
        "interpretation": (
            "Passing confirms that section-local public judgment bridges remain visible and source-bound. "
            "It does not prove hidden reasoning, mathematical correctness, authorship, or naturalness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--packet-index", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.candidate, args.packet_index)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"SECTION JUDGMENT BRIDGES {report['status'].upper()} sections={report['sections_checked']} errors={report['errors']}")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
