"""
baseline.py
MMM feature engineering and baseline model.
Based on actual dt_simulated_weekly.csv column structure.

Sprint 1: adstock + saturation transforms fully implemented.
          OLS model returns real coefficients once data is loaded.

Run:
    docker exec mmm_ds python models/baseline.py
"""

import json
import sys
import os

# Ensure db_client.py (in parent ds/ directory) is importable when running
# from ds/models/ subdirectory: docker exec mmm_ds python models/baseline.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from db_client import read_table, write_dataframe, get_engine
from sqlalchemy import text

# ── Channel configuration ─────────────────────────────────────────────────────
# Decay rates from MMM literature, calibrated to these channel types.
# Sprint 2 will tune these using Bayesian optimization.
ADSTOCK_DECAY = {
    "tv":       0.68,   # TV builds brand memory slowly, fades slowly
    "ooh":      0.40,   # Billboards moderate carryover
    "print":    0.35,   # Print slightly less than OOH
    "facebook": 0.25,   # Social fades faster than traditional
    "search":   0.12,   # Search is intent-driven, minimal carryover
}

# Hill function parameters (K = half-saturation point as fraction of max spend)
# Will be calibrated from df_curve_reach_freq.csv in Sprint 2
HILL_K_FRACTION = {
    "tv":       0.50,
    "ooh":      0.45,
    "print":    0.50,
    "facebook": 0.40,
    "search":   0.35,
}
HILL_N = 2.0   # Shape parameter (steepness)


# ── Transforms ────────────────────────────────────────────────────────────────

def apply_adstock(series: pd.Series, decay: float) -> pd.Series:
    """
    Geometric adstock: adstock[t] = spend[t] + decay * adstock[t-1]
    Models the carryover effect — ads keep working weeks after they run.
    """
    values = series.values.astype(float)
    result = np.zeros(len(values))
    for i in range(len(values)):
        result[i] = values[i] + (decay * result[i-1] if i > 0 else 0.0)
    return pd.Series(result, index=series.index)


def apply_hill(series: pd.Series, k_fraction: float = 0.5, n: float = 2.0) -> pd.Series:
    """
    Hill saturation: f(x) = x^n / (x^n + K^n)
    Models diminishing returns — spending more yields less marginal revenue.
    K is set as a fraction of the max value in the series.
    Output is scaled 0→1.
    """
    x = series.values.astype(float)
    max_x = x.max()
    if max_x == 0:
        return pd.Series(np.zeros(len(x)), index=series.index)
    K = k_fraction * max_x
    saturated = (x**n) / (x**n + K**n)
    return pd.Series(saturated, index=series.index)


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(spend_df: pd.DataFrame, revenue_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds the full feature matrix for the MMM regression.

    Steps:
      1. Pivot spend from long → wide (one col per channel)
      2. Join with revenue
      3. Apply adstock per channel
      4. Apply Hill saturation per channel
      5. Add control variables (seasonality, events encoding)

    Returns DataFrame ready for OLS regression.
    """
    # Pivot spend long → wide
    wide = spend_df.pivot_table(
        index="week_start", columns="channel", values="spend_usd", aggfunc="sum"
    ).reset_index()

    df = wide.merge(revenue_df[["week_start", "total_revenue"]], on="week_start")
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start").reset_index(drop=True)

    # Adstock + saturation per channel
    for channel, decay in ADSTOCK_DECAY.items():
        if channel not in df.columns:
            continue
        k_frac = HILL_K_FRACTION.get(channel, 0.5)
        df[f"{channel}_adstock"]   = apply_adstock(df[channel], decay)
        df[f"{channel}_saturated"] = apply_hill(df[f"{channel}_adstock"], k_frac, HILL_N)

    # Seasonality — strong Q4 peak pattern found in EDA
    df["month"]     = df["week_start"].dt.month
    df["quarter"]   = df["week_start"].dt.quarter
    df["is_q4"]     = (df["quarter"] == 4).astype(int)

    return df


def get_feature_cols(df: pd.DataFrame) -> list:
    """Returns the list of feature columns to use in the model."""
    saturated = [f"{ch}_saturated" for ch in ADSTOCK_DECAY if f"{ch}_saturated" in df.columns]
    controls  = [c for c in ["is_q4", "month"] if c in df.columns]
    return saturated + controls


# ── OLS model ─────────────────────────────────────────────────────────────────

def run_model(df: pd.DataFrame) -> dict:
    """
    Trains OLS regression and returns coefficients + R².
    Writes results to channel_coefficients and model_runs tables.
    """
    feature_cols = get_feature_cols(df)
    X = df[feature_cols].values
    y = df["total_revenue"].values

    # 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False   # time-series — no shuffle
    )

    model = LinearRegression()
    model.fit(X_train, y_train)

    y_pred  = model.predict(X_test)
    r2      = r2_score(y_test, y_pred)
    r2_train = r2_score(y_train, model.predict(X_train))

    print(f"\n  Model Results:")
    print(f"    R² (train): {r2_train:.4f}")
    print(f"    R² (test):  {r2:.4f}")
    print(f"    Intercept:  ${model.intercept_:,.0f}")
    print(f"\n  Coefficients:")

    coefficients = {}
    for col, coef in zip(feature_cols, model.coef_):
        print(f"    {col:<25} {coef:>+12.2f}")
        coefficients[col] = float(coef)

    # Compute ROI per channel (revenue per $1 spent)
    # ROI = coefficient * (avg saturated value) / avg_spend
    roi_estimates = {}
    for ch in ADSTOCK_DECAY:
        sat_col = f"{ch}_saturated"
        if sat_col in df.columns and sat_col in coefficients:
            avg_sat   = df[sat_col].mean()
            avg_spend = df[ch].mean() if df[ch].mean() > 0 else 1
            roi = (coefficients[sat_col] * avg_sat) / avg_spend if avg_spend > 0 else 0
            roi_estimates[ch] = max(0.0, float(roi))
            print(f"    ROI {ch:<12}  ${roi_estimates[ch]:.2f} per $1 spent")

    return {
        "r_squared":      round(r2, 4),
        "r_squared_train": round(r2_train, 4),
        "feature_cols":   feature_cols,
        "coefficients":   coefficients,
        "roi_estimates":  roi_estimates,
        "intercept":      float(model.intercept_),
    }


def write_results_to_db(model_results: dict, df: pd.DataFrame):
    """
    Writes model run + channel coefficients to the database.
    """
    engine = get_engine()

    hyperparams = {
        "adstock_decay":   ADSTOCK_DECAY,
        "hill_k_fraction": HILL_K_FRACTION,
        "hill_n":          HILL_N,
        "feature_cols":    model_results["feature_cols"],
        "intercept":       model_results["intercept"],
        "r_squared_train": model_results["r_squared_train"],
    }

    # Insert model run
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO model_runs (model_version, status, r_squared, hyperparameters, notes)
            VALUES (:version, 'complete', :r2, :params, :notes)
            RETURNING id
        """), {
            "version": "v1.0-ols",
            "r2":      model_results["r_squared"],
            "params":  json.dumps(hyperparams),
            "notes":   "OLS regression with adstock + Hill saturation. Sprint 1 baseline."
        })
        run_id = result.fetchone()[0]

    # Compute total attributed revenue for contribution %
    channels  = list(model_results["roi_estimates"].keys())
    total_roi = sum(model_results["roi_estimates"].values()) or 1

    # Insert one row per channel
    coeff_rows = []
    for ch in channels:
        sat_col   = f"{ch}_saturated"
        coef      = model_results["coefficients"].get(sat_col, 0)
        roi       = model_results["roi_estimates"].get(ch, 0)
        contrib   = round(roi / total_roi * 100, 2)
        coeff_rows.append({
            "model_run_id":     run_id,
            "channel":          ch,
            "coefficient":      round(coef, 6),
            "roi_estimate":     round(roi, 4),
            "contribution_pct": contrib,
        })

    write_dataframe(
        pd.DataFrame(coeff_rows),
        "channel_coefficients",
        if_exists="append"
    )

    print(f"\n  Written to DB:")
    print(f"    model_runs.id = {run_id}  (v1.0-ols, R²={model_results['r_squared']:.4f})")
    print(f"    channel_coefficients: {len(coeff_rows)} rows")
    return run_id


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== MMM Baseline Model ===")

    print("\nLoading data from database...")
    spend_df   = read_table("raw_spend_data")
    revenue_df = read_table("revenue_data")

    if spend_df.empty or revenue_df.empty:
        print("No data in database. Run load_data.py in the DB container first.")
        import sys; sys.exit(1)

    print(f"  Spend rows:   {len(spend_df)}")
    print(f"  Revenue rows: {len(revenue_df)}")

    print("\nBuilding feature matrix...")
    features = build_features(spend_df, revenue_df)
    print(f"  Feature matrix: {features.shape[0]} rows × {features.shape[1]} cols")

    print("\nTraining OLS model...")
    results = run_model(features)

    print("\nWriting results to database...")
    run_id = write_results_to_db(results, features)

    print("\nDone. Check http://localhost:8000/results to see the output.")
