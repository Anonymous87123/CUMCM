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
AUTHORING_PATH = SKILL / "scripts" / "scaffold_humanize_short_patch.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


authoring = load_module("short_patch_span_suggestion_test", AUTHORING_PATH)


class HumanizeShortPatchSpanSuggestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(
        self,
        text: str,
        *,
        mode: str = "SENTENCE",
        suffix: str = ".md",
        newline: str | None = None,
    ) -> tuple[Path, Path, dict]:
        source = self.root / f"source{suffix}"
        if newline is None:
            source.write_text(text, encoding="utf-8", newline="")
        else:
            source.write_text(text, encoding="utf-8", newline=newline)
        output = self.root / f"selection-{mode.lower()}.authoring.json"
        payload = authoring.create_scaffold(
            source,
            output,
            requested_output="PATCH",
            scene="GENERAL",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode=mode,
        )
        return source, output, payload

    @staticmethod
    def available(payload: dict, kind: str | None = None) -> list[dict]:
        return [
            item
            for item in payload["span_suggestions"]
            if item["status"] == "AVAILABLE"
            and (kind is None or item["kind"] == kind)
        ]

    @staticmethod
    def suppressed(payload: dict, kind: str | None = None) -> list[dict]:
        return [
            item
            for item in payload["span_suggestions"]
            if item["status"] == "SUPPRESSED"
            and (kind is None or item["kind"] == kind)
        ]

    @staticmethod
    def write_payload(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_create_v2_offers_one_source_bound_sentence_for_multiple_highs(self) -> None:
        sentence = (
            "值得注意的是，本文系统梳理了相关现象，"
            "这个结论具有重要意义，为后续研究奠定基础。"
        )
        source, path, payload = self.create(sentence + "\n")

        self.assertEqual(
            "humanize-short-patch-selection-authoring/v4",
            payload["schema_version"],
        )
        self.assertEqual("SENTENCE", payload["configuration"]["span_suggestion_mode"])
        self.assertIn("authoring_tool_sha256", payload["policy_hashes"])
        sentence_suggestions = self.available(payload, "SENTENCE")
        self.assertEqual(1, len(sentence_suggestions))
        suggestion = sentence_suggestions[0]
        candidate_ids = {
            item["finding_id"]
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE"
        }
        self.assertEqual(candidate_ids, set(suggestion["finding_ids"]))
        span = next(
            item for item in payload["spans"] if item["span_id"] == suggestion["span_id"]
        )
        self.assertEqual([], span["finding_ids"])
        self.assertEqual(sentence, span["source_text"])
        raw = source.read_bytes()
        self.assertEqual(
            sentence.encode("utf-8"),
            raw[suggestion["start_byte"] : suggestion["end_byte"]],
        )
        serialized = path.read_text(encoding="utf-8")
        self.assertEqual(1, serialized.count(sentence))

    def test_suggestions_never_author_decisions_or_claim_authority(self) -> None:
        _source, _path, payload = self.create("值得注意的是，先核对条件。\n")
        self.assertEqual([], payload["hunks"])
        self.assertEqual([], payload["selected_spans"])
        self.assertEqual([], payload["explicit_conflicts"])
        self.assertTrue(
            all(item["decision"] == "PENDING" for item in payload["lexical_resolutions"])
        )
        forbidden = {
            "replacement",
            "reason",
            "decision",
            "hunk_id",
            "selection_id",
            "conflict_id",
            "authorized",
        }
        for suggestion in payload["span_suggestions"]:
            self.assertTrue(forbidden.isdisjoint(suggestion))
        self.assertFalse(payload["span_suggestion_policy"]["decision_authority"])
        self.assertEqual(
            "CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY",
            payload["authoring_integrity_scope"],
        )
        self.assertFalse(payload["completion_claim_allowed"])
        self.assertFalse(payload["humanize_quality_claim_allowed"])

    def test_sentence_and_paragraph_overlapping_protected_content_are_suppressed(self) -> None:
        text = "值得注意的是，结果写为 $E=mc^2$，并保留“原始引语”。\n"
        _source, _path, payload = self.create(
            text, mode="SENTENCE_AND_PARAGRAPH", suffix=".tex"
        )
        candidate_ids = {
            item["finding_id"]
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE"
        }
        self.assertTrue(candidate_ids)
        self.assertEqual([], self.available(payload))
        suppressed = self.suppressed(payload)
        self.assertEqual({"SENTENCE", "PARAGRAPH"}, {item["kind"] for item in suppressed})
        self.assertTrue(
            all("PROTECTED_SPAN_OVERLAP" in item["reason_codes"] for item in suppressed)
        )
        suggestion_span_ids = {
            item["span_id"] for item in payload["span_suggestions"] if item["span_id"]
        }
        self.assertFalse(suggestion_span_ids)

    def test_non_candidate_protected_high_never_receives_suggestion(self) -> None:
        _source, _path, payload = self.create("“值得注意的是”是被锁定的引语。\n")
        protected_ids = {
            item["finding_id"]
            for item in payload["high_findings"]
            if item["role"] == "PROTECTED"
        }
        self.assertTrue(protected_ids)
        suggested_ids = {
            finding_id
            for item in payload["span_suggestions"]
            for finding_id in item["finding_ids"]
        }
        self.assertTrue(protected_ids.isdisjoint(suggested_ids))

    def test_crlf_suggestion_offsets_preserve_exact_source_bytes(self) -> None:
        source, _path, payload = self.create(
            "第一行。\n值得注意的是，先核对条件。\n第三行。\n",
            newline="\r\n",
        )
        raw = source.read_bytes()
        suggestion = self.available(payload, "SENTENCE")[0]
        span = next(
            item for item in payload["spans"] if item["span_id"] == suggestion["span_id"]
        )
        selected = raw[suggestion["start_byte"] : suggestion["end_byte"]]
        self.assertEqual(span["source_text"].encode("utf-8"), selected)
        self.assertFalse(
            suggestion["start_byte"] > 0
            and raw[suggestion["start_byte"] - 1 : suggestion["start_byte"] + 1]
            == b"\r\n"
        )
        self.assertFalse(
            suggestion["end_byte"] < len(raw)
            and raw[suggestion["end_byte"] - 1 : suggestion["end_byte"] + 1]
            == b"\r\n"
        )

    def test_finalize_accepts_explicit_hunk_reference_to_suggested_sentence(self) -> None:
        source, draft, payload = self.create("值得注意的是，先核对条件。\n")
        suggestion = self.available(payload, "SENTENCE")[0]
        candidate_ids = [
            item["finding_id"]
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE"
        ]
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": suggestion["span_id"],
                "decision": "REWRITE",
                "replacement": "先核对条件。",
                "reason": "删除空重点提示壳，同时保留原句已有的核对动作。",
            }
        ]
        for resolution in payload["lexical_resolutions"]:
            self.assertIn(resolution["finding_id"], candidate_ids)
            resolution.update({"decision": "HUNK", "hunk_id": "H001", "reason": None})
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": suggestion["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方明确把该建议句界选入本次最小 PATCH。",
            }
        ]
        self.write_payload(draft, payload)
        selection = authoring.finalize_scaffold(
            source, draft, self.root / "selection.v2.json"
        )
        self.assertEqual("值得注意的是，先核对条件。", selection["hunks"][0]["source_text"])
        self.assertEqual(
            selection["hunks"][0]["source_text"],
            selection["coverage"]["selected_spans"][0]["source_text"],
        )

    def test_finalize_rejects_tampered_suggestion_or_missing_registry_span(self) -> None:
        source, draft, payload = self.create("值得注意的是，先核对条件。\n")
        payload["span_suggestions"][0]["start_byte"] += 1
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "SPAN_SUGGESTION_DRIFT"):
            authoring.finalize_scaffold(
                source, draft, self.root / "tampered-selection.json"
            )

        source, draft, payload = self.create(
            "值得注意的是，先核对条件。\n", mode="PARAGRAPH"
        )
        suggestion = self.available(payload, "PARAGRAPH")[0]
        payload["spans"] = [
            item for item in payload["spans"] if item["span_id"] != suggestion["span_id"]
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "SUGGESTION_SPAN_MISSING"):
            authoring.finalize_scaffold(
                source, draft, self.root / "missing-selection.json"
            )

    def test_none_mode_produces_no_suggestions_and_cli_defaults_to_sentence(self) -> None:
        _source, _draft, payload = self.create(
            "值得注意的是，先核对条件。\n", mode="NONE"
        )
        self.assertEqual([], payload["span_suggestions"])
        self.assertEqual("NONE", payload["span_suggestion_policy"]["mode"])

        source = self.root / "cli.md"
        source.write_text("值得注意的是，先核对条件。\n", encoding="utf-8")
        output = self.root / "cli.authoring.json"
        process = subprocess.run(
            [
                sys.executable,
                str(AUTHORING_PATH),
                "create",
                str(source),
                "--scene",
                "GENERAL",
                "--source-kind",
                "DOCUMENT",
                "--output",
                str(output),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        cli_payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            "CLAUSE_AND_SENTENCE",
            cli_payload["configuration"]["span_suggestion_mode"],
        )
        self.assertGreaterEqual(len(self.available(cli_payload, "CLAUSE")), 1)
        self.assertGreaterEqual(len(self.available(cli_payload, "SENTENCE")), 1)

    def test_default_mode_offers_clause_and_full_sentence_for_real_research_shell(self) -> None:
        text = (
            "值得注意的是，本文系统梳理了相关现象，并深入探讨了可能原因，"
            "为后续研究奠定基础。\n"
        )
        source = self.root / "default-research.md"
        source.write_text(text, encoding="utf-8")
        payload = authoring.create_scaffold(
            source,
            self.root / "default-research.authoring.json",
            requested_output="PATCH",
            scene="RESEARCH",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
        )
        self.assertEqual(
            "CLAUSE_AND_SENTENCE",
            payload["configuration"]["span_suggestion_mode"],
        )
        spans = {item["span_id"]: item["source_text"] for item in payload["spans"]}
        offered = {
            spans[item["span_id"]]
            for item in self.available(payload)
        }
        self.assertEqual(
            {"CLAUSE", "SENTENCE"},
            {item["kind"] for item in self.available(payload)},
        )
        self.assertIn("值得注意的是，", offered)
        self.assertIn(text.strip(), offered)

    def test_available_suggestions_fully_cover_every_bound_finding(self) -> None:
        _source, _path, payload = self.create(
            "形成证据；分析闭环。\n", mode="CLAUSE_AND_SENTENCE"
        )
        findings = {
            item["finding_id"]: item
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE"
        }
        self.assertTrue(findings)
        self.assertEqual([], self.available(payload))
        suppressed = self.suppressed(payload)
        self.assertEqual({"CLAUSE", "SENTENCE"}, {item["kind"] for item in suppressed})
        for suggestion in suppressed:
            self.assertIn("FINDING_NOT_FULLY_COVERED", suggestion["reason_codes"])
        for suggestion in self.available(payload):
            for finding_id in suggestion["finding_ids"]:
                finding = findings[finding_id]
                self.assertLessEqual(suggestion["start_byte"], finding["start_byte"])
                self.assertGreaterEqual(suggestion["end_byte"], finding["end_byte"])

    def test_tex_command_arguments_suppress_all_overlapping_suggestions(self) -> None:
        cases = [
            "\\textbf{标签，值得注意的是，结论}。\n",
            "\\cmd[标签，值得注意的是]{结论}。\n",
            "\\outer{\\inner{标签，值得注意的是，结论}}。\n",
        ]
        case_number = 0
        for suffix in (".tex", ".md"):
            for text in cases:
                case_number += 1
                with self.subTest(suffix=suffix, text=text):
                    source = self.root / f"tex-command-{case_number}{suffix}"
                    source.write_text(text, encoding="utf-8")
                    output = self.root / f"tex-command-{case_number}.authoring.json"
                    payload = authoring.create_scaffold(
                        source,
                        output,
                        requested_output="PATCH",
                        scene="GENERAL",
                        intensity="BALANCED",
                        source_kind="DOCUMENT",
                        protected_terms=[],
                        span_suggestion_mode="CLAUSE_AND_SENTENCE",
                    )
                    self.assertTrue(
                        any(
                            item["role"] == "CANDIDATE"
                            for item in payload["high_findings"]
                        )
                    )
                    self.assertEqual([], self.available(payload))
                    self.assertTrue(self.suppressed(payload))
                    self.assertTrue(
                        all(
                            "TEX_CONTROL_SEQUENCE_OVERLAP" in item["reason_codes"]
                            for item in self.suppressed(payload)
                        )
                    )

    def test_tex_comment_between_command_and_argument_preserves_protection(self) -> None:
        _source, _path, payload = self.create(
            "\\textbf% keep\n{标签，值得注意的是，结论}。\n",
            mode="CLAUSE_AND_SENTENCE",
            suffix=".tex",
        )
        self.assertEqual([], self.available(payload))
        self.assertTrue(self.suppressed(payload))
        self.assertTrue(
            all(
                "TEX_CONTROL_SEQUENCE_OVERLAP" in item["reason_codes"]
                for item in self.suppressed(payload)
            )
        )

    def test_finalize_rejects_manual_hunk_inside_tex_command_argument(self) -> None:
        source, draft, payload = self.create(
            "\\textbf% keep\n{标签，值得注意的是，结论}。\n",
            mode="NONE",
            suffix=".tex",
        )
        finding = next(
            item for item in payload["high_findings"] if item["role"] == "CANDIDATE"
        )
        span = next(
            item
            for item in payload["spans"]
            if finding["finding_id"] in item["finding_ids"]
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": span["span_id"],
                "decision": "DELETE_STYLE_SHELL",
                "replacement": "",
                "reason": "尝试删除 TeX 命令参数中的空重点提示壳。",
            }
        ]
        payload["lexical_resolutions"][0].update(
            {"decision": "HUNK", "hunk_id": "H001", "reason": None}
        )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": span["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方将该参数内跨度列入最小 PATCH。",
            }
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(
            authoring.AuthoringError, "HUNK_OVERLAPS_PROTECTED_SPAN"
        ):
            authoring.finalize_scaffold(
                source, draft, self.root / "tex-command-argument.selection.json"
            )

    def test_default_deduplicates_identical_ranges_across_views(self) -> None:
        _source, _path, payload = self.create(
            "值得注意的是；\n", mode="CLAUSE_AND_SENTENCE"
        )
        ranges = [
            (item["start_byte"], item["end_byte"])
            for item in self.available(payload)
        ]
        self.assertEqual(len(ranges), len(set(ranges)))

    def test_finalize_rejects_overlapping_selected_boundaries(self) -> None:
        source, draft, payload = self.create(
            "值得注意的是，先核对条件。这个结论具有重要意义。\n",
            mode="ALL",
        )
        spans = {item["span_id"]: item for item in payload["spans"]}
        clause = next(
            item
            for item in self.available(payload, "CLAUSE")
            if spans[item["span_id"]]["source_text"] == "值得注意的是，"
        )
        sentence = next(
            item
            for item in self.available(payload, "SENTENCE")
            if spans[item["span_id"]]["source_text"] == "值得注意的是，先核对条件。"
        )
        target_finding = next(
            item
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE" and item["source_text"] == "具有重要意义"
        )
        target_span = next(
            item
            for item in payload["spans"]
            if target_finding["finding_id"] in item["finding_ids"]
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": target_span["span_id"],
                "decision": "DELETE_STYLE_SHELL",
                "replacement": "",
                "reason": "删除没有具体对象或后果支撑的泛化意义判断。",
            }
        ]
        for resolution in payload["lexical_resolutions"]:
            if resolution["finding_id"] == target_finding["finding_id"]:
                resolution.update(
                    {"decision": "HUNK", "hunk_id": "H001", "reason": None}
                )
            else:
                resolution.update(
                    {
                        "decision": "KEEP",
                        "hunk_id": None,
                        "reason": "该教学提醒明确要求先核对条件，本次保留其约束作用。",
                    }
                )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": clause["span_id"],
                "decision": "KEEP",
                "hunk_id": None,
                "reason": "调用方把局部提示壳边界列入复核并决定保留。",
            },
            {
                "selection_id": "S002",
                "span_id": sentence["span_id"],
                "decision": "KEEP",
                "hunk_id": None,
                "reason": "调用方又把包含前一边界的整句列入复核。",
            },
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "SELECTED_SPANS_OVERLAP"):
            authoring.finalize_scaffold(
                source, draft, self.root / "overlapping-selected.selection.json"
            )

    def test_api_auto_format_is_consistent_across_create_finalize_and_build(self) -> None:
        source = self.root / "api-auto.md"
        source.write_text("值得注意的是，先核对条件。\n", encoding="utf-8")
        draft = self.root / "api-auto.authoring.json"
        payload = authoring.create_scaffold(
            source,
            draft,
            requested_output="PATCH",
            scene="GENERAL",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            document_format="AUTO",
        )
        self.assertEqual("markdown", payload["source"]["document_format"])
        suggestion = next(
            item
            for item in self.available(payload, "CLAUSE")
            if item["boundary_variant"] == "RIGHT_DELIMITER"
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": suggestion["span_id"],
                "decision": "DELETE_STYLE_SHELL",
                "replacement": "",
                "reason": "删除空重点提示壳并保留核对条件的动作。",
            }
        ]
        for resolution in payload["lexical_resolutions"]:
            resolution.update(
                {"decision": "HUNK", "hunk_id": "H001", "reason": None}
            )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": suggestion["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方把该提示壳边界列入本次 PATCH。",
            }
        ]
        self.write_payload(draft, payload)
        selection_path = self.root / "api-auto.selection.json"
        selection = authoring.finalize_scaffold(
            source, draft, selection_path, document_format="auto"
        )
        self.assertEqual(
            "humanize-short-patch-selection/v2", selection["schema_version"]
        )
        bundle = authoring.short_patch.build_bundle(
            source,
            selection_path,
            self.root / "api-auto.bundle.json",
            document_format="AUTO",
        )
        self.assertEqual("markdown", bundle["document_format"])

    def test_clause_suggestions_cover_real_research_shell_boundaries(self) -> None:
        text = (
            "这个结果说明参数变化会影响系统表现，也具有重要意义。"
            "值得注意的是，本文系统梳理了相关现象，并深入探讨了可能原因，"
            "为后续研究奠定基础。\n"
        )
        _source, _path, payload = self.create(text, mode="CLAUSE")
        spans = {item["span_id"]: item["source_text"] for item in payload["spans"]}
        offered = {
            spans[item["span_id"]]
            for item in self.available(payload, "CLAUSE")
        }
        self.assertIn("，也具有重要意义", offered)
        self.assertIn("值得注意的是，", offered)
        self.assertIn("，为后续研究奠定基础", offered)
        self.assertTrue(
            all(
                item["boundary_variant"]
                in {"CORE", "LEFT_DELIMITER", "RIGHT_DELIMITER"}
                for item in self.available(payload, "CLAUSE")
            )
        )

    def test_v40_non_high_candidate_gets_advisory_boundary_suggestions(self) -> None:
        _source, _path, payload = self.create(
            "表格的作用也在于让读者看出每个参数来自哪条事实链。\n",
            mode="CLAUSE_AND_SENTENCE",
        )

        self.assertEqual([], payload["high_findings"])
        suggestions = self.available(payload)
        self.assertTrue(suggestions)
        self.assertTrue(all(item["finding_ids"] == [] for item in suggestions))
        self.assertTrue(
            any(
                "ADVISORY_NON_HIGH_SIGNAL:medium:LEX-TABLE-ROLE-01"
                in item["reason_codes"]
                for item in suggestions
            )
        )

    def test_v41_focus_is_additive_to_scanner_suggestions(self) -> None:
        source = self.root / "additive-focus.md"
        source.write_text(
            "值得注意的是，先核对条件。这里补充说明一个局部理由。\n",
            encoding="utf-8",
        )
        focus_spec = self.root / "additive-focus.json"
        focus_spec.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-short-patch-focus/v1",
                    "spans": [
                        {
                            "focus_id": "F001",
                            "source_text": "这里补充说明",
                            "start_byte": None,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        payload = authoring.create_scaffold(
            source,
            self.root / "additive-focus.authoring.json",
            requested_output="PATCH",
            scene="GENERAL",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="CLAUSE_AND_SENTENCE",
            focus_spec_path=focus_spec,
        )

        self.assertTrue(
            any(item["role"] == "CANDIDATE" for item in payload["high_findings"])
        )
        self.assertTrue(self.available(payload, "CLAUSE"))
        self.assertTrue(self.available(payload, "SENTENCE"))
        focus = self.available(payload, "FOCUS")
        self.assertEqual(1, len(focus))
        self.assertEqual([], focus[0]["finding_ids"])
        self.assertIn("CALLER_DIAGNOSIS_REQUIRED", focus[0]["reason_codes"])

    def test_v40_advisory_suggestion_finalizes_without_becoming_high_coverage(self) -> None:
        source, authoring_path, payload = self.create(
            "表格的作用也在于让读者看出每个参数来自哪条事实链。\n",
            mode="CLAUSE_AND_SENTENCE",
        )
        suggestion = self.available(payload, "SENTENCE")[0]
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": suggestion["span_id"],
                "decision": "REWRITE",
                "replacement": "表格让每个参数的事实来源更容易辨认。",
                "reason": "压缩表格功能的后台说明，保留读者辨认参数来源这一作用。",
            }
        ]
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": suggestion["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方将该表格功能句列入本次最小 PATCH。",
            }
        ]
        self.write_payload(authoring_path, payload)

        selection = authoring.finalize_scaffold(
            source,
            authoring_path,
            self.root / "advisory.selection.json",
        )

        self.assertEqual([], selection["coverage"]["lexical_keeps"])
        self.assertEqual(1, len(selection["coverage"]["selected_spans"]))
        self.assertEqual(1, len(selection["hunks"]))

    def test_v40_focus_spec_registers_exact_unprotected_span(self) -> None:
        source = self.root / "focus-source.tex"
        source.write_text(
            "\\section{标题}\n为了看清 $x$，现在代入 $y$。\n",
            encoding="utf-8",
        )
        focus_spec = self.root / "focus.json"
        focus_spec.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-short-patch-focus/v1",
                    "spans": [
                        {
                            "focus_id": "F001",
                            "source_text": "为了看清 ",
                            "start_byte": None,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = self.root / "focus.authoring.json"

        payload = authoring.create_scaffold(
            source,
            output,
            requested_output="PATCH",
            scene="COURSE",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="FOCUS",
            focus_spec_path=focus_spec,
        )

        self.assertEqual([], payload["high_findings"])
        self.assertEqual(1, len(payload["focus_spans"]))
        suggestions = self.available(payload, "FOCUS")
        self.assertEqual(1, len(suggestions))
        suggestion = suggestions[0]
        self.assertEqual("EXACT", suggestion["boundary_variant"])
        self.assertEqual([], suggestion["finding_ids"])
        self.assertIn("CALLER_DIAGNOSIS_REQUIRED", suggestion["reason_codes"])
        raw = source.read_bytes()
        self.assertEqual(
            "为了看清 ",
            raw[suggestion["start_byte"] : suggestion["end_byte"]].decode("utf-8"),
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": suggestion["span_id"],
                "decision": "REWRITE",
                "replacement": "为观察 ",
                "reason": "压缩公式推导前的主持语，只保留观察目标。",
            }
        ]
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": suggestion["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方将该精确讲解主持语列入本次 PATCH。",
            }
        ]
        self.write_payload(output, payload)
        selection = authoring.finalize_scaffold(
            source,
            output,
            self.root / "focus.selection.json",
        )
        self.assertEqual(1, len(selection["hunks"]))
        self.assertEqual(1, len(selection["coverage"]["selected_spans"]))

    def test_v40_focus_spec_suppresses_protected_span_and_rejects_ambiguity(self) -> None:
        source = self.root / "focus-protected.tex"
        source.write_text("这里保留 $x$。这里再说明。\n", encoding="utf-8")
        protected_spec = self.root / "focus-protected.json"
        protected_spec.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-short-patch-focus/v1",
                    "spans": [
                        {"focus_id": "F001", "source_text": "$x$", "start_byte": None}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        protected_payload = authoring.create_scaffold(
            source,
            self.root / "focus-protected.authoring.json",
            requested_output="PATCH",
            scene="COURSE",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="FOCUS",
            focus_spec_path=protected_spec,
        )
        suppressed = self.suppressed(protected_payload, "FOCUS")
        self.assertEqual(1, len(suppressed))
        self.assertIsNone(suppressed[0]["span_id"])
        self.assertIn("PROTECTED_SPAN_OVERLAP", suppressed[0]["reason_codes"])

        ambiguous_spec = self.root / "focus-ambiguous.json"
        ambiguous_spec.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-short-patch-focus/v1",
                    "spans": [
                        {"focus_id": "F001", "source_text": "这里", "start_byte": None}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(authoring.AuthoringError, "ambiguous"):
            authoring.create_scaffold(
                source,
                self.root / "focus-ambiguous.authoring.json",
                requested_output="PATCH",
                scene="COURSE",
                intensity="BALANCED",
                source_kind="DOCUMENT",
                protected_terms=[],
                span_suggestion_mode="FOCUS",
                focus_spec_path=ambiguous_spec,
            )

    def test_txt_can_explicitly_use_tex_protection_grammar(self) -> None:
        source = self.root / "source.txt"
        source.write_text(
            "% 值得注意的是，注释。\n值得注意的是，正文。\n",
            encoding="utf-8",
        )
        output = self.root / "tex-in-txt.authoring.json"
        payload = authoring.create_scaffold(
            source,
            output,
            requested_output="PATCH",
            scene="GENERAL",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="CLAUSE",
            document_format="tex",
        )
        self.assertEqual("tex", payload["source"]["document_format"])
        self.assertTrue(payload["high_findings"])
        self.assertEqual(
            {"PROTECTED", "CANDIDATE"},
            {item["role"] for item in payload["high_findings"]},
        )
        suggestion = next(
            item
            for item in self.available(payload, "CLAUSE")
            if item["boundary_variant"] == "RIGHT_DELIMITER"
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": suggestion["span_id"],
                "decision": "DELETE_STYLE_SHELL",
                "replacement": "",
                "reason": "删除作者正文中的空重点提示壳，不触碰上一行 TeX 注释。",
            }
        ]
        for resolution in payload["lexical_resolutions"]:
            resolution.update(
                {"decision": "HUNK", "hunk_id": "H001", "reason": None}
            )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": suggestion["span_id"],
                "decision": "HUNK",
                "hunk_id": "H001",
                "reason": "调用方把作者正文中的提示壳列入本次 PATCH。",
            }
        ]
        self.write_payload(output, payload)
        selection_path = self.root / "tex-in-txt.selection.json"
        authoring.finalize_scaffold(
            source,
            output,
            selection_path,
            document_format="tex",
        )
        bundle = authoring.short_patch.build_bundle(
            source,
            selection_path,
            self.root / "tex-in-txt.bundle.json",
            document_format="tex",
        )
        self.assertEqual("tex", bundle["coverage"]["source"]["document_format"])

    def test_all_mode_emits_clause_sentence_and_paragraph_views(self) -> None:
        _source, _path, payload = self.create(
            "值得注意的是，先核对条件。第二句保留原样。\n", mode="ALL"
        )
        kinds = {item["kind"] for item in self.available(payload)}
        self.assertEqual({"CLAUSE", "SENTENCE", "PARAGRAPH"}, kinds)
        ranges = [
            (item["start_byte"], item["end_byte"])
            for item in self.available(payload)
        ]
        self.assertEqual(len(ranges), len(set(ranges)))

    def test_oversize_sentence_is_audited_as_suppressed(self) -> None:
        text = "值得注意的是，" + ("甲" * 1300) + "。\n"
        _source, _path, payload = self.create(text, mode="SENTENCE")
        self.assertEqual([], self.available(payload, "SENTENCE"))
        suppressed = self.suppressed(payload, "SENTENCE")
        self.assertEqual(1, len(suppressed))
        self.assertIn("SPAN_TOO_LARGE", suppressed[0]["reason_codes"])

    def test_tex_control_sequence_suppresses_broad_sentence_suggestion(self) -> None:
        _source, _path, payload = self.create(
            "值得注意的是，\\textbf{先核对条件}。\n",
            mode="SENTENCE",
            suffix=".tex",
        )
        self.assertEqual([], self.available(payload, "SENTENCE"))
        suppressed = self.suppressed(payload, "SENTENCE")
        self.assertEqual(1, len(suppressed))
        self.assertIn("TEX_CONTROL_SEQUENCE_OVERLAP", suppressed[0]["reason_codes"])


if __name__ == "__main__":
    unittest.main()
