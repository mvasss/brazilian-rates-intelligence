"""
Curve Processor — Yield curve derived metrics.

Computes:
- Slope: DI_10Y - DI_2Y
- Curvature: 2×DI_5Y - DI_2Y - DI_10Y (butterfly spread)
- Real Yield: Nominal_yield - IPCA_expectation (Focus)
- Level: mean of all vertices
- Daily/weekly changes
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_slope(
    vertices_df: pd.DataFrame,
    long: str = "10Y",
    short: str = "2Y",
) -> pd.Series:
    """
    Yield curve slope = long_rate - short_rate.

    Default: 10Y - 2Y (standard slope measure).
    Units: percentage points.
    """
    if long not in vertices_df.columns or short not in vertices_df.columns:
        available = list(vertices_df.columns)
        logger.warning(
            f"Vertices {long} or {short} not in columns {available}. "
            "Falling back to last - first column."
        )
        return vertices_df.iloc[:, -1] - vertices_df.iloc[:, 0]

    return (vertices_df[long] - vertices_df[short]).rename("slope")


def compute_curvature(
    vertices_df: pd.DataFrame,
    belly: str = "5Y",
    long: str = "10Y",
    short: str = "2Y",
) -> pd.Series:
    """
    Butterfly spread / curvature = 2×belly - short - long.

    Positive curvature = belly above the line connecting short and long.
    """
    cols = [belly, long, short]
    missing = [c for c in cols if c not in vertices_df.columns]
    if missing:
        logger.warning(f"Missing vertices for curvature: {missing}")
        return pd.Series(dtype=float, name="curvature")

    return (
        2 * vertices_df[belly] - vertices_df[short] - vertices_df[long]
    ).rename("curvature")


def compute_level(vertices_df: pd.DataFrame) -> pd.Series:
    """Average rate across all vertices — the general level of the curve."""
    return vertices_df.mean(axis=1).rename("level")


def compute_real_yield(
    nominal_yield: pd.Series,
    inflation_expectation: pd.Series,
) -> pd.Series:
    """
    Real yield ≈ nominal yield - inflation expectation.

    Simple Fisher approximation. For more precision, use:
    real = (1+nominal)/(1+expected_inflation) - 1
    """
    # Align indices
    aligned = pd.DataFrame({
        "nominal": nominal_yield,
        "inflation_exp": inflation_expectation,
    }).ffill()

    real = aligned["nominal"] - aligned["inflation_exp"]
    return real.rename("real_yield")


def compute_curve_metrics(
    vertices_df: pd.DataFrame,
    inflation_exp: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Compute all derived curve metrics in one call.

    Returns DataFrame with columns: level, slope, curvature, real_yield,
    and their changes (1d, 1w, 1m).
    """
    metrics = pd.DataFrame(index=vertices_df.index)

    metrics["level"] = compute_level(vertices_df)
    metrics["slope"] = compute_slope(vertices_df)
    metrics["curvature"] = compute_curvature(vertices_df)

    if inflation_exp is not None:
        # Use 1Y vertex as reference for real yield
        if "1Y" in vertices_df.columns:
            nominal = vertices_df["1Y"]
        else:
            nominal = metrics["level"]
        metrics["real_yield"] = compute_real_yield(nominal, inflation_exp)

    # Changes
    for col in ["level", "slope", "curvature"]:
        if col in metrics.columns:
            metrics[f"{col}_1d"] = metrics[col].diff(1)
            metrics[f"{col}_1w"] = metrics[col].diff(5)
            metrics[f"{col}_1m"] = metrics[col].diff(21)

    metrics.index.name = "date"
    return metrics


def compute_term_premium(
    vertices_df: pd.DataFrame,
    short_rate: pd.Series,
) -> pd.DataFrame:
    """
    Naive term premium = vertex_rate - short_rate.

    The difference between each vertex and the short rate (Selic)
    proxies the term premium for each maturity.
    """
    aligned = vertices_df.copy()
    aligned["short_rate"] = short_rate.reindex(aligned.index).ffill()

    tp = pd.DataFrame(index=aligned.index)
    for col in vertices_df.columns:
        tp[f"tp_{col}"] = aligned[col] - aligned["short_rate"]

    tp.index.name = "date"
    return tp
