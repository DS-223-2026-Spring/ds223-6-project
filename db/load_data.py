"""
load_data.py
Loads all Robyn CSV files into PostgreSQL including organic signals.
Safe to run multiple times — uses ON CONFLICT DO NOTHING.

Run:
    docker exec mmm_db python load_data.py
"""

import os
import sys
import json
import pandas as pd
from db_helpers import insert_rows, count_rows, verify_connection, get_connection, select_query

DATA_DIR = os.getenv("DATA_DIR", "/app/data")


def load_spend_and_revenue(filepath: str):
    """
    Reads dt_simulated_weekly.csv.
    Loads revenue_data, raw_spend_data, and organic_signals tables.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}  |  Date range: {df['DATE'].min()} -> {df['DATE'].max()}")

    conn   = get_connection()
    cursor = conn.cursor()

    # ── Revenue ──────────────────────────────────────────────────────────────
    inserted_rev = 0
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO revenue_data (week_start, total_revenue)
            VALUES (%s, %s)
            ON CONFLICT (week_start) DO NOTHING
        """, (row["DATE"], float(row["revenue"])))
        inserted_rev += cursor.rowcount
    conn.commit()
    print(f"  revenue_data:      {inserted_rev} rows inserted")

    # ── Paid spend (wide -> long) ────────────────────────────────────────────
    spend_map = {
        "tv_S":       "tv",
        "ooh_S":      "ooh",
        "print_S":    "print",
        "facebook_S": "facebook",
        "search_S":   "search",
    }
    inserted_spend = 0
    for _, row in df.iterrows():
        for col, channel in spend_map.items():
            cursor.execute("""
                INSERT INTO raw_spend_data (week_start, channel, spend_usd)
                VALUES (%s, %s, %s)
                ON CONFLICT (week_start, channel) DO NOTHING
            """, (row["DATE"], channel, float(row[col])))
            inserted_spend += cursor.rowcount
    conn.commit()
    print(f"  raw_spend_data:    {inserted_spend} rows inserted  ({inserted_spend//5 if inserted_spend else 0} weeks x 5 channels)")

    # ── Organic signals ──────────────────────────────────────────────────────
    inserted_org = 0
    for _, row in df.iterrows():
        event_val = str(row.get("events", "na")).strip()
        if event_val.lower() == "nan":
            event_val = "na"
        cursor.execute("""
            INSERT INTO organic_signals
                (week_start, competitor_sales, newsletter_subs,
                 facebook_impressions, search_clicks, event_flag)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (week_start) DO NOTHING
        """, (
            row["DATE"],
            float(row.get("competitor_sales_B", 0)),
            float(row.get("newsletter", 0)),
            float(row.get("facebook_I", 0)),
            float(row.get("search_clicks_P", 0)),
            event_val,
        ))
        inserted_org += cursor.rowcount
    conn.commit()
    conn.close()
    print(f"  organic_signals:   {inserted_org} rows inserted")


def load_holidays(filepath: str):
    """
    Stores US holiday dates as JSON reference in model_runs.
    Skips if already loaded.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    us = df[df["country"] == "US"]
    us_dates = sorted(set(us["ds"].tolist()))
    print(f"  US holidays: {len(us_dates)} unique dates")

    existing = select_query("SELECT id FROM model_runs WHERE model_version = %s", ("holiday_ref",))
    if existing:
        print(f"  Already loaded (id={existing[0]['id']}) — skipping")
        return

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO model_runs (model_version, status, notes, hyperparameters)
        VALUES (%s, %s, %s, %s)
    """, (
        "holiday_ref", "reference",
        "US holiday dates from dt_prophet_holidays.csv",
        json.dumps({"us_holiday_dates": us_dates})
    ))
    conn.commit()
    conn.close()
    print(f"  Stored {len(us_dates)} US holiday dates in model_runs")


def load_curve_params(filepath: str):
    """
    Stores saturation curve params as JSON reference in model_runs.
    Skips if already loaded.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}  |  Freq buckets: {df['freq_bucket'].nunique()}")

    existing = select_query("SELECT id FROM model_runs WHERE model_version = %s", ("curve_ref",))
    if existing:
        print(f"  Already loaded (id={existing[0]['id']}) — skipping")
        return

    params = {}
    for bucket, group in df.groupby("freq_bucket"):
        params[bucket] = {
            "spend":    group["spend_cumulated"].tolist(),
            "response": group["response_cumulated"].round(2).tolist(),
        }

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO model_runs (model_version, status, notes, hyperparameters)
        VALUES (%s, %s, %s, %s)
    """, (
        "curve_ref", "reference",
        "Saturation curve params from df_curve_reach_freq.csv",
        json.dumps(params)
    ))
    conn.commit()
    conn.close()
    print(f"  Stored {len(params)} frequency bucket curves in model_runs")


def validate_load():
    """Validates row counts after loading."""
    print("\n=== Validation ===")
    expected = [
        ("raw_spend_data",  1040, "208 weeks x 5 channels"),
        ("revenue_data",     208, "208 weeks"),
        ("organic_signals",  208, "208 weeks"),
    ]
    all_ok = True
    for table, exp, note in expected:
        actual = count_rows(table)
        ok     = actual >= exp
        status = "OK" if ok else f"WARNING — expected {exp}"
        print(f"  {table:<25} {actual:>6} rows  ({note})  {status}")
        if not ok:
            all_ok = False

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT week_start, total_revenue FROM revenue_data ORDER BY week_start LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        print(f"\n  First week: {row[0]}  |  Revenue: ${row[1]:,.0f}")
    return all_ok


if __name__ == "__main__":
    print("=== MMM Data Loader ===")
    if not verify_connection():
        print("Cannot connect to database.")
        sys.exit(1)

    files = {
        "weekly":   os.path.join(DATA_DIR, "dt_simulated_weekly.csv"),
        "holidays": os.path.join(DATA_DIR, "dt_prophet_holidays.csv"),
        "curves":   os.path.join(DATA_DIR, "df_curve_reach_freq.csv"),
    }
    for name, path in files.items():
        if not os.path.exists(path):
            print(f"\nMissing: {path}")
            sys.exit(1)

    load_spend_and_revenue(files["weekly"])
    load_holidays(files["holidays"])
    load_curve_params(files["curves"])
    validate_load()
    print("\nData loading complete.")
