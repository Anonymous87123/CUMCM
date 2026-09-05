import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "build_humanize_action_profile.py"
CATALOG = SKILL / "references" / "corpus-action-sources.json"
SPEC = importlib.util.spec_from_file_location("humanize_action_profile", SCRIPT)
profile_builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(profile_builder)


def write_catalog(
    path: Path,
    source_path: Path,
    *,
    line_end: int = 2,
    origin_class: str = "HUMAN_CONFIRMED",
) -> None:
    payload = {
        "schema_version": 2,
        "purpose": "Test-only action index without source prose.",
        "global_copy_limit": {"max_contiguous_han_chars": 7, "rule": "No copying."},
        "sources": [
            {
                "id": "SOURCE-ONE",
                "source_tier": "A1",
                "origin_class": origin_class,
                "scene_scope": ["RESEARCH"],
                "role": "positive_action_reference",
                "path": str(source_path),
                "provenance": "test",
                "use_limit": "test",
            }
        ],
        "action_cards": [
            {
                "id": "RESEARCH-ONE-01",
                "scene": "RESEARCH",
                "kind": "positive_action",
                "action": "Keep a stated scope attached to its conclusion.",
                "requires": ["scope", "claim"],
                "required_anchor_roles": ["scope"],
                "forbids": ["invented evidence"],
                "source_refs": [{"source_id": "SOURCE-ONE", "line_start": 1, "line_end": line_end}],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class HumanizeCorpusActionProfileTests(unittest.TestCase):
    def test_catalog_and_builder_exist_and_real_catalog_is_auditable(self) -> None:
        self.assertTrue(CATALOG.is_file())
        self.assertTrue(SCRIPT.is_file())

        profile = profile_builder.build_action_profile(CATALOG)

        self.assertEqual("PASS", profile["status"])
        self.assertGreaterEqual(profile["summary"]["available_action_cards"], 10)
        cards = {card["id"]: card for card in profile["action_cards"]}
        self.assertNotIn("RESEARCH-SCOPE-01", cards)
        self.assertEqual(
            "AVAILABLE",
            cards["NEGATIVE-RESEARCH-MAIN-META-SHELL-01"]["status"],
        )
        self.assertEqual("AVAILABLE", cards["COURSE-ERROR-01"]["status"])
        self.assertTrue(all(card["kind"] in {"positive_action", "negative_guard"} for card in cards.values()))
        self.assertTrue(all(card["required_anchor_roles"] for card in cards.values()))
        self.assertTrue(all(
            (card["kind"] == "negative_guard") == ("detector" in card)
            for card in cards.values()
        ))
        general_support = profile["summary"]["scene_corpus_support"]["GENERAL"]
        self.assertEqual("CORPUS_INSUFFICIENT", general_support["status"])
        self.assertEqual(0, general_support["independent_positive_source_count"])
        research_support = profile["summary"]["scene_corpus_support"]["RESEARCH"]
        self.assertEqual("CORPUS_INSUFFICIENT", research_support["status"])
        self.assertEqual(0, research_support["independent_positive_source_count"])
        self.assertEqual(0, profile["summary"]["model_generated_positive_source_count"])
        self.assertEqual(0, profile["summary"]["model_origin_unresolved_positive_source_count"])
        self.assertEqual(0, profile["summary"]["human_confirmed_positive_source_count"])
        self.assertEqual(17, profile["summary"]["provisional_available_positive_action_cards"])
        self.assertEqual(0, profile["summary"]["production_available_positive_action_cards"])
        self.assertEqual(5, profile["summary"]["runtime_authorized_negative_guard_count"])
        self.assertEqual(6, profile["summary"]["audit_only_negative_guard_count"])
        recap = cards["NEGATIVE-REPORT-REPEATED-RECAP-LISTS-01"]
        self.assertEqual("AVAILABLE", recap["status"])
        self.assertEqual("structured_repeated_list/v1", recap["detector"]["type"])
        self.assertEqual(
            [(73, 83), (844, 859), (964, 979)],
            [
                (ref["line_start"], ref["line_end"])
                for ref in recap["source_refs"]
            ],
        )
        self.assertEqual(
            "AUDIT_ONLY", cards["GENERAL-NEG-OPINION-AS-EVIDENCE"]["status"]
        )
        self.assertEqual(
            "SUPPORTED_PROVISIONAL",
            profile["summary"]["scene_corpus_support"]["COURSE"]["status"],
        )
        self.assertEqual(
            "SUPPORTED_PROVISIONAL",
            profile["summary"]["scene_corpus_support"]["MODELING"]["status"],
        )
        sources = {source["id"]: source for source in profile["sources"]}
        self.assertEqual("MODEL_GENERATED", sources["SOURCE-MAIN-TEX"]["origin_class"])
        self.assertEqual("negative_template_reference", sources["SOURCE-MAIN-TEX"]["role"])
        self.assertEqual("EXCLUDED_CONFIG", sources["SOURCE-CET6-DAMAGED"]["status"])
        self.assertEqual("EXCLUDED_CONFIG", sources["SOURCE-CET6-USER-EXCLUDED"]["status"])
        for source_id in (
            "SOURCE-MODELING-METHOD-SECTION",
            "SOURCE-MODELING-PAPER-MAIN",
            "SOURCE-MODELING-PAPER-CN",
        ):
            self.assertEqual("EXCLUDED_CONFIG", sources[source_id]["status"])
            self.assertEqual("origin_unresolved_excluded", sources[source_id]["role"])

    def test_text_summary_separates_production_and_provisional_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "profile.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = profile_builder.main(
                    ["--output", str(output), "--format", "text"]
                )

        rendered = stdout.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("PROFILE_PASS", rendered)
        self.assertIn("production_positive=0", rendered)
        self.assertIn("provisional_positive=17", rendered)
        self.assertNotIn("21 available", rendered)

    def test_invalid_negative_guard_is_strict_by_default_and_reviewable_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "negative.md"
            source.write_text("固定句壳只作负例。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1, origin_class="MODEL_GENERATED")
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["role"] = "negative_template_reference"
            payload["action_cards"][0].update(
                {
                    "id": "NEGATIVE-BROKEN-01",
                    "kind": "negative_guard",
                    "required_anchor_roles": ["template"],
                    "detector": {
                        "type": "structured_repeated_list/v1",
                        "block_role": "sensitive body",
                    },
                }
            )
            catalog.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                profile_builder.CatalogError,
                "NEGATIVE-BROKEN-01.detector is invalid",
            ):
                profile_builder.build_action_profile(catalog)

            profile = profile_builder.build_action_profile(
                catalog,
                invalid_negative_guard_as_review=True,
            )

            card = profile["action_cards"][0]
            self.assertEqual("REVIEW", profile["status"])
            self.assertEqual("UNAVAILABLE", card["status"])
            self.assertEqual("NEGATIVE-BROKEN-01", card["id"])
            self.assertIsNone(card["detector"])
            self.assertEqual("REVIEW", card["detector_validation_status"])
            self.assertEqual(
                "INVALID_NEGATIVE_GUARD_DETECTOR",
                card["detector_review_code"],
            )
            self.assertNotIn("sensitive body", json.dumps(profile, ensure_ascii=False))

    def test_model_generated_source_cannot_back_a_positive_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "model.md"
            source.write_text("这是模型生成的测试正文。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["schema_version"] = 2
            payload["sources"][0]["origin_class"] = "MODEL_GENERATED"
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(
                profile_builder.CatalogError,
                "MODEL_GENERATED.*positive_action_reference",
            ):
                profile_builder.build_action_profile(catalog)

    def test_non_author_origin_classes_cannot_back_a_positive_action(self) -> None:
        for origin_class in (
            "MODEL_ORIGIN_UNRESOLVED",
            "OCR_INHERITED",
            "THIRD_PARTY",
        ):
            with self.subTest(origin_class=origin_class), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "non-author.md"
                source.write_text("不能作为人类正向语料的测试正文。\n", encoding="utf-8")
                catalog = root / "catalog.json"
                write_catalog(
                    catalog,
                    source,
                    line_end=1,
                    origin_class=origin_class,
                )

                with self.assertRaisesRegex(
                    profile_builder.CatalogError,
                    f"{origin_class}.*positive_action_reference",
                ):
                    profile_builder.build_action_profile(catalog)

    def test_unknown_positive_source_is_provisional_not_production_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "unknown.md"
            source.write_text("仅用于测试组织动作的来源。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1, origin_class="UNKNOWN")

            profile = profile_builder.build_action_profile(catalog)

            card = profile["action_cards"][0]
            support = profile["summary"]["scene_corpus_support"]["RESEARCH"]
            self.assertEqual("PROVISIONAL", card["origin_assurance"])
            self.assertEqual(["UNKNOWN"], card["source_origin_classes"])
            self.assertEqual("SUPPORTED_PROVISIONAL", support["status"])
            self.assertEqual(0, support["production_independent_positive_source_count"])
            self.assertEqual(1, support["provisional_independent_positive_source_count"])
            self.assertEqual(1, profile["summary"]["provisional_positive_source_count"])

    def test_human_confirmed_without_external_attestation_is_provisional(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "human.md"
            source.write_text("由来源台账确认为人写的测试正文。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1)

            profile = profile_builder.build_action_profile(catalog)

            card = profile["action_cards"][0]
            support = profile["summary"]["scene_corpus_support"]["RESEARCH"]
            self.assertEqual("PROVISIONAL", card["origin_assurance"])
            self.assertFalse(card["production_positive"])
            self.assertEqual("SUPPORTED_PROVISIONAL", support["status"])
            self.assertEqual(0, support["production_independent_positive_source_count"])
            self.assertEqual(1, support["provisional_independent_positive_source_count"])
            self.assertEqual(
                "EXTERNAL_ATTESTATION_REQUIRED",
                card["source_provenance_decisions"][0]["reason_code"],
            )
            self.assertFalse(profile["source_trust_policy"]["production_path_available"])

    def test_local_catalog_cannot_attach_an_origin_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "human.md"
            source.write_text("来源声明不能自行升级。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["origin_attestation"] = {
                "status": "VERIFIED",
                "issuer": "LOCAL_CALLER",
            }
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(
                profile_builder.CatalogError,
                "origin_attestation is unsupported",
            ):
                profile_builder.build_action_profile(catalog)

    def test_local_policy_cannot_enable_production_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            policy = json.loads(
                profile_builder.DEFAULT_SOURCE_TRUST_POLICY.read_text(encoding="utf-8")
            )
            policy["production_attestation"]["enabled"] = True
            policy["production_attestation"]["accepted_schemes"] = ["CALLER_JSON"]
            policy_path = root / "trust.json"
            policy_path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
            source = root / "human.md"
            source.write_text("测试来源。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1)

            with self.assertRaisesRegex(
                profile_builder.CatalogError,
                "cannot enable production trust",
            ):
                profile_builder.build_action_profile(catalog, policy_path)

    def test_duplicate_source_ids_with_identical_bytes_count_as_one_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "same.md"
            source.write_text("相同字节不能制造独立来源。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1, origin_class="UNKNOWN")
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["scene_scope"] = ["GENERAL"]
            duplicate = dict(payload["sources"][0])
            duplicate["id"] = "SOURCE-TWO"
            payload["sources"].append(duplicate)
            payload["action_cards"][0]["scene"] = "GENERAL"
            payload["action_cards"][0]["source_refs"].append(
                {"source_id": "SOURCE-TWO", "line_start": 1, "line_end": 1}
            )
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            profile = profile_builder.build_action_profile(catalog)
            support = profile["summary"]["scene_corpus_support"]["GENERAL"]

            self.assertEqual(1, support["independent_positive_source_count"])
            self.assertEqual("CORPUS_INSUFFICIENT", support["status"])

    def test_model_generated_source_remains_usable_as_a_negative_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "model.md"
            source.write_text("问题真正要回答的不是表面现象，而是深层机制。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["schema_version"] = 2
            payload["sources"][0].update(
                {
                    "origin_class": "MODEL_GENERATED",
                    "role": "negative_template_reference",
                }
            )
            payload["action_cards"][0].update(
                {
                    "kind": "negative_guard",
                    "action": "Reject a repeated meta-question contrast shell.",
                    "required_anchor_roles": ["template"],
                    "detector": {
                        "minimum_groups": 1,
                        "pattern_groups": [
                            {
                                "id": "meta_question",
                                "regex": "真正要回答的不是.{1,40}而是",
                                "minimum_occurrences": 1,
                            }
                        ],
                    },
                }
            )
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            profile = profile_builder.build_action_profile(catalog)

            self.assertEqual("PASS", profile["status"])
            self.assertEqual("AVAILABLE", profile["action_cards"][0]["status"])
            self.assertEqual("MODEL_GENERATED", profile["sources"][0]["origin_class"])

    def test_unknown_source_negative_guard_is_audit_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "unknown.md"
            source.write_text("只用于审计的未知来源固定句壳。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1, origin_class="UNKNOWN")
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["role"] = "negative_template_reference"
            payload["action_cards"][0].update(
                {
                    "kind": "negative_guard",
                    "required_anchor_roles": ["template"],
                    "detector": {
                        "minimum_groups": 1,
                        "pattern_groups": [
                            {
                                "id": "shell",
                                "regex": "固定句壳",
                                "minimum_occurrences": 1,
                            }
                        ],
                    },
                }
            )
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            profile = profile_builder.build_action_profile(catalog)

            card = profile["action_cards"][0]
            self.assertEqual("AUDIT_ONLY", card["status"])
            self.assertFalse(card["negative_guard_runtime_authorized"])
            self.assertEqual("PASS", profile["status"])

    def test_audit_only_negative_guard_cannot_hide_an_unavailable_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "missing.md"
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=1, origin_class="UNKNOWN")
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["role"] = "negative_template_reference"
            payload["action_cards"][0].update(
                {
                    "kind": "negative_guard",
                    "required_anchor_roles": ["template"],
                    "detector": {
                        "minimum_groups": 1,
                        "pattern_groups": [
                            {
                                "id": "shell",
                                "regex": "固定句壳",
                                "minimum_occurrences": 1,
                            }
                        ],
                    },
                }
            )
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            profile = profile_builder.build_action_profile(catalog)

            card = profile["action_cards"][0]
            self.assertEqual("REVIEW", profile["status"])
            self.assertEqual("MISSING", profile["sources"][0]["status"])
            self.assertEqual("UNAVAILABLE", card["status"])
            self.assertEqual("SOURCE_UNAVAILABLE", card["source_refs"][0]["status"])
            self.assertFalse(card["negative_guard_runtime_authorized"])
            self.assertEqual(1, profile["summary"]["action_card_statuses"]["UNAVAILABLE"])
            self.assertEqual(0, profile["summary"]["audit_only_action_cards"])

    def test_general_opinion_guard_does_not_treat_legal_obligations_as_mobilization(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        card = next(
            item
            for item in catalog["action_cards"]
            if item["id"] == "GENERAL-NEG-OPINION-AS-EVIDENCE"
        )
        mobilizing = next(
            item
            for item in card["detector"]["pattern_groups"]
            if item["id"] == "mobilizing_command"
        )
        legal = (
            "行政机关必须说明理由；平台经营者必须保存交易记录；"
            "数据处理者必须履行安全保护义务。"
        )
        coaching = "考生必须牢记条件，学生务必掌握这一步。"

        self.assertEqual([], re.findall(mobilizing["regex"], legal))
        self.assertGreaterEqual(
            len(re.findall(mobilizing["regex"], coaching)),
            mobilizing["minimum_occurrences"],
        )

    def test_profile_exports_hashes_but_never_source_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.tex"
            source.write_text("私有证据短语不得进入profile\n第二行", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source)

            profile = profile_builder.build_action_profile(catalog)
            serialized = json.dumps(profile, ensure_ascii=False)

            self.assertEqual("PASS", profile["status"])
            self.assertNotIn("私有证据短语不得进入profile", serialized)
            reference = profile["action_cards"][0]["source_refs"][0]
            self.assertEqual("VERIFIED", reference["status"])
            self.assertRegex(reference["content_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(profile["summary"]["source_text_exported"] is False)

    def test_unreadable_source_is_explicit_and_blocks_its_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "damaged.tex"
            source.write_bytes(b"\x00\xff\xfe")
            catalog = root / "catalog.json"
            write_catalog(catalog, source)

            profile = profile_builder.build_action_profile(catalog)

            self.assertEqual("REVIEW", profile["status"])
            self.assertEqual("SKIPPED_UNREADABLE", profile["sources"][0]["status"])
            self.assertEqual("binary_or_nul_bytes", profile["sources"][0]["reason"])
            self.assertEqual("UNAVAILABLE", profile["action_cards"][0]["status"])
            self.assertEqual("SOURCE_UNAVAILABLE", profile["action_cards"][0]["source_refs"][0]["status"])

    def test_invalid_line_range_is_explicit_and_blocks_its_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "short.tex"
            source.write_text("only line\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source, line_end=9)

            profile = profile_builder.build_action_profile(catalog)

            self.assertEqual("REVIEW", profile["status"])
            ref = profile["action_cards"][0]["source_refs"][0]
            self.assertEqual("OUT_OF_RANGE", ref["status"])
            self.assertEqual(1, ref["source_line_count"])

    def test_excluded_source_cannot_be_used_by_an_action_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = root / "catalog.json"
            payload = {
                "schema_version": 2,
                "purpose": "test",
                "global_copy_limit": {"max_contiguous_han_chars": 7, "rule": "No copying."},
                "sources": [
                    {
                        "id": "DAMAGED",
                        "source_tier": "A1",
                        "origin_class": "UNKNOWN",
                        "scene_scope": ["ALL"],
                        "role": "unreadable_excluded",
                        "path": str(root / "skip.tex"),
                        "exclude_reason": "known damaged",
                    }
                ],
                "action_cards": [
                    {
                        "id": "ALL-ONE-01",
                        "scene": "ALL",
                        "kind": "negative_guard",
                        "action": "Never available.",
                        "requires": ["x"],
                        "required_anchor_roles": ["template"],
                        "forbids": ["y"],
                        "detector": {
                            "minimum_groups": 1,
                            "pattern_groups": [
                                {"id": "test", "regex": "永远", "minimum_occurrences": 1}
                            ],
                        },
                        "source_refs": [{"source_id": "DAMAGED", "line_start": 1, "line_end": 1}],
                    }
                ],
            }
            catalog.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(profile_builder.CatalogError, "cannot use excluded source"):
                profile_builder.build_action_profile(catalog)

    def test_positive_and_negative_cards_cannot_swap_source_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "negative.md"
            source.write_text("固定模板只作负例。\n", encoding="utf-8")
            catalog = root / "catalog.json"
            write_catalog(catalog, source)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["sources"][0]["role"] = "negative_template_reference"
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(profile_builder.CatalogError, "cannot use source role"):
                profile_builder.build_action_profile(catalog)


if __name__ == "__main__":
    unittest.main()
