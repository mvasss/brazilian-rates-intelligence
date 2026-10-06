"""
Página 1 — Macro Overview
"O que está acontecendo?"

KPI cards + gráficos interativos de séries macro + heatmap de correlação.
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

st.set_page_config(page_title="BRI — Macro", page_icon="📊", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_macro_data(start, end):
    """Load all macro data with caching."""
    try:
        from src.collectors.bcb_collector import fetch_sgs_series, fetch_focus_latest_median
        from src.collectors.market_collector import fetch_market_data

        sgs = fetch_sgs_series(start=start, end=end)
        focus = fetch_focus_latest_median(start=start)
        market = fetch_market_data(start=start, end=end, include_sectors=False)
        return sgs, focus, market
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# 📊 Macro Overview")
    st.markdown(f"*O que está acontecendo na economia brasileira?*")

    sgs, focus, market = load_macro_data(start, end)

    if sgs.empty:
        st.warning("Não foi possível carregar dados do BCB. Verifique sua conexão.")
        st.info("💡 Instale as dependências: `pip install -r requirements.txt`")
        _show_demo_data()
        return

    # === KPI Row ===
    metrics = []
    if "selic_meta" in sgs.columns:
        last_selic = sgs["selic_meta"].dropna().iloc[-1]
        metrics.append({"label": "Selic Meta", "value": f"{last_selic:.2f}%"})

    if "ipca_12m" in sgs.columns:
        last_ipca = sgs["ipca_12m"].dropna().iloc[-1]
        prev_ipca = sgs["ipca_12m"].dropna().iloc[-2] if len(sgs["ipca_12m"].dropna()) > 1 else None
        delta = last_ipca - prev_ipca if prev_ipca else None
        metrics.append({"label": "IPCA 12m", "value": f"{last_ipca:.2f}%", "delta": delta, "suffix": "pp"})

    if "usd_brl_ptax" in sgs.columns:
        last_fx = sgs["usd_brl_ptax"].dropna().iloc[-1]
        metrics.append({"label": "USD/BRL", "value": f"R$ {last_fx:.2f}"})

    if not focus.empty and "IPCA_current" in focus.columns:
        last_focus = focus["IPCA_current"].dropna().iloc[-1]
        metrics.append({"label": "Focus IPCA", "value": f"{last_focus:.2f}%"})

    if "divida_bruta_pib" in sgs.columns:
        last_debt = sgs["divida_bruta_pib"].dropna().iloc[-1]
        metrics.append({"label": "Dívida/PIB", "value": f"{last_debt:.1f}%"})

    if metrics:
        render_kpi_row(metrics)

    st.markdown("---")

    # === Macro Charts ===
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏦 Política Monetária", "📈 Inflação", "💱 Câmbio & Atividade", "🔗 Correlações"
    ])

    with tab1:
        _plot_monetary_policy(sgs, focus)

    with tab2:
        _plot_inflation(sgs, focus)

    with tab3:
        _plot_fx_activity(sgs, market)

    with tab4:
        _plot_correlations(sgs, market)


def _plot_monetary_policy(sgs, focus):
    """Selic + Focus Selic expectations."""
    fig = go.Figure()

    if "selic_meta" in sgs.columns:
        s = sgs["selic_meta"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Selic Meta", line=dict(color=CHART_COLORS[0], width=2.5),
            fill="tozeroy", fillcolor=f"rgba(0,210,255,0.08)",
        ))

    if not focus.empty and "Selic_current" in focus.columns:
        s = focus["Selic_current"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Focus Selic (ano corrente)", line=dict(color=CHART_COLORS[1], width=2, dash="dash"),
        ))

    if not focus.empty and "Selic_next" in focus.columns:
        s = focus["Selic_next"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Focus Selic (próximo ano)", line=dict(color=CHART_COLORS[2], width=1.5, dash="dot"),
        ))

    fig.update_layout(
        title="Taxa Selic vs Expectativas Focus",
        yaxis_title="% a.a.",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_inflation(sgs, focus):
    """IPCA + Focus expectations."""
    fig = go.Figure()

    if "ipca_12m" in sgs.columns:
        s = sgs["ipca_12m"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="IPCA 12m (realizado)", line=dict(color=CHART_COLORS[0], width=2.5),
        ))

    if not focus.empty and "IPCA_current" in focus.columns:
        s = focus["IPCA_current"].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name="Focus IPCA (ano corrente)", line=dict(color=CHART_COLORS[1], width=2, dash="dash"),
        ))

    # Add inflation target band
    fig.add_hline(y=3.0, line_dash="dot", line_color=COLORS["text_muted"],
                  annotation_text="Meta (3.0%)")
    fig.add_hline(y=4.5, line_dash="dot", line_color="rgba(255,23,68,0.3)",
                  annotation_text="Teto (4.5%)")
    fig.add_hline(y=1.5, line_dash="dot", line_color="rgba(0,200,83,0.3)",
                  annotation_text="Piso (1.5%)")

    fig.update_layout(
        title="Inflação: Realizado vs Expectativas",
        yaxis_title="%",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_fx_activity(sgs, market):
    """USD/BRL + activity indicators."""
    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        if "usd_brl_ptax" in sgs.columns:
            s = sgs["usd_brl_ptax"].dropna()
            fig.add_trace(go.Scatter(
                x=s.index, y=s.values,
                name="USD/BRL (PTAX)", line=dict(color=CHART_COLORS[3], width=2),
                fill="tozeroy", fillcolor=f"rgba(0,200,83,0.05)",
            ))
        fig.update_layout(title="Câmbio USD/BRL", yaxis_title="R$/US$", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        if "desemprego_pnad" in sgs.columns:
            s = sgs["desemprego_pnad"].dropna()
            fig.add_trace(go.Bar(
                x=s.index, y=s.values,
                name="Desemprego PNAD",
                marker_color=CHART_COLORS[4],
                opacity=0.7,
            ))
        fig.update_layout(title="Taxa de Desemprego", yaxis_title="%", height=380)
        st.plotly_chart(fig, use_container_width=True)


def _plot_correlations(sgs, market):
    """Correlation heatmap of macro variables."""
    combined = pd.DataFrame()

    for col in ["selic_meta", "ipca_12m", "usd_brl_ptax", "divida_bruta_pib"]:
        if col in sgs.columns:
            combined[col] = sgs[col]

    if not market.empty:
        for col in market.columns:
            combined[col] = market[col]

    if combined.shape[1] < 2:
        st.info("Dados insuficientes para calcular correlações.")
        return

    # Use returns for market data, levels for macro
    corr = combined.pct_change().dropna().corr()

    # Clean labels
    labels = {
        "selic_meta": "Selic", "ipca_12m": "IPCA 12m",
        "usd_brl_ptax": "USD/BRL", "divida_bruta_pib": "Dívida/PIB",
        "ibovespa": "Ibovespa", "ifix": "IFIX",
        "usd_brl": "USD/BRL (mkt)", "imab11": "IMAB11",
    }
    corr.index = [labels.get(c, c) for c in corr.index]
    corr.columns = [labels.get(c, c) for c in corr.columns]

    fig = px.imshow(
        corr,
        color_continuous_scale=["#E94560", "#1A1A2E", "#00D2FF"],
        zmin=-1, zmax=1,
        text_auto=".2f",
    )
    fig.update_layout(title="Matriz de Correlação", height=500)
    st.plotly_chart(fig, use_container_width=True)


def _show_demo_data():
    """Show demo placeholder when data is unavailable."""
    st.markdown("### 📊 Dados de demonstração")
    st.info("Os gráficos abaixo usam dados sintéticos para demonstração do layout.")

    dates = pd.bdate_range("2020-01-01", periods=1200)
    np.random.seed(42)

    # Synthetic Selic
    selic = pd.Series(
        np.concatenate([
            np.linspace(4.5, 2.0, 200),
            np.full(200, 2.0),
            np.linspace(2.0, 13.75, 400),
            np.linspace(13.75, 10.5, 200),
            np.linspace(10.5, 14.75, 200),
        ]),
        index=dates,
    )

    metrics = [
        {"label": "Selic Meta", "value": "14.75%"},
        {"label": "IPCA 12m", "value": "5.20%", "delta": 0.15, "suffix": "pp"},
        {"label": "USD/BRL", "value": "R$ 5.45"},
        {"label": "Focus IPCA", "value": "5.50%"},
        {"label": "Dívida/PIB", "value": "78.3%"},
    ]
    render_kpi_row(metrics)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=selic.index, y=selic.values,
        name="Selic Meta (demo)", line=dict(color=CHART_COLORS[0], width=2.5),
        fill="tozeroy", fillcolor="rgba(0,210,255,0.08)",
    ))
    fig.update_layout(title="Taxa Selic (dados de demonstração)", yaxis_title="% a.a.", height=400)
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
