#!/usr/bin/env python3
"""Generate the three manuscript figures from the same solver used for the numbers.

Each figure carries one judgement, per paper-structure.md: the measured-versus-model
history shows where the model is weak, the thickness sweep shows the monotonicity the
bisection relies on, and the sensitivity panel shows why the optimum is ill-conditioned.
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
from simulator import (read_materials, read_measurement, Simulator,  # noqa: E402
                       constraint_metrics, minimal_feasible_d2)

plt.rcParams.update({"font.family": "SimSun", "axes.unicode_minus": False,
                     "font.size": 10, "figure.dpi": 200})
FIG = W / "figures"
FIG.mkdir(exist_ok=True)


def main() -> int:
    materials = read_materials()
    times, measured = read_measurement()
    report = json.loads((W / "results" / "run-report.json").read_text(encoding="utf-8"))
    h = report["calibration"]["from_history"]

    # 图 1：模型与实测对比 + 残差，判断是“模型在平台可靠、前十分钟偏乐观”
    sim = Simulator(materials, 6.0, 5.0)
    t, skin = sim.run(75.0, h, times[-1], dt_s=1.0)
    residual = skin[: measured.size] - measured
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.2, 4.6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(times / 60, measured, lw=1.6, label="附件 2 实测")
    ax1.plot(times / 60, skin[: measured.size], lw=1.1, ls="--", label="本文模型")
    ax1.axhline(48.08, lw=0.6, color="0.5")
    ax1.set_ylabel("皮肤外侧温度 / °C")
    ax1.legend(loc="lower right", frameon=False)
    ax2.plot(times / 60, residual, lw=0.9, color="0.25")
    ax2.axhline(0, lw=0.6, color="0.6")
    ax2.set_xlabel("时间 / min")
    ax2.set_ylabel("残差 / °C")
    fig.tight_layout()
    fig.savefig(FIG / "fig-q1-fit.pdf")
    plt.close(fig)

    # 图 2：厚度扫描，判断是“峰值单调不增，故二分成立”
    widths = np.array([0.6, 3.0, 6.0, 10.0, 14.0, 18.161, 22.0, 25.0])
    peaks, above = [], []
    for d2 in widths:
        s = Simulator(materials, float(d2), 5.5, cells_per_layer=20)
        tt, yy = s.run(65.0, h, 3600.0, dt_s=2.0)
        m = constraint_metrics(tt, yy, 3600.0)
        peaks.append(m["peak_skin_c"])
        above.append(m["seconds_above_44"])
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    ax.plot(widths, peaks, marker="o", lw=1.3, label="峰值温度")
    ax.axhline(44.0, lw=0.7, ls=":", color="0.4")
    ax.set_xlabel("第 II 层厚度 $d_2$ / mm")
    ax.set_ylabel("峰值温度 / °C")
    twin = ax.twinx()
    twin.plot(widths, np.array(above) / 60, marker="s", ms=4, lw=1.0,
              color="0.35", label="超过 44 °C 时长")
    twin.axhline(5.0, lw=0.7, ls="--", color="0.35")
    twin.set_ylabel("超过 44 °C 时长 / min")
    lines = ax.get_lines()[:1] + twin.get_lines()[:1]
    ax.legend(lines, [l.get_label() for l in lines], loc="center right", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig-q2-monotone.pdf")
    plt.close(fig)

    # 图 3：最优厚度对散热系数的敏感性，判断是“该约束病态，交付区间”
    factors = np.array([0.90, 0.95, 0.98, 1.00, 1.02, 1.05, 1.10])
    optima = []
    for factor in factors:
        found = minimal_feasible_d2(materials, h * float(factor), 65.0, 3600.0, 5.5,
                                    dt_s=4.0, tol_mm=0.05)
        optima.append(found.get("d2_mm"))
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    known = [(f, d) for f, d in zip(factors, optima) if d is not None]
    ax.plot([f * h for f, _ in known], [d for _, d in known], marker="o", lw=1.3)
    ax.axvspan(h * 0.98, h * 1.02, color="0.85", label="标定精度带 $\\pm2\\%$")
    ax.set_xlabel("皮肤侧散热系数 $h$ / W·m$^{-2}$·K$^{-1}$")
    ax.set_ylabel("最小可行 $d_2$ / mm")
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig-q2-sensitivity.pdf")
    plt.close(fig)

    print("figures written:")
    for path in sorted(FIG.glob("*.pdf")):
        print(f"  {path.name}  {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
