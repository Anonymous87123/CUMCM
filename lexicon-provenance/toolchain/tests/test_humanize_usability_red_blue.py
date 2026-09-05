import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "humanize_usability_red_blue"
FORWARD_V6 = ROOT / "tests" / "fixtures" / "humanize_forward_v6"
CANONICAL_DIAGNOSE_HEADER = (
    "Severity | Location | Source role | Scene | Signal/Pathology | "
    "Trigger | Reading effect | Decision | Action"
)


class HumanizeUsabilityRedBlueEvidenceTests(unittest.TestCase):
    def load_json(self, relative: str) -> dict:
        return json.loads((FIXTURES / relative).read_text(encoding="utf-8-sig"))

    def test_manifest_cases_and_evidence_paths_are_resolvable(self) -> None:
        manifest = self.load_json("manifest.json")
        self.assertEqual("1.1", manifest["schema_version"])
        self.assertGreaterEqual(len(manifest["cases"]), 7)
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue((FIXTURES / case["before"]).is_file())
                self.assertTrue((FIXTURES / case["after"]).is_file())
        for relative in manifest["artifacts"]["validation"].values():
            self.assertTrue((FIXTURES / relative).is_file())
        self.assertTrue((FIXTURES / manifest["artifacts"]["red_team"]["final_review"]).is_file())
        self.assertTrue((FIXTURES / manifest["artifacts"]["diagnose"]["fresh_output"]).is_file())
        self.assertTrue((FIXTURES / manifest["artifacts"]["tex_e2e"]["before"]).is_file())
        self.assertTrue((FIXTURES / manifest["artifacts"]["tex_e2e"]["result"]).is_file())

    def test_course_retry_is_pre_provenance_failure_evidence(self) -> None:
        payload = self.load_json("validation/course_postfix_retry.json")
        # This archived PASS predates reviewer provenance.  Reason strings alone
        # cannot establish that an external human supplied the decision.
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(0, payload["exit_code"])
        self.assertNotIn("delivery_gate_status", payload)
        self.assertNotIn("warning_review", payload)
        self.assertFalse(payload["invariants"]["hard_failure"])
        self.assertEqual(0, payload["lexical_summary"]["unexplained_high_candidates"])
        accepted = payload["accepted_warning_reasons"]
        self.assertEqual(
            {"SPEECH_ACT_NEGATION_CHANGED", "SPEECH_ACT_MODALITY_SCOPE_CHANGED"},
            set(accepted),
        )
        self.assertTrue(all(len(reason) >= 12 for reason in accepted.values()))

    def test_forward_course_keeps_agent_warning_proposals_at_review(self) -> None:
        run = (FORWARD_V6 / "blind_course_run.md").read_text(encoding="utf-8")
        self.assertIn("真实进程退出码：`2`", run)
        self.assertIn("`delivery_gate_status=REVIEW`", run)
        self.assertIn("`speech_act_layer_status=REVIEW`", run)
        self.assertIn("代理随后给出了两条 warning 处理 proposal", run)
        self.assertIn("未获外部真实人工确认", run)
        self.assertIn("provenance 失败证据", run)
        self.assertIn("不计入生成前向 PASS", run)
        self.assertIn("生成前向有效状态：`REVIEW/2`", run)
        self.assertIn("`warning_review.identity_verified=false`", run)
        self.assertNotIn("人工复核并登记", run)
        self.assertNotIn("最终运行机器字段", run)

    def test_forward_diagnose_has_single_contract_table_and_no_rewrite(self) -> None:
        input_path = FORWARD_V6 / "blind_diagnose_input.md"
        output_path = FORWARD_V6 / "blind_diagnose_output.md"
        run_path = FORWARD_V6 / "blind_diagnose_run.md"
        source = input_path.read_text(encoding="utf-8")
        output = output_path.read_text(encoding="utf-8")
        run = run_path.read_text(encoding="utf-8")

        table_header = "| " + CANONICAL_DIAGNOSE_HEADER + " |"
        self.assertEqual(1, output.count(table_header))
        self.assertEqual(9, len([part for part in table_header.split("|") if part.strip()]))
        self.assertNotIn(source.strip(), output)
        self.assertIn("`UNRESOLVED`", output)
        for forbidden in ("改后正文", "已改写", "已调整"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, output)

        recorded_hashes = re.findall(
            r"诊断[前后]输入 SHA-256：`([0-9A-F]{64})`", run
        )
        self.assertEqual(2, len(recorded_hashes))
        self.assertEqual(recorded_hashes[0], recorded_hashes[1])
        self.assertEqual(
            hashlib.sha256(input_path.read_bytes()).hexdigest().upper(),
            recorded_hashes[0],
        )
        self.assertIn("输出不含改后全文", run)
        self.assertIn("`UNRESOLVED`", run)

    def test_research_fresh_output_is_reviewed_for_new_source_background(self) -> None:
        payload = self.load_json("validation/research_fresh.json")
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        warnings = {item["code"] for item in payload["unaccepted_warnings"]}
        self.assertIn("SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED", warnings)
        details = next(
            item["details"]
            for item in payload["unaccepted_warnings"]
            if item["code"] == "SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED"
        )
        self.assertEqual({"已有研究": 1}, details["after"])
        self.assertEqual({}, details["before"])

    def test_research_final_output_is_reviewed_for_residual_templates(self) -> None:
        payload = self.load_json("validation/research_final.json")
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        signal_ids = {item["signal_id"] for item in payload["unexplained_high_findings"]}
        self.assertEqual(
            {"LEX-EMPH-01", "LEX-MARKET-01", "LEX-FOUNDATION-01"},
            signal_ids,
        )
        self.assertIn("introduced_style_signal", payload["review_reasons"])

    def test_forward_research_record_must_not_confuse_review_with_hard_failure(self) -> None:
        run = (ROOT / "tests" / "fixtures" / "humanize_forward_v6" / "blind_research_run.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("status=REVIEW", run)
        self.assertIn("delivery_gate_status=REVIEW", run)
        self.assertIn("speech_act_layer_status=REVIEW", run)
        self.assertIn("验证器退出码为 2", run)
        self.assertNotIn("验证器退出码为 1", run)

    def test_diagnose_fixture_uses_contract_header_and_does_not_supply_rewrite(self) -> None:
        text = (FIXTURES / "diagnose_fresh_output.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("| " + CANONICAL_DIAGNOSE_HEADER + " |"))
        self.assertNotIn("改后正文", text)
        self.assertNotIn("已调整", text)
        self.assertNotIn("已删除", text)
        self.assertIn("quoted", text)
        self.assertIn("KEEP", text)

    def test_tex_probe_is_narrow_and_does_not_claim_compile_or_idempotency(self) -> None:
        payload = self.load_json("tex_e2e_result.json")
        self.assertEqual("PASS", payload["status"])
        self.assertTrue(payload["full_completion_claim_allowed"])
        self.assertEqual(0, payload["source_files_modified"])
        self.assertEqual("NOT_RUN", payload["compile_check"]["status"])
        self.assertEqual("NOT_RUN", payload["idempotency"])
        self.assertEqual(1, payload["units_total"])

    def test_final_red_team_review_preserves_non_qualification_boundary(self) -> None:
        manifest = self.load_json("manifest.json")
        review = (FIXTURES / manifest["artifacts"]["red_team"]["final_review"]).read_text(
            encoding="utf-8"
        )
        self.assertEqual("15/28", manifest["artifacts"]["red_team"]["score"])
        self.assertEqual("not_qualified", manifest["artifacts"]["red_team"]["default_generation"])
        self.assertEqual(
            "NOT_EVALUATED",
            manifest["artifacts"]["red_team"]["full_generation_qualification"],
        )
        self.assertIn("未确认本轮 P0", review)
        self.assertIn("科研核心维度为 0", review)
        self.assertIn("NOT_EVALUATED", review)


if __name__ == "__main__":
    unittest.main()
