import csv
import importlib.util
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
SCRIPT = SKILL / "scripts" / "prepare_humanize_long_document.py"
SPEC = importlib.util.spec_from_file_location("prepare_humanize_long_document", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preparer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preparer
SPEC.loader.exec_module(preparer)


class LongDocumentPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_adjacent_display_and_inline_math_do_not_cross_mask_boundaries(self) -> None:
        text = (
            "$$v=\\frac{3}{2}t^2$$将力 $F=6t$ 以及位移元 "
            "$\\mathrm{d}x=\\frac{3}{2}t^2\\mathrm{d}t$ 一并代入。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        contents = [item["content"] for item in spans]

        self.assertIn("$$v=\\frac{3}{2}t^2$$", contents)
        self.assertIn("$F=6t$", contents)
        self.assertIn("$\\mathrm{d}x=\\frac{3}{2}t^2\\mathrm{d}t$", contents)
        self.assertTrue(all("将力" not in item for item in contents))
        self.assertTrue(all("一并代入" not in item for item in contents))

    def test_markdown_structure_uses_shared_protection_contract(self) -> None:
        text = (
            "---\r\ntitle: 完全够用\r\n---\r\n"
            "# 先盯住变量\n"
            "[正文](数值明明在变)\n"
            "[ref]: 两条关系接得上\n"
            '<span data-note="必须牢记">可编辑正文</span>\n'
        )
        spans = preparer.protected_spans(text, ".md", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text,
            0,
            len(text),
            spans,
        )

        for protected_text in (
            "title: 完全够用",
            "# 先盯住变量",
            "数值明明在变",
            "两条关系接得上",
            'data-note="必须牢记"',
        ):
            self.assertNotIn(protected_text, masked)
        self.assertIn("可编辑正文", masked)

    def test_tex_command_calls_protect_all_nested_arguments_by_default(self) -> None:
        text = (
            "正文使用 \\textbf{甲项与 \\emph{嵌套内容}}，"
            "并引用 \\mycite[见][第2页]{source-a,source-b}。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        contents = [item["content"] for item in spans]

        self.assertIn(r"\textbf{甲项与 \emph{嵌套内容}}", contents)
        self.assertIn(r"\mycite[见][第2页]{source-a,source-b}", contents)

    def test_tex_inline_verbatim_payload_is_not_exposed_to_authoring(self) -> None:
        text = (
            r"正文使用 \verb|token_甲=1|，并展示 "
            r"\Verb+token_丁=3+、"
            r'\lstinline!print("乙项")!，以及 '
            r"\lstinline[language=Python]!token_丙=2!，随后继续说明。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        contents = [item["content"] for item in spans]

        self.assertIn(r"\verb|token_甲=1|", contents)
        self.assertIn(r"\Verb+token_丁=3+", contents)
        self.assertIn(r'\lstinline!print("乙项")!', contents)
        self.assertIn(r"\lstinline[language=Python]!token_丙=2!", contents)
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )
        self.assertNotIn("token_甲=1", masked)
        self.assertNotIn("token_丁=3", masked)
        self.assertNotIn("print", masked)
        self.assertNotIn("token_丙=2", masked)
        self.assertIn("随后继续说明", masked)

    def test_custom_and_declared_short_verbatim_payloads_are_not_exposed(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "|token_甲=1|\n"
            "\\UndefineShortVerb{\\|}\n"
            "正文展示 \\CustomVerb!token_乙=2!，随后继续说明。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )

        self.assertNotIn("token_甲=1", masked)
        self.assertNotIn("token_乙=2", masked)
        self.assertIn("随后继续说明", masked)

    def test_short_and_custom_verbatim_aliases_reach_prepare_masking(self) -> None:
        text = (
            "\\MakeShortVerb{\\|}\n"
            "|token_甲=1|\n"
            "\\DeleteShortVerb{\\|}\n"
            "\\RecustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
            "\\InlineCode!token_乙=2!\n"
            "正文继续说明。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )

        self.assertNotIn("token_甲=1", masked)
        self.assertNotIn("token_乙=2", masked)
        self.assertIn("正文继续说明", masked)

    def test_declared_nonverb_command_and_parameterized_code_environment_are_masked(self) -> None:
        text = (
            "\\CustomVerbatimCommand{\\InlineCode}{Verb}{formatcom=\\small}\n"
            "正文 \\InlineCode|token_甲=1|。\n"
            "\\begin{Verbatim}[commandchars=\\\\\\{\\}]\n"
            "token_乙=2\n"
            "\\end{Verbatim}\n"
            "随后继续说明。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )
        scanner_payloads = [
            text[start:end]
            for start, end, _reason in preparer.lexical._merge_spans(
                preparer.lexical._tex_code_like_spans(text)[0]
            )
        ]

        self.assertNotIn("token_甲=1", masked)
        self.assertNotIn("token_乙=2", masked)
        self.assertIn("随后继续说明", masked)
        self.assertTrue(all(item in {span["content"] for span in spans} for item in scanner_payloads))

    def test_short_verb_undeclaration_returns_later_text_to_editable_scope(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\n"
            "|token_甲=1|\n"
            "\\UndefineShortVerb{\\|}\n"
            "正文 |形成完整闭环|。"
        )
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )

        self.assertNotIn("token_甲=1", masked)
        self.assertIn("形成完整闭环", masked)

    def test_percent_inside_verbatim_payload_does_not_hide_following_prose(self) -> None:
        text = r"正文 \verb|token%甲项|，随后继续说明。"
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )

        self.assertNotIn("token%甲项", masked)
        self.assertIn("随后继续说明", masked)

    def test_tex_structure_discovery_ignores_verbatim_payloads(self) -> None:
        text = (
            "\\verb|\\input{inline-ghost}|\n"
            "\\begin{Verbatim}\n"
            "\\input{environment-ghost}\n"
            "\\section{伪标题}\n"
            "\\begin{fake}\n"
            "\\end{Verbatim}\n"
            "\\section{真标题}\n"
            "正文。"
        )

        includes = preparer.discover_tex_includes(self.root / "main.tex", text)
        unresolved = preparer.discover_unresolved_tex_includes(text)
        environment_problems = preparer._environment_problems(text, ".tex")
        headings = preparer._heading_regions(text, ".tex")

        self.assertEqual([], includes)
        self.assertEqual([], unresolved)
        self.assertEqual([], environment_problems)
        self.assertEqual(
            ["(front-matter)", "真标题"],
            [item["heading_path"] for item in headings],
        )

    def test_prepare_uses_authenticated_balanced_tex_headings_end_to_end(self) -> None:
        list_body = (
            "\\begin{itemize}\n"
            "\\item 共同锚点甲说明\n"
            "\\item 共同锚点乙说明\n"
            "\\item 共同锚点丙说明\n"
            "\\end{itemize}\n"
        )
        headings = {
            "nested-command": "\\section{摘要 \\custom{重点}}\n",
            "inside-label": "\\section{摘要\\label{inside}}\n",
            "space-before-required": "\\section {摘要}\n",
            "trailing-label": "\\section{摘要}\\label{sec:x}\n",
            "optional-multiline": "\\section[\n短题\n]{摘要}\n",
            "required-multiline": "\\section[短题]{\n摘要\n}\n",
            "optional-required-multiline": "\\section[\n短题\n]\n{\n摘要\n}\n",
            "comment-before-required": "\\section%comment\n{摘要}\n",
        }

        for label, heading in headings.items():
            with self.subTest(label=label):
                source = self.root / f"{label}.tex"
                output = self.root / f"{label}-run"
                source.write_text(heading + list_body, encoding="utf-8")

                metadata = preparer.prepare(
                    [source], output, scene="GENERAL", min_author_chars=0
                )
                manifest = self.read_csv(output / "file_manifest.csv")
                units = [
                    json.loads(line)
                    for line in (output / "units.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                chunks = [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (output / "chunks").glob("*.json")
                ]
                spans = [
                    json.loads(line)
                    for line in (output / "protected_spans.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]

                self.assertEqual("READY", metadata["status"])
                self.assertEqual(1, len(manifest))
                self.assertEqual("READY", manifest[0]["status"])
                self.assertEqual(["摘要"], [item["heading_path"] for item in units])
                self.assertEqual(["PENDING"], [item["status"] for item in units])
                self.assertEqual(["摘要"], [item["heading_path"] for item in chunks])
                self.assertNotIn(
                    "(front-matter)",
                    {item["heading_path"] for item in [*units, *chunks]},
                )
                heading_spans = [
                    item for item in spans if "\\section" in item["content"]
                ]
                self.assertTrue(heading_spans)
                self.assertTrue(
                    any("locked-heading" in item["reason"] for item in heading_spans)
                )
                self.assertFalse(
                    any(item["status"] == "UNRESOLVED" for item in units)
                )

    def test_prepare_keeps_payload_free_heading_boundaries_distinct(self) -> None:
        headings = [
            r"\section{}",
            r"\section{$E=mc^2$}",
            r"\section{``Quoted''}",
            r"\section{\LaTeX}",
            r"\section{\custom{HiddenSummary}}",
        ]
        source = self.root / "opaque-headings.tex"
        source.write_text(
            "\n".join(
                heading + "\n" + f"\u6b63\u6587\u6bb5\u843d {index}\u3002"
                for index, heading in enumerate(headings, 1)
            ),
            encoding="utf-8",
        )
        output = self.root / "opaque-headings-run"

        metadata = preparer.prepare(
            [source], output, scene="GENERAL", min_author_chars=0
        )
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual(len(headings), len(units))
        self.assertEqual(["PENDING"] * len(headings), [item["status"] for item in units])
        paths = [str(item["heading_path"]) for item in units]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(
            all(
                path.startswith("(tex-section-title-line-")
                and "-offset-" in path
                for path in paths
            )
        )
        evidence = json.dumps(paths, ensure_ascii=False)
        for payload in ("HiddenSummary", "E=mc^2", "Quoted", "LaTeX"):
            self.assertNotIn(payload, evidence)

    def test_prepare_routes_visible_tex_heading_wrappers_end_to_end(self) -> None:
        headings = [
            (r"\section{\emph{课程说明}}", "课程说明"),
            (r"\section{前言 \textbf{模型建立}}", "前言 模型建立"),
            (r"\section{\textit{研究方法}}", "研究方法"),
        ]
        source = self.root / "visible-heading-wrappers.tex"
        source.write_text(
            "\n".join(
                heading + "\n" + f"正文段落 {index}。"
                for index, (heading, _expected) in enumerate(headings, 1)
            ),
            encoding="utf-8",
        )
        output = self.root / "visible-heading-wrappers-run"

        metadata = preparer.prepare(
            [source], output, scene="GENERAL", min_author_chars=0
        )
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual(
            [expected for _heading, expected in headings],
            [item["heading_path"] for item in units],
        )
        self.assertEqual(["PENDING"] * len(headings), [item["status"] for item in units])

    def test_prepare_heading_lock_uses_exact_arity_and_keeps_same_line_prose(self) -> None:
        same_line_prose = "\u540c\u4e00\u884c\u6b63\u6587\u3002"
        grouped_prose = "\u5206\u7ec4\u6b63\u6587"
        source = self.root / "exact-heading-arity.tex"
        source.write_text(
            "\n".join(
                [
                    rf"\section{{Summary}} {same_line_prose}",
                    rf"\section{{Intro}}{{{grouped_prose}}}",
                    "\u540e\u7eed\u6b63\u6587\u3002",
                ]
            ),
            encoding="utf-8",
        )
        output = self.root / "exact-heading-arity-run"

        metadata = preparer.prepare(
            [source], output, scene="GENERAL", min_author_chars=0
        )
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        spans = [
            json.loads(line)
            for line in (output / "protected_spans.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual(["PENDING", "PENDING"], [item["status"] for item in units])
        masked = "\n".join(str(item["masked_text"]) for item in chunks)
        self.assertIn(same_line_prose, masked)
        self.assertIn("{" + grouped_prose + "}", masked)
        heading_contents = [
            str(item["content"])
            for item in spans
            if "\\section" in str(item["content"])
        ]
        self.assertIn(r"\section{Summary}", heading_contents)
        self.assertIn(r"\section{Intro}", heading_contents)
        self.assertTrue(all(same_line_prose not in item for item in heading_contents))
        self.assertTrue(all(grouped_prose not in item for item in heading_contents))

    def test_prepare_marks_unsupported_heading_and_dynamic_tex_as_review(self) -> None:
        cases = {
            "single-token": (
                r"\section Intro",
                "TEX_HEADING_REQUIRED_ARGUMENT_UNSUPPORTED",
            ),
            "mid-line": (
                r"prefix \section{Same}",
                "TEX_HEADING_POSITION_UNSUPPORTED",
            ),
            "mid-line-unbalanced": (
                r"prefix \section{Broken",
                "TEX_HEADING_POSITION_UNSUPPORTED",
            ),
            "dynamic-control": (
                r"\csname section\endcsname{Fake}",
                "TEX_DYNAMIC_CONTROL_SEQUENCE_UNSUPPORTED",
            ),
            "conditional": (
                r"\iffalse \section{Fake} \fi",
                "TEX_CONDITIONAL_BRANCH_UNSUPPORTED",
            ),
            "catcode": (
                r"\catcode`\@=11 \section{Fake}",
                "TEX_CATCODE_MUTATION_UNSUPPORTED",
            ),
            "definition": (
                r"\def\generated{\section{Fake}}",
                "TEX_MACRO_DEFINITION_UNSUPPORTED",
            ),
        }
        for label, (text, problem_code) in cases.items():
            with self.subTest(label=label):
                source = self.root / f"{label}.tex"
                source.write_text(text + "\n", encoding="utf-8")
                output = self.root / f"{label}-run"

                metadata = preparer.prepare(
                    [source], output, scene="GENERAL", min_author_chars=0
                )
                manifest = self.read_csv(output / "file_manifest.csv")
                units = [
                    json.loads(line)
                    for line in (output / "units.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                chunks = [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (output / "chunks").glob("*.json")
                ]
                spans = [
                    json.loads(line)
                    for line in (output / "protected_spans.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]

                self.assertEqual("REVIEW", metadata["status"])
                self.assertEqual("READY", manifest[0]["status"])
                self.assertEqual(["UNRESOLVED"], [item["status"] for item in units])
                self.assertIn(problem_code, str(units[0]["notes"]))
                self.assertTrue(
                    any(
                        "malformed-locked-heading" in str(item["reason"])
                        for item in spans
                    )
                )
                masked = "\n".join(str(item["masked_text"]) for item in chunks)
                self.assertNotIn(text[text.index("\\"):], masked)

    def test_balanced_macro_definition_is_local_and_later_section_stays_pending(self) -> None:
        source = self.root / "local-definition.tex"
        definition = (
            r"\newcommand{\foo}[1]{\ifx#1\empty\else\textbf{#1}\fi}"
        )
        source.write_text(
            definition
            + "\n"
            + r"\section{Real}"
            + "\n\u771f\u5b9e\u6b63\u6587\u4ecd\u53ef\u7f16\u8f91\u3002\n",
            encoding="utf-8",
        )
        output = self.root / "local-definition-run"

        metadata = preparer.prepare(
            [source], output, scene="GENERAL", min_author_chars=0
        )
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        spans = [
            json.loads(line)
            for line in (output / "protected_spans.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual(
            ["UNRESOLVED", "PENDING"],
            [item["status"] for item in units],
        )
        real_chunk = next(item for item in chunks if item["heading_path"] == "Real")
        self.assertIn("\u771f\u5b9e\u6b63\u6587", real_chunk["masked_text"])
        definition_span = next(
            item for item in spans if definition in str(item["content"])
        )
        self.assertEqual(definition, definition_span["content"])
        self.assertNotIn(r"\section{Real}", definition_span["content"])

    def test_prepare_rejects_protected_and_nested_fake_tex_headings(self) -> None:
        list_body = (
            "\\begin{itemize}\n"
            "\\item 共同锚点甲说明\n"
            "\\item 共同锚点乙说明\n"
            "\\item 共同锚点丙说明\n"
            "\\end{itemize}\n"
        )
        prefixes = {
            "outer-command": "\\foo{\n\\section{伪标题}\n封装内容。\n}\n",
            "math": "\\[\n\\section{伪标题}\n\\]\n",
            "verbatim": (
                "\\begin{Verbatim}\n"
                "\\section{伪标题}\n"
                "\\end{Verbatim}\n"
            ),
            "comment": "% \\section{伪标题}\n",
        }

        for label, prefix in prefixes.items():
            with self.subTest(label=label):
                source = self.root / f"fake-{label}.tex"
                output = self.root / f"fake-{label}-run"
                source.write_text(
                    prefix + "\\section{真实标题}\n" + list_body,
                    encoding="utf-8",
                )

                metadata = preparer.prepare(
                    [source], output, scene="GENERAL", min_author_chars=0
                )
                manifest = self.read_csv(output / "file_manifest.csv")
                units = [
                    json.loads(line)
                    for line in (output / "units.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                chunks = [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (output / "chunks").glob("*.json")
                ]
                spans = [
                    json.loads(line)
                    for line in (output / "protected_spans.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]

                self.assertEqual("READY", metadata["status"])
                self.assertEqual(1, len(manifest))
                self.assertEqual("READY", manifest[0]["status"])
                self.assertEqual(
                    ["(front-matter)", "真实标题"],
                    [item["heading_path"] for item in units],
                )
                self.assertEqual(
                    {"(front-matter)", "真实标题"},
                    {item["heading_path"] for item in chunks},
                )
                self.assertNotIn("伪标题", {item["heading_path"] for item in units})
                self.assertFalse(
                    any(item["status"] == "UNRESOLVED" for item in units)
                )
                self.assertFalse(
                    any("protected_span_crosses_unit_boundary" in item["notes"] for item in units)
                )
                fake_spans = [
                    item
                    for item in spans
                    if "伪标题" in item["content"] and "真实标题" not in item["content"]
                ]
                self.assertTrue(fake_spans)
                self.assertFalse(
                    any("locked-heading" in item["reason"] for item in fake_spans)
                )
                self.assertTrue(
                    any(
                        "真实标题" in item["content"]
                        and "locked-heading" in item["reason"]
                        for item in spans
                    )
                )

    def test_prepare_does_not_follow_includes_or_structure_inside_verbatim(self) -> None:
        main = self.root / "main.tex"
        inline_ghost = self.root / "inline-ghost.tex"
        environment_ghost = self.root / "environment-ghost.tex"
        main.write_text(
            "\\verb|\\input{inline-ghost}|\n"
            "\\begin{Verbatim}\n"
            "\\input{environment-ghost}\n"
            "\\section{伪标题}\n"
            "\\begin{fake}\n"
            "\\end{Verbatim}\n"
            "\\section{真实标题}\n"
            "这里是唯一可编辑的正文。\n",
            encoding="utf-8",
        )
        # These files make false include discovery observable at the public API.
        inline_ghost.write_text("\\section{幽灵一}\n不应进入文件图。\n", encoding="utf-8")
        environment_ghost.write_text("\\section{幽灵二}\n不应进入文件图。\n", encoding="utf-8")
        output = self.root / "run"

        metadata = preparer.prepare([main], output, scene="GENERAL", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual([main.resolve()], [Path(row["path"]) for row in manifest])
        self.assertTrue(chunks)
        self.assertTrue(any(item["heading_path"] == "真实标题" for item in chunks))
        self.assertFalse(any("伪标题" in item["heading_path"] for item in chunks))
        self.assertFalse(any("fake" in item["notes"] for item in chunks))

    def test_prepare_ignores_structure_and_includes_inside_nonrendering_environments(self) -> None:
        for environment in ("comment", "filecontents", "filecontents*"):
            with self.subTest(environment=environment):
                suffix = environment.replace("*", "star")
                main = self.root / f"main-{suffix}.tex"
                ghost = self.root / f"ghost-{suffix}.tex"
                begin = (
                    f"\\begin{{{environment}}}{{generated-hidden.tex}}"
                    if environment.startswith("filecontents")
                    else f"\\begin{{{environment}}}"
                )
                main.write_text(
                    f"{begin}\n"
                    f"\\input{{{ghost.stem}}}\n"
                    "\\section{伪标题}\n"
                    "不可编辑载荷。\n"
                    f"\\end{{{environment}}}\n"
                    "\\section{真实标题}\n"
                    "这里是唯一可编辑的正文。\n",
                    encoding="utf-8",
                )
                ghost.write_text("\\section{幽灵}\n不应进入文件图。\n", encoding="utf-8")
                output = self.root / f"run-{suffix}"

                metadata = preparer.prepare(
                    [main], output, scene="GENERAL", min_author_chars=0
                )
                manifest = self.read_csv(output / "file_manifest.csv")
                units = [
                    json.loads(line)
                    for line in (output / "units.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]

                self.assertEqual("READY", metadata["status"])
                self.assertEqual([main.resolve()], [Path(row["path"]) for row in manifest])
                self.assertEqual(
                    ["(front-matter)", "真实标题"],
                    [item["heading_path"] for item in units],
                )
                self.assertNotIn("伪标题", {item["heading_path"] for item in units})
                self.assertNotIn("幽灵", {item["heading_path"] for item in units})

    def test_unclosed_short_verb_is_line_bounded_but_marks_run_unresolved(self) -> None:
        text = (
            "\\DefineShortVerb{\\|}\r\n"
            "|token_甲=1\r\n"
            "下一行 |token_乙=2|。\r\n"
        )
        source = self.root / "short-verb-crlf.tex"
        source.write_text(text, encoding="utf-8", newline="")
        output = self.root / "short-verb-crlf-run"

        metadata = preparer.prepare(
            [source], output, scene="GENERAL", min_author_chars=0
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        manifest = self.read_csv(output / "file_manifest.csv")

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual("AUTHOR_TEXT", manifest[0]["source_role"])
        self.assertIn(
            "TEX_MARKER_SCAN_INCOMPLETE",
            {
                item["kind"]
                for item in json.loads(manifest[0]["source_role_evidence"])
            },
        )
        self.assertTrue(chunks)
        self.assertTrue(all(item["status"] == "UNRESOLVED" for item in chunks))
        self.assertTrue(all("token_甲=1" not in item["masked_text"] for item in chunks))
        self.assertTrue(all("token_乙=2" not in item["masked_text"] for item in chunks))

    def test_incomplete_tex_protection_is_masked_and_marks_unit_unresolved(self) -> None:
        cases = {
            "verb": ("正文 \\verb|token_甲=1\n后文。", "token_甲=1"),
            "declared-verb": (
                "\\CustomVerbatimCommand{\\InlineCode}{Verb}{}\n"
                "正文 \\InlineCode|token_戊=5\n后文。",
                "token_戊=5",
            ),
            "code-environment": (
                "正文 \\begin{minted}{python}\ntoken_乙=2\n后文。",
                "token_乙=2",
            ),
            "nonrendering-environment": (
                "\\begin{comment}\ntoken_壬=9\n后文。",
                "token_壬=9",
            ),
            "inline-math": ("正文 $token_丙=3\n后文。", "token_丙=3"),
            "display-math": ("正文 $$token_己=6\n后文。", "token_己=6"),
            "paren-math": ("正文 \\(token_丁=4\n后文。", "token_丁=4"),
            "bracket-math": ("正文 \\[token_庚=7\n后文。", "token_庚=7"),
            "math-environment": (
                "正文 \\begin{equation}\ntoken_辛=8\n后文。",
                "token_辛=8",
            ),
        }
        for label, (text, payload) in cases.items():
            with self.subTest(label=label):
                source = self.root / f"{label}.tex"
                source.write_text(text, encoding="utf-8")
                output = self.root / f"{label}-run"
                metadata = preparer.prepare(
                    [source], output, scene="GENERAL", min_author_chars=0
                )
                chunks = [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (output / "chunks").glob("*.json")
                ]
                manifest = self.read_csv(output / "file_manifest.csv")

                self.assertEqual("REVIEW", metadata["status"])
                self.assertEqual("AUTHOR_TEXT", manifest[0]["source_role"])
                self.assertTrue(chunks)
                self.assertTrue(all(item["status"] == "UNRESOLVED" for item in chunks))
                self.assertTrue(all(payload not in item["masked_text"] for item in chunks))
                self.assertTrue(
                    all("environment:" in item["notes"] for item in chunks)
                )

    def test_multiline_and_even_escaped_inline_math_is_not_exposed(self) -> None:
        text = "跨行公式 $F=ma\n且仍在公式内$，以及换行符号 \\\\$G=mb$ 均应保护。"
        spans = preparer.protected_spans(text, ".tex", "F00001")
        masked, _protected_ids, _crossing = preparer._mask_text(
            text, 0, len(text), spans
        )

        self.assertNotIn("F=ma", masked)
        self.assertNotIn("且仍在公式内", masked)
        self.assertNotIn("G=mb", masked)

    def test_cli_missing_input_is_structured_fail_not_review_or_path_leak(self) -> None:
        private_root = self.root / "Alice" / "PrivateProject"
        missing = private_root / "student-name-main.tex"
        output = self.root / "missing-run"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(missing),
                "--output",
                str(output),
                "--scene",
                "GENERAL",
                "--intensity",
                "BALANCED",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["delivery_gate_status"])
        self.assertEqual("FAILED", payload["publish_state"])
        self.assertEqual(1, payload["exit_code"])
        self.assertEqual("INPUT_NOT_FOUND", payload["error_code"])
        self.assertFalse(payload["coverage_completion_claim_allowed"])
        self.assertFalse(payload["humanize_completion_claim_allowed"])
        self.assertEqual("", completed.stderr)
        self.assertNotIn(str(private_root), completed.stdout + completed.stderr)
        self.assertFalse(output.exists())

    def test_cli_existing_output_is_structured_contract_fail_not_review(self) -> None:
        source = self.root / "source.md"
        source.write_text("正文。\n", encoding="utf-8")
        output = self.root / "existing-run"
        output.mkdir()
        marker = output / "user.txt"
        marker.write_text("preserve", encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(source), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("INPUT_CONTRACT_INVALID", payload["error_code"])
        self.assertEqual("", completed.stderr)
        self.assertNotIn(str(output), completed.stdout + completed.stderr)
        self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_recursive_include_manifest_and_commented_include(self) -> None:
        main = self.root / "main.tex"
        chapter = self.root / "chapter.tex"
        main.write_text(
            "\\documentclass{article}\n\\begin{document}\n"
            "% \\input{ignored}\n\\input{chapter}\n\\end{document}\n",
            encoding="utf-8",
        )
        chapter.write_text("\\section{分析}\n模型用于比较两个方案。\n", encoding="utf-8")
        output = self.root / "run"
        metadata = preparer.prepare([main], output, scene="MODELING", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        self.assertEqual(2, len(manifest))
        self.assertFalse([row for row in manifest if "ignored" in row["path"]])
        chapter_row = next(row for row in manifest if row["path"].endswith("chapter.tex"))
        self.assertEqual("input", chapter_row["relation"])
        self.assertEqual(2, metadata["files_total"])

    def test_generated_include_marker_is_snapshotted_but_not_authored(self) -> None:
        main = self.root / "main.tex"
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        generated = generated_dir / "auto.tex"
        main.write_text(
            "\\input{generated/auto}\n主文件中的作者正文保留在改写队列。\n",
            encoding="utf-8",
        )
        generated.write_text(
            "% AUTO-GENERATED FILE. DO NOT EDIT\n"
            "这段生成文本不得进入作者正文改写队列。\n",
            encoding="utf-8",
        )
        output = self.root / "generated-run"

        metadata = preparer.prepare([main], output, scene="GENERAL", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        generated_row = next(row for row in manifest if Path(row["path"]).name == "auto.tex")
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual("GENERATED", generated_row["source_role"])
        self.assertEqual("RETAINED_GENERATED_NO_AUTHORING", generated_row["source_processing_status"])
        self.assertTrue((output / generated_row["snapshot_copy"]).is_file())
        self.assertFalse(any(item["file_id"] == generated_row["file_id"] for item in units))
        evidence = json.loads(generated_row["source_role_evidence"])
        self.assertTrue(
            any(
                item.get("marker_id") == "TEX_COMMENT_EN_AUTOGENERATED_DO_NOT_EDIT"
                for item in evidence
            )
        )

    def test_generated_path_without_marker_is_unresolved_not_generated(self) -> None:
        main = self.root / "main.tex"
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        included = generated_dir / "chapter.tex"
        main.write_text(
            "\\input{generated/chapter}\n主文件正文仍可进入队列。\n",
            encoding="utf-8",
        )
        included.write_text("没有确定性生成标记的正文。\n", encoding="utf-8")
        output = self.root / "path-only-run"

        metadata = preparer.prepare([main], output, scene="GENERAL", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        row = next(item for item in manifest if Path(item["path"]).name == "chapter.tex")
        units = [
            json.loads(line)
            for line in (output / "units.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual("UNRESOLVED", row["source_role"])
        self.assertEqual("UNRESOLVED_SOURCE_ROLE_NO_AUTHORING", row["source_processing_status"])
        self.assertFalse(any(item["file_id"] == row["file_id"] for item in units))
        evidence = json.loads(row["source_role_evidence"])
        self.assertTrue(any(item.get("kind") == "AUXILIARY_PATH_SEGMENT" for item in evidence))
        self.assertTrue(
            any(item.get("reason") == "PATH_SEGMENT_IS_AUXILIARY_ONLY" for item in evidence)
        )

    def test_generation_marker_inside_opaque_or_body_text_is_not_evidence(self) -> None:
        cases = {
            "verbatim": (
                "\\begin{verbatim}\n% AUTO-GENERATED FILE. DO NOT EDIT\n\\end{verbatim}\n正文。\n"
            ),
            "comment": (
                "\\begin{comment}\n% AUTO-GENERATED FILE. DO NOT EDIT\n\\end{comment}\n正文。\n"
            ),
            "filecontents": (
                "\\begin{filecontents}{sample.tex}\n"
                "% AUTO-GENERATED FILE. DO NOT EDIT\n"
                "\\end{filecontents}\n正文。\n"
            ),
            "body": "AUTO-GENERATED FILE. DO NOT EDIT\n正文。\n",
            "command": "\\texttt{AUTO-GENERATED FILE. DO NOT EDIT}\n正文。\n",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                source = self.root / f"marker-{label}.tex"
                source.write_text(text, encoding="utf-8")
                output = self.root / f"marker-{label}-run"

                metadata = preparer.prepare(
                    [source], output, scene="GENERAL", min_author_chars=0
                )
                row = self.read_csv(output / "file_manifest.csv")[0]

                self.assertEqual("READY", metadata["status"])
                self.assertEqual("AUTHOR_TEXT", row["source_role"])
                evidence = json.loads(row["source_role_evidence"])
                self.assertFalse(
                    any(item.get("kind") == "DETERMINISTIC_TEX_COMMENT_MARKER" for item in evidence)
                )

    def test_nested_case_variant_and_alias_include_reaches_one_generated_record(self) -> None:
        main = self.root / "main.tex"
        chapters = self.root / "chapters"
        generated_dir = self.root / "generated"
        chapters.mkdir()
        generated_dir.mkdir()
        chapter = chapters / "chapter.tex"
        generated = generated_dir / "Auto.TeX"
        main.write_text("\\input{chapters/chapter}\n主文件正文。\n", encoding="utf-8")
        chapter.write_text(
            "\\input{../generated/AUTO}\n"
            "\\input{../generated/../generated/auto}\n"
            "章节作者正文。\n",
            encoding="utf-8",
        )
        generated.write_text(
            "% ThIs Is An AuTo-GeNeRaTeD FiLe; Do NoT EdIt.\n生成内容。\n",
            encoding="utf-8",
        )
        output = self.root / "nested-alias-run"

        preparer.prepare([main], output, scene="GENERAL", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        generated_rows = [
            row for row in manifest if Path(row["path"]).name.casefold() == "auto.tex"
        ]

        self.assertEqual(1, len(generated_rows))
        self.assertEqual("GENERATED", generated_rows[0]["source_role"])
        self.assertEqual("input", generated_rows[0]["relation"])

    def test_source_role_override_binds_reason_file_and_snapshot_hash(self) -> None:
        main = self.root / "main.tex"
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        included = generated_dir / "chapter.tex"
        main.write_text("\\input{generated/chapter}\n主文件正文。\n", encoding="utf-8")
        included.write_text("调用方明确纳入的作者正文。\n", encoding="utf-8")
        override = self.root / "scope.json"
        override.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-source-role-overrides/v1",
                    "overrides": [
                        {
                            "path": "generated/chapter.tex",
                            "source_role": "AUTHOR_TEXT",
                            "reason": "用户明确指定该章节属于本轮作者正文范围",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = self.root / "override-run"

        metadata = preparer.prepare(
            [main],
            output,
            scene="GENERAL",
            min_author_chars=0,
            source_role_overrides=override,
        )
        manifest = self.read_csv(output / "file_manifest.csv")
        row = next(item for item in manifest if Path(item["path"]).name == "chapter.tex")
        artifact = json.loads(
            (output / "source_role_overrides.json").read_text(encoding="utf-8")
        )
        applied = artifact["overrides"][0]["applied_files"]

        self.assertEqual("READY", metadata["status"])
        self.assertEqual("APPLIED", metadata["source_role_override_status"])
        self.assertEqual("AUTHOR_TEXT", row["source_role"])
        self.assertEqual("AUTHORING_QUEUE_BY_CALLER_OVERRIDE", row["source_processing_status"])
        self.assertEqual(
            [{"file_id": row["file_id"], "snapshot_sha256": row["sha256"]}],
            applied,
        )
        self.assertIn(artifact["overrides"][0]["override_id"], row["source_role_evidence"])

    def test_source_role_override_unknown_target_fails_closed(self) -> None:
        source = self.root / "main.tex"
        source.write_text("作者正文。\n", encoding="utf-8")
        override = self.root / "scope-missing.json"
        override.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-source-role-overrides/v1",
                    "overrides": [
                        {
                            "path": "missing.tex",
                            "source_role": "AUTHOR_TEXT",
                            "reason": "该文件并未进入冻结闭包",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "must match exactly one readable file"):
            preparer.prepare(
                [source],
                self.root / "override-missing-run",
                scene="GENERAL",
                min_author_chars=0,
                source_role_overrides=override,
            )

    def test_dynamic_tex_include_is_recorded_as_unresolved(self) -> None:
        main = self.root / "main.tex"
        chapter_dir = self.root / "chapters"
        chapter_dir.mkdir()
        (chapter_dir / "chapter.tex").write_text(
            "\\section{章节}\n这一章必须进入全文覆盖。\n",
            encoding="utf-8",
        )
        main.write_text(
            "\\newcommand{\\chapterdir}{chapters}\n"
            "\\input{\\chapterdir/chapter}\n"
            "主文件正文。\n",
            encoding="utf-8",
        )

        output = self.root / "run"
        metadata = preparer.prepare([main], output, min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        unresolved = [row for row in manifest if row["status"] == "UNRESOLVED_INCLUDE"]

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual(1, len(unresolved))
        self.assertEqual("input", unresolved[0]["relation"])
        self.assertIn(r"\chapterdir/chapter", unresolved[0]["reason"])

    def test_garbled_include_is_recorded_and_other_files_continue(self) -> None:
        main = self.root / "main.tex"
        bad = self.root / "bad.tex"
        good = self.root / "good.tex"
        main.write_text("\\input{bad}\n\\input{good}\n", encoding="utf-8")
        bad.write_bytes(b"\x81\x30\xff\xff\x81")
        good.write_text("\\section{结果}\n结果保持稳定。\n", encoding="utf-8")
        output = self.root / "run"
        metadata = preparer.prepare([main], output, min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        statuses = {Path(row["path"]).name: row["status"] for row in manifest}
        reasons = {Path(row["path"]).name: row["reason"] for row in manifest}
        self.assertEqual("SKIPPED_GARBLED", statuses["bad.tex"])
        self.assertEqual("READY", statuses["good.tex"])
        self.assertRegex(
            reasons["bad.tex"],
            r"utf8_decode_error:start=0:end=1:bytes=81:input_bytes=5;"
            r"gb18030_decode_error:start=0:end=1:bytes=81:input_bytes=5",
        )
        self.assertNotIn("\\input", reasons["bad.tex"])
        self.assertEqual("REVIEW", metadata["status"])

    def test_utf16le_input_is_marked_garbled(self) -> None:
        source = self.root / "utf16.tex"
        source.write_bytes("\\section{背景}\n这是一段中文正文。\n".encode("utf-16-le"))

        output = self.root / "run"
        metadata = preparer.prepare([source], output, min_author_chars=0)
        row = self.read_csv(output / "file_manifest.csv")[0]

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual("SKIPPED_GARBLED", row["status"])
        self.assertIn("control", row["reason"])

    def test_nul_and_control_characters_are_marked_garbled(self) -> None:
        for name, payload in (
            ("nul.tex", "\\section{背景}\x00\n正文。\n"),
            ("control.tex", "\\section{背景}\x01\n正文。\n"),
        ):
            with self.subTest(name=name):
                source = self.root / name
                source.write_text(payload, encoding="utf-8")
                output = self.root / f"run-{name}"

                metadata = preparer.prepare([source], output, min_author_chars=0)
                row = self.read_csv(output / "file_manifest.csv")[0]

                self.assertEqual("REVIEW", metadata["status"])
                self.assertEqual("SKIPPED_GARBLED", row["status"])
                self.assertIn("control", row["reason"])

    def test_fixed_read_does_not_absorb_appended_bytes(self) -> None:
        path = self.root / "active.md"
        path.write_bytes("第一版".encode("utf-8"))
        length = path.stat().st_size
        path.write_bytes("第一版追加".encode("utf-8"))
        frozen = preparer.read_fixed_bytes(path, length)
        self.assertEqual("第一版", frozen.decode("utf-8"))

    def test_tex_units_mask_math_exam_and_commands(self) -> None:
        source = self.root / "book.tex"
        source.write_text(
            "\\section{导数}\n"
            "作者先说明判断条件。公式为 $f'(x)=2x-2$。\n\n"
            "\\begin{exercise}\n必须牢记原题。\n\\end{exercise}\n\n"
            "参见式 \\eqref{eq:a}，再比较两个区间。\n",
            encoding="utf-8",
        )
        output = self.root / "run"
        preparer.prepare([source], output, scene="COURSE", min_author_chars=0)
        chunks = list((output / "chunks").glob("*.json"))
        self.assertTrue(chunks)
        combined = "\n".join(json.loads(path.read_text(encoding="utf-8"))["masked_text"] for path in chunks)
        self.assertIn("[[PROTECTED:", combined)
        self.assertNotIn("f'(x)=2x-2", combined)
        self.assertNotIn("必须牢记原题", combined)
        self.assertNotIn("eqref{eq:a}", combined)

    def test_tex_style_wrappers_require_explicit_edit_permission(self) -> None:
        source = self.root / "styled.tex"
        source.write_text(
            "\\section{结果}\n普通说明与\\textbf{装饰性强调}并列。\n",
            encoding="utf-8",
        )

        locked_output = self.root / "locked"
        locked = preparer.prepare([source], locked_output, min_author_chars=0)
        locked_text = "\n".join(
            json.loads(path.read_text(encoding="utf-8"))["masked_text"]
            for path in (locked_output / "chunks").glob("*.json")
        )
        self.assertNotIn(r"\textbf", locked_text)
        self.assertEqual([], locked["editable_style_wrappers"])

        editable_output = self.root / "editable"
        editable = preparer.prepare(
            [source],
            editable_output,
            min_author_chars=0,
            editable_style_wrappers=["textbf"],
        )
        editable_text = "\n".join(
            json.loads(path.read_text(encoding="utf-8"))["masked_text"]
            for path in (editable_output / "chunks").glob("*.json")
        )
        self.assertIn(r"\textbf{装饰性强调}", editable_text)
        self.assertEqual(["textbf"], editable["editable_style_wrappers"])

        with self.assertRaisesRegex(ValueError, "unsupported editable style wrapper"):
            preparer.prepare(
                [source],
                self.root / "invalid-wrapper",
                min_author_chars=0,
                editable_style_wrappers=["section"],
            )

    def test_markdown_units_and_ledger_statuses_sum(self) -> None:
        source = self.root / "notes.md"
        source.write_text(
            "---\ntitle: 示例\n---\n\n# 第一节\n这是一段作者说明。\n\n"
            "## 第二节\n> 这是直接引语。\n\n作者继续说明。\n",
            encoding="utf-8",
        )
        output = self.root / "run"
        metadata = preparer.prepare([source], output, scene="GENERAL", min_author_chars=0)
        ledger = self.read_csv(output / "coverage_ledger.csv")
        self.assertEqual(metadata["units_total"], len(ledger))
        allowed = {"PENDING", "SKIPPED_PROTECTED", "SKIPPED_GARBLED", "UNRESOLVED", "CHANGED_AFTER_SNAPSHOT"}
        self.assertFalse({row["status"] for row in ledger} - allowed)
        self.assertNotIn("DONE", {row["status"] for row in ledger})
        self.assertTrue((output / "snapshot.json").is_file())
        self.assertTrue((output / "units.jsonl").is_file())
        self.assertTrue((output / "protected_spans.jsonl").is_file())
        self.assertTrue((output / "prepare_integrity.json").is_file())

    def test_plain_text_seed_is_discovered_and_split_as_paragraphs(self) -> None:
        source = self.root / "notes.txt"
        source.write_text(
            "第一段说明研究对象和范围。\n\n第二段说明结果的边界。\n",
            encoding="utf-8",
        )

        output = self.root / "txt-run"
        metadata = preparer.prepare([source], output, scene="GENERAL", min_author_chars=0)
        manifest = self.read_csv(output / "file_manifest.csv")
        ledger = self.read_csv(output / "coverage_ledger.csv")

        self.assertEqual("READY", metadata["status"])
        self.assertEqual(".txt", manifest[0]["suffix"])
        self.assertEqual(1, len(ledger))
        self.assertTrue(all(row["status"] == "PENDING" for row in ledger))

    def test_structural_intensity_freezes_paragraph_inventory_and_title_lock(self) -> None:
        source = self.root / "structural.md"
        source.write_text(
            "# 讨论\n\n第一段说明当前观察对象与范围。\n\n"
            "第二段解释两种表述之间的差别。\n\n"
            "第三段收束本节已经形成的判断范围与适用条件。\n",
            encoding="utf-8",
        )
        output = self.root / "structural-run"

        metadata = preparer.prepare(
            [source],
            output,
            scene="GENERAL",
            intensity="STRUCTURAL",
            min_author_chars=0,
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        pending = next(item for item in chunks if item["status"] == "PENDING")
        inventory = pending["structural_paragraphs"]

        self.assertEqual("STRUCTURAL", metadata["intensity"])
        self.assertEqual("STRUCTURAL", pending["intensity"])
        self.assertEqual("humanize-structural-plan/v1", pending["structural_plan_schema"])
        self.assertEqual("UNIT", pending["structural_scope"])
        self.assertTrue(pending["structural_title_lock"])
        self.assertFalse(pending["structural_cross_unit_moves_allowed"])
        self.assertEqual(
            preparer.structural_inventory_sha256(inventory),
            pending["structural_inventory_sha256"],
        )
        self.assertGreaterEqual(sum(bool(item["movable"]) for item in inventory), 2)
        self.assertTrue(any(item["lock_reason"] for item in inventory))

        with self.assertRaisesRegex(ValueError, "unsupported rewrite intensity"):
            preparer.prepare(
                [source],
                self.root / "bad-intensity",
                intensity="AGGRESSIVE",
                min_author_chars=0,
            )

    def test_structural_transaction_inventory_is_always_emitted_with_safe_default(self) -> None:
        source = self.root / "default-scope.md"
        source.write_text("# 背景\n这一段只用于检查默认事务范围。\n", encoding="utf-8")

        ordinary_output = self.root / "ordinary"
        ordinary = preparer.prepare(
            [source],
            ordinary_output,
            scene="GENERAL",
            min_author_chars=0,
        )
        ordinary_inventory = json.loads(
            (ordinary_output / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("NONE", ordinary["structural_transaction_scope"])
        self.assertEqual("NOT_APPLICABLE", ordinary_inventory["status"])
        self.assertEqual([], ordinary_inventory["transactions"])
        self.assertEqual(0, ordinary["structural_transaction_candidates"])
        self.assertFalse(
            ordinary_inventory["scope_authorization"][
                "mechanical_scope_permission_granted"
            ]
        )

        structural_output = self.root / "structural-disabled"
        structural = preparer.prepare(
            [source],
            structural_output,
            scene="GENERAL",
            intensity="STRUCTURAL",
            min_author_chars=0,
        )
        structural_inventory = json.loads(
            (structural_output / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("NONE", structural["structural_transaction_scope"])
        self.assertEqual("DISABLED", structural_inventory["status"])
        self.assertEqual([], structural_inventory["transactions"])
        self.assertFalse(
            structural_inventory["scope_authorization"][
                "mechanical_scope_permission_granted"
            ]
        )

    def test_adjacent_pair_scope_requires_structural_intensity(self) -> None:
        source = self.root / "invalid-scope.md"
        source.write_text("# 背景\n普通作者正文。\n", encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "ADJACENT_PAIR_requires_STRUCTURAL_intensity",
        ):
            preparer.prepare(
                [source],
                self.root / "invalid-run",
                intensity="BALANCED",
                structural_transaction_scope="ADJACENT_PAIR",
                min_author_chars=0,
            )
        self.assertFalse((self.root / "invalid-run").exists())

        with self.assertRaisesRegex(ValueError, "unsupported structural transaction scope"):
            preparer.prepare(
                [source],
                self.root / "unknown-run",
                intensity="STRUCTURAL",
                structural_transaction_scope="WHOLE_SECTION",
                min_author_chars=0,
            )
        self.assertFalse((self.root / "unknown-run").exists())

    def test_adjacent_pair_inventory_binds_snapshot_voice_and_compound_refs(self) -> None:
        source = self.root / "adjacent-pair.md"
        source.write_text(
            "# 讨论\n第一部分说明观察对象、判断边界与所采用的比较口径。\n\n"
            "第二部分说明两种表达的差别以及本段保留的限定范围。\n",
            encoding="utf-8",
        )
        output = self.root / "adjacent-pair-run"

        metadata = preparer.prepare(
            [source],
            output,
            scene="GENERAL",
            intensity="STRUCTURAL",
            structural_transaction_scope="ADJACENT_PAIR",
            max_author_chars=32,
            min_author_chars=0,
        )
        inventory = json.loads(
            (output / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual(2, len(chunks))
        self.assertEqual("READY", inventory["status"])
        self.assertEqual("ADJACENT_PAIR", inventory["candidate_scope"])
        self.assertEqual(2, inventory["candidate_cardinality"])
        self.assertEqual(1, metadata["structural_transaction_candidates"])
        self.assertEqual(
            "structural_transaction_inventory.json",
            metadata["structural_transaction_inventory"],
        )
        self.assertEqual(inventory["inventory_sha256"], metadata["structural_transaction_inventory_sha256"])
        self.assertEqual(
            inventory["eligibility_policy_revision"],
            metadata["structural_transaction_policy_revision"],
        )
        self.assertEqual(
            inventory["eligibility_policy_sha256"],
            metadata["structural_transaction_policy_sha256"],
        )
        self.assertEqual(
            preparer.canonical_sha256(preparer.STRUCTURAL_TRANSACTION_POLICY),
            inventory["eligibility_policy_sha256"],
        )
        self.assertEqual(
            preparer.sha256((output / "snapshot.json").read_bytes()),
            inventory["snapshot_sha256"],
        )
        self.assertEqual(
            preparer.canonical_sha256(
                {key: value for key, value in inventory.items() if key != "inventory_sha256"}
            ),
            inventory["inventory_sha256"],
        )

        transaction = inventory["transactions"][0]
        self.assertEqual(2, transaction["participant_count"])
        self.assertEqual(inventory["snapshot_id"], transaction["snapshot_id"])
        self.assertEqual(inventory["snapshot_sha256"], transaction["snapshot_sha256"])
        self.assertEqual(
            inventory["candidate_basis_sha256"],
            transaction["candidate_basis_sha256"],
        )
        self.assertEqual(["LEFT", "RIGHT"], [item["role"] for item in transaction["compound_refs"]])
        self.assertEqual(
            [item["unit_id"] for item in chunks],
            [item["unit_id"] for item in transaction["compound_refs"]],
        )
        for compound_ref in transaction["compound_refs"]:
            self.assertEqual(
                preparer.canonical_sha256(
                    {
                        key: value
                        for key, value in compound_ref.items()
                        if key != "compound_ref_sha256"
                    }
                ),
                compound_ref["compound_ref_sha256"],
            )
        self.assertEqual(chunks[0]["end"], chunks[1]["start"])
        self.assertEqual(chunks[0]["end"], transaction["boundary"]["left_end"])
        self.assertEqual(chunks[1]["start"], transaction["boundary"]["right_start"])
        self.assertEqual(chunks[1]["unit_id"], transaction["boundary"]["left_context_after_unit"])
        self.assertEqual(chunks[0]["unit_id"], transaction["boundary"]["right_context_before_unit"])
        self.assertEqual(
            {
                "voice_profile_id",
                "voice_profile_revision",
                "voice_profile_confidence",
                "voice_profile_kind",
                "voice_profile_source",
                "voice_profile_binding_scene",
                "voice_profile_sha256",
                "voice_default_disclosure",
            },
            set(transaction["voice_binding"]),
        )
        self.assertEqual(
            preparer.canonical_sha256(transaction["voice_binding"]),
            transaction["voice_binding_sha256"],
        )
        transaction_payload = {
            key: value
            for key, value in transaction.items()
            if key not in {"transaction_id", "transaction_binding_sha256"}
        }
        self.assertEqual(
            preparer.canonical_sha256(transaction_payload),
            transaction["transaction_binding_sha256"],
        )
        self.assertTrue(transaction["transaction_id"].startswith("STX-"))
        self.assertTrue(
            inventory["scope_authorization"][
                "mechanical_scope_permission_granted"
            ]
        )
        self.assertTrue(
            transaction["constraints"]["mechanical_scope_permission_granted"]
        )
        self.assertFalse(
            transaction["constraints"]["candidate_inventory_is_execution_request"]
        )
        self.assertFalse(
            transaction["constraints"]["inventory_alone_execution_authorized"]
        )
        self.assertTrue(
            transaction["constraints"]["bound_transaction_bundle_required"]
        )
        self.assertFalse(transaction["constraints"]["semantic_clearance_granted"])
        self.assertEqual("NOT_EVALUATED", transaction["constraints"]["structural_semantic_mapping"])
        self.assertTrue(all(item["structural_scope"] == "UNIT" for item in chunks))
        self.assertTrue(all(not item["structural_cross_unit_moves_allowed"] for item in chunks))

    def test_adjacent_pair_inventory_allows_overlapping_edges_but_filters_bad_pairs(self) -> None:
        source = self.root / "three-parts.md"
        source.write_text(
            "# 讨论\n第一部分只说明当前观察对象和比较范围。\n\n"
            "第二部分只说明两个表述之间的具体差别。\n\n"
            "第三部分只说明这一判断适用的限定范围。\n",
            encoding="utf-8",
        )
        output = self.root / "three-parts-run"
        preparer.prepare(
            [source],
            output,
            scene="GENERAL",
            intensity="STRUCTURAL",
            structural_transaction_scope="ADJACENT_PAIR",
            max_author_chars=24,
            min_author_chars=0,
        )
        inventory = json.loads(
            (output / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual(3, len(chunks))
        self.assertEqual(2, len(inventory["transactions"]))
        self.assertEqual(
            2,
            len({item["transaction_id"] for item in inventory["transactions"]}),
        )
        self.assertEqual(
            chunks[1]["unit_id"],
            inventory["transactions"][0]["compound_refs"][1]["unit_id"],
        )
        self.assertEqual(
            chunks[1]["unit_id"],
            inventory["transactions"][1]["compound_refs"][0]["unit_id"],
        )

        snapshot = json.loads((output / "snapshot.json").read_text(encoding="utf-8"))
        file_sha256_by_id = {
            item["file_id"]: item["sha256"] for item in snapshot["files"]
        }

        def rebuilt(mutator) -> dict:
            changed = [dict(item) for item in chunks]
            mutator(changed)
            return preparer.build_structural_transaction_inventory(
                changed,
                snapshot_id=snapshot["snapshot_id"],
                snapshot_sha256=preparer.sha256((output / "snapshot.json").read_bytes()),
                file_sha256_by_id=file_sha256_by_id,
                intensity="STRUCTURAL",
                scope="ADJACENT_PAIR",
            )

        mutations = (
            lambda items: items[1].update(status="UNRESOLVED"),
            lambda items: items[1].update(file_id="F-other"),
            lambda items: items[1].update(start=items[1]["start"] + 1),
            lambda items: items[1].update(heading_path="另一节"),
            lambda items: items[1].update(part=99),
            lambda items: items[1].update(scene="RESEARCH"),
            lambda items: items[1].update(voice_profile_sha256="f" * 64),
            lambda items: items[0].update(context_after_unit="U-other"),
            lambda items: items[1].update(context_before_unit="U-other"),
        )
        for mutator in mutations:
            with self.subTest(mutator=mutator):
                rebuilt_inventory = rebuilt(mutator)
                self.assertLess(len(rebuilt_inventory["transactions"]), 2)
                self.assertNotEqual(
                    inventory["candidate_basis_sha256"],
                    rebuilt_inventory["candidate_basis_sha256"],
                )

    def test_prepare_integrity_v2_is_strict_sorted_and_binds_inventory(self) -> None:
        source = self.root / "integrity.md"
        source.write_text("# 背景\n这一段用于检查准备工件完整性。\n", encoding="utf-8")
        output = self.root / "integrity-run"
        preparer.prepare([source], output, scene="GENERAL", min_author_chars=0)

        manifest = json.loads((output / "prepare_integrity.json").read_text(encoding="utf-8"))
        paths = [item["path"] for item in manifest["artifacts"]]
        self.assertEqual(2, manifest["schema_version"])
        self.assertEqual(
            preparer.PREPARE_INTEGRITY_PURPOSE,
            manifest["purpose"],
        )
        self.assertEqual(
            {"schema_version", "purpose", "artifacts"},
            set(manifest),
        )
        self.assertEqual(sorted(paths), paths)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("structural_transaction_inventory.json", paths)
        self.assertTrue(all(set(item) == {"path", "sha256", "bytes"} for item in manifest["artifacts"]))
        for item in manifest["artifacts"]:
            artifact = output / item["path"]
            self.assertEqual(artifact.stat().st_size, item["bytes"])
            self.assertEqual(preparer.sha256(artifact.read_bytes()), item["sha256"])
        preparer.validate_integrity_manifest(output, manifest)

        malformed = json.loads(json.dumps(manifest))
        malformed["artifacts"][0]["extra"] = True
        with self.assertRaisesRegex(ValueError, "integrity artifact fields mismatch"):
            preparer.validate_integrity_manifest(output, malformed)

        duplicate = json.loads(json.dumps(manifest))
        duplicate["artifacts"].append(dict(duplicate["artifacts"][0]))
        with self.assertRaisesRegex(ValueError, "integrity artifact paths must be unique and sorted"):
            preparer.validate_integrity_manifest(output, duplicate)

        wrong_bytes = json.loads(json.dumps(manifest))
        wrong_bytes["artifacts"][0]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "integrity artifact bytes mismatch"):
            preparer.validate_integrity_manifest(output, wrong_bytes)

    def test_real_physics_tex_structural_inventory_is_nontrivial_and_conservative(self) -> None:
        source = Path(__file__).resolve().parents[1] / "physics1.tex"
        if not source.is_file():
            self.skipTest("workspace physics1.tex is unavailable")
        output = self.root / "real-physics-structural"

        metadata = preparer.prepare(
            [source],
            output,
            scene="COURSE",
            intensity="STRUCTURAL",
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        pending = [item for item in chunks if item["status"] == "PENDING"]
        paragraphs = [
            paragraph
            for chunk in pending
            for paragraph in chunk["structural_paragraphs"]
        ]
        movable = [item for item in paragraphs if item["movable"]]
        locked = [item for item in paragraphs if not item["movable"]]

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual("STRUCTURAL", metadata["intensity"])
        self.assertGreaterEqual(len(pending), 40)
        self.assertGreaterEqual(metadata["protected_spans_total"], 2000)
        self.assertGreaterEqual(len(paragraphs), 400)
        self.assertGreaterEqual(len(movable), 20)
        self.assertGreater(len(locked), len(movable))
        self.assertTrue(any(item["protected_ids"] for item in movable))
        self.assertTrue(
            any(
                item["lock_reason"] == "contains_immovable_protected_span"
                for item in locked
            )
        )
        self.assertTrue(
            all(
                item["structural_title_lock"]
                and not item["structural_cross_unit_moves_allowed"]
                for item in pending
            )
        )

    def test_auto_routes_each_unit_and_binds_scene_specific_default_profiles(self) -> None:
        source = self.root / "mixed.md"
        source.write_text(
            "# 例题与解析\n本题先辨认条件，再代入公式。\n\n"
            "# 问题三的模型建立与求解\n建立状态变量并设置参数，随后进行数值求解。\n\n"
            "# 结果与讨论\n本研究的实验结果表明，该判断仅在当前范围成立。\n\n"
            "# 背景\n该段保留原有范围说明。\n",
            encoding="utf-8",
        )
        output = self.root / "auto-mixed"

        metadata = preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual("PASS", metadata["scene_routing_status"])
        self.assertEqual(
            ["COURSE", "MODELING", "RESEARCH", "GENERAL"],
            [item["scene"] for item in chunks],
        )
        self.assertEqual(
            ["ROUTED", "ROUTED", "ROUTED", "FALLBACK_GENERAL"],
            [item["scene_routing_decision"] for item in chunks],
        )
        self.assertEqual(4, len({item["voice_profile_sha256"] for item in chunks}))
        self.assertTrue((output / "voice_profile_set.json").is_file())
        self.assertEqual(4, len(list((output / "voice_profiles").glob("*.json"))))

    def test_auto_ambiguous_unit_is_unresolved_and_cannot_enter_rewrite_queue(self) -> None:
        source = self.root / "ambiguous.md"
        source.write_text(
            "# 模型建立与研究方法\n本研究建立状态变量模型。\n",
            encoding="utf-8",
        )
        output = self.root / "auto-ambiguous"

        metadata = preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunk = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        )

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual("REVIEW", metadata["scene_routing_status"])
        self.assertEqual("AMBIGUOUS", chunk["scene_routing_decision"])
        self.assertEqual("UNRESOLVED", chunk["status"])
        self.assertIn("ambiguous_scene_route", chunk["notes"])

    def test_auto_low_score_positive_tie_is_also_unresolved(self) -> None:
        source = self.root / "low-score-ambiguous.md"
        source.write_text(
            "# 方法\n本题需要说明。本研究需要说明。\n",
            encoding="utf-8",
        )
        output = self.root / "auto-low-score-ambiguous"

        metadata = preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunk = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        )

        self.assertEqual("REVIEW", metadata["scene_routing_status"])
        self.assertEqual("AMBIGUOUS", chunk["scene_routing_decision"])
        self.assertEqual({"COURSE": 2, "MODELING": 0, "RESEARCH": 2}, chunk["scene_routing_scores"])
        self.assertEqual("UNRESOLVED", chunk["status"])

    def test_protected_only_ambiguous_heading_does_not_create_false_unresolved_gap(self) -> None:
        source = self.root / "protected-ambiguous.md"
        source.write_text(
            "# 模型建立与研究方法\n> 本研究建立状态变量模型。\n\n"
            "# 背景\n普通作者正文。\n",
            encoding="utf-8",
        )
        output = self.root / "protected-ambiguous-run"

        metadata = preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual("READY", metadata["status"])
        self.assertEqual("PASS", metadata["scene_routing_status"])
        self.assertEqual(0, chunks[0]["author_chars"])
        self.assertEqual("SKIPPED_PROTECTED", chunks[0]["status"])

    def test_document_prior_only_completes_aligned_weak_unit(self) -> None:
        source = self.root / "course-prior.md"
        source.write_text(
            "# 例题一\n本题先辨认条件，再代入公式。\n\n"
            "# 例题二\n本题需要先判断方向，再核对答案。\n\n"
            "# 小结\n本题最后核对方向。\n",
            encoding="utf-8",
        )
        output = self.root / "course-prior-run"

        preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual("COURSE", chunks[-1]["scene"])
        self.assertEqual("ROUTED", chunks[-1]["scene_routing_decision"])
        self.assertEqual("COURSE", chunks[-1]["scene_document_prior"])

    def test_neutral_unit_does_not_inherit_unrelated_document_prior(self) -> None:
        source = self.root / "model-with-neutral-background.md"
        source.write_text(
            "# 模型建立\n建立状态变量并设置参数，随后进行数值求解。\n\n"
            "# 背景\n该段保留原有范围说明。\n",
            encoding="utf-8",
        )
        output = self.root / "neutral-prior-run"

        preparer.prepare([source], output, scene="AUTO", min_author_chars=0)
        chunks = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (output / "chunks").glob("*.json")
            ),
            key=lambda item: item["start"],
        )

        self.assertEqual("MODELING", chunks[0]["scene"])
        self.assertEqual("GENERAL", chunks[1]["scene"])
        self.assertEqual("FALLBACK_GENERAL", chunks[1]["scene_routing_decision"])
        self.assertEqual("MODELING", chunks[1]["scene_document_prior"])

    def test_include_graph_shares_document_prior_without_overriding_local_evidence(self) -> None:
        main = self.root / "main.tex"
        model = self.root / "model.tex"
        appendix = self.root / "appendix.tex"
        main.write_text("\\input{model}\n\\input{appendix}\n", encoding="utf-8")
        model.write_text(
            "\\section{模型建立}\n建立状态变量并设置参数，随后进行数值求解。\n",
            encoding="utf-8",
        )
        appendix.write_text(
            "\\section{附录小结}\n参数设置沿用前文。\n",
            encoding="utf-8",
        )
        output = self.root / "include-prior-run"

        preparer.prepare([main], output, scene="AUTO", min_author_chars=0)
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        appendix_chunk = next(item for item in chunks if "参数设置沿用前文" in item["masked_text"])

        self.assertEqual("MODELING", appendix_chunk["scene"])
        self.assertEqual("ROUTED", appendix_chunk["scene_routing_decision"])
        self.assertEqual("MODELING", appendix_chunk["scene_document_prior"])

    def test_markdown_percentage_does_not_mask_following_author_prose(self) -> None:
        source = self.root / "percentage.md"
        source.write_text(
            "# 结果\n相对误差为 16.47%。两类结果需要分开报告。\n",
            encoding="utf-8",
        )
        output = self.root / "run"

        preparer.prepare([source], output, scene="RESEARCH", min_author_chars=0)

        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        self.assertEqual(1, len(chunks))
        self.assertIn("16.47%", chunks[0]["masked_text"])
        self.assertIn("需要分开报告", chunks[0]["masked_text"])
        self.assertNotIn("latex-comment", chunks[0]["masked_text"])

    def test_protected_only_scope_is_review_before_finalize(self) -> None:
        source = self.root / "protected-only.tex"
        source.write_text("\\section{标题}\n\\label{eq:x}\n\\[x=1\\]\n", encoding="utf-8")
        output = self.root / "run"

        metadata = preparer.prepare([source], output, scene="RESEARCH", min_author_chars=0)

        self.assertEqual("REVIEW", metadata["status"])
        self.assertEqual(0, metadata["processable_editable_units"])
        self.assertTrue(metadata["no_editable_scope"])
        self.assertIn("No editable author-text units", metadata["next_action"])
        self.assertNotIn("Rewrite only PENDING", metadata["next_action"])

    def test_adjacent_units_have_read_only_context_and_unique_owners(self) -> None:
        source = self.root / "two.md"
        source.write_text(
            "# 第一节\n第一节作者正文，用于前文衔接。\n\n"
            "# 第二节\n第二节作者正文，用于后文衔接。\n",
            encoding="utf-8",
        )
        output = self.root / "run"
        preparer.prepare([source], output, scene="GENERAL", min_author_chars=0)
        chunks = sorted(
            (json.loads(path.read_text(encoding="utf-8")) for path in (output / "chunks").glob("*.json")),
            key=lambda item: item["start"],
        )
        owners = [item["owner_chunk"] for item in chunks]
        self.assertEqual(len(owners), len(set(owners)))
        self.assertEqual(chunks[1]["unit_id"], chunks[0]["context_after_unit"])
        self.assertEqual(chunks[0]["unit_id"], chunks[1]["context_before_unit"])
        self.assertIn("第二节作者正文", chunks[0]["read_only_context_after"])
        self.assertIn("第一节作者正文", chunks[1]["read_only_context_before"])

    def test_cli_outputs_all_audit_artifacts(self) -> None:
        source = self.root / "sample.md"
        source.write_text("# 标题\n正文需要处理。\n", encoding="utf-8")
        output = self.root / "run"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(source),
                "--output",
                str(output),
                "--scene",
                "general",
                "--min-author-chars",
                "0",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        for name in (
            "snapshot.json",
            "file_manifest.csv",
            "coverage_ledger.csv",
            "units.jsonl",
            "protected_spans.jsonl",
            "run_metadata.json",
            "structural_transaction_inventory.json",
            "prepare_integrity.json",
        ):
            self.assertTrue((output / name).is_file(), name)

    def test_cli_help_and_error_explain_chunk_budget_bounds(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, help_result.returncode)
        self.assertIn("必须 >= 1000", help_result.stdout)
        self.assertIn("必须 >= 50", help_result.stdout)
        self.assertIn("必须 >= 0", help_result.stdout)

        source = self.root / "invalid-budget.md"
        source.write_text("正文。\n", encoding="utf-8")
        invalid = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(source),
                "--output",
                str(self.root / "invalid-budget-run"),
                "--max-author-chars",
                "350",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, invalid.returncode)
        self.assertIn("--max-author-chars must be >= 1000", invalid.stderr)

    def test_cli_accepts_adjacent_pair_only_with_structural_intensity(self) -> None:
        source = self.root / "cli-transaction.md"
        source.write_text("# 标题\n正文需要处理。\n", encoding="utf-8")
        output = self.root / "cli-structural-run"

        accepted = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(source),
                "--output",
                str(output),
                "--scene",
                "general",
                "--intensity",
                "structural",
                "--structural-transaction-scope",
                "adjacent_pair",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual(
            "ADJACENT_PAIR",
            json.loads(accepted.stdout)["structural_transaction_scope"],
        )
        self.assertEqual(
            "EMPTY",
            json.loads(
                (output / "structural_transaction_inventory.json").read_text(
                    encoding="utf-8"
                )
            )["status"],
        )
        self.assertTrue(
            json.loads(
                (output / "structural_transaction_inventory.json").read_text(
                    encoding="utf-8"
                )
            )["scope_authorization"]["mechanical_scope_permission_granted"]
        )

        rejected_output = self.root / "cli-balanced-run"
        rejected = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(source),
                "--output",
                str(rejected_output),
                "--intensity",
                "balanced",
                "--structural-transaction-scope",
                "adjacent_pair",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(1, rejected.returncode)
        rejected_payload = json.loads(rejected.stdout)
        self.assertEqual("FAIL", rejected_payload["delivery_gate_status"])
        self.assertEqual("INPUT_CONTRACT_INVALID", rejected_payload["error_code"])
        self.assertEqual("", rejected.stderr)
        self.assertFalse(rejected_output.exists())


if __name__ == "__main__":
    unittest.main()
