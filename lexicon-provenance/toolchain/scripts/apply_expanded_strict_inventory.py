#!/usr/bin/env python
"""Install a verified expanded strict phrase inventory into the Humanize Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HAN_PHRASE_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]{2,12}$")
STRICT_CORPUS_POLICY_SCHEMA = "humanize-strict-corpus-policy/v4"
EXPECTED_RELEASE_INVENTORY_ENTRIES = 1417
EXPECTED_RELEASE_INVENTORY_SHA256 = (
    "3282de02a7664e70befc4bfe9ee4ab1dbd775b6c7b0c8ad91b04c2d7b52bbe66"
)
CATEGORY_CONFIG = {
    "process-broadcast": (
        "LEX-STRICT-CORPUS-PROCESS-01",
        "过程播报与工作台旁白",
        "把过程播报改成直接承载对象、动作或结果的正文；学术正文不得保留助手工作台旁白。",
    ),
    "completion-closure": (
        "LEX-STRICT-CORPUS-CLOSURE-01",
        "完成态、闭环与验收封口",
        "删除无证据的完成态和验收封口，改写为可见结果或保留原有未决状态。",
    ),
    "audit-governance": (
        "LEX-STRICT-CORPUS-AUDIT-01",
        "审计、门禁与治理腔",
        "正文若不是在讨论审计对象本身，应将治理状态词改回具体事实、检查动作或证据关系。",
    ),
    "scope-boundary": (
        "LEX-STRICT-CORPUS-SCOPE-01",
        "范围、边界与强制限定串",
        "减少连续的权限、范围和强制限定播报；保留真实边界时必须绑定具体对象和位置。",
    ),
    "contrast-correction": (
        "LEX-STRICT-CORPUS-CONTRAST-01",
        "否定纠偏与核心本质壳",
        "删除预演式纠偏和空泛的核心、本质判断，让真实差异或对象关系直接承担对比。",
    ),
    "transition-roadmap": (
        "LEX-STRICT-CORPUS-TRANSITION-01",
        "过渡路标与顺序播报",
        "删除可由段序和因果关系自行显现的路标；真实推导连接词需要位置级 KEEP 理由。",
    ),
    "emphasis-shell": (
        "LEX-STRICT-CORPUS-EMPHASIS-01",
        "重点提示与显然性句壳",
        "把强调壳改为具体对象、变化、条件或例外，禁止用统一句首先宣布重点。",
    ),
    "academic-packaging": (
        "LEX-STRICT-CORPUS-PACKAGING-01",
        "抽象学术包装与价值拔高",
        "抽象名词和评价动词默认禁用；只有明确专业术语或不可替代关系才允许位置级 KEEP。",
    ),
    "research-self-proof": (
        "LEX-STRICT-CORPUS-SELFPROOF-01",
        "论文自证、贡献与意义包装",
        "删除自动贡献、意义和支撑声明，改为问题、方法、观察或限制本身。",
    ),
    "recommendation-outlook": (
        "LEX-STRICT-CORPUS-OUTLOOK-01",
        "自动建议、展望与邀请",
        "没有材料授权的建议和展望直接删除；真实后续工作必须绑定 supplied content。",
    ),
    "certainty-limitation": (
        "LEX-STRICT-CORPUS-CERTAINTY-01",
        "确定性、真实性与缓和限定",
        "删除无证据的确定性包装或叠加缓和词，保持原文的主张力度和认识论边界。",
    ),
    "interaction-invitation": (
        "LEX-STRICT-CORPUS-INVITATION-01",
        "助手式邀请和后续服务话术",
        "学术正文中直接删除助手邀请、后续服务和对话式承诺，不以同义服务话术替换。",
    ),
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_inventory_sha256(entries: list[dict[str, Any]]) -> str:
    """Bind the reviewed entry payload, independent of JSON formatting/order."""
    payload = json.dumps(
        sorted(entries, key=lambda entry: entry["phrase"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload)


def validate_inventory(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    entries = inventory.get("entries")
    if not isinstance(entries, list) or len(entries) < 1000:
        raise ValueError("inventory must contain at least 1000 entries")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        phrase = entry.get("phrase")
        category = entry.get("category")
        if not isinstance(phrase, str) or not HAN_PHRASE_RE.fullmatch(phrase):
            raise ValueError(f"entry {index} has invalid 2-12 Han phrase: {phrase!r}")
        if phrase in seen:
            raise ValueError(f"duplicate phrase: {phrase}")
        seen.add(phrase)
        if category not in CATEGORY_CONFIG:
            raise ValueError(f"entry {index} has unknown category: {category!r}")
        if int(entry.get("combined_coverage", 0)) <= 0:
            raise ValueError(f"entry {index} has no current evidence: {phrase}")
        if entry.get("evidence_scope") == "none":
            raise ValueError(f"entry {index} has evidence_scope=none: {phrase}")
    summary_count = int(
        inventory.get("summary", {}).get("selection", {}).get("strict_inventory_entries", -1)
    )
    if summary_count != len(entries):
        raise ValueError(
            f"summary count {summary_count} does not match entries {len(entries)}"
        )
    return entries


def build_strict_signals(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        grouped[entry["category"]].append(entry["phrase"])
    signals = []
    for category, (signal_id, label, rationale) in CATEGORY_CONFIG.items():
        signals.append(
            {
                "id": signal_id,
                "category": f"strict-corpus/{category}",
                "label": label,
                "variants": grouped[category],
                "regex": [],
                "scenes": ["ALL"],
                "severity": "high",
                "threshold": {
                    "min_occurrences": 1,
                    "window": "document",
                    "window_chars": 0,
                },
                "exclusions": [],
                "action": "REWRITE",
                "rationale": rationale,
                "positive_examples": [
                    "命中本组词条后保持原句不变，或只换成同类抽象词。"
                ],
                "negative_examples": [
                    "位于代码、公式、引语或其他保护区的同形文本逐字保留。"
                ],
                "provenance": [
                    {
                        "file": "references/lexical-signals.json",
                        "rule": f"strict_phrase_inventory/{category}",
                    }
                ],
            }
        )
    return signals


def install(
    inventory_path: Path,
    lexicon_path: Path,
    root_ranking_path: Path | None,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    inventory_raw = inventory_path.read_bytes()
    inventory = json.loads(inventory_raw.decode("utf-8"))
    entries = validate_inventory(inventory)
    inventory_manifest_sha256 = canonical_inventory_sha256(entries)
    if len(entries) != EXPECTED_RELEASE_INVENTORY_ENTRIES:
        raise ValueError(
            "inventory is not the reviewed release: "
            f"expected {EXPECTED_RELEASE_INVENTORY_ENTRIES} entries, got {len(entries)}"
        )
    if inventory_manifest_sha256 != EXPECTED_RELEASE_INVENTORY_SHA256:
        raise ValueError(
            "inventory is not the reviewed release: canonical manifest hash differs"
        )
    lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))
    strict_signals = build_strict_signals(entries)
    roots: list[dict[str, Any]] = []
    root_hash = None
    if root_ranking_path is not None:
        root_raw = root_ranking_path.read_bytes()
        roots = json.loads(root_raw.decode("utf-8"))
        root_hash = sha256(root_raw)

    lexicon["schema_version"] = "1.5.0"
    lexicon["strict_corpus_policy"] = {
        "schema_version": STRICT_CORPUS_POLICY_SCHEMA,
        "enabled_by_default": True,
        "inventory_entries": len(entries),
        "minimum_inventory_entries": EXPECTED_RELEASE_INVENTORY_ENTRIES,
        "enforcement": "BLOCK_CLEAN_UNLESS_REWRITTEN_OR_POSITION_KEEP",
        "no_change_allowed_with_unresolved_match": False,
        "protected_spans_are_exempt": True,
        "technical_term_exception": "POSITION_BOUND_KEEP_REASON_REQUIRED",
        "source_inventory_sha256": sha256(inventory_raw),
        "inventory_manifest_sha256": inventory_manifest_sha256,
        "scan_summary": inventory["summary"],
        "single_character_root_policy": {
            "discovery_only": True,
            "bare_single_character_bans": 0,
            "emitted_phrase_length": {"minimum": 2, "maximum": 12},
            "ranked_roots": len(roots),
            "eligible_roots": sum(
                1 for row in roots if row.get("root_status") == "eligible_root"
            ),
            "root_ranking_sha256": root_hash,
        },
        "source_kind_counts": dict(Counter(entry.get("source_kind") for entry in entries)),
        "signal_ids": [item[0] for item in CATEGORY_CONFIG.values()],
    }
    lexicon["strict_phrase_inventory"] = entries
    lexicon["signals"] = [
        signal
        for signal in lexicon["signals"]
        if not signal["id"].startswith("LEX-STRICT-CORPUS-")
    ] + strict_signals

    rendered = json.dumps(lexicon, ensure_ascii=False, indent=2) + "\n"
    if not dry_run:
        temporary = lexicon_path.with_name(lexicon_path.name + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(lexicon_path)
    return {
        "dry_run": dry_run,
        "lexicon": str(lexicon_path),
        "inventory_entries": len(entries),
        "strict_signals": len(strict_signals),
        "total_signals": len(lexicon["signals"]),
        "inventory_sha256": sha256(inventory_raw),
        "inventory_manifest_sha256": inventory_manifest_sha256,
        "rendered_lexicon_sha256": sha256(rendered.encode("utf-8")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--root-ranking", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = install(
        args.inventory, args.lexicon, args.root_ranking, dry_run=args.dry_run
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
