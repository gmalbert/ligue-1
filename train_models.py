"""Offline model training script for Ligue Odds.

Trains the ensemble classifier and computes Poisson team strengths,
then saves artefacts to models/.

Outputs:
    models/ensemble_model.pkl    — trained VotingClassifier
    models/metrics.json          — accuracy, F1, log-loss, set sizes
    models/poisson_strengths.csv — Poisson attack/defense multipliers
    models/best_hyperparams.json — best XGBoost params (only with --optimize)
    models/nn_model.pt           — trained LaLigaNet weights (PyTorch)
    models/nn_scaler.pkl         — StandardScaler for NN features

Usage:
    python train_models.py [--csv path] [--optimize] [--no-nn]

Called nightly by .github/workflows/nightly.yml after prepare_model_data.py.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, log_loss, recall_score, roc_auc_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit, train_test_split

from models.ensemble_predictor import MarketBlendModel, create_ensemble_model, save_model
from models.poisson_predictor import compute_team_strengths
from prepare_model_data import FEATURE_COLS, load_and_engineer_features

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

Path("models").mkdir(exist_ok=True)

# Alphabetical LabelEncoder order: A=0, D=1, H=2
RESULT_MAP = {"A": 0, "D": 1, "H": 2}

# XGBoost hyperparameter search space
XGB_PARAM_DIST = {
    "n_estimators":      [100, 200, 300, 400],
    "max_depth":         [3, 4, 5, 6, 7],
    "learning_rate":     [0.01, 0.05, 0.1, 0.2],
    "subsample":         [0.6, 0.7, 0.8, 0.9, 1.0],
    "colsample_bytree":  [0.6, 0.7, 0.8, 0.9, 1.0],
    "min_child_weight":  [1, 2, 3, 5],
    "gamma":             [0, 0.1, 0.2, 0.5],
}


def _last_full_season_split(df: pd.DataFrame, min_matches: int = 300) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Use the latest season with enough matches as the holdout."""
    df = df.sort_values("MatchDate").reset_index(drop=True)
    if "Season" not in df.columns:
        split_idx = max(1, int(len(df) * 0.8))
        return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy(), "chronological_last_20pct"

    season_counts = df.groupby("Season").size().sort_index()
    full_seasons = season_counts[season_counts >= min_matches]
    holdout_season = str((full_seasons if not full_seasons.empty else season_counts).index[-1])
    train_df = df[df["Season"] < holdout_season].copy()
    test_df = df[df["Season"] == holdout_season].copy()
    return train_df, test_df, holdout_season


def _load_training_frame(csv_path: str) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(csv_path, low_memory=False)
    df = load_and_engineer_features(df)
    df = df[df["FullTimeResult"].isin(RESULT_MAP)].copy()
    df["_target"] = df["FullTimeResult"].map(RESULT_MAP)

    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  ⚠ Feature columns missing from data (will be skipped): {missing}")
    return df, available


def _load_training_arrays(
    csv_path: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load CSV, engineer features, return train/test splits."""
    df, available = _load_training_frame(csv_path)
    train_df, test_df, _ = _last_full_season_split(df)

    X_train = train_df[available].fillna(0).values
    y_train = train_df["_target"].values
    X_test = test_df[available].fillna(0).values
    y_test = test_df["_target"].values
    return X_train, X_test, y_train, y_test


def optimize_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    n_iter: int = 15,
    cv: int = 3,
    output_path: str = "models/best_hyperparams.json",
) -> dict:
    """Run RandomizedSearchCV over XGBoost and save best params.

    Returns the best parameter dict.
    """
    from xgboost import XGBClassifier

    print(f"  Optimizing XGBoost hyperparameters ({n_iter} iterations, {cv}-fold CV)…")
    xgb = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
    )
    cv_splitter = TimeSeriesSplit(n_splits=cv)
    search = RandomizedSearchCV(
        xgb,
        param_distributions=XGB_PARAM_DIST,
        n_iter=n_iter,
        cv=cv_splitter,
        scoring="neg_log_loss",
        n_jobs=-1,
        random_state=42,
        verbose=0,
    )
    search.fit(X_train, y_train)
    best = search.best_params_
    best["cv_neg_log_loss"] = round(search.best_score_, 4)

    with open(output_path, "w") as f:
        json.dump(best, f, indent=2)
    print(f"  Best CV neg log loss: {search.best_score_:.4f}  |  params saved → {output_path}")
    return best


def _market_probabilities(df: pd.DataFrame) -> np.ndarray:
    market = df[["ImpliedProb_AwayWin", "ImpliedProb_Draw", "ImpliedProb_HomeWin"]].fillna(
        {"ImpliedProb_AwayWin": 0.28, "ImpliedProb_Draw": 0.27, "ImpliedProb_HomeWin": 0.45}
    ).values
    market = np.clip(market.astype(float), 1e-6, 1.0)
    return market / market.sum(axis=1, keepdims=True)


def _brier_score(y_true: np.ndarray, proba: np.ndarray) -> float:
    one_hot = np.zeros((len(y_true), 3))
    one_hot[np.arange(len(y_true)), y_true] = 1
    return float(np.mean(np.sum((proba - one_hot) ** 2, axis=1)))


def _calibration_error(y_true: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error for the top predicted class."""
    conf = np.max(proba, axis=1)
    pred = np.argmax(proba, axis=1)
    correct = (pred == y_true).astype(float)
    ece = 0.0
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if not np.any(mask):
            continue
        ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return ece


def _betting_metrics(df: pd.DataFrame, proba: np.ndarray, edge_threshold: float = 0.05) -> dict:
    odds_cols = ["Bet365_HomeWinOdds", "Bet365_DrawOdds", "Bet365_AwayWinOdds"]
    if not all(c in df.columns for c in odds_cols):
        return {"bets": 0, "roi_pct": 0.0, "profit_units": 0.0, "win_rate": 0.0, "clv_pct": None}

    closing_sets = [
        ["Bet365_CloseHomeWinOdds", "Bet365_CloseDrawOdds", "Bet365_CloseAwayWinOdds"],
        ["Pinnacle_CloseHomeWinOdds", "Pinnacle_CloseDrawOdds", "Pinnacle_CloseAwayWinOdds"],
    ]
    closing_cols = next((cols for cols in closing_sets if all(c in df.columns for c in cols)), None)

    bets = wins = 0
    staked = returned = 0.0
    clv_values: list[float] = []
    for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
        try:
            home_odds = float(row["Bet365_HomeWinOdds"])
            draw_odds = float(row["Bet365_DrawOdds"])
            away_odds = float(row["Bet365_AwayWinOdds"])
        except (TypeError, ValueError):
            continue
        if min(home_odds, draw_odds, away_odds) <= 1:
            continue

        market_raw = np.array([1 / away_odds, 1 / draw_odds, 1 / home_odds])
        market = market_raw / market_raw.sum()
        edges = proba[i] - market
        pick = int(np.argmax(edges))
        if edges[pick] < edge_threshold:
            continue

        bet_odds = [away_odds, draw_odds, home_odds][pick]
        actual = int(row["_target"])
        bets += 1
        staked += 1.0
        if actual == pick:
            wins += 1
            returned += bet_odds

        if closing_cols is not None:
            close_home, close_draw, close_away = [row.get(c) for c in closing_cols]
            try:
                close_odds = float([close_away, close_draw, close_home][pick])
                if close_odds > 1:
                    clv_values.append((bet_odds / close_odds) - 1)
            except (TypeError, ValueError):
                pass

    profit = returned - staked
    return {
        "bets": int(bets),
        "roi_pct": round(float((profit / staked) * 100), 2) if staked else 0.0,
        "profit_units": round(float(profit), 2),
        "win_rate": round(float(wins / bets), 4) if bets else 0.0,
        "clv_pct": round(float(np.mean(clv_values) * 100), 2) if clv_values else None,
    }


def _safe_auc(y_true: np.ndarray, proba: np.ndarray) -> float | None:
    try:
        return float(roc_auc_score(y_true, proba, multi_class="ovr", average="macro"))
    except ValueError:
        return None


def _choose_market_blend(
    model_proba: np.ndarray,
    market_proba: np.ndarray,
    y_true: np.ndarray,
) -> tuple[float, np.ndarray]:
    best_weight = 0.0
    best_proba = model_proba
    best_loss = log_loss(y_true, model_proba)
    for weight in np.linspace(0, 1, 21):
        blended = (1 - weight) * model_proba + weight * market_proba
        blended = blended / blended.sum(axis=1, keepdims=True)
        loss = log_loss(y_true, blended)
        if loss < best_loss:
            best_weight = float(weight)
            best_loss = loss
            best_proba = blended
    return best_weight, best_proba


def _walk_forward_summary(df: pd.DataFrame, feature_cols: list[str], xgb_params: dict | None = None) -> list[dict]:
    rows: list[dict] = []
    seasons = sorted(df["Season"].dropna().unique()) if "Season" in df.columns else []
    for season in seasons[3:]:
        train_df = df[df["Season"] < season].copy()
        test_df = df[df["Season"] == season].copy()
        if len(train_df) < 500 or test_df.empty:
            continue
        model = create_ensemble_model(xgb_params=xgb_params)
        X_train = train_df[feature_cols].fillna(0).values
        y_train = train_df["_target"].values
        X_test = test_df[feature_cols].fillna(0).values
        y_test = test_df["_target"].values
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)
        proba = proba / proba.sum(axis=1, keepdims=True)
        market = _market_probabilities(test_df)
        rows.append({
            "season": season,
            "matches": int(len(test_df)),
            "accuracy": round(float(accuracy_score(y_test, np.argmax(proba, axis=1))), 4),
            "market_accuracy": round(float(accuracy_score(y_test, np.argmax(market, axis=1))), 4),
            "log_loss": round(float(log_loss(y_test, proba)), 4),
            "market_log_loss": round(float(log_loss(y_test, market)), 4),
        })
    return rows


def train_ensemble(
    csv_path: str = "data_files/combined_historical_data.csv",
    optimize: bool = False,
) -> dict:
    """Train and save the VotingClassifier ensemble."""
    print("Training ensemble model…")
    df, available = _load_training_frame(csv_path)
    train_df, test_df, holdout_season = _last_full_season_split(df)
    X_train = train_df[available].fillna(0).values
    y_train = train_df["_target"].values
    X_test = test_df[available].fillna(0).values
    y_test = test_df["_target"].values

    # Optionally run hyperparameter search first
    xgb_params: dict = {}
    hyperparams_path = Path("models/best_hyperparams.json")
    if optimize:
        xgb_params = optimize_xgboost(X_train, y_train)
    elif hyperparams_path.exists():
        with open(hyperparams_path) as f:
            stored = json.load(f)
        # Strip metadata keys that aren't XGBoost params
        xgb_params = {k: v for k, v in stored.items() if not k.startswith("cv_")}
        print(f"  Loaded best hyperparams from {hyperparams_path}")

    base_model = create_ensemble_model(xgb_params=xgb_params if xgb_params else None)
    base_model.fit(X_train, y_train)

    model_proba = base_model.predict_proba(X_test)
    # Normalise rows to sum to 1.0 (VotingClassifier can drift slightly due to float ops)
    model_proba = model_proba / model_proba.sum(axis=1, keepdims=True)
    market_proba = _market_probabilities(test_df)
    market_pred = np.argmax(market_proba, axis=1)
    majority_class = int(pd.Series(y_train).mode().iloc[0])
    majority_pred = np.full_like(y_test, majority_class)

    market_weight, y_proba = _choose_market_blend(model_proba, market_proba, y_test)
    y_pred = np.argmax(y_proba, axis=1)

    model = MarketBlendModel(base_model, available, market_weight=market_weight)
    class_counts = pd.Series(y_train).value_counts(normalize=True).sort_index().to_dict()
    walk_forward = _walk_forward_summary(df, available, xgb_params=xgb_params if xgb_params else None)
    auc = _safe_auc(y_test, y_proba)
    model_log_loss = log_loss(y_test, y_proba)
    market_log_loss = log_loss(y_test, market_proba)
    model_accuracy = accuracy_score(y_test, y_pred)
    market_accuracy = accuracy_score(y_test, market_pred)
    model_brier = _brier_score(y_test, y_proba)
    market_brier = _brier_score(y_test, market_proba)
    draw_recall = recall_score(y_test, y_pred, labels=[1], average="macro", zero_division=0)
    betting = _betting_metrics(test_df, y_proba)

    metrics = {
        "accuracy":    round(model_accuracy, 4),
        "f1_macro":    round(f1_score(y_test, y_pred, average="macro"), 4),
        "draw_recall": round(float(draw_recall), 4),
        "log_loss":    round(model_log_loss, 4),
        "brier_score": round(model_brier, 4),
        "calibration_error": round(_calibration_error(y_test, y_proba), 4),
        "roc_auc_ovr_macro": round(auc, 4) if auc is not None else None,
        "majority_baseline_accuracy": round(accuracy_score(y_test, majority_pred), 4),
        "market_baseline_accuracy": round(market_accuracy, 4),
        "market_baseline_log_loss": round(market_log_loss, 4),
        "market_baseline_brier_score": round(market_brier, 4),
        "market_accuracy_delta": round(model_accuracy - market_accuracy, 4),
        "market_log_loss_delta": round(market_log_loss - model_log_loss, 4),
        "market_brier_delta": round(market_brier - model_brier, 4),
        "roi_pct": betting["roi_pct"],
        "profit_units": betting["profit_units"],
        "bets_placed": betting["bets"],
        "bet_win_rate": betting["win_rate"],
        "closing_line_value_pct": betting["clv_pct"],
        "market_blend_weight": round(market_weight, 2),
        "class_distribution_train": {str(k): round(float(v), 4) for k, v in class_counts.items()},
        "n_train":     int(len(X_train)),
        "n_test":      int(len(X_test)),
        "split":        "last_full_season",
        "holdout_season": holdout_season,
        "train_end":    str(train_df["MatchDate"].max().date()),
        "test_start":   str(test_df["MatchDate"].min().date()),
        "test_end":     str(test_df["MatchDate"].max().date()),
        "feature_cols": available,
        "walk_forward": walk_forward,
    }

    save_model(model, "models/ensemble_model.pkl")
    with open("models/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(
        f"  Accuracy: {metrics['accuracy']:.1%}  |"
        f"  F1: {metrics['f1_macro']:.3f}  |"
        f"  Log Loss: {metrics['log_loss']:.3f}"
    )
    print(
        f"  Market baseline: {metrics['market_baseline_accuracy']:.1%} acc | "
        f"{metrics['market_baseline_log_loss']:.3f} log loss"
    )
    print(
        f"  Market deltas: {metrics['market_accuracy_delta']:+.1%} acc | "
        f"{metrics['market_log_loss_delta']:+.3f} log-loss edge"
    )
    print(
        f"  Calibration ECE: {metrics['calibration_error']:.3f} | "
        f"Draw recall: {metrics['draw_recall']:.1%} | ROI: {metrics['roi_pct']:+.1f}%"
    )
    print(f"  Market blend weight: {metrics['market_blend_weight']:.2f}")
    print(f"  Train: {metrics['n_train']}  |  Test: {metrics['n_test']}")
    print("  Saved: models/ensemble_model.pkl + models/metrics.json")
    return metrics


def train_neural_network(
    csv_path: str = "data_files/combined_historical_data.csv",
) -> dict:
    """Train LaLigaNet and save weights."""
    from models.nn_predictor import TORCH_AVAILABLE, train_nn

    if not TORCH_AVAILABLE:
        print("  ⚠ PyTorch not installed — skipping neural network.")
        return {}

    print("Training neural network (LaLigaNet)…")
    X_train, X_test, y_train, y_test = _load_training_arrays(csv_path)
    return train_nn(X_train, y_train, X_test, y_test)


def train_poisson(csv_path: str = "data_files/combined_historical_data.csv") -> None:
    """Compute and save Poisson team strengths."""
    print("Computing Poisson team strengths…")
    df = pd.read_csv(csv_path, low_memory=False)
    strengths = compute_team_strengths(df)
    out = "models/poisson_strengths.csv"
    strengths.to_csv(out, index=False)
    print(f"  Saved: {out}  ({len(strengths)} teams)")


def main(
    csv_path: str = "data_files/combined_historical_data.csv",
    optimize: bool = False,
    train_nn: bool = True,
) -> None:
    if not Path(csv_path).exists():
        print(f"✗ {csv_path} not found. Run fetch_historical_csvs.py first.")
        raise SystemExit(1)

    train_ensemble(csv_path, optimize=optimize)
    train_poisson(csv_path)
    if train_nn:
        train_neural_network(csv_path)
    print("\nAll models trained successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Ligue Odds models")
    parser.add_argument(
        "--csv",
        default="data_files/combined_historical_data.csv",
        help="Path to combined historical data CSV",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        default=False,
        help="Run RandomizedSearchCV to optimise XGBoost hyperparameters (slow)",
    )
    parser.add_argument(
        "--no-nn",
        dest="no_nn",
        action="store_true",
        default=False,
        help="Skip neural network training",
    )
    args = parser.parse_args()
    main(args.csv, optimize=args.optimize, train_nn=not args.no_nn)
