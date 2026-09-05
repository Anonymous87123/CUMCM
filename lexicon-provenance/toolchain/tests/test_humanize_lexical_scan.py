import csv
import importlib.util
import io
import json
import os
import subprocess
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
LEXICON = SKILL / "references" / "lexical-signals.json"
SCANNER = SKILL / "scripts" / "scan_humanize_chinese.py"
FIXTURES = Path(__file__).parent / "fixtures" / "humanize_lexical"


def load_scanner():
    spec = importlib.util.spec_from_file_location("scan_humanize_chinese", SCANNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scanner = load_scanner()


class HumanizeLexicalSchemaTests(unittest.TestCase):
    def test_duplicate_lexicon_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = LEXICON.read_text(encoding="utf-8")
            path = Path(temp_dir) / "lexicon.json"
            path.write_text('{"signals":[],' + raw.lstrip()[1:], encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate JSON key: signals"):
                scanner.load_lexicon(path)

    def test_non_finite_lexicon_numbers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = LEXICON.read_text(encoding="utf-8")
            path = Path(temp_dir) / "lexicon.json"
            path.write_text(
                raw.replace('"min_occurrences": 1', '"min_occurrences": Infinity', 1),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "non-finite JSON number: Infinity"):
                scanner.load_lexicon(path)

    def test_schema_is_context_aware_and_actionable(self) -> None:
        data = json.loads(LEXICON.read_text(encoding="utf-8"))
        self.assertEqual("1.2.7", data["schema_version"])
        self.assertGreaterEqual(len(data["signals"]), 28)
        required = {
            "id",
            "variants",
            "regex",
            "scenes",
            "severity",
            "threshold",
            "exclusions",
            "action",
            "rationale",
            "positive_examples",
            "negative_examples",
            "provenance",
        }
        categories = set()
        for signal in data["signals"]:
            self.assertFalse(required - signal.keys(), signal["id"])
            self.assertTrue(
                signal["variants"] or signal["regex"] or signal.get("structural_matcher"),
                signal["id"],
            )
            self.assertIn(signal["action"], {"KEEP", "DELETE", "REWRITE", "REVIEW"})
            self.assertGreaterEqual(signal["threshold"]["min_occurrences"], 1)
            self.assertIn(signal["threshold"]["window"], {"document", "paragraph", "sentence", "line"})
            self.assertTrue(signal["positive_examples"], signal["id"])
            self.assertTrue(signal["negative_examples"], signal["id"])
            self.assertTrue(signal["provenance"], signal["id"])
            categories.add(signal["category"])

        expected_categories = {
            "transition-density",
            "outline-shell",
            "management-voice",
            "marketing-innovation-voice",
            "coaching-voice",
            "meta-writing",
            "table-role-ambiguity",
            "modal-hedge-density",
            "repair-template-repetition",
            "theory-opening-repetition",
            "case-closing-repetition",
            "passive-analysis-shell",
            "problem-announcement-shell",
            "vague-attribution-source",
            "copula-avoidance-density",
            "academic-packaging-density",
            "three-part-enumeration-shell",
            "dash-density",
            "bold-emphasis-density",
            "formula-caption-run",
        }
        self.assertFalse(expected_categories - categories)


class HumanizeLexicalScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lexicon = scanner.load_lexicon(LEXICON)

    def scan_fixture(self, name: str, **kwargs):
        path = FIXTURES / name
        return scanner.scan_file(path, lexicon=self.lexicon, **kwargs)

    def test_positive_fixture_exposes_concrete_candidates(self) -> None:
        findings = self.scan_fixture("positive.md", scene="ALL")
        ids = {item["signal_id"] for item in findings}
        expected = {
            "LEX-TRANS-01",
            "LEX-EMPH-01",
            "LEX-OUTLINE-01",
            "LEX-MGMT-01",
            "LEX-MARKET-01",
            "LEX-COACH-01",
            "LEX-META-01",
            "LEX-HEDGE-01",
            "LEX-RESULT-01",
            "LEX-FOUNDATION-01",
            "LEX-FUTURE-01",
            "LEX-REPAIR-01",
        }
        self.assertFalse(expected - ids)

    def test_draft_editorial_requirement_left_in_prose_is_located(self) -> None:
        findings = scanner.scan_text(
            "因此，总量硬锚点校准与局地一致性检验需要分开报告。",
            file="draft.md",
            scene="RESEARCH",
            lexicon=self.lexicon,
        )

        self.assertIn("LEX-META-01", {item["signal_id"] for item in findings})

    def test_course_copular_comma_break_is_narrowly_located(self) -> None:
        unsafe = scanner.scan_text(
            "第一种误判是，认为只要记住平均位置就够了。",
            file="course.tex",
            scene="COURSE",
            lexicon=self.lexicon,
        )
        safe = scanner.scan_text(
            "第一种误判是：觉得只要记住平均位置就够了。"
            "最典型的误判是把知识时效问题诊断成模型太弱。"
            "问题是，认为这一结论成立的人没有说明样本范围。",
            file="course.tex",
            scene="COURSE",
            lexicon=self.lexicon,
        )
        other_scene = scanner.scan_text(
            "第一种误判是，认为只要记住平均位置就够了。",
            file="research.tex",
            scene="RESEARCH",
            lexicon=self.lexicon,
        )

        hits = [
            item
            for item in unsafe
            if item["signal_id"] == "LEX-COURSE-COPULAR-COMMA-01"
        ]
        self.assertEqual(1, len(hits))
        self.assertEqual("high", hits[0]["severity"])
        self.assertEqual("REWRITE", hits[0]["action"])
        self.assertNotIn(
            "LEX-COURSE-COPULAR-COMMA-01",
            {item["signal_id"] for item in safe},
        )
        self.assertNotIn(
            "LEX-COURSE-COPULAR-COMMA-01",
            {item["signal_id"] for item in other_scene},
        )

    def test_v30_combined_editorial_boundary_and_next_section_forecast_is_located(self) -> None:
        findings = scanner.scan_text(
            "该段只交代实验设置，不把它写成研究贡献，也不预告下一节。",
            file="draft.md",
            scene="RESEARCH",
            lexicon=self.lexicon,
        )
        meta = [item for item in findings if item["signal_id"] == "LEX-META-01"]
        self.assertTrue(meta)
        self.assertTrue(any("不把" in item["matched"] or "不预告" in item["matched"] for item in meta))

    def test_v19_abstract_closed_loop_and_path_shell_are_concrete_candidates(self) -> None:
        research = scanner.scan_text(
            "本问按参数设定、校准和反事实对照的实证闭环收紧。",
            file="research.md",
            scene="RESEARCH",
            lexicon=self.lexicon,
        )
        modeling = scanner.scan_text(
            "问题二的证据关系由禁渔和食源恢复出发，经通道与污染修正，最终落到种群变化。",
            file="modeling.md",
            scene="MODELING",
            lexicon=self.lexicon,
        )

        for findings in (research, modeling):
            hit = [item for item in findings if item["signal_id"] == "LEX-MGMT-01"]
            self.assertTrue(hit)
            self.assertTrue(all(item["severity"] == "high" for item in hit))
            self.assertTrue(all(item["action"] == "REWRITE" for item in hit))

    def test_table_role_is_reviewed_separately_from_editorial_directives(self) -> None:
        findings = scanner.scan_text(
            "表格的作用在于让读者看出每个参数来自哪条事实链。",
            file="modeling.md",
            scene="MODELING",
            lexicon=self.lexicon,
        )
        ids = {item["signal_id"] for item in findings}

        self.assertIn("LEX-TABLE-ROLE-01", ids)
        self.assertNotIn("LEX-META-01", ids)
        table_hit = next(item for item in findings if item["signal_id"] == "LEX-TABLE-ROLE-01")
        self.assertEqual("REVIEW", table_hit["action"])
        self.assertEqual("medium", table_hit["severity"])

    def test_markdown_percentage_does_not_hide_the_rest_of_the_line_as_tex_comment(self) -> None:
        findings = scanner.scan_text(
            "相对误差为 16.47%。因此，两类结果需要分开报告。",
            file="draft.md",
            scene="RESEARCH",
            lexicon=self.lexicon,
        )

        meta = [item for item in findings if item["signal_id"] == "LEX-META-01"]
        self.assertEqual(1, len(meta))
        self.assertFalse(meta[0]["protected"])
        for finding in findings:
            self.assertGreaterEqual(finding["line"], 1)
            self.assertGreaterEqual(finding["column"], 1)
            self.assertTrue(finding["matched"])
            self.assertTrue(finding["context"])
            self.assertGreaterEqual(finding["count"], 1)
            self.assertIn(finding["action"], {"DELETE", "REWRITE", "REVIEW"})
            self.assertTrue(finding["candidate"])

    def test_technical_terms_and_real_proof_chain_are_not_candidates(self) -> None:
        findings = self.scan_fixture("negative.tex", scene="ALL")
        self.assertEqual([], findings)

    def test_retired_rules_are_context_candidates_not_banned_words(self) -> None:
        findings = self.scan_fixture("legacy_candidates.md", scene="ALL")
        ids = {item["signal_id"] for item in findings}
        expected = {
            "LEX-THEORY-OPEN-01",
            "LEX-CASE-CLOSE-01",
            "LEX-PASSIVE-ANALYSIS-01",
            "LEX-PROBLEM-SHELL-01",
            "LEX-VAGUE-ATTRIBUTION-01",
            "LEX-COPULA-AVOID-01",
            "LEX-ACADEMIC-PACKAGE-01",
            "LEX-ENUM-01",
            "LEX-PUNCT-DASH-01",
            "LEX-FORMAT-BOLD-01",
        }
        self.assertFalse(expected - ids)
        self.assertTrue(all(item["action"] == "REVIEW" for item in findings if item["signal_id"] in expected))

    def test_single_normal_uses_and_functional_exclusions_are_protected(self) -> None:
        findings = self.scan_fixture("legacy_safe.md", scene="ALL")
        self.assertEqual([], findings)

        audit = self.scan_fixture("legacy_safe.md", scene="ALL", include_excluded=True)
        excluded_ids = {item["signal_id"] for item in audit if item["excluded"]}
        self.assertIn("LEX-VAGUE-ATTRIBUTION-01", excluded_ids)
        self.assertIn("LEX-ENUM-01", excluded_ids)
        self.assertTrue(all(item["action"] == "KEEP" for item in audit))

    def test_retired_closure_and_packaging_variants_are_located(self) -> None:
        text = (
            "总体而言，需要说明的是，该领域未来可期、前景广阔、意义深远，"
            "可为相关研究提供新思路并开辟新方向。"
            "本文系统梳理材料并综合运用多种方法。"
        )
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="ALL")
        ids = {item["signal_id"] for item in findings}
        self.assertIn("LEX-CONCLUDE-01", ids)
        self.assertIn("LEX-EMPH-01", ids)
        self.assertIn("LEX-MARKET-01", ids)
        self.assertIn("LEX-ACADEMIC-PACKAGE-01", ids)

    def test_proof_exclusions_are_visible_on_request(self) -> None:
        findings = self.scan_fixture("negative.tex", scene="ALL", include_excluded=True)
        proof_hits = [item for item in findings if item["signal_id"] == "LEX-TRANS-01"]
        self.assertEqual(3, len(proof_hits))
        self.assertTrue(all(item["action"] == "KEEP" for item in proof_hits))
        self.assertTrue(all(item["excluded"] for item in proof_hits))
        self.assertTrue(all("因果链" in item["exclusion"] for item in proof_hits))

    def test_code_math_comments_and_quotes_are_protected(self) -> None:
        findings = self.scan_fixture("negative.tex", scene="ALL", include_protected=True)
        protected = [item for item in findings if item["protected"]]
        protections = " ".join(item["protection"] for item in protected)
        self.assertIn("chinese-double-quote", protections)
        self.assertIn("inline-code", protections)
        self.assertIn("latex-comment", protections)
        self.assertTrue(
            "latex-verbatim-or-math-environment" in protections or "display-math" in protections
        )
        self.assertIn("markdown-fence", protections)
        self.assertTrue(all(item["action"] == "KEEP" for item in protected))
        self.assertTrue(all(not item["candidate"] for item in protected))

    def test_tex_exam_statements_and_tex_quotes_are_protected(self) -> None:
        text = (
            "\\begin{exercise}\n必须牢记，并形成完整闭环。\n\\end{exercise}\n"
            "\\begin{theorem}\n综上所述，命题成立。\n\\end{theorem}\n"
            "作者记录道：``必须牢记这一条件。''\n"
            "作者又写道：\\enquote{必须牢记 \\textbf{边界条件}。}\n"
        )
        self.assertEqual([], scanner.scan_text(text, lexicon=self.lexicon, scene="AUTO"))
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            include_protected=True,
        )
        reasons = " ".join(item["protection"] for item in findings)
        self.assertIn("latex-exam-or-formal-statement-environment", reasons)
        self.assertIn("latex-quote", reasons)
        self.assertTrue(all(item["action"] == "KEEP" for item in findings))

    def test_multiline_chinese_quote_is_one_protected_span(self) -> None:
        text = "作者原话是：“第一行必须保留。\n第二行也必须保留。”\n正文可以修改。"
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "markdown"))
        quoted = [text[start:end] for start, end, reason in spans if "quote" in reason]
        self.assertEqual(["“第一行必须保留。\n第二行也必须保留。”"], quoted)

    def test_markdown_structure_spans_cover_non_prose_payloads_only(self) -> None:
        text = (
            "---\r\ntitle: 完全够用\r\n...\r\n"
            "## 先盯住变量\n"
            "[正文](数值明明在变)\n"
            "[ref]: 两条关系接得上\n"
            '<span data-note="必须牢记">可编辑正文</span>\n'
            "<!-- 形成完整闭环 -->\n"
        )
        spans = scanner._merge_spans(scanner._markdown_structure_spans(text))
        protected = [text[start:end] for start, end, _reason in spans]

        self.assertTrue(any("title: 完全够用" in item for item in protected))
        self.assertIn("## 先盯住变量", protected)
        self.assertIn("数值明明在变", protected)
        self.assertIn("两条关系接得上", protected)
        self.assertIn('<span data-note="必须牢记">', protected)
        self.assertIn("</span>", protected)
        self.assertIn("<!-- 形成完整闭环 -->", protected)
        self.assertTrue(all("可编辑正文" not in item for item in protected))

    def test_tex_inline_verbatim_commands_are_fully_protected(self) -> None:
        text = (
            r"正文 \verb|token_甲=形成完整闭环| 与 "
            r"\Verb+token_丁=3+ 与 "
            r'\lstinline!print("乙项")! 与 '
            r"\lstinline[language=Python]!token_丙=2! 均为代码。"
        )
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [
            text[start:end]
            for start, end, reason in spans
            if "latex-inline-verbatim" in reason
        ]

        self.assertEqual(
            [
                r"\verb|token_甲=形成完整闭环|",
                r"\Verb+token_丁=3+",
                r'\lstinline!print("乙项")!',
                r"\lstinline[language=Python]!token_丙=2!",
            ],
            protected,
        )
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )
        self.assertEqual([], findings)

    def test_declared_short_verb_and_custom_verb_like_commands_are_protected(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "|token_甲=形成完整闭环|\n"
            "\\UndefineShortVerb{\\|}\n"
            "正文含 \\CustomVerb!token_乙=必须牢记!，其余可编辑。"
        )
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [text[start:end] for start, end, _reason in spans]

        self.assertIn("|token_甲=形成完整闭环|", protected)
        self.assertIn(r"\CustomVerb!token_乙=必须牢记!", protected)
        self.assertEqual(
            [],
            scanner.scan_text(
                text,
                lexicon=self.lexicon,
                scene="AUTO",
                document_format="tex",
            ),
        )

    def test_short_verb_aliases_and_recustom_command_follow_the_same_contract(self) -> None:
        text = (
            "\\MakeShortVerb{\\|}\n"
            "|token_甲=形成完整闭环|\n"
            "\\DeleteShortVerb{\\|}\n"
            "正文 |形成完整闭环|。\n"
            "\\RecustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "\\InlineCode!token_乙=必须牢记!"
        )
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [text[start:end] for start, end, _reason in spans]
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertIn("|token_甲=形成完整闭环|", protected)
        self.assertIn(r"\InlineCode!token_乙=必须牢记!", protected)
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_short_and_custom_verbatim_declarations_are_group_scoped(self) -> None:
        text = (
            "{\\DefineShortVerb{\\|}|inside|}\n"
            "正文 |形成完整闭环|。\n"
            "{\\CustomVerbatimCommand{\\InlineCode}{Verb}{}"
            "\\InlineCode!inside!}\n"
            "正文 \\InlineCode!必须牢记!。"
        )

        spans, problems = scanner._tex_code_like_spans(text)
        protected = [text[start:end] for start, end, _reason in spans]
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertEqual([], problems)
        self.assertIn("|inside|", protected)
        self.assertIn(r"\InlineCode!inside!", protected)
        self.assertNotIn("|形成完整闭环|", protected)
        self.assertNotIn(r"\InlineCode!必须牢记!", protected)
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})
        self.assertIn("LEX-COACH-01", {item["signal_id"] for item in findings})

    def test_short_verbatim_payload_cannot_execute_a_fake_undeclaration(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "|literal \\DeleteShortVerb{\\|} payload|\n"
            "|形成完整闭环|"
        )

        spans, problems = scanner._tex_code_like_spans(text)
        protected = [text[start:end] for start, end, _reason in spans]

        self.assertEqual([], problems)
        self.assertIn(r"|literal \DeleteShortVerb{\|} payload|", protected)
        self.assertIn("|形成完整闭环|", protected)

    def test_short_verb_scope_distinguishes_local_and_explicit_global_aliases(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "{\\UndefineShortVerb{\\|}}\n"
            "|局部撤销后仍受保护|\n"
            "{\\MakeShortVerb{\\!}}\n"
            "!全局声明后仍受保护!\n"
            "{\\DeleteShortVerb{\\!}}\n"
            "正文 !形成完整闭环!。"
        )

        spans, problems = scanner._tex_code_like_spans(text)
        protected = [text[start:end] for start, end, _reason in spans]
        findings = scanner.scan_text(
            text, lexicon=self.lexicon, scene="AUTO", document_format="tex"
        )

        self.assertEqual([], problems)
        self.assertIn("|局部撤销后仍受保护|", protected)
        self.assertIn("!全局声明后仍受保护!", protected)
        self.assertNotIn("!形成完整闭环!", protected)
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_declared_custom_verbatim_command_with_nonverb_name_is_protected(self) -> None:
        text = (
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{formatcom=\\small}\n"
            "正文含 \\InlineCode|形成完整闭环|，其余可编辑。"
        )

        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [text[start:end] for start, end, _reason in spans]

        self.assertIn(r"\InlineCode|形成完整闭环|", protected)
        self.assertEqual(
            [],
            scanner.scan_text(
                text,
                lexicon=self.lexicon,
                scene="AUTO",
                document_format="tex",
            ),
        )

    def test_verbatim_payload_is_not_recursively_parsed_as_another_command(self) -> None:
        text = (
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "正文 \\InlineCode|literal \\OtherVerb!unclosed|。"
        )

        spans, problems = scanner._tex_code_like_spans(text)
        payloads = [text[start:end] for start, end, _reason in spans]

        self.assertEqual([], problems)
        self.assertIn(r"\InlineCode|literal \OtherVerb!unclosed|", payloads)
        self.assertFalse(any(item.startswith(r"\OtherVerb") for item in payloads))

    def test_inline_verbatim_payload_cannot_create_a_fake_code_environment(self) -> None:
        text = r"正文 \verb|\begin{verbatim}|，随后形成完整闭环。"

        spans, problems = scanner._tex_code_like_spans(text)
        payloads = [text[start:end] for start, end, _reason in spans]
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertEqual([], problems)
        self.assertEqual([r"\verb|\begin{verbatim}|"], payloads)
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_braced_nonverbatim_macro_ending_in_verb_is_not_hidden(self) -> None:
        text = r"正文 \Adverb{形成完整闭环}。"

        spans, problems = scanner._tex_code_like_spans(text)
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertEqual([], problems)
        self.assertEqual([], spans)
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_commented_short_verb_declaration_does_not_activate_delimiter(self) -> None:
        text = "% \\DefineShortVerb{\\|}\n正文 |形成完整闭环|。"

        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})
        self.assertEqual([], scanner._tex_protection_problems(text, "tex"))

    def test_short_verb_is_line_bounded_and_scanning_resumes_after_crlf(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\r\n"
            "|第一行必须牢记\r\n"
            "下一行 |形成完整闭环|。\r\n"
            "\\UndefineShortVerb{\\|}\r\n"
        )
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [text[start:end] for start, end, _reason in spans]
        problems = scanner._tex_protection_problems(text, "tex")

        self.assertIn("|第一行必须牢记\r", protected)
        self.assertIn("|形成完整闭环|", protected)
        self.assertTrue(any(item.startswith("unclosed_short_verbatim@") for item in problems))
        self.assertFalse(any("第一行必须牢记\r\n下一行" in item for item in protected))

    def test_short_verb_undeclaration_ends_protection_scope(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "|代码载荷|\n"
            "\\UndefineShortVerb{\\|}\n"
            "正文 |形成完整闭环|。"
        )

        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_percent_inside_inline_verbatim_does_not_comment_out_later_prose(self) -> None:
        text = r"正文 \verb|token%必须牢记|，随后形成完整闭环。"
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [text[start:end] for start, end, _reason in spans]
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertIn(r"\verb|token%必须牢记|", protected)
        self.assertFalse(any("随后形成完整闭环" in item for item in protected))
        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})

    def test_code_environment_ignores_commented_end_marker(self) -> None:
        text = (
            "\\begin{Verbatim}\n"
            "% \\end{Verbatim}\n"
            "token_甲=形成完整闭环\n"
            "\\end{Verbatim}\n"
            "正文形成完整闭环。"
        )
        spans = scanner._tex_code_like_spans(text)[0]
        payloads = [text[start:end] for start, end, _reason in spans]

        self.assertEqual(1, len(payloads))
        self.assertIn("token_甲=形成完整闭环", payloads[0])
        self.assertTrue(payloads[0].endswith(r"\end{Verbatim}"))

    def test_commented_code_begin_does_not_protect_following_prose(self) -> None:
        text = "% \\begin{minted}{python}\n正文形成完整闭环。\n\\end{minted}"

        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )

        self.assertIn("LEX-MGMT-01", {item["signal_id"] for item in findings})
        self.assertEqual([], scanner._tex_protection_problems(text, "tex"))

    def test_commented_only_code_end_leaves_environment_unclosed(self) -> None:
        text = (
            "\\begin{minted}{python}\n"
            "token_甲=1\n"
            "% \\end{minted}\n"
            "后文。"
        )

        spans, problems = scanner._tex_code_like_spans(text)

        self.assertTrue(any(reason == "latex-unclosed-code-environment" for _, _, reason in spans))
        self.assertTrue(any(item.startswith("unclosed_code_environment:minted@") for item in problems))

    def test_code_environment_closer_is_case_sensitive_and_must_start_its_line(self) -> None:
        cases = {
            "case-mismatch": (
                "\\begin{verbatim}\n\\end{Verbatim}\n值得注意的是",
                "unclosed_code_environment:verbatim@",
            ),
            "inline-fake-closer": (
                "\\begin{verbatim}\nx\\end{verbatim}值得注意的是\n\\end{verbatim}",
                "",
            ),
        }
        for label, (text, expected_problem) in cases.items():
            with self.subTest(label=label):
                spans, problems = scanner._tex_code_like_spans(text)
                protected = [text[start:end] for start, end, _reason in spans]

                if expected_problem:
                    self.assertTrue(any(item.startswith(expected_problem) for item in problems))
                else:
                    self.assertEqual([], problems)
                self.assertEqual(1, len(protected))
                self.assertIn("值得注意的是", protected[0])

    def test_commented_math_closers_do_not_expose_protected_text(self) -> None:
        cases = (
            "$x % $\n值得注意的是\n$",
            "\\begin{equation}\n% \\end{equation}\n值得注意的是\n\\end{equation}",
        )
        for text in cases:
            with self.subTest(text=text):
                spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
                protected = [text[start:end] for start, end, _reason in spans]
                findings = scanner.scan_text(
                    text, lexicon=self.lexicon, scene="AUTO", document_format="tex"
                )

                self.assertTrue(any("值得注意的是" in item for item in protected))
                self.assertNotIn("LEX-EMPTY-01", {item["signal_id"] for item in findings})

    def test_extended_verbatim_environment_family_is_protected(self) -> None:
        for environment in (
            "BVerbatim",
            "BVerbatim*",
            "LVerbatim",
            "LVerbatim*",
            "alltt",
        ):
            with self.subTest(environment=environment):
                text = (
                    f"\\begin{{{environment}}}[commandchars=\\\\\\{{\\}}]\n"
                    "形成完整闭环\n"
                    f"\\end{{{environment}}}\n"
                    "正文形成完整闭环。"
                )
                spans, problems = scanner._tex_code_like_spans(text)
                protected = [text[start:end] for start, end, _reason in spans]
                findings = scanner.scan_text(
                    text,
                    lexicon=self.lexicon,
                    scene="AUTO",
                    document_format="tex",
                )

                self.assertEqual([], problems)
                self.assertEqual(1, len(protected))
                self.assertTrue(protected[0].startswith(f"\\begin{{{environment}}}"))
                self.assertEqual(1, sum(item["signal_id"] == "LEX-MGMT-01" for item in findings))

    def test_nonrendering_environment_family_is_protected_without_hiding_later_prose(self) -> None:
        for environment in ("comment", "filecontents", "filecontents*"):
            with self.subTest(environment=environment):
                begin = (
                    f"\\begin{{{environment}}}{{hidden.tex}}"
                    if environment.startswith("filecontents")
                    else f"\\begin{{{environment}}}"
                )
                text = (
                    f"{begin}\n"
                    "形成完整闭环\n"
                    f"\\end{{{environment}}}\n"
                    "正文形成完整闭环。"
                )
                spans, problems = scanner._tex_code_like_spans(text)
                protected = [
                    (text[start:end], reason) for start, end, reason in spans
                ]
                findings = scanner.scan_text(
                    text,
                    lexicon=self.lexicon,
                    scene="AUTO",
                    document_format="tex",
                )

                self.assertEqual([], problems)
                self.assertEqual(1, len(protected))
                self.assertEqual("latex-nonrendering-environment", protected[0][1])
                self.assertTrue(protected[0][0].startswith(begin))
                self.assertEqual(
                    1,
                    sum(item["signal_id"] == "LEX-MGMT-01" for item in findings),
                )

    def test_explicit_document_format_rejects_unknown_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "document_format"):
            scanner.scan_text(
                "正文。",
                lexicon=self.lexicon,
                document_format="latex",
            )

    def test_unclosed_tex_code_and_math_are_fail_closed_protection_spans(self) -> None:
        cases = {
            "verb": ("正文 \\verb|token_甲=必须牢记\n后文", "unclosed_inline_verbatim"),
            "declared-verb": (
                "\\CustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
                "正文 \\InlineCode|token_戊=必须牢记\n后文",
                "unclosed_declared_inline_verbatim",
            ),
            "environment": (
                "正文 \\begin{minted}{python}\ntoken_乙=形成完整闭环\n后文",
                "unclosed_code_environment",
            ),
            "nonrendering-environment": (
                "\\begin{comment}\ntoken_壬=形成完整闭环\n后文",
                "unclosed_nonrendering_environment:comment@",
            ),
            "dollar": ("正文 $token_丙=必须牢记\n后文", "unclosed_math:$"),
            "double-dollar": (
                "正文 $$token_己=必须牢记\n后文",
                "unclosed_math:$$",
            ),
            "paren": ("正文 \\(token_丁=形成完整闭环\n后文", r"unclosed_math:\("),
            "bracket": (
                "正文 \\[token_庚=形成完整闭环\n后文",
                r"unclosed_math:\[",
            ),
            "math-environment": (
                "正文 \\begin{equation}\ntoken_辛=形成完整闭环\n后文",
                "unclosed_math_environment:equation",
            ),
        }
        for label, (text, problem_prefix) in cases.items():
            with self.subTest(label=label):
                spans = scanner._merge_spans(
                    scanner._raw_protected_spans(text, "tex")
                )
                self.assertTrue(any("unclosed" in reason for _, _, reason in spans))
                self.assertTrue(
                    any(
                        item.startswith(problem_prefix)
                        for item in scanner._tex_protection_problems(text, "tex")
                    )
                )
                self.assertEqual(
                    [],
                    scanner.scan_text(
                        text,
                        lexicon=self.lexicon,
                        scene="AUTO",
                        document_format="tex",
                    ),
                )

    def test_fullwidth_dollar_is_not_silently_reclassified_as_tex_math(self) -> None:
        text = "正文使用全角符号＄形成完整闭环＄，该符号不是 TeX 数学定界符。"
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))

        self.assertFalse(any("math" in reason for _, _, reason in spans))
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            document_format="tex",
        )
        self.assertTrue(any(item["signal_id"] == "LEX-MGMT-01" for item in findings))

    def test_tex_inline_math_can_cross_lines_and_respects_even_backslashes(self) -> None:
        text = "跨行公式 $F=ma\n且仍在公式内$，以及换行符号 \\\\$G=mb$ 均应保护。"
        spans = scanner._merge_spans(scanner._raw_protected_spans(text, "tex"))
        protected = [
            text[start:end]
            for start, end, reason in spans
            if "inline-math" in reason
        ]

        self.assertIn("$F=ma\n且仍在公式内$", protected)
        self.assertTrue(any(item.endswith("$G=mb$") for item in protected))

    def test_commonmark_longer_closing_fence_is_protected(self) -> None:
        text = "```text\n必须牢记并形成完整闭环。\n````\n"
        self.assertEqual([], scanner.scan_text(text, lexicon=self.lexicon, scene="AUTO"))
        protected = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            include_protected=True,
        )
        self.assertTrue(protected)
        self.assertTrue(all(item["protection"] == "markdown-fence" for item in protected))

    def test_sentence_exclusion_only_applies_when_it_overlaps_the_finding(self) -> None:
        text = "闭环控制用于调节，该报告形成完整闭环。"
        findings = scanner.scan_text(
            text,
            lexicon=self.lexicon,
            scene="AUTO",
            include_excluded=True,
        )
        shell = [
            item
            for item in findings
            if item["signal_id"] == "LEX-MGMT-01" and item["matched"] == "形成完整闭环"
        ]
        self.assertEqual(1, len(shell))
        self.assertTrue(shell[0]["candidate"])
        self.assertFalse(shell[0]["excluded"])

    def test_repair_templates_trigger_only_when_repeated(self) -> None:
        single = "这里只比较峰值，其余情形沿用前式。"
        repeated = "这里只比较峰值。\n\n这里只看误差，其余情形沿用前式。"
        single_findings = scanner.scan_text(single, lexicon=self.lexicon)
        repeated_findings = scanner.scan_text(repeated, lexicon=self.lexicon)
        self.assertFalse([item for item in single_findings if item["signal_id"] == "LEX-REPAIR-01"])
        repair = [item for item in repeated_findings if item["signal_id"] == "LEX-REPAIR-01"]
        self.assertGreaterEqual(len(repair), 2)
        self.assertTrue(all(item["count"] >= 2 for item in repair))

    def test_boundaries_do_not_split_unrelated_words(self) -> None:
        text = (
            "先验分布用于预测，再生水用于冲洗。显示屏位于闭环控制器旁，边界条件保持不变。"
            "柔软链条从小孔下落，三块碎片同时落地，落地点分别为 A、B、C。"
        )
        findings = scanner.scan_text(text, lexicon=self.lexicon, include_excluded=True)
        candidates = [item for item in findings if item["candidate"]]
        self.assertEqual([], candidates)

    def test_scene_filter(self) -> None:
        text = "这张救命表必须牢记，可以秒杀同类题。"
        course = scanner.scan_text(text, lexicon=self.lexicon, scene="COURSE")
        research = scanner.scan_text(text, lexicon=self.lexicon, scene="RESEARCH")
        general = scanner.scan_text(text, lexicon=self.lexicon, scene="GENERAL")
        auto = scanner.scan_text(text, lexicon=self.lexicon, scene="AUTO")
        self.assertTrue([item for item in course if item["signal_id"] == "LEX-COACH-01"])
        self.assertFalse([item for item in research if item["signal_id"] == "LEX-COACH-01"])
        self.assertFalse([item for item in general if item["signal_id"] == "LEX-COACH-01"])
        self.assertTrue([item for item in auto if item["signal_id"] == "LEX-COACH-01"])

    def test_course_consecutive_short_formula_captions_are_advisory_candidates(self) -> None:
        text = (
            "水平方向合力为\n"
            " \\(F_x=F-\\mu N.\\)\n"
            "因此\n"
            " \\(a=F_x/m.\\)\n"
            "令 \\(a\\) 取极值：\n"
            " \\(a'=0.\\)\n"
            "于是\n"
            " \\(\\tan\\theta=\\mu.\\)\n"
        )
        findings = scanner.scan_text(
            text,
            file="course.tex",
            lexicon=self.lexicon,
            scene="COURSE",
        )
        captions = [
            item
            for item in findings
            if item["signal_id"] == "LEX-COURSE-FORMULA-CAPTION-01"
        ]

        self.assertEqual(
            ["水平方向合力为", "因此", "令 \\(a\\) 取极值：", "于是"],
            [item["matched"] for item in captions],
        )
        self.assertTrue(all(item["candidate"] for item in captions))
        self.assertTrue(all(item["action"] == "REVIEW" for item in captions))
        self.assertTrue(all(item["severity"] == "medium" for item in captions))

    def test_course_formula_caption_signal_requires_a_run(self) -> None:
        text = (
            "由受力关系可得：\n \\(F_x=F-\\mu N.\\)\n"
            "整理得：\n \\(a=F_x/m.\\)\n"
            "接着讨论边界条件。\n"
        )
        findings = scanner.scan_text(
            text,
            file="course.tex",
            lexicon=self.lexicon,
            scene="COURSE",
        )

        self.assertFalse(
            [
                item
                for item in findings
                if item["signal_id"] == "LEX-COURSE-FORMULA-CAPTION-01"
            ]
        )

    def test_course_formula_caption_requires_formula_only_physical_lines(self) -> None:
        text = (
            "水平方向\n"
            "\\(x=1\\) 解释 \\(y=2\\)\n"
            "竖直方向\n"
            "$$u=3$$ trailing\n"
            "回到原式\n"
            "\\[p=5\\] trailing\n"
        )
        findings = scanner.scan_text(
            text,
            file="course.tex",
            lexicon=self.lexicon,
            scene="COURSE",
        )

        self.assertFalse(
            [
                item
                for item in findings
                if item["signal_id"] == "LEX-COURSE-FORMULA-CAPTION-01"
            ]
        )

    def test_course_formula_caption_supports_declared_formula_forms(self) -> None:
        formula_blocks = (
            "$x=1$",
            "$$x=1$$",
            "\\[x=1\\]",
            "\\[\nx=1\n\\]",
            "\\begin{equation}\nx=1\n\\end{equation}",
        )
        for formula in formula_blocks:
            with self.subTest(formula=formula):
                text = "".join(
                    f"第{label}步\n{formula}\n"
                    for label in ("一", "二", "三")
                )
                findings = scanner.scan_text(
                    text,
                    file="course.tex",
                    lexicon=self.lexicon,
                    scene="COURSE",
                )
                captions = [
                    item
                    for item in findings
                    if item["signal_id"] == "LEX-COURSE-FORMULA-CAPTION-01"
                ]
                self.assertEqual(3, len(captions))
                self.assertTrue(all(item["action"] == "REVIEW" for item in captions))
                self.assertTrue(all(item["severity"] == "medium" for item in captions))

    def test_course_formula_caption_signal_excludes_formal_labels_and_derivation(self) -> None:
        texts = (
            (
                "定义：\n \\(f(x)=x^2.\\)\n"
                "命题：\n \\(f(x)\\ge 0.\\)\n"
                "定理：\n \\(f'(x)=2x.\\)\n"
            ),
            "由牛顿第二定律可得：\n\\[\nF=ma\n\\]\n\n整理得：\n\\[\na=F/m\n\\]\n",
            (
                "\\begin{definition}\n"
                "能量关系：\n\\[\nE=mc^2\n\\]\n"
                "动量关系：\n\\[\np=mv\n\\]\n"
                "速度关系：\n\\[\nv=p/m\n\\]\n"
                "\\end{definition}\n"
            ),
        )
        for text in texts:
            with self.subTest(text=text[:16]):
                findings = scanner.scan_text(
                    text,
                    file="course.tex",
                    lexicon=self.lexicon,
                    scene="COURSE",
                )
                self.assertFalse(
                    [
                        item
                        for item in findings
                        if item["signal_id"] == "LEX-COURSE-FORMULA-CAPTION-01"
                    ]
                )

    def test_high_risk_bridge_and_long_closure_variants_are_located(self) -> None:
        text = (
            "该模型形成了从数据到决策的完整闭环，为工程应用提供有力支撑。"
            "本题也为后续研究极值问题打下了基础，这条判断链也是后续讨论的基础，必须记住。"
            "该结论深入揭示该机制，后续可将其拓展至更多应用场景。"
            "现有结果为后续检验界面重排的作用提供了线索，也是后续研究的出发点。"
        )
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="AUTO")
        ids = {item["signal_id"] for item in findings}
        self.assertIn("LEX-MGMT-01", ids)
        self.assertIn("LEX-MARKET-01", ids)
        self.assertIn("LEX-FOUNDATION-01", ids)
        self.assertIn("LEX-COACH-01", ids)
        self.assertIn("LEX-FUTURE-01", ids)

    def test_nested_cross_signal_findings_merge_but_preserve_strict_obligation(self) -> None:
        findings = [
            {
                "start_char": 0,
                "end_char": 4,
                "file": "x.md",
                "line": 1,
                "column": 1,
                "matched": "值得注意",
                "signal_id": "LEX-STRICT-CORPUS-0001",
                "severity": "high",
                "candidate": True,
                "protected": False,
                "excluded": False,
                "count": 2,
            },
            {
                "start_char": 0,
                "end_char": 6,
                "file": "x.md",
                "line": 1,
                "column": 1,
                "matched": "值得注意的是",
                "signal_id": "LEX-EMPHASIS-01",
                "severity": "high",
                "candidate": True,
                "protected": False,
                "excluded": False,
                "count": 1,
            },
        ]
        merged = scanner._deduplicate_cross_signal_findings(findings)
        self.assertEqual(1, len(merged))
        self.assertEqual("值得注意的是", merged[0]["matched"])
        self.assertEqual(
            ["LEX-EMPHASIS-01", "LEX-STRICT-CORPUS-0001"],
            merged[0]["merged_signal_ids"],
        )
        self.assertEqual("REWRITE", merged[0]["action"])
        self.assertTrue(merged[0]["strict_overlap_requires_rewrite"])

    def test_crossing_signal_spans_are_not_collapsed(self) -> None:
        findings = [
            {
                "start_char": 0,
                "end_char": 4,
                "file": "x.md",
                "line": 1,
                "column": 1,
                "matched": "甲乙丙丁",
                "signal_id": "LEX-A",
                "severity": "high",
                "candidate": True,
                "protected": False,
                "excluded": False,
                "count": 1,
            },
            {
                "start_char": 2,
                "end_char": 6,
                "file": "x.md",
                "line": 1,
                "column": 3,
                "matched": "丙丁戊己",
                "signal_id": "LEX-B",
                "severity": "high",
                "candidate": True,
                "protected": False,
                "excluded": False,
                "count": 1,
            },
        ]
        self.assertEqual(2, len(scanner._deduplicate_cross_signal_findings(findings)))

    def test_trend_breakthrough_slogan_chain_is_located_without_banning_key_words(self) -> None:
        slogan = scanner.scan_text(
            "这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            lexicon=self.lexicon,
            scene="COURSE",
        )
        self.assertGreaterEqual(
            sum(item["signal_id"] == "LEX-MARKET-01" for item in slogan),
            3,
        )

        technical = scanner.scan_text(
            "判断函数单调性的关键是导数符号。",
            lexicon=self.lexicon,
            scene="COURSE",
        )
        self.assertNotIn("LEX-MARKET-01", {item["signal_id"] for item in technical})

    def test_market_slogans_in_explicit_template_fields_are_excluded_only_on_that_line(self) -> None:
        template = scanner.scan_text(
            "逻辑链条：给定首句。这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            lexicon=self.lexicon,
            scene="COURSE",
            include_excluded=True,
        )
        template_market = [item for item in template if item["signal_id"] == "LEX-MARKET-01"]
        self.assertEqual(3, len(template_market))
        self.assertTrue(all(item["excluded"] and item["action"] == "KEEP" for item in template_market))

        prose = scanner.scan_text(
            "这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            lexicon=self.lexicon,
            scene="COURSE",
            include_excluded=True,
        )
        prose_market = [item for item in prose if item["signal_id"] == "LEX-MARKET-01"]
        self.assertEqual(3, len(prose_market))
        self.assertTrue(all(item["candidate"] and not item["excluded"] for item in prose_market))

    def test_foundation_synonym_repair_to_research_starting_point_is_located(self) -> None:
        text = "这一结果不仅揭示了控制机制，而且是后续研究的出发点。"
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="RESEARCH")
        foundation = [item for item in findings if item["signal_id"] == "LEX-FOUNDATION-01"]

        self.assertEqual(1, len(foundation))
        self.assertEqual("high", foundation[0]["severity"])
        self.assertEqual("是后续研究的出发点", foundation[0]["matched"])

    def test_v51_abstract_benefit_and_vague_depth_repairs_are_located(self) -> None:
        text = (
            "这一现象并非单纯的测量误差问题，而是涉及更深层次的机制问题。"
            "上述结果为理解该现象的内在机制提供了线索。"
        )
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="RESEARCH")
        ids = {item["signal_id"] for item in findings}

        self.assertIn("LEX-ABSTRACT-BENEFIT-01", ids)
        self.assertIn("LEX-VAGUE-DEPTH-01", ids)
        self.assertTrue(
            all(
                item["severity"] == "high" and item["action"] == "REVIEW"
                for item in findings
                if item["signal_id"]
                in {"LEX-ABSTRACT-BENEFIT-01", "LEX-VAGUE-DEPTH-01"}
            )
        )

    def test_v51_specific_observation_and_named_alternatives_are_not_depth_shells(self) -> None:
        text = (
            "显微图像记录到界面条纹随温度发生位移。"
            "这一差值不能只归为测量误差；仪器漂移、样品老化和界面重排仍需分别检验。"
        )
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="RESEARCH")
        ids = {item["signal_id"] for item in findings}

        self.assertNotIn("LEX-ABSTRACT-BENEFIT-01", ids)
        self.assertNotIn("LEX-VAGUE-DEPTH-01", ids)

    def test_foundation_repair_to_reliable_starting_point_is_located(self) -> None:
        text = "相关结果也为后续研究提供了可靠起点。"
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="RESEARCH")
        foundation = [item for item in findings if item["signal_id"] == "LEX-FOUNDATION-01"]

        self.assertEqual(1, len(foundation))
        self.assertEqual("high", foundation[0]["severity"])
        self.assertEqual("为后续研究提供了可靠起点", foundation[0]["matched"])

    def test_course_coaching_and_empty_conclusion_synonym_repairs_are_located(self) -> None:
        text = "遇到这类题，必须注意，不要直接套公式。由此可以得出结论。"
        findings = scanner.scan_text(text, lexicon=self.lexicon, scene="COURSE")
        ids = {item["signal_id"] for item in findings}

        self.assertIn("LEX-COACH-01", ids)
        self.assertIn("LEX-CONCLUDE-01", ids)

    def test_v7_course_coaching_synonym_and_label_stripped_outlook_are_located(self) -> None:
        course = scanner.scan_text("遇到这类题目，公式必须记清楚。", lexicon=self.lexicon, scene="COURSE")
        modeling = scanner.scan_text(
            "传感器漂移可能影响模型。应用场景可以进一步拓展。",
            lexicon=self.lexicon,
            scene="MODELING",
        )

        self.assertIn("LEX-COACH-01", {item["signal_id"] for item in course})
        future = [item for item in modeling if item["signal_id"] == "LEX-FUTURE-01"]
        self.assertEqual(1, len(future))
        self.assertEqual("high", future[0]["severity"])

    def test_v8_course_memory_synonym_and_surviving_editor_note_are_located(self) -> None:
        course = scanner.scan_text("遇到这类题，公式需要记住。", lexicon=self.lexicon, scene="COURSE")
        modeling = scanner.scan_text(
            "20 ℃、25 ℃ 和 30 ℃ 三组数据仍需在正文中保留。",
            lexicon=self.lexicon,
            scene="MODELING",
        )

        self.assertIn("LEX-COACH-01", {item["signal_id"] for item in course})
        self.assertIn("LEX-META-01", {item["signal_id"] for item in modeling})

    def test_json_csv_and_text_outputs_have_location_contract(self) -> None:
        findings = scanner.scan_text("值得注意的是，结果并不均匀。", file="sample.md", lexicon=self.lexicon)
        notice = self.lexicon["output_policy"]

        json_payload = json.loads(scanner.render_output(findings, output_format="json", notice=notice))
        self.assertEqual(1, json_payload["candidate_count"])
        self.assertEqual("sample.md", json_payload["findings"][0]["file"])
        self.assertNotIn("score", json_payload)

        csv_text = scanner.render_output(findings, output_format="csv", notice=notice)
        csv_rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual("1", csv_rows[0]["line"])
        self.assertEqual("1", csv_rows[0]["column"])
        self.assertEqual("值得注意的是", csv_rows[0]["matched"])

        text_output = scanner.render_output(findings, output_format="text", notice=notice)
        self.assertIn("sample.md:1:1", text_output)
        self.assertIn("LEX-EMPH-01", text_output)

    def test_internal_occurrence_view_preserves_exact_character_offsets(self) -> None:
        text = "甲😀。值得注意的是，结果变化。"
        findings = scanner.scan_text_with_offsets(
            text,
            file="sample.md",
            lexicon=self.lexicon,
            scene="AUTO",
        )
        target = next(item for item in findings if item["signal_id"] == "LEX-EMPH-01")
        self.assertEqual("值得注意的是", text[target["start_char"] : target["end_char"]])
        public = scanner.scan_text(
            text,
            file="sample.md",
            lexicon=self.lexicon,
            scene="AUTO",
        )
        self.assertNotIn("start_char", public[0])
        self.assertNotIn("end_char", public[0])

    def test_finding_must_be_fully_inside_protected_span_to_be_protected(self) -> None:
        text = "“形成”研究闭环。"
        findings = scanner.scan_text_with_offsets(
            text,
            file="sample.md",
            lexicon=self.lexicon,
            scene="AUTO",
            include_protected=True,
        )
        target = next(item for item in findings if item["signal_id"] == "LEX-MGMT-01")
        self.assertFalse(target["protected"])
        self.assertTrue(target["candidate"])

    def test_cli_writes_machine_readable_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCANNER),
                str(FIXTURES / "positive.md"),
                "--scene",
                "auto",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertGreater(payload["candidate_count"], 0)
        first = payload["findings"][0]
        self.assertFalse({"file", "line", "column", "matched", "context", "count", "action"} - first.keys())
        self.assertTrue(all(item["scene"] == "AUTO" for item in payload["findings"]))
        self.assertEqual("PASS", payload["coverage"]["status"])
        self.assertEqual(1, payload["coverage"]["scanned_count"])

    def test_cli_reports_invalid_utf8_in_json_and_returns_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "invalid.md"
            invalid.write_bytes(b"\xff\xfe\xfa")
            completed = subprocess.run(
                [sys.executable, str(SCANNER), str(invalid), "--format", "json"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(2, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertEqual("REVIEW", payload["coverage"]["status"])
        self.assertEqual(1, payload["coverage"]["skipped_count"])
        self.assertEqual([str(invalid.resolve())], payload["coverage"]["skipped_files"])


if __name__ == "__main__":
    unittest.main()
