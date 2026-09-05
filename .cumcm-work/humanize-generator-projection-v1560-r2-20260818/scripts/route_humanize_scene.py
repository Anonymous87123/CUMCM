#!/usr/bin/env python3
"""Route one complete Chinese writing unit to a Humanize scene."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_POLICY = SKILL_DIR / "references" / "scene-routing-policy.json"
ROUTABLE_SCENES = ("COURSE", "MODELING", "RESEARCH")
VALID_REQUESTED_SCENES = {*ROUTABLE_SCENES, "GENERAL", "AUTO"}
PLACEHOLDER_RE = re.compile(r"\[\[PROTECTED:[^\]]+\]\]")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")


class RoutingPolicyError(ValueError):
    """Raised when the static routing policy is malformed."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RoutingPolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise RoutingPolicyError(f"non-finite JSON number: {value}")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise RoutingPolicyError(
            f"{label} keys mismatch: missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )


def load_policy(path: Path = DEFAULT_POLICY) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_text(encoding="utf-8")
        policy = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RoutingPolicyError(f"cannot load scene routing policy: {error}") from error
    if not isinstance(policy, dict):
        raise RoutingPolicyError("scene routing policy must be an object")
    _require_exact_keys(
        policy,
        {
            "schema_version",
            "revision",
            "purpose",
            "thresholds",
            "scenes",
            "fallback_scene",
            "ambiguity_action",
        },
        "policy",
    )
    if policy["schema_version"] != "humanize-scene-routing-policy/v1":
        raise RoutingPolicyError("unsupported scene routing policy schema")
    if not isinstance(policy["revision"], int) or policy["revision"] < 1:
        raise RoutingPolicyError("policy revision must be a positive integer")
    if policy["fallback_scene"] != "GENERAL":
        raise RoutingPolicyError("fallback_scene must be GENERAL")
    thresholds = policy["thresholds"]
    if not isinstance(thresholds, dict):
        raise RoutingPolicyError("thresholds must be an object")
    _require_exact_keys(
        thresholds,
        {
            "minimum_route_score",
            "minimum_route_margin",
            "minimum_document_prior_local_score",
        },
        "thresholds",
    )
    if any(not isinstance(thresholds[key], int) or thresholds[key] < 1 for key in thresholds):
        raise RoutingPolicyError("routing thresholds must be positive integers")
    scenes = policy["scenes"]
    if not isinstance(scenes, dict) or set(scenes) != set(ROUTABLE_SCENES):
        raise RoutingPolicyError("policy scenes must be COURSE, MODELING, and RESEARCH")
    seen_rule_ids: set[str] = set()
    for scene in ROUTABLE_SCENES:
        scene_policy = scenes[scene]
        if not isinstance(scene_policy, dict):
            raise RoutingPolicyError(f"scene {scene} must be an object")
        _require_exact_keys(scene_policy, {"rules"}, f"scene {scene}")
        rules = scene_policy["rules"]
        if not isinstance(rules, list) or not rules:
            raise RoutingPolicyError(f"scene {scene} needs rules")
        for index, rule in enumerate(rules, 1):
            if not isinstance(rule, dict):
                raise RoutingPolicyError(f"scene {scene} rule {index} must be an object")
            _require_exact_keys(
                rule,
                {"id", "scope", "regex", "weight", "max_occurrences"},
                f"scene {scene} rule {index}",
            )
            rule_id = rule["id"]
            if not isinstance(rule_id, str) or not rule_id or rule_id in seen_rule_ids:
                raise RoutingPolicyError(f"invalid or duplicate rule id: {rule_id}")
            seen_rule_ids.add(rule_id)
            if rule["scope"] not in {"heading", "body"}:
                raise RoutingPolicyError(f"rule {rule_id} has invalid scope")
            if not isinstance(rule["weight"], int) or rule["weight"] < 1:
                raise RoutingPolicyError(f"rule {rule_id} has invalid weight")
            if not isinstance(rule["max_occurrences"], int) or rule["max_occurrences"] < 1:
                raise RoutingPolicyError(f"rule {rule_id} has invalid max_occurrences")
            try:
                re.compile(rule["regex"])
            except (TypeError, re.error) as error:
                raise RoutingPolicyError(f"rule {rule_id} has invalid regex: {error}") from error
    return policy, hashlib.sha256(_canonical_json(policy)).hexdigest()


def _routing_view(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = PLACEHOLDER_RE.sub(" ", normalized)
    normalized = ZERO_WIDTH_RE.sub("", normalized)
    return normalized


def route_scene(
    heading_path: str,
    masked_text: str,
    *,
    requested_scene: str = "AUTO",
    document_prior_scene: str | None = None,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    policy, policy_sha256 = load_policy(policy_path)
    requested = requested_scene.upper()
    if requested not in VALID_REQUESTED_SCENES:
        raise ValueError(f"invalid requested scene: {requested_scene}")
    document_prior = str(document_prior_scene or "").upper()
    if document_prior and document_prior not in {*ROUTABLE_SCENES, "GENERAL"}:
        raise ValueError(f"invalid document prior scene: {document_prior_scene}")
    base = {
        "schema_version": "humanize-unit-scene-route/v1",
        "requested_scene": requested,
        "policy_schema_version": policy["schema_version"],
        "policy_revision": policy["revision"],
        "policy_sha256": policy_sha256,
        "document_prior_scene": document_prior,
    }
    if requested != "AUTO":
        return {
            **base,
            "status": "EXPLICIT",
            "final_scene": requested,
            "scores": {scene: 0 for scene in ROUTABLE_SCENES},
            "top_score": 0,
            "margin": 0,
            "ambiguous_scenes": [],
            "evidence": [],
        }

    views = {
        "heading": _routing_view(heading_path),
        "body": _routing_view(masked_text),
    }
    scores = {scene: 0 for scene in ROUTABLE_SCENES}
    evidence: list[dict[str, Any]] = []
    for scene in ROUTABLE_SCENES:
        for rule in policy["scenes"][scene]["rules"]:
            count = len(re.findall(rule["regex"], views[rule["scope"]]))
            bounded = min(count, rule["max_occurrences"])
            contribution = bounded * rule["weight"]
            scores[scene] += contribution
            if count:
                evidence.append(
                    {
                        "scene": scene,
                        "rule_id": rule["id"],
                        "scope": rule["scope"],
                        "occurrences": count,
                        "bounded_occurrences": bounded,
                        "contribution": contribution,
                    }
                )
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_score = ranked[0][1]
    top_scenes = sorted(scene for scene, score in scores.items() if score == top_score)
    second_score = max((score for _scene, score in ranked if score < top_score), default=0)
    margin = top_score - second_score if len(top_scenes) == 1 else 0
    thresholds = policy["thresholds"]
    positive_scores = [score for score in scores.values() if score > 0]
    competing_positive_scene = len(positive_scores) > 1
    if top_score == 0:
        status = "FALLBACK_GENERAL"
        final_scene = policy["fallback_scene"]
        ambiguous_scenes: list[str] = []
    elif len(top_scenes) > 1 or (
        competing_positive_scene and margin < thresholds["minimum_route_margin"]
    ):
        status = "AMBIGUOUS"
        final_scene = policy["fallback_scene"]
        ambiguous_scenes = top_scenes if len(top_scenes) > 1 else [ranked[0][0], ranked[1][0]]
    elif top_score < thresholds["minimum_route_score"]:
        status = "FALLBACK_GENERAL"
        final_scene = policy["fallback_scene"]
        ambiguous_scenes = []
    else:
        status = "ROUTED"
        final_scene = top_scenes[0]
        ambiguous_scenes = []
    prior_local_score = scores.get(document_prior, 0)
    prior_eligible = bool(
        document_prior in ROUTABLE_SCENES
        and status == "FALLBACK_GENERAL"
        and len(top_scenes) == 1
        and second_score == 0
        and prior_local_score >= thresholds["minimum_document_prior_local_score"]
        and prior_local_score == top_score
    )
    if prior_eligible:
        status = "ROUTED_DOCUMENT_PRIOR"
        final_scene = document_prior
    return {
        **base,
        "status": status,
        "final_scene": final_scene,
        "scores": scores,
        "top_score": top_score,
        "margin": margin,
        "ambiguous_scenes": ambiguous_scenes,
        "evidence": sorted(evidence, key=lambda item: (item["scene"], item["rule_id"])),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heading", default="", help="whole-unit heading path")
    parser.add_argument("--text-file", type=Path, required=True, help="UTF-8 masked unit text")
    parser.add_argument(
        "--scene",
        type=str.upper,
        choices=sorted(VALID_REQUESTED_SCENES),
        default="AUTO",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        text = args.text_file.read_text(encoding="utf-8")
        result = route_scene(
            args.heading,
            text,
            requested_scene=args.scene,
            policy_path=args.policy,
        )
    except (OSError, UnicodeError, ValueError, RoutingPolicyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"] == "AMBIGUOUS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
