"""
Cache utility — local file caching for API responses.

Stores DataFrames as parquet in data/raw/ with timestamp-based TTL.
Avoids redundant API calls during development and dashboard refresh.
"""
import hashlib
import time
from pathlib import Path

import pandas as pd

from config.settings import RAW_DIR, CACHE_TTL_HOURS


def _cache_path(key: str) -> Path:
    """Generate a deterministic cache file path from a string key."""
    safe = hashlib.md5(key.encode()).hexdigest()
    return RAW_DIR / f"cache_{safe}.parquet"


def _meta_path(key: str) -> Path:
    safe = hashlib.md5(key.encode()).hexdigest()
    return RAW_DIR / f"cache_{safe}.meta"


def get_cached(key: str) -> pd.DataFrame | None:
    """Return cached DataFrame if exists and not expired, else None."""
    path = _cache_path(key)
    meta = _meta_path(key)
    if not path.exists() or not meta.exists():
        return None
    try:
        ts = float(meta.read_text().strip())
        if (time.time() - ts) > CACHE_TTL_HOURS * 3600:
            return None
        return pd.read_parquet(path)
    except Exception:
        return None


def set_cached(key: str, df: pd.DataFrame) -> None:
    """Store a DataFrame in cache."""
    path = _cache_path(key)
    meta = _meta_path(key)
    df.to_parquet(path, index=True)
    meta.write_text(str(time.time()))


def clear_cache() -> int:
    """Remove all cache files. Returns count of files removed."""
    count = 0
    for f in RAW_DIR.glob("cache_*"):
        f.unlink()
        count += 1
    return count
