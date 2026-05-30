"""Fetch cached Ligue 1 squad data from API-Football.

This is a low-frequency enrichment job. It costs roughly one teams request plus
one squad request per Ligue 1 club when the cache is stale, so the default cache
TTL is 30 days.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from api_football_client import ApiFootballHTTPError, ApiFootballQuotaError, api_get, quota_status
from team_name_mapping import normalize_team_name

TEAMS_PATH = Path("data_files/raw/api_football_teams.csv")
SQUADS_PATH = Path("data_files/raw/api_football_squads.csv")
STRENGTH_PATH = Path("data_files/raw/squad_strength.csv")

TEAM_COLUMNS = ["TeamId", "Team", "Venue", "Season", "FetchedAt"]
SQUAD_COLUMNS = ["TeamId", "Team", "PlayerId", "PlayerName", "Age", "Position", "FetchedAt"]
STRENGTH_COLUMNS = [
    "Team",
    "SquadPlayers",
    "AverageAge",
    "Goalkeepers",
    "Defenders",
    "Midfielders",
    "Attackers",
    "SquadFetchedAt",
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


def _cache_days() -> int:
    return int(os.getenv("API_FOOTBALL_SQUAD_CACHE_DAYS", "30"))


def _request_delay_seconds() -> float:
    return float(os.getenv("API_FOOTBALL_REQUEST_DELAY_SEC", "7"))


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if pd.read_csv(path).empty:
            return False
    except (OSError, pd.errors.EmptyDataError):
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return modified >= datetime.now() - timedelta(days=_cache_days())


def _ensure_file(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def _fetch_teams(fetched_at: str) -> pd.DataFrame:
    last_error: Exception | None = None
    seasons = [_season()]
    if _fallback_season() not in seasons:
        seasons.append(_fallback_season())

    body: dict[str, Any] | None = None
    used_season = seasons[0]
    for season in seasons:
        try:
            body = api_get("teams", {"league": _league_id(), "season": season})
            used_season = season
            break
        except RuntimeError as exc:
            last_error = exc
            if "Free plans do not have access to this season" in str(exc):
                print(f"API-Football season {season} unavailable on this plan; trying fallback season.")
                continue
            raise
    if body is None:
        raise RuntimeError(f"Could not fetch API-Football teams: {last_error}")

    rows: list[dict[str, Any]] = []
    for item in body.get("response", []):
        team = item.get("team") or {}
        venue = item.get("venue") or {}
        rows.append({
            "TeamId": team.get("id"),
            "Team": normalize_team_name(str(team.get("name", ""))),
            "Venue": venue.get("name"),
            "Season": used_season,
            "FetchedAt": fetched_at,
        })
    df = pd.DataFrame(rows, columns=TEAM_COLUMNS)
    TEAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(TEAMS_PATH, index=False)
    return df


def _fetch_squads(teams: pd.DataFrame, fetched_at: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, team_row in teams.iterrows():
        try:
            body = api_get("players/squads", {"team": int(team_row["TeamId"])})
        except ApiFootballQuotaError:
            print("API-Football quota guard stopped squad refresh.")
            break
        except ApiFootballHTTPError as exc:
            if exc.status_code == 429:
                print("API-Football per-minute throttle stopped squad refresh; saving partial cache.")
                break
            raise
        response = body.get("response", [])
        if not response:
            continue
        for player in response[0].get("players", []):
            rows.append({
                "TeamId": team_row["TeamId"],
                "Team": team_row["Team"],
                "PlayerId": player.get("id"),
                "PlayerName": player.get("name"),
                "Age": player.get("age"),
                "Position": player.get("position"),
                "FetchedAt": fetched_at,
            })
        time.sleep(_request_delay_seconds())
    df = pd.DataFrame(rows, columns=SQUAD_COLUMNS)
    SQUADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SQUADS_PATH, index=False)
    return df


def build_squad_strength(squads: pd.DataFrame | None = None) -> pd.DataFrame:
    if squads is None:
        _ensure_file(SQUADS_PATH, SQUAD_COLUMNS)
        squads = pd.read_csv(SQUADS_PATH)
    if squads.empty:
        strength = pd.DataFrame(columns=STRENGTH_COLUMNS)
        strength.to_csv(STRENGTH_PATH, index=False)
        return strength

    squads = squads.copy()
    squads["Age"] = pd.to_numeric(squads["Age"], errors="coerce")
    position = squads["Position"].fillna("").str.lower()
    squads["Goalkeeper"] = position.str.contains("goalkeeper").astype(int)
    squads["Defender"] = position.str.contains("defender").astype(int)
    squads["Midfielder"] = position.str.contains("midfielder").astype(int)
    squads["Attacker"] = position.str.contains("attacker").astype(int)
    strength = (
        squads.groupby("Team", as_index=False)
        .agg(
            SquadPlayers=("PlayerId", "nunique"),
            AverageAge=("Age", "mean"),
            Goalkeepers=("Goalkeeper", "sum"),
            Defenders=("Defender", "sum"),
            Midfielders=("Midfielder", "sum"),
            Attackers=("Attacker", "sum"),
            SquadFetchedAt=("FetchedAt", "max"),
        )
    )
    strength["AverageAge"] = strength["AverageAge"].round(2)
    STRENGTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    strength.to_csv(STRENGTH_PATH, index=False)
    return strength


def fetch_squad_strength(force: bool = False) -> pd.DataFrame:
    _ensure_file(TEAMS_PATH, TEAM_COLUMNS)
    _ensure_file(SQUADS_PATH, SQUAD_COLUMNS)
    if not force and _is_cache_fresh(SQUADS_PATH):
        squads = pd.read_csv(SQUADS_PATH)
        strength = build_squad_strength(squads)
        print(f"Squad cache is fresh; rebuilt {len(strength)} squad strength rows.")
        return strength

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    teams = _fetch_teams(fetched_at)
    squads = _fetch_squads(teams, fetched_at)
    strength = build_squad_strength(squads)
    status = quota_status()
    print(f"Fetched {len(teams)} teams and {len(squads)} squad player rows.")
    print(f"Built {len(strength)} squad strength rows -> {STRENGTH_PATH}")
    print(f"API-Football quota used today: {status['used']} of {status['usable_limit']} usable.")
    return strength


if __name__ == "__main__":
    fetch_squad_strength(force=os.getenv("API_FOOTBALL_FORCE_SQUADS", "").lower() == "true")
