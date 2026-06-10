"""Fetch weather data for upcoming Ligue-1 fixtures.

Uses the Open-Meteo API (free, no API key required).
For each upcoming fixture, looks up the stadium coordinates and fetches
the forecast for that match date.

Outputs:
    data_files/raw/match_weather.csv

Usage:
    python fetch_weather_data.py

Called by: automation/nightly_pipeline.py
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from fetch_utils import request_with_retry
from team_name_mapping import normalize_team_name

# ── Stadium Coordinates ────────────────────────────────────────────────────
# (latitude, longitude) for each Ligue-1 club's home stadium
STADIUM_COORDS: dict[str, tuple[float, float]] = {
    "Paris SG":                  (48.8414,  2.2530),   # Parc des Princes
    "Marseille":                 (43.2698,  5.3958),   # Stade Vélodrome
    "Lyon":                      (45.7652,  4.9820),   # Parc Olympique Lyonnais
    "Monaco":                    (43.7275,  7.4156),   # Stade Louis II
    "Lille":                     (50.6119,  3.1304),   # Stade Pierre-Mauroy
    "Nice":                      (43.7051,  7.1926),   # Allianz Riviera
    "Lens":                      (50.4329,  2.8153),   # Stade Bollaert-Delelis
    "Rennes":                    (48.1075, -1.7128),   # Roazhon Park
    "Bordeaux":                  (44.8978, -0.5612),   # Matmut Atlantique
    "Montpellier":               (43.6225,  3.8121),   # Stade de la Mosson
    "Reims":                     (49.2468,  4.0250),   # Stade Auguste-Delaune
    "Nantes":                    (47.2561, -1.5247),   # Stade de la Beaujoire
    "Toulouse":                  (43.5833,  1.4342),   # Stadium de Toulouse
    "Strasbourg":                (48.5601,  7.7551),   # Stade de la Meinau
    "Brest":                     (48.3890, -4.4618),   # Stade Francis-Le Blé
    "Angers":                    (47.4606, -0.5311),   # Stade Raymond Kopa
    "Lorient":                   (47.7482, -3.3680),   # Stade du Moustoir
    "St Etienne":                (45.4608,  4.3900),   # Stade Geoffroy-Guichard
    "Le Havre":                  (49.4979,  0.1619),   # Stade Océane
    "Clermont":                  (45.8000,  3.1167),   # Stade Gabriel-Montpied
    "Metz":                      (49.1099,  6.1603),   # Stade Saint-Symphorien
    "Auxerre":                   (47.7978,  3.5683),   # Stade de l'Abbé-Deschamps
    "Troyes":                    (48.2978,  4.0744),   # Stade de l'Aube
}

# ── Helpers ────────────────────────────────────────────────────────────────

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_PARAMS  = "temperature_2m_max,precipitation_sum,windspeed_10m_max,weathercode"
OUTPUT_COLUMNS = ["Date", "HomeTeam", "WeatherDesc", "TempMaxC", "PrecipMM", "WindKmh"]


def _get_coords(team: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a team, or None if not found."""
    return STADIUM_COORDS.get(team) or STADIUM_COORDS.get(team.split()[0])


def _weather_description(code: int) -> str:
    """Map WMO weather code → human-readable label."""
    if code == 0:
        return "Clear"
    if code in (1, 2, 3):
        return "Partly cloudy"
    if code in (45, 48):
        return "Foggy"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67):
        return "Rainy"
    if code in (71, 73, 75, 77):
        return "Snowy"
    if code in (80, 81, 82, 85, 86):
        return "Showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"


def fetch_fixture_weather(home_team: str, match_date: str) -> dict:
    """Fetch single-day forecast for a fixture. Returns a weather dict."""
    coords = _get_coords(home_team)
    if coords is None:
        return {
            "WeatherDesc": "N/A",
            "TempMaxC": None,
            "PrecipMM": None,
            "WindKmh": None,
        }

    lat, lon = coords
    params = {
        "latitude":         lat,
        "longitude":        lon,
        "daily":            DAILY_PARAMS,
        "timezone":         "Europe/Paris",
        "start_date":       match_date,
        "end_date":         match_date,
    }
    try:
        resp = request_with_retry(FORECAST_URL, params=params, timeout=10)
        data = resp.json().get("daily", {})
        code = data.get("weathercode", [None])[0]
        return {
            "WeatherDesc": _weather_description(int(code)) if code is not None else "N/A",
            "TempMaxC":    data.get("temperature_2m_max", [None])[0],
            "PrecipMM":    data.get("precipitation_sum", [None])[0],
            "WindKmh":     data.get("windspeed_10m_max", [None])[0],
        }
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ Weather fetch failed for {home_team} on {match_date}: {exc}")
        return {"WeatherDesc": "N/A", "TempMaxC": None, "PrecipMM": None, "WindKmh": None}


def fetch_all_weather(
    fixtures_path: str = "data_files/upcoming_fixtures.csv",
    out_path: str = "data_files/raw/match_weather.csv",
) -> None:
    """Fetch forecast weather for all upcoming fixtures and write CSV."""
    fixtures_p = Path(fixtures_path)
    if not fixtures_p.exists():
        print(f"✗ Fixtures file not found: {fixtures_path}")
        return

    df = pd.read_csv(fixtures_path)
    if df.empty:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(out_path, index=False)
        print(f"  No upcoming fixtures to fetch weather for. Cleared {out_path}")
        return

    date_col = next((c for c in ["Date", "MatchDate", "date"] if c in df.columns), None)
    home_col = next((c for c in ["HomeTeam", "home_team", "home"] if c in df.columns), None)
    if date_col is None or home_col is None:
        print("  ✗ Could not find Date/HomeTeam columns in fixtures.")
        return

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    print(f"  Fetching weather for {len(df)} fixtures…")

    for _, row in df.iterrows():
        match_date = str(row[date_col])[:10]          # YYYY-MM-DD
        home_team  = normalize_team_name(str(row[home_col]))
        weather    = fetch_fixture_weather(home_team, match_date)
        rows.append({
            "Date":      match_date,
            "HomeTeam":  home_team,
            **weather,
        })
        time.sleep(0.05)   # polite rate limiting (Open-Meteo allows 10k/day free)

    out_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    out_df.to_csv(out_path, index=False)
    print(f"  Saved {len(out_df)} rows → {out_path}")


if __name__ == "__main__":
    fetch_all_weather()
    print("Weather data fetch complete.")
