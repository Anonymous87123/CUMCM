import hashlib
import importlib.util
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
SCRIPT = SKILL / "scripts" / "scaffold_humanize_rewrites.py"


def directory_bytes(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class RewriteScaffoldTests(unittest.TestCase):
    def test_cli_help_is_utf8_from_non_utf8_windows_locale(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode)
        help_text = completed.stdout.decode("utf-8")
        self.assertIn("为 prepare 长文运行生成", help_text)
        self.assertIn("该路径必须尚不存在", help_text)
        self.assertEqual("", completed.stderr.decode("utf-8"))

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def prepare(
        self,
        text: str = "\\section{例题}\n本题先判断条件，再说明计算顺序。\n",
        *,
        scene: str = "COURSE",
        name: str = "main.tex",
    ) -> tuple[Path, Path, list[dict]]:
        source = self.root / name
        source.write_text(text, encoding="utf-8")
        run_dir = self.root / f"run-{source.stem}"
        preparer.prepare(
            [source],
            run_dir,
            scene=scene,
            min_author_chars=0,
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((run_dir / "chunks").glob("*.json"))
        ]
        return source, run_dir, [chunk for chunk in chunks if chunk["status"] == "PENDING"]

    def prepare_two_units(self) -> tuple[Path, Path, list[dict]]:
        return self.prepare(
            "# 第一节\n第一段说明材料范围与记录边界。\n\n"
            "# 第二节\n第二段说明对象条件与来源状态。\n",
            scene="GENERAL",
            name="two.md",
        )

    def prepare_adjacent_structural_candidate(self) -> tuple[Path, Path, list[dict]]:
        phrase = (
            "\u7b2c\u4e00\u6bb5\u6709\u8db3\u591f\u7684\u4e2d\u6587\u5185\u5bb9\u7528\u4e8e\u68c0\u67e5"
            "\u7ed3\u6784\u5019\u9009\u548c\u76f8\u90bb\u5355\u5143\uff0c\u5e76\u4e14\u9700\u8981"
            "\u8d85\u8fc7\u5207\u5206\u9608\u503c\u3002"
        )
        source = self.root / "adjacent.md"
        source.write_text(
            "# A\n"
            + phrase * 16
            + "\n\n"
            + phrase.replace("\u7b2c\u4e00\u6bb5", "\u7b2c\u4e8c\u6bb5") * 16
            + "\n",
            encoding="utf-8",
        )
        run_dir = self.root / "run-adjacent"
        preparer.prepare(
            [source],
            run_dir,
            scene="GENERAL",
            intensity="STRUCTURAL",
            structural_transaction_scope="ADJACENT_PAIR",
            max_author_chars=1000,
            min_author_chars=0,
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((run_dir / "chunks").glob("*.json"))
        ]
        return source, run_dir, [chunk for chunk in chunks if chunk["status"] == "PENDING"]

    def reseal_integrity(self, run_dir: Path) -> None:
        manifest = preparer.build_integrity_manifest(run_dir)
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def assert_no_publish(self, output: Path) -> None:
        self.assertFalse(os.path.lexists(output))
        self.assertEqual(
            [],
            list(output.parent.glob(".humanize-scaffold-*.tmp")),
        )

    @staticmethod
    def line_span(masked_text: str, needle: str) -> dict:
        lines = masked_text.replace("\r\n", "\n").replace("\r", "\n").splitlines(
            keepends=True
        )
        line_number = next(index for index, line in enumerate(lines, 1) if needle in line)
        return {
            "id": "S1",
            "start_line": line_number,
            "end_line": line_number,
            "sha256": hashlib.sha256(lines[line_number - 1].encode("utf-8")).hexdigest(),
        }

    def test_v5_scaffold_embeds_source_scene_voice_binding(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "rewrites"

        metadata = scaffolder.scaffold(run_dir, output, "REWRITE")
        unit_id = chunks[0]["unit_id"]
        bundle = json.loads((output / f"{unit_id}.json").read_text(encoding="utf-8"))
        record = metadata["records"][0]
        binding = bundle["authoring_binding"]

        self.assertEqual("humanize-unit-rewrite-bundle/v4", bundle["schema_version"])
        self.assertIsNone(bundle["template_field_edit_scope"])
        self.assertEqual("humanize-rewrite-scaffold/v5", metadata["schema_version"])
        self.assertEqual("humanize-long-authoring-preflight/v1", metadata["preflight"]["schema_version"])
        self.assertEqual("PASS", metadata["preflight"]["status"])
        self.assertEqual("humanize-long-authoring-binding/v1", binding["schema_version"])
        self.assertEqual("COURSE", binding["scene_route"]["resolved_scene"])
        self.assertEqual("USER_EXPLICIT_SCENE", binding["scene_route"]["reason_code"])
        self.assertEqual("COURSE", binding["voice_binding"]["binding_scene"])
        self.assertEqual(chunks[0]["chunk_binding_sha256"], binding["source_binding"]["chunk_binding_sha256"])
        self.assertEqual(binding["authoring_binding_sha256"], record["authoring_binding_sha256"])
        self.assertEqual(binding["source_binding"]["source_span_sha256"], record["source_span_sha256"])
        self.assertEqual("TODO", bundle["rewrite_intent"]["summary"])
        self.assertFalse(metadata["completion_claim_allowed"])
        self.assertTrue(metadata["requires_manual_completion"])

    def test_cli_exposes_frozen_route_reason_and_binding_visibility(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "cli-visible"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision",
                "REWRITE",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode)
        self.assertEqual("SCAFFOLDED", payload["status"])
        self.assertEqual(
            [
                {
                    "requested_scene": "COURSE",
                    "resolved_scene": "COURSE",
                    "route_status": "EXPLICIT",
                    "reason_code": "USER_EXPLICIT_SCENE",
                    "units": 1,
                }
            ],
            payload["authoring_route_summary"],
        )
        self.assertEqual(
            {
                "template_field": "authoring_binding",
                "metadata_hash_field": "authoring_binding_sha256",
                "scope": "FROZEN_PREPARED_RUN_BINDING",
            },
            payload["authoring_binding_visibility"],
        )
        self.assertEqual(
            [
                "LEX",
                "HUM",
                "VOICE",
                "STYLE",
                "SCENE",
                "USER",
                "REPETITION",
                "COLLOCATION",
                "RHYTHM",
                "HIERARCHY",
            ],
            payload["rewrite_intent_authoring_contract"]["target_signal_prefixes"],
        )
        self.assertIn(
            "SCENE-COURSE-RHYTHM",
            payload["rewrite_intent_authoring_contract"]["examples"],
        )
        field_contract = payload["template_field_edit_scope_authoring_contract"]
        self.assertEqual(
            "humanize-unit-template-field-edit-scope/v1",
            field_contract["schema_version"],
        )
        self.assertEqual("PAYLOAD_ONLY", field_contract["permission_boundary"])
        self.assertIsNone(field_contract["default"])
        self.assertFalse(field_contract["quality_clearance_granted"])
        self.assertTrue(field_contract["role_or_force_drift_still_reviews"])

    def test_adjacent_structural_candidate_is_authoring_review_but_scaffold_is_kept(self) -> None:
        _source, run_dir, chunks = self.prepare_adjacent_structural_candidate()
        self.assertEqual(2, len(chunks))
        output = self.root / "adjacent-rewrites"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision",
                "REWRITE",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual("SCAFFOLDED", payload["scaffold_publication_status"])
        self.assertEqual("REVIEW", payload["authoring_gate"]["status"])
        self.assertEqual(
            ["structural_transaction_candidates_require_explicit_disposition"],
            payload["authoring_gate"]["review_reasons"],
        )
        self.assertEqual(1, payload["authoring_gate"]["structural_transaction_candidates_pending"])
        self.assertFalse(payload["authoring_gate"]["caller_reason_trusted"])
        self.assertFalse(payload["authoring_gate"]["caller_selection_trusted"])
        self.assertTrue(output.is_dir())
        sidecar = json.loads((output / "scaffold_metadata.json").read_text(encoding="utf-8"))
        self.assertNotIn("authoring_gate", sidecar)

    def test_caller_reason_and_selection_are_not_decision_inputs(self) -> None:
        _source, run_dir, chunks = self.prepare()
        decision_map = self.root / "caller-fields.json"
        decision_map.write_text(
            json.dumps(
                {
                    chunks[0]["unit_id"]: {
                        "decision": "NO_CHANGE",
                        "reason": "caller claims this is already natural",
                        "selection": "all-high-findings",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = self.root / "caller-fields-out"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision-map",
                str(decision_map),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertIn("decision_map values", payload["error"])
        self.assert_no_publish(output)

    def test_cli_missing_decision_map_is_structured_fail_without_path_leak(self) -> None:
        private_map = self.root / "private" / "secret-decisions.json"
        private_run = self.root / "private-run"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(private_run),
                "--output",
                str(self.root / "unused-output"),
                "--decision-map",
                str(private_map),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("DECISION_MAP_NOT_FOUND", payload["error_code"])
        self.assertTrue(payload["paths_redacted"])
        self.assertFalse(payload["completion_claim_allowed"])
        self.assertNotIn(str(private_map), completed.stdout)
        self.assertNotIn(str(private_map), completed.stderr)
        self.assertNotIn(str(private_run), completed.stdout)

    def test_cli_decision_map_read_errors_use_stable_redacted_codes(self) -> None:
        cases = (
            (PermissionError("private path denied"), "DECISION_MAP_PERMISSION_DENIED"),
            (OSError("private device path failed"), "DECISION_MAP_READ_FAILED"),
        )
        for error, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with (
                    mock.patch.object(Path, "read_bytes", side_effect=error),
                    mock.patch("builtins.print") as mocked_print,
                ):
                    result = scaffolder.main(
                        [
                            "--run-dir",
                            str(self.root / "private-run"),
                            "--output",
                            str(self.root / "unused-output"),
                            "--decision-map",
                            str(self.root / "private-map.json"),
                            "--format",
                            "json",
                        ]
                    )

                self.assertEqual(1, result)
                payload = json.loads(mocked_print.call_args.args[0])
                self.assertEqual("FAIL", payload["status"])
                self.assertEqual(expected_code, payload["error_code"])
                self.assertTrue(payload["paths_redacted"])
                self.assertNotIn("private", payload["error"])

    def test_cli_decision_map_parse_errors_use_stable_codes(self) -> None:
        cases = (
            (b"\xff", "DECISION_MAP_ENCODING_INVALID"),
            (b"{", "DECISION_MAP_JSON_INVALID"),
            (b"[]", "DECISION_MAP_CONTRACT_INVALID"),
        )
        for raw, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                with (
                    mock.patch.object(Path, "read_bytes", return_value=raw),
                    mock.patch("builtins.print") as mocked_print,
                ):
                    result = scaffolder.main(
                        [
                            "--run-dir",
                            str(self.root / "unused-run"),
                            "--output",
                            str(self.root / "unused-output"),
                            "--decision-map",
                            str(self.root / "private-map.json"),
                            "--format",
                            "json",
                        ]
                    )

                self.assertEqual(1, result)
                payload = json.loads(mocked_print.call_args.args[0])
                self.assertEqual(expected_code, payload["error_code"])
                self.assertTrue(payload["paths_redacted"])
                self.assertFalse(payload["completion_claim_allowed"])

    def test_no_change_scaffold_is_invalid_until_specific_evidence_is_supplied(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "no-change"
        scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        bundle = json.loads(
            (output / f"{chunks[0]['unit_id']}.json").read_text(encoding="utf-8")
        )

        self.assertEqual("NO_CHANGE", bundle["decision"])
        self.assertEqual("TODO", bundle["reason"])
        self.assertEqual([], bundle["evidence_spans"])
        self.assertNotIn("masked_text", bundle)

    def test_any_preexisting_output_is_rejected_without_mutation(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        for populated in (False, True):
            with self.subTest(populated=populated):
                output = self.root / f"rewrites-{populated}"
                output.mkdir()
                marker = output / "existing.txt"
                if populated:
                    marker.write_text("do not overwrite", encoding="utf-8")
                before = output.stat(follow_symlinks=False)
                with self.assertRaisesRegex(ValueError, "must not already exist"):
                    scaffolder.scaffold(run_dir, output, "REWRITE")
                self.assertTrue(os.path.samestat(before, output.stat(follow_symlinks=False)))
                if populated:
                    self.assertEqual("do not overwrite", marker.read_text(encoding="utf-8"))

    def test_cli_preexisting_empty_output_is_structured_fail_without_path_leak(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "private-existing-rewrites"
        output.mkdir()
        before = output.stat(follow_symlinks=False)

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision",
                "REWRITE",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        after = output.stat(follow_symlinks=False)
        self.assertEqual(1, completed.returncode)
        self.assertEqual("FAIL", payload["status"])
        self.assertEqual("output must not already exist", payload["error"])
        self.assertNotIn(str(output), completed.stdout)
        self.assertNotIn(str(output), completed.stderr)
        self.assertEqual([], list(output.iterdir()))
        self.assertTrue(os.path.samestat(before, after))

    def test_decision_map_supports_mixed_units_and_requires_exact_coverage(self) -> None:
        _source, run_dir, chunks = self.prepare_two_units()
        self.assertEqual(2, len(chunks))
        unit_ids = [chunk["unit_id"] for chunk in chunks]
        decisions = {unit_ids[0]: "REWRITE", unit_ids[1]: "NO_CHANGE"}
        output = self.root / "mixed"

        metadata = scaffolder.scaffold(run_dir, output, decision_map=decisions)

        self.assertEqual("MIXED", metadata["decision"])
        self.assertEqual(dict(sorted(decisions.items())), metadata["decision_map"])
        for unit_id, decision in decisions.items():
            bundle = json.loads((output / f"{unit_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(decision, bundle["decision"])
        with self.assertRaisesRegex(ValueError, "exactly every"):
            scaffolder.scaffold(
                run_dir,
                self.root / "bad-map",
                decision_map={unit_ids[0]: "REWRITE"},
            )

    def test_missing_or_forged_prepare_integrity_fails_without_output(self) -> None:
        attacks = ("missing", "forged")
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, _chunks = self.prepare()
                integrity = run_dir / "prepare_integrity.json"
                if attack == "missing":
                    integrity.unlink()
                else:
                    payload = json.loads(integrity.read_text(encoding="utf-8"))
                    payload["artifacts"][0]["sha256"] = "0" * 64
                    integrity.write_text(json.dumps(payload), encoding="utf-8")
                output = self.root / "rewrites"
                with self.assertRaisesRegex(ValueError, "integrity|prepare_integrity"):
                    scaffolder.scaffold(run_dir, output, "REWRITE")
                self.assert_no_publish(output)

    def test_legacy_prepare_integrity_requires_reprepare_review(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        current = json.loads(
            (run_dir / "prepare_integrity.json").read_text(encoding="utf-8")
        )
        (run_dir / "structural_transaction_inventory.json").unlink()
        (run_dir / "source_role_overrides.json").unlink()
        run_metadata_path = run_dir / "run_metadata.json"
        run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
        run_metadata = {
            key: value
            for key, value in run_metadata.items()
            if not key.startswith("structural_transaction_")
            and not key.startswith("source_role_override")
        }
        run_metadata_path.write_text(
            json.dumps(run_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy = {
            "schema_version": 1,
            "artifacts": [
                {
                    "path": item["path"],
                    "sha256": (
                        hashlib.sha256(run_metadata_path.read_bytes()).hexdigest()
                        if item["path"] == "run_metadata.json"
                        else item["sha256"]
                    ),
                }
                for item in current["artifacts"]
                if item["path"]
                not in {
                    "source_role_overrides.json",
                    "structural_transaction_inventory.json",
                }
            ],
        }
        (run_dir / "prepare_integrity.json").write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output = self.root / "legacy-rewrites"

        with self.assertRaisesRegex(
            scaffolder.ScaffoldReview,
            "legacy_prepare_requires_reprepare",
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision",
                "REWRITE",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(
            ["legacy_prepare_requires_reprepare"],
            payload["review_reasons"],
        )
        self.assert_no_publish(output)

    def test_legacy_manifest_cannot_hide_v2_source_role_artifact(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        integrity_path = run_dir / "prepare_integrity.json"
        current = json.loads(integrity_path.read_text(encoding="utf-8"))
        (run_dir / "structural_transaction_inventory.json").unlink()
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = {
            key: value
            for key, value in metadata.items()
            if not key.startswith("structural_transaction_")
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy = {
            "schema_version": 1,
            "artifacts": [
                {
                    **item,
                    "sha256": (
                        hashlib.sha256(metadata_path.read_bytes()).hexdigest()
                        if item["path"] == "run_metadata.json"
                        else item["sha256"]
                    ),
                }
                for item in current["artifacts"]
                if item["path"]
                not in {
                    "source_role_overrides.json",
                    "structural_transaction_inventory.json",
                }
            ],
        }
        integrity_path.write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output = self.root / "mixed-legacy-rewrites"

        with self.assertRaisesRegex(
            ValueError,
            "legacy prepare integrity cannot authorize source role overrides",
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def test_legacy_manifest_cannot_hide_v2_source_role_metadata(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        integrity_path = run_dir / "prepare_integrity.json"
        current = json.loads(integrity_path.read_text(encoding="utf-8"))
        (run_dir / "structural_transaction_inventory.json").unlink()
        (run_dir / "source_role_overrides.json").unlink()
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = {
            key: value
            for key, value in metadata.items()
            if not key.startswith("structural_transaction_")
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        legacy = {
            "schema_version": 1,
            "artifacts": [
                {
                    **item,
                    "sha256": (
                        hashlib.sha256(metadata_path.read_bytes()).hexdigest()
                        if item["path"] == "run_metadata.json"
                        else item["sha256"]
                    ),
                }
                for item in current["artifacts"]
                if item["path"]
                not in {
                    "source_role_overrides.json",
                    "structural_transaction_inventory.json",
                }
            ],
        }
        integrity_path.write_text(
            json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output = self.root / "mixed-legacy-metadata-rewrites"

        with self.assertRaisesRegex(
            ValueError,
            "legacy prepare metadata cannot authorize source role overrides",
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def test_policy_snapshot_drift_fails_even_after_local_reseal(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        snapshot = dict(metadata["policy_snapshot"])
        hashes = dict(snapshot["implementation_hashes"])
        hashes["finalize_script_sha256"] = "0" * 64
        snapshot["implementation_hashes"] = hashes
        metadata["policy_snapshot"] = snapshot
        metadata["policy_snapshot_sha256"] = preparer.policy_snapshot_sha256(snapshot)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        self.reseal_integrity(run_dir)
        output = self.root / "rewrites"

        with self.assertRaisesRegex(ValueError, "policy snapshot drift"):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def test_chunk_tamper_and_coordinated_integrity_reseal_both_fail(self) -> None:
        for reseal in (False, True):
            with self.subTest(reseal=reseal), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, chunks = self.prepare()
                path = run_dir / "chunks" / f"{chunks[0]['unit_id']}.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["masked_text"] += "伪造追加。"
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                if reseal:
                    self.reseal_integrity(run_dir)
                output = self.root / "rewrites"
                with self.assertRaisesRegex(
                    ValueError,
                    "integrity|canonical chunk|rebuild|reconstructed source",
                ):
                    scaffolder.scaffold(run_dir, output, "REWRITE")
                self.assert_no_publish(output)

    def test_resealed_route_ledger_injection_fails_source_replay(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        units_path = run_dir / "units.jsonl"
        rows = [
            json.loads(line)
            for line in units_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        pending = next(row for row in rows if row["status"] == "PENDING")
        pending["scene_routing_top_score"] += 9
        pending["scene_routing_margin"] += 9
        pending["scene_routing_evidence"] = []
        units_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        self.reseal_integrity(run_dir)
        output = self.root / "rewrites"

        with self.assertRaisesRegex(ValueError, "initial prepare state mismatch|scene|rebuild"):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def test_modified_or_missing_live_source_returns_review_without_output(self) -> None:
        for attack in ("modified", "missing"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                source, run_dir, _chunks = self.prepare()
                if attack == "modified":
                    source.write_text(source.read_text(encoding="utf-8") + "% changed\n", encoding="utf-8")
                else:
                    source.unlink()
                output = self.root / "rewrites"
                with self.assertRaises(scaffolder.ScaffoldReview) as caught:
                    scaffolder.scaffold(run_dir, output, "REWRITE")
                self.assertEqual("live_source_not_current", caught.exception.reason)
                self.assertEqual("REVIEW", caught.exception.preflight["status"])
                self.assert_no_publish(output)

    def test_hardlinked_live_source_returns_review(self) -> None:
        source, run_dir, _chunks = self.prepare()
        try:
            os.link(source, self.root / "source-hardlink.tex")
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        output = self.root / "rewrites"
        with self.assertRaises(scaffolder.ScaffoldReview) as caught:
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertEqual("HARDLINK", caught.exception.preflight["source_change_units"][0]["current_state"])
        self.assert_no_publish(output)

    def test_symlinked_live_source_returns_review(self) -> None:
        source, run_dir, _chunks = self.prepare()
        target = self.root / "source-target.tex"
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")
        output = self.root / "rewrites"
        with self.assertRaises(scaffolder.ScaffoldReview) as caught:
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertEqual("LINK_OR_REPARSE", caught.exception.preflight["source_change_units"][0]["current_state"])
        self.assert_no_publish(output)

    def test_no_editable_scope_returns_review_and_cli_exit_two(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        run_dir = self.root / "empty-run"
        preparer.prepare([empty], run_dir, scene="COURSE", min_author_chars=0)
        output = self.root / "rewrites"

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision",
                "REWRITE",
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode)
        self.assertEqual("REVIEW", payload["status"])
        self.assertEqual(["no_authoring_eligible_units"], payload["review_reasons"])
        self.assert_no_publish(output)

    def test_source_drift_between_preflights_rolls_back_staging(self) -> None:
        source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        real_validate = finalizer.validate_long_authoring_snapshot
        calls = 0

        def drift(path: Path):
            nonlocal calls
            result = real_validate(path)
            calls += 1
            if calls == 1:
                source.write_text(source.read_text(encoding="utf-8") + "% drift\n", encoding="utf-8")
            return result

        with mock.patch.object(scaffolder.finalizer, "validate_long_authoring_snapshot", side_effect=drift):
            with self.assertRaises(scaffolder.ScaffoldReview):
                scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertEqual(2, calls)
        self.assert_no_publish(output)

    def test_output_appearing_before_commit_is_preserved(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "appeared"
        real_validate = finalizer.validate_long_authoring_snapshot
        calls = 0

        def appear(path: Path):
            nonlocal calls
            result = real_validate(path)
            calls += 1
            if calls == 2:
                output.mkdir()
            return result

        with mock.patch.object(
            scaffolder.finalizer,
            "validate_long_authoring_snapshot",
            side_effect=appear,
        ):
            with self.assertRaisesRegex(ValueError, "output appeared"):
                scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertTrue(output.is_dir())
        self.assertEqual([], list(output.iterdir()))
        self.assertEqual([], list(self.root.glob(".humanize-scaffold-*.tmp")))

    def test_staging_byte_or_closure_tamper_fails_before_publish(self) -> None:
        for attack in ("modify", "delete", "extra"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, chunks = self.prepare()
                output = self.root / "rewrites"
                real_validate = finalizer.validate_long_authoring_snapshot
                calls = 0

                def tamper(path: Path):
                    nonlocal calls
                    result = real_validate(path)
                    calls += 1
                    if calls == 2:
                        staging = next(self.root.glob(".humanize-scaffold-*.tmp"))
                        template = staging / f"{chunks[0]['unit_id']}.json"
                        if attack == "modify":
                            template.write_bytes(template.read_bytes() + b" ")
                        elif attack == "delete":
                            template.unlink()
                        else:
                            (staging / "injected.json").write_text("{}", encoding="utf-8")
                    return result

                with mock.patch.object(
                    scaffolder.finalizer,
                    "validate_long_authoring_snapshot",
                    side_effect=tamper,
                ):
                    with self.assertRaisesRegex(
                        (ValueError, RuntimeError),
                        "staging|template|file closure",
                    ):
                        scaffolder.scaffold(run_dir, output, "REWRITE")
                self.assert_no_publish(output)

    def test_run_corruption_between_preflights_rolls_back_staging(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "rewrites"
        real_validate = finalizer.validate_long_authoring_snapshot
        calls = 0

        def corrupt(path: Path):
            nonlocal calls
            result = real_validate(path)
            calls += 1
            if calls == 1:
                chunk_path = run_dir / "chunks" / f"{chunks[0]['unit_id']}.json"
                chunk_path.write_bytes(chunk_path.read_bytes() + b" ")
            return result

        with mock.patch.object(scaffolder.finalizer, "validate_long_authoring_snapshot", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "integrity|artifact"):
                scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def test_v3_downgrade_to_v2_is_readable_but_authoring_gate_is_review(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "rewrites"
        scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        (output / "scaffold_metadata.json").unlink()
        (output / scaffolder.COMMITTED_MARKER_NAME).unlink()
        unit = chunks[0]
        path = output / f"{unit['unit_id']}.json"
        bundle = json.loads(path.read_text(encoding="utf-8"))
        bundle["schema_version"] = "humanize-unit-rewrite-bundle/v2"
        bundle.pop("authoring_binding")
        bundle["reason"] = "题解保留条件判断与计算顺序，避免改变两个步骤的先后关系"
        bundle["evidence_spans"] = [self.line_span(unit["masked_text"], "本题")]
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

        result = finalizer.finalize(run_dir, output)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["authoring_binding_status"])
        self.assertEqual(1, result["authoring_bindings_missing"])
        self.assertFalse(result["humanize_completion_claim_allowed"])

    def test_v5_metadata_and_bundle_binding_tamper_are_rejected(self) -> None:
        attacks = ("metadata", "bundle")
        for attack in attacks:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, chunks = self.prepare()
                output = self.root / "rewrites"
                scaffolder.scaffold(run_dir, output, "NO_CHANGE")
                if attack == "metadata":
                    path = output / "scaffold_metadata.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["records"][0]["source_span_sha256"] = "f" * 64
                else:
                    path = output / f"{chunks[0]['unit_id']}.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["authoring_binding"]["scene_route"]["top_score"] += 1
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "binding|hash|metadata"):
                    finalizer.collect_rewrites(output)

    def test_v5_preflight_globals_are_rebound_to_current_run(self) -> None:
        for attack in ("run_dir_name", "run_state_sha256"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, _chunks = self.prepare()
                output = self.root / "rewrites"
                scaffolder.scaffold(run_dir, output, "NO_CHANGE")
                path = output / "scaffold_metadata.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                if attack == "run_dir_name":
                    payload["run_dir_name"] = "forged-run"
                else:
                    payload["preflight"]["run_state_sha256"] = "f" * 64
                    canonical = dict(payload["preflight"])
                    canonical.pop("preflight_sha256")
                    payload["preflight"]["preflight_sha256"] = hashlib.sha256(
                        json.dumps(
                            canonical,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "run.*binding|prepared-run"):
                    finalizer.collect_rewrites(output, run_dir=run_dir)

    def test_v5_scaffold_requires_every_pending_record(self) -> None:
        _source, run_dir, chunks = self.prepare_two_units()
        output = self.root / "rewrites"
        metadata = scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        removed = metadata["records"].pop()
        metadata["decision_map"].pop(removed["unit_id"])
        metadata["pending_units_total"] = 1
        metadata["templates_total"] = 1
        (output / removed["path"]).unlink()
        (output / "scaffold_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "unit coverage|count"):
            finalizer.collect_rewrites(output, run_dir=run_dir)
        self.assertEqual(2, len(chunks))

    def test_v5_scaffold_rebuilds_original_template_hash(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        metadata = scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        metadata["records"][0]["template_sha256"] = "f" * 64
        (output / "scaffold_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "record mismatch.*template_sha256"):
            finalizer.collect_rewrites(output, run_dir=run_dir)

    def test_v5_scaffold_rejects_coordinated_binding_reseal(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "rewrites"
        metadata = scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        unit_id = chunks[0]["unit_id"]
        bundle_path = output / f"{unit_id}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        binding = bundle["authoring_binding"]
        binding["scene_route"]["top_score"] += 1
        binding_without_hash = dict(binding)
        binding_without_hash.pop("authoring_binding_sha256")
        binding["authoring_binding_sha256"] = hashlib.sha256(
            finalizer._canonical_json(binding_without_hash).encode("utf-8")
        ).hexdigest()
        record = metadata["records"][0]
        record["scene_routing_top_score"] = binding["scene_route"]["top_score"]
        record["authoring_binding_sha256"] = binding[
            "authoring_binding_sha256"
        ]
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output / "scaffold_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "prepared-run record mismatch|binding_drift"):
            finalizer.collect_rewrites(output, run_dir=run_dir)

    def test_v5_run_binding_ignores_later_finalization_artifacts(self) -> None:
        _source, run_dir, chunks = self.prepare()
        output = self.root / "rewrites"
        scaffolder.scaffold(run_dir, output, "NO_CHANGE")
        validation = run_dir / "validation"
        validation.mkdir()
        (validation / "prior.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "finalization_metadata.json").write_text(
            "{}\n", encoding="utf-8"
        )

        rewrites, transactions, declines = finalizer.collect_rewrites(
            output,
            run_dir=run_dir,
        )
        self.assertEqual({chunks[0]["unit_id"]}, set(rewrites))
        self.assertEqual({}, transactions)
        self.assertEqual({}, declines)

    def test_scaffold_is_deterministic_for_same_frozen_run(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        first = self.root / "first"
        second = self.root / "second"
        scaffolder.scaffold(run_dir, first, "REWRITE")
        scaffolder.scaffold(run_dir, second, "REWRITE")
        self.assertEqual(directory_bytes(first), directory_bytes(second))

    def test_duplicate_decision_map_keys_fail_before_output(self) -> None:
        _source, run_dir, chunks = self.prepare()
        decision_map = self.root / "decision-map.json"
        unit_id = chunks[0]["unit_id"]
        decision_map.write_text(
            f'{{"{unit_id}":"REWRITE","{unit_id}":"NO_CHANGE"}}',
            encoding="utf-8",
        )
        output = self.root / "rewrites"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--run-dir",
                str(run_dir),
                "--output",
                str(output),
                "--decision-map",
                str(decision_map),
                "--format",
                "json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(1, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertEqual("DECISION_MAP_JSON_INVALID", payload["error_code"])
        self.assertTrue(payload["paths_redacted"])
        self.assert_no_publish(output)

    def test_output_inside_run_dir_is_refused(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = run_dir / "rewrites"
        with self.assertRaisesRegex(ValueError, "outside run_dir"):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assert_no_publish(output)

    def make_junction(self, link: Path, target: Path) -> None:
        if os.name != "nt":
            self.skipTest("junction test is Windows-specific")
        completed = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            self.skipTest(f"junctions unavailable: {completed.stderr.strip()}")

    def test_run_and_output_parent_junction_aliases_are_rejected(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        run_alias = self.root / "run-alias"
        output_target = self.root / "output-target"
        output_target.mkdir()
        output_alias = self.root / "output-alias"
        self.make_junction(run_alias, run_dir)
        self.make_junction(output_alias, output_target)
        try:
            with self.assertRaisesRegex(ValueError, "link or reparse"):
                scaffolder.scaffold(
                    run_alias,
                    self.root / "run-alias-output",
                    "REWRITE",
                )
            with self.assertRaisesRegex(ValueError, "link or reparse"):
                scaffolder.scaffold(
                    run_dir,
                    output_alias / "rewrites",
                    "REWRITE",
                )
            self.assertFalse((output_target / "rewrites").exists())
        finally:
            if os.path.lexists(run_alias):
                os.rmdir(run_alias)
            if os.path.lexists(output_alias):
                os.rmdir(output_alias)

    def test_output_parent_swap_after_link_check_is_rejected(self) -> None:
        if os.name != "nt":
            self.skipTest("junction test is Windows-specific")
        _source, run_dir, _chunks = self.prepare()
        parent = self.root / "requested-parent"
        parent.mkdir()
        saved_parent = self.root / "requested-parent-saved"
        victim = self.root / "victim-parent"
        victim.mkdir()
        sentinel = victim / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        output = parent / "rewrites"
        real_reject = scaffolder._reject_link_components
        swapped = False

        def swap_after_check(path: Path, label: str) -> None:
            nonlocal swapped
            real_reject(path, label)
            if label == "output" and not swapped:
                parent.rename(saved_parent)
                self.make_junction(parent, victim)
                swapped = True

        try:
            with mock.patch.object(
                scaffolder,
                "_reject_link_components",
                side_effect=swap_after_check,
            ):
                with self.assertRaisesRegex(ValueError, "reparse|identity"):
                    scaffolder.scaffold(run_dir, output, "REWRITE")
            self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))
            self.assertFalse((victim / "rewrites").exists())
        finally:
            if os.path.lexists(parent):
                os.rmdir(parent)
            if saved_parent.exists():
                saved_parent.rename(parent)

    def test_staging_directory_cannot_be_replaced_at_publish_boundary(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        moved = self.root / "staging-moved"
        real_publish = scaffolder._publish_directory_exclusive
        replacement_blocked = False

        def try_replace(staging: Path, target: Path, lease=None) -> None:
            nonlocal replacement_blocked
            try:
                staging.rename(moved)
            except PermissionError:
                replacement_blocked = True
            else:
                self.fail("pinned staging directory was replaceable")
            real_publish(staging, target, lease)

        with mock.patch.object(
            scaffolder,
            "_publish_directory_exclusive",
            side_effect=try_replace,
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertTrue(replacement_blocked)
        self.assertTrue((output / "scaffold_metadata.json").is_file())
        self.assertFalse(moved.exists())

    def test_staging_parent_cannot_be_replaced_during_exclusive_write(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle creation test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        moved = self.root / "write-staging-moved"
        real_open = scaffolder.os.open
        replacement_blocked = False

        def try_replace(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal replacement_blocked
            candidate = Path(path)
            if (
                candidate.suffix == ".json"
                and candidate.parent.name.startswith(".humanize-scaffold-")
                and not replacement_blocked
            ):
                try:
                    candidate.parent.rename(moved)
                except PermissionError:
                    replacement_blocked = True
                else:
                    self.fail("staging parent was replaceable before os.open")
            if dir_fd is None:
                return real_open(path, flags, mode)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with mock.patch.object(scaffolder.os, "open", side_effect=try_replace):
            scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertTrue(replacement_blocked)
        self.assertTrue((output / "scaffold_metadata.json").is_file())
        self.assertFalse(moved.exists())

    def test_destination_appearing_at_handle_rename_is_preserved(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "appeared-at-rename"
        real_rename = scaffolder._win_set_directory_name
        appeared = False

        def appear(
            handle: int,
            destination: Path | str,
            root_handle: int | None = None,
        ) -> None:
            nonlocal appeared
            if os.fspath(destination) == output.name and not appeared:
                output.mkdir()
                (output / "marker.txt").write_text("keep", encoding="utf-8")
                appeared = True
            real_rename(handle, destination, root_handle)

        with mock.patch.object(
            scaffolder,
            "_win_set_directory_name",
            side_effect=appear,
        ):
            with self.assertRaises(FileExistsError):
                scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertTrue(appeared)
        self.assertEqual(
            "keep", (output / "marker.txt").read_text(encoding="utf-8")
        )
        self.assertEqual([], list(self.root.glob(".humanize-scaffold-*.tmp")))

    def test_publish_hardlink_takeover_restores_victim_bytes_and_link_count(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows hardlink publication test")
        for target_kind in ("unit", "metadata"):
            with self.subTest(target_kind=target_kind), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                _source, run_dir, chunks = self.prepare()
                output = self.root / "rewrites"
                victim = self.root / "victim.txt"
                victim.write_text("victim-bytes", encoding="utf-8")
                before = victim.stat(follow_symlinks=False)
                real_publish = scaffolder._publish_directory_exclusive

                def take_over(staging: Path, target: Path, lease=None) -> None:
                    name = (
                        "scaffold_metadata.json"
                        if target_kind == "metadata"
                        else f"{chunks[0]['unit_id']}.json"
                    )
                    member = staging / name
                    member.unlink()
                    os.link(victim, member)
                    real_publish(staging, target, lease)

                with mock.patch.object(
                    scaffolder,
                    "_publish_directory_exclusive",
                    side_effect=take_over,
                ):
                    with self.assertRaisesRegex(
                        (ValueError, RuntimeError),
                        "hardlinked|metadata|template|staging",
                    ):
                        scaffolder.scaffold(run_dir, output, "REWRITE")
                after = victim.stat(follow_symlinks=False)
                self.assertEqual(b"victim-bytes", victim.read_bytes())
                self.assertEqual(before.st_nlink, after.st_nlink)
                self.assertFalse(output.exists())
                self.assertEqual([], list(self.root.glob(".humanize-scaffold-*.tmp")))

    def test_cleanup_member_swap_does_not_mutate_hardlink_victim(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle cleanup test")
        staging = self.root / ".humanize-scaffold-cleanup.tmp"
        staging.mkdir()
        member = staging / "unit.json"
        member.write_text("owned", encoding="utf-8")
        victim = self.root / "victim.txt"
        victim.write_text("victim", encoding="utf-8")
        victim_before = victim.stat(follow_symlinks=False)
        identity = scaffolder._path_identity(staging)
        real_open = scaffolder._win_open_path_handle
        swapped = False

        def swap_after_open(path: Path, **kwargs):
            nonlocal swapped
            handle = real_open(path, **kwargs)
            if Path(path) == member and not swapped:
                member.unlink()
                os.link(victim, member)
                swapped = True
            return handle

        with mock.patch.object(
            scaffolder,
            "_win_open_path_handle",
            side_effect=swap_after_open,
        ):
            scaffolder._safe_remove_staging(staging, self.root, identity)
        victim_after = victim.stat(follow_symlinks=False)
        self.assertTrue(swapped)
        self.assertFalse(staging.exists())
        self.assertEqual(b"victim", victim.read_bytes())
        self.assertEqual(victim_before.st_nlink, victim_after.st_nlink)

    def test_injected_staging_subdirectory_is_never_recursively_removed(self) -> None:
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        real_validate = finalizer.validate_long_authoring_snapshot
        calls = 0
        injected: Path | None = None

        def inject(path: Path):
            nonlocal calls, injected
            result = real_validate(path)
            calls += 1
            if calls == 2:
                staging = next(self.root.glob(".humanize-scaffold-*.tmp"))
                injected = staging / "injected-directory"
                injected.mkdir()
                (injected / "sentinel.txt").write_text("keep", encoding="utf-8")
            return result

        with mock.patch.object(
            scaffolder.finalizer,
            "validate_long_authoring_snapshot",
            side_effect=inject,
        ):
            with self.assertRaisesRegex(ValueError, "file closure mismatch") as caught:
                scaffolder.scaffold(run_dir, output, "REWRITE")
        self.assertTrue(
            any(
                "recursive staging cleanup" in note
                for note in getattr(caught.exception, "__notes__", [])
            )
        )
        assert injected is not None
        self.assertEqual(
            "keep", (injected / "sentinel.txt").read_text(encoding="utf-8")
        )
        self.assertFalse(output.exists())
        (injected / "sentinel.txt").unlink()
        injected.rmdir()
        staging = injected.parent
        for path in staging.iterdir():
            path.unlink()
        staging.rmdir()

    def test_only_uncommitted_marker_is_visible_before_commit(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        observed_markers: list[set[str]] = []
        real_commit = scaffolder._WindowsStagingLease.commit_marker

        def inspect_before_commit(
            lease, path: Path, expected_sha256: str
        ) -> None:
            self.assertTrue(path.is_dir())
            marker_names = {
                name
                for name in (
                    scaffolder.UNCOMMITTED_MARKER_NAME,
                    scaffolder.COMMITTED_MARKER_NAME,
                )
                if os.path.lexists(path / name)
            }
            observed_markers.append(marker_names)
            self.assertEqual(
                {scaffolder.UNCOMMITTED_MARKER_NAME},
                marker_names,
            )
            real_commit(lease, path, expected_sha256)

        with mock.patch.object(
            scaffolder._WindowsStagingLease,
            "commit_marker",
            new=inspect_before_commit,
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")

        self.assertEqual(
            [{scaffolder.UNCOMMITTED_MARKER_NAME}],
            observed_markers,
        )
        self.assertFalse(
            os.path.lexists(output / scaffolder.UNCOMMITTED_MARKER_NAME)
        )
        self.assertTrue((output / scaffolder.COMMITTED_MARKER_NAME).is_file())

    def test_post_publish_failure_with_rollback_collision_is_dirty(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle rollback test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        real_publish = scaffolder._publish_directory_exclusive
        real_validate = scaffolder._validate_staged_scaffold
        rollback_target: Path | None = None

        def publish_then_collide(staging: Path, target: Path, lease=None) -> None:
            nonlocal rollback_target
            real_publish(staging, target, lease)
            rollback_target = staging
            staging.mkdir()

        def fail_published_verification(
            path: Path,
            metadata: dict,
            staging_identity: tuple[int, ...],
        ) -> str:
            if path == output:
                raise ValueError("injected post-publication verification failure")
            return real_validate(path, metadata, staging_identity)

        with mock.patch.object(
            scaffolder,
            "_publish_directory_exclusive",
            side_effect=publish_then_collide,
        ), mock.patch.object(
            scaffolder,
            "_validate_staged_scaffold",
            side_effect=fail_published_verification,
        ):
            with self.assertRaisesRegex(
                scaffolder.ScaffoldDirtyFailure,
                "publication verification failed.*rollback failed",
            ) as caught:
                scaffolder.scaffold(run_dir, output, "REWRITE")

        self.assertEqual(output, caught.exception.output)
        self.assertTrue(caught.exception.output_may_exist)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn(
            "injected post-publication verification failure",
            str(caught.exception.__cause__),
        )
        self.assertTrue(output.is_dir())
        self.assertTrue(
            (output / scaffolder.UNCOMMITTED_MARKER_NAME).is_file()
        )
        self.assertFalse(
            os.path.lexists(output / scaffolder.COMMITTED_MARKER_NAME)
        )
        self.assertIsNotNone(rollback_target)
        assert rollback_target is not None
        self.assertTrue(rollback_target.is_dir())

    def test_cli_reports_fail_dirty_and_output_may_exist(self) -> None:
        output = self.root / "possibly-published"
        failure = scaffolder.ScaffoldDirtyFailure(
            "injected dirty publication",
            output,
        )

        with mock.patch.object(
            scaffolder,
            "scaffold",
            side_effect=failure,
        ), mock.patch("builtins.print") as mocked_print:
            result = scaffolder.main(
                [
                    "--run-dir",
                    str(self.root / "run"),
                    "--output",
                    str(output),
                    "--decision",
                    "REWRITE",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(1, result)
        mocked_print.assert_called_once()
        payload = json.loads(mocked_print.call_args.args[0])
        self.assertEqual("FAIL_DIRTY", payload["status"])
        self.assertTrue(payload["output_may_exist"])
        self.assertEqual(str(output), payload["output"])
        self.assertEqual(
            scaffolder.UNCOMMITTED_MARKER_NAME,
            payload["uncommitted_marker"],
        )
        self.assertFalse(payload["completion_claim_allowed"])

    def test_non_bmp_output_leaf_publishes_through_windows_rename(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites-\U0001f680"

        scaffolder.scaffold(run_dir, output, "REWRITE")

        self.assertTrue((output / "scaffold_metadata.json").is_file())
        self.assertTrue((output / scaffolder.COMMITTED_MARKER_NAME).is_file())
        self.assertFalse(
            os.path.lexists(output / scaffolder.UNCOMMITTED_MARKER_NAME)
        )

    def test_uncommitted_marker_is_frozen_before_commit_rename(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        real_rename = scaffolder._win_set_directory_name
        mutation_blocked = False

        def try_mutation_before_marker_rename(
            handle: int,
            destination: Path | str,
            root_handle: int | None = None,
        ) -> None:
            nonlocal mutation_blocked
            if destination == scaffolder.COMMITTED_MARKER_NAME:
                marker = output / scaffolder.UNCOMMITTED_MARKER_NAME
                try:
                    marker.write_text("{}\n", encoding="utf-8")
                except OSError:
                    mutation_blocked = True
                else:
                    self.fail("uncommitted marker remained writable after freeze")
            real_rename(handle, destination, root_handle)

        with mock.patch.object(
            scaffolder,
            "_win_set_directory_name",
            side_effect=try_mutation_before_marker_rename,
        ):
            scaffolder.scaffold(run_dir, output, "REWRITE")

        self.assertTrue(mutation_blocked)
        self.assertTrue((output / scaffolder.COMMITTED_MARKER_NAME).is_file())
        self.assertFalse(
            os.path.lexists(output / scaffolder.UNCOMMITTED_MARKER_NAME)
        )

    def test_marker_tamper_after_published_validation_is_rejected(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        real_commit = scaffolder._WindowsStagingLease.commit_marker

        def tamper_then_commit(
            lease, path: Path, expected_sha256: str
        ) -> None:
            (path / scaffolder.UNCOMMITTED_MARKER_NAME).write_text(
                "{}\n", encoding="utf-8"
            )
            real_commit(lease, path, expected_sha256)

        with mock.patch.object(
            scaffolder._WindowsStagingLease,
            "commit_marker",
            new=tamper_then_commit,
        ):
            with self.assertRaisesRegex(
                ValueError, "marker bytes changed before commit"
            ):
                scaffolder.scaffold(run_dir, output, "REWRITE")

        self.assertFalse(output.exists())

    def test_marker_hardlink_after_published_validation_is_rejected(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows hardlink publication test")
        _source, run_dir, _chunks = self.prepare()
        output = self.root / "rewrites"
        marker_alias = self.root / "marker-alias"
        real_commit = scaffolder._WindowsStagingLease.commit_marker

        def hardlink_then_commit(
            lease, path: Path, expected_sha256: str
        ) -> None:
            os.link(path / scaffolder.UNCOMMITTED_MARKER_NAME, marker_alias)
            real_commit(lease, path, expected_sha256)

        try:
            with mock.patch.object(
                scaffolder._WindowsStagingLease,
                "commit_marker",
                new=hardlink_then_commit,
            ):
                with self.assertRaisesRegex(
                    ValueError, "marker became hardlinked"
                ):
                    scaffolder.scaffold(run_dir, output, "REWRITE")
            self.assertFalse(output.exists())
        finally:
            if marker_alias.exists():
                marker_alias.unlink()

    def test_handle_relative_rename_uses_pinned_parent_after_ancestor_rebind(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows handle publication test")
        ancestor = self.root / "requested"
        parent = ancestor / "parent"
        parent.mkdir(parents=True)
        staging = parent / "staging"
        staging.mkdir()
        saved = self.root / "requested-saved"
        alternate = self.root / "alternate"
        (alternate / "parent").mkdir(parents=True)
        parent_handle: int | None = None
        lease = None
        junction_created = False
        try:
            parent_handle = scaffolder._win_open_directory_guard(
                parent,
                scaffolder._path_identity(parent),
                "output parent",
            )
            lease = scaffolder._WindowsStagingLease.acquire(
                staging,
                scaffolder._path_identity(staging),
                parent_handle,
            )
            try:
                ancestor.rename(saved)
            except PermissionError as error:
                self.skipTest(f"ancestor rename is blocked by the host: {error}")
            self.make_junction(ancestor, alternate)
            junction_created = True

            lease.rename(ancestor / "parent" / "published")

            self.assertTrue((saved / "parent" / "published").is_dir())
            self.assertFalse((alternate / "parent" / "published").exists())
        finally:
            if lease is not None:
                lease.close()
            if parent_handle is not None:
                scaffolder._win_close_handle(parent_handle)
            if junction_created and os.path.lexists(ancestor):
                os.rmdir(ancestor)
            if saved.exists() and not ancestor.exists():
                saved.rename(ancestor)

    def test_directory_guard_rejects_non_ntfs_and_remote_ntfs(self) -> None:
        expected_identity = (1, 2, 3, 4)
        base_patches = (
            mock.patch.object(scaffolder, "_win_open_path_handle", return_value=101),
            mock.patch.object(
                scaffolder,
                "_win_handle_information",
                return_value={
                    "attributes": scaffolder._WIN_FILE_ATTRIBUTE_DIRECTORY,
                    "volume_serial": 1,
                    "file_index": 2,
                    "size": 0,
                    "links": 1,
                },
            ),
            mock.patch.object(scaffolder, "_path_identity", return_value=expected_identity),
        )
        for filesystem in ("REFS", "FAT32", "EXFAT"):
            with self.subTest(filesystem=filesystem), base_patches[0], base_patches[1], base_patches[2], mock.patch.object(
                scaffolder, "_win_filesystem_name", return_value=filesystem
            ), mock.patch.object(scaffolder, "_win_close_handle") as close_handle:
                with self.assertRaisesRegex(RuntimeError, "tested NTFS"):
                    scaffolder._win_open_directory_guard(
                        self.root,
                        expected_identity,
                        "output parent",
                    )
                close_handle.assert_called_once_with(101)

        with mock.patch.object(
            scaffolder, "_win_open_path_handle", return_value=202
        ), mock.patch.object(
            scaffolder,
            "_win_handle_information",
            return_value={
                "attributes": scaffolder._WIN_FILE_ATTRIBUTE_DIRECTORY,
                "volume_serial": 1,
                "file_index": 2,
                "size": 0,
                "links": 1,
            },
        ), mock.patch.object(
            scaffolder, "_path_identity", return_value=expected_identity
        ), mock.patch.object(
            scaffolder, "_win_filesystem_name", return_value="NTFS"
        ), mock.patch.object(
            scaffolder,
            "_win_remote_protocol",
            return_value={"protocol": 0x00020000},
        ), mock.patch.object(scaffolder, "_win_close_handle") as close_handle:
            with self.assertRaisesRegex(RuntimeError, "local NTFS"):
                scaffolder._win_open_directory_guard(
                    self.root,
                    expected_identity,
                    "run_dir",
                )
            close_handle.assert_called_once_with(202)

    def test_close_members_attempts_all_and_retains_failed_ownership(self) -> None:
        names = ("first.json", "middle.json", "last.json")
        handles = (101, 202, 303)

        for failed_index in range(len(handles)):
            with self.subTest(failed_member=names[failed_index]):
                lease = scaffolder._WindowsStagingLease(
                    self.root,
                    (1, 2, 3, 4),
                    directory_handle=404,
                    parent_handle=505,
                )
                lease.member_handles = {
                    name: (handle, {"file_index": handle})
                    for name, handle in zip(names, handles)
                }
                attempted: list[int] = []

                def close_with_one_failure(handle: int | None) -> None:
                    assert handle is not None
                    attempted.append(handle)
                    if handle == handles[failed_index]:
                        raise OSError(f"injected CloseHandle failure: {handle}")

                with mock.patch.object(
                    scaffolder,
                    "_win_close_handle",
                    side_effect=close_with_one_failure,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "failed to close 1 scaffold member handle",
                    ):
                        lease.close_members()

                self.assertEqual(list(handles), attempted)
                self.assertEqual(
                    {names[failed_index]},
                    set(lease.member_handles),
                )
                self.assertEqual(
                    handles[failed_index],
                    lease.member_handles[names[failed_index]][0],
                )

    def test_non_windows_scaffold_fails_closed_before_filesystem_work(self) -> None:
        output = self.root / "rewrites"

        with mock.patch.object(scaffolder.os, "name", "posix"):
            with self.assertRaisesRegex(
                RuntimeError,
                "requires tested Windows NTFS handle semantics",
            ):
                scaffolder.scaffold(
                    self.root / "does-not-need-to-exist",
                    output,
                    "REWRITE",
                )

        self.assertFalse(os.path.lexists(output))

    def test_stable_file_read_rejects_hardlink_created_after_read(self) -> None:
        path = self.root / "staged.json"
        path.write_text("{}", encoding="utf-8")
        alias = self.root / "alias.json"
        real_read = Path.read_bytes

        def link_after_read(current: Path) -> bytes:
            raw = real_read(current)
            if current == path and not alias.exists():
                os.link(path, alias)
            return raw

        try:
            with mock.patch.object(Path, "read_bytes", new=link_after_read):
                with self.assertRaisesRegex(ValueError, "linked|changed"):
                    scaffolder._stable_file_bytes(path, "staged file")
        finally:
            if alias.exists():
                alias.unlink()


if __name__ == "__main__":
    unittest.main()
