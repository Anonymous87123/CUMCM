from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_humanize_root_closure.py"
SPEC = importlib.util.spec_from_file_location("run_humanize_root_closure", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_canonical_set_hash_ignores_order_and_duplicates() -> None:
    assert MODULE.canonical_set_sha256(["收紧", "更稳", "收紧"]) == (
        MODULE.canonical_set_sha256(["更稳", "收紧"])
    )


def test_root_accounting_accepts_explicit_pre_exact_fragment_rejection(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "round-01"
    run_dir.mkdir()
    (run_dir / "root_inversion_selected_roots.json").write_text(
        json.dumps([{"root": "fragment-root"}]), encoding="utf-8"
    )
    (run_dir / "root_inversion_family_candidate_audit.csv").write_text(
        "phrase,root_inversion_primary_root,selected_for_exact_rescan,"
        "pool_decision,preselection_reason,final_rejection_reason\n"
        "fragment,fragment-root,False,"
        "rejected_before_pool:known_noise_or_fragment,,\n",
        encoding="utf-8",
    )
    (run_dir / "all_candidates_after_exact_rescan.csv").write_text(
        "phrase,root_inversion_primary_root\n", encoding="utf-8"
    )

    rows, blockers = MODULE.build_root_release_accounting(run_dir, set())

    assert blockers == {}
    assert rows[0]["status"] == "TERMINAL_REJECTED_PRE_EXACT_REVIEW"
    assert rows[0]["family_terminal_rejection_count"] == 1
    assert rows[0]["terminal_rejection_count"] == 1
    assert rows[0]["terminal_rejection_reasons"] == {
        "rejected_before_pool:known_noise_or_fragment": 1
    }


def test_pool_blockers_reject_quota_limited_false_convergence() -> None:
    summary = {
        "selection": {"rejection/longphrase_target_cap": 3},
        "aggregate_discovery": {
            "root_inversion_family_dropped_by_pool": 2,
            "root_inversion_family_unexpected_selection_gaps": 1,
        },
        "document_ngram_discovery": {
            "document_ngram_candidates_dropped_by_pool": 7
        },
        "csv_decomposition": {"parents_truncated_to_limit": 4},
    }
    assert MODULE.pool_blockers(summary) == {
        "longphrase_target_cap": 3,
        "root_family_pool_drops": 2,
        "root_family_selection_gaps": 1,
        "document_root_pool_drops": 7,
        "decomposition_parent_pool_drops": 4,
    }


def test_round_convergence_requires_bidirectional_stability() -> None:
    state = {
        "new_phrase_count": 0,
        "removed_phrase_count": 0,
        "new_candidate_phrase_count": 0,
        "removed_candidate_phrase_count": 0,
        "new_root_count": 0,
        "removed_root_count": 0,
        "new_selected_inversion_root_count": 0,
        "removed_selected_inversion_root_count": 0,
        "pool_blockers": {},
        "root_accounting_blockers": {},
    }
    assert not MODULE.round_is_converged(1, state)
    assert MODULE.round_is_converged(2, state)
    for field in (
        "new_phrase_count",
        "removed_phrase_count",
        "new_candidate_phrase_count",
        "removed_candidate_phrase_count",
        "new_root_count",
        "removed_root_count",
        "new_selected_inversion_root_count",
        "removed_selected_inversion_root_count",
    ):
        changed = {**state, field: 1}
        assert not MODULE.round_is_converged(2, changed), field
    assert not MODULE.round_is_converged(
        2, {**state, "pool_blockers": {"subphrase_target_cap": 1}}
    )
    assert not MODULE.round_is_converged(
        2,
        {
            **state,
            "root_accounting_blockers": {
                "selected_roots_without_exact_rescan": 1
            },
        },
    )
def test_build_round_state_tracks_new_phrases_roots_and_candidate_set(
    tmp_path: Path,
    ) -> None:
    run_dir = tmp_path / "round-01"
    run_dir.mkdir()
    (run_dir / "strict_ai_phrase_inventory_expanded.json").write_text(
        json.dumps(
            {"entries": [{"phrase": "更稳"}, {"phrase": "完整闭环"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "all_candidates_after_exact_rescan.csv").write_text(
        "phrase,category,root_inversion_primary_root,semantic_release_decision,semantic_release_reason\n"
        "更稳,certainty-limitation,稳,publish_strict,root_release\n"
        "再收紧,scope-boundary,收紧,audit_only,cross_source_missing\n",
        encoding="utf-8",
    )
    (run_dir / "root_inversion_family_candidate_audit.csv").write_text(
        "phrase,root_inversion_primary_root,selected_for_exact_rescan\n"
        "更稳,稳,True\n"
        "再收紧,收紧,True\n",
        encoding="utf-8",
    )
    (run_dir / "root_inversion_selected_roots.json").write_text(
        json.dumps([{"root": "稳"}, {"root": "收紧"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "single_character_root_rankings.json").write_text(
        json.dumps(
            [
                {"root": "稳", "root_status": "eligible_root"},
                {"root": "的", "root_status": "function_character_stoplist"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config_hash = MODULE.file_sha256(MODULE.semantic_config_path(SCRIPT))
    config_schema = "semantic-publication/v8"
    expander_hash = MODULE.file_sha256(SCRIPT)
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "selection": {},
                "aggregate_discovery": {},
                "document_ngram_discovery": {},
                "csv_decomposition": {},
                "semantic_release_config_sha256": config_hash,
                "semantic_release_config_schema": config_schema,
                "expander_sha256": expander_hash,
            }
        ),
        encoding="utf-8",
    )

    state = MODULE.build_round_state(
        iteration=1,
        run_dir=run_dir,
        baseline_phrases={"更稳"},
        previous_candidate_phrases={"更稳", "旧候选"},
        previous_roots={"稳"},
        previous_selected_inversion_roots={"former-root"},
        aggregate_sha256="a" * 64,
        chat_snapshot_sha256="b" * 64,
        document_snapshot_sha256="c" * 64,
        expander_sha256=expander_hash,
        semantic_release_config_sha256=config_hash,
        semantic_release_config_schema=config_schema,
    )
    assert state["new_phrase_count"] == 1
    assert state["removed_phrase_count"] == 0
    assert state["new_phrase_examples"] == ["完整闭环"]
    assert state["new_root_count"] == 1
    assert state["removed_root_count"] == 0
    assert state["selected_inversion_root_count"] == 2
    assert state["new_selected_inversion_root_count"] == 2
    assert state["removed_selected_inversion_root_count"] == 1
    assert state["removed_selected_inversion_root_examples"] == ["former-root"]
    assert state["new_root_examples"] == ["收紧"]
    assert state["candidate_phrase_count"] == 2
    assert state["new_candidate_phrase_count"] == 1
    assert state["new_candidate_phrase_examples"] == ["再收紧"]
    assert state["removed_candidate_phrase_count"] == 1
    assert state["removed_candidate_phrase_examples"] == ["旧候选"]
    assert state["pool_blockers"] == {}
    assert state["root_accounting_blockers"] == {}
    assert state["expander_sha256"] == expander_hash
    assert state["root_release_accounting"] == {
        "selected_root_count": 2,
        "released_root_count": 1,
        "terminal_rejected_review_count": 1,
        "unrouted_candidate_count": 0,
        "terminal_rejected_review_roots": ["收紧"],
    }
    assert (run_dir / "root_release_accounting.json").exists()
    assert (run_dir / "root_release_accounting.csv").exists()


def test_build_round_state_rejects_semantic_config_hash_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "round-01"
    run_dir.mkdir()
    (run_dir / "strict_ai_phrase_inventory_expanded.json").write_text(
        json.dumps({"entries": []}), encoding="utf-8"
    )
    (run_dir / "all_candidates_after_exact_rescan.csv").write_text(
        "phrase\n", encoding="utf-8"
    )
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "selection": {},
                "aggregate_discovery": {},
                "document_ngram_discovery": {},
                "csv_decomposition": {},
                "semantic_release_config_sha256": "0" * 64,
                "semantic_release_config_schema": "semantic-publication/v8",
                "expander_sha256": MODULE.file_sha256(SCRIPT),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="config changed during closure"):
        MODULE.build_round_state(
            iteration=1,
            run_dir=run_dir,
            baseline_phrases=set(),
            previous_candidate_phrases=set(),
            previous_roots=set(),
            previous_selected_inversion_roots=set(),
            aggregate_sha256="a" * 64,
            chat_snapshot_sha256="b" * 64,
            document_snapshot_sha256="c" * 64,
            expander_sha256=MODULE.file_sha256(SCRIPT),
            semantic_release_config_sha256="1" * 64,
            semantic_release_config_schema="semantic-publication/v8",
        )


def test_build_round_state_rejects_expander_hash_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "round-01"
    run_dir.mkdir()
    (run_dir / "strict_ai_phrase_inventory_expanded.json").write_text(
        json.dumps({"entries": []}), encoding="utf-8"
    )
    (run_dir / "all_candidates_after_exact_rescan.csv").write_text(
        "phrase\n", encoding="utf-8"
    )
    config_hash = MODULE.file_sha256(MODULE.semantic_config_path(SCRIPT))
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "selection": {},
                "aggregate_discovery": {},
                "document_ngram_discovery": {},
                "csv_decomposition": {},
                "semantic_release_config_sha256": config_hash,
                "semantic_release_config_schema": "semantic-publication/v8",
                "expander_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="expander changed during closure"):
        MODULE.build_round_state(
            iteration=1,
            run_dir=run_dir,
            baseline_phrases=set(),
            previous_candidate_phrases=set(),
            previous_roots=set(),
            previous_selected_inversion_roots=set(),
            aggregate_sha256="a" * 64,
            chat_snapshot_sha256="b" * 64,
            document_snapshot_sha256="c" * 64,
            expander_sha256="1" * 64,
            semantic_release_config_sha256=config_hash,
            semantic_release_config_schema="semantic-publication/v8",
        )
