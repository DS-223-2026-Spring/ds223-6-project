# Orchestration Service — Prefect

Manages and schedules the MMM data pipeline.
Prefect UI at http://localhost:4200

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Prefect 3.3.6 container |
| `requirements.txt` | Python dependencies |
| `config.py` | All flow parameters from environment variables |
| `pipeline_flow.py` | Main Prefect flow with 5 tasks |
| `ORCHESTRATION_PLAN.md` | Which jobs are manual vs automated |

## How to run

```bash
# The Prefect server starts automatically with docker-compose
# UI: http://localhost:4200

# Run the pipeline flow manually
docker exec mmm_orch python pipeline_flow.py

# Force reload data
docker exec -e RELOAD_DATA=true mmm_orch python pipeline_flow.py

# Enable model training (Sprint 2+)
docker exec -e RUN_MODEL=true mmm_orch python pipeline_flow.py
```

## Flow: mmm-pipeline

```
check_source_files
      ↓
check_db_connection
      ↓
load_raw_data
      ↓
validate_data
      ↓
trigger_model_pipeline
```

See ORCHESTRATION_PLAN.md for full details on manual vs automated jobs.
