# Orchestration Service

Prefect 3.3.6 — manages and schedules the MMM pipeline.

Prefect UI: **http://localhost:4200**

## Two flows

### `mmm-pipeline-test` (fast, no side effects)
Validates infrastructure only. Runs in seconds. Use during development.

```
check_source_files → check_db_connection → validate_data
```

### `mmm-pipeline-full` (end-to-end)
Full pipeline from CSV to trained model. Logs results to `pipeline_run_log`.

```
check_source_files
      ↓
check_db_connection
      ↓
load_raw_data        ← calls db/load_data.py via subprocess
      ↓
validate_data        ← asserts row counts, channels, data quality
      ↓
run_model_task       ← calls ds/models/baseline.py via subprocess
      ↓
log to pipeline_run_log
```

## How to run

```bash
# Full pipeline (load + train)
docker exec mmm_orch python pipeline_flow.py

# Test flow only (no data changes)
docker exec mmm_orch python pipeline_flow.py --test

# Force reload data even if already loaded
docker exec -e RELOAD_DATA=true mmm_orch python pipeline_flow.py

# View runs in Prefect UI
open http://localhost:4200
```

## Configuration (config.py)

| Parameter | Default | Override |
|-----------|---------|---------|
| `DATA_DIR` | `/app/data` | `ENV: DATA_DIR` |
| `RUN_MODE` | `manual` | `ENV: RUN_MODE` |
| `RELOAD_DATA` | `false` | `ENV: RELOAD_DATA=true` |
| `RUN_MODEL` | `false` | `ENV: RUN_MODEL=true` |
| `POSTGRES_HOST` | `db` | `ENV: POSTGRES_HOST` |

## Pipeline run log

Every run writes to the `pipeline_run_log` table:

```sql
SELECT flow_name, status, spend_rows, revenue_rows, model_run_id, finished_at
FROM pipeline_run_log
ORDER BY started_at DESC;
```

## Failure handling

- `check_source_files`: retries 2× with 5s delay
- `check_db_connection`: retries 3× with 10s delay (handles slow DB startup)
- `load_raw_data`: retries 1× with 5s delay
- `run_model_task`: retries 1× with 10s delay
- All failures are logged to `pipeline_run_log.status = 'failed'`

## Manual jobs (Sprint 3)

These still run manually but will be connected to Prefect in Sprint 4:

| Job | Command |
|-----|---------|
| Load data | `docker exec mmm_db python load_data.py` |
| Train model | `docker exec mmm_ds python models/baseline.py` |
| Full pipeline | `docker exec mmm_orch python pipeline_flow.py` |
