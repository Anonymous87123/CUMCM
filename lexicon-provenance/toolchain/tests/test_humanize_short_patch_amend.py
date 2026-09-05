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
SCRIPTS = SKILL / "scripts"
BUILDER_PATH = SCRIPTS / "build_humanize_short_patch.py"
APPLICATOR_PATH = SCRIPTS / "apply_humanize_short_patch.py"
VERIFIER_PATH = SCRIPTS / "verify_humanize_short_patch.py"
AMEND_PATH = SCRIPTS / "amend_humanize_short_patch.py"


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
amend = load_module("amend_humanize_short_patch", AMEND_PATH)


class HumanizeShortPatchAmendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture_temp.name)
        cls.source_bytes = (
            "值得注意的是，先读题。\r\n"
            "若条件冲突，保留原句。\r\n"
            "这个结论具有重要意义。\r\n"
        ).encode("utf-8")
        source = cls.fixture_root / "source.tex"
        source.write_bytes(cls.source_bytes)
        spec = {
            "schema_version": "humanize-short-patch-selection/v2",
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
            "coverage": {
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
            },
        }
        spec_path = cls.fixture_root / "selection.json"
        spec_path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        bundle_path = cls.fixture_root / "patch.bundle.json"
        builder.build_bundle(source, spec_path, bundle_path)
        cls.fixture_review = cls.fixture_root / "base-review"
        applicator.apply_patch(source, bundle_path, cls.fixture_review)
        verified = verifier.verify_directory(cls.fixture_review)
        if verified.get("status") != "PASS":
            raise AssertionError(f"base fixture did not verify: {verified}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture_temp.cleanup()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base-review"
        shutil.copytree(self.fixture_review, self.base)
        self.live_source = self.root / "live-source.tex"
        self.live_source.write_bytes(self.source_bytes)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write_payload(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def create(self, *hunks: str, live: bool = False, name: str = "amend.json"):
        path = self.root / name
        payload = amend.create_authoring(
            self.base,
            list(hunks),
            path,
            live_source=self.live_source if live else None,
        )
        return path, payload

    def change_h002(self, path: Path, payload: dict, replacement: str = "先核对题设条件"):
        change = next(item for item in payload["changes"] if item["hunk_id"] == "H002")
        change["after"] = {
            "decision": "REWRITE",
            "replacement": replacement,
            "reason": "把动作限定为核对题设中的既有条件。",
        }
        self.write_payload(path, payload)

    def test_success_preserves_unchanged_hunks_and_publishes_v3_review(self) -> None:
        authoring_path, authoring = self.create("H002")
        parent_bundle = json.loads((self.base / "patch.bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(set(amend.AUTHORING_FIELDS), set(authoring))
        self.assertEqual(set(amend.BASE_FIELDS), set(authoring["base"]))
        self.assertEqual(set(amend.CHANGE_FIELDS), set(authoring["changes"][0]))
        self.assertEqual(parent_bundle["hunks"][1], authoring["changes"][0]["before"])
        self.assertEqual(
            {
                "decision": parent_bundle["hunks"][1]["decision"],
                "replacement": parent_bundle["hunks"][1]["replacement"],
                "reason": parent_bundle["hunks"][1]["reason"],
            },
            authoring["changes"][0]["after"],
        )
        self.change_h002(authoring_path, authoring)
        output = self.root / "amended-review"
        result = amend.apply_amendment(self.base, authoring_path, output)
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        child = json.loads((output / "patch.bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(builder.BUNDLE_SCHEMA_V3, child["schema_version"])
        self.assertEqual(1, child["amendment"]["amendment_depth"])
        self.assertEqual(authoring["base"]["manifest_sha256"], child["amendment"]["parent_manifest_sha256"])
        self.assertEqual(["H002"], [item["hunk_id"] for item in child["amendment"]["changed_hunks"]])
        for before, after in zip(parent_bundle["hunks"], child["hunks"]):
            if before["hunk_id"] == "H002":
                self.assertEqual("先核对题设条件", after["replacement"])
            else:
                self.assertEqual(before, after)
        verified = verifier.verify_directory(output)
        self.assertEqual("PASS", verified["status"])
        self.assertEqual("PASS", verified["amendment_lineage_status"])
        self.assertEqual(1, verified["amendment_depth"])

    def test_multiple_hunks_are_frozen_in_parent_source_order(self) -> None:
        _path, payload = self.create("H004", "H001", "H003")
        self.assertEqual(["H001", "H003", "H004"], [item["hunk_id"] for item in payload["changes"]])

    def test_noop_and_tampered_before_anchor_fail_without_output(self) -> None:
        path, payload = self.create("H002")
        output = self.root / "no-op-output"
        with self.assertRaisesRegex(amend.AmendError, "SELECTED_HUNK_NOT_CHANGED"):
            amend.apply_amendment(self.base, path, output)
        self.assertFalse(output.exists())
        payload["changes"][0]["before"]["start_byte"] += 1
        self.change_h002(path, payload)
        with self.assertRaisesRegex(amend.AmendError, "before anchor mismatch"):
            amend.apply_amendment(self.base, path, output)
        self.assertFalse(output.exists())

    def test_stale_base_and_tampered_parent_fail_closed(self) -> None:
        path, payload = self.create("H002")
        self.change_h002(path, payload)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["base"]["bundle_sha256"] = "0" * 64
        self.write_payload(path, payload)
        output = self.root / "stale-output"
        with self.assertRaisesRegex(amend.AmendError, "base anchors"):
            amend.apply_amendment(self.base, path, output)
        self.assertFalse(output.exists())

        path2, payload2 = self.create("H002", name="tampered-parent.json")
        self.change_h002(path2, payload2)
        with (self.base / "patch.diff").open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaisesRegex(amend.AmendError, "PARENT_VERIFICATION_FAILED"):
            amend.apply_amendment(self.base, path2, self.root / "tampered-parent-output")

    def test_illegal_topology_or_configuration_fields_are_rejected(self) -> None:
        path, payload = self.create("H002")
        self.change_h002(path, payload)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["scene"] = "GENERAL"
        self.write_payload(path, payload)
        with self.assertRaisesRegex(amend.AmendError, "fields drifted"):
            amend.apply_amendment(self.base, path, self.root / "illegal-config")

        payload.pop("scene")
        payload["changes"][0]["after"]["start_byte"] = 0
        self.write_payload(path, payload)
        with self.assertRaisesRegex(amend.AmendError, "fields drifted"):
            amend.apply_amendment(self.base, path, self.root / "illegal-topology")

    def test_policy_and_live_source_drift_return_review_without_output(self) -> None:
        path, payload = self.create("H002")
        self.change_h002(path, payload)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["policy_hashes"]["validator_sha256"] = "0" * 64
        self.write_payload(path, payload)
        with self.assertRaisesRegex(amend.AmendReview, "POLICY_DRIFT"):
            amend.apply_amendment(self.base, path, self.root / "policy-output")
        self.assertFalse((self.root / "policy-output").exists())

        live_path, live_payload = self.create("H002", live=True, name="live-amend.json")
        self.change_h002(live_path, live_payload)
        self.live_source.write_text("来源已经变化。", encoding="utf-8")
        with self.assertRaisesRegex(amend.AmendReview, "LIVE_SOURCE_NOT_CURRENT"):
            amend.apply_amendment(
                self.base,
                live_path,
                self.root / "live-output",
                live_source=self.live_source,
            )
        with self.assertRaisesRegex(amend.AmendReview, "LIVE_SOURCE_REQUIRED"):
            amend.apply_amendment(self.base, live_path, self.root / "missing-live-output")

    def test_matching_caller_path_is_only_unverified_self_consistency(self) -> None:
        path, payload = self.create("H002", live=True, name="matching-amend.json")
        self.assertTrue(payload["base"]["live_source_required"])
        self.change_h002(path, payload)
        output = self.root / "matching-output"
        result = amend.apply_amendment(
            self.base,
            path,
            output,
            live_source=self.live_source,
        )
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(2, result["exit_code"])
        self.assertFalse(result["freshness_claim_allowed"])
        self.assertEqual(
            "CALLER_SUPPLIED_MATCH_UNVERIFIED",
            result["live_source_status"]["status"],
        )
        self.assertEqual(
            "UNVERIFIED_CALLER_PATH",
            result["live_source_status"]["path_binding"],
        )
        self.assertFalse(result["live_source_status"]["freshness_claim_allowed"])
        self.assertEqual(
            ["LIVE_SOURCE_PATH_BINDING_UNVERIFIED"],
            result["review_reasons"],
        )
        self.assertTrue(output.is_dir())

        # An arbitrary byte-identical copy must not make the verifier claim
        # trusted freshness or return PASS for the explicit live-source check.
        decoy = self.root / "decoy-copy.tex"
        decoy.write_bytes(self.source_bytes)
        checked = verifier.verify_directory(output, live_source=decoy)
        self.assertEqual("REVIEW", checked["status"])
        self.assertEqual(2, checked["exit_code"])
        self.assertEqual(
            "CALLER_SUPPLIED_MATCH_UNVERIFIED",
            checked["live_source_status"]["status"],
        )
        self.assertFalse(checked["live_source_status"]["freshness_claim_allowed"])
        self.assertIn(
            "LIVE_SOURCE_PATH_BINDING_UNVERIFIED", checked["review_reasons"]
        )

    def test_cli_create_with_matching_live_source_returns_review(self) -> None:
        authoring = self.root / "live-cli-amend.json"
        created = subprocess.run(
            [
                sys.executable,
                str(AMEND_PATH),
                "create",
                str(self.base),
                "--hunk",
                "H002",
                "--output",
                str(authoring),
                "--live-source",
                str(self.live_source),
                "--format",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(2, created.returncode, created.stderr.decode("utf-8"))
        summary = json.loads(created.stdout.decode("utf-8"))
        self.assertEqual("REVIEW", summary["delivery_gate_status"])
        self.assertEqual("PENDING_AMENDMENT", summary["authoring_status"])
        self.assertEqual(
            "CALLER_SUPPLIED_MATCH_UNVERIFIED", summary["live_source_status"]
        )
        self.assertEqual("UNVERIFIED_CALLER_PATH", summary["path_binding"])
        self.assertFalse(summary["freshness_claim_allowed"])
        self.assertEqual(
            ["LIVE_SOURCE_PATH_BINDING_UNVERIFIED"], summary["review_reasons"]
        )
        self.assertTrue(authoring.is_file())
        payload = json.loads(authoring.read_text(encoding="utf-8"))
        self.change_h002(authoring, payload)
        output = self.root / "live-cli-output"
        applied = subprocess.run(
            [
                sys.executable,
                str(AMEND_PATH),
                "apply",
                str(self.base),
                "--amendment",
                str(authoring),
                "--output",
                str(output),
                "--live-source",
                str(self.live_source),
                "--format",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(2, applied.returncode, applied.stderr.decode("utf-8"))
        applied_summary = json.loads(applied.stdout.decode("utf-8"))
        self.assertEqual("REVIEW", applied_summary["delivery_gate_status"])
        self.assertEqual(
            "CALLER_SUPPLIED_MATCH_UNVERIFIED",
            applied_summary["live_source_status"]["status"],
        )
        self.assertFalse(applied_summary["freshness_claim_allowed"])
        self.assertIn(
            "LIVE_SOURCE_PATH_BINDING_UNVERIFIED",
            applied_summary["review_reasons"],
        )
        self.assertTrue(output.is_dir())

    def test_policy_change_during_apply_removes_staging_and_publishes_nothing(self) -> None:
        path, payload = self.create("H002")
        self.change_h002(path, payload)
        frozen = dict(payload["policy_hashes"])
        changed = dict(frozen)
        changed["validator_sha256"] = "0" * 64
        output = self.root / "policy-race-output"
        with mock.patch.object(amend, "current_policy_hashes", side_effect=[frozen, changed]):
            with self.assertRaisesRegex(amend.AmendReview, "POLICY_CHANGED_DURING_APPLY"):
                amend.apply_amendment(self.base, path, output)
        self.assertFalse(output.exists())
        self.assertEqual([], list(self.root.glob(".*.amend-staging-*")))

    def test_applicator_failure_is_atomic_and_existing_output_is_preserved(self) -> None:
        path, payload = self.create("H002")
        self.change_h002(path, payload)
        output = self.root / "atomic-output"
        with mock.patch.object(applicator, "apply_patch", side_effect=builder.ShortPatchError("boom")):
            with self.assertRaisesRegex(builder.ShortPatchError, "boom"):
                amend.apply_amendment(self.base, path, output)
        self.assertFalse(output.exists())
        self.assertEqual([], list(self.root.glob(".*.amend-staging-*")))

        output.mkdir()
        marker = output / "user.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(builder.ShortPatchError, "output_exists"):
            amend.apply_amendment(self.base, path, output)
        self.assertEqual("keep", marker.read_text(encoding="utf-8"))

    def test_cli_create_apply_and_failure_statuses(self) -> None:
        authoring = self.root / "cli-amend.json"
        created = subprocess.run(
            [
                sys.executable,
                str(AMEND_PATH),
                "create",
                str(self.base),
                "--hunk",
                "H002",
                "--output",
                str(authoring),
                "--format",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, created.returncode, created.stderr.decode("utf-8"))
        created_payload = json.loads(created.stdout.decode("utf-8"))
        self.assertEqual("PENDING_AMENDMENT", created_payload["status"])
        payload = json.loads(authoring.read_text(encoding="utf-8"))
        self.change_h002(authoring, payload)
        output = self.root / "cli-output"
        applied = subprocess.run(
            [
                sys.executable,
                str(AMEND_PATH),
                "apply",
                str(self.base),
                "--amendment",
                str(authoring),
                "--output",
                str(output),
                "--format",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(2, applied.returncode, applied.stderr.decode("utf-8"))
        applied_payload = json.loads(applied.stdout.decode("utf-8"))
        self.assertEqual("REVIEW", applied_payload["delivery_gate_status"])
        self.assertTrue(output.is_dir())

        invalid = subprocess.run(
            [sys.executable, str(AMEND_PATH), "create", str(self.base), "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(1, invalid.returncode)
        self.assertEqual("FAIL", json.loads(invalid.stdout.decode("utf-8"))["status"])

    def test_chained_amend_uses_current_v3_parent_and_increments_depth(self) -> None:
        first_authoring, first_payload = self.create("H002")
        self.change_h002(first_authoring, first_payload)
        first_review = self.root / "first-review"
        amend.apply_amendment(self.base, first_authoring, first_review)

        second_authoring = self.root / "second-amend.json"
        second_payload = amend.create_authoring(
            first_review, ["H002"], second_authoring
        )
        self.change_h002(second_authoring, second_payload, replacement="先检查题设条件")
        second_review = self.root / "second-review"
        amend.apply_amendment(first_review, second_authoring, second_review)
        child = json.loads((second_review / "patch.bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(builder.BUNDLE_SCHEMA_V3, child["schema_version"])
        self.assertEqual(2, child["amendment"]["amendment_depth"])
        self.assertEqual(builder.BUNDLE_SCHEMA_V3, child["amendment"]["parent_bundle"]["schema_version"])
        self.assertEqual("PASS", verifier.verify_directory(second_review)["status"])

    def test_rehashed_v3_cannot_hide_an_undeclared_hunk_change(self) -> None:
        authoring_path, authoring = self.create("H002")
        self.change_h002(authoring_path, authoring)
        output = self.root / "lineage-tamper-review"
        amend.apply_amendment(self.base, authoring_path, output)
        child = json.loads((output / "patch.bundle.json").read_text(encoding="utf-8"))
        child["hunks"][0]["reason"] = "调用方试图在 changed set 之外改写 H001 的理由。"
        child["bundle_sha256"] = builder._bundle_hash(child)
        with self.assertRaisesRegex(
            builder.ShortPatchError,
            "changed_hunks|coverage record|COVERAGE_REPLAY_MISMATCH",
        ):
            builder.validate_bundle_payload(child, self.source_bytes)

    def test_ninth_amendment_depth_requires_a_new_authoring_run(self) -> None:
        parent = json.loads((self.base / "patch.bundle.json").read_text(encoding="utf-8"))
        replacements = ("先检查题设条件", "先核对题设条件")
        for index in range(builder.MAX_AMENDMENT_DEPTH):
            amendment = {
                "base": {
                    "manifest_sha256": "a" * 64,
                    "candidate_sha256": builder.sha256(
                        builder._apply_bundle_bytes(self.source_bytes, parent)
                    ),
                }
            }
            raw = json.dumps(amendment, ensure_ascii=False).encode("utf-8")
            parent = builder.build_amended_bundle_payload(
                self.source_bytes,
                parent,
                raw,
                [
                    {
                        "hunk_id": "H002",
                        "decision": "REWRITE",
                        "replacement": replacements[index % 2],
                        "reason": "在冻结跨度内交替核对题设条件，用于验证血缘深度上限。",
                    }
                ],
            )
            self.assertEqual(index + 1, parent["amendment"]["amendment_depth"])

        amendment = {
            "base": {
                "manifest_sha256": "b" * 64,
                "candidate_sha256": builder.sha256(
                    builder._apply_bundle_bytes(self.source_bytes, parent)
                ),
            }
        }
        with self.assertRaisesRegex(
            builder.ShortPatchError,
            "AMENDMENT_CHAIN_LIMIT_REQUIRES_NEW_AUTHORING_RUN",
        ):
            builder.build_amended_bundle_payload(
                self.source_bytes,
                parent,
                json.dumps(amendment).encode("utf-8"),
                [
                    {
                        "hunk_id": "H002",
                        "decision": "REWRITE",
                        "replacement": "先再次检查题设条件",
                        "reason": "第九层必须要求重新建立普通 authoring run。",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
