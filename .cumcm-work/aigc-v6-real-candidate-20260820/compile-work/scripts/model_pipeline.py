from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"
OUT_DIR = ROOT / "outputs"
FIG_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)


plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update(
    {
        "figure.dpi": 160,
        "savefig.dpi": 220,
        "axes.unicode_minus": False,
        "font.size": 10,
    }
)


def _clip_positive(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _normalize(series: np.ndarray, ref: float | None = None) -> np.ndarray:
    base = series[0] if ref is None else ref
    return series / (base if base != 0 else 1.0)


def _safe_savefig(fig: plt.Figure, path: Path) -> None:
    try:
        fig.savefig(path, bbox_inches="tight")
    except PermissionError:
        fallback = Path.cwd() / f"{path.stem}_refresh_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
        fig.savefig(fallback, bbox_inches="tight")
        print(f"[warn] locked figure path: {path}; wrote {fallback.name} instead")


def _positive_normalize(weights: np.ndarray) -> np.ndarray:
    weights = np.clip(np.array(weights, dtype=float), 0.0, None)
    total = float(np.sum(weights))
    if total <= 1e-12:
        return np.full_like(weights, 1.0 / len(weights))
    return weights / total


def _normalize_indicator_matrix(matrix: np.ndarray, benefit_mask: np.ndarray) -> np.ndarray:
    matrix = np.array(matrix, dtype=float)
    out = np.zeros_like(matrix, dtype=float)
    for j in range(matrix.shape[1]):
        col = matrix[:, j]
        span = float(np.ptp(col))
        if span <= 1e-12:
            out[:, j] = 1.0
            continue
        if benefit_mask[j]:
            out[:, j] = (col - np.min(col)) / span
        else:
            out[:, j] = (np.max(col) - col) / span
    return out


def entropy_weights(matrix: np.ndarray) -> np.ndarray:
    matrix = np.array(matrix, dtype=float)
    m, n = matrix.shape
    if m <= 1:
        return np.full(n, 1.0 / n)
    col_sums = np.sum(matrix, axis=0, keepdims=True)
    probs = np.divide(matrix, col_sums, out=np.full_like(matrix, 1.0 / m), where=col_sums > 1e-12)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(probs > 0, probs * np.log(probs), 0.0)
    entropy = -np.sum(terms, axis=0) / math.log(m)
    diversification = 1.0 - entropy
    return _positive_normalize(diversification)


def critic_weights(matrix: np.ndarray) -> np.ndarray:
    matrix = np.array(matrix, dtype=float)
    std = np.std(matrix, axis=0, ddof=0)
    if np.all(std <= 1e-12):
        return np.full(matrix.shape[1], 1.0 / matrix.shape[1])
    corr = np.corrcoef(matrix, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    contrast = std * np.sum(1.0 - corr, axis=1)
    return _positive_normalize(contrast)


Q2_PROXY_BASAL_WEIGHT = 0.62
Q2_PROXY_WEIGHT_SCAN = np.linspace(0.50, 0.75, 6)
Q2_STURGEON_BARRIER_MULTIPLIER = 1.30
Q2_STURGEON_BARRIER_SCAN = np.linspace(1.10, 1.50, 5)
Q2_DIRECTIONAL_VALIDATION_T = 3.0


def fishing_pressure(t: float, h0: float) -> float:
    return h0


@dataclass(frozen=True)
class FoodWebParams:
    """Dimensionless structural parameters for the normalized single-zone food-web model.

    Only ``gain_scale`` is calibrated against the 2025 aggregate-carp anchor.
    The remaining coefficients are structural scenario settings used to preserve
    relative trophic time scales and Holling-type couplings in the normalized system.
    """
    rw: float = 1.15
    rp: float = 0.95
    rz: float = 0.82
    rn: float = 0.72
    kw: float = 1.0
    kp: float = 1.0
    kz: float = 1.0
    kn: float = 1.0
    a_wg: float = 1.22
    a_ps: float = 0.92
    a_zb: float = 0.84
    a_nq: float = 0.76
    h_w: float = 0.55
    h_p: float = 0.50
    h_z: float = 0.48
    h_n: float = 0.45
    e_wg: float = 0.43
    e_ps: float = 0.35
    e_zb: float = 0.33
    e_nq: float = 0.30
    m_g: float = 0.16
    m_s: float = 0.14
    m_b: float = 0.13
    m_q: float = 0.12
    gain_scale: float = 1.0
    h_fishing: float = 0.0
    pollution: float = 0.0


def food_web_rhs(t: float, y: np.ndarray, p: FoodWebParams) -> np.ndarray:
    w, ph, z, n, g, s, b, q = y
    h = fishing_pressure(t, p.h_fishing)
    u = p.pollution

    env = max(0.18, 1.0 - 0.55 * u)
    dw = p.rw * w * (1.0 - w / p.kw) * env - p.a_wg * w * g / (1.0 + p.h_w * w) - 0.14 * u * w
    dph = p.rp * ph * (1.0 - ph / p.kp) * env - p.a_ps * ph * s / (1.0 + p.h_p * ph) - 0.10 * u * ph
    dz = p.rz * z * (1.0 - z / p.kz) * env - p.a_zb * z * b / (1.0 + p.h_z * z) - 0.10 * u * z
    dn = p.rn * n * (1.0 - n / p.kn) * env - p.a_nq * n * q / (1.0 + p.h_n * n) - 0.08 * u * n

    dg = p.gain_scale * p.e_wg * p.a_wg * w * g / (1.0 + p.h_w * w) - (p.m_g + h + 0.12 * u) * g
    ds = p.gain_scale * p.e_ps * p.a_ps * ph * s / (1.0 + p.h_p * ph) - (p.m_s + h + 0.12 * u) * s
    db = p.gain_scale * p.e_zb * p.a_zb * z * b / (1.0 + p.h_z * z) - (p.m_b + h + 0.12 * u) * b
    dq = p.gain_scale * p.e_nq * p.a_nq * n * q / (1.0 + p.h_n * n) - (p.m_q + h + 0.12 * u) * q

    return np.array([dw, dph, dz, dn, dg, ds, db, dq], dtype=float)


@dataclass(frozen=True)
class RareSpeciesParams:
    r_m: float = 0.55
    k_m: float = 1.0
    a_d: float = 0.52
    a_s: float = 0.18
    a_v: float = 0.36
    h_m: float = 0.55
    e_d: float = 0.42
    e_s: float = 0.24
    e_v: float = 0.38
    m_d: float = 0.050
    m_s: float = 0.060
    m_v: float = 0.100
    barrier: float = 0.03
    sturgeon_barrier_multiplier: float = Q2_STURGEON_BARRIER_MULTIPLIER
    pollution: float = 0.0
    release_s: float = 0.012


def rare_species_rhs(
    t: float,
    y: np.ndarray,
    p: RareSpeciesParams,
    food_supply: Callable[[float], float],
) -> np.ndarray:
    m, d, s, v = y
    u = p.pollution
    supply = float(food_supply(t))
    k_eff = p.k_m * (0.62 + 0.76 * supply) * max(0.30, 1.0 - 0.60 * u)
    k_eff = max(k_eff, 0.18)

    dm = p.r_m * m * (1.0 - m / k_eff) - p.a_d * m * d / (1.0 + p.h_m * m) - p.a_s * m * s / (1.0 + p.h_m * m) - p.a_v * m * v / (1.0 + p.h_m * m) - 0.10 * u * m
    dd = p.e_d * p.a_d * m * d / (1.0 + p.h_m * m) - (p.m_d + p.barrier + 0.08 * u) * d
    ds = (
        p.release_s
        + p.e_s * p.a_s * m * s / (1.0 + p.h_m * m)
        - (p.m_s + p.sturgeon_barrier_multiplier * p.barrier + 0.11 * u) * s
    )
    dv = p.e_v * p.a_v * m * v / (1.0 + p.h_m * m) - (p.m_v + 0.05 * u) * v
    return np.array([dm, dd, ds, dv], dtype=float)


@dataclass(frozen=True)
class HPParams:
    r: float = 1.0
    a1: float = 5.0
    b1: float = 1.0
    a2: float = 0.1
    b2: float = 2.0
    d1: float = 0.4
    d2: float = 0.01
    k: float = 3.0


def hp_rhs(t: float, y: np.ndarray, p: HPParams) -> np.ndarray:
    x1, x2, x3 = y
    dx1 = p.r * x1 * (1.0 - x1 / p.k) - p.a1 * x1 * x2 / (p.b1 + x1)
    dx2 = p.a1 * x1 * x2 / (p.b1 + x1) - p.a2 * x2 * x3 / (p.b2 + x2) - p.d1 * x2
    dx3 = p.a2 * x2 * x3 / (p.b2 + x2) - p.d2 * x3
    return np.array([dx1, dx2, dx3], dtype=float)


def hp_jacobian(y: np.ndarray, p: HPParams) -> np.ndarray:
    x1, x2, x3 = y
    j11 = p.r * (1.0 - 2.0 * x1 / p.k) - p.a1 * x2 * p.b1 / (p.b1 + x1) ** 2
    j12 = -p.a1 * x1 / (p.b1 + x1)
    j13 = 0.0

    j21 = p.a1 * x2 * p.b1 / (p.b1 + x1) ** 2
    j22 = p.a1 * x1 / (p.b1 + x1) - p.a2 * x3 * p.b2 / (p.b2 + x2) ** 2 - p.d1
    j23 = -p.a2 * x2 / (p.b2 + x2)

    j31 = 0.0
    j32 = p.a2 * x3 * p.b2 / (p.b2 + x2) ** 2
    j33 = p.a2 * x2 / (p.b2 + x2) - p.d2

    return np.array([[j11, j12, j13], [j21, j22, j23], [j31, j32, j33]], dtype=float)


def rk4_step_state_tangent(
    y: np.ndarray,
    v: np.ndarray,
    dt: float,
    p: HPParams,
) -> tuple[np.ndarray, np.ndarray]:
    def f(x: np.ndarray) -> np.ndarray:
        return hp_rhs(0.0, x, p)

    def g(x: np.ndarray, vec: np.ndarray) -> np.ndarray:
        return hp_jacobian(x, p) @ vec

    k1y = f(y)
    k1v = g(y, v)

    y2 = y + 0.5 * dt * k1y
    v2 = v + 0.5 * dt * k1v
    k2y = f(y2)
    k2v = g(y2, v2)

    y3 = y + 0.5 * dt * k2y
    v3 = v + 0.5 * dt * k2v
    k3y = f(y3)
    k3v = g(y3, v3)

    y4 = y + dt * k3y
    v4 = v + dt * k3v
    k4y = f(y4)
    k4v = g(y4, v4)

    y_next = y + dt * (k1y + 2 * k2y + 2 * k3y + k4y) / 6.0
    v_next = v + dt * (k1v + 2 * k2v + 2 * k3v + k4v) / 6.0
    y_next = np.clip(y_next, 1e-10, None)
    return y_next, v_next


def lyapunov_max(p: HPParams, y0: np.ndarray, dt: float = 0.01, t_trans: float = 50.0, t_total: float = 150.0) -> float:
    y = np.array(y0, dtype=float)
    v = np.array([1.0, 0.0, 0.0], dtype=float)
    steps_trans = int(t_trans / dt)
    steps = int(t_total / dt)

    for _ in range(steps_trans):
        y, v = rk4_step_state_tangent(y, v, dt, p)
        norm = np.linalg.norm(v)
        if norm <= 0:
            v = np.array([1.0, 0.0, 0.0], dtype=float)
        else:
            v /= norm

    acc = 0.0
    for _ in range(steps):
        y, v = rk4_step_state_tangent(y, v, dt, p)
        norm = np.linalg.norm(v)
        norm = max(norm, 1e-12)
        acc += math.log(norm)
        v /= norm
    return acc / (steps * dt)


def simulate_food_web(p: FoodWebParams, t_span: tuple[float, float], y0: np.ndarray, n: int = 1201):
    t_eval = np.linspace(t_span[0], t_span[1], n)
    sol = solve_ivp(lambda t, y: food_web_rhs(t, y, p), t_span, y0, t_eval=t_eval, method="RK45", rtol=1e-7, atol=1e-9)
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.t, np.clip(sol.y, 0.0, None)


def simulate_rare_species(
    p: RareSpeciesParams,
    t_span: tuple[float, float],
    y0: np.ndarray,
    food_supply: Callable[[float], float],
    n: int = 1201,
):
    t_eval = np.linspace(t_span[0], t_span[1], n)
    sol = solve_ivp(
        lambda t, y: rare_species_rhs(t, y, p, food_supply),
        t_span,
        y0,
        t_eval=t_eval,
        method="RK45",
        rtol=1e-7,
        atol=1e-9,
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol.t, np.clip(sol.y, 0.0, None)


def build_ecosystem_index_components(series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w, ph, z, n, g, s, b, q = series
    basal = 0.30 * _normalize(w) + 0.25 * _normalize(ph) + 0.25 * _normalize(z) + 0.20 * _normalize(n)
    carp = 0.28 * _normalize(g) + 0.24 * _normalize(s) + 0.24 * _normalize(b) + 0.24 * _normalize(q)
    return basal, carp


def build_ecosystem_index(series: np.ndarray, basal_weight: float = Q2_PROXY_BASAL_WEIGHT) -> np.ndarray:
    basal, carp = build_ecosystem_index_components(series)
    return float(basal_weight) * basal + (1.0 - float(basal_weight)) * carp


Q1_TIME_ANCHORS = {"policy_start": 2021, "gazette_year": 2022, "monitor_year": 2025}
Q1_TARGETS = {"aggregate_carp_ratio_2025": 1.8, "cpue_proxy_ratio_2025": 2.2}
# Heuristic proxy weights: black carp is down-weighted because of lower single-net visibility.
Q1_CPUE_WEIGHTS = np.array([1.0, 1.0, 1.0, 0.7], dtype=float)
# Fixed initial-state normalization for the single-zone competition paper version.
Q1_FIXED_CONSUMER_SCALE = 0.60
# Mid-range counterfactual fishing pressure used only for the no-ban scenario.
Q1_COUNTERFACTUAL_H0 = 0.25
Q1_COUNTERFACTUAL_SCAN = np.linspace(0.10, 0.40, 7)


def total_carp(series: np.ndarray) -> np.ndarray:
    return np.sum(series[4:], axis=0)


def total_basal(series: np.ndarray) -> np.ndarray:
    return np.sum(series[:4], axis=0)


def cpue_proxy(series: np.ndarray, weights: np.ndarray = Q1_CPUE_WEIGHTS) -> np.ndarray:
    return np.sum(series[4:] * weights[:, None], axis=0)


def pressure_index(series: np.ndarray) -> np.ndarray:
    resources = total_basal(series)
    consumers = total_carp(series)
    return consumers / np.maximum(resources, 1e-12)


def q2_end_values(series: np.ndarray) -> dict[str, float]:
    sturgeon_end = float(_normalize(series[2])[-1])
    return {
        "M": float(_normalize(series[0])[-1]),
        "D": float(_normalize(series[1])[-1]),
        "A": sturgeon_end,
        "S": sturgeon_end,
        "V": float(_normalize(series[3])[-1]),
    }


def health_score(row: np.ndarray, weights: tuple[float, float, float, float]) -> float:
    return float(weights[0] * row[0] + weights[1] * row[1] + weights[2] * row[2] + weights[3] * row[3])


def make_q1_initial_state(base: np.ndarray, consumer_scale: float) -> np.ndarray:
    y0 = np.array(base, dtype=float)
    y0[4:] *= consumer_scale
    return y0


def q1_metrics(t: np.ndarray, series: np.ndarray) -> dict:
    time_to_value = {
        "2021": float(t[0]),
        "2022": float(Q1_TIME_ANCHORS["gazette_year"] - Q1_TIME_ANCHORS["policy_start"]),
        "2025": float(Q1_TIME_ANCHORS["monitor_year"] - Q1_TIME_ANCHORS["policy_start"]),
    }
    idx_2025 = int(np.argmin(np.abs(t - time_to_value["2025"])))
    idx_2022 = int(np.argmin(np.abs(t - time_to_value["2022"])))

    carp_total = total_carp(series)
    basal_total = total_basal(series)
    cpue = cpue_proxy(series)
    phi = pressure_index(series)
    water = _normalize(series[0])
    carp_norm = _normalize(carp_total)
    recover_mask = carp_norm > 1.01
    milestones = {
        "carp_recovers_above_baseline_year": float(t[np.argmax(recover_mask)]) if np.any(recover_mask) else None,
        "pressure_peak_year": float(t[int(np.argmax(phi))]),
        "water_min_year": float(t[int(np.argmin(water))]),
    }
    return {
        "aggregate_carp_ratio_2025": float(_normalize(carp_total)[idx_2025]),
        "aggregate_carp_ratio_2022": float(_normalize(carp_total)[idx_2022]),
        "cpue_proxy_ratio_2025": float(_normalize(cpue)[idx_2025]),
        "cpue_proxy_ratio_2022": float(_normalize(cpue)[idx_2022]),
        "pressure_start": float(phi[0]),
        "pressure_end": float(phi[-1]),
        "pressure_change": float(phi[-1] / max(phi[0], 1e-12)),
        "water_end": float(water[-1]),
        "water_min": float(np.min(water)),
        "water_min_year": float(t[int(np.argmin(water))]),
        "milestones": milestones,
        "species_end": {
            "W": float(_normalize(series[0])[-1]),
            "G": float(_normalize(series[4])[-1]),
            "S": float(_normalize(series[5])[-1]),
            "B": float(_normalize(series[6])[-1]),
            "Q": float(_normalize(series[7])[-1]),
        },
    }


def q1_loss(metrics: dict) -> float:
    agg = metrics["aggregate_carp_ratio_2025"]
    return ((agg - Q1_TARGETS["aggregate_carp_ratio_2025"]) / Q1_TARGETS["aggregate_carp_ratio_2025"]) ** 2


def calibrate_q1(
    base_y0: np.ndarray,
    t_span: tuple[float, float],
    structural_overrides: dict[str, float] | None = None,
) -> tuple[np.ndarray, FoodWebParams, dict]:
    best = None
    consumer_scale = Q1_FIXED_CONSUMER_SCALE
    gain_grid = np.linspace(0.8, 1.8, 101)
    y0 = make_q1_initial_state(base_y0, consumer_scale)
    structural_kwargs = FoodWebParams().__dict__.copy()
    if structural_overrides:
        structural_kwargs.update(structural_overrides)
    for gain_scale in gain_grid:
        params = FoodWebParams(
            **{
                **structural_kwargs,
                "h_fishing": 0.0,
                "pollution": 0.0,
                "gain_scale": float(gain_scale),
            }
        )
        t, series = simulate_food_web(params, t_span, y0, n=481)
        metrics = q1_metrics(t, series)
        loss = q1_loss(metrics)
        if best is None or loss < best["loss"]:
            best = {
                "loss": float(loss),
                "consumer_scale": float(consumer_scale),
                "gain_scale": float(gain_scale),
                "t": t,
                "series": series,
                "metrics": metrics,
            }
    assert best is not None
    best_y0 = make_q1_initial_state(base_y0, best["consumer_scale"])
    best_params = FoodWebParams(
        **{
            **structural_kwargs,
            "h_fishing": 0.0,
            "pollution": 0.0,
            "gain_scale": best["gain_scale"],
        }
    )
    best_t, best_series = simulate_food_web(best_params, t_span, best_y0)
    best_metrics = q1_metrics(best_t, best_series)
    summary = {
        "consumer_scale": best["consumer_scale"],
        "gain_scale": best["gain_scale"],
        "loss": best["loss"],
        "metrics": best_metrics,
        "calibration_scope": "fit aggregate_carp_ratio_2025 only; reserve CPUE proxy for post-fit consistency",
        "gain_grid": [float(gain_grid[0]), float(gain_grid[-1]), int(len(gain_grid))],
    }
    return best_y0, best_params, summary


def evaluate_counterfactual_h0(
    base_params: FoodWebParams, y0: np.ndarray, t_span: tuple[float, float], ban_metrics: dict
) -> tuple[FoodWebParams, np.ndarray, dict]:
    h0 = Q1_COUNTERFACTUAL_H0
    params = FoodWebParams(**{**base_params.__dict__, "h_fishing": h0})
    t, series = simulate_food_web(params, t_span, y0)
    metrics = q1_metrics(t, series)
    max_carp_ratio = float(np.max(_normalize(total_carp(series))))
    summary = {
        "h0": h0,
        "metrics": metrics,
        "selection_rule": "fixed mid-range counterfactual within [0.10, 0.40]; not estimated from observations",
        "aggregate_lower_than_ban": bool(metrics["aggregate_carp_ratio_2025"] < ban_metrics["aggregate_carp_ratio_2025"]),
        "cpue_lower_than_ban": bool(metrics["cpue_proxy_ratio_2025"] < ban_metrics["cpue_proxy_ratio_2025"]),
        "max_carp_ratio": max_carp_ratio,
        "no_overshoot": bool(max_carp_ratio <= 1.05),
    }
    return params, series, summary


def run_q1_counterfactual_scan(
    base_params: FoodWebParams,
    y0: np.ndarray,
    t_span: tuple[float, float],
    ban_metrics: dict,
) -> dict:
    samples = []
    for h0 in Q1_COUNTERFACTUAL_SCAN:
        params = FoodWebParams(**{**base_params.__dict__, "h_fishing": float(h0)})
        t, series = simulate_food_web(params, t_span, y0)
        metrics = q1_metrics(t, series)
        aggregate_gap = ban_metrics["aggregate_carp_ratio_2025"] - metrics["aggregate_carp_ratio_2025"]
        cpue_gap = ban_metrics["cpue_proxy_ratio_2025"] - metrics["cpue_proxy_ratio_2025"]
        max_carp_ratio = float(np.max(_normalize(total_carp(series))))
        samples.append(
            {
                "h0": float(h0),
                "aggregate_carp_ratio_2025": metrics["aggregate_carp_ratio_2025"],
                "cpue_proxy_ratio_2025": metrics["cpue_proxy_ratio_2025"],
                "aggregate_gap_vs_ban": float(aggregate_gap),
                "aggregate_gap_vs_ban_share": float(aggregate_gap / ban_metrics["aggregate_carp_ratio_2025"]),
                "cpue_gap_vs_ban": float(cpue_gap),
                "cpue_gap_vs_ban_share": float(cpue_gap / ban_metrics["cpue_proxy_ratio_2025"]),
                "ban_stronger_than_noban": bool(metrics["aggregate_carp_ratio_2025"] < ban_metrics["aggregate_carp_ratio_2025"]),
                "no_overshoot": bool(max_carp_ratio <= 1.05),
            }
        )

    h0_ge_015 = [sample for sample in samples if sample["h0"] >= 0.15 - 1e-12]
    return {
        "scan_range": [float(Q1_COUNTERFACTUAL_SCAN[0]), float(Q1_COUNTERFACTUAL_SCAN[-1])],
        "points": int(len(Q1_COUNTERFACTUAL_SCAN)),
        "samples": samples,
        "all_ban_stronger_than_noban": bool(all(sample["ban_stronger_than_noban"] for sample in samples)),
        "all_no_overshoot": bool(all(sample["no_overshoot"] for sample in samples)),
        "aggregate_gap_check_for_h0_ge_0_15": {
            "threshold_share": 0.30,
            "min_gap_share": float(min(sample["aggregate_gap_vs_ban_share"] for sample in h0_ge_015)),
            "all_above_threshold": bool(all(sample["aggregate_gap_vs_ban_share"] > 0.30 for sample in h0_ge_015)),
        },
    }


def run_q1_sensitivity(
    base_y0_template: np.ndarray,
    fitted_y0: np.ndarray,
    base_params: FoodWebParams,
    h0: float,
    t_span: tuple[float, float],
) -> dict:
    scenarios = {}
    settings = {
        "gain_scale": ("params", [0.9, 1.1]),
        "consumer_scale": ("y0", [0.9, 1.1]),
        "H0": ("h0", [0.9, 1.1]),
    }
    for name, (kind, scales) in settings.items():
        scenarios[name] = {}
        for scale in scales:
            if kind == "params":
                params = FoodWebParams(**{**base_params.__dict__, "gain_scale": base_params.gain_scale * scale})
                y0 = fitted_y0.copy()
                t, series = simulate_food_web(params, t_span, y0)
            elif kind == "y0":
                params = base_params
                y0 = fitted_y0.copy()
                y0[4:] *= scale
                t, series = simulate_food_web(params, t_span, y0)
            else:
                params = FoodWebParams(**{**base_params.__dict__, "h_fishing": h0 * scale})
                y0 = fitted_y0.copy()
                t, series = simulate_food_web(params, t_span, y0)
            metrics = q1_metrics(t, series)
            scenarios[name][f"{scale:.1f}x"] = {
                "aggregate_carp_ratio_2025": metrics["aggregate_carp_ratio_2025"],
                "cpue_proxy_ratio_2025": metrics["cpue_proxy_ratio_2025"],
                "pressure_end": metrics["pressure_end"],
                "water_min": metrics["water_min"],
                "water_min_year": metrics["water_min_year"],
            }

    structural_groups = {
        "resource_growth": ["rw", "rp", "rz", "rn"],
        "coupling_strength": ["a_wg", "a_ps", "a_zb", "a_nq"],
        "conversion_efficiency": ["e_wg", "e_ps", "e_zb", "e_nq"],
        "natural_loss": ["m_g", "m_s", "m_b", "m_q"],
    }
    structural_recalibration = {}
    for group_name, field_names in structural_groups.items():
        structural_recalibration[group_name] = {}
        for scale in (0.8, 1.2):
            overrides = {field: getattr(base_params, field) * scale for field in field_names}
            y0_refit, params_refit, fit_summary = calibrate_q1(base_y0_template, t_span, structural_overrides=overrides)
            t_ban, ban_series = simulate_food_web(params_refit, t_span, y0_refit)
            ban_metrics = q1_metrics(t_ban, ban_series)
            noban_params = FoodWebParams(**{**params_refit.__dict__, "h_fishing": h0})
            _, noban_series = simulate_food_web(noban_params, t_span, y0_refit)
            noban_metrics = q1_metrics(t_ban, noban_series)
            structural_recalibration[group_name][f"{scale:.1f}x"] = {
                "refitted_gain_scale": fit_summary["gain_scale"],
                "aggregate_carp_ratio_2025": ban_metrics["aggregate_carp_ratio_2025"],
                "cpue_proxy_ratio_2025": ban_metrics["cpue_proxy_ratio_2025"],
                "pressure_end": ban_metrics["pressure_end"],
                "water_end": ban_metrics["water_end"],
                "water_min": ban_metrics["water_min"],
                "water_min_year": ban_metrics["water_min_year"],
                "ban_stronger_than_noban": bool(
                    ban_metrics["aggregate_carp_ratio_2025"] > noban_metrics["aggregate_carp_ratio_2025"]
                ),
            }
    scenarios["structural_grouped_recalibration"] = {
        "perturbation": "groupwise +/-20% structural perturbation with aggregate-carp anchor re-fitted",
        "groups": structural_recalibration,
    }
    return scenarios


def run_q1_cpue_weight_sensitivity(t: np.ndarray, series: np.ndarray) -> dict:
    idx_2025 = int(np.argmin(np.abs(t - (Q1_TIME_ANCHORS["monitor_year"] - Q1_TIME_ANCHORS["policy_start"]))))
    scanned_weights = np.linspace(0.5, 1.0, 6)
    ratios = {}
    values = []
    for black_carp_weight in scanned_weights:
        weights = np.array([1.0, 1.0, 1.0, float(black_carp_weight)], dtype=float)
        cpue = cpue_proxy(series, weights=weights)
        ratio_2025 = float(_normalize(cpue)[idx_2025])
        ratios[f"{black_carp_weight:.1f}"] = ratio_2025
        values.append(ratio_2025)
    return {
        "black_carp_weight_range": [0.5, 1.0],
        "ratios_2025_by_weight": ratios,
        "min_ratio_2025": float(min(values)),
        "max_ratio_2025": float(max(values)),
    }


def build_q1_summary(
    t: np.ndarray,
    ban: np.ndarray,
    noban: np.ndarray,
    calibration: dict,
    h0_summary: dict,
    counterfactual_scan: dict,
    sensitivity: dict,
) -> dict:
    ban_metrics = q1_metrics(t, ban)
    noban_metrics = q1_metrics(t, noban)
    rel_errors = {
        "aggregate_carp_ratio_2025": float(
            abs(ban_metrics["aggregate_carp_ratio_2025"] - Q1_TARGETS["aggregate_carp_ratio_2025"]) / Q1_TARGETS["aggregate_carp_ratio_2025"]
        ),
        "cpue_proxy_ratio_2025": float(
            abs(ban_metrics["cpue_proxy_ratio_2025"] - Q1_TARGETS["cpue_proxy_ratio_2025"]) / Q1_TARGETS["cpue_proxy_ratio_2025"]
        ),
    }
    return {
        "time_anchor_years": Q1_TIME_ANCHORS,
        "targets": Q1_TARGETS,
        "fitted_parameters": {
            "consumer_scale": calibration["consumer_scale"],
            "gain_scale": calibration["gain_scale"],
            "counterfactual_h0": h0_summary["h0"],
            "cpue_weights": Q1_CPUE_WEIGHTS.tolist(),
            "calibration_loss": calibration["loss"],
            "calibration_scope": calibration["calibration_scope"],
        },
        "parameter_roles": {
            "consumer_scale": "fixed initial-state normalization; not estimated from 2025 observations",
            "gain_scale": "single fitted parameter for the 2025 aggregate-carp hard anchor",
            "counterfactual_h0": "fixed counterfactual fishing-pressure parameter; not part of observation fitting",
            "cpue_weights": "heuristic proxy weights for local consistency checking only",
        },
        "counterfactual_check": {
            "selection_rule": h0_summary["selection_rule"],
            "aggregate_lower_than_ban": h0_summary["aggregate_lower_than_ban"],
            "cpue_lower_than_ban": h0_summary["cpue_lower_than_ban"],
            "max_carp_ratio": h0_summary["max_carp_ratio"],
            "no_overshoot": h0_summary["no_overshoot"],
        },
        "counterfactual_scan": counterfactual_scan,
        "aggregate_carp_ratio_2025": {
            "target": Q1_TARGETS["aggregate_carp_ratio_2025"],
            "ban": ban_metrics["aggregate_carp_ratio_2025"],
            "noban": noban_metrics["aggregate_carp_ratio_2025"],
        },
        "cpue_proxy_ratio_2025": {
            "target": Q1_TARGETS["cpue_proxy_ratio_2025"],
            "ban": ban_metrics["cpue_proxy_ratio_2025"],
            "noban": noban_metrics["cpue_proxy_ratio_2025"],
        },
        "relative_errors": rel_errors,
        "ban": ban_metrics,
        "noban": noban_metrics,
        "milestones": {
            "ban": ban_metrics["milestones"],
            "noban": noban_metrics["milestones"],
        },
        "sensitivity": sensitivity,
        "cpue_weight_sensitivity": run_q1_cpue_weight_sensitivity(t, ban),
    }


def plot_q1_comparison(t: np.ndarray, ban: np.ndarray, noban: np.ndarray, q1_summary: dict) -> dict:
    labels = ["W", "Ph", "Z", "N", "G", "S", "B", "Q"]
    nice = {
        "W": "Aquatic plants",
        "Ph": "Phytoplankton",
        "Z": "Zooplankton",
        "N": "Benthos",
        "G": "Grass carp",
        "S": "Silver carp",
        "B": "Bighead carp",
        "Q": "Black carp",
    }

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=False)
    anchor_t_2022 = Q1_TIME_ANCHORS["gazette_year"] - Q1_TIME_ANCHORS["policy_start"]
    anchor_t_2025 = Q1_TIME_ANCHORS["monitor_year"] - Q1_TIME_ANCHORS["policy_start"]

    for idx, ax in enumerate([axes[0, 0], axes[0, 1]]):
        data = ban if idx == 0 else noban
        title = "Fishing ban" if idx == 0 else "No ban"
        for i, lab in enumerate(labels):
            ax.plot(t, _normalize(data[i]), label=nice[lab], lw=1.8)
        ax.axvline(anchor_t_2022, color="#666666", lw=1.0, ls="--")
        ax.axvline(anchor_t_2025, color="#d62728", lw=1.0, ls=":")
        ax.set_title(title)
        ax.set_ylabel("Normalized biomass")
        ax.legend(ncol=4, fontsize=8, frameon=False)
        ax.set_xlabel("Time since 2021 (years)")

    ax_obs = axes[1, 0]
    categories = ["Carp biomass ratio", "CPUE proxy ratio"]
    observed = [
        q1_summary["targets"]["aggregate_carp_ratio_2025"],
        q1_summary["targets"]["cpue_proxy_ratio_2025"],
    ]
    simulated = [
        q1_summary["aggregate_carp_ratio_2025"]["ban"],
        q1_summary["cpue_proxy_ratio_2025"]["ban"],
    ]
    x = np.arange(len(categories))
    width = 0.32
    ax_obs.bar(x - width / 2, observed, width=width, label="Observed target", color="#4c78a8")
    ax_obs.bar(x + width / 2, simulated, width=width, label="Simulated", color="#f58518")
    ax_obs.set_xticks(x)
    ax_obs.set_xticklabels(categories, rotation=8)
    ax_obs.set_ylabel("Ratio to 2021 baseline")
    ax_obs.set_title("2025 hard anchor and local consistency check")
    ax_obs.legend(frameon=False)

    ax_mech = axes[1, 1]
    phi_ban = pressure_index(ban)
    phi_noban = pressure_index(noban)
    water_ban = _normalize(ban[0])
    water_noban = _normalize(noban[0])
    ax_mech.plot(t, phi_ban, label="Phi(t) - ban", lw=2.0, color="#d62728")
    ax_mech.plot(t, phi_noban, label="Phi(t) - no ban", lw=1.8, ls="--", color="#ff9896")
    ax_mech.plot(t, water_ban, label="Water plants - ban", lw=2.0, color="#2ca02c")
    ax_mech.plot(t, water_noban, label="Water plants - no ban", lw=1.8, ls="--", color="#98df8a")
    ax_mech.axvline(anchor_t_2025, color="#666666", lw=1.0, ls=":")
    ax_mech.set_xlabel("Time since 2021 (years)")
    ax_mech.set_ylabel("Index / normalized biomass")
    ax_mech.set_title("Mechanism: pressure vs basal recovery")
    ax_mech.legend(frameon=False, fontsize=8)

    fig.suptitle("Question 1: calibrated trajectories and empirical anchors", y=0.99, fontsize=12)
    fig.tight_layout()
    _safe_savefig(fig, FIG_DIR / "fig01_q1_foodweb.png")
    plt.close(fig)

    return q1_summary


def plot_q2_comparison(t: np.ndarray, base: np.ndarray, polluted: np.ndarray) -> dict:
    labels = ["M", "D", "S", "V"]
    nice = {"M": "Forage fish", "D": "Porpoise", "S": "Sturgeon", "V": "Invader"}
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for i, lab in enumerate(labels):
        ax.plot(t, _normalize(base[i]), lw=2.0, label=f"{nice[lab]} - baseline")
    for i, lab in enumerate(labels):
        ax.plot(t, _normalize(polluted[i]), lw=1.8, ls="--", label=f"{nice[lab]} - polluted")
    ax.set_xlabel("Time (years)")
    ax.set_ylabel("Normalized biomass")
    ax.set_title("Question 2 / 5: rare species and invasion module")
    ax.legend(ncol=2, fontsize=8, frameon=False)
    fig.tight_layout()
    _safe_savefig(fig, FIG_DIR / "fig02_q2_rare_species.png")
    plt.close(fig)

    base_end = q2_end_values(base)
    polluted_end = q2_end_values(polluted)
    labels_for_ratio = ("M", "D", "A", "V")
    polluted_vs_base = {
        lab: float(polluted_end[lab] / base_end[lab] - 1.0) if base_end[lab] else None for lab in labels_for_ratio
    }
    polluted_vs_base["S"] = polluted_vs_base["A"]

    return {
        "base_end": base_end,
        "polluted_end": polluted_end,
        "polluted_vs_base_ratio": polluted_vs_base,
    }


def summarize_q2_upstream_proxy(t: np.ndarray, series: np.ndarray, basal_weight: float = Q2_PROXY_BASAL_WEIGHT) -> dict:
    basal, carp = build_ecosystem_index_components(series)
    proxy = build_ecosystem_index(series, basal_weight=basal_weight)
    idx_2025 = int(np.argmin(np.abs(t - (Q1_TIME_ANCHORS["monitor_year"] - Q1_TIME_ANCHORS["policy_start"]))))
    return {
        "definition": "E(t)=w_basal*E_basal(t)+(1-w_basal)*E_carp(t)",
        "default_weights": {
            "basal": float(basal_weight),
            "carp": float(1.0 - basal_weight),
        },
        "component_construction": {
            "E_basal": "0.30*W + 0.25*Ph + 0.25*Z + 0.20*N after within-layer normalization",
            "E_carp": "0.28*G + 0.24*S + 0.24*B + 0.24*Q after within-layer normalization",
        },
        "calibrated_2025_levels": {
            "E_basal": float(basal[idx_2025]),
            "E_carp": float(carp[idx_2025]),
            "E_total": float(proxy[idx_2025]),
            "B_carp": float(_normalize(total_carp(series))[idx_2025]),
        },
        "trajectory_diagnostics": {
            "corr_with_B_carp": {
                "E_basal": float(np.corrcoef(basal, _normalize(total_carp(series)))[0, 1]),
                "E_carp": float(np.corrcoef(carp, _normalize(total_carp(series)))[0, 1]),
            },
            "tail_std": {
                "E_basal": float(np.std(basal)),
                "E_carp": float(np.std(carp)),
            },
        },
        "choice_note": (
            "The default blend keeps the resource-side signal explicit so that the q2 forcing proxy "
            "does not collapse into a pure fish-self-feedback index; robustness is checked by the weight scan below."
        ),
    }


def run_q2_sensitivity(
    rare_base_params: RareSpeciesParams,
    t_span: tuple[float, float],
    y0_q2_base: np.ndarray,
    food_supply_ban: Callable[[float], float],
) -> dict:
    sens_params = ["barrier", "release_s", "e_d", "e_s", "a_d", "a_s"]
    sens_scale = 0.20
    sens_results: dict[str, dict[str, float]] = {}
    _, base = simulate_rare_species(rare_base_params, t_span, y0_q2_base, food_supply_ban)
    base_d = float(base[1, -1])
    base_a = float(base[2, -1])
    for pname in sens_params:
        base_val = getattr(rare_base_params, pname)
        row: dict[str, float] = {"base_value": float(base_val)}
        for direction, factor in [("plus20", 1 + sens_scale), ("minus20", 1 - sens_scale)]:
            perturbed = rare_base_params.__class__(
                **{k: (v * factor if k == pname else v) for k, v in rare_base_params.__dict__.items()}
            )
            _, sol_sens = simulate_rare_species(perturbed, t_span, y0_q2_base, food_supply_ban)
            row[f"D_{direction}"] = float(sol_sens[1, -1] / base_d - 1.0)
            row[f"A_{direction}"] = float(sol_sens[2, -1] / base_a - 1.0)
            row[f"S_{direction}"] = row[f"A_{direction}"]
        sens_results[pname] = row
    return sens_results


def run_q2_proxy_weight_scan(
    t: np.ndarray,
    ban_series: np.ndarray,
    polluted_q1_series: np.ndarray,
    t_span: tuple[float, float],
    y0_q2_base: np.ndarray,
    scenario_params: dict[str, RareSpeciesParams],
) -> dict:
    def scenario_endpoints(basal_weight: float) -> dict[str, dict[str, float]]:
        food_supply_ban = interp1d(
            t,
            build_ecosystem_index(ban_series, basal_weight=basal_weight),
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
        )
        food_supply_polluted = interp1d(
            t,
            build_ecosystem_index(polluted_q1_series, basal_weight=basal_weight),
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
        )
        endpoints = {}
        for name, params in scenario_params.items():
            food_supply = food_supply_polluted if name == "polluted" else food_supply_ban
            _, sol = simulate_rare_species(params, t_span, y0_q2_base, food_supply)
            endpoints[name] = q2_end_values(sol)
        return endpoints

    default_endpoints = scenario_endpoints(Q2_PROXY_BASAL_WEIGHT)
    samples = []
    max_d_base = 0.0
    max_a_base = 0.0
    max_d_all = 0.0
    max_a_all = 0.0
    porpoise_orders = []
    sturgeon_orders = []

    for basal_weight in Q2_PROXY_WEIGHT_SCAN:
        endpoints = scenario_endpoints(float(basal_weight))
        porpoise_order = sorted(endpoints, key=lambda name: endpoints[name]["D"], reverse=True)
        sturgeon_order = sorted(endpoints, key=lambda name: endpoints[name]["A"], reverse=True)
        porpoise_orders.append(porpoise_order)
        sturgeon_orders.append(sturgeon_order)

        local_d_all = 0.0
        local_a_all = 0.0
        for name in endpoints:
            local_d_all = max(local_d_all, abs(endpoints[name]["D"] / default_endpoints[name]["D"] - 1.0))
            local_a_all = max(local_a_all, abs(endpoints[name]["A"] / default_endpoints[name]["A"] - 1.0))
        local_d_base = abs(endpoints["base"]["D"] / default_endpoints["base"]["D"] - 1.0)
        local_a_base = abs(endpoints["base"]["A"] / default_endpoints["base"]["A"] - 1.0)
        max_d_base = max(max_d_base, local_d_base)
        max_a_base = max(max_a_base, local_a_base)
        max_d_all = max(max_d_all, local_d_all)
        max_a_all = max(max_a_all, local_a_all)

        samples.append(
            {
                "basal_weight": float(basal_weight),
                "carp_weight": float(1.0 - basal_weight),
                "scenario_endpoints": {
                    name: {"D": endpoints[name]["D"], "A": endpoints[name]["A"]} for name in endpoints
                },
                "porpoise_order": porpoise_order,
                "sturgeon_order": sturgeon_order,
                "max_abs_relative_change_base": {
                    "D": float(local_d_base),
                    "A": float(local_a_base),
                },
                "max_abs_relative_change_all_scenarios": {
                    "D": float(local_d_all),
                    "A": float(local_a_all),
                },
            }
        )

    return {
        "scan_range": [float(Q2_PROXY_WEIGHT_SCAN[0]), float(Q2_PROXY_WEIGHT_SCAN[-1])],
        "default_weights": {
            "basal": float(Q2_PROXY_BASAL_WEIGHT),
            "carp": float(1.0 - Q2_PROXY_BASAL_WEIGHT),
        },
        "samples": samples,
        "max_abs_relative_change_base": {
            "D": float(max_d_base),
            "A": float(max_a_base),
        },
        "max_abs_relative_change_all_scenarios": {
            "D": float(max_d_all),
            "A": float(max_a_all),
        },
        "stability_checks": {
            "porpoise_order_preserved": bool(all(order == porpoise_orders[0] for order in porpoise_orders)),
            "sturgeon_order_preserved": bool(all(order == sturgeon_orders[0] for order in sturgeon_orders)),
            "barrier_penalty_preserved": bool(
                all(
                    sample["scenario_endpoints"]["barrier"]["D"] < sample["scenario_endpoints"]["base"]["D"]
                    and sample["scenario_endpoints"]["barrier"]["A"] < sample["scenario_endpoints"]["base"]["A"]
                    for sample in samples
                )
            ),
            "release_lift_preserved": bool(
                all(
                    sample["scenario_endpoints"]["base"]["A"] > sample["scenario_endpoints"]["no_release"]["A"]
                    for sample in samples
                )
            ),
            "pollution_penalty_preserved": bool(
                all(
                    sample["scenario_endpoints"]["polluted"]["D"] < sample["scenario_endpoints"]["base"]["D"]
                    and sample["scenario_endpoints"]["polluted"]["A"] < sample["scenario_endpoints"]["base"]["A"]
                    for sample in samples
                )
            ),
        },
    }


def run_q2_barrier_multiplier_scan(
    t: np.ndarray,
    t_span: tuple[float, float],
    y0_q2_base: np.ndarray,
    scenario_params: dict[str, RareSpeciesParams],
    food_supply_ban: Callable[[float], float],
    food_supply_polluted: Callable[[float], float],
) -> dict:
    def scenario_endpoints(multiplier: float) -> dict[str, dict[str, float]]:
        endpoints = {}
        for name, params in scenario_params.items():
            food_supply = food_supply_polluted if name == "polluted" else food_supply_ban
            params_now = RareSpeciesParams(**{**params.__dict__, "sturgeon_barrier_multiplier": float(multiplier)})
            _, sol = simulate_rare_species(params_now, t_span, y0_q2_base, food_supply)
            endpoints[name] = q2_end_values(sol)
        return endpoints

    default_endpoints = scenario_endpoints(Q2_STURGEON_BARRIER_MULTIPLIER)
    samples = []
    max_d_base = 0.0
    max_a_base = 0.0
    max_d_all = 0.0
    max_a_all = 0.0
    porpoise_orders = []
    sturgeon_orders = []

    for multiplier in Q2_STURGEON_BARRIER_SCAN:
        endpoints = scenario_endpoints(float(multiplier))
        porpoise_order = sorted(endpoints, key=lambda name: endpoints[name]["D"], reverse=True)
        sturgeon_order = sorted(endpoints, key=lambda name: endpoints[name]["A"], reverse=True)
        porpoise_orders.append(porpoise_order)
        sturgeon_orders.append(sturgeon_order)

        local_d_all = 0.0
        local_a_all = 0.0
        for name in endpoints:
            local_d_all = max(local_d_all, abs(endpoints[name]["D"] / default_endpoints[name]["D"] - 1.0))
            local_a_all = max(local_a_all, abs(endpoints[name]["A"] / default_endpoints[name]["A"] - 1.0))
        local_d_base = abs(endpoints["base"]["D"] / default_endpoints["base"]["D"] - 1.0)
        local_a_base = abs(endpoints["base"]["A"] / default_endpoints["base"]["A"] - 1.0)
        max_d_base = max(max_d_base, local_d_base)
        max_a_base = max(max_a_base, local_a_base)
        max_d_all = max(max_d_all, local_d_all)
        max_a_all = max(max_a_all, local_a_all)

        samples.append(
            {
                "sturgeon_barrier_multiplier": float(multiplier),
                "scenario_endpoints": {
                    name: {"D": endpoints[name]["D"], "A": endpoints[name]["A"]} for name in endpoints
                },
                "porpoise_order": porpoise_order,
                "sturgeon_order": sturgeon_order,
                "max_abs_relative_change_base": {
                    "D": float(local_d_base),
                    "A": float(local_a_base),
                },
                "max_abs_relative_change_all_scenarios": {
                    "D": float(local_d_all),
                    "A": float(local_a_all),
                },
            }
        )

    return {
        "scan_range": [float(Q2_STURGEON_BARRIER_SCAN[0]), float(Q2_STURGEON_BARRIER_SCAN[-1])],
        "default_multiplier": float(Q2_STURGEON_BARRIER_MULTIPLIER),
        "samples": samples,
        "max_abs_relative_change_base": {
            "D": float(max_d_base),
            "A": float(max_a_base),
        },
        "max_abs_relative_change_all_scenarios": {
            "D": float(max_d_all),
            "A": float(max_a_all),
        },
        "stability_checks": {
            "porpoise_order_preserved": bool(all(order == porpoise_orders[0] for order in porpoise_orders)),
            "sturgeon_order_preserved": bool(all(order == sturgeon_orders[0] for order in sturgeon_orders)),
            "barrier_penalty_preserved": bool(
                all(
                    sample["scenario_endpoints"]["barrier"]["D"] < sample["scenario_endpoints"]["base"]["D"]
                    and sample["scenario_endpoints"]["barrier"]["A"] < sample["scenario_endpoints"]["base"]["A"]
                    for sample in samples
                )
            ),
            "release_lift_preserved": bool(
                all(
                    sample["scenario_endpoints"]["base"]["A"] > sample["scenario_endpoints"]["no_release"]["A"]
                    for sample in samples
                )
            ),
            "pollution_penalty_preserved": bool(
                all(
                    sample["scenario_endpoints"]["polluted"]["D"] < sample["scenario_endpoints"]["base"]["D"]
                    and sample["scenario_endpoints"]["polluted"]["A"] < sample["scenario_endpoints"]["base"]["A"]
                    for sample in samples
                )
            ),
        },
    }


def compute_q2_directional_validation(t: np.ndarray, base: np.ndarray) -> dict:
    idx = int(np.argmin(np.abs(t - Q2_DIRECTIONAL_VALIDATION_T)))
    a_ratio = float(base[2, idx] / max(base[2, 0], 1e-12))
    d_ratio = float(base[1, idx] / max(base[1, 0], 1e-12))
    return {
        "model_time": float(Q2_DIRECTIONAL_VALIDATION_T),
        "calendar_year": int(Q1_TIME_ANCHORS["policy_start"] + Q2_DIRECTIONAL_VALIDATION_T),
        "A_ratio": a_ratio,
        "D_ratio": d_ratio,
        "sturgeon_positive_growth": bool(a_ratio > 1.0),
        "porpoise_positive_growth": bool(d_ratio > 1.0),
    }


def _positive_runs(ks: np.ndarray, values: np.ndarray, min_len: int = 3) -> list[tuple[int, int]]:
    mask = values > 0
    runs = []
    start = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        if start is not None and (not flag or i == len(mask) - 1):
            end = i if flag and i == len(mask) - 1 else i - 1
            if end - start + 1 >= min_len:
                runs.append((start, end))
            start = None
    return runs


def _peak_times(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    if len(x) < 3:
        return np.array([], dtype=float)
    mid = x[1:-1]
    peak_mask = (mid > x[:-2]) & (mid >= x[2:])
    peak_idx = np.where(peak_mask)[0] + 1
    return t[peak_idx]


def _orbit_descriptors(sol, window_start: float = 90.0) -> dict:
    mask = sol.t >= window_start
    if not np.any(mask):
        mask = np.ones_like(sol.t, dtype=bool)

    t_tail = sol.t[mask]
    x1_tail = sol.y[0][mask]
    peak_times = _peak_times(t_tail, x1_tail)
    peak_intervals = np.diff(peak_times) if len(peak_times) >= 2 else np.array([], dtype=float)
    mean_peak_interval = float(np.mean(peak_intervals)) if len(peak_intervals) else None
    peak_interval_cv = float(np.std(peak_intervals) / np.mean(peak_intervals)) if len(peak_intervals) and np.mean(peak_intervals) > 0 else None

    return {
        "window_start": float(t_tail[0]),
        "window_end": float(t_tail[-1]),
        "tail_mean_x1": float(np.mean(x1_tail)),
        "tail_std_x1": float(np.std(x1_tail)),
        "x1_min": float(np.min(x1_tail)),
        "x1_max": float(np.max(x1_tail)),
        "x1_peak_to_peak": float(np.ptp(x1_tail)),
        "peak_count": int(len(peak_times)),
        "mean_peak_interval": mean_peak_interval,
        "peak_interval_cv": peak_interval_cv,
    }


def _scan_window_summary(ks: np.ndarray, mles: np.ndarray, scan_min: float = 3.0, scan_max: float = 3.4) -> dict:
    mask = (ks >= scan_min) & (ks <= scan_max)
    scan_ks = ks[mask]
    scan_mles = mles[mask]
    runs = _positive_runs(scan_ks, scan_mles, min_len=3)
    continuous_window = None
    if runs:
        start_idx, end_idx = runs[0]
        continuous_window = {
            "start": float(scan_ks[start_idx]),
            "end": float(scan_ks[end_idx]),
            "step": float(scan_ks[1] - scan_ks[0]) if len(scan_ks) > 1 else 0.0,
        }
    positive_idx = np.where(scan_mles > 0)[0]
    return {
        "scan_range": [float(scan_min), float(scan_max)],
        "continuous_positive_window": continuous_window,
        "first_positive_k": float(scan_ks[positive_idx[0]]) if len(positive_idx) else None,
        "positive_point_count": int(len(positive_idx)),
        "mle_at_3.20": float(scan_mles[int(np.argmin(np.abs(scan_ks - 3.20)))]),
        "mle_at_3.22": float(scan_mles[int(np.argmin(np.abs(scan_ks - 3.22)))]),
    }


def plot_hp_results():
    coarse_ks = np.linspace(1.4, 4.8, 44)
    fine_ks = np.linspace(3.0, 3.4, 41)
    ks = np.unique(np.concatenate([coarse_ks, fine_ks]))
    y0 = np.array([0.8, 0.2, 0.2], dtype=float)
    scan_totals = [90.0, 150.0, 200.0]
    numerical_settings = {
        "dt": 0.01,
        "transient_time": 40.0,
        "total_time": scan_totals[0],
        "initial_state": y0.tolist(),
    }
    snapshots = {}
    mle_scans = {}

    for total_time in scan_totals:
        window_values = []
        for k in ks:
            p = HPParams(k=float(k))
            window_values.append(
                lyapunov_max(
                    p,
                    y0=y0,
                    dt=numerical_settings["dt"],
                    t_trans=numerical_settings["transient_time"],
                    t_total=total_time,
                )
            )
            if total_time == scan_totals[0] and k not in snapshots:
                t = np.linspace(0, 180, 2500)
                sol = solve_ivp(lambda tt, yy: hp_rhs(tt, yy, p), (t[0], t[-1]), y0, t_eval=t, rtol=1e-7, atol=1e-9)
                snapshots[k] = sol
        mle_scans[total_time] = np.array(window_values, dtype=float)

    mles = mle_scans[scan_totals[0]]
    baseline_scan = _scan_window_summary(ks, mles)
    chaos_window = baseline_scan["continuous_positive_window"] or {
        "start": 3.22,
        "end": 3.22,
        "step": 0.0,
    }

    chaos_candidates = np.where((ks >= chaos_window["start"]) & (mles > 0))[0]
    if len(chaos_candidates):
        irregular_k = float(ks[chaos_candidates[np.argmax(mles[chaos_candidates])]])
    else:
        irregular_k = 4.8

    stable_k = 1.8
    periodic_k = 2.7
    irregular_k = float(irregular_k if irregular_k >= 3.0 else 4.8)
    stable_obs_k = min(ks, key=lambda x: abs(x - stable_k))
    periodic_obs_k = min(ks, key=lambda x: abs(x - periodic_k))
    irregular_obs_k = min(ks, key=lambda x: abs(x - irregular_k))
    stable = snapshots[stable_obs_k]
    periodic = snapshots[periodic_obs_k]
    irregular = snapshots[irregular_obs_k]

    def nearest_summary(target_k: float) -> dict:
        idx = int(np.argmin(np.abs(ks - target_k)))
        snapshot = snapshots[float(ks[idx])]
        descriptors = _orbit_descriptors(snapshot, window_start=90.0)
        return {
            "target_k": float(target_k),
            "observed_k": float(ks[idx]),
            "mle_t90": float(mles[idx]),
            "trajectory_window": {
                "start": descriptors["window_start"],
                "end": descriptors["window_end"],
            },
            "descriptors": {
                "tail_mean_x1": descriptors["tail_mean_x1"],
                "tail_std_x1": descriptors["tail_std_x1"],
                "x1_min": descriptors["x1_min"],
                "x1_max": descriptors["x1_max"],
                "x1_peak_to_peak": descriptors["x1_peak_to_peak"],
                "peak_count": descriptors["peak_count"],
                "mean_peak_interval": descriptors["mean_peak_interval"],
                "peak_interval_cv": descriptors["peak_interval_cv"],
            },
        }

    isolated_positive_candidates = [float(k) for k, mle in zip(ks, mles) if k < chaos_window["start"] and mle > 0]

    def mle_at(k: float, dt: float = 0.01, t_total: float = 90.0, y0_override: np.ndarray | None = None) -> float:
        y0_local = y0 if y0_override is None else np.array(y0_override, dtype=float)
        return float(
            lyapunov_max(
                HPParams(k=float(k)),
                y0=y0_local,
                dt=dt,
                t_trans=numerical_settings["transient_time"],
                t_total=t_total,
            )
        )

    local_bracket_checks = {
        "base_dt_0.010": {
            "dt": 0.010,
            "initial_state": y0.tolist(),
            "k_left": 3.20,
            "mle_left": mle_at(3.20, dt=0.010),
            "k_right": 3.22,
            "mle_right": mle_at(3.22, dt=0.010),
        },
        "dt_0.008": {
            "dt": 0.008,
            "initial_state": y0.tolist(),
            "k_left": 3.20,
            "mle_left": mle_at(3.20, dt=0.008),
            "k_right": 3.22,
            "mle_right": mle_at(3.22, dt=0.008),
        },
        "dt_0.012": {
            "dt": 0.012,
            "initial_state": y0.tolist(),
            "k_left": 3.20,
            "mle_left": mle_at(3.20, dt=0.012),
            "k_right": 3.22,
            "mle_right": mle_at(3.22, dt=0.012),
        },
        "y0_perturbed": {
            "dt": 0.010,
            "initial_state": [0.8005, 0.1995, 0.2],
            "k_left": 3.20,
            "mle_left": mle_at(3.20, dt=0.010, y0_override=np.array([0.8005, 0.1995, 0.2], dtype=float)),
            "k_right": 3.22,
            "mle_right": mle_at(3.22, dt=0.010, y0_override=np.array([0.8005, 0.1995, 0.2], dtype=float)),
        },
    }
    bracket_sign_stable = all(
        item["mle_left"] < 0 and item["mle_right"] > 0 for item in local_bracket_checks.values()
    )

    fig_q3, axes_q3 = plt.subplots(1, 3, figsize=(13.2, 3.9), sharey=False)
    for ax, sol, observed_k, label, color in [
        (axes_q3[0], stable, stable_obs_k, "Bounded oscillation", "#1f77b4"),
        (axes_q3[1], periodic, periodic_obs_k, "Periodic oscillation", "#2ca02c"),
        (axes_q3[2], irregular, irregular_obs_k, "Irregular sample", "#d62728"),
    ]:
        desc = _orbit_descriptors(sol, window_start=90.0)
        ax.plot(sol.t, sol.y[0], lw=1.3, color=color)
        ax.set_xlabel("Time")
        ax.set_title(
            f"{label}\nK={float(observed_k):.3f}, "
            f"$\\sigma(X_1)$={desc['tail_std_x1']:.3f}, "
            f"$CV_T$={0.0 if desc['peak_interval_cv'] is None else desc['peak_interval_cv']:.3f}"
        )
    axes_q3[0].set_ylabel("X1")
    fig_q3.tight_layout()
    _safe_savefig(fig_q3, FIG_DIR / "fig03_q3_hastings_powell.png")
    plt.close(fig_q3)

    fig_q4, axes_q4 = plt.subplots(2, 1, figsize=(10.5, 8.2), sharex=False)
    colors = {90.0: "#1f77b4", 150.0: "#ff7f0e", 200.0: "#2ca02c"}
    for total_time in scan_totals:
        label = f"$t_{{total}}$={int(total_time)}"
        axes_q4[0].plot(ks, mle_scans[total_time], lw=1.5, color=colors[total_time], label=label)
        zoom_mask = (ks >= 3.0) & (ks <= 3.4)
        axes_q4[1].plot(ks[zoom_mask], mle_scans[total_time][zoom_mask], lw=1.5, color=colors[total_time], label=label)
    for ax in axes_q4:
        ax.axhline(0.0, color="black", lw=1.0, ls="--")
    axes_q4[1].axvline(3.20, color="#555555", lw=1.0, ls=":")
    axes_q4[1].axvline(3.22, color="#999999", lw=1.0, ls=":")
    axes_q4[0].set_ylabel("Largest Lyapunov exponent")
    axes_q4[0].set_title("Finite-time MLE scan under different integration windows")
    axes_q4[0].legend(frameon=False, ncol=3)
    axes_q4[1].set_xlabel("K")
    axes_q4[1].set_ylabel("Largest Lyapunov exponent")
    axes_q4[1].set_title("Zoom near the short-window sign-crossing bracket")
    fig_q4.tight_layout()
    _safe_savefig(fig_q4, FIG_DIR / "fig04_q4_lyapunov_scan.png")
    plt.close(fig_q4)

    window_sensitivity_scan = {
        f"t_total_{int(total_time)}": _scan_window_summary(ks, mle_scans[total_time]) for total_time in scan_totals
    }

    return {
        "control_parameter": {
            "name": "K",
            "interpretation": "dimensionless effective carrying capacity",
        },
        "observation_window": {
            "start": 90.0,
            "end": 180.0,
            "observable": "X1 tail-window descriptors for q3",
        },
        "numerical_settings": numerical_settings,
        "ks": ks.tolist(),
        "mles": mles.tolist(),
        "chaos_window": chaos_window,
        "window_sensitivity_scan": window_sensitivity_scan,
        "local_bracket": {
            "left_k": 3.20,
            "right_k": 3.22,
            "criterion": "lambda(left)<0<lambda(right) under nearby numerical settings",
            "sign_stable": bracket_sign_stable,
        },
        "local_bracket_checks": local_bracket_checks,
        "irregular_rep_k": irregular_k,
        "representative_behaviors": {
            "bounded_oscillation": nearest_summary(stable_k),
            "periodic_oscillation": nearest_summary(periodic_k),
            "irregular_trajectory": nearest_summary(irregular_k),
        },
        "isolated_positive_candidates_before_window": isolated_positive_candidates,
        "diagnosis_rule": "finite-time MLE scan with a short-window baseline and cross-window drift check",
        "scope_note": (
            "finite-time MLE depends on integration-window choice; "
            "the short-window sign-crossing near 3.20--3.22 is local, while longer windows shift the first-positive region"
        ),
    }


def extended_q4_robustness_test() -> dict:
    """Broader stress test for the local Q4 chaos-candidate bracket.

    The paper's main claim is intentionally local: under the baseline scan
    settings and nearby perturbations, K=3.20 stays negative while K=3.22
    turns positive. This helper widens the test grid so the paper can report
    how far that sign-crossing survives once initial states, step sizes, and
    integration windows are pushed farther away from the baseline setup.
    """
    y0_variants = [
        ("baseline", np.array([0.80, 0.20, 0.20], dtype=float)),
        ("x1_down", np.array([0.75, 0.25, 0.20], dtype=float)),
        ("x1_up", np.array([0.85, 0.15, 0.20], dtype=float)),
        ("x3_up", np.array([0.80, 0.20, 0.25], dtype=float)),
        ("x3_down", np.array([0.80, 0.20, 0.15], dtype=float)),
    ]
    dts = [0.005, 0.008, 0.010, 0.012, 0.015]
    t_totals = [90.0, 150.0, 200.0]
    t_trans = 40.0
    k_left = 3.20
    k_right = 3.22

    def sign_outcome(mle_left: float, mle_right: float) -> str:
        if mle_left < 0 < mle_right:
            return "sign_cross"
        if mle_left >= 0 and mle_right > 0:
            return "both_positive"
        if mle_left < 0 and mle_right <= 0:
            return "both_negative"
        return "reversed_or_zero_tied"

    def aggregate(subset: list[dict]) -> dict:
        total = len(subset)
        passed = sum(1 for item in subset if item["sign_cross_detected"])
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": float(passed / total) if total else 0.0,
        }

    test_results = []
    for y0_name, y0 in y0_variants:
        for dt in dts:
            for t_total in t_totals:
                mle_left = lyapunov_max(
                    HPParams(k=k_left),
                    y0=y0,
                    dt=dt,
                    t_trans=t_trans,
                    t_total=t_total,
                )
                mle_right = lyapunov_max(
                    HPParams(k=k_right),
                    y0=y0,
                    dt=dt,
                    t_trans=t_trans,
                    t_total=t_total,
                )
                outcome = sign_outcome(float(mle_left), float(mle_right))
                test_results.append(
                    {
                        "y0_variant": y0_name,
                        "y0": y0.tolist(),
                        "dt": float(dt),
                        "t_total": float(t_total),
                        "t_trans": float(t_trans),
                        "k_left": float(k_left),
                        "k_right": float(k_right),
                        "mle_left": float(mle_left),
                        "mle_right": float(mle_right),
                        "sign_cross_detected": bool(outcome == "sign_cross"),
                        "outcome": outcome,
                    }
                )

    total_tests = len(test_results)
    overall = aggregate(test_results)

    by_y0 = {}
    for y0_name, _ in y0_variants:
        subset = [item for item in test_results if item["y0_variant"] == y0_name]
        by_y0[y0_name] = aggregate(subset)

    by_dt = {}
    for dt in dts:
        subset = [item for item in test_results if item["dt"] == dt]
        by_dt[f"dt_{dt:.3f}"] = aggregate(subset)

    by_t_total = {}
    for t_total in t_totals:
        subset = [item for item in test_results if item["t_total"] == t_total]
        by_t_total[f"t_total_{int(t_total)}"] = aggregate(subset)

    outcome_counts = {}
    for label in ("sign_cross", "both_positive", "both_negative", "reversed_or_zero_tied"):
        outcome_counts[label] = sum(1 for item in test_results if item["outcome"] == label)

    sign_cross_cases = [
        {
            "y0_variant": item["y0_variant"],
            "dt": item["dt"],
            "t_total": item["t_total"],
            "mle_left": item["mle_left"],
            "mle_right": item["mle_right"],
        }
        for item in test_results
        if item["sign_cross_detected"]
    ]
    failure_examples = [
        {
            "y0_variant": item["y0_variant"],
            "dt": item["dt"],
            "t_total": item["t_total"],
            "mle_left": item["mle_left"],
            "mle_right": item["mle_right"],
            "outcome": item["outcome"],
        }
        for item in test_results
        if not item["sign_cross_detected"]
    ][:12]

    return {
        "test_configuration": {
            "k_left": float(k_left),
            "k_right": float(k_right),
            "t_trans": float(t_trans),
            "y0_variants": {name: values.tolist() for name, values in y0_variants},
            "dt_values": dts,
            "t_total_values": t_totals,
            "total_combinations": total_tests,
        },
        "overall_statistics": overall,
        "by_initial_condition": by_y0,
        "by_step_size": by_dt,
        "by_integration_time": by_t_total,
        "outcome_counts": outcome_counts,
        "sign_cross_cases": sign_cross_cases,
        "failure_examples": failure_examples,
        "detailed_results": test_results,
        "interpretation": {
            "criterion": "MLE(K=3.20) < 0 < MLE(K=3.22) indicates a local sign-crossing bracket",
            "main_reading": (
                f"Sign crossing survives in {overall['passed']}/{total_tests} stress-test settings; "
                "the bracket should therefore be read as a local finite-time candidate rather than a universal threshold."
            ),
            "scope": "Broader stress test on the finite-time MLE bracket; results complement but do not replace the paper's baseline local check.",
        },
    }


def plot_q5_scenarios(scenarios: dict[str, np.ndarray]) -> dict:
    names = list(scenarios.keys())
    metrics = ["Food", "Porpoise", "Sturgeon", "Invader", "Health"]
    tail_window = 200

    def tail_mean(series: np.ndarray) -> float:
        return float(np.mean(_normalize(series)[-tail_window:]))

    raw_indicator_matrix = []
    end_indicator_matrix = []
    for name in names:
        _, data = scenarios[name]
        m, d, s, v = data
        raw_indicator_matrix.append([tail_mean(m), tail_mean(d), tail_mean(s), tail_mean(v)])
        end_indicator_matrix.append(
            [float(_normalize(m)[-1]), float(_normalize(d)[-1]), float(_normalize(s)[-1]), float(_normalize(v)[-1])]
        )

    raw_indicator_matrix = np.array(raw_indicator_matrix, dtype=float)
    end_indicator_matrix = np.array(end_indicator_matrix, dtype=float)
    benefit_mask = np.array([True, True, True, False], dtype=bool)
    score_matrix = _normalize_indicator_matrix(raw_indicator_matrix, benefit_mask)
    entropy = entropy_weights(score_matrix)
    critic = critic_weights(score_matrix)
    equal = np.full(4, 0.25)
    combined = _positive_normalize(0.5 * (entropy + critic))

    method_weights = {
        "entropy": entropy,
        "critic": critic,
        "combined": combined,
        "equal": equal,
    }
    method_scores = {label: score_matrix @ weights for label, weights in method_weights.items()}
    base_scores = method_scores["combined"]
    matrix = np.column_stack([raw_indicator_matrix, base_scores])

    def ranking_from_scores(scores: np.ndarray) -> list[str]:
        return sorted(names, key=lambda name: scores[names.index(name)], reverse=True)

    base_order = ranking_from_scores(base_scores)
    method_rankings = {label: ranking_from_scores(scores) for label, scores in method_scores.items()}

    rng = np.random.default_rng(20260515)
    perturbation_samples = 2000
    perturbation_orders = []
    invasion_worst_count = 0
    full_order_count = 0
    for _ in range(perturbation_samples):
        local_weights = _positive_normalize(combined * rng.uniform(0.85, 1.15, size=combined.shape[0]))
        local_scores = score_matrix @ local_weights
        local_order = ranking_from_scores(local_scores)
        perturbation_orders.append(local_order)
        if local_order == base_order:
            full_order_count += 1
        if local_order[-1] == "Ban + pollution + invasion":
            invasion_worst_count += 1

    ranking_stable = all(order == base_order for order in method_rankings.values()) and full_order_count == perturbation_samples
    invasion_worst_stable = all(order[-1] == "Ban + pollution + invasion" for order in method_rankings.values()) and (
        invasion_worst_count == perturbation_samples
    )

    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    x = np.arange(len(metrics))
    width = 0.22
    for i, name in enumerate(names):
        ax.bar(x + (i - (len(names) - 1) / 2) * width, matrix[i], width, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, max(1.05, float(matrix.max()) * 1.15))
    ax.set_ylabel("Tail-mean level / score")
    ax.set_title("Question 5: internal scenario comparison")
    ax.legend(frameon=False)
    fig.tight_layout()
    _safe_savefig(fig, FIG_DIR / "fig05_q5_scenarios.png")
    plt.close(fig)

    result = {name: {m: float(matrix[i, j]) for j, m in enumerate(metrics)} for i, name in enumerate(names)}
    ban_row = result["Ban only"]
    polluted_row = result["Ban + pollution"]
    invasion_row = result["Ban + pollution + invasion"]

    def rel_change(row_now: dict[str, float], row_ref: dict[str, float]) -> dict[str, float | None]:
        out = {}
        for key in metrics:
            ref = row_ref[key]
            out[key] = float(row_now[key] / ref - 1.0) if ref else None
        return out

    result["relative_changes"] = {
        "pollution_vs_ban_only": rel_change(polluted_row, ban_row),
        "invasion_vs_pollution": rel_change(invasion_row, polluted_row),
        "invasion_vs_ban_only": rel_change(invasion_row, ban_row),
    }
    result["end_values"] = {
        name: {
            "Food": float(end_indicator_matrix[i, 0]),
            "Porpoise": float(end_indicator_matrix[i, 1]),
            "Sturgeon": float(end_indicator_matrix[i, 2]),
            "Invader": float(end_indicator_matrix[i, 3]),
        }
        for i, name in enumerate(names)
    }
    result["robust_conclusions"] = {
        "full_ranking_stable": ranking_stable,
        "invasion_worst_stable": invasion_worst_stable,
        "base_vs_pollution_order_sensitive": not ranking_stable,
        "conservative_statement": (
            "Under entropy, CRITIC, equal, combined, and local renormalized perturbation weights, "
            "the ordering Ban only > Ban + pollution > Ban + pollution + invasion is preserved."
        ),
    }
    result["objective_weighting"] = {
        "tail_window_steps": tail_window,
        "indicator_type": {
            "Food": "benefit",
            "Porpoise": "benefit",
            "Sturgeon": "benefit",
            "Invader": "cost",
        },
        "raw_tail_means": {
            name: {
                "Food": float(raw_indicator_matrix[i, 0]),
                "Porpoise": float(raw_indicator_matrix[i, 1]),
                "Sturgeon": float(raw_indicator_matrix[i, 2]),
                "Invader": float(raw_indicator_matrix[i, 3]),
            }
            for i, name in enumerate(names)
        },
        "positive_oriented_scores": {
            name: {
                "Food": float(score_matrix[i, 0]),
                "Porpoise": float(score_matrix[i, 1]),
                "Sturgeon": float(score_matrix[i, 2]),
                "Invader": float(score_matrix[i, 3]),
            }
            for i, name in enumerate(names)
        },
        "weights": {label: [float(x) for x in weights] for label, weights in method_weights.items()},
        "method_rankings": method_rankings,
        "perturbation_test": {
            "seed": 20260515,
            "samples": perturbation_samples,
            "factor_range": [0.85, 1.15],
            "full_ranking_stability_rate": float(full_order_count / perturbation_samples),
            "invasion_worst_stability_rate": float(invasion_worst_count / perturbation_samples),
        },
    }
    result["health_window_steps"] = tail_window
    result["health_definition"] = (
        "combined entropy-CRITIC score of the positive-oriented tail-mean indicators; "
        "all weights are nonnegative and sum to 1"
    )
    result["scope_note"] = "internal scenario comparison under q2-normalized state variables; not an external ecological-health validation"
    return result


def main():
    existing_results: dict[str, dict] = {}
    existing_summary_path = OUT_DIR / "summary.json"
    if existing_summary_path.exists():
        try:
            with open(existing_summary_path, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_results = {}

    # Question 1: ban vs no-ban
    y0_q1_base = np.array([0.88, 0.82, 0.76, 0.70, 0.46, 0.42, 0.38, 0.34], dtype=float)
    t_q1 = (0.0, 10.0)
    y0_q1, ban_params, calibration = calibrate_q1(y0_q1_base, t_q1)
    t, ban = simulate_food_web(ban_params, t_q1, y0_q1)
    ban_metrics = q1_metrics(t, ban)
    noban_params, noban, h0_summary = evaluate_counterfactual_h0(ban_params, y0_q1, t_q1, ban_metrics)
    counterfactual_scan = run_q1_counterfactual_scan(ban_params, y0_q1, t_q1, ban_metrics)
    sensitivity = run_q1_sensitivity(y0_q1_base, y0_q1, ban_params, h0_summary["h0"], t_q1)
    q1_summary = build_q1_summary(t, ban, noban, calibration, h0_summary, counterfactual_scan, sensitivity)
    q1_summary = plot_q1_comparison(t, ban, noban, q1_summary)

    # Question 2 / 5: rare species module driven by food supply from Q1
    food_supply_ban = interp1d(t, build_ecosystem_index(ban), kind="linear", fill_value="extrapolate", bounds_error=False)

    y0_q2_base = np.array([0.62, 1.00, 0.14, 0.02], dtype=float)
    y0_q2_polluted = np.array([0.62, 1.00, 0.14, 0.02], dtype=float)
    rare_base_params = RareSpeciesParams(barrier=0.015, pollution=0.0, release_s=0.012, e_d=0.44, m_d=0.045)
    rare_barrier_params = RareSpeciesParams(barrier=0.05, pollution=0.0, release_s=0.012, e_d=0.44, m_d=0.045)
    rare_polluted_params = RareSpeciesParams(barrier=0.05, pollution=0.28, release_s=0.012, e_d=0.40, m_d=0.050)

    t2, base = simulate_rare_species(rare_base_params, t_q1, y0_q2_base, food_supply_ban)
    _, barrier_only = simulate_rare_species(rare_barrier_params, t_q1, y0_q2_base, food_supply_ban)

    # Polluted scenario: re-run Q1 with pollution to get degraded E(t)
    polluted_web_params = FoodWebParams(
        gain_scale=ban_params.gain_scale, h_fishing=0.0, pollution=rare_polluted_params.pollution
    )
    _, ban_polluted_q2 = simulate_food_web(polluted_web_params, t_q1, y0_q1)
    food_supply_polluted = interp1d(
        t, build_ecosystem_index(ban_polluted_q2), kind="linear", fill_value="extrapolate", bounds_error=False
    )
    _, polluted = simulate_rare_species(rare_polluted_params, t_q1, y0_q2_polluted, food_supply_polluted)
    q2_summary = plot_q2_comparison(t2, base, polluted)
    q2_summary["barrier_end"] = q2_end_values(barrier_only)
    no_release_params = RareSpeciesParams(**{**rare_base_params.__dict__, "release_s": 0.0})
    _, no_release = simulate_rare_species(no_release_params, t_q1, y0_q2_base, food_supply_ban)
    q2_summary["no_release_end"] = q2_end_values(no_release)
    q2_summary["release_lift"] = {
        "M": float(q2_summary["base_end"]["M"] - q2_summary["no_release_end"]["M"]),
        "D": float(q2_summary["base_end"]["D"] - q2_summary["no_release_end"]["D"]),
        "A": float(q2_summary["base_end"]["A"] - q2_summary["no_release_end"]["A"]),
        "S": float(q2_summary["base_end"]["A"] - q2_summary["no_release_end"]["A"]),
        "V": float(q2_summary["base_end"]["V"] - q2_summary["no_release_end"]["V"]),
    }
    q2_summary["anchors"] = {
        "policy_start_year": 2021,
        "gazette_year": 2022,
        "initial_counts": {
            "porpoise": 1249,
            "sturgeon": 438,
        },
        "attachment_1": {
            "facts": ["migration path", "barrier", "fish pass"],
            "mapped_parameter": "barrier",
        },
        "attachment_2": {
            "facts": ["food-web relations", "supplemental release"],
            "mapped_parameters": ["a_d", "a_s", "a_v", "release_s"],
        },
        "upstream_proxy": {
            "source": "Q1 ecosystem index E(t)",
            "role": "forcing input, not external observation",
        },
    }
    q2_summary["parameter_roles"] = {
        "D0_A0": "2022 gazette initial anchors for porpoise and sturgeon",
        "barrier": "attachment-1 constraint carried by the normalized corridor-loss parameter",
        "upstream_proxy": "internal food-supply proxy inherited from q1 rather than an external observation",
        "a_d_a_s_a_v": "heuristic structural priors for species interaction intensity",
        "release_s": "scenario-control parameter for artificial release rather than a fitted observation",
        "sturgeon_barrier_multiplier": "sturgeon-specific amplification of corridor blockage relative to porpoise",
    }
    q2_summary["focus_relatives"] = {
        "sturgeon_release_ratio": float(q2_summary["base_end"]["A"] / q2_summary["no_release_end"]["A"] - 1.0),
        "porpoise_barrier_ratio": float(q2_summary["barrier_end"]["D"] / q2_summary["base_end"]["D"] - 1.0),
        "sturgeon_barrier_ratio": float(q2_summary["barrier_end"]["A"] / q2_summary["base_end"]["A"] - 1.0),
        "porpoise_pollution_ratio": float(q2_summary["polluted_end"]["D"] / q2_summary["base_end"]["D"] - 1.0),
        "sturgeon_pollution_ratio": float(q2_summary["polluted_end"]["A"] / q2_summary["base_end"]["A"] - 1.0),
    }
    q2_summary["scope_note"] = "scenario output under a 2022-normalized anchor; not an independent external validation"
    q2_scenarios = {
        "base": rare_base_params,
        "barrier": rare_barrier_params,
        "polluted": rare_polluted_params,
        "no_release": no_release_params,
    }
    q2_summary["upstream_proxy"] = summarize_q2_upstream_proxy(t, ban)
    q2_summary["upstream_proxy"]["weight_scan"] = run_q2_proxy_weight_scan(
        t=t,
        ban_series=ban,
        polluted_q1_series=ban_polluted_q2,
        t_span=t_q1,
        y0_q2_base=y0_q2_base,
        scenario_params=q2_scenarios,
    )
    q2_summary["barrier_multiplier_scan"] = run_q2_barrier_multiplier_scan(
        t=t,
        t_span=t_q1,
        y0_q2_base=y0_q2_base,
        scenario_params=q2_scenarios,
        food_supply_ban=food_supply_ban,
        food_supply_polluted=food_supply_polluted,
    )
    q2_summary["directional_validation_2024"] = compute_q2_directional_validation(t2, base)

    # Q2 sensitivity analysis: ±20% perturbation on 6 key parameters
    print("[info] Running Q2 sensitivity analysis...")
    q2_summary["sensitivity"] = run_q2_sensitivity(rare_base_params, t_q1, y0_q2_base, food_supply_ban)
    print("[info] Q2 sensitivity done.")

    q34_cache_ready = (
        isinstance(existing_results.get("q3"), dict)
        and isinstance(existing_results.get("q4"), dict)
        and (FIG_DIR / "fig03_q3_hastings_powell.png").exists()
        and (FIG_DIR / "fig04_q4_lyapunov_scan.png").exists()
    )
    if q34_cache_ready:
        print("[info] Reusing existing Q3/Q4 summaries and figures; this refresh focuses on the changed Q1/Q2 outputs.")
        q3_summary = existing_results["q3"]
        hp_summary = existing_results["q4"]
    else:
        # Question 4: chaos scan
        hp_summary = plot_hp_results()

        # Extended Q4 robustness testing
        print("[info] Running extended Q4 robustness tests (75 combinations)...")
        q4_robustness = extended_q4_robustness_test()
        hp_summary["extended_robustness"] = q4_robustness
        print(
            "[info] Q4 robustness: "
            f"{q4_robustness['overall_statistics']['passed']}/{q4_robustness['overall_statistics']['total']} "
            f"tests kept the sign-crossing bracket ({q4_robustness['overall_statistics']['pass_rate']*100:.1f}%)"
        )

        q3_summary = {
            "control_parameter": hp_summary["control_parameter"],
            "observation_window": hp_summary["observation_window"],
            "representative_behaviors": hp_summary["representative_behaviors"],
            "scope_note": "representative long-term trajectories only; finite-time MLE drift is handled separately in q4",
        }

    # Question 5: scenario comparison (reuses food_supply_polluted from Q2 block above)
    y0_q2_inv = np.array([0.62, 1.00, 0.14, 0.10], dtype=float)
    t3, rare_mixed = simulate_rare_species(
        RareSpeciesParams(barrier=0.05, pollution=0.28, release_s=0.012, a_v=0.48, e_v=0.42),
        t_q1,
        y0_q2_inv,
        food_supply_polluted,
    )

    scenarios = {
        "Ban only": (t2, base),
        "Ban + pollution": (t2, polluted),
        "Ban + pollution + invasion": (t3, rare_mixed),
    }
    q5_summary = plot_q5_scenarios(scenarios)
    q5_summary["scenario_setup"] = {
        "Ban only": {
            "barrier": 0.015,
            "pollution": 0.0,
            "release_s": 0.012,
            "a_v": 0.36,
            "e_v": 0.38,
            "initial_state": [0.62, 1.00, 0.14, 0.02],
        },
        "Ban + pollution": {
            "barrier": 0.05,
            "pollution": 0.28,
            "release_s": 0.012,
            "a_v": 0.36,
            "e_v": 0.38,
            "initial_state": [0.62, 1.00, 0.14, 0.02],
        },
        "Ban + pollution + invasion": {
            "barrier": 0.05,
            "pollution": 0.28,
            "release_s": 0.012,
            "a_v": 0.48,
            "e_v": 0.42,
            "initial_state": [0.62, 1.00, 0.14, 0.10],
        },
    }

    results = {
        "q1": q1_summary,
        "q2": q2_summary,
        "q3": q3_summary,
        "q4": hp_summary,
        "q5": q5_summary,
    }
    summary_path = OUT_DIR / "summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except PermissionError:
        summary_path = Path.cwd() / f"summary_refresh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[warn] skipped locked summary path, wrote {summary_path.name} instead")

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
