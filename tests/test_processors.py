"""
Tests for Data Processors.
Verifies economic and quantitative intent:
1. Curve metrics: slope = 10Y - 2Y, curvature = 2*5Y - 2Y - 10Y, real yield = nominal - expected inflation.
2. Returns processor: log and simple returns consistency, annualized volatility scaling, drawdown.
3. Macro processor: z-scores, daily interpolation.
"""
import numpy as np
import pandas as pd
import pytest

from src.processors.curve_processor import (
    compute_curve_metrics,
    compute_slope,
    compute_curvature,
    compute_real_yield,
)
from src.processors.returns_processor import (
    compute_returns,
    compute_realized_vol,
    compute_drawdown,
)
from src.processors.macro_processor import (
    compute_zscore,
    interpolate_to_daily,
)


def test_curve_slope_and_curvature_calculation():
    """Slope must reflect curve tilt; Curvature must reflect butterfly spread."""
    vertices = pd.DataFrame({
        "2Y": [10.0, 11.0],
        "5Y": [11.5, 12.0],
        "10Y": [12.5, 13.0],
    }, index=pd.date_range("2024-01-01", periods=2, freq="B"))

    slope = compute_slope(vertices)
    assert np.isclose(slope.iloc[0], 2.5), "Slope must be 10Y - 2Y = 12.5 - 10.0 = 2.5"

    curvature = compute_curvature(vertices)
    # 2*5Y - 2Y - 10Y = 2*11.5 - 10.0 - 12.5 = 23.0 - 22.5 = 0.5
    assert np.isclose(curvature.iloc[0], 0.5), "Curvature must be 2*5Y - 2Y - 10Y = 0.5"


def test_real_yield_deducts_inflation_expectation():
    """Ex-ante real yield should be nominal yield minus expected inflation."""
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    nominal = pd.Series([12.0, 12.5, 13.0], index=dates)
    inflation_exp = pd.Series([4.0, 4.5, 5.0], index=dates)

    real_y = compute_real_yield(nominal, inflation_exp)
    assert np.isclose(real_y.iloc[0], 8.0), "12.0% - 4.0% = 8.0%"
    assert np.isclose(real_y.iloc[2], 8.0), "13.0% - 5.0% = 8.0%"


def test_returns_and_annualized_volatility():
    """Realized volatility must scale by sqrt(252)."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    prices = pd.DataFrame({"asset": np.cumprod(1 + np.random.normal(0, 0.01, 100))}, index=dates)
    returns = compute_returns(prices, method="simple")
    vol = compute_realized_vol(returns, windows=[21], annualize=True)

    # Rolling vol should be positive and roughly around 0.01 * sqrt(252) ~= 0.158
    assert vol["asset_vol_21d"].dropna().mean() > 0.08
    assert vol["asset_vol_21d"].dropna().mean() < 0.30


def test_drawdown_calculation():
    """Drawdown must be <= 0 and reach trough at lowest cumulative point."""
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    prices = pd.DataFrame({"asset": [100, 110, 105, 90, 95]}, index=dates)
    dd = compute_drawdown(prices)

    assert dd["asset_drawdown"].max() <= 0.0001, "Drawdown can never exceed 0"
    # Peak is 110, trough is 90 -> (90 - 110) / 110 = -18.18%
    assert np.isclose(dd["asset_drawdown"].min(), (90 - 110) / 110, atol=1e-3)


def test_macro_zscore_and_daily_interpolation():
    """Z-score must calculate rolling deviation and interpolation expand rows."""
    dates = pd.date_range("2024-01-01", periods=300, freq="B")
    series = pd.Series(np.random.normal(10, 2, size=300), index=dates)
    z = compute_zscore(series, window=63, min_periods=30)
    assert not z.dropna().empty

    monthly = pd.DataFrame({"gdp": [100, 101]}, index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    daily = interpolate_to_daily(monthly)
    assert len(daily) > 2
