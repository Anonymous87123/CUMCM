#!/usr/bin/env python3
"""Build a deterministic, evidence-bound Chinese Voice Profile.

The builder deliberately publishes only a small registry of mechanically
rebuildable features.  It never embeds source prose in the profile.  Samples
that cannot be decoded safely are audited and skipped instead of guessed.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import unicodedata
from array import array
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


PROFILE_SCHEMA_VERSION = "humanize-voice-profile/v1"
MANIFEST_SCHEMA_VERSION = "humanize-voice-sample-manifest/v2"
SPEC_SCHEMA_VERSION = "humanize-voice-sample-spec/v1"
SCENES = ("COURSE", "MODELING", "RESEARCH", "GENERAL")
ORIGINS = (
    "USER_CONFIRMED_AUTHOR",
    "USER_CONFIRMED_ADOPTED",
    "UNKNOWN",
    "MODEL_GENERATED",
)
ROLES = ("author", "quoted", "exam-original", "ocr", "code", "math", "template", "unknown")
ELIGIBLE_ORIGINS = {"USER_CONFIRMED_AUTHOR", "USER_CONFIRMED_ADOPTED"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
CHINESE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
MAX_JSON_DEPTH = 64


def _reject_floats_and_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError(f"JSON nesting exceeds {MAX_JSON_DEPTH}")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number is forbidden")
        raise ValueError("floating-point values are forbidden in Voice Profile artifacts")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            _reject_floats_and_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _reject_floats_and_depth(item, depth + 1)


def _canonical_json_bytes(value: Any) -> bytes:
    _reject_floats_and_depth(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_hash(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def canonical_profile_sha256(profile: dict[str, Any]) -> str:
    """Return the semantic SHA-256 after removing ``profile_sha256``.

    Key order, indentation, UTF-8 escaping and source file line endings do not
    affect this identity.  Floats and over-deep values are rejected because
    they create avoidable cross-parser ambiguity.
    """

    if not isinstance(profile, dict):
        raise ValueError("voice profile must be a JSON object")
    payload = dict(profile)
    payload.pop("profile_sha256", None)
    return _sha256_bytes(_canonical_json_bytes(payload))


ROLE_POLICY = {
    "version": "voice-role-policy/v1",
    "eligible_origins": sorted(ELIGIBLE_ORIGINS),
    "protected_roles": [role for role in ROLES if role != "author"],
    "automatic_protection": [
        "markdown-fence",
        "markdown-inline-code",
        "markdown-blockquote",
        "tex-code-environment",
        "tex-math-environment",
        "tex-quote-environment",
        "tex-template-line",
        "chinese-direct-quote",
    ],
}
DEDUP_POLICY = {
    "version": "voice-dedup/v2",
    "normalization": "NFC+alnum-only",
    "exact": True,
    "near_min_chars": 40,
    "gram_size": 5,
    "jaccard_ppm": 900000,
    "containment_ppm": 950000,
    "clustering": "connected-components-order-invariant",
}
FEATURE_REGISTRY = {
    "version": "voice-feature-registry/v1",
    "features": {
        "syntax.subject_position": ["TEXT_OR_OBJECT_SUBJECT", "FIRST_PERSON_SUBJECT"],
        "syntax.condition_opening": ["CONDITION_BEFORE_CLAIM"],
        "transition.explicit_connector": ["EXPLICIT_LOGICAL_CONNECTOR"],
        "layout.paragraph_terminal": ["EXPLICIT_TERMINAL_PUNCTUATION"],
        "layout.parenthetical_note": ["PARENTHETICAL_QUALIFICATION"],
        "layout.semicolon_grouping": ["SEMICOLON_GROUPING"],
        "layout.paragraph_form": ["NON_LIST_PROSE"],
    },
    "negative_controls": {
        "transition.template_shell": ["KNOWN_AI_TEMPLATE_SHELL"],
        "transition.repeated_opening": ["REPEATED_PARAGRAPH_OPENING"],
    },
}
FEATURE_EXTRACTORS = {
    "TEXT_OR_OBJECT_SUBJECT": {
        "feature_type": "syntax.subject_position",
        "rule_id": "subject-position/v1",
        "pattern": re.compile(
            r"(?m)^\s*(?:#{1,6}\s*)?(?:本文|本研究|本节|该(?:方法|模型|系统|结果|过程|问题)|这一(?:方法|模型|结果|过程))"
        ),
    },
    "FIRST_PERSON_SUBJECT": {
        "feature_type": "syntax.subject_position",
        "rule_id": "first-person-subject/v1",
        "pattern": re.compile(r"(?m)^\s*(?:我们|笔者|我)(?:认为|采用|选择|将|把|在|对)"),
    },
    "CONDITION_BEFORE_CLAIM": {
        "feature_type": "syntax.condition_opening",
        "rule_id": "condition-opening/v1",
        "pattern": re.compile(r"(?m)^\s*(?:如果|若|当|在[^，。]{0,24}(?:条件|情形|情况下))"),
    },
    "EXPLICIT_LOGICAL_CONNECTOR": {
        "feature_type": "transition.explicit_connector",
        "rule_id": "logical-connector/v1",
        "pattern": re.compile(r"(?:因此|然而|不过|同时|由此|相较之下|换言之)"),
    },
    "EXPLICIT_TERMINAL_PUNCTUATION": {
        "feature_type": "layout.paragraph_terminal",
        "rule_id": "paragraph-terminal/v1",
        "pattern": re.compile(r"[。！？；]\s*$"),
    },
    "PARENTHETICAL_QUALIFICATION": {
        "feature_type": "layout.parenthetical_note",
        "rule_id": "parenthetical-note/v1",
        "pattern": re.compile(r"（[^（）\n]{1,80}）"),
    },
    "SEMICOLON_GROUPING": {
        "feature_type": "layout.semicolon_grouping",
        "rule_id": "semicolon-grouping/v1",
        "pattern": re.compile(r"；"),
    },
    "NON_LIST_PROSE": {
        "feature_type": "layout.paragraph_form",
        "rule_id": "paragraph-form/v1",
        "pattern": re.compile(
            r"(?m)^(?!\s*(?:[-*+]\s|\d+[.)、]\s|#{1,6}\s|\\(?:section|subsection|item)\b))\s*[\u3400-\u9fff]"
        ),
    },
}
FEATURE_EXTRACTOR_POLICY = {
    "version": "voice-feature-extractors/v1",
    "extractors": [
        {
            "code": code,
            "feature_type": item["feature_type"],
            "rule_id": item["rule_id"],
            "pattern": item["pattern"].pattern,
            "flags": item["pattern"].flags,
        }
        for code, item in sorted(FEATURE_EXTRACTORS.items())
    ],
}
SCENE_DEFAULTS = {
    "COURSE": {
        "policy_version": 1,
        "style_codes": [
            "NATURAL_EXPLANATION",
            "SELECTIVE_EXPANSION",
            "SLOW_AT_DIFFICULTY",
            "COMPRESS_ROUTINE_STEPS",
        ],
    },
    "MODELING": {
        "policy_version": 1,
        "style_codes": [
            "PRACTICAL_DIRECT",
            "MAKE_TRADEOFFS_VISIBLE",
            "OBJECT_AND_RESULT_FIRST",
            "NO_SETTING_BY_SETTING_NARRATION",
        ],
    },
    "RESEARCH": {
        "policy_version": 1,
        "style_codes": [
            "RESTRAINED_FORMAL",
            "ARGUMENT_HIERARCHY",
            "NO_DEFENSE_OR_PROMOTION_VOICE",
            "NO_OVER_CLOSED_ENDING",
        ],
    },
    "GENERAL": {
        "policy_version": 1,
        "style_codes": [
            "PRESERVE_EXISTING_FORMALITY",
            "REMOVE_MECHANICAL_TEMPLATES",
            "BREAK_UNIFORM_RHYTHM_ONLY",
        ],
    },
}
ROLE_POLICY_SHA256 = _stable_hash(ROLE_POLICY)
DEDUP_POLICY_SHA256 = _stable_hash(DEDUP_POLICY)
FEATURE_REGISTRY_SHA256 = _stable_hash(FEATURE_REGISTRY)
FEATURE_EXTRACTOR_POLICY_SHA256 = _stable_hash(FEATURE_EXTRACTOR_POLICY)
SCENE_DEFAULT_POLICY_SHA256 = _stable_hash(SCENE_DEFAULTS)


def _policy_binding() -> dict[str, str]:
    return {
        "role_policy_sha256": ROLE_POLICY_SHA256,
        "dedup_policy_sha256": DEDUP_POLICY_SHA256,
        "feature_registry_sha256": FEATURE_REGISTRY_SHA256,
        "feature_extractor_policy_sha256": FEATURE_EXTRACTOR_POLICY_SHA256,
        "scene_default_policy_sha256": SCENE_DEFAULT_POLICY_SHA256,
    }


def _scene_default_payload(scene: str) -> dict[str, Any]:
    source = SCENE_DEFAULTS[scene]
    return {
        "policy_version": source["policy_version"],
        "style_codes": list(source["style_codes"]),
    }


def build_scene_default_profile(scene: str) -> dict[str, Any]:
    """Build one of the four immutable, versioned scene defaults."""

    scene = str(scene).upper()
    if scene not in SCENES:
        raise ValueError(f"unknown voice scene: {scene!r}")
    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_id": f"scene-default-{scene.lower()}",
        "version": 1,
        "revision": 1,
        "supersedes_profile_sha256": None,
        "profile_kind": "DEFAULT",
        "source_kind": "SCENE_DEFAULT",
        "binding_scene": scene,
        "validation_status": "PASS",
        "confidence": "DEFAULT",
        "sample_binding": {
            "manifest_sha256": "0" * 64,
            "readable_author_chars": 0,
            "unique_analysis_units": 0,
            "unique_complete_units": 0,
            "sample_scenes": [],
        },
        "policy_binding": _policy_binding(),
        "features": [],
        "negative_controls": [],
        "defaults": {
            "use_scene_default": True,
            "scene": scene,
            "reason": "NO_AUTHOR_SAMPLES",
            "disclosure_required": True,
            "personal_voice_claim_allowed": False,
        },
        "scene_default": _scene_default_payload(scene),
        "claims": {
            "identity_verified": False,
            "author_personality_inferred": False,
            "academic_correctness": "NOT_EVALUATED",
            "sample_text_embedded": False,
        },
    }
    profile["profile_sha256"] = canonical_profile_sha256(profile)
    return profile


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_strict(path: Path, *, max_bytes: int = 16 * 1024 * 1024) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read JSON artifact {path}: {exc}") from exc
    if len(raw) > max_bytes:
        raise ValueError(f"JSON artifact exceeds {max_bytes} bytes: {path}")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"JSON artifact is not strict UTF-8: {path}") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid number {token}")),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid JSON artifact {path}: {exc}") from exc
    _reject_floats_and_depth(value)
    return value


def _expect_exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{where} keys mismatch; missing={missing}, extra={extra}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_int(value: Any, where: str, *, minimum: int = 0) -> int:
    if not _is_int(value) or value < minimum:
        raise ValueError(f"{where} must be an integer >= {minimum}")
    return value


def _validate_anchor(anchor: Any, where: str) -> None:
    if not isinstance(anchor, dict):
        raise ValueError(f"{where} must be an object")
    _expect_exact_keys(
        anchor,
        {"unit_id", "byte_start", "byte_end", "span_sha256", "judgment"},
        where,
    )
    if not isinstance(anchor["unit_id"], str) or not anchor["unit_id"]:
        raise ValueError(f"{where}.unit_id must be non-empty")
    start = _require_int(anchor["byte_start"], f"{where}.byte_start")
    end = _require_int(anchor["byte_end"], f"{where}.byte_end")
    if end <= start:
        raise ValueError(f"{where} must use a non-empty half-open byte interval")
    if not isinstance(anchor["span_sha256"], str) or not SHA256_RE.fullmatch(anchor["span_sha256"]):
        raise ValueError(f"{where}.span_sha256 must be lowercase SHA-256")
    if anchor["judgment"] not in {"SUPPORT", "COUNTEREXAMPLE"}:
        raise ValueError(f"{where}.judgment is invalid")


def _validate_feature(feature: Any, where: str, *, negative: bool = False) -> None:
    if not isinstance(feature, dict):
        raise ValueError(f"{where} must be an object")
    _expect_exact_keys(
        feature,
        {"feature_key", "feature_type", "scope", "disposition", "confidence", "value", "evidence"},
        where,
    )
    feature_key = feature["feature_key"]
    feature_type = feature["feature_type"]
    if not isinstance(feature_key, str) or not re.fullmatch(r"[a-z0-9_.-]{3,160}", feature_key):
        raise ValueError(f"{where}.feature_key is invalid")
    registry = FEATURE_REGISTRY["negative_controls" if negative else "features"]
    if feature_type not in registry:
        raise ValueError(f"{where}.feature_type is not registered")
    scope = feature["scope"]
    if not isinstance(scope, list) or not scope or len(scope) != len(set(scope)):
        raise ValueError(f"{where}.scope must be a unique non-empty list")
    if any(item not in {"GLOBAL", *SCENES} for item in scope):
        raise ValueError(f"{where}.scope contains an invalid scene")
    if "GLOBAL" in scope and len(scope) != 1:
        raise ValueError(f"{where}.scope cannot mix GLOBAL and a scene")
    allowed_dispositions = {"DO_NOT_AMPLIFY"} if negative else {"PREFER", "ALLOW", "RARE", "AVOID"}
    if feature["disposition"] not in allowed_dispositions:
        raise ValueError(f"{where}.disposition is invalid")
    if feature["confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError(f"{where}.confidence is invalid")
    value = feature["value"]
    if not isinstance(value, dict):
        raise ValueError(f"{where}.value must be an object")
    _expect_exact_keys(value, {"kind", "code"}, f"{where}.value")
    if value["kind"] != "CATEGORY" or value["code"] not in registry[feature_type]:
        raise ValueError(f"{where}.value is outside the feature registry")
    evidence = feature["evidence"]
    if not isinstance(evidence, dict):
        raise ValueError(f"{where}.evidence must be an object")
    _expect_exact_keys(
        evidence,
        {
            "extractor_id",
            "extractor_sha256",
            "opportunity_count",
            "support_count",
            "counterexample_count",
            "support_ratio_ppm",
            "distinct_analysis_units",
            "distinct_complete_units",
            "anchors",
        },
        f"{where}.evidence",
    )
    if not isinstance(evidence["extractor_id"], str) or not evidence["extractor_id"]:
        raise ValueError(f"{where}.evidence.extractor_id is invalid")
    if not isinstance(evidence["extractor_sha256"], str) or not SHA256_RE.fullmatch(evidence["extractor_sha256"]):
        raise ValueError(f"{where}.evidence.extractor_sha256 is invalid")
    opportunity = _require_int(evidence["opportunity_count"], f"{where}.opportunity_count", minimum=1)
    support = _require_int(evidence["support_count"], f"{where}.support_count", minimum=1)
    counter = _require_int(evidence["counterexample_count"], f"{where}.counterexample_count")
    ratio = _require_int(evidence["support_ratio_ppm"], f"{where}.support_ratio_ppm")
    distinct = _require_int(evidence["distinct_analysis_units"], f"{where}.distinct_analysis_units", minimum=1)
    _require_int(evidence["distinct_complete_units"], f"{where}.distinct_complete_units")
    if support + counter > opportunity or support > distinct or ratio > 1_000_000:
        raise ValueError(f"{where}.evidence counts are inconsistent")
    if ratio != support * 1_000_000 // opportunity:
        raise ValueError(f"{where}.support_ratio_ppm is not rebuildable")
    anchors = evidence["anchors"]
    if not isinstance(anchors, list) or not anchors:
        raise ValueError(f"{where}.anchors must be non-empty")
    seen_anchor: set[tuple[str, int, int]] = set()
    for index, anchor in enumerate(anchors):
        _validate_anchor(anchor, f"{where}.anchors[{index}]")
        identity = (anchor["unit_id"], anchor["byte_start"], anchor["byte_end"])
        if identity in seen_anchor:
            raise ValueError(f"{where} repeats an evidence anchor")
        seen_anchor.add(identity)
    if not negative:
        if support < 3 or distinct < 3:
            raise ValueError(f"{where} lacks three independent supporting units")
        if feature["confidence"] == "LOW" and counter != 0:
            raise ValueError(f"{where} LOW feature has a counterexample")
        if feature["confidence"] in {"MEDIUM", "HIGH"} and ratio < 700_000:
            raise ValueError(f"{where} support ratio is below 0.70")


PROFILE_KEYS = {
    "schema_version",
    "profile_id",
    "version",
    "revision",
    "supersedes_profile_sha256",
    "profile_kind",
    "source_kind",
    "binding_scene",
    "validation_status",
    "confidence",
    "sample_binding",
    "policy_binding",
    "features",
    "negative_controls",
    "defaults",
    "scene_default",
    "claims",
    "profile_sha256",
}


def validate_profile_object(profile: Any) -> dict[str, Any]:
    """Strictly validate a parsed profile and return it unchanged."""

    if not isinstance(profile, dict):
        raise ValueError("voice profile must be an object")
    _expect_exact_keys(profile, PROFILE_KEYS, "profile")
    if profile["schema_version"] != PROFILE_SCHEMA_VERSION:
        raise ValueError("unsupported voice profile schema_version")
    stored_hash = profile["profile_sha256"]
    if not isinstance(stored_hash, str) or not SHA256_RE.fullmatch(stored_hash):
        raise ValueError("profile.profile_sha256 must be lowercase SHA-256")
    actual_hash = canonical_profile_sha256(profile)
    if stored_hash != actual_hash:
        raise ValueError(f"profile self-hash mismatch: expected {stored_hash}, rebuilt {actual_hash}")
    if not isinstance(profile["profile_id"], str) or not PROFILE_ID_RE.fullmatch(profile["profile_id"]):
        raise ValueError("profile.profile_id is invalid")
    version = _require_int(profile["version"], "profile.version", minimum=1)
    revision = _require_int(profile["revision"], "profile.revision", minimum=1)
    if version != revision:
        raise ValueError("profile.version and profile.revision must match")
    supersedes = profile["supersedes_profile_sha256"]
    if revision == 1 and supersedes is not None:
        raise ValueError("revision 1 cannot supersede another profile")
    if revision > 1 and (not isinstance(supersedes, str) or not SHA256_RE.fullmatch(supersedes)):
        raise ValueError("revisions after 1 must bind the superseded profile hash")
    if profile["profile_kind"] not in {"PERSONAL", "DEFAULT"}:
        raise ValueError("profile.profile_kind is invalid")
    if profile["source_kind"] not in {"AUTHOR_PROFILE", "SCENE_DEFAULT"}:
        raise ValueError("profile.source_kind is invalid")
    if profile["binding_scene"] not in SCENES:
        raise ValueError("profile.binding_scene is invalid")
    if profile["validation_status"] not in {"PASS", "REVIEW", "FAIL"}:
        raise ValueError("profile.validation_status is invalid")
    if profile["confidence"] not in {"LOW", "MEDIUM", "HIGH", "DEFAULT"}:
        raise ValueError("profile.confidence is invalid")

    binding = profile["sample_binding"]
    if not isinstance(binding, dict):
        raise ValueError("profile.sample_binding must be an object")
    _expect_exact_keys(
        binding,
        {
            "manifest_sha256",
            "readable_author_chars",
            "unique_analysis_units",
            "unique_complete_units",
            "sample_scenes",
        },
        "profile.sample_binding",
    )
    if not isinstance(binding["manifest_sha256"], str) or not SHA256_RE.fullmatch(binding["manifest_sha256"]):
        raise ValueError("profile.sample_binding.manifest_sha256 is invalid")
    chars = _require_int(binding["readable_author_chars"], "profile.readable_author_chars")
    units = _require_int(binding["unique_analysis_units"], "profile.unique_analysis_units")
    complete_units = _require_int(binding["unique_complete_units"], "profile.unique_complete_units")
    scenes = binding["sample_scenes"]
    if not isinstance(scenes, list) or scenes != sorted(set(scenes)) or any(scene not in SCENES for scene in scenes):
        raise ValueError("profile.sample_binding.sample_scenes must be a sorted unique scene list")

    if profile["policy_binding"] != _policy_binding():
        raise ValueError("profile policy binding is stale or unknown")
    if not isinstance(profile["features"], list) or not isinstance(profile["negative_controls"], list):
        raise ValueError("profile feature collections must be lists")
    seen_features: set[str] = set()
    for index, feature in enumerate(profile["features"]):
        _validate_feature(feature, f"profile.features[{index}]")
        if feature["feature_key"] in seen_features:
            raise ValueError("profile repeats a feature_key")
        seen_features.add(feature["feature_key"])
    for index, feature in enumerate(profile["negative_controls"]):
        _validate_feature(feature, f"profile.negative_controls[{index}]", negative=True)
        if feature["feature_key"] in seen_features:
            raise ValueError("profile repeats a feature_key")
        seen_features.add(feature["feature_key"])

    defaults = profile["defaults"]
    if not isinstance(defaults, dict):
        raise ValueError("profile.defaults must be an object")
    _expect_exact_keys(
        defaults,
        {"use_scene_default", "scene", "reason", "disclosure_required", "personal_voice_claim_allowed"},
        "profile.defaults",
    )
    if defaults["scene"] != profile["binding_scene"]:
        raise ValueError("profile defaults scene does not match binding_scene")
    if not all(isinstance(defaults[name], bool) for name in ("use_scene_default", "disclosure_required", "personal_voice_claim_allowed")):
        raise ValueError("profile.defaults booleans have invalid types")
    claims = profile["claims"]
    if claims != {
        "identity_verified": False,
        "author_personality_inferred": False,
        "academic_correctness": "NOT_EVALUATED",
        "sample_text_embedded": False,
    }:
        raise ValueError("profile claims exceed the Voice Profile trust boundary")

    if profile["profile_kind"] == "DEFAULT":
        if profile["source_kind"] != "SCENE_DEFAULT" or profile["confidence"] != "DEFAULT":
            raise ValueError("DEFAULT profile kind/source/confidence are inconsistent")
        if profile["features"] or profile["negative_controls"]:
            raise ValueError("DEFAULT profile cannot carry personal features")
        if not defaults["use_scene_default"] or not defaults["disclosure_required"] or defaults["personal_voice_claim_allowed"]:
            raise ValueError("DEFAULT disclosure/claim semantics are invalid")
        if defaults["reason"] not in {"NO_AUTHOR_SAMPLES", "BELOW_300_AUTHOR_CHARS", "NO_ELIGIBLE_AUTHOR_TEXT"}:
            raise ValueError("DEFAULT reason is invalid")
        if profile["scene_default"] != _scene_default_payload(profile["binding_scene"]):
            raise ValueError("DEFAULT profile does not match the versioned scene policy")
        if chars >= 300:
            raise ValueError("DEFAULT profile cannot hide 300 or more eligible author characters")
    else:
        if profile["source_kind"] != "AUTHOR_PROFILE" or profile["confidence"] == "DEFAULT":
            raise ValueError("PERSONAL profile kind/source/confidence are inconsistent")
        if profile["scene_default"] is not None:
            raise ValueError("PERSONAL profile cannot embed a scene default as author evidence")
        if defaults["use_scene_default"] or defaults["disclosure_required"]:
            raise ValueError("PERSONAL profile cannot claim a default fallback")
        if defaults["reason"] is not None:
            raise ValueError("PERSONAL defaults.reason must be null")
        if chars < 300:
            raise ValueError("PERSONAL profile has fewer than 300 eligible author characters")
        expected_confidence = "LOW" if chars < 1000 else "MEDIUM"
        if chars >= 5000 and complete_units >= 3:
            expected_confidence = "HIGH"
        if profile["confidence"] != expected_confidence:
            raise ValueError("PERSONAL confidence does not match the sample threshold")
        if profile["validation_status"] == "PASS":
            if not profile["features"]:
                raise ValueError("PASS PERSONAL profile needs at least one accepted feature")
            has_counterexample = any(item["evidence"]["counterexample_count"] > 0 for item in profile["features"])
            if not profile["negative_controls"] and not has_counterexample:
                raise ValueError("PASS PERSONAL profile needs a negative control or counterexample")
            if not defaults["personal_voice_claim_allowed"]:
                raise ValueError("PASS PERSONAL profile unexpectedly disables its bounded voice claim")
            if scenes != [profile["binding_scene"]]:
                raise ValueError("PASS PERSONAL profile cannot relabel cross-scene evidence")
            allowed_scopes = {profile["binding_scene"], "GLOBAL"}
            if any(
                not set(item["scope"]).issubset(allowed_scopes)
                for item in [*profile["features"], *profile["negative_controls"]]
            ):
                raise ValueError("PASS PERSONAL profile carries incompatible feature scope")
        elif defaults["personal_voice_claim_allowed"]:
            raise ValueError("non-PASS PERSONAL profile cannot allow a personal voice claim")
        if units < 1:
            raise ValueError("PERSONAL profile has no unique analysis units")

    return profile


def load_and_validate_profile(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load strict UTF-8 JSON, validate schema/self-hash, or raise ValueError."""

    value = _load_json_strict(Path(path))
    return validate_profile_object(value)


def _validate_spec(spec: Any) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        raise ValueError("sample spec must be an object")
    _expect_exact_keys(spec, {"schema_version", "samples"}, "sample_spec")
    if spec["schema_version"] != SPEC_SCHEMA_VERSION:
        raise ValueError("unsupported sample spec schema_version")
    samples = spec["samples"]
    if not isinstance(samples, list):
        raise ValueError("sample_spec.samples must be a list")
    seen_ids: set[str] = set()
    result: list[dict[str, Any]] = []
    required = {"sample_id", "locator", "origin", "scene", "complete_unit", "default_role", "role_ranges"}
    for index, sample in enumerate(samples):
        where = f"sample_spec.samples[{index}]"
        if not isinstance(sample, dict):
            raise ValueError(f"{where} must be an object")
        _expect_exact_keys(sample, required, where)
        sample_id = sample["sample_id"]
        if not isinstance(sample_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", sample_id):
            raise ValueError(f"{where}.sample_id is invalid")
        if sample_id in seen_ids:
            raise ValueError(f"duplicate sample_id: {sample_id}")
        seen_ids.add(sample_id)
        locator = sample["locator"]
        if not isinstance(locator, str) or not locator or "\\" in locator:
            raise ValueError(f"{where}.locator must be a POSIX relative path")
        pure = PurePosixPath(locator)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError(f"{where}.locator escapes or is not canonical")
        if sample["origin"] not in ORIGINS or sample["scene"] not in SCENES:
            raise ValueError(f"{where} origin or scene is invalid")
        if not isinstance(sample["complete_unit"], bool) or sample["default_role"] not in ROLES:
            raise ValueError(f"{where} complete_unit/default_role is invalid")
        ranges = sample["role_ranges"]
        if not isinstance(ranges, list):
            raise ValueError(f"{where}.role_ranges must be a list")
        previous_end = 0
        for range_index, role_range in enumerate(ranges):
            range_where = f"{where}.role_ranges[{range_index}]"
            if not isinstance(role_range, dict):
                raise ValueError(f"{range_where} must be an object")
            _expect_exact_keys(role_range, {"byte_start", "byte_end", "role"}, range_where)
            start = _require_int(role_range["byte_start"], f"{range_where}.byte_start")
            end = _require_int(role_range["byte_end"], f"{range_where}.byte_end")
            if end <= start or start < previous_end or role_range["role"] not in ROLES:
                raise ValueError(f"{range_where} is empty, overlapping, unsorted, or has an invalid role")
            previous_end = end
        result.append(sample)
    return result


def _safe_sample_path(root: Path, locator: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(locator).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"sample path cannot be resolved: {locator}: {exc}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"sample path escapes allowed root: {locator}") from exc
    current = root
    for part in resolved.relative_to(root).parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ValueError(f"cannot stat sample component: {locator}: {exc}") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if current.is_symlink() or attributes & reparse:
            raise ValueError(f"sample path contains a link or reparse point: {locator}")
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"sample is not a regular file: {locator}")
    return resolved


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


def _read_frozen(
    path: Path,
    max_bytes: int,
    expected_identity: tuple[int, int, int, int, int] | None = None,
) -> bytes:
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if expected_identity is not None and _stat_identity(before) != expected_identity:
            raise ValueError(f"sample path changed between validation and open: {path}")
        if before.st_size > max_bytes:
            raise ValueError(f"sample exceeds --max-file-bytes: {path}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"short read while freezing sample: {path}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if handle.read(1):
            raise ValueError(f"sample grew while being frozen: {path}")
        after = os.fstat(handle.fileno())
    identity_before = _stat_identity(before)
    identity_after = _stat_identity(after)
    if identity_before != identity_after:
        raise ValueError(f"sample changed while being frozen: {path}")
    payload = b"".join(chunks)
    if len(payload) != before.st_size:
        raise ValueError(f"sample short read: {path}")
    try:
        current = path.lstat()
    except OSError as exc:
        raise ValueError(f"sample path changed after freezing: {path}: {exc}") from exc
    if _stat_identity(current) != identity_after:
        raise ValueError(f"sample path changed after freezing: {path}")
    return payload


def _byte_offsets(text: str) -> array:
    offsets = array("I", [0])
    total = 0
    for char in text:
        total += len(char.encode("utf-8"))
        offsets.append(total)
    return offsets


def _byte_to_char(offsets: Sequence[int], byte_offset: int, where: str) -> int:
    index = bisect.bisect_left(offsets, byte_offset)
    if index >= len(offsets) or offsets[index] != byte_offset:
        raise ValueError(f"{where} is not aligned to a UTF-8 character boundary")
    return index


def _merge_spans(spans: Iterable[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    priority = {role: index for index, role in enumerate(ROLES)}
    events: list[tuple[int, int, str]] = []
    for start, end, role in spans:
        if end > start:
            events.append((start, end, role))
    events.sort(key=lambda item: (item[0], item[1], priority[item[2]]))
    return events


def _automatic_protected_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    patterns: list[tuple[str, str, int]] = [
        (r"(?ms)^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[ \t]*$", "code", 0),
        (r"(?ms)^[ \t]*(?:```|~~~)[^\n]*\n(?:(?!^[ \t]*(?:```|~~~)[ \t]*$).)*\Z", "code", 0),
        (r"(?s)`[^`\n]+`", "code", 0),
        (r"(?m)^\s*>.*$", "quoted", 0),
        (r"(?s)“[^”]{1,2000}”", "quoted", 0),
        (r"(?s)\\begin\{(?:quote|quotation)\}.*?\\end\{(?:quote|quotation)\}", "quoted", 0),
        (r"(?s)\\begin\{(?:verbatim\*?|lstlisting|minted)\}.*?\\end\{(?:verbatim\*?|lstlisting|minted)\}", "code", 0),
        (
            r"(?s)\\begin\{(?:equation\*?|align\*?|aligned|gather\*?|multline\*?|displaymath|math|cases|matrix|pmatrix|bmatrix)\}.*?\\end\{(?:equation\*?|align\*?|aligned|gather\*?|multline\*?|displaymath|math|cases|matrix|pmatrix|bmatrix)\}",
            "math",
            0,
        ),
        (r"(?s)\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)", "math", 0),
        (r"(?<!\\)\$(?!\s)(?:\\.|[^$\n])+?(?<!\s)(?<!\\)\$", "math", 0),
        (
            r"(?m)^\s*\\(?:documentclass|usepackage|RequirePackage|title|author|date|maketitle|bibliographystyle|bibliography|begin\{document\}|end\{document\})\b.*$",
            "template",
            0,
        ),
    ]
    for pattern, role, flags in patterns:
        try:
            for match in re.finditer(pattern, text, flags):
                spans.append((match.start(), match.end(), role))
        except re.error as exc:  # pragma: no cover - registry constants are compile-time checked
            raise RuntimeError(f"invalid protected-span registry expression: {pattern}") from exc
    return _merge_spans(spans)


def _looks_mojibake(text: str) -> bool:
    if "\ufffd" in text or "锟斤拷" in text:
        return True
    suspicious = sum(text.count(token) for token in ("Ã", "Â", "â€", "æ–", "浣滆€", "鍙"))
    return suspicious >= 8 and suspicious * 40 > max(len(text), 1)


def _normalize_dedup(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return "".join(char.casefold() for char in normalized if char.isalnum())


def _chinese_count(text: str) -> int:
    return len(CHINESE_RE.findall(text))


def _gram_set(value: str, size: int = 5) -> set[str]:
    if len(value) < size:
        return set()
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def _near_duplicate_clusters(units: list[dict[str, Any]]) -> None:
    if not units:
        return

    parents = list(range(len(units)))
    ranks = [0] * len(units)

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if ranks[left_root] < ranks[right_root]:
            left_root, right_root = right_root, left_root
        parents[right_root] = left_root
        if ranks[left_root] == ranks[right_root]:
            ranks[left_root] += 1

    exact_groups: dict[str, list[int]] = defaultdict(list)
    for index, unit in enumerate(units):
        value = unit["dedup_view"]
        digest = _sha256_bytes(value.encode("utf-8"))
        unit["dedup_sha256"] = digest
        exact_groups[digest].append(index)
    for indexes in exact_groups.values():
        for index in indexes[1:]:
            union(indexes[0], index)

    distinct = [
        min(indexes, key=lambda index: units[index]["unit_id"])
        for _digest, indexes in sorted(exact_groups.items())
    ]
    distinct.sort(
        key=lambda index: (
            units[index]["dedup_sha256"],
            units[index]["dedup_view"],
        )
    )
    grams_by_index: dict[int, set[str]] = {}
    inverted: dict[str, list[int]] = defaultdict(list)
    for index in distinct:
        value = units[index]["dedup_view"]
        if len(value) < DEDUP_POLICY["near_min_chars"]:
            continue
        grams = _gram_set(value, DEDUP_POLICY["gram_size"])
        shared: Counter[int] = Counter()
        for gram in grams:
            for other in inverted.get(gram, ()):  # every distinct candidate pair is considered once
                shared[other] += 1
        for other, intersection in shared.items():
            other_grams = grams_by_index[other]
            gram_union = len(grams) + len(other_grams) - intersection
            jaccard_ppm = intersection * 1_000_000 // max(gram_union, 1)
            containment_ppm = intersection * 1_000_000 // max(
                min(len(grams), len(other_grams)), 1
            )
            if (
                jaccard_ppm >= DEDUP_POLICY["jaccard_ppm"]
                or containment_ppm >= DEDUP_POLICY["containment_ppm"]
            ):
                union(index, other)
        grams_by_index[index] = grams
        for gram in grams:
            inverted[gram].append(index)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(units)):
        components[find(index)].append(index)

    ordered_components: list[tuple[tuple[str, str], int, list[int]]] = []
    for indexes in components.values():
        representative = min(
            indexes,
            key=lambda index: (
                units[index]["dedup_sha256"],
                units[index]["dedup_view"],
                units[index]["unit_id"],
            ),
        )
        ordered_components.append(
            (
                (
                    units[representative]["dedup_sha256"],
                    units[representative]["dedup_view"],
                ),
                representative,
                indexes,
            )
        )

    for cluster_number, (_key, representative, indexes) in enumerate(
        sorted(ordered_components, key=lambda item: item[0]), 1
    ):
        cluster_id = f"cluster-{cluster_number:06d}"
        representative_digest = units[representative]["dedup_sha256"]
        digest_groups: dict[str, list[int]] = defaultdict(list)
        for index in indexes:
            digest_groups[units[index]["dedup_sha256"]].append(index)
            units[index]["representative_index"] = representative
            units[index]["dedup_cluster_id"] = cluster_id
            units[index]["is_representative"] = index == representative
        units[representative]["dedup_relation"] = "UNIQUE"
        for digest, digest_indexes in digest_groups.items():
            ordered = sorted(digest_indexes, key=lambda index: units[index]["unit_id"])
            first = ordered[0]
            if digest != representative_digest:
                units[first]["dedup_relation"] = "NEAR"
            for index in ordered[1:]:
                if index != representative:
                    units[index]["dedup_relation"] = "EXACT"


def _scope_for_units(units: Sequence[dict[str, Any]]) -> list[str]:
    scenes = sorted({unit["scene"] for unit in units})
    return scenes if len(scenes) == 1 else ["GLOBAL"]


def _anchor(unit: dict[str, Any], local_start: int, local_end: int, judgment: str) -> dict[str, Any]:
    sample = unit["_sample"]
    global_start = unit["char_start"] + local_start
    global_end = unit["char_start"] + local_end
    byte_start = sample["byte_offsets"][global_start]
    byte_end = sample["byte_offsets"][global_end]
    if byte_end <= byte_start:
        raise ValueError("empty evidence anchor")
    payload = sample["raw"][byte_start:byte_end]
    return {
        "unit_id": unit["unit_id"],
        "byte_start": int(byte_start),
        "byte_end": int(byte_end),
        "span_sha256": _sha256_bytes(payload),
        "judgment": judgment,
    }


def _counter_anchor(unit: dict[str, Any]) -> dict[str, Any]:
    match = CHINESE_RE.search(unit["text"])
    if match is None:
        raise ValueError("counterexample unit contains no Chinese character")
    return _anchor(unit, match.start(), match.end(), "COUNTEREXAMPLE")


def _feature_from_rule(
    feature_type: str,
    code: str,
    rule_id: str,
    pattern: re.Pattern[str],
    units: list[dict[str, Any]],
    confidence: str,
) -> dict[str, Any] | None:
    supports: list[tuple[dict[str, Any], re.Match[str]]] = []
    counters: list[dict[str, Any]] = []
    for unit in units:
        match = pattern.search(unit["text"])
        if match:
            supports.append((unit, match))
        else:
            counters.append(unit)
    opportunity = len(units)
    support = len(supports)
    if support < 3:
        return None
    ratio = support * 1_000_000 // opportunity
    if confidence == "LOW" and counters:
        return None
    if confidence in {"MEDIUM", "HIGH"} and ratio < 700_000:
        return None
    support_units = [unit for unit, _ in supports]
    anchors = [_anchor(unit, match.start(), match.end(), "SUPPORT") for unit, match in supports[:12]]
    anchors.extend(_counter_anchor(unit) for unit in counters[:4])
    feature_confidence = confidence
    if feature_type == "layout.paragraph_form" and confidence == "HIGH":
        feature_confidence = "MEDIUM"
    rule_payload = {"rule_id": rule_id, "pattern": pattern.pattern, "flags": pattern.flags, "code": code}
    return {
        "feature_key": f"{feature_type}.{code.lower()}",
        "feature_type": feature_type,
        "scope": _scope_for_units(support_units),
        "disposition": "PREFER",
        "confidence": feature_confidence,
        "value": {"kind": "CATEGORY", "code": code},
        "evidence": {
            "extractor_id": rule_id,
            "extractor_sha256": _stable_hash(rule_payload),
            "opportunity_count": opportunity,
            "support_count": support,
            "counterexample_count": len(counters),
            "support_ratio_ppm": ratio,
            "distinct_analysis_units": support,
            "distinct_complete_units": len({unit["sample_id"] for unit in support_units if unit["complete_unit"]}),
            "anchors": anchors,
        },
    }


def _build_features(units: list[dict[str, Any]], confidence: str) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for code, extractor in FEATURE_EXTRACTORS.items():
        feature = _feature_from_rule(
            str(extractor["feature_type"]),
            code,
            str(extractor["rule_id"]),
            extractor["pattern"],
            units,
            confidence,
        )
        if feature is not None:
            features.append(feature)
    return features[:8]


AI_SHELL_RE = re.compile(
    r"(?:综上所述|值得注意的是|需要指出的是|不难发现|显而易见|毋庸置疑|本文将从|总而言之|由此可见)"
)


def _negative_feature(
    feature_key: str,
    feature_type: str,
    code: str,
    rule_id: str,
    matches: list[tuple[dict[str, Any], int, int]],
    opportunity: int,
) -> dict[str, Any]:
    units_by_id = {unit["unit_id"]: unit for unit, _, _ in matches}
    anchors = [_anchor(unit, start, end, "SUPPORT") for unit, start, end in matches[:12]]
    return {
        "feature_key": feature_key,
        "feature_type": feature_type,
        "scope": _scope_for_units(list(units_by_id.values())),
        "disposition": "DO_NOT_AMPLIFY",
        "confidence": "LOW",
        "value": {"kind": "CATEGORY", "code": code},
        "evidence": {
            "extractor_id": rule_id,
            "extractor_sha256": _stable_hash({"rule_id": rule_id, "code": code}),
            "opportunity_count": opportunity,
            "support_count": len(units_by_id),
            "counterexample_count": 0,
            "support_ratio_ppm": len(units_by_id) * 1_000_000 // max(opportunity, 1),
            "distinct_analysis_units": len(units_by_id),
            "distinct_complete_units": len({unit["sample_id"] for unit in units_by_id.values() if unit["complete_unit"]}),
            "anchors": anchors,
        },
    }


def _build_negative_controls(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    shell_matches: list[tuple[dict[str, Any], int, int]] = []
    for unit in units:
        match = AI_SHELL_RE.search(unit["text"])
        if match:
            shell_matches.append((unit, match.start(), match.end()))
    if shell_matches:
        controls.append(
            _negative_feature(
                "transition.template_shell.known_ai_template_shell",
                "transition.template_shell",
                "KNOWN_AI_TEMPLATE_SHELL",
                "known-ai-shell/v1",
                shell_matches,
                len(units),
            )
        )

    opening_groups: dict[str, list[tuple[dict[str, Any], int, int]]] = defaultdict(list)
    for unit in units:
        chinese_matches = list(CHINESE_RE.finditer(unit["text"]))
        if len(chinese_matches) < 4:
            continue
        selected = chinese_matches[:4]
        key = "".join(match.group(0) for match in selected)
        opening_groups[key].append((unit, selected[0].start(), selected[-1].end()))
    repeated = [matches for matches in opening_groups.values() if len({m[0]["unit_id"] for m in matches}) >= 3]
    if repeated:
        repeated.sort(key=lambda matches: (-len(matches), matches[0][0]["unit_id"]))
        controls.append(
            _negative_feature(
                "transition.repeated_opening.repeated_paragraph_opening",
                "transition.repeated_opening",
                "REPEATED_PARAGRAPH_OPENING",
                "repeated-opening/v1",
                repeated[0],
                len(units),
            )
        )
    return controls


def _profile_confidence(chars: int, complete_units: int) -> str:
    if chars < 300:
        return "DEFAULT"
    if chars < 1000:
        return "LOW"
    if chars >= 5000 and complete_units >= 3:
        return "HIGH"
    return "MEDIUM"


def _manifest_self_hash(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return _sha256_bytes(_canonical_json_bytes(payload))


def _role_runs(roles: bytearray, offsets: Sequence[int], raw: bytes, sample_id: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not roles:
        return runs
    reverse_roles = {index: role for index, role in enumerate(ROLES)}
    start = 0
    current = roles[0]
    for index in range(1, len(roles) + 1):
        if index == len(roles) or roles[index] != current:
            byte_start = int(offsets[start])
            byte_end = int(offsets[index])
            if byte_end > byte_start:
                runs.append(
                    {
                        "sample_id": sample_id,
                        "byte_start": byte_start,
                        "byte_end": byte_end,
                        "role": reverse_roles[current],
                        "range_sha256": _sha256_bytes(raw[byte_start:byte_end]),
                    }
                )
            if index < len(roles):
                start = index
                current = roles[index]
    return runs


def _unit_blocks(author_view: str) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start = 0
    for separator in re.finditer(r"\n[ \t]*\n+", author_view):
        if separator.start() > start:
            blocks.append((start, separator.start()))
        start = separator.end()
    if start < len(author_view):
        blocks.append((start, len(author_view)))
    return blocks


def build_voice_profile(
    *,
    sample_spec: Path,
    allowed_root: Path,
    profile_id: str,
    scene: str,
    revision: int = 1,
    source_date_epoch: int | None = None,
    max_file_bytes: int = 8 * 1024 * 1024,
    max_total_bytes: int = 32 * 1024 * 1024,
    max_units: int = 5000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not PROFILE_ID_RE.fullmatch(profile_id):
        raise ValueError("--profile-id is invalid")
    if scene not in {"AUTO", *SCENES}:
        raise ValueError("--scene must be AUTO, COURSE, MODELING, RESEARCH, or GENERAL")
    _require_int(revision, "revision", minimum=1)
    if revision != 1:
        raise ValueError("revision > 1 requires an explicit supersedes hash; v1 CLI only builds revision 1")
    if max_file_bytes < 1 or max_total_bytes < 1 or max_units < 1:
        raise ValueError("resource limits must be positive")
    if source_date_epoch is not None and (not _is_int(source_date_epoch) or source_date_epoch < 0):
        raise ValueError("--source-date-epoch must be a non-negative integer")
    root = allowed_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--allowed-root must be a directory")
    sample_spec_object = _load_json_strict(sample_spec)
    samples = _validate_spec(sample_spec_object)
    sample_spec_sha256 = _sha256_bytes(_canonical_json_bytes(sample_spec_object))

    total_bytes = 0
    sample_records: list[dict[str, Any]] = []
    all_role_ranges: list[dict[str, Any]] = []
    runtime_units: list[dict[str, Any]] = []
    runtime_complete_units: list[dict[str, Any]] = []
    runtime_samples: list[dict[str, Any]] = []
    protected_range_count = 0
    excluded_range_count = 0

    for sample in samples:
        path = _safe_sample_path(root, sample["locator"])
        expected_identity = _stat_identity(path.lstat())
        raw = _read_frozen(path, max_file_bytes, expected_identity)
        total_bytes += len(raw)
        if total_bytes > max_total_bytes:
            raise ValueError("samples exceed --max-total-bytes")
        file_hash = _sha256_bytes(raw)
        base_record: dict[str, Any] = {
            "sample_id": sample["sample_id"],
            "locator": sample["locator"],
            "origin": sample["origin"],
            "scene": sample["scene"],
            "complete_unit": sample["complete_unit"],
            "encoding": "UTF-8",
            "decode_status": "PASS",
            "file_size": len(raw),
            "file_sha256": file_hash,
            "role_map_sha256": "0" * 64,
            "author_view_sha256": "0" * 64,
            "complete_unit_sha256": "0" * 64,
            "complete_unit_dedup_cluster_id": "",
            "complete_unit_dedup_relation": "NONE",
            "complete_unit_is_representative": False,
            "analysis_unit_ids": [],
            "readable_author_chars_before_dedup": 0,
            "readable_author_chars_after_dedup": 0,
        }
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            base_record["encoding"] = "UNKNOWN"
            base_record["decode_status"] = "SKIPPED_INVALID_UTF8"
            sample_records.append(base_record)
            continue
        if "\x00" in text or _looks_mojibake(text):
            base_record["decode_status"] = "SKIPPED_OCR_OR_MOJIBAKE"
            sample_records.append(base_record)
            continue
        offsets = _byte_offsets(text)
        if offsets[-1] != len(raw):
            raise ValueError(f"UTF-8 byte map mismatch for {sample['locator']}")
        trusted = sample["origin"] in ELIGIBLE_ORIGINS
        default_role = sample["default_role"] if trusted else "unknown"
        role_codes = {role: index for index, role in enumerate(ROLES)}
        roles = bytearray([role_codes[default_role]]) * len(text)
        for range_index, role_range in enumerate(sample["role_ranges"]):
            if role_range["byte_end"] > len(raw):
                raise ValueError(f"role range exceeds sample bytes: {sample['sample_id']}[{range_index}]")
            start = _byte_to_char(offsets, role_range["byte_start"], "role_range.byte_start")
            end = _byte_to_char(offsets, role_range["byte_end"], "role_range.byte_end")
            role = role_range["role"] if trusted else "unknown"
            roles[start:end] = bytearray([role_codes[role]]) * (end - start)
        for start, end, role in _automatic_protected_spans(text):
            code = role_codes[role]
            for index in range(start, end):
                if roles[index] == role_codes["author"]:
                    roles[index] = code
        role_map = _role_runs(roles, offsets, raw, sample["sample_id"])
        all_role_ranges.extend(role_map)
        protected_range_count += sum(1 for item in role_map if item["role"] not in {"author", "unknown"})
        excluded_range_count += sum(1 for item in role_map if item["role"] == "unknown")
        base_record["role_map_sha256"] = _stable_hash(role_map)
        author_chars = [
            char if roles[index] == role_codes["author"] else ("\n" if char in "\r\n" else " ")
            for index, char in enumerate(text)
        ]
        author_view = unicodedata.normalize("NFC", "".join(author_chars).replace("\r\n", "\n").replace("\r", "\n"))
        # NFC could change character indices. Chinese academic prose overwhelmingly
        # uses precomposed characters; fail safely instead of publishing wrong anchors.
        if len(author_view) != len(text):
            base_record["decode_status"] = "SKIPPED_NFC_INDEX_DRIFT"
            sample_records.append(base_record)
            continue
        base_record["author_view_sha256"] = _sha256_bytes(author_view.encode("utf-8"))
        sample_runtime = {
            "raw": raw,
            "text": text,
            "byte_offsets": offsets,
            "record": base_record,
        }
        runtime_samples.append(sample_runtime)
        clean_for_complete: list[str] = []
        for block_start, block_end in _unit_blocks(author_view):
            block = author_view[block_start:block_end]
            if not CHINESE_RE.search(block):
                continue
            dedup_view = _normalize_dedup(block)
            if not dedup_view:
                continue
            if len(runtime_units) >= max_units:
                raise ValueError("analysis units exceed --max-units")
            unit_id = f"unit-{len(runtime_units) + 1:06d}"
            chinese_chars = _chinese_count(block)
            unit = {
                "unit_id": unit_id,
                "sample_id": sample["sample_id"],
                "scene": sample["scene"],
                "complete_unit": sample["complete_unit"],
                "char_start": block_start,
                "char_end": block_end,
                "byte_start": int(offsets[block_start]),
                "byte_end": int(offsets[block_end]),
                "text": block,
                "dedup_view": dedup_view,
                "canonical_author_sha256": _sha256_bytes(unicodedata.normalize("NFC", block).encode("utf-8")),
                "chinese_chars": chinese_chars,
                "_sample": sample_runtime,
            }
            runtime_units.append(unit)
            clean_for_complete.append(dedup_view)
            base_record["analysis_unit_ids"].append(unit_id)
            base_record["readable_author_chars_before_dedup"] += chinese_chars
        complete_view = "\n".join(clean_for_complete)
        if complete_view:
            base_record["complete_unit_sha256"] = _sha256_bytes(complete_view.encode("utf-8"))
            if sample["complete_unit"] and trusted:
                runtime_complete_units.append(
                    {
                        "unit_id": f"complete-{len(runtime_complete_units) + 1:06d}",
                        "dedup_view": complete_view,
                        "record": base_record,
                    }
                )
        sample_records.append(base_record)

    _near_duplicate_clusters(runtime_units)
    _near_duplicate_clusters(runtime_complete_units)
    for complete in runtime_complete_units:
        record = complete["record"]
        record["complete_unit_dedup_cluster_id"] = complete["dedup_cluster_id"]
        record["complete_unit_dedup_relation"] = complete["dedup_relation"]
        record["complete_unit_is_representative"] = complete["is_representative"]
    representatives = [unit for unit in runtime_units if unit["is_representative"]]
    for unit in representatives:
        unit["_sample"]["record"]["readable_author_chars_after_dedup"] += unit["chinese_chars"]

    readable_chars = sum(unit["chinese_chars"] for unit in representatives)
    unique_complete_units = sum(
        1 for unit in runtime_complete_units if unit["is_representative"]
    )
    sample_scenes = sorted({unit["scene"] for unit in representatives})

    analysis_manifest: list[dict[str, Any]] = []
    for unit in runtime_units:
        analysis_manifest.append(
            {
                "unit_id": unit["unit_id"],
                "sample_id": unit["sample_id"],
                "byte_start": unit["byte_start"],
                "byte_end": unit["byte_end"],
                "canonical_author_sha256": unit["canonical_author_sha256"],
                "dedup_sha256": unit["dedup_sha256"],
                "dedup_cluster_id": unit["dedup_cluster_id"],
                "dedup_relation": unit["dedup_relation"],
                "is_representative": unit["is_representative"],
                "readable_author_chars": unit["chinese_chars"],
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_date_epoch": source_date_epoch,
        "allowed_root_id": _sha256_bytes(str(root).casefold().encode("utf-8"))[:16],
        "hash_spec": {
            "algorithm": "SHA-256",
            "json_canonicalization": "PYTHON-SORTED-UTF8/v1",
            "text_integrity_view": "UTF8-NFC-LF/v1",
            "dedup_view": "VOICE-DEDUP/v1",
            "sample_spec_view": "STRICT-JSON-CANONICAL/v1",
        },
        "sample_spec_sha256": sample_spec_sha256,
        "policy_binding": {
            "role_policy_sha256": ROLE_POLICY_SHA256,
            "dedup_policy_sha256": DEDUP_POLICY_SHA256,
            "unitizer_sha256": _stable_hash({"version": "paragraph-unitizer/v1", "separator": "blank-line"}),
        },
        "samples": sample_records,
        "role_ranges": all_role_ranges,
        "analysis_units": analysis_manifest,
        "aggregate": {
            "requested_samples": len(samples),
            "accepted_samples": sum(
                1
                for record in sample_records
                if record["decode_status"] == "PASS"
                and record["origin"] in ELIGIBLE_ORIGINS
                and record["readable_author_chars_before_dedup"] > 0
            ),
            "rejected_samples": sum(
                1
                for record in sample_records
                if record["decode_status"] != "PASS"
                or record["origin"] not in ELIGIBLE_ORIGINS
                or record["readable_author_chars_before_dedup"] == 0
            ),
            "readable_author_chars": readable_chars,
            "unique_analysis_units": len(representatives),
            "unique_complete_units": unique_complete_units,
            "protected_ranges": protected_range_count,
            "excluded_ranges": excluded_range_count,
            "exact_duplicate_units": sum(1 for unit in runtime_units if unit["dedup_relation"] == "EXACT"),
            "near_duplicate_units": sum(1 for unit in runtime_units if unit["dedup_relation"] == "NEAR"),
        },
    }
    manifest["manifest_sha256"] = _manifest_self_hash(manifest)

    binding_scene = scene
    if scene == "AUTO":
        binding_scene = sample_scenes[0] if len(sample_scenes) == 1 else "GENERAL"
    confidence = _profile_confidence(readable_chars, unique_complete_units)
    sample_binding = {
        "manifest_sha256": manifest["manifest_sha256"],
        "readable_author_chars": readable_chars,
        "unique_analysis_units": len(representatives),
        "unique_complete_units": unique_complete_units,
        "sample_scenes": sample_scenes,
    }
    if confidence == "DEFAULT":
        profile = build_scene_default_profile(binding_scene)
        profile["sample_binding"] = sample_binding
        profile["defaults"]["reason"] = "NO_ELIGIBLE_AUTHOR_TEXT" if readable_chars == 0 else "BELOW_300_AUTHOR_CHARS"
        profile["profile_sha256"] = canonical_profile_sha256(profile)
        validate_profile_object(profile)
        return manifest, profile

    features = _build_features(representatives, confidence)
    negative_controls = _build_negative_controls(representatives)
    has_counterexample = any(feature["evidence"]["counterexample_count"] > 0 for feature in features)
    scene_evidence_compatible = sample_scenes == [binding_scene]
    validation_status = (
        "PASS"
        if features
        and (negative_controls or has_counterexample)
        and scene_evidence_compatible
        else "REVIEW"
    )
    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_id": profile_id,
        "version": revision,
        "revision": revision,
        "supersedes_profile_sha256": None,
        "profile_kind": "PERSONAL",
        "source_kind": "AUTHOR_PROFILE",
        "binding_scene": binding_scene,
        "validation_status": validation_status,
        "confidence": confidence,
        "sample_binding": sample_binding,
        "policy_binding": _policy_binding(),
        "features": features,
        "negative_controls": negative_controls,
        "defaults": {
            "use_scene_default": False,
            "scene": binding_scene,
            "reason": None,
            "disclosure_required": False,
            "personal_voice_claim_allowed": validation_status == "PASS",
        },
        "scene_default": None,
        "claims": {
            "identity_verified": False,
            "author_personality_inferred": False,
            "academic_correctness": "NOT_EVALUATED",
            "sample_text_embedded": False,
        },
    }
    profile["profile_sha256"] = canonical_profile_sha256(profile)
    validate_profile_object(profile)
    return manifest, profile


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json_bytes(value) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-spec", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--scene", choices=("AUTO", *SCENES), default="AUTO")
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--source-date-epoch", type=int)
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-total-bytes", type=int, default=32 * 1024 * 1024)
    parser.add_argument("--max-units", type=int, default=5000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest, profile = build_voice_profile(
            sample_spec=args.sample_spec,
            allowed_root=args.allowed_root,
            profile_id=args.profile_id,
            scene=args.scene,
            revision=args.revision,
            source_date_epoch=args.source_date_epoch,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
            max_units=args.max_units,
        )
        _atomic_write_json(args.manifest_out, manifest)
        _atomic_write_json(args.output, profile)
    except (OSError, ValueError) as exc:
        if isinstance(exc, FileNotFoundError):
            error_code = "INPUT_NOT_FOUND"
        elif isinstance(exc, PermissionError):
            error_code = "INPUT_PERMISSION_DENIED"
        elif isinstance(exc, OSError):
            error_code = "INPUT_READ_FAILED"
        else:
            error_code = "INPUT_CONTRACT_INVALID"
        result = {
            "status": "FAIL",
            "error_code": error_code,
            "error": "Voice-profile input could not be accepted; inspect the local invocation and files.",
        }
        print(
            json.dumps(result, ensure_ascii=False, sort_keys=True)
            if args.format == "json"
            else f"FAIL: {error_code}"
        )
        return 1
    result = {
        "status": profile["validation_status"],
        "profile_kind": profile["profile_kind"],
        "confidence": profile["confidence"],
        "profile_sha256": profile["profile_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "readable_author_chars": profile["sample_binding"]["readable_author_chars"],
        "unique_analysis_units": profile["sample_binding"]["unique_analysis_units"],
        "unique_complete_units": profile["sample_binding"]["unique_complete_units"],
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"{result['status']}: {result['profile_kind']} {result['confidence']} "
            f"chars={result['readable_author_chars']} units={result['unique_analysis_units']} "
            f"profile_sha256={result['profile_sha256']}"
        )
    return 0 if profile["validation_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
