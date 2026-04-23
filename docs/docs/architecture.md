# Architecture

## Overview

The MMM Platform is a six-service containerized application.
All services communicate over a shared Docker network (`mmm_network`).

## Services

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `mmm_db` | postgres:15 | 5432 | PostgreSQL database |
| `mmm_ds` | python:3.11 | — | Data pipeline + modeling |
| `mmm_back` | python:3.11 | 8000 | FastAPI REST API |
| `mmm_front` | node:20 | 3000 | React dashboard |
| `mmm_orch` | python:3.11 | 4200 | Prefect orchestration |
| `mmm_docs` | python:3.11 | 8080 | MkDocs documentation |

## Data flow

```
CSV files (data/)
      ↓
  DB service (load_data.py)
      ↓ writes
  raw_spend_data + revenue_data
      ↓
  DS service (baseline.py)
      ↓ applies adstock + saturation + OLS
  channel_coefficients + model_runs
      ↓
  Backend API (GET /results)
      ↓
  Frontend Dashboard
```

## Database tables

| Table | Written by | Read by |
|-------|-----------|--------|
| raw_spend_data | DB / Orch | DS, Back |
| revenue_data | DB / Orch | DS, Back |
| processed_features | DS | DS, Back |
| model_runs | DS | Back |
| channel_coefficients | DS | Back |
| budget_scenarios | Back | Back, Front |
