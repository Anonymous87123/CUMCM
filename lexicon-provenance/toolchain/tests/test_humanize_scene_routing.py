import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "route_humanize_scene.py"
POLICY = SKILL / "references" / "scene-routing-policy.json"
SPEC = importlib.util.spec_from_file_location("route_humanize_scene", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
router = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = router
SPEC.loader.exec_module(router)


class HumanizeSceneRoutingTests(unittest.TestCase):
    def test_policy_is_strict_and_hash_stable(self) -> None:
        first, first_hash = router.load_policy(POLICY)
        second, second_hash = router.load_policy(POLICY)

        self.assertEqual(first, second)
        self.assertEqual(first_hash, second_hash)
        self.assertRegex(first_hash, r"^[0-9a-f]{64}$")

    def test_routes_course_modeling_and_research_from_whole_unit_signals(self) -> None:
        cases = (
            ("例题与解析", "本题先辨认条件，再代入公式。", "COURSE"),
            ("问题三的模型建立与求解", "建立状态变量并设置参数，随后进行数值求解。", "MODELING"),
            ("结果与讨论", "本研究的实验结果表明，该判断仅在当前范围成立。", "RESEARCH"),
        )
        for heading, body, expected in cases:
            with self.subTest(expected=expected):
                result = router.route_scene(heading, body)
                self.assertEqual("ROUTED", result["status"])
                self.assertEqual(expected, result["final_scene"])
                self.assertTrue(result["evidence"])

    def test_routes_real_cet6_exam_strategy_language_to_course(self) -> None:
        result = router.route_scene(
            "六级长篇段落匹配做题规律总报告/摘要",
            (
                "第一，长篇段落匹配这十道题，拿到手以后先做哪几道更适合优先处理。"
                "第二，某一道一旦做出来了，下一道更该往文章哪里找。"
                "因为做题时，不是同时处理十道题，而是先做出几题，再利用这些题去帮助别题。"
            ),
        )

        self.assertEqual("ROUTED", result["status"])
        self.assertEqual("COURSE", result["final_scene"])
        self.assertGreater(result["scores"]["COURSE"], result["scores"]["RESEARCH"])
        self.assertIn(
            "COURSE-EXAM-STRATEGY-01",
            {item["rule_id"] for item in result["evidence"]},
        )

    def test_exam_dataset_research_without_teaching_actions_stays_research(self) -> None:
        result = router.route_scene(
            "研究方法",
            "本研究分析考试题目在不同年份的分布，并讨论样本范围。",
        )

        self.assertEqual("ROUTED", result["status"])
        self.assertEqual("RESEARCH", result["final_scene"])

    def test_weak_or_absent_signal_falls_back_to_general(self) -> None:
        result = router.route_scene("背景", "该段保留原有范围说明。")

        self.assertEqual("FALLBACK_GENERAL", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])

    def test_contract_threshold_routes_unique_two_point_scene(self) -> None:
        cases = (
            ("说明", "本节面向学生解释排班方案。", "COURSE"),
            ("说明", "本节建立状态变量并比较方案。", "MODELING"),
            ("说明", "本研究考察当前样本。", "RESEARCH"),
        )
        for heading, body, expected in cases:
            with self.subTest(expected=expected):
                result = router.route_scene(heading, body)
                self.assertEqual("ROUTED", result["status"])
                self.assertEqual(expected, result["final_scene"])

    def test_engineering_experiment_result_stays_modeling_when_body_names_model_output(self) -> None:
        result = router.route_scene("实验结果", "模型输出显示该情景的评价指标下降。")

        self.assertEqual("ROUTED", result["status"])
        self.assertEqual("MODELING", result["final_scene"])

    def test_shared_abstract_introduction_or_conclusion_heading_is_not_research_by_itself(self) -> None:
        for heading, body in (
            ("摘要", "方案甲的指标更低。"),
            ("引言", "这里交代讨论背景。"),
            ("结论", "方向向左。"),
            ("实验结果", "记录值保持不变。"),
        ):
            with self.subTest(heading=heading):
                result = router.route_scene(heading, body)
                self.assertEqual("FALLBACK_GENERAL", result["status"])
                self.assertEqual("GENERAL", result["final_scene"])

    def test_document_prior_requires_aligned_local_evidence(self) -> None:
        result = router.route_scene(
            "结论",
            "方向向左。",
            document_prior_scene="COURSE",
        )

        self.assertEqual("FALLBACK_GENERAL", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])

        aligned = router.route_scene(
            "小结",
            "本题最后核对方向。",
            document_prior_scene="COURSE",
        )
        self.assertEqual("ROUTED", aligned["status"])
        self.assertEqual("COURSE", aligned["final_scene"])

    def test_document_prior_never_resolves_a_strong_ambiguity(self) -> None:
        result = router.route_scene(
            "模型建立与研究方法",
            "本研究建立状态变量模型。",
            document_prior_scene="MODELING",
        )

        self.assertEqual("AMBIGUOUS", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])

    def test_low_score_positive_tie_is_ambiguous_before_general_fallback(self) -> None:
        result = router.route_scene(
            "",
            "本题需要说明。本研究需要说明。",
        )

        self.assertEqual({"COURSE": 2, "MODELING": 0, "RESEARCH": 2}, result["scores"])
        self.assertEqual("AMBIGUOUS", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])
        self.assertEqual(["COURSE", "RESEARCH"], result["ambiguous_scenes"])

    def test_document_prior_cannot_resolve_a_low_score_positive_tie(self) -> None:
        result = router.route_scene(
            "",
            "本题需要说明。本研究需要说明。",
            document_prior_scene="COURSE",
        )

        self.assertEqual("AMBIGUOUS", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])

    def test_tex_solution_or_note_role_routes_to_course(self) -> None:
        for body in ("{solution}先判断受力方向。", "{note}这里解释常见误读。"):
            with self.subTest(body=body):
                result = router.route_scene("答案", body)
                self.assertEqual("ROUTED", result["status"])
                self.assertEqual("COURSE", result["final_scene"])

    def test_ordinary_notebook_or_solution_word_does_not_impersonate_tex_role(self) -> None:
        for body in (
            "使用 Jupyter Notebook 完成分析。",
            "The solution remains part of the implementation discussion.",
        ):
            with self.subTest(body=body):
                result = router.route_scene("方法", body)
                self.assertEqual("FALLBACK_GENERAL", result["status"])
                self.assertEqual("GENERAL", result["final_scene"])

    def test_strong_tie_is_ambiguous_instead_of_using_hidden_priority(self) -> None:
        result = router.route_scene(
            "模型建立与研究方法",
            "本研究建立状态变量模型。",
        )

        self.assertEqual("AMBIGUOUS", result["status"])
        self.assertEqual("GENERAL", result["final_scene"])
        self.assertIn("MODELING", result["ambiguous_scenes"])
        self.assertIn("RESEARCH", result["ambiguous_scenes"])

    def test_evidence_never_exports_matched_text(self) -> None:
        secret = "内部不可导出的研究对象"
        result = router.route_scene("研究方法", f"本研究讨论{secret}。")
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("matched_text", serialized)

    def test_malformed_or_unknown_policy_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = json.loads(POLICY.read_text(encoding="utf-8"))
            payload["unexpected"] = True
            path = Path(temp) / "policy.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(router.RoutingPolicyError, "keys mismatch"):
                router.load_policy(path)

    def test_duplicate_policy_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            raw = POLICY.read_text(encoding="utf-8")
            path = Path(temp) / "policy.json"
            path.write_text('{"revision":999,' + raw.lstrip()[1:], encoding="utf-8")

            with self.assertRaisesRegex(router.RoutingPolicyError, "duplicate JSON key: revision"):
                router.load_policy(path)

    def test_non_finite_policy_numbers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            raw = POLICY.read_text(encoding="utf-8")
            path = Path(temp) / "policy.json"
            path.write_text(
                raw.replace('"minimum_route_score": 2', '"minimum_route_score": NaN'),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(router.RoutingPolicyError, "non-finite JSON number: NaN"):
                router.load_policy(path)


if __name__ == "__main__":
    unittest.main()
