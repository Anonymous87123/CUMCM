#!/usr/bin/env python3
"""Replay fixed long-document qualification scenarios against the live toolchain."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import finalize_humanize_long_document as finalizer  # noqa: E402
import prepare_humanize_long_document as preparer  # noqa: E402


SCENARIOS = {
    "LONG-20",
    "LONG-21",
    "LONG-22",
    "LONG-23",
    "LONG-24",
    "LONG-25",
    "LONG-26",
    "LONG-27",
}
BOUND_FIXTURE_SHA256 = "348026b7b26c646e67e809285ea11881865a3d35193a4131ff850813582c4d71"
REQUEST_SCHEMA = "humanize-structural-semantic-review-request/v1"
PAIRED_QUALITY_REQUEST_SCHEMA = "humanize-paired-quality-review-request/v1"


class ReplayError(ValueError):
    """Fail-closed fixture or replay error."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_regular_utf8(path: Path, label: str) -> tuple[Path, bytes, str]:
    if path.is_symlink():
        raise ReplayError(f"{label} must not be a symlink")
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ReplayError(f"cannot stat {label}: {error}") from error
    if not stat.S_ISREG(info.st_mode):
        raise ReplayError(f"{label} must be a regular file")
    attributes = int(getattr(info, "st_file_attributes", 0))
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    if attributes & reparse:
        raise ReplayError(f"{label} must not be a reparse point")
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise ReplayError(f"{label} must be strict UTF-8: {error}") from error
    if "\x00" in text or "\ufffd" in text:
        raise ReplayError(f"{label} contains forbidden NUL or replacement characters")
    return resolved, raw, text


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _specific_reason() -> str:
    return "保持说明职责并调整相邻说明段的阅读顺序"


def _single_unit_fixture_text(source_text: str) -> str:
    if not source_text.strip():
        raise ReplayError("bound fixture text is empty")
    return (
        "甲组曲线在前半段保持平缓，后半段的离散程度有所增加。\n\n"
        + "乙组曲线在相同区间内逐步上升，末段变化幅度略高。\n"
    )


def _transaction_fixture_text(source_text: str) -> str:
    if not source_text.strip():
        raise ReplayError("bound fixture text is empty")
    paragraphs = (
        "甲组曲线在前半段保持平缓，末段的离散程度略有增加。",
        "乙组曲线在相同区间缓慢上升，观测末段仍保持连续。",
        "丙组记录覆盖同一采样时段，曲线中部出现轻微波动。",
        "丁组记录沿用相同采样间隔，末段变化幅度相对较小。",
        "两组图线使用一致的坐标尺度，图例位置保持不变。",
        "比较文字只描述可见变化，不补充记录之外的原因。",
        "段落顺序服务于相邻比较，说明对象在句首直接出现。",
        "末段保留范围限制，读者可以据此区分观察与解释。",
    )
    return "\n\n".join(paragraphs) + "\n"


def _single_unit_structural_bundle(
    unit: dict[str, Any], chunk: dict[str, Any]
) -> dict[str, Any]:
    inventory = chunk.get("structural_paragraphs")
    if not isinstance(inventory, list) or len(inventory) < 2:
        raise ReplayError("fixture did not produce a usable structural paragraph inventory")
    movable_adjacent: tuple[int, int] | None = None
    for left in range(len(inventory) - 1):
        right = left + 1
        if (
            inventory[left].get("movable") is True
            and inventory[right].get("movable") is True
            and inventory[left].get("responsibility")
            == inventory[right].get("responsibility")
        ):
            movable_adjacent = (left, right)
            break
    if movable_adjacent is None:
        raise ReplayError("fixture has no adjacent same-responsibility movable paragraphs")
    left, right = movable_adjacent
    source_blocks = preparer.structural_paragraph_blocks(str(chunk["masked_text"]))
    source_by_id = {
        str(item["paragraph_id"]): source_blocks[int(item["ordinal"]) - 1]
        for item in inventory
    }
    ordered_ids = [str(item["paragraph_id"]) for item in inventory]
    ordered_ids[left], ordered_ids[right] = ordered_ids[right], ordered_ids[left]
    target_blocks = [source_by_id[item] for item in ordered_ids]
    masked_text = "\n\n".join(target_blocks)
    if str(chunk["masked_text"]).endswith(("\n", "\r")):
        masked_text += "\n"
    inventory_by_id = {str(item["paragraph_id"]): item for item in inventory}
    target_groups = [
        {
            "source_paragraph_ids": [paragraph_id],
            "target_paragraph_sha256": _sha256(block.encode("utf-8")),
            "responsibility": inventory_by_id[paragraph_id]["responsibility"],
            "reason": _specific_reason(),
        }
        for paragraph_id, block in zip(ordered_ids, target_blocks)
    ]
    return {
        "unit_id": unit["unit_id"],
        "chunk_binding_sha256": chunk["chunk_binding_sha256"],
        "voice_profile_sha256": chunk["voice_profile_sha256"],
        "decision": "REWRITE",
        "masked_text": masked_text,
        "keep_reasons": {},
        "structural_plan": {
            "schema_version": preparer.STRUCTURAL_PLAN_SCHEMA,
            "source_inventory_sha256": chunk["structural_inventory_sha256"],
            "target_groups": target_groups,
        },
    }


def _load_pending(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    units = finalizer._load_jsonl(run_dir / "units.jsonl")
    for unit in units:
        if unit.get("status") != "PENDING":
            continue
        chunk = finalizer._load_json(run_dir / "chunks" / f"{unit['unit_id']}.json")
        if isinstance(chunk, dict):
            return unit, chunk
    raise ReplayError("fixture prepare produced no PENDING unit")


def _verify_request(
    run_dir: Path,
    result: dict[str, Any],
    unit: dict[str, Any],
    chunk: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    requests = result.get("structural_semantic_review_requests")
    if not isinstance(requests, dict) or set(requests) != {unit["unit_id"]}:
        raise ReplayError("structural review request inventory mismatch")
    record = requests[unit["unit_id"]]
    relative = record.get("path")
    if not isinstance(relative, str) or not relative.startswith("validation/"):
        raise ReplayError("structural review request path is not stable and run-relative")
    request_path = run_dir / Path(relative)
    if request_path.is_symlink() or not request_path.is_file():
        raise ReplayError("structural review request artifact is missing or aliased")
    request = finalizer._load_json(request_path)
    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        raise ReplayError("structural review request schema mismatch")
    unsigned = dict(request)
    stored = unsigned.pop("request_sha256", None)
    if stored != _sha256(_canonical_json(unsigned)) or stored != record.get("request_sha256"):
        raise ReplayError("structural review request self-hash mismatch")
    artifact = request.get("artifact")
    trust = request.get("trust_boundary")
    refs = request.get("artifact_refs")
    if not isinstance(artifact, dict) or not isinstance(trust, dict) or not isinstance(refs, dict):
        raise ReplayError("structural review request evidence sections are missing")
    expected = {
        "chunk_binding_sha256": chunk["chunk_binding_sha256"],
        "voice_profile_sha256": chunk["voice_profile_sha256"],
        "source_inventory_sha256": chunk["structural_inventory_sha256"],
        "structural_plan_sha256": _sha256(_canonical_json(bundle["structural_plan"])),
    }
    if any(artifact.get(key) != value for key, value in expected.items()):
        raise ReplayError("structural review request identity binding mismatch")
    for relative_ref in refs.values():
        if not isinstance(relative_ref, str) or not relative_ref.startswith("validation/"):
            raise ReplayError("structural review request contains an unstable artifact ref")
        artifact_path = run_dir / Path(relative_ref)
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise ReplayError("structural review request points to missing evidence")
    if (
        trust.get("local_clearance_supported") is not False
        or trust.get("external_signature_verified") is not False
        or trust.get("completion_claim_allowed") is not False
    ):
        raise ReplayError("structural review request exceeds the local trust boundary")
    return request


def _run_single_unit_case(source_text: str, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source.md"
    source.write_text(source_text, encoding="utf-8", newline="\n")
    run_dir = root / "run"
    preparer.prepare(
        [source],
        run_dir,
        scene="GENERAL",
        intensity="STRUCTURAL",
    )
    unit, chunk = _load_pending(run_dir)
    bundle = _single_unit_structural_bundle(unit, chunk)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    _write_json(rewrites / f"{unit['unit_id']}.json", bundle)
    result = finalizer.finalize(run_dir, rewrites)
    request = _verify_request(run_dir, result, unit, chunk, bundle)
    return result, {
        "run_dir": run_dir,
        "unit": unit,
        "chunk": chunk,
        "bundle": bundle,
        "request": request,
    }


def _pending_units_and_chunks(
    run_dir: Path,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for unit in finalizer._load_jsonl(run_dir / "units.jsonl"):
        if unit.get("status") != "PENDING":
            continue
        unit_id = str(unit["unit_id"])
        chunk = finalizer._load_json(run_dir / "chunks" / f"{unit_id}.json")
        if not isinstance(chunk, dict):
            raise ReplayError("paired-quality fixture chunk is missing")
        pairs.append((unit, chunk))
    if not pairs:
        raise ReplayError("paired-quality fixture produced no PENDING units")
    return pairs


def _verify_paired_quality_requests(
    run_dir: Path,
    result: dict[str, Any],
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    expected_ids = {str(unit["unit_id"]) for unit, _chunk in pairs}
    records = result.get("paired_quality_review_requests")
    if not isinstance(records, dict) or set(records) != expected_ids:
        raise ReplayError("paired-quality request inventory mismatch")
    schemas: set[str] = set()
    decisions: set[str] = set()
    for unit_id in sorted(expected_ids):
        record = records[unit_id]
        relative = record.get("path") if isinstance(record, dict) else None
        if not isinstance(relative, str) or not relative.startswith("validation/"):
            raise ReplayError("paired-quality request path is not stable and run-relative")
        request_path = run_dir / Path(relative)
        if request_path.is_symlink() or not request_path.is_file():
            raise ReplayError("paired-quality request artifact is missing or aliased")
        request = finalizer._load_json(request_path)
        if not isinstance(request, dict):
            raise ReplayError("paired-quality request is not an object")
        schemas.add(str(request.get("schema", "")))
        unsigned = dict(request)
        stored_hash = unsigned.pop("request_sha256", None)
        if (
            stored_hash != _sha256(_canonical_json(unsigned))
            or stored_hash != record.get("request_sha256")
        ):
            raise ReplayError("paired-quality request self-hash mismatch")
        validation = finalizer._load_json(
            run_dir / "validation" / f"{unit_id}.validation.json"
        )
        artifact = request.get("artifact")
        context = request.get("validation_context")
        if (
            not isinstance(validation, dict)
            or not isinstance(artifact, dict)
            or not isinstance(context, dict)
            or artifact.get("before_sha256")
            != validation.get("evidence", {}).get("before_sha256")
            or artifact.get("after_sha256")
            != validation.get("evidence", {}).get("after_sha256")
            or context.get("mechanical_validation_status") != "PASS"
            or request.get("status") != "PENDING_EXTERNAL_REVIEW"
            or request.get("limitations", {}).get("quality_clearance_granted")
            is not False
        ):
            raise ReplayError("paired-quality request artifact binding mismatch")
        decision = str(context.get("decision", ""))
        decisions.add(decision)
        if decision == "NO_CHANGE" and (
            request.get("changes") != []
            or artifact.get("before_sha256") != artifact.get("after_sha256")
        ):
            raise ReplayError("NO_CHANGE paired-quality request is not empty and bound")
    if schemas != {PAIRED_QUALITY_REQUEST_SCHEMA}:
        raise ReplayError("paired-quality request schema mismatch")
    return {
        "schema": next(iter(schemas)),
        "binding_status": "PASS",
        "no_change_status": "PASS" if decisions == {"NO_CHANGE"} else "FAIL",
    }


def _run_paired_quality_case(
    source_text: str,
    root: Path,
    *,
    reject_second_pass_receipt: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source.md"
    source.write_text(source_text, encoding="utf-8", newline="\n")
    run_dir = root / "run"
    preparer.prepare([source], run_dir, scene="GENERAL", intensity="BALANCED")
    pairs = _pending_units_and_chunks(run_dir)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    for unit, chunk in pairs:
        unit_id = str(unit["unit_id"])
        _write_json(
            rewrites / f"{unit_id}.json",
            {
                "unit_id": unit_id,
                "chunk_binding_sha256": chunk["chunk_binding_sha256"],
                "voice_profile_sha256": chunk["voice_profile_sha256"],
                "decision": "NO_CHANGE",
                "reason": "原段职责与平行关系均保持清楚",
                "keep_reasons": {},
            },
        )
    receipt = root / "caller-receipt.json" if reject_second_pass_receipt else None
    result = finalizer.finalize(run_dir, rewrites, second_pass_receipt=receipt)
    evidence: dict[str, Any] = {
        "run_dir": run_dir,
        "pairs": pairs,
        "rewrites": rewrites,
    }
    if not reject_second_pass_receipt:
        evidence["request_state"] = _verify_paired_quality_requests(
            run_dir, result, pairs
        )
    return result, evidence


def _self_clearance_is_rejected(source_text: str, root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source.md"
    source.write_text(source_text, encoding="utf-8", newline="\n")
    run_dir = root / "run"
    preparer.prepare(
        [source],
        run_dir,
        scene="GENERAL",
        intensity="STRUCTURAL",
    )
    unit, chunk = _load_pending(run_dir)
    bundle = _single_unit_structural_bundle(unit, chunk)
    bundle["structural_semantic_clearance"] = {
        "reviewer_kind": "VERIFIED_HUMAN",
        "status": "PASS",
    }
    rewrites = root / "rewrites"
    rewrites.mkdir()
    _write_json(rewrites / f"{unit['unit_id']}.json", bundle)
    result = finalizer.finalize(run_dir, rewrites)
    ledger = finalizer._load_csv(run_dir / "coverage_ledger.final.csv")
    row = next(item for item in ledger if item["unit_id"] == unit["unit_id"])
    return bool(
        result.get("candidate_assembly_status") == "REVIEW"
        and result.get("structural_semantic_review_requests") == {}
        and row.get("status") == "UNRESOLVED"
        and "structural_semantic_clearance" in row.get("notes", "")
    )


def _load_transaction_candidate(
    run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    inventory = finalizer._load_json(run_dir / "structural_transaction_inventory.json")
    if not isinstance(inventory, dict):
        raise ReplayError("transaction inventory is not an object")
    transactions = inventory.get("transactions")
    if inventory.get("status") != "READY" or not isinstance(transactions, list):
        raise ReplayError("transaction inventory did not produce READY candidates")
    for transaction in transactions:
        if not isinstance(transaction, dict):
            continue
        refs = transaction.get("compound_refs")
        if not isinstance(refs, list) or len(refs) != 2:
            continue
        chunks: dict[str, dict[str, Any]] = {}
        eligible = True
        for ref in refs:
            unit_id = str(ref.get("unit_id", "")) if isinstance(ref, dict) else ""
            chunk = finalizer._load_json(run_dir / "chunks" / f"{unit_id}.json")
            if not isinstance(chunk, dict):
                eligible = False
                break
            chunks[unit_id] = chunk
        if not eligible:
            continue
        right_id = str(refs[1]["unit_id"])
        right_inventory = chunks[right_id].get("structural_paragraphs")
        if (
            isinstance(right_inventory, list)
            and len(right_inventory) >= 2
            and right_inventory[0].get("movable") is True
        ):
            return inventory, transaction, chunks
    raise ReplayError("no transaction candidate supports a boundary-only movable source ref")


def _source_records(
    transaction: dict[str, Any], chunks: dict[str, dict[str, Any]]
) -> tuple[list[str], dict[tuple[str, str], dict[str, Any]]]:
    ordered_units = [str(ref["unit_id"]) for ref in transaction["compound_refs"]]
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for unit_id in ordered_units:
        chunk = chunks[unit_id]
        blocks = preparer.structural_paragraph_blocks(str(chunk["masked_text"]))
        for item in chunk["structural_paragraphs"]:
            paragraph_id = str(item["paragraph_id"])
            records[(unit_id, paragraph_id)] = {
                "unit_id": unit_id,
                "paragraph_id": paragraph_id,
                "block": blocks[int(item["ordinal"]) - 1],
                "inventory": item,
            }
    return ordered_units, records


def _fragment_from_refs(
    target_unit_id: str,
    refs: list[tuple[str, str]],
    records: dict[tuple[str, str], dict[str, Any]],
    *,
    trailing_newline: bool,
) -> dict[str, Any]:
    blocks = [str(records[ref]["block"]) for ref in refs]
    masked_text = "\n\n".join(blocks) + ("\n" if trailing_newline else "")
    lines = masked_text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
        keepends=True
    )
    evidence_line = next(
        (
            index
            for index, line in enumerate(lines, 1)
            if re.search(r"[\u3400-\u9fff]", line)
        ),
        None,
    )
    if evidence_line is None:
        raise ReplayError("transaction fragment has no author line for intent evidence")
    return {
        "target_unit_id": target_unit_id,
        "masked_text": masked_text,
        "keep_reasons": {},
        "target_groups": [
            {
                "source_refs": [
                    {"unit_id": ref[0], "paragraph_id": ref[1]}
                ],
                "target_paragraph_sha256": _sha256(
                    str(records[ref]["block"]).encode("utf-8")
                ),
                "responsibility": records[ref]["inventory"]["responsibility"],
                "reason": "保持说明职责并调整相邻分块的段落归属",
            }
            for ref in refs
        ],
        "local_rewrite_intent": {
            "decision": "NO_CHANGE",
            "reason": "该目标片段只承接结构移动，保留段内原有对象和措辞",
            "evidence_spans": [
                {
                    "id": "S1",
                    "start_line": evidence_line,
                    "end_line": evidence_line,
                    "sha256": _sha256(lines[evidence_line - 1].encode("utf-8")),
                }
            ],
        },
        "template_field_edit_scope": None,
    }


def _transaction_bundle(
    inventory: dict[str, Any],
    transaction: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ordered_units, records = _source_records(transaction, chunks)
    left_id, right_id = ordered_units
    left_refs = [key for key in records if key[0] == left_id]
    right_refs = [key for key in records if key[0] == right_id]
    move_ref = right_refs[0]
    if records[move_ref]["inventory"].get("movable") is not True or len(right_refs) < 2:
        raise ReplayError("transaction fixture cannot move the right boundary paragraph")
    left_target = [*left_refs, move_ref]
    right_target = right_refs[1:]
    fragments = [
        _fragment_from_refs(
            left_id,
            left_target,
            records,
            trailing_newline=str(chunks[left_id]["masked_text"]).endswith(("\n", "\r")),
        ),
        _fragment_from_refs(
            right_id,
            right_target,
            records,
            trailing_newline=str(chunks[right_id]["masked_text"]).endswith(("\n", "\r")),
        ),
    ]
    return {
        "schema_version": finalizer.STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA,
        "transaction_id": transaction["transaction_id"],
        "transaction_binding_sha256": transaction["transaction_binding_sha256"],
        "transaction_inventory_sha256": inventory["inventory_sha256"],
        "unit_bindings": [
            {
                "unit_id": unit_id,
                "chunk_binding_sha256": chunks[unit_id]["chunk_binding_sha256"],
                "voice_profile_sha256": chunks[unit_id]["voice_profile_sha256"],
            }
            for unit_id in ordered_units
        ],
        "fragments": fragments,
    }


def _prepare_transaction_run(source_text: str, root: Path) -> tuple[Path, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=False)
    source = root / "source.md"
    source.write_text(source_text, encoding="utf-8", newline="\n")
    run_dir = root / "run"
    preparer.prepare(
        [source],
        run_dir,
        scene="GENERAL",
        intensity="STRUCTURAL",
        structural_transaction_scope="ADJACENT_PAIR",
        max_author_chars=100,
        max_lines=80,
        min_author_chars=30,
    )
    inventory, transaction, chunks = _load_transaction_candidate(run_dir)
    return run_dir, _transaction_bundle(inventory, transaction, chunks)


def _transaction_decline_bundle(
    run_dir: Path, transaction_bundle: dict[str, Any]
) -> dict[str, Any]:
    evidence_refs: list[dict[str, str]] = []
    for binding in transaction_bundle["unit_bindings"]:
        unit_id = str(binding["unit_id"])
        chunk = finalizer._load_json(run_dir / "chunks" / f"{unit_id}.json")
        paragraphs = chunk.get("structural_paragraphs") if isinstance(chunk, dict) else None
        if not isinstance(paragraphs, list) or not paragraphs:
            raise ReplayError("transaction decline member has no source paragraph evidence")
        evidence_refs.append(
            {
                "unit_id": unit_id,
                "paragraph_id": str(paragraphs[0]["paragraph_id"]),
            }
        )
    return {
        "schema_version": "humanize-structural-transaction-decline/v1",
        "decision": "DECLINE",
        "transaction_id": transaction_bundle["transaction_id"],
        "transaction_binding_sha256": transaction_bundle[
            "transaction_binding_sha256"
        ],
        "transaction_inventory_sha256": transaction_bundle[
            "transaction_inventory_sha256"
        ],
        "unit_bindings": copy.deepcopy(transaction_bundle["unit_bindings"]),
        "reason_code": "DEPENDENCY_OR_REFERENT_RISK",
        "reason": "两侧说明分别依赖各自观察对象，跨单元移动会造成指代范围漂移",
        "evidence_refs": evidence_refs,
    }


def _write_pending_unit_no_changes(run_dir: Path, rewrites: Path) -> int:
    count = 0
    for path in sorted((run_dir / "chunks").glob("*.json")):
        chunk = finalizer._load_json(path)
        if not isinstance(chunk, dict) or chunk.get("status") != "PENDING":
            continue
        unit_id = str(chunk["unit_id"])
        bundle = {
            "unit_id": unit_id,
            "chunk_binding_sha256": chunk["chunk_binding_sha256"],
            "voice_profile_sha256": chunk["voice_profile_sha256"],
            "decision": "NO_CHANGE",
            "reason": "现有段序和说明职责已经对应清楚",
            "keep_reasons": {},
        }
        _write_json(rewrites / f"{unit_id}.json", bundle)
        count += 1
    if count == 0:
        raise ReplayError("transaction disposition fixture has no pending units")
    return count


def _run_transaction_disposition_case(
    source_text: str, root: Path, *, include_decline: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir, transaction_bundle = _prepare_transaction_run(source_text, root)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    unit_count = _write_pending_unit_no_changes(run_dir, rewrites)
    decline = _transaction_decline_bundle(run_dir, transaction_bundle)
    if include_decline:
        _write_json(rewrites / "candidate.decline.json", decline)
    result = finalizer.finalize(run_dir, rewrites)
    return result, {
        "run_dir": run_dir,
        "rewrites": rewrites,
        "transaction_bundle": transaction_bundle,
        "decline": decline,
        "unit_count": unit_count,
    }


def _transaction_execution_decline_conflict_rejected(
    source_text: str, root: Path
) -> bool:
    run_dir, transaction_bundle = _prepare_transaction_run(source_text, root)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    _write_json(rewrites / "candidate.transaction.json", transaction_bundle)
    _write_json(
        rewrites / "candidate.decline.json",
        _transaction_decline_bundle(run_dir, transaction_bundle),
    )
    try:
        finalizer.finalize(run_dir, rewrites)
    except ValueError as error:
        return bool(
            "structural transaction execution and decline conflict" in str(error)
            and not (run_dir / "coverage_ledger.final.csv").exists()
            and not (run_dir / "rendered").exists()
        )
    return False


def _transaction_stale_decline_rejected(source_text: str, root: Path) -> bool:
    run_dir, transaction_bundle = _prepare_transaction_run(source_text, root)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    stale = _transaction_decline_bundle(run_dir, transaction_bundle)
    stale["transaction_binding_sha256"] = "f" * 64
    _write_json(rewrites / "candidate.decline.json", stale)
    try:
        finalizer.finalize(run_dir, rewrites)
    except ValueError as error:
        return bool(
            "structural_transaction_binding_hash_mismatch" in str(error)
            and not (run_dir / "coverage_ledger.final.csv").exists()
            and not (run_dir / "rendered").exists()
        )
    return False


def _run_transaction_case(source_text: str, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir, bundle = _prepare_transaction_run(source_text, root)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    transaction_id = str(bundle["transaction_id"])
    bundle_path = rewrites / f"{transaction_id}.json"
    _write_json(bundle_path, bundle)
    result = finalizer.finalize(run_dir, rewrites)
    transaction_results = result.get("structural_transaction_results")
    request_records = result.get("structural_transaction_review_requests")
    if not isinstance(transaction_results, dict) or transaction_id not in transaction_results:
        raise ReplayError("finalizer omitted the submitted transaction result")
    if not isinstance(request_records, dict) or transaction_id not in request_records:
        raise ReplayError("finalizer omitted the transaction review request")
    request_record = request_records[transaction_id]
    request_path = run_dir / Path(str(request_record.get("path", "")))
    if request_path.is_symlink() or not request_path.is_file():
        raise ReplayError("transaction review request path is missing or aliased")
    request = finalizer._load_json(request_path)
    if (
        not isinstance(request, dict)
        or request.get("schema") != "humanize-structural-transaction-review-request/v2"
    ):
        raise ReplayError("transaction review request schema mismatch")
    unsigned = dict(request)
    stored = unsigned.pop("request_sha256", None)
    if stored != _sha256(_canonical_json(unsigned)) or stored != request_record.get(
        "request_sha256"
    ):
        raise ReplayError("transaction review request self-hash mismatch")
    return result, {
        "run_dir": run_dir,
        "rewrites": rewrites,
        "bundle": bundle,
        "bundle_path": bundle_path,
        "transaction_id": transaction_id,
        "transaction_result": transaction_results[transaction_id],
        "request": request,
    }


def _transaction_member_conflict_rejected(source_text: str, root: Path) -> bool:
    run_dir, bundle = _prepare_transaction_run(source_text, root)
    rewrites = root / "rewrites"
    rewrites.mkdir()
    transaction_id = str(bundle["transaction_id"])
    _write_json(rewrites / f"{transaction_id}.json", bundle)
    left = bundle["unit_bindings"][0]
    chunk = finalizer._load_json(run_dir / "chunks" / f"{left['unit_id']}.json")
    standalone = {
        "unit_id": left["unit_id"],
        "chunk_binding_sha256": left["chunk_binding_sha256"],
        "voice_profile_sha256": left["voice_profile_sha256"],
        "decision": "NO_CHANGE",
        "reason": "相邻事务已经负责该单元的结构调整",
        "keep_reasons": {},
    }
    if not isinstance(chunk, dict):
        raise ReplayError("transaction conflict chunk is missing")
    _write_json(rewrites / f"{left['unit_id']}.json", standalone)
    try:
        finalizer.finalize(run_dir, rewrites)
    except ValueError as error:
        return bool(
            str(error).startswith(
                "structural transaction member also has standalone rewrite:"
            )
            and not (run_dir / "coverage_ledger.final.csv").exists()
            and not (run_dir / "diffs").exists()
            and not (run_dir / "rendered_review").exists()
        )
    return False


def _transaction_atomic_rollback_passes(source_text: str, root: Path) -> bool:
    run_dir, bundle = _prepare_transaction_run(source_text, root)
    bad = copy.deepcopy(bundle)
    bad["fragments"][0]["target_groups"][0]["target_paragraph_sha256"] = "0" * 64
    rewrites = root / "rewrites"
    rewrites.mkdir()
    transaction_id = str(bundle["transaction_id"])
    _write_json(rewrites / f"{transaction_id}.json", bad)
    result = finalizer.finalize(run_dir, rewrites)
    ledger = finalizer._load_csv(run_dir / "coverage_ledger.final.csv")
    member_ids = {str(item["unit_id"]) for item in bundle["unit_bindings"]}
    rows = [row for row in ledger if row.get("unit_id") in member_ids]
    rolled_back = result.get("structural_transaction_rolled_back_ids")
    return bool(
        isinstance(rolled_back, list)
        and transaction_id in rolled_back
        and len(rows) == 2
        and all(row.get("status") == "UNRESOLVED" for row in rows)
        and not any((run_dir / "diffs" / f"{unit_id}.diff").exists() for unit_id in member_ids)
    )


def _transaction_replay_is_stable(evidence: dict[str, Any]) -> bool:
    run_dir = Path(evidence["run_dir"])
    before_rendered = finalizer._directory_hashes(run_dir / "rendered_review")
    before_validation = finalizer._directory_hashes(run_dir / "validation")
    replay = finalizer.finalize(run_dir, Path(evidence["rewrites"]))
    return bool(
        replay.get("assembly_replay_idempotency") == "PASS"
        and before_rendered == finalizer._directory_hashes(run_dir / "rendered_review")
        and before_validation == finalizer._directory_hashes(run_dir / "validation")
    )


def _second_pass_seed_is_rejected(run_dir: Path, root: Path) -> bool:
    path = SCRIPT_DIR / "prepare_humanize_second_pass.py"
    spec = importlib.util.spec_from_file_location("_long_replay_second_pass", path)
    if spec is None or spec.loader is None:
        raise ReplayError("cannot load second-pass preparer")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
    try:
        module.prepare_second_pass(run_dir, root / "second-run", root / "cases")
    except module.SecondPassPreparationError:
        return True
    return False


def _projection_transaction_checks(root: Path) -> dict[str, bool]:
    global finalizer, preparer

    root.mkdir(parents=True, exist_ok=False)
    path = SCRIPT_DIR / "build_humanize_generator_projection.py"
    spec = importlib.util.spec_from_file_location("_long_replay_projection", path)
    if spec is None or spec.loader is None:
        raise ReplayError("cannot load projection builder")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
    projection = root / "projection-a"
    manifest = root / "projection-a-manifest.json"
    result = module.build_projection(SCRIPT_DIR.parent, projection, manifest)
    projection_b = root / "projection-b"
    manifest_b = root / "projection-b-manifest.json"
    result_b = module.build_projection(SCRIPT_DIR.parent, projection_b, manifest_b)
    tree_a = {
        path.relative_to(projection).as_posix(): path.read_bytes()
        for path in projection.rglob("*")
        if path.is_file()
    }
    tree_b = {
        path.relative_to(projection_b).as_posix(): path.read_bytes()
        for path in projection_b.rglob("*")
        if path.is_file()
    }
    reproducible = bool(
        tree_a == tree_b
        and result.get("projection_tree_sha256")
        == result_b.get("projection_tree_sha256")
    )
    text = "\n".join(
        artifact.read_text(encoding="utf-8")
        for artifact in projection.rglob("*")
        if artifact.is_file() and artifact.suffix.lower() in {".md", ".json", ".py", ".yaml"}
    )
    forbidden = (
        "LONG-20",
        "LONG-21",
        "LONG-22",
        "LONG-23",
        "LONG-24",
        "LONG-25",
        "LONG-26",
        "LONG-27",
        "replay_humanize_long_fixture.py",
        "transaction_non_downgrade_status",
    )
    control_absent = bool(
        result.get("audits", {}).get("secret_control_identifier_scan") == "PASS"
        and all(token not in text for token in forbidden)
    )

    scripts = projection / "scripts"
    previous_path = list(sys.path)
    previous_preparer_module = sys.modules.get("prepare_humanize_long_document")
    previous_finalizer_module = sys.modules.get("finalize_humanize_long_document")
    installed_preparer = preparer
    installed_finalizer = finalizer
    transaction_surface = False
    try:
        sys.path.insert(0, str(scripts))
        preparer_spec = importlib.util.spec_from_file_location(
            "prepare_humanize_long_document",
            scripts / "prepare_humanize_long_document.py",
        )
        if preparer_spec is None or preparer_spec.loader is None:
            raise ReplayError("cannot load projected prepare entrypoint")
        projected_preparer = importlib.util.module_from_spec(preparer_spec)
        sys.modules["prepare_humanize_long_document"] = projected_preparer
        preparer_spec.loader.exec_module(projected_preparer)

        finalizer_spec = importlib.util.spec_from_file_location(
            "finalize_humanize_long_document",
            scripts / "finalize_humanize_long_document.py",
        )
        if finalizer_spec is None or finalizer_spec.loader is None:
            raise ReplayError("cannot load projected finalize entrypoint")
        projected_finalizer = importlib.util.module_from_spec(finalizer_spec)
        sys.modules["finalize_humanize_long_document"] = projected_finalizer
        finalizer_spec.loader.exec_module(projected_finalizer)

        preparer = projected_preparer
        finalizer = projected_finalizer
        smoke_result, smoke_evidence = _run_transaction_case(
            _transaction_fixture_text("projection transaction smoke"),
            root / "projection-transaction-smoke",
        )
        transaction_surface = bool(
            smoke_result.get("candidate_assembly_status") == "PASS"
            and smoke_result.get("delivery_gate_status") == "REVIEW"
            and smoke_result.get("structural_transactions_total") == 1
            and smoke_evidence.get("transaction_result", {}).get(
                "atomic_gate_status"
            )
            == "PASS"
            and (Path(smoke_evidence["run_dir"]) / "rendered_review").is_dir()
        )
    finally:
        preparer = installed_preparer
        finalizer = installed_finalizer
        sys.path[:] = previous_path
        if previous_preparer_module is None:
            sys.modules.pop("prepare_humanize_long_document", None)
        else:
            sys.modules["prepare_humanize_long_document"] = previous_preparer_module
        if previous_finalizer_module is None:
            sys.modules.pop("finalize_humanize_long_document", None)
        else:
            sys.modules["finalize_humanize_long_document"] = previous_finalizer_module

    return {
        "control_surface_absent": control_absent,
        "reproducible": reproducible,
        "transaction_surface": transaction_surface,
    }


def _transaction_layer_statuses(evidence: dict[str, Any]) -> dict[str, str]:
    run_dir = Path(evidence["run_dir"])
    statuses: dict[str, list[str]] = {
        "hard_invariant_layer_status": [],
        "speech_act_layer_status": [],
        "style_signal_layer_status": [],
    }
    for binding in evidence["bundle"]["unit_bindings"]:
        path = run_dir / "validation" / f"{binding['unit_id']}.validation.json"
        payload = finalizer._load_json(path)
        if not isinstance(payload, dict):
            raise ReplayError("transaction member validation artifact is invalid")
        for field in statuses:
            statuses[field].append(str(payload.get(field, "")))
    return {
        "hard_invariant_layer_status": (
            "PASS" if all(item == "PASS" for item in statuses["hard_invariant_layer_status"]) else "FAIL"
        ),
        "speech_act_layer_status": (
            "PASS" if all(item == "PASS" for item in statuses["speech_act_layer_status"]) else "REVIEW"
        ),
        "style_signal_layer_status": (
            "PASS" if all(item == "PASS" for item in statuses["style_signal_layer_status"]) else "REVIEW"
        ),
    }


def replay(input_path: Path, output_path: Path, scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ReplayError(f"unsupported scenario: {scenario}")
    _input, input_raw, input_text = _strict_regular_utf8(input_path, "input")
    _output, output_raw, _output_text = _strict_regular_utf8(output_path, "output")
    if input_raw != output_raw:
        raise ReplayError("output mirror bytes do not equal the bound input fixture")
    if _sha256(input_raw) != BOUND_FIXTURE_SHA256:
        raise ReplayError("input/output bytes are not the fixed qualification fixture")
    with tempfile.TemporaryDirectory(prefix="humanize-long-replay-") as temporary:
        temp_root = Path(temporary)
        if scenario in {"LONG-20", "LONG-21"}:
            fixture_text = _single_unit_fixture_text(input_text)
            result, evidence = _run_single_unit_case(fixture_text, temp_root / "primary")
            request = evidence["request"]
            clearance_rejected = None
            if scenario == "LONG-21":
                clearance_rejected = _self_clearance_is_rejected(
                    fixture_text, temp_root / "clearance"
                )
            if clearance_rejected is False:
                raise ReplayError("local structural semantic clearance was not rejected")
            run_dir = evidence["run_dir"]
            validation = finalizer._load_json(
                run_dir / "validation" / f"{evidence['unit']['unit_id']}.validation.json"
            )
            payload = {
                "status": result["status"],
                "delivery_gate_status": result["delivery_gate_status"],
                "exit_code": result["exit_code"],
                "delivery_gate_exit_code": result["exit_code"],
                "academic_correctness": "NOT_EVALUATED",
                "hard_invariant_layer_status": validation["hard_invariant_layer_status"],
                "speech_act_layer_status": validation["speech_act_layer_status"],
                "style_signal_layer_status": validation["style_signal_layer_status"],
                "candidate_assembly_status": result["candidate_assembly_status"],
                "publish_state": result["publish_state"],
                "structural_plan_status": result["structural_plan_status"],
                "structural_semantic_mapping": result["structural_semantic_mapping"],
                "structural_semantic_review_status": result[
                    "structural_semantic_review_status"
                ],
                "structural_review_request_schema": request["schema"],
                "structural_review_request_binding_status": "PASS",
                "local_clearance_supported": request["trust_boundary"][
                    "local_clearance_supported"
                ],
                "local_clearance_bundle_rejected": (
                    clearance_rejected
                    if clearance_rejected is not None
                    else "NOT_RUN"
                ),
                "rendered_exists": (run_dir / "rendered").exists(),
                "rendered_review_exists": (run_dir / "rendered_review").is_dir(),
            }
        elif scenario in {"LONG-26", "LONG-27"}:
            fixture_text = _single_unit_fixture_text(input_text)
            result, evidence = _run_paired_quality_case(
                fixture_text, temp_root / "paired-quality-primary"
            )
            request_state = evidence["request_state"]
            receipt_result = None
            if scenario == "LONG-27":
                receipt_result, _receipt_evidence = _run_paired_quality_case(
                    fixture_text,
                    temp_root / "paired-quality-receipt-rejection",
                    reject_second_pass_receipt=True,
                )
                receipt_error = receipt_result.get(
                    "humanize_second_pass_evidence", {}
                ).get("error")
                if not (
                    receipt_result.get("status") == "FAIL"
                    and receipt_result.get("second_pass_stability_status")
                    == "INVALID_EVIDENCE"
                    and receipt_result.get("second_pass_quality_clearance_granted")
                    is False
                    and receipt_result.get("paired_quality_clearance_granted") is False
                    and receipt_result.get("humanize_completion_claim_allowed") is False
                    and receipt_error
                    == "second_pass_receipt_not_allowed_for_review_candidate:PAIRED_QUALITY"
                ):
                    raise ReplayError(
                        "paired-quality second-pass receipt was not rejected"
                    )
            run_dir = Path(evidence["run_dir"])
            validations = [
                finalizer._load_json(
                    run_dir / "validation" / f"{unit['unit_id']}.validation.json"
                )
                for unit, _chunk in evidence["pairs"]
            ]
            if not all(isinstance(item, dict) for item in validations):
                raise ReplayError("paired-quality validation evidence is missing")
            payload = {
                "status": result["status"],
                "delivery_gate_status": result["delivery_gate_status"],
                "exit_code": result["exit_code"],
                "delivery_gate_exit_code": result["exit_code"],
                "academic_correctness": "NOT_EVALUATED",
                "hard_invariant_layer_status": (
                    "PASS"
                    if all(item.get("hard_invariant_layer_status") == "PASS" for item in validations)
                    else "FAIL"
                ),
                "speech_act_layer_status": (
                    "PASS"
                    if all(item.get("speech_act_layer_status") == "PASS" for item in validations)
                    else "REVIEW"
                ),
                "style_signal_layer_status": (
                    "PASS"
                    if all(item.get("style_signal_layer_status") == "PASS" for item in validations)
                    else "REVIEW"
                ),
                "candidate_assembly_status": result["candidate_assembly_status"],
                "publish_state": result["publish_state"],
                "paired_quality_review_request_schema": request_state["schema"],
                "paired_quality_review_request_binding_status": request_state[
                    "binding_status"
                ],
                "paired_quality_review_request_coverage_status": result[
                    "paired_quality_review_request_coverage_status"
                ],
                "paired_quality_gate_status": result["paired_quality_gate_status"],
                "paired_quality_units_total": result["paired_quality_units_total"],
                "paired_quality_units_pending": result[
                    "paired_quality_units_pending"
                ],
                "paired_quality_units_missing": result["paired_quality_units_missing"],
                "paired_quality_clearance_granted": result[
                    "paired_quality_clearance_granted"
                ],
                "paired_quality_local_clearance_supported": result[
                    "paired_quality_local_clearance_supported"
                ],
                "paired_quality_no_change_request_status": request_state[
                    "no_change_status"
                ],
                "humanize_completion_claim_allowed": result[
                    "humanize_completion_claim_allowed"
                ],
                "rendered_exists": (run_dir / "rendered").exists(),
                "rendered_review_exists": (run_dir / "rendered_review").is_dir(),
            }
            if receipt_result is not None:
                payload.update(
                    {
                        "second_pass_seed_rejected": True,
                        "humanize_second_pass_convergence": receipt_result[
                            "humanize_second_pass_convergence"
                        ],
                        "second_pass_stability_status": receipt_result[
                            "second_pass_stability_status"
                        ],
                        "second_pass_quality_clearance_granted": receipt_result[
                            "second_pass_quality_clearance_granted"
                        ],
                    }
                )
        elif scenario == "LONG-25":
            fixture_text = _transaction_fixture_text(input_text)
            pending_result, pending_evidence = _run_transaction_disposition_case(
                fixture_text,
                temp_root / "pending-disposition",
                include_decline=False,
            )
            decline_result, decline_evidence = _run_transaction_disposition_case(
                fixture_text,
                temp_root / "declined-disposition",
                include_decline=True,
            )
            conflict_rejected = _transaction_execution_decline_conflict_rejected(
                fixture_text, temp_root / "execution-decline-conflict"
            )
            stale_decline_rejected = _transaction_stale_decline_rejected(
                fixture_text, temp_root / "stale-decline"
            )
            transaction_id = str(
                decline_evidence["transaction_bundle"]["transaction_id"]
            )
            decline_record = decline_result.get(
                "structural_transaction_decline_results", {}
            ).get(transaction_id, {})
            disposition = decline_result.get(
                "structural_transaction_candidate_dispositions", {}
            ).get(transaction_id, {})
            pending_transaction_id = str(
                pending_evidence["transaction_bundle"]["transaction_id"]
            )
            pending_disposition = pending_result.get(
                "structural_transaction_candidate_dispositions", {}
            ).get(pending_transaction_id, {})
            decline_path = Path(decline_evidence["run_dir"]) / Path(
                str(decline_record.get("path", ""))
            )
            no_change_does_not_dispose = bool(
                pending_disposition.get("disposition") == "PENDING"
                and pending_result.get("structural_transaction_candidates_pending") == 1
                and pending_result.get(
                    "structural_transaction_candidate_coverage_status"
                )
                == "REVIEW"
                and pending_result.get("coverage_completion_claim_allowed") is False
                and set(pending_result.get("unit_statuses", {})) == {"NO_CHANGE"}
            )
            decline_closure_passes = bool(
                decline_result.get("structural_transaction_candidates_declined") == 1
                and decline_result.get("structural_transaction_candidates_pending") == 0
                and decline_result.get(
                    "structural_transaction_candidate_coverage_status"
                )
                == "PASS"
                and decline_result.get("structural_transaction_scope_complete") is True
                and decline_result.get("candidate_assembly_status") == "PASS"
                and decline_result.get("delivery_gate_status") == "REVIEW"
                and decline_result.get("publish_state") == "REVIEW_CANDIDATE"
                and decline_result.get(
                    "paired_quality_review_request_coverage_status"
                )
                == "PASS"
                and decline_result.get("paired_quality_gate_status")
                == "PENDING_EXTERNAL_REVIEW"
                and decline_result.get("humanize_completion_claim_allowed") is False
                and disposition.get("disposition") == "DECLINED"
                and disposition.get("evidence_member_coverage") == "PASS"
                and decline_path.is_file()
            )
            if not all(
                (
                    no_change_does_not_dispose,
                    decline_closure_passes,
                    conflict_rejected,
                    stale_decline_rejected,
                )
            ):
                raise ReplayError("transaction candidate disposition replay gate did not pass")
            pending_run_dir = Path(pending_evidence["run_dir"])
            decline_run_dir = Path(decline_evidence["run_dir"])
            payload = {
                "status": pending_result["status"],
                "delivery_gate_status": pending_result["delivery_gate_status"],
                "exit_code": pending_result["exit_code"],
                "delivery_gate_exit_code": pending_result["exit_code"],
                "academic_correctness": "NOT_EVALUATED",
                "candidate_assembly_status": pending_result[
                    "candidate_assembly_status"
                ],
                "publish_state": pending_result["publish_state"],
                "structural_semantic_mapping": pending_result[
                    "structural_semantic_mapping"
                ],
                "structural_transaction_candidates_total": pending_result[
                    "structural_transaction_candidates_total"
                ],
                "structural_transaction_candidates_executed": pending_result[
                    "structural_transaction_candidates_executed"
                ],
                "structural_transaction_candidates_declined": pending_result[
                    "structural_transaction_candidates_declined"
                ],
                "structural_transaction_candidates_pending": pending_result[
                    "structural_transaction_candidates_pending"
                ],
                "structural_transaction_candidate_coverage_status": pending_result[
                    "structural_transaction_candidate_coverage_status"
                ],
                "structural_transaction_scope_complete": pending_result[
                    "structural_transaction_scope_complete"
                ],
                "candidate_no_change_does_not_dispose": no_change_does_not_dispose,
                "decline_schema": decline_record.get("schema_version"),
                "decline_closure_status": (
                    "PASS" if decline_closure_passes else "FAIL"
                ),
                "decline_candidate_coverage_status": decline_result[
                    "structural_transaction_candidate_coverage_status"
                ],
                "decline_delivery_gate_status": decline_result[
                    "delivery_gate_status"
                ],
                "decline_publish_state": decline_result["publish_state"],
                "decline_paired_quality_review_request_coverage_status": decline_result[
                    "paired_quality_review_request_coverage_status"
                ],
                "decline_paired_quality_gate_status": decline_result[
                    "paired_quality_gate_status"
                ],
                "decline_humanize_completion_claim_allowed": decline_result[
                    "humanize_completion_claim_allowed"
                ],
                "decline_disposition": disposition.get("disposition"),
                "decline_evidence_member_coverage": disposition.get(
                    "evidence_member_coverage"
                ),
                "execution_decline_conflict_rejected": conflict_rejected,
                "stale_decline_rejected": stale_decline_rejected,
                "rendered_exists": (pending_run_dir / "rendered").exists(),
                "rendered_partial_exists": (
                    pending_run_dir / "rendered_partial"
                ).is_dir(),
                "decline_rendered_exists": (
                    decline_run_dir / "rendered"
                ).is_dir(),
                "decline_rendered_review_exists": (
                    decline_run_dir / "rendered_review"
                ).is_dir(),
                "rendered_review_exists": (
                    pending_run_dir / "rendered_review"
                ).exists(),
            }
        else:
            fixture_text = _transaction_fixture_text(input_text)
            result, evidence = _run_transaction_case(fixture_text, temp_root / "primary")
            run_dir = Path(evidence["run_dir"])
            tx_result = evidence["transaction_result"]
            member_ids = [
                str(item["unit_id"]) for item in evidence["bundle"]["unit_bindings"]
            ]
            conflict_rejected = None
            rollback_pass = None
            replay_pass = None
            second_pass_rejected = None
            projection_checks = None
            projection_error = None
            if scenario == "LONG-22":
                conflict_rejected = _transaction_member_conflict_rejected(
                    fixture_text, temp_root / "conflict"
                )
            elif scenario == "LONG-23":
                rollback_pass = _transaction_atomic_rollback_passes(
                    fixture_text, temp_root / "rollback"
                )
            elif scenario == "LONG-24":
                replay_pass = _transaction_replay_is_stable(evidence)
                second_pass_rejected = _second_pass_seed_is_rejected(
                    run_dir, temp_root / "second-pass"
                )
                try:
                    projection_checks = _projection_transaction_checks(
                        temp_root / "projection-check"
                    )
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
                    projection_error = str(error)
            executed_adversarial_checks = [
                item
                for item in (
                    conflict_rejected,
                    rollback_pass,
                    replay_pass,
                    second_pass_rejected,
                    (
                        None
                        if scenario != "LONG-24"
                        else projection_error is None
                        and projection_checks is not None
                        and all(projection_checks.values())
                    ),
                )
                if item is not None
            ]
            adversarial_gate_pass = bool(
                executed_adversarial_checks and all(executed_adversarial_checks)
            )
            payload = {
                "status": result["status"] if adversarial_gate_pass else "FAIL",
                "delivery_gate_status": (
                    result["delivery_gate_status"] if adversarial_gate_pass else "FAIL"
                ),
                "exit_code": result["exit_code"] if adversarial_gate_pass else 1,
                "delivery_gate_exit_code": (
                    result["exit_code"] if adversarial_gate_pass else 1
                ),
                "academic_correctness": "NOT_EVALUATED",
                **_transaction_layer_statuses(evidence),
                "candidate_assembly_status": result["candidate_assembly_status"],
                "publish_state": result["publish_state"],
                "structural_semantic_mapping": result["structural_semantic_mapping"],
                "structural_transaction_status": tx_result.get("status"),
                "structural_transaction_count": result.get("structural_transactions_total"),
                "structural_transaction_member_coverage": (
                    "PASS" if tx_result.get("unit_ids") == member_ids else "FAIL"
                ),
                "structural_transaction_authority_status": tx_result.get(
                    "source_member_claim_status"
                ),
                "structural_transaction_conflict_rejected": (
                    conflict_rejected if conflict_rejected is not None else "NOT_RUN"
                ),
                "structural_transaction_atomicity": tx_result.get("atomic_gate_status"),
                "transaction_review_request_schema": evidence["request"].get(
                    "schema"
                ),
                "rewrite_intent_coverage_status": result.get(
                    "rewrite_intent_coverage_status"
                ),
                "rewrite_intent_units_missing": result.get(
                    "rewrite_intent_units_missing"
                ),
                "structural_transaction_rollback_status": (
                    "PASS"
                    if rollback_pass is True
                    else "FAIL"
                    if rollback_pass is False
                    else "NOT_RUN"
                ),
                "transaction_non_downgrade_status": (
                    "PASS"
                    if result.get("structural_semantic_mapping") == "NOT_EVALUATED"
                    and result.get("delivery_gate_status") == "REVIEW"
                    else "FAIL"
                ),
                "transaction_replay_status": (
                    "PASS"
                    if replay_pass is True
                    else "FAIL"
                    if replay_pass is False
                    else "NOT_RUN"
                ),
                "second_pass_seed_rejected": (
                    second_pass_rejected
                    if second_pass_rejected is not None
                    else "NOT_RUN"
                ),
                "generator_projection_execution_status": (
                    "FAIL"
                    if projection_error is not None
                    else "PASS"
                    if projection_checks is not None
                    else "NOT_RUN"
                ),
                "generator_projection_control_surface": (
                    "ABSENT"
                    if projection_checks is not None
                    and projection_checks["control_surface_absent"]
                    else "PRESENT"
                    if projection_checks is not None
                    else "NOT_RUN"
                ),
                "generator_projection_reproducibility": (
                    "PASS"
                    if projection_checks is not None
                    and projection_checks["reproducible"]
                    else "FAIL"
                    if projection_checks is not None
                    else "NOT_RUN"
                ),
                "generator_projection_transaction_surface": (
                    "PASS"
                    if projection_checks is not None
                    and projection_checks["transaction_surface"]
                    else "FAIL"
                    if projection_checks is not None
                    else "NOT_RUN"
                ),
                "rendered_exists": (run_dir / "rendered").exists(),
                "rendered_review_exists": (run_dir / "rendered_review").is_dir(),
            }
            if not adversarial_gate_pass:
                payload["error"] = projection_error or (
                    "transaction adversarial replay gate did not pass"
                )
        payload.update(
            {
                "evidence_binding_status": "PASS",
                "evidence": {
                    "before_sha256": _sha256(input_raw),
                    "after_sha256": _sha256(output_raw),
                },
            }
        )
        return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def _failure_payload(scenario: str, error: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "FAIL",
        "delivery_gate_status": "FAIL",
        "exit_code": 1,
        "delivery_gate_exit_code": 1,
        "academic_correctness": "NOT_EVALUATED",
        "evidence_binding_status": "FAIL",
        "evidence": {
            "before_sha256": "NOT_RUN",
            "after_sha256": "NOT_RUN",
        },
        "error": str(error),
    }
    if scenario in {"LONG-22", "LONG-23", "LONG-24"}:
        payload.update(
            {
                "hard_invariant_layer_status": "NOT_RUN",
                "speech_act_layer_status": "NOT_RUN",
                "style_signal_layer_status": "NOT_RUN",
                "candidate_assembly_status": "FAIL",
                "publish_state": "NOT_RUN",
                "structural_semantic_mapping": "NOT_EVALUATED",
                "structural_transaction_status": "FAIL",
                "structural_transaction_count": 0,
                "structural_transaction_member_coverage": "NOT_RUN",
                "structural_transaction_authority_status": "NOT_RUN",
                "structural_transaction_conflict_rejected": "NOT_RUN",
                "structural_transaction_atomicity": "NOT_RUN",
                "transaction_review_request_schema": "NOT_RUN",
                "rewrite_intent_coverage_status": "NOT_RUN",
                "rewrite_intent_units_missing": "NOT_RUN",
                "structural_transaction_rollback_status": "NOT_RUN",
                "transaction_non_downgrade_status": "NOT_RUN",
                "transaction_replay_status": "NOT_RUN",
                "second_pass_seed_rejected": "NOT_RUN",
                "generator_projection_execution_status": "NOT_RUN",
                "generator_projection_control_surface": "NOT_RUN",
                "generator_projection_reproducibility": "NOT_RUN",
                "generator_projection_transaction_surface": "NOT_RUN",
                "rendered_exists": False,
                "rendered_review_exists": False,
            }
        )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = replay(args.input, args.output, args.scenario)
        exit_code = int(payload["exit_code"])
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        payload = _failure_payload(args.scenario, error)
        exit_code = 1
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(" ".join(f"{key}={value}" for key, value in payload.items()))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
