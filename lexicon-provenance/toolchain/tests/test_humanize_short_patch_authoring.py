import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
AUTHORING_PATH = SKILL / "scripts" / "scaffold_humanize_short_patch.py"
BUILDER_PATH = SKILL / "scripts" / "build_humanize_short_patch.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("authoring_test_builder", BUILDER_PATH)
authoring = load_module("scaffold_humanize_short_patch", AUTHORING_PATH)


class HumanizeShortPatchAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.tex"
        self.source_text = (
            "值得注意的是，先读题。\n"
            "若条件冲突，保留原句。\n"
            "这个结论具有重要意义。\n"
        )
        self.source.write_text(self.source_text, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(self, name: str = "selection.authoring.json") -> tuple[Path, dict]:
        output = self.root / name
        payload = authoring.create_scaffold(
            self.source,
            output,
            requested_output="PATCH",
            scene="COURSE",
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="NONE",
        )
        return output, payload

    @staticmethod
    def resolve_all_high_with_hunks(payload: dict) -> None:
        span_by_finding = {
            finding_id: span["span_id"]
            for span in payload["spans"]
            for finding_id in span["finding_ids"]
        }
        for index, resolution in enumerate(payload["lexical_resolutions"], start=1):
            hunk_id = f"H{index:03d}"
            resolution.update(
                {"decision": "HUNK", "hunk_id": hunk_id, "reason": None}
            )
            payload["hunks"].append(
                {
                    "hunk_id": hunk_id,
                    "span_id": span_by_finding[resolution["finding_id"]],
                    "decision": "DELETE_STYLE_SHELL",
                    "replacement": "",
                    "reason": "删除该处未增加对象或判断条件的高风险句壳。",
                }
            )

    def write_payload(self, path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_create_scaffold_freezes_source_policy_and_all_auto_high(self) -> None:
        path, payload = self.create()
        self.assertEqual("humanize-short-patch-selection-authoring/v4", payload["schema_version"])
        self.assertEqual(builder.sha256(self.source.read_bytes()), payload["source"]["sha256"])
        self.assertEqual("tex", payload["source"]["document_format"])
        self.assertEqual("AUTO", payload["source"]["scan_scene"])
        self.assertEqual("COURSE", payload["configuration"]["requested_scene"])
        self.assertEqual("COURSE", payload["configuration"]["resolved_scene"])
        self.assertEqual("EXPLICIT", payload["scene_route"]["status"])
        self.assertEqual("USER_EXPLICIT_SCENE", payload["scene_route"]["reason_code"])
        self.assertTrue(payload["scene_route"]["authoring_allowed"])
        self.assertEqual(
            payload["source"]["sha256"], payload["scene_route"]["source_sha256"]
        )
        self.assertEqual("DOCUMENT", payload["configuration"]["source_kind"])
        self.assertEqual(authoring.current_policy_hashes(), payload["policy_hashes"])
        self.assertEqual("NONE", payload["configuration"]["span_suggestion_mode"])
        self.assertEqual([], payload["span_suggestions"])
        self.assertGreaterEqual(len(payload["high_findings"]), 2)
        candidate_ids = {
            item["finding_id"]
            for item in payload["high_findings"]
            if item["role"] == "CANDIDATE"
        }
        self.assertEqual(
            candidate_ids,
            {item["finding_id"] for item in payload["lexical_resolutions"]},
        )
        self.assertTrue(
            all(item["decision"] == "PENDING" for item in payload["lexical_resolutions"])
        )
        self.assertEqual(
            len(payload["high_findings"]),
            sum(len(span["finding_ids"]) for span in payload["spans"]),
        )
        self.assertEqual(payload, json.loads(path.read_text(encoding="utf-8")))
        self.assertFalse(payload["completion_claim_allowed"])

    def test_finalize_expands_single_span_registry_to_strict_v2_selection(self) -> None:
        draft_path, payload = self.create()
        self.resolve_all_high_with_hunks(payload)
        first_hunk = payload["hunks"][0]
        payload["selected_spans"].append(
            {
                "selection_id": "S001",
                "span_id": first_hunk["span_id"],
                "decision": "HUNK",
                "hunk_id": first_hunk["hunk_id"],
                "reason": "用户把该精确 span 列入本次处理范围。",
            }
        )
        self.write_payload(draft_path, payload)
        selection_path = self.root / "selection.v2.json"
        selection = authoring.finalize_scaffold(
            self.source, draft_path, selection_path
        )

        self.assertEqual("humanize-short-patch-selection/v2", selection["schema_version"])
        self.assertNotIn("spans", selection)
        self.assertNotIn("lexical_resolutions", selection)
        self.assertEqual(
            selection["hunks"][0]["source_text"],
            selection["coverage"]["selected_spans"][0]["source_text"],
        )
        self.assertEqual(
            selection["hunks"][0]["start_byte"],
            selection["coverage"]["selected_spans"][0]["start_byte"],
        )
        bundle = builder._build_payload(
            self.source.read_bytes(),
            selection_path.read_bytes(),
            selection,
            document_format="tex",
        )
        self.assertEqual("humanize-short-patch/v2", bundle["schema_version"])
        self.assertEqual("PASS", bundle["coverage"]["mechanical_coverage_status"])

    def test_finalize_rejects_pending_source_drift_and_policy_drift(self) -> None:
        draft_path, payload = self.create()
        with self.assertRaisesRegex(authoring.AuthoringError, "PENDING"):
            authoring.finalize_scaffold(
                self.source, draft_path, self.root / "pending-selection.json"
            )

        self.resolve_all_high_with_hunks(payload)
        payload["policy_hashes"]["scanner_sha256"] = "0" * 64
        self.write_payload(draft_path, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "POLICY_DRIFT"):
            authoring.finalize_scaffold(
                self.source, draft_path, self.root / "drift-selection.json"
            )

        payload["policy_hashes"] = authoring.current_policy_hashes()
        self.write_payload(draft_path, payload)
        self.source.write_text(self.source_text + "追加文本。\n", encoding="utf-8")
        with self.assertRaisesRegex(authoring.AuthoringError, "SOURCE_DRIFT"):
            authoring.finalize_scaffold(
                self.source, draft_path, self.root / "source-drift-selection.json"
            )

    def test_finalize_rejects_dangling_duplicate_and_mismatched_references(self) -> None:
        draft_path, payload = self.create()
        self.resolve_all_high_with_hunks(payload)
        payload["hunks"][0]["span_id"] = "MISSING"
        self.write_payload(draft_path, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "span_id"):
            authoring.finalize_scaffold(
                self.source, draft_path, self.root / "dangling-selection.json"
            )

        _new_path, payload = self.create("selection-duplicate.authoring.json")
        duplicate_path = self.root / "selection-duplicate.authoring.json"
        self.resolve_all_high_with_hunks(payload)
        payload["spans"].append(dict(payload["spans"][0]))
        self.write_payload(duplicate_path, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "duplicate span_id"):
            authoring.finalize_scaffold(
                self.source, duplicate_path, self.root / "duplicate-selection.json"
            )

        _mismatch_path, payload = self.create("selection-mismatch.authoring.json")
        mismatch_path = self.root / "selection-mismatch.authoring.json"
        self.resolve_all_high_with_hunks(payload)
        payload["selected_spans"].append(
            {
                "selection_id": "S001",
                "span_id": payload["hunks"][1]["span_id"],
                "decision": "HUNK",
                "hunk_id": payload["hunks"][0]["hunk_id"],
                "reason": "错误地把另一 span 绑定到首个 hunk。",
            }
        )
        self.write_payload(mismatch_path, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "SELECTION_HUNK_MISMATCH"):
            authoring.finalize_scaffold(
                self.source, mismatch_path, self.root / "mismatch-selection.json"
            )

    def test_cli_is_fail_closed_and_never_overwrites_outputs(self) -> None:
        draft = self.root / "cli.authoring.json"
        create = subprocess.run(
            [
                sys.executable,
                str(AUTHORING_PATH),
                "create",
                str(self.source),
                "--scene",
                "COURSE",
                "--source-kind",
                "DOCUMENT",
                "--output",
                str(draft),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, create.returncode, create.stdout + create.stderr)
        self.assertEqual("PENDING", json.loads(create.stdout)["status"])
        repeated = subprocess.run(
            [
                sys.executable,
                str(AUTHORING_PATH),
                "create",
                str(self.source),
                "--scene",
                "COURSE",
                "--source-kind",
                "DOCUMENT",
                "--output",
                str(draft),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(1, repeated.returncode)
        self.assertNotIn(str(self.root), repeated.stdout + repeated.stderr)
        finalize = subprocess.run(
            [
                sys.executable,
                str(AUTHORING_PATH),
                "finalize",
                str(self.source),
                "--authoring",
                str(draft),
                "--output",
                str(self.root / "cli-selection.json"),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(1, finalize.returncode)
        self.assertIn("PENDING", finalize.stdout)

    def test_finalize_detects_policy_change_during_execution(self) -> None:
        draft_path, payload = self.create()
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft_path, payload)
        original = authoring.current_policy_hashes
        calls = 0

        def drifting_policy() -> dict[str, str]:
            nonlocal calls
            calls += 1
            value = original()
            if calls > 1:
                value["scanner_sha256"] = "f" * 64
            return value

        with mock.patch.object(authoring, "current_policy_hashes", side_effect=drifting_policy):
            with self.assertRaisesRegex(authoring.AuthoringError, "POLICY_CHANGED_DURING_FINALIZE"):
                authoring.finalize_scaffold(
                    self.source, draft_path, self.root / "policy-race-selection.json"
                )

    def test_inline_selection_is_bound_at_finalize_not_blocked_at_create(self) -> None:
        draft = self.root / "inline.authoring.json"
        payload = authoring.create_scaffold(
            self.source,
            draft,
            requested_output="PATCH",
            scene="COURSE",
            intensity="BALANCED",
            source_kind="INLINE_SELECTION",
            protected_terms=[],
            span_suggestion_mode="NONE",
        )
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "BOUND_SELECTION_REQUIRED"):
            authoring.finalize_scaffold(
                self.source, draft, self.root / "inline-unbound-selection.json"
            )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": payload["hunks"][0]["span_id"],
                "decision": "HUNK",
                "hunk_id": payload["hunks"][0]["hunk_id"],
                "reason": "该精确内联 span 是调用方声明的处理范围。",
            }
        ]
        self.write_payload(draft, payload)
        selection = authoring.finalize_scaffold(
            self.source, draft, self.root / "inline-bound-selection.json"
        )
        self.assertEqual("INLINE_SELECTION", selection["coverage"]["source_kind"])

    def test_malformed_finding_ids_fails_as_structured_authoring_error(self) -> None:
        draft, payload = self.create()
        payload["spans"][0]["finding_ids"] = [{"not": "hashable"}]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "finding_ids is invalid"):
            authoring.finalize_scaffold(
                self.source, draft, self.root / "malformed-finding-selection.json"
            )

    def test_invalid_cli_arguments_honor_requested_json_failure_contract(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                str(AUTHORING_PATH),
                "create",
                str(self.source),
                "--scene",
                "INVALID",
                "--source-kind",
                "DOCUMENT",
                "--output",
                str(self.root / "invalid.authoring.json"),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(1, process.returncode)
        self.assertEqual("", process.stderr)
        failure = json.loads(process.stdout)
        self.assertEqual("FAIL", failure["status"])
        self.assertEqual("INVALID_ARGUMENTS", failure["error"])

    def test_in_process_cli_create_finalize_and_json_failure_paths(self) -> None:
        draft = self.root / "in-process.authoring.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = authoring.main(
                [
                    "create",
                    str(self.source),
                    "--scene",
                    "COURSE",
                    "--source-kind",
                    "DOCUMENT",
                    "--output",
                    str(draft),
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("PENDING high=", stdout.getvalue())
        payload = json.loads(draft.read_text(encoding="utf-8"))
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft, payload)
        selection = self.root / "in-process.selection.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = authoring.main(
                [
                    "finalize",
                    str(self.source),
                    "--authoring",
                    str(draft),
                    "--output",
                    str(selection),
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("FINALIZED hunks=", stdout.getvalue())
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = authoring.main(
                [
                    "create",
                    str(self.source),
                    "--scene",
                    "INVALID",
                    "--source-kind",
                    "DOCUMENT",
                    "--output",
                    str(self.root / "never-written.json"),
                    "--format=json",
                ]
            )
        self.assertEqual(1, exit_code)
        self.assertEqual("FAIL", json.loads(stdout.getvalue())["status"])

    def test_keep_resolutions_and_selected_keep_compile_without_duplicate_text(self) -> None:
        draft, payload = self.create("keep.authoring.json")
        span_by_finding = {
            finding_id: span["span_id"]
            for span in payload["spans"]
            for finding_id in span["finding_ids"]
        }
        first, *remaining = payload["lexical_resolutions"]
        first.update(
            {
                "decision": "KEEP",
                "hunk_id": None,
                "reason": "该处在本段真实承担对比重点，保留其提示功能。",
            }
        )
        payload["hunks"] = []
        for index, resolution in enumerate(remaining, start=1):
            hunk_id = f"H{index:03d}"
            resolution.update(
                {"decision": "HUNK", "hunk_id": hunk_id, "reason": None}
            )
            payload["hunks"].append(
                {
                    "hunk_id": hunk_id,
                    "span_id": span_by_finding[resolution["finding_id"]],
                    "decision": "DELETE_STYLE_SHELL",
                    "replacement": "",
                    "reason": "删除没有新增对象或后果的泛化句壳。",
                }
            )
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": span_by_finding[first["finding_id"]],
                "decision": "KEEP",
                "hunk_id": None,
                "reason": "用户明确要求该精确 span 保持不变。",
            }
        ]
        self.write_payload(draft, payload)
        selection = authoring.finalize_scaffold(
            self.source, draft, self.root / "keep.selection.json"
        )
        self.assertEqual(1, len(selection["coverage"]["lexical_keeps"]))
        self.assertEqual("KEEP", selection["coverage"]["selected_spans"][0]["decision"])

    def test_v1_authoring_remains_read_only_compatible(self) -> None:
        draft, payload = self.create("legacy.authoring.json")
        payload["schema_version"] = "humanize-short-patch-selection-authoring/v1"
        payload.pop("scene_route")
        payload.pop("span_suggestion_policy")
        payload.pop("span_suggestions")
        payload.pop("authoring_integrity_scope")
        payload.pop("focus_spans")
        payload["configuration"]["scene"] = payload["configuration"].pop(
            "resolved_scene"
        )
        payload["configuration"].pop("requested_scene")
        payload["configuration"].pop("span_suggestion_mode")
        payload["policy_hashes"] = authoring._policy_hashes_for_schema(
            payload["schema_version"]
        )
        payload["inventory_sha256"] = authoring._inventory_hash(
            payload["source"],
            payload["configuration"],
            payload["policy_hashes"],
            payload["high_findings"],
        )
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft, payload)
        selection = authoring.finalize_scaffold(
            self.source, draft, self.root / "legacy.selection.json"
        )
        self.assertEqual("humanize-short-patch-selection/v2", selection["schema_version"])

    def test_v2_authoring_remains_read_only_compatible(self) -> None:
        draft, payload = self.create("legacy-v2.authoring.json")
        payload["schema_version"] = "humanize-short-patch-selection-authoring/v2"
        payload.pop("scene_route")
        payload.pop("focus_spans")
        payload["configuration"]["scene"] = payload["configuration"].pop(
            "resolved_scene"
        )
        payload["configuration"].pop("requested_scene")
        payload["policy_hashes"] = authoring._policy_hashes_for_schema(
            payload["schema_version"]
        )
        payload["inventory_sha256"] = authoring._inventory_hash(
            payload["source"],
            payload["configuration"],
            payload["policy_hashes"],
            payload["high_findings"],
            span_suggestion_policy=payload["span_suggestion_policy"],
            span_suggestions=payload["span_suggestions"],
        )
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft, payload)

        selection = authoring.finalize_scaffold(
            self.source, draft, self.root / "legacy-v2.selection.json"
        )

        self.assertEqual("humanize-short-patch-selection/v2", selection["schema_version"])

    def test_v3_authoring_remains_read_only_compatible(self) -> None:
        draft, payload = self.create("legacy-v3.authoring.json")
        payload["schema_version"] = "humanize-short-patch-selection-authoring/v3"
        payload.pop("scene_route")
        payload["configuration"]["scene"] = payload["configuration"].pop(
            "resolved_scene"
        )
        payload["configuration"].pop("requested_scene")
        payload["policy_hashes"] = authoring._policy_hashes_for_schema(
            payload["schema_version"]
        )
        payload["inventory_sha256"] = authoring._inventory_hash(
            payload["source"],
            payload["configuration"],
            payload["policy_hashes"],
            payload["high_findings"],
            focus_spans=payload["focus_spans"],
            span_suggestion_policy=payload["span_suggestion_policy"],
            span_suggestions=payload["span_suggestions"],
        )
        self.resolve_all_high_with_hunks(payload)
        self.write_payload(draft, payload)

        selection = authoring.finalize_scaffold(
            self.source, draft, self.root / "legacy-v3.selection.json"
        )

        self.assertEqual("humanize-short-patch-selection/v2", selection["schema_version"])

    def test_create_refuses_scaffold_larger_than_finalize_can_read(self) -> None:
        output = self.root / "oversize.authoring.json"
        with mock.patch.object(authoring.short_patch, "MAX_JSON_BYTES", 600):
            with self.assertRaisesRegex(authoring.AuthoringError, "AUTHORING_OUTPUT_EXCEEDS_LIMIT"):
                authoring.create_scaffold(
                    self.source,
                    output,
                    requested_output="PATCH",
                    scene="COURSE",
                    intensity="BALANCED",
                    source_kind="DOCUMENT",
                    protected_terms=[],
                    span_suggestion_mode="SENTENCE",
                )
        self.assertFalse(output.exists())

    def test_finalize_rejects_editing_any_protected_code_span_before_builder(self) -> None:
        self.source.write_text("```text\ncode_token\n```\n", encoding="utf-8")
        draft, payload = self.create("protected.authoring.json")
        payload["spans"].append(
            {
                "span_id": "A900",
                "finding_ids": [],
                "source_text": "code_token",
                "start_byte": None,
            }
        )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": "A900",
                "decision": "REWRITE",
                "replacement": "changed",
                "reason": "尝试修改代码围栏中的受保护 token。",
            }
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "HUNK_OVERLAPS_PROTECTED_SPAN"):
            authoring.finalize_scaffold(
                self.source, draft, self.root / "protected.selection.json"
            )

    def test_reason_terminal_punctuation_does_not_bypass_unfinished_rejection(self) -> None:
        draft, payload = self.create("generic-reason.authoring.json")
        first_resolution = payload["lexical_resolutions"][0]
        span_id = next(
            span["span_id"]
            for span in payload["spans"]
            if first_resolution["finding_id"] in span["finding_ids"]
        )
        first_resolution.update(
            {"decision": "HUNK", "hunk_id": "H001", "reason": None}
        )
        for resolution in payload["lexical_resolutions"][1:]:
            resolution.update(
                {
                    "decision": "KEEP",
                    "hunk_id": None,
                    "reason": "该处承担当前段的真实条件提醒，暂不删除其功能。",
                }
            )
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "span_id": span_id,
                "decision": "DELETE_STYLE_SHELL",
                "replacement": "",
                "reason": "TODO。",
            }
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "generic or unfinished"):
            authoring.finalize_scaffold(
                self.source, draft, self.root / "generic-reason.selection.json"
            )

    def test_reference_ids_must_match_declared_case_exactly(self) -> None:
        draft, payload = self.create("case-reference.authoring.json")
        self.resolve_all_high_with_hunks(payload)
        payload["selected_spans"] = [
            {
                "selection_id": "S001",
                "span_id": payload["hunks"][0]["span_id"],
                "decision": "HUNK",
                "hunk_id": payload["hunks"][0]["hunk_id"].lower(),
                "reason": "该精确 span 由调用方列入本次最小 PATCH。",
            }
        ]
        self.write_payload(draft, payload)
        with self.assertRaisesRegex(authoring.AuthoringError, "REFERENCE_ID_CASE_MISMATCH"):
            authoring.finalize_scaffold(
                self.source, draft, self.root / "case-reference.selection.json"
            )

    def test_zero_high_create_reports_no_findings_and_finalize_requires_manual_hunk(self) -> None:
        self.source.write_text("普通句子。\n", encoding="utf-8")
        output = self.root / "zero-high.authoring.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = authoring.main(
                [
                    "create",
                    str(self.source),
                    "--scene",
                    "GENERAL",
                    "--source-kind",
                    "DOCUMENT",
                    "--output",
                    str(output),
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(0, exit_code)
        result = json.loads(stdout.getvalue())
        self.assertEqual("NO_HIGH_FINDINGS", result["status"])
        self.assertFalse(result["completion_claim_allowed"])
        with self.assertRaisesRegex(authoring.AuthoringError, "NO_PATCH_HUNKS"):
            authoring.finalize_scaffold(
                self.source, output, self.root / "zero-high.selection.json"
            )


if __name__ == "__main__":
    unittest.main()
