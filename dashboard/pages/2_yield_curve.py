"""
Página 2 — Yield Curve
"O que a curva está precificando?"

Curva atual vs histórica, slope, curvature, real yield, heatmap 3D.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

from dashboard.components.theme import CUSTOM_CSS, COLORS, CHART_COLORS
from dashboard.components.kpi_cards import render_kpi_row
from dashboard.components.sidebar import render_sidebar

st.set_page_config(page_title="BRI — Yield Curve", page_icon="📈", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_curve_data(start, end):
    """Load yield curve data."""
    try:
        from src.collectors.curve_collector import fetch_historical_curves, extract_curve_vertices
        from src.collectors.bcb_collector import fetch_focus_latest_median
        from src.processors.curve_processor import compute_curve_metrics

        curves = fetch_historical_curves(start=start, end=end, frequency="weekly")
        vertices = extract_curve_vertices(curves) if not curves.empty else pd.DataFrame()

        focus = fetch_focus_latest_median(["IPCA"], start=start)
        inflation_exp = focus.get("IPCA_current") if not focus.empty else None

        metrics = compute_curve_metrics(vertices, inflation_exp) if not vertices.empty else pd.DataFrame()

        return curves, vertices, metrics
    except Exception as e:
        st.error(f"Erro ao carregar curva: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# 📈 Yield Curve")
    st.markdown("*O que a curva de juros está precificando?*")

    curves, vertices, metrics = load_curve_data(start, end)

    if vertices.empty:
        st.warning("Dados de curva não disponíveis. Mostrando dados de demonstração.")
        _show_demo_curve()
        return

    # === KPI Row ===
    kpis = []
    if not metrics.empty:
        last = metrics.iloc[-1]
        if "level" in metrics.columns:
            kpis.append({"label": "Nível da Curva", "value": f"{last['level']:.2f}%"})
        if "slope" in metrics.columns:
            delta = last.get("slope_1w")
            kpis.append({"label": "Slope (10Y-2Y)", "value": f"{last['slope']:.2f}pp",
                          "delta": round(delta, 2) if pd.notna(delta) else None, "suffix": "pp"})
        if "curvature" in metrics.columns:
            kpis.append({"label": "Curvatura", "value": f"{last['curvature']:.2f}pp"})
        if "real_yield" in metrics.columns and pd.notna(last.get("real_yield")):
            kpis.append({"label": "Real Yield", "value": f"{last['real_yield']:.2f}%"})

    if kpis:
        render_kpi_row(kpis)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "📉 Curva Atual", "📊 Evolução Temporal", "🌡️ Heatmap"
    ])

    with tab1:
        _plot_current_curve(vertices)

    with tab2:
        _plot_curve_evolution(metrics)

    with tab3:
        _plot_curve_heatmap(vertices)


def _plot_current_curve(vertices):
    """Current curve vs historical snapshots."""
    fig = go.Figure()

    labels = list(vertices.columns)
    today = vertices.iloc[-1]

    fig.add_trace(go.Scatter(
        x=labels, y=today.values,
        name="Atual", mode="lines+markers",
        line=dict(color=CHART_COLORS[0], width=3),
        marker=dict(size=8, color=CHART_COLORS[0]),
    ))

    # Historical comparisons
    comparisons = [
        ("1 mês atrás", -4, CHART_COLORS[1], "dash"),
        ("3 meses atrás", -13, CHART_COLORS[2], "dash"),
        ("1 ano atrás", -52, CHART_COLORS[3], "dot"),
    ]

    for label, offset, color, dash in comparisons:
        idx = len(vertices) + offset
        if idx >= 0:
            row = vertices.iloc[idx]
            fig.add_trace(go.Scatter(
                x=labels, y=row.values,
                name=f"{label} ({row.name.strftime('%d/%m/%y')})",
                mode="lines+markers",
                line=dict(color=color, width=1.5, dash=dash),
                marker=dict(size=5, color=color),
                opacity=0.7,
            ))

    fig.update_layout(
        title="Estrutura a Termo — Curva PRE",
        xaxis_title="Vértice",
        yaxis_title="Taxa (% a.a.)",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_curve_evolution(metrics):
    """Time series of slope, curvature, level."""
    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        if "slope" in metrics.columns:
            s = metrics["slope"].dropna()
            fig.add_trace(go.Scatter(
                x=s.index, y=s.values,
                name="Slope (10Y-2Y)", line=dict(color=CHART_COLORS[0], width=2),
                fill="tozeroy", fillcolor="rgba(0,210,255,0.06)",
            ))
            fig.add_hline(y=0, line_color=COLORS["text_muted"], line_dash="dash")
        fig.update_layout(title="Inclinação da Curva (Slope)", yaxis_title="pp", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        if "curvature" in metrics.columns:
            s = metrics["curvature"].dropna()
            fig.add_trace(go.Scatter(
                x=s.index, y=s.values,
                name="Curvatura (Butterfly)", line=dict(color=CHART_COLORS[1], width=2),
                fill="tozeroy", fillcolor="rgba(233,69,96,0.06)",
            ))
            fig.add_hline(y=0, line_color=COLORS["text_muted"], line_dash="dash")
        fig.update_layout(title="Curvatura (Butterfly Spread)", yaxis_title="pp", height=380)
        st.plotly_chart(fig, use_container_width=True)

    # Level + Real Yield
    fig = go.Figure()
    if "level" in metrics.columns:
        s = metrics["level"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Nível Nominal", line=dict(color=CHART_COLORS[2], width=2),
        ))
    if "real_yield" in metrics.columns:
        s = metrics["real_yield"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Real Yield", line=dict(color=CHART_COLORS[3], width=2),
        ))
    fig.update_layout(
        title="Nível da Curva: Nominal vs Real",
        yaxis_title="%", height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_curve_heatmap(vertices):
    """Heatmap of the curve over time."""
    fig = px.imshow(
        vertices.T,
        x=vertices.index,
        y=vertices.columns,
        color_continuous_scale=["#0F3460", "#533483", "#E94560", "#FFD600"],
        labels=dict(x="Data", y="Vértice", color="Taxa (%)"),
        aspect="auto",
    )
    fig.update_layout(
        title="Evolução da Curva ao Longo do Tempo",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _show_demo_curve():
    """Demo data when real data is unavailable."""
    st.markdown("### 📈 Dados de demonstração")

    labels = ["1M", "2M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "10Y"]
    np.random.seed(42)

    # Synthetic upward sloping curve
    current = [14.5, 14.4, 14.3, 14.0, 13.5, 13.0, 12.8, 12.5, 12.3]
    month_ago = [c + 0.3 for c in current]
    year_ago = [c - 1.5 for c in current]

    kpis = [
        {"label": "Nível da Curva", "value": "13.37%"},
        {"label": "Slope (10Y-2Y)", "value": "-0.70pp"},
        {"label": "Curvatura", "value": "0.30pp"},
        {"label": "Real Yield", "value": "7.87%"},
    ]
    render_kpi_row(kpis)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=current, name="Atual", mode="lines+markers",
                              line=dict(color=CHART_COLORS[0], width=3), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=labels, y=month_ago, name="1 mês atrás", mode="lines+markers",
                              line=dict(color=CHART_COLORS[1], width=1.5, dash="dash"), opacity=0.7))
    fig.add_trace(go.Scatter(x=labels, y=year_ago, name="1 ano atrás", mode="lines+markers",
                              line=dict(color=CHART_COLORS[3], width=1.5, dash="dot"), opacity=0.7))
    fig.update_layout(title="Estrutura a Termo (demo)", xaxis_title="Vértice", yaxis_title="% a.a.", height=450)
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
