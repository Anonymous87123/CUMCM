#!/usr/bin/env python
"""Preflight heavy root-graph selection without rescanning chats or documents."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import expand_humanize_strict_lexicon as discovery  # noqa: E402


VERSION = "1.0.0"


def load_csv_rows(
    path: Path,
    predicate: Callable[[dict[str, str]], bool] | None = None,
) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if predicate is not None:
        rows = [row for row in rows if predicate(row)]
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-inventory", type=Path, required=True)
    parser.add_argument("--decompose-csv", type=Path, action="append", default=[])
    parser.add_argument("--raw-short-audit", type=Path, required=True)
    parser.add_argument("--document-short-selected", type=Path, required=True)
    parser.add_argument("--root-selection-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output}")

    baseline_payload = json.loads(args.baseline_inventory.read_text(encoding="utf-8"))
    baseline = list(baseline_payload.get("entries", []))
    decomposition, _manifest, decomposition_stats = (
        discovery.load_csv_decomposition_parents(args.decompose_csv)
    )
    raw_short = load_csv_rows(
        args.raw_short_audit,
        lambda row: row.get("preselection_reason") == "eligible_raw_short_core",
    )
    document_short = load_csv_rows(args.document_short_selected)
    confirmed = [*baseline, *decomposition, *raw_short, *document_short]
    external = discovery.load_root_graph_allowlist(args.root_selection_audit)
    fragment_blocklist = discovery.load_root_graph_fragment_blocklist(
        args.root_selection_audit
    )
    selected, stats = discovery.select_confirmed_parent_graph_roots(
        confirmed,
        discovery.marker_map(baseline),
        external,
        fragment_blocklist=fragment_blocklist,
        audit_path=args.output / "confirmed_parent_root_probe_audit.csv",
    )

    selected_path = args.output / "selected_confirmed_roots.json"
    selected_path.write_text(
        json.dumps(sorted(selected), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metadata = {
        "schema_version": "humanize-confirmed-root-selection-preflight/v1",
        "version": VERSION,
        "baseline_inventory": str(args.baseline_inventory),
        "baseline_inventory_sha256": discovery.sha256_path(args.baseline_inventory),
        "decompose_csv": [str(path) for path in args.decompose_csv],
        "raw_short_audit": str(args.raw_short_audit),
        "document_short_selected": str(args.document_short_selected),
        "root_selection_audit": str(args.root_selection_audit),
        "root_selection_audit_sha256": discovery.sha256_path(
            args.root_selection_audit
        ),
        "inputs": {
            "baseline_entries": len(baseline),
            "decomposition_parents": len(decomposition),
            "raw_short_selected": len(raw_short),
            "document_short_selected": len(document_short),
            "confirmed_parent_rows": len(confirmed),
            "external_roots": len(external),
            "immediate_extension_fragment_roots": len(fragment_blocklist),
        },
        "decomposition_stats": decomposition_stats,
        "selection_stats": stats,
        "selected_roots": len(selected),
        "selected_roots_sha256": discovery.sha256_path(selected_path),
    }
    (args.output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
