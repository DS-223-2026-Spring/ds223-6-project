"""
main.py – MMM Platform Backend API  (Sprint 3 — complete)
Swagger UI: http://localhost:8000/docs

All endpoints use:
  - Pydantic request schemas  (validated input)
  - Pydantic response schemas (typed Swagger output)
  - Depends(get_db)           (one session per request, auto-closed)
  - crud.py functions         (no raw SQL in this file)
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import scipy.optimize as opt
import numpy as np

from pydantic import BaseModel

class BayesianRetrainRequest(BaseModel):
    draws: int = 500

from database import get_db, check_connection
import crud
from schemas import (
    HealthResponse,
    ModelResult, ModelRunsResponse,
    OptimizeRequest, OptimizeResponse,
    ScenarioRequest, ScenarioUpdateRequest,
    ScenarioRecord, ScenariosResponse, ScenarioSaveResponse,
    DataSummaryResponse,
    RetainResponse,
    PredictionsResponse, PredictionPoint,
    OrganicSignalsResponse,
    PipelineRunsResponse,
    WeeklyAllChannelsResponse,
    ModelTypeResponse,
)

app = FastAPI(
    title="MMM Platform API",
    description=(
        "Marketing Mix Modeling platform. Attributes weekly revenue to advertising "
        "channels (TV, OOH, Print, Facebook, Search) and optimises budget allocation.\n\n"
        "**Workflow:** load data → train model (`/retrain`) → read results (`/results`) "
        "→ optimise budget (`/optimize`) → save scenarios (`/scenarios`)."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHANNELS = ["tv", "ooh", "print", "facebook", "search"]


# ── Health ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="API and database health check",
)
def health():
    """
    Returns the API status and whether the PostgreSQL database is reachable.

    - **status**: `ok` if everything is healthy, `degraded` if DB is unreachable
    - **database**: `connected` or `unreachable`
    """
    db_ok = check_connection()
    return HealthResponse(
        status   = "ok" if db_ok else "degraded",
        service  = "mmm-back",
        database = "connected" if db_ok else "unreachable",
    )


# ── Model results ─────────────────────────────────────────────────────────────

@app.get(
    "/results",
    response_model=ModelResult,
    tags=["Model"],
    summary="Latest model run — channel ROI and revenue attribution",
)
def get_results(db: Session = Depends(get_db)):
    """
    Returns the most recent **completed** model run with per-channel results.

    Each channel entry contains:
    - **roi_estimate**: revenue generated per $1 spent (higher = better channel)
    - **contribution_pct**: share of total attributed revenue (%)
    - **recommendation**: `under-invested` | `over-invested` | `optimal`

    Returns an empty `channels` list if no model has been trained yet.
    Train the model first by calling `POST /retrain`.
    """
    return crud.get_latest_results(db)


@app.get(
    "/model-runs",
    response_model=ModelRunsResponse,
    tags=["Model"],
    summary="Full model training history",
)
def get_model_runs(
    limit:  int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Returns model runs ordered by most recent first.

    - `limit`: number of runs to return (default 50)
    - `offset`: pagination offset (default 0)

    Each run includes the **R² score**, model version, and status.
    Use this to compare model iterations over time.
    """
    return {"runs": crud.get_model_runs(db, limit=limit, offset=offset)}


@app.post(
    "/retrain",
    response_model=RetainResponse,
    tags=["Model"],
    summary="Trigger model retraining",
)
def trigger_retrain(background_tasks: BackgroundTasks):
    """
    Triggers the MMM model pipeline via the DS container's internal trigger API.

    **Pipeline steps:**
    1. Read raw_spend_data, revenue_data, organic_signals from PostgreSQL
    2. Apply adstock decay and Hill function saturation per channel
    3. Train OLS regression with organic control variables
    4. Write results to processed_features, model_runs, channel_coefficients

    The retrain runs synchronously inside the DS container (~20-40 seconds).
    The dashboard auto-refreshes after completion.

    **Expected duration:** 20–40 seconds depending on machine.
    """
    import urllib.request
    import urllib.error
    import json as _json

    def run_pipeline():
        try:
            # Call the trigger API running inside the ds container
            # The ds service is reachable as 'ds' on the shared Docker network
            req = urllib.request.Request(
                "http://ds:5000/run",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=b"{}",
            )
            with urllib.request.urlopen(req, timeout=360) as resp:
                result = _json.loads(resp.read().decode())
                if result.get("status") == "success":
                    print(f"[retrain] Pipeline completed successfully")
                else:
                    print(f"[retrain] Pipeline failed: {result.get('error','unknown error')}")
        except urllib.error.URLError as e:
            print(f"[retrain] Could not reach DS trigger API: {e}")
            print("[retrain] Fallback: run manually with: docker exec mmm_ds python models/baseline.py")
        except Exception as e:
            print(f"[retrain] Unexpected error: {e}")

    background_tasks.add_task(run_pipeline)
    return RetainResponse(
        message="Retrain started. The model runs inside the DS container (~30s). Refresh Model Settings in 40 seconds.",
        status="started",
    )


# ── Budget optimizer ──────────────────────────────────────────────────────────

@app.post(
    "/optimize",
    response_model=OptimizeResponse,
    tags=["Optimizer"],
    summary="Optimise budget allocation across channels",
)
def run_optimizer(req: OptimizeRequest, db: Session = Depends(get_db)):
    """
    Reads the latest channel ROI coefficients from the database and uses
    **scipy SLSQP constrained optimisation** to find the spend allocation
    that maximises predicted revenue subject to the total budget.

    **Request body:**
    - `total_budget`: total spend in USD (required, must be > 0)
    - `constraints`: optional per-channel min/max bounds in USD.
      Example: `{"tv": {"min": 5000, "max": 40000}, "search": {"min": 10000}}`

    **Returns:**
    - `allocation`: optimal spend per channel in USD
    - `predicted_revenue`: estimated weekly revenue for this allocation

    Falls back to an equal split if no trained model exists yet.
    """
    results  = crud.get_latest_results(db)
    channels = results.get("channels", [])

    if not channels:
        equal = round(req.total_budget / len(CHANNELS), 2)
        return OptimizeResponse(
            total_budget      = req.total_budget,
            allocation        = {ch: equal for ch in CHANNELS},
            predicted_revenue = None,
            note              = "No model results found — returning equal split. Train the model first.",
        )

    roi_map    = {c["channel"]: c["roi_estimate"] or 0.0 for c in channels}
    roi_vector = np.array([roi_map.get(ch, 0.0) for ch in CHANNELS])

    def neg_revenue(spend_array):
        return -np.dot(roi_vector, spend_array)

    opt_constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - req.total_budget}]

    # Default minimum floor: every channel gets at least 3% of total budget.
    # This reflects real-world constraints — you can't fully abandon any channel.
    # Users can override per-channel bounds via the constraints parameter.
    default_min = req.total_budget * 0.03
    default_max = req.total_budget * 0.70   # no single channel gets more than 70%

    bounds = []
    for ch in CHANNELS:
        lo = default_min
        hi = default_max
        if req.constraints and ch in req.constraints:
            lo = float(req.constraints[ch].get("min", default_min))
            hi = float(req.constraints[ch].get("max", default_max))
        bounds.append((lo, hi))

    x0     = np.array([req.total_budget / len(CHANNELS)] * len(CHANNELS))
    result = opt.minimize(
        neg_revenue, x0, method="SLSQP",
        bounds=bounds, constraints=opt_constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    allocation = {ch: round(float(v), 2) for ch, v in zip(CHANNELS, result.x)}
    # Ensure allocation sums exactly to total_budget (fix floating point drift)
    diff = round(req.total_budget - sum(allocation.values()), 2)
    if diff != 0:
        top_ch = max(allocation, key=allocation.get)
        allocation[top_ch] = round(allocation[top_ch] + diff, 2)

    return OptimizeResponse(
        total_budget      = req.total_budget,
        allocation        = allocation,
        predicted_revenue = round(float(-result.fun), 2),
    )


# ── Scenarios ─────────────────────────────────────────────────────────────────

@app.get(
    "/scenarios",
    response_model=ScenariosResponse,
    tags=["Scenarios"],
    summary="List all saved budget scenarios",
)
def get_scenarios(
    limit:  int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Returns saved budget scenarios ordered by most recently created first.

    - `limit`: number of scenarios to return (default 50, max 200)
    - `offset`: pagination offset (default 0)

    Use the **scenario comparison** view in the dashboard to compare up to
    three scenarios side by side.
    """
    limit = min(limit, 200)
    return {"scenarios": crud.get_all_scenarios(db, limit=limit, offset=offset)}


@app.post(
    "/scenarios",
    response_model=ScenarioSaveResponse,
    tags=["Scenarios"],
    summary="Save a budget scenario",
)
def save_scenario(req: ScenarioRequest, db: Session = Depends(get_db)):
    """
    Saves a budget allocation scenario to the database for future comparison.

    Typically called after `POST /optimize` to persist the recommended allocation,
    or manually to save a custom allocation for comparison.

    - `scenario_name`: human-readable label (e.g. "Q4 aggressive search")
    - `allocation`: dict of channel → spend amount in USD
    - `predicted_revenue`: optional — supply the value from `/optimize`
    """
    saved = crud.save_scenario(
        db=db,
        scenario_name     = req.scenario_name,
        total_budget      = req.total_budget,
        allocation        = req.allocation,
        predicted_revenue = req.predicted_revenue,
        model_run_id      = req.model_run_id,
    )
    return {"message": "Scenario saved", "scenario": saved}


@app.put(
    "/scenarios/{scenario_id}",
    response_model=ScenarioSaveResponse,
    tags=["Scenarios"],
    summary="Update a saved scenario",
)
def update_scenario(
    scenario_id: int,
    req: ScenarioUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Updates one or more fields of an existing scenario by its ID.
    Only the fields included in the request body are changed.
    Returns 404 if the scenario ID does not exist.
    """
    updated = crud.update_scenario(db, scenario_id, req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"message": "Scenario updated", "scenario": updated}


@app.delete(
    "/scenarios/{scenario_id}",
    tags=["Scenarios"],
    summary="Delete a saved scenario",
)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """
    Permanently deletes a scenario by its ID.
    Returns 404 if the scenario ID does not exist.
    """
    deleted = crud.delete_scenario(db, scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"message": f"Scenario {scenario_id} deleted"}


# ── Data summary ──────────────────────────────────────────────────────────────

@app.get(
    "/data-summary",
    response_model=DataSummaryResponse,
    tags=["Data"],
    summary="Raw data overview — date range and spend totals",
)
def get_data_summary(db: Session = Depends(get_db)):
    """
    Returns the date range of loaded data and total spend per channel.

    Useful for the dashboard header and for confirming data was loaded correctly.
    If all spend values are 0, run `load_data.py` in the DB container first.
    """
    return crud.get_spend_summary(db)


# ── Predictions (actual vs predicted) ────────────────────────────────────────

@app.get(
    "/predictions",
    response_model=PredictionsResponse,
    tags=["Analytics"],
    summary="Weekly actual vs predicted revenue for the latest model run",
)
def get_predictions(
    model_run_id: int = None,
    db: Session = Depends(get_db),
):
    """
    Returns weekly actual vs predicted revenue for visualisation.

    Use this to render the **actual vs predicted time-series chart** in the
    Overview dashboard. Each point contains the week, actual revenue, model
    prediction, and residual (actual − predicted).

    - `model_run_id` (optional): specify a run ID to compare model versions.
      Defaults to the latest completed run.

    Returns an empty `points` list if the model has not been trained yet or
    if predictions were not persisted (run `baseline.py` to populate).
    """
    points = crud.get_predictions(db, model_run_id)
    # Resolve the actual run_id used (crud resolves None to latest)
    if model_run_id is None and points:
        # crude resolution: not needed for display, but keep consistent
        pass
    return PredictionsResponse(
        model_run_id=model_run_id,
        points=points,
    )


# ── Organic signals ───────────────────────────────────────────────────────────

@app.get(
    "/organic-signals",
    response_model=OrganicSignalsResponse,
    tags=["Analytics"],
    summary="Weekly organic and external signals",
)
def get_organic_signals(db: Session = Depends(get_db)):
    """
    Returns weekly organic signal data used as model control variables:

    - **competitor_sales**: competitor revenue (strong confound, r=+0.92 with revenue)
    - **newsletter_subs**: newsletter subscriber count (organic demand driver)
    - **facebook_impressions**: total Facebook impression volume
    - **search_clicks**: total paid search click volume
    - **event_flag**: `na` | `event1` | `event2` — special event weeks

    Use this to render the **organic signals chart** alongside paid channel data,
    helping users understand what drives revenue beyond advertising spend.
    """
    return OrganicSignalsResponse(points=crud.get_organic_signals(db))


# ── Pipeline run log ──────────────────────────────────────────────────────────

@app.get(
    "/pipeline-runs",
    response_model=PipelineRunsResponse,
    tags=["Orchestration"],
    summary="Prefect pipeline run history",
)
def get_pipeline_runs(db: Session = Depends(get_db)):
    """
    Returns the Prefect pipeline run log — every automated or manual run
    of `mmm-pipeline-full` or `mmm-pipeline-test`.

    Each entry includes:
    - **status**: `running` | `success` | `failed`
    - **spend_rows** / **revenue_rows**: data loaded in that run
    - **model_run_id**: links to the model trained in that run
    - **error_msg**: populated if the run failed

    Use this in the Model Settings page to show the full operational history,
    not just model training runs.
    """
    return PipelineRunsResponse(runs=crud.get_pipeline_runs(db))


# ── Weekly channel data ───────────────────────────────────────────────────────

@app.get(
    "/channel-weekly",
    response_model=WeeklyAllChannelsResponse,
    tags=["Analytics"],
    summary="Weekly spend, adstock, saturation and contribution per channel",
)
def get_channel_weekly(db: Session = Depends(get_db)):
    """
    Returns weekly time-series data for all channels, including:

    - **spend**: raw weekly spend in USD
    - **adstock**: spend after carryover decay transform
    - **saturated**: adstock after Hill function saturation (0-1 scale)
    - **contribution**: estimated revenue contribution (saturated × coefficient)

    Used by the **Channel Deep Dive** page to render real data charts instead
    of simulated curves. Requires the model to have been trained first.
    """
    return crud.get_weekly_channel_data(db)


# ── Model type selector ───────────────────────────────────────────────────────

@app.get(
    "/model-types",
    response_model=ModelTypeResponse,
    tags=["Model"],
    summary="Available model types and current active version",
)
def get_model_types(db: Session = Depends(get_db)):
    """
    Returns available model types and the currently active version.

    - **ols**: Fast OLS regression (seconds). Good for iteration.
    - **bayesian**: PyMC Bayesian model (2-5 minutes). Produces credible intervals.

    The current model is determined by the latest completed run in `model_runs`.
    Use `POST /retrain-bayesian` to train the Bayesian model.
    """
    latest = db.execute(text("""
        SELECT model_version FROM model_runs
        WHERE status = 'complete'
        ORDER BY run_at DESC LIMIT 1
    """)).fetchone()

    current = latest.model_version if latest else None
    model_type = "bayesian" if current and "bayesian" in current else "ols"

    return ModelTypeResponse(
        available=["ols", "bayesian"],
        current=model_type,
        note="Use POST /retrain for OLS (fast). Use POST /retrain-bayesian for Bayesian (2-5 min, produces credible intervals).",
    )


@app.post(
    "/retrain-bayesian",
    response_model=RetainResponse,
    tags=["Model"],
    summary="Trigger Bayesian model retraining (PyMC)",
)
def trigger_retrain_bayesian(payload: BayesianRetrainRequest, background_tasks: BackgroundTasks):
    """
    Triggers the Bayesian MMM model (PyMC) inside the DS container.

    **Differences from OLS (`POST /retrain`):**
    - Takes 2–5 minutes instead of ~30 seconds
    - Produces 90% credible intervals for each channel's ROI
    - `roi_lower_90` and `roi_upper_90` fields are populated in results
    - Model version will be `v3.0-bayesian`

    The retrain runs asynchronously. Poll `GET /model-runs` to check completion.
    """
    import urllib.request
    import urllib.error
    import json as _json

    print("🚀 BAYESIAN DRAW REQUEST:", payload.draws)

    def run_bayesian():
        try:
            payload_json = _json.dumps({"draws": payload.draws}).encode()

            req = urllib.request.Request(
                "http://ds:5000/run-bayesian",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=payload_json,
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                result = _json.loads(resp.read().decode())
                status = result.get("status", "unknown")
                print(f"[retrain-bayesian] {status}")
                if result.get("error"):
                    print(f"[retrain-bayesian] Error: {result['error']}")
        except Exception as e:
            print(f"[retrain-bayesian] Failed: {e}")
            print("[retrain-bayesian] Fallback: docker exec mmm_ds python models/bayesian.py")

    background_tasks.add_task(run_bayesian)
    return RetainResponse(
        message=f"Bayesian retrain started with {payload.draws} draws. Poll GET /model-runs for completion.",
        status="started",
    )
