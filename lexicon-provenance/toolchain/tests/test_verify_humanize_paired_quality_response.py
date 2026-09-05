import base64
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
SCRIPT = SKILL / "scripts" / "verify_humanize_paired_quality_response.py"
SPEC = importlib.util.spec_from_file_location("verify_paired_quality", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class PairedQualityVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parent / "_sandbox_tmp"
        )
        self.root = Path(self.temp.name)
        self.before = self.root / "before.md"
        self.after = self.root / "after.md"
        self.before.write_text("值得注意的是，峰值出现在高温组。\n", encoding="utf-8")
        self.after.write_text("峰值出现在高温组。\n", encoding="utf-8")
        self.request_path = self.root / "request.json"
        self.challenge_path = self.root / "challenge.json"
        self.response_path = self.root / "response.jws"
        self.review_record_path = self.root / "review-record.json"
        self.keyset_path = self.root / "keyset.json"
        self.anchor_path = self.root / "anchor.json"
        self.redemption_ledger_path = self.root / "redemption-ledger.json"
        self.now = 1_000_000
        self.private = Ed25519PrivateKey.generate()
        self.request = self._write_request()
        self.challenge = self._write_challenge()
        self._write_keyset_and_anchor()
        self._write_review_record()
        self._write_response()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_request(self) -> dict:
        before_hash = verifier._sha256(self.before.read_bytes())
        after_hash = verifier._sha256(self.after.read_bytes())
        change = verifier._changed_line_records(
            self.before.read_bytes().decode("utf-8"),
            self.after.read_bytes().decode("utf-8"),
        )[0]
        body = {
            "schema": verifier.REQUEST_SCHEMA,
            "status": "PENDING_EXTERNAL_REVIEW",
            "artifact": {"before_sha256": before_hash, "after_sha256": after_hash},
            "validation_context": {
                "mode": "REWRITE", "decision": "REWRITE", "scene": "RESEARCH",
                "document_format": "markdown", "document_scope": "DOCUMENT",
                "mechanical_validation_status": "PASS",
            },
            "policy_hashes": verifier._current_policy_hashes(),
            "changes": [change],
            "review_contract": {
                "required_per_change_verdicts": ["ACCEPT", "REVISE", "REVERT"],
                "required_dimensions": list(verifier.DIMENSIONS),
                "empty_or_generic_benefit_is_clearance": False,
                "local_model_or_caller_assertion_is_clearance": False,
                "validator_pass_is_quality_clearance": False,
            },
            "limitations": {
                "academic_correctness": "NOT_EVALUATED",
                "authorship": "NOT_EVALUATED",
                "quality_clearance_granted": False,
            },
        }
        request = {**body, "request_sha256": verifier._sha256(verifier._canonical_json(body))}
        self.request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        return request

    def _write_challenge(self) -> dict:
        body = {
            "schema": verifier.CHALLENGE_SCHEMA,
            "challenge_id": b64(b"c" * 32),
            "request_sha256": self.request["request_sha256"],
            "subject_binding": {
                "kind": "SINGLE_DOCUMENT",
                "before_sha256": self.request["artifact"]["before_sha256"],
                "after_sha256": self.request["artifact"]["after_sha256"],
                "scene": "RESEARCH",
                "document_scope": "DOCUMENT",
            },
            "issued_at": self.now - 30,
            "expires_at": self.now + 3600,
        }
        challenge = {**body, "challenge_sha256": verifier._sha256(verifier._canonical_json(body))}
        self.challenge_path.write_text(json.dumps(challenge, ensure_ascii=False), encoding="utf-8")
        return challenge

    def _write_keyset_and_anchor(self) -> None:
        public = self.private.public_key().public_bytes_raw()
        keyset = {
            "schema": verifier.KEYSET_SCHEMA,
            "sequence": 1,
            "issued_at": self.now - 100,
            "next_update": self.now + 3600,
            "issuer": verifier.EXPECTED_ISSUER,
            "audience": verifier.EXPECTED_AUDIENCE,
            "keys": [{
                "kid": "pq-test", "alg": "EdDSA", "public_key": b64(public),
                "not_before": self.now - 100, "not_after": self.now + 3600,
                "status": "ACTIVE", "usages": ["paired-quality-clearance"],
            }],
            "revocations": [],
        }
        keyset_raw = json.dumps(keyset, ensure_ascii=False).encode("utf-8")
        self.keyset_path.write_bytes(keyset_raw)
        anchor = {
            "schema": verifier.ANCHOR_SCHEMA,
            "keyset_sha256": verifier._sha256(keyset_raw),
            "sequence": 1,
            "issuer": verifier.EXPECTED_ISSUER,
            "audience": verifier.EXPECTED_AUDIENCE,
        }
        self.anchor_path.write_text(json.dumps(anchor), encoding="utf-8")

    def _write_review_record(self) -> None:
        decision = self.request["validation_context"]["decision"]
        target = (
            "NO_CHANGE"
            if decision == "NO_CHANGE"
            else self.request["changes"][0]["change_id"]
        )
        record = {
            "schema": verifier.REVIEW_RECORD_SCHEMA,
            "request_sha256": self.request["request_sha256"],
            "challenge_sha256": self.challenge["challenge_sha256"],
            "response_id": b64(b"r" * 32),
            "items": [{
                "target": target,
                "problem_span": "原句开头使用空重点提示壳",
                "reading_effect": "提示壳推迟了峰值结果的直接出现",
                "decision_rationale": "删除提示壳后主张未变且信息进入更直接",
            }],
        }
        self.review_record_path.write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )

    def _write_response(self) -> None:
        target = (
            "NO_CHANGE"
            if self.request["validation_context"]["decision"] == "NO_CHANGE"
            else self.request["changes"][0]["change_id"]
        )
        review = {"target": target, "verdict": "ACCEPT"}
        review.update({
            dimension: "PASS"
            for dimension in self.request["review_contract"]["required_dimensions"]
        })
        body = {
            "schema": verifier.RESPONSE_SCHEMA,
            "iss": verifier.EXPECTED_ISSUER,
            "aud": verifier.EXPECTED_AUDIENCE,
            "response_id": b64(b"r" * 32),
            "challenge_id": self.challenge["challenge_id"],
            "challenge_sha256": self.challenge["challenge_sha256"],
            "request_sha256": self.request["request_sha256"],
            "review_contract_sha256": verifier._sha256(verifier._canonical_json(self.request["review_contract"])),
            "review_items": [review],
            "overall_verdict": "CLEAR",
            "review_record_sha256": verifier._sha256(self.review_record_path.read_bytes()),
            "issued_at": self.now,
            "not_before": self.now,
            "expires_at": self.now + 1800,
            "trust_epoch": 1,
        }
        header = {"alg": "EdDSA", "kid": "pq-test", "typ": verifier.EXPECTED_TYP}
        protected = b64(verifier._canonical_json(header))
        payload = b64(verifier._canonical_json(body))
        signing_input = f"{protected}.{payload}".encode("ascii")
        self.response_path.write_text(f"{protected}.{payload}.{b64(self.private.sign(signing_input))}", encoding="ascii")

    def _commit_request_body(self, body: dict) -> None:
        self.request = {
            **body,
            "request_sha256": verifier._sha256(verifier._canonical_json(body)),
        }
        self.request_path.write_text(
            json.dumps(self.request, ensure_ascii=False), encoding="utf-8"
        )
        self.challenge = self._write_challenge()
        self._write_review_record()
        self._write_response()

    def _configure_template_field_request(self) -> None:
        before_line = "用词建议：避免空泛提示。"
        after_line = "用词建议：删去空泛提示。"
        before_payload = "避免空泛提示。"
        after_payload = "删去空泛提示。"
        self.before.write_text(before_line + "\n", encoding="utf-8")
        self.after.write_text(after_line + "\n", encoding="utf-8")
        change = verifier._changed_line_records(
            self.before.read_bytes().decode("utf-8"),
            self.after.read_bytes().decode("utf-8"),
        )[0]
        template_field_change = {
            "code": "TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED",
            "severity": "info",
            "change_id": change["change_id"],
            "field_label": "用词建议",
            "source_role": verifier.TEMPLATE_FIELD_SOURCE_ROLE,
            "payload_role": verifier.TEMPLATE_FIELD_LABEL_ROLES["用词建议"],
            "source_line": 1,
            "after_line": 1,
            "authorization_status": "AUTHORIZED_PAYLOAD_ONLY",
            "permission": verifier.TEMPLATE_FIELD_PERMISSION,
            "authorization_reason": "第1行用词建议字段仅调整载荷措辞并保持字段职责",
            "change_types": [],
            "before_span": {
                "line": 1,
                "payload_sha256": verifier._sha256(before_payload.encode("utf-8")),
                "line_sha256": verifier._sha256(before_line.encode("utf-8")),
            },
            "after_span": {
                "line": 1,
                "payload_sha256": verifier._sha256(after_payload.encode("utf-8")),
                "line_sha256": verifier._sha256(after_line.encode("utf-8")),
            },
            "local_clearance_supported": False,
        }
        body = {
            "schema": verifier.REQUEST_SCHEMA,
            "status": "PENDING_EXTERNAL_REVIEW",
            "artifact": {
                "before_sha256": verifier._sha256(self.before.read_bytes()),
                "after_sha256": verifier._sha256(self.after.read_bytes()),
            },
            "validation_context": {
                "mode": "REWRITE",
                "decision": "REWRITE",
                "scene": "RESEARCH",
                "document_format": "markdown",
                "document_scope": "DOCUMENT",
                "mechanical_validation_status": "PASS",
            },
            "policy_hashes": verifier._current_policy_hashes(),
            "changes": [change],
            "template_field_changes": [template_field_change],
            "review_contract": {
                "required_per_change_verdicts": ["ACCEPT", "REVISE", "REVERT"],
                "required_dimensions": list(verifier.TEMPLATE_FIELD_AWARE_DIMENSIONS),
                "empty_or_generic_benefit_is_clearance": False,
                "local_model_or_caller_assertion_is_clearance": False,
                "validator_pass_is_quality_clearance": False,
            },
            "limitations": {
                "academic_correctness": "NOT_EVALUATED",
                "authorship": "NOT_EVALUATED",
                "quality_clearance_granted": False,
            },
        }
        self._commit_request_body(body)

    def _mutate_request(self, mutate) -> None:
        body = json.loads(json.dumps(self.request, ensure_ascii=False))
        body.pop("request_sha256")
        mutate(body)
        self._commit_request_body(body)

    def _signed_response(
        self,
        name: str,
        *,
        payload_change=None,
        header_change=None,
    ) -> Path:
        protected_segment, payload_segment, _ = self.response_path.read_text(encoding="ascii").split(".")
        header = json.loads(base64.urlsafe_b64decode(protected_segment + "=="))
        payload = json.loads(base64.urlsafe_b64decode(payload_segment + "=="))
        if header_change is not None:
            header_change(header)
        if payload_change is not None:
            payload_change(payload)
        protected_segment = b64(verifier._canonical_json(header))
        payload_segment = b64(verifier._canonical_json(payload))
        signing_input = f"{protected_segment}.{payload_segment}".encode("ascii")
        path = self.root / name
        path.write_text(
            f"{protected_segment}.{payload_segment}.{b64(self.private.sign(signing_input))}",
            encoding="ascii",
        )
        return path

    def _rewrite_keyset(self, mutate) -> None:
        keyset = json.loads(self.keyset_path.read_text(encoding="utf-8"))
        mutate(keyset)
        raw = json.dumps(keyset, ensure_ascii=False).encode("utf-8")
        self.keyset_path.write_bytes(raw)
        anchor = json.loads(self.anchor_path.read_text(encoding="utf-8"))
        anchor["keyset_sha256"] = verifier._sha256(raw)
        anchor["sequence"] = keyset["sequence"]
        self.anchor_path.write_text(json.dumps(anchor), encoding="utf-8")

    def _configure_no_change(self) -> None:
        self.after.write_bytes(self.before.read_bytes())
        body = dict(self.request)
        body.pop("request_sha256")
        body["artifact"] = {
            "before_sha256": verifier._sha256(self.before.read_bytes()),
            "after_sha256": verifier._sha256(self.after.read_bytes()),
        }
        body["validation_context"] = dict(body["validation_context"])
        body["validation_context"]["decision"] = "NO_CHANGE"
        body["changes"] = []
        self.request = {
            **body,
            "request_sha256": verifier._sha256(verifier._canonical_json(body)),
        }
        self.request_path.write_text(json.dumps(self.request, ensure_ascii=False), encoding="utf-8")
        self.challenge = self._write_challenge()
        self._write_review_record()
        self._write_response()
        response = self._signed_response(
            "no-change-response.jws",
            payload_change=lambda payload: payload.update({
                "request_sha256": self.request["request_sha256"],
                "challenge_id": self.challenge["challenge_id"],
                "challenge_sha256": self.challenge["challenge_sha256"],
                "review_contract_sha256": verifier._sha256(
                    verifier._canonical_json(self.request["review_contract"])
                ),
                "review_items": [
                    {
                        "target": "NO_CHANGE",
                        "verdict": "ACCEPT",
                        **{
                            dimension: "PASS"
                            for dimension in self.request["review_contract"]["required_dimensions"]
                        },
                    }
                ],
            }),
        )
        self.response_path.write_bytes(response.read_bytes())

    def invoke(
        self,
        *,
        anchor: bool = True,
        response: Path | None = None,
        protected_anchor: bool = True,
        with_review_record: bool = True,
        review_record: Path | None = None,
        redemption_ledger: Path | None = None,
    ) -> dict:
        environment = {verifier.EXTERNAL_ANCHOR_ENV: str(self.anchor_path)} if anchor else {}
        protection = mock.patch.object(
            verifier, "_trust_anchor_is_protected", return_value=protected_anchor
        )
        with mock.patch.dict(os.environ, environment, clear=False), protection:
            if not anchor:
                os.environ.pop(verifier.EXTERNAL_ANCHOR_ENV, None)
            return verifier.verify(
                request_path=self.request_path,
                challenge_path=self.challenge_path,
                response_path=response or self.response_path,
                before_path=self.before,
                after_path=self.after,
                keyset_path=self.keyset_path,
                trust_anchor_path=self.anchor_path if anchor else None,
                review_record_path=(
                    review_record or self.review_record_path
                    if with_review_record
                    else None
                ),
                redemption_ledger_path=(redemption_ledger or self.redemption_ledger_path),
                now=self.now,
            )

    def test_externally_anchored_valid_response_grants_only_paired_clearance(self) -> None:
        result = self.invoke()
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertEqual("PASS", result["review_record_status"])
        self.assertEqual("NOT_EVALUATED", result["academic_correctness"])

    def test_legacy_v1_request_without_template_field_changes_remains_compatible(self) -> None:
        self.assertNotIn("template_field_changes", self.request)
        self.assertEqual(
            list(verifier.DIMENSIONS),
            self.request["review_contract"]["required_dimensions"],
        )
        result = self.invoke()
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_template_field_aware_v1_request_is_verified_but_never_locally_cleared(self) -> None:
        self._configure_template_field_request()
        result = self.invoke()
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["quality_clearance_granted"])

    def test_template_field_aware_empty_list_uses_the_new_exact_review_contract(self) -> None:
        self._mutate_request(
            lambda body: (
                body.update({"template_field_changes": []}),
                body["review_contract"].update({
                    "required_dimensions": list(
                        verifier.TEMPLATE_FIELD_AWARE_DIMENSIONS
                    )
                }),
            )
        )
        result = self.invoke()
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_template_field_scope_cannot_replace_the_external_quality_dimension(self) -> None:
        self._configure_template_field_request()
        response = self._signed_response(
            "missing-template-field-dimension.jws",
            payload_change=lambda payload: payload["review_items"][0].pop(
                verifier.TEMPLATE_FIELD_DIMENSION
            ),
        )
        result = self.invoke(response=response)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("QUALITY_REVIEW_INCOMPLETE", result["reasons"][0]["code"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse(result["quality_clearance_granted"])

    def test_template_field_changes_validate_exact_fields_and_authorization(self) -> None:
        cases = (
            (
                "unknown-field",
                lambda finding: finding.update({"unbound_scope_claim": True}),
                "UNKNOWN_FIELD",
            ),
            (
                "invalid-hash",
                lambda finding: finding["before_span"].update({
                    "payload_sha256": "A" * 64
                }),
                "INVALID_HASH",
            ),
            (
                "change-types",
                lambda finding: finding.update({
                    "change_types": ["NEGATION_SCOPE_CHANGED"]
                }),
                "INVALID_TEMPLATE_FIELD_CHANGE_TYPES",
            ),
            (
                "authorization",
                lambda finding: finding.update({"permission": "HEADER_AND_PAYLOAD"}),
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
            ),
            (
                "local-clearance",
                lambda finding: finding.update({"local_clearance_supported": True}),
                "INVALID_TEMPLATE_FIELD_AUTHORIZATION",
            ),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                self._configure_template_field_request()
                self._mutate_request(
                    lambda body, mutate=mutate: mutate(
                        body["template_field_changes"][0]
                    )
                )
                result = self.invoke()
                self.assertEqual("FAIL", result["status"])
                self.assertEqual(expected_code, result["reasons"][0]["code"])

    def test_template_field_hashes_are_replayed_against_current_artifacts(self) -> None:
        self._configure_template_field_request()
        self._mutate_request(
            lambda body: body["template_field_changes"][0]["before_span"].update({
                "payload_sha256": "a" * 64
            })
        )
        result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(
            "TEMPLATE_FIELD_ARTIFACT_MISMATCH",
            result["reasons"][0]["code"],
        )

    def test_unsafe_template_field_finding_cannot_be_declared_mechanical_pass(self) -> None:
        self._configure_template_field_request()

        def make_unauthorized(body: dict) -> None:
            finding = body["template_field_changes"][0]
            finding.update({
                "code": "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED",
                "severity": "warning",
                "authorization_status": "NOT_AUTHORIZED",
                "permission": None,
                "authorization_reason": None,
            })

        self._mutate_request(make_unauthorized)
        result = self.invoke()
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("MECHANICAL_GATE_BLOCKED", result["reasons"][0]["code"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_caller_provided_redemption_ledger_is_diagnostic_only(self) -> None:
        result = self.invoke(redemption_ledger=self.root / "missing" / "ledger.json")
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertEqual("CALLER_PROVIDED_DIAGNOSTIC_ONLY", result["redemption_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])
        self.assertFalse((self.root / "missing" / "ledger.json").exists())

    def test_caller_redemption_ledger_cannot_change_repeated_verification(self) -> None:
        first = self.invoke()
        self.assertEqual("REVIEW", first["status"])
        self.assertEqual("PASS", first["verification_status"])
        second = self.invoke()
        self.assertEqual("REVIEW", second["status"])
        self.assertEqual("PASS", second["verification_status"])
        self.assertEqual(first["paired_quality_gate_status"], second["paired_quality_gate_status"])
        self.assertFalse(self.redemption_ledger_path.exists())

    def test_missing_review_record_remains_review(self) -> None:
        result = self.invoke(with_review_record=False)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("MISSING_REVIEW_RECORD", result["reasons"][0]["code"])

    def test_review_record_hash_mismatch_is_fail(self) -> None:
        self.review_record_path.write_text("{}", encoding="utf-8")
        result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("REVIEW_RECORD_HASH_MISMATCH", result["reasons"][0]["code"])

    def test_request_drift_during_final_reread_is_fail(self) -> None:
        original = verifier._read_bytes
        reads = 0

        def racing_read(path, label):
            nonlocal reads
            if label == "request":
                reads += 1
                if reads == 2:
                    self.request_path.write_text("{}", encoding="utf-8")
            return original(path, label)

        with mock.patch.object(verifier, "_read_bytes", side_effect=racing_read):
            result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("EVIDENCE_DRIFT_AFTER_VERIFY", result["reasons"][0]["code"])

    def test_artifact_drift_during_final_reread_is_fail(self) -> None:
        original = verifier._read_bytes
        reads = 0

        def racing_read(path, label):
            nonlocal reads
            if label == "after artifact":
                reads += 1
                if reads == 3:
                    self.after.write_text("验签后发生漂移。\n", encoding="utf-8")
            return original(path, label)

        with mock.patch.object(verifier, "_read_bytes", side_effect=racing_read):
            result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("ARTIFACT_DRIFT_AFTER_VERIFY", result["reasons"][0]["code"])

    def test_generic_review_rationale_cannot_clear_quality_gate(self) -> None:
        record = json.loads(self.review_record_path.read_text(encoding="utf-8"))
        record["items"][0]["decision_rationale"] = "已人工审核"
        self.review_record_path.write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        response = self._signed_response(
            "generic-review-record.jws",
            payload_change=lambda payload: payload.update({
                "review_record_sha256": verifier._sha256(
                    self.review_record_path.read_bytes()
                )
            }),
        )
        result = self.invoke(response=response)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("GENERIC_REVIEW_RATIONALE", result["reasons"][0]["code"])

    def test_local_self_signed_anchor_cannot_grant_clearance(self) -> None:
        result = self.invoke(protected_anchor=False)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["cryptographic_signature_status"])
        self.assertEqual("UNPROTECTED_TRUST_ANCHOR", result["reasons"][0]["code"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_caller_owned_posix_anchor_is_not_a_protected_trust_root(self) -> None:
        caller_owned = mock.Mock(
            st_uid=1000,
            st_mode=stat.S_IFREG | 0o600,
        )
        with mock.patch.object(verifier.os, "name", "posix"), mock.patch.object(
            verifier.os, "getuid", return_value=1000, create=True
        ), mock.patch.object(type(self.anchor_path), "stat", return_value=caller_owned):
            protected = verifier._trust_anchor_is_protected(self.anchor_path)

        self.assertFalse(protected)
        result = self.invoke(protected_anchor=protected)
        self.assertEqual("REVIEW", result["status"])
        self.assertNotEqual("EXTERNALLY_ANCHORED", result["trust_root_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_valid_signature_without_external_anchor_is_review(self) -> None:
        result = self.invoke(anchor=False)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("PASS", result["cryptographic_signature_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_caller_supplied_anchor_without_launcher_boundary_is_review(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(verifier.EXTERNAL_ANCHOR_ENV, None)
            result = verifier.verify(
                request_path=self.request_path, challenge_path=self.challenge_path,
                response_path=self.response_path, before_path=self.before, after_path=self.after,
                keyset_path=self.keyset_path, trust_anchor_path=self.anchor_path, now=self.now,
            )
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("UNTRUSTED_LOCAL_KEYSET", result["trust_root_status"])
        self.assertFalse(result["paired_quality_clearance_granted"])

    def test_missing_challenge_is_review(self) -> None:
        result = verifier.verify(
            request_path=self.request_path, challenge_path=None, response_path=None,
            before_path=self.before, after_path=self.after, keyset_path=self.keyset_path,
            trust_anchor_path=self.anchor_path, now=self.now,
        )
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])

    def test_unsigned_response_is_review(self) -> None:
        unsigned = self.root / "unsigned.json"
        unsigned.write_text(
            json.dumps({"schema": verifier.RESPONSE_SCHEMA}), encoding="utf-8"
        )
        result = self.invoke(response=unsigned)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("UNSIGNED_RESPONSE", result["reasons"][0]["code"])

    def test_bad_signature_is_fail(self) -> None:
        bad = self.root / "bad.jws"
        raw = self.response_path.read_text(encoding="ascii")
        parts = raw.split(".")
        parts[2] = b64(b"x" * 64)
        bad.write_text(".".join(parts), encoding="ascii")
        result = self.invoke(response=bad)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("SIGNATURE_INVALID", result["reasons"][0]["code"])

    def test_artifact_drift_is_fail(self) -> None:
        self.after.write_text("发生漂移。\n", encoding="utf-8")
        result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("ARTIFACT_BINDING_MISMATCH", result["reasons"][0]["code"])

    def test_extra_target_is_fail(self) -> None:
        # The request is immutable; mutate the signed payload and re-sign it to
        # ensure target-set checks are independent of signature validity.
        raw = self.response_path.read_text(encoding="ascii").split(".")
        payload = json.loads(base64.urlsafe_b64decode(raw[1] + "=="), object_pairs_hook=dict)
        payload["review_items"][0]["target"] = "OTHER"
        encoded = b64(verifier._canonical_json(payload))
        signing_input = f"{raw[0]}.{encoded}".encode("ascii")
        bad = self.root / "extra-target.jws"
        bad.write_text(f"{raw[0]}.{encoded}.{b64(self.private.sign(signing_input))}", encoding="ascii")
        result = self.invoke(response=bad)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("CHANGE_TARGET_MISMATCH", result["reasons"][0]["code"])

    def test_algorithm_downgrades_are_rejected_before_key_lookup(self) -> None:
        for alg in ("none", "HS256", "ES256"):
            with self.subTest(alg=alg):
                response = self._signed_response(
                    f"alg-{alg}.jws",
                    header_change=lambda header, value=alg: header.update({"alg": value}),
                )
                result = self.invoke(response=response)
                self.assertEqual("FAIL", result["status"])
                self.assertEqual("UNSUPPORTED_ALGORITHM", result["reasons"][0]["code"])

    def test_duplicate_and_unknown_jws_fields_are_rejected(self) -> None:
        parts = self.response_path.read_text(encoding="ascii").split(".")
        duplicate_header = b64(
            (
                '{"alg":"EdDSA","alg":"HS256","kid":"pq-test",'
                f'"typ":"{verifier.EXPECTED_TYP}"}}'
            ).encode("utf-8")
        )
        signing_input = f"{duplicate_header}.{parts[1]}".encode("ascii")
        duplicate = self.root / "duplicate-header.jws"
        duplicate.write_text(
            f"{duplicate_header}.{parts[1]}.{b64(self.private.sign(signing_input))}",
            encoding="ascii",
        )
        result = self.invoke(response=duplicate)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("INVALID_JSON", result["reasons"][0]["code"])

        unknown_header = self._signed_response(
            "unknown-header.jws",
            header_change=lambda header: header.update({"jwk": {"kty": "OKP"}}),
        )
        result = self.invoke(response=unknown_header)
        self.assertEqual("UNKNOWN_FIELD", result["reasons"][0]["code"])

        unknown_payload = self._signed_response(
            "unknown-payload.jws",
            payload_change=lambda payload: payload.update({"jku": "file:///tmp/attacker.json"}),
        )
        result = self.invoke(response=unknown_payload)
        self.assertEqual("UNKNOWN_FIELD", result["reasons"][0]["code"])

    def test_response_future_expired_and_excessive_ttl_are_rejected(self) -> None:
        cases = (
            (
                "future.jws",
                lambda payload: payload.update({
                    "issued_at": self.now + verifier.MAX_CLOCK_SKEW + 1,
                    "not_before": self.now + verifier.MAX_CLOCK_SKEW + 1,
                    "expires_at": self.now + verifier.MAX_CLOCK_SKEW + 2,
                }),
                "RESPONSE_EXPIRED",
            ),
            (
                "expired.jws",
                lambda payload: payload.update({
                    "issued_at": self.now - 1000,
                    "not_before": self.now - 1000,
                    "expires_at": self.now - verifier.MAX_CLOCK_SKEW - 1,
                }),
                "RESPONSE_EXPIRED",
            ),
            (
                "ttl.jws",
                lambda payload: payload.update({
                    "issued_at": self.now,
                    "not_before": self.now,
                    "expires_at": self.now + verifier.MAX_TTL + 1,
                }),
                "INVALID_TIME_WINDOW",
            ),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                result = self.invoke(response=self._signed_response(name, payload_change=mutate))
                self.assertEqual("FAIL", result["status"])
                self.assertEqual(expected_code, result["reasons"][0]["code"])

    def test_time_policy_inputs_must_be_finite_and_within_fixed_limits(self) -> None:
        common = {
            "request_path": self.request_path,
            "challenge_path": self.challenge_path,
            "response_path": self.response_path,
            "before_path": self.before,
            "after_path": self.after,
            "keyset_path": self.keyset_path,
            "trust_anchor_path": self.anchor_path,
            "review_record_path": self.review_record_path,
            "now": self.now,
        }
        for field, value in (("now", float("nan")), ("now", float("inf")),
                             ("clock_skew", float("nan")), ("max_ttl", float("inf"))):
            with self.subTest(field=field, value=value):
                kwargs = dict(common)
                kwargs[field] = value
                with self.assertRaisesRegex(ValueError, "finite"):
                    verifier.verify(**kwargs)

        for field, value in (("clock_skew", verifier.MAX_CLOCK_SKEW + 1),
                             ("max_ttl", verifier.MAX_TTL + 1)):
            with self.subTest(field=field, value=value):
                kwargs = dict(common)
                kwargs[field] = value
                with self.assertRaisesRegex(ValueError, "maximum"):
                    verifier.verify(**kwargs)

    def test_malformed_revocation_entries_fail_closed(self) -> None:
        cases = (
            {"kid": "pq-test", "mode": "UNKNOWN"},
            {"kid": "pq-test", "mode": "ISSUED_AT_OR_AFTER"},
            {"kid": "pq-test", "mode": "ISSUED_AT_OR_AFTER", "issued_at": "not-int"},
            {"kid": "pq-test", "mode": "ALL_SIGNATURES", "extra": True},
        )
        for revocation in cases:
            with self.subTest(revocation=revocation):
                self._rewrite_keyset(
                    lambda keyset, revocation=revocation: keyset["revocations"].append(
                        revocation
                    )
                )
                result = self.invoke()
                self.assertEqual("FAIL", result["status"])
                self.assertEqual("INVALID_KEYSET", result["reasons"][0]["code"])
                self._write_keyset_and_anchor()

    def test_challenge_future_expired_and_excessive_ttl_are_rejected(self) -> None:
        original = json.loads(self.challenge_path.read_text(encoding="utf-8"))
        for name, issued, expires, expected_code in (
            ("future", self.now + verifier.MAX_CLOCK_SKEW + 1, self.now + verifier.MAX_CLOCK_SKEW + 2, "CHALLENGE_EXPIRED"),
            ("expired", self.now - 1000, self.now - verifier.MAX_CLOCK_SKEW - 1, "CHALLENGE_EXPIRED"),
            ("ttl", self.now, self.now + verifier.MAX_TTL + 1, "INVALID_TIME_WINDOW"),
        ):
            with self.subTest(name=name):
                challenge = dict(original)
                challenge["issued_at"] = issued
                challenge["expires_at"] = expires
                body = dict(challenge)
                body.pop("challenge_sha256")
                challenge["challenge_sha256"] = verifier._sha256(verifier._canonical_json(body))
                self.challenge_path.write_text(json.dumps(challenge), encoding="utf-8")
                result = self.invoke()
                self.assertEqual("FAIL", result["status"])
                self.assertEqual(expected_code, result["reasons"][0]["code"])
            self.challenge_path.write_text(json.dumps(original), encoding="utf-8")

    def test_unknown_retired_and_revoked_keys_are_rejected(self) -> None:
        unknown = self._signed_response(
            "unknown-kid.jws",
            header_change=lambda header: header.update({"kid": "does-not-exist"}),
        )
        result = self.invoke(response=unknown)
        self.assertEqual("UNKNOWN_KEY", result["reasons"][0]["code"])

        self._rewrite_keyset(lambda keyset: keyset["keys"][0].update({"status": "RETIRED"}))
        result = self.invoke()
        self.assertEqual("KEY_NOT_ACTIVE", result["reasons"][0]["code"])

        self._write_keyset_and_anchor()
        self._rewrite_keyset(
            lambda keyset: keyset["revocations"].append({
                "kid": "pq-test", "mode": "ALL_SIGNATURES"
            })
        )
        result = self.invoke()
        self.assertEqual("KEY_REVOKED", result["reasons"][0]["code"])

    def test_keyset_rollback_and_response_trust_epoch_mismatch_are_rejected(self) -> None:
        self._rewrite_keyset(lambda keyset: keyset.update({"sequence": 0}))
        # Keep the protected anchor at its prior high-water sequence.
        anchor = json.loads(self.anchor_path.read_text(encoding="utf-8"))
        anchor["sequence"] = 1
        self.anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
        result = self.invoke()
        self.assertEqual("TRUST_EPOCH_MISMATCH", result["reasons"][0]["code"])

        self._write_keyset_and_anchor()
        mismatch = self._signed_response(
            "epoch-mismatch.jws",
            payload_change=lambda payload: payload.update({"trust_epoch": 2}),
        )
        result = self.invoke(response=mismatch)
        self.assertEqual("TRUST_EPOCH_MISMATCH", result["reasons"][0]["code"])

    def test_no_change_requires_one_synthetic_target(self) -> None:
        self._configure_no_change()
        result = self.invoke()
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual("PASS", result["verification_status"])
        self.assertEqual("PASS", result["paired_quality_gate_status"])
        self.assertEqual("REVIEW", result["delivery_gate_status"])
        self.assertEqual(["NO_CHANGE"], result["expected_change_targets"])

        empty = self._signed_response(
            "no-change-empty.jws",
            payload_change=lambda payload: payload.update({"review_items": []}),
        )
        result = self.invoke(response=empty)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("CHANGE_TARGET_MISMATCH", result["reasons"][0]["code"])

    def test_partial_quality_dimensions_remain_review_not_fail(self) -> None:
        response = self._signed_response(
            "partial-dimensions.jws",
            payload_change=lambda payload: payload["review_items"][0].pop(verifier.DIMENSIONS[-1]),
        )
        result = self.invoke(response=response)
        self.assertEqual("REVIEW", result["status"])
        self.assertEqual(2, result["exit_code"])
        self.assertEqual("QUALITY_REVIEW_INCOMPLETE", result["reasons"][0]["code"])

    def test_request_requires_complete_exact_policy_hash_surface(self) -> None:
        cases = (
            ("missing", "INVALID_SCHEMA"),
            ("unknown", "UNKNOWN_FIELD"),
            ("invalid", "INVALID_HASH"),
        )
        for case, expected_code in cases:
            with self.subTest(case=case):
                request = json.loads(self.request_path.read_text(encoding="utf-8"))
                body = dict(request)
                body.pop("request_sha256")
                hashes = dict(body["policy_hashes"])
                if case == "missing":
                    hashes.pop("validator_sha256")
                elif case == "unknown":
                    hashes["unbound_policy_sha256"] = "a" * 64
                else:
                    hashes["validator_sha256"] = "not-a-hash"
                body["policy_hashes"] = hashes
                request = {
                    **body,
                    "request_sha256": verifier._sha256(verifier._canonical_json(body)),
                }
                self.request_path.write_text(
                    json.dumps(request, ensure_ascii=False),
                    encoding="utf-8",
                )
                result = self.invoke()
                self.assertEqual("FAIL", result["status"])
                self.assertEqual(expected_code, result["reasons"][0]["code"])
            self.request_path.write_text(
                json.dumps(self.request, ensure_ascii=False),
                encoding="utf-8",
            )

    def test_request_hunks_are_bound_to_current_artifact_bytes(self) -> None:
        forged = json.loads(self.request_path.read_text(encoding="utf-8"))
        forged["changes"][0]["before"]["sha256"] = "d" * 64
        with self.assertRaisesRegex(verifier.VerificationError, "hunks do not match"):
            verifier._validate_request_hunks_against_artifacts(
                forged, self.before.read_bytes(), self.after.read_bytes()
            )

    def test_policy_hash_drift_blocks_before_external_signature_clearance(self) -> None:
        request = json.loads(self.request_path.read_text(encoding="utf-8"))
        body = dict(request)
        body.pop("request_sha256")
        body["policy_hashes"] = dict(body["policy_hashes"])
        body["policy_hashes"]["validator_sha256"] = "e" * 64
        request = {
            **body,
            "request_sha256": verifier._sha256(verifier._canonical_json(body)),
        }
        self.request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        result = self.invoke()
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("POLICY_HASH_DRIFT", result["reasons"][0]["code"])

    def test_symlinked_input_path_is_rejected(self) -> None:
        link = self.root / "response-link.jws"
        try:
            link.symlink_to(self.response_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        result = self.invoke(response=link)
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("UNSAFE_PATH", result["reasons"][0]["code"])


if __name__ == "__main__":
    unittest.main()
