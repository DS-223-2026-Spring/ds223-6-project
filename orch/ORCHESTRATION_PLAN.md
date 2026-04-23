# Orchestration Plan — MMM Platform

## What Prefect does in this project

Prefect is the workflow orchestration layer. It manages the execution order of
pipeline steps, handles retries on failure, and provides a UI to monitor runs.

## Current pipeline steps (as of Sprint 1)

```
check_source_files → check_db_connection → load_raw_data → validate_data → trigger_model_pipeline
```

| Step | What it does | Status |
|------|-------------|--------|
| check_source_files | Verifies all 3 Robyn CSVs are present | Live |
| check_db_connection | Confirms DB is up and all 6 tables exist | Live |
| load_raw_data | Loads CSVs into raw_spend_data + revenue_data | Checks only (Sprint 2 loads) |
| validate_data | Checks 208 weeks, 5 channels, no negative spend | Live |
| trigger_model_pipeline | Runs adstock + saturation + OLS regression | Stub (Sprint 2) |

## Manual jobs (Sprint 1)

These are done manually by running scripts directly:

| Job | Command | Who runs it |
|-----|---------|-------------|
| Load CSV data | `docker exec mmm_db python load_data.py` | DB Engineer |
| Run EDA | `docker exec mmm_ds python eda.py` | Data Scientist |
| Train model | `docker exec mmm_ds python models/baseline.py` | Data Scientist |
| Run full pipeline | `docker exec mmm_orch python pipeline_flow.py` | Orchestration |

## Jobs to automate in Sprint 2

| Job | Trigger | Notes |
|-----|---------|-------|
| Data load | On new CSV file detected | Use Prefect file watcher |
| Model retrain | After data load completes | Chain from load flow |
| API cache refresh | After model run completes | Notify backend via HTTP |

## Jobs to schedule in Sprint 3+

| Job | Schedule | Notes |
|-----|---------|-------|
| Weekly data refresh | Every Monday 06:00 | Simulated for class demo |
| Model retrain | After weekly refresh | Only if R² drops below 0.80 |

## How to run Prefect locally

```bash
# Start the Prefect server (already running via docker-compose)
# UI available at: http://localhost:4200

# Run the pipeline manually
docker exec mmm_orch python pipeline_flow.py

# Run with data reload forced
docker exec -e RELOAD_DATA=true mmm_orch python pipeline_flow.py

# Run with model training enabled
docker exec -e RUN_MODEL=true mmm_orch python pipeline_flow.py
```

## Configuration parameters (orch/config.py)

| Parameter | Default | Override via |
|-----------|---------|-------------|
| DATA_DIR | /app/data | ENV: DATA_DIR |
| RUN_MODE | manual | ENV: RUN_MODE |
| RELOAD_DATA | false | ENV: RELOAD_DATA |
| RUN_MODEL | false | ENV: RUN_MODEL |
| POSTGRES_HOST | db | ENV: POSTGRES_HOST |
