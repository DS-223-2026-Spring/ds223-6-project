# MMM Platform

> **Marketing Mix Modeling Platform** — a containerized, full-stack analytics application that attributes revenue to advertising channels and optimizes marketing budget allocation.

Built for the Marketing Analytics class group project. Implements the Marketing Mix Modeling (MMM) methodology used by companies like P&G, Unilever, and Google — powered by Meta's open-source Robyn demo dataset.

---

## What it does

Given 4 years of weekly ad spend across 5 channels (TV, OOH, Print, Facebook, Search) and weekly revenue, the platform:

1. **Transforms** raw spend data using adstock decay (carryover effects) and Hill function saturation (diminishing returns)
2. **Includes organic controls** — competitor sales, newsletter subscribers, and event flags to isolate true paid channel effect
3. **Trains** an OLS regression model to attribute revenue to each channel
4. **Calculates** the ROI (revenue per $1 spent) and a recommendation for each channel (under-invested / over-invested / optimal)
5. **Optimizes** budget allocation — given any total budget, finds the spend split that maximizes predicted revenue with realistic per-channel floors and ceilings
6. **Presents** everything through a fully interactive React web dashboard

---

## Architecture

```
CSV files (data/)
      │
      ▼
  db service          ← PostgreSQL 15 — stores all raw data, features, and model outputs
      │
      ▼
  ds service          ← Python — EDA, adstock/saturation transforms, OLS regression
      │               ← Also runs a lightweight trigger API on port 5000 (internal)
      ▼
  back service        ← FastAPI — REST API serving results and running the optimizer
      │
      ▼
  front service       ← React — dashboard with charts, KPI cards, and budget sliders
      │
  orch service        ← Prefect — two pipeline flows (test + full)
  docs service        ← MkDocs — live documentation site
```

All six services run in Docker containers on a shared network (`mmm_network`). They communicate using service names — e.g. `back` reaches `db` at `db:5432` and calls `ds` at `ds:5000`.

---

## Services and ports

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| Database | `mmm_db` | 5432 | PostgreSQL — all data storage |
| Data Science | `mmm_ds` | 5000 (internal) | Pipeline scripts, EDA, model training + trigger API |
| Backend API | `mmm_back` | **8000** | FastAPI REST API + Swagger UI |
| Frontend | `mmm_front` | **3000** | React dashboard |
| Orchestration | `mmm_orch` | **4200** | Prefect workflow UI |

> Port 5000 on the DS service is internal only — it is not exposed to the host machine.

---

## Team roles

| Branch | Role | Service owned |
|--------|------|---------------|
| `db` | DB Engineer | `db/` — schema, helpers, data loader |
| `ds` | Data Scientist | `ds/` — EDA, transforms, model, trigger API |
| `back` | Backend Developer | `back/` — FastAPI endpoints |
| `front` | Frontend Developer | `front/` — React dashboard |
| `orch` | Orchestration | `orch/` — Prefect pipeline flows |
| `main` | PM | Repo structure, docs, PR reviews |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [Git](https://git-scm.com/)

No other local installs required — Python, Node.js, and all libraries run inside containers.

---

## Quick start

```bash
# 1. Clone the repository
git clone <repo-url>
cd mmm-platform

# 2. Copy environment file (never commit .env)
cp .env.example .env

# 3. Start all 6 services
docker compose up --build
```

First build takes 3–8 minutes. Subsequent starts take ~30 seconds.

---

## First-time data setup

After all containers are running, load the CSV data and train the model:

```bash
# Load all 3 Robyn CSV files into PostgreSQL
# Populates: raw_spend_data, revenue_data, organic_signals
docker exec mmm_db python load_data.py

# Run exploratory data analysis
docker exec mmm_ds python eda.py

# Train the MMM model and write results to the database
# Writes: processed_features, model_runs, channel_coefficients
docker exec mmm_ds python models/baseline.py
```

After `baseline.py` completes, the dashboard at `http://localhost:3000` shows real channel ROI data, recommendations, and the live budget optimizer.

---

## Data sources

Three open-source datasets from Meta's [Robyn MMM project](https://github.com/facebookexperimental/Robyn):

| File | Rows | Loaded into | Description |
|------|------|-------------|-------------|
| `dt_simulated_weekly.csv` | 208 | `raw_spend_data`, `revenue_data`, `organic_signals` | Weekly revenue + paid spend + organic signals (2015–2019) |
| `dt_prophet_holidays.csv` | 87,651 | `model_runs` (JSON reference) | Holiday calendar for 123 countries — used for holiday effect feature |
| `df_curve_reach_freq.csv` | 300 | `model_runs` (JSON reference) | Reach/frequency saturation curves — calibrates Hill function K values |

The data is simulated — not from a real company — and is free to use for educational purposes.

---

## Database schema

### Core tables (Sprint 1–2)

| Table | Written by | Read by | Description |
|-------|-----------|---------|-------------|
| `raw_spend_data` | DB loader | DS, API | Weekly paid spend per channel — 1040 rows (208 weeks x 5 channels). UNIQUE on (week_start, channel). |
| `revenue_data` | DB loader | DS, API | Weekly total revenue — 208 rows. UNIQUE on week_start. |
| `processed_features` | DS pipeline | DS, API | Adstock + Hill saturated values per channel per week. UNIQUE on (week_start, channel). |
| `model_runs` | DS model | API | One row per training run. Stores R², model version, status, and hyperparameters as JSONB. Also holds holiday and curve reference JSON. |
| `channel_coefficients` | DS model | API | ROI estimate, contribution %, OLS coefficient, recommendation, and predicted revenue contribution per channel per run. |
| `budget_scenarios` | API | API, Frontend | Saved optimizer results. Per-channel allocation stored as JSONB. |

### New tables added in Sprint 3

| Table | Written by | Read by | Description |
|-------|-----------|---------|-------------|
| `organic_signals` | DB loader | DS | Competitor sales, newsletter subscribers, Facebook impressions, search clicks, and event flags — one row per week. UNIQUE on week_start. |
| `pipeline_run_log` | Orchestration | Orch | Audit trail for every Prefect or manual pipeline run. Records flow name, start/finish times, status, row counts, model_run_id, and error message. |

### Column changes in Sprint 3

| Table | Change | Reason |
|-------|--------|--------|
| `channel_coefficients` | Added `recommendation VARCHAR(50)` | Stores under-invested / over-invested / optimal |
| `channel_coefficients` | Added `predicted_revenue_contribution NUMERIC(14,2)` | Channel's estimated revenue in USD |
| `channel_coefficients` | Widened `coefficient` to `NUMERIC(18,4)` | OLS values like 561357.77 overflowed `NUMERIC(10,6)` |
| `channel_coefficients` | Widened `roi_estimate` to `NUMERIC(12,4)` | Consistent with coefficient fix |

### Indexes added in Sprint 3

| Index | Column | Purpose |
|-------|--------|---------|
| `idx_model_runs_status` | `model_runs(status)` | Fast lookup of completed runs by the API |
| `idx_scenarios_created` | `budget_scenarios(created_at DESC)` | Most-recent-first ordering |
| `idx_organic_week` | `organic_signals(week_start)` | Join performance with revenue/spend tables |
| `idx_pipeline_log_status` | `pipeline_run_log(status)` | Filter failed/running pipeline runs |

### Constraints added in Sprint 3

| Constraint | Table | Definition |
|-----------|-------|------------|
| `uq_features_week_channel` | `processed_features` | UNIQUE (week_start, channel) — prevents duplicate rows on pipeline re-runs |

---

## API endpoints

Full interactive docs at **http://localhost:8000/docs**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | API status + DB connectivity |
| `GET` | `/results` | Latest completed model run — channel ROI, contribution %, recommendations |
| `GET` | `/model-runs` | Full model training history with R² scores and timestamps |
| `POST` | `/retrain` | Triggers model retraining inside the DS container via its internal API |
| `POST` | `/optimize` | Budget optimizer — returns optimal channel allocation for a given budget |
| `GET` | `/scenarios` | All saved budget scenarios ordered by most recent |
| `POST` | `/scenarios` | Save a named budget scenario |
| `PUT` | `/scenarios/{id}` | Update a saved scenario |
| `DELETE` | `/scenarios/{id}` | Delete a scenario |
| `GET` | `/data-summary` | Date range and total spend per channel |

### How POST /retrain works (wired in Sprint 3)

The retrain endpoint calls `http://ds:5000/run` as a FastAPI `BackgroundTask`. The DS trigger API (`ds/trigger.py`) runs `baseline.py` inside the DS container where all data science packages (sklearn, sqlalchemy, pandas) are installed. Poll `GET /model-runs` to see the new run appear with status `complete`.

### How POST /optimize works

Reads the latest channel ROI coefficients from `channel_coefficients`, then uses `scipy.optimize.minimize` (SLSQP method) to find the allocation maximising:

```
predicted_revenue = sum(roi_per_channel x spend_per_channel)
subject to:
  sum(spend) = total_budget
  total_budget x 0.03 <= spend_per_channel <= total_budget x 0.70
```

Default 3% floor and 70% ceiling are applied automatically. Override per-channel with the `constraints` parameter.

---

## Analytical methodology

### Adstock transformation

Models carryover effect — ads keep influencing purchases after they run.

```
adstock(t) = spend(t) + lambda x adstock(t-1)
```

| Channel | Lambda | Effect duration |
|---------|--------|----------------|
| TV | 0.68 | ~3 weeks |
| OOH | 0.40 | ~1.5 weeks |
| Print | 0.35 | ~1 week |
| Facebook | 0.25 | Fades quickly |
| Search | 0.12 | Almost none — intent-driven |

### Hill function saturation

Models diminishing returns — doubling spend does not double revenue.

```
saturation(x) = x^n / (x^n + K^n)     n=2.0, K = 0.4-0.5 x max(spend)
```

Output scaled 0 to 1. K calibrated per channel using `df_curve_reach_freq.csv`.

### OLS regression (updated in Sprint 3 to include organic controls)

```
revenue ~ tv_sat + ooh_sat + print_sat + facebook_sat + search_sat
        + competitor_sales + newsletter_subs + event_dummy
        + is_q4 + month
```

Adding `competitor_sales` (Pearson r = +0.92 with revenue) as a control variable was the critical Sprint 3 improvement — it separates organic market growth from paid channel effect.

### Model performance (Sprint 3)

| Metric | Value |
|--------|-------|
| R² test set | **0.97** |
| R² training set | 0.89 |
| Naive baseline R² | -0.17 |
| MAE test | ~$91k/week |
| Naive MAE | ~$626k/week |
| Improvement over naive | **85.5%** |

### Channel recommendations

| Label | Condition |
|-------|-----------|
| `under-invested` | ROI share > spend share x 1.2 — increase budget here |
| `over-invested` | ROI share < spend share x 0.8 — reduce spend here |
| `optimal` | ROI share within 20% of spend share |

---

## Frontend dashboard

Four fully-wired pages (built in Sprint 3):

| Page | What it shows |
|------|--------------|
| **Overview** | KPI cards, horizontal ROI bar chart with break-even line, contribution % chart, per-channel recommendation pills |
| **Channels** | Channel selector, saturation response curve (where diminishing returns begin), adstock decay chart (how long each channel's effect lasts) |
| **Budget Optimizer** | Total budget slider, live allocation chart (400ms debounced API calls), predicted revenue display, save/delete scenario table |
| **Model Settings** | Run history table with R² colour-coding, Retrain button, pipeline step explainer |

---

## Orchestration — two Prefect flows

| Flow | Command | Purpose |
|------|---------|---------|
| `mmm-pipeline-test` | `docker exec mmm_orch python pipeline_flow.py --test` | Fast validation — checks files, DB, data quality. No loading or training. |
| `mmm-pipeline-full` | `docker exec mmm_orch python pipeline_flow.py` | Full pipeline — validates, loads, trains, logs to `pipeline_run_log`. |

Every run is logged to `pipeline_run_log`. View runs in the Prefect UI at **http://localhost:4200**.

---

## Development workflow

```bash
# Rebuild one service after code changes
docker compose up --build ds

# Live logs from one service
docker compose logs -f back

# Open a shell inside a container
docker exec -it mmm_ds bash

# Stop everything (data preserved in db_data volume)
docker compose down

# Stop and wipe all data (fresh start)
docker compose down -v
```

---

## Running tests

```bash
# Verify DB connection and row counts
docker exec mmm_db python db_helpers.py

# Run EDA
docker exec mmm_ds python eda.py

# Train the model
docker exec mmm_ds python models/baseline.py

# Fast validation flow (no side effects)
docker exec mmm_orch python pipeline_flow.py --test

# Full pipeline flow
docker exec mmm_orch python pipeline_flow.py

# API health check
curl http://localhost:8000/health

# Optimizer — $100k budget
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"total_budget": 100000}'

# Optimizer — with channel constraints
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"total_budget": 100000, "constraints": {"tv": {"min": 10000}, "print": {"max": 5000}}}'
```

---

## Project roadmap

| Sprint | Weeks | Focus | Status |
|--------|-------|-------|--------|
| 1 | 1–2 | Infrastructure: Docker, DB schema, all 6 services | Complete |
| 2 | 3–4 | Pipeline + Model: transforms, OLS baseline, DB writes | Complete |
| 3 | 5–6 | Final model with organic controls, full dashboard, orchestration | Complete |
| 4 | 7–8 | Demo polish, remaining improvements | In progress |

### Sprint 1 deliverables
- All 6 Docker services running via docker compose up --build
- PostgreSQL schema with 6 tables, constraints, and indexes
- DB helper library (db_helpers.py) with full CRUD functions
- FastAPI backend with all endpoints and Swagger UI
- React frontend skeleton with navigation and API health badge
- Prefect orchestration container with placeholder pipeline flow
- MkDocs documentation site

### Sprint 2 deliverables
- Robyn CSV data loaded into raw_spend_data and revenue_data
- Adstock decay transform per channel (configurable lambda)
- Hill function saturation transform per channel
- OLS regression baseline model with R^2 evaluation
- Model results written to channel_coefficients and model_runs
- All backend endpoints wired to PostgreSQL via crud.py
- Pydantic request and response schemas on all 10 endpoints

### Sprint 3 deliverables
- organic_signals table — competitor sales, newsletter, events loaded
- pipeline_run_log table — full audit trail for every pipeline run
- Model updated with organic control variables — R^2 improved to 0.97
- Channel recommendations (under/over/optimal) computed and written to DB
- processed_features persisted to database after every model run
- Schema widened: coefficient NUMERIC(18,4) to handle large OLS values
- Missing indexes added: model_runs(status), budget_scenarios(created_at)
- POST /retrain wired end-to-end via DS trigger API (ds/trigger.py)
- Optimizer default bounds: 3% floor and 70% ceiling per channel
- Overview page: ROI bar chart, contribution chart, recommendation pills
- Channel Deep Dive page: saturation curve and adstock decay chart
- Budget Optimizer page: live optimizer, scenario save/delete
- Model Settings page: run history table, retrain button
- Two Prefect flows: mmm-pipeline-test and mmm-pipeline-full
- All 5 MkDocs service documentation pages filled in

### Remaining work (Sprint 4)
- model_predictions table — persist weekly actual vs predicted revenue
- GET /predictions endpoint — expose predictions for time-series chart
- Actual vs predicted revenue line chart on Overview page
- Scenario side-by-side comparison layout in Budget Optimizer
- Auto-polling after Retrain button click
- Export results to CSV
- Prefect scheduled deployment (weekly cron)
- Bayesian model upgrade using PyMC (stretch goal)

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_DB | mmm_db | Database name |
| POSTGRES_USER | mmm_user | Database user |
| POSTGRES_PASSWORD | mmm_pass | Database password |
| REACT_APP_API_URL | http://localhost:8000 | Backend URL seen by the browser |
| PREFECT_API_URL | http://127.0.0.1:4200/api | Prefect server URL (in-container) |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit message format, PR process, and folder ownership rules.

---

## References

- [Meta Robyn — Open Source MMM](https://github.com/facebookexperimental/Robyn)
- [Prefect 3 Documentation](https://docs.prefect.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Recharts Documentation](https://recharts.org/)
- [scikit-learn LinearRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html)
