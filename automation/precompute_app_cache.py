"""Precompute app-facing cache artifacts for Ligue Odds.

This runs after the nightly data/model pipeline so Streamlit pages can read
small prepared files instead of recomputing common views on first user load.

Outputs:
    data_files/app_cache/league_stats.json
    data_files/app_cache/standings.csv
    data_files/app_cache/team_form.csv
    data_files/app_cache/feature_importance.csv
    data_files/app_cache/manifest.json
"""

from __future__ import annotations

import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

HIST_PATH = ROOT / "data_files" / "combined_historical_data.csv"
METRICS_PATH = ROOT / "models" / "metrics.json"
MODEL_PATH = ROOT / "models" / "ensemble_model.pkl"
CACHE_DIR = ROOT / "data_files" / "app_cache"


def _season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[2:]}"


def _normalise_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    for col in ["FullTimeHomeGoals", "FullTimeAwayGoals"]:
        df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0)
    return df.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam"])


def _league_stats_for_year(df: pd.DataFrame, season_year: int) -> dict | None:
    current = df[df["MatchDate"].dt.year == season_year]
    if current.empty:
        return None

    hg = pd.to_numeric(current.get("FullTimeHomeGoals", 0), errors="coerce").fillna(0)
    ag = pd.to_numeric(current.get("FullTimeAwayGoals", 0), errors="coerce").fillna(0)
    res = current.get("FullTimeResult", pd.Series(dtype=str))
    total = hg + ag
    n = len(current)
    if n == 0:
        return None

    return {
        "n": int(n),
        "home_win_pct": float((res == "H").sum() / n),
        "draw_pct": float((res == "D").sum() / n),
        "away_win_pct": float((res == "A").sum() / n),
        "avg_total_goals": float(total.mean()),
        "btts_pct": float(((hg > 0) & (ag > 0)).sum() / n),
        "over_2_5_pct": float((total > 2.5).sum() / n),
        "over_1_5_pct": float((total > 1.5).sum() / n),
        "over_3_5_pct": float((total > 3.5).sum() / n),
        "clean_sheet_pct": float(((hg == 0) | (ag == 0)).sum() / n),
    }


def _compute_standings(df: pd.DataFrame, season_start: str) -> pd.DataFrame:
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
            hw = 1
            al = 1
        elif res == "D":
            hd = 1
            ad = 1
        elif res == "A":
            hl = 1
            aw = 1

        records.append({"Team": home, "GF": hg, "GA": ag, "W": hw, "D": hd, "L": hl})
        records.append({"Team": away, "GF": ag, "GA": hg, "W": aw, "D": ad, "L": al})

    mdf = pd.DataFrame(records)
    table = mdf.groupby("Team").agg(
        Played=("GF", "count"),
        W=("W", "sum"),
        D=("D", "sum"),
        L=("L", "sum"),
        GF=("GF", "sum"),
        GA=("GA", "sum"),
    ).reset_index()
    table["GD"] = table["GF"] - table["GA"]
    table["Pts"] = table["W"] * 3 + table["D"]
    table = table.sort_values(["Pts", "GD", "GF"], ascending=False).reset_index(drop=True)
    table.insert(0, "#", table.index + 1)

    def _form(team: str) -> str:
        rows = mdf[mdf["Team"] == team].tail(5)
        icons = {"W": "🟢", "D": "🟡", "L": "🔴"}
        return " ".join(
            icons.get("W" if r["W"] else ("D" if r["D"] else "L"), "")
            for _, r in rows.iterrows()
        )

    table["Form"] = table["Team"].apply(_form)
    return table[["#", "Team", "Played", "W", "D", "L", "GF", "GA", "GD", "Pts", "Form"]]


def _write_league_stats(df: pd.DataFrame) -> None:
    years = sorted(df["MatchDate"].dt.year.dropna().astype(int).unique())
    payload = {
        str(year): stats
        for year in years
        if (stats := _league_stats_for_year(df, year)) is not None
    }
    (CACHE_DIR / "league_stats.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Cached league stats for {len(payload)} years")


def _write_standings(df: pd.DataFrame) -> None:
    cache_file = CACHE_DIR / "standings.csv"
    if cache_file.exists():
        cache_file.unlink()

    max_year = max(datetime.now().year + 1, int(df["MatchDate"].dt.year.max()) + 1)
    frames = []
    for start_year in range(2015, max_year):
        season_start = f"{start_year}-08-01"
        table = _compute_standings(df, season_start=season_start)
        if table.empty:
            continue
        table = table.copy()
        table.insert(0, "SeasonStart", season_start)
        table.insert(0, "Season", _season_label(start_year))
        frames.append(table)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(cache_file, index=False)
    print(f"Cached standings rows: {len(out)}")


def _write_team_form(df: pd.DataFrame) -> None:
    teams = sorted(set(df["HomeTeam"].dropna()) | set(df["AwayTeam"].dropna()))
    rows = []
    for team in teams:
        home_m = df[df["HomeTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
            Won=lambda d: d["FullTimeResult"] == "H",
            Drew=lambda d: d["FullTimeResult"] == "D",
        )
        away_m = df[df["AwayTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
            Won=lambda d: d["FullTimeResult"] == "A",
            Drew=lambda d: d["FullTimeResult"] == "D",
        )
        last = pd.concat([home_m, away_m]).sort_values("MatchDate").tail(5)
        form_str = "".join("W" if r["Won"] else ("D" if r["Drew"] else "L") for _, r in last.iterrows())
        pts_l5 = sum(3 if c == "W" else (1 if c == "D" else 0) for c in form_str)
        rows.append({"Team": team, "Form": form_str, "Pts (L5)": pts_l5})

    out = pd.DataFrame(rows).sort_values("Pts (L5)", ascending=False).reset_index(drop=True)
    out.insert(0, "#", out.index + 1)
    out.to_csv(CACHE_DIR / "team_form.csv", index=False)
    print(f"Cached team form rows: {len(out)}")


def _write_feature_importance() -> None:
    if not METRICS_PATH.exists() or not MODEL_PATH.exists():
        print("Feature importance skipped: metrics/model missing")
        return

    with open(METRICS_PATH) as f:
        metrics = json.load(f)
    feat_names = metrics.get("feature_cols", [])
    if not feat_names:
        print("Feature importance skipped: no feature_cols in metrics")
        return

    with open(MODEL_PATH, "rb") as f:
        ensemble = pickle.load(f)
    xgb_est = getattr(ensemble, "named_estimators_", {}).get("xgb")
    if xgb_est is None or not hasattr(xgb_est, "feature_importances_"):
        print("Feature importance skipped: xgb importances unavailable")
        return

    importances = xgb_est.feature_importances_
    n = min(len(importances), len(feat_names))
    out = pd.DataFrame({
        "Feature": feat_names[:n],
        "Importance": importances[:n],
    }).sort_values("Importance", ascending=True)
    out.to_csv(CACHE_DIR / "feature_importance.csv", index=False)
    print(f"Cached feature importances: {len(out)}")


def main() -> None:
    if not HIST_PATH.exists():
        raise SystemExit(f"{HIST_PATH} not found. Run fetch_historical_csvs.py first.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df = _normalise_history(pd.read_csv(HIST_PATH, low_memory=False))

    _write_league_stats(df)
    _write_standings(df)
    _write_team_form(df)
    _write_feature_importance()

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(HIST_PATH.relative_to(ROOT)),
    }
    (CACHE_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"App cache written to {CACHE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
