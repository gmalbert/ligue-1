"""Small quota-aware API-Football client.

The free API-Football key is limited, so all enrichment scripts share a simple
daily ledger before making network calls. This keeps exploratory scripts from
quietly burning through the 100 request/day allowance.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").strip()
API_KEY = (
    os.getenv("API_FOOTBALL_KEY")
    or os.getenv("APIFOOTBALL_KEY")
    or os.getenv("API_SPORTS_KEY")
    or ""
).strip().strip("\"'")
DAILY_LIMIT = int(os.getenv("API_FOOTBALL_DAILY_LIMIT", "100"))
DAILY_RESERVE = int(os.getenv("API_FOOTBALL_DAILY_RESERVE", "10"))
USAGE_PATH = Path(os.getenv("API_FOOTBALL_USAGE_PATH", "data_files/api_usage/api_football_usage.json"))


class ApiFootballQuotaError(RuntimeError):
    """Raised when the local daily API-Football quota ledger is exhausted."""


class ApiFootballHTTPError(RuntimeError):
    """Raised for non-2xx API-Football responses."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"API-Football returned HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def _today_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_usage() -> dict[str, Any]:
    if not USAGE_PATH.exists():
        return {"date": _today_key(), "used": 0}
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {"date": _today_key(), "used": 0}
    if data.get("date") != _today_key():
        return {"date": _today_key(), "used": 0}
    return {"date": data.get("date", _today_key()), "used": int(data.get("used", 0))}


def _write_usage(data: dict[str, Any]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USAGE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def quota_status() -> dict[str, int | str]:
    usage = _read_usage()
    usable_limit = max(0, DAILY_LIMIT - DAILY_RESERVE)
    remaining = max(0, usable_limit - int(usage["used"]))
    return {
        "date": str(usage["date"]),
        "used": int(usage["used"]),
        "daily_limit": DAILY_LIMIT,
        "reserve": DAILY_RESERVE,
        "usable_limit": usable_limit,
        "remaining": remaining,
    }


def _consume_quota(units: int = 1) -> None:
    usage = _read_usage()
    usable_limit = max(0, DAILY_LIMIT - DAILY_RESERVE)
    if int(usage["used"]) + units > usable_limit:
        raise ApiFootballQuotaError(
            "API-Football local quota guard stopped this run: "
            f"{usage['used']} used, {usable_limit} usable today "
            f"({DAILY_LIMIT} limit with {DAILY_RESERVE} reserved)."
        )
    usage["used"] = int(usage["used"]) + units
    _write_usage(usage)


def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET an API-Football endpoint and return the parsed response body."""
    if not API_KEY:
        raise EnvironmentError("API_FOOTBALL_KEY is not set in .env.")

    _consume_quota(1)
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        resp = requests.get(
            url,
            params=params or {},
            headers={"x-apisports-key": API_KEY},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"API-Football request failed before a response was received ({type(exc).__name__})."
        ) from None

    if not resp.ok:
        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = resp.text
        raise ApiFootballHTTPError(resp.status_code, body) from None
    body = resp.json()
    errors = body.get("errors") if isinstance(body, dict) else None
    if errors:
        raise RuntimeError(f"API-Football returned provider errors: {errors}")
    return body
