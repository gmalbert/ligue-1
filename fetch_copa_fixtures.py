"""Fetch Coupe de France fixtures from the ESPN unofficial API.

Saves: data_files/raw/copa_fixtures.csv
       Columns: MatchDate (datetime), TeamName (str)
       One row per team per match (long format), used to compute
       the cup congestion flag in prepare_model_data.py.

Usage:
    python fetch_copa_fixtures.py [season_start_year]

    season_start_year defaults to the current or most recent season.
    e.g. 2024 → fetches the 2024-25 Coupe de France.

No API key required.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from team_name_mapping import normalize_team_name

# ESPN Coupe de France league slug
COPA_SLUG = "fra.coupe_de_france"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

Path("data_files/raw").mkdir(parents=True, exist_ok=True)


def _current_season_year() -> int:
    """Return the start year of the current/most-recent Coupe de France season."""
    now = datetime.now()
    # Coupe de France starts in August; if before August treat previous year as start
    return now.year if now.month >= 8 else now.year - 1


def fetch_copa_month(year: int, month: int) -> list[dict]:
    """
    Fetch all Coupe de France events for a single calendar month.
    ESPN scoreboard accepts ?dates=YYYYMM to return a full month.
    """
    date_str = f"{year}{month:02d}"
    url = f"{ESPN_BASE}/{COPA_SLUG}/scoreboard"
    try:
        resp = requests.get(url, params={"dates": date_str}, timeout=15)
        if resp.status_code == 404:
            # League slug may vary; return empty and let caller handle
            return []
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as exc:
        print(f"  Warning: {year}-{month:02d} — {exc}")
        return []


def _parse_event(event: dict) -> tuple[str, str, str] | None:
    """Extract (date, home_team, away_team) from an ESPN event dict."""
    date = event.get("date", "")[:10]
    comps = event.get("competitions", [])
    if not comps:
        return None
    competitors = comps[0].get("competitors", [])
    if len(competitors) < 2:
        return None
    home = next(
        (c["team"]["displayName"] for c in competitors if c.get("homeAway") == "home"),
        None,
    )
    away = next(
        (c["team"]["displayName"] for c in competitors if c.get("homeAway") == "away"),
        None,
    )
    if home and away:
        return date, home, away
    return None


def fetch_copa_fixtures(season_start_year: int | None = None) -> pd.DataFrame:
    """
    Fetch all Coupe de France fixtures for a full season (Aug → Jun).
    Returns a long-format DataFrame: one row per team per match.
    """
    if season_start_year is None:
        season_start_year = _current_season_year()

    season_label = f"{season_start_year}-{str(season_start_year + 1)[2:]}"
    print(f"Fetching Coupe de France {season_label} via ESPN…")

    # Coupe de France season spans August → June
    months = (
        [(season_start_year, m) for m in range(8, 13)]
        + [(season_start_year + 1, m) for m in range(1, 7)]
    )

    match_rows: list[dict] = []
    for year, month in months:
        events = fetch_copa_month(year, month)
        for event in events:
            parsed = _parse_event(event)
            if parsed:
                date, home, away = parsed
                match_rows.append({"MatchDate": date, "HomeTeam": home, "AwayTeam": away})
        time.sleep(0.4)  # polite delay

    if not match_rows:
        print(
            "  ✗ No Coupe de France fixtures found. ESPN may use a different slug for this season.\n"
            f"  Tried slug: {COPA_SLUG}\n"
            "  Check https://www.espn.com/soccer/ for the correct league URL."
        )
        return pd.DataFrame(columns=["MatchDate", "TeamName"])

    df = pd.DataFrame(match_rows).drop_duplicates()
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")

    # Convert to long format: one row per team per match
    home_df = df[["MatchDate", "HomeTeam"]].rename(columns={"HomeTeam": "TeamName"})
    away_df = df[["MatchDate", "AwayTeam"]].rename(columns={"AwayTeam": "TeamName"})
    copa_long = (
        pd.concat([home_df, away_df], ignore_index=True)
        .drop_duplicates()
        .sort_values("MatchDate")
        .reset_index(drop=True)
    )
    copa_long["TeamName"] = copa_long["TeamName"].map(normalize_team_name)

    out = "data_files/raw/copa_fixtures.csv"
    copa_long.to_csv(out, index=False)
    print(f"  ✓ {len(df)} Coupe de France matches → {len(copa_long)} team-match rows → {out}")
    return copa_long


if __name__ == "__main__":
    year_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    fetch_copa_fixtures(year_arg)
