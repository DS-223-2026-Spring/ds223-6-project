"""
bayesian.py — Bayesian MMM using PyMC  (Sprint 4)

Extends the OLS baseline with a fully Bayesian specification.
Key advantage: produces posterior distributions for each channel's ROI,
giving credible intervals (e.g. "$18.32 ± $4.10 at 90% CI") rather than
single point estimates. This makes budget recommendations more trustworthy.

Model specification:
    revenue ~ Normal(mu, sigma)
    mu = intercept
        + Σ_channels (beta_ch * saturated_spend_ch)
        + beta_competitor * competitor_sales
        + beta_newsletter * newsletter_subs
        + beta_event * event_dummy
        + beta_q4 * is_q4
        + beta_month * month

    Priors:
        intercept    ~ Normal(mean_revenue, sigma_revenue)
        beta_ch      ~ HalfNormal(sigma=500000)    -- channel betas must be positive
        beta_controls ~ Normal(0, sigma_control)   -- control variables can be negative
        sigma        ~ HalfNormal(sigma=sigma_revenue)

Run:
    docker exec mmm_ds python models/bayesian.py

Note: Bayesian sampling takes 2-5 minutes. OLS runs in seconds.
Use OLS for rapid iteration; use Bayesian for final demo and reporting.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pymc as pm
import arviz as az
from sqlalchemy import text

import argparse

from db_client import read_table, get_engine
from models.baseline import (
    build_features, get_feature_cols,
    write_processed_features,
    compute_recommendations,
    CHANNELS, ADSTOCK_DECAY, HILL_K_FRACTION, HILL_N,
)

MODEL_VERSION  = "v3.0-bayesian"
DEFAULT_DRAWS  = 500
parser = argparse.ArgumentParser()
parser.add_argument("draws", nargs="?", type=int, default=DEFAULT_DRAWS)
args = parser.parse_args()
DRAWS = args.draws

print("ARGV RECEIVED:", sys.argv)
print("FINAL DRAWS:", DRAWS)
CHAINS         = 2      # parallel chains (2 is enough for class demo)
TARGET_ACCEPT  = 0.9    # NUTS sampler acceptance rate

# Controls that are continuous and need z-score standardisation before PyMC.
# Binary/dummy columns (holiday_flag, event_dummy, is_q4) are NOT standardised —
# their scale is already [0,1] and their coefficients are directly interpretable.
CONTINUOUS_CONTROLS = ["competitor_sales", "newsletter_subs", "month"]


# ── Build the PyMC model ──────────────────────────────────────────────────────

def standardise_controls(df: pd.DataFrame, control_cols: list) -> tuple[pd.DataFrame, dict]:
    """
    Z-score standardises continuous control columns in-place on a copy.
    Binary/flag columns are left unchanged.

    Returns (df_scaled, scalers) where scalers maps col -> (mean, std)
    so coefficients can be back-transformed for reporting.
    """
    df = df.copy()
    scalers = {}
    for col in control_cols:
        if col in CONTINUOUS_CONTROLS:
            mu  = float(df[col].mean())
            std = float(df[col].std())
            if std > 0:
                df[col] = (df[col] - mu) / std
                scalers[col] = (mu, std)
            else:
                scalers[col] = (mu, 1.0)   # constant column — no scaling needed
        # Binary columns (holiday_flag, event_dummy, is_q4) pass through unchanged
    return df, scalers


def build_pymc_model(df: pd.DataFrame, feature_cols: list) -> tuple:
    """
    Builds and returns the PyMC model object.
    Does NOT sample — call pm.sample() on the returned model.

    Continuous control variables MUST be z-score standardised before calling
    this function (see standardise_controls). This keeps all inputs on a
    comparable scale and prevents exp() overflow in the NUTS gradient.

    Prior choices are weakly informative:
    - Channel betas are HalfNormal (must be >= 0: spend can only help revenue)
    - Control betas are Normal(0, sigma_rev) — after standardising, a 1-SD
      change in any control variable should plausibly move revenue by up to
      ~sigma_rev, which is a sensible weakly-informative prior.
    - Intercept centred on mean revenue with wide prior
    """
    saturated_cols = [c for c in feature_cols if c.endswith("_saturated")]
    control_cols   = [c for c in feature_cols if not c.endswith("_saturated")]

    X_sat  = df[saturated_cols].values.astype(float)
    X_ctrl = df[control_cols].values.astype(float) if control_cols else np.zeros((len(df), 0))
    y      = df["total_revenue"].values.astype(float)

    mean_rev   = float(y.mean())
    sigma_rev  = float(y.std())
    n_channels = X_sat.shape[1]
    n_controls = X_ctrl.shape[1]

    with pm.Model() as model:
        # ── Priors ────────────────────────────────────────────────────────────
        intercept = pm.Normal("intercept", mu=mean_rev, sigma=sigma_rev * 2)

        # Channel betas — positive only (spending drives revenue).
        # Saturated features are 0-1 scaled, so sigma=sigma_rev means a
        # fully-saturated channel could plausibly generate ~sigma_rev revenue.
        beta_channels = pm.HalfNormal(
            "beta_channels",
            sigma=sigma_rev,
            shape=n_channels,
        )

        # Control variable betas — can be any sign.
        # After z-score standardisation, each unit = 1 SD of the control,
        # so sigma=sigma_rev is a reasonable weakly-informative prior.
        if n_controls > 0:
            beta_controls = pm.Normal(
                "beta_controls",
                mu=0,
                sigma=sigma_rev,
                shape=n_controls,
            )

        # Observation noise — weakly informative half-normal
        sigma = pm.HalfNormal("sigma", sigma=sigma_rev * 0.5)

        # ── Likelihood ────────────────────────────────────────────────────────
        mu = intercept + pm.math.dot(X_sat, beta_channels)
        if n_controls > 0:
            mu = mu + pm.math.dot(X_ctrl, beta_controls)

        pm.Normal("revenue_obs", mu=mu, sigma=sigma, observed=y)

    return model, saturated_cols, control_cols


# ── Sample and extract results ─────────────────────────────────────────────────

def sample_model(model: pm.Model) -> az.InferenceData:
    """
    Runs NUTS sampler and returns ArviZ InferenceData object.
    """
    print(f"  Sampling {DRAWS} draws × {CHAINS} chains...")
    with model:
        idata = pm.sample(
            draws          = DRAWS,
            chains         = CHAINS,
            target_accept  = TARGET_ACCEPT,
            progressbar    = True,
            return_inferencedata = True,
        )
    return idata


def extract_results(
    idata: az.InferenceData,
    saturated_cols: list,
    control_cols: list,
    df: pd.DataFrame,
    spend_df: pd.DataFrame,
    scalers: dict,
) -> dict:
    """
    Extracts posterior summaries from the InferenceData object.

    `scalers` maps control column name -> (mean, std) from standardisation.
    Used to back-transform control coefficients to original units for reporting.

    Returns a dict matching the structure expected by write_results_to_db()
    from baseline.py, extended with credible interval fields.
    """
    feature_cols = saturated_cols + control_cols

    # ── R² (Bayesian posterior mean) ──────────────────────────────────────────
    posterior_mean = idata.posterior["intercept"].values.mean()
    beta_ch_means  = [
        idata.posterior["beta_channels"].values[:, :, i].mean()
        for i in range(len(saturated_cols))
    ]

    X_sat  = df[saturated_cols].values
    y      = df["total_revenue"].values
    y_pred = posterior_mean + X_sat @ np.array(beta_ch_means)

    if control_cols:
        beta_ctrl_means = [
            idata.posterior["beta_controls"].values[:, :, i].mean()
            for i in range(len(control_cols))
        ]
        X_ctrl = df[control_cols].values   # already standardised
        y_pred = y_pred + X_ctrl @ np.array(beta_ctrl_means)

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2     = float(1 - ss_res / ss_tot)

    print(f"  Bayesian R² (posterior mean): {r2:.4f}")

    # ── ROI estimates with credible intervals ─────────────────────────────────
    coefficients  = {}
    roi_estimates = {}
    roi_lower_90  = {}
    roi_upper_90  = {}

    for i, sat_col in enumerate(saturated_cols):
        ch        = sat_col.replace("_saturated", "")
        raw_spend = spend_df[spend_df["channel"] == ch]["spend_usd"]
        avg_spend = float(raw_spend.mean()) if len(raw_spend) > 0 else 1.0
        avg_sat   = float(df[sat_col].mean())

        # Posterior samples for this channel's beta (on original scale — no scaling needed)
        beta_samples = idata.posterior["beta_channels"].values[:, :, i].flatten()

        coef  = float(beta_samples.mean())
        roi   = max(0.0, (coef * avg_sat) / avg_spend) if avg_spend > 0 else 0.0

        lo_coef = float(np.percentile(beta_samples, 5))
        hi_coef = float(np.percentile(beta_samples, 95))
        roi_lo  = max(0.0, (lo_coef * avg_sat) / avg_spend)
        roi_hi  = max(0.0, (hi_coef * avg_sat) / avg_spend)

        coefficients[sat_col] = round(coef, 6)
        roi_estimates[ch]     = round(roi, 4)
        roi_lower_90[ch]      = round(roi_lo, 4)
        roi_upper_90[ch]      = round(roi_hi, 4)

        print(f"    {ch:<12}  ROI ${roi:.2f}  [90% CI: ${roi_lo:.2f} – ${roi_hi:.2f}]")

    # Back-transform control coefficients to original (unscaled) units for storage
    if control_cols:
        for i, col in enumerate(control_cols):
            beta_samples_ctrl = idata.posterior["beta_controls"].values[:, :, i].flatten()
            coef_scaled = float(beta_samples_ctrl.mean())
            if col in scalers:
                _, std = scalers[col]
                coef_original = coef_scaled / std   # chain rule: d(revenue)/d(x_orig)
            else:
                coef_original = coef_scaled
            coefficients[col] = round(coef_original, 6)

    return {
        "r_squared":         round(r2, 4),
        "r_squared_train":   round(r2, 4),   # Bayesian uses full dataset
        "r_squared_naive":   0.0,
        "mae_test":          float(np.mean(np.abs(y - y_pred))),
        "mae_naive":         float(np.mean(np.abs(y - y.mean()))),
        "feature_cols":      feature_cols,
        "coefficients":      coefficients,
        "roi_estimates":     roi_estimates,
        "roi_lower_90":      roi_lower_90,
        "roi_upper_90":      roi_upper_90,
        "intercept":         float(posterior_mean),
        "predictions":       y_pred.tolist(),
        "actuals":           y.tolist(),
        "model_type":        "bayesian",
        "model_version":     MODEL_VERSION,   # passed to write_results_to_db so DB stores "v3.0-bayesian"
        "draws":             DRAWS,
        "chains":            CHAINS,
    }


# ── Extended DB write (adds CI columns) ──────────────────────────────────────

def write_bayesian_results(model_results: dict, df: pd.DataFrame, spend_df: pd.DataFrame) -> int:
    """
    Writes Bayesian model results to the database.
    Extends the standard write_results_to_db() with credible interval columns.
    Adds roi_lower_90 and roi_upper_90 columns to channel_coefficients if missing.
    """
    from models.baseline import write_results_to_db

    # First write standard results (handles all the existing columns)
    run_id = write_results_to_db(model_results, df, spend_df)

    # Then add CI columns if they don't exist yet
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE channel_coefficients "
            "ADD COLUMN IF NOT EXISTS roi_lower_90 NUMERIC(12,4)"
        ))
        conn.execute(text(
            "ALTER TABLE channel_coefficients "
            "ADD COLUMN IF NOT EXISTS roi_upper_90 NUMERIC(12,4)"
        ))

        # Update with credible interval values
        for ch in CHANNELS:
            conn.execute(text("""
                UPDATE channel_coefficients
                SET roi_lower_90 = :lo, roi_upper_90 = :hi
                WHERE model_run_id = :run_id AND channel = :channel
            """), {
                "lo":      model_results["roi_lower_90"].get(ch),
                "hi":      model_results["roi_upper_90"].get(ch),
                "run_id":  run_id,
                "channel": ch,
            })

    print(f"  Credible intervals written to channel_coefficients (run_id={run_id})")
    return run_id


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== MMM Bayesian Model (PyMC) ===")
    print(f"  Config: {DRAWS} draws × {CHAINS} chains  |  target_accept={TARGET_ACCEPT}")
    print("  Note: sampling takes 2-5 minutes\n")

    print("Loading data from database...")
    spend_df   = read_table("raw_spend_data")
    revenue_df = read_table("revenue_data")
    organic_df = read_table("organic_signals")

    if spend_df.empty or revenue_df.empty:
        print("No data found. Run load_data.py first.")
        sys.exit(1)

    print(f"  Spend rows: {len(spend_df)}  Revenue rows: {len(revenue_df)}  Organic rows: {len(organic_df)}")

    print("\nBuilding feature matrix...")
    from db_client import get_engine as _get_engine
    _engine      = _get_engine()
    # Pass engine so build_features can load holiday dates and set holiday_flag
    features     = build_features(spend_df, revenue_df, organic_df, engine=_engine)
    feature_cols = get_feature_cols(features)
    print(f"  Features: {feature_cols}")

    # Standardise continuous controls before PyMC — prevents exp() overflow
    # in NUTS gradients when raw values are on a very different scale to revenue.
    control_cols_raw = [c for c in feature_cols if not c.endswith("_saturated")]
    features_scaled, scalers = standardise_controls(features, control_cols_raw)
    print(f"  Standardised controls: {list(scalers.keys())}")

    print("\nBuilding PyMC model...")
    model, saturated_cols, control_cols = build_pymc_model(features_scaled, feature_cols)

    print("\nSampling posterior...")
    idata = sample_model(model)

    print("\nExtracting results...")
    # Pass features_scaled so matrix dimensions match; scalers for back-transform
    results = extract_results(idata, saturated_cols, control_cols, features_scaled, spend_df, scalers)

    print(f"\n  R²:               {results['r_squared']:.4f}")
    print(f"  MAE:              ${results['mae_test']:,.0f}")
    print(f"  Model type:       {results['model_type']}")

    print("\nWriting results to database...")
    run_id = write_bayesian_results(results, features, spend_df)

    print(f"\nDone. Run ID = {run_id}")
    print("Visit http://localhost:8000/results to see Bayesian ROI estimates with CIs.")
