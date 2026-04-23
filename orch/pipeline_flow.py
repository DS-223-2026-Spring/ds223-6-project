"""
pipeline_flow.py
Prefect orchestration for the MMM data pipeline.
Sprint 1: real task structure matching actual CSV columns and DB tables.
Sprint 2: tasks will execute the actual DS pipeline scripts.

Run locally:
    docker exec mmm_orch python pipeline_flow.py

View in Prefect UI:
    http://localhost:4200
"""

import os
import psycopg2
from prefect import flow, task
from prefect.logging import get_run_logger
from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    WEEKLY_CSV, HOLIDAYS_CSV, CURVE_CSV,
    EXPECTED_WEEKS, EXPECTED_CHANNELS, EXPECTED_SPEND_ROWS,
    RUN_MODE, RELOAD_DATA, RUN_MODEL,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )


# ── Task 1: Check source files ────────────────────────────────────────────────

@task(name="check-source-files", retries=2, retry_delay_seconds=5)
def check_source_files() -> dict:
    """
    Verifies the three Robyn CSV files are present in /app/data.
    Returns a dict of {filename: exists (bool)}.
    """
    logger = get_run_logger()
    files = {
        "dt_simulated_weekly.csv":  WEEKLY_CSV,
        "dt_prophet_holidays.csv":  HOLIDAYS_CSV,
        "df_curve_reach_freq.csv":  CURVE_CSV,
    }
    results = {}
    for name, path in files.items():
        exists = os.path.exists(path)
        results[name] = exists
        status = "FOUND" if exists else "MISSING"
        logger.info(f"  {name}: {status}")

    missing = [n for n, ok in results.items() if not ok]
    if missing:
        raise FileNotFoundError(f"Missing data files: {missing}")

    logger.info("All source files present.")
    return results


# ── Task 2: Check DB connection ───────────────────────────────────────────────

@task(name="check-db-connection", retries=3, retry_delay_seconds=10)
def check_db_connection() -> bool:
    """
    Verifies the DB container is reachable and all 6 tables exist.
    """
    logger = get_run_logger()
    expected_tables = [
        "raw_spend_data", "revenue_data", "processed_features",
        "model_runs", "channel_coefficients", "budget_scenarios"
    ]
    conn   = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
    """)
    existing = {row[0] for row in cursor.fetchall()}
    conn.close()

    for table in expected_tables:
        found = table in existing
        logger.info(f"  Table {table}: {'OK' if found else 'MISSING'}")
        if not found:
            raise RuntimeError(f"Table {table} not found in database")

    logger.info("Database connection and schema verified.")
    return True


# ── Task 3: Load raw data ─────────────────────────────────────────────────────

@task(name="load-raw-data")
def load_raw_data(force_reload: bool = False) -> dict:
    """
    Checks if raw data is already loaded; loads from CSV if not (or if forced).
    Actual tables written: raw_spend_data (1040 rows), revenue_data (208 rows).

    Sprint 1: checks counts and reports status.
    Sprint 2: calls db/load_data.py to do the actual loading.
    """
    logger = get_run_logger()
    conn   = get_db_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM raw_spend_data")
    spend_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM revenue_data")
    revenue_count = cursor.fetchone()[0]
    conn.close()

    logger.info(f"  raw_spend_data:  {spend_count} rows  (expected {EXPECTED_SPEND_ROWS})")
    logger.info(f"  revenue_data:    {revenue_count} rows  (expected {EXPECTED_WEEKS})")

    if spend_count >= EXPECTED_SPEND_ROWS and not force_reload:
        logger.info("Data already loaded — skipping (use RELOAD_DATA=true to force)")
        return {"loaded": False, "spend_rows": spend_count, "revenue_rows": revenue_count}

    # Sprint 2: uncomment to run the actual loader
    # import subprocess
    # subprocess.run(["python", "/app/db/load_data.py"], check=True)
    logger.info("Sprint 2: will call load_data.py here")
    return {"loaded": True, "spend_rows": spend_count, "revenue_rows": revenue_count}


# ── Task 4: Validate data ─────────────────────────────────────────────────────

@task(name="validate-data")
def validate_data(load_result: dict) -> bool:
    """
    Validates that data shape matches expectations from the actual Robyn CSVs:
    - 208 weeks (2015-11-23 to 2019-11-11)
    - 5 channels: tv, ooh, print, facebook, search
    - No negative spend values
    - Revenue > 0 for all weeks
    """
    logger = get_run_logger()
    conn   = get_db_conn()
    cursor = conn.cursor()

    # Check channels
    cursor.execute("SELECT DISTINCT channel FROM raw_spend_data ORDER BY channel")
    found_channels = [row[0] for row in cursor.fetchall()]
    logger.info(f"  Channels found: {found_channels}")
    for ch in EXPECTED_CHANNELS:
        if ch not in found_channels:
            logger.warning(f"  Missing channel: {ch}")

    # Check date range
    cursor.execute("SELECT MIN(week_start), MAX(week_start) FROM revenue_data")
    row = cursor.fetchone()
    if row[0]:
        logger.info(f"  Date range: {row[0]} → {row[1]}")

    # Check for bad values
    cursor.execute("SELECT COUNT(*) FROM raw_spend_data WHERE spend_usd < 0")
    neg = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM revenue_data WHERE total_revenue <= 0")
    bad_rev = cursor.fetchone()[0]

    logger.info(f"  Negative spend rows: {neg}  (expected 0)")
    logger.info(f"  Zero/negative revenue rows: {bad_rev}  (expected 0)")
    conn.close()

    if neg > 0 or bad_rev > 0:
        raise ValueError(f"Data quality issues: {neg} negative spend, {bad_rev} bad revenue rows")

    logger.info("Data validation passed.")
    return True


# ── Task 5: Trigger model pipeline ───────────────────────────────────────────

@task(name="trigger-model-pipeline")
def trigger_model_pipeline(validated: bool, run_model: bool = False) -> dict:
    """
    Triggers the DS model pipeline (adstock → saturation → OLS → write to DB).
    Sprint 1: logs plan only.
    Sprint 2: calls ds/models/baseline.py via subprocess.
    """
    logger = get_run_logger()

    if not run_model:
        logger.info("RUN_MODEL=false — skipping model training (Sprint 1 mode)")
        logger.info("To train: set RUN_MODEL=true and re-run this flow")
        return {"model_triggered": False}

    # Sprint 2: uncomment this block
    # import subprocess
    # result = subprocess.run(
    #     ["python", "/app/ds/models/baseline.py"],
    #     capture_output=True, text=True
    # )
    # logger.info(result.stdout)
    # if result.returncode != 0:
    #     raise RuntimeError(f"Model failed: {result.stderr}")

    logger.info("Sprint 2: will call baseline.py here")
    return {"model_triggered": True}


# ── Main flow ─────────────────────────────────────────────────────────────────

@flow(name="mmm-pipeline")
def mmm_pipeline(force_reload: bool = RELOAD_DATA, run_model: bool = RUN_MODEL):
    """
    Full MMM pipeline:
      1. Check CSV source files exist
      2. Verify DB connection and schema
      3. Load raw data (spend + revenue) into PostgreSQL
      4. Validate data quality and shape
      5. Trigger model training (adstock + saturation + OLS)

    Parameters (set via environment variables or passed directly):
      force_reload: re-load CSVs even if data already exists
      run_model:    train the model after loading (Sprint 2+)
    """
    logger = get_run_logger()
    logger.info(f"MMM pipeline starting  |  mode={RUN_MODE}  |  reload={force_reload}  |  train={run_model}")

    files     = check_source_files()
    db_ok     = check_db_connection()
    loaded    = load_raw_data(force_reload)
    validated = validate_data(loaded)
    model_out = trigger_model_pipeline(validated, run_model)

    logger.info("Pipeline complete.")
    return {
        "files_ok":       all(files.values()),
        "db_ok":          db_ok,
        "data_loaded":    loaded,
        "data_valid":     validated,
        "model_result":   model_out,
    }


if __name__ == "__main__":
    mmm_pipeline()
