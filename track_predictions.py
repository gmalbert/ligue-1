"""Prediction logger and validator for Ligue Odds.

Responsibilities:
  1. Log new predictions to data_files/predictions_log.csv
  2. Enrich logged predictions with actual results once matches finish
  3. Report rolling accuracy (--validate mode)

Usage:
    python track_predictions.py                # log today's predictions
    python track_predictions.py --validate     # match actuals + print accuracy
    python track_predictions.py --validate --csv path/to/historical.csv

Called nightly by .github/workflows/nightly.yml after train_models.py.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

LOG_PATH  = "data_files/predictions_log.csv"
HIST_PATH = "data_files/combined_historical_data.csv"

LOG_COLUMNS = [
    "LoggedAt",
    "MatchDate",
    "HomeTeam",
    "AwayTeam",
    "PredHomeWin",
    "PredDraw",
    "PredAwayWin",
    "PredictedResult",
    "ActualResult",
    "Correct",
    "ModelVersion",
]


# ── Logging ───────────────────────────────────────────────────────────────

def log_predictions(predictions_df: pd.DataFrame, model_version: str = "ensemble_v1") -> None:
    """
    Append a batch of predictions to the log.

    predictions_df must have columns:
        MatchDate, HomeTeam, AwayTeam,
        PredHomeWin, PredDraw, PredAwayWin, PredictedResult
    """
    if predictions_df.empty:
        return

    df = predictions_df.copy()
    df["LoggedAt"]     = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    df["ActualResult"] = np.nan
    df["Correct"]      = np.nan
    df["ModelVersion"] = model_version

    # Ensure all LOG_COLUMNS exist
    for col in LOG_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df = df[LOG_COLUMNS]

    log_path = Path(LOG_PATH)
    if log_path.exists():
        existing = pd.read_csv(log_path)
        # Deduplicate per model version so ensemble and NN rows can coexist.
        existing_keys = set(
            zip(
                existing["MatchDate"].astype(str),
                existing["HomeTeam"].astype(str),
                existing["AwayTeam"].astype(str),
                existing["ModelVersion"].astype(str),
            )
        )
        new_rows = df[
            ~df.apply(
                lambda r: (
                    str(r["MatchDate"]),
                    str(r["HomeTeam"]),
                    str(r["AwayTeam"]),
                    str(r["ModelVersion"]),
                )
                in existing_keys,
                axis=1,
            )
        ]
        if new_rows.empty:
            print("  No new predictions to log (all already in log).")
            return
        updated = pd.concat([existing, new_rows], ignore_index=True)
    else:
        updated = df

    Path("data_files").mkdir(parents=True, exist_ok=True)
    updated.to_csv(LOG_PATH, index=False)
    n = len(updated) - (len(existing) if "existing" in dir() else 0)
    print(f"  ✓ Logged {n} new predictions → {LOG_PATH}")


# ── Validation ────────────────────────────────────────────────────────────

def _load_actuals(hist_path: str) -> pd.DataFrame:
    """Load finished match results from the historical CSV."""
    if not Path(hist_path).exists():
        return pd.DataFrame()
    df = pd.read_csv(hist_path, low_memory=False)
    # Normalise column names
    rename = {"Date": "MatchDate", "FTR": "FullTimeResult"}
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)
    df["MatchDate"] = pd.to_datetime(df.get("MatchDate"), errors="coerce").dt.strftime("%Y-%m-%d")
    return df[["MatchDate", "HomeTeam", "AwayTeam", "FullTimeResult"]].dropna()


def enrich_with_actuals(log_df: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """
    Join logged predictions to actual results.
    Fills ActualResult and Correct (1/0) for rows where the match has finished.
    """
    if actuals.empty or log_df.empty:
        return log_df

    log_df = log_df.copy()
    log_df["MatchDate"] = pd.to_datetime(log_df["MatchDate"], errors="coerce").dt.strftime("%Y-%m-%d")

    lookup = actuals.set_index(["MatchDate", "HomeTeam", "AwayTeam"])["FullTimeResult"].to_dict()

    for idx, row in log_df.iterrows():
        key = (str(row["MatchDate"]), str(row["HomeTeam"]), str(row["AwayTeam"]))
        actual = lookup.get(key)
        if actual:
            log_df.at[idx, "ActualResult"] = actual
            log_df.at[idx, "Correct"] = int(str(row["PredictedResult"]) == str(actual))

    return log_df


def print_validation_report(log_df: pd.DataFrame) -> None:
    """Print a summary of prediction accuracy to stdout."""
    resolved = log_df[log_df["Correct"].notna()].copy()
    if resolved.empty:
        print("  No resolved predictions to validate yet.")
        return

    total   = len(resolved)
    correct = int(resolved["Correct"].sum())
    acc     = correct / total

    print(f"\n{'='*50}")
    print("  Ligue Odds — Prediction Accuracy Report")
    print(f"{'='*50}")
    print(f"  Total resolved:  {total}")
    print(f"  Correct:         {correct}  ({acc:.1%})")
    print(f"  Incorrect:       {total - correct}")

    # Per-outcome breakdown
    for outcome in ["H", "D", "A"]:
        label = {"H": "Home Win", "D": "Draw", "A": "Away Win"}[outcome]
        subset = resolved[resolved["PredictedResult"] == outcome]
        if len(subset) == 0:
            continue
        o_acc = subset["Correct"].mean()
        print(f"  {label:12s}:  {len(subset):4d} predictions  |  {o_acc:.1%} accuracy")

    # Recent form (last 30 days)
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent = resolved[resolved["MatchDate"] >= cutoff]
    if len(recent) >= 5:
        r_acc = recent["Correct"].mean()
        print(f"\n  Last 30 days:    {len(recent)} matches  |  {r_acc:.1%} accuracy")

    print(f"{'='*50}\n")


# ── Main ──────────────────────────────────────────────────────────────────

def validate(hist_path: str = HIST_PATH) -> None:
    """Enrich log with actuals and print accuracy report."""
    log_path = Path(LOG_PATH)
    if not log_path.exists():
        print(f"  No prediction log found at {LOG_PATH}. Nothing to validate.")
        return

    log_df  = pd.read_csv(LOG_PATH)
    actuals = _load_actuals(hist_path)

    print(f"  Matching {len(log_df)} logged predictions against {len(actuals)} known results…")
    log_df = enrich_with_actuals(log_df, actuals)
    log_df.to_csv(LOG_PATH, index=False)
    print(f"  ✓ Updated log saved → {LOG_PATH}")

    print_validation_report(log_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track and validate Ligue 1 predictions")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Enrich log with actual results and print accuracy report",
    )
    parser.add_argument(
        "--csv",
        default=HIST_PATH,
        help="Path to combined historical data CSV (used for actuals lookup)",
    )
    args = parser.parse_args()

    if args.validate:
        validate(args.csv)
    else:
        print(
            "track_predictions.py\n"
            "  --validate   Enrich prediction log with actual results + print accuracy\n"
            "\nTo log predictions programmatically, import log_predictions() from this module."
        )
