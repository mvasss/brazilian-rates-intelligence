"""
Events Collector — Macro event datasets for event studies.

Sources:
- COPOM decisions (scraped from BCB or hardcoded)
- Focus surprises (large weekly changes in expectations)
- FOMC decisions (curated dataset)
- Fiscal events (curated dataset)
"""
import logging
import io
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import DATA_START_DATE, EVENTS_DIR
from config.series_codes import FOMC_KEY_DECISIONS, FISCAL_EVENTS
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)


def fetch_copom_decisions(start: str = DATA_START_DATE, end: str | None = None) -> pd.DataFrame:
    """
    Fetch COPOM meeting dates and Selic decisions.

    Tries scraping BCB website first, falls back to a curated dataset.

    Returns
    -------
    DataFrame with columns: date, selic_target, change_bps, decision_type.
    """
    cache_key = f"copom_decisions_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    df = _scrape_copom_decisions()

    if df.empty:
        logger.info("Scraping failed, using hardcoded COPOM decisions")
        df = _hardcoded_copom_decisions()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"] >= start]
        if end:
            df = df[df["date"] <= end]
        df = df.sort_values("date").reset_index(drop=True)
        # Calculate change in bps
        if "change_bps" not in df.columns:
            df["change_bps"] = df["selic_target"].diff() * 100
        df["decision_type"] = df["change_bps"].apply(
            lambda x: "hike" if x > 0 else ("cut" if x < 0 else "hold")
        )

    set_cached(cache_key, df)
    return df


def _scrape_copom_decisions() -> pd.DataFrame:
    """Try to scrape COPOM decisions from BCB website."""
    url = "https://www.bcb.gov.br/en/monetarypolicy/interestrate"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        if tables:
            df = tables[0]
            # Normalize column names
            df.columns = [c.lower().strip() for c in df.columns]
            return df
    except Exception as e:
        logger.debug(f"BCB scraping failed: {e}")
    return pd.DataFrame()


def _hardcoded_copom_decisions() -> pd.DataFrame:
    """Curated COPOM decisions (2019-2025)."""
    data = [
        # 2019
        ("2019-02-06", 6.50), ("2019-03-20", 6.50), ("2019-05-08", 6.50),
        ("2019-06-19", 6.50), ("2019-07-31", 6.00), ("2019-09-18", 5.50),
        ("2019-10-30", 5.00), ("2019-12-11", 4.50),
        # 2020
        ("2020-02-05", 4.25), ("2020-03-18", 3.75), ("2020-05-06", 3.00),
        ("2020-06-17", 2.25), ("2020-08-05", 2.00), ("2020-09-16", 2.00),
        ("2020-10-28", 2.00), ("2020-12-09", 2.00),
        # 2021
        ("2021-01-20", 2.00), ("2021-03-17", 2.75), ("2021-05-05", 3.50),
        ("2021-06-16", 4.25), ("2021-08-04", 5.25), ("2021-09-22", 6.25),
        ("2021-10-27", 7.75), ("2021-12-08", 9.25),
        # 2022
        ("2022-02-02", 10.75), ("2022-03-16", 11.75), ("2022-05-04", 12.75),
        ("2022-06-15", 13.25), ("2022-08-03", 13.75), ("2022-09-21", 13.75),
        ("2022-10-26", 13.75), ("2022-12-07", 13.75),
        # 2023
        ("2023-02-01", 13.75), ("2023-03-22", 13.75), ("2023-05-03", 13.75),
        ("2023-06-21", 13.75), ("2023-08-02", 13.25), ("2023-09-20", 12.75),
        ("2023-11-01", 12.25), ("2023-12-13", 11.75),
        # 2024
        ("2024-01-31", 11.25), ("2024-03-20", 10.75), ("2024-05-08", 10.50),
        ("2024-06-19", 10.50), ("2024-07-31", 10.50), ("2024-09-18", 10.75),
        ("2024-11-06", 11.25), ("2024-12-11", 12.25),
        # 2025
        ("2025-01-29", 13.25), ("2025-03-19", 14.25), ("2025-05-07", 14.75),
        ("2025-06-18", 14.75),
    ]
    df = pd.DataFrame(data, columns=["date", "selic_target"])
    df["date"] = pd.to_datetime(df["date"])
    df["change_bps"] = df["selic_target"].diff() * 100
    df["decision_type"] = df["change_bps"].apply(
        lambda x: "hike" if x > 0 else ("cut" if x < 0 else "hold")
    )
    return df
def fetch_focus_surprises(
    threshold_pp: float = 0.5,
    start: str = DATA_START_DATE,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Identify dates where Focus IPCA median changed significantly week-over-week.

    A 'surprise' is defined as a weekly change in the median IPCA expectation
    larger than threshold_pp (percentage points).

    Returns
    -------
    DataFrame with columns: date, indicator, median_before, median_after,
                            change_pp, direction.
    """
    cache_key = f"focus_surprises_{threshold_pp}_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    from src.collectors.bcb_collector import fetch_focus_latest_median

    focus = fetch_focus_latest_median(["IPCA", "Selic"], start=start)

    if focus.empty:
        return pd.DataFrame()

    events = []
    for col in focus.columns:
        series = focus[col].dropna()
        weekly = series.resample("W-FRI").last().dropna()
        changes = weekly.diff()
        big = changes[changes.abs() >= threshold_pp]

        for date, change in big.items():
            idx = weekly.index.get_loc(date)
            events.append({
                "date": date,
                "indicator": col,
                "median_before": weekly.iloc[idx - 1] if idx > 0 else None,
                "median_after": weekly.iloc[idx],
                "change_pp": change,
                "direction": "hawkish" if change > 0 else "dovish",
            })

    result = pd.DataFrame(events)
    if not result.empty:
        result["date"] = pd.to_datetime(result["date"])
        if end:
            result = result[result["date"] <= end]
        result = result.sort_values("date").reset_index(drop=True)

    set_cached(cache_key, result)
    return result


def fetch_fomc_decisions(start: str = DATA_START_DATE, end: str | None = None) -> pd.DataFrame:
    """Return curated FOMC key decisions as DataFrame."""
    data = []
    for date_str, bps, desc in FOMC_KEY_DECISIONS:
        data.append({
            "date": pd.to_datetime(date_str),
            "change_bps": bps,
            "description": desc,
            "decision_type": (
                "hike" if bps > 0 else ("cut" if bps < 0 else "hold")
            ),
        })
    df = pd.DataFrame(data)
    df = df[df["date"] >= start]
    if end:
        df = df[df["date"] <= end]
    return df.reset_index(drop=True)


def fetch_fiscal_events(start: str = DATA_START_DATE, end: str | None = None) -> pd.DataFrame:
    """Return curated fiscal events as DataFrame."""
    data = []
    for date_str, direction, desc in FISCAL_EVENTS:
        data.append({
            "date": pd.to_datetime(date_str),
            "direction": direction,
            "description": desc,
        })
    df = pd.DataFrame(data)
    df = df[df["date"] >= start]
    if end:
        df = df[df["date"] <= end]
    return df.reset_index(drop=True)


def fetch_all_events(start: str = DATA_START_DATE, end: str | None = None) -> pd.DataFrame:
    """
    Combine all event types into a single DataFrame for event studies.

    Returns DataFrame with columns: date, event_type, direction, description.
    """
    all_events = []

    # COPOM
    copom = fetch_copom_decisions(start=start, end=end)
    if not copom.empty:
        for _, row in copom.iterrows():
            all_events.append({
                "date": row["date"],
                "event_type": "copom",
                "direction": row["decision_type"],
                "description": f"Selic → {row['selic_target']}% ({row['change_bps']:+.0f}bps)",
            })

    # Focus surprises
    focus = fetch_focus_surprises(start=start, end=end)
    if not focus.empty:
        for _, row in focus.iterrows():
            all_events.append({
                "date": row["date"],
                "event_type": "focus_surprise",
                "direction": row["direction"],
                "description": f"{row['indicator']}: {row['change_pp']:+.2f}pp",
            })

    # FOMC
    fomc = fetch_fomc_decisions(start=start, end=end)
    if not fomc.empty:
        for _, row in fomc.iterrows():
            all_events.append({
                "date": row["date"],
                "event_type": "fomc",
                "direction": row["decision_type"],
                "description": row["description"],
            })

    # Fiscal
    fiscal = fetch_fiscal_events(start=start, end=end)
    if not fiscal.empty:
        for _, row in fiscal.iterrows():
            all_events.append({
                "date": row["date"],
                "event_type": "fiscal",
                "direction": row["direction"],
                "description": row["description"],
            })

    df = pd.DataFrame(all_events)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        if end:
            df = df[df["date"] <= end]
        df = df.sort_values("date").reset_index(drop=True)
    return df
