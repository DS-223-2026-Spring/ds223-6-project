"""
baseline.py
Final MMM model — Sprint 3.

Pipeline:
  1. Load spend, revenue, and organic signals from DB
  2. Apply adstock decay per channel
  3. Apply Hill function saturation per channel
  4. Build feature matrix with organic controls
  5. Train OLS regression (80/20 time-series split)
  6. Compare against naive baseline
  7. Compute channel ROI, contribution %, recommendations
  8. Write all outputs to DB:
       - processed_features  (adstock + saturated values per week/channel)
       - model_runs          (R², hyperparameters, notes)
       - channel_coefficients (ROI, contribution, recommendation)

Run:
    docker exec mmm_ds python models/baseline.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error
from db_client import read_table, get_engine
from sqlalchemy import text

# ── Configuration ─────────────────────────────────────────────────────────────

CHANNELS = ["tv", "ooh", "print", "facebook", "search"]

ADSTOCK_DECAY = {
    "tv":       0.68,
    "ooh":      0.40,
    "print":    0.35,
    "facebook": 0.25,
    "search":   0.12,
}

HILL_K_FRACTION = {
    "tv":       0.50,
    "ooh":      0.45,
    "print":    0.50,
    "facebook": 0.40,
    "search":   0.35,
}
HILL_N = 2.0

MODEL_VERSION = "v2.0-ols-organic"


# ── Transforms ────────────────────────────────────────────────────────────────

def apply_adstock(series: pd.Series, decay: float) -> pd.Series:
    """
    Geometric adstock: adstock[t] = spend[t] + decay * adstock[t-1]
    Captures carryover effect — ads keep influencing purchases after they run.
    """
    values = series.values.astype(float)
    result = np.zeros(len(values))
    for i in range(len(values)):
        result[i] = values[i] + (decay * result[i - 1] if i > 0 else 0.0)
    return pd.Series(result, index=series.index)


def apply_hill(series: pd.Series, k_fraction: float = 0.5, n: float = 2.0) -> pd.Series:
    """
    Hill saturation: f(x) = x^n / (x^n + K^n)
    Models diminishing returns. K = k_fraction * max(series). Output is 0-1.
    """
    x     = series.values.astype(float)
    max_x = x.max()
    if max_x == 0:
        return pd.Series(np.zeros(len(x)), index=series.index)
    K         = k_fraction * max_x
    saturated = (x ** n) / (x ** n + K ** n)
    return pd.Series(saturated, index=series.index)


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(
    spend_df: pd.DataFrame,
    revenue_df: pd.DataFrame,
    organic_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Builds the full MMM feature matrix.

    Inputs:
        spend_df:   raw_spend_data (long format — one row per channel per week)
        revenue_df: revenue_data
        organic_df: organic_signals (competitor sales, newsletter, events)

    Returns:
        Wide DataFrame with one row per week containing:
        - raw spend per channel
        - adstock-transformed spend per channel
        - Hill-saturated spend per channel (these are the model regressors)
        - organic controls (competitor_sales, newsletter, event_flag encoded)
        - seasonality controls (month, is_q4)
        - total_revenue (target)
    """
    # Pivot spend long -> wide
    wide = spend_df.pivot_table(
        index="week_start", columns="channel", values="spend_usd", aggfunc="sum"
    ).reset_index()

    df = wide.merge(revenue_df[["week_start", "total_revenue"]], on="week_start")
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start").reset_index(drop=True)

    # Merge organic signals
    if not organic_df.empty:
        organic_df["week_start"] = pd.to_datetime(organic_df["week_start"])
        df = df.merge(
            organic_df[["week_start", "competitor_sales", "newsletter_subs", "event_flag"]],
            on="week_start", how="left"
        )
        # Encode event_flag as binary dummy
        df["event_dummy"] = df["event_flag"].apply(
            lambda x: 1 if str(x).startswith("event") else 0
        )
        df["competitor_sales"]  = df["competitor_sales"].fillna(0)
        df["newsletter_subs"]   = df["newsletter_subs"].fillna(0)
    else:
        df["competitor_sales"] = 0
        df["newsletter_subs"]  = 0
        df["event_dummy"]      = 0

    # Adstock + Hill saturation per channel
    for channel in CHANNELS:
        if channel not in df.columns:
            continue
        decay  = ADSTOCK_DECAY[channel]
        k_frac = HILL_K_FRACTION[channel]
        df[f"{channel}_adstock"]   = apply_adstock(df[channel], decay)
        df[f"{channel}_saturated"] = apply_hill(df[f"{channel}_adstock"], k_frac, HILL_N)

    # Seasonality controls — strong Q4 peak visible in EDA
    df["month"] = df["week_start"].dt.month
    df["is_q4"] = (df["week_start"].dt.quarter == 4).astype(int)

    return df


def get_feature_cols(df: pd.DataFrame) -> list:
    """Returns ordered list of regression feature columns."""
    saturated = [f"{ch}_saturated" for ch in CHANNELS if f"{ch}_saturated" in df.columns]
    controls  = [c for c in ["competitor_sales", "newsletter_subs", "event_dummy", "is_q4", "month"]
                 if c in df.columns]
    return saturated + controls


# ── Model training ────────────────────────────────────────────────────────────

def run_model(df: pd.DataFrame) -> dict:
    """
    Trains OLS regression and compares against naive baseline.

    Train/test split: 80/20 time-ordered (no shuffle — respects time series).
    Naive baseline: predict mean revenue for all weeks.

    Returns:
        dict with R², MAE, coefficients, ROI estimates, predictions
    """
    feature_cols = get_feature_cols(df)
    X = df[feature_cols].values
    y = df["total_revenue"].values

    split     = int(len(df) * 0.8)
    X_train   = X[:split]
    X_test    = X[split:]
    y_train   = y[:split]
    y_test    = y[split:]

    # OLS model
    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred_train = model.predict(X_train)
    y_pred_test  = model.predict(X_test)
    y_pred_all   = model.predict(X)

    r2_train = r2_score(y_train, y_pred_train)
    r2_test  = r2_score(y_test,  y_pred_test)
    mae_test = mean_absolute_error(y_test, y_pred_test)

    # Naive baseline: predict mean of training set
    naive_pred  = np.full(len(y_test), y_train.mean())
    r2_naive    = r2_score(y_test, naive_pred)
    mae_naive   = mean_absolute_error(y_test, naive_pred)

    print(f"\n  Model Results:")
    print(f"    R² train:      {r2_train:.4f}")
    print(f"    R² test:       {r2_test:.4f}  (naive baseline: {r2_naive:.4f})")
    print(f"    MAE test:      ${mae_test:,.0f}  (naive: ${mae_naive:,.0f})")
    print(f"    Improvement:   {((mae_naive - mae_test) / mae_naive * 100):.1f}% over naive")
    print(f"    Intercept:     ${model.intercept_:,.0f}")
    print(f"\n  Coefficients:")

    coefficients = {}
    for col, coef in zip(feature_cols, model.coef_):
        print(f"    {col:<28} {coef:>+14.4f}")
        coefficients[col] = float(coef)

    # ROI = revenue per $1 of actual spend
    roi_estimates = {}
    for ch in CHANNELS:
        sat_col   = f"{ch}_saturated"
        raw_spend = df[ch] if ch in df.columns else pd.Series([0])
        if sat_col in coefficients and raw_spend.mean() > 0:
            avg_sat   = df[sat_col].mean()
            avg_spend = raw_spend.mean()
            roi       = max(0.0, float((coefficients[sat_col] * avg_sat) / avg_spend))
        else:
            roi = 0.0
        roi_estimates[ch] = round(roi, 4)
        print(f"    ROI {ch:<14}  ${roi:.2f} / $1 spent")

    return {
        "r_squared":       round(r2_test, 4),
        "r_squared_train": round(r2_train, 4),
        "r_squared_naive": round(r2_naive, 4),
        "mae_test":        round(mae_test, 2),
        "mae_naive":       round(mae_naive, 2),
        "feature_cols":    feature_cols,
        "coefficients":    coefficients,
        "roi_estimates":   roi_estimates,
        "intercept":       float(model.intercept_),
        "predictions":     y_pred_all.tolist(),
        "actuals":         y.tolist(),
    }


# ── Database writes ───────────────────────────────────────────────────────────

def write_processed_features(df: pd.DataFrame, engine):
    """
    Persists adstock and saturated values to processed_features table.
    Clears existing rows for this pipeline run first.
    """
    rows = []
    for _, row in df.iterrows():
        for ch in CHANNELS:
            if f"{ch}_adstock" not in df.columns:
                continue
            rows.append({
                "week_start":      row["week_start"].strftime("%Y-%m-%d"),
                "channel":         ch,
                "adstock_value":   round(float(row[f"{ch}_adstock"]),   4),
                "saturated_value": round(float(row[f"{ch}_saturated"]), 4),
                "holiday_flag":    0,
                "promo_flag":      0,
            })

    if not rows:
        return

    with engine.begin() as conn:
        # Delete all existing processed features first, then insert fresh.
        # This makes the operation idempotent without needing a UNIQUE constraint.
        conn.execute(text("DELETE FROM processed_features"))
        for r in rows:
            conn.execute(text("""
                INSERT INTO processed_features
                    (week_start, channel, adstock_value, saturated_value, holiday_flag, promo_flag)
                VALUES
                    (:week_start, :channel, :adstock_value, :saturated_value, :holiday_flag, :promo_flag)
            """), r)

    print(f"  processed_features: {len(rows)} rows written ({len(rows)//len(CHANNELS)} weeks x {len(CHANNELS)} channels)")


def compute_recommendations(roi_estimates: dict, spend_df: pd.DataFrame) -> dict:
    """
    Classifies each channel as under-invested, over-invested, or optimal
    by comparing its ROI rank to its share of total spend.
    """
    total_spend = spend_df.groupby("channel")["spend_usd"].sum().to_dict()
    grand_total = sum(total_spend.values()) or 1
    spend_share = {ch: total_spend.get(ch, 0) / grand_total for ch in CHANNELS}

    total_roi = sum(roi_estimates.values()) or 1
    roi_share = {ch: roi_estimates.get(ch, 0) / total_roi for ch in CHANNELS}

    recommendations = {}
    for ch in CHANNELS:
        roi_s   = roi_share.get(ch, 0)
        spend_s = spend_share.get(ch, 0)
        if roi_s == 0:
            recommendations[ch] = "no-signal"
        elif roi_s > spend_s * 1.2:
            recommendations[ch] = "under-invested"   # ROI share > spend share -> worth more
        elif roi_s < spend_s * 0.8:
            recommendations[ch] = "over-invested"    # spending too much for the return
        else:
            recommendations[ch] = "optimal"
    return recommendations


def write_results_to_db(model_results: dict, df: pd.DataFrame, spend_df: pd.DataFrame) -> int:
    """
    Writes model run, channel coefficients, and predictions to the database.
    Returns the new model_run_id.
    """
    engine = get_engine()

    # Persist processed features first
    print("\n  Writing processed features...")
    write_processed_features(df, engine)

    hyperparams = {
        "adstock_decay":     ADSTOCK_DECAY,
        "hill_k_fraction":   HILL_K_FRACTION,
        "hill_n":            HILL_N,
        "feature_cols":      model_results["feature_cols"],
        "intercept":         model_results["intercept"],
        "r_squared_train":   model_results["r_squared_train"],
        "r_squared_naive":   model_results["r_squared_naive"],
        "mae_test":          model_results["mae_test"],
        "mae_naive":         model_results["mae_naive"],
        "includes_organics": True,
    }

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO model_runs
                (model_version, status, r_squared, hyperparameters, notes)
            VALUES
                (:version, 'complete', :r2, CAST(:params AS jsonb), :notes)
            RETURNING id
        """), {
            "version": MODEL_VERSION,
            "r2":      model_results["r_squared"],
            "params":  json.dumps(hyperparams),
            "notes":   (
                f"OLS with adstock + Hill saturation + organic controls. "
                f"R²={model_results['r_squared']:.4f} (naive={model_results['r_squared_naive']:.4f}). "
                f"MAE=${model_results['mae_test']:,.0f}"
            ),
        })
        run_id = result.fetchone()[0]

    # Channel coefficients + recommendations
    recommendations = compute_recommendations(model_results["roi_estimates"], spend_df)
    total_roi       = sum(model_results["roi_estimates"].values()) or 1
    total_rev       = sum(model_results["actuals"])

    with engine.begin() as conn:
        # Auto-add Sprint 3 columns if the migration has not run yet
        conn.execute(text(
            "ALTER TABLE channel_coefficients "
            "ADD COLUMN IF NOT EXISTS recommendation VARCHAR(50)"
        ))
        conn.execute(text(
            "ALTER TABLE channel_coefficients "
            "ADD COLUMN IF NOT EXISTS predicted_revenue_contribution NUMERIC(14,2)"
        ))

        for ch in CHANNELS:
            sat_col     = f"{ch}_saturated"
            coef        = model_results["coefficients"].get(sat_col, 0.0)
            roi         = model_results["roi_estimates"].get(ch, 0.0)
            contrib_pct = round(roi / total_roi * 100, 2)
            pred_rev    = round(roi / total_roi * total_rev, 2)
            rec         = recommendations.get(ch, "unknown")

            conn.execute(text("""
                INSERT INTO channel_coefficients
                    (model_run_id, channel, coefficient, roi_estimate,
                     contribution_pct, recommendation, predicted_revenue_contribution)
                VALUES
                    (:run_id, :channel, :coef, :roi,
                     :contrib, :rec, :pred_rev)
            """), {
                "run_id":   run_id,
                "channel":  ch,
                "coef":     round(coef, 6),
                "roi":      round(roi, 4),
                "contrib":  contrib_pct,
                "rec":      rec,
                "pred_rev": pred_rev,
            })

    print(f"  model_runs.id = {run_id}  ({MODEL_VERSION}, R²={model_results['r_squared']:.4f})")
    print(f"  channel_coefficients: {len(CHANNELS)} rows")
    return run_id


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== MMM Final Model — Sprint 3 ===")

    print("\nLoading data from database...")
    spend_df   = read_table("raw_spend_data")
    revenue_df = read_table("revenue_data")
    organic_df = read_table("organic_signals")

    if spend_df.empty or revenue_df.empty:
        print("No data in database. Run load_data.py in the DB container first.")
        sys.exit(1)

    print(f"  Spend rows:    {len(spend_df)}")
    print(f"  Revenue rows:  {len(revenue_df)}")
    print(f"  Organic rows:  {len(organic_df)}")

    print("\nBuilding feature matrix...")
    features = build_features(spend_df, revenue_df, organic_df)
    print(f"  Feature matrix: {features.shape[0]} rows x {features.shape[1]} cols")
    print(f"  Feature cols:   {get_feature_cols(features)}")

    print("\nTraining OLS model...")
    results = run_model(features)

    print("\nWriting results to database...")
    run_id = write_results_to_db(results, features, spend_df)

    print("\nDone. Visit http://localhost:8000/results to verify output.")
    print(f"      Visit http://localhost:3000 to see the dashboard.")
