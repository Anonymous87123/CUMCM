import hashlib
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
CAPTURE_PATH = SKILL / "scripts" / "capture_humanize_validation.py"
CAPTURE_REPLAY_PATH = SKILL / "scripts" / "replay_humanize_validation_capture.py"
VALIDATOR_PATH = SKILL / "scripts" / "validate_humanize_output.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture = load_module("humanize_capture_v29_tests", CAPTURE_PATH)
capture_replay = load_module("humanize_capture_replay_v29_tests", CAPTURE_REPLAY_PATH)
validator = load_module("humanize_capture_validator_v29_tests", VALIDATOR_PATH)


class HumanizeValidationCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "captures"
        self.before = self.root / "before.md"
        self.after = self.root / "after.md"
        self.before.write_text("值得注意的是，峰值出现在高温组。", encoding="utf-8")
        self.after.write_text("峰值出现在高温组。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_capture_help_is_a_real_cli_help_path(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CAPTURE_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(0, completed.returncode)
        self.assertIn("--output-root", completed.stdout)
        self.assertIn("-- <validator-arguments>", completed.stdout)
        self.assertIn("Required invocation form:", completed.stdout)
        self.assertIn(
            "python scripts/capture_humanize_validation.py",
            completed.stdout,
        )
        self.assertIn("before.md after.md --scene GENERAL --format json", completed.stdout)
        self.assertNotIn("MISSING_VALIDATOR_SEPARATOR", completed.stdout)

    def test_validator_rejects_long_option_abbreviations(self) -> None:
        cases = (
            "--evidence-d=PRIVATE",
            "--warning-reviewer-i=ALICE",
            "--report-s=PRIVATE",
            "--propose-warning-r=fp=SECRET",
        )
        for token in cases:
            with self.subTest(token=token):
                with self.assertRaises(SystemExit) as raised:
                    validator.build_parser().parse_args(
                        [str(self.before), str(self.after), token]
                    )
                self.assertEqual(2, raised.exception.code)

    def test_capture_rejects_unknown_or_abbreviated_validator_options(self) -> None:
        cases = (
            [str(self.before), str(self.after), "--evidence-d=PRIVATE"],
            [str(self.before), str(self.after), "--warning-reviewer-i", "ALICE"],
            [str(self.before), str(self.after), "--report-s", "PRIVATE"],
            [str(self.before), str(self.after), "--propose-warning-r=fp=SECRET"],
            [str(self.before), str(self.after), "--unknown=SECRET"],
            [str(self.before), str(self.after), "--unknown", "SECRET"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(capture.CaptureError) as raised:
                    capture._argument_layout(arguments)
                self.assertEqual("UNKNOWN_VALIDATOR_OPTION", raised.exception.code)
                self.assertNotIn(arguments[-1], str(raised.exception))

    def test_capture_rejects_unsafe_layout_before_creating_a_record(self) -> None:
        cases = (
            (
                [str(self.before), str(self.after), "--warning-reviewer-i", "ALICE"],
                "UNKNOWN_VALIDATOR_OPTION",
                "ALICE",
            ),
            (
                [str(self.before), str(self.after), "--report-s=PRIVATE_SCOPE"],
                "UNKNOWN_VALIDATOR_OPTION",
                "PRIVATE_SCOPE",
            ),
            (
                [str(self.before), str(self.after), "PRIVATE_THIRD.md"],
                "INVALID_VALIDATOR_POSITIONAL_COUNT",
                "PRIVATE_THIRD.md",
            ),
            (
                [str(self.before), "--term", "PRIVATE_AFTER.md"],
                "INVALID_VALIDATOR_POSITIONAL_COUNT",
                "PRIVATE_AFTER.md",
            ),
            (
                [str(self.before), "--term=PRIVATE_AFTER_EQUALS.md"],
                "INVALID_VALIDATOR_POSITIONAL_COUNT",
                "PRIVATE_AFTER_EQUALS.md",
            ),
            (
                ["--help"],
                "INVALID_VALIDATOR_POSITIONAL_COUNT",
                "--help",
            ),
            (
                [
                    str(self.before),
                    str(self.after),
                    "--term",
                    "--warning-reviewer-id",
                    "ALICE",
                ],
                "MISSING_VALIDATOR_OPTION_VALUE",
                "ALICE",
            ),
        )
        for index, (arguments, error_code, private_value) in enumerate(cases):
            with self.subTest(arguments=arguments):
                output = self.root / f"rejected-{index}-{private_value}"
                _completed, payload = self.run_capture(
                    arguments,
                    expected_exit=1,
                    output=output,
                )
                self.assertEqual(error_code, payload["error_code"])
                self.assertNotIn(private_value, json.dumps(payload, ensure_ascii=False))
                self.assertFalse(output.exists())

    def test_exact_caller_evidence_directory_remains_specifically_rejected(self) -> None:
        output = self.root / "caller-evidence-rejected"
        _completed, payload = self.run_capture(
            [
                str(self.before),
                str(self.after),
                "--evidence-dir",
                "PRIVATE_EVIDENCE",
            ],
            expected_exit=1,
            output=output,
        )
        self.assertEqual("CALLER_EVIDENCE_DIR_REJECTED", payload["error_code"])
        self.assertNotIn("PRIVATE_EVIDENCE", json.dumps(payload, ensure_ascii=False))
        self.assertFalse(output.exists())

    def test_capture_parent_parser_rejects_abbreviations(self) -> None:
        cases = (
            ["--output-r", str(self.output)],
            ["--output-root", str(self.output), "--capture-f=text"],
            ["--he"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit) as raised:
                    capture._capture_argument_parser().parse_args(arguments)
                self.assertEqual(2, raised.exception.code)

    def run_capture(
        self,
        validator_args: list[str] | None = None,
        *,
        expected_exit: int | None = None,
        output: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = (
            [str(self.before), str(self.after), "--scene", "RESEARCH", "--format", "json"]
            if validator_args is None
            else validator_args
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(CAPTURE_PATH),
                "--output-root",
                str(output or self.output),
                "--capture-format",
                "json",
                "--",
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        payload = json.loads(completed.stdout)
        if expected_exit is not None:
            self.assertEqual(
                expected_exit,
                completed.returncode,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        return completed, payload

    def replay(self, record: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = subprocess.run(
            [
                sys.executable,
                str(CAPTURE_REPLAY_PATH),
                str(record),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return completed, json.loads(completed.stdout)

    @staticmethod
    def tree_bytes(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def refresh_manifest(record: Path) -> None:
        manifest_path = record / "capture-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = {}
        for path in record.rglob("*"):
            if not path.is_file() or path == manifest_path:
                continue
            raw = path.read_bytes()
            records[path.relative_to(record).as_posix()] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        manifest["artifacts"] = dict(sorted(records.items()))
        identity = {"schema": manifest["schema"], "artifacts": manifest["artifacts"]}
        record_sha = hashlib.sha256(capture._canonical_json_bytes(identity)).hexdigest()
        manifest["record_sha256"] = record_sha
        manifest["capture_id"] = f"hvc1-{record_sha}"
        body = dict(manifest)
        body.pop("manifest_sha256", None)
        manifest["manifest_sha256"] = hashlib.sha256(
            capture._canonical_json_bytes(body)
        ).hexdigest()
        manifest_path.write_bytes(capture._pretty_json_bytes(manifest))

    def template_field_scope(
        self,
        before: Path,
        *,
        name: str = "template-field-edit-scope.json",
        source_sha256: str | None = None,
    ) -> Path:
        scope = self.root / name
        scope.write_bytes(
            validator._pretty_json_bytes(
                {
                    "schema_version": "humanize-template-field-edit-scope/v1",
                    "source_sha256": (
                        source_sha256
                        if source_sha256 is not None
                        else validator._sha256(before.read_bytes())
                    ),
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

    def test_template_field_scope_is_isolated_for_both_cli_forms(self) -> None:
        scope = self.template_field_scope(self.before)
        scope_raw = scope.read_bytes()
        cases = (
            (
                "separate",
                [
                    str(self.before),
                    str(self.after),
                    "--template-field-edit-scope",
                    str(scope),
                ],
                3,
            ),
            (
                "equals",
                [
                    str(self.before),
                    str(self.after),
                    f"--template-field-edit-scope={scope}",
                ],
                2,
            ),
        )
        for name, arguments, scope_position in cases:
            with self.subTest(name=name):
                launch_dir = self.root / f"launch-{name}"
                launch_dir.mkdir()
                child, private_tokens = capture._prepare_child_arguments(
                    arguments,
                    launch_dir,
                )

                self.assertEqual(str(launch_dir / "before.md"), child[0])
                self.assertEqual(str(launch_dir / "after.md"), child[1])
                self.assertEqual(self.before.read_bytes(), Path(child[0]).read_bytes())
                self.assertEqual(self.after.read_bytes(), Path(child[1]).read_bytes())
                isolated_scope_token = child[scope_position]
                isolated_scope_value = (
                    isolated_scope_token.split("=", 1)[1]
                    if isolated_scope_token.startswith(
                        "--template-field-edit-scope="
                    )
                    else isolated_scope_token
                )
                self.assertEqual(
                    str(launch_dir / "template-field-edit-scope.json"),
                    isolated_scope_value,
                )
                self.assertEqual(scope_raw, Path(isolated_scope_value).read_bytes())
                self.assertFalse(
                    any(
                        token == str(scope) or token.endswith(f"={scope}")
                        for token in child
                    )
                )
                self.assertIn(str(scope).encode("utf-8"), private_tokens)

    def test_template_field_scope_capture_replays_inner_and_parent_offline(self) -> None:
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
        scope = self.template_field_scope(before, name="offline-template-scope.json")
        scope_raw = scope.read_bytes()
        _, payload = self.run_capture(
            [
                str(before),
                str(after),
                "--scene",
                "COURSE",
                "--format",
                "json",
                "--template-field-edit-scope",
                str(scope),
            ],
            expected_exit=2,
            output=self.root / "template-scope-captures",
        )
        record = Path(payload["capture_record"])
        inner_dir = record / "validation-record"
        manifest = json.loads(
            (inner_dir / "evidence-manifest.json").read_text(encoding="utf-8")
        )
        invocation = json.loads(
            (inner_dir / "invocation-request.json").read_text(encoding="utf-8")
        )

        self.assertEqual("humanize-direct-validation-evidence/v5", manifest["schema"])
        self.assertEqual("humanize-validation-invocation/v4", invocation["schema"])
        self.assertTrue(invocation["run_id"].startswith("hvr4-"))
        self.assertEqual(
            {"before", "after", "template_field_edit_scope"},
            set(invocation["inputs"]),
        )
        self.assertTrue(
            invocation["arguments"]["template_field_edit_scope"]["provided"]
        )
        self.assertEqual(
            scope_raw,
            (inner_dir / "inputs" / "template-field-edit-scope.json").read_bytes(),
        )

        inner_payload, inner_exit = capture.inner_replay.replay_record(inner_dir)
        self.assertEqual(0, inner_exit)
        self.assertEqual("PASS", inner_payload["record_integrity_status"])
        self.assertEqual("PASS", inner_payload["reexecution_status"])

        before.unlink()
        after.unlink()
        scope.unlink()
        completed, replayed = self.replay(record)
        self.assertEqual(
            2,
            completed.returncode,
            json.dumps(replayed, ensure_ascii=False, indent=2),
        )
        self.assertEqual("REVIEW", replayed["status"])
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("PASS", replayed["capture_integrity_status"])
        self.assertEqual("PASS", replayed["reexecution_status"])
        self.assertEqual("PASS", replayed["parent_observation_binding_status"])

    def test_template_field_scope_tamper_is_rejected_by_parent_replay(self) -> None:
        before = self.root / "tamper-template-before.md"
        after = self.root / "tamper-template-after.md"
        before.write_text("适用题目： 积极的、普遍认可的趋势。\n", encoding="utf-8")
        after.write_text("适用题目： 积极且普遍受到认可的趋势。\n", encoding="utf-8")
        scope = self.template_field_scope(before, name="tamper-template-scope.json")
        _, payload = self.run_capture(
            [
                str(before),
                str(after),
                "--scene",
                "COURSE",
                "--format",
                "json",
                "--template-field-edit-scope",
                str(scope),
            ],
            expected_exit=2,
            output=self.root / "template-tamper-captures",
        )
        source = Path(payload["capture_record"])
        tampered = self.root / "tampered-template-capture" / source.name
        shutil.copytree(source, tampered)
        archived_scope = (
            tampered
            / "validation-record"
            / "inputs"
            / "template-field-edit-scope.json"
        )
        archived_scope.write_bytes(archived_scope.read_bytes() + b" ")

        completed, replayed = self.replay(tampered)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("ARTIFACT_HASH_MISMATCH", replayed["error_code"])

    def test_template_field_scope_with_wrong_source_binding_is_rejected(self) -> None:
        before = self.root / "wrong-source-template-before.md"
        after = self.root / "wrong-source-template-after.md"
        before.write_text("适用题目： 积极的、普遍认可的趋势。\n", encoding="utf-8")
        after.write_text("适用题目： 积极且普遍受到认可的趋势。\n", encoding="utf-8")
        scope = self.template_field_scope(
            before,
            name="wrong-source-template-scope.json",
            source_sha256="0" * 64,
        )
        _, payload = self.run_capture(
            [
                str(before),
                str(after),
                "--scene",
                "COURSE",
                "--format",
                "json",
                "--template-field-edit-scope",
                str(scope),
            ],
            expected_exit=1,
            output=self.root / "wrong-source-template-captures",
        )
        record = Path(payload["capture_record"])
        observation = json.loads(
            (record / "process-observation.json").read_text(encoding="utf-8")
        )
        child_payload = json.loads(
            (record / "observed-stdout.bin").read_text(encoding="utf-8")
        )

        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("FAIL", payload["capture_integrity_status"])
        self.assertEqual(1, payload["observed_os_exit_code"])
        self.assertEqual("NOT_AVAILABLE", payload["validation_delivery_gate_status"])
        self.assertEqual("ABSENT", observation["inner_record"]["record_status"])
        self.assertIn(
            "INNER_VALIDATION_RECORD_NOT_AVAILABLE",
            observation["failure_reasons"],
        )
        self.assertEqual("INPUT_CONTRACT_INVALID", child_payload["error_code"])
        self.assertFalse((record / "validation-record").exists())

        completed, replayed = self.replay(record)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", replayed["status"])
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("FAIL", replayed["capture_integrity_status"])
        self.assertEqual("NOT_RUN", replayed["reexecution_status"])

    def test_review_exit_is_observed_and_not_upgraded_to_capture_pass(self) -> None:
        _completed, payload = self.run_capture(expected_exit=2)
        record = Path(payload["capture_record"])
        observation = json.loads(
            (record / "process-observation.json").read_text(encoding="utf-8")
        )
        inner = json.loads(
            (record / "validation-record" / "validation-result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("PASS", payload["capture_integrity_status"])
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(2, payload["observed_os_exit_code"])
        self.assertEqual(2, observation["observed_os_exit_code"])
        self.assertEqual(2, inner["exit_code"])
        self.assertEqual(
            (record / "observed-stdout.bin").read_bytes(),
            (record / "validation-record" / "rendered-output.txt").read_bytes(),
        )
        replayed, replay_payload = self.replay(record)
        self.assertEqual(2, replayed.returncode)
        self.assertEqual("REVIEW", replay_payload["status"])
        self.assertEqual("PASS", replay_payload["reexecution_status"])
        self.assertFalse(replay_payload["humanize_quality_claim_allowed"])

    def test_draft_pass_and_hard_failure_both_preserve_validator_gate(self) -> None:
        supplied = self.root / "supplied.md"
        draft = self.root / "draft.md"
        supplied.write_text("材料 A 的结果为 1。", encoding="utf-8")
        draft.write_text("材料 A 的结果为 1。", encoding="utf-8")
        _, passed = self.run_capture(
            [str(supplied), str(draft), "--mode", "DRAFT", "--format", "json"],
            expected_exit=0,
            output=self.root / "draft-captures",
        )
        self.assertEqual("PASS", passed["status"])
        self.assertEqual("PASS", passed["capture_integrity_status"])

        hard_before = self.root / "hard-before.tex"
        hard_after = self.root / "hard-after.tex"
        hard_before.write_text("公式为 $x=1$。", encoding="utf-8")
        hard_after.write_text("公式为 $x=2$。", encoding="utf-8")
        _, failed = self.run_capture(
            [str(hard_before), str(hard_after), "--format", "json"],
            expected_exit=1,
            output=self.root / "hard-captures",
        )
        self.assertEqual("FAIL", failed["status"])
        self.assertEqual("PASS", failed["capture_integrity_status"])
        self.assertEqual(1, failed["observed_os_exit_code"])

    def test_missing_positionals_are_rejected_before_output_creation(self) -> None:
        output = self.root / "missing-positionals"
        _completed, payload = self.run_capture([], expected_exit=1, output=output)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual(
            "INVALID_VALIDATOR_POSITIONAL_COUNT",
            payload["error_code"],
        )
        self.assertFalse(output.exists())

    def test_unexpected_io_errors_use_path_free_structured_messages(self) -> None:
        private_root = r"C:\private-project\confidential"
        private_name = "PRIVATE_SOURCE.tex"
        cases = (
            PermissionError(13, "Permission denied", f"{private_root}\\{private_name}"),
            OSError(5, "Access is denied", f"{private_root}\\{private_name}"),
        )
        for error in cases:
            with self.subTest(error_type=type(error).__name__):
                payload = capture._error_payload(error)
                serialized = json.dumps(payload, ensure_ascii=False)
                self.assertEqual("CAPTURE_IO_ERROR", payload["error_code"])
                self.assertEqual(
                    "capture failed during a filesystem or process operation",
                    payload["error"],
                )
                self.assertNotIn(private_root, serialized)
                self.assertNotIn(private_name, serialized)
                self.assertNotIn("Permission denied", serialized)
                self.assertNotIn("Access is denied", serialized)

    def test_missing_and_invalid_utf8_inputs_are_captured_without_source_locator(self) -> None:
        cases: list[tuple[str, Path]] = []
        missing = self.root / "private-project-name" / "missing.md"
        cases.append(("missing", missing))
        invalid = self.root / "private-project-name" / "invalid.md"
        invalid.parent.mkdir()
        invalid.write_bytes(b"\xff\xfe")
        cases.append(("invalid", invalid))
        for index, (name, after) in enumerate(cases):
            with self.subTest(name=name):
                _, payload = self.run_capture(
                    [str(self.before), str(after), "--format", "json"],
                    expected_exit=1,
                    output=self.root / f"error-captures-{index}",
                )
                record = Path(payload["capture_record"])
                all_bytes = b"\n".join(self.tree_bytes(record).values())
                self.assertEqual(1, payload["observed_os_exit_code"])
                self.assertNotIn(str(after).encode("utf-8"), all_bytes)
                self.assertNotIn(after.name.encode("utf-8"), all_bytes)
                self.assertNotIn(
                    hashlib.sha256(str(after).encode("utf-8")).hexdigest().encode("ascii"),
                    all_bytes,
                )

    def test_anonymous_request_bound_proposal_replays_without_human_identity(self) -> None:
        before = self.root / "warning-before.md"
        after = self.root / "warning-after.md"
        before.write_text("结果可能变化。", encoding="utf-8")
        after.write_text("结果发生变化。", encoding="utf-8")
        first = validator.validate(before, after, scene="GENERAL")
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        _, payload = self.run_capture(
            [
                str(before),
                str(after),
                "--scene",
                "GENERAL",
                "--format",
                "json",
                "--propose-warning-resolution",
                f"{fingerprint}=调用方建议恢复原句中的模态范围以保留表达功能",
                "--warning-review-request-sha256",
                request["request_sha256"],
            ],
            expected_exit=2,
            output=self.root / "proposal-captures",
        )
        record = Path(payload["capture_record"])
        result = json.loads(
            (record / "validation-record" / "validation-result.json").read_text(
                encoding="utf-8"
            )
        )
        proposal = result["warning_proposal_state"]
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["reviewer_identifier_collected"])
        self.assertNotIn("warning_review", result)
        replayed, replay_payload = self.replay(record)
        self.assertEqual(2, replayed.returncode)
        self.assertEqual("PASS", replay_payload["reexecution_status"])
        self.assertEqual("REVIEW", replay_payload["status"])

    def test_retired_reviewer_label_and_plain_hash_never_enter_capture_tree(self) -> None:
        label = "alice"
        _, payload = self.run_capture(
            [
                str(self.before),
                str(self.after),
                "--warning-reviewer-kind",
                "HUMAN",
                "--warning-reviewer-id",
                label,
            ],
            expected_exit=1,
            output=self.root / "retired-identity-captures",
        )
        record = Path(payload["capture_record"])
        all_bytes = b"\n".join(self.tree_bytes(record).values())
        self.assertNotIn(label.encode("utf-8"), all_bytes)
        self.assertNotIn(hashlib.sha256(label.encode()).hexdigest().encode(), all_bytes)
        self.assertNotIn(b"reviewer_id_sha256", all_bytes)

    def test_same_content_in_different_private_directories_has_identical_record(self) -> None:
        first_dir = self.root / "alice-project"
        second_dir = self.root / "bob-project"
        first_dir.mkdir()
        second_dir.mkdir()
        for directory in (first_dir, second_dir):
            (directory / "named-before.md").write_bytes(self.before.read_bytes())
            (directory / "named-after.md").write_bytes(self.after.read_bytes())
        _, first = self.run_capture(
            [
                str(first_dir / "named-before.md"),
                str(first_dir / "named-after.md"),
                "--scene",
                "RESEARCH",
                "--format",
                "json",
            ],
            expected_exit=2,
            output=self.root / "cross-path-a",
        )
        _, second = self.run_capture(
            [
                str(second_dir / "named-before.md"),
                str(second_dir / "named-after.md"),
                "--scene",
                "RESEARCH",
                "--format",
                "json",
            ],
            expected_exit=2,
            output=self.root / "cross-path-b",
        )
        self.assertEqual(first["capture_id"], second["capture_id"])
        self.assertEqual(
            self.tree_bytes(Path(first["capture_record"])),
            self.tree_bytes(Path(second["capture_record"])),
        )

    def test_identical_capture_is_idempotent_and_byte_preserving(self) -> None:
        _, first = self.run_capture(expected_exit=2)
        record = Path(first["capture_record"])
        baseline = self.tree_bytes(record)
        _, second = self.run_capture(expected_exit=2)
        self.assertEqual(first["capture_id"], second["capture_id"])
        self.assertEqual("IDEMPOTENT_REPLAY", second["publication_status"])
        self.assertEqual(baseline, self.tree_bytes(record))

    def test_existing_lock_is_not_deleted_by_failed_publisher(self) -> None:
        _, first = self.run_capture(expected_exit=2)
        record = Path(first["capture_record"])
        lock = record.parent / f".{first['capture_id']}.publish.lock"
        lock.write_bytes(b"foreign-owner-sentinel")
        _completed, failed = self.run_capture(expected_exit=1)
        self.assertEqual("CAPTURE_IO_ERROR", failed["error_code"])
        self.assertEqual(b"foreign-owner-sentinel", lock.read_bytes())

    def test_extra_empty_directory_and_hardlink_are_rejected(self) -> None:
        _, payload = self.run_capture(expected_exit=2)
        source = Path(payload["capture_record"])
        with_extra = self.root / source.name
        shutil.copytree(source, with_extra)
        (with_extra / "extra-empty").mkdir()
        completed, replayed = self.replay(with_extra)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("CAPTURE_INVENTORY_MISMATCH", replayed["error_code"])

        hardlinked = self.root / "hardlinked" / source.name
        shutil.copytree(source, hardlinked)
        try:
            os.link(
                hardlinked / "observed-stdout.bin",
                self.root / "stdout-hardlink.bin",
            )
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        completed, replayed = self.replay(hardlinked)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("HARDLINK_REJECTED", replayed["error_code"])

    def test_artifact_tamper_and_rehashed_manifest_status_forgery_fail(self) -> None:
        _, payload = self.run_capture(expected_exit=2)
        source = Path(payload["capture_record"])
        tampered = self.root / "tampered" / source.name
        shutil.copytree(source, tampered)
        stream = tampered / "observed-stdout.bin"
        stream.write_bytes(stream.read_bytes() + b"X")
        completed, replayed = self.replay(tampered)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("ARTIFACT_HASH_MISMATCH", replayed["error_code"])

        forged = self.root / "forged" / source.name
        shutil.copytree(source, forged)
        manifest_path = forged / "capture-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "PASS"
        manifest["exit_code"] = 0
        body = dict(manifest)
        body.pop("manifest_sha256")
        manifest["manifest_sha256"] = hashlib.sha256(
            capture._canonical_json_bytes(body)
        ).hexdigest()
        manifest_path.write_bytes(capture._pretty_json_bytes(manifest))
        completed, replayed = self.replay(forged)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("CAPTURE_INTEGRITY_MISMATCH", replayed["error_code"])

    def test_policy_drift_is_review_and_does_not_reexecute(self) -> None:
        _, payload = self.run_capture(expected_exit=2)
        record = Path(payload["capture_record"])
        current = capture._capture_policy_hashes()
        changed = json.loads(json.dumps(current))
        changed["capture_script_sha256"] = "0" * 64
        with mock.patch.object(capture_replay.capture, "_capture_policy_hashes", return_value=changed):
            replayed, exit_code = capture_replay.replay_capture(record)
        self.assertEqual(2, exit_code)
        self.assertEqual("REVIEW", replayed["status"])
        self.assertEqual("PASS", replayed["record_integrity_status"])
        self.assertEqual("NOT_RUN", replayed["reexecution_status"])

    def test_timeout_observation_is_fail_and_has_no_fake_delivery_status(self) -> None:
        def fake_run(
            _arguments,
            *,
            inner_dir,
            stdout_path,
            stderr_path,
            timeout_seconds,
        ):
            del inner_dir, timeout_seconds
            stdout_path.write_bytes(b"partial")
            stderr_path.write_bytes(b"")
            return {
                "termination_reason": "TIMEOUT",
                "observed_os_exit_code": None,
                "process_returncode_after_termination": 1,
            }

        with mock.patch.object(capture, "_run_validator", side_effect=fake_run):
            payload, exit_code = capture.capture_validation(
                [str(self.before), str(self.after)],
                output_root=self.root / "timeout-captures",
            )
        self.assertEqual(1, exit_code)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("NOT_AVAILABLE", payload["validation_delivery_gate_status"])

    def test_output_inside_installed_skill_is_rejected(self) -> None:
        with self.assertRaisesRegex(capture.CaptureError, "must not pollute"):
            capture.capture_validation(
                [str(self.before), str(self.after)],
                output_root=SKILL / "build" / "forbidden-capture",
            )


if __name__ == "__main__":
    unittest.main()
