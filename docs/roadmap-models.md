# Model Improvements Roadmap — Ligue Odds

## Status
- ✅ Ensemble, Poisson, neural network, hyperparameter search, feature engineering, and backtesting are implemented.
- 🟡 Partial: Poisson is trained/saved but not exposed as a selectable prediction mode in the UI.
- ⚪ Outstanding: LSTM momentum model and standalone model-comparison report.
- Reviewed: 2026-05-28

## Current Implementation Status

| Area | Status |
|---|---|
| Ensemble classifier | ✅ Implemented in `models/ensemble_predictor.py` and trained by `train_models.py` |
| Poisson model | 🟡 Implemented in `models/poisson_predictor.py`; strengths are saved by `train_models.py`, but UI integration remains outstanding |
| Neural network | ✅ Implemented in `models/nn_predictor.py` and trained by `train_models.py` |
| LSTM momentum model | ⚪ Not implemented |
| Hyperparameter optimization | ✅ Implemented via `train_models.py --optimize` and `RandomizedSearchCV` |
| Feature engineering with lagged rolling windows | ✅ Implemented in `prepare_model_data.py` and `utils.py` |
| Historical backtesting | ✅ Implemented in `backtest.py` and surfaced in Statistics/Performance |
| Model comparison framework | ⚪ Not implemented as a standalone `compare_models.py` report |

## Current Target Variables
- **Primary:** 1X2 match result (Home Win / Draw / Away Win)
- **Secondary:** Over/Under 2.5 goals, Both Teams to Score (BTTS), Asian handicap

## Training Window
- 2015–16 through 2024–25 = **9 seasons × ~380 games = ~3,400 examples**
- Weight recent seasons more heavily (exponential decay, half-life = 2 seasons)
- Do **not** mix with EPL or Bundesliga data — La Liga has different scoring distributions

---

## Model 1 — Ensemble Classifier (Primary Model)
**Priority:** High | **Complexity:** Medium | **Expected Accuracy:** 50–60%

XGBoost + Random Forest + Gradient Boosting + Logistic Regression with soft voting (identical architecture to EPL/MLS apps — just retrained on La Liga data).

```python
# models/ensemble_predictor.py
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
import pickle

def create_ensemble_model():
    """Create soft-voting ensemble for La Liga match outcome prediction."""
    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )
    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    gb = GradientBoostingClassifier(n_estimators=150, max_depth=5, random_state=42)
    lr = LogisticRegression(max_iter=1000, random_state=42)

    ensemble = VotingClassifier(
        estimators=[("xgb", xgb), ("rf", rf), ("gb", gb), ("lr", lr)],
        voting="soft",
        weights=[2, 1.5, 1, 0.5],  # Higher weight for XGBoost
    )
    return ensemble


def train_and_save(X_train, y_train, path: str = "models/ensemble_model.pkl"):
    model = create_ensemble_model()
    model.fit(X_train, y_train)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    print(f"Model saved to {path}")
    return model


def load_model(path: str = "models/ensemble_model.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)
```

**Usage in `la_liga_linea.py`:**
```python
import streamlit as st
from sklearn.metrics import accuracy_score, mean_absolute_error

@st.cache_resource
def get_trained_model(X_train, y_train):
    from models.ensemble_predictor import create_ensemble_model
    m = create_ensemble_model()
    m.fit(X_train, y_train)
    return m

model = get_trained_model(X_train, y_train)
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)

col1, col2, col3 = st.columns(3)
col1.metric("Model Accuracy", f"{acc:.1%}", f"{acc - 0.5:.1%} vs random")
col2.metric("Mean Absolute Error", f"{mae:.3f}")
col3.metric("Test Predictions", len(y_test))
```

---

## Model 2 — Poisson Regression (Goal Prediction)
**Priority:** High | **Complexity:** Low | **Impact:** Enables over/under + scoreline markets

Dixon-Coles Poisson model. Estimate each team's attack and defense strength from historical goals, then use the Poisson PMF to generate a full scoreline probability matrix.

```python
# models/poisson_predictor.py
import numpy as np
from scipy.stats import poisson
import pandas as pd
from typing import Optional

LA_LIGA_AVG_HOME_GOALS = 1.45  # La Liga baseline (slightly lower than EPL ~1.53)
LA_LIGA_AVG_AWAY_GOALS = 1.12

def compute_team_strengths(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute attack/defense strength multipliers for each team.
    Uses last-N-seasons historical average goals as the baseline.
    """
    league_home_avg = df["FullTimeHomeGoals"].mean()
    league_away_avg = df["FullTimeAwayGoals"].mean()

    records = []
    for team in df["HomeTeam"].unique():
        home_matches = df[df["HomeTeam"] == team]
        away_matches = df[df["AwayTeam"] == team]

        if len(home_matches) == 0 or len(away_matches) == 0:
            continue

        home_attack  = home_matches["FullTimeHomeGoals"].mean() / league_home_avg
        home_defense = home_matches["FullTimeAwayGoals"].mean() / league_away_avg
        away_attack  = away_matches["FullTimeAwayGoals"].mean() / league_away_avg
        away_defense = away_matches["FullTimeHomeGoals"].mean() / league_home_avg

        records.append({
            "Team": team,
            "HomeAttack": home_attack,
            "HomeDefense": home_defense,
            "AwayAttack": away_attack,
            "AwayDefense": away_defense,
        })

    return pd.DataFrame(records)


def predict_match_poisson(
    home_team: str,
    away_team: str,
    strengths: pd.DataFrame,
    max_goals: int = 6,
) -> dict:
    """
    Predict match outcome using Poisson model.
    Returns HomeWinProb, DrawProb, AwayWinProb, ExpectedHomeGoals,
    ExpectedAwayGoals, MostLikelyScore, ScoreMatrix.
    """
    home_row = strengths[strengths["Team"] == home_team]
    away_row = strengths[strengths["Team"] == away_team]

    if home_row.empty or away_row.empty:
        # Fallback: league average
        exp_home = LA_LIGA_AVG_HOME_GOALS
        exp_away = LA_LIGA_AVG_AWAY_GOALS
    else:
        h = home_row.iloc[0]
        a = away_row.iloc[0]
        exp_home = h["HomeAttack"] * a["AwayDefense"] * LA_LIGA_AVG_HOME_GOALS
        exp_away = a["AwayAttack"] * h["HomeDefense"] * LA_LIGA_AVG_AWAY_GOALS

    # Build score matrix
    score_matrix = np.outer(
        poisson.pmf(range(max_goals + 1), exp_home),
        poisson.pmf(range(max_goals + 1), exp_away),
    )

    home_win = float(np.tril(score_matrix, -1).sum())
    draw     = float(np.trace(score_matrix))
    away_win = float(np.triu(score_matrix, 1).sum())

    # Most likely exact score
    best_i, best_j = np.unravel_index(score_matrix.argmax(), score_matrix.shape)

    # Over/under and BTTS
    over_2_5 = 1 - sum(
        score_matrix[i, j]
        for i in range(max_goals + 1)
        for j in range(max_goals + 1)
        if i + j <= 2
    )
    btts = 1 - float(
        score_matrix[:, 0].sum() + score_matrix[0, :].sum() - score_matrix[0, 0]
    )

    return {
        "HomeWinProb": round(home_win, 4),
        "DrawProb":    round(draw, 4),
        "AwayWinProb": round(away_win, 4),
        "ExpectedHomeGoals": round(exp_home, 2),
        "ExpectedAwayGoals": round(exp_away, 2),
        "MostLikelyScore": f"{best_i}–{best_j}",
        "Over2_5Prob": round(over_2_5, 4),
        "BTTSProb": round(btts, 4),
        "ScoreMatrix": score_matrix,
    }


# Example usage
if __name__ == "__main__":
    import pandas as pd
    df = pd.read_csv("data_files/combined_historical_data.csv")
    strengths = compute_team_strengths(df)
    result = predict_match_poisson("Real Madrid CF", "FC Barcelona", strengths)
    print(result)
```

**UI integration:**
```python
# In la_liga_linea.py predictions tab
model_choice = st.radio("Select model:", ["Ensemble Classifier", "Poisson Regression"], horizontal=True)

if model_choice == "Poisson Regression":
    from models.poisson_predictor import compute_team_strengths, predict_match_poisson
    strengths = compute_team_strengths(df_hist)
    for _, fix in upcoming_df.iterrows():
        result = predict_match_poisson(fix["HomeTeam"], fix["AwayTeam"], strengths)
        # Display result...
```

---

## Model 3 — Neural Network (PyTorch)
**Priority:** Medium | **Complexity:** High | **Expected Improvement:** +4–7% vs XGBoost baseline

3-layer fully connected network with batch normalization and dropout. Same architecture as EPL neural network — just re-trained on La Liga data.

```python
# models/nn_predictor.py
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from sklearn.preprocessing import StandardScaler

class LaLigaNet(nn.Module):
    def __init__(self, input_dim: int, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 3),   # Home Win / Draw / Away Win
        )

    def forward(self, x):
        return self.net(x)


def train_nn(
    X_train: np.ndarray,
    y_train: np.ndarray,
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 1e-3,
) -> tuple:
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    X_t = torch.FloatTensor(X_scaled)
    y_t = torch.LongTensor(y_train)
    loader = DataLoader(TensorDataset(X_t, y_t), batch_size=batch_size, shuffle=True)

    model = LaLigaNet(X_train.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(epochs):
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()

    return model, scaler


def predict_nn(model, scaler, X: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        X_t = torch.FloatTensor(scaler.transform(X))
        logits = model(X_t)
        return torch.softmax(logits, dim=1).numpy()
```

---

## Model 4 — LSTM Momentum Model
**Priority:** Low | **Complexity:** High | **Impact:** Captures temporal team momentum

Sequence-based LSTM that takes the last 5 matches (shots, corners, goals, result) as input to predict the next match outcome.

```python
# models/lstm_predictor.py
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

SEQUENCE_LENGTH = 5
MATCH_FEATURES = ["HomeShotsOnTarget", "FullTimeHomeGoals", "HomeShots"]  # expand as needed

class LSTMPredictor(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 3),
        )

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.fc(h_n[-1])


def prepare_sequences(df: pd.DataFrame, team: str, seq_len: int = 5) -> np.ndarray:
    """Extract last `seq_len` match feature rows for `team` as home team."""
    team_matches = df[df["HomeTeam"] == team].sort_values("MatchDate")
    feature_cols = [c for c in MATCH_FEATURES if c in team_matches.columns]
    sequences = team_matches[feature_cols].fillna(0).values
    if len(sequences) < seq_len:
        pad = np.zeros((seq_len - len(sequences), len(feature_cols)))
        sequences = np.vstack([pad, sequences])
    return sequences[-seq_len:]
```

---

## Model 5 — Hyperparameter Optimization
**Priority:** Medium | **Complexity:** Low | **Expected Improvement:** +1–3%

RandomizedSearchCV for XGBoost. Run nightly via GitHub Actions and cache best parameters.

```python
# In train_models.py
from sklearn.model_selection import RandomizedSearchCV
from xgboost import XGBClassifier
import json

PARAM_DIST = {
    "n_estimators": [100, 150, 200, 300],
    "max_depth": [3, 4, 5, 6, 7],
    "learning_rate": [0.05, 0.1, 0.15, 0.2],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.7, 0.8, 0.9, 1.0],
    "min_child_weight": [1, 3, 5, 7],
    "gamma": [0, 0.1, 0.2],
}

def optimize_xgboost(X_train, y_train) -> dict:
    base = XGBClassifier(eval_metric="mlogloss", random_state=42, verbosity=0)
    search = RandomizedSearchCV(
        base,
        PARAM_DIST,
        n_iter=15,
        cv=3,
        scoring="accuracy",
        random_state=42,
        n_jobs=-1,
    )
    search.fit(X_train, y_train)
    best = search.best_params_
    with open("models/best_hyperparams.json", "w") as f:
        json.dump(best, f, indent=2)
    print(f"Best params: {best}  |  CV accuracy: {search.best_score_:.3f}")
    return best
```

---

## Model Comparison Framework

```python
# compare_models.py
from sklearn.metrics import accuracy_score, f1_score, log_loss
import pandas as pd

def compare_all_models(X_train, X_test, y_train, y_test) -> pd.DataFrame:
    from models.ensemble_predictor import create_ensemble_model
    from xgboost import XGBClassifier
    from sklearn.ensemble import RandomForestClassifier

    models = {
        "XGBoost (baseline)": XGBClassifier(eval_metric="mlogloss", random_state=42, verbosity=0),
        "Random Forest":       RandomForestClassifier(n_estimators=200, random_state=42),
        "Ensemble":            create_ensemble_model(),
    }

    results = []
    for name, m in models.items():
        m.fit(X_train, y_train)
        y_pred  = m.predict(X_test)
        y_proba = m.predict_proba(X_test)
        results.append({
            "Model":    name,
            "Accuracy": round(accuracy_score(y_test, y_pred), 4),
            "F1 (macro)": round(f1_score(y_test, y_pred, average="macro"), 4),
            "Log Loss": round(log_loss(y_test, y_proba), 4),
        })

    return pd.DataFrame(results).sort_values("Accuracy", ascending=False)
```

---

## Feature Engineering for Models

All features must use `shift(1)` on rolling windows to prevent data leakage.

```python
# In prepare_model_data.py

def calculate_la_liga_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer all predictive features from historical match data.
    Uses shift(1) on rolling windows to ensure no data leakage.
    """
    df = df.sort_values("MatchDate").reset_index(drop=True)

    # --- xG proxy from shots (until FBref xG is integrated) ---
    df["xG_Home_Match"] = df["HomeShotsOnTarget"] * 0.35 + df["HomeShots"] * 0.10
    df["xG_Away_Match"] = df["AwayShotsOnTarget"] * 0.35 + df["AwayShots"] * 0.10

    # --- Rolling home team metrics (last 5, using shift to exclude current) ---
    df["HomexG_Avg_L5"] = (
        df.groupby("HomeTeam")["xG_Home_Match"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["HomeGoals_Avg_L5"] = (
        df.groupby("HomeTeam")["FullTimeHomeGoals"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["HomeGoalsAgainst_Avg_L5"] = (
        df.groupby("HomeTeam")["FullTimeAwayGoals"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["HomeMomentum_L3"] = (
        df.groupby("HomeTeam")["FullTimeHomeGoals"]
        .shift(1).rolling(3, min_periods=1).sum()
        .reset_index(level=0, drop=True)
    )

    # --- Rolling away team metrics ---
    df["AwayxG_Avg_L5"] = (
        df.groupby("AwayTeam")["xG_Away_Match"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["AwayGoals_Avg_L5"] = (
        df.groupby("AwayTeam")["FullTimeAwayGoals"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["AwayGoalsAgainst_Avg_L5"] = (
        df.groupby("AwayTeam")["FullTimeHomeGoals"]
        .shift(1).rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
    )
    df["AwayMomentum_L3"] = (
        df.groupby("AwayTeam")["FullTimeAwayGoals"]
        .shift(1).rolling(3, min_periods=1).sum()
        .reset_index(level=0, drop=True)
    )

    # --- Days rest ---
    df["HomeRestDays"] = (
        df.groupby("HomeTeam")["MatchDate"]
        .diff().dt.days.fillna(7)
    )
    df["AwayRestDays"] = (
        df.groupby("AwayTeam")["MatchDate"]
        .diff().dt.days.fillna(7)
    )

    # --- Head-to-head win rate (last 5 meetings) ---
    df["H2H_HomeWinRate_L5"] = df.apply(
        lambda r: _h2h_win_rate(df, r["HomeTeam"], r["AwayTeam"], r["MatchDate"]), axis=1
    )

    # Fill NaN defaults
    defaults = {
        "HomexG_Avg_L5": 1.35, "AwayxG_Avg_L5": 1.05,
        "HomeGoals_Avg_L5": 1.45, "AwayGoals_Avg_L5": 1.12,
        "HomeGoalsAgainst_Avg_L5": 1.12, "AwayGoalsAgainst_Avg_L5": 1.45,
        "HomeMomentum_L3": 4.0, "AwayMomentum_L3": 3.0,
        "H2H_HomeWinRate_L5": 0.33,
    }
    for col, val in defaults.items():
        df[col] = df[col].fillna(val)

    # Clean up intermediate columns
    df.drop(columns=["xG_Home_Match", "xG_Away_Match"], errors="ignore", inplace=True)
    return df


def _h2h_win_rate(df, home_team, away_team, match_date, n=5) -> float:
    mask = (
        ((df["HomeTeam"] == home_team) & (df["AwayTeam"] == away_team)) |
        ((df["HomeTeam"] == away_team) & (df["AwayTeam"] == home_team))
    ) & (df["MatchDate"] < match_date)
    past = df[mask].sort_values("MatchDate").tail(n)
    if len(past) == 0:
        return 0.33
    wins = sum(
        1 for _, r in past.iterrows()
        if (r["HomeTeam"] == home_team and r["FullTimeResult"] == "H") or
           (r["AwayTeam"] == home_team and r["FullTimeResult"] == "A")
    )
    return wins / len(past)
```

---

## Backtesting

Evaluate model against closing odds lines to measure edge.

```python
# backtest.py
import pandas as pd
import numpy as np

def backtest_model(df: pd.DataFrame, predictions: np.ndarray) -> dict:
    """
    Compare model predicted probabilities against implied market probabilities.
    Requires 'ImpliedProb_HomeWin', 'ImpliedProb_Draw', 'ImpliedProb_AwayWin' columns.
    Returns Brier score, ROI simulation, and calibration stats.
    """
    actual = df["FullTimeResult"].map({"H": 0, "D": 1, "A": 2}).values
    # Brier score (lower is better; random = 0.667)
    brier = float(np.mean(np.sum((predictions - np.eye(3)[actual]) ** 2, axis=1)))

    # Flat-stake ROI simulation (bet whenever model > market by threshold)
    THRESHOLD = 0.05
    total_bets = 0
    profit = 0.0
    for i, row in df.iterrows():
        for outcome, col, prob_idx in [
            ("H", "Bet365_HomeWinOdds", 0),
            ("D", "Bet365_DrawOdds", 1),
            ("A", "Bet365_AwayWinOdds", 2),
        ]:
            if col not in df.columns:
                continue
            market_prob = 1 / row[col]
            model_prob = predictions[i, prob_idx]
            if model_prob - market_prob >= THRESHOLD:
                total_bets += 1
                if row["FullTimeResult"] == outcome:
                    profit += row[col] - 1
                else:
                    profit -= 1

    roi = (profit / total_bets * 100) if total_bets > 0 else 0.0
    return {
        "BrierScore": round(brier, 4),
        "TotalBets": total_bets,
        "Profit": round(profit, 2),
        "ROI_%": round(roi, 2),
    }
```

---

## Recommended Next Steps

1. ✅ **Implement ensemble model** — complete for Ligue 1 data.
2. 🟡 **Add Poisson model** — model is implemented; UI/market integration remains.
3. ✅ **Hyperparameter tuning** — available through `train_models.py --optimize`.
4. ✅ **Neural network** — implemented and wired into the nightly training path.
5. ⚪ **LSTM** — still outstanding.
6. ✅ **Backtesting dashboard** — implemented through `backtest.py`, Statistics, and Performance.
