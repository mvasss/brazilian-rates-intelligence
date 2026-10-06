"""
Página 4 — Event Studies
"Como o mercado reagiu historicamente a choques macroeconômicos?"

Event study clássico em janelas [-5, +20] para decisões do COPOM, FOMC,
surpresas de inflação Focus e eventos fiscais.
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
from src.analytics.event_study import (
    run_event_study,
    run_multi_asset_event_study,
    format_event_study_table,
)

st.set_page_config(page_title="BRI — Event Studies", page_icon="⚡", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_event_study_data(start, end):
    """Load events and asset returns."""
    try:
        from src.collectors.events_collector import fetch_all_events
        from src.collectors.market_collector import fetch_market_data
        try:
            from src.processors.returns_processor import compute_all_asset_returns
        except ImportError:
            from src.processors.returns_processor import compute_returns as compute_all_asset_returns

        events = fetch_all_events(start=start, end=end)
        market = fetch_market_data(start=start, end=end, include_sectors=False)
        returns = compute_all_asset_returns(market) if not market.empty else pd.DataFrame()

        return events, returns
    except Exception as e:
        st.error(f"Erro ao carregar dados de eventos: {e}")
        return pd.DataFrame(), pd.DataFrame()


def main():
    params = render_sidebar()
    start = params["start_date"]
    end = params["end_date"]

    st.markdown("# ⚡ Event Studies")
    st.markdown("*Transmissão de surpresas e decisões de política econômica para os preços de mercado.*")

    events, returns = load_event_study_data(start, end)

    if events.empty or returns.empty:
        st.warning("Dados reais não carregados. Apresentando estudo de eventos demonstrativo.")
        _show_demo_events()
        return

    # Friendly dictionaries for intuitive UI
    asset_labels = {
        "bova11": "BOVA11 (ETF Ibovespa)",
        "ibovespa": "Ibovespa (Índice de Ações)",
        "ifix": "IFIX (Fundos Imobiliários)",
        "imab11": "IMAB11 (Títulos Públicos IPCA)",
        "usd_brl": "USD/BRL (Dólar Comercial)",
    }
    event_type_labels = {
        "copom": "Decisões do COPOM (Taxa Selic)",
        "focus_surprise": "Surpresas do Relatório Focus",
        "fomc": "Decisões do FOMC (Fed EUA)",
        "fiscal": "Eventos Fiscais e Reformas",
    }
    direction_labels = {
        "hike": "Elevação / Aperto (Hike)",
        "cut": "Corte de Juros (Cut)",
        "hold": "Manutenção (Sem Mudança)",
        "hawkish": "Surpresa de Alta (Hawkish)",
        "dovish": "Surpresa de Queda (Dovish)",
        "deterioration": "Deterioração Fiscal",
        "consolidation": "Ajuste / Consolidação Fiscal",
    }

    # Event selection controls
    c1, c2, c3 = st.columns(3)
    with c1:
        event_types = sorted(events["event_type"].dropna().unique().tolist())
        sel_type = st.selectbox(
            "Tipo de Evento Econômico",
            ["Todos"] + event_types,
            format_func=lambda x: event_type_labels.get(x, x if x != "Todos" else "Todos os Eventos"),
        )
    with c2:
        dirs = ["Todos"]
        if sel_type != "Todos":
            dirs += sorted(events[events["event_type"] == sel_type]["direction"].dropna().unique().tolist())
        sel_dir = st.selectbox(
            "Direção do Choque",
            dirs,
            format_func=lambda x: direction_labels.get(x, x if x != "Todos" else "Todas as Direções"),
        )
    with c3:
        asset_options = list(returns.columns)
        sel_asset = st.selectbox(
            "Ativo em Análise",
            asset_options,
            index=0,
            format_func=lambda x: asset_labels.get(x.lower(), x.upper()),
        )

    filter_type = None if sel_type == "Todos" else sel_type
    filter_dir = None if sel_dir == "Todos" else sel_dir

    result = run_event_study(
        events=events,
        returns=returns,
        asset=sel_asset,
        event_type=filter_type,
        direction=filter_dir,
    )

    if result is None or result.n_events == 0:
        st.info("Nenhum evento com dados suficientes encontrado para os filtros selecionados.")
        return

    # KPIs
    car_5d = result.car.loc[5, "car"] * 100 if 5 in result.car.index else 0
    t_stat_5d = result.t_stats.get(5, 0)
    p_val_5d = result.p_values.get(5, 1)
    sig_label = "Estatisticamente Significativo (p < 0.05)" if p_val_5d < 0.05 else "Oscilação Normal (Não significativo)"
    asset_display = asset_labels.get(sel_asset.lower(), sel_asset.upper())

    kpis = [
        {"label": "Total de Decisões Mapeadas", "value": f"{result.n_events} eventos"},
        {"label": f"Impacto Médio em 5 Dias ({asset_display})", "value": f"{car_5d:+.2f}%", "delta": round(car_5d, 2), "suffix": "%"},
        {"label": "Confiabilidade Estatística (t-stat)", "value": f"{t_stat_5d:.2f}"},
        {"label": "Validação Estatística", "value": sig_label},
    ]
    render_kpi_row(kpis)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "📈 Trajetória Média do Impacto (CAR)",
        "🔍 Dispersão Individual dos Eventos",
        "📋 Comparativo Entre Classes de Ativos",
    ])

    with tab1:
        _plot_car_trajectory(result, asset_display)

    with tab2:
        _plot_individual_events(result, asset_display)

    with tab3:
        _plot_multi_asset(events, returns, filter_type, filter_dir, asset_labels)


def _plot_car_trajectory(result, asset_name):
    """Plot mean Cumulative Abnormal Return with error bands."""
    car_series = result.car["car"] * 100
    days = car_series.index.tolist()
    std_err = (result.car_by_event.std() / np.sqrt(result.n_events) * 100).reindex(days).fillna(0)

    upper = car_series + 1.96 * std_err
    lower = car_series - 1.96 * std_err

    fig = go.Figure()

    # Confidence interval band
    fig.add_trace(go.Scatter(
        x=days + days[::-1],
        y=upper.tolist() + lower.tolist()[::-1],
        fill="toself",
        fillcolor="rgba(0, 210, 255, 0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        hoverinfo="skip",
        name="IC 95%",
    ))

    # Mean CAR line
    fig.add_trace(go.Scatter(
        x=days,
        y=car_series,
        mode="lines+markers",
        name="CAR Médio",
        line=dict(color=COLORS["accent_4"], width=3),
    ))

    # Reference lines
    fig.add_vline(x=0, line_dash="dash", line_color="#FF1744", annotation_text="Data do Evento (t=0)")
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_width=1)

    fig.update_layout(
        title=f"Retorno Anormal Acumulado (CAR) — {asset_name.upper()} (N={result.n_events})",
        xaxis_title="Dias Úteis em Relação ao Evento (t)",
        yaxis_title="Retorno Anormal Acumulado (%)",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_individual_events(result, asset_name):
    """Plot individual event trajectories behind the mean."""
    fig = go.Figure()

    # Individual traces
    for dt, row in result.car_by_event.iterrows():
        fig.add_trace(go.Scatter(
            x=row.index,
            y=row.values * 100,
            mode="lines",
            line=dict(color="rgba(255, 255, 255, 0.12)", width=1),
            hoverinfo="y+text",
            text=str(dt)[:10],
            showlegend=False,
        ))

    # Mean trace
    mean_car = result.car["car"] * 100
    fig.add_trace(go.Scatter(
        x=mean_car.index,
        y=mean_car.values,
        mode="lines",
        name="Média",
        line=dict(color=COLORS["accent_3"], width=3.5),
    ))

    fig.add_vline(x=0, line_dash="dash", line_color="#FFD600")
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)")

    fig.update_layout(
        title=f"Dispersão de Respostas Individuais — {asset_name.upper()}",
        xaxis_title="Dias Úteis em Torno do Evento",
        yaxis_title="CAR (%)",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plot_multi_asset(events, returns, event_type, direction, asset_labels: dict | None = None):
    """Multi-asset summary table."""
    multi_res = run_multi_asset_event_study(events, returns, event_type=event_type, direction=direction)
    if not multi_res:
        st.info("Dados indisponíveis para múltiplos ativos.")
        return

    table_5d = format_event_study_table(multi_res, window=5)
    if not table_5d.empty:
        if asset_labels:
            table_5d["asset"] = table_5d["asset"].map(lambda x: asset_labels.get(str(x).lower(), str(x).upper()))
        
        rename_cols = {
            "asset": "Classe de Ativo",
            "CAR[0,+5] (%)": "Retorno Acumulado Médio 5D (%) [CAR]",
            "t-stat": "Estatística-t (t-stat)",
            "p-value": "P-Valor (Significância)",
            "n_events": "Qtd. de Eventos",
        }
        table_5d = table_5d.rename(columns=rename_cols)

    st.markdown("### 📊 Resposta dos Ativos na Janela de 5 Dias [0, +5]")
    st.dataframe(table_5d, use_container_width=True)
    st.caption("* p < 0.10, ** p < 0.05, *** p < 0.01 (Teste t bicaudal — asteriscos indicam significância estatística)")


def _show_demo_events():
    """Demo view with synthetic events."""
    days = list(range(-5, 21))
    np.random.seed(42)

    mean_trajectory = np.cumsum(np.concatenate([[0], np.random.normal(-0.15, 0.3, size=25)]))
    mean_trajectory[:5] = np.random.normal(0, 0.1, size=5)

    kpis = [
        {"label": "Total de Eventos (Demo)", "value": "24 decisões COPOM"},
        {"label": "CAR t+5 (Ibovespa)", "value": "-1.45%", "delta": -1.45, "suffix": "%"},
        {"label": "T-Stat (t+5)", "value": "-2.34"},
        {"label": "Significância", "value": "p < 0.05 (Significante)"},
    ]
    render_kpi_row(kpis)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days, y=mean_trajectory,
        mode="lines+markers",
        name="CAR Médio (Demo)",
        line=dict(color=COLORS["accent_4"], width=3),
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#FF1744", annotation_text="COPOM")
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)")
    fig.update_layout(title="Impacto Médio de Elevação da Selic sobre o Ibovespa (Demo)", height=450)
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
