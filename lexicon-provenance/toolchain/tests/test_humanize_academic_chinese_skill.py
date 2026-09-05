import os
import re
import json
import unittest
from pathlib import Path


SKILL = Path(
    os.environ.get(
        "HUMANIZE_SKILL_DIR",
        Path.home() / ".codex" / "skills" / "humanize-academic-chinese",
    )
)
REFERENCES = SKILL / "references"


class HumanizeAcademicChineseSkillTests(unittest.TestCase):
    def test_skill_root_has_no_nested_discoverable_skill_entrypoints(self) -> None:
        nested = sorted(
            str(path.relative_to(SKILL)).replace("\\", "/")
            for path in SKILL.rglob("SKILL.md")
            if path != SKILL / "SKILL.md"
        )
        self.assertEqual(
            [],
            nested,
            "derived projections or archives under a live skill root create "
            "duplicate discoverable skills",
        )

    def test_required_files_exist(self) -> None:
        required = {
            SKILL / "SKILL.md",
            SKILL / "agents" / "openai.yaml",
            REFERENCES / "pathology-catalog.md",
            REFERENCES / "course-notes.md",
            REFERENCES / "modeling-engineering.md",
            REFERENCES / "research-journal.md",
            REFERENCES / "workflow.md",
            REFERENCES / "rewrite-patterns.md",
            REFERENCES / "style-gates.md",
            REFERENCES / "system-prompt-contract.md",
            REFERENCES / "quick-checklist.md",
            REFERENCES / "lexical-signals.json",
            REFERENCES / "operational-contract.md",
            REFERENCES / "voice-profile.md",
            REFERENCES / "long-document-workflow.md",
            REFERENCES / "evaluation-contract.md",
            REFERENCES / "detector-report-intake.md",
            REFERENCES / "corpus-action-sources.json",
            SKILL / "scripts" / "scan_humanize_chinese.py",
            SKILL / "scripts" / "check_humanize_invariants.py",
            SKILL / "scripts" / "run_humanize_inline.py",
            SKILL / "scripts" / "validate_humanize_output.py",
            SKILL / "scripts" / "build_humanize_action_profile.py",
            SKILL / "scripts" / "load_humanize_negative_guards.py",
            SKILL / "scripts" / "build_humanize_voice_profile.py",
            SKILL / "scripts" / "validate_humanize_voice_profile.py",
            SKILL / "scripts" / "validate_humanize_candidate_queue.py",
            SKILL / "scripts" / "prepare_humanize_candidate_revision.py",
            SKILL / "scripts" / "prepare_humanize_long_document.py",
            SKILL / "scripts" / "finalize_humanize_long_document.py",
            SKILL / "scripts" / "extract_detector_report_scope.py",
        }
        self.assertTrue(SKILL.is_dir())
        self.assertFalse([str(path) for path in required if not path.is_file()])

    def test_skill_frontmatter_and_size(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?s)^---\nname: humanize-academic-chinese\ndescription: .+?\n---")
        self.assertLess(len(text.splitlines()), 500)
        self.assertNotIn("TODO", text)
        self.assertIn("去 AI 味", text)
        self.assertIn("检测报告或检测器标注只能作为候选范围线索", text)
        self.assertIn("拒绝目标百分比、规避检测和操纵检测器", text)
        self.assertNotIn("aigc-down-skill", text)
        self.assertIn("社科、人文、法学", text)
        self.assertIn("Do not promise detector outcomes", text)

    def test_inline_rewrite_lifecycle_is_front_loaded_and_cross_referenced(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        lifecycle = skill.index("## `REWRITE/DRAFT` 必做主路径")
        decision = skill.index("## 决策优先级")
        self.assertLess(lifecycle, decision)
        for token in (
            "run_humanize_inline.py\" run",
            "run_humanize_inline.py\" emit",
            "run_humanize_inline.py attest",
            "BODY_ONLY",
            "mechanical_validation_status",
            "delivery_gate_status",
            "diagnostics",
            "NOT_EVALUATED",
            "验证后任何字节变化",
        ):
            self.assertIn(token, skill)

        operational = (REFERENCES / "operational-contract.md").read_text(
            encoding="utf-8"
        )
        checklist = (REFERENCES / "quick-checklist.md").read_text(encoding="utf-8")
        prompt = (REFERENCES / "system-prompt-contract.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        for text in (operational, checklist, prompt, workflow):
            self.assertIn("run_humanize_inline.py", text)
            self.assertIn("BODY_ONLY", text)
            self.assertIn("attest <run-dir>", text)
            self.assertIn("diagnostics", text)
            self.assertIn("NOT_EVALUATED", text)
            self.assertIn("不得", text)

    def test_user_facing_commands_do_not_depend_on_current_working_directory(self) -> None:
        markdown_files = [SKILL / "SKILL.md", *REFERENCES.glob("*.md")]
        for markdown in markdown_files:
            text = markdown.read_text(encoding="utf-8")
            self.assertNotIn("python scripts/", text, str(markdown))
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("$skillRoot = Join-Path $HOME", skill_text)
        self.assertIn('python "$skillRoot\\scripts\\', skill_text)

    def test_all_relative_markdown_links_resolve(self) -> None:
        for markdown in SKILL.rglob("*.md"):
            text = markdown.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (markdown.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(resolved.exists(), f"broken link in {markdown}: {target}")

    def test_long_references_have_table_of_contents(self) -> None:
        for markdown in REFERENCES.glob("*.md"):
            text = markdown.read_text(encoding="utf-8")
            if len(text.splitlines()) > 100:
                self.assertIn("## 目录", text, str(markdown))

    def test_pathology_catalog_covers_all_registered_diseases(self) -> None:
        text = (REFERENCES / "pathology-catalog.md").read_text(encoding="utf-8")
        matches = list(re.finditer(r"^## HUM-(\d{2})\b", text, flags=re.MULTILINE))
        self.assertEqual([f"{i:02d}" for i in range(1, 23)], [m.group(1) for m in matches])

        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[match.start():end]
            disease = match.group(1)
            self.assertIn("**规则**", block, disease)
            self.assertIn("**案例**", block, disease)
            self.assertIn("**改写动作**", block, disease)
            self.assertRegex(block, rf"`HUM-{disease} MUST`")

    def test_scene_rule_counts_and_unique_ids(self) -> None:
        expected = {
            "course-notes.md": ("NOTE-HUM", 42),
            "modeling-engineering.md": ("MOD-HUM", 41),
            "research-journal.md": ("RJH", 37),
        }
        all_ids: list[str] = []
        for filename, (prefix, count) in expected.items():
            text = (REFERENCES / filename).read_text(encoding="utf-8")
            ids = re.findall(rf"`({re.escape(prefix)}-\d{{2}}) (?:MUST|SHOULD)`", text)
            self.assertEqual(count, len(ids), filename)
            self.assertEqual(len(ids), len(set(ids)), filename)
            all_ids.extend(ids)
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_course_residual_triage_is_explicit_without_becoming_a_blacklist(self) -> None:
        course = (REFERENCES / "course-notes.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")

        self.assertIn("`NOTE-HUM-41 MUST`", course)
        self.assertIn("过程中处理", course)
        self.assertIn("概括为以下", course)
        self.assertIn("样本口径如下", course)
        self.assertIn("不得单凭这一例禁用", course)
        self.assertIn("NOTE-HUM-41", workflow)
        self.assertIn("不计入 high 覆盖率", workflow)

        # The residual triage is deliberately not a lexical signal or a
        # positive rewrite pair. It must remain a paired-review instruction.
        lexicon = json.loads((REFERENCES / "lexical-signals.json").read_text(encoding="utf-8"))
        note_41_signals = [
            signal
            for signal in lexicon["signals"]
            if any(
                item.get("rule") == "NOTE-HUM-41"
                for item in signal.get("references", [])
            )
        ]
        self.assertEqual([], note_41_signals)

    def test_each_scene_has_blacklist_rhythm_and_machine_perfection_sections(self) -> None:
        for filename in (
            "course-notes.md",
            "modeling-engineering.md",
            "research-journal.md",
        ):
            text = (REFERENCES / filename).read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^## 2\. AI 文风黑名单$")
            self.assertRegex(text, r"(?m)^## 4\..*节奏")
            self.assertRegex(text, r"(?m)^## 5\. 机器完美感破除$")
            self.assertIn("终审问题", text)

    def test_sixty_scene_rewrite_patterns_exist(self) -> None:
        text = (REFERENCES / "rewrite-patterns.md").read_text(encoding="utf-8")
        expected_counts = {"CP": 21, "MP": 20, "RP": 20}
        for prefix, count in expected_counts.items():
            ids = re.findall(rf"^### ({prefix}-\d{{2}})\b", text, flags=re.MULTILINE)
            self.assertEqual([f"{prefix}-{i:02d}" for i in range(1, count + 1)], ids)
        self.assertGreaterEqual(text.count("**改前**"), 61)
        self.assertGreaterEqual(text.count("**动作**"), 61)
        self.assertGreaterEqual(text.count("**改后**"), 60)
        course_negative = re.search(
            r"(?ms)^### CP-21\b.*?(?=^## 2\.)",
            text,
        )
        self.assertIsNotNone(course_negative)
        self.assertIn("**失败动作**", course_negative.group(0))
        self.assertIn("不是正向模板", course_negative.group(0))

    def test_scene_rules_do_not_activate_quality_control_workflows(self) -> None:
        scene_text = "\n".join(
            (REFERENCES / filename).read_text(encoding="utf-8")
            for filename in ("course-notes.md", "modeling-engineering.md", "research-journal.md")
        )
        rule_lines = "\n".join(
            line for line in scene_text.splitlines()
            if re.match(r"`(?:NOTE-HUM|MOD-HUM|RJH)-\d{2} (?:MUST|SHOULD)`", line)
        )
        forbidden_active_checks = (
            r"核(?:对|验).*(?:来源|引文|公式|数据|实验|结论)",
            r"(?:判断|验证|检查).*(?:正确|真实|可信|可复现)",
            r"建立.*(?:证据账本|来源账本|参数账本|主张矩阵)",
            r"(?:Blocking|Major|PASS/FAIL/NOT RUN)",
            r"(?:NOTE-MATH|MOD-EVD|MOD-CODE|MOD-EXP|RES-PROOF)-",
        )
        for pattern in forbidden_active_checks:
            self.assertNotRegex(rule_lines, pattern)

    def test_physical_isolation_from_old_quality_skills(self) -> None:
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", skill_text)
        self.assertFalse([link for link in links if "deai-" in link])
        self.assertIn("不得判断内容对错", skill_text)
        self.assertIn("低优先级规则不得覆盖高优先级约束", skill_text)

    def test_style_only_gates_and_no_detector_promise(self) -> None:
        gates = (REFERENCES / "style-gates.md").read_text(encoding="utf-8")
        contract = (REFERENCES / "system-prompt-contract.md").read_text(encoding="utf-8")
        self.assertEqual(13, len(re.findall(r"^### STYLE-\d{2}\b", gates, re.MULTILINE)))
        self.assertEqual(5, len(re.findall(r"^### DG-\d{2}\b", gates, re.MULTILINE)))
        self.assertIn("不判断内容正确性", contract)
        self.assertIn("检测报告只能提供候选范围", contract)
        self.assertNotRegex(contract, r"(?:保证|确保).{0,12}(?:绕过|规避|通过).{0,12}(?:检测|AIGC)")

    def test_modes_intensity_and_conflict_states_are_explicit(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        for value in (
            "DIAGNOSE",
            "REWRITE",
            "DRAFT",
            "LIGHT",
            "BALANCED",
            "STRUCTURAL",
            "NO_CHANGE",
            "UNRESOLVED",
            "GENERAL",
        ):
            self.assertIn(value, skill)
        diagnose = workflow.split("## 2. DIAGNOSE", 1)[1].split(
            "## 3. REWRITE", 1
        )[0]
        self.assertIn("只诊断，不改正文", diagnose)
        self.assertNotIn("已完成纯文风改写", diagnose)
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL / "SKILL.md", *REFERENCES.glob("*.md")]
        )
        self.assertNotRegex(combined, r"STYLE-(?:DIAGNOSE|REWRITE|DRAFT)")

    def test_entrypoint_routing_and_long_document_terminal_states_are_consistent(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        longdoc = (REFERENCES / "long-document-workflow.md").read_text(
            encoding="utf-8"
        )
        portable = (REFERENCES / "system-prompt-contract.md").read_text(
            encoding="utf-8"
        )
        evaluation = (REFERENCES / "evaluation-contract.md").read_text(
            encoding="utf-8"
        )
        finalizer = (SKILL / "scripts" / "finalize_humanize_long_document.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("不确定时用 `GENERAL`", workflow)
        self.assertNotIn("路由不确定时，以原结构", portable)
        for text in (skill, workflow, portable, evaluation):
            self.assertRegex(text, r"(?:正分场景|COURSE/MODELING).{0,40}(?:平局|margin)")
            self.assertIn("AMBIGUOUS", text)
        self.assertIn("`GENERAL` 不读取专属场景文件", skill)
        self.assertIn("Rewrite/质量完成声明", workflow)
        self.assertIn("已完成纯文风诊断", workflow)

        self.assertNotIn("提升为一个临时合并单元", longdoc)
        self.assertIn("不得在 prepare 后手造临时 unit", longdoc)
        self.assertIn("调整分块预算并新建 prepare run", longdoc)
        self.assertIn("publish_state=REVIEW_CANDIDATE", longdoc)
        self.assertIn("paired_quality_clearance_granted = False", finalizer)
        self.assertIn("当前没有外部 paired-quality/结构语义审批", longdoc)

    def test_diagnose_schema_has_one_canonical_source(self) -> None:
        canonical = (
            "Severity | Location | Source role | Scene | Signal/Pathology | "
            "Trigger | Reading effect | Decision | Action"
        )
        contract = (REFERENCES / "operational-contract.md").read_text(encoding="utf-8")
        self.assertEqual(1, contract.count(canonical))
        for name in ("workflow.md", "style-gates.md"):
            text = (REFERENCES / name).read_text(encoding="utf-8")
            self.assertIn("operational-contract.md", text)
            self.assertNotIn("Severity | Location | Signal/Pathology | Reading effect | Decision", text)
        portable = (REFERENCES / "system-prompt-contract.md").read_text(encoding="utf-8")
        self.assertIn(canonical, portable)

    def test_semantic_speech_acts_and_functional_exemptions_are_locked(self) -> None:
        combined = "\n".join(
            (REFERENCES / name).read_text(encoding="utf-8")
            for name in (
                "quick-checklist.md",
                "style-gates.md",
                "workflow.md",
                "research-journal.md",
            )
        )
        for phrase in (
            "称为/定义为",
            "结果表明",
            "等权",
            "闭环控制",
            "真实证明链",
            "修复语",
        ):
            self.assertIn(phrase, combined)

    def test_v7_predicate_source_and_scene_stop_rules_are_production_instructions(self) -> None:
        names = (
            "operational-contract.md",
            "workflow.md",
            "style-gates.md",
            "course-notes.md",
            "modeling-engineering.md",
            "research-journal.md",
            "rewrite-patterns.md",
        )
        combined = "\n".join((REFERENCES / name).read_text(encoding="utf-8") for name in names)

        for phrase in (
            "COPY",
            "ENTAILED_PARAPHRASE",
            "DELETE_STYLE_SHELL",
            "要求/应当/作用在于",
            "方案后果不是必填项",
            "不得只删“未来/后续工作”",
            "不得把剩余缓和词拆成新分句",
            "作者动作必须在当前交付范围内有正文兑现",
        ):
            self.assertIn(phrase, combined)

    def test_v19_pairwise_quality_gate_rejects_shorter_but_worse_rewrites(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        quick = (REFERENCES / "quick-checklist.md").read_text(encoding="utf-8")
        modeling = (REFERENCES / "modeling-engineering.md").read_text(encoding="utf-8")
        research = (REFERENCES / "research-journal.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, workflow, quick, modeling, research))

        for phrase in (
            "成对质量门",
            "段落职责",
            "改后不能稳定优于原文",
            "主语错位",
            "READER_FACING_ARTIFACT_ROLE",
            "不得按逗号、分号平均截断",
            "机械 `PASS` 不能证明搭配",
        ):
            self.assertIn(phrase, combined)

    def test_v20_general_draft_and_report_scope_gates_are_explicit(self) -> None:
        names = (
            "../SKILL.md",
            "workflow.md",
            "style-gates.md",
            "quick-checklist.md",
            "operational-contract.md",
            "detector-report-intake.md",
            "system-prompt-contract.md",
        )
        combined = "\n".join((REFERENCES / name).read_text(encoding="utf-8") for name in names)

        for phrase in (
            "GENERAL 改写准入",
            "`BALANCED` 当成改动配额",
            "形式化同义轮换",
            "先局部回退",
            "--report-scope",
            "report_scope_check=PASS",
            "selection 外",
            "值集合",
            "同一已提供",
            "归因标记仍",
        ):
            self.assertIn(phrase, combined)

    def test_scene_guides_keep_all_positive_cards_out_of_normal_rewrites(self) -> None:
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        course = (REFERENCES / "course-notes.md").read_text(encoding="utf-8")
        modeling = (REFERENCES / "modeling-engineering.md").read_text(encoding="utf-8")
        research = (REFERENCES / "research-journal.md").read_text(encoding="utf-8")

        self.assertIn("选择至多两张", workflow)
        self.assertIn("NONE_APPLICABLE", workflow)
        self.assertIn("## 来源信任边界", skill)
        self.assertIn("source-provenance-trust.json", skill)
        self.assertIn("generator projection 删除全部 positive action", skill)
        for card_id in (
            "COURSE-DECISION-01",
            "COURSE-ERROR-01",
            "COURSE-DERIVATION-01",
            "COURSE-MEANING-01",
        ):
            self.assertNotIn(card_id, course)
        for card_id in (
            "MODELING-METRIC-ROLE-01",
            "MODELING-STRUCTURE-COST-01",
            "MODELING-MINIMUM-TEST-01",
            "MODELING-CONFLICTING-METRICS-01",
        ):
            self.assertNotIn(card_id, modeling)
        for retired_card_id in (
            "MODELING-METHOD-BOUNDARY-01",
            "MODELING-CONTROLLED-CONTRAST-01",
            "MODELING-NEGATIVE-CONTROL-01",
            "MODELING-BACKEND-BOUNDARY-01",
        ):
            self.assertNotIn(retired_card_id, modeling)
        self.assertIn("SUPPORTED_PROVISIONAL", workflow)
        self.assertIn("corpus_action_support=NONE", workflow)
        self.assertIn("当前所有场景均没有生产级 action-card 支持", workflow)
        self.assertIn("不进入 generator projection", course)
        self.assertIn("不进入 generator", modeling)
        retired_research_cards = (
            "RESEARCH-MAP-01",
            "RESEARCH-EVIDENCE-01",
            "RESEARCH-MECHANISM-01",
            "RESEARCH-SCOPE-01",
            "RESEARCH-CLAIM-01",
            "RESEARCH-UNCERTAINTY-01",
        )
        for card_id in retired_research_cards:
            self.assertNotIn(card_id, research)
        self.assertIn("CORPUS_INSUFFICIENT", research)
        self.assertIn("NEGATIVE-RESEARCH-MAIN-META-SHELL-01", research)
        self.assertIn("MODEL_GENERATED + negative_template_reference", research)

    def test_v9_editor_directive_payload_can_be_recovered_without_claiming_completion(self) -> None:
        contract = (REFERENCES / "operational-contract.md").read_text(encoding="utf-8")
        modeling = (REFERENCES / "modeling-engineering.md").read_text(encoding="utf-8")
        patterns = (REFERENCES / "rewrite-patterns.md").read_text(encoding="utf-8")
        combined = "\n".join((contract, modeling, patterns))

        self.assertIn("编辑指令中的字面载荷", combined)
        self.assertIn("三组数据的温度分别为", combined)
        self.assertIn("不能声称表格已经列出", combined)

    def test_v28_compression_preserves_relation_responsibility_and_collocation(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        course = (REFERENCES / "course-notes.md").read_text(encoding="utf-8")
        modeling = (REFERENCES / "modeling-engineering.md").read_text(encoding="utf-8")

        self.assertIn("因果/并列关系、动作责任主体、谓词支配对象和场景声线", skill)
        self.assertIn("共同样本、共同参数或相邻位置不能被静默改写为充分因果", workflow)
        self.assertIn("NOTE-HUM-42 MUST", course)
        self.assertIn("不新增“样本共包括”“这表示”“也就是说”的词项黑名单", course)
        self.assertIn("MOD-HUM-41 MUST", modeling)
        self.assertIn("对象—参数—判据", modeling)
        self.assertIn("academic_correctness=NOT_EVALUATED", modeling)

    def test_verification_claims_require_executed_evidence(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        contract = (REFERENCES / "operational-contract.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, workflow, contract))
        self.assertIn("退出码 `0/1/2`", combined)
        self.assertIn("mechanical_validation_status=PASS", combined)
        self.assertIn("检查后又改文", combined)
        self.assertIn("NOT_RUN", combined)
        self.assertIn("对改后正文重新运行词项扫描器", skill)

    def test_v26_clean_output_never_claims_direct_or_final_delivery(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        contract = (REFERENCES / "operational-contract.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, contract))

        for forbidden in (
            "终审工具",
            "学术初稿生成后的终审、",
            "只给可直接使用的正文",
            "直接交付正文",
            "输出可直接使用的正文",
            "已完成所列范围",
        ):
            self.assertNotIn(forbidden, combined)
        for required in (
            "待审候选生成与机械审计工具",
            "终审辅助",
            "无可信外部 paired-quality clearance 时仍是待审候选",
            "已生成授权范围内的纯文风待审候选",
        ):
            self.assertIn(required, combined)

    def test_inline_rewrites_lock_quotes_high_signals_and_unsourced_attribution(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        quick = (REFERENCES / "quick-checklist.md").read_text(encoding="utf-8")
        prompt = (REFERENCES / "system-prompt-contract.md").read_text(encoding="utf-8")
        operational = (REFERENCES / "operational-contract.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, quick, prompt, operational))
        for phrase in (
            "逐字复制完整原始跨度",
            "更换中文单双引号也算保护区变化",
            "单点删除不等于通过",
            "UNRESOLVED_UNSOURCED_ATTRIBUTION",
            "不得改成客观断言",
        ):
            self.assertIn(phrase, combined)
        for signal in ("具有重要意义", "系统梳理", "深入探讨"):
            self.assertIn(signal, skill)
        for mixed_gate in (
            "拒绝规避部分不等于纯文风部分已通过",
            "由此形成的认识为后续研究提供支撑",
            "不得新造抽象桥接出口",
            "为后续检验提供线索",
            "为后续研究提供可靠起点",
            "不得默示接受目标检测率",
            "CLEAN 不能原样带回未决 high span",
            "摘要声明未决不能补救正文中的 high 残留",
            "改用 `UNRESOLVED + 最小 PATCH/ANNOTATED`",
            "requested_output=CLEAN",
            "effective_output=PATCH",
            "不得把降级后的 PATCH/ANNOTATED 标成 CLEAN",
            "effective_output=PATCH 时必须给实际 hunk",
            "不得把截短正文标成 PATCH",
            "模态强度保留不等于模态 marker 逐字保留",
            "表头必须逐列为",
            "理解而非死记",
            "不以“从题目可推出”为理由自行补写",
        ):
            self.assertIn(mixed_gate, "\n".join((skill, quick, prompt)))

    def test_production_commands_are_wired_into_the_skill(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        gates = (REFERENCES / "style-gates.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, workflow, gates))
        for command in (
            "validate_humanize_output.py",
            "prepare_humanize_long_document.py",
            "finalize_humanize_long_document.py",
            "full_completion_claim_allowed",
            "rendered_partial",
            "--evidence-dir",
            "evidence-manifest.json",
            "replay_humanize_validation_record.py",
            "SELF_CONSISTENCY_ONLY",
            "humanize-direct-validation-evidence/v5",
            "humanize-validation-invocation/v4",
            "hvr4-",
            "UNVERIFIED_CALLER_PROPOSAL",
            "SAME_HOST_SAME_USER_PARENT_PROCESS",
            "inputs/before.bin",
            "record_sha256",
        ):
            self.assertIn(command, combined)

    def test_lexicon_provenance_targets_exist_and_match_categories(self) -> None:
        payload = json.loads((REFERENCES / "lexical-signals.json").read_text(encoding="utf-8"))
        expected = {
            "LEX-TRANS-01": [("references/pathology-catalog.md", "HUM-02"), ("references/course-notes.md", "NOTE-HUM-11")],
            "LEX-EMPH-01": [("references/research-journal.md", "RJH-04"), ("references/modeling-engineering.md", "MOD-HUM-13")],
            "LEX-CONCLUDE-01": [("references/pathology-catalog.md", "HUM-11"), ("references/style-gates.md", "STYLE-07")],
            "LEX-OUTLINE-01": [("references/research-journal.md", "RJH-09"), ("references/pathology-catalog.md", "HUM-01")],
            "LEX-ORDER-01": [("references/course-notes.md", "NOTE-HUM-11"), ("references/course-notes.md", "NOTE-HUM-37"), ("references/research-journal.md", "RJH-11")],
            "LEX-CONTRAST-01": [("references/pathology-catalog.md", "HUM-03"), ("references/research-journal.md", "RJH-05")],
            "LEX-PARALLEL-01": [("references/pathology-catalog.md", "HUM-13")],
            "LEX-MGMT-01": [("references/style-gates.md", "STYLE-06"), ("references/research-journal.md", "RJH-10"), ("references/modeling-engineering.md", "MOD-HUM-19")],
            "LEX-MGMT-02": [("references/modeling-engineering.md", "MOD-HUM-19"), ("references/research-journal.md", "RJH-10")],
            "LEX-MARKET-01": [("references/style-gates.md", "STYLE-06"), ("references/pathology-catalog.md", "HUM-09")],
            "LEX-COACH-01": [("references/course-notes.md", "NOTE-HUM-28"), ("references/style-gates.md", "STYLE-06")],
            "LEX-META-01": [("references/modeling-engineering.md", "MOD-HUM-01"), ("references/rewrite-patterns.md", "MP-01/MP-02")],
            "LEX-TABLE-ROLE-01": [("references/modeling-engineering.md", "MOD-HUM-02")],
            "LEX-HEDGE-01": [("references/research-journal.md", "RJH-08"), ("references/pathology-catalog.md", "HUM-15")],
            "LEX-ABSTRACT-01": [("references/style-gates.md", "STYLE-06"), ("references/pathology-catalog.md", "HUM-08")],
            "LEX-RESULT-01": [("references/rewrite-patterns.md", "MP-18"), ("references/research-journal.md", "RJH-20")],
            "LEX-FOUNDATION-01": [("references/pathology-catalog.md", "HUM-04/HUM-11"), ("references/style-gates.md", "STYLE-07")],
            "LEX-FUTURE-01": [("references/research-journal.md", "RJH-29"), ("references/pathology-catalog.md", "HUM-11")],
            "LEX-THEORY-OPEN-01": [("references/pathology-catalog.md", "HUM-01")],
            "LEX-CASE-CLOSE-01": [("references/pathology-catalog.md", "HUM-11")],
            "LEX-PASSIVE-ANALYSIS-01": [("references/pathology-catalog.md", "HUM-08")],
            "LEX-PROBLEM-SHELL-01": [("references/pathology-catalog.md", "HUM-01")],
            "LEX-VAGUE-ATTRIBUTION-01": [("references/style-gates.md", "STYLE-03")],
            "LEX-COPULA-AVOID-01": [("references/pathology-catalog.md", "HUM-08")],
            "LEX-ACADEMIC-PACKAGE-01": [("references/pathology-catalog.md", "HUM-08")],
            "LEX-ENUM-01": [("references/pathology-catalog.md", "HUM-13")],
            "LEX-PUNCT-DASH-01": [("references/pathology-catalog.md", "HUM-06")],
            "LEX-FORMAT-BOLD-01": [("references/pathology-catalog.md", "HUM-14")],
            "LEX-COURSE-FORMULA-CAPTION-01": [("references/course-notes.md", "NOTE-HUM-35")],
            "LEX-REPAIR-01": [("references/pathology-catalog.md", "HUM-16")],
            "LEX-ABSTRACT-BENEFIT-01": [("references/pathology-catalog.md", "HUM-11"), ("references/research-journal.md", "RJH-30")],
            "LEX-VAGUE-DEPTH-01": [("references/pathology-catalog.md", "HUM-11"), ("references/research-journal.md", "RJH-30")],
            "LEX-META-02": [("references/pathology-catalog.md", "HUM-17")],
            "LEX-SELF-VALIDATION-01": [("references/pathology-catalog.md", "HUM-18")],
            "LEX-SELF-AUDIT-TRIPLET-01": [("references/pathology-catalog.md", "HUM-19")],
            "LEX-QUESTION-ANALYSIS-CONTRAST-01": [("references/modeling-engineering.md", "MOD-HUM-06/MOD-HUM-11")],
            "LEX-QUESTION-AVOID-MISREAD-01": [("references/modeling-engineering.md", "MOD-HUM-39"), ("references/pathology-catalog.md", "HUM-21")],
            "LEX-QUESTION-BENEFIT-SELF-PROOF-01": [("references/modeling-engineering.md", "MOD-HUM-40"), ("references/pathology-catalog.md", "HUM-22")],
            "LEX-COURSE-COPULAR-COMMA-01": [("references/course-notes.md", "NOTE-HUM-40")],
        }
        actual = {
            signal["id"]: [(item["file"], item["rule"]) for item in signal["provenance"]]
            for signal in payload["signals"]
        }
        self.assertEqual(expected, actual)
        for signal in payload["signals"]:
            for source in signal["provenance"]:
                target = SKILL / source["file"]
                self.assertTrue(target.is_file(), f"{signal['id']}: {target}")
                text = target.read_text(encoding="utf-8")
                for rule in source["rule"].split("/"):
                    pattern = rf"(?m)^(?:#{{2,4}}\s+`?{re.escape(rule)}\b|`{re.escape(rule)}\s+(?:MUST|SHOULD|MAY)`)"
                    self.assertRegex(text, pattern, f"{signal['id']}: {source}")

        distilled = [
            signal
            for signal in payload["signals"]
            if signal["id"] in {
                "LEX-THEORY-OPEN-01", "LEX-CASE-CLOSE-01", "LEX-PASSIVE-ANALYSIS-01",
                "LEX-PROBLEM-SHELL-01", "LEX-VAGUE-ATTRIBUTION-01", "LEX-COPULA-AVOID-01",
                "LEX-ACADEMIC-PACKAGE-01", "LEX-ENUM-01", "LEX-PUNCT-DASH-01",
                "LEX-FORMAT-BOLD-01",
            }
        ]
        self.assertEqual(10, len(distilled))
        for signal in distilled:
            self.assertTrue(signal["exclusions"], signal["id"])
            self.assertTrue(all("source_detail" in item for item in signal["provenance"]))
            self.assertNotIn("aigc-down-skill", json.dumps(signal, ensure_ascii=False))

    def test_voice_profile_template_round_trips_all_speech_acts(self) -> None:
        text = (REFERENCES / "voice-profile.md").read_text(encoding="utf-8")
        template = re.search(r"(?s)## 13\. Profile 模板.*?```yaml\n(.*?)```", text)
        self.assertIsNotNone(template)
        speech = re.search(r"(?m)^speech_acts:\n((?:  [a-z_]+:.*\n)+)", template.group(1))
        self.assertIsNotNone(speech)
        keys = set(re.findall(r"(?m)^  ([a-z_]+):", speech.group(1)))
        expected = {
            "naming", "section_choice", "scoping", "comparison",
            "reporting_observation", "reference_back", "omission",
            "formula_table_introduction", "closure",
        }
        self.assertEqual(expected, keys)
        fixture = {"speech_acts": {key: f"样例-{key}" for key in sorted(keys)}}
        self.assertEqual(fixture, json.loads(json.dumps(fixture, ensure_ascii=False)))

    def test_examples_do_not_reintroduce_known_fabrications_or_math_drift(self) -> None:
        pathology = (REFERENCES / "pathology-catalog.md").read_text(encoding="utf-8")
        patterns = (REFERENCES / "rewrite-patterns.md").read_text(encoding="utf-8")
        self.assertNotIn("真正需要区分的是响应速度", pathology)
        self.assertNotIn("情景 A 在第 6 年达到峰值", patterns)
        self.assertNotIn("F1 的精确 Hessian 给出最直接的起点", patterns)
        self.assertNotIn("最明显的变化出现在 F11", patterns)
        self.assertIn("s(x)=-q(x)>0", patterns)
        self.assertIn("\\phi(x)=1/s(x)", patterns)
        self.assertNotIn("s=-q>0", patterns)

    def test_unresolved_and_file_gaps_always_block_full_completion(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        longdoc = (REFERENCES / "long-document-workflow.md").read_text(encoding="utf-8")
        gates = (REFERENCES / "style-gates.md").read_text(encoding="utf-8")
        evaluation = (REFERENCES / "evaluation-contract.md").read_text(encoding="utf-8")
        for token in ("UNRESOLVED", "SKIPPED_GARBLED", "CHANGED_AFTER_SNAPSHOT"):
            self.assertIn(token, skill)
            self.assertIn(token, longdoc)
            self.assertIn(token, gates)
            self.assertIn(token, evaluation)
        self.assertIn("不存在 `PENDING`、`IN_PROGRESS` 或 `UNRESOLVED`", longdoc)
        self.assertIn("`coverage_completion_claim_allowed`", longdoc)
        self.assertIn("`humanize_completion_claim_allowed`", longdoc)
        self.assertIn("assembly_replay_idempotency", longdoc)
        self.assertIn("humanize_second_pass_convergence", longdoc)

    def test_v34_pure_style_layer_must_not_choose_between_conflicting_source_claims(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        operational = (REFERENCES / "operational-contract.md").read_text(
            encoding="utf-8"
        )
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        prompt = (REFERENCES / "system-prompt-contract.md").read_text(
            encoding="utf-8"
        )
        quick = (REFERENCES / "quick-checklist.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, operational, workflow, prompt, quick))

        for phrase in (
            "源文内部冲突不属于纯文风层的裁决权限",
            "不得自行选择其中一条主张",
            "两个冲突 span 都必须原样回显",
            "requested_output=CLEAN; effective_output=PATCH",
            "SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED",
            "不判断哪一条主张正确",
        ):
            self.assertIn(phrase, combined)

    def test_v34_draft_classification_counts_require_replayable_unitization(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        operational = (REFERENCES / "operational-contract.md").read_text(
            encoding="utf-8"
        )
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        prompt = (REFERENCES / "system-prompt-contract.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, operational, workflow, prompt))

        for phrase in (
            "不构成独立外部验证",
            "不是本问的直接观测目标",
            "FACT_BOUNDARY",
            "unit_id + source_span + category",
            "classification_counts=OMITTED_UNUNITIZED",
            "不得输出 `FACT_PAYLOAD=n`",
        ):
            self.assertIn(phrase, combined)
        self.assertNotIn("交付摘要列出三类计数", workflow)
        self.assertNotIn("交付前列出三类计数", operational)

    def test_v34_patch_spans_and_draft_relations_are_source_bound(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        operational = (REFERENCES / "operational-contract.md").read_text(
            encoding="utf-8"
        )
        workflow = (REFERENCES / "workflow.md").read_text(encoding="utf-8")
        prompt = (REFERENCES / "system-prompt-contract.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, operational, workflow, prompt))

        for phrase in (
            "patch_hunks_source_partition=NON_OVERLAPPING",
            "同一 source span 只能属于一个 patch hunk",
            "REWRITE hunk 不得包住另一个 UNRESOLVED span",
            "数字在材料中出现不等于授权自行比较",
            "DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED",
            "不得新增“更大/更高/低于另一情景/进一步侵蚀”",
            "内容缺失不能改写成关系缺失",
            "缺少 X 层 -> 缺少 X 的衔接",
            "SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE",
        ):
            self.assertIn(phrase, combined)

    def test_evaluation_separates_toolchain_and_model_qualification(self) -> None:
        text = (REFERENCES / "evaluation-contract.md").read_text(encoding="utf-8")
        self.assertIn("### 16.1 确定性工具链发布门", text)
        self.assertIn("### 16.2 生成模型前向资格门", text)
        self.assertIn("总体生成资格只有 `PASS/FAIL/NOT_EVALUATED` 三态", text)
        self.assertIn("不能把单次 `REVIEW/2` 原样上浮", text)
        self.assertIn("已有 9 次盲测", text)

    def test_openai_metadata_is_complete(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "中文学术文风 Humanizer"', text)
        short = re.search(r'^  short_description: "([^"]+)"$', text, re.MULTILINE)
        prompt = re.search(r'^  default_prompt: "([^"]+)"$', text, re.MULTILINE)
        self.assertIsNotNone(short)
        self.assertIsNotNone(prompt)
        self.assertGreaterEqual(len(short.group(1)), 25)
        self.assertLessEqual(len(short.group(1)), 64)
        self.assertIn("经验证样本", short.group(1))
        self.assertNotIn("作者声线保护", short.group(1))
        self.assertTrue(prompt.group(1).startswith("Use $humanize-academic-chinese "))
        for boundary in (
            "不优化检测结果",
            "不判断作者身份",
            "学术正确性",
            "不把机械 PASS、NO_CHANGE 或 second pass 当作质量完成",
        ):
            self.assertIn(boundary, prompt.group(1))

    def test_utf8_has_no_replacement_characters(self) -> None:
        for path in SKILL.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml"}:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("\ufffd", text, str(path))


if __name__ == "__main__":
    unittest.main()
