"""
Dashboard Theme — Premium dark mode visual system.

Color palette, typography, Plotly layout defaults, and CSS injection
for Streamlit. Designed for a professional CIB/Asset look.
"""
import plotly.graph_objects as go
import plotly.io as pio

# =============================================================================
# Color Palette
# =============================================================================
COLORS = {
    # Backgrounds
    "bg_primary": "#0E1117",
    "bg_secondary": "#1A1A2E",
    "bg_card": "#16213E",
    "bg_card_hover": "#1C2A4A",
    # Accent gradient
    "accent_1": "#0F3460",
    "accent_2": "#533483",
    "accent_3": "#E94560",
    "accent_4": "#00D2FF",
    # Semantic
    "positive": "#00C853",
    "negative": "#FF1744",
    "neutral": "#FFD600",
    "info": "#2979FF",
    # Text
    "text_primary": "#E8EAED",
    "text_secondary": "#9AA0A6",
    "text_muted": "#5F6368",
    # Regime colors
    "risk_on": "#00C853",
    "risk_off": "#FF1744",
    "inflationary": "#FFD600",
    "disinflationary": "#2979FF",
    # Chart colors (sequential)
    "chart_1": "#00D2FF",
    "chart_2": "#E94560",
    "chart_3": "#FFD600",
    "chart_4": "#00C853",
    "chart_5": "#533483",
    "chart_6": "#FF6D00",
    "chart_7": "#00BFA5",
    "chart_8": "#FF80AB",
}

CHART_COLORS = [
    COLORS["chart_1"], COLORS["chart_2"], COLORS["chart_3"],
    COLORS["chart_4"], COLORS["chart_5"], COLORS["chart_6"],
    COLORS["chart_7"], COLORS["chart_8"],
]

# =============================================================================
# Plotly Template
# =============================================================================
PLOTLY_LAYOUT = dict(
    paper_bgcolor=COLORS["bg_primary"],
    plot_bgcolor=COLORS["bg_secondary"],
    font=dict(family="Inter, system-ui, sans-serif", color=COLORS["text_primary"], size=13),
    title=dict(font=dict(size=18, color=COLORS["text_primary"]), x=0.02, y=0.97),
    xaxis=dict(
        gridcolor="#2A2A4A",
        gridwidth=0.5,
        zerolinecolor="#2A2A4A",
        showline=False,
        tickfont=dict(size=11, color=COLORS["text_secondary"]),
    ),
    yaxis=dict(
        gridcolor="#2A2A4A",
        gridwidth=0.5,
        zerolinecolor="#2A2A4A",
        showline=False,
        tickfont=dict(size=11, color=COLORS["text_secondary"]),
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color=COLORS["text_secondary"]),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    margin=dict(l=60, r=30, t=60, b=40),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor=COLORS["bg_card"],
        font=dict(color=COLORS["text_primary"], size=12),
        bordercolor=COLORS["accent_1"],
    ),
)

# Register custom template
pio.templates["bri_dark"] = go.layout.Template(layout=go.Layout(**PLOTLY_LAYOUT))
pio.templates.default = "bri_dark"

# =============================================================================
# Streamlit CSS Injection
# =============================================================================
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #16213E 0%, #1A1A2E 100%);
        border: 1px solid rgba(15, 52, 96, 0.5);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }
    div[data-testid="stMetric"] label {
        color: #9AA0A6 !important;
        font-size: 0.85rem;
        font-weight: 500;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #E8EAED;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background: #16213E;
        border-radius: 8px;
        border: 1px solid #0F3460;
        padding: 8px 20px;
        color: #9AA0A6;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0F3460, #533483);
        color: #E8EAED !important;
        border-color: #533483;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0E1117 0%, #1A1A2E 100%);
        border-right: 1px solid #16213E;
    }

    /* Headers */
    h1 {
        background: linear-gradient(90deg, #00D2FF, #E94560);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    h2 {
        color: #E8EAED;
        font-weight: 600;
        border-bottom: 2px solid #0F3460;
        padding-bottom: 8px;
    }
    h3 {
        color: #9AA0A6;
        font-weight: 500;
    }

    /* Selectbox / inputs */
    .stSelectbox > div > div {
        background: #16213E;
        border: 1px solid #0F3460;
        border-radius: 8px;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: #16213E;
        border-radius: 8px;
        color: #E8EAED;
    }

    /* Plotly charts container */
    .stPlotlyChart {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Glassmorphism card helper */
    .glass-card {
        background: rgba(22, 33, 62, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(15, 52, 96, 0.3);
        border-radius: 12px;
        padding: 20px;
    }
</style>
"""


def apply_theme(st_module):
    """Apply the premium dark theme to a Streamlit page."""
    st_module.set_page_config(
        page_title="Brazilian Rates Intelligence",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st_module.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def styled_metric_card(st_module, label: str, value: str, delta: str = None, delta_color: str = "normal"):
    """Render a styled metric card."""
    st_module.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def section_header(st_module, title: str, subtitle: str = ""):
    """Render a styled section header."""
    st_module.markdown(f"## {title}")
    if subtitle:
        st_module.markdown(f"*{subtitle}*")
