"""
Macro Processor — Clean, transform, and enrich macro data.

Handles:
- Interpolation of monthly → daily (forward fill)
- Z-score normalization
- MoM / YoY variations
- Unified macro panel construction
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def interpolate_to_daily(
    monthly_df: pd.DataFrame,
    method: str = "ffill",
) -> pd.DataFrame:
    """
    Interpolate monthly series to daily frequency.

    Uses forward-fill by default (appropriate for macro indicators that
    represent the latest known value until the next release).
    """
    daily_idx = pd.bdate_range(monthly_df.index.min(), monthly_df.index.max())
    daily = monthly_df.reindex(daily_idx)

    if method == "ffill":
        daily = daily.ffill()
    elif method == "linear":
        daily = daily.interpolate(method="linear")

    daily.index.name = "date"
    return daily


def compute_zscore(
    series: pd.Series,
    window: int = 252,
    min_periods: int = 63,
) -> pd.Series:
    """
    Rolling z-score: (x - rolling_mean) / rolling_std.

    Parameters
    ----------
    window : lookback window in business days.
    min_periods : minimum observations required.
    """
    roll_mean = series.rolling(window, min_periods=min_periods).mean()
    roll_std = series.rolling(window, min_periods=min_periods).std()
    z = (series - roll_mean) / roll_std.replace(0, np.nan)
    return z


def compute_variations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add MoM and YoY percentage change columns for each series.

    For monthly data: MoM = 1-period diff, YoY = 12-period diff.
    For daily data: MoM = 21-period, YoY = 252-period.
    """
    freq = pd.infer_freq(df.index)
    is_monthly = freq and "M" in freq.upper()

    mom_periods = 1 if is_monthly else 21
    yoy_periods = 12 if is_monthly else 252

    result = df.copy()
    for col in df.columns:
        result[f"{col}_mom"] = df[col].pct_change(mom_periods) * 100
        result[f"{col}_yoy"] = df[col].pct_change(yoy_periods) * 100

    return result


def build_macro_panel(
    sgs_data: pd.DataFrame,
    focus_data: pd.DataFrame | None = None,
    market_data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build a unified daily macro panel from multiple sources.

    Aligns all series to business day frequency. Monthly macro data is
    forward-filled. Market data is used as-is (already daily).

    Returns
    -------
    DataFrame with all macro + focus + market columns aligned on business days.
    """
    # Separate daily and monthly SGS series
    daily_cols = []
    monthly_cols = []
    for col in sgs_data.columns:
        # Check if series has less than one observation per week on average
        non_null = sgs_data[col].dropna()
        if len(non_null) < 2:
            continue
        avg_gap = (non_null.index[-1] - non_null.index[0]).days / len(non_null)
        if avg_gap > 15:
            monthly_cols.append(col)
        else:
            daily_cols.append(col)

    panels = []

    # Daily SGS series
    if daily_cols:
        daily_sgs = sgs_data[daily_cols].copy()
        panels.append(daily_sgs)

    # Monthly SGS series → forward-fill to daily
    if monthly_cols:
        monthly_sgs = sgs_data[monthly_cols].dropna(how="all")
        if not monthly_sgs.empty:
            monthly_daily = interpolate_to_daily(monthly_sgs)
            panels.append(monthly_daily)

    # Focus expectations
    if focus_data is not None and not focus_data.empty:
        focus_daily = interpolate_to_daily(focus_data)
        panels.append(focus_daily)

    # Market data
    if market_data is not None and not market_data.empty:
        panels.append(market_data)

    if not panels:
        return pd.DataFrame()

    # Merge on date index
    panel = panels[0]
    for p in panels[1:]:
        panel = panel.join(p, how="outer", rsuffix="_dup")

    # Remove duplicate columns
    dup_cols = [c for c in panel.columns if c.endswith("_dup")]
    panel = panel.drop(columns=dup_cols)

    # Forward-fill gaps (max 5 business days)
    panel = panel.ffill(limit=5)
    panel.index.name = "date"

    return panel
