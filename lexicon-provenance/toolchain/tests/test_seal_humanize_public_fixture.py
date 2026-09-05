import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
SCRIPT = SKILL / "scripts" / "seal_humanize_public_fixture.py"
SPEC = importlib.util.spec_from_file_location("seal_humanize_public_fixture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
sealer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sealer
SPEC.loader.exec_module(sealer)


class HumanizePublicFixtureSealerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / "source.md"
        self.prompt = self.root / "request.txt"
        self.input.write_text("值得注意的是，峰值出现在高温组。", encoding="utf-8")
        self.prompt.write_text("请改得自然一些，只输出正文。", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def seal(self, output: Path | None = None):
        return sealer.seal_fixture(
            self.input,
            self.prompt,
            output or (self.root / "sealed"),
            case_id="CASE-001",
            mode="REWRITE",
            scene="RESEARCH",
            intensity="BALANCED",
            output_format="CLEAN",
            report_context="NONE",
            scope="selection",
            title_lock=True,
            structure_lock=False,
        )

    def test_sealer_publishes_runner_valid_fixture(self) -> None:
        result = self.seal()
        self.assertEqual("SEALED", result["status"])
        self.assertEqual("NOT_EVALUATED", result["semantic_leakage_review"])
        runner = sealer._load_runner()
        case = runner.load_public_case(Path(result["output"]))
        self.assertEqual("CASE-001", case.case_id)
        public_context = json.loads(
            case.public_context_path.read_text(encoding="utf-8")
        )
        self.assertEqual("BALANCED", public_context["intensity"])
        self.assertEqual({}, public_context["task_options"])

    def test_sealer_refuses_existing_output(self) -> None:
        output = self.root / "sealed"
        output.mkdir()
        with self.assertRaisesRegex(sealer.SealError, "must not already exist"):
            self.seal(output)

    def test_sealer_rejects_atom_leakage(self) -> None:
        self.prompt.write_text("请按 PATH-05 的预期答案重写。", encoding="utf-8")
        with self.assertRaisesRegex(sealer.SealError, "leaks qualification atom"):
            self.seal()

    def test_sealer_rejects_non_utf8(self) -> None:
        self.input.write_bytes(b"\xff\xfe\x00")
        with self.assertRaisesRegex(sealer.SealError, "not UTF-8"):
            self.seal()

    def test_catalog_public_contexts_are_sealer_reproducible(self) -> None:
        fixture_root = SKILL / "references" / "generation-qualification-fixtures" / "v1"
        cases = {
            "mode-02": {
                "mode": "REWRITE",
                "scene": "RESEARCH",
                "intensity": "BALANCED",
                "output_format": "CLEAN",
                "report_context": "NONE",
                "scope": "document",
                "title_lock": True,
                "structure_lock": False,
                "summary_max_sentences": 1,
            },
            "role-02": {
                "mode": "REWRITE",
                "scene": "GENERAL",
                "intensity": "BALANCED",
                "output_format": "CLEAN",
                "report_context": "REPORT_INFORMED",
                "scope": "selection",
                "title_lock": False,
                "structure_lock": False,
                "locked_literals": ["“我并不认为时间更短就一定更好”"],
                "preserve_numbers_math": True,
            },
            "path-05": {
                "mode": "REWRITE",
                "scene": "RESEARCH",
                "intensity": "BALANCED",
                "output_format": "CLEAN",
                "report_context": "NONE",
                "scope": "document",
                "title_lock": False,
                "structure_lock": False,
                "preserve_three_groups": True,
                "vary_paragraph_rhythm_without_forced_asymmetry": True,
            },
            "long-01": {
                "mode": "REWRITE",
                "scene": "RESEARCH",
                "intensity": "BALANCED",
                "output_format": "PATCH",
                "report_context": "NONE",
                "scope": "document",
                "title_lock": False,
                "structure_lock": True,
                "operation": "PREPARE_LONG_DOCUMENT",
                "required_output_format": "JSON_INCLUDE_MANIFEST",
            },
        }
        for index, (name, options) in enumerate(cases.items(), 1):
            with self.subTest(name=name):
                result = sealer.seal_fixture(
                    fixture_root / f"{name}-input.{ 'tex' if name == 'long-01' else 'md'}",
                    fixture_root / f"{name}-prompt.txt",
                    self.root / f"sealed-{name}",
                    case_id=f"REPRO-{index:03d}",
                    **options,
                )
                actual = Path(result["output"]) / "public-context.json"
                expected = fixture_root / f"{name}-context.json"
                self.assertEqual(expected.read_bytes(), actual.read_bytes())

        result = sealer.seal_fixture(
            fixture_root / "source-a-input.txt",
            fixture_root / "source-provenance-prompt.txt",
            self.root / "sealed-source-provenance",
            case_id="SOURCE-PROVENANCE-001",
            mode="DIAGNOSE",
            scene="GENERAL",
            intensity="LIGHT",
            output_format="ANNOTATED",
            report_context="NONE",
            scope="selection",
            title_lock=True,
            structure_lock=True,
            operation="CLASSIFY_SOURCE_PROVENANCE",
        )
        actual = Path(result["output"]) / "public-context.json"
        expected = fixture_root / "source-provenance-context.json"
        self.assertEqual(expected.read_bytes(), actual.read_bytes())


if __name__ == "__main__":
    unittest.main()
