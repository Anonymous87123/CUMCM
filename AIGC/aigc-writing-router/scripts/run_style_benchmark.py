#!/usr/bin/env python3
"""Run reproducible dev/holdout blind benchmarks for AIGC writing candidates.

Public interfaces:
    python run_style_benchmark.py init SUITE.json --output-dir RUN
    python run_style_benchmark.py register MANIFEST.json --case-id ID
    --provider NAME --trial N --candidate FILE --verification REPORT --output NEXT.json
        --generation GENERATION.json
    python run_style_benchmark.py prepare MANIFEST.json --seed N --output NEXT.json
    python run_style_benchmark.py package-review MANIFEST.json --output NEXT.json
    python run_style_benchmark.py score MANIFEST.json RATINGS.csv \
        --ratings-merge RATINGS-MERGE.json --output NEXT.json
    python run_style_benchmark.py audit MANIFEST.json --format text|json
    python run_style_benchmark.py aggregate MANIFEST.json [...] --output REPORT.json
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import copy
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import shutil
import unicodedata

from adapter_core import find_package, read_registry, sha256_file, write_json
from blind_pair_evaluation import DIMENSIONS, prepare as prepare_blind, score as score_blind
from merge_style_benchmark_ratings import audit_merge_report
from render_style_benchmark_review import audit_bundle as audit_review_bundle, render_review
from route_aigc_tools import DOCUMENT_FORMATS, DOCUMENT_TYPES, select_route
from run_stack_evaluation import evaluate as evaluate_stack


SUITE_SCHEMA = "aigc-style-benchmark-suite/v1"
MANIFEST_SCHEMA = "aigc-style-benchmark-manifest/v1"
GENERATION_SCHEMA = "aigc-benchmark-generation/v1"
SCORING_PROTOCOL = "aigc-blind-scoring/v2"
CONTENT_NORMALIZATION = "unicode-nfkc-collapse-whitespace/v1"
BENCHMARK_GOALS = {"preservation", "improvement"}
AUTHORING_DECISIONS = {"NO_CHANGE", "REWRITE"}
GENERATION_EVIDENCE_TYPES = {"stack_evaluation"}
FAILURE_SCHEMA = "aigc-style-failure-capsules/v1"
PORTFOLIO_SCHEMA = "aigc-style-benchmark-portfolio/v1"
STATES = {
    "SOURCE_FROZEN",
    "CANDIDATES_READY",
    "BLIND_READY",
    "SCORED_DEV",
    "SCORED_HOLDOUT_SEALED",
}
SCORED_STATES = {"SCORED_DEV", "SCORED_HOLDOUT_SEALED"}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ALLOWED_CHALLENGES = {
    "public-judgment", "specificity", "content-density", "semantic-fidelity",
    "math-protection", "citation-protection", "voice", "causal-calibration",
    "boundary-conditions", "result-explanation", "paragraph-rhythm",
}
ACTION_BY_DIMENSION = {
    "naturalness": (
        "复查句群节奏、段落起落和作者常用衔接；不要改成新的统一套话或继续叠加禁用词。"
    ),
    "judgment_trajectory": (
        "补回可公开的证据、犹豫点、候选比较或边界裁决；不要套固定步骤标题。"
    ),
    "specificity": (
        "恢复数据对象、变量、阈值、事件对象和适用条件，删除可替换到任何题目的泛句。"
    ),
    "content_density": (
        "区分重复扩写与推导缺口：前者合并，后者补足依据、结果解释或检验。"
    ),
    "semantic_fidelity": (
        "停止润色并丢弃该候选；从冻结源重新处理限定、否定、因果、数字和数学方向。"
    ),
}


def _add(findings: list[dict], severity: str, code: str, **detail: object) -> None:
    findings.append({"severity": severity, "code": code, **detail})


def _locked(path: Path) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _normalize_benchmark_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("\ufeff", "").replace("\u200b", ""))
    return " ".join(text.split())


def _content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _content_delta(left_path: Path, right_path: Path, *, trial_pair: bool = False) -> dict:
    left = _normalize_benchmark_text(left_path.read_text(encoding="utf-8-sig"))
    right = _normalize_benchmark_text(right_path.read_text(encoding="utf-8-sig"))
    if not left or not right:
        raise ValueError("benchmark source and candidate must contain visible text")
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    changed_left = 0
    changed_right = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag != "equal":
            changed_left += left_end - left_start
            changed_right += right_end - right_start
    changed = max(changed_left, changed_right)
    reference_length = min(len(left), len(right))
    if trial_pair:
        minimum = max(4, min(16, (reference_length + 199) // 200))
    else:
        minimum = max(8, min(32, (len(left) + 99) // 100))
    return {
        "normalization": CONTENT_NORMALIZATION,
        "left_content_sha256": _content_sha256(left),
        "right_content_sha256": _content_sha256(right),
        "left_visible_chars": len(left),
        "right_visible_chars": len(right),
        "changed_visible_chars": changed,
        "minimum_changed_chars": minimum,
        "similarity": round(matcher.ratio(), 6),
        "substantive": _content_sha256(left) != _content_sha256(right) and changed >= minimum,
    }


def _candidate_content_evidence(
    case: dict,
    candidate_path: Path,
    benchmark_goal: str,
    authoring_decision: str,
) -> dict:
    source_path = Path(str(case["source"]["path"])).resolve()
    delta = _content_delta(source_path, candidate_path)
    return {
        "schema": "aigc-benchmark-content-decision/v2",
        "benchmark_goal": benchmark_goal,
        "authoring_decision": authoring_decision,
        "normalization": delta["normalization"],
        "source_content_sha256": delta["left_content_sha256"],
        "candidate_content_sha256": delta["right_content_sha256"],
        "source_visible_chars": delta["left_visible_chars"],
        "candidate_visible_chars": delta["right_visible_chars"],
        "changed_visible_chars": delta["changed_visible_chars"],
        "minimum_changed_chars": delta["minimum_changed_chars"],
        "similarity": delta["similarity"],
        "substantive": delta["substantive"],
    }


def _content_evidence_matches(recorded: object, actual: dict) -> bool:
    if not isinstance(recorded, dict):
        return False
    return all(recorded.get(key) == actual.get(key) for key in (
        "schema", "benchmark_goal", "authoring_decision", "normalization",
        "source_content_sha256", "candidate_content_sha256",
        "source_visible_chars", "candidate_visible_chars", "changed_visible_chars",
        "minimum_changed_chars", "similarity", "substantive",
    ))


def _scoring_rule_snapshot() -> list[dict]:
    return [_locked(Path(__file__).resolve().with_name("blind_pair_evaluation.py"))]


def _linked_skill_files(skill_path: Path) -> tuple[Path, ...]:
    """Return direct local files referenced by one SKILL.md.

    Executable scripts remain explicitly listed below. This companion scan
    prevents a directly linked rule/reference from silently falling outside
    the generation and benchmark lock when a Skill evolves.
    """
    root = skill_path.resolve().parent
    text = skill_path.read_text(encoding="utf-8-sig")
    files: list[Path] = []
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", text):
        target = target.strip().strip("<>")
        if not target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        path = (root / target).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file() and path not in files:
            files.append(path)
    return tuple(files)


def _writing_rule_paths() -> tuple[Path, ...]:
    """Return the files that define the current writing route and corpus contract."""
    skills_root = Path(__file__).resolve().parents[3]
    aigc_root = skills_root / "AIGC"
    mcm_root = skills_root / "mcm-cup-standard-write"
    explicit = (
        aigc_root / "aigc-writing-router" / "SKILL.md",
        aigc_root / "aigc-writing-router" / "scripts" / "route_aigc_tools.py",
        aigc_root / "aigc-writing-router" / "references" / "role-contracts.json",
        aigc_root / "aigc-writing-router" / "references" / "content-role-contracts.json",
        aigc_root / "aigc-writing-router" / "references" / "folder-utilization.json",
        aigc_root / "aigc-writing-router" / "references" / "stack-registry.json",
        aigc_root / "aigc-writing-router" / "references" / "workflow-contract.md",
        aigc_root / "aigc-writing-router" / "references" / "teacher-research-readiness.md",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_academic_candidate.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_voice_mode.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_style_rhythm.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_reasoning_scaffold.py",
        aigc_root / "aigc-writing-router" / "scripts" / "compare_style_revision.py",
        aigc_root / "aigc-writing-router" / "scripts" / "run_longform_portfolio.py",
        aigc_root / "aigc-writing-router" / "scripts" / "run_aigc_adapter.py",
        aigc_root / "aigc-writing-router" / "scripts" / "prepare_benchmark_generation.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_benchmark_owner_ledger.py",
        aigc_root / "aigc-writing-router" / "scripts" / "prepare_benchmark_stack.py",
        aigc_root / "aigc-writing-router" / "scripts" / "prepare_draft_improvement_suite.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_style_benchmark_matrix.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_research_draft_readiness.py",
        aigc_root / "aigc-writing-router" / "scripts" / "build_matrix_dev_candidates.py",
        aigc_root / "aigc-writing-router" / "scripts" / "run_matrix_dev_chain.py",
        aigc_root / "aigc-writing-router" / "scripts" / "run_matrix_holdout_chain.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_auxiliary_roles.py",
        aigc_root / "aigc-writing-router" / "scripts" / "audit_longform_auxiliary_roles.py",
        aigc_root / "aigc-writing-router" / "scripts" / "build_style_benchmark_matrix.py",
        aigc_root / "aigc-writing-router" / "scripts" / "prepare_stack_evaluation.py",
        aigc_root / "aigc-writing-router" / "scripts" / "run_stack_evaluation.py",
        aigc_root / "humanize-main" / "ai-check" / "SKILL.md",
        aigc_root / "AI_paper" / "main.py",
        aigc_root / "humanize-academic-chinese" / "SKILL.md",
        aigc_root / "humanize-academic-chinese" / "scripts" / "scan_humanize_chinese.py",
        aigc_root / "humanize-academic-chinese" / "references" / "lexical-signals.json",
        aigc_root / "humanize-academic-chinese" / "references" / "modeling-reasoning-preservation.md",
        aigc_root / "humanize-academic-chinese" / "references" / "scene-routing-policy.json",
        aigc_root / "humanize-academic-chinese" / "references" / "operational-contract.md",
        aigc_root / "humanize-academic-chinese" / "references" / "style-gates.md",
        aigc_root / "humanize-academic-chinese" / "references" / "structural-rewrite-contract.md",
        aigc_root / "humanize-academic-chinese" / "references" / "paired-quality-clearance-contract.md",
        aigc_root / "aigc-writing-router" / "references" / "benchmarks" / "cumcm-v2-dev.json",
        aigc_root / "aigc-writing-router" / "references" / "benchmarks" / "cumcm-v2-holdout.json",
        mcm_root / "SKILL.md",
        mcm_root / "scripts" / "audit_modeling_workbench.py",
        mcm_root / "scripts" / "audit_reasoning_preflight.py",
        mcm_root / "scripts" / "audit_section_authoring_brief.py",
        mcm_root / "scripts" / "audit_section_drafting_packets.py",
        mcm_root / "scripts" / "audit_section_drafting_usage.py",
        mcm_root / "scripts" / "audit_section_judgment_bridges.py",
        mcm_root / "scripts" / "audit_judgment_ledger.py",
        mcm_root / "scripts" / "audit_corpus_overlap.py",
        mcm_root / "scripts" / "audit_lexical_corpus_calibration.py",
        mcm_root / "scripts" / "audit_manuscript.py",
        mcm_root / "scripts" / "audit_content_density.py",
        mcm_root / "scripts" / "audit_competition_length.py",
        mcm_root / "scripts" / "audit_math_semantics.py",
        mcm_root / "scripts" / "audit_result_sync.py",
        mcm_root / "scripts" / "audit_repro_manifest.py",
        mcm_root / "scripts" / "audit_reasoning_review.py",
        mcm_root / "scripts" / "audit_style_retrieval_plan.py",
        mcm_root / "scripts" / "prepare_section_authoring_brief.py",
        mcm_root / "scripts" / "prepare_section_drafting_packets.py",
        mcm_root / "scripts" / "prepare_section_drafting_usage.py",
        mcm_root / "scripts" / "prepare_style_retrieval_plan.py",
        mcm_root / "scripts" / "audit_rewrite_contract.py",
        mcm_root / "references" / "decision-moves.md",
        mcm_root / "references" / "reasoning-before-model.md",
        mcm_root / "references" / "section-language.md",
        mcm_root / "references" / "human-style.md",
        mcm_root / "references" / "natural-reasoning.md",
        mcm_root / "references" / "fulltext-style-stats.json",
        mcm_root / "references" / "fulltext-style-index.jsonl",
        mcm_root / "references" / "style-benchmark-holdout.json",
        skills_root / "deai-academic-writing" / "SKILL.md",
        skills_root / "deai-academic-writing" / "references" / "aigc-tool-orchestration.md",
        skills_root / "deai-academic-writing" / "references" / "diagnostic-matrix.md",
        skills_root / "deai-academic-writing" / "references" / "genre-playbooks.md",
        skills_root / "deai-academic-writing" / "references" / "rewrite-patterns.md",
        skills_root / "deai-academic-writing" / "references" / "rules.md",
        skills_root / "deai-academic-writing" / "references" / "scenario-case-map.md",
        skills_root / "deai-academic-writing" / "references" / "scenario-pattern-map.md",
        skills_root / "deai-academic-writing" / "references" / "scenario-playbook-map.md",
        skills_root / "deai-academic-writing" / "references" / "scenario-router.md",
        skills_root / "deai-academic-writing" / "references" / "scenario-rule-map.md",
        skills_root / "deai-academic-writing" / "references" / "system-prompt-contract.md",
        skills_root / "deai-academic-writing" / "references" / "validation-gates.md",
        skills_root / "deai-modeling-writing" / "SKILL.md",
        skills_root / "deai-modeling-writing" / "references" / "cases.md",
        skills_root / "deai-modeling-writing" / "references" / "diagnostic-matrix.md",
        skills_root / "deai-modeling-writing" / "references" / "playbook.md",
        skills_root / "deai-modeling-writing" / "references" / "rewrite-patterns.md",
        skills_root / "deai-modeling-writing" / "references" / "rules.md",
        skills_root / "deai-modeling-writing" / "references" / "system-prompt-contract.md",
        skills_root / "deai-modeling-writing" / "references" / "validation-gates.md",
        skills_root / "deai-research-writing" / "SKILL.md",
        skills_root / "deai-course-notes" / "SKILL.md",
    )
    linked: list[Path] = []
    for skill_path in (
        aigc_root / "aigc-writing-router" / "SKILL.md",
        aigc_root / "humanize-academic-chinese" / "SKILL.md",
        mcm_root / "SKILL.md",
        skills_root / "deai-academic-writing" / "SKILL.md",
        skills_root / "deai-modeling-writing" / "SKILL.md",
        skills_root / "deai-research-writing" / "SKILL.md",
        skills_root / "deai-course-notes" / "SKILL.md",
    ):
        linked.extend(_linked_skill_files(skill_path))
    return tuple(dict.fromkeys((*explicit, *linked)))


def _mcm_route_rule_owners() -> dict[str, tuple[Path, ...]]:
    skills_root = Path(__file__).resolve().parents[3]
    aigc_root = skills_root / "AIGC"
    return {
        "deai-academic-writing": (skills_root / "deai-academic-writing" / "SKILL.md",),
        "mcm-cup-standard-write": (skills_root / "mcm-cup-standard-write" / "SKILL.md",),
        "deai-modeling-writing": (skills_root / "deai-modeling-writing" / "SKILL.md",),
        "deai-research-writing": (skills_root / "deai-research-writing" / "SKILL.md",),
        "deai-course-notes": (skills_root / "deai-course-notes" / "SKILL.md",),
        "humanize-academic-chinese": (aigc_root / "humanize-academic-chinese" / "SKILL.md",),
        "ai-check": (aigc_root / "humanize-main" / "ai-check" / "SKILL.md",),
        "AI_paper": (
            aigc_root / "AI_paper" / "main.py",
            aigc_root / "aigc-writing-router" / "references" / "folder-utilization.json",
            aigc_root / "aigc-writing-router" / "scripts" / "run_aigc_adapter.py",
        ),
    }


def _validate_mcm_route_rule_coverage(paths: tuple[Path, ...]) -> None:
    owners = _mcm_route_rule_owners()
    providers: set[str] = set()
    for document_type in ("mcm", "modeling", "research", "course-notes"):
        route = select_route(document_type, "rewrite", "tex", "document")
        if route.get("status") != "pass":
            raise ValueError(
                f"{document_type} writing route is invalid: {route.get('findings', [])}"
            )
        providers.update(
            str(stage.get("provider")) for stage in route.get("stages", [])
            if isinstance(stage, dict) and stage.get("provider")
        )
    missing_owners = providers - set(owners)
    if missing_owners:
        raise ValueError(f"MCM route providers lack writing-rule owners: {sorted(missing_owners)}")
    declared = {path.resolve() for path in paths}
    uncovered = {
        provider: [str(path.resolve()) for path in owner_paths if path.resolve() not in declared]
        for provider, owner_paths in owners.items()
        if provider in providers and any(path.resolve() not in declared for path in owner_paths)
    }
    if uncovered:
        raise ValueError(f"MCM route writing-rule files are not snapshotted: {uncovered}")


def _writing_rule_snapshot() -> list[dict]:
    paths = _writing_rule_paths()
    _validate_mcm_route_rule_coverage(paths)
    return [_locked(path) for path in paths]


def _rule_snapshot_validation(value: object) -> tuple[str, list[dict]]:
    """Validate a writing-rule snapshot without mutating the frozen benchmark."""
    if not isinstance(value, list) or not value:
        return "historical-unbound", [{"severity": "warning", "code": "BENCHMARK_WRITING_RULE_SNAPSHOT_MISSING"}]
    expected = {path.resolve() for path in _writing_rule_paths()}
    findings: list[dict] = []
    seen: set[Path] = set()
    for index, record in enumerate(value):
        if not isinstance(record, dict) or not record.get("path"):
            findings.append({
                "severity": "error", "code": "BENCHMARK_WRITING_RULE_SNAPSHOT_INVALID",
                "index": index,
            })
            continue
        path = Path(str(record["path"])).resolve()
        if path in seen or path not in expected:
            findings.append({
                "severity": "error", "code": "BENCHMARK_WRITING_RULE_SNAPSHOT_INVALID",
                "index": index, "path": str(path),
            })
            continue
        seen.add(path)
        if not path.is_file():
            findings.append({
                "severity": "error", "code": "BENCHMARK_WRITING_RULE_FILE_MISSING",
                "path": str(path),
            })
            continue
        actual = sha256_file(path)
        if actual != record.get("sha256"):
            findings.append({
                "severity": "error", "code": "BENCHMARK_WRITING_RULE_FILE_DRIFT",
                "path": str(path), "expected": record.get("sha256"), "actual": actual,
            })
    missing = expected - seen
    if missing:
        findings.append({
            "severity": "error", "code": "BENCHMARK_WRITING_RULE_SNAPSHOT_INCOMPLETE",
            "missing": [str(path) for path in sorted(missing)],
        })
    if any(item["severity"] == "error" for item in findings):
        return "drifted", findings
    return "current-bound", findings


def _rule_snapshot_key(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    rows = []
    for record in value:
        if isinstance(record, dict):
            rows.append((str(Path(str(record.get("path", ""))).resolve()), str(record.get("sha256", ""))))
    return tuple(sorted(rows))


def _check_lock(record: object, findings: list[dict], label: str) -> Path | None:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        _add(findings, "error", "BENCHMARK_LOCK_INVALID", label=label)
        return None
    path = Path(str(record["path"])).resolve()
    if not path.is_file():
        _add(findings, "error", "BENCHMARK_FILE_MISSING", label=label, path=str(path))
        return None
    actual = sha256_file(path)
    if actual != record.get("sha256"):
        _add(
            findings, "error", "BENCHMARK_FILE_DRIFT", label=label,
            expected=record.get("sha256"), actual=actual, path=str(path),
        )
        return None
    return path


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _ensure_new_output(path: Path, predecessor: Path | None = None) -> Path:
    path = path.resolve()
    if predecessor is not None and path == predecessor.resolve():
        raise ValueError("successor manifest must not overwrite its predecessor")
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _successor(payload: dict, predecessor: Path, output: Path, event: str) -> dict:
    output = _ensure_new_output(output, predecessor)
    updated = copy.deepcopy(payload)
    updated["parent_manifest"] = _locked(predecessor)
    updated.setdefault("history", []).append({
        "event": event,
        "predecessor_sha256": sha256_file(predecessor),
    })
    write_json(output, updated)
    return updated


def _case_index(payload: dict) -> dict[str, dict]:
    return {str(item.get("id")): item for item in payload.get("cases", [])}


def _candidate_key(case_id: str, provider: str, trial: int) -> str:
    return f"{case_id}::{provider}::t{trial}"


def _route_accepts(case: dict, provider: str) -> dict:
    scene = case["scene"]
    return select_route(
        str(scene["document_type"]),
        "rewrite",
        str(scene["document_format"]),
        str(scene.get("scope", "document")),
        requested_editor=provider,
    )


def _suite_benchmark_goal(suite: dict) -> tuple[str, str]:
    explicit = str(suite.get("benchmark_goal", "")).strip()
    if explicit:
        if explicit not in BENCHMARK_GOALS:
            raise ValueError(f"benchmark_goal must be one of {sorted(BENCHMARK_GOALS)}")
        return explicit, "explicit"
    raw_cases = suite.get("cases", [])
    award_provenance = bool(raw_cases) and all(
        isinstance(case, dict)
        and isinstance(case.get("provenance"), dict)
        and str(case["provenance"].get("record_id", "")).strip()
        and str(case["provenance"].get("paper", "")).strip()
        for case in raw_cases
    )
    if award_provenance:
        return "preservation", "inferred-award-provenance"
    raise ValueError(
        "benchmark_goal is required for suites without award-paper provenance; "
        "use preservation or improvement"
    )


def init_suite(suite_path: Path, output_dir: Path, registry_path: Path) -> tuple[dict, Path]:
    suite_path = suite_path.resolve()
    suite = _load(suite_path)
    if suite.get("schema") != SUITE_SCHEMA:
        raise ValueError(f"expected schema {SUITE_SCHEMA}")
    suite_id = str(suite.get("suite_id", "")).strip()
    version = str(suite.get("version", "")).strip()
    split = str(suite.get("split", "")).strip()
    if not SAFE_ID_RE.fullmatch(suite_id) or not version or split not in {"dev", "holdout"}:
        raise ValueError("suite_id, version, or split is invalid")
    providers = [str(value).strip() for value in suite.get("providers", [])]
    if not providers or len(set(providers)) != len(providers):
        raise ValueError("providers must be a non-empty unique list")
    benchmark_goal, benchmark_goal_source = _suite_benchmark_goal(suite)
    required_trials = suite.get("required_trials", 3)
    if not isinstance(required_trials, int) or required_trials < 3 or required_trials > 10:
        raise ValueError("required_trials must be an integer from 3 to 10")
    required_generation_evidence = suite.get("required_generation_evidence", [])
    if (
        not isinstance(required_generation_evidence, list)
        or len(set(required_generation_evidence)) != len(required_generation_evidence)
        or set(required_generation_evidence) - GENERATION_EVIDENCE_TYPES
    ):
        raise ValueError("required_generation_evidence is invalid")
    if split == "holdout":
        holdout = suite.get("holdout_policy", {})
        if not isinstance(holdout, dict) or not str(holdout.get("curator", "")).strip() \
                or not str(holdout.get("release_id", "")).strip():
            raise ValueError("holdout suites require holdout_policy.curator and release_id")

    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"benchmark output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    sources_dir = output_dir / "sources"
    sources_dir.mkdir()
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    frozen_cases: list[dict] = []
    for raw_case in suite.get("cases", []):
        case_id = str(raw_case.get("id", "")).strip()
        if not SAFE_ID_RE.fullmatch(case_id) or case_id in seen_ids:
            raise ValueError(f"invalid or duplicate case id: {case_id!r}")
        seen_ids.add(case_id)
        scene = raw_case.get("scene", {})
        document_type = str(scene.get("document_type", ""))
        document_format = str(scene.get("document_format", ""))
        scope = str(scene.get("scope", "document"))
        if document_type not in DOCUMENT_TYPES or document_type == "external-app":
            raise ValueError(f"case {case_id} has an unsupported document type")
        if document_format not in DOCUMENT_FORMATS or scope not in {"document", "local"}:
            raise ValueError(f"case {case_id} has an invalid format or scope")
        source = Path(str(raw_case.get("source", "")))
        if not source.is_absolute():
            source = (suite_path.parent / source).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        text = source.read_text(encoding="utf-8-sig")
        if not text.strip():
            raise ValueError(f"case {case_id} source is empty")
        source_hash = sha256_file(source)
        if source_hash in seen_hashes:
            raise ValueError(f"duplicate source content in suite: {case_id}")
        seen_hashes.add(source_hash)
        challenges = [str(value) for value in raw_case.get("challenge_tags", [])]
        if not challenges or set(challenges) - ALLOWED_CHALLENGES:
            raise ValueError(f"case {case_id} has invalid challenge_tags")
        snapshot = sources_dir / f"{case_id}{source.suffix or '.txt'}"
        shutil.copy2(source, snapshot)
        frozen = {
            "id": case_id,
            "scene": {
                "document_type": document_type,
                "document_format": document_format,
                "scope": scope,
            },
            "challenge_tags": challenges,
            "source": _locked(snapshot),
        }
        for provider in providers:
            route = _route_accepts(frozen, provider)
            if route.get("status") != "pass" or provider not in set(
                route.get("candidate_policy", {}).get("providers", [])
            ):
                raise ValueError(
                    f"provider {provider!r} cannot own case {case_id!r}: "
                    f"{route.get('findings', [])}"
                )
        frozen_cases.append(frozen)
    if not frozen_cases:
        raise ValueError("at least one benchmark case is required")

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "state": "SOURCE_FROZEN",
        "suite": {
            "id": suite_id,
            "version": version,
            "split": split,
            "benchmark_goal": benchmark_goal,
            "benchmark_goal_source": benchmark_goal_source,
            "required_trials": required_trials,
            "providers": providers,
            "required_generation_evidence": required_generation_evidence,
            "holdout_policy": suite.get("holdout_policy") if split == "holdout" else None,
            "definition": _locked(suite_path),
            "writing_rule_snapshot": _writing_rule_snapshot(),
        },
        "run_root": str(output_dir),
        "cases": frozen_cases,
        "candidates": [],
        "blind": None,
        "score": None,
        "parent_manifest": None,
        "history": [{"event": "SOURCE_FROZEN"}],
        "claims": {
            "authorship_or_detector_verdict": False,
            "automatic_winner_selection": False,
        },
    }
    manifest_path = output_dir / "benchmark-source-frozen.json"
    write_json(manifest_path, manifest)
    report = audit_manifest(manifest_path, registry_path)
    if report["status"] != "pass":
        raise ValueError(f"initialized manifest failed audit: {report['findings']}")
    return manifest, manifest_path


def _validate_verification(
    report_path: Path,
    registry: dict,
    provider: str,
    source_sha256: str,
    candidate_sha256: str,
) -> dict:
    report = _load(report_path)
    package = find_package(registry, provider)
    checks = {
        "schema": report.get("schema") == "aigc-adapter-run/v1",
        "package": report.get("package") == package.get("directory"),
        "action": report.get("action") == "verify-candidate",
        "status": report.get("status") == "pass",
        "source": report.get("source", {}).get("sha256") == source_sha256,
        "candidate": report.get("candidate", {}).get("sha256") == candidate_sha256,
        "human_review": report.get("human_review_required") is True,
    }
    failed = [key for key, value in checks.items() if not value]
    if failed:
        raise ValueError(f"candidate verification contract failed: {failed}")
    return report


def _resolve_locked_path(base: Path, record: object, label: str) -> Path:
    if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
        raise ValueError(f"{label} lock is missing or invalid")
    path = Path(str(record["path"]))
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or sha256_file(path) != str(record["sha256"]):
        raise ValueError(f"{label} lock drifted")
    return path


def _validate_stack_generation(
    record: object,
    provider: str,
    source_sha256: str,
    candidate_sha256: str,
    registry_path: Path,
) -> dict:
    if not isinstance(record, dict):
        raise ValueError("stack evaluation evidence is missing")
    report_path = _resolve_locked_path(Path.cwd(), record.get("report"), "stack report")
    manifest_path = _resolve_locked_path(Path.cwd(), record.get("manifest"), "stack manifest")
    report = _load(report_path)
    manifest = _load(manifest_path)
    if report.get("schema") != "aigc-stack-evaluation-report/v1":
        raise ValueError("stack report schema mismatch")
    if manifest.get("schema") != "aigc-stack-evaluation/v1":
        raise ValueError("stack manifest schema mismatch")
    report_manifest = _resolve_locked_path(report_path.parent, report.get("manifest"), "stack report manifest")
    if report_manifest != manifest_path:
        raise ValueError("stack report and generation envelope reference different manifests")
    source_path = _resolve_locked_path(manifest_path.parent, manifest.get("source"), "stack source")
    candidate_path = _resolve_locked_path(manifest_path.parent, manifest.get("candidate"), "stack candidate")
    if sha256_file(source_path) != source_sha256 or sha256_file(candidate_path) != candidate_sha256:
        raise ValueError("stack source or candidate hash mismatch")
    if manifest.get("candidate", {}).get("provider") != provider:
        raise ValueError("stack candidate provider mismatch")
    fresh = evaluate_stack(manifest_path, registry_path)
    if (
        fresh.get("status") not in {"MECHANICAL_PASS_HUMAN_PENDING", "HUMAN_EVALUATED_PASS"}
        or fresh.get("errors") != 0
        or fresh.get("candidate", {}).get("provider") != provider
        or fresh.get("required_stage_providers") != fresh.get("covered_stage_providers")
        or report.get("status") != fresh.get("status")
        or report.get("required_stage_providers") != fresh.get("required_stage_providers")
        or record.get("document_type") != fresh.get("scene", {}).get("document_type")
        or record.get("required_stage_providers") != fresh.get("required_stage_providers")
    ):
        raise ValueError("stack evaluation is incomplete, stale, or inconsistent")
    return fresh


def _validate_generation(
    report_path: Path,
    provider: str,
    source_sha256: str,
    candidate_sha256: str,
    allow_legacy: bool = False,
    require_stack_evaluation: bool = False,
    registry_path: Path | None = None,
) -> tuple[dict, str, str | None]:
    report = _load(report_path)
    if report.get("schema") != GENERATION_SCHEMA:
        raise ValueError("generation evidence schema mismatch")
    if report.get("provider") != provider or report.get("status") != "pass":
        raise ValueError("generation evidence provider or status is invalid")
    if report.get("authoring_actor") not in {"model", "human", "external_tool"}:
        raise ValueError("generation authoring_actor is missing or invalid")
    authoring_decision = report.get("authoring_decision")
    if authoring_decision not in AUTHORING_DECISIONS:
        if not (allow_legacy and authoring_decision is None):
            raise ValueError(
                f"generation authoring_decision must be one of {sorted(AUTHORING_DECISIONS)}"
            )
    claims = report.get("claims")
    if (
        not isinstance(claims, dict)
        or claims.get("human_authorship_proven") is not False
        or claims.get("native_generation_proven") is not False
        or claims.get("validation_executed") is not True
    ):
        raise ValueError("generation evidence must not claim human authorship")
    if report.get("source", {}).get("sha256") != source_sha256:
        raise ValueError("generation source hash mismatch")
    if report.get("candidate", {}).get("sha256") != candidate_sha256:
        raise ValueError("generation candidate hash mismatch")
    execution = report.get("execution")
    if not isinstance(execution, dict) or execution.get("mode") not in {
        "native_executed", "model_authored_native_validated",
    }:
        raise ValueError("generation mode is missing or invalid")
    if execution.get("mode") == "model_authored_native_validated" and report.get("authoring_actor") != "model":
        raise ValueError("model_authored_native_validated requires authoring_actor=model")
    run_id = str(execution.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("generation run_id is missing")
    native = report.get("native_report")
    if not isinstance(native, dict) or not native.get("path") or not native.get("sha256"):
        raise ValueError("native generation report is missing")
    native_path = Path(str(native["path"])).resolve()
    if not native_path.is_file() or sha256_file(native_path) != str(native["sha256"]):
        raise ValueError("native generation report drifted")
    native_payload = _load(native_path)
    successful = (
        native_payload.get("status") == "pass"
        or native_payload.get("candidate_assembly_status") == "PASS"
        or native_payload.get("mechanical_validation_status") == "PASS"
    )
    if not successful:
        raise ValueError("native generation report does not declare success")
    stack_record = report.get("stack_evaluation")
    if require_stack_evaluation or stack_record is not None:
        effective_registry = (
            registry_path.resolve() if registry_path is not None
            else Path(__file__).resolve().parents[1] / "references" / "stack-registry.json"
        )
        _validate_stack_generation(
            stack_record, provider, source_sha256, candidate_sha256, effective_registry,
        )
    if require_stack_evaluation and execution.get("role_chain_bound") is not True:
        raise ValueError("generation evidence does not declare a bound role chain")
    rule_snapshot = report.get("writing_rule_snapshot")
    if rule_snapshot is not None:
        freshness, rule_findings = _rule_snapshot_validation(rule_snapshot)
        if freshness != "current-bound":
            raise ValueError(f"generation writing-rule snapshot is {freshness}: {rule_findings}")
    return report, run_id, authoring_decision


def _snapshot_stack_bundle(
    generation: dict,
    source_snapshot: Path,
    candidate_snapshot: Path,
    verification_snapshot: Path,
    evidence_dir: Path,
    safe_provider: str,
    trial: int,
    registry_path: Path,
) -> dict:
    stack = generation.get("stack_evaluation")
    if not isinstance(stack, dict):
        return generation
    original_report = _resolve_locked_path(Path.cwd(), stack.get("report"), "stack report")
    original_manifest = _resolve_locked_path(Path.cwd(), stack.get("manifest"), "stack manifest")
    manifest = _load(original_manifest)
    stack_dir = evidence_dir / f"{safe_provider}-t{trial}-stack"
    if stack_dir.exists():
        raise FileExistsError(stack_dir)
    stack_dir.mkdir(parents=True)
    artifacts_dir = stack_dir / "artifacts"
    artifacts_dir.mkdir()

    stage_locks: list[dict] = []
    for stage_index, stage_record in enumerate(manifest.get("stage_evidence", []), start=1):
        stage_path = _resolve_locked_path(
            original_manifest.parent, stage_record, f"stack stage {stage_index}",
        )
        stage = _load(stage_path)
        artifact_locks: list[dict] = []
        for artifact_index, artifact_record in enumerate(stage.get("artifacts", []), start=1):
            artifact_path = _resolve_locked_path(
                stage_path.parent, artifact_record,
                f"stack stage {stage_index} artifact {artifact_index}",
            )
            target = artifacts_dir / (
                f"s{stage_index:02d}-a{artifact_index:02d}{artifact_path.suffix or '.bin'}"
            )
            shutil.copy2(artifact_path, target)
            artifact_locks.append(_locked(target))
        stage["artifacts"] = artifact_locks
        stage_snapshot = stack_dir / f"stage-{stage_index:02d}.json"
        write_json(stage_snapshot, stage)
        stage_locks.append(_locked(stage_snapshot))

    manifest["source"] = _locked(source_snapshot)
    manifest["candidate"] = {
        **_locked(candidate_snapshot),
        "id": manifest.get("candidate", {}).get("id"),
        "provider": manifest.get("candidate", {}).get("provider"),
    }
    manifest["candidate_verification"] = _locked(verification_snapshot)
    manifest["stage_evidence"] = stage_locks
    if manifest.get("blind_score") is not None:
        blind_path = _resolve_locked_path(
            original_manifest.parent, manifest.get("blind_score"), "stack blind score",
        )
        blind_target = stack_dir / f"blind-score{blind_path.suffix or '.json'}"
        shutil.copy2(blind_path, blind_target)
        manifest["blind_score"] = _locked(blind_target)
    manifest_snapshot = stack_dir / "stack-manifest.json"
    write_json(manifest_snapshot, manifest)
    fresh_report = evaluate_stack(manifest_snapshot, registry_path)
    if fresh_report.get("status") == "FAIL" or fresh_report.get("errors") != 0:
        raise ValueError(f"snapshotted stack bundle failed evaluation: {fresh_report.get('findings', [])}")
    report_snapshot = stack_dir / "stack-report.json"
    write_json(report_snapshot, fresh_report)
    updated = copy.deepcopy(generation)
    updated["stack_evaluation"] = {
        "report": _locked(report_snapshot),
        "manifest": _locked(manifest_snapshot),
        "document_type": fresh_report.get("scene", {}).get("document_type"),
        "required_stage_providers": fresh_report.get("required_stage_providers", []),
    }
    return updated


def register_candidate(
    manifest_path: Path,
    case_id: str,
    provider: str,
    trial: int,
    candidate_path: Path,
    verification_path: Path,
    output: Path,
    registry_path: Path,
    generation_path: Path,
) -> tuple[dict, Path]:
    manifest_path = manifest_path.resolve()
    payload = _load(manifest_path)
    report = audit_manifest(manifest_path, registry_path)
    if report["status"] != "pass":
        raise ValueError(f"manifest audit failed: {report['findings']}")
    if payload.get("state") not in {"SOURCE_FROZEN", "CANDIDATES_READY"}:
        raise ValueError("candidate registration is closed after blind preparation")
    cases = _case_index(payload)
    if case_id not in cases:
        raise ValueError(f"unknown case: {case_id}")
    if provider not in payload["suite"]["providers"]:
        raise ValueError(f"provider is not declared by the suite: {provider}")
    required_trials = int(payload["suite"]["required_trials"])
    if trial < 1 or trial > required_trials:
        raise ValueError(f"trial must be from 1 to {required_trials}")
    key = _candidate_key(case_id, provider, trial)
    if any(item.get("id") == key for item in payload.get("candidates", [])):
        raise ValueError(f"candidate trial already registered: {key}")
    route = _route_accepts(cases[case_id], provider)
    if route.get("status") != "pass" or provider not in set(
        route.get("candidate_policy", {}).get("providers", [])
    ):
        raise ValueError(f"provider no longer owns this scene: {route.get('findings', [])}")

    candidate_path = candidate_path.resolve()
    verification_path = verification_path.resolve()
    generation_path = generation_path.resolve()
    if not candidate_path.is_file() or not verification_path.is_file() or not generation_path.is_file():
        missing = next(path for path in (candidate_path, verification_path, generation_path) if not path.is_file())
        raise FileNotFoundError(missing)
    source_sha = str(cases[case_id]["source"]["sha256"])
    candidate_sha = sha256_file(candidate_path)
    registry = read_registry(registry_path)
    _validate_verification(
        verification_path, registry, provider, source_sha, candidate_sha,
    )
    generation, run_id, authoring_decision = _validate_generation(
        generation_path, provider, source_sha, candidate_sha,
        require_stack_evaluation=(
            "stack_evaluation"
            in payload.get("suite", {}).get("required_generation_evidence", [])
        ),
        registry_path=registry_path,
    )
    if authoring_decision is None:
        raise ValueError("current benchmark generation must declare authoring_decision")
    benchmark_goal = str(payload.get("suite", {}).get("benchmark_goal", ""))
    if benchmark_goal not in BENCHMARK_GOALS:
        raise ValueError("manifest benchmark_goal is missing or invalid")
    content_evidence = _candidate_content_evidence(
        cases[case_id], candidate_path, benchmark_goal, authoring_decision,
    )
    normalized_equal = (
        content_evidence["source_content_sha256"]
        == content_evidence["candidate_content_sha256"]
    )
    if benchmark_goal == "improvement" and authoring_decision != "REWRITE":
        raise ValueError("improvement benchmarks require authoring_decision=REWRITE")
    if authoring_decision == "NO_CHANGE" and not normalized_equal:
        raise ValueError("NO_CHANGE decision does not match the normalized candidate content")
    if authoring_decision == "REWRITE" and not content_evidence["substantive"]:
        raise ValueError(
            "REWRITE candidate lacks a substantive content change after Unicode and whitespace "
            f"normalization: changed={content_evidence['changed_visible_chars']} "
            f"required={content_evidence['minimum_changed_chars']}"
        )
    for existing in payload.get("candidates", []):
        if (
            authoring_decision != "REWRITE"
            or existing.get("authoring_decision") != "REWRITE"
            or existing.get("case_id") != case_id
            or existing.get("provider") != provider
        ):
            continue
        existing_path = Path(str(existing.get("candidate", {}).get("path", ""))).resolve()
        if not existing_path.is_file():
            continue
        trial_delta = _content_delta(existing_path, candidate_path, trial_pair=True)
        if not trial_delta["substantive"]:
            raise ValueError(
                "REWRITE trial is a normalized duplicate or near-duplicate of "
                f"{existing.get('id')}: changed={trial_delta['changed_visible_chars']} "
                f"required={trial_delta['minimum_changed_chars']}"
            )
    suite_snapshot = payload.get("suite", {}).get("writing_rule_snapshot")
    if suite_snapshot and _rule_snapshot_key(suite_snapshot) != _rule_snapshot_key(
        generation.get("writing_rule_snapshot")
    ):
        raise ValueError("generation writing-rule snapshot does not match suite snapshot")
    if any(item.get("generation", {}).get("run_id") == run_id for item in payload.get("candidates", [])):
        raise ValueError(f"generation run_id already registered: {run_id}")
    run_root = Path(str(payload["run_root"])).resolve()
    candidate_dir = run_root / "candidates" / case_id
    evidence_dir = run_root / "evidence" / case_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_provider = re.sub(r"[^A-Za-z0-9._-]+", "-", provider)
    snapshot = candidate_dir / f"{safe_provider}-t{trial}{candidate_path.suffix or '.txt'}"
    verification_snapshot = evidence_dir / f"{safe_provider}-t{trial}-verification.json"
    generation_snapshot = evidence_dir / f"{safe_provider}-t{trial}-generation.json"
    native_path = Path(str(generation["native_report"]["path"])).resolve()
    native_snapshot = evidence_dir / f"{safe_provider}-t{trial}-native-report.json"
    if snapshot.exists() or verification_snapshot.exists() or generation_snapshot.exists():
        raise FileExistsError(next(path for path in (snapshot, verification_snapshot, generation_snapshot) if path.exists()))
    shutil.copy2(candidate_path, snapshot)
    shutil.copy2(verification_path, verification_snapshot)
    shutil.copy2(native_path, native_snapshot)
    generation_snapshot_payload = copy.deepcopy(generation)
    generation_snapshot_payload["native_report"] = {
        "path": str(native_snapshot.resolve()),
        "sha256": sha256_file(native_snapshot),
    }
    generation_snapshot_payload = _snapshot_stack_bundle(
        generation_snapshot_payload,
        Path(str(cases[case_id]["source"]["path"])).resolve(),
        snapshot,
        verification_snapshot,
        evidence_dir,
        safe_provider,
        trial,
        registry_path,
    )
    write_json(generation_snapshot, generation_snapshot_payload)

    updated = copy.deepcopy(payload)
    updated["state"] = "CANDIDATES_READY"
    updated.setdefault("candidates", []).append({
        "id": key,
        "case_id": case_id,
        "provider": provider,
        "trial": trial,
        "authoring_decision": authoring_decision,
        "candidate": _locked(snapshot),
        "content_evidence": content_evidence,
        "verification": _locked(verification_snapshot),
        "generation": {
            **_locked(generation_snapshot),
            "run_id": run_id,
            "authoring_decision": authoring_decision,
        },
    })
    return _successor(updated, manifest_path, output, f"REGISTER:{key}"), output.resolve()


def _required_candidate_keys(payload: dict) -> set[str]:
    return {
        _candidate_key(str(case["id"]), str(provider), trial)
        for case in payload.get("cases", [])
        for provider in payload.get("suite", {}).get("providers", [])
        for trial in range(1, int(payload.get("suite", {}).get("required_trials", 0)) + 1)
    }


def prepare_benchmark(
    manifest_path: Path,
    seed: int,
    output: Path,
    registry_path: Path,
) -> tuple[dict, Path]:
    manifest_path = manifest_path.resolve()
    payload = _load(manifest_path)
    report = audit_manifest(manifest_path, registry_path)
    if report["status"] != "pass":
        raise ValueError(f"manifest audit failed: {report['findings']}")
    if payload.get("state") != "CANDIDATES_READY":
        raise ValueError("benchmark must be CANDIDATES_READY")
    actual = {str(item.get("id")) for item in payload.get("candidates", [])}
    required = _required_candidate_keys(payload)
    if actual != required:
        raise ValueError(f"candidate matrix is incomplete: missing={sorted(required - actual)}")
    run_root = Path(str(payload["run_root"])).resolve()
    blind_dir = run_root / "blind"
    if blind_dir.exists():
        raise FileExistsError(blind_dir)
    blind_dir.mkdir(parents=True)
    cases = _case_index(payload)
    pairs = []
    pair_map: dict[str, dict] = {}
    for index, candidate in enumerate(sorted(payload["candidates"], key=lambda item: item["id"]), start=1):
        pair_id = f"P{index:04d}"
        case = cases[str(candidate["case_id"])]
        source_path = Path(str(case["source"]["path"]))
        candidate_path = Path(str(candidate["candidate"]["path"]))
        source_id = f"{case['id']}::source"
        pairs.append({
            "id": pair_id,
            "variants": [
                {"id": source_id, "text": source_path.read_text(encoding="utf-8-sig")},
                {"id": candidate["id"], "text": candidate_path.read_text(encoding="utf-8-sig")},
            ],
        })
        pair_map[pair_id] = {
            "case_id": case["id"],
            "scene": case["scene"]["document_type"],
            "challenge_tags": case["challenge_tags"],
            "provider": candidate["provider"],
            "trial": candidate["trial"],
            "source_id": source_id,
            "candidate_id": candidate["id"],
        }
    pairs_path = blind_dir / "pairs.json"
    write_json(pairs_path, {"schema": "aigc-blind-pairs/v1", "pairs": pairs})
    prepared = prepare_blind(pairs_path, blind_dir, seed)
    pair_map_path = blind_dir / "pair-map.json"
    write_json(pair_map_path, {"schema": "aigc-style-pair-map/v1", "pairs": pair_map})

    updated = copy.deepcopy(payload)
    updated["state"] = "BLIND_READY"
    updated["blind"] = {
        "seed": seed,
        "pairs": _locked(pairs_path),
        "packet": _locked(Path(prepared["packet"])),
        "key": _locked(Path(prepared["key"])),
        "ratings_template": _locked(Path(prepared["ratings_template"])),
        "review_page": _locked(Path(prepared["review_page"])),
        "review_bundle": _locked(Path(prepared["review_bundle"])),
        "scoring_protocol": SCORING_PROTOCOL,
        "scoring_rules": _scoring_rule_snapshot(),
        "scoring_orchestrator": _locked(Path(__file__).resolve()),
        "pair_map": _locked(pair_map_path),
        "rater_instruction": (
            "Distribute review_page or packet plus a clean ratings copy; keep manifest, key and pair map hidden."
        ),
    }
    return _successor(updated, manifest_path, output, "BLIND_READY"), output.resolve()


def package_review(
    manifest_path: Path,
    output: Path,
    registry_path: Path,
    refresh: bool = False,
) -> tuple[dict, Path]:
    """Add a provenance-free review page to a legacy audited blind manifest."""
    manifest_path = manifest_path.resolve()
    payload = _load(manifest_path)
    report = audit_manifest(
        manifest_path,
        registry_path,
        allow_missing_review=True,
        ignore_existing_review=refresh,
        allow_legacy_protocol=True,
    )
    if report["status"] != "pass":
        raise ValueError(f"manifest audit failed: {report['findings']}")
    if payload.get("state") not in {"BLIND_READY", *SCORED_STATES}:
        raise ValueError("review packaging requires a blind or scored benchmark")
    blind = payload.get("blind", {})
    if (blind.get("review_page") or blind.get("review_bundle")) and not refresh:
        raise ValueError("review package is already locked in the manifest")
    packet_path = Path(str(blind["packet"]["path"])).resolve()
    ratings_path = Path(str(blind["ratings_template"]["path"])).resolve()
    blind_dir = packet_path.parent
    if refresh:
        version = 2
        while (blind_dir / f"review-v{version}.html").exists() or (blind_dir / f"review-bundle-v{version}.json").exists():
            version += 1
        review_path = blind_dir / f"review-v{version}.html"
        bundle_path = blind_dir / f"review-bundle-v{version}.json"
    else:
        review_path = blind_dir / "review.html"
        bundle_path = blind_dir / "review-bundle.json"
    rendered = render_review(packet_path, review_path, ratings_path, bundle_path)
    updated = copy.deepcopy(payload)
    updated["blind"]["review_page"] = _locked(Path(rendered["review_page"]))
    updated["blind"]["review_bundle"] = _locked(Path(rendered["bundle"]))
    updated["blind"]["scoring_protocol"] = SCORING_PROTOCOL
    updated["blind"]["scoring_rules"] = _scoring_rule_snapshot()
    updated["blind"]["scoring_orchestrator"] = _locked(Path(__file__).resolve())
    updated["blind"]["rater_instruction"] = (
        "Distribute review_page or packet plus a clean ratings copy; keep manifest, key and pair map hidden."
    )
    event = "REVIEW_REFRESHED" if refresh else "REVIEW_PACKAGED"
    return _successor(updated, manifest_path, output, event), output.resolve()


def _outcome(counts: dict, candidate_id: str, source_id: str) -> str:
    candidate_votes = int(counts.get(candidate_id, 0))
    source_votes = int(counts.get(source_id, 0))
    if candidate_votes > source_votes:
        return "win"
    if candidate_votes < source_votes:
        return "loss"
    return "tie"


def _validate_formal_merge(
    merge_report_path: Path,
    ratings_path: Path,
    blind: dict,
) -> dict:
    merge_report_path = merge_report_path.resolve()
    ratings_path = ratings_path.resolve()
    report = audit_merge_report(merge_report_path)
    if report.get("status") != "pass":
        raise ValueError(f"ratings merge audit failed: {report.get('findings', [])}")
    payload = _load(merge_report_path)
    output = payload.get("output", {})
    packet = payload.get("packet", {})
    if (
        Path(str(output.get("path", ""))).resolve() != ratings_path
        or output.get("sha256") != sha256_file(ratings_path)
    ):
        raise ValueError("ratings merge report does not bind the submitted merged CSV")
    if (
        Path(str(packet.get("path", ""))).resolve() != Path(str(blind["packet"]["path"])).resolve()
        or packet.get("sha256") != blind["packet"]["sha256"]
    ):
        raise ValueError("ratings merge report does not bind the manifest packet")
    if int(payload.get("declared_human_files", 0)) < 2:
        raise ValueError("formal benchmark requires at least two separately hashed human rating files")
    return payload


def score_benchmark(
    manifest_path: Path,
    ratings_path: Path,
    ratings_merge_path: Path,
    output: Path,
    registry_path: Path,
) -> tuple[dict, Path]:
    manifest_path = manifest_path.resolve()
    payload = _load(manifest_path)
    report = audit_manifest(manifest_path, registry_path)
    if report["status"] != "pass":
        raise ValueError(f"manifest audit failed: {report['findings']}")
    if report.get("rule_freshness") != "current-bound":
        raise ValueError(
            "formal benchmark scoring requires a current-bound writing-rule snapshot; "
            f"got {report.get('rule_freshness', 'historical-unbound')}"
        )
    if payload.get("state") != "BLIND_READY":
        raise ValueError("benchmark must be BLIND_READY")
    blind = payload["blind"]
    _validate_formal_merge(ratings_merge_path, ratings_path, blind)
    blind_report = score_blind(
        Path(blind["key"]["path"]), ratings_path.resolve(), ratings_merge_path.resolve(),
    )
    if (
        blind_report.get("status") != "pass"
        or blind_report.get("scoring_protocol") != SCORING_PROTOCOL
        or blind_report.get("warnings") != 0
        or blind_report.get("formal_human_ready") is not True
    ):
        raise ValueError(
            "formal benchmark requires scoring protocol v2, an audited merge report, and majority-backed human ratings"
        )
    run_root = Path(str(payload["run_root"])).resolve()
    score_path = run_root / "blind" / "score.json"
    failure_path = run_root / "blind" / "failure-capsules.json"
    if score_path.exists() or failure_path.exists():
        raise FileExistsError(score_path if score_path.exists() else failure_path)
    write_json(score_path, blind_report)
    pair_map = _load(Path(blind["pair_map"]["path"]))["pairs"]
    notes_by_pair: dict[str, list[dict]] = defaultdict(list)
    for note in blind_report.get("rater_notes", []):
        notes_by_pair[str(note.get("pair_id"))].append(note)
    totals: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {dimension: {"win": 0, "loss": 0, "tie": 0} for dimension in DIMENSIONS}
    )
    scene_totals: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {dimension: {"win": 0, "loss": 0, "tie": 0} for dimension in DIMENSIONS}
    )
    case_provider_totals: dict[tuple[str, str], dict[str, dict[str, int]]] = defaultdict(
        lambda: {dimension: {"win": 0, "loss": 0, "tie": 0} for dimension in DIMENSIONS}
    )
    failures: list[dict] = []
    pair_results: list[dict] = []
    for pair_id, meta in pair_map.items():
        dimension_results = {}
        for dimension in DIMENSIONS:
            counts = blind_report["per_pair_counts"][pair_id][dimension]
            outcome = _outcome(counts, meta["candidate_id"], meta["source_id"])
            dimension_results[dimension] = {"outcome": outcome, "counts": counts}
            totals[meta["provider"]][dimension][outcome] += 1
            scene_totals[meta["scene"]][dimension][outcome] += 1
            case_provider_totals[(meta["case_id"], meta["provider"])][dimension][outcome] += 1
            is_failure = outcome == "loss" or (
                outcome == "tie" and dimension != "semantic_fidelity"
            )
            if is_failure:
                failures.append({
                    "pair_id": pair_id,
                    "case_id": meta["case_id"],
                    "split": payload["suite"]["split"],
                    "scene": meta["scene"],
                    "provider": meta["provider"],
                    "trial": meta["trial"],
                    "dimension": dimension,
                    "outcome": outcome,
                    "severity": "error" if dimension == "semantic_fidelity" else (
                        "warning" if outcome == "loss" else "note"
                    ),
                    "challenge_tags": meta["challenge_tags"],
                    "rater_notes": notes_by_pair.get(pair_id, []),
                    "recommended_action": ACTION_BY_DIMENSION[dimension],
                })
        pair_results.append({"pair_id": pair_id, **meta, "dimensions": dimension_results})
    failures_payload = {
        "schema": FAILURE_SCHEMA,
        "suite_id": payload["suite"]["id"],
        "version": payload["suite"]["version"],
        "split": payload["suite"]["split"],
        "failures": failures,
        "rule": "Use dev failures to revise prompts; preserve holdout failures as release evidence.",
    }
    write_json(failure_path, failures_payload)
    consistency = []
    for (case_id, provider), dimensions in sorted(case_provider_totals.items()):
        dimension_summary = {}
        for dimension, outcomes in dimensions.items():
            trials = sum(outcomes.values())
            dimension_summary[dimension] = {
                **outcomes,
                "trials": trials,
                "win_rate": round(outcomes["win"] / trials, 4) if trials else 0.0,
            }
        consistency.append({
            "case_id": case_id,
            "provider": provider,
            "dimensions": dimension_summary,
        })
    split = payload["suite"]["split"]
    updated = copy.deepcopy(payload)
    updated["state"] = "SCORED_HOLDOUT_SEALED" if split == "holdout" else "SCORED_DEV"
    updated["score"] = {
        "blind_score": _locked(score_path),
        "ratings": _locked(ratings_path.resolve()),
        "ratings_merge": _locked(ratings_merge_path.resolve()),
        "failure_capsules": _locked(failure_path),
        "summary": {
            "by_provider": json.loads(json.dumps(totals)),
            "by_scene": json.loads(json.dumps(scene_totals)),
            "consistency": consistency,
            "pair_results": pair_results,
            "failure_count": len(failures),
        },
        "interpretation": (
            "Outcomes are human preferences on these frozen passages only; no authorship, "
            "detector, or universal quality claim is made."
        ),
    }
    event = "SCORED_HOLDOUT_SEALED" if split == "holdout" else "SCORED_DEV"
    return _successor(updated, manifest_path, output, event), output.resolve()


def probe_benchmark(
    manifest_path: Path,
    ratings_path: Path,
    output: Path,
    registry_path: Path,
) -> dict:
    manifest_path = manifest_path.resolve()
    output = _ensure_new_output(output)
    payload = _load(manifest_path)
    report = audit_manifest(manifest_path, registry_path)
    if report["status"] != "pass" or payload.get("state") != "BLIND_READY":
        raise ValueError("model probe requires an audited BLIND_READY manifest")
    blind_report = score_blind(Path(payload["blind"]["key"]["path"]), ratings_path.resolve())
    if blind_report.get("status") != "pass":
        raise ValueError("model probe ratings are invalid")
    if any(value for value in blind_report.get("human_coverage", {}).values()):
        raise ValueError("model probe must not contain human ratings")
    if any(value for value in blind_report.get("unspecified_coverage", {}).values()):
        raise ValueError("model probe must declare rater_kind=model on every row")
    if not blind_report.get("model_coverage") or not all(
        value >= 1 for value in blind_report["model_coverage"].values()
    ):
        raise ValueError("model probe requires at least one model rating per pair")
    probe = {
        "schema": "aigc-style-benchmark-model-probe/v1",
        "status": "pass",
        "suite_id": payload["suite"]["id"],
        "split": payload["suite"]["split"],
        "manifest": _locked(manifest_path),
        "ratings": _locked(ratings_path.resolve()),
        "formal_human_ready": False,
        "evaluation_level": "MODEL_PROBE_ONLY",
        "human_coverage": blind_report["human_coverage"],
        "model_coverage": blind_report["model_coverage"],
        "score": blind_report,
        "claims": {
            "may_select_candidate": False,
            "may_advance_manifest_state": False,
            "human_quality_clearance": False,
        },
    }
    write_json(output, probe)
    return probe


def audit_manifest(
    manifest_path: Path,
    registry_path: Path,
    allow_missing_review: bool = False,
    ignore_existing_review: bool = False,
    allow_legacy_protocol: bool = False,
) -> dict:
    manifest_path = manifest_path.resolve()
    findings: list[dict] = []
    try:
        payload = _load(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "aigc-style-benchmark-audit/v1", "status": "fail",
            "errors": 1, "warnings": 0,
            "findings": [{"severity": "error", "code": "BENCHMARK_MANIFEST_INVALID", "error": str(exc)}],
        }
    if payload.get("schema") != MANIFEST_SCHEMA:
        _add(findings, "error", "BENCHMARK_SCHEMA_MISMATCH")
    state = str(payload.get("state", ""))
    if state not in STATES:
        _add(findings, "error", "BENCHMARK_STATE_INVALID", state=state)
    suite = payload.get("suite", {})
    split = str(suite.get("split", "")) if isinstance(suite, dict) else ""
    if split not in {"dev", "holdout"}:
        _add(findings, "error", "BENCHMARK_SPLIT_INVALID", split=split)
    if state == "SCORED_HOLDOUT_SEALED" and split != "holdout":
        _add(findings, "error", "BENCHMARK_HOLDOUT_STATE_MISMATCH")
    if state == "SCORED_DEV" and split != "dev":
        _add(findings, "error", "BENCHMARK_DEV_STATE_MISMATCH")
    _check_lock(suite.get("definition") if isinstance(suite, dict) else None, findings, "suite.definition")
    rule_freshness, rule_findings = _rule_snapshot_validation(
        suite.get("writing_rule_snapshot") if isinstance(suite, dict) else None,
    )
    findings.extend(rule_findings)
    benchmark_goal = str(suite.get("benchmark_goal", "")) if isinstance(suite, dict) else ""
    if benchmark_goal not in BENCHMARK_GOALS:
        severity = "warning" if rule_freshness == "historical-unbound" else "error"
        _add(findings, severity, "BENCHMARK_GOAL_MISSING_OR_INVALID", value=benchmark_goal)
        if rule_freshness == "historical-unbound":
            benchmark_goal = "preservation"
    required_generation_evidence = (
        suite.get("required_generation_evidence", []) if isinstance(suite, dict) else []
    )
    if (
        not isinstance(required_generation_evidence, list)
        or len(set(required_generation_evidence)) != len(required_generation_evidence)
        or set(required_generation_evidence) - GENERATION_EVIDENCE_TYPES
    ):
        _add(findings, "error", "BENCHMARK_REQUIRED_GENERATION_EVIDENCE_INVALID")
        required_generation_evidence = []
    if rule_freshness == "current-bound":
        for index, record in enumerate(suite.get("writing_rule_snapshot", [])):
            _check_lock(record, findings, f"suite.writing_rule_snapshot[{index}]")
    case_ids: set[str] = set()
    for index, case in enumerate(payload.get("cases", [])):
        case_id = str(case.get("id", ""))
        if case_id in case_ids:
            _add(findings, "error", "BENCHMARK_CASE_DUPLICATE", case_id=case_id)
        case_ids.add(case_id)
        _check_lock(case.get("source"), findings, f"cases[{index}].source")
    registry = read_registry(registry_path)
    candidate_ids: set[str] = set()
    trial_content_groups: dict[tuple[str, str], list[tuple[str, Path]]] = defaultdict(list)
    for index, candidate in enumerate(payload.get("candidates", [])):
        candidate_id = str(candidate.get("id", ""))
        if candidate_id in candidate_ids:
            _add(findings, "error", "BENCHMARK_CANDIDATE_DUPLICATE", candidate_id=candidate_id)
        candidate_ids.add(candidate_id)
        candidate_path = _check_lock(candidate.get("candidate"), findings, f"candidates[{index}].candidate")
        verification_path = _check_lock(
            candidate.get("verification"), findings, f"candidates[{index}].verification",
        )
        generation_path = _check_lock(
            candidate.get("generation"), findings, f"candidates[{index}].generation",
        )
        case = _case_index(payload).get(str(candidate.get("case_id")))
        if case is None:
            _add(findings, "error", "BENCHMARK_CANDIDATE_CASE_UNKNOWN", candidate_id=candidate_id)
        elif candidate_path is not None and verification_path is not None and generation_path is not None:
            try:
                generation_payload = _load(generation_path)
                authoring_decision = generation_payload.get("authoring_decision")
                if authoring_decision not in AUTHORING_DECISIONS:
                    severity = "warning" if rule_freshness == "historical-unbound" else "error"
                    _add(
                        findings, severity, "BENCHMARK_AUTHORING_DECISION_MISSING_OR_INVALID",
                        candidate_id=candidate_id, value=authoring_decision,
                    )
                effective_goal = benchmark_goal if benchmark_goal in BENCHMARK_GOALS else "improvement"
                effective_decision = (
                    str(authoring_decision)
                    if authoring_decision in AUTHORING_DECISIONS
                    else "REWRITE"
                )
                actual_content = _candidate_content_evidence(
                    case, candidate_path, effective_goal, effective_decision,
                )
                normalized_equal = (
                    actual_content["source_content_sha256"]
                    == actual_content["candidate_content_sha256"]
                )
                if authoring_decision == "NO_CHANGE" and not normalized_equal:
                    _add(
                        findings, "error", "BENCHMARK_DECISION_CONTENT_MISMATCH",
                        candidate_id=candidate_id, decision=authoring_decision,
                    )
                if authoring_decision == "REWRITE":
                    if normalized_equal:
                        _add(
                            findings, "error", "BENCHMARK_CANDIDATE_CONTENT_UNCHANGED",
                            candidate_id=candidate_id, normalization=CONTENT_NORMALIZATION,
                        )
                    elif not actual_content["substantive"]:
                        _add(
                            findings, "error", "BENCHMARK_CANDIDATE_CONTENT_TOO_SMALL",
                            candidate_id=candidate_id,
                            changed=actual_content["changed_visible_chars"],
                            required=actual_content["minimum_changed_chars"],
                        )
                if benchmark_goal == "improvement" and authoring_decision != "REWRITE":
                    _add(
                        findings, "error", "BENCHMARK_IMPROVEMENT_REQUIRES_REWRITE",
                        candidate_id=candidate_id, decision=authoring_decision,
                    )
                if candidate.get("authoring_decision") != authoring_decision:
                    severity = "warning" if rule_freshness == "historical-unbound" else "error"
                    _add(
                        findings, severity, "BENCHMARK_AUTHORING_DECISION_LOCK_MISMATCH",
                        candidate_id=candidate_id,
                    )
                recorded_content = candidate.get("content_evidence")
                if recorded_content is None:
                    severity = "warning" if rule_freshness == "historical-unbound" else "error"
                    _add(
                        findings, severity, "BENCHMARK_CONTENT_EVIDENCE_MISSING",
                        candidate_id=candidate_id,
                    )
                elif not _content_evidence_matches(recorded_content, actual_content):
                    _add(
                        findings, "error", "BENCHMARK_CONTENT_EVIDENCE_MISMATCH",
                        candidate_id=candidate_id,
                    )
                group_key = (str(candidate.get("case_id")), str(candidate.get("provider")))
                if authoring_decision == "REWRITE":
                    for other_id, other_path in trial_content_groups[group_key]:
                        trial_delta = _content_delta(other_path, candidate_path, trial_pair=True)
                        if not trial_delta["substantive"]:
                            code = (
                                "BENCHMARK_TRIAL_CONTENT_DUPLICATE"
                                if trial_delta["left_content_sha256"] == trial_delta["right_content_sha256"]
                                else "BENCHMARK_TRIAL_CONTENT_NEAR_DUPLICATE"
                            )
                            _add(
                                findings, "error", code, candidate_id=candidate_id,
                                other_candidate_id=other_id,
                                changed=trial_delta["changed_visible_chars"],
                                required=trial_delta["minimum_changed_chars"],
                            )
                    trial_content_groups[group_key].append((candidate_id, candidate_path))
            except (OSError, UnicodeError, ValueError) as exc:
                _add(
                    findings, "error", "BENCHMARK_CONTENT_EVIDENCE_INVALID",
                    candidate_id=candidate_id, error=str(exc),
                )
            try:
                _validate_verification(
                    verification_path,
                    registry,
                    str(candidate.get("provider")),
                    str(case["source"]["sha256"]),
                    str(candidate["candidate"]["sha256"]),
                )
            except (ValueError, KeyError) as exc:
                _add(
                    findings, "error", "BENCHMARK_CANDIDATE_VERIFICATION_INVALID",
                    candidate_id=candidate_id, error=str(exc),
                )
            try:
                generation_payload = _load(generation_path)
                _validate_generation(
                    generation_path,
                    str(candidate.get("provider")),
                    str(case["source"]["sha256"]),
                    str(candidate["candidate"]["sha256"]),
                    allow_legacy=rule_freshness == "historical-unbound",
                    require_stack_evaluation=(
                        "stack_evaluation" in required_generation_evidence
                    ),
                    registry_path=registry_path,
                )
                if isinstance(suite, dict) and suite.get("writing_rule_snapshot") \
                        and generation_payload.get("writing_rule_snapshot") is None:
                    _add(
                        findings, "error", "BENCHMARK_GENERATION_RULE_SNAPSHOT_MISSING",
                        candidate_id=candidate_id,
                    )
                elif isinstance(suite, dict) and suite.get("writing_rule_snapshot") \
                        and _rule_snapshot_key(suite.get("writing_rule_snapshot")) != _rule_snapshot_key(
                            generation_payload.get("writing_rule_snapshot")
                        ):
                    _add(
                        findings, "error", "BENCHMARK_GENERATION_RULE_SNAPSHOT_MISMATCH",
                        candidate_id=candidate_id,
                    )
                if any(
                    other.get("id") != candidate_id
                    and other.get("generation", {}).get("run_id") == generation_payload.get("execution", {}).get("run_id")
                    for other in payload.get("candidates", [])
                ):
                    _add(findings, "error", "BENCHMARK_GENERATION_RUN_DUPLICATE", candidate_id=candidate_id)
            except (ValueError, KeyError) as exc:
                _add(findings, "error", "BENCHMARK_GENERATION_INVALID", candidate_id=candidate_id, error=str(exc))
    if state in {"BLIND_READY", *SCORED_STATES}:
        required = _required_candidate_keys(payload)
        if candidate_ids != required:
            _add(
                findings, "error", "BENCHMARK_CANDIDATE_MATRIX_INCOMPLETE",
                missing=sorted(required - candidate_ids), extra=sorted(candidate_ids - required),
            )
        blind = payload.get("blind", {})
        for key in ("pairs", "packet", "key", "ratings_template", "pair_map"):
            _check_lock(blind.get(key) if isinstance(blind, dict) else None, findings, f"blind.{key}")
        review_page = blind.get("review_page") if isinstance(blind, dict) else None
        review_bundle = blind.get("review_bundle") if isinstance(blind, dict) else None
        if ignore_existing_review and review_page is not None and review_bundle is not None:
            _add(findings, "warning", "BENCHMARK_REVIEW_PACKAGE_IGNORED_FOR_REFRESH")
        elif review_page is None and review_bundle is None and allow_missing_review:
            _add(findings, "warning", "BENCHMARK_REVIEW_PACKAGE_MISSING")
        elif review_page is None or review_bundle is None:
            _add(findings, "error", "BENCHMARK_REVIEW_PACKAGE_INCOMPLETE")
        else:
            page_path = _check_lock(review_page, findings, "blind.review_page")
            bundle_path = _check_lock(review_bundle, findings, "blind.review_bundle")
            if page_path is not None and bundle_path is not None:
                review_report = audit_review_bundle(bundle_path)
                if review_report.get("status") != "pass":
                    _add(
                        findings, "error", "BENCHMARK_REVIEW_PACKAGE_INVALID",
                        review_findings=review_report.get("findings", []),
                    )
                else:
                    bundle_payload = _load(bundle_path)
                    if (
                        bundle_payload.get("packet", {}).get("sha256") != blind.get("packet", {}).get("sha256")
                        or bundle_payload.get("ratings_template", {}).get("sha256")
                        != blind.get("ratings_template", {}).get("sha256")
                        or bundle_payload.get("review_page", {}).get("sha256") != review_page.get("sha256")
                    ):
                        _add(findings, "error", "BENCHMARK_REVIEW_PACKAGE_LOCK_MISMATCH")
        if ignore_existing_review:
            _add(findings, "warning", "BENCHMARK_SCORING_SNAPSHOT_IGNORED_FOR_REFRESH")
        else:
            scoring_protocol = blind.get("scoring_protocol") if isinstance(blind, dict) else None
            scoring_rules = blind.get("scoring_rules") if isinstance(blind, dict) else None
            if scoring_protocol != SCORING_PROTOCOL:
                if allow_legacy_protocol:
                    _add(findings, "warning", "BENCHMARK_SCORING_PROTOCOL_LEGACY", value=scoring_protocol)
                else:
                    _add(findings, "error", "BENCHMARK_SCORING_PROTOCOL_INVALID", value=scoring_protocol)
            if not isinstance(scoring_rules, list) or not scoring_rules:
                if allow_legacy_protocol:
                    _add(findings, "warning", "BENCHMARK_SCORING_RULE_SNAPSHOT_MISSING")
                else:
                    _add(findings, "error", "BENCHMARK_SCORING_RULE_SNAPSHOT_MISSING")
            else:
                expected_rule = Path(__file__).resolve().with_name("blind_pair_evaluation.py")
                if len(scoring_rules) != 1 or Path(str(scoring_rules[0].get("path", ""))).resolve() != expected_rule:
                    _add(findings, "error", "BENCHMARK_SCORING_RULE_SNAPSHOT_INVALID")
                else:
                    _check_lock(scoring_rules[0], findings, "blind.scoring_rules[0]")
            scoring_orchestrator = blind.get("scoring_orchestrator") if isinstance(blind, dict) else None
            expected_orchestrator = Path(__file__).resolve()
            if not isinstance(scoring_orchestrator, dict):
                if allow_legacy_protocol:
                    _add(findings, "warning", "BENCHMARK_SCORING_ORCHESTRATOR_SNAPSHOT_MISSING")
                else:
                    _add(findings, "error", "BENCHMARK_SCORING_ORCHESTRATOR_SNAPSHOT_MISSING")
            elif Path(str(scoring_orchestrator.get("path", ""))).resolve() != expected_orchestrator:
                _add(findings, "error", "BENCHMARK_SCORING_ORCHESTRATOR_SNAPSHOT_INVALID")
            else:
                if rule_freshness == "historical-unbound":
                    actual = sha256_file(expected_orchestrator)
                    if actual != scoring_orchestrator.get("sha256"):
                        _add(
                            findings, "warning", "BENCHMARK_LEGACY_SCORING_ORCHESTRATOR_DRIFT",
                            expected=scoring_orchestrator.get("sha256"), actual=actual,
                            path=str(expected_orchestrator),
                        )
                    else:
                        _check_lock(scoring_orchestrator, findings, "blind.scoring_orchestrator")
                else:
                    _check_lock(scoring_orchestrator, findings, "blind.scoring_orchestrator")
    if state in SCORED_STATES:
        score_record = payload.get("score", {})
        for key in ("blind_score", "ratings", "ratings_merge", "failure_capsules"):
            _check_lock(
                score_record.get(key) if isinstance(score_record, dict) else None,
                findings, f"score.{key}",
            )
        if not isinstance(score_record, dict) or not score_record.get("summary"):
            _add(findings, "error", "BENCHMARK_SCORE_SUMMARY_MISSING")
    parent = payload.get("parent_manifest")
    if parent is not None:
        _check_lock(parent, findings, "parent_manifest")
    claims = payload.get("claims", {})
    if claims.get("authorship_or_detector_verdict") is not False \
            or claims.get("automatic_winner_selection") is not False:
        _add(findings, "error", "BENCHMARK_FORBIDDEN_CLAIM_ENABLED")
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "schema": "aigc-style-benchmark-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "state": state,
        "suite_id": suite.get("id") if isinstance(suite, dict) else None,
        "split": split,
        "benchmark_goal": benchmark_goal,
        "cases": len(case_ids),
        "candidates": len(candidate_ids),
        "rule_freshness": rule_freshness,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }


def aggregate(manifest_paths: list[Path], output: Path, registry_path: Path) -> dict:
    output = _ensure_new_output(output)
    totals: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {dimension: {"win": 0, "loss": 0, "tie": 0} for dimension in DIMENSIONS}
    )
    scenes: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {dimension: {"win": 0, "loss": 0, "tie": 0} for dimension in DIMENSIONS}
    )
    suites = []
    seen: set[tuple[str, str, str]] = set()
    seen_source_hashes: set[str] = set()
    failure_records = []
    for path in manifest_paths:
        path = path.resolve()
        report = audit_manifest(path, registry_path)
        if report["status"] != "pass" or report["state"] not in SCORED_STATES:
            raise ValueError(f"benchmark is not a valid scored manifest: {path}: {report['findings']}")
        payload = _load(path)
        identity = (
            str(payload["suite"]["id"]), str(payload["suite"]["version"]),
            str(payload["suite"]["split"]),
        )
        if identity in seen:
            raise ValueError(f"duplicate scored suite: {identity}")
        seen.add(identity)
        for case in payload["cases"]:
            source_hash = str(case["source"]["sha256"])
            if source_hash in seen_source_hashes:
                raise ValueError(
                    "a source passage appears in more than one aggregated suite; "
                    "dev and holdout must not reuse text"
                )
            seen_source_hashes.add(source_hash)
        summary = payload["score"]["summary"]
        for provider, dimensions in summary["by_provider"].items():
            for dimension, outcomes in dimensions.items():
                for outcome, count in outcomes.items():
                    totals[provider][dimension][outcome] += int(count)
        for scene, dimensions in summary["by_scene"].items():
            for dimension, outcomes in dimensions.items():
                for outcome, count in outcomes.items():
                    scenes[scene][dimension][outcome] += int(count)
        failure_payload = _load(Path(payload["score"]["failure_capsules"]["path"]))
        failure_records.extend(failure_payload.get("failures", []))
        suites.append({
            "id": identity[0], "version": identity[1], "split": identity[2],
            "manifest": _locked(path), "state": payload["state"],
            "cases": len(payload["cases"]), "candidates": len(payload["candidates"]),
        })
    report = {
        "schema": PORTFOLIO_SCHEMA,
        "status": "HUMAN_EVIDENCE_AGGREGATED",
        "suites": suites,
        "by_provider": json.loads(json.dumps(totals)),
        "by_scene": json.loads(json.dumps(scenes)),
        "failure_capsules": failure_records,
        "interpretation": (
            "This portfolio aggregates frozen human pairwise choices. It does not prove human "
            "authorship, detector evasion, or quality outside the represented scenes."
        ),
    }
    write_json(output, report)
    return report


def _print_report(report: dict, label: str, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(
        f"{label} {str(report.get('status', report.get('state', ''))).upper()} "
        f"suite={report.get('suite_id', '')} cases={report.get('cases', '')} "
        f"candidates={report.get('candidates', '')}"
    )
    for finding in report.get("findings", []):
        detail = ", ".join(
            f"{key}={value}" for key, value in finding.items()
            if key not in {"severity", "code"}
        )
        print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("suite", type=Path)
    init_parser.add_argument("--output-dir", type=Path, required=True)
    init_parser.add_argument("--format", choices=("text", "json"), default="text")
    register_parser = sub.add_parser("register")
    register_parser.add_argument("manifest", type=Path)
    register_parser.add_argument("--case-id", required=True)
    register_parser.add_argument("--provider", required=True)
    register_parser.add_argument("--trial", type=int, required=True)
    register_parser.add_argument("--candidate", type=Path, required=True)
    register_parser.add_argument("--verification", type=Path, required=True)
    register_parser.add_argument("--generation", type=Path, required=True)
    register_parser.add_argument("--output", type=Path, required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("manifest", type=Path)
    prepare_parser.add_argument("--seed", type=int, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    review_parser = sub.add_parser("package-review")
    review_parser.add_argument("manifest", type=Path)
    review_parser.add_argument("--output", type=Path, required=True)
    review_parser.add_argument("--refresh", action="store_true")
    score_parser = sub.add_parser("score")
    score_parser.add_argument("manifest", type=Path)
    score_parser.add_argument("ratings", type=Path)
    score_parser.add_argument("--ratings-merge", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    probe_parser = sub.add_parser("probe")
    probe_parser.add_argument("manifest", type=Path)
    probe_parser.add_argument("ratings", type=Path)
    probe_parser.add_argument("--output", type=Path, required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("manifest", type=Path)
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument("manifests", type=Path, nargs="+")
    aggregate_parser.add_argument("--output", type=Path, required=True)
    aggregate_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    if args.command == "init":
        _, path = init_suite(args.suite, args.output_dir, registry)
        report = audit_manifest(path, registry)
        _print_report(report, "STYLE BENCHMARK INIT", args.format)
        print(f"manifest={path}")
        return 0
    if args.command == "register":
        payload, path = register_candidate(
            args.manifest, args.case_id, args.provider, args.trial,
            args.candidate, args.verification, args.output, registry,
            args.generation,
        )
        print(
            f"STYLE BENCHMARK REGISTERED state={payload['state']} "
            f"candidates={len(payload['candidates'])} manifest={path}"
        )
        return 0
    if args.command == "prepare":
        payload, path = prepare_benchmark(args.manifest, args.seed, args.output, registry)
        print(
            f"STYLE BENCHMARK BLIND_READY pairs={len(payload['candidates'])} "
            f"packet={payload['blind']['packet']['path']} manifest={path}"
        )
        return 0
    if args.command == "package-review":
        payload, path = package_review(args.manifest, args.output, registry, args.refresh)
        print(
            f"STYLE BENCHMARK REVIEW PACKAGED state={payload['state']} "
            f"page={payload['blind']['review_page']['path']} manifest={path}"
        )
        return 0
    if args.command == "score":
        payload, path = score_benchmark(
            args.manifest, args.ratings, args.ratings_merge, args.output, registry,
        )
        print(
            f"STYLE BENCHMARK {payload['state']} failures="
            f"{payload['score']['summary']['failure_count']} manifest={path}"
        )
        return 0
    if args.command == "probe":
        report = probe_benchmark(args.manifest, args.ratings, args.output, registry)
        print(
            f"STYLE BENCHMARK MODEL PROBE PASS suite={report['suite_id']} "
            f"pairs={len(report['model_coverage'])} output={args.output.resolve()}"
        )
        return 0
    if args.command == "audit":
        report = audit_manifest(args.manifest, registry)
        _print_report(report, "STYLE BENCHMARK AUDIT", args.format)
        return 0 if report["status"] == "pass" else 1
    report = aggregate(args.manifests, args.output, registry)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"STYLE BENCHMARK PORTFOLIO {report['status']} "
            f"suites={len(report['suites'])} failures={len(report['failure_capsules'])}"
        )
        print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
