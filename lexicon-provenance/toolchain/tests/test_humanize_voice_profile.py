import copy
import importlib.util
import json
import os
import re
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
BUILDER_SCRIPT = SKILL / "scripts" / "build_humanize_voice_profile.py"
VALIDATOR_SCRIPT = SKILL / "scripts" / "validate_humanize_voice_profile.py"
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
SOURCE_DATE_EPOCH = "1710000000"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def han_count(text: str) -> int:
    return len(HAN_RE.findall(text))


def author_unit(char_count: int, filler: str) -> str:
    """Create one distinct author unit with an exact Han-character count."""
    opening = "本文认为"
    if char_count < len(opening):
        return filler * char_count
    text = opening + filler * (char_count - len(opening))
    assert han_count(text) == char_count
    return text


class HumanizeVoiceProfileTests(unittest.TestCase):

    def test_builder_missing_private_spec_returns_stable_code_without_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Alice" / "PrivateProject"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_SCRIPT),
                    "--sample-spec",
                    str(root / "voice.spec.json"),
                    "--allowed-root",
                    str(root),
                    "--profile-id",
                    "demo",
                    "--manifest-out",
                    str(root / "manifest.json"),
                    "--output",
                    str(root / "profile.json"),
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
        self.assertEqual("INPUT_NOT_FOUND", payload["error_code"])
        self.assertNotIn(str(root), completed.stdout + completed.stderr)
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_script(BUILDER_SCRIPT, "build_humanize_voice_profile_test")
        cls.validator = load_script(
            VALIDATOR_SCRIPT, "validate_humanize_voice_profile_test"
        )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_counter = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_spec(self, samples: list[dict], *, name: str = "samples.spec.json") -> Path:
        path = self.root / name
        payload = {
            "schema_version": "humanize-voice-sample-spec/v1",
            "samples": samples,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return path

    def write_boundary_samples(
        self,
        total_chars: int,
        *,
        sample_count: int = 3,
        complete_unit_count: int | None = None,
        prefix: str = "boundary",
    ) -> list[dict]:
        if complete_unit_count is None:
            complete_unit_count = sample_count
        fillers = "甲乙丙丁戊己庚辛壬癸"
        self.assertLessEqual(sample_count, len(fillers))
        quotient, remainder = divmod(total_chars, sample_count)
        samples: list[dict] = []
        for index in range(sample_count):
            chars = quotient + (1 if index < remainder else 0)
            relative = Path("samples") / f"{prefix}-{index + 1:02d}.md"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            text = author_unit(chars, fillers[index])
            path.write_text(text, encoding="utf-8", newline="\n")
            samples.append(
                {
                    "sample_id": f"{prefix}-{index + 1:02d}",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": index < complete_unit_count,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        self.assertEqual(
            total_chars,
            sum(
                han_count((self.root / sample["locator"]).read_text(encoding="utf-8"))
                for sample in samples
            ),
        )
        return samples

    def run_builder(
        self,
        spec: Path,
        *,
        profile_id: str = "test-author-style",
        suffix: str | None = None,
        expected_returncode: int = 0,
    ) -> tuple[dict, dict, bytes, bytes]:
        self.run_counter += 1
        suffix = suffix or str(self.run_counter)
        profile_path = self.root / f"voice-profile-{suffix}.json"
        manifest_path = self.root / f"voice-manifest-{suffix}.json"
        command = [
            sys.executable,
            str(BUILDER_SCRIPT),
            "--sample-spec",
            str(spec),
            "--allowed-root",
            str(self.root),
            "--profile-id",
            profile_id,
            "--scene",
            "AUTO",
            "--manifest-out",
            str(manifest_path),
            "--output",
            str(profile_path),
            "--format",
            "json",
            "--source-date-epoch",
            SOURCE_DATE_EPOCH,
        ]
        completed = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            expected_returncode,
            completed.returncode,
            msg=(
                f"builder failed\nstdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            ),
        )
        self.assertTrue(profile_path.is_file(), "builder did not write profile")
        self.assertTrue(manifest_path.is_file(), "builder did not write manifest")
        profile_bytes = profile_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
        return (
            json.loads(profile_bytes),
            json.loads(manifest_bytes),
            profile_bytes,
            manifest_bytes,
        )

    def test_scene_defaults_are_safe_distinct_and_self_hashed(self) -> None:
        hashes: set[str] = set()
        for scene in ("COURSE", "MODELING", "RESEARCH", "GENERAL"):
            with self.subTest(scene=scene):
                profile = self.builder.build_scene_default_profile(scene)
                self.assertEqual("DEFAULT", profile["profile_kind"])
                self.assertEqual("PASS", profile["validation_status"])
                self.assertEqual("DEFAULT", profile["confidence"])
                self.assertEqual([], profile["features"])
                self.assertEqual([], profile["negative_controls"])
                self.assertTrue(profile["defaults"]["use_scene_default"])
                self.assertEqual(scene, profile["defaults"]["scene"])
                self.assertTrue(profile["defaults"]["disclosure_required"])
                self.assertFalse(
                    profile["defaults"]["personal_voice_claim_allowed"]
                )
                self.assertEqual(
                    profile["profile_sha256"],
                    self.builder.canonical_profile_sha256(profile),
                )
                hashes.add(profile["profile_sha256"])
        self.assertEqual(4, len(hashes), "scene must be covered by the profile hash")

    def test_confidence_thresholds_use_clean_unique_author_chars(self) -> None:
        cases = (
            (299, "DEFAULT", "DEFAULT"),
            (300, "PERSONAL", "LOW"),
            (999, "PERSONAL", "LOW"),
            (1000, "PERSONAL", "MEDIUM"),
            (4999, "PERSONAL", "MEDIUM"),
            (5000, "PERSONAL", "HIGH"),
        )
        for total_chars, profile_kind, confidence in cases:
            with self.subTest(total_chars=total_chars):
                samples = self.write_boundary_samples(
                    total_chars, prefix=f"threshold-{total_chars}"
                )
                spec = self.write_spec(
                    samples, name=f"threshold-{total_chars}.spec.json"
                )
                profile, manifest, _profile_bytes, _manifest_bytes = self.run_builder(
                    spec, suffix=f"threshold-{total_chars}"
                )
                self.assertEqual(profile_kind, profile["profile_kind"])
                self.assertEqual(confidence, profile["confidence"])
                self.assertFalse(profile["claims"]["identity_verified"])
                self.assertEqual("PASS", profile["validation_status"])
                self.assertEqual(
                    total_chars, profile["sample_binding"]["readable_author_chars"]
                )
                self.assertEqual(
                    total_chars, manifest["aggregate"]["readable_author_chars"]
                )
                self.assertEqual(
                    3, profile["sample_binding"]["unique_complete_units"]
                )
                if profile_kind == "DEFAULT":
                    self.assertEqual([], profile["features"])
                    self.assertFalse(
                        profile["defaults"]["personal_voice_claim_allowed"]
                    )
                else:
                    self.assertTrue(profile["features"])
                    self.assertTrue(
                        profile["defaults"]["personal_voice_claim_allowed"]
                    )

    def test_5000_chars_without_three_complete_units_is_capped_at_medium(self) -> None:
        samples = self.write_boundary_samples(
            5000,
            sample_count=4,
            complete_unit_count=2,
            prefix="high-cap",
        )
        spec = self.write_spec(samples, name="high-cap.spec.json")
        profile, manifest, _profile_bytes, _manifest_bytes = self.run_builder(
            spec, suffix="high-cap"
        )

        self.assertEqual("PERSONAL", profile["profile_kind"])
        self.assertEqual("MEDIUM", profile["confidence"])
        self.assertEqual(5000, profile["sample_binding"]["readable_author_chars"])
        self.assertEqual(2, profile["sample_binding"]["unique_complete_units"])
        self.assertEqual(2, manifest["aggregate"]["unique_complete_units"])

    def test_three_near_duplicate_complete_files_do_not_unlock_high(self) -> None:
        base = "本文认为" + "甲" * 4996
        variants = (base, base[:-1] + "乙", base[:-1] + "丙")
        samples = []
        for index, text in enumerate(variants, 1):
            relative = Path("samples") / f"near-complete-{index}.md"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            samples.append(
                {
                    "sample_id": f"near-complete-{index}",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        spec = self.write_spec(samples, name="near-complete.spec.json")
        profile, manifest, _profile_bytes, _manifest_bytes = self.run_builder(
            spec, suffix="near-complete", expected_returncode=2
        )

        self.assertEqual(5000, manifest["aggregate"]["readable_author_chars"])
        self.assertEqual(1, manifest["aggregate"]["unique_complete_units"])
        self.assertEqual("MEDIUM", profile["confidence"])
        self.assertEqual("REVIEW", profile["validation_status"])
        self.assertEqual(
            1,
            sum(
                1
                for sample in manifest["samples"]
                if sample["complete_unit_is_representative"]
            ),
        )

    def test_near_duplicate_chain_is_order_invariant(self) -> None:
        prefix = "本文说明"
        base = "".join(chr(0x4E00 + index) for index in range(5000))
        versions = [prefix + base]
        current = list(base)
        for replacement_index, start in enumerate((100, 1100, 2100, 3100)):
            current[start : start + 150] = [
                chr(0x4E00 + 6000 + replacement_index * 200 + offset)
                for offset in range(150)
            ]
            versions.append(prefix + "".join(current))

        samples = []
        for index, text in enumerate(versions):
            relative = Path("samples") / f"chain-{index}.md"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            samples.append(
                {
                    "sample_id": f"chain-{index}",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )

        results = []
        for suffix, order in (("natural", (0, 1, 2, 3, 4)), ("reordered", (0, 1, 3, 2, 4))):
            spec = self.write_spec(
                [samples[index] for index in order], name=f"chain-{suffix}.spec.json"
            )
            manifest, profile = self.builder.build_voice_profile(
                sample_spec=spec,
                allowed_root=self.root,
                profile_id=f"chain-{suffix}",
                scene="RESEARCH",
                source_date_epoch=int(SOURCE_DATE_EPOCH),
            )
            results.append((manifest, profile))

        for manifest, profile in results:
            self.assertEqual(5004, manifest["aggregate"]["readable_author_chars"])
            self.assertEqual(1, manifest["aggregate"]["unique_analysis_units"])
            self.assertEqual(1, manifest["aggregate"]["unique_complete_units"])
            self.assertEqual("MEDIUM", profile["confidence"])
            self.assertEqual("REVIEW", profile["validation_status"])

    def test_cross_scene_personal_evidence_cannot_be_relabelled_pass(self) -> None:
        samples = []
        for index, filler in enumerate("甲乙丙", 1):
            relative = Path("samples") / f"course-only-{index}.md"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("本文说明" + filler * 396, encoding="utf-8")
            samples.append(
                {
                    "sample_id": f"course-only-{index}",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "COURSE",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            )
        spec = self.write_spec(samples, name="course-only.spec.json")
        _manifest, profile = self.builder.build_voice_profile(
            sample_spec=spec,
            allowed_root=self.root,
            profile_id="course-evidence-research-label",
            scene="RESEARCH",
            source_date_epoch=int(SOURCE_DATE_EPOCH),
        )

        self.assertEqual("PERSONAL", profile["profile_kind"])
        self.assertEqual(["COURSE"], profile["sample_binding"]["sample_scenes"])
        self.assertEqual("RESEARCH", profile["binding_scene"])
        self.assertEqual("REVIEW", profile["validation_status"])
        self.assertFalse(profile["defaults"]["personal_voice_claim_allowed"])

    def test_repeated_paragraphs_cannot_inflate_chars_or_confidence(self) -> None:
        paragraph = author_unit(200, "重")
        relative = Path("samples") / "repeated.md"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join([paragraph] * 30), encoding="utf-8", newline="\n")
        self.assertEqual(6000, han_count(path.read_text(encoding="utf-8")))
        spec = self.write_spec(
            [
                {
                    "sample_id": "repeated-sample",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": [],
                }
            ],
            name="repeated.spec.json",
        )
        profile, manifest, _profile_bytes, _manifest_bytes = self.run_builder(
            spec, suffix="repeated"
        )

        sample = manifest["samples"][0]
        self.assertEqual(6000, sample["readable_author_chars_before_dedup"])
        self.assertEqual(200, sample["readable_author_chars_after_dedup"])
        self.assertEqual(200, manifest["aggregate"]["readable_author_chars"])
        self.assertEqual(1, manifest["aggregate"]["unique_analysis_units"])
        self.assertEqual("DEFAULT", profile["profile_kind"])
        self.assertEqual("DEFAULT", profile["confidence"])

    def test_code_math_and_quotation_ranges_are_excluded_from_author_chars(self) -> None:
        author = author_unit(240, "述")
        protected_segments = (
            ("code", "\n```text\n" + "代码区伪造偏好" * 20 + "\n```\n"),
            ("math", "\n\\[\\text{公式区伪造偏好反复出现}\\]\n"),
            ("quoted", "\n> “引语区伪造偏好反复出现，并非作者叙述。”\n"),
        )
        raw = author
        role_ranges: list[dict] = []
        for role, segment in protected_segments:
            byte_start = len(raw.encode("utf-8"))
            raw += segment
            role_ranges.append(
                {
                    "byte_start": byte_start,
                    "byte_end": len(raw.encode("utf-8")),
                    "role": role,
                }
            )
        self.assertGreater(han_count(raw), 300, "fixture must cross the LOW threshold raw")
        relative = Path("samples") / "protected.md"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8", newline="")
        spec = self.write_spec(
            [
                {
                    "sample_id": "protected-sample",
                    "locator": relative.as_posix(),
                    "origin": "USER_CONFIRMED_AUTHOR",
                    "scene": "RESEARCH",
                    "complete_unit": True,
                    "default_role": "author",
                    "role_ranges": role_ranges,
                }
            ],
            name="protected.spec.json",
        )
        profile, manifest, _profile_bytes, _manifest_bytes = self.run_builder(
            spec, suffix="protected"
        )

        self.assertEqual(240, manifest["aggregate"]["readable_author_chars"])
        self.assertEqual(240, profile["sample_binding"]["readable_author_chars"])
        self.assertEqual("DEFAULT", profile["profile_kind"])
        roles = {item["role"] for item in manifest["role_ranges"]}
        self.assertTrue({"code", "math", "quoted"}.issubset(roles))
        serialized = json.dumps(
            {"profile": profile, "manifest": manifest}, ensure_ascii=False
        )
        for protected_phrase in ("代码区伪造偏好", "公式区伪造偏好", "引语区伪造偏好"):
            self.assertNotIn(protected_phrase, serialized)

    def test_profile_self_hash_tampering_is_rejected(self) -> None:
        profile = self.builder.build_scene_default_profile("RESEARCH")
        original_hash = profile["profile_sha256"]
        tampered = copy.deepcopy(profile)
        tampered["defaults"]["scene"] = "GENERAL"
        self.assertEqual(original_hash, tampered["profile_sha256"])
        self.assertNotEqual(
            original_hash, self.builder.canonical_profile_sha256(tampered)
        )
        path = self.root / "tampered-profile.json"
        path.write_text(
            json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, r"(?i)(profile_sha256|hash)"):
            self.validator.load_and_validate_profile(path)

    def test_same_snapshot_and_epoch_rebuild_byte_identically(self) -> None:
        samples = self.write_boundary_samples(1200, prefix="stable")
        spec = self.write_spec(samples, name="stable.spec.json")
        first_profile, first_manifest, first_profile_bytes, first_manifest_bytes = (
            self.run_builder(spec, suffix="stable-a")
        )
        second_profile, second_manifest, second_profile_bytes, second_manifest_bytes = (
            self.run_builder(spec, suffix="stable-b")
        )

        self.assertEqual(first_profile, second_profile)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_profile_bytes, second_profile_bytes)
        self.assertEqual(first_manifest_bytes, second_manifest_bytes)
        self.assertEqual(
            first_profile["profile_sha256"],
            self.builder.canonical_profile_sha256(first_profile),
        )

    def test_validator_rebuilds_pinned_evidence_and_rejects_source_drift(self) -> None:
        samples = self.write_boundary_samples(1200, prefix="validator-rebuild")
        spec = self.write_spec(samples, name="validator-rebuild.spec.json")
        self.run_builder(spec, suffix="validator-rebuild")
        profile = self.root / "voice-profile-validator-rebuild.json"
        manifest = self.root / "voice-manifest-validator-rebuild.json"
        command = [
            sys.executable,
            str(VALIDATOR_SCRIPT),
            str(profile),
            "--manifest",
            str(manifest),
            "--sample-spec",
            str(spec),
            "--allowed-root",
            str(self.root),
            "--rebuild-evidence",
            "--format",
            "json",
        ]
        clean = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, clean.returncode, clean.stderr)
        self.assertTrue(json.loads(clean.stdout)["evidence_rebuilt"])

        sample_path = self.root / samples[0]["locator"]
        sample_path.write_text(
            sample_path.read_text(encoding="utf-8") + "样本漂移",
            encoding="utf-8",
        )
        drift = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(1, drift.returncode)
        self.assertIn("rebuilt sample evidence differs", drift.stdout)

    def test_validator_profile_only_cannot_admit_personal_profile(self) -> None:
        samples = self.write_boundary_samples(1200, prefix="profile-only")
        spec = self.write_spec(samples, name="profile-only.spec.json")
        self.run_builder(spec, suffix="profile-only")
        profile_path = self.root / "voice-profile-profile-only.json"

        completed = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), str(profile_path), "--format", "json"],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("PASS", result["profile_validation_status"])
        self.assertEqual("REVIEW", result["production_admission_status"])
        self.assertEqual("EVIDENCE_REBUILD_REQUIRED", result["production_admission_reason"])
        self.assertFalse(result["evidence_rebuilt"])

        default = self.builder.build_scene_default_profile("RESEARCH")
        default_path = self.root / "deterministic-default.json"
        default_path.write_text(json.dumps(default, ensure_ascii=False), encoding="utf-8")
        default_completed = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), str(default_path), "--format", "json"],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, default_completed.returncode)
        self.assertEqual(
            "DETERMINISTIC_DEFAULT",
            json.loads(default_completed.stdout)["production_admission_reason"],
        )

    def test_frozen_read_rejects_file_identity_swap_after_path_validation(self) -> None:
        path = self.root / "identity.md"
        path.write_text("原始样本", encoding="utf-8")
        expected = self.builder._stat_identity(path.lstat())
        replacement = self.root / "replacement.md"
        replacement.write_text("替换样本", encoding="utf-8")
        os.replace(replacement, path)

        with self.assertRaisesRegex(ValueError, "changed between validation and open"):
            self.builder._read_frozen(path, 1024, expected)


if __name__ == "__main__":
    unittest.main()
