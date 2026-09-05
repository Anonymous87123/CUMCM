from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "classify_academic_scenarios.py"
TAXONOMY = Path(__file__).parents[1] / "scripts" / "academic_scenario_taxonomy.json"
SPEC = importlib.util.spec_from_file_location("scenario_classifier", SCRIPT)
assert SPEC and SPEC.loader
scenario = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenario)


class AcademicScenarioClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = scenario.load_taxonomy(TAXONOMY)

    def test_curated_roots_route_to_distinct_scenes(self) -> None:
        examples = {
            r"D:\code LateX\简单导数\chapters\chap6.tex": "course_notes",
            r"D:\LSGO-platform\docs\metric_screening_notes.md": "modeling_engineering",
            r"D:\2026-BYD-arxiv\paper\paper_CN.tex": "research_journal",
        }
        for path, expected in examples.items():
            with self.subTest(path=path):
                self.assertEqual(expected, scenario.classify_path(path, self.taxonomy)["scene"])

    def test_dependencies_are_decided_but_never_style_evidence(self) -> None:
        result = scenario.classify_path(
            r"C:\Users\Lenovo\.codex\skills\some-skill\SKILL.md",
            self.taxonomy,
        )
        self.assertEqual("not_applicable", result["scene"])
        self.assertEqual("excluded_dependency", result["eligibility"])

    def test_manifest_keeps_every_readable_row_and_marks_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.csv"
            fields = [
                "path",
                "status",
                "document_format",
                "han_chars",
                "source_label",
                "sha256",
                "duplicate_of",
            ]
            rows = [
                {
                    "path": r"D:\code LateX\简单导数\chapters\chap6.tex",
                    "status": "readable",
                    "document_format": "tex",
                    "han_chars": "100",
                    "source_label": "d_drive_tex",
                    "sha256": "a",
                    "duplicate_of": "",
                },
                {
                    "path": r"D:\Program Files\tool\README.md",
                    "status": "readable",
                    "document_format": "md",
                    "han_chars": "0",
                    "source_label": "d_drive_markdown",
                    "sha256": "b",
                    "duplicate_of": "",
                },
                {
                    "path": r"D:\ignored\bad.tex",
                    "status": "decode_error",
                    "document_format": "tex",
                    "han_chars": "0",
                    "source_label": "d_drive_tex",
                    "sha256": "c",
                    "duplicate_of": "",
                },
            ]
            with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            classified = scenario.classify_manifest(
                manifest,
                self.taxonomy,
                {scenario.normalize_path(rows[0]["path"])},
            )
            self.assertEqual(2, len(classified))
            self.assertEqual("yes", classified[0]["core_207_candidate"])
            self.assertEqual("primary_style_candidate", classified[0]["evidence_role"])
            self.assertNotEqual("primary_style_candidate", classified[1]["evidence_role"])

            summary = scenario.summarize(classified, self.taxonomy)
            self.assertTrue(summary["invariants"]["all_rows_have_decision"])
            self.assertTrue(summary["invariants"]["non_target_never_primary_style_evidence"])

    def test_taxonomy_is_json_and_has_exact_scene_set(self) -> None:
        raw = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        self.assertEqual(scenario.SCENES, set(raw["scene_labels"]))


if __name__ == "__main__":
    unittest.main()
