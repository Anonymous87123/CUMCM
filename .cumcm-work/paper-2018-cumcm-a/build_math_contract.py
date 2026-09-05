#!/usr/bin/env python3
"""Build math-semantics-contract.json from the frozen run report.

Every `expected` comes from results/run-report.json, and every `manuscript_literal`
is the string actually written in main.tex. The contract therefore fails if the
manuscript and the solver output ever drift apart.
"""
from __future__ import annotations

import json
from pathlib import Path

W = Path(__file__).resolve().parent
RUN = "results/run-report.json"
SOLVER = "solver/simulator.py"


def recheck(name: str, json_path: str, expected: float, literal: str,
            tolerance: float = 1e-6) -> dict[str, object]:
    return {"name": name, "source": RUN, "json_path": json_path, "operation": "literal",
            "expected": expected, "tolerance": tolerance, "manuscript_literal": literal}


def main() -> int:
    report = json.loads((W / RUN).read_text(encoding="utf-8"))
    cal = report["calibration"]
    q1 = report["q1_validation"]
    q2 = report["q2"]["result"]
    q2m = q2["metrics"]
    grid_delta = max(row["delta_vs_finest_c"] for row in report["grid_convergence"])

    contract = {
        "schema": "mcm-math-semantics-contract/v1",
        "note": "契约把正文的每个关键数值绑回 results/run-report.json 的具体字段，"
                "并把目标、约束与代码接口逐项对应。它不证明模型正确，只保证正文与运行输出同源。",
        "symbols": [
            {"name": "h_skin", "definition_pattern": r"h\$ & 皮肤侧散热系数",
             "use_pattern": r"h=\\SI\{8\.7739\}"},
            {"name": "theta", "definition_pattern": r"\\theta\(t\)\$ & 皮肤外侧温度",
             "use_pattern": r"\\theta\(t\)=T\(L,t\)"},
            {"name": "diffusivity", "definition_pattern": r"a_i=\\lambda_i/\(\\rho_i c_i\)",
             "use_pattern": r"空气层的 \$a=\\SI\{2\.361e-5\}"},
            {"name": "d2", "definition_pattern": r"d_i\$ & 第 \$i\$ 层厚度",
             "use_pattern": r"d_2\^\{\*\}"},
            {"name": "R_stack", "definition_pattern": r"R\$ & 四层串联总热阻",
             "use_pattern": r"R=\\sum_\{i=1\}\^\{4\}"},
        ],
        "objectives": [
            {"name": "q2-min-thickness",
             "manuscript_patterns": [r"\\min_\{d_2\}\\ d_2", r"目标函数取 \$d_2\$ 本身"],
             "forbidden_patterns": [r"\\min\(d_2-d_4\)\s*为本文", r"取 \$\\min\(d_2-d_4\)\$"],
             "code_path": SOLVER,
             "code_patterns": [r"def minimal_feasible_d2", r"low, high = BOUNDS_MM\[\"II\"\]"]},
            {"name": "q3-front-not-scalarised",
             "manuscript_patterns": [r"d_2\^\{\*\}\(d_4\)=\\min", r"保留双目标"],
             "forbidden_patterns": [],
             "code_path": SOLVER, "code_patterns": [r"def pareto_d2_d4"]},
        ],
        "constraints": [
            {"name": "cap-47",
             "manuscript_patterns": [r"\\max_\{0\\le t\\le T_\{\\mathrm\{w\}\}\}\\theta\(t\)\\le \\SI\{47\}"],
             "code_path": SOLVER, "code_patterns": [r"cap_c: float = 47\.0", r"peak <= cap_c"]},
            {"name": "budget-44-300s",
             "manuscript_patterns": [r"\\le \\SI\{300\}\{s\}", r"越阈累计时长"],
             "code_path": SOLVER,
             "code_patterns": [r"soft_c: float = 44\.0", r"soft_budget_s: float = 300\.0",
                               r"above_soft <= soft_budget_s"]},
            {"name": "thickness-bounds",
             "manuscript_patterns": [r"0\.6\\le d_2\\le 25"],
             "code_path": SOLVER,
             "code_patterns": [r"\"II\": \(0\.6, 25\.0\)", r"\"IV\": \(0\.6, 6\.4\)"]},
        ],
        "code_map": [
            {"name": "harmonic-face-conductance",
             "manuscript_patterns": [r"K_\{j\+1/2\}=", r"调和平均"],
             "code_path": SOLVER,
             "code_patterns": [r"self\.face = 1\.0 / \(half_left \+ half_right\)"]},
            {"name": "backward-euler",
             "manuscript_patterns": [r"后向 Euler", r"三对角"],
             "code_path": SOLVER, "code_patterns": [r"solve_banded"]},
            {"name": "skin-face-recovery",
             "manuscript_patterns": [r"皮肤外侧温度不是最后一格的格心值"],
             "code_path": SOLVER, "code_patterns": [r"def _skin_face"]},
            {"name": "robin-boundary",
             "manuscript_patterns": [r"-\\lambda_4 \\left\.", r"T_\{\\mathrm\{core\}\}"],
             "code_path": SOLVER, "code_patterns": [r"BODY_CORE_C = 37\.0", r"skin_conductance"]},
        ],
        "rechecks": [
            recheck("calibration-plateau", "calibration.from_plateau",
                    cal["from_plateau"], "8.6124", 1e-4),
            recheck("calibration-history", "calibration.from_history",
                    cal["from_history"], "8.7739", 1e-4),
            recheck("q1-rmse", "q1_validation.rmse_c", q1["rmse_c"], "0.4517", 1e-4),
            recheck("q1-max-abs", "q1_validation.max_abs_c", q1["max_abs_c"], "1.7972", 1e-4),
            recheck("q1-last-30min", "q1_validation.holdout_last_30min_rmse_c",
                    q1["holdout_last_30min_rmse_c"], "0.1453", 1e-4),
            recheck("q1-first-10min", "q1_validation.holdout_first_10min_rmse_c",
                    q1["holdout_first_10min_rmse_c"], "1.2798", 1e-4),
            recheck("q1-final-model", "q1_validation.final_model_c",
                    q1["final_model_c"], "47.9347", 1e-4),
            recheck("q1-steady-closed-form", "q1_validation.steady_state_closed_form_c",
                    q1["steady_state_closed_form_c"], "47.934716682526", 1e-9),
            recheck("air-layer-diffusivity", "diffusivity_m2_s.IV",
                    report["diffusivity_m2_s"]["IV"], "2.361e-5", 1e-9),
            recheck("q2-d2-star", "q2.result.d2_mm", q2["d2_mm"], "18.16", 1e-6),
            recheck("q2-peak", "q2.result.metrics.peak_skin_c", q2m["peak_skin_c"], "44.045", 1e-3),
            recheck("q2-first-cross", "q2.result.metrics.first_cross_44_s",
                    q2m["first_cross_44_s"], "3302", 1e-6),
            recheck("q2-budget-tight", "q2.result.metrics.seconds_above_44",
                    q2m["seconds_above_44"], "300", 1e-6),
            {"name": "grid-convergence-bound", "values": [grid_delta], "operation": "literal",
             "expected": grid_delta, "tolerance": 1e-12, "manuscript_literal": "2.7e-9"},
        ],
    }
    out = W / "math-semantics-contract.json"
    out.write_text(json.dumps(contract, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  symbols={len(contract['symbols'])} objectives={len(contract['objectives'])} "
          f"constraints={len(contract['constraints'])} code_map={len(contract['code_map'])} "
          f"rechecks={len(contract['rechecks'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
