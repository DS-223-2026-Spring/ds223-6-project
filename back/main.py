"""
main.py – MMM Platform Backend API
All endpoints now read from / write to PostgreSQL via crud.py.
Swagger UI: http://localhost:8000/docs
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import scipy.optimize as opt
import numpy as np

from database import get_db, check_connection
import crud

app = FastAPI(
    title="MMM Platform API",
    description="Marketing Mix Modeling – channel ROI and budget optimizer",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHANNELS = ["search", "facebook", "tv", "ooh", "print"]


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)):
    """Returns API status and confirms the database is reachable."""
    db_ok = check_connection()
    return {
        "status":   "ok" if db_ok else "degraded",
        "service":  "mmm-back",
        "database": "connected" if db_ok else "unreachable",
    }


# ── Model results ─────────────────────────────────────────────────────────────

@app.get("/results", tags=["Model"])
def get_results(db: Session = Depends(get_db)):
    """
    Returns the latest completed model run with channel ROI estimates.
    Reads from: model_runs + channel_coefficients tables.
    Returns empty channel list if no model has been trained yet.
    """
    return crud.get_latest_results(db)


@app.get("/model-runs", tags=["Model"])
def get_model_runs(db: Session = Depends(get_db)):
    """
    Returns all model runs ordered by most recent first.
    Reads from: model_runs table.
    """
    runs = crud.get_model_runs(db)
    return {"runs": runs}


@app.post("/retrain", tags=["Model"])
def trigger_retrain():
    """
    Triggers a model retrain in the DS container.
    Placeholder until Sprint 4 — DS runs the model manually for now.
    """
    return {"message": "Manual retrain required — run pipeline in DS container (Sprint 4 will automate this)"}


# ── Budget optimizer ──────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    total_budget: float
    constraints:  Optional[dict] = None    # e.g. {"tv": {"min": 5000, "max": 30000}}

@app.post("/optimize", tags=["Optimizer"])
def run_optimizer(req: OptimizeRequest, db: Session = Depends(get_db)):
    """
    Reads the latest channel ROI coefficients from the DB and returns
    the spend allocation that maximises predicted revenue.
    Falls back to equal split if no model results exist yet.
    """
    results  = crud.get_latest_results(db)
    channels = results.get("channels", [])

    # No model trained yet — return equal split as fallback
    if not channels:
        equal = round(req.total_budget / len(CHANNELS), 2)
        return {
            "total_budget":      req.total_budget,
            "note":              "No model results found — returning equal split as fallback",
            "allocation":        {ch: equal for ch in CHANNELS},
            "predicted_revenue": None,
        }

    roi_map    = {c["channel"]: c["roi_estimate"] or 0.0 for c in channels}
    roi_vector = np.array([roi_map.get(ch, 0.0) for ch in CHANNELS])

    def neg_revenue(spend_array):
        return -np.dot(roi_vector, spend_array)

    constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - req.total_budget}]

    bounds = []
    for ch in CHANNELS:
        lo, hi = 0.0, req.total_budget
        if req.constraints and ch in req.constraints:
            lo = req.constraints[ch].get("min", 0.0)
            hi = req.constraints[ch].get("max", req.total_budget)
        bounds.append((lo, hi))

    x0     = np.array([req.total_budget / len(CHANNELS)] * len(CHANNELS))
    result = opt.minimize(neg_revenue, x0, method="SLSQP",
                          bounds=bounds, constraints=constraints)

    return {
        "total_budget":      req.total_budget,
        "allocation":        {ch: round(float(v), 2) for ch, v in zip(CHANNELS, result.x)},
        "predicted_revenue": round(float(-result.fun), 2),
    }


# ── Scenarios ─────────────────────────────────────────────────────────────────

@app.get("/scenarios", tags=["Scenarios"])
def get_scenarios(db: Session = Depends(get_db)):
    """Returns all saved budget scenarios. Reads from: budget_scenarios table."""
    return {"scenarios": crud.get_all_scenarios(db)}


class ScenarioRequest(BaseModel):
    scenario_name:     str
    total_budget:      float
    allocation:        dict
    predicted_revenue: Optional[float] = None
    model_run_id:      Optional[int]   = None

@app.post("/scenarios", tags=["Scenarios"])
def save_scenario(req: ScenarioRequest, db: Session = Depends(get_db)):
    """Saves a budget allocation scenario. Writes to: budget_scenarios table."""
    saved = crud.save_scenario(
        db=db,
        scenario_name=req.scenario_name,
        total_budget=req.total_budget,
        allocation=req.allocation,
        predicted_revenue=req.predicted_revenue,
        model_run_id=req.model_run_id,
    )
    return {"message": "Scenario saved", "scenario": saved}


# ── Data summary ──────────────────────────────────────────────────────────────

@app.get("/data-summary", tags=["Data"])
def get_data_summary(db: Session = Depends(get_db)):
    """Returns date range and total spend per channel. Reads from: raw_spend_data."""
    return crud.get_spend_summary(db)


# ── PUT / DELETE scenarios (complete CRUD) ────────────────────────────────────

class ScenarioUpdateRequest(BaseModel):
    scenario_name:     Optional[str]   = None
    total_budget:      Optional[float] = None
    allocation:        Optional[dict]  = None
    predicted_revenue: Optional[float] = None

@app.put("/scenarios/{scenario_id}", tags=["Scenarios"])
def update_scenario(scenario_id: int, req: ScenarioUpdateRequest,
                    db: Session = Depends(get_db)):
    """Updates an existing scenario by ID. Writes to: budget_scenarios table."""
    updated = crud.update_scenario(db, scenario_id, req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"message": "Scenario updated", "scenario": updated}


@app.delete("/scenarios/{scenario_id}", tags=["Scenarios"])
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """Deletes a scenario by ID. Writes to: budget_scenarios table."""
    deleted = crud.delete_scenario(db, scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"message": f"Scenario {scenario_id} deleted"}
