"""
Market Collector — Market data via yfinance.

Fetches:
- Ibovespa, IFIX, USD/BRL, IMAB11 (IMA-B proxy)
- Sector indices (Financeiro, Small Caps)
"""
import logging

import pandas as pd
import yfinance as yf

from config.settings import DATA_START_DATE
from config.series_codes import YFINANCE_TICKERS, SECTOR_TICKERS
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger(__name__)


def fetch_market_data(
    ticker_keys: list[str] | None = None,
    start: str = DATA_START_DATE,
    end: str | None = None,
    include_sectors: bool = True,
) -> pd.DataFrame:
    """
    Fetch daily close prices for market indices/ETFs.

    Parameters
    ----------
    ticker_keys : list of keys from YFINANCE_TICKERS, or None for all.
    include_sectors : if True, also fetches SECTOR_TICKERS.

    Returns
    -------
    DataFrame with DatetimeIndex and one column per asset (close price).
    """
    all_tickers = dict(YFINANCE_TICKERS)
    if include_sectors:
        all_tickers.update(SECTOR_TICKERS)

    if ticker_keys is not None:
        all_tickers = {k: v for k, v in all_tickers.items() if k in ticker_keys}

    cache_key = f"market_{'_'.join(sorted(all_tickers.keys()))}_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        logger.info("Market data loaded from cache")
        return cached

    symbols = [v["ticker"] for v in all_tickers.values()]
    names = list(all_tickers.keys())

    logger.info(f"Fetching market data: {names}")

    try:
        raw = yf.download(symbols, start=start, end=end, auto_adjust=True)

        if len(symbols) == 1:
            df = pd.DataFrame({names[0]: raw["Close"]})
        else:
            df = raw["Close"].copy()
            # Map ticker symbols back to friendly names
            ticker_to_name = {
                v["ticker"]: k for k, v in all_tickers.items()
            }
            df.columns = [ticker_to_name.get(c, c) for c in df.columns]

    except Exception as e:
        logger.error(f"yfinance download failed: {e}")
        # Fallback: fetch one at a time
        frames = {}
        for name, meta in all_tickers.items():
            try:
                t = yf.Ticker(meta["ticker"])
                hist = t.history(start=start, end=end)
                frames[name] = hist["Close"]
            except Exception as e2:
                logger.warning(f"Could not fetch {name}: {e2}")
        df = pd.DataFrame(frames)

    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    # Remove timezone info if present
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    set_cached(cache_key, df)
    return df


def fetch_vix(start: str = DATA_START_DATE, end: str | None = None) -> pd.Series:
    """Fetch VIX index for regime classification."""
    cache_key = f"vix_{start}_{end}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached.squeeze()

    try:
        raw = yf.download("^VIX", start=start, end=end, auto_adjust=True)
        s = raw["Close"].squeeze()
        s.index = pd.to_datetime(s.index)
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        s.name = "vix"
        s.index.name = "date"
        df = s.to_frame()
        set_cached(cache_key, df)
        return s
    except Exception as e:
        logger.error(f"VIX fetch failed: {e}")
        return pd.Series(dtype=float, name="vix")
