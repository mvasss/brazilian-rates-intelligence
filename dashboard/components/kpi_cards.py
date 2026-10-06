"""
KPI Cards — Styled metric card components.
"""
import streamlit as st
from dashboard.components.theme import COLORS


def render_kpi_row(metrics: list[dict]):
    """
    Render a row of KPI metric cards.

    Each metric dict should have: label, value, delta (optional), suffix (optional).
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            delta = m.get("delta")
            delta_str = None
            delta_color = "normal"

            if delta is not None:
                suffix = m.get("suffix", "")
                if isinstance(delta, (int, float)):
                    delta_str = f"{delta:+.2f}{suffix}"
                    delta_color = "normal" if m.get("inverse", False) else "normal"
                else:
                    delta_str = str(delta)

            st.metric(
                label=m["label"],
                value=m["value"],
                delta=delta_str,
                delta_color=delta_color,
            )


def render_signal_gauge(score: float, label: str = "Rates Pressure Score"):
    """
    Render a visual gauge for the rates signal score.

    Uses colored HTML/CSS to display the score magnitude and direction.
    """
    if score > 50:
        color = COLORS["negative"]
        icon = "🔴"
        bar_pct = min(score, 100)
    elif score > 20:
        color = "#FF6D00"
        icon = "🟠"
        bar_pct = min(score, 100)
    elif score > -20:
        color = COLORS["neutral"]
        icon = "🟡"
        bar_pct = 50  # center
    elif score > -50:
        color = COLORS["info"]
        icon = "🔵"
        bar_pct = max(100 + score, 0)
    else:
        color = COLORS["positive"]
        icon = "🟢"
        bar_pct = max(100 + score, 0)

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {COLORS['bg_card']} 0%, {COLORS['bg_secondary']} 100%);
            border: 1px solid {COLORS['accent_1']};
            border-radius: 16px;
            padding: 24px;
            text-align: center;
        ">
            <p style="color: {COLORS['text_secondary']}; font-size: 0.85rem; margin: 0 0 8px 0;
               text-transform: uppercase; letter-spacing: 0.05em;">
                {label}
            </p>
            <p style="font-size: 3rem; font-weight: 700; color: {color}; margin: 0; line-height: 1.2;">
                {icon} {score:+.0f}
            </p>
            <div style="
                background: rgba(255,255,255,0.05);
                border-radius: 8px;
                height: 8px;
                margin: 16px 0 8px 0;
                overflow: hidden;
            ">
                <div style="
                    background: linear-gradient(90deg, {COLORS['positive']}, {COLORS['neutral']}, {COLORS['negative']});
                    height: 100%;
                    width: 100%;
                    border-radius: 8px;
                "></div>
            </div>
            <div style="display: flex; justify-content: space-between;
                        color: {COLORS['text_muted']}; font-size: 0.7rem;">
                <span>-100 (Queda)</span>
                <span>0</span>
                <span>+100 (Alta)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_regime_badge(regime: str, confidence: float, emoji: str = "⚪"):
    """Render a styled badge for the current market regime."""
    regime_colors = {
        "risk_on": COLORS["positive"],
        "risk_off": COLORS["negative"],
        "inflationary": COLORS["neutral"],
        "disinflationary": COLORS["info"],
    }
    color = regime_colors.get(regime, COLORS["text_muted"])
    display_name = regime.replace("_", " ").title()

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {COLORS['bg_card']} 0%, rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15) 100%);
            border: 2px solid {color};
            border-radius: 16px;
            padding: 24px;
            text-align: center;
        ">
            <p style="font-size: 2.5rem; margin: 0;">{emoji}</p>
            <p style="font-size: 1.4rem; font-weight: 700; color: {color}; margin: 8px 0 4px 0;">
                {display_name}
            </p>
            <p style="color: {COLORS['text_secondary']}; font-size: 0.85rem; margin: 0;">
                Confiança: {confidence:.0%}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
