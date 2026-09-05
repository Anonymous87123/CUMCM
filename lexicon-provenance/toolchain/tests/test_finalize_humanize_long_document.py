import ast
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import concurrent.futures
from pathlib import Path
from unittest import mock


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


preparer = load_module(
    "prepare_humanize_long_document",
    SKILL / "scripts" / "prepare_humanize_long_document.py",
)
finalizer = load_module(
    "finalize_humanize_long_document",
    SKILL / "scripts" / "finalize_humanize_long_document.py",
)
scaffolder = load_module(
    "scaffold_humanize_rewrites",
    SKILL / "scripts" / "scaffold_humanize_rewrites.py",
)


def _directory_bytes(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class LongDocumentFinalizationTests(unittest.TestCase):
    COMPILE_CHECK_FIELDS = {
        "status",
        "command",
        "exit_code",
        "stdout",
        "stderr",
        "cwd",
        "integrity_status",
        "integrity_changes",
        "process_containment",
        "descendant_cleanup",
        "timed_out",
        "timeout_seconds",
    }

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def prepare(
        self, text: str, *, intensity: str = "BALANCED"
    ) -> tuple[Path, Path, dict]:
        source = self.root / "main.tex"
        source.write_text(text, encoding="utf-8")
        run_dir = self.root / "run"
        preparer.prepare(
            [source],
            run_dir,
            scene="COURSE",
            intensity=intensity,
            min_author_chars=0,
        )
        chunks = [json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "chunks").glob("*.json")]
        pending = next(item for item in chunks if item["status"] == "PENDING")
        return source, run_dir, pending

    def prepare_markdown_unit(
        self,
        text: str,
        *,
        intensity: str = "BALANCED",
        name: str = "source",
    ) -> tuple[Path, Path, dict]:
        source = self.root / f"{name}.md"
        source.write_text(text, encoding="utf-8")
        run_dir = self.root / f"run-{name}"
        preparer.prepare(
            [source],
            run_dir,
            scene="GENERAL",
            intensity=intensity,
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
        ]
        pending = next(item for item in chunks if item["status"] == "PENDING")
        return source, run_dir, pending

    def rewrite_dir(self) -> Path:
        path = self.root / "rewrites"
        path.mkdir(exist_ok=True)
        return path

    def valid_v5_no_change_scaffold(self) -> tuple[Path, Path, dict, Path]:
        source, run_dir, pending = self.prepare(
            "\\section{定义}\n该定义保持原有条件范围和说明结构。\n"
        )
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "NO_CHANGE")
        bundle_path = rewrites / f"{pending['unit_id']}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["reason"] = "正式定义段落保留原有条件范围和说明结构"
        bundle["evidence_spans"] = [
            self.masked_line_span(pending["masked_text"], "该定义")
        ]
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return source, run_dir, pending, rewrites

    def test_scaffold_metadata_is_validated_and_not_collected_as_a_unit(self) -> None:
        _, run_dir, pending = self.prepare("这是一段可以保持原样的正文。")
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "NO_CHANGE")
        bundle_path = rewrites / f"{pending['unit_id']}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["reason"] = "原文结构自然"
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        rewrites_map, transactions, declines = finalizer.collect_rewrites(rewrites)

        self.assertEqual({pending["unit_id"]}, set(rewrites_map))
        self.assertEqual({}, transactions)
        self.assertEqual({}, declines)
        result = finalizer.finalize(run_dir, rewrites)
        self.assertNotIn("unknown rewrite units", " ".join(result.get("errors", [])))
        self.assertEqual("REVIEW", result["status"])

    def test_malformed_scaffold_metadata_is_not_silently_ignored(self) -> None:
        rewrites = self.rewrite_dir()
        (rewrites / "scaffold_metadata.json").write_text(
            json.dumps({"schema_version": "humanize-rewrite-scaffold/v1"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "scaffold metadata"):
            finalizer.collect_rewrites(rewrites)

    def test_scaffold_metadata_rejects_invalid_template_hash(self) -> None:
        _, run_dir, _ = self.prepare("这是一段可以保持原样的正文。")
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "NO_CHANGE")
        metadata_path = rewrites / "scaffold_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["records"][0]["template_sha256"] = "CALLER-FORGED-NOT-A-HASH"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "template hash"):
            finalizer.collect_rewrites(rewrites)

    def test_v5_scaffold_live_source_drift_remains_review_two(self) -> None:
        source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        source.write_text(
            source.read_text(encoding="utf-8") + "% external drift\n",
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        self.assertFalse(result.get("runtime_error", False))
        self.assertEqual(1, result["source_files_changed_since_snapshot"])
        self.assertEqual("MODIFIED", result["source_change_details"][0]["current_state"])

    def test_v5_scaffold_requires_publication_commit(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        (rewrites / finalizer.SCAFFOLD_COMMITTED_MARKER_NAME).unlink()

        with self.assertRaisesRegex(ValueError, "missing publication commit"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def test_v5_scaffold_rejects_tampered_publication_commit(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        marker_path = rewrites / finalizer.SCAFFOLD_COMMITTED_MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["scaffold_metadata_sha256"] = "f" * 64
        marker_path.write_text(
            json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "metadata hash mismatch"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def test_v5_scaffold_rejects_invalid_publication_commit_schema(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        marker_path = rewrites / finalizer.SCAFFOLD_COMMITTED_MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["schema_version"] = "humanize-scaffold-publication-commit/v999"
        marker_path.write_text(
            json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "publication commit schema"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def test_v5_scaffold_rejects_hardlinked_publication_commit(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        marker_path = rewrites / finalizer.SCAFFOLD_COMMITTED_MARKER_NAME
        os.link(marker_path, self.root / "commit-marker-alias")

        with self.assertRaisesRegex(ValueError, "standalone regular file"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def test_v5_scaffold_rejects_linked_publication_commit(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        marker_path = rewrites / finalizer.SCAFFOLD_COMMITTED_MARKER_NAME
        original = self.root / "commit-marker-original"
        marker_path.rename(original)
        try:
            os.symlink(original, marker_path)
        except OSError as error:
            original.rename(marker_path)
            self.skipTest(f"file symlinks unavailable: {error}")

        with self.assertRaisesRegex(ValueError, "commit must not be a link"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def test_v5_scaffold_rejects_residual_uncommitted_marker(self) -> None:
        _source, run_dir, _pending, rewrites = self.valid_v5_no_change_scaffold()
        (rewrites / finalizer.SCAFFOLD_UNCOMMITTED_MARKER_NAME).write_text(
            "{}\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "publication is uncommitted"):
            finalizer.collect_rewrites(rewrites, run_dir=run_dir)

    def voice_bound_bundle(self, unit: dict, payload: dict) -> dict:
        return {
            "unit_id": unit["unit_id"],
            "chunk_binding_sha256": unit["chunk_binding_sha256"],
            "voice_profile_sha256": unit["voice_profile_sha256"],
            **payload,
        }

    def authoring_bound_bundle(
        self,
        run_dir: Path,
        unit: dict,
        payload: dict,
    ) -> dict:
        preflight = finalizer.validate_long_authoring_snapshot(run_dir)
        binding = preflight["bindings"][unit["unit_id"]]
        return self.voice_bound_bundle(
            unit,
            {
                **payload,
                "schema_version": finalizer.UNIT_REWRITE_BUNDLE_SCHEMA,
                "authoring_binding": binding,
                "template_field_edit_scope": None,
            },
        )

    def masked_line_span(
        self,
        masked_text: str,
        needle: str,
        *,
        span_id: str = "S1",
    ) -> dict:
        lines = masked_text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
            keepends=True
        )
        line_number = next(
            index for index, line in enumerate(lines, 1) if needle in line
        )
        return {
            "id": span_id,
            "start_line": line_number,
            "end_line": line_number,
            "sha256": hashlib.sha256(
                lines[line_number - 1].encode("utf-8")
            ).hexdigest(),
        }

    def masked_line_range_span(
        self,
        masked_text: str,
        start_needle: str,
        end_needle: str,
        *,
        span_id: str = "S1",
    ) -> dict:
        lines = masked_text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
            keepends=True
        )
        start_line = next(
            index for index, line in enumerate(lines, 1) if start_needle in line
        )
        end_line = next(
            index
            for index, line in enumerate(lines[start_line - 1 :], start_line)
            if end_needle in line
        )
        return {
            "id": span_id,
            "start_line": start_line,
            "end_line": end_line,
            "sha256": hashlib.sha256(
                "".join(lines[start_line - 1 : end_line]).encode("utf-8")
            ).hexdigest(),
        }

    def test_v35_rewrite_intent_source_spans_form_an_ordered_nonoverlapping_partition(self) -> None:
        digest = "a" * 64
        cases = {
            "range_duplicate": [
                {"id": "S1", "start_line": 1, "end_line": 2, "sha256": digest},
                {"id": "S2", "start_line": 1, "end_line": 2, "sha256": digest},
            ],
            "overlap": [
                {"id": "S1", "start_line": 1, "end_line": 2, "sha256": digest},
                {"id": "S2", "start_line": 2, "end_line": 3, "sha256": digest},
            ],
            "out_of_order": [
                {"id": "S1", "start_line": 3, "end_line": 3, "sha256": digest},
                {"id": "S2", "start_line": 1, "end_line": 1, "sha256": digest},
            ],
        }
        for error, spans in cases.items():
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    finalizer._validate_intent_span_shape(
                        spans,
                        "rewrite_intent_source_spans",
                    )

        finalizer._validate_intent_span_shape(
            [
                {"id": "S1", "start_line": 1, "end_line": 1, "sha256": digest},
                {"id": "S2", "start_line": 2, "end_line": 3, "sha256": digest},
            ],
            "rewrite_intent_source_spans",
        )

    def v3_rewrite_bundle(
        self,
        run_dir: Path,
        unit: dict,
        *,
        masked_text: str,
        source_span: dict,
        summary: str = "删除空泛收尾并保留材料范围",
        target_signal: str = "STYLE-EMPTY-ENDING",
    ) -> dict:
        return self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "REWRITE",
                "masked_text": masked_text,
                "keep_reasons": {},
                "rewrite_intent": {
                    "summary": summary,
                    "operations": [
                        {
                            "id": "O1",
                            "kind": "REWRITE_STYLE_SHELL",
                            "source_span_ids": [source_span["id"]],
                            "target_signals": [target_signal],
                            "summary": summary,
                        }
                    ],
                    "source_spans": [source_span],
                    "target_signals": [target_signal],
                },
            },
        )

    def v3_topology_bundle(
        self,
        run_dir: Path,
        unit: dict,
        *,
        masked_text: str,
        source_span: dict,
        operation_kind: str,
        target_signal: str,
        summary: str,
    ) -> dict:
        return self.v3_rewrite_bundle(
            run_dir,
            unit,
            masked_text=masked_text,
            source_span=source_span,
            summary=summary,
            target_signal=target_signal,
        ) | {
            "rewrite_intent": {
                "summary": summary,
                "operations": [
                    {
                        "id": "O1",
                        "kind": operation_kind,
                        "source_span_ids": [source_span["id"]],
                        "target_signals": [target_signal],
                        "summary": summary,
                    }
                ],
                "source_spans": [source_span],
                "target_signals": [target_signal],
            }
        }

    def test_rewrite_intent_target_signal_prefix_contract_is_explicit(self) -> None:
        digest = hashlib.sha256(b"source").hexdigest()

        def intent(signal: str) -> dict:
            return {
                "summary": "调整课程讲解段的节奏但不改变条件范围",
                "operations": [
                    {
                        "id": "O1",
                        "kind": "REWRITE_STYLE_SHELL",
                        "source_span_ids": ["S1"],
                        "target_signals": [signal],
                        "summary": "调整课程讲解段的节奏但不改变条件范围",
                    }
                ],
                "source_spans": [
                    {
                        "id": "S1",
                        "start_line": 1,
                        "end_line": 1,
                        "sha256": digest,
                    }
                ],
                "target_signals": [signal],
            }

        finalizer._validate_rewrite_intent_shape(intent("SCENE-COURSE-RHYTHM"))
        with self.assertRaisesRegex(
            ValueError,
            "rewrite_intent_target_signals_invalid",
        ):
            finalizer._validate_rewrite_intent_shape(intent("COURSE-RHYTHM"))

    def test_v3_rewrite_intent_is_bound_to_source_diff_and_review_request(self) -> None:
        source_text = (
            "# 讨论\n\n"
            "材料范围限于已经登记的记录，随后用一句空泛说明结束。\n\n"
            "下一段保留原有对象与限定条件。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(source_text, name="intent-pass")
        span = self.masked_line_span(unit["masked_text"], "材料范围")
        revised = unit["masked_text"].replace(
            "随后用一句空泛说明结束", "相关说明仍限于这些记录"
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual(1, result["unit_statuses"]["DONE"])
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        self.assertEqual(1, result["rewrite_intent_units_pass"])
        record = result["rewrite_intent_evidence"][unit["unit_id"]]
        evidence = json.loads(
            (run_dir / record["path"]).read_text(encoding="utf-8")
        )
        request = result["paired_quality_review_requests"][unit["unit_id"]]
        diff_path = run_dir / evidence["diff"]["path"]
        self.assertEqual("PASS", evidence["status"])
        self.assertEqual(
            hashlib.sha256(diff_path.read_bytes()).hexdigest(),
            evidence["diff"]["sha256"],
        )
        self.assertEqual(
            request["request_sha256"],
            evidence["paired_quality_review_request_sha256"],
        )
        self.assertEqual(record["path"], request["rewrite_intent_evidence_path"])
        self.assertEqual("PASS", evidence["intent_diff_binding"]["status"])
        body = {
            key: value for key, value in evidence.items() if key != "evidence_sha256"
        }
        self.assertEqual(
            hashlib.sha256(
                finalizer._canonical_json(body).encode("utf-8")
            ).hexdigest(),
            evidence["evidence_sha256"],
        )

    def test_v4_unit_template_field_scope_is_source_bound_and_not_quality_clearance(
        self,
    ) -> None:
        source_text = (
            "\\section{议论文模板}\n"
            "适用题目：带有社会责任意义的题目,也包括个人成长类命题。\n"
            "这一段说明写作材料的适用范围。\n"
        )
        _, run_dir, unit = self.prepare(source_text)
        span = self.masked_line_span(unit["masked_text"], "适用题目")
        revised = unit["masked_text"].replace(
            "题目,也包括", "题目，也包括"
        )
        line = next(
            index
            for index, text in enumerate(
                unit["masked_text"].replace("\r\n", "\n").splitlines(),
                1,
            )
            if text.startswith("适用题目：")
        )
        bundle = self.v3_rewrite_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            summary="修正字段内中英文标点混用且保持适用范围不变",
            target_signal="SCENE-COURSE-RHYTHM",
        )
        bundle["template_field_edit_scope"] = {
            "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "permission_boundary": "PAYLOAD_ONLY",
            "edits": [
                {
                    "line": line,
                    "label": "适用题目",
                    "permission": "PAYLOAD_ONLY",
                    "reason": "原句字段内中英文标点混用，授权只修正逗号表达形式",
                }
            ],
        }
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(
                encoding="utf-8"
            )
        )
        scope_path = (
            run_dir
            / "validation"
            / f"{unit['unit_id']}.template-field-edit-scope.json"
        )
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        before_path = run_dir / "validation" / f"{unit['unit_id']}.before.tex"
        self.assertEqual(1, result["unit_statuses"]["DONE"])
        self.assertEqual("PASS", validation["mechanical_validation_status"])
        self.assertEqual("PASS", validation["template_field_layer_status"])
        self.assertEqual(
            "PASS", validation["template_field_edit_scope_check"]["status"]
        )
        self.assertEqual(
            ["TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED"],
            [item["code"] for item in validation["template_field_findings"]],
        )
        self.assertEqual(
            hashlib.sha256(before_path.read_bytes()).hexdigest(),
            scope["source_sha256"],
        )
        self.assertEqual("PENDING_EXTERNAL_REVIEW", validation["paired_quality_review_status"])
        self.assertFalse(
            validation["template_field_edit_scope_check"]["local_clearance_supported"]
        )

    def test_v4_unit_template_field_scope_bad_line_is_unresolved(self) -> None:
        source_text = (
            "\\section{议论文模板}\n"
            "适用题目：带有社会责任意义的题目,也包括个人成长类命题。\n"
            "这一段说明写作材料的适用范围。\n"
        )
        _, run_dir, unit = self.prepare(source_text)
        span = self.masked_line_span(unit["masked_text"], "适用题目")
        bundle = self.v3_rewrite_bundle(
            run_dir,
            unit,
            masked_text=unit["masked_text"].replace("题目,也包括", "题目，也包括"),
            source_span=span,
            summary="修正字段内中英文标点混用且保持适用范围不变",
            target_signal="SCENE-COURSE-RHYTHM",
        )
        bundle["template_field_edit_scope"] = {
            "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "permission_boundary": "PAYLOAD_ONLY",
            "edits": [
                {
                    "line": 1,
                    "label": "适用题目",
                    "permission": "PAYLOAD_ONLY",
                    "reason": "原句字段内中英文标点混用，授权只修正逗号表达形式",
                }
            ],
        }
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("invalid_template_field_edit_scope", row["notes"])
        self.assertIn("TEMPLATE_FIELD_EDIT_SCOPE_INVALID", row["unresolved_codes_json"])
        self.assertFalse(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").exists()
        )

    def test_v3_rewrite_intent_rejects_span_outside_actual_diff(self) -> None:
        source_text = (
            "# 讨论\n\n"
            "第一段说明材料范围与记录边界。\n\n"
            "第二段说明对象条件与来源状态。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-outside-diff"
        )
        span = self.masked_line_span(unit["masked_text"], "第二段")
        revised = unit["masked_text"].replace(
            "第一段说明材料范围与记录边界", "第一段只说明已登记材料的范围"
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("rewrite_intent_source_spans_outside_diff", row["notes"])
        self.assertEqual("FAIL", row["rewrite_intent_status"])

    def test_v3_rewrite_intent_rejects_undeclared_second_change(self) -> None:
        source_text = (
            "# 讨论\n\n"
            "第一段说明材料范围与记录边界。\n\n"
            "第二段说明对象条件与来源状态。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-extra-diff"
        )
        span = self.masked_line_span(unit["masked_text"], "第一段")
        revised = (
            unit["masked_text"]
            .replace("第一段说明材料范围与记录边界", "第一段只说明已登记材料的范围")
            .replace("第二段说明对象条件与来源状态", "第二段改写了未申报的内容")
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("rewrite_intent_diff_outside_declared_spans", row["notes"])

    def test_v3_no_change_rejects_generic_reason_even_with_bound_span(self) -> None:
        source_text = "# 定义\n\n正式定义保持对象、条件和并列结构。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-generic-no-change"
        )
        span = self.masked_line_span(unit["masked_text"], "正式定义")
        rewrites = self.rewrite_dir()
        bundle = self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "NO_CHANGE",
                "reason": "该段保持原有自然表达",
                "evidence_spans": [span],
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("NO_CHANGE_reason_invalid:generic_template", row["notes"])
        self.assertIn(
            "required=min_han_8+specific_function_anchor", row["notes"]
        )
        self.assertIn("reason_redacted=true", row["notes"])
        self.assertEqual(
            {
                "total": 1,
                "classified": 1,
                "unclassified": 0,
                "codes": {"generic_template": 1},
                "structured_code_schema": "humanize-unresolved-code/v1",
                "structured_code_source": "UNIT_UNRESOLVED_CODES",
                "structured_classified": 1,
                "structured_unclassified": 0,
                "structured_code_counts": {
                    "NO_CHANGE_REASON_GENERIC_TEMPLATE": 1
                },
                "details_artifact": "coverage_ledger.final.csv",
                "content_redacted": True,
            },
            result["unresolved_reason_summary"],
        )
        summary = finalizer._render_text_summary(result)
        self.assertIn("unresolved_details=coverage_ledger.final.csv", summary)
        self.assertIn("reason_codes[generic_template=1]", summary)
        self.assertNotIn("该段保持原有自然表达", summary)
        self.assertEqual(
            "PROCESSABLE_UNIT_ACCOUNTING_ONLY",
            result["processable_scope_complete_scope"],
        )
        self.assertTrue(
            result[
                "processable_scope_complete_does_not_mean_resolved_or_deliverable"
            ]
        )
        self.assertEqual(
            result,
            json.loads(
                (run_dir / "latest_attempt_metadata.json").read_text(
                    encoding="utf-8"
                )
            ),
        )

    def test_no_change_reason_diagnostics_are_specific_and_redacted(self) -> None:
        cases = {
            "保持原样": "too_short_han",
            "该段保持原有自然表达": "generic_template",
            "文字已经足够清楚无需再作调整": "missing_function_anchor",
        }
        for reason, issue in cases.items():
            with self.subTest(issue=issue):
                error = finalizer._no_change_reason_error(reason)
                self.assertEqual(
                    f"NO_CHANGE_reason_invalid:{issue};"
                    "required=min_han_8+specific_function_anchor;"
                    "reason_redacted=true",
                    error,
                )
                self.assertNotIn(reason, error)

        injected = "该段保持原有自然表达SECRET-CONTENT"
        error = finalizer._no_change_reason_error(injected)
        self.assertIn("NO_CHANGE_reason_invalid:generic_template", error)
        self.assertNotIn("SECRET-CONTENT", error)

    def test_unresolved_summary_classifies_empty_intent_spans_without_notes(self) -> None:
        summary = finalizer._unresolved_reason_summary(
            [
                {
                    "status": "UNRESOLVED",
                    "notes": "invalid_rewrite_bundle:no_change_evidence_spans_must_be_nonempty SECRET-A",
                },
                {
                    "status": "UNRESOLVED",
                    "notes": "invalid_rewrite_bundle:rewrite_intent_source_spans_must_be_nonempty SECRET-B",
                },
                {"status": "UNRESOLVED", "notes": "unknown SECRET-C"},
                {"status": "NO_CHANGE", "notes": "SECRET-D"},
            ]
        )

        self.assertEqual(3, summary["total"])
        self.assertEqual(2, summary["classified"])
        self.assertEqual(1, summary["unclassified"])
        self.assertEqual(
            {
                "no_change_evidence_spans_must_be_nonempty": 1,
                "rewrite_intent_source_spans_must_be_nonempty": 1,
            },
            summary["codes"],
        )
        self.assertNotIn("notes", summary)
        self.assertNotIn("SECRET", json.dumps(summary))

    def test_unresolved_summary_does_not_classify_code_named_unknown_field(self) -> None:
        summary = finalizer._unresolved_reason_summary(
            [
                {
                    "status": "UNRESOLVED",
                    "notes": (
                        "invalid_rewrite_bundle:unknown_rewrite_bundle_fields:"
                        "no_change_evidence_spans_must_be_nonempty"
                    ),
                }
            ]
        )

        self.assertEqual(1, summary["total"])
        self.assertEqual(0, summary["classified"])
        self.assertEqual(1, summary["unclassified"])
        self.assertEqual({}, summary["codes"])
        self.assertEqual(0, summary["structured_classified"])
        self.assertEqual(1, summary["structured_unclassified"])
        self.assertEqual({}, summary["structured_code_counts"])

    def test_unresolved_code_registry_rejects_dynamic_or_user_controlled_codes(self) -> None:
        unit = {"status": "UNRESOLVED", "notes": "SECRET-CONTENT"}
        with self.assertRaisesRegex(
            AssertionError, "unknown internal unresolved code"
        ):
            finalizer._add_unresolved_code(
                unit, "REWRITE_DECISION_UNSUPPORTED:SECRET-CONTENT"
            )
        self.assertNotIn("unresolved_codes", unit)

    def test_every_unresolved_status_assignment_has_same_branch_registry_code(self) -> None:
        source_path = SKILL / "scripts" / "finalize_humanize_long_document.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        failures: list[int] = []

        def is_unresolved_assignment(statement: ast.stmt) -> bool:
            if not isinstance(statement, ast.Assign):
                return False
            if not isinstance(statement.value, ast.Constant):
                return False
            if statement.value.value != "UNRESOLVED":
                return False
            return any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "unit"
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "status"
                for target in statement.targets
            )

        def contains_registry_call(statement: ast.stmt) -> bool:
            return any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_add_unresolved_code"
                and len(node.args) >= 2
                for node in ast.walk(statement)
            )

        def inspect_block(statements: list[ast.stmt]) -> None:
            for index, statement in enumerate(statements):
                if is_unresolved_assignment(statement):
                    found = False
                    for following in statements[index + 1 :]:
                        if contains_registry_call(following):
                            found = True
                            break
                        if isinstance(
                            following, (ast.Continue, ast.Break, ast.Return, ast.Raise)
                        ):
                            break
                    if not found:
                        failures.append(statement.lineno)
                for _field, value in ast.iter_fields(statement):
                    if isinstance(value, list) and value and all(
                        isinstance(item, ast.stmt) for item in value
                    ):
                        inspect_block(value)

        inspect_block(tree.body)
        self.assertEqual([], failures)

    def test_csv_writer_neutralizes_spreadsheet_formula_prefixes(self) -> None:
        path = self.root / "ledger.csv"
        rows = [
            {"unit_id": "U1", "notes": "=HYPERLINK(\"https://invalid\")"},
            {"unit_id": "U2", "notes": "+SUM(1,1)"},
            {"unit_id": "U3", "notes": "ordinary note"},
        ]
        finalizer._write_csv(path, rows, ("unit_id", "notes"))
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            written = list(csv.DictReader(handle))

        self.assertEqual("'=HYPERLINK(\"https://invalid\")", written[0]["notes"])
        self.assertEqual("'+SUM(1,1)", written[1]["notes"])
        self.assertEqual("ordinary note", written[2]["notes"])

    def test_previous_final_ledger_accepts_explicit_legacy_columns(self) -> None:
        path = self.root / "coverage_ledger.final.csv"
        finalizer._write_csv(
            path,
            [
                {"unit_id": "U1", "status": "DONE", "notes": "legacy"},
                {"unit_id": "U2", "status": "UNRESOLVED", "notes": "legacy"},
            ],
            ("unit_id", "status", "notes"),
        )
        self.assertEqual({"U1"}, finalizer._load_previous_accepted_units(path))

    def test_previous_final_ledger_rejects_missing_or_duplicate_authority_fields(self) -> None:
        missing = self.root / "missing.csv"
        finalizer._write_csv(missing, [{"status": "DONE"}], ("status",))
        with self.assertRaisesRegex(ValueError, "missing columns unit_id"):
            finalizer._load_previous_accepted_units(missing)

        duplicate = self.root / "duplicate.csv"
        finalizer._write_csv(
            duplicate,
            [
                {"unit_id": "U1", "status": "DONE"},
                {"unit_id": "U1", "status": "NO_CHANGE"},
            ],
            ("unit_id", "status"),
        )
        with self.assertRaisesRegex(ValueError, "blank or duplicated"):
            finalizer._load_previous_accepted_units(duplicate)

    def test_v3_no_change_short_reason_uses_v3_contract_not_legacy_hint(self) -> None:
        source_text = "# 定义\n\n正式定义保持对象、条件和并列结构。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-short-no-change"
        )
        span = self.masked_line_span(unit["masked_text"], "正式定义")
        rewrites = self.rewrite_dir()
        bundle = self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "NO_CHANGE",
                "reason": "保持原样",
                "evidence_spans": [span],
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("NO_CHANGE_reason_invalid:too_short_han", row["notes"])
        self.assertNotIn("at least 4 Chinese characters", row["notes"])

    def test_v3_empty_no_change_evidence_is_classified_at_top_level(self) -> None:
        source_text = "# 定义\n\n正式定义保持对象、条件和并列结构。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-empty-no-change-evidence"
        )
        rewrites = self.rewrite_dir()
        bundle = self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "NO_CHANGE",
                "reason": "正式定义保留对象条件和并列结构，避免改变等权关系",
                "evidence_spans": [],
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertEqual(
            {"no_change_evidence_spans_must_be_nonempty": 1},
            result["unresolved_reason_summary"]["codes"],
        )
        self.assertEqual(0, result["unresolved_reason_summary"]["unclassified"])
        self.assertEqual(
            {"NO_CHANGE_EVIDENCE_SPANS_EMPTY": 1},
            result["unresolved_reason_summary"]["structured_code_counts"],
        )
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual(
            '["NO_CHANGE_EVIDENCE_SPANS_EMPTY"]',
            row["unresolved_codes_json"],
        )
        self.assertIn(
            "reason_codes[no_change_evidence_spans_must_be_nonempty=1]",
            finalizer._render_text_summary(result),
        )

    def test_v3_no_change_with_specific_bound_reason_passes_intent(self) -> None:
        source_text = "# 定义\n\n正式定义保留对象、条件和并列结构。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-specific-no-change"
        )
        span = self.masked_line_span(unit["masked_text"], "正式定义")
        rewrites = self.rewrite_dir()
        bundle = self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "NO_CHANGE",
                "reason": "正式定义保留对象、条件和并列结构，避免改变等权关系",
                "evidence_spans": [span],
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        evidence = result["rewrite_intent_evidence"][unit["unit_id"]]
        payload = json.loads((run_dir / evidence["path"]).read_text(encoding="utf-8"))

        self.assertEqual(1, result["unit_statuses"]["NO_CHANGE"])
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        self.assertEqual("PASS", payload["status"])
        self.assertEqual("NO_CHANGE", payload["decision"])

    def test_v3_rewrite_rejects_source_span_hash_mismatch(self) -> None:
        source_text = "# 讨论\n\n原段说明材料范围，随后给出空泛收尾。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-source-hash-mismatch"
        )
        span = self.masked_line_span(unit["masked_text"], "原段说明")
        span["sha256"] = "f" * 64
        revised = unit["masked_text"].replace(
            "随后给出空泛收尾", "说明仍限于这些材料"
        )
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("rewrite_intent_source_spans_sha256_mismatch", row["notes"])

    def test_v3_rewrite_rejects_uncovered_target_signal(self) -> None:
        source_text = "# 讨论\n\n原段说明材料范围，随后给出空泛收尾。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-target-signal-coverage"
        )
        span = self.masked_line_span(unit["masked_text"], "原段说明")
        revised = unit["masked_text"].replace(
            "随后给出空泛收尾", "说明仍限于这些材料"
        )
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        bundle["rewrite_intent"]["target_signals"].append(
            "STYLE-UNREFERENCED-SIGNAL"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("rewrite_intent_target_signal_coverage_incomplete", row["notes"])

    def test_unit_explicit_null_schema_is_not_legacy(self) -> None:
        source_text = "# 讨论\n\n原段说明材料范围，随后给出空泛收尾。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-null-schema"
        )
        span = self.masked_line_span(unit["masked_text"], "原段说明")
        revised = unit["masked_text"].replace(
            "随后给出空泛收尾", "说明仍限于这些材料"
        )
        bundle = self.v3_rewrite_bundle(
            run_dir, unit, masked_text=revised, source_span=span
        )
        bundle["schema_version"] = None
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("unit_rewrite_bundle_schema_invalid", row["notes"])

    def test_legacy_rewrite_remains_readable_but_intent_coverage_is_review(self) -> None:
        source_text = "# 讨论\n\n原段说明材料范围，随后给出空泛收尾。\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="intent-legacy"
        )
        revised = unit["masked_text"].replace(
            "随后给出空泛收尾", "说明仍限于这些材料"
        )
        rewrites = self.rewrite_dir()
        legacy = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": revised,
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual(1, result["unit_statuses"]["DONE"])
        self.assertEqual("REVIEW", result["rewrite_intent_coverage_status"])
        self.assertTrue(result["rewrite_intent_blocks_delivery"])
        evidence = result["rewrite_intent_evidence"][unit["unit_id"]]
        self.assertEqual("REVIEW", evidence["status"])

    def test_balanced_rewrite_rejects_undeclared_full_paragraph_reorder(self) -> None:
        source = self.root / "source.md"
        source.write_text(
            "# 范围\n"
            "甲样本呈现局部波动。此处先描述观察范围，随后解释边界，读者据此辨认现象与结论的差别。\n\n"
            "乙样本呈现稳定趋势。此处承接前段限定的范围，结尾说明甲乙观察各自对应不同条件。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare(
            [source],
            run_dir,
            scene="GENERAL",
            intensity="BALANCED",
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
        ]
        unit = next(item for item in chunks if item["status"] == "PENDING")
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        self.assertEqual(2, len(blocks), unit["masked_text"])
        title, first = blocks[0].splitlines()
        second = blocks[1]
        swapped = title + "\n" + second + "\n\n" + first + "\n"
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": swapped,
                        "keep_reasons": {},
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertEqual("REVIEW", structural["status"])
        self.assertTrue(
            structural["non_structural_paragraph_order_check"]["reordered"]
        )
        self.assertEqual(
            "BLOCKED_BY_SCOPE_VIOLATION", structural["semantic_review_status"]
        )
        self.assertEqual({}, result["structural_semantic_review_requests"])
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_balanced_rewrite_rejects_near_exact_paragraph_reorder(self) -> None:
        source_text = (
            "# 结果讨论\n\n"
            "样本筛选首先处理记录之间的可比性。研究者按照预先列出的字段核对缺项，并把无法确认来源的记录留在待核清单中。这个步骤只决定哪些材料进入后续整理，不对材料质量作额外判断。\n\n"
            "编码环节随后处理同义表达的归并。相同含义的表述被放到同一标签下，但原记录中的否定和条件仍单独保留。这样做是为了避免表面用词差异被误当成新的观察。\n\n"
            "比较环节关注不同标签在材料中的出现位置。段落重心落在比较范围，不把顺序差异写成主次判断。\n\n"
            "解释环节最后回到原记录能够支持的命题。缺少来源支撑的内容仍保留为未决事项。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(source_text, name="near-reorder")
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        title, first, second, third, fourth = blocks
        revised_first = first.replace("首先处理", "处理").replace("这个步骤", "该步骤")
        revised_second = second.replace("随后处理", "处理").replace("这样做是为了", "这样可以")
        first_end = unit["masked_text"].index(first) + len(first)
        second_start = unit["masked_text"].index(second, first_end)
        paragraph_separator = unit["masked_text"][first_end:second_start]
        source_pair = first + paragraph_separator + second
        self.assertIn(source_pair, unit["masked_text"])
        masked = unit["masked_text"].replace(
            source_pair,
            revised_second + paragraph_separator + revised_first,
            1,
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "REWRITE", "masked_text": masked, "keep_reasons": {}},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertTrue(structural["non_structural_paragraph_order_check"]["reordered"])
        self.assertTrue(
            structural["non_structural_paragraph_order_check"]["near_exact_reordered"]
        )
        self.assertFalse(
            structural["non_structural_paragraph_order_check"][
                "protected_anchor_reordered"
            ]
        )

    def test_balanced_rewrite_rejects_significant_paragraph_merge_and_split(self) -> None:
        source_text = (
            "# 方法\n\n"
            "第一段说明样本进入分析前的整理范围，并保留原有对象和限定条件。\n\n"
            "第二段说明标签归并的操作边界，否定和来源状态仍分别保存。\n\n"
            "第三段说明比较时采用的阅读顺序，不把顺序差异写成主次判断。\n\n"
            "第四段说明解释的收尾范围，缺少依据的内容继续保留为未决事项。\n"
        )
        for name, transform in (
            (
                "merge",
                lambda blocks: [blocks[0] + blocks[1], *blocks[2:]],
            ),
            (
                "split",
                lambda blocks: [
                    "第一段说明样本进入分析前的整理范围。",
                    "这一处理保留原有对象和限定条件。",
                    *blocks[1:],
                ],
            ),
        ):
            with self.subTest(name=name):
                _, run_dir, unit = self.prepare_markdown_unit(source_text, name=name)
                blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
                title, *author_blocks = blocks
                body_start = unit["masked_text"].index(author_blocks[0])
                first_end = body_start + len(author_blocks[0])
                second_start = unit["masked_text"].index(author_blocks[1], first_end)
                paragraph_separator = unit["masked_text"][first_end:second_start]
                body_end = unit["masked_text"].index(
                    author_blocks[-1], second_start
                ) + len(author_blocks[-1])
                source_body = unit["masked_text"][body_start:body_end]
                self.assertIn(source_body, unit["masked_text"])
                masked = unit["masked_text"].replace(
                    source_body,
                    paragraph_separator.join(transform(author_blocks)),
                    1,
                )
                rewrites = self.root / f"rewrites-{name}"
                rewrites.mkdir()
                (rewrites / f"{unit['unit_id']}.json").write_text(
                    json.dumps(
                        self.voice_bound_bundle(
                            unit,
                            {
                                "decision": "REWRITE",
                                "masked_text": masked,
                                "keep_reasons": {},
                            },
                        ),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                result = finalizer.finalize(run_dir, rewrites)

                self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
                row = next(
                    item
                    for item in self.final_ledger(run_dir)
                    if item["unit_id"] == unit["unit_id"]
                )
                self.assertEqual("non_structural_paragraph_topology_changed", row["notes"])
                self.assertFalse((run_dir / "rendered_review").exists())

    def test_balanced_v3_allows_declared_adjacent_redundancy_merge(self) -> None:
        first = "第一段说明样本范围只包括已经登记的记录。"
        second = "第二段重复说明分析对象仍限于这些登记记录。"
        third = "第三段保留独立的方法边界和来源状态。"
        source_text = "# 方法\n\n" + "\n\n".join((first, second, third)) + "\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="declared-balanced-merge"
        )
        span = self.masked_line_range_span(
            unit["masked_text"], "第一段说明", "第二段重复"
        )
        revised = unit["masked_text"].replace("\r\n", "\n").replace(
            first + "\n\n" + second,
            first + second,
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="MERGE_ADJACENT_REDUNDANCY",
            target_signal="HIERARCHY-ADJACENT-REDUNDANCY",
            summary="合并职责重复的相邻两段并保留共同的材料范围",
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(1, result["unit_statuses"]["DONE"])
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        topology = structural["non_structural_paragraph_order_check"]
        self.assertEqual("PASS", topology["status"])
        self.assertEqual("PASS", topology["topology_authorization_status"])
        self.assertEqual(1, topology["authorized_topology_operations"])

    def test_balanced_v3_allows_declared_overloaded_paragraph_split(self) -> None:
        overloaded = (
            "本段先界定样本范围，只纳入已经登记的记录。"
            "随后说明标签归并保留否定和来源状态。"
            "最后说明缺项记录仍进入待核清单。"
        )
        following = "下一段单独讨论比较结果的适用边界。"
        source_text = "# 方法\n\n" + overloaded + "\n\n" + following + "\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="declared-balanced-split"
        )
        span = self.masked_line_span(unit["masked_text"], "本段先界定")
        revised = unit["masked_text"].replace(
            overloaded,
            "本段先界定样本范围，只纳入已经登记的记录。\n\n"
            "随后说明标签归并保留否定和来源状态。最后说明缺项记录仍进入待核清单。",
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="SPLIT_OVERLOADED_PARAGRAPH",
            target_signal="HIERARCHY-OVERLOADED-PARAGRAPH",
            summary="拆开职责过载段落以区分范围界定和操作说明",
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(1, result["unit_statuses"]["DONE"])
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        topology = structural["non_structural_paragraph_order_check"]
        self.assertEqual("PASS", topology["status"])
        self.assertEqual("PASS", topology["topology_authorization_status"])
        self.assertEqual(1, topology["authorized_topology_operations"])

    def test_balanced_v3_rejects_topology_operation_kind_mismatch(self) -> None:
        first = "第一段说明样本范围只包括已经登记的记录。"
        second = "第二段重复说明分析对象仍限于这些登记记录。"
        source_text = "# 方法\n\n" + first + "\n\n" + second + "\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="balanced-topology-kind-mismatch"
        )
        span = self.masked_line_range_span(
            unit["masked_text"], "第一段说明", "第二段重复"
        )
        revised = unit["masked_text"].replace("\r\n", "\n").replace(
            first + "\n\n" + second, first + second
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="SPLIT_OVERLOADED_PARAGRAPH",
            target_signal="HIERARCHY-OVERLOADED-PARAGRAPH",
            summary="错误地把相邻段合并申报为拆分操作",
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("balanced_topology_operation_kind_mismatch", row["notes"])

    def test_balanced_v3_rejects_merge_span_covering_three_paragraphs(self) -> None:
        paragraphs = (
            "第一段说明样本范围只包括已经登记的记录。",
            "第二段重复说明分析对象仍限于这些登记记录。",
            "第三段保留独立的方法边界和来源状态。",
        )
        source_text = "# 方法\n\n" + "\n\n".join(paragraphs) + "\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="balanced-merge-overbroad-span"
        )
        span = self.masked_line_range_span(
            unit["masked_text"], "第一段说明", "第三段保留"
        )
        revised = unit["masked_text"].replace("\r\n", "\n").replace(
            paragraphs[0] + "\n\n" + paragraphs[1],
            paragraphs[0] + paragraphs[1],
        )
        rewrites = self.rewrite_dir()
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="MERGE_ADJACENT_REDUNDANCY",
            target_signal="HIERARCHY-ADJACENT-REDUNDANCY",
            summary="用过宽跨度申报相邻重复段合并",
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertIn("balanced_merge_source_paragraph_count_invalid", row["notes"])

    def test_balanced_v3_authorizes_net_zero_merge_and_split_separately(self) -> None:
        first = "第一段说明样本范围只包括已经登记的记录。"
        second = "第二段重复说明分析对象仍限于这些登记记录。"
        overloaded = (
            "第三段先说明标签归并保留否定和来源状态。"
            "随后说明缺项记录仍进入待核清单。"
        )
        fourth = "第四段单独讨论比较结果的适用边界。"
        source_text = (
            "# 方法\n\n" + "\n\n".join((first, second, overloaded, fourth)) + "\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="balanced-net-zero-topology"
        )
        merge_span = self.masked_line_range_span(
            unit["masked_text"], "第一段说明", "第二段重复", span_id="S1"
        )
        split_span = self.masked_line_span(
            unit["masked_text"], "第三段先说明", span_id="S2"
        )
        revised = (
            unit["masked_text"]
            .replace("\r\n", "\n")
            .replace(first + "\n\n" + second, first + second)
            .replace(
                overloaded,
                "第三段先说明标签归并保留否定和来源状态。\n\n"
                "随后说明缺项记录仍进入待核清单。",
            )
        )
        signals = [
            "HIERARCHY-ADJACENT-REDUNDANCY",
            "HIERARCHY-OVERLOADED-PARAGRAPH",
        ]
        bundle = self.authoring_bound_bundle(
            run_dir,
            unit,
            {
                "decision": "REWRITE",
                "masked_text": revised,
                "keep_reasons": {},
                "rewrite_intent": {
                    "summary": "分别合并相邻重复段并拆开职责过载段",
                    "operations": [
                        {
                            "id": "O1",
                            "kind": "MERGE_ADJACENT_REDUNDANCY",
                            "source_span_ids": ["S1"],
                            "target_signals": [signals[0]],
                            "summary": "合并重复说明同一材料范围的相邻两段",
                        },
                        {
                            "id": "O2",
                            "kind": "SPLIT_OVERLOADED_PARAGRAPH",
                            "source_span_ids": ["S2"],
                            "target_signals": [signals[1]],
                            "summary": "拆开同时承担归并规则和缺项处置的段落",
                        },
                    ],
                    "source_spans": [merge_span, split_span],
                    "target_signals": signals,
                },
            },
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        topology = structural["non_structural_paragraph_order_check"]
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual(
            1,
            result["unit_statuses"].get("DONE", 0),
            {"ledger": row, "topology": topology},
        )
        self.assertTrue(topology["paragraph_topology_changed"])
        self.assertEqual(1, len(topology["detected_paragraph_merges"]))
        self.assertEqual(1, len(topology["detected_paragraph_splits"]))
        self.assertEqual(2, topology["authorized_topology_operations"])

    def test_balanced_v3_rejects_merge_across_standalone_protected_anchor(self) -> None:
        source_text = (
            "# 讨论\n\n"
            "第一段说明材料范围只包括已经登记的记录。\n\n"
            "> “该引语必须保留在两个论述段之间。”\n\n"
            "第二段重复说明分析对象仍限于这些登记记录。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text, name="balanced-merge-protected-anchor"
        )
        span = self.masked_line_range_span(
            unit["masked_text"], "第一段说明", "第二段重复"
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        title, first_with_protected, second = blocks
        protected = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(first_with_protected)
        ).group(0)
        protected_start = unit["masked_text"].index(protected)
        protected_end = protected_start + len(protected)
        second_start = unit["masked_text"].index(second, protected_end)
        protected_boundary = unit["masked_text"][protected_end:second_start]
        self.assertTrue(protected_boundary.strip("\r\n") == "")
        revised = (
            unit["masked_text"][:protected_end]
            + unit["masked_text"][second_start:]
        )
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="MERGE_ADJACENT_REDUNDANCY",
            target_signal="HIERARCHY-ADJACENT-REDUNDANCY",
            summary="错误地跨独立引语锚点合并相邻论述段",
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertEqual(
            "balanced_topology_standalone_protected_anchor_in_source",
            row["notes"],
        )

    def test_light_rejects_even_declared_paragraph_split(self) -> None:
        overloaded = (
            "本段先界定样本范围，只纳入已经登记的记录。"
            "随后说明标签归并保留否定和来源状态。"
        )
        source_text = "# 方法\n\n" + overloaded + "\n"
        _, run_dir, unit = self.prepare_markdown_unit(
            source_text,
            intensity="LIGHT",
            name="light-declared-topology",
        )
        span = self.masked_line_span(unit["masked_text"], "本段先界定")
        revised = unit["masked_text"].replace(
            overloaded,
            "本段先界定样本范围，只纳入已经登记的记录。\n\n"
            "随后说明标签归并保留否定和来源状态。",
        )
        bundle = self.v3_topology_bundle(
            run_dir,
            unit,
            masked_text=revised,
            source_span=span,
            operation_kind="SPLIT_OVERLOADED_PARAGRAPH",
            target_signal="HIERARCHY-OVERLOADED-PARAGRAPH",
            summary="在 LIGHT 范围内错误申报拆分职责过载段落",
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])

    def test_balanced_rewrite_rejects_protected_block_anchor_move(self) -> None:
        source_text = (
            "# 讨论\n\n"
            "第一段说明材料进入分析前的整理范围，并保留原有对象和限定条件。\n\n"
            "> “该引语必须逐字保留，并维持原有位置。”\n\n"
            "第二段说明标签归并的操作边界，否定和来源状态仍分别保存。\n\n"
            "第三段说明比较时采用的阅读顺序，不把顺序差异写成主次判断。\n"
        )
        _, run_dir, unit = self.prepare_markdown_unit(source_text, name="protected-anchor")
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        title, first_with_protected, second, third = blocks
        protected_match = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(first_with_protected)
        )
        protected = protected_match.group(0)
        prefix = first_with_protected[: protected_match.start()]
        first = prefix.rstrip("\r\n")
        line_separator = prefix[len(first) :]
        source_pair = first + line_separator + protected
        self.assertIn(source_pair, unit["masked_text"])
        masked = unit["masked_text"].replace(
            source_pair,
            protected + line_separator + first,
            1,
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "REWRITE", "masked_text": masked, "keep_reasons": {}},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        structural = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(1, result["unit_statuses"]["UNRESOLVED"])
        self.assertTrue(
            structural["non_structural_paragraph_order_check"]["protected_anchor_reordered"]
        )
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_light_rejects_sentence_reorder_but_balanced_allows_it(self) -> None:
        source_text = (
            "# 结果\n\n"
            "样本筛选范围限于已登记材料。缺项记录暂时留在待核清单。当前段落不评价材料质量。\n\n"
            "下一段说明标签归并边界，并保留原记录中的限定条件。\n"
        )
        for intensity, expected_status in (("LIGHT", "UNRESOLVED"), ("BALANCED", "DONE")):
            with self.subTest(intensity=intensity):
                _, run_dir, unit = self.prepare_markdown_unit(
                    source_text,
                    intensity=intensity,
                    name=f"sentence-{intensity.lower()}",
                )
                blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
                title, first, second = blocks
                reordered = (
                    "缺项记录暂时留在待核清单。样本筛选范围限于已登记材料。"
                    "当前段落不评价材料质量。"
                )
                self.assertIn(first, unit["masked_text"])
                masked = unit["masked_text"].replace(first, reordered, 1)
                rewrites = self.root / f"rewrites-sentence-{intensity.lower()}"
                rewrites.mkdir()
                (rewrites / f"{unit['unit_id']}.json").write_text(
                    json.dumps(
                        self.voice_bound_bundle(
                            unit,
                            {
                                "decision": "REWRITE",
                                "masked_text": masked,
                                "keep_reasons": {},
                            },
                        ),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                result = finalizer.finalize(run_dir, rewrites)

                self.assertEqual(1, result["unit_statuses"][expected_status])
                if intensity == "LIGHT":
                    row = next(
                        item
                        for item in self.final_ledger(run_dir)
                        if item["unit_id"] == unit["unit_id"]
                    )
                    self.assertEqual("light_sentence_reorder_not_allowed", row["notes"])

    def assert_paired_quality_review_candidate(
        self,
        result: dict,
        *,
        units: int | None = None,
    ) -> None:
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual("PASS", result["paired_quality_review_request_coverage_status"])
        self.assertEqual("PENDING_EXTERNAL_REVIEW", result["paired_quality_gate_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["paired_quality_local_clearance_supported"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertTrue(Path(result["published_path"]).name == "rendered_review")
        if units is not None:
            self.assertEqual(units, result["paired_quality_units_total"])
            self.assertEqual(units, result["paired_quality_units_pending"])
            self.assertEqual(units, len(result["paired_quality_review_requests"]))

    def structural_plan(
        self,
        unit: dict,
        target_text: str,
        target_source_groups: list[list[str]],
    ) -> dict:
        source_by_id = {
            item["paragraph_id"]: item for item in unit["structural_paragraphs"]
        }
        target_blocks = preparer.structural_paragraph_blocks(target_text)
        self.assertEqual(len(target_blocks), len(target_source_groups))
        groups = []
        for block, source_ids in zip(target_blocks, target_source_groups):
            groups.append(
                {
                    "source_paragraph_ids": source_ids,
                    "target_paragraph_sha256": hashlib.sha256(
                        block.encode("utf-8")
                    ).hexdigest(),
                    "responsibility": source_by_id[source_ids[0]]["responsibility"],
                    "reason": "保持该段原有论述职责并调整相邻次序",
                }
            )
        return {
            "schema_version": "humanize-structural-plan/v1",
            "source_inventory_sha256": unit["structural_inventory_sha256"],
            "target_groups": groups,
        }

    def prepare_structural_pair(
        self, *, extra_pending: bool = False, template_field: bool = False
    ) -> tuple[Path, Path, list[dict]]:
        source = self.root / "transaction.tex"
        fourth_paragraph = "值得注意的是，第四段补充比较结果。"
        if template_field:
            fourth_paragraph = "适用题目：" + fourth_paragraph
        text = (
            "\\section{讨论}\n\n"
            "值得注意的是，第一段说明当前观察对象。\n\n"
            "第二段补充两种表述之间的差别 $x=1$。\n\n"
            "第三段说明另一组观察对象 $y=2$。\n\n"
            f"{fourth_paragraph}\n"
        )
        if extra_pending:
            text += "\n\\section{附录}\n\n附录中的独立说明仍待处理。\n"
        source.write_text(text, encoding="utf-8")
        run_dir = self.root / "transaction-run"
        preparer.prepare(
            [source],
            run_dir,
            scene="COURSE",
            intensity="STRUCTURAL",
            structural_transaction_scope="ADJACENT_PAIR",
            max_author_chars=35,
            min_author_chars=0,
        )
        pending = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"]
                == "PENDING"
            ),
            key=lambda item: int(item["start"]),
        )
        inventory = json.loads(
            (run_dir / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("READY", inventory["status"])
        self.assertEqual(1, len(inventory["transactions"]))
        participant_ids = [
            item["unit_id"]
            for item in inventory["transactions"][0]["compound_refs"]
        ]
        pair = [next(item for item in pending if item["unit_id"] == unit_id) for unit_id in participant_ids]
        self.assertEqual(pair[1]["unit_id"], pair[0]["context_after_unit"])
        self.assertEqual(pair[0]["unit_id"], pair[1]["context_before_unit"])
        self.assertEqual(3 if extra_pending else 2, len(pending))
        return source, run_dir, pair

    def prepare_structural_chain(self) -> tuple[Path, Path, list[dict], dict]:
        source = self.root / "transaction-chain.tex"
        paragraphs = [
            "当前观察对象位于比较区间之内。",
            "另一种表述补充两个对象之间的差别。",
            "当前材料还说明另一组观察对象的变化。",
            "比较结果在这里保留原有适用范围。",
            "新的观察对象位于后续讨论区间之内。",
            "相邻说明补充判断过程及其限制。",
            "末组观察对象仍位于给定范围之内。",
            "相关说明补充结论范围和使用条件。",
            "上述观察在末段收束并保留原有边界。",
        ]
        source.write_text(
            "\\section{讨论}\n\n" + "\n\n".join(paragraphs) + "\n",
            encoding="utf-8",
        )
        run_dir = self.root / "transaction-chain-run"
        preparer.prepare(
            [source],
            run_dir,
            scene="COURSE",
            intensity="STRUCTURAL",
            structural_transaction_scope="ADJACENT_PAIR",
            max_author_chars=35,
            min_author_chars=0,
        )
        pending = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"]
                == "PENDING"
            ),
            key=lambda item: int(item["start"]),
        )
        inventory = json.loads(
            (run_dir / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertGreaterEqual(len(pending), 3)
        self.assertGreaterEqual(len(inventory["transactions"]), 2)
        return source, run_dir, pending, inventory

    def structural_transaction_v1_bundle(
        self, run_dir: Path, units: list[dict]
    ) -> dict:
        inventory = json.loads(
            (run_dir / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        transaction = inventory["transactions"][0]
        bindings = [
            {
                "unit_id": unit["unit_id"],
                "chunk_binding_sha256": unit["chunk_binding_sha256"],
                "voice_profile_sha256": unit["voice_profile_sha256"],
            }
            for unit in units
        ]
        blocks = [
            preparer.structural_paragraph_blocks(unit["masked_text"])
            for unit in units
        ]
        source = [unit["structural_paragraphs"] for unit in units]
        self.assertEqual([3, 2], [len(item) for item in blocks])
        target_specs = [
            (
                [
                    blocks[0][0],
                    blocks[0][1].replace("值得注意的是，", ""),
                    blocks[1][0],
                ],
                [[(0, 0)], [(0, 1)], [(1, 0)]],
            ),
            (
                [blocks[0][2], blocks[1][1].replace("值得注意的是，", "")],
                [[(0, 2)], [(1, 1)]],
            ),
        ]
        fragments = []
        for target_unit, (target_blocks, target_source_groups) in zip(
            units, target_specs
        ):
            target_text = "\n\n".join(target_blocks) + "\n"
            target_groups = []
            for block, source_group in zip(target_blocks, target_source_groups):
                target_groups.append(
                    {
                        "source_refs": [
                            {
                                "unit_id": units[unit_index]["unit_id"],
                                "paragraph_id": source[unit_index][paragraph_index][
                                    "paragraph_id"
                                ],
                            }
                            for unit_index, paragraph_index in source_group
                        ],
                        "target_paragraph_sha256": hashlib.sha256(
                            block.encode("utf-8")
                        ).hexdigest(),
                        "responsibility": source[source_group[0][0]][
                            source_group[0][1]
                        ]["responsibility"],
                        "reason": "保持该段原有论述职责并调整相邻次序",
                    }
                )
            fragments.append(
                {
                    "target_unit_id": target_unit["unit_id"],
                    "masked_text": target_text,
                    "keep_reasons": {},
                    "target_groups": target_groups,
                }
            )
        return {
            "schema_version": "humanize-structural-transaction-bundle/v1",
            "transaction_id": transaction["transaction_id"],
            "transaction_binding_sha256": transaction[
                "transaction_binding_sha256"
            ],
            "transaction_inventory_sha256": inventory["inventory_sha256"],
            "unit_bindings": bindings,
            "fragments": fragments,
        }

    def structural_transaction_v2_bundle(
        self, run_dir: Path, units: list[dict]
    ) -> dict:
        bundle = self.structural_transaction_v1_bundle(run_dir, units)
        bundle["schema_version"] = finalizer.STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA_V2
        chunks = {
            unit["unit_id"]: json.loads(
                (run_dir / "chunks" / f"{unit['unit_id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            for unit in units
        }
        unit_ids = [unit["unit_id"] for unit in units]
        ordered_refs, source_map = finalizer._transaction_source_inventory(
            unit_ids, chunks
        )
        for fragment in bundle["fragments"]:
            plan = finalizer._validate_structural_transaction_fragment_plan(
                fragment,
                target_unit_id=fragment["target_unit_id"],
                ordered_source_refs=ordered_refs,
                source_map=source_map,
            )
            baseline = str(plan["_baseline_masked_text"])
            candidate = str(fragment["masked_text"])
            before_lines = baseline.replace("\r\n", "\n").replace(
                "\r", "\n"
            ).splitlines(keepends=True)
            after_lines = candidate.replace("\r\n", "\n").replace(
                "\r", "\n"
            ).splitlines(keepends=True)
            matcher = __import__("difflib").SequenceMatcher(
                a=before_lines, b=after_lines, autojunk=False
            )
            ranges = []
            for tag, before_start, before_end, _after_start, _after_end in matcher.get_opcodes():
                if tag == "equal":
                    continue
                if before_end > before_start:
                    start_line = before_start + 1
                    end_line = before_end
                else:
                    start_line = max(1, before_start)
                    end_line = start_line
                ranges.append((start_line, end_line))
            if ranges:
                spans = []
                operations = []
                signals = []
                for index, (start_line, end_line) in enumerate(ranges, 1):
                    span_id = f"S{index}"
                    signal = f"STYLE-TRANSACTION-LOCAL-{index}"
                    spans.append(
                        {
                            "id": span_id,
                            "start_line": start_line,
                            "end_line": end_line,
                            "sha256": hashlib.sha256(
                                "".join(before_lines[start_line - 1 : end_line]).encode(
                                    "utf-8"
                                )
                            ).hexdigest(),
                        }
                    )
                    operations.append(
                        {
                            "id": f"O{index}",
                            "kind": "REWRITE_STYLE_SHELL",
                            "source_span_ids": [span_id],
                            "target_signals": [signal],
                            "summary": "删除目标片段中的空泛强调壳并保留原有观察对象",
                        }
                    )
                    signals.append(signal)
                fragment["local_rewrite_intent"] = {
                    "decision": "REWRITE",
                    "rewrite_intent": {
                        "summary": "删除目标片段中的空泛强调壳并保留原有观察对象",
                        "operations": operations,
                        "source_spans": spans,
                        "target_signals": signals,
                    },
                }
            else:
                evidence_line = next(
                    index
                    for index, line in enumerate(before_lines, 1)
                    if re.search(r"[\u3400-\u9fff]", line)
                )
                fragment["local_rewrite_intent"] = {
                    "decision": "NO_CHANGE",
                    "reason": "该目标片段只承接结构移动，保留段内原有对象和措辞",
                    "evidence_spans": [
                        {
                            "id": "S1",
                            "start_line": evidence_line,
                            "end_line": evidence_line,
                            "sha256": hashlib.sha256(
                                before_lines[evidence_line - 1].encode("utf-8")
                            ).hexdigest(),
                        }
                    ],
                }
        return bundle

    def structural_transaction_v3_bundle(
        self, run_dir: Path, units: list[dict]
    ) -> dict:
        bundle = self.structural_transaction_v2_bundle(run_dir, units)
        bundle["schema_version"] = finalizer.STRUCTURAL_TRANSACTION_BUNDLE_SCHEMA
        for fragment in bundle["fragments"]:
            fragment["template_field_edit_scope"] = None
        return bundle

    def structural_transaction_bundle(
        self, run_dir: Path, units: list[dict]
    ) -> dict:
        return self.structural_transaction_v3_bundle(run_dir, units)

    def structural_transaction_fragment_baseline(
        self,
        run_dir: Path,
        units: list[dict],
        fragment: dict,
    ) -> str:
        chunks = {
            unit["unit_id"]: json.loads(
                (run_dir / "chunks" / f"{unit['unit_id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            for unit in units
        }
        ordered_refs, source_map = finalizer._transaction_source_inventory(
            [unit["unit_id"] for unit in units], chunks
        )
        plan = finalizer._validate_structural_transaction_fragment_plan(
            fragment,
            target_unit_id=fragment["target_unit_id"],
            ordered_source_refs=ordered_refs,
            source_map=source_map,
        )
        return str(plan["_baseline_masked_text"])

    def set_transaction_fragment_local_no_change(
        self,
        bundle: dict,
        run_dir: Path,
        units: list[dict],
        *,
        fragment_index: int = 0,
    ) -> None:
        chunks = {
            unit["unit_id"]: json.loads(
                (run_dir / "chunks" / f"{unit['unit_id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            for unit in units
        }
        unit_ids = [unit["unit_id"] for unit in units]
        ordered_refs, source_map = finalizer._transaction_source_inventory(
            unit_ids, chunks
        )
        fragment = bundle["fragments"][fragment_index]
        plan = finalizer._validate_structural_transaction_fragment_plan(
            fragment,
            target_unit_id=fragment["target_unit_id"],
            ordered_source_refs=ordered_refs,
            source_map=source_map,
        )
        baseline = str(plan["_baseline_masked_text"])
        fragment["masked_text"] = baseline
        for target_group, block in zip(
            fragment["target_groups"],
            preparer.structural_paragraph_blocks(baseline),
        ):
            target_group["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        if "值得注意的是" in baseline:
            fragment["keep_reasons"] = {
                "LEX-EMPH-01": "课程原段用该提示明确切换观察对象，保留其教学定位功能"
            }
        lines = baseline.replace("\r\n", "\n").replace("\r", "\n").splitlines(
            keepends=True
        )
        evidence_line = next(
            index
            for index, line in enumerate(lines, 1)
            if re.search(r"[\u3400-\u9fff]", line)
        )
        fragment["local_rewrite_intent"] = {
            "decision": "NO_CHANGE",
            "reason": "该目标片段只承接结构移动，保留段内原有对象和措辞",
            "evidence_spans": [
                {
                    "id": "S1",
                    "start_line": evidence_line,
                    "end_line": evidence_line,
                    "sha256": hashlib.sha256(
                        lines[evidence_line - 1].encode("utf-8")
                    ).hexdigest(),
                }
            ],
        }

    def structural_transaction_decline(
        self,
        run_dir: Path,
        units: list[dict],
        *,
        transaction_index: int = 0,
        reason_code: str = "QUESTION_ANSWER_PAIRING_RISK",
        reason: str = "两侧段落分别服务于各自题干，跨单元移动会打乱题解对应关系",
    ) -> dict:
        inventory = json.loads(
            (run_dir / "structural_transaction_inventory.json").read_text(
                encoding="utf-8"
            )
        )
        transaction = inventory["transactions"][transaction_index]
        return {
            "schema_version": "humanize-structural-transaction-decline/v1",
            "decision": "DECLINE",
            "transaction_id": transaction["transaction_id"],
            "transaction_binding_sha256": transaction[
                "transaction_binding_sha256"
            ],
            "transaction_inventory_sha256": inventory["inventory_sha256"],
            "unit_bindings": [
                {
                    "unit_id": unit["unit_id"],
                    "chunk_binding_sha256": unit["chunk_binding_sha256"],
                    "voice_profile_sha256": unit["voice_profile_sha256"],
                }
                for unit in units
            ],
            "reason_code": reason_code,
            "reason": reason,
            "evidence_refs": [
                {
                    "unit_id": unit["unit_id"],
                    "paragraph_id": unit["structural_paragraphs"][0][
                        "paragraph_id"
                    ],
                }
                for unit in units
            ],
        }

    def write_pair_no_change(self, directory: Path, units: list[dict]) -> None:
        for unit in units:
            keep_reasons = (
                {
                    "LEX-EMPH-01": "课程原段用该提示明确切换观察对象，保留其教学定位功能"
                }
                if "值得注意的是" in unit["masked_text"]
                else {}
            )
            payload = self.voice_bound_bundle(
                unit,
                {
                    "decision": "NO_CHANGE",
                    "reason": "现有段序和职责对应清楚",
                    "keep_reasons": keep_reasons,
                },
            )
            (directory / f"{unit['unit_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

    def final_ledger(self, run_dir: Path) -> list[dict[str, str]]:
        with (run_dir / "coverage_ledger.final.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def warning_proposal_fields(self, before_text: str, after_text: str) -> dict:
        before = self.root / "proposal-before.tex"
        after = self.root / "proposal-after.tex"
        before.write_text(before_text, encoding="utf-8")
        after.write_text(after_text, encoding="utf-8")
        first = finalizer.output_validator.validate(
            before,
            after,
            scene="COURSE",
            fragment_mode=True,
        )
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        return {
            "warning_resolutions": {
                fingerprint: "人工建议核对删除的是重复缓和而非结论强度",
            },
            "warning_review_request_sha256": request["request_sha256"],
        }

    def evidence_snapshot(self, run_dir: Path) -> dict[str, bytes]:
        paths = [
            run_dir / "coverage_ledger.final.csv",
            run_dir / "rendered_manifest.csv",
            run_dir / "rollback_manifest.json",
        ]
        for directory in (run_dir / "validation", run_dir / "diffs"):
            paths.extend(path for path in directory.rglob("*") if path.is_file())
        return {
            str(path.relative_to(run_dir)).replace("\\", "/"): path.read_bytes()
            for path in paths
            if path.is_file()
        }

    def assert_compile_check_schema(self, payload: dict) -> None:
        self.assertEqual(self.COMPILE_CHECK_FIELDS, set(payload))
        self.assertIsInstance(payload["status"], str)
        self.assertIsInstance(payload["command"], str)
        self.assertTrue(payload["exit_code"] is None or isinstance(payload["exit_code"], int))
        self.assertIsInstance(payload["stdout"], str)
        self.assertIsInstance(payload["stderr"], str)
        self.assertTrue(payload["cwd"] is None or isinstance(payload["cwd"], str))
        self.assertIn(payload["integrity_status"], {"PASS", "FAIL", "NOT_RUN"})
        self.assertIsInstance(payload["integrity_changes"], dict)
        self.assertIn(
            payload["process_containment"],
            {
                "NOT_RUN",
                "WINDOWS_JOB_OBJECT",
                "LINUX_SUBREAPER_PROCESS_GROUP",
                "LINUX_SUBREAPER_UNAVAILABLE",
                "POSIX_SUBREAPER_UNSUPPORTED",
                "UNAVAILABLE",
            },
        )
        self.assertIn(payload["descendant_cleanup"], {"NOT_RUN", "PASS", "FAIL"})
        self.assertIsInstance(payload["timed_out"], bool)
        self.assertTrue(
            payload["timeout_seconds"] is None
            or isinstance(payload["timeout_seconds"], float)
        )

    def test_valid_rewrite_restores_protected_text_and_writes_diff(self) -> None:
        source, run_dir, unit = self.prepare(
            "\\section{例题}\n值得注意的是，函数 $f(x)=x^2$ 在此处连续。\n"
        )
        rewrites = self.rewrite_dir()
        masked = unit["masked_text"].replace("值得注意的是，", "")
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(unit, {"decision": "REWRITE", "masked_text": masked}),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = finalizer.finalize(run_dir, rewrites)
        ledger = self.final_ledger(run_dir)
        row = next(item for item in ledger if item["unit_id"] == unit["unit_id"])
        self.assert_paired_quality_review_candidate(result)
        self.assertEqual("DONE", row["status"])
        self.assertTrue((run_dir / row["diff_path"]).is_file())
        rendered = next((run_dir / "rendered_review").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        self.assertIn("$f(x)=x^2$", rendered)
        self.assertNotIn("值得注意的是", rendered)
        self.assertEqual("值得注意的是，函数 $f(x)=x^2$ 在此处连续。\n", source.read_text(encoding="utf-8").split("\n", 1)[1])

    def test_rewrite_paired_quality_request_is_persisted_and_hash_bound(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{例题}\n值得注意的是，该结论保留原有限定。\n"
        )
        rewrites = self.rewrite_dir()
        rewritten = unit["masked_text"].replace("值得注意的是，", "")
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit, {"decision": "REWRITE", "masked_text": rewritten}
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result, units=1)
        record = result["paired_quality_review_requests"][unit["unit_id"]]
        self.assertEqual("REWRITE", record["decision"])
        self.assertGreater(record["changes_total"], 0)
        request_path = run_dir / record["path"]
        self.assertTrue(request_path.is_file())
        request = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(
            "humanize-paired-quality-review-request/v1", request["schema"]
        )
        self.assertEqual("PENDING_EXTERNAL_REVIEW", request["status"])
        self.assertEqual("REWRITE", request["validation_context"]["decision"])
        self.assertEqual("PASS", request["validation_context"]["mechanical_validation_status"])
        self.assertEqual(
            {
                "validator_sha256",
                "invariant_checker_sha256",
                "scanner_sha256",
                "lexicon_sha256",
                "report_extractor_sha256",
                "runtime_contract_sha256",
                "paired_quality_verifier_sha256",
                "paired_quality_contract_sha256",
            },
            set(request["policy_hashes"]),
        )
        self.assertTrue(
            all(len(value) == 64 for value in request["policy_hashes"].values())
        )
        validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            validation["evidence"]["before_sha256"],
            request["artifact"]["before_sha256"],
        )
        self.assertEqual(
            validation["evidence"]["after_sha256"],
            request["artifact"]["after_sha256"],
        )
        request_body = dict(request)
        request_body.pop("request_sha256")
        expected_request_sha256 = hashlib.sha256(
            json.dumps(
                request_body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected_request_sha256, request["request_sha256"])
        self.assertEqual(request["request_sha256"], record["request_sha256"])

    def test_no_change_paired_quality_request_cannot_self_clear(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result, units=1)
        record = result["paired_quality_review_requests"][unit["unit_id"]]
        request = json.loads((run_dir / record["path"]).read_text(encoding="utf-8"))
        self.assertEqual("NO_CHANGE", record["decision"])
        self.assertEqual(0, record["changes_total"])
        self.assertEqual("NO_CHANGE", request["validation_context"]["decision"])
        self.assertEqual([], request["changes"])
        self.assertEqual(
            request["artifact"]["before_sha256"],
            request["artifact"]["after_sha256"],
        )
        self.assertFalse(request["limitations"]["quality_clearance_granted"])
        self.assertFalse(
            request["review_contract"]["validator_pass_is_quality_clearance"]
        )
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["humanize_completion_claim_allowed"])

    def test_missing_paired_quality_request_blocks_formal_delivery(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with mock.patch.object(
            finalizer, "_persist_paired_quality_review_request", return_value=None
        ):
            result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual(
            "REVIEW", result["paired_quality_review_request_coverage_status"]
        )
        self.assertEqual("BLOCKED", result["paired_quality_gate_status"])
        self.assertEqual(1, result["paired_quality_units_total"])
        self.assertEqual(0, result["paired_quality_units_pending"])
        self.assertEqual(1, result["paired_quality_units_missing"])
        self.assertEqual({}, result["paired_quality_review_requests"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertEqual(
            "rendered_review", Path(result["published_path"]).name
        )
        self.assertTrue((run_dir / "rendered_review").is_dir())
        self.assertFalse((run_dir / "rendered").exists())

    def test_structural_rewrite_requires_bound_plan_and_accepts_plain_paragraph_move(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n"
            "值得注意的是，第一段说明当前观察对象 $x=1$。\n\n"
            "第二段解释两种表述之间的差别 $y=2$。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [item["paragraph_id"] for item in unit["structural_paragraphs"]]
        self.assertEqual(3, len(blocks))
        target_blocks = [blocks[0], blocks[2], blocks[1].replace("值得注意的是，", "")]
        target_text = "\n\n".join(target_blocks) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[2]], [source_ids[1]]],
        )
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": target_text,
                "structural_plan": plan,
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        ledger = self.final_ledger(run_dir)
        row = next(item for item in ledger if item["unit_id"] == unit["unit_id"])
        evidence = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.structural.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("REVIEW", result["status"], result)
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual(0, result["candidate_assembly_exit_code"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual("PASS", result["structural_plan_status"])
        self.assertEqual(1, result["structural_changes_applied"])
        self.assertEqual("NOT_EVALUATED", result["structural_semantic_mapping"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            result["structural_semantic_review_status"],
        )
        self.assertFalse(result["structural_semantic_review_local_clearance_supported"])
        self.assertFalse(result["voice_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertEqual("DONE", row["status"])
        self.assertEqual("PASS", row["structural_plan_status"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            row["structural_semantic_review_status"],
        )
        self.assertTrue(evidence["change_applied"])
        self.assertEqual("NOT_EVALUATED", evidence["semantic_mapping"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW", evidence["semantic_review_status"]
        )
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())
        request_record = result["structural_semantic_review_requests"][unit["unit_id"]]
        request_path = run_dir / request_record["path"]
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request_body = {
            key: value for key, value in request.items() if key != "request_sha256"
        }
        expected_request_sha256 = hashlib.sha256(
            json.dumps(
                request_body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected_request_sha256, request["request_sha256"])
        self.assertEqual(request["request_sha256"], request_record["request_sha256"])
        self.assertEqual(
            "humanize-structural-semantic-review-request/v1", request["schema"]
        )
        self.assertEqual("PENDING_EXTERNAL_REVIEW", request["status"])
        self.assertFalse(request["trust_boundary"]["local_clearance_supported"])
        self.assertFalse(request["trust_boundary"]["completion_claim_allowed"])
        self.assertTrue(request["structural_deltas"])
        self.assertNotIn(
            ".validation_staging", json.dumps(request, ensure_ascii=False)
        )
        validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            f"validation/{unit['unit_id']}.before.tex",
            validation["evidence"]["before_path"],
        )
        self.assertEqual(
            f"validation/{unit['unit_id']}.after.tex",
            validation["evidence"]["after_path"],
        )

    def test_structural_no_change_does_not_require_semantic_review(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n第一段保持职责。\n\n第二段保持职责。\n",
            intensity="STRUCTURAL",
        )
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "NO_CHANGE",
                "reason": "现有段序和职责对应清楚",
                "keep_reasons": {},
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assert_paired_quality_review_candidate(result)
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("PASS", result["structural_semantic_mapping"])
        self.assertEqual("NOT_REQUIRED", result["structural_semantic_review_status"])
        self.assertEqual({}, result["structural_semantic_review_requests"])
        self.assertEqual("NOT_REQUIRED", row["structural_semantic_review_status"])
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())

    def test_structural_review_request_captures_pending_modality_warning(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n"
            "分析时必须保留这一限制。\n\n"
            "另一种表述中也必须保留同一限制。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [
            item["paragraph_id"] for item in unit["structural_paragraphs"]
        ]
        target_text = "\n\n".join(
            [
                blocks[0],
                "分析时必须保留这一限制。另一种表述沿用同一限制。",
            ]
        ) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[1], source_ids[2]]],
        )
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": target_text,
                "structural_plan": plan,
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["candidate_assembly_status"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            result["structural_semantic_review_status"],
        )
        request_record = result["structural_semantic_review_requests"][unit["unit_id"]]
        request = json.loads(
            (run_dir / request_record["path"]).read_text(encoding="utf-8")
        )
        self.assertIn(
            "SPEECH_ACT_MODALITY_SCOPE_CHANGED",
            {item["code"] for item in request["speech_act_warnings"]},
        )
        self.assertFalse((run_dir / "rendered_review").exists())
        self.assertTrue((run_dir / "rendered_partial").is_dir())

    def test_structural_bundle_cannot_self_issue_semantic_clearance(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n第一段说明对象。\n\n第二段说明差别。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [
            item["paragraph_id"] for item in unit["structural_paragraphs"]
        ]
        target_text = "\n\n".join([blocks[0], blocks[2], blocks[1]]) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[2]], [source_ids[1]]],
        )
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": target_text,
                "structural_plan": plan,
                "structural_semantic_clearance": {
                    "reviewer_kind": "VERIFIED_HUMAN",
                    "overall_status": "PASS",
                },
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("structural_semantic_clearance", row["notes"])
        self.assertEqual({}, result["structural_semantic_review_requests"])

    def test_structural_rewrite_without_plan_is_rejected(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n"
            "值得注意的是，第一段说明当前观察对象。\n\n"
            "第二段解释两种表述之间的差别。\n",
            intensity="STRUCTURAL",
        )
        rewrites = self.rewrite_dir()
        target = unit["masked_text"].replace("值得注意的是，", "")
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit, {"decision": "REWRITE", "masked_text": target}
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["structural_plan_status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("structural_plan_missing", row["notes"])

    def test_structural_plan_cannot_move_locked_heading_paragraph(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n第一段保持职责。\n\n第二段保持职责。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [item["paragraph_id"] for item in unit["structural_paragraphs"]]
        target_text = "\n\n".join([blocks[1], blocks[0], blocks[2]]) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[1]], [source_ids[0]], [source_ids[2]]],
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": target_text,
                        "structural_plan": plan,
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertIn("structural_locked_paragraph_moved_or_merged", row["notes"])

    def test_structural_default_mapping_cannot_hide_payload_swap(self) -> None:
        _source, run_dir, unit = self.prepare(
            "甲对象的作用落在局部条件上。\n\n乙对象的限制来自边界条件。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [item["paragraph_id"] for item in unit["structural_paragraphs"]]
        target_text = "\n\n".join([blocks[1], blocks[0]]) + "\n"
        # Deliberately retain the default one-to-one source IDs.  The target
        # text has moved payload, but the old plan implementation treated this
        # as no structural change.
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[1]]],
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": target_text,
                        "structural_plan": plan,
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("NOT_EVALUATED", result["structural_semantic_mapping"])
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("DONE", row["status"])
        self.assertEqual("PENDING_EXTERNAL_REVIEW", row["structural_semantic_review_status"])

    def test_structural_plan_cannot_detach_formula_from_its_source_paragraph(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n第一段说明对象 $x=1$。\n\n"
            "第二段说明差别 $y=2$。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [item["paragraph_id"] for item in unit["structural_paragraphs"]]
        p2_token = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(blocks[1])
        ).group(0)
        p3_token = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(blocks[2])
        ).group(0)
        detached_p3 = blocks[2].replace(p3_token, p2_token)
        detached_p2 = blocks[1].replace(p2_token, p3_token)
        target_text = "\n\n".join([blocks[0], detached_p3, detached_p2]) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[2]], [source_ids[1]]],
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": target_text,
                        "structural_plan": plan,
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertIn("structural_protected_span_left_source_paragraph", row["notes"])

    def test_structural_plan_rejects_explicit_paragraph_responsibility_drift(self) -> None:
        _source, run_dir, unit = self.prepare(
            "\\section{讨论}\n\n第一段说明当前观察对象。\n\n第二段解释差别。\n",
            intensity="STRUCTURAL",
        )
        blocks = preparer.structural_paragraph_blocks(unit["masked_text"])
        source_ids = [item["paragraph_id"] for item in unit["structural_paragraphs"]]
        target_blocks = [blocks[0], "综上，" + blocks[1], blocks[2]]
        target_text = "\n\n".join(target_blocks) + "\n"
        plan = self.structural_plan(
            unit,
            target_text,
            [[source_ids[0]], [source_ids[1]], [source_ids[2]]],
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": target_text,
                        "structural_plan": plan,
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertIn("structural_target_responsibility_drift", row["notes"])

    def test_ready_candidate_requires_explicit_disposition(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        self.write_pair_no_change(rewrites, units)

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("REVIEW", result["candidate_assembly_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual("PARTIAL", result["publish_state"])
        self.assertEqual(1, result["structural_transaction_candidates_total"])
        self.assertEqual(0, result["structural_transaction_candidates_executed"])
        self.assertEqual(0, result["structural_transaction_candidates_declined"])
        self.assertEqual(1, result["structural_transaction_candidates_pending"])
        self.assertEqual(
            "REVIEW", result["structural_transaction_candidate_coverage_status"]
        )
        self.assertFalse(result["structural_transaction_scope_complete"])
        self.assertFalse(result["coverage_completion_claim_allowed"])
        disposition = next(
            iter(result["structural_transaction_candidate_dispositions"].values())
        )
        self.assertEqual("PENDING", disposition["disposition"])
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_partial").is_dir())

    def test_bound_decline_closes_candidate_without_replacing_unit_coverage(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        decline = self.structural_transaction_decline(run_dir, units)
        (rewrites / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["structural_transaction_candidate_coverage_status"])
        self.assertTrue(result["structural_transaction_scope_complete"])
        self.assertEqual(1, result["structural_transaction_candidates_declined"])
        self.assertEqual(0, result["structural_transaction_candidates_pending"])
        self.assertEqual(2, result["unit_statuses"]["PENDING"])
        self.assertFalse(result["coverage_completion_claim_allowed"])

    def test_bound_decline_and_unit_no_change_publish_final(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        self.write_pair_no_change(rewrites, units)
        decline = self.structural_transaction_decline(run_dir, units)
        (rewrites / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result, units=2)
        self.assertTrue(result["coverage_completion_claim_allowed"])
        self.assertEqual(1, result["structural_transaction_declines_total"])
        self.assertEqual(1, result["structural_transaction_candidates_declined"])
        self.assertEqual(0, result["structural_transaction_candidates_pending"])
        disposition = result["structural_transaction_candidate_dispositions"][
            decline["transaction_id"]
        ]
        self.assertEqual("DECLINED", disposition["disposition"])
        self.assertEqual("PASS", disposition["evidence_member_coverage"])
        self.assertTrue((run_dir / disposition["path"]).is_file())
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())

    def test_decline_rejects_stale_authority_bindings(self) -> None:
        attacks = (
            "transaction_id",
            "transaction_binding_sha256",
            "transaction_inventory_sha256",
            "chunk_binding_sha256",
            "voice_profile_sha256",
        )
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                decline = self.structural_transaction_decline(run_dir, units)
                if attack == "transaction_id":
                    decline[attack] = "STX-" + "f" * 24
                elif attack in {
                    "transaction_binding_sha256",
                    "transaction_inventory_sha256",
                }:
                    decline[attack] = "f" * 64
                else:
                    decline["unit_bindings"][0][attack] = "f" * 64
                (rewrites / "pair.decline.json").write_text(
                    json.dumps(decline, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "structural_transaction_(?:candidate_not_unique|binding_hash_mismatch|inventory_hash_mismatch|chunk_binding_mismatch|voice_binding_mismatch)",
                ):
                    finalizer.finalize(run_dir, rewrites)
        self.root = original_root

    def test_decline_rejects_generic_reason_and_invalid_evidence(self) -> None:
        attacks = (
            "generic_reason",
            "generic_long_reason",
            "single_member",
            "unknown",
            "duplicate",
        )
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                decline = self.structural_transaction_decline(run_dir, units)
                if attack == "generic_reason":
                    decline["reason"] = "候选已经审阅无需调整"
                elif attack == "generic_long_reason":
                    decline["reason"] = "候选已经完成审阅并且无需进行任何调整"
                elif attack == "single_member":
                    decline["evidence_refs"] = [decline["evidence_refs"][0]] * 2
                    decline["evidence_refs"][1]["paragraph_id"] = units[0][
                        "structural_paragraphs"
                    ][1]["paragraph_id"]
                elif attack == "unknown":
                    decline["evidence_refs"][0]["paragraph_id"] = "P999-unknown"
                else:
                    decline["evidence_refs"].append(
                        dict(decline["evidence_refs"][0])
                    )
                (rewrites / "pair.decline.json").write_text(
                    json.dumps(decline, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "structural_transaction_decline_(?:reason_not_specific|evidence_ref_duplicate|evidence_ref_unknown|evidence_member_coverage_mismatch)",
                ):
                    finalizer.finalize(run_dir, rewrites)
        self.root = original_root

    def test_transaction_execution_and_decline_conflict(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        transaction = self.structural_transaction_bundle(run_dir, units)
        decline = self.structural_transaction_decline(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(transaction, ensure_ascii=False), encoding="utf-8"
        )
        (rewrites / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "execution and decline conflict"):
            finalizer.finalize(run_dir, rewrites)

    def test_decline_replay_is_deterministic(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        self.write_pair_no_change(rewrites, units)
        decline = self.structural_transaction_decline(run_dir, units)
        (rewrites / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )

        first = finalizer.finalize(run_dir, rewrites)
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        decline_before = (run_dir / "validation" / f"{decline['transaction_id']}.decline.json").read_bytes()
        second = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(second, units=2)
        self.assertEqual("PASS", second["assembly_replay_idempotency"])
        self.assertEqual(
            first["structural_transaction_candidate_dispositions"],
            second["structural_transaction_candidate_dispositions"],
        )
        self.assertEqual(
            rendered_before, _directory_bytes(run_dir / "rendered_review")
        )
        self.assertEqual(
            decline_before,
            (run_dir / "validation" / f"{decline['transaction_id']}.decline.json").read_bytes(),
        )

    def test_overlapping_candidates_require_individual_dispositions(self) -> None:
        _source, run_dir, pending, inventory = self.prepare_structural_chain()
        rewrites = self.rewrite_dir()
        self.write_pair_no_change(rewrites, pending)
        unit_by_id = {unit["unit_id"]: unit for unit in pending}

        first_candidate = inventory["transactions"][0]
        first_units = [
            unit_by_id[item["unit_id"]]
            for item in first_candidate["compound_refs"]
        ]
        first_decline = self.structural_transaction_decline(
            run_dir,
            first_units,
            transaction_index=0,
            reason_code="NO_CROSS_UNIT_STYLE_GAIN",
            reason="两侧段落已经各自承担完整说明职责，跨单元移动没有独立文风收益",
        )
        (rewrites / "first.decline.json").write_text(
            json.dumps(first_decline, ensure_ascii=False), encoding="utf-8"
        )

        first = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", first["status"])
        self.assertEqual(1, first["structural_transaction_candidates_declined"])
        self.assertEqual(
            len(inventory["transactions"]) - 1,
            first["structural_transaction_candidates_pending"],
        )

        for index, candidate in enumerate(inventory["transactions"][1:], 1):
            candidate_units = [
                unit_by_id[item["unit_id"]] for item in candidate["compound_refs"]
            ]
            decline = self.structural_transaction_decline(
                run_dir,
                candidate_units,
                transaction_index=index,
                reason_code="DEPENDENCY_OR_REFERENT_RISK",
                reason="相邻说明依赖各自单元中的观察对象，跨单元移动会造成指代范围漂移",
            )
            (rewrites / f"candidate-{index}.decline.json").write_text(
                json.dumps(decline, ensure_ascii=False), encoding="utf-8"
            )

        second = finalizer.finalize(run_dir, rewrites)
        self.assert_paired_quality_review_candidate(second, units=5)
        self.assertEqual(
            len(inventory["transactions"]),
            second["structural_transaction_candidates_declined"],
        )
        self.assertEqual(0, second["structural_transaction_candidates_pending"])
        self.assertTrue(second["structural_transaction_scope_complete"])

    def test_v5_scaffold_accepts_bound_transaction_member_substitution(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "REWRITE")
        for unit in units:
            (rewrites / f"{unit['unit_id']}.json").unlink()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual(1, result["structural_transaction_candidates_executed"])
        self.assertEqual(0, result["structural_transaction_candidates_pending"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual(
            {"DONE"},
            {
                row["status"]
                for row in self.final_ledger(run_dir)
                if row["unit_id"] in {unit["unit_id"] for unit in units}
            },
        )

    def test_v5_scaffold_decline_does_not_substitute_for_unit_bundles(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "NO_CHANGE")
        for unit in units:
            (rewrites / f"{unit['unit_id']}.json").unlink()
        decline = self.structural_transaction_decline(run_dir, units)
        (rewrites / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "bundle coverage mismatch"):
            finalizer.finalize(run_dir, rewrites)
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / "rendered_partial").exists())
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_v5_no_change_scaffold_cannot_be_replaced_by_transaction(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.root / "scaffold-rewrites"
        scaffolder.scaffold(run_dir, rewrites, "NO_CHANGE")
        for unit in units:
            (rewrites / f"{unit['unit_id']}.json").unlink()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValueError,
            "transaction substitution requires REWRITE decision",
        ):
            finalizer.finalize(run_dir, rewrites)
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / "rendered_partial").exists())
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_structural_transaction_v3_passes_two_fragments_and_document_gate(self) -> None:
        source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("REVIEW", result["status"], result)
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual(1, result["structural_transaction_candidates_executed"])
        self.assertEqual(0, result["structural_transaction_candidates_pending"])
        self.assertEqual(
            "EXECUTED",
            result["structural_transaction_candidate_dispositions"][
                bundle["transaction_id"]
            ]["disposition"],
        )
        self.assertEqual("PASS", transaction["atomic_gate_status"], transaction)
        self.assertEqual("PASS", transaction["source_member_claim_status"])
        self.assertEqual(
            {unit["unit_id"]: "PASS" for unit in units},
            transaction["fragment_gate_statuses"],
        )
        self.assertEqual("PASS", transaction["document_gate_status"])
        self.assertTrue(transaction["change_applied"])
        self.assertEqual(
            {"DONE"}, {ledger[unit["unit_id"]]["status"] for unit in units}
        )
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / "rendered_partial").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())
        self.assertEqual(
            source.read_text(encoding="utf-8"),
            "\\section{讨论}\n\n"
            "值得注意的是，第一段说明当前观察对象。\n\n"
            "第二段补充两种表述之间的差别 $x=1$。\n\n"
            "第三段说明另一组观察对象 $y=2$。\n\n"
            "值得注意的是，第四段补充比较结果。\n",
        )
        request_record = result["structural_transaction_review_requests"][
            bundle["transaction_id"]
        ]
        request = json.loads(
            (run_dir / request_record["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            finalizer.STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA,
            request["schema"],
        )
        self.assertEqual(
            [unit["unit_id"] for unit in units], request["unit_ids"]
        )
        self.assertEqual("NOT_EVALUATED", request["trust_boundary"]["semantic_mapping"])
        self.assertFalse(request["trust_boundary"]["local_clearance_supported"])
        self.assertEqual(2, len(request["source_mapping"]))
        self.assertTrue(
            any(
                "CROSS_UNIT_MOVE" in delta["change_kinds"]
                for delta in request["structural_deltas"]
            )
        )
        self.assertEqual(4, len(request["context_hashes"]))
        self.assertEqual(
            bundle["transaction_binding_sha256"],
            request["transaction_binding_sha256"],
        )
        self.assertEqual(2, len(request["frozen_pair"]["compound_refs"]))
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        self.assertEqual(2, result["rewrite_intent_units_pass"])
        self.assertEqual(0, result["rewrite_intent_units_review"])
        self.assertEqual(0, result["rewrite_intent_units_missing"])

    def test_structural_transaction_v3_binds_fragment_intent_and_evidence(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("PASS", transaction["atomic_gate_status"])
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        self.assertEqual(2, result["rewrite_intent_units_pass"])
        self.assertEqual(0, result["rewrite_intent_units_review"])
        self.assertEqual(0, result["rewrite_intent_units_missing"])
        transaction_request = result["structural_transaction_review_requests"][
            bundle["transaction_id"]
        ]
        request = json.loads(
            (run_dir / transaction_request["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            finalizer.STRUCTURAL_TRANSACTION_REVIEW_REQUEST_SCHEMA,
            request["schema"],
        )
        self.assertEqual(
            {unit["unit_id"] for unit in units},
            set(request["fragment_rewrite_intents"]),
        )
        self.assertTrue(
            all(
                item["status"] == "PASS"
                for item in request["fragment_rewrite_intents"].values()
            )
        )
        for unit in units:
            unit_id = unit["unit_id"]
            record = result["rewrite_intent_evidence"][unit_id]
            evidence = json.loads(
                (run_dir / record["path"]).read_text(encoding="utf-8")
            )
            paired = result["paired_quality_review_requests"][unit_id]
            body = {
                key: value
                for key, value in evidence.items()
                if key != "evidence_sha256"
            }
            self.assertEqual(
                "humanize-transaction-fragment-rewrite-intent-evidence/v1",
                evidence["schema_version"],
            )
            self.assertEqual("PASS", evidence["status"])
            self.assertEqual(transaction["bundle_sha256"], evidence["bundle_sha256"])
            self.assertEqual(
                paired["request_sha256"],
                evidence["paired_quality_review_request_sha256"],
            )
            self.assertEqual(
                transaction_request["request_sha256"],
                evidence["structural_transaction_review_request_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(
                    finalizer._canonical_json(body).encode("utf-8")
                ).hexdigest(),
                evidence["evidence_sha256"],
            )
            self.assertEqual(record["path"], paired["rewrite_intent_evidence_path"])

    def test_structural_transaction_v1_and_v2_are_read_compatible_schema_reviews(
        self,
    ) -> None:
        original_root = self.root
        try:
            for schema_version in ("v1", "v2"):
                with self.subTest(schema_version=schema_version), tempfile.TemporaryDirectory() as temp:
                    self.root = Path(temp)
                    source, run_dir, units = self.prepare_structural_pair()
                    source_before = source.read_bytes()
                    rewrites = self.rewrite_dir()
                    bundle = (
                        self.structural_transaction_v1_bundle(run_dir, units)
                        if schema_version == "v1"
                        else self.structural_transaction_v2_bundle(run_dir, units)
                    )
                    (rewrites / "pair.transaction.json").write_text(
                        json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
                    )

                    result = finalizer.finalize(run_dir, rewrites)
                    transaction = result["structural_transaction_results"][
                        bundle["transaction_id"]
                    ]

                    self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
                    self.assertEqual("SCHEMA_GATE", transaction["rollback_reason"])
                    self.assertFalse(transaction["change_applied"])
                    self.assertEqual("REVIEW", transaction["rewrite_intent_schema_status"])
                    self.assertEqual(
                        {unit["unit_id"]: "PASS" for unit in units},
                        transaction["fragment_gate_statuses"],
                    )
                    self.assertEqual(
                        {unit["unit_id"]: "REVIEW" for unit in units},
                        transaction["fragment_rewrite_intent_statuses"],
                    )
                    self.assertIn(
                        "structural_transaction_current_v3_schema_required",
                        transaction["errors"],
                    )
                    self.assertEqual({}, result["rewrite_intent_evidence"])
                    partial = next((run_dir / "rendered_partial").rglob("*.tex"))
                    self.assertEqual(source_before, partial.read_bytes())
        finally:
            self.root = original_root

    def test_structural_transaction_v3_allows_fragment_local_no_change(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        self.set_transaction_fragment_local_no_change(bundle, run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("PASS", transaction["atomic_gate_status"], transaction)
        self.assertEqual("PASS", result["rewrite_intent_coverage_status"])
        evidence = result["rewrite_intent_evidence"][units[0]["unit_id"]]
        payload = json.loads((run_dir / evidence["path"]).read_text(encoding="utf-8"))
        self.assertEqual("NO_CHANGE", payload["decision"])
        self.assertEqual("NOT_APPLICABLE", payload["intent_diff_binding"]["status"])

    def test_structural_transaction_v3_template_field_scope_is_source_bound_without_quality_clearance(
        self,
    ) -> None:
        _source, run_dir, units = self.prepare_structural_pair(template_field=True)
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        fragment = next(
            item
            for item in bundle["fragments"]
            if "适用题目：" in self.structural_transaction_fragment_baseline(
                run_dir, units, item
            )
        )
        baseline = self.structural_transaction_fragment_baseline(
            run_dir, units, fragment
        )
        line = next(
            index
            for index, text in enumerate(baseline.splitlines(), 1)
            if text.startswith("适用题目：")
        )
        fragment["template_field_edit_scope"] = {
            "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "permission_boundary": "PAYLOAD_ONLY",
            "edits": [
                {
                    "line": line,
                    "label": "适用题目",
                    "permission": "PAYLOAD_ONLY",
                    "reason": "适用题目字段中的值得注意的是只承担空泛强调功能，删除后仍保留第四段比较对象和结果范围",
                }
            ],
        }
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        unit_id = fragment["target_unit_id"]
        validation_path = run_dir / "validation" / f"{unit_id}.validation.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        scope_path = (
            run_dir
            / "validation"
            / f"{unit_id}.template-field-edit-scope.json"
        )
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
        before_path = run_dir / "validation" / f"{unit_id}.before.tex"

        self.assertEqual("PASS", transaction["atomic_gate_status"], transaction)
        self.assertEqual("PASS", transaction["rewrite_intent_schema_status"])
        self.assertEqual("PASS", transaction["fragment_gate_statuses"][unit_id])
        self.assertEqual("PASS", validation["template_field_layer_status"])
        self.assertEqual(
            ["TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED"],
            [item["code"] for item in validation["template_field_findings"]],
        )
        self.assertEqual(
            hashlib.sha256(before_path.read_bytes()).hexdigest(),
            scope["source_sha256"],
        )
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            validation["paired_quality_review_status"],
        )
        self.assertFalse(
            validation["paired_quality_review_local_clearance_supported"]
        )
        self.assertFalse(validation["paired_quality_clearance_granted"])
        self.assertFalse(result["paired_quality_local_clearance_supported"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_structural_transaction_v3_invalid_template_scope_rolls_back_pair_and_publishes_independent_unit(
        self,
    ) -> None:
        source, run_dir, units = self.prepare_structural_pair(
            extra_pending=True, template_field=True
        )
        source_before = source.read_text(encoding="utf-8")
        pending = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        ]
        unit_ids = {unit["unit_id"] for unit in units}
        independent = next(unit for unit in pending if unit["unit_id"] not in unit_ids)
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        fragment = next(
            item
            for item in bundle["fragments"]
            if "适用题目：" in self.structural_transaction_fragment_baseline(
                run_dir, units, item
            )
        )
        baseline = self.structural_transaction_fragment_baseline(
            run_dir, units, fragment
        )
        wrong_line = next(
            index
            for index, text in enumerate(baseline.splitlines(), 1)
            if text and not text.startswith("适用题目：")
        )
        fragment["template_field_edit_scope"] = {
            "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "permission_boundary": "PAYLOAD_ONLY",
            "edits": [
                {
                    "line": wrong_line,
                    "label": "适用题目",
                    "permission": "PAYLOAD_ONLY",
                    "reason": "授权行必须绑定结构基线中的适用题目字段载荷",
                }
            ],
        }
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        independent_after = independent["masked_text"].replace(
            "仍待处理", "仍需处理", 1
        )
        independent_bundle = self.v3_rewrite_bundle(
            run_dir,
            independent,
            masked_text=independent_after,
            source_span=self.masked_line_span(
                independent["masked_text"], "仍待处理"
            ),
            summary="把独立附录中的暂存措辞改为明确的后续处理说明",
            target_signal="STYLE-INDEPENDENT-PROGRESS",
        )
        independent_bundle["structural_plan"] = self.structural_plan(
            independent,
            independent_after,
            [
                [paragraph["paragraph_id"]]
                for paragraph in independent["structural_paragraphs"]
            ],
        )
        (rewrites / f"{independent['unit_id']}.json").write_text(
            json.dumps(independent_bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        partial_path = next((run_dir / "rendered_partial").rglob("*.tex"))
        partial = partial_path.read_text(encoding="utf-8")

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PARTIAL", result["publish_state"])
        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertEqual("FRAGMENT_GATE", transaction["rollback_reason"])
        self.assertEqual(
            "REVIEW",
            transaction["fragment_gate_statuses"][fragment["target_unit_id"]],
        )
        self.assertTrue(
            any(
                "invalid_template_field_edit_scope" in error
                for error in transaction["errors"]
            ),
            transaction,
        )
        self.assertEqual(
            {"UNRESOLVED"},
            {ledger[unit["unit_id"]]["status"] for unit in units},
        )
        self.assertEqual("DONE", ledger[independent["unit_id"]]["status"])
        for unit in units:
            self.assertEqual(
                source_before[int(unit["start"]) : int(unit["end"])],
                partial[int(unit["start"]) : int(unit["end"])],
            )
        self.assertIn("附录中的独立说明仍需处理。", partial)
        self.assertEqual(source_before, source.read_text(encoding="utf-8"))
        rollback = json.loads(
            (run_dir / "rollback_manifest.json").read_text(encoding="utf-8")
        )["atomic_transactions"][bundle["transaction_id"]]
        self.assertEqual(0, rollback["accepted_member_count"])
        self.assertEqual(0, rollback["published_member_count"])

    def test_structural_transaction_v3_authorized_template_role_drift_is_review_and_rolls_back(
        self,
    ) -> None:
        source, run_dir, units = self.prepare_structural_pair(template_field=True)
        source_before = source.read_bytes()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        fragment = next(
            item
            for item in bundle["fragments"]
            if "适用题目：" in self.structural_transaction_fragment_baseline(
                run_dir, units, item
            )
        )
        baseline = self.structural_transaction_fragment_baseline(
            run_dir, units, fragment
        )
        line = next(
            index
            for index, text in enumerate(baseline.splitlines(), 1)
            if text.startswith("适用题目：")
        )
        fragment["template_field_edit_scope"] = {
            "schema_version": finalizer.UNIT_TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "permission_boundary": "PAYLOAD_ONLY",
            "edits": [
                {
                    "line": line,
                    "label": "适用题目",
                    "permission": "PAYLOAD_ONLY",
                    "reason": "仅授权调整字段载荷措辞，不授权改变适用关系或否定范围",
                }
            ],
        }
        before_line = "适用题目：第四段补充比较结果。"
        after_line = "适用题目：不能用于第四段补充比较结果。"
        self.assertIn(before_line, fragment["masked_text"])
        fragment["masked_text"] = fragment["masked_text"].replace(
            before_line, after_line, 1
        )
        for target_group, block in zip(
            fragment["target_groups"],
            preparer.structural_paragraph_blocks(fragment["masked_text"]),
        ):
            target_group["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        unit_id = fragment["target_unit_id"]
        validation = json.loads(
            (run_dir / "validation" / f"{unit_id}.validation.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertEqual("FRAGMENT_GATE", transaction["rollback_reason"])
        self.assertEqual("REVIEW", transaction["fragment_gate_statuses"][unit_id])
        self.assertEqual("REVIEW", validation["template_field_layer_status"])
        self.assertIn(
            "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT",
            [item["code"] for item in validation["template_field_findings"]],
        )
        self.assertEqual(source_before, source.read_bytes())
        partial = next((run_dir / "rendered_partial").rglob("*.tex"))
        self.assertEqual(source_before, partial.read_bytes())

    def test_structural_transaction_v3_requires_template_scope_key_on_every_fragment(
        self,
    ) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        bundle["fragments"][0].pop("template_field_edit_scope")
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValueError, "structural_transaction_fragment_fields_invalid"
        ):
            finalizer.collect_rewrites(rewrites)

    def test_structural_transaction_v2_rejects_fragment_intent_hash_mismatch(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v2_bundle(run_dir, units)
        local = bundle["fragments"][0]["local_rewrite_intent"]
        local["rewrite_intent"]["source_spans"][0]["sha256"] = "f" * 64
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertTrue(
            any("rewrite_intent_source_spans_sha256_mismatch" in error for error in transaction["errors"]),
            transaction,
        )
        self.assertEqual({}, result["rewrite_intent_evidence"])

    def test_structural_transaction_v2_rejects_local_no_change_with_hidden_edit(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v2_bundle(run_dir, units)
        self.set_transaction_fragment_local_no_change(bundle, run_dir, units)
        fragment = bundle["fragments"][0]
        fragment["masked_text"] = fragment["masked_text"].replace(
            "当前观察对象", "当前观察范围", 1
        )
        for target_group, block in zip(
            fragment["target_groups"],
            preparer.structural_paragraph_blocks(fragment["masked_text"]),
        ):
            target_group["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertTrue(
            any("transaction_fragment_NO_CHANGE_has_local_diff" in error for error in transaction["errors"]),
            transaction,
        )
        self.assertEqual({}, result["rewrite_intent_evidence"])

    def test_structural_transaction_v2_rejects_undeclared_second_local_change(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v2_bundle(run_dir, units)
        fragment = bundle["fragments"][0]
        fragment["masked_text"] = fragment["masked_text"].replace(
            "另一组观察对象", "另一组观察范围", 1
        )
        for target_group, block in zip(
            fragment["target_groups"],
            preparer.structural_paragraph_blocks(fragment["masked_text"]),
        ):
            target_group["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertTrue(
            any("rewrite_intent_diff_outside_declared_spans" in error for error in transaction["errors"]),
            transaction,
        )
        self.assertEqual({}, result["rewrite_intent_evidence"])

    def test_structural_transaction_explicit_null_schema_is_not_a_unit_bundle(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        bundle["schema_version"] = None
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValueError, "structural_transaction_bundle_schema_invalid"
        ):
            finalizer.finalize(run_dir, rewrites)

    def test_structural_transaction_v3_replay_keeps_intent_evidence_bytes(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        first = finalizer.finalize(run_dir, rewrites)
        evidence_before = {
            unit["unit_id"]: (run_dir / first["rewrite_intent_evidence"][unit["unit_id"]]["path"]).read_bytes()
            for unit in units
        }

        second = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("PASS", second["idempotency"])
        self.assertEqual(
            evidence_before,
            {
                unit["unit_id"]: (
                    run_dir
                    / second["rewrite_intent_evidence"][unit["unit_id"]]["path"]
                ).read_bytes()
                for unit in units
            },
        )

    def test_structural_transaction_single_fragment_failure_rolls_back_both(self) -> None:
        source, run_dir, units = self.prepare_structural_pair()
        source_before = source.read_bytes()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        second = bundle["fragments"][1]
        protected = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(second["masked_text"])
        ).group(0)
        second["masked_text"] = second["masked_text"].replace(protected, "", 1)
        target_blocks = preparer.structural_paragraph_blocks(second["masked_text"])
        for target, block in zip(second["target_groups"], target_blocks):
            target["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertEqual(1, result["structural_transaction_candidates_executed"])
        self.assertEqual(0, result["structural_transaction_candidates_pending"])
        self.assertEqual(
            "EXECUTED",
            result["structural_transaction_candidate_dispositions"][
                bundle["transaction_id"]
            ]["disposition"],
        )
        self.assertEqual("PASS", transaction["fragment_gate_statuses"][units[0]["unit_id"]])
        self.assertEqual("FAIL", transaction["fragment_gate_statuses"][units[1]["unit_id"]])
        self.assertEqual("NOT_RUN", transaction["document_gate_status"])
        self.assertEqual(
            {"UNRESOLVED"},
            {ledger[unit["unit_id"]]["status"] for unit in units},
        )
        self.assertTrue(
            all(not ledger[unit["unit_id"]]["diff_path"] for unit in units)
        )
        self.assertFalse((run_dir / "rendered_review").exists())
        self.assertEqual({}, result["paired_quality_review_requests"])
        self.assertEqual([], list((run_dir / "validation").glob(
            "*.paired-quality-review-request.json"
        )))
        self.assertEqual(source_before, source.read_bytes())
        rollback = json.loads(
            (run_dir / "rollback_manifest.json").read_text(encoding="utf-8")
        )["atomic_transactions"][bundle["transaction_id"]]
        self.assertEqual(0, rollback["accepted_member_count"])
        self.assertEqual(0, rollback["published_member_count"])

    def test_structural_transaction_repetition_block_rolls_back_entire_pair(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        repetition_result = {
            "schema_version": "humanize-cross-unit-repetition/v1",
            "status": "REVIEW",
            "expected_units": 2,
            "evaluated_units": 2,
            "before_blocks": 6,
            "after_blocks": 6,
            "findings": [],
            "finding_count": 1,
            "inherited_findings": [],
            "inherited_finding_count": 0,
            "blocking_unit_ids": [units[0]["unit_id"]],
            "review_reasons": [],
        }

        with mock.patch.object(
            finalizer,
            "_audit_cross_unit_repetition",
            return_value=repetition_result,
        ):
            result = finalizer.finalize(run_dir, rewrites)

        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertEqual("CROSS_UNIT_REPETITION", transaction["rollback_reason"])
        self.assertEqual(
            {"UNRESOLVED"},
            {ledger[unit["unit_id"]]["status"] for unit in units},
        )
        self.assertTrue(
            all(not ledger[unit["unit_id"]]["diff_path"] for unit in units)
        )
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_transaction_inventory_self_reseal_cannot_replace_frozen_rebuild(self) -> None:
        _source, run_dir, _units = self.prepare_structural_pair()
        inventory_path = run_dir / "structural_transaction_inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["transactions"][0]["constraints"][
            "semantic_clearance_granted"
        ] = True
        inventory.pop("inventory_sha256")
        inventory["inventory_sha256"] = preparer.canonical_sha256(inventory)
        inventory_path.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        resealed = preparer.build_integrity_manifest(run_dir)
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(resealed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError, "structural transaction inventory rebuild mismatch"
        ):
            finalizer.finalize(run_dir, self.rewrite_dir())

    def test_finalizer_enforces_strict_v2_integrity_manifest_contract(self) -> None:
        attacks = ("duplicate", "path_traversal", "unknown_field", "invalid_bytes")
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, _units = self.prepare_structural_pair()
                path = run_dir / "prepare_integrity.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if attack == "duplicate":
                    manifest["artifacts"].append(dict(manifest["artifacts"][0]))
                elif attack == "path_traversal":
                    manifest["artifacts"][0]["path"] = "../outside.json"
                elif attack == "unknown_field":
                    manifest["authority"] = "caller"
                else:
                    manifest["artifacts"][0]["bytes"] = True
                path.write_text(
                    json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "integrity"):
                    finalizer.finalize(run_dir, self.rewrite_dir())
        self.root = original_root

    def test_legacy_integrity_schema_cannot_authorize_transaction_inventory(self) -> None:
        _source, run_dir, _units = self.prepare_structural_pair()
        path = run_dir / "prepare_integrity.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        legacy = {"schema_version": 1, "artifacts": manifest["artifacts"]}
        path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError, "legacy prepare integrity cannot authorize transactions"
        ):
            finalizer.finalize(run_dir, self.rewrite_dir())

    def test_transaction_member_cannot_also_have_standalone_bundle(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        standalone = self.voice_bound_bundle(
            units[0],
            {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
        )
        (rewrites / f"{units[0]['unit_id']}.json").write_text(
            json.dumps(standalone, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ValueError, "member also has standalone rewrite"
        ):
            finalizer.finalize(run_dir, rewrites)

    def test_structural_transaction_shape_rejects_duplicate_members(self) -> None:
        original_root = self.root
        for attack in ("binding", "fragment"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                bundle = self.structural_transaction_bundle(run_dir, units)
                if attack == "binding":
                    bundle["unit_bindings"][1] = dict(bundle["unit_bindings"][0])
                else:
                    bundle["fragments"][1]["target_unit_id"] = bundle[
                        "fragments"
                    ][0]["target_unit_id"]
                (rewrites / "pair.transaction.json").write_text(
                    json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "unit_binding_duplicate|fragment_target_duplicate",
                ):
                    finalizer.collect_rewrites(rewrites)
        self.root = original_root

    def test_structural_transaction_atomic_count_gate_rejects_half_state(self) -> None:
        result = {
            "unit_ids": ["U-one", "U-two"],
            "atomic_gate_status": "PASS",
        }
        half = {
            "U-one": {"status": "DONE"},
            "U-two": {"status": "UNRESOLVED"},
        }
        with self.assertRaisesRegex(ValueError, "acceptance_partial"):
            finalizer._structural_transaction_atomic_counts(
                result,
                half,
                published=False,
            )
        result["atomic_gate_status"] = "ROLLED_BACK"
        with self.assertRaisesRegex(ValueError, "retained_member"):
            finalizer._structural_transaction_atomic_counts(
                result,
                half,
                published=False,
            )

        complete = {
            "U-one": {"status": "DONE"},
            "U-two": {"status": "DONE"},
        }
        result["atomic_gate_status"] = "PASS"
        self.assertEqual(
            {
                "atomic_member_count": 2,
                "accepted_member_count": 2,
                "published_member_count": 2,
            },
            finalizer._structural_transaction_atomic_counts(
                result,
                complete,
                published=True,
            ),
        )

    def test_transaction_member_cannot_be_claimed_by_two_transactions(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        first = self.structural_transaction_bundle(run_dir, units)
        second = json.loads(json.dumps(first))
        second["transaction_id"] = "STX-" + "b" * 24
        (rewrites / "first.transaction.json").write_text(
            json.dumps(first, ensure_ascii=False), encoding="utf-8"
        )
        (rewrites / "second.transaction.json").write_text(
            json.dumps(second, ensure_ascii=False), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "member claimed twice"):
            finalizer.finalize(run_dir, rewrites)

    def test_transaction_source_ref_attacks_roll_back_both_members(self) -> None:
        attacks = ("duplicate", "unknown", "locked_cross_unit")
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                bundle = self.structural_transaction_bundle(run_dir, units)
                if attack == "duplicate":
                    bundle["fragments"][1]["target_groups"][0]["source_refs"] = [
                        dict(
                            bundle["fragments"][0]["target_groups"][1][
                                "source_refs"
                            ][0]
                        )
                    ]
                elif attack == "unknown":
                    bundle["fragments"][1]["target_groups"][0]["source_refs"] = [
                        {"unit_id": "U-third", "paragraph_id": "P001-unknown"}
                    ]
                else:
                    heading_block = preparer.structural_paragraph_blocks(
                        units[0]["masked_text"]
                    )[0]
                    heading = units[0]["structural_paragraphs"][0]
                    bundle["fragments"][1]["masked_text"] = "\n\n".join(
                        [
                            heading_block,
                            preparer.structural_paragraph_blocks(
                                bundle["fragments"][1]["masked_text"]
                            )[1],
                        ]
                    ) + "\n"
                    target = bundle["fragments"][1]["target_groups"][0]
                    target["source_refs"] = [
                        {
                            "unit_id": units[0]["unit_id"],
                            "paragraph_id": heading["paragraph_id"],
                        }
                    ]
                    target["target_paragraph_sha256"] = hashlib.sha256(
                        heading_block.encode("utf-8")
                    ).hexdigest()
                    target["responsibility"] = heading["responsibility"]
                (rewrites / "pair.transaction.json").write_text(
                    json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
                )

                result = finalizer.finalize(run_dir, rewrites)
                ledger = {
                    row["unit_id"]: row for row in self.final_ledger(run_dir)
                }
                transaction = result["structural_transaction_results"][
                    bundle["transaction_id"]
                ]
                self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
                self.assertEqual(
                    {"UNRESOLVED"},
                    {ledger[unit["unit_id"]]["status"] for unit in units},
                )
                self.assertTrue(
                    all(
                        not ledger[unit["unit_id"]]["diff_path"] for unit in units
                    )
                )
                self.assertFalse((run_dir / "rendered_review").exists())
        self.root = original_root

    def test_transaction_document_gate_failure_rolls_back_two_fragment_passes(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        original_check = finalizer.invariants.check_documents

        def fail_document_only(before, after, **kwargs):
            result = original_check(before, after, **kwargs)
            if not kwargs.get("fragment_mode", False):
                result.errors.append(
                    finalizer.invariants.Diagnostic(
                        code="TEST_DOCUMENT_GATE_FAILURE",
                        severity="error",
                        message="forced document gate failure",
                    )
                )
            return result

        with mock.patch.object(
            finalizer.invariants,
            "check_documents",
            side_effect=fail_document_only,
        ):
            result = finalizer.finalize(run_dir, rewrites)

        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        self.assertEqual(
            {unit["unit_id"]: "PASS" for unit in units},
            transaction["fragment_gate_statuses"],
        )
        self.assertEqual("FAIL", transaction["document_gate_status"])
        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertTrue(
            all(ledger[unit["unit_id"]]["status"] == "UNRESOLVED" for unit in units)
        )
        self.assertTrue(
            all(not ledger[unit["unit_id"]]["diff_path"] for unit in units)
        )

    def test_transaction_stale_binding_surfaces_roll_back_both_members(self) -> None:
        attacks = (
            "transaction_binding_sha256",
            "transaction_inventory_sha256",
            "chunk_binding_sha256",
            "voice_profile_sha256",
            "transaction_id",
        )
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                bundle = self.structural_transaction_bundle(run_dir, units)
                if attack in {
                    "transaction_binding_sha256",
                    "transaction_inventory_sha256",
                }:
                    bundle[attack] = "f" * 64
                elif attack == "transaction_id":
                    bundle[attack] = "STX-" + "f" * 24
                else:
                    bundle["unit_bindings"][0][attack] = "f" * 64
                (rewrites / "pair.transaction.json").write_text(
                    json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
                )

                result = finalizer.finalize(run_dir, rewrites)
                transaction = result["structural_transaction_results"][
                    bundle["transaction_id"]
                ]
                ledger = {
                    row["unit_id"]: row for row in self.final_ledger(run_dir)
                }
                self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
                self.assertEqual("AUTHORITY_BINDING", transaction["rollback_reason"])
                self.assertTrue(
                    all(
                        ledger[unit["unit_id"]]["status"] == "UNRESOLVED"
                        and not ledger[unit["unit_id"]]["diff_path"]
                        for unit in units
                    )
                )
        self.root = original_root

    def test_transaction_strict_schema_rejects_bare_refs_clearance_and_path_id(self) -> None:
        attacks = ("bare_ref", "self_clearance", "path_id")
        original_root = self.root
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, units = self.prepare_structural_pair()
                rewrites = self.rewrite_dir()
                bundle = self.structural_transaction_bundle(run_dir, units)
                if attack == "bare_ref":
                    bundle["fragments"][0]["target_groups"][0][
                        "source_refs"
                    ] = [units[0]["structural_paragraphs"][0]["paragraph_id"]]
                elif attack == "self_clearance":
                    bundle["structural_semantic_clearance"] = {
                        "reviewer_kind": "VERIFIED_HUMAN",
                        "status": "PASS",
                    }
                else:
                    bundle["transaction_id"] = "../STX-escape"
                (rewrites / "pair.transaction.json").write_text(
                    json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "structural_transaction_(?:source_ref_fields|bundle_fields|id)_invalid",
                ):
                    finalizer.finalize(run_dir, rewrites)
        self.root = original_root

    def test_transaction_never_enters_partial_when_other_unit_is_pending(self) -> None:
        source, run_dir, units = self.prepare_structural_pair(extra_pending=True)
        source_before = source.read_text(encoding="utf-8")
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        transaction = result["structural_transaction_results"][
            bundle["transaction_id"]
        ]
        self.assertEqual("ROLLED_BACK", transaction["atomic_gate_status"])
        self.assertEqual(
            "INCOMPLETE_DOCUMENT_COVERAGE", transaction["rollback_reason"]
        )
        self.assertFalse((run_dir / "rendered_review").exists())
        partial = next((run_dir / "rendered_partial").rglob("*.tex"))
        self.assertEqual(source_before, partial.read_text(encoding="utf-8"))
        rollback = json.loads(
            (run_dir / "rollback_manifest.json").read_text(encoding="utf-8")
        )["atomic_transactions"][bundle["transaction_id"]]
        self.assertEqual(0, rollback["accepted_member_count"])
        self.assertEqual(0, rollback["published_member_count"])

    def test_transaction_review_candidate_replay_is_idempotent(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        first = finalizer.finalize(run_dir, rewrites)
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        request_before = first["structural_transaction_review_requests"][
            bundle["transaction_id"]
        ]["request_sha256"]

        second = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("PASS", second["idempotency"])
        self.assertEqual(rendered_before, _directory_bytes(run_dir / "rendered_review"))
        self.assertEqual(
            request_before,
            second["structural_transaction_review_requests"][
                bundle["transaction_id"]
            ]["request_sha256"],
        )

    def test_failed_transaction_rerun_preserves_previous_review_candidate(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        path = rewrites / "pair.transaction.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        first = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", first["status"])
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        evidence_before = self.evidence_snapshot(run_dir)

        second_fragment = bundle["fragments"][1]
        protected = next(
            preparer.PROTECTED_PLACEHOLDER_RE.finditer(
                second_fragment["masked_text"]
            )
        ).group(0)
        second_fragment["masked_text"] = second_fragment["masked_text"].replace(
            protected, "", 1
        )
        for target, block in zip(
            second_fragment["target_groups"],
            preparer.structural_paragraph_blocks(second_fragment["masked_text"]),
        ):
            target["target_paragraph_sha256"] = hashlib.sha256(
                block.encode("utf-8")
            ).hexdigest()
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

        second = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("FAIL", second["status"])
        self.assertEqual(rendered_before, _directory_bytes(run_dir / "rendered_review"))
        self.assertEqual(evidence_before, self.evidence_snapshot(run_dir))

    def test_failed_transaction_v3_intent_rerun_preserves_previous_evidence(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_v3_bundle(run_dir, units)
        path = rewrites / "pair.transaction.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        first = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("PASS", first["rewrite_intent_coverage_status"])
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        evidence_before = self.evidence_snapshot(run_dir)

        bundle["fragments"][0]["local_rewrite_intent"]["rewrite_intent"][
            "source_spans"
        ][0]["sha256"] = "f" * 64
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

        second = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("FAIL", second["status"])
        self.assertTrue(second["failed_attempt"])
        self.assertEqual(rendered_before, _directory_bytes(run_dir / "rendered_review"))
        self.assertEqual(evidence_before, self.evidence_snapshot(run_dir))

    def test_transaction_compile_failure_publishes_no_review_candidate(self) -> None:
        source, run_dir, units = self.prepare_structural_pair()
        source_before = source.read_bytes()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        command = f'"{sys.executable}" -c "raise SystemExit(9)"'

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", result["status"])
        self.assertEqual(9, result["compile_check"]["exit_code"])
        self.assertFalse((run_dir / "rendered_review").exists())
        self.assertTrue((run_dir / "failed_staging").is_dir())
        self.assertEqual(source_before, source.read_bytes())
        rollback = json.loads(
            (run_dir / "rollback_manifest.json").read_text(encoding="utf-8")
        )["atomic_transactions"][bundle["transaction_id"]]
        self.assertEqual(0, rollback["published_member_count"])

    def test_transaction_revises_previous_quality_review_candidate(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        no_change = self.rewrite_dir()
        self.write_pair_no_change(no_change, units)
        decline = self.structural_transaction_decline(run_dir, units)
        (no_change / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )
        first = finalizer.finalize(run_dir, no_change)
        self.assert_paired_quality_review_candidate(first, units=2)
        review_before = _directory_bytes(run_dir / "rendered_review")

        transactions = self.root / "transaction-rewrites"
        transactions.mkdir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (transactions / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        second = finalizer.finalize(run_dir, transactions)

        self.assert_paired_quality_review_candidate(second, units=2)
        self.assertFalse(second["published_namespace_conflict"])
        self.assertNotEqual(
            review_before, _directory_bytes(run_dir / "rendered_review")
        )
        self.assertEqual("NOT_APPLICABLE_PROGRESS", second["idempotency"])
        self.assertTrue((run_dir / "partial_history.jsonl").is_file())
        self.assertFalse((run_dir / "rendered").exists())

    def test_no_change_revises_previous_transaction_review_candidate(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        transactions = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (transactions / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        first = finalizer.finalize(run_dir, transactions)
        self.assert_paired_quality_review_candidate(first, units=2)
        review_before = _directory_bytes(run_dir / "rendered_review")

        no_change = self.root / "no-change-rewrites"
        no_change.mkdir()
        self.write_pair_no_change(no_change, units)
        decline = self.structural_transaction_decline(run_dir, units)
        (no_change / "pair.decline.json").write_text(
            json.dumps(decline, ensure_ascii=False), encoding="utf-8"
        )
        second = finalizer.finalize(run_dir, no_change)

        self.assert_paired_quality_review_candidate(second, units=2)
        self.assertFalse(second["published_namespace_conflict"])
        self.assertNotEqual(
            review_before, _directory_bytes(run_dir / "rendered_review")
        )
        self.assertEqual("NOT_APPLICABLE_PROGRESS", second["idempotency"])
        self.assertEqual("PASS", second["structural_semantic_mapping"])
        self.assertEqual("NOT_REQUIRED", second["structural_semantic_review_status"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_transaction_rejects_second_pass_receipt_as_false_convergence(self) -> None:
        _source, run_dir, units = self.prepare_structural_pair()
        rewrites = self.rewrite_dir()
        bundle = self.structural_transaction_bundle(run_dir, units)
        (rewrites / "pair.transaction.json").write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(
            run_dir,
            rewrites,
            second_pass_receipt=self.root / "caller-receipt.json",
        )

        self.assertEqual("FAIL", result["status"])
        self.assertEqual("FAIL", result["humanize_second_pass_convergence"])
        self.assertEqual(
            "second_pass_receipt_not_allowed_for_review_candidate:STRUCTURAL_TRANSACTION",
            result["humanize_second_pass_evidence"]["error"],
        )
        self.assertEqual("INVALID_EVIDENCE", result["second_pass_stability_status"])
        self.assertFalse(result["second_pass_quality_clearance_granted"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_paired_quality_candidate_rejects_second_pass_receipt(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(
            run_dir,
            rewrites,
            second_pass_receipt=self.root / "caller-receipt.json",
        )

        self.assertEqual("FAIL", result["status"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("FAIL", result["humanize_second_pass_convergence"])
        self.assertEqual(
            "second_pass_receipt_not_allowed_for_review_candidate:PAIRED_QUALITY",
            result["humanize_second_pass_evidence"]["error"],
        )
        self.assertEqual("INVALID_EVIDENCE", result["second_pass_stability_status"])
        self.assertFalse(result["second_pass_quality_clearance_granted"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_cross_chunk_tex_boundary_uses_fragment_validation_then_full_check(self) -> None:
        source, run_dir, unit = self.prepare(
            "\\begin{document}\n"
            "\\begin{abstract}\n"
            "值得注意的是，结论保持不变。\n"
            "\\end{abstract}\n\n"
            "\\section{下一节}\n"
            "下一节正文保持不变。\n"
            "\\end{document}\n"
        )
        source_text = source.read_text(encoding="utf-8")
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
        ]
        unit = next(
            item
            for item in chunks
            if item["status"] == "PENDING"
            and "\\begin{document}"
            in source_text[int(item["start"]):int(item["end"])]
        )
        original = source_text[int(unit["start"]):int(unit["end"])]
        self.assertIn("\\begin{document}", original)
        self.assertNotIn("\\end{document}", original)
        rewrites = self.rewrite_dir()
        masked = unit["masked_text"].replace("值得注意的是，", "")
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "REWRITE", "masked_text": masked},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        ledger = {
            row["unit_id"]: row for row in self.final_ledger(run_dir)
        }
        validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual("DONE", ledger[unit["unit_id"]]["status"])
        self.assertEqual("REVIEW", validation["status"])
        self.assertEqual("PASS", validation["mechanical_validation_status"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW", validation["paired_quality_review_status"]
        )
        self.assertEqual("FRAGMENT", validation["evidence"]["document_scope"])
        self.assertEqual([], result["full_format_errors"])
        self.assertEqual("REVIEW", result["status"])

    def test_utf8_bom_rewrite_bundle_is_accepted(self) -> None:
        source, run_dir, unit = self.prepare(
            "\\section{例题}\n值得注意的是，函数 $f(x)=x^2$ 在此处连续。\n"
        )
        rewrites = self.rewrite_dir()
        payload = json.dumps(
            self.voice_bound_bundle(
                unit,
                {
                    "decision": "REWRITE",
                    "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                },
            ),
            ensure_ascii=False,
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(payload, encoding="utf-8-sig")

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result)
        rendered = next((run_dir / "rendered_review").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        self.assertIn("$f(x)=x^2$", rendered)
        self.assertNotIn("值得注意的是", rendered)

    def test_rewrite_bundle_cannot_be_renamed_across_units(self) -> None:
        source = self.root / "replay.tex"
        source.write_text(
            "\\section{甲}\n甲段保持简洁。\n\n\\section{乙}\n乙段保持简洁。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "replay-run"
        preparer.prepare([source], run_dir, scene="COURSE", min_author_chars=0)
        pending = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )
        self.assertGreaterEqual(len(pending), 2)
        first, second = pending[:2]
        rewrites = self.rewrite_dir()
        replayed = self.voice_bound_bundle(
            first,
            {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
        )
        (rewrites / f"{second['unit_id']}.json").write_text(
            json.dumps(replayed, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        ledger = {row["unit_id"]: row for row in self.final_ledger(run_dir)}
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["rewrite_binding_status"])
        self.assertEqual("UNRESOLVED", ledger[second["unit_id"]]["status"])
        self.assertIn("bundle_unit_id_mismatch", ledger[second["unit_id"]]["notes"])
        self.assertEqual("PENDING", ledger[first["unit_id"]]["status"])

    def test_wrong_chunk_binding_hash_is_rejected_before_text_validation(self) -> None:
        _, run_dir, unit = self.prepare("\\section{例题}\n该段保持简洁。\n")
        rewrites = self.rewrite_dir()
        payload = self.voice_bound_bundle(
            unit,
            {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
        )
        payload["chunk_binding_sha256"] = "f" * 64
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("REVIEW", result["rewrite_binding_status"])
        self.assertEqual(1, result["rewrite_bindings_mismatched"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("chunk_binding_hash_mismatch", row["notes"])

    def test_authorized_tex_style_wrapper_can_be_removed_without_losing_text(self) -> None:
        source = self.root / "main.tex"
        source.write_text(
            "\\section{结果}\n普通说明与\\textbf{装饰性强调}并列。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare(
            [source],
            run_dir,
            scene="GENERAL",
            min_author_chars=0,
            editable_style_wrappers=["textbf"],
        )
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        self.assertIn(r"\textbf{装饰性强调}", unit["masked_text"])

        rewrites = self.rewrite_dir()
        rewritten = unit["masked_text"].replace(r"\textbf{装饰性强调}", "装饰性强调")
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(unit, {"decision": "REWRITE", "masked_text": rewritten}),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result)
        rendered = next((run_dir / "rendered_review").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        self.assertNotIn(r"\textbf", rendered)
        self.assertIn("装饰性强调", rendered)
        self.assertIn(r"\textbf{装饰性强调}", source.read_text(encoding="utf-8"))

    def test_missing_placeholder_rejects_unit_atomically(self) -> None:
        source, run_dir, unit = self.prepare("\\section{例题}\n文字与 $x=1$ 同时出现。\n")
        rewrites = self.rewrite_dir()
        masked = re_placeholder = unit["masked_text"]
        import re

        masked = re.sub(r"\[\[PROTECTED:[^\]]+\]\]", "", re_placeholder, count=1)
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(unit, {"decision": "REWRITE", "masked_text": masked}),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertEqual("FAIL", row["protected_hashes_ok"])
        rendered = next((run_dir / "rendered_partial").rglob("*.tex"))
        self.assertEqual(
            source.read_bytes(),
            rendered.read_bytes(),
            "a rejected protected candidate must fall back to frozen source bytes",
        )

    def test_placeholder_hash_drift_rejects_unit_atomically(self) -> None:
        source, run_dir, unit = self.prepare("\\section{例题}\n文字与 $x=1$ 同时出现。\n")
        rewrites = self.rewrite_dir()
        import re

        def drift_hash(match: re.Match[str]) -> str:
            digest = match.group("digest")
            replacement = ("0" if digest[0] != "0" else "1") + digest[1:]
            return f"{match.group('prefix')}{replacement}{match.group('suffix')}"

        masked = re.sub(
            r"(?P<prefix>\[\[PROTECTED:[^:\]]+:)"
            r"(?P<digest>[0-9a-f]{12})(?P<suffix>\]\])",
            drift_hash,
            unit["masked_text"],
            count=1,
        )
        self.assertNotEqual(unit["masked_text"], masked)
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "REWRITE", "masked_text": masked},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(
            item
            for item in self.final_ledger(run_dir)
            if item["unit_id"] == unit["unit_id"]
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertEqual("FAIL", row["protected_hashes_ok"])
        rendered = next((run_dir / "rendered_partial").rglob("*.tex"))
        self.assertEqual(
            source.read_bytes(),
            rendered.read_bytes(),
            "placeholder hash drift must not reach the partial publication",
        )

    def test_no_change_requires_specific_reason(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        bundle_path = rewrites / f"{unit['unit_id']}.json"
        bundle_path.write_text(
            json.dumps(
                self.voice_bound_bundle(unit, {"decision": "NO_CHANGE", "reason": "短"}),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("UNRESOLVED", row["status"])

    def test_no_change_with_high_signal_requires_specific_keep_reason(self) -> None:
        _, run_dir, unit = self.prepare("\\section{提示}\n这条规则必须牢记。\n")
        rewrites = self.rewrite_dir()
        bundle = rewrites / f"{unit['unit_id']}.json"
        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "用户明确锁定这条教学原句"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        rejected = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", rejected["status"])
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("UNRESOLVED", row["status"])

        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "用户明确锁定这条教学原句",
                        "keep_reasons": {"LEX-COACH-01": "用户明确锁定的直接教学提醒"},
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        accepted = finalizer.finalize(run_dir, rewrites)
        self.assert_paired_quality_review_candidate(accepted)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("NO_CHANGE", row["status"])

    def test_mismatched_warning_proposal_keeps_unit_unresolved(self) -> None:
        source_text = "\\section{结果}\n结果可能变化。\n"
        _, run_dir, unit = self.prepare(source_text)
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": unit["masked_text"].replace("结果可能变化", "结果发生变化"),
                **self.warning_proposal_fields(
                    source_text[int(unit["start"]):int(unit["end"])],
                    source_text[int(unit["start"]):int(unit["end"])].replace(
                        "结果可能变化", "结果发生变化"
                    ),
                ),
            },
        )
        bundle["warning_review_request_sha256"] = "0" * 64
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("warning_review_request_sha256 does not match", row["notes"])
        self.assertFalse(result["full_completion_claim_allowed"])

    def test_agent_cannot_attest_long_document_warning_proposal(self) -> None:
        source_text = "\\section{结果}\n结果可能变化。\n"
        _, run_dir, unit = self.prepare(source_text)
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": unit["masked_text"].replace("结果可能变化", "结果发生变化"),
                **self.warning_proposal_fields(
                    source_text[int(unit["start"]):int(unit["end"])],
                    source_text[int(unit["start"]):int(unit["end"])].replace(
                        "结果可能变化", "结果发生变化"
                    ),
                ),
                "warning_review": {
                    "reviewer_kind": "AGENT",
                    "reviewer_id": "forward-agent",
                },
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("warning_reviewer_identity_metadata_retired", row["notes"])
        self.assertNotEqual("PASS", row["style_validation"])

    def test_identity_free_proposal_is_recorded_but_cannot_complete_unit(self) -> None:
        source_text = "\\section{结果}\n结果可能变化。\n"
        _, run_dir, unit = self.prepare(source_text)
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": unit["masked_text"].replace("结果可能变化", "结果发生变化"),
            },
        )
        bundle_path = rewrites / f"{unit['unit_id']}.json"
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False),
            encoding="utf-8",
        )

        initial_result = finalizer.finalize(run_dir, rewrites)
        initial_validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(
                encoding="utf-8"
            )
        )
        request = initial_validation["warning_review_request"]
        bundle.update(
            {
                "warning_resolutions": {
                    request["warnings"][0]["warning_fingerprint"]:
                        "人工建议核对删除的是重复缓和而非结论强度",
                },
                "warning_review_request_sha256": request["request_sha256"],
            }
        )
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        validation = json.loads(
            (run_dir / "validation" / f"{unit['unit_id']}.validation.json").read_text(encoding="utf-8")
        )
        proposal = validation["warning_proposal_state"]

        self.assertEqual("REVIEW", initial_result["status"])
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["reviewer_identifier_collected"])
        self.assertFalse(proposal["identity_verified"])
        self.assertFalse(proposal["review_clearance_granted"])
        self.assertNotIn("reviewer_id_sha256", json.dumps(validation, ensure_ascii=False))
        self.assertNotIn("warning_review", validation)

    def test_warning_review_metadata_without_resolution_is_unresolved(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{例题}\n值得注意的是，函数 $f(x)=x^2$ 在此处连续。\n"
        )
        rewrites = self.rewrite_dir()
        bundle = self.voice_bound_bundle(
            unit,
            {
                "decision": "REWRITE",
                "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                "warning_review": {
                    "reviewer_kind": "HUMAN",
                    "reviewer_id": "external-reviewer",
                },
            },
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(bundle, ensure_ascii=False),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("warning_reviewer_identity_metadata_retired", row["notes"])
        self.assertFalse(result["full_completion_claim_allowed"])

    def test_all_warning_reviewer_ids_are_retired(self) -> None:
        for index, reviewer_id in enumerate(("ab", "x" * 129)):
            with self.subTest(reviewer_id_length=len(reviewer_id)):
                root = self.root / f"case-{index}"
                root.mkdir()
                source = root / "main.tex"
                source.write_text("\\section{结果}\n结果可能变化。\n", encoding="utf-8")
                run_dir = root / "run"
                preparer.prepare([source], run_dir, scene="COURSE", min_author_chars=0)
                unit = next(
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (run_dir / "chunks").glob("*.json")
                    if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
                )
                rewrites = root / "rewrites"
                rewrites.mkdir()
                source_text = "\\section{结果}\n结果可能变化。\n"
                proposal = self.warning_proposal_fields(
                    source_text[int(unit["start"]):int(unit["end"])],
                    source_text[int(unit["start"]):int(unit["end"])].replace(
                        "结果可能变化", "结果发生变化"
                    ),
                )
                (rewrites / f"{unit['unit_id']}.json").write_text(
                    json.dumps(
                        self.voice_bound_bundle(
                            unit,
                            {
                                "decision": "REWRITE",
                                "masked_text": unit["masked_text"].replace("结果可能变化", "结果发生变化"),
                                **proposal,
                                "warning_review": {
                                    "reviewer_kind": "HUMAN",
                                    "reviewer_id": reviewer_id,
                                },
                            },
                        ),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                result = finalizer.finalize(run_dir, rewrites)
                with (run_dir / "coverage_ledger.final.csv").open(
                    "r", encoding="utf-8-sig", newline=""
                ) as handle:
                    row = next(
                        item for item in csv.DictReader(handle) if item["unit_id"] == unit["unit_id"]
                    )

                self.assertEqual("REVIEW", result["status"])
                self.assertEqual("UNRESOLVED", row["status"])
                self.assertIn("warning_reviewer_identity_metadata_retired", row["notes"])

    def test_legacy_acceptance_and_authority_field_injection_are_unresolved(self) -> None:
        _, run_dir, unit = self.prepare("\\section{结果}\n结果可能变化。\n")
        rewrites = self.rewrite_dir()
        path = rewrites / f"{unit['unit_id']}.json"
        path.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("结果可能变化", "结果发生变化"),
                        "accepted_warnings": {},
                        "status": "PASS",
                        "identity_verified": True,
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("unknown_rewrite_bundle_fields", row["notes"])

    def test_incomplete_rewrites_leave_pending_and_forbid_completion_claim(self) -> None:
        source = self.root / "main.tex"
        source.write_text("\\section{一}\n第一段。\n\\section{二}\n第二段。\n", encoding="utf-8")
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, min_author_chars=0)
        rewrites = self.rewrite_dir()
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertGreater(result["unit_statuses"].get("PENDING", 0), 0)
        self.assertTrue((run_dir / "rendered_partial").is_dir())

    def test_tampered_units_ledger_cannot_forge_full_completion(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        units_path = run_dir / "units.jsonl"
        rows = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        target = next(row for row in rows if row["unit_id"] == unit["unit_id"])
        target.update({
            "status": "DONE",
            "hash_after": target["hash_before"],
            "style_validation": "PASS",
            "protected_hashes_ok": "PASS",
        })
        units_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "(?:prepare|integrity) artifact .*mismatch"):
            finalizer.finalize(run_dir, self.rewrite_dir())

        self.assertFalse((run_dir / "rendered").exists())

    def test_tampered_units_and_forged_integrity_manifest_still_fail_rebuild(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        units_path = run_dir / "units.jsonl"
        rows = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        target = next(row for row in rows if row["unit_id"] == unit["unit_id"])
        target["status"] = "DONE"
        target["hash_after"] = target["hash_before"]
        units_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        forged = preparer.build_integrity_manifest(run_dir)
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(forged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "initial prepare state mismatch"):
            finalizer.finalize(run_dir, self.rewrite_dir())

        self.assertFalse((run_dir / "rendered").exists())

    def test_generated_include_is_preserved_without_entering_authoring_queue(self) -> None:
        main = self.root / "main.tex"
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        generated = generated_dir / "auto.tex"
        main.write_text(
            "\\input{generated/auto}\n主文件作者正文保持原有范围。\n",
            encoding="utf-8",
        )
        generated_bytes = (
            "% AUTO-GENERATED FILE. DO NOT EDIT\r\n"
            "生成文件的字节、换行与正文必须原样保留。\r\n"
        ).encode("utf-8")
        generated.write_bytes(generated_bytes)
        run_dir = self.root / "generated-run"
        preparer.prepare(
            [main], run_dir, scene="GENERAL", intensity="BALANCED", min_author_chars=0
        )
        with (run_dir / "file_manifest.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            manifest = list(csv.DictReader(handle))
        generated_row = next(
            row for row in manifest if Path(row["path"]).name == "auto.tex"
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
        ]
        pending = [item for item in chunks if item["status"] == "PENDING"]
        self.assertTrue(pending)
        self.assertFalse(any(item["file_id"] == generated_row["file_id"] for item in chunks))
        rewrites = self.rewrite_dir()
        for unit in pending:
            (rewrites / f"{unit['unit_id']}.json").write_text(
                json.dumps(
                    self.voice_bound_bundle(
                        unit,
                        {
                            "decision": "NO_CHANGE",
                            "reason": "该作者段保留原有对象、范围和限定方式",
                        },
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result)
        rendered_generated = next(
            path
            for path in (run_dir / "rendered_review").rglob("*")
            if path.is_file() and path.name.casefold() == "auto.tex"
        )
        self.assertEqual(generated_bytes, rendered_generated.read_bytes())

    def test_resealed_source_role_override_hash_tamper_fails_rebuild(self) -> None:
        main = self.root / "main.tex"
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        chapter = generated_dir / "chapter.tex"
        main.write_text("\\input{generated/chapter}\n主文件正文。\n", encoding="utf-8")
        chapter.write_text("明确纳入的作者章节。\n", encoding="utf-8")
        override = self.root / "source-role-scope.json"
        override.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-source-role-overrides/v1",
                    "overrides": [
                        {
                            "path": "generated/chapter.tex",
                            "source_role": "AUTHOR_TEXT",
                            "reason": "用户明确将该章节纳入本轮作者正文范围",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run_dir = self.root / "override-run"
        preparer.prepare(
            [main],
            run_dir,
            scene="GENERAL",
            min_author_chars=0,
            source_role_overrides=override,
        )
        artifact_path = run_dir / "source_role_overrides.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["overrides"][0]["applied_files"][0]["snapshot_sha256"] = "f" * 64
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(
                preparer.build_integrity_manifest(run_dir),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "applied-file binding mismatch"):
            finalizer.finalize(run_dir, self.rewrite_dir())
        self.assertFalse((run_dir / "rendered_review").exists())

    def test_empty_prepare_scope_cannot_claim_full_completion(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        run_dir = self.root / "run"
        preparer.prepare([empty], run_dir, scene="COURSE", min_author_chars=0)

        result = finalizer.finalize(run_dir, self.rewrite_dir())

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertTrue(result["empty_processable_scope"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_concurrent_finalize_same_run_is_serialized(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: finalizer.finalize(run_dir, rewrites), range(2)))

        self.assertEqual(["REVIEW", "REVIEW"], [result["status"] for result in results])
        for result in results:
            self.assert_paired_quality_review_candidate(result)
        self.assertEqual(
            ["NOT_RUN", "PASS"],
            sorted(result["idempotency"] for result in results),
        )
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())

    def test_tampered_units_and_self_resealed_integrity_cannot_forge_completion(self) -> None:
        source = self.root / "main.md"
        source.write_text(
            "## \u6807\u9898\n"
            "\u8fd9\u662f\u4e00\u6bb5\u8db3\u591f\u957f\u7684\u4e2d\u6587\u6b63\u6587\uff0c"
            "\u7528\u4e8e\u9a8c\u8bc1\u521d\u59cb\u72b6\u6001\u4e0d\u80fd\u88ab\u4f2a\u9020\u3002\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="GENERAL", min_author_chars=0)

        units_path = run_dir / "units.jsonl"
        rows = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        target = next(row for row in rows if row["status"] == "PENDING")
        target.update(
            {
                "status": "SKIPPED_PROTECTED",
                "hash_after": "",
                "style_validation": "NOT_RUN",
                "protected_hashes_ok": "NOT_RUN",
            }
        )
        units_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

        # Model an attacker who also rewrites the self-reported integrity
        # manifest after changing the mutable units ledger.
        integrity_path = run_dir / "prepare_integrity.json"
        integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
        for artifact in integrity["artifacts"]:
            artifact_path = run_dir / artifact["path"]
            artifact["sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            artifact["bytes"] = artifact_path.stat().st_size
        integrity_path.write_text(
            json.dumps(integrity, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "initial prepare state mismatch|canonical chunk"):
            finalizer.finalize(run_dir, self.rewrite_dir())
        self.assertFalse((run_dir / "rendered").exists())

    def test_tampered_prepare_completion_metadata_cannot_pass_after_local_reseal(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持原有平行结构。\n")
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.update(
            {
                "status": "PASS",
                "completion_claim_allowed": True,
                "processable_editable_units": 0,
                "no_editable_scope": True,
                "unit_statuses": {"DONE": 999},
            }
        )
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(
                preparer.build_integrity_manifest(run_dir),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保留平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "run metadata derived fields mismatch"):
            finalizer.finalize(run_dir, rewrites)
        self.assertFalse((run_dir / "rendered").exists())

    def test_resealed_frozen_routing_policy_cannot_replace_current_policy(self) -> None:
        _, run_dir, unit = self.prepare("\\section{例题}\n本题先判断方向。\n")
        policy_path = run_dir / "scene_routing_policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["purpose"] = "attacker supplied replacement policy"
        policy_path.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _, forged_sha = preparer.scene_router.load_policy(policy_path)
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["scene_routing_policy_sha256"] = forged_sha
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(
                preparer.build_integrity_manifest(run_dir),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "题解表达已经直接"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "policy changed after prepare"):
            finalizer.finalize(run_dir, rewrites)

    def test_resealed_old_policy_snapshot_cannot_be_consumed_after_policy_drift(self) -> None:
        _, run_dir, unit = self.prepare("\\section{例题}\n本题先判断方向。\n")
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        snapshot = dict(metadata["policy_snapshot"])
        implementation_hashes = dict(snapshot["implementation_hashes"])
        implementation_hashes["finalize_script_sha256"] = "0" * 64
        snapshot["implementation_hashes"] = implementation_hashes
        metadata["policy_snapshot"] = snapshot
        metadata["policy_snapshot_sha256"] = preparer.policy_snapshot_sha256(snapshot)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(
                preparer.build_integrity_manifest(run_dir),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "原句已经直接"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"run policy snapshot drift: components=implementation_hashes\.finalize_script_sha256; total=1; values_redacted=true",
        ) as caught:
            finalizer.finalize(run_dir, rewrites)
        self.assertNotIn("0" * 64, str(caught.exception))
        self.assertNotIn(str(run_dir), str(caught.exception))

    def test_policy_snapshot_drift_diagnostic_bounds_untrusted_structure(self) -> None:
        current = preparer.build_policy_snapshot()
        forged = dict(current)
        forged["private-C:\\Users\\secret\\document.tex"] = "sensitive-value"
        validators = dict(current["validator_policy_hashes"])
        validators["attacker-controlled-secret-name"] = "0" * 64
        forged["validator_policy_hashes"] = validators

        components, total = preparer._policy_snapshot_drift_components(
            forged, current, limit=1
        )
        self.assertEqual(["snapshot_structure"], components)
        self.assertEqual(2, total)
        diagnostic = f"components={','.join(components)}; total={total}; values_redacted=true"
        self.assertNotIn("secret", diagnostic)
        self.assertNotIn("sensitive-value", diagnostic)
        self.assertNotIn("0" * 64, diagnostic)

    def test_resealed_unit_route_voice_ledger_and_chunk_forgery_fails_source_rebuild(self) -> None:
        _, run_dir, unit = self.prepare("\\section{例题}\n本题先判断方向。\n")
        units_path = run_dir / "units.jsonl"
        units = [
            json.loads(line)
            for line in units_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        target = next(item for item in units if item["unit_id"] == unit["unit_id"])
        target["scene"] = "RESEARCH"
        target["scene_routing_decision"] = "ROUTED"
        target["voice_profile_binding_scene"] = "RESEARCH"
        target["voice_profile_sha256"] = "f" * 64
        units_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                for item in units
            ),
            encoding="utf-8",
        )
        chunk_path = run_dir / "chunks" / f"{unit['unit_id']}.json"
        chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
        chunk.update(
            {
                "scene": "RESEARCH",
                "scene_routing_decision": "ROUTED",
                "voice_profile_binding_scene": "RESEARCH",
                "voice_profile_sha256": "f" * 64,
            }
        )
        chunk["chunk_binding_sha256"] = preparer.chunk_binding_sha256(chunk)
        chunk_path.write_text(
            json.dumps(chunk, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        target["chunk_binding_sha256"] = chunk["chunk_binding_sha256"]
        units_path.write_text(
            "".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                for item in units
            ),
            encoding="utf-8",
        )
        ledger_path = run_dir / "coverage_ledger.csv"
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        for row in rows:
            if row["unit_id"] == unit["unit_id"]:
                row.update(
                    {
                        "scene": "RESEARCH",
                        "scene_routing_decision": "ROUTED",
                        "voice_profile_binding_scene": "RESEARCH",
                        "voice_profile_sha256": "f" * 64,
                        "chunk_binding_sha256": chunk["chunk_binding_sha256"],
                    }
                )
        with ledger_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(
                preparer.build_integrity_manifest(run_dir),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "voice binding unit mismatch|initial prepare state mismatch"):
            finalizer.finalize(run_dir, self.rewrite_dir())

    def test_tampered_chunk_cannot_forge_prepare_integrity(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        chunk_path = run_dir / "chunks" / f"{unit['unit_id']}.json"
        payload = json.loads(chunk_path.read_text(encoding="utf-8"))
        payload["status"] = "DONE"
        chunk_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "(?:prepare|integrity) artifact .*mismatch"):
            finalizer.finalize(run_dir, self.rewrite_dir())

    def test_missing_prepare_integrity_refuses_finalize(self) -> None:
        _, run_dir, _ = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        (run_dir / "prepare_integrity.json").unlink()

        with self.assertRaisesRegex(ValueError, "missing prepare_integrity.json"):
            finalizer.finalize(run_dir, self.rewrite_dir())

        self.assertFalse((run_dir / "rendered").exists())

    def test_repeat_with_same_output_is_idempotent(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first = finalizer.finalize(run_dir, rewrites)
        second = finalizer.finalize(run_dir, rewrites)
        self.assert_paired_quality_review_candidate(first)
        self.assert_paired_quality_review_candidate(second)
        self.assertEqual("PASS", second["idempotency"])

    def test_compile_failure_keeps_source_and_does_not_publish_rendered(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = f'"{sys.executable}" -c "raise SystemExit(7)"'
        result = finalizer.finalize(run_dir, rewrites, check_command=command)
        self.assertEqual("FAIL", result["status"])
        self.assert_compile_check_schema(result["compile_check"])
        self.assertEqual(7, result["compile_check"]["exit_code"])
        self.assertEqual("PASS", result["compile_check"]["integrity_status"])
        self.assertEqual({}, result["compile_check"]["integrity_changes"])
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "failed_staging").is_dir())
        self.assertEqual("\\section{定义}\n该定义保持平行结构。\n", source.read_text(encoding="utf-8"))

    def test_progressive_partial_run_publishes_review_candidate_without_formal_output(self) -> None:
        source = self.root / "main.tex"
        source.write_text("\\section{一}\n第一段。\n\\section{二}\n第二段。\n", encoding="utf-8")
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, min_author_chars=0)
        chunks = [json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "chunks").glob("*.json")]
        pending = [item for item in chunks if item["status"] == "PENDING"]
        rewrites = self.rewrite_dir()
        first = pending[0]
        (rewrites / f"{first['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    first,
                    {"decision": "NO_CHANGE", "reason": "该段属于自然简短陈述"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result_one = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result_one["status"])
        self.assertTrue((run_dir / "rendered_partial").is_dir())
        second = pending[1]
        (rewrites / f"{second['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    second,
                    {"decision": "NO_CHANGE", "reason": "该段属于自然简短陈述"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result_two = finalizer.finalize(run_dir, rewrites)
        self.assert_paired_quality_review_candidate(result_two)
        self.assertFalse((run_dir / "rendered").exists())
        self.assertTrue((run_dir / "rendered_review").is_dir())
        self.assertFalse((run_dir / "rendered_partial").exists())
        self.assertEqual(
            (run_dir / "rendered_review").resolve(),
            Path(result_two["published_path"]).resolve(),
        )
        history = [
            json.loads(line)
            for line in (run_dir / "partial_history.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual("full_review_candidate_published", history[-1]["reason"])
        self.assertTrue(history[-1]["old_hashes"])
        self.assertTrue(history[-1]["new_hashes"])

    def test_file_level_garbled_gap_blocks_full_completion(self) -> None:
        main = self.root / "main.tex"
        bad = self.root / "bad.tex"
        main.write_text("\\input{bad}\n", encoding="utf-8")
        bad.write_bytes(b"\x81\x30\xff\xff\x81")
        run_dir = self.root / "run"
        preparer.prepare([main], run_dir, min_author_chars=0)
        rewrites = self.rewrite_dir()
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(1, result["file_statuses"].get("SKIPPED_GARBLED", 0))
        self.assertTrue((run_dir / "rendered_partial").is_dir())

    def test_dynamic_include_gap_blocks_full_completion(self) -> None:
        main = self.root / "main.tex"
        chapter_dir = self.root / "chapters"
        chapter_dir.mkdir()
        (chapter_dir / "chapter.tex").write_text("\\section{章节}\n章节正文。\n", encoding="utf-8")
        main.write_text(
            "\\newcommand{\\chapterdir}{chapters}\n"
            "\\input{\\chapterdir/chapter}\n"
            "主文件正文。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([main], run_dir, min_author_chars=0)
        rewrites = self.rewrite_dir()
        for path in (run_dir / "chunks").glob("*.json"):
            unit = json.loads(path.read_text(encoding="utf-8"))
            if unit["status"] == "PENDING":
                (rewrites / f"{unit['unit_id']}.json").write_text(
                    json.dumps(
                        self.voice_bound_bundle(
                            unit,
                            {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
                        ),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(1, result["file_statuses"].get("UNRESOLVED_INCLUDE", 0))

    def test_source_change_after_snapshot_is_rechecked_at_finalize(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        source.write_text(source.read_text(encoding="utf-8") + "% external append\n", encoding="utf-8")
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(1, result["source_files_changed_since_snapshot"])
        self.assertTrue((run_dir / "rendered_partial").is_dir())
        summary = finalizer._render_text_summary(result)
        self.assertIn("source_snapshot=CHANGED count=1", summary)
        self.assertIn("unit_statuses_do_not_establish_current_source_coverage=true", summary)
        with (run_dir / "rendered_manifest.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            manifest = list(csv.DictReader(handle))
        self.assertTrue(manifest)
        row = manifest[0]
        self.assertEqual("LIVE_LOCATION_LABEL_NOT_HASH_TARGET", row["source_path_scope"])
        self.assertEqual("RENDERED_CANDIDATE_BYTES", row["sha256_scope"])
        self.assertEqual(row["sha256"], row["rendered_sha256"])
        self.assertRegex(row["source_snapshot_copy"], r"^source[/\\]F\d+")
        self.assertRegex(row["source_snapshot_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(
            row["source_snapshot_sha256"],
            finalizer.sha256(source.read_bytes()),
        )

    def test_source_deleted_after_snapshot_blocks_full_completion(self) -> None:
        source, run_dir, unit = self.prepare("\\section{背景}\n本段保持原有自然表达。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        source.unlink()

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(1, result["source_files_changed_since_snapshot"])
        self.assertEqual("MISSING", result["source_change_details"][0]["current_state"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_source_replaced_by_directory_blocks_full_completion(self) -> None:
        source, run_dir, unit = self.prepare("\\section{背景}\n本段保持原有自然表达。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        source.unlink()
        source.mkdir()

        result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(1, result["source_files_changed_since_snapshot"])
        self.assertEqual("NOT_FILE", result["source_change_details"][0]["current_state"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_copying_read_only_adjacent_context_is_rejected(self) -> None:
        source = self.root / "main.md"
        source.write_text(
            "# 甲节\n甲段文字保持简洁。\n\n# 乙节\n乙段文字保持简洁。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="GENERAL", min_author_chars=0)
        chunks = sorted(
            (json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "chunks").glob("*.json")),
            key=lambda item: item["start"],
        )
        first, second = chunks
        rewrites = self.rewrite_dir()
        (rewrites / f"{first['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    first,
                    {
                        "decision": "REWRITE",
                        "masked_text": first["masked_text"] + "\n乙段文字保持简洁。\n",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (rewrites / f"{second['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    second,
                    {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == first["unit_id"])
        published = Path(result["published_path"])
        rendered = next(published.rglob("*.md")).read_text(encoding="utf-8")

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("read_only_context_copied", row["notes"])
        self.assertEqual(1, rendered.count("乙段文字保持简洁。"))

    def test_raw_copy_of_protected_content_is_rejected(self) -> None:
        _, run_dir, unit = self.prepare("\\section{背景}\n本段讨论对象范围。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"] + "\n\\section{背景}\n",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)
        row = next(item for item in self.final_ledger(run_dir) if item["unit_id"] == unit["unit_id"])

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("protected_content_count_changed", row["notes"])

    def test_non_cumulative_partial_run_preserves_previous_partial(self) -> None:
        source = self.root / "main.md"
        source.write_text(
            "# 甲节\n值得注意的是，甲段文字自然。\n\n# 乙节\n乙段文字自然。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="GENERAL", min_author_chars=0)
        chunks = sorted(
            (json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "chunks").glob("*.json")),
            key=lambda item: item["start"],
        )
        first, second = chunks
        first_rewrites = self.rewrite_dir()
        (first_rewrites / f"{first['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    first,
                    {
                        "decision": "REWRITE",
                        "masked_text": first["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first_result = finalizer.finalize(run_dir, first_rewrites)
        partial_path = next((run_dir / "rendered_partial").rglob("*.md"))
        partial_before = partial_path.read_bytes()
        evidence_before = self.evidence_snapshot(run_dir)

        second_rewrites = self.root / "rewrites-second"
        second_rewrites.mkdir()
        (second_rewrites / f"{second['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    second,
                    {"decision": "NO_CHANGE", "reason": "该段保持原有自然表达"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        second_result = finalizer.finalize(run_dir, second_rewrites)

        self.assertEqual("REVIEW", first_result["status"])
        self.assertEqual("FAIL", second_result["status"])
        self.assertEqual("FAIL", second_result["idempotency"])
        self.assertIn(first["unit_id"], second_result["partial_regression_units"])
        self.assertEqual(partial_before, partial_path.read_bytes())
        self.assertEqual(evidence_before, self.evidence_snapshot(run_dir))

    def test_invalid_revised_bundle_cannot_regress_previous_partial(self) -> None:
        source = self.root / "main.md"
        source.write_text(
            "# 甲节\n值得注意的是，甲段文字自然。\n\n# 乙节\n乙段文字自然。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="GENERAL", min_author_chars=0)
        first = min(
            (json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "chunks").glob("*.json")),
            key=lambda item: item["start"],
        )
        rewrites = self.rewrite_dir()
        bundle = rewrites / f"{first['unit_id']}.json"
        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    first,
                    {
                        "decision": "REWRITE",
                        "masked_text": first["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first_result = finalizer.finalize(run_dir, rewrites)
        partial_path = next((run_dir / "rendered_partial").rglob("*.md"))
        partial_before = partial_path.read_bytes()
        evidence_before = self.evidence_snapshot(run_dir)

        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    first,
                    {"decision": "REWRITE", "masked_text": first["masked_text"]},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        second_result = finalizer.finalize(run_dir, rewrites)

        self.assertEqual("REVIEW", first_result["status"])
        self.assertEqual("FAIL", second_result["status"])
        self.assertIn(first["unit_id"], second_result["partial_regression_units"])
        self.assertEqual(partial_before, partial_path.read_bytes())
        self.assertEqual(evidence_before, self.evidence_snapshot(run_dir))

    def test_revised_review_candidate_replaces_prior_candidate_with_history(self) -> None:
        source = self.root / "main.md"
        source.write_text("# 标题\n值得注意的是，该段文字自然。\n", encoding="utf-8")
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="GENERAL", min_author_chars=0)
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        rewrites = self.rewrite_dir()
        bundle = rewrites / f"{unit['unit_id']}.json"
        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first_result = finalizer.finalize(run_dir, rewrites)
        rendered_path = next((run_dir / "rendered_review").rglob("*.md"))
        rendered_before = rendered_path.read_bytes()
        evidence_before = self.evidence_snapshot(run_dir)

        bundle.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace(
                            "值得注意的是，该段文字自然。",
                            "这段文字保持自然。",
                        ),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        second_result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(first_result)
        self.assert_paired_quality_review_candidate(second_result)
        self.assertEqual("NOT_APPLICABLE_PROGRESS", second_result["idempotency"])
        self.assertNotEqual(rendered_before, rendered_path.read_bytes())
        self.assertNotEqual(evidence_before, self.evidence_snapshot(run_dir))
        history = [
            json.loads(line)
            for line in (run_dir / "partial_history.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual("revised_review_candidate", history[-1]["reason"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_compile_command_cannot_modify_source_without_hard_failure(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = (
            f'"{sys.executable}" -c '
            f'"from pathlib import Path; p=Path(r\'{source}\'); p.write_text(p.read_text(encoding=\'utf-8\')+\'% changed\\n\', encoding=\'utf-8\')"'
        )
        result = finalizer.finalize(run_dir, rewrites, check_command=command)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(result["source_changed_during_compile_or_finalize"])
        self.assertEqual(1, result["source_files_modified"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_check_command_cannot_modify_real_staging_tree(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        source_span = self.masked_line_span(
            unit["masked_text"], "值得注意的是"
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.v3_rewrite_bundle(
                    run_dir,
                    unit,
                    masked_text=unit["masked_text"].replace(
                        "值得注意的是，", ""
                    ),
                    source_span=source_span,
                    summary="删除失去强调作用的程式化提示语",
                    target_signal="LEX-EMPH-01",
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'p=Path(r\'{run_dir / ".rendered_staging" / "main.tex"}\'); '
            f'p.write_text(\'MALICIOUS\\n\', encoding=\'utf-8\')"'
        )

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", result["status"])
        self.assert_compile_check_schema(result["compile_check"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertTrue(result["staging_artifacts_changed_during_check"])
        self.assertFalse(result["run_artifacts_changed_during_check"])
        self.assertEqual("FAIL", result["compile_check"]["integrity_status"])
        self.assertIn("staging", result["compile_check"]["integrity_changes"])
        self.assertEqual(0, result["source_files_modified"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_check_command_cannot_modify_run_snapshot(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'p=next(Path(r\'{run_dir / "source"}\').rglob(\'*.tex\')); '
            f'p.write_text(\'MUTATED\\n\', encoding=\'utf-8\')"'
        )

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", result["status"])
        self.assert_compile_check_schema(result["compile_check"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertTrue(result["run_artifacts_changed_during_check"])
        self.assertFalse(result["staging_artifacts_changed_during_check"])
        self.assertEqual("FAIL", result["compile_check"]["integrity_status"])
        self.assertIn("run_dir", result["compile_check"]["integrity_changes"])
        self.assertEqual(0, result["source_files_modified"])
        self.assertFalse(result["source_changed_during_compile_or_finalize"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_check_command_cannot_poison_validation_evidence(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        validation_path = run_dir / ".validation_staging" / f"{unit['unit_id']}.validation.json"
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'p=Path(r\'{validation_path}\'); p.write_text(\'{{}}\', encoding=\'utf-8\')"'
        )

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertTrue(result["evidence_artifacts_changed_during_check"])
        self.assertEqual("FAIL", result["compile_check"]["integrity_status"])
        self.assertIn("evidence_staging", result["compile_check"]["integrity_changes"])
        self.assertTrue(result["staged_evidence_discarded"])
        self.assertFalse(result["published_evidence_preserved"])
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / "validation").exists())

    def test_check_command_cannot_poison_diff_evidence(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        diff_path = run_dir / ".diffs_staging" / f"{unit['unit_id']}.diff"
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'p=Path(r\'{diff_path}\'); p.write_text(\'FORGED\', encoding=\'utf-8\')"'
        )

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", result["status"])
        self.assertTrue(result["evidence_artifacts_changed_during_check"])
        self.assertIn("evidence_staging", result["compile_check"]["integrity_changes"])
        self.assertTrue(result["staged_evidence_discarded"])
        self.assertFalse((run_dir / "diffs").exists())

    def test_poisoned_rerun_preserves_previously_published_evidence(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace("值得注意的是，", ""),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first = finalizer.finalize(run_dir, rewrites)
        evidence_before = self.evidence_snapshot(run_dir)
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        validation_path = run_dir / ".validation_staging" / f"{unit['unit_id']}.validation.json"
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'p=Path(r\'{validation_path}\'); p.write_text(\'{{}}\', encoding=\'utf-8\')"'
        )

        second = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assert_paired_quality_review_candidate(first)
        self.assertEqual("FAIL", second["status"])
        self.assertTrue(second["published_evidence_preserved"])
        self.assertTrue(second["staged_evidence_discarded"])
        self.assertEqual(evidence_before, self.evidence_snapshot(run_dir))
        self.assertEqual(
            rendered_before, _directory_bytes(run_dir / "rendered_review")
        )

    def test_failed_rerun_keeps_previous_metadata_and_detaches_new_evidence(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n值得注意的是，该段文字自然。\n"
        )
        rewrites = self.rewrite_dir()
        path = rewrites / f"{unit['unit_id']}.json"
        path.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace(
                            "值得注意的是，", ""
                        ),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first = finalizer.finalize(run_dir, rewrites)
        old_metadata = (run_dir / "finalization_metadata.json").read_bytes()
        old_evidence = self.evidence_snapshot(run_dir)
        old_request_sha = first["paired_quality_review_requests"][
            unit["unit_id"]
        ]["request_sha256"]

        path.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace(
                            "值得注意的是，该段文字自然。",
                            "该段文字保持自然。",
                        ),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = f'"{sys.executable}" -c "raise SystemExit(9)"'
        second = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", second["status"])
        self.assertTrue(second["run_state_restored_after_failure"])
        self.assertTrue(second["finalization_metadata_preserved"])
        self.assertTrue(second["published_evidence_preserved"])
        self.assertEqual(
            "NOT_RETAINED_AFTER_ROLLBACK",
            second["failed_attempt_evidence_status"],
        )
        new_request = second["paired_quality_review_requests"][unit["unit_id"]]
        self.assertNotEqual(old_request_sha, new_request["request_sha256"])
        self.assertEqual("", new_request["path"])
        self.assertEqual("", new_request["rewrite_intent_evidence_path"])
        self.assertFalse(second["failed_attempt_evidence_paths_reusable"])
        self.assertTrue(second["failed_attempt_sensitive_fields_redacted"])
        self.assertEqual("", second["compile_check"]["command"])
        self.assertEqual("", second["compile_check"]["cwd"])
        self.assertEqual("", second["compile_check"]["stdout"])
        self.assertEqual("", second["compile_check"]["stderr"])
        unresolved = second["unresolved_reason_summary"]
        self.assertEqual("", unresolved["details_artifact"])
        self.assertEqual(
            "NOT_RETAINED_AFTER_ROLLBACK",
            unresolved["details_artifact_status"],
        )
        for change in second["source_change_details"]:
            self.assertEqual("", change["path"])
        serialized = json.dumps(second, ensure_ascii=False)
        self.assertNotIn(str(self.root.resolve()), serialized)
        self.assertNotIn(sys.executable, serialized)
        self.assertEqual(
            old_metadata, (run_dir / "finalization_metadata.json").read_bytes()
        )
        self.assertEqual(old_evidence, self.evidence_snapshot(run_dir))
        self.assertEqual(
            second,
            json.loads(
                (run_dir / "last_failed_attempt_metadata.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertEqual(
            second,
            json.loads(
                (run_dir / "latest_attempt_metadata.json").read_text(
                    encoding="utf-8"
                )
            ),
        )

    def test_absolute_check_pollution_restores_previous_review_candidate(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n值得注意的是，该段文字自然。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace(
                            "值得注意的是，", ""
                        ),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        first = finalizer.finalize(run_dir, rewrites)
        self.assert_paired_quality_review_candidate(first)
        rendered_before = _directory_bytes(run_dir / "rendered_review")
        metadata_before = (run_dir / "finalization_metadata.json").read_bytes()
        rendered_path = next((run_dir / "rendered_review").rglob("*.tex"))
        command = (
            f'"{sys.executable}" -c "from pathlib import Path; '
            f'Path(r\'{rendered_path}\').write_text(\'MALICIOUS\\n\', encoding=\'utf-8\')"'
        )

        second = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assertEqual("FAIL", second["status"])
        self.assertTrue(second["run_artifacts_changed_during_check"])
        self.assertTrue(second["run_state_restored_after_failure"])
        self.assertTrue(second["published_evidence_preserved"])
        self.assertEqual(
            rendered_before, _directory_bytes(run_dir / "rendered_review")
        )
        self.assertEqual(
            metadata_before, (run_dir / "finalization_metadata.json").read_bytes()
        )

    def test_publish_and_evidence_commit_failures_restore_exact_run_state(self) -> None:
        outer_root = self.root
        for replacement in (False, True):
            for failed_commit in (0, 1):
                with self.subTest(
                    replacement=replacement, failed_commit=failed_commit
                ):
                    case_root = outer_root / f"case-{int(replacement)}-{failed_commit}"
                    case_root.mkdir()
                    self.root = case_root
                    try:
                        _, run_dir, unit = self.prepare(
                            "\\section{定义}\n值得注意的是，该段文字自然。\n"
                        )
                        rewrites = self.rewrite_dir()
                        path = rewrites / f"{unit['unit_id']}.json"
                        first_masked = unit["masked_text"].replace(
                            "值得注意的是，", ""
                        )
                        path.write_text(
                            json.dumps(
                                self.voice_bound_bundle(
                                    unit,
                                    {
                                        "decision": "REWRITE",
                                        "masked_text": first_masked,
                                    },
                                ),
                                ensure_ascii=False,
                            ),
                            encoding="utf-8",
                        )
                        if replacement:
                            finalizer.finalize(run_dir, rewrites)
                            path.write_text(
                                json.dumps(
                                    self.voice_bound_bundle(
                                        unit,
                                        {
                                            "decision": "REWRITE",
                                            "masked_text": unit["masked_text"].replace(
                                                "值得注意的是，该段文字自然。",
                                                "该段文字保持自然。",
                                            ),
                                        },
                                    ),
                                    ensure_ascii=False,
                                ),
                                encoding="utf-8",
                            )
                        state_before = finalizer._run_state_hashes(run_dir)
                        state_before.pop("latest_attempt_metadata.json", None)
                        error = OSError(f"evidence commit {failed_commit} failed")
                        side_effect = (
                            [error] if failed_commit == 0 else [None, error]
                        )
                        with mock.patch.object(
                            finalizer,
                            "_commit_evidence_directory",
                            side_effect=side_effect,
                        ):
                            with self.assertRaisesRegex(
                                OSError, f"evidence commit {failed_commit} failed"
                            ):
                                finalizer.finalize(run_dir, rewrites)
                        state_after = finalizer._run_state_hashes(run_dir)
                        state_after.pop("last_failed_attempt_metadata.json", None)
                        state_after.pop("latest_attempt_metadata.json", None)
                        self.assertEqual(state_before, state_after)
                        failure = json.loads(
                            (run_dir / "last_failed_attempt_metadata.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        self.assertEqual("FAIL", failure["status"])
                        self.assertEqual(1, failure["exit_code"])
                        self.assertTrue(failure["failed_attempt"])
                        self.assertEqual(
                            "last_failed_attempt_metadata.json",
                            failure["failed_attempt_metadata_path"],
                        )
                        self.assertEqual(
                            "NOT_RETAINED_AFTER_ROLLBACK",
                            failure["failed_attempt_evidence_status"],
                        )
                        self.assertFalse(
                            failure["failed_attempt_evidence_paths_reusable"]
                        )
                        self.assertTrue(
                            failure["run_state_restored_after_failure"]
                        )
                        self.assertEqual(
                            replacement,
                            failure["finalization_metadata_preserved"],
                        )
                    finally:
                        self.root = outer_root

    def test_transaction_backup_rejects_hard_link_artifact(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.link(run_dir / "snapshot.json", run_dir / "snapshot-hardlink.json")

        with self.assertRaisesRegex(ValueError, "hard link is not supported"):
            finalizer.finalize(run_dir, rewrites)

        self.assertFalse((run_dir / "rendered_review").exists())
        self.assertFalse((run_dir / "validation").exists())
        self.assertFalse((run_dir / "finalization_metadata.json").exists())

    def test_runtime_error_is_structured_fail_one_not_review_two(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(
            finalizer, "finalize", side_effect=OSError("publication failed")
        ), mock.patch.object(sys, "stdout", stdout), mock.patch.object(
            sys, "stderr", stderr
        ):
            exit_code = finalizer.main(
                ["--run-dir", str(self.root / "run"), "--rewrites", str(self.root)]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual(1, payload["exit_code"])
        self.assertEqual("FAIL", payload["delivery_gate_status"])
        self.assertEqual("FAILED", payload["publish_state"])
        self.assertTrue(payload["runtime_error"])
        self.assertTrue(payload["failed_attempt"])
        self.assertFalse(payload["failed_attempt_evidence_paths_reusable"])
        self.assertEqual("OSError", payload["error_type"])
        self.assertEqual("OS_ERROR", payload["error_code"])
        self.assertTrue(payload["error_message_redacted"])
        self.assertTrue(payload["paths_redacted"])
        self.assertNotIn("error", payload)
        self.assertNotIn("run_dir", payload)
        self.assertNotIn("publication failed", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def make_authority_crash_fixture(
        self, parent: Path, *, transaction_id: str = "1" * 24
    ) -> tuple[Path, Path, bytes, bytes, bytes, bytes, Path, dict[str, object]]:
        first = parent / "finalization_metadata.json"
        second = parent / "latest_attempt_metadata.json"
        old_first = b"FIRST-OLD\n"
        old_second = old_first
        new_first = b"FIRST-NEW\n"
        new_second = new_first
        old_members = {
            "finalization_metadata.json": old_first,
            "last_failed_attempt_metadata.json": None,
            "latest_attempt_metadata.json": old_second,
        }
        new_members = {
            "finalization_metadata.json": new_first,
            "last_failed_attempt_metadata.json": None,
            "latest_attempt_metadata.json": new_second,
        }
        base_commit = finalizer._authority_commit_payload(
            generation=0,
            transaction_id="BOOTSTRAP",
            role="LEGACY_BASELINE",
            members=old_members,
        )
        base_commit_raw = finalizer._canonical_json_bytes(base_commit)
        (parent / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(base_commit_raw)
        next_commit = finalizer._authority_commit_payload(
            generation=1,
            transaction_id=transaction_id,
            role="SUCCESS",
            members=new_members,
        )
        next_commit_raw = finalizer._canonical_json_bytes(next_commit)
        transaction_dir = parent / (
            finalizer.AUTHORITY_GROUP_TRANSACTION_PREFIX + transaction_id
        )
        transaction_dir.mkdir()
        journal_members: list[dict[str, object]] = []
        for index, target_name in enumerate(finalizer.AUTHORITY_GROUP_TARGET_NAMES):
            old_raw = old_members[target_name]
            new_raw = new_members[target_name]
            backup_name = f"member-{index}.old"
            staging_name = f"member-{index}.new"
            if old_raw is not None:
                (transaction_dir / backup_name).write_bytes(old_raw)
            if new_raw is not None:
                (transaction_dir / staging_name).write_bytes(new_raw)
            journal_members.append(
                {
                    "target": target_name,
                    "old_exists": old_raw is not None,
                    "old_sha256": finalizer.sha256(old_raw) if old_raw is not None else None,
                    "old_bytes": len(old_raw) if old_raw is not None else 0,
                    "new_exists": new_raw is not None,
                    "new_sha256": finalizer.sha256(new_raw) if new_raw is not None else None,
                    "new_bytes": len(new_raw) if new_raw is not None else 0,
                    "backup": backup_name,
                    "staging": staging_name,
                }
            )
        (transaction_dir / "commit.new").write_bytes(next_commit_raw)
        journal: dict[str, object] = {
            "schema_version": finalizer.AUTHORITY_GROUP_JOURNAL_SCHEMA,
            "transaction_id": transaction_id,
            "state": "PREPARED",
            "role": "SUCCESS",
            "base_generation": 0,
            "next_generation": 1,
            "base_commit_sha256": finalizer.sha256(base_commit_raw),
            "next_commit_sha256": finalizer.sha256(next_commit_raw),
            "members": journal_members,
        }
        finalizer._write_json(
            parent / finalizer.AUTHORITY_GROUP_JOURNAL_NAME, journal
        )
        return (
            first,
            second,
            old_first,
            old_second,
            new_first,
            new_second,
            transaction_dir,
            journal,
        )

    def test_metadata_authority_group_restores_every_prior_byte_on_second_write_failure(self) -> None:
        first = self.root / "finalization_metadata.json"
        second = self.root / "latest_attempt_metadata.json"
        first.write_bytes(b"PAIR-OLD\n")
        second.write_bytes(b"PAIR-OLD\n")
        real_replace = finalizer.os.replace
        committed = 0

        def fail_second(source: object, target: object) -> None:
            nonlocal committed
            target_path = Path(target)
            if target_path in {first, second}:
                committed += 1
                if committed == 2:
                    raise OSError("SECOND-WRITE-FAILED SECRET-CONTENT")
            real_replace(source, target)

        with mock.patch.object(finalizer.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                finalizer._write_json_group_atomic(
                    ((first, {"new": 1}), (second, {"new": 1}))
                )

        self.assertEqual(b"PAIR-OLD\n", first.read_bytes())
        self.assertEqual(b"PAIR-OLD\n", second.read_bytes())

    def test_metadata_authority_group_reports_rollback_failure(self) -> None:
        first = self.root / "finalization_metadata.json"
        second = self.root / "latest_attempt_metadata.json"
        first.write_bytes(b"PAIR-OLD\n")
        second.write_bytes(b"PAIR-OLD\n")
        real_replace = finalizer.os.replace
        target_replaces = 0

        def fail_publication_and_restore(source: object, target: object) -> None:
            nonlocal target_replaces
            target_path = Path(target)
            if target_path in {first, second}:
                target_replaces += 1
                if target_replaces >= 2:
                    raise OSError("REPLACE-FAILED")
            real_replace(source, target)

        with mock.patch.object(
            finalizer.os, "replace", side_effect=fail_publication_and_restore
        ):
            with self.assertRaisesRegex(
                RuntimeError, "metadata authority group rollback failed"
            ):
                finalizer._write_json_group_atomic(
                    ((first, {"new": 1}), (second, {"new": 1}))
                )

    def test_authority_group_journal_recovers_mixed_crash_state(self) -> None:
        (
            first,
            second,
            old_first,
            old_second,
            new_first,
            _new_second,
            transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(self.root)
        first.write_bytes(new_first)
        second.write_bytes(old_second)

        self.assertTrue(finalizer._recover_authority_group_journal(self.root))

        self.assertEqual(old_first, first.read_bytes())
        self.assertEqual(old_second, second.read_bytes())
        self.assertFalse(
            (self.root / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).exists()
        )
        self.assertFalse(transaction_dir.exists())

    def test_authority_group_committed_dirty_state_rolls_forward(self) -> None:
        (
            first,
            second,
            _old_first,
            old_second,
            new_first,
            new_second,
            transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(self.root)
        first.write_bytes(new_first)
        second.write_bytes(old_second)
        (self.root / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(
            (transaction_dir / "commit.new").read_bytes()
        )

        self.assertTrue(finalizer._recover_authority_group_journal(self.root))

        self.assertEqual(new_first, first.read_bytes())
        self.assertEqual(new_second, second.read_bytes())
        self.assertFalse(
            (self.root / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).exists()
        )
        self.assertFalse(transaction_dir.exists())
        self.assertFalse(finalizer._recover_authority_group_journal(self.root))

    def test_authority_group_recovery_rejects_third_commit_without_mutation(self) -> None:
        (
            first,
            second,
            _old_first,
            old_second,
            new_first,
            _new_second,
            _transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(self.root)
        first.write_bytes(new_first)
        second.write_bytes(old_second)
        third_commit = finalizer._authority_commit_payload(
            generation=99,
            transaction_id="f" * 24,
            role="SUCCESS",
            members={
                "finalization_metadata.json": new_first,
                "last_failed_attempt_metadata.json": None,
                "latest_attempt_metadata.json": new_first,
            },
        )
        (self.root / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(
            finalizer._canonical_json_bytes(third_commit)
        )

        with self.assertRaisesRegex(RuntimeError, "outside journal state"):
            finalizer._recover_authority_group_journal(self.root)

        self.assertEqual(new_first, first.read_bytes())
        self.assertEqual(old_second, second.read_bytes())

    def test_authority_staging_residue_is_removed_before_clean_validation(self) -> None:
        residue = self.root / (
            finalizer.AUTHORITY_GROUP_COMMIT_STAGING_PREFIX + "dead.staging"
        )
        residue.write_bytes(b"INCOMPLETE")

        self.assertFalse(finalizer._recover_authority_group_journal(self.root))

        self.assertFalse(residue.exists())
        self.assertTrue(
            (self.root / finalizer.AUTHORITY_GROUP_COMMIT_NAME).is_file()
        )

    def test_authority_target_staging_residue_is_removed_before_bootstrap(self) -> None:
        residue = self.root / (
            finalizer.AUTHORITY_GROUP_TARGET_STAGING_PREFIX + "dead.staging"
        )
        residue.write_bytes(b"INCOMPLETE")

        self.assertFalse(finalizer._recover_authority_group_journal(self.root))

        self.assertFalse(residue.exists())

    def test_prejournal_transaction_staging_residue_is_safely_discarded(self) -> None:
        transaction = self.root / (
            finalizer.AUTHORITY_GROUP_TRANSACTION_PREFIX + "d" * 24
        )
        transaction.mkdir()
        residue = transaction / (
            finalizer.AUTHORITY_GROUP_TRANSACTION_STAGING_PREFIX + "dead.staging"
        )
        residue.write_bytes(b"INCOMPLETE")

        self.assertFalse(finalizer._recover_authority_group_journal(self.root))

        self.assertFalse(transaction.exists())

    def test_authority_writer_rejects_nonidentical_active_pair(self) -> None:
        with self.assertRaisesRegex(ValueError, "byte-identical"):
            finalizer._write_json_group_atomic(
                (
                    (self.root / "finalization_metadata.json", {"value": 1}),
                    (self.root / "latest_attempt_metadata.json", {"value": 2}),
                )
            )

    def test_bootstrap_rejects_partial_authority_closure(self) -> None:
        (self.root / "latest_attempt_metadata.json").write_text(
            "{}\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(RuntimeError, "partial authority closure"):
            finalizer._recover_authority_group_journal(self.root)

    def test_recovery_rejects_missing_target_when_old_and_new_both_exist(self) -> None:
        (
            first,
            second,
            _old_first,
            old_second,
            _new_first,
            _new_second,
            _transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(self.root)
        second.write_bytes(old_second)

        with self.assertRaisesRegex(ValueError, "missing target"):
            finalizer._recover_authority_group_journal(self.root)

        self.assertFalse(first.exists())

    def test_run_state_restore_never_touches_authority_closure(self) -> None:
        run_dir = self.root / "run"
        run_dir.mkdir()
        backup = self.root / "backup"
        backup.mkdir()
        ordinary = run_dir / "ordinary.txt"
        ordinary.write_text("new", encoding="utf-8")
        (backup / "ordinary.txt").write_text("old", encoding="utf-8")
        authority_paths = [
            run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME,
            *(run_dir / name for name in finalizer.AUTHORITY_GROUP_TARGET_NAMES),
        ]
        for index, path in enumerate(authority_paths):
            path.write_bytes(f"authority-{index}".encode("ascii"))
        before = {path: path.read_bytes() for path in authority_paths}

        finalizer._restore_run_state(run_dir, backup)

        self.assertEqual("old", ordinary.read_text(encoding="utf-8"))
        self.assertEqual(before, {path: path.read_bytes() for path in authority_paths})

    def make_run_state_recovery_fixture(self) -> tuple[Path, str, Path]:
        run_dir = self.root / "durable-run"
        run_dir.mkdir()
        ordinary = run_dir / "ordinary.txt"
        ordinary.write_text("base", encoding="utf-8")
        finalizer._recover_authority_group_journal(run_dir)
        transaction_id, backup_dir = finalizer._begin_run_state_transaction(run_dir)
        return run_dir, transaction_id, backup_dir

    def make_bound_run_state_recovery_fixture(
        self, name: str, *, pointer: str
    ) -> tuple[Path, str, dict, bytes, dict]:
        run_dir = self.root / name
        run_dir.mkdir()
        (run_dir / "ordinary.txt").write_text("base", encoding="utf-8")
        finalizer._recover_authority_group_journal(run_dir)
        transaction_id, _backup_dir = finalizer._begin_run_state_transaction(run_dir)
        base_raw = (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).read_bytes()
        base_commit = finalizer._parse_authority_commit(base_raw)
        next_commit = finalizer._authority_commit_payload(
            generation=base_commit["generation"] + 1,
            transaction_id=transaction_id,
            role="LEGACY_BASELINE",
            members=finalizer._authority_closure_bytes(run_dir),
        )
        next_raw = finalizer._canonical_json_bytes(next_commit)
        (run_dir / "ordinary.txt").write_text("next", encoding="utf-8")
        finalizer._bind_run_state_next(
            run_dir, transaction_id, next_raw, next_commit
        )
        if pointer == "next":
            (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(next_raw)
        elif pointer != "base":
            raise ValueError("pointer must be base or next")
        return run_dir, transaction_id, base_commit, next_raw, next_commit

    def test_run_state_next_pointer_repairs_third_live_closure_from_sealed_image(self) -> None:
        run_dir, transaction_id, _base, _next_raw, _next = (
            self.make_bound_run_state_recovery_fixture(
                "next-live-tamper", pointer="next"
            )
        )
        (run_dir / "ordinary.txt").write_text(
            "tampered-third-state", encoding="utf-8"
        )
        self.assertTrue(finalizer._recover_run_state_journal(run_dir))

        self.assertEqual(
            "next", (run_dir / "ordinary.txt").read_text(encoding="utf-8")
        )
        self.assertFalse((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).exists())
        self.assertFalse(
            finalizer._run_state_transaction_path(run_dir, transaction_id).exists()
        )

    def test_run_state_cleanup_revalidates_selected_closure_before_deleting_evidence(self) -> None:
        run_dir, transaction_id, _base, _next_raw, _next = (
            self.make_bound_run_state_recovery_fixture(
                "cleanup-image-tamper", pointer="next"
            )
        )
        journal_path = run_dir / finalizer.RUN_STATE_JOURNAL_NAME
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["state"] = "CLEANUP"
        journal_path.write_bytes(finalizer._canonical_json_bytes(journal))
        next_file = (
            finalizer._run_state_transaction_path(run_dir, transaction_id)
            / "next"
            / "ordinary.txt"
        )
        next_file.write_text("tampered-image", encoding="utf-8")
        before = _directory_bytes(run_dir)

        with self.assertRaisesRegex(RuntimeError, "image does not match journal closure"):
            finalizer._recover_run_state_journal(run_dir)

        self.assertEqual(before, _directory_bytes(run_dir))
        self.assertTrue(journal_path.is_file())
        self.assertTrue(
            finalizer._run_state_transaction_path(run_dir, transaction_id).is_dir()
        )

    def test_run_state_cleanup_restart_finishes_when_transaction_delete_is_interrupted(self) -> None:
        run_dir, transaction_id, _base, _next_raw, _next = (
            self.make_bound_run_state_recovery_fixture(
                "cleanup-delete-interrupted", pointer="next"
            )
        )
        transaction_dir = finalizer._run_state_transaction_path(
            run_dir, transaction_id
        )
        real_rmtree = finalizer.shutil.rmtree

        def interrupt_transaction_delete(path: object, *args: object, **kwargs: object) -> None:
            if Path(path) == transaction_dir:
                raise KeyboardInterrupt
            real_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            finalizer.shutil, "rmtree", side_effect=interrupt_transaction_delete
        ):
            with self.assertRaises(KeyboardInterrupt):
                finalizer._cleanup_run_state_transaction(run_dir, transaction_id)

        self.assertFalse((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).exists())
        self.assertTrue(transaction_dir.is_dir())
        self.assertTrue(
            (run_dir / (finalizer.RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json")).is_file()
        )
        self.assertTrue(finalizer._recover_run_state_journal(run_dir))
        self.assertFalse(transaction_dir.exists())
        self.assertFalse(
            (run_dir / (finalizer.RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json")).exists()
        )
        self.assertEqual(
            "next", (run_dir / "ordinary.txt").read_text(encoding="utf-8")
        )

    def test_run_state_cleanup_restart_finishes_after_transaction_was_deleted(self) -> None:
        run_dir, transaction_id, _base, _next_raw, _next = (
            self.make_bound_run_state_recovery_fixture(
                "cleanup-delete-then-interrupt", pointer="next"
            )
        )
        transaction_dir = finalizer._run_state_transaction_path(
            run_dir, transaction_id
        )
        real_rmtree = finalizer.shutil.rmtree

        def delete_then_interrupt(path: object, *args: object, **kwargs: object) -> None:
            real_rmtree(path, *args, **kwargs)
            if Path(path) == transaction_dir:
                raise KeyboardInterrupt

        with mock.patch.object(
            finalizer.shutil, "rmtree", side_effect=delete_then_interrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                finalizer._cleanup_run_state_transaction(run_dir, transaction_id)

        self.assertFalse((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).exists())
        self.assertFalse(transaction_dir.exists())
        self.assertTrue(finalizer._recover_run_state_journal(run_dir))
        self.assertFalse(
            (run_dir / (finalizer.RUN_STATE_CLEANUP_PREFIX + transaction_id + ".json")).exists()
        )

    def test_run_state_selected_base_or_next_image_tampering_fails_closed(self) -> None:
        cases = (
            ("base-hash", "base", "hash"),
            ("base-type", "base", "type"),
            ("next-hash", "next", "hash"),
            ("next-type", "next", "type"),
        )
        for name, side, mutation in cases:
            with self.subTest(side=side, mutation=mutation):
                run_dir, transaction_id, _base, _next_raw, _next = (
                    self.make_bound_run_state_recovery_fixture(
                        f"selected-image-{name}", pointer=side
                    )
                )
                selected_file = (
                    finalizer._run_state_transaction_path(run_dir, transaction_id)
                    / side
                    / "ordinary.txt"
                )
                if mutation == "hash":
                    selected_file.write_text("wrong-image-bytes", encoding="utf-8")
                else:
                    selected_file.unlink()
                    selected_file.mkdir()
                before = _directory_bytes(run_dir)

                with self.assertRaisesRegex(
                    RuntimeError, "image does not match journal closure"
                ):
                    finalizer._recover_run_state_journal(run_dir)

                self.assertEqual(before, _directory_bytes(run_dir))
                self.assertTrue(
                    (run_dir / finalizer.RUN_STATE_JOURNAL_NAME).is_file()
                )
                self.assertTrue(
                    finalizer._run_state_transaction_path(
                        run_dir, transaction_id
                    ).is_dir()
                )

    def test_run_state_bound_journal_rejects_third_pointer_without_live_mutation(self) -> None:
        run_dir, transaction_id, _base, _next_raw, next_commit = (
            self.make_bound_run_state_recovery_fixture(
                "bound-third-pointer", pointer="next"
            )
        )
        third_commit = finalizer._authority_commit_payload(
            generation=next_commit["generation"] + 1,
            transaction_id="e" * 24,
            role="LEGACY_BASELINE",
            members=finalizer._authority_closure_bytes(run_dir),
        )
        (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(
            finalizer._canonical_json_bytes(third_commit)
        )
        before = _directory_bytes(run_dir)

        with self.assertRaisesRegex(RuntimeError, "outside run-state journal"):
            finalizer._recover_run_state_journal(run_dir)

        self.assertEqual(before, _directory_bytes(run_dir))
        self.assertTrue((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).is_file())
        self.assertTrue(
            finalizer._run_state_transaction_path(run_dir, transaction_id).is_dir()
        )

    def test_run_state_journal_restarts_base_restore_after_interruption(self) -> None:
        run_dir, transaction_id, _backup_dir = self.make_run_state_recovery_fixture()
        ordinary = run_dir / "ordinary.txt"
        ordinary.write_text("new", encoding="utf-8")
        (run_dir / "added.txt").write_text("partial", encoding="utf-8")
        real_copy2 = finalizer.shutil.copy2
        interrupted = False

        def interrupt_first_copy(source: object, target: object, *args: object, **kwargs: object) -> object:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            return real_copy2(source, target, *args, **kwargs)

        with mock.patch.object(finalizer.shutil, "copy2", side_effect=interrupt_first_copy):
            with self.assertRaises(KeyboardInterrupt):
                finalizer._recover_run_state_journal(run_dir)

        self.assertTrue((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).is_file())
        self.assertTrue(
            finalizer._run_state_transaction_path(run_dir, transaction_id).is_dir()
        )
        self.assertTrue(finalizer._recover_run_state_journal(run_dir))
        self.assertEqual("base", ordinary.read_text(encoding="utf-8"))
        self.assertFalse((run_dir / "added.txt").exists())
        self.assertFalse((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).exists())

    def test_run_state_journal_keeps_next_state_after_matching_authority_commit(self) -> None:
        run_dir, transaction_id, _backup_dir = self.make_run_state_recovery_fixture()
        ordinary = run_dir / "ordinary.txt"
        ordinary.write_text("next", encoding="utf-8")
        base_raw = (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).read_bytes()
        base = finalizer._parse_authority_commit(base_raw)
        closure = finalizer._authority_closure_bytes(run_dir)
        next_commit = finalizer._authority_commit_payload(
            generation=base["generation"] + 1,
            transaction_id=transaction_id,
            role="LEGACY_BASELINE",
            members=closure,
        )
        next_commit_raw = finalizer._canonical_json_bytes(next_commit)
        finalizer._bind_run_state_next(
            run_dir,
            transaction_id,
            next_commit_raw,
            next_commit,
        )
        (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(
            next_commit_raw
        )

        self.assertTrue(finalizer._recover_run_state_journal(run_dir))

        self.assertEqual("next", ordinary.read_text(encoding="utf-8"))
        self.assertFalse((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).exists())

    def test_run_state_journal_rejects_third_authority_pointer_without_mutation(self) -> None:
        run_dir, _transaction_id, _backup_dir = self.make_run_state_recovery_fixture()
        ordinary = run_dir / "ordinary.txt"
        ordinary.write_text("partial", encoding="utf-8")
        closure = finalizer._authority_closure_bytes(run_dir)
        third = finalizer._authority_commit_payload(
            generation=99,
            transaction_id="e" * 24,
            role="LEGACY_BASELINE",
            members=closure,
        )
        (run_dir / finalizer.AUTHORITY_GROUP_COMMIT_NAME).write_bytes(
            finalizer._canonical_json_bytes(third)
        )

        with self.assertRaisesRegex(RuntimeError, "outside run-state journal"):
            finalizer._recover_run_state_journal(run_dir)

        self.assertEqual("partial", ordinary.read_text(encoding="utf-8"))
        self.assertTrue((run_dir / finalizer.RUN_STATE_JOURNAL_NAME).is_file())

    def test_orphan_run_state_transaction_fails_closed(self) -> None:
        run_dir = self.root / "orphan-run"
        run_dir.mkdir()
        orphan = finalizer._run_state_transaction_path(run_dir, "f" * 24)
        orphan.mkdir()

        with self.assertRaisesRegex(RuntimeError, "orphan run-state transaction"):
            finalizer._recover_run_state_journal(run_dir)

        self.assertTrue(orphan.is_dir())

    def test_required_run_state_binding_rejects_missing_journal_before_authority_publish(self) -> None:
        run_dir = self.root / "missing-required-journal"
        run_dir.mkdir()
        finalizer._recover_authority_group_journal(run_dir)
        before = _directory_bytes(run_dir)

        with self.assertRaisesRegex(RuntimeError, "required run-state journal"):
            finalizer._write_json_group_atomic(
                (
                    (run_dir / "finalization_metadata.json", {"value": 1}),
                    (run_dir / "latest_attempt_metadata.json", {"value": 1}),
                ),
                transaction_id="a" * 24,
                require_run_state_binding=True,
            )

        self.assertEqual(before, _directory_bytes(run_dir))

    def test_required_run_state_precheck_preserves_authority_crash_evidence(self) -> None:
        self.make_authority_crash_fixture(self.root)
        before = _directory_bytes(self.root)

        with self.assertRaisesRegex(RuntimeError, "required run-state journal"):
            finalizer._write_json_group_atomic(
                (
                    (self.root / "finalization_metadata.json", {"value": 1}),
                    (self.root / "latest_attempt_metadata.json", {"value": 1}),
                ),
                transaction_id="a" * 24,
                require_run_state_binding=True,
            )

        self.assertEqual(before, _directory_bytes(self.root))

    def test_nested_reserved_prefix_artifact_survives_run_state_restore(self) -> None:
        run_dir = self.root / "nested-prefix-artifact"
        victim = run_dir / "docs" / ".humanize-run-state-notes.txt"
        victim.parent.mkdir(parents=True)
        victim.write_bytes(b"KEEP")
        finalizer._recover_authority_group_journal(run_dir)
        transaction_id, backup_dir = finalizer._begin_run_state_transaction(run_dir)
        victim.write_bytes(b"CHANGED")

        finalizer._restore_run_state(run_dir, backup_dir)

        self.assertEqual(b"KEEP", victim.read_bytes())
        finalizer._cleanup_run_state_transaction(run_dir, transaction_id)

    def test_untrusted_run_state_staging_prefix_is_preserved_and_blocks_recovery(self) -> None:
        run_dir = self.root / "staging-prefix-collision"
        run_dir.mkdir()
        victim = run_dir / (
            finalizer.RUN_STATE_CLEANUP_STAGING_PREFIX + "user-notes"
        )
        victim.write_bytes(b"KEEP")

        with self.assertRaisesRegex(RuntimeError, "staging residue"):
            finalizer._recover_run_state_journal(run_dir)

        self.assertEqual(b"KEEP", victim.read_bytes())

    def test_unrelated_broad_run_state_prefix_does_not_create_orphan_transaction(self) -> None:
        run_dir = self.root / "broad-prefix-collision"
        run_dir.mkdir()
        victim = run_dir / ".humanize-run-state-user-notes.txt"
        victim.write_bytes(b"KEEP")

        self.assertFalse(finalizer._recover_run_state_journal(run_dir))

        self.assertEqual(b"KEEP", victim.read_bytes())

    def test_metadata_authority_group_keyboard_interrupt_restores_old_bytes(self) -> None:
        first = self.root / "finalization_metadata.json"
        second = self.root / "latest_attempt_metadata.json"
        first.write_bytes(b"PAIR-OLD\n")
        second.write_bytes(b"PAIR-OLD\n")
        real_replace = finalizer.os.replace
        target_replaces = 0

        def interrupt_second(source: object, target: object) -> None:
            nonlocal target_replaces
            if Path(target) in {first, second}:
                target_replaces += 1
                if target_replaces == 2:
                    raise KeyboardInterrupt
            real_replace(source, target)

        with mock.patch.object(
            finalizer.os, "replace", side_effect=interrupt_second
        ):
            with self.assertRaises(KeyboardInterrupt):
                finalizer._write_json_group_atomic(
                    ((first, {"new": 1}), (second, {"new": 1}))
                )

        self.assertEqual(b"PAIR-OLD\n", first.read_bytes())
        self.assertEqual(b"PAIR-OLD\n", second.read_bytes())
        self.assertFalse(
            (self.root / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).exists()
        )

    def test_metadata_authority_group_system_exit_restores_old_bytes(self) -> None:
        first = self.root / "finalization_metadata.json"
        second = self.root / "latest_attempt_metadata.json"
        first.write_bytes(b"PAIR-OLD\n")
        second.write_bytes(b"PAIR-OLD\n")
        real_replace = finalizer.os.replace
        target_replaces = 0

        def exit_on_second(source: object, target: object) -> None:
            nonlocal target_replaces
            if Path(target) in {first, second}:
                target_replaces += 1
                if target_replaces == 2:
                    raise SystemExit(73)
            real_replace(source, target)

        with mock.patch.object(finalizer.os, "replace", side_effect=exit_on_second):
            with self.assertRaisesRegex(SystemExit, "73"):
                finalizer._write_json_group_atomic(
                    ((first, {"new": 1}), (second, {"new": 1}))
                )

        self.assertEqual(b"PAIR-OLD\n", first.read_bytes())
        self.assertEqual(b"PAIR-OLD\n", second.read_bytes())

    def test_authority_group_recovery_is_retryable_after_mid_restore_failure(self) -> None:
        (
            first,
            second,
            old_first,
            old_second,
            new_first,
            _new_second,
            transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(self.root)
        first.write_bytes(new_first)
        second.write_bytes(old_second)
        real_replace = finalizer._replace_bytes_atomic
        recovery_replaces = 0

        def fail_second_recovery(path: Path, raw: bytes, **kwargs: object) -> None:
            nonlocal recovery_replaces
            if path in {first, second}:
                recovery_replaces += 1
                if recovery_replaces == 2:
                    raise OSError("RECOVERY-INTERRUPTED")
            real_replace(path, raw, **kwargs)

        with mock.patch.object(
            finalizer, "_replace_bytes_atomic", side_effect=fail_second_recovery
        ):
            with self.assertRaisesRegex(OSError, "RECOVERY-INTERRUPTED"):
                finalizer._recover_authority_group_journal(self.root)

        self.assertTrue(
            (self.root / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).is_file()
        )
        self.assertTrue(transaction_dir.is_dir())

        self.assertTrue(finalizer._recover_authority_group_journal(self.root))
        self.assertEqual(old_first, first.read_bytes())
        self.assertEqual(old_second, second.read_bytes())

    def test_authority_group_journal_tampering_fails_before_target_change(self) -> None:
        mutations = {
            "unknown_top_field": lambda journal: journal.update({"extra": 1}),
            "wrong_state": lambda journal: journal.update({"state": "COMMITTED"}),
            "duplicate_target": lambda journal: journal["members"][1].update(
                {"target": journal["members"][0]["target"]}
            ),
            "path_traversal": lambda journal: journal["members"][0].update(
                {"target": "../outside.json"}
            ),
            "wrong_old_hash": lambda journal: journal["members"][0].update(
                {"old_sha256": "0" * 64}
            ),
        }
        for index, (label, mutate) in enumerate(mutations.items()):
            with self.subTest(label=label):
                parent = self.root / f"tamper-{index}"
                parent.mkdir()
                (
                    first,
                    second,
                    _old_first,
                    old_second,
                    new_first,
                    _new_second,
                    _transaction_dir,
                    journal,
                ) = self.make_authority_crash_fixture(
                    parent, transaction_id=f"{index + 1:024x}"
                )
                first.write_bytes(new_first)
                second.write_bytes(old_second)
                mutate(journal)
                finalizer._write_json(
                    parent / finalizer.AUTHORITY_GROUP_JOURNAL_NAME, journal
                )

                with self.assertRaises(ValueError):
                    finalizer._recover_authority_group_journal(parent)

                self.assertEqual(new_first, first.read_bytes())
                self.assertEqual(old_second, second.read_bytes())

    def test_authority_group_recovery_rejects_backup_hardlink(self) -> None:
        (
            first,
            second,
            old_first,
            old_second,
            new_first,
            _new_second,
            transaction_dir,
            _journal,
        ) = self.make_authority_crash_fixture(
            self.root, transaction_id="a" * 24
        )
        first.write_bytes(new_first)
        second.write_bytes(old_second)
        (transaction_dir / "member-0.old").unlink()
        external_backup = self.root / "external-backup.bin"
        external_backup.write_bytes(old_first)
        os.link(external_backup, transaction_dir / "member-0.old")

        with self.assertRaisesRegex(ValueError, "hard link"):
            finalizer._recover_authority_group_journal(self.root)

        self.assertEqual(new_first, first.read_bytes())
        self.assertEqual(old_second, second.read_bytes())

    def test_orphan_authority_transaction_cleanup_is_closed_set(self) -> None:
        safe = self.root / (
            finalizer.AUTHORITY_GROUP_TRANSACTION_PREFIX + "b" * 24
        )
        safe.mkdir()
        (safe / "member-0.old").write_bytes(b"OLD")

        self.assertFalse(finalizer._recover_authority_group_journal(self.root))
        self.assertFalse(safe.exists())

        unsafe = self.root / (
            finalizer.AUTHORITY_GROUP_TRANSACTION_PREFIX + "c" * 24
        )
        unsafe.mkdir()
        (unsafe / "unexpected.txt").write_text("do not delete", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "unknown member"):
            finalizer._recover_authority_group_journal(self.root)
        self.assertTrue((unsafe / "unexpected.txt").exists())

    def test_finalize_keyboard_interrupt_before_authority_commit_restores_run_state(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        finalizer._recover_authority_group_journal(run_dir)
        before = finalizer._run_state_hashes(run_dir)

        with mock.patch.object(
            finalizer, "_write_json_group_atomic", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                finalizer.finalize(run_dir, rewrites)

        self.assertEqual(before, finalizer._run_state_hashes(run_dir))
        self.assertFalse((run_dir / "rendered_review").exists())
        self.assertFalse((run_dir / "validation").exists())

    def test_finalize_lock_rejects_hardlink(self) -> None:
        lock_target = self.root / "lock-target.bin"
        lock_target.write_bytes(b"0")
        os.link(lock_target, self.root / ".finalize.lock")

        with self.assertRaisesRegex(ValueError, "hard link"):
            with finalizer._run_lock(self.root):
                self.fail("hard-linked lock must not be acquired")

    def test_metadata_persistence_failure_restores_run_and_survives_only_in_memory(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        state_before = finalizer._run_state_hashes(run_dir)
        real_replace = finalizer.os.replace

        def fail_latest(source: object, target: object) -> None:
            if Path(target).name == "latest_attempt_metadata.json":
                raise PermissionError(
                    r"C:\Users\Private\SECRET-CONTENT\latest_attempt_metadata.json"
                )
            real_replace(source, target)

        with mock.patch.object(finalizer.os, "replace", side_effect=fail_latest):
            with self.assertRaises(PermissionError) as raised:
                finalizer.finalize(run_dir, rewrites)

        self.assertEqual(state_before, finalizer._run_state_hashes(run_dir))
        self.assertFalse((run_dir / "last_failed_attempt_metadata.json").exists())
        self.assertFalse((run_dir / "latest_attempt_metadata.json").exists())
        self.assertFalse((run_dir / "finalization_metadata.json").exists())
        failure = getattr(raised.exception, "_humanize_failure_metadata")
        self.assertTrue(failure["run_state_restored_after_failure"])
        self.assertEqual("FAILED", failure["attempt_metadata_persistence_status"])
        self.assertFalse(failure["attempt_metadata_paths_authoritative"])
        serialized = json.dumps(failure, ensure_ascii=False)
        self.assertNotIn("SECRET-CONTENT", serialized)
        self.assertNotIn(r"C:\Users\Private", serialized)

    def test_runtime_text_summary_redacts_exception_message_and_paths(self) -> None:
        metadata = finalizer._runtime_failure_metadata(
            FileNotFoundError(r"C:\Users\Private\SECRET-CONTENT"),
            run_dir=Path(r"C:\Users\Private\run"),
            run_state_restored=True,
            finalization_metadata_preserved=True,
            published_evidence_preserved=True,
        )
        summary = finalizer._render_text_summary(metadata)

        self.assertIn("runtime_error=FileNotFoundError:FILE_NOT_FOUND", summary)
        self.assertIn("details=latest_attempt_metadata.json", summary)
        self.assertIn("content_redacted=true", summary)
        self.assertNotIn("SECRET-CONTENT", summary)
        self.assertNotIn(r"C:\Users\Private", summary)

    def test_main_uses_in_memory_failure_when_attempt_metadata_cannot_persist(self) -> None:
        error = PermissionError(r"C:\Users\Private\SECRET-CONTENT")
        failure = finalizer._runtime_failure_metadata(
            error,
            run_dir=self.root / "run",
            run_state_restored=True,
            finalization_metadata_preserved=True,
            published_evidence_preserved=True,
        )
        failure["attempt_metadata_persistence_status"] = "FAILED"
        failure["attempt_metadata_paths_authoritative"] = False
        setattr(error, "_humanize_failure_metadata", failure)
        stdout = io.StringIO()

        with mock.patch.object(finalizer, "finalize", side_effect=error), mock.patch.object(
            sys, "stdout", stdout
        ):
            exit_code = finalizer.main(
                [
                    "--run-dir",
                    str(self.root / "run"),
                    "--rewrites",
                    str(self.root),
                    "--format",
                    "text",
                ]
            )

        rendered = stdout.getvalue()
        self.assertEqual(1, exit_code)
        self.assertIn("attempt_metadata_persistence=FAILED", rendered)
        self.assertIn("paths_authoritative=false", rendered)
        self.assertNotIn("SECRET-CONTENT", rendered)
        self.assertNotIn(r"C:\Users\Private", rendered)

    def test_main_never_reuses_stale_latest_after_restore_failure(self) -> None:
        run_dir = self.root / "run"
        run_dir.mkdir()
        stale = finalizer._runtime_failure_metadata(
            PermissionError("OLD"),
            run_dir=run_dir,
            run_state_restored=True,
            finalization_metadata_preserved=True,
            published_evidence_preserved=True,
        )
        stale["created_at"] = "2000-01-01T00:00:00Z"
        stale["attempt_metadata_role"] = "LATEST_FAILED_ATTEMPT_AUTHORITY"
        finalizer._write_json(run_dir / "latest_attempt_metadata.json", stale)

        error = PermissionError("CURRENT-RESTORE-FAILURE")
        current = finalizer._runtime_failure_metadata(
            error,
            run_dir=run_dir,
            run_state_restored=False,
            finalization_metadata_preserved=False,
            published_evidence_preserved=False,
        )
        current.update(
            {
                "run_state_restore_status": "FAILED",
                "run_state_restore_error_code": "RUN_STATE_RESTORE_FAILED",
                "attempt_metadata_persistence_status": "FAILED",
                "attempt_metadata_paths_authoritative": False,
            }
        )
        setattr(error, "_humanize_failure_metadata", current)
        stdout = io.StringIO()
        with mock.patch.object(finalizer, "finalize", side_effect=error), mock.patch.object(
            sys, "stdout", stdout
        ):
            exit_code = finalizer.main(
                [
                    "--run-dir",
                    str(run_dir),
                    "--rewrites",
                    str(self.root),
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("FAILED", payload["run_state_restore_status"])
        self.assertEqual(
            "RUN_STATE_RESTORE_FAILED", payload["run_state_restore_error_code"]
        )
        self.assertFalse(payload["attempt_metadata_paths_authoritative"])
        self.assertNotEqual("2000-01-01T00:00:00Z", payload["created_at"])

    def test_text_summary_leads_with_authoritative_delivery_state(self) -> None:
        stdout = io.StringIO()
        metadata = {
            "status": "REVIEW",
            "exit_code": 2,
            "delivery_gate_status": "REVIEW",
            "publish_state": "REVIEW_CANDIDATE",
            "candidate_assembly_status": "PASS",
            "paired_quality_gate_status": "PENDING_EXTERNAL_REVIEW",
            "unit_statuses": {"DONE": 1},
            "published_path": str(self.root / "run" / "rendered_review"),
            "compile_check": {"status": "NOT_RUN"},
            "humanize_completion_claim_allowed": False,
        }
        with mock.patch.object(finalizer, "finalize", return_value=metadata), mock.patch.object(
            sys, "stdout", stdout
        ):
            exit_code = finalizer.main(
                [
                    "--run-dir",
                    str(self.root / "run"),
                    "--rewrites",
                    str(self.root),
                    "--format",
                    "text",
                ]
            )

        rendered = stdout.getvalue()
        self.assertEqual(2, exit_code)
        self.assertEqual(
            "DELIVERY REVIEW exit=2 publish=REVIEW_CANDIDATE",
            rendered.splitlines()[0],
        )
        self.assertIn("scope=CANDIDATE_ASSEMBLY_NOT_DELIVERY", rendered)
        self.assertIn("review_candidate=", rendered)
        self.assertIn("humanize_completion_claim_allowed=false", rendered)

    def test_text_summary_indexes_unresolved_details_without_echoing_notes(self) -> None:
        summary = finalizer._render_text_summary(
            {
                "delivery_gate_status": "REVIEW",
                "exit_code": 2,
                "publish_state": "PARTIAL",
                "candidate_assembly_status": "REVIEW",
                "paired_quality_gate_status": "BLOCKED",
                "unit_statuses": {"UNRESOLVED": 2},
                "unresolved_reason_summary": {
                    "total": 2,
                    "classified": 1,
                    "unclassified": 1,
                    "codes": {"missing_function_anchor": 1},
                    "details_artifact": "coverage_ledger.final.csv",
                    "content_redacted": True,
                },
                "compile_check": {"status": "NOT_RUN"},
                "humanize_completion_claim_allowed": False,
                "notes": "SECRET-CONTENT",
            }
        )

        self.assertIn("unresolved_details=coverage_ledger.final.csv", summary)
        self.assertIn("reason_codes[missing_function_anchor=1]", summary)
        self.assertIn("content_redacted=true", summary)
        self.assertNotIn("SECRET-CONTENT", summary)

    def test_malformed_rerun_restores_previous_candidate_and_marks_failed_attempt(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        path = rewrites / f"{unit['unit_id']}.json"
        path.write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        finalizer.finalize(run_dir, rewrites)
        state_before = finalizer._run_state_hashes(run_dir)
        state_before.pop("latest_attempt_metadata.json", None)
        path.write_text("{", encoding="utf-8")

        with self.assertRaises(ValueError):
            finalizer.finalize(run_dir, rewrites)

        state_after = finalizer._run_state_hashes(run_dir)
        state_after.pop("last_failed_attempt_metadata.json", None)
        state_after.pop("latest_attempt_metadata.json", None)
        self.assertEqual(state_before, state_after)
        failure = json.loads(
            (run_dir / "last_failed_attempt_metadata.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("FAIL", failure["delivery_gate_status"])
        self.assertEqual(1, failure["exit_code"])
        self.assertTrue(failure["failed_attempt"])
        self.assertTrue(failure["run_state_restored_after_failure"])
        self.assertTrue(failure["published_evidence_preserved"])
        self.assertEqual(
            "NOT_RETAINED_AFTER_ROLLBACK",
            failure["failed_attempt_evidence_status"],
        )
        self.assertFalse(failure["failed_attempt_evidence_paths_reusable"])
        self.assertEqual(
            failure,
            json.loads(
                (run_dir / "latest_attempt_metadata.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertEqual(
            "LATEST_FAILED_ATTEMPT_AUTHORITY",
            failure["attempt_metadata_role"],
        )
        self.assertTrue(failure["error_message_redacted"])
        self.assertTrue(failure["paths_redacted"])
        self.assertNotIn("error", failure)
        self.assertNotIn("run_dir", failure)

    def test_finalize_interrupt_after_authority_pointer_commit_does_not_restore_old_evidence(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持原有平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "正式定义保持原有平行结构",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        real_replace = finalizer.os.replace
        pointer_replacements = 0

        def interrupt_after_pointer(source: object, target: object) -> None:
            nonlocal pointer_replacements
            real_replace(source, target)
            if Path(target).name == finalizer.AUTHORITY_GROUP_COMMIT_NAME:
                pointer_replacements += 1
                if pointer_replacements == 2:
                    raise KeyboardInterrupt

        with mock.patch.object(
            finalizer.os, "replace", side_effect=interrupt_after_pointer
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                finalizer.finalize(run_dir, rewrites)

        failure = getattr(caught.exception, "_humanize_failure_metadata")
        self.assertTrue(failure["authority_generation_committed_before_interruption"])
        self.assertEqual(
            "NOT_ATTEMPTED_AFTER_AUTHORITY_COMMIT",
            failure["run_state_restore_status"],
        )
        self.assertTrue((run_dir / "finalization_metadata.json").is_file())
        self.assertTrue((run_dir / "latest_attempt_metadata.json").is_file())
        self.assertFalse((run_dir / "last_failed_attempt_metadata.json").exists())
        self.assertTrue(
            (run_dir / "rendered_review").is_dir()
            or (run_dir / "rendered").is_dir()
            or (run_dir / "rendered_partial").is_dir()
        )
        self.assertFalse(
            (run_dir / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).exists()
        )

    def test_argument_syntax_error_keeps_argparse_exit_two(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "stdout", stdout), mock.patch.object(
            sys, "stderr", stderr
        ):
            with self.assertRaises(SystemExit) as raised:
                finalizer.main([])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("usage:", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

    def test_protected_only_document_cannot_claim_full_completion(self) -> None:
        source = self.root / "only.tex"
        source.write_text(
            "\\section{保护内容}\n\\label{eq:one}\n\\[x^2=1\\]\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run"
        preparer.prepare([source], run_dir, scene="RESEARCH", min_author_chars=0)

        result = finalizer.finalize(run_dir, self.rewrite_dir())

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(0, result["processable_editable_units"])
        self.assertFalse((run_dir / "rendered").exists())

    def test_check_command_side_effects_in_disposable_copy_do_not_publish(self) -> None:
        source, run_dir, unit = self.prepare("\\section{定义}\n值得注意的是，该段文字自然。\n")
        rewrites = self.rewrite_dir()
        source_span = self.masked_line_span(
            unit["masked_text"], "值得注意的是"
        )
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.v3_rewrite_bundle(
                    run_dir,
                    unit,
                    masked_text=unit["masked_text"].replace(
                        "值得注意的是，", ""
                    ),
                    source_span=source_span,
                    summary="删除失去强调作用的程式化提示语",
                    target_signal="LEX-EMPH-01",
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        command = f'"{sys.executable}" -c "from pathlib import Path; Path(\'build-side-effect.txt\').write_text(\'ok\')"'

        result = finalizer.finalize(run_dir, rewrites, check_command=command)

        self.assert_paired_quality_review_candidate(result)
        self.assert_compile_check_schema(result["compile_check"])
        self.assertTrue(result["coverage_completion_claim_allowed"])
        self.assertEqual("PASS", result["voice_binding_status"])
        self.assertEqual("PASS", result["voice_conformance_status"])
        self.assertEqual("PASS", result["cross_unit_repetition_status"])
        self.assertEqual("NOT_RUN", result["humanize_second_pass_convergence"])
        self.assertTrue(result["voice_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse(result["full_completion_claim_allowed"])
        self.assertEqual(result["idempotency"], result["assembly_replay_idempotency"])
        self.assertEqual(
            str((run_dir / ".compile_check_staging").resolve()),
            result["compile_check"]["cwd"],
        )
        self.assertEqual("PASS", result["compile_check"]["integrity_status"])
        self.assertEqual({}, result["compile_check"]["integrity_changes"])
        self.assertFalse(result["evidence_artifacts_changed_during_check"])
        self.assertFalse(result["staged_evidence_discarded"])
        rendered = next((run_dir / "rendered_review").rglob("*.tex")).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("值得注意的是", rendered)
        self.assertFalse(
            (run_dir / "rendered_review" / "build-side-effect.txt").exists()
        )
        self.assertFalse((run_dir / "rendered").exists())
        self.assertFalse((run_dir / ".compile_check_staging").exists())

    def test_check_command_descendants_cannot_poison_after_finalize_returns(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n值得注意的是，该段文字自然。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "REWRITE",
                        "masked_text": unit["masked_text"].replace(
                            "值得注意的是，", ""
                        ),
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        target = run_dir / "rendered_review" / "main.tex"
        child = self.root / "late-child.py"
        child.write_text(
            "import time\n"
            "from pathlib import Path\n"
            "time.sleep(0.8)\n"
            f"target = Path({str(target)!r})\n"
            "if target.is_file():\n"
            "    target.write_text('LATE_POISON\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        spawner = self.root / "spawn-late-child.py"
        spawner.write_text(
            "import os, subprocess, sys\n"
            "kwargs = {}\n"
            "if os.name == 'nt':\n"
            "    kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP\n"
            "else:\n"
            "    kwargs['start_new_session'] = True\n"
            f"subprocess.Popen([sys.executable, {str(child)!r}], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
            "stderr=subprocess.DEVNULL, close_fds=True, **kwargs)\n",
            encoding="utf-8",
        )
        command = f'"{sys.executable}" "{spawner}"'

        result = finalizer.finalize(run_dir, rewrites, check_command=command)
        time.sleep(1.1)

        self.assert_paired_quality_review_candidate(result)
        self.assertEqual("PASS", result["compile_check"]["descendant_cleanup"])
        self.assertEqual(
            "WINDOWS_JOB_OBJECT"
            if os.name == "nt"
            else "LINUX_SUBREAPER_PROCESS_GROUP",
            result["compile_check"]["process_containment"],
        )
        self.assertNotEqual("LATE_POISON\n", target.read_text(encoding="utf-8"))

    def test_posix_supervisor_enables_subreaper_before_command_spawn(self) -> None:
        source = finalizer._posix_compile_wrapper_source()

        self.assertLess(
            source.index("subreaper_enabled = enable_subreaper()"),
            source.index("child = subprocess.Popen(command, shell=True, close_fds=True)"),
        )
        self.assertLess(
            source.index("signal.signal(watched_signal, raise_supervisor_signal)"),
            source.index("child = subprocess.Popen(command, shell=True, close_fds=True)"),
        )
        self.assertLess(
            source.index("ignore_supervisor_signals()"),
            source.index("direct_child_stopped = stop_direct_child(child)"),
        )
        interrupted = source.index("except SupervisorSignal as interruption:")
        self.assertLess(
            source.index("direct_child_stopped = stop_direct_child(child)", interrupted),
            source.index("cleanup_ok = cleanup_adopted_descendants", interrupted),
        )
        self.assertIn(
            "cleanup_adopted_descendants(subreaper_enabled)",
            source,
        )
        self.assertIn(
            "if not subreaper_enabled:",
            source,
        )

    def test_posix_supervisor_stop_prefers_graceful_cleanup_to_sigkill(self) -> None:
        events: list[str] = []

        class Process:
            pid = 41001

            def terminate(self) -> None:
                events.append("terminate")

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                return 143

            def kill(self) -> None:
                events.append("kill")

        result = finalizer._stop_posix_compile_supervisor(
            Process(), graceful_timeout=0.01
        )

        self.assertEqual("PASS", result)
        self.assertEqual(["terminate", "wait:0.01"], events)

    def test_posix_containment_labels_fail_closed_capability_states(self) -> None:
        with mock.patch.object(finalizer.sys, "platform", "linux"):
            self.assertEqual(
                "LINUX_SUBREAPER_UNAVAILABLE",
                finalizer._posix_process_containment_label(
                    supervisor_cleanup="FAIL", return_code=125
                ),
            )
            self.assertEqual(
                "LINUX_SUBREAPER_PROCESS_GROUP",
                finalizer._posix_process_containment_label(
                    supervisor_cleanup="PASS", return_code=125
                ),
            )
        with mock.patch.object(finalizer.sys, "platform", "darwin"):
            self.assertEqual(
                "POSIX_SUBREAPER_UNSUPPORTED",
                finalizer._posix_process_containment_label(
                    supervisor_cleanup="FAIL", return_code=125
                ),
            )

    def test_posix_supervisor_timeout_enumerates_descendants_before_sigkill(self) -> None:
        events: list[str] = []

        class Process:
            pid = 41002

            def terminate(self) -> None:
                events.append("terminate")

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                if timeout is not None:
                    raise subprocess.TimeoutExpired("wrapper", timeout)
                return -9

            def kill(self) -> None:
                events.append("kill")

        process = Process()

        def kill_descendants(live_process: object) -> str:
            self.assertIs(process, live_process)
            self.assertNotIn("kill", events)
            events.append("enumerate-descendants")
            return "PASS"

        with mock.patch.object(
            finalizer,
            "_kill_linux_descendants_before_supervisor_exit",
            side_effect=kill_descendants,
        ), mock.patch.object(
            finalizer,
            "_terminate_compile_process_tree",
            return_value="PASS",
        ):
            result = finalizer._stop_posix_compile_supervisor(
                process, graceful_timeout=0.01
            )

        self.assertEqual("PASS", result)
        self.assertLess(events.index("enumerate-descendants"), events.index("kill"))

    def test_run_compile_interruption_routes_posix_wrapper_to_graceful_stop(self) -> None:
        events: list[str] = []

        class Process:
            pid = 41003
            returncode = None

            def communicate(
                self, _command: str, timeout: float | None = None
            ) -> None:
                events.append("communicate")
                raise KeyboardInterrupt

            def poll(self) -> int | None:
                return None

            def kill(self) -> None:
                events.append("kill")

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                return -15

        process = Process()
        with mock.patch.object(finalizer.os, "name", "posix"), mock.patch.object(
            finalizer.subprocess, "Popen", return_value=process
        ), mock.patch.object(
            finalizer,
            "_stop_posix_compile_supervisor",
            return_value="PASS",
        ) as graceful_stop:
            with self.assertRaises(KeyboardInterrupt):
                finalizer._run_compile("exit 0", self.root)

        graceful_stop.assert_called_once_with(process)
        self.assertNotIn("kill", events)

    def test_posix_supervisor_stop_swallows_second_interrupt_and_still_kills(self) -> None:
        events: list[str] = []

        class Process:
            pid = 41004

            def terminate(self) -> None:
                events.append("terminate")
                raise KeyboardInterrupt

            def poll(self) -> int | None:
                return None

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                if timeout is not None:
                    raise subprocess.TimeoutExpired("wrapper", timeout)
                return -9

            def kill(self) -> None:
                events.append("kill")

        process = Process()
        with mock.patch.object(
            finalizer,
            "_kill_linux_descendants_before_supervisor_exit",
            return_value="PASS",
        ) as kill_descendants, mock.patch.object(
            finalizer,
            "_terminate_compile_process_tree",
            return_value="PASS",
        ):
            result = finalizer._stop_posix_compile_supervisor(process)

        self.assertEqual("PASS", result)
        kill_descendants.assert_called_once_with(process)
        self.assertLess(events.index("terminate"), events.index("kill"))

    def test_posix_supervisor_stop_swallows_interrupt_during_kill(self) -> None:
        events: list[str] = []

        class Process:
            pid = 41005

            def terminate(self) -> None:
                events.append("terminate")

            def poll(self) -> int | None:
                return None

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                if timeout is not None:
                    raise subprocess.TimeoutExpired("wrapper", timeout)
                return -9

            def kill(self) -> None:
                events.append("kill")
                raise KeyboardInterrupt

        process = Process()
        with mock.patch.object(
            finalizer,
            "_kill_linux_descendants_before_supervisor_exit",
            return_value="PASS",
        ), mock.patch.object(
            finalizer,
            "_terminate_compile_process_tree",
            return_value="PASS",
        ):
            result = finalizer._stop_posix_compile_supervisor(process)

        self.assertEqual("PASS", result)
        self.assertIn("kill", events)

    def test_windows_job_handle_closes_when_termination_is_interrupted(self) -> None:
        closed: list[int] = []

        class Kernel:
            def TerminateJobObject(self, _job: int, _code: int) -> bool:
                raise KeyboardInterrupt

            def CloseHandle(self, job: int) -> bool:
                closed.append(job)
                return True

        with mock.patch.object(finalizer.os, "name", "nt"):
            result = finalizer._terminate_compile_process_tree(
                mock.Mock(), (17, Kernel())
            )

        self.assertEqual("FAIL", result)
        self.assertEqual([17], closed)

    def test_windows_uncontained_cleanup_retries_after_interrupt(self) -> None:
        class Process:
            pid = 41006

            def __init__(self) -> None:
                self.alive = True
                self.kill_calls = 0

            def poll(self) -> int | None:
                return None if self.alive else -9

            def kill(self) -> None:
                self.kill_calls += 1
                if self.kill_calls == 1:
                    raise KeyboardInterrupt
                self.alive = False

            def wait(self, timeout: float | None = None) -> int:
                return -9

        process = Process()
        with mock.patch.object(finalizer.os, "name", "nt"):
            result = finalizer._terminate_compile_process_tree(process, None)

        self.assertEqual("PASS", result)
        self.assertEqual(2, process.kill_calls)

    def test_compile_wrapper_launch_uses_isolated_python_flags(self) -> None:
        calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        class Process:
            returncode = 0

            def communicate(
                self, _command: str, timeout: float | None = None
            ) -> tuple[None, None]:
                return None, None

        process = Process()

        def fake_popen(*args: object, **kwargs: object) -> Process:
            calls.append((args, kwargs))
            return process

        def fake_read(fd: int, **_kwargs: object) -> str:
            os.close(fd)
            return "PASS"

        with mock.patch.object(finalizer.os, "name", "posix"), mock.patch.object(
            finalizer.subprocess, "Popen", side_effect=fake_popen
        ), mock.patch.object(
            finalizer, "_read_posix_compile_status", side_effect=fake_read
        ), mock.patch.object(
            finalizer, "_terminate_compile_process_tree", return_value="PASS"
        ):
            result = finalizer._run_compile("exit 0", self.root)

        self.assertEqual("PASS", result["status"])
        argv = calls[0][0][0]
        self.assertEqual(
            [sys.executable, "-I", "-S", "-X", "utf8", "-c"],
            list(argv[:6]),
        )

    def test_run_compile_setup_interrupt_closes_posix_status_fds(self) -> None:
        real_pipe = os.pipe
        real_close = os.close
        real_set_inheritable = os.set_inheritable
        status_read_fd, status_write_fd = real_pipe()
        closed: list[int] = []

        def fake_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        def fake_set_inheritable(fd: int, inheritable: bool) -> None:
            if fd == status_write_fd:
                raise KeyboardInterrupt
            real_set_inheritable(fd, inheritable)

        try:
            with mock.patch.object(finalizer.os, "name", "posix"), mock.patch.object(
                finalizer.os, "pipe", return_value=(status_read_fd, status_write_fd)
            ), mock.patch.object(
                finalizer.os, "set_inheritable", side_effect=fake_set_inheritable
            ), mock.patch.object(finalizer.os, "close", side_effect=fake_close):
                with self.assertRaises(KeyboardInterrupt):
                    finalizer._run_compile("exit 0", self.root)
        finally:
            for fd in (status_read_fd, status_write_fd):
                try:
                    real_close(fd)
                except OSError:
                    pass

        self.assertIn(status_read_fd, closed)
        self.assertIn(status_write_fd, closed)

    def test_run_compile_timeout_is_structured_and_routes_posix_cleanup(self) -> None:
        calls: list[tuple[str, float | None]] = []

        class Process:
            pid = 41007
            returncode = 143

            def communicate(
                self, command: str, timeout: float | None = None
            ) -> None:
                calls.append((command, timeout))
                raise subprocess.TimeoutExpired(command, timeout)

        process = Process()

        def fake_status_read(fd: int, **_kwargs: object) -> str:
            os.close(fd)
            return "PASS"

        with mock.patch.object(finalizer.os, "name", "posix"), mock.patch.object(
            finalizer.sys, "platform", "linux"
        ), mock.patch.object(
            finalizer.subprocess, "Popen", return_value=process
        ), mock.patch.object(
            finalizer,
            "_stop_posix_compile_supervisor",
            return_value="PASS",
        ) as graceful_stop, mock.patch.object(
            finalizer,
            "_read_posix_compile_status",
            side_effect=fake_status_read,
        ), mock.patch.object(
            finalizer,
            "_terminate_compile_process_tree",
            return_value="PASS",
        ) as group_cleanup:
            result = finalizer._run_compile(
                "long-running-check", self.root, timeout_seconds=0.25
            )

        self.assert_compile_check_schema(result)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(124, result["exit_code"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(0.25, result["timeout_seconds"])
        self.assertEqual("PASS", result["descendant_cleanup"])
        self.assertEqual("LINUX_SUBREAPER_PROCESS_GROUP", result["process_containment"])
        self.assertIn("timed out after 0.25 seconds", result["stderr"])
        self.assertEqual([("long-running-check", 0.25)], calls)
        graceful_stop.assert_called_once_with(process)
        group_cleanup.assert_called_once_with(process, None)

    def test_run_compile_timeout_assigns_windows_job_before_releasing_command(self) -> None:
        events: list[str] = []
        containment = object()

        class Process:
            returncode = 1

            def communicate(
                self, command: str, timeout: float | None = None
            ) -> None:
                self.command = command
                events.append(f"communicate:{timeout}")
                raise subprocess.TimeoutExpired(command, timeout)

            def wait(self, timeout: float | None = None) -> int:
                events.append(f"wait:{timeout}")
                return 1

        process = Process()

        def assign_job(_process: object) -> object:
            self.assertIs(process, _process)
            events.append("assign-job")
            return containment

        def terminate_tree(_process: object, active_containment: object) -> str:
            self.assertIs(process, _process)
            self.assertIs(containment, active_containment)
            events.append("terminate-job")
            return "PASS"

        with mock.patch.object(finalizer.os, "name", "nt"), mock.patch.object(
            finalizer.subprocess, "CREATE_NO_WINDOW", 0, create=True
        ), mock.patch.object(
            finalizer.subprocess, "Popen", return_value=process
        ), mock.patch.object(
            finalizer,
            "_assign_windows_kill_on_close_job",
            side_effect=assign_job,
        ), mock.patch.object(
            finalizer,
            "_terminate_compile_process_tree",
            side_effect=terminate_tree,
        ):
            result = finalizer._run_compile(
                "long-running-check", self.root, timeout_seconds=0.5
            )

        self.assert_compile_check_schema(result)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(124, result["exit_code"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(0.5, result["timeout_seconds"])
        self.assertEqual("PASS", result["descendant_cleanup"])
        self.assertEqual("WINDOWS_JOB_OBJECT", result["process_containment"])
        self.assertLess(events.index("assign-job"), events.index("communicate:0.5"))
        self.assertLess(events.index("communicate:0.5"), events.index("terminate-job"))
        self.assertLess(events.index("terminate-job"), events.index("wait:1.0"))

    def test_posix_status_read_has_a_deadline_when_writer_stays_open(self) -> None:
        read_fd, write_fd = os.pipe()
        started = time.monotonic()
        try:
            result = finalizer._read_posix_compile_status(
                read_fd, timeout_seconds=0.03
            )
            read_fd = -1
        finally:
            os.close(write_fd)
            if read_fd >= 0:
                os.close(read_fd)

        self.assertEqual("FAIL", result)
        self.assertLess(time.monotonic() - started, 0.5)

    def test_posix_status_reader_requires_one_exact_record(self) -> None:
        payloads = [
            b'{"cleanup":"FAIL","command_exit":9}\n'
            b'{"cleanup":"PASS","command_exit":0}\n',
            b'{"cleanup":"PASS","command_exit":0,"extra":true}\n',
            b'{"cleanup":"PASS","command_exit":true}\n',
            b'{"cleanup":"FAIL","cleanup":"PASS","command_exit":0}\n',
            b'{"cleanup":"PASS","command_exit":NaN}\n',
        ]
        for payload in payloads:
            read_fd, write_fd = os.pipe()
            try:
                os.write(write_fd, payload)
                os.close(write_fd)
                write_fd = -1
                self.assertEqual("FAIL", finalizer._read_posix_compile_status(read_fd))
                read_fd = -1
            finally:
                for fd in (read_fd, write_fd):
                    if fd >= 0:
                        os.close(fd)

    def test_posix_status_reader_binds_command_exit_to_wrapper(self) -> None:
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b'{"cleanup":"PASS","command_exit":0}\n')
            os.close(write_fd)
            write_fd = -1
            self.assertEqual(
                "FAIL",
                finalizer._read_posix_compile_status(
                    read_fd, expected_command_exit=143
                ),
            )
            read_fd = -1
        finally:
            for fd in (read_fd, write_fd):
                if fd >= 0:
                    os.close(fd)

    @unittest.skipUnless(
        os.name == "nt" or sys.platform.startswith("linux"),
        "requires Windows Job Object or Linux subreaper containment",
    )
    def test_real_compile_timeout_kills_detached_descendant(self) -> None:
        poison = self.root / "timeout-poison.txt"
        child_pid_path = self.root / "timeout-child.pid"
        spawner_pid_path = self.root / "timeout-spawner.pid"
        child = self.root / "timeout-child.py"
        child.write_text(
            "import os, time\n"
            "from pathlib import Path\n"
            f"Path({str(child_pid_path)!r}).write_text(str(os.getpid()), encoding='ascii')\n"
            "time.sleep(0.8)\n"
            f"Path({str(poison)!r}).write_text('POISON', encoding='ascii')\n",
            encoding="utf-8",
        )
        spawner = self.root / "timeout-spawner.py"
        spawner.write_text(
            "import os, subprocess, sys, time\n"
            "from pathlib import Path\n"
            f"Path({str(spawner_pid_path)!r}).write_text(str(os.getpid()), encoding='ascii')\n"
            "kwargs = {}\n"
            "if os.name == 'nt':\n"
            "    kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP\n"
            "else:\n"
            "    kwargs['start_new_session'] = True\n"
            f"subprocess.Popen([sys.executable, {str(child)!r}], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
            "stderr=subprocess.DEVNULL, close_fds=True, **kwargs)\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        command = f'"{sys.executable}" "{spawner}"'

        pids: list[int] = []
        try:
            result = finalizer._run_compile(
                command, self.root, timeout_seconds=0.2
            )
            time.sleep(1.0)
            for path in (child_pid_path, spawner_pid_path):
                if path.is_file():
                    pids.append(int(path.read_text(encoding="ascii")))

            self.assert_compile_check_schema(result)
            self.assertEqual("FAIL", result["status"])
            self.assertEqual(124, result["exit_code"])
            self.assertTrue(result["timed_out"])
            self.assertEqual(0.2, result["timeout_seconds"])
            self.assertEqual("PASS", result["descendant_cleanup"])
            self.assertFalse(poison.exists())
        finally:
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "requires Linux subreaper semantics"
    )
    def test_posix_wrapper_signal_cleans_setsids_descendant_before_exit(self) -> None:
        target = self.root / "late-poison.txt"
        started = self.root / "detached-started.txt"
        child = self.root / "detached-child.py"
        child.write_text(
            "import os, time\n"
            "from pathlib import Path\n"
            f"Path({str(started)!r}).write_text(str(os.getpid()), encoding='ascii')\n"
            "time.sleep(0.8)\n"
            f"Path({str(target)!r}).write_text('POISON', encoding='ascii')\n",
            encoding="utf-8",
        )
        spawner = self.root / "long-running-spawner.py"
        spawner.write_text(
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, {str(child)!r}], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
            "stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        command = f"{shlex.quote(sys.executable)} {shlex.quote(str(spawner))}"
        read_fd, write_fd = os.pipe()
        os.set_inheritable(write_fd, True)
        environment = os.environ.copy()
        environment["CODEX_COMPILE_STATUS_FD"] = str(write_fd)
        process = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                "-c",
                finalizer._posix_compile_wrapper_source(),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=environment,
            pass_fds=(write_fd,),
            start_new_session=True,
        )
        os.close(write_fd)
        detached_pid: int | None = None
        try:
            assert process.stdin is not None
            process.stdin.write(command)
            process.stdin.close()
            deadline = time.monotonic() + 5.0
            while not started.is_file() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(started.is_file(), "detached child did not start")
            detached_pid = int(started.read_text(encoding="ascii"))
            process.terminate()
            process.wait(timeout=5.0)
            cleanup = finalizer._read_posix_compile_status(read_fd)
            read_fd = -1
            time.sleep(1.0)
            self.assertEqual("PASS", cleanup)
            self.assertFalse(target.exists())
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            if process.poll() is None:
                process.kill()
                process.wait()
            if detached_pid is not None:
                try:
                    os.kill(detached_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_compile_check_schema_is_stable_when_command_is_not_provided(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持平行结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "正式定义保持原有平行结构"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(run_dir, rewrites)

        self.assert_paired_quality_review_candidate(result)
        self.assert_compile_check_schema(result["compile_check"])
        self.assertEqual("NOT_RUN", result["compile_check"]["status"])
        self.assertFalse(result["compile_check"]["timed_out"])
        self.assertIsNone(result["compile_check"]["timeout_seconds"])
        self.assertIsNone(result["compile_check"]["cwd"])
        self.assertEqual("PASS", result["compile_check"]["integrity_status"])
        self.assertEqual({}, result["compile_check"]["integrity_changes"])

    def test_invalid_compile_timeout_is_rejected_before_any_skip_branch(self) -> None:
        _, run_dir, _unit = self.prepare("\\section{定义}\n该定义保持原有的逻辑结构。\n")
        with self.assertRaisesRegex(ValueError, "finite positive"):
            finalizer._finalize_locked(
                run_dir,
                self.rewrite_dir(),
                check_timeout_seconds=0,
            )

    def test_compile_check_schema_is_stable_when_format_check_fails(self) -> None:
        _, run_dir, unit = self.prepare(
            "\\section{定义}\n该定义保持{未闭合的平行结构。\n"
        )
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {"decision": "NO_CHANGE", "reason": "保留输入中的原有形式"},
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = finalizer.finalize(
            run_dir,
            rewrites,
            check_command=f'"{sys.executable}" -c "raise SystemExit(9)"',
        )

        self.assertEqual("FAIL", result["status"])
        self.assertTrue(result["full_format_errors"])
        self.assert_compile_check_schema(result["compile_check"])
        self.assertEqual("NOT_RUN_DUE_TO_FORMAT_FAILURE", result["compile_check"]["status"])
        self.assertIsNone(result["compile_check"]["cwd"])
        self.assertEqual("NOT_RUN", result["compile_check"]["integrity_status"])
        self.assertEqual({}, result["compile_check"]["integrity_changes"])

    def test_compile_setup_failure_is_a_structured_gate_failure(self) -> None:
        _, run_dir, unit = self.prepare("\\section{定义}\n该定义保持原有的逻辑结构。\n")
        rewrites = self.rewrite_dir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            json.dumps(
                self.voice_bound_bundle(
                    unit,
                    {
                        "decision": "NO_CHANGE",
                        "reason": "The definition already preserves the required structure.",
                    },
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with mock.patch.object(
            finalizer, "_run_compile", side_effect=OSError("job assignment failed")
        ):
            result = finalizer.finalize(
                run_dir,
                rewrites,
                check_command="compile-check",
                check_timeout_seconds=7.5,
            )

        compile_check = result["compile_check"]
        self.assert_compile_check_schema(compile_check)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("FAIL", compile_check["status"])
        self.assertEqual("UNAVAILABLE", compile_check["process_containment"])
        self.assertEqual("FAIL", compile_check["descendant_cleanup"])
        self.assertFalse(compile_check["timed_out"])
        self.assertEqual(7.5, compile_check["timeout_seconds"])
        self.assertIn("OSError: job assignment failed", compile_check["stderr"])


if __name__ == "__main__":
    unittest.main()
