#!/usr/bin/env python
"""Aggregate 9-12 character chat families around discovered short roots.

The broad pass keeps every 1-8 character n-gram.  This second pass avoids the
combinatorial cost of every unrelated long window: a 9-12 character window is
retained only when it contains an evidence-backed 1-3 character discovery
root and has a complete root-family shape (or contains an explicit manual
style root).  No raw assistant text is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_humanize_chat_ngram_aggregate as broad  # noqa: E402
import expand_humanize_strict_lexicon as discovery  # noqa: E402


VERSION = "1.1.0"
MINIMUM_LONG_LENGTH = 9
MAXIMUM_LONG_LENGTH = 12
MINIMUM_NONMANUAL_EXACT_COVERAGE = 20
MAXIMUM_IMMEDIATE_EXTENSION_DOMINANCE = 0.80


def load_manual_roots(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    strict = payload.get("strict_release", {})
    roots: set[str] = set()
    for key in (
        "discovery_root_only_exact",
        "short_literal_exact",
        "high_confidence_style_core_exact",
    ):
        for value in strict.get(key, []):
            phrase = str(value)
            if 1 <= len(phrase) <= 3 and discovery.HAN_EXACT_RE.fullmatch(phrase):
                roots.add(phrase)
    return roots


def load_baseline_roots(path: Path | None) -> set[str]:
    if path is None:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for entry in payload.get("entries", []):
        phrase = str(entry.get("phrase", ""))
        if 1 <= len(phrase) <= 3 and discovery.HAN_EXACT_RE.fullmatch(phrase):
            roots.add(phrase)
    return roots


def discover_shell_roots(
    aggregate: Path,
) -> tuple[dict[str, Counter[str]], dict[str, int]]:
    evidence: dict[str, Counter[str]] = defaultdict(Counter)
    stats: Counter[str] = Counter()
    with aggregate.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stats["aggregate_rows_scanned_for_shell_roots"] += 1
            item = json.loads(raw)
            parent = str(item.get("phrase", ""))
            coverage = int(item.get("message_coverage", 0))
            if (
                coverage < 1
                or not 2 <= len(parent) <= 12
                or not discovery.HAN_EXACT_RE.fullmatch(parent)
            ):
                continue
            occurrences = int(item.get("count", 0))
            seen: set[str] = set()
            for root, _prefix, _suffix, _category in (
                discovery.root_inversion_residuals(parent, {})
            ):
                if root in seen:
                    continue
                seen.add(root)
                row = evidence[root]
                row["parent_count"] += 1
                row["weighted_coverage"] += max(1, coverage)
                row["weighted_occurrences"] += max(1, occurrences)
                row["max_parent_coverage"] = max(
                    row["max_parent_coverage"], coverage
                )
                row[f"shell_type/{_prefix}|{_suffix}"] = 1
            if seen:
                stats["shell_parent_rows"] += 1
    stats["shell_roots_observed"] = len(evidence)
    return evidence, dict(stats)


def discover_immediate_extension_contexts(
    aggregate: Path,
    roots: set[str],
) -> tuple[dict[str, Counter[str]], dict[str, int]]:
    """Measure whether a short root is almost always a clipped longer string.

    Aggregate rows already contain exact message coverage for every 1-8 Han
    n-gram.  A one-character extension therefore gives a cheap, deterministic
    fragment test before the expensive raw-chat pass.  The full root audit is
    still retained even when this gate rejects a long-scan anchor.
    """
    evidence: dict[str, Counter[str]] = defaultdict(Counter)
    stats: Counter[str] = Counter()
    with aggregate.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stats["aggregate_rows_scanned_for_immediate_extensions"] += 1
            item = json.loads(raw)
            parent = str(item.get("phrase", ""))
            if not 2 <= len(parent) <= 4 or not discovery.HAN_EXACT_RE.fullmatch(parent):
                continue
            coverage = int(item.get("message_coverage", 0))
            if coverage < 1:
                continue
            left_root = parent[1:]
            if left_root in roots:
                evidence[left_root][f"left/{parent[0]}"] += coverage
            right_root = parent[:-1]
            if right_root in roots:
                evidence[right_root][f"right/{parent[-1]}"] += coverage
            stats["immediate_extension_rows_considered"] += 1
    stats["roots_with_immediate_extension_evidence"] = len(evidence)
    return evidence, dict(stats)


def extension_metrics(
    evidence: Counter[str],
    exact_coverage: int,
) -> dict[str, Any]:
    left = {key[5:]: value for key, value in evidence.items() if key.startswith("left/")}
    right = {key[6:]: value for key, value in evidence.items() if key.startswith("right/")}
    denominator = max(1, exact_coverage)
    left_char, left_coverage = max(left.items(), key=lambda item: item[1], default=("", 0))
    right_char, right_coverage = max(
        right.items(), key=lambda item: item[1], default=("", 0)
    )
    left_dominance = min(1.0, left_coverage / denominator)
    right_dominance = min(1.0, right_coverage / denominator)
    return {
        "left_extension_type_count": len(left),
        "right_extension_type_count": len(right),
        "dominant_left_extension": left_char,
        "dominant_right_extension": right_char,
        "dominant_left_extension_coverage": left_coverage,
        "dominant_right_extension_coverage": right_coverage,
        "left_extension_dominance": round(left_dominance, 8),
        "right_extension_dominance": round(right_dominance, 8),
        "immediate_extension_fragment": max(left_dominance, right_dominance)
        >= MAXIMUM_IMMEDIATE_EXTENSION_DOMINANCE,
    }


def select_roots(
    aggregate: Path,
    manual_roots: set[str],
    baseline_roots: set[str],
    audit_path: Path,
) -> tuple[set[str], list[dict[str, Any]], dict[str, int]]:
    probes, stats = discovery.discover_aggregate_root_probes(
        aggregate,
        required_roots=manual_roots,
        audit_path=audit_path,
    )
    shell_roots, shell_stats = discover_shell_roots(aggregate)
    root_universe = set(shell_roots) | manual_roots | baseline_roots
    extension_evidence, extension_stats = discover_immediate_extension_contexts(
        aggregate, root_universe
    )
    selected: set[str] = set()
    rows: list[dict[str, Any]] = []
    for root in root_universe:
        probe = probes.get(root, discovery.RootProbeEvidence())
        shell = shell_roots.get(root, Counter())
        reason = discovery.root_inversion_basic_reason(root)
        required = root in manual_roots
        baseline_seed = root in baseline_roots
        evidence_ready = (
            probe.exact_message_coverage
            >= discovery.ROOT_GRAPH_EXACT_MIN_COVERAGE
            or (
                probe.short_parent_count
                >= discovery.ROOT_GRAPH_EMBEDDED_MIN_PARENT_COUNT
                and probe.short_parent_weighted_coverage
                >= discovery.ROOT_GRAPH_EMBEDDED_MIN_WEIGHTED_COVERAGE
            )
        )
        shell_ready = (
            shell["parent_count"] >= 2
            and shell["weighted_coverage"] >= 10
        )
        shell_type_count = sum(
            1 for key in shell if key.startswith("shell_type/")
        )
        extension = extension_metrics(
            extension_evidence.get(root, Counter()), probe.exact_message_coverage
        )
        exact_ready_for_long_scan = (
            probe.exact_message_coverage >= MINIMUM_NONMANUAL_EXACT_COVERAGE
        )
        single_root_ready = len(root) >= 2 or required
        extension_ready = not bool(extension["immediate_extension_fragment"])
        allowed = reason == "eligible_basic_shape" or required
        keep = allowed and (
            required
            or (
                single_root_ready
                and exact_ready_for_long_scan
                and extension_ready
                and (shell_ready or (baseline_seed and evidence_ready))
            )
        )
        if keep:
            selected.add(root)
        rows.append(
            {
                "root": root,
                "root_length": len(root),
                "basic_reason": reason,
                "manual_root": required,
                "baseline_strict_parent_root": baseline_seed,
                "shell_parent_count": shell["parent_count"],
                "shell_weighted_coverage": shell["weighted_coverage"],
                "shell_type_count": shell_type_count,
                "shell_ready": shell_ready,
                "exact_ready_for_long_scan": exact_ready_for_long_scan,
                "single_root_ready": single_root_ready,
                "extension_ready": extension_ready,
                "selected_for_targeted_long_scan": keep,
                "exact_message_coverage": probe.exact_message_coverage,
                "parent_phrase_count": probe.short_parent_count,
                "weighted_parent_coverage": probe.short_parent_weighted_coverage,
                **extension,
            }
        )
    rows.sort(
        key=lambda row: (
            not row["selected_for_targeted_long_scan"],
            -int(row["weighted_parent_coverage"]),
            str(row["root"]),
        )
    )
    selection_stats = Counter()
    selection_stats["root_universe_for_targeted_long_scan"] = len(root_universe)
    selection_stats["selected_roots_for_targeted_long_scan"] = len(selected)
    selection_stats["selected_manual_roots"] = len(selected & manual_roots)
    selection_stats["selected_nonmanual_roots"] = len(selected - manual_roots)
    selection_stats["rejected_immediate_extension_fragments"] = sum(
        bool(row["immediate_extension_fragment"]) and not bool(row["manual_root"])
        for row in rows
    )
    return selected, rows, {
        **stats,
        **shell_stats,
        **extension_stats,
        **dict(selection_stats),
    }


def roots_by_start(run: str, roots: set[str]) -> dict[int, set[str]]:
    matches: dict[int, set[str]] = defaultdict(set)
    for start in range(len(run)):
        for length in (1, 2, 3):
            end = start + length
            if end > len(run):
                break
            root = run[start:end]
            if root in roots:
                matches[start].add(root)
    return matches


def targeted_long_ngrams(
    text: str,
    roots: set[str],
    manual_roots: set[str],
) -> Counter[str]:
    return targeted_long_ngrams_from_runs(
        broad.prose_han_runs(text), roots, manual_roots
    )


def targeted_long_ngrams_from_runs(
    runs: Iterable[str],
    roots: set[str],
    manual_roots: set[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for run in runs:
        if len(run) < MINIMUM_LONG_LENGTH:
            continue
        matches = roots_by_start(run, roots)
        if not matches:
            continue
        for length in range(
            MINIMUM_LONG_LENGTH, min(MAXIMUM_LONG_LENGTH, len(run)) + 1
        ):
            for start in range(len(run) - length + 1):
                end = start + length
                hits = {
                    root
                    for root_start, root_values in matches.items()
                    if start <= root_start < end
                    for root in root_values
                    if root_start + len(root) <= end
                }
                if not hits:
                    continue
                phrase = run[start:end]
                shapes, _reason = discovery.classify_root_inversion_family_shapes(
                    phrase, hits
                )
                reversible_shell = any(
                    shape.get("gate_kind") == "reversible_shell" for shape in shapes
                )
                compound_family, _triggers, _compound_reason = (
                    discovery.classify_compound_root_candidate(phrase, 20)
                )
                if reversible_shell or compound_family is not None:
                    counts[phrase] += 1
    return counts


def scan_snapshot(
    entries: list[dict[str, Any]],
    connection,
    roots: set[str],
    manual_roots: set[str],
    *,
    flush_unique_phrases: int,
) -> dict[str, int]:
    occurrences: Counter[str] = Counter()
    coverage: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for number, entry in enumerate(entries, start=1):
        digest = hashlib.sha256()
        try:
            for raw in broad.iter_frozen_lines(entry):
                digest.update(raw)
                totals["lines"] += 1
                if (
                    broad.QUICK_RESPONSE_ITEM not in raw
                    or broad.QUICK_OUTPUT_TEXT not in raw
                    or broad.QUICK_ASSISTANT not in raw
                ):
                    continue
                try:
                    event = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    totals["parse_errors"] += 1
                    continue
                text = broad.extract_assistant_text(event)
                if not text:
                    continue
                if "\ufffd" in text or broad.MOJIBAKE_RE.search(text):
                    totals["garbled_messages"] += 1
                    continue
                runs = tuple(broad.prose_han_runs(text))
                if not runs:
                    totals["assistant_messages_without_han"] += 1
                    continue
                local = targeted_long_ngrams_from_runs(runs, roots, manual_roots)
                totals["assistant_output_messages"] += 1
                if not local:
                    continue
                totals["messages_with_targeted_long_families"] += 1
                occurrences.update(local)
                coverage.update(local.keys())
                totals["targeted_long_occurrences"] += sum(local.values())
                if len(occurrences) >= flush_unique_phrases:
                    totals["sqlite_rows_flushed"] += broad.flush_counts(
                        connection, occurrences, coverage
                    )
                    totals["sqlite_flushes"] += 1
        except OSError:
            totals["read_errors"] += 1
        totals["session_files_scanned"] += 1
        if number % 25 == 0 or number == len(entries):
            print(
                f"targeted long scan {number}/{len(entries)}; "
                f"messages={totals['assistant_output_messages']}; "
                f"pending={len(occurrences)}",
                flush=True,
            )
    totals["sqlite_rows_flushed"] += broad.flush_counts(
        connection, occurrences, coverage
    )
    totals["sqlite_flushes"] += 1
    return dict(totals)


def write_root_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    import csv

    rows = list(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["root"])
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--chat-snapshot", type=Path, required=True)
    parser.add_argument(
        "--lexicon",
        type=Path,
        default=discovery.STYLE_ANALYSIS_LEXICON_PATH,
    )
    parser.add_argument("--baseline-inventory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flush-unique-phrases", type=int, default=250_000)
    parser.add_argument(
        "--roots-only",
        action="store_true",
        help="Write the complete root-selection audit without rescanning chat text.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output}")
    snapshot, snapshot_payload = broad.load_snapshot(args.chat_snapshot)
    manual_roots = load_manual_roots(args.lexicon)
    baseline_roots = load_baseline_roots(args.baseline_inventory)
    root_audit = args.output / "root_probe_audit.csv"
    roots, root_rows, root_stats = select_roots(
        args.aggregate, manual_roots, baseline_roots, root_audit
    )
    write_root_rows(args.output / "selected_roots.csv", root_rows)

    selection_metadata = {
        "schema_version": "humanize-targeted-long-root-selection/v1",
        "version": VERSION,
        "aggregate_source": str(args.aggregate),
        "aggregate_source_sha256": broad.sha256_path(args.aggregate),
        "chat_snapshot": str(args.chat_snapshot),
        "chat_snapshot_file_set_sha256": broad.snapshot_file_set_sha256(snapshot),
        "source_snapshot_schema": snapshot_payload.get("schema_version"),
        "manual_roots": len(manual_roots),
        "baseline_roots": len(baseline_roots),
        "selected_roots": len(roots),
        "root_probe_stats": root_stats,
        "roots_only": args.roots_only,
    }
    if args.roots_only:
        (args.output / "run_metadata.json").write_text(
            json.dumps(selection_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(selection_metadata, ensure_ascii=False, indent=2), flush=True)
        return 0

    database = args.output / "targeted_long_ngrams.sqlite3"
    connection = broad.initialize_database(database)
    try:
        scan_stats = scan_snapshot(
            snapshot,
            connection,
            roots,
            manual_roots,
            flush_unique_phrases=args.flush_unique_phrases,
        )
        aggregate = args.output / "targeted_long_candidates.jsonl"
        unique_candidates = broad.export_aggregate(
            connection,
            aggregate,
            assistant_messages=int(scan_stats.get("assistant_output_messages", 0)),
        )
    finally:
        connection.close()

    metadata = {
        **selection_metadata,
        "schema_version": "humanize-targeted-long-ngram-run/v1",
        "ngram_lengths": [MINIMUM_LONG_LENGTH, MAXIMUM_LONG_LENGTH],
        "unique_candidates": unique_candidates,
        "aggregate": str(aggregate),
        "aggregate_sha256": broad.sha256_path(aggregate),
        "stats": scan_stats,
        "privacy": {
            "raw_message_text_written": False,
            "assistant_output_text_only": True,
            "code_and_math_removed_before_ngrams": True,
        },
    }
    (args.output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
