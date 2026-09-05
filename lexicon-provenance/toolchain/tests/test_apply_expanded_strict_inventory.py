from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "apply_expanded_strict_inventory.py"
SPEC = importlib.util.spec_from_file_location("apply_expanded_strict_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_inventory() -> dict:
    entries = [
        {
            "phrase": f"严格短语{chr(0x4E00 + index // 100)}{chr(0x4E00 + index % 100)}",
            "category": "process-broadcast",
            "combined_coverage": 1,
            "evidence_scope": "chat-only",
        }
        for index in range(1000)
    ]
    return {
        "summary": {"selection": {"strict_inventory_entries": len(entries)}},
        "entries": entries,
    }


def test_validate_inventory_rejects_single_character_ban() -> None:
    inventory = valid_inventory()
    inventory["entries"][0]["phrase"] = "稳"
    with pytest.raises(ValueError, match="invalid 2-12 Han phrase"):
        MODULE.validate_inventory(inventory)


def test_validate_inventory_rejects_zero_coverage() -> None:
    inventory = valid_inventory()
    inventory["entries"][0]["combined_coverage"] = 0
    with pytest.raises(ValueError, match="no current evidence"):
        MODULE.validate_inventory(inventory)


def test_validate_inventory_accepts_evidence_backed_phrases() -> None:
    inventory = valid_inventory()
    assert len(MODULE.validate_inventory(inventory)) == 1000


def test_canonical_inventory_hash_ignores_entry_and_key_order() -> None:
    entries = valid_inventory()["entries"][:2]
    reversed_keys = [dict(reversed(list(entry.items()))) for entry in reversed(entries)]
    assert MODULE.canonical_inventory_sha256(entries) == (
        MODULE.canonical_inventory_sha256(reversed_keys)
    )


def test_install_rejects_an_unreviewed_large_inventory(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    lexicon_path = tmp_path / "lexicon.json"
    inventory_path.write_text(
        json.dumps(valid_inventory(), ensure_ascii=False), encoding="utf-8"
    )
    lexicon_path.write_text('{"signals": []}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not the reviewed release"):
        MODULE.install(
            inventory_path,
            lexicon_path,
            None,
            dry_run=True,
        )
