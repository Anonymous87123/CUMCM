from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "2025_Problem_C_Data"
OUT = ROOT / "audit" / "data_audit.json"


def read_csv(name: str) -> pd.DataFrame:
    path = DATA / name
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"cannot decode {path}")


def normalize_name(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"-\d+$", "", text)
    text = re.sub(r"\s+", " ", text)
    aliases = {
        "United States of America": "United States",
        "Great Britain": "Great Britain",
        "People's Republic of China": "China",
        "Republic of Korea": "South Korea",
        "Korea": "South Korea",
        "Russian Federation": "Russia",
        "Czechia": "Czech Republic",
    }
    return aliases.get(text, text)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    athletes = read_csv("summerOly_athletes.csv")
    medals = read_csv("summerOly_medal_counts.csv")
    hosts = read_csv("summerOly_hosts.csv")
    programs = read_csv("summerOly_programs.csv")

    athletes["Team_norm"] = athletes["Team"].map(normalize_name)
    medals["NOC_norm"] = medals["NOC"].map(normalize_name)

    current_teams = set(athletes.loc[athletes["Year"] == 2024, "Team_norm"])
    current_medal_names = set(medals.loc[medals["Year"] == 2024, "NOC_norm"])
    current_noc_map = (
        athletes.loc[athletes["Year"] == 2024]
        .groupby("NOC")["Team_norm"]
        .agg(lambda x: x.value_counts().index[0])
        .sort_index()
    )

    medal_rows = athletes.loc[athletes["Medal"].ne("No medal")].copy()
    raw_medal_athletes = len(medal_rows)
    unique_country_event_medals = len(
        medal_rows.drop_duplicates(["Year", "NOC", "Sport", "Event", "Medal"])
    )

    exact_by_year = []
    for year in sorted(set(medals["Year"]) & set(athletes["Year"])):
        medal_names = set(medals.loc[medals["Year"] == year, "NOC_norm"])
        team_names = set(athletes.loc[athletes["Year"] == year, "Team_norm"])
        exact_by_year.append(
            {
                "year": int(year),
                "medal_countries": len(medal_names),
                "matched_exact": len(medal_names & team_names),
                "unmatched": sorted(medal_names - team_names)[:20],
            }
        )

    report = {
        "files": {
            "athletes": {
                "shape": list(athletes.shape),
                "columns": athletes.columns.tolist(),
                "years": [int(athletes["Year"].min()), int(athletes["Year"].max())],
                "missing": athletes.isna().sum().to_dict(),
            },
            "medal_counts": {
                "shape": list(medals.shape),
                "columns": medals.columns.tolist(),
                "years": [int(medals["Year"].min()), int(medals["Year"].max())],
                "missing": medals.isna().sum().to_dict(),
            },
            "hosts": {
                "shape": list(hosts.shape),
                "columns": hosts.columns.tolist(),
                "tail": hosts.tail(5).to_dict(orient="records"),
            },
            "programs": {
                "shape": list(programs.shape),
                "columns": programs.columns.tolist(),
                "head": programs.head(5).to_dict(orient="records"),
            },
        },
        "2024": {
            "athlete_team_count": len(current_teams),
            "medal_country_count": len(current_medal_names),
            "exact_overlap": len(current_teams & current_medal_names),
            "medal_names_not_in_teams": sorted(current_medal_names - current_teams),
            "teams_without_medal_table_row_sample": sorted(current_teams - current_medal_names)[:40],
            "noc_to_team_sample": current_noc_map.head(20).to_dict(),
        },
        "team_event_duplication": {
            "raw_medal_athlete_rows": raw_medal_athletes,
            "unique_year_noc_sport_event_medal_rows": unique_country_event_medals,
            "ratio": unique_country_event_medals / raw_medal_athletes,
        },
        "exact_name_match_by_year": exact_by_year,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
