"""
Página 3 — Regimes de Mercado
"Em qual regime estamos?"

Classificação de regimes (Risk-on, Risk-off, Inflacionário, Desinflacionário),
timeline histórica, radar de drivers e performance dos ativos por regime.
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
from src.analytics.regime_classifier import (
    REGIME_COLORS,
    REGIME_EMOJI,
    REGIME_LABELS,
    build_regime_features,
    classify_regimes_rules,
    classify_regimes_gmm,
    get_current_regime,
    regime_performance_table,
)

st.set_page_config(page_title="BRI — Regimes", page_icon="🔄", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_regime_data(start, end):
    """Load data and compute regime classifications."""
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

        if curve_metrics.empty or market.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        features = build_regime_features(curve_metrics, market, focus)
        rules_df = classify_regimes_rules(features)
        gmm_df = classify_regimes_gmm(features)

        return rules_df, gmm_df, features, returns
    except Exception as e:
        st.error(f"Erro ao computar regimes: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# 🔄 Regimes de Mercado")
    st.markdown("*Em qual regime macroeconômico estamos e como os ativos se comportam?*")

    rules_df, gmm_df, features, returns = load_regime_data(start, end)

    if rules_df.empty:
        st.warning("Dados insuficientes para classificação ao vivo. Exibindo demonstração quantitativa.")
        _show_demo_regimes()
        return

    regime_names_pt = {
        "risk_on": "Apetite a Risco (Risk-On)",
        "risk_off": "Aversão a Risco (Risk-Off)",
        "inflationary": "Choque Inflacionário",
        "disinflationary": "Desinflação / Alívio",
    }
    regime_name = regime_names_pt.get(curr["regime"], curr["regime"].replace("_", " ").title())

    # Calculate days in current regime
    r_series = rules_df["regime"]
    streak = 1
    for i in range(len(r_series) - 2, -1, -1):
        if r_series.iloc[i] == curr["regime"]:
            streak += 1
        else:
            break

    kpis = [
        {"label": "Regime de Mercado Atual", "value": f"{curr['emoji']} {regime_name}"},
        {"label": "Grau de Confiança do Sinal", "value": f"{curr['confidence'] * 100:.1f}%"},
        {"label": "Tempo no Regime Atual", "value": f"{streak} dias úteis"},
        {"label": "Validação Estatística (GMM)", "value": "Consistente (Modelos Convergem)" if not gmm_df.empty and gmm_df.iloc[-1].get("regime_gmm") == curr["regime"] else "Transição em Andamento"},
    ]
    render_kpi_row(kpis)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "🗺️ Linha do Tempo Histórica",
        "🧭 Forças Propulsoras do Regime (Drivers)",
        "📊 Retornos e Risco por Regime",
    ])

    with tab1:
        _plot_timeline(rules_df, features)

    with tab2:
        _plot_drivers(features, rules_df)

    with tab3:
        if not returns.empty:
            _plot_performance(rules_df, returns, regime_names_pt)
        else:
            st.info("Séries de retornos indisponíveis para a janela selecionada.")


def _plot_timeline(rules_df: pd.DataFrame, features: pd.DataFrame):
    """Plot regime timeline with background bands."""
    fig = go.Figure()

    # Map regimes to numerical levels for visualization
    regime_map = {"risk_on": 1, "disinflationary": 0.5, "inflationary": -0.5, "risk_off": -1}
    y_vals = rules_df["regime"].map(regime_map)

    for regime_key, color in REGIME_COLORS.items():
        mask = rules_df["regime"] == regime_key
        if mask.any():
            fig.add_trace(go.Scatter(
                x=rules_df.index[mask],
                y=y_vals[mask],
                mode="markers",
                name=f"{REGIME_EMOJI.get(regime_key, '')} {regime_key.replace('_', ' ').title()}",
                marker=dict(size=8, color=color, symbol="square"),
            ))

    # Add trend line
    if "equity_change" in features.columns:
        fig.add_trace(go.Scatter(
            x=features.index,
            y=features["equity_change"],
            name="Ibovespa Z-Score",
            line=dict(color="rgba(255, 255, 255, 0.4)", width=1, dash="dot"),
            yaxis="y2"
        ))

    fig.update_layout(
        title="Histórico de Classificação de Regimes",
        yaxis=dict(
            tickmode="array",
            tickvals=[1, 0.5, -0.5, -1],
            ticktext=["🟢 Risk-on", "🔵 Disinfl.", "🟡 Infl.", "🔴 Risk-off"],
            title="Regime",
        ),
        yaxis2=dict(
            title="Equity Z-Score",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_drivers(features: pd.DataFrame, rules_df: pd.DataFrame):
    """Plot the underlying rolling Z-score components with friendly labels."""
    fig = go.Figure()
    drivers = [c for c in features.columns if c.endswith("_change") or c.endswith("_level")]

    driver_labels = {
        "slope_change": "Variação da Inclinação da Curva (Slope)",
        "brl_change": "Variação Cambial (Dólar USD/BRL)",
        "equity_change": "Variação da Bolsa (Ibovespa)",
        "inflation_exp_change": "Expectativa de Inflação (Focus IPCA)",
        "vix_level": "Índice de Aversão Global (VIX)",
    }

    colors_cycle = CHART_COLORS
    for i, col in enumerate(drivers):
        fig.add_trace(go.Scatter(
            x=features.index,
            y=features[col],
            name=driver_labels.get(col, col.replace("_", " ").title()),
            line=dict(color=colors_cycle[i % len(colors_cycle)], width=1.8),
        ))

    fig.add_hline(y=0.5, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)", annotation_text="+0.5σ (Pressão)")
    fig.add_hline(y=-0.5, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)", annotation_text="-0.5σ (Alívio)")

    fig.update_layout(
        title="Forças Propulsoras dos Regimes (Indicadores Normalizados em Desvios σ)",
        yaxis_title="Intensidade da Variação (Desvios σ)",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_performance(rules_df: pd.DataFrame, returns: pd.DataFrame, regime_names_pt: dict):
    """Display asset returns conditional on regime with intuitive labels."""
    table = regime_performance_table(rules_df, returns)
    if table.empty:
        st.info("Amostra insuficiente para cálculo de retorno condicional.")
        return

    col_labels = {
        "n_days": "Dias no Regime",
        "bova11_ann_ret": "BOVA11 Retorno (%)",
        "bova11_ann_vol": "BOVA11 Volatilidade (%)",
        "bova11_hit_rate": "BOVA11 % Positivo",
        "ifix_ann_ret": "IFIX Retorno (%)",
        "ifix_ann_vol": "IFIX Volatilidade (%)",
        "ifix_hit_rate": "IFIX % Positivo",
        "imab11_ann_ret": "IMAB11 Retorno (%)",
        "imab11_ann_vol": "IMAB11 Volatilidade (%)",
        "imab11_hit_rate": "IMAB11 % Positivo",
        "usd_brl_ann_ret": "Dólar Variação (%)",
        "usd_brl_ann_vol": "Dólar Volatilidade (%)",
        "usd_brl_hit_rate": "Dólar % Positivo",
        "ibovespa_ann_ret": "Ibovespa Retorno (%)",
        "ibovespa_ann_vol": "Ibovespa Volatilidade (%)",
        "ibovespa_hit_rate": "Ibovespa % Positivo",
    }

    display_table = table.copy()
    display_table.index = [regime_names_pt.get(idx, idx) for idx in display_table.index]
    display_table = display_table.rename(columns=col_labels)

    st.markdown("### 📋 Retornos Anualizados, Volatilidade e Taxa de Positividade por Regime")
    st.dataframe(display_table.style.format("{:.2f}"), use_container_width=True)

    # Bar chart of mean annualized returns
    ret_cols = [c for c in table.columns if c.endswith("_ann_ret")]
    if ret_cols:
        asset_names_map = {
            "BOVA11": "BOVA11 (ETF Ibov)",
            "IFIX": "IFIX (Fundos Imob.)",
            "IMAB11": "IMAB11 (Títulos IPCA)",
            "USD_BRL": "Dólar (USD/BRL)",
            "IBOVESPA": "Ibovespa (Índice)",
        }
        chart_data = table[ret_cols].reset_index()
        chart_data.columns = [c.replace("_ann_ret", "").upper() for c in chart_data.columns]
        chart_data["REGIME"] = chart_data["REGIME"].map(lambda x: regime_names_pt.get(x.lower(), x))

        melted_chart = chart_data.melt(id_vars=["REGIME"], var_name="Ativo", value_name="Retorno Anualizado (%)")
        melted_chart["Ativo"] = melted_chart["Ativo"].map(lambda x: asset_names_map.get(x, x))

        fig = px.bar(
            melted_chart,
            x="Ativo",
            y="Retorno Anualizado (%)",
            color="REGIME",
            barmode="group",
            title="Comparativo de Retorno Anualizado por Classe de Ativo e Regime",
        )
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)


def _show_demo_regimes():
    """Fallback interactive demo when live data feeds are offline."""
    dates = pd.bdate_range("2021-01-01", "2024-12-31")
    np.random.seed(42)

    # Create realistic regime cycles
    regimes = []
    current = "risk_on"
    choices = list(REGIME_LABELS.values())
    for _ in range(len(dates)):
        if np.random.rand() < 0.03:
            current = np.random.choice(choices)
        regimes.append(current)

    demo_rules = pd.DataFrame({
        "regime": regimes,
        "confidence": np.random.uniform(0.65, 0.95, size=len(dates)),
    }, index=dates)

    demo_features = pd.DataFrame({
        "slope_change": np.random.normal(0, 1, size=len(dates)),
        "brl_change": np.random.normal(0, 1, size=len(dates)),
        "equity_change": np.random.normal(0, 1, size=len(dates)),
        "inflation_exp_change": np.random.normal(0, 1, size=len(dates)),
    }, index=dates)

    demo_returns = pd.DataFrame({
        "ibovespa": np.random.normal(0.0005, 0.015, size=len(dates)),
        "ifix": np.random.normal(0.0003, 0.005, size=len(dates)),
        "usd_brl": np.random.normal(0.0001, 0.009, size=len(dates)),
        "imab11": np.random.normal(0.0004, 0.007, size=len(dates)),
    }, index=dates)

    curr = get_current_regime(demo_rules)
    kpis = [
        {"label": "Regime Atual (Demo)", "value": f"{curr['emoji']} {curr['regime'].replace('_', ' ').title()}"},
        {"label": "Confiança", "value": f"{curr['confidence'] * 100:.1f}%"},
        {"label": "Ativo Destaque", "value": "IMAB11 (+14.2% a.a.)"},
        {"label": "Volatilidade Geral", "value": "Moderada (16.8%)"},
    ]
    render_kpi_row(kpis)

    tab1, tab2, tab3 = st.tabs(["🗺️ Timeline Histórica", "🧭 Drivers do Regime", "📊 Retornos por Regime"])
    with tab1:
        _plot_timeline(demo_rules, demo_features)
    with tab2:
        _plot_drivers(demo_features, demo_rules)
    with tab3:
        _plot_performance(demo_rules, demo_returns)


if __name__ == "__main__":
    main()
