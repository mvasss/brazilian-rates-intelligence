"""
Brazilian Rates Intelligence — Dashboard Entry Point

A quantitative framework for understanding the Brazilian yield curve.

Run: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from dashboard.components.theme import CUSTOM_CSS, COLORS

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Brazilian Rates Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main():
    # Sidebar navigation
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

    # Home page
    st.markdown(
        f"""
        <div style="text-align: center; padding: 40px 0;">
            <h1 style="
                font-size: 2.8rem;
                background: linear-gradient(90deg, #00D2FF, #E94560, #533483);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 0;
                font-weight: 700;
            ">Brazilian Rates Intelligence</h1>
            <p style="
                color: {COLORS['text_secondary']};
                font-size: 1.1rem;
                margin: 12px 0 0 0;
                font-weight: 300;
            ">A quantitative framework for understanding the Brazilian yield curve</p>
            <p style="
                color: {COLORS['text_muted']};
                font-size: 0.85rem;
                margin: 24px auto 0 auto;
                max-width: 700px;
                line-height: 1.6;
                font-style: italic;
            ">"Como mudanças nas expectativas de inflação, política monetária e risco fiscal
            se propagam pela curva de juros brasileira e pelos principais ativos?"</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Navigation cards
    pages = [
        ("📊", "Macro Overview", "O que está acontecendo?", "1_macro"),
        ("📈", "Yield Curve", "O que a curva está precificando?", "2_yield_curve"),
        ("🎯", "Regimes", "Qual regime estamos?", "3_regimes"),
        ("📋", "Event Studies", "Como o mercado reagiu historicamente?", "4_event_studies"),
        ("💰", "Asset Impact", "O que isso significa para os ativos?", "5_asset_impact"),
        ("🚦", "Rates Signal", "O modelo indica pressão de alta ou queda?", "6_signal"),
    ]

    cols = st.columns(3)
    for i, (icon, title, subtitle, page_key) in enumerate(pages):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, {COLORS['bg_card']} 0%, {COLORS['bg_secondary']} 100%);
                    border: 1px solid {COLORS['accent_1']};
                    border-radius: 16px;
                    padding: 28px;
                    margin: 8px 0;
                    text-align: center;
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                    cursor: pointer;
                    min-height: 160px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                ">
                    <p style="font-size: 2rem; margin: 0 0 8px 0;">{icon}</p>
                    <p style="
                        font-size: 1.1rem; font-weight: 600;
                        color: {COLORS['text_primary']}; margin: 0 0 6px 0;
                    ">{title}</p>
                    <p style="
                        font-size: 0.8rem; color: {COLORS['text_secondary']};
                        margin: 0;
                    ">{subtitle}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Footer
    st.markdown(
        f"""
        <div style="text-align: center; padding: 20px 0; color: {COLORS['text_muted']}; font-size: 0.75rem;">
            <p>⚠️ Este dashboard não constitui recomendação de investimento. Modelo indica probabilidades históricas.</p>
            <p>Fontes: BCB SGS/Focus • B3/ANBIMA • Yahoo Finance • IPEA</p>
            <p>Navegue usando o menu lateral → Pages</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
