"""
Curve Collector — Brazilian yield curve data via pyettj.

Fetches:
- ETTJ PRE (DI futures curve)
- ETTJ IPCA (NTN-B implied curve)
- Historical curves for time-series analysis
"""
import logging
from datetime import datetime, timedelta

import pandas as pd

from config.settings import DATA_START_DATE, CURVE_VERTEX_LABELS, CURVE_VERTICES_BD
from config.series_codes import ETTJ_CURVES
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)


def _try_import_pyettj():
    """Import pyettj with graceful fallback."""
    try:
        import pyettj
        return pyettj
    except ImportError:
        logger.warning("pyettj not installed. Yield curve data unavailable.")
        return None


def fetch_yield_curve(
    date: str | datetime,
    curve_type: str = "PRE",
) -> pd.DataFrame:
    """
    Fetch yield curve for a single date.

    Parameters
    ----------
    date : date string 'DD/MM/YYYY' or datetime.
    curve_type : 'PRE' or 'DIC' (IPCA).

    Returns
    -------
    DataFrame with columns: business_days, rate (% a.a.), date.
    """
    ettj = _try_import_pyettj()
    if ettj is None:
        return pd.DataFrame()

    if isinstance(date, (datetime, pd.Timestamp)):
        date_str = date.strftime("%d/%m/%Y")
    else:
        date_str = date

    try:
        df = ettj.get_ettj(date_str, curva=curve_type)
        df["date"] = pd.to_datetime(date_str, dayfirst=True)
        return df
    except Exception as e:
        logger.debug(f"No curve data for {date_str}: {e}")
        return pd.DataFrame()


def fetch_historical_curves(
    start: str = DATA_START_DATE,
    end: str | None = None,
    curve_type: str = "PRE",
    frequency: str = "weekly",
) -> pd.DataFrame:
    """
    Build historical yield curve dataset.

    Fetches curves at weekly or monthly intervals to keep API calls manageable.

    Parameters
    ----------
    frequency : 'daily', 'weekly', or 'monthly'.

    Returns
    -------
    DataFrame with columns: date, business_days, rate.
    """
    cache_key = f"curves_{curve_type}_{frequency}_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        logger.info(f"Historical curves ({curve_type}) loaded from cache")
        return cached

    ettj = _try_import_pyettj()
    if ettj is None:
        return pd.DataFrame()

    from concurrent.futures import ThreadPoolExecutor

    now = datetime.now()
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end) if end else now
    if end_dt > now:
        end_dt = now

    # Adaptive frequency: if date span > 1.5 years, use monthly to ensure ultra-fast load
    span_days = (end_dt - start_dt).days
    effective_freq = frequency
    if span_days > 500 and frequency == "weekly":
        effective_freq = "monthly"

    # Generate date range
    if effective_freq == "daily":
        dates = pd.bdate_range(start_dt, end_dt)
        if len(dates) > 100:
            dates = dates[::3]  # Subsample if too dense
    elif effective_freq == "weekly":
        dates = pd.bdate_range(start_dt, end_dt, freq="W-FRI")
    else:  # monthly
        dates = pd.bdate_range(start_dt, end_dt, freq="BME")

    if len(dates) == 0:
        dates = pd.DatetimeIndex([end_dt])

    logger.info(
        f"Fetching {len(dates)} {curve_type} curves ({effective_freq}) concurrently..."
    )

    def _fetch_single(dt):
        try:
            df = ettj.get_ettj(dt.strftime("%d/%m/%Y"), curva=curve_type, timeout=3, retry=1)
            if df is not None and not df.empty:
                df["date"] = dt
                return df
        except Exception:
            return None
        return None

    # Fetch concurrently with a pool of workers
    with ThreadPoolExecutor(max_workers=8) as executor:
        all_curves = [res for res in executor.map(_fetch_single, dates) if res is not None]

    if not all_curves:
        logger.warning("No curves fetched via pyettj. Checking baseline cache.")
        from config.settings import PROCESSED_DIR
        base_file = PROCESSED_DIR / "curve_vertices.parquet"
        if base_file.exists():
            return pd.read_parquet(base_file)
        return pd.DataFrame()

    result = pd.concat(all_curves, ignore_index=True)
    logger.info(f"Successfully fetched {len(all_curves)} curves.")

    set_cached(cache_key, result)
    return result


def extract_curve_vertices(
    curves_df: pd.DataFrame,
    target_vertices: list[int] | None = None,
) -> pd.DataFrame:
    """
    Extract specific vertices from a historical curves DataFrame.

    Interpolates to standard vertex points if exact match not found.

    Parameters
    ----------
    curves_df : output of fetch_historical_curves().
    target_vertices : list of business days (e.g., [252, 504, 2520]).

    Returns
    -------
    DataFrame indexed by date with columns for each vertex label.
    """
    if curves_df.empty:
        from config.settings import PROCESSED_DIR
        base_file = PROCESSED_DIR / "curve_vertices.parquet"
        if base_file.exists():
            return pd.read_parquet(base_file)
        return pd.DataFrame()

    # If curves_df is already extracted vertices (indexed by date with vertex labels)
    if any(col in curves_df.columns for col in ["1Y", "2Y", "5Y", "10Y"]) and "taxa" not in curves_df.columns:
        return curves_df

    if target_vertices is None:
        target_vertices = CURVE_VERTICES_BD

    # Identify the business_days column (pyettj may name it differently)
    bd_col = None
    for col in ["prazo", "business_days", "du", "dias_uteis"]:
        if col in curves_df.columns:
            bd_col = col
            break
    if bd_col is None:
        # Assume first numeric column is business days
        numeric = curves_df.select_dtypes("number").columns
        if len(numeric) >= 1:
            bd_col = numeric[0]
        else:
            logger.error("Cannot identify business_days column in curves_df")
            return pd.DataFrame()

    rate_col = None
    for col in ["taxa", "rate", "taxa_spot", "taxa_252"]:
        if col in curves_df.columns:
            rate_col = col
            break
    if rate_col is None:
        numeric = curves_df.select_dtypes("number").columns
        candidates = [c for c in numeric if c != bd_col]
        if candidates:
            rate_col = candidates[0]
        else:
            logger.error("Cannot identify rate column in curves_df")
            return pd.DataFrame()

    result = {}
    for date, group in curves_df.groupby("date"):
        g = group.sort_values(bd_col).drop_duplicates(subset=bd_col)
        if len(g) < 2:
            continue
        rates = {}
        for bd, label in zip(target_vertices, CURVE_VERTEX_LABELS):
            exact = g[g[bd_col] == bd]
            if not exact.empty:
                rates[label] = exact[rate_col].iloc[0]
            else:
                # Linear interpolation
                below = g[g[bd_col] <= bd]
                above = g[g[bd_col] >= bd]
                if below.empty or above.empty:
                    continue
                b = below.iloc[-1]
                a = above.iloc[0]
                if b[bd_col] == a[bd_col]:
                    rates[label] = b[rate_col]
                else:
                    w = (bd - b[bd_col]) / (a[bd_col] - b[bd_col])
                    rates[label] = b[rate_col] + w * (a[rate_col] - b[rate_col])
        result[date] = rates

    df = pd.DataFrame(result).T
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    df = df.sort_index()

    # Normalize to percentage points if expressed in decimals (e.g. 0.105 -> 10.5%)
    if not df.empty and (df.select_dtypes("number").max().max() < 1.0):
        df = df * 100.0

    return df
