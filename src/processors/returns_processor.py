"""
Returns Processor — Asset return metrics.

Computes:
- Log and simple returns
- Realized volatility (multiple windows)
- Drawdown and max drawdown
- Rolling correlations (curve vs assets)
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_returns(
    prices: pd.DataFrame,
    method: str = "log",
) -> pd.DataFrame:
    """
    Compute returns from price data.

    Parameters
    ----------
    method : 'log' for log returns, 'simple' for arithmetic returns.
    """
    if method == "log":
        return np.log(prices / prices.shift(1))
    return prices.pct_change()


def compute_all_asset_returns(
    prices: pd.DataFrame,
    method: str = "simple",
) -> pd.DataFrame:
    """
    Compute percentage or log returns for all assets in the price dataframe.

    Parameters
    ----------
    prices : DataFrame of asset prices indexed by date.
    method : 'simple' or 'log'.

    Returns
    -------
    DataFrame of asset returns.
    """
    return compute_returns(prices, method=method).dropna(how="all")


def compute_realized_vol(
    returns: pd.DataFrame,
    windows: list[int] | None = None,
    annualize: bool = True,
) -> pd.DataFrame:
    """
    Rolling realized volatility.

    Parameters
    ----------
    windows : list of lookback windows in business days.
              Default: [21, 63, 252] (1M, 3M, 1Y).
    annualize : if True, multiply by sqrt(252).
    """
    if windows is None:
        windows = [21, 63, 252]

    factor = np.sqrt(252) if annualize else 1.0

    result = pd.DataFrame(index=returns.index)
    for col in returns.columns:
        for w in windows:
            label = f"{col}_vol_{w}d"
            result[label] = returns[col].rolling(w, min_periods=w // 2).std() * factor

    result.index.name = "date"
    return result


def compute_drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Drawdown from running maximum.

    Returns DataFrame of same shape with drawdown values (negative = loss).
    """
    cummax = prices.cummax()
    dd = (prices - cummax) / cummax
    dd.columns = [f"{c}_drawdown" for c in dd.columns]
    dd.index.name = "date"
    return dd


def compute_max_drawdown(
    prices: pd.DataFrame,
    window: int = 252,
) -> pd.DataFrame:
    """Rolling max drawdown over a window."""
    dd = compute_drawdown(prices)
    mdd = dd.rolling(window, min_periods=window // 2).min()
    mdd.columns = [c.replace("_drawdown", "_mdd") for c in mdd.columns]
    mdd.index.name = "date"
    return mdd


def compute_rolling_correlation(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 63,
) -> pd.Series:
    """Rolling Pearson correlation between two series."""
    return series_a.rolling(window).corr(series_b).rename(
        f"corr_{series_a.name}_{series_b.name}"
    )


def compute_correlation_matrix(
    returns: pd.DataFrame,
    window: int | None = None,
) -> pd.DataFrame:
    """
    Correlation matrix (full sample or trailing window).

    Parameters
    ----------
    window : if None, uses full sample. Otherwise, uses last N observations.
    """
    if window is not None:
        data = returns.tail(window)
    else:
        data = returns
    return data.corr()


def build_returns_panel(
    prices: pd.DataFrame,
    curve_metrics: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build a comprehensive returns panel from price data.

    Returns DataFrame with: returns, volatility, drawdowns, and optionally
    correlations with curve metrics.
    """
    returns = compute_returns(prices, method="log")
    vol = compute_realized_vol(returns)
    dd = compute_drawdown(prices)

    panel = returns.join(vol).join(dd)

    if curve_metrics is not None and "slope" in curve_metrics.columns:
        # Add rolling correlation of each asset with slope
        slope = curve_metrics["slope"].reindex(panel.index)
        for col in returns.columns:
            corr = compute_rolling_correlation(
                returns[col].dropna(), slope.dropna(), window=63
            )
            panel[f"corr_slope_{col}"] = corr

    panel.index.name = "date"
    return panel
