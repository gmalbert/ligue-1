"""Fetch upcoming Ligue-1 match odds.

Saves: data_files/raw/odds.csv

Usage:
    python fetch_odds.py

Requires:
    ODDS_PROVIDER in .env (optional: therundown, odds_api_io, or the_odds_api)
    THERUNDOWN_API_KEY in .env for TheRundown
    ODDS_API_IO_KEY in .env for odds-api.io
    ODDS_API_KEY in .env for The Odds API
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from fetch_utils import request_with_retry
from team_name_mapping import normalize_dataframe_teams
import fetch_rundown

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip().strip("\"'")

ODDS_PROVIDER = _env("ODDS_PROVIDER").lower()
ODDS_API_KEY = _env("ODDS_API_KEY")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_IO_KEY = _env("ODDS_API_IO_KEY")
ODDS_API_IO_BASE = _env("ODDS_API_IO_BASE", "https://api.odds-api.io/v3")
ODDS_API_IO_SPORT = _env("ODDS_API_IO_SPORT", "football")
ODDS_API_IO_LEAGUE = _env("ODDS_API_IO_LEAGUE", "france-ligue-1")
ODDS_API_IO_BOOKMAKERS = _env("ODDS_API_IO_BOOKMAKERS")

# Ligue-1 sport key for The Odds API
SPORT_KEY = "soccer_france_ligue_one"

OUT_PATH = "data_files/raw/odds.csv"
OUTPUT_COLUMNS = [
    "Date",
    "HomeTeam",
    "AwayTeam",
    "Bookmaker",
    "HomeWinOdds",
    "DrawOdds",
    "AwayWinOdds",
    "ImpliedProb_HomeWin",
    "ImpliedProb_Draw",
    "ImpliedProb_AwayWin",
    "BookmakerMargin",
]


class OddsApiHTTPError(RuntimeError):
    """HTTP error with sanitized details for odds provider requests."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"Odds provider returned HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def _clear_stale_odds() -> None:
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(OUT_PATH, index=False)


def _write_odds(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty:
        df = normalize_dataframe_teams(df)

    if not df.empty:
        df["RawHome"] = 1 / df["HomeWinOdds"]
        df["RawDraw"] = 1 / df["DrawOdds"]
        df["RawAway"] = 1 / df["AwayWinOdds"]
        total = df["RawHome"] + df["RawDraw"] + df["RawAway"]
        df["ImpliedProb_HomeWin"] = (df["RawHome"] / total).round(4)
        df["ImpliedProb_Draw"] = (df["RawDraw"] / total).round(4)
        df["ImpliedProb_AwayWin"] = (df["RawAway"] / total).round(4)
        df["BookmakerMargin"] = ((total - 1) * 100).round(2)
        df.drop(columns=["RawHome", "RawDraw", "RawAway"], inplace=True)
        df = df[OUTPUT_COLUMNS]
    else:
        df = pd.DataFrame(columns=OUTPUT_COLUMNS)

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    return df


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_csv_env(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _request_json(url: str, params: dict[str, Any], timeout: int = 20) -> tuple[Any, Any]:
    try:
        resp = request_with_retry(url, params=params, timeout=timeout)
    except Exception as exc:
        raise RuntimeError(
            f"Odds provider request failed ({type(exc).__name__})."
        ) from None

    if not resp.ok:
        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = resp.text
        print(f"Odds request failed ({resp.status_code}): {body}")
        raise OddsApiHTTPError(resp.status_code, body) from None
    return resp.json(), resp


def fetch_the_odds_api_odds() -> pd.DataFrame:
    """Fetch upcoming Ligue-1 match odds (1X2 moneyline) from The Odds API."""
    if not ODDS_API_KEY:
        raise EnvironmentError(
            "ODDS_API_KEY not set. Copy .env.example to .env and add your key."
        )

    games, _ = _request_json(
        f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds",
        params={
            "apiKey":      ODDS_API_KEY,
            "regions":     "us",
            "markets":     "h2h",          # 1X2 moneyline
            "oddsFormat":  "decimal",
            "bookmakers":  "draftkings,betmgm,pinnacle",
        },
        timeout=15,
    )

    rows: list[dict] = []
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        date = game["commence_time"][:10]

        for bm in game.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                prices = {o["name"]: o["price"] for o in market["outcomes"]}
                rows.append({
                    "Date":         date,
                    "HomeTeam":     home,
                    "AwayTeam":     away,
                    "Bookmaker":    bm["key"],
                    "HomeWinOdds":  prices.get(home),
                    "DrawOdds":     prices.get("Draw"),
                    "AwayWinOdds":  prices.get(away),
                })

    df = _write_odds(pd.DataFrame(rows))
    print(f"Fetched odds for {len(games)} games from The Odds API -> {OUT_PATH}")
    return df


def _odds_api_io_get(path: str, params: dict[str, Any] | None = None) -> tuple[Any, requests.Response]:
    if not ODDS_API_IO_KEY:
        raise EnvironmentError(
            "ODDS_API_IO_KEY not set. Copy .env.example to .env and add your key."
        )

    all_params: dict[str, Any] = {"apiKey": ODDS_API_IO_KEY}
    if params:
        all_params.update(params)
    return _request_json(f"{ODDS_API_IO_BASE}/{path.lstrip('/')}", all_params)


def _selected_odds_api_io_bookmakers() -> list[str]:
    body, resp = _odds_api_io_get("bookmakers/selected")
    remaining = resp.headers.get("x-ratelimit-remaining")
    reset = resp.headers.get("x-ratelimit-reset")
    if remaining is not None:
        print(f"odds-api.io rate limit remaining: {remaining} (resets {reset or 'unknown'})")
    return list(body.get("bookmakers", []))


def _odds_api_io_bookmakers() -> list[str]:
    configured = _parse_csv_env(ODDS_API_IO_BOOKMAKERS)
    if configured:
        return configured
    selected = _selected_odds_api_io_bookmakers()
    if not selected:
        raise RuntimeError("odds-api.io returned no selected bookmakers for this account.")
    return selected


def _discover_odds_api_io_league() -> str:
    if ODDS_API_IO_LEAGUE:
        return ODDS_API_IO_LEAGUE

    leagues, _ = _odds_api_io_get("leagues", {"sport": ODDS_API_IO_SPORT, "all": "true"})
    candidates: list[dict[str, Any]] = []
    for league in leagues:
        name = str(league.get("name", ""))
        slug = str(league.get("slug", ""))
        haystack = f"{name} {slug}".lower()
        if "ligue" in haystack and ("1" in haystack or "one" in haystack) and "france" in haystack:
            candidates.append(league)

    if not candidates:
        examples = ", ".join(
            str(league.get("slug") or league.get("name")) for league in leagues[:12]
        )
        raise RuntimeError(
            "Could not auto-discover the odds-api.io Ligue 1 league slug. "
            "Set ODDS_API_IO_LEAGUE in .env. "
            f"First returned leagues: {examples}"
        )

    candidates.sort(key=lambda item: str(item.get("slug", "")))
    league = str(candidates[0].get("slug"))
    print(f"Discovered odds-api.io Ligue 1 league: {league}")
    return league


def _fetch_odds_api_io_events(league: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    limit = 50
    skip = 0
    while True:
        batch, _ = _odds_api_io_get(
            "events",
            {
                "sport": ODDS_API_IO_SPORT,
                "league": league,
                "status": "pending,live",
                "limit": limit,
                "skip": skip,
            },
        )
        if not batch:
            break
        events.extend(batch)
        if len(batch) < limit:
            break
        skip += limit
    return events


def _extract_odds_api_io_ml(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for market in markets:
        market_name = str(market.get("name", "")).lower()
        if market_name not in {"ml", "moneyline", "match winner", "1x2"}:
            continue
        odds = market.get("odds") or []
        if odds:
            return odds[0]
    return None


def _extract_odds_api_io_prices(ml: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    home = _float_or_none(ml.get("home"))
    away = _float_or_none(ml.get("away"))
    draw = (
        _float_or_none(ml.get("draw"))
        or _float_or_none(ml.get("tie"))
        or _float_or_none(ml.get("x"))
    )

    # Some 1X2 feeds may emit named outcomes instead of home/draw/away keys.
    outcomes = ml.get("outcomes")
    if isinstance(outcomes, list):
        for outcome in outcomes:
            name = str(outcome.get("name", "")).lower()
            price = _float_or_none(outcome.get("price") or outcome.get("odds"))
            if not price:
                continue
            if name in {"draw", "tie", "x"}:
                draw = price
            elif name in {"home", "1"}:
                home = price
            elif name in {"away", "2"}:
                away = price

    return home, draw, away


def fetch_odds_api_io_odds() -> pd.DataFrame:
    """Fetch upcoming Ligue-1 match odds from odds-api.io."""
    league = _discover_odds_api_io_league()
    bookmakers = _odds_api_io_bookmakers()
    events = _fetch_odds_api_io_events(league)

    rows: list[dict[str, Any]] = []
    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        try:
            odds, _ = _odds_api_io_get(
                "odds",
                {"eventId": event_id, "bookmakers": ",".join(bookmakers)},
            )
        except OddsApiHTTPError as exc:
            if exc.status_code == 403:
                allowed = _selected_odds_api_io_bookmakers()
                odds, _ = _odds_api_io_get(
                    "odds",
                    {"eventId": event_id, "bookmakers": ",".join(allowed)},
                )
            else:
                raise

        home = odds.get("home") or event.get("home") or event.get("homeTeam")
        away = odds.get("away") or event.get("away") or event.get("awayTeam")
        date = str(odds.get("date") or event.get("date") or event.get("commence_time") or "")[:10]

        for bookmaker, markets in (odds.get("bookmakers") or {}).items():
            ml = _extract_odds_api_io_ml(markets)
            if not ml:
                continue
            home_odds, draw_odds, away_odds = _extract_odds_api_io_prices(ml)
            if not all([home_odds, draw_odds, away_odds]):
                continue
            rows.append({
                "Date": date,
                "HomeTeam": home,
                "AwayTeam": away,
                "Bookmaker": bookmaker,
                "HomeWinOdds": home_odds,
                "DrawOdds": draw_odds,
                "AwayWinOdds": away_odds,
            })

    df = _write_odds(pd.DataFrame(rows))
    print(f"Fetched odds for {len(events)} events from odds-api.io -> {OUT_PATH}")
    return df


def fetch_therundown_odds() -> pd.DataFrame:
    """Fetch upcoming Ligue 1 1X2 odds from TheRundown."""
    raw = pd.DataFrame(fetch_rundown.market_rows(fetch_rundown.fetch_events()))
    raw = raw[
        raw["Market"].eq("1X2")
        & raw["Outcome"].isin(["Home", "Draw", "Away"])
    ] if not raw.empty else raw
    if raw.empty:
        df = _write_odds(pd.DataFrame())
    else:
        prices = raw.pivot_table(
            index=["Date", "HomeTeam", "AwayTeam", "Bookmaker"],
            columns="Outcome",
            values="Odds",
            aggfunc="first",
        ).reset_index()
        prices.columns.name = None
        prices = prices.rename(columns={
            "Home": "HomeWinOdds", "Draw": "DrawOdds", "Away": "AwayWinOdds",
        })
        prices = prices.dropna(subset=["HomeWinOdds", "DrawOdds", "AwayWinOdds"])
        df = _write_odds(prices)
    print(f"Fetched odds for {len(df)} bookmaker-event rows from TheRundown -> {OUT_PATH}")
    return df


def fetch_upcoming_odds() -> pd.DataFrame:
    """Fetch upcoming Ligue-1 match odds from the configured provider."""
    provider = ODDS_PROVIDER
    if not provider:
        provider = "therundown" if os.getenv("THERUNDOWN_API_KEY") else (
            "odds_api_io" if ODDS_API_IO_KEY else "the_odds_api"
        )
    provider = provider.replace(".", "_")

    try:
        if provider in {"therundown", "the_rundown", "the-rundown", "rundown"}:
            return fetch_therundown_odds()
        if provider in {"odds_api_io", "odds-api-io", "oddsapiio"}:
            return fetch_odds_api_io_odds()
        if provider in {"the_odds_api", "the-odds-api", "theoddsapi"}:
            return fetch_the_odds_api_odds()
        raise ValueError(
            "Unsupported ODDS_PROVIDER. Use therundown, odds_api_io, or the_odds_api."
        )
    except Exception:
        _clear_stale_odds()
        print(f"Odds fetch failed. Cleared {OUT_PATH} to avoid stale markets.")
        raise


if __name__ == "__main__":
    fetch_upcoming_odds()
