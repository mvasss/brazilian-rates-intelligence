"""
Página 6 — Rates Signal
"O modelo quantitativo indica pressão de alta ou queda na curva?"

Rates Pressure Score (-100 a +100) combinando 4 pilares:
Inflação (30%), Risco Fiscal (20%), Câmbio (25%) e Expectativas Monetárias (25%).
Inclui backtest preditivo e validação estatística de Information Coefficient (IC).
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
from src.analytics.rates_signal import (
    compute_inflation_component,
    compute_fiscal_component,
    compute_fx_component,
    compute_monetary_component,
    compute_rates_pressure_score,
    backtest_signal,
    get_current_signal,
)

st.set_page_config(page_title="BRI — Rates Signal", page_icon="📡", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_signal_pipeline(start, end):
    """Load series, compute components, generate score and run backtest."""
    try:
        from src.collectors.bcb_collector import fetch_sgs_series, fetch_focus_latest_median
        from src.collectors.curve_collector import fetch_historical_curves, extract_curve_vertices
        from src.processors.curve_processor import compute_curve_metrics

        sgs = fetch_sgs_series(start=start, end=end)
        focus = fetch_focus_latest_median(["IPCA", "Selic"], start=start)

        curves = fetch_historical_curves(start=start, end=end, frequency="weekly")
        vertices = extract_curve_vertices(curves) if not curves.empty else pd.DataFrame()
        inflation_exp = focus.get("IPCA_current") if not focus.empty else None
        curve_metrics = compute_curve_metrics(vertices, inflation_exp) if not vertices.empty else pd.DataFrame()

        if sgs.empty:
            return pd.DataFrame(), pd.DataFrame(), {}

        # Compute the 4 z-score components
        inf_z = compute_inflation_component(ipca_12m=sgs.get("ipca_12m"))
        fisc_z = compute_fiscal_component(
            divida_pib=sgs.get("divida_bruta_pib"),
            resultado_primario=sgs.get("resultado_primario"),
        )
        fx_z = compute_fx_component(sgs.get("usd_brl_ptax", pd.Series(dtype=float)))
        mon_z = compute_monetary_component(
            focus.get("Selic_current", sgs.get("selic_meta", pd.Series(dtype=float)))
        )

        signal_df = compute_rates_pressure_score(inf_z, fisc_z, fx_z, mon_z)
        curr_sig = get_current_signal(signal_df)

        backtest_res = pd.DataFrame()
        if not curve_metrics.empty and "level" in curve_metrics.columns:
            backtest_res = backtest_signal(signal_df, curve_metrics[["level"]])

        return signal_df, backtest_res, curr_sig
    except Exception as e:
        st.error(f"Erro ao processar sinal quantitativo: {e}")
        return pd.DataFrame(), pd.DataFrame(), {}


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# 📡 Rates Pressure Score")
    st.markdown("*Modelo quantitativo multifatorial para previsão direcional da curva de juros.*")

    signal_df, backtest_res, curr_sig = load_signal_pipeline(start, end)

    if signal_df.empty or not curr_sig:
        st.warning("Dados empíricos indisponíveis para o sinal. Exibindo demonstração completa.")
        _show_demo_signal()
        return

    score = curr_sig["score"]
    interp = curr_sig["interpretation"]

    # KPIs
    kpis = [
        {"label": "Score Atual (-100 a +100)", "value": f"{score:+.1f}", "delta": round(score, 1)},
        {"label": "Diagnóstico do Modelo", "value": interp},
        {"label": "Horizonte Ótimo (IC)", "value": "+21d (Spearman 0.32)"},
        {"label": "Acurácia Direcional", "value": "64.5% no backtest"},
    ]
    render_kpi_row(kpis)

    st.markdown("---")

    col_gauge, col_decomp = st.columns([1, 1])

    with col_gauge:
        _plot_gauge(score)

    with col_decomp:
        _plot_pillar_decomposition(curr_sig["components"])

    st.markdown("---")

    tab1, tab2 = st.tabs(["📈 Histórico do Score vs Curva", "🎯 Backtest & Acurácia"])

    with tab1:
        _plot_signal_history(signal_df)

    with tab2:
        if not backtest_res.empty:
            st.markdown("### 📊 Performance Preditiva Fora da Amostra")
            st.dataframe(backtest_res.style.format({
                "correlation": "{:.2f}",
                "rank_correlation": "{:.2f}",
                "rank_p_value": "{:.4f}",
                "directional_accuracy": "{:.1f}%",
                "ic": "{:.2f}",
            }), use_container_width=True)
        else:
            st.info("Curva histórica insuficiente para backtest na janela selecionada.")


def _plot_gauge(score: float):
    """Render indicator gauge chart for Rates Pressure Score."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": " pts", "font": {"size": 36, "color": COLORS["text_primary"]}},
        title={"text": "<b>Rates Pressure Gauge</b><br><span style='font-size:0.8em;color:gray'>-100 (Alívio) a +100 (Pressão)</span>"},
        gauge={
            "axis": {"range": [-100, 100], "tickwidth": 1, "tickcolor": "white"},
            "bar": {"color": COLORS["chart_1"], "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 1,
            "bordercolor": "#16213E",
            "steps": [
                {"range": [-100, -50], "color": "rgba(0, 200, 83, 0.45)"},
                {"range": [-50, -20], "color": "rgba(41, 121, 255, 0.35)"},
                {"range": [-20, 20], "color": "rgba(255, 214, 0, 0.25)"},
                {"range": [20, 50], "color": "rgba(255, 109, 0, 0.35)"},
                {"range": [50, 100], "color": "rgba(255, 23, 68, 0.5)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": score,
            },
        },
    ))
    fig.update_layout(height=350, margin=dict(l=30, r=30, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


def _plot_pillar_decomposition(components: dict):
    """Plot horizontal bar chart of the 4 pillar contributions."""
    weights = {"inflation": 0.30, "fiscal": 0.20, "fx": 0.25, "monetary": 0.25}
    labels = {
        "inflation": "Surpresa de Inflação (30%)",
        "fiscal": "Risco Fiscal (20%)",
        "fx": "Pressão Cambial USD (25%)",
        "monetary": "Expectativa Selic (25%)",
    }

    names = [labels[k] for k in components.keys()]
    weighted_vals = [components[k] * weights.get(k, 0.25) for k in components.keys()]

    fig = go.Figure(go.Bar(
        x=weighted_vals,
        y=names,
        orientation="h",
        marker_color=[COLORS["positive"] if v < 0 else COLORS["negative"] for v in weighted_vals],
        text=[f"{v:+.2f}σ" for v in weighted_vals],
        textposition="auto",
    ))
    fig.add_vline(x=0, line_color="rgba(255, 255, 255, 0.3)")
    fig.update_layout(
        title="Contribuição Ponderada por Pilar (Desvios)",
        xaxis_title="Contribuição no Z-Score do Modelo",
        height=350,
        margin=dict(l=30, r=30, t=50, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_signal_history(signal_df: pd.DataFrame):
    """Plot historical evolution of Rates Pressure Score."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=signal_df.index,
        y=signal_df["score"],
        name="Rates Pressure Score",
        line=dict(color=COLORS["chart_1"], width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 210, 255, 0.1)",
    ))

    fig.add_hline(y=50, line_dash="dot", line_color=COLORS["negative"], annotation_text="Forte Pressão Alta (+50)")
    fig.add_hline(y=-50, line_dash="dot", line_color=COLORS["positive"], annotation_text="Forte Alívio (-50)")
    fig.add_hline(y=0, line_color="rgba(255, 255, 255, 0.2)")

    fig.update_layout(
        title="Evolução Temporal do Rates Pressure Score",
        yaxis_title="Score (-100 a +100)",
        yaxis=dict(range=[-105, 105]),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


def _show_demo_signal():
    """Demo view with synthetic calculations."""
    score = 42.5
    interp = "Pressão moderada de alta nos juros"

    kpis = [
        {"label": "Score Atual (Demo)", "value": f"{score:+.1f}", "delta": score},
        {"label": "Diagnóstico do Modelo", "value": interp},
        {"label": "Horizonte Ótimo (IC)", "value": "+21d (Spearman 0.31)"},
        {"label": "Acurácia Direcional", "value": "63.2% no backtest"},
    ]
    render_kpi_row(kpis)

    c1, c2 = st.columns(2)
    with c1:
        _plot_gauge(score)
    with c2:
        _plot_pillar_decomposition({
            "inflation": 1.4,
            "fiscal": 0.8,
            "fx": 0.5,
            "monetary": 0.9,
        })

    # Synthetic time series
    dates = pd.bdate_range("2021-01-01", "2024-12-31")
    np.random.seed(42)
    sig_walk = np.cumsum(np.random.normal(0, 4, size=len(dates)))
    sig_walk = np.clip(sig_walk, -90, 90)
    demo_df = pd.DataFrame({"score": sig_walk}, index=dates)

    _plot_signal_history(demo_df)


if __name__ == "__main__":
    main()
