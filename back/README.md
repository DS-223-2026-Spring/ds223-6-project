# Backend Service — FastAPI

REST API that serves MMM model results and runs the budget optimizer.
Swagger UI available at http://localhost:8000/docs

## Folder structure

```
back/
├── Dockerfile
├── requirements.txt
├── main.py        # FastAPI app — all endpoint definitions
├── database.py    # SQLAlchemy engine, session factory, get_db() dependency
└── crud.py        # All SQL queries — endpoints never write raw SQL
```

## Endpoints

All 10 endpoints are live. Complete interactive documentation at **http://localhost:8000/docs**

Quick reference — endpoints mapped to product functionality:

| Endpoint | Product feature |
|----------|----------------|
| GET /health | System status — confirms API + DB are running |
| GET /results | Channel ROI dashboard — feeds the Overview and Channels pages |
| GET /model-runs | Model history — feeds the Model Settings run history table |
| POST /retrain | Train model button — triggers full MMM pipeline |
| POST /optimize | Budget optimizer — called live as user moves sliders |
| GET /scenarios | Scenario list — loads saved scenarios in Optimizer page |
| POST /scenarios | Save scenario — stores a named allocation for comparison |
| PUT /scenarios/{id} | Edit scenario — rename or adjust a saved scenario |
| DELETE /scenarios/{id} | Remove scenario — deletes from comparison table |
| GET /data-summary | Dashboard header — date range and total spend per channel |

---

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + DB connection status |
| GET | `/results` | Latest model run with channel ROI estimates |
| GET | `/model-runs` | Full model run history |
| POST | `/retrain` | Trigger model retrain (placeholder until Sprint 4) |
| POST | `/optimize` | Budget optimizer — returns optimal channel split |
| GET | `/scenarios` | All saved budget scenarios |
| POST | `/scenarios` | Save a new scenario |
| PUT | `/scenarios/{id}` | Update a scenario |
| DELETE | `/scenarios/{id}` | Delete a scenario |
| GET | `/data-summary` | Date range and total spend per channel |

## How to run

```bash
docker-compose up back
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
```

## How the DB connection works

Every endpoint declares `db: Session = Depends(get_db)`.
FastAPI automatically calls `get_db()` from `database.py`, which opens a
session from the connection pool, passes it to the endpoint, and closes it
when the request finishes — even if an exception occurs.

Endpoints never write SQL directly. All queries live in `crud.py`.

## Pending dependencies

- `/results` returns empty until the DS container trains and writes a model run.
- `/optimize` returns an equal split fallback until model coefficients exist in DB.
- `/retrain` is a placeholder — Sprint 4 will wire it to trigger the DS pipeline.
