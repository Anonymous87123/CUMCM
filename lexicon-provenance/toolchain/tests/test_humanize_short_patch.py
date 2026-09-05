import importlib.util
import json
import os
import shutil
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
BUILDER_PATH = SKILL / "scripts" / "build_humanize_short_patch.py"
APPLICATOR_PATH = SKILL / "scripts" / "apply_humanize_short_patch.py"
VERIFIER_PATH = SKILL / "scripts" / "verify_humanize_short_patch.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module("build_humanize_short_patch", BUILDER_PATH)
applicator = load_module("apply_humanize_short_patch", APPLICATOR_PATH)
verifier = load_module("verify_humanize_short_patch", VERIFIER_PATH)


class HumanizeShortPatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.tex"
        self.source_text = (
            "值得注意的是，先读题。\r\n"
            "若条件冲突，保留原句。\r\n"
            "这个结论具有重要意义。\r\n"
        )
        self.source.write_bytes(self.source_text.encode("utf-8"))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def valid_spec(self) -> dict:
        return {
            "schema_version": "humanize-short-patch-selection/v1",
            "requested_output": "CLEAN",
            "mode": "REWRITE",
            "scene": "COURSE",
            "intensity": "BALANCED",
            "protected_terms": [],
            "hunks": [
                {
                    "hunk_id": "H001",
                    "decision": "DELETE_STYLE_SHELL",
                    "source_text": "值得注意的是，",
                    "start_byte": None,
                    "replacement": "",
                    "reason": "删除没有新增信息的重点提示壳。",
                },
                {
                    "hunk_id": "H002",
                    "decision": "REWRITE",
                    "source_text": "先读题",
                    "start_byte": None,
                    "replacement": "先核对题目条件",
                    "reason": "把泛化动作落到原句已有的条件判断。",
                },
                {
                    "hunk_id": "H003",
                    "decision": "UNRESOLVED",
                    "source_text": "若条件冲突，保留原句。",
                    "start_byte": None,
                    "replacement": "若条件冲突，保留原句。",
                    "reason": "该处存在来源主张冲突，纯文风层不能裁决。",
                },
                {
                    "hunk_id": "H004",
                    "decision": "DELETE_STYLE_SHELL",
                    "source_text": "这个结论具有重要意义。",
                    "start_byte": None,
                    "replacement": "",
                    "reason": "删除没有对象和后果的泛化意义尾句。",
                },
            ],
        }

    def valid_coverage_spec(self) -> dict:
        payload = self.valid_spec()
        payload["schema_version"] = "humanize-short-patch-selection/v2"
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [
                {
                    "selection_id": "S001",
                    "source_text": "值得注意的是，",
                    "start_byte": None,
                    "decision": "HUNK",
                    "hunk_id": "H001",
                    "reason": "用户把空重点句壳列入本次处理范围。",
                },
                {
                    "selection_id": "S002",
                    "source_text": "若条件冲突，保留原句。",
                    "start_byte": None,
                    "decision": "HUNK",
                    "hunk_id": "H003",
                    "reason": "用户要求保留该未决条件句。",
                },
            ],
            "explicit_conflicts": [],
        }
        return payload

    def write_spec(self, payload: dict | None = None, name: str = "selection.json") -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(payload or self.valid_spec(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def build(self, payload: dict | None = None, name: str = "patch.json") -> tuple[Path, dict]:
        spec = self.write_spec(payload)
        output = self.root / name
        result = builder.build_bundle(self.source, spec, output)
        return output, result

    @staticmethod
    def refresh_evidence_manifest(output: Path, artifact_name: str) -> None:
        manifest_path = output / "evidence-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = (output / artifact_name).read_bytes()
        for entry in manifest["artifacts"]:
            if entry["path"] == artifact_name:
                entry["size"] = len(raw)
                entry["sha256"] = builder.sha256(raw)
                break
        else:
            raise AssertionError(f"artifact not found in manifest: {artifact_name}")
        manifest["manifest_sha256"] = verifier._manifest_hash(manifest)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_build_and_apply_mixed_patch_preserves_unlisted_bytes(self) -> None:
        original = self.source.read_bytes()
        spec = self.write_spec()
        bundle_path = self.root / "patch.json"

        bundle = builder.build_bundle(self.source, spec, bundle_path)

        self.assertEqual("humanize-short-patch/v1", bundle["schema_version"])
        self.assertEqual("PATCH", bundle["effective_output"])
        self.assertEqual("NON_OVERLAPPING", bundle["patch_hunks_source_partition"])
        self.assertEqual("COPY_EXACT", bundle["unlisted_source_policy"])
        self.assertEqual("NOT_EVALUATED", bundle["semantic_judgment"])
        self.assertFalse(bundle["completion_claim_allowed"])
        self.assertEqual(4, len(bundle["hunks"]))
        self.assertEqual(sorted(h["start_byte"] for h in bundle["hunks"]), [h["start_byte"] for h in bundle["hunks"]])
        for hunk in bundle["hunks"]:
            raw = original[hunk["start_byte"] : hunk["end_byte"]]
            self.assertEqual(hunk["source_text"].encode("utf-8"), raw)

        output_dir = self.root / "applied"
        result = applicator.apply_patch(self.source, bundle_path, output_dir)

        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["structural_validation_status"])
        self.assertEqual("PASS", result["patch_application_status"])
        self.assertIn(result["unified_validator_status"], {"PASS", "REVIEW"})
        self.assertEqual("PASS", result["hard_invariant_layer_status"])
        self.assertIn(
            result["paired_quality_review_status"],
            {"PENDING_EXTERNAL_REVIEW", "BLOCKED_BY_MECHANICAL_GATE"},
        )
        self.assertEqual("NOT_PROVIDED", result["coverage_status"])
        self.assertFalse(result["coverage_completion_claim_allowed"])
        self.assertEqual("NOT_EVALUATED", result["semantic_judgment"])
        self.assertEqual(1, result["unresolved_total"])
        self.assertFalse(result["humanize_quality_claim_allowed"])
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual("humanize-short-patch-result/v2", result["schema_version"])
        self.assertEqual("review.md", result["review_path"])
        self.assertEqual(original, self.source.read_bytes())
        candidate = (output_dir / "candidate.review.tex").read_bytes().decode("utf-8")
        self.assertEqual(
            "先核对题目条件。\r\n若条件冲突，保留原句。\r\n\r\n",
            candidate,
        )
        self.assertIn("--- source", (output_dir / "patch.diff").read_text(encoding="utf-8"))
        review = (output_dir / "review.md").read_text(encoding="utf-8")
        self.assertIn("## 已变化 hunk", review)
        self.assertIn("## 未变化的未决 hunk", review)
        self.assertIn("若条件冲突，保留原句。", review)
        self.assertIn("humanize_quality_claim_allowed=false", review)
        self.assertNotIn(str(self.root), review)
        self.assertEqual(result, json.loads((output_dir / "result.json").read_text(encoding="utf-8")))
        validation = json.loads((output_dir / "validation.json").read_text(encoding="utf-8"))
        self.assertEqual(result["validator_exit_code"], validation["exit_code"])
        self.assertEqual(result["validator_delivery_gate_status"], validation["delivery_gate_status"])
        self.assertEqual(bundle_path.read_bytes(), (output_dir / "patch.bundle.json").read_bytes())
        manifest = json.loads((output_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("humanize-short-patch-evidence-manifest/v1", manifest["schema_version"])
        verified = verifier.verify_directory(output_dir)
        self.assertEqual("PASS", verified["status"])
        self.assertEqual("SELF_CONSISTENCY_ONLY", verified["integrity_scope"])
        self.assertEqual("MATCH", verified["current_policy_status"])
        self.assertEqual("PASS", verified["current_policy_replay_status"])
        self.assertEqual("NOT_PROVIDED", verified["live_source_status"]["status"])
        self.assertEqual(2, verified["delivery_gate_exit_code"])
        self.assertFalse(verified["humanize_quality_claim_allowed"])
        self.assertEqual("PASS", verified["review_artifact_status"])

    def test_short_patch_template_field_payload_edit_cannot_gain_completion_without_scope(self) -> None:
        self.source_text = "适用题目：旧题型。\r\n正文保持不变。\r\n"
        self.source.write_bytes(self.source_text.encode("utf-8"))
        spec = {
            "schema_version": "humanize-short-patch-selection/v1",
            "requested_output": "CLEAN",
            "mode": "REWRITE",
            "scene": "COURSE",
            "intensity": "BALANCED",
            "protected_terms": [],
            "hunks": [
                {
                    "hunk_id": "H001",
                    "decision": "REWRITE",
                    "source_text": "旧题型。",
                    "start_byte": None,
                    "replacement": "新题型。",
                    "reason": "修改适用题目字段的分类内容，检查无授权短补丁不能获得完成态。",
                }
            ],
        }
        bundle_path, _bundle = self.build(spec, "template-payload-patch.json")
        output = self.root / "template-payload-output"

        result = applicator.apply_patch(self.source, bundle_path, output)
        validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))

        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        self.assertFalse(result["completion_claim_allowed"])
        self.assertFalse(result["humanize_quality_claim_allowed"])
        self.assertEqual("REVIEW", validation["template_field_layer_status"])
        self.assertEqual("N/A", validation["template_field_edit_scope_check"]["status"])
        self.assertEqual(0, validation["template_field_edit_scope_check"]["authorized_edit_count"])
        self.assertEqual(1, validation["template_field_summary"]["review_finding_count"])
        self.assertEqual("NOT_AUTHORIZED", validation["template_field_findings"][0]["authorization_status"])

        verified = verifier.verify_directory(output)
        self.assertEqual("PASS", verified["record_integrity_status"])
        self.assertEqual("REVIEW", verified["delivery_gate_status"])
        self.assertFalse(verified["humanize_quality_claim_allowed"])

    def test_short_patch_template_field_header_edit_is_rejected_before_publish(self) -> None:
        self.source_text = "适用题目：旧题型。\r\n正文保持不变。\r\n"
        self.source.write_bytes(self.source_text.encode("utf-8"))
        spec = {
            "schema_version": "humanize-short-patch-selection/v1",
            "requested_output": "CLEAN",
            "mode": "REWRITE",
            "scene": "COURSE",
            "intensity": "BALANCED",
            "protected_terms": [],
            "hunks": [
                {
                    "hunk_id": "H001",
                    "decision": "REWRITE",
                    "source_text": "适用题目：",
                    "start_byte": None,
                    "replacement": "适用范围：",
                    "reason": "尝试修改受保护字段标签，用于确认短补丁发布前的硬拒绝。",
                }
            ],
        }
        bundle_path, _bundle = self.build(spec, "template-header-patch.json")
        output = self.root / "template-header-output"

        with self.assertRaisesRegex(applicator.ShortPatchError, "UNIFIED_VALIDATOR_FAILED"):
            applicator.apply_patch(self.source, bundle_path, output)

        self.assertFalse(output.exists())
        self.assertEqual(self.source_text.encode("utf-8"), self.source.read_bytes())

    def test_review_artifact_is_deterministic_and_rejects_rehashed_tamper(self) -> None:
        bundle_path, _bundle = self.build(self.valid_coverage_spec())
        output = self.root / "review-artifact-output"
        applicator.apply_patch(self.source, bundle_path, output)
        review_path = output / "review.md"
        review = review_path.read_text(encoding="utf-8")
        self.assertIn("## 覆盖范围与限制", review)
        self.assertIn("ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY", review)
        self.assertIn("## 显式冲突对", review)
        self.assertEqual(
            review_path.read_bytes(),
            applicator._review_markdown(
                json.loads((output / "patch.bundle.json").read_text(encoding="utf-8")),
                json.loads((output / "result.json").read_text(encoding="utf-8")),
                json.loads((output / "validation.json").read_text(encoding="utf-8")),
            ),
        )
        review_path.write_text(review + "\n伪造的人工复核：PASS\n", encoding="utf-8")
        self.refresh_evidence_manifest(output, "review.md")
        with self.assertRaisesRegex(verifier.ShortPatchError, "review artifact"):
            verifier.verify_directory(output)

    def test_review_artifact_escapes_source_markup_and_keeps_unresolved_visible(self) -> None:
        bundle_path, _bundle = self.build(self.valid_spec(), "markup-review-bundle.json")
        output = self.root / "markup-review-output"
        applicator.apply_patch(self.source, bundle_path, output)
        bundle = json.loads((output / "patch.bundle.json").read_text(encoding="utf-8"))
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
        validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
        bundle["hunks"][0]["source_text"] = "</pre><script>alert(1)</script>"
        bundle["hunks"][0]["replacement"] = "安全文本"
        bundle["hunks"][0]["reason"] = "伪造理由\n# 人工复核 PASS"
        review = applicator._review_markdown(bundle, result, validation).decode("utf-8")
        self.assertNotIn("<script>", review)
        self.assertIn("&lt;script&gt;", review)
        self.assertNotIn("\n# 人工复核 PASS", review)
        self.assertIn("若条件冲突，保留原句。", review)

    def test_verifier_replays_current_policy_and_rejects_rehashed_core_tamper(self) -> None:
        bundle_path, _bundle = self.build()
        output = self.root / "replay-tamper-output"
        applicator.apply_patch(self.source, bundle_path, output)

        validation_path = output / "validation.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation["speech_act_layer_status"] = (
            "PASS" if validation["speech_act_layer_status"] == "REVIEW" else "REVIEW"
        )
        validation_path.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.refresh_evidence_manifest(output, "validation.json")

        with self.assertRaisesRegex(
            verifier.ShortPatchError,
            "review artifact|CURRENT_POLICY_REPLAY_MISMATCH",
        ):
            verifier.verify_directory(output)

    def test_policy_drift_is_review_and_does_not_claim_current_replay(self) -> None:
        bundle_path, _bundle = self.build()
        output = self.root / "policy-drift-output"
        applicator.apply_patch(self.source, bundle_path, output)
        validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
        changed_policy = dict(validation["evidence"]["policy_hashes"])
        changed_policy["validator_sha256"] = "0" * 64

        with mock.patch.object(
            verifier, "_current_policy_hashes", return_value=changed_policy
        ):
            verified = verifier.verify_directory(output)

        self.assertEqual("REVIEW", verified["status"])
        self.assertEqual(2, verified["exit_code"])
        self.assertEqual("DRIFT", verified["current_policy_status"])
        self.assertEqual("NOT_RUN", verified["current_policy_replay_status"])
        self.assertIn("POLICY_DRIFT", verified["review_reasons"])
        self.assertFalse(verified["completion_claim_allowed"])

    def test_live_source_match_drift_and_missing_are_visible_without_changing_record(self) -> None:
        bundle_path, _bundle = self.build()
        output = self.root / "live-source-output"
        applicator.apply_patch(self.source, bundle_path, output)
        manifest_before = (output / "evidence-manifest.json").read_bytes()

        matching = verifier.verify_directory(output, live_source=self.source)
        self.assertEqual("REVIEW", matching["status"])
        self.assertEqual(2, matching["exit_code"])
        self.assertEqual(
            "CALLER_SUPPLIED_MATCH_UNVERIFIED",
            matching["live_source_status"]["status"],
        )
        self.assertEqual(
            "UNVERIFIED_CALLER_PATH",
            matching["live_source_status"]["path_binding"],
        )
        self.assertFalse(matching["live_source_status"]["freshness_claim_allowed"])
        self.assertIn("LIVE_SOURCE_PATH_BINDING_UNVERIFIED", matching["review_reasons"])

        self.source.write_text("来源在 PATCH 之后已修改。", encoding="utf-8")
        drifted = verifier.verify_directory(output, live_source=self.source)
        self.assertEqual("REVIEW", drifted["status"])
        self.assertEqual(2, drifted["exit_code"])
        self.assertEqual(
            "CALLER_SUPPLIED_NOT_CURRENT",
            drifted["live_source_status"]["status"],
        )
        self.assertIn("LIVE_SOURCE_NOT_CURRENT", drifted["review_reasons"])
        self.assertIn("LIVE_SOURCE_PATH_BINDING_UNVERIFIED", drifted["review_reasons"])

        missing_path = self.root / "missing-live-source.tex"
        missing = verifier.verify_directory(output, live_source=missing_path)
        self.assertEqual("REVIEW", missing["status"])
        self.assertEqual("UNAVAILABLE", missing["live_source_status"]["status"])
        self.assertNotIn(str(missing_path), json.dumps(missing, ensure_ascii=False))
        self.assertEqual(manifest_before, (output / "evidence-manifest.json").read_bytes())

    def test_evidence_verifier_detects_tamper_and_extra_files(self) -> None:
        bundle_path, _bundle = self.build()
        output = self.root / "tamper-output"
        applicator.apply_patch(self.source, bundle_path, output)
        candidate = output / "candidate.review.tex"
        candidate.write_bytes(candidate.read_bytes() + b"tamper")
        with self.assertRaisesRegex(verifier.ShortPatchError, "artifact_(?:size|sha256)"):
            verifier.verify_directory(output)

        output2 = self.root / "extra-output"
        applicator.apply_patch(self.source, bundle_path, output2)
        (output2 / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(verifier.ShortPatchError, "closed file set"):
            verifier.verify_directory(output2)

    def test_utf8_byte_offsets_and_explicit_occurrence_are_exact(self) -> None:
        self.source.write_text("甲😀重复。乙😀重复。\n", encoding="utf-8", newline="")
        second_text = "😀重复"
        second_start = self.source.read_bytes().rfind(second_text.encode("utf-8"))
        payload = self.valid_spec()
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": second_text,
                "start_byte": second_start,
                "replacement": "😀复核",
                "reason": "只改第二处同形文本，第一处保持原样。",
            }
        ]
        bundle_path, bundle = self.build(payload)
        self.assertEqual(second_start, bundle["hunks"][0]["start_byte"])
        out = self.root / "unicode-out"
        applicator.apply_patch(self.source, bundle_path, out)
        self.assertEqual(
            "甲😀重复。乙😀复核。\n",
            (out / "candidate.review.tex").read_text(encoding="utf-8"),
        )

    def test_no_unresolved_hunk_still_cannot_claim_humanize_quality(self) -> None:
        payload = self.valid_spec()
        payload["hunks"] = payload["hunks"][:2]
        bundle_path, _bundle = self.build(payload)
        result = applicator.apply_patch(self.source, bundle_path, self.root / "safe-review")

        self.assertEqual(0, result["unresolved_total"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        self.assertFalse(result["humanize_quality_claim_allowed"])
        self.assertIn(
            result["paired_quality_review_status"],
            {"PENDING_EXTERNAL_REVIEW", "BLOCKED_BY_MECHANICAL_GATE"},
        )

    def test_v2_coverage_inventory_binds_high_findings_selections_and_evidence(self) -> None:
        bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-patch.json")
        self.assertEqual("humanize-short-patch/v2", bundle["schema_version"])
        coverage = bundle["coverage"]
        self.assertEqual("humanize-short-patch-coverage/v2", coverage["schema_version"])
        self.assertEqual("PASS", coverage["mechanical_coverage_status"])
        self.assertTrue(coverage["coverage_completion_claim_allowed"])
        self.assertFalse(coverage["semantic_completeness_claim_allowed"])
        self.assertEqual(2, coverage["summary"]["lexical_high_total"])
        self.assertEqual(2, coverage["summary"]["selected_spans_total"])
        self.assertEqual(
            {"H001", "H004"},
            {
                item["disposition"]["hunk_id"]
                for item in coverage["inventories"]["lexical_high"]
            },
        )

        output = self.root / "coverage-output"
        result = applicator.apply_patch(self.source, bundle_path, output)
        self.assertEqual("PASS", result["coverage_status"])
        self.assertTrue(result["coverage_completion_claim_allowed"])
        self.assertEqual(
            "ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY",
            result["coverage_claim_scope"],
        )
        self.assertEqual("COURSE", result["coverage_scene"])
        self.assertEqual("AUTO", result["coverage_scan_scene"])
        self.assertEqual("DOCUMENT", result["coverage_source_kind"])
        self.assertIn("coverage.json", result["artifacts_written"])
        self.assertEqual(
            coverage,
            json.loads((output / "coverage.json").read_text(encoding="utf-8")),
        )
        verified = verifier.verify_directory(output)
        self.assertEqual("PASS", verified["coverage_policy_status"])
        self.assertEqual("PASS", verified["coverage_replay_status"])
        self.assertTrue(verified["coverage_completion_claim_allowed"])
        self.assertEqual(
            "ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY",
            verified["coverage_claim_scope"],
        )
        self.assertEqual("AUTO", verified["coverage_scan_scene"])

    def test_v2_coverage_rejects_uncovered_high_finding_and_unknown_keep(self) -> None:
        payload = self.valid_coverage_spec()
        payload["hunks"] = [payload["hunks"][1]]
        payload["coverage"]["selected_spans"] = []
        with self.assertRaisesRegex(builder.ShortPatchError, "UNCOVERED_LEXICAL_HIGH"):
            self.build(payload, "uncovered-high.json")

        payload["coverage"]["lexical_keeps"] = [
            {
                "signal_id": "LEX-NOT-REAL",
                "source_text": "值得注意的是",
                "start_byte": None,
                "reason": "该位置承担真实的对比提醒功能。",
            }
        ]
        with self.assertRaisesRegex(builder.ShortPatchError, "UNKNOWN_LEXICAL_KEEP"):
            self.build(payload, "unknown-keep.json")

    def test_v2_coverage_selection_must_map_exactly_to_declared_hunk(self) -> None:
        payload = self.valid_coverage_spec()
        payload["coverage"]["selected_spans"][0]["hunk_id"] = "H002"
        with self.assertRaisesRegex(builder.ShortPatchError, "SELECTION_HUNK_MISMATCH"):
            self.build(payload, "selection-mismatch.json")

    def test_v2_selection_keep_cannot_overlap_an_actual_hunk(self) -> None:
        payload = self.valid_coverage_spec()
        payload["coverage"]["selected_spans"] = [
            {
                "selection_id": "S-KEEP",
                "source_text": "先读题",
                "start_byte": None,
                "decision": "KEEP",
                "hunk_id": None,
                "reason": "用户要求该动作短语保持原样。",
            }
        ]
        with self.assertRaisesRegex(
            builder.ShortPatchError, "SELECTION_KEEP_OVERLAPS_HUNK"
        ):
            self.build(payload, "selection-keep-overlap.json")

    def test_excluded_or_protected_high_cannot_overlap_patch_hunk(self) -> None:
        cases = (
            ("边界层流动需要分析。\n", "边界层流动", "近壁流动", "EXCLUDED"),
            ("“形成研究闭环”。\n", "形成研究闭环", "形成讨论", "PROTECTED"),
        )
        for index, (source_text, selected, replacement, role) in enumerate(cases):
            with self.subTest(role=role):
                self.source.write_text(source_text, encoding="utf-8")
                payload = self.valid_coverage_spec()
                payload["scene"] = "GENERAL"
                payload["hunks"] = [
                    {
                        "hunk_id": "H001",
                        "decision": "REWRITE",
                        "source_text": selected,
                        "start_byte": None,
                        "replacement": replacement,
                        "reason": "验证保护或技术豁免命中不能被 coverage 隐去。",
                    }
                ]
                payload["coverage"] = {
                    "source_kind": "DOCUMENT",
                    "lexical_keeps": [],
                    "selected_spans": [],
                    "explicit_conflicts": [],
                }
                with self.assertRaisesRegex(
                    builder.ShortPatchError, "NON_EDITABLE_HIGH_OVERLAPS_HUNK"
                ):
                    self.build(payload, f"non-editable-{index}.json")

    def test_coverage_uses_auto_audit_view_even_when_task_scene_is_general(self) -> None:
        self.source.write_text("必须牢记公式。\n", encoding="utf-8")
        payload = self.valid_coverage_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "DELETE_STYLE_SHELL",
                "source_text": "必须牢记公式。",
                "start_byte": None,
                "replacement": "",
                "reason": "删除没有新增条件的记忆命令句壳。",
            }
        ]
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [],
        }
        _path, bundle = self.build(payload, "auto-audit-view.json")
        signals = {
            item["signal_id"]
            for item in bundle["coverage"]["inventories"]["lexical_high"]
        }
        self.assertIn("LEX-COACH-01", signals)
        self.assertEqual("AUTO", bundle["coverage"]["source"]["scan_scene"])

    def test_v2_explicit_conflict_requires_two_distinct_unresolved_hunks(self) -> None:
        self.source.write_text(
            "若甲成立，可以直接代入。\n若甲不成立，不能直接代入。\n",
            encoding="utf-8",
        )
        payload = self.valid_coverage_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "UNRESOLVED",
                "source_text": "若甲成立，可以直接代入。",
                "start_byte": None,
                "replacement": "若甲成立，可以直接代入。",
                "reason": "与后句形成显式相反许可，纯文风层不裁决。",
            },
            {
                "hunk_id": "H002",
                "decision": "UNRESOLVED",
                "source_text": "若甲不成立，不能直接代入。",
                "start_byte": None,
                "replacement": "若甲不成立，不能直接代入。",
                "reason": "与前句形成显式相反许可，纯文风层不裁决。",
            },
        ]
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [
                {
                    "conflict_id": "C001",
                    "rule_code": "OPPOSING_PERMISSION",
                    "left_hunk_id": "H001",
                    "right_hunk_id": "H002",
                    "reason": "两句给出相反的直接代入许可，必须成对保留。",
                }
            ],
        }
        _path, bundle = self.build(payload, "conflict-coverage.json")
        conflict = bundle["coverage"]["inventories"]["explicit_conflicts"][0]
        self.assertEqual("H001", conflict["left"]["hunk_id"])
        self.assertEqual("H002", conflict["right"]["hunk_id"])

        payload["hunks"][1] = {
            **payload["hunks"][1],
            "decision": "REWRITE",
            "replacement": "若甲不成立，则不能直接代入。",
        }
        with self.assertRaisesRegex(builder.ShortPatchError, "CONFLICT_REQUIRES_UNRESOLVED"):
            self.build(payload, "bad-conflict-coverage.json")

    def test_conflict_rule_code_and_reason_are_fail_closed(self) -> None:
        self.source.write_text(
            "若甲成立，可以直接代入。\n若甲不成立，不能直接代入。\n",
            encoding="utf-8",
        )
        payload = self.valid_coverage_spec()
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "UNRESOLVED",
                "source_text": "若甲成立，可以直接代入。",
                "start_byte": None,
                "replacement": "若甲成立，可以直接代入。",
                "reason": "与后句存在许可方向张力，纯文风层不裁决。",
            },
            {
                "hunk_id": "H002",
                "decision": "UNRESOLVED",
                "source_text": "若甲不成立，不能直接代入。",
                "start_byte": None,
                "replacement": "若甲不成立，不能直接代入。",
                "reason": "与前句存在许可方向张力，纯文风层不裁决。",
            },
        ]
        conflict = {
            "conflict_id": "C001",
            "rule_code": "OPPOSING_PERMISION_TYPO",
            "left_hunk_id": "H001",
            "right_hunk_id": "H002",
            "reason": "两句给出相反许可，纯文风层必须成对保留。",
        }
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [conflict],
        }
        with self.assertRaisesRegex(builder.ShortPatchError, "rule_code"):
            self.build(payload, "bad-conflict-rule.json")

        conflict["rule_code"] = "OPPOSING_PERMISSION"
        conflict["reason"] = "保持原样。"
        with self.assertRaisesRegex(builder.ShortPatchError, "generic or unfinished"):
            self.build(payload, "generic-conflict-reason.json")

    def test_selection_ids_reject_casefold_collisions_in_direct_v2_spec(self) -> None:
        payload = self.valid_coverage_spec()
        payload["coverage"]["selected_spans"][1]["selection_id"] = "s001"
        with self.assertRaisesRegex(builder.ShortPatchError, "duplicate selection_id"):
            self.build(payload, "casefold-selection-id.json")

    def test_conflict_ids_reject_casefold_collisions_in_coverage_input(self) -> None:
        conflict = {
            "conflict_id": "C001",
            "rule_code": "OTHER_DECLARED_CONFLICT",
            "left_hunk_id": "H001",
            "right_hunk_id": "H002",
            "reason": "调用方声明两侧存在其他不能由纯文风层裁决的冲突。",
        }
        spec = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [
                conflict,
                {
                    **conflict,
                    "conflict_id": "c001",
                    "left_hunk_id": "H003",
                    "right_hunk_id": "H004",
                },
            ],
        }
        with self.assertRaisesRegex(
            builder.coverage_layer.CoverageError, "duplicate conflict_id"
        ):
            builder.coverage_layer._normalized_declarations(
                self.source.read_bytes(), spec
            )

    def test_coverage_artifact_tamper_fails_even_after_manifest_rehash(self) -> None:
        bundle_path, _bundle = self.build(self.valid_coverage_spec(), "coverage-tamper.json")
        output = self.root / "coverage-tamper-output"
        applicator.apply_patch(self.source, bundle_path, output)
        coverage_path = output / "coverage.json"
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        coverage["summary"]["lexical_high_total"] -= 1
        coverage_path.write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.refresh_evidence_manifest(output, "coverage.json")
        with self.assertRaisesRegex(verifier.ShortPatchError, "coverage artifact"):
            verifier.verify_directory(output)

    def test_coverage_policy_drift_is_review_with_validator_replay_still_passed(self) -> None:
        bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-drift.json")
        output = self.root / "coverage-drift-output"
        applicator.apply_patch(self.source, bundle_path, output)
        changed = dict(bundle["coverage"]["policy_hashes"])
        changed["coverage_builder_sha256"] = "0" * 64
        with mock.patch.object(
            verifier.coverage_layer,
            "current_policy_hashes",
            return_value=changed,
        ):
            verified = verifier.verify_directory(output)
        self.assertEqual("REVIEW", verified["status"])
        self.assertEqual(2, verified["exit_code"])
        self.assertEqual("DRIFT", verified["coverage_policy_status"])
        self.assertEqual("NOT_RUN", verified["coverage_replay_status"])
        self.assertEqual("PASS", verified["current_policy_replay_status"])
        self.assertIn("COVERAGE_POLICY_DRIFT", verified["review_reasons"])
        self.assertFalse(verified["coverage_completion_claim_allowed"])

    def test_coverage_policy_key_set_change_is_review_not_corruption(self) -> None:
        bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-key-drift.json")
        output = self.root / "coverage-key-drift-output"
        applicator.apply_patch(self.source, bundle_path, output)
        changed = dict(bundle["coverage"]["policy_hashes"])
        changed["new_component_sha256"] = "1" * 64
        with mock.patch.object(
            verifier.coverage_layer,
            "current_policy_hashes",
            return_value=changed,
        ):
            verified = verifier.verify_directory(output)
        self.assertEqual("REVIEW", verified["status"])
        self.assertEqual("DRIFT", verified["coverage_policy_status"])
        self.assertEqual("PASS", verified["record_integrity_status"])

    def test_legacy_coverage_v1_is_integrity_checked_then_marked_policy_drift(self) -> None:
        _bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-v1-compat.json")
        legacy = json.loads(json.dumps(bundle["coverage"]))
        legacy["schema_version"] = "humanize-short-patch-coverage/v1"
        legacy["source"].pop("scan_scene")
        legacy["policy_hashes"]["coverage_builder_sha256"] = "0" * 64
        unsigned = dict(legacy)
        unsigned.pop("coverage_sha256")
        legacy["coverage_sha256"] = builder.sha256(builder.canonical_json(unsigned))
        validated = verifier.coverage_layer.validate_record_integrity(
            self.source.read_bytes(), legacy
        )
        self.assertEqual("humanize-short-patch-coverage/v1", validated["schema_version"])
        replayed, status = verifier.coverage_layer.replay_coverage(
            self.source.read_bytes(), hunks=bundle["hunks"], recorded=legacy
        )
        self.assertIsNone(replayed)
        self.assertEqual("DRIFT", status)

    def test_rehashed_bundle_cannot_delete_deterministic_high_inventory(self) -> None:
        _bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-forge.json")
        forged = json.loads(json.dumps(bundle))
        forged_coverage = forged["coverage"]
        forged_coverage["inventories"]["lexical_high"] = forged_coverage["inventories"][
            "lexical_high"
        ][1:]
        remaining = forged_coverage["inventories"]["lexical_high"]
        forged_coverage["summary"]["lexical_high_total"] = len(remaining)
        forged_coverage["summary"]["lexical_candidate_total"] = sum(
            item["role"] == "CANDIDATE" for item in remaining
        )
        disposition_counts: dict[str, int] = {}
        for item in remaining:
            decision = item["disposition"]["decision"]
            disposition_counts[decision] = disposition_counts.get(decision, 0) + 1
        forged_coverage["summary"]["lexical_disposition_counts"] = dict(
            sorted(disposition_counts.items())
        )
        coverage_unsigned = dict(forged_coverage)
        coverage_unsigned.pop("coverage_sha256")
        forged_coverage["coverage_sha256"] = builder.sha256(
            builder.canonical_json(coverage_unsigned)
        )
        forged["bundle_sha256"] = builder._bundle_hash(forged)
        with self.assertRaisesRegex(builder.ShortPatchError, "COVERAGE_REPLAY_MISMATCH"):
            builder.validate_bundle_payload(forged, self.source.read_bytes())

    def test_coverage_record_integrity_rejects_malformed_inventory_and_summary(self) -> None:
        _bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-shape.json")
        cases = (
            (
                "inventory-type",
                lambda item: item["coverage"]["inventories"].update(
                    {"lexical_high": 1}
                ),
                "lexical_high must be an array",
            ),
            (
                "summary-counts",
                lambda item: item["coverage"]["summary"].update(
                    {"lexical_disposition_counts": {"KEEP": 999}}
                ),
                "disposition_counts mismatch",
            ),
            (
                "role-type",
                lambda item: item["coverage"]["inventories"]["lexical_high"][0].update(
                    {"role": []}
                ),
                "lexical role is invalid",
            ),
            (
                "hunk-id-type",
                lambda item: item["coverage"]["inventories"]["lexical_high"][0][
                    "disposition"
                ].update({"hunk_id": []}),
                "candidate disposition hunk_id is invalid",
            ),
            (
                "selection-disposition",
                lambda item: item["coverage"]["inventories"]["selected_spans"][0][
                    "disposition"
                ].update({"decision": "KEEP", "hunk_id": None}),
                "selected inventory does not match declarations",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                forged = json.loads(json.dumps(bundle))
                mutate(forged)
                coverage_unsigned = dict(forged["coverage"])
                coverage_unsigned.pop("coverage_sha256")
                forged["coverage"]["coverage_sha256"] = builder.sha256(
                    builder.canonical_json(coverage_unsigned)
                )
                forged["bundle_sha256"] = builder._bundle_hash(forged)
                with self.assertRaisesRegex(builder.ShortPatchError, expected):
                    builder.validate_bundle_payload(
                        forged,
                        self.source.read_bytes(),
                        require_current_coverage_policy=False,
                    )

    def test_coverage_scope_and_limitations_cannot_be_broadened_by_rehash(self) -> None:
        _bundle_path, bundle = self.build(self.valid_coverage_spec(), "coverage-claims.json")
        cases = (
            (
                "scope",
                lambda item: item["coverage"].update(
                    {"coverage_claim_scope": "ALL_SEMANTIC_PROBLEMS"}
                ),
                "claim fields are invalid",
            ),
            (
                "limitations",
                lambda item: item["coverage"].update({"coverage_limitations": []}),
                "coverage limitations are invalid",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                forged = json.loads(json.dumps(bundle))
                mutate(forged)
                coverage_unsigned = dict(forged["coverage"])
                coverage_unsigned.pop("coverage_sha256")
                forged["coverage"]["coverage_sha256"] = builder.sha256(
                    builder.canonical_json(coverage_unsigned)
                )
                forged["bundle_sha256"] = builder._bundle_hash(forged)
                with self.assertRaisesRegex(builder.ShortPatchError, expected):
                    builder.validate_bundle_payload(
                        forged,
                        self.source.read_bytes(),
                        require_current_coverage_policy=False,
                    )

    def test_legacy_v1_result_without_coverage_fields_remains_read_only_compatible(self) -> None:
        bundle_path, _bundle = self.build()
        output = self.root / "legacy-v1-output"
        applicator.apply_patch(self.source, bundle_path, output)
        result_path = output / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["schema_version"] = "humanize-short-patch-result/v1"
        result.pop("review_path")
        result["artifacts_written"].remove("review.md")
        for key in (
            "coverage_path",
            "coverage_status",
            "coverage_completion_claim_allowed",
            "semantic_completeness_claim_allowed",
            "coverage_claim_scope",
            "coverage_scene",
            "coverage_scan_scene",
            "coverage_source_kind",
            "delivery_gate_exit_code",
        ):
            result.pop(key)
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output / "review.md").unlink()
        manifest_path = output / "evidence-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"] = [
            item for item in manifest["artifacts"] if item["path"] != "review.md"
        ]
        manifest["manifest_sha256"] = verifier._manifest_hash(manifest)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.refresh_evidence_manifest(output, "result.json")
        verified = verifier.verify_directory(output)
        self.assertEqual("PASS", verified["status"])
        self.assertEqual("NOT_PROVIDED", verified["coverage_policy_status"])
        self.assertFalse(verified["coverage_completion_claim_allowed"])

    def test_verifier_rejects_rehashed_result_claims_unknown_paths_and_duplicate_artifacts(self) -> None:
        bundle_path, _bundle = self.build()
        baseline = self.root / "result-closure-baseline"
        applicator.apply_patch(self.source, bundle_path, baseline)
        cases = (
            ("semantic", lambda item: item.update({"semantic_judgment": "PASS"}), "semantic_judgment"),
            (
                "paired",
                lambda item: item.update({"paired_quality_review_status": "PASS"}),
                "paired_quality_review_status",
            ),
            (
                "path",
                lambda item: item.update({"source_path": "C:/private/source.tex"}),
                "result fields drifted",
            ),
            (
                "duplicate-artifact",
                lambda item: item["artifacts_written"].append(item["artifacts_written"][0]),
                "artifacts_written",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                output = self.root / f"result-closure-{label}"
                shutil.copytree(baseline, output)
                result_path = output / "result.json"
                result = json.loads(result_path.read_text(encoding="utf-8"))
                mutate(result)
                result_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                self.refresh_evidence_manifest(output, "result.json")
                with self.assertRaisesRegex(verifier.ShortPatchError, expected):
                    verifier.verify_directory(output)

    def test_ltx_source_is_validated_and_published_as_tex(self) -> None:
        self.source = self.root / "source.ltx"
        self.source.write_text("值得注意的是，结果变化。\n", encoding="utf-8")
        payload = self.valid_coverage_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [payload["hunks"][0]]
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [],
        }
        bundle_path, bundle = self.build(payload, "ltx-bundle.json")
        output = self.root / "ltx-output"
        result = applicator.apply_patch(self.source, bundle_path, output)
        validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
        self.assertEqual("tex", bundle["document_format"])
        self.assertEqual("candidate.review.tex", result["candidate_path"])
        self.assertEqual("tex", validation["evidence"]["document_format"])

    def test_txt_source_with_explicit_tex_comment_change_is_rejected(self) -> None:
        self.source = self.root / "source.txt"
        self.source.write_text("这里保留原有结论。\n", encoding="utf-8")
        payload = self.valid_coverage_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "这里保留原有结论。",
                "start_byte": None,
                "replacement": "这里保留原有结论。% 新增注释",
                "reason": "恶意测试显式 TeX 格式不能在应用阶段退化为 Markdown。",
            }
        ]
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [],
        }
        spec = self.write_spec(payload)
        bundle_path = self.root / "txt-tex-bundle.json"
        bundle = builder.build_bundle(
            self.source,
            spec,
            bundle_path,
            document_format="tex",
        )
        output = self.root / "txt-tex-output"

        self.assertEqual("tex", bundle["document_format"])
        with self.assertRaisesRegex(
            applicator.ShortPatchError,
            "UNIFIED_VALIDATOR_FAILED",
        ):
            applicator.apply_patch(self.source, bundle_path, output)
        self.assertFalse(output.exists())

    def test_verifier_rejects_validation_format_different_from_bound_bundle(self) -> None:
        self.source = self.root / "source.txt"
        self.source.write_text("这里保留原有结论。\n", encoding="utf-8")
        payload = self.valid_coverage_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "这里保留原有结论。",
                "start_byte": None,
                "replacement": "这里仍保留原有结论。",
                "reason": "构造可发布记录以检查验证格式与 bundle 的闭合绑定。",
            }
        ]
        payload["coverage"] = {
            "source_kind": "DOCUMENT",
            "lexical_keeps": [],
            "selected_spans": [],
            "explicit_conflicts": [],
        }
        spec = self.write_spec(payload)
        bundle_path = self.root / "format-binding-bundle.json"
        builder.build_bundle(
            self.source,
            spec,
            bundle_path,
            document_format="tex",
        )
        output = self.root / "format-binding-output"
        applicator.apply_patch(self.source, bundle_path, output)

        validation_path = output / "validation.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        self.assertEqual("tex", validation["evidence"]["document_format"])
        validation["evidence"]["document_format"] = "markdown"
        validation_path.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.refresh_evidence_manifest(output, "validation.json")

        with self.assertRaisesRegex(
            verifier.ShortPatchError,
            "document_format does not match",
        ):
            verifier.verify_directory(output)

    def test_inline_scope_requires_selection_and_report_scope_cannot_self_assert(self) -> None:
        payload = self.valid_coverage_spec()
        payload["coverage"]["source_kind"] = "INLINE_SELECTION"
        payload["coverage"]["selected_spans"] = []
        with self.assertRaisesRegex(builder.ShortPatchError, "BOUND_SELECTION_REQUIRED"):
            self.build(payload, "inline-selection.json")

        payload = self.valid_coverage_spec()
        payload["coverage"]["source_kind"] = "REPORT_SELECTION"
        with self.assertRaisesRegex(builder.ShortPatchError, "source_kind is invalid"):
            self.build(payload, "report-selection.json")

    def test_hard_invariant_failure_rolls_back_all_candidate_artifacts(self) -> None:
        self.source.write_text("设 $x=1$，则结果成立。\n", encoding="utf-8")
        payload = self.valid_spec()
        payload["scene"] = "GENERAL"
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "$x=1$",
                "start_byte": None,
                "replacement": "$x=2$",
                "reason": "恶意测试不得改动公式保护区。",
            }
        ]
        bundle_path, _bundle = self.build(payload)
        output = self.root / "formula-must-fail"

        with self.assertRaisesRegex(applicator.ShortPatchError, "UNIFIED_VALIDATOR_FAILED"):
            applicator.apply_patch(self.source, bundle_path, output)
        self.assertFalse(output.exists())
        self.assertEqual("设 $x=1$，则结果成立。\n", self.source.read_text(encoding="utf-8"))

    def test_explicit_protected_term_is_bound_and_cannot_be_changed(self) -> None:
        self.source.write_text("本文采用 ABC 方法处理数据。\n", encoding="utf-8")
        payload = self.valid_spec()
        payload["scene"] = "GENERAL"
        payload["protected_terms"] = ["ABC 方法"]
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "ABC 方法",
                "start_byte": None,
                "replacement": "ABD 方法",
                "reason": "恶意测试不得改动显式保护术语。",
            }
        ]
        spec = self.write_spec(payload)
        bundle_path = self.root / "term-patch.json"
        builder.build_bundle(self.source, spec, bundle_path)
        with self.assertRaisesRegex(applicator.ShortPatchError, "UNIFIED_VALIDATOR_FAILED"):
            applicator.apply_patch(self.source, bundle_path, self.root / "term-output")
        self.assertFalse((self.root / "term-output").exists())
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.assertEqual(["ABC 方法"], bundle["protected_terms"])

    def fake_validator_payload(
        self,
        before: bytes,
        after: bytes,
        *,
        mechanical: str = "PASS",
    ) -> bytes:
        payload = {
            "delivery_gate_status": "REVIEW",
            "exit_code": 2,
            "mechanical_validation_status": mechanical,
            "hard_invariant_layer_status": "PASS",
            "paired_quality_review_status": "PENDING_EXTERNAL_REVIEW",
            "evidence": {
                "before_sha256": builder.sha256(before),
                "after_sha256": builder.sha256(after),
            },
        }
        return json.dumps(payload).encode("utf-8")

    def test_validator_reads_frozen_source_snapshot_not_live_source_path(self) -> None:
        bundle_path, _bundle = self.build()
        original = self.source.read_bytes()
        observed: dict[str, Path] = {}

        def fake_run(argv, **_kwargs):
            before_path = Path(argv[2])
            after_path = Path(argv[3])
            observed["before"] = before_path
            self.assertNotEqual(self.source.resolve(), before_path.resolve())
            self.assertEqual(original, before_path.read_bytes())
            return subprocess.CompletedProcess(
                argv,
                2,
                stdout=self.fake_validator_payload(before_path.read_bytes(), after_path.read_bytes()),
                stderr=b"",
            )

        with mock.patch.object(applicator.subprocess, "run", side_effect=fake_run):
            applicator.apply_patch(self.source, bundle_path, self.root / "snapshot-output")
        self.assertIn("before", observed)
        self.assertTrue((self.root / "snapshot-output" / "source.snapshot.bin").is_file())

    def test_validator_hash_mismatch_or_mechanical_fail_cannot_publish(self) -> None:
        bundle_path, _bundle = self.build()

        def wrong_hash(argv, **_kwargs):
            after = Path(argv[3]).read_bytes()
            return subprocess.CompletedProcess(
                argv,
                2,
                stdout=self.fake_validator_payload(b"wrong-before", after),
                stderr=b"",
            )

        with mock.patch.object(applicator.subprocess, "run", side_effect=wrong_hash):
            with self.assertRaisesRegex(applicator.ShortPatchError, "EVIDENCE_HASH_MISMATCH"):
                applicator.apply_patch(self.source, bundle_path, self.root / "wrong-hash-output")
        self.assertFalse((self.root / "wrong-hash-output").exists())

        def mechanical_fail(argv, **_kwargs):
            before = Path(argv[2]).read_bytes()
            after = Path(argv[3]).read_bytes()
            return subprocess.CompletedProcess(
                argv,
                2,
                stdout=self.fake_validator_payload(before, after, mechanical="FAIL"),
                stderr=b"",
            )

        with mock.patch.object(applicator.subprocess, "run", side_effect=mechanical_fail):
            with self.assertRaisesRegex(applicator.ShortPatchError, "RESULT_INCONSISTENT"):
                applicator.apply_patch(self.source, bundle_path, self.root / "mechanical-fail-output")
        self.assertFalse((self.root / "mechanical-fail-output").exists())

    def test_utf8_bom_and_crlf_survive_unlisted_source_copy(self) -> None:
        raw = b"\xef\xbb\xbf" + "甲。\r\n乙。\r\n".encode("utf-8")
        self.source.write_bytes(raw)
        payload = self.valid_spec()
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "乙",
                "start_byte": None,
                "replacement": "丙",
                "reason": "只替换第二行正文字符。",
            }
        ]
        bundle_path, _bundle = self.build(payload)
        out = self.root / "bom-output"
        applicator.apply_patch(self.source, bundle_path, out)
        candidate = (out / "candidate.review.tex").read_bytes()
        self.assertTrue(candidate.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(b"\xef\xbb\xbf" + "甲。\r\n丙。\r\n".encode("utf-8"), candidate)

    def test_crlf_grapheme_boundaries_and_new_bidi_controls_are_rejected(self) -> None:
        cases = (
            ("甲。\r\n乙。", "\r", "", "CRLF"),
            ("Cafe\u0301。", "e", "E", "grapheme"),
            ("正文。", "正文", "正\u202e文", "bidi"),
        )
        for index, (source_text, selected, replacement, message) in enumerate(cases):
            with self.subTest(message=message):
                self.source.write_text(source_text, encoding="utf-8", newline="")
                payload = self.valid_spec()
                payload["hunks"] = [
                    {
                        "hunk_id": "H001",
                        "decision": "DELETE_STYLE_SHELL" if replacement == "" else "REWRITE",
                        "source_text": selected,
                        "start_byte": None,
                        "replacement": replacement,
                        "reason": "验证边界和不可见控制字符门。",
                    }
                ]
                spec = self.write_spec(payload, f"boundary-{index}.json")
                with self.assertRaisesRegex(builder.ShortPatchError, message):
                    builder.build_bundle(
                        self.source,
                        spec,
                        self.root / f"boundary-{index}-bundle.json",
                    )

    def test_repeated_source_text_requires_explicit_start_byte(self) -> None:
        self.source.write_text("重复，重复。", encoding="utf-8")
        payload = self.valid_spec()
        payload["hunks"] = [
            {
                "hunk_id": "H001",
                "decision": "REWRITE",
                "source_text": "重复",
                "start_byte": None,
                "replacement": "复核",
                "reason": "测试重复选择必须显式定位。",
            }
        ]
        with self.assertRaisesRegex(builder.ShortPatchError, "ambiguous") as caught:
            self.build(payload)
        self.assertIn("candidate_start_bytes=[0, 9]", str(caught.exception))

    def test_overlap_duplicate_and_out_of_order_hunks_fail_before_output(self) -> None:
        self.source.write_text("abcdef", encoding="utf-8")
        base = {
            "schema_version": "humanize-short-patch-selection/v1",
            "requested_output": "PATCH",
            "mode": "REWRITE",
            "scene": "GENERAL",
            "intensity": "LIGHT",
            "protected_terms": [],
        }
        cases = {
            "overlap": [
                {"hunk_id": "H001", "decision": "REWRITE", "source_text": "abc", "start_byte": 0, "replacement": "ABC", "reason": "改写第一个跨度。"},
                {"hunk_id": "H002", "decision": "UNRESOLVED", "source_text": "bc", "start_byte": 1, "replacement": "bc", "reason": "重叠跨度保持未决。"},
            ],
            "duplicate": [
                {"hunk_id": "H001", "decision": "REWRITE", "source_text": "abc", "start_byte": 0, "replacement": "ABC", "reason": "第一次改写。"},
                {"hunk_id": "H002", "decision": "UNRESOLVED", "source_text": "abc", "start_byte": 0, "replacement": "abc", "reason": "同一跨度重复登记。"},
            ],
            "out_of_order": [
                {"hunk_id": "H001", "decision": "REWRITE", "source_text": "def", "start_byte": 3, "replacement": "DEF", "reason": "后面的跨度先登记。"},
                {"hunk_id": "H002", "decision": "REWRITE", "source_text": "abc", "start_byte": 0, "replacement": "ABC", "reason": "前面的跨度后登记。"},
            ],
        }
        for label, hunks in cases.items():
            with self.subTest(label=label):
                output = self.root / f"{label}.json"
                spec = self.write_spec({**base, "hunks": hunks}, f"{label}-selection.json")
                with self.assertRaisesRegex(builder.ShortPatchError, "overlap|order|duplicate"):
                    builder.build_bundle(self.source, spec, output)
                self.assertFalse(output.exists())

    def test_decision_replacement_contract_is_fail_closed(self) -> None:
        bad_values = (
            ("DELETE_STYLE_SHELL", "不应出现", "DELETE_STYLE_SHELL"),
            ("UNRESOLVED", "被改写", "UNRESOLVED"),
            ("REWRITE", "先读题", "REWRITE"),
            ("REWRITE", "", "REWRITE"),
        )
        for index, (decision, replacement, message) in enumerate(bad_values):
            with self.subTest(decision=decision, replacement=replacement):
                payload = self.valid_spec()
                payload["hunks"] = [
                    {
                        "hunk_id": "H001",
                        "decision": decision,
                        "source_text": "先读题",
                        "start_byte": None,
                        "replacement": replacement,
                        "reason": "验证动作与替换文本的一致性。",
                    }
                ]
                spec = self.write_spec(payload, f"bad-{index}.json")
                with self.assertRaisesRegex(builder.ShortPatchError, message):
                    builder.build_bundle(self.source, spec, self.root / f"bad-{index}-bundle.json")

    def test_rewrite_scope_is_bounded_to_one_local_sentence(self) -> None:
        builder._validate_rewrite_scope("REWRITE", "单句可以改写。", "single")
        builder._validate_rewrite_scope("UNRESOLVED", "第一句。第二句。", "unresolved")

        rejected = (
            ("第一句。第二句。", "multiple sentence boundaries"),
            ("结论提高。结论下降", "multiple sentence boundaries"),
            ("第一行\n第二行", "line boundary"),
            ("甲" * 401, "1200-byte"),
        )
        for source_text, message in rejected:
            with self.subTest(message=message):
                with self.assertRaisesRegex(builder.ShortPatchError, message):
                    builder._validate_rewrite_scope("REWRITE", source_text, "bounded")

    def test_source_or_bundle_drift_never_publishes_output(self) -> None:
        bundle_path, _bundle = self.build()
        self.source.write_bytes(self.source.read_bytes() + b"later")
        with self.assertRaisesRegex(applicator.ShortPatchError, "source_sha256"):
            applicator.apply_patch(self.source, bundle_path, self.root / "source-drift")
        self.assertFalse((self.root / "source-drift").exists())

        self.source.write_bytes(self.source_text.encode("utf-8"))
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        payload["hunks"][0]["reason"] = "tampered"
        bundle_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(applicator.ShortPatchError, "bundle_sha256"):
            applicator.apply_patch(self.source, bundle_path, self.root / "bundle-drift")
        self.assertFalse((self.root / "bundle-drift").exists())

    def test_strict_json_rejects_duplicate_unknown_float_and_invalid_utf8(self) -> None:
        valid = self.valid_spec()
        cases = {
            "duplicate": b'{"schema_version":"humanize-short-patch-selection/v1","schema_version":"humanize-short-patch-selection/v1"}',
            "unknown": json.dumps({**valid, "surprise": True}, ensure_ascii=False).encode("utf-8"),
            "float": json.dumps({**valid, "hunks": [{**valid["hunks"][0], "start_byte": 0.0}]}, ensure_ascii=False).encode("utf-8"),
            "invalid_utf8": b"\xff\xfe{",
        }
        for label, raw in cases.items():
            with self.subTest(label=label):
                spec = self.root / f"strict-{label}.json"
                spec.write_bytes(raw)
                with self.assertRaisesRegex(builder.ShortPatchError, "duplicate|fields|integer|UTF-8|JSON"):
                    builder.build_bundle(self.source, spec, self.root / f"strict-{label}-bundle.json")

    def test_apply_rejects_unknown_bundle_field_before_writing(self) -> None:
        bundle_path, bundle = self.build()
        bundle["unexpected"] = "value"
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(applicator.ShortPatchError, "fields"):
            applicator.apply_patch(self.source, bundle_path, self.root / "unknown-out")
        self.assertFalse((self.root / "unknown-out").exists())

    def test_inputs_and_existing_outputs_are_never_overwritten(self) -> None:
        spec = self.write_spec()
        source_before = self.source.read_bytes()
        spec_before = spec.read_bytes()
        bundle_path = self.root / "patch.json"
        bundle_path.write_text("occupied", encoding="utf-8")
        with self.assertRaisesRegex(builder.ShortPatchError, "output_exists") as caught:
            builder.build_bundle(self.source, spec, bundle_path)
        self.assertNotIn(str(self.root), str(caught.exception))
        self.assertEqual(source_before, self.source.read_bytes())
        self.assertEqual(spec_before, spec.read_bytes())
        self.assertEqual("occupied", bundle_path.read_text(encoding="utf-8"))

        bundle_path.unlink()
        builder.build_bundle(self.source, spec, bundle_path)
        output_dir = self.root / "existing"
        output_dir.mkdir()
        marker = output_dir / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(applicator.ShortPatchError, "output_exists"):
            applicator.apply_patch(self.source, bundle_path, output_dir)
        self.assertEqual("keep", marker.read_text(encoding="utf-8"))
        self.assertEqual(source_before, self.source.read_bytes())

    def test_hardlinked_source_is_rejected_before_bundle_write(self) -> None:
        hardlink = self.root / "source-hardlink.tex"
        os.link(self.source, hardlink)
        spec = self.write_spec()
        output = self.root / "hardlink-bundle.json"
        with self.assertRaisesRegex(builder.ShortPatchError, "hardlink"):
            builder.build_bundle(hardlink, spec, output)
        self.assertFalse(output.exists())

    def test_symlinked_source_or_output_parent_is_rejected(self) -> None:
        source_link = self.root / "source-link.tex"
        real_output_parent = self.root / "real-output-parent"
        output_parent_link = self.root / "output-parent-link"
        real_output_parent.mkdir()
        try:
            source_link.symlink_to(self.source)
            output_parent_link.symlink_to(real_output_parent, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink creation unavailable: {error}")
        spec = self.write_spec()
        with self.assertRaisesRegex(builder.ShortPatchError, "symlink|reparse"):
            builder.build_bundle(source_link, spec, self.root / "symlink-source-bundle.json")
        with self.assertRaisesRegex(builder.ShortPatchError, "symlink|reparse"):
            builder.build_bundle(
                self.source,
                spec,
                output_parent_link / "patch.json",
            )
        self.assertFalse((real_output_parent / "patch.json").exists())

    def test_cli_exposes_machine_status_and_review_exit_code(self) -> None:
        spec = self.write_spec()
        bundle = self.root / "cli-patch.json"
        built = subprocess.run(
            [sys.executable, str(BUILDER_PATH), str(self.source), "--selection-spec", str(spec), "--output", str(bundle), "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, built.returncode, built.stderr + built.stdout)
        self.assertEqual("BUNDLED", json.loads(built.stdout)["status"])

        applied = subprocess.run(
            [sys.executable, str(APPLICATOR_PATH), str(self.source), "--bundle", str(bundle), "--output", str(self.root / "cli-out"), "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, applied.returncode, applied.stderr + applied.stdout)
        result = json.loads(applied.stdout)
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertFalse(result["humanize_quality_claim_allowed"])

        text_run = subprocess.run(
            [sys.executable, str(APPLICATOR_PATH), str(self.source), "--bundle", str(bundle), "--output", str(self.root / "cli-text-out"), "--format", "text"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, text_run.returncode, text_run.stderr + text_run.stdout)
        self.assertIn("unified_validator=", text_run.stdout)
        self.assertNotIn("unified_validator=NOT_RUN", text_run.stdout)
        self.assertIn("coverage=NOT_PROVIDED", text_run.stdout)

        verified = subprocess.run(
            [sys.executable, str(VERIFIER_PATH), str(self.root / "cli-text-out"), "--format", "text"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, verified.returncode, verified.stderr + verified.stdout)
        self.assertTrue(verified.stdout.startswith("INTEGRITY PASS"))
        self.assertIn("CURRENT_POLICY_REPLAY PASS", verified.stdout)
        self.assertIn("COVERAGE NOT_PROVIDED", verified.stdout)
        self.assertIn("DELIVERY REVIEW", verified.stdout)

        self.source.write_text("源文件已在证据发布后改变。", encoding="utf-8")
        live_drift = subprocess.run(
            [
                sys.executable,
                str(VERIFIER_PATH),
                str(self.root / "cli-text-out"),
                "--live-source",
                str(self.source),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, live_drift.returncode, live_drift.stderr + live_drift.stdout)
        live_payload = json.loads(live_drift.stdout)
        self.assertEqual("REVIEW", live_payload["status"])
        self.assertEqual("PASS", live_payload["record_integrity_status"])
        self.assertEqual("PASS", live_payload["current_policy_replay_status"])
        self.assertEqual(
            "CALLER_SUPPLIED_NOT_CURRENT",
            live_payload["live_source_status"]["status"],
        )
        self.assertFalse(live_payload["live_source_status"]["freshness_claim_allowed"])
        self.assertNotIn(str(self.source), live_drift.stdout)

        invalid = subprocess.run(
            [
                sys.executable,
                str(VERIFIER_PATH),
                str(self.root / "cli-text-out"),
                "--format",
                "invalid",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(1, invalid.returncode, invalid.stderr + invalid.stdout)
        self.assertEqual("", invalid.stderr)
        self.assertIn("VERIFICATION FAIL exit=1", invalid.stdout)
        self.assertNotIn(str(self.root), invalid.stdout)

    def test_v2_builder_cli_reports_actual_schema_and_coverage(self) -> None:
        spec = self.write_spec(self.valid_coverage_spec(), "coverage-cli-selection.json")
        bundle = self.root / "coverage-cli-bundle.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(BUILDER_PATH),
                str(self.source),
                "--selection-spec",
                str(spec),
                "--output",
                str(bundle),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stderr + completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual("humanize-short-patch/v2", payload["schema_version"])
        self.assertEqual("PASS", payload["coverage_status"])
        self.assertTrue(payload["coverage_completion_claim_allowed"])
        self.assertEqual(
            "ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY",
            payload["coverage_claim_scope"],
        )
        self.assertEqual("COURSE", payload["coverage_scene"])
        self.assertEqual("AUTO", payload["coverage_scan_scene"])
        self.assertEqual("DOCUMENT", payload["coverage_source_kind"])

    def test_generator_projection_policy_includes_short_patch_tools(self) -> None:
        policy = json.loads(
            (SKILL / "references" / "generator-projection-policy.json").read_text(encoding="utf-8")
        )
        for relative in (
            "references/short-patch-workflow.md",
            "scripts/amend_humanize_short_patch.py",
            "scripts/build_humanize_short_patch.py",
            "scripts/apply_humanize_short_patch.py",
            "scripts/verify_humanize_short_patch.py",
            "scripts/humanize_short_patch_coverage.py",
        ):
            self.assertIn(relative, policy["include_exact"])

        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL / "references" / "short-patch-workflow.md").read_text(encoding="utf-8")
        self.assertIn("short-patch-workflow.md", skill_text)
        self.assertIn("humanize-short-patch-selection/v1", reference)
        self.assertIn("humanize-short-patch-selection/v2", reference)
        self.assertIn("coverage_completion_claim_allowed", reference)
        self.assertIn("NO_COMPLETE_NATURAL_LANGUAGE_SEMANTIC_DISCOVERY", reference)
        self.assertIn("humanize-short-patch/v1", reference)
        self.assertIn("humanize-short-patch/v3", reference)
        self.assertIn("DELIVERY REVIEW exit=2", reference)
        self.assertIn("CURRENT_POLICY_REPLAY", reference)
        self.assertIn("--live-source", reference)
        self.assertIn("不得覆盖源文件", reference)


if __name__ == "__main__":
    unittest.main()
