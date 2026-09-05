#!/usr/bin/env python3
"""Check that named methods in a CUMCM manuscript have public local grounds.

Public interface:
    python audit_judgment_ledger.py main.tex --ledger judgment-ledger.json \
        --workbench modeling-workbench.json \
        --format text|json

The ledger is a private writing aid. It records only public, fact-backed
bridges from local problem material to a named method; it must not contain or
request hidden chain-of-thought.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import re

from audit_manuscript import first_method_introduction, question_sections, visible_prose
from audit_manuscript import BASED_METHOD_PATTERN, MODEL_INTRO_PATTERN


SCHEMA = "mcm-public-judgment-ledger/v1"
BASIS_KINDS = {
    "relation", "data", "constraint", "interface", "trial", "result", "boundary", "structure",
}
GENERIC_METHOD_WORDING = re.compile(
    r"^(?:采用|选用|选择|建立|构建|引入|改用|使用|基于|借助)(?:了)?"
    r"(?:一个|一种|该|相应|上述|新的|改进的)?"
    r"(?:数学|优化|预测|评价|求解|计算|综合|通用)?"
    r"(?:模型|算法|方法|回归|规划|网络|求解器)$",
    re.I,
)
GENERIC_METHOD_TERMS = {
    "模型", "算法", "方法", "回归", "规划", "网络", "求解器",
    "数学模型", "优化模型", "预测模型", "评价模型", "求解方法", "计算方法",
}


def _finding(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _load_json(path: Path, findings: list[dict]) -> dict | None:
    if not path.is_file():
        _finding(findings, "LEDGER_FILE_MISSING", path=str(path))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, "LEDGER_JSON_INVALID", error=str(exc))
        return None
    if not isinstance(payload, dict):
        _finding(findings, "LEDGER_JSON_NOT_OBJECT")
        return None
    return payload


def _input_record(path: Path) -> dict:
    path = path.resolve()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
    }


def _question_scopes(tex: str) -> tuple[dict[str, str], set[str]]:
    scopes: dict[str, list[str]] = defaultdict(list)
    method_questions: set[str] = set()
    for question_id, title, _start, _content_start, body in question_sections(tex):
        scopes[question_id].append("\n".join((visible_prose(title), visible_prose(body))))
        if first_method_introduction(title, body) is not None:
            method_questions.add(question_id)
    return {question_id: "\n".join(parts) for question_id, parts in scopes.items()}, method_questions


def _searchable(text: str) -> str:
    return "".join(text.casefold().split())


def _first_position(text: str, terms: list[str]) -> int | None:
    searchable = _searchable(text)
    positions = [
        searchable.find(_searchable(term))
        for term in terms
        if _searchable(term) in searchable
    ]
    return min(positions) if positions else None


def _explicit_method_mentions(title: str, body: str) -> list[str]:
    mentions: list[str] = []
    seen: set[str] = set()
    for text, patterns in ((title, (BASED_METHOD_PATTERN,)), (body, (MODEL_INTRO_PATTERN, BASED_METHOD_PATTERN))):
        for pattern in patterns:
            for match in pattern.finditer(text):
                wording = visible_prose(match.group(0)).strip()
                key = _searchable(wording)
                if not key or GENERIC_METHOD_WORDING.fullmatch(key) or key in seen:
                    continue
                seen.add(key)
                mentions.append(wording)
    return mentions


def _question_method_mentions(tex: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for question_id, title, _start, _content_start, body in question_sections(tex):
        for wording in _explicit_method_mentions(title, body):
            key = _searchable(wording)
            if key not in seen[question_id]:
                seen[question_id].add(key)
                grouped[question_id].append(wording)
    return grouped


def _nonempty_strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _validate_basis(raw: object, question_id: str, findings: list[dict]) -> dict | None:
    if not isinstance(raw, dict):
        _finding(findings, "LEDGER_BASIS_INVALID", question_id=question_id)
        return None
    basis_id = raw.get("id")
    terms = _nonempty_strings(raw.get("terms"))
    source_ref = raw.get("source_ref")
    source_ids = _nonempty_strings(raw.get("source_ids")) if "source_ids" in raw else None
    if not isinstance(basis_id, str) or not basis_id.strip() or terms is None:
        _finding(findings, "LEDGER_BASIS_FIELDS_INVALID", question_id=question_id)
        return None
    if raw.get("kind") not in BASIS_KINDS:
        _finding(findings, "LEDGER_BASIS_KIND_INVALID", question_id=question_id, basis_id=basis_id)
        return None
    if not isinstance(source_ref, str) or len(source_ref.strip()) < 3:
        _finding(findings, "LEDGER_BASIS_SOURCE_REF_INVALID", question_id=question_id, basis_id=basis_id)
        return None
    return {
        "id": basis_id.strip(), "terms": terms, "kind": raw["kind"],
        "source_ref": source_ref.strip(), "source_ids": source_ids,
    }


def _workbench_links(path: Path, findings: list[dict]) -> tuple[set[str], dict[str, dict[str, dict]]]:
    payload = _load_json(path, findings)
    if payload is None:
        return set(), {}
    if payload.get("schema") != "mcm-modeling-workbench/v1":
        _finding(
            findings, "LEDGER_WORKBENCH_SCHEMA_MISMATCH",
            expected="mcm-modeling-workbench/v1", actual=payload.get("schema"),
        )
    raw_sources = payload.get("sources")
    source_ids: set[str] = set()
    if not isinstance(raw_sources, list) or not raw_sources:
        _finding(findings, "LEDGER_WORKBENCH_SOURCES_INVALID")
    else:
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict) or not isinstance(raw_source.get("id"), str) or not raw_source["id"].strip():
                _finding(findings, "LEDGER_WORKBENCH_SOURCE_INVALID")
                continue
            source_id = raw_source["id"].strip()
            if source_id in source_ids:
                _finding(findings, "LEDGER_WORKBENCH_SOURCE_DUPLICATE", source_id=source_id)
            source_ids.add(source_id)
    anchors: dict[str, dict[str, dict]] = {}
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        _finding(findings, "LEDGER_WORKBENCH_QUESTIONS_INVALID")
    else:
        for raw_question in raw_questions:
            if not isinstance(raw_question, dict) or not isinstance(raw_question.get("id"), str):
                _finding(findings, "LEDGER_WORKBENCH_QUESTION_INVALID")
                continue
            question_id = raw_question["id"].strip()
            question_anchors: dict[str, dict] = {}
            raw_anchors = raw_question.get("anchors", [])
            if not isinstance(raw_anchors, list):
                _finding(findings, "LEDGER_WORKBENCH_ANCHORS_INVALID", question_id=question_id)
                raw_anchors = []
            for raw_anchor in raw_anchors:
                if not isinstance(raw_anchor, dict) or not isinstance(raw_anchor.get("id"), str):
                    _finding(findings, "LEDGER_WORKBENCH_ANCHOR_INVALID", question_id=question_id)
                    continue
                anchor_id = raw_anchor["id"].strip()
                anchor_source_ids = _nonempty_strings(raw_anchor.get("source_ids"))
                anchor_terms = _nonempty_strings(raw_anchor.get("terms"))
                anchor_kind = raw_anchor.get("kind")
                if (
                    not anchor_id or anchor_source_ids is None or anchor_terms is None
                    or anchor_kind not in BASIS_KINDS
                ):
                    _finding(findings, "LEDGER_WORKBENCH_ANCHOR_FIELDS_INVALID", question_id=question_id)
                    continue
                if anchor_id in question_anchors:
                    _finding(
                        findings, "LEDGER_WORKBENCH_ANCHOR_DUPLICATE",
                        question_id=question_id, anchor_id=anchor_id,
                    )
                    continue
                question_anchors[anchor_id] = {
                    "source_ids": set(anchor_source_ids),
                    "terms": {_searchable(term) for term in anchor_terms},
                    "kind": anchor_kind,
                }
            anchors[question_id] = question_anchors
    return source_ids, anchors


def audit(tex_path: Path, ledger_path: Path, workbench_path: Path | None = None) -> dict:
    findings: list[dict] = []
    tex_path = tex_path.resolve()
    ledger_path = ledger_path.resolve()
    inputs = {
        "main_tex": _input_record(tex_path),
        "ledger": _input_record(ledger_path),
    }
    workbench_sources: set[str] = set()
    workbench_anchors: dict[str, dict[str, dict]] = {}
    if workbench_path is not None:
        workbench_path = workbench_path.resolve()
        inputs["workbench"] = _input_record(workbench_path)
        workbench_sources, workbench_anchors = _workbench_links(workbench_path, findings)
    if not tex_path.is_file():
        _finding(findings, "LEDGER_MANUSCRIPT_MISSING", path=str(tex_path))
        return _report(findings, 0, 0, inputs)
    ledger = _load_json(ledger_path, findings)
    if ledger is None:
        return _report(findings, 0, 0, inputs)
    if ledger.get("schema") != SCHEMA:
        _finding(findings, "LEDGER_SCHEMA_MISMATCH", expected=SCHEMA, actual=ledger.get("schema"))
    tex = tex_path.read_text(encoding="utf-8-sig")
    scopes, method_questions = _question_scopes(tex)
    explicit_mentions = _question_method_mentions(tex)
    if not scopes:
        _finding(findings, "LEDGER_NO_NUMBERED_QUESTIONS")
    raw_questions = ledger.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        _finding(findings, "LEDGER_QUESTIONS_INVALID")
        return _report(findings, len(scopes), 0, inputs)

    declared_ids: set[str] = set()
    validated_questions = 0
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            _finding(findings, "LEDGER_QUESTION_INVALID")
            continue
        question_id = str(raw_question.get("id", "")).strip()
        if not question_id or question_id in declared_ids:
            _finding(findings, "LEDGER_QUESTION_ID_INVALID", question_id=question_id)
            continue
        declared_ids.add(question_id)
        scope = scopes.get(question_id)
        if scope is None:
            _finding(findings, "LEDGER_QUESTION_SCOPE_MISSING", question_id=question_id)
            continue
        if workbench_path is not None and question_id not in workbench_anchors:
            _finding(findings, "LEDGER_QUESTION_NOT_IN_WORKBENCH", question_id=question_id)

        bases: dict[str, dict] = {}
        raw_bases = raw_question.get("basis")
        if not isinstance(raw_bases, list) or not raw_bases:
            _finding(findings, "LEDGER_BASIS_MISSING", question_id=question_id)
        else:
            for raw_basis in raw_bases:
                basis = _validate_basis(raw_basis, question_id, findings)
                if basis is None:
                    continue
                if basis["id"] in bases:
                    _finding(findings, "LEDGER_BASIS_ID_DUPLICATE", question_id=question_id, basis_id=basis["id"])
                    continue
                bases[basis["id"]] = basis
                if _first_position(scope, basis["terms"]) is None:
                    _finding(findings, "LEDGER_BASIS_NOT_IN_SCOPE", question_id=question_id, basis_id=basis["id"])
                if workbench_path is not None:
                    declared_source_ids = basis.get("source_ids")
                    if declared_source_ids is None:
                        _finding(
                            findings, "LEDGER_BASIS_SOURCE_IDS_MISSING",
                            question_id=question_id, basis_id=basis["id"],
                        )
                    else:
                        unknown = sorted(set(declared_source_ids) - workbench_sources)
                        if unknown:
                            _finding(
                                findings, "LEDGER_BASIS_SOURCE_IDS_UNKNOWN",
                                question_id=question_id, basis_id=basis["id"], source_ids=unknown,
                            )
                        anchor = workbench_anchors.get(question_id, {}).get(basis["id"])
                        if anchor is None:
                            _finding(
                                findings, "LEDGER_BASIS_ANCHOR_UNKNOWN",
                                question_id=question_id, basis_id=basis["id"],
                            )
                        else:
                            if not set(declared_source_ids) <= anchor["source_ids"]:
                                _finding(
                                    findings, "LEDGER_BASIS_SOURCE_BINDING_MISMATCH",
                                    question_id=question_id, basis_id=basis["id"],
                                )
                            if basis["kind"] != anchor["kind"]:
                                _finding(
                                    findings, "LEDGER_BASIS_KIND_BINDING_MISMATCH",
                                    question_id=question_id, basis_id=basis["id"],
                                )
                            if not {_searchable(term) for term in basis["terms"]} & anchor["terms"]:
                                _finding(
                                    findings, "LEDGER_BASIS_TERMS_BINDING_MISMATCH",
                                    question_id=question_id, basis_id=basis["id"],
                                )

        raw_methods = raw_question.get("methods")
        if not isinstance(raw_methods, list):
            _finding(findings, "LEDGER_METHODS_INVALID", question_id=question_id)
            raw_methods = []
        if not raw_methods and raw_question.get("direct_relation") is not True:
            _finding(findings, "LEDGER_METHOD_OR_DIRECT_RELATION_MISSING", question_id=question_id)
        if raw_question.get("direct_relation") is True and not bases:
            _finding(findings, "LEDGER_DIRECT_RELATION_WITHOUT_BASIS", question_id=question_id)

        declared_specific_terms: list[str] = []
        for raw_method in raw_methods:
            if not isinstance(raw_method, dict):
                _finding(findings, "LEDGER_METHOD_INVALID", question_id=question_id)
                continue
            name = raw_method.get("name")
            terms = _nonempty_strings(raw_method.get("terms"))
            basis_ids = _nonempty_strings(raw_method.get("basis_ids"))
            if not isinstance(name, str) or not name.strip() or terms is None or basis_ids is None:
                _finding(findings, "LEDGER_METHOD_FIELDS_INVALID", question_id=question_id)
                continue
            declared_specific_terms.extend(
                term for term in terms
                if _searchable(term) not in GENERIC_METHOD_TERMS and len(_searchable(term)) >= 2
            )
            method_position = _first_position(scope, terms)
            if method_position is None:
                _finding(findings, "LEDGER_METHOD_NOT_IN_SCOPE", question_id=question_id, method=name)
                continue
            linked = [bases.get(basis_id) for basis_id in basis_ids]
            if any(basis is None for basis in linked):
                _finding(findings, "LEDGER_METHOD_BASIS_UNKNOWN", question_id=question_id, method=name)
                continue
            basis_positions = [
                _first_position(scope, basis["terms"])
                for basis in linked
                if basis is not None
            ]
            if not any(position is not None and position < method_position for position in basis_positions):
                _finding(
                    findings,
                    "LEDGER_METHOD_WITHOUT_PRECEDING_BASIS",
                    question_id=question_id,
                    method=name,
                )
        for wording in explicit_mentions.get(question_id, []):
            searchable_wording = _searchable(wording)
            if not any(_searchable(term) in searchable_wording for term in declared_specific_terms):
                _finding(
                    findings, "LEDGER_EXPLICIT_METHOD_UNDECLARED",
                    question_id=question_id, wording=wording,
                )
        validated_questions += 1

    for question_id in sorted(method_questions - declared_ids):
        _finding(findings, "LEDGER_METHOD_QUESTION_UNDECLARED", question_id=question_id)
    for question_id in sorted(declared_ids - set(scopes)):
        _finding(findings, "LEDGER_DECLARED_QUESTION_NOT_IN_MANUSCRIPT", question_id=question_id)
    return _report(findings, len(scopes), validated_questions, inputs,
                   workbench_linked=workbench_path is not None)


def _report(findings: list[dict], manuscript_questions: int, ledger_questions: int, inputs: dict,
            workbench_linked: bool = False) -> dict:
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "mcm-public-judgment-ledger-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "coverage": "full" if workbench_linked else "partial",
        "skipped_checks": ([] if workbench_linked else [{
            "check": "workbench-anchor-link",
            "reason": "缺少 --workbench；未核对账本分问与工作台锚点的对应",
            "consequence": "本次运行没有检查公开依据是否绑回冻结源，PASS 不代表依据可追溯",
        }]),
        "errors": errors,
        "warnings": 0,
        "inputs": inputs,
        "manuscript_questions": manuscript_questions,
        "ledger_questions": ledger_questions,
        "findings": findings,
        "interpretation": (
            "Passing confirms that declared public bases appear before each declared method in its question scope. "
            "It does not establish model correctness, prose quality, hidden reasoning, or unlisted-method coverage."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--workbench", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.ledger, args.workbench)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"JUDGMENT LEDGER {report['status'].upper()} coverage={report['coverage']} questions="
            f"{report['ledger_questions']}/{report['manuscript_questions']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
        for item in report["skipped_checks"]:
            print(f"[SKIPPED] {item['check']}: {item['reason']}；{item['consequence']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
