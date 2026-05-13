# DB Service

PostgreSQL 15 database — stores all raw data, features, and model outputs.

## Tables

| Table | Rows | Description |
|-------|------|-------------|
| `raw_spend_data` | 1040 | Weekly paid spend per channel (208 weeks × 5 channels) |
| `revenue_data` | 208 | Weekly total revenue |
| `organic_signals` | 208 | Competitor sales, newsletter, events, impressions |
| `processed_features` | 1040 | Adstock + saturation values per week/channel |
| `model_runs` | varies | One row per training run — R², hyperparameters, status, model type |
| `channel_coefficients` | varies | ROI, contribution %, recommendation, credible intervals per channel per run |
| `budget_scenarios` | varies | Saved optimizer results with allocation JSON |
| `pipeline_run_log` | varies | Prefect/manual run audit trail |

## Key constraints

- `raw_spend_data`: UNIQUE (week_start, channel) — prevents duplicate loads
- `revenue_data`: UNIQUE (week_start) — one revenue row per week
- `organic_signals`: UNIQUE (week_start) — one organic row per week
- `processed_features`: UNIQUE (week_start, channel) — idempotent pipeline re-runs

## How to run

```bash
# Verify tables were created
docker exec mmm_db psql -U mmm_user -d mmm_db -c "\dt"

# Load all CSV data
docker exec mmm_db python load_data.py

# Verify row counts
docker exec mmm_db python db_helpers.py

# Connect with psql
docker exec -it mmm_db psql -U mmm_user -d mmm_db
```

## db_helpers.py API

```python
from db_helpers import (
    get_connection,     # raw psycopg2 connection
    verify_connection,  # True/False + prints DB version
    select_rows,        # table, optional filters -> list[dict]
    select_query,       # custom SQL -> list[dict]
    insert_row,         # table, data dict -> new id
    insert_rows,        # table, list[dict] -> count (bulk, efficient)
    update_row,         # table, id, data dict -> bool
    delete_row,         # table, id -> bool
    count_rows,         # table -> int
    validate_table,     # table, expected_cols -> {ok, missing_columns}
)
```

```text
## ERD (text)
raw_spend_data ──────────┐  
revenue_data             ├── DS pipeline ──> processed_features  
organic_signals ─────────┘  
model_runs ──> channel_coefficients  
model_runs ──> budget_scenarios  
pipeline_run_log  
```

## Assumptions

- All monetary values use `NUMERIC` to avoid floating-point rounding errors.
- `allocation_json` and `hyperparameters` columns use PostgreSQL `JSONB`.
- Schema is created automatically on first `docker-compose up` via init scripts.
- Init scripts run in alphabetical order: `01_schema.sql` → `02_add_organic_signals.sql` → `03_add_predictions.sql`.
- `channel_coefficients` has optional columns `roi_lower_90` and `roi_upper_90` (added for Bayesian model runs); the backend checks for their existence before querying.