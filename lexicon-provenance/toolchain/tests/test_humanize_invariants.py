import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "humanize_invariants"
SCRIPT = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
) / "scripts" / "check_humanize_invariants.py"

SPEC = importlib.util.spec_from_file_location("check_humanize_invariants", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
invariants = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = invariants
SPEC.loader.exec_module(invariants)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def codes(result: object, field: str) -> set[str]:
    return {item.code for item in getattr(result, field)}


class HumanizeInvariantTests(unittest.TestCase):
    def test_safe_style_rewrite_passes_without_warning(self) -> None:
        result = invariants.check_documents(
            fixture("safe_before.md"),
            fixture("safe_after.md"),
            document_format="markdown",
        )
        self.assertEqual("pass", result.status)
        self.assertFalse(result.errors)
        self.assertFalse(result.warnings)
        self.assertEqual("NOT_PROVIDED", result.evidence["protected_terms"]["status"])
        self.assertIsNone(result.evidence["protected_terms"]["sha256"])
        self.assertEqual("DOCUMENT", result.evidence["document_scope"])

    def test_explicit_method_and_material_terms_are_hard_invariants(self) -> None:
        result = invariants.check_documents(
            "采用有限元法求解，材料为 Q235钢。有限元法保持不变。",
            "采用谱方法求解，材料为 Q345钢。",
            protected_terms=["有限元法", "Q235钢"],
        )
        self.assertIn("PROTECTED_TERM_CHANGED", codes(result, "errors"))
        evidence = result.evidence["protected_terms"]
        self.assertEqual("CHECKED", evidence["status"])
        self.assertEqual(2, evidence["count"])
        self.assertRegex(str(evidence["sha256"]), r"^[0-9a-f]{64}$")

    def test_changed_formula_is_a_hard_failure(self) -> None:
        result = invariants.check_documents(
            fixture("changed_formula_before.tex"),
            fixture("changed_formula_after.tex"),
            document_format="tex",
        )
        self.assertTrue(result.hard_failure)
        self.assertIn("PROTECTED_MATH_CHANGED", codes(result, "errors"))

    def test_alignat_formula_is_protected(self) -> None:
        result = invariants.check_documents(
            "\\begin{alignat}{2}\nx &= y\n\\end{alignat}\n",
            "\\begin{alignat}{2}\nx &= z\n\\end{alignat}\n",
            document_format="tex",
        )
        self.assertIn("PROTECTED_MATH_CHANGED", codes(result, "errors"))

    def test_exam_and_formal_statement_environments_are_protected(self) -> None:
        result = invariants.check_documents(
            "\\begin{exercise}\n求函数的极值。\n\\end{exercise}\n",
            "\\begin{exercise}\n计算函数的极值。\n\\end{exercise}\n",
            document_format="tex",
        )
        self.assertIn("PROTECTED_FORMAL_STATEMENT_CHANGED", codes(result, "errors"))

    def test_changed_direct_quote_is_a_hard_failure_by_default(self) -> None:
        before = fixture("changed_quote_before.md")
        after = fixture("changed_quote_after.md")
        protected = invariants.check_documents(before, after)
        allowed = invariants.check_documents(before, after, protect_quotes=False)
        self.assertIn("DIRECT_QUOTATION_CHANGED", codes(protected, "errors"))
        self.assertFalse(allowed.errors)

    def test_speech_act_drift_warns_and_strict_mode_fails(self) -> None:
        before = fixture("speech_act_drift_before.md")
        after = fixture("speech_act_drift_after.md")
        normal = invariants.check_documents(before, after)
        strict = invariants.check_documents(before, after, strict_speech_acts=True)
        self.assertFalse(normal.errors)
        self.assertIn("SPEECH_ACT_DEFINITION_NAMING_CHANGED", codes(normal, "warnings"))
        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(normal, "warnings"))
        self.assertIn("SPEECH_ACT_REPORTING_OBSERVATION_CHANGED", codes(normal, "warnings"))
        self.assertTrue(strict.hard_failure)
        self.assertFalse(strict.warnings)

    def test_default_scope_cannot_be_silently_strengthened_to_universal(self) -> None:
        before = "后面所有主要结论，默认都来自这同一批样本。"
        after = "后文的主要结论均来自这批样本。"
        normal = invariants.check_documents(before, after)
        strict = invariants.check_documents(before, after, strict_speech_acts=True)

        code = "SPEECH_ACT_MODALITY_SCOPE_CHANGED"
        self.assertIn(code, codes(normal, "warnings"))
        self.assertIn(code, codes(strict, "errors"))
        modality = normal.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]
        self.assertEqual({"默认": 1}, modality["raw_delta"]["removed"])
        self.assertEqual({}, modality["raw_delta"]["added"])

    def test_unchanged_default_scope_does_not_warn(self) -> None:
        result = invariants.check_documents(
            "后文结论默认来自完整样本。",
            "完整样本是后文结论的默认来源。",
        )

        self.assertNotIn(
            "SPEECH_ACT_MODALITY_SCOPE_CHANGED",
            codes(result, "warnings"),
        )

    def test_attribution_source_drift_requires_review_and_strict_mode_fails(self) -> None:
        before = "专家认为，该方法在低频组更稳定。"
        after = "本文证实，该方法在低频组更稳定。"
        normal = invariants.check_documents(before, after)
        strict = invariants.check_documents(before, after, strict_speech_acts=True)
        code = "SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED"
        self.assertFalse(normal.errors)
        self.assertIn(code, codes(normal, "warnings"))
        self.assertIn(code, codes(strict, "errors"))
        self.assertTrue(strict.hard_failure)

    def test_unchanged_explicit_attribution_does_not_warn(self) -> None:
        before = "王明（2020）指出，该效应只在低频组出现。"
        after = "王明（2020）指出，该效应仅在低频组出现。"
        result = invariants.check_documents(before, after)
        self.assertNotIn("SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED", codes(result, "warnings"))

    def test_v19_focus_scope_cannot_be_absolutized_silently(self) -> None:
        normal = invariants.check_documents(
            "本问的重点不是比较两个物种的绝对值，而是考察政策收益的保留程度。",
            "本问不比较两个物种的绝对值，而是考察政策收益的保留程度。",
        )
        strict = invariants.check_documents(
            "本问的重点不是比较两个物种的绝对值，而是考察政策收益的保留程度。",
            "本问不比较两个物种的绝对值，而是考察政策收益的保留程度。",
            strict_speech_acts=True,
        )

        self.assertIn("SPEECH_ACT_FOCUS_SCOPE_CHANGED", codes(normal, "warnings"))
        self.assertIn("SPEECH_ACT_FOCUS_SCOPE_CHANGED", codes(strict, "errors"))

    def test_v7_directive_must_not_become_completed_artifact_assertion(self) -> None:
        result = invariants.check_documents(
            "表格的作用在于统一实验口径，正文里要保留 20 ℃、25 ℃ 和 30 ℃ 三组数据。",
            "表格列出 20 ℃、25 ℃ 和 30 ℃ 三组数据，以统一实验口径。",
        )
        self.assertIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", codes(result, "warnings"))

    def test_v41_editorial_evidence_instruction_must_not_become_support_claim(self) -> None:
        result = invariants.check_documents(
            "正文里既要保留粗扫结果，也要保留加密扫描结果，并把结论写成区间性的观测判断。",
            "粗扫结果与加密扫描结果共同支持区间性的观测判断。",
        )
        self.assertIn("SPEECH_ACT_EDITORIAL_TO_EVIDENCE", codes(result, "warnings"))

    def test_v42_editorial_location_scope_cannot_be_silently_deleted(self) -> None:
        result = invariants.check_documents(
            "因此，正文里既要保留粗扫结果，也要保留加密扫描结果，并把结论写成区间性的观测判断。",
            "因此，既要保留粗扫结果，也要保留加密扫描结果，并把结论写成区间性的观测判断。",
        )
        self.assertIn(
            "SPEECH_ACT_EDITORIAL_SCOPE_DROPPED",
            codes(result, "warnings"),
        )

    def test_v42_editorial_location_scope_may_move_without_warning(self) -> None:
        result = invariants.check_documents(
            "正文里需要保留粗扫结果和加密扫描结果。",
            "粗扫结果和加密扫描结果都需要保留在正文中。",
        )
        self.assertNotIn(
            "SPEECH_ACT_EDITORIAL_SCOPE_DROPPED",
            codes(result, "warnings"),
        )

    def test_v42_unscoped_or_non_directive_prose_does_not_trigger_scope_gate(self) -> None:
        unscoped = invariants.check_documents(
            "需要保留粗扫结果和加密扫描结果。",
            "粗扫结果和加密扫描结果需要保留。",
        )
        descriptive = invariants.check_documents(
            "正文中展示了粗扫结果和加密扫描结果。",
            "这里展示了粗扫结果和加密扫描结果。",
        )
        self.assertNotIn(
            "SPEECH_ACT_EDITORIAL_SCOPE_DROPPED",
            codes(unscoped, "warnings"),
        )
        self.assertNotIn(
            "SPEECH_ACT_EDITORIAL_SCOPE_DROPPED",
            codes(descriptive, "warnings"),
        )

    def test_v7_support_claim_must_not_become_actual_engineering_use(self) -> None:
        result = invariants.check_documents(
            "该模型形成了从数据到决策的完整闭环，为工程应用提供有力支撑。",
            "该模型将参数扫描结果用于工程决策，为工程应用提供依据。",
        )
        self.assertIn("SPEECH_ACT_SUPPORT_TO_ACTUAL_USE", codes(result, "warnings"))

    def test_v41_new_singular_first_person_reference_requires_review(self) -> None:
        result = invariants.check_documents(
            "工程上，下一阶段先完成三件事。",
            "下一阶段我先做三件事。",
        )
        self.assertIn(
            "SPEECH_ACT_FIRST_PERSON_REFERENCE_INTRODUCED",
            codes(result, "warnings"),
        )

    def test_v41_removing_presenter_plural_does_not_require_person_shift_review(self) -> None:
        result = invariants.check_documents(
            "我们先核对条件，再写出结果。",
            "先核对条件，再写出结果。",
        )
        self.assertNotIn(
            "SPEECH_ACT_FIRST_PERSON_REFERENCE_INTRODUCED",
            codes(result, "warnings"),
        )

    def test_v7_hedge_stack_must_not_become_new_degree_claim(self) -> None:
        result = invariants.check_documents(
            "模型可能在一定程度上或许仍会受到传感器漂移影响。",
            "传感器漂移可能影响模型，影响程度或许有限。",
        )
        self.assertIn("SPEECH_ACT_MODALITY_TO_DEGREE", codes(result, "warnings"))

    def test_v32_local_redundant_possibility_stack_can_collapse_to_one_hedge(self) -> None:
        result = invariants.check_documents(
            "该结果可能在一定程度上或许暗示界面重排。",
            "该结果可能暗示界面重排。",
        )

        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        self.assertNotIn("SPEECH_ACT_MODALITY_TO_DEGREE", codes(result, "warnings"))
        modality = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]
        self.assertEqual([], modality["residual_delta"])
        self.assertEqual(1, len(modality["safe_compression_allowances"]))
        allowance = modality["safe_compression_allowances"][0]
        self.assertEqual(2, allowance["budget"])
        self.assertEqual(2, allowance["consumed"])
        self.assertEqual(0, allowance["remaining"])

    def test_v33_speech_occurrences_include_line_column_claim_and_context(self) -> None:
        text = "首句保持不变。\n该结果可能成立，也或许受边界影响。"
        result = invariants.check_documents(text, text)
        occurrences = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"]

        self.assertEqual(["可能", "或许"], [item["marker"] for item in occurrences])
        self.assertEqual(2, occurrences[0]["line"])
        self.assertEqual(4, occurrences[0]["column"])
        self.assertRegex(str(occurrences[0]["sentence_id"]), r"^T\d{4}$")
        self.assertRegex(str(occurrences[0]["claim_id"]), r"^C\d{4}$")
        self.assertIn("该结果可能成立", occurrences[0]["sentence_context"])

    def test_single_character_modal_ying_respects_lexical_boundaries(self) -> None:
        non_modal = (
            "相应参数、响应信号、适应过程和供应条件均已记录；"
            "呼应关系、回应信号、感应电流和顺应性也已讨论；"
            "应急预案与应激反应另行说明。"
        )
        result = invariants.check_documents(non_modal, non_modal)
        modality = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]
        self.assertEqual([], modality["before_occurrences"])
        self.assertEqual([], modality["after_occurrences"])

        modal = "应当保留该项；应予说明；应由作者复核；应开展后续实验。"
        modal_result = invariants.check_documents(modal, modal)
        modal_occurrences = modal_result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"]
        self.assertEqual(
            ["应当", "应", "应", "应"],
            [item["marker"] for item in modal_occurrences],
        )

    def test_full_lexical_exclusion_suppresses_every_single_marker_in_span(self) -> None:
        technical = "该表示不可约；模型满足不可压缩流条件。"
        result = invariants.check_documents(technical, technical)
        categories = result.evidence["speech_act_audit"]["categories"]

        self.assertEqual([], categories["negation"]["before_occurrences"])
        self.assertEqual([], categories["modality_scope"]["before_occurrences"])

        directive = "本轮不可开展；下一轮可开展；相关说明应开展。"
        directive_result = invariants.check_documents(directive, directive)
        directive_categories = directive_result.evidence["speech_act_audit"][
            "categories"
        ]
        self.assertEqual(
            ["不"],
            [item["marker"] for item in directive_categories["negation"]["before_occurrences"]],
        )
        self.assertEqual(
            ["可", "可", "应"],
            [
                item["marker"]
                for item in directive_categories["modality_scope"]["before_occurrences"]
            ],
        )

    def test_negative_technical_predicates_keep_real_negation_polarity(self) -> None:
        cases = (
            ("该函数不连续。", "该函数连续。"),
            ("两个对象不同。", "两个对象相同。"),
            ("该结构不对称。", "该结构对称。"),
        )
        for before, after in cases:
            with self.subTest(before=before):
                normal = invariants.check_documents(before, after)
                strict = invariants.check_documents(
                    before,
                    after,
                    strict_speech_acts=True,
                )
                code = "SPEECH_ACT_NEGATION_CHANGED"
                self.assertIn(code, codes(normal, "warnings"))
                self.assertIn(code, codes(strict, "errors"))
                self.assertTrue(strict.hard_failure)
                occurrences = normal.evidence["speech_act_audit"]["categories"][
                    "negation"
                ]["before_occurrences"]
                self.assertEqual(["不"], [item["marker"] for item in occurrences])

    def test_technical_ke_terms_do_not_create_modality_drift(self) -> None:
        before = "该函数可微，积分可积，映射可逆，曲线可导。"
        after = "该函数存在导数，积分存在，映射存在逆，曲线存在导数。"
        result = invariants.check_documents(
            before,
            after,
            strict_speech_acts=True,
        )

        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "errors"))
        modality = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]
        self.assertEqual([], modality["before_occurrences"])
        self.assertEqual([], modality["after_occurrences"])

    def test_bukewei_excludes_technical_ke_but_preserves_bu_polarity(self) -> None:
        result = invariants.check_documents(
            "该函数不可微。",
            "该函数可微。",
            strict_speech_acts=True,
        )
        categories = result.evidence["speech_act_audit"]["categories"]

        self.assertIn("SPEECH_ACT_NEGATION_CHANGED", codes(result, "errors"))
        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "errors"))
        self.assertEqual(
            ["不"],
            [item["marker"] for item in categories["negation"]["before_occurrences"]],
        )
        self.assertEqual([], categories["modality_scope"]["before_occurrences"])
        self.assertEqual([], categories["modality_scope"]["after_occurrences"])

    def test_route_shell_exempts_only_its_leading_logical_marker(self) -> None:
        before = "因此本节讨论方法，所以结论成立。"
        after = "本节讨论方法，结论成立。"
        normal = invariants.check_documents(before, after)
        strict = invariants.check_documents(
            before,
            after,
            strict_speech_acts=True,
        )

        code = "SPEECH_ACT_LOGICAL_RELATION_CHANGED"
        self.assertIn(code, codes(normal, "warnings"))
        self.assertIn(code, codes(strict, "errors"))
        logical = normal.evidence["speech_act_audit"]["categories"][
            "logical_relation"
        ]
        self.assertEqual(["所以"], [item["marker"] for item in logical["before_occurrences"]])
        self.assertEqual({"所以": 1}, logical["raw_delta"]["removed"])

    def test_leading_route_shell_may_be_deleted_without_logical_warning(self) -> None:
        result = invariants.check_documents(
            "因此，本节讨论方法。",
            "本节讨论方法。",
            strict_speech_acts=True,
        )

        self.assertNotIn("SPEECH_ACT_LOGICAL_RELATION_CHANGED", codes(result, "errors"))

    def test_empty_emphasis_shell_marker_is_not_treated_as_modality(self) -> None:
        result = invariants.check_documents(
            "需要指出的是，问卷结果可能受样本结构影响。",
            "问卷结果可能受样本结构影响。",
            strict_speech_acts=True,
        )

        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "errors"))
        modality = result.evidence["speech_act_audit"]["categories"]["modality_scope"]
        self.assertEqual(["可能"], [item["marker"] for item in modality["before_occurrences"]])

    def test_future_bridge_shell_marker_may_be_deleted_but_real_inference_remains_protected(self) -> None:
        shell = invariants.check_documents(
            "本文梳理三类回答，从而为后续分析提供可靠起点。",
            "本文梳理三类回答。",
            strict_speech_acts=True,
        )
        inference = invariants.check_documents(
            "样本扩大，从而误差下降。",
            "样本扩大，误差下降。",
            strict_speech_acts=True,
        )

        self.assertNotIn("SPEECH_ACT_LOGICAL_RELATION_CHANGED", codes(shell, "errors"))
        self.assertIn("SPEECH_ACT_LOGICAL_RELATION_CHANGED", codes(inference, "errors"))

    def test_suoyiran_is_not_a_logical_relation_marker(self) -> None:
        result = invariants.check_documents(
            "还应进一步说明其所以然。",
            "还应进一步解释其中原因。",
            strict_speech_acts=True,
        )

        self.assertNotIn("SPEECH_ACT_LOGICAL_RELATION_CHANGED", codes(result, "errors"))
        logical = result.evidence["speech_act_audit"]["categories"][
            "logical_relation"
        ]
        self.assertEqual([], logical["before_occurrences"])
        self.assertEqual([], logical["after_occurrences"])

    def test_formula_caption_connectives_cannot_be_silently_deleted(self) -> None:
        before = (
            "水平方向合力为\n"
            " \\(F_x=F-\\mu N.\\)\n"
            "因此\n"
            " \\(a=F_x/m.\\)\n"
            "求取极值后\n"
            " \\(a'=0.\\)\n"
            "于是\n"
            " \\(\\tan\\theta=\\mu.\\)"
        )
        after = (
            "水平方向合力为\n"
            " \\(F_x=F-\\mu N.\\)\n"
            " \\(a=F_x/m.\\)\n"
            "求取极值后\n"
            " \\(a'=0.\\)\n"
            " \\(\\tan\\theta=\\mu.\\)"
        )
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn(
            "SPEECH_ACT_LOGICAL_RELATION_CHANGED",
            codes(result, "warnings"),
        )
        logical = result.evidence["speech_act_audit"]["categories"][
            "logical_relation"
        ]
        self.assertEqual({"因此": 1, "于是": 1}, logical["raw_delta"]["removed"])
        self.assertEqual({}, logical["raw_delta"]["added"])

    def test_formula_caption_connectives_may_move_without_count_drift(self) -> None:
        before = "因此\n \\(a=F/m.\\)\n于是\n \\(a'=0.\\)"
        after = "由前式，因此 \\(a=F/m.\\)；求导后，于是 \\(a'=0.\\)"
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertNotIn(
            "SPEECH_ACT_LOGICAL_RELATION_CHANGED",
            codes(result, "warnings"),
        )

    def test_v33_modality_relocation_between_claims_cannot_hide_behind_equal_counts(self) -> None:
        result = invariants.check_documents(
            "甲可能成立。乙成立。",
            "甲成立。乙可能成立。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        diagnostic = next(
            item
            for item in result.warnings
            if item.code == "SPEECH_ACT_MODALITY_SCOPE_CHANGED"
        )
        self.assertEqual({}, diagnostic.details["raw_delta"]["removed"])
        self.assertEqual({}, diagnostic.details["raw_delta"]["added"])
        self.assertEqual(2, len(diagnostic.details["residual_delta"]))

    def test_v33_local_allowance_cannot_pay_for_other_claim_or_new_claim(self) -> None:
        result = invariants.check_documents(
            "甲可能或许成立。乙可能成立。",
            "甲可能成立。乙成立。丙可能成立。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        diagnostic = next(
            item
            for item in result.warnings
            if item.code == "SPEECH_ACT_MODALITY_SCOPE_CHANGED"
        )
        self.assertEqual(1, len(diagnostic.details["safe_compression_allowances"]))
        self.assertTrue(diagnostic.details["residual_delta"])

    def test_v33_protected_quote_cannot_lend_possibility_allowance(self) -> None:
        result = invariants.check_documents(
            "“可能或许”，甲可能成立。",
            "“可能或许”，甲成立。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        occurrences = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"]
        self.assertEqual(["可能"], [item["marker"] for item in occurrences])

    def test_v33_degree_claim_in_another_sentence_cannot_exempt_modality_drift(self) -> None:
        result = invariants.check_documents(
            "甲可能或许改变。乙影响有限。",
            "甲可能改变且影响显著。乙影响有限。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))

    def test_v33_single_core_possibility_plus_degree_phrase_has_no_allowance(self) -> None:
        result = invariants.check_documents(
            "该结果可能在一定程度上改变。",
            "该结果可能改变。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        modality = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]
        self.assertEqual([], modality["safe_compression_allowances"])

    def test_v33_duplicate_claim_keys_fail_closed_without_allowance(self) -> None:
        result = invariants.check_documents(
            "甲可能或许成立。甲可能或许成立。",
            "甲可能成立。甲可能成立。",
        )

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        pairing = result.evidence["speech_act_audit"]["claim_pairing"]
        self.assertEqual(0, pairing["unique_exact_pairs"])

    def test_v33_tex_comment_and_formal_statement_do_not_supply_speech_markers(self) -> None:
        before = (
            "% 可能或许只是注释\n"
            "\\begin{definition}可能或许作为正式表述。\\end{definition}\n"
            "正文可能成立。"
        )
        after = (
            "% 可能或许只是注释\n"
            "\\begin{definition}可能或许作为正式表述。\\end{definition}\n"
            "正文成立。"
        )
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))
        occurrences = result.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"]
        self.assertEqual(["可能"], [item["marker"] for item in occurrences])

    def test_v33_crlf_and_lf_share_stable_occurrence_coordinates(self) -> None:
        crlf = invariants.check_documents(
            "首行。\r\n结果可能成立。", "首行。\r\n结果可能成立。"
        )
        lf = invariants.check_documents(
            "首行。\n结果可能成立。", "首行。\n结果可能成立。"
        )
        crlf_occurrence = crlf.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"][0]
        lf_occurrence = lf.evidence["speech_act_audit"]["categories"][
            "modality_scope"
        ]["before_occurrences"][0]

        self.assertEqual(
            (lf_occurrence["line"], lf_occurrence["column"]),
            (crlf_occurrence["line"], crlf_occurrence["column"]),
        )

    def test_v33_inherited_claim_strength_tension_is_nonblocking_advisory(self) -> None:
        text = "该结果可能证明机制成立。"
        normal = invariants.check_documents(text, text)
        strict = invariants.check_documents(text, text, strict_speech_acts=True)

        code = "SPEECH_ACT_INHERITED_CLAIM_STRENGTH_TENSION"
        self.assertIn(code, codes(normal, "advisories"))
        self.assertNotIn(code, codes(normal, "warnings"))
        self.assertFalse(normal.errors)
        self.assertFalse(strict.errors)
        advisory = next(item for item in normal.advisories if item.code == code)
        self.assertTrue(advisory.details["inherited"])
        self.assertEqual("NONE", advisory.details["automatic_decision"])
        self.assertEqual("NOT_EVALUATED", advisory.details["semantic_judgment"])

    def test_v32_yiweizhe_is_implication_not_definition_marker(self) -> None:
        result = invariants.check_documents(
            "这并不意味着已经排除仪器漂移。",
            "这并不代表已经排除仪器漂移。",
        )

        self.assertNotIn("SPEECH_ACT_DEFINITION_NAMING_CHANGED", codes(result, "warnings"))
        self.assertIn("SPEECH_ACT_NEGATION_CHANGED", codes(result, "warnings"))

    def test_v7_transition_checks_do_not_fire_when_source_already_states_result(self) -> None:
        result = invariants.check_documents(
            "表格列出三组数据。该结果已用于工程决策。传感器漂移的影响程度有限。",
            "表格给出三组数据。该结果用于工程决策。传感器漂移影响有限。",
        )
        transition_codes = {
            "SPEECH_ACT_DIRECTIVE_TO_COMPLETION",
            "SPEECH_ACT_SUPPORT_TO_ACTUAL_USE",
            "SPEECH_ACT_MODALITY_TO_DEGREE",
        }
        self.assertFalse(transition_codes & codes(result, "warnings"))

    def test_v7_transition_checks_respect_strict_mode(self) -> None:
        result = invariants.check_documents(
            "正文里要保留三组数据。该模型为工程应用提供支撑。",
            "表格列出三组数据。该模型用于工程决策。",
            strict_speech_acts=True,
        )
        self.assertIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", codes(result, "errors"))
        self.assertIn("SPEECH_ACT_SUPPORT_TO_ACTUAL_USE", codes(result, "errors"))
        self.assertFalse(result.warnings)

    def test_v34_missing_content_cannot_be_rewritten_as_missing_linkage(self) -> None:
        normal = invariants.check_documents(
            "从模型情景直接滑到治理建议时，缺少成本、政策执行和外部验证层。",
            "从模型情景过渡到治理建议时，缺少成本、政策执行和外部验证层面的衔接。",
        )
        strict = invariants.check_documents(
            "从模型情景直接滑到治理建议时，缺少成本、政策执行和外部验证层。",
            "从模型情景过渡到治理建议时，缺少成本、政策执行和外部验证层面的衔接。",
            strict_speech_acts=True,
        )
        code = "SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE"

        self.assertIn(code, codes(normal, "warnings"))
        self.assertIn(code, codes(strict, "errors"))
        diagnostic = next(item for item in normal.warnings if item.code == code)
        self.assertFalse(diagnostic.details["source_contains_rewrite_predicate"])

    def test_v34_existing_linkage_claim_is_not_a_missing_content_transition(self) -> None:
        result = invariants.check_documents(
            "该段缺少成本分析与政策执行之间的衔接。",
            "该段缺少成本与政策执行层面的联系。",
        )

        self.assertNotIn(
            "SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE",
            codes(result, "warnings"),
        )

    def test_v35_real_gpt_material_predicate_upgrades_require_review(self) -> None:
        cases = (
            (
                "SPEECH_ACT_ABSENCE_TO_FAILURE",
                "MemoryError，因此后续字段没法完整生成。",
                "后续字段验证失败，说明字段生成逻辑有误。",
            ),
            (
                "SPEECH_ACT_PURPOSE_TO_RESULT",
                "污染情景用于比较污染叠加阻隔对基线收益的影响。",
                "结果表明污染叠加阻隔侵蚀了基线收益。",
            ),
            (
                "SPEECH_ACT_PENDING_CHECK_TO_COMPLETION",
                "热生效这点需要实测，宿主可能已把配置读进内存。",
                "配置已经热生效，补丁已关闭。",
            ),
            (
                "SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION",
                "综合健康指数是内部比较指标，不是外部生态健康验证。",
                "综合健康指数验证了实际生态健康状况。",
            ),
            (
                "SPEECH_ACT_CANDIDATE_TO_CONFIRMED",
                "3.20--3.22 是固定初值和短积分窗下的局部混沌候选括号。",
                "K=3.22 是经稳健性验证的混沌临界阈值。",
            ),
        )
        for code, before, after in cases:
            with self.subTest(code=code):
                normal = invariants.check_documents(before, after)
                strict = invariants.check_documents(
                    before,
                    after,
                    strict_speech_acts=True,
                )
                self.assertIn(code, codes(normal, "warnings"))
                self.assertIn(code, codes(strict, "errors"))
                diagnostic = next(item for item in normal.warnings if item.code == code)
                self.assertEqual("NOT_EVALUATED", diagnostic.details["semantic_judgment"])
                self.assertFalse(diagnostic.details["source_contains_rewrite_predicate"])

    def test_v35_predicate_upgrade_controls_preserve_supplied_status(self) -> None:
        cases = (
            (
                "SPEECH_ACT_ABSENCE_TO_FAILURE",
                "MemoryError，因此后续字段没法完整生成。",
                "MemoryError 后，后续字段仍未完整生成。",
            ),
            (
                "SPEECH_ACT_PURPOSE_TO_RESULT",
                "污染情景用于比较污染叠加阻隔对基线收益的影响。",
                "污染情景仍用于比较污染叠加阻隔对基线收益的影响。",
            ),
            (
                "SPEECH_ACT_PENDING_CHECK_TO_COMPLETION",
                "热生效这点需要实测，宿主可能已把配置读进内存。",
                "配置是否热生效仍需实测。",
            ),
            (
                "SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION",
                "综合健康指数是内部比较指标，不是外部生态健康验证。",
                "综合健康指数仍是内部比较指标，不构成外部生态健康验证。",
            ),
            (
                "SPEECH_ACT_CANDIDATE_TO_CONFIRMED",
                "3.20--3.22 是固定初值和短积分窗下的局部混沌候选括号。",
                "3.20--3.22 仍只作为当前条件下的局部混沌候选括号。",
            ),
        )
        for code, before, after in cases:
            with self.subTest(code=code):
                result = invariants.check_documents(before, after)
                self.assertNotIn(code, codes(result, "warnings"))

    def test_v35_existing_result_predicate_and_protected_text_do_not_false_trigger(self) -> None:
        supplied_result = invariants.check_documents(
            "结果表明污染叠加阻隔侵蚀了基线收益。",
            "结果显示污染叠加阻隔侵蚀了基线收益。",
        )
        protected = invariants.check_documents(
            "```text\n内部指标不是外部验证。\n```",
            "```text\n内部指标验证了实际状况。\n```",
        )
        self.assertNotIn("SPEECH_ACT_PURPOSE_TO_RESULT", codes(supplied_result, "warnings"))
        self.assertNotIn(
            "SPEECH_ACT_INTERNAL_TO_EXTERNAL_VALIDATION",
            codes(protected, "warnings"),
        )

    def test_v35_pending_check_completion_does_not_cross_source_clause_boundary(self) -> None:
        overreach = invariants.check_documents(
            "配置已经写入，热生效情况仍待实测。",
            "配置已经写入，并且已生效。",
        )
        safe = invariants.check_documents(
            "配置已经写入，热生效情况仍待实测。",
            "配置已经写入；热生效情况仍待实测。",
        )
        code = "SPEECH_ACT_PENDING_CHECK_TO_COMPLETION"
        self.assertIn(code, codes(overreach, "warnings"))
        self.assertNotIn(code, codes(safe, "warnings"))

    def test_v7_transition_checks_ignore_protected_code_and_math(self) -> None:
        markdown = invariants.check_documents(
            "```text\n正文里要保留三组数据。\n```",
            "```text\n表格列出三组数据。\n```",
        )
        tex = invariants.check_documents(
            "设 $x=\\text{正文里要保留}$。",
            "设 $x=\\text{表格列出}$。",
            document_format="tex",
        )
        self.assertNotIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", codes(markdown, "warnings"))
        self.assertNotIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", codes(tex, "warnings"))

    def test_v8_bujin_is_not_counted_as_negation_or_scope_marker(self) -> None:
        result = invariants.check_documents(
            "该模型不仅全面提升了预测性能，而且形成完整闭环。",
            "",
        )
        self.assertNotIn("SPEECH_ACT_NEGATION_CHANGED", codes(result, "warnings"))
        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", codes(result, "warnings"))

    def test_v40_feichang_is_not_counted_as_sentence_negation(self) -> None:
        result = invariants.check_documents(
            "这一步非常直观地把加速度分成了两部分。",
            "这一步直观地把加速度分成了两部分。",
        )

        self.assertNotIn("SPEECH_ACT_NEGATION_CHANGED", codes(result, "warnings"))
        occurrences = result.evidence["speech_act_audit"]["categories"][
            "negation"
        ]["before_occurrences"]
        self.assertEqual([], occurrences)

    def test_v30_lexicalized_bu_compounds_are_not_sentence_negation(self) -> None:
        result = invariants.check_documents(
            "材料为不锈钢；模型满足不可压缩流条件。",
            "材料采用不锈钢；模型符合不可压缩流条件。",
        )
        self.assertNotIn("SPEECH_ACT_NEGATION_CHANGED", codes(result, "warnings"))
        negation = result.evidence["speech_act_audit"]["categories"]["negation"]
        self.assertEqual([], negation["before_occurrences"])
        self.assertEqual([], negation["after_occurrences"])

    def test_v9_editor_payload_paraphrase_is_not_a_completion_upgrade(self) -> None:
        result = invariants.check_documents(
            "正文里要保留三组数据，温度分别为 20 ℃、25 ℃ 和 30 ℃。",
            "三组数据的温度分别为 20 ℃、25 ℃ 和 30 ℃。",
        )
        self.assertNotIn("SPEECH_ACT_DIRECTIVE_TO_COMPLETION", codes(result, "warnings"))

    def test_v34_source_polarity_tension_cannot_be_resolved_by_selecting_one_side(self) -> None:
        result = invariants.check_documents(
            "若已知速度随时间减小，就可以直接套用匀变速公式。"
            "先确认题目给出的量是否满足匀变速条件；若条件不满足，"
            "不能因为公式看起来相似就直接代入。",
            "看到速度随时间减小，不能据此直接套用匀变速公式。"
            "先确认题目给出的量是否满足匀变速条件；若条件不满足，"
            "即使公式形式相似，也不能直接代入。",
        )

        code = "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED"
        self.assertIn(code, codes(result, "warnings"))
        diagnostic = next(item for item in result.warnings if item.code == code)
        self.assertEqual("NOT_EVALUATED", diagnostic.details["academic_correctness"])
        self.assertEqual("PRESERVE_BOTH_AND_ESCALATE", diagnostic.details["required_action"])
        self.assertTrue(diagnostic.details["shared_anchors"])
        self.assertTrue(diagnostic.details["source_positive_spans"])
        self.assertTrue(diagnostic.details["source_negative_spans"])
        self.assertFalse(diagnostic.details["rewrite_positive_spans"])
        self.assertTrue(diagnostic.details["rewrite_negative_spans"])

    def test_v34_source_polarity_tension_is_not_a_domain_correctness_oracle(self) -> None:
        preserved = invariants.check_documents(
            "满足甲条件时，可以直接使用该公式；不满足甲条件时，不能直接使用该公式。",
            "满足甲条件时，可以直接使用该公式；不满足甲条件时，不能直接使用该公式。",
        )
        unrelated = invariants.check_documents(
            "甲程序可以直接读取数据。乙模型不能直接给出结论。",
            "乙模型不能直接给出结论。",
        )
        code = "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED"

        self.assertNotIn(code, codes(preserved, "warnings"))
        self.assertNotIn(code, codes(unrelated, "warnings"))

    def test_v34_source_polarity_tension_respects_strict_mode(self) -> None:
        result = invariants.check_documents(
            "满足条件时，可以直接使用该公式；条件不足时，不能直接使用该公式。",
            "条件不足时，不能直接使用该公式。",
            strict_speech_acts=True,
        )

        self.assertIn(
            "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
            codes(result, "errors"),
        )
        self.assertFalse(result.warnings)

    def test_v34_source_polarity_tension_ignores_protected_quote_code_and_math(self) -> None:
        quoted = invariants.check_documents(
            "作者写道：“满足条件时可以直接使用该公式；条件不足时不能直接使用该公式。”",
            "作者仍保留原话：“满足条件时可以直接使用该公式；条件不足时不能直接使用该公式。”",
        )
        coded = invariants.check_documents(
            "```text\n可以直接运行；不能直接运行。\n```\n正文甲。",
            "```text\n可以直接运行；不能直接运行。\n```\n正文乙。",
        )
        math = invariants.check_documents(
            r"设 $\text{可以直接使用公式；不能直接使用公式}$，正文甲。",
            r"设 $\text{可以直接使用公式；不能直接使用公式}$，正文乙。",
            document_format="tex",
        )
        code = "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED"

        self.assertNotIn(code, codes(quoted, "warnings"))
        self.assertNotIn(code, codes(coded, "warnings"))
        self.assertNotIn(code, codes(math, "warnings"))

    def test_tex_comments_are_protected_by_default(self) -> None:
        result = invariants.check_documents(
            fixture("tex_comments_before.tex"),
            fixture("tex_comments_after.tex"),
            document_format="tex",
        )
        self.assertIn("TEX_COMMENT_CHANGED", codes(result, "errors"))

    def test_number_or_unit_change_is_a_hard_failure(self) -> None:
        result = invariants.check_documents(
            "样本在 25 ℃ 下保持 30 分钟。",
            "样本在 35 ℃ 下保持 30 分钟。",
        )
        self.assertIn("NUMBER_OR_UNIT_CHANGED", codes(result, "errors"))

    def test_chinese_number_change_is_a_hard_failure(self) -> None:
        result = invariants.check_documents("样本分为三组。", "样本分为四组。")
        self.assertIn("NUMBER_OR_UNIT_CHANGED", codes(result, "errors"))

    def test_replacement_character_or_mojibake_change_is_a_hard_failure(self) -> None:
        replacement = invariants.check_documents("OCR：\ufffd字。", "OCR：清字。")
        mojibake = invariants.check_documents("片段：绾腑。", "片段：正常。")
        self.assertIn("GARBLED_TEXT_CHANGED", codes(replacement, "errors"))
        self.assertIn("GARBLED_TEXT_CHANGED", codes(mojibake, "errors"))

    def test_critical_command_arguments_and_order_are_protected(self) -> None:
        result = invariants.check_documents(
            r"见式 \eqref{eq:a} 与文献 \citep[p. 3]{alpha,beta}。",
            r"见式 \eqref{eq:b} 与文献 \citep[p. 3]{alpha,beta}。",
            document_format="tex",
        )
        self.assertIn("CRITICAL_LATEX_COMMAND_CHANGED", codes(result, "errors"))

    def test_code_fences_and_inline_code_are_protected(self) -> None:
        before = "运行 `python app.py`：\n\n```python\nvalue = 1\n```\n"
        after = "执行 `python app.py`：\n\n```python\nvalue = 2\n```\n"
        result = invariants.check_documents(before, after)
        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_commonmark_longer_closing_fence_is_protected(self) -> None:
        before = "```python\ntoken = alpha\n````\n"
        after = "```python\ntoken = beta\n````\n"
        result = invariants.check_documents(before, after)
        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_tex_verbatim_code_is_protected_and_braces_inside_are_ignored(self) -> None:
        before = "\\verb|mapping = {'a': 1}|\n\\begin{lstlisting}\nx = {1: 2}\n\\end{lstlisting}\n"
        after = "\\verb|mapping = {'a': 1}|\n\\begin{lstlisting}\nx = {1: 3}\n\\end{lstlisting}\n"
        result = invariants.check_documents(before, after, document_format="tex")
        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))
        self.assertNotIn("LATEX_BRACES_UNBALANCED", codes(result, "errors"))

    def test_tex_nonrendering_environment_payload_is_immutable(self) -> None:
        for environment in ("comment", "filecontents", "filecontents*"):
            with self.subTest(environment=environment):
                begin = (
                    f"\\begin{{{environment}}}{{hidden.tex}}"
                    if environment.startswith("filecontents")
                    else f"\\begin{{{environment}}}"
                )
                before = (
                    f"{begin}\n"
                    "\\section{隐藏标题}\n"
                    "token_甲=1\n"
                    f"\\end{{{environment}}}\n"
                    "可见正文。"
                )
                after = before.replace("token_甲=1", "token_甲=2")

                result = invariants.check_documents(
                    before, after, document_format="tex"
                )

                self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_lstinline_with_optional_arguments_is_protected(self) -> None:
        before = r"正文 \lstinline[language=Python]!token_甲=1!。"
        after = r"正文 \lstinline[language=Python]!token_甲=2!。"
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_fancyvrb_inline_verb_is_protected(self) -> None:
        before = r"正文 \Verb+token_甲=1+。"
        after = r"正文 \Verb+token_甲=2+。"
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_declared_short_verb_and_custom_verb_like_changes_are_protected(self) -> None:
        before = (
            "\\DefineShortVerb{\\|}\n"
            "|token_甲=1|\n"
            "\\UndefineShortVerb{\\|}\n"
            "正文 \\CustomVerb!token_乙=2!。"
        )
        after = before.replace("token_甲=1", "token_甲=9").replace(
            "token_乙=2", "token_乙=8"
        )
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_declared_nonverb_custom_command_change_is_protected(self) -> None:
        before = (
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{formatcom=\\small}\n"
            "正文 \\InlineCode|token_甲=1|。"
        )
        after = before.replace("token_甲=1", "token_甲=2")

        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_short_and_custom_verbatim_alias_changes_are_protected(self) -> None:
        before = (
            "\\MakeShortVerb{\\|}\n"
            "|token_甲=1|\n"
            "\\DeleteShortVerb{\\|}\n"
            "\\RecustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "\\InlineCode!token_乙=2!"
        )
        after = before.replace("token_甲=1", "token_甲=9").replace(
            "token_乙=2", "token_乙=8"
        )

        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))

    def test_unclosed_short_verb_change_is_hard_error_and_review(self) -> None:
        before = "\\DefineShortVerb{\\|}\r\n|token_甲=1\r\n后文。"
        after = before.replace("token_甲=1", "token_甲=2")

        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))
        self.assertIn("TEX_PROTECTION_PARSE_REVIEW", codes(result, "warnings"))

    def test_commented_short_verb_declaration_does_not_create_code_span(self) -> None:
        text = "% \\DefineShortVerb{\\|}\n正文 |普通文本|。"

        code, _ranges = invariants._code_spans(text)

        self.assertEqual([], code)

    def test_percent_inside_inline_verbatim_stays_inside_code_span_only(self) -> None:
        text = r"正文 \verb|token%甲项|，随后继续说明。"

        code, ranges = invariants._code_spans(text)

        self.assertEqual([r"\verb|token%甲项|"], code)
        self.assertEqual([r"\verb|token%甲项|"], [text[start:end] for start, end in ranges])

    def test_inline_verbatim_fake_environment_does_not_create_parse_review(self) -> None:
        text = r"正文 \verb|\begin{verbatim}|，随后继续说明。"

        result = invariants.check_documents(text, text, document_format="tex")

        self.assertNotIn("TEX_PROTECTION_PARSE_REVIEW", codes(result, "warnings"))

    def test_protected_multiline_whitespace_and_line_endings_are_exact(self) -> None:
        cases = (
            (
                "verbatim-trailing-space",
                "\\begin{verbatim}\nabc  \n\\end{verbatim}",
                "\\begin{verbatim}\nabc \n\\end{verbatim}",
                "PROTECTED_CODE_CHANGED",
            ),
            (
                "verbatim-crlf",
                "\\begin{verbatim}\r\nabc\r\n\\end{verbatim}",
                "\\begin{verbatim}\nabc\n\\end{verbatim}",
                "PROTECTED_CODE_CHANGED",
            ),
            (
                "math-trailing-space",
                "\\[\na+b  \n\\]",
                "\\[\na+b \n\\]",
                "PROTECTED_MATH_CHANGED",
            ),
            (
                "math-crlf",
                "\\[\r\na+b\r\n\\]",
                "\\[\na+b\n\\]",
                "PROTECTED_MATH_CHANGED",
            ),
        )
        for label, before, after, expected_code in cases:
            with self.subTest(label=label):
                result = invariants.check_documents(
                    before, after, document_format="tex"
                )
                self.assertIn(expected_code, codes(result, "errors"))

    def test_incomplete_tex_protection_requires_review_even_when_unchanged(self) -> None:
        cases = (
            "正文 \\verb|token_甲=1\n后文。",
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "正文 \\InlineCode|token_戊=5\n后文。",
            "正文 \\begin{minted}{python}\ntoken_乙=2\n后文。",
            "\\begin{comment}\ntoken_壬=9\n后文。",
            "正文 $token_丙=3\n后文。",
            "正文 $$token_己=6\n后文。",
            "正文 \\(token_丁=4\n后文。",
            "正文 \\[token_庚=7\n后文。",
            "正文 \\begin{equation}\ntoken_辛=8\n后文。",
        )
        for text in cases:
            with self.subTest(text=text):
                result = invariants.check_documents(
                    text, text, document_format="tex"
                )
                self.assertIn(
                    "TEX_PROTECTION_PARSE_REVIEW", codes(result, "warnings")
                )

    def test_incomplete_protected_payload_change_is_a_hard_error(self) -> None:
        before = "正文 \\verb|token_甲=1\n后文。"
        after = "正文 \\verb|token_甲=2\n后文。"
        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))
        self.assertIn("TEX_PROTECTION_PARSE_REVIEW", codes(result, "warnings"))

    def test_incomplete_declared_custom_payload_change_is_a_hard_error(self) -> None:
        before = (
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "正文 \\InlineCode|token_甲=1\n后文。"
        )
        after = before.replace("token_甲=1", "token_甲=2")

        result = invariants.check_documents(before, after, document_format="tex")

        self.assertIn("PROTECTED_CODE_CHANGED", codes(result, "errors"))
        self.assertIn("TEX_PROTECTION_PARSE_REVIEW", codes(result, "warnings"))

    def test_fullwidth_dollar_is_not_treated_as_tex_math(self) -> None:
        text = "正文 ＄token_甲=1＄。"

        self.assertEqual([], invariants._math_spans(text, []))

    def test_ascii_direct_quote_is_protected(self) -> None:
        result = invariants.check_documents(
            '作者使用 "local response" 指代该现象。',
            '作者使用 "regional response" 指代该现象。',
        )
        self.assertIn("DIRECT_QUOTATION_CHANGED", codes(result, "errors"))

    def test_nested_latex_quote_command_is_protected(self) -> None:
        result = invariants.check_documents(
            r"作者写道：\enquote{模型 \textbf{A} 保持稳定}。",
            r"作者写道：\enquote{模型 \textbf{B} 保持稳定}。",
            document_format="tex",
        )
        self.assertIn("DIRECT_QUOTATION_CHANGED", codes(result, "errors"))

    def test_common_citation_variants_are_protected(self) -> None:
        result = invariants.check_documents(
            r"参见 \parencite[12]{alpha}。",
            r"参见 \parencite[12]{beta}。",
            document_format="tex",
        )
        self.assertIn("CRITICAL_LATEX_COMMAND_CHANGED", codes(result, "errors"))

    def test_comment_only_line_inside_math_is_protected(self) -> None:
        before = "\\[\nx = 1\n% old note 20 and \\ref{fake}\n\\]\n"
        after = "\\[\nx = 1\n\\]\n"
        result = invariants.check_documents(before, after, document_format="tex")
        self.assertIn("TEX_COMMENT_CHANGED", codes(result, "errors"))

    def test_unchanged_comment_and_escaped_percent_pass(self) -> None:
        before = "% keep this layout comment\n比例为 50\\%，因此保留原式。\n"
        after = "% keep this layout comment\n比例为 50\\%，故保留原式。\n"
        result = invariants.check_documents(before, after, document_format="tex")
        self.assertNotIn("TEX_COMMENT_CHANGED", codes(result, "errors"))

    def test_environment_order_and_brace_balance_are_checked(self) -> None:
        before = "\\begin{itemize}\n\\item A\n\\end{itemize}\n"
        after = "\\begin{enumerate}\n\\item A}\n\\end{enumerate}\n"
        result = invariants.check_documents(before, after, document_format="tex")
        self.assertIn("LATEX_ENVIRONMENT_ORDER_CHANGED", codes(result, "errors"))
        self.assertIn("LATEX_BRACES_UNBALANCED", codes(result, "errors"))

    def test_fragment_mode_allows_only_unchanged_boundary_imbalance(self) -> None:
        before = "\\begin{document}\n值得注意的是，结论保持不变。\n"
        after = "\\begin{document}\n结论保持不变。\n"
        whole_document = invariants.check_documents(
            before, after, document_format="tex"
        )
        fragment = invariants.check_documents(
            before,
            after,
            document_format="tex",
            fragment_mode=True,
        )

        self.assertIn("LATEX_ENVIRONMENT_UNBALANCED", codes(whole_document, "errors"))
        self.assertNotIn("LATEX_ENVIRONMENT_UNBALANCED", codes(fragment, "errors"))
        self.assertFalse(fragment.errors)
        self.assertEqual("FRAGMENT", fragment.evidence["document_scope"])

        drifted = invariants.check_documents(
            before,
            "结论保持不变。\n",
            document_format="tex",
            fragment_mode=True,
        )
        self.assertIn("LATEX_ENVIRONMENT_ORDER_CHANGED", codes(drifted, "errors"))

    def test_cli_json_and_exit_codes(self) -> None:
        safe = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(FIXTURES / "safe_before.md"),
                str(FIXTURES / "safe_after.md"),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        changed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(FIXTURES / "changed_formula_before.tex"),
                str(FIXTURES / "changed_formula_after.tex"),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, safe.returncode, safe.stderr)
        self.assertEqual("pass", json.loads(safe.stdout)["status"])
        self.assertEqual(1, changed.returncode, changed.stderr)
        payload = json.loads(changed.stdout)
        self.assertEqual("fail", payload["status"])
        self.assertTrue(payload["hard_failure"])


if __name__ == "__main__":
    unittest.main()
