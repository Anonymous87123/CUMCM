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
SCRIPT = SKILL / "scripts" / "run_humanize_inline.py"
SPEC = importlib.util.spec_from_file_location("run_humanize_inline", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
inline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inline
SPEC.loader.exec_module(inline)


class HumanizeInlineRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output_root = self.root / "runs"
        self.before = self.root / "source.md"
        self.after = self.root / "candidate.md"
        self.before.write_text(
            "值得注意的是，峰值出现在高温组。\n", encoding="utf-8"
        )
        self.after.write_text("峰值出现在高温组。\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_candidate(self, *, visible_output: str = "BODY_WITH_SUMMARY"):
        return inline.run_inline(
            self.before,
            self.after,
            output_root=self.output_root,
            mode="REWRITE",
            scene="RESEARCH",
            document_format="markdown",
            visible_output=visible_output,
        )

    def test_run_materializes_unique_artifacts_and_preserves_top_level_review(self) -> None:
        first, first_dir = self.run_candidate()
        second, second_dir = self.run_candidate()
        verification, body = inline.verify_run(first_dir)

        self.assertNotEqual(first_dir, second_dir)
        self.assertEqual("humanize-inline-run/v2", first["schema_version"])
        self.assertEqual("humanize-inline-verification/v2", verification["schema_version"])
        self.assertEqual("INLINE_TEXT", first["source_kind"])
        self.assertEqual("VALIDATED", first["execution_status"])
        self.assertEqual("PASS", first["mechanical_validation_status"])
        self.assertEqual("REVIEW", first["delivery_gate_status"])
        self.assertEqual(2, first["exit_code"])
        self.assertFalse(first["completion_claim_allowed"])
        self.assertTrue(first["body_emission_allowed"])
        self.assertEqual("NOT_EVALUATED", verification["chat_transport_byte_identity_status"])
        self.assertEqual(self.after.read_bytes(), body)
        self.assertTrue((first_dir / "evidence" / "evidence-manifest.json").is_file())
        self.assertEqual(
            self.before.read_bytes(),
            (first_dir / first["artifacts"]["before"]["path"]).read_bytes(),
        )
        self.assertEqual(
            self.after.read_bytes(),
            (first_dir / first["artifacts"]["after"]["path"]).read_bytes(),
        )

    def test_body_only_hides_audit_display_but_still_creates_evidence(self) -> None:
        record, run_dir = self.run_candidate(visible_output="BODY_ONLY")

        self.assertEqual("BODY_ONLY", record["visible_output"])
        self.assertTrue(
            record["response_contract"][
                "body_only_hides_audit_display_not_audit_execution"
            ]
        )
        self.assertEqual("VALIDATED", record["execution_status"])
        self.assertTrue((run_dir / "validation.json").is_file())
        self.assertTrue((run_dir / "evidence" / "evidence-manifest.json").is_file())

    def test_emit_body_rechecks_and_returns_exact_validated_bytes(self) -> None:
        _record, run_dir = self.run_candidate(visible_output="BODY_ONLY")

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "emit", str(run_dir), "--format", "body"],
            check=False,
            capture_output=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertEqual(self.after.read_bytes(), completed.stdout)
        self.assertEqual(b"", completed.stderr)
        self.assertNotIn(b"delivery_gate_status", completed.stdout)

    def test_post_validation_mutation_blocks_body_emission(self) -> None:
        record, run_dir = self.run_candidate(visible_output="BODY_ONLY")
        frozen_after = run_dir / record["artifacts"]["after"]["path"]
        frozen_after.write_text("峰值位置发生了变化。\n", encoding="utf-8")

        verification, body = inline.verify_run(run_dir)

        self.assertEqual("FAIL", verification["status"])
        self.assertEqual(1, verification["exit_code"])
        self.assertEqual("FAIL", verification["delivery_gate_status"])
        self.assertFalse(verification["body_emission_allowed"])
        self.assertIn("artifact_sha256_mismatch:after", verification["reason"])
        self.assertIsNone(body)

    def test_validator_not_started_is_honest_not_run_review(self) -> None:
        record, run_dir = inline.run_inline(
            self.before,
            self.after,
            output_root=self.output_root,
            mode="REWRITE",
            scene="RESEARCH",
            document_format="markdown",
            visible_output="BODY_ONLY",
            validator_path=self.root / "missing-validator.py",
        )

        self.assertEqual("NOT_RUN", record["execution_status"])
        self.assertEqual("NOT_RUN", record["mechanical_validation_status"])
        self.assertEqual("REVIEW", record["delivery_gate_status"])
        self.assertEqual(2, record["exit_code"])
        self.assertFalse(record["body_emission_allowed"])
        validation = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
        self.assertFalse(validation["evidence"]["checker_executed"])
        self.assertFalse(
            (run_dir / record["artifacts"]["evidence_manifest"]["path"]).exists()
        )

    def test_tampered_validation_record_fails_closed(self) -> None:
        record, run_dir = self.run_candidate()
        validation_path = run_dir / record["artifacts"]["validation"]["path"]
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        payload["delivery_gate_status"] = "PASS"
        validation_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        verification, body = inline.verify_run(run_dir)

        self.assertEqual("FAIL", verification["status"])
        self.assertFalse(verification["body_emission_allowed"])
        self.assertIsNone(body)

    def test_tampered_invocation_record_fails_closed(self) -> None:
        record, run_dir = self.run_candidate()
        invocation_path = run_dir / record["artifacts"]["invocation"]["path"]
        payload = json.loads(invocation_path.read_text(encoding="utf-8"))
        payload["scene"] = "GENERAL"
        invocation_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        verification, body = inline.verify_run(run_dir)

        self.assertEqual("FAIL", verification["status"])
        self.assertIn("artifact_sha256_mismatch:invocation", verification["reason"])
        self.assertIsNone(body)

    def test_tampered_evidence_manifest_fails_closed(self) -> None:
        record, run_dir = self.run_candidate()
        manifest_path = run_dir / record["artifacts"]["evidence_manifest"]["path"]
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["scene"] = "GENERAL"
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        verification, body = inline.verify_run(run_dir)

        self.assertEqual("FAIL", verification["status"])
        self.assertIn("artifact_sha256_mismatch:evidence_manifest", verification["reason"])
        self.assertIsNone(body)

    def test_tampered_evidence_child_artifact_fails_closed(self) -> None:
        _record, run_dir = self.run_candidate()
        (run_dir / "evidence" / "inputs" / "after.bin").write_bytes(
            "被篡改的证据。\n".encode("utf-8")
        )

        verification, body = inline.verify_run(run_dir)

        self.assertEqual("FAIL", verification["status"])
        self.assertIn("evidence_artifact_hash_mismatch:inputs/after.bin", verification["reason"])
        self.assertIsNone(body)

    def test_unmanifested_evidence_file_or_directory_fails_closed(self) -> None:
        for extra_kind in ("file", "directory"):
            with self.subTest(extra_kind=extra_kind):
                _record, run_dir = self.run_candidate()
                extra = run_dir / "evidence" / f"unexpected-{extra_kind}"
                if extra_kind == "file":
                    extra.write_text("unexpected", encoding="utf-8")
                else:
                    extra.mkdir()

                verification, body = inline.verify_run(run_dir)

                self.assertEqual("FAIL", verification["status"])
                self.assertIn("evidence_inventory_mismatch", verification["reason"])
                self.assertIsNone(body)

    def test_validator_payload_cross_field_inconsistency_is_rejected(self) -> None:
        record, run_dir = self.run_candidate()
        validation = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
        arguments = {
            "process_exit_code": record["validator_process_exit_code"],
            "before_sha256": record["artifacts"]["before"]["sha256"],
            "after_sha256": record["artifacts"]["after"]["sha256"],
            "mode": record["mode"],
            "scene": record["scene"],
        }
        cases = (
            ("status", "PASS", "validator_status_delivery_mismatch"),
            (
                "delivery_gate_exit_code",
                0,
                "validator_delivery_exit_code_mismatch",
            ),
            ("scene", "GENERAL", "validator_invocation_context_mismatch"),
        )
        for field, value, reason in cases:
            with self.subTest(field=field):
                candidate = json.loads(json.dumps(validation, ensure_ascii=False))
                candidate[field] = value
                with self.assertRaisesRegex(inline.InlineRunError, reason):
                    inline._validate_payload(candidate, **arguments)

    def test_compact_diagnostics_expose_actionable_codes(self) -> None:
        diagnostics = inline._summarize_validation(
            {
                "mechanical_validation_status": "FAIL",
                "review_reasons": ["hard_invariant_failed"],
                "invariants": {
                    "errors": [{"code": "NUMBER_OR_UNIT_CHANGED"}]
                },
                "warnings_without_resolution_proposal": [
                    {"code": "SPEECH_ACT_REPORTING_OBSERVATION_CHANGED"}
                ],
                "unexplained_high_findings": [{"signal_id": "LEX-META-01"}],
                "introduced_findings": [{"signal_id": "LEX-BRIDGE-02"}],
            }
        )

        self.assertEqual("STOP_HARD_FAILURE", diagnostics["next_action"])
        self.assertEqual(
            ["NUMBER_OR_UNIT_CHANGED"], diagnostics["hard_error_codes"]
        )
        self.assertEqual(
            ["SPEECH_ACT_REPORTING_OBSERVATION_CHANGED"],
            diagnostics["pending_warning_codes"],
        )
        self.assertEqual(["LEX-META-01"], diagnostics["unexplained_high_signal_ids"])
        self.assertEqual(["LEX-BRIDGE-02"], diagnostics["introduced_signal_ids"])

    def test_tampered_diagnostics_or_response_contract_fails_closed(self) -> None:
        for field in ("diagnostics", "response_contract"):
            with self.subTest(field=field):
                _record, run_dir = self.run_candidate()
                record_path = run_dir / "run.json"
                payload = json.loads(record_path.read_text(encoding="utf-8"))
                if field == "diagnostics":
                    payload[field]["next_action"] = "UNTRUSTED_ACTION"
                else:
                    payload[field]["chat_transport_byte_identity_status"] = "PASS"
                record_path.write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

                verification, body = inline.verify_run(run_dir)

                self.assertEqual("FAIL", verification["status"])
                self.assertIsNone(body)

    def test_visible_body_attestation_passes_only_for_exact_bytes(self) -> None:
        _record, run_dir = self.run_candidate(visible_output="BODY_ONLY")
        visible = self.root / "visible-response.md"
        visible.write_bytes(self.after.read_bytes())

        attestation = inline.attest_visible_body(run_dir, visible)

        self.assertEqual("humanize-visible-delivery-attestation/v1", attestation["schema_version"])
        self.assertEqual("PASS", attestation["attestation_status"])
        self.assertEqual(0, attestation["exit_code"])
        self.assertTrue(attestation["byte_identity"])
        self.assertEqual("REVIEW", attestation["candidate_delivery_gate_status"])
        self.assertEqual(2, attestation["candidate_delivery_gate_exit_code"])
        self.assertFalse(attestation["candidate_completion_claim_allowed"])
        self.assertEqual(
            "CALLER_SUPPLIED_RESPONSE_BYTES_ONLY", attestation["attestation_scope"]
        )
        self.assertEqual(
            "NOT_EVALUATED", attestation["chat_transport_byte_identity_status"]
        )
        self.assertEqual("NOT_EVALUATED", attestation["ui_rendering_status"])

    def test_visible_body_attestation_detects_dropped_terminal_newline(self) -> None:
        _record, run_dir = self.run_candidate(visible_output="BODY_ONLY")
        visible = self.root / "visible-response.md"
        visible.write_text("峰值出现在高温组。", encoding="utf-8")

        attestation = inline.attest_visible_body(run_dir, visible)

        self.assertEqual("FAIL", attestation["attestation_status"])
        self.assertEqual(1, attestation["exit_code"])
        self.assertFalse(attestation["byte_identity"])
        self.assertFalse(attestation["terminal_line_ending_matches"])
        self.assertNotEqual(
            attestation["expected_sha256"], attestation["observed_sha256"]
        )

    def test_attest_cli_reports_exact_file_scope_without_quality_claim(self) -> None:
        _record, run_dir = self.run_candidate(visible_output="BODY_ONLY")
        visible = self.root / "visible-response.md"
        visible.write_bytes(self.after.read_bytes())

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "attest", str(run_dir), str(visible)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(0, completed.returncode)
        self.assertEqual("PASS", payload["attestation_status"])
        self.assertTrue(payload["byte_identity"])
        self.assertFalse(payload["candidate_completion_claim_allowed"])
        self.assertEqual("NOT_EVALUATED", payload["chat_transport_byte_identity_status"])

    def test_draft_can_emit_mechanically_clear_candidate_without_quality_claim(self) -> None:
        self.before.write_text(
            "低温组误差小于高温组。两组峰值位置接近。\n", encoding="utf-8"
        )
        self.after.write_text(
            "低温组误差小于高温组，两组峰值位置接近。\n", encoding="utf-8"
        )

        record, run_dir = inline.run_inline(
            self.before,
            self.after,
            output_root=self.output_root,
            mode="DRAFT",
            scene="RESEARCH",
            document_format="markdown",
            visible_output="BODY_ONLY",
        )
        verification, body = inline.verify_run(run_dir)

        self.assertEqual("PASS", record["mechanical_validation_status"])
        self.assertEqual("REVIEW", record["delivery_gate_status"])
        self.assertEqual(2, record["exit_code"])
        self.assertFalse(record["humanize_quality_claim_allowed"])
        self.assertTrue(record["body_emission_allowed"])
        self.assertEqual("PASS", verification["status"])
        self.assertEqual(self.after.read_bytes(), body)

    def test_tex_candidate_preserves_formula_and_emits_exact_bytes(self) -> None:
        self.before = self.root / "source.tex"
        self.after = self.root / "candidate.tex"
        self.before.write_text(
            "值得注意的是，关系为 \\(E=mc^2\\)。\n", encoding="utf-8"
        )
        self.after.write_text("关系为 \\(E=mc^2\\)。\n", encoding="utf-8")

        record, run_dir = inline.run_inline(
            self.before,
            self.after,
            output_root=self.output_root,
            mode="REWRITE",
            scene="RESEARCH",
            document_format="tex",
            visible_output="BODY_ONLY",
        )
        verification, body = inline.verify_run(run_dir)

        self.assertEqual("PASS", record["mechanical_validation_status"])
        self.assertEqual("REVIEW", record["delivery_gate_status"])
        self.assertEqual(self.after.read_bytes(), body)

    def test_cli_run_reports_run_directory_without_claiming_completion(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "run",
                str(self.before),
                str(self.after),
                "--output-root",
                str(self.output_root),
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "markdown",
                "--visible-output",
                "BODY_ONLY",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("PASS", payload["mechanical_validation_status"])
        self.assertEqual("REVIEW", payload["delivery_gate_status"])
        self.assertFalse(payload["completion_claim_allowed"])
        self.assertTrue(Path(payload["run_dir"]).is_dir())


if __name__ == "__main__":
    unittest.main()
