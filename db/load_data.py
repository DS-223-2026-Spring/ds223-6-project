"""
load_data.py
Loads the three Robyn CSV files into PostgreSQL.
Column names are matched to the ACTUAL Robyn dataset structure.

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING
so re-runs will not duplicate rows.

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
    Reads dt_simulated_weekly.csv (208 rows, weekly 2015-11-23 to 2019-11-11).

    Actual columns:
      DATE, revenue, tv_S, ooh_S, print_S, facebook_I, search_clicks_P,
      search_S, competitor_sales_B, facebook_S, events, newsletter

    Splits into:
      - revenue_data    (1 row per week: DATE + revenue)
      - raw_spend_data  (5 rows per week: one per paid channel)

    Uses ON CONFLICT DO NOTHING — safe to re-run without duplicating data.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}  |  Date range: {df['DATE'].min()} -> {df['DATE'].max()}")

    conn   = get_connection()
    cursor = conn.cursor()

    # ── Revenue (ON CONFLICT because week_start has UNIQUE constraint) ──────
    inserted_rev = 0
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO revenue_data (week_start, total_revenue)
            VALUES (%s, %s)
            ON CONFLICT (week_start) DO NOTHING
        """, (row["DATE"], float(row["revenue"])))
        inserted_rev += cursor.rowcount
    conn.commit()
    print(f"  revenue_data:    {inserted_rev} rows inserted (skipped duplicates)")

    # ── Spend (ON CONFLICT on (week_start, channel) unique constraint) ──────
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
    conn.close()
    print(f"  raw_spend_data:  {inserted_spend} rows inserted (skipped duplicates)")


def load_holidays(filepath: str):
    """
    Reads dt_prophet_holidays.csv (87,651 rows, 123 countries, 1995-2044).
    Filters to US (588 rows) and stores as JSON reference in model_runs.
    Safe to re-run — checks if holiday_ref already exists first.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Total rows: {len(df)}  |  Countries: {df['country'].nunique()}")

    us       = df[df['country'] == 'US'].copy()
    us_dates = set(us['ds'].tolist())
    print(f"  US holidays: {len(us)} rows  |  Unique dates: {len(us_dates)}")

    # Check if already loaded
    existing = select_query(
        "SELECT id FROM model_runs WHERE model_version = %s", ("holiday_ref",)
    )
    if existing:
        print(f"  Holiday reference already exists (id={existing[0]['id']}) — skipping")
        return

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO model_runs (model_version, status, notes, hyperparameters)
        VALUES (%s, %s, %s, %s)
    """, (
        "holiday_ref",
        "reference",
        "US holiday dates from dt_prophet_holidays.csv — used by pipeline to set holiday_flag",
        json.dumps({"us_holiday_dates": sorted(us_dates)})
    ))
    conn.commit()
    conn.close()
    print(f"  Holiday reference stored in model_runs (status=reference)")


def load_curve_params(filepath: str):
    """
    Reads df_curve_reach_freq.csv (300 rows, 10 frequency buckets).
    Stores saturation curve parameters as JSON in model_runs.
    Safe to re-run — checks if curve_ref already exists first.
    """
    print(f"\nLoading {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}  |  Freq buckets: {sorted(df['freq_bucket'].unique().tolist())}")

    # Check if already loaded
    existing = select_query(
        "SELECT id FROM model_runs WHERE model_version = %s", ("curve_ref",)
    )
    if existing:
        print(f"  Curve reference already exists (id={existing[0]['id']}) — skipping")
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
        "curve_ref",
        "reference",
        "Saturation curve params from df_curve_reach_freq.csv — calibrates Hill function K",
        json.dumps(params)
    ))
    conn.commit()
    conn.close()
    print(f"  Curve parameters stored in model_runs (status=reference)")


def validate_load():
    """Prints row counts and spot-checks the loaded data."""
    print("\n=== Validation ===")
    checks = [
        ("raw_spend_data", 1040, "208 weeks x 5 channels"),
        ("revenue_data",    208, "208 weeks"),
    ]
    all_ok = True
    for table, expected, note in checks:
        actual = count_rows(table)
        ok     = actual >= expected
        status = "OK" if ok else f"WARNING — expected {expected}"
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
    print("Verifying database connection...")

    if not verify_connection():
        print("Cannot connect to database. Is the db container running?")
        sys.exit(1)

    files = {
        "dt_simulated_weekly": os.path.join(DATA_DIR, "dt_simulated_weekly.csv"),
        "dt_prophet_holidays": os.path.join(DATA_DIR, "dt_prophet_holidays.csv"),
        "df_curve_reach_freq": os.path.join(DATA_DIR, "df_curve_reach_freq.csv"),
    }
    for name, path in files.items():
        if not os.path.exists(path):
            print(f"\nMissing: {path}")
            print("Place CSV files in the /data folder and re-run.")
            sys.exit(1)

    load_spend_and_revenue(files["dt_simulated_weekly"])
    load_holidays(files["dt_prophet_holidays"])
    load_curve_params(files["df_curve_reach_freq"])
    validate_load()
    print("\nData loading complete.")
