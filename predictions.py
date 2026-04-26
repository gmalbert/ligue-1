"""La Liga Linea — Streamlit app entry point.

Run with:
    streamlit run predictions.py
"""

import os
from os import path

import streamlit as st

# ── Page config — must be first Streamlit call ─────────────────────────────
st.set_page_config(
    page_title="La Liga Linea",
    page_icon="🇪🇸",
    layout="wide",
    initial_sidebar_state="expanded",
)

from footer import add_betting_oracle_footer  # noqa: E402
from themes import apply_theme  # noqa: E402
from utils import load_upcoming_fixtures, next_match_countdown  # noqa: E402

# ── Mode must be set before apply_theme() ─────────────────────────────────
# Auto-detect from browser clock via ?hour= query param (injected by JS below).
# Only auto-set when the user hasn't manually toggled this session.
_hour_param = st.query_params.get("hour", None)
if not st.session_state.get("dark_mode_manual", False):
    if _hour_param is not None:
        try:
            _h = int(_hour_param)
            st.session_state["dark_mode"] = not (6 <= _h < 20)
        except ValueError:
            st.session_state.setdefault("dark_mode", True)
    else:
        st.session_state.setdefault("dark_mode", True)

# Always inject JS so a stale ?hour from a previous session is updated on
# every page load. JS only does a location.replace() when the value changes.
st.iframe(
    """
    <script>
    const h = new Date().getHours();
    const url = new URL(window.parent.location.href);
    const existing = url.searchParams.get('hour');
    if (existing === null || parseInt(existing, 10) !== h) {
        url.searchParams.set('hour', h);
        window.parent.location.replace(url.toString());
    }
    </script>
    """,
    height=10,
)

# ── Sidebar ────────────────────────────────────────────────────────────────
_logo = path.join("data_files", "logo.png")
if path.exists(_logo):
    st.sidebar.image(_logo, width=220)
else:
    st.sidebar.markdown("## 🇪🇸 La Liga Linea")

st.sidebar.markdown("**La Liga Predictions & Analysis**")
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

st.sidebar.divider()

# Night / Day toggle
_mode_label = "☀️ Switch to Day" if st.session_state["dark_mode"] else "🌙 Switch to Night"
if st.sidebar.button(_mode_label, width='stretch'):
    st.session_state["dark_mode"] = not st.session_state["dark_mode"]
    st.session_state["dark_mode_manual"] = True  # suppress auto-override for this session
    st.rerun()

apply_theme()

st.sidebar.divider()

st.sidebar.caption("Data: football-data.org · FBref · The Odds API")
st.sidebar.caption("© Betting Oracle")

# ── Navigation ─────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "⚽ La Liga": [
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

pg.run()

add_betting_oracle_footer()
