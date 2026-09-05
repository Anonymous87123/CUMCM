import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_full_style_corpus.py"
SPEC = importlib.util.spec_from_file_location("full_style_corpus", SCRIPT)
corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus)


class FullStyleCorpusTests(unittest.TestCase):
    def test_markdown_extraction_keeps_prose_and_structure(self) -> None:
        source = """---
title: hidden
---
# 标题

这是第一段。它有两句！

```python
secret = 'not prose'
```

- 列表项带有中文说明。
"""
        document = corpus.extract_markdown_document(source)

        self.assertEqual(["标题"], document["headings"])
        self.assertIn("这是第一段", document["prose"])
        self.assertNotIn("secret", document["prose"])
        self.assertEqual(2, len(document["paragraphs"]))
        self.assertGreaterEqual(len(document["sentences"]), 3)

    def test_redaction_and_md_path_extraction(self) -> None:
        text = "已写入 D:\\work\\report.md，联系 a@example.com，key sk-abcdefghijklmnopqrstuvwxyz123456"
        paths = corpus.extract_markdown_paths(text)
        redacted = corpus.redact_sensitive(text)

        self.assertIn(r"D:\work\report.md", paths)
        self.assertIn("[EMAIL]", redacted)
        self.assertIn("[OPENAI_KEY]", redacted)
        self.assertNotIn("a@example.com", redacted)

    def test_jsonl_scan_keeps_assistant_and_md_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "session.jsonl"
            rows = [
                {"type": "session_meta", "payload": {"id": "s1", "originator": "codex"}},
                {"type": "turn_context", "payload": {"model": "gpt-test", "personality": "pragmatic"}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "已生成 D:\\work\\result.md，并完成中文总结。"}]}},
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "用户内容不能成为聊天样本"}]}},
            ]
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

            messages, provenance, audit = corpus.scan_jsonl_file(path)

            self.assertEqual(1, len(messages))
            self.assertEqual("gpt-test", messages[0]["model"])
            self.assertEqual("final_answer", messages[0]["phase"])
            self.assertEqual(1, len(provenance))
            self.assertEqual(r"D:\work\result.md", provenance[0]["mentioned_path"])
            self.assertEqual(0, audit["json_errors"])

    def test_markdown_manifest_tracks_empty_and_duplicate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.md").write_text("# 标题\n\n中文正文。", encoding="utf-8")
            (root / "b.md").write_text("# 标题\n\n中文正文。", encoding="utf-8")
            (root / "empty.md").write_text("", encoding="utf-8")

            rows, paragraphs, sentences = corpus.scan_markdown_tree(root, source_label="d_drive")

            statuses = {row["path"].split("\\")[-1]: row["status"] for row in rows}
            self.assertEqual("empty", statuses["empty.md"])
            self.assertEqual(2, sum(row["status"] == "readable" for row in rows))
            self.assertTrue(any(row["duplicate_of"] for row in rows if row["status"] == "readable"))
            self.assertEqual(2, len(paragraphs))
            self.assertGreaterEqual(len(sentences), 2)

    def test_tex_extraction_preserves_prose_but_excludes_display_math(self) -> None:
        source = r"""\section{研究背景}

本文讨论一个具体问题，并说明适用范围。

\begin{equation}
  x = y + z
\end{equation}

结论不能外推到未验证的样本。
"""
        document = corpus.extract_tex_document(source)

        self.assertEqual(["研究背景"], document["headings"])
        self.assertIn("本文讨论一个具体问题", document["prose"])
        self.assertIn("结论不能外推", document["prose"])
        self.assertNotIn("x = y + z", document["prose"])

    def test_document_path_extraction_supports_tex(self) -> None:
        paths = corpus.extract_document_paths(r"已更新 D:\paper\main.tex 与 D:\paper\notes.md")

        self.assertEqual([r"D:\paper\main.tex", r"D:\paper\notes.md"], paths)


if __name__ == "__main__":
    unittest.main()
