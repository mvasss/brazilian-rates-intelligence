"""
Regime Classifier — Market regime identification.

Classifies periods into:
  🟢 Risk-on      : Slope ↓ + BRL ↑ + Ibovespa ↑ + VIX ↓
  🔴 Risk-off     : Slope ↑ + BRL ↓ + Ibovespa ↓ + VIX ↑
  🟡 Inflationary : Focus IPCA ↑ + Curve steepening + BRL ↓
  🔵 Disinflationary : Focus IPCA ↓ + Curve flattening + BRL stable/↑

Two methods:
1. Rule-based scoring (primary)
2. Gaussian Mixture Model validation (secondary)
"""
import logging

import numpy as np
import pandas as pd
try:
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    GaussianMixture = None
    StandardScaler = None
    HAS_SKLEARN = False

from config.settings import REGIME_LOOKBACK_DAYS, REGIME_Z_THRESHOLD

logger = logging.getLogger(__name__)

# Regime labels and colors
REGIME_LABELS = {
    0: "risk_on",
    1: "risk_off",
    2: "inflationary",
    3: "disinflationary",
}

REGIME_COLORS = {
    "risk_on": "#00C853",
    "risk_off": "#FF1744",
    "inflationary": "#FFD600",
    "disinflationary": "#2979FF",
}

REGIME_EMOJI = {
    "risk_on": "🟢",
    "risk_off": "🔴",
    "inflationary": "🟡",
    "disinflationary": "🔵",
}


def _rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling z-score adapting window when series length or frequency is smaller."""
    valid = series.dropna()
    n = len(valid)
    if n == 0:
        return pd.Series(0.0, index=series.index)
    eff_window = min(window, max(8, n))
    min_p = max(3, min(eff_window // 4, 15))
    m = series.rolling(eff_window, min_periods=min_p).mean()
    s = series.rolling(eff_window, min_periods=min_p).std()
    z = (series - m) / s.replace(0, np.nan)
    return z.bfill().fillna(0)


def build_regime_features(
    curve_metrics: pd.DataFrame,
    market_data: pd.DataFrame,
    focus_data: pd.DataFrame | None = None,
    vix: pd.Series | None = None,
    lookback: int = REGIME_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """
    Construct feature matrix for regime classification.

    Features (all as rolling z-scores of their changes):
    - slope_change: Change in yield curve slope
    - brl_change: Change in USD/BRL (positive = BRL depreciation)
    - equity_change: Change in Ibovespa
    - vix_level: VIX level z-score
    - inflation_exp_change: Change in Focus IPCA expectation
    """
    features = pd.DataFrame(index=curve_metrics.index)
    is_subdaily = len(curve_metrics) < 150
    eff_lookback = max(1, lookback // 5) if is_subdaily else lookback
    eff_window = 52 if is_subdaily else 252

    # 1. Slope change
    if "slope" in curve_metrics.columns:
        slope_chg = curve_metrics["slope"].diff(eff_lookback)
        features["slope_change"] = _rolling_zscore(slope_chg, eff_window)

    # 2. BRL change (USD/BRL: positive = BRL weakening)
    for col in ["usd_brl", "usd_brl_ptax"]:
        if market_data is not None and col in market_data.columns:
            s = market_data[col].reindex(features.index).ffill()
            brl_chg = s.pct_change(eff_lookback)
            features["brl_change"] = _rolling_zscore(brl_chg, eff_window)
            break

    # 3. Equity returns
    if market_data is not None and "ibovespa" in market_data.columns:
        s = market_data["ibovespa"].reindex(features.index).ffill()
        eq_ret = s.pct_change(eff_lookback)
        features["equity_change"] = _rolling_zscore(eq_ret, eff_window)

    # 4. VIX
    if vix is not None and not vix.empty:
        vix_aligned = vix.reindex(features.index).ffill()
        features["vix_level"] = _rolling_zscore(vix_aligned, eff_window)

    # 5. Inflation expectation change
    if focus_data is not None and not focus_data.empty:
        ipca_col = None
        for col in focus_data.columns:
            if "ipca" in col.lower():
                ipca_col = col
                break
        if ipca_col:
            inf_exp = focus_data[ipca_col].reindex(features.index).ffill()
            inf_chg = inf_exp.diff(eff_lookback)
            features["inflation_exp_change"] = _rolling_zscore(inf_chg, eff_window)

    features = features.dropna(how="all")
    return features


def classify_regimes_rules(
    features: pd.DataFrame,
    threshold: float = REGIME_Z_THRESHOLD,
) -> pd.DataFrame:
    """
    Rule-based regime classification using scoring.

    Each condition contributes +1 or -1 to regime scores.
    The regime with the highest score wins.
    """
    n = len(features)
    scores = pd.DataFrame(0.0, index=features.index, columns=REGIME_LABELS.values())

    slope = features.get("slope_change", pd.Series(0, index=features.index))
    brl = features.get("brl_change", pd.Series(0, index=features.index))
    equity = features.get("equity_change", pd.Series(0, index=features.index))
    vix = features.get("vix_level", pd.Series(0, index=features.index))
    inf_exp = features.get("inflation_exp_change", pd.Series(0, index=features.index))

    # Risk-on: slope ↓, BRL ↑ (USD/BRL ↓), equity ↑, VIX ↓
    scores["risk_on"] += (slope < -threshold).astype(float)
    scores["risk_on"] += (brl < -threshold).astype(float)
    scores["risk_on"] += (equity > threshold).astype(float)
    scores["risk_on"] += (vix < -threshold).astype(float)

    # Risk-off: slope ↑, BRL ↓ (USD/BRL ↑), equity ↓, VIX ↑
    scores["risk_off"] += (slope > threshold).astype(float)
    scores["risk_off"] += (brl > threshold).astype(float)
    scores["risk_off"] += (equity < -threshold).astype(float)
    scores["risk_off"] += (vix > threshold).astype(float)

    # Inflationary: Focus IPCA ↑, curve steepening, BRL ↓
    scores["inflationary"] += (inf_exp > threshold).astype(float)
    scores["inflationary"] += (slope > threshold).astype(float) * 0.5
    scores["inflationary"] += (brl > threshold).astype(float)

    # Disinflationary: Focus IPCA ↓, curve flattening, BRL stable/↑
    scores["disinflationary"] += (inf_exp < -threshold).astype(float)
    scores["disinflationary"] += (slope < -threshold).astype(float) * 0.5
    scores["disinflationary"] += (brl < threshold).astype(float) * 0.5

    # Winner-take-all
    regime = scores.idxmax(axis=1)
    regime[scores.max(axis=1) == 0] = "risk_on"  # default when no signal

    result = pd.DataFrame({
        "regime": regime,
        "confidence": scores.max(axis=1) / scores.sum(axis=1).replace(0, 1),
    }, index=features.index)

    # Add individual scores
    for col in scores.columns:
        result[f"score_{col}"] = scores[col]

    result.index.name = "date"
    return result


def classify_regimes_gmm(
    features: pd.DataFrame,
    n_regimes: int = 4,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    GMM-based regime classification for validation.

    Uses Gaussian Mixture Model to find clusters in the feature space,
    then maps clusters to regime labels based on cluster centers.
    """
    if not HAS_SKLEARN:
        logger.warning("scikit-learn is not installed. Skipping GMM classification.")
        return pd.DataFrame()

    clean = features.dropna()
    if len(clean) < n_regimes * 10:
        logger.warning(f"Too few observations ({len(clean)}) for GMM")
        return pd.DataFrame()

    scaler = StandardScaler()
    X = scaler.fit_transform(clean)

    gmm = GaussianMixture(
        n_components=n_regimes,
        covariance_type="full",
        random_state=random_state,
        n_init=5,
    )
    labels = gmm.fit_predict(X)
    probs = gmm.predict_proba(X)

    # Map clusters to regime names based on center characteristics
    centers = pd.DataFrame(
        scaler.inverse_transform(gmm.means_),
        columns=clean.columns,
    )
    regime_map = _map_clusters_to_regimes(centers, clean.columns)

    result = pd.DataFrame({
        "regime_gmm": [regime_map.get(l, "unknown") for l in labels],
        "confidence_gmm": probs.max(axis=1),
    }, index=clean.index)

    result.index.name = "date"
    return result


def _map_clusters_to_regimes(
    centers: pd.DataFrame,
    feature_names: pd.Index,
) -> dict:
    """
    Heuristic mapping of GMM cluster centers to regime labels.

    Uses the dominant feature of each center to assign a regime name.
    """
    mapping = {}
    used_regimes = set()

    # Score each cluster for each regime
    cluster_regime_scores = {}
    for idx, center in centers.iterrows():
        scores = {}

        slope = center.get("slope_change", 0)
        equity = center.get("equity_change", 0)
        brl = center.get("brl_change", 0)
        inf_exp = center.get("inflation_exp_change", 0)

        scores["risk_on"] = -slope + equity - brl
        scores["risk_off"] = slope - equity + brl
        scores["inflationary"] = inf_exp + brl + slope * 0.5
        scores["disinflationary"] = -inf_exp - slope * 0.5

        cluster_regime_scores[idx] = scores

    # Greedy assignment
    for _ in range(len(centers)):
        best_score = -np.inf
        best_cluster = None
        best_regime = None

        for cluster, scores in cluster_regime_scores.items():
            if cluster in mapping:
                continue
            for regime, score in scores.items():
                if regime in used_regimes:
                    continue
                if score > best_score:
                    best_score = score
                    best_cluster = cluster
                    best_regime = regime

        if best_cluster is not None and best_regime is not None:
            mapping[best_cluster] = best_regime
            used_regimes.add(best_regime)

    return mapping


def get_current_regime(regime_df: pd.DataFrame) -> dict:
    """Return the most recent regime classification and its details."""
    if regime_df.empty:
        return {"regime": "unknown", "confidence": 0, "date": None}

    last = regime_df.iloc[-1]
    return {
        "regime": last["regime"],
        "confidence": last.get("confidence", 0),
        "date": regime_df.index[-1],
        "emoji": REGIME_EMOJI.get(last["regime"], "⚪"),
        "color": REGIME_COLORS.get(last["regime"], "#999"),
    }


def regime_performance_table(
    regime_df: pd.DataFrame,
    returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Average asset performance by regime.

    Returns DataFrame with regimes as index and assets as columns,
    showing annualized returns and hit rate.
    """
    aligned = returns.reindex(regime_df.index)
    aligned["regime"] = regime_df["regime"]

    stats = []
    for regime in REGIME_LABELS.values():
        mask = aligned["regime"] == regime
        subset = aligned.loc[mask].drop(columns=["regime"])

        if subset.empty:
            continue

        row = {"regime": regime, "n_days": len(subset)}
        for col in subset.columns:
            s = subset[col].dropna()
            row[f"{col}_ann_ret"] = s.mean() * 252 * 100
            row[f"{col}_ann_vol"] = s.std() * np.sqrt(252) * 100
            row[f"{col}_hit_rate"] = (s > 0).mean() * 100

        stats.append(row)

    return pd.DataFrame(stats).set_index("regime")
