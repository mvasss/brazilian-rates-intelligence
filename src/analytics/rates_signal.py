"""
Rates Signal — Rates Pressure Score model.

Composite score from -100 to +100 indicating directional pressure on rates.

Components:
  w₁ × Inflation_Surprise_Z    (0.30)
  w₂ × Fiscal_Risk_Z           (0.20)
  w₃ × FX_Pressure_Z           (0.25)
  w₄ × Monetary_Expectation_Z  (0.25)

Each component normalized as z-score (252-day rolling window).
Final score scaled to [-100, +100].

Important: This is NOT a buy/sell recommendation. It indicates:
"The model suggests a higher historical probability of..."
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from config.settings import SIGNAL_WEIGHTS, SIGNAL_ZSCORE_WINDOW

logger = logging.getLogger(__name__)


def _rolling_zscore(series: pd.Series, window: int = SIGNAL_ZSCORE_WINDOW) -> pd.Series:
    """Rolling z-score normalization."""
    m = series.rolling(window, min_periods=window // 4).mean()
    s = series.rolling(window, min_periods=window // 4).std()
    return ((series - m) / s.replace(0, np.nan))


def _scale_to_range(z: pd.Series, lo: float = -100, hi: float = 100) -> pd.Series:
    """Scale z-score to [lo, hi] using tanh (smooth capping)."""
    return np.tanh(z / 2) * hi


def compute_inflation_component(
    ipca_realized: pd.Series | None = None,
    ipca_expected: pd.Series | None = None,
    ipca_12m: pd.Series | None = None,
) -> pd.Series:
    """
    Inflation surprise component.

    Primary: IPCA realized - Focus expected (monthly, interpolated).
    Fallback: IPCA 12m rolling z-score.
    """
    if ipca_realized is not None and ipca_expected is not None:
        surprise = ipca_realized - ipca_expected
        surprise = surprise.resample("B").ffill()
        return _rolling_zscore(surprise).rename("inflation_z")

    if ipca_12m is not None:
        chg = ipca_12m.diff()
        chg = chg.resample("B").ffill()
        return _rolling_zscore(chg).rename("inflation_z")

    return pd.Series(dtype=float, name="inflation_z")


def compute_fiscal_component(
    divida_pib: pd.Series | None = None,
    resultado_primario: pd.Series | None = None,
) -> pd.Series:
    """
    Fiscal risk component.

    Uses change in debt/GDP + primary balance deterioration.
    Both as rolling z-scores, equally weighted within the component.
    """
    parts = []

    if divida_pib is not None:
        chg = divida_pib.diff()
        chg = chg.resample("B").ffill()
        parts.append(_rolling_zscore(chg))

    if resultado_primario is not None:
        # Negative primary result = fiscal deterioration = positive pressure
        neg = -resultado_primario.diff()
        neg = neg.resample("B").ffill()
        parts.append(_rolling_zscore(neg))

    if not parts:
        return pd.Series(dtype=float, name="fiscal_z")

    fiscal = pd.concat(parts, axis=1).mean(axis=1)
    return fiscal.rename("fiscal_z")


def compute_fx_component(
    usd_brl: pd.Series,
    window: int = 21,
) -> pd.Series:
    """
    FX pressure component.

    Uses 21-day USD/BRL percentage change z-score.
    Positive = BRL depreciation = upward rate pressure.
    """
    pct_chg = usd_brl.pct_change(window)
    return _rolling_zscore(pct_chg).rename("fx_z")


def compute_monetary_component(
    selic_exp: pd.Series,
    window: int = 21,
) -> pd.Series:
    """
    Monetary expectation component.

    Uses change in Focus Selic expectation z-score.
    Positive = market expects higher Selic = upward rate pressure.
    """
    chg = selic_exp.diff(window)
    chg = chg.resample("B").ffill()
    return _rolling_zscore(chg).rename("monetary_z")


def compute_rates_pressure_score(
    inflation_z: pd.Series,
    fiscal_z: pd.Series,
    fx_z: pd.Series,
    monetary_z: pd.Series,
    weights: dict | None = None,
) -> pd.DataFrame:
    """
    Compute the composite Rates Pressure Score.

    Parameters
    ----------
    *_z : z-score components (output of compute_*_component functions).
    weights : dict of component weights. Default from config.

    Returns
    -------
    DataFrame with columns: score, inflation_z, fiscal_z, fx_z, monetary_z,
    and the raw weighted composite.
    """
    if weights is None:
        weights = SIGNAL_WEIGHTS

    components = pd.DataFrame({
        "inflation_z": inflation_z,
        "fiscal_z": fiscal_z,
        "fx_z": fx_z,
        "monetary_z": monetary_z,
    }).dropna(how="all")

    # Fill NaN components with 0 (neutral)
    components = components.fillna(0)

    # Weighted composite
    composite = (
        components["inflation_z"] * weights["inflation_surprise"]
        + components["fiscal_z"] * weights["fiscal_risk"]
        + components["fx_z"] * weights["fx_pressure"]
        + components["monetary_z"] * weights["monetary_expectation"]
    )

    # Scale to [-100, +100]
    score = _scale_to_range(composite)

    result = components.copy()
    result["composite_z"] = composite
    result["score"] = score
    result.index.name = "date"

    return result


def backtest_signal(
    signal_df: pd.DataFrame,
    curve_future_returns: pd.DataFrame,
    forward_windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    Backtest the Rates Pressure Score against future curve movements.

    Parameters
    ----------
    signal_df : output of compute_rates_pressure_score().
    curve_future_returns : DataFrame with forward returns of curve level.
    forward_windows : list of forward periods in days.

    Returns
    -------
    DataFrame with correlation, directional accuracy, and IC for each window.
    """
    if forward_windows is None:
        forward_windows = [5, 21, 63]

    score = signal_df["score"]

    results = []
    for w in forward_windows:
        # Forward return of curve level
        if f"fwd_{w}d" in curve_future_returns.columns:
            fwd = curve_future_returns[f"fwd_{w}d"]
        else:
            # Try computing from level
            if "level" in curve_future_returns.columns:
                fwd = curve_future_returns["level"].diff(w).shift(-w)
            else:
                continue

        # Align
        aligned = pd.DataFrame({"score": score, "fwd_return": fwd}).dropna()
        if len(aligned) < 30:
            continue

        corr = aligned["score"].corr(aligned["fwd_return"])
        rank_corr = sp_stats.spearmanr(aligned["score"], aligned["fwd_return"])

        # Directional accuracy
        same_sign = (
            (aligned["score"] > 0) & (aligned["fwd_return"] > 0)
        ) | (
            (aligned["score"] < 0) & (aligned["fwd_return"] < 0)
        )
        accuracy = same_sign.mean()

        # Information Coefficient (IC)
        ic = aligned["score"].corr(aligned["fwd_return"])

        results.append({
            "window": f"+{w}d",
            "correlation": corr,
            "rank_correlation": rank_corr.statistic,
            "rank_p_value": rank_corr.pvalue,
            "directional_accuracy": accuracy * 100,
            "n_observations": len(aligned),
            "ic": ic,
        })

    return pd.DataFrame(results)


def get_current_signal(signal_df: pd.DataFrame) -> dict:
    """Return the latest signal reading and decomposition."""
    if signal_df.empty:
        return {"score": 0, "interpretation": "No data"}

    last = signal_df.iloc[-1]
    score = last["score"]

    if score > 50:
        interpretation = "Forte pressão de alta nos juros"
    elif score > 20:
        interpretation = "Pressão moderada de alta nos juros"
    elif score > -20:
        interpretation = "Neutro"
    elif score > -50:
        interpretation = "Pressão moderada de queda nos juros"
    else:
        interpretation = "Forte pressão de queda nos juros"

    return {
        "score": score,
        "interpretation": interpretation,
        "date": signal_df.index[-1],
        "components": {
            "inflation": last.get("inflation_z", 0),
            "fiscal": last.get("fiscal_z", 0),
            "fx": last.get("fx_z", 0),
            "monetary": last.get("monetary_z", 0),
        },
    }
