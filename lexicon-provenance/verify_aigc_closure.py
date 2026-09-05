#!/usr/bin/env python3
"""AIGC 栈闭环校验：三处入口、技能可发现性、规则快照、发布绑定与来源链。

用法：
    python lexicon-provenance/verify_aigc_closure.py [--format text|json]

只读。不修改任何文件，不产生检测分数，不判断作者身份。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

TRUTH = Path(r"F:\CUMCM")
AIGC = TRUTH / "AIGC"
ROUTER = AIGC / "aigc-writing-router"
HAC = AIGC / "humanize-academic-chinese"
LEXICON = HAC / "references" / "lexical-signals.json"
SCANNER = HAC / "scripts" / "scan_humanize_chinese.py"
PROV = TRUTH / "lexicon-provenance" / "provenance-manifest.json"

ROOTS = {
    "f:\\CUMCM (truth)": AIGC,
    "~/.codex/skills/AIGC": Path.home() / ".codex" / "skills" / "AIGC",
    "~/.claude/skills (flat)": Path.home() / ".claude" / "skills",
}

# 期望在两个 harness 中都能按名字发现的技能 -> SKILL.md 的 name 字段
EXPECTED_SKILLS = {
    "aigc-writing-router": "aigc-writing-router",
    "humanize-academic-chinese": "humanize-academic-chinese",
    "baibaiAIGC": "baibai-aigc",
    "academic-humanizer": "academic-humanizer",
    "patina": "patina",
    "humanizer": "humanizer",
    "humanizer-zh": "humanizer-zh",
    "humanizer-medical-academic": "humanizer-medical-academic",
    "humanizer-brandonwise": "humanizer-brandonwise",
    "humanize-chinese-copy-lab": "humanize-chinese-copy-lab",
    "humanize-tiany-candidate-lab": "humanize-tiany-candidate-lab",
    "ai-check": "ai-check",
    "humanize-english-editor": "humanize-english-editor",
    "humanizer-voice-profile": "humanizer-voice-profile",
    "mcm-cup-standard-write": "mcm-cup-standard-write",
    "deai-academic-writing": "deai-academic-writing",
    "deai-modeling-writing": "deai-modeling-writing",
    "deai-research-writing": "deai-research-writing",
    "deai-course-notes": "deai-course-notes",
    "math-modeling-skill": "math-modeling-skill",
}
RETIRED = "aigc-down-skill"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def skill_name(skill_md: Path) -> str | None:
    try:
        text = skill_md.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    match = re.search(r"^name:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def check_roots(findings: list[dict]) -> None:
    """三处入口必须解析到同一真源，且词库逐位相同。"""
    hashes = {}
    for label, root in ROOTS.items():
        lexicon = root / "humanize-academic-chinese" / "references" / "lexical-signals.json"
        if not lexicon.is_file():
            findings.append({"check": "roots", "status": "fail", "root": label,
                             "detail": f"词库不可达: {lexicon}"})
            continue
        hashes[label] = (sha256(lexicon), str(lexicon.resolve()))
    if len(hashes) != len(ROOTS):
        return
    distinct_hash = {h for h, _ in hashes.values()}
    distinct_real = {r for _, r in hashes.values()}
    findings.append({
        "check": "roots", "status": "pass" if len(distinct_hash) == 1 else "fail",
        "detail": f"{len(ROOTS)} 处入口，词库哈希 {len(distinct_hash)} 种，解析真路径 {len(distinct_real)} 种",
        "sha256": sorted(distinct_hash)[0][:16],
        "resolved": sorted(distinct_real)[0],
    })


def check_discovery(findings: list[dict]) -> None:
    """两个 harness 都要能按名字发现同一批技能，且退休技能清零。"""
    for label, base in (("~/.claude/skills", Path.home() / ".claude" / "skills"),
                        ("~/.codex/skills", Path.home() / ".codex" / "skills")):
        missing, mismatched = [], []
        for directory, expected in EXPECTED_SKILLS.items():
            candidates = [base / directory, base / "AIGC" / directory]
            found = next((c for c in candidates if (c / "SKILL.md").is_file()), None)
            if found is None:
                missing.append(directory)
                continue
            actual = skill_name(found / "SKILL.md")
            if actual != expected:
                mismatched.append(f"{directory}:{actual}")
        retired_present = (base / RETIRED).exists()
        ok = not missing and not mismatched and not retired_present
        findings.append({
            "check": "discovery", "status": "pass" if ok else "fail", "root": label,
            "detail": f"{len(EXPECTED_SKILLS) - len(missing)}/{len(EXPECTED_SKILLS)} 可发现"
                      f"；名字不符 {len(mismatched)}；退休技能 {RETIRED} "
                      f"{'仍在' if retired_present else '已清零'}",
            "missing": missing, "mismatched": mismatched,
        })


def check_rule_snapshot(findings: list[dict]) -> None:
    """run_style_benchmark 的写作规则快照必须逐项可解析。"""
    scripts = ROUTER / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("_rsb", scripts / "run_style_benchmark.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        paths = [Path(p) for p in module._writing_rule_paths()]
        missing = [str(p) for p in paths if not p.exists()]
        findings.append({
            "check": "rule-snapshot", "status": "pass" if not missing else "fail",
            "detail": f"{len(paths) - len(missing)}/{len(paths)} 规则文件可解析",
            "missing": missing[:10],
        })
    except Exception as exc:  # noqa: BLE001 - 报告而不是中断整轮校验
        findings.append({"check": "rule-snapshot", "status": "fail", "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        sys.path.remove(str(scripts))


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def check_role_contracts(findings: list[dict]) -> None:
    code, out = _run([sys.executable, "scripts/audit_role_contracts.py", "--format", "text"], ROUTER)
    ok = code == 0 and "PASS" in out
    findings.append({"check": "role-contracts", "status": "pass" if ok else "fail",
                     "detail": out.strip().splitlines()[-1] if out.strip() else f"exit {code}"})


def check_mcm_route(findings: list[dict]) -> None:
    """mcm 场景必须拿到完整责任链：3 个内容负责人 + 主编辑 + 复核 + 工作台。"""
    code, out = _run([sys.executable, "scripts/route_aigc_tools.py", "--document-type", "mcm",
                      "--intent", "draft", "--document-format", "tex", "--scope", "document",
                      "--format", "json"], ROUTER)
    required = {"deai-academic-writing", "mcm-cup-standard-write", "deai-modeling-writing",
                "humanize-academic-chinese", "ai-check", "AI_paper"}
    try:
        plan = json.loads(out)
        providers = {str(stage.get("provider")) for stage in plan.get("stages", [])}
        gates = plan.get("final_gates", [])
        absent = sorted(required - providers)
        ok = code == 0 and not absent and plan.get("status") == "pass"
        findings.append({"check": "mcm-route", "status": "pass" if ok else "fail",
                         "detail": f"{len(providers)} 个阶段负责人，{len(gates)} 道终门"
                                   f"{'；缺 ' + ', '.join(absent) if absent else ''}"})
    except Exception as exc:  # noqa: BLE001
        findings.append({"check": "mcm-route", "status": "fail", "detail": f"{type(exc).__name__}: {exc}"})


def check_release_binding(findings: list[dict]) -> None:
    """词库条数、清单哈希与扫描器里的 release 常量必须三者互锁。"""
    data = json.loads(LEXICON.read_text(encoding="utf-8"))
    inventory = data["strict_phrase_inventory"]
    policy = data["strict_corpus_policy"]
    payload = json.dumps(sorted(inventory, key=lambda e: e["phrase"]), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    recomputed = hashlib.sha256(payload).hexdigest()
    source = SCANNER.read_text(encoding="utf-8")
    pinned_n = re.search(r"EXPECTED_STRICT_INVENTORY_ENTRIES = (\d+)", source)
    pinned_h = re.search(r'EXPECTED_STRICT_INVENTORY_SHA256 = \(\s*"([0-9a-f]{64})"', source)
    variants = {v for signal in data["signals"] if signal["id"].startswith("LEX-STRICT-CORPUS-")
                for v in signal.get("variants", [])}
    problems = []
    if policy["inventory_entries"] != len(inventory):
        problems.append("inventory_entries 与实际条数不符")
    if policy["minimum_inventory_entries"] != len(inventory):
        problems.append("minimum_inventory_entries 与实际条数不符")
    if policy["inventory_manifest_sha256"] != recomputed:
        problems.append("清单哈希与重算不符")
    if not pinned_n or int(pinned_n.group(1)) != len(inventory):
        problems.append("扫描器 ENTRIES 常量不符")
    if not pinned_h or pinned_h.group(1) != recomputed:
        problems.append("扫描器 SHA256 常量不符")
    if variants != {e["phrase"] for e in inventory}:
        problems.append("strict signal variants 与词条集合不一致")
    findings.append({"check": "release-binding", "status": "pass" if not problems else "fail",
                     "detail": f"{len(inventory)} 条，manifest {recomputed[:16]}"
                               f"{'；' + '；'.join(problems) if problems else ''}"})


def check_provenance(findings: list[dict]) -> None:
    """来源链：挖掘器、候选语料与被引用的 Section B 证据都要能对上记录的哈希。"""
    manifest = json.loads(PROV.read_text(encoding="utf-8"))
    problems, checked = [], 0

    expander = TRUTH / "lexicon-provenance" / "toolchain" / "scripts" / "expand_humanize_strict_lexicon.py"
    recorded = manifest["toolchain"]["expander"]["recorded_expander_sha256"]
    if not expander.is_file():
        problems.append("挖掘器缺失")
    elif sha256(expander) != recorded:
        problems.append("挖掘器哈希与词库记录不符")
    else:
        checked += 1

    corpus = Path(manifest["candidate_corpus"]["root"])
    main_csv = corpus / manifest["candidate_corpus"]["main_csv"]["name"]
    if not main_csv.is_file():
        problems.append(f"候选语料不可达: {main_csv}")
    else:
        checked += 1  # 1.34GB，默认不重算哈希，仅确认可达

    section_b = manifest.get("section_b_cet6_evidence", {})
    for item in section_b.get("cited_artifacts", []):
        target = TRUTH / item["path"]
        if not target.is_file():
            problems.append(f"被引证据缺失: {item['path']}")
        elif sha256(target).upper() != item["sha256"].upper():
            problems.append(f"被引证据哈希不符: {item['path']}")
        else:
            checked += 1

    findings.append({"check": "provenance", "status": "pass" if not problems else "fail",
                     "detail": f"{checked} 项来源可对账"
                               f"{'；' + '；'.join(problems) if problems else ''}"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    findings: list[dict] = []
    check_roots(findings)
    check_discovery(findings)
    check_rule_snapshot(findings)
    check_role_contracts(findings)
    check_mcm_route(findings)
    check_release_binding(findings)
    check_provenance(findings)

    failed = [f for f in findings if f["status"] != "pass"]
    report = {
        "schema": "aigc-closure-verification/v1",
        "status": "pass" if not failed else "fail",
        "truth_root": str(TRUTH),
        "checks": len(findings),
        "failed": len(failed),
        "findings": findings,
        "disclaimer": "本校验只确认文件、责任链与哈希绑定闭合；不构成文风质量、"
                      "检测器表现或人类作者身份结论。",
    }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"AIGC CLOSURE {report['status'].upper()}  checks={report['checks']} failed={report['failed']}")
        for item in findings:
            mark = "OK  " if item["status"] == "pass" else "FAIL"
            root = f" [{item['root']}]" if item.get("root") else ""
            print(f"  {mark} {item['check']}{root}: {item['detail']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())


