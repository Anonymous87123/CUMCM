import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_codex_chinese_style.py"
SPEC = importlib.util.spec_from_file_location("style_analyzer", SCRIPT)
analyzer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyzer)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


class StyleAnalyzerTests(unittest.TestCase):
    def test_snapshot_parser_collects_only_assistant_output_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_jsonl(
                root / "session.jsonl",
                [
                    {"type": "session_meta", "payload": {"id": "session-1", "originator": "codex", "source": "vscode", "model_provider": "API"}},
                    {"type": "turn_context", "payload": {"model": "gpt-test", "personality": "pragmatic"}},
                    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "请修复 bug 并补测试"}]}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "commentary", "content": [{"type": "output_text", "text": "我先检查问题。"}]}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "已修复并验证。"}]}},
                    {"type": "response_item", "payload": {"type": "function_call", "role": "assistant", "content": []}},
                    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "这条用户消息不能被采集"}]}},
                ],
            )

            snapshot = analyzer.build_snapshot(root)
            records, audit = analyzer.collect_records(snapshot)

            self.assertEqual(2, len(records))
            self.assertEqual("gpt-test", records[0]["model"])
            self.assertEqual("pragmatic", records[0]["personality"])
            self.assertEqual("commentary", records[0]["phase"])
            self.assertEqual("debugging", records[0]["task_primary"])
            self.assertEqual("testing", records[0]["task_labels"][1])
            self.assertEqual(2, audit["assistant_chinese_messages"])

    def test_redaction_and_prose_view_remove_sensitive_data_and_code(self) -> None:
        raw = "联系 alice@example.com，密钥 sk-abcdefghijklmnopqrstuvwxyz123456。\n```python\nprint('secret')\n```\n我先确认 `README.md` 的结果。"
        redacted = analyzer.redact_sensitive(raw)
        prose = analyzer.prose_view(redacted)

        self.assertNotIn("alice@example.com", redacted)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", redacted)
        self.assertIn("[EMAIL]", redacted)
        self.assertIn("[OPENAI_KEY]", redacted)
        self.assertNotIn("print", prose)
        self.assertIn("README.md", prose)

    def test_snapshot_excludes_records_appended_after_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "session.jsonl"
            rows = [
                {"type": "session_meta", "payload": {"id": "session-3"}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "这是快照前的中文消息。"}]}},
            ]
            write_jsonl(path, rows)
            snapshot = analyzer.build_snapshot(root)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n" + json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "这是快照后的中文消息。"}]}}, ensure_ascii=False))

            records, audit = analyzer.collect_records(snapshot)

            self.assertEqual(1, len(records))
            self.assertTrue(audit["files_changed_since_snapshot"])
            self.assertIn("快照前", records[0]["raw_text"])

    def test_malformed_json_is_audited_without_stopping_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "session.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "session_meta", "payload": {"id": "session-4"}}, ensure_ascii=False),
                        "{not-json}",
                        json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "损坏行之后仍应继续采集中文消息。"}]}}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )

            records, audit = analyzer.collect_records(analyzer.build_snapshot(root))

            self.assertEqual(1, len(records))
            self.assertEqual(1, audit["json_parse_errors"])

    def test_run_analysis_writes_auditable_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "logs"
            root.mkdir()
            output = Path(temp) / "output"
            snapshot_path = Path(temp) / "snapshot.json"
            write_jsonl(
                root / "session.jsonl",
                [
                    {"type": "session_meta", "payload": {"id": "session-2", "originator": "codex", "source": "cli", "model_provider": "API"}},
                    {"type": "turn_context", "payload": {"model": "gpt-test", "personality": "friendly"}},
                    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "请写一份文档说明"}]}},
                    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "结论：我已经完成文档，并检查了现有结构、说明范围和格式一致性。下一步可以直接补充示例，再验证读者能否按步骤复现主要操作。"}]}},
                ],
            )

            analyzer.run_analysis(root, snapshot_path, output, evidence="raw", timezone_name="Asia/Shanghai")

            for name in ["run_metadata.json", "file_manifest.csv", "metrics.json", "phrase_rankings.csv", "group_comparisons.csv", "task_classification_summary.csv", "evidence_raw_redacted.md", "examples.jsonl"]:
                self.assertTrue((output / name).exists(), name)
            self.assertTrue((output / "figures" / "phase_length_distribution.svg").exists())
            evidence = (output / "evidence_raw_redacted.md").read_text(encoding="utf-8")
            self.assertIn("gpt-test", evidence)


if __name__ == "__main__":
    unittest.main()
