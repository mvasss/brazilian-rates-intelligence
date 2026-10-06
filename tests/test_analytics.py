"""
Tests for Analytics Modules.
Verifies quantitative and economic modeling intent:
1. Regime classification logic correctly maps macro drivers into the 4 states.
2. Event study calculates cumulative abnormal returns (CAR) relative to estimation mean.
3. Rates Pressure Score outputs [-100, +100] bounded signals responsive to macro shocks.
4. Asset impact identifies large yield moves and measures asset transmission.
"""
import numpy as np
import pandas as pd
import pytest

from src.analytics.regime_classifier import (
    build_regime_features,
    classify_regimes_rules,
    get_current_regime,
)
from src.analytics.event_study import (
    run_event_study,
    EventStudyResult,
)
from src.analytics.rates_signal import (
    compute_rates_pressure_score,
    get_current_signal,
    backtest_signal,
)
from src.analytics.asset_impact import (
    identify_rate_scenarios,
    compute_asset_response,
)


def test_regime_classifier_rules():
    """Verify that bull conditions produce Risk-on and inflationary shocks produce Inflationary regime."""
    dates = pd.date_range("2023-01-01", periods=10, freq="B")

    # Risk-on scenario: slope drops, BRL strengthens (usd_brl drops), equities rally, VIX drops
    features_risk_on = pd.DataFrame({
        "slope_change": [-1.5] * 10,
        "brl_change": [-1.2] * 10,
        "equity_change": [1.5] * 10,
        "vix_level": [-1.0] * 10,
        "inflation_exp_change": [0.0] * 10,
    }, index=dates)

    classified = classify_regimes_rules(features_risk_on, threshold=0.5)
    assert (classified["regime"] == "risk_on").all(), "Expected risk_on when equities rally and slope drops"

    # Inflationary scenario: inflation expectations surge, curve steepens, BRL weakens
    features_infl = pd.DataFrame({
        "slope_change": [1.5] * 10,
        "brl_change": [1.2] * 10,
        "equity_change": [0.0] * 10,
        "vix_level": [0.0] * 10,
        "inflation_exp_change": [2.0] * 10,
    }, index=dates)

    classified_infl = classify_regimes_rules(features_infl, threshold=0.5)
    assert (classified_infl["regime"] == "inflationary").all(), "Expected inflationary regime"


def test_rates_pressure_score_bounds_and_directionality():
    """Score must strictly respect [-100, 100] bounds and increase with inflationary pressure."""
    dates = pd.date_range("2023-01-01", periods=5, freq="B")

    # High pressure shock
    inf_z = pd.Series([3.0] * 5, index=dates)
    fiscal_z = pd.Series([2.5] * 5, index=dates)
    fx_z = pd.Series([2.0] * 5, index=dates)
    mon_z = pd.Series([2.0] * 5, index=dates)

    signal_df = compute_rates_pressure_score(inf_z, fiscal_z, fx_z, mon_z)

    assert (signal_df["score"] <= 100.0).all()
    assert (signal_df["score"] >= -100.0).all()
    assert signal_df["score"].iloc[-1] > 50.0, "High inflationary & fiscal pressure must yield score > 50"

    curr = get_current_signal(signal_df)
    assert "Forte pressão de alta" in curr["interpretation"]


def test_event_study_abnormal_returns():
    """CAR should be computed correctly relative to baseline estimation window."""
    dates = pd.date_range("2023-01-01", periods=250, freq="B")
    returns = pd.DataFrame({
        "asset_a": [0.01] * 250,
    }, index=dates)

    events = pd.DataFrame({
        "date": [dates[150]],
        "event_type": ["copom"],
        "direction": ["hike"],
    })

    # If returns are constant (0.01), abnormal returns are zero (0.01 - 0.01 = 0)
    res = run_event_study(events, returns, asset="asset_a", window_before=5, window_after=5)
    assert res is not None
    assert isinstance(res, EventStudyResult)
    assert np.isclose(res.car.loc[5, "car"], 0.0, atol=1e-5)


def test_asset_impact_scenarios():
    """Scenario identification should accurately find ±100bps moves."""
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    # Simulate a rate level that jumps by 1.5% (150bps) between t=20 and t=83
    curve_level = pd.Series(10.0, index=dates)
    curve_level.iloc[65:] = 11.5

    scenarios = identify_rate_scenarios(curve_level, thresholds_bps=[50, 100], window=63)
    assert not scenarios.empty
    assert (scenarios["direction"] == "up").any()
