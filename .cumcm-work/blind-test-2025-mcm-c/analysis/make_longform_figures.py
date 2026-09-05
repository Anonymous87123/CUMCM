from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "results"
FIG = ROOT / "paper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def rolling_by_year() -> None:
    data = pd.read_csv(RESULTS / "rolling_validation.csv")
    data = data.loc[data.model.isin(["persistence", "blend50"])]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.1), constrained_layout=True)
    for ax, target, title in zip(axes, ["total", "gold"], ["Total medals", "Gold medals"]):
        part = data.loc[data.target.eq(target)]
        for model, style in [("persistence", "--o"), ("blend50", "-s")]:
            row = part.loc[part.model.eq(model)].sort_values("year")
            ax.plot(row.year, row.mae, style, label=model)
        ax.set_title(title)
        ax.set_xlabel("Target edition")
        ax.set_ylabel("MAE")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    fig.savefig(FIG / "rolling_by_year.pdf", bbox_inches="tight")
    plt.close(fig)


def forecast_change() -> None:
    forecast = pd.read_csv(RESULTS / "forecast_2028.csv")
    panel = pd.read_csv(RESULTS / "model_panel.csv")
    last = panel.loc[panel.Year.eq(2024), ["NOC", "target_total"]].rename(
        columns={"target_total": "last_total"}
    )
    top = forecast.nlargest(12, "pred_total").merge(last, on="NOC", how="left")
    top = top.sort_values("pred_total")
    fig, ax = plt.subplots(figsize=(8.4, 5.8), constrained_layout=True)
    y = range(len(top))
    ax.barh(list(y), top.last_total, color="#b7c3d0", label="2024 official total")
    ax.barh(list(y), top.pred_total, color="#2c6e9f", alpha=0.75, label="2028 prediction")
    ax.set_yticks(list(y), top.country)
    ax.set_xlabel("Total medals")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(FIG / "forecast_change.pdf", bbox_inches="tight")
    plt.close(fig)


def coach_episodes() -> None:
    episodes = pd.read_csv(RESULTS / "coach_like_episodes.csv").head(10).iloc[::-1]
    labels = episodes.country + " / " + episodes.Sport
    fig, ax = plt.subplots(figsize=(8.5, 5.8), constrained_layout=True)
    y = range(len(episodes))
    ax.barh(list(y), episodes.observed_medals, color="#4f81a8", label="Observed")
    ax.barh(list(y), episodes.expected_medals, color="#d9a441", alpha=0.85, label="Expected")
    ax.set_yticks(list(y), labels)
    ax.set_xlabel("Two-edition medal sum")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(FIG / "coach_episode_comparison.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    rolling_by_year()
    forecast_change()
    coach_episodes()
