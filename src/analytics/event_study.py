"""
Event Study — Classical event study framework.

Methodology:
- Estimation window: [-120, -21] days before event
- Event window: [-5, 0, +5, +10, +20] days around event
- Normal returns: mean model from estimation window
- Abnormal returns: AR = R_actual - R_expected
- Cumulative abnormal returns (CAR) with t-statistics

Supports: COPOM, Focus surprise, FOMC, fiscal events.
"""
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from config.settings import (
    EVENT_ESTIMATION_WINDOW,
    EVENT_WINDOW_BEFORE,
    EVENT_WINDOW_AFTER,
)

logger = logging.getLogger(__name__)


@dataclass
class EventStudyResult:
    """Container for event study results."""
    event_type: str
    n_events: int
    car: pd.DataFrame          # Cumulative Abnormal Returns (mean across events)
    car_by_event: pd.DataFrame  # CAR for each individual event
    t_stats: pd.Series         # t-statistics at each event day
    p_values: pd.Series        # p-values at each event day
    summary: pd.DataFrame      # Summary statistics at key windows


def _compute_normal_return(
    returns: pd.Series,
    estimation_start: int,
    estimation_end: int,
    event_date: pd.Timestamp,
    all_dates: pd.DatetimeIndex,
) -> float:
    """
    Estimate normal (expected) return using mean model.

    Uses the mean return during the estimation window as the expected
    return during the event window.
    """
    date_idx = all_dates.get_loc(event_date)

    est_start_idx = max(0, date_idx + estimation_start)
    est_end_idx = max(0, date_idx + estimation_end)

    est_returns = returns.iloc[est_start_idx:est_end_idx]
    if len(est_returns) < 20:
        return 0.0

    return est_returns.mean()


def run_event_study(
    events: pd.DataFrame,
    returns: pd.DataFrame,
    asset: str,
    event_type: str | None = None,
    direction: str | None = None,
    window_before: int = EVENT_WINDOW_BEFORE,
    window_after: int = EVENT_WINDOW_AFTER,
    estimation_window: tuple[int, int] = EVENT_ESTIMATION_WINDOW,
) -> EventStudyResult | None:
    """
    Run event study for a specific asset and event type.

    Parameters
    ----------
    events : DataFrame with columns: date, event_type, direction.
    returns : DataFrame of asset returns (DatetimeIndex).
    asset : column name in returns to analyze.
    event_type : filter events by type (copom, fomc, fiscal, focus_surprise).
    direction : filter by direction (hike, cut, hold, hawkish, dovish, etc.).
    window_before, window_after : event window size in trading days.
    estimation_window : (start, end) relative to event date for normal returns.

    Returns
    -------
    EventStudyResult or None if insufficient data.
    """
    if asset not in returns.columns:
        logger.warning(f"Asset {asset} not in returns columns")
        return None

    asset_returns = returns[asset].dropna()
    all_dates = asset_returns.index

    # Filter events
    ev = events.copy()
    if event_type:
        ev = ev[ev["event_type"] == event_type]
    if direction:
        ev = ev[ev["direction"] == direction]

    if ev.empty:
        logger.warning(f"No events found for type={event_type}, dir={direction}")
        return None

    # Map event dates to trading dates
    event_dates = []
    for d in ev["date"]:
        d = pd.to_datetime(d)
        # Find nearest trading day
        idx = all_dates.searchsorted(d)
        if idx < len(all_dates):
            event_dates.append(all_dates[idx])

    if not event_dates:
        return None

    # Compute abnormal returns for each event
    window_range = list(range(-window_before, window_after + 1))
    car_by_event = {}

    for event_date in event_dates:
        date_idx = all_dates.get_loc(event_date)

        # Check we have enough data
        if date_idx + estimation_window[0] < 0:
            continue
        if date_idx + window_after >= len(all_dates):
            continue

        # Normal return
        mu = _compute_normal_return(
            asset_returns,
            estimation_window[0],
            estimation_window[1],
            event_date,
            all_dates,
        )

        # Abnormal returns in event window
        ar = {}
        for t in window_range:
            idx = date_idx + t
            if 0 <= idx < len(all_dates):
                ar[t] = asset_returns.iloc[idx] - mu

        if ar:
            car_by_event[event_date] = pd.Series(ar).cumsum()

    if not car_by_event:
        return None

    car_df = pd.DataFrame(car_by_event).T
    car_df.columns.name = "event_day"

    # Mean CAR across events
    mean_car = car_df.mean()
    std_car = car_df.std()
    n = len(car_df)

    # t-statistics
    if n > 1:
        std_err = std_car / np.sqrt(n)
        t_stat = mean_car / std_err.replace(0, np.nan)
        p_val = pd.Series(2 * (1 - sp_stats.t.cdf(np.abs(t_stat), df=n - 1)), index=mean_car.index)
    else:
        t_stat = pd.Series(np.nan, index=mean_car.index)
        p_val = pd.Series(np.nan, index=mean_car.index)

    # Summary at key windows
    key_windows = [0, 1, 5, 10, window_after]
    key_windows = [w for w in key_windows if w in mean_car.index]

    summary_rows = []
    for w in key_windows:
        summary_rows.append({
            "window": f"+{w}" if w > 0 else str(w),
            "car_mean": mean_car[w] * 100,
            "car_std": std_car[w] * 100 if w in std_car.index else np.nan,
            "t_stat": t_stat[w] if w in t_stat.index else np.nan,
            "p_value": p_val[w] if w in p_val.index else np.nan,
            "n_events": n,
            "pct_positive": (car_df[w] > 0).mean() * 100 if w in car_df.columns else np.nan,
        })

    summary = pd.DataFrame(summary_rows)

    return EventStudyResult(
        event_type=event_type or "all",
        n_events=n,
        car=mean_car.to_frame("car"),
        car_by_event=car_df,
        t_stats=t_stat,
        p_values=p_val,
        summary=summary,
    )


def run_multi_asset_event_study(
    events: pd.DataFrame,
    returns: pd.DataFrame,
    assets: list[str] | None = None,
    event_type: str | None = None,
    direction: str | None = None,
) -> dict[str, EventStudyResult]:
    """
    Run event study across multiple assets.

    Returns dict mapping asset name → EventStudyResult.
    """
    if assets is None:
        assets = list(returns.columns)

    results = {}
    for asset in assets:
        result = run_event_study(
            events, returns, asset, event_type, direction
        )
        if result is not None:
            results[asset] = result

    return results


def format_event_study_table(
    results: dict[str, EventStudyResult],
    window: int = 5,
) -> pd.DataFrame:
    """
    Create a summary table of event study results across assets.

    Shows CAR at the specified window for each asset.
    """
    rows = []
    for asset, result in results.items():
        if window in result.car.index:
            car_val = result.car.loc[window, "car"] * 100
            t_val = result.t_stats.get(window, np.nan)
            p_val = result.p_values.get(window, np.nan)
            sig = "***" if p_val < 0.01 else "**" if p_val < 0.05 else "*" if p_val < 0.1 else ""

            rows.append({
                "asset": asset,
                f"CAR[0,+{window}] (%)": f"{car_val:.2f}{sig}",
                "t-stat": f"{t_val:.2f}",
                "p-value": f"{p_val:.3f}",
                "n_events": result.n_events,
            })

    return pd.DataFrame(rows)
