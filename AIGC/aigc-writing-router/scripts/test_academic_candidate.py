#!/usr/bin/env python3
"""Regression tests for the unified academic candidate release gate."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

from audit_academic_candidate import audit


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def document(body: str) -> str:
    return (
        "\\documentclass{ctexart}\n"
        "\\begin{document}\n"
        "\\section{模型建立}\n"
        f"{body}\n"
        "设状态量为 $x_t$，观测步长取 $1$ 小时。\n"
        "\\end{document}\n"
    )


def write_bridge_packet(source: Path, root: Path) -> Path:
    mcm_scripts = Path(__file__).resolve().parents[3] / "mcm-cup-standard-write" / "scripts"
    if str(mcm_scripts) not in sys.path:
        sys.path.insert(0, str(mcm_scripts))
    from prepare_style_retrieval_plan import section_target_records

    target = section_target_records(source.read_text(encoding="utf-8"))[0]
    packet_path = root / "bridge-packet.json"
    packet_path.write_text(
        json.dumps(
            {
                "schema": "mcm-section-drafting-packet/v1",
                "target": {
                    "id": "T01",
                    "title": target["title"],
                    "role": target["role"],
                    "question_id": target["question_id"],
                },
                "public_judgment_contract": {
                    "schema": "mcm-section-public-judgment-contract/v1",
                    "required": True,
                    "questions": [
                        {
                            "question_id": "1",
                            "basis_nodes": [{"id": "capacity", "terms": ["容量上限"]}],
                            "mathematical_change_nodes": [
                                {"id": "feasible", "terms": ["可行域"]}
                            ],
                            "selected_route": {
                                "id": "ip", "name": "整数规划", "terms": ["整数规划"]
                            },
                            "recorded_alternative_routes": [],
                            "local_requirements": {
                                "basis_term_required": True,
                                "mathematical_change_term_required": True,
                                "selected_route_term_required": True,
                                "minimum_basis_groups": 1,
                                "minimum_target_groups": 1,
                            },
                        }
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    index_path = root / "bridge-packet-index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema": "mcm-section-drafting-packet-index/v1",
                "status": "pass",
                "packets": [
                    {
                        "target_id": "T01",
                        "path": str(packet_path),
                        "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return index_path


def write_result_bridge_packet(source: Path, root: Path) -> Path:
    mcm_scripts = Path(__file__).resolve().parents[3] / "mcm-cup-standard-write" / "scripts"
    if str(mcm_scripts) not in sys.path:
        sys.path.insert(0, str(mcm_scripts))
    from prepare_style_retrieval_plan import section_target_records

    target = section_target_records(source.read_text(encoding="utf-8"))[0]
    packet_path = root / "result-bridge-packet.json"
    packet_path.write_text(json.dumps({
        "schema": "mcm-section-drafting-packet/v1",
        "target": {
            "id": "T01", "title": target["title"], "role": target["role"],
            "question_id": target["question_id"],
        },
        "public_judgment_contract": {
            "schema": "mcm-section-public-judgment-contract/v1",
            "required": True,
            "questions": [{
                "question_id": "1",
                "result_interpretations": [{
                    "id": "capacity-active", "kind": "active_constraint",
                    "observation_terms": ["总成本最低"],
                    "explanation_terms": ["容量约束"],
                    "source_ids": ["result"], "source_ref": "results/summary.csv:3",
                }],
                "actual_checks": [],
                "local_requirements": {
                    "result_interpretation_required": True,
                    "validation_conclusion_required": False,
                    "model_comparison_guard": False,
                },
            }],
        },
    }, ensure_ascii=False), encoding="utf-8")
    index_path = root / "result-bridge-packet-index.json"
    index_path.write_text(json.dumps({
        "schema": "mcm-section-drafting-packet-index/v1",
        "status": "pass",
        "packets": [{
            "target_id": "T01", "path": str(packet_path),
            "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return index_path


def run_humanize_keep(source: Path, candidate: Path, output_root: Path) -> Path:
    humanize_root = Path(__file__).resolve().parents[1].parent / "humanize-academic-chinese"
    scanner = humanize_root / "scripts" / "scan_humanize_chinese.py"
    scanned = subprocess.run(
        [sys.executable, str(scanner), str(candidate), "--scene", "MODELING", "--format", "json"],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        timeout=120, check=False,
    )
    require(scanned.returncode in {0, 2}, "strict fixture scan failed", scanned.stderr)
    scan_payload = json.loads(scanned.stdout)
    finding = next(
        item for item in scan_payload.get("findings", [])
        if item.get("candidate")
        and item.get("signal_id") == "LEX-STRICT-CORPUS-CERTAINTY-01"
        and item.get("matched") == "不能稳定"
    )
    binding = f"{finding['signal_id']}@{finding['line']}:{finding['column']}"
    runner = humanize_root / "scripts" / "run_humanize_inline.py"
    completed = subprocess.run(
        [
            sys.executable, str(runner), "run", str(source), str(candidate),
            "--output-root", str(output_root), "--mode", "REWRITE",
            "--scene", "MODELING", "--document-format", "tex",
            "--visible-output", "BODY_ONLY", "--keep-reason",
            binding + "=描述偏离均衡条件后的技术稳定性结论，否定强度不可削弱",
        ],
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        timeout=300, check=False,
    )
    require(completed.returncode == 2, "Humanize KEEP fixture did not await paired review", {
        "returncode": completed.returncode, "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    })
    payload = json.loads(completed.stdout)
    require(
        payload.get("mechanical_validation_status") == "PASS",
        "Humanize KEEP fixture failed mechanical validation", payload,
    )
    return Path(payload["run_dir"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-academic-gate-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        clean = root / "clean.tex"
        source.write_text(
            document("原始记录按小时保存流量。曲线在第六个时段出现折点，邻近测点没有同步变化。"),
            encoding="utf-8",
        )
        clean.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        clean_report = audit(source, clean)
        require(clean_report["status"] == "pass", "clean protected candidate did not pass", clean_report)
        require(
            {item["id"] for item in clean_report["gates"] if item["required"]}
            == {"humanize-lexical", "protected-rewrite-contract", "section-voice", "paragraph-rhythm", "public-reasoning-scaffold"},
            "a required component was not executed",
            clean_report,
        )
        require(len(clean_report["dependencies"]) == 10, "dependency inventory is incomplete", clean_report)
        require(
            clean_report["recovery"]["route"] == "READY_FOR_HUMAN_REVIEW",
            "clean candidate did not enter human review",
            clean_report,
        )

        no_gain_report = audit(source, clean, require_style_gain=True)
        no_gain_gate = next(item for item in no_gain_report["gates"] if item["id"] == "style-gain")
        require(
            no_gain_report["status"] == "review"
            and no_gain_report["style_intent"] == "require-gain"
            and no_gain_gate["required"]
            and no_gain_gate["status"] == "review",
            "a byte-identical candidate passed a release that requires a measured style gain",
            no_gain_report,
        )

        gain_source = root / "gain-source.tex"
        gain_candidate = root / "gain-candidate.tex"
        gain_source.write_text(
            document("这里讨论的不是采样误差，而是边界误差。"),
            encoding="utf-8",
        )
        gain_candidate.write_text(
            document("这里讨论边界误差，采样误差不在本问范围内。"),
            encoding="utf-8",
        )
        gain_report = audit(gain_source, gain_candidate, require_style_gain=True)
        gain_gate = next(item for item in gain_report["gates"] if item["id"] == "style-gain")
        require(
            gain_report["status"] == "pass"
            and gain_gate["status"] == "pass"
            and any(item["metric"] == "rhythm_findings" for item in gain_gate["improvements"]),
            "a safe removal of a contrast-correction shell did not satisfy the style-gain release gate",
            gain_report,
        )

        bridge_source = root / "bridge-source.tex"
        bridge_candidate = root / "bridge-candidate.tex"
        bridge_source.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一模型建立}\n"
            "直接采用整数规划求解，随后才说明容量上限和可行域。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        bridge_candidate.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一模型建立}\n"
            "题面的容量上限写入可行域，先说明这一关系，再用整数规划处理离散选择。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        bridge_index = write_bridge_packet(bridge_source, root)
        bridge_report = audit(
            bridge_source, bridge_candidate,
            require_style_gain=True, packet_index_path=bridge_index,
        )
        bridge_gain = next(item for item in bridge_report["gates"] if item["id"] == "style-gain")
        bridge_gate = next(
            item for item in bridge_report["gates"]
            if item["id"] == "source-bound-judgment-bridge"
        )
        require(
            bridge_report["status"] == "pass"
            and bridge_gate["status"] == "pass"
            and bridge_gain["status"] == "pass"
            and any(
                item["code"] == "SECTION_BRIDGE_ORDER_INVALID"
                for item in bridge_gain["source_bound_improvements"]
            ),
            "a packet-bound repair of a direct model jump did not satisfy the style-gain gate",
            bridge_report,
        )
        uncorrected_bridge = audit(
            bridge_source, bridge_source,
            require_style_gain=True, packet_index_path=bridge_index,
        )
        uncorrected_gate = next(
            item for item in uncorrected_bridge["gates"]
            if item["id"] == "source-bound-judgment-bridge"
        )
        require(
            uncorrected_bridge["status"] == "fail"
            and uncorrected_gate["status"] == "fail",
            "an unchanged direct model jump passed by merely attaching a packet index",
            uncorrected_bridge,
        )

        result_source = root / "result-source.tex"
        result_candidate = root / "result-candidate.tex"
        result_source.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一结果分析}\n总成本最低出现在方案三。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        result_candidate.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n"
            "\\section{问题一结果分析}\n"
            "总成本最低出现在方案三，容量约束在该方案取到上界。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        result_index = write_result_bridge_packet(result_source, root)
        result_report = audit(
            result_source, result_candidate,
            require_style_gain=True, packet_index_path=result_index,
        )
        result_gain = next(item for item in result_report["gates"] if item["id"] == "style-gain")
        require(
            result_report["status"] == "pass"
            and any(
                item["code"] == "SECTION_BRIDGE_RESULT_EXPLANATION_MISSING"
                for item in result_gain["source_bound_improvements"]
            ),
            "a packet-bound result explanation did not count as a source-grounded content gain",
            result_report,
        )

        attested_source = root / "attested-source.tex"
        attested_candidate = root / "attested-candidate.tex"
        attested_source.write_text(
            document("可视化结果保留了第六时段的折点，便于比较相邻测点。"),
            encoding="utf-8",
        )
        attested_candidate.write_text(attested_source.read_text(encoding="utf-8"), encoding="utf-8")
        attested_report = audit(attested_source, attested_candidate)
        attested_lexical = next(item for item in attested_report["gates"] if item["id"] == "humanize-lexical")
        require(
            attested_report["status"] == "pass"
            and attested_lexical["human_corpus_calibration"]["papers"] == 59
            and attested_lexical["human_corpus_calibration"]["contextual_findings"] >= 1,
            "a widely human-attested CUMCM phrase remained a one-hit hard blocker",
            attested_report,
        )

        inherited_source = root / "inherited-source.tex"
        inherited_candidate = root / "inherited-candidate.tex"
        inherited_source.write_text(
            document("若混合策略偏离均衡条件，原有概率组合就不能稳定存在；该结论只针对当前策略集。"),
            encoding="utf-8",
        )
        inherited_candidate.write_text(
            document("若混合策略偏离均衡条件，原有概率组合就不能稳定存在。该结论只针对当前策略集。"),
            encoding="utf-8",
        )
        inherited_without_run = audit(inherited_source, inherited_candidate)
        require(
            inherited_without_run["status"] == "review",
            "an unexplained inherited strict phrase bypassed the unified gate",
            inherited_without_run,
        )
        inherited_run = run_humanize_keep(
            inherited_source, inherited_candidate, root / "humanize-keep-runs"
        )
        inherited_with_run = audit(
            inherited_source, inherited_candidate, humanize_run_path=inherited_run
        )
        inherited_lexical = next(
            item for item in inherited_with_run["gates"] if item["id"] == "humanize-lexical"
        )
        require(
            inherited_with_run["status"] == "pass"
            and inherited_lexical["kept_by_replayed_humanize_run"] == 1
            and inherited_lexical["humanize_run_keep_evidence"]["status"] == "pass",
            "a replayed source-inherited technical KEEP did not reach the unified gate",
            inherited_with_run,
        )
        inherited_drift = root / "inherited-drift.tex"
        inherited_drift.write_text(
            inherited_candidate.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        drifted_keep_report = audit(
            inherited_source, inherited_drift, humanize_run_path=inherited_run
        )
        drifted_keep_lexical = next(
            item for item in drifted_keep_report["gates"] if item["id"] == "humanize-lexical"
        )
        require(
            drifted_keep_report["status"] == "review"
            and drifted_keep_lexical["kept_by_replayed_humanize_run"] == 0
            and any(
                item["code"] == "HUMANIZE_RUN_CANDIDATE_HASH_MISMATCH"
                for item in drifted_keep_lexical["humanize_run_keep_evidence"]["errors"]
            ),
            "a Humanize KEEP run was replayed against a different candidate",
            drifted_keep_report,
        )

        contrast = root / "contrast.tex"
        contrast.write_text(
            document("这里讨论的不是采样误差，而是边界误差。曲线在第六个时段出现折点。"),
            encoding="utf-8",
        )
        contrast_report = audit(source, contrast)
        lexical = next(item for item in contrast_report["gates"] if item["id"] == "humanize-lexical")
        require(
            contrast_report["status"] != "pass"
            and lexical["unresolved_findings"] >= 1
            and "LEX-CONTRAST-01" in lexical["signal_counts"],
            "one contrast-correction shell was not blocked",
            contrast_report,
        )
        require(
            contrast_report["recovery"]["route"]
            in {"LOCAL_REPAIR_ON_CURRENT_CANDIDATE", "SEMANTIC_REVIEW_ON_CURRENT_CANDIDATE"}
            and contrast_report["recovery"]["current_candidate_repair_allowed"],
            "non-drifting lexical finding did not stay on the current candidate",
            contrast_report,
        )

        warning_source = root / "warning-source.tex"
        warning_candidate = root / "warning-candidate.tex"
        warning_source.write_text(
            document("边界变化导致局部波动，当前资料不足以作因果外推。"),
            encoding="utf-8",
        )
        warning_candidate.write_text(
            document("局部波动由边界变化引起，当前资料不足以作因果外推。"),
            encoding="utf-8",
        )
        warning_report = audit(warning_source, warning_candidate)
        warning_contract = next(
            item for item in warning_report["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            warning_report["status"] == "review"
            and len(warning_contract["unresolved_warnings"]) == 1,
            "unreviewed semantic marker change was not held for review",
            warning_report,
        )
        finding = warning_contract["unresolved_warnings"][0]
        decisions = root / "semantic-decisions.json"
        decisions.write_text(
            json.dumps(
                {
                    "schema": "aigc-academic-style-decisions/v1",
                    "source_tree_sha256": warning_report["source"]["tree_sha256"],
                    "candidate_tree_sha256": warning_report["candidate"]["tree_sha256"],
                    "decisions": [],
                    "semantic_decisions": [
                        {
                            "code": finding["code"],
                            "finding_sha256": finding["finding_sha256"],
                            "decision": "accept",
                            "reason": "两句保留同一条件性因果方向，仅替换因果动词。",
                            "reviewer": "test-reviewer",
                            "reviewer_kind": "human",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        adjudicated = audit(warning_source, warning_candidate, decisions_path=decisions)
        adjudicated_contract = next(
            item for item in adjudicated["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            adjudicated["status"] == "pass"
            and len(adjudicated_contract["adjudicated_warnings"]) == 1
            and not adjudicated_contract["unresolved_warnings"],
            "hash-bound semantic adjudication did not clear a warning-only candidate",
            adjudicated,
        )
        model_decisions_payload = json.loads(decisions.read_text(encoding="utf-8"))
        model_decisions_payload["semantic_decisions"][0]["reviewer_kind"] = "model"
        model_decisions = root / "model-semantic-decisions.json"
        model_decisions.write_text(
            json.dumps(model_decisions_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        model_adjudicated = audit(warning_source, warning_candidate, decisions_path=model_decisions)
        model_contract = next(
            item for item in model_adjudicated["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            model_adjudicated["status"] == "review"
            and any(
                item["code"] == "SEMANTIC_DECISION_REQUIRES_HUMAN_REVIEW"
                for item in model_contract["semantic_decision_errors"]
            ),
            "model self-review was allowed to clear a semantic warning",
            model_adjudicated,
        )

        chain_source = root / "chain-source.tex"
        chain_candidate = root / "chain-candidate.tex"
        chain_source.write_text(
            "\\section{问题分析}\n"
            "观测记录表明两类数据的尺度不同，因此用全流域数据约束总量，并把局部记录保留为波动项。"
            "该变化使同一参数不必同时承担两种职责，随后选择分层模型进行标定。"
            "结果仅在当前记录范围内用于比较，不能外推为无条件结论。\n",
            encoding="utf-8",
        )
        chain_candidate.write_text(
            "\\section{问题分析}\n"
            "两类数据用于分层模型标定和结果比较，结论适用于当前记录范围。\n",
            encoding="utf-8",
        )
        chain_report = audit(chain_source, chain_candidate, scene="MODELING")
        chain_contract = next(
            item for item in chain_report["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            chain_report["status"] == "review"
            and any(
                item["code"] == "MODELING_JUDGMENT_CHAIN_LOSS"
                for item in chain_contract["unresolved_warnings"]
            ),
            "modeling judgment-chain loss did not reach the unified release gate",
            chain_report,
        )

        multi_source = root / "multi-source"
        multi_candidate = root / "multi-candidate"
        multi_source.mkdir()
        multi_candidate.mkdir()
        for directory in (multi_source, multi_candidate):
            (directory / "main.tex").write_text(
                "\\documentclass{ctexart}\n\\begin{document}\n\\input{q1}\n\\end{document}\n",
                encoding="utf-8",
            )
            (directory / "q1.tex").write_text(
                "\\section{问题分析}\n这里讨论的不是采样误差，而是边界误差。该区分来自题面给出的观测位置。\n",
                encoding="utf-8",
            )
        multi_report = audit(multi_source / "main.tex", multi_candidate / "main.tex")
        rhythm_gate = next(item for item in multi_report["gates"] if item["id"] == "paragraph-rhythm")
        shell = next(item for item in rhythm_gate["findings"] if item["code"] == "CONTRAST_CORRECTION_SHELL")
        require(
            shell.get("relative_path") == "q1.tex"
            and shell.get("actual_line") == 2
            and shell.get("combined_line", 0) > shell.get("actual_line", 0),
            "combined TeX finding was not mapped back to its actual include file",
            shell,
        )

        repeated = root / "repeated.tex"
        repeated_body = "".join(
            f"\\section{{问题{index}}}\n"
            "题面数据呈现明显变化，需要先说明观测依据。\n\n"
            "基线方法存在不足，无法解释容量约束带来的变化。\n\n"
            "比较候选方案后保留适合本问的路线，并说明舍弃原因。\n\n"
            "建立回归模型，写出目标函数和约束条件。\n\n"
            "采用迭代算法求解，按停止条件更新变量。\n\n"
            "得到结果后进行误差检验，检查约束是否满足。\n"
            for index in ("一", "二", "三")
        )
        repeated.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n" + repeated_body + "\\end{document}\n",
            encoding="utf-8",
        )
        repeated_report = audit(repeated, repeated)
        scaffold_gate = next(
            item for item in repeated_report["gates"] if item["id"] == "public-reasoning-scaffold"
        )
        require(
            repeated_report["status"] == "review"
            and any(item["code"] == "REPEATED_REASONING_SCAFFOLD" for item in scaffold_gate["findings"]),
            "repeated public reasoning scaffold did not reach the unified release gate",
            repeated_report,
        )

        number_drift = root / "number-drift.tex"
        number_drift.write_text(
            source.read_text(encoding="utf-8").replace("$1$", "$2$"),
            encoding="utf-8",
        )
        drift_report = audit(source, number_drift)
        contract = next(
            item for item in drift_report["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            drift_report["status"] == "fail"
            and any(item["code"] in {"MATH_CHANGED", "NUMBER_CHANGED"} for item in contract["findings"]),
            "protected numeric drift was not blocked",
            drift_report,
        )
        require(
            drift_report["recovery"]["route"] == "REBASE_FROM_FROZEN_SOURCE"
            and not drift_report["recovery"]["current_candidate_repair_allowed"]
            and not drift_report["recovery"]["lexical_findings_actionable_now"],
            "protected drift did not suppress unsafe lexical repair",
            drift_report,
        )

        hard_decisions = root / "hard-decisions.json"
        hard_decisions.write_text(
            json.dumps(
                {
                    "schema": "aigc-academic-style-decisions/v1",
                    "source_tree_sha256": drift_report["source"]["tree_sha256"],
                    "candidate_tree_sha256": drift_report["candidate"]["tree_sha256"],
                    "decisions": [],
                    "semantic_decisions": [
                        {
                            "code": "MATH_CHANGED",
                            "finding_sha256": "0" * 64,
                            "decision": "accept",
                            "reason": "该记录故意尝试豁免数学硬错误，测试必须拒绝。",
                            "reviewer": "test-reviewer",
                            "reviewer_kind": "human",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        hard_report = audit(source, number_drift, decisions_path=hard_decisions)
        hard_contract = next(
            item for item in hard_report["gates"] if item["id"] == "protected-rewrite-contract"
        )
        require(
            hard_report["status"] == "fail"
            and any(
                item["code"] == "SEMANTIC_DECISION_TARGET_NOT_WARNING"
                for item in hard_contract["semantic_decision_errors"]
            ),
            "a semantic decision was allowed to waive a hard protected-content error",
            hard_report,
        )

    print("PASS: the unified gate executes every component and blocks lexical and protected-content regressions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
