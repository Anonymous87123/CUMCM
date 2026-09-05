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
SCRIPT = SKILL / "scripts" / "build_humanize_generator_projection.py"
SPEC = importlib.util.spec_from_file_location("build_humanize_generator_projection", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class HumanizeGeneratorProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill = self.root / "humanize-academic-chinese"
        shutil.copytree(
            SKILL,
            self.skill,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        self.counter = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, *, real_quick_validate: bool = False) -> tuple[dict, Path, Path]:
        self.counter += 1
        output = self.root / f"projection-{self.counter}"
        manifest = self.root / f"manifest-{self.counter}.json"
        if real_quick_validate:
            result = builder.build_projection(self.skill, output, manifest)
        else:
            with mock.patch.object(builder, "_quick_validate", return_value="PASS"):
                result = builder.build_projection(self.skill, output, manifest)
        return result, output, manifest

    def policy_payload(self) -> dict:
        path = self.skill / "references" / "generator-projection-policy.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def write_policy(self, payload: dict) -> None:
        path = self.skill / "references" / "generator-projection-policy.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def manifest_core(result: dict) -> dict:
        return {
            key: value
            for key, value in result.items()
            if key not in {"manifest_sha256", "projection_root", "manifest_path"}
        }

    def test_baseline_projection_has_exact_capability_surface(self) -> None:
        result, output, manifest = self.build(real_quick_validate=True)
        files = sorted(
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        )
        expected = sorted([*builder.EXPECTED_INCLUDE, *builder.EXPECTED_TRANSFORM])
        self.assertEqual(expected, files)
        self.assertEqual(40, len(files))
        self.assertIn("references/structural-rewrite-contract.md", files)
        self.assertIn("scripts/audit_humanize_repetition_guards.py", files)
        self.assertIn("scripts/run_humanize_inline.py", files)
        self.assertFalse((output / manifest.name).exists())
        self.assertEqual("PASS", result["audits"]["skill_quick_validate"])
        self.assertFalse(result["audits"]["read_only_marking_is_isolation_proof"])

    def test_v54_inline_lifecycle_and_attestation_reach_projection(self) -> None:
        _result, output, _manifest = self.build()
        runner = (output / "scripts" / "run_humanize_inline.py").read_text(
            encoding="utf-8"
        )
        projected_skill = (output / "SKILL.md").read_text(encoding="utf-8")
        projected_contract = (
            output / "references" / "operational-contract.md"
        ).read_text(encoding="utf-8")

        self.assertIn("def run_inline(", runner)
        self.assertIn("def verify_run(", runner)
        self.assertIn("def attest_visible_body(", runner)
        self.assertIn("humanize-inline-run/v2", runner)
        self.assertIn("humanize-visible-delivery-attestation/v1", runner)
        self.assertIn("run_humanize_inline.py\" run", projected_skill)
        self.assertIn("run_humanize_inline.py\" emit", projected_skill)
        self.assertIn("run_humanize_inline.py attest", projected_skill)
        self.assertIn("BODY_ONLY", projected_contract)
        self.assertIn("CALLER_SUPPLIED_RESPONSE_BYTES_ONLY", runner)
        self.assertIn("chat_transport_byte_identity_status", runner)
        self.assertIn("attest <run-dir>", projected_contract)
        self.assertIn("任何改字", projected_contract)

    def test_v34_source_conflict_and_draft_unitization_contract_reach_projection(self) -> None:
        _result, output, _manifest = self.build()
        projected_skill = (output / "SKILL.md").read_text(encoding="utf-8")
        projected_workflow = (output / "references" / "workflow.md").read_text(
            encoding="utf-8"
        )
        projected_checker = (
            output / "scripts" / "check_humanize_invariants.py"
        ).read_text(encoding="utf-8")

        self.assertIn("源文内部冲突不属于纯文风层的裁决权限", projected_skill)
        self.assertIn("classification_counts=OMITTED_UNUNITIZED", projected_skill)
        self.assertIn("unit_id + source_span + category", projected_workflow)
        self.assertIn(
            "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
            projected_checker,
        )

    def test_v35_short_patch_tools_and_contract_reach_projection(self) -> None:
        _result, output, _manifest = self.build()
        for relative in (
            "references/short-patch-workflow.md",
            "scripts/build_humanize_short_patch.py",
            "scripts/apply_humanize_short_patch.py",
            "scripts/verify_humanize_short_patch.py",
            "scripts/scaffold_humanize_short_patch.py",
        ):
            self.assertTrue((output / relative).is_file(), relative)
        projected_skill = (output / "SKILL.md").read_text(encoding="utf-8")
        projected_contract = (
            output / "references" / "short-patch-workflow.md"
        ).read_text(encoding="utf-8")
        self.assertIn("short-patch-workflow.md", projected_skill)
        self.assertIn("humanize-short-patch/v1", projected_contract)
        self.assertIn("DELIVERY REVIEW exit=2", projected_contract)

    def test_v40_focus_authoring_reaches_projection_without_claim_authority(self) -> None:
        _result, output, _manifest = self.build()
        scaffold = (
            output / "scripts" / "scaffold_humanize_short_patch.py"
        ).read_text(encoding="utf-8")
        workflow = (output / "references" / "short-patch-workflow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("humanize-short-patch-selection-authoring/v3", scaffold)
        self.assertIn("humanize-short-patch-focus/v1", scaffold)
        self.assertIn("ADVISORY_NON_HIGH_SIGNAL", scaffold)
        self.assertIn("focus_spans", scaffold)
        self.assertIn("CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY", scaffold)
        self.assertIn("--focus-spec", workflow)
        self.assertIn("finding_ids=[]", workflow)
        self.assertIn("SUPPRESSED", workflow)
        self.assertNotIn("focus_authority=true", workflow)
        self.assertNotIn("user_authorized=true", workflow)
        self.assertNotIn("authoring_integrity_scope=EXTERNALLY_ANCHORED", workflow)

    def test_v43_auto_scene_prefreeze_reaches_projection_fail_closed(self) -> None:
        result, output, _manifest = self.build()
        scaffold = (
            output / "scripts" / "scaffold_humanize_short_patch.py"
        ).read_text(encoding="utf-8")
        router = (output / "scripts" / "route_humanize_scene.py").read_text(
            encoding="utf-8"
        )
        workflow = (output / "references" / "short-patch-workflow.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(builder.BUILDER_VERSION, result["projection_policy"]["version"])
        self.assertIn("humanize-short-patch-selection-authoring/v4", scaffold)
        self.assertIn("humanize-short-patch-scene-route/v1", scaffold)
        self.assertIn("requested_scene", scaffold)
        self.assertIn("resolved_scene", scaffold)
        self.assertIn("SCENE_ROUTE_DRIFT", scaffold)
        self.assertIn("SCENE_ROUTE_AMBIGUOUS", scaffold)
        self.assertIn("ROUTE_REVIEW", workflow)
        self.assertIn("competing_positive_scene", router)
        self.assertIn("second_score == 0", router)
        self.assertNotIn("matched_text", scaffold)

    def test_v44_long_authoring_contract_is_reachable_across_projected_modules(self) -> None:
        result, output, _manifest = self.build()
        projected_scaffold = (
            output / "scripts" / "scaffold_humanize_rewrites.py"
        ).read_text(encoding="utf-8")
        projected_finalizer = (
            output / "scripts" / "finalize_humanize_long_document.py"
        ).read_text(encoding="utf-8")
        projected_workflow = (
            output / "references" / "long-document-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(builder.BUILDER_VERSION, result["projection_policy"]["version"])
        self.assertIn("humanize-rewrite-scaffold/v5", projected_scaffold)
        self.assertIn(".humanize-scaffold-committed", projected_scaffold)
        self.assertIn("humanize-unit-rewrite-bundle/v4", projected_finalizer)
        self.assertIn("humanize-long-authoring-binding/v1", projected_finalizer)
        self.assertIn(
            "DELIVERY <status> exit=<code> publish=<state>",
            projected_workflow,
        )

        scripts = output / "scripts"
        probe = (
            "import sys;"
            f"sys.path.insert(0, {str(scripts)!r});"
            "import scaffold_humanize_rewrites as s;"
            "import finalize_humanize_long_document as f;"
            "print('|'.join((s.SCAFFOLD_SCHEMA, "
            "f.UNIT_REWRITE_BUNDLE_SCHEMA, f.LONG_AUTHORING_BINDING_SCHEMA)))"
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe],
            cwd=output,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            "humanize-rewrite-scaffold/v5|"
            "humanize-unit-rewrite-bundle/v4|"
            "humanize-long-authoring-binding/v1",
            completed.stdout.strip(),
        )

    def test_v46_formula_caption_relation_guard_reaches_projection(self) -> None:
        result, output, _manifest = self.build()
        checker = (
            output / "scripts" / "check_humanize_invariants.py"
        ).read_text(encoding="utf-8")
        course = (output / "references" / "course-notes.md").read_text(
            encoding="utf-8"
        )
        contract = (
            output / "references" / "system-prompt-contract.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(builder.BUILDER_VERSION, result["projection_policy"]["version"])
        self.assertIn('"logical_relation": (', checker)
        self.assertIn("LOGICAL_RELATION_ROUTE_SHELL_RE", checker)
        self.assertIn("scanner candidate 不得直接映射为 `DELETE_STYLE_SHELL`", course)
        self.assertIn("只让公式相邻不算保留关系", contract)

    def test_v47_v138_tex_protection_parser_reaches_projection(self) -> None:
        result, output, _manifest = self.build()
        scanner = (output / "scripts" / "scan_humanize_chinese.py").read_text(
            encoding="utf-8"
        )
        preparer = (
            output / "scripts" / "prepare_humanize_long_document.py"
        ).read_text(encoding="utf-8")
        checker = (
            output / "scripts" / "check_humanize_invariants.py"
        ).read_text(encoding="utf-8")
        workflow = (
            output / "references" / "long-document-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(builder.BUILDER_VERSION, result["projection_policy"]["version"])
        for token in (
            "MakeShortVerb",
            "DeleteShortVerb",
            "RecustomVerbatimCommand",
            "BVerbatim*",
            "LVerbatim*",
            "alltt",
            "unclosed_declared_inline_verbatim",
            "unclosed_math_environment",
        ):
            self.assertIn(token, scanner)
        self.assertIn("lexical._tex_protection_problems", preparer)
        self.assertIn("TEX_PROTECTION_PARSE_REVIEW", checker)
        self.assertIn("`$$...$$`", workflow)
        self.assertIn("`\\[...\\]`", workflow)
        self.assertIn("数学环境", workflow)
        self.assertIn("`UNRESOLVED`", workflow)

    def test_projected_tex_heading_wrappers_preserve_visible_role_semantics(self) -> None:
        _result, output, _manifest = self.build()
        scripts = output / "scripts"
        probe = r'''
import json
import sys

sys.path.insert(0, sys.argv[1])
import audit_humanize_repetition_guards as audit


def tex_list(variant):
    return "\n".join([
        r"\begin{itemize}",
        rf"\item 共同校验步骤：{variant}项",
        rf"\item 共同校验步骤：{variant}项补充",
        rf"\item 共同校验步骤：{variant}项复核",
        r"\end{itemize}",
    ])


detector = {
    "type": "structured_repeated_list/v1",
    "block_role": {"heading_leaf_regex": r"^摘要$"},
    "thresholds": {"minimum_blocks": 3, "minimum_items_per_block": 3},
    "shared_anchor": {
        "mode": "MAXIMAL_HAN_NGRAM",
        "minimum_han_chars": 4,
        "maximum_han_chars": 8,
        "minimum_block_coverage": 3,
    },
}

results = []
for heading in (r"\section{摘要}", r"\section{\textbf{摘要}}"):
    text = "\n".join([heading, *(tex_list(item) for item in ("甲", "乙", "丙"))])
    result = audit.evaluate_detector_snapshot(
        {
            "unit_id": "U-01",
            "document_id": "DOC-01",
            "resolved_scene": "RESEARCH",
            "format": "tex",
            "heading_path": "",
            "text": text,
        },
        detector,
    )
    results.append({
        "triggered": result["triggered"],
        "qualified_block_count": result["qualified_block_count"],
    })

hidden_text = "\n".join(
    "\n".join(
        [
            r"\begin{comment}",
            r"\section{摘要}",
            tex_list(variant),
            r"\end{comment}",
        ]
    )
    for variant in ("甲", "乙", "丙")
)
hidden_result = audit.evaluate_detector_snapshot(
    {
        "unit_id": "U-02",
        "document_id": "DOC-01",
        "resolved_scene": "RESEARCH",
        "format": "tex",
        "heading_path": "",
        "text": hidden_text,
    },
    detector,
)

print(json.dumps({
    "leaves": [
        item["heading_leaf"]
        for item in audit.authenticated_tex_headings(
            "\n".join([
                r"\section{摘要}",
                r"\section{\textbf{摘要}}",
                r"\section{\emph{\textit{摘要}}}",
                r"\section{前言 \textbf{模型建立}}",
            ])
        )
    ],
    "opaque": audit.authenticated_tex_headings(
        r"\section{执行清单 \custom{HIDDEN-PAYLOAD}}"
    )[0]["heading_leaf"],
    "results": results,
    "nonrendering": {
        "headings": audit.authenticated_tex_headings(hidden_text),
        "triggered": hidden_result["triggered"],
        "qualified_block_count": hidden_result["qualified_block_count"],
    },
}, ensure_ascii=True, sort_keys=True))
'''
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(scripts)],
            cwd=output,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertNotIn("HIDDEN-PAYLOAD", completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            ["摘要", "摘要", "摘要", "前言 模型建立"],
            payload["leaves"],
        )
        self.assertEqual("执行清单", payload["opaque"])
        self.assertEqual(
            [
                {"triggered": True, "qualified_block_count": 3},
                {"triggered": True, "qualified_block_count": 3},
            ],
            payload["results"],
        )
        self.assertEqual(
            {
                "headings": [],
                "triggered": False,
                "qualified_block_count": 0,
            },
            payload["nonrendering"],
        )

    def test_projected_cross_unit_v3_requires_resolved_scene(self) -> None:
        _result, output, _manifest = self.build()
        scripts = output / "scripts"
        probe = r'''
import hashlib
import json
import sys

sys.path.insert(0, sys.argv[1])
import finalize_humanize_long_document as finalizer


def record(unit_id, resolved_scene="RESEARCH"):
    return {
        "unit_id": unit_id,
        "document_id": "DOC-01",
        "resolved_scene": resolved_scene,
        "expected": True,
        "state": "NO_CHANGE",
        "style_validation": "PASS",
        "before_masked": "普通基线。",
        "after_masked": "普通基线。",
    }


valid_records = [record("U-01", "RESEARCH"), record("U-02", "MODELING")]
valid = finalizer._audit_cross_unit_repetition(valid_records)

cases = {}
for name, mutate in (
    ("missing", lambda item: item.pop("resolved_scene")),
    ("empty", lambda item: item.__setitem__("resolved_scene", "")),
    ("invalid", lambda item: item.__setitem__("resolved_scene", "UNKNOWN")),
    (
        "legacy_only",
        lambda item: (
            item.__setitem__("scene", item.pop("resolved_scene"))
        ),
    ),
    ("matching", lambda item: item.__setitem__("scene", "research")),
    ("conflict", lambda item: item.__setitem__("scene", "MODELING")),
):
    item = record("U-10")
    mutate(item)
    result = finalizer._audit_cross_unit_repetition([item])
    cases[name] = {
        "status": result["status"],
        "review_reasons": result["review_reasons"],
        "evaluation_partitions": result["evaluation_partitions"],
    }

unit_inventory = [
    {
        "unit_id": item["unit_id"],
        "document_id": item["document_id"],
        "resolved_scene": item["resolved_scene"],
        "expected": item["expected"],
        "state": item["state"],
    }
    for item in valid_records
]
expected_inventory_hash = hashlib.sha256(
    json.dumps(
        unit_inventory,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

print(json.dumps({
    "schema_version": valid["schema_version"],
    "policy_version": valid["policy"]["version"],
    "partition_key": valid["policy"]["partition_key"],
    "evaluation_partitions": valid["evaluation_partitions"],
    "logical_document_hashes": valid["logical_document_hashes"],
    "unit_inventory_sha256": valid["unit_inventory_sha256"],
    "expected_inventory_sha256": expected_inventory_hash,
    "cases": cases,
}, ensure_ascii=False, sort_keys=True))
'''
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(scripts)],
            cwd=output,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)

        self.assertEqual("humanize-cross-unit-repetition/v3", payload["schema_version"])
        self.assertEqual("cross-unit-repetition/v3", payload["policy_version"])
        self.assertEqual(
            ["logical_document_id", "resolved_scene"],
            payload["partition_key"],
        )
        self.assertEqual(1, len(payload["logical_document_hashes"]))
        self.assertEqual(
            ["MODELING", "RESEARCH"],
            sorted(
                partition["resolved_scene"]
                for partition in payload["evaluation_partitions"]
            ),
        )
        self.assertTrue(
            all("scene" not in partition for partition in payload["evaluation_partitions"])
        )
        self.assertEqual(
            payload["expected_inventory_sha256"],
            payload["unit_inventory_sha256"],
        )

        expected_errors = {
            "missing": "PARTITION_RESOLVED_SCENE_MISSING",
            "empty": "PARTITION_RESOLVED_SCENE_MISSING",
            "invalid": "PARTITION_RESOLVED_SCENE_INVALID",
            "legacy_only": "PARTITION_RESOLVED_SCENE_MISSING",
            "conflict": "PARTITION_SCENE_CONFLICT",
        }
        for name, error_code in expected_errors.items():
            with self.subTest(name=name):
                case = payload["cases"][name]
                self.assertEqual("REVIEW", case["status"])
                self.assertEqual([], case["evaluation_partitions"])
                self.assertTrue(
                    any(error_code in reason for reason in case["review_reasons"]),
                    case["review_reasons"],
                )

        matching = payload["cases"]["matching"]
        self.assertEqual("PASS", matching["status"])
        self.assertEqual([], matching["review_reasons"])
        self.assertEqual(
            "RESEARCH",
            matching["evaluation_partitions"][0]["resolved_scene"],
        )

    def test_v39_authoring_span_suggestions_reach_projection_without_claim_authority(self) -> None:
        _result, output, _manifest = self.build()
        scaffold = (
            output / "scripts" / "scaffold_humanize_short_patch.py"
        ).read_text(encoding="utf-8")
        workflow = (output / "references" / "short-patch-workflow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("humanize-short-patch-selection-authoring/v3", scaffold)
        self.assertIn("SENTENCE_AND_PARAGRAPH", scaffold)
        self.assertIn("CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY", scaffold)
        self.assertIn("decision_authority", scaffold)
        self.assertIn("SUPPRESSED", workflow)
        self.assertNotIn("authoring_integrity_scope=EXTERNALLY_ANCHORED", workflow)

    def test_rebuild_is_byte_deterministic(self) -> None:
        first, first_output, first_manifest = self.build()
        second, second_output, second_manifest = self.build()

        def file_bytes(root: Path) -> dict[str, bytes]:
            return {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

        self.assertEqual(first["projection_tree_sha256"], second["projection_tree_sha256"])
        self.assertEqual(first_manifest.read_bytes(), second_manifest.read_bytes())
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(file_bytes(first_output), file_bytes(second_output))
        self.assertEqual(
            first["projection_tree_sha256"],
            builder._directory_tree_hash(first_output),
        )
        self.assertEqual(
            second["projection_tree_sha256"],
            builder._directory_tree_hash(second_output),
        )
        first_verified = builder.verify_projection(
            first_output,
            self.manifest_core(first),
            source_root=self.skill,
        )
        second_verified = builder.verify_projection(
            second_output,
            self.manifest_core(second),
            source_root=self.skill,
        )
        self.assertEqual("PASS", first_verified["source_currentness"])
        self.assertEqual("PASS", second_verified["source_currentness"])

    def test_manifest_binds_hidden_evaluation_surface_without_entering_projection(self) -> None:
        result, output, _manifest = self.build()
        excluded = {item["path"] for item in result["excluded"]}
        self.assertIn("references/generation-qualification-oracles.json", excluded)
        self.assertIn("references/generation-qualification-trust.json", excluded)
        self.assertIn("scripts/audit_humanize_generation_qualification.py", excluded)
        self.assertIn("scripts/replay_humanize_validation_record.py", excluded)
        self.assertIn("scripts/replay_humanize_long_fixture.py", excluded)
        self.assertFalse(
            (output / "scripts" / "replay_humanize_validation_record.py").exists()
        )
        self.assertFalse((output / "scripts" / "replay_humanize_long_fixture.py").exists())
        self.assertRegex(result["source"]["evaluation_surface_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(any("qualification" in path.name for path in output.rglob("*")))

    def test_second_pass_control_plane_is_hidden_from_fresh_generator(self) -> None:
        result, output, _manifest = self.build()
        excluded = {item["path"] for item in result["excluded"]}
        self.assertIn("scripts/prepare_humanize_second_pass.py", excluded)
        self.assertIn("scripts/verify_humanize_second_pass.py", excluded)
        self.assertFalse((output / "scripts" / "prepare_humanize_second_pass.py").exists())
        self.assertFalse((output / "scripts" / "verify_humanize_second_pass.py").exists())
        projected_finalizer = (
            output / "scripts" / "finalize_humanize_long_document.py"
        ).read_text(encoding="utf-8")
        for leaked_control in (
            "all_units_no_change",
            "second_output_equals_first",
            "verify_humanize_second_pass.py",
            "expected_outcome_exposed",
        ):
            self.assertNotIn(leaked_control, projected_finalizer)

    def test_long_replay_and_transaction_qualification_controls_do_not_leak(self) -> None:
        _result, output, _manifest = self.build()
        projected_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in output.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".py", ".yaml"}
        )
        self.assertNotIn("replay_humanize_long_fixture.py", projected_text)
        for control_id in (
            "LONG-20",
            "LONG-21",
            "LONG-22",
            "LONG-23",
            "LONG-24",
            "LONG-25",
            "LONG-26",
            "LONG-27",
            "DEC-09",
        ):
            self.assertNotIn(control_id, projected_text)
        for hidden_outcome in (
            "structural_review_request_binding_status",
            "transaction_non_downgrade_status",
        ):
            self.assertNotIn(hidden_outcome, projected_text)

    def test_skill_transform_removes_only_fixed_control_spans(self) -> None:
        raw = (self.skill / "SKILL.md").read_bytes()
        projected, removed = builder._transform_skill(raw)
        self.assertEqual(5, len(removed))
        labels = {item["label"] for item in removed}
        self.assertEqual(
            {
                "route-row:来源动作候选审计",
                "route-row:验证 Skill",
                "route-row:生成资格审计",
                "sections:生成资格与来源候选审计",
                "control:SECOND_PASS",
            },
            labels,
        )
        text = projected.decode("utf-8")
        self.assertNotIn("## 生成资格采集边界", text)
        self.assertNotIn("## 来源锚定的改写候选", text)
        self.assertIn("## 来源信任边界", text)
        self.assertIn("| 长 MD/TEX/TXT |", text)
        self.assertNotIn("validate_humanize_candidate_queue.py", text)

    def test_long_workflow_transform_removes_convergence_answer_surface(self) -> None:
        raw = (self.skill / "references" / "long-document-workflow.md").read_bytes()
        projected, removed = builder._transform_long_workflow(raw)
        text = projected.decode("utf-8")
        self.assertEqual(2, len(removed))
        self.assertIn("## 16. 独立复读", text)
        self.assertNotIn("prepare_humanize_second_pass.py", text)
        self.assertNotIn("verify_humanize_second_pass.py", text)
        self.assertNotIn("全部 fresh 决策为 `NO_CHANGE`", text)

    def test_corpus_transform_emits_strict_detector_only_registry(self) -> None:
        raw = (self.skill / "references" / "corpus-action-sources.json").read_bytes()
        original = json.loads(raw.decode("utf-8"))

        projected_raw, removed = builder._transform_corpus_action_sources(raw)
        projected = json.loads(projected_raw.decode("utf-8"))

        self.assertEqual(4, len(removed))
        self.assertEqual(17, removed[0]["count"])
        self.assertEqual(
            {
                "schema_version": "humanize-negative-guard-registry/v2",
                "registry_id": "humanize-academic-chinese/corpus-negative-guards/v2",
            },
            {key: projected[key] for key in ("schema_version", "registry_id")},
        )
        self.assertEqual({"schema_version", "registry_id", "guards"}, set(projected))
        self.assertEqual(5, len(projected["guards"]))
        self.assertTrue(
            all(set(guard) == {"id", "scene", "detector"} for guard in projected["guards"])
        )
        source_origins = {
            source["id"]: source["origin_class"] for source in original["sources"]
        }
        runtime_origins = {"MODEL_GENERATED", "MODEL_ORIGIN_UNRESOLVED"}
        expected = {
            card["id"]: {
                "scene": card["scene"],
                "detector": builder.negative_guards.normalize_detector(
                    card["detector"],
                    card["id"],
                    allow_legacy_regex=True,
                ),
            }
            for card in original["action_cards"]
            if card["kind"] == "negative_guard"
            and all(
                source_origins[ref["source_id"]] in runtime_origins
                for ref in card["source_refs"]
            )
        }
        actual = {
            guard["id"]: {"scene": guard["scene"], "detector": guard["detector"]}
            for guard in projected["guards"]
        }
        self.assertEqual(expected, actual)
        self.assertEqual(6, removed[2]["count"])
        serialized = projected_raw.decode("utf-8")
        self.assertNotIn("COURSE-DECISION-01", serialized)
        self.assertNotIn("MODELING-METRIC-ROLE-01", serialized)
        for forbidden in (
            "sources",
            "source_refs",
            "origin_class",
            "source_tier",
            "path",
            "action",
            "requires",
            "forbids",
            "use_limit",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_projection_contains_loader_but_not_full_action_builder(self) -> None:
        _result, output, _manifest = self.build()
        self.assertTrue((output / "scripts" / "load_humanize_negative_guards.py").is_file())
        self.assertFalse((output / "scripts" / "build_humanize_action_profile.py").exists())

    def test_corpus_transform_rejects_local_negative_permission_widening(self) -> None:
        raw = (self.skill / "references" / "corpus-action-sources.json").read_bytes()
        trust_path = self.skill / "references" / "source-provenance-trust.json"
        trust = json.loads(trust_path.read_text(encoding="utf-8"))
        trust["origin_decisions"]["THIRD_PARTY"]["allowed_uses"].append(
            "NEGATIVE_GUARD"
        )
        with self.assertRaisesRegex(builder.ProjectionError, "decision matrix drifted"):
            builder._transform_corpus_action_sources(
                raw, json.dumps(trust, ensure_ascii=False).encode("utf-8")
            )

    def test_candidate_queue_control_is_absent_from_generator_projection(self) -> None:
        _result, output, _manifest = self.build()
        for relative in (
            "scripts/prepare_humanize_candidate_revision.py",
            "scripts/validate_humanize_candidate_queue.py",
        ):
            self.assertFalse((output / relative).exists())

    def test_missing_or_duplicate_transform_anchor_fails_closed(self) -> None:
        skill_path = self.skill / "SKILL.md"
        original = skill_path.read_text(encoding="utf-8")
        for name, changed in (
            ("missing", original.replace("## 生成资格采集边界", "## 资格边界", 1)),
            (
                "duplicate",
                original.replace(
                    "| 验证 Skill |",
                    "| 验证 Skill | duplicate |\n| 验证 Skill |",
                    1,
                ),
            ),
        ):
            with self.subTest(name=name):
                with self.assertRaises(builder.ProjectionError):
                    builder._transform_skill(changed.encode("utf-8"))

    def test_invalid_utf8_skill_fails(self) -> None:
        with self.assertRaisesRegex(builder.ProjectionError, "strict UTF-8"):
            builder._transform_skill(b"---\nname: x\ndescription: x\n---\n\xff")

    def test_unknown_source_file_fails_instead_of_auto_including(self) -> None:
        (self.skill / "references" / "new-helpful-rule.md").write_text(
            "看似生产规则", encoding="utf-8"
        )
        with self.assertRaisesRegex(builder.ProjectionError, "unclassified source file"):
            self.build()

    def test_unknown_oracle_like_file_also_fails(self) -> None:
        (self.skill / "references" / "oracle-copy.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(builder.ProjectionError, "unclassified source file"):
            self.build()

    def test_policy_cannot_widen_include_set(self) -> None:
        payload = self.policy_payload()
        payload["include_exact"].append("references/evaluation-contract.md")
        payload["exclude_exact"].remove("references/evaluation-contract.md")
        self.write_policy(payload)
        with self.assertRaisesRegex(builder.ProjectionError, "include_exact drifted"):
            self.build()

    def test_policy_cannot_drop_trust_or_oracle_exclusion(self) -> None:
        for path in (
            "references/generation-qualification-trust.json",
            "references/generation-qualification-oracles.json",
            "scripts/replay_humanize_validation_record.py",
        ):
            with self.subTest(path=path):
                payload = self.policy_payload()
                payload["exclude_exact"].remove(path)
                self.write_policy(payload)
                with self.assertRaisesRegex(builder.ProjectionError, "exclude_exact drifted"):
                    self.build()
                shutil.copyfile(SKILL / "references" / "generator-projection-policy.json", self.skill / "references" / "generator-projection-policy.json")

    def test_duplicate_policy_key_is_rejected(self) -> None:
        path = self.skill / "references" / "generator-projection-policy.json"
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw[:-2] + ',"policy_id":"duplicate"}\n', encoding="utf-8")
        with self.assertRaisesRegex(builder.ProjectionError, "duplicate JSON key"):
            self.build()

    def test_missing_policy_path_is_rejected(self) -> None:
        (self.skill / "references" / "course-notes.md").unlink()
        with self.assertRaisesRegex(builder.ProjectionError, "policy paths are absent"):
            self.build()

    def test_forbidden_basename_leak_in_production_file_is_rejected(self) -> None:
        path = self.skill / "references" / "course-notes.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n参见 generation-qualification-oracles.json。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ProjectionError, "forbidden evaluation basename"):
            self.build()

    def test_control_id_leak_in_production_file_is_rejected(self) -> None:
        path = self.skill / "references" / "course-notes.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n执行 PATH-05。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ProjectionError, "qualification control ID leaked"):
            self.build()

    def test_non_numeric_global_control_id_leak_is_rejected(self) -> None:
        path = self.skill / "references" / "course-notes.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n执行 PROTECTED/hash-zero。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ProjectionError, "hidden catalog identifier leaked"):
            self.build()

    def test_benign_capability_content_drift_requires_policy_approval(self) -> None:
        path = self.skill / "references" / "course-notes.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n这是一条没有控制词的新增规则。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ProjectionError, "source hash is not approved"):
            self.build()

    def test_transform_registry_approval_drift_is_rejected(self) -> None:
        changed_registry = dict(builder.TRANSFORM_REGISTRY)
        transform_id = next(iter(changed_registry))
        changed_registry[transform_id] += "/unapproved-drift"

        with mock.patch.object(builder, "TRANSFORM_REGISTRY", changed_registry):
            with self.assertRaisesRegex(
                builder.ProjectionError,
                "approved_transform_registry_sha256 does not approve",
            ):
                builder.load_policy(
                    self.skill / "references" / "generator-projection-policy.json"
                )

    def test_missing_local_reference_is_rejected(self) -> None:
        path = self.skill / "references" / "course-notes.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n参见 [缺失](references/not-present.md)。\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(builder.ProjectionError, "reference closure failed"):
            self.build()

    def test_manifest_inside_projection_is_rejected(self) -> None:
        output = self.root / "projection"
        with self.assertRaisesRegex(builder.ProjectionError, "manifest must remain outside"):
            builder.build_projection(self.skill, output, output / "manifest.json")

    def test_manifest_inside_source_skill_is_rejected(self) -> None:
        with self.assertRaisesRegex(builder.ProjectionError, "outside the source Skill"):
            builder.build_projection(
                self.skill,
                self.root / "projection",
                self.skill / "build" / "projection-manifest.json",
            )

    def test_source_and_output_containment_is_rejected(self) -> None:
        with self.assertRaisesRegex(builder.ProjectionError, "must not contain each other"):
            builder.build_projection(
                self.skill,
                self.skill / "projection",
                self.root / "manifest.json",
            )

    def test_manifest_publish_failure_rolls_back_projection(self) -> None:
        output = self.root / "projection"
        manifest = self.root / "manifest.json"
        with (
            mock.patch.object(builder, "_quick_validate", return_value="PASS"),
            mock.patch.object(builder.os, "replace", side_effect=OSError("publish failed")),
            self.assertRaisesRegex(OSError, "publish failed"),
        ):
            builder.build_projection(self.skill, output, manifest)
        self.assertFalse(output.exists())
        self.assertFalse(manifest.exists())

    def test_manifest_publish_base_exceptions_roll_back_and_allow_retry(self) -> None:
        for index, interruption in enumerate((KeyboardInterrupt(), SystemExit(9)), 1):
            with self.subTest(interruption=type(interruption).__name__):
                output = self.root / f"interrupted-projection-{index}"
                manifest = self.root / f"interrupted-manifest-{index}.json"
                with (
                    mock.patch.object(builder, "_quick_validate", return_value="PASS"),
                    mock.patch.object(builder.os, "replace", side_effect=interruption),
                    self.assertRaises(type(interruption)),
                ):
                    builder.build_projection(self.skill, output, manifest)
                self.assertFalse(output.exists())
                self.assertFalse(manifest.exists())

                with mock.patch.object(builder, "_quick_validate", return_value="PASS"):
                    result = builder.build_projection(self.skill, output, manifest)
                self.assertTrue(output.is_dir())
                self.assertTrue(manifest.is_file())
                self.assertEqual(
                    "humanize-generator-projection-manifest/v2",
                    result["schema_version"],
                )

    def test_qualification_section_cannot_swallow_an_inserted_h2(self) -> None:
        raw = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        changed = raw.replace(
            "## 来源锚定的改写候选",
            "## 新增生产规则\n\n这段内容不得被静默删除。\n\n## 来源锚定的改写候选",
            1,
        )
        with self.assertRaisesRegex(builder.ProjectionError, "immediate next H2"):
            builder._transform_skill(changed.encode("utf-8"))

    def test_qualification_heading_inside_code_fence_is_not_an_anchor(self) -> None:
        raw = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        changed = raw.replace(
            "## 生成资格采集边界",
            "```text\n## 生成资格采集边界\n```",
            1,
        )
        with self.assertRaisesRegex(builder.ProjectionError, "unfenced heading"):
            builder._transform_skill(changed.encode("utf-8"))

    def test_existing_output_or_manifest_is_rejected(self) -> None:
        output = self.root / "projection"
        output.mkdir()
        with self.assertRaisesRegex(builder.ProjectionError, "must not already exist"):
            builder.build_projection(self.skill, output, self.root / "manifest.json")
        output.rmdir()
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(builder.ProjectionError, "must not already exist"):
            builder.build_projection(self.skill, output, manifest)

    def test_symlink_or_reparse_source_is_rejected(self) -> None:
        link = self.skill / "references" / "linked.md"
        try:
            link.symlink_to(self.skill / "references" / "course-notes.md")
        except OSError as error:
            self.skipTest(f"symlink creation is unavailable: {error}")
        with self.assertRaisesRegex(builder.ProjectionError, "symlink or reparse point"):
            self.build()

    def test_hardlinked_capability_files_are_rejected(self) -> None:
        first = self.skill / "references" / "course-notes.md"
        second = self.skill / "references" / "workflow.md"
        second.unlink()
        try:
            os.link(first, second)
        except OSError as error:
            self.skipTest(f"hard-link creation is unavailable: {error}")
        with self.assertRaisesRegex(builder.ProjectionError, "hard-link identity"):
            self.build()

    def test_projected_tree_hash_recomputes_from_retained_bytes(self) -> None:
        result, output, _manifest = self.build()
        files = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        self.assertEqual(result["projection_tree_sha256"], builder._tree_hash(files))
        files["SKILL.md"] += b"\n"
        self.assertNotEqual(result["projection_tree_sha256"], builder._tree_hash(files))

    def test_projection_verifier_rejects_unexpected_empty_directory(self) -> None:
        result, output, _manifest = self.build()
        (output / "unexpected-empty").mkdir()
        manifest = {
            key: value
            for key, value in result.items()
            if key not in {"manifest_sha256", "projection_root", "manifest_path"}
        }
        with self.assertRaisesRegex(builder.ProjectionError, "unexpected directory"):
            builder.verify_projection(output, manifest, source_root=self.skill)

    def test_projection_verifier_requires_source_unless_explicitly_downgraded(self) -> None:
        result, output, _manifest = self.build()
        manifest = self.manifest_core(result)

        with self.assertRaisesRegex(builder.ProjectionError, "source_root is required"):
            builder.verify_projection(output, manifest)
        downgraded = builder.verify_projection(
            output,
            manifest,
            allow_source_unverified=True,
        )
        self.assertEqual(
            "PROJECTED_BYTES_CURRENT_BUILDER_ONLY",
            downgraded["verification_scope"],
        )
        self.assertEqual("NOT_EVALUATED", downgraded["source_currentness"])
        self.assertEqual("NOT_EVALUATED", downgraded["historical_authenticity"])

    def test_source_bound_verifier_rebuilds_all_manifest_metadata(self) -> None:
        result, output, _manifest = self.build()
        manifest = self.manifest_core(result)
        verified = builder.verify_projection(output, manifest, source_root=self.skill)

        self.assertEqual("SOURCE_BOUND_CURRENT", verified["verification_scope"])
        self.assertEqual("PASS", verified["source_currentness"])

        attacks = []
        missing_excluded = json.loads(json.dumps(manifest))
        missing_excluded["excluded"] = []
        attacks.append(("excluded", missing_excluded))

        fabricated_transform = json.loads(json.dumps(manifest))
        fabricated_transform["transformations"][0]["removed_spans"] = [
            {"fabricated": "PASS"}
        ]
        attacks.append(("transformations", fabricated_transform))

        forged_source = json.loads(json.dumps(manifest))
        transformed_path = forged_source["transformations"][0]["path"]
        transformed_file = next(
            item for item in forged_source["files"] if item["path"] == transformed_path
        )
        transformed_file["source_sha256"] = "0" * 64
        forged_source["transformations"][0]["source_sha256"] = "0" * 64
        attacks.append(("source hash", forged_source))

        for label, attacked in attacks:
            with self.subTest(label=label), self.assertRaises(builder.ProjectionError):
                builder.verify_projection(output, attacked, source_root=self.skill)

    def test_projected_python_import_closure_is_executed(self) -> None:
        result, output, _manifest = self.build()
        manifest = self.manifest_core(result)
        loader = output / "scripts" / "load_humanize_negative_guards.py"
        loader.write_bytes(loader.read_bytes() + b"\nraise RuntimeError('import probe')\n")
        loader_record = next(
            item
            for item in manifest["files"]
            if item["path"] == "scripts/load_humanize_negative_guards.py"
        )
        loader_raw = loader.read_bytes()
        loader_record["size"] = len(loader_raw)
        loader_record["projected_sha256"] = sha256(loader_raw)
        loader_record["source_sha256"] = sha256(loader_raw)
        projected = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        manifest["projection_tree_sha256"] = builder._tree_hash(projected)

        with self.assertRaisesRegex(builder.ProjectionError, "import closure failed"):
            builder.verify_projection(
                output,
                manifest,
                allow_source_unverified=True,
            )

    def test_source_bound_verifier_rejects_source_builder_drift(self) -> None:
        result, output, _manifest = self.build()
        manifest = self.manifest_core(result)
        source_builder = self.skill / "scripts" / "build_humanize_generator_projection.py"
        source_builder.write_bytes(source_builder.read_bytes() + b"\n# drift\n")

        with self.assertRaisesRegex(builder.ProjectionError, "source Skill builder differs"):
            builder.verify_projection(output, manifest, source_root=self.skill)

    def test_projection_verifier_rejects_root_symlink_or_junction(self) -> None:
        result, output, _manifest = self.build()
        alias = self.root / "projection-root-alias"
        if os.name == "nt":
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(alias), str(output)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                shell=False,
            )
            if created.returncode != 0:
                self.skipTest("Windows junction creation is unavailable")
        else:
            alias.symlink_to(output, target_is_directory=True)
        try:
            with self.assertRaisesRegex(
                builder.ProjectionError, "regular non-reparse directory"
            ):
                builder.verify_projection(alias, result, source_root=self.skill)
        finally:
            alias.rmdir()

    def test_external_source_paths_are_inventory_only(self) -> None:
        result, output, _manifest = self.build()
        refs = result["declared_external_capability_refs"]
        self.assertEqual([], refs)
        original = json.loads(
            (self.skill / "references" / "corpus-action-sources.json").read_text(encoding="utf-8")
        )
        provisional_paths = {
            source["path"]
            for source in original["sources"]
            if source.get("role") == "positive_action_reference"
            and source.get("origin_class") == "UNKNOWN"
        }
        self.assertTrue(provisional_paths)
        self.assertTrue(set(refs).isdisjoint(provisional_paths))


if __name__ == "__main__":
    unittest.main()
