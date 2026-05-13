# DS Service

Python 3.11 data science container — EDA, feature engineering, and MMM modeling.

## Files

| File | Purpose |
|------|---------|
| `db_client.py` | SQLAlchemy DB connector — read/write DataFrames |
| `eda.py` | Exploratory data analysis — stats, correlations, quality checks |
| `models/baseline.py` | Full OLS MMM pipeline — adstock, saturation, OLS regression, DB write |
| `models/bayesian.py` | Bayesian MMM using PyMC — posterior distributions and credible intervals |
| `trigger.py` | Lightweight FastAPI HTTP trigger — exposes `/run` and `/run-bayesian` for the backend |

## How to run

```bash
# Verify DB connection
docker exec mmm_ds python db_client.py

# Run EDA (data must be loaded first)
docker exec mmm_ds python eda.py

# Train the OLS model
docker exec mmm_ds python models/baseline.py

# Train the Bayesian model (2–5 minutes)
docker exec mmm_ds python models/bayesian.py

# Start the DS trigger API (started automatically by docker-compose)
uvicorn trigger:app --host 0.0.0.0 --port 5000
```

## Trigger API

`trigger.py` runs inside the `ds` container and exposes two endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DS trigger service health check |
| POST | `/run` | Triggers `models/baseline.py` (OLS), returns stdout/stderr |
| POST | `/run-bayesian` | Triggers `models/bayesian.py` with configurable `draws`, returns stdout/stderr |

The `back` container calls these endpoints instead of running subprocesses directly.

## OLS modeling pipeline
raw_spend_data + revenue_data + organic_signals
│
▼
apply_adstock(decay λ per channel)
│
▼
apply_hill(saturation K, n=2.0)
│
▼
build_features() — joins organic controls + seasonality
│
▼
OLS regression (80/20 time-series split)
│
├── write processed_features → DB
├── write model_runs → DB
└── write channel_coefficients → DB

## Bayesian modeling pipeline

Extends the OLS baseline with a full PyMC specification. The key advantage is
posterior distributions per channel ROI, enabling credible intervals
(e.g. "$18.32 ± $4.10 at 90% CI") rather than single point estimates.
Same features as OLS baseline
│
▼
PyMC model (Normal likelihood, HalfNormal priors on channel betas)
│
▼
NUTS sampler (default 500 draws)
│
├── write model_runs (version: v3.0-bayesian) → DB
└── write channel_coefficients with roi_lower_90, roi_upper_90 → DB

## Adstock decay rates (λ)

| Channel | λ | Meaning |
|---------|---|---------| 
| TV | 0.68 | Effect lasts ~3 weeks |
| OOH | 0.40 | Effect lasts ~1.5 weeks |
| Print | 0.35 | Effect lasts ~1 week |
| Facebook | 0.25 | Effect fades quickly |
| Search | 0.12 | Almost no carryover (intent-driven) |

## Features used in the model

| Feature | Type | Description |
|---------|------|-------------|
| `{ch}_saturated` | Predictor | Hill-transformed adstock per channel |
| `competitor_sales` | Control | Strong confound (r=+0.92 with revenue) |
| `newsletter_subs` | Control | Organic demand signal |
| `event_dummy` | Control | Binary flag for event1/event2 |
| `is_q4` | Control | Strong Q4 seasonality (2× avg revenue) |
| `month` | Control | Monthly seasonality |

## Target variable

`total_revenue` (weekly, USD) — from `revenue_data` table.

## Expected model performance

- OLS R² test set: > 0.85 with organic controls included
- Bayesian R²: comparable to OLS; key benefit is uncertainty quantification
- Naive baseline R²: ~0.20 (predict mean revenue)
- Key improvement driver: including `competitor_sales_B` as a control variable