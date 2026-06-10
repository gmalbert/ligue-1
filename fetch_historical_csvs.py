"""Download historical Ligue-1 match data from football-data.co.uk.

Saves individual season CSVs to data_files/raw/FR1_XXXX.csv and a combined
file to data_files/combined_historical_data.csv.

Usage:
    python fetch_historical_csvs.py

Source: https://www.football-data.co.uk/french.php
Column reference: https://www.football-data.co.uk/notes.txt
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

from fetch_utils import request_with_retry

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Season codes for football-data.co.uk ────────────────────────────────────
# Format: {YYMM: "YYYY-YY"}  (e.g. "1516" → "2015-16")
SEASONS: dict[str, str] = {
    "1516": "2015-16",
    "1617": "2016-17",
    "1718": "2017-18",
    "1819": "2018-19",
    "1920": "2019-20",
    "2021": "2020-21",
    "2122": "2021-22",
    "2223": "2022-23",
    "2324": "2023-24",
    "2425": "2024-25",
    "2526": "2025-26",
}

# Ligue-1 uses FR1.csv (not SP1.csv which is La Liga)
BASE_URL = "https://www.football-data.co.uk/mmz4281/{code}/FR1.csv"

# Columns to keep (subset of the full CSV — keeps file sizes manageable)
COLUMN_MAP: dict[str, str] = {
    "Div":    "Div",
    "Date":   "MatchDate",
    "HomeTeam": "HomeTeam",
    "AwayTeam": "AwayTeam",
    "FTHG":   "FullTimeHomeGoals",
    "FTAG":   "FullTimeAwayGoals",
    "FTR":    "FullTimeResult",
    "HTHG":   "HalfTimeHomeGoals",
    "HTAG":   "HalfTimeAwayGoals",
    "HTR":    "HalfTimeResult",
    "Referee":"Referee",
    "HS":     "HomeShots",
    "AS":     "AwayShots",
    "HST":    "HomeShotsOnTarget",
    "AST":    "AwayShotsOnTarget",
    "HF":     "HomeFouls",
    "AF":     "AwayFouls",
    "HC":     "HomeCorners",
    "AC":     "AwayCorners",
    "HY":     "HomeYellowCards",
    "AY":     "AwayYellowCards",
    "HR":     "HomeRedCards",
    "AR":     "AwayRedCards",
    # Betting odds
    "B365H":  "Bet365_HomeWinOdds",
    "B365D":  "Bet365_DrawOdds",
    "B365A":  "Bet365_AwayWinOdds",
    "BWH":    "BW_HomeWinOdds",
    "BWD":    "BW_DrawOdds",
    "BWA":    "BW_AwayWinOdds",
    "PSH":    "Pinnacle_HomeWinOdds",
    "PSD":    "Pinnacle_DrawOdds",
    "PSA":    "Pinnacle_AwayWinOdds",
    # Closing odds, when football-data.co.uk provides them
    "B365CH": "Bet365_CloseHomeWinOdds",
    "B365CD": "Bet365_CloseDrawOdds",
    "B365CA": "Bet365_CloseAwayWinOdds",
    "PSCH":   "Pinnacle_CloseHomeWinOdds",
    "PSCD":   "Pinnacle_CloseDrawOdds",
    "PSCA":   "Pinnacle_CloseAwayWinOdds",
}


def download_season(season_code: str, season_label: str) -> pd.DataFrame:
    """Download a single Ligue-1 season CSV from football-data.co.uk."""
    url = BASE_URL.format(code=season_code)
    try:
        resp = request_with_retry(url)
        df = pd.read_csv(io.StringIO(resp.text), encoding="latin-1", on_bad_lines="skip")
        # Keep only columns we care about
        keep = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        df = df[list(keep.keys())].rename(columns=keep)
        df["Season"] = season_label
        df["MatchDate"] = pd.to_datetime(df["MatchDate"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        print(f"  ✗ {season_label}: {e}")
        return pd.DataFrame()


def build_historical_dataset() -> pd.DataFrame:
    """Download all Ligue-1 seasons and combine into one CSV."""
    Path("data_files/raw").mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    for code, label in SEASONS.items():
        print(f"Downloading {label} (FR1_{code}.csv)...")
        df = download_season(code, label)
        if not df.empty:
            df.to_csv(f"data_files/raw/FR1_{code}.csv", index=False)
            frames.append(df)
            print(f"  ✓ {len(df)} matches")

    if not frames:
        print("\n✗ No seasons downloaded. Check your internet connection.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("MatchDate").reset_index(drop=True)

    out_path = "data_files/combined_historical_data.csv"
    combined.to_csv(out_path, index=False)
    print(f"\n✓ Combined dataset: {len(combined)} matches across {len(frames)} seasons → {out_path}")
    return combined


if __name__ == "__main__":
    build_historical_dataset()
