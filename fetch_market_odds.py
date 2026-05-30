"""Fetch append-only market odds snapshots from odds-api.io.

This complements fetch_odds.py. The existing odds.csv remains the simple app
view for current 1X2 odds, while this script preserves timestamped snapshots
for opener/latest/closing-line and market-movement features.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import fetch_odds
from team_name_mapping import normalize_dataframe_teams

SNAPSHOT_PATH = Path("data_files/raw/market_odds_snapshots.csv")
FEATURE_PATH = Path("data_files/model_features/market_features.csv")

SNAPSHOT_COLUMNS = [
    "SnapshotTime",
    "Provider",
    "EventId",
    "Date",
    "HomeTeam",
    "AwayTeam",
    "Bookmaker",
    "Market",
    "Line",
    "Outcome",
    "Odds",
    "ImpliedProbability",
]

FEATURE_COLUMNS = [
    "Date",
    "HomeTeam",
    "AwayTeam",
    "MarketConsensusHome",
    "MarketConsensusDraw",
    "MarketConsensusAway",
    "MarketMarginConsensus",
    "MarketHomeMove",
    "MarketDrawMove",
    "MarketAwayMove",
    "TotalGoalsLine",
    "OverProb",
    "UnderProb",
    "BTTSYesProb",
    "BTTSNoProb",
    "SnapshotCount",
    "LatestSnapshotTime",
]


def _ensure_file(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def _decimal_to_prob(value: Any) -> float | None:
    try:
        odds = float(value)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return 1.0 / odds


def _market_name(raw_name: str) -> str | None:
    name = raw_name.strip().lower()
    if name in {"ml", "moneyline", "match winner", "1x2", "h2h"}:
        return "1X2"
    if name in {"totals", "total", "over/under", "over under"}:
        return "Totals"
    if name in {"spread", "spreads", "handicap", "asian handicap"}:
        return "Spread"
    if name in {"btts", "both teams to score", "both teams score"}:
        return "BTTS"
    return None


def _append_row(
    rows: list[dict[str, Any]],
    *,
    snapshot_time: str,
    event_id: Any,
    date: str,
    home: str,
    away: str,
    bookmaker: str,
    market: str,
    line: Any,
    outcome: str,
    odds: Any,
) -> None:
    price = fetch_odds._float_or_none(odds)
    implied = _decimal_to_prob(price)
    if price is None or implied is None:
        return
    rows.append({
        "SnapshotTime": snapshot_time,
        "Provider": "odds-api.io",
        "EventId": event_id,
        "Date": date,
        "HomeTeam": home,
        "AwayTeam": away,
        "Bookmaker": bookmaker,
        "Market": market,
        "Line": line,
        "Outcome": outcome,
        "Odds": price,
        "ImpliedProbability": round(implied, 6),
    })


def _extract_market_rows(
    odds: dict[str, Any],
    event: dict[str, Any],
    snapshot_time: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event_id = odds.get("id") or event.get("id")
    home = odds.get("home") or event.get("home") or event.get("homeTeam")
    away = odds.get("away") or event.get("away") or event.get("awayTeam")
    date = str(odds.get("date") or event.get("date") or event.get("commence_time") or "")[:10]

    for bookmaker, markets in (odds.get("bookmakers") or {}).items():
        for raw_market in markets or []:
            market = _market_name(str(raw_market.get("name", "")))
            if not market:
                continue
            for item in raw_market.get("odds") or []:
                if market == "1X2":
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line="",
                        outcome="Home",
                        odds=item.get("home"),
                    )
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line="",
                        outcome="Draw",
                        odds=item.get("draw") or item.get("tie") or item.get("x"),
                    )
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line="",
                        outcome="Away",
                        odds=item.get("away"),
                    )
                elif market == "Totals":
                    line = item.get("hdp") or item.get("line")
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line=line,
                        outcome="Over",
                        odds=item.get("over"),
                    )
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line=line,
                        outcome="Under",
                        odds=item.get("under"),
                    )
                elif market == "Spread":
                    line = item.get("hdp") or item.get("line")
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line=line,
                        outcome="Home",
                        odds=item.get("home"),
                    )
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line=line,
                        outcome="Away",
                        odds=item.get("away"),
                    )
                elif market == "BTTS":
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line="",
                        outcome="Yes",
                        odds=item.get("yes") or item.get("home"),
                    )
                    _append_row(
                        rows,
                        snapshot_time=snapshot_time,
                        event_id=event_id,
                        date=date,
                        home=home,
                        away=away,
                        bookmaker=bookmaker,
                        market=market,
                        line="",
                        outcome="No",
                        odds=item.get("no") or item.get("away"),
                    )
    return rows


def _main_totals_rows(df: pd.DataFrame) -> pd.DataFrame:
    totals = df[df["Market"].eq("Totals")].copy()
    if totals.empty:
        return totals
    totals["LineNum"] = pd.to_numeric(totals["Line"], errors="coerce")
    totals = totals.dropna(subset=["LineNum"])
    if totals.empty:
        return totals
    main_line = (
        totals.groupby(["Date", "HomeTeam", "AwayTeam"])["LineNum"]
        .agg(lambda x: x.value_counts().index[0])
        .reset_index(name="MainLine")
    )
    totals = totals.merge(main_line, on=["Date", "HomeTeam", "AwayTeam"], how="inner")
    return totals[np.isclose(totals["LineNum"], totals["MainLine"])]


def build_market_features(snapshot_path: Path = SNAPSHOT_PATH) -> pd.DataFrame:
    _ensure_file(FEATURE_PATH, FEATURE_COLUMNS)
    if not snapshot_path.exists():
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    df = pd.read_csv(snapshot_path)
    if df.empty:
        features = pd.DataFrame(columns=FEATURE_COLUMNS)
        features.to_csv(FEATURE_PATH, index=False)
        return features

    df["SnapshotTime"] = pd.to_datetime(df["SnapshotTime"], errors="coerce", utc=True)
    df["ImpliedProbability"] = pd.to_numeric(df["ImpliedProbability"], errors="coerce")
    df = df.dropna(subset=["SnapshotTime", "ImpliedProbability"])
    keys = ["Date", "HomeTeam", "AwayTeam"]

    latest = (
        df.sort_values("SnapshotTime")
        .groupby(keys + ["Market", "Line", "Outcome", "Bookmaker"], dropna=False)
        .tail(1)
    )
    rows: list[dict[str, Any]] = []
    for match_key, match_df in latest.groupby(keys, dropna=False):
        date, home, away = match_key
        row: dict[str, Any] = {
            "Date": date,
            "HomeTeam": home,
            "AwayTeam": away,
            "SnapshotCount": int(df[(df["Date"].eq(date)) & (df["HomeTeam"].eq(home)) & (df["AwayTeam"].eq(away))]["SnapshotTime"].nunique()),
            "LatestSnapshotTime": match_df["SnapshotTime"].max().isoformat(),
        }

        one_x_two = match_df[match_df["Market"].eq("1X2")]
        if not one_x_two.empty:
            consensus = one_x_two.groupby("Outcome")["ImpliedProbability"].mean()
            total = consensus.reindex(["Home", "Draw", "Away"]).sum()
            if total > 0:
                row["MarketConsensusHome"] = round(float(consensus.get("Home", np.nan) / total), 4)
                row["MarketConsensusDraw"] = round(float(consensus.get("Draw", np.nan) / total), 4)
                row["MarketConsensusAway"] = round(float(consensus.get("Away", np.nan) / total), 4)
                row["MarketMarginConsensus"] = round(float((total - 1) * 100), 2)

            history = df[
                df["Date"].eq(date)
                & df["HomeTeam"].eq(home)
                & df["AwayTeam"].eq(away)
                & df["Market"].eq("1X2")
            ].sort_values("SnapshotTime")
            opener = history.groupby("Outcome").head(1).groupby("Outcome")["ImpliedProbability"].mean()
            latest_probs = one_x_two.groupby("Outcome")["ImpliedProbability"].mean()
            for outcome, col in [("Home", "MarketHomeMove"), ("Draw", "MarketDrawMove"), ("Away", "MarketAwayMove")]:
                if outcome in opener and outcome in latest_probs:
                    row[col] = round(float(latest_probs[outcome] - opener[outcome]), 4)

        totals = _main_totals_rows(match_df)
        if not totals.empty:
            row["TotalGoalsLine"] = round(float(pd.to_numeric(totals["Line"], errors="coerce").dropna().mean()), 2)
            total_probs = totals.groupby("Outcome")["ImpliedProbability"].mean()
            denom = total_probs.reindex(["Over", "Under"]).sum()
            if denom > 0:
                row["OverProb"] = round(float(total_probs.get("Over", np.nan) / denom), 4)
                row["UnderProb"] = round(float(total_probs.get("Under", np.nan) / denom), 4)

        btts = match_df[match_df["Market"].eq("BTTS")]
        if not btts.empty:
            btts_probs = btts.groupby("Outcome")["ImpliedProbability"].mean()
            denom = btts_probs.reindex(["Yes", "No"]).sum()
            if denom > 0:
                row["BTTSYesProb"] = round(float(btts_probs.get("Yes", np.nan) / denom), 4)
                row["BTTSNoProb"] = round(float(btts_probs.get("No", np.nan) / denom), 4)
        rows.append(row)

    features = pd.DataFrame(rows)
    for col in FEATURE_COLUMNS:
        if col not in features.columns:
            features[col] = np.nan
    features = features[FEATURE_COLUMNS]
    FEATURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURE_PATH, index=False)
    return features


def fetch_market_odds() -> pd.DataFrame:
    _ensure_file(SNAPSHOT_PATH, SNAPSHOT_COLUMNS)
    league = fetch_odds._discover_odds_api_io_league()
    bookmakers = fetch_odds._odds_api_io_bookmakers()
    events = fetch_odds._fetch_odds_api_io_events(league)
    snapshot_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    rows: list[dict[str, Any]] = []
    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue
        odds, _ = fetch_odds._odds_api_io_get(
            "odds",
            {"eventId": event_id, "bookmakers": ",".join(bookmakers)},
        )
        rows.extend(_extract_market_rows(odds, event, snapshot_time))

    new_df = pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)
    if not new_df.empty:
        new_df = normalize_dataframe_teams(new_df)
        existing = pd.read_csv(SNAPSHOT_PATH) if SNAPSHOT_PATH.exists() else pd.DataFrame(columns=SNAPSHOT_COLUMNS)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=SNAPSHOT_COLUMNS)
        combined.to_csv(SNAPSHOT_PATH, index=False)

    features = build_market_features(SNAPSHOT_PATH)
    print(f"Fetched {len(new_df)} market snapshot rows across {len(events)} events.")
    print(f"Built {len(features)} market feature rows -> {FEATURE_PATH}")
    return new_df


if __name__ == "__main__":
    fetch_market_odds()
