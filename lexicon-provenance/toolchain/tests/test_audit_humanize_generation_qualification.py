import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"
SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
SCRIPT = SKILL / "scripts" / "audit_humanize_generation_qualification.py"
REQUIREMENTS = SKILL / "references" / "generation-qualification-requirements.json"
CONTRACT = SKILL / "references" / "evaluation-contract.md"
ORACLE = SKILL / "references" / "generation-qualification-oracles.json"
TRUST = SKILL / "references" / "generation-qualification-trust.json"
FIXTURE_MANIFEST = (
    TESTS_ROOT / "fixtures" / "humanize_generation_qualification" / "manifest.json"
)
SPEC = importlib.util.spec_from_file_location("audit_humanize_generation_qualification", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
auditor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = auditor
SPEC.loader.exec_module(auditor)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class HumanizeGenerationQualificationAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def current_bindings(self) -> dict[str, str]:
        return auditor._current_bindings(SKILL, CONTRACT, REQUIREMENTS)

    def current_projection(self) -> object:
        return auditor._current_projection_state(SKILL)

    def write_artifact(self, name: str, content: str | bytes) -> tuple[dict, Path]:
        path = self.root / name
        raw = content.encode("utf-8") if isinstance(content, str) else content
        path.write_bytes(raw)
        return {"path": path.name, "sha256": sha256(raw)}, path

    def artifact_object(self, key: str, path: Path) -> object:
        raw = path.read_bytes()
        digest = sha256(raw)
        return auditor.Artifact(key, path, digest, digest, len(raw), raw)

    def write_manifest(self, payload: dict, name: str = "manifest.json") -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def rewrite_case_artifact(self, case: dict, key: str, payload: dict) -> str:
        descriptor = case["artifacts"][key]
        path = self.root / descriptor["path"]
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        path.write_bytes(raw)
        digest = sha256(raw)
        descriptor["sha256"] = digest
        return digest

    def sync_run_seal(self, case: dict) -> None:
        seal_path = self.root / case["artifacts"]["run_seal"]["path"]
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        seal["run_record_sha256"] = case["artifacts"]["raw_run"]["sha256"]
        seal["runner_receipt_sha256"] = case["artifacts"]["runner_receipt"]["sha256"]
        self.rewrite_case_artifact(case, "run_seal", seal)

    def audit_manifest(self, payload: dict, name: str = "manifest.json") -> dict:
        return auditor.audit(
            self.write_manifest(payload, name),
            skill_root=SKILL,
            requirements_path=REQUIREMENTS,
            contract_path=CONTRACT,
            artifact_root=self.root,
            replay_timeout=30,
        )

    def oracle_catalog(self) -> object:
        requirements = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        atoms, errors = auditor._expand_requirements(requirements)
        self.assertEqual([], errors)
        return auditor._load_oracle_catalog(
            SKILL, CONTRACT, REQUIREMENTS, requirements, atoms
        )

    def make_v2_case(
        self,
        suite_id: str,
        *,
        output: str | bytes | None = None,
        run_id: str = "RUN-V2-001",
        include_generation: bool = True,
        isolation_verified: bool = False,
        add_passing_review: bool = False,
        corrupt_run_binding_field: str | None = None,
        omit_public_seal: bool = False,
    ) -> tuple[dict, dict[str, Path]]:
        catalog = self.oracle_catalog()
        suite = catalog.suites[suite_id]
        bindings = self.current_bindings()
        artifacts: dict[str, dict] = {}
        paths: dict[str, Path] = {}
        for role, fixture_descriptor in suite["fixture_bindings"].items():
            source = SKILL / fixture_descriptor["path"]
            target_name = f"{role}{source.suffix or '.bin'}"
            descriptor, path = self.write_artifact(target_name, source.read_bytes())
            artifacts[role] = descriptor
            paths[role] = path
        if "public_context" in artifacts:
            dynamic_context = {
                "schema_version": "humanize-generation-dynamic-context/v1",
                "public_context_sha256": artifacts["public_context"]["sha256"],
                "runner": "UNIT_TEST_HARNESS",
                "model": "synthetic-test-model",
                "oracle_catalog_sha256": catalog.raw_sha256,
                "manifest_schema": auditor.MANIFEST_V2_SCHEMA,
                "filesystem_isolation_verified": isolation_verified,
            }
            descriptor, path = self.write_artifact(
                "context.json",
                json.dumps(dynamic_context, ensure_ascii=False, sort_keys=True),
            )
            artifacts["context"] = descriptor
            paths["context"] = path
        if output is not None:
            descriptor, path = self.write_artifact("output.md", output)
            artifacts["output"] = descriptor
            paths["output"] = path
        if not include_generation:
            case = {
                "id": "V2-CASE-001",
                "artifacts": artifacts,
                "claims": [
                    {
                        "claim_id": "V2-CLAIM-001",
                        "atom_id": suite["atom_id"],
                        "oracle_suite_id": suite_id,
                    }
                ],
            }
            return case, paths
        self.assertIn("input", artifacts)
        self.assertIn("output", artifacts)
        self.assertIn("prompt", artifacts)
        self.assertIn("context", artifacts)
        public_prompt_descriptor, public_prompt_path = self.write_artifact(
            "public-prompt.txt", paths["prompt"].read_bytes()
        )
        artifacts["public_prompt"] = public_prompt_descriptor
        paths["public_prompt"] = public_prompt_path
        projection = self.current_projection()
        projection_descriptor, projection_path = self.write_artifact(
            "projection-manifest.json", projection.manifest_raw
        )
        artifacts["projection_manifest"] = projection_descriptor
        paths["projection_manifest"] = projection_path
        artifact_hashes = {
            role: artifacts[role]["sha256"]
            for role in ("input", "output", "prompt", "context")
        }
        run_bindings = dict(bindings)
        if corrupt_run_binding_field is not None:
            run_bindings[corrupt_run_binding_field] = "0" * 64
        public_artifact_hashes = {
            "input": artifacts["input"]["sha256"],
            "prompt": artifacts["public_prompt"]["sha256"],
            "public_context": artifacts["public_context"]["sha256"],
        }
        receipt = {
            "schema_version": auditor.RUNNER_RECEIPT_SCHEMA,
            "runner_version": "1.1.0",
            "runner_status": "CAPTURED_E2",
            "campaign_id": None,
            "case_id": "V2-CASE-001",
            "run_id": run_id,
            "runner_executable_sha256": "1" * 64,
            "codex_executable": "synthetic-codex",
            "codex_executable_sha256": "2" * 64,
            "codex_version": "synthetic",
            "process_identity": {"pid": 1234, "new_process_observed": True},
            "started_at": "2026-07-14T00:00:00Z",
            "ended_at": "2026-07-14T00:00:01Z",
            "model_requested": "synthetic-test-model",
            "provider_ids": {"request_id": ["request-1"], "response_id": [], "turn_id": []},
            "provider_request_id_observed": True,
            "sandbox": "read-only",
            "generator_projection": dict(projection.runner_binding),
            "isolation": {
                "filesystem_isolation_verified": False,
                "host_excluded_roots_unreachable_verified": False,
                "oracle_catalog_present_in_projection": False,
                "oracle_catalog_unreachable_to_generator": "UNVERIFIED",
                "verification_source": "LOCAL_COPY_ONLY",
                "evidence_cap": "E2",
            },
            "filesystem_isolation_verified": False,
            "excluded_roots_unreachable_verified": False,
            "oracle_catalog_visible_to_generator": None,
            "evidence_cap": "E2",
            "artifact_sha256": {
                **artifact_hashes,
                "public_context": artifacts["public_context"]["sha256"],
                "events": "3" * 64,
                "stderr": "4" * 64,
            },
            "qualification_bindings": run_bindings,
            "public_manifest_sha256": "5" * 64,
            "public_seal_sha256": "6" * 64,
            "exit_status": {
                "returncode": 0,
                "timed_out": False,
                "event_parse_error": None,
                "output_present": True,
                "post_run_validation_error": None,
            },
        }
        receipt_descriptor, receipt_path = self.write_artifact(
            "runner-receipt.json",
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        artifacts["runner_receipt"] = receipt_descriptor
        paths["runner_receipt"] = receipt_path
        run_record: dict = {
            "schema_version": auditor.GENERATION_RUN_RECORD_SCHEMA,
            "run_id": run_id,
            "fresh_context": True,
            "blindness_attestation": auditor.BLINDNESS_ATTESTATION,
            "artifact_sha256": artifact_hashes,
            "qualification_bindings": run_bindings,
            "generator_projection": dict(projection.runner_binding),
            "oracle_catalog_visible_to_generator": False if isolation_verified else None,
            "filesystem_isolation_verified": isolation_verified,
            "isolation_verification_source": (
                "HARNESS_VERIFIED_GENERATOR_PROJECTION"
                if isolation_verified
                else "LOCAL_COPY_ONLY"
            ),
            "runner_receipt_sha256": receipt_descriptor["sha256"],
            "execution_provenance": {
                "source": "HARNESS_OWNED_LOCAL_RUNNER",
                "process_boundary_observed": True,
                "filesystem_isolation_verified": False,
                "oracle_catalog_present_in_projection": False,
                "oracle_catalog_unreachable_to_generator": "UNVERIFIED",
                "evidence_cap": "E2",
            },
            "generator_context": {
                "stdin_prompt_sha256": artifacts["prompt"]["sha256"],
                "staged_case_sha256": {
                    paths["input"].name: artifacts["input"]["sha256"],
                    "prompt.txt": artifacts["public_prompt"]["sha256"],
                    "public-context.json": artifacts["public_context"]["sha256"],
                },
                "capture_context_sha256": artifacts["context"]["sha256"],
                "capture_context_generator_visible": False,
                "system_messages": "UNAVAILABLE_FROM_CODEX_EXEC_CLI",
                "developer_messages": "UNAVAILABLE_FROM_CODEX_EXEC_CLI",
                "complete": False,
            },
        }
        if not omit_public_seal:
            run_record["public_artifact_sha256"] = public_artifact_hashes
        raw_descriptor, raw_path = self.write_artifact(
            "raw_run.json",
            json.dumps(run_record, ensure_ascii=False, sort_keys=True),
        )
        artifacts["raw_run"] = raw_descriptor
        paths["raw_run"] = raw_path
        run_seal = {
            "schema_version": auditor.RUN_SEAL_SCHEMA,
            "run_id": run_id,
            "case_id": "V2-CASE-001",
            "run_record_sha256": raw_descriptor["sha256"],
            "runner_receipt_sha256": receipt_descriptor["sha256"],
            "artifact_sha256": artifact_hashes,
            "public_artifact_sha256": public_artifact_hashes,
            "transcript_sha256": {"events": "3" * 64, "stderr": "4" * 64},
            "generator_projection": {
                "manifest_sha256": projection.manifest_sha256,
                "tree_sha256": projection.manifest["projection_tree_sha256"],
            },
        }
        seal_descriptor, seal_path = self.write_artifact(
            "run-seal.json",
            json.dumps(run_seal, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        artifacts["run_seal"] = seal_descriptor
        paths["run_seal"] = seal_path
        case: dict = {
            "id": "V2-CASE-001",
            "artifacts": artifacts,
            "generation": {
                "run_id": run_id,
                "raw_run_artifact": "raw_run",
                "raw_run_sha256": raw_descriptor["sha256"],
                "prompt_artifact": "prompt",
                "context_artifact": "context",
                "fresh_context": True,
                "blindness_attestation": auditor.BLINDNESS_ATTESTATION,
            },
            "claims": [
                {
                    "claim_id": "V2-CLAIM-001",
                    "atom_id": suite["atom_id"],
                    "oracle_suite_id": suite_id,
                }
            ],
        }
        if add_passing_review:
            rubric_id = suite["required_reviews"][0]
            rubric = catalog.rubrics[rubric_id]
            review = {
                "schema_version": auditor.ORACLE_REVIEW_SCHEMA,
                "review_id": "REVIEW-V2-001",
                "case_id": case["id"],
                "suite_id": suite_id,
                "rubric_id": rubric_id,
                "reviewer": {
                    "kind": "MODEL",
                    "id_sha256": "9" * 64,
                    "identity_verified": False,
                    "provenance": "CALLER_DECLARED",
                    "review_run_id": "REVIEW-RUN-V2-001",
                    "expected_answers_staged": False,
                },
                "bindings": {
                    "input_sha256": artifacts["input"]["sha256"],
                    "output_sha256": artifacts["output"]["sha256"],
                    "generation_run_record_sha256": raw_descriptor["sha256"],
                    "anonymous_bundle_sha256": artifacts["review_bundle"]["sha256"],
                    "rubric_sha256": catalog.rubric_sha256[rubric_id],
                    "oracle_catalog_sha256": catalog.raw_sha256,
                },
                "answers": [
                    {"question_id": question["id"], "answer": "PASS"}
                    for question in rubric["questions"]
                ],
            }
            review_descriptor, review_path = self.write_artifact(
                "review.json", json.dumps(review, ensure_ascii=False, sort_keys=True)
            )
            artifacts["review"] = review_descriptor
            paths["review"] = review_path
            case["reviews"] = [{"artifact": "review"}]
        return case, paths

    def v2_manifest(self, case: dict) -> dict:
        return {
            "schema_version": auditor.MANIFEST_V2_SCHEMA,
            "bindings": self.current_bindings(),
            "cases": [case],
            "archived_failures": [],
        }

    def test_tests_total_and_archived_e1_pass_do_not_add_qualification_coverage(self) -> None:
        report = auditor.audit(
            FIXTURE_MANIFEST,
            skill_root=SKILL,
            requirements_path=REQUIREMENTS,
            contract_path=CONTRACT,
            artifact_root=TESTS_ROOT,
        )
        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("NOT_EVALUATED", report["qualification_status"])
        self.assertEqual(2, report["exit_code"])
        self.assertTrue(report["tests_total_ignored"])
        self.assertEqual(999999, report["declared_tests_total"])
        self.assertEqual(0, report["summary"]["atoms_pass"])
        self.assertEqual(193, report["summary"]["atoms_not_evaluated"])
        self.assertEqual("E1", report["cases"][0]["evidence_level"])
        self.assertTrue(report["cases"][0]["archived"])
        self.assertEqual("NOT_EVALUATED", report["cases"][0]["claims"][0]["status"])
        atom_id = report["cases"][0]["claims"][0]["atom_id"]
        atom = next(item for item in report["atoms"] if item["atom_id"] == atom_id)
        self.assertTrue(atom["claims"][0]["archived"])

    def test_p2_failure_is_counted_and_nonblocking_only_after_evaluation(self) -> None:
        p0_pass = {"status": "PASS", "severity": "P0"}
        p2_fail = {"status": "FAIL", "severity": "P2"}
        p2_pending = {"status": "NOT_EVALUATED", "severity": "P2"}

        self.assertEqual(
            ("PASS", "PASS", 0),
            auditor._aggregate_qualification([p0_pass, p2_fail], []),
        )
        self.assertEqual(
            ("PASS", "NOT_EVALUATED", 2),
            auditor._aggregate_qualification([p0_pass, p2_pending], []),
        )
        self.assertEqual(
            {"P0": 0, "P1": 0, "P2": 1},
            auditor._failure_counts_by_severity([p0_pass, p2_fail]),
        )

    def test_unknown_atom_is_an_integrity_failure(self) -> None:
        payload = {
            "schema_version": "humanize-generation-qualification-manifest/v1",
            "cases": [
                {
                    "id": "UNKNOWN-ATOM-CASE",
                    "assertions": [{"id": "UNKNOWN-ASSERT", "result": "PASS"}],
                    "claims": [
                        {
                            "claim_id": "UNKNOWN-CLAIM",
                            "atom_id": "UNKNOWN/atom",
                            "assertion_ids": ["UNKNOWN-ASSERT"],
                        }
                    ],
                }
            ],
            "archived_failures": [],
        }
        report = self.audit_manifest(payload)
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertEqual(1, report["exit_code"])
        self.assertTrue(any("unknown atom" in item for item in report["integrity_errors"]))

    def test_duplicate_coverage_atom_is_rejected(self) -> None:
        cases = []
        for number in (1, 2):
            cases.append(
                {
                    "id": f"DUPLICATE-ATOM-CASE-{number}",
                    "assertions": [{"id": f"DUPLICATE-ASSERT-{number}", "result": "PASS"}],
                    "claims": [
                        {
                            "claim_id": f"DUPLICATE-CLAIM-{number}",
                            "atom_id": "MODE-02",
                            "assertion_ids": [f"DUPLICATE-ASSERT-{number}"],
                        }
                    ],
                }
            )
        report = self.audit_manifest(
            {
                "schema_version": "humanize-generation-qualification-manifest/v1",
                "cases": cases,
                "archived_failures": [],
            }
        )
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any("duplicate coverage atom: MODE-02" in item for item in report["integrity_errors"])
        )

    def test_duplicate_requirement_atom_is_rejected_before_coverage(self) -> None:
        requirements = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        requirements["global_atoms"].append(copy.deepcopy(requirements["global_atoms"][0]))
        _atoms, errors = auditor._expand_requirements(requirements)
        self.assertTrue(any("duplicate atom" in item for item in errors))

    def test_current_contract_atoms_are_registered_in_the_qualification_matrix(self) -> None:
        requirements = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        atoms, errors = auditor._expand_requirements(requirements)
        self.assertEqual([], errors)
        self.assertEqual(193, len(atoms))
        self.assertIn("DEC-09", atoms)
        self.assertEqual("E3", atoms["DEC-09"].minimum_evidence)
        self.assertEqual("P1", atoms["DEC-09"].severity)
        self.assertIn("VOICE-11", atoms)
        self.assertEqual("E3", atoms["VOICE-11"].minimum_evidence)
        self.assertEqual("P1", atoms["VOICE-11"].severity)
        self.assertIn("VOICE-12", atoms)
        self.assertEqual("E3", atoms["VOICE-12"].minimum_evidence)
        self.assertEqual("P1", atoms["VOICE-12"].severity)
        for atom_id in (
            "LONG-14",
            "LONG-15",
            "LONG-16",
            "LONG-17",
            "LONG-18",
            "LONG-19",
            "LONG-20",
            "LONG-21",
            "LONG-22",
            "LONG-23",
            "LONG-24",
            "LONG-25",
            "LONG-26",
            "LONG-27",
            "LONG-28",
        ):
            self.assertIn(atom_id, atoms)
            self.assertEqual("E3", atoms[atom_id].minimum_evidence)
            self.assertEqual("P0", atoms[atom_id].severity)
        for atom_id in (
            "ROUTE-13",
            "ROUTE-14",
            "VOICE-13",
            "VOICE-14",
            "ROLE-10",
            "ROLE-11",
            "ROLE-12",
            "ROLE-13",
            "ROLE-14",
            "ROLE-15",
            "ROLE-16",
            "ROLE-17",
        ):
            self.assertIn(atom_id, atoms)
        for atom_id in ("ROLE-14", "ROLE-15", "ROLE-16", "ROLE-17"):
            self.assertEqual("E3", atoms[atom_id].minimum_evidence)
            self.assertEqual("P0", atoms[atom_id].severity)
        self.assertEqual(
            [],
            auditor._contract_alignment(
                CONTRACT.read_text(encoding="utf-8"), atoms
            ),
        )

    def test_requirements_binding_contract_requires_oracle_catalog(self) -> None:
        requirements = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        required = requirements["evidence_binding_contract"]["required_current_bindings"]
        self.assertIn("oracle_catalog_sha256", required)
        self.assertIn("trust_policy_sha256", required)
        requirements["evidence_binding_contract"]["required_current_bindings"] = [
            item for item in required if item != "oracle_catalog_sha256"
        ]
        _atoms, errors = auditor._expand_requirements(requirements)
        self.assertTrue(any("evidence binding contract" in item for item in errors))

    def test_trust_policy_is_fixed_and_cannot_enable_e3(self) -> None:
        policy = auditor._load_trust_policy(SKILL)
        self.assertFalse(policy.production_e3_enabled)
        self.assertEqual((), policy.accepted_receipt_schemes)
        self.assertEqual("E2", policy.local_runner_maximum_evidence)
        temporary_skill = self.root / "skill"
        references = temporary_skill / "references"
        references.mkdir(parents=True)
        payload = json.loads(TRUST.read_text(encoding="utf-8"))
        payload["e3"]["production_enabled"] = True
        payload["e3"]["accepted_receipt_schemes"] = ["CALLER_JSON"]
        (references / TRUST.name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(auditor.AuditError, "cannot enable E3"):
            auditor._load_trust_policy(temporary_skill)

    def test_catalog_separates_shadow_and_fresh_forward_suites(self) -> None:
        catalog = self.oracle_catalog()
        self.assertTrue(catalog.suites)
        for atom_id in ("ROLE-10", "ROLE-11", "ROLE-12", "ROLE-13"):
            suite = catalog.suites[f"{atom_id}/source-provenance/v1"]
            self.assertEqual("FRESH_FORWARD", suite["qualification_stage"])
            self.assertTrue(suite["runner_compatible"])
        shadow = [
            suite
            for suite in catalog.suites.values()
            if suite["qualification_stage"] == "SHADOW"
        ]
        self.assertEqual(19, len(shadow))
        self.assertTrue(all(suite["runner_compatible"] is False for suite in shadow))
        public_context = (
            SKILL
            / "references"
            / "generation-qualification-fixtures"
            / "v1"
            / "path-05-context.json"
        ).read_text(encoding="utf-8")
        payload = json.loads(public_context)
        self.assertEqual(auditor.PUBLIC_CONTEXT_SCHEMA, payload["schema_version"])
        self.assertEqual(
            {
                "schema_version",
                "mode",
                "scene",
                "intensity",
                "output",
                "report_context",
                "scope",
                "title_lock",
                "structure_lock",
                "task_options",
            },
            set(payload),
        )

    def test_new_contract_atoms_have_fixed_e2_shadow_checks(self) -> None:
        catalog = self.oracle_catalog()
        raw = CONTRACT.read_bytes()
        digest = sha256(raw)
        artifact = auditor.Artifact(
            "contract", CONTRACT, digest, digest, len(raw), raw
        )
        for atom_id, (suite_id, check_id, expected_hashes) in (
            auditor.REQUIRED_CONTRACT_ROW_SLICE.items()
        ):
            with self.subTest(atom_id=atom_id):
                suite = catalog.suites[suite_id]
                self.assertEqual(atom_id, suite["atom_id"])
                self.assertEqual("SHADOW", suite["qualification_stage"])
                self.assertFalse(suite["runner_compatible"])
                self.assertEqual([check_id], suite["required_checks"])
                self.assertEqual([], suite["required_reviews"])
                check = catalog.checks[check_id]
                self.assertEqual("contract_matrix_row", check["type"])
                self.assertEqual(
                    {
                        "artifact_role": "contract",
                        "atom_id": atom_id,
                        "expected_cell_sha256": list(expected_hashes),
                    },
                    check["configuration"],
                )
                errors: list[str] = []
                result = auditor._evaluate_oracle_check(
                    check_id,
                    catalog,
                    {"contract": artifact},
                    SKILL,
                    30,
                    errors,
                )
                self.assertEqual([], errors)
                self.assertTrue(result["integrity_valid"])
                self.assertEqual("PASS", result["status"])

    def test_passing_contract_row_check_cannot_upgrade_e3_atom(self) -> None:
        case, _ = self.make_v2_case(
            "ROLE-16/template-field-contract/v1",
            include_generation=False,
        )
        synthetic_projection = auditor.ProjectionState(
            manifest_raw=b"{}",
            manifest_sha256="0" * 64,
            manifest={
                "projection_tree_sha256": "1" * 64,
                "projection_policy": {"sha256": "2" * 64},
                "builder": {"executable_sha256": "3" * 64},
                "source": {"inventory_sha256": "4" * 64},
            },
            runner_binding={},
        )
        with mock.patch.object(
            auditor, "_current_projection_state", return_value=synthetic_projection
        ):
            report = self.audit_manifest(
                self.v2_manifest(case), name="role-16-contract-only.json"
            )
        claim = report["cases"][0]["claims"][0]
        check = report["cases"][0]["oracle_suites"][0]["checks"][0]
        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("E2", report["cases"][0]["evidence_level"])
        self.assertEqual("PASS", check["status"])
        self.assertEqual("E3", claim["minimum_evidence"])
        self.assertEqual("NOT_EVALUATED", claim["status"])

    def test_contract_row_checks_reject_role_and_scope_drift(self) -> None:
        catalog = self.oracle_catalog()
        original = CONTRACT.read_text(encoding="utf-8")
        long_28_row = next(
            line for line in original.splitlines() if line.startswith("| `LONG-28` |")
        )
        cases = (
            (
                "contract/ROLE-16/template-field/v1",
                original.replace(
                    "READER_FACING_ARTIFACT_ROLE/PROMPT_STEM",
                    "EDITORIAL_PAYLOAD/TEACHING_REASONING",
                    1,
                ),
            ),
            (
                "contract/LONG-28/template-field-edit-scope/v1",
                original.replace(
                    long_28_row,
                    long_28_row.replace(
                        "PAYLOAD_ONLY/local_clearance_supported=false",
                        "PAYLOAD_ONLY/local_clearance_supported=true",
                        1,
                    ),
                    1,
                ),
            ),
        )
        for check_id, drifted in cases:
            with self.subTest(check_id=check_id):
                descriptor, path = self.write_artifact("contract.md", drifted)
                artifact = auditor.Artifact(
                    "contract",
                    path,
                    descriptor["sha256"],
                    descriptor["sha256"],
                    path.stat().st_size,
                    path.read_bytes(),
                )
                errors: list[str] = []
                result = auditor._evaluate_oracle_check(
                    check_id,
                    catalog,
                    {"contract": artifact},
                    SKILL,
                    30,
                    errors,
                )
                self.assertEqual([], errors)
                self.assertTrue(result["integrity_valid"])
                self.assertEqual("FAIL", result["status"])

    def test_contract_row_check_rejects_missing_or_duplicate_atom_row(self) -> None:
        catalog = self.oracle_catalog()
        check_id = "contract/ROLE-14/template-field/v1"
        original = CONTRACT.read_text(encoding="utf-8")
        row = next(
            line for line in original.splitlines() if line.startswith("| `ROLE-14` |")
        )
        candidates = {
            "missing": original.replace(row + "\n", "", 1),
            "duplicate": original.replace(row + "\n", row + "\n" + row + "\n", 1),
        }
        for label, candidate in candidates.items():
            with self.subTest(label=label):
                descriptor, path = self.write_artifact(
                    f"contract-{label}.md", candidate
                )
                artifact = auditor.Artifact(
                    "contract",
                    path,
                    descriptor["sha256"],
                    descriptor["sha256"],
                    path.stat().st_size,
                    path.read_bytes(),
                )
                errors: list[str] = []
                result = auditor._evaluate_oracle_check(
                    check_id,
                    catalog,
                    {"contract": artifact},
                    SKILL,
                    30,
                    errors,
                )
                self.assertEqual([], errors)
                self.assertEqual("FAIL", result["status"])
                self.assertEqual(0 if label == "missing" else 2, result["observation"]["row_count"])

    def test_contract_row_configuration_rejects_unknown_fields_and_hashes(self) -> None:
        base = {
            "artifact_role": "contract",
            "atom_id": "ROLE-16",
            "expected_cell_sha256": ["0" * 64, "1" * 64],
        }
        invalid_atom = dict(base, atom_id="ROUTE-01")
        with self.assertRaisesRegex(auditor.AuditError, "ROLE/LONG contract ID"):
            auditor._validate_catalog_check_configuration(
                "contract_matrix_row", invalid_atom, "contract-check"
            )
        invalid_hashes = dict(base, expected_cell_sha256=["not-a-hash"])
        with self.assertRaisesRegex(auditor.AuditError, "hash array"):
            auditor._validate_catalog_check_configuration(
                "contract_matrix_row", invalid_hashes, "contract-check"
            )
        extra = dict(base, payload_role="EDITORIAL_PAYLOAD")
        with self.assertRaisesRegex(auditor.AuditError, "fields are invalid"):
            auditor._validate_catalog_check_configuration(
                "contract_matrix_row", extra, "contract-check"
            )

    def test_dec_09_recomputes_paired_quality_request_binding(self) -> None:
        catalog = self.oracle_catalog()
        suite = catalog.suites["DEC-09/paired-quality-gate/v1"]
        check = catalog.checks[suite["required_checks"][0]]
        fixture = (
            SKILL
            / "references"
            / "generation-qualification-fixtures"
            / "v1"
            / "protected-output.md"
        )
        raw = fixture.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        artifacts = {
            role: auditor.Artifact(role, fixture, digest, digest, len(raw), raw)
            for role in ("input", "output")
        }
        errors: list[str] = []
        replay = auditor._run_replay(
            check["configuration"],
            artifacts,
            SKILL,
            30,
            "DEC-09-test",
            errors,
        )
        self.assertEqual([], errors)
        self.assertTrue(replay["integrity_valid"])
        self.assertTrue(replay["behavior_matches_expected"])
        self.assertEqual(
            "PASS",
            replay["actual"]["paired_quality_review_request_binding_status"],
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(SKILL / "scripts" / "validate_humanize_output.py"),
                str(fixture),
                str(fixture),
                "--mode",
                "REWRITE",
                "--scene",
                "GENERAL",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        valid_payload = json.loads(completed.stdout)

        def resign(candidate: dict) -> None:
            request = candidate["paired_quality_review_request"]
            unsigned = dict(request)
            unsigned.pop("request_sha256", None)
            request["request_sha256"] = auditor._sha256(
                auditor._canonical_json(unsigned)
            )

        tampered_payloads = {}
        unknown_field = copy.deepcopy(valid_payload)
        unknown_field["paired_quality_review_request"][
            "external_clearance_granted"
        ] = True
        tampered_payloads["unknown clearance field"] = unknown_field

        contradictory_clearance = copy.deepcopy(valid_payload)
        contradictory_clearance["paired_quality_review_request"]["limitations"][
            "quality_clearance_granted"
        ] = True
        tampered_payloads["contradictory clearance"] = contradictory_clearance

        verdict_drift = copy.deepcopy(valid_payload)
        verdict_drift["paired_quality_review_request"]["review_contract"][
            "required_per_change_verdicts"
        ].remove("REVERT")
        tampered_payloads["required verdict drift"] = verdict_drift

        dimension_drift = copy.deepcopy(valid_payload)
        dimension_drift["paired_quality_review_request"]["review_contract"][
            "required_dimensions"
        ].remove("author_voice_non_regression")
        tampered_payloads["required dimension drift"] = dimension_drift

        for label, tampered in tampered_payloads.items():
            with self.subTest(label=label):
                resign(tampered)
                observation = auditor._paired_quality_request_observation(
                    tampered, artifacts, SKILL
                )
                self.assertEqual(
                    "FAIL",
                    observation["paired_quality_review_request_binding_status"],
                )

    def test_dec_09_template_field_change_contract_is_closed(self) -> None:
        change_id = "change-1"
        changes = [{"change_id": change_id}]
        record = {
            "code": "TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED",
            "severity": "info",
            "change_id": change_id,
            "field_label": "用词建议",
            "source_role": "TEMPLATE_FIELD",
            "payload_role": "EDITORIAL_PAYLOAD/LEXICAL_GUIDANCE",
            "source_line": 1,
            "after_line": 1,
            "authorization_status": "AUTHORIZED_PAYLOAD_ONLY",
            "permission": "PAYLOAD_ONLY",
            "authorization_reason": "第1行用词建议字段仅调整载荷措辞并保持字段职责",
            "change_types": [],
            "before_span": {
                "line": 1,
                "payload_sha256": "a" * 64,
                "line_sha256": "b" * 64,
            },
            "after_span": {
                "line": 1,
                "payload_sha256": "c" * 64,
                "line_sha256": "d" * 64,
            },
            "local_clearance_supported": False,
        }
        self.assertTrue(
            auditor._paired_template_field_changes_valid(
                [record], changes, "REWRITE"
            )
        )

        invalid_records = {}
        unknown_field = copy.deepcopy(record)
        unknown_field["self_clearance"] = True
        invalid_records["unknown field"] = [unknown_field]
        false_authorization = copy.deepcopy(record)
        false_authorization["authorization_status"] = "NOT_AUTHORIZED"
        invalid_records["false authorization"] = [false_authorization]
        unbound_change = copy.deepcopy(record)
        unbound_change["change_id"] = "change-2"
        invalid_records["unbound change"] = [unbound_change]
        invalid_records["duplicate record"] = [record, copy.deepcopy(record)]
        invalid_span = copy.deepcopy(record)
        invalid_span["before_span"]["payload_sha256"] = "not-a-hash"
        invalid_records["invalid span"] = [invalid_span]

        for label, candidate in invalid_records.items():
            with self.subTest(label=label):
                self.assertFalse(
                    auditor._paired_template_field_changes_valid(
                        candidate, changes, "REWRITE"
                    )
                )
        self.assertFalse(
            auditor._paired_template_field_changes_valid(
                [record], changes, "NO_CHANGE"
            )
        )

    def test_long_structural_atoms_have_fixed_executable_shadow_routes(self) -> None:
        catalog = self.oracle_catalog()
        expected = {
            "LONG-20": "LONG-20/structural-review-request/v1",
            "LONG-21": "LONG-21/review-only-delivery/v1",
            "LONG-22": "LONG-22/adjacent-pair-authority/v1",
            "LONG-23": "LONG-23/adjacent-pair-atomic-review/v1",
            "LONG-24": "LONG-24/transaction-non-downgrade/v1",
            "LONG-25": "LONG-25/transaction-candidate-disposition/v1",
            "LONG-26": "LONG-26/paired-quality-candidate/v1",
            "LONG-27": "LONG-27/paired-quality-second-pass-non-clearance/v1",
        }
        for atom_id, suite_id in expected.items():
            with self.subTest(atom_id=atom_id):
                suite = catalog.suites[suite_id]
                self.assertEqual(atom_id, suite["atom_id"])
                self.assertEqual("SHADOW", suite["qualification_stage"])
                self.assertFalse(suite["runner_compatible"])
                self.assertTrue(suite["required_checks"])
                self.assertEqual(
                    (suite_id, suite["required_checks"][0]),
                    auditor.REQUIRED_LONG_REPLAY_SLICE[atom_id],
                )
                for check_id in suite["required_checks"]:
                    check = catalog.checks[check_id]
                    self.assertEqual("replay_result", check["type"])
                    self.assertEqual(
                        "replay_humanize_long_fixture",
                        check["configuration"]["tool_id"],
                    )
                    self.assertEqual(
                        ["${INPUT}", "${OUTPUT}", "--scenario", atom_id],
                        check["configuration"]["args"],
                    )
                    self.assertEqual(
                        auditor.REPLAY_SCENARIO_EXPECTED_FIELDS[atom_id],
                        set(check["configuration"]["expected"]),
                    )
        self.assertEqual(
            "scripts/replay_humanize_long_fixture.py",
            auditor.TOOL_ALLOWLIST["replay_humanize_long_fixture"]["relative_path"],
        )
        self.assertTrue(
            all(
                atom_id in auditor.REQUIRED_VERTICAL_SLICE
                for atom_id in expected
            )
        )

    def test_long_replay_expected_fields_and_scalar_types_are_closed(self) -> None:
        catalog = self.oracle_catalog()
        check = catalog.checks[
            "replay/LONG-22/adjacent-pair-authority/v1"
        ]
        expected, error = auditor._expected_machine_result(
            check["configuration"]
        )
        self.assertIsNone(error)
        self.assertEqual(
            auditor.REPLAY_SCENARIO_EXPECTED_FIELDS["LONG-22"], set(expected)
        )

        missing = copy.deepcopy(check["configuration"])
        missing["expected"].pop("structural_transaction_conflict_rejected")
        _expected, error = auditor._expected_machine_result(missing)
        self.assertIn("fields drifted", error)

        bool_as_count = copy.deepcopy(check["configuration"])
        bool_as_count["expected"]["structural_transaction_count"] = True
        _expected, error = auditor._expected_machine_result(bool_as_count)
        self.assertIn("invalid scalar type", error)

        disposition_check = catalog.checks[
            "replay/LONG-25/transaction-candidate-disposition/v1"
        ]
        disposition_expected, error = auditor._expected_machine_result(
            disposition_check["configuration"]
        )
        self.assertIsNone(error)
        self.assertEqual(
            auditor.REPLAY_SCENARIO_EXPECTED_FIELDS["LONG-25"],
            set(disposition_expected),
        )

        for atom_id, check_id in (
            ("LONG-26", "replay/LONG-26/paired-quality-candidate/v1"),
            (
                "LONG-27",
                "replay/LONG-27/paired-quality-second-pass-non-clearance/v1",
            ),
        ):
            with self.subTest(atom_id=atom_id):
                paired_check = catalog.checks[check_id]
                paired_expected, error = auditor._expected_machine_result(
                    paired_check["configuration"]
                )
                self.assertIsNone(error)
                self.assertEqual(
                    auditor.REPLAY_SCENARIO_EXPECTED_FIELDS[atom_id],
                    set(paired_expected),
                )

    def test_source_provenance_suites_use_hidden_policy_decisions_at_e2(self) -> None:
        expected = {
            "ROLE-10": {
                "source_id": "source-a",
                "production_positive": False,
                "assurance": "NEGATIVE_ONLY",
                "allowed_uses": ["AUDIT", "NEGATIVE_GUARD"],
                "reason_code": "MODEL_TEXT_NEGATIVE_ONLY",
            },
            "ROLE-11": {
                "source_id": "source-b",
                "production_positive": False,
                "assurance": "PROVISIONAL",
                "allowed_uses": ["AUDIT", "EXPERIMENTAL_POSITIVE_REVIEW"],
                "reason_code": "EXTERNAL_ATTESTATION_REQUIRED",
            },
            "ROLE-12": {
                "source_id": "source-c",
                "production_positive": False,
                "assurance": "PROVISIONAL",
                "allowed_uses": ["AUDIT", "EXPERIMENTAL_POSITIVE_REVIEW"],
                "reason_code": "ORIGIN_UNKNOWN",
            },
            "ROLE-13": {
                "source_id": "source-d",
                "production_positive": False,
                "assurance": "NEGATIVE_ONLY",
                "allowed_uses": ["AUDIT", "NEGATIVE_GUARD"],
                "reason_code": "MODEL_ORIGIN_UNRESOLVED_NEGATIVE_ONLY",
            },
        }
        for atom_id, decision in expected.items():
            with self.subTest(atom_id=atom_id):
                case, _ = self.make_v2_case(
                    f"{atom_id}/source-provenance/v1",
                    output=json.dumps(decision, ensure_ascii=False),
                    include_generation=False,
                )
                report = self.audit_manifest(
                    self.v2_manifest(case), name=f"{atom_id.lower()}-policy-pass.json"
                )
                claim = report["cases"][0]["claims"][0]
                check = report["cases"][0]["oracle_suites"][0]["checks"][0]
                self.assertEqual("PASS", report["evidence_integrity_status"])
                self.assertEqual("E2", report["cases"][0]["evidence_level"])
                self.assertEqual("PASS", check["status"])
                self.assertEqual("NOT_EVALUATED", claim["status"])

    def test_source_provenance_self_report_cannot_override_hidden_policy(self) -> None:
        forged = {
            "source_id": "source-b",
            "production_positive": True,
            "assurance": "PRODUCTION",
            "allowed_uses": ["PRODUCTION_POSITIVE"],
            "reason_code": "CALLER_VERIFIED",
        }
        case, _ = self.make_v2_case(
            "ROLE-11/source-provenance/v1",
            output=json.dumps(forged, ensure_ascii=False),
            include_generation=False,
        )
        report = self.audit_manifest(self.v2_manifest(case), name="role-11-forged.json")
        claim = report["cases"][0]["claims"][0]
        check = report["cases"][0]["oracle_suites"][0]["checks"][0]

        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("FAIL", check["status"])
        self.assertEqual("FAIL", claim["status"])

    def test_canonical_oracle_hash_changes_on_semantic_drift(self) -> None:
        payload = json.loads(ORACLE.read_text(encoding="utf-8"))
        check = next(
            item for item in payload["checks"] if item["id"] == "json/LONG-01/include-manifest/v1"
        )
        original = auditor._canonical_definition_hash(check)
        drifted = copy.deepcopy(check)
        drifted["configuration"]["expected"].append("omitted-file.tex")
        self.assertNotEqual(original, auditor._canonical_definition_hash(drifted))

    def test_oracle_contract_binding_drift_fails_closed(self) -> None:
        real_file_sha256 = auditor._file_sha256

        def drift_contract(path: Path) -> str:
            if path.resolve(strict=True) == CONTRACT.resolve(strict=True):
                return "0" * 64
            return real_file_sha256(path)

        with mock.patch.object(auditor, "_file_sha256", side_effect=drift_contract):
            with self.assertRaisesRegex(
                auditor.AuditError, "oracle catalog contract_binding is stale"
            ):
                self.oracle_catalog()

    def test_oracle_provenance_source_hash_drift_fails_closed(self) -> None:
        provenance_source = (
            SKILL / "references" / "corpus-action-sources.json"
        ).resolve(strict=True)
        real_file_sha256 = auditor._file_sha256

        def drift_one_source(path: Path) -> str:
            if path.resolve(strict=True) == provenance_source:
                return "0" * 64
            return real_file_sha256(path)

        with mock.patch.object(auditor, "_file_sha256", side_effect=drift_one_source):
            with self.assertRaisesRegex(auditor.AuditError, "provenance.*hash drift"):
                self.oracle_catalog()

    def test_artifact_skill_and_contract_hash_drift_invalidate_evidence(self) -> None:
        bindings = self.current_bindings()
        for field in (
            "skill_snapshot_sha256",
            "contract_sha256",
            "requirements_sha256",
            "oracle_catalog_sha256",
            "trust_policy_sha256",
        ):
            with self.subTest(binding=field):
                drifted = dict(bindings)
                drifted[field] = "0" * 64
                report = self.audit_manifest(
                    {
                        "schema_version": "humanize-generation-qualification-manifest/v1",
                        "bindings": drifted,
                        "cases": [],
                        "archived_failures": [],
                    },
                    name=f"{field}.json",
                )
                self.assertEqual("FAIL", report["evidence_integrity_status"])
                self.assertEqual(1, report["exit_code"])
                self.assertTrue(any(field in item for item in report["integrity_errors"]))

        input_descriptor, _ = self.write_artifact("drift-input.md", "输入正文。")
        output_descriptor, _ = self.write_artifact("drift-output.md", "输出正文。")
        input_descriptor["sha256"] = "f" * 64
        report = self.audit_manifest(
            {
                "schema_version": "humanize-generation-qualification-manifest/v1",
                "cases": [
                    {
                        "id": "ARTIFACT-DRIFT-CASE",
                        "artifacts": {
                            "input": input_descriptor,
                            "output": output_descriptor,
                        },
                        "assertions": [],
                        "claims": [],
                    }
                ],
                "archived_failures": [],
            },
            name="artifact-drift.json",
        )
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(any("SHA-256 mismatch" in item for item in report["integrity_errors"]))

    def test_self_attested_mode_01_false_positive_is_rejected(self) -> None:
        payload = {
            "schema_version": auditor.MANIFEST_V2_SCHEMA,
            "bindings": self.current_bindings(),
            "cases": [
                {
                    "id": "SELF-ATTESTED-MODE-01",
                    "assertions": [{"id": "MODE-01-A", "result": "PASS"}],
                    "claims": [
                        {
                            "claim_id": "MODE-01-C",
                            "atom_id": "MODE-01",
                            "assertion_ids": ["MODE-01-A"],
                        }
                    ],
                }
            ],
            "archived_failures": [],
        }
        report = self.audit_manifest(payload)
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertEqual(0, report["summary"]["atoms_pass"])
        self.assertTrue(
            any(
                "forbids caller-owned grading fields" in item
                for item in report["integrity_errors"]
            )
        )

    def test_v1_current_result_flip_never_contributes_pass(self) -> None:
        statuses = []
        for result in ("PASS", "FAIL"):
            payload = {
                "schema_version": "humanize-generation-qualification-manifest/v1",
                "cases": [
                    {
                        "id": f"LEGACY-CURRENT-{result}",
                        "assertions": [{"id": f"LEGACY-A-{result}", "result": result}],
                        "claims": [
                            {
                                "claim_id": f"LEGACY-C-{result}",
                                "atom_id": "MODE-02",
                                "assertion_ids": [f"LEGACY-A-{result}"],
                            }
                        ],
                    }
                ],
                "archived_failures": [],
            }
            report = self.audit_manifest(payload, name=f"legacy-{result}.json")
            self.assertEqual("FAIL", report["evidence_integrity_status"])
            self.assertTrue(report["cases"][0]["archived"])
            statuses.append(report["cases"][0]["claims"][0]["status"])
            self.assertEqual(0, report["summary"]["atoms_pass"])
        self.assertEqual(["NOT_EVALUATED", "NOT_EVALUATED"], statuses)

    def test_catalog_owned_protected_measurement_can_reach_e2(self) -> None:
        case, paths = self.make_v2_case(
            "PROTECTED/hash-zero/v1", include_generation=False
        )
        before_hashes = {role: sha256(path.read_bytes()) for role, path in paths.items()}
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("E2", report["cases"][0]["evidence_level"])
        self.assertEqual("PASS", report["cases"][0]["claims"][0]["status"])
        self.assertEqual(1, report["summary"]["atoms_pass"])
        checks = report["cases"][0]["oracle_suites"][0]["checks"]
        self.assertEqual(["measurement/PROTECTED/hash-zero/v1"], [x["check_id"] for x in checks])
        self.assertEqual(before_hashes, {role: sha256(path.read_bytes()) for role, path in paths.items()})

    def test_v2_rejects_result_expected_and_check_selection(self) -> None:
        for field, value in (
            ("result", "PASS"),
            ("expected", {"status": "PASS"}),
            ("check_ids", ["measurement/PROTECTED/hash-zero/v1"]),
        ):
            with self.subTest(field=field):
                case, _ = self.make_v2_case(
                    "PROTECTED/hash-zero/v1", include_generation=False
                )
                case["claims"][0][field] = value
                report = self.audit_manifest(
                    self.v2_manifest(case), name=f"forbidden-{field}.json"
                )
                self.assertEqual("FAIL", report["evidence_integrity_status"])
                self.assertEqual(0, report["summary"]["atoms_pass"])
                self.assertTrue(
                    any(field in item for item in report["integrity_errors"])
                )

    def test_fixture_atom_suite_and_catalog_drift_fail_closed(self) -> None:
        case, _ = self.make_v2_case(
            "PROTECTED/hash-zero/v1", include_generation=False
        )
        changed, _ = self.write_artifact("changed-input.md", "已替换的输入。")
        case["artifacts"]["input"] = changed
        report = self.audit_manifest(self.v2_manifest(case), name="fixture-drift.json")
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(any("fixture binding mismatch" in item for item in report["integrity_errors"]))

        case, _ = self.make_v2_case(
            "PROTECTED/hash-zero/v1", include_generation=False
        )
        case["claims"][0]["atom_id"] = "MODE-02"
        report = self.audit_manifest(self.v2_manifest(case), name="suite-drift.json")
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(any("atom/suite mismatch" in item for item in report["integrity_errors"]))

        case, _ = self.make_v2_case(
            "PROTECTED/hash-zero/v1", include_generation=False
        )
        case["claims"][0]["oracle_suite_id"] = "PROTECTED/easier-omitted-check/v1"
        report = self.audit_manifest(self.v2_manifest(case), name="unknown-suite.json")
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(any("unknown oracle suite" in item for item in report["integrity_errors"]))

        case, _ = self.make_v2_case(
            "PROTECTED/hash-zero/v1", include_generation=False
        )
        payload = self.v2_manifest(case)
        payload["bindings"]["oracle_catalog_sha256"] = "0" * 64
        report = self.audit_manifest(payload, name="catalog-drift.json")
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(any("oracle_catalog_sha256" in item for item in report["integrity_errors"]))

    def test_subjective_pass_cannot_override_deterministic_fail(self) -> None:
        input_text = (
            SKILL
            / "references"
            / "generation-qualification-fixtures"
            / "v1"
            / "path-05-input.md"
        ).read_text(encoding="utf-8")
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output=input_text,
            isolation_verified=False,
            add_passing_review=True,
        )
        report = self.audit_manifest(self.v2_manifest(case))
        claim = report["cases"][0]["claims"][0]
        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("E2", report["cases"][0]["evidence_level"])
        self.assertEqual("FAIL", claim["deterministic_outcome"])
        self.assertEqual("NOT_EVALUATED", claim["review_outcome"])
        self.assertTrue(claim["model_behavior_evaluated"])
        self.assertEqual("CATALOG_EVALUATED", claim["deterministic_outcome_attribution"])
        self.assertEqual("FAIL", claim["status"])
        review = report["cases"][0]["oracle_suites"][0]["reviews"]["reviews"][0][
            "reviews"
        ][0]
        self.assertEqual("PASS", review["declared_outcome"])
        self.assertFalse(review["qualification_eligible"])

    def test_deterministic_fail_beats_another_missing_check(self) -> None:
        input_text = (
            SKILL
            / "references"
            / "generation-qualification-fixtures"
            / "v1"
            / "path-05-input.md"
        ).read_text(encoding="utf-8")
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output=input_text,
            include_generation=False,
        )
        del case["artifacts"]["context"]
        report = self.audit_manifest(self.v2_manifest(case))
        claim = report["cases"][0]["claims"][0]
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertEqual("FAIL", claim["deterministic_outcome"])
        self.assertEqual("FAIL", claim["status"])

    def test_infrastructure_invalid_generation_does_not_become_model_failure(self) -> None:
        input_text = (
            SKILL
            / "references"
            / "generation-qualification-fixtures"
            / "v1"
            / "path-05-input.md"
        ).read_text(encoding="utf-8")
        for missing_artifact in ("raw_run", "run_seal", "runner_receipt"):
            with self.subTest(missing_artifact=missing_artifact):
                case, _ = self.make_v2_case(
                    "PATH-05/positive/v1",
                    output=input_text,
                    isolation_verified=False,
                )
                del case["artifacts"][missing_artifact]

                report = self.audit_manifest(self.v2_manifest(case))
                claim = report["cases"][0]["claims"][0]
                atom = next(
                    item
                    for item in report["atoms"]
                    if item["atom_id"] == "PATH-05/positive"
                )

                self.assertEqual("FAIL", report["evidence_integrity_status"])
                self.assertEqual("NOT_EVALUATED", report["qualification_status"])
                self.assertEqual("FAIL", claim["deterministic_outcome"])
                self.assertEqual(
                    "UNATTRIBUTED_INFRA_INVALID",
                    claim["deterministic_outcome_attribution"],
                )
                self.assertFalse(claim["model_behavior_evaluated"])
                self.assertFalse(
                    report["cases"][0]["blind_forward"][
                        "model_behavior_evaluated"
                    ]
                )
                self.assertEqual("NOT_EVALUATED", claim["status"])
                self.assertIn("infrastructure-invalid", claim["reason"])
                self.assertEqual("NOT_EVALUATED", atom["status"])
                self.assertNotIn("PATH-05/positive", report["failed_atoms"])

    def test_full_skill_visible_generation_is_capped_at_e2(self) -> None:
        output = (
            "第一组数据保持稳定，波动幅度较小。\n\n"
            "第二组数据逐步上升。峰值出现在末段。\n\n"
            "第三组数据先降。随后上升。转折发生在中段。"
        )
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output=output,
            isolation_verified=False,
            add_passing_review=True,
        )
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("PASS", report["evidence_integrity_status"])
        self.assertEqual("E2", report["cases"][0]["evidence_level"])
        self.assertEqual("NOT_EVALUATED", report["cases"][0]["claims"][0]["status"])
        self.assertEqual("E2", report["cases"][0]["blind_forward"]["evidence_cap"])
        self.assertFalse(report["trust_boundary"]["oracle_catalog_binding_is_blindness_proof"])

    def test_caller_cannot_self_assert_harness_verified_isolation(self) -> None:
        output = (
            "第一组数据保持稳定，波动幅度较小。\n\n"
            "第二组数据逐步上升。峰值出现在末段。\n\n"
            "第三组数据先降。随后上升。转折发生在中段。"
        )
        case, paths = self.make_v2_case(
            "PATH-05/positive/v1",
            output=output,
            isolation_verified=True,
        )
        artifacts = {
            key: self.artifact_object(key, path)
            for key, path in paths.items()
        }
        errors: list[str] = []
        valid, state = auditor._blind_forward_state(
            case,
            artifacts,
            True,
            self.current_bindings(),
            set(),
            "V2-CASE-001",
            errors,
            auditor._load_trust_policy(SKILL),
            self.current_projection(),
        )
        self.assertFalse(valid)
        self.assertEqual("E2", state["evidence_cap"])
        self.assertEqual("REJECTED_UNTRUSTED_ISOLATION_CLAIM", state["verification_state"])
        self.assertTrue(any("cannot self-assert" in item for item in errors))
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertEqual(0, report["summary"]["atoms_pass"])
        self.assertTrue(
            any("cannot self-assert" in item for item in report["integrity_errors"])
        )

    def test_current_projection_is_reproduced_and_reported_at_e2_only(self) -> None:
        report = self.audit_manifest(
            {
                "schema_version": auditor.MANIFEST_V2_SCHEMA,
                "bindings": self.current_bindings(),
                "cases": [],
                "archived_failures": [],
            }
        )
        projection = report["generator_projection"]
        self.assertRegex(projection["manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(projection["tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(projection["evaluation_surface_present_in_projection"])
        self.assertFalse(projection["host_excluded_roots_unreachable_verified"])
        self.assertEqual("E2", projection["evidence_cap"])

    def test_missing_projection_evidence_is_integrity_failure(self) -> None:
        output = (
            "第一组数据保持稳定，波动幅度较小。\n\n"
            "第二组数据逐步上升。峰值出现在末段。\n\n"
            "第三组数据先降。随后上升。转折发生在中段。"
        )
        for missing in (
            "projection_manifest",
            "runner_receipt",
            "run_seal",
            "public_prompt",
        ):
            with self.subTest(missing=missing):
                case, _ = self.make_v2_case("PATH-05/positive/v1", output=output)
                del case["artifacts"][missing]
                report = self.audit_manifest(
                    self.v2_manifest(case), name=f"missing-{missing}.json"
                )
                self.assertEqual("FAIL", report["evidence_integrity_status"])
                self.assertEqual(0, report["summary"]["atoms_pass"])
                self.assertTrue(
                    any(
                        "MISSING_PROJECTION_EVIDENCE" in item
                        for item in report["integrity_errors"]
                    )
                )

    def test_projection_manifest_drift_is_integrity_failure(self) -> None:
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output="第一组稳定。\n\n第二组上升。\n\n第三组先降后升。",
        )
        self.rewrite_case_artifact(
            case,
            "projection_manifest",
            {"schema_version": auditor.PROJECTION_MANIFEST_SCHEMA},
        )
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any("PROJECTION_BINDING_MISMATCH" in item for item in report["integrity_errors"])
        )

    def test_run_record_projection_claim_is_recomputed_not_trusted(self) -> None:
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output="第一组稳定。\n\n第二组上升。\n\n第三组先降后升。",
        )
        raw_path = self.root / case["artifacts"]["raw_run"]["path"]
        record = json.loads(raw_path.read_text(encoding="utf-8"))
        record["generator_projection"]["tree_sha256"] = "0" * 64
        digest = self.rewrite_case_artifact(case, "raw_run", record)
        case["generation"]["raw_run_sha256"] = digest
        self.sync_run_seal(case)
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any("run record projection" in item for item in report["integrity_errors"])
        )

    def test_runner_receipt_projection_claim_is_recomputed_not_trusted(self) -> None:
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output="第一组稳定。\n\n第二组上升。\n\n第三组先降后升。",
        )
        receipt_path = self.root / case["artifacts"]["runner_receipt"]["path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["generator_projection"]["tree_sha256"] = "0" * 64
        receipt_digest = self.rewrite_case_artifact(case, "runner_receipt", receipt)
        raw_path = self.root / case["artifacts"]["raw_run"]["path"]
        record = json.loads(raw_path.read_text(encoding="utf-8"))
        record["runner_receipt_sha256"] = receipt_digest
        raw_digest = self.rewrite_case_artifact(case, "raw_run", record)
        case["generation"]["raw_run_sha256"] = raw_digest
        self.sync_run_seal(case)
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any("runner receipt projection" in item for item in report["integrity_errors"])
        )

    def test_contradictory_isolation_fields_are_rejected(self) -> None:
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output="第一组稳定。\n\n第二组上升。\n\n第三组先降后升。",
        )
        raw_path = self.root / case["artifacts"]["raw_run"]["path"]
        record = json.loads(raw_path.read_text(encoding="utf-8"))
        record["filesystem_isolation_verified"] = True
        record["oracle_catalog_visible_to_generator"] = None
        digest = self.rewrite_case_artifact(case, "raw_run", record)
        case["generation"]["raw_run_sha256"] = digest
        self.sync_run_seal(case)
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any("internally contradictory" in item for item in report["integrity_errors"])
        )

    def test_run_record_catalog_binding_drift_is_rejected(self) -> None:
        output = (
            "第一组数据保持稳定，波动幅度较小。\n\n"
            "第二组数据逐步上升。峰值出现在末段。\n\n"
            "第三组数据先降。随后上升。转折发生在中段。"
        )
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output=output,
            corrupt_run_binding_field="oracle_catalog_sha256",
        )
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any(
                "oracle catalog" in item
                for item in report["integrity_errors"]
            )
        )

    def test_run_record_must_bind_public_input_prompt_context_seal(self) -> None:
        output = (
            "第一组数据保持稳定，波动幅度较小。\n\n"
            "第二组数据逐步上升。峰值出现在末段。\n\n"
            "第三组数据先降。随后上升。转折发生在中段。"
        )
        case, _ = self.make_v2_case(
            "PATH-05/positive/v1",
            output=output,
            omit_public_seal=True,
        )
        report = self.audit_manifest(self.v2_manifest(case))
        self.assertEqual("FAIL", report["evidence_integrity_status"])
        self.assertTrue(
            any(
                "public_artifact_sha256" in item
                for item in report["integrity_errors"]
            )
        )

    def test_only_complete_synthetic_atom_matrix_can_pass(self) -> None:
        complete = [
            {"atom_id": "A", "severity": "P0", "status": "PASS"},
            {"atom_id": "B", "severity": "P1", "status": "PASS"},
        ]
        self.assertEqual(("PASS", "PASS", 0), auditor._aggregate_qualification(complete, []))
        incomplete = [complete[0], {**complete[1], "status": "NOT_EVALUATED"}]
        self.assertEqual(
            ("PASS", "NOT_EVALUATED", 2),
            auditor._aggregate_qualification(incomplete, []),
        )
        failed = [complete[0], {**complete[1], "status": "FAIL"}]
        self.assertEqual(("PASS", "FAIL", 1), auditor._aggregate_qualification(failed, []))
        self.assertEqual(
            ("FAIL", "NOT_EVALUATED", 1),
            auditor._aggregate_qualification(complete, ["hash drift"]),
        )

    def blind_review_material(self) -> tuple[dict[str, object], dict, dict[str, str]]:
        _, rubric_path = self.write_artifact("rubric.md", "匿名文风盲评量表")
        _, bundle_path = self.write_artifact("bundle.json", '{"candidate":"A"}')
        artifacts = {
            "rubric": self.artifact_object("rubric", rubric_path),
            "bundle": self.artifact_object("bundle", bundle_path),
        }
        current = self.current_bindings()
        forward = {
            "valid": True,
            "run_id": "BLIND-RUN-001",
            "raw_run_sha256": "1" * 64,
            "artifact_sha256": {
                "input": "2" * 64,
                "output": "3" * 64,
                "prompt": "4" * 64,
                "context": "5" * 64,
            },
        }
        return artifacts, forward, current

    def make_ballot(
        self,
        ballot_id: str,
        reviewer_hash: str,
        generation_binding: dict,
        artifacts: dict[str, object],
        *,
        kind: str = "HUMAN",
    ) -> dict:
        return {
            "ballot_id": ballot_id,
            "reviewer_kind": kind,
            "reviewer_id_sha256": reviewer_hash,
            "identity_verified": False,
            "attestation_status": "CALLER_ASSERTED_HUMAN_REVIEW",
            "rubric_sha256": artifacts["rubric"].actual_sha256,
            "bundle_sha256": artifacts["bundle"].actual_sha256,
            "generation_binding": generation_binding,
            "result": "PASS",
        }

    def test_agent_and_duplicate_human_ballots_do_not_satisfy_e4(self) -> None:
        artifacts, forward, current = self.blind_review_material()
        generation_binding = {
            "run_id": forward["run_id"],
            "run_record_sha256": forward["raw_run_sha256"],
            "output_sha256": forward["artifact_sha256"]["output"],
            "prompt_sha256": forward["artifact_sha256"]["prompt"],
            "context_sha256": forward["artifact_sha256"]["context"],
            "skill_snapshot_sha256": current["skill_snapshot_sha256"],
            "oracle_catalog_sha256": current["oracle_catalog_sha256"],
        }
        for label, first_kind, first_hash, second_hash, expected_error in (
            ("agent", "AGENT", "a" * 64, "b" * 64, "reviewer_kind must be HUMAN"),
            ("duplicate", "HUMAN", "c" * 64, "c" * 64, "reuses a reviewer identity"),
        ):
            with self.subTest(label=label):
                case = {
                    "blind_review": {
                        "rubric_artifact": "rubric",
                        "bundle_artifact": "bundle",
                        "generation_binding": generation_binding,
                        "ballots": [
                            self.make_ballot(
                                f"{label}-ballot-1",
                                first_hash,
                                generation_binding,
                                artifacts,
                                kind=first_kind,
                            ),
                            self.make_ballot(
                                f"{label}-ballot-2",
                                second_hash,
                                generation_binding,
                                artifacts,
                            ),
                        ],
                    }
                }
                errors: list[str] = []
                valid, _passed, state, _reviewers = auditor._blind_review_state(
                    case,
                    artifacts,
                    True,
                    forward,
                    current,
                    set(),
                    label,
                    errors,
                )
                self.assertFalse(valid)
                self.assertFalse(state["valid"])
                self.assertFalse(state["identity_verified"])
                self.assertTrue(any(expected_error in item for item in errors))

    def test_e4_generation_binding_mismatch_is_rejected(self) -> None:
        artifacts, forward, current = self.blind_review_material()
        correct = {
            "run_id": forward["run_id"],
            "run_record_sha256": forward["raw_run_sha256"],
            "output_sha256": forward["artifact_sha256"]["output"],
            "prompt_sha256": forward["artifact_sha256"]["prompt"],
            "context_sha256": forward["artifact_sha256"]["context"],
            "skill_snapshot_sha256": current["skill_snapshot_sha256"],
            "oracle_catalog_sha256": current["oracle_catalog_sha256"],
        }
        wrong = {**correct, "output_sha256": "f" * 64}
        case = {
            "blind_review": {
                "rubric_artifact": "rubric",
                "bundle_artifact": "bundle",
                "generation_binding": wrong,
                "ballots": [
                    self.make_ballot("binding-ballot-1", "d" * 64, wrong, artifacts),
                    self.make_ballot("binding-ballot-2", "e" * 64, wrong, artifacts),
                ],
            }
        }
        errors: list[str] = []
        valid, _passed, _state, _reviewers = auditor._blind_review_state(
            case, artifacts, True, forward, current, set(), "binding", errors
        )
        self.assertFalse(valid)
        self.assertTrue(any("not bound to the current generation run" in item for item in errors))

    def test_two_bound_human_ballots_reach_e4_without_claiming_verified_identity(self) -> None:
        artifacts, forward, current = self.blind_review_material()
        generation_binding = {
            "run_id": forward["run_id"],
            "run_record_sha256": forward["raw_run_sha256"],
            "output_sha256": forward["artifact_sha256"]["output"],
            "prompt_sha256": forward["artifact_sha256"]["prompt"],
            "context_sha256": forward["artifact_sha256"]["context"],
            "skill_snapshot_sha256": current["skill_snapshot_sha256"],
            "oracle_catalog_sha256": current["oracle_catalog_sha256"],
        }
        case = {
            "blind_review": {
                "rubric_artifact": "rubric",
                "bundle_artifact": "bundle",
                "generation_binding": generation_binding,
                "ballots": [
                    self.make_ballot("valid-ballot-1", "6" * 64, generation_binding, artifacts),
                    self.make_ballot("valid-ballot-2", "7" * 64, generation_binding, artifacts),
                ],
            }
        }
        errors: list[str] = []
        valid, passed, state, reviewers = auditor._blind_review_state(
            case, artifacts, True, forward, current, set(), "valid", errors
        )
        self.assertTrue(valid)
        self.assertTrue(passed)
        self.assertEqual(set(), set(errors))
        self.assertEqual(2, len(reviewers))
        self.assertFalse(state["identity_verified"])

    def make_bound_run_artifacts(
        self,
        prefix: str,
        run_id: str,
        bindings: dict[str, str],
        shared: dict[str, object],
        output_key: str,
        output_path: Path,
    ) -> tuple[dict[str, object], dict]:
        role_artifacts = {
            "input": shared["input"],
            "output": self.artifact_object(output_key, output_path),
            "prompt": shared["prompt"],
            "context": shared["context"],
        }
        record = {
            "schema_version": auditor.LEGACY_GENERATION_RUN_RECORD_SCHEMA,
            "run_id": run_id,
            "fresh_context": True,
            "blindness_attestation": auditor.BLINDNESS_ATTESTATION,
            "artifact_sha256": {
                role: artifact.actual_sha256 for role, artifact in role_artifacts.items()
            },
            "qualification_bindings": bindings,
        }
        _, record_path = self.write_artifact(
            f"{prefix}-raw.json", json.dumps(record, ensure_ascii=False, sort_keys=True)
        )
        raw_key = f"{prefix}_raw"
        raw_artifact = self.artifact_object(raw_key, record_path)
        entry = {
            "run_record_artifact": raw_key,
            "input_artifact": role_artifacts["input"].key,
            "output_artifact": output_key,
            "prompt_artifact": role_artifacts["prompt"].key,
            "context_artifact": role_artifacts["context"].key,
        }
        artifact_map = {artifact.key: artifact for artifact in role_artifacts.values()}
        artifact_map[raw_key] = raw_artifact
        return artifact_map, entry

    def test_route_stability_rejects_copied_run_provenance(self) -> None:
        bindings = self.current_bindings()
        _, input_path = self.write_artifact("route-input.md", "同一输入")
        _, prompt_path = self.write_artifact("route-prompt.txt", "同一路由任务")
        _, context_path = self.write_artifact("route-context.json", "{}")
        shared = {
            "input": self.artifact_object("route_input", input_path),
            "prompt": self.artifact_object("route_prompt", prompt_path),
            "context": self.artifact_object("route_context", context_path),
        }
        artifacts = {artifact.key: artifact for artifact in shared.values()}
        runs = []
        copied_raw: bytes | None = None
        copied_hash: str | None = None
        for number in range(1, 4):
            _, output_path = self.write_artifact(f"route-output-{number}.md", "同一路由输出")
            output_key = f"route_output_{number}"
            role_artifacts, entry = self.make_bound_run_artifacts(
                f"route-{number}", "COPIED-ROUTE-RUN", bindings, shared, output_key, output_path
            )
            raw_artifact = role_artifacts[entry["run_record_artifact"]]
            if copied_raw is None:
                copied_raw = raw_artifact.raw
                copied_hash = raw_artifact.actual_sha256
            else:
                raw_artifact.path.write_bytes(copied_raw)
                raw_artifact = self.artifact_object(raw_artifact.key, raw_artifact.path)
                role_artifacts[raw_artifact.key] = raw_artifact
                self.assertEqual(copied_hash, raw_artifact.actual_sha256)
            artifacts.update(role_artifacts)
            observation = {
                "schema_version": auditor.ROUTE_OBSERVATION_SCHEMA,
                "run_id": "COPIED-ROUTE-RUN",
                "run_record_sha256": raw_artifact.actual_sha256,
                "oracle_catalog_sha256": bindings["oracle_catalog_sha256"],
                "scene": "RESEARCH",
                "roles": ["author"],
                "decisions": ["REWRITE"],
                "owners": ["unit-1"],
            }
            _, observation_path = self.write_artifact(
                f"route-observation-{number}.json",
                json.dumps(observation, ensure_ascii=False, sort_keys=True),
            )
            observation_key = f"route_observation_{number}"
            artifacts[observation_key] = self.artifact_object(observation_key, observation_path)
            entry["observation_artifact"] = observation_key
            runs.append(entry)
        result, state = auditor._route_stability_measurement(
            {
                "route_stability": {
                    "independence_attestation": auditor.INDEPENDENCE_ATTESTATION,
                    "runs": runs,
                }
            },
            artifacts,
            bindings,
            auditor._measurement_run_state(
                runs[0], artifacts, bindings, "route-negative-forward"
            )[1],
        )
        self.assertIsNone(result)
        self.assertEqual("NON_INDEPENDENT_RUNS", state["status"])

    def test_three_bound_distinct_route_runs_can_pass_stability_measurement(self) -> None:
        bindings = self.current_bindings()
        _, input_path = self.write_artifact("valid-route-input.md", "同一输入")
        _, prompt_path = self.write_artifact("valid-route-prompt.txt", "同一路由任务")
        _, context_path = self.write_artifact("valid-route-context.json", "{}")
        shared = {
            "input": self.artifact_object("valid_route_input", input_path),
            "prompt": self.artifact_object("valid_route_prompt", prompt_path),
            "context": self.artifact_object("valid_route_context", context_path),
        }
        artifacts = {artifact.key: artifact for artifact in shared.values()}
        runs = []
        for number in range(1, 4):
            _, output_path = self.write_artifact(
                f"valid-route-output-{number}.md", "稳定的路由输出"
            )
            output_key = f"valid_route_output_{number}"
            run_id = f"VALID-ROUTE-RUN-{number}"
            run_artifacts, entry = self.make_bound_run_artifacts(
                f"valid-route-{number}", run_id, bindings, shared, output_key, output_path
            )
            artifacts.update(run_artifacts)
            raw_artifact = artifacts[entry["run_record_artifact"]]
            observation = {
                "schema_version": auditor.ROUTE_OBSERVATION_SCHEMA,
                "run_id": run_id,
                "run_record_sha256": raw_artifact.actual_sha256,
                "oracle_catalog_sha256": bindings["oracle_catalog_sha256"],
                "scene": "RESEARCH",
                "roles": ["author"],
                "decisions": ["REWRITE"],
                "owners": ["unit-1"],
            }
            _, observation_path = self.write_artifact(
                f"valid-route-observation-{number}.json",
                json.dumps(observation, ensure_ascii=False, sort_keys=True),
            )
            observation_key = f"valid_route_observation_{number}"
            artifacts[observation_key] = self.artifact_object(observation_key, observation_path)
            entry["observation_artifact"] = observation_key
            runs.append(entry)
        result, state = auditor._route_stability_measurement(
            {
                "route_stability": {
                    "independence_attestation": auditor.INDEPENDENCE_ATTESTATION,
                    "runs": runs,
                }
            },
            artifacts,
            bindings,
            auditor._measurement_run_state(
                runs[0], artifacts, bindings, "route-positive-forward"
            )[1],
        )
        self.assertTrue(result)
        self.assertEqual("PASS", state["status"])
        self.assertEqual(3, len(set(state["run_ids"])))
        self.assertEqual(3, len(set(state["raw_run_sha256"])))

    def test_idempotency_rejects_copied_run_provenance(self) -> None:
        bindings = self.current_bindings()
        _, input_path = self.write_artifact("idem-input.md", "已经自然的正文。")
        _, output_path = self.write_artifact("idem-output.md", "已经自然的正文。")
        _, second_output_path = self.write_artifact("idem-output-2.md", "已经自然的正文。")
        _, prompt_path = self.write_artifact("idem-prompt.txt", "对输出再次执行相同文风任务")
        _, context_path = self.write_artifact("idem-context.json", "{}")
        shared = {
            "input": self.artifact_object("idem_input", input_path),
            "prompt": self.artifact_object("idem_prompt", prompt_path),
            "context": self.artifact_object("idem_context", context_path),
        }
        artifacts = {artifact.key: artifact for artifact in shared.values()}
        first_roles, first_entry = self.make_bound_run_artifacts(
            "idem-first",
            "COPIED-IDEM-RUN",
            bindings,
            shared,
            "idem_output",
            output_path,
        )
        first_raw = first_roles[first_entry["run_record_artifact"]]
        artifacts.update(first_roles)

        second_shared = {
            "input": self.artifact_object("idem_output", output_path),
            "prompt": shared["prompt"],
            "context": shared["context"],
        }
        second_roles, second_entry = self.make_bound_run_artifacts(
            "idem-second",
            "COPIED-IDEM-RUN",
            bindings,
            second_shared,
            "idem_output_2",
            second_output_path,
        )
        second_raw = second_roles[second_entry["run_record_artifact"]]
        second_raw.path.write_bytes(first_raw.raw)
        second_raw = self.artifact_object(second_raw.key, second_raw.path)
        second_roles[second_raw.key] = second_raw
        self.assertEqual(first_raw.actual_sha256, second_raw.actual_sha256)
        artifacts.update(second_roles)
        result, state = auditor._idempotency_measurement(
            {
                "idempotency": {
                    "independence_attestation": auditor.INDEPENDENCE_ATTESTATION,
                    "first": first_entry,
                    "second": second_entry,
                }
            },
            artifacts,
            bindings,
            auditor._measurement_run_state(
                first_entry, artifacts, bindings, "idempotency-negative-forward"
            )[1],
        )
        self.assertIsNone(result)
        self.assertEqual("NON_INDEPENDENT_RUNS", state["status"])

    def test_two_bound_distinct_runs_can_pass_idempotency_measurement(self) -> None:
        bindings = self.current_bindings()
        _, input_path = self.write_artifact("valid-idem-input.md", "值得注意的是，峰值稳定。")
        _, output_path = self.write_artifact("valid-idem-output.md", "峰值稳定。")
        _, second_output_path = self.write_artifact("valid-idem-output-2.md", "峰值稳定。")
        _, prompt_path = self.write_artifact("valid-idem-prompt.txt", "执行相同文风任务")
        _, context_path = self.write_artifact("valid-idem-context.json", "{}")
        shared = {
            "input": self.artifact_object("valid_idem_input", input_path),
            "prompt": self.artifact_object("valid_idem_prompt", prompt_path),
            "context": self.artifact_object("valid_idem_context", context_path),
        }
        artifacts = {artifact.key: artifact for artifact in shared.values()}
        first_artifacts, first_entry = self.make_bound_run_artifacts(
            "valid-idem-first",
            "VALID-IDEM-RUN-1",
            bindings,
            shared,
            "valid_idem_output",
            output_path,
        )
        artifacts.update(first_artifacts)
        second_shared = {
            "input": self.artifact_object("valid_idem_output", output_path),
            "prompt": shared["prompt"],
            "context": shared["context"],
        }
        second_artifacts, second_entry = self.make_bound_run_artifacts(
            "valid-idem-second",
            "VALID-IDEM-RUN-2",
            bindings,
            second_shared,
            "valid_idem_output_2",
            second_output_path,
        )
        artifacts.update(second_artifacts)
        result, state = auditor._idempotency_measurement(
            {
                "idempotency": {
                    "independence_attestation": auditor.INDEPENDENCE_ATTESTATION,
                    "first": first_entry,
                    "second": second_entry,
                }
            },
            artifacts,
            bindings,
            auditor._measurement_run_state(
                first_entry, artifacts, bindings, "idempotency-positive-forward"
            )[1],
        )
        self.assertTrue(result)
        self.assertEqual("PASS", state["status"])
        self.assertNotEqual(state["first_run_id"], state["second_run_id"])
        self.assertNotEqual(state["first_raw_run_sha256"], state["second_raw_run_sha256"])


if __name__ == "__main__":
    unittest.main()
