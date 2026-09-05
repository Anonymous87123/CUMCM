import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "validate_humanize_candidate_queue.py"
SPEC = importlib.util.spec_from_file_location("validate_humanize_candidate_queue", SCRIPT)
candidate_validator = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(candidate_validator)


def write_catalog(
    path: Path,
    source: Path,
    *,
    role: str = "positive_action_reference",
    origin_class: str = "HUMAN_CONFIRMED",
) -> None:
    payload = {
        "schema_version": 2,
        "purpose": "Test-only source action catalog without excerpts.",
        "global_copy_limit": {"max_contiguous_han_chars": 7, "rule": "No copying."},
        "sources": [
            {
                "id": "SOURCE-ONE",
                "source_tier": "A1",
                "origin_class": origin_class,
                "scene_scope": ["RESEARCH"],
                "role": role,
                "path": str(source),
                "provenance": "test",
                "use_limit": "test",
            }
        ],
        "action_cards": [
            {
                "id": "RESEARCH-ONE-01",
                "scene": "RESEARCH",
                "kind": "positive_action",
                "action": "Bind a stated scope to an already present result.",
                "requires": ["scope", "reported result"],
                "required_anchor_roles": ["scope"],
                "forbids": ["invented evidence"],
                "source_refs": [{"source_id": "SOURCE-ONE", "line_start": 1, "line_end": 1}],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class CandidateQueueValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.tex"
        self.source.write_text("来自语料的八字短语甲乙丙丁戊己庚辛壬\n", encoding="utf-8")
        self.catalog = self.root / "catalog.json"
        write_catalog(self.catalog, self.source)
        self.original_default_catalog = candidate_validator.DEFAULT_CATALOG
        candidate_validator.DEFAULT_CATALOG = self.catalog
        self.before = self.root / "before.md"
        self.after = self.root / "after.md"
        self.before.write_text("值得注意的是，实验仅在当前条件下记录到峰值。\n", encoding="utf-8")
        self.after.write_text("实验仅在当前条件下记录到峰值。\n", encoding="utf-8")

    def tearDown(self) -> None:
        candidate_validator.DEFAULT_CATALOG = self.original_default_catalog
        self.temp_dir.cleanup()

    def write_candidate(self, **changes: object) -> Path:
        payload: dict[str, object] = {
            "schema_version": "2.0",
            "candidate_id": "research-scope-001",
            "scene": "RESEARCH",
            "corpus_action_support": "NONE",
            "before_path": str(self.before),
            "after_path": str(self.after),
            "action_cards": [],
            "action_evidence": {},
            "anchors": [
                {
                    "id": "scope-anchor",
                    "before_text": "实验仅在当前条件下记录到峰值。",
                    "after_text": "实验仅在当前条件下记录到峰值。",
                    "role": "scope",
                }
            ],
            "keep_reasons": {},
        }
        payload.update(changes)
        path = self.root / "candidate.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def validate(self, candidate: Path, *, queue: bool = False) -> dict:
        output = self.root / "queue" if queue else None
        return candidate_validator.validate_candidate(
            candidate,
            catalog_path=self.catalog,
            queue_dir=output,
        )

    def configure_negative_guard(
        self,
        detector: object,
        *,
        guard_id: str = "NEGATIVE-BROKEN-01",
    ) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"][0].update(
            {
                "origin_class": "MODEL_GENERATED",
                "role": "negative_template_reference",
            }
        )
        catalog["action_cards"][0].update(
            {
                "id": guard_id,
                "kind": "negative_guard",
                "required_anchor_roles": ["template"],
                "detector": detector,
            }
        )
        self.catalog.write_text(
            json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
        )

    def assert_redacted_cli_failure(
        self,
        stdout: io.StringIO,
        stderr: io.StringIO,
        *,
        expected: str,
        sensitive_marker: str,
    ) -> None:
        rendered_error = stderr.getvalue()
        self.assertEqual("", stdout.getvalue())
        self.assertIn(expected, rendered_error)
        self.assertNotIn(sensitive_marker, rendered_error)
        self.assertNotIn("Traceback", rendered_error)
        self.assertNotIn(str(self.root.resolve()), rendered_error)

    def test_candidate_package_rejects_duplicate_json_keys(self) -> None:
        candidate = self.write_candidate()
        raw = candidate.read_text(encoding="utf-8")
        candidate.write_text(
            '{"candidate_id":"shadow",' + raw.lstrip()[1:],
            encoding="utf-8",
        )

        with self.assertRaisesRegex(candidate_validator.CandidateError, "duplicate_json_key:candidate_id"):
            self.validate(candidate)

    def test_candidate_package_rejects_non_finite_json_numbers(self) -> None:
        candidate = self.write_candidate()
        raw = candidate.read_text(encoding="utf-8")
        candidate.write_text(
            raw.replace('"candidate_id": "research-scope-001"', '"candidate_id": NaN'),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(candidate_validator.CandidateError, "non_finite_json_number:NaN"):
            self.validate(candidate)

    def warning_candidate(self, **changes: object) -> Path:
        self.before.write_text("结果可能变化。\n", encoding="utf-8")
        self.after.write_text("结果发生变化。\n", encoding="utf-8")
        first = candidate_validator.output_validator.validate(
            self.before,
            self.after,
            scene="RESEARCH",
        )
        request = first["warning_review_request"]
        fingerprint = request["warnings"][0]["warning_fingerprint"]
        payload: dict[str, object] = {
            "anchors": [
                {
                    "id": "scope-anchor",
                    "before_text": "结果可能变化。",
                    "after_text": "结果发生变化。",
                    "role": "scope",
                }
            ],
            "warning_resolutions": {
                fingerprint: "人工建议核对删除的是重复缓和而非结论强度",
            },
            "warning_review_request_sha256": request["request_sha256"],
        }
        payload.update(changes)
        return self.write_candidate(**payload)

    def test_valid_candidate_enters_review_without_exporting_source_prose(self) -> None:
        result = self.validate(self.write_candidate(), queue=True)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        self.assertEqual("PENDING_REVIEW", result["queue_disposition"])
        self.assertEqual("STRUCTURAL_PASS", result["action_contract"]["status"])
        self.assertEqual("NOT_EVALUATED", result["action_contract"]["semantic_requirements"])
        self.assertTrue((self.root / "queue" / "review" / "research-scope-001.json").is_file())
        self.assertFalse((self.root / "queue" / "accepted" / "research-scope-001.json").exists())
        self.assertFalse((self.root / "queue" / "rejected" / "research-scope-001.json").exists())
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("来自语料的八字短语甲乙丙丁戊己庚辛壬", serialized)

    def test_external_catalog_cannot_promote_self_declared_human_source_to_acceptance(self) -> None:
        candidate_validator.DEFAULT_CATALOG = self.original_default_catalog
        try:
            result = self.validate(
                self.write_candidate(
                    corpus_action_support="ACTION_CARDS",
                    action_cards=["RESEARCH-ONE-01"],
                    action_evidence={"RESEARCH-ONE-01": ["scope-anchor"]},
                ),
                queue=True,
            )
        finally:
            candidate_validator.DEFAULT_CATALOG = self.catalog

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        self.assertEqual("EXTERNAL_UNVERIFIED", result["catalog_authority"])
        self.assertIn(
            "external_catalog_not_production_trusted",
            result["review_reasons"],
        )
        self.assertTrue(
            (self.root / "queue" / "review" / "research-scope-001.result.json").is_file()
        )

    def test_installed_default_path_cannot_promote_local_human_claim(self) -> None:
        result = self.validate(
            self.write_candidate(
                corpus_action_support="ACTION_CARDS",
                action_cards=["RESEARCH-ONE-01"],
                action_evidence={"RESEARCH-ONE-01": ["scope-anchor"]},
            ),
            queue=True,
        )

        self.assertEqual("INSTALLED_DEFAULT", result["catalog_authority"])
        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        self.assertIn(
            "provisional_action_card:RESEARCH-ONE-01",
            result["review_reasons"],
        )
        selected = result["action_contract"]["selected_cards"][0]
        self.assertEqual("PROVISIONAL", selected["origin_assurance"])

    def test_unknown_action_card_is_provisional_and_cannot_be_accepted(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"][0]["origin_class"] = "UNKNOWN"
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

        result = self.validate(
            self.write_candidate(
                corpus_action_support="ACTION_CARDS",
                action_cards=["RESEARCH-ONE-01"],
                action_evidence={"RESEARCH-ONE-01": ["scope-anchor"]},
            ),
            queue=True,
        )

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        self.assertIn(
            "scene_corpus_origin_unresolved:RESEARCH",
            result["review_reasons"],
        )
        self.assertIn(
            "provisional_action_card:RESEARCH-ONE-01",
            result["review_reasons"],
        )
        selected = result["action_contract"]["selected_cards"][0]
        self.assertEqual("PROVISIONAL", selected["origin_assurance"])
        self.assertEqual(["UNKNOWN"], selected["source_origin_classes"])
        self.assertTrue(
            (self.root / "queue" / "review" / "research-scope-001.json").is_file()
        )

    def test_provisional_scene_can_opt_out_of_action_cards_and_pass_style_gate(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"][0]["origin_class"] = "UNKNOWN"
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        candidate = self.write_candidate(
            corpus_action_support="NONE",
            action_cards=[],
            action_evidence={},
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(["style_validator_review"], result["review_reasons"])
        self.assertEqual(
            "SUPPORTED_PROVISIONAL",
            result["action_contract"]["scene_corpus_status"]["status"],
        )
        self.assertEqual("NONE", result["action_contract"]["corpus_action_support"])

    def test_warning_resolution_uses_identity_free_request_bound_proposal(self) -> None:
        anonymous = self.validate(self.warning_candidate())
        self.assertEqual("REVIEW", anonymous["status"])
        self.assertEqual([], anonymous["contract_errors"])
        proposal = anonymous["style_validation"]["warning_proposal_state"]
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["reviewer_identifier_collected"])

        empty = self.validate(self.warning_candidate(warning_review={}))
        self.assertEqual("FAIL", empty["status"])
        self.assertIn("warning_reviewer_identity_metadata_retired", empty["contract_errors"])

    def test_agent_cannot_self_attest_warning_resolution_proposal(self) -> None:
        result = self.validate(
            self.warning_candidate(
                warning_review={
                    "reviewer_kind": "AGENT",
                    "reviewer_id": "forward-agent",
                }
            )
        )

        self.assertEqual("FAIL", result["status"])
        self.assertIn("warning_reviewer_identity_metadata_retired", result["contract_errors"])

    def test_identity_free_proposal_never_accepts_candidate(self) -> None:
        result = self.validate(self.warning_candidate(), queue=True)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        proposal = result["style_validation"]["warning_proposal_state"]
        self.assertEqual("UNVERIFIED_CALLER_PROPOSAL", proposal["proposal_source"])
        self.assertFalse(proposal["identity_verified"])
        self.assertFalse(proposal["review_clearance_granted"])
        self.assertNotIn("reviewer_id_sha256", json.dumps(result, ensure_ascii=False))
        self.assertTrue(
            (self.root / "queue" / "review" / "research-scope-001.json").is_file()
        )

    def test_warning_review_metadata_is_rejected_without_resolution_proposal(self) -> None:
        result = self.validate(
            self.write_candidate(
                warning_review={
                    "reviewer_kind": "HUMAN",
                    "reviewer_id": "external-reviewer-label",
                }
            )
        )

        self.assertEqual("FAIL", result["status"])
        self.assertIn("warning_reviewer_identity_metadata_retired", result["contract_errors"])

    def test_legacy_acceptance_and_authority_field_injection_are_rejected(self) -> None:
        legacy = self.validate(self.write_candidate(accepted_warnings={}))
        self.assertEqual("FAIL", legacy["status"])
        self.assertIn("retired_accepted_warnings_field", legacy["contract_errors"])

        injected = self.validate(self.write_candidate(status="PASS", identity_verified=True))
        self.assertEqual("FAIL", injected["status"])
        self.assertTrue(
            any(item.startswith("unknown_candidate_fields:") for item in injected["contract_errors"])
        )

    def test_mismatched_or_unavailable_card_fails_the_contract(self) -> None:
        candidate = self.write_candidate(
            corpus_action_support="ACTION_CARDS",
            action_cards=["UNKNOWN-01"],
            action_evidence={"UNKNOWN-01": ["scope-anchor"]},
        )
        result = self.validate(candidate)

        self.assertEqual("FAIL", result["status"])
        self.assertIn("unknown_action_card:UNKNOWN-01", result["contract_errors"])

        self.source.unlink()
        result = self.validate(
            self.write_candidate(
                corpus_action_support="ACTION_CARDS",
                action_cards=["RESEARCH-ONE-01"],
                action_evidence={"RESEARCH-ONE-01": ["scope-anchor"]},
            )
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertIn("unavailable_action_card:RESEARCH-ONE-01", result["review_reasons"])

    def test_missing_candidate_anchor_fails_and_is_rejected(self) -> None:
        candidate = self.write_candidate(
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "实验仅在当前条件下记录到峰值。",
                    "after_text": "候选稿中不存在的锚点。",
                    "role": "scope",
                }
            ]
        )
        result = self.validate(candidate, queue=True)

        self.assertEqual("FAIL", result["status"])
        self.assertIn("anchor_after_missing:scope-anchor", result["contract_errors"])
        self.assertTrue((self.root / "queue" / "rejected" / "research-scope-001.json").is_file())

    def test_source_sentence_copy_and_future_bridge_cannot_be_accepted(self) -> None:
        self.before.write_text("值得注意的是，甲乙丙丁戊己庚辛壬用于范围说明。\n", encoding="utf-8")
        self.after.write_text(
            "甲乙丙丁戊己庚辛壬用于范围说明，并为后续研究提供线索。\n",
            encoding="utf-8",
        )
        candidate = self.write_candidate(
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "甲乙丙丁戊己庚辛壬用于范围说明。",
                    "after_text": "甲乙丙丁戊己庚辛壬用于范围说明",
                    "role": "scope",
                }
            ]
        )
        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertFalse(result["accepted"])
        self.assertEqual(0, result["source_copy_check"]["introduced_match_count"])
        self.assertGreaterEqual(result["source_copy_check"]["inherited_match_count"], 1)
        self.assertIn("automatic_future_bridge", result["template_check"]["codes"])

    def test_only_new_source_copy_blocks_and_reports_candidate_location(self) -> None:
        self.before.write_text("值得注意的是，当前结果仅用于范围说明。\n", encoding="utf-8")
        self.after.write_text("来自语料的八字短语甲乙丙丁戊己庚辛壬。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "当前结果仅用于范围说明。",
                    "after_text": "来自语料的八字短语",
                    "role": "scope",
                }
            ]
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertGreater(result["source_copy_check"]["introduced_match_count"], 0)
        first = result["source_copy_check"]["introduced_matches"][0]
        self.assertEqual(1, first["candidate_line"])
        self.assertGreaterEqual(first["candidate_column"], 1)
        self.assertNotIn("来自语料的八字短语", json.dumps(result, ensure_ascii=False))

    def test_queue_revision_replaces_stale_review_head_and_requires_lineage(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate, queue=True)
        review = self.root / "queue" / "review" / "research-scope-001.json"
        self.assertEqual("REVIEW", first["status"])
        self.assertTrue(review.is_file())
        first_head = review.read_bytes()

        self.after.write_text("实验仅在当前条件下记录到峰值，并为后续研究提供线索。\n", encoding="utf-8")
        collision = self.write_candidate(
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "实验仅在当前条件下记录到峰值。",
                    "after_text": "实验仅在当前条件下记录到峰值",
                    "role": "scope",
                }
            ]
        )
        with self.assertRaisesRegex(candidate_validator.CandidateError, "candidate_id_collision"):
            self.validate(collision, queue=True)
        self.assertEqual(first_head, review.read_bytes())

        revised = self.write_candidate(
            supersedes_candidate_sha256=first["candidate_sha256"],
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "实验仅在当前条件下记录到峰值。",
                    "after_text": "实验仅在当前条件下记录到峰值",
                    "role": "scope",
                }
            ],
        )
        second = self.validate(revised, queue=True)

        self.assertEqual("REVIEW", second["status"])
        self.assertTrue(review.is_file())
        self.assertNotEqual(first_head, review.read_bytes())
        self.assertFalse((self.root / "queue" / "accepted" / "research-scope-001.json").exists())
        self.assertFalse((self.root / "queue" / "rejected" / "research-scope-001.json").exists())
        self.assertEqual(first["candidate_sha256"], second["supersedes_candidate_sha256"])

        rerun = self.validate(revised, queue=True)
        self.assertTrue(rerun["queue"]["idempotent_rerun"])
        self.assertEqual(second["candidate_sha256"], rerun["candidate_sha256"])

    def test_existing_queue_result_rejects_non_finite_json_numbers(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate, queue=True)
        result_path = self.root / "queue" / "review" / "research-scope-001.result.json"
        result_path.write_text(
            '{"candidate_sha256":"' + first["candidate_sha256"] + '","poison":Infinity}',
            encoding="utf-8",
        )

        self.after.write_text("实验仅在当前条件下记录到峰值，并为后续研究提供线索。\n", encoding="utf-8")
        revised = self.write_candidate(
            supersedes_candidate_sha256=first["candidate_sha256"],
            anchors=[{
                "id": "scope-anchor",
                "before_text": "实验仅在当前条件下记录到峰值。",
                "after_text": "实验仅在当前条件下记录到峰值",
                "role": "scope",
            }],
        )
        with self.assertRaisesRegex(candidate_validator.CandidateError, "queue_state_unreadable"):
            self.validate(revised, queue=True)

    def test_candidate_hash_binds_before_and_after_content(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate)

        self.after.write_text("实验仅在另一条件下记录到峰值。\n", encoding="utf-8")
        second = self.validate(candidate)

        self.assertNotEqual(first["candidate_sha256"], second["candidate_sha256"])
        self.assertNotEqual(
            first["artifact_hashes"]["after_sha256"],
            second["artifact_hashes"]["after_sha256"],
        )

    def test_artifact_change_after_validation_cannot_be_published(self) -> None:
        candidate = self.write_candidate()
        original_copy_check = candidate_validator._source_copy_check

        def mutate_after(*args, **kwargs):
            result = original_copy_check(*args, **kwargs)
            self.after.write_text("实验仅在另一条件下记录到峰值。\n", encoding="utf-8")
            return result

        with mock.patch.object(candidate_validator, "_source_copy_check", side_effect=mutate_after):
            with self.assertRaisesRegex(
                candidate_validator.CandidateError,
                "artifact_changed_before_publish:after",
            ):
                self.validate(candidate, queue=True)

        self.assertFalse((self.root / "queue" / "accepted" / "research-scope-001.json").exists())

    def test_all_text_gates_share_one_frozen_snapshot_during_swap_restore(self) -> None:
        candidate = self.write_candidate()
        original_text = self.after.read_text(encoding="utf-8")
        seen: dict[str, Path] = {}
        observed_scene: list[str] = []
        original_anchor = candidate_validator._anchor_contract
        original_style = candidate_validator.output_validator.validate
        original_copy = candidate_validator._source_copy_check
        original_template = candidate_validator._template_check

        def anchor(parsed):
            seen["anchor"] = parsed["after_path"]
            return original_anchor(parsed)

        def style(before_path, after_path, **kwargs):
            seen["style"] = after_path
            self.after.write_text("来自语料的八字短语甲乙丙丁戊己庚辛。\n", encoding="utf-8")
            try:
                return original_style(before_path, after_path, **kwargs)
            finally:
                self.after.write_text(original_text, encoding="utf-8")

        def copy_gate(parsed, sources, cards):
            seen["copy"] = parsed["after_path"]
            return original_copy(parsed, sources, cards)

        def template(after_path, guards=(), *, resolved_scene="GENERAL"):
            seen["template"] = after_path
            observed_scene.append(resolved_scene)
            return original_template(
                after_path, guards, resolved_scene=resolved_scene
            )

        with (
            mock.patch.object(candidate_validator, "_anchor_contract", side_effect=anchor),
            mock.patch.object(candidate_validator.output_validator, "validate", side_effect=style),
            mock.patch.object(candidate_validator, "_source_copy_check", side_effect=copy_gate),
            mock.patch.object(candidate_validator, "_template_check", side_effect=template),
        ):
            result = self.validate(candidate)

        self.assertEqual({"anchor", "style", "copy", "template"}, set(seen))
        self.assertEqual(1, len(set(seen.values())))
        self.assertEqual(["RESEARCH"], observed_scene)
        self.assertNotEqual(self.after.resolve(), next(iter(seen.values())).resolve())
        self.assertEqual(original_text, self.after.read_text(encoding="utf-8"))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("artifact_changed_before_publish:after", result["contract_errors"])

    def test_queue_target_cannot_alias_or_contain_after_input(self) -> None:
        candidate = self.write_candidate()
        original_after = self.after.read_bytes()

        with self.assertRaisesRegex(candidate_validator.CandidateError, "queue_input_alias:after"):
            candidate_validator.validate_candidate(
                candidate,
                catalog_path=self.catalog,
                queue_dir=self.after,
            )

        self.assertEqual(original_after, self.after.read_bytes())

        containing = self.root / "contains-input"
        containing.mkdir()
        nested_after = containing / "after.md"
        nested_after.write_bytes(original_after)
        nested_candidate = self.write_candidate(after_path=str(nested_after))
        with self.assertRaisesRegex(candidate_validator.CandidateError, "queue_contains_input:after"):
            candidate_validator.validate_candidate(
                nested_candidate,
                catalog_path=self.catalog,
                queue_dir=containing,
            )

    def test_source_profile_change_after_validation_cannot_be_published(self) -> None:
        candidate = self.write_candidate()
        original_copy_check = candidate_validator._source_copy_check

        def mutate_source(*args, **kwargs):
            result = original_copy_check(*args, **kwargs)
            self.source.write_text("语料文件已发生变化，不能继续复用。\n", encoding="utf-8")
            return result

        with mock.patch.object(candidate_validator, "_source_copy_check", side_effect=mutate_source):
            with self.assertRaisesRegex(
                candidate_validator.CandidateError,
                "source_changed_during_validation:SOURCE-ONE",
            ):
                self.validate(candidate, queue=True)

        self.assertFalse((self.root / "queue" / "accepted" / "research-scope-001.json").exists())
        self.assertFalse((self.root / "queue" / "rejected" / "research-scope-001.json").exists())

    def test_post_publish_snapshot_recheck_rolls_back_visible_head(self) -> None:
        candidate = self.write_candidate()
        original_verify = candidate_validator._verify_catalog_bundle
        calls = 0

        def change_catalog_on_post_publish(bundle):
            nonlocal calls
            calls += 1
            if calls == 3:
                payload = json.loads(self.catalog.read_text(encoding="utf-8"))
                payload["purpose"] = "changed after queue publication"
                self.catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return original_verify(bundle)

        with mock.patch.object(
            candidate_validator,
            "_verify_catalog_bundle",
            side_effect=change_catalog_on_post_publish,
        ):
            with self.assertRaisesRegex(
                candidate_validator.CandidateError,
                "catalog_changed_during_validation",
            ):
                self.validate(candidate, queue=True)

        queue = self.root / "queue"
        self.assertFalse((queue / "accepted" / "research-scope-001.json").exists())
        self.assertFalse((queue / "accepted" / "research-scope-001.result.json").exists())
        self.assertFalse((queue / "review" / "research-scope-001.json").exists())
        self.assertFalse((queue / "review" / "research-scope-001.result.json").exists())
        self.assertFalse((queue / "rejected" / "research-scope-001.json").exists())

    def test_same_artifact_revalidation_preserves_first_history_attestation(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate, queue=True)
        history = self.root / "queue" / "history" / "research-scope-001"
        canonical = history / f"{first['candidate_sha256']}.result.json"
        first_history = canonical.read_bytes()

        self.source.unlink()
        second = self.validate(candidate, queue=True)

        self.assertEqual("REVIEW", second["status"])
        self.assertTrue(second["queue"]["same_candidate_artifact"])
        self.assertFalse(second["queue"]["same_evaluation_run"])
        self.assertFalse(second["queue"]["idempotent_rerun"])
        self.assertNotEqual(first["evaluation_sha256"], second["evaluation_sha256"])
        self.assertEqual(first_history, canonical.read_bytes())
        artifact_history = history / candidate_validator._history_hash_key(
            "a", first["candidate_sha256"]
        )
        runs = list((artifact_history / "runs").glob("*.result.json"))
        self.assertGreaterEqual(len(runs), 2)

    def test_queue_tree_never_stores_raw_reviewer_label(self) -> None:
        reviewer_id = "external-review-label-secret"
        candidate = self.warning_candidate(
            warning_review={
                "reviewer_kind": "HUMAN",
                "reviewer_id": reviewer_id,
            }
        )

        result = self.validate(candidate, queue=True)
        self.assertEqual("FAIL", result["status"])

        queue = self.root / "queue"
        for path in queue.rglob("*"):
            self.assertNotIn(reviewer_id, str(path.relative_to(queue)))
            if path.is_file():
                self.assertNotIn(reviewer_id.encode("utf-8"), path.read_bytes())
        stored = queue / "review" / "research-scope-001.json"
        if not stored.exists():
            stored = queue / "rejected" / "research-scope-001.json"
        payload = json.loads(stored.read_text(encoding="utf-8"))
        self.assertNotIn("reviewer_id", payload["warning_review"])
        self.assertNotIn("reviewer_id_sha256", json.dumps(payload, ensure_ascii=False))
        all_bytes = b"\n".join(
            path.read_bytes() for path in queue.rglob("*") if path.is_file()
        )
        self.assertNotIn(hashlib.sha256(reviewer_id.encode()).hexdigest().encode(), all_bytes)

    def test_conflicting_immutable_history_is_rejected(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate, queue=True)
        history_candidate = (
            self.root
            / "queue"
            / "history"
            / "research-scope-001"
            / f"{first['candidate_sha256']}.json"
        )
        history_candidate.write_text("{\"tampered\":true}\n", encoding="utf-8")

        with self.assertRaisesRegex(candidate_validator.CandidateError, "immutable_history_conflict"):
            self.validate(candidate, queue=True)

    def test_unsafe_candidate_id_is_quarantined_under_a_safe_storage_id(self) -> None:
        candidate = self.write_candidate(candidate_id="../../outside")
        result = self.validate(candidate, queue=True)

        self.assertEqual("FAIL", result["status"])
        self.assertIn("unsafe_candidate_id", result["contract_errors"])
        self.assertRegex(result["queue"]["storage_id"], r"^invalid-[0-9a-f]{20}$")
        self.assertFalse((self.root / "outside.json").exists())
        self.assertTrue(
            (self.root / "queue" / "rejected" / f"{result['queue']['storage_id']}.json").is_file()
        )

    def test_optional_allowed_root_rejects_candidate_paths_outside_it(self) -> None:
        outside = Path(tempfile.mkdtemp()) / "outside.md"
        outside.write_text("实验仅在当前条件下记录到峰值。\n", encoding="utf-8")
        candidate = self.write_candidate(before_path=str(outside), after_path=str(outside))

        result = candidate_validator.validate_candidate(
            candidate,
            catalog_path=self.catalog,
            allowed_root=self.root / "allowed",
        )

        self.assertEqual("FAIL", result["status"])
        self.assertIn("before_path_outside_allowed_root", result["contract_errors"])
        self.assertIn("after_path_outside_allowed_root", result["contract_errors"])

    def test_allowed_root_also_rejects_candidate_package_outside_it(self) -> None:
        result = candidate_validator.validate_candidate(
            self.write_candidate(),
            catalog_path=self.catalog,
            allowed_root=self.root / "allowed",
        )

        self.assertEqual("FAIL", result["status"])
        self.assertIn("candidate_path_outside_allowed_root", result["contract_errors"])

    def test_staging_failure_leaves_previous_queue_head_intact(self) -> None:
        candidate = self.write_candidate()
        first = self.validate(candidate, queue=True)
        review = self.root / "queue" / "review" / "research-scope-001.result.json"
        review_before = review.read_bytes()

        self.after.write_text("实验仅在当前条件下记录到峰值，并为后续研究提供线索。\n", encoding="utf-8")
        revised = self.write_candidate(
            supersedes_candidate_sha256=first["candidate_sha256"],
            anchors=[{
                "id": "scope-anchor",
                "before_text": "实验仅在当前条件下记录到峰值。",
                "after_text": "实验仅在当前条件下记录到峰值",
                "role": "scope",
            }],
        )
        real_atomic_write = candidate_validator._atomic_write
        call_count = 0

        def fail_third_write(path: Path, raw: bytes) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise OSError("injected staging failure")
            real_atomic_write(path, raw)

        with mock.patch.object(candidate_validator, "_atomic_write", side_effect=fail_third_write):
            with self.assertRaisesRegex(candidate_validator.CandidateError, "queue_publish_error:OSError"):
                self.validate(revised, queue=True)

        self.assertEqual(review_before, review.read_bytes())
        self.assertFalse((self.root / "queue" / "rejected" / "research-scope-001.result.json").exists())

    def test_copy_occurrence_growth_and_punctuation_insertion_are_introduced(self) -> None:
        self.source.write_text("甲乙丙丁戊己庚辛\n", encoding="utf-8")
        self.before.write_text("甲乙丙丁戊己庚辛只出现一次。\n", encoding="utf-8")
        self.after.write_text("甲乙丙丁戊己庚辛只出现一次，另一次甲乙丙丁戊己庚辛在这里。\n", encoding="utf-8")
        duplicate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "甲乙丙丁戊己庚辛只出现一次。",
                "after_text": "另一次甲乙丙丁戊己庚辛在这里。",
                "role": "scope",
            }]
        )
        duplicate_result = self.validate(duplicate)
        self.assertEqual("REVIEW", duplicate_result["source_copy_check"]["status"])
        self.assertGreater(duplicate_result["source_copy_check"]["introduced_match_count"], 0)

        self.before.write_text("当前结果只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("甲乙丙丁戊己庚，辛只用于范围说明。\n", encoding="utf-8")
        punctuated = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙丙丁戊己庚，辛只用于范围说明。",
                "role": "scope",
            }]
        )
        punctuated_result = self.validate(punctuated)
        self.assertEqual("REVIEW", punctuated_result["source_copy_check"]["status"])
        self.assertGreater(punctuated_result["source_copy_check"]["introduced_match_count"], 0)

    def test_copy_gate_joins_one_soft_physical_line_in_source_and_candidate(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["action_cards"][0]["source_refs"][0]["line_end"] = 2
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.source.write_text("甲乙丙丁\n戊己庚辛\n", encoding="utf-8")
        self.before.write_text("当前结果只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("甲乙丙丁戊己庚辛只用于范围说明。\n", encoding="utf-8")
        source_wrapped = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙丙丁戊己庚辛只用于范围说明。",
                "role": "scope",
            }]
        )

        source_wrapped_result = self.validate(source_wrapped)

        self.assertEqual("REVIEW", source_wrapped_result["source_copy_check"]["status"])
        self.assertGreater(source_wrapped_result["source_copy_check"]["introduced_match_count"], 0)
        self.assertEqual(
            "transparent",
            source_wrapped_result["source_copy_check"]["normalization"]["single_prose_physical_line_break"],
        )
        self.assertEqual(
            "hard_boundary",
            source_wrapped_result["source_copy_check"]["normalization"]["protected_span"],
        )
        self.assertEqual(
            "full_source_before_registered_line_slice",
            source_wrapped_result["source_copy_check"]["normalization"]["source_protection_scope"],
        )

        self.source.write_text("甲乙丙丁戊己庚辛\n", encoding="utf-8")
        catalog["action_cards"][0]["source_refs"][0]["line_end"] = 1
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.after.write_text("甲乙丙丁\n戊己庚辛只用于范围说明。\n", encoding="utf-8")
        candidate_wrapped = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙丙丁\n戊己庚辛只用于范围说明。",
                "role": "scope",
            }]
        )

        candidate_wrapped_result = self.validate(candidate_wrapped)

        self.assertEqual("REVIEW", candidate_wrapped_result["source_copy_check"]["status"])
        self.assertGreater(candidate_wrapped_result["source_copy_check"]["introduced_match_count"], 0)

    def test_copy_gate_normalizes_sparse_inline_spacing_and_punctuation(self) -> None:
        self.source.write_text("甲乙丙丁戊己庚辛\n", encoding="utf-8")
        self.before.write_text("当前结果只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("甲乙 丙丁，戊己；庚辛只用于范围说明。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙 丙丁，戊己；庚辛只用于范围说明。",
                "role": "scope",
            }]
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["source_copy_check"]["status"])
        self.assertGreater(result["source_copy_check"]["introduced_match_count"], 0)

        self.after.write_text("甲乙　丙丁\u00a0戊己\u200b庚辛只用于范围说明。\n", encoding="utf-8")
        unicode_spacing = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙　丙丁\u00a0戊己\u200b庚辛只用于范围说明。",
                "role": "scope",
            }]
        )

        unicode_spacing_result = self.validate(unicode_spacing)

        self.assertEqual("REVIEW", unicode_spacing_result["source_copy_check"]["status"])
        self.assertGreater(unicode_spacing_result["source_copy_check"]["introduced_match_count"], 0)

    def test_copy_gate_does_not_join_paragraph_structure_or_protected_spans(self) -> None:
        self.before.write_text("当前结果只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("甲乙丙丁戊己庚辛只用于范围说明。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙丙丁戊己庚辛只用于范围说明。",
                "role": "scope",
            }]
        )
        cases = {
            "blank-paragraph": ("甲乙丙丁\n\n戊己庚辛\n", 1, 3),
            "markdown-list": ("甲乙丙丁\n- 戊己庚辛\n", 1, 2),
            "markdown-tab-indented-code": ("甲乙丙丁\n\t戊己庚辛\n", 1, 2),
            "markdown-hard-line-break": ("甲乙丙丁  \n戊己庚辛\n", 1, 2),
            "inline-code": ("甲乙丙丁`x`戊己庚辛\n", 1, 1),
            "tex-math": ("甲乙丙丁\n\\begin{equation}x\\end{equation}\n戊己庚辛\n", 1, 3),
            "range-inside-markdown-fence": ("```text\n甲乙丙丁戊己庚辛\n```\n", 2, 2),
            "range-inside-tex-code": ("\\begin{lstlisting}\n甲乙丙丁戊己庚辛\n\\end{lstlisting}\n", 2, 2),
            "tex-inline-code": ("前文\\verb|甲乙丙丁戊己庚辛|后文\n", 1, 1),
        }

        for label, (source_text, line_start, line_end) in cases.items():
            with self.subTest(label=label):
                self.source.write_text(source_text, encoding="utf-8")
                catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
                catalog["action_cards"][0]["source_refs"][0]["line_start"] = line_start
                catalog["action_cards"][0]["source_refs"][0]["line_end"] = line_end
                self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

                result = self.validate(candidate)

                self.assertEqual("PASS", result["source_copy_check"]["status"])
                self.assertEqual(0, result["source_copy_check"]["introduced_match_count"])

    def test_introduced_protected_span_cannot_turn_copy_split_into_acceptance(self) -> None:
        self.source.write_text("甲乙丙丁戊己庚辛\n", encoding="utf-8")
        self.before.write_text("当前结果只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("甲乙丙丁`x`戊己庚辛只用于范围说明。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "当前结果只用于范围说明。",
                "after_text": "甲乙丙丁`x`戊己庚辛只用于范围说明。",
                "role": "scope",
            }]
        )

        result = self.validate(candidate)

        self.assertEqual("PASS", result["source_copy_check"]["status"])
        self.assertEqual("FAIL", result["status"])
        invariant_codes = {
            item["code"] for item in result["style_validation"]["invariants"]["errors"]
        }
        self.assertIn("PROTECTED_CODE_CHANGED", invariant_codes)

    def test_copy_gate_scans_unselected_registered_source_cards(self) -> None:
        source_two = self.root / "source-two.tex"
        source_two.write_text("未选择动作卡的来源泄漏短语甲乙丙丁戊己庚辛\n", encoding="utf-8")
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"].append({
            "id": "SOURCE-TWO",
            "source_tier": "A1",
            "origin_class": "UNKNOWN",
            "scene_scope": ["RESEARCH"],
            "role": "positive_action_reference",
            "path": str(source_two),
            "provenance": "test",
            "use_limit": "test",
        })
        catalog["action_cards"].append({
            "id": "RESEARCH-TWO-01",
            "scene": "RESEARCH",
            "kind": "positive_action",
            "action": "Use the second source.",
            "requires": ["scope"],
            "required_anchor_roles": ["scope"],
            "forbids": ["invented evidence"],
            "source_refs": [{"source_id": "SOURCE-TWO", "line_start": 1, "line_end": 1}],
        })
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.before.write_text("实验仅在当前条件下记录到峰值。\n", encoding="utf-8")
        self.after.write_text("未选择动作卡的来源泄漏短语甲乙丙丁戊己庚辛。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "实验仅在当前条件下记录到峰值。",
                "after_text": "未选择动作卡的来源泄漏短语甲乙丙丁戊己庚辛。",
                "role": "scope",
            }]
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertGreater(result["source_copy_check"]["introduced_match_count"], 0)

    def test_queue_publish_is_serialized_for_concurrent_idempotent_runs(self) -> None:
        candidate = self.write_candidate()
        queue = self.root / "concurrent-queue"

        def run_once(_: int) -> dict:
            return candidate_validator.validate_candidate(
                candidate,
                catalog_path=self.catalog,
                queue_dir=queue,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(run_once, range(24)))

        self.assertTrue(all(result["status"] == "REVIEW" for result in results))
        non_idempotent = [result for result in results if not result["queue"]["idempotent_rerun"]]
        self.assertLessEqual(len(non_idempotent), 1)
        heads = list((queue / "review").glob("research-scope-001*.json"))
        self.assertEqual(2, len(heads))

    def test_long_windows_queue_history_paths_publish_with_short_storage_keys(self) -> None:
        candidate_id = "c" * 128
        candidate = self.write_candidate(candidate_id=candidate_id)
        queue = self.root / ("queue-" + "x" * 80)

        result = candidate_validator.validate_candidate(
            candidate,
            catalog_path=self.catalog,
            queue_dir=queue,
        )

        self.assertEqual("REVIEW", result["status"])
        storage_id = result["queue"]["storage_id"]
        self.assertLessEqual(len(storage_id), 20)
        self.assertTrue((queue / "review" / f"{storage_id}.result.json").is_file())
        nested_files = [path for path in (queue / "history" / storage_id).rglob("*") if path.is_file()]
        self.assertTrue(nested_files)
        self.assertLess(max(len(str(path)) for path in nested_files), 260)

    def test_report_candidates_use_auto_style_scan_instead_of_general(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"][0]["scene_scope"] = ["REPORT"]
        card = catalog["action_cards"][0]
        card.update({"id": "REPORT-ONE-01", "scene": "REPORT"})
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.before.write_text("该报告记录当前样本。\n", encoding="utf-8")
        self.after.write_text("必须牢记该报告记录当前样本。\n", encoding="utf-8")
        candidate = self.write_candidate(
            scene="REPORT",
            action_cards=["REPORT-ONE-01"],
            action_evidence={"REPORT-ONE-01": ["scope-anchor"]},
            anchors=[{
                "id": "scope-anchor",
                "before_text": "该报告记录当前样本。",
                "after_text": "必须牢记该报告记录当前样本。",
                "role": "scope",
            }],
        )

        result = self.validate(candidate)

        self.assertEqual("AUTO", result["style_validation"]["scene"])
        self.assertEqual("REVIEW", result["style_validation"]["status"])

    def test_active_negative_guard_is_executed_even_when_not_selected(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"].append(
            {
                "id": "SOURCE-NEGATIVE",
                "source_tier": "A1",
                "origin_class": "MODEL_GENERATED",
                "scene_scope": ["ALL"],
                "role": "negative_template_reference",
                "path": str(self.source),
                "provenance": "test",
                "use_limit": "negative test only",
            }
        )
        catalog["action_cards"].append(
            {
                "id": "NEGATIVE-CHAIN-01",
                "scene": "ALL",
                "kind": "negative_guard",
                "action": "Reject a fixed chain.",
                "requires": ["template"],
                "required_anchor_roles": ["template"],
                "forbids": ["selection as positive action"],
                "detector": {
                    "minimum_groups": 2,
                    "pattern_groups": [
                        {"id": "a", "regex": "固定模板", "minimum_occurrences": 1},
                        {"id": "b", "regex": "必须牢记", "minimum_occurrences": 1},
                    ],
                },
                "source_refs": [{"source_id": "SOURCE-NEGATIVE", "line_start": 1, "line_end": 1}],
            }
        )
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        self.before.write_text("原句只用于范围说明。\n", encoding="utf-8")
        self.after.write_text("固定模板出现，必须牢记当前范围。\n", encoding="utf-8")
        candidate = self.write_candidate(
            anchors=[{
                "id": "scope-anchor",
                "before_text": "原句只用于范围说明。",
                "after_text": "固定模板出现，必须牢记当前范围。",
                "role": "scope",
            }]
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertIn("negative_guard:NEGATIVE-CHAIN-01", result["template_check"]["codes"])
        self.assertEqual("REVIEW", result["template_check"]["status"])
        self.assertIn("NEGATIVE-CHAIN-01", json.dumps(result, ensure_ascii=False))

    def test_active_structured_negative_guard_uses_raw_tex_and_keeps_evidence(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"].append(
            {
                "id": "SOURCE-STRUCTURED-NEGATIVE",
                "source_tier": "A1",
                "origin_class": "MODEL_GENERATED",
                "scene_scope": ["ALL"],
                "role": "negative_template_reference",
                "path": str(self.source),
                "provenance": "test",
                "use_limit": "negative test only",
            }
        )
        detector = {
            "type": "structured_repeated_list/v1",
            "block_role": {
                "heading_leaf_regex": "^(?:摘要|最短执行版|最后只记)$",
            },
            "thresholds": {
                "minimum_blocks": 3,
                "minimum_items_per_block": 3,
            },
            "shared_anchor": {
                "mode": "MAXIMAL_HAN_NGRAM",
                "minimum_han_chars": 4,
                "maximum_han_chars": 8,
                "minimum_block_coverage": 3,
            },
        }
        catalog["action_cards"].append(
            {
                "id": "NEGATIVE-STRUCTURED-TEX-01",
                "scene": "ALL",
                "kind": "negative_guard",
                "action": "Reject repeated recap lists.",
                "requires": ["template"],
                "required_anchor_roles": ["template"],
                "forbids": ["selection as a positive action"],
                "detector": detector,
                "source_refs": [
                    {
                        "source_id": "SOURCE-STRUCTURED-NEGATIVE",
                        "line_start": 1,
                        "line_end": 1,
                    }
                ],
            }
        )
        self.catalog.write_text(
            json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
        )
        before_tex = self.root / "before.tex"
        after_tex = self.root / "after.tex"
        anchor = "本文只记录当前范围。"
        before_tex.write_text(anchor + "\n", encoding="utf-8")
        after_tex.write_text(
            "\n".join(
                [
                    anchor,
                    r"\section*[HEADING_OPTION_SECRET]{摘要 $HEADING_MATH_SECRET$}",
                    r"\begin{enumerate}",
                    r"\item[ITEM_LABEL_SECRET] 共同校验步骤核对甲条件",
                    r"\item 共同校验步骤复算甲数据 \secretcommand{COMMAND_ARG_SECRET}",
                    r"\item 共同校验步骤记录甲结论",
                    r"\end{enumerate}",
                    r"\subsection*{最短执行版}",
                    r"\begin{enumerate}",
                    r"\item 共同校验步骤核对乙条件",
                    r"\item 共同校验步骤复算乙数据",
                    r"\item 共同校验步骤记录乙结论",
                    r"\end{enumerate}",
                    r"\subsection*{最后只记}",
                    r"\begin{enumerate}",
                    r"\item 共同校验步骤核对丙条件",
                    r"\item 共同校验步骤复算丙数据",
                    r"\item 共同校验步骤记录丙结论",
                    r"\end{enumerate}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        candidate = self.write_candidate(
            before_path=str(before_tex),
            after_path=str(after_tex),
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": anchor,
                    "after_text": anchor,
                    "role": "scope",
                }
            ],
        )

        result = self.validate(candidate)

        template = result["template_check"]
        self.assertEqual("REVIEW", template["status"])
        self.assertIn(
            "negative_guard:NEGATIVE-STRUCTURED-TEX-01", template["codes"]
        )
        hit = next(
            item
            for item in template["negative_guard_hits"]
            if item["card_id"] == "NEGATIVE-STRUCTURED-TEX-01"
        )
        self.assertEqual("structured_repeated_list/v1", hit["detector_type"])
        self.assertRegex(hit["definition_sha256"], r"^[0-9a-f]{64}$")
        evidence = hit["structured_evidence"]
        self.assertEqual(3, evidence["qualified_block_count"])
        self.assertEqual(3, len(evidence["qualified_blocks"]))
        self.assertTrue(evidence["shared_anchors"])
        self.assertTrue(all(item["format"] == "tex" for item in evidence["qualified_blocks"]))
        rendered_evidence = json.dumps(evidence, ensure_ascii=False)
        for protected_payload in (
            "HEADING_OPTION_SECRET",
            "HEADING_MATH_SECRET",
            "ITEM_LABEL_SECRET",
            "COMMAND_ARG_SECRET",
        ):
            self.assertNotIn(protected_payload, rendered_evidence)

    def test_regex_negative_guard_uses_protected_aware_author_view(self) -> None:
        after_tex = self.root / "protected.tex"
        after_tex.write_text(
            "普通正文必须牢记当前范围。\\verb|固定模板|\n",
            encoding="utf-8",
        )
        guard = {
            "id": "NEGATIVE-PROTECTED-REGEX-01",
            "scene": "ALL",
            "status": "AVAILABLE",
            "detector": {
                "type": "regex_groups/v1",
                "minimum_groups": 2,
                "pattern_groups": [
                    {"id": "visible", "regex": "必须牢记", "minimum_occurrences": 1},
                    {"id": "protected", "regex": "固定模板", "minimum_occurrences": 1},
                ],
            },
        }

        result = candidate_validator._template_check(after_tex, [guard])

        self.assertEqual("PASS", result["status"])
        self.assertEqual([], result["negative_guard_hits"])

    def test_unknown_and_broken_detectors_review_without_rereading_after(self) -> None:
        class CountingAfter:
            suffix = ".md"

            def __init__(self, text: str) -> None:
                self.text = text
                self.read_count = 0

            def read_text(self, *, encoding: str) -> str:
                self.read_count += 1
                return self.text

        after = CountingAfter("普通候选正文。\n")
        guards = [
            {
                "id": "NEGATIVE-UNKNOWN-01",
                "scene": "ALL",
                "status": "AVAILABLE",
                "detector": {"type": "unknown_detector/v9"},
            },
            {
                "id": "NEGATIVE-BROKEN-01",
                "scene": "ALL",
                "status": "AVAILABLE",
                "detector": {"type": "structured_repeated_list/v1"},
            },
        ]

        result = candidate_validator._template_check(after, guards)

        self.assertEqual(1, after.read_count)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(
            {
                "negative_guard_detector_review:NEGATIVE-UNKNOWN-01",
                "negative_guard_detector_review:NEGATIVE-BROKEN-01",
            },
            set(result["codes"]),
        )
        self.assertEqual(2, len(result["negative_guard_hits"]))
        for hit in result["negative_guard_hits"]:
            self.assertEqual("REVIEW", hit["evaluation_status"])
            self.assertEqual("DETECTOR_EVALUATION_REVIEW", hit["review_code"])
            self.assertRegex(hit["definition_sha256"], r"^[0-9a-f]{64}$")

    def test_malformed_catalog_detector_is_end_to_end_review(self) -> None:
        guard_id = "NEGATIVE-BROKEN-01"
        self.configure_negative_guard({"type": "structured_repeated_list/v1"})
        candidate = self.write_candidate()

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual(
            [guard_id],
            [item["id"] for item in result["action_contract"]["active_negative_guards"]],
        )
        self.assertIn(
            f"negative_guard_detector_review:{guard_id}",
            result["template_check"]["codes"],
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = candidate_validator.main(
                [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
            )
        self.assertEqual(2, exit_code)
        self.assertEqual("REVIEW", json.loads(stdout.getvalue())["status"])
        self.assertEqual("", stderr.getvalue())

    def test_missing_and_malformed_catalog_are_hard_failures(self) -> None:
        candidate = self.write_candidate()
        cases = {
            "missing": self.root / "missing-catalog.json",
            "malformed": self.root / "malformed-catalog.json",
        }
        cases["malformed"].write_text("{not-json", encoding="utf-8")

        for label, catalog in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(candidate_validator.CandidateError):
                    candidate_validator.validate_candidate(
                        candidate,
                        catalog_path=catalog,
                    )
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = candidate_validator.main(
                        [str(candidate), "--catalog", str(catalog), "--format", "json"]
                    )
                self.assertEqual(1, exit_code)
                self.assertEqual("", stdout.getvalue())

    def test_detector_contract_error_is_review_for_api_and_cli(self) -> None:
        self.configure_negative_guard(
            {
                "minimum_groups": 1,
                "pattern_groups": [
                    {"id": "shell", "regex": "固定句壳", "minimum_occurrences": 1}
                ],
            },
            guard_id="NEGATIVE-CONTRACT-01",
        )
        candidate = self.write_candidate()

        with mock.patch.object(
            candidate_validator.repetition_guards,
            "evaluate_detector_snapshot",
            side_effect=candidate_validator.repetition_guards.DetectorEvaluationReview(
                "sensitive body"
            ),
        ):
            result = self.validate(candidate)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = candidate_validator.main(
                    [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
                )

        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual(2, exit_code)
        self.assertEqual("REVIEW", json.loads(stdout.getvalue())["status"])
        self.assertNotIn("sensitive body", json.dumps(result, ensure_ascii=False))
        self.assertEqual("", stderr.getvalue())

    def test_detector_runtime_error_is_redacted_hard_failure_for_api_and_cli(self) -> None:
        guard_id = "NEGATIVE-RUNTIME-01"
        self.configure_negative_guard(
            {
                "minimum_groups": 1,
                "pattern_groups": [
                    {"id": "shell", "regex": "固定句壳", "minimum_occurrences": 1}
                ],
            },
            guard_id=guard_id,
        )
        candidate = self.write_candidate()

        with mock.patch.object(
            candidate_validator.repetition_guards,
            "evaluate_detector_snapshot",
            side_effect=RuntimeError("sensitive body"),
        ):
            with self.assertRaisesRegex(
                candidate_validator.CandidateError,
                f"negative_guard_evaluation_runtime_error:{guard_id}:RuntimeError",
            ):
                self.validate(candidate)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = candidate_validator.main(
                    [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
                )

        rendered_error = stderr.getvalue()
        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn(
            f"negative_guard_evaluation_runtime_error:{guard_id}:RuntimeError",
            rendered_error,
        )
        self.assertNotIn("sensitive body", rendered_error)
        self.assertNotIn("Traceback", rendered_error)

    def test_malformed_regex_detector_evidence_fails_closed_for_api_and_cli(self) -> None:
        guard_id = "NEGATIVE-EVIDENCE-01"
        self.configure_negative_guard(
            {
                "type": "regex_groups/v1",
                "minimum_groups": 1,
                "pattern_groups": [
                    {"id": "shell", "regex": "fixed shell", "minimum_occurrences": 1}
                ],
            },
            guard_id=guard_id,
        )
        candidate = self.write_candidate()
        cases = {
            "empty": {},
            "none": None,
            "triggered_not_bool": {"triggered": "SENSITIVE_EVIDENCE_TRIGGER"},
            "matched_units_not_list": {
                "triggered": False,
                "group_results": [],
                "matched_units": "SENSITIVE_EVIDENCE_UNITS",
            },
            "bool_occurrences": {
                "triggered": True,
                "group_results": [
                    {
                        "id": "shell",
                        "occurrences": True,
                        "minimum_occurrences": 1,
                        "units": [],
                        "triggered": True,
                    }
                ],
                "matched_units": [],
            },
        }
        expected = (
            f"negative_guard_evaluation_runtime_error:{guard_id}:InvalidEvidence"
        )

        for label, evidence in cases.items():
            with self.subTest(label=label), mock.patch.object(
                candidate_validator.repetition_guards,
                "evaluate_detector_snapshot",
                return_value=evidence,
            ):
                with self.assertRaises(candidate_validator.CandidateError) as raised:
                    self.validate(candidate)
                self.assertEqual(expected, str(raised.exception))

                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = candidate_validator.main(
                        [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
                    )

                self.assertEqual(1, exit_code)
                self.assert_redacted_cli_failure(
                    stdout,
                    stderr,
                    expected=expected,
                    sensitive_marker="SENSITIVE_EVIDENCE",
                )

    def test_malformed_structured_detector_evidence_fails_closed(self) -> None:
        guard_id = "NEGATIVE-STRUCTURED-EVIDENCE-01"
        self.configure_negative_guard(
            {
                "type": "structured_repeated_list/v1",
                "block_role": {"heading_leaf_regex": "^summary$"},
                "thresholds": {
                    "minimum_blocks": 3,
                    "minimum_items_per_block": 3,
                },
                "shared_anchor": {
                    "mode": "MAXIMAL_HAN_NGRAM",
                    "minimum_han_chars": 4,
                    "maximum_han_chars": 8,
                    "minimum_block_coverage": 3,
                },
            },
            guard_id=guard_id,
        )
        candidate = self.write_candidate()
        evidence = {
            "triggered": False,
            "qualified_block_count": False,
            "qualified_blocks": [],
            "shared_anchors": [],
        }
        expected = (
            f"negative_guard_evaluation_runtime_error:{guard_id}:InvalidEvidence"
        )

        with mock.patch.object(
            candidate_validator.repetition_guards,
            "evaluate_detector_snapshot",
            return_value=evidence,
        ):
            with self.assertRaises(candidate_validator.CandidateError) as raised:
                self.validate(candidate)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = candidate_validator.main(
                    [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
                )

        self.assertEqual(expected, str(raised.exception))
        self.assertEqual(1, exit_code)
        self.assert_redacted_cli_failure(
            stdout,
            stderr,
            expected=expected,
            sensitive_marker="SENSITIVE_STRUCTURED_EVIDENCE",
        )

    def test_internal_stage_errors_are_redacted_for_api_and_cli(self) -> None:
        candidate = self.write_candidate()
        cases = (
            (
                candidate_validator.action_profile,
                "build_action_profile",
                "action_profile_runtime_error:RuntimeError",
            ),
            (
                candidate_validator,
                "_source_copy_check",
                "source_copy_check_runtime_error:RuntimeError",
            ),
        )

        for owner, attribute, expected in cases:
            marker = f"SENSITIVE_{attribute.upper()}"
            with self.subTest(stage=attribute), mock.patch.object(
                owner,
                attribute,
                side_effect=RuntimeError(marker),
            ):
                with self.assertRaises(candidate_validator.CandidateError) as raised:
                    self.validate(candidate)
                self.assertEqual(expected, str(raised.exception))
                self.assertNotIn(marker, str(raised.exception))
                self.assertNotIn(str(self.root.resolve()), str(raised.exception))

                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = candidate_validator.main(
                        [str(candidate), "--catalog", str(self.catalog), "--format", "json"]
                    )

                self.assertEqual(1, exit_code)
                self.assert_redacted_cli_failure(
                    stdout,
                    stderr,
                    expected=expected,
                    sensitive_marker=marker,
                )

    def test_queue_io_error_is_redacted_for_api_and_cli(self) -> None:
        candidate = self.write_candidate()
        queue_dir = self.root / "queue-redaction"
        marker = "SENSITIVE_QUEUE_BODY"
        expected = "queue_publish_error:OSError"

        with mock.patch.object(
            candidate_validator,
            "_atomic_write",
            side_effect=OSError(marker),
        ):
            with self.assertRaises(candidate_validator.CandidateError) as raised:
                candidate_validator.validate_candidate(
                    candidate,
                    catalog_path=self.catalog,
                    queue_dir=queue_dir,
                )
            self.assertEqual(expected, str(raised.exception))

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = candidate_validator.main(
                    [
                        str(candidate),
                        "--catalog",
                        str(self.catalog),
                        "--queue-dir",
                        str(queue_dir),
                        "--format",
                        "json",
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assert_redacted_cli_failure(
            stdout,
            stderr,
            expected=expected,
            sensitive_marker=marker,
        )

    def test_main_redacts_unexpected_exception_and_does_not_catch_base_exception(self) -> None:
        candidate = self.write_candidate()
        marker = "SENSITIVE_CLI_BODY"
        expected = "candidate_cli_runtime_error:RuntimeError"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(
            candidate_validator,
            "validate_candidate",
            side_effect=RuntimeError(marker),
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = candidate_validator.main([str(candidate)])

        self.assertEqual(1, exit_code)
        self.assert_redacted_cli_failure(
            stdout,
            stderr,
            expected=expected,
            sensitive_marker=marker,
        )

        with mock.patch.object(
            candidate_validator,
            "validate_candidate",
            side_effect=KeyboardInterrupt,
        ), self.assertRaises(KeyboardInterrupt):
            candidate_validator.main([str(candidate)])

    def test_general_candidate_can_declare_no_corpus_support_without_fabricating_a_card(self) -> None:
        candidate = self.write_candidate(
            scene="GENERAL",
            corpus_action_support="NONE",
            action_cards=[],
            action_evidence={},
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertIn("style_validator_review", result["review_reasons"])
        self.assertEqual("NONE", result["action_contract"]["corpus_action_support"])
        self.assertEqual(
            "CORPUS_INSUFFICIENT",
            result["action_contract"]["scene_corpus_status"]["status"],
        )

        now_allowed = self.write_candidate(
            scene="RESEARCH",
            corpus_action_support="NONE",
            action_cards=[],
            action_evidence={},
        )
        allowed_result = self.validate(now_allowed)
        self.assertEqual("REVIEW", allowed_result["status"])
        self.assertIn("style_validator_review", allowed_result["review_reasons"])
        self.assertEqual(
            "SUPPORTED_PROVISIONAL",
            allowed_result["action_contract"]["scene_corpus_status"]["status"],
        )

    def test_research_candidate_can_declare_none_after_provenance_removes_positive_cards(self) -> None:
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"][0].update(
            {
                "origin_class": "MODEL_GENERATED",
                "role": "negative_template_reference",
            }
        )
        catalog["action_cards"][0].update(
            {
                "kind": "negative_guard",
                "action": "Reject a repeated meta-question shell.",
                "required_anchor_roles": ["template"],
                "detector": {
                    "minimum_groups": 1,
                    "pattern_groups": [
                        {
                            "id": "meta_question",
                            "regex": "真正要回答的不是.{1,40}而是",
                            "minimum_occurrences": 2,
                        }
                    ],
                },
            }
        )
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        candidate = self.write_candidate(
            corpus_action_support="NONE",
            action_cards=[],
            action_evidence={},
        )

        result = self.validate(candidate)

        self.assertEqual("REVIEW", result["status"])
        self.assertIn("style_validator_review", result["review_reasons"])
        self.assertEqual(
            "CORPUS_INSUFFICIENT",
            result["action_contract"]["scene_corpus_status"]["status"],
        )

    def test_action_evidence_must_cover_each_card_with_declared_anchor_ids(self) -> None:
        candidate = self.write_candidate(
            corpus_action_support="ACTION_CARDS",
            action_cards=["RESEARCH-ONE-01"],
            action_evidence={"RESEARCH-ONE-01": ["missing-anchor"]},
        )
        result = self.validate(candidate)

        self.assertEqual("FAIL", result["status"])
        self.assertIn("action_evidence_unknown_anchor:RESEARCH-ONE-01:missing-anchor", result["contract_errors"])

    def test_anchor_text_must_identify_one_location_in_each_version(self) -> None:
        self.after.write_text(
            "实验仅在当前条件下记录到峰值。实验仅在当前条件下记录到峰值。\n",
            encoding="utf-8",
        )
        result = self.validate(self.write_candidate())

        self.assertEqual("FAIL", result["status"])
        self.assertIn("anchor_after_ambiguous:scope-anchor", result["contract_errors"])

    def test_action_card_requires_declared_anchor_roles_and_negative_guards_are_not_selectable(self) -> None:
        wrong_role = self.write_candidate(
            corpus_action_support="ACTION_CARDS",
            action_cards=["RESEARCH-ONE-01"],
            action_evidence={"RESEARCH-ONE-01": ["scope-anchor"]},
            anchors=[
                {
                    "id": "scope-anchor",
                    "before_text": "实验仅在当前条件下记录到峰值。",
                    "after_text": "实验仅在当前条件下记录到峰值。",
                    "role": "claim",
                }
            ]
        )
        result = self.validate(wrong_role)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("missing_anchor_role:RESEARCH-ONE-01:scope", result["contract_errors"])

        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["sources"].append(
            {
                "id": "SOURCE-NEGATIVE",
                "source_tier": "A1",
                "origin_class": "UNKNOWN",
                "scene_scope": ["ALL"],
                "role": "negative_template_reference",
                "path": str(self.source),
                "provenance": "test",
                "use_limit": "negative test only",
            }
        )
        catalog["action_cards"].append(
            {
                "id": "NEGATIVE-ONE-01",
                "scene": "ALL",
                "kind": "negative_guard",
                "action": "Reject a fixed ending.",
                "requires": ["template"],
                "required_anchor_roles": ["template"],
                "forbids": ["selection as a positive action"],
                "detector": {
                    "minimum_groups": 1,
                    "pattern_groups": [{"id": "template", "regex": "固定", "minimum_occurrences": 1}],
                },
                "source_refs": [{"source_id": "SOURCE-NEGATIVE", "line_start": 1, "line_end": 1}],
            }
        )
        self.catalog.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        negative = self.write_candidate(
            corpus_action_support="ACTION_CARDS",
            action_cards=["NEGATIVE-ONE-01"],
            action_evidence={"NEGATIVE-ONE-01": ["scope-anchor"]},
        )
        result = self.validate(negative)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("negative_guard_not_selectable:NEGATIVE-ONE-01", result["contract_errors"])


if __name__ == "__main__":
    unittest.main()
