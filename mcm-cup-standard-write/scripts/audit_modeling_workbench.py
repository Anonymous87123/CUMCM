#!/usr/bin/env python3
"""Check the concise, fact-backed modeling workbench for a CUMCM manuscript.

Public interface:
    python audit_modeling_workbench.py main.tex --workbench modeling-workbench.json \
        --phase preflight|release --format text|json

The workbench records revisable modeling artifacts, not hidden chain-of-thought.
Passing validates local structure and manuscript correspondence; it does not
establish mathematical correctness or prove private reasoning occurred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from audit_manuscript import first_method_introduction, question_sections, visible_prose


SCHEMA = "mcm-modeling-workbench/v1"
ANCHOR_KINDS = {
    "relation", "data", "constraint", "interface", "trial", "result", "boundary", "structure",
}
ROUTE_STATUSES = {"selected", "rejected", "deferred"}
SOURCE_ROLES = {"problem", "data", "code", "result", "figure", "log", "prior-output"}
CHECK_KINDS = {
    "derivation", "boundary", "feasibility", "counterexample", "unit", "sensitivity",
    "replay", "residual", "implementation",
}
INTERPRETATION_KINDS = {
    "active_constraint", "event_switch", "trend", "exception", "comparison",
    "mechanism", "uncertainty", "boundary",
}
INTERPRETATION_SOURCE_ROLES = {"code", "result", "figure", "log", "prior-output"}
DRAFTING_MODES = {
    "direct_derivation", "relation_then_method", "interface_extension",
    "result_then_refine", "method_after_structure",
}


def _finding(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _nonempty_strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def _searchable(text: str) -> str:
    return "".join(text.casefold().split())


def _first_position(text: str, terms: list[str]) -> int | None:
    scope = _searchable(text)
    positions = [scope.find(_searchable(term)) for term in terms if _searchable(term) in scope]
    return min(positions) if positions else None


def _load(path: Path, findings: list[dict]) -> dict | None:
    if not path.is_file():
        _finding(findings, "WORKBENCH_FILE_MISSING", path=str(path))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, "WORKBENCH_JSON_INVALID", error=str(exc))
        return None
    if not isinstance(payload, dict):
        _finding(findings, "WORKBENCH_JSON_NOT_OBJECT")
        return None
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_record(path: Path) -> dict:
    path = path.resolve()
    return {
        "path": str(path),
        "sha256": _sha256(path) if path.is_file() else None,
    }


def _parse_sources(payload: dict, root: Path, findings: list[dict]) -> dict[str, dict]:
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        _finding(findings, "WORKBENCH_SOURCES_MISSING")
        return {}
    sources: dict[str, dict] = {}
    for raw in raw_sources:
        if not isinstance(raw, dict):
            _finding(findings, "WORKBENCH_SOURCE_INVALID")
            continue
        source_id = raw.get("id")
        relative_path = raw.get("path")
        declared_hash = raw.get("sha256")
        if (
            not isinstance(source_id, str) or not source_id.strip() or source_id in sources
            or raw.get("role") not in SOURCE_ROLES
            or not isinstance(relative_path, str) or not relative_path.strip()
            or not isinstance(declared_hash, str) or len(declared_hash) != 64
        ):
            _finding(findings, "WORKBENCH_SOURCE_FIELDS_INVALID")
            continue
        source_path = (root / relative_path).resolve()
        try:
            source_path.relative_to(root.resolve())
        except ValueError:
            _finding(findings, "WORKBENCH_SOURCE_OUTSIDE_ROOT", source_id=source_id)
            continue
        if not source_path.is_file():
            _finding(findings, "WORKBENCH_SOURCE_MISSING", source_id=source_id)
            continue
        if _sha256(source_path).casefold() != declared_hash.casefold():
            _finding(findings, "WORKBENCH_SOURCE_HASH_MISMATCH", source_id=source_id)
            continue
        sources[source_id] = {"role": raw["role"], "path": source_path}
    return sources


def _question_scopes(tex: str) -> tuple[dict[str, str], set[str]]:
    scopes: dict[str, list[str]] = defaultdict(list)
    method_questions: set[str] = set()
    for question_id, title, _start, _content_start, body in question_sections(tex):
        scopes[question_id].append("\n".join((visible_prose(title), visible_prose(body))))
        if first_method_introduction(title, body) is not None:
            method_questions.add(question_id)
    return {key: "\n".join(parts) for key, parts in scopes.items()}, method_questions


def _parse_anchor(raw: object, question_id: str, findings: list[dict]) -> dict | None:
    if not isinstance(raw, dict):
        _finding(findings, "WORKBENCH_ANCHOR_INVALID", question_id=question_id)
        return None
    anchor_id = raw.get("id")
    terms = _nonempty_strings(raw.get("terms"))
    if (
        not isinstance(anchor_id, str) or not anchor_id.strip() or terms is None
        or raw.get("kind") not in ANCHOR_KINDS
        or not isinstance(raw.get("source_ref"), str) or len(raw["source_ref"].strip()) < 3
    ):
        _finding(findings, "WORKBENCH_ANCHOR_FIELDS_INVALID", question_id=question_id)
        return None
    source_ids = _nonempty_strings(raw.get("source_ids"))
    if source_ids is None:
        _finding(findings, "WORKBENCH_ANCHOR_SOURCES_INVALID", question_id=question_id, anchor_id=anchor_id)
        return None
    return {
        "id": anchor_id.strip(), "kind": raw.get("kind"),
        "terms": terms, "source_ids": source_ids,
    }


def _parse_target(raw: object, question_id: str, findings: list[dict]) -> dict | None:
    if not isinstance(raw, dict):
        _finding(findings, "WORKBENCH_TARGET_INVALID", question_id=question_id)
        return None
    target_id = raw.get("id")
    terms = _nonempty_strings(raw.get("terms"))
    if (
        not isinstance(target_id, str) or not target_id.strip() or terms is None
        or not isinstance(raw.get("source_ref"), str) or len(raw["source_ref"].strip()) < 3
    ):
        _finding(findings, "WORKBENCH_TARGET_FIELDS_INVALID", question_id=question_id)
        return None
    return {"id": target_id.strip(), "terms": terms}


def _artifact_ok(raw: object, root: Path, findings: list[dict], question_id: str, check_id: str) -> bool:
    if raw is None:
        return False
    if not isinstance(raw, dict) or not isinstance(raw.get("path"), str) or not raw["path"].strip():
        _finding(findings, "WORKBENCH_ARTIFACT_INVALID", question_id=question_id, check_id=check_id)
        return False
    artifact = (root / raw["path"]).resolve()
    try:
        artifact.relative_to(root.resolve())
    except ValueError:
        _finding(findings, "WORKBENCH_ARTIFACT_OUTSIDE_ROOT", question_id=question_id, check_id=check_id)
        return False
    if not artifact.is_file():
        _finding(findings, "WORKBENCH_ARTIFACT_MISSING", question_id=question_id, check_id=check_id)
        return False
    declared_hash = raw.get("sha256")
    if declared_hash is not None:
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if not isinstance(declared_hash, str) or declared_hash.casefold() != actual_hash:
            _finding(findings, "WORKBENCH_ARTIFACT_HASH_MISMATCH", question_id=question_id, check_id=check_id)
            return False
    return True


def audit(tex_path: Path, workbench_path: Path, phase: str = "release") -> dict:
    if phase not in {"preflight", "release"}:
        raise ValueError(f"unsupported workbench audit phase: {phase}")
    findings: list[dict] = []
    tex_path = tex_path.resolve()
    workbench_path = workbench_path.resolve()
    inputs = {
        "main_tex": _input_record(tex_path),
        "workbench": _input_record(workbench_path),
    }
    if not tex_path.is_file():
        _finding(findings, "WORKBENCH_MANUSCRIPT_MISSING", path=str(tex_path))
        return _report(findings, 0, 0, inputs, phase)
    payload = _load(workbench_path, findings)
    if payload is None:
        return _report(findings, 0, 0, inputs, phase)
    if payload.get("schema") != SCHEMA:
        _finding(findings, "WORKBENCH_SCHEMA_MISMATCH", expected=SCHEMA, actual=payload.get("schema"))
    sources = _parse_sources(payload, workbench_path.parent, findings)
    tex = tex_path.read_text(encoding="utf-8-sig")
    scopes, method_questions = _question_scopes(tex)
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        _finding(findings, "WORKBENCH_QUESTIONS_INVALID")
        return _report(findings, len(scopes), 0, inputs, phase)

    declared_ids: set[str] = set()
    validated = 0
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            _finding(findings, "WORKBENCH_QUESTION_INVALID")
            continue
        question_id = str(raw_question.get("id", "")).strip()
        if not question_id or question_id in declared_ids:
            _finding(findings, "WORKBENCH_QUESTION_ID_INVALID", question_id=question_id)
            continue
        declared_ids.add(question_id)
        scope = scopes.get(question_id)
        if scope is None:
            _finding(findings, "WORKBENCH_QUESTION_SCOPE_MISSING", question_id=question_id)
            continue

        anchors: dict[str, dict] = {}
        raw_anchors = raw_question.get("anchors")
        if not isinstance(raw_anchors, list) or not raw_anchors:
            _finding(findings, "WORKBENCH_ANCHORS_MISSING", question_id=question_id)
        else:
            for raw_anchor in raw_anchors:
                anchor = _parse_anchor(raw_anchor, question_id, findings)
                if anchor is None:
                    continue
                if anchor["id"] in anchors:
                    _finding(findings, "WORKBENCH_ANCHOR_ID_DUPLICATE", question_id=question_id, anchor_id=anchor["id"])
                    continue
                anchors[anchor["id"]] = anchor
                if any(source_id not in sources for source_id in anchor["source_ids"]):
                    _finding(findings, "WORKBENCH_ANCHOR_SOURCE_UNKNOWN", question_id=question_id, anchor_id=anchor["id"])
                if phase == "release" and _first_position(scope, anchor["terms"]) is None:
                    _finding(findings, "WORKBENCH_ANCHOR_NOT_IN_SCOPE", question_id=question_id, anchor_id=anchor["id"])

        targets: dict[str, dict] = {}
        raw_targets = raw_question.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            _finding(findings, "WORKBENCH_TARGETS_MISSING", question_id=question_id)
        else:
            for raw_target in raw_targets:
                target = _parse_target(raw_target, question_id, findings)
                if target is None:
                    continue
                if target["id"] in targets:
                    _finding(findings, "WORKBENCH_TARGET_ID_DUPLICATE", question_id=question_id, target_id=target["id"])
                    continue
                targets[target["id"]] = target
                if phase == "release" and _first_position(scope, target["terms"]) is None:
                    _finding(findings, "WORKBENCH_TARGET_NOT_IN_SCOPE", question_id=question_id, target_id=target["id"])

        selected: list[dict] = []
        raw_routes = raw_question.get("routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            _finding(findings, "WORKBENCH_ROUTES_MISSING", question_id=question_id)
            raw_routes = []
        route_ids: set[str] = set()
        for route in raw_routes:
            if not isinstance(route, dict):
                _finding(findings, "WORKBENCH_ROUTE_INVALID", question_id=question_id)
                continue
            route_id = route.get("id")
            terms = _nonempty_strings(route.get("terms"))
            anchor_ids = _nonempty_strings(route.get("anchor_ids"))
            target_ids = _nonempty_strings(route.get("target_ids"))
            evidence_ids = _nonempty_strings(route.get("evidence_ids"))
            status = route.get("status")
            if (
                not isinstance(route_id, str) or not route_id.strip() or route_id in route_ids
                or not isinstance(route.get("name"), str) or not route["name"].strip()
                or terms is None or anchor_ids is None or target_ids is None or evidence_ids is None or status not in ROUTE_STATUSES
                or not isinstance(route.get("evidence_ref"), str) or len(route["evidence_ref"].strip()) < 3
            ):
                _finding(findings, "WORKBENCH_ROUTE_FIELDS_INVALID", question_id=question_id)
                continue
            route_ids.add(route_id)
            if any(anchor_id not in anchors for anchor_id in anchor_ids):
                _finding(findings, "WORKBENCH_ROUTE_ANCHOR_UNKNOWN", question_id=question_id, route_id=route_id)
            if any(target_id not in targets for target_id in target_ids):
                _finding(findings, "WORKBENCH_ROUTE_TARGET_UNKNOWN", question_id=question_id, route_id=route_id)
            if any(source_id not in sources for source_id in evidence_ids):
                _finding(findings, "WORKBENCH_ROUTE_EVIDENCE_UNKNOWN", question_id=question_id, route_id=route_id)
            if status in {"rejected", "deferred"} and (
                not isinstance(route.get("reason"), str) or len(route["reason"].strip()) < 3
            ):
                _finding(findings, "WORKBENCH_NONSELECTED_ROUTE_REASON_MISSING", question_id=question_id, route_id=route_id)
            if status == "selected":
                selected.append({
                    "id": route_id,
                    "terms": terms,
                    "anchor_ids": anchor_ids,
                    "target_ids": target_ids,
                    "position": _first_position(scope, terms),
                })
                route_position = _first_position(scope, terms)
                if phase == "release" and route_position is None:
                    _finding(findings, "WORKBENCH_SELECTED_ROUTE_NOT_IN_SCOPE", question_id=question_id, route_id=route_id)
                elif phase == "release":
                    anchor_positions = [_first_position(scope, anchors[anchor_id]["terms"]) for anchor_id in anchor_ids if anchor_id in anchors]
                    if not any(position is not None and position < route_position for position in anchor_positions):
                        _finding(findings, "WORKBENCH_SELECTED_ROUTE_WITHOUT_PRECEDING_ANCHOR", question_id=question_id, route_id=route_id)
        if len(selected) != 1:
            _finding(findings, "WORKBENCH_SELECTED_ROUTE_COUNT_INVALID", question_id=question_id, count=len(selected))

        raw_checks = raw_question.get("checks", [])
        if not isinstance(raw_checks, list):
            _finding(findings, "WORKBENCH_CHECKS_INVALID", question_id=question_id)
        else:
            check_ids: set[str] = set()
            for check in raw_checks:
                if not isinstance(check, dict):
                    _finding(findings, "WORKBENCH_CHECK_INVALID", question_id=question_id)
                    continue
                check_id = check.get("id")
                terms = check.get("terms")
                terms_valid = terms is None or _nonempty_strings(terms) is not None
                result_terms = check.get("result_terms")
                result_terms_valid = (
                    result_terms is None or _nonempty_strings(result_terms) is not None
                )
                if (
                    not isinstance(check_id, str) or not check_id.strip() or check_id in check_ids
                    or check.get("kind") not in CHECK_KINDS
                    or not isinstance(check.get("result"), str) or len(check["result"].strip()) < 3
                    or not terms_valid or not result_terms_valid
                ):
                    _finding(findings, "WORKBENCH_CHECK_FIELDS_INVALID", question_id=question_id)
                    continue
                check_ids.add(check_id)
                terms_list = _nonempty_strings(terms) if terms is not None else None
                artifact_ok = _artifact_ok(check.get("artifact"), workbench_path.parent, findings, question_id, check_id)
                if terms_list is None and not artifact_ok:
                    _finding(findings, "WORKBENCH_CHECK_WITHOUT_SUPPORT", question_id=question_id, check_id=check_id)
                elif (
                    phase == "release" and terms_list is not None
                    and _first_position(scope, terms_list) is None and not artifact_ok
                ):
                    _finding(findings, "WORKBENCH_CHECK_NOT_IN_SCOPE", question_id=question_id, check_id=check_id)

        raw_interpretations = raw_question.get("interpretations", [])
        if not isinstance(raw_interpretations, list):
            _finding(findings, "WORKBENCH_INTERPRETATIONS_INVALID", question_id=question_id)
        else:
            interpretation_ids: set[str] = set()
            for interpretation in raw_interpretations:
                if not isinstance(interpretation, dict):
                    _finding(findings, "WORKBENCH_INTERPRETATION_INVALID", question_id=question_id)
                    continue
                interpretation_id = interpretation.get("id")
                observation_terms = _nonempty_strings(interpretation.get("observation_terms"))
                explanation_terms = _nonempty_strings(interpretation.get("explanation_terms"))
                source_ids = _nonempty_strings(interpretation.get("source_ids"))
                if (
                    not isinstance(interpretation_id, str) or not interpretation_id.strip()
                    or interpretation_id in interpretation_ids
                    or interpretation.get("kind") not in INTERPRETATION_KINDS
                    or observation_terms is None or explanation_terms is None
                    or source_ids is None
                    or not isinstance(interpretation.get("source_ref"), str)
                    or len(interpretation["source_ref"].strip()) < 3
                ):
                    _finding(
                        findings, "WORKBENCH_INTERPRETATION_FIELDS_INVALID",
                        question_id=question_id,
                    )
                    continue
                interpretation_ids.add(interpretation_id)
                unknown = [source_id for source_id in source_ids if source_id not in sources]
                if unknown:
                    _finding(
                        findings, "WORKBENCH_INTERPRETATION_SOURCE_UNKNOWN",
                        question_id=question_id, interpretation_id=interpretation_id,
                        source_ids=unknown,
                    )
                elif not any(
                    sources[source_id]["role"] in INTERPRETATION_SOURCE_ROLES
                    for source_id in source_ids
                ):
                    _finding(
                        findings, "WORKBENCH_INTERPRETATION_WITHOUT_RESULT_SOURCE",
                        question_id=question_id, interpretation_id=interpretation_id,
                    )

        drafting = raw_question.get("drafting")
        if not isinstance(drafting, dict) or drafting.get("mode") not in DRAFTING_MODES:
            _finding(findings, "WORKBENCH_DRAFTING_INVALID", question_id=question_id)
        elif drafting.get("public_route_id") not in {route["id"] for route in selected}:
            _finding(findings, "WORKBENCH_DRAFTING_ROUTE_INVALID", question_id=question_id)
        elif phase == "release" and len(selected) == 1:
            route = selected[0]
            route_position = route["position"]
            target_positions = [
                _first_position(scope, targets[target_id]["terms"])
                for target_id in route["target_ids"] if target_id in targets
            ]
            anchor_positions = [
                _first_position(scope, anchors[anchor_id]["terms"])
                for anchor_id in route["anchor_ids"] if anchor_id in anchors
            ]
            if drafting["mode"] == "direct_derivation":
                bridge_exists = any(
                    anchor is not None and target is not None and route_position is not None
                    and anchor < target <= route_position
                    for anchor in anchor_positions for target in target_positions
                )
            else:
                bridge_exists = any(
                    anchor is not None and target is not None and route_position is not None
                    and anchor < target < route_position
                    for anchor in anchor_positions for target in target_positions
                )
            if not bridge_exists:
                _finding(
                    findings,
                    "WORKBENCH_REASONING_BRIDGE_MISSING",
                    question_id=question_id,
                    route_id=route["id"],
                    mode=drafting["mode"],
                )
        validated += 1

    for question_id in sorted(set(scopes) - declared_ids):
        _finding(findings, "WORKBENCH_MANUSCRIPT_QUESTION_UNDECLARED", question_id=question_id)
    for question_id in sorted(declared_ids - set(scopes)):
        _finding(findings, "WORKBENCH_DECLARED_QUESTION_NOT_IN_MANUSCRIPT", question_id=question_id)
    if phase == "release":
        for question_id in sorted(method_questions - declared_ids):
            _finding(findings, "WORKBENCH_METHOD_QUESTION_UNDECLARED", question_id=question_id)
    return _report(findings, len(scopes), validated, inputs, phase)


def _report(
    findings: list[dict], manuscript_questions: int, workbench_questions: int,
    inputs: dict, phase: str = "release",
) -> dict:
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "mcm-modeling-workbench-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "phase": phase,
        "errors": errors,
        "warnings": 0,
        "inputs": inputs,
        "manuscript_questions": manuscript_questions,
        "workbench_questions": workbench_questions,
        "findings": findings,
        "interpretation": (
            "Preflight passing confirms frozen sources, workbench structure, and question mapping before drafting; "
            "it does not require the initial draft to already contain the intended reasoning bridge. Release passing "
            "additionally confirms local anchors, mathematical transitions, selected routes, and declared checks are "
            "visible in the candidate. Neither phase proves mathematical correctness, hidden reasoning, or authorship."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--workbench", type=Path, required=True)
    parser.add_argument("--phase", choices=("preflight", "release"), default="release")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.workbench, args.phase)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"MODELING WORKBENCH {report['status'].upper()} phase={report['phase']} questions="
            f"{report['workbench_questions']}/{report['manuscript_questions']} errors={report['errors']}"
        )
        for finding in report["findings"]:
            detail = ", ".join(f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"})
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
