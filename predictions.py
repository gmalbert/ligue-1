"""Ligue Odds — Streamlit app entry point.

Run with:
    streamlit run predictions.py
"""

from os import path
from datetime import datetime

import streamlit as st

# ── Page config — must be first Streamlit call ─────────────────────────────
st.set_page_config(
    page_title="Ligue Odds",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

from footer import add_betting_oracle_footer  # noqa: E402
from themes import apply_theme  # noqa: E402
from utils import load_upcoming_fixtures, next_match_countdown  # noqa: E402

_logo = path.join("data_files", "logo.png")

# ── Mode must be set before apply_theme() ─────────────────────────────────
# Browser-local time is sent to Streamlit via a query param. First paint uses
# night mode until the browser reports its hour, then the page reruns.
_hour_param = st.query_params.get("browser_hour", None)
try:
    _browser_hour = int(_hour_param) if _hour_param is not None else None
except ValueError:
    _browser_hour = None

_theme_hour = _browser_hour if _browser_hour is not None else datetime.now().hour
st.session_state["dark_mode"] = not (6 <= _theme_hour < 20)

st.iframe(
    """
    <script>
    const h = new Date().getHours();
    const url = new URL(window.parent.location.href);
    const existing = url.searchParams.get('browser_hour');
    if (existing === null || parseInt(existing, 10) !== h) {
        url.searchParams.set('browser_hour', h);
        window.parent.location.replace(url.toString());
    }
    </script>
    """,
    height=1,
    tab_index=-1,
)

# ── Navigation ─────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "⚽ Ligue 1": [
            st.Page(
                "pages/predictions_tab.py",
                title="Predictions",
                icon="🎯",
                default=True,
            ),
            st.Page("pages/fixtures.py",       title="Fixtures & Standings", icon="🗓️"),
            st.Page("pages/statistics.py",      title="Statistics",           icon="📊"),
            st.Page("pages/team_deep_dive.py",  title="Team Deep Dive",       icon="🔬"),
            st.Page("pages/raw_data.py",        title="Raw Data",             icon="📁"),
        ],
        "💰 Betting": [
            st.Page("pages/markets.py",     title="Markets",    icon="📈"),
            st.Page("pages/best_bets.py",   title="Best Bets",  icon="💰"),
            st.Page("pages/performance.py", title="Performance", icon="📈"),
        ],
    }
)

# ── Sidebar ────────────────────────────────────────────────────────────────
if pg.url_path and path.exists(_logo):
    st.sidebar.image(_logo, width=220)
else:
    st.sidebar.markdown("## Ligue Odds")

if pg.url_path:
    st.sidebar.markdown("**Ligue 1 predictions & analysis**")
st.sidebar.divider()

# Next-match countdown
_fix_path = "data_files/upcoming_fixtures.csv"
if path.exists(_fix_path):
    _upcoming = load_upcoming_fixtures(_fix_path)
    _cd = next_match_countdown(_upcoming)
    if _cd:
        st.sidebar.info(_cd)

# Season selector — stored in session state so all pages can read it
_seasons = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]
if "selected_season" not in st.session_state:
    st.session_state["selected_season"] = _seasons[0]

st.session_state["selected_season"] = st.sidebar.selectbox(
    "Season",
    _seasons,
    index=_seasons.index(st.session_state.get("selected_season", _seasons[0])),
)

apply_theme()

st.sidebar.divider()

# st.sidebar.caption("Data: football-data.org · FBref · The Odds API")
# st.sidebar.caption("© Betting Oracle")

pg.run()

add_betting_oracle_footer()
