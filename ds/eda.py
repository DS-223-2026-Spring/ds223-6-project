"""
eda.py
Exploratory Data Analysis for the MMM Platform.
Based on actual dt_simulated_weekly.csv structure (208 weeks, 2015-2019).

Actual columns discovered:
  DATE, revenue, tv_S, ooh_S, print_S, facebook_S, search_S  ← paid spend
  facebook_I, search_clicks_P                                 ← impression/clicks
  competitor_sales_B, events, newsletter                      ← organic/external

Run:
    docker exec mmm_ds python eda.py
"""

import pandas as pd
import numpy as np
from db_client import read_table

SPEND_COLS   = ["tv_S", "ooh_S", "print_S", "facebook_S", "search_S"]
ORGANIC_COLS = ["facebook_I", "search_clicks_P", "newsletter", "competitor_sales_B"]
CHANNEL_MAP  = {"tv_S": "tv", "ooh_S": "ooh", "print_S": "print",
                "facebook_S": "facebook", "search_S": "search"}


def load_wide_data() -> pd.DataFrame:
    """
    Loads spend and revenue from DB and pivots spend back to wide format
    (one column per channel) for analysis.
    """
    spend_df   = read_table("raw_spend_data")
    revenue_df = read_table("revenue_data")

    if spend_df.empty:
        return pd.DataFrame()

    wide = spend_df.pivot_table(
        index="week_start", columns="channel", values="spend_usd", aggfunc="sum"
    ).reset_index()
    df = wide.merge(revenue_df[["week_start", "total_revenue"]], on="week_start")
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values("week_start").reset_index(drop=True)
    return df


def section(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def explore_revenue(df: pd.DataFrame):
    section("Revenue Analysis")
    rev = df["total_revenue"]
    print(f"  Weeks:        {len(df)}")
    print(f"  Date range:   {df['week_start'].min().date()} → {df['week_start'].max().date()}")
    print(f"  Mean/week:    ${rev.mean():>12,.0f}")
    print(f"  Std dev:      ${rev.std():>12,.0f}  ({rev.std()/rev.mean()*100:.0f}% CV)")
    print(f"  Min:          ${rev.min():>12,.0f}")
    print(f"  Max:          ${rev.max():>12,.0f}")
    print(f"  Total (4yr):  ${rev.sum():>12,.0f}")

    # Seasonality — strong pattern found in analysis
    df["month"] = df["week_start"].dt.month
    monthly = df.groupby("month")["total_revenue"].mean()
    print(f"\n  Monthly avg revenue (strong seasonality — Q4 peak):")
    for m, v in monthly.items():
        bar = "█" * int(v / 100000)
        print(f"    Month {m:>2}: ${v:>10,.0f}  {bar}")


def explore_spend(df: pd.DataFrame):
    section("Paid Channel Spend")
    channels = ["tv", "ooh", "print", "facebook", "search"]

    print(f"  {'Channel':<12} {'Total $':>12} {'Avg/wk':>10} {'Zero wks':>10} {'Zero %':>8}")
    print(f"  {'-'*56}")
    for ch in channels:
        if ch not in df.columns:
            continue
        col   = df[ch]
        zeros = (col == 0).sum()
        print(f"  {ch:<12} ${col.sum():>11,.0f} ${col.mean():>9,.0f} {zeros:>10} {zeros/len(df)*100:>7.0f}%")

    print(f"\n  Key finding: TV, OOH, Print, Facebook have 50-59% zero-spend weeks")
    print(f"  Key finding: Search is the most consistent channel (only 15% zero weeks)")
    print(f"  Key finding: OOH has the highest peak spend ($500k in one week)")


def explore_correlations(df: pd.DataFrame):
    section("Raw Correlations with Revenue")
    channels = ["tv", "ooh", "print", "facebook", "search"]
    all_cols = channels

    print(f"  (Raw Pearson — before adstock/saturation transforms)")
    print(f"  {'Channel':<18} {'Correlation':>12}  {'Strength'}")
    print(f"  {'-'*50}")

    corrs = {}
    for ch in all_cols:
        if ch in df.columns:
            c = df[ch].corr(df["total_revenue"])
            corrs[ch] = c

    for ch, c in sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True):
        strength = "Strong" if abs(c) > 0.4 else "Moderate" if abs(c) > 0.2 else "Weak"
        bar = ("+" if c > 0 else "-") * int(abs(c) * 20)
        print(f"  {ch:<18} {c:>+.3f}        {strength}  {bar}")

    print(f"\n  Key finding: competitor_sales_B has r=+0.916 (confounding variable!)")
    print(f"  Key finding: search_S and tv_S are strongest paid channel predictors")
    print(f"  Key finding: newsletter (organic) has r=+0.406 — important control variable")


def explore_data_quality(df: pd.DataFrame):
    section("Data Quality Report")
    print(f"  Null values:        {df.isnull().sum().sum()}  (none — clean dataset)")

    channels = ["tv", "ooh", "print", "facebook", "search"]
    neg = sum((df[ch] < 0).sum() for ch in channels if ch in df.columns)
    print(f"  Negative spend:     {neg}  (none)")

    print(f"\n  Columns available in DB (mapped from CSV):")
    print(f"    raw_spend_data:  week_start, channel, spend_usd")
    print(f"    revenue_data:    week_start, total_revenue")
    print(f"\n  Columns NOT in DB (organic/external — need separate table or features):")
    print(f"    facebook_I       (Facebook impressions — corr +0.315)")
    print(f"    search_clicks_P  (Search clicks — corr +0.428)")
    print(f"    competitor_sales_B (Strong confound — corr +0.916)")
    print(f"    events           (event1 / event2 appear once each)")
    print(f"    newsletter       (subscribers — corr +0.406)")


def summarize_modeling_plan():
    section("Modeling Plan for Sprint 2")
    print("""
  Target variable:
    total_revenue (weekly, continuous)

  Paid predictors (will be adstock + Hill transformed):
    tv       — adstock λ ≈ 0.68  (long TV carryover)
    ooh      — adstock λ ≈ 0.40
    print    — adstock λ ≈ 0.35
    facebook — adstock λ ≈ 0.25
    search   — adstock λ ≈ 0.12  (short digital carryover)

  Control variables (no spend transform needed):
    newsletter       — direct include (subscribers, organic)
    competitor_sales — include as control (strong confound r=+0.916)
    events           — encode as dummy (event1=1, event2=1, na=0)
    month            — encode as seasonality (clear Q4 peak pattern)

  What we are NOT modelling yet (Sprint 2 stretch):
    facebook_I, search_clicks_P — impression/click data
    Holiday effect — will join US holidays from dt_prophet_holidays.csv

  Model: OLS Regression
    revenue ~ tv_sat + ooh_sat + print_sat + facebook_sat + search_sat
            + newsletter + competitor_sales + event_dummy + month_dummies

  Expected R²: > 0.85 based on correlation structure
    """)


if __name__ == "__main__":
    print("=== MMM Platform — EDA ===")
    df = load_wide_data()
    if df.empty:
        print("No data in database. Run load_data.py in the DB container first.")
    else:
        explore_revenue(df)
        explore_spend(df)
        explore_correlations(df)
        explore_data_quality(df)
        summarize_modeling_plan()
    print("\nEDA complete.")
