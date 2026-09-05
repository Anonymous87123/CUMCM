import importlib.util
import hashlib
import json
import os
import re
import sys
import unittest
from pathlib import Path


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = load_module(
    "audit_humanize_repetition_guards_contract",
    SKILL / "scripts" / "audit_humanize_repetition_guards.py",
)


class HumanizeRepetitionGuardTests(unittest.TestCase):
    @staticmethod
    def record(
        unit_id: str,
        before: str,
        after: str,
        *,
        document_id: str = "DOC-01",
        scene: str = "RESEARCH",
        document_format: str = "markdown",
        heading_path: str = "结果 / 执行清单",
        protected_structure_tokens: dict | None = None,
    ) -> dict:
        record = {
            "unit_id": unit_id,
            "document_id": document_id,
            "resolved_scene": scene,
            "format": document_format,
            "suffix": ".tex" if document_format == "tex" else ".md",
            "heading_path": heading_path,
            "before_masked": before,
            "after_masked": after,
        }
        if protected_structure_tokens is not None:
            record["protected_structure_tokens"] = protected_structure_tokens
        return record

    @staticmethod
    def regex_guard(guard_id: str = "NEGATIVE-REGEX-TEST") -> dict:
        return {
            "id": guard_id,
            "scene": "ALL",
            "status": "AVAILABLE",
            "detector": {
                "type": "regex_groups/v1",
                "minimum_groups": 1,
                "pattern_groups": [
                    {
                        "id": "shell",
                        "regex": "这里只",
                        "minimum_occurrences": 2,
                    }
                ],
            },
        }

    @staticmethod
    def structured_guard(guard_id: str = "NEGATIVE-STRUCTURED-TEST") -> dict:
        return {
            "id": guard_id,
            "scene": "ALL",
            "status": "AVAILABLE",
            "detector": {
                "type": "structured_repeated_list/v1",
                "block_role": {"heading_leaf_regex": "总结|执行清单"},
                "thresholds": {
                    "minimum_blocks": 3,
                    "minimum_items_per_block": 3,
                },
                "shared_anchor": {
                    "mode": "MAXIMAL_HAN_NGRAM",
                    "minimum_han_chars": 4,
                    "maximum_han_chars": 8,
                    "minimum_block_coverage": 3,
                },
            },
        }

    @staticmethod
    def markdown_list(anchor: str, variant: str) -> str:
        return "\n".join(
            [
                "# 执行清单",
                f"- {anchor}：核对{variant}条件",
                f"- {anchor}：复算{variant}数据",
                f"- {anchor}：记录{variant}结论",
            ]
        )

    @staticmethod
    def tex_list(anchor: str, variant: str) -> str:
        return "\n".join(
            [
                r"\begin{itemize}",
                rf"\item {anchor}：核对{variant}条件",
                rf"\item {anchor}：复算{variant}数据",
                rf"\item {anchor}：记录{variant}结论",
                r"\end{itemize}",
            ]
        )

    @staticmethod
    def assert_fingerprint(test: unittest.TestCase, finding: dict) -> None:
        fingerprint = finding.get("finding_fingerprint")
        test.assertIsInstance(fingerprint, str)
        test.assertRegex(fingerprint, re.compile(r"^[0-9a-f]{64}$"))

    def test_regex_guard_blocks_the_unique_introducing_unit(self) -> None:
        records = [
            self.record("U-01", "这里只讨论基线。", "这里只讨论基线。"),
            self.record("U-02", "该段讨论误差。", "这里只讨论误差。"),
        ]

        result = audit.audit_negative_guards(records, [self.regex_guard()])

        self.assertEqual(["U-02"], result["blocking_unit_ids"])
        self.assertEqual(1, len(result["findings"]))
        finding = result["findings"][0]
        self.assertEqual("UNIQUE_MINIMAL_REVERT_SET", finding["attribution_status"])
        self.assertEqual(["U-02"], finding["introduced_unit_ids"])
        self.assertEqual(2, finding["after_groups"][0]["occurrences"])
        self.assert_fingerprint(self, finding)

    def test_regex_cannot_match_across_a_protected_placeholder(self) -> None:
        protected = "[[PROTECTED:P-001:0123456789ab]]"
        records = [
            self.record("U-01", "普通基线。", "这里只讨论基线。"),
            self.record("U-02", "普通误差。", f"这里{protected}只讨论误差。"),
        ]

        result = audit.audit_negative_guards(records, [self.regex_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_markdown_structured_guard_detects_three_qualified_blocks(self) -> None:
        records = [
            self.record(
                f"U-{index:02d}",
                f"第{index}段基线。",
                self.markdown_list("共同校验步骤", variant),
            )
            for index, variant in enumerate(("甲", "乙", "丙"), 1)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(1, len(result["findings"]))
        finding = result["findings"][0]
        self.assertEqual(3, finding["after"]["qualified_block_count"])
        self.assertTrue(finding["after"]["shared_anchors"])
        self.assertEqual("AMBIGUOUS_MINIMAL_REVERT_SETS", finding["attribution_status"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assert_fingerprint(self, finding)

    def test_markdown_nested_items_do_not_satisfy_the_item_threshold(self) -> None:
        nested = "\n".join(
            [
                "# 执行清单",
                "- 共同校验步骤：外层甲项",
                "  - 共同校验步骤：内层补项",
                "- 共同校验步骤：外层乙项",
                "  1. 共同校验步骤：内层复核",
            ]
        )
        records = [
            self.record(f"U-{index:02d}", "普通基线。", nested)
            for index in range(1, 4)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_three_markdown_blocks_in_one_unit_remain_distinct(self) -> None:
        after = "\n\n".join(
            self.markdown_list("共同校验步骤", variant)
            for variant in ("甲", "乙", "丙")
        )
        records = [self.record("U-01", "普通基线。", after)]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(1, len(result["findings"]))
        finding = result["findings"][0]
        self.assertEqual(3, finding["after"]["qualified_block_count"])
        block_ids = [
            block["block_id"] for block in finding["after"]["qualified_blocks"]
        ]
        self.assertEqual(3, len(set(block_ids)))
        self.assertEqual(["U-01"], result["blocking_unit_ids"])

    def test_raw_tex_itemize_and_enumerate_are_parsed(self) -> None:
        records = [
            self.record(
                "U-01",
                "普通基线。",
                self.tex_list("共同校验步骤", "甲"),
                document_format="tex",
            ),
            self.record(
                "U-02",
                "普通基线。",
                self.tex_list("共同校验步骤", "乙").replace(
                    "itemize", "enumerate"
                ),
                document_format="tex",
            ),
            self.record(
                "U-03",
                "普通基线。",
                self.tex_list("共同校验步骤", "丙"),
                document_format="tex",
            ),
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(1, len(result["findings"]))
        blocks = result["findings"][0]["after"]["qualified_blocks"]
        self.assertEqual(3, len(blocks))
        self.assertEqual({"tex"}, {block["format"] for block in blocks})

    def test_raw_tex_source_headings_are_authenticated_and_payloads_stay_masked(self) -> None:
        records = []
        for index, variant in enumerate(("甲", "乙", "丙"), 1):
            after = "\n".join(
                [
                    rf"\section*[SHORT_TITLE_SECRET]{{执行清单 $HEADING_MATH_SECRET$}}",
                    r"\begin {itemize} [label=BEGIN_OPTION_SECRET]",
                    rf"\item[ITEM_LABEL_SECRET] 共同校验步骤核对{variant}条件",
                    rf"\item 共同校验步骤复算{variant}数据 \secret{{COMMAND_ARG_SECRET}}",
                    rf"\item 共同校验步骤记录{variant}结论",
                    r"\end {itemize}",
                ]
            )
            records.append(
                self.record(
                    f"U-{index:02d}",
                    "普通基线。",
                    after,
                    document_format="tex",
                    heading_path="",
                )
            )

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(1, len(result["findings"]))
        evidence = json.dumps(result["findings"][0], ensure_ascii=False)
        for protected_payload in (
            "SHORT_TITLE_SECRET",
            "HEADING_MATH_SECRET",
            "BEGIN_OPTION_SECRET",
            "ITEM_LABEL_SECRET",
            "COMMAND_ARG_SECRET",
        ):
            self.assertNotIn(protected_payload, evidence)

    def test_heading_like_commands_inside_verbatim_do_not_set_block_role(self) -> None:
        records = []
        for index, variant in enumerate(("甲", "乙", "丙"), 1):
            after = "\n".join(
                [
                    r"\begin{verbatim}",
                    r"\section{执行清单}",
                    r"\end{verbatim}",
                    self.tex_list("共同校验步骤", variant),
                ]
            )
            records.append(
                self.record(
                    f"U-{index:02d}",
                    "普通基线。",
                    after,
                    document_format="tex",
                    heading_path="",
                )
            )

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])

    def test_nonrendering_tex_environments_cannot_authenticate_headings_or_lists(self) -> None:
        detector = self.structured_guard()["detector"]
        for environment in ("comment", "filecontents", "filecontents*"):
            with self.subTest(environment=environment):
                hidden_blocks = []
                for variant in ("甲", "乙", "丙"):
                    hidden_blocks.extend(
                        [
                            rf"\begin{{{environment}}}{{hidden-{variant}.tex}}"
                            if environment.startswith("filecontents")
                            else rf"\begin{{{environment}}}",
                            r"\section{执行清单}",
                            self.tex_list("共同校验步骤", variant),
                            rf"\end{{{environment}}}",
                        ]
                    )
                text = "\n".join(
                    [*hidden_blocks, r"\section{真实标题}", "可见正文。"]
                )

                self.assertEqual(
                    ["真实标题"],
                    [
                        item["heading_leaf"]
                        for item in audit.authenticated_tex_headings(text)
                    ],
                )
                result = audit.evaluate_detector_snapshot(
                    {
                        "unit_id": "U-01",
                        "document_id": "DOC-01",
                        "resolved_scene": "RESEARCH",
                        "format": "tex",
                        "heading_path": "",
                        "text": text,
                    },
                    detector,
                )
                self.assertFalse(result["triggered"])
                self.assertEqual(0, result["qualified_block_count"])

    def test_heading_inside_outer_tex_argument_does_not_set_block_role(self) -> None:
        records = []
        for index, variant in enumerate(("甲", "乙", "丙"), 1):
            after = "\n".join(
                [
                    r"\outer{",
                    r"\section{执行清单}",
                    r"}",
                    self.tex_list("共同校验步骤", variant),
                ]
            )
            records.append(
                self.record(
                    f"U-{index:02d}",
                    "普通基线。",
                    after,
                    document_format="tex",
                    heading_path="",
                )
            )

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])

    def test_shared_text_only_in_tex_labels_and_arguments_is_not_an_anchor(self) -> None:
        records = []
        unique_items = (
            ("甲辰天地", "乙巳山河", "丙午星月"),
            ("丁未江海", "戊申风雨", "己酉晨昏"),
            ("庚戌草木", "辛亥经纬", "壬子寒暑"),
        )
        for index, items in enumerate(unique_items, 1):
            after = "\n".join(
                [
                    r"\section{执行清单}",
                    r"\begin{enumerate}[label=共同校验步骤]",
                    rf"\item[共同校验步骤] {items[0]}",
                    rf"\item {items[1]} \secret{{共同校验步骤}}",
                    rf"\item {items[2]} $共同校验步骤$",
                    r"\end{enumerate}",
                ]
            )
            record = self.record(
                f"U-{index:02d}",
                "普通基线。",
                after,
                document_format="tex",
                heading_path="",
            )
            records.append(record)
            blocks = audit._structured_blocks(record, "after_masked")
            self.assertNotIn(
                "共同校验步骤", json.dumps(blocks, ensure_ascii=False)
            )

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])

    def test_raw_tex_balanced_list_arguments_and_item_star_are_parsed(self) -> None:
        cases = {
            "nested-square": (
                r"\begin{enumerate}[label={[\alph*]}]",
                r"\item[tag={[x]}]",
            ),
            "multiline": (
                "\\begin{enumerate}[label=\n(\\alph*)]",
                "\\item[tag=\n{x}]",
            ),
            "comment-separated": (
                "\\begin{enumerate}% option follows\n[label=(\\alph*)]",
                "\\item% label follows\n[tag]",
            ),
            "star-prefix": (r"\begin{enumerate}", r"\item*"),
        }
        detector = self.structured_guard()["detector"]
        for label, (begin, item) in cases.items():
            with self.subTest(label=label):
                text = "\n".join(
                    "\n".join(
                        [begin]
                        + [
                            f"{item} 共同校验步骤：核对{variant}条件",
                            f"{item} 共同校验步骤：复算{variant}数据",
                            f"{item} 共同校验步骤：记录{variant}结论",
                        ]
                        + [r"\end{enumerate}"]
                    )
                    for variant in ("甲", "乙", "丙")
                )
                result = audit.evaluate_detector_snapshot(
                    {
                        "unit_id": "U-01",
                        "document_id": "DOC-01",
                        "resolved_scene": "RESEARCH",
                        "format": "tex",
                        "heading_path": "执行清单",
                        "text": text,
                    },
                    detector,
                )
                self.assertTrue(result["triggered"])
                self.assertEqual(3, result["qualified_block_count"])

    def test_tex_item_command_prefixes_and_unclosed_label_fail_safely(self) -> None:
        for command in (r"\itemize", r"\item@fake"):
            with self.subTest(command=command):
                text = "\n".join(
                    [r"\begin{enumerate}"]
                    + [f"{command} 共同校验步骤" for _ in range(3)]
                    + [r"\end{enumerate}"]
                )
                blocks = audit._tex_list_blocks(
                    {"unit_id": "U-01", "format": "tex", "heading_path": "执行清单"},
                    text,
                )
                self.assertEqual([], blocks)

        malformed = "\n".join(
            [r"\begin{enumerate}"]
            + [r"\item[共同校验步骤" for _ in range(3)]
            + [r"\end{enumerate}"]
        )
        with self.assertRaisesRegex(
            audit.DetectorEvaluationReview,
            "optional argument is unbalanced",
        ):
            audit._tex_list_blocks(
                {"unit_id": "U-01", "format": "tex", "heading_path": "执行清单"},
                malformed,
            )

    def test_authenticated_tex_headings_support_balanced_commands_and_labels(self) -> None:
        self.assertEqual([], audit.authenticated_tex_headings(""))
        headings = {
            "nested-title-command": r"\section{执行清单 \custom{不进入角色}}",
            "nested-title-label": r"\section{执行清单\label{inside}}",
            "space-before-group": r"\section {执行清单}",
            "trailing-label-comment": r"\section{执行清单} \label{outside}% note",
        }
        detector = self.structured_guard()["detector"]
        for label, heading in headings.items():
            with self.subTest(label=label):
                text = "\n".join(
                    [heading]
                    + [self.tex_list("共同校验步骤", variant) for variant in ("甲", "乙", "丙")]
                )
                result = audit.evaluate_detector_snapshot(
                    {
                        "unit_id": "U-01",
                        "document_id": "DOC-01",
                        "resolved_scene": "RESEARCH",
                        "format": "tex",
                        "heading_path": "",
                        "text": text,
                    },
                    detector,
                )
                self.assertTrue(result["triggered"])
                self.assertEqual(3, result["qualified_block_count"])
                evidence = json.dumps(result, ensure_ascii=False)
                self.assertNotIn("不进入角色", evidence)
                self.assertNotIn("inside", evidence)
                self.assertNotIn("outside", evidence)
                authenticated = audit.authenticated_tex_headings(text)
                self.assertEqual(
                    ["执行清单"],
                    [item["heading_leaf"] for item in authenticated],
                )
                self.assertEqual(
                    ["section"],
                    [item["level"] for item in authenticated],
                )
                self.assertTrue(
                    all(item["line_start"] <= item["start"] for item in authenticated)
                )
                self.assertTrue(
                    all(item["end"] <= item["line_end"] for item in authenticated)
                )

    def test_visible_tex_heading_wrappers_preserve_role_and_detector_semantics(self) -> None:
        headings = [
            r"\section{摘要}",
            r"\section{\textbf{摘要}}",
            r"\section{\emph{\textit{摘要}}}",
        ]
        self.assertEqual(
            ["摘要", "摘要", "摘要"],
            [
                item["heading_leaf"]
                for item in audit.authenticated_tex_headings("\n".join(headings))
            ],
        )
        mixed = audit.authenticated_tex_headings(
            r"\section{前言 \textbf{模型建立}}"
        )
        self.assertEqual("前言 模型建立", mixed[0]["heading_leaf"])

        detector = self.structured_guard()["detector"]
        detector["block_role"]["heading_leaf_regex"] = r"^摘要$"
        results = []
        for heading in (headings[0], headings[1]):
            text = "\n".join(
                [heading]
                + [
                    self.tex_list("共同校验步骤", variant)
                    for variant in ("甲", "乙", "丙")
                ]
            )
            results.append(
                audit.evaluate_detector_snapshot(
                    {
                        "unit_id": "U-01",
                        "document_id": "DOC-01",
                        "resolved_scene": "RESEARCH",
                        "format": "tex",
                        "heading_path": "",
                        "text": text,
                    },
                    detector,
                )
            )
        self.assertEqual(
            [(True, 3), (True, 3)],
            [
                (result["triggered"], result["qualified_block_count"])
                for result in results
            ],
        )

    def test_authenticated_tex_headings_keep_opaque_boundaries_and_exact_arity(self) -> None:
        payload_free = [
            r"\section{}",
            r"\section{$E=mc^2$}",
            r"\section{``Quoted''}",
            r"\section{\LaTeX}",
            r"\section{\custom{HiddenSummary}}",
        ]
        text = "\n".join(payload_free)
        authenticated = audit.authenticated_tex_headings(text)

        self.assertEqual(len(payload_free), len(authenticated))
        leaves = [str(item["heading_leaf"]) for item in authenticated]
        self.assertEqual(len(leaves), len(set(leaves)))
        self.assertTrue(
            all(
                leaf.startswith("(tex-section-title-line-")
                and "-offset-" in leaf
                for leaf in leaves
            )
        )
        evidence = json.dumps(authenticated, ensure_ascii=False)
        for payload in ("HiddenSummary", "E=mc^2", "Quoted", "LaTeX"):
            self.assertNotIn(payload, evidence)

        same_line = r"\section{Summary} editable prose"
        same_line_heading = audit.authenticated_tex_headings(same_line)[0]
        self.assertEqual(len(r"\section{Summary}"), same_line_heading["end"])

        consecutive_group = r"\section{Intro}{editable group}"
        consecutive_heading = audit.authenticated_tex_headings(consecutive_group)[0]
        self.assertEqual(len(r"\section{Intro}"), consecutive_heading["end"])

    def test_tex_heading_analysis_fails_closed_on_unsupported_static_syntax(self) -> None:
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
                analysis = audit.analyze_tex_headings(text)
                self.assertEqual([], analysis["headings"])
                self.assertTrue(
                    any(problem.startswith(problem_code + ":") for problem in analysis["problems"])
                )
                self.assertTrue(analysis["malformed_spans"])
                self.assertEqual(len(text), analysis["malformed_spans"][0]["end"])
                with self.assertRaisesRegex(
                    audit.DetectorEvaluationReview,
                    problem_code,
                ):
                    audit._tex_heading_leaves_by_line(
                        text,
                        protected_spans=[],
                        command_spans=[],
                    )

    def test_raw_tex_nested_items_do_not_satisfy_the_item_threshold(self) -> None:
        nested = "\n".join(
            [
                r"\begin{itemize}",
                r"\item 共同校验步骤：外层甲项",
                r"\begin{enumerate}",
                r"\item 共同校验步骤：内层补项",
                r"\end{enumerate}",
                r"\item 共同校验步骤：外层乙项",
                r"\end{itemize}",
            ]
        )
        records = [
            self.record(
                f"U-{index:02d}",
                "普通基线。",
                nested,
                document_format="tex",
            )
            for index in range(1, 4)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_protected_placeholder_breaks_a_structured_shared_anchor(self) -> None:
        protected = "[[PROTECTED:P-001:0123456789ab]]"
        unique_items = (
            ("甲辰天地", "乙巳山河", "丙午星月"),
            ("丁未江海", "戊申风雨", "己酉晨昏"),
            ("庚戌草木", "辛亥经纬", "壬子寒暑"),
        )
        records = []
        for index, tails in enumerate(unique_items, 1):
            after = "\n".join(
                ["# 执行清单"]
                + [f"- 共同{protected}锚点{tail}" for tail in tails]
            )
            records.append(self.record(f"U-{index:02d}", "普通基线。", after))

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_scene_partitions_cannot_be_combined(self) -> None:
        records = [
            self.record(
                "U-01",
                "普通基线。",
                self.markdown_list("共同校验步骤", "甲"),
                scene="RESEARCH",
            ),
            self.record(
                "U-02",
                "普通基线。",
                self.markdown_list("共同校验步骤", "乙"),
                scene="RESEARCH",
            ),
            self.record(
                "U-03",
                "普通基线。",
                self.markdown_list("共同校验步骤", "丙"),
                scene="MODELING",
            ),
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_document_partitions_cannot_be_combined(self) -> None:
        records = [
            self.record(
                "U-01",
                "普通基线。",
                self.markdown_list("共同校验步骤", "甲"),
                document_id="DOC-A",
            ),
            self.record(
                "U-02",
                "普通基线。",
                self.markdown_list("共同校验步骤", "乙"),
                document_id="DOC-A",
            ),
            self.record(
                "U-03",
                "普通基线。",
                self.markdown_list("共同校验步骤", "丙"),
                document_id="DOC-B",
            ),
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])

    def test_missing_partition_metadata_fails_closed_without_default_grouping(self) -> None:
        for missing in ("document_id", "resolved_scene"):
            with self.subTest(missing=missing):
                record = self.record("U-01", "普通基线。", "普通基线。")
                record.pop(missing)

                result = audit.audit_negative_guards(
                    [record], [self.structured_guard()]
                )

                self.assertEqual([], result["findings"])
                self.assertEqual([], result["blocking_unit_ids"])
                self.assertEqual(1, len(result["review_reasons"]))
                self.assertTrue(
                    result["review_reasons"][0].startswith(
                        "NEGATIVE_GUARD_PARTITION_METADATA_REVIEW:"
                    )
                )

    def test_snapshot_evaluator_requires_explicit_partition_metadata(self) -> None:
        snapshot = {
            "unit_id": "U-01",
            "document_id": "DOC-01",
            "resolved_scene": "RESEARCH",
            "format": "markdown",
            "heading_path": "执行清单",
            "text": self.markdown_list("共同校验步骤", "甲"),
        }
        for missing in ("document_id", "resolved_scene"):
            with self.subTest(missing=missing):
                invalid = dict(snapshot)
                invalid.pop(missing)
                with self.assertRaises(audit.DetectorEvaluationReview):
                    audit.evaluate_detector_snapshot(
                        invalid, self.structured_guard()["detector"]
                    )

    def test_partition_requires_resolved_scene_even_when_legacy_scene_exists(self) -> None:
        record = self.record("U-01", "普通基线。", "普通基线。")
        record["scene"] = record.pop("resolved_scene")

        result = audit.audit_negative_guards([record], [self.regex_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual(
            [
                "NEGATIVE_GUARD_PARTITION_METADATA_REVIEW:"
                "PARTITION_RESOLVED_SCENE_MISSING"
            ],
            result["review_reasons"],
        )

    def test_partition_rejects_invalid_or_conflicting_resolved_scene(self) -> None:
        cases = (
            ("", None, "PARTITION_RESOLVED_SCENE_MISSING"),
            ("UNKNOWN", None, "PARTITION_RESOLVED_SCENE_INVALID"),
            ("RESEARCH", "MODELING", "PARTITION_SCENE_CONFLICT"),
        )
        for resolved_scene, compatibility_scene, reason in cases:
            with self.subTest(reason=reason):
                record = self.record("U-01", "普通基线。", "普通基线。")
                record["resolved_scene"] = resolved_scene
                if compatibility_scene is not None:
                    record["scene"] = compatibility_scene

                result = audit.audit_negative_guards([record], [self.regex_guard()])

                self.assertEqual(
                    [f"NEGATIVE_GUARD_PARTITION_METADATA_REVIEW:{reason}"],
                    result["review_reasons"],
                )

    def test_matching_compatibility_scene_is_accepted(self) -> None:
        records = [
            self.record("U-01", "这里只讨论基线。", "这里只讨论基线。"),
            self.record("U-02", "普通误差。", "这里只讨论误差。"),
        ]
        for record in records:
            record["scene"] = "research"

        result = audit.audit_negative_guards(records, [self.regex_guard()])

        self.assertEqual(["U-02"], result["blocking_unit_ids"])
        self.assertEqual([], result["review_reasons"])

    def test_inherited_trigger_is_audited_without_blocking(self) -> None:
        paragraphs = [
            self.markdown_list("共同校验步骤", variant)
            for variant in ("甲", "乙", "丙")
        ]
        records = [
            self.record(f"U-{index:02d}", paragraph, paragraph)
            for index, paragraph in enumerate(paragraphs, 1)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertEqual(1, len(result["inherited_findings"]))
        inherited = result["inherited_findings"][0]
        self.assertEqual("INHERITED_BEFORE_THRESHOLD", inherited["attribution_status"])
        self.assert_fingerprint(self, inherited)

    def test_structured_unique_minimal_revert_set_blocks_only_new_unit(self) -> None:
        first = self.markdown_list("共同校验步骤", "甲")
        second = self.markdown_list("共同校验步骤", "乙")
        third = self.markdown_list("共同校验步骤", "丙")
        records = [
            self.record("U-01", first, first),
            self.record("U-02", second, second),
            self.record("U-03", "普通基线。", third),
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(["U-03"], result["blocking_unit_ids"])
        finding = result["findings"][0]
        self.assertEqual("UNIQUE_MINIMAL_REVERT_SET", finding["attribution_status"])
        self.assertEqual(["U-03"], finding["introduced_unit_ids"])
        self.assertEqual(1, finding["minimal_revert_set_count"])

    def test_structured_ambiguous_minimal_revert_sets_require_review(self) -> None:
        records = [
            self.record(
                f"U-{index:02d}",
                f"第{index}段基线。",
                self.markdown_list("共同校验步骤", variant),
            )
            for index, variant in enumerate(("甲", "乙", "丙"), 1)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        finding = result["findings"][0]
        self.assertEqual("AMBIGUOUS_MINIMAL_REVERT_SETS", finding["attribution_status"])
        self.assertEqual([], finding["introduced_unit_ids"])
        self.assertGreaterEqual(finding["minimal_revert_set_count"], 2)
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertTrue(
            any(
                reason.startswith(
                    "NEGATIVE_GUARD_ATTRIBUTION_AMBIGUOUS_MINIMAL_REVERT_SETS:"
                )
                for reason in result["review_reasons"]
            )
        )

    def test_definition_hash_and_fingerprints_are_replay_stable(self) -> None:
        regex_records = [
            self.record(
                "R-01",
                "这里只讨论基线。",
                "这里只讨论基线。",
                document_id="DOC-REGEX",
            ),
            self.record(
                "R-02",
                "普通误差。",
                "这里只讨论误差。",
                document_id="DOC-REGEX",
            ),
        ]
        structured_records = [
            self.record(
                f"S-{index:02d}",
                f"第{index}段基线。",
                self.markdown_list("共同校验步骤", variant),
                document_id="DOC-LIST",
            )
            for index, variant in enumerate(("甲", "乙", "丙"), 1)
        ]
        records = regex_records + structured_records
        guards = [self.regex_guard(), self.structured_guard()]

        first = audit.audit_negative_guards(records, guards)
        replay = audit.audit_negative_guards(list(reversed(records)), list(reversed(guards)))

        self.assertEqual(
            first["active_detector_definition_sha256"],
            replay["active_detector_definition_sha256"],
        )
        self.assertEqual(2, len(first["active_detector_definition_sha256"]))
        independently_recomputed_detector_hashes = sorted(
            hashlib.sha256(
                json.dumps(
                    guard["detector"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            for guard in guards
        )
        self.assertEqual(
            independently_recomputed_detector_hashes,
            first["active_detector_definition_sha256"],
        )
        for digest in first["active_detector_definition_sha256"]:
            self.assertRegex(digest, re.compile(r"^[0-9a-f]{64}$"))

        def fingerprints(result: dict) -> dict[tuple[str, str], str]:
            return {
                (finding["card_id"], finding["document_id"]): finding[
                    "finding_fingerprint"
                ]
                for finding in result["findings"]
            }

        self.assertEqual(fingerprints(first), fingerprints(replay))
        self.assertTrue(fingerprints(first))
        for fingerprint in fingerprints(first).values():
            self.assertRegex(fingerprint, re.compile(r"^[0-9a-f]{64}$"))
        for finding in first["findings"]:
            fingerprint_payload = {
                key: value
                for key, value in finding.items()
                if key != "finding_fingerprint"
            }
            independently_recomputed_fingerprint = hashlib.sha256(
                json.dumps(
                    fingerprint_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(
                independently_recomputed_fingerprint,
                finding["finding_fingerprint"],
            )

    @staticmethod
    def masked_tex_record(unit_id: str, variant: str) -> dict:
        prefix = unit_id.replace("U-", "")
        ids = {
            "begin": f"P-{prefix}-BEGIN",
            "item_1": f"P-{prefix}-ITEM-1",
            "item_2": f"P-{prefix}-ITEM-2",
            "item_3": f"P-{prefix}-ITEM-3",
            "end": f"P-{prefix}-END",
        }
        hashes = {
            key: f"{index:012x}"
            for index, key in enumerate(ids, 1)
        }

        def placeholder(key: str) -> str:
            return f"[[PROTECTED:{ids[key]}:{hashes[key]}]]"

        baseline_by_variant = {
            "甲": ("甲辰天地", "乙巳山河", "丙午星月"),
            "乙": ("丁未江海", "戊申风雨", "己酉晨昏"),
            "丙": ("庚戌草木", "辛亥经纬", "壬子寒暑"),
        }
        before = "\n".join(
            [placeholder("begin")]
            + [
                f"{placeholder(f'item_{index}')} {tail}"
                for index, tail in enumerate(baseline_by_variant[variant], 1)
            ]
            + [placeholder("end")]
        )
        after = "\n".join(
            [
                placeholder("begin"),
                f"{placeholder('item_1')} 共同校验步骤：核对{variant}条件",
                f"{placeholder('item_2')} 共同校验步骤：复算{variant}数据",
                f"{placeholder('item_3')} 共同校验步骤：记录{variant}结论",
                placeholder("end"),
            ]
        )
        tokens = {
            ids["begin"]: {"kind": "LIST_BEGIN", "list_kind": "itemize"},
            ids["item_1"]: {"kind": "LIST_ITEM"},
            ids["item_2"]: {"kind": "LIST_ITEM"},
            ids["item_3"]: {"kind": "LIST_ITEM"},
            ids["end"]: {"kind": "LIST_END", "list_kind": "itemize"},
        }
        return HumanizeRepetitionGuardTests.record(
            unit_id,
            before,
            after,
            document_format="tex",
            protected_structure_tokens=tokens,
        )

    def test_masked_tex_structure_side_channel_recovers_list_blocks(self) -> None:
        records = [
            self.masked_tex_record(f"U-{index:02d}", variant)
            for index, variant in enumerate(("甲", "乙", "丙"), 1)
        ]

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual(1, len(result["findings"]))
        finding = result["findings"][0]
        self.assertEqual(3, finding["after"]["qualified_block_count"])
        self.assertTrue(finding["after"]["shared_anchors"])
        self.assertEqual(
            "AMBIGUOUS_MINIMAL_REVERT_SETS", finding["attribution_status"]
        )
        self.assertTrue(
            any(
                reason.startswith(
                    "NEGATIVE_GUARD_ATTRIBUTION_AMBIGUOUS_MINIMAL_REVERT_SETS:"
                )
                for reason in result["review_reasons"]
            )
        )

    def test_masked_tex_nested_side_channel_items_are_not_counted(self) -> None:
        records = []
        for index in range(1, 4):
            prefix = f"P-{index:02d}"
            placeholder = lambda name, number: (  # noqa: E731
                f"[[PROTECTED:{prefix}-{name}:{number:012x}]]"
            )
            after = "\n".join(
                [
                    placeholder("OUTER-BEGIN", 1),
                    f"{placeholder('OUTER-ITEM-1', 2)} 共同校验步骤：外层甲项",
                    placeholder("INNER-BEGIN", 3),
                    f"{placeholder('INNER-ITEM', 4)} 共同校验步骤：内层补项",
                    placeholder("INNER-END", 5),
                    f"{placeholder('OUTER-ITEM-2', 6)} 共同校验步骤：外层乙项",
                    placeholder("OUTER-END", 7),
                ]
            )
            tokens = {
                f"{prefix}-OUTER-BEGIN": {
                    "kind": "LIST_BEGIN",
                    "list_kind": "itemize",
                },
                f"{prefix}-OUTER-ITEM-1": {"kind": "LIST_ITEM"},
                f"{prefix}-INNER-BEGIN": {
                    "kind": "LIST_BEGIN",
                    "list_kind": "enumerate",
                },
                f"{prefix}-INNER-ITEM": {"kind": "LIST_ITEM"},
                f"{prefix}-INNER-END": {
                    "kind": "LIST_END",
                    "list_kind": "enumerate",
                },
                f"{prefix}-OUTER-ITEM-2": {"kind": "LIST_ITEM"},
                f"{prefix}-OUTER-END": {
                    "kind": "LIST_END",
                    "list_kind": "itemize",
                },
            }
            records.append(
                self.record(
                    f"U-{index:02d}",
                    after,
                    after,
                    document_format="tex",
                    protected_structure_tokens=tokens,
                )
            )

        result = audit.audit_negative_guards(records, [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertEqual([], result["review_reasons"])

    def test_unknown_masked_tex_structure_id_fails_closed_to_review(self) -> None:
        protected = "[[PROTECTED:P-UNKNOWN:0123456789ab]]"
        record = self.record(
            "U-01",
            f"{protected}\n共同校验步骤。",
            f"{protected}\n共同校验步骤。",
            document_format="tex",
            protected_structure_tokens={
                "P-KNOWN": {"kind": "LIST_BEGIN", "list_kind": "itemize"}
            },
        )

        result = audit.audit_negative_guards([record], [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertTrue(result["review_reasons"])

    def test_invalid_masked_tex_structure_token_fails_closed_to_review(self) -> None:
        protected = "[[PROTECTED:P-INVALID:0123456789ab]]"
        record = self.record(
            "U-01",
            f"{protected}\n共同校验步骤。",
            f"{protected}\n共同校验步骤。",
            document_format="tex",
            protected_structure_tokens={
                "P-INVALID": {"kind": "RAW_TEX", "payload": r"\begin{itemize}"}
            },
        )

        result = audit.audit_negative_guards([record], [self.structured_guard()])

        self.assertEqual([], result["findings"])
        self.assertEqual([], result["blocking_unit_ids"])
        self.assertTrue(result["review_reasons"])


if __name__ == "__main__":
    unittest.main()
