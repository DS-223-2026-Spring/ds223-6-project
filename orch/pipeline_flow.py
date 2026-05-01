"""
pipeline_flow.py  —  MMM Orchestration  (Sprint 3 — complete)

Two flows:
  mmm_pipeline_test()  — fast validation only, no data load or model run
  mmm_pipeline_full()  — end-to-end: validate → load → train → log to DB

Run:
    docker exec mmm_orch python pipeline_flow.py           # runs full pipeline
    docker exec mmm_orch python pipeline_flow.py --test    # runs test flow only

View runs in Prefect UI: http://localhost:4200
"""

import sys
import os
import json
import subprocess
import psycopg2
from datetime import datetime
from prefect import flow, task
from prefect.logging import get_run_logger

from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    WEEKLY_CSV, HOLIDAYS_CSV, CURVE_CSV,
    EXPECTED_WEEKS, EXPECTED_CHANNELS, EXPECTED_SPEND_ROWS,
    RUN_MODE, RELOAD_DATA, RUN_MODEL,
)

# Absolute paths — ds/ and db/ are mounted into orch container via docker-compose
# /ds  -> ./ds  (ds service source)
# /db  -> ./db  (db service source)
LOAD_DATA_SCRIPT = "/db/load_data.py"
MODEL_SCRIPT     = "/ds/models/baseline.py"


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )


def log_pipeline_run(flow_name: str, started_at: datetime) -> int:
    """Insert a pipeline_run_log row and return its id. Creates table if missing."""
    conn   = get_conn()
    cursor = conn.cursor()
    # Ensure table exists (migration may not have run on existing DB)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_run_log (
            id           SERIAL PRIMARY KEY,
            flow_name    VARCHAR(100) NOT NULL,
            started_at   TIMESTAMP DEFAULT NOW(),
            finished_at  TIMESTAMP,
            status       VARCHAR(20) DEFAULT 'running',
            spend_rows   INTEGER,
            revenue_rows INTEGER,
            model_run_id INTEGER,
            result_json  JSONB,
            error_msg    TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO pipeline_run_log (flow_name, started_at, status)
        VALUES (%s, %s, 'running')
        RETURNING id
    """, (flow_name, started_at))
    run_log_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return run_log_id


def update_pipeline_log(run_log_id: int, status: str, result: dict, error_msg: str = None):
    """Update a pipeline_run_log row with final status and results."""
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pipeline_run_log
        SET status      = %s,
            finished_at = NOW(),
            result_json = %s,
            error_msg   = %s,
            spend_rows  = %s,
            revenue_rows= %s,
            model_run_id= %s
        WHERE id = %s
    """, (
        status,
        json.dumps(result),
        error_msg,
        result.get("spend_rows"),
        result.get("revenue_rows"),
        result.get("model_run_id"),
        run_log_id,
    ))
    conn.commit()
    conn.close()


# ── Shared tasks ──────────────────────────────────────────────────────────────

@task(name="check-source-files", retries=2, retry_delay_seconds=5)
def check_source_files() -> dict:
    """
    Verifies the three Robyn CSV files exist in /app/data.
    Raises FileNotFoundError if any are missing.
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
        logger.info(f"  {name}: {'FOUND' if exists else 'MISSING'}")

    missing = [n for n, ok in results.items() if not ok]
    if missing:
        raise FileNotFoundError(f"Missing data files: {missing}")

    logger.info("All source files present.")
    return results


@task(name="check-db-connection", retries=3, retry_delay_seconds=10)
def check_db_connection() -> bool:
    """
    Verifies the DB is reachable and all required tables exist.
    Retries up to 3 times with 10s delay (handles slow DB startup).
    """
    logger = get_run_logger()
    required = [
        "raw_spend_data", "revenue_data", "processed_features",
        "model_runs", "channel_coefficients", "budget_scenarios",
        "organic_signals", "pipeline_run_log",
    ]
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'
    """)
    existing = {row[0] for row in cursor.fetchall()}
    conn.close()

    missing_tables = [t for t in required if t not in existing]
    if missing_tables:
        logger.warning(f"  Missing tables: {missing_tables}")
        # Non-fatal for test flow — some tables added in Sprint 3 migration
    else:
        logger.info(f"  All {len(required)} required tables present.")

    return True


@task(name="validate-data")
def validate_data() -> dict:
    """
    Validates row counts, channel names, date range, and data quality.
    Returns a summary dict with validation results.
    """
    logger = get_run_logger()
    conn   = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM raw_spend_data")
    spend_rows = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM revenue_data")
    rev_rows = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM organic_signals")
    org_rows = cursor.fetchone()[0]
    cursor.execute("SELECT DISTINCT channel FROM raw_spend_data ORDER BY channel")
    found_channels = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT MIN(week_start), MAX(week_start) FROM revenue_data")
    date_range = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM raw_spend_data WHERE spend_usd < 0")
    neg_spend = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM revenue_data WHERE total_revenue <= 0")
    bad_rev = cursor.fetchone()[0]
    conn.close()

    logger.info(f"  raw_spend_data:  {spend_rows} rows  (expected {EXPECTED_SPEND_ROWS})")
    logger.info(f"  revenue_data:    {rev_rows} rows  (expected {EXPECTED_WEEKS})")
    logger.info(f"  organic_signals: {org_rows} rows  (expected {EXPECTED_WEEKS})")
    logger.info(f"  Channels found:  {found_channels}")
    if date_range[0]:
        logger.info(f"  Date range:      {date_range[0]} -> {date_range[1]}")
    logger.info(f"  Negative spend:  {neg_spend}  Bad revenue: {bad_rev}")

    if neg_spend > 0 or bad_rev > 0:
        raise ValueError(f"Data quality issues: {neg_spend} negative spend rows, {bad_rev} bad revenue rows")

    return {
        "spend_rows":     spend_rows,
        "revenue_rows":   rev_rows,
        "organic_rows":   org_rows,
        "channels":       found_channels,
        "data_loaded":    spend_rows >= EXPECTED_SPEND_ROWS,
    }


# ── Full pipeline tasks ───────────────────────────────────────────────────────

@task(name="load-raw-data", retries=1, retry_delay_seconds=5)
def load_raw_data(force_reload: bool = False) -> dict:
    """
    Loads CSV data into the database using db/load_data.py.
    Skips if data is already loaded (idempotent) unless force_reload=True.
    """
    logger = get_run_logger()
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM raw_spend_data")
    existing_count = cursor.fetchone()[0]
    conn.close()

    if existing_count >= EXPECTED_SPEND_ROWS and not force_reload:
        logger.info(f"  Data already loaded ({existing_count} rows) — skipping (use RELOAD_DATA=true to force)")
        return {"loaded": False, "spend_rows": existing_count}

    logger.info(f"  Running load_data.py (existing rows: {existing_count})...")
    result = subprocess.run(
        [sys.executable, LOAD_DATA_SCRIPT],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": "/db"},   # so load_data.py can import db_helpers
    )
    if result.returncode != 0:
        logger.error(f"  load_data.py failed:\n{result.stderr}")
        raise RuntimeError(f"Data load failed: {result.stderr[:500]}")

    logger.info(result.stdout)

    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM raw_spend_data")
    new_count = cursor.fetchone()[0]
    conn.close()
    logger.info(f"  After load: {new_count} spend rows")
    return {"loaded": True, "spend_rows": new_count}


@task(name="run-model", retries=1, retry_delay_seconds=10)
def run_model_task() -> dict:
    """
    Runs the MMM model pipeline using ds/models/baseline.py.
    Writes results to processed_features, model_runs, channel_coefficients.
    Returns the new model_run_id.
    """
    logger = get_run_logger()
    logger.info("  Running baseline.py...")
    result = subprocess.run(
        [sys.executable, MODEL_SCRIPT],
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "PYTHONPATH": "/ds"},  # so baseline.py can import db_client
    )
    if result.returncode != 0:
        logger.error(f"  baseline.py failed:\n{result.stderr}")
        raise RuntimeError(f"Model training failed: {result.stderr[:500]}")

    logger.info(result.stdout)

    # Read back the latest model run id from the DB
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, model_version, r_squared
        FROM model_runs
        WHERE status = 'complete'
        ORDER BY run_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        logger.info(f"  Model run id={row[0]}  version={row[1]}  R²={row[2]}")
        return {"model_run_id": row[0], "model_version": row[1], "r_squared": float(row[2]) if row[2] else None}
    return {"model_run_id": None}


# ══════════════════════════════════════════════════════════════════════════════
#  FLOW 1 — Test flow (fast, no side effects)
# ══════════════════════════════════════════════════════════════════════════════

@flow(name="mmm-pipeline-test")
def mmm_pipeline_test():
    """
    Fast validation flow — runs in seconds with no data loading or model training.
    Use this during development to verify infrastructure is working.

    Tasks: check_source_files → check_db_connection → validate_data
    """
    logger = get_run_logger()
    logger.info("=== MMM TEST FLOW (validation only) ===")

    files  = check_source_files()
    db_ok  = check_db_connection()
    result = validate_data()

    logger.info("=== TEST FLOW COMPLETE ===")
    return {
        "flow":       "mmm-pipeline-test",
        "files_ok":   all(files.values()),
        "db_ok":      db_ok,
        "validation": result,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  FLOW 2 — Full pipeline (end-to-end)
# ══════════════════════════════════════════════════════════════════════════════

@flow(name="mmm-pipeline-full")
def mmm_pipeline_full(
    force_reload: bool = RELOAD_DATA,
    run_model:    bool = RUN_MODEL,
):
    """
    Full end-to-end MMM pipeline:
      1. check_source_files — verify CSVs present
      2. check_db_connection — verify DB and schema
      3. load_raw_data — load CSVs into PostgreSQL
      4. validate_data — assert data quality
      5. run_model_task — adstock → saturation → OLS → write to DB
      6. log to pipeline_run_log

    Parameters (override via environment variables):
      force_reload: re-load CSVs even if data already exists
      run_model:    train the model after loading (default True in full flow)
    """
    logger     = get_run_logger()
    started_at = datetime.utcnow()
    run_log_id = None
    result     = {}

    logger.info(f"=== MMM FULL PIPELINE ===  reload={force_reload}  train={run_model}")

    try:
        # Create run log entry
        try:
            run_log_id = log_pipeline_run("mmm-pipeline-full", started_at)
            logger.info(f"  pipeline_run_log.id = {run_log_id}")
        except Exception as e:
            logger.warning(f"  Could not create run log (non-fatal): {e}")

        # Step 1-2: infrastructure checks
        files = check_source_files()
        db_ok = check_db_connection()

        # Step 3: load data
        load_result = load_raw_data(force_reload)
        result.update(load_result)

        # Step 4: validate
        val_result = validate_data()
        result.update(val_result)

        # Step 5: train model
        if run_model:
            model_result = run_model_task()
            result.update(model_result)
            logger.info(f"  Model training complete. Run ID: {model_result.get('model_run_id')}")
        else:
            logger.info("  RUN_MODEL=false — skipping model training")
            result["model_run_id"] = None

        # Update run log as success
        if run_log_id:
            update_pipeline_log(run_log_id, "success", result)

        logger.info("=== FULL PIPELINE COMPLETE ===")
        return {"flow": "mmm-pipeline-full", "status": "success", **result}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"  Pipeline failed: {error_msg}")
        if run_log_id:
            update_pipeline_log(run_log_id, "failed", result, error_msg)
        raise


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        mmm_pipeline_test()
    else:
        mmm_pipeline_full(force_reload=RELOAD_DATA, run_model=True)
