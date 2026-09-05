import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_full_style_corpus.py"
SPEC = importlib.util.spec_from_file_location("full_style_analysis", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class FullStyleAnalysisTests(unittest.TestCase):
    def test_measure_text_reports_sentence_and_rhetorical_features(self) -> None:
        metrics = analysis.measure_text("我先检查结果。当前不是只看数量，而是确认边界；因此建议补充测试。")

        self.assertEqual(2, metrics["sentences"])
        self.assertTrue(metrics["feature_first_person"])
        self.assertTrue(metrics["feature_state_scope"])
        self.assertTrue(metrics["pattern_contrastive"])
        self.assertTrue(metrics["feature_recommendation"])

    def test_classify_markdown_path_separates_system_and_local_writing(self) -> None:
        self.assertEqual("third_party_dependency", analysis.classify_markdown_path(r"D:\repo\node_modules\pkg\README.md"))
        self.assertEqual("codex_skill", analysis.classify_markdown_path(r"C:\Users\Lenovo\.codex\skills\x\SKILL.md"))
        self.assertEqual("local_report", analysis.classify_markdown_path(r"D:\project\drafts\analysis_report.md"))

    def test_aggregate_group_has_rates_and_intervals(self) -> None:
        rows = [
            {"group": "chat", "metrics": analysis.measure_text("我先检查。")},
            {"group": "chat", "metrics": analysis.measure_text("我会继续验证。")},
            {"group": "writing", "metrics": analysis.measure_text("本文分析模型边界。")},
        ]
        result = analysis.aggregate_groups(rows, "group")
        chat_first_person = next(row for row in result if row["group"] == "chat" and row["feature"] == "first_person")

        self.assertEqual(2, chat_first_person["records"])
        self.assertEqual(1.0, chat_first_person["rate"])
        self.assertLessEqual(chat_first_person["ci_low"], chat_first_person["rate"])
        self.assertGreaterEqual(chat_first_person["ci_high"], chat_first_person["rate"])


if __name__ == "__main__":
    unittest.main()
