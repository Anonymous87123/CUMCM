#!/usr/bin/env python3
"""Regression tests for complete-role AIGC portfolio planning."""

from __future__ import annotations

import json
from pathlib import Path
import re

from audit_aigc_stack import audit
from route_aigc_tools import APP_CONFIG, select_route


def providers(report: dict) -> list[str]:
    return [item["provider"] for item in report["stages"]]


def require(condition: bool, message: str, payload: dict) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    router_skill = (skill_root / "SKILL.md").read_text(encoding="utf-8-sig")
    require(
        all(token in router_skill for token in (
            "`VERDICT`", "`AI-EDITED FRACTION`", "`SIGNAL LOAD`", "`CALIBRATION`",
        )),
        "ai-check adaptation no longer strips authorship fields while retaining evidence signals",
        {"path": str(skill_root / "SKILL.md")},
    )
    stack = audit(skill_root.parent, skill_root / "references" / "stack-registry.json")
    require(stack["status"] == "pass" and stack["warnings"] == 0, "stack registry is not closed", stack)

    zh_skill = (skill_root.parent / "Humanizer-zh-main" / "SKILL.md").read_text(encoding="utf-8-sig")
    zh_patterns = [int(value) for value in re.findall(r"^###\s+(\d+)\.", zh_skill, re.MULTILINE)]
    require(
        zh_patterns == list(range(1, 34)),
        "general Chinese editor does not expose one complete 33-pattern sequence",
        {"patterns": zh_patterns},
    )
    require(
        "本技能是旧版" not in zh_skill and "$aigc-writing-router" in zh_skill,
        "general Chinese editor still carries the legacy role",
        {"legacy_marker": "本技能是旧版" in zh_skill},
    )

    baibai_agent = (skill_root.parent / "baibaiAIGC" / "agents" / "openai.yaml").read_text(encoding="utf-8-sig")
    require(
        "allow_implicit_invocation: false" in baibai_agent,
        "explicit alternative candidate can still be invoked implicitly",
        {"path": str(skill_root.parent / "baibaiAIGC" / "agents" / "openai.yaml")},
    )

    orchestration = (
        skill_root.parent.parent / "deai-academic-writing" / "references" / "aigc-tool-orchestration.md"
    ).read_text(encoding="utf-8-sig")
    require(
        all(name in orchestration for name in ("aigc-writing-router", "humanizer-zh", "humanizer")),
        "academic scene orchestrator has a stale AIGC capability map",
        {"path": "deai-academic-writing/references/aigc-tool-orchestration.md"},
    )

    mcm = select_route("mcm", "rewrite", "tex")
    mcm_providers = providers(mcm)
    require(mcm["status"] == "pass", "MCM plan failed", mcm)
    require(
        mcm_providers[:4] == [
            "deai-academic-writing",
            "mcm-cup-standard-write",
            "deai-modeling-writing",
            "humanize-academic-chinese",
        ],
        "MCM plan does not assign all complete owners",
        mcm,
    )
    require(
        mcm_providers[-2:] == ["ai-check", "AI_paper"]
        and mcm["reviewer"] == "ai-check"
        and mcm["workbench"] == "AI_paper"
        and mcm["candidate_policy"]["providers"] == ["humanize-academic-chinese"]
        and mcm["stages"][-2].get("read_only") is True,
        "MCM one-call does not attach its default read-only reviewer and workbench plan",
        mcm,
    )
    require(
        mcm["stages"][-1]["mode"] == "WORKBENCH_PLAN_READ_ONLY"
        and mcm["stages"][-1].get("manual") is False
        and mcm["manual_confirmation_required"] is False,
        "default MCM workbench plan still requires a GUI or manual tool launch",
        mcm,
    )
    genre_stage = next(item for item in mcm["stages"] if item["provider"] == "mcm-cup-standard-write")
    require(
        genre_stage.get("style_retrieval_required") is True
        and "prepare_style_retrieval_plan.py" in genre_stage.get("style_retrieval_script", "")
        and genre_stage.get("section_authoring_brief_required") is True
        and "prepare_section_authoring_brief.py" in genre_stage.get("section_authoring_brief_script", "")
        and genre_stage.get("section_drafting_packets_required") is True
        and "prepare_section_drafting_packets.py" in genre_stage.get("section_drafting_packets_script", "")
        and genre_stage.get("section_drafting_usage_required") is True
        and "prepare_section_drafting_usage.py" in genre_stage.get("section_drafting_usage_script", "")
        and genre_stage.get("generation_input_lock_required") is True
        and "lock-generation" in genre_stage.get("generation_input_lock_script", "")
        and "generation-input-lock" in mcm["final_gates"]
        and "style-retrieval-plan" in mcm["final_gates"]
        and "section-authoring-brief" in mcm["final_gates"]
        and "section-drafting-packets" in mcm["final_gates"]
        and "section-drafting-usage" in mcm["final_gates"]
        and "judgment-ledger" in mcm["final_gates"]
        and "public-judgment-bridges" in mcm["final_gates"]
        and "human-blind-selection-v2" in mcm["final_gates"],
        "MCM route does not bind section-level current facts to corpus style retrieval",
        mcm,
    )

    modeling = select_route("modeling", "audit", "markdown")
    require(
        providers(modeling) == ["deai-academic-writing", "deai-modeling-writing", "humanize-academic-chinese"],
        "modeling route is incomplete",
        modeling,
    )

    research = select_route("research", "rewrite", "docx")
    require(
        providers(research) == [
            "deai-academic-writing",
            "deai-research-writing",
            "humanize-academic-chinese",
            "FYADR",
        ],
        "research DOCX route does not use the research owner and document governor",
        research,
    )
    require(
        "manual-document-governance-review" in research["final_gates"],
        "research DOCX route lacks the FYADR review gate",
        research,
    )

    course = select_route("course-notes", "generate", "markdown")
    require("deai-course-notes" in providers(course), "course route lacks its complete scene owner", course)

    academic_en = select_route("academic-en", "rewrite", "tex")
    require(
        providers(academic_en) == ["deai-research-writing", "academic-humanizer"],
        "English academic route does not use its complete integrity and style owners",
        academic_en,
    )

    medical_en = select_route("medical-en", "rewrite", "plain")
    require(
        providers(medical_en) == ["deai-research-writing", "humanizer-medical-academic"],
        "medical English route does not use the medical editor",
        medical_en,
    )

    comparison = select_route("mcm", "compare", "tex", "local")
    require(
        comparison["candidate_policy"]["providers"] == ["humanize-academic-chinese", "baibai-aigc"],
        "academic comparison does not branch H and B from the same source",
        comparison,
    )

    general_zh = select_route("general-zh", "rewrite", "plain")
    require(providers(general_zh) == ["humanizer-zh"], "general Chinese is not owned by humanizer-zh", general_zh)

    general_en = select_route("general-en", "rewrite", "plain")
    require(providers(general_en) == ["humanizer"], "general English is not owned by humanizer", general_en)

    general_voice = select_route(
        "general-en", "rewrite", "plain", requested_editor="humanizer-voice-profile"
    )
    require(
        providers(general_voice) == ["humanizer-voice-profile"],
        "explicit voice-profile editor cannot own its complete general-English route",
        general_voice,
    )

    chinese_copy_lab = select_route(
        "general-zh", "rewrite", "plain", requested_editor="humanize-chinese-copy-lab"
    )
    require(
        providers(chinese_copy_lab) == ["humanize-chinese-copy-lab"],
        "Chinese candidate laboratory cannot own its explicit general-copy route",
        chinese_copy_lab,
    )

    technical = select_route("technical", "rewrite", "plain")
    require(providers(technical) == ["humanizer"], "general technical prose is not owned by humanizer", technical)

    blocked_general_generation = select_route("general-zh", "generate", "plain")
    require(
        blocked_general_generation["status"] == "blocked",
        "general editor was treated as a source-free content generator",
        blocked_general_generation,
    )

    blocked_editor = select_route("mcm", "rewrite", "tex", "document", "humanizer-zh")
    require(blocked_editor["status"] == "blocked", "general Chinese editor entered MCM", blocked_editor)

    blocked_baibai = select_route("mcm", "rewrite", "tex", "document", "baibai-aigc")
    require(blocked_baibai["status"] == "blocked", "Baibai was allowed to own a full MCM document", blocked_baibai)

    blocked_tex = select_route("technical", "rewrite", "tex")
    require(blocked_tex["status"] == "blocked", "generic technical editor accepted a TeX evidence document", blocked_tex)

    blocked_app = select_route("external-app", "rewrite")
    require(blocked_app["status"] == "blocked", "unnamed external app was auto-selected", blocked_app)

    blocked_workbench_scene = select_route(
        "mcm", "audit", "tex", requested_app="AI-Cleaner"
    )
    require(
        blocked_workbench_scene["status"] == "blocked"
        and any(
            item["code"] == "WORKBENCH_DOES_NOT_OWN_SCENE"
            for item in blocked_workbench_scene["findings"]
        ),
        "general-Chinese diagnostic workbench entered the MCM chain",
        blocked_workbench_scene,
    )

    mcm_patina = select_route(
        "mcm", "audit", "tex", requested_reviewer="patina"
    )
    patina_stage = next(
        item for item in mcm_patina["stages"] if item.get("provider") == "patina"
    )
    require(
        mcm_patina["status"] == "pass"
        and patina_stage["mode"] == "AUDIT_EXTRACTED_PROSE_ONLY"
        and mcm_patina["reviewer_can_select_candidate"] is False,
        "Patina did not receive a complete read-only prose audit behind the TeX boundary",
        mcm_patina,
    )

    blocked_english_reviewer = select_route(
        "mcm", "audit", "plain", requested_reviewer="humanizer-brandonwise"
    )
    require(
        blocked_english_reviewer["status"] == "blocked",
        "English statistical reviewer entered a Chinese CUMCM route",
        blocked_english_reviewer,
    )

    for app_name, config in APP_CONFIG.items():
        app_plan = select_route("external-app", "audit", requested_app=app_name)
        require(
            app_plan["status"] == "pass"
            and providers(app_plan) == [app_name]
            and app_plan["stages"][0]["role"] == config["role"],
            f"{app_name} did not receive its complete workbench role",
            app_plan,
        )

    print("PASS: complete scene owners, role evidence, independent candidates, compatible workbenches, and blockers are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
