"""
Asset Impact — Macro → Market transmission analysis.

Central question: "When rates move X bps, what happens to assets?"

Analysis:
- Identify historical rate move scenarios (±50, ±100, ±200 bps)
- Compute median asset returns during those periods
- Decompose impact by market regime
- Lead/lag analysis
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def identify_rate_scenarios(
    curve_level: pd.Series,
    thresholds_bps: list[int] | None = None,
    window: int = 63,
) -> pd.DataFrame:
    """
    Identify periods where rates moved by at least X bps over a window.

    Parameters
    ----------
    curve_level : time series of a curve metric (e.g., level or 2Y rate).
    thresholds_bps : list of thresholds in basis points (e.g., [50, 100, 200]).
    window : rolling window in business days for computing the move.

    Returns
    -------
    DataFrame with columns: date, move_bps, scenario.
    """
    if thresholds_bps is None:
        thresholds_bps = [50, 100, 200]

    moves = (curve_level.diff(window) * 100).dropna()  # rates are in %

    scenarios = []
    for threshold in sorted(thresholds_bps):
        # Upward moves
        up_dates = moves[moves >= threshold].index
        for d in up_dates:
            scenarios.append({
                "date": d,
                "move_bps": moves.loc[d],
                "scenario": f"+{threshold}bps",
                "direction": "up",
            })

        # Downward moves
        dn_dates = moves[moves <= -threshold].index
        for d in dn_dates:
            scenarios.append({
                "date": d,
                "move_bps": moves.loc[d],
                "scenario": f"-{threshold}bps",
                "direction": "down",
            })

    df = pd.DataFrame(scenarios)
    if not df.empty:
        df = df.drop_duplicates(subset=["date"]).sort_values("date")
        # Keep only the largest threshold hit for each date
        df["abs_threshold"] = df["scenario"].str.extract(r"(\d+)").astype(int)
        df = df.sort_values(["date", "abs_threshold"], ascending=[True, False])
        df = df.drop_duplicates(subset=["date"], keep="first")
        df = df.drop(columns=["abs_threshold"]).reset_index(drop=True)

    return df


def compute_asset_response(
    scenarios: pd.DataFrame,
    asset_returns: pd.DataFrame,
    forward_windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    For each rate scenario, compute forward asset returns.

    Parameters
    ----------
    forward_windows : list of forward periods in trading days.
                      Default: [5, 10, 21, 63].

    Returns
    -------
    DataFrame with scenario info + forward returns for each asset × window.
    """
    if forward_windows is None:
        forward_windows = [5, 10, 21, 63]

    results = []
    all_dates = asset_returns.index

    for _, event in scenarios.iterrows():
        d = pd.to_datetime(event["date"])
        idx = all_dates.searchsorted(d)
        if idx >= len(all_dates):
            continue

        row = {
            "date": d,
            "scenario": event["scenario"],
            "direction": event["direction"],
            "move_bps": event["move_bps"],
        }

        for w in forward_windows:
            end_idx = idx + w
            if end_idx >= len(all_dates):
                continue
            for asset in asset_returns.columns:
                cum_ret = asset_returns[asset].iloc[idx:end_idx].sum()
                row[f"{asset}_{w}d"] = cum_ret * 100

        results.append(row)

    return pd.DataFrame(results)


def scenario_impact_summary(
    responses: pd.DataFrame,
    regime_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Summarize asset impact by scenario.

    Returns median, mean, std, and % positive for each scenario × asset.
    Optionally decomposes by regime.
    """
    if responses.empty:
        return pd.DataFrame()

    # Add regime if available
    if regime_df is not None and not regime_df.empty:
        responses = responses.copy()
        responses["regime"] = responses["date"].apply(
            lambda d: _get_regime_at_date(d, regime_df)
        )
        group_cols = ["scenario", "regime"]
    else:
        group_cols = ["scenario"]

    # Identify return columns
    ret_cols = [c for c in responses.columns
                if any(c.endswith(f"_{w}d") for w in [5, 10, 21, 63])]

    stats = []
    for name, group in responses.groupby(group_cols):
        if isinstance(name, str):
            row = {"scenario": name}
        else:
            row = dict(zip(group_cols, name))

        row["n_observations"] = len(group)

        for col in ret_cols:
            data = group[col].dropna()
            if len(data) == 0:
                continue
            row[f"{col}_median"] = data.median()
            row[f"{col}_mean"] = data.mean()
            row[f"{col}_std"] = data.std()
            row[f"{col}_pct_positive"] = (data > 0).mean() * 100

        stats.append(row)

    return pd.DataFrame(stats)


def _get_regime_at_date(
    date: pd.Timestamp,
    regime_df: pd.DataFrame,
) -> str:
    """Find the regime classification at a given date."""
    if "regime" not in regime_df.columns:
        return "unknown"
    prior = regime_df[regime_df.index <= date]
    if prior.empty:
        return "unknown"
    return prior.iloc[-1]["regime"]


def compute_lead_lag(
    curve_changes: pd.Series,
    asset_returns: pd.Series,
    max_lag: int = 21,
) -> pd.DataFrame:
    """
    Lead/lag cross-correlation between curve changes and asset returns.

    Negative lag = asset leads curve; Positive lag = curve leads asset.
    """
    correlations = []
    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            corr = curve_changes.corr(asset_returns)
        elif lag > 0:
            corr = curve_changes.shift(lag).corr(asset_returns)
        else:
            corr = curve_changes.corr(asset_returns.shift(-lag))

        correlations.append({"lag": lag, "correlation": corr})

    return pd.DataFrame(correlations)


def build_impact_heatmap(
    responses: pd.DataFrame,
    window: int = 21,
) -> pd.DataFrame:
    """
    Build a heatmap-ready DataFrame of median returns by scenario × asset.

    Returns pivot table with scenarios as index and assets as columns.
    """
    ret_cols = [c for c in responses.columns if c.endswith(f"_{window}d")]

    if not ret_cols:
        return pd.DataFrame()

    medians = responses.groupby("scenario")[ret_cols].median()
    # Clean column names
    medians.columns = [c.replace(f"_{window}d", "") for c in medians.columns]

    return medians
