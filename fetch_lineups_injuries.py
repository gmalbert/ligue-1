"""Fetch API-Football injuries and lineups with a daily quota guard.

The script is intentionally fixture-driven and cache-first. It only asks
API-Football for upcoming Ligue 1 fixtures in a short window, then skips
injury/lineup calls that are already cached.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from api_football_client import ApiFootballQuotaError, api_get, quota_status
from team_name_mapping import normalize_dataframe_teams, normalize_team_name

INJURIES_PATH = Path("data_files/raw/injuries.csv")
LINEUPS_PATH = Path("data_files/raw/lineups.csv")
AVAILABILITY_FEATURES_PATH = Path("data_files/model_features/availability_features.csv")
FIXTURE_MAP_PATH = Path("data_files/raw/api_football_upcoming_fixtures.csv")

INJURY_COLUMNS = [
    "FixtureId",
    "Date",
    "Team",
    "PlayerId",
    "PlayerName",
    "Reason",
    "Type",
    "FetchedAt",
]
LINEUP_COLUMNS = [
    "FixtureId",
    "Date",
    "Team",
    "PlayerId",
    "PlayerName",
    "Role",
    "Position",
    "Grid",
    "Formation",
    "FetchedAt",
]
FEATURE_COLUMNS = [
    "Date",
    "HomeTeam",
    "AwayTeam",
    "HomeUnavailableCount",
    "AwayUnavailableCount",
    "HomeExpectedStarterCount",
    "AwayExpectedStarterCount",
    "HomeLineupContinuity",
    "AwayLineupContinuity",
    "AvailabilityFetchedAt",
]


def _season() -> int:
    configured = os.getenv("API_FOOTBALL_SEASON", "").strip()
    if configured:
        return int(configured)
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def _empty_fixtures(reason: str) -> pd.DataFrame:
    print(reason)
    df = pd.DataFrame(columns=["FixtureId", "Date", "KickoffUTC", "HomeTeam", "AwayTeam", "Status"])
    FIXTURE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIXTURE_MAP_PATH, index=False)
    return df


def _league_id() -> int:
    return int(os.getenv("API_FOOTBALL_LEAGUE_ID", "61"))


def _lookahead_days() -> int:
    return int(os.getenv("API_FOOTBALL_AVAILABILITY_LOOKAHEAD_DAYS", "14"))


def _lineup_window_hours() -> int:
    return int(os.getenv("API_FOOTBALL_LINEUP_LOOKAHEAD_HOURS", "36"))


def _max_fixtures() -> int:
    return int(os.getenv("API_FOOTBALL_AVAILABILITY_FIXTURE_LIMIT", "8"))


def _ensure_file(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def _load(path: Path, columns: list[str]) -> pd.DataFrame:
    _ensure_file(path, columns)
    return pd.read_csv(path)


def _fixture_row(item: dict[str, Any]) -> dict[str, Any]:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    return {
        "FixtureId": fixture.get("id"),
        "Date": str(fixture.get("date", ""))[:10],
        "KickoffUTC": fixture.get("date"),
        "HomeTeam": normalize_team_name(str(home.get("name", ""))),
        "AwayTeam": normalize_team_name(str(away.get("name", ""))),
        "Status": ((fixture.get("status") or {}).get("short")),
    }


def _fetch_upcoming_fixtures() -> pd.DataFrame:
    today = datetime.now(timezone.utc).date()
    try:
        body = api_get(
            "fixtures",
            {
                "league": _league_id(),
                "season": _season(),
                "from": today.isoformat(),
                "to": (today + timedelta(days=_lookahead_days())).isoformat(),
            },
        )
    except RuntimeError as exc:
        if "Free plans do not have access to this season" in str(exc):
            return _empty_fixtures(
                "API-Football current-season injuries/lineups are unavailable on this plan."
            )
        raise
    rows = [_fixture_row(item) for item in body.get("response", [])]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = normalize_dataframe_teams(df)
        df = df.head(_max_fixtures())
    FIXTURE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIXTURE_MAP_PATH, index=False)
    return df


def _injury_rows(fixture: pd.Series, payload: list[dict[str, Any]], fetched_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        player = item.get("player") or {}
        team = item.get("team") or {}
        rows.append({
            "FixtureId": fixture["FixtureId"],
            "Date": fixture["Date"],
            "Team": normalize_team_name(str(team.get("name", ""))),
            "PlayerId": player.get("id"),
            "PlayerName": player.get("name"),
            "Reason": item.get("reason"),
            "Type": item.get("type"),
            "FetchedAt": fetched_at,
        })
    return rows


def _lineup_rows(fixture: pd.Series, payload: list[dict[str, Any]], fetched_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team_lineup in payload:
        team = normalize_team_name(str((team_lineup.get("team") or {}).get("name", "")))
        formation = team_lineup.get("formation")
        for role, players in [("Start", team_lineup.get("startXI") or []), ("Sub", team_lineup.get("substitutes") or [])]:
            for wrapper in players:
                player = wrapper.get("player") or {}
                rows.append({
                    "FixtureId": fixture["FixtureId"],
                    "Date": fixture["Date"],
                    "Team": team,
                    "PlayerId": player.get("id"),
                    "PlayerName": player.get("name"),
                    "Role": role,
                    "Position": player.get("pos"),
                    "Grid": player.get("grid"),
                    "Formation": formation,
                    "FetchedAt": fetched_at,
                })
    return rows


def build_availability_features(fixtures: pd.DataFrame | None = None) -> pd.DataFrame:
    injuries = _load(INJURIES_PATH, INJURY_COLUMNS)
    lineups = _load(LINEUPS_PATH, LINEUP_COLUMNS)
    if fixtures is None:
        fixtures = pd.read_csv(FIXTURE_MAP_PATH) if FIXTURE_MAP_PATH.exists() else pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for _, fixture in fixtures.iterrows():
        home = fixture["HomeTeam"]
        away = fixture["AwayTeam"]
        fixture_id = fixture["FixtureId"]
        inj = injuries[injuries["FixtureId"].astype(str).eq(str(fixture_id))]
        lineup = lineups[lineups["FixtureId"].astype(str).eq(str(fixture_id))]
        home_lineup = lineup[lineup["Team"].eq(home)]
        away_lineup = lineup[lineup["Team"].eq(away)]
        rows.append({
            "Date": fixture["Date"],
            "HomeTeam": home,
            "AwayTeam": away,
            "HomeUnavailableCount": int(inj[inj["Team"].eq(home)]["PlayerId"].nunique()),
            "AwayUnavailableCount": int(inj[inj["Team"].eq(away)]["PlayerId"].nunique()),
            "HomeExpectedStarterCount": int(home_lineup[home_lineup["Role"].eq("Start")]["PlayerId"].nunique()),
            "AwayExpectedStarterCount": int(away_lineup[away_lineup["Role"].eq("Start")]["PlayerId"].nunique()),
            "HomeLineupContinuity": "",
            "AwayLineupContinuity": "",
            "AvailabilityFetchedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        })

    features = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    AVAILABILITY_FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(AVAILABILITY_FEATURES_PATH, index=False)
    return features


def fetch_lineups_injuries() -> pd.DataFrame:
    injuries = _load(INJURIES_PATH, INJURY_COLUMNS)
    lineups = _load(LINEUPS_PATH, LINEUP_COLUMNS)
    fixtures = _fetch_upcoming_fixtures()
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    new_injuries: list[dict[str, Any]] = []
    new_lineups: list[dict[str, Any]] = []
    cached_injury_ids = set(injuries.get("FixtureId", pd.Series(dtype=str)).astype(str))
    cached_lineup_ids = set(lineups.get("FixtureId", pd.Series(dtype=str)).astype(str))

    for _, fixture in fixtures.iterrows():
        fixture_id = str(fixture["FixtureId"])
        try:
            if fixture_id not in cached_injury_ids:
                body = api_get("injuries", {"fixture": fixture_id})
                new_injuries.extend(_injury_rows(fixture, body.get("response", []), fetched_at))

            kickoff = pd.to_datetime(fixture.get("KickoffUTC"), utc=True, errors="coerce")
            close_to_kickoff = pd.notna(kickoff) and kickoff <= pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=_lineup_window_hours())
            if close_to_kickoff and fixture_id not in cached_lineup_ids:
                body = api_get("fixtures/lineups", {"fixture": fixture_id})
                new_lineups.extend(_lineup_rows(fixture, body.get("response", []), fetched_at))
        except ApiFootballQuotaError:
            print("API-Football quota guard stopped injuries/lineups refresh.")
            break

    if new_injuries:
        injuries = pd.concat([injuries, pd.DataFrame(new_injuries)], ignore_index=True)
        injuries = injuries.drop_duplicates(subset=["FixtureId", "Team", "PlayerId", "Reason"], keep="last")
        injuries.to_csv(INJURIES_PATH, index=False)
    if new_lineups:
        lineups = pd.concat([lineups, pd.DataFrame(new_lineups)], ignore_index=True)
        lineups = lineups.drop_duplicates(subset=["FixtureId", "Team", "PlayerId", "Role"], keep="last")
        lineups.to_csv(LINEUPS_PATH, index=False)

    features = build_availability_features(fixtures)
    status = quota_status()
    print(f"Fetched {len(new_injuries)} injury rows and {len(new_lineups)} lineup rows.")
    print(f"Built {len(features)} availability feature rows -> {AVAILABILITY_FEATURES_PATH}")
    print(f"API-Football quota used today: {status['used']} of {status['usable_limit']} usable.")
    return features


if __name__ == "__main__":
    fetch_lineups_injuries()
