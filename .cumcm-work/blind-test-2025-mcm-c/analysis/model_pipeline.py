from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "2025_Problem_C_Data"
OUT = ROOT / "analysis" / "results"
FIG = ROOT / "paper" / "figures"
SEED = 20250814

YEARS = [1896, 1900, 1904, 1908, 1912, 1920, 1924, 1928, 1932, 1936,
         1948, 1952, 1956, 1960, 1964, 1968, 1972, 1976, 1980, 1984,
         1988, 1992, 1996, 2000, 2004, 2008, 2012, 2016, 2020, 2024]
MODERN = [y for y in YEARS if y >= 1996]
HOST_NOC = {
    1988: "KOR", 1992: "ESP", 1996: "USA", 2000: "AUS", 2004: "GRE",
    2008: "CHN", 2012: "GBR", 2016: "BRA", 2020: "JPN", 2024: "FRA",
    2028: "USA",
}
PSEUDO_NOCS = {"AIN", "EOR", "IOA", "IOP", "MIX", "ROC", "WIF", "ZZX"}


def read_csv(name: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(DATA / name, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(name)


def canonical_sport(value: str) -> str:
    value = str(value).split(",")[0].strip()
    mapping = {
        "3x3 Basketball": "Basketball",
        "Artistic Gymnastics": "Gymnastics",
        "Rhythmic Gymnastics": "Gymnastics",
        "Trampoline Gymnastics": "Gymnastics",
        "Trampolining": "Gymnastics",
        "Artistic Swimming": "Aquatics",
        "Synchronized Swimming": "Aquatics",
        "Swimming": "Aquatics",
        "Marathon Swimming": "Aquatics",
        "Diving": "Aquatics",
        "Water Polo": "Aquatics",
        "Beach Volleyball": "Volleyball",
        "Canoe Slalom": "Canoeing",
        "Canoe Sprint": "Canoeing",
        "Cycling BMX Freestyle": "Cycling",
        "Cycling BMX Racing": "Cycling",
        "Cycling Mountain Bike": "Cycling",
        "Cycling Road": "Cycling",
        "Cycling Track": "Cycling",
        "Equestrianism": "Equestrian",
        "Hockey": "Field hockey",
        "Jeu De Paume": "Jeu de Paume",
        "Motorboating": "Water Motorsports",
        "Racquets": "Rackets",
        "Rugby Sevens": "Rugby",
        "Tug-Of-War": "Tug of War",
        "Baseball": "Baseball and Softball",
        "Softball": "Baseball and Softball",
        "Baseball/Softball": "Baseball and Softball",
    }
    return mapping.get(value, value)


def prepare() -> tuple[pd.DataFrame, pd.DataFrame, dict[int, dict[str, int]], dict[str, str]]:
    athletes = read_csv("summerOly_athletes.csv")
    official = read_csv("summerOly_medal_counts.csv")
    athletes["SportC"] = athletes["Sport"].map(canonical_sport)
    current_names = (
        athletes.sort_values("Year")
        .groupby("NOC")["Team"]
        .agg(lambda x: re.sub(r"-\d+$", "", str(x.iloc[-1])))
        .to_dict()
    )

    participation = (
        athletes.groupby(["Year", "NOC"], as_index=False)
        .agg(
            athletes=("Name", "nunique"),
            sports=("SportC", "nunique"),
            event_entries=("Event", "nunique"),
        )
    )

    medal_rows = athletes.loc[athletes["Medal"].ne("No medal")].drop_duplicates(
        ["Year", "NOC", "SportC", "Event", "Medal"]
    )
    reconstructed = (
        medal_rows.assign(Gold=lambda x: x["Medal"].eq("Gold").astype(int))
        .groupby(["Year", "NOC"], as_index=False)
        .agg(Gold=("Gold", "sum"), Total=("Medal", "size"))
    )
    team_to_noc = (
        athletes.assign(TeamBase=lambda x: x.Team.str.replace(r"-\d+$", "", regex=True))
        .groupby(["Year", "TeamBase"])["NOC"]
        .agg(lambda x: x.value_counts().index[0])
        .to_dict()
    )
    official["TeamBase"] = official.NOC
    official["NOC_code"] = [team_to_noc.get((int(y), str(name))) for y, name in zip(official.Year, official.TeamBase)]
    direct_aliases = {
        "Hong Kong": "HKG", "Iran": "IRI", "Ivory Coast": "CIV",
        "Moldova": "MDA", "North Korea": "PRK", "Refugee Olympic Team": "EOR",
        "Turkey": "TUR", "South Korea": "KOR", "Czech Republic": "CZE",
        "FR Yugoslavia": "SCG", "ROC": "ROC",
        "Independent Olympic Athletes": "IOA", "Independent Olympic Participants": "IOP",
    }
    for idx in official.index[official.NOC_code.isna()]:
        official.loc[idx, "NOC_code"] = direct_aliases.get(official.loc[idx, "NOC"])
    fallback = {
        (1992, "Independent Olympic Participants"): "IOP",
        (1908, "Russian Empire"): "RUS", (1912, "Russian Empire"): "RUS",
        (1896, "Mixed team"): "MIX", (1900, "Mixed team"): "MIX", (1904, "Mixed team"): "MIX",
        (1948, "Ceylon"): "SRI", (1956, "United Team of Germany"): "GER",
        (1960, "United Team of Germany"): "GER", (1964, "United Team of Germany"): "GER",
        (1960, "Egypt"): "EGY", (1960, "Formosa"): "TPE", (1960, "British West Indies"): "WIF",
        (1968, "Taiwan"): "TPE", (1988, "Virgin Islands"): "ISV",
    }
    for idx in official.index[official.NOC_code.isna()]:
        official.loc[idx, "NOC_code"] = fallback.get((int(official.loc[idx, "Year"]), official.loc[idx, "NOC"]))
    targets = official.loc[official.NOC_code.notna(), ["Year", "NOC_code", "Gold", "Total"]].rename(columns={"NOC_code": "NOC"})
    for _, row in official.loc[(official.Year == 2024) & official.NOC_code.notna()].iterrows():
        current_names[str(row.NOC_code)] = str(row.NOC)
    panel = participation.merge(targets, on=["Year", "NOC"], how="left")
    panel[["Gold", "Total"]] = panel[["Gold", "Total"]].fillna(0).astype(int)

    event_counts = {
        int(year): group.groupby("SportC")["Event"].nunique().astype(int).to_dict()
        for year, group in athletes.groupby("Year")
    }
    return athletes, panel, event_counts, current_names


def prior_rows(panel: pd.DataFrame, noc: str, year: int) -> pd.DataFrame:
    return panel.loc[(panel.NOC == noc) & (panel.Year < year)].sort_values("Year")


def opportunity_score(
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
    noc: str,
    year: int,
    schedule_year: int | None = None,
) -> float:
    prev_years = [y for y in YEARS if y < year][-3:]
    hist = medal_sport.loc[(medal_sport.NOC == noc) & medal_sport.Year.isin(prev_years)]
    global_hist = medal_sport.loc[medal_sport.Year.isin(prev_years)]
    country = hist.groupby("SportC").Medals.sum()
    total = global_hist.groupby("SportC").Medals.sum()
    share = country.div(total).replace([np.inf, -np.inf], np.nan).fillna(0)
    sched = event_counts.get(schedule_year or year, event_counts[2024])
    return float(sum(sched.get(sport, 0) * value for sport, value in share.items()))


def feature_row(
    panel: pd.DataFrame,
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
    noc: str,
    year: int,
    schedule_year: int | None = None,
) -> dict[str, float | int | str]:
    hist = prior_rows(panel, noc, year)
    last = hist.iloc[-1] if len(hist) else None
    last2 = hist.iloc[-2] if len(hist) >= 2 else None
    tail3 = hist.tail(3)
    weights = np.array([0.2, 0.3, 0.5])[-len(tail3):]
    weights = weights / weights.sum() if len(weights) else weights
    ewm_total = float(np.dot(tail3.Total, weights)) if len(tail3) else 0.0
    ewm_gold = float(np.dot(tail3.Gold, weights)) if len(tail3) else 0.0
    current_events = sum(event_counts.get(schedule_year or year, event_counts[2024]).values())
    previous_years = [y for y in YEARS if y < year]
    previous_olympic = previous_years[-1] if previous_years else year
    previous_events = sum(event_counts.get(previous_olympic, event_counts[2024]).values())
    return {
        "Year": year,
        "NOC": noc,
        "lag_total": float(last.Total) if last is not None else 0.0,
        "lag_gold": float(last.Gold) if last is not None else 0.0,
        "ewm_total": ewm_total,
        "ewm_gold": ewm_gold,
        "trend_total": float(last.Total - last2.Total) if last2 is not None else 0.0,
        "trend_gold": float(last.Gold - last2.Gold) if last2 is not None else 0.0,
        "lag_athletes": float(last.athletes) if last is not None else 0.0,
        "lag_sports": float(last.sports) if last is not None else 0.0,
        "lag_event_entries": float(last.event_entries) if last is not None else 0.0,
        "participation_editions": int(len(hist)),
        "medal_editions": int((hist.Total > 0).sum()),
        "host": int(HOST_NOC.get(year) == noc),
        "post_host": int(HOST_NOC.get(previous_olympic) == noc),
        "event_total": int(current_events),
        "lag_event_total": int(previous_events),
        "event_scale": float(current_events / previous_events) if previous_events else 1.0,
        "opportunity": opportunity_score(
            medal_sport, event_counts, noc, year, schedule_year=schedule_year
        ),
    }


FEATURES = [
    "lag_total", "lag_gold", "ewm_total", "ewm_gold", "trend_total", "trend_gold",
    "lag_athletes", "lag_sports", "lag_event_entries", "participation_editions",
    "medal_editions", "host", "post_host", "event_total", "lag_event_total",
    "event_scale", "opportunity",
]


def host_adjusted_prediction(train: pd.DataFrame, test: pd.DataFrame, target: str) -> np.ndarray:
    lag_col = f"lag_{target}"
    target_col = f"target_{target}"
    base_train = train[lag_col] * train.event_scale
    host_residuals = train.loc[train.host.eq(1), target_col] - base_train.loc[train.host.eq(1)]
    bonus = float(host_residuals.median()) if len(host_residuals) >= 2 else 0.0
    base = test[lag_col].to_numpy(float) * test.event_scale.to_numpy(float)
    adjusted = base + bonus * test.host.to_numpy(float) - bonus * test.post_host.to_numpy(float)
    return np.clip(adjusted, 0, None)


def build_model_panel(
    athletes: pd.DataFrame,
    panel: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    medal_rows = athletes.loc[athletes.Medal.ne("No medal")].drop_duplicates(
        ["Year", "NOC", "SportC", "Event", "Medal"]
    )
    medal_sport = (
        medal_rows.groupby(["Year", "NOC", "SportC"], as_index=False)
        .size().rename(columns={"size": "Medals"})
    )
    rows = []
    for year in MODERN:
        for noc in sorted(panel.loc[panel.Year == year, "NOC"].unique()):
            row = feature_row(panel, medal_sport, event_counts, noc, year)
            target = panel.loc[(panel.Year == year) & (panel.NOC == noc)].iloc[0]
            row.update(target_total=int(target.Total), target_gold=int(target.Gold))
            rows.append(row)
    return pd.DataFrame(rows), medal_sport


def candidate_models(target: str) -> dict[str, object]:
    return {
        "persistence": None,
        "host_adjusted": None,
        "blend25": None,
        "blend50": None,
        "ridge_log": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", TransformedTargetRegressor(
                regressor=Ridge(alpha=8.0), func=np.log1p, inverse_func=np.expm1
            )),
        ]),
        "poisson_hgb": HistGradientBoostingRegressor(
            loss="poisson", max_depth=3, learning_rate=0.05, max_iter=240,
            min_samples_leaf=12, l2_regularization=1.0, random_state=SEED,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=320, max_depth=8, min_samples_leaf=3,
            max_features=0.8, random_state=SEED, n_jobs=1,
        ),
    }


def rolling_validation(model_panel: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_col = f"target_{target}"
    lag_col = f"lag_{target}"
    records, predictions = [], []
    for val_year in [2008, 2012, 2016, 2020, 2024]:
        train = model_panel.loc[(model_panel.Year < val_year) & (model_panel.Year >= 1996)]
        test = model_panel.loc[model_panel.Year == val_year]
        for name, model in candidate_models(target).items():
            if name == "persistence":
                pred = test[lag_col].to_numpy(float)
            elif name == "host_adjusted":
                pred = host_adjusted_prediction(train, test, target)
            elif name in {"blend25", "blend50"}:
                rf = candidate_models(target)["random_forest"]
                rf.fit(train[FEATURES], train[target_col])
                rf_pred = np.clip(rf.predict(test[FEATURES]), 0, None)
                base = host_adjusted_prediction(train, test, target)
                weight = 0.25 if name == "blend25" else 0.50
                pred = (1 - weight) * base + weight * rf_pred
            else:
                model.fit(train[FEATURES], train[target_col])
                pred = model.predict(test[FEATURES])
            pred = np.clip(pred, 0, None)
            actual = test[target_col].to_numpy(float)
            records.append({
                "target": target,
                "year": val_year,
                "model": name,
                "mae": mean_absolute_error(actual, pred),
                "rmse": math.sqrt(mean_squared_error(actual, pred)),
                "top20_mae": mean_absolute_error(
                    actual[np.argsort(actual)[-20:]], pred[np.argsort(actual)[-20:]]
                ),
            })
            predictions.extend({
                "target": target, "year": val_year, "model": name,
                "NOC": noc, "actual": float(a), "pred": float(p),
            } for noc, a, p in zip(test.NOC, actual, pred))
    return pd.DataFrame(records), pd.DataFrame(predictions)


def fit_and_forecast(
    model_panel: pd.DataFrame,
    panel: pd.DataFrame,
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
    target: str,
    best_model: str,
    oof: pd.DataFrame,
) -> pd.DataFrame:
    candidates = sorted(set(panel.loc[panel.Year == 2024, "NOC"].unique()) - PSEUDO_NOCS)
    future = pd.DataFrame([
        feature_row(panel, medal_sport, event_counts, noc, 2028, schedule_year=2024)
        for noc in candidates
    ])
    train = model_panel.loc[model_panel.Year >= 1996]
    if best_model == "persistence":
        point = future[f"lag_{target}"].to_numpy(float)
    elif best_model == "host_adjusted":
        point = host_adjusted_prediction(train, future, target)
    elif best_model in {"blend25", "blend50"}:
        rf = candidate_models(target)["random_forest"]
        rf.fit(train[FEATURES], train[f"target_{target}"])
        rf_pred = np.clip(rf.predict(future[FEATURES]), 0, None)
        base = host_adjusted_prediction(train, future, target)
        weight = 0.25 if best_model == "blend25" else 0.50
        point = (1 - weight) * base + weight * rf_pred
    else:
        model = candidate_models(target)[best_model]
        model.fit(train[FEATURES], train[f"target_{target}"])
        point = np.clip(model.predict(future[FEATURES]), 0, None)

    selected = oof.loc[oof.model == best_model].copy()
    selected["resid"] = selected.actual - selected.pred
    bins = pd.cut(selected["pred"], [-np.inf, 0.75, 3, 10, np.inf], labels=False)
    future_bins = pd.cut(point, [-np.inf, 0.75, 3, 10, np.inf], labels=False)
    lows, highs = [], []
    global_q = selected.resid.quantile([0.05, 0.95]).to_dict()
    for b, p in zip(future_bins, point):
        r = selected.loc[bins == b, "resid"]
        if len(r) < 20:
            q05, q95 = global_q[0.05], global_q[0.95]
        else:
            q05, q95 = r.quantile([0.05, 0.95])
        lows.append(max(0.0, p + q05))
        highs.append(max(p, p + q95))
    return pd.DataFrame({
        "NOC": candidates,
        f"pred_{target}": point,
        f"lo_{target}": lows,
        f"hi_{target}": highs,
    })


def first_medal_model(
    model_panel: pd.DataFrame,
    panel: pd.DataFrame,
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    rows = []
    for year in MODERN:
        for noc in sorted(panel.loc[panel.Year == year, "NOC"].unique()):
            hist = prior_rows(panel, noc, year)
            if hist.Total.sum() > 0:
                continue
            row = feature_row(panel, medal_sport, event_counts, noc, year)
            row["first_medal"] = int(
                panel.loc[(panel.Year == year) & (panel.NOC == noc), "Total"].iloc[0] > 0
            )
            rows.append(row)
    first_panel = pd.DataFrame(rows)
    cls_features = [
        "lag_athletes", "lag_sports", "lag_event_entries", "participation_editions",
        "host", "event_total",
    ]
    oof = []
    for year in [2008, 2012, 2016, 2020, 2024]:
        train = first_panel.loc[first_panel.Year < year]
        test = first_panel.loc[first_panel.Year == year]
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.35, class_weight="balanced", max_iter=3000)),
        ])
        pipe.fit(train[cls_features], train.first_medal)
        prob = pipe.predict_proba(test[cls_features])[:, 1]
        oof.extend(zip(test.first_medal.astype(int), prob))

    eligible = []
    for noc in sorted(panel.loc[panel.Year == 2024, "NOC"].unique()):
        if noc in PSEUDO_NOCS:
            continue
        if panel.loc[(panel.NOC == noc) & (panel.Year <= 2024), "Total"].sum() == 0:
            eligible.append(feature_row(panel, medal_sport, event_counts, noc, 2028, 2024))
    future = pd.DataFrame(eligible)
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=0.35, class_weight="balanced", max_iter=3000)),
    ])
    pipe.fit(first_panel[cls_features], first_panel.first_medal)
    raw_prob = pipe.predict_proba(future[cls_features])[:, 1]

    # Balanced fitting improves ranking but inflates probabilities. Calibrate by the
    # observed rolling prevalence while retaining the fitted odds ratios.
    y_oof = np.array([x[0] for x in oof])
    p_oof = np.array([x[1] for x in oof])
    observed = y_oof.mean()
    predicted = p_oof.mean()
    odds_scale = (observed / (1 - observed)) / (predicted / (1 - predicted))
    odds = raw_prob / np.clip(1 - raw_prob, 1e-9, None) * odds_scale
    prob = odds / (1 + odds)
    pred = future[["NOC", "lag_athletes", "lag_sports", "participation_editions"]].copy()
    pred["probability"] = prob
    pred = pred.sort_values("probability", ascending=False)

    rng = np.random.default_rng(SEED)
    draws = (rng.random((50000, len(prob))) < prob).sum(axis=1)
    summary = {
        "rolling_brier_raw": float(brier_score_loss(y_oof, p_oof)),
        "rolling_prevalence": float(observed),
        "raw_probability_mean": float(predicted),
        "expected_first_medal_countries": float(prob.sum()),
        "count_lo90": float(np.quantile(draws, 0.05)),
        "count_hi90": float(np.quantile(draws, 0.95)),
        "prob_at_least_one": float((draws >= 1).mean()),
    }
    return pred, summary


def coach_like_effects(
    athletes: pd.DataFrame,
    panel: pd.DataFrame,
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    part = (
        athletes.groupby(["Year", "NOC", "SportC"], as_index=False)
        .agg(athletes=("Name", "nunique"), events=("Event", "nunique"))
    )
    sport_panel = part.merge(medal_sport, on=["Year", "NOC", "SportC"], how="left")
    sport_panel.Medals = sport_panel.Medals.fillna(0)
    rows = []
    for _, row in sport_panel.loc[sport_panel.Year >= 2000].iterrows():
        hist = sport_panel.loc[
            (sport_panel.NOC == row.NOC) & (sport_panel.SportC == row.SportC) &
            (sport_panel.Year < row.Year)
        ].sort_values("Year")
        tail = hist.tail(3)
        lag = float(tail.Medals.iloc[-1]) if len(tail) else 0.0
        avg = float(tail.Medals.mean()) if len(tail) else 0.0
        lag_a = float(tail.athletes.iloc[-1]) if len(tail) else 0.0
        rows.append({
            "Year": int(row.Year), "NOC": row.NOC, "SportC": row.SportC,
            "target": float(row.Medals), "lag": lag, "avg3": avg,
            "athletes": float(row.athletes), "lag_athletes": lag_a,
            "events": float(row.events), "host": int(HOST_NOC.get(row.Year) == row.NOC),
        })
    sp = pd.DataFrame(rows)
    feats = ["lag", "avg3", "athletes", "lag_athletes", "events", "host"]
    pred_parts = []
    for year in sorted(sp.Year.unique()):
        train = sp.loc[sp.Year < year]
        test = sp.loc[sp.Year == year].copy()
        if len(train) < 100:
            continue
        model = HistGradientBoostingRegressor(
            loss="poisson", max_depth=3, max_iter=180, learning_rate=0.06,
            min_samples_leaf=15, l2_regularization=1.5, random_state=SEED,
        )
        model.fit(train[feats], train.target)
        test["expected"] = np.clip(model.predict(test[feats]), 0, None)
        test["residual"] = test.target - test.expected
        test["z"] = test.residual / np.sqrt(test.expected + 1)
        pred_parts.append(test)
    resid = pd.concat(pred_parts, ignore_index=True)
    episodes = []
    for (noc, sport), group in resid.groupby(["NOC", "SportC"]):
        g = group.sort_values("Year").reset_index(drop=True)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if b.Year - a.Year not in (4, 5):
                continue
            if a.residual > 0 and b.residual > 0:
                episodes.append({
                    "NOC": noc, "Sport": sport, "start_year": int(a.Year),
                    "end_year": int(b.Year), "observed_medals": a.target + b.target,
                    "expected_medals": a.expected + b.expected,
                    "excess_medals": a.residual + b.residual,
                    "score": a.z + b.z,
                })
    episodes = pd.DataFrame(episodes).sort_values(
        ["score", "excess_medals"], ascending=False
    )

    recent = sport_panel.loc[sport_panel.Year.isin([2020, 2024])].groupby(
        ["NOC", "SportC"], as_index=False
    ).agg(athletes=("athletes", "mean"), medals=("Medals", "mean"))
    recent["conversion"] = recent.medals / recent.athletes.clip(lower=1)
    q75 = recent.loc[recent.athletes >= 5].groupby("SportC").conversion.quantile(0.75)
    recent["frontier"] = recent.SportC.map(q75).fillna(0)
    recent["gain_raw"] = (recent.frontier - recent.conversion).clip(lower=0) * recent.athletes
    recent["estimated_gain"] = recent.gain_raw.clip(upper=5)
    overall_2024 = panel.loc[panel.Year == 2024, ["NOC", "Total"]]
    rec = recent.merge(overall_2024, on="NOC", how="left")
    rec = rec.loc[(rec.athletes >= 8) & (rec.Total.between(1, 40))]
    recommendations = (
        rec.sort_values(["estimated_gain", "athletes"], ascending=False)
        .drop_duplicates("NOC").head(12)
    )
    return episodes.head(30), recommendations


def sport_scenarios(
    forecast: pd.DataFrame,
    medal_sport: pd.DataFrame,
    event_counts: dict[int, dict[str, int]],
    current_names: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    recent = medal_sport.loc[medal_sport.Year.isin([2016, 2020, 2024])]
    country = recent.groupby(["NOC", "SportC"]).Medals.sum()
    global_total = recent.groupby("SportC").Medals.sum()
    share = country.div(global_total, level="SportC").rename("medal_share").reset_index()
    top_nocs = forecast.nlargest(15, "pred_total").NOC
    marginal = share.loc[share.NOC.isin(top_nocs)].copy()
    marginal["country"] = marginal.NOC.map(current_names).fillna(marginal.NOC)
    marginal = marginal.sort_values(["NOC", "medal_share"], ascending=[True, False])

    concentration = []
    for noc, group in recent.groupby("NOC"):
        vals = group.groupby("SportC").Medals.sum()
        total = vals.sum()
        if total <= 0:
            continue
        shares = vals / total
        concentration.append({
            "NOC": noc, "hhi": float((shares ** 2).sum()),
            "top_sport_share": float(shares.max()), "recent_medals": float(total),
            "top_sport": str(shares.idxmax()),
        })
    return marginal, pd.DataFrame(concentration)


def make_figures(
    validation: pd.DataFrame,
    forecast: pd.DataFrame,
    first: pd.DataFrame,
    concentration: pd.DataFrame,
    current_names: dict[str, str],
) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    avg = validation.groupby(["target", "model"], as_index=False).mae.mean()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for i, target in enumerate(["total", "gold"]):
        sub = avg.loc[avg.target == target]
        x = np.arange(len(sub)) + (i - 0.5) * 0.34
        ax.bar(x, sub.mae, width=0.34, label=target)
    ax.set_xticks(np.arange(len(sub)))
    ax.set_xticklabels(sub.model, rotation=15)
    ax.set_ylabel("Rolling-validation MAE")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "validation_mae.pdf")
    plt.close(fig)

    top = forecast.nlargest(15, "pred_total").sort_values("pred_total")
    labels = [current_names.get(x, x) for x in top.NOC]
    fig, ax = plt.subplots(figsize=(8.2, 6.2))
    ax.errorbar(
        top.pred_total, np.arange(len(top)),
        xerr=[top.pred_total - top.lo_total, top.hi_total - top.pred_total],
        fmt="o", capsize=3, color="#2c6e9b",
    )
    ax.set_yticks(np.arange(len(top)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Projected total medals (90% empirical interval)")
    fig.tight_layout()
    fig.savefig(FIG / "forecast_top15.pdf")
    plt.close(fig)

    topf = first.head(12).sort_values("probability")
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.barh([current_names.get(x, x) for x in topf.NOC], topf.probability, color="#5f9e6e")
    ax.set_xlabel("Probability of first Olympic medal")
    ax.set_xlim(0, max(0.35, topf.probability.max() * 1.15))
    fig.tight_layout()
    fig.savefig(FIG / "first_medal_probabilities.pdf")
    plt.close(fig)

    plot = concentration.loc[concentration.recent_medals >= 3].copy()
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.scatter(plot.recent_medals, plot.hhi, alpha=0.65, s=28)
    # Label a few interpretable concentration examples rather than stacking
    # every HHI=1 point at the same coordinate.
    label_nocs = ["KEN", "JAM", "KGZ", "JOR", "FIN"]
    label_offsets = {"KEN": (5, -15), "JAM": (5, 7), "KGZ": (5, 5), "JOR": (5, 5), "FIN": (5, 5)}
    for noc in label_nocs:
        rows = plot.loc[plot.NOC.eq(noc)]
        if rows.empty:
            continue
        row = rows.iloc[0]
        ax.annotate(
            current_names.get(row.NOC, row.NOC),
            (row.recent_medals, row.hhi),
            xytext=label_offsets.get(noc, (5, 5)),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xscale("log")
    ax.set_xlabel("Medals in 2016--2024 (log scale)")
    ax.set_ylabel("Sport concentration (HHI)")
    fig.tight_layout()
    fig.savefig(FIG / "portfolio_concentration.pdf")
    plt.close(fig)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    athletes, panel, event_counts, current_names = prepare()
    model_panel, medal_sport = build_model_panel(athletes, panel, event_counts)

    validation_parts, oof_parts = [], []
    for target in ["total", "gold"]:
        v, o = rolling_validation(model_panel, target)
        validation_parts.append(v)
        oof_parts.append(o)
    validation = pd.concat(validation_parts, ignore_index=True)
    oof = pd.concat(oof_parts, ignore_index=True)
    avg = validation.groupby(["target", "model"], as_index=False).mae.mean()
    best = {}
    for target in ["total", "gold"]:
        sub = validation.loc[validation.target == target].groupby("model").agg(
            mae=("mae", "mean"), top20_mae=("top20_mae", "mean")
        )
        composite = 0.35 * sub.mae / sub.loc["persistence", "mae"] + 0.65 * sub.top20_mae / sub.loc["persistence", "top20_mae"]
        winner = composite.idxmin()
        # A complex model must improve the combined all-country/top-table score
        # by at least 2%; otherwise the persistence baseline is retained.
        if winner != "persistence" and composite[winner] > 0.98:
            winner = "persistence"
        best[target] = winner

    total_fc = fit_and_forecast(
        model_panel, panel, medal_sport, event_counts, "total", best["total"], oof
    )
    gold_fc = fit_and_forecast(
        model_panel, panel, medal_sport, event_counts, "gold", best["gold"], oof
    )
    forecast = total_fc.merge(gold_fc, on="NOC")
    target_total_medals = float(panel.loc[panel.Year == 2024, "Total"].sum())
    target_gold_medals = float(panel.loc[panel.Year == 2024, "Gold"].sum())
    for stem, target_sum in [("total", target_total_medals), ("gold", target_gold_medals)]:
        scale = target_sum / forecast[f"pred_{stem}"].sum()
        forecast[f"pred_{stem}"] *= scale
        forecast[f"lo_{stem}"] *= scale
        forecast[f"hi_{stem}"] *= scale
    forecast["pred_gold"] = np.minimum(forecast.pred_gold, forecast.pred_total)
    forecast["lo_total"] = np.minimum(forecast.lo_total, forecast.pred_total)
    forecast["hi_total"] = np.maximum(forecast.hi_total, forecast.pred_total)
    forecast["lo_gold"] = np.minimum.reduce([
        forecast.lo_gold, forecast.pred_gold, forecast.lo_total
    ])
    forecast["hi_gold"] = np.minimum(
        np.maximum(forecast.hi_gold, forecast.pred_gold), forecast.hi_total
    )
    forecast["country"] = forecast.NOC.map(current_names).fillna(forecast.NOC)
    forecast = forecast.sort_values(["pred_gold", "pred_total"], ascending=False)

    first, first_summary = first_medal_model(model_panel, panel, medal_sport, event_counts)
    first["country"] = first.NOC.map(current_names).fillna(first.NOC)
    episodes, recommendations = coach_like_effects(
        athletes, panel, medal_sport, event_counts
    )
    episodes["country"] = episodes.NOC.map(current_names).fillna(episodes.NOC)
    recommendations["country"] = recommendations.NOC.map(current_names).fillna(recommendations.NOC)
    marginal, concentration = sport_scenarios(forecast, medal_sport, event_counts, current_names)
    concentration["country"] = concentration.NOC.map(current_names).fillna(concentration.NOC)

    validation.to_csv(OUT / "rolling_validation.csv", index=False)
    oof.to_csv(OUT / "rolling_predictions.csv", index=False)
    forecast.to_csv(OUT / "forecast_2028.csv", index=False)
    first.to_csv(OUT / "first_medal_probabilities.csv", index=False)
    episodes.to_csv(OUT / "coach_like_episodes.csv", index=False)
    recommendations.to_csv(OUT / "coach_investment_candidates.csv", index=False)
    marginal.to_csv(OUT / "sport_event_marginal_shares.csv", index=False)
    concentration.to_csv(OUT / "sport_portfolio_concentration.csv", index=False)
    model_panel.to_csv(OUT / "model_panel.csv", index=False)

    summary = {
        "best_models": best,
        "validation_mean": avg.to_dict(orient="records"),
        "first_medal": first_summary,
        "program_data_boundary": {
            "latest_available_year": 2024,
            "base_2028_schedule": "carry forward the 2024 sport-event structure",
            "scenario_interface": "one additional event changes a country's expectation by its 2016-2024 medal share in that sport",
        },
        "target_reconstruction": {
            "definition": "official medal-count table mapped year by year from country labels to athlete-table NOC codes",
            "sport_level_definition": "deduplicate athlete medal rows by Year-NOC-canonical sport-Event-Medal",
            "reason": "the official table is the country-level target; athlete rows are used only for sport attribution because team events repeat one medal across several athletes",
        },
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_figures(validation, forecast, first, concentration, current_names)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nTOP FORECAST\n", forecast.head(20).to_string(index=False))
    print("\nFIRST MEDAL\n", first.head(15).to_string(index=False))
    print("\nCOACH-LIKE EPISODES\n", episodes.head(12).to_string(index=False))
    print("\nRECOMMENDATIONS\n", recommendations.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
