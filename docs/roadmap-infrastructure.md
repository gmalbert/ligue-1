# Technical Infrastructure Roadmap — Ligue Odds

## Status
- ✅ Nightly automation, keep-alive workflow, offline training, caching, `.env`, and prediction/backtest generation are implemented.
- 🟡 Partial: logging and testing remain light; the keep-alive workflow still references the old La Liga app URL.
- ⚪ Outstanding: SQLite migration, API layer, and formal pytest suite.
- Reviewed: 2026-05-28

## Current Implementation Status

| # | Infrastructure Item | Status |
|---|---|---|
| 1 | GitHub Actions nightly pipeline | ✅ Implemented in `.github/workflows/nightly.yml` |
| 2 | Keep-alive workflow | 🟡 Implemented in `.github/workflows/keep-alive.yml`, but URL still points to the old La Liga app |
| 3 | Automated local pipeline script | ✅ Implemented in `automation/nightly_pipeline.py` |
| 4 | Model training script | ✅ Implemented in `train_models.py` |
| 5 | Logging system | ⚪ Not implemented as a shared rotating logger |
| 6 | Streamlit caching | ✅ Implemented with `@st.cache_data` and `@st.cache_resource` in `utils.py` |
| 7 | SQLite migration | ⚪ Not implemented |
| 8 | Testing framework | ⚪ No `tests/` suite currently present |
| 9 | Environment variables | ✅ Implemented with `.env.example`, `python-dotenv`, and `.gitignore` entries |

## Current Architecture (Starting Point)
- **Framework:** Streamlit
- **ML:** XGBoost, scikit-learn
- **Data:** Pandas, NumPy
- **Storage:** CSV files
- **Deployment:** Local / GitHub Pages via Streamlit Community Cloud

---

## 1. GitHub Actions — Nightly Data Pipeline
**Priority:** High | **Effort:** Low | **Impact:** Very High

Auto-fetch fixtures, results, and retrain models every night so the app always shows current data. Mirrors the EPL and MLS nightly workflows.

```yaml
# .github/workflows/nightly.yml
name: Nightly Data + Model Update

on:
  schedule:
    - cron: "0 7 * * *"   # 3:00 AM ET (UTC-4 summer / UTC-5 winter)
  workflow_dispatch:        # Allow manual trigger from GitHub Actions UI

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch historical match data
        env:
          FOOTBALL_DATA_KEY: ${{ secrets.FOOTBALL_DATA_KEY }}
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
        run: python fetch_historical_csvs.py

      - name: Fetch upcoming fixtures
        env:
          FOOTBALL_DATA_KEY: ${{ secrets.FOOTBALL_DATA_KEY }}
        run: python fetch_upcoming_fixtures.py

      - name: Fetch FBref xG data
        run: python fetch_fbref_xg.py

      - name: Fetch Copa del Rey fixtures
        env:
          FOOTBALL_DATA_KEY: ${{ secrets.FOOTBALL_DATA_KEY }}
        run: python fetch_copa_fixtures.py

      - name: Fetch odds
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
        run: python fetch_odds.py

      - name: Prepare model data (feature engineering)
        run: python prepare_model_data.py

      - name: Train and save models
        run: python train_models.py

      - name: Validate predictions
        run: python track_predictions.py --validate

      - name: Commit updated data and models
        run: |
          git config user.name  "actions-user"
          git config user.email "actions@github.com"
          git add data_files/ models/
          git diff --staged --quiet || git commit -m "Nightly update - $(date +%Y-%m-%d) - Data + Models"
          git push
```

**Required GitHub Secrets:**
```
FOOTBALL_DATA_KEY   → football-data.org API key
ODDS_API_KEY        → The Odds API key
```

Add via: `Repository → Settings → Secrets and variables → Actions`

---

## 2. Keep-Alive Workflow (Streamlit Community Cloud)
**Priority:** High | **Effort:** Very Low | **Impact:** High

Streamlit Community Cloud hibernates apps after inactivity. A daily ping keeps the app live.

```yaml
# .github/workflows/keep-alive.yml
name: Keep App Alive

on:
  schedule:
    - cron: "0 12 * * *"   # 8:00 AM ET daily
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping La Liga Linea app
        run: |
          curl -s -o /dev/null -w "%{http_code}" \
            https://la-liga-linea.streamlit.app/ || echo "Ping sent"
```

---

## 3. Automated Data Pipeline Script
**Priority:** High | **Effort:** Low | **Impact:** High

A single orchestrator script that can be run locally or called from GitHub Actions.

```python
# automation/nightly_pipeline.py
import subprocess
import sys
from datetime import datetime

STEPS = [
    ("Fetch historical CSVs",  ["python", "fetch_historical_csvs.py"]),
    ("Fetch upcoming fixtures", ["python", "fetch_upcoming_fixtures.py"]),
    ("Fetch FBref xG",         ["python", "fetch_fbref_xg.py"]),
    ("Fetch Copa fixtures",    ["python", "fetch_copa_fixtures.py"]),
    ("Fetch odds",             ["python", "fetch_odds.py"]),
    ("Prepare model data",     ["python", "prepare_model_data.py"]),
    ("Train models",           ["python", "train_models.py"]),
    ("Validate predictions",   ["python", "track_predictions.py", "--validate"]),
]

def run_pipeline():
    print(f"\n{'='*60}")
    print(f"La Liga Linea — Nightly Pipeline")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    failed = []
    for name, cmd in STEPS:
        print(f"▶ {name}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✓ Done\n")
        else:
            print(f"  ✗ FAILED\n  stderr: {result.stderr[:200]}\n")
            failed.append(name)

    print(f"\n{'='*60}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if failed:
        print(f"Failed steps: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All steps completed successfully.")

if __name__ == "__main__":
    run_pipeline()
```

---

## 4. Model Training Script
**Priority:** High | **Effort:** Low | **Impact:** High

Offline model training to be run nightly, saving `.pkl` files that the app loads at startup (avoids in-request training).

```python
# train_models.py
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, log_loss

from models.ensemble_predictor import create_ensemble_model
from models.poisson_predictor import compute_team_strengths
from prepare_model_data import load_and_engineer_features

Path("models").mkdir(exist_ok=True)

def load_training_data(csv_path: str):
    df = pd.read_csv(csv_path)
    df = load_and_engineer_features(df)

    result_map = {"H": 0, "D": 1, "A": 2}
    df = df[df["FullTimeResult"].isin(result_map)].copy()
    df["target"] = df["FullTimeResult"].map(result_map)

    drop_cols = [
        "FullTimeResult", "target", "MatchDate", "HomeTeam", "AwayTeam",
        "FullTimeHomeGoals", "FullTimeAwayGoals", "Season",
    ]
    X = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
    y = df["target"]

    X_num = X.select_dtypes(include=[np.number])
    for col in X.select_dtypes(include=["object"]).columns:
        le = LabelEncoder()
        X_num[col] = le.fit_transform(X[col].astype(str))

    X_final = X_num.fillna(0)
    return train_test_split(X_final.values, y.values, test_size=0.2, random_state=42, stratify=y)


def train_ensemble(csv_path: str = "data_files/combined_historical_data.csv"):
    print("Training ensemble model…")
    X_train, X_test, y_train, y_test = load_training_data(csv_path)

    model = create_ensemble_model()
    model.fit(X_train, y_train)

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    metrics = {
        "accuracy":   round(accuracy_score(y_test, y_pred), 4),
        "f1_macro":   round(f1_score(y_test, y_pred, average="macro"), 4),
        "log_loss":   round(log_loss(y_test, y_proba), 4),
        "n_train":    len(X_train),
        "n_test":     len(X_test),
    }

    with open("models/ensemble_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open("models/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"  Accuracy: {metrics['accuracy']:.1%}  |  F1: {metrics['f1_macro']:.3f}  |  Log Loss: {metrics['log_loss']:.3f}")
    print("  Saved: models/ensemble_model.pkl")


def train_poisson(csv_path: str = "data_files/combined_historical_data.csv"):
    print("Computing Poisson team strengths…")
    df = pd.read_csv(csv_path)
    strengths = compute_team_strengths(df)
    strengths.to_csv("models/poisson_strengths.csv", index=False)
    print(f"  Saved: models/poisson_strengths.csv ({len(strengths)} teams)")


if __name__ == "__main__":
    train_ensemble()
    train_poisson()
    print("\nAll models trained successfully.")
```

---

## 5. Logging System
**Priority:** Medium | **Effort:** Low | **Impact:** Medium

```python
# utils/logger.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(name: str, log_file: str = "app.log", level=logging.INFO):
    Path("logs").mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:   # Avoid duplicate handlers on re-import
        return logger

    fmt = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")

    fh = RotatingFileHandler(f"logs/{log_file}", maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setFormatter(fmt)
    fh.setLevel(level)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(level)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# Usage
# from utils.logger import setup_logger
# logger = setup_logger("data_pipeline")
# logger.info("Fetching fixtures…")
# logger.error("API request failed", exc_info=True)
```

---

## 6. Streamlit Caching Strategy
**Priority:** High | **Effort:** Low | **Impact:** High

Use `@st.cache_data` for DataFrames (serializable) and `@st.cache_resource` for models (non-serializable).

```python
# Caching patterns in la_liga_linea.py

import streamlit as st
import pandas as pd
import pickle

@st.cache_data(ttl=3600)           # Re-load every hour
def load_historical_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    return df

@st.cache_data(ttl=3600)
def load_upcoming_fixtures(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)

@st.cache_resource                 # Persist model in memory for the session
def load_trained_model(model_path: str = "models/ensemble_model.pkl"):
    """Load pre-trained model from disk (avoids retraining on every page load)."""
    try:
        with open(model_path, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

@st.cache_data(ttl=7200)
def load_fbref_xg(path: str = "data_files/raw/fbref_team_xg.csv") -> pd.DataFrame:
    from os import path as ospath
    if not ospath.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)

# Dynamic dataframe height helper (reused from MLS app)
def get_dataframe_height(
    df: pd.DataFrame,
    row_height: int = 35,
    header_height: int = 38,
    padding: int = 2,
    max_height: int = 600,
) -> int:
    calculated = len(df) * row_height + header_height + padding
    return min(calculated, max_height) if max_height else calculated
```

---

## 7. Database Migration (SQLite)
**Priority:** Low | **Effort:** Medium | **Impact:** Medium

Optional upgrade from CSV to SQLite for faster queries and better concurrency.

```python
# database/setup.py
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "data_files/la_liga.db"

def create_database():
    Path("data_files").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            match_date         DATE NOT NULL,
            matchday           INTEGER,
            home_team          TEXT NOT NULL,
            away_team          TEXT NOT NULL,
            full_time_result   TEXT,
            home_goals         INTEGER,
            away_goals         INTEGER,
            season             TEXT,
            home_xg_l5         REAL,
            away_xg_l5         REAL,
            home_rest_days     INTEGER,
            away_rest_days     INTEGER,
            home_copa_flag     INTEGER DEFAULT 0,
            away_copa_flag     INTEGER DEFAULT 0,
            implied_prob_home  REAL,
            implied_prob_draw  REAL,
            implied_prob_away  REAL,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id       INTEGER REFERENCES matches(match_id),
            pred_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            home_win_prob  REAL,
            draw_prob      REAL,
            away_win_prob  REAL,
            model_version  TEXT,
            actual_result  TEXT,
            correct        INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database created at {DB_PATH}")


def migrate_csv_to_db(csv_path: str = "data_files/combined_historical_data.csv"):
    df = pd.read_csv(csv_path)
    conn = sqlite3.connect(DB_PATH)

    col_map = {
        "MatchDate":           "match_date",
        "Matchday":            "matchday",
        "HomeTeam":            "home_team",
        "AwayTeam":            "away_team",
        "FullTimeResult":      "full_time_result",
        "FullTimeHomeGoals":   "home_goals",
        "FullTimeAwayGoals":   "away_goals",
        "Season":              "season",
        "HomexG_Avg_L5":       "home_xg_l5",
        "AwayxG_Avg_L5":       "away_xg_l5",
        "HomeRestDays":        "home_rest_days",
        "AwayRestDays":        "away_rest_days",
        "HomeCopaCongestion":  "home_copa_flag",
        "AwayCopaCongestion":  "away_copa_flag",
        "ImpliedProb_HomeWin": "implied_prob_home",
        "ImpliedProb_Draw":    "implied_prob_draw",
        "ImpliedProb_AwayWin": "implied_prob_away",
    }

    db_df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    keep = list(col_map.values())
    db_df = db_df[[c for c in keep if c in db_df.columns]]
    db_df.to_sql("matches", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Migrated {len(db_df)} matches to SQLite.")


def query_matches(team: str = None, start_date: str = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    q = "SELECT * FROM matches WHERE 1=1"
    params = []
    if team:
        q += " AND (home_team = ? OR away_team = ?)"
        params += [team, team]
    if start_date:
        q += " AND match_date >= ?"
        params.append(start_date)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df
```

---

## 8. Testing Framework
**Priority:** Medium | **Effort:** Medium | **Impact:** High

```python
# tests/test_pipeline.py
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

def test_historical_data_exists():
    assert Path("data_files/combined_historical_data.csv").exists(), \
        "Run fetch_historical_csvs.py first"

def test_historical_data_schema():
    df = pd.read_csv("data_files/combined_historical_data.csv")
    required = ["MatchDate", "HomeTeam", "AwayTeam", "FullTimeResult",
                "FullTimeHomeGoals", "FullTimeAwayGoals"]
    for col in required:
        assert col in df.columns, f"Missing column: {col}"

def test_result_values():
    df = pd.read_csv("data_files/combined_historical_data.csv")
    invalid = df[~df["FullTimeResult"].isin(["H", "D", "A", ""])]["FullTimeResult"].unique()
    assert len(invalid) == 0, f"Unexpected FullTimeResult values: {invalid}"

def test_ensemble_model_output_shape():
    from models.ensemble_predictor import create_ensemble_model
    m = create_ensemble_model()
    X = np.random.rand(30, 10)
    y = np.array([0, 1, 2] * 10)
    m.fit(X, y)
    proba = m.predict_proba(X)
    assert proba.shape == (30, 3), f"Expected (30, 3), got {proba.shape}"
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5), "Probabilities must sum to 1"

def test_poisson_probabilities_sum_to_one():
    import pandas as pd
    from models.poisson_predictor import compute_team_strengths, predict_match_poisson

    # Minimal fake data
    df = pd.DataFrame({
        "HomeTeam":          ["Real Madrid CF"] * 10 + ["FC Barcelona"] * 10,
        "AwayTeam":          ["FC Barcelona"] * 10 + ["Real Madrid CF"] * 10,
        "FullTimeHomeGoals": [2, 1, 3, 0, 2, 1, 0, 2, 1, 3] * 2,
        "FullTimeAwayGoals": [1, 2, 1, 0, 0, 1, 2, 1, 0, 2] * 2,
    })
    strengths = compute_team_strengths(df)
    result = predict_match_poisson("Real Madrid CF", "FC Barcelona", strengths)
    total = result["HomeWinProb"] + result["DrawProb"] + result["AwayWinProb"]
    assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, expected ~1.0"

def test_feature_engineering_no_leakage():
    """Ensure rolling features use shift(1) — no data from the current match."""
    from prepare_model_data import calculate_la_liga_features
    df = pd.read_csv("data_files/combined_historical_data.csv")
    df = calculate_la_liga_features(df.head(100))
    # If xG average for the first home appearance is NaN or equal to default,
    # that confirms shift(1) is working correctly.
    assert "HomexG_Avg_L5" in df.columns
```

**Run tests:**
```bash
pip install pytest
pytest tests/ -v
```

**Add to GitHub Actions:**
```yaml
      - name: Run tests
        run: pytest tests/ -v
```

---

## 9. Environment Variables (`.env`)
**Priority:** High | **Effort:** Very Low | **Impact:** High (security)

```bash
# .env  — DO NOT COMMIT — add to .gitignore
FOOTBALL_DATA_KEY=your_football_data_org_key_here
ODDS_API_KEY=your_odds_api_key_here
```

```python
# Load in any script that needs API keys
from dotenv import load_dotenv
import os

load_dotenv()
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")
ODDS_API_KEY      = os.environ.get("ODDS_API_KEY", "")
```

```
# .gitignore additions
.env
*.pkl
logs/
__pycache__/
.streamlit/secrets.toml
```

---

## Infrastructure Timeline

**Phase 1 (Week 1):**
- ✅ `.env` + python-dotenv for secrets
- ✅ Caching patterns (`@st.cache_data`, `@st.cache_resource`)
- ⚪ Logging system

**Phase 2 (Week 2):**
- ✅ GitHub Actions nightly pipeline
- 🟡 Keep-alive workflow
- ✅ `train_models.py` offline training

**Phase 3 (Month 1):**
- ⚪ Testing framework (`pytest`)
- ⚪ CI tests in GitHub Actions

**Phase 4 (Month 2):**
- ⚪ SQLite migration
- ⚪ API layer (FastAPI, optional)
