#!/usr/bin/env python3
"""Audit CUMCM dev/holdout style suites against the verified full-text corpus.

Public interface:
    python audit_cumcm_style_benchmark.py --format text|json

The audit validates frozen source provenance and retrieval isolation. It does
not score prose, decide authorship, or infer any detector outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
import subprocess
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"
FULLTEXT_INDEX = REFERENCES / "fulltext-style-index.jsonl"
RESERVATION_PATH = REFERENCES / "style-benchmark-holdout.json"
DEFAULT_ROUTER_ROOT = SKILL_ROOT.parent / "AIGC" / "aigc-writing-router"
DEFAULT_RUNS_REGISTRY = REFERENCES / "style-benchmark-runs.json"
SUITE_SCHEMA = "aigc-style-benchmark-suite/v1"
MANIFEST_SCHEMA = "aigc-style-benchmark-manifest/v1"
RESERVATION_SCHEMAS = {
    "cumcm-style-holdout-reservations/v1",
    "cumcm-style-holdout-reservations/v2",
}
EXPECTED_SUITES = {
    "dev": "cumcm-v1-dev",
    "holdout": "cumcm-v1-holdout",
}
LEGACY_TRANSPORT_CONTENT_ERRORS = {
    "BENCHMARK_CANDIDATE_CONTENT_UNCHANGED",
    "BENCHMARK_CANDIDATE_CONTENT_TOO_SMALL",
    "BENCHMARK_TRIAL_CONTENT_DUPLICATE",
    "BENCHMARK_TRIAL_CONTENT_NEAR_DUPLICATE",
    "BENCHMARK_GOAL_MISSING_OR_INVALID",
    "BENCHMARK_AUTHORING_DECISION_MISSING_OR_INVALID",
    "BENCHMARK_AUTHORING_DECISION_LOCK_MISMATCH",
    "BENCHMARK_CONTENT_EVIDENCE_MISSING",
}


def resolve_runs_root(explicit: Path | None, registry_path: Path) -> Path:
    if explicit is not None:
        return explicit.resolve()
    environment = os.environ.get("CUMCM_STYLE_BENCHMARK_RUNS", "").strip()
    if environment:
        return Path(environment).resolve()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = {}
    if (
        isinstance(registry, dict)
        and registry.get("schema") == "cumcm-style-benchmark-runs/v1"
        and isinstance(registry.get("active_runs_root"), str)
        and registry["active_runs_root"].strip()
    ):
        return Path(registry["active_runs_root"]).resolve()
    return (Path.cwd() / ".cumcm-work" / "aigc-style-benchmark").resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path, findings: list[dict], label: str) -> dict | None:
    if not path.is_file():
        findings.append({"severity": "error", "code": "BENCHMARK_FILE_MISSING", "label": label, "path": str(path)})
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append({"severity": "error", "code": "BENCHMARK_JSON_INVALID", "label": label, "error": str(exc)})
        return None
    if not isinstance(payload, dict):
        findings.append({"severity": "error", "code": "BENCHMARK_JSON_NOT_OBJECT", "label": label})
        return None
    return payload


def _add(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def _add_warning(findings: list[dict], code: str, **detail: object) -> None:
    findings.append({"severity": "warning", "code": code, **detail})


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _path(value: object) -> Path:
    """Normalize Windows extended-length paths emitted by a frozen manifest."""
    raw = str(value)
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    return Path(raw)


def _load_index(findings: list[dict]) -> dict[str, dict]:
    if not FULLTEXT_INDEX.is_file():
        _add(findings, "FULLTEXT_INDEX_MISSING", path=str(FULLTEXT_INDEX))
        return {}
    records: dict[str, dict] = {}
    try:
        with FULLTEXT_INDEX.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                record["_index_line"] = line_number
                record_id = str(record.get("id", ""))
                if not record_id or record_id in records:
                    _add(findings, "FULLTEXT_INDEX_ID_INVALID", record_id=record_id, line=line_number)
                    continue
                records[record_id] = record
    except (OSError, json.JSONDecodeError) as exc:
        _add(findings, "FULLTEXT_INDEX_INVALID", error=str(exc))
    return records


def _check_provenance(
    suite_path: Path,
    case: dict,
    record: dict,
    findings: list[dict],
) -> None:
    case_id = str(case.get("id", ""))
    provenance = case.get("provenance")
    if not isinstance(provenance, dict):
        _add(findings, "BENCHMARK_PROVENANCE_MISSING", case_id=case_id)
        return
    if provenance.get("record_id") != record.get("id"):
        _add(findings, "BENCHMARK_RECORD_ID_MISMATCH", case_id=case_id)
    expected_paper = str(record.get("source", "")).split("#", 1)[0]
    if provenance.get("paper") != expected_paper:
        _add(
            findings,
            "BENCHMARK_PAPER_LOCATOR_MISMATCH",
            case_id=case_id,
            expected=expected_paper,
            actual=provenance.get("paper"),
        )
    if provenance.get("section") != record.get("section"):
        _add(
            findings,
            "BENCHMARK_SECTION_MISMATCH",
            case_id=case_id,
            expected=record.get("section"),
            actual=provenance.get("section"),
        )
    expected_pages = [record.get("page_start"), record.get("page_end")]
    declared_pages = provenance.get("pages")
    if declared_pages is None:
        declared_pages = [provenance.get("page"), provenance.get("page")]
    if declared_pages != expected_pages:
        _add(
            findings,
            "BENCHMARK_PAGE_MISMATCH",
            case_id=case_id,
            expected=expected_pages,
            actual=declared_pages,
        )
    expected_index = f"mcm-cup-standard-write/references/fulltext-style-index.jsonl:{record['_index_line']}"
    if provenance.get("index") != expected_index:
        _add(
            findings,
            "BENCHMARK_INDEX_LOCATOR_MISMATCH",
            case_id=case_id,
            expected=expected_index,
            actual=provenance.get("index"),
        )
    source_value = case.get("source")
    source_path = (suite_path.parent / str(source_value)).resolve()
    if not _is_inside(source_path, suite_path.parent):
        _add(findings, "BENCHMARK_SOURCE_OUTSIDE_SUITE", case_id=case_id, path=str(source_path))
        return
    if not source_path.is_file():
        _add(findings, "BENCHMARK_SOURCE_MISSING", case_id=case_id, path=str(source_path))
        return
    if source_path.read_text(encoding="utf-8-sig").strip() != str(record.get("text", "")).strip():
        _add(findings, "BENCHMARK_SOURCE_TEXT_DRIFT", case_id=case_id, path=str(source_path))


def _check_suite(
    suite_path: Path,
    split: str,
    records: dict[str, dict],
    findings: list[dict],
    expected_suite_id: str | None = None,
    expected_benchmark_goal: str | None = None,
) -> dict[str, dict]:
    suite = _load(suite_path, findings, f"{split}-suite")
    if suite is None:
        return {}
    if suite.get("schema") != SUITE_SCHEMA:
        _add(findings, "BENCHMARK_SUITE_SCHEMA_MISMATCH", split=split)
    expected_id = expected_suite_id or EXPECTED_SUITES[split]
    if suite.get("suite_id") != expected_id or suite.get("split") != split:
        _add(findings, "BENCHMARK_SUITE_ID_OR_SPLIT_MISMATCH", split=split)
    if expected_benchmark_goal is not None and suite.get("benchmark_goal") != expected_benchmark_goal:
        _add(
            findings, "BENCHMARK_SUITE_GOAL_MISMATCH", split=split,
            expected=expected_benchmark_goal, actual=suite.get("benchmark_goal"),
        )
    if suite.get("providers") != ["humanize-academic-chinese"] or suite.get("required_trials") != 3:
        _add(findings, "BENCHMARK_SUITE_CANDIDATE_CONTRACT_MISMATCH", split=split)
    if split == "holdout":
        policy = suite.get("holdout_policy")
        if not isinstance(policy, dict) or not str(policy.get("curator", "")).strip() or not str(policy.get("release_id", "")).strip():
            _add(findings, "BENCHMARK_HOLDOUT_POLICY_INVALID")

    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        _add(findings, "BENCHMARK_CASE_COUNT_INVALID", split=split)
        return {}
    selected: dict[str, dict] = {}
    type_counts: Counter[str] = Counter()
    for case in cases:
        if not isinstance(case, dict):
            _add(findings, "BENCHMARK_CASE_INVALID", split=split)
            continue
        case_id = str(case.get("id", ""))
        provenance = case.get("provenance")
        record_id = str(provenance.get("record_id", "")) if isinstance(provenance, dict) else ""
        if not case_id or case_id in selected:
            _add(findings, "BENCHMARK_CASE_ID_INVALID", split=split, case_id=case_id)
            continue
        record = records.get(record_id)
        if record is None:
            _add(findings, "BENCHMARK_RECORD_NOT_IN_CORPUS", split=split, case_id=case_id, record_id=record_id)
            continue
        selected[case_id] = record
        type_counts[str(record.get("problem_type", ""))] += 1
        if record.get("quality") != "high" or not record.get("retrieval_eligible"):
            _add(findings, "BENCHMARK_RECORD_NOT_RETRIEVAL_READY", case_id=case_id, record_id=record_id)
        scene = case.get("scene")
        if not isinstance(scene, dict) or scene != {"document_type": "mcm", "document_format": "plain", "scope": "local"}:
            _add(findings, "BENCHMARK_SCENE_INVALID", case_id=case_id)
        tags = case.get("challenge_tags")
        if not isinstance(tags, list) or "public-judgment" not in tags:
            _add(findings, "BENCHMARK_JUDGMENT_CHALLENGE_MISSING", case_id=case_id)
        _check_provenance(suite_path, case, record, findings)
    if dict(type_counts) != {"A": 1, "B": 1, "C": 1}:
        _add(findings, "BENCHMARK_ABC_COVERAGE_INVALID", split=split, actual=dict(type_counts))
    return selected


def _check_reservation(
    reservation_path: Path,
    holdout_records: dict[str, dict],
    findings: list[dict],
    expected_suite_id: str | None = None,
) -> None:
    reservation = _load(reservation_path, findings, "holdout-reservation")
    if reservation is None:
        return
    if reservation.get("schema") not in RESERVATION_SCHEMAS:
        _add(findings, "BENCHMARK_RESERVATION_SCHEMA_MISMATCH")
    expected_id = expected_suite_id or EXPECTED_SUITES["holdout"]
    raw_benchmarks = reservation.get("benchmarks")
    if not isinstance(raw_benchmarks, list):
        legacy = reservation.get("benchmark")
        raw_benchmarks = [legacy] if isinstance(legacy, dict) else []
    benchmark_ids = {
        str(item.get("suite_id")) for item in raw_benchmarks if isinstance(item, dict)
    }
    if expected_id not in benchmark_ids:
        _add(findings, "BENCHMARK_RESERVATION_SUITE_MISMATCH")
    expected_ids = {str(record.get("id")) for record in holdout_records.values()}
    actual_ids = set(reservation.get("reserved_record_ids", []))
    if not expected_ids.issubset(actual_ids):
        _add(
            findings,
            "BENCHMARK_RESERVATION_RECORDS_MISMATCH",
            expected=sorted(expected_ids),
            actual=sorted(actual_ids),
        )


def _check_frozen_run(
    suite_path: Path,
    selected: dict[str, dict],
    runs_root: Path,
    findings: list[dict],
) -> None:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite_id = str(suite.get("suite_id"))
    manifest_path = runs_root / suite_id / "benchmark-source-frozen.json"
    if not manifest_path.is_file():
        findings.append({"severity": "warning", "code": "BENCHMARK_FROZEN_RUN_NOT_FOUND", "suite_id": suite_id, "path": str(manifest_path)})
        return
    manifest = _load(manifest_path, findings, f"{suite_id}-frozen-run")
    if manifest is None:
        return
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("state") != "SOURCE_FROZEN":
        _add(findings, "BENCHMARK_FROZEN_RUN_STATE_INVALID", suite_id=suite_id)
    frozen_suite = manifest.get("suite")
    if not isinstance(frozen_suite, dict) or frozen_suite.get("id") != suite_id:
        _add(findings, "BENCHMARK_FROZEN_RUN_SUITE_MISMATCH", suite_id=suite_id)
    else:
        definition = frozen_suite.get("definition")
        if not isinstance(definition, dict) or definition.get("sha256") != _sha256(suite_path):
            _add(findings, "BENCHMARK_FROZEN_DEFINITION_DRIFT", suite_id=suite_id)
    frozen_cases = manifest.get("cases")
    if not isinstance(frozen_cases, list) or {case.get("id") for case in frozen_cases if isinstance(case, dict)} != set(selected):
        _add(findings, "BENCHMARK_FROZEN_CASES_MISMATCH", suite_id=suite_id)
        return
    source_by_id = {case["id"]: case.get("source") for case in frozen_cases if isinstance(case, dict)}
    for case in suite.get("cases", []):
        case_id = case.get("id")
        lock = source_by_id.get(case_id)
        original = (suite_path.parent / str(case.get("source"))).resolve()
        if not isinstance(lock, dict) or not original.is_file():
            _add(findings, "BENCHMARK_FROZEN_SOURCE_LOCK_INVALID", suite_id=suite_id, case_id=case_id)
            continue
        snapshot = _path(lock.get("path", "")).resolve()
        if not _is_inside(snapshot, runs_root / suite_id / "sources") or not snapshot.is_file():
            _add(findings, "BENCHMARK_FROZEN_SOURCE_PATH_INVALID", suite_id=suite_id, case_id=case_id)
            continue
        if lock.get("sha256") != _sha256(snapshot) or lock.get("sha256") != _sha256(original):
            _add(findings, "BENCHMARK_FROZEN_SOURCE_HASH_DRIFT", suite_id=suite_id, case_id=case_id)


def _check_active_manifests(
    registry_path: Path,
    dev_suite: Path,
    holdout_suite: Path,
    runs_root: Path,
    findings: list[dict],
) -> dict[str, str]:
    registry = _load(registry_path, findings, "active-runs-registry")
    if registry is None:
        return {}
    if registry.get("schema") != "cumcm-style-benchmark-runs/v1":
        _add(findings, "BENCHMARK_RUNS_REGISTRY_SCHEMA_MISMATCH")
        return {}
    active = registry.get("active_manifests")
    if not isinstance(active, dict):
        _add(findings, "BENCHMARK_ACTIVE_MANIFESTS_MISSING")
        return {}
    audit_script = dev_suite.parents[2] / "scripts" / "run_style_benchmark.py"
    if not audit_script.is_file():
        _add(findings, "BENCHMARK_ROUTER_AUDITOR_MISSING", path=str(audit_script))
        return {}
    states: dict[str, str] = {}
    for split, suite_path in (("dev", dev_suite), ("holdout", holdout_suite)):
        item = active.get(split)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            _add(findings, "BENCHMARK_ACTIVE_MANIFEST_INVALID", split=split)
            continue
        manifest_path = _path(item["path"]).resolve()
        if not _is_inside(manifest_path, runs_root) or not manifest_path.is_file():
            _add(findings, "BENCHMARK_ACTIVE_MANIFEST_PATH_INVALID", split=split, path=str(manifest_path))
            continue
        if str(item["sha256"]).casefold() != _sha256(manifest_path).casefold():
            _add(findings, "BENCHMARK_ACTIVE_MANIFEST_HASH_DRIFT", split=split)
            continue
        completed = subprocess.run(
            [sys.executable, str(audit_script), "audit", str(manifest_path), "--format", "json"],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False,
        )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError:
            _add(findings, "BENCHMARK_ACTIVE_MANIFEST_AUDIT_INVALID", split=split)
            continue
        error_codes = {
            str(finding.get("code")) for finding in report.get("findings", [])
            if finding.get("severity") == "error"
        }
        historical_transport_only = item.get("historical_transport_only") is True
        legacy_content_only = (
            completed.returncode != 0
            and historical_transport_only
            and report.get("rule_freshness") == "historical-unbound"
            and bool(error_codes)
            and error_codes.issubset(LEGACY_TRANSPORT_CONTENT_ERRORS)
        )
        if completed.returncode != 0 and not legacy_content_only:
            _add(
                findings, "BENCHMARK_ACTIVE_MANIFEST_AUDIT_FAILED",
                split=split, returncode=completed.returncode,
                error_codes=sorted(error_codes), stderr=completed.stderr[-500:],
            )
            continue
        if legacy_content_only:
            _add_warning(
                findings, "BENCHMARK_ACTIVE_HISTORICAL_CONTENT_INVALID",
                split=split, error_codes=sorted(error_codes),
            )
        if report.get("rule_freshness") != "current-bound":
            _add_warning(
                findings, "BENCHMARK_ACTIVE_RULES_NOT_CURRENT_BOUND",
                split=split, freshness=report.get("rule_freshness", "historical-unbound"),
            )
        expected_suite = json.loads(suite_path.read_text(encoding="utf-8"))
        expected_candidates = len(expected_suite.get("cases", [])) * int(expected_suite.get("required_trials", 0))
        allowed_states = {"BLIND_READY", "SCORED_DEV"} if split == "dev" else {"BLIND_READY", "SCORED_HOLDOUT_SEALED"}
        if (
            (report.get("status") != "pass" and not legacy_content_only)
            or report.get("suite_id") != expected_suite.get("suite_id")
            or report.get("state") not in allowed_states
            or report.get("candidates") != expected_candidates
        ):
            _add(findings, "BENCHMARK_ACTIVE_MANIFEST_STATE_INVALID", split=split, report=report)
            continue
        states[split] = str(report["state"])
    return states


def _check_current_rule_suites(
    registry_path: Path,
    dev_suite: Path,
    holdout_suite: Path,
    runs_root: Path,
    records: dict[str, dict],
    reservation_path: Path,
    findings: list[dict],
) -> dict[str, str]:
    """Audit registered suites prepared under the current writing-rule tree."""
    registry = _load(registry_path, findings, "current-rule-runs-registry")
    if registry is None:
        return {}
    entries = registry.get("current_rule_suites")
    if not isinstance(entries, dict):
        _add(findings, "BENCHMARK_CURRENT_RULE_SUITES_MISSING")
        return {}
    audit_script = dev_suite.parents[2] / "scripts" / "run_style_benchmark.py"
    if not audit_script.is_file():
        _add(findings, "BENCHMARK_ROUTER_AUDITOR_MISSING", path=str(audit_script))
        return {}
    states: dict[str, str] = {}
    for split in ("dev", "holdout"):
        item = entries.get(split)
        if not isinstance(item, dict):
            _add(findings, "BENCHMARK_CURRENT_RULE_SUITE_INVALID", split=split)
            continue
        expected_suite_id = str(item.get("suite_id", "")).strip()
        definition_path = _path(item.get("definition_path", "")).resolve()
        if (
            not expected_suite_id
            or not definition_path.is_file()
            or str(item.get("definition_sha256", "")).casefold()
            != _sha256(definition_path).casefold()
        ):
            _add(
                findings, "BENCHMARK_CURRENT_RULE_DEFINITION_INVALID",
                split=split, path=str(definition_path),
            )
            continue
        selected = _check_suite(
            definition_path, split, records, findings,
            expected_suite_id=expected_suite_id,
            expected_benchmark_goal="preservation",
        )
        if split == "holdout":
            _check_reservation(
                reservation_path, selected, findings,
                expected_suite_id=expected_suite_id,
            )
        manifest_path = _path(item.get("path", "")).resolve()
        if not _is_inside(manifest_path, runs_root) or not manifest_path.is_file():
            _add(
                findings, "BENCHMARK_CURRENT_RULE_SUITE_PATH_INVALID",
                split=split, path=str(manifest_path),
            )
            continue
        if str(item.get("sha256", "")).casefold() != _sha256(manifest_path).casefold():
            _add(findings, "BENCHMARK_CURRENT_RULE_SUITE_HASH_DRIFT", split=split)
            continue
        completed = subprocess.run(
            [sys.executable, str(audit_script), "audit", str(manifest_path), "--format", "json"],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False,
        )
        if completed.returncode != 0:
            _add(
                findings, "BENCHMARK_CURRENT_RULE_SUITE_AUDIT_FAILED",
                split=split, returncode=completed.returncode, stderr=completed.stderr[-500:],
            )
            continue
        try:
            report = json.loads(completed.stdout)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _add(findings, "BENCHMARK_CURRENT_RULE_SUITE_AUDIT_INVALID", split=split)
            continue
        definition = manifest.get("suite", {}).get("definition", {})
        expected_state = str(item.get("state", ""))
        expected_candidates = item.get("candidates")
        if (
            item.get("rule_freshness") != "current-bound"
            or report.get("status") != "pass"
            or report.get("rule_freshness") != "current-bound"
            or report.get("benchmark_goal") != "preservation"
            or report.get("suite_id") != expected_suite_id
            or report.get("state") != expected_state
            or not isinstance(expected_candidates, int)
            or report.get("candidates") != expected_candidates
            or not isinstance(definition, dict)
            or definition.get("sha256") != _sha256(definition_path)
        ):
            _add(
                findings, "BENCHMARK_CURRENT_RULE_SUITE_STATE_INVALID",
                split=split, registration=item, report=report,
            )
            continue
        states[split] = str(report["state"])
    return states


def _check_improvement_definition(
    definition_path: Path,
    split: str,
    expected_suite_id: str,
    build_report: dict,
    source_path: Path,
    source_sha256: str,
    findings: list[dict],
) -> set[str]:
    suite = _load(definition_path, findings, f"improvement-{split}-suite")
    if suite is None:
        return set()
    if (
        suite.get("schema") != SUITE_SCHEMA
        or suite.get("suite_id") != expected_suite_id
        or suite.get("split") != split
        or suite.get("benchmark_goal") != "improvement"
        or suite.get("providers") != ["humanize-academic-chinese"]
        or suite.get("required_trials") != 3
    ):
        _add(findings, "BENCHMARK_IMPROVEMENT_DEFINITION_INVALID", split=split)
    if split == "holdout":
        policy = suite.get("holdout_policy")
        if not isinstance(policy, dict) or not all(
            str(policy.get(key, "")).strip() for key in ("curator", "release_id")
        ):
            _add(findings, "BENCHMARK_IMPROVEMENT_HOLDOUT_POLICY_INVALID")

    build_split = build_report.get(split)
    if not isinstance(build_split, dict):
        _add(findings, "BENCHMARK_IMPROVEMENT_BUILD_SPLIT_MISSING", split=split)
    else:
        declared_suite = _path(build_split.get("suite", "")).resolve()
        if (
            declared_suite != definition_path
            or str(build_split.get("sha256", "")).casefold() != _sha256(definition_path).casefold()
            or build_split.get("cases") != 3
        ):
            _add(findings, "BENCHMARK_IMPROVEMENT_BUILD_SUITE_DRIFT", split=split)

    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        _add(findings, "BENCHMARK_IMPROVEMENT_CASE_COUNT_INVALID", split=split)
        return set()
    original_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    paragraph_hashes: set[str] = set()
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            _add(findings, "BENCHMARK_IMPROVEMENT_CASE_INVALID", split=split)
            continue
        case_id = str(case.get("id", ""))
        if not case_id or case_id in case_ids:
            _add(findings, "BENCHMARK_IMPROVEMENT_CASE_ID_INVALID", split=split, case_id=case_id)
            continue
        case_ids.add(case_id)
        if case.get("scene") != {"document_type": "mcm", "document_format": "tex", "scope": "local"}:
            _add(findings, "BENCHMARK_IMPROVEMENT_SCENE_INVALID", split=split, case_id=case_id)
        tags = case.get("challenge_tags")
        if not isinstance(tags, list) or not {
            "public-judgment", "specificity", "content-density", "semantic-fidelity",
        }.issubset(set(tags)):
            _add(findings, "BENCHMARK_IMPROVEMENT_CHALLENGES_INVALID", split=split, case_id=case_id)
        provenance = case.get("provenance")
        if not isinstance(provenance, dict):
            _add(findings, "BENCHMARK_IMPROVEMENT_PROVENANCE_MISSING", split=split, case_id=case_id)
            continue
        digest = str(provenance.get("paragraph_sha256", ""))
        if (
            provenance.get("kind") != "real-draft-section"
            or _path(provenance.get("source_document", "")).resolve() != source_path
            or str(provenance.get("source_document_sha256", "")).casefold() != source_sha256.casefold()
            or provenance.get("quality_label_used_for_selection") is not False
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.casefold())
            or provenance.get("selection_seed") != build_report.get("seed")
            or not str(provenance.get("heading", "")).strip()
            or digest in paragraph_hashes
        ):
            _add(findings, "BENCHMARK_IMPROVEMENT_PROVENANCE_INVALID", split=split, case_id=case_id)
            continue
        paragraph_hashes.add(digest)
        source_value = case.get("source")
        snapshot = (definition_path.parent / str(source_value)).resolve()
        if not _is_inside(snapshot, definition_path.parent) or not snapshot.is_file():
            _add(findings, "BENCHMARK_IMPROVEMENT_SOURCE_INVALID", split=split, case_id=case_id)
            continue
        snapshot_text = snapshot.read_text(encoding="utf-8-sig").rstrip("\r\n")
        snapshot_digest = hashlib.sha256(snapshot_text.encode("utf-8")).hexdigest()
        start = provenance.get("start_line")
        end = provenance.get("end_line")
        if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= len(original_lines):
            _add(findings, "BENCHMARK_IMPROVEMENT_LINE_RANGE_INVALID", split=split, case_id=case_id)
            continue
        original_excerpt = "\n".join(original_lines[start - 1:end]).strip()
        if snapshot_digest != digest or original_excerpt != snapshot_text:
            _add(findings, "BENCHMARK_IMPROVEMENT_PARAGRAPH_DRIFT", split=split, case_id=case_id)
    return paragraph_hashes


def _check_current_improvement_suites(
    registry_path: Path,
    router_root: Path,
    runs_root: Path,
    findings: list[dict],
) -> dict[str, str]:
    registry = _load(registry_path, findings, "current-improvement-runs-registry")
    if registry is None:
        return {}
    entries = registry.get("current_improvement_suites")
    if not isinstance(entries, dict):
        _add(findings, "BENCHMARK_CURRENT_IMPROVEMENT_SUITES_MISSING")
        return {}
    allowed_root = runs_root.parent.resolve()
    build_lock = entries.get("build_report")
    source_lock = entries.get("source")
    if not isinstance(build_lock, dict) or not isinstance(source_lock, dict):
        _add(findings, "BENCHMARK_IMPROVEMENT_ROOT_LOCKS_MISSING")
        return {}
    build_path = _path(build_lock.get("path", "")).resolve()
    source_path = _path(source_lock.get("path", "")).resolve()
    if (
        not _is_inside(build_path, allowed_root)
        or not build_path.is_file()
        or str(build_lock.get("sha256", "")).casefold() != _sha256(build_path).casefold()
    ):
        _add(findings, "BENCHMARK_IMPROVEMENT_BUILD_REPORT_INVALID", path=str(build_path))
        return {}
    if (
        not source_path.is_file()
        or str(source_lock.get("sha256", "")).casefold() != _sha256(source_path).casefold()
    ):
        _add(findings, "BENCHMARK_IMPROVEMENT_SOURCE_LOCK_INVALID", path=str(source_path))
        return {}
    build_report = _load(build_path, findings, "current-improvement-build-report")
    if build_report is None:
        return {}
    source_sha256 = _sha256(source_path)
    expected_builder = router_root / "scripts" / "prepare_draft_improvement_suite.py"
    builder = build_report.get("builder")
    build_source = build_report.get("source")
    exclusions = build_report.get("exclusion_suites")
    if (
        build_report.get("schema") != "aigc-draft-improvement-suite-build/v1"
        or build_report.get("status") != "pass"
        or build_report.get("selection_uses_quality_labels") is not False
        or not isinstance(builder, dict)
        or _path(builder.get("path", "")).resolve() != expected_builder.resolve()
        or not expected_builder.is_file()
        or str(builder.get("sha256", "")).casefold() != _sha256(expected_builder).casefold()
        or not isinstance(build_source, dict)
        or _path(build_source.get("path", "")).resolve() != source_path
        or str(build_source.get("sha256", "")).casefold() != source_sha256.casefold()
    ):
        _add(findings, "BENCHMARK_IMPROVEMENT_BUILD_PROVENANCE_INVALID")
    excluded_hashes: set[str] = set()
    if not isinstance(exclusions, list) or not exclusions:
        _add(findings, "BENCHMARK_IMPROVEMENT_EXCLUSIONS_MISSING")
    else:
        for index, lock in enumerate(exclusions):
            path = _path(lock.get("path", "")).resolve() if isinstance(lock, dict) else Path()
            if (
                not isinstance(lock, dict)
                or not _is_inside(path, allowed_root)
                or not path.is_file()
                or str(lock.get("sha256", "")).casefold() != _sha256(path).casefold()
                or not isinstance(lock.get("paragraphs"), int)
                or lock.get("paragraphs", 0) < 1
            ):
                _add(findings, "BENCHMARK_IMPROVEMENT_EXCLUSION_LOCK_INVALID", index=index)
                continue
            try:
                excluded_suite = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _add(findings, "BENCHMARK_IMPROVEMENT_EXCLUSION_SUITE_INVALID", index=index)
                continue
            cases = excluded_suite.get("cases")
            suite_hashes: set[str] = set()
            if isinstance(cases, list):
                for case in cases:
                    provenance = case.get("provenance") if isinstance(case, dict) else None
                    if isinstance(provenance, dict):
                        suite_hashes.add(str(provenance.get("paragraph_sha256", "")))
            if (
                not suite_hashes
                or "" in suite_hashes
                or lock.get("paragraphs") != len(suite_hashes)
            ):
                _add(findings, "BENCHMARK_IMPROVEMENT_EXCLUSION_CONTENT_INVALID", index=index)
                continue
            excluded_hashes.update(suite_hashes)
    if (
        not isinstance(build_report.get("eligible_paragraphs_before_exclusions"), int)
        or not isinstance(build_report.get("eligible_paragraphs"), int)
        or not isinstance(build_report.get("excluded_paragraphs"), int)
        or build_report.get("eligible_paragraphs_before_exclusions")
        != build_report.get("eligible_paragraphs") + build_report.get("excluded_paragraphs")
        or build_report.get("excluded_paragraphs") != len(excluded_hashes)
    ):
        _add(findings, "BENCHMARK_IMPROVEMENT_EXCLUSION_COUNTS_INVALID")

    audit_script = router_root / "scripts" / "run_style_benchmark.py"
    if not audit_script.is_file():
        _add(findings, "BENCHMARK_ROUTER_AUDITOR_MISSING", path=str(audit_script))
        return {}
    states: dict[str, str] = {}
    split_hashes: dict[str, set[str]] = {}
    for split in ("dev", "holdout"):
        item = entries.get(split)
        if not isinstance(item, dict):
            _add(findings, "BENCHMARK_CURRENT_IMPROVEMENT_SUITE_INVALID", split=split)
            continue
        expected_suite_id = str(item.get("suite_id", ""))
        definition_path = _path(item.get("definition_path", "")).resolve()
        manifest_path = _path(item.get("path", "")).resolve()
        if (
            item.get("benchmark_goal") != "improvement"
            or not expected_suite_id
            or not _is_inside(definition_path, allowed_root)
            or not definition_path.is_file()
            or str(item.get("definition_sha256", "")).casefold() != _sha256(definition_path).casefold()
            or not _is_inside(manifest_path, allowed_root)
            or not manifest_path.is_file()
            or str(item.get("sha256", "")).casefold() != _sha256(manifest_path).casefold()
        ):
            _add(findings, "BENCHMARK_CURRENT_IMPROVEMENT_LOCK_INVALID", split=split)
            continue
        split_hashes[split] = _check_improvement_definition(
            definition_path, split, expected_suite_id, build_report,
            source_path, source_sha256, findings,
        )
        completed = subprocess.run(
            [sys.executable, str(audit_script), "audit", str(manifest_path), "--format", "json"],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False,
        )
        try:
            report = json.loads(completed.stdout)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _add(findings, "BENCHMARK_CURRENT_IMPROVEMENT_AUDIT_INVALID", split=split)
            continue
        expected_state = str(item.get("state", ""))
        expected_candidates = item.get("candidates")
        definition_lock = manifest.get("suite", {}).get("definition", {})
        if (
            completed.returncode != 0
            or item.get("rule_freshness") != "current-bound"
            or report.get("status") != "pass"
            or report.get("rule_freshness") != "current-bound"
            or report.get("benchmark_goal") != "improvement"
            or report.get("suite_id") != expected_suite_id
            or report.get("state") != expected_state
            or not isinstance(expected_candidates, int)
            or report.get("candidates") != expected_candidates
            or not isinstance(definition_lock, dict)
            or definition_lock.get("sha256") != _sha256(definition_path)
        ):
            _add(
                findings, "BENCHMARK_CURRENT_IMPROVEMENT_STATE_INVALID",
                split=split, registration=item, report=report,
            )
            continue
        states[split] = str(report["state"])
    if split_hashes.get("dev", set()) & split_hashes.get("holdout", set()):
        _add(
            findings, "BENCHMARK_IMPROVEMENT_DEV_HOLDOUT_OVERLAP",
            paragraphs=sorted(split_hashes["dev"] & split_hashes["holdout"]),
        )
    reused = (split_hashes.get("dev", set()) | split_hashes.get("holdout", set())) & excluded_hashes
    if reused:
        _add(
            findings, "BENCHMARK_IMPROVEMENT_EXCLUDED_PARAGRAPH_REUSED",
            paragraphs=sorted(reused),
        )
    return states


def _check_real_draft_holdouts(
    registry_path: Path,
    dev_suite: Path,
    runs_root: Path,
    findings: list[dict],
) -> int:
    registry = _load(registry_path, findings, "real-draft-runs-registry")
    if registry is None:
        return 0
    entries = registry.get("real_draft_holdouts")
    if not isinstance(entries, list) or not entries:
        _add(findings, "BENCHMARK_REAL_DRAFT_HOLDOUTS_MISSING")
        return 0
    audit_script = dev_suite.parents[2] / "scripts" / "attach_legacy_blind_review.py"
    if not audit_script.is_file():
        _add(findings, "BENCHMARK_REAL_DRAFT_AUDITOR_MISSING", path=str(audit_script))
        return 0
    allowed_root = runs_root.parent.resolve()
    seen: set[str] = set()
    passed = 0
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            _add(findings, "BENCHMARK_REAL_DRAFT_ENTRY_INVALID", index=index)
            continue
        entry_id = str(item.get("id", "")).strip()
        if not entry_id or entry_id in seen:
            _add(findings, "BENCHMARK_REAL_DRAFT_ID_INVALID", index=index, entry_id=entry_id)
            continue
        seen.add(entry_id)
        if item.get("kind") != "historical_transport_only" or item.get("current_release_validation") is not False:
            _add(findings, "BENCHMARK_REAL_DRAFT_CLAIM_INVALID", entry_id=entry_id)
            continue
        path = _path(item.get("path", "")).resolve()
        if not _is_inside(path, allowed_root) or not path.is_file():
            _add(findings, "BENCHMARK_REAL_DRAFT_PATH_INVALID", entry_id=entry_id, path=str(path))
            continue
        if str(item.get("sha256", "")).casefold() != _sha256(path).casefold():
            _add(findings, "BENCHMARK_REAL_DRAFT_HASH_DRIFT", entry_id=entry_id)
            continue
        completed = subprocess.run(
            [sys.executable, str(audit_script), "audit", str(path), "--format", "json"],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False,
        )
        if completed.returncode != 0:
            _add(
                findings, "BENCHMARK_REAL_DRAFT_AUDIT_FAILED",
                entry_id=entry_id, returncode=completed.returncode, stderr=completed.stderr[-500:],
            )
            continue
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError:
            _add(findings, "BENCHMARK_REAL_DRAFT_AUDIT_INVALID", entry_id=entry_id)
            continue
        if report.get("status") != "pass" or int(report.get("pairs", 0)) < 1:
            _add(findings, "BENCHMARK_REAL_DRAFT_STATE_INVALID", entry_id=entry_id, report=report)
            continue
        passed += 1
    return passed


def audit(
    dev_suite: Path,
    holdout_suite: Path,
    reservation_path: Path,
    runs_root: Path | None,
    active_registry: Path | None = None,
) -> dict:
    findings: list[dict] = []
    records = _load_index(findings)
    dev_records = _check_suite(dev_suite, "dev", records, findings)
    holdout_records = _check_suite(holdout_suite, "holdout", records, findings)
    dev_ids = {str(record.get("id")) for record in dev_records.values()}
    holdout_ids = {str(record.get("id")) for record in holdout_records.values()}
    if dev_ids & holdout_ids:
        _add(findings, "BENCHMARK_DEV_HOLDOUT_RECORD_OVERLAP", records=sorted(dev_ids & holdout_ids))
    _check_reservation(reservation_path, holdout_records, findings)
    if runs_root is not None:
        _check_frozen_run(dev_suite, dev_records, runs_root, findings)
        _check_frozen_run(holdout_suite, holdout_records, runs_root, findings)
    active_states = (
        _check_active_manifests(active_registry, dev_suite, holdout_suite, runs_root, findings)
        if active_registry is not None and runs_root is not None else {}
    )
    current_rule_states = (
        _check_current_rule_suites(
            active_registry, dev_suite, holdout_suite, runs_root,
            records, reservation_path, findings,
        )
        if active_registry is not None and runs_root is not None else {}
    )
    current_improvement_states = (
        _check_current_improvement_suites(
            active_registry, dev_suite.parents[2], runs_root, findings,
        )
        if active_registry is not None and runs_root is not None else {}
    )
    real_draft_holdouts = (
        _check_real_draft_holdouts(active_registry, dev_suite, runs_root, findings)
        if active_registry is not None and runs_root is not None else 0
    )
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    def quality_status(states: dict[str, str]) -> str:
        values = set(states.values())
        if {"dev", "holdout"}.issubset(states) and values.issubset(
            {"SCORED_DEV", "SCORED_HOLDOUT_SEALED"}
        ):
            return "HUMAN_RESULTS_AVAILABLE"
        if {"dev", "holdout"}.issubset(states) and "BLIND_READY" in values:
            return "HUMAN_RATINGS_PENDING"
        if states:
            return "CURRENT_RULE_EVIDENCE_INCOMPLETE"
        return "CURRENT_RULE_EVIDENCE_INVALID"

    preservation_quality_status = quality_status(current_rule_states)
    improvement_quality_status = quality_status(current_improvement_states)
    if "CURRENT_RULE_EVIDENCE_INVALID" in {
        preservation_quality_status, improvement_quality_status,
    }:
        human_quality_status = "CURRENT_RULE_EVIDENCE_INVALID"
    elif "CURRENT_RULE_EVIDENCE_INCOMPLETE" in {
        preservation_quality_status, improvement_quality_status,
    }:
        human_quality_status = "CURRENT_RULE_EVIDENCE_INCOMPLETE"
    elif "HUMAN_RATINGS_PENDING" in {
        preservation_quality_status, improvement_quality_status,
    }:
        human_quality_status = "HUMAN_RATINGS_PENDING"
    else:
        human_quality_status = "HUMAN_RESULTS_AVAILABLE"
    return {
        "schema": "cumcm-style-benchmark-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "warnings": warnings,
        "dev_cases": len(dev_records),
        "holdout_cases": len(holdout_records),
        "runs_root": str(runs_root.resolve()) if runs_root is not None else None,
        "active_states": active_states,
        "current_rule_states": current_rule_states,
        "current_improvement_states": current_improvement_states,
        "preservation_human_quality_status": preservation_quality_status,
        "improvement_human_quality_status": improvement_quality_status,
        "human_quality_status": human_quality_status,
        "real_draft_holdouts": real_draft_holdouts,
        "runs_root": str(runs_root.resolve()) if runs_root is not None else None,
        "findings": findings,
        "interpretation": (
            "The audit verifies corpus provenance, A/B/C coverage, retrieval isolation, frozen-file integrity, "
            "registered real-draft review transport, current-rule preservation suites, and current-rule "
            "real-draft improvement suites with source, sampler, exclusion, and paragraph locks. "
            "Historical addenda and legacy manifests without that snapshot remain explicitly non-current releases. "
            "It does not evaluate style quality, authorship, detector outcomes, or mathematical correctness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router-root", type=Path, default=DEFAULT_ROUTER_ROOT)
    parser.add_argument("--reservation", type=Path, default=RESERVATION_PATH)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument("--runs-registry", type=Path, default=DEFAULT_RUNS_REGISTRY)
    parser.add_argument("--no-run-check", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    router_root = args.router_root.resolve()
    report = audit(
        router_root / "references" / "benchmarks" / "cumcm-v1-dev.json",
        router_root / "references" / "benchmarks" / "cumcm-v1-holdout.json",
        args.reservation.resolve(),
        None if args.no_run_check else resolve_runs_root(args.runs_root, args.runs_registry.resolve()),
        None if args.no_run_check else args.runs_registry.resolve(),
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"CUMCM STYLE BENCHMARK transport={report['status'].upper()} "
            f"human_quality={report['human_quality_status']} "
            f"dev={report['dev_cases']} holdout={report['holdout_cases']} "
            f"errors={report['errors']} warnings={report['warnings']}"
        )
        for finding in report["findings"]:
            details = ", ".join(
                f"{key}={value}" for key, value in finding.items()
                if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {details}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
