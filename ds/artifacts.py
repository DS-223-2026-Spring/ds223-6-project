"""
artifacts.py
Generates visual summary artifacts and insight tables from model results.
Run after baseline.py has written results to the database.

Outputs (saved to /app/data/artifacts/):
  - channel_roi_summary.csv     — ROI table for all channels
  - model_comparison.csv        — R² and MAE across all model runs
  - weekly_predictions.csv      — Actual vs predicted per week
  - insights.txt                — Plain-language model insights

Run:
    docker exec mmm_ds python artifacts.py
"""

import os
import sys
import json
import pandas as pd
from db_client import read_table, get_engine
from sqlalchemy import text

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "artifacts")


def ensure_dir():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)


def export_channel_roi_summary():
    """
    Exports the latest channel ROI table with all columns to CSV.
    File: channel_roi_summary.csv
    """
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT
                cc.channel,
                cc.roi_estimate,
                cc.contribution_pct,
                cc.recommendation,
                cc.coefficient,
                cc.predicted_revenue_contribution,
                mr.model_version,
                mr.r_squared,
                mr.run_at
            FROM channel_coefficients cc
            JOIN model_runs mr ON cc.model_run_id = mr.id
            WHERE mr.status = 'complete'
            ORDER BY mr.run_at DESC, cc.roi_estimate DESC NULLS LAST
            LIMIT 10
        """), conn)

    path = os.path.join(ARTIFACT_DIR, "channel_roi_summary.csv")
    df.to_csv(path, index=False)
    print(f"  Saved: {path}  ({len(df)} rows)")
    return df


def export_model_comparison():
    """
    Exports all model runs for version comparison.
    File: model_comparison.csv
    """
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT
                id,
                model_version,
                r_squared,
                status,
                run_at,
                notes
            FROM model_runs
            WHERE status = 'complete'
            ORDER BY run_at DESC
        """), conn)

    path = os.path.join(ARTIFACT_DIR, "model_comparison.csv")
    df.to_csv(path, index=False)
    print(f"  Saved: {path}  ({len(df)} rows)")
    return df


def export_weekly_predictions():
    """
    Exports weekly actual vs predicted revenue for the latest run.
    File: weekly_predictions.csv
    """
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT
                mp.week_start,
                mp.actual_revenue,
                mp.predicted_revenue,
                mp.residual,
                mr.model_version
            FROM model_predictions mp
            JOIN model_runs mr ON mp.model_run_id = mr.id
            WHERE mr.status = 'complete'
            ORDER BY mr.run_at DESC, mp.week_start
            LIMIT 208
        """), conn)

    path = os.path.join(ARTIFACT_DIR, "weekly_predictions.csv")
    df.to_csv(path, index=False)
    print(f"  Saved: {path}  ({len(df)} rows)")
    return df


def generate_insights(roi_df: pd.DataFrame, model_df: pd.DataFrame) -> str:
    """
    Generates plain-language insights from model results.
    File: insights.txt
    """
    if roi_df.empty or model_df.empty:
        return "No model results found."

    latest = model_df.iloc[0]
    roi_df_sorted = roi_df[roi_df["model_version"] == latest["model_version"]].copy()
    roi_df_sorted = roi_df_sorted.sort_values("roi_estimate", ascending=False)

    best  = roi_df_sorted.iloc[0]  if len(roi_df_sorted) > 0 else None
    worst = roi_df_sorted.iloc[-1] if len(roi_df_sorted) > 0 else None
    under = roi_df_sorted[roi_df_sorted["recommendation"] == "under-invested"]
    over  = roi_df_sorted[roi_df_sorted["recommendation"] == "over-invested"]

    lines = [
        "=== MMM Platform — Model Insights ===",
        f"Model version:  {latest['model_version']}",
        f"R² (test set):  {latest['r_squared']:.4f}  (1.0 = perfect, >0.85 = good)",
        f"Run date:       {latest['run_at']}",
        "",
        "--- Channel ROI Ranking ---",
    ]

    for _, row in roi_df_sorted.iterrows():
        lines.append(
            f"  {row['channel']:<12}  ROI: ${row['roi_estimate']:.2f}/dollar  "
            f"  Contribution: {row['contribution_pct']:.1f}%  "
            f"  Status: {row['recommendation']}"
        )

    lines += ["", "--- Key Findings ---"]

    if best is not None:
        lines.append(
            f"  Best performing:  {best['channel']} at ${best['roi_estimate']:.2f} per $1 spent"
        )
    if worst is not None:
        lines.append(
            f"  Lowest return:    {worst['channel']} at ${worst['roi_estimate']:.2f} per $1 spent"
        )
    if not under.empty:
        channels = ", ".join(under["channel"].tolist())
        lines.append(f"  Under-invested:   {channels} — consider increasing budget here")
    if not over.empty:
        channels = ", ".join(over["channel"].tolist())
        lines.append(f"  Over-invested:    {channels} — consider reducing budget here")

    lines += [
        "",
        "--- Recommendation ---",
        "  Use the Budget Optimizer at http://localhost:3000 to simulate",
        "  budget reallocations and compare predicted revenue outcomes.",
    ]

    text = "\n".join(lines)
    path = os.path.join(ARTIFACT_DIR, "insights.txt")
    with open(path, "w") as f:
        f.write(text)
    print(f"  Saved: {path}")
    return text


if __name__ == "__main__":
    print("=== MMM Artifact Generator ===")
    ensure_dir()

    print("\nExporting channel ROI summary...")
    roi_df = export_channel_roi_summary()

    print("\nExporting model comparison...")
    model_df = export_model_comparison()

    print("\nExporting weekly predictions...")
    export_weekly_predictions()

    print("\nGenerating insights...")
    insights = generate_insights(roi_df, model_df)
    print("\n" + insights)

    print(f"\nAll artifacts saved to: {ARTIFACT_DIR}")
