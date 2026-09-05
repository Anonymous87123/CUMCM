#!/usr/bin/env python3
"""Tests for sealed TeX holdout drift auditing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from adapter_core import sha256_file
from audit_tex_blind_holdout import audit
from blind_pair_evaluation import prepare


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-holdout-audit-") as temp:
        root = Path(temp)
        pairs = root / "pairs.json"
        pairs.write_text(json.dumps({
            "schema": "aigc-blind-pairs/v1",
            "pairs": [{"id": "p1", "variants": [
                {"id": "source", "text": "源段落。"},
                {"id": "candidate", "text": "候选段落。"},
            ]}],
        }, ensure_ascii=False), encoding="utf-8")
        blind = root / "blind"
        prepared = prepare(pairs, blind, 7)
        dummy_spec = root / "spec.json"
        dummy_spec.write_text("{}\n", encoding="utf-8")
        rule = root / "rule.py"
        rule.write_text("RULE = 1\n", encoding="utf-8")
        artifact_paths = {
            "spec": dummy_spec,
            "pairs": pairs,
            "key": Path(prepared["key"]),
            "packet": Path(prepared["packet"]),
            "ratings_template": Path(prepared["ratings_template"]),
            "review_page": Path(prepared["review_page"]),
            "review_bundle": Path(prepared["review_bundle"]),
        }
        seal = root / "seal.json"
        payload = {
            "schema": "aigc-tex-blind-holdout-seal/v1",
            "state": "SEALED_UNSCORED",
            "release_id": "test",
            "pair_count": 1,
            "artifacts": {
                name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                for name, path in artifact_paths.items()
            },
            "rule_snapshot": [{
                "path": str(rule),
                "bytes": rule.stat().st_size,
                "sha256": sha256_file(rule),
            }],
            "scoring_protocol": "aigc-blind-scoring/v2",
            "scoring_rule_snapshot": [{
                "path": str(Path(__file__).with_name("blind_pair_evaluation.py")),
                "bytes": Path(__file__).with_name("blind_pair_evaluation.py").stat().st_size,
                "sha256": sha256_file(Path(__file__).with_name("blind_pair_evaluation.py")),
            }],
            "release_requirements": {
                "model_ratings_are_diagnostic_only": True,
                "review_page_provenance_free_bundle_required": True,
                "scoring_protocol_frozen": True,
            },
        }
        seal.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = audit(seal)
        require(report["status"] == "pass" and report["checked_files"] == 9, "valid seal audit failed", report)

        protocol_drift_seal = root / "protocol-drift-seal.json"
        protocol_payload = json.loads(seal.read_text(encoding="utf-8"))
        protocol_payload["scoring_protocol"] = "aigc-blind-scoring/v1"
        protocol_drift_seal.write_text(
            json.dumps(protocol_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        protocol_drift = audit(protocol_drift_seal)
        require(
            protocol_drift["status"] == "fail"
            and any(item["code"] == "SCORING_PROTOCOL_INVALID" for item in protocol_drift["errors"]),
            "scoring protocol downgrade passed",
            protocol_drift,
        )

        rule.write_text("RULE = 2\n", encoding="utf-8")
        drift = audit(seal)
        require(drift["status"] == "fail", "rule drift passed", drift)
        require(any(item["code"] == "SHA256_DRIFT" for item in drift["errors"]), "rule drift was not identified", drift)

    print("PASS: sealed holdout audits reject artifact or rule drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
