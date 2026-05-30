"""Statistics page — xG rankings, team form, H2H, Coupe de France congestion, feature importance."""

from __future__ import annotations
import json
from os import path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import get_dataframe_height, render_table, load_historical_data
from themes import plotly_theme

HIST_PATH     = "data_files/combined_historical_data.csv"
METRICS_PATH  = "models/metrics.json"
BACKTEST_PATH = "models/backtest_results.json"
FEATURE_IMPORTANCE_PATH = "data_files/app_cache/feature_importance.csv"
TEAM_FORM_PATH = "data_files/app_cache/team_form.csv"

st.title("📊 Statistics")

if not path.exists(HIST_PATH):
    st.info("Historical data not yet available — data is refreshed nightly via GitHub Actions.")
    st.stop()

hist_df = load_historical_data(HIST_PATH)


# ── Feature Importance ────────────────────────────────────────────────────
st.subheader("🧠 Model Feature Importance")
if path.exists(FEATURE_IMPORTANCE_PATH):
    fi_df = pd.read_csv(FEATURE_IMPORTANCE_PATH)
    fig = px.bar(
        fi_df,
        x="Importance",
        y="Feature",
        orientation="h",
        title="XGBoost Feature Importances (Gain)",
        color="Importance",
        color_continuous_scale="reds",
    )
    fig.update_layout(coloraxis_showscale=False, yaxis_title=None)
    fig.update_layout(**plotly_theme())
    st.plotly_chart(fig, width='stretch')
elif path.exists(METRICS_PATH):
    with open(METRICS_PATH) as f:
        m = json.load(f)

    from utils import FEATURE_COLS as _FEATURE_COLS
    feat_names = m.get("feature_cols", []) or _FEATURE_COLS

    # Try to get XGBoost feature importances from the saved model
    try:
        import pickle
        with open("models/ensemble_model.pkl", "rb") as f:
            ensemble = pickle.load(f)

        # VotingClassifier.named_estimators_ is a dict {name: fitted_estimator}
        xgb_est = ensemble.named_estimators_.get("xgb")

        if xgb_est is not None and hasattr(xgb_est, "feature_importances_"):
            importances = xgb_est.feature_importances_
            n = min(len(importances), len(feat_names))
            fi_df = pd.DataFrame({
                "Feature":    feat_names[:n],
                "Importance": importances[:n],
            }).sort_values("Importance", ascending=True)

            fig = px.bar(
                fi_df,
                x="Importance",
                y="Feature",
                orientation="h",
                title="XGBoost Feature Importances (Gain)",
                color="Importance",
                color_continuous_scale="reds",
            )
            fig.update_layout(coloraxis_showscale=False, yaxis_title=None)
            fig.update_layout(**plotly_theme())
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Feature importance chart not available — model does not expose importances.")
    except Exception as _e:
        st.info(f"Feature importance chart not available — {_e}")
else:
    st.info("Model metrics not found — data is refreshed nightly.")

st.divider()


# ── Backtest Summary ──────────────────────────────────────────────────────
st.subheader("🧪 Backtest Summary")
if path.exists(BACKTEST_PATH):
    with open(BACKTEST_PATH) as f:
        bt = json.load(f)
    bc1, bc2, bc3, bc4 = st.columns(4)
    bc1.metric("Backtest Accuracy",  f"{bt.get('accuracy', 0):.1%}")
    bc2.metric("Market Accuracy",    f"{bt.get('market_accuracy', 0):.1%}")
    bc3.metric("Bets Placed",        bt.get("n_bets_placed", 0))
    bc4.metric("Flat-Stake ROI",     f"{bt.get('roi_pct', 0):+.1f}%")
    bc5, bc6, bc7, bc8 = st.columns(4)
    bc5.metric("Log Loss Edge", f"{bt.get('market_log_loss_delta', 0):+.3f}")
    bc6.metric("Calibration Error", f"{bt.get('calibration_error', 0):.3f}")
    bc7.metric("Draw Recall", f"{bt.get('draw_recall', 0):.1%}")
    clv = bt.get("closing_line_value_pct")
    bc8.metric("CLV", "N/A" if clv is None else f"{clv:+.2f}%")
    st.caption(
        f"Holdout season: {bt.get('holdout_season', '?')} · "
        f"Brier score: {bt.get('brier_score', 0):.4f}"
    )
    st.caption("Full details on the **📈 Performance** page.")
else:
    st.info("Backtest results not yet available — refreshed nightly.")

st.divider()


# ── xG Rankings ───────────────────────────────────────────────────────────
st.subheader("⚽ Team xG Rankings (FBref)")
fbref_path = "data_files/raw/fbref_team_xg.csv"
if path.exists(fbref_path):
    xg_df = pd.read_csv(fbref_path)
    xg_df = xg_df.sort_values("xG", ascending=False).reset_index(drop=True)
    xg_df.insert(0, "#", xg_df.index + 1)
    render_table(xg_df, hide_index=True, width='stretch',
                 height=get_dataframe_height(xg_df, max_height=500))
else:
    st.info("xG data not yet available — refreshed nightly.")

st.divider()


# ── Team Form ─────────────────────────────────────────────────────────────
st.subheader("📈 Recent Team Form (Last 5 Matches)")
icons = {"W": "🟢", "D": "🟡", "L": "🔴"}
all_teams = sorted(
    set(hist_df["HomeTeam"].dropna()) | set(hist_df["AwayTeam"].dropna())
)

if path.exists(TEAM_FORM_PATH):
    form_df = pd.read_csv(TEAM_FORM_PATH)
    form_df["Form"] = form_df["Form"].astype(str).apply(
        lambda form: " ".join(icons.get(c, c) for c in form)
    )
else:
    form_rows = []
    for team in all_teams:
        home_m = hist_df[hist_df["HomeTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
            Won=lambda d: (d["FullTimeResult"] == "H"),
            Drew=lambda d: (d["FullTimeResult"] == "D"),
        )
        away_m = hist_df[hist_df["AwayTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
            Won=lambda d: (d["FullTimeResult"] == "A"),
            Drew=lambda d: (d["FullTimeResult"] == "D"),
        )
        all_m = (
            pd.concat([home_m, away_m])
            .sort_values("MatchDate")
            .tail(5)
        )
        form_str = "".join("W" if r["Won"] else ("D" if r["Drew"] else "L") for _, r in all_m.iterrows())
        form_disp = " ".join(icons.get(c, c) for c in form_str)
        pts_l5 = sum(3 if c == "W" else (1 if c == "D" else 0) for c in form_str)
        form_rows.append({"Team": team, "Form": form_disp, "Pts (L5)": pts_l5})

    form_df = (
        pd.DataFrame(form_rows)
        .sort_values("Pts (L5)", ascending=False)
        .reset_index(drop=True)
    )
    form_df.insert(0, "#", form_df.index + 1)
render_table(
    form_df[["#", "Team", "Form", "Pts (L5)"]],
    hide_index=True,
    width='stretch',
    height=get_dataframe_height(form_df, max_height=680),
)

st.divider()


# ── Head-to-Head Analyzer ─────────────────────────────────────────────────
st.subheader("🏆 Head-to-Head Analyzer")
hc1, hc2 = st.columns(2)
with hc1:
    t1 = st.selectbox("Team 1", all_teams, key="h2h_t1")
with hc2:
    t2 = st.selectbox("Team 2", [t for t in all_teams if t != t1], key="h2h_t2")

if st.button("🔍 Analyse H2H", width='stretch'):
    mask = (
        ((hist_df["HomeTeam"] == t1) & (hist_df["AwayTeam"] == t2)) |
        ((hist_df["HomeTeam"] == t2) & (hist_df["AwayTeam"] == t1))
    )
    h2h = hist_df[mask].sort_values("MatchDate", ascending=False).head(10)
    if h2h.empty:
        st.info(f"No recorded meetings between {t1} and {t2}.")
    else:
        t1_wins = (
            ((h2h["HomeTeam"] == t1) & (h2h["FullTimeResult"] == "H")).sum() +
            ((h2h["AwayTeam"] == t1) & (h2h["FullTimeResult"] == "A")).sum()
        )
        t2_wins = (
            ((h2h["HomeTeam"] == t2) & (h2h["FullTimeResult"] == "H")).sum() +
            ((h2h["AwayTeam"] == t2) & (h2h["FullTimeResult"] == "A")).sum()
        )
        draws = (h2h["FullTimeResult"] == "D").sum()

        hc1r, hc2r, hc3r = st.columns(3)
        hc1r.metric(f"{t1} Wins",  int(t1_wins))
        hc2r.metric("Draws",       int(draws))
        hc3r.metric(f"{t2} Wins",  int(t2_wins))

        show_cols = ["MatchDate", "HomeTeam", "FullTimeHomeGoals",
                     "FullTimeAwayGoals", "AwayTeam", "FullTimeResult"]
        show_cols = [c for c in show_cols if c in h2h.columns]
        render_table(h2h[show_cols].rename(columns={
            "MatchDate": "Date", "FullTimeHomeGoals": "HG",
            "FullTimeAwayGoals": "AG", "FullTimeResult": "FTR",
        }), hide_index=True, width='stretch')

st.divider()


# ── Coupe de France Congestion ─────────────────────────────────────────────
st.subheader("🏆 Coupe de France Congestion Flag")
copa_path = "data_files/raw/copa_fixtures.csv"
if path.exists(copa_path):
    copa_df = pd.read_csv(copa_path)
    copa_df["MatchDate"] = pd.to_datetime(copa_df["MatchDate"], errors="coerce")
    recent_copa = copa_df[
        copa_df["MatchDate"] >= (pd.Timestamp.now() - pd.Timedelta(days=7))
    ]
    if recent_copa.empty:
        st.success("No teams played Coupe de France in the last 7 days.")
    else:
        flagged = recent_copa["TeamName"].nunique() if "TeamName" in recent_copa.columns else "?"
        st.warning(f"⚠️ {flagged} team(s) played Coupe de France in the last 7 days.")
        render_table(recent_copa, hide_index=True, width='stretch', height=get_dataframe_height(recent_copa))
else:
    st.info("Coupe de France data not yet available — refreshed nightly.")
