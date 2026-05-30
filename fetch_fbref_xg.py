"""Compute team-level xG proxy stats for Ligue Odds.

Primary source: data_files/combined_historical_data.csv
    football-data.co.uk CSVs include shots on target (HST/AST) which are
    used as a reliable xG proxy (Ligue Odds SOT->goal conversion ~31pct).

FBref is protected by Cloudflare JS challenge and cannot be scraped with
standard HTTP libraries. Understat is fully client-side rendered. This
script derives equivalent metrics from the historical shot data we already
have, which is more reliable for a nightly pipeline.

Saves:
    data_files/raw/fbref_team_xg.csv   - team-level xG proxy stats
    data_files/raw/fbref_match_xg.csv  - match-level goal/shot stats

Usage:
    python fetch_fbref_xg.py [--seasons N]
    --seasons N  Only use the last N seasons (default: 3, ~1140 matches)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

HIST_PATH    = "data_files/combined_historical_data.csv"
TEAM_OUT     = "data_files/raw/fbref_team_xg.csv"
MATCH_OUT    = "data_files/raw/fbref_match_xg.csv"

SOT_XG_FACTOR = 0.31

Path("data_files/raw").mkdir(parents=True, exist_ok=True)


def compute_from_historical(n_seasons: int = 3) -> tuple:
    if not Path(HIST_PATH).exists():
        raise FileNotFoundError(
            f"{HIST_PATH} not found. Run fetch_historical_csvs.py first."
        )

    df = pd.read_csv(HIST_PATH, low_memory=False)
    df["MatchDate"] = pd.to_datetime(df.get("MatchDate"), errors="coerce")
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "MatchDate"])
    df = df.sort_values("MatchDate").reset_index(drop=True)

    if "Season" in df.columns:
        all_seasons = sorted(df["Season"].dropna().unique())
        recent = all_seasons[-n_seasons:]
        df = df[df["Season"].isin(recent)].copy()
    else:
        df = df.tail(380 * n_seasons).copy()

    for col in ["FullTimeHomeGoals", "FullTimeAwayGoals",
                "HomeShotsOnTarget", "AwayShotsOnTarget",
                "HomeShots", "AwayShots"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    match_df = df[["MatchDate", "HomeTeam", "AwayTeam",
                   "FullTimeHomeGoals", "FullTimeAwayGoals"]].copy()
    match_df = match_df.rename(columns={
        "FullTimeHomeGoals": "HomeGoals",
        "FullTimeAwayGoals": "AwayGoals",
    })
    if "HomeShotsOnTarget" in df.columns:
        match_df["Home_xG"] = (df["HomeShotsOnTarget"] * SOT_XG_FACTOR).round(2)
        match_df["Away_xG"] = (df["AwayShotsOnTarget"] * SOT_XG_FACTOR).round(2)
    else:
        match_df["Home_xG"] = match_df["HomeGoals"]
        match_df["Away_xG"] = match_df["AwayGoals"]
    match_df.to_csv(MATCH_OUT, index=False)
    print(f"  xG Match proxy: {len(match_df)} matches -> {MATCH_OUT}")

    records = []
    all_teams = set(df["HomeTeam"].dropna()) | set(df["AwayTeam"].dropna())
    for team in sorted(all_teams):
        home_m = df[df["HomeTeam"] == team]
        away_m = df[df["AwayTeam"] == team]
        all_m  = len(home_m) + len(away_m)
        if all_m == 0:
            continue
        home_gf = home_m["FullTimeHomeGoals"].mean() if len(home_m) else 0
        home_ga = home_m["FullTimeAwayGoals"].mean() if len(home_m) else 0
        away_gf = away_m["FullTimeAwayGoals"].mean() if len(away_m) else 0
        away_ga = away_m["FullTimeHomeGoals"].mean() if len(away_m) else 0
        goals_for     = (home_gf * len(home_m) + away_gf * len(away_m)) / all_m
        goals_against = (home_ga * len(home_m) + away_ga * len(away_m)) / all_m
        if "HomeShotsOnTarget" in df.columns:
            hsot_f = home_m["HomeShotsOnTarget"].mean() if len(home_m) else 0
            hsot_a = home_m["AwayShotsOnTarget"].mean() if len(home_m) else 0
            asot_f = away_m["AwayShotsOnTarget"].mean() if len(away_m) else 0
            asot_a = away_m["HomeShotsOnTarget"].mean()  if len(away_m) else 0
            xg_for = ((hsot_f*len(home_m)+asot_f*len(away_m))/all_m)*SOT_XG_FACTOR
            xga    = ((hsot_a*len(home_m)+asot_a*len(away_m))/all_m)*SOT_XG_FACTOR
        else:
            xg_for = goals_for
            xga    = goals_against
        home_results = home_m["FullTimeResult"].value_counts().to_dict() if len(home_m) else {}
        away_results = away_m["FullTimeResult"].value_counts().to_dict() if len(away_m) else {}
        wins   = home_results.get("H",0)+away_results.get("A",0)
        draws  = home_results.get("D",0)+away_results.get("D",0)
        losses = home_results.get("A",0)+away_results.get("H",0)
        records.append({
            "Team": team, "MatchesPlayed": all_m,
            "Wins": wins, "Draws": draws, "Losses": losses,
            "Goals": round(goals_for*all_m), "GoalsAgainst": round(goals_against*all_m),
            "GoalsPerGame": round(goals_for,2),
            "xG": round(xg_for*all_m,1), "xGA": round(xga*all_m,1),
            "xGD": round((xg_for-xga)*all_m,1), "xGD_per90": round(xg_for-xga,3),
            "Possession": None,
        })
    team_df = pd.DataFrame(records).sort_values("xGD", ascending=False).reset_index(drop=True)
    team_df.to_csv(TEAM_OUT, index=False)
    print(f"  xG Team proxy: {len(team_df)} teams -> {TEAM_OUT}")
    return team_df, match_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, default=3)
    args = parser.parse_args()
    print(f"Computing xG proxy from last {args.seasons} season(s)...")
    compute_from_historical(args.seasons)
    print("Done.")
