import csv
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


preparer = load_module(
    "prepare_humanize_long_document",
    SKILL / "scripts" / "prepare_humanize_long_document.py",
)
finalizer = load_module(
    "finalize_humanize_long_document",
    SKILL / "scripts" / "finalize_humanize_long_document.py",
)
voice = finalizer.voice_profiles


class HumanizeDocumentStyleGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def records(before: list[str], after: list[str], *, scene: str = "RESEARCH") -> list[dict]:
        assert len(before) == len(after)
        return [
            {
                "unit_id": f"U-{index:02d}",
                "document_id": "DOC-01",
                "resolved_scene": scene,
                "expected": True,
                "state": "NO_CHANGE" if old == new else "DONE",
                "style_validation": "PASS",
                "before_masked": old,
                "after_masked": new,
            }
            for index, (old, new) in enumerate(zip(before, after), 1)
        ]

    @staticmethod
    def personal_profile() -> dict:
        code = "TEXT_OR_OBJECT_SUBJECT"
        extractor = voice.FEATURE_EXTRACTORS[code]
        extractor_sha256 = voice._stable_hash(
            {
                "rule_id": extractor["rule_id"],
                "pattern": extractor["pattern"].pattern,
                "flags": extractor["pattern"].flags,
                "code": code,
            }
        )
        return {
            "profile_kind": "PERSONAL",
            "profile_sha256": "a" * 64,
            "features": [
                {
                    "feature_key": "syntax.subject_position.text_or_object_subject",
                    "value": {"code": code},
                    "scope": ["RESEARCH"],
                    "disposition": "PREFER",
                    "evidence": {
                        "support_ratio_ppm": 1_000_000,
                        "extractor_sha256": extractor_sha256,
                    },
                }
            ],
            "negative_controls": [],
            "defaults": {"personal_voice_claim_allowed": True},
        }

    def test_personal_profile_no_change_passes_registered_feature_gate(self) -> None:
        paragraphs = [f"本文说明第{index}项内容。" for index in range(1, 7)]
        result = finalizer._audit_voice_conformance(
            self.personal_profile(),
            self.records(paragraphs, paragraphs),
            scene_routing_status="PASS",
        )

        self.assertEqual("PASS", result["status"])
        self.assertEqual("PERSONAL_PROFILE_NON_REGRESSION", result["basis"])
        self.assertFalse(result["identity_verified"])
        self.assertEqual(6, result["feature_results"][0]["after_support"])

    def test_personal_profile_material_subject_regression_is_reviewed(self) -> None:
        before = [f"本文说明第{index}项内容。" for index in range(1, 7)]
        after = [f"结果说明第{index}项内容。" for index in range(1, 7)]
        result = finalizer._audit_voice_conformance(
            self.personal_profile(),
            self.records(before, after),
            scene_routing_status="PASS",
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertIn(
            result["feature_results"][0]["reason"],
            {"MATERIAL_PREFERRED_FEATURE_REGRESSION", "SEVERE_PROFILE_FEATURE_GAP"},
        )

    def test_personal_profile_short_target_does_not_claim_conformance(self) -> None:
        paragraphs = ["本文说明甲项。", "本文说明乙项。"]
        result = finalizer._audit_voice_conformance(
            self.personal_profile(),
            self.records(paragraphs, paragraphs),
            scene_routing_status="PASS",
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertIn("INSUFFICIENT_TARGET_BLOCKS", result["review_reasons"])

    def test_cross_unit_repair_family_blocks_only_introduced_units(self) -> None:
        before = ["本段比较峰值。", "本段讨论误差。"]
        after = ["这里只比较峰值。", "这里只讨论误差。"]
        result = finalizer._audit_cross_unit_repetition(self.records(before, after))

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(["U-01", "U-02"], result["blocking_unit_ids"])
        self.assertIn(
            "LEX-REPAIR-01",
            {item.get("signal_id") for item in result["findings"]},
        )
        replay = finalizer._audit_cross_unit_repetition(self.records(before, after))
        self.assertEqual(
            [item["finding_fingerprint"] for item in result["findings"]],
            [item["finding_fingerprint"] for item in replay["findings"]],
        )
        self.assertEqual(result["blocking_unit_ids"], replay["blocking_unit_ids"])

    def test_cross_unit_repetition_missing_partition_metadata_is_reviewed(self) -> None:
        for missing in ("document_id", "resolved_scene"):
            with self.subTest(missing=missing):
                records = self.records(["本段保持原样。"], ["本段保持原样。"])
                records[0].pop(missing)

                result = finalizer._audit_cross_unit_repetition(records)

                self.assertEqual("REVIEW", result["status"])
                self.assertEqual([], result["evaluation_partitions"])
                self.assertTrue(
                    any(
                        reason.startswith(
                            "CROSS_UNIT_PARTITION_METADATA_REVIEW:"
                        )
                        for reason in result["review_reasons"]
                    )
                )

    def test_inherited_cross_unit_repair_family_is_audited_but_not_blocked(self) -> None:
        paragraphs = ["这里只比较峰值。", "这里只讨论误差。"]
        result = finalizer._audit_cross_unit_repetition(
            self.records(paragraphs, paragraphs)
        )

        self.assertEqual("PASS", result["status"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertGreaterEqual(result["inherited_finding_count"], 1)

    def test_protected_payload_is_absent_and_zero_width_cannot_bypass_gate(self) -> None:
        protected = "[[PROTECTED:P-001:0123456789ab]]"
        protected_result = finalizer._audit_cross_unit_repetition(
            self.records([protected, protected], [protected, protected])
        )
        self.assertEqual("PASS", protected_result["status"])
        self.assertEqual(0, protected_result["finding_count"])

        before = ["本段比较峰值。", "本段讨论误差。"]
        after = ["这\u200b里只比较峰值。", "这\u2060里只讨论误差。"]
        bypass_result = finalizer._audit_cross_unit_repetition(
            self.records(before, after)
        )
        self.assertEqual("REVIEW", bypass_result["status"])
        self.assertEqual(["U-01", "U-02"], bypass_result["blocking_unit_ids"])

    def test_registered_corpus_negative_guard_runs_across_units(self) -> None:
        before = ["甲项用于表面比较。", "乙项用于机制说明。"]
        after = ["这不是甲项而是乙项。", "这不是表面差异而是机制变化。"]
        result = finalizer._audit_cross_unit_repetition(self.records(before, after))

        self.assertEqual("REVIEW", result["status"])
        guard_findings = [
            item for item in result["findings"] if item["kind"] == "CORPUS_NEGATIVE_GUARD"
        ]
        self.assertIn(
            "NEGATIVE-TEMPLATE-01", {item["card_id"] for item in guard_findings}
        )
        self.assertRegex(result["action_catalog_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["action_profile_sha256"], r"^[0-9a-f]{64}$")

    def test_partial_scope_and_unavailable_negative_guard_cannot_pass(self) -> None:
        partial = self.records(["本段保持原样。"], ["本段保持原样。"])
        partial[0]["state"] = "PENDING"
        partial[0]["after_masked"] = None
        partial_result = finalizer._audit_cross_unit_repetition(partial)
        self.assertEqual("REVIEW", partial_result["status"])
        self.assertEqual("PARTIAL", partial_result["evaluation_scope"])

        unavailable_registry = {
            "status": "REVIEW",
            "guards": [
                {
                    "id": "NEGATIVE-TEMPLATE-UNAVAILABLE",
                    "scene": "ALL",
                    "status": "UNAVAILABLE",
                    "detector": {
                        "minimum_groups": 1,
                        "pattern_groups": [
                            {
                                "id": "shell",
                                "regex": "这里只",
                                "minimum_occurrences": 1,
                            }
                        ],
                    },
                },
            ],
            "registry_sha256": "1" * 64,
            "source_sha256": "2" * 64,
            "source_format": "TEST",
        }
        with mock.patch.object(
            finalizer.negative_guards,
            "load_negative_guard_registry",
            return_value=unavailable_registry,
        ):
            result = finalizer._audit_cross_unit_repetition(
                self.records(
                    ["本段保持原样。", "另一段保持原样。"],
                    ["本段保持原样。", "另一段保持原样。"],
                )
            )
        self.assertEqual("REVIEW", result["status"])
        self.assertIn(
            "NEGATIVE_GUARD_UNAVAILABLE:NEGATIVE-TEMPLATE-UNAVAILABLE",
            result["review_reasons"],
        )

    def test_negative_guard_registry_failure_is_review_not_silent_pass(self) -> None:
        with mock.patch.object(
            finalizer.negative_guards,
            "load_negative_guard_registry",
            side_effect=finalizer.negative_guards.NegativeGuardRegistryError("broken"),
        ):
            result = finalizer._audit_cross_unit_repetition(
                self.records(
                    ["甲段保持原样。", "乙段保持原样。"],
                    ["甲段保持原样。", "乙段保持原样。"],
                )
            )
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertIn(
            "NEGATIVE_GUARD_REGISTRY_UNAVAILABLE:NegativeGuardRegistryError",
            result["review_reasons"],
        )
        self.assertEqual("NOT_AVAILABLE", result["negative_guard_registry_status"])

    def test_logical_document_ids_resolve_include_roots_and_reject_bad_graphs(self) -> None:
        resolved = finalizer._logical_document_ids(
            [
                {"file_id": "F1", "parent_file_id": ""},
                {"file_id": "F2", "parent_file_id": "F1"},
                {"file_id": "F3", "parent_file_id": "F2"},
                {"file_id": "F4", "parent_file_id": ""},
            ]
        )
        self.assertEqual(
            {"F1": "F1", "F2": "F1", "F3": "F1", "F4": "F4"},
            resolved,
        )
        bad_manifests = (
            [
                {"file_id": "F1", "parent_file_id": ""},
                {"file_id": "F1", "parent_file_id": ""},
            ],
            [{"file_id": "F1", "parent_file_id": "F-missing"}],
            [
                {"file_id": "F1", "parent_file_id": "F2"},
                {"file_id": "F2", "parent_file_id": "F1"},
            ],
        )
        for manifest in bad_manifests:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                finalizer._logical_document_ids(manifest)

    def test_tex_structure_side_channel_exposes_only_validated_list_tokens(self) -> None:
        contents = {
            "P-BEGIN": r"\begin{itemize}",
            "P-BEGIN-NESTED": r"\begin{enumerate}[label={[\alph*]}]",
            "P-BEGIN-MULTILINE": "\\begin{enumerate}[label=\n(\\alph*)]",
            "P-BEGIN-COMMENT": "\\begin{enumerate}% option follows\n[label=(\\alph*)]",
            "P-ITEM": r"\item[标签]",
            "P-ITEM-NESTED": r"\item[tag={[x]}]",
            "P-ITEM-MULTILINE": "\\item[tag=\n{x}]",
            "P-ITEM-COMMENT": "\\item% label follows\n[tag]",
            "P-ITEM-STAR": r"\item*",
            "P-ITEM-PREFIX": r"\itemize",
            "P-ITEM-AT": r"\item@fake",
            "P-END": r"\end{itemize}",
            "P-OTHER": r"\textbf{不能回流}",
        }
        spans = {
            protected_id: {
                "protected_id": protected_id,
                "file_id": "F1",
                "sha256": finalizer.sha256(content.encode("utf-8")),
                "content": content,
            }
            for protected_id, content in contents.items()
        }
        masked = "\n".join(
            f"[[PROTECTED:{protected_id}:{span['sha256'][:12]}]]"
            for protected_id, span in spans.items()
        )
        tokens = finalizer._protected_structure_tokens(
            masked,
            file_id="F1",
            document_format="tex",
            span_map=spans,
        )
        self.assertEqual(
            {
                "P-BEGIN": {"kind": "LIST_BEGIN", "list_kind": "itemize"},
                "P-BEGIN-NESTED": {
                    "kind": "LIST_BEGIN",
                    "list_kind": "enumerate",
                },
                "P-BEGIN-MULTILINE": {
                    "kind": "LIST_BEGIN",
                    "list_kind": "enumerate",
                },
                "P-BEGIN-COMMENT": {
                    "kind": "LIST_BEGIN",
                    "list_kind": "enumerate",
                },
                "P-ITEM": {"kind": "LIST_ITEM"},
                "P-ITEM-NESTED": {"kind": "LIST_ITEM"},
                "P-ITEM-MULTILINE": {"kind": "LIST_ITEM"},
                "P-ITEM-COMMENT": {"kind": "LIST_ITEM"},
                "P-ITEM-STAR": {"kind": "LIST_ITEM", "item_prefix": "*"},
                "P-END": {"kind": "LIST_END", "list_kind": "itemize"},
            },
            tokens,
        )
        self.assertNotIn("不能回流", json.dumps(tokens, ensure_ascii=False))
        self.assertEqual(
            {},
            finalizer._protected_structure_tokens(
                masked,
                file_id="F1",
                document_format="markdown",
                span_map=spans,
            ),
        )

    def test_prepare_to_finalizer_balanced_tex_list_projection_is_consistent(self) -> None:
        cases = {
            "nested-square": (
                r"\begin{enumerate}[label={[\alph*]}]",
                r"\item[tag={[x]}]",
                "",
            ),
            "multiline": (
                "\\begin{enumerate}[label=\n(\\alph*)]",
                "\\item[tag=\n{x}]",
                "",
            ),
            "comment-separated": (
                "\\begin{enumerate}% option follows\n[label=(\\alph*)]",
                "\\item% label follows\n[tag]",
                "",
            ),
            "star-prefix": (r"\begin{enumerate}", r"\item*", "*"),
        }
        for label, (begin, item, item_prefix) in cases.items():
            with self.subTest(label=label):
                source = f"{begin}\n{item} 作者正文\n\\end{{enumerate}}\n"
                spans = preparer.protected_spans(source, ".tex", "F1")
                masked, _ids, crossing = preparer._mask_text(
                    source,
                    0,
                    len(source),
                    spans,
                )
                self.assertFalse(crossing)
                tokens = finalizer._protected_structure_tokens(
                    masked,
                    file_id="F1",
                    document_format="tex",
                    span_map={item["protected_id"]: item for item in spans},
                )
                self.assertEqual(
                    ["LIST_BEGIN", "LIST_ITEM", "LIST_END"],
                    [item["kind"] for item in tokens.values()],
                )
                projected_item = next(
                    item for item in tokens.values() if item["kind"] == "LIST_ITEM"
                )
                self.assertEqual(item_prefix, projected_item.get("item_prefix", ""))
                self.assertNotIn("label", json.dumps(tokens, ensure_ascii=False))

        fake_source = "\n".join(
            [
                r"\begin{enumerate}",
                r"\itemize 不是列表项",
                r"\item@fake 也不是列表项",
                r"\end{enumerate}",
            ]
        )
        spans = preparer.protected_spans(fake_source, ".tex", "F1")
        masked, _ids, _crossing = preparer._mask_text(
            fake_source,
            0,
            len(fake_source),
            spans,
        )
        tokens = finalizer._protected_structure_tokens(
            masked,
            file_id="F1",
            document_format="tex",
            span_map={item["protected_id"]: item for item in spans},
        )
        self.assertEqual(
            ["LIST_BEGIN", "LIST_END"],
            [item["kind"] for item in tokens.values()],
        )

    @staticmethod
    def structured_guard() -> dict:
        return {
            "id": "NEGATIVE-STRUCTURED-LIST-TEST",
            "scene": "ALL",
            "status": "AVAILABLE",
            "detector": {
                "type": "structured_repeated_list/v1",
                "block_role": {"heading_leaf_regex": r"^模块[甲乙丙]$"},
                "thresholds": {
                    "minimum_blocks": 3,
                    "minimum_items_per_block": 3,
                },
                "shared_anchor": {
                    "mode": "MAXIMAL_HAN_NGRAM",
                    "minimum_han_chars": 6,
                    "maximum_han_chars": 8,
                    "minimum_block_coverage": 3,
                },
            },
        }

    def test_finalizer_audit_consumes_structured_guard_with_block_evidence(self) -> None:
        records = []
        for index, heading in enumerate(("模块甲", "模块乙", "模块丙"), 1):
            before_items = [
                "- 处理建议如下",
                f"- 校验第{index}类账目",
                f"- 审阅第{index}类边界",
            ]
            if index == 3:
                before_items.pop()
            after_items = [
                "- 处理建议如下",
                f"- 校验第{index}类账目",
                f"- 审阅第{index}类边界",
            ]
            records.append(
                {
                    "unit_id": f"U-{index:02d}",
                    "document_id": "DOC-1",
                    "resolved_scene": "RESEARCH",
                    "format": "markdown",
                    "heading_path": heading,
                    "expected": True,
                    "state": "DONE" if index == 3 else "NO_CHANGE",
                    "style_validation": "PASS",
                    "before_masked": "\n".join(before_items),
                    "after_masked": "\n".join(after_items),
                    "protected_structure_tokens": {},
                }
            )
        registry = {
            "status": "PASS",
            "guards": [self.structured_guard()],
            "registry_sha256": "1" * 64,
            "source_sha256": "2" * 64,
            "source_format": "TEST",
        }
        with mock.patch.object(
            finalizer.negative_guards,
            "load_negative_guard_registry",
            return_value=registry,
        ):
            result = finalizer._audit_cross_unit_repetition(records)

        finding = next(
            item
            for item in result["findings"]
            if item.get("card_id") == "NEGATIVE-STRUCTURED-LIST-TEST"
        )
        self.assertEqual("humanize-cross-unit-repetition/v3", result["schema_version"])
        self.assertEqual("cross-unit-repetition/v3", result["policy"]["version"])
        self.assertEqual("structured_repeated_list/v1", finding["detector_type"])
        self.assertEqual("DOC-1", finding["document_id"])
        self.assertEqual("RESEARCH", finding["evaluated_scene"])
        self.assertEqual(2, finding["before"]["qualified_block_count"])
        self.assertEqual(3, finding["after"]["qualified_block_count"])
        self.assertEqual(["U-03"], finding["introduced_unit_ids"])
        self.assertEqual(["U-03"], result["blocking_unit_ids"])
        self.assertEqual(3, len(finding["after"]["qualified_blocks"]))
        self.assertRegex(finding["finding_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(1, len(result["logical_document_hashes"]))
        self.assertEqual(1, len(result["evaluation_partitions"]))
        self.assertEqual(
            "RESEARCH", result["evaluation_partitions"][0]["resolved_scene"]
        )
        self.assertNotIn("scene", result["evaluation_partitions"][0])

    def test_structured_guard_never_combines_documents_or_scenes(self) -> None:
        records = []
        partitions = (("DOC-A", "RESEARCH"), ("DOC-A", "RESEARCH"), ("DOC-B", "RESEARCH"))
        for index, (document_id, scene) in enumerate(partitions, 1):
            text = "\n".join(
                [
                    "- 处理建议如下",
                    f"- 校验第{index}类账目",
                    f"- 审阅第{index}类边界",
                ]
            )
            records.append(
                {
                    "unit_id": f"U-{index:02d}",
                    "document_id": document_id,
                    "resolved_scene": scene,
                    "format": "markdown",
                    "heading_path": ("模块甲", "模块乙", "模块丙")[index - 1],
                    "expected": True,
                    "state": "NO_CHANGE",
                    "style_validation": "PASS",
                    "before_masked": text,
                    "after_masked": text,
                    "protected_structure_tokens": {},
                }
            )
        registry = {
            "status": "PASS",
            "guards": [self.structured_guard()],
            "registry_sha256": "1" * 64,
            "source_sha256": "2" * 64,
            "source_format": "TEST",
        }
        with mock.patch.object(
            finalizer.negative_guards,
            "load_negative_guard_registry",
            return_value=registry,
        ):
            result = finalizer._audit_cross_unit_repetition(records)
        self.assertEqual("PASS", result["status"])
        self.assertFalse(
            any(
                item.get("card_id") == "NEGATIVE-STRUCTURED-LIST-TEST"
                for item in [*result["findings"], *result["inherited_findings"]]
            )
        )
        self.assertEqual(2, len(result["logical_document_hashes"]))

    def test_finalizer_rolls_back_locally_valid_cross_unit_repair_templates(self) -> None:
        source = self.root / "main.tex"
        source.write_text(
            "\\section{甲}\n本段只比较峰值。\n\n"
            "\\section{乙}\n本段只讨论误差。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="COURSE", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: int(item["start"]),
        )
        self.assertEqual(2, len(chunks))
        rewrites = self.root / "rewrites"
        rewrites.mkdir()
        replacements = (
            ("本段只比较峰值。", "这里只比较峰值。"),
            ("本段只讨论误差。", "这里只讨论误差。"),
        )
        for unit, (old, new) in zip(chunks, replacements):
            payload = {
                "unit_id": unit["unit_id"],
                "chunk_binding_sha256": unit["chunk_binding_sha256"],
                "voice_profile_sha256": unit["voice_profile_sha256"],
                "decision": "REWRITE",
                "masked_text": unit["masked_text"].replace(old, new),
                "keep_reasons": {},
            }
            (rewrites / f"{unit['unit_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

        result = finalizer.finalize(run_dir, rewrites)
        with (run_dir / "coverage_ledger.final.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            ledger = list(csv.DictReader(handle))

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["cross_unit_repetition_status"])
        self.assertEqual(
            {"UNRESOLVED"},
            {row["status"] for row in ledger if row["unit_id"] in result["cross_unit_repetition"]["blocking_unit_ids"]},
        )
        self.assertFalse(result["coverage_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        rendered = next((run_dir / "rendered_partial").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("这里只", rendered)
        self.assertTrue((run_dir / "validation" / "cross_unit_repetition.json").is_file())

    def test_tex_prepare_to_finalize_structured_guard_uses_protected_side_channel(self) -> None:
        source = self.root / "structured.tex"
        source.write_text(
            "\\section{模块甲}\n"
            "\\begin {itemize}[BEGIN_OPTION_SECRET]\n"
            "\\item[SECRET_LABEL] 处理建议如下 $共同校验步骤$\n"
            "\\item 校验甲类账目 \\secretcommand{PROTECTED_SECRET_PAYLOAD}\n"
            "\\item 审阅甲类边界\n"
            "\\end{itemize}\n"
            "\\section{模块乙}\n"
            "\\begin{itemize} [SECOND_BEGIN_SECRET]\n"
            "\\item[SECRET_LABEL] 处理建议如下 $共同校验步骤$\n"
            "\\item 校验乙类账目 \\secretcommand{PROTECTED_SECRET_PAYLOAD}\n"
            "\\item 审阅乙类边界\n"
            "\\end{itemize}\n"
            "\\section{模块丙}\n"
            "\\begin{itemize}\n"
            "\\item[SECRET_LABEL] 处置步骤另列 $共同校验步骤$\n"
            "\\item 校验丙类账目 \\secretcommand{PROTECTED_SECRET_PAYLOAD}\n"
            "\\item 审阅丙类边界\n"
            "\\end{itemize}\n",
            encoding="utf-8",
        )
        run_dir = self.root / "structured-run"
        preparer.prepare([source], run_dir, scene="RESEARCH", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: int(item["start"]),
        )
        self.assertEqual(3, len(chunks))
        rewrites = self.root / "structured-rewrites"
        rewrites.mkdir()
        changed_unit_id = ""
        for chunk in chunks:
            if "处置步骤另列" in chunk["masked_text"]:
                changed_unit_id = chunk["unit_id"]
                decision = "REWRITE"
                masked_text = chunk["masked_text"].replace(
                    "处置步骤另列", "处理建议如下"
                )
                payload = {
                    "unit_id": chunk["unit_id"],
                    "chunk_binding_sha256": chunk["chunk_binding_sha256"],
                    "voice_profile_sha256": chunk["voice_profile_sha256"],
                    "decision": decision,
                    "masked_text": masked_text,
                    "keep_reasons": {},
                }
            else:
                payload = {
                    "unit_id": chunk["unit_id"],
                    "chunk_binding_sha256": chunk["chunk_binding_sha256"],
                    "voice_profile_sha256": chunk["voice_profile_sha256"],
                    "decision": "NO_CHANGE",
                    "reason": "列表内容分别承担不同对象的核对职责",
                    "keep_reasons": {},
                }
            (rewrites / f"{chunk['unit_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        self.assertTrue(changed_unit_id)
        registry = {
            "status": "PASS",
            "guards": [self.structured_guard()],
            "registry_sha256": "1" * 64,
            "source_sha256": "2" * 64,
            "source_format": "TEST",
        }
        with mock.patch.object(
            finalizer.negative_guards,
            "load_negative_guard_registry",
            return_value=registry,
        ):
            result = finalizer.finalize(run_dir, rewrites)

        finding = next(
            item
            for item in result["cross_unit_repetition"]["findings"]
            if item.get("card_id") == "NEGATIVE-STRUCTURED-LIST-TEST"
        )
        self.assertEqual([changed_unit_id], finding["introduced_unit_ids"])
        self.assertEqual([changed_unit_id], result["cross_unit_repetition"]["blocking_unit_ids"])
        self.assertTrue(
            all(item["format"] == "tex" for item in finding["after"]["qualified_blocks"])
        )
        self.assertEqual(3, finding["after"]["qualified_block_count"])
        self.assertEqual("REVIEW", result["cross_unit_repetition_status"])
        self.assertFalse(result["coverage_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse(
            (run_dir / "validation" / f"{changed_unit_id}.rewrite-intent.json").exists()
        )
        self.assertFalse((run_dir / "rendered").exists())
        cross_unit_report = (
            run_dir / "validation" / "cross_unit_repetition.json"
        ).read_text(encoding="utf-8")
        for protected_payload in (
            "SECRET_LABEL",
            "PROTECTED_SECRET_PAYLOAD",
            "共同校验步骤",
            "BEGIN_OPTION_SECRET",
            "SECOND_BEGIN_SECRET",
        ):
            self.assertNotIn(protected_payload, cross_unit_report)

        rendered = next((run_dir / "rendered_partial").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        source_text = source.read_text(encoding="utf-8")
        structure_token = re.compile(
            r"\\begin\s*\{\s*(?:itemize|enumerate)\s*\}"
            r"(?:\s*\[[^\]\r\n]*\])?"
            r"|\\item(?:\[[^\]\r\n]*\])?"
            r"|\\end\s*\{\s*(?:itemize|enumerate)\s*\}"
        )
        self.assertEqual(
            structure_token.findall(source_text),
            structure_token.findall(rendered),
        )
        self.assertEqual(
            source_text.count(r"\item[SECRET_LABEL]"),
            rendered.count(r"\item[SECRET_LABEL]"),
        )
        self.assertEqual(
            source_text.count(r"\secretcommand{PROTECTED_SECRET_PAYLOAD}"),
            rendered.count(r"\secretcommand{PROTECTED_SECRET_PAYLOAD}"),
        )
        self.assertEqual(
            source_text.count("$共同校验步骤$"),
            rendered.count("$共同校验步骤$"),
        )


if __name__ == "__main__":
    unittest.main()
