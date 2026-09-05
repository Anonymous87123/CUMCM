from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "paper" / "figures"
HORIZON = 8 * 3600.0
SEED = 20180915
POSITIONS = np.array([0, 0, 1, 1, 2, 2, 3, 3], dtype=int)

PARAMETER_SETS = {
    "set1": {"travel": [0, 20, 33, 46], "one": 560, "first": 400, "second": 378, "odd": 28, "even": 31, "clean": 25},
    "set2": {"travel": [0, 23, 41, 59], "one": 580, "first": 280, "second": 500, "odd": 30, "even": 35, "clean": 30},
    "set3": {"travel": [0, 18, 32, 46], "one": 545, "first": 455, "second": 182, "odd": 27, "even": 32, "clean": 25},
}


@dataclass
class CNC:
    stage: int
    state: str = "empty"
    ready: float = 0.0
    finish_kind: str = "good"
    busy_time: float = 0.0


@dataclass
class Simulation:
    completed: int
    scrapped: int
    failures: int
    rgv_busy: float
    rgv_wait: float
    cnc_utilization: list[float]
    actions: list[dict] = field(default_factory=list)


def service_time(index: int, params: dict) -> float:
    return float(params["odd"] if index % 2 == 0 else params["even"])


def movement_time(start: int, destination: int, params: dict) -> float:
    return float(params["travel"][abs(start - destination)])


def update_states(cncs: list[CNC], time: float) -> tuple[int, int]:
    failures = scraps = 0
    for cnc in cncs:
        if cnc.state == "processing" and cnc.ready <= time + 1.0e-9:
            if cnc.finish_kind == "failure":
                cnc.state = "empty"
                failures += 1
                scraps += 1
            else:
                cnc.state = "done"
    return failures, scraps


def begin_processing(
    cnc: CNC,
    start: float,
    duration: float,
    rng: np.random.Generator,
    failure_probability: float,
) -> None:
    cnc.state = "processing"
    if rng.random() < failure_probability:
        fail_after = rng.uniform(0.0, duration)
        repair = rng.uniform(600.0, 1200.0)
        cnc.ready = start + fail_after + repair
        cnc.finish_kind = "failure"
        cnc.busy_time += min(duration, fail_after)
    else:
        cnc.ready = start + duration
        cnc.finish_kind = "good"
        cnc.busy_time += duration


def candidate_score(
    index: int,
    cnc: CNC,
    time: float,
    rgv_position: int,
    params: dict,
    policy: str,
) -> tuple[float, float, int]:
    travel = movement_time(rgv_position, POSITIONS[index], params)
    arrival = time + travel
    wait = max(0.0, cnc.ready - arrival) if cnc.state == "processing" else 0.0
    if policy == "nearest":
        return travel + wait, cnc.ready, index
    if policy == "earliest-finish":
        return max(arrival, cnc.ready) + service_time(index, params), travel, index
    # Balance waiting against travel and prefer a completed machine over an
    # empty one when both are reachable at nearly the same time.
    completion_credit = -0.35 * params.get("clean", 0) if cnc.state == "done" else 0.0
    return travel + 0.8 * wait + completion_credit, cnc.ready, index


def simulate(
    params: dict,
    stages: tuple[int, ...],
    policy: str,
    seed: int,
    failure_probability: float = 0.0,
    keep_log: bool = False,
) -> Simulation:
    rng = np.random.default_rng(seed)
    cncs = [CNC(stage=stage) for stage in stages]
    one_stage = all(stage == 1 for stage in stages)
    time = 0.0
    rgv_position = 0
    carrying_intermediate = False
    completed = failures = scrapped = 0
    rgv_busy = rgv_wait = 0.0
    actions: list[dict] = []

    while time < HORIZON:
        new_failures, new_scraps = update_states(cncs, time)
        failures += new_failures
        scrapped += new_scraps

        eligible: list[int] = []
        if one_stage:
            eligible = [i for i, cnc in enumerate(cncs) if cnc.state in {"empty", "done"}]
        elif carrying_intermediate:
            eligible = [
                i
                for i, cnc in enumerate(cncs)
                if cnc.stage == 2 and cnc.state in {"empty", "done"}
            ]
        else:
            eligible = [
                i
                for i, cnc in enumerate(cncs)
                if (cnc.stage == 1 and cnc.state in {"empty", "done"})
                or (cnc.stage == 2 and cnc.state == "done")
            ]

        if not eligible:
            next_ready = min(
                (cnc.ready for cnc in cncs if cnc.state == "processing"),
                default=HORIZON,
            )
            if next_ready <= time + 1.0e-9:
                next_ready = time + 1.0
            rgv_wait += max(0.0, min(next_ready, HORIZON) - time)
            time = min(next_ready, HORIZON)
            continue

        index = min(
            eligible,
            key=lambda i: candidate_score(i, cncs[i], time, rgv_position, params, policy),
        )
        cnc = cncs[index]
        travel = movement_time(rgv_position, POSITIONS[index], params)
        start = time
        rgv_busy += min(travel, max(0.0, HORIZON - time))
        time += travel
        if cnc.state == "processing" and cnc.ready > time:
            wait_duration = cnc.ready - time
            rgv_wait += min(wait_duration, max(0.0, HORIZON - time))
            time = cnc.ready
            new_failures, new_scraps = update_states(cncs, time)
            failures += new_failures
            scrapped += new_scraps
        if time >= HORIZON:
            break

        action = ""
        service = service_time(index, params)
        had_final = False
        if one_stage:
            had_final = cnc.state == "done"
            action = "unload-final-load-raw" if had_final else "load-raw"
            rgv_busy += min(service, max(0.0, HORIZON - time))
            time += service
            begin_processing(cnc, time, params["one"], rng, failure_probability)
            if had_final:
                rgv_busy += min(params["clean"], max(0.0, HORIZON - time))
                time += params["clean"]
                if time <= HORIZON:
                    completed += 1
        elif carrying_intermediate:
            had_final = cnc.state == "done"
            action = "unload-final-load-stage2" if had_final else "load-stage2"
            rgv_busy += min(service, max(0.0, HORIZON - time))
            time += service
            carrying_intermediate = False
            begin_processing(cnc, time, params["second"], rng, failure_probability)
            if had_final:
                rgv_busy += min(params["clean"], max(0.0, HORIZON - time))
                time += params["clean"]
                if time <= HORIZON:
                    completed += 1
        elif cnc.stage == 1:
            had_intermediate = cnc.state == "done"
            action = "unload-stage1-load-raw" if had_intermediate else "load-raw-stage1"
            rgv_busy += min(service, max(0.0, HORIZON - time))
            time += service
            begin_processing(cnc, time, params["first"], rng, failure_probability)
            carrying_intermediate = had_intermediate
        else:
            action = "unload-final-stage2"
            total_service = service + params["clean"]
            rgv_busy += min(total_service, max(0.0, HORIZON - time))
            time += total_service
            cnc.state = "empty"
            if time <= HORIZON:
                completed += 1

        if keep_log:
            actions.append(
                {
                    "start": start,
                    "end": min(time, HORIZON),
                    "cnc": index + 1,
                    "position": int(POSITIONS[index]),
                    "action": action,
                    "completed_total": completed,
                }
            )
        rgv_position = int(POSITIONS[index])

    return Simulation(
        completed=completed,
        scrapped=scrapped,
        failures=failures,
        rgv_busy=rgv_busy,
        rgv_wait=rgv_wait,
        cnc_utilization=[min(cnc.busy_time, HORIZON) / HORIZON for cnc in cncs],
        actions=actions,
    )


def stage_allocations() -> list[tuple[int, ...]]:
    allocations = []
    for first_count in range(2, 7):
        for first_indices in itertools.combinations(range(8), first_count):
            first_set = set(first_indices)
            allocations.append(tuple(1 if i in first_set else 2 for i in range(8)))
    return allocations


def deterministic_study() -> tuple[dict, pd.DataFrame]:
    summary = {}
    rows = []
    policies = ("nearest", "earliest-finish", "balanced")
    allocations = stage_allocations()
    for set_index, (name, params) in enumerate(PARAMETER_SETS.items()):
        one_results = {}
        for policy in policies:
            result = simulate(params, (1,) * 8, policy, SEED + set_index, keep_log=True)
            one_results[policy] = result
            rows.append({"parameter_set": name, "case": "one-stage", "policy": policy, "allocation": "all", "completed": result.completed})

        two_candidates = []
        for policy in policies:
            for allocation in allocations:
                result = simulate(params, allocation, policy, SEED + set_index)
                two_candidates.append((result.completed, policy, allocation, result))
                rows.append({"parameter_set": name, "case": "two-stage", "policy": policy, "allocation": "".join(map(str, allocation)), "completed": result.completed})
        best_two = max(two_candidates, key=lambda item: (item[0], -sum(item[2])))
        best_one_policy, best_one = max(one_results.items(), key=lambda item: item[1].completed)
        best_two_full = simulate(params, best_two[2], best_two[1], SEED + set_index, keep_log=True)
        summary[name] = {
            "one_stage": {
                "policy": best_one_policy,
                "completed": best_one.completed,
                "rgv_busy_fraction": best_one.rgv_busy / HORIZON,
                "rgv_wait_fraction": best_one.rgv_wait / HORIZON,
                "mean_cnc_utilization": float(np.mean(best_one.cnc_utilization)),
                "actions": best_one.actions,
            },
            "two_stage": {
                "policy": best_two[1],
                "allocation": list(best_two[2]),
                "first_stage_cncs": [i + 1 for i, stage in enumerate(best_two[2]) if stage == 1],
                "second_stage_cncs": [i + 1 for i, stage in enumerate(best_two[2]) if stage == 2],
                "completed": best_two_full.completed,
                "rgv_busy_fraction": best_two_full.rgv_busy / HORIZON,
                "rgv_wait_fraction": best_two_full.rgv_wait / HORIZON,
                "mean_cnc_utilization": float(np.mean(best_two_full.cnc_utilization)),
                "actions": best_two_full.actions,
            },
        }
    return summary, pd.DataFrame(rows)


def failure_study(deterministic: dict) -> tuple[dict, pd.DataFrame]:
    records = []
    report = {}
    for set_index, (name, params) in enumerate(PARAMETER_SETS.items()):
        report[name] = {}
        for case in ("one_stage", "two_stage"):
            config = deterministic[name][case]
            stages = (1,) * 8 if case == "one_stage" else tuple(config["allocation"])
            values = []
            for run in range(200):
                result = simulate(
                    params,
                    stages,
                    config["policy"],
                    SEED + 1000 * set_index + run,
                    failure_probability=0.01,
                )
                values.append(result.completed)
                records.append({"parameter_set": name, "case": case, "run": run, "completed": result.completed, "scrapped": result.scrapped, "failures": result.failures})
            array = np.asarray(values, dtype=float)
            report[name][case] = {
                "runs": 200,
                "mean_completed": float(np.mean(array)),
                "std_completed": float(np.std(array, ddof=1)),
                "q05_completed": float(np.quantile(array, 0.05)),
                "median_completed": float(np.median(array)),
                "q95_completed": float(np.quantile(array, 0.95)),
            }
    return report, pd.DataFrame(records)


def plot_results(deterministic: dict, candidates: pd.DataFrame, failures: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.unicode_minus": False})
    labels = list(PARAMETER_SETS)
    one = [deterministic[name]["one_stage"]["completed"] for name in labels]
    two = [deterministic[name]["two_stage"]["completed"] for name in labels]
    x = np.arange(len(labels))
    figure, axis = plt.subplots(figsize=(7.6, 4.2))
    axis.bar(x - 0.18, one, 0.36, label="one-stage", color="#315f76")
    axis.bar(x + 0.18, two, 0.36, label="two-stage", color="#ad6a32")
    axis.set(xticks=x, xticklabels=labels, ylabel="completed products / shift")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "throughput.pdf")
    plt.close(figure)

    best_by_policy = candidates.groupby(["parameter_set", "case", "policy"], as_index=False)["completed"].max()
    pivot = best_by_policy.pivot(index=["parameter_set", "case"], columns="policy", values="completed")
    figure, axis = plt.subplots(figsize=(8.5, 4.5))
    pivot.plot(kind="bar", ax=axis, color=["#315f76", "#ad6a32", "#577b55"])
    axis.set(ylabel="best completed products", xlabel="parameter set and process case")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "policy_comparison.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.5, 4.5))
    groups = []
    names = []
    for parameter_set in labels:
        for case in ("one_stage", "two_stage"):
            groups.append(failures.loc[(failures.parameter_set == parameter_set) & (failures.case == case), "completed"].to_numpy())
            names.append(f"{parameter_set}\n{case}")
    axis.boxplot(groups, tick_labels=names, showfliers=False)
    axis.set_ylabel("completed products under 1% failure")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "failure_distribution.pdf")
    plt.close(figure)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    deterministic, candidates = deterministic_study()
    failure_report, failure_rows = failure_study(deterministic)
    candidates.to_csv(RESULTS / "strategy_candidates.csv", index=False, encoding="utf-8-sig")
    failure_rows.to_csv(RESULTS / "failure_runs.csv", index=False, encoding="utf-8-sig")
    for name in deterministic:
        for case in ("one_stage", "two_stage"):
            pd.DataFrame(deterministic[name][case]["actions"]).to_csv(
                RESULTS / f"schedule_{name}_{case}.csv", index=False, encoding="utf-8-sig"
            )
            deterministic[name][case].pop("actions")
    plot_results(deterministic, candidates, failure_rows)
    summary = {
        "seed": SEED,
        "horizon_seconds": HORIZON,
        "policies": ["nearest", "earliest-finish", "balanced"],
        "deterministic": deterministic,
        "failure_probability_per_processing_start": 0.01,
        "failure_repair_seconds": [600, 1200],
        "failure_monte_carlo": failure_report,
        "claim_boundary": "allocation search is exhaustive over 2--6 first-stage CNCs; dispatch results are policy-specific feasible schedules, not a proof over all possible dynamic policies",
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
