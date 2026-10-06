"""
Brazilian Rates Intelligence — Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVENTS_DIR = DATA_DIR / "events"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Create directories
for d in [RAW_DIR, PROCESSED_DIR, EVENTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Data collection parameters
DATA_START_DATE = "2019-01-01"
DATA_END_DATE = None  # None = today

# Cache TTL (seconds)
CACHE_TTL_HOURS = 12

# Yield curve vertices (business days / years)
CURVE_VERTICES_BD = [21, 42, 63, 126, 252, 504, 756, 1260, 2520]
CURVE_VERTICES_YEARS = [v / 252 for v in CURVE_VERTICES_BD]
CURVE_VERTEX_LABELS = ["1M", "2M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "10Y"]

# Regime classification thresholds
REGIME_LOOKBACK_DAYS = 63  # ~3 months for regime features
REGIME_Z_THRESHOLD = 0.5   # z-score threshold for rule-based regime

# Event study windows
EVENT_ESTIMATION_WINDOW = (-120, -21)
EVENT_WINDOW_BEFORE = 5
EVENT_WINDOW_AFTER = 20

# Rates Signal weights
SIGNAL_WEIGHTS = {
    "inflation_surprise": 0.30,
    "fiscal_risk": 0.20,
    "fx_pressure": 0.25,
    "monetary_expectation": 0.25,
}
SIGNAL_ZSCORE_WINDOW = 252  # 1 year rolling z-score
