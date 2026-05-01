# Backend Service

FastAPI REST API — serves model results and runs the budget optimizer.

Swagger UI: **http://localhost:8000/docs**

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + DB connectivity status |
| GET | `/results` | Latest model run — channel ROI, contribution %, recommendations |
| GET | `/model-runs` | Full model training history with R² scores |
| POST | `/retrain` | Trigger model retraining (runs as background task) |
| POST | `/optimize` | Budget optimizer — returns optimal channel split for given budget |
| GET | `/scenarios` | All saved budget scenarios |
| POST | `/scenarios` | Save a new scenario |
| PUT | `/scenarios/{id}` | Update a scenario |
| DELETE | `/scenarios/{id}` | Delete a scenario |
| GET | `/data-summary` | Date range and total spend per channel |

## File structure

```
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

```
predicted_revenue = Σ (roi_per_channel × spend_per_channel)
subject to: Σ spend = total_budget
            0 ≤ spend_per_channel ≤ total_budget
```

## How to run locally

```bash
docker-compose up back
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
```

## Pending dependencies

- `POST /retrain` triggers a background subprocess. In Docker, it requires
  the `ds/` folder to be mounted into the `back` container, or triggering
  via the Prefect orchestration layer instead.
