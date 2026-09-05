import importlib.util
import html
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "validate_humanize_output.py"
FORWARD_FIXTURES = Path(__file__).parent / "fixtures" / "humanize_forward_v3"
FORWARD_V4_FIXTURES = Path(__file__).parent / "fixtures" / "humanize_forward_v4"
GOLD_FIXTURES = Path(__file__).parent / "fixtures" / "humanize_gold"
FORWARD_V5_FIXTURES = Path(__file__).parent / "fixtures" / "humanize_forward_v5"
FORWARD_V10_FIXTURES = Path(__file__).parent / "fixtures" / "humanize_forward_v10"
COURSE_VOICE_FLATTENING_FIXTURES = (
    Path(__file__).parent / "fixtures" / "humanize_course_voice_flattening"
)
SPEC = importlib.util.spec_from_file_location("validate_humanize_output", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class HumanizeOutputValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def pair(self, before: str, after: str, suffix: str = ".md") -> tuple[Path, Path]:
        before_path = self.root / f"before{suffix}"
        after_path = self.root / f"after{suffix}"
        before_path.write_text(before, encoding="utf-8")
        after_path.write_text(after, encoding="utf-8")
        return before_path, after_path

    def test_cli_missing_input_is_structured_fail_not_review_or_path_leak(self) -> None:
        private_root = self.root / "Alice" / "PrivateProject"
        missing_before = private_root / "student-name-before.md"
        missing_after = private_root / "student-name-after.md"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(missing_before),
                str(missing_after),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["delivery_gate_status"])
        self.assertEqual("INPUT_NOT_FOUND", payload["error_code"])
        self.assertNotIn(str(private_root), completed.stdout + completed.stderr)

    def report_scope(self, source: Path, selections: list[str]) -> Path:
        source_text = source.read_bytes().decode("utf-8-sig")
        for selection in selections:
            self.assertEqual(1, source_text.count(selection))
        report = self.root / "report.html"
        report.write_text(
            '<!doctype html><html><meta charset="utf-8"><body>'
            + "".join(f"<mark>{html.escape(selection)}</mark>" for selection in selections)
            + "</body></html>",
            encoding="utf-8",
        )
        payload = validator.detector_scope.analyze_report(report, source)
        self.assertEqual("PASS", payload["status"])
        path = self.root / "report-scope.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def assert_paired_quality_review(
        self,
        payload: dict,
        *,
        decision: str,
        changes: int | None = None,
    ) -> dict:
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("PASS", payload["candidate_assembly_status"])
        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("PENDING_EXTERNAL_REVIEW", payload["paired_quality_review_status"])
        self.assertFalse(payload["paired_quality_clearance_granted"])
        self.assertFalse(payload["humanize_quality_claim_allowed"])
        self.assertIn("paired_quality_not_evaluated", payload["review_reasons"])
        request = payload["paired_quality_review_request"]
        self.assertEqual("humanize-paired-quality-review-request/v1", request["schema"])
        self.assertEqual(decision, request["validation_context"]["decision"])
        self.assertRegex(request["request_sha256"], r"^[0-9a-f]{64}$")
        if changes is not None:
            self.assertEqual(changes, len(request["changes"]))
        return request

    def template_field_scope(
        self,
        before: Path,
        edits: list[tuple[int, str]],
        *,
        name: str = "template-field-edit-scope.json",
    ) -> Path:
        path = self.root / name
        payload = {
            "schema_version": "humanize-template-field-edit-scope/v1",
            "source_sha256": validator._sha256(before.read_bytes()),
            "edits": [
                {
                    "line": line,
                    "label": label,
                    "permission": "PAYLOAD_ONLY",
                    "reason": "用户明确授权修复原句表达，同时保持字段范围、语气和功能不变。",
                }
                for line, label in edits
            ],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def v1518_template_pair_text() -> tuple[str, str]:
        before = "\n".join(
            (
                "适用题目： 积极的、普遍认可的趋势（如：环保生活、终身学习、乐于助人、数字技能、团队精神、扎实基础、独立性、自律、实践等）。",
                "逻辑链条： 给定首句。这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行/推进这一趋势。",
                "适用题目： 带有焦虑、局限、困境、或者负面担忧的题目（如：外貌焦虑、选择过剩、老年人数字鸿沟、AI冲击人类创造力、信息爆炸、剧烈竞争等）。",
                "逻辑链条： 给定首句。这种现代文明的副作用如果任其蔓延，将会侵蚀我们的生活质量/创新活力。鉴于此，当务之急是采取理性审慎的举措加以扭转。",
                "适用题目： 强调两者同等重要、需要沟通、或者在特定平台进行多维度探索的题目（如：真实社交与虚拟网络、分歧中的友好讨论、学术与实践并重、大学探索多种可能性、社交媒体责任、师生共同成长、中国梦与个人价值等）。",
                "逻辑链条： 给定首句。它精准地勾勒出复杂时代下我们需要维持的动态平衡。因此，在紧拥新兴时代红利的同时，绝不能抛弃传统的根基或理性约束。",
            )
        ) + "\n"
        after = "\n".join(
            (
                "适用题目： 积极且普遍受到认可的趋势（如：环保生活、终身学习、乐于助人、数字技能、团队精神、扎实基础、独立性、自律、实践等）。",
                "逻辑链条： 围绕给定首句展开，说明这一趋势不仅顺应时代发展，也能成为个人/社会突破现实困境的关键。因此，我们必须持之以恒地践行/推进这一趋势。",
                "适用题目： 涉及焦虑、局限、困境或负面担忧的话题（如：外貌焦虑、选择过剩、老年人数字鸿沟、AI冲击人类创造力、信息爆炸、剧烈竞争等）。",
                "逻辑链条： 围绕给定首句展开，说明这种现代文明的副作用如果任其蔓延，将会侵蚀我们的生活质量/创新活力。鉴于此，当务之急是采取理性审慎的举措加以扭转。",
                "适用题目： 强调两者同等重要、需要沟通，或要求在特定平台进行多维度探索的话题（如：真实社交与虚拟网络、分歧中的友好讨论、学术与实践并重、大学探索多种可能性、社交媒体责任、师生共同成长、中国梦与个人价值等）。",
                "逻辑链条： 围绕给定首句展开，说明它勾勒出复杂时代中需要维持的动态平衡。因此，在把握新兴时代红利的同时，绝不能抛弃传统根基或理性约束。",
            )
        ) + "\n"
        return before, after

    def synthetic_course_transition_window(
        self,
        *,
        char_width: int,
        line_count: int,
    ) -> list[dict]:
        starts = [0, 200, 400, char_width - 2]
        lines = [1, 8, 16, line_count]
        transition_ids = [
            "COURSE-FLAT-01",
            "COURSE-FLAT-02",
            "COURSE-FLAT-03",
            "COURSE-FLAT-05",
        ]
        families = [
            "bounded_directness",
            "teaching_attention",
            "contrast_emphasis",
            "relation_fit",
        ]
        output = []
        for index, (start, line, transition_id, family) in enumerate(
            zip(starts, lines, transition_ids, families),
            1,
        ):
            span = {
                "char_start": start,
                "char_end": start + 2,
                "line": line,
                "end_line": line,
            }
            output.append(
                {
                    "occurrence_id": f"CVF-SYNTHETIC-{index}",
                    "transition_id": transition_id,
                    "family": family,
                    "change_id": f"CHANGE-{min(index, 3)}",
                    "section_binding": {
                        "before": {
                            "ordinal": 1,
                            "level": 1,
                            "heading_sha256": "a" * 64,
                        },
                        "after": {
                            "ordinal": 1,
                            "level": 1,
                            "heading_sha256": "a" * 64,
                        },
                    },
                    "removed": dict(span),
                    "introduced": dict(span),
                }
            )
        return output

    def test_safe_rewrite_passes_with_hash_evidence(self) -> None:
        before, after = self.pair("值得注意的是，峰值出现在高温组。", "峰值出现在高温组。")
        payload = validator.validate(before, after, scene="RESEARCH")
        self.assert_paired_quality_review(payload, decision="REWRITE", changes=1)
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual("NOT_EVALUATED", payload["academic_correctness"])
        self.assertTrue(payload["evidence"]["checker_executed"])
        self.assertRegex(payload["evidence"]["before_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual("NOT_PROVIDED", payload["evidence"]["protected_terms"]["status"])
        self.assertEqual("DOCUMENT", payload["evidence"]["document_scope"])

    def test_template_field_header_change_is_fail_one_even_with_payload_authorization(self) -> None:
        cases = {
            "label": (
                "适用题目： 积极趋势。\n逻辑链条： 围绕给定首句展开。\n",
                "适用话题： 积极趋势。\n逻辑链条： 围绕给定首句展开。\n",
            ),
            "separator": (
                "适用题目： 积极趋势。\n逻辑链条： 围绕给定首句展开。\n",
                "适用题目: 积极趋势。\n逻辑链条： 围绕给定首句展开。\n",
            ),
        }
        for name, (before_text, after_text) in cases.items():
            with self.subTest(name=name):
                before, after = self.pair(before_text, after_text, suffix=".tex")
                scope = self.template_field_scope(
                    before,
                    [(1, "适用题目")],
                    name=f"header-{name}.json",
                )

                payload = validator.validate(
                    before,
                    after,
                    scene="COURSE",
                    template_field_edit_scope_path=scope,
                )

                self.assertEqual("FAIL", payload["status"])
                self.assertEqual(1, payload["exit_code"])
                self.assertEqual("FAIL", payload["hard_invariant_layer_status"])
                self.assertEqual("FAIL", payload["template_field_layer_status"])
                self.assertEqual("FAIL", payload["mechanical_validation_status"])
                self.assertEqual(
                    "BLOCKED_BY_MECHANICAL_GATE",
                    payload["paired_quality_review_status"],
                )
                self.assertIn(
                    "TEMPLATE_FIELD_HEADER_CHANGED",
                    {item["code"] for item in payload["invariants"]["errors"]},
                )
                finding = next(
                    item
                    for item in payload["template_field_findings"]
                    if item["code"] == "TEMPLATE_FIELD_HEADER_CHANGED"
                )
                self.assertEqual("HEADER_CHANGE_NOT_AUTHORIZABLE", finding["authorization_status"])

    def test_unscoped_template_field_payload_edit_requires_mechanical_review(self) -> None:
        before, after = self.pair(
            "适用题目： 积极的、普遍认可的趋势。\n",
            "适用题目： 积极且普遍受到认可的趋势。\n",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["template_field_layer_status"])
        self.assertEqual("REVIEW", payload["mechanical_validation_status"])
        self.assertEqual(
            "BLOCKED_BY_MECHANICAL_GATE",
            payload["paired_quality_review_status"],
        )
        self.assertEqual("N/A", payload["template_field_edit_scope_check"]["status"])
        self.assertEqual(1, len(payload["template_field_findings"]))
        finding = payload["template_field_findings"][0]
        self.assertEqual("TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED", finding["code"])
        self.assertEqual("NOT_AUTHORIZED", finding["authorization_status"])
        self.assertEqual([], finding["change_types"])

    def test_exact_template_field_payload_authorization_passes_mechanical_gate_but_not_delivery(self) -> None:
        before, after = self.pair(
            "适用题目： 积极的、普遍认可的趋势。\n",
            "适用题目： 积极且普遍受到认可的趋势。\n",
            suffix=".tex",
        )
        scope = self.template_field_scope(before, [(1, "适用题目")])

        payload = validator.validate(
            before,
            after,
            scene="COURSE",
            template_field_edit_scope_path=scope,
        )

        request = self.assert_paired_quality_review(
            payload,
            decision="REWRITE",
            changes=1,
        )
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("PASS", payload["template_field_edit_scope_check"]["status"])
        self.assertEqual(1, payload["template_field_edit_scope_check"]["authorized_edit_count"])
        self.assertFalse(payload["template_field_edit_scope_check"]["local_clearance_supported"])
        self.assertEqual(1, len(payload["template_field_findings"]))
        finding = payload["template_field_findings"][0]
        self.assertEqual("TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED", finding["code"])
        self.assertEqual("info", finding["severity"])
        self.assertEqual("AUTHORIZED_PAYLOAD_ONLY", finding["authorization_status"])
        self.assertEqual([], finding["change_types"])
        self.assertEqual(payload["template_field_findings"], request["template_field_changes"])

    def test_v1518_authorization_does_not_clear_force_applicability_or_role_drift(self) -> None:
        before_text, after_text = self.v1518_template_pair_text()
        before, after = self.pair(before_text, after_text, suffix=".tex")
        scope = self.template_field_scope(
            before,
            [
                (1, "适用题目"),
                (2, "逻辑链条"),
                (3, "适用题目"),
                (4, "逻辑链条"),
                (5, "适用题目"),
                (6, "逻辑链条"),
            ],
        )

        payload = validator.validate(
            before,
            after,
            scene="COURSE",
            template_field_edit_scope_path=scope,
        )

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("REVIEW", payload["template_field_layer_status"])
        self.assertEqual("REVIEW", payload["mechanical_validation_status"])
        self.assertEqual(
            "BLOCKED_BY_MECHANICAL_GATE",
            payload["paired_quality_review_status"],
        )
        self.assertEqual(6, payload["template_field_edit_scope_check"]["authorized_edit_count"])

        by_line = {
            int(item["source_line"]): item
            for item in payload["template_field_findings"]
            if "source_line" in item
        }
        self.assertEqual({1, 2, 3, 4, 5, 6}, set(by_line))
        for line in (1, 4, 6):
            self.assertEqual("TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED", by_line[line]["code"])
            self.assertEqual([], by_line[line]["change_types"])

        self.assertEqual("TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT", by_line[2]["code"])
        self.assertIn("ASSERTION_FORCE_WEAKENED", by_line[2]["change_types"])

        self.assertEqual("TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT", by_line[3]["code"])
        self.assertIn("APPLICABILITY_OBJECT_CHANGED", by_line[3]["change_types"])
        self.assertIn("APPLICABILITY_PREDICATE_CHANGED", by_line[3]["change_types"])

        self.assertEqual("TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT", by_line[5]["code"])
        self.assertIn("APPLICABILITY_OBJECT_CHANGED", by_line[5]["change_types"])
        self.assertIn("CLASSIFICATION_TO_READER_INSTRUCTION_DRIFT", by_line[5]["change_types"])

    def test_template_field_scope_rejects_stale_sha_duplicate_keys_unknown_label_and_duplicate_line(self) -> None:
        before, after = self.pair(
            "适用题目： 积极趋势。\n",
            "适用题目： 积极且稳健的趋势。\n",
            suffix=".tex",
        )
        source_sha = validator._sha256(before.read_bytes())
        base_edit = {
            "line": 1,
            "label": "适用题目",
            "permission": "PAYLOAD_ONLY",
            "reason": "用户明确授权修复原句表达，同时保持字段范围和功能不变。",
        }

        stale = self.root / "stale-template-scope.json"
        stale.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-template-field-edit-scope/v1",
                    "source_sha256": "0" * 64,
                    "edits": [base_edit],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "source_sha256 does not match before"):
            validator.validate(before, after, template_field_edit_scope_path=stale)

        duplicate_key = self.root / "duplicate-key-template-scope.json"
        duplicate_key.write_text(
            "{"
            '"schema_version":"humanize-template-field-edit-scope/v1",'
            f'"source_sha256":"{source_sha}",'
            f'"source_sha256":"{source_sha}",'
            '"edits":[{'
            '"line":1,"label":"适用题目","permission":"PAYLOAD_ONLY",'
            '"reason":"用户明确授权修复原句表达，同时保持字段范围和功能不变。"'
            "}]}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            validator.validate(before, after, template_field_edit_scope_path=duplicate_key)

        unknown_label = self.root / "unknown-label-template-scope.json"
        unknown_payload = {
            "schema_version": "humanize-template-field-edit-scope/v1",
            "source_sha256": source_sha,
            "edits": [{**base_edit, "label": "适用话题"}],
        }
        unknown_label.write_text(
            json.dumps(unknown_payload, ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "label is unknown"):
            validator.validate(before, after, template_field_edit_scope_path=unknown_label)

        duplicate_line = self.root / "duplicate-line-template-scope.json"
        duplicate_line.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-template-field-edit-scope/v1",
                    "source_sha256": source_sha,
                    "edits": [base_edit, dict(base_edit)],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "duplicates source line 1"):
            validator.validate(before, after, template_field_edit_scope_path=duplicate_line)

    def test_given_first_sentence_template_text_is_not_misparsed_as_an_extra_field(self) -> None:
        text = (
            "给定首句： Learning is a lifelong journey.\n"
            "逻辑链条： 给定首句。围绕该句说明持续学习的作用。\n"
        )
        before, after = self.pair(text, text, suffix=".tex")

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual([], payload["template_field_findings"])
        self.assertEqual(0, payload["template_field_summary"]["finding_count"])

    def test_template_field_vocabulary_in_plain_prose_does_not_enter_field_contract(self) -> None:
        before, after = self.pair(
            "这个题目带有焦虑色彩，关键处更是需要说明；本文也讨论“适用题目：焦虑类”这一标签。",
            "这个话题涉及焦虑，关键处也能说明；本文仍讨论“适用题目：焦虑类”这一标签。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual([], payload["template_field_findings"])
        self.assertNotIn(
            "template_field_authorization_or_role_drift",
            payload["review_reasons"],
        )

    def test_markdown_fenced_code_field_shape_is_not_a_template_field(self) -> None:
        before, after = self.pair(
            "```text\n适用题目： 伪造字段原值。\n```\n正文保持不变。\n",
            "```text\n适用题目： 伪造字段改值。\n```\n正文保持不变。\n",
        )

        payload = validator.validate(before, after, scene="GENERAL")

        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual([], payload["template_field_findings"])
        self.assertNotIn(
            "TEMPLATE_FIELD_HEADER_CHANGED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_tex_verbatim_and_comment_field_shapes_do_not_enter_template_contract(self) -> None:
        before, after = self.pair(
            "\\begin{verbatim}\n"
            "适用题目： 伪造字段原值。\n"
            "\\end{verbatim}\n"
            "% 逻辑链条： 注释中的伪造字段原值。\n"
            "正文保持不变。\n",
            "\\begin{verbatim}\n"
            "适用题目： 伪造字段改值。\n"
            "\\end{verbatim}\n"
            "% 逻辑链条： 注释中的伪造字段改值。\n"
            "正文保持不变。\n",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="GENERAL")

        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual([], payload["template_field_findings"])
        self.assertNotIn(
            "TEMPLATE_FIELD_HEADER_CHANGED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_course_formula_caption_cleanup_preserves_inference_relations(self) -> None:
        before, after = self.pair(
            "因此\n \\(a=F/m.\\)\n于是\n \\(\\tan\\theta=\\mu.\\)",
            " \\(a=F/m.\\)\n \\(\\tan\\theta=\\mu.\\)",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertIn("SPEECH_ACT_LOGICAL_RELATION_CHANGED", warning_codes)

    def test_real_cet6_candidate_blocks_copular_comma_and_default_scope_drift(self) -> None:
        before, after = self.pair(
            "后面所有主要结论，默认都来自这同一批样本。\n"
            "第一种误判是：觉得只要记住平均位置就够了。\n"
            "第二种误判是：觉得题号相邻，原文位置也大概率相邻。\n",
            "后文的主要结论均来自这批样本。\n"
            "第一种误判是，认为只要记住平均位置就够了。\n"
            "第二种误判是，认为题号相邻，原文位置也大概率相邻。\n",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}
        introduced = [
            item
            for item in payload["introduced_findings"]
            if item["signal_id"] == "LEX-COURSE-COPULAR-COMMA-01"
        ]

        self.assertEqual("REVIEW", payload["mechanical_validation_status"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["candidate_assembly_status"])
        self.assertEqual("BLOCKED_BY_MECHANICAL_GATE", payload["paired_quality_review_status"])
        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", warning_codes)
        self.assertEqual(2, len(introduced))
        self.assertTrue(all(item["severity"] == "high" for item in introduced))

    def test_real_blind_course_voice_flattening_cluster_blocks_false_style_pass(self) -> None:
        before = COURSE_VOICE_FLATTENING_FIXTURES / "blind_before.tex"
        after = COURSE_VOICE_FLATTENING_FIXTURES / "blind_after.tex"

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("REVIEW", payload["mechanical_validation_status"])
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["paired_style_delta_layer_status"])
        self.assertIn("course_voice_flattening_cluster", payload["review_reasons"])
        self.assertEqual(
            "BLOCKED_BY_MECHANICAL_GATE",
            payload["paired_quality_review_status"],
        )
        self.assertEqual(1, len(payload["paired_style_delta_findings"]))

        finding = payload["paired_style_delta_findings"][0]
        self.assertEqual("STYLE_COURSE_VOICE_FLATTENING_CLUSTER", finding["code"])
        self.assertGreaterEqual(finding["observed"]["distinct_transition_count"], 7)
        self.assertGreaterEqual(finding["observed"]["distinct_family_count"], 3)
        self.assertGreaterEqual(finding["observed"]["changed_hunk_count"], 3)
        self.assertIn(
            "COURSE-FLAT-08",
            finding["observed"]["distinct_transition_ids"],
        )
        self.assertFalse(finding["limitations"]["authorship_inference"])
        self.assertFalse(finding["limitations"]["single_word_is_prohibited"])

        before_text = before.read_text(encoding="utf-8")
        after_text = after.read_text(encoding="utf-8")
        before_raw = before.read_bytes()
        after_raw = after.read_bytes()
        for transition in finding["transitions"]:
            removed = transition["removed"]
            introduced = transition["introduced"]
            self.assertEqual(
                removed["text"],
                before_text[removed["char_start"] : removed["char_end"]],
            )
            self.assertEqual(
                introduced["text"],
                after_text[introduced["char_start"] : introduced["char_end"]],
            )
            self.assertEqual(
                removed["text"],
                before_raw[removed["utf8_start"] : removed["utf8_end"]].decode(
                    "utf-8"
                ),
            )
            self.assertEqual(
                introduced["text"],
                after_raw[
                    introduced["utf8_start"] : introduced["utf8_end"]
                ].decode("utf-8"),
            )

    def test_course_voice_flattening_single_formalization_does_not_trigger_cluster(self) -> None:
        before, after = self.pair(
            "把原方程补成标准形式。",
            "将原方程改写为标准形式。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual("PASS", payload["paired_style_delta_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_requires_character_level_replacement_binding(self) -> None:
        unchanged = "中间这一句保持不变。"
        before, after = self.pair(
            "\n".join(
                [
                    "完全够用。保留同一对象。末尾甲。",
                    unchanged,
                    "先盯住变量。保留同一对象。末尾乙。",
                    unchanged,
                    "数值明明在变。保留同一对象。末尾丙。",
                    unchanged,
                    "两条关系接得上。保留同一对象。末尾丁。",
                ]
            ),
            "\n".join(
                [
                    "可以使用。保留同一对象。末尾足以描述。",
                    unchanged,
                    "先看变量。保留同一对象。末尾考察。",
                    unchanged,
                    "数值确实在变。保留同一对象。末尾仍随。",
                    unchanged,
                    "两条关系吻合。保留同一对象。末尾严格对应。",
                ]
            ),
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])
        self.assertEqual("PASS", payload["paired_style_delta_layer_status"])

    def test_course_voice_flattening_cluster_is_bounded_by_distance_and_lines(self) -> None:
        separator = "\n".join(f"保持原句{i:04d}。" for i in range(180))
        before, after = self.pair(
            f"完全够用。\n{separator}\n先盯住变量。\n{separator}\n"
            f"数值明明在变。\n{separator}\n两条关系接得上。",
            f"足以描述。\n{separator}\n先考察变量。\n{separator}\n"
            f"数值仍随条件变化。\n{separator}\n两条关系严格对应。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_cluster_uses_full_span_boundary(self) -> None:
        at_char_limit = self.synthetic_course_transition_window(
            char_width=1200,
            line_count=24,
        )
        over_char_limit = self.synthetic_course_transition_window(
            char_width=1201,
            line_count=24,
        )
        over_line_limit = self.synthetic_course_transition_window(
            char_width=1200,
            line_count=25,
        )

        at_limit_clusters = validator._transition_cluster_candidates(at_char_limit)
        self.assertEqual(1, len(at_limit_clusters))
        self.assertEqual(
            {
                "char_start": 0,
                "char_end": 1200,
                "char_width": 1200,
                "line_start": 1,
                "line_end": 24,
                "line_count": 24,
            },
            validator._transition_envelope(at_limit_clusters[0], "removed"),
        )
        self.assertEqual([], validator._transition_cluster_candidates(over_char_limit))
        self.assertEqual([], validator._transition_cluster_candidates(over_line_limit))

    def test_course_voice_flattening_cluster_does_not_cross_headings(self) -> None:
        before, after = self.pair(
            "# 第一节\n完全够用。\n保持。\n先盯住变量。\n"
            "# 第二节\n数值明明在变。\n保持。\n两条关系接得上。",
            "# 第一节\n足以描述。\n保持。\n先考察变量。\n"
            "# 第二节\n数值仍随条件变化。\n保持。\n两条关系严格对应。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_markdown_structure_is_protected(self) -> None:
        cases = {
            "yaml": (
                "---\na: 完全够用\nb: 先盯住变量\nc: 数值明明在变\nd: 两条关系接得上\n---\n正文。",
                "---\na: 足以描述\nb: 先考察变量\nc: 数值仍随条件变化\nd: 两条关系严格对应\n---\n正文。",
            ),
            "link-targets": (
                "[甲](完全够用)\n[乙](先盯住变量)\n[丙](数值明明在变)\n[丁](两条关系接得上)",
                "[甲](足以描述)\n[乙](先考察变量)\n[丙](数值仍随条件变化)\n[丁](两条关系严格对应)",
            ),
            "html-attributes": (
                '<p a="完全够用">正文</p>\n<p a="先盯住变量">正文</p>\n'
                '<p a="数值明明在变">正文</p>\n<p a="两条关系接得上">正文</p>',
                '<p a="足以描述">正文</p>\n<p a="先考察变量">正文</p>\n'
                '<p a="数值仍随条件变化">正文</p>\n<p a="两条关系严格对应">正文</p>',
            ),
        }
        for name, (before_text, after_text) in cases.items():
            with self.subTest(name=name):
                before, after = self.pair(before_text, after_text)
                payload = validator.validate(before, after, scene="COURSE")
                self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_quoted_occurrences_are_protected(self) -> None:
        unchanged = "本行保持。"
        before, after = self.pair(
            "\n".join(
                [
                    "“这个结论完全够用。”",
                    unchanged,
                    "“先盯住变量。”",
                    unchanged,
                    "“数值明明在变。”",
                    unchanged,
                    "“两条关系接得上。”",
                ]
            ),
            "\n".join(
                [
                    "“这个结论足以描述。”",
                    unchanged,
                    "“先考察变量。”",
                    unchanged,
                    "“数值仍随条件变化。”",
                    unchanged,
                    "“两条关系严格对应。”",
                ]
            ),
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_tex_command_arguments_are_protected(self) -> None:
        unchanged = "本行保持。"
        before, after = self.pair(
            "\n".join(
                [
                    r"\locked{这个结论完全够用。}",
                    unchanged,
                    r"\locked{先盯住变量。}",
                    unchanged,
                    r"\locked{数值明明在变。}",
                    unchanged,
                    r"\locked{两条关系接得上。}",
                ]
            ),
            "\n".join(
                [
                    r"\locked{这个结论足以描述。}",
                    unchanged,
                    r"\locked{先考察变量。}",
                    unchanged,
                    r"\locked{数值仍随条件变化。}",
                    unchanged,
                    r"\locked{两条关系严格对应。}",
                ]
            ),
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_formal_environment_is_protected(self) -> None:
        before, after = self.pair(
            "\\begin{theorem}\n完全够用。\n保持。\n先盯住变量。\n保持。\n"
            "数值明明在变。\n保持。\n两条关系接得上。\n\\end{theorem}",
            "\\begin{theorem}\n足以描述。\n保持。\n先考察变量。\n保持。\n"
            "数值仍随条件变化。\n保持。\n两条关系严格对应。\n\\end{theorem}",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_adjacent_true_cluster_still_triggers(self) -> None:
        unchanged = "本行保持。"
        before, after = self.pair(
            "\n".join(
                [
                    "这个结论完全够用。",
                    unchanged,
                    "先盯住变量。",
                    unchanged,
                    "数值明明在变。",
                    unchanged,
                    "两条关系接得上。",
                ]
            ),
            "\n".join(
                [
                    "这个结论足以描述。",
                    unchanged,
                    "先考察变量。",
                    unchanged,
                    "数值仍随条件变化。",
                    unchanged,
                    "两条关系严格对应。",
                ]
            ),
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual(1, len(payload["paired_style_delta_findings"]))
        finding = payload["paired_style_delta_findings"][0]
        self.assertEqual(4, finding["observed"]["distinct_transition_count"])
        self.assertEqual(4, finding["observed"]["changed_hunk_count"])
        self.assertEqual(
            "humanize-course-voice-non-regression/v3",
            finding["policy_provenance"],
        )
        self.assertNotIn("evidence_basis", finding)

    def test_course_voice_flattening_reports_all_bound_occurrences(self) -> None:
        unchanged = "本行保持。"
        before, after = self.pair(
            "\n".join(
                [
                    "这个说法完全够用，另一个说法也完全够用。",
                    unchanged,
                    "先盯住变量。",
                    unchanged,
                    "数值明明在变。",
                    unchanged,
                    "两条关系接得上。",
                ]
            ),
            "\n".join(
                [
                    "这个说法足以描述，另一个说法也足以说明。",
                    unchanged,
                    "先考察变量。",
                    unchanged,
                    "数值仍随条件变化。",
                    unchanged,
                    "两条关系严格对应。",
                ]
            ),
        )

        payload = validator.validate(before, after, scene="COURSE")

        transitions = payload["paired_style_delta_findings"][0]["transitions"]
        repeated = [
            item for item in transitions if item["transition_id"] == "COURSE-FLAT-01"
        ]
        self.assertEqual(2, len(repeated))
        self.assertEqual(2, len({item["occurrence_id"] for item in repeated}))

    def test_course_voice_flattening_rejects_asymmetric_occurrence_pairing(self) -> None:
        before, after = self.pair(
            "AAAA完全够用BBBB完全够用CCCC\n保持\n先盯住变量\n保持\n"
            "数值明明在变\n保持\n两条关系接得上",
            "DDDD普通表达EEEE足以描述FFFF\n保持\n先考察变量\n保持\n"
            "数值仍随条件变化\n保持\n两条关系严格对应",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_bom_offsets_bind_original_artifact_bytes(self) -> None:
        unchanged = "本行保持。"
        before_text = "\n".join(
            [
                "这个结论完全够用。",
                unchanged,
                "先盯住变量。",
                unchanged,
                "数值明明在变。",
                unchanged,
                "两条关系接得上。",
            ]
        )
        after_text = "\n".join(
            [
                "这个结论足以描述。",
                unchanged,
                "先考察变量。",
                unchanged,
                "数值仍随条件变化。",
                unchanged,
                "两条关系严格对应。",
            ]
        )
        before = self.root / "before-bom.md"
        after = self.root / "after-bom.md"
        before.write_bytes(b"\xef\xbb\xbf" + before_text.encode("utf-8"))
        after.write_bytes(b"\xef\xbb\xbf" + after_text.encode("utf-8"))

        payload = validator.validate(before, after, scene="COURSE")

        finding = payload["paired_style_delta_findings"][0]
        before_raw = before.read_bytes()
        after_raw = after.read_bytes()
        for transition in finding["transitions"]:
            for span, raw, text in (
                (transition["removed"], before_raw, before_text),
                (transition["introduced"], after_raw, after_text),
            ):
                self.assertEqual(
                    span["text"],
                    raw[span["utf8_start"] : span["utf8_end"]].decode("utf-8"),
                )
                self.assertEqual(
                    3 + len(text[: span["char_start"]].encode("utf-8")),
                    span["utf8_start"],
                )
                self.assertEqual(validator._sha256(raw), span["artifact_sha256"])

    def test_course_voice_flattening_reverse_direction_does_not_trigger(self) -> None:
        unchanged = "本行保持。"
        before, after = self.pair(
            "\n".join(
                [
                    "这个结论足以描述。",
                    unchanged,
                    "先考察变量。",
                    unchanged,
                    "数值仍随条件变化。",
                    unchanged,
                    "两条关系严格对应。",
                ]
            ),
            "\n".join(
                [
                    "这个结论完全够用。",
                    unchanged,
                    "先盯住变量。",
                    unchanged,
                    "数值明明在变。",
                    unchanged,
                    "两条关系接得上。",
                ]
            ),
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_is_not_applicable_to_draft(self) -> None:
        before, after = self.pair(
            "完全够用。先盯住变量。数值明明在变。两条关系接得上。",
            "足以描述。先考察变量。数值仍随条件变化。两条关系严格对应。",
        )

        payload = validator.validate(before, after, mode="DRAFT", scene="COURSE")

        self.assertEqual("NOT_APPLICABLE", payload["paired_style_delta_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_does_not_flag_formal_terms_already_in_source(self) -> None:
        before, after = self.pair(
            "值得注意的是，将位移项纳入方程，并把关系改写为标准形式。",
            "将位移项纳入方程，并把关系改写为标准形式。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_same_family_only_does_not_trigger_cluster(self) -> None:
        before, after = self.pair(
            "先把变化记成源项。\n再把两项统一记账。\n最后检查记账始终一致。",
            "先将变化纳入源项。\n再把两项合在一起。\n最后检查总电流始终一致。",
        )

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["paired_style_delta_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_policy_is_not_applied_to_research_scene(self) -> None:
        before, after = self.pair(
            "这个结论完全够用。\n先盯住变量明明还在跟着变。\n"
            "把变化记成源项，再补成标准形式。",
            "这一结论足以描述该情形。\n先考察变量仍随时间随之变化。\n"
            "将变化纳入源项，再改写为标准形式。",
        )

        payload = validator.validate(before, after, scene="RESEARCH")

        self.assertEqual("NOT_APPLICABLE", payload["paired_style_delta_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_course_voice_flattening_no_change_does_not_trigger_cluster(self) -> None:
        source = (COURSE_VOICE_FLATTENING_FIXTURES / "blind_before.tex").read_text(
            encoding="utf-8"
        )
        before, after = self.pair(source, source, suffix=".tex")

        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("PASS", payload["paired_style_delta_layer_status"])
        self.assertEqual([], payload["paired_style_delta_findings"])

    def test_v24_unseen_collocation_cannot_receive_false_delivery_pass(self) -> None:
        before, after = self.pair(
            "这类题看上去在测长度，其实真正要写的是厚度怎样增长。",
            "这类题测的是长度，但求解先要确定厚度怎样增长。",
        )

        payload = validator.validate(before, after, scene="COURSE")
        request = self.assert_paired_quality_review(
            payload, decision="REWRITE", changes=1
        )

        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual(1, len(request["changes"]))
        self.assertFalse(
            request["review_contract"]["validator_pass_is_quality_clearance"]
        )

    def test_no_change_is_bound_for_external_quality_review(self) -> None:
        before, after = self.pair("该段表面自然，但仍可能存在未识别病灶。", "该段表面自然，但仍可能存在未识别病灶。")

        first = validator.validate(before, after, scene="GENERAL")
        second = validator.validate(before, after, scene="GENERAL")
        first_request = self.assert_paired_quality_review(
            first, decision="NO_CHANGE", changes=0
        )
        second_request = self.assert_paired_quality_review(
            second, decision="NO_CHANGE", changes=0
        )

        self.assertEqual(
            first_request["request_sha256"], second_request["request_sha256"]
        )
        self.assertIn(
            "no_change_is_best_available_decision",
            first_request["review_contract"]["required_dimensions"],
        )

    def test_paired_quality_hunks_preserve_eol_only_changes(self) -> None:
        before, after = self.pair("第一行。\r\n第二行。\r\n", "第一行。\n第二行。\n")
        before.write_bytes("第一行。\r\n第二行。\r\n".encode("utf-8"))
        after.write_bytes("第一行。\n第二行。\n".encode("utf-8"))

        payload = validator.validate(before, after, scene="GENERAL")
        request = self.assert_paired_quality_review(
            payload, decision="REWRITE", changes=1
        )

        change = request["changes"][0]
        self.assertEqual("REPLACE", change["operation"])
        self.assertNotEqual(
            change["before"]["sha256"], change["after"]["sha256"]
        )

    def test_paired_quality_hunks_preserve_bom_only_changes(self) -> None:
        before, after = self.pair("同一正文。", "同一正文。")
        before.write_bytes(b"\xef\xbb\xbf" + "同一正文。".encode("utf-8"))
        after.write_bytes("同一正文。".encode("utf-8"))

        payload = validator.validate(before, after, scene="GENERAL")
        request = self.assert_paired_quality_review(
            payload, decision="REWRITE", changes=1
        )

        self.assertNotEqual(
            request["artifact"]["before_sha256"],
            request["artifact"]["after_sha256"],
        )

    def test_paired_quality_hunks_preserve_trailing_newline_changes(self) -> None:
        before, after = self.pair("同一正文。\n", "同一正文。")
        before.write_bytes("同一正文。\n".encode("utf-8"))
        after.write_bytes("同一正文。".encode("utf-8"))

        payload = validator.validate(before, after, scene="GENERAL")
        request = self.assert_paired_quality_review(
            payload, decision="REWRITE", changes=1
        )

        self.assertEqual("REPLACE", request["changes"][0]["operation"])

    def test_paired_quality_request_binds_policy_hashes(self) -> None:
        before, after = self.pair("原句表述稍长。", "原句较长。")
        baseline = validator.validate(before, after, scene="GENERAL")
        baseline_request = baseline["paired_quality_review_request"]
        with mock.patch.object(
            validator,
            "_policy_hashes",
            return_value={
                "validator_sha256": "1" * 64,
                "invariant_checker_sha256": "2" * 64,
                "scanner_sha256": "3" * 64,
                "lexicon_sha256": "4" * 64,
            },
        ):
            drifted = validator.validate(before, after, scene="GENERAL")

        self.assertNotEqual(
            baseline_request["request_sha256"],
            drifted["paired_quality_review_request"]["request_sha256"],
        )

    def test_mechanical_failure_blocks_quality_review_instead_of_masking_failure(self) -> None:
        before, after = self.pair("公式为 $x=1$。", "公式为 $x=2$。", suffix=".tex")

        payload = validator.validate(before, after, scene="GENERAL")

        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("FAIL", payload["mechanical_validation_status"])
        self.assertEqual("BLOCKED_BY_MECHANICAL_GATE", payload["paired_quality_review_status"])
        self.assertEqual(
            "BLOCKED_BY_MECHANICAL_GATE",
            payload["paired_quality_review_request"]["status"],
        )

    def test_fragment_scope_is_explicit_and_does_not_hide_structure_drift(self) -> None:
        before, after = self.pair(
            "\\begin{document}\n值得注意的是，结论保持不变。\n",
            "\\begin{document}\n结论保持不变。\n",
            suffix=".tex",
        )
        payload = validator.validate(
            before,
            after,
            scene="RESEARCH",
            fragment_mode=True,
        )
        self.assert_paired_quality_review(payload, decision="REWRITE", changes=1)
        self.assertEqual("FRAGMENT", payload["evidence"]["document_scope"])
        self.assertEqual("FRAGMENT", payload["invariants"]["evidence"]["document_scope"])

        after.write_text("结论保持不变。\n", encoding="utf-8")
        drifted = validator.validate(
            before,
            after,
            scene="RESEARCH",
            fragment_mode=True,
        )
        self.assertEqual("FAIL", drifted["status"])
        self.assertEqual("FAIL", drifted["hard_invariant_layer_status"])

        with self.assertRaisesRegex(ValueError, "only valid for REWRITE"):
            validator.validate(before, after, mode="DRAFT", fragment_mode=True)

    def test_draft_mode_uses_supply_surface_gate_and_never_claims_semantic_pass(self) -> None:
        supplied, draft = self.pair(
            "# 写作要点\n\n- 2025 年共三组数据。\n- 材料没有提供原因。\n",
            "2025 年共三组数据。\n",
        )

        payload = validator.validate(supplied, draft, mode="DRAFT", scene="GENERAL")

        self.assertEqual("DRAFT", payload["mode"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["draft_surface_source_check"]["status"])
        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("NOT_EVALUATED", payload["semantic_source_check"])
        self.assertEqual("REVIEW", payload["status"])
        self.assertIn("semantic_source_not_evaluated", payload["review_reasons"])
        self.assertFalse(
            any(
                item["code"] == "SPEECH_ACT_NEGATION_CHANGED"
                for item in payload["unaccepted_warnings"]
            )
        )

    def test_draft_copy_only_never_allows_humanize_quality_claim(self) -> None:
        supplied, draft = self.pair(
            "供稿内容保持原样。",
            "供稿内容保持原样。",
        )

        payload = validator.validate(supplied, draft, mode="DRAFT", scene="GENERAL")

        self.assertEqual("PASS", payload["status"])
        self.assertEqual("PASS_COPY_ONLY", payload["semantic_source_check"])
        self.assertFalse(payload["humanize_quality_claim_allowed"])

    def test_draft_mode_rejects_number_not_present_in_supplied_content(self) -> None:
        supplied, draft = self.pair(
            "材料记录了三组数据，共 3 组。\n",
            "材料记录了四组数据，共 4 组。\n",
        )

        payload = validator.validate(supplied, draft, mode="DRAFT", scene="GENERAL")

        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("FAIL", payload["hard_invariant_layer_status"])
        self.assertEqual("FAIL", payload["draft_surface_source_check"]["status"])
        self.assertIn(
            "DRAFT_NUMBER_OR_UNIT_NOT_SUPPLIED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_draft_mode_rejects_new_attribution_shell(self) -> None:
        supplied, draft = self.pair(
            "材料记录了三组数据，共 3 组。\n",
            "已有研究表明，材料记录了三组数据，共 3 组。\n",
        )

        payload = validator.validate(supplied, draft, mode="DRAFT", scene="GENERAL")

        self.assertEqual("FAIL", payload["status"])
        self.assertIn(
            "DRAFT_ATTRIBUTION_NOT_SUPPLIED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_draft_mode_reuses_supplied_surface_values_without_occurrence_budget(self) -> None:
        cases = (
            ("code", "材料给出 `alpha()`。", "先运行 `alpha()`，再核对 `alpha()`。", ".md", ()),
            ("math", r"材料给出 \(x=y\)。", r"先使用 \(x=y\)，再由 \(x=y\) 展开。", ".tex", ()),
            (
                "formal",
                "\\begin{theorem}\n命题甲成立。\n\\end{theorem}\n",
                "\\begin{theorem}\n命题甲成立。\n\\end{theorem}\n\n"
                "\\begin{theorem}\n命题甲成立。\n\\end{theorem}\n",
                ".tex",
                (),
            ),
            (
                "command",
                r"材料引用 \cite{sourceA}。",
                r"依据 \cite{sourceA}，并参见 \cite{sourceA}。",
                ".tex",
                (),
            ),
            (
                "quotation",
                "材料原句为“边界保持不变”。",
                "“边界保持不变”；换言之，仍是“边界保持不变”。",
                ".md",
                (),
            ),
            ("garbled", "OCR： �字 。", "记录为 �字 。再次记录为 �字 。", ".md", ()),
            (
                "term",
                "本文采用有限元法。",
                "有限元法用于求解；有限元法保持不变。",
                ".md",
                ("有限元法", "谱方法"),
            ),
        )
        for name, supplied_text, draft_text, suffix, terms in cases:
            with self.subTest(name=name):
                supplied, draft = self.pair(supplied_text, draft_text, suffix=suffix)
                payload = validator.validate(
                    supplied,
                    draft,
                    mode="DRAFT",
                    scene="GENERAL",
                    protected_terms=terms,
                )
                self.assertEqual("PASS", payload["draft_surface_source_check"]["status"])
                self.assertEqual("PASS", payload["hard_invariant_layer_status"])
                self.assertEqual("NOT_EVALUATED", payload["semantic_source_check"])
                self.assertEqual("REVIEW", payload["status"])
                self.assertEqual(2, payload["exit_code"])

    def test_draft_mode_still_rejects_new_surface_values(self) -> None:
        cases = (
            ("code", "材料给出 `alpha()`。", "材料给出 `beta()`。", ".md", (), "DRAFT_CODE_NOT_SUPPLIED"),
            ("math", r"材料给出 \(x=y\)。", r"材料给出 \(x=z\)。", ".tex", (), "DRAFT_MATH_NOT_SUPPLIED"),
            (
                "formal",
                "\\begin{theorem}\n命题甲成立。\n\\end{theorem}\n",
                "\\begin{theorem}\n命题乙成立。\n\\end{theorem}\n",
                ".tex",
                (),
                "DRAFT_FORMAL_STATEMENT_NOT_SUPPLIED",
            ),
            (
                "command",
                r"材料引用 \cite{sourceA}。",
                r"材料引用 \cite{sourceB}。",
                ".tex",
                (),
                "DRAFT_CRITICAL_COMMAND_NOT_SUPPLIED",
            ),
            (
                "quotation",
                "材料原句为“边界保持不变”。",
                "材料原句为“边界已经改变”。",
                ".md",
                (),
                "DRAFT_QUOTATION_NOT_SUPPLIED",
            ),
            ("garbled", "OCR： �字 。", "记录为 �词 。", ".md", (), "DRAFT_GARBLED_TEXT_NOT_SUPPLIED"),
            (
                "term",
                "本文采用有限元法。",
                "本文采用谱方法。",
                ".md",
                ("有限元法", "谱方法"),
                "DRAFT_PROTECTED_TERM_NOT_SUPPLIED",
            ),
        )
        for name, supplied_text, draft_text, suffix, terms, error_code in cases:
            with self.subTest(name=name):
                supplied, draft = self.pair(supplied_text, draft_text, suffix=suffix)
                payload = validator.validate(
                    supplied,
                    draft,
                    mode="DRAFT",
                    scene="GENERAL",
                    protected_terms=terms,
                )
                self.assertEqual("FAIL", payload["status"])
                self.assertEqual(1, payload["exit_code"])
                self.assertIn(error_code, {item["code"] for item in payload["invariants"]["errors"]})

    def test_draft_mode_realistic_result_and_discussion_can_reuse_math(self) -> None:
        supplied, draft = self.pair(
            "将人工放流项置为 \\(R_S=0\\) 时，长江鲟末值为 0.519。\n",
            "将人工放流项置为 \\(R_S=0\\) 时，长江鲟末值为 0.519。\n\n"
            "讨论中，\\(R_S=0\\) 对照用于拆分人工放流补偿效应。\n",
            suffix=".tex",
        )
        payload = validator.validate(supplied, draft, mode="DRAFT", scene="MODELING")
        self.assertEqual("PASS", payload["draft_surface_source_check"]["status"])
        self.assertEqual("REVIEW", payload["status"])
        self.assertNotIn(
            "DRAFT_MATH_NOT_SUPPLIED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_rewrite_math_occurrence_protection_is_unchanged(self) -> None:
        before, after = self.pair(
            "模型使用 \\(x=y\\)。",
            "模型使用 \\(x=y\\)，并再次使用 \\(x=y\\)。",
            suffix=".tex",
        )
        payload = validator.validate(before, after, mode="REWRITE", scene="GENERAL")
        self.assertEqual("FAIL", payload["status"])
        self.assertIn(
            "PROTECTED_MATH_CHANGED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_explicit_tex_format_on_txt_rejects_added_comment(self) -> None:
        before, after = self.pair(
            "这里保留原有结论。\n",
            "这里保留原有结论。% 新增注释\n",
            suffix=".txt",
        )

        inferred = validator.validate(before, after, scene="GENERAL")
        explicit = validator.validate(
            before,
            after,
            scene="GENERAL",
            document_format="tex",
        )

        self.assertEqual("markdown", inferred["evidence"]["document_format"])
        self.assertEqual("PASS", inferred["hard_invariant_layer_status"])
        self.assertEqual("tex", explicit["evidence"]["document_format"])
        self.assertEqual("FAIL", explicit["delivery_gate_status"])
        self.assertEqual(1, explicit["exit_code"])
        self.assertEqual("FAIL", explicit["hard_invariant_layer_status"])
        self.assertIn(
            "TEX_COMMENT_CHANGED",
            {item["code"] for item in explicit["invariants"]["errors"]},
        )

    def test_rewrite_rejects_multiline_quote_content_change(self) -> None:
        before, after = self.pair(
            "作者写道：“第一行保留。\n第二行是乙项。”\n",
            "作者写道：“第一行保留。\n第二行是丙项。”\n",
        )
        payload = validator.validate(before, after, mode="REWRITE", scene="GENERAL")
        self.assertEqual("FAIL", payload["hard_invariant_layer_status"])
        self.assertIn(
            "DIRECT_QUOTATION_CHANGED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_rewrite_rejects_custom_citation_and_style_command_argument_changes(self) -> None:
        cases = (
            (
                r"材料见 \mycite{potter1994cooperative,de1995evolving}。",
                r"材料见 \mycite{potter1994cooperative,omidvar2021review}。",
            ),
            (r"结论为 \textbf{甲项}。", r"结论为 \textbf{乙项}。"),
        )
        for before_text, after_text in cases:
            with self.subTest(before_text=before_text):
                before, after = self.pair(before_text, after_text, suffix=".tex")
                payload = validator.validate(
                    before,
                    after,
                    mode="REWRITE",
                    scene="RESEARCH",
                )
                self.assertEqual("FAIL", payload["hard_invariant_layer_status"])
                self.assertIn(
                    "CRITICAL_LATEX_COMMAND_CHANGED",
                    {item["code"] for item in payload["invariants"]["errors"]},
                )

    def test_report_scope_binds_rewrite_to_unique_selection_ranges(self) -> None:
        before, after = self.pair(
            "开头保持。\n\n标注一表述生硬。\n\n中间保持。\n\n标注二表述冗长。\n\n结尾保持。\n",
            "开头保持。\n\n标注一表述自然。\n\n中间保持。\n\n标注二更加简洁。\n\n结尾保持。\n",
        )
        scope = self.report_scope(before, ["标注一表述生硬。", "标注二表述冗长。"])
        payload = validator.validate(before, after, scene="GENERAL", report_scope_path=scope)
        self.assert_paired_quality_review(payload, decision="REWRITE", changes=2)
        self.assertEqual("PASS", payload["report_scope_check"]["status"])
        self.assertTrue(payload["report_scope_check"]["outside_selection_unchanged"])
        self.assertTrue(payload["report_scope_check"]["extractor_replay_match"])
        self.assertEqual(2, payload["report_scope_check"]["editable_range_count"])
        self.assertEqual("REPORT_SELECTION", payload["evidence"]["document_scope"])

    def test_report_scope_rejects_change_outside_selection_even_when_other_gates_pass(self) -> None:
        before, after = self.pair(
            "开头保持。\n\n标注段表述生硬。\n\n结尾保持。\n",
            "开头内容改变。\n\n标注段表述自然。\n\n结尾保持。\n",
        )
        scope = self.report_scope(before, ["标注段表述生硬。"])
        payload = validator.validate(before, after, scene="GENERAL", report_scope_path=scope)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("FAIL", payload["report_scope_check"]["status"])
        self.assertFalse(payload["report_scope_check"]["outside_selection_unchanged"])
        self.assertIn(
            "REPORT_SCOPE_OUTSIDE_SELECTION_CHANGED",
            {item["code"] for item in payload["invariants"]["errors"]},
        )

    def test_report_scope_rejects_stale_source_hash(self) -> None:
        before, after = self.pair("标注段需要改写。", "标注段改得自然。")
        scope = self.report_scope(before, ["标注段需要改写。"])
        scope_payload = json.loads(scope.read_text(encoding="utf-8"))
        scope_payload["source_sha256"] = "0" * 64
        scope.write_text(json.dumps(scope_payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            validator.validate(before, after, scene="GENERAL", report_scope_path=scope)

    def test_report_scope_rejects_duplicate_json_keys(self) -> None:
        before, after = self.pair("标注段需要改写。", "标注段改得自然。")
        scope = self.report_scope(before, ["标注段需要改写。"])
        raw = scope.read_text(encoding="utf-8")
        scope.write_text('{"status":"FAIL",' + raw.lstrip()[1:], encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "duplicate JSON key: status"):
            validator.validate(before, after, scene="GENERAL", report_scope_path=scope)

    def test_report_scope_rejects_non_finite_json_numbers(self) -> None:
        before, after = self.pair("标注段需要改写。", "标注段改得自然。")
        scope = self.report_scope(before, ["标注段需要改写。"])
        raw = scope.read_text(encoding="utf-8")
        scope.write_text(
            raw.replace('"source_start": 0', '"source_start": NaN', 1),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "non-finite JSON number: NaN"):
            validator.validate(before, after, scene="GENERAL", report_scope_path=scope)

    def test_report_scope_replays_artifact_relative_report_locator(self) -> None:
        before, after = self.pair("标注段表述生硬。", "标注段表述自然。")
        report = self.root / "report.html"
        scope = self.root / "report_scope.json"
        report.write_text("<mark>标注段表述生硬。</mark>", encoding="utf-8")
        payload = validator.detector_scope.analyze_report(report, before)
        payload["report_path"] = "report.html"
        payload["source_path"] = "before.md"
        payload["path_base"] = "SCOPE_ARTIFACT_PARENT"
        scope.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = validator.validate(
            before,
            after,
            scene="GENERAL",
            report_scope_path=scope,
        )
        self.assertEqual("PASS", result["report_scope_check"]["status"])

    def test_report_scope_rejects_relative_locator_escape(self) -> None:
        before, after = self.pair("标注段表述生硬。", "标注段表述自然。")
        scope = self.report_scope(before, ["标注段表述生硬。"])
        payload = json.loads(scope.read_text(encoding="utf-8"))
        payload["report_path"] = "../outside.html"
        payload["source_path"] = "before.md"
        payload["path_base"] = "SCOPE_ARTIFACT_PARENT"
        scope.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "escapes its artifact root"):
            validator.validate(before, after, scene="GENERAL", report_scope_path=scope)

    def test_report_scope_rejects_forged_ranges_that_do_not_replay_from_report(self) -> None:
        before, after = self.pair(
            "开头保持。\n\n标注段表述生硬。\n\n结尾保持。\n",
            "开头保持。\n\n标注段表述自然。\n\n结尾保持。\n",
        )
        scope = self.report_scope(before, ["标注段表述生硬。"])
        scope_payload = json.loads(scope.read_text(encoding="utf-8"))
        scope_payload["fragments"][0]["source_start"] = 0
        scope_payload["fragments"][0]["source_end"] = len(before.read_text(encoding="utf-8"))
        scope.write_text(json.dumps(scope_payload, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "extractor replay"):
            validator.validate(before, after, scene="GENERAL", report_scope_path=scope)

    def test_unexplained_high_signal_requires_review(self) -> None:
        before, after = self.pair("这张表必须牢记。", "这张表必须牢记。")
        payload = validator.validate(before, after, scene="COURSE")
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual(1, payload["lexical_summary"]["unexplained_high_candidates"])

    def test_trend_breakthrough_slogan_chain_cannot_be_delivered_as_clean_pass(self) -> None:
        before, after = self.pair(
            "给定首句。这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            "给定首句之后，说明这一趋势既顺应了时代的演变，也是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
        )
        payload = validator.validate(before, after, scene="COURSE")
        market = [
            item
            for item in payload["unexplained_high_findings"]
            if item["signal_id"] == "LEX-MARKET-01"
        ]
        self.assertGreaterEqual(len(market), 3)
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertFalse(payload["humanize_quality_claim_allowed"])

    def test_required_style_shell_deletions_do_not_deadlock_speech_act_gate(self) -> None:
        cases = (
            (
                "需要指出的是，问卷结果可能受样本结构影响。",
                "问卷结果可能受样本结构影响。",
            ),
            (
                "本文梳理三类回答，从而为后续分析提供可靠起点。",
                "本文梳理三类回答。",
            ),
        )
        for before_text, after_text in cases:
            with self.subTest(before=before_text):
                before, after = self.pair(before_text, after_text)
                payload = validator.validate(before, after, scene="GENERAL")
                self.assertEqual("PASS", payload["speech_act_layer_status"])
                self.assertEqual("PASS", payload["mechanical_validation_status"])
                self.assertEqual("REVIEW", payload["delivery_gate_status"])

    def test_v19_closed_loop_and_abstract_path_shell_cannot_silently_pass(self) -> None:
        cases = (
            (
                "本问按参数设定、校准和反事实对照的实证闭环收紧。",
                "RESEARCH",
            ),
            (
                "问题二的证据关系由禁渔和食源恢复出发，经通道与污染修正，最终落到种群变化。",
                "MODELING",
            ),
        )
        for text, scene in cases:
            with self.subTest(scene=scene):
                before, after = self.pair(text, text)
                payload = validator.validate(before, after, scene=scene)
                ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
                self.assertEqual("REVIEW", payload["delivery_gate_status"])
                self.assertEqual(2, payload["delivery_gate_exit_code"])
                self.assertIn("LEX-MGMT-01", ids)

    def test_strict_root_family_match_blocks_unchanged_no_change(self) -> None:
        for phrase in ("\u66f4\u7a33", "\u6536\u7d27"):
            with self.subTest(phrase=phrase):
                before, after = self.pair(f"本方案{phrase}。", f"本方案{phrase}。")
                payload = validator.validate(before, after, scene="GENERAL")
                strict = payload["strict_corpus_summary"]
                self.assertGreaterEqual(strict["after_candidates"], 1)
                self.assertGreaterEqual(strict["unexplained_candidates"], 1)
                self.assertFalse(strict["no_change_allowed"])
                self.assertEqual("REVIEW", payload["mechanical_validation_status"])
                self.assertEqual("REVIEW", payload["delivery_gate_status"])
                self.assertIn(
                    "unexplained_strict_corpus_signal", payload["review_reasons"]
                )
                request = payload["paired_quality_review_request"]
                self.assertEqual("BLOCKED_BY_MECHANICAL_GATE", request["status"])
                context = request["validation_context"]
                self.assertEqual("BLOCKED_NO_CHANGE", context["decision"])
                self.assertEqual("UNCHANGED", context["artifact_relation"])
                self.assertFalse(context["decision_eligible"])

    def test_explicit_keep_reason_can_clear_a_surface_hit(self) -> None:
        before, after = self.pair("这张表必须牢记。", "这张表必须牢记。")
        payload = validator.validate(
            before,
            after,
            scene="COURSE",
            keep_reasons={"LEX-COACH-01": "用户锁定的课程原句"},
        )
        self.assert_paired_quality_review(payload, decision="NO_CHANGE", changes=0)
        self.assertEqual(1, len(payload["accepted_findings"]))
        self.assertRegex(payload["accepted_findings"][0]["finding_hash"], r"^[0-9a-f]{64}$")

    def test_introduced_repair_template_requires_review(self) -> None:
        before, after = self.pair(
            "峰值用于比较。误差用于比较。",
            "这里只看峰值。这里只比较误差。",
        )
        payload = validator.validate(before, after, scene="GENERAL")
        ids = {item["signal_id"] for item in payload["introduced_findings"]}
        self.assertEqual("REVIEW", payload["status"])
        self.assertIn("LEX-REPAIR-01", ids)

    def test_speech_act_warning_requires_review(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        payload = validator.validate(before, after, scene="GENERAL")
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertIn("speech_act_warning", payload["review_reasons"])
        request = payload["warning_review_request"]
        self.assertIsNotNone(request)
        self.assertRegex(request["request_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(1, len(request["warnings"]))
        self.assertRegex(
            request["warnings"][0]["warning_fingerprint"],
            r"^[0-9a-f]{64}$",
        )
        self.assertEqual(payload["evidence"]["before_sha256"], request["artifact"]["before_sha256"])
        self.assertEqual(payload["evidence"]["after_sha256"], request["artifact"]["after_sha256"])
        self.assertEqual("GENERAL", request["validation_context"]["scene"])
        self.assertEqual("markdown", request["validation_context"]["document_format"])
        self.assertEqual(
            payload["evidence"]["protected_terms"],
            request["validation_context"]["protected_terms"],
        )
        self.assertEqual(
            {
                "validator_sha256",
                "invariant_checker_sha256",
                "scanner_sha256",
                "lexicon_sha256",
                "report_extractor_sha256",
                "runtime_contract_sha256",
                "paired_quality_verifier_sha256",
                "paired_quality_contract_sha256",
            },
            set(request["policy_hashes"]),
        )
        for policy_hash in request["policy_hashes"].values():
            self.assertRegex(policy_hash, r"^[0-9a-f]{64}$")

    def test_v19_focus_scope_loss_requires_review(self) -> None:
        before, after = self.pair(
            "本问的重点不是比较两个物种的绝对值，而是考察政策收益的保留程度。",
            "本问不比较两个物种的绝对值，而是考察政策收益的保留程度。",
        )
        payload = validator.validate(before, after, scene="MODELING")

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertIn(
            "SPEECH_ACT_FOCUS_SCOPE_CHANGED",
            {item["code"] for item in payload["unaccepted_warnings"]},
        )

    def test_v7_modeling_false_pass_is_blocked_by_transition_and_outlook_gates(self) -> None:
        before, after = self.pair(
            "本文构建模型。表格的作用在于统一实验口径，正文里要保留 20 ℃、25 ℃ 和 30 ℃ 三组数据。"
            "该模型形成了从数据到决策的完整闭环，为工程应用提供有力支撑。"
            "模型可能在一定程度上或许仍会受到传感器漂移影响，因此后续工作可以进一步拓展应用场景。",
            "本文构建模型。表格列出 20 ℃、25 ℃ 和 30 ℃ 三组数据，以统一实验口径。"
            "该模型将参数扫描结果用于工程决策，为工程应用提供依据。"
            "传感器漂移可能影响模型，影响程度或许有限。应用场景可以进一步拓展。",
        )
        payload = validator.validate(before, after, scene="MODELING")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", warning_codes)
        self.assertIn("SPEECH_ACT_SUPPORT_TO_ACTUAL_USE", warning_codes)
        self.assertIn("SPEECH_ACT_MODALITY_TO_DEGREE", warning_codes)
        self.assertIn(
            "LEX-FUTURE-01",
            {item["signal_id"] for item in payload["introduced_findings"]},
        )

    def test_v7_course_coaching_synonym_cannot_pass(self) -> None:
        before, after = self.pair(
            "遇到这类题目时必须牢记公式。",
            "遇到这类题目，公式必须记清楚。",
        )
        payload = validator.validate(before, after, scene="COURSE")

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertIn(
            "LEX-COACH-01",
            {item["signal_id"] for item in payload["unexplained_high_findings"]},
        )

    def test_v8_memory_synonym_and_editor_note_cannot_pass(self) -> None:
        course_before, course_after = self.pair(
            "遇到这类题目时必须牢记公式。",
            "遇到这类题，公式需要记住。",
        )
        course = validator.validate(course_before, course_after, scene="COURSE")
        self.assertEqual("REVIEW", course["delivery_gate_status"])
        self.assertIn(
            "LEX-COACH-01",
            {item["signal_id"] for item in course["unexplained_high_findings"]},
        )

        modeling_before, modeling_after = self.pair(
            "正文里要保留 20 ℃、25 ℃ 和 30 ℃ 三组数据。",
            "20 ℃、25 ℃ 和 30 ℃ 三组数据仍需在正文中保留。",
        )
        modeling = validator.validate(modeling_before, modeling_after, scene="MODELING")
        self.assertEqual("REVIEW", modeling["delivery_gate_status"])
        self.assertIn(
            "LEX-META-01",
            {item["signal_id"] for item in modeling["unexplained_high_findings"]},
        )

    def test_v10_course_real_forward_deletes_coaching_shell_without_false_pass(self) -> None:
        payload = validator.validate(
            FORWARD_V10_FIXTURES / "course_before.tex",
            FORWARD_V10_FIXTURES / "course_after.tex",
            scene="COURSE",
        )
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual(0, payload["lexical_summary"]["after_candidates"])
        self.assertIn(
            "SPEECH_ACT_MODALITY_SCOPE_CHANGED",
            {item["code"] for item in payload["unaccepted_warnings"]},
        )

    def test_v10_modeling_real_forward_recovers_payload_without_predicate_upgrade(self) -> None:
        payload = validator.validate(
            FORWARD_V10_FIXTURES / "modeling_before.md",
            FORWARD_V10_FIXTURES / "modeling_after.md",
            scene="MODELING",
        )
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual(0, payload["lexical_summary"]["after_candidates"])
        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", warning_codes)
        self.assertFalse(
            {
                "SPEECH_ACT_DIRECTIVE_TO_COMPLETION",
                "SPEECH_ACT_SUPPORT_TO_ACTUAL_USE",
                "SPEECH_ACT_MODALITY_TO_DEGREE",
            }
            & warning_codes
        )

    def test_v10_research_real_forward_passes_all_three_layers(self) -> None:
        payload = validator.validate(
            FORWARD_V10_FIXTURES / "research_before.md",
            FORWARD_V10_FIXTURES / "research_after.md",
            scene="RESEARCH",
        )
        self.assert_paired_quality_review(payload, decision="REWRITE")
        self.assertEqual("PASS", payload["hard_invariant_layer_status"])
        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual(0, payload["lexical_summary"]["after_candidates"])

    def test_warning_review_request_and_fingerprints_are_deterministic(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL", protected_terms=["结果"])
        second = validator.validate(before, after, scene="GENERAL", protected_terms=["结果"])

        self.assertEqual(
            first["warning_review_request"]["request_sha256"],
            second["warning_review_request"]["request_sha256"],
        )
        self.assertEqual(
            first["warning_review_request"]["warnings"],
            second["warning_review_request"]["warnings"],
        )

    def test_v33_warning_request_carries_occurrence_and_residual_diagnostics(self) -> None:
        before, after = self.pair(
            "甲可能成立。乙成立。",
            "甲成立。乙可能成立。",
        )
        payload = validator.validate(before, after, scene="GENERAL")
        warning = next(
            item
            for item in payload["warning_review_request"]["warnings"]
            if item["code"] == "SPEECH_ACT_MODALITY_SCOPE_CHANGED"
        )

        self.assertTrue(warning["details"]["before_occurrences"])
        self.assertTrue(warning["details"]["after_occurrences"])
        self.assertEqual({}, warning["details"]["raw_delta"]["removed"])
        self.assertEqual(2, len(warning["details"]["residual_delta"]))
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])

    def test_v33_inherited_tension_is_exposed_without_changing_layer_status(self) -> None:
        before, after = self.pair(
            "该结果可能证明机制成立。",
            "该结果可能证明机制成立。",
        )
        payload = validator.validate(before, after, scene="RESEARCH")

        self.assertEqual("PASS", payload["speech_act_layer_status"])
        self.assertEqual(1, len(payload["speech_act_diagnostics"]))
        self.assertEqual(
            "SPEECH_ACT_INHERITED_CLAIM_STRENGTH_TENSION",
            payload["speech_act_diagnostics"][0]["code"],
        )
        self.assertNotIn("speech_act_warning", payload["review_reasons"])

    def test_attribution_source_upgrade_cannot_silently_pass(self) -> None:
        before, after = self.pair(
            "专家认为，该方法在低频组更稳定。",
            "本文证实，该方法在低频组更稳定。",
        )
        payload = validator.validate(before, after, scene="RESEARCH")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertIn("SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED", warning_codes)

    def test_new_literature_background_cannot_silently_pass(self) -> None:
        before, after = self.pair(
            "本文结合问题背景和实验现象讨论可能机制。",
            "本文结合问题背景、实验现象和已有研究讨论可能机制。",
        )
        payload = validator.validate(before, after, scene="RESEARCH")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertIn("SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED", warning_codes)

    def test_unverified_caller_proposal_never_clears_warning(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        payload = validator.validate(
            before,
            after,
            scene="GENERAL",
            warning_resolutions={
                fingerprint: "调用方建议恢复原句中的模态范围以保留结论强度",
            },
            warning_review_request_sha256=request["request_sha256"],
        )
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertEqual([], payload["accepted_warnings"])
        self.assertEqual(1, len(payload["unaccepted_warnings"]))
        self.assertEqual(1, len(payload["proposed_warning_resolutions"]))
        self.assertEqual(1, len(payload["pending_warnings"]))
        self.assertEqual([], payload["warnings_without_resolution_proposal"])
        self.assertFalse(payload["proposed_warning_resolutions"][0]["review_clearance_granted"])
        proposal = payload["warning_proposal_state"]
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["reviewer_identifier_collected"])
        self.assertFalse(proposal["identity_verified"])
        self.assertFalse(proposal["review_clearance_granted"])
        self.assertEqual(
            "NOT_APPLICABLE",
            proposal["attestation_status"],
        )
        self.assertNotIn("warning_review", payload)

    def test_retired_accepted_warnings_are_explicitly_rejected(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        with self.assertRaisesRegex(ValueError, "accepted_warnings/--accept-warning is retired"):
            validator.validate(
                before,
                after,
                accepted_warnings={
                    "SPEECH_ACT_MODALITY_SCOPE_CHANGED": "人工确认该模态变化不影响原句表达功能",
                },
                warning_reviewer_kind="HUMAN",
                warning_reviewer_id="external-reviewer",
            )

    def test_reviewer_identity_metadata_is_retired(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after)
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        with self.assertRaisesRegex(ValueError, "identity metadata is retired"):
            validator.validate(
                before,
                after,
                warning_resolutions={
                    fingerprint: "模型建议恢复原句中的模态范围以保留表达功能",
                },
                warning_review_request_sha256=request["request_sha256"],
                warning_reviewer_kind="AGENT",
                warning_reviewer_id="forward-agent",
            )

    def test_retired_identity_or_request_without_proposal_is_rejected(self) -> None:
        before, after = self.pair("结果保持稳定。", "结果保持稳定。")
        with self.assertRaisesRegex(ValueError, "identity metadata is retired"):
            validator.validate(
                before,
                after,
                warning_reviewer_kind="HUMAN",
                warning_reviewer_id="external-reviewer",
            )
        with self.assertRaisesRegex(ValueError, "hash is only valid with warning_resolutions"):
            validator.validate(
                before,
                after,
                warning_review_request_sha256="0" * 64,
            )

    def test_all_warning_reviewer_labels_are_rejected_without_inspection(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after)
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        for reviewer_id in ("ab", "x" * 129, "human\nreviewer"):
            with self.subTest(reviewer_id=repr(reviewer_id)):
                with self.assertRaisesRegex(ValueError, "identity metadata is retired"):
                    validator.validate(
                        before,
                        after,
                        warning_resolutions={
                            fingerprint: "人工建议恢复原句中的模态范围以保留表达功能",
                        },
                        warning_review_request_sha256=request["request_sha256"],
                        warning_reviewer_kind="HUMAN",
                        warning_reviewer_id=reviewer_id,
                    )

    def test_cli_proposal_preserves_review_and_real_exit_code(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, first.returncode, first.stderr)
        initial = json.loads(first.stdout)
        request = initial["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        command = [
            sys.executable,
            str(SCRIPT),
            str(before),
            str(after),
            "--format",
            "json",
            "--propose-warning-resolution",
            f"{fingerprint}=人工建议恢复原句中的模态范围以保留表达功能",
            "--warning-review-request-sha256",
            request["request_sha256"],
        ]

        proposed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, proposed.returncode, proposed.stderr)
        payload = json.loads(proposed.stdout)
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        proposal = payload["warning_proposal_state"]
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["reviewer_identifier_collected"])
        self.assertFalse(proposal["identity_verified"])
        self.assertFalse(proposal["review_clearance_granted"])

        retired = subprocess.run(
            command + [
                "--warning-reviewer-kind",
                "HUMAN",
                "--warning-reviewer-id",
                "external-reviewer-label",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(1, retired.returncode)
        retired_payload = json.loads(retired.stdout)
        self.assertEqual("FAIL", retired_payload["delivery_gate_status"])
        self.assertEqual("INPUT_CONTRACT_INVALID", retired_payload["error_code"])
        self.assertNotIn("external-reviewer-label", retired.stdout)
        self.assertEqual("", retired.stderr)

    def test_cli_retired_accept_warning_is_rejected_even_with_human_label(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--format",
                "json",
                "--accept-warning",
                "SPEECH_ACT_MODALITY_SCOPE_CHANGED=人工确认该模态变化不影响原句表达功能",
                "--warning-reviewer-kind",
                "HUMAN",
                "--warning-reviewer-id",
                "external-reviewer-label",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(1, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertEqual("FAIL", payload["delivery_gate_status"])
        self.assertEqual("INPUT_CONTRACT_INVALID", payload["error_code"])
        self.assertNotIn("external-reviewer-label", completed.stdout)
        self.assertEqual("", completed.stderr)

    def test_unknown_or_vague_warning_resolution_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validator._parse_reason_pairs(
                ["SPEECH_ACT_MODALITY_SCOPE_CHANGED=接受"],
                "--propose-warning-resolution",
            )
        with self.assertRaises(ValueError):
            validator._parse_reason_pairs(
                ["SPEECH_ACT_MODALITY_SCOPE_CHANGED=人工确认"],
                "--propose-warning-resolution",
            )
        with self.assertRaises(ValueError):
            validator._parse_reason_pairs(
                ["SPEECH_ACT_MODALITY_SCOPE_CHANGED=这是一个具体理由"],
                "--propose-warning-resolution",
            )
        with self.assertRaisesRegex(ValueError, "重复提交 CODE"):
            validator._parse_reason_pairs(
                [
                    "f" * 64 + "=人工建议恢复原句模态以保留表达功能",
                    "f" * 64 + "=人工建议保留原句模态所限定的结论范围",
                ],
                "--propose-warning-resolution",
            )

    def test_review_request_cannot_be_replayed_across_artifacts(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        after.write_text("结果发生改变。", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "does not match the current artifact"):
            validator.validate(
                before,
                after,
                scene="GENERAL",
                warning_resolutions={
                    fingerprint: "人工建议恢复原句中的模态范围以保留表达功能",
                },
                warning_review_request_sha256=request["request_sha256"],
            )

    def test_review_request_rejects_policy_hash_drift(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        changed_policy = dict(request["policy_hashes"])
        changed_policy["validator_sha256"] = "0" * 64

        with mock.patch.object(validator, "_policy_hashes", return_value=changed_policy):
            with self.assertRaisesRegex(ValueError, "policy hashes"):
                validator.validate(
                    before,
                    after,
                    scene="GENERAL",
                    warning_resolutions={
                        fingerprint: "人工建议恢复原句中的模态范围以保留表达功能",
                    },
                    warning_review_request_sha256=request["request_sha256"],
                )

    def test_review_request_cannot_be_replayed_across_validation_context(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]

        for changed_context in (
            {"scene": "RESEARCH"},
            {"scene": "GENERAL", "protected_terms": ["结果"]},
        ):
            with self.subTest(changed_context=changed_context):
                with self.assertRaisesRegex(ValueError, "does not match the current artifact"):
                    validator.validate(
                        before,
                        after,
                        warning_resolutions={
                            fingerprint: "人工建议恢复原句中的模态范围以保留表达功能",
                        },
                        warning_review_request_sha256=request["request_sha256"],
                        **changed_context,
                    )

    def test_resolution_fingerprint_must_exist_in_current_request(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]

        with self.assertRaisesRegex(ValueError, "fingerprint not present"):
            validator.validate(
                before,
                after,
                scene="GENERAL",
                warning_resolutions={
                    "f" * 64: "人工建议恢复原句中的模态范围以保留表达功能",
                },
                warning_review_request_sha256=request["request_sha256"],
            )

    def test_pass_requires_revised_draft_to_eliminate_warning(self) -> None:
        before, warned = self.pair("结果可能变化。", "结果发生变化。")
        first = validator.validate(before, warned, scene="GENERAL")
        self.assertEqual("REVIEW", first["status"])
        warned.write_text("结果可能发生变化。", encoding="utf-8")

        revised = validator.validate(before, warned, scene="GENERAL")
        self.assert_paired_quality_review(revised, decision="REWRITE")
        self.assertEqual([], revised["unaccepted_warnings"])
        self.assertIsNone(revised["warning_review_request"])
        self.assertEqual(
            "NOT_PROVIDED",
            revised["warning_proposal_state"]["attestation_status"],
        )

    def test_hard_invariant_change_fails(self) -> None:
        before, after = self.pair("公式为 $x=1$。", "公式为 $x=2$。", suffix=".tex")
        payload = validator.validate(before, after, scene="GENERAL")
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual(1, payload["exit_code"])
        self.assertEqual("FAIL", payload["hard_invariant_layer_status"])
        self.assertEqual("FAIL", payload["delivery_gate_status"])
        self.assertTrue(payload["invariants"]["hard_failure"])

    def test_text_output_names_layer_statuses_and_non_evaluated_scope(self) -> None:
        before, after = self.pair("结果可能变化。", "结果发生变化。")
        payload = validator.validate(before, after, scene="GENERAL")
        rendered = validator._text_output(payload)

        self.assertIn("delivery_gate_status: REVIEW", rendered)
        self.assertIn("hard_invariant_layer_status: PASS", rendered)
        self.assertIn("speech_act_layer_status: REVIEW", rendered)
        self.assertIn("style_signal_layer_status: PASS", rendered)
        self.assertIn("academic_correctness: NOT_EVALUATED", rendered)
        self.assertIn("warning_proposal_attestation_status: NOT_PROVIDED", rendered)
        self.assertIn("warning_proposal_identity_verified: FALSE", rendered)
        self.assertIn("warning_proposal_clearance_granted: FALSE", rendered)
        self.assertIn("warning_reviewer_identifier_collected: FALSE", rendered)
        self.assertNotIn("reviewer_id_sha256", rendered)
        self.assertRegex(rendered, r"warning_review_request_sha256: [0-9a-f]{64}")
        self.assertIn(
            "warning: SPEECH_ACT_MODALITY_SCOPE_CHANGED [warning]",
            rendered,
        )

    def test_extended_protected_content_and_garbled_text_fail(self) -> None:
        cases = (
            (
                "\\begin{alignat}{2}\nx &= y\n\\end{alignat}\n",
                "\\begin{alignat}{2}\nx &= z\n\\end{alignat}\n",
                ".tex",
            ),
            (
                "\\begin{exercise}\n求函数的极值。\n\\end{exercise}\n",
                "\\begin{exercise}\n计算函数的极值。\n\\end{exercise}\n",
                ".tex",
            ),
            ("```text\ntoken=alpha\n````\n", "```text\ntoken=beta\n````\n", ".md"),
            ("样本分为三组。", "样本分为四组。", ".md"),
            ("OCR：\ufffd字。", "OCR：清字。", ".md"),
        )
        for before_text, after_text, suffix in cases:
            with self.subTest(before=before_text):
                before, after = self.pair(before_text, after_text, suffix=suffix)
                payload = validator.validate(before, after)
                self.assertEqual("FAIL", payload["status"])
                self.assertEqual(1, payload["exit_code"])

    def test_repeated_term_cli_hard_fails_and_records_glossary_evidence(self) -> None:
        before, after = self.pair(
            "采用有限元法求解，材料为 Q235钢。",
            "采用谱方法求解，材料为 Q345钢。",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--format",
                "json",
                "--term",
                "有限元法",
                "--term",
                "Q235钢",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(1, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("CHECKED", payload["evidence"]["protected_terms"]["status"])
        self.assertEqual(2, payload["evidence"]["protected_terms"]["count"])
        self.assertRegex(payload["evidence"]["protected_terms"]["sha256"], r"^[0-9a-f]{64}$")
        error_codes = {item["code"] for item in payload["invariants"]["errors"]}
        self.assertIn("PROTECTED_TERM_CHANGED", error_codes)

    def test_cli_json_status_and_exit_code(self) -> None:
        before, after = self.pair("这张表必须牢记。", "这张表必须牢记。")
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--scene",
                "course",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("REVIEW", payload["status"])
        self.assertRegex(payload["evidence"]["after_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("score", payload)

    def test_template_field_scope_is_persisted_in_direct_evidence_and_invocation(self) -> None:
        before, after = self.pair(
            "适用题目： 积极的、普遍认可的趋势。\n",
            "适用题目： 积极且普遍受到认可的趋势。\n",
            suffix=".tex",
        )
        scope = self.template_field_scope(before, [(1, "适用题目")])
        scope_raw = scope.read_bytes()
        evidence_dir = self.root / "template-field-direct-evidence"

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--scene",
                "COURSE",
                "--format",
                "json",
                "--template-field-edit-scope",
                str(scope),
                "--evidence-dir",
                str(evidence_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )

        self.assertEqual(2, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("PERSISTED", payload["evidence_bundle"]["status"])
        self.assertEqual("PASS", payload["template_field_layer_status"])
        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])

        archived_scope = evidence_dir / "inputs" / "template-field-edit-scope.json"
        self.assertEqual(scope_raw, archived_scope.read_bytes())
        invocation = json.loads(
            (evidence_dir / "invocation-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual("humanize-validation-invocation/v4", invocation["schema"])
        self.assertTrue(invocation["run_id"].startswith("hvr4-"))
        scope_argument = invocation["arguments"]["template_field_edit_scope"]
        self.assertTrue(scope_argument["provided"])
        self.assertEqual(
            "inputs/template-field-edit-scope.json",
            scope_argument["archive_path"],
        )
        self.assertEqual("PAYLOAD_ONLY", scope_argument["permission_boundary"])
        self.assertFalse(scope_argument["local_clearance_supported"])
        self.assertEqual(
            validator._sha256(scope_raw),
            scope_argument["sha256"],
        )
        self.assertEqual(
            validator._sha256(before.read_bytes()),
            scope_argument["source_sha256"],
        )
        scope_input = invocation["inputs"]["template_field_edit_scope"]
        self.assertEqual(
            "inputs/template-field-edit-scope.json",
            scope_input["archive_path"],
        )
        self.assertEqual(validator._sha256(scope_raw), scope_input["sha256"])

        manifest = json.loads(
            (evidence_dir / "evidence-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("humanize-direct-validation-evidence/v5", manifest["schema"])
        self.assertEqual(invocation["run_id"], manifest["run_id"])
        self.assertIn(
            "inputs/template-field-edit-scope.json",
            set(manifest["artifacts"]),
        )

    def test_template_field_scope_tamper_after_validation_blocks_evidence_capture(self) -> None:
        before, after = self.pair(
            "适用题目： 积极的、普遍认可的趋势。\n",
            "适用题目： 积极且普遍受到认可的趋势。\n",
            suffix=".tex",
        )
        scope = self.template_field_scope(before, [(1, "适用题目")])
        payload = validator.validate(
            before,
            after,
            scene="COURSE",
            template_field_edit_scope_path=scope,
        )
        tampered = json.loads(scope.read_text(encoding="utf-8"))
        tampered["edits"][0]["reason"] = (
            "用户改写了授权理由并试图重封证据，但原验证仍绑定旧授权字节。"
        )
        scope.write_text(
            json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            "template field edit scope changed after validation",
        ):
            validator._build_invocation_request(
                payload,
                before=before,
                after=after,
                mode="REWRITE",
                scene="COURSE",
                template_field_edit_scope_path=scope,
            )

    def test_cli_evidence_dir_persists_result_request_and_manifest_atomically(self) -> None:
        before, after = self.pair("值得注意的是，结果为 1。", "结果为 1。")
        evidence_dir = self.root / "direct-evidence"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--format",
                "json",
                "--evidence-dir",
                str(evidence_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("PERSISTED", payload["evidence_bundle"]["status"])
        result_path = evidence_dir / "validation-result.json"
        request_path = evidence_dir / "paired-quality-review-request.json"
        invocation_path = evidence_dir / "invocation-request.json"
        execution_path = evidence_dir / "execution-record.json"
        stdout_path = evidence_dir / "rendered-output.txt"
        stderr_path = evidence_dir / "stderr.txt"
        manifest_path = evidence_dir / "evidence-manifest.json"
        before_archive = evidence_dir / "inputs" / "before.bin"
        after_archive = evidence_dir / "inputs" / "after.bin"
        self.assertTrue(result_path.is_file())
        self.assertTrue(request_path.is_file())
        self.assertTrue(invocation_path.is_file())
        self.assertTrue(execution_path.is_file())
        self.assertTrue(stdout_path.is_file())
        self.assertTrue(stderr_path.is_file())
        self.assertTrue(manifest_path.is_file())
        self.assertEqual(before.read_bytes(), before_archive.read_bytes())
        self.assertEqual(after.read_bytes(), after_archive.read_bytes())
        self.assertEqual(completed.stdout.encode("utf-8"), stdout_path.read_bytes())
        self.assertEqual(b"", stderr_path.read_bytes())
        self.assertEqual(payload, json.loads(result_path.read_text(encoding="utf-8")))
        self.assertEqual(
            payload["paired_quality_review_request"],
            json.loads(request_path.read_text(encoding="utf-8")),
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("humanize-direct-validation-evidence/v5", manifest["schema"])
        self.assertEqual("SELF_CONSISTENCY_ONLY", manifest["integrity_scope"])
        self.assertEqual(payload["evidence_bundle"]["run_id"], manifest["run_id"])
        invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
        self.assertEqual("humanize-validation-invocation/v4", invocation["schema"])
        self.assertTrue(invocation["run_id"].startswith("hvr4-"))
        self.assertEqual("markdown", invocation["arguments"]["document_format"])
        self.assertEqual(
            {"provided": False},
            invocation["arguments"]["template_field_edit_scope"],
        )
        self.assertEqual(manifest["run_id"], invocation["run_id"])
        self.assertEqual("SUPPORTED", invocation["reexecution"]["status"])
        self.assertFalse(invocation["privacy"]["reviewer_identifier_collected"])
        self.assertFalse(invocation["privacy"]["stable_reviewer_pseudonym_archived"])
        self.assertFalse(invocation["privacy"]["source_locator_archived"])
        self.assertEqual(payload["exit_code"], manifest["exit_code"])
        self.assertEqual(
            payload["paired_quality_review_request"]["request_sha256"],
            manifest["paired_quality_review_request_sha256"],
        )
        manifest_hash = manifest.pop("manifest_sha256")
        self.assertEqual(
            validator._sha256(validator._canonical_json_bytes(manifest)),
            manifest_hash,
        )
        before_hash = validator._sha256(before.read_bytes())
        self.assertEqual(before_hash, manifest["source_bindings"]["before"]["sha256"])

        rerun = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(before),
                str(after),
                "--format",
                "json",
                "--evidence-dir",
                str(evidence_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, rerun.returncode)
        rerun_payload = json.loads(rerun.stdout)
        self.assertEqual(payload, rerun_payload)
        self.assertEqual(manifest_hash, json.loads(manifest_path.read_text(encoding="utf-8"))["manifest_sha256"])

    def test_evidence_bundle_failure_leaves_no_staging_or_published_directory(self) -> None:
        before, after = self.pair("值得注意的是，结果为 1。", "结果为 1。")
        payload = validator.validate(before, after)
        payload["evidence_bundle"] = validator._evidence_bundle_record(payload)
        evidence_dir = self.root / "atomic-evidence"
        original = validator._write_exclusive
        calls = {"count": 0}

        def fail_on_second(path: Path, raw: bytes) -> None:
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("injected evidence write failure")
            original(path, raw)

        with mock.patch.object(validator, "_write_exclusive", side_effect=fail_on_second):
            with self.assertRaisesRegex(OSError, "injected evidence write failure"):
                validator._persist_evidence_bundle(
                    payload,
                    before=before,
                    after=after,
                    output_dir=evidence_dir,
                )
        self.assertFalse(evidence_dir.exists())
        self.assertEqual([], list(self.root.glob(".atomic-evidence.staging-*")))

    def test_evidence_bundle_every_write_failure_rolls_back_completely(self) -> None:
        before, after = self.pair("值得注意的是，结果为 1。", "结果为 1。")
        payload = validator.validate(before, after)
        invocation = validator._build_invocation_request(
            payload,
            before=before,
            after=after,
        )
        payload["evidence_bundle"] = validator._evidence_bundle_record(
            payload,
            run_id=invocation["run_id"],
        )
        rendered = validator._pretty_json_bytes(payload)
        baseline = self.root / "write-count-baseline"
        validator._persist_evidence_bundle(
            payload,
            before=before,
            after=after,
            output_dir=baseline,
            invocation_request=invocation,
            rendered_output=rendered,
        )
        write_count = len(json.loads(
            (baseline / "evidence-manifest.json").read_text(encoding="utf-8")
        )["artifacts"]) + 1

        original = validator._write_exclusive
        for fail_at in range(1, write_count + 1):
            with self.subTest(fail_at=fail_at):
                target = self.root / f"write-failure-{fail_at}"
                calls = {"count": 0}

                def fail_selected(path: Path, raw: bytes) -> None:
                    calls["count"] += 1
                    if calls["count"] == fail_at:
                        raise OSError(f"injected write failure {fail_at}")
                    original(path, raw)

                with mock.patch.object(
                    validator,
                    "_write_exclusive",
                    side_effect=fail_selected,
                ):
                    with self.assertRaisesRegex(OSError, "injected write failure"):
                        validator._persist_evidence_bundle(
                            payload,
                            before=before,
                            after=after,
                            output_dir=target,
                            invocation_request=invocation,
                            rendered_output=rendered,
                        )
                self.assertFalse(target.exists())
                self.assertEqual(
                    [],
                    list(self.root.glob(f".{target.name}.staging-*")),
                )
                self.assertFalse(
                    target.with_name(f".{target.name}.publish.lock").exists()
                )

    def test_evidence_rename_failure_and_late_source_drift_roll_back(self) -> None:
        before, after = self.pair("值得注意的是，结果为 1。", "结果为 1。")
        payload = validator.validate(before, after)
        invocation = validator._build_invocation_request(
            payload,
            before=before,
            after=after,
        )
        payload["evidence_bundle"] = validator._evidence_bundle_record(
            payload,
            run_id=invocation["run_id"],
        )
        rendered = validator._pretty_json_bytes(payload)
        rename_target = self.root / "rename-failure"
        with mock.patch.object(Path, "rename", side_effect=OSError("rename failed")):
            with self.assertRaisesRegex(OSError, "rename failed"):
                validator._persist_evidence_bundle(
                    payload,
                    before=before,
                    after=after,
                    output_dir=rename_target,
                    invocation_request=invocation,
                    rendered_output=rendered,
                )
        self.assertFalse(rename_target.exists())
        self.assertEqual([], list(self.root.glob(".rename-failure.staging-*")))
        self.assertFalse((self.root / ".rename-failure.publish.lock").exists())

        drift_target = self.root / "source-drift"
        original_write = validator._write_exclusive

        def drift_after_manifest(path: Path, raw: bytes) -> None:
            original_write(path, raw)
            if path.name == "evidence-manifest.json":
                before.write_text("来源在提交前被替换。", encoding="utf-8")

        with mock.patch.object(
            validator,
            "_write_exclusive",
            side_effect=drift_after_manifest,
        ):
            with self.assertRaisesRegex(ValueError, "changed before evidence publication"):
                validator._persist_evidence_bundle(
                    payload,
                    before=before,
                    after=after,
                    output_dir=drift_target,
                    invocation_request=invocation,
                    rendered_output=rendered,
                )
        self.assertFalse(drift_target.exists())
        self.assertEqual([], list(self.root.glob(".source-drift.staging-*")))
        self.assertFalse((self.root / ".source-drift.publish.lock").exists())

    def test_keep_reason_requires_specific_chinese_reason(self) -> None:
        valid = {"LEX-COACH-01"}
        with self.assertRaises(ValueError):
            validator._parse_keep_reasons(["LEX-COACH-01=保留"], valid)
        with self.assertRaises(ValueError):
            validator._parse_keep_reasons(["LEX-COACH-01=确认保留"], valid)
        with self.assertRaises(ValueError):
            validator._parse_keep_reasons(["LEX-COACH-01=这是一个具体理由"], valid)
        with self.assertRaises(ValueError):
            validator._parse_keep_reasons(
                ["LEX-COACH-01=此处表达功能需要保留"], valid
            )
        before, after = self.pair("这张表必须牢记。", "这张表必须牢记。")
        with self.assertRaises(ValueError):
            validator.validate(
                before,
                after,
                scene="COURSE",
                keep_reasons={"LEX-COACH-01": "保留"},
            )
        with self.assertRaises(ValueError):
            validator.validate(
                before,
                after,
                scene="COURSE",
                keep_reasons={"NOT_A_SIGNAL": "这是一个不存在的信号"},
            )

    def test_multiple_keep_findings_require_location_and_emit_acceptance_ledger(self) -> None:
        before, after = self.pair("必须牢记。\n必须牢记。", "必须牢记。\n必须牢记。")
        with self.assertRaises(ValueError):
            validator.validate(
                before,
                after,
                scene="COURSE",
                keep_reasons={"LEX-COACH-01": "用户明确锁定这处课程原句"},
            )
        partial = validator.validate(
            before,
            after,
            scene="COURSE",
            keep_reasons={"LEX-COACH-01@1:1": "首处是用户明确锁定的课程原句"},
        )
        self.assertEqual("REVIEW", partial["status"])
        self.assertEqual(1, len(partial["accepted_findings"]))
        self.assertEqual(1, partial["accepted_findings"][0]["line"])
        complete = validator.validate(
            before,
            after,
            scene="COURSE",
            keep_reasons={
                "LEX-COACH-01@1:1": "首处是用户明确锁定的课程原句",
                "LEX-COACH-01@2:1": "次处是题面要求保留的课程原句",
            },
        )
        self.assert_paired_quality_review(complete, decision="NO_CHANGE", changes=0)
        self.assertEqual(2, len(complete["accepted_findings"]))

    def test_tex_protected_high_signals_are_not_false_keep_candidates(self) -> None:
        before, after = self.pair(
            "\\verb|值得注意的是|\\n"
            "% 值得注意的是，此注释不属于可编辑正文。\\n"
            "\\begin{verbatim}\\n"
            "值得注意的是\\n"
            "\\end{verbatim}\\n",
            "\\verb|值得注意的是|\\n"
            "% 值得注意的是，此注释不属于可编辑正文。\\n"
            "\\begin{verbatim}\\n"
            "值得注意的是\\n"
            "\\end{verbatim}\\n",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="GENERAL")

        self.assert_paired_quality_review(payload, decision="NO_CHANGE", changes=0)
        self.assertEqual("PASS", payload["style_signal_layer_status"])
        self.assertEqual(0, payload["lexical_summary"]["after_candidates"])
        self.assertEqual(0, payload["lexical_summary"]["unexplained_high_candidates"])
        self.assertEqual([], payload["accepted_findings"])
        with self.assertRaisesRegex(ValueError, "未唯一定位待复核 finding"):
            validator.validate(
                before,
                after,
                scene="GENERAL",
                keep_reasons={
                    "LEX-EMPH-01@2:3": "该位置属于受保护注释，逐字保留以说明正文保护范围"
                },
            )

    def test_blind_forward_failures_are_machine_detectable(self) -> None:
        expected = {
            "course": "LEX-COACH-01",
            "modeling": "LEX-MARKET-01",
            "research": "LEX-FOUNDATION-01",
        }
        scenes = {"course": "COURSE", "modeling": "MODELING", "research": "RESEARCH"}
        for name, signal_id in expected.items():
            with self.subTest(scene=name):
                payload = validator.validate(
                    FORWARD_FIXTURES / f"{name}_before.md",
                    FORWARD_FIXTURES / f"{name}_after.md",
                    scene=scenes[name],
                )
                ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
                self.assertEqual("REVIEW", payload["status"])
                self.assertIn(signal_id, ids)

    def test_second_blind_pass_exposes_residual_and_synonym_dodges(self) -> None:
        expected = {
            "course": {"LEX-COACH-01", "LEX-FOUNDATION-01"},
            "modeling": {"LEX-MGMT-01", "LEX-MARKET-01"},
            "research": {"LEX-MARKET-01", "LEX-FOUNDATION-01"},
        }
        scenes = {"course": "COURSE", "modeling": "MODELING", "research": "RESEARCH"}
        for name, expected_ids in expected.items():
            with self.subTest(scene=name):
                payload = validator.validate(
                    FORWARD_FIXTURES / f"{name}_before.md",
                    FORWARD_V4_FIXTURES / f"{name}_after.md",
                    scene=scenes[name],
                )
                ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
                self.assertEqual("REVIEW", payload["status"])
                self.assertFalse(expected_ids - ids)

    def test_caller_asserted_proposals_cannot_close_gold_scenes(self) -> None:
        scenes = {"course": "COURSE", "modeling": "MODELING", "research": "RESEARCH"}
        for name, scene in scenes.items():
            with self.subTest(scene=name):
                first = validator.validate(
                    FORWARD_FIXTURES / f"{name}_before.md",
                    GOLD_FIXTURES / f"{name}_after.md",
                    scene=scene,
                )
                self.assertFalse(first["invariants"]["hard_failure"])
                self.assertEqual(0, first["lexical_summary"]["unexplained_high_candidates"])
                self.assertEqual(0, first["lexical_summary"]["introduced_candidates"])
                request = first["warning_review_request"]
                resolutions = {
                    item["warning_fingerprint"]: (
                        "人工建议恢复相应模态或写作命令以保留原句表达功能"
                    )
                    for item in request["warnings"]
                }
                second = validator.validate(
                    FORWARD_FIXTURES / f"{name}_before.md",
                    GOLD_FIXTURES / f"{name}_after.md",
                    scene=scene,
                    warning_resolutions=resolutions,
                    warning_review_request_sha256=request["request_sha256"],
                )
                self.assertEqual("REVIEW", second["status"])
                self.assertEqual(2, second["exit_code"])
                self.assertEqual([], second["accepted_warnings"])
                self.assertFalse(
                    second["warning_proposal_state"]["review_clearance_granted"]
                )

    def test_third_blind_pass_is_honest_but_still_requires_review(self) -> None:
        expected = {
            "course": "LEX-COACH-01",
            "modeling": "LEX-FUTURE-01",
            "research": "LEX-FOUNDATION-01",
        }
        scenes = {"course": "COURSE", "modeling": "MODELING", "research": "RESEARCH"}
        for name, signal_id in expected.items():
            with self.subTest(scene=name):
                payload = validator.validate(
                    FORWARD_FIXTURES / f"{name}_before.md",
                    FORWARD_V5_FIXTURES / f"{name}_after.md",
                    scene=scenes[name],
                )
                high_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
                introduced_ids = {item["signal_id"] for item in payload["introduced_findings"]}
                self.assertEqual("REVIEW", payload["status"])
                self.assertIn(signal_id, high_ids | introduced_ids)

    def test_usability_red_blue_research_bridge_is_detected(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures" / "humanize_usability_red_blue"
        payload = validator.validate(
            fixture_root / "research_before.md",
            fixture_root / "research_blue_body.md",
            scene="RESEARCH",
        )
        introduced_ids = {item["signal_id"] for item in payload["introduced_findings"]}
        self.assertEqual("REVIEW", payload["status"])
        self.assertIn("LEX-FOUNDATION-01", introduced_ids)

    def test_fresh_forward_foundation_synonym_cannot_receive_false_pass(self) -> None:
        before, after = self.pair(
            "已有研究表明，参数 $\\alpha=0.35$ 时，该方法可能在一定程度上显著提升系统稳定性。"
            "值得注意的是，这一结果不仅深刻揭示了控制机制，而且为后续研究奠定了坚实基础。",
            "已有研究表明，参数 $\\alpha=0.35$ 时，该方法可能在一定程度上显著提升系统稳定性。"
            "这一结果不仅揭示了控制机制，而且是后续研究的出发点。",
        )

        payload = validator.validate(before, after, scene="RESEARCH")
        high_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertIn("LEX-FOUNDATION-01", high_ids)

    def test_v33_forward_reliable_starting_point_cannot_receive_style_pass(self) -> None:
        before, after = self.pair(
            "现有数据并不能证明界面重排是唯一原因。"
            "本研究深刻揭示了该现象的内在机制，并为后续研究奠定了坚实基础。",
            "现有数据并不能证明界面重排是唯一原因。"
            "本研究由此阐明了该现象的内在机制，相关结果也为后续研究提供了可靠起点。",
        )

        payload = validator.validate(before, after, scene="RESEARCH")
        high_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertIn("LEX-FOUNDATION-01", high_ids)

    def test_v51_abstract_insight_repair_and_vague_depth_cannot_receive_style_pass(self) -> None:
        before, after = self.pair(
            "这一现象并非单纯的测量误差问题，而是涉及更深层次的机制问题。"
            "综上，本研究深刻揭示了该现象的内在机制，并为后续研究奠定了坚实基础。",
            "这一现象并非单纯的测量误差问题，而是涉及更深层次的机制问题。"
            "上述结果为理解该现象的内在机制提供了线索。",
        )

        payload = validator.validate(before, after, scene="RESEARCH")
        high_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
        introduced_ids = {item["signal_id"] for item in payload["introduced_findings"]}

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("REVIEW", payload["style_signal_layer_status"])
        self.assertIn("LEX-VAGUE-DEPTH-01", high_ids)
        self.assertIn("LEX-ABSTRACT-BENEFIT-01", introduced_ids)

    def test_fresh_course_synonym_repairs_cannot_receive_false_pass(self) -> None:
        before, after = self.pair(
            "\\begin{solution}必须牢记，遇到这类题千万不要直接套公式。"
            "值得注意的是，当 $x>0$ 时，由 $f'(x)=2x$ 可知函数递增。"
            "因此，我们可以很容易地得出最终结论。\\end{solution}",
            "\\begin{solution}遇到这类题，必须注意，不要直接套公式。"
            "当 $x>0$ 时，由 $f'(x)=2x$ 可知函数递增，由此可以得出结论。\\end{solution}",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")
        high_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
        introduced_ids = {item["signal_id"] for item in payload["introduced_findings"]}

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertIn("LEX-COACH-01", high_ids)
        self.assertIn("LEX-CONCLUDE-01", introduced_ids)

    def test_v34_course_source_conflict_selection_has_a_specific_review_reason(self) -> None:
        before, after = self.pair(
            "若已知速度随时间减小，就可以直接套用匀变速公式。\n"
            "先确认题目给出的量是否满足匀变速条件；若条件不满足，"
            "不能因为公式看起来相似就直接代入。",
            "看到速度随时间减小，不能据此直接套用匀变速公式。\n"
            "先确认题目给出的量是否满足匀变速条件；若条件不满足，"
            "即使公式形式相似，也不能直接代入。",
            suffix=".tex",
        )

        payload = validator.validate(before, after, scene="COURSE")
        warning_codes = {
            item["code"] for item in payload["unaccepted_warnings"]
        }

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertIn("speech_act_warning", payload["review_reasons"])
        self.assertIn(
            "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
            warning_codes,
        )
        request_codes = {
            item["code"] for item in payload["warning_review_request"]["warnings"]
        }
        self.assertIn(
            "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
            request_codes,
        )

    def test_v34_draft_derived_comparison_from_numbers_requires_review(self) -> None:
        before, after = self.pair(
            "甲的降幅为 20.5%，乙的降幅为 24.9%。"
            "污染情景下两者降幅为 45.0% 和 38.0%。"
            "这一情景用于比较污染叠加对基线收益的侵蚀。",
            "甲的降幅为 20.5%，乙的降幅为 24.9%，因此乙的降幅更大。"
            "污染情景下两者降幅为 45.0% 和 38.0%，均高于前一情景，"
            "反映出污染叠加对基线收益的进一步侵蚀。",
        )

        payload = validator.validate(before, after, mode="DRAFT", scene="MODELING")
        warnings = {
            item["code"]: item for item in payload["unaccepted_warnings"]
        }

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertIn("DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED", warnings)
        details = warnings["DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED"]["details"]
        self.assertEqual("NOT_EVALUATED", details["semantic_entailment"])
        self.assertEqual("PRESERVE_EXPLICIT_SUPPLIED_RELATIONS", details["required_action"])
        self.assertGreaterEqual(len(details["introduced_candidates"]), 2)
        self.assertIn(
            "derived_comparison_markers",
            payload["draft_surface_source_check"]["scope"],
        )

    def test_v34_explicitly_supplied_comparison_does_not_trigger_draft_warning(self) -> None:
        before, after = self.pair(
            "甲的降幅为 20.5%，乙的降幅为 24.9%，乙的降幅更大。",
            "乙的降幅更大：甲为 20.5%，乙为 24.9%。",
        )

        payload = validator.validate(before, after, mode="DRAFT", scene="MODELING")
        warning_codes = {
            item["code"] for item in payload["unaccepted_warnings"]
        }
        self.assertNotIn("DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED", warning_codes)

    def test_v35_real_material_predicate_upgrade_reaches_delivery_review_request(self) -> None:
        before, after = self.pair(
            "综合健康指数是内部比较指标，不是外部生态健康验证。",
            "综合健康指数验证了实际生态健康状况。",
        )
        payload = validator.validate(before, after, scene="MODELING")
        warning_codes = {item["code"] for item in payload["unaccepted_warnings"]}
        request_codes = {
            item["code"] for item in payload["warning_review_request"]["warnings"]
        }

        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("REVIEW", payload["speech_act_layer_status"])
        self.assertIn("SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION", warning_codes)
        self.assertIn("SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION", request_codes)
        self.assertFalse(payload["humanize_quality_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
