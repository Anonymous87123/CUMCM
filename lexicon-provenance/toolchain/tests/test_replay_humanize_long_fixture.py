import json
import os
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
SCRIPT = SKILL / "scripts" / "replay_humanize_long_fixture.py"
SOURCE = (
    SKILL
    / "references"
    / "generation-qualification-fixtures"
    / "v1"
    / "mode-02-input.md"
)


class ReplayHumanizeLongFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / "input.md"
        self.output = self.root / "output.md"
        raw = SOURCE.read_bytes()
        self.input.write_bytes(raw)
        self.output.write_bytes(raw)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_helper(self, scenario: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(SCRIPT),
                str(self.input),
                str(self.output),
                "--scenario",
                scenario,
                "--format",
                "json",
            ],
            text=True,
            encoding="utf-8",
            errors="strict",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )

    def test_long_20_and_21_replay_current_finalizer_review_contract(self) -> None:
        for scenario in ("LONG-20", "LONG-21"):
            with self.subTest(scenario=scenario):
                result = self.run_helper(scenario)
                self.assertEqual(2, result.returncode, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual("REVIEW", payload["status"])
                self.assertEqual("REVIEW", payload["delivery_gate_status"])
                self.assertEqual(2, payload["exit_code"])
                self.assertEqual(2, payload["delivery_gate_exit_code"])
                self.assertEqual("NOT_EVALUATED", payload["academic_correctness"])
                self.assertEqual("PASS", payload["candidate_assembly_status"])
                self.assertEqual("REVIEW_CANDIDATE", payload["publish_state"])
                self.assertEqual("PASS", payload["structural_plan_status"])
                self.assertEqual(
                    "NOT_EVALUATED", payload["structural_semantic_mapping"]
                )
                self.assertEqual(
                    "PENDING_EXTERNAL_REVIEW",
                    payload["structural_semantic_review_status"],
                )
                self.assertTrue(payload["rendered_review_exists"])
                self.assertFalse(payload["rendered_exists"])
                self.assertEqual(
                    "humanize-structural-semantic-review-request/v1",
                    payload["structural_review_request_schema"],
                )
                self.assertEqual(
                    "PASS", payload["structural_review_request_binding_status"]
                )
                self.assertFalse(payload["local_clearance_supported"])
                self.assertEqual(
                    self.input.read_bytes(), self.output.read_bytes()
                )

    def test_all_registered_scenarios_are_machine_executable(self) -> None:
        for scenario in (
            "LONG-20",
            "LONG-21",
            "LONG-22",
            "LONG-23",
            "LONG-24",
            "LONG-25",
            "LONG-26",
            "LONG-27",
        ):
            with self.subTest(scenario=scenario):
                result = self.run_helper(scenario)
                self.assertIn(result.returncode, {0, 1, 2}, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, payload["exit_code"])
                self.assertEqual(payload["status"], payload["delivery_gate_status"])
                self.assertEqual(
                    "NOT_EVALUATED", payload["academic_correctness"]
                )
                self.assertEqual("PASS", payload["evidence_binding_status"])

    def test_long_25_replays_candidate_disposition_closure(self) -> None:
        result = self.run_helper("LONG-25")
        self.assertEqual(2, result.returncode, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual("REVIEW", payload["candidate_assembly_status"])
        self.assertEqual("PARTIAL", payload["publish_state"])
        self.assertEqual(1, payload["structural_transaction_candidates_total"])
        self.assertEqual(0, payload["structural_transaction_candidates_executed"])
        self.assertEqual(0, payload["structural_transaction_candidates_declined"])
        self.assertEqual(1, payload["structural_transaction_candidates_pending"])
        self.assertEqual(
            "REVIEW", payload["structural_transaction_candidate_coverage_status"]
        )
        self.assertFalse(payload["structural_transaction_scope_complete"])
        self.assertTrue(payload["candidate_no_change_does_not_dispose"])
        self.assertEqual(
            "humanize-structural-transaction-decline/v1",
            payload["decline_schema"],
        )
        self.assertEqual("PASS", payload["decline_closure_status"])
        self.assertEqual("PASS", payload["decline_candidate_coverage_status"])
        self.assertEqual("REVIEW", payload["decline_delivery_gate_status"])
        self.assertEqual("REVIEW_CANDIDATE", payload["decline_publish_state"])
        self.assertEqual(
            "PASS",
            payload["decline_paired_quality_review_request_coverage_status"],
        )
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW",
            payload["decline_paired_quality_gate_status"],
        )
        self.assertFalse(payload["decline_humanize_completion_claim_allowed"])
        self.assertEqual("DECLINED", payload["decline_disposition"])
        self.assertEqual("PASS", payload["decline_evidence_member_coverage"])
        self.assertTrue(payload["execution_decline_conflict_rejected"])
        self.assertTrue(payload["stale_decline_rejected"])
        self.assertFalse(payload["rendered_exists"])
        self.assertTrue(payload["rendered_partial_exists"])
        self.assertFalse(payload["decline_rendered_exists"])
        self.assertTrue(payload["decline_rendered_review_exists"])

    def test_long_26_replays_paired_quality_review_candidate(self) -> None:
        result = self.run_helper("LONG-26")
        self.assertEqual(2, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("PASS", payload["candidate_assembly_status"])
        self.assertEqual("REVIEW_CANDIDATE", payload["publish_state"])
        self.assertEqual(
            "humanize-paired-quality-review-request/v1",
            payload["paired_quality_review_request_schema"],
        )
        self.assertEqual(
            "PASS", payload["paired_quality_review_request_binding_status"]
        )
        self.assertEqual(
            "PASS", payload["paired_quality_review_request_coverage_status"]
        )
        self.assertEqual(
            "PENDING_EXTERNAL_REVIEW", payload["paired_quality_gate_status"]
        )
        self.assertEqual(payload["paired_quality_units_total"], payload["paired_quality_units_pending"])
        self.assertEqual(0, payload["paired_quality_units_missing"])
        self.assertEqual("PASS", payload["paired_quality_no_change_request_status"])
        self.assertFalse(payload["paired_quality_clearance_granted"])
        self.assertFalse(payload["humanize_completion_claim_allowed"])
        self.assertFalse(payload["rendered_exists"])
        self.assertTrue(payload["rendered_review_exists"])

    def test_long_27_rejects_second_pass_as_quality_clearance(self) -> None:
        result = self.run_helper("LONG-27")
        self.assertEqual(2, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["second_pass_seed_rejected"])
        self.assertEqual("FAIL", payload["humanize_second_pass_convergence"])
        self.assertEqual("INVALID_EVIDENCE", payload["second_pass_stability_status"])
        self.assertFalse(payload["second_pass_quality_clearance_granted"])
        self.assertFalse(payload["paired_quality_clearance_granted"])
        self.assertFalse(payload["humanize_completion_claim_allowed"])

    def test_transaction_scenarios_do_not_claim_unexecuted_gates(self) -> None:
        long_22 = json.loads(self.run_helper("LONG-22").stdout)
        self.assertTrue(long_22["structural_transaction_conflict_rejected"])
        self.assertEqual(
            "NOT_RUN", long_22["structural_transaction_rollback_status"]
        )
        self.assertEqual("NOT_RUN", long_22["transaction_replay_status"])
        self.assertEqual("NOT_RUN", long_22["second_pass_seed_rejected"])
        self.assertEqual(
            "NOT_RUN", long_22["generator_projection_control_surface"]
        )

        long_23 = json.loads(self.run_helper("LONG-23").stdout)
        self.assertEqual(
            "NOT_RUN", long_23["structural_transaction_conflict_rejected"]
        )
        self.assertEqual(
            "PASS", long_23["structural_transaction_rollback_status"]
        )
        self.assertEqual("NOT_RUN", long_23["transaction_replay_status"])
        self.assertEqual(
            "humanize-structural-transaction-review-request/v2",
            long_23["transaction_review_request_schema"],
        )
        self.assertEqual("PASS", long_23["rewrite_intent_coverage_status"])
        self.assertEqual(0, long_23["rewrite_intent_units_missing"])

        long_24 = json.loads(self.run_helper("LONG-24").stdout)
        self.assertEqual(
            "NOT_RUN", long_24["structural_transaction_conflict_rejected"]
        )
        self.assertEqual(
            "NOT_RUN", long_24["structural_transaction_rollback_status"]
        )
        self.assertEqual("PASS", long_24["transaction_replay_status"])
        self.assertTrue(long_24["second_pass_seed_rejected"])
        projection_execution = long_24["generator_projection_execution_status"]
        self.assertIn(projection_execution, {"PASS", "FAIL"})
        if projection_execution == "PASS":
            self.assertEqual(
                "ABSENT", long_24["generator_projection_control_surface"]
            )
            self.assertEqual(
                "PASS", long_24["generator_projection_reproducibility"]
            )
            self.assertEqual(
                "PASS", long_24["generator_projection_transaction_surface"]
            )
        else:
            self.assertEqual("FAIL", long_24["status"])
            self.assertEqual("FAIL", long_24["delivery_gate_status"])
            self.assertEqual(1, long_24["exit_code"])
            self.assertEqual(
                "NOT_RUN", long_24["generator_projection_control_surface"]
            )
            self.assertEqual(
                "NOT_RUN", long_24["generator_projection_reproducibility"]
            )
            self.assertEqual(
                "NOT_RUN", long_24["generator_projection_transaction_surface"]
            )
            self.assertTrue(long_24.get("error"))

    def test_unknown_scenario_and_mismatched_mirror_fail_closed(self) -> None:
        unknown = self.run_helper("LONG-99")
        self.assertEqual(1, unknown.returncode)
        self.assertEqual("FAIL", json.loads(unknown.stdout)["status"])

        self.output.write_text("different", encoding="utf-8")
        mismatch = self.run_helper("LONG-20")
        self.assertEqual(1, mismatch.returncode)
        self.assertIn("mirror", json.loads(mismatch.stdout)["error"])

        self.input.write_text("same arbitrary bytes", encoding="utf-8")
        self.output.write_text("same arbitrary bytes", encoding="utf-8")
        unbound = self.run_helper("LONG-20")
        self.assertEqual(1, unbound.returncode)
        self.assertIn("fixed qualification fixture", json.loads(unbound.stdout)["error"])

    def test_invalid_utf8_and_input_symlink_fail_closed(self) -> None:
        self.input.write_bytes(b"\xff\xfe")
        self.output.write_bytes(b"\xff\xfe")
        invalid = self.run_helper("LONG-20")
        self.assertEqual(1, invalid.returncode)
        self.assertIn("UTF-8", json.loads(invalid.stdout)["error"])

        if not hasattr(os, "symlink"):
            return
        self.input.unlink()
        try:
            os.symlink(SOURCE, self.input)
        except OSError:
            self.skipTest("symlink creation is unavailable")
        self.output.write_bytes(SOURCE.read_bytes())
        linked = self.run_helper("LONG-20")
        self.assertEqual(1, linked.returncode)
        self.assertIn("symlink", json.loads(linked.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
