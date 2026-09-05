#!/usr/bin/env python3
"""Load the detector-only negative-guard registry used by production gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_REGISTRY = SKILL_DIR / "references" / "corpus-action-sources.json"
DEFAULT_SOURCE_TRUST_POLICY = SKILL_DIR / "references" / "source-provenance-trust.json"
REGISTRY_SCHEMA = "humanize-negative-guard-registry/v2"
REGISTRY_ID = "humanize-academic-chinese/corpus-negative-guards/v2"
SOURCE_TRUST_SCHEMA = "humanize-source-provenance-trust/v1"
LOADER_VERSION = "2.0.0"
VALID_SCENES = {"ALL", "COURSE", "GENERAL", "MODELING", "RESEARCH", "REPORT"}
GUARD_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{2,127}$")
GROUP_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
EXPECTED_ORIGIN_DECISIONS = {
    "HUMAN_CONFIRMED": {
        "production_positive": False,
        "assurance": "PROVISIONAL",
        "allowed_uses": ["AUDIT", "EXPERIMENTAL_POSITIVE_REVIEW"],
        "reason_code": "EXTERNAL_ATTESTATION_REQUIRED",
    },
    "MODEL_GENERATED": {
        "production_positive": False,
        "assurance": "NEGATIVE_ONLY",
        "allowed_uses": ["AUDIT", "NEGATIVE_GUARD"],
        "reason_code": "MODEL_TEXT_NEGATIVE_ONLY",
    },
    "MODEL_ORIGIN_UNRESOLVED": {
        "production_positive": False,
        "assurance": "NEGATIVE_ONLY",
        "allowed_uses": ["AUDIT", "NEGATIVE_GUARD"],
        "reason_code": "MODEL_ORIGIN_UNRESOLVED_NEGATIVE_ONLY",
    },
    "OCR_INHERITED": {
        "production_positive": False,
        "assurance": "NEGATIVE_ONLY",
        "allowed_uses": ["AUDIT"],
        "reason_code": "OCR_PROVENANCE_NOT_AUTHOR_VOICE",
    },
    "THIRD_PARTY": {
        "production_positive": False,
        "assurance": "NEGATIVE_ONLY",
        "allowed_uses": ["AUDIT"],
        "reason_code": "THIRD_PARTY_NOT_AUTHOR_VOICE",
    },
    "UNKNOWN": {
        "production_positive": False,
        "assurance": "PROVISIONAL",
        "allowed_uses": ["AUDIT", "EXPERIMENTAL_POSITIVE_REVIEW"],
        "reason_code": "ORIGIN_UNKNOWN",
    },
}
EXPECTED_PRODUCTION_ATTESTATION = {
    "enabled": False,
    "external_verifier_required": True,
    "accepted_schemes": [],
    "local_claims_are_identity_proof": False,
}


class NegativeGuardRegistryError(ValueError):
    """Raised when detector-only registry data is not structurally trustworthy."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NegativeGuardRegistryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                NegativeGuardRegistryError(
                    f"non-finite JSON number in {label}: {value}"
                )
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise NegativeGuardRegistryError(
            f"{label} is not strict UTF-8 JSON: {error}"
        ) from error


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise NegativeGuardRegistryError(
            f"{label} fields drifted; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise NegativeGuardRegistryError(f"{label} must be a non-empty trimmed string")
    return value


def _compile_nonempty_pattern(pattern: str, label: str) -> None:
    try:
        compiled = re.compile(pattern)
    except re.error as error:
        raise NegativeGuardRegistryError(f"{label} is invalid: {error}") from error
    if compiled.search("") is not None:
        raise NegativeGuardRegistryError(f"{label} must not match empty text")


def _normalize_regex_groups_detector(
    value: Mapping[str, Any], guard_id: str, *, legacy: bool
) -> dict[str, Any]:
    expected = {"minimum_groups", "pattern_groups"}
    if not legacy:
        expected.add("type")
    _exact_keys(value, expected, f"guard {guard_id}.detector")
    if not isinstance(value, dict):
        raise NegativeGuardRegistryError(f"guard {guard_id}.detector must be an object")
    groups = value.get("pattern_groups")
    minimum_groups = value.get("minimum_groups")
    if not isinstance(groups, list) or not groups:
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.pattern_groups must be non-empty"
        )
    if (
        not isinstance(minimum_groups, int)
        or isinstance(minimum_groups, bool)
        or not 1 <= minimum_groups <= len(groups)
    ):
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.minimum_groups is invalid"
        )
    normalized_groups: list[dict[str, Any]] = []
    seen_group_ids: set[str] = set()
    for position, raw_group in enumerate(groups, start=1):
        if not isinstance(raw_group, dict):
            raise NegativeGuardRegistryError(
                f"guard {guard_id} pattern_groups[{position}] must be an object"
            )
        _exact_keys(
            raw_group,
            {"id", "regex", "minimum_occurrences"},
            f"guard {guard_id} pattern_groups[{position}]",
        )
        group_id = _require_text(raw_group.get("id"), f"guard {guard_id} group id")
        if not GROUP_ID_RE.fullmatch(group_id):
            raise NegativeGuardRegistryError(
                f"guard {guard_id} has invalid detector group id: {group_id}"
            )
        if group_id in seen_group_ids:
            raise NegativeGuardRegistryError(
                f"guard {guard_id} repeats detector group id: {group_id}"
            )
        seen_group_ids.add(group_id)
        pattern = _require_text(
            raw_group.get("regex"), f"guard {guard_id} group {group_id}.regex"
        )
        if len(pattern) > 4096:
            raise NegativeGuardRegistryError(
                f"guard {guard_id} group {group_id}.regex is too long"
            )
        _compile_nonempty_pattern(
            pattern, f"guard {guard_id} group {group_id}.regex"
        )
        minimum_occurrences = raw_group.get("minimum_occurrences")
        if (
            not isinstance(minimum_occurrences, int)
            or isinstance(minimum_occurrences, bool)
            or minimum_occurrences < 1
            or minimum_occurrences > 1000
        ):
            raise NegativeGuardRegistryError(
                f"guard {guard_id} group {group_id}.minimum_occurrences is invalid"
            )
        normalized_groups.append(
            {
                "id": group_id,
                "regex": pattern,
                "minimum_occurrences": minimum_occurrences,
            }
        )
    return {
        "type": "regex_groups/v1",
        "minimum_groups": minimum_groups,
        "pattern_groups": normalized_groups,
    }


def _bounded_int(
    value: Any, label: str, *, minimum: int, maximum: int
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        raise NegativeGuardRegistryError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _normalize_structured_repeated_list_detector(
    value: Mapping[str, Any], guard_id: str
) -> dict[str, Any]:
    _exact_keys(
        value,
        {"type", "block_role", "thresholds", "shared_anchor"},
        f"guard {guard_id}.detector",
    )
    block_role = value.get("block_role")
    thresholds = value.get("thresholds")
    shared_anchor = value.get("shared_anchor")
    if not isinstance(block_role, dict):
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.block_role must be an object"
        )
    if not isinstance(thresholds, dict):
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.thresholds must be an object"
        )
    if not isinstance(shared_anchor, dict):
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.shared_anchor must be an object"
        )
    _exact_keys(
        block_role,
        {"heading_leaf_regex"},
        f"guard {guard_id}.detector.block_role",
    )
    _exact_keys(
        thresholds,
        {"minimum_blocks", "minimum_items_per_block"},
        f"guard {guard_id}.detector.thresholds",
    )
    _exact_keys(
        shared_anchor,
        {
            "mode",
            "minimum_han_chars",
            "maximum_han_chars",
            "minimum_block_coverage",
        },
        f"guard {guard_id}.detector.shared_anchor",
    )
    heading_pattern = _require_text(
        block_role.get("heading_leaf_regex"),
        f"guard {guard_id}.detector.block_role.heading_leaf_regex",
    )
    if len(heading_pattern) > 4096:
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.block_role.heading_leaf_regex is too long"
        )
    _compile_nonempty_pattern(
        heading_pattern,
        f"guard {guard_id}.detector.block_role.heading_leaf_regex",
    )
    minimum_blocks = _bounded_int(
        thresholds.get("minimum_blocks"),
        f"guard {guard_id}.detector.thresholds.minimum_blocks",
        minimum=3,
        maximum=100,
    )
    minimum_items = _bounded_int(
        thresholds.get("minimum_items_per_block"),
        f"guard {guard_id}.detector.thresholds.minimum_items_per_block",
        minimum=3,
        maximum=100,
    )
    mode = _require_text(
        shared_anchor.get("mode"),
        f"guard {guard_id}.detector.shared_anchor.mode",
    )
    if mode != "MAXIMAL_HAN_NGRAM":
        raise NegativeGuardRegistryError(
            f"guard {guard_id}.detector.shared_anchor.mode is unsupported"
        )
    minimum_han = _bounded_int(
        shared_anchor.get("minimum_han_chars"),
        f"guard {guard_id}.detector.shared_anchor.minimum_han_chars",
        minimum=4,
        maximum=12,
    )
    maximum_han = _bounded_int(
        shared_anchor.get("maximum_han_chars"),
        f"guard {guard_id}.detector.shared_anchor.maximum_han_chars",
        minimum=minimum_han,
        maximum=12,
    )
    minimum_coverage = _bounded_int(
        shared_anchor.get("minimum_block_coverage"),
        f"guard {guard_id}.detector.shared_anchor.minimum_block_coverage",
        minimum=3,
        maximum=minimum_blocks,
    )
    return {
        "type": "structured_repeated_list/v1",
        "block_role": {"heading_leaf_regex": heading_pattern},
        "thresholds": {
            "minimum_blocks": minimum_blocks,
            "minimum_items_per_block": minimum_items,
        },
        "shared_anchor": {
            "mode": mode,
            "minimum_han_chars": minimum_han,
            "maximum_han_chars": maximum_han,
            "minimum_block_coverage": minimum_coverage,
        },
    }


def normalize_detector(
    value: Any, guard_id: str, *, allow_legacy_regex: bool = False
) -> dict[str, Any]:
    """Normalize one versioned detector without admitting executable code."""
    if not isinstance(value, dict):
        raise NegativeGuardRegistryError(f"guard {guard_id}.detector must be an object")
    detector_type = value.get("type")
    if detector_type is None and allow_legacy_regex:
        return _normalize_regex_groups_detector(value, guard_id, legacy=True)
    if detector_type == "regex_groups/v1":
        return _normalize_regex_groups_detector(value, guard_id, legacy=False)
    if detector_type == "structured_repeated_list/v1":
        return _normalize_structured_repeated_list_detector(value, guard_id)
    raise NegativeGuardRegistryError(
        f"guard {guard_id}.detector.type is unsupported: {detector_type!r}"
    )


def _normalize_guard(value: Any, position: int, *, detector_only: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NegativeGuardRegistryError(f"guard[{position}] must be an object")
    if detector_only:
        _exact_keys(value, {"id", "scene", "detector"}, f"guard[{position}]")
    guard_id = _require_text(value.get("id"), f"guard[{position}].id")
    if not GUARD_ID_RE.fullmatch(guard_id):
        raise NegativeGuardRegistryError(f"invalid negative guard id: {guard_id}")
    scene = _require_text(value.get("scene"), f"guard {guard_id}.scene")
    if scene not in VALID_SCENES:
        raise NegativeGuardRegistryError(
            f"guard {guard_id} has invalid scene: {scene}"
        )
    return {
        "id": guard_id,
        "scene": scene,
        "detector": normalize_detector(
            value.get("detector"),
            guard_id,
            allow_legacy_regex=not detector_only,
        ),
        "status": "AVAILABLE",
    }


def _from_detector_registry(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    _exact_keys(payload, {"schema_version", "registry_id", "guards"}, "registry")
    if payload.get("registry_id") != REGISTRY_ID:
        raise NegativeGuardRegistryError(f"registry_id must be {REGISTRY_ID}")
    raw_guards = payload.get("guards")
    if not isinstance(raw_guards, list) or not raw_guards:
        raise NegativeGuardRegistryError("registry.guards must be a non-empty array")
    return [
        _normalize_guard(raw_guard, position, detector_only=True)
        for position, raw_guard in enumerate(raw_guards, start=1)
    ]


def _load_origin_decisions(raw: bytes) -> dict[str, dict[str, Any]]:
    payload = _strict_json(raw, "source provenance trust policy")
    if not isinstance(payload, dict):
        raise NegativeGuardRegistryError("source provenance trust policy must be an object")
    _exact_keys(
        payload,
        {
            "schema_version",
            "policy_version",
            "production_attestation",
            "origin_decisions",
        },
        "source provenance trust policy",
    )
    if payload.get("schema_version") != SOURCE_TRUST_SCHEMA:
        raise NegativeGuardRegistryError(
            f"source trust schema must be {SOURCE_TRUST_SCHEMA}"
        )
    if payload.get("policy_version") != "1.0.0":
        raise NegativeGuardRegistryError("source trust policy_version drifted")
    if payload.get("production_attestation") != EXPECTED_PRODUCTION_ATTESTATION:
        raise NegativeGuardRegistryError("source trust production attestation widened")
    decisions = payload.get("origin_decisions")
    if decisions != EXPECTED_ORIGIN_DECISIONS:
        raise NegativeGuardRegistryError("source trust origin decision matrix drifted")
    return decisions


def _from_full_audit_catalog(
    payload: Mapping[str, Any], origin_decisions: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    cards = payload.get("action_cards")
    sources = payload.get("sources")
    if (
        payload.get("schema_version") != 2
        or not isinstance(cards, list)
        or not isinstance(sources, list)
    ):
        raise NegativeGuardRegistryError("unsupported negative guard source format")
    source_origins: dict[str, str] = {}
    for position, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            raise NegativeGuardRegistryError(f"sources[{position}] must be an object")
        source_id = _require_text(source.get("id"), f"sources[{position}].id")
        origin_class = _require_text(
            source.get("origin_class"), f"source {source_id}.origin_class"
        )
        if source_id in source_origins:
            raise NegativeGuardRegistryError(f"duplicate source id: {source_id}")
        if origin_class not in origin_decisions:
            raise NegativeGuardRegistryError(
                f"source {source_id} has unsupported origin class: {origin_class}"
            )
        source_origins[source_id] = origin_class
    guards: list[dict[str, Any]] = []
    audit_only_guard_ids: list[str] = []
    for position, card in enumerate(cards, start=1):
        if not isinstance(card, dict):
            raise NegativeGuardRegistryError(f"action_cards[{position}] must be an object")
        kind = card.get("kind")
        if kind == "positive_action":
            continue
        if kind != "negative_guard":
            raise NegativeGuardRegistryError(
                f"action_cards[{position}] has unsupported kind: {kind!r}"
            )
        normalized = _normalize_guard(card, position, detector_only=False)
        refs = card.get("source_refs")
        if not isinstance(refs, list) or not refs:
            raise NegativeGuardRegistryError(
                f"negative guard {normalized['id']} must have source_refs"
            )
        origins: set[str] = set()
        for ref_position, ref in enumerate(refs, start=1):
            if not isinstance(ref, dict):
                raise NegativeGuardRegistryError(
                    f"guard {normalized['id']} source_refs[{ref_position}] must be an object"
                )
            source_id = _require_text(
                ref.get("source_id"),
                f"guard {normalized['id']} source_refs[{ref_position}].source_id",
            )
            if source_id not in source_origins:
                raise NegativeGuardRegistryError(
                    f"guard {normalized['id']} references unknown source: {source_id}"
                )
            origins.add(source_origins[source_id])
        runtime_authorized = all(
            "NEGATIVE_GUARD" in origin_decisions[origin]["allowed_uses"]
            for origin in origins
        )
        if runtime_authorized:
            guards.append(normalized)
        else:
            audit_only_guard_ids.append(normalized["id"])
    if not guards:
        raise NegativeGuardRegistryError(
            "full audit catalog has no runtime-authorized negative guards"
        )
    return guards, sorted(audit_only_guard_ids)


def parse_negative_guard_registry(
    raw: bytes,
    *,
    label: str = "negative guard registry",
    source_path: str = "<memory>",
    source_trust_policy_raw: bytes | None = None,
) -> dict[str, Any]:
    """Parse registry bytes without admitting positive actions into the result."""
    payload = _strict_json(raw, label)
    if not isinstance(payload, dict):
        raise NegativeGuardRegistryError("negative guard registry must be an object")
    if payload.get("schema_version") == REGISTRY_SCHEMA:
        source_format = "DETECTOR_ONLY_REGISTRY"
        guards = _from_detector_registry(payload)
        audit_only_guard_ids: list[str] = []
        source_trust_policy_sha256 = ""
    else:
        source_format = "FULL_AUDIT_CATALOG"
        if source_trust_policy_raw is None:
            raise NegativeGuardRegistryError(
                "full audit catalog requires a frozen source trust policy"
            )
        origin_decisions = _load_origin_decisions(source_trust_policy_raw)
        guards, audit_only_guard_ids = _from_full_audit_catalog(
            payload, origin_decisions
        )
        source_trust_policy_sha256 = _sha256(source_trust_policy_raw)
    guard_ids = [guard["id"] for guard in guards]
    if len(guard_ids) != len(set(guard_ids)):
        raise NegativeGuardRegistryError("negative guard ids must be unique")
    guards.sort(key=lambda guard: guard["id"].encode("utf-8"))
    canonical_registry = {
        "schema_version": REGISTRY_SCHEMA,
        "registry_id": REGISTRY_ID,
        "guards": [
            {
                "id": guard["id"],
                "scene": guard["scene"],
                "detector": guard["detector"],
            }
            for guard in guards
        ],
    }
    return {
        **canonical_registry,
        "tool": "load_humanize_negative_guards.py",
        "loader_version": LOADER_VERSION,
        "source_format": source_format,
        "source_path": source_path,
        "source_sha256": _sha256(raw),
        "source_trust_policy_sha256": source_trust_policy_sha256,
        "registry_sha256": _sha256(_canonical_json(canonical_registry)),
        "status": "PASS",
        "guards": guards,
        "summary": {
            "guard_count": len(guards),
            "audit_only_guard_count": len(audit_only_guard_ids),
            "audit_only_guard_ids": audit_only_guard_ids,
            "scene_counts": {
                scene: sum(guard["scene"] == scene for guard in guards)
                for scene in sorted({guard["scene"] for guard in guards})
            },
        },
    }


def load_negative_guard_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Return only executable negative detectors; positive actions never enter the result."""
    raw = path.read_bytes()
    trust_raw = None
    payload = _strict_json(raw, "negative guard registry")
    if not isinstance(payload, dict):
        raise NegativeGuardRegistryError("negative guard registry must be an object")
    if payload.get("schema_version") != REGISTRY_SCHEMA:
        trust_raw = DEFAULT_SOURCE_TRUST_POLICY.read_bytes()
    return parse_negative_guard_registry(
        raw,
        source_path=str(path),
        source_trust_policy_raw=trust_raw,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and emit the detector-only negative-guard runtime registry."
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        result = load_negative_guard_registry(args.registry)
    except (OSError, NegativeGuardRegistryError) as error:
        print(f"negative guard registry invalid: {error}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"negative_guard_registry=PASS guards={result['summary']['guard_count']} "
            f"source_format={result['source_format']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
