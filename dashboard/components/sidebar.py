"""
Sidebar — Shared sidebar for all dashboard pages.

Provides:
- Date range selector
- Data refresh controls
- Navigation info
"""
import streamlit as st
from datetime import datetime, timedelta

from dashboard.components.theme import COLORS


def render_sidebar():
    """Render the shared sidebar and return selected parameters."""
    with st.sidebar:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 20px 0 10px 0;">
                <h1 style="
                    font-size: 1.4rem;
                    background: linear-gradient(90deg, #00D2FF, #E94560);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin: 0;
                ">📈 BRI</h1>
                <p style="color: {COLORS['text_secondary']}; font-size: 0.75rem; margin: 4px 0 0 0;">
                    Brazilian Rates Intelligence
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Date range
        st.markdown(f"**📅 Período de Análise**")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Início",
                value=datetime(2020, 1, 1),
                min_value=datetime(2019, 1, 1),
                max_value=datetime.now(),
                key="sidebar_start",
            )
        with col2:
            end_date = st.date_input(
                "Fim",
                value=datetime.now(),
                min_value=datetime(2019, 1, 1),
                max_value=datetime.now(),
                key="sidebar_end",
            )

        st.markdown("---")

        # Quick date ranges
        st.markdown(f"**⚡ Atalhos**")
        preset = st.radio(
            "Período pré-definido",
            ["Customizado", "1 Ano", "2 Anos", "3 Anos", "5 Anos", "Máximo"],
            index=0,
            key="sidebar_preset",
            horizontal=True,
        )

        if preset != "Customizado":
            end_date = datetime.now().date()
            years = {"1 Ano": 1, "2 Anos": 2, "3 Anos": 3, "5 Anos": 5, "Máximo": 7}
            start_date = end_date - timedelta(days=365 * years.get(preset, 5))

        st.markdown("---")

        # Info
        with st.expander("ℹ️ Sobre", expanded=False):
            st.markdown(
                f"""
                <div style="color: {COLORS['text_secondary']}; font-size: 0.8rem;">
                    <p><strong>Fontes de dados:</strong></p>
                    <ul>
                        <li>BCB SGS / Focus</li>
                        <li>B3 / ANBIMA (pyettj)</li>
                        <li>Yahoo Finance</li>
                        <li>IPEA</li>
                    </ul>
                    <p><strong>Metodologia:</strong></p>
                    <p>Framework quantitativo para análise da curva de juros brasileira.
                    Regime classification, event studies e rates signal.</p>
                    <p style="color: {COLORS['text_muted']}; font-size: 0.7rem;">
                    ⚠️ Este dashboard não constitui recomendação de investimento.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Refresh button
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
    }
