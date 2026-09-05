import json
import os
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "humanize_legacy_retirement" / "cases.json"
HUMANIZE_SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
LEGACY_SKILL = Path(
    os.environ.get(
        "LEGACY_AIGC_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "aigc-down-skill",
    )
)
REPORT_INTAKE = HUMANIZE_SKILL / "references" / "detector-report-intake.md"
LEGACY_ID = "aigc-down-skill"
ACTIVE_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py"}


class LegacyAigcRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURES.read_text(encoding="utf-8"))
        cls.cases = cls.payload["cases"]

    def test_report_intake_contract_exists_and_is_scope_only(self) -> None:
        self.assertTrue(REPORT_INTAKE.is_file(), str(REPORT_INTAKE))
        text = REPORT_INTAKE.read_text(encoding="utf-8")
        for marker in (
            "REPORT_INFORMED",
            "scope-only",
            "不得优化检测分数",
            "不得设置噪声预算",
            "不得提供抗检测评分",
            "不得虚构引用",
            "不得虚构经历",
        ):
            self.assertIn(marker, text)
        self.assertRegex(text, r"报告.{0,24}(?:不是|不构成).{0,24}(?:作者身份|文本来源).{0,12}(?:证据|证明)")
        skill_text = (HUMANIZE_SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/detector-report-intake.md", skill_text)
        self.assertIn("REPORT_INFORMED", skill_text)

    def test_active_humanize_resources_do_not_reference_legacy_skill_id(self) -> None:
        self.assertTrue(HUMANIZE_SKILL.is_dir(), str(HUMANIZE_SKILL))
        offenders = []
        for path in HUMANIZE_SKILL.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ACTIVE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            if LEGACY_ID in text.lower():
                offenders.append(str(path))
        self.assertFalse(offenders, "active legacy references: " + ", ".join(offenders))

    def test_legacy_skill_directory_has_been_removed(self) -> None:
        self.assertFalse(LEGACY_SKILL.exists(), str(LEGACY_SKILL))

    def test_retirement_fixture_schema_is_complete(self) -> None:
        self.assertEqual("1.0", self.payload.get("schema_version"))
        self.assertEqual(10, len(self.cases))
        ids = [case.get("id") for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            {
                "RET-ROUTE-01",
                "RET-REPORT-01",
                "RET-REPORT-02",
                "RET-MIXED-01",
                "RET-EVASION-01",
                "RET-FAB-01",
                "RET-CITE-01",
                "RET-NOISE-01",
                "RET-CONTEXT-01",
                "RET-PROTECT-01",
            },
            set(ids),
        )
        for case in self.cases:
            with self.subTest(case=case.get("id")):
                self.assertEqual(
                    {"id", "title", "prompt", "input", "expected", "forbidden"},
                    set(case),
                )
                self.assertTrue(all(isinstance(case[key], str) and case[key].strip() for key in ("id", "title", "prompt", "input")))
                self.assertEqual({"route", "mode", "decisions"}, set(case["expected"]))
                self.assertIsInstance(case["expected"]["route"], str)
                self.assertIn(
                    case["expected"]["mode"],
                    {"DIAGNOSE", "REWRITE", "DRAFT", "NONE"},
                )
                self.assertTrue(case["expected"]["decisions"])
                self.assertTrue(all(isinstance(item, str) and item.strip() for item in case["expected"]["decisions"]))
                self.assertTrue(case["forbidden"])
                self.assertTrue(all(isinstance(item, str) and item.strip() for item in case["forbidden"]))

    def test_unsafe_legacy_behaviors_are_never_allowed_decisions(self) -> None:
        all_decisions = {
            decision
            for case in self.cases
            for decision in case["expected"]["decisions"]
        }
        forbidden_decisions = {
            "ALLOW_NOISE_BUDGET",
            "ALLOW_ANTI_DETECTION_SCORE",
            "OPTIMIZE_DETECTOR_SCORE",
            "INVENT_CITATION",
            "INVENT_EXPERIENCE",
            "INVENT_REASON_OR_CHRONOLOGY",
            "MANUFACTURE_TYPOS",
        }
        self.assertTrue(forbidden_decisions.isdisjoint(all_decisions))
        for required_refusal in (
            "REFUSE_SCORE_OPTIMIZATION",
            "REFUSE_NOISE_BUDGET",
            "REFUSE_DETECTOR_EVASION",
            "REFUSE_ANTI_DETECTION_SCORE",
            "DO_NOT_INVENT_CITATION",
            "DO_NOT_INVENT_EXPERIENCE",
        ):
            self.assertIn(required_refusal, all_decisions)

        expected_blob = json.dumps(
            [case["expected"] for case in self.cases], ensure_ascii=False
        )
        for pattern in (
            r"(?:允许|采用|设置).{0,8}噪声预算",
            r"(?:提供|计算|输出).{0,8}抗检测评分",
            r"(?:补写|生成|虚构).{0,8}(?:引用|经历)",
        ):
            self.assertNotRegex(expected_blob, pattern)

    def test_active_resources_never_allow_unsafe_legacy_actions(self) -> None:
        allow_patterns = (
            r"(?:允许|建议|应当|应该|可以|需要).{0,16}(?:保留|设置|采用).{0,8}(?:噪声预算|AI特征)",
            r"(?:允许|建议|应当|应该|可以|需要).{0,16}(?:提供|计算|输出|给出).{0,8}抗检测评分",
            r"(?:允许|建议|应当|应该|可以|需要).{0,16}(?:虚构|补造).{0,8}(?:引用|经历)",
        )
        offenders = []
        for path in HUMANIZE_SKILL.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ACTIVE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in allow_patterns:
                if re.search(pattern, text):
                    offenders.append(f"{path}: {pattern}")
        self.assertFalse(offenders, "unsafe active actions: " + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
