"""Nightly pipeline orchestrator for Ligue-1 Odds.

Runs all fetch, feature engineering, model training, and prediction
pre-generation steps in order. Can be run locally or invoked from
GitHub Actions.

Usage:
    python automation/nightly_pipeline.py
    python automation/nightly_pipeline.py --skip-odds   # spare odds API quota
    python automation/nightly_pipeline.py --skip-api-football
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Run from repo root regardless of where the script is called from
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


STEPS: list[tuple[str, list[str], bool, bool]] = [
    # (label, command, requires_odds_api, requires_api_football)
    ("Fetch historical CSVs",       ["python", "fetch_historical_csvs.py"],   False, False),
    ("Fetch upcoming fixtures",     ["python", "fetch_upcoming_fixtures.py"], False, False),
    ("Fetch xG proxy",              ["python", "fetch_fbref_xg.py"],          False, False),
    ("Fetch Coupe de France",       ["python", "fetch_copa_fixtures.py"],     False, False),
    ("Fetch bookmaker odds",        ["python", "fetch_odds.py"],              True,  False),
    ("Fetch market odds snapshots", ["python", "fetch_market_odds.py"],       True,  False),
    ("Fetch API-Football xG/stats", ["python", "fetch_xg_data.py"],           False, True),
    ("Fetch injuries and lineups",  ["python", "fetch_lineups_injuries.py"],  False, True),
    ("Fetch squad strength",        ["python", "fetch_squad_strength.py"],    False, True),
    ("Fetch weather forecasts",     ["python", "fetch_weather_data.py"],      False, False),
    ("Prepare model features",      ["python", "prepare_model_data.py"],      False, False),
    ("Build enriched feature store", ["python", "build_enriched_features.py"], False, False),
    ("Train models",                ["python", "train_models.py"],            False, False),
    ("Run historical backtest",     ["python", "backtest.py"],                False, False),
    ("Pre-generate predictions",    ["python", "automation/generate_predictions.py"], False, False),
    ("Validate prediction log",     ["python", "track_predictions.py", "--validate"], False, False),
    ("Precompute app cache",        ["python", "automation/precompute_app_cache.py"], False, False),
]


def run_pipeline(skip_odds: bool = False, skip_api_football: bool = False) -> None:
    print(f"\n{'='*60}")
    print("Ligue-1 Odds — Nightly Pipeline")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if skip_odds:
        print("⚠ Odds fetch skipped (--skip-odds)")
    if skip_api_football:
        print("⚠ API-Football enrichment skipped (--skip-api-football)")
    print(f"{'='*60}\n")

    failed: list[str] = []
    for label, cmd, needs_odds, needs_api_football in STEPS:
        if skip_odds and needs_odds:
            print(f"⏭  {label} (skipped)\n")
            continue
        if skip_api_football and needs_api_football:
            print(f"⏭  {label} (skipped)\n")
            continue

        print(f"▶  {label}...")
        result = subprocess.run(cmd, capture_output=False, text=True, cwd=ROOT)
        if result.returncode == 0:
            print(f"   ✓ Done\n")
        else:
            print(f"   ✗ FAILED (exit {result.returncode})\n")
            failed.append(label)

    print(f"{'='*60}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if failed:
        print(f"Failed steps: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All steps completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ligue-1 nightly data pipeline")
    parser.add_argument(
        "--skip-odds",
        action="store_true",
        help="Skip fetch_odds.py to preserve odds API quota",
    )
    parser.add_argument(
        "--skip-api-football",
        action="store_true",
        help="Skip API-Football enrichment to preserve the daily 100 request quota",
    )
    args = parser.parse_args()
    run_pipeline(skip_odds=args.skip_odds, skip_api_football=args.skip_api_football)
