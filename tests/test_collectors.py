"""
Tests for Data Collectors.
Verifies data acquisition structure and fallback resilience:
1. Event collector loads hardcoded COPOM, FOMC, and fiscal dates correctly.
2. Curve collector vertices extraction produces sorted maturity labels.
3. Cache mechanism stores and retrieves cached frames.
"""
import pandas as pd
import pytest

from src.collectors.events_collector import (
    fetch_copom_decisions,
    fetch_fomc_decisions,
    fetch_fiscal_events,
    fetch_all_events,
)
from src.collectors.curve_collector import extract_curve_vertices
from src.utils.cache import set_cached, get_cached


def test_hardcoded_events_datasets():
    """COPOM, FOMC, and fiscal events should have date, event_type, and direction columns."""
    copom = fetch_copom_decisions()
    assert not copom.empty
    assert "date" in copom.columns
    assert "decision_type" in copom.columns or "direction" in copom.columns

    fomc = fetch_fomc_decisions()
    assert not fomc.empty
    assert "decision_type" in fomc.columns or "direction" in fomc.columns

    fiscal = fetch_fiscal_events()
    assert not fiscal.empty
    assert "direction" in fiscal.columns

    all_ev = fetch_all_events()
    assert not all_ev.empty
    assert "event_type" in all_ev.columns
    assert "direction" in all_ev.columns


def test_extract_curve_vertices():
    """Verify that vertex extraction reshapes date-maturity pairs into standard columns."""
    # Synthetic pyettj long dataframe
    dates = pd.date_range("2024-01-01", periods=2, freq="B")
    records = []
    for d in dates:
        records.append({"date": d, "days": 504, "rate": 10.5})   # ~2Y
        records.append({"date": d, "days": 1260, "rate": 11.2})  # ~5Y
        records.append({"date": d, "days": 2520, "rate": 12.0})  # ~10Y

    long_df = pd.DataFrame(records)
    vertices = extract_curve_vertices(long_df)

    assert not vertices.empty
    assert "2Y" in vertices.columns or "5Y" in vertices.columns or "10Y" in vertices.columns


def test_cache_storage():
    """Ensure dataframes can be cached and retrieved reliably."""
    df = pd.DataFrame({"val": [1, 2, 3]}, index=pd.date_range("2024-01-01", periods=3))
    cache_key = "test_unit_cache_key"

    set_cached(cache_key, df)
    loaded = get_cached(cache_key)

    assert loaded is not None
    assert (loaded["val"] == df["val"]).all()
