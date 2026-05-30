"""Backtesting module for Ligue Odds.

Evaluates the ensemble model's historical prediction quality and simulated
flat-stake betting ROI using Bet365 odds from historical data.

Usage:
    python backtest.py [--csv path] [--output path]

Also importable:
    from backtest import backtest_model, BacktestResult
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, log_loss, recall_score

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Edge threshold: only place a simulated bet when the model's implied prob
# exceeds the market's implied prob by at least this margin.
EDGE_THRESHOLD = 0.05

# Flat stake per bet in arbitrary units (e.g. £10)
FLAT_STAKE = 10.0


def _last_full_season_split(df: pd.DataFrame, min_matches: int = 300) -> tuple[pd.DataFrame, str]:
    if "Season" not in df.columns:
        split_idx = max(1, int(len(df) * 0.8))
        return df.iloc[split_idx:].copy(), "chronological_last_20pct"
    season_counts = df.groupby("Season").size().sort_index()
    full_seasons = season_counts[season_counts >= min_matches]
    holdout_season = str((full_seasons if not full_seasons.empty else season_counts).index[-1])
    return df[df["Season"] == holdout_season].copy(), holdout_season


def _calibration_error(y_true: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    conf = np.max(proba, axis=1)
    pred = np.argmax(proba, axis=1)
    correct = (pred == y_true).astype(float)
    ece = 0.0
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if np.any(mask):
            ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return ece


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Container for backtest output metrics."""
    n_matches:        int
    n_bets_placed:    int
    accuracy:         float          # Model accuracy on historical sample
    brier_score:      float          # Lower is better (0 = perfect)
    roi_pct:          float          # Flat-stake ROI %
    profit_units:     float          # Net profit in stake units
    win_rate_bets:    float          # Win rate of bets actually placed
    market_accuracy:  float
    market_brier_score: float
    log_loss:         float
    market_log_loss:  float
    calibration_error: float
    draw_recall:      float
    f1_macro:         float
    market_accuracy_delta: float
    market_log_loss_delta: float
    closing_line_value_pct: float | None
    holdout_season:   str
    season_summary:   pd.DataFrame   # Per-season accuracy + ROI
    confusion_matrix: pd.DataFrame   # 3×3 H/D/A confusion

    def to_dict(self) -> dict:
        return {
            "n_matches":     self.n_matches,
            "n_bets_placed": self.n_bets_placed,
            "accuracy":      round(self.accuracy, 4),
            "brier_score":   round(self.brier_score, 4),
            "roi_pct":       round(self.roi_pct, 2),
            "profit_units":  round(self.profit_units, 2),
            "win_rate_bets": round(self.win_rate_bets, 4),
            "market_accuracy": round(self.market_accuracy, 4),
            "market_brier_score": round(self.market_brier_score, 4),
            "log_loss": round(self.log_loss, 4),
            "market_log_loss": round(self.market_log_loss, 4),
            "calibration_error": round(self.calibration_error, 4),
            "draw_recall": round(self.draw_recall, 4),
            "f1_macro": round(self.f1_macro, 4),
            "market_accuracy_delta": round(self.market_accuracy_delta, 4),
            "market_log_loss_delta": round(self.market_log_loss_delta, 4),
            "closing_line_value_pct": self.closing_line_value_pct,
            "holdout_season": self.holdout_season,
            "evaluation": "last_full_season_holdout",
        }


# ── Core Backtest ─────────────────────────────────────────────────────────

def backtest_model(
    csv_path: str = "data_files/combined_historical_data.csv",
    model_path: str = "models/ensemble_model.pkl",
) -> BacktestResult | None:
    """Run a full historical backtest.

    For each row in the historical CSV that has Bet365 odds:
    - Load the pre-engineered features
    - Run the trained ensemble to get [P(A), P(D), P(H)]
    - Compare implied probs vs. Bet365 odds → place bet when edge > EDGE_THRESHOLD
    - Track accuracy, Brier score, ROI

    Returns None if required files are missing.
    """
    import pickle
    from prepare_model_data import FEATURE_COLS, load_and_engineer_features

    for p in [csv_path, model_path]:
        if not Path(p).exists():
            print(f"✗ Required file missing: {p}")
            return None

    print(f"Loading historical data from {csv_path}…")
    df_raw = pd.read_csv(csv_path, low_memory=False)
    df = load_and_engineer_features(df_raw)

    RESULT_MAP  = {"A": 0, "D": 1, "H": 2}
    RESULT_RMAP = {0: "A", 1: "D", 2: "H"}

    df = df[df["FullTimeResult"].isin(RESULT_MAP)].copy()
    df["_y"] = df["FullTimeResult"].map(RESULT_MAP)

    # Keep only rows with Bet365 odds (needed for ROI calc)
    odds_cols = ["Bet365_HomeWinOdds", "Bet365_DrawOdds", "Bet365_AwayWinOdds"]
    odds_available = all(c in df.columns for c in odds_cols)

    df = df.sort_values("MatchDate").reset_index(drop=True)
    eval_df, holdout_season = _last_full_season_split(df)
    eval_df = eval_df.reset_index(drop=True)

    available_feats = [c for c in FEATURE_COLS if c in df.columns]
    X = eval_df[available_feats].fillna(0).values

    print(f"Loading model from {model_path}…")
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    proba = model.predict_proba(X)
    # Normalise to sum=1 per row
    proba = proba / proba.sum(axis=1, keepdims=True)
    y_pred = np.argmax(proba, axis=1)
    y_true = eval_df["_y"].values

    # ── Accuracy ──────────────────────────────────────────────────────────
    accuracy = float((y_pred == y_true).mean())

    # ── Brier Score (multi-class) ─────────────────────────────────────────
    n = len(y_true)
    one_hot = np.zeros((n, 3))
    one_hot[np.arange(n), y_true] = 1
    brier = float(np.mean(np.sum((proba - one_hot) ** 2, axis=1)))
    market_proba = eval_df[["ImpliedProb_AwayWin", "ImpliedProb_Draw", "ImpliedProb_HomeWin"]].fillna(
        {"ImpliedProb_AwayWin": 0.28, "ImpliedProb_Draw": 0.27, "ImpliedProb_HomeWin": 0.45}
    ).values
    market_proba = np.clip(market_proba.astype(float), 1e-6, 1.0)
    market_proba = market_proba / market_proba.sum(axis=1, keepdims=True)
    market_pred = np.argmax(market_proba, axis=1)
    market_accuracy = float((market_pred == y_true).mean())
    market_brier = float(np.mean(np.sum((market_proba - one_hot) ** 2, axis=1)))
    model_log_loss = float(log_loss(y_true, proba))
    market_log_loss = float(log_loss(y_true, market_proba))
    calibration_error = _calibration_error(y_true, proba)
    draw_recall = float(recall_score(y_true, y_pred, labels=[1], average="macro", zero_division=0))
    f1_macro = float(f1_score(y_true, y_pred, average="macro"))

    # ── ROI Simulation ────────────────────────────────────────────────────
    bets_placed  = 0
    bets_won     = 0
    total_staked = 0.0
    total_return = 0.0
    clv_values: list[float] = []

    if odds_available:
        df_odds = eval_df.copy()
        # Implied probs from Bet365 (columns already renamed in historical CSV)
        for c in odds_cols:
            df_odds[c] = pd.to_numeric(df_odds[c], errors="coerce")

        df_odds = df_odds.dropna(subset=odds_cols)
        df_odds = df_odds[odds_cols + ["_y"]].reset_index(drop=True)

        # Re-slice proba to only matched rows
        odds_idx = df[df.index.isin(df_odds.index) if not df_odds.empty else df.index].index
        # Use positional alignment: iterate with shared index
        sub_df   = eval_df.copy().reset_index(drop=True)
        sub_prob = proba.copy()

        for i, (row_idx, row) in enumerate(sub_df.iterrows()):
            if not all(pd.notna(row.get(c)) for c in odds_cols):
                continue
            try:
                home_odds  = float(row["Bet365_HomeWinOdds"])
                draw_odds  = float(row["Bet365_DrawOdds"])
                away_odds  = float(row["Bet365_AwayWinOdds"])
            except (KeyError, ValueError, TypeError):
                continue

            if home_odds <= 1 or draw_odds <= 1 or away_odds <= 1:
                continue

            mkt_implied = np.array([
                1 / away_odds,
                1 / draw_odds,
                1 / home_odds,
            ])  # order: [A, D, H]

            model_prob = sub_prob[i]
            edges = model_prob - mkt_implied / mkt_implied.sum()  # normalise market

            best_idx = int(np.argmax(edges))
            if edges[best_idx] < EDGE_THRESHOLD:
                continue

            # Place flat-stake bet on best_idx outcome
            bet_odds = [away_odds, draw_odds, home_odds][best_idx]
            actual   = int(row["_y"])

            bets_placed  += 1
            total_staked += FLAT_STAKE
            if actual == best_idx:
                bets_won     += 1
                total_return += FLAT_STAKE * bet_odds

            closing_sets = [
                ["Bet365_CloseAwayWinOdds", "Bet365_CloseDrawOdds", "Bet365_CloseHomeWinOdds"],
                ["Pinnacle_CloseAwayWinOdds", "Pinnacle_CloseDrawOdds", "Pinnacle_CloseHomeWinOdds"],
            ]
            closing_cols = next((cols for cols in closing_sets if all(c in row.index for c in cols)), None)
            if closing_cols is not None:
                try:
                    close_odds = float(row[closing_cols[best_idx]])
                    if close_odds > 1:
                        clv_values.append((bet_odds / close_odds) - 1)
                except (TypeError, ValueError):
                    pass

    roi_pct      = ((total_return - total_staked) / total_staked * 100) if total_staked > 0 else 0.0
    profit_units = (total_return - total_staked) / FLAT_STAKE if FLAT_STAKE > 0 else 0.0
    win_rate     = bets_won / bets_placed if bets_placed > 0 else 0.0
    clv_pct = round(float(np.mean(clv_values) * 100), 2) if clv_values else None

    # ── Per-Season Summary ────────────────────────────────────────────────
    season_rows: list[dict] = []
    if "Season" in df.columns:
        for season, grp in eval_df.groupby("Season"):
            grp_idx   = grp.reset_index(drop=True).index
            g_proba   = proba[grp.index.values] if len(proba) > max(grp.index.values) else proba
            g_true    = grp["_y"].values
            g_pred    = np.argmax(g_proba, axis=1)
            season_rows.append({
                "Season":   season,
                "Matches":  len(grp),
                "Accuracy": round(float((g_pred == g_true).mean()), 3),
            })
    season_df = pd.DataFrame(season_rows) if season_rows else pd.DataFrame(
        columns=["Season", "Matches", "Accuracy"]
    )

    # ── Confusion Matrix ──────────────────────────────────────────────────
    labels = ["Away", "Draw", "Home"]
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    cm_df = pd.DataFrame(cm, index=[f"Actual {l}" for l in labels],
                         columns=[f"Pred {l}" for l in labels])

    result = BacktestResult(
        n_matches        = int(n),
        n_bets_placed    = int(bets_placed),
        accuracy         = accuracy,
        brier_score      = brier,
        roi_pct          = roi_pct,
        profit_units     = profit_units,
        win_rate_bets    = win_rate,
        market_accuracy  = market_accuracy,
        market_brier_score = market_brier,
        log_loss         = model_log_loss,
        market_log_loss  = market_log_loss,
        calibration_error = calibration_error,
        draw_recall      = draw_recall,
        f1_macro         = f1_macro,
        market_accuracy_delta = accuracy - market_accuracy,
        market_log_loss_delta = market_log_loss - model_log_loss,
        closing_line_value_pct = clv_pct,
        holdout_season   = holdout_season,
        season_summary   = season_df,
        confusion_matrix = cm_df,
    )

    print(
        f"\n  Backtest Results ({holdout_season}, {n} matches)\n"
        f"  {'─'*40}\n"
        f"  Accuracy:        {accuracy:.1%}\n"
        f"  Market Accuracy: {market_accuracy:.1%}\n"
        f"  Brier Score:     {brier:.4f}\n"
        f"  Market Brier:    {market_brier:.4f}\n"
        f"  Calibration ECE: {calibration_error:.4f}\n"
        f"  Draw Recall:     {draw_recall:.1%}\n"
        f"  Bets Placed:     {bets_placed}\n"
        f"  Bet Win Rate:    {win_rate:.1%}\n"
        f"  Flat-Stake ROI:  {roi_pct:+.1f}%  ({profit_units:+.1f} units)\n"
        f"  CLV:             {'N/A' if clv_pct is None else f'{clv_pct:+.2f}%'}\n"
    )
    return result


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Ligue Odds ensemble model")
    parser.add_argument("--csv",    default="data_files/combined_historical_data.csv")
    parser.add_argument("--model",  default="models/ensemble_model.pkl")
    parser.add_argument("--output", default="models/backtest_results.json",
                        help="Optional JSON output path")
    args = parser.parse_args()

    result = backtest_model(args.csv, args.model)
    if result is None:
        raise SystemExit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
