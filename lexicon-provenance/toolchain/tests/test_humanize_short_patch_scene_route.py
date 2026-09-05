import contextlib
import importlib.util
import io
import json
import os
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
AUTHORING_PATH = SKILL / "scripts" / "scaffold_humanize_short_patch.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


authoring = load_module("short_patch_scene_route_authoring", AUTHORING_PATH)


class HumanizeShortPatchSceneRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(self, text: str, *, scene: str = "AUTO", suffix: str = ".md"):
        source = self.root / f"source{suffix}"
        output = self.root / f"authoring-{len(list(self.root.glob('authoring-*'))):03d}.json"
        source.write_text(text, encoding="utf-8")
        payload = authoring.create_scaffold(
            source,
            output,
            requested_output="PATCH",
            scene=scene,
            intensity="BALANCED",
            source_kind="DOCUMENT",
            protected_terms=[],
            span_suggestion_mode="NONE",
        )
        return source, output, payload

    @staticmethod
    def resolve_all_high(payload: dict) -> None:
        span_by_finding = {
            finding_id: span["span_id"]
            for span in payload["spans"]
            for finding_id in span["finding_ids"]
        }
        for index, resolution in enumerate(payload["lexical_resolutions"], 1):
            hunk_id = f"H{index:03d}"
            resolution.update(
                {"decision": "HUNK", "hunk_id": hunk_id, "reason": None}
            )
            payload["hunks"].append(
                {
                    "hunk_id": hunk_id,
                    "span_id": span_by_finding[resolution["finding_id"]],
                    "decision": "DELETE_STYLE_SHELL",
                    "replacement": "",
                    "reason": "删除只描述编辑动作、没有进入正文命题的句壳。",
                }
            )

    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_auto_scene_is_resolved_and_frozen_before_authoring(self) -> None:
        source, draft, payload = self.create(
            "值得注意的是，模型输出显示基线情景的评价指标下降。\n"
        )

        self.assertEqual("AUTO", payload["configuration"]["requested_scene"])
        self.assertEqual("MODELING", payload["configuration"]["resolved_scene"])
        self.assertEqual("ROUTED", payload["scene_route"]["status"])
        self.assertGreaterEqual(payload["scene_route"]["scores"]["MODELING"], 3)
        self.assertTrue(payload["scene_route"]["authoring_allowed"])

        self.resolve_all_high(payload)
        self.write(draft, payload)
        selection = authoring.finalize_scaffold(
            source, draft, self.root / "selection.json"
        )
        self.assertEqual("MODELING", selection["scene"])

    def test_explicit_scene_has_priority_over_strong_heuristic_signals(self) -> None:
        _source, _draft, payload = self.create(
            "模型输出显示基线情景的评价指标下降。本节需要说明参数设置。\n",
            scene="GENERAL",
        )

        self.assertEqual("GENERAL", payload["configuration"]["requested_scene"])
        self.assertEqual("GENERAL", payload["configuration"]["resolved_scene"])
        self.assertEqual("EXPLICIT", payload["scene_route"]["status"])
        self.assertEqual(
            "USER_EXPLICIT_SCENE", payload["scene_route"]["reason_code"]
        )
        self.assertEqual(
            {"COURSE": 0, "MODELING": 0, "RESEARCH": 0},
            payload["scene_route"]["scores"],
        )

    def test_weak_auto_signal_falls_back_to_general_without_false_ambiguity(self) -> None:
        _source, _draft, payload = self.create("这里交代本段的范围。\n")

        self.assertEqual("GENERAL", payload["configuration"]["resolved_scene"])
        self.assertEqual("FALLBACK_GENERAL", payload["scene_route"]["status"])
        self.assertEqual(
            "AUTO_INSUFFICIENT_SCENE_EVIDENCE",
            payload["scene_route"]["reason_code"],
        )
        self.assertTrue(payload["scene_route"]["authoring_allowed"])

    def test_ambiguous_auto_route_is_review_and_cannot_finalize(self) -> None:
        text = (
            "本研究的研究结果表明，本文考察模型输出是否仍在当前范围内。"
            "值得注意的是，应保留范围。\n"
        )
        source = self.root / "ambiguous.md"
        output = self.root / "ambiguous.authoring.json"
        source.write_text(text, encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = authoring.main(
                [
                    "create",
                    str(source),
                    "--scene",
                    "AUTO",
                    "--source-kind",
                    "DOCUMENT",
                    "--suggest-spans",
                    "NONE",
                    "--output",
                    str(output),
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(2, exit_code)
        result = json.loads(stdout.getvalue())
        self.assertEqual("ROUTE_REVIEW", result["status"])
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("AMBIGUOUS", payload["scene_route"]["status"])
        self.assertFalse(payload["scene_route"]["authoring_allowed"])
        with self.assertRaisesRegex(authoring.AuthoringError, "SCENE_ROUTE_AMBIGUOUS"):
            authoring.finalize_scaffold(
                source, output, self.root / "ambiguous.selection.json"
            )

    def test_route_record_is_replayed_even_after_coordinated_local_rehash(self) -> None:
        source, draft, payload = self.create(
            "模型输出显示基线情景的评价指标下降。本节需要说明参数设置。\n"
        )
        payload["scene_route"]["scores"]["MODELING"] += 2
        record = dict(payload["scene_route"])
        record.pop("route_record_sha256")
        payload["scene_route"]["route_record_sha256"] = authoring.short_patch.sha256(
            authoring.short_patch.canonical_json(record)
        )
        payload["inventory_sha256"] = authoring._inventory_hash(
            payload["source"],
            payload["configuration"],
            payload["policy_hashes"],
            payload["high_findings"],
            scene_route=payload["scene_route"],
            focus_spans=payload["focus_spans"],
            span_suggestion_policy=payload["span_suggestion_policy"],
            span_suggestions=payload["span_suggestions"],
        )
        self.resolve_all_high(payload)
        self.write(draft, payload)

        with self.assertRaisesRegex(authoring.AuthoringError, "SCENE_ROUTE_DRIFT"):
            authoring.finalize_scaffold(
                source, draft, self.root / "forged.selection.json"
            )

    def test_protected_code_does_not_drive_auto_route(self) -> None:
        _source, _draft, payload = self.create(
            "```text\n模型输出 基线情景 评价指标 状态变量 目标函数\n```\n普通说明。\n"
        )

        self.assertEqual("FALLBACK_GENERAL", payload["scene_route"]["status"])
        self.assertEqual("GENERAL", payload["scene_route"]["resolved_scene"])

    def test_route_evidence_never_exports_source_prose(self) -> None:
        secret = "内部不可导出的项目代号甲乙丙"
        _source, _draft, payload = self.create(
            f"本研究讨论{secret}。值得注意的是，需要保留边界。\n"
        )
        serialized = json.dumps(payload["scene_route"], ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("matched_text", serialized)

    def test_finalize_replays_route_when_router_result_changes(self) -> None:
        source, draft, payload = self.create(
            "模型输出显示基线情景的评价指标下降。本节需要说明参数设置。\n"
        )
        self.resolve_all_high(payload)
        self.write(draft, payload)
        original = authoring.scene_router.route_scene

        def changed_route(*args, **kwargs):
            result = original(*args, **kwargs)
            result["margin"] += 1
            return result

        with mock.patch.object(
            authoring.scene_router, "route_scene", side_effect=changed_route
        ):
            with self.assertRaisesRegex(authoring.AuthoringError, "SCENE_ROUTE_DRIFT"):
                authoring.finalize_scaffold(
                    source, draft, self.root / "changed-route.selection.json"
                )


if __name__ == "__main__":
    unittest.main()
