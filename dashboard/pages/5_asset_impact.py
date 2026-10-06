"""
Página 5 — Asset Impact
"O que o movimento da curva de juros provoca nos principais ativos?"

Mapeamento empírico da sensibilidade de Ibovespa, IFIX, USD/BRL e IMAB11
a choques de abertura ou fechamento da curva de juros (±50bps, ±100bps, ±200bps).
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
from src.analytics.asset_impact import (
    identify_rate_scenarios,
    compute_asset_response,
    scenario_impact_summary,
    compute_lead_lag,
    build_impact_heatmap,
)

st.set_page_config(page_title="BRI — Asset Impact", page_icon="🎯", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_impact_data(start, end):
    """Load curve metrics and market asset returns."""
    try:
        from src.collectors.curve_collector import fetch_historical_curves, extract_curve_vertices
        from src.collectors.bcb_collector import fetch_focus_latest_median
        from src.collectors.market_collector import fetch_market_data
        from src.processors.curve_processor import compute_curve_metrics
        try:
            from src.processors.returns_processor import compute_all_asset_returns
        except ImportError:
            from src.processors.returns_processor import compute_returns as compute_all_asset_returns

        curves = fetch_historical_curves(start=start, end=end, frequency="weekly")
        vertices = extract_curve_vertices(curves) if not curves.empty else pd.DataFrame()
        focus = fetch_focus_latest_median(["IPCA"], start=start)
        inflation_exp = focus.get("IPCA_current") if not focus.empty else None
        curve_metrics = compute_curve_metrics(vertices, inflation_exp) if not vertices.empty else pd.DataFrame()

        market = fetch_market_data(start=start, end=end, include_sectors=False)
        returns = compute_all_asset_returns(market) if not market.empty else pd.DataFrame()

        return curve_metrics, returns
    except Exception as e:
        st.error(f"Erro ao carregar dados de impacto: {e}")
        return pd.DataFrame(), pd.DataFrame()


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# 🎯 Asset Impact — Transmissão da Curva")
    st.markdown("*Como a abertura ou fechamento da curva de juros impacta a precificação das classes de ativos?*")

    curve_metrics, returns = load_impact_data(start, end)

    if curve_metrics.empty or returns.empty or "level" not in curve_metrics.columns:
        st.warning("Dados empíricos insuficientes. Exibindo simulador com dados sintéticos de mercado.")
        _show_demo_impact()
        return

    # Scenario computation
    scenarios = identify_rate_scenarios(curve_metrics["level"], thresholds_bps=[50, 100, 200], window=63)
    if scenarios.empty:
        st.info("Nenhum choque de taxa significativo (±50bps) identificado na janela selecionada.")
        return

    responses = compute_asset_response(scenarios, returns, forward_windows=[5, 10, 21, 63])
    if responses.empty:
        st.info("Não foi possível calcular respostas com a janela selecionada.")
        return

    # Friendly mappings for non-technical readability
    scenario_labels = {
        "+50bps": "Abertura Leve da Curva (+50 bps / +0,50 pp)",
        "+100bps": "Abertura Forte (+100 bps / +1,00 pp)",
        "+200bps": "Choque Severo de Alta (+200 bps / +2,00 pp)",
        "-50bps": "Fechamento Leve (-50 bps / -0,50 pp)",
        "-100bps": "Fechamento Forte (-100 bps / -1,00 pp)",
        "-200bps": "Alívio Expressivo de Queda (-200 bps / -2,00 pp)",
    }
    asset_labels = {
        "bova11": "BOVA11 (Ações)",
        "ibovespa": "Ibovespa (Índice)",
        "ifix": "IFIX (Fundos Imob.)",
        "imab11": "IMAB11 (Renda Fixa IPCA)",
        "usd_brl": "Dólar (USD/BRL)",
    }

    # Interactive Scenario Filter
    scenario_list = sorted(responses["scenario"].unique().tolist())
    selected_scen = st.selectbox(
        "Simulador: Selecione o Cenário de Movimento de Taxas",
        scenario_list,
        index=0,
        format_func=lambda x: scenario_labels.get(x, x),
    )

    sub_resp = responses[responses["scenario"] == selected_scen]
    n_cases = len(sub_resp)

    # KPIs for the selected scenario
    kpis = [{"label": "Cenário Simulado", "value": scenario_labels.get(selected_scen, selected_scen)}]
    for asset in ["ibovespa", "ifix", "imab11", "usd_brl"]:
        col = f"{asset}_21d"
        if col in sub_resp.columns:
            med_ret = sub_resp[col].median()
            kpis.append({
                "label": f"{asset_labels.get(asset, asset.upper())} (Mediana 21d)",
                "value": f"{med_ret:+.2f}%",
                "delta": round(med_ret, 2),
                "suffix": "%",
            })

    render_kpi_row(kpis)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "🔥 Mapa de Sensibilidade Entre Ativos",
        "📦 Distribuição Histórica dos Retornos",
        "⏱️ Defasagem Temporal (Lead / Lag)",
    ])

    with tab1:
        _plot_heatmap(responses, asset_labels, scenario_labels)

    with tab2:
        _plot_distributions(sub_resp, selected_scen, asset_labels, scenario_labels)

    with tab3:
        _plot_lead_lag_view(curve_metrics, returns)


def _plot_heatmap(responses: pd.DataFrame, asset_labels: dict | None = None, scenario_labels: dict | None = None):
    """Plot cross-asset sensitivity heatmap for 21-day forward window."""
    heatmap_df = build_impact_heatmap(responses, window=21)
    if heatmap_df.empty:
        st.info("Dados insuficientes para construir heatmap de sensibilidade.")
        return

    # Translate column and index names for display
    plot_df = heatmap_df.copy()
    if asset_labels:
        plot_df.columns = [asset_labels.get(c.lower(), c.upper()) for c in plot_df.columns]
    if scenario_labels:
        plot_df.index = [scenario_labels.get(idx, idx) for idx in plot_df.index]

    fig = px.imshow(
        plot_df,
        color_continuous_scale=["#E94560", "#16213E", "#00D2FF"],
        text_auto=".2f",
        labels=dict(x="Classe de Ativo", y="Cenário de Movimento na Curva", color="Retorno Mediano (%)"),
    )
    fig.update_layout(
        title="Sensibilidade: Retorno Mediano em 21 Dias Úteis por Choque de Taxas (%)",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_distributions(sub_resp: pd.DataFrame, scenario_name: str, asset_labels: dict | None = None, scenario_labels: dict | None = None):
    """Plot boxplot and dispersion of asset returns."""
    ret_cols = [c for c in sub_resp.columns if c.endswith("_21d")]
    if not ret_cols:
        return

    melted = sub_resp.melt(
        id_vars=["date", "scenario"],
        value_vars=ret_cols,
        var_name="Ativo",
        value_name="Retorno 21d (%)"
    )
    melted["Ativo"] = melted["Ativo"].str.replace("_21d", "")
    if asset_labels:
        melted["Ativo"] = melted["Ativo"].map(lambda x: asset_labels.get(x.lower(), x.upper()))
    else:
        melted["Ativo"] = melted["Ativo"].str.upper()

    display_scen = scenario_labels.get(scenario_name, scenario_name) if scenario_labels else scenario_name

    fig = px.box(
        melted,
        x="Ativo",
        y="Retorno 21d (%)",
        color="Ativo",
        points="all",
        title=f"Distribuição do Retorno em 21 Dias Úteis — {display_scen}",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255, 255, 255, 0.3)")
    fig.update_layout(height=450, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def _plot_lead_lag_view(curve_metrics: pd.DataFrame, returns: pd.DataFrame):
    """Lead / lag cross correlation."""
    if "level" not in curve_metrics.columns or "ibovespa" not in returns.columns:
        st.info("Métricas necessárias para Lead/Lag ausentes.")
        return

    curve_diff = curve_metrics["level"].diff().dropna()
    eq_ret = returns["ibovespa"].dropna()
    aligned = pd.concat([curve_diff, eq_ret], axis=1).dropna()

    ll_df = compute_lead_lag(aligned.iloc[:, 0], aligned.iloc[:, 1], max_lag=20)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ll_df["lag"],
        y=ll_df["correlation"],
        marker_color=np.where(ll_df["correlation"] >= 0, COLORS["accent_4"], COLORS["accent_3"]),
        name="Correlação Cruzada",
    ))
    fig.update_layout(
        title="Correlação Cruzada (Lead / Lag): Variação da Curva vs Retorno Ibovespa",
        xaxis_title="Lag em Dias (Negativo = Ações antecipam a Curva | Positivo = Curva antecipa as Ações)",
        yaxis_title="Correlação de Pearson",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _show_demo_impact():
    """Demo view for asset impact."""
    scenarios = ["-200bps", "-100bps", "-50bps", "+50bps", "+100bps", "+200bps"]
    assets = ["IBOVESPA", "USD_BRL", "IMAB11", "IFIX"]

    demo_matrix = pd.DataFrame(
        [
            [+12.4, -6.1, +8.5, +7.2],
            [+6.2,  -3.2, +4.8, +3.9],
            [+2.1,  -1.1, +1.9, +1.5],
            [-2.4,  +1.8, -1.8, -1.3],
            [-6.8,  +4.2, -4.5, -3.8],
            [-13.5, +8.6, -9.1, -7.4],
        ],
        index=scenarios,
        columns=assets,
    )

    kpis = [
        {"label": "Choque Típico", "value": "+100bps (Abertura)"},
        {"label": "Ibovespa (Mediana 21d)", "value": "-6.8%", "delta": -6.8, "suffix": "%"},
        {"label": "USD/BRL (Mediana 21d)", "value": "+4.2%", "delta": 4.2, "suffix": "%"},
        {"label": "IMAB11 (Mediana 21d)", "value": "-4.5%", "delta": -4.5, "suffix": "%"},
    ]
    render_kpi_row(kpis)

    fig = px.imshow(
        demo_matrix,
        color_continuous_scale=["#E94560", "#16213E", "#00D2FF"],
        text_auto=".1f",
        labels=dict(x="Classe de Ativo", y="Choque na Curva", color="Retorno (%)"),
    )
    fig.update_layout(title="Sensibilidade Cruzada Histórica (Demonstração)", height=420)
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
