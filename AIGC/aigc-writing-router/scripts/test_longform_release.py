#!/usr/bin/env python3
"""Positive and negative tests for the MCM long-form release state machine."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile

import audit_academic_candidate as academic_candidate
from blind_pair_evaluation import prepare as prepare_blind, score as score_blind
from merge_style_benchmark_ratings import merge_ratings

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mcm-cup-standard-write" / "scripts"))

from run_longform_portfolio import (
    RENDER_CHECKS,
    _default_executor,
    audit_manifest,
    finalize_release,
    initialise,
    lock_generation_inputs,
    register_candidate,
    run_release_gates,
    select_target,
)
from prepare_style_retrieval_plan import build_plan


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def expect_value_error(action, message: str) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError(message)


def executor(failing_gate: str | None = None, compile_log: str = ""):
    def run(command: list[str], cwd: Path, gate_id: str, run_dir: Path) -> dict:
        del cwd, run_dir
        if gate_id == "compile":
            outdir = Path(next(item.split("=", 1)[1] for item in command if item.startswith("-outdir=")))
            outdir.mkdir(parents=True, exist_ok=True)
            target = Path(command[-1])
            (outdir / f"{target.stem}.pdf").write_bytes(b"%PDF-1.4\n% release fixture\n")
            (outdir / f"{target.stem}.aux").write_text(
                "\\newlabel{mcm-body-start}{{}{1}}\n\\newlabel{mcm-body-end}{{}{25}}\n",
                encoding="utf-8",
            )
            (outdir / f"{target.stem}.log").write_text(compile_log, encoding="utf-8")
            return {"returncode": 0, "stdout": "fixture compile passed", "stderr": ""}
        status = "fail" if gate_id == failing_gate else "pass"
        payload = {"status": status}
        if gate_id == "academic-style-release" and status == "pass":
            payload["dependencies"] = [
                academic_candidate._dependency(path, role)
                for path, role in (
                    (academic_candidate.LEXICAL_SCANNER, "humanize-lexical-scanner"),
                    (academic_candidate.LEXICAL_SIGNALS, "humanize-lexical-signals"),
                    (academic_candidate.REWRITE_CONTRACT, "protected-rewrite-contract"),
                    (academic_candidate.VOICE_AUDIT, "section-voice-audit"),
                    (academic_candidate.RHYTHM_AUDIT, "paragraph-rhythm-audit"),
                    (academic_candidate.STYLE_COMPARISON, "relative-style-comparison"),
                )
            ]
        return {
            "returncode": 1 if status == "fail" else 0,
            "stdout": json.dumps(payload),
            "stderr": "intentional failure" if status == "fail" else "",
        }
    return run


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    with tempfile.TemporaryDirectory(prefix="aigc-longform-release-") as temp:
        root = Path(temp)
        source_dir = root / "source"
        source_dir.mkdir()
        source = source_dir / "main.tex"
        source.write_text(
            "\\documentclass{ctexart}\n\\usepackage{graphicx}\n\\begin{document}\n"
            "\\includegraphics{figure.png}\n"
            "% \\includegraphics{commented-missing.png}\n"
            "\\section{问题分析}\n目标为最小化总成本。\n"
            "\\label{mcm-body-start}\n\\section{模型建立}\n令 $x=3.2$。\n"
            "\\label{mcm-body-end}\n\\end{document}\n",
            encoding="utf-8",
        )
        source_figure = source_dir / "figure.png"
        source_figure.write_bytes(b"fixture image resource")
        manifest_path, _ = initialise(source, root / "ledger", "mcm", "A", registry)
        inputs = {}
        for name in ("workbench", "preflight"):
            path = root / f"{name}.json"
            path.write_text(json.dumps({"fixture": name}), encoding="utf-8")
            inputs[name] = path
        inputs["style-retrieval"] = root / "style-retrieval-plan.json"
        inputs["style-retrieval"].write_text(
            json.dumps(build_plan(source, "A", minimum=3, limit=3, context_window=1), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        inputs["authoring-brief"] = root / "section-authoring-brief.json"
        inputs["authoring-brief"].write_text(json.dumps({"fixture": "section-authoring-brief"}), encoding="utf-8")
        inputs["drafting-packets"] = root / "packet-index.json"
        inputs["drafting-packets"].write_text(json.dumps({"fixture": "section-drafting-packets"}), encoding="utf-8")
        locked_path, locked_manifest, generation_lock = lock_generation_inputs(
            manifest_path, inputs["workbench"], inputs["preflight"],
            inputs["style-retrieval"], inputs["authoring-brief"],
            inputs["drafting-packets"], executor=executor(),
        )
        require(generation_lock["status"] == "pass", "fixture generation lock failed", generation_lock)
        generation_workbench_gate = next(
            item for item in generation_lock["gates"] if item["id"] == "modeling-workbench"
        )
        require(
            "--phase" in generation_workbench_gate.get("command", [])
            and "preflight" in generation_workbench_gate.get("command", [])
            and "release" not in generation_workbench_gate.get("command", []),
            "the generation lock required release-state prose before drafting",
            generation_workbench_gate,
        )
        require(locked_manifest["state"] == "GENERATION_INPUTS_LOCKED", "fixture generation state is wrong", locked_manifest)
        candidate_dir = root / "candidate"
        candidate_dir.mkdir()
        candidate = candidate_dir / "main.tex"
        candidate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        candidate_figure = candidate_dir / "figure.png"
        candidate_figure.write_bytes(source_figure.read_bytes())
        registered_path, _, verification = register_candidate(
            locked_path, candidate, "humanize-academic-chinese", "H1",
        )
        require(verification["status"] == "pass", "fixture candidate did not pass", verification)

        selected_path, selected = select_target(
            registered_path, "H1", "队长", "保留限定条件，段落衔接更清楚。",
        )
        require(selected["state"] == "HUMAN_SELECTED", "selection state did not advance", selected)
        require(audit_manifest(selected_path)["status"] == "pass", "selected manifest failed audit", selected)
        require(
            any(
                item["relative_path"] == "figure.png"
                for item in selected["selection"]["compile_resource_files"]
            ),
            "selection did not lock the local graphic resource", selected["selection"],
        )
        frozen_candidate_figure = candidate_figure.read_bytes()
        candidate_figure.write_bytes(frozen_candidate_figure + b"\n")
        selected_resource_drift = audit_manifest(selected_path)
        require(
            selected_resource_drift["status"] == "fail"
            and any(
                item["code"] == "SELECTED_COMPILE_RESOURCE_DRIFT"
                for item in selected_resource_drift["findings"]
            ),
            "compile resource drift between selection and gates was not detected",
            selected_resource_drift,
        )
        candidate_figure.write_bytes(frozen_candidate_figure)

        for name in ("coverage", "math", "repro", "results", "reasoning-review", "judgment-ledger", "evidence-bundle", "portfolio"):
            path = root / f"{name}.json"
            path.write_text(json.dumps({"fixture": name}), encoding="utf-8")
            inputs[name] = path
        inputs["drafting-usage"] = root / "section-drafting-usage.json"
        inputs["drafting-usage"].write_text(json.dumps({"fixture": "section-drafting-usage"}), encoding="utf-8")
        missing_ledger = root / "missing-judgment-ledger.json"
        try:
            run_release_gates(
                selected_path, root / "missing-ledger-run", inputs["coverage"], inputs["math"],
                inputs["repro"], inputs["results"], inputs["workbench"], inputs["preflight"],
                inputs["reasoning-review"], inputs["evidence-bundle"], inputs["portfolio"],
                style_retrieval_plan=inputs["style-retrieval"],
                authoring_brief=inputs["authoring-brief"], judgment_ledger=missing_ledger,
                drafting_packet_index=inputs["drafting-packets"],
                drafting_usage=inputs["drafting-usage"],
                executor=executor(),
            )
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing public judgment ledger was accepted")
        alternate_preflight = root / "alternate-preflight.json"
        alternate_preflight.write_text(json.dumps({"fixture": "alternate-preflight"}), encoding="utf-8")
        expect_value_error(
            lambda: run_release_gates(
                selected_path, root / "mismatched-generation-input-run",
                inputs["coverage"], inputs["math"], inputs["repro"], inputs["results"],
                inputs["workbench"], alternate_preflight, inputs["reasoning-review"],
                inputs["evidence-bundle"], inputs["portfolio"],
                style_retrieval_plan=inputs["style-retrieval"],
                authoring_brief=inputs["authoring-brief"],
                judgment_ledger=inputs["judgment-ledger"],
                drafting_packet_index=inputs["drafting-packets"],
                drafting_usage=inputs["drafting-usage"], executor=executor(),
            ),
            "release accepted a preflight different from the pre-candidate generation lock",
        )
        gated_path, gated, gate_report = run_release_gates(
            selected_path, root / "gate-run", inputs["coverage"], inputs["math"],
            inputs["repro"], inputs["results"], inputs["workbench"],
            inputs["preflight"], inputs["reasoning-review"], inputs["evidence-bundle"],
            inputs["portfolio"], style_retrieval_plan=inputs["style-retrieval"],
            authoring_brief=inputs["authoring-brief"], judgment_ledger=inputs["judgment-ledger"],
            drafting_packet_index=inputs["drafting-packets"], drafting_usage=inputs["drafting-usage"], executor=executor(),
        )
        require(gate_report["status"] == "pass", "passing release gates failed", gate_report)
        require(gated["state"] == "GATES_PASS", "gate state did not advance", gated)
        release_text = gate_report["target"]["release_path"]
        auxiliary_gate = next(item for item in gate_report["gates"] if item["id"] == "auxiliary-roles")
        require(
            auxiliary_gate.get("required") is True
            and auxiliary_gate.get("status") == "pass"
            and "audit_longform_auxiliary_roles.py" in " ".join(auxiliary_gate.get("command", [])),
            "the long-form release did not execute the read-only auxiliary roles gate",
            auxiliary_gate,
        )
        generation_gate = next(item for item in gate_report["gates"] if item["id"] == "generation-input-lock")
        require(
            generation_gate.get("required") is True
            and generation_gate.get("status") == "pass"
            and Path(generation_gate.get("report", {}).get("path", "")).resolve()
            == Path(locked_manifest["generation_input_lock"]["path"]).resolve()
            and generation_gate.get("report", {}).get("sha256")
            == locked_manifest["generation_input_lock"]["sha256"]
            and generation_gate.get("source_sha256") == locked_manifest["authority"]["main_sha256"]
            and generation_gate.get("source_tree_sha256")
            == generation_lock["source"]["tree_sha256"],
            "the release report did not preserve the pre-candidate generation-input lock",
            generation_gate,
        )
        academic_gate = next(item for item in gate_report["gates"] if item["id"] == "academic-style-release")
        require(
            academic_gate.get("required") is True
            and academic_gate.get("status") == "pass"
            and release_text in academic_gate.get("command", [])
            and "--require-style-gain" in academic_gate.get("command", [])
            and "--packet-index" in academic_gate.get("command", [])
            and str(inputs["drafting-packets"].resolve()) in academic_gate.get("command", [])
            and len(academic_gate.get("dependencies", [])) == 6,
            "the academic release gate did not require packet-bound style gain or record its dependencies",
            academic_gate,
        )
        release_workbench_gate = next(
            item for item in gate_report["gates"] if item["id"] == "modeling-workbench"
        )
        require(
            "--phase" in release_workbench_gate.get("command", [])
            and "release" in release_workbench_gate.get("command", []),
            "the release gate did not require the completed candidate reasoning bridge",
            release_workbench_gate,
        )
        style_gate = next(item for item in gate_report["gates"] if item["id"] == "style-retrieval-plan")
        require(
            style_gate.get("required") is True
            and style_gate.get("status") == "pass"
            and str(inputs["style-retrieval"].resolve()) in style_gate.get("command", []),
            "the release runner did not execute the bound style retrieval plan",
            style_gate,
        )
        brief_gate = next(item for item in gate_report["gates"] if item["id"] == "section-authoring-brief")
        require(
            brief_gate.get("required") is True
            and brief_gate.get("status") == "pass"
            and str(inputs["authoring-brief"].resolve()) in brief_gate.get("command", []),
            "the release runner did not execute the section authoring brief gate",
            brief_gate,
        )
        packet_gate = next(item for item in gate_report["gates"] if item["id"] == "section-drafting-packets")
        require(
            packet_gate.get("required") is True
            and packet_gate.get("status") == "pass"
            and str(inputs["drafting-packets"].resolve()) in packet_gate.get("command", []),
            "the release runner did not execute the section drafting packet gate",
            packet_gate,
        )
        usage_gate = next(item for item in gate_report["gates"] if item["id"] == "section-drafting-usage")
        require(
            usage_gate.get("required") is True
            and usage_gate.get("status") == "pass"
            and str(inputs["drafting-usage"].resolve()) in usage_gate.get("command", []),
            "the release runner did not execute the section drafting usage gate",
            usage_gate,
        )
        bridge_gate = next(item for item in gate_report["gates"] if item["id"] == "public-judgment-bridges")
        require(
            bridge_gate.get("required") is True
            and bridge_gate.get("status") == "pass"
            and str((Path(__file__).resolve().parents[3] / "mcm-cup-standard-write" / "scripts" / "audit_section_judgment_bridges.py").resolve()) in bridge_gate.get("command", [])
            and str(inputs["drafting-packets"].resolve()) in bridge_gate.get("command", []),
            "the release runner did not execute the public judgment bridge gate",
            bridge_gate,
        )
        scaffold_gate = next(item for item in gate_report["gates"] if item["id"] == "public-reasoning-scaffold")
        require(
            scaffold_gate.get("required") is True
            and scaffold_gate.get("status") == "pass"
            and str((Path(__file__).resolve().parent / "audit_reasoning_scaffold.py").resolve()) in scaffold_gate.get("command", []),
            "the release runner did not execute the public reasoning scaffold gate",
            scaffold_gate,
        )
        for gate in gate_report["gates"]:
            if gate["id"] in {"portfolio-selection", "academic-style-release", "public-reasoning-scaffold", "modeling-workbench", "corpus-overlap", "reasoning-review", "judgment-ledger", "public-judgment-bridges", "manuscript", "math-semantics", "result-sync", "compile", "competition-length", "content-density", "section-drafting-usage"}:
                require(release_text in gate.get("command", []), "a gate audited the wrong manuscript target", gate)
        frozen_source_main = next(
            item["snapshot_path"] for item in gated["authority"]["files"]
            if Path(item["authority_path"]).resolve() == Path(gated["authority"]["main_path"]).resolve()
        )
        for source_gate in (style_gate, brief_gate, packet_gate):
            require(
                str(Path(frozen_source_main).resolve()) in source_gate.get("command", [])
                and release_text not in source_gate.get("command", []),
                "a generation-input gate was not bound to the pre-candidate frozen source",
                source_gate,
            )
        preflight_gate = next(item for item in gate_report["gates"] if item["id"] == "reasoning-preflight")
        require(
            str(inputs["workbench"].resolve()) in preflight_gate["command"]
            and str(inputs["preflight"].resolve()) in preflight_gate["command"],
            "the preflight gate did not receive its locked workbench and approval inputs",
            preflight_gate,
        )
        evidence_gate = next(item for item in gate_report["gates"] if item["id"] == "evidence-bundle")
        require(
            evidence_gate["required"] is True
            and str(inputs["evidence-bundle"].resolve()) in evidence_gate["command"],
            "the evidence bundle gate did not receive the locked competition materials manifest",
            evidence_gate,
        )
        portfolio_gate = next(item for item in gate_report["gates"] if item["id"] == "portfolio-selection")
        require(
            portfolio_gate["required"] is True
            and str(inputs["portfolio"].resolve()) in portfolio_gate["command"]
            and "H1" in portfolio_gate["command"],
            "the release runner did not bind the selected target to role receipts",
            portfolio_gate,
        )
        review_gate = next(item for item in gate_report["gates"] if item["id"] == "reasoning-review")
        require(
            str(inputs["reasoning-review"].resolve()) in review_gate["command"],
            "the reasoning review gate did not receive its locked team review input",
            review_gate,
        )
        ledger_gate = next(item for item in gate_report["gates"] if item["id"] == "judgment-ledger")
        require(
            str(inputs["judgment-ledger"].resolve()) in ledger_gate["command"]
            and str(inputs["workbench"].resolve()) in ledger_gate["command"],
            "the public judgment ledger gate did not receive its locked ledger and workbench inputs",
            ledger_gate,
        )
        require(
            release_text != str(source.resolve())
            and release_text != str(candidate.resolve())
            and Path(release_text).read_bytes() == candidate.read_bytes(),
            "release gates did not use an immutable selected-source snapshot", gate_report["target"],
        )
        release_figure = Path(next(
            item["path"] for item in gate_report["target"]["files"]
            if item["relative_path"] == "figure.png"
        ))
        require(
            release_figure.read_bytes() == candidate_figure.read_bytes()
            and gate_report["target"].get("release_tree_sha256"),
            "compile resources were not included in the immutable release tree", gate_report["target"],
        )
        require(audit_manifest(gated_path)["status"] == "pass", "gated manifest failed audit", gated)

        expect_value_error(
            lambda: finalize_release(
                gated_path, "组员1", "页面检查完成。", sorted(RENDER_CHECKS - {"formulas"}),
                root / "incomplete-review.json",
            ),
            "an incomplete visual checklist was accepted",
        )
        expect_value_error(
            lambda: finalize_release(
                gated_path, "Codex", "模型已经完成页面检查。", sorted(RENDER_CHECKS),
                root / "model-review.json", reviewer_kind="model",
            ),
            "a model reviewer was allowed to finalize the release",
        )
        final_path, final = finalize_release(
            gated_path, "组员1", "逐页检查标题、跨页表、公式、图注、参考文献、附录和溢出乱码。",
            sorted(RENDER_CHECKS),
        )
        require(
            final["state"] == "RELEASE_READY"
            and final["final_review"]["reviewer_kind"] == "human",
            "final state did not advance with an explicit human review",
            final,
        )
        require(audit_manifest(final_path)["status"] == "pass", "release-ready manifest failed audit", final)

        report_path = Path(final["release_gate_run"]["path"])
        frozen_report = report_path.read_text(encoding="utf-8")
        report_path.write_text(frozen_report + "\n", encoding="utf-8")
        tampered = audit_manifest(final_path)
        require(
            tampered["status"] == "fail"
            and any(item["code"] == "RELEASE_GATE_REPORT_DRIFT" for item in tampered["findings"]),
            "release report tampering was not detected", tampered,
        )
        report_path.write_text(frozen_report, encoding="utf-8")

        restored_report = json.loads(frozen_report)
        tool_snapshot = Path(next(
            gate["tool"]["snapshot"]["path"]
            for gate in restored_report["gates"]
            if gate.get("tool", {}).get("snapshot")
        ))
        frozen_tool = tool_snapshot.read_bytes()
        tool_snapshot.write_bytes(frozen_tool + b"\n")
        tool_drift = audit_manifest(final_path)
        require(
            tool_drift["status"] == "fail"
            and any(item["code"] == "RELEASE_GATE_TOOL_SNAPSHOT_DRIFT" for item in tool_drift["findings"]),
            "quality-gate tool snapshot tampering was not detected", tool_drift,
        )
        tool_snapshot.write_bytes(frozen_tool)

        dependency_snapshot = Path(next(
            dependency["snapshot"]["path"]
            for gate in restored_report["gates"]
            if gate.get("id") == "academic-style-release"
            for dependency in gate.get("dependencies", [])
        ))
        frozen_dependency = dependency_snapshot.read_bytes()
        dependency_snapshot.write_bytes(frozen_dependency + b"\n")
        dependency_drift = audit_manifest(final_path)
        require(
            dependency_drift["status"] == "fail"
            and any(
                item["code"] == "RELEASE_GATE_DEPENDENCY_SNAPSHOT_DRIFT"
                for item in dependency_drift["findings"]
            ),
            "academic-style dependency tampering was not detected",
            dependency_drift,
        )
        dependency_snapshot.write_bytes(frozen_dependency)

        release_source = Path(restored_report["target"]["release_path"])
        frozen_release_source = release_source.read_bytes()
        release_source.write_bytes(frozen_release_source + b"\n")
        release_source_drift = audit_manifest(final_path)
        require(
            release_source_drift["status"] == "fail"
            and any(item["code"] == "RELEASE_SELECTED_MAIN_DRIFT" for item in release_source_drift["findings"]),
            "selected-source snapshot tampering was not detected", release_source_drift,
        )
        release_source.write_bytes(frozen_release_source)

        frozen_release_figure = release_figure.read_bytes()
        release_figure.write_bytes(frozen_release_figure + b"\n")
        release_resource_drift = audit_manifest(final_path)
        require(
            release_resource_drift["status"] == "fail"
            and any(item["code"] == "RELEASE_SELECTED_TREE_DRIFT" for item in release_resource_drift["findings"]),
            "non-TeX release resource tampering was not detected", release_resource_drift,
        )
        release_figure.write_bytes(frozen_release_figure)

        failed_selected_path, _ = select_target(
            registered_path, "H1", "队长", "用于失败门回归。", output_path=root / "selected-failure.json",
        )
        failed_gated_path, failed_gated, failed_report = run_release_gates(
            failed_selected_path, root / "gate-failure", inputs["coverage"], inputs["math"],
            inputs["repro"], inputs["results"], inputs["workbench"], inputs["preflight"],
            inputs["reasoning-review"], inputs["evidence-bundle"], inputs["portfolio"], output_path=root / "gated-failure.json",
            style_retrieval_plan=inputs["style-retrieval"],
            authoring_brief=inputs["authoring-brief"],
            judgment_ledger=inputs["judgment-ledger"],
            drafting_packet_index=inputs["drafting-packets"],
            drafting_usage=inputs["drafting-usage"],
            executor=executor("math-semantics"),
        )
        require(failed_report["status"] == "fail", "failed gate run was marked pass", failed_report)
        require(failed_gated["state"] == "GATES_FAILED", "failed gate state was wrong", failed_gated)
        require(audit_manifest(failed_gated_path)["status"] == "pass", "honest failed-gate ledger should remain auditable", failed_gated)
        expect_value_error(
            lambda: finalize_release(
                failed_gated_path, "组员2", "不应放行。", sorted(RENDER_CHECKS), root / "bad-final.json",
            ),
            "a failed gate run reached RELEASE_READY",
        )

        overflow_gated_path, overflow_gated, overflow_report = run_release_gates(
            failed_selected_path, root / "gate-overflow", inputs["coverage"], inputs["math"],
            inputs["repro"], inputs["results"], inputs["workbench"], inputs["preflight"],
            inputs["reasoning-review"], inputs["evidence-bundle"], inputs["portfolio"], output_path=root / "gated-overflow.json",
            style_retrieval_plan=inputs["style-retrieval"],
            authoring_brief=inputs["authoring-brief"],
            judgment_ledger=inputs["judgment-ledger"],
            drafting_packet_index=inputs["drafting-packets"],
            drafting_usage=inputs["drafting-usage"],
            executor=executor(compile_log="Overfull \\hbox (10.0pt too wide) in paragraph"),
        )
        compile_record = next(item for item in overflow_report["gates"] if item["id"] == "compile")
        require(
            overflow_report["status"] == "fail"
            and overflow_gated["state"] == "GATES_FAILED"
            and compile_record["latex_log"]["scan"]["blockers"].get("overfull-box") == 1,
            "an overfull TeX box did not block release", overflow_report,
        )
        require(
            audit_manifest(overflow_gated_path)["status"] == "pass",
            "the honest overflow failure ledger was not auditable", overflow_gated,
        )

        candidate2_dir = root / "candidate2"
        candidate2_dir.mkdir()
        candidate2 = candidate2_dir / "main.tex"
        candidate2.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        (candidate2_dir / "figure.png").write_bytes(source_figure.read_bytes())
        two_path, _, two_verification = register_candidate(
            registered_path, candidate2, "humanize-academic-chinese", "H2", root / "two-candidates.json",
        )
        require(two_verification["status"] == "pass", "second fixture candidate failed", two_verification)
        expect_value_error(
            lambda: select_target(
                two_path, "H2", "队长", "没有双盲证据。", output_path=root / "unblinded.json",
            ),
            "multiple passing candidates were selected without blind evidence",
        )
        weak_blind = root / "weak-blind.json"
        weak_blind.write_text(json.dumps({
            "schema": "aigc-blind-score/v1", "status": "pass",
            "coverage": {"p1": 1}, "pairs": 1, "ratings": 1,
        }), encoding="utf-8")
        expect_value_error(
            lambda: select_target(
                two_path, "H2", "队长", "评审人数不足。", weak_blind,
                root / "weakly-reviewed.json",
            ),
            "one-rater blind evidence was accepted",
        )

        pairs_path = root / "release-pairs.json"
        pairs_path.write_text(json.dumps({
            "schema": "aigc-blind-pairs/v1",
            "pairs": [{
                "id": "paragraph-1",
                "variants": [
                    {"id": "H1", "text": "目标为最小化总成本。"},
                    {"id": "H2", "text": "总成本是本问需要压低的量。"},
                ],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        prepared = prepare_blind(pairs_path, root / "blind-run", 2026)
        raw_ratings_path = root / "release-ratings-raw.csv"
        with raw_ratings_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "pair_id", "rater_id", "rater_kind", "naturalness", "judgment_trajectory",
                "specificity", "content_density", "semantic_fidelity", "notes",
            ))
            writer.writeheader()
            for rater in ("R1", "R2"):
                writer.writerow({
                    "pair_id": "paragraph-1", "rater_id": rater, "rater_kind": "human",
                    "naturalness": "TIE", "judgment_trajectory": "TIE",
                    "specificity": "TIE", "content_density": "TIE",
                    "semantic_fidelity": "TIE", "notes": "",
                })
        with raw_ratings_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rating_fields = tuple(reader.fieldnames or ())
            rating_rows = list(reader)
        single_ratings = []
        for rater_id in ("R1", "R2"):
            single_path = root / f"release-ratings-{rater_id}.csv"
            with single_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rating_fields)
                writer.writeheader()
                writer.writerows(row for row in rating_rows if row["rater_id"] == rater_id)
            single_ratings.append(single_path)
        ratings_path = root / "release-ratings.csv"
        merge_report_path = root / "release-ratings-merge.json"
        merge_ratings(Path(prepared["packet"]), single_ratings, ratings_path, merge_report_path)
        blind_score_path = root / "release-blind-score.json"
        blind_score_path.write_text(
            json.dumps(
                score_blind(Path(prepared["key"]), ratings_path, merge_report_path),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        blind_selected_path, blind_selected = select_target(
            two_path, "H2", "队长", "双盲比较后由队伍结合语义复核采用。",
            blind_score_path, root / "blind-selected.json",
        )
        require(blind_selected["state"] == "HUMAN_SELECTED", "valid blind evidence was rejected", blind_selected)
        require(audit_manifest(blind_selected_path)["status"] == "pass", "blind-selected ledger failed", blind_selected)
        frozen_ratings = ratings_path.read_text(encoding="utf-8-sig")
        ratings_path.write_text(frozen_ratings + "\n", encoding="utf-8-sig")
        blind_drift = audit_manifest(blind_selected_path)
        require(
            blind_drift["status"] == "fail"
            and any(item["code"] == "BLIND_EVIDENCE_DRIFT" for item in blind_drift["findings"]),
            "ratings drift after selection was not detected", blind_drift,
        )
        ratings_path.write_text(frozen_ratings, encoding="utf-8-sig")

        frozen_single = single_ratings[0].read_text(encoding="utf-8-sig")
        single_ratings[0].write_text(frozen_single + "\n", encoding="utf-8-sig")
        single_drift = audit_manifest(blind_selected_path)
        require(
            single_drift["status"] == "fail"
            and any(item["code"] == "BLIND_MERGE_REPORT_INVALID" for item in single_drift["findings"]),
            "individual reviewer-file drift after selection was not detected",
            single_drift,
        )
        single_ratings[0].write_text(frozen_single, encoding="utf-8-sig")

        smoke_dir = root / "real-compile-smoke"
        smoke_dir.mkdir()
        smoke_tex = smoke_dir / "smoke.tex"
        smoke_tex.write_text(
            "\\documentclass{ctexart}\n\\begin{document}\n发布编译烟雾测试。\n\\end{document}\n",
            encoding="utf-8",
        )
        smoke_build = smoke_dir / "build"
        smoke_build.mkdir()
        latexmk = shutil.which("latexmk")
        require(bool(latexmk), "latexmk is unavailable", {})
        compile_result = _default_executor(
            [
                str(latexmk), "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
                f"-outdir={smoke_build}", str(smoke_tex),
            ],
            smoke_dir, "compile-smoke", smoke_dir,
        )
        require(
            compile_result["returncode"] == 0
            and (smoke_build / "smoke.pdf").is_file()
            and (smoke_build / "smoke.aux").is_file(),
            "real XeLaTeX smoke compile failed", compile_result,
        )

    print("PASS: selection, selected-target gates, artifact locks, failure blocking, rendered-page review and real XeLaTeX compile are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
