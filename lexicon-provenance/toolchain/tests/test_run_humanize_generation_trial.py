import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
SCRIPT = SKILL / "scripts" / "run_humanize_generation_trial.py"
SPEC = importlib.util.spec_from_file_location("run_humanize_generation_trial", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FakeAuditor:
    GENERATION_RUN_RECORD_SCHEMA = "humanize-generation-run-record/v2"
    BLINDNESS_ATTESTATION = "CALLER_ATTESTED_STAGED_CONTEXT"

    @staticmethod
    def _skill_snapshot(root: Path):
        entries = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                entries.append((path.relative_to(root).as_posix(), sha256(path.read_bytes())))
        return sha256(json.dumps(entries).encode("utf-8")), entries


class HumanizeGenerationTrialRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_case(
        self,
        *,
        case_id: str = "CASE-001",
        input_text: str = "值得注意的是，峰值出现在高温组。",
        prompt_text: str = "请直接改写为自然的科研正文，只输出正文。",
    ) -> Path:
        case = self.root / "public"
        case.mkdir()
        input_raw = input_text.encode("utf-8")
        prompt_raw = prompt_text.encode("utf-8")
        (case / "input.md").write_bytes(input_raw)
        (case / "prompt.txt").write_bytes(prompt_raw)
        public_context = {
            "schema_version": runner.PUBLIC_CONTEXT_SCHEMA,
            "mode": "REWRITE",
            "scene": "RESEARCH",
            "intensity": "BALANCED",
            "output": "CLEAN",
            "report_context": "NONE",
            "scope": "selection",
            "title_lock": True,
            "structure_lock": False,
            "task_options": {},
        }
        public_context_raw = json.dumps(
            public_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        (case / "public-context.json").write_bytes(public_context_raw)
        manifest = {
            "schema_version": runner.PUBLIC_SCHEMA,
            "case_id": case_id,
            "input": {"path": "input.md", "sha256": sha256(input_raw)},
            "prompt": {"path": "prompt.txt", "sha256": sha256(prompt_raw)},
            "public_context": {
                "path": "public-context.json",
                "sha256": sha256(public_context_raw),
            },
        }
        manifest_raw = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        (case / "public-manifest.json").write_bytes(manifest_raw)
        seal = {
            "schema_version": runner.PUBLIC_SEAL_SCHEMA,
            "case_id": case_id,
            "public_manifest_sha256": sha256(manifest_raw),
            "artifact_sha256": {
                "input": sha256(input_raw),
                "prompt": sha256(prompt_raw),
                "public_context": sha256(public_context_raw),
            },
        }
        (case / "public-seal.json").write_text(
            json.dumps(seal, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        return case

    def copied_skill(self) -> Path:
        target = self.root / "humanize-academic-chinese"
        shutil.copytree(
            SKILL,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        return target

    def binding_pair(self, skill: Path) -> tuple[FakeAuditor, dict[str, str]]:
        return FakeAuditor(), {
            "skill_snapshot_sha256": FakeAuditor._skill_snapshot(skill)[0],
            "contract_sha256": "b" * 64,
            "requirements_sha256": "c" * 64,
            "oracle_catalog_sha256": "d" * 64,
            "trust_policy_sha256": "e" * 64,
        }

    @staticmethod
    def successful_invocation(command, mutation=None):
        if mutation is not None:
            mutation(Path(command[command.index("-C") + 1]))
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text("峰值出现在高温组。", encoding="utf-8")
        return runner.Invocation(
            command=tuple(command),
            pid=31415,
            returncode=0,
            stdout=b'{"request_id":"req-1","turn_id":"turn-1"}\n',
            stderr=b"",
            timed_out=False,
            started_at="2026-07-14T00:00:00Z",
            ended_at="2026-07-14T00:00:01Z",
        )

    def test_sealed_public_case_loads(self) -> None:
        case = runner.load_public_case(self.make_case())
        self.assertEqual("CASE-001", case.case_id)
        self.assertEqual("input.md", case.input_path.name)
        self.assertRegex(case.seal_sha256, r"^[0-9a-f]{64}$")

    def test_public_case_rejects_unsealed_extra_file(self) -> None:
        case = self.make_case()
        (case / "prior-output.md").write_text("旧结果", encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "unsealed extra"):
            runner.load_public_case(case)

    def test_public_case_rejects_atom_id_leakage(self) -> None:
        case = self.make_case(prompt_text="请完成 MODE-02 并让断言通过。")
        with self.assertRaisesRegex(runner.RunnerError, "leaks qualification atom"):
            runner.load_public_case(case)

    def test_public_case_rejects_non_numeric_and_hidden_catalog_ids(self) -> None:
        for text in (
            "请完成 PROTECTED/hash-zero/v1。",
            "请运行 measurement/PROTECTED/hash-zero/v1。",
            "请套用 PATH-05/positive/v1。",
        ):
            with self.subTest(text=text):
                case = self.make_case(case_id="CASE-" + sha256(text.encode())[:8], prompt_text=text)
                with self.assertRaisesRegex(
                    runner.RunnerError, "qualification (?:atom ID|identifier)"
                ):
                    runner.load_public_case(case)
                shutil.rmtree(case)

    def test_public_leak_check_rejects_composite_gold_filename(self) -> None:
        path = self.root / "gold-answer.md"
        path.write_text("中性正文。", encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "oracle vocabulary"):
            runner._public_leak_check("CASE-001", [path])

    def test_public_case_rejects_hash_drift(self) -> None:
        case = self.make_case()
        (case / "input.md").write_text("被替换", encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "hash does not match"):
            runner.load_public_case(case)

    def test_public_case_rejects_path_escape(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("正文", encoding="utf-8")
        case = self.make_case()
        manifest_path = case / "public-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["input"] = {"path": "../outside.md", "sha256": sha256(outside.read_bytes())}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "escapes"):
            runner.load_public_case(case)

    def test_public_case_rejects_duplicate_manifest_key(self) -> None:
        case = self.make_case()
        raw = (case / "public-manifest.json").read_text(encoding="utf-8")
        duplicate = raw[:-1] + ',"case_id":"CASE-002"}'
        (case / "public-manifest.json").write_text(duplicate, encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "duplicate JSON key"):
            runner.load_public_case(case)

    def test_public_case_rejects_caller_expected_answer_param(self) -> None:
        case = self.make_case()
        context_path = case / "public-context.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))
        context["task_options"]["expected_answer"] = "删除第一句"
        context_raw = json.dumps(
            context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        context_path.write_bytes(context_raw)
        manifest_path = case / "public-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["public_context"]["sha256"] = sha256(context_raw)
        manifest_raw = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest_path.write_bytes(manifest_raw)
        seal_path = case / "public-seal.json"
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        seal["public_manifest_sha256"] = sha256(manifest_raw)
        seal["artifact_sha256"]["public_context"] = sha256(context_raw)
        seal_path.write_text(json.dumps(seal), encoding="utf-8")
        with self.assertRaisesRegex(runner.RunnerError, "task_options has unknown fields"):
            runner.load_public_case(case)

    def test_event_stream_must_be_strict_jsonl(self) -> None:
        with self.assertRaisesRegex(runner.RunnerError, "event 2 is invalid"):
            runner._event_ids(b'{"request_id":"req-1"}\nnot-json\n')
        with self.assertRaisesRegex(runner.RunnerError, "duplicate JSON key"):
            runner._event_ids(
                b'{"request_id":"req-1","request_id":"req-2"}\n'
            )
        with self.assertRaisesRegex(runner.RunnerError, "non-finite JSON number"):
            runner._event_observation_summary(b'{"type":"turn.started","value":NaN}\n')

    def test_event_observation_distinguishes_reconnect_from_item_warning(self) -> None:
        raw = (
            b'{"type":"thread.started"}\n'
            b'{"type":"turn.started"}\n'
            b'{"type":"item.completed","item":{"type":"error","message":"budget warning"}}\n'
            b'{"type":"error","message":"Reconnecting... 2/5 (request timed out)"}\n'
        )
        summary = runner._event_observation_summary(raw)
        self.assertTrue(summary["thread_started"])
        self.assertTrue(summary["turn_started"])
        self.assertEqual(1, summary["reconnect_count"])
        self.assertEqual(["budget warning"], summary["item_error_messages"])
        self.assertEqual("error", summary["last_event_type"])

    def test_invoke_timeout_terminates_descendant_pipe_holders_promptly(self) -> None:
        child_code = "import time; time.sleep(8)"
        parent_code = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c',sys.argv[1]]); "
            "time.sleep(8)"
        )
        started = time.monotonic()

        invocation = runner._invoke_codex(
            [sys.executable, "-c", parent_code, child_code],
            b"",
            os.environ,
            1,
        )

        elapsed = time.monotonic() - started
        self.assertTrue(invocation.timed_out)
        self.assertLess(elapsed, 5.0)
        self.assertNotEqual("NONE", invocation.termination_method)

    def test_context_never_claims_verified_filesystem_isolation(self) -> None:
        case = runner.load_public_case(self.make_case())
        payload = runner._context_payload(
            case,
            "gpt-5",
            ["PATH"],
            "codex-cli test",
        )
        self.assertEqual(
            "UNVERIFIED_LOCAL_READ_ONLY",
            payload["execution_boundary"]["filesystem_enforcement"],
        )
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("qualification_bindings", rendered)
        self.assertNotIn("oracle_catalog", rendered)

    def test_runner_has_no_full_skill_snapshot_copy_path(self) -> None:
        self.assertFalse(hasattr(runner, "_copy_skill_snapshot"))

    def test_effective_prompt_carries_sealed_params_and_locks(self) -> None:
        case = runner.load_public_case(self.make_case())
        prompt = runner._effective_prompt(
            case.prompt_path.read_text(encoding="utf-8"),
            case.input_path.name,
            case.params,
            case.locks,
            case.task_options,
        )
        self.assertIn('"mode":"REWRITE"', prompt)
        self.assertIn('"scene":"RESEARCH"', prompt)
        self.assertIn('"title_lock":true', prompt)
        self.assertNotIn(str(case.root), prompt)
        self.assertNotIn("tests", prompt)
        self.assertNotIn("gold", prompt)
        self.assertNotIn("qualification", prompt)
        self.assertNotIn("evaluator", prompt)

    def test_runner_owns_output_receipt_and_e2_run_record(self) -> None:
        case = self.make_case()
        output = self.root / "run"
        skill = self.root / "skill"
        skill.mkdir()
        skill_snapshot_sha256 = FakeAuditor._skill_snapshot(skill)[0]
        bindings = {
            "skill_snapshot_sha256": skill_snapshot_sha256,
            "contract_sha256": "b" * 64,
            "requirements_sha256": "c" * 64,
            "oracle_catalog_sha256": "d" * 64,
            "trust_policy_sha256": "e" * 64,
        }

        class FakeProjectionBuilder:
            class ProjectionError(ValueError):
                pass

            @staticmethod
            def verify_projection(
                _root: Path,
                manifest: dict,
                **_kwargs: object,
            ) -> dict:
                if manifest["projection_tree_sha256"] != "f" * 64:
                    raise FakeProjectionBuilder.ProjectionError("tree drift")
                return {"projection_tree_sha256": "f" * 64, "files": 1}

            @staticmethod
            def build_projection(_source: Path, target: Path, manifest: Path) -> dict:
                target.mkdir(parents=True)
                (target / "SKILL.md").write_text("# fixture", encoding="utf-8")
                payload = {
                    "schema_version": "humanize-generator-projection-manifest/v2",
                    "projection_tree_sha256": "f" * 64,
                    "projection_policy": {"sha256": "1" * 64},
                    "builder": {"executable_sha256": "2" * 64},
                    "source": {
                        "inventory_sha256": "3" * 64,
                        "evaluation_surface_sha256": "4" * 64,
                    },
                }
                raw = json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                manifest.write_bytes(raw)
                return {**payload, "manifest_sha256": sha256(raw)}

        def fake_invoke(command, _prompt, _env, _timeout):
            output_path = Path(command[command.index("-o") + 1])
            output_path.write_text("峰值出现在高温组。", encoding="utf-8")
            return runner.Invocation(
                command=tuple(command),
                pid=31415,
                returncode=0,
                stdout=b'{"request_id":"req-1","turn_id":"turn-1"}\n',
                stderr=b"",
                timed_out=False,
                started_at="2026-07-14T00:00:00Z",
                ended_at="2026-07-14T00:00:01Z",
            )

        with (
            mock.patch.object(
                runner, "_qualification_bindings", return_value=(FakeAuditor(), bindings)
            ),
            mock.patch.object(
                runner, "_load_projection_builder", return_value=FakeProjectionBuilder()
            ),
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner.shutil, "which", return_value=sys.executable),
            mock.patch.object(runner, "_codex_version", return_value="codex-cli test"),
            mock.patch.object(runner, "_invoke_codex", side_effect=fake_invoke),
        ):
            result = runner.run_trial(case, output, skill_root=skill)

        self.assertEqual("CAPTURED_E2", result["status"])
        self.assertFalse(result["filesystem_isolation_verified"])
        receipt = json.loads((output / "runner-receipt.json").read_text(encoding="utf-8"))
        record = json.loads((output / "run-record.json").read_text(encoding="utf-8"))
        seal = json.loads((output / "run-seal.json").read_text(encoding="utf-8"))
        context = json.loads((output / "request" / "context.json").read_text(encoding="utf-8"))
        self.assertEqual("E2", receipt["evidence_cap"])
        self.assertFalse(receipt["filesystem_isolation_verified"])
        self.assertIsNone(receipt["oracle_catalog_visible_to_generator"])
        self.assertFalse(
            receipt["generator_projection"]["evaluation_surface_present_in_projection"]
        )
        self.assertFalse(receipt["isolation"]["oracle_catalog_present_in_projection"])
        self.assertEqual(
            "UNVERIFIED",
            receipt["isolation"]["oracle_catalog_unreachable_to_generator"],
        )
        self.assertEqual(bindings, record["qualification_bindings"])
        self.assertEqual(
            sha256((output / "request" / "public-context.json").read_bytes()),
            record["public_artifact_sha256"]["public_context"],
        )
        self.assertIsNone(record["oracle_catalog_visible_to_generator"])
        self.assertFalse(record["filesystem_isolation_verified"])
        self.assertEqual("LOCAL_COPY_ONLY", record["isolation_verification_source"])
        self.assertEqual("E2", record["execution_provenance"]["evidence_cap"])
        self.assertFalse(
            record["execution_provenance"]["oracle_catalog_present_in_projection"]
        )
        self.assertEqual(
            "UNVERIFIED",
            record["execution_provenance"]["oracle_catalog_unreachable_to_generator"],
        )
        self.assertNotIn("qualification_bindings", context)
        self.assertNotIn("oracle_catalog", json.dumps(context))
        self.assertEqual(
            sha256((output / "run-record.json").read_bytes()),
            seal["run_record_sha256"],
        )
        observation = json.loads(
            (output / "transcript" / "observation.json").read_text(encoding="utf-8")
        )
        invocation = json.loads(
            (output / "request" / "invocation.json").read_text(encoding="utf-8")
        )
        self.assertEqual("E2", observation["evidence_attained"])
        self.assertFalse(observation["model_behavior_evaluated"])
        self.assertEqual("NO_AUTOMATIC_RETRY", invocation["retry_policy"])
        self.assertTrue(invocation["qualification_timing_eligible"])
        self.assertEqual("<EXECUTION_ROOT>", invocation["sanitized_argv"][
            invocation["sanitized_argv"].index("-C") + 1
        ])
        for role in ("invocation", "invocation_observation", "runner_source"):
            self.assertRegex(receipt["artifact_sha256"][role], r"^[0-9a-f]{64}$")

    def test_timeout_receipt_classifies_transport_without_model_failure(self) -> None:
        case = self.make_case(case_id="CASE-TIMEOUT")
        skill = self.copied_skill()
        output = self.root / "timeout-run"
        timed_out = runner.Invocation(
            command=("codex", "exec"),
            pid=27182,
            returncode=1,
            stdout=(
                b'{"type":"thread.started"}\n'
                b'{"type":"turn.started"}\n'
                b'{"type":"error","message":"Reconnecting... 2/5 (request timed out)"}\n'
            ),
            stderr=b"",
            timed_out=True,
            started_at="2026-07-16T15:02:49Z",
            ended_at="2026-07-16T15:03:49Z",
            termination_method="WINDOWS_TASKKILL_TREE",
            termination_returncode=0,
        )
        with (
            mock.patch.object(
                runner, "_qualification_bindings", return_value=self.binding_pair(skill)
            ),
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner.shutil, "which", return_value=sys.executable),
            mock.patch.object(runner, "_codex_version", return_value="codex-cli test"),
            mock.patch.object(runner, "_invoke_codex", return_value=timed_out),
            self.assertRaisesRegex(runner.RunnerError, "infrastructure-invalid"),
        ):
            runner.run_trial(case, output, skill_root=skill, timeout=60)

        receipt = json.loads((output / "runner-receipt.json").read_text(encoding="utf-8"))
        observation = json.loads(
            (output / "transcript" / "observation.json").read_text(encoding="utf-8")
        )
        invocation = json.loads(
            (output / "request" / "invocation.json").read_text(encoding="utf-8")
        )
        self.assertEqual("INFRA_INVALID", receipt["runner_status"])
        self.assertEqual("INVOCATION_TRANSPORT", observation["failure_domain"])
        self.assertEqual("WAITING_PROVIDER_RESPONSE", observation["failure_phase"])
        self.assertEqual("E0", observation["evidence_attained"])
        self.assertFalse(observation["model_behavior_evaluated"])
        self.assertEqual(1, observation["event_stream"]["reconnect_count"])
        self.assertFalse(invocation["qualification_timing_eligible"])
        self.assertEqual("DIAGNOSTIC_SHORT_TIMEOUT", invocation["run_purpose"])
        self.assertFalse((output / "run-record.json").exists())

    def test_builder_return_must_match_projection_manifest_before_invoke(self) -> None:
        case = self.make_case()
        skill = self.copied_skill()
        output = self.root / "mismatch-run"
        actual_builder = runner._load_projection_builder()

        class MismatchBuilder:
            ProjectionError = actual_builder.ProjectionError

            @staticmethod
            def build_projection(source, target, manifest):
                result = actual_builder.build_projection(source, target, manifest)
                result["projection_tree_sha256"] = "0" * 64
                return result

            verify_projection = staticmethod(actual_builder.verify_projection)

        invoke = mock.Mock()
        with (
            mock.patch.object(
                runner, "_qualification_bindings", return_value=self.binding_pair(skill)
            ),
            mock.patch.object(runner, "_load_projection_builder", return_value=MismatchBuilder()),
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner, "_invoke_codex", invoke),
            self.assertRaisesRegex(runner.RunnerError, "return does not match manifest"),
        ):
            runner.run_trial(case, output, skill_root=skill)
        invoke.assert_not_called()
        self.assertFalse((output / "run-record.json").exists())
        self.assertFalse((output / "run-seal.json").exists())

    def test_execution_case_drift_blocks_run_record_and_seal(self) -> None:
        case = self.make_case()
        skill = self.copied_skill()
        output = self.root / "case-drift-run"

        def mutate(execution: Path) -> None:
            input_path = next(
                path
                for path in (execution / "case").iterdir()
                if path.name not in {"prompt.txt", "public-context.json"}
            )
            input_path.write_text("运行中被替换。", encoding="utf-8")

        with (
            mock.patch.object(
                runner, "_qualification_bindings", return_value=self.binding_pair(skill)
            ),
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner.shutil, "which", return_value=sys.executable),
            mock.patch.object(runner, "_codex_version", return_value="codex-cli test"),
            mock.patch.object(
                runner,
                "_invoke_codex",
                side_effect=lambda command, _prompt, _env, _timeout: self.successful_invocation(
                    command, mutate
                ),
            ),
            self.assertRaisesRegex(runner.RunnerError, "infrastructure-invalid"),
        ):
            runner.run_trial(case, output, skill_root=skill)
        receipt = json.loads((output / "runner-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual("INFRA_INVALID", receipt["runner_status"])
        self.assertEqual("FAIL", receipt["generator_projection"]["projection_audit_status"])
        self.assertIn("execution case drift", receipt["exit_status"]["post_run_validation_error"])
        self.assertFalse((output / "run-record.json").exists())
        self.assertFalse((output / "run-seal.json").exists())

    def test_projection_drift_leaves_only_explicit_failure_receipt(self) -> None:
        case = self.make_case()
        skill = self.copied_skill()
        output = self.root / "projection-drift-run"

        def mutate(execution: Path) -> None:
            path = execution / "skill" / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\n污染。\n", encoding="utf-8")

        with (
            mock.patch.object(
                runner, "_qualification_bindings", return_value=self.binding_pair(skill)
            ),
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner.shutil, "which", return_value=sys.executable),
            mock.patch.object(runner, "_codex_version", return_value="codex-cli test"),
            mock.patch.object(
                runner,
                "_invoke_codex",
                side_effect=lambda command, _prompt, _env, _timeout: self.successful_invocation(
                    command, mutate
                ),
            ),
            self.assertRaisesRegex(runner.RunnerError, "infrastructure-invalid"),
        ):
            runner.run_trial(case, output, skill_root=skill)
        receipt = json.loads((output / "runner-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual("INFRA_INVALID", receipt["runner_status"])
        self.assertEqual("FAIL", receipt["generator_projection"]["projection_audit_status"])
        self.assertIn("does not match manifest", receipt["exit_status"]["post_run_validation_error"])
        self.assertFalse((output / "run-record.json").exists())
        self.assertFalse((output / "run-seal.json").exists())


if __name__ == "__main__":
    unittest.main()
