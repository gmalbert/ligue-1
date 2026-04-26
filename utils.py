"""Shared utilities for La Liga Linea.

Includes: data loading, feature engineering, model training/loading,
standings computation, prediction risk scoring, and display helpers.
"""

from __future__ import annotations

import json
import os
import pickle
import warnings
from datetime import datetime
from os import path
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ── Constants ──────────────────────────────────────────────────────────────

MODEL_PATH   = "models/ensemble_model.pkl"
METRICS_PATH = "models/metrics.json"

FEATURE_COLS: list[str] = [
    "HomeGoals_Avg_L5",
    "HomeConceded_Avg_L5",
    "HomeWinRate_L10",
    "HomeMomentum_L3",
    "HomeRestDays",
    "AwayGoals_Avg_L5",
    "AwayConceded_Avg_L5",
    "AwayWinRate_L10",
    "AwayMomentum_L3",
    "AwayRestDays",
    "ImpliedProb_HomeWin",
    "ImpliedProb_Draw",
    "ImpliedProb_AwayWin",
]

# Alphabetical LabelEncoder order: A=0, D=1, H=2
RESULT_MAP  = {"A": 0, "D": 1, "H": 2}
RESULT_RMAP = {0: "A", 1: "D", 2: "H"}

# La Liga average goal rates (2015-16 → 2023-24)
LA_LIGA_AVG_HOME_GOALS = 1.45
LA_LIGA_AVG_AWAY_GOALS = 1.12


# ── Display Helpers ────────────────────────────────────────────────────────

def show_last_updated(file_path: str, label: str = "Data") -> None:
    """Render a caption showing how long ago a file was last modified."""
    if not path.exists(file_path):
        return
    mtime = os.path.getmtime(file_path)
    delta = datetime.now() - datetime.fromtimestamp(mtime)
    days  = delta.days
    hours = delta.seconds // 3600
    mins  = (delta.seconds % 3600) // 60
    if days > 0:
        age = f"{days}d {hours}h ago"
    elif hours > 0:
        age = f"{hours}h {mins}m ago"
    else:
        age = f"{mins}m ago"
    st.caption(f"🕐 {label} last updated: {age}")


# ── Data Loading ───────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_historical_data(csv_path: str) -> pd.DataFrame:
    """Load and normalize the combined historical match CSV."""
    df = pd.read_csv(csv_path, low_memory=False)

    # Normalize football-data.co.uk column names to internal standard
    col_map = {
        "Date":  "MatchDate",
        "FTHG":  "FullTimeHomeGoals",
        "FTAG":  "FullTimeAwayGoals",
        "FTR":   "FullTimeResult",
        "B365H": "OddsHome",
        "B365D": "OddsDraw",
        "B365A": "OddsAway",
        "BWH":   "OddsHome",
        "BWD":   "OddsDraw",
        "BWA":   "OddsAway",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    df["MatchDate"] = pd.to_datetime(df["MatchDate"], dayfirst=True, errors="coerce")
    df["FullTimeHomeGoals"] = pd.to_numeric(df.get("FullTimeHomeGoals"), errors="coerce").fillna(0)
    df["FullTimeAwayGoals"] = pd.to_numeric(df.get("FullTimeAwayGoals"), errors="coerce").fillna(0)
    df = df.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam"])
    df = df.sort_values("MatchDate").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def load_upcoming_fixtures(csv_path: str) -> pd.DataFrame:
    if not path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df["Date"] = pd.to_datetime(df.get("Date", ""), errors="coerce")
    df = df.sort_values("Date").reset_index(drop=True)
    return df


# ── Feature Engineering ────────────────────────────────────────────────────

def calculate_la_liga_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized feature engineering for historical match data.
    Uses shift(1) per team to prevent data leakage.
    """
    df = df.copy().sort_values("MatchDate").reset_index(drop=True)

    # Long format: one row per team per match
    home_side = df[
        ["MatchDate", "HomeTeam", "FullTimeHomeGoals", "FullTimeAwayGoals", "FullTimeResult"]
    ].copy()
    home_side.columns = ["MatchDate", "Team", "GF", "GA", "FTR"]
    home_side["Pts"] = home_side["FTR"].map({"H": 3, "D": 1, "A": 0}).fillna(0)
    home_side["Won"] = (home_side["FTR"] == "H").astype(float)

    away_side = df[
        ["MatchDate", "AwayTeam", "FullTimeAwayGoals", "FullTimeHomeGoals", "FullTimeResult"]
    ].copy()
    away_side.columns = ["MatchDate", "Team", "GF", "GA", "FTR"]
    away_side["Pts"] = away_side["FTR"].map({"A": 3, "D": 1, "H": 0}).fillna(0)
    away_side["Won"] = (away_side["FTR"] == "A").astype(float)

    long = pd.concat([home_side, away_side], ignore_index=True)
    long = long.sort_values(["Team", "MatchDate"]).reset_index(drop=True)

    grp = long.groupby("Team")
    long["GF_L5"]    = grp["GF"].transform(lambda x: x.shift(1).rolling(5,  min_periods=1).mean())
    long["GA_L5"]    = grp["GA"].transform(lambda x: x.shift(1).rolling(5,  min_periods=1).mean())
    long["Won_L10"]  = grp["Won"].transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
    long["Pts_L3"]   = grp["Pts"].transform(lambda x: x.shift(1).rolling(3,  min_periods=1).sum())

    long["PrevDate"] = grp["MatchDate"].shift(1)
    long["RestDays"] = (
        (long["MatchDate"] - long["PrevDate"]).dt.days
        .clip(1, 30)
        .fillna(7)
        .astype(float)
    )

    feat_cols = ["MatchDate", "Team", "GF_L5", "GA_L5", "Won_L10", "Pts_L3", "RestDays"]

    home_feats = long[feat_cols].rename(columns={
        "Team":    "HomeTeam",
        "GF_L5":   "HomeGoals_Avg_L5",
        "GA_L5":   "HomeConceded_Avg_L5",
        "Won_L10": "HomeWinRate_L10",
        "Pts_L3":  "HomeMomentum_L3",
        "RestDays":"HomeRestDays",
    })
    away_feats = long[feat_cols].rename(columns={
        "Team":    "AwayTeam",
        "GF_L5":   "AwayGoals_Avg_L5",
        "GA_L5":   "AwayConceded_Avg_L5",
        "Won_L10": "AwayWinRate_L10",
        "Pts_L3":  "AwayMomentum_L3",
        "RestDays":"AwayRestDays",
    })

    df = df.merge(home_feats, on=["MatchDate", "HomeTeam"], how="left")
    df = df.merge(away_feats, on=["MatchDate", "AwayTeam"], how="left")

    # Implied probabilities from bookmaker odds
    for col in ["OddsHome", "OddsDraw", "OddsAway"]:
        if col not in df.columns:
            df[col] = np.nan
    df[["OddsHome", "OddsDraw", "OddsAway"]] = df[
        ["OddsHome", "OddsDraw", "OddsAway"]
    ].apply(pd.to_numeric, errors="coerce")

    valid_odds = df["OddsHome"].notna() & df["OddsDraw"].notna() & df["OddsAway"].notna()
    df.loc[valid_odds, "_vig"] = (
        1 / df.loc[valid_odds, "OddsHome"]
        + 1 / df.loc[valid_odds, "OddsDraw"]
        + 1 / df.loc[valid_odds, "OddsAway"]
    )
    df.loc[valid_odds, "ImpliedProb_HomeWin"] = (1 / df.loc[valid_odds, "OddsHome"]) / df.loc[valid_odds, "_vig"]
    df.loc[valid_odds, "ImpliedProb_Draw"]    = (1 / df.loc[valid_odds, "OddsDraw"])  / df.loc[valid_odds, "_vig"]
    df.loc[valid_odds, "ImpliedProb_AwayWin"] = (1 / df.loc[valid_odds, "OddsAway"])  / df.loc[valid_odds, "_vig"]
    df.drop(columns=["_vig"], errors="ignore", inplace=True)

    df["ImpliedProb_HomeWin"] = df.get("ImpliedProb_HomeWin", pd.Series(dtype=float)).fillna(0.45)
    df["ImpliedProb_Draw"]    = df.get("ImpliedProb_Draw",    pd.Series(dtype=float)).fillna(0.27)
    df["ImpliedProb_AwayWin"] = df.get("ImpliedProb_AwayWin", pd.Series(dtype=float)).fillna(0.28)

    return df


def _team_stats_for_upcoming(hist_df: pd.DataFrame, team: str) -> dict:
    """Current rolling stats for a team — used to build the upcoming fixtures feature vector."""
    _default = {
        "goals_avg_l5":    LA_LIGA_AVG_HOME_GOALS,
        "conceded_avg_l5": LA_LIGA_AVG_AWAY_GOALS,
        "win_rate_l10":    0.33,
        "momentum_l3":     3.0,
        "rest_days":       7,
    }

    home_m = hist_df[hist_df["HomeTeam"] == team].copy()
    away_m = hist_df[hist_df["AwayTeam"] == team].copy()

    if home_m.empty and away_m.empty:
        return _default

    home_m = home_m.assign(
        GF=pd.to_numeric(home_m["FullTimeHomeGoals"], errors="coerce").fillna(0),
        GA=pd.to_numeric(home_m["FullTimeAwayGoals"], errors="coerce").fillna(0),
        Won=(home_m["FullTimeResult"] == "H").astype(int),
        Pts=home_m["FullTimeResult"].map({"H": 3, "D": 1, "A": 0}).fillna(0),
    )
    away_m = away_m.assign(
        GF=pd.to_numeric(away_m["FullTimeAwayGoals"], errors="coerce").fillna(0),
        GA=pd.to_numeric(away_m["FullTimeHomeGoals"], errors="coerce").fillna(0),
        Won=(away_m["FullTimeResult"] == "A").astype(int),
        Pts=away_m["FullTimeResult"].map({"A": 3, "D": 1, "H": 0}).fillna(0),
    )

    all_m = (
        pd.concat([
            home_m[["MatchDate", "GF", "GA", "Won", "Pts"]],
            away_m[["MatchDate", "GF", "GA", "Won", "Pts"]],
        ])
        .sort_values("MatchDate")
        .reset_index(drop=True)
    )

    last5  = all_m.tail(5)
    last10 = all_m.tail(10)
    last3  = all_m.tail(3)

    last_date = all_m["MatchDate"].max()
    rest = max(1, min(int((pd.Timestamp.now() - last_date).days), 30))

    return {
        "goals_avg_l5":    float(last5["GF"].mean())   if len(last5)  else _default["goals_avg_l5"],
        "conceded_avg_l5": float(last5["GA"].mean())   if len(last5)  else _default["conceded_avg_l5"],
        "win_rate_l10":    float(last10["Won"].mean())  if len(last10) else _default["win_rate_l10"],
        "momentum_l3":     float(last3["Pts"].sum())    if len(last3)  else _default["momentum_l3"],
        "rest_days":       rest,
    }


# ── Model ──────────────────────────────────────────────────────────────────

def _create_ensemble() -> VotingClassifier:
    return VotingClassifier(
        estimators=[
            ("xgb", XGBClassifier(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                random_state=42, eval_metric="mlogloss", verbosity=0,
            )),
            ("rf",  RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)),
            ("gb",  GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=42)),
            ("lr",  LogisticRegression(max_iter=500, random_state=42, multi_class="multinomial")),
        ],
        voting="soft",
        weights=[2, 1.5, 1, 0.5],
    )


@st.cache_resource
def load_or_train_model(
    hist_df: pd.DataFrame,
) -> tuple[VotingClassifier | None, list[str], dict]:
    """
    Return (model, feature_names, metrics).
    Loads from disk if the pkl exists; otherwise trains from hist_df and saves.
    """
    if path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        metrics: dict = {}
        if path.exists(METRICS_PATH):
            with open(METRICS_PATH) as f:
                metrics = json.load(f)
        return model, FEATURE_COLS, metrics

    # Train from scratch
    df = calculate_la_liga_features(hist_df)
    df = df[df["FullTimeResult"].isin(RESULT_MAP)].copy()
    df["_target"] = df["FullTimeResult"].map(RESULT_MAP)

    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0).values
    y = df["_target"].values

    if len(X) < 100:
        return None, available, {}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = _create_ensemble()
    model.fit(X_train, y_train)

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_test, y_pred, average="macro")), 4),
        "log_loss": round(float(log_loss(y_test, y_proba)), 4),
        "n_train":  int(len(X_train)),
        "n_test":   int(len(X_test)),
    }

    Path("models").mkdir(exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    return model, available, metrics


def predict_for_upcoming(
    upcoming_df: pd.DataFrame,
    hist_df: pd.DataFrame,
    model: VotingClassifier,
    feature_names: list[str],
) -> pd.DataFrame:
    """Build the predictions DataFrame for all upcoming fixtures."""
    if upcoming_df.empty or hist_df.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, fix in upcoming_df.iterrows():
        home_raw = str(fix.get("HomeTeam", ""))
        away_raw = str(fix.get("AwayTeam", ""))
        if not home_raw or not away_raw or home_raw == "nan" or away_raw == "nan":
            continue

        # Normalize to football-data.co.uk short names used in historical data
        from team_name_mapping import normalize_team_name
        home = normalize_team_name(home_raw)
        away = normalize_team_name(away_raw)

        h = _team_stats_for_upcoming(hist_df, home)
        a = _team_stats_for_upcoming(hist_df, away)

        feat_vec = {
            "HomeGoals_Avg_L5":    h["goals_avg_l5"],
            "HomeConceded_Avg_L5": h["conceded_avg_l5"],
            "HomeWinRate_L10":     h["win_rate_l10"],
            "HomeMomentum_L3":     h["momentum_l3"],
            "HomeRestDays":        h["rest_days"],
            "AwayGoals_Avg_L5":    a["goals_avg_l5"],
            "AwayConceded_Avg_L5": a["conceded_avg_l5"],
            "AwayWinRate_L10":     a["win_rate_l10"],
            "AwayMomentum_L3":     a["momentum_l3"],
            "AwayRestDays":        a["rest_days"],
            "ImpliedProb_HomeWin": 0.45,
            "ImpliedProb_Draw":    0.27,
            "ImpliedProb_AwayWin": 0.28,
        }

        X = np.array([[feat_vec.get(f, 0.0) for f in feature_names]])
        # Classes order: A=0, D=1, H=2 → proba indices match
        proba = model.predict_proba(X)[0]
        p_away, p_draw, p_home = proba[0], proba[1], proba[2]

        risk_score, conf_score = calculate_prediction_risk(p_home, p_draw, p_away)
        r_cat   = risk_category(risk_score)
        bet_tip = betting_recommendation(p_home, p_draw, p_away, risk_score)

        date_val = fix.get("Date", "")
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val)

        rows.append({
            "Date":          date_str,
            "Time":          fix.get("Time", ""),
            "HomeTeam":      home_raw,
            "AwayTeam":      away_raw,
            "Home Win %":    round(p_home * 100, 1),
            "Draw %":        round(p_draw * 100, 1),
            "Away Win %":    round(p_away * 100, 1),
            "Risk Score":    round(risk_score, 1),
            "Risk Category": r_cat,
            "Confidence %":  round(conf_score * 100, 1),
            "Betting Tip":   bet_tip,
            "_ph": p_home,
            "_pd": p_draw,
            "_pa": p_away,
        })

    return pd.DataFrame(rows)


# ── Prediction Risk Helpers ────────────────────────────────────────────────

def calculate_prediction_risk(
    home_prob: float, draw_prob: float, away_prob: float
) -> tuple[float, float]:
    """Return (risk_score 0-100, confidence_score 0-1)."""
    probs = np.clip([home_prob, draw_prob, away_prob], 1e-10, 1.0)
    entropy = -np.sum(probs * np.log(probs))
    confidence = 1.0 - (entropy / np.log(3))
    variance = float(np.sum((probs - 1 / 3) ** 2) / 3)
    risk_score = min(100.0, max(0.0, (1 - confidence) * 50 + variance * 50))
    return risk_score, confidence


def risk_category(score: float) -> str:
    if score > 47:
        return "🚨 Critical"
    if score > 40:
        return "🔴 High"
    if score > 30:
        return "🟡 Moderate"
    return "🟢 Low"


def betting_recommendation(
    home_prob: float, draw_prob: float, away_prob: float, risk_score: float
) -> str:
    max_prob = max(home_prob, draw_prob, away_prob)
    if max_prob >= 0.60 and risk_score <= 30:
        if home_prob == max_prob:
            return "💰 Bet Home Win"
        if draw_prob == max_prob:
            return "💰 Bet Draw"
        return "💰 Bet Away Win"
    if max_prob >= 0.50 and risk_score <= 50:
        if home_prob == max_prob:
            return "🤔 Consider Home"
        if draw_prob == max_prob:
            return "🤔 Consider Draw"
        return "🤔 Consider Away"
    return "❌ Avoid / Skip"


def color_risk_rows(row: pd.Series) -> list[str]:
    """Pandas Styler row-apply function — color-codes rows by risk category."""
    import streamlit as st
    dark = st.session_state.get("dark_mode", True)
    cat = str(row.get("Risk Category", ""))
    if dark:
        # Semi-transparent tints over dark canvas; light text
        if "Low" in cat:
            s = "background-color: rgba(46,204,113,0.15); color: #c8ffd4"
        elif "Moderate" in cat:
            s = "background-color: rgba(243,156,18,0.15); color: #ffe8a1"
        elif "High" in cat:
            s = "background-color: rgba(231,76,60,0.15); color: #ffc0bb"
        elif "Critical" in cat:
            s = "background-color: rgba(192,57,43,0.25); color: #ffc0bb"
        else:
            s = ""
    else:
        # Solid backgrounds fully override the dark canvas; dark text on light bg
        if "Low" in cat:
            s = "background-color: #d4edda; color: #0a3a1a"
        elif "Moderate" in cat:
            s = "background-color: #fff3cd; color: #3a2800"
        elif "High" in cat:
            s = "background-color: #cce5ff; color: #0a1e3a"
        elif "Critical" in cat:
            s = "background-color: #b8d9f8; color: #0a1428"
        else:
            s = "background-color: #f0f8ff; color: #0a1428"
    return [s] * len(row)


def generate_match_commentary(
    home: str,
    away: str,
    p_home: float,
    p_draw: float,
    p_away: float,
    risk_cat: str,
) -> str:
    top = max(p_home, p_draw, p_away)
    if p_home == top:
        label = f"{home} to win"
    elif p_away == top:
        label = f"{away} to win"
    else:
        label = "a draw"

    if top >= 0.60:
        conf = "confident on"
    elif top >= 0.45:
        conf = "leaning toward"
    else:
        conf = "uncertain — slight lean toward"

    tip = {
        "🟢 Low":      "Solid value play.",
        "🟡 Moderate": "Worth a small stake.",
        "🔴 High":     "High variance — smaller units.",
        "🚨 Critical": "Very uncertain — proceed with caution.",
    }.get(risk_cat, "")

    return f"Model is {conf} **{label}** at {top:.0%} confidence. {tip}"


# ── Standings ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def compute_la_liga_standings(
    df: pd.DataFrame,
    season_start: str = "2025-08-01",
) -> pd.DataFrame:
    current = df[df["MatchDate"] >= pd.Timestamp(season_start)].copy()
    if current.empty:
        return pd.DataFrame()

    records: list[dict] = []
    for _, row in current.iterrows():
        home, away = row["HomeTeam"], row["AwayTeam"]
        hg = int(row.get("FullTimeHomeGoals", 0) or 0)
        ag = int(row.get("FullTimeAwayGoals", 0) or 0)
        res = row.get("FullTimeResult", "")

        hw = hd = hl = aw = ad = al = 0
        if res == "H":
            hw = 1; al = 1
        elif res == "D":
            hd = 1; ad = 1
        elif res == "A":
            hl = 1; aw = 1

        records.append({"Team": home, "GF": hg, "GA": ag, "W": hw, "D": hd, "L": hl})
        records.append({"Team": away, "GF": ag, "GA": hg, "W": aw, "D": ad, "L": al})

    mdf = pd.DataFrame(records)
    t = mdf.groupby("Team").agg(
        Played=("GF", "count"),
        W=("W", "sum"),
        D=("D", "sum"),
        L=("L", "sum"),
        GF=("GF", "sum"),
        GA=("GA", "sum"),
    ).reset_index()
    t["GD"] = t["GF"] - t["GA"]
    t["Pts"] = t["W"] * 3 + t["D"]
    t = t.sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)
    t.insert(0, "#", t.index + 1)

    def _form(team: str) -> str:
        rows = mdf[mdf["Team"] == team].tail(5)
        icons = {"W": "🟢", "D": "🟡", "L": "🔴"}
        return " ".join(
            icons.get("W" if r["W"] else ("D" if r["D"] else "L"), "")
            for _, r in rows.iterrows()
        )

    t["Form"] = t["Team"].apply(_form)
    return t[["#", "Team", "Played", "W", "D", "L", "GF", "GA", "GD", "Pts", "Form"]]


# ── League Stats ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def compute_league_stats(csv_path: str, season_year: int) -> dict | None:
    if not path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path, low_memory=False)
    df["MatchDate"] = pd.to_datetime(df.get("Date", df.get("MatchDate", "")), dayfirst=True, errors="coerce")
    df = df[df["MatchDate"].dt.year == season_year]
    if df.empty:
        return None

    hg_col = "FTHG" if "FTHG" in df.columns else "FullTimeHomeGoals"
    ag_col = "FTAG" if "FTAG" in df.columns else "FullTimeAwayGoals"
    res_col = "FTR"  if "FTR"  in df.columns else "FullTimeResult"

    hg = pd.to_numeric(df.get(hg_col, 0), errors="coerce").fillna(0)
    ag = pd.to_numeric(df.get(ag_col, 0), errors="coerce").fillna(0)
    res = df.get(res_col, pd.Series(dtype=str))
    total = hg + ag
    n = len(df)
    if n == 0:
        return None

    return {
        "n":              n,
        "home_win_pct":   float((res == "H").sum() / n),
        "draw_pct":       float((res == "D").sum() / n),
        "away_win_pct":   float((res == "A").sum() / n),
        "avg_total_goals": float(total.mean()),
        "btts_pct":       float(((hg > 0) & (ag > 0)).sum() / n),
        "over_2_5_pct":   float((total > 2.5).sum() / n),
        "over_1_5_pct":   float((total > 1.5).sum() / n),
        "over_3_5_pct":   float((total > 3.5).sum() / n),
        "clean_sheet_pct": float(((hg == 0) | (ag == 0)).sum() / n),
    }


# ── Display Helpers ────────────────────────────────────────────────────────

def get_dataframe_height(
    df: pd.DataFrame,
    row_height: int = 35,
    header_height: int = 38,
    padding: int = 4,
    max_height: int = 600,
) -> int:
    """Compute a sensible fixed height for st.dataframe()."""
    h = len(df) * row_height + header_height + padding
    return min(h, max_height)


def render_table(df_or_styled, *, hide_index: bool = True, use_container_width: bool = True, height: int | None = None, **kwargs) -> None:
    """Render a DataFrame or Styler.

    Night mode  → st.dataframe() (interactive canvas, dark theme)
    Day mode    → styled HTML table (no canvas, fully CSS-controlled)
    """
    dark = st.session_state.get("dark_mode", True)
    if dark:
        st.dataframe(df_or_styled, hide_index=hide_index,
                     use_container_width=use_container_width, height=height, **kwargs)
        return

    # Day mode: render as HTML so CSS can control all cell colours
    if isinstance(df_or_styled, pd.io.formats.style.Styler):
        try:
            html_str = df_or_styled.hide(axis="index").to_html()
        except TypeError:
            html_str = df_or_styled.to_html()
    else:
        html_str = df_or_styled.to_html(index=(not hide_index))

    style = "overflow-x:auto; max-height:{}px; overflow-y:auto;".format(height) if height else "overflow-x:auto;"
    st.markdown(f'<div class="lt-tbl" style="{style}">{html_str}</div>', unsafe_allow_html=True)


def next_match_countdown(upcoming_df: pd.DataFrame) -> str | None:
    """Return a formatted countdown string for the next upcoming fixture."""
    if upcoming_df is None or upcoming_df.empty:
        return None
    try:
        df = upcoming_df.copy()
        df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        future = df[df["_dt"] > pd.Timestamp.now()].sort_values("_dt")
        if future.empty:
            return None
        nxt = future.iloc[0]
        delta = nxt["_dt"] - pd.Timestamp.now()
        d  = delta.days
        h  = delta.seconds // 3600
        m  = (delta.seconds % 3600) // 60
        home = nxt.get("HomeTeam", "?")
        away = nxt.get("AwayTeam", "?")
        return f"⏱️ Next: **{home} vs {away}**\n{d}d {h}h {m}m"
    except Exception:
        return None
