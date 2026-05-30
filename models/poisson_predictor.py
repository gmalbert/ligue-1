"""Dixon-Coles Poisson model for Ligue 1 goal and scoreline prediction.

Provides:
    compute_team_strengths(df)  → DataFrame of attack/defense multipliers
    predict_match_poisson(...)  → dict with probabilities and expected goals

Output keys: HomeWinProb, DrawProb, AwayWinProb,
             ExpectedHomeGoals, ExpectedAwayGoals,
             MostLikelyScore, Over2_5Prob, BTTSProb, ScoreMatrix
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

LA_LIGA_AVG_HOME_GOALS = 1.45
LA_LIGA_AVG_AWAY_GOALS = 1.12


def compute_team_strengths(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute attack and defense strength multipliers for every team.
    Uses historical home/away goal averages relative to the league mean.

    Returns a DataFrame with columns:
        Team, HomeAttack, HomeDefense, AwayAttack, AwayDefense
    """
    df = df.copy()
    df["FullTimeHomeGoals"] = pd.to_numeric(df.get("FullTimeHomeGoals"), errors="coerce").fillna(0)
    df["FullTimeAwayGoals"] = pd.to_numeric(df.get("FullTimeAwayGoals"), errors="coerce").fillna(0)

    league_home_avg = df["FullTimeHomeGoals"].mean() or LA_LIGA_AVG_HOME_GOALS
    league_away_avg = df["FullTimeAwayGoals"].mean() or LA_LIGA_AVG_AWAY_GOALS

    records = []
    all_teams = set(df["HomeTeam"].dropna()) | set(df["AwayTeam"].dropna())

    for team in all_teams:
        home_m = df[df["HomeTeam"] == team]
        away_m = df[df["AwayTeam"] == team]

        if home_m.empty or away_m.empty:
            continue

        home_attack  = home_m["FullTimeHomeGoals"].mean() / league_home_avg
        home_defense = home_m["FullTimeAwayGoals"].mean() / league_away_avg
        away_attack  = away_m["FullTimeAwayGoals"].mean() / league_away_avg
        away_defense = away_m["FullTimeHomeGoals"].mean() / league_home_avg

        records.append({
            "Team":         team,
            "HomeAttack":   round(home_attack,  4),
            "HomeDefense":  round(home_defense, 4),
            "AwayAttack":   round(away_attack,  4),
            "AwayDefense":  round(away_defense, 4),
        })

    return pd.DataFrame(records)


def predict_match_poisson(
    home_team: str,
    away_team: str,
    strengths: pd.DataFrame,
    max_goals: int = 6,
) -> dict:
    """
    Predict match outcome using a Poisson model.

    Returns a dict with:
        HomeWinProb, DrawProb, AwayWinProb,
        ExpectedHomeGoals, ExpectedAwayGoals,
        MostLikelyScore (e.g. "1–0"),
        Over2_5Prob, BTTSProb,
        ScoreMatrix (numpy array)
    """
    home_row = strengths[strengths["Team"] == home_team]
    away_row = strengths[strengths["Team"] == away_team]

    if home_row.empty or away_row.empty:
        exp_home = LA_LIGA_AVG_HOME_GOALS
        exp_away = LA_LIGA_AVG_AWAY_GOALS
    else:
        h = home_row.iloc[0]
        a = away_row.iloc[0]
        exp_home = h["HomeAttack"] * a["AwayDefense"] * LA_LIGA_AVG_HOME_GOALS
        exp_away = a["AwayAttack"] * h["HomeDefense"] * LA_LIGA_AVG_AWAY_GOALS

    # Build scoreline probability matrix
    home_pmf = poisson.pmf(range(max_goals + 1), exp_home)
    away_pmf = poisson.pmf(range(max_goals + 1), exp_away)
    score_matrix = np.outer(home_pmf, away_pmf)

    home_win = float(np.tril(score_matrix, -1).sum())
    draw     = float(np.trace(score_matrix))
    away_win = float(np.triu(score_matrix, 1).sum())

    # Most likely exact score
    best_i, best_j = np.unravel_index(score_matrix.argmax(), score_matrix.shape)

    # Over 2.5 goals
    over_2_5 = 1.0 - sum(
        score_matrix[i, j]
        for i in range(max_goals + 1)
        for j in range(max_goals + 1)
        if i + j <= 2
    )

    # Both teams to score
    btts = 1.0 - float(
        score_matrix[:, 0].sum()
        + score_matrix[0, :].sum()
        - score_matrix[0, 0]
    )

    return {
        "HomeWinProb":       round(home_win,  4),
        "DrawProb":          round(draw,      4),
        "AwayWinProb":       round(away_win,  4),
        "ExpectedHomeGoals": round(exp_home,  2),
        "ExpectedAwayGoals": round(exp_away,  2),
        "MostLikelyScore":   f"{best_i}–{best_j}",
        "Over2_5Prob":       round(over_2_5,  4),
        "BTTSProb":          round(btts,      4),
        "ScoreMatrix":       score_matrix,
    }
