#!/usr/bin/env python3
"""Third batch: dimensionless groups, bisection trace, property perturbation, Q2 history figure.

All values come from the same solver as the rest of the manuscript. Written as a
file, not a heredoc: this shell strips backslashes from heredocs.
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
from simulator import (read_materials, Simulator, LAYERS, constraint_metrics,  # noqa: E402
                       BOUNDS_MM, BODY_CORE_C)

plt.rcParams.update({"font.family": "SimSun", "axes.unicode_minus": False,
                     "font.size": 9, "figure.dpi": 200})
TAB, FIG = W / "tables", W / "figures"
FIXED = {"I": 0.6e-3, "III": 3.6e-3}
BS = "\\"


def row(cells: list[str]) -> str:
    return "    " + " & ".join(cells) + " " + BS + BS


def table(header: str, spec: str, rows: list[str]) -> str:
    return (BS + "begin{tabular}{" + spec + "}\n" + "  " + BS + "toprule\n"
            + header + "\n  " + BS + "midrule\n" + "\n".join(rows)
            + "\n  " + BS + "bottomrule\n" + BS + "end{tabular}\n")


def main() -> int:
    materials = read_materials()
    report = json.loads((W / "results" / "run-report.json").read_text(encoding="utf-8"))
    h = report["calibration"]["from_history"]
    thickness = dict(FIXED, II=6.0e-3, IV=5.0e-3)

    # 无量纲群：Biot 用皮肤侧散热系数，Fourier 用九十分钟窗口
    rows = []
    for key in LAYERS:
        m = materials[key]
        biot = h * thickness[key] / m.lam
        fourier = m.diffusivity * 5400.0 / thickness[key] ** 2
        rows.append(row([key, f"{biot:.4f}", f"{fourier:.1f}",
                         "热阻主导" if biot > 1 else "温度近似均匀"]))
    (TAB / "tab-dimensionless.tex").write_text(
        table("    层 & $\\mathit{Bi}=h d/\\lambda$ & $\\mathit{Fo}=a t_{\\mathrm{w}}/d^2$ & 含义 " + BS + BS,
              "cccc", rows), encoding="utf-8")

    # 二分收敛轨迹（问题二）
    low, high = BOUNDS_MM["II"]
    rows, step = [], 0
    while high - low > 0.01 and step < 12:
        mid = 0.5 * (low + high)
        sim = Simulator(materials, mid, 5.5, cells_per_layer=20)
        times, skin = sim.run(65.0, h, 3600.0, dt_s=2.0)
        metrics = constraint_metrics(times, skin, 3600.0)
        step += 1
        rows.append(row([str(step), f"{low:.3f}", f"{high:.3f}", f"{mid:.3f}",
                         f"{metrics['seconds_above_44']:.0f}",
                         "可行" if metrics["feasible"] else "不可行"]))
        if metrics["feasible"]:
            high = mid
        else:
            low = mid
    (TAB / "tab-bisect.tex").write_text(
        table("    步 & 下界/\\si{mm} & 上界/\\si{mm} & 试探点/\\si{mm} & "
              "$>\\SI{44}{\\celsius}$ 时长/\\si{s} & 判定 " + BS + BS,
              "cccccc", rows), encoding="utf-8")

    # 物性扰动：逐层 lambda 单独 +5%，看问题二最优厚度怎么动
    from simulator import minimal_feasible_d2, Material
    base = minimal_feasible_d2(materials, h, 65.0, 3600.0, 5.5, dt_s=4.0, tol_mm=0.05)
    rows = [row(["基准", "---", f"{base['d2_mm']:.2f}", "---"])]
    for key in LAYERS:
        m = materials[key]
        bumped = dict(materials)
        bumped[key] = Material(m.rho, m.c, m.lam * 1.05)
        found = minimal_feasible_d2(bumped, h, 65.0, 3600.0, 5.5, dt_s=4.0, tol_mm=0.05)
        value = found.get("d2_mm")
        shown = f"{value:.2f}" if value is not None else found["status"]
        delta = f"{value - base['d2_mm']:+.2f}" if value is not None else "---"
        rows.append(row([f"$\\lambda_{{\\mathrm{{{key}}}}}$", "$+5\\%$", shown, delta]))
    (TAB / "tab-material.tex").write_text(
        table("    扰动对象 & 幅度 & 最小可行 $d_2$/\\si{mm} & 相对基准 " + BS + BS,
              "cccc", rows), encoding="utf-8")

    # 问题二最优点的温度历程与两条阈值
    sim = Simulator(materials, base["d2_mm"], 5.5, cells_per_layer=20)
    times, skin = sim.run(65.0, h, 3600.0, dt_s=1.0)
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.plot(times / 60, skin, lw=1.4, label="皮肤外侧温度")
    ax.axhline(47.0, ls="--", lw=0.8, color="0.3", label="47 °C 上限")
    ax.axhline(44.0, ls=":", lw=0.9, color="0.45", label="44 °C 阈值")
    cross = times[np.argmax(skin > 44.0)] / 60
    ax.axvspan(cross, 60, color="0.9", label=f"越阈区间 {60 - cross:.0f} min")
    ax.set_xlabel("时间 / min")
    ax.set_ylabel("温度 / °C")
    ax.set_xlim(0, 60)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "fig-q2-history.pdf")
    plt.close(fig)

    for name in ("tab-dimensionless", "tab-bisect", "tab-material"):
        text = (TAB / f"{name}.tex").read_text(encoding="utf-8")
        assert text.startswith(BS + "begin{tabular}"), name
        print(f"  tables/{name}.tex")
    print("  figures/fig-q2-history.pdf")
    print(f"  bisection steps recorded: {step}; d2* = {base['d2_mm']:.3f} mm; "
          f"first cross 44 at {cross:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
