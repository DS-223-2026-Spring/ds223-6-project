# Backend Service

FastAPI REST API — serves model results and runs the budget optimizer.

Swagger UI: **http://localhost:8000/docs**

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + DB connectivity status |
| GET | `/results` | Latest model run — channel ROI, contribution %, recommendations |
| GET | `/model-runs` | Full model training history with R² scores |
| POST | `/retrain` | Trigger OLS model retraining (runs as background task) |
| POST | `/retrain-bayesian` | Trigger Bayesian model retraining with configurable draws |
| POST | `/optimize` | Budget optimizer — returns optimal channel split for given budget |
| GET | `/scenarios` | All saved budget scenarios |
| POST | `/scenarios` | Save a new scenario |
| PUT | `/scenarios/{id}` | Update a scenario |
| DELETE | `/scenarios/{id}` | Delete a scenario |
| GET | `/data-summary` | Date range and total spend per channel |
| GET | `/predictions` | Actual vs predicted revenue (optionally filtered by model run) |
| GET | `/organic-signals` | Weekly organic signal data (competitor sales, newsletter, events) |
| GET | `/pipeline-runs` | Prefect/manual pipeline run audit log |
| GET | `/channel-weekly` | Weekly spend per channel (all channels) |
| GET | `/model-types` | Available model types (OLS, Bayesian) and their status |

```text
## File structure
back/  
├── main.py      — FastAPI app, all endpoint definitions  
├── crud.py      — All SQL queries (no SQL in main.py)  
├── database.py  — Lazy SQLAlchemy engine, get_db() dependency  
├── schemas.py   — Pydantic request + response models  
└── requirements.txt  
```

## How DB connection works

```python
# Every endpoint declares:
def my_endpoint(db: Session = Depends(get_db)):
    ...
```

FastAPI calls `get_db()` from `database.py`, opens a session from the pool,
passes it to the endpoint, and closes it when the request finishes.

## How the optimizer works

`POST /optimize` reads the latest channel ROI coefficients from
`channel_coefficients` and runs `scipy.optimize.minimize` with the
SLSQP method to find the spend allocation maximising:
predicted_revenue = Σ (roi_per_channel × spend_per_channel)
subject to: Σ spend = total_budget
0 ≤ spend_per_channel ≤ total_budget

## Bayesian retraining

`POST /retrain-bayesian` accepts an optional `draws` parameter (default 500)
and triggers `bayesian.py` via the DS trigger service. Bayesian sampling
takes 2–5 minutes. Results include 90% credible intervals per channel
(`roi_lower_90`, `roi_upper_90`) stored alongside the point estimate.

## How to run locally

```bash
docker-compose up back
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
```

## How retrain works (Sprint 4)

`POST /retrain` and `POST /retrain-bayesian` both communicate with the DS
trigger service (`http://ds:5000`) via HTTP rather than a direct subprocess.
The `back` container no longer needs the `ds/` folder mounted — the trigger
API handles subprocess execution inside the `ds` container.


## API Reference

### main.py
::: back.main

### database.py
::: back.database

### schemas.py
::: back.schemas

### crud.py
::: back.crud