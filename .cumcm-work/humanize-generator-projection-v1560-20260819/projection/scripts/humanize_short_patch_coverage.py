#!/usr/bin/env python3
"""Build and replay the mechanically enumerable short PATCH coverage layer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import scan_humanize_chinese as lexical  # noqa: E402


COVERAGE_SCHEMA_V1 = "humanize-short-patch-coverage/v1"
COVERAGE_SCHEMA = "humanize-short-patch-coverage/v2"
COVERAGE_SPEC_FIELDS = {
    "source_kind",
    "lexical_keeps",
    "selected_spans",
    "explicit_conflicts",
}
LEXICAL_KEEP_FIELDS = {"signal_id", "source_text", "start_byte", "reason"}
SELECTED_SPAN_FIELDS = {
    "selection_id",
    "source_text",
    "start_byte",
    "decision",
    "hunk_id",
    "reason",
}
CONFLICT_FIELDS = {
    "conflict_id",
    "rule_code",
    "left_hunk_id",
    "right_hunk_id",
    "reason",
}
SOURCE_KINDS = {"DOCUMENT", "INLINE_TEXT", "INLINE_SELECTION"}
SELECTION_DECISIONS = {"HUNK", "KEEP"}
CONFLICT_RULE_CODES = {
    "OPPOSING_PERMISSION",
    "MUTUALLY_EXCLUSIVE_CONDITION",
    "CONTRADICTORY_CONCLUSION",
    "INCOMPATIBLE_SCOPE",
    "OTHER_DECLARED_CONFLICT",
}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
SIGNAL_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,63}$")
GENERIC_REASONS = {"todo", "待定", "保持原样", "无需修改", "已经自然", "没有问题"}
COVERAGE_FIELDS = {
    "schema_version",
    "source",
    "policy_hashes",
    "declarations",
    "declarations_sha256",
    "inventories",
    "summary",
    "coverage_basis",
    "coverage_limitations",
    "mechanical_coverage_status",
    "coverage_completion_claim_allowed",
    "coverage_claim_scope",
    "semantic_completeness_claim_allowed",
    "humanize_quality_claim_allowed",
    "academic_correctness",
    "coverage_sha256",
}
SOURCE_FIELDS = {
    "sha256",
    "size_bytes",
    "encoding",
    "offset_unit",
    "document_format",
    "scene",
    "scan_scene",
    "source_kind",
}
RESOLVED_KEEP_FIELDS = LEXICAL_KEEP_FIELDS | {
    "end_byte",
    "source_text_sha256",
}
RESOLVED_SELECTION_FIELDS = SELECTED_SPAN_FIELDS | {
    "end_byte",
    "source_text_sha256",
}
INVENTORY_FIELDS = {"lexical_high", "selected_spans", "explicit_conflicts"}
LEXICAL_INVENTORY_FIELDS = {
    "finding_id",
    "signal_id",
    "severity",
    "role",
    "start_byte",
    "end_byte",
    "source_text",
    "source_text_sha256",
    "disposition",
}
DISPOSITION_FIELDS = {"decision", "hunk_id", "reason"}
SELECTION_INVENTORY_FIELDS = RESOLVED_SELECTION_FIELDS | {"disposition"}
CONFLICT_INVENTORY_FIELDS = CONFLICT_FIELDS | {
    "left",
    "right",
    "disposition",
}
HUNK_SPAN_FIELDS = {
    "hunk_id",
    "decision",
    "start_byte",
    "end_byte",
    "source_text_sha256",
}
SUMMARY_FIELDS = {
    "lexical_high_total",
    "lexical_candidate_total",
    "lexical_disposition_counts",
    "selected_spans_total",
    "explicit_conflicts_total",
}
COVERAGE_BASIS = [
    "CURRENT_SCANNER_HIGH_AUDIT_VIEW",
    "CALLER_BOUND_SELECTED_SPANS",
    "CALLER_DECLARED_CONFLICT_PAIRS",
]
COVERAGE_LIMITATIONS = [
    "NO_COMPLETE_NATURAL_LANGUAGE_SEMANTIC_DISCOVERY",
    "CONFLICT_INVENTORY_IS_CALLER_DECLARED_ONLY",
    "KEEP_REASONS_ARE_NOT_EXTERNAL_QUALITY_CLEARANCE",
    "SELF_CONSISTENCY_ONLY_WITHOUT_EXTERNAL_REQUEST_ANCHOR",
]


class CoverageError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CoverageError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CoverageError(f"{label} must be a non-empty string")
    return value


def _specific_reason(value: Any, label: str) -> str:
    reason = _required_string(value, label).strip()
    normalized = re.sub(r"[\s。！？!?.,，;；:：]+$", "", reason).strip().casefold()
    if normalized in GENERIC_REASONS:
        raise CoverageError(f"{label} is generic or unfinished")
    return reason


def _identifier(value: Any, label: str, *, signal: bool = False) -> str:
    identifier = _required_string(value, label)
    pattern = SIGNAL_RE if signal else ID_RE
    if not pattern.fullmatch(identifier):
        raise CoverageError(f"{label} is invalid")
    return identifier


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CoverageError(f"{label} must be an integer >= 0")
    return value


def _locate(source: bytes, text: str, start_byte: Any, label: str) -> tuple[int, int]:
    needle = _required_string(text, f"{label}.source_text").encode("utf-8")
    if start_byte is None:
        positions: list[int] = []
        cursor = 0
        while True:
            found = source.find(needle, cursor)
            if found < 0:
                break
            positions.append(found)
            cursor = found + 1
        if len(positions) != 1:
            raise CoverageError(
                f"{label}.source_text is missing or ambiguous; "
                f"candidate_start_bytes={positions}"
            )
        start = positions[0]
    else:
        start = _integer(start_byte, f"{label}.start_byte")
        if source[start : start + len(needle)] != needle:
            raise CoverageError(f"{label}.start_byte does not match source_text")
    return start, start + len(needle)


def _char_to_byte_offsets(text: str, offsets: set[int]) -> dict[int, int]:
    result: dict[int, int] = {}
    byte_offset = 0
    for index, character in enumerate(text):
        if index in offsets:
            result[index] = byte_offset
        byte_offset += len(character.encode("utf-8"))
    if len(text) in offsets:
        result[len(text)] = byte_offset
    if set(result) != offsets:
        raise CoverageError("scanner returned an invalid character offset")
    return result


def current_policy_hashes() -> dict[str, str]:
    runtime = {
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "python_version": list(sys.version_info[:3]),
        "unicode_version": unicodedata.unidata_version,
        "os_name": os.name,
    }
    return {
        "coverage_builder_sha256": _sha256(Path(__file__).resolve().read_bytes()),
        "scanner_sha256": _sha256(Path(lexical.__file__).resolve().read_bytes()),
        "lexicon_sha256": _sha256(Path(lexical.DEFAULT_LEXICON).resolve().read_bytes()),
        "runtime_contract_sha256": _sha256(_canonical_json(runtime)),
    }


def _normalized_declarations(source: bytes, spec: Mapping[str, Any]) -> dict[str, Any]:
    _exact_fields(spec, COVERAGE_SPEC_FIELDS, "coverage spec")
    source_kind = _required_string(spec.get("source_kind"), "coverage.source_kind")
    if source_kind not in SOURCE_KINDS:
        raise CoverageError("coverage.source_kind is invalid")

    keeps_raw = spec.get("lexical_keeps")
    if not isinstance(keeps_raw, list):
        raise CoverageError("coverage.lexical_keeps must be an array")
    keeps: list[dict[str, Any]] = []
    keep_keys: set[tuple[str, int, int]] = set()
    for index, item in enumerate(keeps_raw):
        label = f"coverage.lexical_keeps[{index}]"
        if not isinstance(item, dict):
            raise CoverageError(f"{label} must be an object")
        _exact_fields(item, LEXICAL_KEEP_FIELDS, label)
        signal_id = _identifier(item.get("signal_id"), f"{label}.signal_id", signal=True)
        text = _required_string(item.get("source_text"), f"{label}.source_text")
        start, end = _locate(source, text, item.get("start_byte"), label)
        key = (signal_id, start, end)
        if key in keep_keys:
            raise CoverageError("coverage.lexical_keeps contains a duplicate anchor")
        keep_keys.add(key)
        keeps.append(
            {
                "signal_id": signal_id,
                "source_text": text,
                "start_byte": start,
                "end_byte": end,
                "source_text_sha256": _sha256(source[start:end]),
                "reason": _specific_reason(item.get("reason"), f"{label}.reason"),
            }
        )

    selections_raw = spec.get("selected_spans")
    if not isinstance(selections_raw, list):
        raise CoverageError("coverage.selected_spans must be an array")
    selections: list[dict[str, Any]] = []
    selection_ids: set[str] = set()
    selection_spans: set[tuple[int, int]] = set()
    for index, item in enumerate(selections_raw):
        label = f"coverage.selected_spans[{index}]"
        if not isinstance(item, dict):
            raise CoverageError(f"{label} must be an object")
        _exact_fields(item, SELECTED_SPAN_FIELDS, label)
        selection_id = _identifier(item.get("selection_id"), f"{label}.selection_id")
        selection_key = selection_id.casefold()
        if selection_key in selection_ids:
            raise CoverageError("coverage.selected_spans contains a duplicate selection_id")
        selection_ids.add(selection_key)
        text = _required_string(item.get("source_text"), f"{label}.source_text")
        start, end = _locate(source, text, item.get("start_byte"), label)
        if (start, end) in selection_spans:
            raise CoverageError("coverage.selected_spans contains a duplicate span")
        selection_spans.add((start, end))
        decision = _required_string(item.get("decision"), f"{label}.decision")
        if decision not in SELECTION_DECISIONS:
            raise CoverageError(f"{label}.decision is invalid")
        hunk_id = item.get("hunk_id")
        if decision == "HUNK":
            hunk_id = _identifier(hunk_id, f"{label}.hunk_id")
        elif hunk_id is not None:
            raise CoverageError(f"{label}.hunk_id must be null for KEEP")
        selections.append(
            {
                "selection_id": selection_id,
                "source_text": text,
                "start_byte": start,
                "end_byte": end,
                "source_text_sha256": _sha256(source[start:end]),
                "decision": decision,
                "hunk_id": hunk_id,
                "reason": _specific_reason(item.get("reason"), f"{label}.reason"),
            }
        )
    if source_kind == "INLINE_SELECTION" and not selections:
        raise CoverageError("BOUND_SELECTION_REQUIRED")

    conflicts_raw = spec.get("explicit_conflicts")
    if not isinstance(conflicts_raw, list):
        raise CoverageError("coverage.explicit_conflicts must be an array")
    conflicts: list[dict[str, Any]] = []
    conflict_ids: set[str] = set()
    conflict_members: set[str] = set()
    for index, item in enumerate(conflicts_raw):
        label = f"coverage.explicit_conflicts[{index}]"
        if not isinstance(item, dict):
            raise CoverageError(f"{label} must be an object")
        _exact_fields(item, CONFLICT_FIELDS, label)
        conflict_id = _identifier(item.get("conflict_id"), f"{label}.conflict_id")
        conflict_key = conflict_id.casefold()
        if conflict_key in conflict_ids:
            raise CoverageError("coverage.explicit_conflicts contains a duplicate conflict_id")
        conflict_ids.add(conflict_key)
        left = _identifier(item.get("left_hunk_id"), f"{label}.left_hunk_id")
        right = _identifier(item.get("right_hunk_id"), f"{label}.right_hunk_id")
        left_key = left.casefold()
        right_key = right.casefold()
        if (
            left_key == right_key
            or left_key in conflict_members
            or right_key in conflict_members
        ):
            raise CoverageError("explicit conflict members must be distinct and non-reused")
        conflict_members.update((left_key, right_key))
        rule_code = _identifier(
            item.get("rule_code"), f"{label}.rule_code", signal=True
        )
        if rule_code not in CONFLICT_RULE_CODES:
            raise CoverageError(f"{label}.rule_code is invalid")
        conflicts.append(
            {
                "conflict_id": conflict_id,
                "rule_code": rule_code,
                "left_hunk_id": left,
                "right_hunk_id": right,
                "reason": _specific_reason(item.get("reason"), f"{label}.reason"),
            }
        )
    return {
        "source_kind": source_kind,
        "lexical_keeps": keeps,
        "selected_spans": selections,
        "explicit_conflicts": conflicts,
    }


def _resolved_declarations(spec: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "source_kind",
        "lexical_keeps",
        "selected_spans",
        "explicit_conflicts",
    }
    _exact_fields(spec, expected, "coverage declarations")
    for index, item in enumerate(spec.get("lexical_keeps", [])):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage declarations.lexical_keeps[{index}] must be an object")
        _exact_fields(item, RESOLVED_KEEP_FIELDS, f"coverage declarations.lexical_keeps[{index}]")
    for index, item in enumerate(spec.get("selected_spans", [])):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage declarations.selected_spans[{index}] must be an object")
        _exact_fields(item, RESOLVED_SELECTION_FIELDS, f"coverage declarations.selected_spans[{index}]")
    for index, item in enumerate(spec.get("explicit_conflicts", [])):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage declarations.explicit_conflicts[{index}] must be an object")
        _exact_fields(item, CONFLICT_FIELDS, f"coverage declarations.explicit_conflicts[{index}]")
    # Reuse the normalizer after converting resolved anchors back to its input view.
    raw = {
        "source_kind": spec["source_kind"],
        "lexical_keeps": [
            {
                "signal_id": item["signal_id"],
                "source_text": item["source_text"],
                "start_byte": item["start_byte"],
                "reason": item["reason"],
            }
            for item in spec["lexical_keeps"]
        ],
        "selected_spans": [
            {
                "selection_id": item["selection_id"],
                "source_text": item["source_text"],
                "start_byte": item["start_byte"],
                "decision": item["decision"],
                "hunk_id": item["hunk_id"],
                "reason": item["reason"],
            }
            for item in spec["selected_spans"]
        ],
        "explicit_conflicts": [dict(item) for item in spec["explicit_conflicts"]],
    }
    return raw


def _hunk_span(hunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hunk_id": hunk["hunk_id"],
        "decision": hunk["decision"],
        "start_byte": hunk["start_byte"],
        "end_byte": hunk["end_byte"],
        "source_text_sha256": hunk["source_text_sha256"],
    }


def scan_high_findings(source: bytes, *, document_format: str) -> list[dict[str, Any]]:
    """Return the exact AUTO high inventory shared by authoring and coverage."""
    if document_format not in {"markdown", "tex"}:
        raise CoverageError("coverage document_format is invalid")
    try:
        text = source.decode("utf-8")
    except UnicodeError as error:
        raise CoverageError("coverage source is not strict UTF-8") from error
    scan_file = "source.tex" if document_format == "tex" else "source.md"
    raw_findings = [
        item
        for item in lexical.scan_text_with_offsets(
            text,
            file=scan_file,
            scene="AUTO",
            include_protected=True,
            include_excluded=True,
        )
        if item["severity"] == "high"
    ]
    offsets = {
        offset
        for item in raw_findings
        for offset in (int(item["start_char"]), int(item["end_char"]))
    }
    byte_offsets = _char_to_byte_offsets(text, offsets)
    findings: list[dict[str, Any]] = []
    for item in raw_findings:
        start = byte_offsets[int(item["start_char"])]
        end = byte_offsets[int(item["end_char"])]
        role = (
            "PROTECTED"
            if item["protected"]
            else "EXCLUDED"
            if item["excluded"]
            else "CANDIDATE"
        )
        anchor = {
            "signal_id": item["signal_id"],
            "start_byte": start,
            "end_byte": end,
            "source_text_sha256": _sha256(source[start:end]),
            "role": role,
        }
        findings.append(
            {
                "finding_id": "LF-" + _sha256(_canonical_json(anchor))[:24],
                "signal_id": item["signal_id"],
                "severity": "high",
                "role": role,
                "start_byte": start,
                "end_byte": end,
                "source_text": source[start:end].decode("utf-8"),
                "source_text_sha256": _sha256(source[start:end]),
                "automatic_reason": (
                    item["protection"]
                    if role == "PROTECTED"
                    else item["exclusion"]
                    if role == "EXCLUDED"
                    else None
                ),
            }
        )
    return findings


def build_coverage(
    source: bytes,
    *,
    scene: str,
    document_format: str,
    hunks: Sequence[Mapping[str, Any]],
    coverage_spec: Mapping[str, Any],
    resolved_spec: bool = False,
) -> dict[str, Any]:
    declarations_input = (
        _resolved_declarations(coverage_spec) if resolved_spec else coverage_spec
    )
    declarations = _normalized_declarations(source, declarations_input)
    hunk_by_id = {str(item["hunk_id"]): item for item in hunks}

    findings = scan_high_findings(source, document_format=document_format)
    keep_by_key = {
        (item["signal_id"], item["start_byte"], item["end_byte"]): item
        for item in declarations["lexical_keeps"]
    }
    used_keeps: set[tuple[str, int, int]] = set()
    lexical_inventory: list[dict[str, Any]] = []
    uncovered: list[str] = []
    for finding in findings:
        start = int(finding["start_byte"])
        end = int(finding["end_byte"])
        role = str(finding["role"])
        if role == "PROTECTED":
            if any(
                int(hunk["start_byte"]) < end and int(hunk["end_byte"]) > start
                for hunk in hunks
            ):
                raise CoverageError("NON_EDITABLE_HIGH_OVERLAPS_HUNK")
            disposition = {
                "decision": "PROTECTED",
                "hunk_id": None,
                "reason": finding["automatic_reason"],
            }
        elif role == "EXCLUDED":
            if any(
                int(hunk["start_byte"]) < end and int(hunk["end_byte"]) > start
                for hunk in hunks
            ):
                raise CoverageError("NON_EDITABLE_HIGH_OVERLAPS_HUNK")
            disposition = {
                "decision": "EXCLUDED",
                "hunk_id": None,
                "reason": finding["automatic_reason"],
            }
        else:
            covering = [
                hunk
                for hunk in hunks
                if int(hunk["start_byte"]) <= start and int(hunk["end_byte"]) >= end
            ]
            if len(covering) > 1:
                raise CoverageError("lexical high finding maps to multiple hunks")
            if covering:
                hunk = covering[0]
                disposition = {
                    "decision": hunk["decision"],
                    "hunk_id": hunk["hunk_id"],
                    "reason": hunk["reason"],
                }
            else:
                keep_key = (finding["signal_id"], start, end)
                keep = keep_by_key.get(keep_key)
                if keep is None:
                    uncovered.append(f"{finding['signal_id']}@{start}:{end}")
                    disposition = None
                else:
                    used_keeps.add(keep_key)
                    disposition = {
                        "decision": "KEEP",
                        "hunk_id": None,
                        "reason": keep["reason"],
                    }
        lexical_inventory.append(
            {
                "finding_id": finding["finding_id"],
                "signal_id": finding["signal_id"],
                "severity": "high",
                "role": role,
                "start_byte": start,
                "end_byte": end,
                "source_text": finding["source_text"],
                "source_text_sha256": finding["source_text_sha256"],
                "disposition": disposition,
            }
        )
    unknown_keeps = set(keep_by_key) - used_keeps
    if unknown_keeps:
        raise CoverageError("UNKNOWN_LEXICAL_KEEP")
    if uncovered:
        raise CoverageError("UNCOVERED_LEXICAL_HIGH: " + ",".join(uncovered))

    selection_inventory: list[dict[str, Any]] = []
    for selection in declarations["selected_spans"]:
        hunk_id = selection["hunk_id"]
        if selection["decision"] == "HUNK":
            hunk = hunk_by_id.get(str(hunk_id))
            if hunk is None or (
                int(hunk["start_byte"]) != selection["start_byte"]
                or int(hunk["end_byte"]) != selection["end_byte"]
            ):
                raise CoverageError("SELECTION_HUNK_MISMATCH")
            disposition = {
                "decision": hunk["decision"],
                "hunk_id": hunk["hunk_id"],
                "reason": selection["reason"],
            }
        else:
            if any(
                int(hunk["start_byte"]) < selection["end_byte"]
                and int(hunk["end_byte"]) > selection["start_byte"]
                for hunk in hunks
            ):
                raise CoverageError("SELECTION_KEEP_OVERLAPS_HUNK")
            disposition = {
                "decision": "KEEP",
                "hunk_id": None,
                "reason": selection["reason"],
            }
        selection_inventory.append({**selection, "disposition": disposition})

    conflict_inventory: list[dict[str, Any]] = []
    for conflict in declarations["explicit_conflicts"]:
        left = hunk_by_id.get(conflict["left_hunk_id"])
        right = hunk_by_id.get(conflict["right_hunk_id"])
        if left is None or right is None or left["decision"] != "UNRESOLVED" or right["decision"] != "UNRESOLVED":
            raise CoverageError("CONFLICT_REQUIRES_UNRESOLVED")
        conflict_inventory.append(
            {
                **conflict,
                "left": _hunk_span(left),
                "right": _hunk_span(right),
                "disposition": "UNRESOLVED_PAIR",
            }
        )

    counts = Counter(
        str(item["disposition"]["decision"]) for item in lexical_inventory
    )
    payload: dict[str, Any] = {
        "schema_version": COVERAGE_SCHEMA,
        "source": {
            "sha256": _sha256(source),
            "size_bytes": len(source),
            "encoding": "utf-8",
            "offset_unit": "UTF8_BYTES",
            "document_format": document_format,
            "scene": scene,
            "scan_scene": "AUTO",
            "source_kind": declarations["source_kind"],
        },
        "policy_hashes": current_policy_hashes(),
        "declarations": declarations,
        "declarations_sha256": _sha256(_canonical_json(declarations)),
        "inventories": {
            "lexical_high": lexical_inventory,
            "selected_spans": selection_inventory,
            "explicit_conflicts": conflict_inventory,
        },
        "summary": {
            "lexical_high_total": len(lexical_inventory),
            "lexical_candidate_total": sum(item["role"] == "CANDIDATE" for item in lexical_inventory),
            "lexical_disposition_counts": dict(sorted(counts.items())),
            "selected_spans_total": len(selection_inventory),
            "explicit_conflicts_total": len(conflict_inventory),
        },
        "coverage_basis": list(COVERAGE_BASIS),
        "coverage_limitations": list(COVERAGE_LIMITATIONS),
        "mechanical_coverage_status": "PASS",
        "coverage_completion_claim_allowed": True,
        "coverage_claim_scope": "ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY",
        "semantic_completeness_claim_allowed": False,
        "humanize_quality_claim_allowed": False,
        "academic_correctness": "NOT_EVALUATED",
        "coverage_sha256": "",
    }
    unsigned = dict(payload)
    unsigned.pop("coverage_sha256")
    payload["coverage_sha256"] = _sha256(_canonical_json(unsigned))
    return payload


def validate_record_integrity(
    source: bytes,
    recorded: Mapping[str, Any],
    *,
    hunks: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(recorded, dict):
        raise CoverageError("coverage record must be an object")
    _exact_fields(recorded, COVERAGE_FIELDS, "coverage record")
    schema = recorded.get("schema_version")
    if schema not in {COVERAGE_SCHEMA_V1, COVERAGE_SCHEMA}:
        raise CoverageError("coverage record schema_version is invalid")
    unsigned = dict(recorded)
    unsigned.pop("coverage_sha256")
    if recorded.get("coverage_sha256") != _sha256(_canonical_json(unsigned)):
        raise CoverageError("coverage_sha256 mismatch")

    source_record = recorded.get("source")
    if not isinstance(source_record, dict):
        raise CoverageError("coverage source must be an object")
    _exact_fields(
        source_record,
        SOURCE_FIELDS if schema == COVERAGE_SCHEMA else SOURCE_FIELDS - {"scan_scene"},
        "coverage source",
    )
    if source_record.get("sha256") != _sha256(source):
        raise CoverageError("coverage source sha256 mismatch")
    if source_record.get("size_bytes") != len(source):
        raise CoverageError("coverage source size mismatch")
    if source_record.get("encoding") != "utf-8" or source_record.get("offset_unit") != "UTF8_BYTES":
        raise CoverageError("coverage source encoding contract is invalid")
    if source_record.get("document_format") not in {"markdown", "tex"}:
        raise CoverageError("coverage source document_format is invalid")
    if schema == COVERAGE_SCHEMA and source_record.get("scan_scene") != "AUTO":
        raise CoverageError("coverage source scan_scene is invalid")
    if source_record.get("source_kind") not in SOURCE_KINDS:
        raise CoverageError("coverage source_kind is invalid")

    policy = recorded.get("policy_hashes")
    if not isinstance(policy, dict) or not policy:
        raise CoverageError("coverage policy_hashes fields are invalid")
    if any(
        not isinstance(key, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]*_sha256", key)
        or not isinstance(value, str)
        or not re.fullmatch(r"[0-9a-f]{64}", value)
        for key, value in policy.items()
    ):
        raise CoverageError("coverage policy_hashes values are invalid")

    declarations = recorded.get("declarations")
    if not isinstance(declarations, dict):
        raise CoverageError("coverage declarations must be an object")
    normalized = _normalized_declarations(source, _resolved_declarations(declarations))
    if normalized != declarations:
        raise CoverageError("coverage declarations are not canonical")
    if recorded.get("declarations_sha256") != _sha256(_canonical_json(declarations)):
        raise CoverageError("coverage declarations_sha256 mismatch")
    hunk_by_id = {str(item.get("hunk_id")): item for item in (hunks or [])}

    inventories = recorded.get("inventories")
    if not isinstance(inventories, dict):
        raise CoverageError("coverage inventories must be an object")
    _exact_fields(inventories, INVENTORY_FIELDS, "coverage inventories")
    for name in sorted(INVENTORY_FIELDS):
        if not isinstance(inventories.get(name), list):
            raise CoverageError(f"coverage inventories.{name} must be an array")
    for index, item in enumerate(inventories["lexical_high"]):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage lexical_high[{index}] must be an object")
        _exact_fields(item, LEXICAL_INVENTORY_FIELDS, f"coverage lexical_high[{index}]")
        role = item.get("role")
        if not isinstance(role, str) or role not in {
            "CANDIDATE",
            "PROTECTED",
            "EXCLUDED",
        }:
            raise CoverageError("coverage lexical role is invalid")
        if item.get("severity") != "high":
            raise CoverageError("coverage lexical severity is invalid")
        if not isinstance(item.get("finding_id"), str) or not re.fullmatch(
            r"LF-[0-9a-f]{24}", item["finding_id"]
        ):
            raise CoverageError("coverage lexical finding_id is invalid")
        if not isinstance(item.get("signal_id"), str) or not SIGNAL_RE.fullmatch(
            item["signal_id"]
        ):
            raise CoverageError("coverage lexical signal_id is invalid")
        start = item.get("start_byte")
        end = item.get("end_byte")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source)
        ):
            raise CoverageError("coverage lexical span is invalid")
        raw_span = source[start:end]
        try:
            span_text = raw_span.decode("utf-8")
        except UnicodeError as error:
            raise CoverageError("coverage lexical span is not UTF-8") from error
        if item.get("source_text") != span_text or item.get("source_text_sha256") != _sha256(raw_span):
            raise CoverageError("coverage lexical source binding mismatch")
        disposition = item.get("disposition")
        if not isinstance(disposition, dict):
            raise CoverageError(f"coverage lexical_high[{index}].disposition must be an object")
        _exact_fields(disposition, DISPOSITION_FIELDS, f"coverage lexical_high[{index}].disposition")
        decision = disposition.get("decision")
        hunk_id = disposition.get("hunk_id")
        if not isinstance(disposition.get("reason"), str) or not disposition["reason"]:
            raise CoverageError("coverage lexical disposition reason is invalid")
        if role == "PROTECTED" and (decision != "PROTECTED" or hunk_id is not None):
            raise CoverageError("coverage protected disposition is invalid")
        if role == "EXCLUDED" and (decision != "EXCLUDED" or hunk_id is not None):
            raise CoverageError("coverage excluded disposition is invalid")
        if role == "CANDIDATE" and decision not in {
            "KEEP",
            "DELETE_STYLE_SHELL",
            "REWRITE",
            "UNRESOLVED",
        }:
            raise CoverageError("coverage candidate disposition is invalid")
        if role == "CANDIDATE" and decision == "KEEP" and hunk_id is not None:
            raise CoverageError("coverage candidate KEEP hunk_id is invalid")
        if role == "CANDIDATE" and decision != "KEEP":
            if not isinstance(hunk_id, str) or not ID_RE.fullmatch(hunk_id):
                raise CoverageError("coverage candidate disposition hunk_id is invalid")
            if hunk_by_id:
                hunk = hunk_by_id.get(hunk_id)
                if (
                    hunk is None
                    or hunk.get("decision") != decision
                    or int(hunk["start_byte"]) > start
                    or int(hunk["end_byte"]) < end
                ):
                    raise CoverageError("coverage candidate disposition does not match hunk")
    selection_by_id = {
        item["selection_id"]: item for item in declarations["selected_spans"]
    }
    for index, item in enumerate(inventories["selected_spans"]):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage selected_spans[{index}] must be an object")
        _exact_fields(item, SELECTION_INVENTORY_FIELDS, f"coverage selected_spans[{index}]")
        disposition = item.get("disposition")
        if not isinstance(disposition, dict):
            raise CoverageError(f"coverage selected_spans[{index}].disposition must be an object")
        _exact_fields(disposition, DISPOSITION_FIELDS, f"coverage selected_spans[{index}].disposition")
        selection_id = item.get("selection_id")
        declared = selection_by_id.get(selection_id)
        inventory_declaration = {
            key: value for key, value in item.items() if key != "disposition"
        }
        if declared is None or inventory_declaration != declared:
            raise CoverageError("coverage selected inventory does not match declarations")
        if declared["decision"] == "KEEP":
            expected_disposition = {
                "decision": "KEEP",
                "hunk_id": None,
                "reason": declared["reason"],
            }
        else:
            hunk = hunk_by_id.get(str(declared["hunk_id"])) if hunk_by_id else None
            expected_disposition = {
                "decision": hunk["decision"] if hunk is not None else disposition.get("decision"),
                "hunk_id": declared["hunk_id"],
                "reason": declared["reason"],
            }
        if disposition != expected_disposition:
            raise CoverageError("coverage selected inventory does not match declarations")
    for index, item in enumerate(inventories["explicit_conflicts"]):
        if not isinstance(item, dict):
            raise CoverageError(f"coverage explicit_conflicts[{index}] must be an object")
        _exact_fields(item, CONFLICT_INVENTORY_FIELDS, f"coverage explicit_conflicts[{index}]")
        for side in ("left", "right"):
            if not isinstance(item.get(side), dict):
                raise CoverageError(f"coverage explicit_conflicts[{index}].{side} must be an object")
            _exact_fields(item[side], HUNK_SPAN_FIELDS, f"coverage explicit_conflicts[{index}].{side}")

    summary = recorded.get("summary")
    if not isinstance(summary, dict):
        raise CoverageError("coverage summary must be an object")
    _exact_fields(summary, SUMMARY_FIELDS, "coverage summary")
    if summary.get("lexical_high_total") != len(inventories["lexical_high"]):
        raise CoverageError("coverage lexical_high_total mismatch")
    if summary.get("selected_spans_total") != len(inventories["selected_spans"]):
        raise CoverageError("coverage selected_spans_total mismatch")
    if summary.get("explicit_conflicts_total") != len(inventories["explicit_conflicts"]):
        raise CoverageError("coverage explicit_conflicts_total mismatch")
    expected_candidate_total = sum(
        item.get("role") == "CANDIDATE" for item in inventories["lexical_high"]
    )
    if summary.get("lexical_candidate_total") != expected_candidate_total:
        raise CoverageError("coverage lexical_candidate_total mismatch")
    expected_dispositions = dict(
        sorted(
            Counter(
                str(item["disposition"].get("decision"))
                for item in inventories["lexical_high"]
            ).items()
        )
    )
    if summary.get("lexical_disposition_counts") != expected_dispositions:
        raise CoverageError("coverage lexical_disposition_counts mismatch")
    if recorded.get("coverage_basis") != COVERAGE_BASIS:
        raise CoverageError("coverage basis is invalid")
    if recorded.get("coverage_limitations") != COVERAGE_LIMITATIONS:
        raise CoverageError("coverage limitations are invalid")
    if (
        recorded.get("mechanical_coverage_status") != "PASS"
        or recorded.get("coverage_completion_claim_allowed") is not True
        or recorded.get("coverage_claim_scope") != "ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY"
        or recorded.get("semantic_completeness_claim_allowed") is not False
        or recorded.get("humanize_quality_claim_allowed") is not False
        or recorded.get("academic_correctness") != "NOT_EVALUATED"
    ):
        raise CoverageError("coverage claim fields are invalid")
    return dict(recorded)


def replay_coverage(
    source: bytes,
    *,
    hunks: Sequence[Mapping[str, Any]],
    recorded: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    validate_record_integrity(source, recorded, hunks=hunks)
    policy = recorded.get("policy_hashes")
    if not isinstance(policy, dict) or policy != current_policy_hashes():
        return None, "DRIFT"
    source_record = recorded.get("source")
    declarations = recorded.get("declarations")
    if not isinstance(source_record, dict) or not isinstance(declarations, dict):
        raise CoverageError("coverage record is missing source or declarations")
    replayed = build_coverage(
        source,
        scene=str(source_record.get("scene", "")),
        document_format=str(source_record.get("document_format", "")),
        hunks=hunks,
        coverage_spec=declarations,
        resolved_spec=True,
    )
    if replayed != recorded:
        raise CoverageError("COVERAGE_REPLAY_MISMATCH")
    return replayed, "PASS"
