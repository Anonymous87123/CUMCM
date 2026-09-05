from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
BASE_SKILL = Path(r"C:\Users\Lenovo\.codex\skills\deai-academic-writing")
OWNERSHIP = ROOT / "scripts" / "base_rule_scene_ownership.json"


class SceneSkillClusterTests(unittest.TestCase):
    def test_all_base_rules_have_exactly_one_owner(self) -> None:
        rules_text = (BASE_SKILL / "references" / "rules.md").read_text(encoding="utf-8")
        defined = set(re.findall(r"^### ([A-Z]{3}-\d{2})\b", rules_text, re.MULTILINE))
        ownership = json.loads(OWNERSHIP.read_text(encoding="utf-8"))["owners"]
        flattened = [rule for rules in ownership.values() for rule in rules]
        self.assertEqual(80, len(defined))
        self.assertEqual(len(flattened), len(set(flattened)), "a rule has multiple scene owners")
        self.assertEqual(defined, set(flattened))

    def test_router_names_all_three_children(self) -> None:
        text = (BASE_SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in ("deai-course-notes", "deai-modeling-writing", "deai-research-writing"):
            self.assertIn(f"${name}", text)

    def test_child_skills_are_self_contained_when_present(self) -> None:
        for name, rule_pattern, case_pattern, rewrite_pattern, minimums in (
            (
                "deai-course-notes",
                r"^### (NOTE-[A-Z]+-\d{2})\b",
                r"^## CASE-NOTE-\d{2}\b",
                r"^## PAT-NOTE-\d{2}\b",
                (18, 12, 14),
            ),
            (
                "deai-modeling-writing",
                r"^### (MOD-[A-Z]+-\d{2})\b",
                r"^## \d+\.",
                r"^## \d+\.",
                (24, 14, 16),
            ),
            (
                "deai-research-writing",
                r"^### (RES-\d{3})\b",
                r"^## \d+\.",
                r"^## \d+\.",
                (24, 14, 16),
            ),
        ):
            skill = BASE_SKILL.parent / name
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            rules_text = (skill / "references" / "rules.md").read_text(encoding="utf-8")
            self.assertNotIn("TODO", skill_text)
            rule_ids = re.findall(rule_pattern, rules_text, re.MULTILINE)
            case_count = len(
                re.findall(
                    case_pattern,
                    (skill / "references" / "cases.md").read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
            )
            rewrite_count = len(
                re.findall(
                    rewrite_pattern,
                    (skill / "references" / "rewrite-patterns.md").read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
            )
            self.assertEqual(len(rule_ids), len(set(rule_ids)), f"{name}: duplicate rule ID")
            self.assertGreaterEqual(len(rule_ids), minimums[0], f"{name}: too few rules")
            self.assertGreaterEqual(case_count, minimums[1], f"{name}: too few cases")
            self.assertGreaterEqual(rewrite_count, minimums[2], f"{name}: too few rewrites")
            self.assertLessEqual(len(skill_text.splitlines()), 500, f"{name}: SKILL.md too long")
            for reference in (
                "rules.md",
                "cases.md",
                "rewrite-patterns.md",
                "playbook.md",
                "diagnostic-matrix.md",
                "validation-gates.md",
                "system-prompt-contract.md",
            ):
                self.assertTrue((skill / "references" / reference).exists(), f"{name}: {reference}")

            all_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in skill.rglob("*")
                if path.is_file() and path.suffix in {".md", ".yaml"}
            )
            self.assertNotIn("\ufffd", all_text, f"{name}: replacement character")
            self.assertNotRegex(all_text, r"(?i)\bTODO\b", f"{name}: TODO residue")

    def test_child_relative_links_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^\]]+\]\((?!https?://|/)([^)#]+)(?:#[^)]+)?\)")
        for name in ("deai-course-notes", "deai-modeling-writing", "deai-research-writing"):
            skill = BASE_SKILL.parent / name
            for document in skill.rglob("*.md"):
                text = document.read_text(encoding="utf-8")
                for match in link_pattern.finditer(text):
                    target = document.parent / match.group(1)
                    self.assertTrue(target.exists(), f"{name}: broken link {document} -> {match.group(1)}")

    def test_child_rule_references_are_defined(self) -> None:
        for name, pattern in (
            ("deai-course-notes", r"NOTE-[A-Z]+-\d{2}"),
            ("deai-modeling-writing", r"MOD-[A-Z]+-\d{2}"),
            ("deai-research-writing", r"RES-\d{3}"),
        ):
            skill = BASE_SKILL.parent / name
            rules_text = (skill / "references" / "rules.md").read_text(encoding="utf-8")
            defined = set(re.findall(rf"^### ({pattern})\b", rules_text, re.MULTILINE))
            referenced: set[str] = set()
            for document in skill.rglob("*.md"):
                referenced.update(re.findall(rf"\b{pattern}\b", document.read_text(encoding="utf-8")))
            self.assertFalse(referenced - defined, f"{name}: undefined IDs {sorted(referenced - defined)}")


if __name__ == "__main__":
    unittest.main()
