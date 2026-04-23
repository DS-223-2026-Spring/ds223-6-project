# DB Service

PostgreSQL 15 database for the MMM Platform.

## What's in here

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the PostgreSQL container |
| `init/01_schema.sql` | Creates all 6 tables on first startup |
| `db_helpers.py` | Reusable CRUD functions for all services |
| `load_data.py` | Loads Robyn CSV files into the database |

## Tables

| Table | Description |
|-------|-------------|
| `raw_spend_data` | Weekly ad spend per channel from Robyn CSVs |
| `revenue_data` | Weekly total revenue |
| `processed_features` | Adstock + saturation transforms (written by DS) |
| `model_runs` | One record per model training run |
| `channel_coefficients` | ROI and contribution % per channel per run |
| `budget_scenarios` | Saved optimizer results |

## How to run

```bash
# Start the DB container
docker-compose up db

# Verify tables were created
docker exec mmm_db psql -U mmm_user -d mmm_db -c "\dt"

# Load the Robyn CSV files (place them in /data first)
docker exec mmm_db python load_data.py

# Verify row counts
docker exec mmm_db python db_helpers.py
```

## Using db_helpers.py in other services

```python
from db_helpers import select_rows, insert_rows, update_row, delete_row

# Select all TV spend rows
rows = select_rows("raw_spend_data", {"channel": "tv"})

# Insert a new revenue row
insert_row("revenue_data", {"week_start": "2024-01-01", "total_revenue": 150000})

# Update a model run status
update_row("model_runs", row_id=1, data={"status": "complete", "r_squared": 0.91})

# Delete a scenario
delete_row("budget_scenarios", row_id=3)
```

## Assumptions

- All monetary values stored as `NUMERIC` to avoid float rounding errors.
- `allocation_json` in `budget_scenarios` stores the per-channel split as a JSONB object.
- `hyperparameters` in `model_runs` stores adstock λ and Hill function params as JSONB.
- The schema is created automatically on first `docker-compose up` via the init script.
