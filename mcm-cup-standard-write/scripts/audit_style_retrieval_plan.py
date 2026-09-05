#!/usr/bin/env python3
"""Audit a section-bound CUMCM style retrieval plan before release.

The plan is evidence for how a draft was exposed to human-paper prose.  This
audit never treats retrieved text as a source of facts and never rewrites the
manuscript; it only checks that the plan is fresh, section-complete, and
holdout-safe for the exact manuscript being released.

Public interface:
    python audit_style_retrieval_plan.py <main.tex> --plan plan.json
        --problem-type A|B|C --format text|json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_content_density import normalize_tex
from audit_manuscript import read_tex_tree
from prepare_style_retrieval_plan import (
    GENERATOR_PATH,
    PRIMARY_SCORE_TOLERANCE,
    RETRIEVAL_ENGINE_PATH,
    STYLE_PORTFOLIO_SCORE_TOLERANCE,
    build_plan,
    section_targets,
)
from query_style_patterns import FULLTEXT_INDEX, HOLDOUT_RESERVATIONS, load_holdout_record_ids


SCHEMA = "mcm-style-retrieval-audit/v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finding(findings: list[dict[str, object]], code: str, **detail: object) -> None:
    findings.append({"severity": "error", "code": code, **detail})


def audit(main_tex: Path, plan_path: Path, problem_type: str) -> dict[str, object]:
    main_tex = main_tex.resolve()
    plan_path = plan_path.resolve()
    findings: list[dict[str, object]] = []
    if not main_tex.is_file():
        _finding(findings, "MANUSCRIPT_MISSING", path=str(main_tex))
        return {"schema": SCHEMA, "status": "fail", "errors": len(findings), "findings": findings}
    if not plan_path.is_file():
        _finding(findings, "STYLE_PLAN_MISSING", path=str(plan_path))
        return {"schema": SCHEMA, "status": "fail", "errors": len(findings), "findings": findings}
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _finding(findings, "STYLE_PLAN_UNREADABLE", path=str(plan_path), detail=str(exc))
        return {"schema": SCHEMA, "status": "fail", "errors": len(findings), "findings": findings}

    if plan.get("schema") != "mcm-style-retrieval-plan/v1":
        _finding(findings, "STYLE_PLAN_SCHEMA_MISMATCH", schema=plan.get("schema"))
    if plan.get("status") != "pass" or plan.get("errors", 1):
        _finding(findings, "STYLE_PLAN_NOT_PASSING", status=plan.get("status"), errors=plan.get("errors"))
    if plan.get("problem_type") != problem_type:
        _finding(findings, "STYLE_PLAN_PROBLEM_TYPE_MISMATCH", expected=problem_type, actual=plan.get("problem_type"))

    source = plan.get("source") if isinstance(plan.get("source"), dict) else {}
    actual_source_hash = sha256_file(main_tex)
    if source.get("sha256") != actual_source_hash:
        _finding(findings, "STYLE_PLAN_SOURCE_DRIFT", expected=actual_source_hash, actual=source.get("sha256"))
    raw = normalize_tex(read_tex_tree(main_tex))
    actual_tree_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if source.get("tex_tree_sha256") != actual_tree_hash:
        _finding(
            findings, "STYLE_PLAN_TEX_TREE_DRIFT",
            expected=actual_tree_hash, actual=source.get("tex_tree_sha256"),
        )

    corpus = plan.get("corpus") if isinstance(plan.get("corpus"), dict) else {}
    for key, path in (("fulltext_index", FULLTEXT_INDEX), ("holdout_reservations", HOLDOUT_RESERVATIONS)):
        recorded_path = corpus.get(key)
        recorded_hash_key = f"{key}_sha256"
        if not path.is_file():
            _finding(findings, "STYLE_CORPUS_FILE_MISSING", key=key, path=str(path))
            continue
        current_hash = sha256_file(path)
        if recorded_path != str(path):
            _finding(findings, "STYLE_CORPUS_PATH_MISMATCH", key=key, expected=str(path), actual=recorded_path)
        if corpus.get(recorded_hash_key) != current_hash:
            _finding(findings, "STYLE_CORPUS_DRIFT", key=key, expected=current_hash, actual=corpus.get(recorded_hash_key))

    generator = plan.get("generator") if isinstance(plan.get("generator"), dict) else {}
    for key, path in (("plan_builder", GENERATOR_PATH), ("retrieval_engine", RETRIEVAL_ENGINE_PATH)):
        record = generator.get(key) if isinstance(generator.get(key), dict) else {}
        if record.get("path") != str(path) or record.get("sha256") != sha256_file(path):
            _finding(findings, "STYLE_PLAN_GENERATOR_DRIFT", component=key)

    policy = plan.get("policy") if isinstance(plan.get("policy"), dict) else {}
    minimum = policy.get("minimum_anchors_per_target")
    maximum = policy.get("maximum_anchors_per_target")
    if not isinstance(minimum, int) or not isinstance(maximum, int) or not 3 <= minimum <= maximum <= 8:
        _finding(findings, "STYLE_PLAN_POLICY_INVALID", minimum=minimum, maximum=maximum)
        minimum, maximum = 3, 8
    if policy.get("minimum_distinct_papers_per_target") != 2:
        _finding(findings, "STYLE_PLAN_DIVERSITY_POLICY_INVALID")
    if (
        policy.get("primary_anchor_selection") != "relevance-bounded-low-reuse"
        or policy.get("primary_anchor_score_tolerance") != PRIMARY_SCORE_TOLERANCE
    ):
        _finding(findings, "STYLE_PLAN_PRIMARY_POLICY_INVALID")
    if (
        policy.get("supporting_anchor_selection") != "relevance-bounded-style-portfolio"
        or policy.get("supporting_anchor_score_tolerance") != STYLE_PORTFOLIO_SCORE_TOLERANCE
        or set(policy.get("supporting_anchor_dimensions", []))
        != {
            "paper", "action_sequence", "opening_family", "closing_family", "ending_action",
            "cadence_band", "formula_nearby", "visual_nearby",
        }
    ):
        _finding(findings, "STYLE_PLAN_PORTFOLIO_POLICY_INVALID")
    if policy.get("copying_forbidden") is not True or policy.get("facts_must_come_from_current_problem") is not True:
        _finding(findings, "STYLE_PLAN_USAGE_POLICY_WEAK")

    reserved = load_holdout_record_ids()
    targets = plan.get("targets") if isinstance(plan.get("targets"), list) else []
    expected = section_targets(raw)
    expected_signature = [(title, role, line, question_id) for title, role, _scope, line, question_id in expected]
    actual_signature = [
        (item.get("title"), item.get("role"), item.get("line"), item.get("question_id"))
        for item in targets if isinstance(item, dict)
    ]
    if actual_signature != expected_signature:
        _finding(
            findings, "STYLE_PLAN_TARGET_DRIFT",
            expected_count=len(expected_signature), actual_count=len(actual_signature),
        )
    if not targets:
        _finding(findings, "STYLE_PLAN_HAS_NO_TARGETS")
    for index, item in enumerate(targets, 1):
        if not isinstance(item, dict):
            _finding(findings, "STYLE_PLAN_TARGET_INVALID", target=index)
            continue
        anchors = item.get("anchors") if isinstance(item.get("anchors"), list) else []
        if not minimum <= len(anchors) <= maximum:
            _finding(findings, "STYLE_ANCHOR_COUNT_INVALID", target=item.get("id", index), count=len(anchors))
        anchor_ids = [anchor.get("id") for anchor in anchors if isinstance(anchor, dict)]
        if len(anchor_ids) != len(set(anchor_ids)):
            _finding(findings, "STYLE_ANCHOR_DUPLICATE", target=item.get("id", index))
        distinct_papers = {
            str(anchor.get("paper")) for anchor in anchors
            if isinstance(anchor, dict) and anchor.get("paper")
        }
        if len(distinct_papers) < 2:
            _finding(
                findings, "STYLE_ANCHOR_PAPER_DIVERSITY_THIN",
                target=item.get("id", index), distinct_papers=sorted(distinct_papers), minimum=2,
            )
        portfolio = item.get("style_portfolio_summary") if isinstance(item.get("style_portfolio_summary"), dict) else {}
        scores = [int(anchor.get("score", 0)) for anchor in anchors if isinstance(anchor, dict)]
        best_score = max(scores, default=0)
        score_deltas = [best_score - score for score in scores]
        if (
            portfolio.get("selection") != "relevance-bounded-style-portfolio"
            or portfolio.get("score_tolerance") != STYLE_PORTFOLIO_SCORE_TOLERANCE
            or portfolio.get("anchors") != len(anchors)
            or portfolio.get("distinct_papers") != len(distinct_papers)
            or portfolio.get("best_score") != best_score
            or portfolio.get("score_deltas") != score_deltas
            or portfolio.get("outside_score_tolerance")
            != sum(delta > STYLE_PORTFOLIO_SCORE_TOLERANCE for delta in score_deltas)
            or not isinstance(portfolio.get("distinct_ending_actions"), int)
            or portfolio.get("distinct_ending_actions", 0) <= 0
            or not isinstance(portfolio.get("shapes"), list)
            or len(portfolio.get("shapes", [])) != len(anchors)
            or any(not shape.get("ending_action") for shape in portfolio.get("shapes", []))
        ):
            _finding(findings, "STYLE_ANCHOR_PORTFOLIO_INVALID", target=item.get("id", index))
        if item.get("usage_rule") and "Do not copy sentences" not in str(item.get("usage_rule")):
            _finding(findings, "STYLE_PLAN_USAGE_RULE_WEAK", target=item.get("id", index))
        for anchor in anchors:
            if not isinstance(anchor, dict) or not anchor.get("id"):
                _finding(findings, "STYLE_ANCHOR_INVALID", target=item.get("id", index))
                continue
            if anchor["id"] in reserved:
                _finding(findings, "RESERVED_HOLDOUT_LEAK", target=item.get("id", index), record_id=anchor["id"])
            if anchor.get("source_type") != "fulltext":
                _finding(findings, "STYLE_ANCHOR_SOURCE_INVALID", target=item.get("id", index), record_id=anchor["id"])

    context_window = policy.get("context_window")
    if not isinstance(context_window, int) or context_window not in {0, 1, 2}:
        _finding(findings, "STYLE_PLAN_CONTEXT_WINDOW_INVALID", actual=context_window)
    else:
        expected_plan = build_plan(main_tex, problem_type, minimum, maximum, context_window)
        if (
            plan.get("targets") != expected_plan.get("targets")
            or plan.get("corpus") != expected_plan.get("corpus")
            or plan.get("generator") != expected_plan.get("generator")
            or plan.get("policy") != expected_plan.get("policy")
            or plan.get("primary_anchor_summary") != expected_plan.get("primary_anchor_summary")
        ):
            _finding(
                findings,
                "STYLE_PLAN_RETRIEVAL_DRIFT",
                detail="retrieved anchors or their full-text metadata do not match deterministic recomputation",
            )

    errors = len(findings)
    return {
        "schema": SCHEMA,
        "status": "pass" if errors == 0 else "fail",
        "problem_type": problem_type,
        "manuscript": {
            "path": str(main_tex),
            "sha256": actual_source_hash,
            "tex_tree_sha256": actual_tree_hash,
        },
        "plan": {"path": str(plan_path), "sha256": sha256_file(plan_path)},
        "target_count": len(targets),
        "minimum_anchors": minimum,
        "maximum_anchors": maximum,
        "minimum_distinct_papers": 2,
        "reserved_records_excluded": len(reserved),
        "errors": errors,
        "warnings": 0,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("main_tex", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--problem-type", choices=("A", "B", "C"), required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.main_tex, args.plan, args.problem_type)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"STYLE RETRIEVAL AUDIT {report['status'].upper()} "
            f"targets={report.get('target_count', 0)} errors={report['errors']}"
        )
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['code']}: {finding}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
