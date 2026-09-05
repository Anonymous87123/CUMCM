import csv
import importlib.util
import json
import os
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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


voice = load_module(
    "build_humanize_voice_profile",
    SKILL / "scripts" / "build_humanize_voice_profile.py",
)
preparer = load_module(
    "prepare_humanize_long_document",
    SKILL / "scripts" / "prepare_humanize_long_document.py",
)
finalizer = load_module(
    "finalize_humanize_long_document",
    SKILL / "scripts" / "finalize_humanize_long_document.py",
)


class LongDocumentVoiceBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def prepare(self, *, supplied: bool = False) -> tuple[Path, Path, dict]:
        source = self.root / "main.md"
        source.write_text("# 结果\n该段保持原有的简短判断。\n", encoding="utf-8")
        output = self.root / "run"
        kwargs = {}
        if supplied:
            profile = voice.build_scene_default_profile("RESEARCH")
            profile_path = self.root / "profile.json"
            profile_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            kwargs = {
                "voice_profile": profile_path,
                "voice_profile_sha256": profile["profile_sha256"],
            }
        preparer.prepare(
            [source],
            output,
            scene="RESEARCH",
            min_author_chars=0,
            **kwargs,
        )
        chunks = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (output / "chunks").glob("*.json")
        ]
        return source, output, next(item for item in chunks if item["status"] == "PENDING")

    def rewrite_dir(self, unit: dict, *, hash_value: str | None) -> Path:
        path = self.root / "rewrites"
        path.mkdir(exist_ok=True)
        payload = {
            "unit_id": unit["unit_id"],
            "chunk_binding_sha256": unit["chunk_binding_sha256"],
            "decision": "NO_CHANGE",
            "reason": "该段保持原有的自然简短判断",
        }
        if hash_value is not None:
            payload["voice_profile_sha256"] = hash_value
        (path / f"{unit['unit_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_default_profile_is_materialized_and_bound_in_every_prepare_artifact(self) -> None:
        _, run_dir, chunk = self.prepare()
        profile_path = run_dir / "voice_profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        unit = json.loads((run_dir / "units.jsonl").read_text(encoding="utf-8").splitlines()[0])
        with (run_dir / "coverage_ledger.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            ledger = next(csv.DictReader(handle))
        integrity = json.loads((run_dir / "prepare_integrity.json").read_text(encoding="utf-8"))

        expected = voice.build_scene_default_profile("RESEARCH")
        self.assertEqual(expected, profile)
        self.assertEqual("DEFAULT", profile["profile_kind"])
        self.assertTrue(profile["defaults"]["disclosure_required"])
        for record in (metadata["voice_binding"], unit, chunk, ledger):
            self.assertEqual(profile["profile_sha256"], record["voice_profile_sha256"])
            self.assertEqual(profile["profile_id"], record["voice_profile_id"])
            self.assertEqual("RESEARCH", record["voice_profile_binding_scene"])
        self.assertEqual(chunk["chunk_binding_sha256"], unit["chunk_binding_sha256"])
        self.assertEqual(chunk["chunk_binding_sha256"], ledger["chunk_binding_sha256"])
        self.assertEqual(
            chunk["chunk_binding_sha256"], preparer.chunk_binding_sha256(chunk)
        )
        self.assertEqual("RESEARCH", metadata["voice_binding"]["profile_binding_scene"])
        self.assertEqual("RESEARCH", metadata["voice_binding"]["binding_scene"])
        self.assertEqual("RESEARCH", metadata["voice_binding"]["requested_scene"])
        self.assertIn("voice_profile.json", {item["path"] for item in integrity["artifacts"]})

    def test_default_profiles_are_rejected_when_request_scene_differs(self) -> None:
        source = self.root / "scene-target.md"
        source.write_text("# 结果\n该段保持原有判断。\n", encoding="utf-8")
        for index, (profile_scene, requested_scene) in enumerate(
            (("GENERAL", "RESEARCH"), ("COURSE", "AUTO")), 1
        ):
            with self.subTest(profile_scene=profile_scene, requested_scene=requested_scene):
                profile = voice.build_scene_default_profile(profile_scene)
                profile_path = self.root / f"scene-profile-{index}.json"
                profile_path.write_text(
                    json.dumps(profile, ensure_ascii=False), encoding="utf-8"
                )
                expected_error = (
                    "AUTO_does_not_accept_single_voice_profile"
                    if requested_scene == "AUTO"
                    else "voice_profile_scene_mismatch"
                )
                with self.assertRaisesRegex(ValueError, expected_error):
                    preparer.prepare(
                        [source],
                        self.root / f"scene-run-{index}",
                        scene=requested_scene,
                        min_author_chars=0,
                        voice_profile=profile_path,
                        voice_profile_sha256=profile["profile_sha256"],
                    )

    def test_supplied_profile_requires_exact_expected_hash_and_is_snapshotted(self) -> None:
        _, run_dir, chunk = self.prepare(supplied=True)
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual("SUPPLIED", metadata["voice_binding"]["profile_source"])
        self.assertEqual(chunk["voice_profile_sha256"], metadata["voice_binding"]["voice_profile_sha256"])

        bad_output = self.root / "bad-run"
        source = self.root / "other.md"
        source.write_text("正文。\n", encoding="utf-8")
        profile_path = self.root / "profile.json"
        with self.assertRaisesRegex(ValueError, "voice_profile_sha256_mismatch"):
            preparer.prepare(
                [source],
                bad_output,
                scene="RESEARCH",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256="0" * 64,
            )

    def test_missing_or_wrong_bundle_hash_is_reviewed_before_text_validation(self) -> None:
        _, run_dir, unit = self.prepare()
        missing = finalizer.finalize(run_dir, self.rewrite_dir(unit, hash_value=None))
        self.assertEqual("REVIEW", missing["status"])
        self.assertEqual("REVIEW", missing["voice_binding_status"])
        with (run_dir / "coverage_ledger.final.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual("UNRESOLVED", row["status"])
        self.assertIn("voice_profile_hash_missing", row["notes"])

        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        _, run_dir, unit = self.prepare()
        wrong = finalizer.finalize(run_dir, self.rewrite_dir(unit, hash_value="f" * 64))
        self.assertEqual("REVIEW", wrong["status"])
        self.assertEqual("REVIEW", wrong["voice_binding_status"])

    def test_duplicate_voice_hash_json_key_is_rejected(self) -> None:
        _, run_dir, unit = self.prepare()
        rewrites = self.root / "duplicate-key-rewrites"
        rewrites.mkdir()
        (rewrites / f"{unit['unit_id']}.json").write_text(
            "{"
            '"decision":"NO_CHANGE",'
            '"reason":"该段保持原有自然判断",'
            '"voice_profile_sha256":"' + "f" * 64 + '",'
            '"voice_profile_sha256":"' + unit["voice_profile_sha256"] + '"'
            "}",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "duplicate JSON key: voice_profile_sha256"):
            finalizer.finalize(run_dir, rewrites)

    def test_correct_default_bundle_passes_non_personal_voice_conformance(self) -> None:
        _, run_dir, unit = self.prepare()
        result = finalizer.finalize(
            run_dir,
            self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW", result["paired_quality_gate_status"]
        )
        self.assertEqual("PASS", result["voice_binding_status"])
        self.assertEqual("PASS", result["voice_conformance_status"])
        self.assertEqual(
            "SCENE_DEFAULT_UNIT_VALIDATION", result["voice_conformance"]["basis"]
        )
        self.assertFalse(
            result["voice_conformance"]["personal_voice_claim_allowed"]
        )
        self.assertEqual("REVIEW", result["authoring_binding_status"])
        self.assertFalse(result["voice_completion_claim_allowed"])
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse(result["full_completion_claim_allowed"])

    def test_auto_scene_fallback_is_routed_and_bound_after_finalize(self) -> None:
        source = self.root / "auto.md"
        source.write_text("# 结果\n该段保持原有判断。\n", encoding="utf-8")
        run_dir = self.root / "auto-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        profile_set = json.loads(
            (run_dir / "voice_profile_set.json").read_text(encoding="utf-8")
        )
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )

        self.assertEqual(
            {"COURSE", "GENERAL", "MODELING", "RESEARCH"},
            set(profile_set["profiles"]),
        )
        self.assertEqual("AUTO", metadata["voice_binding"]["requested_scene"])
        self.assertEqual("UNIT_ROUTED", metadata["voice_binding"]["scene_binding_status"])
        self.assertEqual("GENERAL", unit["scene"])
        self.assertEqual("FALLBACK_GENERAL", unit["scene_routing_decision"])
        result = finalizer.finalize(
            run_dir,
            self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
        )
        self.assertEqual("PASS", result["voice_binding_status"])
        self.assertEqual("PASS", result["rewrite_binding_status"])
        self.assertEqual("PASS", result["scene_routing_status"])
        self.assertEqual(
            profile_set["profile_set_sha256"], result["voice_profile_set_sha256"]
        )
        self.assertFalse(result["humanize_completion_claim_allowed"])
        self.assertFalse(result["full_completion_claim_allowed"])

    def test_auto_profile_set_cannot_overclaim_identity_after_full_local_reseal(self) -> None:
        source = self.root / "auto-overclaim.md"
        source.write_text("# 背景\n该段保持原有判断。\n", encoding="utf-8")
        run_dir = self.root / "auto-overclaim-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        profile_set_path = run_dir / "voice_profile_set.json"
        profile_set = json.loads(profile_set_path.read_text(encoding="utf-8"))
        profile_set["claims"]["identity_verified"] = True
        unsigned = dict(profile_set)
        unsigned.pop("profile_set_sha256")
        new_hash = preparer.sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        profile_set["profile_set_sha256"] = new_hash
        profile_set_path.write_text(
            json.dumps(profile_set, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["voice_binding"]["profile_set_sha256"] = new_hash
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

        with self.assertRaisesRegex(ValueError, "claims"):
            finalizer.finalize(
                run_dir,
                self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
            )

    def test_auto_profile_set_entry_cannot_hide_authority_claim_after_reseal(self) -> None:
        source = self.root / "auto-entry-overclaim.md"
        source.write_text("# 背景\n该段保持原有判断。\n", encoding="utf-8")
        run_dir = self.root / "auto-entry-overclaim-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        profile_set_path = run_dir / "voice_profile_set.json"
        profile_set = json.loads(profile_set_path.read_text(encoding="utf-8"))
        profile_set["profiles"]["GENERAL"]["identity_verified"] = True
        unsigned = dict(profile_set)
        unsigned.pop("profile_set_sha256")
        new_hash = preparer.sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        profile_set["profile_set_sha256"] = new_hash
        profile_set_path.write_text(
            json.dumps(profile_set, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["voice_binding"]["profile_set_sha256"] = new_hash
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

        with self.assertRaisesRegex(ValueError, "entry keys mismatch"):
            finalizer.finalize(
                run_dir,
                self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
            )

    def test_auto_metadata_binding_cannot_hide_authority_claim_after_reseal(self) -> None:
        source = self.root / "auto-metadata-overclaim.md"
        source.write_text("# 背景\n该段保持原有判断。\n", encoding="utf-8")
        run_dir = self.root / "auto-metadata-overclaim-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        metadata_path = run_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["voice_binding"]["identity_verified"] = True
        metadata["voice_binding"]["external_clearance"] = "VERIFIED_HUMAN"
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

        with self.assertRaisesRegex(ValueError, "metadata keys mismatch"):
            finalizer.finalize(
                run_dir,
                self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
            )

    def test_auto_bundle_cannot_borrow_another_scenes_valid_voice_hash(self) -> None:
        source = self.root / "auto-cross-scene.md"
        source.write_text(
            "# 例题与解析\n本题先辨认条件，再代入公式。\n\n"
            "# 模型建立\n建立状态变量并设置参数，随后进行数值求解。\n",
            encoding="utf-8",
        )
        run_dir = self.root / "auto-cross-scene-run"
        preparer.prepare([source], run_dir, scene="AUTO", min_author_chars=0)
        units = sorted(
            (
                json.loads(path.read_text(encoding="utf-8"))
                for path in (run_dir / "chunks").glob("*.json")
                if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
            ),
            key=lambda item: item["start"],
        )
        self.assertEqual(["COURSE", "MODELING"], [item["scene"] for item in units])
        rewrites = self.root / "cross-scene-rewrites"
        rewrites.mkdir()
        payload = {
            "unit_id": units[0]["unit_id"],
            "chunk_binding_sha256": units[0]["chunk_binding_sha256"],
            "voice_profile_sha256": units[1]["voice_profile_sha256"],
            "decision": "NO_CHANGE",
            "reason": "题解已经直接说明判断条件",
        }
        (rewrites / f"{units[0]['unit_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

        result = finalizer.finalize(run_dir, rewrites)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("REVIEW", result["voice_binding_status"])
        with (run_dir / "coverage_ledger.final.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            row = next(
                item
                for item in csv.DictReader(handle)
                if item["unit_id"] == units[0]["unit_id"]
            )
        self.assertIn("voice_profile_hash_mismatch", row["notes"])

    def test_profile_artifact_drift_is_a_hard_integrity_failure(self) -> None:
        _, run_dir, unit = self.prepare()
        profile_path = run_dir / "voice_profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["revision"] += 1
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            r"integrity artifact bytes mismatch: voice_profile\.json",
        ):
            finalizer.finalize(
                run_dir,
                self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
            )

    def test_personal_profile_requires_manifest_spec_and_source_rebuild(self) -> None:
        sample_dir = self.root / "samples"
        sample_dir.mkdir()
        samples = []
        for index, filler in enumerate("甲乙丙", 1):
            path = sample_dir / f"sample-{index}.md"
            path.write_text("本文说明" + filler * 396, encoding="utf-8")
            samples.append(
                {
                    "sample_id": f"sample-{index}",
                    "locator": f"samples/sample-{index}.md",
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        spec_path = self.root / "samples.spec.json"
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
        manifest, profile = voice.build_voice_profile(
            sample_spec=spec_path,
            allowed_root=self.root,
            profile_id="verified-personal-profile",
            scene="RESEARCH",
            source_date_epoch=1710000000,
        )
        self.assertEqual("PERSONAL", profile["profile_kind"])
        self.assertEqual("PASS", profile["validation_status"])
        profile_path = self.root / "personal-profile.json"
        manifest_path = self.root / "personal-manifest.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        source = self.root / "target.md"
        source.write_text("# 结果\n该段保持原有判断。\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "personal_voice_profile_requires_rebuild_evidence"):
            preparer.prepare(
                [source],
                self.root / "missing-evidence-run",
                scene="RESEARCH",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256=profile["profile_sha256"],
            )

        run_dir = self.root / "personal-run"
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
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual("REBUILT_PASS", metadata["voice_binding"]["voice_evidence_status"])
        self.assertTrue((run_dir / "voice_sample_manifest.json").is_file())
        self.assertTrue((run_dir / "voice_sample_spec.json").is_file())

        with self.assertRaisesRegex(ValueError, "voice_profile_scene_mismatch"):
            preparer.prepare(
                [source],
                self.root / "personal-scene-mismatch-run",
                scene="COURSE",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256=profile["profile_sha256"],
                voice_manifest=manifest_path,
                voice_sample_spec=spec_path,
                voice_allowed_root=self.root,
            )

        personal_sample = sample_dir / "sample-1.md"
        personal_sample.write_text(
            personal_sample.read_text(encoding="utf-8") + "样本发生漂移",
            encoding="utf-8",
        )
        stale_run = self.root / "personal-stale-evidence-run"
        with self.assertRaisesRegex(ValueError, "rebuilt sample evidence differs"):
            preparer.prepare(
                [source],
                stale_run,
                scene="RESEARCH",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256=profile["profile_sha256"],
                voice_manifest=manifest_path,
                voice_sample_spec=spec_path,
                voice_allowed_root=self.root,
            )
        self.assertFalse(stale_run.exists())

        frozen_spec_path = run_dir / "voice_sample_spec.json"
        frozen_spec = json.loads(frozen_spec_path.read_text(encoding="utf-8"))
        for sample_record in frozen_spec["samples"]:
            sample_record["origin"] = "MODEL_GENERATED"
        frozen_spec_path.write_text(
            json.dumps(frozen_spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        with self.assertRaisesRegex(
            ValueError, "frozen voice sample spec does not match manifest"
        ):
            finalizer.finalize(
                run_dir,
                self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
            )

    def test_personal_review_profile_is_rejected_before_prepare(self) -> None:
        sample_dir = self.root / "review-samples"
        sample_dir.mkdir()
        base = "本文认为" + "甲" * 4996
        samples = []
        for index, text in enumerate((base, base[:-1] + "乙", base[:-1] + "丙"), 1):
            path = sample_dir / f"sample-{index}.md"
            path.write_text(text, encoding="utf-8")
            samples.append(
                {
                    "sample_id": f"review-sample-{index}",
                    "locator": f"review-samples/sample-{index}.md",
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        spec_path = self.root / "review.spec.json"
        spec_path.write_text(
            json.dumps(
                {"schema_version": "humanize-voice-sample-spec/v1", "samples": samples},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest, profile = voice.build_voice_profile(
            sample_spec=spec_path,
            allowed_root=self.root,
            profile_id="review-personal-profile",
            scene="RESEARCH",
            source_date_epoch=1710000000,
        )
        self.assertEqual("PERSONAL", profile["profile_kind"])
        self.assertEqual("REVIEW", profile["validation_status"])
        profile_path = self.root / "review-profile.json"
        manifest_path = self.root / "review-manifest.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        source = self.root / "review-target.md"
        source.write_text("# 结果\n该段保持原有判断。\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "voice_profile_status_not_pass"):
            preparer.prepare(
                [source],
                self.root / "review-run",
                scene="RESEARCH",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256=profile["profile_sha256"],
                voice_manifest=manifest_path,
                voice_sample_spec=spec_path,
                voice_allowed_root=self.root,
            )

    def test_evidence_bound_default_from_insufficient_sample_is_consumable(self) -> None:
        sample = self.root / "short-sample.md"
        sample.write_text("本文说明" + "甲" * 236, encoding="utf-8")
        spec_path = self.root / "short.spec.json"
        spec_path.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-voice-sample-spec/v1",
                    "samples": [
                        {
                            "sample_id": "short-sample",
                            "locator": "short-sample.md",
                            "origin": "USER_CONFIRMED_AUTHOR",
                            "scene": "RESEARCH",
                            "complete_unit": True,
                            "default_role": "author",
                            "role_ranges": [],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest, profile = voice.build_voice_profile(
            sample_spec=spec_path,
            allowed_root=self.root,
            profile_id="short-default-profile",
            scene="RESEARCH",
            source_date_epoch=1710000000,
        )
        self.assertEqual("DEFAULT", profile["profile_kind"])
        self.assertNotEqual("0" * 64, profile["sample_binding"]["manifest_sha256"])
        profile_path = self.root / "short-profile.json"
        manifest_path = self.root / "short-manifest.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        target = self.root / "target-short.md"
        target.write_text("# 结果\n该段保持原有判断。\n", encoding="utf-8")
        run_dir = self.root / "short-run"

        preparer.prepare(
            [target],
            run_dir,
            scene="RESEARCH",
            min_author_chars=0,
            voice_profile=profile_path,
            voice_profile_sha256=profile["profile_sha256"],
            voice_manifest=manifest_path,
            voice_sample_spec=spec_path,
            voice_allowed_root=self.root,
        )

        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual("REBUILT_DEFAULT_PASS", metadata["voice_binding"]["voice_evidence_status"])
        unit = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (run_dir / "chunks").glob("*.json")
            if json.loads(path.read_text(encoding="utf-8"))["status"] == "PENDING"
        )
        result = finalizer.finalize(
            run_dir,
            self.rewrite_dir(unit, hash_value=unit["voice_profile_sha256"]),
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PASS", result["candidate_assembly_status"])
        self.assertEqual("REVIEW_CANDIDATE", result["publish_state"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertEqual("PASS", result["voice_binding_status"])
        self.assertEqual(
            manifest["manifest_sha256"], result["voice_profile_manifest_sha256"]
        )
        self.assertNotEqual(
            profile["profile_sha256"], result["voice_profile_manifest_sha256"]
        )

        sample.write_text(sample.read_text(encoding="utf-8") + "样本发生漂移", encoding="utf-8")
        stale_run = self.root / "short-stale-evidence-run"
        with self.assertRaisesRegex(ValueError, "rebuilt sample evidence differs"):
            preparer.prepare(
                [target],
                stale_run,
                scene="RESEARCH",
                min_author_chars=0,
                voice_profile=profile_path,
                voice_profile_sha256=profile["profile_sha256"],
                voice_manifest=manifest_path,
                voice_sample_spec=spec_path,
                voice_allowed_root=self.root,
            )
        self.assertFalse(stale_run.exists())


if __name__ == "__main__":
    unittest.main()
