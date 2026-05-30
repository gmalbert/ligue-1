"""Fetch match statistics from API-Football and extract xG when available.

API-Football's xG availability can vary by competition, plan, and match. This
script stores true provider xG when the fixture statistics payload includes it;
otherwise it leaves xG blank and keeps the existing shot-on-target proxy as the
fallback used by fetch_fbref_xg.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api_football_client import ApiFootballQuotaError, api_get, quota_status
from team_name_mapping import normalize_dataframe_teams, normalize_team_name

MATCH_XG_PATH = Path("data_files/raw/match_xg.csv")
TEAM_XG_PATH = Path("data_files/raw/team_xg_rolling.csv")
FIXTURE_MAP_PATH = Path("data_files/raw/api_football_fixtures.csv")
MATCH_COLUMNS = [
    "FixtureId",
    "MatchDate",
    "HomeTeam",
    "AwayTeam",
    "Home_xG",
    "Away_xG",
    "HomeShots",
    "AwayShots",
    "HomeShotsOnTarget",
    "AwayShotsOnTarget",
    "XGSource",
    "FetchedAt",
]
TEAM_COLUMNS = [
    "Team",
    "MatchDate",
    "RollingXGFor_L5",
    "RollingXGA_L5",
    "RollingXGDiff_L5",
    "RollingShots_L5",
    "RollingSOT_L5",
]


def _season() -> int:
    configured = os.getenv("API_FOOTBALL_SEASON", "").strip()
    if configured:
        return int(configured)
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def _fallback_season() -> int:
    return int(os.getenv("API_FOOTBALL_FALLBACK_SEASON", "2024"))


def _league_id() -> int:
    return int(os.getenv("API_FOOTBALL_LEAGUE_ID", "61"))


def _limit() -> int:
    return int(os.getenv("API_FOOTBALL_XG_FIXTURE_LIMIT", "12"))


def _ensure_file(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def _stat_value(stats: list[dict[str, Any]], names: set[str]) -> float | None:
    for stat in stats:
        name = str(stat.get("type", "")).strip().lower()
        if name not in names:
            continue
        value = stat.get("value")
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _extract_team_stats(payload: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for team_payload in payload:
        team = normalize_team_name(str((team_payload.get("team") or {}).get("name", "")))
        stats = team_payload.get("statistics") or []
        out[team] = {
            "xg": _stat_value(stats, {"expected goals", "expected_goals", "xg"}),
            "shots": _stat_value(stats, {"total shots", "shots total", "shots"}),
            "sot": _stat_value(stats, {"shots on goal", "shots on target"}),
        }
    return out


def _load_existing() -> pd.DataFrame:
    _ensure_file(MATCH_XG_PATH, MATCH_COLUMNS)
    return pd.read_csv(MATCH_XG_PATH)


def _fixture_row(item: dict[str, Any]) -> dict[str, Any]:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    return {
        "FixtureId": fixture.get("id"),
        "MatchDate": str(fixture.get("date", ""))[:10],
        "HomeTeam": normalize_team_name(str(home.get("name", ""))),
        "AwayTeam": normalize_team_name(str(away.get("name", ""))),
        "Status": ((fixture.get("status") or {}).get("short")),
    }


def _fetch_recent_final_fixtures() -> pd.DataFrame:
    last_error: Exception | None = None
    seasons = [_season()]
    if _fallback_season() not in seasons:
        seasons.append(_fallback_season())

    for season in seasons:
        try:
            return _fetch_recent_final_fixtures_for_season(season)
        except RuntimeError as exc:
            last_error = exc
            if "Free plans do not have access to this season" in str(exc):
                print(f"API-Football season {season} unavailable on this plan; trying fallback season.")
                continue
            raise
    if last_error:
        print(f"API-Football fixture lookup skipped: {last_error}")
    return pd.DataFrame(columns=["FixtureId", "MatchDate", "HomeTeam", "AwayTeam", "Status"])


def _fetch_recent_final_fixtures_for_season(season: int) -> pd.DataFrame:
    params = {
        "league": _league_id(),
        "season": season,
        "status": "FT",
        "last": max(_limit() * 2, 20),
    }
    try:
        body = api_get("fixtures", params)
    except RuntimeError as exc:
        if "Last parameter" not in str(exc):
            raise
        date_params = {
            "league": _league_id(),
            "season": season,
            "from": f"{season + 1}-05-01",
            "to": f"{season + 1}-06-15",
        }
        body = api_get("fixtures", date_params)
    if not body.get("response"):
        fallback = dict(params)
        fallback.pop("status", None)
        try:
            body = api_get("fixtures", fallback)
        except RuntimeError as exc:
            if "Last parameter" not in str(exc):
                raise
            body = {"response": []}
    rows = [_fixture_row(item) for item in body.get("response", [])]
    df = pd.DataFrame(rows)
    if not df.empty:
        if "Status" in df.columns:
            df = df[df["Status"].isin(["FT", "AET", "PEN"])].copy()
        df = df.tail(max(_limit() * 2, 20))
        df["ApiFootballSeason"] = season
        df = normalize_dataframe_teams(df)
        FIXTURE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(FIXTURE_MAP_PATH, index=False)
    return df


def build_team_xg_rolling(match_df: pd.DataFrame) -> pd.DataFrame:
    if match_df.empty:
        team_df = pd.DataFrame(columns=TEAM_COLUMNS)
        team_df.to_csv(TEAM_XG_PATH, index=False)
        return team_df

    df = match_df.copy()
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    for col in ["Home_xG", "Away_xG", "HomeShots", "AwayShots", "HomeShotsOnTarget", "AwayShotsOnTarget"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    home = df[["MatchDate", "HomeTeam", "Home_xG", "Away_xG", "HomeShots", "HomeShotsOnTarget"]].copy()
    home.columns = ["MatchDate", "Team", "XGFor", "XGA", "Shots", "SOT"]
    away = df[["MatchDate", "AwayTeam", "Away_xG", "Home_xG", "AwayShots", "AwayShotsOnTarget"]].copy()
    away.columns = ["MatchDate", "Team", "XGFor", "XGA", "Shots", "SOT"]
    long = pd.concat([home, away], ignore_index=True).sort_values(["Team", "MatchDate"])
    grp = long.groupby("Team")
    long["RollingXGFor_L5"] = grp["XGFor"].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    long["RollingXGA_L5"] = grp["XGA"].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    long["RollingXGDiff_L5"] = long["RollingXGFor_L5"] - long["RollingXGA_L5"]
    long["RollingShots_L5"] = grp["Shots"].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    long["RollingSOT_L5"] = grp["SOT"].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    team_df = long[TEAM_COLUMNS].replace({np.nan: ""})
    TEAM_XG_PATH.parent.mkdir(parents=True, exist_ok=True)
    team_df.to_csv(TEAM_XG_PATH, index=False)
    return team_df


def fetch_xg_data() -> pd.DataFrame:
    existing = _load_existing()
    seen = set(pd.to_numeric(existing.get("FixtureId"), errors="coerce").dropna().astype(int).tolist())
    fixtures = _fetch_recent_final_fixtures()

    rows: list[dict[str, Any]] = []
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for _, fixture in fixtures.iterrows():
        fixture_id = int(fixture["FixtureId"])
        if fixture_id in seen:
            continue
        if len(rows) >= _limit():
            break
        try:
            body = api_get("fixtures/statistics", {"fixture": fixture_id})
        except ApiFootballQuotaError:
            print("API-Football quota guard stopped xG/statistics refresh.")
            break

        stats = _extract_team_stats(body.get("response", []))
        home = fixture["HomeTeam"]
        away = fixture["AwayTeam"]
        home_stats = stats.get(home, {})
        away_stats = stats.get(away, {})
        has_true_xg = home_stats.get("xg") is not None and away_stats.get("xg") is not None
        rows.append({
            "FixtureId": fixture_id,
            "MatchDate": fixture["MatchDate"],
            "HomeTeam": home,
            "AwayTeam": away,
            "Home_xG": home_stats.get("xg"),
            "Away_xG": away_stats.get("xg"),
            "HomeShots": home_stats.get("shots"),
            "AwayShots": away_stats.get("shots"),
            "HomeShotsOnTarget": home_stats.get("sot"),
            "AwayShotsOnTarget": away_stats.get("sot"),
            "XGSource": "api-football" if has_true_xg else "unavailable",
            "FetchedAt": fetched_at,
        })

    new_df = pd.DataFrame(rows, columns=MATCH_COLUMNS)
    combined = pd.concat([existing, new_df], ignore_index=True)
    if not combined.empty:
        combined = normalize_dataframe_teams(combined)
        combined = combined.drop_duplicates(subset=["FixtureId"], keep="last")
    combined.to_csv(MATCH_XG_PATH, index=False)
    team_df = build_team_xg_rolling(combined)
    status = quota_status()
    print(f"Fetched {len(new_df)} new API-Football match-stat rows -> {MATCH_XG_PATH}")
    print(f"Built {len(team_df)} rolling xG/stat rows -> {TEAM_XG_PATH}")
    print(f"API-Football quota used today: {status['used']} of {status['usable_limit']} usable.")
    return combined


if __name__ == "__main__":
    fetch_xg_data()
