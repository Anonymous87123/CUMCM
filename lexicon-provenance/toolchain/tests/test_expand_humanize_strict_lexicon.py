from __future__ import annotations

import importlib.util
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "expand_humanize_strict_lexicon.py"
SPEC = importlib.util.spec_from_file_location("expand_humanize_strict_lexicon", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parent_subphrase_requires_repeated_complete_context() -> None:
    entries = [
        {
            "phrase": "提供有力支撑",
            "category": "research-self-proof",
            "combined_occurrences": 800,
        },
        {
            "phrase": "形成有力支撑",
            "category": "academic-packaging",
            "combined_occurrences": 600,
        },
        {
            "phrase": "有力支撑作用",
            "category": "academic-packaging",
            "combined_occurrences": 400,
        },
    ]

    evidence = MODULE.generate_subphrase_candidates(entries)

    usable, reason = MODULE.usable_subphrase("有力支撑", evidence["有力支撑"])
    assert usable is True
    assert reason == "eligible"
    assert len(evidence["有力支撑"].parents) == 3

    usable, reason = MODULE.usable_subphrase("力支", evidence["力支"])
    assert usable is False
    assert reason in {"fixed_left_fragment", "fixed_right_fragment"}


def test_csv_decomposition_reads_complete_parents_and_marks_new_route(tmp_path: Path) -> None:
    csv_path = tmp_path / "all_candidates_after_exact_rescan.csv"
    csv_path.write_text(
        "phrase,category,combined_coverage,combined_occurrences\n"
        "进一步收紧,scope-boundary,120,240\n"
        "收紧边界,scope-boundary,80,160\n"
        "短,scope-boundary,100,200\n"
        "代码路径,scope-boundary,79,200\n",
        encoding="utf-8",
    )
    parents, manifest, stats = MODULE.load_csv_decomposition_parents([csv_path])
    assert [row["phrase"] for row in parents] == ["进一步收紧", "收紧边界"]
    assert manifest[0]["source_kind"] == "csv-decomposition-pass6"
    assert stats["csv_rows_scanned"] == 4
    assert stats["rows_rejected_coverage"] == 1
    assert stats["rows_rejected_shape"] == 1

    repeated = [
        {
            "phrase": phrase,
            "category": "scope-boundary",
            "combined_occurrences": 100,
            "_decomposition_source": "csv-decomposition-pass6",
        }
        for phrase in ("进一步收紧", "口径收紧", "边界收紧")
    ]
    evidence = MODULE.generate_subphrase_candidates(repeated)
    assert "csv-decomposition-pass6" in evidence["收紧"].source_kinds


def test_csv_decomposition_semantic_gate_rejects_components_and_keeps_style_shell() -> None:
    protected = {
        "phrase": "配置文件",
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.2,
        "chat_context_right_boundary_rate": 0.2,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    assert MODULE.csv_decomposition_semantic_reason(protected).startswith(
        "protected_or_generic_component:"
    )
    style = dict(protected, phrase="进一步收紧")
    assert MODULE.csv_decomposition_semantic_reason(style) is None


def test_csv_decomposition_selection_gate_keeps_style_and_rejects_content() -> None:
    base = {
        "category": "scope-boundary",
        "source_kind": "csv-decomposition-pass6",
        "combined_occurrences": 200,
        "combined_coverage": 180,
        "chat_message_coverage": 120,
        "md_unit_coverage": 50,
        "tex_unit_coverage": 10,
        "combined_score": 100.0,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.2,
        "chat_context_right_boundary_rate": 0.2,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    style = dict(base, phrase="进一步收紧")
    content = dict(base, phrase="配置文件")
    final, rejected, _stats = MODULE.select_final([style, content], 10, 10)
    assert [row["phrase"] for row in final] == ["进一步收紧"]
    assert rejected[0]["final_rejection_reason"] == "protected_or_generic_component:文件,配置"


def test_select_final_deduplicates_phrase_across_discovery_routes() -> None:
    phrase = "\u66f4\u7a33"
    common = {
        "phrase": phrase,
        "category": "certainty-limitation",
        "combined_occurrences": 500,
        "combined_coverage": 400,
        "chat_message_coverage": 300,
        "md_unit_coverage": 100,
        "tex_unit_coverage": 0,
        "combined_score": 10.0,
        "semantic_release_decision": "publish_strict",
        "semantic_release_reason": "test",
        "semantic_signals": {},
    }
    baseline = {
        **common,
        "source_kind": "baseline-v1",
        "source_kinds": ["baseline-v1"],
    }
    rediscovered = {
        **common,
        "source_kind": "compound-root-pass4",
        "source_kinds": ["compound-root-pass4"],
    }

    final, rejected, stats = MODULE.select_final(
        [baseline, rediscovered], 10, 10
    )

    assert [row["phrase"] for row in final] == [phrase]
    assert final[0]["source_kinds"] == ["baseline-v1", "compound-root-pass4"]
    assert stats["strict_inventory_entries"] == 1
    assert stats["duplicate_final_rows_removed"] == 1
    assert any(
        row.get("final_rejection_reason") == "duplicate_phrase_already_selected"
        for row in rejected
    )


def test_parent_subphrase_rejects_known_high_frequency_fragments() -> None:
    evidence = MODULE.SubphraseEvidence()
    evidence.parents.update({"父词甲", "父词乙", "父词丙"})
    evidence.categories.update({"process-broadcast": 3})
    evidence.weighted_categories.update({"process-broadcast": 3})
    evidence.left_contexts.update({"甲": 1, "乙": 1, "丙": 1})
    evidence.right_contexts.update({"甲": 1, "乙": 1, "丙": 1})

    for phrase in ("下一", "当前文", "机器结", "证据支", "由此可", "尚未完"):
        usable, reason = MODULE.usable_subphrase(phrase, evidence)
        assert usable is False
        assert reason == "known_subphrase_fragment"


def test_independent_long_phrase_needs_markers_and_complete_boundary() -> None:
    markers = {
        "全面": "academic-packaging",
        "推进": "process-broadcast",
    }

    category, triggers, reason = MODULE.classify_long_candidate(
        "全面推进工作", 300, markers
    )
    assert category in {"academic-packaging", "process-broadcast"}
    assert set(triggers) == {"全面", "推进"}
    assert reason == "eligible"

    category, _triggers, reason = MODULE.classify_long_candidate(
        "普通文本内容", 300, markers
    )
    assert category is None
    assert reason in {"no_complete_boundary_signal", "insufficient_marker_support"}


def test_comparative_single_root_family_discovers_more_stable(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {
                "phrase": "更稳",
                "count": 2806,
                "message_coverage": 2527,
                "coverage_rate": 0.015,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    baseline = [
        {
            "phrase": "稳定生成",
            "category": "certainty-limitation",
            "combined_occurrences": 100,
        }
    ]

    _sub_counts, long_rows, _root_audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, baseline, per_category_pool=20
    )

    assert any(
        row["phrase"] == "更稳"
        and row["source_kind"] == "comparative-root-pass3"
        and row["category"] == "certainty-limitation"
        for row in long_rows
    )


def test_comparative_root_discards_fixed_width_fragment(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 500,
                    "message_coverage": 400,
                    "coverage_rate": 0.01,
                },
                ensure_ascii=False,
            )
            for phrase in (
                "下一步最值", "更稳", "更稳一点", "成更稳", "个更稳",
                "改成更稳", "反而更好", "更自然", "更明确", "更成熟",
                "文更自然", "前最稳妥", "本文更稳妥的结论", "所以更准确",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _sub_counts, long_rows, _root_audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, [], per_category_pool=20
    )
    phrases = {row["phrase"] for row in long_rows}
    assert "更稳" in phrases
    assert "更稳一点" in phrases
    assert "改成更稳" in phrases
    assert "反而更好" in phrases
    assert "更自然" in phrases
    assert "更明确" in phrases
    assert "更成熟" in phrases
    assert "本文更稳妥的结论" in phrases
    assert "所以更准确" in phrases
    assert "下一步最值" not in phrases
    assert "成更稳" not in phrases
    assert "个更稳" not in phrases
    assert "文更自然" not in phrases
    assert "前最稳妥" not in phrases


def test_raw_short_core_is_discovered_without_old_inventory_parent(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    rows = [
        {"phrase": "收紧", "count": 800, "message_coverage": 700},
        {"phrase": "进行", "count": 900, "message_coverage": 800},
        {"phrase": "步收紧", "count": 800, "message_coverage": 700},
        {"phrase": "收紧一", "count": 800, "message_coverage": 700},
    ]
    for phrase in (
        "进一步收紧",
        "口径收紧范围",
        "当前收紧规则",
        "继续收紧边界",
        "最终收紧条件",
        "严格收紧权限",
        "建议收紧标准",
        "已经收紧口径",
        "验证收紧要求",
        "重新收紧范围",
    ):
        rows.append({"phrase": phrase, "count": 60, "message_coverage": 50})
    aggregate.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    selected, audit, stats = MODULE.discover_raw_short_cores(aggregate, [])
    selected_by_phrase = {row["phrase"]: row for row in selected}
    audit_by_phrase = {row["phrase"]: row for row in audit}

    assert selected_by_phrase["收紧"]["source_kind"] == "raw-short-core-pass4"
    assert selected_by_phrase["收紧"]["styled_parent_count"] >= 8
    assert selected_by_phrase["收紧"]["parent_category_count"] >= 2
    assert selected_by_phrase["收紧"]["aggregate_left_context_count"] >= 4
    assert selected_by_phrase["收紧"]["aggregate_right_context_count"] >= 4
    assert audit_by_phrase["进行"]["preselection_reason"] == "function_or_noise_exact"
    assert audit_by_phrase["步收紧"]["preselection_reason"] == "known_fragment"
    assert audit_by_phrase["收紧一"]["preselection_reason"] == "known_fragment"
    assert stats["raw_short_selected_for_exact_rescan"] == 1


def test_raw_short_core_does_not_require_old_marker_categories(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    rows = [{"phrase": "收束", "count": 900, "message_coverage": 700}]
    rows.extend(
        {"phrase": phrase, "count": 60, "message_coverage": 50}
        for phrase in ("甲收束乙", "丙收束丁", "戊收束己", "庚收束辛")
    )
    aggregate.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    selected, _audit, _stats = MODULE.discover_raw_short_cores(aggregate, [])
    row = next(row for row in selected if row["phrase"] == "收束")
    assert row["family_parent_count"] == 4
    assert row["styled_parent_count"] == 0
    assert row["parent_category_count"] == 0


def test_root_families_bypass_tiny_category_heap(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 500 - index,
                    "message_coverage": 400 - index,
                },
                ensure_ascii=False,
            )
            for index, phrase in enumerate(
                ("再收束", "继续收束", "进一步收束", "必须进一步收束")
            )
        )
        + "\n",
        encoding="utf-8",
    )
    raw_rows = [
        {
            "phrase": "收束",
            "category": "scope-boundary",
            "aggregate_chat_message_coverage": 700,
        }
    ]

    _sub_counts, long_rows, _root_audit, stats = MODULE.stream_aggregate_candidates(
        aggregate,
        {},
        [],
        per_category_pool=1,
        raw_short_rows=raw_rows,
    )
    phrases = {row["phrase"] for row in long_rows}
    assert {"再收束", "继续收束", "进一步收束", "必须进一步收束"} <= phrases
    assert stats["root_family_reserve_groups"] == 0
    assert stats["root_family_selected_without_top_k"] == 4


def test_dynamic_raw_core_cannot_reactivate_known_fragment(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": "续成熟化", "count": 500, "message_coverage": 400},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    raw_rows = [
        {
            "phrase": "成熟",
            "category": "certainty-limitation",
            "aggregate_chat_message_coverage": 700,
        }
    ]

    _sub_counts, long_rows, _root_audit, stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, [], per_category_pool=20, raw_short_rows=raw_rows
    )
    assert "续成熟化" not in {row["phrase"] for row in long_rows}
    assert stats["long_rejected/global_known_fragment"] == 1


def test_raw_short_seed_adds_new_single_character_roots(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    prefixes = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
    rows = [
        {"phrase": f"{prefix}收束", "count": 700, "message_coverage": 600}
        for prefix in prefixes
    ]
    aggregate.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    seed_rows = [
        {
            "phrase": "收束",
            "category": "scope-boundary",
            "aggregate_chat_occurrences": 900,
            "aggregate_chat_message_coverage": 700,
        }
    ]

    roots = MODULE.build_single_root_evidence([], aggregate, seed_rows=seed_rows)
    by_root = {row["root"]: row for row in roots}
    for root in ("收", "束"):
        assert by_root[root]["root_status"] == "eligible_root"
        assert by_root[root]["root_discovery_mode"] == "raw-short-seed"
        assert by_root[root]["seed_phrases"] == ["收束"]


def test_candidate_merge_prefers_raw_evidence_over_parent_slice() -> None:
    candidates: dict[str, dict[str, object]] = {}
    MODULE.merge_candidate(
        candidates,
        {"phrase": "收紧", "source_kind": "parent-subphrase-pass2"},
    )
    MODULE.merge_candidate(
        candidates,
        {"phrase": "收紧", "source_kind": "raw-short-core-pass4"},
    )
    assert candidates["收紧"]["source_kind"] == "raw-short-core-pass4"
    assert candidates["收紧"]["source_kinds"] == [
        "parent-subphrase-pass2",
        "raw-short-core-pass4",
    ]


def test_root_closure_publication_keeps_rooted_phrases_and_rejects_fixed_windows() -> None:
    assert MODULE.publication_candidate_allowed(
        {"source_kind": "root-inversion-family-pass8"}, root_closure_only=True
    )
    assert MODULE.publication_candidate_allowed(
        {"source_kind": "raw-short-core-pass4"}, root_closure_only=True
    )
    assert not MODULE.publication_candidate_allowed(
        {"source_kind": "independent-longphrase-pass2"}, root_closure_only=True
    )
    assert not MODULE.publication_candidate_allowed(
        {"source_kind": "csv-decomposition-pass6"}, root_closure_only=True
    )
    assert MODULE.publication_candidate_allowed(
        {"source_kind": "independent-longphrase-pass2"}, root_closure_only=False
    )


def test_final_family_reserve_is_round_robin_across_roots() -> None:
    rows = [
        {
            "phrase": "甲族完整",
            "source_kind": "raw-core-family-pass5",
            "trigger_phrases": ["甲族"],
            "combined_score": 100.0,
            "combined_coverage": 1000,
            "combined_occurrences": 1000,
        },
        {
            "phrase": "甲族明确",
            "source_kind": "raw-core-family-pass5",
            "trigger_phrases": ["甲族"],
            "combined_score": 90.0,
            "combined_coverage": 900,
            "combined_occurrences": 900,
        },
        {
            "phrase": "乙族完整",
            "source_kind": "raw-core-family-pass5",
            "trigger_phrases": ["乙族"],
            "combined_score": 80.0,
            "combined_coverage": 800,
            "combined_occurrences": 800,
        },
    ]

    selected, overflow, stats = MODULE.select_long_with_family_reserve(rows, 2)
    assert {row["phrase"] for row in selected} == {"甲族完整", "乙族完整"}
    assert [row["phrase"] for row in overflow] == ["甲族明确"]
    assert stats["family_final_reserve_groups"] == 2


def test_compound_root_shell_keeps_complete_forms_and_rejects_fragments(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 500,
                    "message_coverage": 400,
                    "coverage_rate": 0.01,
                },
                ensure_ascii=False,
            )
            for phrase in (
                "收紧",
                "再收紧",
                "收紧一点",
                "进一步收紧",
                "必须进一步收紧",
                "要收紧",
                "再收紧一点",
                "一起收紧",
                "口径收紧",
                "步收紧",
                "径收紧",
                "收紧一",
                "再收紧一",
                "收紧为",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    _sub_counts, long_rows, _root_audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, [], per_category_pool=20
    )
    by_phrase = {row["phrase"]: row for row in long_rows}
    for phrase in (
        "收紧",
        "再收紧",
        "收紧一点",
        "进一步收紧",
        "必须进一步收紧",
        "要收紧",
        "再收紧一点",
        "一起收紧",
        "口径收紧",
    ):
        assert by_phrase[phrase]["source_kind"] == "compound-root-pass4"
    for phrase in ("步收紧", "径收紧", "收紧一", "再收紧一", "收紧为"):
        assert phrase not in by_phrase


def test_raw_short_live_context_rejects_fixed_extension() -> None:
    complete = {
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 9,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.5,
    }
    assert MODULE.raw_short_live_context_reason(complete) is None

    fragment = dict(complete)
    fragment["chat_context_right_context_count"] = 2
    fragment["chat_context_right_boundary_rate"] = 0.0
    fragment["chat_context_right_nonboundary_dominance"] = 0.98
    assert MODULE.raw_short_live_context_reason(fragment) in {
        "live_right_context_count_lt_4",
        "live_right_context_dominance_gt_0.75",
        "live_right_boundary_dominance_gt_0.50",
        "live_both_sides_boundary_lt_0.10",
    }

    clipped = dict(complete)
    clipped["chat_context_left_boundary_rate"] = 0.0
    clipped["chat_context_right_boundary_rate"] = 0.04
    clipped["chat_context_left_nonboundary_dominance"] = 0.43
    clipped["chat_context_right_nonboundary_dominance"] = 0.42
    assert MODULE.raw_short_live_context_reason(clipped) == "live_both_sides_boundary_lt_0.10"


def test_single_root_family_does_not_promote_bare_functional_ngrams(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 500,
                    "message_coverage": 400,
                    "coverage_rate": 0.01,
                },
                ensure_ascii=False,
            )
            for phrase in (
                "一轮", "收益", "项测试", "的结果", "不会再", "更稳", "更稳一点"
            )
        )
        + "\n",
        encoding="utf-8",
    )
    roots = [
        {"root": root, "root_status": "eligible_root", "dominant_category": "certainty-limitation"}
        for root in ("一", "收", "项", "测", "试", "结", "果", "再", "稳")
    ]
    _sub_counts, long_rows, _root_audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, [], per_category_pool=20, root_rows=roots
    )
    phrases = {row["phrase"] for row in long_rows}
    assert "更稳" in phrases
    assert "更稳一点" in phrases
    assert "一轮" not in phrases
    assert "收益" not in phrases
    assert "项测试" not in phrases
    assert "的结果" not in phrases
    assert "不会再" not in phrases


def test_single_root_family_rejects_technical_terms_and_fixed_width_shells(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 500,
                    "message_coverage": 400,
                    "coverage_rate": 0.01,
                },
                ensure_ascii=False,
            )
            for phrase in (
                "持久化", "目标值", "续成熟化", "当前会话已经实际",
                "继续成熟化", "我下一步", "更稳的写法", "并通过", "次完整",
                "目标不", "完整读取并", "继续压了",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    roots = [
        {
            "root": root,
            "root_status": "eligible_root",
            "dominant_category": "process-broadcast",
        }
        for root in set("持久化目标值续成熟当前会话已经实际继我下一步稳写法")
    ]
    _sub_counts, long_rows, _root_audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate, {}, [], per_category_pool=40, root_rows=roots
    )
    phrases = {row["phrase"] for row in long_rows}
    assert "持久化" not in phrases
    assert "目标值" not in phrases
    assert "续成熟化" not in phrases
    assert "当前会话已经实际" not in phrases
    assert "继续成熟化" in phrases
    assert "我下一步" in phrases
    assert "更稳的写法" in phrases
    assert "并通过" not in phrases
    assert "次完整" not in phrases
    assert "目标不" not in phrases
    assert "完整读取并" not in phrases
    assert "继续压了" not in phrases


def test_final_inventory_gate_requires_target_family_and_rejects_fragments() -> None:
    rows = [
        {"phrase": phrase, "combined_coverage": 1}
        for phrase in MODULE.REQUIRED_FINAL_PHRASES
    ]
    MODULE.validate_final_inventory(rows)

    rows.append({"phrase": "成更稳", "combined_coverage": 1})
    with pytest.raises(RuntimeError, match="forbidden_fragments"):
        MODULE.validate_final_inventory(rows)


def test_uncurated_two_character_root_is_discovery_only() -> None:
    annotated, _ = MODULE.annotate_semantic_publication([semantic_row("直接")])
    decision = annotated[0]

    assert decision["semantic_release_decision"] == "audit_only"
    assert decision["semantic_release_reason"] == (
        "candidate_short_discovery_root_only"
    )
    assert MODULE.strict_literal_release_veto("更稳") is None
    assert MODULE.strict_literal_release_veto("收紧") is None


def test_route_independent_veto_blocks_protected_new_route_and_baseline() -> None:
    candidate = {
        **semantic_row("更稳妥的结论", source_kind="comparative-root-pass3"),
        "source_kind": "comparative-root-pass3",
    }
    baseline = {**candidate, "source_kind": "baseline-v1"}

    annotated_candidate, _ = MODULE.annotate_semantic_publication([candidate])
    annotated_baseline, _ = MODULE.annotate_semantic_publication([baseline])

    assert annotated_candidate[0]["semantic_release_decision"] == "audit_only"
    assert annotated_candidate[0]["semantic_release_reason"] == (
        "candidate_protected_content"
    )
    assert annotated_baseline[0]["semantic_release_decision"] == "audit_only"
    assert annotated_baseline[0]["semantic_release_reason"] == (
        "baseline_protected_content"
    )

    for row in annotated_candidate:
        row.update(
            combined_coverage=1000,
            combined_occurrences=1000,
            combined_score=100.0,
        )
    final, rejected, _ = MODULE.select_final(
        annotated_candidate, target_subphrases=100, target_longphrases=100
    )
    assert not final
    assert rejected[0]["final_rejection_reason"] == (
        "semantic_audit_only:candidate_protected_content"
    )


def test_baseline_is_revalidated_even_when_old_schema_matches() -> None:
    route = semantic_row("更稳的写法", source_kind="comparative-root-pass3")
    first, _ = MODULE.annotate_semantic_publication([route])
    assert first[0]["semantic_release_decision"] == "publish_strict"
    assert first[0]["semantic_release_reason"].startswith("route_evidence:")

    replay = {**first[0], "source_kind": "baseline-v1"}
    second, _ = MODULE.annotate_semantic_publication(
        [replay],
        baseline_semantic_schema=MODULE.STRICT_RELEASE_CONFIG["schema_version"],
    )
    assert second[0]["semantic_release_decision"] == "publish_strict"
    assert second[0]["semantic_release_reason"] == (
        "baseline_required_family_regression_anchor"
    )

    replay_again = {**second[0], "source_kind": "baseline-v1"}
    third, _ = MODULE.annotate_semantic_publication(
        [replay_again],
        baseline_semantic_schema=MODULE.STRICT_RELEASE_CONFIG["schema_version"],
    )
    assert third[0]["semantic_release_reason"] == (
        "baseline_required_family_regression_anchor"
    )
    assert third[0]["semantic_signals"]["baseline_policy_replayed"] is False

    tampered = {
        **replay,
        "phrase": "更稳妥的结论",
        "semantic_release_decision": "publish_strict",
    }
    blocked, _ = MODULE.annotate_semantic_publication(
        [tampered],
        baseline_semantic_schema=MODULE.STRICT_RELEASE_CONFIG["schema_version"],
    )
    assert blocked[0]["semantic_release_decision"] == "audit_only"
    assert blocked[0]["semantic_release_reason"] == "baseline_protected_content"


def test_changed_policy_rechecks_short_baseline_instead_of_grandfathering() -> None:
    inherited = [
        {
            **semantic_row(
                phrase,
                source_kind="baseline-v1",
                styled_parents=0,
                family_parents=0,
                discourse_attachment_parents=0,
            ),
            "semantic_release_decision": "publish_strict",
            "semantic_release_reason": "baseline_current_policy_release",
        }
        for phrase in ("本文", "指出", "现在", "闭环", "关键问题", "最容易")
    ]
    inherited.extend(
        [
            {
                **semantic_row("更稳", source_kind="baseline-v1"),
                "semantic_release_decision": "publish_strict",
            },
            {
                **semantic_row("收紧", source_kind="baseline-v1"),
                "semantic_release_decision": "publish_strict",
            },
            {
                **semantic_row("进一步收紧", source_kind="baseline-v1"),
                "semantic_release_decision": "publish_strict",
            },
        ]
    )

    annotated, _ = MODULE.annotate_semantic_publication(
        inherited,
        baseline_semantic_schema="semantic-publication/v5",
    )
    by_phrase = {row["phrase"]: row for row in annotated}

    for phrase in ("本文", "指出", "现在", "闭环", "关键问题", "最容易"):
        assert by_phrase[phrase]["semantic_release_decision"] == "audit_only"
        assert by_phrase[phrase]["semantic_signals"][
            "short_baseline_current_policy_recheck"
        ] is True
    for phrase in ("更稳", "收紧", "进一步收紧"):
        assert by_phrase[phrase]["semantic_release_decision"] == "publish_strict"

def test_chat_snapshot_only_counts_assistant_output_before_append(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    events = [
        {"type": "session_meta", "payload": {"id": "fixture"}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "用户提到有力支撑"}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "正文形成有力支撑，也在全面推进工作。"}
                ],
            },
        },
        {
            "type": "response_item",
            "payload": {"type": "function_call", "role": "assistant", "content": []},
        },
    ]
    session.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
        encoding="utf-8",
    )
    stat = session.stat()
    snapshot = [{"path": str(session), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}]
    with session.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "追加的有力支撑"}],
                    },
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    counts, stats = MODULE.scan_chats(
        snapshot,
        ["有力支撑", "全面推进"],
        tmp_path / "chat_manifest.csv",
        context_phrases={"有力支撑"},
    )

    assert counts["有力支撑"]["chat_occurrences"] == 1
    assert counts["有力支撑"]["chat_message_coverage"] == 1
    assert counts["全面推进"]["chat_occurrences"] == 1
    assert counts["有力支撑"]["chat_context_left_context_count"] == 1
    assert counts["有力支撑"]["chat_context_right_context_count"] == 1
    assert stats["assistant_output_messages"] == 1


def test_chat_snapshot_follows_same_named_archived_session_without_reading_append(
    tmp_path: Path,
) -> None:
    codex_root = tmp_path / ".codex"
    session = codex_root / "sessions" / "2026" / "08" / "fixture.jsonl"
    archived = codex_root / "archived_sessions" / session.name
    session.parent.mkdir(parents=True)
    archived.parent.mkdir(parents=True)
    frozen_events = [
        {"type": "session_meta", "payload": {"id": "fixture"}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "这样更稳"}],
            },
        },
    ]
    frozen = (
        "\n".join(json.dumps(item, ensure_ascii=False) for item in frozen_events) + "\n"
    ).encode("utf-8")
    session.write_bytes(frozen)
    stat = session.stat()
    snapshot = [{"path": str(session), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}]
    session.replace(archived)
    with archived.open("ab") as handle:
        handle.write(
            (
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": "后来追加也更稳"}
                            ],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")
        )

    manifest = tmp_path / "chat_manifest.csv"
    counts, stats = MODULE.scan_chats(snapshot, ["更稳"], manifest)

    assert counts["更稳"]["chat_occurrences"] == 1
    assert counts["更稳"]["chat_message_coverage"] == 1
    assert stats["assistant_output_messages"] == 1
    assert stats["chat_files_relocated_after_snapshot"] == 1
    rows = list(csv.DictReader(manifest.open(encoding="utf-8-sig")))
    assert rows[0]["relocated_after_snapshot"] == "true"
    assert rows[0]["changed_after_snapshot"] == "true"


def test_chat_snapshot_rejects_unrelated_missing_file(tmp_path: Path) -> None:
    entry = {
        "path": str(tmp_path / "missing.jsonl"),
        "size": 10,
        "mtime_ns": 1,
    }
    with pytest.raises(FileNotFoundError, match="original or archived path"):
        list(MODULE.iter_frozen_lines(entry))


def test_snapshot_loader_preserves_frozen_byte_lengths(tmp_path: Path) -> None:
    payload = {
        "created_at": "2026-08-01T00:00:00+00:00",
        "files": [
            {"path": str(tmp_path / "a.jsonl"), "size": 123, "mtime_ns": 456}
        ],
    }
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    files, metadata = MODULE.load_snapshot_files(snapshot)
    assert files == payload["files"]
    assert metadata["created_at"] == payload["created_at"]

    snapshot.write_text(json.dumps({"files": [{"path": "missing-size"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid snapshot entry"):
        MODULE.load_snapshot_files(snapshot)


def test_document_scan_removes_code_and_tex_commands(tmp_path: Path) -> None:
    markdown = tmp_path / "sample.md"
    tex = tmp_path / "sample.tex"
    markdown.write_text("正文提供有力支撑。\n```text\n全面推进工作\n```\n", encoding="utf-8")
    tex.write_text("\\section{标题}\n正文全面推进工作。", encoding="utf-8")
    snapshot = []
    for path in (markdown, tex):
        stat = path.stat()
        snapshot.append({"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})

    counts, stats = MODULE.scan_documents(
        snapshot,
        ["有力支撑", "全面推进"],
        tmp_path / "document_manifest.csv",
        context_phrases={"有力支撑"},
    )

    assert counts["有力支撑"]["md_occurrences"] == 1
    assert counts["全面推进"]["md_occurrences"] == 0
    assert counts["全面推进"]["tex_occurrences"] == 1
    assert counts["有力支撑"]["document_context_left_context_count"] == 1
    assert counts["有力支撑"]["document_context_right_context_count"] == 1
    assert stats["semantic_units"] >= 2


def semantic_row(
    phrase: str,
    *,
    source_kind: str = "raw-short-core-pass4",
    styled_parents: int = 30,
    family_parents: int = 100,
    chat: int = 1000,
    md: int = 100,
    tex: int = 50,
    category: str = "scope-boundary",
    triggers: list[str] | None = None,
    discourse_attachment_parents: int = 30,
) -> dict[str, object]:
    return {
        "phrase": phrase,
        "source_kind": source_kind,
        "category": category,
        "styled_parent_count": styled_parents,
        "family_parent_count": family_parents,
        "chat_message_coverage": chat,
        "md_unit_coverage": md,
        "tex_unit_coverage": tex,
        "trigger_phrases": triggers or [],
        "discourse_attachment_parent_count": discourse_attachment_parents,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.5,
        "chat_context_right_nonboundary_dominance": 0.5,
    }


def test_semantic_release_discovers_style_cores_without_phrase_allowlist() -> None:
    tighten = semantic_row(
        "收紧",
        styled_parents=118,
        family_parents=461,
        chat=4207,
        md=1417,
        tex=156,
        discourse_attachment_parents=259,
    )
    tighten_decision = MODULE.classify_raw_short_semantic_publication(tighten)
    assert tighten_decision["semantic_release_decision"] == "publish_strict"
    assert "收紧" not in MODULE.STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES
    assert tighten_decision["semantic_release_reason"] == "relative_discourse_attachment"

    converge = semantic_row(
        "收束",
        styled_parents=59,
        family_parents=392,
        chat=3028,
        md=647,
        tex=145,
        category="contrast-correction",
        discourse_attachment_parents=96,
    )
    converge_decision = MODULE.classify_raw_short_semantic_publication(converge)
    assert converge_decision["semantic_release_decision"] == "publish_strict"
    assert "收束" not in MODULE.STRICT_RELEASE_HIGH_CONFIDENCE_STYLE_CORES
    assert converge_decision["semantic_release_reason"] == "relative_discourse_attachment"


def test_relative_discourse_attachment_distinguishes_action_from_object() -> None:
    assert MODULE.relative_discourse_attachment("进一步收紧范围", 3, 5) == (
        True,
        False,
    )
    assert MODULE.relative_discourse_attachment("收束成结论", 0, 2) == (
        False,
        True,
    )
    assert MODULE.relative_discourse_attachment("运行脚本文件", 2, 4) == (
        False,
        False,
    )


def test_style_parent_ratio_alone_cannot_release_a_short_core() -> None:
    low_attachment = semantic_row(
        "甲核",
        styled_parents=900,
        family_parents=1000,
        discourse_attachment_parents=199,
    )
    decision = MODULE.classify_raw_short_semantic_publication(low_attachment)
    assert decision["semantic_release_decision"] == "audit_only"
    assert (
        decision["semantic_release_reason"]
        == "insufficient_relative_discourse_attachment"
    )

    high_attachment = dict(low_attachment)
    high_attachment["discourse_attachment_parent_count"] = 200
    decision = MODULE.classify_raw_short_semantic_publication(high_attachment)
    assert decision["semantic_release_decision"] == "publish_strict"
    assert decision["semantic_release_reason"] == "relative_discourse_attachment"


def test_document_dominant_short_core_stays_in_audit_even_with_attachment() -> None:
    decision = MODULE.classify_raw_short_semantic_publication(
        semantic_row(
            "甲核",
            styled_parents=500,
            family_parents=1000,
            chat=100,
            md=1000,
            tex=1000,
            discourse_attachment_parents=500,
        )
    )
    assert decision["semantic_release_decision"] == "audit_only"
    assert (
        decision["semantic_release_reason"]
        == "insufficient_chat_dominant_style_evidence"
    )


def test_generic_voice_core_is_not_granted_an_allowlist_bypass() -> None:
    voice = semantic_row(
        "我们",
        styled_parents=100,
        family_parents=1000,
        discourse_attachment_parents=0,
    )
    decision = MODULE.classify_raw_short_semantic_publication(voice)
    assert decision["semantic_release_reason"] == "insufficient_relative_discourse_attachment"
    assert decision["semantic_release_decision"] == "audit_only"

    technical = semantic_row(
        "脚本",
        styled_parents=900,
        family_parents=1000,
        discourse_attachment_parents=900,
    )
    decision = MODULE.classify_raw_short_semantic_publication(technical)
    assert decision["semantic_release_reason"] == "protected_content_exact"
    assert decision["semantic_release_decision"] == "audit_only"


@pytest.mark.parametrize("phrase", ["方程", "积分", "参数", "算法", "证明", "定义"])
def test_semantic_release_protects_content_terms_even_with_style_parents(
    phrase: str,
) -> None:
    row = semantic_row(
        phrase,
        styled_parents=900,
        family_parents=1000,
        chat=5000,
        md=5000,
        tex=5000,
    )
    decision = MODULE.classify_raw_short_semantic_publication(row)
    assert decision["semantic_class"] == "technical_or_content"
    assert decision["semantic_release_decision"] == "audit_only"
    assert decision["semantic_release_reason"] == "protected_content_exact"


@pytest.mark.parametrize("phrase", ["进行", "使用", "两个", "每个"])
def test_semantic_release_does_not_promote_generic_frequency(phrase: str) -> None:
    decision = MODULE.classify_raw_short_semantic_publication(
        semantic_row(phrase, styled_parents=900, family_parents=1000)
    )
    assert decision["semantic_class"] == "function_or_generic"
    assert decision["semantic_release_decision"] == "audit_only"


def test_semantic_release_uses_tex_dominance_for_unlisted_technical_term() -> None:
    decision = MODULE.classify_raw_short_semantic_publication(
        semantic_row(
            "偏振",
            styled_parents=10,
            family_parents=100,
            chat=100,
            md=100,
            tex=900,
        )
    )
    assert decision["semantic_class"] == "technical_or_content"
    assert decision["semantic_release_decision"] == "audit_only"
    assert decision["semantic_release_reason"] == "technical_tex_dominant"


def test_only_released_short_cores_can_publish_data_driven_families() -> None:
    rows = [
        semantic_row(
            "收紧",
            styled_parents=300,
            family_parents=1000,
            discourse_attachment_parents=250,
        ),
        semantic_row(
            "直接",
            styled_parents=300,
            family_parents=1000,
            discourse_attachment_parents=250,
        ),
        semantic_row(
            "必须",
            styled_parents=300,
            family_parents=1000,
            discourse_attachment_parents=250,
        ),
        semantic_row(
            "严谨",
            styled_parents=300,
            family_parents=1000,
            discourse_attachment_parents=250,
        ),
        semantic_row("方程", styled_parents=900, family_parents=1000),
        semantic_row(
            "必须直接",
            source_kind="raw-core-family-pass5",
            triggers=["直接"],
        ),
        semantic_row(
            "进一步收紧",
            source_kind="raw-core-family-pass5",
            triggers=["收紧"],
        ),
        semantic_row(
            "微分方程",
            source_kind="raw-core-family-pass5",
            triggers=["方程"],
        ),
        semantic_row("线性方程", source_kind="single-root-family-pass3"),
        semantic_row(
            "严谨表达式",
            source_kind="raw-core-family-pass5",
            triggers=["严谨"],
        ),
        semantic_row(
            "必须保留方程",
            source_kind="raw-core-family-pass5",
            triggers=["必须", "方程"],
        ),
    ]
    annotated, stats = MODULE.annotate_semantic_publication(rows)
    by_phrase = {row["phrase"]: row for row in annotated}

    assert by_phrase["进一步收紧"]["semantic_release_decision"] == "publish_strict"
    assert by_phrase["必须直接"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["必须直接"]["semantic_release_reason"].startswith(
        "family_has_no_released_style_core"
    )
    assert by_phrase["必须直接"]["semantic_release_roots"] == []
    assert by_phrase["微分方程"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["线性方程"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["严谨表达式"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["严谨表达式"]["semantic_release_reason"].startswith(
        "family_has_no_released_style_core"
    )
    assert by_phrase["必须保留方程"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["必须保留方程"]["semantic_release_reason"].startswith(
        "family_has_no_released_style_core"
    )
    assert by_phrase["必须保留方程"]["semantic_signals"]["protected_content_hits"] == [
        "方程"
    ]
    assert stats["released_raw_short_cores"] == 1


def test_family_release_requires_local_attachment_and_respects_content_veto() -> None:
    rows = [
        semantic_row(
            "收紧",
            styled_parents=118,
            family_parents=461,
            discourse_attachment_parents=259,
        ),
        semantic_row(
            "进一步收紧",
            source_kind="raw-core-family-pass5",
            triggers=["收紧"],
        ),
        semantic_row(
            "收紧一点",
            source_kind="raw-core-family-pass5",
            triggers=["收紧"],
        ),
        semantic_row(
            "逐层收紧",
            source_kind="single-root-family-pass3",
        ),
        semantic_row(
            "脚本收紧",
            source_kind="single-root-family-pass3",
        ),
    ]
    annotated, stats = MODULE.annotate_semantic_publication(rows)
    by_phrase = {row["phrase"]: row for row in annotated}

    assert by_phrase["进一步收紧"]["semantic_release_decision"] == "publish_strict"
    assert by_phrase["收紧一点"]["semantic_release_decision"] == "publish_strict"
    assert (
        by_phrase["逐层收紧"]["semantic_release_reason"]
        == "family_lacks_relative_discourse_attachment"
    )
    assert by_phrase["脚本收紧"]["semantic_release_reason"] == "family_protected_content"
    assert stats["released_raw_short_cores"] == 1


def test_select_final_rejects_semantic_audit_only_candidates() -> None:
    candidates = [
        semantic_row(
            "收紧",
            styled_parents=118,
            family_parents=461,
            chat=4207,
            md=1417,
            tex=156,
            discourse_attachment_parents=259,
        ),
        semantic_row(
            "方程",
            styled_parents=900,
            family_parents=1000,
            chat=5000,
            md=5000,
            tex=5000,
        ),
    ]
    for row in candidates:
        row.update(
            combined_coverage=int(row["chat_message_coverage"])
            + int(row["md_unit_coverage"])
            + int(row["tex_unit_coverage"]),
            combined_occurrences=20_000,
            combined_score=100.0,
        )
    annotated, _stats = MODULE.annotate_semantic_publication(candidates)
    final, rejected, _selection = MODULE.select_final(annotated, 100, 100)

    assert {row["phrase"] for row in final} == {"收紧"}
    rejected_by_phrase = {row["phrase"]: row for row in rejected}
    assert rejected_by_phrase["方程"]["final_rejection_reason"].startswith(
        "semantic_audit_only:protected_content_exact"
    )


def test_final_inventory_gate_refuses_unreleased_semantic_candidate() -> None:
    rows = [
        {"phrase": phrase, "combined_coverage": 1}
        for phrase in MODULE.REQUIRED_FINAL_PHRASES
    ]
    rows.append(
        {
            "phrase": "方程",
            "source_kind": "raw-short-core-pass4",
            "combined_coverage": 1,
            "semantic_release_decision": "audit_only",
        }
    )
    with pytest.raises(RuntimeError, match="semantic_gate_violations"):
        MODULE.validate_final_inventory(rows)


def test_semantic_units_do_not_join_separate_han_runs() -> None:
    left = "\u7532\u7532"
    right = "\u4e59\u4e59"
    units = list(MODULE.semantic_units(f"{left}ABC{right}", ".md"))
    assert units == [left, right]
    assert left + right not in units


def test_scan_documents_excludes_exact_duplicate_and_cross_run_phrase(
    tmp_path: Path,
) -> None:
    left = "\u7532\u7532"
    right = "\u4e59\u4e59"
    raw = f"{left}ABC{right}".encode("utf-8")
    first = tmp_path / "first.md"
    duplicate = tmp_path / "duplicate.md"
    first.write_bytes(raw)
    duplicate.write_bytes(raw)
    snapshot = [
        {
            "path": str(path),
            "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in (first, duplicate)
    ]
    result, stats = MODULE.scan_documents(
        snapshot,
        [left, left + right],
        tmp_path / "manifest.csv",
    )
    assert result[left]["md_occurrences"] == 1
    assert result[left]["md_file_coverage"] == 1
    assert result[left + right]["md_occurrences"] == 0
    assert stats["document_files_exact_duplicates"] == 1


def test_document_ngram_discovery_finds_document_only_root_and_deduplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = "\u66f4\u7a33"
    texts = [
        f"\u8fd9\u6837{root}\u4e00\u70b9\u3002{root}\u7684\u5199\u6cd5\u3002",
        f"\u6539\u6210{root}\u3002{root}\u7684\u8bf4\u6cd5\u3002",
    ]
    paths = []
    for index, text in enumerate([*texts, texts[0]]):
        path = tmp_path / f"doc-{index}.md"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    snapshot = [
        {
            "path": str(path),
            "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in paths
    ]
    monkeypatch.setattr(MODULE, "DOCUMENT_NGRAM_MIN_UNITS", {2: 2, 3: 2})
    monkeypatch.setattr(MODULE, "DOCUMENT_NGRAM_MIN_FILES", {2: 2, 3: 2})
    monkeypatch.setattr(MODULE, "DOCUMENT_NGRAM_MIN_OCCURRENCES", {2: 2, 3: 2})
    monkeypatch.setattr(MODULE, "DOCUMENT_ROOT_AUDIT_MIN_UNITS", {1: 2, 2: 2, 3: 2})
    monkeypatch.setattr(MODULE, "DOCUMENT_ROOT_MIN_FILES", {1: 2, 2: 2, 3: 2})
    monkeypatch.setattr(MODULE, "DOCUMENT_ROOT_MIN_OCCURRENCES", {1: 2, 2: 2, 3: 2})

    selected, audit, root_audit, stats = MODULE.discover_document_ngram_seeds(
        snapshot, [], limit=100
    )
    selected_by_phrase = {row["phrase"]: row for row in selected}
    assert root in selected_by_phrase
    assert selected_by_phrase[root]["document_ngram_file_coverage"] == 2
    assert any(row["phrase"] == root for row in audit)
    assert any(row["root"] == root for row in root_audit)
    assert stats["document_ngram_duplicate_files"] == 1

    (
        uncapped,
        uncapped_audit,
        uncapped_root_audit,
        uncapped_stats,
    ) = MODULE.discover_document_ngram_seeds(snapshot, [], limit=None)
    assert {row["phrase"] for row in uncapped} == {
        row["phrase"] for row in uncapped_audit
    }
    assert uncapped_stats["document_ngram_candidates_dropped_by_pool"] == 0
    assert uncapped_stats["document_ngram_selection_policy_no_top_k"] == 1
    assert {row["root"] for row in uncapped_root_audit} == {
        row["root"] for row in root_audit
    }


def test_exact_count_cache_reuses_only_complete_context_metrics(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "all_candidates_after_exact_rescan.csv"
    fields = [
        "phrase",
        *MODULE.CHAT_EXACT_BASE_FIELDS,
        *MODULE.DOCUMENT_EXACT_BASE_FIELDS,
        *MODULE.EXACT_CONTEXT_FIELDS,
    ]
    complete = {field: "1" for field in fields}
    complete.update(
        {
            "phrase": "更稳",
            "chat_message_coverage_rate": "0.25",
            **{
                field: "{}" if field.endswith("_contexts") else "0.2"
                if field.endswith(("_rate", "_dominance"))
                else "4"
                for field in MODULE.EXACT_CONTEXT_FIELDS
            },
        }
    )
    incomplete = dict(complete, phrase="收紧", chat_context_left_context_count="")
    with cache.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([complete, incomplete])

    chat, documents, cached, stats = MODULE.load_exact_count_cache(
        cache,
        {"更稳", "收紧"},
        {"更稳", "收紧"},
    )
    assert cached == {"更稳"}
    assert chat["更稳"]["chat_message_coverage_rate"] == 0.25
    assert documents["更稳"]["document_context_left_contexts"] == {}
    assert stats["phrases_reused"] == 1
    assert stats["phrases_requiring_rescan"] == 1


def test_exact_count_cache_binding_uses_snapshot_file_sets_not_timestamps(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "all_candidates_after_exact_rescan.csv"
    cache.write_text("phrase\n更稳\n", encoding="utf-8")
    aggregate_hash = "a" * 64
    (tmp_path / "run_metadata.json").write_text(
        json.dumps({"aggregate_candidates_sha256": aggregate_hash}),
        encoding="utf-8",
    )
    files = [{"path": "C:/fixed/chat.jsonl", "size": 12, "mtime_ns": 34}]
    cached_chat = tmp_path / "chat_snapshot.json"
    cached_document = tmp_path / "document_snapshot.json"
    cached_chat.write_text(
        json.dumps({"created_at": "old", "files": files}), encoding="utf-8"
    )
    cached_document.write_text(
        json.dumps({"created_at": "old", "files": files}), encoding="utf-8"
    )
    current_chat = tmp_path / "current-chat.json"
    current_document = tmp_path / "current-document.json"
    current_chat.write_text(
        json.dumps({"created_at": "new", "files": files}), encoding="utf-8"
    )
    current_document.write_text(
        json.dumps({"created_at": "newer", "files": files}), encoding="utf-8"
    )

    result = MODULE.validate_exact_count_cache_binding(
        cache,
        aggregate_sha256=aggregate_hash,
        chat_snapshot=current_chat,
        document_snapshot=current_document,
    )
    assert all(result["binding_checks"].values())

    current_document.write_text(
        json.dumps(
            {
                "files": [
                    {"path": "C:/fixed/chat.jsonl", "size": 13, "mtime_ns": 34}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not bound"):
        MODULE.validate_exact_count_cache_binding(
            cache,
            aggregate_sha256=aggregate_hash,
            chat_snapshot=current_chat,
            document_snapshot=current_document,
        )


def test_snapshot_loader_rejects_a_stale_declared_file_set_hash(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot.json"
    files = [{"path": "C:/docs/a.md", "size": 10, "mtime_ns": 20}]
    snapshot.write_text(
        json.dumps({"file_set_sha256": "0" * 64, "files": files}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="file_set_sha256 mismatch"):
        MODULE.load_snapshot_files(snapshot)


def test_preselection_pool_drop_is_explicitly_returned() -> None:
    phrases = ["\u6536\u7d27", "\u6536\u675f", "\u843d\u5730"]
    evidence = {}
    aggregate = {}
    for phrase in phrases:
        item = MODULE.SubphraseEvidence()
        item.parents.update(
            {
                "\u518d" + phrase + "\u4e00\u70b9",
                "\u7ee7\u7eed" + phrase + "\u8fb9\u754c",
                "\u9010\u6b65" + phrase + "\u89c4\u5219",
            }
        )
        item.categories.update({"scope-boundary": 3})
        item.weighted_categories.update({"scope-boundary": 300})
        item.left_contexts.update({"\u518d": 1, "\u7eed": 1, "\u6b65": 1})
        item.right_contexts.update({"\u4e00": 1, "\u8fb9": 1, "\u89c4": 1})
        evidence[phrase] = item
        aggregate[phrase] = {
            "aggregate_chat_occurrences": 500,
            "aggregate_chat_message_coverage": 400,
            "aggregate_chat_message_coverage_rate": 0.1,
        }

    selected, rejected, dropped = MODULE.preselect_subphrases(
        evidence, aggregate, pool_limit=1
    )
    assert len(selected) == 1
    assert rejected == []
    assert len(dropped) == 2
    assert {row["preselection_reason"] for row in dropped} == {
        "eligible_dropped_by_pool"
    }


def test_document_short_requires_style_anchor_not_just_chat_frequency() -> None:
    generic = {
        "phrase": "\u6307\u5b9a",
        "trigger_phrases": [],
        "chat_message_coverage": 2_000,
        "md_occurrences": 2_000,
        "md_unit_coverage": 1_600,
        "md_file_coverage": 100,
        "tex_occurrences": 1_000,
        "tex_unit_coverage": 900,
        "tex_file_coverage": 50,
        "document_context_left_context_count": 20,
        "document_context_right_context_count": 20,
        "document_context_left_boundary_rate": 0.2,
        "document_context_right_boundary_rate": 0.2,
        "document_context_left_nonboundary_dominance": 0.3,
        "document_context_right_nonboundary_dominance": 0.3,
    }
    assert (
        MODULE.document_short_semantic_reason(generic)
        == "document_style_anchor_missing"
    )


def test_document_short_rejects_one_sided_fixed_fragment() -> None:
    fragment = {
        "phrase": "\u7a0b\u7ec4",
        "trigger_phrases": ["\u7a0b\u7ec4"],
        "chat_message_coverage": 0,
        "md_occurrences": 200,
        "md_unit_coverage": 100,
        "md_file_coverage": 10,
        "tex_occurrences": 200,
        "tex_unit_coverage": 100,
        "tex_file_coverage": 10,
        "document_context_left_context_count": 8,
        "document_context_right_context_count": 8,
        "document_context_left_boundary_rate": 0.0,
        "document_context_right_boundary_rate": 0.5,
        "document_context_left_nonboundary_dominance": 0.99,
        "document_context_right_nonboundary_dominance": 0.4,
    }
    assert (
        MODULE.document_short_semantic_reason(fragment)
        == "document_left_context_dominance_gt_0.75"
    )


def test_root_inversion_discovers_unlisted_compound_from_diverse_shells(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "再收束",
        "继续收束",
        "进一步收束",
        "必须收束",
        "需要收束",
        "重新收束",
        "收束一点",
        "收束",
        "口径收束",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 160, "message_coverage": 120},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )

    selected, audit, stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["收束"]["root_status"] == "eligible_root_inversion"
    assert by_root["收束"]["shell_parent_count"] >= 6
    assert by_root["收束"]["shell_type_count"] >= 6
    assert "收束" not in MODULE.COMPOUND_ROOT_PATTERNS
    assert stats["roots_selected_for_family_scan"] >= 1

    _counts, families, family_audit, _stream_stats = (
        MODULE.stream_aggregate_candidates(
            aggregate,
            {},
            [],
            per_category_pool=20,
            root_inversion_rows=selected,
        )
    )
    by_phrase = {row["phrase"]: row for row in families}
    assert by_phrase["收束"]["source_kind"] == "root-inversion-family-pass8"
    assert by_phrase["口径收束"]["source_kind"] == "root-inversion-family-pass8"
    assert any(row["phrase"] == "口径收束" for row in family_audit)


def test_root_inversion_rediscovers_shoujin_without_manual_compound_or_required_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "再收紧",
        "继续收紧",
        "进一步收紧",
        "必须收紧",
        "需要收紧",
        "重新收紧",
        "收紧一点",
        "收紧",
        "口径收紧",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 240, "message_coverage": 200},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MODULE,
        "COMPOUND_ROOT_PATTERNS",
        {
            phrase: category
            for phrase, category in MODULE.COMPOUND_ROOT_PATTERNS.items()
            if phrase != "收紧"
        },
    )
    monkeypatch.setattr(
        MODULE,
        "REQUIRED_FINAL_PHRASES",
        frozenset(phrase for phrase in MODULE.REQUIRED_FINAL_PHRASES if "收紧" not in phrase),
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["收紧"]["root_status"] == "eligible_root_inversion"
    assert by_root["收紧"]["shell_parent_count"] >= 6
    assert by_root["收紧"]["root_leave_one_out_ready"] is True
    assert by_root["收紧"]["root_manual_hint_used"] is False

    _counts, families, _family_audit, _stream_stats = (
        MODULE.stream_aggregate_candidates(
            aggregate,
            {},
            [],
            per_category_pool=20,
            root_inversion_rows=selected,
        )
    )
    released = {row["phrase"] for row in families}
    assert {"收紧", "再收紧", "收紧一点", "口径收紧"} <= released


def test_root_inversion_rediscovers_wen_without_comparative_or_required_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "更稳",
        "很稳",
        "最稳",
        "较稳",
        "太稳",
        "愈稳",
        "会稳",
        "已经稳",
        "仍然稳",
        "最终稳",
        "稳一点",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 240, "message_coverage": 200},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MODULE,
        "COMPARATIVE_ROOT_PATTERNS",
        tuple(row for row in MODULE.COMPARATIVE_ROOT_PATTERNS if "稳" not in row[0]),
    )
    monkeypatch.setattr(
        MODULE,
        "REQUIRED_FINAL_PHRASES",
        frozenset(phrase for phrase in MODULE.REQUIRED_FINAL_PHRASES if "稳" not in phrase),
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["稳"]["root_status"] == "eligible_root_inversion"
    assert by_root["稳"]["comparative_shell_type_count"] >= 4
    assert by_root["稳"]["root_leave_one_out_ready"] is True
    assert by_root["稳"]["root_manual_hint_used"] is False

    _counts, families, _family_audit, _stream_stats = (
        MODULE.stream_aggregate_candidates(
            aggregate,
            {},
            [],
            per_category_pool=20,
            root_inversion_rows=selected,
        )
    )
    released = {row["phrase"] for row in families}
    assert {"更稳", "最稳", "较稳", "稳一点"} <= released


def test_root_first_window_graph_finds_unlisted_root_and_keeps_bare_root_audit_only(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "继续补齐", "再补齐", "进一步补齐", "已经补齐", "同步补齐", "逐步补齐",
        "重新补齐", "再次补齐", "建议补齐", "可以补齐", "需要补齐", "务必补齐",
        "补齐内容", "补齐范围", "补齐步骤", "补齐信息", "补齐",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 160, "message_coverage": 80},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["补齐"]["root_status"] == "eligible_root_inversion"
    assert "aggregate-root-window" in by_root["补齐"]["parent_sources"]
    assert by_root["补齐"]["root_first_counts_ready"]
    assert MODULE.strict_literal_release_veto("补齐") == "discovery_root_only"
    assert "补齐" in {row["root"] for row in selected}

    _counts, families, _family_audit, _stream_stats = (
        MODULE.stream_aggregate_candidates(
            aggregate,
            {},
            [],
            per_category_pool=1,
            root_inversion_rows=selected,
        )
    )
    family_phrases = {row["phrase"] for row in families}
    assert "继续补齐" in family_phrases
    assert "补齐" in family_phrases


def test_root_first_empirical_shells_do_not_require_known_markers_or_categories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    prefixes = ("语气", "论证", "证据", "表述", "结构", "局部")
    suffixes = ("理由", "依据", "部分", "说明", "逻辑", "内容")
    style_seed_roots = (
        "收紧", "收束", "补齐", "收口", "落地", "锁定", "定版", "闭环",
    )
    phrases = tuple(
        [f"{prefix}补强" for prefix in prefixes]
        + [f"补强{suffix}" for suffix in suffixes]
        + ["补强"]
        + [
            phrase
            for seed_root in style_seed_roots
            for phrase in (
                *[f"{prefix}{seed_root}" for prefix in prefixes],
                *[f"{seed_root}{suffix}" for suffix in suffixes],
                seed_root,
            )
        ]
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 320, "message_coverage": 240},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MODULE,
        "root_window_attachment",
        lambda _parent, _root, _markers: (None, "audit-governance"),
    )
    monkeypatch.setattr(
        MODULE,
        "STRICT_RELEASE_DISCOVERY_ROOT_ONLY",
        frozenset(MODULE.STRICT_RELEASE_DISCOVERY_ROOT_ONLY - {"补强"}),
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["补强"]["root_status"] == "eligible_root_inversion"
    assert by_root["补强"]["empirical_shell_ready"]
    assert by_root["补强"]["empirical_direct_ready"]
    assert by_root["补强"]["root_leave_one_out_ready"] is True
    assert by_root["补强"]["root_manual_hint_used"] is False
    assert by_root["补强"]["parent_category_count"] == 1
    assert by_root["补强"]["root_discovery_mode"] == (
        "root-first-empirical-shell-context"
    )

    disk_selected, disk_audit, disk_stats = MODULE.discover_root_inversion(
        aggregate,
        [],
        [],
        empirical_shell_db_path=tmp_path / "root-empirical-shells.sqlite3",
    )
    disk_by_root = {row["root"]: row for row in disk_audit}
    assert {row["root"] for row in disk_selected} == {
        row["root"] for row in selected
    }
    for field in (
        "root_status",
        "empirical_shell_parent_count",
        "empirical_shell_type_count",
        "empirical_shell_weighted_parent_coverage",
        "style_shell_type_count",
        "style_shell_parent_count",
        "style_shell_weighted_coverage",
        "style_shell_ready",
        "empirical_direct_ready",
    ):
        assert disk_by_root["补强"][field] == by_root["补强"][field]
    assert disk_stats["empirical_shell_store_disk_backed"] == 1
    assert disk_stats["empirical_shell_store_rows"] > 0

    _counts, families, _family_audit, stats = MODULE.stream_aggregate_candidates(
        aggregate,
        {},
        [],
        per_category_pool=1,
        root_inversion_rows=selected,
    )
    family_phrases = {row["phrase"] for row in families}
    assert {"语气补强", "补强理由"} <= family_phrases
    assert stats["root_family_selected_without_top_k"] >= 2


def test_root_inversion_keeps_single_roots_discovery_only_and_protects_generic(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "更稳",
        "很稳",
        "最稳",
        "较稳",
        "太稳",
        "会稳",
        "已经稳",
        "仍然稳",
        "最终稳",
        "稳一点",
        "需要使用",
        "可以使用",
        "继续使用",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 240, "message_coverage": 200},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["稳"]["root_status"] == "eligible_root_inversion"
    assert by_root["使用"]["root_status"] == "function_or_generic_exact"
    assert "使用" not in {row["root"] for row in selected}

    _counts, families, _family_audit, _stream_stats = (
        MODULE.stream_aggregate_candidates(
            aggregate,
            {},
            [],
            per_category_pool=20,
            root_inversion_rows=selected,
        )
    )
    assert all(len(row["phrase"]) >= 2 for row in families)
    assert "稳" not in {row["phrase"] for row in families}


def test_data_derived_short_seeds_feed_the_single_character_root_graph(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "更稳", "很稳", "最稳", "较稳", "太稳", "愈稳", "稳一点",
        "会稳", "已经稳", "仍然稳", "最终稳",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 240, "message_coverage": 200},
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )
    data_seeds = [
        {
            "phrase": phrase,
            "category": "certainty-limitation",
            "combined_occurrences": 800,
            "combined_coverage": 700,
            "source_kind": "raw-short-core-pass4",
        }
        for phrase in ("稳定", "稳妥", "不稳", "稳健")
    ]

    selected, audit, _stats = MODULE.discover_root_inversion(
        aggregate, [], data_seeds
    )
    by_root = {row["root"]: row for row in audit}
    assert by_root["稳"]["root_status"] == "eligible_root_inversion"
    assert by_root["稳"]["confirmed_parent_count"] >= 4
    assert "raw-short-core-pass4" in by_root["稳"]["parent_sources"]
    assert "稳" in {row["root"] for row in selected}


def test_root_inversion_flags_but_keeps_single_character_explained_by_longer_root(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = (
        "更直", "很直", "最直", "较直", "太直",
        "会直", "可以直", "需要直", "再直", "已经直",
        "更直接", "很直接", "最直接", "较直接", "太直接", "会直接",
        "直接",
    )
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 900 if phrase.endswith("直接") else 300,
                    "message_coverage": 800 if phrase.endswith("直接") else 250,
                },
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )

    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["直接"]["root_status"] == "eligible_root_inversion"
    assert by_root["直"]["root_status"] == "eligible_root_inversion"
    assert by_root["直"]["longer_root_dominance_flag"] is True
    assert by_root["直"]["dominated_by_root"] == "直接"
    assert "直" in {row["root"] for row in selected}


def test_root_inversion_hard_function_character_never_released_by_frequency(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": prefix + "不", "count": 1000, "message_coverage": 900},
                ensure_ascii=False,
            )
            for prefix in ("更", "很", "最", "较", "太", "愈")
        )
        + "\n",
        encoding="utf-8",
    )
    selected, audit, _stats = MODULE.discover_root_inversion(aggregate, [], [])
    by_root = {row["root"]: row for row in audit}
    assert by_root["不"]["root_status"] == "hard_function_character_stoplist"
    assert "不" not in {row["root"] for row in selected}


def test_root_probe_audits_coverage_one_without_allocating_context_graph(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": "稀见", "count": 1, "message_coverage": 1},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    audit_path = tmp_path / "root_probe.csv"

    selected, stats = MODULE.discover_aggregate_root_probes(
        aggregate, audit_path=audit_path
    )
    rows = {
        row["root"]: row
        for row in csv.DictReader(
            audit_path.open(encoding="utf-8-sig", newline="")
        )
    }

    assert "稀见" in rows
    assert rows["稀见"]["exact_chat_message_coverage"] == "1"
    assert rows["稀见"]["root_graph_selected"] == "False"
    assert rows["稀见"]["root_graph_decision"] == (
        "audit_only:below_context_graph_evidence"
    )
    assert "稀见" not in selected
    assert stats["aggregate_root_probes_observed"] >= 1


def test_root_probe_prior_evidence_rescues_low_coverage_root_for_graph(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": "稀见", "count": 1, "message_coverage": 1},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    selected, _stats = MODULE.discover_aggregate_root_probes(
        aggregate, required_roots={"稀见"}
    )

    assert "稀见" in selected


def test_root_probe_allowlist_keeps_unselected_root_in_light_audit(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 30, "message_coverage": 20},
                ensure_ascii=False,
            )
            for phrase in ("\u6536\u7d27", "\u6587\u4ef6")
        )
        + "\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.csv"

    selected, stats = MODULE.discover_aggregate_root_probes(
        aggregate,
        context_graph_allowlist={"\u6536\u7d27"},
        audit_path=audit,
    )
    rows = {
        row["root"]: row
        for row in csv.DictReader(audit.open(encoding="utf-8-sig", newline=""))
    }

    assert "\u6536\u7d27" in selected
    assert "\u6587\u4ef6" not in selected
    assert rows["\u6587\u4ef6"]["root_graph_decision"] == (
        "audit_only:not_in_context_graph_allowlist"
    )
    assert stats["aggregate_root_probes_excluded_by_context_graph_allowlist"] >= 1


def test_load_root_graph_allowlist_reads_only_selected_rows(tmp_path: Path) -> None:
    path = tmp_path / "roots.csv"
    path.write_text(
        "root,selected_for_targeted_long_scan\n"
        "\u6536\u7d27,True\n"
        "\u6587\u4ef6,False\n",
        encoding="utf-8",
    )

    assert MODULE.load_root_graph_allowlist(path) == {"\u6536\u7d27"}


def test_root_graph_allowlist_rescues_generic_complete_shell_roots(
    tmp_path: Path,
) -> None:
    path = tmp_path / "roots.csv"
    path.write_text(
        "root,selected_for_targeted_long_scan,basic_reason,shell_ready,"
        "exact_ready_for_long_scan,immediate_extension_fragment\n"
        "\u81ea\u7136,False,function_or_generic_exact,True,True,False\n"
        "\u8fdb\u884c,False,function_or_generic_exact,False,True,False\n"
        "\u5b50\u4ee3,False,function_or_generic_exact,True,True,True\n",
        encoding="utf-8",
    )

    assert MODULE.load_root_graph_allowlist(path) == {"\u81ea\u7136"}


def test_load_root_graph_fragment_blocklist_reads_clipped_roots(tmp_path: Path) -> None:
    path = tmp_path / "roots.csv"
    path.write_text(
        "root,immediate_extension_fragment\n"
        "\u6536\u7d27,False\n"
        "\u5b50\u4ee3,True\n",
        encoding="utf-8",
    )

    assert MODULE.load_root_graph_fragment_blocklist(path) == {"\u5b50\u4ee3"}


def test_bounded_root_inversion_keeps_document_noise_out_of_heavy_graph(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 80, "message_coverage": 60},
                ensure_ascii=False,
            )
            for phrase in (
                "\u6536\u7d27",
                "\u7ee7\u7eed\u6536\u7d27",
                "\u8fdb\u4e00\u6b65\u6536\u7d27",
                "\u6587\u4ef6",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    document_rows = [
        {
            "root": "\u6536\u7d27",
            "document_root_occurrences": 100,
            "document_root_unit_coverage": 80,
        },
        {
            "root": "\u6587\u4ef6",
            "document_root_occurrences": 10000,
            "document_root_unit_coverage": 8000,
        },
    ]

    _selected, audit, stats = MODULE.discover_root_inversion(
        aggregate,
        [],
        [],
        document_root_rows=document_rows,
        aggregate_root_allowlist={"\u6536\u7d27"},
    )

    assert "\u6536\u7d27" in {row["root"] for row in audit}
    assert "\u6587\u4ef6" not in {row["root"] for row in audit}
    assert stats["document_root_rows_retained_in_light_audit_only"] == 1


def test_long_parents_create_unseen_two_character_roots_without_prior_hints(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    parents = [
        "\u8fdb\u4e00\u6b65\u6536\u7d27",
        "\u7ee7\u7eed\u6536\u7d27",
        "\u540c\u6b65\u6536\u7d27",
    ]
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {"phrase": phrase, "count": 8, "message_coverage": 6},
                ensure_ascii=False,
            )
            for phrase in parents
        )
        + "\n",
        encoding="utf-8",
    )

    selected, stats = MODULE.discover_aggregate_root_probes(aggregate)

    assert "\u6536\u7d27" in selected
    assert selected["\u6536\u7d27"].short_parent_count == 3
    assert stats["aggregate_root_probe_long_parent_all_windows_rows"] == 3


def test_generic_root_is_discovered_from_complete_comparative_shells(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    phrases = ["\u81ea\u7136"] + [
        prefix + "\u81ea\u7136"
        for prefix in ("\u66f4", "\u5f88", "\u6700", "\u592a", "\u8f83", "\u6108")
    ]
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 1200 if phrase == "\u81ea\u7136" else 240,
                    "message_coverage": (
                        1000 if phrase == "\u81ea\u7136" else 200
                    ),
                },
                ensure_ascii=False,
            )
            for phrase in phrases
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "COMPARATIVE_ROOT_PATTERNS", ())

    selected, audit, _stats = MODULE.discover_root_inversion(
        aggregate,
        [],
        [],
        aggregate_root_allowlist={"\u81ea\u7136"},
    )
    by_root = {row["root"]: row for row in audit}

    assert "\u81ea\u7136" in {row["root"] for row in selected}
    assert by_root["\u81ea\u7136"]["root_status"] == "eligible_root_inversion"
    assert by_root["\u81ea\u7136"]["root_discovery_mode"] == (
        "generic-comparative-shell-context"
    )
    assert by_root["\u81ea\u7136"]["generic_complete_collocation_ready"]
    assert by_root["\u81ea\u7136"]["root_requires_complete_collocation"]
    assert by_root["\u81ea\u7136"]["root_manual_hint_used"] is False


def test_root_parent_records_multi_character_context_windows() -> None:
    evidence = defaultdict(MODULE.RootInversionEvidence)
    MODULE._record_root_inversion_parent(
        evidence,
        root="\u6536\u7d27",
        parent="\u5fc5\u987b\u8fdb\u4e00\u6b65\u6536\u7d27\u4e00\u70b9",
        category="scope-boundary",
        source="test",
        occurrences=5,
        coverage=4,
        shell=None,
        confirmed=False,
    )

    row = evidence["\u6536\u7d27"]
    assert row.left_context_windows["\u5fc5\u987b\u8fdb\u4e00\u6b65"] == 1
    assert row.right_context_windows["\u4e00\u70b9"] == 1
    assert row.context_envelopes["\u5fc5\u987b\u8fdb\u4e00\u6b65|\u4e00\u70b9"] == 1
    assert row.detailed_context_parent_evidence_count == 1
    assert row.omitted_detailed_context_parent_evidence_count == 0


def test_aggregate_root_parent_omits_only_audit_context_windows() -> None:
    evidence = defaultdict(MODULE.RootInversionEvidence)
    MODULE._record_root_inversion_parent(
        evidence,
        root="\u6536\u7d27",
        parent="\u518d\u6536\u7d27\u4e00\u70b9",
        category="scope-boundary",
        source="aggregate-root-window",
        occurrences=5,
        coverage=4,
        shell=None,
        confirmed=False,
        retain_parent_identity=False,
        retain_detailed_contexts=False,
    )

    row = evidence["\u6536\u7d27"]
    assert not row.left_context_windows
    assert not row.right_context_windows
    assert not row.context_envelopes
    assert row.left_contexts["\u518d"] == 1
    assert row.right_contexts["\u4e00"] == 1
    assert row.empirical_shells["B:\u518d|\u4e00\u70b9"] == 1
    assert row.parent_evidence_count == 1
    assert row.omitted_detailed_context_parent_evidence_count == 1
    assert row.detailed_context_parent_evidence_count == 0


def test_empirical_shell_store_preserves_exact_counts_on_disk(
    tmp_path: Path,
) -> None:
    path = tmp_path / "root-shells.sqlite3"
    store = MODULE.EmpiricalShellStore(path)
    store.add("\u6536\u7d27", "L:\u518d", 1, 20)
    store.add("\u6536\u7d27", "L:\u518d", 1, 30)
    store.add("\u6536\u7d27", "L:\u8fdb\u4e00\u6b65", 1, 40)
    store.add("\u7a33", "L:\u518d", 1, 50)
    store.finalize()

    assert store.root_type_counts() == {"\u6536\u7d27": 2, "\u7a33": 1}
    assert store.seed_root_map({"\u6536\u7d27"}) == {
        "L:\u518d": {"\u6536\u7d27"},
        "L:\u8fdb\u4e00\u6b65": {"\u6536\u7d27"},
    }
    assert store.shell_root_counts({"L:\u518d"}) == {"L:\u518d": 2}

    evidence = defaultdict(MODULE.RootInversionEvidence)
    evidence["\u6536\u7d27"]
    evidence["\u7a33"]
    store.hydrate_style_shells(evidence, {"L:\u518d"})
    assert evidence["\u6536\u7d27"].empirical_shells["L:\u518d"] == 2
    assert (
        evidence["\u6536\u7d27"].empirical_shell_weighted_coverages["L:\u518d"]
        == 50
    )
    assert evidence["\u7a33"].empirical_shells["L:\u518d"] == 1
    assert store.row_count() == 3
    store.close()
    assert path.exists()


def test_root_inversion_families_are_not_dropped_by_top_k(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        "\n".join(
            json.dumps(
                {
                    "phrase": phrase,
                    "count": 200 - index,
                    "message_coverage": 160 - index,
                },
                ensure_ascii=False,
            )
            for index, phrase in enumerate(("再收束", "要收束", "严收束"))
        )
        + "\n",
        encoding="utf-8",
    )
    roots = [
        {
            "root": "收束",
            "root_status": "eligible_root_inversion",
            "dominant_category": "scope-boundary",
            "parent_phrase_count": 10,
            "shell_parent_count": 8,
            "confirmed_parent_count": 0,
            "shell_type_count": 4,
            "discovery_score": 20.0,
            "example_parent_phrases": ["再收束", "要收束", "严收束"],
        }
    ]
    _counts, selected, audit, stats = MODULE.stream_aggregate_candidates(
        aggregate,
        {},
        [],
        per_category_pool=1,
        root_inversion_rows=roots,
    )
    # The category pool is deliberately smaller than the eligible family.
    # Root-family coverage, rather than heap rank, must still retain all rows.
    assert len(selected) == 3
    assert len(audit) == 3
    assert {row["pool_decision"] for row in audit} == {
        "selected_for_exact_rescan_no_top_k"
    }
    assert stats["root_inversion_family_dropped_by_pool"] == 0
    assert stats["root_inversion_family_unexpected_selection_gaps"] == 0


def test_invalid_comparative_interpretation_does_not_suppress_other_root_route(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": "已更新", "count": 180, "message_coverage": 150},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    roots = [
        {
            "root": "更新",
            "root_status": "eligible_root_inversion",
            "dominant_category": "process-broadcast",
            "parent_phrase_count": 20,
            "shell_parent_count": 10,
            "confirmed_parent_count": 5,
            "shell_type_count": 5,
            "shell_weighted_parent_coverage": 2000,
            "discovery_score": 20.0,
            "example_parent_phrases": ["已更新", "重新更新"],
        }
    ]

    _counts, selected, audit, stats = MODULE.stream_aggregate_candidates(
        aggregate,
        {},
        [],
        per_category_pool=1,
        root_inversion_rows=roots,
    )
    assert [row["phrase"] for row in selected] == ["已更新"]
    assert audit[0]["pool_decision"] == "selected_for_exact_rescan_no_top_k"
    assert stats["root_inversion_family_unexpected_selection_gaps"] == 0


def test_root_inversion_semantic_gate_releases_shell_and_blocks_content() -> None:
    base = {
        "category": "scope-boundary",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["收束"],
        "root_inversion_primary_root": "收束",
        "root_inversion_parent_count": 20,
        "root_inversion_shell_parent_count": 12,
        "root_inversion_confirmed_parent_count": 4,
        "root_inversion_shell_type_count": 4,
        "root_inversion_shell_weighted_parent_coverage": 1000,
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    rows = [
        semantic_row("收束"),
        dict(base, phrase="再收束"),
        dict(base, phrase="脚本收束"),
    ]
    annotated, _stats = MODULE.annotate_semantic_publication(rows)
    by_phrase = {row["phrase"]: row for row in annotated}
    assert by_phrase["再收束"]["semantic_release_decision"] == "publish_strict"
    assert (
        by_phrase["再收束"]["semantic_release_reason"]
        == "root_inversion_reversible_shell_and_live_context"
    )
    assert by_phrase["脚本收束"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["脚本收束"]["semantic_release_reason"] == "root_inversion_hard_content"


def test_generic_root_releases_only_complete_comparative_family() -> None:
    base = {
        "category": "certainty-limitation",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["\u81ea\u7136"],
        "root_inversion_primary_root": "\u81ea\u7136",
        "root_inversion_root_status": "eligible_root_inversion",
        "root_inversion_parent_count": 30,
        "root_inversion_shell_parent_count": 20,
        "root_inversion_confirmed_parent_count": 0,
        "root_inversion_shell_type_count": 6,
        "root_inversion_shell_weighted_parent_coverage": 2000,
        "root_inversion_root_first_shell_ready": True,
        "root_inversion_confirmed_context_ready": False,
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    rows = [
        dict(base, phrase="\u66f4\u81ea\u7136"),
        dict(base, phrase="\u81ea\u7136"),
        dict(base, phrase="\u81ea\u7136\u8bed\u8a00"),
    ]

    annotated, _stats = MODULE.annotate_semantic_publication(rows)
    by_phrase = {row["phrase"]: row for row in annotated}

    assert by_phrase["\u66f4\u81ea\u7136"]["semantic_release_decision"] == (
        "publish_strict"
    )
    assert by_phrase["\u66f4\u81ea\u7136"]["semantic_signals"][
        "generic_primary_comparative_shell"
    ]
    assert by_phrase["\u81ea\u7136"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["\u81ea\u7136"]["semantic_release_reason"] == (
        "root_inversion_generic_or_fragment_root"
    )
    assert by_phrase["\u81ea\u7136\u8bed\u8a00"][
        "semantic_release_decision"
    ] == "audit_only"


def test_root_inversion_shape_gate_separates_shell_exact_edge_and_fragment() -> None:
    roots = ["稳", "更稳", "收束", "正确", "生成"]
    expected = {
        "会更稳": "reversible_shell",
        "更稳一点": "reversible_shell",
        "进一步收束": "reversible_shell",
        "收束": "exact_root",
        "口径收束": "edge_context_pending",
        "术正确": "edge_context_pending",
        "生成资": "edge_context_pending",
    }
    for phrase, gate_kind in expected.items():
        shapes, reason = MODULE.classify_root_inversion_family_shapes(phrase, roots)
        assert reason == "eligible_root_inversion_recall"
        assert shapes[0]["gate_kind"] == gate_kind

    shapes, reason = MODULE.classify_root_inversion_family_shapes("收束一", roots)
    assert shapes == []
    assert reason == "known_noise_or_fragment"


def test_raw_root_family_route_keeps_nine_to_twelve_character_phrases(
    tmp_path: Path,
) -> None:
    phrase = "\u6d41\u7a0b\u8303\u56f4\u9700\u8981\u8fdb\u4e00\u6b65\u6536\u7d27"
    assert 9 <= len(phrase) <= 12
    aggregate = tmp_path / "aggregate.jsonl"
    aggregate.write_text(
        json.dumps(
            {"phrase": phrase, "count": 80, "message_coverage": 60},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    raw_rows = [
        {
            "phrase": "\u6536\u7d27",
            "category": "scope-boundary",
            "aggregate_chat_message_coverage": 100,
        }
    ]

    _counts, selected, _audit, _stats = MODULE.stream_aggregate_candidates(
        aggregate,
        {},
        [],
        per_category_pool=10,
        raw_short_rows=raw_rows,
    )

    row = next(item for item in selected if item["phrase"] == phrase)
    assert row["source_kind"] == "raw-core-family-pass5"


def test_root_inversion_edge_requires_diverse_exact_source_contexts() -> None:
    base = {
        "category": "scope-boundary",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["收束"],
        "root_inversion_primary_root": "收束",
        "root_inversion_shell_parent_count": 12,
        "root_inversion_shell_type_count": 4,
        "root_inversion_shell_weighted_parent_coverage": 1000,
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.0,
        "chat_context_right_boundary_rate": 0.0,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    good = dict(base, phrase="口径收束")
    clipped = dict(
        base,
        phrase="术语收束",
        chat_context_left_nonboundary_dominance=0.95,
    )
    modifier = semantic_row("口径")
    annotated, _stats = MODULE.annotate_semantic_publication(
        [semantic_row("收束"), modifier, semantic_row("术语"), good, clipped]
    )
    by_phrase = {row["phrase"]: row for row in annotated}
    assert by_phrase["口径收束"]["semantic_release_decision"] == "publish_strict"
    assert (
        by_phrase["口径收束"]["semantic_release_reason"]
        == "root_inversion_edge_verified_by_live_context"
    )
    assert by_phrase["术语收束"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["术语收束"]["semantic_release_reason"].startswith(
        "root_inversion_live_context:"
    )


def test_root_inversion_edge_rejects_single_character_fixed_width_modifier() -> None:
    family = {
        "phrase": "轮只做",
        "category": "process-broadcast",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["只做"],
        "root_inversion_primary_root": "只做",
        "root_inversion_shell_parent_count": 12,
        "root_inversion_shell_type_count": 4,
        "root_inversion_shell_weighted_parent_coverage": 1000,
        "root_inversion_gate_kind": "edge_context_pending",
        "root_inversion_prefix": "轮",
        "root_inversion_suffix": "",
        "chat_message_coverage": 500,
        "md_unit_coverage": 5,
        "tex_unit_coverage": 0,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    annotated, _stats = MODULE.annotate_semantic_publication(
        [semantic_row("只做"), family]
    )
    by_phrase = {row["phrase"]: row for row in annotated}
    assert by_phrase["轮只做"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["轮只做"]["semantic_release_reason"] == (
        "root_inversion_edge_modifier:edge_modifier_length_lt_2"
    )


def test_root_inversion_requires_the_primary_root_itself_to_be_anchored() -> None:
    family = {
        "phrase": "再收束",
        "category": "scope-boundary",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["收束"],
        "root_inversion_primary_root": "收束",
        "root_inversion_shell_parent_count": 12,
        "root_inversion_shell_type_count": 4,
        "root_inversion_shell_weighted_parent_coverage": 1000,
        "root_inversion_gate_kind": "reversible_shell",
        "root_inversion_prefix": "再",
        "root_inversion_suffix": "",
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    # An unrelated released core inside another route must not anchor 收束.
    annotated, _stats = MODULE.annotate_semantic_publication(
        [semantic_row("再"), family]
    )
    by_phrase = {row["phrase"]: row for row in annotated}
    assert by_phrase["再收束"]["semantic_release_decision"] == "audit_only"
    assert by_phrase["再收束"]["semantic_release_reason"] == (
        "root_inversion_primary_root_not_cross_source_anchored"
    )


@pytest.mark.parametrize(
    ("phrase", "root", "prefix", "suffix", "component"),
    [
        ("进一步判断", "进一步", "", "判断", "判断"),
        ("傅里叶展开", "展开", "傅里叶", "", "傅里叶"),
    ],
)
def test_root_inversion_protects_neutral_content_inside_edge_family(
    phrase: str,
    root: str,
    prefix: str,
    suffix: str,
    component: str,
) -> None:
    anchor = semantic_row(root)
    protected_component = semantic_row(component)
    family = {
        "phrase": phrase,
        "category": "academic-packaging",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": [root],
        "root_inversion_primary_root": root,
        "root_inversion_shell_parent_count": 12,
        "root_inversion_shell_type_count": 4,
        "root_inversion_shell_weighted_parent_coverage": 1000,
        "root_inversion_gate_kind": "edge_context_pending",
        "root_inversion_prefix": prefix,
        "root_inversion_suffix": suffix,
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    annotated, _stats = MODULE.annotate_semantic_publication(
        [anchor, protected_component, family]
    )
    by_phrase = {row["phrase"]: row for row in annotated}
    assert by_phrase[phrase]["semantic_release_decision"] == "audit_only"
    assert by_phrase[phrase]["semantic_release_reason"] in {
        "root_inversion_hard_content",
        "root_inversion_protected_component",
    }


def test_confirmed_parent_count_cannot_bypass_root_shell_evidence() -> None:
    row = {
        "phrase": "再收束",
        "category": "scope-boundary",
        "source_kind": "root-inversion-family-pass8",
        "trigger_phrases": ["收束"],
        "root_inversion_primary_root": "收束",
        "root_inversion_shell_parent_count": 0,
        "root_inversion_shell_type_count": 0,
        "root_inversion_shell_weighted_parent_coverage": 0,
        "root_inversion_confirmed_parent_count": 999,
        "chat_message_coverage": 500,
        "md_unit_coverage": 80,
        "tex_unit_coverage": 10,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
    }
    annotated, _stats = MODULE.annotate_semantic_publication(
        [semantic_row("收束"), row]
    )
    by_phrase = {item["phrase"]: item for item in annotated}
    assert by_phrase["再收束"]["semantic_release_decision"] == "audit_only"
    assert (
        by_phrase["再收束"]["semantic_release_reason"]
        == "root_inversion_root_not_shell_ready"
    )


def test_root_inversion_family_inherits_released_core_document_anchor() -> None:
    base = {
        "phrase": "再收束",
        "category": "scope-boundary",
        "source_kind": "root-inversion-family-pass8",
        "semantic_release_decision": "publish_strict",
        "semantic_signals": {"cross_source_released_roots": ["收束"]},
        "root_inversion_gate_kind": "reversible_shell",
        "chat_message_coverage": 120,
        "md_unit_coverage": 0,
        "tex_unit_coverage": 0,
        "combined_coverage": 120,
        "combined_occurrences": 140,
        "combined_score": 20.0,
        "chat_context_left_context_count": 8,
        "chat_context_right_context_count": 8,
        "chat_context_left_boundary_rate": 0.1,
        "chat_context_right_boundary_rate": 0.1,
        "chat_context_left_nonboundary_dominance": 0.4,
        "chat_context_right_nonboundary_dominance": 0.4,
        "trigger_phrases": ["收束"],
    }
    final, rejected, _stats = MODULE.select_final([base], 10, 10)
    assert [row["phrase"] for row in final] == ["再收束"]
    assert rejected == []

    edge_without_document = dict(
        base,
        phrase="口径收束",
        root_inversion_gate_kind="edge_context_pending",
    )
    final, rejected, _stats = MODULE.select_final(
        [edge_without_document], 10, 10
    )
    assert final == []
    assert (
        rejected[0]["final_rejection_reason"]
        == "root_inversion_edge_document_unit_coverage_lt_1"
    )

    edge_with_document = dict(edge_without_document, md_unit_coverage=1)
    final, rejected, _stats = MODULE.select_final([edge_with_document], 10, 10)
    assert [row["phrase"] for row in final] == ["口径收束"]
    assert rejected == []


@pytest.mark.parametrize(
    "phrase",
    [
        "解释", "影响", "替换", "分析", "子代理", "技术", "结果", "方法",
        "方案", "标准", "验证", "测试", "生成", "正确", "申请", "权限",
        "条件", "证据", "正文", "实现", "记录", "检查", "优化", "边界", "删除",
    ],
)
def test_new_content_protections_cannot_become_literal_short_bans(phrase: str) -> None:
    decision = MODULE.classify_raw_short_semantic_publication(semantic_row(phrase))
    assert decision["semantic_release_decision"] == "audit_only"
    assert decision["semantic_release_reason"] == "protected_content_exact"


@pytest.mark.parametrize("phrase", ["保持原", "不能因", "论文写"])
def test_new_fixed_width_fragments_stay_audit_only(phrase: str) -> None:
    decision = MODULE.classify_raw_short_semantic_publication(semantic_row(phrase))
    assert decision["semantic_release_decision"] == "audit_only"
    assert decision["semantic_release_reason"] == "known_short_fragment"
