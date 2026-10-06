"""
Brazilian Rates Intelligence — Power BI Data Exporter

Generates clean, structured tabular datasets in CSV and Parquet formats
specifically structured for direct connection with Power BI Desktop.
Includes all 6 modules matching the Streamlit tabs:
1. Macro Overview
2. Yield Curve
3. Market Regimes
4. Event Studies
5. Asset Impact
6. Rates Signal
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from config.settings import DATA_START_DATE, PROCESSED_DIR
from src.collectors.bcb_collector import fetch_sgs_series, fetch_focus_latest_median
from src.collectors.market_collector import fetch_market_data
from src.collectors.curve_collector import fetch_historical_curves, extract_curve_vertices
from src.collectors.events_collector import fetch_all_events
from src.processors.macro_processor import interpolate_to_daily, compute_zscore
from src.processors.curve_processor import compute_curve_metrics
from src.processors.returns_processor import compute_all_asset_returns
from src.analytics.regime_classifier import build_regime_features, classify_regimes_rules, regime_performance_table
from src.analytics.event_study import run_event_study, run_multi_asset_event_study
from src.analytics.asset_impact import identify_rate_scenarios, compute_asset_response, scenario_impact_summary, build_impact_heatmap, compute_lead_lag
from src.analytics.rates_signal import (
    compute_inflation_component,
    compute_fiscal_component,
    compute_fx_component,
    compute_monetary_component,
    compute_rates_pressure_score,
    backtest_signal,
    get_current_signal,
)

PBI_DIR = ROOT / "data" / "powerbi"
PBI_DIR.mkdir(parents=True, exist_ok=True)


def export_all():
    start = "2020-01-01"
    end = datetime.now().strftime("%Y-%m-%d")
    print(f"Exporting Brazilian Rates Intelligence tables for Power BI ({start} to {end})...")

    # =========================================================================
    # 1. Macro Overview
    # =========================================================================
    print("1. Processing Macro Overview...")
    sgs = fetch_sgs_series(start=start, end=end)
    focus = fetch_focus_latest_median(["IPCA", "Selic"], start=start)
    market = fetch_market_data(start=start, end=end, include_sectors=False)

    macro_df = pd.DataFrame(index=sgs.index)
    col_rename = {
        "selic_meta": "Selic_Meta",
        "ipca_12m": "IPCA_12m",
        "usd_brl_ptax": "USD_BRL",
        "divida_bruta_pib": "Divida_PIB",
        "resultado_primario": "Resultado_Primario_Milhoes",
        "desemprego_pnad": "Desemprego_PNAD",
    }
    for orig, new_name in col_rename.items():
        if orig in sgs.columns:
            macro_df[new_name] = sgs[orig]

    if not focus.empty:
        if "IPCA_current" in focus.columns:
            macro_df["Focus_IPCA_Ano_Corrente"] = focus["IPCA_current"].reindex(macro_df.index).ffill()
        if "Selic_current" in focus.columns:
            macro_df["Focus_Selic_Ano_Corrente"] = focus["Selic_current"].reindex(macro_df.index).ffill()

    if not market.empty:
        for m_col in market.columns:
            macro_df[f"Mkt_{m_col.upper()}"] = market[m_col].reindex(macro_df.index).ffill()

    macro_df.reset_index(names=["Date"]).to_csv(PBI_DIR / "1_Macro_Overview.csv", index=False)
    macro_df.to_parquet(PBI_DIR / "1_Macro_Overview.parquet")

    # =========================================================================
    # 2. Yield Curve
    # =========================================================================
    print("2. Processing Yield Curve...")
    curves = fetch_historical_curves(start=start, end=end, frequency="weekly")
    vertices = extract_curve_vertices(curves)
    inflation_exp = focus.get("IPCA_current") if not focus.empty else None
    curve_metrics = compute_curve_metrics(vertices, inflation_exp) if not vertices.empty else pd.DataFrame()

    # 2A. Wide metrics
    curve_wide = vertices.copy()
    if not curve_metrics.empty:
        for c in ["level", "slope", "curvature", "real_yield"]:
            if c in curve_metrics.columns:
                curve_wide[f"Metric_{c.title()}"] = curve_metrics[c]

    curve_wide.reset_index(names=["Date"]).to_csv(PBI_DIR / "2_Yield_Curve_TimeSeries.csv", index=False)
    curve_wide.to_parquet(PBI_DIR / "2_Yield_Curve_TimeSeries.parquet")

    # 2B. Unpivoted Curve Snapshots (Current, 1M, 3M, 1Y ago)
    snapshots = []
    if not vertices.empty:
        v_labels = ["1M", "2M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "10Y"]
        v_years = [1/12, 2/12, 3/12, 6/12, 1.0, 2.0, 3.0, 5.0, 10.0]
        v_map = dict(zip(v_labels, v_years))

        last_date = vertices.index[-1]
        dates_to_pick = {
            "Atual": last_date,
            "1 Mês Atrás": vertices.index[max(0, len(vertices)-2)],
            "3 Meses Atrás": vertices.index[max(0, len(vertices)-4)],
            "1 Ano Atrás": vertices.index[max(0, len(vertices)-13)],
        }

        for label, d in dates_to_pick.items():
            row = vertices.loc[d]
            for vl in v_labels:
                if vl in row:
                    snapshots.append({
                        "Snapshot": label,
                        "Date": d,
                        "Vertex_Label": vl,
                        "Vertex_Years": v_map.get(vl, 1.0),
                        "Rate_Pct": row[vl],
                    })

    pd.DataFrame(snapshots).to_csv(PBI_DIR / "2_Yield_Curve_Snapshots.csv", index=False)

    # =========================================================================
    # 3. Market Regimes
    # =========================================================================
    print("3. Processing Market Regimes...")
    returns = compute_all_asset_returns(market) if not market.empty else pd.DataFrame()
    features = build_regime_features(curve_metrics, market, focus) if not curve_metrics.empty else pd.DataFrame()
    rules_df = classify_regimes_rules(features) if not features.empty else pd.DataFrame()

    regimes_pbi = pd.DataFrame(index=rules_df.index) if not rules_df.empty else pd.DataFrame()
    if not rules_df.empty:
        regime_labels_pt = {
            "risk_on": "🟢 Risk-on",
            "risk_off": "🔴 Risk-off",
            "inflationary": "🟡 Inflacionário",
            "disinflationary": "🔵 Desinflacionário",
        }
        regimes_pbi["Regime"] = rules_df["regime"]
        regimes_pbi["Regime_Label"] = rules_df["regime"].map(regime_labels_pt)
        regimes_pbi["Confidence"] = rules_df["confidence"]

        if not features.empty:
            for f_col in features.columns:
                regimes_pbi[f_col] = features[f_col]

        regimes_pbi.reset_index(names=["Date"]).to_csv(PBI_DIR / "3_Market_Regimes.csv", index=False)
        regimes_pbi.to_parquet(PBI_DIR / "3_Market_Regimes.parquet")

        # Performance table
        if not returns.empty:
            perf = regime_performance_table(rules_df, returns)
            perf.reset_index().to_csv(PBI_DIR / "3_Regime_Performance.csv", index=False)

    # =========================================================================
    # 4. Event Studies
    # =========================================================================
    print("4. Processing Event Studies...")
    events = fetch_all_events(start=start, end=end)
    events.to_csv(PBI_DIR / "4_Events_Catalog.csv", index=False)

    car_records = []
    if not events.empty and not returns.empty:
        for asset in ["ibovespa", "usd_brl", "imab11"]:
            if asset in returns.columns:
                for ev_type in ["copom", "fomc", "fiscal"]:
                    res = run_event_study(events, returns, asset=asset, event_type=ev_type, window_before=5, window_after=20)
                    if res is not None:
                        car_series = res.car["car"] * 100
                        std_series = res.car_by_event.std() * 100 / np.sqrt(res.n_events)
                        for day_idx in car_series.index:
                            mean_v = car_series[day_idx]
                            std_v = std_series.get(day_idx, 0)
                            car_records.append({
                                "Asset": asset.upper(),
                                "Event_Type": ev_type.upper(),
                                "Event_Day": int(day_idx),
                                "CAR_Mean_Pct": round(mean_v, 2),
                                "CAR_Lower_95": round(mean_v - 1.96 * std_v, 2),
                                "CAR_Upper_95": round(mean_v + 1.96 * std_v, 2),
                                "T_Stat": round(res.t_stats.get(day_idx, 0), 2),
                                "N_Events": res.n_events,
                            })

    pd.DataFrame(car_records).to_csv(PBI_DIR / "4_Event_Study_CAR.csv", index=False)

    # =========================================================================
    # 5. Asset Impact
    # =========================================================================
    print("5. Processing Asset Impact...")
    if not curve_metrics.empty and not returns.empty and "level" in curve_metrics.columns:
        scenarios = identify_rate_scenarios(curve_metrics["level"], thresholds_bps=[50, 100, 200], window=63)
        if not scenarios.empty:
            responses = compute_asset_response(scenarios, returns, forward_windows=[5, 10, 21, 63])
            responses.to_csv(PBI_DIR / "5_Asset_Impact_Responses.csv", index=False)

            heatmap_21d = build_impact_heatmap(responses, window=21)
            heatmap_21d.reset_index().to_csv(PBI_DIR / "5_Asset_Impact_Heatmap.csv", index=False)

            # Lead Lag
            if "ibovespa" in returns.columns:
                curve_diff = curve_metrics["level"].diff().dropna()
                eq_ret = returns["ibovespa"].dropna()
                aligned = pd.concat([curve_diff, eq_ret], axis=1).dropna()
                ll_df = compute_lead_lag(aligned.iloc[:, 0], aligned.iloc[:, 1], max_lag=20)
                ll_df.to_csv(PBI_DIR / "5_Asset_Impact_LeadLag.csv", index=False)

    # =========================================================================
    # 6. Rates Signal
    # =========================================================================
    print("6. Processing Rates Signal...")
    inf_z = compute_inflation_component(ipca_12m=sgs.get("ipca_12m"))
    fisc_z = compute_fiscal_component(
        divida_pib=sgs.get("divida_bruta_pib"),
        resultado_primario=sgs.get("resultado_primario"),
    )
    fx_z = compute_fx_component(sgs.get("usd_brl_ptax", pd.Series(dtype=float)))
    mon_z = compute_monetary_component(
        focus.get("Selic_current", sgs.get("selic_meta", pd.Series(dtype=float)))
    )

    signal_df = compute_rates_pressure_score(inf_z, fisc_z, fx_z, mon_z)
    if not signal_df.empty:
        # Add qualitative classification
        def _get_interp(score):
            if score > 50: return "Forte pressão de alta"
            elif score > 20: return "Pressão moderada de alta"
            elif score > -20: return "Neutro"
            elif score > -50: return "Pressão moderada de queda"
            else: return "Forte alívio de queda"

        sig_pbi = signal_df.copy()
        sig_pbi["Interpretation"] = sig_pbi["score"].apply(_get_interp)
        if not curve_metrics.empty and "level" in curve_metrics.columns:
            sig_pbi["Curve_Level"] = curve_metrics["level"].reindex(sig_pbi.index).ffill()

        sig_pbi.reset_index(names=["Date"]).to_csv(PBI_DIR / "6_Rates_Signal.csv", index=False)
        sig_pbi.to_parquet(PBI_DIR / "6_Rates_Signal.parquet")

        if not curve_metrics.empty and "level" in curve_metrics.columns:
            backtest_res = backtest_signal(signal_df, curve_metrics[["level"]])
            backtest_res.to_csv(PBI_DIR / "6_Rates_Signal_Backtest.csv", index=False)

    print(f"\nSUCCESS! All Power BI datasets exported to: {PBI_DIR}")


if __name__ == "__main__":
    export_all()
