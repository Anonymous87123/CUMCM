#!/usr/bin/env python3
"""Run the installed academic-humanization checks as one release gate.

Public interface:
    python audit_academic_candidate.py <source.tex> <candidate.tex>
        [--scene MODELING] [--decisions decisions.json]
        [--humanize-run RUN_DIR] [--packet-index packet-index.json]
        [--require-style-gain] --format text|json

The gate does not infer authorship or promise naturalness.  It proves that the
published lexical scanner and the protected-rewrite, voice, rhythm, and
relative-revision checks were actually executed against one frozen candidate.

Exit codes: 0=PASS, 2=REVIEW, 1=FAIL/input error.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = Path(__file__).resolve().parents[3]
HUMANIZE_ROOT = SKILLS_ROOT / "AIGC" / "humanize-academic-chinese"
MCM_ROOT = SKILLS_ROOT / "mcm-cup-standard-write"

LEXICAL_SCANNER = HUMANIZE_ROOT / "scripts" / "scan_humanize_chinese.py"
HUMANIZE_INLINE_RUNNER = HUMANIZE_ROOT / "scripts" / "run_humanize_inline.py"
LEXICAL_SIGNALS = HUMANIZE_ROOT / "references" / "lexical-signals.json"
REWRITE_CONTRACT = MCM_ROOT / "scripts" / "audit_rewrite_contract.py"
VOICE_AUDIT = SCRIPT_DIR / "audit_voice_mode.py"
RHYTHM_AUDIT = SCRIPT_DIR / "audit_style_rhythm.py"
REASONING_SCAFFOLD_AUDIT = SCRIPT_DIR / "audit_reasoning_scaffold.py"
STYLE_COMPARISON = SCRIPT_DIR / "compare_style_revision.py"
MCM_LEXICAL_CALIBRATION = MCM_ROOT / "scripts" / "audit_lexical_corpus_calibration.py"
MCM_FULLTEXT_INDEX = MCM_ROOT / "references" / "fulltext-style-index.jsonl"
MCM_JUDGMENT_BRIDGE_AUDIT = MCM_ROOT / "scripts" / "audit_section_judgment_bridges.py"

INCLUDE_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
DECISION_SCHEMA = "aigc-academic-style-decisions/v1"
REPORT_SCHEMA = "aigc-academic-candidate-audit/v1"
JUDGMENT_GAIN_CODES = {
    "SECTION_BRIDGE_BASIS_MISSING",
    "SECTION_BRIDGE_MATHEMATICAL_CHANGE_MISSING",
    "SECTION_BRIDGE_SELECTED_ROUTE_MISSING",
    "SECTION_BRIDGE_ORDER_INVALID",
    "SECTION_BRIDGE_UNRECORDED_COMPARISON_CLAIM",
    "SECTION_BRIDGE_ALTERNATIVE_NOT_NAMED",
    "SECTION_BRIDGE_ANALYSIS_HAS_NO_LOCAL_BRIDGE",
    "SECTION_BRIDGE_RESULT_OBSERVATION_MISSING",
    "SECTION_BRIDGE_RESULT_EXPLANATION_MISSING",
    "SECTION_BRIDGE_RESULT_LINK_MISSING",
    "SECTION_BRIDGE_CHECK_TERM_MISSING",
    "SECTION_BRIDGE_CHECK_CONCLUSION_MISSING",
    "SECTION_BRIDGE_CHECK_LINK_MISSING",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strip_tex_comments(text: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        cutoff = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            slash_count = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                slash_count += 1
                cursor -= 1
            if slash_count % 2 == 0:
                cutoff = index
                break
        output.append(line[:cutoff])
    return "\n".join(output)


def discover_tex_tree(main_tex: Path) -> list[Path]:
    pending = [main_tex.resolve()]
    discovered: list[Path] = []
    seen: set[Path] = set()
    while pending:
        path = pending.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        discovered.append(path)
        text = _strip_tex_comments(path.read_text(encoding="utf-8-sig"))
        for raw in INCLUDE_RE.findall(text):
            candidate = (path.parent / raw.strip()).resolve()
            if not candidate.is_file() and not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            if candidate not in seen:
                pending.append(candidate)
    return discovered


def tree_sha256(main_tex: Path, files: list[Path]) -> str:
    root = main_tex.resolve().parent
    rows = [f"{path.relative_to(root)}\0{sha256_file(path)}" for path in files]
    return hashlib.sha256("\n".join(sorted(rows)).encode("utf-8")).hexdigest()


def _dependency(path: Path, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "role": role,
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _run_json(tool: Path, arguments: list[str], accepted: set[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    command = [str(Path(sys.executable).resolve()), str(tool.resolve()), *arguments]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=300,
        check=False,
    )
    execution = {
        "command": command,
        "returncode": completed.returncode,
        "stderr": completed.stderr[-2000:],
    }
    if completed.returncode not in accepted:
        raise RuntimeError(
            f"{tool.name} exited {completed.returncode}: {completed.stderr[-600:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{tool.name} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{tool.name} JSON root must be an object")
    return payload, execution


def _combined_tex(files: list[Path], destination: Path, root: Path) -> list[dict[str, Any]]:
    parts = []
    line_maps: list[dict[str, Any]] = []
    newline_count = 0
    for path in files:
        boundary = f"% AIGC_AUDIT_FILE_BOUNDARY: {path.name}\n"
        parts.append(boundary)
        newline_count += boundary.count("\n")
        text = path.read_text(encoding="utf-8-sig")
        content_lines = len(text.splitlines())
        if content_lines:
            line_maps.append({
                "path": str(path.resolve()),
                "relative_path": _relative(str(path), root),
                "combined_start_line": newline_count + 1,
                "combined_end_line": newline_count + content_lines,
            })
        parts.append(text)
        newline_count += text.count("\n")
        parts.append("\n")
        newline_count += 1
    destination.write_text("".join(parts), encoding="utf-8", newline="")
    return line_maps


def _attach_combined_locations(
    findings: list[dict[str, Any]], line_maps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in findings:
        item = dict(raw)
        try:
            line = int(item.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        record = next(
            (
                value for value in line_maps
                if value["combined_start_line"] <= line <= value["combined_end_line"]
            ),
            None,
        )
        if record is not None:
            item["combined_line"] = line
            item["relative_path"] = record["relative_path"]
            item["actual_line"] = line - record["combined_start_line"] + 1
        output.append(item)
    return output


def _relative(path_value: str, root: Path) -> str:
    path = Path(path_value).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _finding_key(item: dict[str, Any], root: Path) -> tuple[Any, ...]:
    return (
        str(item.get("signal_id", "")),
        _relative(str(item.get("file", "")), root),
        int(item.get("line", 0)),
        int(item.get("column", 0)),
        str(item.get("matched", "")),
    )


def _load_decisions(
    path: Path | None,
    candidate_hash: str,
    source_hash: str,
) -> tuple[
    dict[tuple[Any, ...], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    if path is None:
        return {}, {}, [], []
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    lexical_errors: list[dict[str, Any]] = []
    semantic_errors: list[dict[str, Any]] = []
    if payload.get("schema") != DECISION_SCHEMA:
        lexical_errors.append({"code": "DECISION_SCHEMA_MISMATCH"})
    if payload.get("candidate_tree_sha256") != candidate_hash:
        lexical_errors.append({"code": "DECISION_CANDIDATE_HASH_MISMATCH"})
    records: dict[tuple[Any, ...], dict[str, Any]] = {}
    for index, item in enumerate(payload.get("decisions", []), start=1):
        if not isinstance(item, dict):
            lexical_errors.append({"code": "DECISION_INVALID", "index": index})
            continue
        key = (
            str(item.get("signal_id", "")),
            str(item.get("relative_path", "")),
            int(item.get("line", 0)),
            int(item.get("column", 0)),
            str(item.get("matched", "")),
        )
        reason = str(item.get("reason", "")).strip()
        reviewer = str(item.get("reviewer", "")).strip()
        reviewer_kind = str(item.get("reviewer_kind", "")).strip().lower()
        if reviewer_kind != "human":
            lexical_errors.append({"code": "DECISION_REQUIRES_HUMAN_REVIEW", "index": index})
            continue
        if item.get("decision") != "keep" or len(reason) < 12 or not reviewer or not all(key):
            lexical_errors.append({"code": "DECISION_NOT_POSITION_BOUND", "index": index})
            continue
        if key in records:
            lexical_errors.append({"code": "DECISION_DUPLICATE", "index": index})
            continue
        records[key] = item

    semantic_records: dict[tuple[str, str], dict[str, Any]] = {}
    semantic_items = payload.get("semantic_decisions", [])
    if semantic_items and payload.get("source_tree_sha256") != source_hash:
        semantic_errors.append({"code": "SEMANTIC_DECISION_SOURCE_HASH_MISMATCH"})
    if semantic_items and payload.get("candidate_tree_sha256") != candidate_hash:
        semantic_errors.append({"code": "SEMANTIC_DECISION_CANDIDATE_HASH_MISMATCH"})
    for index, item in enumerate(semantic_items, start=1):
        if not isinstance(item, dict):
            semantic_errors.append({"code": "SEMANTIC_DECISION_INVALID", "index": index})
            continue
        code = str(item.get("code", ""))
        fingerprint = str(item.get("finding_sha256", ""))
        key = (code, fingerprint)
        reason = str(item.get("reason", "")).strip()
        reviewer = str(item.get("reviewer", "")).strip()
        reviewer_kind = str(item.get("reviewer_kind", "")).strip().lower()
        if reviewer_kind != "human":
            semantic_errors.append({"code": "SEMANTIC_DECISION_REQUIRES_HUMAN_REVIEW", "index": index})
            continue
        if (
            item.get("decision") != "accept"
            or len(reason) < 12
            or not reviewer
            or not code
            or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
        ):
            semantic_errors.append({"code": "SEMANTIC_DECISION_NOT_EVIDENCE_BOUND", "index": index})
            continue
        if key in semantic_records:
            semantic_errors.append({"code": "SEMANTIC_DECISION_DUPLICATE", "index": index})
            continue
        semantic_records[key] = item
    return records, semantic_records, lexical_errors, semantic_errors


def _expanded_lexical_pairs(item: dict[str, Any]) -> set[tuple[str, str]]:
    signal_ids = item.get("merged_signal_ids")
    if not isinstance(signal_ids, list):
        signal_ids = [item.get("signal_id")]
    matches = item.get("merged_matches")
    if not isinstance(matches, list):
        matches = [item.get("matched")]
    return {
        (str(signal_id), str(matched))
        for signal_id in signal_ids
        for matched in matches
        if str(signal_id) and str(matched)
    }


def _audit_humanize_run_keep_evidence(
    run_path: Path | None,
    source: Path,
    candidate: Path,
    source_tree: list[Path],
    candidate_tree: list[Path],
    source_actionable: list[dict[str, Any]],
    candidate_actionable: list[dict[str, Any]],
    scene: str,
) -> tuple[set[tuple[Any, ...]], dict[str, Any]]:
    """Replay one Humanize run and import only source-inherited lexical KEEP records."""
    if run_path is None:
        return set(), {
            "status": "not-provided",
            "path": None,
            "accepted_findings": 0,
            "used_findings": 0,
            "errors": [],
        }

    errors: list[dict[str, Any]] = []
    run_path = run_path.resolve()
    run_dir = run_path if run_path.is_dir() else run_path.parent
    run_json = run_dir / "run.json" if run_path.is_dir() else run_path
    validation_path = run_dir / "validation.json"
    if len(source_tree) != 1 or len(candidate_tree) != 1:
        errors.append({"code": "HUMANIZE_KEEP_SINGLE_FILE_ONLY"})
    if not run_json.is_file():
        errors.append({"code": "HUMANIZE_RUN_JSON_MISSING", "path": str(run_json)})
    if not validation_path.is_file():
        errors.append({"code": "HUMANIZE_VALIDATION_MISSING", "path": str(validation_path)})
    if errors:
        return set(), {
            "status": "review", "path": str(run_dir),
            "accepted_findings": 0, "used_findings": 0, "errors": errors,
        }

    try:
        run = json.loads(run_json.read_text(encoding="utf-8-sig"))
        validation = json.loads(validation_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), {
            "status": "review", "path": str(run_dir),
            "accepted_findings": 0, "used_findings": 0,
            "errors": [{"code": "HUMANIZE_RUN_UNREADABLE", "detail": str(exc)}],
        }
    if not isinstance(run, dict) or not isinstance(validation, dict):
        return set(), {
            "status": "review", "path": str(run_dir),
            "accepted_findings": 0, "used_findings": 0,
            "errors": [{"code": "HUMANIZE_RUN_ROOT_INVALID"}],
        }

    if run.get("schema_version") != "humanize-inline-run/v3":
        errors.append({"code": "HUMANIZE_RUN_SCHEMA_UNSUPPORTED", "actual": run.get("schema_version")})
    if run.get("mode") != "REWRITE" or run.get("scene") != scene:
        errors.append({
            "code": "HUMANIZE_RUN_CONTEXT_MISMATCH",
            "mode": run.get("mode"), "scene": run.get("scene"),
        })
    if run.get("mechanical_validation_status") != "PASS" or run.get("body_emission_allowed") is not True:
        errors.append({"code": "HUMANIZE_RUN_NOT_MECHANICALLY_RELEASABLE"})
    if validation.get("mechanical_validation_status") != "PASS":
        errors.append({"code": "HUMANIZE_VALIDATION_NOT_PASS"})

    source_sha = sha256_file(source)
    candidate_sha = sha256_file(candidate)
    artifacts = run.get("artifacts", {}) if isinstance(run.get("artifacts"), dict) else {}
    before_lock = artifacts.get("before", {}) if isinstance(artifacts.get("before"), dict) else {}
    after_lock = artifacts.get("after", {}) if isinstance(artifacts.get("after"), dict) else {}
    validation_lock = artifacts.get("validation", {}) if isinstance(artifacts.get("validation"), dict) else {}
    evidence = validation.get("evidence", {}) if isinstance(validation.get("evidence"), dict) else {}
    if before_lock.get("sha256") != source_sha or evidence.get("before_sha256") != source_sha:
        errors.append({"code": "HUMANIZE_RUN_SOURCE_HASH_MISMATCH"})
    if after_lock.get("sha256") != candidate_sha or evidence.get("after_sha256") != candidate_sha:
        errors.append({"code": "HUMANIZE_RUN_CANDIDATE_HASH_MISMATCH"})
    if validation_lock.get("sha256") != sha256_file(validation_path):
        errors.append({"code": "HUMANIZE_RUN_VALIDATION_HASH_MISMATCH"})

    policy_hashes = evidence.get("policy_hashes", {}) if isinstance(evidence.get("policy_hashes"), dict) else {}
    if policy_hashes.get("scanner_sha256") != sha256_file(LEXICAL_SCANNER):
        errors.append({"code": "HUMANIZE_RUN_SCANNER_DRIFT"})
    if policy_hashes.get("lexicon_sha256") != sha256_file(LEXICAL_SIGNALS):
        errors.append({"code": "HUMANIZE_RUN_LEXICON_DRIFT"})

    replay: dict[str, Any] | None = None
    replay_execution: dict[str, Any] | None = None
    try:
        replay, replay_execution = _run_json(
            HUMANIZE_INLINE_RUNNER,
            ["emit", str(run_dir), "--format", "json"],
            {0, 2},
        )
    except RuntimeError as exc:
        errors.append({"code": "HUMANIZE_RUN_REPLAY_FAILED", "detail": str(exc)})
    if replay is not None and (
        replay.get("status") != "PASS"
        or replay.get("mechanical_validation_status") != "PASS"
        or replay.get("body_emission_allowed") is not True
        or replay.get("after_sha256") != candidate_sha
    ):
        errors.append({"code": "HUMANIZE_RUN_REPLAY_MISMATCH"})

    source_counts: Counter[tuple[str, str]] = Counter()
    for item in source_actionable:
        source_counts.update(_expanded_lexical_pairs(item))
    current_by_marker: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for item in candidate_actionable:
        line = int(item.get("line", 0))
        column = int(item.get("column", 0))
        for signal_id, matched in _expanded_lexical_pairs(item):
            current_by_marker[(signal_id, matched, line, column)] = item

    accepted_records = [
        item for item in validation.get("accepted_findings", [])
        if isinstance(item, dict) and str(item.get("signal_id", "")).startswith("LEX-STRICT-CORPUS-")
    ]
    accepted_pair_counts: Counter[tuple[str, str]] = Counter()
    accepted_keys: set[tuple[Any, ...]] = set()
    used_records: list[dict[str, Any]] = []
    for index, item in enumerate(accepted_records, start=1):
        signal_id = str(item.get("signal_id", ""))
        matched = str(item.get("matched", ""))
        line = int(item.get("line", 0))
        column = int(item.get("column", 0))
        binding = str(item.get("binding", ""))
        reason = str(item.get("reason", "")).strip()
        marker = (signal_id, matched, line, column)
        current = current_by_marker.get(marker)
        if (
            item.get("file") != "after"
            or binding != f"{signal_id}@{line}:{column}"
            or len(reason) < 12
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("finding_hash", "")))
            or current is None
        ):
            errors.append({"code": "HUMANIZE_KEEP_RECORD_INVALID", "index": index})
            continue
        pair = (signal_id, matched)
        accepted_pair_counts[pair] += 1
        accepted_keys.add(_finding_key(current, candidate.parent))
        used_records.append({
            "signal_id": signal_id, "matched": matched,
            "line": line, "column": column,
            "finding_hash": item.get("finding_hash"), "reason": reason,
        })
    for pair, count in accepted_pair_counts.items():
        if source_counts[pair] < count:
            errors.append({
                "code": "HUMANIZE_KEEP_NOT_SOURCE_INHERITED",
                "signal_id": pair[0], "matched": pair[1],
                "source_count": source_counts[pair], "accepted_count": count,
            })
            accepted_keys = {
                key for key in accepted_keys
                if not (key[0] == pair[0] and key[4] == pair[1])
            }
    if errors:
        accepted_keys.clear()
    return accepted_keys, {
        "status": "pass" if not errors else "review",
        "path": str(run_dir),
        "run_id": run.get("run_id"),
        "run_json": {"path": str(run_json), "sha256": sha256_file(run_json)},
        "validation": {"path": str(validation_path), "sha256": sha256_file(validation_path)},
        "replay": replay_execution,
        "accepted_findings": len(accepted_records),
        "used_findings": len(used_records) if not errors else 0,
        "records": used_records,
        "source_inheritance_policy": (
            "a replayed KEEP may clear only the same strict phrase already present in the frozen source; "
            "it never clears semantic warnings or hard invariants"
        ),
        "errors": errors,
    }


def build_recovery(gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the only safe next editing surface for a failed candidate."""
    by_id = {str(item.get("id")): item for item in gates}
    contract = by_id.get("protected-rewrite-contract", {})
    required_blockers = [
        str(item.get("id"))
        for item in gates
        if item.get("required") and item.get("status") != "pass"
    ]
    contract_codes = [
        str(item.get("code"))
        for item in contract.get("findings", [])
        if isinstance(item, dict) and item.get("severity") == "error"
    ]
    if contract.get("status") == "fail":
        return {
            "route": "REBASE_FROM_FROZEN_SOURCE",
            "current_candidate_repair_allowed": False,
            "source_rebase_required": True,
            "lexical_findings_actionable_now": False,
            "blocking_gate_ids": required_blockers,
            "reason_codes": contract_codes,
            "next_action": (
                "Discard this file as a release candidate. Start one protected Humanize "
                "run from the frozen source; do not repair lexical findings on the drifted file."
            ),
        }
    if contract.get("status") == "review":
        return {
            "route": "SEMANTIC_REVIEW_ON_CURRENT_CANDIDATE",
            "current_candidate_repair_allowed": True,
            "source_rebase_required": False,
            "lexical_findings_actionable_now": True,
            "blocking_gate_ids": required_blockers,
            "reason_codes": [
                str(item.get("code"))
                for item in contract.get("findings", [])
                if isinstance(item, dict) and item.get("severity") == "warning"
            ],
            "next_action": (
                "Resolve every semantic warning against the frozen source, then perform "
                "position-bound local repairs on the current candidate."
            ),
        }
    if required_blockers:
        return {
            "route": "LOCAL_REPAIR_ON_CURRENT_CANDIDATE",
            "current_candidate_repair_allowed": True,
            "source_rebase_required": False,
            "lexical_findings_actionable_now": True,
            "blocking_gate_ids": required_blockers,
            "reason_codes": [],
            "next_action": (
                "Repair only the reported local prose spans against their source facts; "
                "do not run a second Humanizer over the candidate."
            ),
        }
    return {
        "route": "READY_FOR_HUMAN_REVIEW",
        "current_candidate_repair_allowed": False,
        "source_rebase_required": False,
        "lexical_findings_actionable_now": False,
        "blocking_gate_ids": [],
        "reason_codes": [],
        "next_action": "Freeze the candidate and continue to source-hidden human review.",
    }


def audit(
    source: Path,
    candidate: Path,
    scene: str = "MODELING",
    decisions_path: Path | None = None,
    humanize_run_path: Path | None = None,
    require_style_gain: bool = False,
    packet_index_path: Path | None = None,
) -> dict[str, Any]:
    source = source.resolve()
    candidate = candidate.resolve()
    if not source.is_file() or not candidate.is_file():
        raise FileNotFoundError(source if not source.is_file() else candidate)

    source_tree = discover_tex_tree(source)
    candidate_tree = discover_tex_tree(candidate)
    source_hash = tree_sha256(source, source_tree)
    candidate_hash = tree_sha256(candidate, candidate_tree)
    decisions, semantic_decisions, decision_errors, semantic_decision_errors = _load_decisions(
        decisions_path, candidate_hash, source_hash
    )

    dependencies = [
        _dependency(LEXICAL_SCANNER, "humanize-lexical-scanner"),
        _dependency(HUMANIZE_INLINE_RUNNER, "humanize-inline-run-replayer"),
        _dependency(LEXICAL_SIGNALS, "humanize-lexical-signals"),
        _dependency(REWRITE_CONTRACT, "protected-rewrite-contract"),
        _dependency(VOICE_AUDIT, "section-voice-audit"),
        _dependency(RHYTHM_AUDIT, "paragraph-rhythm-audit"),
        _dependency(REASONING_SCAFFOLD_AUDIT, "public-reasoning-scaffold-audit"),
        _dependency(STYLE_COMPARISON, "relative-style-comparison"),
        _dependency(MCM_LEXICAL_CALIBRATION, "mcm-human-lexical-calibration"),
        _dependency(MCM_FULLTEXT_INDEX, "mcm-verified-human-corpus"),
    ]
    if packet_index_path is not None:
        packet_index_path = packet_index_path.resolve()
        if not packet_index_path.is_file():
            raise FileNotFoundError(packet_index_path)
        dependencies.append(
            _dependency(MCM_JUDGMENT_BRIDGE_AUDIT, "source-bound-judgment-bridge-audit")
        )

    lexical, lexical_execution = _run_json(
        LEXICAL_SCANNER,
        [*(str(path) for path in candidate_tree), "--scene", scene, "--format", "json"],
        {0, 2},
    )
    source_lexical = None
    source_lexical_execution = None
    if humanize_run_path is not None:
        source_lexical, source_lexical_execution = _run_json(
            LEXICAL_SCANNER,
            [*(str(path) for path in source_tree), "--scene", scene, "--format", "json"],
            {0, 2},
        )
    calibration = None
    calibration_execution = None
    contextual_human_attested: list[dict[str, Any]] = []
    calibrated_phrases: dict[str, dict[str, Any]] = {}
    if scene == "MODELING":
        calibration, calibration_execution = _run_json(
            MCM_LEXICAL_CALIBRATION, ["--format", "json"], {0}
        )
        calibrated_phrases = {
            str(item.get("phrase")): item
            for item in calibration.get("phrases", [])
            if isinstance(item, dict) and item.get("disposition") == "contextual-human-attested"
        }
    raw_actionable = [
        item for item in lexical.get("findings", [])
        if item.get("candidate") and not item.get("protected") and not item.get("excluded")
    ]
    source_raw_actionable = [
        item for item in (source_lexical or {}).get("findings", [])
        if item.get("candidate") and not item.get("protected") and not item.get("excluded")
    ]
    actionable = []
    for item in raw_actionable:
        signal_ids = item.get("merged_signal_ids")
        if not isinstance(signal_ids, list):
            signal_ids = [item.get("signal_id")]
        only_strict = all(str(signal_id).startswith("LEX-STRICT-CORPUS-") for signal_id in signal_ids)
        matches = item.get("merged_matches")
        if not isinstance(matches, list):
            matches = [item.get("matched")]
        attested = [calibrated_phrases[str(value)] for value in matches if str(value) in calibrated_phrases]
        if scene == "MODELING" and only_strict and attested:
            contextual_human_attested.append({
                **item,
                "candidate": False,
                "action": "REVIEW_CONTEXT",
                "severity": "medium",
                "calibration": attested,
                "rationale": (
                    "This phrase is attested across at least five verified CUMCM papers. "
                    "A single lexical hit is not a hard blocker; repetition and paragraph function remain reviewable."
                ),
            })
        else:
            actionable.append(item)
    humanize_keep_keys, humanize_keep_evidence = _audit_humanize_run_keep_evidence(
        humanize_run_path,
        source,
        candidate,
        source_tree,
        candidate_tree,
        source_raw_actionable,
        raw_actionable,
        scene,
    )
    unresolved: list[dict[str, Any]] = []
    used_decisions: set[tuple[Any, ...]] = set()
    used_humanize_keep: set[tuple[Any, ...]] = set()
    for item in contextual_human_attested:
        key = _finding_key(item, candidate.parent)
        if key in decisions:
            used_decisions.add(key)
    for item in actionable:
        key = _finding_key(item, candidate.parent)
        if key in humanize_keep_keys:
            used_humanize_keep.add(key)
            continue
        if key in decisions:
            used_decisions.add(key)
            continue
        unresolved.append({
            "signal_id": item.get("signal_id"),
            "relative_path": key[1],
            "line": item.get("line"),
            "column": item.get("column"),
            "matched": item.get("matched"),
            "severity": item.get("severity"),
            "action": item.get("action"),
            "rationale": item.get("rationale"),
        })
    unused_decisions = [
        {
            "signal_id": key[0], "relative_path": key[1], "line": key[2],
            "column": key[3], "matched": key[4],
        }
        for key in decisions if key not in used_decisions
    ]
    coverage_status = str(lexical.get("coverage", {}).get("status", "")).upper()
    lexical_status = (
        "pass" if coverage_status == "PASS" and not unresolved
        and not decision_errors and not unused_decisions
        and humanize_keep_evidence.get("status") in {"pass", "not-provided"} else "review"
    )
    lexical_gate = {
        "id": "humanize-lexical",
        "required": True,
        "status": lexical_status,
        "execution": lexical_execution,
        "source_execution": source_lexical_execution,
        "coverage": lexical.get("coverage"),
        "actionable_findings": len(actionable),
        "kept_by_position_bound_decision": len(used_decisions),
        "kept_by_replayed_humanize_run": len(used_humanize_keep),
        "unresolved_findings": len(unresolved),
        "signal_counts": dict(sorted(Counter(str(item.get("signal_id")) for item in actionable).items())),
        "unresolved": unresolved[:100],
        "human_corpus_calibration": {
            "status": calibration.get("status") if calibration else "not-applicable",
            "execution": calibration_execution,
            "papers": calibration.get("papers") if calibration else None,
            "contextual_phrase_inventory": len(calibrated_phrases),
            "contextual_findings": len(contextual_human_attested),
            "findings": contextual_human_attested[:100],
            "policy": (
                "human-attested strict phrases remain visible but do not hard-block a modeling candidate "
                "on one lexical occurrence alone"
            ),
        },
        "decision_errors": decision_errors,
        "unused_decisions": unused_decisions,
        "humanize_run_keep_evidence": humanize_keep_evidence,
    }

    contract, contract_execution = _run_json(
        REWRITE_CONTRACT,
        [str(source), str(candidate), "--scene", scene, "--format", "json"],
        {0, 1},
    )
    warning_findings = [
        item for item in contract.get("findings", [])
        if isinstance(item, dict) and item.get("severity") == "warning"
    ]
    error_findings = [
        item for item in contract.get("findings", [])
        if isinstance(item, dict) and item.get("severity") == "error"
    ]
    used_semantic: set[tuple[str, str]] = set()
    unresolved_warnings: list[dict[str, Any]] = []
    adjudicated_warnings: list[dict[str, Any]] = []
    for item in warning_findings:
        key = (str(item.get("code", "")), str(item.get("finding_sha256", "")))
        if key in semantic_decisions:
            used_semantic.add(key)
            adjudicated_warnings.append({"code": key[0], "finding_sha256": key[1]})
        else:
            unresolved_warnings.append(item)
    unused_semantic = [
        {"code": key[0], "finding_sha256": key[1]}
        for key in semantic_decisions if key not in used_semantic
    ]
    error_codes = {str(item.get("code", "")) for item in error_findings}
    for item in unused_semantic:
        if item["code"] in error_codes:
            semantic_decision_errors.append({
                "code": "SEMANTIC_DECISION_TARGET_NOT_WARNING",
                "target_code": item["code"],
                "finding_sha256": item["finding_sha256"],
            })
    contract_status = "pass"
    if contract.get("status") != "pass":
        contract_status = "fail"
    elif unresolved_warnings or semantic_decision_errors or unused_semantic:
        contract_status = "review"
    contract_gate = {
        "id": "protected-rewrite-contract",
        "required": True,
        "status": contract_status,
        "execution": contract_execution,
        "errors": contract.get("errors"),
        "warnings": contract.get("warnings"),
        "findings": contract.get("findings", []),
        "adjudicated_warnings": adjudicated_warnings,
        "unresolved_warnings": unresolved_warnings,
        "semantic_decision_errors": semantic_decision_errors,
        "unused_semantic_decisions": unused_semantic,
        "number_diff": contract.get("number_diff", {}),
    }

    with tempfile.TemporaryDirectory(prefix="aigc-academic-candidate-") as temp:
        temp_root = Path(temp)
        source_combined = temp_root / "source-combined.tex"
        candidate_combined = temp_root / "candidate-combined.tex"
        _combined_tex(source_tree, source_combined, source.parent)
        candidate_line_maps = _combined_tex(candidate_tree, candidate_combined, candidate.parent)

        voice, voice_execution = _run_json(
            VOICE_AUDIT, [str(candidate_combined), "--format", "json"], {0, 2}
        )
        rhythm, rhythm_execution = _run_json(
            RHYTHM_AUDIT,
            [str(candidate_combined), "--mode", "auto", "--format", "json"],
            {0, 2},
        )
        scaffold, scaffold_execution = _run_json(
            REASONING_SCAFFOLD_AUDIT,
            [str(candidate_combined), "--mode", "auto", "--format", "json"],
            {0, 2},
        )
        comparison, comparison_execution = _run_json(
            STYLE_COMPARISON,
            [str(source_combined), str(candidate_combined), "--format", "json"],
            {0, 2},
        )

    source_bridge = None
    source_bridge_execution = None
    candidate_bridge = None
    candidate_bridge_execution = None
    judgment_improvements: list[dict[str, Any]] = []
    judgment_bridge_gate = None
    if packet_index_path is not None:
        source_bridge, source_bridge_execution = _run_json(
            MCM_JUDGMENT_BRIDGE_AUDIT,
            [str(source), "--packet-index", str(packet_index_path), "--format", "json"],
            {0, 1},
        )
        candidate_bridge, candidate_bridge_execution = _run_json(
            MCM_JUDGMENT_BRIDGE_AUDIT,
            [str(candidate), "--packet-index", str(packet_index_path), "--format", "json"],
            {0, 1},
        )
        source_counts = Counter(
            str(item.get("code"))
            for item in source_bridge.get("findings", [])
            if isinstance(item, dict) and item.get("code") in JUDGMENT_GAIN_CODES
        )
        candidate_counts = Counter(
            str(item.get("code"))
            for item in candidate_bridge.get("findings", [])
            if isinstance(item, dict) and item.get("code") in JUDGMENT_GAIN_CODES
        )
        if candidate_bridge.get("status") == "pass":
            judgment_improvements = [
                {
                    "metric": "source_bound_judgment_bridge",
                    "code": code,
                    "source": count,
                    "candidate": candidate_counts.get(code, 0),
                    "delta": candidate_counts.get(code, 0) - count,
                }
                for code, count in sorted(source_counts.items())
                if candidate_counts.get(code, 0) < count
            ]
        judgment_bridge_gate = {
            "id": "source-bound-judgment-bridge",
            "required": True,
            "status": "pass" if candidate_bridge.get("status") == "pass" else "fail",
            "packet_index": {
                "path": str(packet_index_path),
                "sha256": sha256_file(packet_index_path),
            },
            "source_execution": source_bridge_execution,
            "candidate_execution": candidate_bridge_execution,
            "source_status": source_bridge.get("status"),
            "candidate_status": candidate_bridge.get("status"),
            "source_findings": source_bridge.get("findings", []),
            "candidate_findings": candidate_bridge.get("findings", []),
            "improvements": judgment_improvements,
            "interpretation": (
                "A gain is counted only when the frozen source fails a recorded section-local "
                "judgment requirement and the candidate passes the same packet-bound audit."
            ),
        }

    voice_findings = _attach_combined_locations(list(voice.get("findings", [])), candidate_line_maps)
    rhythm_findings = _attach_combined_locations(list(rhythm.get("findings", [])), candidate_line_maps)
    voice_gate = {
        "id": "section-voice",
        "required": True,
        "status": "pass" if voice.get("status") == "pass" else "review",
        "execution": voice_execution,
        "summary": voice.get("summary", {}),
        "findings": voice_findings,
        "candidate_file_map": candidate_line_maps,
    }
    rhythm_gate = {
        "id": "paragraph-rhythm",
        "required": True,
        "status": "pass" if rhythm.get("status") == "pass" else "review",
        "execution": rhythm_execution,
        "summary": rhythm.get("summary", {}),
        "findings": rhythm_findings,
        "candidate_file_map": candidate_line_maps,
    }
    scaffold_findings = _attach_combined_locations(
        list(scaffold.get("findings", [])), candidate_line_maps
    )
    scaffold_gate = {
        "id": "public-reasoning-scaffold",
        "required": True,
        "status": "pass" if scaffold.get("status") == "pass" else "review",
        "execution": scaffold_execution,
        "summary": scaffold.get("summary", {}),
        "findings": scaffold_findings,
        "candidate_file_map": candidate_line_maps,
    }
    comparison_gate = {
        "id": "relative-style-comparison",
        "required": False,
        "status": comparison.get("status", "review"),
        "execution": comparison_execution,
        "same_bytes": comparison.get("same_bytes"),
        "improvements": comparison.get("improvements", []),
        "regressions": comparison.get("regressions", []),
    }
    style_gain_gate = {
        "id": "style-gain",
        "required": bool(require_style_gain),
        "status": "pass",
        "reason": "style-gain requirement disabled",
        "same_bytes": comparison.get("same_bytes"),
        "improvements": comparison.get("improvements", []),
        "source_bound_improvements": judgment_improvements,
        "regressions": comparison.get("regressions", []),
    }
    if require_style_gain:
        if comparison.get("regressions"):
            style_gain_gate.update({
                "status": "fail",
                "reason": "relative comparison found structural regressions",
            })
        elif (
            comparison.get("status") == "improved" and comparison.get("improvements")
        ) or judgment_improvements:
            style_gain_gate.update({
                "status": "pass",
                "reason": (
                    "at least one relative structural signal or packet-bound public-judgment "
                    "defect improved without structural regression"
                ),
            })
        else:
            style_gain_gate.update({
                "status": "review",
                "reason": (
                    "candidate is unchanged or has no measured structural improvement; "
                    "return to the affected facts and rewrite the local paragraph"
                ),
            })
    gates = [
        lexical_gate, contract_gate, voice_gate, rhythm_gate, scaffold_gate,
        comparison_gate, style_gain_gate,
    ]
    if judgment_bridge_gate is not None:
        gates.insert(-1, judgment_bridge_gate)
    required = [item for item in gates if item["required"]]
    hard_fail = any(item["status"] == "fail" for item in required)
    needs_review = any(item["status"] != "pass" for item in required)
    status = "fail" if hard_fail else "review" if needs_review else "pass"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "scope": "mechanical academic-style release gate; not authorship detection or final naturalness clearance",
        "source": {
            "path": str(source), "sha256": sha256_file(source),
            "tree_files": len(source_tree), "tree_sha256": source_hash,
        },
        "candidate": {
            "path": str(candidate), "sha256": sha256_file(candidate),
            "tree_files": len(candidate_tree), "tree_sha256": candidate_hash,
        },
        "decisions": {
            "path": str(decisions_path.resolve()) if decisions_path else None,
            "sha256": sha256_file(decisions_path.resolve()) if decisions_path else None,
        },
        "humanize_run": {
            "path": str(humanize_run_path.resolve()) if humanize_run_path else None,
            "status": humanize_keep_evidence.get("status"),
        },
        "packet_index": {
            "path": str(packet_index_path) if packet_index_path else None,
            "sha256": sha256_file(packet_index_path) if packet_index_path else None,
        },
        "style_intent": "require-gain" if require_style_gain else "preserve-or-improve",
        "dependencies": dependencies,
        "gates": gates,
        "recovery": build_recovery(gates),
        "summary": {
            "required": len(required),
            "passed": sum(item["status"] == "pass" for item in required),
            "review": sum(item["status"] == "review" for item in required),
            "failed": sum(item["status"] == "fail" for item in required),
        },
    }


def _render_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"ACADEMIC CANDIDATE {report['status'].upper()} "
        f"passed={summary['passed']}/{summary['required']} "
        f"review={summary['review']} failed={summary['failed']}"
    ]
    lines.extend(
        f"[{gate['status'].upper()}] {gate['id']} required={str(gate['required']).lower()}"
        for gate in report["gates"]
    )
    recovery = report.get("recovery", {})
    lines.append(
        f"RECOVERY {recovery.get('route', 'UNRESOLVED')} "
        f"candidate_repair_allowed={str(recovery.get('current_candidate_repair_allowed', False)).lower()}"
    )
    lines.append("NOTE: PASS is mechanical evidence only; it does not prove human authorship or final prose quality.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--scene", choices=("AUTO", "GENERAL", "MODELING", "RESEARCH", "COURSE"), default="MODELING")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument(
        "--humanize-run", type=Path,
        help=(
            "Replay one humanize-inline-run/v3 and import only exact, source-inherited "
            "strict-lexical KEEP evidence; semantic warnings remain pending."
        ),
    )
    parser.add_argument(
        "--require-style-gain", action="store_true",
        help=(
            "Require a measurable relative style improvement with no structural regression. "
            "Use for machine-voice reduction; omit for preservation-only audits."
        ),
    )
    parser.add_argument(
        "--packet-index", type=Path,
        help=(
            "Audit the frozen source and candidate against one source-bound section drafting "
            "packet index. A repaired model jump may satisfy style gain only when the candidate "
            "passes the same judgment-bridge contract."
        ),
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = audit(
            args.source, args.candidate, scene=args.scene,
            decisions_path=args.decisions, humanize_run_path=args.humanize_run,
            require_style_gain=args.require_style_gain,
            packet_index_path=args.packet_index,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        failure = {"schema": REPORT_SCHEMA, "status": "fail", "error": str(exc)}
        rendered = (
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else f"ACADEMIC CANDIDATE FAIL: {exc}\n"
        )
        if args.output:
            args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
            args.output.resolve().write_text(rendered, encoding="utf-8", newline="")
        else:
            sys.stdout.write(rendered)
        return 1
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else _render_text(report)
    )
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(rendered, encoding="utf-8", newline="")
    else:
        sys.stdout.write(rendered)
    if report["status"] == "pass":
        return 0
    return 1 if report["status"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
