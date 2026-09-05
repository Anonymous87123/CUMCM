from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "paper" / "figures"
HORIZON = 8 * 3600.0


def load_inputs() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    candidates = pd.read_csv(RESULTS / "strategy_candidates.csv", encoding="utf-8-sig")
    failures = pd.read_csv(RESULTS / "failure_runs.csv", encoding="utf-8-sig")
    return summary, candidates, failures


def candidate_diagnostics(candidates: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    rows: list[dict] = []
    report: dict[str, dict] = {}
    two_stage = candidates.loc[candidates["case"] == "two-stage"].copy()
    two_stage["allocation"] = two_stage["allocation"].astype(str).str.zfill(8)
    two_stage["first_stage_count"] = two_stage["allocation"].str.count("1")

    for parameter_set in sorted(candidates["parameter_set"].unique()):
        report[parameter_set] = {}
        for case in ("one-stage", "two-stage"):
            case_rows = candidates.loc[
                (candidates["parameter_set"] == parameter_set)
                & (candidates["case"] == case)
            ]
            report[parameter_set][case] = {}
            for policy in sorted(case_rows["policy"].unique()):
                values = case_rows.loc[case_rows["policy"] == policy, "completed"]
                best = int(values.max())
                entry = {
                    "candidate_count": int(len(values)),
                    "best_completed": best,
                    "median_completed": float(values.median()),
                    "q25_completed": float(values.quantile(0.25)),
                    "q75_completed": float(values.quantile(0.75)),
                    "best_tie_count": int((values == best).sum()),
                }
                report[parameter_set][case][policy] = entry
                rows.append(
                    {
                        "parameter_set": parameter_set,
                        "case": case,
                        "policy": policy,
                        **entry,
                    }
                )

        allocation_counts = Counter(two_stage.loc[
            two_stage["parameter_set"] == parameter_set, "first_stage_count"
        ])
        report[parameter_set]["enumeration"] = {
            "allocation_policy_pairs": int(sum(allocation_counts.values())),
            "unique_allocations": int(
                two_stage.loc[two_stage["parameter_set"] == parameter_set, "allocation"].nunique()
            ),
            "pairs_by_first_stage_count": {
                str(key): int(value) for key, value in sorted(allocation_counts.items())
            },
        }
    return report, pd.DataFrame(rows)


def schedule_diagnostics(summary: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    report: dict[str, dict] = {}
    schedule_rows: list[dict] = []
    bound_rows: list[dict] = []
    parameter_values = {
        "set1": {"one": 560.0, "first": 400.0, "second": 378.0},
        "set2": {"one": 580.0, "first": 280.0, "second": 500.0},
        "set3": {"one": 545.0, "first": 455.0, "second": 182.0},
    }

    for parameter_set, cases in summary["deterministic"].items():
        report[parameter_set] = {}
        for case_key, case_label in (("one_stage", "one-stage"), ("two_stage", "two-stage")):
            path = RESULTS / f"schedule_{parameter_set}_{case_key}.csv"
            frame = pd.read_csv(path, encoding="utf-8-sig")
            completed_change = frame["completed_total"].diff().fillna(frame["completed_total"])
            completion_times = frame.loc[completed_change > 0, "end"].to_numpy(dtype=float)
            intervals = np.diff(completion_times) if len(completion_times) > 1 else np.array([])
            action_counts = {
                str(key): int(value) for key, value in frame["action"].value_counts().sort_index().items()
            }
            expected = int(cases[case_key]["completed"])
            observed = int(frame["completed_total"].max()) if len(frame) else 0
            nondecreasing = bool((frame["completed_total"].diff().fillna(0) >= 0).all())
            report[parameter_set][case_key] = {
                "rows": int(len(frame)),
                "completed_from_log": observed,
                "completed_matches_summary": observed == expected,
                "completed_counter_nondecreasing": nondecreasing,
                "first_completion_second": float(completion_times[0]) if len(completion_times) else None,
                "last_completion_second": float(completion_times[-1]) if len(completion_times) else None,
                "mean_completion_interval_second": float(intervals.mean()) if len(intervals) else None,
                "std_completion_interval_second": float(intervals.std(ddof=1)) if len(intervals) > 1 else 0.0,
                "max_completion_interval_second": float(intervals.max()) if len(intervals) else None,
                "action_counts": action_counts,
            }
            schedule_rows.append(
                {
                    "parameter_set": parameter_set,
                    "case": case_label,
                    "completed": observed,
                    "first_completion_second": report[parameter_set][case_key]["first_completion_second"],
                    "last_completion_second": report[parameter_set][case_key]["last_completion_second"],
                    "mean_interval_second": report[parameter_set][case_key]["mean_completion_interval_second"],
                    "std_interval_second": report[parameter_set][case_key]["std_completion_interval_second"],
                    "max_interval_second": report[parameter_set][case_key]["max_completion_interval_second"],
                }
            )

            params = parameter_values[parameter_set]
            if case_key == "one_stage":
                process_bound = 8.0 * HORIZON / params["one"]
                first_count = 8
                second_count = 0
            else:
                allocation = cases[case_key]["allocation"]
                first_count = int(sum(stage == 1 for stage in allocation))
                second_count = 8 - first_count
                process_bound = min(
                    first_count * HORIZON / params["first"],
                    second_count * HORIZON / params["second"],
                )
            bound_rows.append(
                {
                    "parameter_set": parameter_set,
                    "case": case_label,
                    "first_stage_cncs": first_count,
                    "second_stage_cncs": second_count,
                    "processing_relaxation_bound": process_bound,
                    "completed": observed,
                    "fraction_of_processing_bound": observed / process_bound,
                }
            )
    return report, pd.DataFrame(schedule_rows), pd.DataFrame(bound_rows)


def failure_diagnostics(summary: dict, failures: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    report: dict[str, dict] = {}
    rows: list[dict] = []
    for parameter_set in sorted(failures["parameter_set"].unique()):
        report[parameter_set] = {}
        for case_key, case_label in (("one_stage", "one-stage"), ("two_stage", "two-stage")):
            deterministic = int(summary["deterministic"][parameter_set][case_key]["completed"])
            values = failures.loc[
                (failures["parameter_set"] == parameter_set)
                & (failures["case"] == case_key),
                "completed",
            ].to_numpy(dtype=float)
            losses = deterministic - values
            entry = {
                "runs": int(len(values)),
                "deterministic_completed": deterministic,
                "mean_loss": float(losses.mean()),
                "median_loss": float(np.median(losses)),
                "q95_loss": float(np.quantile(losses, 0.95)),
                "max_loss": float(losses.max()),
                "probability_at_least_95_percent_of_deterministic": float(
                    np.mean(values >= 0.95 * deterministic)
                ),
                "mean_scrapped": float(
                    failures.loc[
                        (failures["parameter_set"] == parameter_set)
                        & (failures["case"] == case_key),
                        "scrapped",
                    ].mean()
                ),
            }
            report[parameter_set][case_key] = entry
            rows.append({"parameter_set": parameter_set, "case": case_label, **entry})
    return report, pd.DataFrame(rows)


def plot_all(
    summary: dict,
    candidates: pd.DataFrame,
    failures: pd.DataFrame,
    schedule_rows: pd.DataFrame,
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.unicode_minus": False})

    two = candidates.loc[candidates["case"] == "two-stage"].copy()
    two["allocation"] = two["allocation"].astype(str).str.zfill(8)
    two["first_stage_count"] = two["allocation"].str.count("1")
    figure, axes = plt.subplots(1, 3, figsize=(10.6, 3.6), sharey=False)
    for axis, parameter_set in zip(axes, sorted(two["parameter_set"].unique())):
        group = two.loc[two["parameter_set"] == parameter_set]
        values = [group.loc[group["first_stage_count"] == count, "completed"] for count in range(2, 7)]
        axis.boxplot(values, tick_labels=range(2, 7), showfliers=False)
        axis.set(title=parameter_set, xlabel="first-stage CNC count")
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("completed products")
    figure.tight_layout()
    figure.savefig(FIGURES / "allocation_landscape.pdf")
    plt.close(figure)

    frame = pd.read_csv(RESULTS / "schedule_set1_two_stage.csv", encoding="utf-8-sig")
    frame = frame.loc[frame["start"] < 3600].copy()
    colors = {
        "load-raw-stage1": "#6d8f72",
        "unload-stage1-load-raw": "#3e6b57",
        "load-stage2": "#c4874f",
        "unload-final-load-stage2": "#a35f2f",
        "unload-final-stage2": "#7a4b35",
    }
    figure, axis = plt.subplots(figsize=(10.2, 4.4))
    for row in frame.itertuples(index=False):
        axis.broken_barh(
            [(row.start, max(row.end - row.start, 1.0))],
            (row.cnc - 0.38, 0.76),
            facecolors=colors.get(row.action, "#577b9d"),
        )
    axis.set(
        xlim=(0, 3600),
        ylim=(0.5, 8.5),
        yticks=range(1, 9),
        xlabel="shift time / s",
        ylabel="CNC index",
        title="set1 two-stage RGV service events in the first hour",
    )
    axis.grid(axis="x", alpha=0.2)
    figure.tight_layout()
    figure.savefig(FIGURES / "schedule_first_hour.pdf")
    plt.close(figure)

    labels: list[str] = []
    intervals: list[np.ndarray] = []
    for parameter_set in ("set1", "set2", "set3"):
        for case_key, short in (("one_stage", "1"), ("two_stage", "2")):
            frame = pd.read_csv(
                RESULTS / f"schedule_{parameter_set}_{case_key}.csv",
                encoding="utf-8-sig",
            )
            changes = frame["completed_total"].diff().fillna(frame["completed_total"])
            times = frame.loc[changes > 0, "end"].to_numpy(dtype=float)
            intervals.append(np.diff(times))
            labels.append(f"{parameter_set}\n{short}-stage")
    figure, axis = plt.subplots(figsize=(9.0, 4.4))
    axis.boxplot(intervals, tick_labels=labels, showfliers=False)
    axis.set(ylabel="completion interval / s")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "completion_intervals.pdf")
    plt.close(figure)

    loss_groups: list[np.ndarray] = []
    loss_labels: list[str] = []
    for parameter_set in ("set1", "set2", "set3"):
        for case_key, short in (("one_stage", "1"), ("two_stage", "2")):
            deterministic = summary["deterministic"][parameter_set][case_key]["completed"]
            values = failures.loc[
                (failures["parameter_set"] == parameter_set)
                & (failures["case"] == case_key),
                "completed",
            ].to_numpy(dtype=float)
            loss_groups.append(deterministic - values)
            loss_labels.append(f"{parameter_set}\n{short}-stage")
    figure, axis = plt.subplots(figsize=(9.0, 4.4))
    axis.boxplot(loss_groups, tick_labels=loss_labels, showfliers=False)
    axis.set(ylabel="loss against no-failure schedule / products")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "failure_loss.pdf")
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9.0, 4.4))
    x = np.arange(len(schedule_rows))
    busy = []
    wait = []
    cnc = []
    labels = []
    for row in schedule_rows.itertuples(index=False):
        key = "one_stage" if row.case == "one-stage" else "two_stage"
        entry = summary["deterministic"][row.parameter_set][key]
        busy.append(entry["rgv_busy_fraction"])
        wait.append(entry["rgv_wait_fraction"])
        cnc.append(entry["mean_cnc_utilization"])
        labels.append(f"{row.parameter_set}\n{row.case[0]}")
    axis.bar(x - 0.25, busy, 0.25, label="RGV busy", color="#315f76")
    axis.bar(x, wait, 0.25, label="RGV wait", color="#ad6a32")
    axis.bar(x + 0.25, cnc, 0.25, label="mean CNC utilization", color="#577b55")
    axis.set(xticks=x, xticklabels=labels, ylabel="fraction of shift", ylim=(0, 1.08))
    axis.legend(ncols=3)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURES / "resource_utilization.pdf")
    plt.close(figure)


def main() -> None:
    summary, candidates, failures = load_inputs()
    candidate_report, policy_rows = candidate_diagnostics(candidates)
    schedule_report, schedule_rows, bound_rows = schedule_diagnostics(summary)
    failure_report, failure_rows = failure_diagnostics(summary, failures)

    checks = {
        "all_schedule_totals_match_summary": all(
            item["completed_matches_summary"]
            for cases in schedule_report.values()
            for item in cases.values()
        ),
        "all_completion_counters_nondecreasing": all(
            item["completed_counter_nondecreasing"]
            for cases in schedule_report.values()
            for item in cases.values()
        ),
        "candidate_rows": int(len(candidates)),
        "failure_rows": int(len(failures)),
    }
    diagnostics = {
        "candidate_search": candidate_report,
        "schedules": schedule_report,
        "capacity_bounds": bound_rows.to_dict(orient="records"),
        "failures": failure_report,
        "checks": checks,
    }
    (RESULTS / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    policy_rows.to_csv(RESULTS / "strategy_by_policy.csv", index=False, encoding="utf-8-sig")
    schedule_rows.to_csv(RESULTS / "schedule_diagnostics.csv", index=False, encoding="utf-8-sig")
    bound_rows.to_csv(RESULTS / "capacity_bounds.csv", index=False, encoding="utf-8-sig")
    failure_rows.to_csv(RESULTS / "failure_loss_summary.csv", index=False, encoding="utf-8-sig")
    plot_all(summary, candidates, failures, schedule_rows)
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
