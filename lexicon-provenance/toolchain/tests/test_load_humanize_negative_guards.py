import importlib.util
import json
import sys
import unittest
from pathlib import Path


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
SCRIPT = SKILL / "scripts" / "load_humanize_negative_guards.py"
SPEC = importlib.util.spec_from_file_location("load_humanize_negative_guards", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
loader = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = loader
SPEC.loader.exec_module(loader)


class NegativeGuardRegistryTests(unittest.TestCase):
    def minimal_registry(self) -> dict:
        return {
            "schema_version": loader.REGISTRY_SCHEMA,
            "registry_id": loader.REGISTRY_ID,
            "guards": [
                {
                    "id": "NEGATIVE-TEST-01",
                    "scene": "ALL",
                    "detector": {
                        "type": "regex_groups/v1",
                        "minimum_groups": 1,
                        "pattern_groups": [
                            {
                                "id": "shell",
                                "regex": "不是.{1,20}而是",
                                "minimum_occurrences": 2,
                            }
                        ],
                    },
                }
            ],
        }

    def encode(self, payload: dict) -> bytes:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def test_full_catalog_exposes_only_negative_runtime_fields(self) -> None:
        result = loader.load_negative_guard_registry()
        self.assertEqual("FULL_AUDIT_CATALOG", result["source_format"])
        self.assertEqual(5, result["summary"]["guard_count"])
        self.assertEqual(6, result["summary"]["audit_only_guard_count"])
        self.assertTrue(all(set(guard) == {"id", "scene", "detector", "status"} for guard in result["guards"]))
        serialized = json.dumps(result["guards"], ensure_ascii=False)
        for positive_id in ("COURSE-DECISION-01", "MODELING-METRIC-ROLE-01"):
            self.assertNotIn(positive_id, serialized)
        for audit_only_id in (
            "NEGATIVE-MODELING-README-SHELL-01",
            "GENERAL-NEG-OPINION-AS-EVIDENCE",
            "GENERAL-NEG-OCR-AND-TEXTBOOK",
        ):
            self.assertNotIn(audit_only_id, serialized)
        self.assertRegex(result["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["registry_sha256"], r"^[0-9a-f]{64}$")

        recap = next(
            guard
            for guard in result["guards"]
            if guard["id"] == "NEGATIVE-REPORT-REPEATED-RECAP-LISTS-01"
        )
        self.assertEqual("ALL", recap["scene"])
        self.assertEqual(
            {
                "type": "structured_repeated_list/v1",
                "block_role": {
                    "heading_leaf_regex": (
                        "^(?:摘要|4[.]6 最短执行版|5[.]3 最后只记这几句话)$"
                    )
                },
                "thresholds": {
                    "minimum_blocks": 3,
                    "minimum_items_per_block": 6,
                },
                "shared_anchor": {
                    "mode": "MAXIMAL_HAN_NGRAM",
                    "minimum_han_chars": 5,
                    "maximum_han_chars": 12,
                    "minimum_block_coverage": 3,
                },
            },
            recap["detector"],
        )

        catalog = json.loads(loader.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        source = next(
            item
            for item in catalog["sources"]
            if item["id"] == "SOURCE-CET6-REPORT-EARLY"
        )
        self.assertEqual(["REPORT"], source["scene_scope"])
        card = next(
            item for item in catalog["action_cards"] if item["id"] == recap["id"]
        )
        self.assertEqual(
            [
                {
                    "source_id": "SOURCE-CET6-REPORT-EARLY",
                    "line_start": 73,
                    "line_end": 83,
                },
                {
                    "source_id": "SOURCE-CET6-REPORT-EARLY",
                    "line_start": 844,
                    "line_end": 859,
                },
                {
                    "source_id": "SOURCE-CET6-REPORT-EARLY",
                    "line_start": 964,
                    "line_end": 979,
                },
            ],
            card["source_refs"],
        )

    def test_detector_registry_round_trips_canonically(self) -> None:
        first = loader.parse_negative_guard_registry(self.encode(self.minimal_registry()))
        second = loader.parse_negative_guard_registry(self.encode(self.minimal_registry()))
        self.assertEqual("DETECTOR_ONLY_REGISTRY", first["source_format"])
        self.assertEqual(first["registry_sha256"], second["registry_sha256"])
        self.assertEqual("AVAILABLE", first["guards"][0]["status"])

    def test_structured_repeated_list_detector_is_strict_and_canonical(self) -> None:
        payload = self.minimal_registry()
        payload["guards"][0]["detector"] = {
            "type": "structured_repeated_list/v1",
            "block_role": {"heading_leaf_regex": "^(?:摘要|结论)$"},
            "thresholds": {
                "minimum_blocks": 3,
                "minimum_items_per_block": 6,
            },
            "shared_anchor": {
                "mode": "MAXIMAL_HAN_NGRAM",
                "minimum_han_chars": 5,
                "maximum_han_chars": 12,
                "minimum_block_coverage": 3,
            },
        }
        parsed = loader.parse_negative_guard_registry(self.encode(payload))
        self.assertEqual(
            payload["guards"][0]["detector"],
            parsed["guards"][0]["detector"],
        )

        mutations = []
        for label, mutate in (
            (
                "unknown type",
                lambda detector: detector.update(
                    {"type": "structured_repeated_list/v2"}
                ),
            ),
            (
                "too few blocks",
                lambda detector: detector["thresholds"].update(
                    {"minimum_blocks": 2}
                ),
            ),
            (
                "coverage exceeds blocks",
                lambda detector: detector["shared_anchor"].update(
                    {"minimum_block_coverage": 4}
                ),
            ),
            (
                "unknown field",
                lambda detector: detector.update({"fallback": "regex_groups/v1"}),
            ),
        ):
            candidate = json.loads(json.dumps(payload, ensure_ascii=False))
            mutate(candidate["guards"][0]["detector"])
            mutations.append((label, candidate))
        for label, candidate in mutations:
            with self.subTest(label=label):
                with self.assertRaises(loader.NegativeGuardRegistryError):
                    loader.parse_negative_guard_registry(self.encode(candidate))

    def test_strict_json_rejects_duplicate_unknown_and_nonfinite_values(self) -> None:
        cases = {
            "duplicate": b'{"schema_version":"humanize-negative-guard-registry/v1","schema_version":"humanize-negative-guard-registry/v1","registry_id":"humanize-academic-chinese/corpus-negative-guards/v1","guards":[]}',
            "unknown": self.encode({**self.minimal_registry(), "sources": []}),
            "nonfinite": self.encode({**self.minimal_registry(), "extra": float("nan")}),
            "invalid_utf8": b"\xff",
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(loader.NegativeGuardRegistryError):
                    loader.parse_negative_guard_registry(raw)

    def test_guard_contract_rejects_scene_ids_regex_and_threshold_drift(self) -> None:
        mutations = []
        for field, value in (("scene", "UNKNOWN"), ("id", "bad id")):
            payload = self.minimal_registry()
            payload["guards"][0][field] = value
            mutations.append((field, payload))
        payload = self.minimal_registry()
        payload["guards"][0]["detector"]["pattern_groups"][0]["regex"] = "("
        mutations.append(("regex", payload))
        payload = self.minimal_registry()
        payload["guards"][0]["detector"]["minimum_groups"] = 2
        mutations.append(("minimum_groups", payload))
        payload = self.minimal_registry()
        payload["guards"][0]["detector"]["pattern_groups"][0]["minimum_occurrences"] = True
        mutations.append(("minimum_occurrences", payload))
        for name, candidate in mutations:
            with self.subTest(name=name):
                with self.assertRaises(loader.NegativeGuardRegistryError):
                    loader.parse_negative_guard_registry(self.encode(candidate))

    def test_duplicate_guard_id_is_rejected(self) -> None:
        payload = self.minimal_registry()
        payload["guards"].append(json.loads(json.dumps(payload["guards"][0])))
        with self.assertRaisesRegex(loader.NegativeGuardRegistryError, "unique"):
            loader.parse_negative_guard_registry(self.encode(payload))

    def test_full_catalog_cannot_widen_negative_guard_permission_locally(self) -> None:
        catalog_raw = loader.DEFAULT_REGISTRY.read_bytes()
        trust = json.loads(loader.DEFAULT_SOURCE_TRUST_POLICY.read_text(encoding="utf-8"))
        trust["origin_decisions"]["UNKNOWN"]["allowed_uses"].append("NEGATIVE_GUARD")
        with self.assertRaisesRegex(
            loader.NegativeGuardRegistryError, "decision matrix drifted"
        ):
            loader.parse_negative_guard_registry(
                catalog_raw,
                source_trust_policy_raw=self.encode(trust),
            )

    def test_audit_only_origins_never_enter_runtime_guard_set(self) -> None:
        result = loader.load_negative_guard_registry()
        active = {guard["id"] for guard in result["guards"]}
        audit_only = set(result["summary"]["audit_only_guard_ids"])
        self.assertTrue(active.isdisjoint(audit_only))
        self.assertEqual(
            {
                "NEGATIVE-MODELING-README-SHELL-01",
                "GENERAL-NEG-GOVERNANCE-VOICE",
                "GENERAL-NEG-RESEARCH-JOURNAL-OVERFIT",
                "GENERAL-NEG-OPINION-AS-EVIDENCE",
                "GENERAL-NEG-OCR-AND-TEXTBOOK",
                "GENERAL-NEG-API-TEMPLATE",
            },
            audit_only,
        )


if __name__ == "__main__":
    unittest.main()
