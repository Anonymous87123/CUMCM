#!/usr/bin/env python
"""Repeat strict-phrase discovery until roots and released phrases converge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EXPANDER = Path(__file__).with_name("expand_humanize_strict_lexicon.py")
STATE_SCHEMA = "humanize-root-closure-state/v5"


def canonical_set_sha256(values: Iterable[str]) -> str:
    payload = json.dumps(
        sorted(set(values)), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_config_path(expander: Path) -> Path:
    return expander.with_name("style_analysis_lexicon.json")


def load_inventory_phrases(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"inventory has no entries list: {path}")
    phrases = {
        str(entry.get("phrase", ""))
        for entry in entries
        if isinstance(entry, dict) and entry.get("phrase")
    }
    if len(phrases) != len(entries):
        raise ValueError(f"inventory contains blank or duplicate phrases: {path}")
    return phrases


def load_candidate_phrases(path: Path) -> set[str]:
    phrases: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            phrase = str(row.get("phrase", "")).strip()
            if phrase:
                phrases.add(phrase)
    return phrases


def load_discovery_roots(run_dir: Path) -> set[str]:
    roots: set[str] = set()
    inversion_path = run_dir / "root_inversion_selected_roots.json"
    if inversion_path.exists():
        payload = json.loads(inversion_path.read_text(encoding="utf-8"))
        for row in payload:
            if isinstance(row, dict) and row.get("root"):
                roots.add(str(row["root"]))
    single_path = run_dir / "single_character_root_rankings.json"
    if single_path.exists():
        payload = json.loads(single_path.read_text(encoding="utf-8"))
        for row in payload:
            if (
                isinstance(row, dict)
                and row.get("root_status") == "eligible_root"
                and row.get("root")
            ):
                roots.add(str(row["root"]))
    return roots


def load_selected_inversion_roots(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "root_inversion_selected_roots.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"selected inversion roots must be a list: {path}")
    rows = [row for row in payload if isinstance(row, dict) and row.get("root")]
    if len({str(row["root"]) for row in rows}) != len(rows):
        raise ValueError(f"selected inversion roots repeat or are blank: {path}")
    return rows


def load_selected_inversion_root_set(run_dir: Path) -> set[str]:
    return {str(row["root"]) for row in load_selected_inversion_roots(run_dir)}


def build_root_release_accounting(
    run_dir: Path,
    final_phrases: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Prove that every strong discovery root has a terminal candidate route."""
    root_rows = load_selected_inversion_roots(run_dir)
    roots = {str(row["root"]): row for row in root_rows}
    if not roots:
        return [], {"selected_inversion_roots_missing": 1}

    family_counts: Counter[str] = Counter()
    family_selected_counts: Counter[str] = Counter()
    family_terminal_rejection_counts: Counter[str] = Counter()
    family_terminal_rejection_reasons: dict[str, Counter[str]] = {
        root: Counter() for root in roots
    }
    family_path = run_dir / "root_inversion_family_candidate_audit.csv"
    if family_path.exists():
        with family_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                root = str(row.get("root_inversion_primary_root", "")).strip()
                if root not in roots:
                    continue
                family_counts[root] += 1
                if str(row.get("selected_for_exact_rescan", "")).lower() == "true":
                    family_selected_counts[root] += 1
                    continue
                reason = str(
                    row.get("final_rejection_reason")
                    or row.get("preselection_reason")
                    or row.get("pool_decision")
                    or ""
                ).strip()
                if reason.startswith("rejected_before_pool:"):
                    family_terminal_rejection_counts[root] += 1
                    family_terminal_rejection_reasons[root][reason] += 1

    exact_counts: Counter[str] = Counter()
    released_counts: Counter[str] = Counter()
    rejected_counts: Counter[str] = Counter()
    unrouted_counts: Counter[str] = Counter()
    reason_counts: dict[str, Counter[str]] = {
        root: Counter() for root in roots
    }
    candidates_path = run_dir / "all_candidates_after_exact_rescan.csv"
    with candidates_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            root = str(row.get("root_inversion_primary_root", "")).strip()
            if root not in roots:
                continue
            exact_counts[root] += 1
            phrase = str(row.get("phrase", "")).strip()
            if phrase in final_phrases:
                released_counts[root] += 1
                continue
            decision = str(row.get("semantic_release_decision", "")).strip()
            reason = str(
                row.get("final_rejection_reason")
                or row.get("semantic_release_reason")
                or ""
            ).strip()
            if decision in {"audit_only", "reject"} and reason:
                rejected_counts[root] += 1
                reason_counts[root][reason] += 1
            elif reason:
                rejected_counts[root] += 1
                reason_counts[root][reason] += 1
            else:
                unrouted_counts[root] += 1

    accounting: list[dict[str, Any]] = []
    blockers: Counter[str] = Counter()
    for root, source in roots.items():
        inventory_hit_count = sum(root in phrase for phrase in final_phrases)
        family_count = family_counts[root]
        exact_count = exact_counts[root]
        released_count = released_counts[root]
        rejected_count = rejected_counts[root]
        unrouted_count = unrouted_counts[root]
        if family_count == 0:
            status = "NO_FAMILY_CANDIDATE"
            blockers["selected_roots_without_family_candidates"] += 1
        elif (
            exact_count == 0
            and family_selected_counts[root] == 0
            and family_terminal_rejection_counts[root] == family_count
        ):
            status = "TERMINAL_REJECTED_PRE_EXACT_REVIEW"
        elif exact_count == 0:
            status = "NO_EXACT_RESCAN_CANDIDATE"
            blockers["selected_roots_without_exact_rescan"] += 1
        elif unrouted_count:
            status = "UNROUTED_CANDIDATES"
            blockers["unrouted_root_candidate_rows"] += unrouted_count
        elif inventory_hit_count:
            status = "RELEASED"
        else:
            status = "TERMINAL_REJECTED_REVIEW"
        accounting.append(
            {
                "root": root,
                "status": status,
                "inventory_hit_count": inventory_hit_count,
                "family_candidate_count": family_count,
                "family_selected_for_exact_rescan_count": family_selected_counts[root],
                "family_terminal_rejection_count": family_terminal_rejection_counts[root],
                "exact_rescan_candidate_count": exact_count,
                "released_candidate_count": released_count,
                "terminal_rejection_count": (
                    rejected_count + family_terminal_rejection_counts[root]
                ),
                "unrouted_candidate_count": unrouted_count,
                "weighted_parent_coverage": int(
                    source.get("weighted_parent_coverage", 0)
                ),
                "shell_weighted_parent_coverage": int(
                    source.get("shell_weighted_parent_coverage", 0)
                ),
                "terminal_rejection_reasons": dict(
                    (
                        reason_counts[root]
                        + family_terminal_rejection_reasons[root]
                    ).most_common()
                ),
            }
        )
    accounting.sort(
        key=lambda row: (
            not row["status"].startswith("TERMINAL_REJECTED_"),
            -row["shell_weighted_parent_coverage"],
            row["root"],
        )
    )
    (run_dir / "root_release_accounting.json").write_text(
        json.dumps(accounting, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_rows = [
        {
            **row,
            "terminal_rejection_reasons": json.dumps(
                row["terminal_rejection_reasons"],
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        for row in accounting
    ]
    with (run_dir / "root_release_accounting.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    return accounting, dict(blockers)


def pool_blockers(summary: dict[str, Any]) -> dict[str, int]:
    selection = summary.get("selection", {})
    aggregate = summary.get("aggregate_discovery", {})
    document = summary.get("document_ngram_discovery", {})
    decomposition = summary.get("csv_decomposition", {})
    blockers = {
        "subphrase_target_cap": int(
            selection.get("rejection/subphrase_target_cap", 0)
        ),
        "longphrase_target_cap": int(
            selection.get("rejection/longphrase_target_cap", 0)
        ),
        "root_family_pool_drops": int(
            aggregate.get("root_inversion_family_dropped_by_pool", 0)
        ),
        "root_family_selection_gaps": int(
            aggregate.get("root_inversion_family_unexpected_selection_gaps", 0)
        ),
        "document_root_pool_drops": int(
            document.get("document_ngram_candidates_dropped_by_pool", 0)
        ),
        "decomposition_parent_pool_drops": int(
            decomposition.get("parents_truncated_to_limit", 0)
        ),
    }
    return {key: value for key, value in blockers.items() if value}


def round_is_converged(iteration: int, state: dict[str, Any]) -> bool:
    if iteration < 2:
        return False
    stable_count_fields = (
        "new_phrase_count",
        "removed_phrase_count",
        "new_candidate_phrase_count",
        "removed_candidate_phrase_count",
        "new_root_count",
        "removed_root_count",
        "new_selected_inversion_root_count",
        "removed_selected_inversion_root_count",
    )
    return (
        all(int(state[field]) == 0 for field in stable_count_fields)
        and not state["pool_blockers"]
        and not state["root_accounting_blockers"]
    )


def build_round_state(
    *,
    iteration: int,
    run_dir: Path,
    baseline_phrases: set[str],
    previous_candidate_phrases: set[str],
    previous_roots: set[str],
    previous_selected_inversion_roots: set[str],
    aggregate_sha256: str,
    chat_snapshot_sha256: str,
    document_snapshot_sha256: str,
    expander_sha256: str,
    semantic_release_config_sha256: str,
    semantic_release_config_schema: str,
    root_selection_audit_sha256: str = "",
) -> dict[str, Any]:
    inventory_path = run_dir / "strict_ai_phrase_inventory_expanded.json"
    candidates_path = run_dir / "all_candidates_after_exact_rescan.csv"
    summary_path = run_dir / "run_metadata.json"
    final_phrases = load_inventory_phrases(inventory_path)
    candidate_phrases = load_candidate_phrases(candidates_path)
    roots = load_discovery_roots(run_dir)
    selected_inversion_roots = load_selected_inversion_root_set(run_dir)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    observed_config_hash = str(summary.get("semantic_release_config_sha256", ""))
    observed_config_schema = str(summary.get("semantic_release_config_schema", ""))
    observed_expander_hash = str(summary.get("expander_sha256", ""))
    observed_root_selection_hash = str(
        summary.get("root_selection_audit_sha256", "") or ""
    )
    if observed_expander_hash != expander_sha256:
        raise RuntimeError(
            "expander changed during closure: "
            f"expected {expander_sha256}, observed {observed_expander_hash}"
        )
    if observed_config_hash != semantic_release_config_sha256:
        raise RuntimeError(
            "semantic release config changed during closure: "
            f"expected {semantic_release_config_sha256}, observed {observed_config_hash}"
        )
    if observed_config_schema != semantic_release_config_schema:
        raise RuntimeError(
            "semantic release config schema changed during closure: "
            f"expected {semantic_release_config_schema}, observed {observed_config_schema}"
        )
    if (
        root_selection_audit_sha256
        and observed_root_selection_hash != root_selection_audit_sha256
    ):
        raise RuntimeError(
            "root selection audit changed during closure: "
            f"expected {root_selection_audit_sha256}, "
            f"observed {observed_root_selection_hash}"
        )
    blockers = pool_blockers(summary)
    root_accounting, root_accounting_blockers = build_root_release_accounting(
        run_dir, final_phrases
    )
    new_phrases = final_phrases - baseline_phrases
    removed_phrases = baseline_phrases - final_phrases
    new_candidates = candidate_phrases - previous_candidate_phrases
    removed_candidates = previous_candidate_phrases - candidate_phrases
    new_roots = roots - previous_roots
    removed_roots = previous_roots - roots
    new_selected_inversion_roots = (
        selected_inversion_roots - previous_selected_inversion_roots
    )
    removed_selected_inversion_roots = (
        previous_selected_inversion_roots - selected_inversion_roots
    )
    return {
        "schema_version": STATE_SCHEMA,
        "iteration": iteration,
        "run_dir": str(run_dir),
        "aggregate_sha256": aggregate_sha256,
        "chat_snapshot_sha256": chat_snapshot_sha256,
        "document_snapshot_sha256": document_snapshot_sha256,
        "expander_sha256": expander_sha256,
        "semantic_release_config_sha256": semantic_release_config_sha256,
        "semantic_release_config_schema": semantic_release_config_schema,
        "root_selection_audit_sha256": root_selection_audit_sha256,
        "baseline_phrase_count": len(baseline_phrases),
        "final_phrase_count": len(final_phrases),
        "candidate_phrase_count": len(candidate_phrases),
        "root_count": len(roots),
        "new_phrase_count": len(new_phrases),
        "removed_phrase_count": len(removed_phrases),
        "new_candidate_phrase_count": len(new_candidates),
        "removed_candidate_phrase_count": len(removed_candidates),
        "new_root_count": len(new_roots),
        "removed_root_count": len(removed_roots),
        "selected_inversion_root_count": len(selected_inversion_roots),
        "new_selected_inversion_root_count": len(new_selected_inversion_roots),
        "removed_selected_inversion_root_count": len(
            removed_selected_inversion_roots
        ),
        "final_phrase_set_sha256": canonical_set_sha256(final_phrases),
        "candidate_phrase_set_sha256": canonical_set_sha256(candidate_phrases),
        "root_set_sha256": canonical_set_sha256(roots),
        "selected_inversion_root_set_sha256": canonical_set_sha256(
            selected_inversion_roots
        ),
        "new_phrase_set_sha256": canonical_set_sha256(new_phrases),
        "removed_phrase_set_sha256": canonical_set_sha256(removed_phrases),
        "new_candidate_phrase_set_sha256": canonical_set_sha256(new_candidates),
        "removed_candidate_phrase_set_sha256": canonical_set_sha256(
            removed_candidates
        ),
        "new_root_set_sha256": canonical_set_sha256(new_roots),
        "removed_root_set_sha256": canonical_set_sha256(removed_roots),
        "new_selected_inversion_root_set_sha256": canonical_set_sha256(
            new_selected_inversion_roots
        ),
        "removed_selected_inversion_root_set_sha256": canonical_set_sha256(
            removed_selected_inversion_roots
        ),
        "new_phrase_examples": sorted(new_phrases)[:200],
        "removed_phrase_examples": sorted(removed_phrases)[:200],
        "new_candidate_phrase_examples": sorted(new_candidates)[:200],
        "removed_candidate_phrase_examples": sorted(removed_candidates)[:200],
        "new_root_examples": sorted(new_roots)[:200],
        "removed_root_examples": sorted(removed_roots)[:200],
        "new_selected_inversion_root_examples": sorted(
            new_selected_inversion_roots
        )[:200],
        "removed_selected_inversion_root_examples": sorted(
            removed_selected_inversion_roots
        )[:200],
        "pool_blockers": blockers,
        "root_accounting_blockers": root_accounting_blockers,
        "root_release_accounting": {
            "selected_root_count": len(root_accounting),
            "released_root_count": sum(
                row["status"] == "RELEASED" for row in root_accounting
            ),
            "terminal_rejected_review_count": sum(
                row["status"].startswith("TERMINAL_REJECTED_")
                for row in root_accounting
            ),
            "unrouted_candidate_count": sum(
                row["unrouted_candidate_count"] for row in root_accounting
            ),
            "terminal_rejected_review_roots": [
                row["root"]
                for row in root_accounting
                if row["status"].startswith("TERMINAL_REJECTED_")
            ],
        },
        "converged": False,
        "stop_reason": "CONTINUE",
    }


def run_expander(
    args: argparse.Namespace,
    *,
    baseline: Path,
    decomposition: Path,
    output: Path,
    exact_count_cache: Path | None = None,
) -> None:
    command = [
        sys.executable,
        str(args.expander),
        "--baseline-inventory",
        str(baseline),
        "--aggregate-chat-candidates",
        str(args.aggregate_chat_candidates),
        "--codex-root",
        str(args.codex_root),
        "--chat-snapshot",
        str(args.chat_snapshot),
        "--document-snapshot",
        str(args.document_snapshot),
        "--decompose-csv",
        str(decomposition),
        "--subphrase-pool",
        str(args.subphrase_pool),
        "--longphrase-pool-per-category",
        str(args.longphrase_pool_per_category),
        "--target-subphrases",
        str(args.target_subphrases),
        "--target-longphrases",
        str(args.target_longphrases),
        "--output",
        str(output),
        "--root-closure-only",
    ]
    if exact_count_cache is not None:
        command.extend(("--exact-count-cache", str(exact_count_cache)))
    if getattr(args, "root_selection_audit", None) is not None:
        command.extend(
            ("--root-selection-audit", str(args.root_selection_audit))
        )
    for path in args.persistent_decompose_csv:
        if path.resolve() != decomposition.resolve():
            command.extend(("--decompose-csv", str(path)))
    for root in args.document_root:
        command.extend(("--document-root", str(root)))
    for root in args.exclude_root:
        command.extend(("--exclude-root", str(root)))
    subprocess.run(command, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expander", type=Path, default=DEFAULT_EXPANDER)
    parser.add_argument("--baseline-inventory", type=Path, required=True)
    parser.add_argument("--aggregate-chat-candidates", type=Path, required=True)
    parser.add_argument("--codex-root", type=Path, required=True)
    parser.add_argument("--chat-snapshot", type=Path, required=True)
    parser.add_argument("--document-snapshot", type=Path, required=True)
    parser.add_argument("--decompose-csv", type=Path, required=True)
    parser.add_argument("--root-selection-audit", type=Path)
    parser.add_argument(
        "--exact-count-cache",
        type=Path,
        help=(
            "Optional cache for round one. Later rounds reuse the immediately "
            "preceding round after its frozen-input binding has been written."
        ),
    )
    parser.add_argument(
        "--persistent-decompose-csv", type=Path, action="append", default=[]
    )
    parser.add_argument("--document-root", type=Path, action="append", default=[])
    parser.add_argument("--exclude-root", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-iterations", type=int, default=4)
    parser.add_argument("--subphrase-pool", type=int, default=100000)
    parser.add_argument("--longphrase-pool-per-category", type=int, default=100000)
    parser.add_argument("--target-subphrases", type=int, default=100000)
    parser.add_argument("--target-longphrases", type=int, default=100000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_iterations < 2:
        raise SystemExit("--max-iterations must be at least 2")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output}")

    aggregate_sha256 = file_sha256(args.aggregate_chat_candidates)
    chat_snapshot_sha256 = file_sha256(args.chat_snapshot)
    document_snapshot_sha256 = file_sha256(args.document_snapshot)
    expander_sha256 = file_sha256(args.expander)
    semantic_config = semantic_config_path(args.expander)
    semantic_release_config_sha256 = file_sha256(semantic_config)
    semantic_release_config_schema = str(
        json.loads(semantic_config.read_text(encoding="utf-8"))["strict_release"][
            "schema_version"
        ]
    )
    root_selection_audit_sha256 = (
        file_sha256(args.root_selection_audit)
        if args.root_selection_audit is not None
        else ""
    )
    baseline = args.baseline_inventory
    decomposition = args.decompose_csv
    previous_candidates = load_candidate_phrases(decomposition)
    previous_roots = load_discovery_roots(decomposition.parent)
    previous_selected_inversion_roots = load_selected_inversion_root_set(
        decomposition.parent
    )
    states: list[dict[str, Any]] = []

    for iteration in range(1, args.max_iterations + 1):
        run_dir = args.output / f"round-{iteration:02d}"
        baseline_phrases = load_inventory_phrases(baseline)
        run_expander(
            args,
            baseline=baseline,
            decomposition=decomposition,
            output=run_dir,
            exact_count_cache=(
                args.exact_count_cache if iteration == 1 else decomposition
            ),
        )
        state = build_round_state(
            iteration=iteration,
            run_dir=run_dir,
            baseline_phrases=baseline_phrases,
            previous_candidate_phrases=previous_candidates,
            previous_roots=previous_roots,
            previous_selected_inversion_roots=previous_selected_inversion_roots,
            aggregate_sha256=aggregate_sha256,
            chat_snapshot_sha256=chat_snapshot_sha256,
            document_snapshot_sha256=document_snapshot_sha256,
            expander_sha256=expander_sha256,
            semantic_release_config_sha256=semantic_release_config_sha256,
            semantic_release_config_schema=semantic_release_config_schema,
            root_selection_audit_sha256=root_selection_audit_sha256,
        )
        state["converged"] = round_is_converged(iteration, state)
        state["stop_reason"] = "CONVERGED" if state["converged"] else "CONTINUE"
        (run_dir / "root_closure_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        states.append(state)
        print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
        if state["converged"]:
            break
        baseline = run_dir / "strict_ai_phrase_inventory_expanded.json"
        decomposition = run_dir / "all_candidates_after_exact_rescan.csv"
        previous_candidates = load_candidate_phrases(decomposition)
        previous_roots = load_discovery_roots(run_dir)
        previous_selected_inversion_roots = load_selected_inversion_root_set(
            run_dir
        )

    converged = bool(states and states[-1]["converged"])
    manifest = {
        "schema_version": "humanize-root-closure-manifest/v5",
        "semantic_release_config_sha256": semantic_release_config_sha256,
        "semantic_release_config_schema": semantic_release_config_schema,
        "expander_sha256": expander_sha256,
        "root_selection_audit": str(args.root_selection_audit)
        if args.root_selection_audit is not None
        else None,
        "root_selection_audit_sha256": root_selection_audit_sha256,
        "converged": converged,
        "iterations_completed": len(states),
        "stop_reason": "CONVERGED" if converged else "MAX_ITERATIONS_WITHOUT_CONVERGENCE",
        "rounds": states,
    }
    (args.output / "root_closure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
