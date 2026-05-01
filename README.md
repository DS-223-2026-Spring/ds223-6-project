# MMM Platform

> **Marketing Mix Modeling Platform** — a containerized, full-stack analytics application that attributes revenue to advertising channels and optimizes marketing budget allocation.

Built for the Marketing Analytics class group project. Implements the Marketing Mix Modeling (MMM) methodology used by companies like P&G, Unilever, and Google — powered by Meta's open-source Robyn demo dataset.

---

## What it does

Given 4 years of weekly ad spend across 5 channels (TV, OOH, Print, Facebook, Search) and weekly revenue, the platform:

1. **Transforms** raw spend data using adstock decay (carryover effects) and Hill function saturation (diminishing returns)
2. **Trains** an OLS regression model to attribute revenue to each channel
3. **Calculates** the ROI (revenue per $1 spent) for each channel
4. **Optimizes** budget allocation — given any total budget, finds the spend split that maximizes predicted revenue
5. **Presents** everything through an interactive web dashboard

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
      │
      ▼
  back service        ← FastAPI — REST API serving results and running the optimizer
      │
      ▼
  front service       ← React — dashboard with charts, KPI cards, and budget sliders
      │
  orch service        ← Prefect — orchestrates and schedules the pipeline
```

All six services run in Docker containers on a shared network. They communicate with each other using service names (e.g. `back` reaches `db` at `db:5432`).

---

## Services and ports

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| Database | `mmm_db` | 5432 | PostgreSQL — all data storage |
| Data Science | `mmm_ds` | — | Pipeline scripts, EDA, model training |
| Backend API | `mmm_back` | **8000** | FastAPI REST API + Swagger UI |
| Frontend | `mmm_front` | **3000** | React dashboard |
| Orchestration | `mmm_orch` | **4200** | Prefect workflow UI |

---

## Team roles

| Branch | Role | Service owned |
|--------|------|---------------|
| `db` | DB Engineer | `db/` — schema, helpers, data loader |
| `ds` | Data Scientist | `ds/` — EDA, transforms, model |
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

After the containers are running, load the CSV data and train the model:

```bash
# Load the 3 Robyn CSV files into PostgreSQL
docker exec mmm_db python load_data.py

# Run exploratory data analysis
docker exec mmm_ds python eda.py

# Train the MMM model and write results to the database
docker exec mmm_ds python models/baseline.py
```

After `baseline.py` completes, the dashboard at `http://localhost:3000` will show real channel ROI data.

---

## Data sources

This project uses three open-source datasets from Meta's [Robyn MMM project](https://github.com/facebookexperimental/Robyn):

| File | Rows | Description |
|------|------|-------------|
| `dt_simulated_weekly.csv` | 208 | Weekly revenue + spend across TV, OOH, Print, Facebook, Search (2015–2019) |
| `dt_prophet_holidays.csv` | 87,651 | Holiday calendar for 123 countries (used to build holiday effect feature) |
| `df_curve_reach_freq.csv` | 300 | Reach/frequency saturation curves (used to calibrate Hill function parameters) |

The data is simulated — not from a real company — and is free to use for educational purposes.

---

## Database schema

| Table | Written by | Read by | Description |
|-------|-----------|---------|-------------|
| `raw_spend_data` | DB loader | DS, API | Weekly spend per channel (1040 rows: 208 weeks × 5 channels) |
| `revenue_data` | DB loader | DS, API | Weekly total revenue (208 rows) |
| `processed_features` | DS pipeline | DS, API | Adstock + saturation transformed values |
| `model_runs` | DS model | API | One row per training run with R² and hyperparameters |
| `channel_coefficients` | DS model | API | ROI estimate and contribution % per channel per run |
| `budget_scenarios` | API | API, Frontend | Saved optimizer results with per-channel allocation |

---

## API endpoints

Full interactive docs at **http://localhost:8000/docs**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | API status + DB connectivity check |
| `GET` | `/results` | Latest model run — channel ROI and contribution % |
| `GET` | `/model-runs` | Full model training history |
| `POST` | `/retrain` | Trigger model retrain (Sprint 4) |
| `POST` | `/optimize` | Budget optimizer — returns optimal channel split |
| `GET` | `/scenarios` | All saved budget scenarios |
| `POST` | `/scenarios` | Save a new optimizer scenario |
| `PUT` | `/scenarios/{id}` | Update a saved scenario |
| `DELETE` | `/scenarios/{id}` | Delete a scenario |
| `GET` | `/data-summary` | Date range and total spend per channel |

---

## Analytical methodology

### Adstock transformation
Models the carryover effect — a TV ad seen this week still influences purchases next week.

```
adstock(t) = spend(t) + λ × adstock(t-1)
```

Decay rates used: TV=0.68, OOH=0.40, Print=0.35, Facebook=0.25, Search=0.12

### Hill function saturation
Models diminishing returns — doubling spend does not double revenue.

```
saturation(x) = xⁿ / (xⁿ + Kⁿ)
```

Output is scaled 0→1. Parameters calibrated from `df_curve_reach_freq.csv`.

### OLS regression
Revenue is regressed on all transformed channel variables plus seasonality controls:

```
revenue ~ tv_sat + ooh_sat + print_sat + facebook_sat + search_sat + is_q4 + month
```

Each coefficient represents the channel's marginal revenue contribution per unit of saturated spend. ROI (revenue per $1 spent) is derived from the coefficients scaled back to dollar terms.

---

## Development workflow

```bash
# Work only in your own service folder and branch
git checkout -b your-branch   # e.g. git checkout -b ds

# Rebuild just your service after code changes (no full restart needed)
docker compose up --build ds

# Live logs from one service
docker compose logs -f back

# Open a shell inside a container
docker exec -it mmm_ds bash

# Stop everything (data is preserved in db_data volume)
docker compose down

# Stop and delete all data (fresh start)
docker compose down -v
```

---

## Running tests

```bash
# Verify database connection and table row counts
docker exec mmm_db python db_helpers.py

# Run EDA (requires data loaded first)
docker exec mmm_ds python eda.py

# Run the model pipeline
docker exec mmm_ds python models/baseline.py

# Test the API health endpoint
curl http://localhost:8000/health

# Test the optimizer with a $100k budget
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"total_budget": 100000}'

# Run the Prefect pipeline flow
docker exec mmm_orch python pipeline_flow.py
```

---

## Project roadmap

| Sprint | Weeks | Focus | Status |
|--------|-------|-------|--------|
| 1 | 1–2 | Infrastructure: Docker, DB schema, base services | ✅ Complete |
| 2 | 3–4 | Pipeline + Model: transforms, OLS, DB writes | ✅ Complete |
| 3 | 5–6 | Full model, real charts, optimizer UI, orchestration | ✅ Complete |
| 4 | 7–8 | Demo polish, Bayesian upgrade (stretch), scheduling | 🔲 Planned |

### Sprint 3 deliverables
- ✅ Organic signals table — competitor sales, newsletter, events loaded and used in model
- ✅ Processed features written to database after every model run
- ✅ Channel recommendations (under/over/optimal) computed and displayed
- ✅ Pydantic response schemas on all 10 endpoints — typed Swagger docs
- ✅ POST /retrain wired to background task running baseline.py
- ✅ React dashboard — full ROI bar chart, contribution chart, recommendations
- ✅ Channel Deep Dive — saturation curve + adstock decay charts
- ✅ Budget Optimizer — live optimizer, debounced API calls, scenario save/delete
- ✅ Model Settings — run history table, retrain button, pipeline info
- ✅ Two Prefect flows — test flow (fast) and full pipeline flow
- ✅ Prefect pipeline_run_log — every run traceable in the database
- ✅ All service documentation pages filled in

### Remaining work (Sprint 4)
- Bayesian model upgrade using PyMC (stretch goal)
- Prefect scheduled deployment (weekly cron)
- Scenario comparison side-by-side view
- Export results to CSV

---

## Environment variables

All variables live in `.env` (copied from `.env.example`). Never commit `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `mmm_db` | Database name |
| `POSTGRES_USER` | `mmm_user` | Database user |
| `POSTGRES_PASSWORD` | `mmm_pass` | Database password |
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend URL for the browser |
| `PREFECT_API_URL` | `http://127.0.0.1:4200/api` | Prefect server URL |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit message format, PR process, and folder ownership rules.

---

## References

- [Meta Robyn — Open Source MMM](https://github.com/facebookexperimental/Robyn)
- [Prefect 3 Documentation](https://docs.prefect.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Recharts Documentation](https://recharts.org/)
