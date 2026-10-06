"""
BCB Collector — Banco Central do Brasil data via python-bcb.

Fetches:
- SGS time series (Selic, IPCA, câmbio, PIB, desemprego, fiscal)
- Focus expectations (IPCA, Selic, PIB, câmbio)
- Inflation surprise (realized - expected)
"""
import logging
from datetime import datetime, timedelta

import pandas as pd
from bcb import sgs, Expectativas

from config.settings import DATA_START_DATE
from config.series_codes import SGS_SERIES, FOCUS_INDICATORS
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)


def fetch_sgs_series(
    series_keys: list[str] | None = None,
    start: str = DATA_START_DATE,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Fetch multiple SGS series and return a single DataFrame.

    Parameters
    ----------
    series_keys : list of keys from SGS_SERIES, or None for all.
    start, end  : date strings 'YYYY-MM-DD'.

    Returns
    -------
    DataFrame with DatetimeIndex and one column per series.
    """
    if series_keys is None:
        series_keys = list(SGS_SERIES.keys())

    cache_key = f"sgs_{'_'.join(sorted(series_keys))}_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        logger.info("SGS data loaded from cache")
        return cached

    code_map = {k: SGS_SERIES[k]["code"] for k in series_keys}
    logger.info(f"Fetching SGS series: {list(code_map.keys())}")

    try:
        df = sgs.get(code_map, start=start, end=end)
    except Exception as e:
        logger.error(f"SGS fetch failed: {e}")
        # Fallback: fetch one by one
        frames = {}
        for name, code in code_map.items():
            try:
                s = sgs.get({name: code}, start=start, end=end)
                frames[name] = s[name]
            except Exception as e2:
                logger.warning(f"Could not fetch {name} (code {code}): {e2}")
        df = pd.DataFrame(frames)

    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    set_cached(cache_key, df)
    return df


def fetch_focus_expectations(
    indicator: str = "IPCA",
    start: str = DATA_START_DATE,
    reference_year: int | None = None,
) -> pd.DataFrame:
    """
    Fetch Focus market expectations for a given indicator.

    Returns DataFrame with columns: Data, Mediana, Media, Maximo, Minimo, etc.
    Filtered for the smoothed (Suavizada = 'S') estimates and Top 5 median.
    """
    cache_key = f"focus_{indicator}_{start}_{reference_year}"
    cached = get_cached(cache_key)
    if cached is not None:
        logger.info(f"Focus {indicator} loaded from cache")
        return cached

    logger.info(f"Fetching Focus expectations: {indicator}")

    em = Expectativas()
    ep = em.get_endpoint("ExpectativasMercadoAnuais")

    query = (
        ep.query()
        .filter(ep.Indicador == indicator)
        .filter(ep.Data >= start)
    )
    if reference_year is not None:
        query = query.filter(ep.DataReferencia == str(reference_year))

    df = query.collect()

    if not df.empty:
        df["Data"] = pd.to_datetime(df["Data"])
        df = df.sort_values("Data")

    set_cached(cache_key, df)
    return df


def fetch_focus_latest_median(
    indicators: list[str] | None = None,
    start: str = DATA_START_DATE,
) -> pd.DataFrame:
    """
    Build a time series of the latest Focus median for each indicator.

    For each survey date, takes the median expectation for the current year
    and the next year. Returns DataFrame indexed by date with columns like
    'IPCA_current', 'IPCA_next', 'Selic_current', 'Selic_next'.
    """
    if indicators is None:
        indicators = ["IPCA", "Selic"]

    cache_key = f"focus_median_{'_'.join(indicators)}_{start}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    all_series = {}
    for indicator in indicators:
        for year_offset, label in [(0, "current"), (1, "next")]:
            ref_year = datetime.now().year + year_offset
            try:
                df = fetch_focus_expectations(indicator, start, ref_year)
                if df.empty:
                    continue
                ts = df.groupby("Data")["Mediana"].last()
                ts.index = pd.to_datetime(ts.index)
                all_series[f"{indicator}_{label}"] = ts
            except Exception as e:
                logger.warning(f"Focus {indicator} {label}: {e}")

    result = pd.DataFrame(all_series)
    result.index.name = "date"
    result = result.sort_index()

    set_cached(cache_key, result)
    return result


def fetch_inflation_surprise(start: str = DATA_START_DATE) -> pd.DataFrame:
    """
    Calculate inflation surprise = IPCA realized - Focus expected.

    Returns monthly DataFrame with columns:
    - ipca_realized: actual IPCA monthly (%)
    - ipca_expected: Focus median for the period
    - surprise: realized - expected
    """
    cache_key = f"inflation_surprise_{start}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    ipca = fetch_sgs_series(["ipca_mensal"], start=start)["ipca_mensal"].dropna()

    # Get Focus expectations for IPCA
    focus = fetch_focus_expectations("IPCA", start=start)

    if focus.empty:
        logger.warning("No Focus data for inflation surprise")
        result = pd.DataFrame({"ipca_realized": ipca})
        result["ipca_expected"] = None
        result["surprise"] = None
        set_cached(cache_key, result)
        return result

    # For each month, get the last Focus median before that month
    monthly_expected = {}
    for date in ipca.index:
        pre = focus[focus["Data"] < date]
        if not pre.empty:
            monthly_expected[date] = pre.iloc[-1]["Mediana"]

    expected = pd.Series(monthly_expected, name="ipca_expected")

    result = pd.DataFrame({
        "ipca_realized": ipca,
        "ipca_expected": expected,
    })
    result["surprise"] = result["ipca_realized"] - result["ipca_expected"]
    result.index.name = "date"

    set_cached(cache_key, result)
    return result
