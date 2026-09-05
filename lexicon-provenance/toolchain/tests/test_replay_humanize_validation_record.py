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


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
VALIDATOR_PATH = SKILL / "scripts" / "validate_humanize_output.py"
REPLAY_PATH = SKILL / "scripts" / "replay_humanize_validation_record.py"
COURSE_VOICE_FIXTURES = (
    Path(__file__).parent / "fixtures" / "humanize_course_voice_flattening"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("humanize_validator_v29_tests", VALIDATOR_PATH)
replayer = load_module("humanize_replayer_v29_tests", REPLAY_PATH)


class HumanizeValidationReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.before = self.root / "before.md"
        self.after = self.root / "after.md"
        self.before.write_text("值得注意的是，峰值出现在高温组。", encoding="utf-8")
        self.after.write_text("峰值出现在高温组。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def publish(
        self,
        evidence_dir: Path,
        *,
        before: Path | None = None,
        after: Path | None = None,
        extra: list[str] | None = None,
        expected_exit: int = 2,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        command = [
            sys.executable,
            str(VALIDATOR_PATH),
            str(before or self.before),
            str(after or self.after),
            "--scene",
            "RESEARCH",
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
        ]
        command.extend(extra or [])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(expected_exit, completed.returncode, completed.stderr)
        return completed, json.loads(completed.stdout)

    def replay_cli(self, evidence_dir: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPLAY_PATH),
                str(evidence_dir),
                "--format",
                "json",
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return completed, json.loads(completed.stdout)

    def replay_text(
        self,
        evidence_dir: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(REPLAY_PATH),
                str(evidence_dir),
                "--format",
                "text",
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )

    @staticmethod
    def tree_hashes(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): validator._sha256(path.read_bytes())
            for path in root.rglob("*")
            if path.is_file()
        }

    def template_field_scope(self, before: Path, *, name: str = "template-scope.json") -> Path:
        scope = self.root / name
        scope.write_bytes(
            validator._pretty_json_bytes(
                {
                    "schema_version": "humanize-template-field-edit-scope/v1",
                    "source_sha256": validator._sha256(before.read_bytes()),
                    "edits": [
                        {
                            "line": 1,
                            "label": "适用题目",
                            "permission": "PAYLOAD_ONLY",
                            "reason": "授权第1行适用题目的具体表达修复",
                        }
                    ],
                }
            )
        )
        return scope

    @staticmethod
    def refresh_manifest(root: Path, changed_path: str) -> None:
        manifest_path = root / "evidence-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = (root / changed_path).read_bytes()
        manifest["artifacts"][changed_path] = {
            "sha256": validator._sha256(raw),
            "size": len(raw),
        }
        identity = {
            "schema": manifest["schema"],
            "run_id": manifest["run_id"],
            "artifacts": manifest["artifacts"],
        }
        manifest["record_sha256"] = validator._sha256(
            validator._canonical_json_bytes(identity)
        )
        body = dict(manifest)
        body.pop("manifest_sha256", None)
        manifest["manifest_sha256"] = validator._sha256(
            validator._canonical_json_bytes(body)
        )
        manifest_path.write_bytes(validator._pretty_json_bytes(manifest))

    def test_supported_record_replays_from_archived_inputs(self) -> None:
        evidence = self.root / "evidence"
        _, original = self.publish(evidence)
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(
            0,
            completed.returncode,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        self.assertEqual("PASS", payload["replay_status"])
        self.assertEqual(0, payload["replay_exit_code"])
        self.assertEqual("PASS", payload["status"])
        self.assertEqual(
            "DEPRECATED_ALIAS_OF_REPLAY_STATUS",
            payload["status_compatibility"],
        )
        self.assertEqual("REVIEW", payload["recorded_delivery_gate_status"])
        self.assertEqual(2, payload["recorded_exit_code"])
        self.assertEqual("SELF_CONSISTENCY_ONLY", payload["scope"])
        self.assertEqual("SELF_CONSISTENCY_ONLY", payload["integrity_scope"])
        self.assertEqual("PASS", payload["record_integrity_status"])
        self.assertEqual("PASS", payload["reexecution_status"])
        self.assertEqual(original["evidence_bundle"]["run_id"], payload["run_id"])
        self.assertEqual("NOT_EVALUATED", payload["academic_correctness"])
        self.assertFalse(payload["paired_quality_clearance_granted"])
        self.assertFalse(payload["humanize_quality_claim_allowed"])

    def test_template_field_scope_is_bound_archived_and_replayed_offline(self) -> None:
        before = self.root / "template-before.md"
        after = self.root / "template-after.md"
        before.write_text(
            "适用题目： 积极的、普遍认可的趋势。\n",
            encoding="utf-8",
        )
        after.write_text(
            "适用题目： 积极且普遍受到认可的趋势。\n",
            encoding="utf-8",
        )
        scope = self.template_field_scope(before)
        scope_raw = scope.read_bytes()
        evidence = self.root / "template-scope-evidence"

        _, original = self.publish(
            evidence,
            before=before,
            after=after,
            extra=[
                "--scene",
                "COURSE",
                "--template-field-edit-scope",
                str(scope),
            ],
        )

        invocation = json.loads(
            (evidence / "invocation-request.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (evidence / "evidence-manifest.json").read_text(encoding="utf-8")
        )
        scope_argument = invocation["arguments"]["template_field_edit_scope"]
        scope_input = invocation["inputs"]["template_field_edit_scope"]
        self.assertEqual("humanize-direct-validation-evidence/v5", manifest["schema"])
        self.assertEqual("humanize-validation-invocation/v4", invocation["schema"])
        self.assertTrue(invocation["run_id"].startswith("hvr4-"))
        self.assertEqual({"before", "after", "template_field_edit_scope"}, set(invocation["inputs"]))
        self.assertTrue(scope_argument["provided"])
        self.assertEqual("PAYLOAD_ONLY", scope_argument["permission_boundary"])
        self.assertFalse(scope_argument["local_clearance_supported"])
        self.assertEqual(validator._sha256(scope_raw), scope_argument["sha256"])
        self.assertEqual(scope_argument["sha256"], scope_input["sha256"])
        self.assertEqual(
            scope_raw,
            (evidence / "inputs" / "template-field-edit-scope.json").read_bytes(),
        )
        self.assertEqual("PASS", original["template_field_edit_scope_check"]["status"])
        self.assertEqual(
            "AUTHORIZED_PAYLOAD_ONLY",
            original["template_field_findings"][0]["authorization_status"],
        )

        before.unlink()
        after.unlink()
        scope.unlink()
        completed, replayed = self.replay_cli(evidence)

        self.assertEqual(
            0,
            completed.returncode,
            json.dumps(replayed, ensure_ascii=False, indent=2),
        )
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("PASS", replayed["reexecution_status"])
        self.assertEqual("NOT_REQUESTED", replayed["live_source_status"]["status"])

    def test_text_template_field_record_replays_exactly(self) -> None:
        before = self.root / "template-text-before.md"
        after = self.root / "template-text-after.md"
        before.write_text("适用题目： 积极的、普遍认可的趋势。\n", encoding="utf-8")
        after.write_text("适用题目： 积极且普遍受到认可的趋势。\n", encoding="utf-8")
        scope = self.template_field_scope(before, name="template-text-scope.json")
        evidence = self.root / "template-text-evidence"
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(before),
                str(after),
                "--scene",
                "COURSE",
                "--format",
                "text",
                "--template-field-edit-scope",
                str(scope),
                "--evidence-dir",
                str(evidence),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertIn("template_field_layer_status: PASS", completed.stdout)
        self.assertIn("template_field_edit_scope_check: PASS", completed.stdout)
        self.assertIn("template_field_findings: 1", completed.stdout)
        self.assertIn("authorization=AUTHORIZED_PAYLOAD_ONLY", completed.stdout)

        replayed, payload = self.replay_cli(evidence)
        self.assertEqual(
            0,
            replayed.returncode,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        self.assertEqual("PASS", payload["reexecution_status"])

    def test_template_field_scope_tamper_and_rehashed_forgery_are_rejected(self) -> None:
        before = self.root / "template-tamper-before.md"
        after = self.root / "template-tamper-after.md"
        before.write_text("适用题目： 积极的、普遍认可的趋势。\n", encoding="utf-8")
        after.write_text("适用题目： 积极且普遍受到认可的趋势。\n", encoding="utf-8")
        scope = self.template_field_scope(before, name="template-tamper-scope.json")
        evidence = self.root / "template-tamper-evidence"
        self.publish(
            evidence,
            before=before,
            after=after,
            extra=["--template-field-edit-scope", str(scope)],
        )

        tampered = self.root / "template-tampered-copy"
        shutil.copytree(evidence, tampered)
        archived_scope = tampered / "inputs" / "template-field-edit-scope.json"
        archived_scope.write_bytes(archived_scope.read_bytes() + b" ")
        completed, payload = self.replay_cli(tampered)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("ARTIFACT_HASH_MISMATCH", payload["error_code"])

        manifest, artifacts = replayer._load_record(evidence)
        baseline = json.loads(artifacts["invocation-request.json"].decode("utf-8"))

        def rebind(invocation: dict, forged_artifacts: dict[str, bytes]) -> tuple[dict, dict[str, bytes]]:
            body = dict(invocation)
            body.pop("invocation_sha256")
            body.pop("run_id")
            invocation_sha = validator._sha256(validator._canonical_json_bytes(body))
            invocation["invocation_sha256"] = invocation_sha
            invocation["run_id"] = f"hvr4-{invocation_sha}"
            rebound_manifest = dict(manifest)
            rebound_manifest["run_id"] = invocation["run_id"]
            rebound_manifest["invocation_request_sha256"] = invocation_sha
            rebound_artifacts = dict(forged_artifacts)
            rebound_artifacts["invocation-request.json"] = validator._pretty_json_bytes(
                invocation
            )
            return rebound_manifest, rebound_artifacts

        cases = []
        wrong_source = json.loads(json.dumps(baseline))
        wrong_source["arguments"]["template_field_edit_scope"]["source_sha256"] = "0" * 64
        cases.append(("source", wrong_source, dict(artifacts), "INPUT_BINDING_MISMATCH"))

        wrong_permission = json.loads(json.dumps(baseline))
        wrong_permission["arguments"]["template_field_edit_scope"]["permission_boundary"] = "HEADER_ALLOWED"
        cases.append(("permission", wrong_permission, dict(artifacts), "INVALID_ARGUMENT"))

        false_with_input = json.loads(json.dumps(baseline))
        false_with_input["arguments"]["template_field_edit_scope"] = {"provided": False}
        cases.append(("false-with-input", false_with_input, dict(artifacts), "INVALID_INPUT_SET"))

        wrong_line = json.loads(json.dumps(baseline))
        wrong_line_artifacts = dict(artifacts)
        wrong_line_scope = json.loads(
            wrong_line_artifacts["inputs/template-field-edit-scope.json"].decode("utf-8")
        )
        wrong_line_scope["edits"][0]["line"] = 2
        wrong_line_raw = validator._pretty_json_bytes(wrong_line_scope)
        wrong_line_artifacts["inputs/template-field-edit-scope.json"] = wrong_line_raw
        wrong_line_sha = validator._sha256(wrong_line_raw)
        wrong_line["arguments"]["template_field_edit_scope"]["sha256"] = wrong_line_sha
        wrong_line["inputs"]["template_field_edit_scope"]["sha256"] = wrong_line_sha
        wrong_line["inputs"]["template_field_edit_scope"]["size"] = len(wrong_line_raw)
        cases.append(("line", wrong_line, wrong_line_artifacts, "INPUT_BINDING_MISMATCH"))

        for name, invocation, forged_artifacts, expected_code in cases:
            with self.subTest(name=name):
                forged_manifest, rebound_artifacts = rebind(invocation, forged_artifacts)
                with self.assertRaises(replayer.ReplayError) as raised:
                    replayer._validate_invocation(forged_manifest, rebound_artifacts)
                self.assertEqual(expected_code, raised.exception.code)

    def test_report_and_template_scopes_replay_together(self) -> None:
        before = self.root / "combined-before.md"
        after = self.root / "combined-after.md"
        before_text = "适用题目： 积极的、普遍认可的趋势。值得注意的是，结果为 1。\n"
        before.write_text(before_text, encoding="utf-8")
        after.write_text(
            "适用题目： 积极且普遍受到认可的趋势。结果为 1。\n",
            encoding="utf-8",
        )
        template_scope = self.template_field_scope(before, name="combined-template-scope.json")
        report = self.root / "combined-report.html"
        report.write_text(
            '<!doctype html><html><meta charset="utf-8"><body><mark>'
            + before_text.strip()
            + "</mark></body></html>",
            encoding="utf-8",
        )
        report_scope_payload = validator.detector_scope.analyze_report(report, before)
        report_scope = self.root / "combined-report-scope.json"
        report_scope.write_bytes(validator._pretty_json_bytes(report_scope_payload))
        evidence = self.root / "combined-scope-evidence"

        self.publish(
            evidence,
            before=before,
            after=after,
            extra=[
                "--report-scope",
                str(report_scope),
                "--template-field-edit-scope",
                str(template_scope),
            ],
        )
        invocation = json.loads(
            (evidence / "invocation-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {
                "before",
                "after",
                "report_scope",
                "report",
                "template_field_edit_scope",
            },
            set(invocation["inputs"]),
        )

        before.unlink()
        after.unlink()
        report.unlink()
        report_scope.unlink()
        template_scope.unlink()
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(
            0,
            completed.returncode,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        self.assertEqual("PASS", payload["reexecution_status"])

    def test_legacy_invocations_use_their_published_policy_hash_set(self) -> None:
        legacy_policy_keys = {
            "validator_sha256",
            "invariant_checker_sha256",
            "scanner_sha256",
            "lexicon_sha256",
            "report_extractor_sha256",
            "runtime_contract_sha256",
        }
        self.assertEqual(legacy_policy_keys, replayer.LEGACY_POLICY_HASHES)

        before_raw = b"before"
        after_raw = b"after"

        def invocation_record(
            invocation_schema: str,
            evidence_schema: str,
            run_prefix: str,
        ) -> tuple[dict, dict[str, bytes]]:
            legacy_v1 = invocation_schema == "humanize-validation-invocation/v1"
            arguments = {
                "mode": "REWRITE",
                "scene": "GENERAL",
                "output_format": "json",
                "strict_speech_acts": False,
                "fragment_mode": False,
                "protected_terms": [],
                "keep_reasons": {},
                "warning_resolutions": {},
                "warning_review_request_sha256": None,
                "report_scope": {"provided": False},
            }
            if legacy_v1:
                arguments.update(
                    warning_reviewer_kind="NONE",
                    warning_reviewer_id_sha256=None,
                )

            def input_record(role: str, raw: bytes) -> dict:
                record = {
                    "archive_path": f"inputs/{role}.bin",
                    "original_suffix": ".md",
                    "sha256": replayer._sha256(raw),
                    "size": len(raw),
                }
                if legacy_v1:
                    record.update(
                        original_name=f"{role}.md",
                        original_path_sha256="0" * 64,
                    )
                return record

            body = {
                "schema": invocation_schema,
                "validator_entrypoint": "scripts/validate_humanize_output.py",
                "arguments": arguments,
                "inputs": {
                    "before": input_record("before", before_raw),
                    "after": input_record("after", after_raw),
                },
                "policy_hashes": {
                    key: "0" * 64 for key in sorted(legacy_policy_keys)
                },
                "expected": {
                    "delivery_gate_status": "REVIEW",
                    "exit_code": 2,
                    "paired_quality_review_request_sha256": "",
                },
                "reexecution": {"status": "SUPPORTED", "reasons": []},
                "privacy": (
                    {
                        "raw_warning_reviewer_id_archived": False,
                        "warning_reviewer_id_sha256": None,
                    }
                    if legacy_v1
                    else {
                        "reviewer_identifier_collected": False,
                        "stable_reviewer_pseudonym_archived": False,
                        "source_locator_archived": False,
                        "contains_unredacted_proposal_text": False,
                    }
                ),
            }
            invocation_sha = replayer._sha256(
                replayer._canonical_json_bytes(body)
            )
            invocation = {
                **body,
                "invocation_sha256": invocation_sha,
                "run_id": f"{run_prefix}-{invocation_sha}",
            }
            manifest = {
                "schema": evidence_schema,
                "run_id": invocation["run_id"],
                "invocation_request_sha256": invocation_sha,
            }
            artifacts = {
                "invocation-request.json": replayer._pretty_json_bytes(invocation),
                "inputs/before.bin": before_raw,
                "inputs/after.bin": after_raw,
            }
            return manifest, artifacts

        legacy_cases = (
            (
                "humanize-validation-invocation/v1",
                "humanize-direct-validation-evidence/v2",
                "hvr1",
            ),
            (
                "humanize-validation-invocation/v2",
                "humanize-direct-validation-evidence/v3",
                "hvr2",
            ),
        )
        for invocation_schema, evidence_schema, run_prefix in legacy_cases:
            with self.subTest(invocation_schema=invocation_schema):
                manifest, artifacts = invocation_record(
                    invocation_schema,
                    evidence_schema,
                    run_prefix,
                )
                invocation = replayer._validate_invocation(manifest, artifacts)
                self.assertEqual(invocation_schema, invocation["schema"])

        manifest, artifacts = invocation_record(
            "humanize-validation-invocation/v2",
            "humanize-direct-validation-evidence/v3",
            "hvr2",
        )
        invocation = json.loads(artifacts["invocation-request.json"])
        invocation["schema"] = "humanize-validation-invocation/v3"
        invocation["arguments"]["document_format"] = "markdown"
        body = dict(invocation)
        body.pop("invocation_sha256")
        body.pop("run_id")
        invocation_sha = replayer._sha256(replayer._canonical_json_bytes(body))
        invocation["invocation_sha256"] = invocation_sha
        invocation["run_id"] = f"hvr3-{invocation_sha}"
        artifacts["invocation-request.json"] = replayer._pretty_json_bytes(invocation)
        manifest.update(
            schema="humanize-direct-validation-evidence/v4",
            run_id=invocation["run_id"],
            invocation_request_sha256=invocation_sha,
        )
        with self.assertRaises(replayer.ReplayError) as raised:
            replayer._validate_invocation(manifest, artifacts)
        self.assertEqual("INVALID_SCHEMA", raised.exception.code)

    def test_impossible_recorded_status_exit_pairs_fail_before_reexecution(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        manifest, artifacts = replayer._load_record(evidence)
        baseline = json.loads(artifacts["invocation-request.json"].decode("utf-8"))
        invalid_pairs = (
            ("PASS", 1),
            ("PASS", 2),
            ("FAIL", 0),
            ("FAIL", 2),
            ("REVIEW", 0),
            ("REVIEW", 1),
        )

        for status, exit_code in invalid_pairs:
            with self.subTest(status=status, exit_code=exit_code):
                invocation = json.loads(json.dumps(baseline))
                invocation["expected"]["delivery_gate_status"] = status
                invocation["expected"]["exit_code"] = exit_code
                body = dict(invocation)
                body.pop("invocation_sha256")
                body.pop("run_id")
                invocation_sha = validator._sha256(
                    validator._canonical_json_bytes(body)
                )
                invocation["invocation_sha256"] = invocation_sha
                prefix = replayer.INVOCATION_SCHEMAS[invocation["schema"]][1]
                invocation["run_id"] = f"{prefix}-{invocation_sha}"
                forged_manifest = dict(manifest)
                forged_manifest["run_id"] = invocation["run_id"]
                forged_manifest["invocation_request_sha256"] = invocation_sha
                forged_artifacts = dict(artifacts)
                forged_artifacts["invocation-request.json"] = (
                    validator._pretty_json_bytes(invocation)
                )

                with self.assertRaises(replayer.ReplayError) as raised:
                    replayer._validate_invocation(forged_manifest, forged_artifacts)
                self.assertEqual("INVALID_EXPECTED_STATUS", raised.exception.code)

    def test_status_exit_helper_rejects_non_string_statuses_as_replay_errors(self) -> None:
        invalid_statuses = ([], {}, None, 0, True, ("PASS",))

        for status in invalid_statuses:
            with self.subTest(status=status):
                with self.assertRaises(replayer.ReplayError) as raised:
                    replayer._require_status_exit_pair(
                        status,
                        0,
                        code="INVALID_TEST_STATUS",
                        label="test delivery",
                    )
                self.assertEqual("INVALID_TEST_STATUS", raised.exception.code)

    def test_cli_structures_non_string_recorded_status_as_fail(self) -> None:
        for index, invalid_status in enumerate(([], {})):
            with self.subTest(status=invalid_status):
                evidence = self.root / f"malformed-status-{index}"
                self.publish(evidence)
                manifest_path = evidence / "evidence-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["delivery_gate_status"] = invalid_status
                body = dict(manifest)
                body.pop("manifest_sha256")
                manifest["manifest_sha256"] = validator._sha256(
                    validator._canonical_json_bytes(body)
                )
                manifest_path.write_bytes(validator._pretty_json_bytes(manifest))

                completed, payload = self.replay_cli(evidence)

                self.assertEqual(1, completed.returncode, completed.stderr)
                self.assertEqual("FAIL", payload["replay_status"])
                self.assertEqual(1, payload["replay_exit_code"])
                self.assertEqual("FAIL", payload["status"])
                self.assertEqual(1, payload["exit_code"])
                self.assertIsNone(payload["recorded_delivery_gate_status"])
                self.assertIsNone(payload["recorded_exit_code"])
                self.assertEqual("RESULT_STATUS_MISMATCH", payload["error_code"])
                self.assertEqual("FAIL", payload["record_integrity_status"])
                self.assertEqual("NOT_RUN", payload["reexecution_status"])

    def test_text_output_names_replay_and_exposes_recorded_review(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)

        completed = self.replay_text(evidence)

        self.assertEqual(0, completed.returncode, completed.stderr)
        lines = completed.stdout.splitlines()
        self.assertEqual(
            [
                "replay_status: PASS",
                "scope: SELF_CONSISTENCY_ONLY",
                "recorded_delivery_gate_status: REVIEW",
                "recorded_exit_code: 2",
                "replay_exit_code: 0",
            ],
            lines[:5],
        )
        self.assertFalse(
            any(line.startswith("status:") for line in lines),
            completed.stdout,
        )

    def test_text_record_with_finding_replays_without_absolute_path_drift(self) -> None:
        before = self.root / "research_before.md"
        after = self.root / "research_after.md"
        before.write_text("本段讨论已有结果。", encoding="utf-8")
        after.write_text("本段为后续研究提供了基础。", encoding="utf-8")
        evidence = self.root / "text-evidence"
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(before),
                str(after),
                "--scene",
                "RESEARCH",
                "--format",
                "text",
                "--evidence-dir",
                str(evidence),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertIn("after:", completed.stdout)
        self.assertNotIn(str(self.root), completed.stdout)
        replayed, payload = self.replay_cli(evidence)
        self.assertEqual(0, replayed.returncode, json.dumps(payload, ensure_ascii=False))
        self.assertEqual("PASS", payload["reexecution_status"])

    def test_text_record_with_paired_style_spans_replays_exactly(self) -> None:
        evidence = self.root / "paired-style-text-evidence"
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                str(COURSE_VOICE_FIXTURES / "blind_before.tex"),
                str(COURSE_VOICE_FIXTURES / "blind_after.tex"),
                "--scene",
                "COURSE",
                "--format",
                "text",
                "--evidence-dir",
                str(evidence),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertIn("paired_style_delta_findings: 1", completed.stdout)
        self.assertIn("paired-style-span: COURSE-FLAT-", completed.stdout)

        replayed, payload = self.replay_cli(evidence)

        self.assertEqual(0, replayed.returncode, json.dumps(payload, ensure_ascii=False))
        self.assertEqual("PASS", payload["record_integrity_status"])
        self.assertEqual("PASS", payload["reexecution_status"])

    def test_identical_publication_is_idempotent_and_byte_preserving(self) -> None:
        evidence = self.root / "evidence"
        _, first = self.publish(evidence)
        before_hashes = self.tree_hashes(evidence)
        _, second = self.publish(evidence)
        self.assertEqual(first, second)
        self.assertEqual(before_hashes, self.tree_hashes(evidence))

    def test_same_invocation_has_same_run_id_and_config_change_has_new_id(self) -> None:
        _, first = self.publish(self.root / "evidence-a")
        _, second = self.publish(self.root / "evidence-b")
        self.assertEqual(
            first["evidence_bundle"]["run_id"],
            second["evidence_bundle"]["run_id"],
        )
        _, changed = self.publish(
            self.root / "evidence-c",
            extra=["--scene", "COURSE"],
        )
        self.assertNotEqual(
            first["evidence_bundle"]["run_id"],
            changed["evidence_bundle"]["run_id"],
        )

    def test_existing_directory_with_different_invocation_is_conflict(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        initial = self.tree_hashes(evidence)
        completed, payload = self.publish(
            evidence,
            extra=["--scene", "COURSE"],
            expected_exit=1,
        )
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("EVIDENCE_PERSISTENCE_FAILED", payload["error_code"])
        self.assertIn("conflict", payload["error"])
        self.assertEqual(initial, self.tree_hashes(evidence))
        self.assertEqual("", completed.stderr)

    def test_each_bound_artifact_tamper_fails_before_reexecution(self) -> None:
        source = self.root / "source-evidence"
        self.publish(source)
        paths = [
            "inputs/before.bin",
            "inputs/after.bin",
            "invocation-request.json",
            "validation-result.json",
            "paired-quality-review-request.json",
            "rendered-output.txt",
            "stderr.txt",
            "execution-record.json",
            "evidence-manifest.json",
        ]
        for index, relative in enumerate(paths):
            with self.subTest(relative=relative):
                tampered = self.root / f"tampered-{index}"
                shutil.copytree(source, tampered)
                path = tampered / relative
                path.write_bytes(path.read_bytes() + b"X")
                completed, payload = self.replay_cli(tampered)
                self.assertEqual(1, completed.returncode)
                self.assertEqual("FAIL", payload["replay_status"])
                self.assertEqual(1, payload["replay_exit_code"])
                self.assertEqual("FAIL", payload["status"])
                self.assertIsNone(payload["recorded_delivery_gate_status"])
                self.assertIsNone(payload["recorded_exit_code"])
                self.assertEqual("SELF_CONSISTENCY_ONLY", payload["scope"])
                self.assertEqual(
                    "DEPRECATED_ALIAS_OF_REPLAY_STATUS",
                    payload["status_compatibility"],
                )
                self.assertEqual("NOT_RUN", payload["reexecution_status"])

    def test_rehashed_result_tamper_still_fails_cross_artifact_binding(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        result_path = evidence / "validation-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["delivery_gate_status"] = "PASS"
        result_path.write_bytes(validator._pretty_json_bytes(result))
        self.refresh_manifest(evidence, "validation-result.json")
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("RESULT_STATUS_MISMATCH", payload["error_code"])

    def test_rehashed_stdout_tamper_still_fails_result_consistency(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        output = evidence / "rendered-output.txt"
        output.write_bytes(output.read_bytes().replace(b'"status": "REVIEW"', b'"status": "PASS__"'))
        self.refresh_manifest(evidence, "rendered-output.txt")
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("STDOUT_RESULT_MISMATCH", payload["error_code"])

    def test_extra_file_is_rejected(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        (evidence / "unbound.txt").write_text("extra", encoding="utf-8")
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("RECORD_INVENTORY_MISMATCH", payload["error_code"])

    def test_hardlinked_record_file_is_rejected(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        try:
            os.link(
                evidence / "validation-result.json",
                self.root / "result-hardlink.json",
            )
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        completed, payload = self.replay_cli(evidence)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("HARDLINK_REJECTED", payload["error_code"])

    def test_policy_drift_is_review_not_false_replay_pass(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        manifest, artifacts = replayer._load_record(evidence)
        invocation = replayer._validate_invocation(manifest, artifacts)
        changed = dict(invocation["policy_hashes"])
        changed["validator_sha256"] = "0" * 64
        with mock.patch.object(replayer, "_current_policy_hashes", return_value=changed):
            payload, exit_code = replayer.replay_record(evidence)
        self.assertEqual(2, exit_code)
        self.assertEqual("REVIEW", payload["replay_status"])
        self.assertEqual(2, payload["replay_exit_code"])
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual("REVIEW", payload["recorded_delivery_gate_status"])
        self.assertEqual(2, payload["recorded_exit_code"])
        self.assertEqual("SELF_CONSISTENCY_ONLY", payload["scope"])
        self.assertEqual("PASS", payload["record_integrity_status"])
        self.assertEqual("NOT_RUN", payload["reexecution_status"])
        self.assertEqual(["POLICY_DRIFT"], payload["reexecution_reasons"])

    def test_rehashed_invocation_unknown_field_and_path_injection_are_rejected(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        manifest, artifacts = replayer._load_record(evidence)
        baseline = json.loads(artifacts["invocation-request.json"].decode("utf-8"))
        cases = (
            ("unknown", lambda item: item["arguments"].update({"hidden_override": True}), "INVALID_SCHEMA"),
            (
                "path",
                lambda item: item["inputs"]["before"].update(
                    {"archive_path": "../inputs/before.bin"}
                ),
                "UNSAFE_ARTIFACT_PATH",
            ),
            (
                "suffix",
                lambda item: item["inputs"]["before"].update(
                    {"original_suffix": ".md/../../escape"}
                ),
                "INVALID_INPUT_SUFFIX",
            ),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                invocation = json.loads(json.dumps(baseline))
                mutate(invocation)
                body = dict(invocation)
                body.pop("invocation_sha256")
                body.pop("run_id")
                invocation_sha = validator._sha256(
                    validator._canonical_json_bytes(body)
                )
                invocation["invocation_sha256"] = invocation_sha
                prefix = replayer.INVOCATION_SCHEMAS[invocation["schema"]][1]
                invocation["run_id"] = f"{prefix}-{invocation_sha}"
                forged_manifest = dict(manifest)
                forged_manifest["run_id"] = invocation["run_id"]
                forged_manifest["invocation_request_sha256"] = invocation_sha
                forged_artifacts = dict(artifacts)
                forged_artifacts["invocation-request.json"] = validator._pretty_json_bytes(
                    invocation
                )
                with self.assertRaises(replayer.ReplayError) as raised:
                    replayer._validate_invocation(forged_manifest, forged_artifacts)
                self.assertEqual(expected_code, raised.exception.code)

    def test_live_source_drift_does_not_change_archive_but_can_be_required(self) -> None:
        evidence = self.root / "evidence"
        self.publish(evidence)
        self.before.write_text("来源已在记录之后改变。", encoding="utf-8")
        payload, exit_code = replayer.replay_record(
            evidence,
            live_before=self.before,
            live_after=self.after,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("NOT_CURRENT", payload["live_source_status"]["status"])
        strict_payload, strict_exit = replayer.replay_record(
            evidence,
            require_live_source_match=True,
            live_before=self.before,
            live_after=self.after,
        )
        self.assertEqual(2, strict_exit)
        self.assertEqual("REVIEW", strict_payload["status"])
        self.assertEqual("PASS", strict_payload["reexecution_status"])

    def test_report_scope_and_report_are_archived_for_offline_replay(self) -> None:
        before = self.root / "report-before.md"
        after = self.root / "report-after.md"
        before.write_text("前文不动。值得注意的是，结果为 1。后文不动。", encoding="utf-8")
        after.write_text("前文不动。结果为 1。后文不动。", encoding="utf-8")
        report = self.root / "report.html"
        report.write_text(
            '<!doctype html><html><meta charset="utf-8"><body>'
            "<mark>值得注意的是，结果为 1。</mark></body></html>",
            encoding="utf-8",
        )
        scope_payload = validator.detector_scope.analyze_report(report, before)
        scope = self.root / "report-scope.json"
        scope.write_bytes(validator._pretty_json_bytes(scope_payload))
        evidence = self.root / "report-evidence"
        _, payload = self.publish(
            evidence,
            before=before,
            after=after,
            extra=["--report-scope", str(scope)],
        )
        request = payload["paired_quality_review_request"]
        self.assertEqual("REPORT_SELECTION", request["validation_context"]["document_scope"])
        self.assertIn("report_scope_binding", request["validation_context"])
        self.assertTrue((evidence / "inputs" / "report-scope.json").is_file())
        self.assertTrue((evidence / "inputs" / "report.bin").is_file())
        before.unlink()
        after.unlink()
        report.unlink()
        scope.unlink()
        completed, replayed = self.replay_cli(evidence)
        self.assertEqual(
            0,
            completed.returncode,
            json.dumps(replayed, ensure_ascii=False, indent=2),
        )
        self.assertEqual("PASS", replayed["reexecution_status"])
        self.assertEqual("NOT_REQUESTED", replayed["live_source_status"]["status"])

    def test_identity_free_proposal_is_replayable_but_never_clears_review(self) -> None:
        before = self.root / "warning-before.md"
        after = self.root / "warning-after.md"
        before.write_text("结果可能变化。", encoding="utf-8")
        after.write_text("结果发生变化。", encoding="utf-8")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        evidence = self.root / "warning-evidence"
        self.publish(
            evidence,
            before=before,
            after=after,
            extra=[
                "--scene",
                "GENERAL",
                "--propose-warning-resolution",
                f"{fingerprint}=人工建议恢复原句中的模态范围以保留表达功能",
                "--warning-review-request-sha256",
                request["request_sha256"],
            ],
        )
        invocation = json.loads(
            (evidence / "invocation-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual("SUPPORTED", invocation["reexecution"]["status"])
        self.assertFalse(invocation["privacy"]["reviewer_identifier_collected"])
        self.assertFalse(invocation["privacy"]["stable_reviewer_pseudonym_archived"])
        completed, replayed = self.replay_cli(evidence)
        self.assertEqual(0, completed.returncode)
        self.assertEqual("PASS", replayed["status"])
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("PASS", replayed["reexecution_status"])
        self.assertFalse(replayed["humanize_quality_claim_allowed"])

    def test_draft_terms_and_fragment_configuration_are_replayable(self) -> None:
        supplied = self.root / "supplied.md"
        draft = self.root / "draft.md"
        supplied.write_text("材料 A 的结果为 1。", encoding="utf-8")
        draft.write_text("材料 A 的结果为 1。", encoding="utf-8")
        draft_evidence = self.root / "draft-evidence"
        self.publish(
            draft_evidence,
            before=supplied,
            after=draft,
            extra=["--mode", "DRAFT", "--term", "材料 A"],
            expected_exit=0,
        )
        completed, payload = self.replay_cli(draft_evidence)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("PASS", payload["reexecution_status"])

        fragment_before = self.root / "fragment-before.tex"
        fragment_after = self.root / "fragment-after.tex"
        fragment_before.write_text("值得注意的是，结果为 1。\\end{solution}", encoding="utf-8")
        fragment_after.write_text("结果为 1。\\end{solution}", encoding="utf-8")
        fragment_evidence = self.root / "fragment-evidence"
        self.publish(
            fragment_evidence,
            before=fragment_before,
            after=fragment_after,
            extra=["--fragment", "--strict-speech-acts"],
        )
        completed, payload = self.replay_cli(fragment_evidence)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("PASS", payload["reexecution_status"])

    def test_explicit_tex_format_on_txt_is_bound_and_replayed(self) -> None:
        before = self.root / "neutral-before.txt"
        after = self.root / "neutral-after.txt"
        before.write_text("值得注意的是，结果为 1。\n", encoding="utf-8")
        after.write_text("结果为 1。\n", encoding="utf-8")
        evidence = self.root / "neutral-tex-evidence"

        _completed, original = self.publish(
            evidence,
            before=before,
            after=after,
            extra=["--document-format", "tex"],
        )
        invocation = json.loads(
            (evidence / "invocation-request.json").read_text(encoding="utf-8")
        )
        completed, replayed = self.replay_cli(evidence)

        self.assertEqual("tex", original["evidence"]["document_format"])
        self.assertEqual("humanize-validation-invocation/v4", invocation["schema"])
        self.assertEqual("tex", invocation["arguments"]["document_format"])
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("PASS", replayed["reexecution_status"])


if __name__ == "__main__":
    unittest.main()
