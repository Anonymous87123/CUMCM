from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import model_pipeline as model


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "paper" / "figures"


def score(metrics: dict[str, float], mean_weight: float = 2.0) -> float:
    return metrics["rmse_mpa"] + mean_weight * abs(metrics["mean_mpa"] - 100.0)


def pressure_diagnostics(
    times: np.ndarray, pressure: np.ndarray, target: float, tail_ms: float
) -> dict[str, float | int]:
    mask = times >= times[-1] - tail_ms
    tail_t = times[mask]
    tail_p = pressure[mask]
    above = tail_p >= target
    crossings = int(np.count_nonzero(above[1:] != above[:-1]))
    return {
        "tail_start_ms": float(tail_t[0]),
        "tail_end_ms": float(tail_t[-1]),
        "within_1_mpa_fraction": float(np.mean(np.abs(tail_p - target) <= 1.0)),
        "within_2_mpa_fraction": float(np.mean(np.abs(tail_p - target) <= 2.0)),
        "minimum_mpa": float(np.min(tail_p)),
        "minimum_time_ms": float(tail_t[int(np.argmin(tail_p))]),
        "maximum_mpa": float(np.max(tail_p)),
        "maximum_time_ms": float(tail_t[int(np.argmax(tail_p))]),
        "target_crossings": crossings,
    }


def simulate_selected(
    inputs: dict[str, np.ndarray],
    p_grid: np.ndarray,
    rho_grid: np.ndarray,
    omega: float,
    nozzles: int,
    offset: float,
    relief_low: float = 0.0,
    relief_high: float = 0.0,
    dt: float = 0.02,
    total_time: float = 10000.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return model.simulate_pump_system(
        p_grid,
        rho_grid,
        inputs["cam_angle"],
        inputs["cam_radius"],
        inputs["needle_time"],
        inputs["needle_lift"],
        omega,
        nozzles,
        offset,
        relief_low,
        relief_high,
        total_time,
        dt,
    )


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    inputs = model.load_inputs()
    p_grid, rho_grid, _ = model.state_table(inputs)

    q1_open = float(summary["problem1"]["steady_100_open_ms"])
    q2_omega = float(summary["problem2"]["omega_rad_per_ms"])
    q3_omega = float(summary["problem3"]["omega_rad_per_ms"])
    q3_offset = float(summary["problem3"]["nozzle_offset_ms"])
    relief = summary["problem3"]["relief"]
    relief_omega = float(relief["omega_rad_per_s"]) / 1000.0
    relief_low = float(relief["low_threshold_mpa"])
    relief_high = float(relief["high_threshold_mpa"])

    q1_rows: list[dict[str, float]] = []
    for open_time in np.linspace(q1_open - 0.12, q1_open + 0.12, 13):
        t, p = model.simulate_constant_supply(
            p_grid, rho_grid, open_time, open_time, 0.0, 20000.0, 100.0, 0.02
        )
        metrics = model.tail_metrics(t, p, 100.0, 5000.0)
        q1_rows.append(
            {
                "open_time_ms": float(open_time),
                **metrics,
                "objective": abs(metrics["mean_mpa"] - 100.0)
                + 0.1 * metrics["std_mpa"],
            }
        )
    q1_profile = pd.DataFrame(q1_rows)
    q1_profile.to_csv(RESULTS / "q1_local_profile.csv", index=False)

    q2_rows: list[dict[str, float]] = []
    for omega in np.linspace(q2_omega - 0.003, q2_omega + 0.003, 13):
        t, p, _ = simulate_selected(
            inputs, p_grid, rho_grid, float(omega), 1, 0.0, dt=0.02, total_time=10000.0
        )
        metrics = model.tail_metrics(t, p, 100.0, 3000.0)
        q2_rows.append(
            {
                "omega_rad_per_s": float(omega * 1000.0),
                **metrics,
                "objective": score(metrics),
            }
        )
    q2_profile = pd.DataFrame(q2_rows)
    q2_profile.to_csv(RESULTS / "q2_local_profile.csv", index=False)

    q3_rows: list[dict[str, float]] = []
    for offset in np.linspace(q3_offset - 12.0, q3_offset + 12.0, 13):
        t, p, _ = simulate_selected(
            inputs,
            p_grid,
            rho_grid,
            q3_omega,
            2,
            float(offset),
            dt=0.02,
            total_time=10000.0,
        )
        metrics = model.tail_metrics(t, p, 100.0, 3000.0)
        q3_rows.append(
            {
                "offset_ms": float(offset),
                **metrics,
                "objective": score(metrics),
            }
        )
    q3_profile = pd.DataFrame(q3_rows)
    q3_profile.to_csv(RESULTS / "q3_offset_profile.csv", index=False)

    convergence_rows: list[dict[str, float | str]] = []
    selected_series: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for dt in (0.08, 0.04, 0.02):
        t1, p1 = model.simulate_constant_supply(
            p_grid, rho_grid, q1_open, q1_open, 0.0, 20000.0, 100.0, dt
        )
        m1 = model.tail_metrics(t1, p1, 100.0, 5000.0)
        convergence_rows.append({"case": "Q1", "dt_ms": dt, **m1})

        for case, omega, nozzles, offset, low, high in (
            ("Q2", q2_omega, 1, 0.0, 0.0, 0.0),
            ("Q3", q3_omega, 2, q3_offset, 0.0, 0.0),
            ("Q3-relief", relief_omega, 2, q3_offset, relief_low, relief_high),
        ):
            t, p, chamber = simulate_selected(
                inputs,
                p_grid,
                rho_grid,
                omega,
                nozzles,
                offset,
                low,
                high,
                dt=dt,
                total_time=10000.0,
            )
            metrics = model.tail_metrics(t, p, 100.0, 3000.0)
            convergence_rows.append({"case": case, "dt_ms": dt, **metrics})
            if dt == 0.02:
                selected_series[case] = (t, p, chamber)
    convergence = pd.DataFrame(convergence_rows)
    convergence.to_csv(RESULTS / "step_convergence.csv", index=False)

    event_summary = {
        case: pressure_diagnostics(t, p, 100.0, 3000.0)
        for case, (t, p, _) in selected_series.items()
    }
    q1_t, q1_p = model.simulate_constant_supply(
        p_grid, rho_grid, q1_open, q1_open, 0.0, 20000.0, 100.0, 0.02
    )
    event_summary["Q1"] = pressure_diagnostics(q1_t, q1_p, 100.0, 5000.0)

    data_summary = {
        "appendix1": {
            "rows": int(len(inputs["cam_angle"])),
            "angle_range_rad": [float(inputs["cam_angle"].min()), float(inputs["cam_angle"].max())],
            "radius_range_mm": [float(inputs["cam_radius"].min()), float(inputs["cam_radius"].max())],
        },
        "appendix2": {
            "rows": int(len(inputs["needle_time"])),
            "time_range_ms": [float(inputs["needle_time"].min()), float(inputs["needle_time"].max())],
            "lift_range_mm": [float(inputs["needle_lift"].min()), float(inputs["needle_lift"].max())],
        },
        "appendix3": {
            "rows": int(len(inputs["modulus_pressure"])),
            "pressure_range_mpa": [float(inputs["modulus_pressure"].min()), float(inputs["modulus_pressure"].max())],
            "modulus_range_mpa": [float(inputs["modulus_value"].min()), float(inputs["modulus_value"].max())],
        },
    }
    diagnostic_summary = {
        "data_summary": data_summary,
        "local_profiles": {
            "q1_minimum_row": q1_profile.loc[q1_profile["objective"].idxmin()].to_dict(),
            "q2_minimum_row": q2_profile.loc[q2_profile["objective"].idxmin()].to_dict(),
            "q3_minimum_row": q3_profile.loc[q3_profile["objective"].idxmin()].to_dict(),
            "scope": "one-variable profiles with all other selected controls held fixed",
        },
        "event_summary": event_summary,
        "convergence": convergence.to_dict(orient="records"),
        "claim_boundary": "diagnostics test local neighborhoods and three time steps; they do not prove continuous global optimality or experimental validity",
    }
    (RESULTS / "diagnostics.json").write_text(
        json.dumps(diagnostic_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    plt.rcParams.update({"font.size": 10, "axes.unicode_minus": False})
    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    axis.plot(q1_profile["open_time_ms"], q1_profile["objective"], marker="o")
    axis.axvline(q1_open, color="black", linestyle="--", linewidth=0.8)
    axis.set(xlabel="valve opening / ms", ylabel="local objective")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "q1_local_profile.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    axis.plot(q2_profile["omega_rad_per_s"], q2_profile["objective"], marker="o")
    axis.axvline(q2_omega * 1000.0, color="black", linestyle="--", linewidth=0.8)
    axis.set(xlabel="cam angular speed / (rad s$^{-1}$)", ylabel="local objective")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "q2_local_profile.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.5, 4.2))
    axis.plot(q3_profile["offset_ms"], q3_profile["objective"], marker="o")
    axis.axvline(q3_offset, color="black", linestyle="--", linewidth=0.8)
    axis.set(xlabel="second-nozzle offset / ms", ylabel="local objective")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "q3_offset_profile.pdf")
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.0))
    q2_t, q2_p, q2_c = selected_series["Q2"]
    window = q2_t >= q2_t[-1] - 250.0
    axes[0].plot(q2_t[window], q2_p[window], label="pipe")
    axes[0].axhline(100.0, color="black", linestyle="--", linewidth=0.7)
    axes[0].set(xlabel="time / ms", ylabel="pipe pressure / MPa")
    axes[1].plot(q2_t[window], q2_c[window], color="#ad6a32", label="chamber")
    axes[1].set(xlabel="time / ms", ylabel="chamber pressure / MPa")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "q2_event_window.pdf")
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.0))
    for case, group in convergence.groupby("case"):
        axes[0].plot(group["dt_ms"], group["mean_mpa"], marker="o", label=case)
        axes[1].plot(group["dt_ms"], group["peak_to_peak_mpa"], marker="o", label=case)
    axes[0].set(xlabel="time step / ms", ylabel="tail mean / MPa")
    axes[1].set(xlabel="time step / ms", ylabel="peak-to-peak / MPa")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.invert_xaxis()
    axes[1].legend(ncol=2, fontsize=8)
    figure.tight_layout()
    figure.savefig(FIGURES / "step_convergence.pdf")
    plt.close(figure)

    print(json.dumps(diagnostic_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
