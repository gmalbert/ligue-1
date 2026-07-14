# TheRundown Odds Integration Guide

This guide migrates a soccer odds pipeline from a provider that requires
per-event odds requests to TheRundown V2. It is designed for data pipelines
that need a simple current 1X2 output and append-only market snapshots.

The central advantage is request shape: TheRundown returns all requested
markets and sportsbooks for a fixture date in a single response. That avoids
the common pattern of listing events and then making one odds request per
event, which can exhaust an hourly request quota.

Official references:

- [Sports and league IDs](https://docs.therundown.io/reference/sports)
- [Market IDs](https://docs.therundown.io/reference/markets)
- [Events and odds response structure](https://docs.therundown.io/guides/getting-live-odds)

## Prerequisites

1. Create a TheRundown account and API key.
2. Add `THERUNDOWN_API_KEY` to the local `.env` file.
3. Add the same value as a GitHub Actions repository secret.
4. Install `pandas`, `requests`, and `python-dotenv`.

```bash
pip install pandas requests python-dotenv
```

Never commit the key. Send it in `X-TheRundown-Key`, not in a query string:

```python
headers = {"X-TheRundown-Key": os.environ["THERUNDOWN_API_KEY"]}
```

## Core IDs and conventions

| Item | Value |
|---|---|
| Ligue 1 sport ID | `12` |
| Moneyline / 1X2 market | `1` |
| Spread / handicap market | `2` |
| Total goals market | `3` |
| DraftKings affiliate | `19` |
| BetMGM affiliate | `22` |
| FanDuel affiliate | `23` |
| Pinnacle affiliate | `3` |

Soccer moneyline is a three-participant market: home team, draw, and away
team. The API price is American odds; convert it before feeding a decimal-odds
model. A price of `0.0001` means the market is off the board and must be
discarded.

## Configuration

Use environment variables so a single client works across leagues and repos:

```dotenv
ODDS_PROVIDER=therundown
THERUNDOWN_API_KEY=replace_me
THERUNDOWN_AFFILIATE_IDS=19,22
THERUNDOWN_MARKET_IDS=1,2,3
THERUNDOWN_LOOKAHEAD_DAYS=45
```

The date window is only a fallback. Prefer obtaining fixture dates from the
repo's schedule/fixtures source and call TheRundown only for those dates.
This avoids pointless requests and reliably catches opening lines more than a
few weeks ahead.

## Drop-in client

Create `fetch_rundown.py` (or equivalent) with the following implementation.
Change `SPORT_ID` for a different league.

```python
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://therundown.io/api/v2"
SPORT_ID = 12  # Ligue 1
MARKETS = {1: "1X2", 2: "Spread", 3: "Totals"}
AFFILIATES = {3: "Pinnacle", 19: "DraftKings", 22: "BetMGM", 23: "FanDuel"}
OFF_BOARD_PRICE = 0.0001


def american_to_decimal(value: Any) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price in {0, OFF_BOARD_PRICE}:
        return None
    return 1 + price / 100 if price > 0 else 1 + 100 / abs(price)


def request_events(target_date: date, affiliate_ids: list[int], market_ids: list[int]) -> list[dict]:
    key = os.getenv("THERUNDOWN_API_KEY", "").strip()
    if not key:
        raise EnvironmentError("Set THERUNDOWN_API_KEY")

    url = f"{BASE_URL}/sports/{SPORT_ID}/events/{target_date.isoformat()}"
    params = {
        "affiliate_ids": ",".join(map(str, affiliate_ids)),
        "market_ids": ",".join(map(str, market_ids)),
        "main_line": "true",  # suppress alternate spread/total lines
        "offset": "300",      # US Central date boundary
    }
    for attempt in range(3):
        response = requests.get(url, headers={"X-TheRundown-Key": key}, params=params, timeout=30)
        if response.status_code != 429 or attempt == 2:
            break
        time.sleep(max(1.0, float(response.headers.get("Retry-After", "1"))))

    if not response.ok:
        # Do not call raise_for_status() here: its exception can include the
        # full request URL if a future client switches to query-string auth.
        raise RuntimeError(f"TheRundown request failed (HTTP {response.status_code}).")

    print(
        "TheRundown usage:",
        response.headers.get("X-Datapoints-Used", "?"),
        "used /",
        response.headers.get("X-Datapoints-Remaining", "?"),
        "remaining",
    )
    return list(response.json().get("events") or [])


def fetch_dates(dates: list[date]) -> list[dict]:
    """Fetch dates sequentially; TheRundown allows one request per second."""
    events: list[dict] = []
    for index, target_date in enumerate(sorted(set(dates))):
        if index:
            time.sleep(1)
        events.extend(request_events(target_date, [19, 22], [1, 2, 3]))
    return events


def event_teams(event: dict) -> tuple[str, str]:
    teams = event.get("teams") or []
    away = next((t.get("name", "") for t in teams if t.get("is_away")), "")
    home = next((t.get("name", "") for t in teams if t.get("is_home")), "")
    # The documented ordering is away, then home; retain this fallback for
    # responses without explicit flags.
    if len(teams) >= 2:
        away = away or teams[0].get("name", "")
        home = home or teams[1].get("name", "")
    return str(home), str(away)
```

## Flattening into a provider-neutral snapshot table

Use one row per event / sportsbook / market / outcome. This supports historical
snapshots, consensus features, and provider changes without changing the raw
format.

```python
from datetime import datetime, timezone


def flatten_events(events: list[dict]) -> list[dict]:
    rows = []
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for event in events:
        home, away = event_teams(event)
        for raw_market in event.get("markets") or []:
            market = MARKETS.get(raw_market.get("market_id"))
            if not market or raw_market.get("period_id", 0) != 0:
                continue
            for participant in raw_market.get("participants") or []:
                name = str(participant.get("name", ""))
                lower = name.lower()
                outcome = name
                if market in {"1X2", "Spread"}:
                    outcome = "Home" if lower == home.lower() else "Away" if lower == away.lower() else "Draw" if lower in {"draw", "tie", "x"} else name
                elif market == "Totals":
                    outcome = "Over" if lower.startswith("over") else "Under" if lower.startswith("under") else name

                for line in participant.get("lines") or []:
                    for affiliate_id, quote in (line.get("prices") or {}).items():
                        odds = american_to_decimal(quote.get("price"))
                        if odds is None:
                            continue
                        affiliate = int(affiliate_id)
                        rows.append({
                            "SnapshotTime": fetched_at,
                            "Provider": "therundown",
                            "EventId": event.get("event_id"),
                            "Date": str(event.get("event_date", ""))[:10],
                            "HomeTeam": home,
                            "AwayTeam": away,
                            "Bookmaker": AFFILIATES.get(affiliate, str(affiliate_id)),
                            "Market": market,
                            "Line": line.get("value", ""),
                            "Outcome": outcome,
                            "Odds": odds,
                            "ImpliedProbability": round(1 / odds, 6),
                        })
    return rows
```

For a current 1X2 table, filter `Market == "1X2"`, pivot the `Home`, `Draw`,
and `Away` outcomes by `Date`, teams, and bookmaker, then remove incomplete
three-outcome rows. Normalize the implied probabilities by their total to
remove each bookmaker's margin.

## GitHub Actions

Pass the secret into every step that fetches odds. Do not reuse an old provider
selector secret if that can point the workflow back to the previous provider.

```yaml
- name: Fetch bookmaker odds
  env:
    ODDS_PROVIDER: therundown
    THERUNDOWN_API_KEY: ${{ secrets.THERUNDOWN_API_KEY }}
    THERUNDOWN_AFFILIATE_IDS: 19,22
    THERUNDOWN_MARKET_IDS: 1,2,3
  run: python fetch_odds.py

- name: Fetch market odds snapshots
  env:
    ODDS_PROVIDER: therundown
    THERUNDOWN_API_KEY: ${{ secrets.THERUNDOWN_API_KEY }}
    THERUNDOWN_AFFILIATE_IDS: 19,22
    THERUNDOWN_MARKET_IDS: 1,2,3
  run: python fetch_market_odds.py
```

## Validation and operational checks

Perform one small authenticated request before enabling a full scheduled job:

```python
from datetime import date
from fetch_rundown import request_events

events = request_events(date.today(), [19, 22], [1, 2, 3])
print(f"Authenticated successfully; returned {len(events)} events")
```

An empty event list is normal in the off-season. A successful response should
still report data-point usage headers. During normal runs:

1. Respect one request per second across date requests.
2. Retry `429` only after `Retry-After` (or one second if absent).
3. Log usage headers, but never log the API key.
4. Drop `0.0001` prices; they mean the book has taken the market off board.
5. Keep `Provider` in every snapshot; never compare historical line movement
   across two providers as though it came from one continuous feed.

## Scope and limitations

This integration deliberately requests only 1X2, spread, and total-goals main
lines from two books. It does **not** provide direct BTTS, player props,
alternate lines, live odds, or a broad multi-book consensus. If your model
needs BTTS while using this restricted setup, use the companion
`derived-btts-features-guide.md` and label the fallback as model-derived.

## Implementation in this repository

The production implementation lives in `fetch_rundown.py`; `fetch_odds.py`
adapts moneyline records into the legacy `odds.csv` schema, and
`fetch_market_odds.py` writes the append-only market snapshot schema.
