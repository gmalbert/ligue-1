"""Pre-generate and log predictions for all upcoming fixtures.

Called nightly by GitHub Actions and automation/nightly_pipeline.py
so the Streamlit app never has to run the model at request time.

Generates predictions from:
  1. Ensemble (VotingClassifier) → ModelVersion = "ensemble_v1"
  2. Neural Network (LaLigaNet, if available) → ModelVersion = "nn_v1"
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils import predict_for_upcoming, FEATURE_COLS  # noqa: E402
from track_predictions import log_predictions         # noqa: E402

HIST_PATH     = ROOT / "data_files" / "combined_historical_data.csv"
FIXTURES_PATH = ROOT / "data_files" / "upcoming_fixtures.csv"
MODEL_PATH    = ROOT / "models" / "ensemble_model.pkl"
NN_MODEL_PATH = ROOT / "models" / "nn_model.pt"
NN_SCALER_PATH= ROOT / "models" / "nn_scaler.pkl"
LOG_PATH      = ROOT / "data_files" / "predictions_log.csv"


def _preds_to_log_df(preds: pd.DataFrame) -> pd.DataFrame:
    """Rename predict_for_upcoming output to log schema."""
    log_df = preds.rename(columns={
        "Date":       "MatchDate",
        "Home Win %": "PredHomeWin",
        "Draw %":     "PredDraw",
        "Away Win %": "PredAwayWin",
    })[["MatchDate", "HomeTeam", "AwayTeam", "PredHomeWin", "PredDraw", "PredAwayWin"]].copy()

    def _pred_result(row: pd.Series) -> str:
        m = max(row["PredHomeWin"], row["PredDraw"], row["PredAwayWin"])
        if m == row["PredHomeWin"]:
            return "H"
        if m == row["PredDraw"]:
            return "D"
        return "A"

    log_df["PredictedResult"] = log_df.apply(_pred_result, axis=1)
    return log_df


def _clear_open_predictions() -> None:
    """Remove unresolved predictions before writing the latest fixture slate."""
    if not LOG_PATH.exists():
        return
    existing = pd.read_csv(LOG_PATH)
    if "ActualResult" not in existing.columns:
        return
    actual = existing["ActualResult"]
    keep = actual.notna() & actual.astype(str).str.strip().ne("")
    updated = existing[keep].copy()
    updated.to_csv(LOG_PATH, index=False)
    removed = len(existing) - len(updated)
    if removed:
        print(f"Cleared {removed} unresolved predictions from {LOG_PATH.relative_to(ROOT)}")


def main() -> None:
    for p, hint in [
        (HIST_PATH,     "run fetch_historical_csvs.py first"),
        (FIXTURES_PATH, "run fetch_upcoming_fixtures.py first"),
        (MODEL_PATH,    "run train_models.py first"),
    ]:
        if not Path(p).exists():
            print(f"✗ Missing {p} — {hint}")
            sys.exit(1)

    hist = pd.read_csv(HIST_PATH, low_memory=False)
    hist["MatchDate"] = pd.to_datetime(hist["MatchDate"], errors="coerce")

    fix = pd.read_csv(FIXTURES_PATH)
    _clear_open_predictions()
    if fix.empty:
        print("No upcoming fixtures to predict. Open predictions were cleared.")
        return

    # ── 1. Ensemble predictions ────────────────────────────────────────────
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    preds = predict_for_upcoming(fix, hist, model, FEATURE_COLS)
    if preds.empty:
        print("No upcoming fixtures to predict.")
        return

    log_df = _preds_to_log_df(preds)
    log_predictions(log_df, model_version="ensemble_v1")
    print(f"✓ Ensemble: {len(log_df)} predictions → data_files/predictions_log.csv")

    # ── 2. Neural network predictions (optional) ───────────────────────────
    try:
        from models.nn_predictor import TORCH_AVAILABLE, load_nn, predict_nn  # noqa: E402

        if TORCH_AVAILABLE and NN_MODEL_PATH.exists() and NN_SCALER_PATH.exists():
            from prepare_model_data import load_and_engineer_features  # noqa: E402

            nn_model, scaler = load_nn(str(NN_MODEL_PATH), str(NN_SCALER_PATH))
            if nn_model is not None:
                # Build feature matrix for upcoming fixtures
                df_hist_eng = load_and_engineer_features(hist)
                available = [c for c in FEATURE_COLS if c in df_hist_eng.columns]

                # Re-use the preds DataFrame which already has HomeTeam/AwayTeam
                # We just replace the probability columns with NN output
                nn_log = log_df.copy()

                # Build X from the same stats lookup used by predict_for_upcoming
                # (We re-use the rows returned by the ensemble run — same features)
                feat_cols_in_preds = [c for c in FEATURE_COLS if c in preds.columns]
                if feat_cols_in_preds:
                    X_nn = preds[feat_cols_in_preds].fillna(0).values
                    proba_nn = predict_nn(X_nn, nn_model, scaler)  # (n, 3) [A, D, H]
                    nn_log["PredAwayWin"] = (proba_nn[:, 0] * 100).round(1)
                    nn_log["PredDraw"]    = (proba_nn[:, 1] * 100).round(1)
                    nn_log["PredHomeWin"] = (proba_nn[:, 2] * 100).round(1)

                    def _pred_result_nn(row: pd.Series) -> str:
                        m = max(row["PredHomeWin"], row["PredDraw"], row["PredAwayWin"])
                        if m == row["PredHomeWin"]:
                            return "H"
                        if m == row["PredDraw"]:
                            return "D"
                        return "A"

                    nn_log["PredictedResult"] = nn_log.apply(_pred_result_nn, axis=1)
                    log_predictions(nn_log, model_version="nn_v1")
                    print(f"✓ Neural Net: {len(nn_log)} predictions → data_files/predictions_log.csv")
                else:
                    print("  ⚠ Feature columns not in preds — skipping NN prediction logging.")
        else:
            if not NN_MODEL_PATH.exists():
                print("  ℹ Neural network model not found — skipping NN predictions.")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ Neural network prediction skipped: {exc}")


if __name__ == "__main__":
    main()

