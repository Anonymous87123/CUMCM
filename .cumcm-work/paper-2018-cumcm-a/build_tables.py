#!/usr/bin/env python3
"""Produce every table and figure the expanded manuscript needs, from one solver run.

Writes tables/*.tex fragments and figures/*.pdf so the manuscript can \input them.
Nothing here is hand-typed: every number comes from the simulator or the attachment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "solver"))
from simulator import (read_materials, read_measurement, Simulator, LAYERS,  # noqa: E402
                       constraint_metrics, minimal_feasible_d2, BODY_CORE_C)

plt.rcParams.update({"font.family": "SimSun", "axes.unicode_minus": False,
                     "font.size": 9, "figure.dpi": 200})
TAB = W / "tables"
FIG = W / "figures"
TAB.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)
FIXED = {"I": 0.6e-3, "III": 3.6e-3}


def write(name: str, body: str) -> None:
    (TAB / name).write_text(body, encoding="utf-8")
    print(f"  tables/{name}")


def table_properties(materials) -> None:
    thickness = {"I": "0.6", "II": "0.6--25", "III": "3.6", "IV": "0.6--6.4"}
    rows = []
    for key in LAYERS:
        m = materials[key]
        rows.append(f"    {key} & {m.rho:g} & {m.c:g} & {m.lam:g} & {thickness[key]} & "
                    f"\\num{{{m.diffusivity:.4g}}} \\\\")
    write("tab-properties.tex",
          "\\begin{tabular}{cccccc}\n  \\toprule\n"
          "    层 & $\\rho$/\\si{kg/m^3} & $c$/\\si{J/(kg.K)} & $\\lambda$/\\si{W/(m.K)}"
          " & $d$/\\si{mm} & $a$/\\si{m^2/s} \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def table_resistance(materials) -> None:
    thickness = dict(FIXED, II=6.0e-3, IV=5.0e-3)
    total = sum(thickness[k] / materials[k].lam for k in LAYERS)
    flux = (75.0 - 48.08) / total
    rows = []
    for key in LAYERS:
        m = materials[key]
        res = thickness[key] / m.lam
        rows.append(f"    {key} & {thickness[key]*1e3:.1f} & {res:.6f} & {res/total*100:.1f} & "
                    f"{flux*res:.3f} & {thickness[key]**2/m.diffusivity:.1f} \\\\")
    write("tab-resistance.tex",
          "\\begin{tabular}{cccccc}\n  \\toprule\n"
          "    层 & $d$/\\si{mm} & $d/\\lambda$/\\si{m^2.K/W} & 占总热阻/\\si{\\percent}"
          " & 稳态温降/\\si{\\celsius} & $d^2/a$/\\si{s} \\\\\n  \\midrule\n"
          + "\n".join(rows)
          + f"\n  \\midrule\n    合计 & {sum(thickness.values())*1e3:.1f} & {total:.6f} & 100.0 & "
            f"{flux*total:.3f} & --- \\\\\n  \\bottomrule\n\\end{{tabular}}\n")


def table_grid(report) -> None:
    rows = [
        f"    {r['cells_per_thinnest_layer']} & {r['dt_s']:.0f} & {r['cells_total']} & "
        f"{r['final_skin_c']:.9f} & \\num{{{r['delta_vs_finest_c']:.2g}}} \\\\"
        for r in report["grid_convergence"]
    ]
    write("tab-grid.tex",
          "\\begin{tabular}{ccccc}\n  \\toprule\n"
          "    最薄层格数 & $\\tau$/\\si{s} & 总格数 & 终点温度/\\si{\\celsius}"
          " & 与最细网格之差/\\si{\\celsius} \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def table_front(materials, h) -> dict:
    rows, data = [], []
    for d4 in np.round(np.arange(0.6, 6.4 + 1e-9, 0.4), 3):
        found = minimal_feasible_d2(materials, h, 80.0, 1800.0, float(d4), dt_s=4.0, tol_mm=0.02)
        d2 = found.get("d2_mm")
        metrics = found.get("metrics") or {}
        data.append({"d4": float(d4), "d2": d2, "status": found["status"],
                     "peak": metrics.get("peak_skin_c")})
        if d2 is None:
            rows.append(f"    {d4:.1f} & 无可行解 & --- & --- \\\\")
        else:
            rows.append(f"    {d4:.1f} & {d2:.3f} & {metrics['peak_skin_c']:.3f} & "
                        f"{d2 + d4:.3f} \\\\")
    write("tab-front.tex",
          "\\begin{tabular}{cccc}\n  \\toprule\n"
          "    $d_4$/\\si{mm} & 最小可行 $d_2$/\\si{mm} & 峰值/\\si{\\celsius}"
          " & 总厚/\\si{mm} \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")
    return {"front": data}


def table_sensitivity(materials, h) -> None:
    rows = []
    for factor in (0.80, 0.90, 0.95, 0.98, 1.00, 1.02, 1.05, 1.10, 1.20):
        hh = h * factor
        found = minimal_feasible_d2(materials, hh, 65.0, 3600.0, 5.5, dt_s=4.0, tol_mm=0.05)
        sim = Simulator(materials, 18.16, 5.5, cells_per_layer=20)
        plateau = sim.steady_state_skin(65.0, hh)
        d2 = found.get("d2_mm")
        shown = f"{d2:.2f}" if d2 is not None else (
            "下界即可行" if found["status"] == "lower_bound_already_feasible" else "整区间不可行")
        rows.append(f"    {factor - 1:+.0%} & {hh:.4f} & {plateau:.4f} & "
                    f"{plateau - 44:+.4f} & {shown} \\\\".replace("%", "\\%"))
    write("tab-sensitivity.tex",
          "\\begin{tabular}{ccccc}\n  \\toprule\n"
          "    $h$ 偏移 & $h$/\\si{W/(m^2.K)} & 平台温度/\\si{\\celsius}"
          " & 与 \\SI{44}{\\celsius} 之差 & 最小可行 $d_2$/\\si{mm} \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def table_slope(materials, h) -> None:
    sim = Simulator(materials, 18.16, 5.5, cells_per_layer=20)
    t, skin = sim.run(65.0, h, 3600.0, dt_s=1.0)
    rows = []
    for minute in (5, 10, 20, 30, 40, 50, 55, 60):
        index = minute * 60
        slope = (skin[index] - skin[index - 60])
        rows.append(f"    {minute} & {skin[index]:.4f} & {slope:+.4f} \\\\")
    write("tab-slope.tex",
          "\\begin{tabular}{ccc}\n  \\toprule\n"
          "    时刻/\\si{min} & 皮肤外侧温度/\\si{\\celsius} & 斜率/(\\si{\\celsius\\per\\minute}) \\\\\n"
          "  \\midrule\n" + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def table_interface(materials, h) -> None:
    sim = Simulator(materials, 6.0, 5.0)
    rows = []
    for minute in (1, 5, 10, 21, 45, 90):
        _, skin = sim.run(75.0, h, minute * 60, dt_s=1.0)
        rows.append(f"    {minute} & {skin[-1]:.4f} \\\\")
    write("tab-history.tex",
          "\\begin{tabular}{cc}\n  \\toprule\n"
          "    时刻/\\si{min} & 模型皮肤外侧温度/\\si{\\celsius} \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def table_verdict(materials, h) -> None:
    cases = [("问题二 \\SI{5.5}{mm}", 65.0, 3600.0, 5.5, 5.5),
             ("问题三 \\SI{5.6}{mm}/\\SI{5.4}{mm}", 80.0, 1800.0, 5.6, 5.4),
             ("问题三 \\SI{5.6}{mm}/\\SI{6.4}{mm}", 80.0, 1800.0, 5.6, 6.4)]
    rows = []
    for tag, env, window, d2, d4 in cases:
        sim = Simulator(materials, d2, d4, cells_per_layer=20)
        t, skin = sim.run(env, h, window, dt_s=2.0)
        m = constraint_metrics(t, skin, window)
        rows.append(f"    {tag} & {m['peak_skin_c']:.2f} & {'是' if m['cap_ok'] else '否'} & "
                    f"{m['seconds_above_44']:.0f} & {'是' if m['feasible'] else '否'} \\\\")
    write("tab-verdict.tex",
          "\\begin{tabular}{ccccc}\n  \\toprule\n"
          "    参考论文报告值 & 峰值/\\si{\\celsius} & 未破 \\SI{47}{\\celsius}"
          " & $>\\SI{44}{\\celsius}$ 时长/\\si{s} & 可行 \\\\\n  \\midrule\n"
          + "\n".join(rows) + "\n  \\bottomrule\n\\end{tabular}\n")


def figure_profile(materials, h) -> None:
    sim = Simulator(materials, 6.0, 5.0)
    edges = np.concatenate(([0.0], np.cumsum(sim.h)))
    centres = 0.5 * (edges[:-1] + edges[1:]) * 1e3
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    for minute, style in ((1, ":"), (5, "-."), (21, "--"), (90, "-")):
        temp = sim.run_field(75.0, h, minute * 60, dt_s=1.0)
        ax.plot(centres, temp, style, lw=1.2, label=f"$t={minute}$ min")
    boundary = np.cumsum([sim.thickness[k] for k in LAYERS]) * 1e3
    for edge in boundary[:-1]:
        ax.axvline(edge, lw=0.5, color="0.75")
    ax.set_xlabel("深度 $x$ / mm")
    ax.set_ylabel("温度 / °C")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "fig-q1-profile.pdf")
    plt.close(fig)
    print("  figures/fig-q1-profile.pdf")


def figure_front(front) -> None:
    ok = [(r["d4"], r["d2"]) for r in front if r["d2"] is not None]
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.plot([d4 for d4, _ in ok], [d2 for _, d2 in ok], marker="o", lw=1.3)
    bad = [r["d4"] for r in front if r["d2"] is None]
    if bad:
        ax.axvspan(min(bad) - 0.2, max(bad) + 0.2, color="0.88", label="整个 $d_2$ 区间不可行")
    ax.set_xlabel("第 IV 层厚度 $d_4$ / mm")
    ax.set_ylabel("最小可行 $d_2$ / mm")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig-q3-front.pdf")
    plt.close(fig)
    print("  figures/fig-q3-front.pdf")


def main() -> int:
    materials = read_materials()
    times, measured = read_measurement()
    report = json.loads((W / "results" / "run-report.json").read_text(encoding="utf-8"))
    h = report["calibration"]["from_history"]
    print("generated:")
    table_properties(materials)
    table_resistance(materials)
    table_grid(report)
    table_history = table_interface(materials, h)
    front = table_front(materials, h)
    table_sensitivity(materials, h)
    table_slope(materials, h)
    table_verdict(materials, h)
    figure_profile(materials, h)
    figure_front(front["front"])
    (W / "results" / "table-data.json").write_text(
        json.dumps(front, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
