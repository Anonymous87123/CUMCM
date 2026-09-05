from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
SCRIPT = SKILL / "scripts" / "extract_detector_report_scope.py"
FIXTURES = ROOT / "tests" / "fixtures" / "detector_report_scope"


def load_extractor():
    spec = importlib.util.spec_from_file_location("extract_detector_report_scope", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load extractor: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


extractor = load_extractor()


class DetectorReportScopeTests(unittest.TestCase):
    def test_extracts_supported_markers_ignores_active_content_and_deduplicates(self) -> None:
        html = (FIXTURES / "report_mixed.html").read_text(encoding="utf-8")
        fragments = extractor.extract_report_fragments(html)

        self.assertEqual(
            [
                "第一段需要改写。",
                "第二段需要改写。",
                "重复片段。",
                "属性值标注。",
                "唯一文本。",
                "链接内标注文本。",
                "ＡＩＧＣ 规范化 映射。",
            ],
            [item["text"] for item in fragments],
        )
        duplicate = next(item for item in fragments if item["text"] == "重复片段。")
        self.assertEqual(2, duplicate["report_occurrences"])
        serialized = json.dumps(fragments, ensure_ascii=False)
        self.assertNotIn("脚本伪标注", serialized)
        self.assertNotIn("样式伪标注", serialized)
        self.assertNotIn("无脚本伪标注", serialized)
        self.assertNotIn("https://", serialized)

    def test_all_unique_normalized_mappings_pass_with_hashes_and_coverage(self) -> None:
        report = FIXTURES / "report_mixed.html"
        source = FIXTURES / "source_unique.md"
        payload = extractor.analyze_report(report, source)

        self.assertEqual("PASS", payload["status"])
        self.assertEqual(0, payload["exit_code"])
        self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), payload["report_sha256"])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), payload["source_sha256"])
        self.assertEqual(7, payload["coverage"]["total_fragments"])
        self.assertEqual(7, payload["coverage"]["uniquely_mapped"])
        self.assertEqual(1.0, payload["coverage"]["ratio"])
        self.assertTrue(all(item["mapping_status"] == "UNIQUE" for item in payload["fragments"]))
        normalized = next(item for item in payload["fragments"] if "ＡＩＧＣ" in item["text"])
        self.assertEqual("AIGC 规范化 映射。", normalized["normalized_text"])
        self.assertGreaterEqual(normalized["source_line"], 1)
        self.assertGreaterEqual(normalized["source_column"], 1)

    def test_missing_and_ambiguous_fragments_require_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.html"
            source = root / "source.md"
            report.write_text(
                '<mark>重复判断。</mark><span class="risk">源文没有。</span>',
                encoding="utf-8",
            )
            source.write_text("重复判断。中间内容。重复判断。", encoding="utf-8")

            payload = extractor.analyze_report(report, source)

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual(0, payload["coverage"]["uniquely_mapped"])
        self.assertEqual(1, payload["coverage"]["ambiguous"])
        self.assertEqual(1, payload["coverage"]["missing"])
        statuses = {item["text"]: item["mapping_status"] for item in payload["fragments"]}
        self.assertEqual("AMBIGUOUS", statuses["重复判断。"])
        self.assertEqual("MISSING", statuses["源文没有。"])

    def test_score_ui_metadata_does_not_pollute_marked_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.html"
            source = root / "source.md"
            sentence = "值得注意的是，现有表述系统梳理了相关问题。"
            report.write_text(
                '<div class="risk-score">综合风险：87%</div>'
                f"<mark>{sentence}</mark>",
                encoding="utf-8",
            )
            source.write_text(sentence, encoding="utf-8")

            payload = extractor.analyze_report(report, source)

        self.assertEqual("PASS", payload["status"])
        self.assertEqual(1, payload["coverage"]["total_fragments"])
        self.assertEqual(sentence, payload["fragments"][0]["text"])

    def test_report_without_source_is_review_not_an_implicit_match(self) -> None:
        payload = extractor.analyze_report(FIXTURES / "report_mixed.html")

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["exit_code"])
        self.assertIsNone(payload["source_sha256"])
        self.assertEqual(7, payload["coverage"]["not_mapped_no_source"])
        self.assertTrue(
            all(item["mapping_status"] == "NOT_MAPPED_NO_SOURCE" for item in payload["fragments"])
        )

    def test_no_flagged_visible_text_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "empty.html"
            report.write_text(
                "<html><body><p>普通报告文本。</p><script><mark>伪标注</mark></script></body></html>",
                encoding="utf-8",
            )
            payload = extractor.analyze_report(report)

        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual("NO_FLAGGED_VISIBLE_TEXT", payload["review_reasons"][0]["code"])
        self.assertEqual([], payload["fragments"])

    def test_cli_emits_json_and_uses_status_exit_code(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(FIXTURES / "report_mixed.html"),
                "--source",
                str(FIXTURES / "source_unique.md"),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(7, len(payload["fragments"]))
        self.assertEqual("<LOCAL_REPORT_NOT_PERSISTED>", payload["report_path"])
        self.assertNotIn(str(FIXTURES.resolve()), completed.stdout)

    def test_persisted_scope_uses_artifact_relative_locators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "inputs" / "report.html"
            source = root / "inputs" / "source.md"
            output = root / "scope.json"
            report.parent.mkdir()
            report.write_text("<mark>标注段。</mark>", encoding="utf-8")
            source.write_text("标注段。", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(report),
                    "--source",
                    str(source),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("inputs/report.html", payload["report_path"])
        self.assertEqual("inputs/source.md", payload["source_path"])
        self.assertEqual("SCOPE_ARTIFACT_PARENT", payload["path_base"])
        self.assertNotIn(str(root), completed.stdout)

    def test_cli_read_failure_is_fail_one_and_does_not_echo_private_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "Alice" / "PrivateProject"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(private / "missing-report.html"),
                    "--source",
                    str(private / "student-name.tex"),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("INPUT_READ_FAILED", payload["review_reasons"][0]["code"])
        self.assertNotIn(str(private), completed.stdout + completed.stderr)

    def test_cli_output_write_failure_is_fail_one_without_path_or_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.html"
            source = root / "source.md"
            blocked_parent = root / "PrivateOutput"
            report.write_text("<mark>标注段。</mark>", encoding="utf-8")
            source.write_text("标注段。", encoding="utf-8")
            blocked_parent.write_text("not a directory", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(report),
                    "--source",
                    str(source),
                    "--output",
                    str(blocked_parent / "scope.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("SCOPE_OUTPUT_WRITE_FAILED", payload["review_reasons"][0]["code"])
        self.assertNotIn(str(root), completed.stdout + completed.stderr)
        self.assertEqual("", completed.stderr)


if __name__ == "__main__":
    unittest.main()
