#!/usr/bin/env python3
"""Generate the residual / calibration / summary tables.

Kept as a file rather than an inline heredoc: this shell strips backslashes from
heredocs even when quoted, which silently corrupts every LaTeX command.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "solver"))
from simulator import read_materials, read_measurement, Simulator  # noqa: E402

BANDS = ((0, 600, "0--10"), (600, 1260, "10--21"), (1260, 2400, "21--40"),
         (2400, 3600, "40--60"), (3600, 5401, "60--90"))


def main() -> int:
    materials = read_materials()
    times, measured = read_measurement()
    report = json.loads((W / "results" / "run-report.json").read_text(encoding="utf-8"))
    h = report["calibration"]["from_history"]
    sim = Simulator(materials, 6.0, 5.0)
    _, skin = sim.run(75.0, h, times[-1], dt_s=1.0)
    residual = skin[: measured.size] - measured

    rows = []
    for lo, hi, tag in BANDS:
        segment = residual[lo:hi]
        rows.append(
            f"    {tag} & {hi - lo} & {np.sqrt(np.mean(segment ** 2)):.4f} & "
            f"{np.max(np.abs(segment)):.4f} & {np.mean(segment):+.4f} " + r"\\"
        )
    (W / "tables" / "tab-residual.tex").write_text(
        r"\begin{tabular}{ccccc}" "\n" r"  \toprule" "\n"
        r"    时段/\si{min} & 样本数 & 残差均方根/\si{\celsius} & "
        r"最大绝对偏差/\si{\celsius} & 平均偏差/\si{\celsius} \\" "\n"
        r"  \midrule" "\n" + "\n".join(rows) + "\n"
        r"  \bottomrule" "\n" r"\end{tabular}" "\n", encoding="utf-8")

    cal = report["calibration"]
    (W / "tables" / "tab-calibration.tex").write_text(
        r"\begin{tabular}{lccl}" "\n" r"  \toprule" "\n"
        r"    标定路线 & 使用的数据 & $h$/\si{W/(m^2.K)} & 说明 \\" "\n"
        r"  \midrule" "\n"
        r"    闭式反解 & 仅平台值 \SI{48.08}{\celsius} & "
        f"{cal['from_plateau']:.4f}" r" & 不看瞬态形状 \\" "\n"
        r"    最小二乘 & 全部 5401 点 & "
        f"{cal['from_history']:.4f}" r" & 残差均方根 \SI{"
        f"{cal['history_rmse_c']:.4f}" r"}{\celsius} \\" "\n"
        r"  \midrule" "\n"
        r"    相对差 & --- & \SI{"
        f"{cal['relative_gap'] * 100:.2f}" r"}{\percent} & 结构未被拟合掩盖 \\" "\n"
        r"  \bottomrule" "\n" r"\end{tabular}" "\n", encoding="utf-8")

    (W / "tables" / "tab-summary.tex").write_text(
        r"\begin{tabular}{clll}" "\n" r"  \toprule" "\n"
        r"    问 & 条件 & 结论 & 紧约束 \\" "\n" r"  \midrule" "\n"
        r"    一 & \SI{75}{\celsius}，\SI{90}{min} & "
        r"$h=\SI{8.7739}{W/(m^2.K)}$，温度分布 & 无（标定问） \\" "\n"
        r"    二 & \SI{65}{\celsius}，\SI{60}{min} & "
        r"$d_2^{*}=\SI{18.16}{mm}$ & 五分钟预算 \\" "\n"
        r"    三 & \SI{80}{\celsius}，\SI{30}{min} & "
        r"前沿 $d_4\ge\SI{3.8}{mm}$，总厚最小 \SI{27.588}{mm} & 五分钟预算 \\" "\n"
        r"  \bottomrule" "\n" r"\end{tabular}" "\n", encoding="utf-8")

    for name in ("tab-residual", "tab-calibration", "tab-summary"):
        text = (W / "tables" / f"{name}.tex").read_text(encoding="utf-8")
        assert text.startswith("\\begin{tabular}"), name
        print(f"  tables/{name}.tex  {len(text)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
