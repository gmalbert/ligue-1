import streamlit as st

# ── Two fixed themes ──────────────────────────────────────────────────────
_NIGHT = dict(
    main_bg="#0e1117",  sidebar_bg="#1a1a2e",  sidebar_text="#fafafa",
    text="#fafafa",     accent="#EF0000",
    df_header_bg="#1a1a2e", df_header_text="#fafafa",
    card_bg="#262730",  input_bg="#262730",    input_text="#fafafa",
    btn_bg="#EF0000",   btn_text="#ffffff",
    cell_bg="#1e1e2e",  cell_text="#fafafa",
    border="#3a3a5a",   alert_bg="#1e2540",
)

_SKY = dict(
    main_bg="#f0f8ff",  sidebar_bg="#4488cc",  sidebar_text="#ffffff",
    text="#0a1428",     accent="#1a5fa8",
    df_header_bg="#c8dff5", df_header_text="#0a1428",
    card_bg="#ddeeff",  input_bg="#ffffff",    input_text="#0a1428",
    btn_bg="#1a5fa8",   btn_text="#ffffff",
    cell_bg="#f0f8ff",  cell_text="#0a1428",
    border="#7ab8e8",   alert_bg="#e0f0ff",
)

# ── CSS template ──────────────────────────────────────────────────────────
_CSS = """
/* ── Top header bar ─────────────────────────────────── */
[data-testid="stHeader"],
header[data-testid="stHeader"],
[data-testid="stHeader"] > div,
[data-testid="stDecoration"] {{
    background-color: {main_bg} !important;
}}

/* ── App background & base text ──────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"],
[data-testid="stBottom"],
section.main > div {{
    background-color: {main_bg} !important;
    color: {text} !important;
}}

/* ── Global text cascade ─────────────────────────────── */
.stApp p, .stApp li, .stApp span, .stApp div,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp label, .stApp caption, .stApp small,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {{
    color: {text} !important;
}}

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background-color: {sidebar_bg} !important;
}}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] caption,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
    color: {sidebar_text} !important;
}}

/* ── Sidebar selectbox field ─────────────────────────── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="select-container"] {{
    background-color: {input_bg} !important;
    border-color: {border} !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] p,
[data-testid="stSidebar"] [data-baseweb="select"] * {{
    color: {input_text} !important;
    background-color: transparent !important;
}}

/* ── Dropdown menus (global + sidebar) ───────────────── */
[data-baseweb="menu"],
[data-baseweb="popover"] ul,
[role="listbox"],
[data-baseweb="menu"] li,
[data-baseweb="option"] {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
}}
[data-baseweb="option"]:hover {{ background-color: {border} !important; }}
[data-testid="stSidebar"] [data-baseweb="menu"],
[data-testid="stSidebar"] [role="listbox"],
[data-testid="stSidebar"] [data-baseweb="popover"] ul {{
    background-color: {input_bg} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"],
[data-testid="stSidebar"] [data-baseweb="menu"] li {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"] *,
[data-testid="stSidebar"] [data-baseweb="menu"] li * {{
    color: {input_text} !important;
    background-color: {input_bg} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"]:hover {{
    background-color: {border} !important;
}}

/* ── Metric values ───────────────────────────────────── */
[data-testid="stMetricValue"] {{
    color: {accent} !important;
    font-weight: 700;
}}
[data-testid="stMetricLabel"] > div,
[data-testid="stMetricDelta"] {{
    color: {text} !important;
}}

/* ── Buttons ─────────────────────────────────────────── */
.stButton > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"],
[data-testid="stDownloadButton"] > button {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
    border-color: {btn_bg} !important;
}}
.stButton > button:hover,
[data-testid="stDownloadButton"] > button:hover {{
    filter: brightness(1.12);
}}

/* ── Dataframe / element toolbar (hover bar above tables) */
[data-testid="stElementToolbar"],
[data-testid="stElementToolbar"] > div {{
    background-color: {card_bg} !important;
    border-color: {border} !important;
}}
[data-testid="stElementToolbar"] button,
[data-testid="stElementToolbar"] [data-testid="stElementToolbarButton"] {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
    border-color: transparent !important;
}}
[data-testid="stElementToolbar"] button:hover {{
    filter: brightness(1.12);
}}

/* ── Text / number / date inputs ─────────────────────── */
[data-baseweb="input"],
[data-baseweb="input"] input,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
textarea,
[data-baseweb="textarea"] {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
    border-color: {border} !important;
}}

/* ── Main-area selectbox ─────────────────────────────── */
[data-baseweb="select"] > div,
[data-baseweb="select"] [data-baseweb="select-container"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
    border-color: {border} !important;
}}
[data-baseweb="select"] * {{ color: {input_text} !important; }}
[data-baseweb="tag"] {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
}}

/* ── Sidebar alert/info boxes — blend with sidebar bg ── */
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stSidebar"] [data-testid="stNotification"],
[data-testid="stSidebar"] [data-baseweb="notification"] {{
    background-color: rgba(255,255,255,0.18) !important;
    border-color: rgba(255,255,255,0.35) !important;
    border-left-color: rgba(255,255,255,0.35) !important;
    border-left-width: 4px !important;
    outline: none !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stAlert"] *,
[data-testid="stSidebar"] [data-testid="stNotification"] *,
[data-testid="stSidebar"] [data-baseweb="notification"] * {{
    color: {sidebar_text} !important;
    background-color: transparent !important;
}}

/* ── st.dataframe (canvas/Glide Data Grid) ──────────── */
[data-testid="stDataFrame"] {{
    border-radius: 4px;
}}

/* ── render_table() HTML tables (day mode) ───────────── */
.lt-tbl {{ overflow-x: auto; border-radius: 4px; }}
.lt-tbl table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    color: {text};
    background-color: {cell_bg};
}}
.lt-tbl th {{
    background-color: {df_header_bg} !important;
    color: {df_header_text} !important;
    padding: 7px 12px;
    text-align: left;
    border-bottom: 2px solid {border};
    white-space: nowrap;
    font-weight: 600;
}}
.lt-tbl td {{
    background-color: {cell_bg};
    color: {text};
    padding: 5px 12px;
    border-bottom: 1px solid {border};
    white-space: nowrap;
}}
.lt-tbl tbody tr:nth-child(even) td {{ background-color: {df_header_bg}; }}
.lt-tbl tbody tr:hover td {{ filter: brightness(0.95); }}

/* ── st.table() (HTML table) ────────────────────────── */
[data-testid="stTable"] table {{
    background-color: {cell_bg} !important;
    color: {cell_text} !important;
}}
[data-testid="stTable"] thead th {{
    background-color: {df_header_bg} !important;
    color: {df_header_text} !important;
    border-bottom: 2px solid {border} !important;
}}
[data-testid="stTable"] tbody td {{
    background-color: {cell_bg} !important;
    color: {cell_text} !important;
    border-color: {border} !important;
}}
[data-testid="stTable"] tbody tr:nth-child(even) td {{
    background-color: {df_header_bg} !important;
}}

/* ── Expander ────────────────────────────────────────── */
details[data-testid="stExpander"],
[data-testid="stExpander"] {{
    background-color: {card_bg} !important;
    border-color: {border} !important;
}}
details[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary {{
    background-color: {df_header_bg} !important;
    border-radius: 4px;
    padding: 6px 10px;
}}
details[data-testid="stExpander"] summary *,
[data-testid="stExpander"] summary *,
[data-testid="stExpanderHeader"],
[data-testid="stExpanderHeader"] *,
.streamlit-expanderHeader,
.streamlit-expanderHeader * {{
    color: {df_header_text} !important;
    background-color: transparent !important;
}}
[data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] > div {{
    background-color: {card_bg} !important;
}}

/* ── Cards / bordered containers ─────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {card_bg} !important;
    border-color: {border} !important;
}}

/* ── Alert boxes ─────────────────────────────────────── */
[data-testid="stAlert"],
[data-testid="stNotification"],
div[class*="stInfo"],
div[class*="stWarning"],
div[class*="stSuccess"],
div[class*="stError"] {{
    background-color: {alert_bg} !important;
    color: {text} !important;
    border-color: {border} !important;
}}
[data-testid="stAlert"] *,
[data-testid="stNotification"] * {{ color: {text} !important; }}

/* ── Tabs ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px;
    background-color: {main_bg} !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 4px 4px 0 0;
    padding: 8px 14px;
    color: {text} !important;
    background-color: {card_bg} !important;
}}
.stTabs [aria-selected="true"][data-baseweb="tab"] {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
}}
.stTabs [data-baseweb="tab-panel"],
.stTabs [data-baseweb="tab-border"] {{
    background-color: {main_bg} !important;
}}

/* ── Progress bar ─────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {{
    background-color: {accent} !important;
}}

/* ── Checkbox / radio labels ─────────────────────────── */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {{ color: {text} !important; }}
"""


def apply_theme() -> None:
    """Inject CSS for Night (dark) or Sky (light) theme."""
    dark_mode = st.session_state.get("dark_mode", True)
    t = _NIGHT if dark_mode else _SKY
    st.markdown(f"<style>{_CSS.format(**t)}</style>", unsafe_allow_html=True)


def plotly_theme() -> dict:
    """Return Plotly layout kwargs that match the current theme."""
    dark = st.session_state.get("dark_mode", True)
    t = _NIGHT if dark else _SKY
    fc = t["text"]
    gc = t["border"]
    return dict(
        paper_bgcolor=t["card_bg"],
        plot_bgcolor=t["card_bg"],
        font=dict(color=fc),
        title_font_color=fc,
        legend_font_color=fc,
        xaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
        yaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
    )

