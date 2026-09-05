#!/usr/bin/env python3
"""Failure-injection coverage for generator projection publication and binding."""

from __future__ import annotations

import importlib.util
import csv
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import scan_humanize_chinese as scanner
import check_humanize_invariants as invariants
import finalize_humanize_long_document as long_finalizer
import prepare_humanize_long_document as long_preparer
import scaffold_humanize_rewrites as long_scaffolder
import build_humanize_rewrite_intent as intent_builder


SKILL_ROOT = SCRIPT_DIR.parent
BUILDER_PATH = SCRIPT_DIR / "build_humanize_generator_projection.py"
INLINE_PATH = SCRIPT_DIR / "run_humanize_inline.py"
QUALIFICATION_AUDITOR_PATH = SCRIPT_DIR / "audit_humanize_generation_qualification.py"
SPEC = importlib.util.spec_from_file_location("projection_builder_under_test", BUILDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load generator projection builder")
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class GenerationQualificationBaselineTests(unittest.TestCase):
    def test_missing_manifest_is_honest_not_evaluated(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(QUALIFICATION_AUDITOR_PATH),
                "--format",
                "json",
            ],
            cwd=SKILL_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(
            completed.returncode,
            2,
            completed.stderr.decode("utf-8", errors="replace"),
        )
        report = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(report["evidence_integrity_status"], "PASS")
        self.assertEqual(report["qualification_status"], "NOT_EVALUATED")
        self.assertEqual(report["exit_code"], 2)
        summary = report["summary"]
        self.assertGreater(summary["atoms_total"], 0)
        self.assertEqual(summary["atoms_pass"], 0)
        self.assertEqual(summary["atoms_fail"], 0)
        self.assertEqual(
            summary["atoms_not_evaluated"],
            summary["atoms_total"],
        )
        self.assertEqual(summary["cases_total"], 0)
        self.assertEqual(
            report["trust_boundary"]["academic_correctness"],
            "NOT_EVALUATED",
        )


def _write_journal(
    *,
    state: str,
    output: Path,
    manifest: Path,
    staging: Path,
    manifest_staging: Path,
    tree_hash: str | None = None,
    manifest_raw: bytes | None = None,
) -> Path:
    payload = builder._publication_journal_payload(
        state=state,
        output_root=output,
        manifest_path=manifest,
        staging_root=staging,
        manifest_staging_path=manifest_staging,
        projection_tree_sha256=tree_hash,
        manifest_sha256=builder._sha256(manifest_raw) if manifest_raw else None,
        manifest_size=len(manifest_raw) if manifest_raw else None,
    )
    journal = builder._publication_journal_path(manifest)
    builder._write_atomic_file(journal, builder._canonical_json(payload))
    return journal


class ProjectionPublicationJournalTests(unittest.TestCase):
    def test_recovery_states_and_tampered_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_raw = b'{"projection":"manifest"}'

            output = root / "allocated-output"
            manifest = root / "allocated-manifest.json"
            staging = root / ".allocated-output.staging-a"
            staging.mkdir()
            manifest_staging = root / ".allocated-manifest.json.staging-a"
            manifest_staging.write_bytes(b"partial")
            journal = _write_journal(
                state="ALLOCATED",
                output=output,
                manifest=manifest,
                staging=staging,
                manifest_staging=manifest_staging,
            )
            builder._recover_publication_journal(journal, output, manifest)
            self.assertFalse(any(item.exists() for item in (staging, manifest_staging, journal)))

            output = root / "prepared-output"
            output.mkdir()
            (output / "entry.txt").write_text("projection", encoding="utf-8")
            tree_hash = builder._directory_tree_hash(output)
            manifest = root / "prepared-manifest.json"
            staging = root / ".prepared-output.staging-a"
            staging.mkdir()
            manifest_staging = root / ".prepared-manifest.json.staging-a"
            manifest_staging.write_bytes(manifest_raw)
            journal = _write_journal(
                state="PREPARED",
                output=output,
                manifest=manifest,
                staging=staging,
                manifest_staging=manifest_staging,
                tree_hash=tree_hash,
                manifest_raw=manifest_raw,
            )
            builder._recover_publication_journal(journal, output, manifest)
            self.assertFalse(any(item.exists() for item in (output, staging, manifest_staging, journal)))

            output = root / "published-output"
            output.mkdir()
            (output / "entry.txt").write_text("projection", encoding="utf-8")
            tree_hash = builder._directory_tree_hash(output)
            manifest = root / "published-manifest.json"
            staging = root / ".published-output.staging-a"
            staging.mkdir()
            manifest_staging = root / ".published-manifest.json.staging-a"
            manifest_staging.write_bytes(manifest_raw)
            journal = _write_journal(
                state="OUTPUT_PUBLISHED",
                output=output,
                manifest=manifest,
                staging=staging,
                manifest_staging=manifest_staging,
                tree_hash=tree_hash,
                manifest_raw=manifest_raw,
            )
            builder._recover_publication_journal(journal, output, manifest)
            self.assertTrue(output.exists())
            self.assertEqual(manifest.read_bytes(), manifest_raw)
            self.assertFalse(any(item.exists() for item in (staging, manifest_staging, journal)))

            staging = root / ".published-output.staging-b"
            staging.mkdir()
            manifest_staging = root / ".published-manifest.json.staging-b"
            journal = _write_journal(
                state="COMMITTED",
                output=output,
                manifest=manifest,
                staging=staging,
                manifest_staging=manifest_staging,
                tree_hash=tree_hash,
                manifest_raw=manifest_raw,
            )
            builder._recover_publication_journal(journal, output, manifest)
            self.assertTrue(output.exists())
            self.assertEqual(manifest.read_bytes(), manifest_raw)
            self.assertFalse(any(item.exists() for item in (staging, manifest_staging, journal)))

            sentinel = root / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            output = root / "tampered-output"
            manifest = root / "tampered-manifest.json"
            staging = root / ".tampered-output.staging-a"
            staging.mkdir()
            manifest_staging = root / ".tampered-manifest.json.staging-a"
            journal = _write_journal(
                state="ALLOCATED",
                output=output,
                manifest=manifest,
                staging=staging,
                manifest_staging=manifest_staging,
            )
            payload = builder._strict_json(journal.read_bytes(), "journal")
            payload["output_root"] = str(root / "other-output")
            builder._write_atomic_file(journal, builder._canonical_json(payload))
            with self.assertRaises(builder.ProjectionError):
                builder._recover_publication_journal(journal, output, manifest)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertTrue(staging.exists())
            self.assertTrue(journal.exists())

    def test_real_builder_recovers_at_both_commit_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "before-manifest-output"
            manifest = root / "before-manifest.json"
            original_replace = builder.os.replace

            def interrupt_manifest_move(source_path: str | Path, target_path: str | Path) -> None:
                if Path(target_path) == manifest and Path(source_path).name.startswith(
                    f".{manifest.name}.staging-"
                ):
                    raise KeyboardInterrupt("test interrupt before manifest commit")
                original_replace(source_path, target_path)

            builder.os.replace = interrupt_manifest_move
            try:
                with self.assertRaises(KeyboardInterrupt):
                    builder.build_projection(SKILL_ROOT, output, manifest)
            finally:
                builder.os.replace = original_replace
            journal = builder._publication_journal_path(manifest)
            self.assertTrue(output.exists())
            self.assertFalse(manifest.exists())
            self.assertTrue(journal.exists())
            with self.assertRaisesRegex(builder.ProjectionError, "output must not already exist"):
                builder.build_projection(SKILL_ROOT, output, manifest)
            self.assertTrue(manifest.exists())
            self.assertFalse(journal.exists())

            output = root / "after-manifest-output"
            manifest = root / "after-manifest.json"
            original_write = builder._write_atomic_file

            def interrupt_committed_journal(path: Path, raw: bytes) -> None:
                if path == builder._publication_journal_path(manifest):
                    payload = builder._strict_json(raw, "test journal")
                    if payload.get("state") == "COMMITTED":
                        raise KeyboardInterrupt("test interrupt after manifest commit")
                original_write(path, raw)

            builder._write_atomic_file = interrupt_committed_journal
            try:
                with self.assertRaises(KeyboardInterrupt):
                    builder.build_projection(SKILL_ROOT, output, manifest)
            finally:
                builder._write_atomic_file = original_write
            journal = builder._publication_journal_path(manifest)
            self.assertTrue(output.exists())
            self.assertTrue(manifest.exists())
            self.assertTrue(journal.exists())
            with self.assertRaisesRegex(builder.ProjectionError, "output must not already exist"):
                builder.build_projection(SKILL_ROOT, output, manifest)
            self.assertFalse(journal.exists())


class ProjectionBindingTests(unittest.TestCase):
    def test_pytest_cache_is_housekeeping_but_other_hidden_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "humanize-academic-chinese"
            shutil.copytree(SKILL_ROOT, source)
            cache = source / ".pytest_cache"
            if cache.exists():
                shutil.rmtree(cache)
            cache.mkdir()
            (cache / ".gitignore").write_text("*\n", encoding="utf-8")

            policy = builder.load_policy(
                source / "references" / "generator-projection-policy.json"
            )
            frozen, dispositions = builder._inventory(source, policy)
            self.assertEqual(dispositions[".pytest_cache/.gitignore"], "HOUSEKEEPING")
            self.assertNotIn(
                ".pytest_cache/.gitignore",
                {item.path for item in frozen},
            )

            unexpected = source / ".unexpected"
            unexpected.mkdir()
            (unexpected / "marker").write_text("must remain classified", encoding="utf-8")
            with self.assertRaisesRegex(
                builder.ProjectionError,
                r"unclassified source file: \.unexpected/marker",
            ):
                builder._inventory(source, policy)

    def test_forged_policy_and_dependency_drift_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "humanize-academic-chinese"
            shutil.copytree(SKILL_ROOT, source)
            policy_path = source / "references" / "generator-projection-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["approved_builder_executable_sha256"] = "0" * 64
            policy_path.write_text(
                json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                builder.ProjectionError, "does not approve the executing builder semantics"
            ):
                builder.build_projection(source, root / "forged-output", root / "forged.json")

            shutil.rmtree(source)
            shutil.copytree(SKILL_ROOT, source)
            dependency = source / "scripts" / "load_humanize_negative_guards.py"
            dependency.write_bytes(dependency.read_bytes() + b"\n# test dependency drift\n")
            copied_policy = builder.load_policy(
                source / "references" / "generator-projection-policy.json"
            )
            frozen, dispositions = builder._inventory(source, copied_policy)
            forged_capability_hash = builder._projection_materials(
                frozen, dispositions, copied_policy
            )["source"]["capability_source_sha256"]
            policy_path = source / "references" / "generator-projection-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["approved_capability_source_sha256"] = forged_capability_hash
            policy_path.write_text(
                json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(builder.ProjectionError, "transform dependency differs"):
                builder.build_projection(source, root / "drift-output", root / "drift.json")


class ProjectionRuntimeTests(unittest.TestCase):
    def test_projected_second_pass_receipt_fails_closed_without_type_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "humanize-academic-chinese"
            shutil.copytree(SKILL_ROOT, source)
            policy_path = source / "references" / "generator-projection-policy.json"
            policy_payload = json.loads(policy_path.read_text(encoding="utf-8"))
            policy_payload["approved_builder_executable_sha256"] = (
                builder._builder_executable_sha256()
            )
            policy_payload["approved_transform_registry_sha256"] = (
                builder._transform_registry_sha256()
            )
            policy_path.write_text(
                json.dumps(policy_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            copied_policy = builder.load_policy(policy_path)
            frozen, dispositions = builder._inventory(source, copied_policy)
            policy_payload["approved_capability_source_sha256"] = (
                builder._projection_materials(frozen, dispositions, copied_policy)["source"][
                    "capability_source_sha256"
                ]
            )
            policy_path.write_text(
                json.dumps(policy_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            projection = root / "projection"
            projection_manifest = builder.build_projection(
                source, projection, root / "projection.manifest.json"
            )
            self.assertEqual(len(projection_manifest["transformations"]), 5)
            validator_transformation = next(
                item
                for item in projection_manifest["transformations"]
                if item["path"] == "scripts/validate_humanize_output.py"
            )
            self.assertEqual(
                [item["label"] for item in validator_transformation["removed_spans"]],
                [
                    "python-span:paired-quality-path-constants",
                    "python-span:paired-quality-implementation-hashes",
                    "python-span:paired-quality-contract-hash",
                ],
            )

            projected_validator = (
                projection / "scripts" / "validate_humanize_output.py"
            ).read_text(encoding="utf-8")
            for preserved_key in (
                "validator_sha256",
                "invariant_checker_sha256",
                "scanner_sha256",
                "lexicon_sha256",
                "report_extractor_sha256",
                "runtime_contract_sha256",
            ):
                self.assertIn(preserved_key, projected_validator)
            for excluded_key in (
                "paired_quality_verifier_sha256",
                "paired_quality_contract_sha256",
                "paired_quality_clearance_contract",
            ):
                self.assertNotIn(excluded_key, projected_validator)

            shutil.rmtree(source)
            self.assertFalse(source.exists())
            isolated_home = root / "isolated-home"
            isolated_home.mkdir()
            runtime_environment = os.environ.copy()
            for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE"):
                runtime_environment.pop(name, None)
            runtime_environment.update(
                {
                    "HOME": str(isolated_home),
                    "USERPROFILE": str(isolated_home),
                    "HOMEDRIVE": isolated_home.drive,
                    "HOMEPATH": str(isolated_home)[len(isolated_home.drive) :],
                    "APPDATA": str(isolated_home / "AppData" / "Roaming"),
                    "LOCALAPPDATA": str(isolated_home / "AppData" / "Local"),
                    "CODEX_HOME": str(isolated_home / ".codex"),
                    "XDG_CONFIG_HOME": str(isolated_home / ".config"),
                    "XDG_DATA_HOME": str(isolated_home / ".local" / "share"),
                }
            )

            seed = root / "generated.tex"
            seed.write_text(
                "% Auto-generated file; do not edit.\nGenerated body.\n",
                encoding="utf-8",
            )
            run_dir = root / "run"
            prepared = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(projection / "scripts" / "prepare_humanize_long_document.py"),
                    str(seed),
                    "--output",
                    str(run_dir),
                    "--scene",
                    "GENERAL",
                ],
                cwd=projection,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=False,
                env=runtime_environment,
            )
            self.assertEqual(prepared.returncode, 2, prepared.stdout + prepared.stderr)
            prepare_metadata = json.loads(prepared.stdout)
            self.assertEqual(prepare_metadata["status"], "REVIEW")
            self.assertTrue(prepare_metadata["no_editable_scope"])
            self.assertFalse(prepare_metadata["completion_claim_allowed"])
            validator_hashes = prepare_metadata["policy_snapshot"][
                "validator_policy_hashes"
            ]
            self.assertIn("runtime_contract_sha256", validator_hashes)
            self.assertNotIn("paired_quality_verifier_sha256", validator_hashes)
            self.assertNotIn("paired_quality_contract_sha256", validator_hashes)
            rewrites = root / "rewrites"
            rewrites.mkdir()
            receipt = root / "second-pass-receipt.json"
            receipt.write_text("{}\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(projection / "scripts" / "finalize_humanize_long_document.py"),
                    "--run-dir",
                    str(run_dir),
                    "--rewrites",
                    str(rewrites),
                    "--second-pass-receipt",
                    str(receipt),
                    "--format",
                    "json",
                ],
                cwd=projection,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=False,
                env=runtime_environment,
            )
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertNotIn("TypeError", completed.stdout + completed.stderr)
            metadata = json.loads(completed.stdout)
            self.assertFalse(metadata.get("runtime_error", False))
            evidence = metadata["humanize_second_pass_evidence"]
            self.assertEqual(evidence["status"], "FAIL")
            self.assertEqual(
                evidence["error"],
                "second-pass control-plane verification is unavailable in generator projection",
            )
            self.assertEqual(metadata["humanize_second_pass_convergence"], "FAIL")
            self.assertEqual(metadata["second_pass_stability_status"], "INVALID_EVIDENCE")
            self.assertFalse(metadata["paired_quality_clearance_granted"])
            self.assertFalse(metadata["paired_quality_local_clearance_supported"])
            self.assertFalse(metadata["humanize_completion_claim_allowed"])


class LexicalTemplateSlotTests(unittest.TestCase):
    def test_strict_corpus_inventory_is_large_bound_and_high_rewrite(self) -> None:
        lexicon = scanner.load_lexicon()
        policy = lexicon["strict_corpus_policy"]
        inventory = lexicon["strict_phrase_inventory"]
        self.assertTrue(policy["enabled_by_default"])
        self.assertEqual(
            scanner.EXPECTED_STRICT_INVENTORY_ENTRIES,
            policy["minimum_inventory_entries"],
        )
        self.assertEqual(policy["inventory_entries"], len(inventory))
        self.assertEqual(scanner.EXPECTED_STRICT_INVENTORY_ENTRIES, len(inventory))
        self.assertEqual(
            scanner.EXPECTED_STRICT_INVENTORY_SHA256,
            policy["inventory_manifest_sha256"],
        )
        self.assertEqual(
            scanner.EXPECTED_STRICT_INVENTORY_SHA256,
            scanner._canonical_inventory_sha256(inventory),
        )
        inventory_phrases = {item["phrase"] for item in inventory}
        strict_signals = [
            item
            for item in lexicon["signals"]
            if item["id"].startswith("LEX-STRICT-CORPUS-")
        ]
        self.assertEqual(set(policy["signal_ids"]), {item["id"] for item in strict_signals})
        self.assertEqual(
            inventory_phrases,
            {variant for item in strict_signals for variant in item["variants"]},
        )
        self.assertTrue(
            all(
                item["severity"] == "high"
                and item["action"] == "REWRITE"
                and item["threshold"]["min_occurrences"] == 1
                for item in strict_signals
            )
        )

        findings = scanner.scan_text_with_offsets(
            "这个写法会更稳，相关口径需要进一步收紧。",
            file="paper.md",
            scene="RESEARCH",
            document_format="markdown",
        )
        strict = [
            item for item in findings if item["signal_id"].startswith("LEX-STRICT-CORPUS-")
        ]
        self.assertTrue(strict)
        self.assertTrue(
            all(
                item["candidate"]
                and item["severity"] == "high"
                and item["action"] == "REWRITE"
                for item in strict
            )
        )
        matched = {item["matched"] for item in strict}
        self.assertTrue({"会更稳", "进一步收紧"} <= matched)

        for phrase in ("\u66f4\u7a33", "\u6536\u7d27"):
            root_findings = scanner.scan_text_with_offsets(
                f"本方案{phrase}。",
                file="paper.md",
                scene="GENERAL",
                document_format="markdown",
            )
            self.assertTrue(
                any(
                    item["matched"] == phrase
                    and item["signal_id"].startswith("LEX-STRICT-CORPUS-")
                    and item["action"] == "REWRITE"
                    for item in root_findings
                )
            )

    def test_strict_corpus_inventory_rejects_content_or_policy_drift(self) -> None:
        lexicon = scanner.load_lexicon()
        content_drift = json.loads(json.dumps(lexicon, ensure_ascii=False))
        content_drift["strict_phrase_inventory"][0]["category"] = (
            "scope-boundary"
            if content_drift["strict_phrase_inventory"][0]["category"]
            != "scope-boundary"
            else "process-broadcast"
        )
        with self.assertRaisesRegex(ValueError, "content differs"):
            scanner._validate_strict_corpus_contract(content_drift)

        policy_drift = json.loads(json.dumps(lexicon, ensure_ascii=False))
        policy_drift["strict_corpus_policy"]["inventory_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "not bound"):
            scanner._validate_strict_corpus_contract(policy_drift)

    def test_strict_corpus_terms_in_code_are_protected(self) -> None:
        findings = scanner.scan_text_with_offsets(
            "```text\n当前 本节 全面 构建 框架\n```",
            file="paper.md",
            scene="RESEARCH",
            document_format="markdown",
        )
        self.assertFalse(
            any(item["signal_id"].startswith("LEX-STRICT-CORPUS-") for item in findings)
        )

    def test_repeated_template_slots_are_candidates_but_single_or_protected_text_is_not(self) -> None:
        template = (
            "适用题目：甲类。\n"
            "逻辑链条：给定首句后展开。\n"
            "这一类题目可用同一段式收尾。\n"
        )
        findings = scanner.scan_text_with_offsets(
            template,
            file="template.tex",
            scene="AUTO",
            document_format="tex",
        )
        slot_findings = [item for item in findings if item["signal_id"] == "LEX-META-02"]
        self.assertEqual([], slot_findings)
        excluded = scanner.scan_text_with_offsets(
            template,
            file="template.tex",
            scene="AUTO",
            document_format="tex",
            include_excluded=True,
        )
        slot_excluded = [item for item in excluded if item["signal_id"] == "LEX-META-02"]
        self.assertEqual(3, len(slot_excluded))
        self.assertTrue(all(item["excluded"] and item["action"] == "KEEP" for item in slot_excluded))

        substantive = "本节只讨论一个逻辑链条如何连接条件和结论。\n"
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-META-02"
                for item in scanner.scan_text_with_offsets(
                    substantive,
                    file="paper.tex",
                    scene="RESEARCH",
                    document_format="tex",
                )
            )
        )

        protected = "\\begin{verbatim}\n" + template + "\\end{verbatim}\n"
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-META-02"
                for item in scanner.scan_text_with_offsets(
                    protected,
                    file="code.tex",
                    scene="AUTO",
                    document_format="tex",
                )
            )
        )

    def test_repeated_self_validation_is_narrow_and_respects_protection(self) -> None:
        repeated = (
            "本研究的价值不在于增加术语，而在于分开两个条件。\n\n"
            "本模型的优点不在于扩大规模，而在于显示不同结果。\n"
        )
        findings = scanner.scan_text_with_offsets(
            repeated,
            file="analysis.tex",
            scene="RESEARCH",
            document_format="tex",
        )
        self_validation = [
            item for item in findings if item["signal_id"] == "LEX-SELF-VALIDATION-01"
        ]
        self.assertEqual(len(self_validation), 2)
        self.assertTrue(all(item["candidate"] and item["action"] == "REVIEW" for item in self_validation))

        single = "本研究的价值不在于增加术语，而在于分开两个条件。\n"
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-SELF-VALIDATION-01"
                for item in scanner.scan_text_with_offsets(
                    single,
                    file="single.tex",
                    scene="RESEARCH",
                    document_format="tex",
                )
            )
        )

        protected = "\\begin{verbatim}\n" + repeated + "\\end{verbatim}\n"
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-SELF-VALIDATION-01"
                for item in scanner.scan_text_with_offsets(
                    protected,
                    file="protected.tex",
                    scene="RESEARCH",
                    document_format="tex",
                )
            )
        )

    def test_limitation_editorial_wrapper_and_generic_future_are_candidates(self) -> None:
        editorial = "本模型的局限需要在正文说明。后续如继续完善，应当补入独立数据。\n"
        findings = scanner.scan_text_with_offsets(
            editorial,
            file="editorial.tex",
            scene="RESEARCH",
            document_format="tex",
        )
        meta = [item for item in findings if item["signal_id"] == "LEX-META-01"]
        future = [item for item in findings if item["signal_id"] == "LEX-FUTURE-01"]
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0]["action"], "DELETE")
        self.assertEqual(len(future), 1)
        self.assertEqual(future[0]["action"], "REWRITE")
        self.assertTrue(future[0]["strict_overlap_requires_rewrite"])

        protected = "\\begin{verbatim}\n" + editorial + "\\end{verbatim}\n"
        protected_findings = scanner.scan_text_with_offsets(
            protected,
            file="editorial-code.tex",
            scene="RESEARCH",
            document_format="tex",
        )
        self.assertFalse(
            any(
                item["signal_id"] in {"LEX-META-01", "LEX-FUTURE-01"}
                for item in protected_findings
            )
        )

        before = "本模型的局限需要在正文说明：当前结果只适用于固定参数组，不构成独立外部验证。\n"
        after = "当前结果只适用于固定参数组，不构成独立外部验证。\n"
        invariant_result = invariants.check_documents(before, after)
        warning_codes = {item.code for item in invariant_result.warnings}
        self.assertNotIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", warning_codes)
        self.assertNotIn("SPEECH_ACT_CONDITION_CHANGED", warning_codes)

        content_before = "本模型需要独立数据。\n"
        content_after = "本模型可使用独立数据。\n"
        content_result = invariants.check_documents(content_before, content_after)
        content_warning_codes = {item.code for item in content_result.warnings}
        self.assertIn("SPEECH_ACT_MODALITY_SCOPE_CHANGED", content_warning_codes)

    def test_section_self_audit_triplet_requires_repeated_complete_unprotected_sections(self) -> None:
        repeated = (
            "\\subsection{模型一分析}\n"
            "本问的优点不在于增加参数，而在于分开两类条件。\n\n"
            "其局限同样需要写清：结果只适用于固定样本。后续若继续补强，应优先加入独立样本。\n\n"
            "\\subsection{模型二分析}\n"
            "本模型的优点不在于扩大规模，而在于区分两种机制。\n\n"
            "本模型的局限需要说明：比较未覆盖季节变化。后续如继续完善，应优先增加 $K=3.20$ 的季节对照。\n"
        )
        findings = scanner.scan_text_with_offsets(
            repeated,
            file="analysis.tex",
            scene="RESEARCH",
            document_format="tex",
        )
        triplets = [
            item for item in findings if item["signal_id"] == "LEX-SELF-AUDIT-TRIPLET-01"
        ]
        self.assertEqual(len(triplets), 2)
        self.assertTrue(all(item["candidate"] and item["action"] == "REVIEW" for item in triplets))

        one_complete = repeated.split("\\subsection{模型二分析}")[0]
        missing_outlook = repeated.replace("后续如继续完善，应优先增加 $K=3.20$ 的季节对照。", "季节对照尚未覆盖。")
        for text in (one_complete, missing_outlook):
            self.assertFalse(
                any(
                    item["signal_id"] == "LEX-SELF-AUDIT-TRIPLET-01"
                    for item in scanner.scan_text_with_offsets(
                        text,
                        file="single.tex",
                        scene="RESEARCH",
                        document_format="tex",
                    )
                )
            )

        protected = (
            "\\subsection{模型一分析}\n"
            "\\begin{verbatim}\n"
            + repeated
            + "\\end{verbatim}\n"
        )
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-SELF-AUDIT-TRIPLET-01"
                for item in scanner.scan_text_with_offsets(
                    protected,
                    file="protected.tex",
                    scene="RESEARCH",
                    document_format="tex",
                )
            )
        )

    def test_question_analysis_opening_contrast_is_modeling_only_and_structure_bound(self) -> None:
        repeated = (
            "\\subsection{问题一分析}\n"
            "问题一不是比较单点值，而是区分两个阶段。\n\n"
            "\\subsection{问题二分析}\n"
            "本问的重点不是比较谁更大，而是说明约束怎样改变结果。\n\n"
            "\\subsection{问题三分析}\n"
            "这一问真正要回答的不是某时刻数值，而是系统属于哪类状态。\n"
        )
        findings = scanner.scan_text_with_offsets(
            repeated,
            file="analysis.tex",
            scene="MODELING",
            document_format="tex",
        )
        contrast_openings = [
            item
            for item in findings
            if item["signal_id"] == "LEX-QUESTION-ANALYSIS-CONTRAST-01"
        ]
        self.assertEqual(len(contrast_openings), 3)
        self.assertTrue(all(item["candidate"] and item["action"] == "REVIEW" for item in contrast_openings))

        two_sections = repeated.rsplit("\\subsection{问题三分析}", 1)[0]
        course_like = (
            "\\subsection{策略说明}\n"
            "不是中间带，而是边缘带给出更强信号。\n\n"
            "\\subsection{解题说明}\n"
            "不是背结论，而是先辨认条件。\n\n"
            "\\subsection{复盘说明}\n"
            "不是机械套用，而是检查题干限制。\n"
        )
        for text in (two_sections, course_like):
            self.assertFalse(
                any(
                    item["signal_id"] == "LEX-QUESTION-ANALYSIS-CONTRAST-01"
                    for item in scanner.scan_text_with_offsets(
                        text,
                        file="negative.tex",
                        scene="MODELING",
                        document_format="tex",
                    )
                )
            )

        protected_third = repeated.replace(
            "这一问真正要回答的不是某时刻数值，而是系统属于哪类状态。",
            "\\begin{verbatim}\n这一问真正要回答的不是某时刻数值，而是系统属于哪类状态。\n\\end{verbatim}",
        )
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-QUESTION-ANALYSIS-CONTRAST-01"
                for item in scanner.scan_text_with_offsets(
                    protected_third,
                    file="protected.tex",
                    scene="MODELING",
                    document_format="tex",
                )
            )
        )

    def test_question_opening_avoid_misread_requires_repeated_model_sections(self) -> None:
        repeated = "".join(
            (
                f"\\section{{问题{label}的模型建立与求解}}\n"
                "\\subsection{模型建立}\n"
                f"为避免把“问题{label}的局地口径”和“全流域平均口径”混为一谈，先登记对象。\n"
            )
            for label in ("一", "二", "三")
        )
        findings = scanner.scan_text_with_offsets(
            repeated,
            file="avoid.tex",
            scene="MODELING",
            document_format="tex",
        )
        matches = [
            item for item in findings if item["signal_id"] == "LEX-QUESTION-AVOID-MISREAD-01"
        ]
        self.assertEqual(3, len(matches))
        self.assertTrue(all(item["candidate"] and item["action"] == "REVIEW" for item in matches))

        single = (
            "\\section{问题一的模型建立与求解}\n"
            "\\subsection{模型建立}\n"
            "为了避免把局部数值现象误写成绝对阈值，保留步长条件。\n"
        )
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-QUESTION-AVOID-MISREAD-01"
                for item in scanner.scan_text_with_offsets(
                    single, file="single.tex", scene="MODELING", document_format="tex"
                )
            )
        )

        protected = repeated.replace(
            "为避免把“问题三的局地口径”和“全流域平均口径”混为一谈，先登记对象。",
            "\\begin{verbatim}\n为避免把“问题三的局地口径”和“全流域平均口径”混为一谈，先登记对象。\n\\end{verbatim}",
        )
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-QUESTION-AVOID-MISREAD-01"
                for item in scanner.scan_text_with_offsets(
                    protected, file="protected.tex", scene="MODELING", document_format="tex"
                )
            )
        )

    def test_question_benefit_self_proof_requires_repeated_analysis_sections(self) -> None:
        repeated = (
            "\\subsection{问题一分析}\n这样的分析既能解释资源变化，也能说明后续响应。\n"
            "\\subsection{问题二分析}\n这样写，问题二的证据链就会更完整。\n"
            "\\subsection{问题三分析}\n这样处理的好处是后文有统一的参数轴。\n"
            "\\subsection{问题四分析}\n这样处理后，问题四的表述就会从“某个点的现象”转为“一个可复核的区间判断”。\n"
            "\\subsection{问题五分析}\n这样，问题五才能从数值汇总上升为机制解释。\n"
        )
        findings = scanner.scan_text_with_offsets(
            repeated,
            file="benefit.tex",
            scene="MODELING",
            document_format="tex",
        )
        matches = [
            item for item in findings if item["signal_id"] == "LEX-QUESTION-BENEFIT-SELF-PROOF-01"
        ]
        self.assertEqual(5, len(matches))
        self.assertTrue(all(item["candidate"] and item["action"] == "REVIEW" for item in matches))

        single = "\\subsection{问题一分析}\n这样处理后，误差从 8.1\\% 降至 5.4\\%。\n"
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-QUESTION-BENEFIT-SELF-PROOF-01"
                for item in scanner.scan_text_with_offsets(
                    single, file="single.tex", scene="MODELING", document_format="tex"
                )
            )
        )

        protected = repeated
        for sentence in (
            "这样的分析既能解释资源变化，也能说明后续响应。",
            "这样写，问题二的证据链就会更完整。",
            "这样处理的好处是后文有统一的参数轴。",
        ):
            protected = protected.replace(
                sentence,
                f"\\begin{{verbatim}}\n{sentence}\n\\end{{verbatim}}",
            )
        self.assertFalse(
            any(
                item["signal_id"] == "LEX-QUESTION-BENEFIT-SELF-PROOF-01"
                for item in scanner.scan_text_with_offsets(
                    protected, file="protected.tex", scene="MODELING", document_format="tex"
                )
            )
        )

    def test_red_team_context_exclusions_do_not_hide_real_candidates(self) -> None:
        coach = scanner.scan_text_with_offsets(
            "只要记住这个条件即可。必须记住另一个独立提醒。",
            file="coach.md",
            scene="COURSE",
            document_format="markdown",
        )
        coach_ids = {item["matched"] for item in coach if item["signal_id"] == "LEX-COACH-01"}
        self.assertNotIn("要记住", coach_ids)
        self.assertIn("必须记住", coach_ids)

        technical = scanner.scan_text_with_offsets(
            "总量锚点、观测口径和硬锚点均来自题面。",
            file="technical.tex",
            scene="MODELING",
            document_format="tex",
        )
        self.assertFalse(any(item["signal_id"] == "LEX-MGMT-02" for item in technical))

        heading_duplicate = (
            "\\subsection*{位置锚，不是起手锚}\n"
            "\\addcontentsline{toc}{subsection}{位置锚，不是起手锚}\n"
        )
        duplicate = scanner.scan_text_with_offsets(
            heading_duplicate,
            file="heading.tex",
            scene="COURSE",
            document_format="tex",
        )
        self.assertFalse(any(item["signal_id"] == "LEX-CONTRAST-01" for item in duplicate))

        real_contrast = scanner.scan_text_with_offsets(
            "这里不是中间带，而是边缘带给出更强信号。另一个句子不是猜均值，而是先看容量约束。",
            file="contrast.tex",
            scene="COURSE",
            document_format="tex",
        )
        self.assertEqual(2, len([item for item in real_contrast if item["signal_id"] == "LEX-CONTRAST-01"]))

        single_contrast = scanner.scan_text_with_offsets(
            "这里讨论的不是数值误差，而是模型误差。",
            file="single-contrast.tex",
            scene="MODELING",
            document_format="tex",
        )
        self.assertEqual(
            1,
            len([item for item in single_contrast if item["signal_id"] == "LEX-CONTRAST-01"]),
        )

        template_payload = scanner.scan_text_with_offsets(
            "逻辑链条：给定首句。这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            file="template.tex",
            scene="COURSE",
            document_format="tex",
            include_excluded=True,
        )
        template_market = [
            item for item in template_payload if item["signal_id"] == "LEX-MARKET-01"
        ]
        self.assertEqual(3, len(template_market))
        self.assertTrue(all(item["excluded"] and item["action"] == "KEEP" for item in template_market))

        authored_slogan = scanner.scan_text_with_offsets(
            "这不仅顺应了时代的演变，更是个人/社会破局的关键。因此，我们必须持之以恒地践行这一趋势。",
            file="prose.tex",
            scene="COURSE",
            document_format="tex",
            include_excluded=True,
        )
        authored_market = [
            item for item in authored_slogan if item["signal_id"] == "LEX-MARKET-01"
        ]
        self.assertEqual(3, len(authored_market))
        self.assertTrue(all(item["candidate"] and not item["excluded"] for item in authored_market))

    def test_order_shell_keeps_only_explicit_course_decision_tables(self) -> None:
        condition_table = (
            "\\begin{longtable}{ll}\n"
            "\\textbf{如果已经发生了这件事} & \\textbf{你下一步立刻做什么} \\\\\n"
            "甲 & 先看甲，再看乙。 \\\\\n"
            "乙 & 先看丙，再看丁。 \\\\\n"
            "\\end{longtable}\n"
        )
        lookup_table = (
            "\\begin{longtable}{ll}\n"
            "\\textbf{第一眼先看哪里} & \\textbf{第一眼没找到再看哪里} \\\\\n"
            "甲 & 先看甲，再看乙。 \\\\\n"
            "乙 & 先看丙，再看丁。 \\\\\n"
            "\\end{longtable}\n"
        )
        generic_table = (
            "\\begin{longtable}{ll}\n"
            "\\textbf{步骤} & \\textbf{结果} \\\\\n"
            "甲 & 先看甲，再看乙。 \\\\\n"
            "乙 & 先看丙，再看丁。 \\\\\n"
            "\\end{longtable}\n"
        )
        prose = "先看甲，再看乙。先看丙，再看丁。"

        for table, expected_count in ((condition_table, 2), (lookup_table, 3)):
            findings = scanner.scan_text_with_offsets(
                table,
                file="course.tex",
                scene="COURSE",
                document_format="tex",
                include_excluded=True,
            )
            order = [item for item in findings if item["signal_id"] == "LEX-ORDER-01"]
            self.assertEqual(len(order), expected_count)
            self.assertTrue(all(item["excluded"] and item["action"] == "KEEP" for item in order))

        for text, file in ((generic_table, "table.tex"), (prose, "prose.tex")):
            findings = scanner.scan_text_with_offsets(
                text,
                file=file,
                scene="COURSE",
                document_format="tex",
            )
            order = [item for item in findings if item["signal_id"] == "LEX-ORDER-01"]
            self.assertEqual(len(order), 2)
            self.assertTrue(all(item["candidate"] and item["action"] == "REWRITE" for item in order))

def _long_manifest(run_dir: Path) -> list[dict[str, str]]:
    with (run_dir / "file_manifest.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def _long_units(run_dir: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (run_dir / "units.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


class DeterministicTexGeneratedMarkerTests(unittest.TestCase):
    def test_comment_case_body_protected_and_false_positive_boundaries(self) -> None:
        markers, problems = long_preparer.deterministic_tex_generation_markers(
            "% THIS FILE WAS AUTO-GENERATED BY BuildTool 2.0\n正文。\n"
        )
        self.assertFalse(problems)
        self.assertEqual(
            [item["marker_id"] for item in markers],
            ["TEX_COMMENT_EN_GENERATED_BY"],
        )
        for text in (
            "This file was auto-generated by BuildTool.\n正文。\n",
            (
                "\\begin{verbatim}\n"
                "% This file was generated by ProtectedExample\n"
                "\\end{verbatim}\n"
                "% This chapter discusses text generated by models.\n正文。\n"
            ),
        ):
            observed, observed_problems = (
                long_preparer.deterministic_tex_generation_markers(text)
            )
            self.assertFalse(observed_problems)
            self.assertEqual(observed, [])


class LongDocumentSourceRoleGateTests(unittest.TestCase):
    def test_nested_alias_gb18030_include_is_retained_not_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "chapters").mkdir()
            (root / "generated").mkdir()
            main = root / "main.tex"
            bridge = root / "chapters" / "bridge.tex"
            generated = root / "generated" / "table.tex"
            main.write_text("主文正文。\\input{chapters/bridge}\n", encoding="utf-8")
            bridge.write_text(
                "桥接正文。\\input{../generated/table}\n"
                "\\input{../generated/./table.tex}\n",
                encoding="utf-8",
            )
            generated.write_bytes(
                "% 本文件由数据工具自动生成，请勿编辑。\n生成内容。\n".encode(
                    "gb18030"
                )
            )
            run_dir = root / "run"
            metadata = long_preparer.prepare([main], run_dir, scene="GENERAL")
            rows = [
                row
                for row in _long_manifest(run_dir)
                if Path(row["path"]).resolve() == generated.resolve()
            ]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual((row["encoding"], row["source_role"]), ("gb18030", "GENERATED"))
            self.assertEqual(
                row["source_processing_status"], "RETAINED_GENERATED_NO_AUTHORING"
            )
            evidence = json.loads(row["source_role_evidence"])
            self.assertIn(
                "TEX_COMMENT_ZH_GENERATED_BY",
                [item.get("marker_id") for item in evidence],
            )
            self.assertTrue((run_dir / row["snapshot_copy"]).is_file())
            self.assertFalse(
                any(unit["file_id"] == row["file_id"] for unit in _long_units(run_dir))
            )
            self.assertEqual(metadata["source_role_summary"]["GENERATED"], 1)
            preflight = long_finalizer.validate_long_authoring_snapshot(run_dir)
            self.assertEqual(preflight["summary"]["integrity_status"], "PASS")


class InlineWorkflowTests(unittest.TestCase):
    def _invoke(self, *args: str | Path) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(INLINE_PATH), *(str(item) for item in args)],
            check=False,
            capture_output=True,
        )

    def _payload(self, completed: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
        self.assertTrue(completed.stdout, completed.stderr.decode("utf-8", errors="replace"))
        payload = json.loads(completed.stdout.decode("utf-8"))
        self.assertIsInstance(payload, dict)
        return payload

    def _template_scope(
        self,
        root: Path,
        before: Path,
        *,
        label: str,
        line: int = 1,
    ) -> Path:
        scope = root / "template-field-edit-scope.json"
        scope.write_text(
            json.dumps(
                {
                    "schema_version": "humanize-template-field-edit-scope/v1",
                    "source_sha256": hashlib.sha256(before.read_bytes()).hexdigest(),
                    "edits": [
                        {
                            "line": line,
                            "label": label,
                            "permission": "PAYLOAD_ONLY",
                            "reason": (
                                "用户明确授权调整该字段载荷的表达，同时保持原句范围、"
                                "字段功能和结论力度不变。"
                            ),
                        }
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return scope

    def _valid_rewrite_run(self, root: Path) -> tuple[dict[str, object], Path]:
        before = root / "before.md"
        after = root / "after.md"
        before.write_text("甲组温度为20摄氏度，乙组温度为25摄氏度。", encoding="utf-8")
        after.write_text("甲组温度为20摄氏度，乙组温度为25摄氏度。", encoding="utf-8")
        completed = self._invoke(
            "run",
            before,
            after,
            "--output-root",
            root / "runs",
            "--mode",
            "REWRITE",
            "--scene",
            "RESEARCH",
            "--document-format",
            "markdown",
            "--visible-output",
            "BODY_ONLY",
            "--strict-speech-acts",
        )
        self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
        payload = self._payload(completed)
        self.assertEqual(payload["mechanical_validation_status"], "PASS")
        self.assertEqual(payload["delivery_gate_status"], "REVIEW")
        self.assertTrue(payload["body_emission_allowed"])
        self.assertFalse(payload["completion_claim_allowed"])
        return payload, after

    def test_run_emit_and_attest_preserve_exact_candidate_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, after = self._valid_rewrite_run(root)
            run_dir = Path(str(payload["run_dir"]))

            emitted = self._invoke("emit", run_dir, "--format", "body")
            self.assertEqual(emitted.returncode, 2)
            self.assertEqual(emitted.stdout, after.read_bytes())
            self.assertEqual(emitted.stderr, b"")

            attested = self._invoke("attest", run_dir, after)
            self.assertEqual(attested.returncode, 0)
            attestation = self._payload(attested)
            self.assertEqual(attestation["status"], "PASS")
            self.assertTrue(attestation["byte_identity"])

            mismatch = root / "visible-mismatch.md"
            mismatch.write_bytes(after.read_bytes() + b"\n")
            rejected = self._invoke("attest", run_dir, mismatch)
            self.assertEqual(rejected.returncode, 1)
            rejection = self._payload(rejected)
            self.assertEqual(rejection["status"], "FAIL")
            self.assertFalse(rejection["byte_identity"])

    def test_emit_fails_closed_after_snapshot_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, _ = self._valid_rewrite_run(root)
            run_dir = Path(str(payload["run_dir"]))
            record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            after_snapshot = run_dir / record["artifacts"]["after"]["path"]
            after_snapshot.write_bytes(after_snapshot.read_bytes() + b" ")

            emitted = self._invoke("emit", run_dir, "--format", "json")
            self.assertEqual(emitted.returncode, 1)
            verification = self._payload(emitted)
            self.assertEqual(verification["status"], "FAIL")
            self.assertFalse(verification["body_emission_allowed"])
            self.assertIn("artifact_sha256_mismatch:after", verification["reason"])

    def test_draft_fragment_combination_is_rejected_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text("给定材料。", encoding="utf-8")
            after.write_text("给定材料。", encoding="utf-8")
            output_root = root / "runs"
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                output_root,
                "--mode",
                "DRAFT",
                "--scene",
                "GENERAL",
                "--document-format",
                "markdown",
                "--fragment",
            )
            self.assertEqual(completed.returncode, 1)
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "FAIL")
            self.assertEqual(payload["delivery_gate_status"], "FAIL")
            self.assertEqual(payload["review_reasons"], ["fragment_requires_rewrite"])
            self.assertFalse(output_root.exists())

    def test_tex_numeric_payload_drift_blocks_body_emission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.tex"
            after = root / "after.tex"
            before.write_text(
                "\\section{结果}\n固定参数为 $x=1$，样本数为 20。\n",
                encoding="utf-8",
            )
            after.write_text(
                "\\section{结果}\n固定参数为 $x=2$，样本数为 20。\n",
                encoding="utf-8",
            )
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "tex",
            )
            self.assertEqual(completed.returncode, 1)
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "FAIL")
            self.assertEqual(payload["delivery_gate_status"], "FAIL")
            self.assertFalse(payload["body_emission_allowed"])
            self.assertFalse(payload["completion_claim_allowed"])

    def test_non_utf8_input_is_rejected_without_a_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_bytes(b"\xff\xfe\x00")
            after.write_text("候选正文。", encoding="utf-8")
            output_root = root / "runs"
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                output_root,
                "--mode",
                "REWRITE",
                "--scene",
                "GENERAL",
                "--document-format",
                "markdown",
            )
            self.assertEqual(completed.returncode, 1)
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "FAIL")
            self.assertIn("input_not_utf8:before", payload["review_reasons"][0])
            self.assertFalse(output_root.exists())

    def test_review_diagnostics_expose_actionable_finding_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            text = "上述记录为后续分析奠定了基础。\n"
            before.write_text(text, encoding="utf-8")
            after.write_text(text, encoding="utf-8")
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "GENERAL",
                "--document-format",
                "markdown",
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            diagnostics = payload["diagnostics"]
            self.assertGreaterEqual(diagnostics["actionable_finding_count"], 1)
            finding = next(
                item
                for item in diagnostics["actionable_findings"]
                if item["signal_id"] == "LEX-FOUNDATION-01"
            )
            self.assertEqual(finding["matched"], "为后续分析奠定了基础")
            self.assertEqual(finding["action"], "DELETE")
            self.assertEqual(finding["line"], 1)
            self.assertGreater(finding["column"], 0)
            self.assertIn("unexplained_high", finding["diagnostic_roles"])

    def test_strict_corpus_hit_blocks_unchanged_candidate_until_position_keep(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            text = "这个写法会更稳。"
            before.write_text(text, encoding="utf-8")
            after.write_text(text, encoding="utf-8")
            blocked = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "blocked-runs",
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "markdown",
            )
            self.assertEqual(blocked.returncode, 2, blocked.stderr.decode("utf-8"))
            blocked_payload = self._payload(blocked)
            self.assertEqual(blocked_payload["mechanical_validation_status"], "REVIEW")
            self.assertFalse(blocked_payload["body_emission_allowed"])
            self.assertGreater(
                blocked_payload["diagnostics"]["strict_unexplained_count"], 0
            )
            self.assertFalse(
                blocked_payload["diagnostics"]["strict_no_change_allowed"]
            )
            strict_findings = [
                item
                for item in blocked_payload["diagnostics"]["actionable_findings"]
                if item["signal_id"] == "LEX-STRICT-CORPUS-CERTAINTY-01"
            ]
            self.assertTrue(strict_findings)
            self.assertEqual(strict_findings[0]["matched"], "会更稳")

            allowed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "allowed-runs",
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "markdown",
                "--keep-reason",
                "LEX-STRICT-CORPUS-CERTAINTY-01@1:5=此处是已有结论中的确定性措辞，需要人工核对",
            )
            self.assertEqual(allowed.returncode, 2, allowed.stderr.decode("utf-8"))
            allowed_payload = self._payload(allowed)
            self.assertEqual(allowed_payload["mechanical_validation_status"], "PASS")
            self.assertTrue(allowed_payload["body_emission_allowed"])
            self.assertEqual(
                allowed_payload["diagnostics"]["strict_unexplained_count"], 0
            )
            self.assertTrue(
                allowed_payload["diagnostics"]["strict_no_change_allowed"]
            )

    def test_speech_act_warning_exposes_actionable_source_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text(
                "四大家鱼的食性不同，决定了它们的作用并不一致。",
                encoding="utf-8",
            )
            after.write_text(
                "四大家鱼食性各异，其作用并不相同。",
                encoding="utf-8",
            )
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "markdown",
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "REVIEW")
            diagnostics = payload["diagnostics"]
            finding = next(
                item
                for item in diagnostics["actionable_findings"]
                if item["signal_id"] == "SPEECH_ACT_NEGATION_CHANGED"
            )
            self.assertEqual(finding["diagnostic_roles"], ["pending_warning"])
            self.assertEqual(finding["action"], "RESTORE_SOURCE_FORCE")
            self.assertEqual(finding["source_side"], "before")
            self.assertEqual(finding["file"], "before")
            self.assertEqual(finding["matched"], "不")
            self.assertEqual(finding["line"], 1)
            self.assertGreater(finding["column"], 0)
            self.assertIn("四大家鱼", finding["sentence_context"])
            self.assertRegex(finding["finding_hash"], r"^[0-9a-f]{64}$")

    def test_template_field_review_exposes_repairs_and_still_blocks_emit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.tex"
            after = root / "after.tex"
            before.write_text(
                "适用题目： 积极的、普遍认可的趋势。\n"
                "逻辑链条： 给定首句。这不仅顺应时代演变，更是个人发展的关键。\n",
                encoding="utf-8",
            )
            after.write_text(
                "适用题目：积极且普遍认可的趋势。\n"
                "逻辑链条：给定首句后，先说明这一趋势如何回应时代变化，再指出其作用。\n",
                encoding="utf-8",
            )
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "COURSE",
                "--document-format",
                "tex",
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "REVIEW")
            self.assertEqual(payload["delivery_gate_status"], "REVIEW")
            self.assertFalse(payload["body_emission_allowed"])
            diagnostics = payload["diagnostics"]
            self.assertEqual(diagnostics["template_field_count"], 2)
            self.assertGreaterEqual(diagnostics["actionable_finding_count"], 2)
            findings = [
                item
                for item in diagnostics["actionable_findings"]
                if "template_field" in item["diagnostic_roles"]
            ]
            self.assertEqual(len(findings), 2)
            self.assertEqual(
                {item["field_label"] for item in findings},
                {"适用题目", "逻辑链条"},
            )
            for finding in findings:
                self.assertEqual(
                    finding["signal_id"],
                    "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED",
                )
                self.assertEqual(finding["error_code"], finding["signal_id"])
                self.assertEqual(finding["action"], "RESTORE_OR_AUTHORIZE_PAYLOAD")
                self.assertEqual(finding["diagnostic_roles"], ["template_field"])
                self.assertEqual(finding["source_line"], finding["after_line"])
                self.assertEqual(finding["line"], finding["after_line"])
                self.assertEqual(finding["column"], 1)
                self.assertEqual(finding["source_side"], "after")
                self.assertEqual(finding["authorization_status"], "NOT_AUTHORIZED")
                self.assertTrue(finding["payload_role"].startswith("EDITORIAL_PAYLOAD/"))

            run_dir = Path(str(payload["run_dir"]))
            emitted = self._invoke("emit", run_dir, "--format", "body")
            self.assertEqual(emitted.returncode, 2)
            self.assertEqual(emitted.stdout, b"")
            verification = json.loads(emitted.stderr.decode("utf-8"))
            self.assertFalse(verification["body_emission_allowed"])
            self.assertEqual(
                verification["reason"],
                "validated_candidate_is_not_mechanically_clear",
            )

    def test_authorized_template_payload_is_frozen_bound_and_emittable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text(
                "适用题目： 连续变量条件下的估计问题。\n", encoding="utf-8"
            )
            after.write_text("适用题目： 连续变量下的估计问题。\n", encoding="utf-8")
            scope = self._template_scope(root, before, label="适用题目")
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "COURSE",
                "--document-format",
                "markdown",
                "--template-field-edit-scope",
                scope,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            self.assertEqual(payload["schema_version"], "humanize-inline-run/v3")
            self.assertEqual(payload["mechanical_validation_status"], "PASS")
            self.assertTrue(payload["body_emission_allowed"])
            run_dir = Path(str(payload["run_dir"]))
            record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            scope_record = record["artifacts"]["template_field_edit_scope"]
            self.assertTrue(scope_record["provided"])
            self.assertEqual(scope_record["sha256"], hashlib.sha256(scope.read_bytes()).hexdigest())
            self.assertEqual(scope_record["source_sha256"], hashlib.sha256(before.read_bytes()).hexdigest())
            frozen_scope = run_dir / scope_record["path"]
            self.assertEqual(frozen_scope.read_bytes(), scope.read_bytes())
            invocation = json.loads((run_dir / "invocation.json").read_text(encoding="utf-8"))
            self.assertEqual(invocation["schema_version"], "humanize-inline-invocation/v2")
            self.assertEqual(invocation["template_field_edit_scope"], scope_record)
            evidence_dir = run_dir / "evidence"
            self.assertEqual(
                (evidence_dir / "inputs" / "template-field-edit-scope.json").read_bytes(),
                scope.read_bytes(),
            )
            evidence_invocation = json.loads(
                (evidence_dir / "invocation-request.json").read_text(encoding="utf-8")
            )
            evidence_scope = evidence_invocation["arguments"]["template_field_edit_scope"]
            self.assertEqual(evidence_scope["permission_boundary"], "PAYLOAD_ONLY")
            self.assertFalse(evidence_scope["local_clearance_supported"])

            emitted = self._invoke("emit", run_dir, "--format", "body")
            self.assertEqual(emitted.returncode, 2)
            self.assertEqual(emitted.stdout, after.read_bytes())

    def test_authorization_cannot_clear_template_role_or_force_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text(
                "逻辑链条： 该结果并非外部验证。\n", encoding="utf-8"
            )
            after.write_text("逻辑链条： 该结果是外部验证。\n", encoding="utf-8")
            scope = self._template_scope(root, before, label="逻辑链条")
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "RESEARCH",
                "--document-format",
                "markdown",
                "--template-field-edit-scope",
                scope,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "REVIEW")
            self.assertFalse(payload["body_emission_allowed"])
            self.assertIn(
                "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT",
                payload["diagnostics"]["template_field_codes"],
            )

    def test_authorization_cannot_clear_template_header_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text(
                "适用题目： 连续变量条件下的估计问题。\n", encoding="utf-8"
            )
            after.write_text(
                "适用题目: 连续变量条件下的估计问题。\n", encoding="utf-8"
            )
            scope = self._template_scope(root, before, label="适用题目")
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "COURSE",
                "--document-format",
                "markdown",
                "--template-field-edit-scope",
                scope,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            self.assertEqual(payload["mechanical_validation_status"], "FAIL")
            self.assertFalse(payload["body_emission_allowed"])
            self.assertIn(
                "TEMPLATE_FIELD_HEADER_CHANGED",
                payload["diagnostics"]["template_field_codes"],
            )

    def test_template_scope_tampering_blocks_emit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text(
                "适用题目： 连续变量条件下的估计问题。\n", encoding="utf-8"
            )
            after.write_text("适用题目： 连续变量下的估计问题。\n", encoding="utf-8")
            scope = self._template_scope(root, before, label="适用题目")
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                root / "runs",
                "--mode",
                "REWRITE",
                "--scene",
                "COURSE",
                "--document-format",
                "markdown",
                "--template-field-edit-scope",
                scope,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr.decode("utf-8"))
            payload = self._payload(completed)
            run_dir = Path(str(payload["run_dir"]))
            scope_path = run_dir / payload["artifacts"]["template_field_edit_scope"]["path"]
            scope_path.write_bytes(scope_path.read_bytes() + b" ")

            emitted = self._invoke("emit", run_dir, "--format", "json")
            self.assertEqual(emitted.returncode, 1)
            verification = self._payload(emitted)
            self.assertEqual(verification["status"], "FAIL")
            self.assertIn(
                "artifact_sha256_mismatch:template_field_edit_scope",
                verification["reason"],
            )

    def test_draft_template_scope_is_rejected_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.md"
            after = root / "after.md"
            before.write_text("适用题目： 给定材料。\n", encoding="utf-8")
            after.write_text("适用题目： 给定材料。\n", encoding="utf-8")
            scope = self._template_scope(root, before, label="适用题目")
            output_root = root / "runs"
            completed = self._invoke(
                "run",
                before,
                after,
                "--output-root",
                output_root,
                "--mode",
                "DRAFT",
                "--scene",
                "GENERAL",
                "--document-format",
                "markdown",
                "--template-field-edit-scope",
                scope,
            )
            self.assertEqual(completed.returncode, 1)
            payload = self._payload(completed)
            self.assertEqual(
                payload["review_reasons"],
                ["template_field_edit_scope_requires_rewrite"],
            )
            self.assertFalse(output_root.exists())

    def test_legacy_v2_run_without_scope_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, after = self._valid_rewrite_run(root)
            run_dir = Path(str(payload["run_dir"]))
            record_path = run_dir / "run.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            invocation_path = run_dir / record["artifacts"]["invocation"]["path"]
            invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
            invocation["schema_version"] = "humanize-inline-invocation/v1"
            invocation.pop("template_field_edit_scope")
            invocation_raw = (
                json.dumps(
                    invocation,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            invocation_path.write_bytes(invocation_raw)
            record["schema_version"] = "humanize-inline-run/v2"
            record["artifacts"].pop("template_field_edit_scope")
            record["artifacts"]["invocation"]["sha256"] = hashlib.sha256(
                invocation_raw
            ).hexdigest()
            record["artifacts"]["invocation"]["size_bytes"] = len(invocation_raw)
            record_path.write_text(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            emitted = self._invoke("emit", run_dir, "--format", "body")
            self.assertEqual(emitted.returncode, 2, emitted.stderr.decode("utf-8"))
            self.assertEqual(emitted.stdout, after.read_bytes())


class LongDocumentSourceRoleAdditionalTests(unittest.TestCase):
    def test_path_only_signal_is_unresolved_and_not_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build").mkdir()
            main = root / "main.tex"
            included = root / "build" / "manual.tex"
            main.write_text("主文正文。\\include{build/manual}\n", encoding="utf-8")
            included.write_text("这是人工编写但路径可疑的正文。\n", encoding="utf-8")
            run_dir = root / "run"
            metadata = long_preparer.prepare([main], run_dir, scene="GENERAL")
            row = next(
                item
                for item in _long_manifest(run_dir)
                if Path(item["path"]).resolve() == included.resolve()
            )
            self.assertEqual(row["source_role"], "UNRESOLVED")
            self.assertEqual(
                row["source_processing_status"],
                "UNRESOLVED_SOURCE_ROLE_NO_AUTHORING",
            )
            self.assertEqual(metadata["status"], "REVIEW")
            self.assertFalse(
                any(unit["file_id"] == row["file_id"] for unit in _long_units(run_dir))
            )

    def test_seed_and_include_markers_both_exclude_author_units(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed.tex"
            child = root / "child.tex"
            seed.write_text(
                "% Auto-generated file; do not edit.\n生成种子正文。\\input{child}\n",
                encoding="utf-8",
            )
            child.write_text(
                "% This file is generated by NestedTool\n生成子文件正文。\n",
                encoding="utf-8",
            )
            run_dir = root / "run"
            long_preparer.prepare([seed], run_dir, scene="GENERAL")
            self.assertEqual(
                {row["source_role"] for row in _long_manifest(run_dir)},
                {"GENERATED"},
            )
            self.assertEqual(_long_units(run_dir), [])

    def test_caller_override_is_strict_frozen_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "generated").mkdir()
            main = root / "main.tex"
            included = root / "generated" / "manual.tex"
            main.write_text("主文正文。\\input{generated/manual}\n", encoding="utf-8")
            included.write_text("调用方确认纳入本轮的正文。\n", encoding="utf-8")
            override = root / "source-roles.json"
            override.write_text(
                json.dumps(
                    {
                        "schema_version": long_preparer.SOURCE_ROLE_OVERRIDE_SCHEMA,
                        "overrides": [
                            {
                                "path": "generated/../generated/manual.tex",
                                "source_role": "AUTHOR_TEXT",
                                "reason": "Caller explicitly reviewed this file for authoring scope.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            run_dir = root / "run"
            metadata = long_preparer.prepare(
                [main],
                run_dir,
                scene="GENERAL",
                source_role_overrides=override,
            )
            row = next(
                item
                for item in _long_manifest(run_dir)
                if Path(item["path"]).resolve() == included.resolve()
            )
            self.assertEqual(row["source_role"], "AUTHOR_TEXT")
            self.assertEqual(
                row["source_processing_status"],
                "AUTHORING_QUEUE_BY_CALLER_OVERRIDE",
            )
            self.assertIn(
                "CALLER_SCOPE_OVERRIDE",
                [item["kind"] for item in json.loads(row["source_role_evidence"])],
            )
            frozen = json.loads(
                (run_dir / "source_role_overrides.json").read_text(encoding="utf-8")
            )
            self.assertEqual(frozen["authority"], long_preparer.SOURCE_ROLE_OVERRIDE_AUTHORITY)
            self.assertEqual(
                frozen["overrides"][0]["applied_files"],
                [{"file_id": row["file_id"], "snapshot_sha256": row["sha256"]}],
            )
            self.assertEqual(metadata["source_role_override_status"], "APPLIED")
            self.assertTrue(
                any(unit["file_id"] == row["file_id"] for unit in _long_units(run_dir))
            )
            preflight = long_finalizer.validate_long_authoring_snapshot(run_dir)
            self.assertEqual(preflight["summary"]["integrity_status"], "PASS")

    def test_live_source_change_after_snapshot_downgrades_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "main.tex"
            main.write_text("作者正文。\n", encoding="utf-8")
            run_dir = root / "run"
            long_preparer.prepare([main], run_dir, scene="GENERAL")

            main.write_text("作者正文已在快照后变化。\n", encoding="utf-8")
            preflight = long_finalizer.validate_long_authoring_snapshot(run_dir)
            summary = preflight["summary"]
            self.assertEqual(summary["status"], "REVIEW")
            self.assertEqual(summary["live_source_status"], "NOT_CURRENT")
            self.assertEqual(len(summary["source_change_units"]), 1)
            self.assertEqual(
                summary["source_change_units"][0]["current_state"], "MODIFIED"
            )
            self.assertFalse(summary["completion_claim_allowed"])

    def test_frozen_source_copy_tampering_fails_authoring_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "main.tex"
            main.write_text("作者正文。\n", encoding="utf-8")
            run_dir = root / "run"
            long_preparer.prepare([main], run_dir, scene="GENERAL")
            row = next(
                item
                for item in _long_manifest(run_dir)
                if Path(item["path"]).resolve() == main.resolve()
            )
            frozen = run_dir / row["snapshot_copy"]
            frozen.write_bytes(frozen.read_bytes() + b" ")

            with self.assertRaisesRegex(
                ValueError, "prepare source copy hash mismatch"
            ):
                long_finalizer.validate_long_authoring_snapshot(run_dir)


@unittest.skipUnless(os.name == "nt", "secure scaffold publication requires Windows")
class LongDocumentScaffoldFinalizeTests(unittest.TestCase):
    def _prepare_scaffold(self, root: Path, decision: str = "REWRITE") -> tuple[Path, Path]:
        source = root / "article.md"
        source.write_text(
            "甲组水温为20摄氏度。需要指出的是，乙组水温为25摄氏度。"
            "两组均测三次。\n",
            encoding="utf-8",
        )
        run_dir = root / "run"
        long_preparer.prepare([source], run_dir, scene="GENERAL")
        self.assertEqual(len(_long_units(run_dir)), 1)
        rewrites_dir = root / "rewrites"
        result = long_scaffolder.scaffold(
            run_dir,
            rewrites_dir,
            decision=decision,
        )
        self.assertFalse(result["completion_claim_allowed"])
        self.assertTrue(result["requires_manual_completion"])
        return run_dir, rewrites_dir

    def _completed_rewrite_bundle(
        self,
        run_dir: Path,
        rewrites_dir: Path,
    ) -> tuple[Path, dict[str, Any], str]:
        unit = _long_units(run_dir)[0]
        unit_id = str(unit["unit_id"])
        chunk = json.loads(
            (run_dir / "chunks" / f"{unit_id}.json").read_text(encoding="utf-8")
        )
        bundle_path = rewrites_dir / f"{unit_id}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        masked_before = str(chunk["masked_text"])
        masked_after = masked_before.replace("需要指出的是，", "")
        self.assertNotEqual(masked_before, masked_after)
        source_lines = (
            masked_before.replace("\r\n", "\n")
            .replace("\r", "\n")
            .splitlines(keepends=True)
        )
        self.assertEqual(len(source_lines), 1)
        source_span = {
            "id": "S1",
            "start_line": 1,
            "end_line": 1,
            "sha256": long_finalizer.sha256(source_lines[0].encode("utf-8")),
        }
        signal = "STYLE-EMPTY-METADISCOURSE"
        summary = "删除不承担内容功能的提示壳，保留两组测量关系"
        bundle["masked_text"] = masked_after
        bundle["rewrite_intent"] = {
            "summary": summary,
            "operations": [
                {
                    "id": "O1",
                    "kind": "REWRITE_STYLE_SHELL",
                    "source_span_ids": ["S1"],
                    "target_signals": [signal],
                    "summary": summary,
                }
            ],
            "source_spans": [source_span],
            "target_signals": [signal],
        }
        return bundle_path, bundle, masked_before

    def _write_bundle(self, path: Path, bundle: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_decision_map_requires_exact_pending_unit_coverage(self) -> None:
        chunks = [{"unit_id": "U-a"}, {"unit_id": "U-b"}]
        self.assertEqual(
            long_scaffolder._normalize_decisions(
                chunks,
                None,
                {"U-a": "rewrite", "U-b": "NO_CHANGE"},
            ),
            {"U-a": "REWRITE", "U-b": "NO_CHANGE"},
        )
        for invalid in (
            {"U-a": "REWRITE"},
            {"U-a": "REWRITE", "U-b": "NO_CHANGE", "U-c": "REWRITE"},
            {"U-a": "REWRITE", "U-b": "SKIP"},
        ):
            with self.assertRaises(ValueError):
                long_scaffolder._normalize_decisions(chunks, None, invalid)
        with self.assertRaises(ValueError):
            long_scaffolder._normalize_decisions(
                chunks,
                "REWRITE",
                {"U-a": "REWRITE", "U-b": "NO_CHANGE"},
            )

    def test_pristine_scaffold_is_actionable_review_not_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            bundle_path = next(
                path for path in rewrites_dir.glob("U-*.json") if path.is_file()
            )
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(
                bundle["rewrite_intent"]["summary"],
                long_finalizer.REWRITE_INTENT_TODO,
            )

            metadata = long_finalizer.finalize(run_dir, rewrites_dir)
            self.assertEqual(metadata["delivery_gate_status"], "REVIEW")
            self.assertFalse(metadata["humanize_completion_claim_allowed"])
            counts = metadata["unresolved_reason_summary"][
                "structured_code_counts"
            ]
            self.assertEqual(counts["REWRITE_INTENT_AUTHORING_INCOMPLETE"], 1)
            self.assertEqual(counts["REWRITE_INTENT_SOURCE_SPANS_EMPTY"], 1)
            actions = metadata["unresolved_reason_summary"][
                "actionable_next_actions"
            ]
            self.assertTrue(
                any(
                    item["reason_code"] == "REWRITE_INTENT_AUTHORING_INCOMPLETE"
                    for item in actions
                )
            )

    def test_scaffold_cli_exposes_required_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "article.md"
            source.write_text(
                "本段记录实验对象、控制条件和观察范围，三者保持原有顺序。\n",
                encoding="utf-8",
            )
            run_dir = root / "run"
            long_preparer.prepare([source], run_dir, scene="GENERAL")
            rewrites_dir = root / "rewrites"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = long_scaffolder.main(
                    [
                        "--run-dir",
                        str(run_dir),
                        "--output",
                        str(rewrites_dir),
                        "--decision",
                        "REWRITE",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["authoring_state"], "PENDING_TEMPLATE_COMPLETION"
            )
            self.assertTrue(payload["do_not_finalize_pristine_scaffold"])
            self.assertEqual(
                payload["next_action"]["action"],
                "COMPLETE_EVERY_TEMPLATE_BEFORE_FINALIZE",
            )
            self.assertIn(
                "rewrite_intent.source_spans",
                payload["rewrite_intent_authoring_contract"][
                    "required_rewrite_fields"
                ],
            )
            contract = payload["rewrite_intent_authoring_contract"]
            self.assertEqual(
                contract["operation_contract"]["exact_fields"],
                [
                    "id",
                    "kind",
                    "source_span_ids",
                    "target_signals",
                    "summary",
                ],
            )
            self.assertEqual(
                contract["source_span_contract"]["exact_fields"],
                ["id", "start_line", "end_line", "sha256"],
            )
            self.assertTrue(
                contract["source_span_contract"]["line_endings_are_hashed"]
            )
            example_context = contract["hash_example_context"]
            example_line = example_context["selected_line_including_line_ending"]
            self.assertEqual(
                example_context["selected_line_sha256"],
                long_finalizer.sha256(example_line.encode("utf-8")),
            )
            long_finalizer._validate_rewrite_intent_shape(
                contract["valid_rewrite_intent_example"]
            )

    def test_invalid_operation_fields_have_specific_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            bundle_path, bundle, _masked_before = self._completed_rewrite_bundle(
                run_dir, rewrites_dir
            )
            bundle["rewrite_intent"]["operations"][0]["rationale"] = (
                "错误的非合同字段"
            )
            self._write_bundle(bundle_path, bundle)

            metadata = long_finalizer.finalize(run_dir, rewrites_dir)
            summary = metadata["unresolved_reason_summary"]
            self.assertEqual(
                summary["structured_code_counts"][
                    "REWRITE_INTENT_OPERATION_FIELDS_INVALID"
                ],
                1,
            )
            actions = {
                item["reason_code"]: item["action"]
                for item in summary["actionable_next_actions"]
            }
            self.assertEqual(
                actions["REWRITE_INTENT_OPERATION_FIELDS_INVALID"],
                "USE_OPERATION_EXACT_FIELDS_ID_KIND_SOURCE_SPAN_IDS_TARGET_SIGNALS_SUMMARY",
            )
            self.assertFalse(metadata["humanize_completion_claim_allowed"])

    def test_invalid_source_span_fields_have_specific_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            bundle_path, bundle, _masked_before = self._completed_rewrite_bundle(
                run_dir, rewrites_dir
            )
            bundle["rewrite_intent"]["source_spans"][0]["unit_hash"] = (
                bundle["rewrite_intent"]["source_spans"][0]["sha256"]
            )
            self._write_bundle(bundle_path, bundle)

            metadata = long_finalizer.finalize(run_dir, rewrites_dir)
            summary = metadata["unresolved_reason_summary"]
            self.assertEqual(
                summary["structured_code_counts"][
                    "REWRITE_INTENT_SOURCE_SPANS_FIELDS_INVALID"
                ],
                1,
            )
            self.assertTrue(summary["actionable_next_actions"])

    def test_whole_unit_hash_cannot_impersonate_partial_source_span(self) -> None:
        masked_before = "第一行保留。\n第二行需要改写。\n"
        whole_unit_hash = long_finalizer.sha256(masked_before.encode("utf-8"))
        spans = [
            {
                "id": "S1",
                "start_line": 2,
                "end_line": 2,
                "sha256": whole_unit_hash,
            }
        ]
        with self.assertRaisesRegex(
            ValueError,
            r"rewrite_intent_source_spans_sha256_mismatch:S1",
        ):
            long_finalizer._validate_intent_span_bindings(
                spans,
                masked_before,
                "rewrite_intent_source_spans",
            )

    def test_intent_builder_generates_bound_fragment_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            unit_id = str(_long_units(run_dir)[0]["unit_id"])
            bundle_path = rewrites_dir / f"{unit_id}.json"
            before_bundle = bundle_path.read_bytes()
            payload = intent_builder.build_intent(
                run_dir,
                unit_id,
                1,
                1,
                "REWRITE_STYLE_SHELL",
                ["STYLE-EMPTY-METADISCOURSE"],
                "删除空泛提示壳并保留两组测量关系",
            )
            self.assertEqual(payload["status"], "GENERATED_AUTHORING_FRAGMENT")
            self.assertFalse(payload["writes_performed"])
            self.assertFalse(payload["completion_claim_allowed"])
            long_finalizer._validate_rewrite_intent_shape(
                payload["rewrite_intent"]
            )
            self.assertEqual(bundle_path.read_bytes(), before_bundle)

    def test_intent_builder_rejects_out_of_range_and_generic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, _rewrites_dir = self._prepare_scaffold(Path(temporary))
            unit_id = str(_long_units(run_dir)[0]["unit_id"])
            common = (run_dir, unit_id, 1, 1, "REWRITE_STYLE_SHELL")
            with self.assertRaisesRegex(ValueError, "summary_must_be_specific"):
                intent_builder.build_intent(
                    *common,
                    ["STYLE-EMPTY-METADISCOURSE"],
                    "优化表达",
                )
            with self.assertRaisesRegex(ValueError, "source_line_range_out_of_bounds"):
                intent_builder.build_intent(
                    run_dir,
                    unit_id,
                    2,
                    2,
                    "REWRITE_STYLE_SHELL",
                    ["STYLE-EMPTY-METADISCOURSE"],
                    "删除空泛提示壳并保留两组测量关系",
                )

    def test_bound_source_span_hash_mismatch_has_specific_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            bundle_path, bundle, _masked_before = self._completed_rewrite_bundle(
                run_dir, rewrites_dir
            )
            bundle["rewrite_intent"]["source_spans"][0]["sha256"] = "0" * 64
            self._write_bundle(bundle_path, bundle)

            metadata = long_finalizer.finalize(run_dir, rewrites_dir)
            summary = metadata["unresolved_reason_summary"]
            self.assertEqual(
                summary["structured_code_counts"][
                    "REWRITE_INTENT_SOURCE_SPANS_HASH_MISMATCH"
                ],
                1,
            )
            actions = {
                item["reason_code"]: item["action"]
                for item in summary["actionable_next_actions"]
            }
            self.assertEqual(
                actions["REWRITE_INTENT_SOURCE_SPANS_HASH_MISMATCH"],
                "RECOMPUTE_SHA256_FROM_NORMALIZED_LF_FROZEN_MASKED_SOURCE_LINES_WITH_LINE_ENDINGS",
            )

    def test_rewrite_intent_diff_errors_map_to_closed_action_codes(self) -> None:
        cases = {
            "rewrite_intent_operation_source_spans_invalid": (
                "REWRITE_INTENT_OPERATION_SOURCE_SPANS_INVALID"
            ),
            "rewrite_intent_operation_target_signals_invalid": (
                "REWRITE_INTENT_OPERATION_TARGET_SIGNALS_INVALID"
            ),
            "rewrite_intent_source_span_coverage_incomplete": (
                "REWRITE_INTENT_SOURCE_SPAN_COVERAGE_INCOMPLETE"
            ),
            "rewrite_intent_target_signal_coverage_incomplete": (
                "REWRITE_INTENT_TARGET_SIGNAL_COVERAGE_INCOMPLETE"
            ),
            "rewrite_intent_source_spans_outside_diff:S1": (
                "REWRITE_INTENT_SOURCE_SPANS_OUTSIDE_DIFF"
            ),
            "rewrite_intent_diff_outside_declared_spans:2": (
                "REWRITE_INTENT_DIFF_OUTSIDE_DECLARED_SPANS"
            ),
        }
        for error, expected_code in cases.items():
            with self.subTest(error=error):
                self.assertEqual(
                    long_finalizer._rewrite_authoring_error_code(error),
                    expected_code,
                )
                summary = long_finalizer._unresolved_reason_summary(
                    [
                        {
                            "status": "UNRESOLVED",
                            "unresolved_codes": [expected_code],
                        }
                    ]
                )
                self.assertEqual(
                    summary["structured_code_counts"][expected_code],
                    1,
                )
                self.assertTrue(summary["actionable_next_actions"])

    def test_completed_intent_reaches_review_candidate_without_false_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, rewrites_dir = self._prepare_scaffold(Path(temporary))
            bundle_path, bundle, _masked_before = self._completed_rewrite_bundle(
                run_dir, rewrites_dir
            )
            self._write_bundle(bundle_path, bundle)

            metadata = long_finalizer.finalize(run_dir, rewrites_dir)
            self.assertEqual(metadata["candidate_assembly_status"], "PASS")
            self.assertEqual(metadata["rewrite_intent_coverage_status"], "PASS")
            self.assertEqual(metadata["delivery_gate_status"], "REVIEW")
            self.assertEqual(
                metadata["paired_quality_gate_status"],
                "PENDING_EXTERNAL_REVIEW",
            )
            self.assertFalse(metadata["paired_quality_clearance_granted"])
            self.assertFalse(metadata["humanize_completion_claim_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
