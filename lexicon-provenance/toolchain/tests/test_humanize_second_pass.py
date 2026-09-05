import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
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
runner = load_module(
    "run_humanize_generation_trial",
    SKILL / "scripts" / "run_humanize_generation_trial.py",
)
second_prepare = load_module(
    "prepare_humanize_second_pass",
    SKILL / "scripts" / "prepare_humanize_second_pass.py",
)
second_verify = load_module(
    "verify_humanize_second_pass",
    SKILL / "scripts" / "verify_humanize_second_pass.py",
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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


class FakeProjectionBuilder:
    class ProjectionError(ValueError):
        pass

    TREE = "f" * 64

    @staticmethod
    def verify_projection(
        _root: Path,
        manifest: dict,
        **_kwargs: object,
    ) -> dict:
        if manifest["projection_tree_sha256"] != FakeProjectionBuilder.TREE:
            raise FakeProjectionBuilder.ProjectionError("tree drift")
        return {"projection_tree_sha256": FakeProjectionBuilder.TREE, "files": 1}

    @staticmethod
    def build_projection(_source: Path, target: Path, manifest: Path) -> dict:
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("# fixture", encoding="utf-8")
        payload = {
            "schema_version": "humanize-generator-projection-manifest/v2",
            "projection_tree_sha256": FakeProjectionBuilder.TREE,
            "projection_policy": {"sha256": "1" * 64},
            "builder": {"executable_sha256": "2" * 64},
            "source": {
                "inventory_sha256": "3" * 64,
                "evaluation_surface_sha256": "4" * 64,
            },
        }
        raw = canonical_json(payload)
        manifest.write_bytes(raw)
        return {**payload, "manifest_sha256": sha256(raw)}


class HumanizeSecondPassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.trial_decision = "NO_CHANGE"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def voice_bound_bundle(unit: dict, payload: dict) -> dict:
        return {
            "unit_id": unit["unit_id"],
            "chunk_binding_sha256": unit["chunk_binding_sha256"],
            "voice_profile_sha256": unit["voice_profile_sha256"],
            "keep_reasons": {},
            **payload,
        }

    @staticmethod
    def pending_chunks(run_dir: Path) -> list[dict]:
        return sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: (item["file_id"], item["start"]),
        )

    @staticmethod
    def promote_review_candidate_for_component_test(run_dir: Path) -> None:
        """Simulate an external clearance that production code cannot issue locally."""

        review = run_dir / "rendered_review"
        rendered = run_dir / "rendered"
        if not review.is_dir() or rendered.exists():
            raise AssertionError("test fixture is not a clean paired-quality review candidate")
        shutil.copytree(review, rendered)
        shutil.rmtree(review)
        metadata_path = run_dir / "finalization_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.update(
            {
                "status": "PASS",
                "exit_code": 0,
                "delivery_gate_status": "PASS",
                "publish_state": "FINAL",
                "published_path": str(rendered),
                "paired_quality_gate_status": "EXTERNALLY_CLEARED_TEST_FIXTURE",
                "paired_quality_clearance_granted": True,
            }
        )
        finalizer._write_json_group_atomic(
            (
                (metadata_path, metadata),
                (run_dir / "latest_attempt_metadata.json", metadata),
            )
        )

    def make_first_pass(
        self, *, units: int = 1, promote_for_component_test: bool = True
    ) -> tuple[Path, Path]:
        source = self.root / "main.tex"
        blocks = [
            f"\\section{{第{index}节}}\n第{index}组峰值出现在当前条件。\n"
            for index in range(1, units + 1)
        ]
        source.write_text("\n".join(blocks), encoding="utf-8")
        run_dir = self.root / "first-run"
        preparer.prepare([source], run_dir, scene="RESEARCH", min_author_chars=0)
        rewrites = self.root / "first-rewrites"
        rewrites.mkdir()
        for unit in self.pending_chunks(run_dir):
            bundle = self.voice_bound_bundle(
                unit,
                {"decision": "NO_CHANGE", "reason": "原句已直接陈述观察结果"},
            )
            (rewrites / f"{unit['unit_id']}.json").write_bytes(canonical_json(bundle))
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PENDING_EXTERNAL_REVIEW", result["paired_quality_gate_status"])
        self.assertTrue(result["coverage_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        if promote_for_component_test:
            self.promote_review_candidate_for_component_test(run_dir)
        return run_dir, rewrites

    def test_paired_quality_review_candidate_is_not_a_second_pass_seed(self) -> None:
        first_run, _rewrites = self.make_first_pass(
            promote_for_component_test=False
        )
        with self.assertRaisesRegex(
            second_prepare.SecondPassPreparationError,
            "first pass is not eligible for fresh convergence: status='REVIEW'",
        ):
            second_prepare.prepare_second_pass(
                first_run,
                self.root / "rejected-second-run",
                self.root / "rejected-second-cases",
            )

    def test_second_pass_refuses_metadata_while_authority_journal_exists(self) -> None:
        first_run, _rewrites = self.make_first_pass()
        (first_run / finalizer.AUTHORITY_GROUP_JOURNAL_NAME).write_text(
            "{}\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(RuntimeError, "requires recovery"):
            second_prepare._first_pass_inputs(first_run)

    def make_auto_first_pass(self) -> tuple[Path, Path]:
        source = self.root / "mixed.md"
        source.write_text(
            "# 例题与解析\n本题先辨认条件，再代入公式。\n\n"
            "# 问题三的模型建立与求解\n建立状态变量并设置参数，随后进行数值求解。\n\n"
            "# 结果与讨论\n本研究的实验结果表明，该判断仅在当前范围成立。\n\n"
            "# 背景\n该段保留原有范围说明。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "auto-first-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        chunks = self.pending_chunks(run_dir)
        self.assertEqual(
            {"COURSE", "GENERAL", "MODELING", "RESEARCH"},
            {chunk["scene"] for chunk in chunks},
        )
        self.assertEqual(4, len({chunk["voice_profile_sha256"] for chunk in chunks}))
        rewrites = self.root / "auto-first-rewrites"
        rewrites.mkdir()
        for unit in chunks:
            bundle = self.voice_bound_bundle(
                unit,
                {"decision": "NO_CHANGE", "reason": "原句已按当前场景直接表达"},
            )
            (rewrites / f"{unit['unit_id']}.json").write_bytes(canonical_json(bundle))
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PASS", result["scene_routing_status"])
        self.assertEqual("PASS", result["voice_binding_status"])
        self.assertTrue(result["voice_profile_set_sha256"])
        self.promote_review_candidate_for_component_test(run_dir)
        return run_dir, rewrites

    def make_personal_first_pass(self) -> tuple[Path, Path]:
        sample_dir = self.root / "voice-samples"
        sample_dir.mkdir()
        samples = []
        for index, marker in enumerate("甲乙丙", 1):
            sample = sample_dir / f"sample-{index}.md"
            sample.write_text(
                "我倾向于先交代判断对象，再说明边界。" + marker * 420,
                encoding="utf-8",
            )
            samples.append(
                {
                    "sample_id": f"sample-{index}",
                    "locator": f"voice-samples/sample-{index}.md",
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        spec_path = self.root / "voice-samples.spec.json"
        spec_path.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-voice-sample-spec/v1",
                    "samples": samples,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest, profile = preparer.voice_profiles.build_voice_profile(
            sample_spec=spec_path,
            allowed_root=self.root,
            profile_id="second-pass-personal-profile",
            scene="RESEARCH",
            source_date_epoch=1710000000,
        )
        self.assertEqual("PERSONAL", profile["profile_kind"])
        profile_path = self.root / "personal-profile.json"
        manifest_path = self.root / "personal-manifest.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        source = self.root / "personal-main.tex"
        source.write_text(
            "\n".join(
                f"\\section{{结果{index}}}\n当前条件下，第{index}组峰值更高。"
                for index in range(1, 7)
            )
            + "\n",
            encoding="utf-8",
        )
        run_dir = self.root / "personal-first-run"
        preparer.prepare(
            [source],
            run_dir,
            scene="RESEARCH",
            min_author_chars=0,
            voice_profile=profile_path,
            voice_profile_sha256=profile["profile_sha256"],
            voice_manifest=manifest_path,
            voice_sample_spec=spec_path,
            voice_allowed_root=self.root,
        )
        units = self.pending_chunks(run_dir)
        self.assertEqual(6, len(units))
        rewrites = self.root / "personal-first-rewrites"
        rewrites.mkdir()
        for unit in units:
            bundle = self.voice_bound_bundle(
                unit,
                {"decision": "NO_CHANGE", "reason": "原句已直接说明对象和边界"},
            )
            (rewrites / f"{unit['unit_id']}.json").write_bytes(canonical_json(bundle))
        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.promote_review_candidate_for_component_test(run_dir)
        return run_dir, rewrites

    def prepare_second(self, *, units: int = 1) -> tuple[Path, Path, Path, Path]:
        first_run, _first_rewrites = self.make_first_pass(units=units)
        second_run = self.root / "second-run"
        cases = self.root / "second-cases"
        plan = second_prepare.prepare_second_pass(first_run, second_run, cases)
        self.assertEqual(units, len(plan["cases"]))
        return first_run, second_run, cases, self.root / "trials"

    def binding_pair(self) -> tuple[FakeAuditor, dict[str, str]]:
        return FakeAuditor(), {
            "skill_snapshot_sha256": FakeAuditor._skill_snapshot(SKILL)[0],
            "contract_sha256": "b" * 64,
            "requirements_sha256": "c" * 64,
            "oracle_catalog_sha256": "d" * 64,
            "trust_policy_sha256": "e" * 64,
        }

    def fake_invoke(self, command, _prompt, _env, _timeout):
        execution = Path(command[command.index("-C") + 1])
        input_path = next((execution / "case").glob("input.*"))
        generation_input = json.loads(input_path.read_text(encoding="utf-8"))
        chunk = generation_input["chunk"]
        output_path = Path(command[command.index("-o") + 1])
        payload = {
            "unit_id": chunk["unit_id"],
            "chunk_binding_sha256": chunk["chunk_binding_sha256"],
            "voice_profile_sha256": chunk["voice_profile_sha256"],
            "decision": self.trial_decision,
            "keep_reasons": {},
        }
        if self.trial_decision == "NO_CHANGE":
            payload["reason"] = "第二遍未发现实质文风改动"
        else:
            payload["masked_text"] = chunk["masked_text"]
        output_path.write_bytes(canonical_json(payload))
        return runner.Invocation(
            command=tuple(command),
            pid=os.getpid(),
            returncode=0,
            stdout=b'{"request_id":"req-1","turn_id":"turn-1"}\n',
            stderr=b"",
            timed_out=False,
            started_at="2026-07-16T00:00:00Z",
            ended_at="2026-07-16T00:00:01Z",
        )

    def run_trials(self, cases: Path, trials: Path) -> None:
        plan = json.loads((cases / "second-pass-plan.json").read_text(encoding="utf-8"))
        with (
            mock.patch.object(runner, "_make_read_only"),
            mock.patch.object(runner.shutil, "which", return_value=sys.executable),
            mock.patch.object(runner, "_codex_version", return_value="codex-cli test"),
            mock.patch.object(runner, "_invoke_codex", side_effect=self.fake_invoke),
        ):
            for item in plan["cases"]:
                runner.run_trial(
                    cases / item["case_path"],
                    trials / item["unit_id"],
                    skill_root=SKILL,
                )

    def complete_second(
        self, *, units: int = 1
    ) -> tuple[Path, Path, Path, Path, Path, dict]:
        first_run, second_run, cases, trials = self.prepare_second(units=units)
        self.run_trials(cases, trials)
        rewrites = self.root / "second-rewrites"
        second_prepare.collect_trial_outputs(second_run, cases, trials, rewrites)
        result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.promote_review_candidate_for_component_test(second_run)
        receipt = second_verify.verify_second_pass(
            first_run, second_run, cases, trials, rewrites
        )
        receipt_path = self.root / "second-pass-receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return first_run, second_run, cases, trials, rewrites, receipt

    @staticmethod
    def rewrite_trial_chain(trial: Path, mutate) -> None:
        receipt_path = trial / "runner-receipt.json"
        record_path = trial / "run-record.json"
        seal_path = trial / "run-seal.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        record = json.loads(record_path.read_text(encoding="utf-8"))
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        mutate(receipt, record, seal)
        receipt_path.write_bytes(canonical_json(receipt))
        record["runner_receipt_sha256"] = sha256(receipt_path.read_bytes())
        record_path.write_bytes(canonical_json(record))
        seal["runner_receipt_sha256"] = sha256(receipt_path.read_bytes())
        seal["run_record_sha256"] = sha256(record_path.read_bytes())
        seal_path.write_bytes(canonical_json(seal))

    def test_prepare_uses_exact_rendered_input_and_prompt_hides_expected_decision(self) -> None:
        first_run, second_run, cases, _trials = self.prepare_second()
        first_rendered = next((first_run / "rendered").rglob("*.tex"))
        second_source = next((second_run / "source").rglob("*.tex"))
        first_meta = json.loads((first_run / "run_metadata.json").read_text(encoding="utf-8"))
        second_meta = json.loads((second_run / "run_metadata.json").read_text(encoding="utf-8"))
        prompt = (cases / "canonical-prompt.txt").read_text(encoding="utf-8")
        plan = json.loads((cases / "second-pass-plan.json").read_text(encoding="utf-8"))
        sealed_input = next(
            (cases / plan["cases"][0]["case_path"]).glob("input.*")
        )
        generation_input = json.loads(sealed_input.read_text(encoding="utf-8"))

        self.assertEqual(first_rendered.read_bytes(), second_source.read_bytes())
        self.assertEqual(first_meta["scene"], second_meta["scene"])
        self.assertEqual(first_meta["budgets"], second_meta["budgets"])
        self.assertEqual(
            first_meta["voice_binding"]["voice_profile_sha256"],
            second_meta["voice_binding"]["voice_profile_sha256"],
        )
        self.assertNotIn("must return NO_CHANGE", prompt)
        self.assertNotIn("expected decision", prompt.lower())
        self.assertNotIn("验收答案", prompt)
        self.assertEqual(second_prepare.GENERATION_INPUT_SCHEMA, generation_input["schema_version"])
        self.assertEqual("DEFAULT", generation_input["voice_profile"]["profile_kind"])
        self.assertFalse(generation_input["voice_profile"]["claims"]["identity_verified"])
        self.assertFalse(generation_input["voice_profile"]["claims"]["sample_text_embedded"])

    def test_structural_first_pass_preserves_intensity_and_unlocks_structure_in_fresh_review(self) -> None:
        source = self.root / "structural.tex"
        source.write_text(
            "\\section{讨论}\n\n第一段说明对象。\n\n第二段说明差别。\n",
            encoding="utf-8",
        )
        first_run = self.root / "structural-first"
        preparer.prepare(
            [source],
            first_run,
            scene="GENERAL",
            intensity="STRUCTURAL",
            min_author_chars=0,
        )
        first_rewrites = self.root / "structural-first-rewrites"
        first_rewrites.mkdir()
        for unit in self.pending_chunks(first_run):
            bundle = self.voice_bound_bundle(
                unit,
                {
                    "decision": "NO_CHANGE",
                    "reason": "当前段落职责与先后关系已经清楚",
                },
            )
            (first_rewrites / f"{unit['unit_id']}.json").write_bytes(
                canonical_json(bundle)
            )
        first_result = finalizer.finalize(first_run, first_rewrites)
        self.assertEqual("PASS", first_result["structural_plan_status"])
        self.assertEqual("REVIEW", first_result["status"])
        self.promote_review_candidate_for_component_test(first_run)

        second_run = self.root / "structural-second"
        cases = self.root / "structural-cases"
        plan = second_prepare.prepare_second_pass(first_run, second_run, cases)
        second_metadata = json.loads(
            (second_run / "run_metadata.json").read_text(encoding="utf-8")
        )
        case = runner.load_public_case(cases / plan["cases"][0]["case_path"])

        self.assertEqual("STRUCTURAL", plan["intensity"])
        self.assertEqual("STRUCTURAL", second_metadata["intensity"])
        self.assertEqual("STRUCTURAL", case.params["intensity"])
        self.assertTrue(case.locks["title_lock"])
        self.assertFalse(case.locks["structure_lock"])
        self.assertIn("structural_plan", second_prepare.CANONICAL_PROMPT)

    def test_personal_profile_is_visible_to_fresh_generator_without_sample_text(self) -> None:
        first_run, _ = self.make_personal_first_pass()
        second_run = self.root / "personal-second-run"
        cases = self.root / "personal-second-cases"
        plan = second_prepare.prepare_second_pass(
            first_run,
            second_run,
            cases,
            voice_allowed_root=self.root,
        )
        self.assertEqual(6, len(plan["cases"]))
        case_root = cases / plan["cases"][0]["case_path"]
        sealed_input = next(case_root.glob("input.*"))
        generation_input = json.loads(sealed_input.read_text(encoding="utf-8"))
        profile = generation_input["voice_profile"]

        self.assertEqual("PERSONAL", profile["profile_kind"])
        self.assertTrue(profile["features"])
        self.assertFalse(profile["claims"]["identity_verified"])
        self.assertFalse(profile["claims"]["sample_text_embedded"])
        serialized = sealed_input.read_text(encoding="utf-8")
        self.assertNotIn("甲" * 40, serialized)
        self.assertNotIn("乙" * 40, serialized)
        self.assertNotIn("丙" * 40, serialized)

        trials = self.root / "personal-trials"
        self.run_trials(cases, trials)
        rewrites = self.root / "personal-second-rewrites"
        second_prepare.collect_trial_outputs(second_run, cases, trials, rewrites)
        second_result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", second_result["status"])
        self.assertEqual("PASS", second_result["candidate_assembly_status"])
        self.assertEqual("REVIEW_CANDIDATE", second_result["publish_state"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            second_result["paired_quality_gate_status"],
        )
        self.assertFalse(second_result["paired_quality_clearance_granted"])
        self.promote_review_candidate_for_component_test(second_run)
        receipt = second_verify.verify_second_pass(
            first_run,
            second_run,
            cases,
            trials,
            rewrites,
        )
        self.assertEqual("PASS", receipt["status"])

    def test_same_scene_chunk_boundary_drift_does_not_block_convergence(self) -> None:
        source = self.root / "compressed.md"
        source.write_text(
            "# 分析\n" + "甲" * 3600 + "\n\n" + "乙" * 3600 + "\n",
            encoding="utf-8",
        )
        first_run = self.root / "compressed-first-run"
        preparer.prepare(
            [source],
            first_run,
            scene="GENERAL",
            max_author_chars=4000,
            min_author_chars=0,
        )
        first_units = self.pending_chunks(first_run)
        self.assertEqual(2, len(first_units))
        first_rewrites = self.root / "compressed-first-rewrites"
        first_rewrites.mkdir()
        for index, unit in enumerate(first_units):
            replacement = unit["masked_text"].replace(
                ("甲" if index == 0 else "乙") * 3600,
                ("甲" if index == 0 else "乙") * 600,
            )
            bundle = self.voice_bound_bundle(
                unit,
                {
                    "decision": "REWRITE",
                    "masked_text": replacement,
                    "keep_reasons": {},
                },
            )
            (first_rewrites / f"{unit['unit_id']}.json").write_bytes(
                canonical_json(bundle)
            )
        first_result = finalizer.finalize(first_run, first_rewrites)
        self.assertEqual("REVIEW", first_result["status"])
        self.promote_review_candidate_for_component_test(first_run)

        second_run = self.root / "compressed-second-run"
        cases = self.root / "compressed-second-cases"
        plan = second_prepare.prepare_second_pass(first_run, second_run, cases)
        self.assertEqual(1, len(plan["cases"]))
        trials = self.root / "compressed-trials"
        self.run_trials(cases, trials)
        rewrites = self.root / "compressed-second-rewrites"
        second_prepare.collect_trial_outputs(second_run, cases, trials, rewrites)
        second_result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", second_result["status"])
        self.promote_review_candidate_for_component_test(second_run)
        receipt = second_verify.verify_second_pass(
            first_run,
            second_run,
            cases,
            trials,
            rewrites,
        )
        self.assertEqual("PASS", receipt["status"])

    def test_second_pass_rebuilds_include_graph_from_original_seeds(self) -> None:
        main = self.root / "graph-main.tex"
        model = self.root / "graph-model.tex"
        weak = self.root / "graph-weak.tex"
        main.write_text(
            "\\input{graph-model}\n\\input{graph-weak}\n",
            encoding="utf-8",
        )
        model.write_text(
            "\\section{模型建立}\n建立状态变量并设置参数，随后进行数值求解。\n",
            encoding="utf-8",
        )
        weak.write_text(
            "\\section{附录小结}\n参数设置沿用前文。\n",
            encoding="utf-8",
        )
        first_run = self.root / "graph-first-run"
        preparer.prepare([main], first_run, scene="AUTO", min_author_chars=0)
        first_units = self.pending_chunks(first_run)
        weak_first = next(item for item in first_units if "参数设置沿用前文" in item["masked_text"])
        self.assertEqual("ROUTED", weak_first["scene_routing_decision"])
        first_rewrites = self.root / "graph-first-rewrites"
        first_rewrites.mkdir()
        for unit in first_units:
            bundle = self.voice_bound_bundle(
                unit,
                {"decision": "NO_CHANGE", "reason": "原句已按当前场景直接表达"},
            )
            (first_rewrites / f"{unit['unit_id']}.json").write_bytes(canonical_json(bundle))
        first_result = finalizer.finalize(first_run, first_rewrites)
        self.assertEqual("REVIEW", first_result["status"])
        self.promote_review_candidate_for_component_test(first_run)

        second_run = self.root / "graph-second-run"
        cases = self.root / "graph-second-cases"
        second_prepare.prepare_second_pass(first_run, second_run, cases)
        with (second_run / "file_manifest.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            second_manifest = list(csv.DictReader(handle))
        self.assertEqual(1, sum(row["relation"] == "seed" for row in second_manifest))
        self.assertEqual(2, sum(bool(row["parent_file_id"]) for row in second_manifest))
        weak_second = next(
            item
            for item in self.pending_chunks(second_run)
            if "参数设置沿用前文" in item["masked_text"]
        )
        self.assertEqual("MODELING", weak_second["scene"])
        self.assertEqual("ROUTED", weak_second["scene_routing_decision"])

    def test_prepare_rejects_files_hidden_outside_the_first_rendered_manifest(self) -> None:
        first_run, _first_rewrites = self.make_first_pass()
        (first_run / "rendered" / "unmanifested.tex").write_text(
            "未进入 manifest 的正文。", encoding="utf-8"
        )

        with self.assertRaisesRegex(
            second_prepare.SecondPassPreparationError, "manifest"
        ):
            second_prepare.prepare_second_pass(
                first_run,
                self.root / "second-run",
                self.root / "second-cases",
            )

    @staticmethod
    def mutate_rendered_manifest(first_run: Path, mutation) -> None:
        path = first_run / "rendered_manifest.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = list(reader.fieldnames or [])
        mutation(rows, fields)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_prepare_accepts_scoped_rendered_manifest(self) -> None:
        first_run, _first_rewrites = self.make_first_pass()
        inputs, rows, _metadata = second_prepare._first_pass_inputs(first_run)
        self.assertEqual(1, len(inputs))
        self.assertEqual("LIVE_LOCATION_LABEL_NOT_HASH_TARGET", rows[0]["source_path_scope"])
        self.assertEqual("RENDERED_CANDIDATE_BYTES", rows[0]["sha256_scope"])
        self.assertEqual(rows[0]["sha256"], rows[0]["rendered_sha256"])

    def test_prepare_rejects_tampered_rendered_manifest_scope(self) -> None:
        for field in ("source_path_scope", "sha256_scope"):
            with self.subTest(field=field):
                first_run, _first_rewrites = self.make_first_pass()
                self.mutate_rendered_manifest(
                    first_run,
                    lambda rows, _fields, field=field: rows[0].__setitem__(field, "UNTRUSTED"),
                )
                with self.assertRaisesRegex(
                    second_prepare.SecondPassPreparationError, "scope"
                ):
                    second_prepare._first_pass_inputs(first_run)
                shutil.rmtree(first_run)
                shutil.rmtree(self.root / "first-rewrites")

    def test_prepare_rejects_disagreeing_rendered_hash_aliases(self) -> None:
        first_run, _first_rewrites = self.make_first_pass()
        self.mutate_rendered_manifest(
            first_run,
            lambda rows, _fields: rows[0].__setitem__("rendered_sha256", "0" * 64),
        )
        with self.assertRaisesRegex(
            second_prepare.SecondPassPreparationError, "aliases disagree"
        ):
            second_prepare._first_pass_inputs(first_run)

    def test_prepare_rejects_unknown_rendered_manifest_column(self) -> None:
        first_run, _first_rewrites = self.make_first_pass()

        def add_unknown(rows, fields):
            fields.append("future_unreviewed_field")
            for row in rows:
                row["future_unreviewed_field"] = "value"

        self.mutate_rendered_manifest(first_run, add_unknown)
        with self.assertRaisesRegex(
            second_prepare.SecondPassPreparationError, "fields are invalid"
        ):
            second_prepare._first_pass_inputs(first_run)

    def test_all_second_pass_csv_readers_reject_duplicate_headers(self) -> None:
        path = self.root / "duplicate-header.csv"
        path.write_text("file_id,file_id,bytes\nF00001,F99999,1\n", encoding="utf-8")
        cases = (
            (finalizer._load_csv, ValueError),
            (second_prepare._load_csv, second_prepare.SecondPassPreparationError),
            (second_verify._load_csv, second_verify.SecondPassVerificationError),
        )
        for loader, error in cases:
            with self.subTest(loader=loader.__module__):
                with self.assertRaisesRegex(error, "duplicated|malformed"):
                    loader(path)

    def test_all_second_pass_csv_readers_reject_row_width_mismatch(self) -> None:
        cases = {
            "short": "file_id,rendered_path,bytes\nF00001,main.tex\n",
            "long": "file_id,rendered_path\nF00001,main.tex,unexpected\n",
        }
        loaders = (
            (finalizer._load_csv, ValueError),
            (second_prepare._load_csv, second_prepare.SecondPassPreparationError),
            (second_verify._load_csv, second_verify.SecondPassVerificationError),
        )
        for label, raw in cases.items():
            path = self.root / f"row-width-{label}.csv"
            path.write_text(raw, encoding="utf-8")
            for loader, error in loaders:
                with self.subTest(case=label, loader=loader.__module__):
                    with self.assertRaisesRegex(error, "row width|malformed"):
                        loader(path)

    def test_missing_trial_is_review_not_pass(self) -> None:
        first_run, second_run, cases, trials = self.prepare_second()
        trials.mkdir()
        rewrites = self.root / "second-rewrites"
        rewrites.mkdir()
        result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", result["status"])
        with self.assertRaises(second_verify.SecondPassNotConverged):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_collect_rejects_code_fence_duplicate_key_and_wrong_binding(self) -> None:
        first_run, second_run, cases, trials = self.prepare_second()
        plan = json.loads((cases / "second-pass-plan.json").read_text(encoding="utf-8"))
        unit_id = plan["cases"][0]["unit_id"]
        chunk = self.pending_chunks(second_run)[0]
        output = trials / unit_id / "response" / "output.txt"
        output.parent.mkdir(parents=True)
        valid = self.voice_bound_bundle(
            chunk,
            {"decision": "NO_CHANGE", "reason": "当前表达无需实质调整"},
        )
        invalid_outputs = {
            "code fence": "```json\n" + json.dumps(valid, ensure_ascii=False) + "\n```",
            "duplicate key": (
                json.dumps(valid, ensure_ascii=False)[:-1]
                + ',"decision":"REWRITE"}'
            ),
            "wrong binding": json.dumps(
                {**valid, "chunk_binding_sha256": "0" * 64},
                ensure_ascii=False,
            ),
        }
        for label, raw in invalid_outputs.items():
            with self.subTest(label=label):
                output.write_text(raw, encoding="utf-8")
                rewrites = self.root / f"rewrites-{label.replace(' ', '-')}"
                with self.assertRaises(ValueError):
                    second_prepare.collect_trial_outputs(
                        second_run, cases, trials, rewrites
                    )

    def test_collect_rejects_a_self_consistent_plan_that_exposes_expected_outcome(self) -> None:
        _first_run, second_run, cases, trials = self.prepare_second()
        plan_path = cases / "second-pass-plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        unit_id = plan["cases"][0]["unit_id"]
        chunk = self.pending_chunks(second_run)[0]
        output = trials / unit_id / "response" / "output.txt"
        output.parent.mkdir(parents=True)
        output.write_bytes(
            canonical_json(
                self.voice_bound_bundle(
                    chunk,
                    {"decision": "NO_CHANGE", "reason": "当前表达无需实质调整"},
                )
            )
        )
        plan["claims"]["expected_outcome_exposed"] = True
        unsigned = dict(plan)
        unsigned.pop("plan_sha256")
        plan["plan_sha256"] = sha256(canonical_json(unsigned))
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            second_prepare.SecondPassPreparationError, "expected outcome"
        ):
            second_prepare.collect_trial_outputs(
                second_run,
                cases,
                trials,
                self.root / "second-rewrites",
            )

    def test_any_fresh_rewrite_keeps_convergence_in_review(self) -> None:
        first_run, second_run, cases, trials = self.prepare_second()
        self.trial_decision = "REWRITE"
        self.run_trials(cases, trials)
        rewrites = self.root / "second-rewrites"
        second_prepare.collect_trial_outputs(second_run, cases, trials, rewrites)
        result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", result["status"])

        with self.assertRaises(second_verify.SecondPassNotConverged):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_receipt_and_run_record_must_share_run_id(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second()
        unit_id = self.pending_chunks(second_run)[0]["unit_id"]

        self.rewrite_trial_chain(
            trials / unit_id,
            lambda receipt, _record, _seal: receipt.update({"run_id": "RUN-forged"}),
        )

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "run id"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_each_unit_requires_a_distinct_fresh_run_id(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second(units=2)
        unit_ids = [unit["unit_id"] for unit in self.pending_chunks(second_run)]
        first_record = json.loads(
            (trials / unit_ids[0] / "run-record.json").read_text(encoding="utf-8")
        )
        duplicate_run_id = first_record["run_id"]

        def duplicate(_receipt, record, seal):
            _receipt["run_id"] = duplicate_run_id
            record["run_id"] = duplicate_run_id
            seal["run_id"] = duplicate_run_id

        self.rewrite_trial_chain(trials / unit_ids[1], duplicate)

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "duplicate run id"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_projection_evidence_must_match_receipt_record_and_seal(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second()
        unit_id = self.pending_chunks(second_run)[0]["unit_id"]

        def drift(receipt, _record, _seal):
            receipt["generator_projection"]["tree_sha256"] = "9" * 64

        self.rewrite_trial_chain(trials / unit_id, drift)

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "projection"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_live_projected_skill_drift_invalidates_the_trial(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second()
        unit_id = self.pending_chunks(second_run)[0]["unit_id"]
        projected_skill = trials / unit_id / "execution" / "skill" / "SKILL.md"
        projected_skill.write_text(
            projected_skill.read_text(encoding="utf-8") + "\n漂移。\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "projection"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_generator_context_cannot_be_relabelled_complete(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second()
        unit_id = self.pending_chunks(second_run)[0]["unit_id"]

        def overclaim(_receipt, record, _seal):
            record["generator_context"]["complete"] = True

        self.rewrite_trial_chain(trials / unit_id, overclaim)

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "generator context"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_runner_isolation_subrecord_cannot_overclaim_oracle_unreachability(self) -> None:
        first_run, second_run, cases, trials, rewrites, _receipt = self.complete_second()
        unit_id = self.pending_chunks(second_run)[0]["unit_id"]

        def overclaim(receipt, _record, _seal):
            receipt["isolation"]["oracle_catalog_unreachable_to_generator"] = "VERIFIED"

        self.rewrite_trial_chain(trials / unit_id, overclaim)

        with self.assertRaisesRegex(
            second_verify.SecondPassVerificationError, "isolation"
        ):
            second_verify.verify_second_pass(
                first_run, second_run, cases, trials, rewrites
            )

    def test_valid_fresh_no_change_trials_issue_pass_receipt(self) -> None:
        first_run, second_run, cases, trials, rewrites, receipt = self.complete_second(units=2)

        self.assertEqual("PASS", receipt["status"])
        self.assertTrue(receipt["all_units_no_change"])
        self.assertTrue(receipt["second_output_equals_first"])
        self.assertEqual(2, receipt["units_total"])
        self.assertFalse(receipt["claims"]["filesystem_isolation_verified"])
        self.assertEqual("E2", receipt["evidence_cap"])
        self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")

        with (second_run / "coverage_ledger.final.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            {"NO_CHANGE"},
            {row["status"] for row in rows if row["unit_id"] in {
                item["unit_id"] for item in receipt["fresh_processes"]
            }},
        )
        self.assertTrue((cases / "second-pass-plan.json").is_file())
        self.assertTrue((trials / "second-pass-collection.json").is_file())
        self.assertTrue(rewrites.is_dir())
        self.assertTrue(first_run.is_dir())

    def test_auto_profile_set_survives_full_fresh_second_pass_chain(self) -> None:
        first_run, first_rewrites = self.make_auto_first_pass()
        second_run = self.root / "auto-second-run"
        cases = self.root / "auto-second-cases"
        plan = second_prepare.prepare_second_pass(first_run, second_run, cases)
        self.assertEqual(4, len(plan["cases"]))
        self.assertEqual(
            json.loads((first_run / "finalization_metadata.json").read_text(encoding="utf-8"))[
                "voice_binding_sha256"
            ],
            plan["voice_binding_sha256"],
        )
        trials = self.root / "auto-second-trials"
        self.run_trials(cases, trials)
        rewrites = self.root / "auto-second-rewrites"
        second_prepare.collect_trial_outputs(second_run, cases, trials, rewrites)
        second_result = finalizer.finalize(second_run, rewrites)
        self.assertEqual("REVIEW", second_result["status"])
        self.assertEqual("PASS", second_result["scene_routing_status"])
        self.promote_review_candidate_for_component_test(second_run)
        receipt = second_verify.verify_second_pass(
            first_run, second_run, cases, trials, rewrites
        )
        receipt_path = self.root / "auto-second-pass-receipt.json"
        receipt_path.write_bytes(canonical_json(receipt))

        completed = finalizer.finalize(
            first_run,
            first_rewrites,
            second_pass_receipt=receipt_path,
        )

        self.assertEqual("FAIL", completed["status"])
        self.assertEqual("FAIL", completed["humanize_second_pass_convergence"])
        self.assertEqual("INVALID_EVIDENCE", completed["second_pass_stability_status"])
        self.assertFalse(completed["second_pass_quality_clearance_granted"])
        self.assertFalse(completed["humanize_completion_claim_allowed"])
        self.assertEqual(
            completed["voice_binding_sha256"], receipt["voice_binding_sha256"]
        )

    def test_finalizer_revalidates_receipt_evidence_instead_of_trusting_self_hash(self) -> None:
        first_run, _second_run, _cases, trials, _rewrites, receipt = self.complete_second()
        receipt_path = self.root / "second-pass-receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(trials)

        first_rewrites = self.root / "first-rewrites"
        result = finalizer.finalize(
            first_run,
            first_rewrites,
            second_pass_receipt=receipt_path,
        )

        self.assertEqual("FAIL", result["status"])
        self.assertEqual("FAIL", result["humanize_second_pass_convergence"])
        self.assertFalse(result["humanize_completion_claim_allowed"])

    def test_finalizer_rejects_live_convergence_as_paired_quality_clearance(self) -> None:
        first_run, _second_run, _cases, _trials, _rewrites, receipt = self.complete_second()
        receipt_path = self.root / "second-pass-receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = finalizer.finalize(
            first_run,
            self.root / "first-rewrites",
            second_pass_receipt=receipt_path,
        )

        self.assertEqual("FAIL", result["status"])
        self.assertEqual("FAIL", result["humanize_second_pass_convergence"])
        self.assertEqual("INVALID_EVIDENCE", result["second_pass_stability_status"])
        self.assertFalse(result["second_pass_quality_clearance_granted"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse(result["full_completion_claim_allowed"])

    def test_finalizer_verifier_loader_ignores_same_name_module_injection(self) -> None:
        injected = types.SimpleNamespace(
            __file__=str(self.root / "verify_humanize_second_pass.py"),
            verify_second_pass=lambda *_args: {"status": "PASS"},
        )
        original = sys.modules.get("verify_humanize_second_pass")
        sys.modules["verify_humanize_second_pass"] = injected
        try:
            loaded = finalizer._load_second_pass_verifier()
        finally:
            if original is None:
                sys.modules.pop("verify_humanize_second_pass", None)
            else:
                sys.modules["verify_humanize_second_pass"] = original

        self.assertIsNot(injected, loaded)
        self.assertEqual(
            (SKILL / "scripts" / "verify_humanize_second_pass.py").resolve(),
            Path(loaded.__file__).resolve(),
        )


if __name__ == "__main__":
    unittest.main()
