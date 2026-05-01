"""
schemas.py
Pydantic request AND response models for all API endpoints.
FastAPI uses response_model= to validate output and generate typed Swagger docs.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Channel / Model results ───────────────────────────────────────────────────

class ChannelResult(BaseModel):
    channel:          str
    roi_estimate:     Optional[float] = Field(None, description="Revenue generated per $1 spent")
    contribution_pct: Optional[float] = Field(None, description="% of total attributed revenue")
    coefficient:      Optional[float] = Field(None, description="Raw OLS regression coefficient")
    recommendation:   Optional[str]   = Field(None, description="under-invested | over-invested | optimal")

class ModelResult(BaseModel):
    model_version: Optional[str]
    r_squared:     Optional[float] = Field(None, description="R² on held-out test set (higher is better)")
    run_at:        Optional[str]
    channels:      List[ChannelResult] = []

class ModelRunRecord(BaseModel):
    id:            int
    model_version: str
    status:        str
    r_squared:     Optional[float]
    run_at:        str
    notes:         Optional[str]

class ModelRunsResponse(BaseModel):
    runs: List[ModelRunRecord]


# ── Optimizer ─────────────────────────────────────────────────────────────────

class ChannelConstraint(BaseModel):
    min: float = 0.0
    max: Optional[float] = None

class OptimizeRequest(BaseModel):
    total_budget: float = Field(..., gt=0, description="Total marketing budget in USD")
    constraints:  Optional[dict] = Field(
        None,
        description="Per-channel min/max bounds. E.g. {\"tv\": {\"min\": 5000, \"max\": 30000}}"
    )

class OptimizeResponse(BaseModel):
    total_budget:      float
    allocation:        dict  = Field(..., description="Optimal spend per channel in USD")
    predicted_revenue: Optional[float] = Field(None, description="Predicted weekly revenue for this allocation")
    note:              Optional[str]   = None


# ── Scenarios ─────────────────────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario_name:     str   = Field(..., description="Human-readable name for this scenario")
    total_budget:      float = Field(..., gt=0)
    allocation:        dict  = Field(..., description="Per-channel spend amounts in USD")
    predicted_revenue: Optional[float] = None
    model_run_id:      Optional[int]   = None

class ScenarioUpdateRequest(BaseModel):
    scenario_name:     Optional[str]   = None
    total_budget:      Optional[float] = None
    allocation:        Optional[dict]  = None
    predicted_revenue: Optional[float] = None

class ScenarioRecord(BaseModel):
    id:                int
    scenario_name:     Optional[str]
    total_budget:      float
    allocation:        dict
    predicted_revenue: Optional[float]
    created_at:        str

class ScenariosResponse(BaseModel):
    scenarios: List[ScenarioRecord]

class ScenarioSaveResponse(BaseModel):
    message:  str
    scenario: ScenarioRecord


# ── Health / Data summary ─────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:   str
    service:  str
    database: str

class SpendByChannel(BaseModel):
    channel:     str
    total_spend: float

class DataSummaryResponse(BaseModel):
    first_week:       Optional[str]
    last_week:        Optional[str]
    total_weeks:      Optional[int]
    spend_by_channel: List[SpendByChannel]

class RetainResponse(BaseModel):
    message: str
    run_id:  Optional[int] = None
    status:  str
