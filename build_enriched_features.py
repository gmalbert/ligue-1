"""Build an additive enriched feature store.

The current production model still trains from data_files/model_ready_data.csv.
This file joins newer enrichment sources into a separate feature store so we can
inspect coverage before making those fields mandatory model inputs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from team_name_mapping import normalize_dataframe_teams, normalize_team_name

MODEL_READY_PATH = Path("data_files/model_ready_data.csv")
UPCOMING_PATH = Path("data_files/upcoming_fixtures.csv")
MARKET_FEATURES_PATH = Path("data_files/model_features/market_features.csv")
TEAM_XG_PATH = Path("data_files/raw/team_xg_rolling.csv")
AVAILABILITY_PATH = Path("data_files/model_features/availability_features.csv")
SQUAD_STRENGTH_PATH = Path("data_files/raw/squad_strength.csv")
OUT_PATH = Path("data_files/model_features/enriched_match_features.csv")


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _base_matches() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if MODEL_READY_PATH.exists():
        hist = pd.read_csv(MODEL_READY_PATH)
        if "MatchDate" in hist.columns:
            hist["Date"] = pd.to_datetime(hist["MatchDate"], errors="coerce").dt.date.astype(str)
        hist["FeatureScope"] = "historical"
        frames.append(hist)
    if UPCOMING_PATH.exists():
        upcoming = pd.read_csv(UPCOMING_PATH)
        if not upcoming.empty:
            upcoming["Date"] = pd.to_datetime(upcoming["Date"], errors="coerce").dt.date.astype(str)
            upcoming["FeatureScope"] = "upcoming"
            frames.append(upcoming)
    if not frames:
        return pd.DataFrame(columns=["Date", "HomeTeam", "AwayTeam", "FeatureScope"])

    base = pd.concat(frames, ignore_index=True, sort=False)
    base = normalize_dataframe_teams(base)
    base["Date"] = pd.to_datetime(base["Date"], errors="coerce").dt.date.astype(str)
    return base


def _team_xg() -> pd.DataFrame:
    xg = _read(TEAM_XG_PATH)
    if xg.empty:
        return xg
    xg["Team"] = xg["Team"].map(normalize_team_name)
    xg["MatchDate"] = pd.to_datetime(xg["MatchDate"], errors="coerce")
    keep = [
        "Team",
        "MatchDate",
        "RollingXGFor_L5",
        "RollingXGA_L5",
        "RollingXGDiff_L5",
        "RollingShots_L5",
        "RollingSOT_L5",
    ]
    return xg[[c for c in keep if c in xg.columns]]


def _join_team_xg_asof(base: pd.DataFrame, team_df: pd.DataFrame, prefix: str, team_col: str) -> pd.DataFrame:
    if team_df.empty:
        return base
    right = team_df.rename(columns={"Team": team_col}).copy()
    right["MatchDate"] = pd.to_datetime(right["MatchDate"], errors="coerce")
    source_cols = [
        "RollingXGFor_L5",
        "RollingXGA_L5",
        "RollingXGDiff_L5",
        "RollingShots_L5",
        "RollingSOT_L5",
    ]
    output_cols = [f"{prefix}{col}" for col in source_cols]
    out = base.copy()
    for col in output_cols:
        out[col] = pd.NA

    team_history = {
        team: hist.sort_values("MatchDate")
        for team, hist in right.groupby(team_col, dropna=False)
    }
    dates = pd.to_datetime(out["Date"], errors="coerce")
    for idx, row in out.iterrows():
        team = row.get(team_col)
        match_date = dates.loc[idx]
        hist = team_history.get(team)
        if hist is None or pd.isna(match_date):
            continue
        eligible = hist[hist["MatchDate"] <= match_date]
        if eligible.empty:
            continue
        latest = eligible.iloc[-1]
        for source, output in zip(source_cols, output_cols):
            if source in latest:
                out.at[idx, output] = latest[source]
    return out


def _join_team_features(base: pd.DataFrame, team_df: pd.DataFrame, prefix: str, team_col: str) -> pd.DataFrame:
    if team_df.empty:
        return base
    renamed = team_df.rename(columns={
        "Team": team_col,
        "RollingXGFor_L5": f"{prefix}RollingXGFor_L5",
        "RollingXGA_L5": f"{prefix}RollingXGA_L5",
        "RollingXGDiff_L5": f"{prefix}RollingXGDiff_L5",
        "RollingShots_L5": f"{prefix}RollingShots_L5",
        "RollingSOT_L5": f"{prefix}RollingSOT_L5",
        "SquadPlayers": f"{prefix}SquadPlayers",
        "AverageAge": f"{prefix}AverageAge",
        "Goalkeepers": f"{prefix}Goalkeepers",
        "Defenders": f"{prefix}Defenders",
        "Midfielders": f"{prefix}Midfielders",
        "Attackers": f"{prefix}Attackers",
        "SquadFetchedAt": f"{prefix}SquadFetchedAt",
    })
    return base.merge(renamed, on=team_col, how="left")


def build_enriched_features() -> pd.DataFrame:
    base = _base_matches()
    keys = ["Date", "HomeTeam", "AwayTeam"]
    if base.empty:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        base.to_csv(OUT_PATH, index=False)
        return base

    market = _read(MARKET_FEATURES_PATH)
    if not market.empty:
        market = normalize_dataframe_teams(market)
        market["Date"] = pd.to_datetime(market["Date"], errors="coerce").dt.date.astype(str)
        base = base.merge(market, on=keys, how="left")

    availability = _read(AVAILABILITY_PATH)
    if not availability.empty:
        availability = normalize_dataframe_teams(availability)
        availability["Date"] = pd.to_datetime(availability["Date"], errors="coerce").dt.date.astype(str)
        base = base.merge(availability, on=keys, how="left")

    team_xg = _team_xg()
    base = _join_team_xg_asof(base, team_xg, "Home", "HomeTeam")
    base = _join_team_xg_asof(base, team_xg, "Away", "AwayTeam")

    squad = _read(SQUAD_STRENGTH_PATH)
    if not squad.empty:
        squad["Team"] = squad["Team"].map(normalize_team_name)
        base = _join_team_features(base, squad, "Home", "HomeTeam")
        base = _join_team_features(base, squad, "Away", "AwayTeam")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(OUT_PATH, index=False)
    print(f"Built enriched feature store with {len(base)} rows -> {OUT_PATH}")
    return base


if __name__ == "__main__":
    build_enriched_features()
