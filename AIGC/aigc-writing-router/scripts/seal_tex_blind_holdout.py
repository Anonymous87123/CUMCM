#!/usr/bin/env python3
"""Seal a TeX draft/candidate holdout and the rules used for that release.

Public interface:
    python seal_tex_blind_holdout.py --spec holdout-spec.json \
        --pairs holdout-pairs.json --key blind-run/evaluation-key.json \
        --packet blind-run/evaluation-packet.json \
        --ratings-template blind-run/ratings-template.csv \
        --review-page blind-run/review.html \
        --review-bundle blind-run/review-bundle.json \
        --rule-file rules.py --release-id RELEASE --output holdout-seal.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapter_core import sha256_file, write_json
from render_style_benchmark_review import audit_bundle as audit_review_bundle


SCORING_PROTOCOL = "aigc-blind-scoring/v2"


def _json(path: Path, schema: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise ValueError(f"{path.name} must use {schema}")
    return value


def _artifact(path: Path, schema: str | None = None) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    result: dict[str, Any] = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if schema is not None:
        result["schema"] = schema
    return result


def _pair_ids(payload: dict[str, Any], key: str) -> list[str]:
    records = payload.get("pairs")
    if not isinstance(records, list) or not records:
        raise ValueError("pair list must be non-empty")
    values = [str(record.get(key, "")) for record in records if isinstance(record, dict)]
    if len(values) != len(records) or any(not value for value in values) or len(set(values)) != len(values):
        raise ValueError("pair ids must be non-empty and unique")
    return values


def seal(
    spec_path: Path,
    pairs_path: Path,
    key_path: Path,
    packet_path: Path,
    ratings_template: Path,
    review_page: Path,
    review_bundle: Path,
    rule_files: list[Path],
    release_id: str,
    output: Path,
) -> dict[str, Any]:
    if not release_id.strip():
        raise ValueError("release_id is required")
    if not rule_files:
        raise ValueError("at least one rule file is required")
    spec_path, pairs_path = spec_path.resolve(), pairs_path.resolve()
    key_path, packet_path = key_path.resolve(), packet_path.resolve()
    ratings_template = ratings_template.resolve()
    review_page, review_bundle = review_page.resolve(), review_bundle.resolve()
    spec = _json(spec_path, "aigc-tex-blind-pair-spec/v1")
    pairs = _json(pairs_path, "aigc-blind-pairs/v1")
    key = _json(key_path, "aigc-blind-key/v1")
    packet = _json(packet_path, "aigc-blind-packet/v1")

    sampling = spec.get("sampling")
    if not isinstance(sampling, dict) or sampling.get("quality_labels_used") is not False:
        raise ValueError("holdout spec must record quality_labels_used=false")
    provenance = pairs.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("pairs provenance is required")
    if provenance.get("spec", {}).get("sha256", "").casefold() != sha256_file(spec_path).casefold():
        raise ValueError("pairs do not bind the current sampling spec")
    for label in ("source", "candidate"):
        if provenance.get(label, {}).get("sha256", "").casefold() != str(spec.get(label, {}).get("sha256", "")).casefold():
            raise ValueError(f"{label} binding differs between spec and pairs")
    if str(key.get("source_pairs_sha256", "")).casefold() != sha256_file(pairs_path).casefold():
        raise ValueError("evaluation key does not bind the current pairs file")
    if str(key.get("packet_sha256", "")).casefold() != sha256_file(packet_path).casefold():
        raise ValueError("evaluation key does not bind the current packet")
    review_report = audit_review_bundle(review_bundle)
    if review_report.get("status") != "pass":
        raise ValueError(f"review bundle audit failed: {review_report.get('findings', [])}")
    review_payload = _json(review_bundle, "aigc-blind-review-bundle/v1")
    if (
        str(review_payload.get("packet", {}).get("sha256", "")).casefold()
        != sha256_file(packet_path).casefold()
        or str(review_payload.get("ratings_template", {}).get("sha256", "")).casefold()
        != sha256_file(ratings_template).casefold()
        or str(review_payload.get("review_page", {}).get("sha256", "")).casefold()
        != sha256_file(review_page).casefold()
    ):
        raise ValueError("review bundle does not bind the current packet, template, and page")

    spec_ids = _pair_ids(spec, "id")
    if spec_ids != _pair_ids(pairs, "id") or spec_ids != _pair_ids(key, "pair_id") or spec_ids != _pair_ids(packet, "pair_id"):
        raise ValueError("pair order or ids differ across sealed artifacts")

    artifacts = {
        "spec": _artifact(spec_path, "aigc-tex-blind-pair-spec/v1"),
        "pairs": _artifact(pairs_path, "aigc-blind-pairs/v1"),
        "key": _artifact(key_path, "aigc-blind-key/v1"),
        "packet": _artifact(packet_path, "aigc-blind-packet/v1"),
        "ratings_template": _artifact(ratings_template),
        "review_page": _artifact(review_page),
        "review_bundle": _artifact(review_bundle, "aigc-blind-review-bundle/v1"),
    }
    rules = [_artifact(path) for path in rule_files]
    scoring_rules = [_artifact(Path(__file__).resolve().with_name("blind_pair_evaluation.py"))]
    result = {
        "schema": "aigc-tex-blind-holdout-seal/v1",
        "state": "SEALED_UNSCORED",
        "release_id": release_id.strip(),
        "sealed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "pair_count": len(spec_ids),
        "sampling": {
            "method": sampling.get("method"),
            "seed": sampling.get("seed"),
            "eligible": sampling.get("eligible"),
            "selected": sampling.get("selected"),
            "quality_labels_used": False,
            "exclude_spec": sampling.get("exclude_spec"),
            "exclude_specs": sampling.get("exclude_specs"),
        },
        "artifacts": artifacts,
        "rule_snapshot": rules,
        "scoring_protocol": SCORING_PROTOCOL,
        "scoring_rule_snapshot": scoring_rules,
        "release_requirements": {
            "minimum_human_raters_per_pair": 2,
            "model_ratings_are_diagnostic_only": True,
            "mapping_key_visibility": "private-until-ratings-frozen",
            "current_rules_must_not_be_tuned_from_holdout_results": True,
            "review_page_provenance_free_bundle_required": True,
            "scoring_protocol_frozen": True,
        },
    }
    output = output.resolve()
    write_json(output, result)
    return {
        "schema": "aigc-tex-blind-holdout-seal-report/v1",
        "status": "pass",
        "state": result["state"],
        "pairs": len(spec_ids),
        "rules": len(rules),
        "output": str(output),
        "output_sha256": sha256_file(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--ratings-template", type=Path, required=True)
    parser.add_argument("--review-page", type=Path, required=True)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--rule-file", type=Path, action="append", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        report = seal(
            args.spec, args.pairs, args.key, args.packet, args.ratings_template,
            args.review_page, args.review_bundle,
            args.rule_file, args.release_id, args.output,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"schema": "aigc-tex-blind-holdout-seal-report/v1", "status": "fail", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"TEX BLIND HOLDOUT SEAL {report['status'].upper()} "
            f"pairs={report.get('pairs', 0)} rules={report.get('rules', 0)}"
        )
        if report.get("error"):
            print(f"[ERROR] {report['error']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
