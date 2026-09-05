from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "audit_humanize_confirmed_root_selection.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_humanize_confirmed_root_selection", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_preflight_separates_document_candidates_from_heavy_roots(
    tmp_path: Path, monkeypatch
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"entries": [{"phrase": "\u6536\u7d27", "category": "scope-boundary"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    raw = tmp_path / "raw.csv"
    write_csv(
        raw,
        "phrase,category,source_kind,preselection_reason",
        [
            "\u590d\u6838,audit-governance,raw-short-core-pass4,eligible_raw_short_core",
            "\u5b50\u4ee3,audit-governance,raw-short-core-pass4,eligible_raw_short_core",
        ],
    )
    document = tmp_path / "document.csv"
    write_csv(
        document,
        "phrase,category,source_kind",
        ["\u65b9\u7a0b,audit-governance,document-short-core-pass7"],
    )
    roots = tmp_path / "roots.csv"
    write_csv(
        roots,
        "root,selected_for_targeted_long_scan,immediate_extension_fragment",
        ["\u6536\u7d27,True,False", "\u5b50\u4ee3,False,True"],
    )
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--baseline-inventory",
            str(baseline),
            "--raw-short-audit",
            str(raw),
            "--document-short-selected",
            str(document),
            "--root-selection-audit",
            str(roots),
            "--output",
            str(output),
        ],
    )

    assert MODULE.main() == 0
    selected = set(
        json.loads((output / "selected_confirmed_roots.json").read_text(encoding="utf-8"))
    )
    assert "\u6536\u7d27" in selected
    assert "\u590d\u6838" in selected
    assert "\u5b50\u4ee3" not in selected
    assert "\u65b9\u7a0b" not in selected
