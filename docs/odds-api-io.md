# odds-api.io — Integration Guide

API docs: <https://docs.odds-api.io/>
Base URL: `https://api.odds-api.io/v3`

---

## Overview

odds-api.io is a real-time sports betting odds API with 250+ bookmakers across
34 sports (as of April 2026). It is distinct from The Odds API (the-odds-api.com)
despite the similar name.

**Coverage tested**: Rugby Union, Rugby League — April 27 2026.

---

## Authentication

API key is passed as a **query parameter** on every request:

```
GET /v3/events?apiKey=YOUR_KEY&sport=rugby
```

Store in `.env` as `ODDS_API_IO_KEY` (separate from `ODDS_API_KEY` which is
used for The Odds API).

> **Never** pass the key in client-side code. Always call from a backend process
> or pipeline script.

---

## Rate Limits

Response headers on every request:

| Header | Description |
|---|---|
| `x-ratelimit-limit` | Total requests allowed in the current window |
| `x-ratelimit-remaining` | Requests left in this window |
| `x-ratelimit-reset` | ISO 8601 UTC timestamp when the window resets |

**Free plan**: 100 req/hour (note: the docs quote 5 000 but the free-tier key
observed in testing is capped at 100). Paid plans start at 5 000 req/hour.

On `429` the response body is:
```json
{"error": "Rate limit exceeded. Please try again later."}
```

---

## Plans & Bookmaker Access

| Plan | Max bookmakers | Additional packages |
|---|---|---|
| Free | **2** (pre-selected at signup) | N/A |
| Starter / Growth / Pro | 5 000 req/hr base | +10K / 20K / 30K req/hr |

On the free plan your two allowed bookmakers are locked at account creation.
The current free-tier selection is **DraftKings** and **BetMGM BR**.

To see which bookmakers are currently selected:
```
GET /v3/bookmakers/selected?apiKey=YOUR_KEY
# → {"bookmakers": ["DraftKings", "BetMGM BR"], "count": 2}
```

Requesting odds for a bookmaker outside your allowed list returns `403`:
```json
{
  "error": "Access denied. You're allowed max 2 bookmakers. Allowed: DraftKings, BetMGM BR."
}
```

---

## Endpoints

### `GET /sports` — no auth required
Returns list of all sports with `name` and `slug`.

```python
import urllib.request, json
sports = json.loads(urllib.request.urlopen("https://api.odds-api.io/v3/sports").read())
# 34 sports as of April 2026, including "rugby" slug
```

### `GET /leagues?apiKey=KEY&sport=SLUG`
Returns leagues for a sport. Add `&all=true` to include leagues with zero
active events (useful for slug discovery).

```python
leagues = api_get("leagues", {"sport": "rugby", "all": "true"})
# Returns 63 leagues covering Rugby Union, Rugby League, Sevens
```

### `GET /events?apiKey=KEY&sport=SLUG`
Returns upcoming / live events. Key filters:

| Parameter | Example | Notes |
|---|---|---|
| `league` | `rugby-union-super-rugby` | league slug |
| `status` | `pending,live` | comma-separated |
| `bookmaker` | `DraftKings` | filter to events with odds from this bookmaker |
| `from` / `to` | `2026-05-01T00:00:00Z` | RFC3339 date range |
| `limit` | `50` | max per page |
| `skip` | `50` | pagination offset |
| `participantId` | `12345` | filter by team ID |

> **`bookmakerCount` is unreliable.** The field appears as `0` for all rugby
> events in the list response, even when odds *are* available via `GET /odds`.
> Always call `GET /odds` directly to confirm coverage; do not skip events based
> on `bookmakerCount`.

### `GET /odds?apiKey=KEY&eventId=ID&bookmakers=BM1,BM2`
Returns full odds for a single event. `bookmakers` is required and must be a
comma-separated list from your allowed set.

> URL-encode bookmaker names that contain spaces:
> `BetMGM%20BR` not `BetMGM BR`.

Response shape:
```json
{
  "id": 70120718,
  "home": "New Zealand",
  "away": "Australia",
  "date": "2026-05-01T...",
  "status": "pending",
  "league": {"name": "Rugby Union - U20 The Rugby Championship", "slug": "..."},
  "sport":  {"name": "Rugby", "slug": "rugby"},
  "bookmakers": {
    "BetMGM BR": [
      {"name": "ML",     "odds": [{"home": "1.45", "away": "2.60"}]},
      {"name": "Spread", "odds": [{"hdp": -6.5, "home": "1.87", "away": "1.87"}, ...]},
      {"name": "Totals", "odds": [{"hdp": 63.5, "over": "1.87", "under": "1.87"}, ...]}
    ]
  },
  "urls": {"BetMGM BR": "https://..."}
}
```

### `GET /bookmakers` — list all bookmakers
Returns all 279 bookmakers with `name` and `active` flag. No auth required.

### `GET /bookmakers/selected` — your selected bookmakers
Returns `{"bookmakers": [...], "count": N}` for the authenticated account.

---

## Odds Format

All odds are returned as **decimal strings** (European format), e.g. `"1.45"`.
The existing `utils/odds.py` helpers use American odds — use the converters
below:

```python
def decimal_to_implied(decimal_odds: float) -> float:
    """Decimal odds (e.g. 1.45) → implied probability [0,1]."""
    return 1.0 / decimal_odds

def decimal_to_american(decimal_odds: float) -> float:
    """Decimal odds → American money-line odds."""
    if decimal_odds >= 2.0:
        return (decimal_odds - 1) * 100
    else:
        return -100 / (decimal_odds - 1)
```

For the Spread market, multiple lines are returned (every available handicap).
To extract the main line (closest handicap to 0):

```python
def main_spread_line(spread_odds: list[dict]) -> dict | None:
    if not spread_odds:
        return None
    return min(spread_odds, key=lambda o: abs(o.get("hdp", 999)))
```

---

## Reusable Client

```python
"""
utils/odds_api_io.py — lightweight odds-api.io client
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://api.odds-api.io/v3"


def _api_get(path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict]:
    """
    GET {BASE}/{path} with query params.
    Returns (body, response_headers).
    Raises urllib.error.HTTPError on non-2xx status.
    """
    api_key = os.environ.get("ODDS_API_IO_KEY", "")
    all_params: dict[str, Any] = {"apiKey": api_key}
    if params:
        all_params.update(params)
    qs = urllib.parse.urlencode(all_params)
    url = f"{BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()), dict(resp.headers)


def get_sports() -> list[dict]:
    """Return all sports (no auth needed)."""
    req = urllib.request.Request(f"{BASE}/sports",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_leagues(sport: str, include_empty: bool = False) -> list[dict]:
    """Return leagues for a sport. Set include_empty=True to see all slugs."""
    params: dict[str, Any] = {"sport": sport}
    if include_empty:
        params["all"] = "true"
    body, _ = _api_get("leagues", params)
    return body


def get_events(
    sport: str,
    *,
    league: str | None = None,
    status: str = "pending,live",
    bookmaker: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    limit: int = 50,
    skip: int = 0,
) -> list[dict]:
    """Return events for a sport with optional filters."""
    params: dict[str, Any] = {"sport": sport, "status": status,
                               "limit": limit, "skip": skip}
    if league:
        params["league"] = league
    if bookmaker:
        params["bookmaker"] = bookmaker
    if from_dt:
        params["from"] = from_dt
    if to_dt:
        params["to"] = to_dt
    body, _ = _api_get("events", params)
    return body


def get_odds(event_id: int, bookmakers: list[str]) -> dict:
    """
    Return odds for a single event from specified bookmakers.

    bookmakers must be within your plan's allowed set.
    Bookmaker names with spaces are URL-encoded automatically.
    """
    params: dict[str, Any] = {
        "eventId": event_id,
        "bookmakers": ",".join(bookmakers),
    }
    body, _ = _api_get("odds", params)
    return body


def get_rate_limit_info() -> dict:
    """Consume one request and return rate limit metadata."""
    _, hdrs = _api_get("bookmakers/selected")
    return {
        "limit": hdrs.get("x-ratelimit-limit"),
        "remaining": hdrs.get("x-ratelimit-remaining"),
        "reset": hdrs.get("x-ratelimit-reset"),
    }


# ── Odds helpers ──────────────────────────────────────────────

def decimal_to_implied(decimal_odds: float) -> float:
    """Decimal odds → implied probability [0,1]."""
    return 1.0 / decimal_odds


def decimal_to_american(decimal_odds: float) -> float:
    """Decimal odds → American money-line odds (float)."""
    if decimal_odds >= 2.0:
        return (decimal_odds - 1) * 100
    return -100.0 / (decimal_odds - 1)


def main_spread_line(spread_odds: list[dict]) -> dict | None:
    """Return the spread line whose handicap is closest to 0."""
    if not spread_odds:
        return None
    return min(spread_odds, key=lambda o: abs(float(o.get("hdp", 999))))


def extract_ml(bookmaker_markets: list[dict]) -> dict | None:
    """Extract the Money Line (ML) market dict from a bookmaker's market list."""
    for m in bookmaker_markets:
        if m.get("name") == "ML":
            odds = m.get("odds", [])
            return odds[0] if odds else None
    return None
```

---

## Rugby Coverage (tested April 27 2026)

### Sport slug
```
rugby
```

### League slug mapping

| App league | API slug | Active events |
|---|---|---|
| Six Nations | `rugby-union-six-nations` | 0 (off-season) |
| Premiership Rugby | `rugby-union-english-premiership` | 10 |
| Top 14 | `rugby-union-top-14` | 14 |
| Super Rugby Pacific | `rugby-union-super-rugby` | 19 |
| United Rugby Championship | `rugby-union-united-rugby-championship` | 16 |
| European Champions Cup | `rugby-union-european-rugby-champions-cup` | 2 |

> **Note**: The API slug is `rugby-union-super-rugby` — there is no
> "pacific" suffix. Six Nations has 0 events out of season (April) but is
> present with `all=true`.

### Bookmaker coverage for rugby (free tier)

| Bookmaker | Coverage |
|---|---|
| **DraftKings** | Super Rugby Union, NRL Premiership — **ML only** |
| **BetMGM BR** | International Rugby Union (e.g. U20 Rugby Championship) — **ML, Spread (all lines), Totals, HT/FT, Team Totals, European Handicap, First Team To Score** |

Neither bookmaker covers: Premiership Rugby, Top 14, URC, European Champions Cup,
Six Nations, or Super League. To get odds on club rugby (Prem, Top 14, URC) you
will need a paid plan with access to Bet365, William Hill, Unibet, or equivalent
European bookmakers.

### All 63 rugby leagues (ranked by active events, April 2026)

```
Rugby League - NRL Premiership                    (29 events)
Rugby League - RFL Championship                   (27 events)
Rugby Union  - NSW Shute Shield                   (24 events)
Rugby League - New South Wales Cup                (22 events)
Rugby League - Super League                       (21 events)
Rugby Union  - URBA Top 12                        (21 events)
Rugby League - Queensland Cup                     (19 events)
Rugby Union  - Super Rugby                        (19 events)
Rugby Union  - Pro D2                             (16 events)
Rugby Union  - United Rugby Championship          (16 events)
Rugby Union  - Top 14                             (14 events)
Rugby Union  - English Premiership                (10 events)
Rugby Union  - Super Rugby Americas               (12 events)
... (50 more leagues with 0-9 events)
```

---

## Other Sports — Quick Reference

All sports confirmed available as of April 2026:

| Sport | Slug |
|---|---|
| Football (soccer) | `football` |
| Basketball | `basketball` |
| American Football | `american-football` |
| Ice Hockey | `ice-hockey` |
| Tennis | `tennis` |
| Baseball | `baseball` |
| Rugby | `rugby` |
| Cricket | `cricket` |
| Aussie Rules | `aussie-rules` |
| Golf | `golf` |
| MMA | `mixed-martial-arts` |
| Boxing | `boxing` |
| Darts | `darts` |
| Handball | `handball` |
| Volleyball | `volleyball` |
| Snooker | `snooker` |
| Table Tennis | `table-tennis` |

Full list: `GET https://api.odds-api.io/v3/sports` (no auth needed).

DraftKings and BetMGM BR both confirmed to cover **American Football** (UFL).

---

## Error Handling

```python
import urllib.error

try:
    odds = get_odds(event_id, ["DraftKings", "BetMGM BR"])
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    if e.code == 401:
        # Invalid or missing API key
        ...
    elif e.code == 403:
        # Bookmaker not in your plan's allowed list
        # body["error"] contains the allowed bookmakers
        ...
    elif e.code == 429:
        # Rate limit — back off until x-ratelimit-reset
        reset_time = e.headers.get("x-ratelimit-reset")
        ...
    elif e.code == 404:
        # Event ID doesn't exist
        ...
```

---

## Gotchas & Quirks

1. **`bookmakerCount` is always 0 in event lists** — the field is unreliable on
   the free tier. Do not use it to pre-filter events; call `GET /odds` directly.

2. **URL-encode bookmaker names with spaces** — `"BetMGM BR"` must be sent as
   `BetMGM%20BR`. The `urllib.parse.urlencode` helper handles this automatically;
   manual string concatenation does not.

3. **Spread market returns all available lines** — not just the main line.
   Use `main_spread_line()` to get the line closest to even (hdp ≈ 0).

4. **Odds are decimal strings, not American** — `"1.45"` means 45% implied
   probability, not American odds. Use `decimal_to_implied()` /
   `decimal_to_american()` from the client above.

5. **The free-tier bookmakers are US-focused** — DraftKings and BetMGM BR
   offer limited rugby coverage (Super Rugby, NRL, and international rugby only).
   European club rugby (Premiership, Top 14, URC) requires a paid plan and
   European bookmakers (Bet365, Unibet, William Hill, etc.).

6. **No `/me` or `/account` endpoint** — there is no API method to check your
   plan details programmatically. Use `GET /bookmakers/selected` to infer allowed
   bookmakers.

7. **Rate-limit window** — free plan is 100 req/hour (observed). The docs state
   5 000 but that appears to apply to paid plans only.

8. **`all=true` required to discover off-season league slugs** — e.g. Six Nations
   shows 0 events in April but is present with `&all=true`.

---

## Integration Checklist for a New Sport Repo

1. Add `ODDS_API_IO_KEY` to `.env` (keep separate from `ODDS_API_KEY`).
2. Copy `utils/odds_api_io.py` from this repo.
3. Run `GET /leagues?sport=SLUG&all=true` to discover the exact league slugs
   for your competitions and build a mapping table.
4. Check which of your target bookmakers actually provide odds for the sport
   by calling `GET /events?sport=SLUG&bookmaker=DraftKings&limit=5` — if events
   come back, DraftKings covers that sport.
5. Use `GET /odds` with `DraftKings,BetMGM%20BR` as bookmakers on the free tier.
6. Upgrade to a paid plan to access Bet365, Unibet, etc. for broader coverage.
7. Cache odds data with `@st.cache_data(ttl=300)` (5 min) to stay well within
   rate limits.
8. Always check `x-ratelimit-remaining` and log a warning below 10.
