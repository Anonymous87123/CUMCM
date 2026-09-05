#!/usr/bin/env python3
"""Regression tests for the embedded-folder utilization contract."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
AIGC_ROOT = SKILL_ROOT.parent
REGISTRY = SKILL_ROOT / "references" / "stack-registry.json"
CATALOG = SKILL_ROOT / "references" / "folder-utilization.json"

sys.path.insert(0, str(SCRIPT_DIR))

from audit_folder_utilization import audit  # noqa: E402
from run_aigc_adapter import execute  # noqa: E402
from route_aigc_tools import select_route  # noqa: E402


class FolderUtilizationTests(unittest.TestCase):
    def _copied_inputs(self, directory: Path) -> tuple[Path, Path]:
        registry = directory / "stack-registry.json"
        catalog = directory / "folder-utilization.json"
        shutil.copy2(REGISTRY, registry)
        shutil.copy2(SKILL_ROOT / "references" / "role-contracts.json", directory / "role-contracts.json")
        shutil.copy2(CATALOG, catalog)
        return registry, catalog

    def test_default_catalog_covers_all_units(self) -> None:
        report = audit(AIGC_ROOT, REGISTRY, CATALOG)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["top_level_registered"], 21)
        self.assertEqual(report["top_level_discovered"], 21)
        self.assertEqual(report["embedded_manifests_discovered"], 29)
        self.assertEqual(report["embedded_manifests_declared"], 29)
        self.assertEqual(report["dispositions"]["workbench-capability"], 11)
        self.assertEqual(report["dispositions"]["maintenance-only"], 10)
        ai_paper_records = [item for item in report["records"] if item["owner"] == "AI_paper"]
        self.assertEqual(len(ai_paper_records), 16)
        self.assertTrue(all(item["entrypoint_class_verified"] for item in ai_paper_records))

    def test_omitted_embedded_unit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry, catalog = self._copied_inputs(Path(raw))
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["embedded_manifests"].pop()
            catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report = audit(AIGC_ROOT, registry, catalog)
            codes = {item["code"] for item in report["findings"]}
            self.assertEqual(report["status"], "fail")
            self.assertIn("EMBEDDED_MANIFEST_UNREGISTERED", codes)

    def test_tree_hash_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry, catalog = self._copied_inputs(Path(raw))
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["expected_embedded_manifest_tree_sha256"] = "0" * 64
            catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report = audit(AIGC_ROOT, registry, catalog)
            self.assertEqual(report["status"], "fail")
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("EMBEDDED_MANIFEST_TREE_DRIFT", codes)
            self.assertIn("FOLDER_CATALOG_HASH_DRIFT", codes)

    def test_maintenance_unit_cannot_enter_writing_scene(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry, catalog = self._copied_inputs(Path(raw))
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            payload["embedded_manifests"][17]["scenes"] = ["package-maintenance", "mcm"]
            catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            report = audit(AIGC_ROOT, registry, catalog)
            self.assertEqual(report["status"], "fail")
            self.assertIn("MAINTENANCE_CAPABILITY_LEAKS_TO_WRITING", {item["code"] for item in report["findings"]})

    def test_ai_paper_workbench_consumes_embedded_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            report = execute(
                REGISTRY, "AI_paper", "workbench-plan",
                output_dir=Path(raw), document_type="mcm",
            )
            self.assertEqual(report["status"], "pass")
            embedded = report["embedded_capabilities"]
            self.assertEqual(embedded["count"], 16)
            self.assertTrue(all(item["owner"] == "AI_paper" for item in embedded["records"]))
            selected_ids = {item["id"] for item in embedded["selected_records"]}
            self.assertIn("argument-structure-checker", selected_ids)
            self.assertIn("abstract-focus-enhancer", selected_ids)
            self.assertNotIn("academic-tone-polisher", selected_ids)
            self.assertNotIn("literature-searcher", selected_ids)
            self.assertEqual(embedded["selected_count"], 10)
            self.assertTrue(report["plan"]["serial_rewrite_forbidden"])

    def test_each_owner_workbench_exposes_its_embedded_units(self) -> None:
        expected = {
            "AI_paper": (16, {"workbench-capability", "research-only", "independent-alternative"}),
            "GankAIGC-2.1.0": (10, {"maintenance-only"}),
            "humanize-main": (2, {"routed-reviewer", "independent-alternative"}),
            "humanizer-skill-0.1.0": (1, {"canonical-entry"}),
        }
        with tempfile.TemporaryDirectory() as raw:
            for owner, (count, dispositions) in expected.items():
                report = execute(REGISTRY, owner, "workbench-plan", output_dir=Path(raw) / owner)
                self.assertEqual(report["status"], "pass", owner)
                embedded = report["embedded_capabilities"]
                self.assertEqual(embedded["count"], count, owner)
                self.assertEqual({item["disposition"] for item in embedded["records"]}, dispositions, owner)

    def test_route_exposes_ai_paper_embedded_activation(self) -> None:
        report = select_route("mcm", "rewrite", "tex", requested_app="AI_paper")
        self.assertEqual(report["status"], "pass")
        workbench = next(item for item in report["stages"] if item.get("provider") == "AI_paper")
        self.assertTrue(workbench["embedded_capability_plan_required"])
        self.assertIn("run_aigc_adapter.py", workbench["embedded_activation_command"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
