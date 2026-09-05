from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "2025_Problem_C_Data"


def read_csv(name: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(DATA / name, encoding=enc)
        except UnicodeDecodeError:
            pass
    raise RuntimeError(name)


def main() -> None:
    athletes = read_csv("summerOly_athletes.csv")
    official = read_csv("summerOly_medal_counts.csv")
    med = athletes.loc[athletes.Medal.ne("No medal")].drop_duplicates(
        ["Year", "NOC", "Sport", "Event", "Medal"]
    )
    reconstructed = (
        med.assign(Gold=lambda x: x.Medal.eq("Gold").astype(int))
        .groupby(["Year", "NOC"], as_index=False)
        .agg(Gold=("Gold", "sum"), Total=("Medal", "size"))
    )
    totals = reconstructed.groupby("Year")[["Gold", "Total"]].sum()
    off_totals = official.groupby("Year")[["Gold", "Total"]].sum()
    cmp = totals.join(off_totals, lsuffix="_recon", rsuffix="_official")
    cmp["gold_gap"] = cmp.Gold_recon - cmp.Gold_official
    cmp["total_gap"] = cmp.Total_recon - cmp.Total_official
    print(cmp.tail(12).to_string())
    print("\nmax abs gaps", cmp[["gold_gap", "total_gap"]].abs().max().to_dict())
    print("2024 reconstructed", reconstructed.query("Year == 2024").sort_values("Total", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
