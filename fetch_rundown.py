"""TheRundown V2 client for Ligue 1 pre-match odds.

The API returns all requested markets and sportsbooks for a match date in one
response. This avoids the per-event request fan-out used by odds-api.io.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()


BASE_URL = "https://therundown.io/api/v2"
LIGUE_1_SPORT_ID = 12
MARKET_IDS = {1: "1X2", 2: "Spread", 3: "Totals"}
AFFILIATES = {3: "Pinnacle", 19: "DraftKings", 22: "BetMGM", 23: "FanDuel"}
OFF_BOARD_PRICE = 0.0001


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip().strip("\"'")


def _csv_ints(value: str) -> list[int]:
    values: list[int] = []
    for item in value.split(","):
        try:
            values.append(int(item.strip()))
        except ValueError:
            continue
    return values


def _fixture_dates() -> list[date]:
    """Use fetched fixture dates when available; otherwise scan a short window."""
    today = date.today()
    lookahead = max(0, int(_env("THERUNDOWN_LOOKAHEAD_DAYS", "45")))
    latest = today + timedelta(days=lookahead)
    fixture_path = Path("data_files/upcoming_fixtures.csv")
    if fixture_path.exists():
        try:
            fixtures = pd.read_csv(fixture_path, usecols=["Date"])
            parsed = pd.to_datetime(fixtures["Date"], errors="coerce").dt.date
            dates = sorted({value for value in parsed.dropna() if today <= value <= latest})
            if dates:
                return dates
        except (OSError, ValueError, pd.errors.ParserError):
            pass
    return [today + timedelta(days=offset) for offset in range(lookahead + 1)]


def _decimal_price(american_price: Any) -> float | None:
    try:
        price = float(american_price)
    except (TypeError, ValueError):
        return None
    if price in {0, OFF_BOARD_PRICE}:
        return None
    return 1 + (price / 100) if price > 0 else 1 + (100 / abs(price))


def _event_teams(event: dict[str, Any]) -> tuple[str, str]:
    teams = event.get("teams") or []
    away = next((str(team.get("name", "")) for team in teams if team.get("is_away")), "")
    home = next((str(team.get("name", "")) for team in teams if team.get("is_home")), "")
    if len(teams) >= 2:
        away = away or str(teams[0].get("name", ""))
        home = home or str(teams[1].get("name", ""))
    return home, away


def _request_events(target_date: date, affiliate_ids: list[int], market_ids: list[int]) -> list[dict[str, Any]]:
    key = _env("THERUNDOWN_API_KEY")
    if not key:
        raise EnvironmentError("THERUNDOWN_API_KEY not set. Add it to .env and GitHub Actions secrets.")
    params = {
        "affiliate_ids": ",".join(map(str, affiliate_ids)),
        "market_ids": ",".join(map(str, market_ids)),
        "main_line": "true",
        "offset": "300",
    }
    url = f"{BASE_URL}/sports/{LIGUE_1_SPORT_ID}/events/{target_date.isoformat()}"
    for attempt in range(3):
        response = requests.get(
            url,
            headers={"X-TheRundown-Key": key},
            params=params,
            timeout=30,
        )
        if response.status_code != 429 or attempt == 2:
            break
        retry_after = float(response.headers.get("Retry-After", "1"))
        print(f"TheRundown rate limit reached; retrying in {retry_after:.1f}s.")
        time.sleep(max(1.0, retry_after))
    if not response.ok:
        raise RuntimeError(f"TheRundown request failed (HTTP {response.status_code}).")
    used = response.headers.get("X-Datapoints-Used", "?")
    remaining = response.headers.get("X-Datapoints-Remaining", "?")
    print(f"TheRundown {target_date}: {used} data points used, {remaining} remaining")
    return list(response.json().get("events") or [])


def fetch_events() -> list[dict[str, Any]]:
    """Fetch upcoming Ligue 1 fixture dates, respecting TheRundown's 1 req/sec cap."""
    affiliate_ids = _csv_ints(_env("THERUNDOWN_AFFILIATE_IDS", "19,22")) or [19, 22]
    market_ids = _csv_ints(_env("THERUNDOWN_MARKET_IDS", "1,2,3")) or [1, 2, 3]
    events: list[dict[str, Any]] = []
    for index, target_date in enumerate(_fixture_dates()):
        if index:
            time.sleep(1)
        events.extend(_request_events(target_date, affiliate_ids, market_ids))
    return events


def market_rows(events: list[dict[str, Any]], fetched_at: str | None = None) -> list[dict[str, Any]]:
    """Flatten Rundown events into provider-neutral decimal-odds market rows."""
    fetched_at = fetched_at or datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    rows: list[dict[str, Any]] = []
    for event in events:
        home, away = _event_teams(event)
        for raw_market in event.get("markets") or []:
            market = MARKET_IDS.get(raw_market.get("market_id"))
            if not market or raw_market.get("period_id", 0) != 0:
                continue
            for participant in raw_market.get("participants") or []:
                outcome = str(participant.get("name", ""))
                if market in {"1X2", "Spread"}:
                    lowered = outcome.lower()
                    if lowered == home.lower():
                        outcome = "Home"
                    elif lowered == away.lower():
                        outcome = "Away"
                    elif lowered in {"draw", "tie", "x"}:
                        outcome = "Draw"
                elif market == "Totals":
                    if outcome.lower().startswith("over"):
                        outcome = "Over"
                    elif outcome.lower().startswith("under"):
                        outcome = "Under"
                for line in participant.get("lines") or []:
                    for affiliate_id, quote in (line.get("prices") or {}).items():
                        decimal = _decimal_price(quote.get("price"))
                        if decimal is None:
                            continue
                        try:
                            affiliate_number = int(affiliate_id)
                        except (TypeError, ValueError):
                            affiliate_number = -1
                        rows.append({
                            "SnapshotTime": fetched_at,
                            "Provider": "therundown",
                            "EventId": event.get("event_id"),
                            "Date": str(event.get("event_date", ""))[:10],
                            "HomeTeam": home,
                            "AwayTeam": away,
                            "Bookmaker": AFFILIATES.get(affiliate_number, str(affiliate_id)),
                            "Market": market,
                            "Line": line.get("value", ""),
                            "Outcome": outcome,
                            "Odds": decimal,
                        })
    return rows
