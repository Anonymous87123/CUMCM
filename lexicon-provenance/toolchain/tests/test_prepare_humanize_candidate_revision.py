import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "prepare_humanize_candidate_revision.py"
SPEC = importlib.util.spec_from_file_location("prepare_humanize_candidate_revision", SCRIPT)
revision = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(revision)


class CandidateRevisionPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.before = self.root / "before.md"
        self.after_one = self.root / "after-one.md"
        self.after_two = self.root / "after-two.md"
        self.before.write_text("当前样本只支持局部比较。\n", encoding="utf-8")
        self.after_one.write_text("当前样本仅支持局部比较。\n", encoding="utf-8")
        self.after_two.write_text("现有样本仅支持局部比较。\n", encoding="utf-8")
        self.candidate = self.root / "candidate.json"
        self.candidate.write_text(
            json.dumps(
                {
                    "candidate_id": "general-001",
                    "scene": "GENERAL",
                    "before_path": str(self.before),
                    "after_path": str(self.after_one),
                    "action_cards": ["GENERAL-ONE-01"],
                    "action_evidence": {"GENERAL-ONE-01": ["scope"]},
                    "anchors": [
                        {
                            "id": "scope",
                            "before_text": "当前样本只支持局部比较。",
                            "after_text": "当前样本仅支持局部比较。",
                            "role": "scope",
                        }
                    ],
                    "keep_reasons": {},
                    "accepted_warnings": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_changed_anchor_requires_explicit_update_and_must_exist_once(self) -> None:
        output = self.root / "revision.json"
        with self.assertRaisesRegex(revision.RevisionError, "anchor_update_required:scope"):
            revision.prepare_revision(self.candidate, self.after_two, output)

        with self.assertRaisesRegex(revision.RevisionError, "anchor_after_missing:scope"):
            revision.prepare_revision(
                self.candidate,
                self.after_two,
                output,
                anchor_updates={"scope": "不存在的范围句"},
            )

        payload = revision.prepare_revision(
            self.candidate,
            self.after_two,
            output,
            anchor_updates={"scope": "现有样本仅支持局部比较。"},
        )
        self.assertEqual(str(self.after_two.resolve()), payload["after_path"])
        self.assertEqual("现有样本仅支持局部比较。", payload["anchors"][0]["after_text"])
        self.assertTrue(output.is_file())

    def test_supersedes_result_is_bound_and_unknown_anchor_is_rejected(self) -> None:
        previous_hash = "a" * 64
        previous_result = self.root / "previous.result.json"
        previous_result.write_text(
            json.dumps({"candidate_sha256": previous_hash}),
            encoding="utf-8",
        )
        output = self.root / "revision.json"
        with self.assertRaisesRegex(revision.RevisionError, "unknown_anchor:missing"):
            revision.prepare_revision(
                self.candidate,
                self.after_two,
                output,
                anchor_updates={"missing": "现有样本仅支持局部比较。", "scope": "现有样本仅支持局部比较。"},
                supersedes_result_path=previous_result,
            )

        payload = revision.prepare_revision(
            self.candidate,
            self.after_two,
            output,
            anchor_updates={"scope": "现有样本仅支持局部比较。"},
            supersedes_result_path=previous_result,
        )
        self.assertEqual(previous_hash, payload["supersedes_candidate_sha256"])

    def test_old_warning_proposal_and_review_state_cannot_cross_revision(self) -> None:
        stale_fields = {
            "accepted_warnings": {
                "SPEECH_ACT_MODALITY_SCOPE_CHANGED": "旧版人工接受记录",
            },
            "warning_resolutions": {
                "b" * 64: "旧候选中的人工处理建议",
            },
            "warning_review_request_sha256": "c" * 64,
            "warning_review": {
                "reviewer_kind": "HUMAN",
                "reviewer_id": "old-reviewer-label",
            },
        }
        original = json.loads(self.candidate.read_text(encoding="utf-8"))
        original.update(stale_fields)
        self.candidate.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

        same_body_output = self.root / "same-body-revision.json"
        same_body = revision.prepare_revision(
            self.candidate,
            self.after_one,
            same_body_output,
        )
        changed_body_output = self.root / "changed-body-revision.json"
        changed_body = revision.prepare_revision(
            self.candidate,
            self.after_two,
            changed_body_output,
            anchor_updates={"scope": "现有样本仅支持局部比较。"},
        )

        for payload, output in (
            (same_body, same_body_output),
            (changed_body, changed_body_output),
        ):
            stored = json.loads(output.read_text(encoding="utf-8"))
            for field in stale_fields:
                self.assertNotIn(field, payload)
                self.assertNotIn(field, stored)
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("old-reviewer-label", serialized)
            self.assertNotIn("旧候选中的人工处理建议", serialized)

    def test_output_is_atomic_and_existing_output_is_not_silently_overwritten(self) -> None:
        output = self.root / "revision.json"
        output.write_text("user content", encoding="utf-8")
        with self.assertRaisesRegex(revision.RevisionError, "output_exists"):
            revision.prepare_revision(
                self.candidate,
                self.after_two,
                output,
                anchor_updates={"scope": "现有样本仅支持局部比较。"},
            )
        self.assertEqual("user content", output.read_text(encoding="utf-8"))

    def test_candidate_and_supersedes_result_reject_duplicate_json_keys(self) -> None:
        raw = self.candidate.read_text(encoding="utf-8")
        self.candidate.write_text(
            '{"candidate_id":"shadow",' + raw.lstrip()[1:],
            encoding="utf-8",
        )
        with self.assertRaisesRegex(revision.RevisionError, "duplicate_json_key:candidate_id"):
            revision.prepare_revision(self.candidate, self.after_one, self.root / "revision.json")

        self.candidate.write_text(raw, encoding="utf-8")
        previous = self.root / "previous.result.json"
        previous.write_text(
            '{"candidate_sha256":"' + "a" * 64 + '","candidate_sha256":"' + "b" * 64 + '"}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(revision.RevisionError, "duplicate_json_key:candidate_sha256"):
            revision.prepare_revision(
                self.candidate,
                self.after_one,
                self.root / "revision.json",
                supersedes_result_path=previous,
            )

    def test_candidate_and_supersedes_result_reject_non_finite_json_numbers(self) -> None:
        raw = self.candidate.read_text(encoding="utf-8")
        self.candidate.write_text(
            raw.replace('"candidate_id": "general-001"', '"candidate_id": NaN'),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(revision.RevisionError, "non_finite_json_number:NaN"):
            revision.prepare_revision(self.candidate, self.after_one, self.root / "revision.json")

        self.candidate.write_text(raw, encoding="utf-8")
        previous = self.root / "previous.result.json"
        previous.write_text(
            '{"candidate_sha256":"' + "a" * 64 + '","poison":Infinity}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(revision.RevisionError, "non_finite_json_number:Infinity"):
            revision.prepare_revision(
                self.candidate,
                self.after_one,
                self.root / "revision.json",
                supersedes_result_path=previous,
            )


if __name__ == "__main__":
    unittest.main()
