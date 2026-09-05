from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_humanize_document_snapshot.py"
SPEC = importlib.util.spec_from_file_location("build_humanize_document_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_snapshot_deduplicates_overlapping_roots_and_excludes_trees(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    excluded = root / "generated"
    nested.mkdir(parents=True)
    excluded.mkdir()
    (root / "one.md").write_text("one", encoding="utf-8")
    (nested / "two.tex").write_text("two", encoding="utf-8")
    (nested / "skip.txt").write_text("skip", encoding="utf-8")
    (excluded / "derived.md").write_text("derived", encoding="utf-8")

    files, audit = MODULE.discover_document_snapshot(
        [root, nested], [excluded]
    )

    assert {Path(item["path"]).name for item in files} == {"one.md", "two.tex"}
    assert len(files) == 2
    assert [item["status"] for item in audit] == ["SCANNED", "SCANNED"]


def test_main_writes_bound_root_and_file_set_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "note.md").write_text("text", encoding="utf-8")
    output = tmp_path / "snapshot.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--root", str(root), "--output", str(output)],
    )

    assert MODULE.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "humanize-document-snapshot/v2"
    assert payload["file_count"] == 1
    assert payload["root_set_sha256"] == MODULE.canonical_path_set_sha256([root])
    assert payload["file_set_sha256"] == MODULE.file_set_sha256(payload["files"])
    assert output.with_suffix(".csv").exists()
