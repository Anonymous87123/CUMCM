from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from numba import njit
from scipy.integrate import cumulative_trapezoid
from scipy.optimize import brentq, differential_evolution


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "paper" / "figures"
SEED = 20190913

PIPE_VOLUME = math.pi * 5.0**2 * 500.0
INLET_AREA = math.pi * 1.4**2 / 4.0
NOZZLE_AREA = INLET_AREA
PLUNGER_AREA = math.pi * 2.5**2
FLOW_COEFFICIENT = 0.85


def load_inputs() -> dict[str, np.ndarray]:
    cam = pd.read_excel(DATA / "appendix1.xlsx").dropna().to_numpy(float)
    needle = pd.read_excel(DATA / "appendix2.xlsx").dropna().to_numpy(float)
    modulus = pd.read_excel(DATA / "appendix3.xlsx").dropna().to_numpy(float)
    return {
        "cam_angle": cam[:, 0],
        "cam_radius": cam[:, 1],
        "needle_time": needle[:, 0],
        "needle_lift": needle[:, 1],
        "modulus_pressure": modulus[:, 0],
        "modulus_value": modulus[:, 1],
    }


def state_table(inputs: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pressure = np.linspace(0.0, 200.0, 20001)
    modulus = np.interp(
        pressure, inputs["modulus_pressure"], inputs["modulus_value"]
    )
    integral = cumulative_trapezoid(1.0 / modulus, pressure, initial=0.0)
    reference = np.interp(100.0, pressure, integral)
    density = 0.850 * np.exp(integral - reference)
    return pressure, density, modulus


@njit(cache=True)
def spray_rate(phase: float) -> float:
    if phase < 0.0 or phase >= 2.4:
        return 0.0
    if phase < 0.2:
        return 100.0 * phase
    if phase <= 2.2:
        return 20.0
    return 100.0 * (2.4 - phase)


@njit(cache=True)
def q_orifice(delta_p: float, density_high: float, area: float) -> float:
    if delta_p <= 0.0:
        return 0.0
    return FLOW_COEFFICIENT * area * math.sqrt(2.0 * delta_p / density_high)


@njit(cache=True)
def simulate_constant_supply(
    pressure_grid: np.ndarray,
    density_grid: np.ndarray,
    open_before: float,
    open_after: float,
    switch_time: float,
    total_time: float,
    initial_pressure: float,
    dt: float,
) -> tuple[np.ndarray, np.ndarray]:
    steps = int(total_time / dt) + 1
    stride = max(1, int(1.0 / dt))
    samples = steps // stride + 1
    times = np.empty(samples)
    pressures = np.empty(samples)
    density = np.interp(initial_pressure, pressure_grid, density_grid)
    density_supply = np.interp(160.0, pressure_grid, density_grid)
    pressure = initial_pressure
    out_index = 0
    for index in range(steps):
        time = index * dt
        phase = time % 100.0
        open_time = open_before if time < switch_time else open_after
        inflow = 0.0
        if phase < open_time:
            inflow = density_supply * q_orifice(
                160.0 - pressure, density_supply, INLET_AREA
            )
        outflow = density * spray_rate(phase)
        density += (inflow - outflow) * dt / PIPE_VOLUME
        pressure = np.interp(density, density_grid, pressure_grid)
        if index % stride == 0:
            times[out_index] = time
            pressures[out_index] = pressure
            out_index += 1
    return times[:out_index], pressures[:out_index]


@njit(cache=True)
def simulate_pump_system(
    pressure_grid: np.ndarray,
    density_grid: np.ndarray,
    cam_angle: np.ndarray,
    cam_radius: np.ndarray,
    needle_time: np.ndarray,
    needle_lift: np.ndarray,
    omega: float,
    nozzles: int,
    nozzle_offset: float,
    relief_low: float,
    relief_high: float,
    total_time: float,
    dt: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    steps = int(total_time / dt) + 1
    stride = max(1, int(1.0 / dt))
    samples = steps // stride + 1
    times = np.empty(samples)
    pipe_pressures = np.empty(samples)
    chamber_pressures = np.empty(samples)

    r_min = np.min(cam_radius)
    r_max = np.max(cam_radius)
    chamber_v_max = 20.0 + PLUNGER_AREA * (r_max - r_min)
    rho_low = np.interp(0.5, pressure_grid, density_grid)
    pipe_density = np.interp(100.0, pressure_grid, density_grid)
    chamber_mass = rho_low * chamber_v_max
    previous_volume = chamber_v_max
    relief_open = False
    out_index = 0

    for index in range(steps):
        time = index * dt
        theta = (omega * time) % (2.0 * math.pi)
        radius = np.interp(theta, cam_angle, cam_radius)
        volume = 20.0 + PLUNGER_AREA * (r_max - radius)
        # During the plunger downstroke the low-pressure inlet keeps the
        # chamber filled at 0.5 MPa.  Freezing the old mass here would leave
        # every cycle after the first one starved of fuel.
        if volume > previous_volume:
            chamber_mass = rho_low * volume
        chamber_density = chamber_mass / volume
        chamber_pressure = np.interp(chamber_density, density_grid, pressure_grid)
        pipe_pressure = np.interp(pipe_density, density_grid, pressure_grid)

        inlet_mass = 0.0
        if chamber_pressure > pipe_pressure:
            volume_rate = q_orifice(
                chamber_pressure - pipe_pressure, chamber_density, INLET_AREA
            )
            inlet_mass = chamber_density * volume_rate
            inlet_mass = min(inlet_mass, chamber_mass / max(dt, 1.0e-12))

        outlet_mass = 0.0
        for nozzle in range(nozzles):
            phase = (time - nozzle * nozzle_offset) % 100.0
            lift = np.interp(phase, needle_time, needle_lift)
            seat_area = math.pi * 2.5 * max(lift, 0.0) * math.sin(math.radians(9.0))
            effective_area = min(NOZZLE_AREA, seat_area)
            outlet_mass += pipe_density * q_orifice(
                pipe_pressure - 0.5, pipe_density, effective_area
            )

        relief_mass = 0.0
        if relief_high > relief_low:
            if pipe_pressure >= relief_high:
                relief_open = True
            elif pipe_pressure <= relief_low:
                relief_open = False
            if relief_open:
                relief_mass = pipe_density * q_orifice(
                    pipe_pressure - 0.5, pipe_density, INLET_AREA
                )

        chamber_mass -= inlet_mass * dt
        pipe_density += (inlet_mass - outlet_mass - relief_mass) * dt / PIPE_VOLUME
        previous_volume = volume

        if index % stride == 0:
            times[out_index] = time
            pipe_pressures[out_index] = np.interp(
                pipe_density, density_grid, pressure_grid
            )
            chamber_pressures[out_index] = chamber_pressure
            out_index += 1
    return (
        times[:out_index],
        pipe_pressures[:out_index],
        chamber_pressures[:out_index],
    )


def tail_metrics(times: np.ndarray, pressure: np.ndarray, target: float, tail_ms: float) -> dict:
    mask = times >= times[-1] - tail_ms
    error = pressure[mask] - target
    return {
        "mean_mpa": float(np.mean(pressure[mask])),
        "std_mpa": float(np.std(pressure[mask])),
        "rmse_mpa": float(np.sqrt(np.mean(error**2))),
        "min_mpa": float(np.min(pressure[mask])),
        "max_mpa": float(np.max(pressure[mask])),
        "peak_to_peak_mpa": float(np.ptp(pressure[mask])),
    }


def q1_analysis(p_grid: np.ndarray, rho_grid: np.ndarray) -> dict:
    def steady_mean(open_time: float, target: float) -> float:
        t, p = simulate_constant_supply(
            p_grid, rho_grid, open_time, open_time, 0.0, 4000.0, target, 0.05
        )
        return float(tail_metrics(t, p, target, 1000.0)["mean_mpa"])

    steady_100 = brentq(
        lambda value: steady_mean(value, 100.0) - 100.0, 1.0, 5.0, xtol=1.0e-4
    )
    steady_150 = brentq(
        lambda value: steady_mean(value, 150.0) - 150.0, 1.0, 10.0, xtol=1.0e-4
    )

    def refine_steady(value: float, target: float) -> tuple[float, list[dict]]:
        rows = []
        for candidate in np.arange(value - 0.20, value + 0.201, 0.02):
            t, p = simulate_constant_supply(
                p_grid,
                rho_grid,
                float(candidate),
                float(candidate),
                0.0,
                20000.0,
                target,
                0.02,
            )
            metrics = tail_metrics(t, p, target, 5000.0)
            score = abs(metrics["mean_mpa"] - target) + 0.1 * metrics["std_mpa"]
            rows.append(
                {
                    "open_time_ms": float(candidate),
                    "score": float(score),
                    **metrics,
                }
            )
        rows.sort(key=lambda row: (row["score"], row["open_time_ms"]))
        return rows[0]["open_time_ms"], rows

    steady_100, steady_100_candidates = refine_steady(steady_100, 100.0)
    steady_150, steady_150_candidates = refine_steady(steady_150, 150.0)

    baseline_time, baseline_pressure = simulate_constant_supply(
        p_grid, rho_grid, steady_100, steady_100, 0.0, 20000.0, 100.0, 0.02
    )
    steady_150_time, steady_150_pressure = simulate_constant_supply(
        p_grid, rho_grid, steady_150, steady_150, 0.0, 20000.0, 150.0, 0.02
    )
    ramps = {}
    for seconds in (2, 5, 10):
        transition = seconds * 1000.0

        def pressure_at_transition(open_time: float) -> float:
            t, p = simulate_constant_supply(
                p_grid,
                rho_grid,
                open_time,
                steady_150,
                transition,
                transition + 1500.0,
                100.0,
                0.05,
            )
            return float(np.interp(transition, t, p))

        coarse_ramp_open = brentq(
            lambda value: pressure_at_transition(value) - 150.0,
            steady_100,
            12.0,
            xtol=1.0e-4,
        )
        best_ramp = (float("inf"), coarse_ramp_open, None, None)
        for candidate in np.arange(
            coarse_ramp_open - 0.12, coarse_ramp_open + 0.121, 0.02
        ):
            t_try, p_try = simulate_constant_supply(
                p_grid,
                rho_grid,
                float(candidate),
                steady_150,
                transition,
                transition + 1000.0,
                100.0,
                0.02,
            )
            switch_pressure = float(np.interp(transition, t_try, p_try))
            score = abs(switch_pressure - 150.0)
            if score < best_ramp[0]:
                best_ramp = (score, float(candidate), t_try, p_try)
        ramp_open = best_ramp[1]
        t, p = best_ramp[2], best_ramp[3]
        ramps[str(seconds)] = {
            "transition_seconds": seconds,
            "ramp_open_ms": float(ramp_open),
            "steady_open_ms": float(steady_150),
            "pressure_at_switch_mpa": float(np.interp(transition, t, p)),
            "tail": tail_metrics(t, p, 150.0, 1000.0),
            "times": t,
            "pressures": p,
        }

    return {
        "steady_100_open_ms": float(steady_100),
        "steady_100_metrics": tail_metrics(
            baseline_time, baseline_pressure, 100.0, 5000.0
        ),
        "steady_100_candidates": steady_100_candidates[:5],
        "steady_150_open_ms": float(steady_150),
        "steady_150_metrics": tail_metrics(
            steady_150_time, steady_150_pressure, 150.0, 5000.0
        ),
        "steady_150_candidates": steady_150_candidates[:5],
        "baseline_times": baseline_time,
        "baseline_pressures": baseline_pressure,
        "ramps": ramps,
    }


def q2_q3_analysis(inputs: dict[str, np.ndarray], p_grid: np.ndarray, rho_grid: np.ndarray) -> dict:
    def evaluate(vector: np.ndarray, nozzles: int, offset: float) -> float:
        omega = float(vector[0])
        t, p, _ = simulate_pump_system(
            p_grid,
            rho_grid,
            inputs["cam_angle"],
            inputs["cam_radius"],
            inputs["needle_time"],
            inputs["needle_lift"],
            omega,
            nozzles,
            offset,
            0.0,
            0.0,
            4000.0,
            0.05,
        )
        metrics = tail_metrics(t, p, 100.0, 1500.0)
        return metrics["rmse_mpa"] + 2.0 * abs(metrics["mean_mpa"] - 100.0)

    q2_search = differential_evolution(
        lambda vector: evaluate(vector, 1, 0.0),
        bounds=[(0.005, 0.12)],
        seed=SEED,
        popsize=12,
        maxiter=28,
        tol=1.0e-4,
        polish=True,
    )
    coarse_q2_omega = float(q2_search.x[0])
    q2_candidates = []
    for omega in np.arange(coarse_q2_omega - 0.003, coarse_q2_omega + 0.00301, 0.0001):
        t_try, p_try, _ = simulate_pump_system(
            p_grid,
            rho_grid,
            inputs["cam_angle"],
            inputs["cam_radius"],
            inputs["needle_time"],
            inputs["needle_lift"],
            float(omega),
            1,
            0.0,
            0.0,
            0.0,
            10000.0,
            0.04,
        )
        metrics = tail_metrics(t_try, p_try, 100.0, 3000.0)
        score = metrics["rmse_mpa"] + 2.0 * abs(metrics["mean_mpa"] - 100.0)
        q2_candidates.append((score, float(omega)))
    q2_coarse_consistent = min(q2_candidates)[1]
    q2_fine_candidates = []
    for omega in np.arange(
        q2_coarse_consistent - 0.00006, q2_coarse_consistent + 0.000061, 0.00001
    ):
        t_try, p_try, _ = simulate_pump_system(
            p_grid,
            rho_grid,
            inputs["cam_angle"],
            inputs["cam_radius"],
            inputs["needle_time"],
            inputs["needle_lift"],
            float(omega),
            1,
            0.0,
            0.0,
            0.0,
            10000.0,
            0.02,
        )
        metrics = tail_metrics(t_try, p_try, 100.0, 3000.0)
        score = metrics["rmse_mpa"] + 2.0 * abs(metrics["mean_mpa"] - 100.0)
        q2_fine_candidates.append((score, float(omega), metrics))
    _, q2_omega, _ = min(q2_fine_candidates, key=lambda row: row[0])
    q2_t, q2_p, q2_chamber = simulate_pump_system(
        p_grid,
        rho_grid,
        inputs["cam_angle"],
        inputs["cam_radius"],
        inputs["needle_time"],
        inputs["needle_lift"],
        q2_omega,
        1,
        0.0,
        0.0,
        0.0,
        10000.0,
        0.02,
    )

    def q3_objective(vector: np.ndarray) -> float:
        return evaluate(vector[:1], 2, float(vector[1]))

    q3_search = differential_evolution(
        q3_objective,
        bounds=[(0.005, 0.18), (0.0, 100.0)],
        seed=SEED + 1,
        popsize=12,
        maxiter=32,
        tol=1.0e-4,
        polish=True,
    )
    coarse_q3_omega, _ = (float(value) for value in q3_search.x)

    def evaluate_q3_consistent(vector: np.ndarray) -> float:
        t_try, p_try, _ = simulate_pump_system(
            p_grid,
            rho_grid,
            inputs["cam_angle"],
            inputs["cam_radius"],
            inputs["needle_time"],
            inputs["needle_lift"],
            float(vector[0]),
            2,
            float(vector[1]),
            0.0,
            0.0,
            8000.0,
            0.04,
        )
        metrics = tail_metrics(t_try, p_try, 100.0, 3000.0)
        return metrics["rmse_mpa"] + 2.0 * abs(metrics["mean_mpa"] - 100.0)

    q3_consistent_search = differential_evolution(
        evaluate_q3_consistent,
        bounds=[
            (max(0.005, coarse_q3_omega - 0.002), min(0.18, coarse_q3_omega + 0.002)),
            (0.0, 100.0),
        ],
        seed=SEED + 2,
        popsize=8,
        maxiter=14,
        tol=1.0e-4,
        polish=True,
    )
    consistent_q3_omega, consistent_q3_offset = (
        float(value) for value in q3_consistent_search.x
    )
    q3_candidates = []
    for omega in np.arange(
        consistent_q3_omega - 0.00012, consistent_q3_omega + 0.000121, 0.00002
    ):
        for offset in np.arange(
            max(0.0, consistent_q3_offset - 12.0),
            min(100.0, consistent_q3_offset + 12.0) + 0.1,
            2.0,
        ):
            t_try, p_try, _ = simulate_pump_system(
                p_grid,
                rho_grid,
                inputs["cam_angle"],
                inputs["cam_radius"],
                inputs["needle_time"],
                inputs["needle_lift"],
                float(omega),
                2,
                float(offset),
                0.0,
                0.0,
                10000.0,
                0.02,
            )
            metrics = tail_metrics(t_try, p_try, 100.0, 3000.0)
            score = metrics["rmse_mpa"] + 2.0 * abs(metrics["mean_mpa"] - 100.0)
            q3_candidates.append((score, float(omega), float(offset)))
    _, q3_omega, q3_offset = min(q3_candidates)
    q3_t, q3_p, q3_chamber = simulate_pump_system(
        p_grid,
        rho_grid,
        inputs["cam_angle"],
        inputs["cam_radius"],
        inputs["needle_time"],
        inputs["needle_lift"],
        q3_omega,
        2,
        q3_offset,
        0.0,
        0.0,
        10000.0,
        0.02,
    )

    relief_candidates = []
    for factor in (1.04, 1.06, 1.08, 1.10, 1.12):
        for high in (101.0, 101.2, 101.5, 101.8, 102.0):
            for band in (0.3, 0.5, 0.8, 1.0):
                t_try, p_try, _ = simulate_pump_system(
                    p_grid,
                    rho_grid,
                    inputs["cam_angle"],
                    inputs["cam_radius"],
                    inputs["needle_time"],
                    inputs["needle_lift"],
                    q3_omega * factor,
                    2,
                    q3_offset,
                    high - band,
                    high,
                    10000.0,
                    0.02,
                )
                metrics = tail_metrics(t_try, p_try, 100.0, 3000.0)
                score = metrics["rmse_mpa"] + abs(metrics["mean_mpa"] - 100.0)
                relief_candidates.append((score, factor, high - band, high))
    _, relief_factor, relief_low, relief_high = min(relief_candidates)
    relief_t, relief_p, relief_chamber = simulate_pump_system(
        p_grid,
        rho_grid,
        inputs["cam_angle"],
        inputs["cam_radius"],
        inputs["needle_time"],
        inputs["needle_lift"],
        q3_omega * relief_factor,
        2,
        q3_offset,
        relief_low,
        relief_high,
        10000.0,
        0.02,
    )
    return {
        "q2": {
            "omega_rad_per_ms": q2_omega,
            "omega_rad_per_s": q2_omega * 1000.0,
            "metrics": tail_metrics(q2_t, q2_p, 100.0, 3000.0),
            "local_candidates": [
                {"score": row[0], "omega_rad_per_s": row[1] * 1000.0, **row[2]}
                for row in sorted(q2_fine_candidates, key=lambda item: item[0])[:5]
            ],
            "times": q2_t,
            "pressures": q2_p,
            "chamber_pressures": q2_chamber,
        },
        "q3": {
            "omega_rad_per_ms": q3_omega,
            "omega_rad_per_s": q3_omega * 1000.0,
            "nozzle_offset_ms": q3_offset,
            "metrics": tail_metrics(q3_t, q3_p, 100.0, 3000.0),
            "local_candidates": [
                {"score": row[0], "omega_rad_per_s": row[1] * 1000.0, "offset_ms": row[2]}
                for row in sorted(q3_candidates)[:8]
            ],
            "times": q3_t,
            "pressures": q3_p,
            "chamber_pressures": q3_chamber,
            "relief": {
                "omega_rad_per_s": q3_omega * relief_factor * 1000.0,
                "low_threshold_mpa": relief_low,
                "high_threshold_mpa": relief_high,
                "metrics": tail_metrics(relief_t, relief_p, 100.0, 3000.0),
                "times": relief_t,
                "pressures": relief_p,
                "chamber_pressures": relief_chamber,
            },
        },
    }


def plot_results(q1: dict, q23: dict, p_grid: np.ndarray, rho_grid: np.ndarray, modulus: np.ndarray) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.unicode_minus": False})

    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.0))
    axes[0].plot(p_grid, rho_grid, color="#315f76")
    axes[0].set(xlabel="pressure / MPa", ylabel="density / (mg mm$^{-3}$)")
    axes[1].plot(p_grid, modulus, color="#ad6a32")
    axes[1].set(xlabel="pressure / MPa", ylabel="elastic modulus / MPa")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "state_relation.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9.0, 4.3))
    axis.plot(q1["baseline_times"] / 1000.0, q1["baseline_pressures"], label="100 MPa hold")
    for seconds, item in q1["ramps"].items():
        axis.plot(item["times"] / 1000.0, item["pressures"], label=f"{seconds} s transition")
    axis.axhline(100.0, color="black", linewidth=0.7, alpha=0.5)
    axis.axhline(150.0, color="black", linewidth=0.7, alpha=0.5)
    axis.set(xlabel="time / s", ylabel="pipe pressure / MPa")
    axis.grid(alpha=0.25)
    axis.legend(ncol=2)
    figure.tight_layout()
    figure.savefig(FIGURES / "q1_control.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9.0, 4.3))
    q2 = q23["q2"]
    q3 = q23["q3"]
    axis.plot(q2["times"] / 1000.0, q2["pressures"], label="one nozzle")
    axis.plot(q3["times"] / 1000.0, q3["pressures"], label="two nozzles")
    axis.plot(
        q3["relief"]["times"] / 1000.0,
        q3["relief"]["pressures"],
        label="two nozzles + relief",
    )
    axis.axhline(100.0, color="black", linestyle="--", linewidth=0.8)
    axis.set(xlabel="time / s", ylabel="pipe pressure / MPa")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(FIGURES / "q23_pressure.pdf")
    plt.close(figure)


def serializable(value):
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items() if key not in {"times", "pressures", "chamber_pressures", "baseline_times", "baseline_pressures"}}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    p_grid, rho_grid, modulus = state_table(inputs)
    q1 = q1_analysis(p_grid, rho_grid)
    q23 = q2_q3_analysis(inputs, p_grid, rho_grid)
    plot_results(q1, q23, p_grid, rho_grid, modulus)
    summary = {
        "seed": SEED,
        "units": {"time": "ms", "pressure": "MPa", "length": "mm", "mass": "mg"},
        "state_relation": {
            "reference_pressure_mpa": 100.0,
            "reference_density_mg_per_mm3": 0.850,
            "pressure_grid_step_mpa": 0.01,
        },
        "problem1": serializable(q1),
        "problem2": serializable(q23["q2"]),
        "problem3": serializable(q23["q3"]),
        "numerics": {
            "integration_step_ms": 0.02,
            "saved_step_ms": 1.0,
            "optimization": "bounded scalar search for problem 1; fixed-seed differential evolution for problems 2 and 3",
            "claim_boundary": "reported controls are best values found under the stated discretization, not proofs of continuous global optimality",
        },
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
